from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any


EXPECTED_GOLD_SHA256 = "fe26c03e3fe35405df13a88dbb9a4724717b41ad8c5b815479d71f796fdef9e9"
EXPECTED_CASES = 560
EXPECTED_SYSTEMS = 11
EXPECTED_OUTPUTS = 6160
EXPECTED_LICENSE_FILES = {
    "LICENSE.md",
    "LICENSE-CODE-MIT.txt",
    "LICENSE-DATA-DOCS-CC-BY-4.0.md",
}
TEXT_SUFFIXES = {".md", ".txt", ".csv", ".json", ".jsonl", ".py", ".cff", ".sha256"}
FORBIDDEN_PATH_TOKENS = {
    ".git",
    ".ds_store",
    ".env",
    "appendix_b",
    "real_cases",
    "real_derived",
    "patient_cluster",
    "few_shot_examples",
    "adjudication",
    "reviewer_worklist",
}
PATTERNS = {
    "local_path": re.compile("/" + "Users/" + r"|[A-Za-z]:\\" + "Users" + r"\\"),
    "private_key": re.compile(r"BEGIN (?:RSA|OPENSSH|EC|DSA) PRIVATE KEY"),
    "openai_style_key": re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    "api_key_assignment": re.compile(r"(?i)\bapi[_-]?key\s*[:=]\s*['\"][^'\"]+"),
}
CASE_PATTERN = re.compile(r"\bgold_(\d{4})\b")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def allowed_case_id(case_id: str) -> bool:
    if not case_id.startswith("gold_") or len(case_id) != 9:
        return False
    try:
        number = int(case_id[5:])
    except ValueError:
        return False
    return 21 <= number <= 100 or 221 <= number <= 700


