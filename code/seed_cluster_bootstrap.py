from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import numpy as np


RULES = ["H1", "H2", "H3", "H4", "H5", "H6"]
EXPECTED_CLUSTERS = 80
EXPECTED_CASES_PER_CLUSTER = 7
EXPECTED_CASES = 560


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def normalize_status(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("status")
    status = str(value or "").strip().upper()
    return "NA" if status in {"N/A", "NOT_APPLICABLE", "NOT-APPLICABLE"} else status


def load_gold(path: Path) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in load_jsonl(path):
        case_id = str(row.get("case_id") or "").strip()
        if not case_id:
            raise SystemExit(f"Gold row without case_id in {path}")
        if case_id in out:
            raise SystemExit(f"duplicate Gold case_id: {case_id}")
        labels = row.get("labels")
        if not isinstance(labels, dict):
            raise SystemExit(f"Gold labels are not an object for {case_id}")
        normalized = {rule: normalize_status(labels.get(rule)) for rule in RULES}
        invalid = {rule: status for rule, status in normalized.items() if status not in {"PASS", "FAIL", "NA"}}
        if invalid:
            raise SystemExit(f"invalid or missing Gold status for {case_id}: {invalid}")
        out[case_id] = normalized
    return out


def load_predictions(path: Path) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in load_jsonl(path):
        case_id = str(row.get("case_id") or "").strip()
        if not case_id:
            raise SystemExit(f"prediction row without case_id in {path}")
        if case_id in out:
            raise SystemExit(f"duplicate prediction case_id in {path}: {case_id}")
        results = row.get("rule_results")
        if not isinstance(results, list):
            raise SystemExit(f"rule_results is not a list in {path} for {case_id}")
        by_rule: dict[str, str] = {}
        for result in results:
            rule = str(result.get("rule_id") or "").strip()
            if rule not in RULES:
                continue
            if rule in by_rule:
                raise SystemExit(f"duplicate prediction rule in {path} for {case_id}: {rule}")
            by_rule[rule] = normalize_status(result.get("status"))
        missing_rules = set(RULES) - set(by_rule)
        invalid = {rule: status for rule, status in by_rule.items() if status not in {"PASS", "FAIL", "NA"}}
        if missing_rules or invalid:
            raise SystemExit(
                f"incomplete or invalid prediction rules in {path} for {case_id}: "
                f"missing={sorted(missing_rules)}, invalid={invalid}"
            )
        out[case_id] = by_rule
    return out


def load_seed_map(path: Path) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    seen_cases: dict[str, str] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or [])
        if "case_id" not in headers:
            raise SystemExit("seed map must contain a case_id column")
        if "synthetic_seed_id" in headers:
            seed_column = "synthetic_seed_id"
        elif "seed_id" in headers:
            seed_column = "seed_id"
        else:
            raise SystemExit("seed map must contain synthetic_seed_id or seed_id")
        for row in reader:
            seed_id = str(row.get(seed_column) or "").strip()
            case_id = str(row.get("case_id") or "").strip()
            if not seed_id or not case_id:
                raise SystemExit(f"seed map has an empty {seed_column} or case_id")
            if case_id in seen_cases:
                raise SystemExit(
                    f"seed map case_id appears more than once: {case_id} "
                    f"({seen_cases[case_id]}, {seed_id})"
                )
            seen_cases[case_id] = seed_id
            out.setdefault(seed_id, []).append(case_id)
    return out


def f1(gold: dict[str, dict[str, str]], pred: dict[str, dict[str, str]], sampled_cases: list[str]) -> tuple[float | None, float | None]:
    per_rule: list[float] = []
    micro_tp = micro_fp = micro_fn = 0
    for rule in RULES:
        tp = fp = fn = 0
        for case_id in sampled_cases:
            g = gold.get(case_id, {}).get(rule)
            p = pred.get(case_id, {}).get(rule)
            if g not in {"PASS", "FAIL"} or p not in {"PASS", "FAIL", "NA"}:
                continue
            if p == "NA":
                p = "PASS"
            if g == "FAIL" and p == "FAIL":
                tp += 1
            elif g == "PASS" and p == "FAIL":
                fp += 1
            elif g == "FAIL" and p == "PASS":
                fn += 1
        den = 2 * tp + fp + fn
        if den:
            per_rule.append(2 * tp / den)
        micro_tp += tp
        micro_fp += fp
        micro_fn += fn
    macro = sum(per_rule) / len(per_rule) if per_rule else None
    micro_den = 2 * micro_tp + micro_fp + micro_fn
    micro = 2 * micro_tp / micro_den if micro_den else None
    return macro, micro


