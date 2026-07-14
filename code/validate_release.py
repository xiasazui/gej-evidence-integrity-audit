from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_NAMES = {".env", ".DS_Store"}
FORBIDDEN_PARTS = {"cases", "reviewer", "adjudication", "appendix_b", "submission"}
PATTERNS = {
    "local_path": re.compile(r"/" + r"Users/|[A-Za-z]:\\" + r"Users\\"),
    "internal_case_id": re.compile(r"\bgold_\d{4}\b"),
    "private_key": re.compile(r"BEGIN (?:RSA|OPENSSH|EC|DSA) PRIVATE KEY"),
    "openai_style_key": re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
}

def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def main() -> int:
    manifest = json.loads((ROOT / "release_manifest.json").read_text(encoding="utf-8"))
    expected = {row["path"]: row for row in manifest["files"]}
    actual = {
        p.relative_to(ROOT).as_posix(): p
        for p in ROOT.rglob("*")
        if p.is_file() and p.name not in {"release_manifest.json", "MANIFEST.sha256"}
    }
    errors: list[str] = []
    if set(expected) != set(actual):
        errors.append(f"manifest coverage mismatch: missing={sorted(set(expected)-set(actual))}, extra={sorted(set(actual)-set(expected))}")
    for rel, row in expected.items():
        path = actual.get(rel)
        if path and (path.stat().st_size != row["bytes"] or digest(path) != row["sha256"]):
            errors.append(f"hash/size mismatch: {rel}")
    for rel, path in actual.items():
        parts = {part.lower() for part in Path(rel).parts}
        if path.name in FORBIDDEN_NAMES or parts & FORBIDDEN_PARTS:
            errors.append(f"forbidden path: {rel}")
        if path.stat().st_size > 50 * 1024 * 1024:
            errors.append(f"file exceeds 50 MiB: {rel}")
        if path.suffix.lower() in {".md", ".txt", ".csv", ".json", ".py", ".cff"}:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            for label, pattern in PATTERNS.items():
                if pattern.search(text):
                    errors.append(f"{label}: {rel}")
    with (ROOT / "data/tables_supp/table_predicted_na_rates.csv").open(encoding="utf-8-sig", newline="") as f:
        pred_na = sum(int(row["pred_na_count_on_gold_applicable"]) for row in csv.DictReader(f))
    if pred_na != 37:
        errors.append(f"expected 37 gold-applicable predicted-NA outputs, got {pred_na}")
    with (ROOT / "data/aggregate/model_run_manifest_public.csv").open(encoding="utf-8-sig", newline="") as f:
        models = list(csv.DictReader(f))
    if len(models) != 11 or any(int(row["total_rule_pairs_eval"]) != 3328 for row in models):
        errors.append("model manifest constants mismatch")
    taxonomy_rows = 0
    for path in (ROOT / "data/taxonomy_redacted").glob("*.csv"):
        with path.open(encoding="utf-8-sig", newline="") as f:
            taxonomy_rows += sum(1 for _ in csv.DictReader(f))
    if taxonomy_rows != 214:
        errors.append(f"expected 214 redacted taxonomy rows, got {taxonomy_rows}")
    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"PASS: {len(actual)} files; 11 models; 37 predicted-NA; 214 redacted taxonomy rows")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
