from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def normalized_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    normalized = ["姓名:<SYNTHETIC_NAME_NORMALIZED>" if re.match(r"^姓名[：:]", line) else line for line in lines]
    return "\n".join(normalized).strip()


def main() -> int:
    lineage_path = ROOT / "data/synthetic_lineage.csv"
    with lineage_path.open(encoding="utf-8-sig", newline="") as handle:
        lineage = list(csv.DictReader(handle))
    if len(lineage) != 560:
        raise SystemExit(f"Expected 560 lineage rows, found {len(lineage)}")

    with tempfile.TemporaryDirectory(prefix="gej_public_synthetic_repro_") as tmp:
        tmp_path = Path(tmp)
        mock_out = tmp_path / "mock_cases_80"
        derived_out = tmp_path / "synthetic_variants_480"
        commands = [
            [
                sys.executable,
                str(ROOT / "code/generate_mock_cases.py"),
                "--n",
                "80",
                "--seed",
                "20251220",
                "--treatment_ratio",
                "0.6",
                "--out_dir",
                str(mock_out),
            ],
            [
                sys.executable,
                str(ROOT / "code/generate_perturbed_cases.py"),
                "--real_glob",
                "__NO_REAL_INPUT__/*.md",
                "--mock_dir",
                str(mock_out),
                "--out_dir",
                str(derived_out),
            ],
        ]
        for command in commands:
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
            if completed.returncode != 0:
                print(completed.stdout)
                print(completed.stderr, file=sys.stderr)
                return completed.returncode

        original_matches = 0
        derived_matches = 0
        mismatches: list[str] = []
        for row in lineage:
            archived = ROOT / row["case_filename"]
            if row["source_class"] == "synthetic_original":
                seed_number = int(row["synthetic_seed_id"].split("_", 1)[1])
                generated = mock_out / f"模拟病历{seed_number}.md"
                target = "original"
            elif row["source_class"] == "synthetic_derived":
                generated = derived_out / f"{row['synthetic_seed_id']}_{row['target_rule']}.md"
                target = "derived"
            else:
                mismatches.append(f"unexpected class:{row['case_id']}")
                continue
            if not generated.is_file() or not archived.is_file():
                mismatches.append(f"missing:{row['case_id']}")
                continue
            if normalized_text(generated) != normalized_text(archived):
                mismatches.append(f"text:{row['case_id']}")
            elif target == "original":
                original_matches += 1
            else:
                derived_matches += 1

    result = {
        "status": "PASS" if not mismatches and original_matches == 80 and derived_matches == 480 else "FAIL",
        "synthetic_original_text_matches": original_matches,
        "synthetic_derived_text_matches": derived_matches,
        "mismatches": mismatches[:20],
        "real_record_inputs_used": 0,
        "comparison_normalization": "universal newlines and synthetic name field",
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