def percentile(values: list[float], quantile: float) -> float:
    values = sorted(values)
    position = (len(values) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    fraction = position - lower
    return values[lower] + (values[upper] - values[lower]) * fraction


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Public synthetic 80-seed cluster percentile bootstrap for paired model F1 differences."
    )
    parser.add_argument("--gold", required=True)
    parser.add_argument(
        "--seed_map",
        required=True,
        help="Synthetic lineage CSV with synthetic_seed_id (or seed_id) and case_id columns",
    )
    parser.add_argument("--pred_a", required=True)
    parser.add_argument("--pred_b", required=True)
    parser.add_argument("--iterations", type=int, default=2000)
    parser.add_argument("--rng_seed", type=int, default=20460720)
    parser.add_argument("--out_json", required=True)
    args = parser.parse_args()

    if args.iterations < 1:
        raise SystemExit("iterations must be at least 1")

    gold = load_gold(Path(args.gold))
    seed_map = load_seed_map(Path(args.seed_map))
    pred_a = load_predictions(Path(args.pred_a))
    pred_b = load_predictions(Path(args.pred_b))
    if not seed_map:
        raise SystemExit("seed map is empty")

    if len(seed_map) != EXPECTED_CLUSTERS:
        raise SystemExit(f"public synthetic bootstrap requires {EXPECTED_CLUSTERS} seed clusters; found {len(seed_map)}")
    wrong_cluster_sizes = {seed_id: len(cases) for seed_id, cases in seed_map.items() if len(cases) != EXPECTED_CASES_PER_CLUSTER}
    if wrong_cluster_sizes:
        preview = list(sorted(wrong_cluster_sizes.items()))[:5]
        raise SystemExit(
            f"each public synthetic seed cluster must contain {EXPECTED_CASES_PER_CLUSTER} cases; "
            f"found {len(wrong_cluster_sizes)} invalid clusters; first={preview}"
        )

    mapped_cases = {case_id for cases in seed_map.values() for case_id in cases}
    if len(mapped_cases) != EXPECTED_CASES:
        raise SystemExit(f"public synthetic bootstrap requires {EXPECTED_CASES} unique mapped cases; found {len(mapped_cases)}")
    for label, cases in (("Gold", set(gold)), ("pred_a", set(pred_a)), ("pred_b", set(pred_b))):
        missing = sorted(mapped_cases - cases)
        extra = sorted(cases - mapped_cases)
        if missing or extra:
            raise SystemExit(
                f"{label} case coverage does not exactly match the public synthetic seed map: "
                f"missing={len(missing)} first={missing[:3]}, extra={len(extra)} first={extra[:3]}"
            )

    seed_ids = sorted(seed_map)
    rng = np.random.Generator(np.random.PCG64(args.rng_seed))
    cluster_probabilities = np.full(len(seed_ids), 1.0 / len(seed_ids))
    macro_deltas: list[float] = []
    micro_deltas: list[float] = []
    for _ in range(args.iterations):
        sampled_cases: list[str] = []
        cluster_counts = rng.multinomial(len(seed_ids), cluster_probabilities)
        for seed_id, count in zip(seed_ids, cluster_counts):
            sampled_cases.extend(seed_map[seed_id] * int(count))
        macro_a, micro_a = f1(gold, pred_a, sampled_cases)
        macro_b, micro_b = f1(gold, pred_b, sampled_cases)
        if macro_a is not None and macro_b is not None:
            macro_deltas.append(macro_a - macro_b)
        if micro_a is not None and micro_b is not None:
            micro_deltas.append(micro_a - micro_b)

    observed_cases = [case_id for seed_id in seed_ids for case_id in seed_map[seed_id]]
    observed_macro_a, observed_micro_a = f1(gold, pred_a, observed_cases)
    observed_macro_b, observed_micro_b = f1(gold, pred_b, observed_cases)
    result = {
        "analysis_scope": "public synthetic layer only",
        "ordinary_mcnemar_used": False,
        "cluster_unit": "seed",
        "cluster_resampling": "PCG64 multinomial weights",
        "n_clusters": len(seed_ids),
        "n_instances": len(observed_cases),
        "iterations": args.iterations,
        "rng_seed": args.rng_seed,
        "predicted_na_policy": "as_pass",
        "macro_f1_delta_a_minus_b": None if observed_macro_a is None or observed_macro_b is None else observed_macro_a - observed_macro_b,
        "macro_f1_delta_ci95": None if not macro_deltas else [percentile(macro_deltas, 0.025), percentile(macro_deltas, 0.975)],
        "micro_f1_delta_a_minus_b": None if observed_micro_a is None or observed_micro_b is None else observed_micro_a - observed_micro_b,
        "micro_f1_delta_ci95": None if not micro_deltas else [percentile(micro_deltas, 0.025), percentile(micro_deltas, 0.975)],
        "valid_macro_replicates": len(macro_deltas),
        "valid_micro_replicates": len(micro_deltas),
    }
    out = Path(args.out_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"wrote": str(out), "n_clusters": len(seed_ids)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
