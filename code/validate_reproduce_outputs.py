from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


def _load_json(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _dir_hash(paths) -> str:
    h = hashlib.sha256()
    for p in sorted(paths):
        if not p.is_file():
            continue
        h.update(str(p).encode("utf-8"))
        h.update(b"\0")
        h.update(_sha256_file(p).encode("ascii"))
        h.update(b"\0")
    return h.hexdigest()


def _validate_model_manifest() -> None:
    manifest_path = Path("results/paper/MODEL_RUN_MANIFEST.json")
    _assert(manifest_path.exists(), "MODEL_RUN_MANIFEST.json is missing")
    rows = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    _assert(isinstance(rows, list) and len(rows) == 11, "Expected 11 model manifest rows")
    required = {
        "model",
        "run_dir",
        "run_dir_sha256",
        "eval_json",
        "eval_json_sha256",
        "prompt_source",
        "prompt_source_sha256",
        "pred_na_policy",
        "exclude_audit_errors",
    }
    for row in rows:
        _assert(isinstance(row, dict), "Model manifest row is not an object")
        missing = required - set(row)
        _assert(not missing, f"Model manifest row missing keys for {row.get('model')}: {sorted(missing)}")

        eval_json = Path(str(row["eval_json"]))
        _assert(eval_json.exists(), f"Manifest eval_json missing for {row['model']}: {eval_json}")
        _assert(_sha256_file(eval_json) == row["eval_json_sha256"], f"eval_json hash mismatch for {row['model']}")

        # The manifest must point to the frozen prompt/rule artifact used for the
        # reported model outputs. Do not validate against the mutable working-tree
        # source, which may continue to evolve after the paper freeze.
        prompt_source = Path(str(row["prompt_source"]))
        _assert(prompt_source.exists(), f"Manifest prompt_source missing: {prompt_source}")
        _assert(_sha256_file(prompt_source) == row["prompt_source_sha256"], f"prompt_source hash mismatch for {row['model']}")

        run_dir = Path(str(row["run_dir"]))
        _assert(run_dir.exists() and run_dir.is_dir(), f"Manifest run_dir missing for {row['model']}: {run_dir}")
        run_files = sorted(run_dir.glob("case_gold_*.json"))
        _assert(len(run_files) == int(row["run_json_files"]), f"run_json_files mismatch for {row['model']}")
        _assert(_dir_hash(run_files) == row["run_dir_sha256"], f"run_dir hash mismatch for {row['model']}")


def main() -> int:
    gold_labels = Path("data/gold/labels/labels_final.jsonl")
    _assert(gold_labels.exists(), "Frozen Gold label file is missing")
    _assert(
        _sha256_file(gold_labels) == "fe26c03e3fe35405df13a88dbb9a4724717b41ad8c5b815479d71f796fdef9e9",
        "Frozen Gold SHA256 drifted from the authorized 2026-07-14 value",
    )
    gold = _load_json("results/paper/gold_dataset_summary.json")
    kappa = _load_json(
        "results/double_review_rerun/20260714_r2_return/gold/kappa_final_vs_new_r2.json"
    )
    tax = _load_json("results/paper/error_taxonomy/taxonomy_summary.json")
    eval_summary = _load_json("data/gold/gold_700/gold_eval_viz/gold_eval_models_summary.json")

    _assert(gold.get("n_labeled_cases") == 700 or gold.get("n_case_files") == 700, "Expected 700 gold cases")
    _assert(round(float((kappa.get("overall") or {}).get("kappa")), 3) == 0.992, "Expected pre-adjudication overall kappa 0.992")
    _assert((tax.get("totals") or {}).get("rows_labeled") == 214, "Expected taxonomy n=214")

    reanalysis = _load_json(
        "results/paper/dataset_composition_reanalysis_20260714/validation_report.json"
    )
    checks = reanalysis.get("checks") or []
    _assert(reanalysis.get("status") == "PASS", "Dataset-composition reanalysis did not pass")
    _assert(len(checks) == 148, f"Expected 148 reanalysis checks, found {len(checks)}")
    _assert(all(row.get("status") == "PASS" for row in checks), "A reanalysis validation check failed")

    with Path("results/paper/tables_supp/table_s16_source_composition.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as f:
        source_rows = list(csv.DictReader(f))
    _assert(
        {row["source_class"]: int(row["n_instances"]) for row in source_rows}
        == {
            "real_original": 20,
            "synthetic_original": 80,
            "real_derived": 120,
            "synthetic_derived": 480,
        },
        "Unexpected four-layer source composition",
    )
    public_aggregate_tables = [
        "table_s1_seed_cluster_bootstrap_selected.csv",
        "table_s16_source_composition.csv",
        "table_s17_gold_label_distribution_by_source.csv",
        "table_s18_model_performance_by_layer.csv",
        "table_s19_model_rule_performance_by_layer.csv",
        "table_s20_pairwise_seed_cluster_bootstrap.csv",
        "table_s21_human_review_sample_source_composition.csv",
        "table_s22_real_original_descriptive.csv",
    ]
    for name in public_aggregate_tables:
        path = Path("results/paper/tables_supp") / name
        _assert(path.exists() and path.stat().st_size > 0, f"Missing/empty aggregate table: {path}")
    _assert(
        not any("provenance_candidate_700" in p.name for p in Path("results/paper/tables_supp").glob("*")),
        "Controlled 700-row provenance was copied into the public supplementary-table directory",
    )

    table = Path("results/paper/tables/table_model_performance_summary.csv")
    with table.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    _assert(rows, "Model performance table is empty")
    top = rows[0]
    _assert(top["model"] == "gemini-3-pro-preview-thinking", f"Unexpected top model: {top['model']}")
    _assert(top["macro_f1"] == "0.984" and top["micro_f1"] == "0.982", "Unexpected top F1 values")

    for fig in [
        "results/paper/figures/fig_benchmark_composition.png",
        "results/paper/figures/fig_macro_micro_f1.png",
        "results/paper/figures/fig_f1_vs_evidence_grounding.png",
        "results/paper/figures/fig_model_rule_f1_heatmap.png",
        "results/paper/figures/fig_rule_distribution_and_kappa.png",
        "results/paper/figures_supp/fig_s9_taxonomy_by_rule_and_actionability.png",
    ]:
        _assert(Path(fig).exists() and Path(fig).stat().st_size > 0, f"Missing/empty figure: {fig}")

    models = eval_summary.get("models")
    _assert(isinstance(models, list) and len(models) == 11, "Expected 11 evaluated models")
    _validate_model_manifest()
    print("PASS: key reproduced outputs and model-manifest hashes match manuscript constants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
