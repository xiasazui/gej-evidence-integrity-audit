from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
RULES = ["H1", "H2", "H3", "H4", "H5", "H6"]
DISPLAY_ORDER = [
    ("deepseek-v3.2-thinking", "DeepSeek"),
    ("gemini-3-pro-preview-thinking", "Gemini"),
    ("gpt-5.2", "GPT-5.2"),
    ("gpt-oss-20b", "GPT-OSS-20B"),
    ("gpt-oss-120b", "GPT-OSS-120B"),
    ("kimi-k2-thinking", "Kimi"),
    ("MiniMax-M2.1", "MiniMax"),
    ("qwen3-30b-a3b-thinking-2507", "Qwen3-30B"),
    ("qwen3-235b-a22b-thinking-2507", "Qwen3-235B"),
    ("qwen3-next-80b-a3b-thinking", "Qwen3-Next"),
    ("deterministic-baseline", "Regex"),
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def safe_div(num: int, den: int) -> float | None:
    return num / den if den else None


def fmt(value: float | None, digits: int = 6) -> str:
    return "" if value is None else f"{value:.{digits}f}"


def normalize_status(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("status")
    status = str(value or "").strip().upper()
    return "NA" if status in {"N/A", "NOT_APPLICABLE", "NOT-APPLICABLE"} else status


def model_metrics_for_cases(
    gold: dict[str, dict[str, str]],
    pred: dict[str, dict[str, str]],
    case_ids: set[str],
) -> tuple[float | None, float | None, int]:
    per_rule_f1: list[float] = []
    micro = [0, 0, 0]  # tp, fp, fn
    n_pairs = 0
    for rule in RULES:
        tp = fp = fn = 0
        for case_id in case_ids:
            g = gold.get(case_id, {}).get(rule)
            p = pred.get(case_id, {}).get(rule)
            if g not in {"PASS", "FAIL"} or p not in {"PASS", "FAIL", "NA"}:
                continue
            if p == "NA":
                p = "PASS"
            n_pairs += 1
            if g == "FAIL" and p == "FAIL":
                tp += 1
            elif g == "PASS" and p == "FAIL":
                fp += 1
            elif g == "FAIL" and p == "PASS":
                fn += 1
        denominator = 2 * tp + fp + fn
        if denominator:
            per_rule_f1.append(2 * tp / denominator)
        micro[0] += tp
        micro[1] += fp
        micro[2] += fn
    macro = sum(per_rule_f1) / len(per_rule_f1) if per_rule_f1 else None
    micro_den = 2 * micro[0] + micro[1] + micro[2]
    micro_f1 = 2 * micro[0] / micro_den if micro_den else None
    return macro, micro_f1, n_pairs


def load_predictions(path: Path) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in load_jsonl(path):
        by_rule: dict[str, str] = {}
        for result in row.get("rule_results", []):
            rule = str(result.get("rule_id") or "")
            status = normalize_status(result.get("status"))
            if rule in RULES and status in {"PASS", "FAIL", "NA"}:
                by_rule[rule] = status
        out[str(row.get("case_id") or "")] = by_rule
    return out


def build_kappa(constants: dict[str, Any]) -> None:
    kappa = dict(constants["kappa"])
    kappa["rules"] = RULES
    kappa["canonical_release"] = constants["canonical_release"]
    kappa["precision_note"] = "Kappa values are the frozen, manuscript-reported values; reviewer-level records are restricted."
    out = ROOT / "data/aggregate/kappa_summary.json"
    out.write_text(json.dumps(kappa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_evidence_tables(constants: dict[str, Any]) -> None:
    source = ROOT / constants["evidence"]["full_700_aggregate_source"]
    rows = load_csv(source)
    endpoints: dict[str, dict[str, Any]] = {}
    endpoint_rows: list[dict[str, Any]] = []
    for row in rows:
        model = row["model"]
        fail_outputs = int(row["fail_outputs"])
        empty = int(row["fail_outputs_empty_evidence"])
        items = int(row["evidence_items_total"])
        recovered_items = int(row["evidence_items_recoverable"])
        all_recovered_outputs = int(row["fail_outputs_all_snippets_recoverable"])
        coverage = safe_div(fail_outputs - empty, fail_outputs)
        conditional = safe_div(recovered_items, items)
        strict = safe_div(all_recovered_outputs, fail_outputs)
        mean_snippets = safe_div(items, fail_outputs)
        values = {
            "predicted_fail_outputs": fail_outputs,
            "outputs_with_nonempty_evidence": fail_outputs - empty,
            "returned_evidence_items": items,
            "recoverable_evidence_items": recovered_items,
            "outputs_all_snippets_recoverable": all_recovered_outputs,
            "evidence_coverage": coverage,
            "conditional_item_recoverability": conditional,
            "all_snippet_recoverability": strict,
            "mean_snippets_per_predicted_fail": mean_snippets,
        }
        endpoints[model] = values
        endpoint_rows.append(
            {
                "model": model,
                **{key: value for key, value in values.items() if isinstance(value, int)},
                "evidence_coverage": fmt(coverage),
                "conditional_item_recoverability": fmt(conditional),
                "all_snippet_recoverability": fmt(strict),
                "mean_snippets_per_predicted_fail": fmt(mean_snippets),
                "analysis_set": constants["evidence"]["primary_analysis_set"],
                "record_level_recomputed_in_public_package": "no",
            }
        )

    endpoint_fields = [
        "model",
        "predicted_fail_outputs",
        "outputs_with_nonempty_evidence",
        "returned_evidence_items",
        "recoverable_evidence_items",
        "outputs_all_snippets_recoverable",
        "evidence_coverage",
        "conditional_item_recoverability",
        "all_snippet_recoverability",
        "mean_snippets_per_predicted_fail",
        "analysis_set",
        "record_level_recomputed_in_public_package",
    ]
    write_csv(ROOT / "data/tables_supp/table_evidence_endpoints_full700_aggregate.csv", endpoint_fields, endpoint_rows)

    eval_path = ROOT / "data/aggregate/gold_eval_models_summary.json"
    eval_summary = load_json(eval_path)
    models = list(eval_summary["models"])
    eval_summary["evidence_endpoints"] = {
        "analysis_set": constants["evidence"]["primary_analysis_set"],
        "record_level_recomputed_in_public_package": False,
        "evidence_coverage": [endpoints[model]["evidence_coverage"] for model in models],
        "conditional_item_recoverability": [endpoints[model]["conditional_item_recoverability"] for model in models],
        "all_snippet_recoverability": [endpoints[model]["all_snippet_recoverability"] for model in models],
        "mean_snippets_per_predicted_fail": [endpoints[model]["mean_snippets_per_predicted_fail"] for model in models],
    }
    eval_summary["evidence_in_text_rate"] = eval_summary["evidence_endpoints"]["conditional_item_recoverability"]
    eval_path.write_text(json.dumps(eval_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    old_table = {row["model"]: row for row in load_csv(ROOT / "data/tables_supp/table_model_rule_performance_full.csv")}
    summary_rows: list[dict[str, Any]] = []
    for model, display in DISPLAY_ORDER:
        old = old_table[model]
        weak_rule = min(RULES, key=lambda rule: float(old[f"{rule}_f1"]))
        summary_rows.append(
            {
                "model": display,
                "model_identifier": model,
                "macro_f1": old["macro_f1"],
                "micro_f1": old["micro_f1"],
                "evidence_coverage": fmt(endpoints[model]["evidence_coverage"], 3),
                "conditional_item_recoverability": fmt(endpoints[model]["conditional_item_recoverability"], 3),
                "all_snippet_recoverability": fmt(endpoints[model]["all_snippet_recoverability"], 3),
                "mean_snippets_per_predicted_fail": fmt(endpoints[model]["mean_snippets_per_predicted_fail"], 2),
                "weak_rule": weak_rule,
                "weak_f1": old[f"{weak_rule}_f1"],
            }
        )
    summary_fields = [
        "model",
        "model_identifier",
        "macro_f1",
        "micro_f1",
        "evidence_coverage",
        "conditional_item_recoverability",
        "all_snippet_recoverability",
        "mean_snippets_per_predicted_fail",
        "weak_rule",
        "weak_f1",
    ]
    write_csv(ROOT / "data/tables/table_model_performance_summary.csv", summary_fields, summary_rows)


def build_operator_family_sensitivity() -> None:
    gold = {row["case_id"]: {rule: normalize_status(value) for rule, value in row["labels"].items()} for row in load_jsonl(ROOT / "data/synthetic_gold_normalized.jsonl")}
    lineage = load_csv(ROOT / "data/synthetic_lineage.csv")
    families: dict[str, set[str]] = defaultdict(set)
    for row in lineage:
        case_id = row["case_id"]
        source_class = row["source_class"]
        target = row["target_rule"]
        if source_class == "synthetic_original":
            families["original"].add(case_id)
        elif target == "H2":
            families["H2-derived"].add(case_id)
        elif target == "H4":
            families["H4-derived"].add(case_id)
        else:
            families["other-derived"].add(case_id)
        families["pooled-public-synthetic"].add(case_id)

    rows: list[dict[str, Any]] = []
    for model, display in DISPLAY_ORDER:
        pred = load_predictions(ROOT / "outputs/frozen_parsed_jsonl" / f"{model}.jsonl")
        for family in ["original", "H2-derived", "H4-derived", "other-derived", "pooled-public-synthetic"]:
            case_ids = families[family]
            macro, micro, pairs = model_metrics_for_cases(gold, pred, case_ids)
            rows.append(
                {
                    "operator_family": family,
                    "model": display,
                    "model_identifier": model,
                    "n_cases": len(case_ids),
                    "n_gold_applicable_pairs": pairs,
                    "macro_f1": fmt(macro),
                    "micro_f1": fmt(micro),
                    "analysis_scope": "public synthetic layer only",
                }
            )
    write_csv(
        ROOT / "data/tables_supp/table_operator_family_sensitivity_public_synthetic.csv",
        ["operator_family", "model", "model_identifier", "n_cases", "n_gold_applicable_pairs", "macro_f1", "micro_f1", "analysis_scope"],
        rows,
    )


def build_source_composition(constants: dict[str, Any]) -> None:
    rows = []
    for source_class in ["real_original", "synthetic_original", "real_derived", "synthetic_derived"]:
        values = constants["composition"][source_class]
        rows.append(
            {
                "source_class": source_class,
                "n_instances": values["n_instances"],
                "n_unique_seeds": values["n_unique_seeds"],
                "record_level_public": "yes" if source_class.startswith("synthetic_") else "no",
            }
        )
    write_csv(
        ROOT / "data/tables_supp/table_s16_source_composition.csv",
        ["source_class", "n_instances", "n_unique_seeds", "record_level_public"],
        rows,
    )


def main() -> int:
    constants = load_json(ROOT / "data/canonical/v2_constants.json")
    build_kappa(constants)
    build_evidence_tables(constants)
    build_operator_family_sensitivity()
    build_source_composition(constants)
    print("rebuilt canonical V2 kappa, evidence endpoints, source composition, and public synthetic operator-family sensitivity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
