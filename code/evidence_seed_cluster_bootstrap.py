from __future__ import annotations

import argparse
import csv
import json
import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


RULES = {"H1", "H2", "H3", "H4", "H5", "H6"}
COUNT_FIELDS = [
    "predicted_fail_outputs",
    "outputs_with_nonempty_evidence",
    "returned_evidence_items",
    "recoverable_evidence_items",
    "outputs_all_snippets_recoverable",
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def status_value(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("status")
    return str(value or "").strip().upper().replace("N/A", "NA")


def load_gold(path: Path) -> dict[str, dict[str, str]]:
    return {
        str(row["case_id"]): {rule: status_value(value) for rule, value in row.get("labels", {}).items()}
        for row in load_jsonl(path)
    }


def load_seed_map(path: Path) -> dict[str, list[str]]:
    seeds: dict[str, list[str]] = defaultdict(list)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            seed = str(row.get("seed_id") or row.get("synthetic_seed_id") or "").strip()
            case_id = str(row.get("case_id") or "").strip()
            if seed and case_id:
                seeds[seed].append(case_id)
    if not seeds:
        raise SystemExit("seed map is empty or lacks seed_id/synthetic_seed_id and case_id")
    return dict(seeds)


def normalize_text(value: Any) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\s+", "", text).casefold()


def evidence_items(result: dict[str, Any]) -> list[str]:
    raw = result.get("evidence")
    if raw is None:
        return []
    if not isinstance(raw, list):
        raw = [raw]
    return [str(item).strip() for item in raw if str(item or "").strip()]


def empty_counts() -> dict[str, int]:
    return {field: 0 for field in COUNT_FIELDS}


def add_counts(target: dict[str, int], source: dict[str, int]) -> None:
    for field in COUNT_FIELDS:
        target[field] += source[field]


def endpoint_values(counts: dict[str, int]) -> dict[str, float | None]:
    fail = counts["predicted_fail_outputs"]
    items = counts["returned_evidence_items"]
    return {
        "evidence_coverage": counts["outputs_with_nonempty_evidence"] / fail if fail else None,
        "conditional_item_recoverability": counts["recoverable_evidence_items"] / items if items else None,
        "all_snippet_recoverability": counts["outputs_all_snippets_recoverable"] / fail if fail else None,
        "mean_snippets_per_predicted_fail": items / fail if fail else None,
    }


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def per_seed_counts(
    predictions: list[dict[str, Any]],
    cases_dir: Path,
    seed_map: dict[str, list[str]],
    gold: dict[str, dict[str, str]],
) -> dict[str, dict[str, dict[str, int]]]:
    case_to_seed = {case_id: seed for seed, case_ids in seed_map.items() for case_id in case_ids}
    case_text = {
        case_id: normalize_text((cases_dir / f"{case_id}.md").read_text(encoding="utf-8-sig"))
        for case_id in case_to_seed
    }
    counts = {
        seed: {"all_predicted_fail": empty_counts(), "gold_applicable_predicted_fail": empty_counts()}
        for seed in seed_map
    }
    seen_cases: set[str] = set()
    for row in predictions:
        case_id = str(row.get("case_id") or "")
        if case_id not in case_to_seed:
            continue
        if row.get("audit_error") or row.get("parse_error"):
            continue
        seen_cases.add(case_id)
        seed = case_to_seed[case_id]
        source = case_text[case_id]
        for result in row.get("rule_results", []):
            rule = str(result.get("rule_id") or "")
            if rule not in RULES or status_value(result.get("status")) != "FAIL":
                continue
            items = evidence_items(result)
            recovered = [normalize_text(item) in source for item in items]
            analysis_sets = ["all_predicted_fail"]
            if gold.get(case_id, {}).get(rule) in {"PASS", "FAIL"}:
                analysis_sets.append("gold_applicable_predicted_fail")
            for analysis_set in analysis_sets:
                bucket = counts[seed][analysis_set]
                bucket["predicted_fail_outputs"] += 1
                bucket["outputs_with_nonempty_evidence"] += int(bool(items))
                bucket["returned_evidence_items"] += len(items)
                bucket["recoverable_evidence_items"] += sum(recovered)
                bucket["outputs_all_snippets_recoverable"] += int(bool(items) and all(recovered))
    missing = sorted(set(case_to_seed) - seen_cases)
    if missing:
        raise SystemExit(f"predictions are missing {len(missing)} mapped cases; first={missing[:3]}")
    return counts


def bootstrap_model(
    model: str,
    counts: dict[str, dict[str, dict[str, int]]],
    iterations: int,
    rng_seed: int,
) -> list[dict[str, Any]]:
    seed_ids = sorted(counts)
    rows: list[dict[str, Any]] = []
    for analysis_index, analysis_set in enumerate(["all_predicted_fail", "gold_applicable_predicted_fail"]):
        observed = empty_counts()
        for seed in seed_ids:
            add_counts(observed, counts[seed][analysis_set])
        observed_values = endpoint_values(observed)
        distributions: dict[str, list[float]] = {key: [] for key in observed_values}
        rng = random.Random(rng_seed + analysis_index)
        for _ in range(iterations):
            sampled = empty_counts()
            for _position in seed_ids:
                add_counts(sampled, counts[rng.choice(seed_ids)][analysis_set])
            for endpoint, value in endpoint_values(sampled).items():
                if value is not None:
                    distributions[endpoint].append(value)
        row: dict[str, Any] = {
            "model": model,
            "analysis_set": analysis_set,
            "cluster_unit": "seed",
            "n_seed_clusters": len(seed_ids),
            "iterations": iterations,
            "rng_seed": rng_seed + analysis_index,
            **observed,
        }
        for endpoint, value in observed_values.items():
            row[endpoint] = value
            row[f"{endpoint}_ci95_low"] = percentile(distributions[endpoint], 0.025)
            row[f"{endpoint}_ci95_high"] = percentile(distributions[endpoint], 0.975)
            row[f"{endpoint}_valid_replicates"] = len(distributions[endpoint])
        rows.append(row)
    return rows


def write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed-cluster bootstrap for evidence coverage and recoverability endpoints.")
    parser.add_argument("--cases_dir", required=True)
    parser.add_argument("--seed_map", required=True)
    parser.add_argument("--gold", required=True)
    parser.add_argument("--pred_dir", required=True, help="Directory of consolidated JSONL prediction files")
    parser.add_argument("--iterations", type=int, default=2000)
    parser.add_argument("--rng_seed", type=int, default=20260810)
    parser.add_argument("--out_csv", required=True)
    parser.add_argument("--out_json", required=True)
    args = parser.parse_args()

    cases_dir = Path(args.cases_dir)
    seed_map = load_seed_map(Path(args.seed_map))
    gold = load_gold(Path(args.gold))
    all_rows: list[dict[str, Any]] = []
    for model_index, path in enumerate(sorted(Path(args.pred_dir).glob("*.jsonl"))):
        counts = per_seed_counts(load_jsonl(path), cases_dir, seed_map, gold)
        all_rows.extend(bootstrap_model(path.stem, counts, args.iterations, args.rng_seed + model_index * 10))
    if not all_rows:
        raise SystemExit("no consolidated prediction JSONL files found")
    write_csv(Path(args.out_csv), all_rows)
    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(all_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"models": len(all_rows) // 2, "rows": len(all_rows), "n_seed_clusters": len(seed_map)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