def label_status(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("status", "")
    return str(value or "").strip().upper()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = root / "release_manifest.json"
    if not manifest_path.is_file():
        return ["release_manifest.json missing"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_constants = {
        "status": "PRIVATE_REMOTE_STAGING_PUBLICATION_DEFERRED_UNTIL_SUBMISSION",
        "source_canonical_gold_sha256": EXPECTED_GOLD_SHA256,
        "institutional_synthetic_scope_confirmed": True,
        "remote_repository_visibility": "PRIVATE",
        "private_remote_staging_authorized": True,
        "remote_publication_deferred_until_submission": True,
        "synthetic_provenance_label": "script-generated synthetic records",
        "synthetic_originals": 80,
        "synthetic_derived": 480,
        "synthetic_cases": EXPECTED_CASES,
        "systems": EXPECTED_SYSTEMS,
        "consolidated_output_files": EXPECTED_SYSTEMS,
        "frozen_output_records": EXPECTED_OUTPUTS,
        "licensing": {
            "approved": True,
            "code_and_python_methods": "MIT",
            "synthetic_data_outputs_evidence_and_documentation": "CC BY 4.0",
            "licence_map": "LICENSE.md",
        },
    }
    for key, value in expected_constants.items():
        if manifest.get(key) != value:
            errors.append(f"manifest constant {key}: expected {value!r}, found {manifest.get(key)!r}")

    expected_files = {row["path"]: row for row in manifest.get("files", [])}
    actual_files = {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if path.is_file()
        and path.name not in {"release_manifest.json", "MANIFEST.sha256"}
        and ".git" not in path.relative_to(root).parts
    }
    if set(expected_files) != set(actual_files):
        errors.append(
            f"manifest coverage mismatch: missing={sorted(set(expected_files)-set(actual_files))[:20]}, "
            f"extra={sorted(set(actual_files)-set(expected_files))[:20]}"
        )
    for relative, row in expected_files.items():
        path = actual_files.get(relative)
        if path and (path.stat().st_size != row["bytes"] or sha256(path) != row["sha256"]):
            errors.append(f"hash/size mismatch: {relative}")

    sha_lines = (root / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines()
    sha_entries: dict[str, str] = {}
    for line in sha_lines:
        if "  " not in line:
            errors.append(f"bad SHA256 line: {line}")
            continue
        digest, relative = line.split("  ", 1)
        sha_entries[relative] = digest
    expected_sha_paths = set(expected_files) | {"release_manifest.json"}
    if set(sha_entries) != expected_sha_paths:
        errors.append("MANIFEST.sha256 coverage mismatch")
    for relative, digest in sha_entries.items():
        path = root / relative
        if not path.is_file() or sha256(path) != digest:
            errors.append(f"MANIFEST.sha256 mismatch: {relative}")

    for relative, path in actual_files.items():
        lower = relative.lower()
        parts = {part.lower() for part in Path(relative).parts}
        exact_tokens = {".git", ".ds_store", ".env"}
        substring_tokens = FORBIDDEN_PATH_TOKENS - exact_tokens
        if parts & exact_tokens or any(token in lower for token in substring_tokens):
            errors.append(f"forbidden path: {relative}")
        if path.stat().st_size > 50 * 1024 * 1024:
            errors.append(f"file exceeds 50 MiB: {relative}")
        if path.suffix.lower() in TEXT_SUFFIXES or path.name == ".gitignore":
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            for label, pattern in PATTERNS.items():
                if pattern.search(text):
                    errors.append(f"{label}: {relative}")
            lowered = text.lower()
            stale_phrases = {
                "fully " + "synthetic",
                "record-" + "informed synthetic",
                "do not " + "publish",
            }
            for phrase in stale_phrases:
                if phrase in lowered:
                    errors.append(f"stale publication wording {phrase!r}: {relative}")
            for match in CASE_PATTERN.finditer(text):
                case_id = f"gold_{match.group(1)}"
                if not allowed_case_id(case_id):
                    errors.append(f"non-synthetic case ID {case_id}: {relative}")
                    break

    cases = sorted((root / "data/synthetic_cases").glob("gold_*.md"))
    case_ids = {path.stem for path in cases}
    if len(cases) != EXPECTED_CASES or any(not allowed_case_id(case_id) for case_id in case_ids):
        errors.append(f"synthetic case coverage/whitelist mismatch: {len(cases)}")

    gold = load_jsonl(root / "data/synthetic_gold_normalized.jsonl")
    gold_ids = {str(row.get("case_id", "")) for row in gold}
    if len(gold) != EXPECTED_CASES or gold_ids != case_ids:
        errors.append(f"synthetic Gold mismatch: rows={len(gold)}, id_delta={len(gold_ids ^ case_ids)}")
    for row in gold:
        labels = row.get("labels", {})
        if set(labels) != {"H1", "H2", "H3", "H4", "H5", "H6"} or any(
            label_status(labels[rule]) not in {"PASS", "FAIL", "NA"} for rule in labels
        ):
            errors.append(f"invalid Gold labels: {row.get('case_id')}")
            break

    with (root / "data/synthetic_lineage.csv").open(encoding="utf-8-sig", newline="") as handle:
        lineage = list(csv.DictReader(handle))
    lineage_ids = {row.get("case_id", "") for row in lineage}
    if len(lineage) != EXPECTED_CASES or lineage_ids != case_ids:
        errors.append(f"lineage mismatch: rows={len(lineage)}, id_delta={len(lineage_ids ^ case_ids)}")
    if lineage and any("patient_cluster" in field.lower() for field in lineage[0]):
        errors.append("patient-cluster field present in lineage")
    classes = {row.get("source_class", "") for row in lineage}
    if classes != {"synthetic_original", "synthetic_derived"}:
        errors.append(f"unexpected lineage classes: {sorted(classes)}")

    output_files = sorted((root / "outputs/frozen_parsed_jsonl").glob("*.jsonl"))
    if len(output_files) != EXPECTED_SYSTEMS:
        errors.append(f"expected {EXPECTED_SYSTEMS} output JSONL files, found {len(output_files)}")
    output_records = 0
    models: set[str] = set()
    for path in output_files:
        rows = load_jsonl(path)
        output_records += len(rows)
        ids = {str(row.get("case_id", "")) for row in rows}
        row_models = {str(row.get("model", "")) for row in rows}
        models.update(row_models)
        if len(rows) != EXPECTED_CASES or ids != case_ids:
            errors.append(f"output coverage mismatch: {path.name}")
        if row_models != {path.stem}:
            errors.append(f"output model mismatch: {path.name} -> {sorted(row_models)}")
        if any("source_path" in row or "report_markdown" in row for row in rows):
            errors.append(f"internal output key present: {path.name}")
    if output_records != EXPECTED_OUTPUTS or len(models) != EXPECTED_SYSTEMS:
        errors.append(f"output totals mismatch: records={output_records}, models={len(models)}")

    aggregate_files = [
        path
        for directory in (root / "data/aggregate", root / "data/tables", root / "data/tables_supp")
        for path in directory.glob("*")
        if path.is_file()
    ]
    if len(aggregate_files) != 20:
        errors.append(f"expected 20 aggregate data/table files, found {len(aggregate_files)}")
    publication_figures = list((root / "figures/main").glob("*.png")) + list(
        (root / "figures/supplementary").glob("*.png")
    )
    if len(publication_figures) != 14:
        errors.append(f"expected 14 publication PNG files, found {len(publication_figures)}")
    if not (root / "code/generate_main_figures.py").is_file():
        errors.append("aggregate-input figure reproduction script missing")

    with (root / "data/tables_supp/table_predicted_na_rates.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        predicted_na = sum(int(row["pred_na_count_on_gold_applicable"]) for row in csv.DictReader(handle))
    if predicted_na != 37:
        errors.append(f"expected 37 gold-applicable predicted-NA outputs, got {predicted_na}")
    with (root / "data/aggregate/model_run_manifest_public.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        aggregate_models = list(csv.DictReader(handle))
    if len(aggregate_models) != EXPECTED_SYSTEMS or any(
        int(row["total_rule_pairs_eval"]) != 3328 for row in aggregate_models
    ):
        errors.append("aggregate model manifest constants mismatch")

    status = json.loads((root / "PUBLICATION_STATUS.json").read_text(encoding="utf-8"))
    if status.get("status") != "PRIVATE_REMOTE_STAGING_PUBLICATION_DEFERRED_UNTIL_SUBMISSION":
        errors.append("private remote-staging deferred-publication status is missing")
    if status.get("remote_repository_visibility") != "PRIVATE":
        errors.append("private remote-staging visibility marker is missing")
    if status.get("private_remote_staging_authorized") is not True:
        errors.append("private remote staging authorization is missing")
    if status.get("ready_for_remote_publish") is not False:
        errors.append("remote publication must remain disabled until submission")
    if status.get("remote_visibility_change_authorized_now") is not False:
        errors.append("remote visibility change must remain unauthorized until submission")
    if status.get("publication_timing") != "AUTHOR_CONTROLLED_AT_SUBMISSION":
        errors.append("author-controlled submission-time publication gate is missing")
    if status.get("institutional_synthetic_scope_confirmed") is not True:
        errors.append("institutional synthetic-scope confirmation is missing")
    if status.get("licensing_approved") is not True:
        errors.append("approved licensing status missing")
    if status.get("code_license") != "MIT":
        errors.append("code licence must be MIT")
    if status.get("data_documentation_license") != "CC BY 4.0":
        errors.append("data/documentation licence must be CC BY 4.0")
    blockers = set(status.get("remaining_blockers", []))
    if blockers != {"PUBLICATION_DEFERRED_UNTIL_SUBMISSION"}:
        errors.append(f"unexpected publication blockers: {sorted(blockers)}")

    missing_licences = sorted(name for name in EXPECTED_LICENSE_FILES if not (root / name).is_file())
    if missing_licences:
        errors.append(f"approved licence files missing: {missing_licences}")
    if (root / "LICENSE_DECISION_REQUIRED.md").exists():
        errors.append("obsolete licence-decision blocker present")

    licence_map = (root / "LICENSE.md").read_text(encoding="utf-8") if (root / "LICENSE.md").is_file() else ""
    readme = (root / "README.md").read_text(encoding="utf-8") if (root / "README.md").is_file() else ""
    mit_text = (root / "LICENSE-CODE-MIT.txt").read_text(encoding="utf-8") if (root / "LICENSE-CODE-MIT.txt").is_file() else ""
    cc_text = (
        (root / "LICENSE-DATA-DOCS-CC-BY-4.0.md").read_text(encoding="utf-8")
        if (root / "LICENSE-DATA-DOCS-CC-BY-4.0.md").is_file()
        else ""
    )
    for label, text in {"README": readme, "licence map": licence_map}.items():
        if "MIT" not in text or "CC BY 4.0" not in text:
            errors.append(f"{label} does not state the MIT/CC BY 4.0 mapping")
    required_mit_clauses = [
        "Permission is hereby granted, free of charge",
        "THE SOFTWARE IS PROVIDED \"AS IS\"",
    ]
    if any(clause not in mit_text for clause in required_mit_clauses):
        errors.append("MIT licence text is incomplete")
    cc_text_normalized = " ".join(cc_text.split())
    required_cc_markers = [
        "Creative Commons Attribution 4.0 International",
        "https://creativecommons.org/licenses/by/4.0/",
        "https://creativecommons.org/licenses/by/4.0/legalcode",
    ]
    if any(marker not in cc_text_normalized for marker in required_cc_markers):
        errors.append("CC BY 4.0 statement or official links are incomplete")

    data_availability = root / "DATA_AVAILABILITY.md"
    if not data_availability.is_file():
        errors.append("DATA_AVAILABILITY.md missing")
    else:
        availability_text = data_availability.read_text(encoding="utf-8")
        required_availability_markers = [
            "80 script-generated synthetic original records",
            "480 synthetic-derived variants",
            "20 de-identified real original clinical notes",
            "120 real-derived variants",
            "v1.0-submission",
        ]
        if any(marker not in availability_text for marker in required_availability_markers):
            errors.append("data-availability public/restricted mapping is incomplete")

    old_route_files = {
        "table_pairwise_comparisons.csv",
        "table_pairwise_comparisons_by_rule.csv",
        ".DS_Store",
        "LICENSES_PENDING.md",
        "LICENSE_DECISION_REQUIRED.md",
    }
    present_names = {path.name for path in root.rglob("*") if path.is_file()}
    for name in sorted(old_route_files & present_names):
        errors.append(f"obsolete or forbidden legacy file present: {name}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the local pre-publication GitHub candidate.")
    parser.add_argument("--candidate", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    root = args.candidate.resolve()
    errors = validate(root)
    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    manifest = json.loads((root / "release_manifest.json").read_text(encoding="utf-8"))
    print(
        "PASS: "
        f"{len(manifest['files'])} manifested files; "
        f"{manifest['synthetic_cases']} synthetic cases; "
        f"{manifest['systems']} systems; "
        f"{manifest['frozen_output_records']} frozen output records; "
        "authorized content scope; remote publication deferred until submission"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
