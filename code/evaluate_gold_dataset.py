from __future__ import annotations

import argparse
import csv
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


RULES: List[str] = ["H1", "H2", "H3", "H4", "H5", "H6"]
METRIC_NAMES = ("sensitivity", "specificity", "ppv", "npv", "f1", "accuracy")
EVIDENCE_COUNT_FIELDS = (
    "predicted_fail_outputs",
    "outputs_with_nonempty_evidence",
    "returned_evidence_items",
    "recoverable_evidence_items",
    "outputs_all_snippets_recoverable",
    "outputs_with_case_text",
    "outputs_missing_case_text",
)
EVIDENCE_ENDPOINT_FIELDS = (
    "evidence_coverage",
    "conditional_item_recoverability",
    "all_snippet_recoverability",
    "mean_snippets_per_predicted_fail",
)
DEFAULT_CASES_DIR = Path(__file__).resolve().parents[1] / "data" / "synthetic_cases"


def _is_audit_error(reason: Optional[str]) -> bool:
    if reason is None:
        return False
    value = str(reason).strip()
    if not value:
        return False
    return value.startswith("规则审计失败") or value.startswith("è§???????è???¤±è′￥")


def _normalize_status(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        value = value.get("status")
        if value is None:
            return ""
    status = str(value).strip().upper()
    if status in ("PASS", "FAIL", "NA"):
        return status
    if status in ("N/A", "NOT_APPLICABLE", "NOTAPPLICABLE", "NOT-APPLICABLE"):
        return "NA"
    if status in ("OK", "YES", "TRUE", "Y", "1"):
        return "PASS"
    if status in ("NO", "FALSE", "N", "0"):
        return "FAIL"
    if status in ("通过", "合格", "满足", "是", "符合"):
        return "PASS"
    if status in ("不通过", "不合格", "不满足", "否", "不符合"):
        return "FAIL"
    if status in ("不适用", "未触发", "不触发"):
        return "NA"
    return ""


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists() or not path.is_file():
        raise SystemExit(f"JSONL file not found: {path}")

    rows: List[Dict[str, Any]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON in {path} at line {line_number}: {exc.msg}") from exc
        if not isinstance(row, dict):
            raise SystemExit(f"Expected a JSON object in {path} at line {line_number}")
        rows.append(row)
    return rows


def _load_gold_labels(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Gold labels not found: {path}")

    if path.suffix.lower() == ".jsonl":
        rows = _load_jsonl(path)
    else:
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(obj, dict) and isinstance(obj.get("cases"), list):
            rows = list(obj["cases"])
        elif isinstance(obj, list):
            rows = obj
        else:
            raise SystemExit(f"Unsupported gold labels JSON structure: {path}")

    labels_by_case: Dict[str, Dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("case_id") or "").strip()
        if not case_id:
            continue
        if case_id in labels_by_case:
            raise SystemExit(f"Duplicate Gold case_id in {path}: {case_id}")
        labels = row.get("labels")
        if not isinstance(labels, dict):
            continue

        by_rule: Dict[str, str] = {}
        for rule_id in RULES:
            value = labels.get(rule_id)
            if isinstance(value, str):
                status = _normalize_status(value)
            elif isinstance(value, dict):
                status = _normalize_status(value.get("status"))
            else:
                status = ""
            if status:
                by_rule[rule_id] = status
        if by_rule:
            labels_by_case[case_id] = by_rule

    if not labels_by_case:
        raise SystemExit(f"No usable Gold labels found in: {path}")
    return labels_by_case


def _load_case_id_set(path: Optional[Path]) -> set[str]:
    if path is None:
        return set()
    if not path.exists():
        raise SystemExit(f"Exclude case-id file not found: {path}")
    out: set[str] = set()
    if path.suffix.lower() == ".json":
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
        values: Any
        if isinstance(obj, dict):
            values = obj.get("case_ids")
            if values is None:
                values = obj.get("exclude_case_ids")
            if values is None and isinstance(obj.get("examples"), list):
                values = [item.get("case_id") for item in obj["examples"] if isinstance(item, dict)]
        else:
            values = obj
        if isinstance(values, list):
            out.update(str(value).strip() for value in values if str(value).strip())
    else:
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            value = line.strip()
            if value and not value.startswith("#"):
                out.add(value)
    return out


@dataclass(frozen=True)
class PredRule:
    status: str
    reason: Optional[str]
    evidence: List[str]


@dataclass(frozen=True)
class PredCase:
    case_id: str
    source_path: Optional[str]
    by_rule: Dict[str, PredRule]
    has_record_error: bool = False


def _prediction_from_payload(
    payload: Dict[str, Any],
    origin: str,
    fallback_case_id: Optional[str] = None,
    strict: bool = True,
) -> Optional[PredCase]:
    case_id = str(payload.get("case_id") or fallback_case_id or "").strip()
    if not case_id:
        if strict:
            raise SystemExit(f"Prediction record has no case_id: {origin}")
        return None

    rule_results = payload.get("rule_results")
    if not isinstance(rule_results, list):
        if strict:
            raise SystemExit(f"Prediction rule_results is not a list for {case_id}: {origin}")
        return None

    by_rule: Dict[str, PredRule] = {}
    for result in rule_results:
        if not isinstance(result, dict):
            continue
        rule_id = str(result.get("rule_id") or "").strip()
        if rule_id not in RULES:
            continue
        if rule_id in by_rule and strict:
            raise SystemExit(f"Duplicate prediction rule {rule_id} for {case_id}: {origin}")
        status = _normalize_status(result.get("status"))
        if not status:
            if strict:
                raise SystemExit(f"Invalid prediction status for {case_id}/{rule_id}: {origin}")
            continue
        reason = result.get("reason")
        evidence_raw = result.get("evidence")
        if evidence_raw is None:
            evidence_raw = result.get("evidences")
        if evidence_raw is None:
            evidence: List[str] = []
        elif isinstance(evidence_raw, list):
            evidence = ["" if item is None else str(item) for item in evidence_raw]
        else:
            evidence = [str(evidence_raw)]
        by_rule[rule_id] = PredRule(
            status=status,
            reason=str(reason) if reason is not None else None,
            evidence=evidence,
        )

    return PredCase(
        case_id=case_id,
        source_path=str(payload.get("source_path")) if payload.get("source_path") else None,
        by_rule=by_rule,
        has_record_error=bool(payload.get("audit_error") or payload.get("parse_error")),
    )


def _load_pred_jsonl(path: Path) -> Dict[str, PredCase]:
    items: Dict[str, PredCase] = {}
    for line_number, payload in enumerate(_load_jsonl(path), start=1):
        pred_case = _prediction_from_payload(payload, f"{path}:line {line_number}", strict=True)
        assert pred_case is not None
        if pred_case.case_id in items:
            raise SystemExit(f"Duplicate prediction case_id in {path}: {pred_case.case_id}")
        items[pred_case.case_id] = pred_case
    if not items:
        raise SystemExit(f"No prediction records found in: {path}")
    return items


def _load_pred_dir(results_dir: Path) -> Dict[str, PredCase]:
    if not results_dir.exists() or not results_dir.is_dir():
        raise SystemExit(f"Pred dir not found: {results_dir}")

    items: Dict[str, PredCase] = {}
    for path in sorted(results_dir.glob("case_*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        fallback_case_id = path.stem.replace("case_", "", 1)
        pred_case = _prediction_from_payload(payload, str(path), fallback_case_id=fallback_case_id, strict=False)
        if pred_case is not None:
            items[pred_case.case_id] = pred_case
    if not items:
        raise SystemExit(f"No usable case_*.json predictions found under: {results_dir}")
    return items


def _load_lineage(path: Path) -> Dict[str, str]:
    if not path.exists() or not path.is_file():
        raise SystemExit(f"Lineage CSV not found: {path}")

    case_to_cluster: Dict[str, str] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        if "case_id" not in fieldnames:
            raise SystemExit("Lineage CSV must contain a case_id column")
        cluster_field = next(
            (name for name in ("synthetic_seed_id", "seed_id", "cluster_id") if name in fieldnames),
            None,
        )
        if cluster_field is None:
            raise SystemExit("Lineage CSV must contain synthetic_seed_id, seed_id, or cluster_id")
        for row_number, row in enumerate(reader, start=2):
            case_id = str(row.get("case_id") or "").strip()
            cluster_id = str(row.get(cluster_field) or "").strip()
            if not case_id or not cluster_id:
                raise SystemExit(f"Empty case_id or {cluster_field} in {path} at row {row_number}")
            if case_id in case_to_cluster:
                raise SystemExit(f"Duplicate lineage case_id in {path}: {case_id}")
            case_to_cluster[case_id] = cluster_id
    if not case_to_cluster:
        raise SystemExit(f"No lineage records found in: {path}")
    return case_to_cluster


def _safe_div(num: int, den: int) -> Optional[float]:
    if den <= 0:
        return None
    return float(num) / float(den)


@dataclass(frozen=True)
class Confusion:
    tp: int
    fp: int
    tn: int
    fn: int


def _metrics_from_conf(confusion: Confusion) -> Dict[str, Optional[float]]:
    sensitivity = _safe_div(confusion.tp, confusion.tp + confusion.fn)
    specificity = _safe_div(confusion.tn, confusion.tn + confusion.fp)
    ppv = _safe_div(confusion.tp, confusion.tp + confusion.fp)
    npv = _safe_div(confusion.tn, confusion.tn + confusion.fn)
    f1 = _safe_div(2 * confusion.tp, 2 * confusion.tp + confusion.fp + confusion.fn)
    accuracy = _safe_div(
        confusion.tp + confusion.tn,
        confusion.tp + confusion.fp + confusion.tn + confusion.fn,
    )
    return {
        "sensitivity": sensitivity,
        "specificity": specificity,
        "ppv": ppv,
        "npv": npv,
        "f1": f1,
        "accuracy": accuracy,
    }


def _percentile(values: List[float], quantile: float) -> float:
    if not values:
        raise ValueError("empty")
    ordered = sorted(values)
    if quantile <= 0:
        return ordered[0]
    if quantile >= 1:
        return ordered[-1]
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    if upper == lower:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _confusion_for_cases(case_ids: Iterable[str], by_case: Dict[str, Tuple[str, str]]) -> Confusion:
    tp = fp = tn = fn = 0
    for case_id in case_ids:
        gold, pred = by_case[case_id]
        if gold == "FAIL" and pred == "FAIL":
            tp += 1
        elif gold == "FAIL" and pred == "PASS":
            fn += 1
        elif gold == "PASS" and pred == "FAIL":
            fp += 1
        elif gold == "PASS" and pred == "PASS":
            tn += 1
    return Confusion(tp=tp, fp=fp, tn=tn, fn=fn)


def _bootstrap_ci(
    case_ids: List[str],
    by_case: Dict[str, Tuple[str, str]],
    n: int,
    rng: random.Random,
    case_to_cluster: Optional[Dict[str, str]] = None,
) -> Dict[str, Optional[Tuple[float, float]]]:
    samples: Dict[str, List[float]] = {name: [] for name in METRIC_NAMES}

    if case_to_cluster is None:
        sampling_units = [[case_id] for case_id in case_ids]
    else:
        missing = sorted(case_id for case_id in case_ids if case_id not in case_to_cluster)
        if missing:
            raise SystemExit(
                f"Lineage is missing {len(missing)} evaluated cases; first={missing[:3]}"
            )
        grouped: Dict[str, List[str]] = {
            cluster_id: [] for cluster_id in sorted(set(case_to_cluster.values()))
        }
        for case_id in case_ids:
            grouped[case_to_cluster[case_id]].append(case_id)
        sampling_units = [grouped[cluster_id] for cluster_id in sorted(grouped)]

    for _ in range(n):
        sampled_cases: List[str] = []
        for _position in sampling_units:
            sampled_cases.extend(rng.choice(sampling_units))
        metrics = _metrics_from_conf(_confusion_for_cases(sampled_cases, by_case))
        for name, value in metrics.items():
            if value is not None:
                samples[name].append(float(value))

    ci: Dict[str, Optional[Tuple[float, float]]] = {}
    for name, values in samples.items():
        if not values:
            ci[name] = None
        else:
            ci[name] = (_percentile(values, 0.025), _percentile(values, 0.975))
    return ci


def _normalize_for_contains(text: str) -> str:
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\s+", "", normalized).casefold()


def _resolve_case_text(case_id: str, pred: PredCase, cases_dir: Optional[Path]) -> Optional[str]:
    if cases_dir is not None:
        direct = cases_dir / f"{case_id}.md"
        candidates = [direct] if direct.is_file() else sorted(cases_dir.glob(f"{case_id}.*"))
        for candidate in candidates:
            try:
                return candidate.read_text(encoding="utf-8-sig")
            except OSError:
                continue

    if pred.source_path:
        source_path = Path(pred.source_path)
        if source_path.exists() and source_path.is_file():
            try:
                return source_path.read_text(encoding="utf-8-sig")
            except OSError:
                return None
    return None


def _empty_evidence_counts() -> Dict[str, int]:
    return {field: 0 for field in EVIDENCE_COUNT_FIELDS}


def _add_evidence_counts(target: Dict[str, int], source: Dict[str, int]) -> None:
    for field in EVIDENCE_COUNT_FIELDS:
        target[field] += source[field]


def _evidence_endpoint_values(counts: Dict[str, int]) -> Dict[str, Optional[float]]:
    predicted_fail_outputs = counts["predicted_fail_outputs"]
    returned_evidence_items = counts["returned_evidence_items"]
    return {
        "evidence_coverage": _safe_div(
            counts["outputs_with_nonempty_evidence"], predicted_fail_outputs
        ),
        "conditional_item_recoverability": _safe_div(
            counts["recoverable_evidence_items"], returned_evidence_items
        ),
        "all_snippet_recoverability": _safe_div(
            counts["outputs_all_snippets_recoverable"], predicted_fail_outputs
        ),
        "mean_snippets_per_predicted_fail": _safe_div(
            returned_evidence_items, predicted_fail_outputs
        ),
    }


def _evidence_endpoint_fractions(counts: Dict[str, int]) -> Dict[str, Dict[str, Any]]:
    endpoints = _evidence_endpoint_values(counts)
    return {
        "evidence_coverage": {
            "numerator": counts["outputs_with_nonempty_evidence"],
            "denominator": counts["predicted_fail_outputs"],
            "rate": endpoints["evidence_coverage"],
        },
        "conditional_item_recoverability": {
            "numerator": counts["recoverable_evidence_items"],
            "denominator": counts["returned_evidence_items"],
            "rate": endpoints["conditional_item_recoverability"],
        },
        "all_snippet_recoverability": {
            "numerator": counts["outputs_all_snippets_recoverable"],
            "denominator": counts["predicted_fail_outputs"],
            "rate": endpoints["all_snippet_recoverability"],
            "empty_evidence_passes": False,
        },
        "mean_snippets_per_predicted_fail": {
            "numerator": counts["returned_evidence_items"],
            "denominator": counts["predicted_fail_outputs"],
            "mean": endpoints["mean_snippets_per_predicted_fail"],
        },
    }


def _bootstrap_evidence_endpoints(
    per_cluster: Dict[str, Dict[str, int]],
    iterations: int,
    rng: random.Random,
) -> Dict[str, Dict[str, Any]]:
    cluster_ids = sorted(per_cluster)
    distributions: Dict[str, List[float]] = {name: [] for name in EVIDENCE_ENDPOINT_FIELDS}
    for _ in range(iterations):
        sampled = _empty_evidence_counts()
        for _position in cluster_ids:
            _add_evidence_counts(sampled, per_cluster[rng.choice(cluster_ids)])
        for name, value in _evidence_endpoint_values(sampled).items():
            if value is not None:
                distributions[name].append(value)

    result: Dict[str, Dict[str, Any]] = {}
    for name, values in distributions.items():
        result[name] = {
            "low": _percentile(values, 0.025) if values else None,
            "high": _percentile(values, 0.975) if values else None,
            "valid_replicates": len(values),
        }
    return result


def _compute_evidence_analysis(
    pred: Dict[str, PredCase],
    gold: Dict[str, Dict[str, str]],
    cases_dir: Path,
    case_to_cluster: Optional[Dict[str, str]],
    bootstrap_iterations: int,
    seed: int,
) -> Dict[str, Any]:
    analysis_set_names = ("all_predicted_fail", "gold_applicable_predicted_fail")
    observed = {name: _empty_evidence_counts() for name in analysis_set_names}
    cluster_counts: Optional[Dict[str, Dict[str, Dict[str, int]]]] = None
    if case_to_cluster is not None:
        cluster_ids = sorted(set(case_to_cluster.values()))
        cluster_counts = {
            name: {cluster_id: _empty_evidence_counts() for cluster_id in cluster_ids}
            for name in analysis_set_names
        }

    case_text_cache: Dict[str, Optional[str]] = {}
    excluded_record_error_cases = 0
    excluded_audit_error_fail_outputs = 0

    for case_id, pred_case in sorted(pred.items()):
        if pred_case.has_record_error:
            excluded_record_error_cases += 1
            continue
        for rule_id in RULES:
            pred_rule = pred_case.by_rule.get(rule_id)
            if pred_rule is None or pred_rule.status != "FAIL":
                continue
            if _is_audit_error(pred_rule.reason):
                excluded_audit_error_fail_outputs += 1
                continue

            if case_id not in case_text_cache:
                case_text_cache[case_id] = _resolve_case_text(case_id, pred_case, cases_dir)
            case_text = case_text_cache[case_id]
            normalized_case = _normalize_for_contains(case_text) if case_text is not None else None
            evidence_items = [
                str(item).strip() for item in pred_rule.evidence if str(item or "").strip()
            ]
            recovered = [
                normalized_case is not None and _normalize_for_contains(item) in normalized_case
                for item in evidence_items
            ]

            set_names = ["all_predicted_fail"]
            if (gold.get(case_id) or {}).get(rule_id) in ("PASS", "FAIL"):
                set_names.append("gold_applicable_predicted_fail")

            if cluster_counts is not None:
                if case_to_cluster is None or case_id not in case_to_cluster:
                    raise SystemExit(f"Lineage is missing predicted FAIL case: {case_id}")
                cluster_id = case_to_cluster[case_id]

            for set_name in set_names:
                delta = _empty_evidence_counts()
                delta["predicted_fail_outputs"] = 1
                delta["outputs_with_nonempty_evidence"] = int(bool(evidence_items))
                delta["returned_evidence_items"] = len(evidence_items)
                delta["recoverable_evidence_items"] = sum(recovered)
                delta["outputs_all_snippets_recoverable"] = int(
                    bool(evidence_items) and all(recovered)
                )
                delta["outputs_with_case_text"] = int(case_text is not None)
                delta["outputs_missing_case_text"] = int(case_text is None)
                _add_evidence_counts(observed[set_name], delta)
                if cluster_counts is not None:
                    _add_evidence_counts(cluster_counts[set_name][cluster_id], delta)

    out: Dict[str, Any] = {
        "definitions": {
            "all_predicted_fail": "All valid H1-H6 outputs whose normalized prediction is FAIL.",
            "gold_applicable_predicted_fail": (
                "Predicted FAIL outputs whose Gold status for the same case and rule is PASS or FAIL."
            ),
            "conditional_item_recoverability": (
                "Exact normalized substring recovery among returned non-empty evidence snippets."
            ),
            "all_snippet_recoverability": (
                "A predicted FAIL output passes only when it returns at least one non-empty evidence "
                "snippet and every returned snippet is recoverable in the case text."
            ),
        },
        "excluded_prediction_records_with_parse_or_audit_error": excluded_record_error_cases,
        "excluded_rule_level_audit_error_fail_outputs": excluded_audit_error_fail_outputs,
        "analysis_sets": {},
    }

    for index, set_name in enumerate(analysis_set_names):
        counts = observed[set_name]
        summary: Dict[str, Any] = {
            **counts,
            **_evidence_endpoint_values(counts),
            "endpoint_fractions": _evidence_endpoint_fractions(counts),
        }
        if cluster_counts is not None:
            evidence_ci = _bootstrap_evidence_endpoints(
                cluster_counts[set_name],
                bootstrap_iterations,
                random.Random(seed + index),
            )
            summary["ci95_seed_cluster_bootstrap"] = evidence_ci
            for endpoint, interval in evidence_ci.items():
                summary[f"{endpoint}_ci95_low"] = interval["low"]
                summary[f"{endpoint}_ci95_high"] = interval["high"]
                summary[f"{endpoint}_valid_replicates"] = interval["valid_replicates"]
            summary["cluster_unit"] = "seed"
            summary["n_seed_clusters"] = len(cluster_counts[set_name])
            summary["bootstrap_iterations"] = bootstrap_iterations
            summary["rng_seed"] = seed + index
            summary["bootstrap_clustered"] = True
        else:
            summary["cluster_unit"] = "case"
            summary["bootstrap_clustered"] = False
        out["analysis_sets"][set_name] = summary
        # Keep the set names directly addressable for lightweight public checks.
        out[set_name] = summary
    return out


def _format_rate(value: Any) -> str:
    return f"{float(value):.3f}" if isinstance(value, (int, float)) else "NA"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate fixed H1-H6 predictions against the public normalized Gold dataset."
    )
    parser.add_argument("--gold_labels", required=True, help="Gold labels file (.jsonl recommended)")
    pred_group = parser.add_mutually_exclusive_group(required=True)
    pred_group.add_argument("--pred_jsonl", help="Consolidated prediction JSONL, one case per line")
    pred_group.add_argument("--pred_dir", help="Legacy directory containing case_*.json predictions")
    parser.add_argument(
        "--cases_dir",
        default=str(DEFAULT_CASES_DIR),
        help="Public case-text directory used for evidence recovery checks",
    )
    parser.add_argument(
        "--lineage_csv",
        "--lineage",
        "--seed_map",
        dest="lineage_csv",
        default="",
        help=(
            "Optional case-to-seed lineage CSV. When supplied, bootstrap resampling uses seed "
            "clusters; otherwise the discrimination bootstrap unit is the individual case."
        ),
    )
    parser.add_argument(
        "--exclude_case_ids",
        default="",
        help="Optional TXT/JSON file with case IDs to exclude from evaluation",
    )
    parser.add_argument(
        "--pred_na_policy",
        default="as_pass",
        choices=("exclude", "as_pass", "as_fail"),
        help="How to handle prediction NA when Gold is PASS/FAIL",
    )
    parser.add_argument(
        "--exclude_audit_errors",
        action="store_true",
        help="Exclude audit-error FAIL outputs from discrimination evaluation",
    )
    parser.add_argument("--bootstrap", type=int, default=1000, help="Bootstrap iterations")
    parser.add_argument("--seed", type=int, default=20260117)
    parser.add_argument("--out_json", default="results/gold_eval/eval_gold.json")
    parser.add_argument("--out_md", default="results/gold_eval/eval_gold.md")
    args = parser.parse_args(argv)

    if args.bootstrap < 0:
        parser.error("--bootstrap must be non-negative")

    gold_path = Path(args.gold_labels)
    pred_jsonl = Path(args.pred_jsonl) if args.pred_jsonl else None
    pred_dir = Path(args.pred_dir) if args.pred_dir else None
    cases_dir = Path(args.cases_dir)
    lineage_path = Path(args.lineage_csv) if str(args.lineage_csv).strip() else None
    if not cases_dir.exists() or not cases_dir.is_dir():
        raise SystemExit(f"Cases dir not found: {cases_dir}")

    exclude_case_ids = (
        _load_case_id_set(Path(args.exclude_case_ids))
        if str(args.exclude_case_ids).strip()
        else set()
    )
    gold = _load_gold_labels(gold_path)
    pred = _load_pred_jsonl(pred_jsonl) if pred_jsonl is not None else _load_pred_dir(pred_dir)  # type: ignore[arg-type]
    if exclude_case_ids:
        gold = {case_id: labels for case_id, labels in gold.items() if case_id not in exclude_case_ids}
        pred = {case_id: item for case_id, item in pred.items() if case_id not in exclude_case_ids}

    case_to_cluster = _load_lineage(lineage_path) if lineage_path is not None else None
    if case_to_cluster is not None:
        missing_lineage = sorted(case_id for case_id in gold if case_id not in case_to_cluster)
        if missing_lineage:
            raise SystemExit(
                f"Lineage is missing {len(missing_lineage)} Gold cases; first={missing_lineage[:3]}"
            )

    bootstrap_unit = "seed_cluster" if case_to_cluster is not None else "case"
    rng = random.Random(int(args.seed))
    per_rule: Dict[str, Any] = {}
    overall_audit_error = 0
    overall_eval_pairs = 0

    for rule_id in RULES:
        pairs: Dict[str, Tuple[str, str]] = {}
        skipped_gold_na = 0
        skipped_pred_missing = 0
        skipped_pred_audit_error = 0
        skipped_pred_na = 0

        for case_id, gold_by_rule in gold.items():
            gold_status = gold_by_rule.get(rule_id)
            if gold_status is None:
                continue
            if gold_status == "NA":
                skipped_gold_na += 1
                continue
            if gold_status not in ("PASS", "FAIL"):
                continue

            pred_case = pred.get(case_id)
            if pred_case is None:
                skipped_pred_missing += 1
                continue
            pred_rule = pred_case.by_rule.get(rule_id)
            if pred_rule is None:
                skipped_pred_missing += 1
                continue

            if pred_rule.status == "FAIL" and _is_audit_error(pred_rule.reason):
                overall_audit_error += 1
                if args.exclude_audit_errors:
                    skipped_pred_audit_error += 1
                    continue

            pred_status = pred_rule.status
            if pred_status == "NA":
                if args.pred_na_policy == "exclude":
                    skipped_pred_na += 1
                    continue
                pred_status = "FAIL" if args.pred_na_policy == "as_fail" else "PASS"

            if pred_status not in ("PASS", "FAIL"):
                skipped_pred_missing += 1
                continue
            pairs[case_id] = (gold_status, pred_status)

        case_ids = sorted(pairs)
        overall_eval_pairs += len(case_ids)
        confusion = _confusion_for_cases(case_ids, pairs)
        metrics = _metrics_from_conf(confusion)
        ci = (
            _bootstrap_ci(
                case_ids=case_ids,
                by_case=pairs,
                n=int(args.bootstrap),
                rng=rng,
                case_to_cluster=case_to_cluster,
            )
            if case_ids
            else {name: None for name in METRIC_NAMES}
        )

        per_rule[rule_id] = {
            "n_eval": len(case_ids),
            "confusion": confusion.__dict__,
            "metrics": metrics,
            "ci95_bootstrap": ci,
            "bootstrap_unit": bootstrap_unit,
            "bootstrap_clustered": case_to_cluster is not None,
            "skipped": {
                "gold_na": skipped_gold_na,
                "pred_missing": skipped_pred_missing,
                "pred_audit_error": skipped_pred_audit_error,
                "pred_na": skipped_pred_na,
            },
        }

    evidence_analysis = _compute_evidence_analysis(
        pred=pred,
        gold=gold,
        cases_dir=cases_dir,
        case_to_cluster=case_to_cluster,
        bootstrap_iterations=int(args.bootstrap),
        seed=int(args.seed),
    )
    gold_applicable_evidence = evidence_analysis["analysis_sets"]["gold_applicable_predicted_fail"]

    prediction_input = pred_jsonl if pred_jsonl is not None else pred_dir
    out = {
        "gold_labels": str(gold_path),
        "pred_jsonl": str(pred_jsonl) if pred_jsonl is not None else None,
        "pred_dir": str(pred_dir) if pred_dir is not None else None,
        "prediction_input": str(prediction_input),
        "cases_dir": str(cases_dir),
        "lineage_csv": str(lineage_path) if lineage_path is not None else None,
        "rules": RULES,
        "pred_na_policy": str(args.pred_na_policy),
        "exclude_audit_errors": bool(args.exclude_audit_errors),
        "bootstrap": int(args.bootstrap),
        "bootstrap_unit": bootstrap_unit,
        "bootstrap_method": f"{bootstrap_unit}_percentile",
        "cluster_unit": "seed" if case_to_cluster is not None else "case",
        "bootstrap_clustered": case_to_cluster is not None,
        "seed": int(args.seed),
        "excluded_case_ids": sorted(exclude_case_ids),
        "n_gold_cases": len(gold),
        "n_prediction_cases": len(pred),
        "per_rule": per_rule,
        "audit_error_rules_in_eval_scan": int(overall_audit_error),
        "total_rule_pairs_eval": int(overall_eval_pairs),
        "evidence_analysis": evidence_analysis,
        "evidence_in_text": {
            "legacy_alias_for": "evidence_analysis.analysis_sets.gold_applicable_predicted_fail",
            "cases_checked": gold_applicable_evidence["outputs_with_case_text"],
            "evidence_items_total": gold_applicable_evidence["returned_evidence_items"],
            "evidence_items_in_text": gold_applicable_evidence["recoverable_evidence_items"],
            "evidence_in_text_rate": gold_applicable_evidence[
                "conditional_item_recoverability"
            ],
        },
    }

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines: List[str] = [
        "# Public Gold evaluation",
        "",
        f"- gold_labels: `{gold_path}`",
        f"- prediction_input: `{prediction_input}`",
        f"- cases_dir: `{cases_dir}`",
        f"- pred_na_policy: `{args.pred_na_policy}`",
        f"- exclude_audit_errors: `{bool(args.exclude_audit_errors)}`",
        f"- bootstrap: `{int(args.bootstrap)}`; unit: `{bootstrap_unit}`",
    ]
    if lineage_path is not None:
        lines.append(f"- lineage_csv: `{lineage_path}`")
    if exclude_case_ids:
        lines.append(f"- excluded_case_ids: `{len(exclude_case_ids)}`")
    lines.extend(
        [
            "",
            "## Rule-level discrimination",
            "",
            "| Rule | n | Sens | Spec | PPV | NPV | F1 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for rule_id in RULES:
        rule_output = per_rule[rule_id]
        metrics = rule_output["metrics"]
        lines.append(
            f"| {rule_id} | {rule_output['n_eval']} | {_format_rate(metrics['sensitivity'])} | "
            f"{_format_rate(metrics['specificity'])} | {_format_rate(metrics['ppv'])} | "
            f"{_format_rate(metrics['npv'])} | {_format_rate(metrics['f1'])} |"
        )

    lines.extend(
        [
            "",
            "## Evidence integrity",
            "",
            "| Analysis set | Predicted FAIL | Evidence coverage | Conditional item recoverability | All-snippet recoverability | Mean snippets/FAIL |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for set_name in ("all_predicted_fail", "gold_applicable_predicted_fail"):
        summary = evidence_analysis["analysis_sets"][set_name]
        fractions = summary["endpoint_fractions"]
        coverage = fractions["evidence_coverage"]
        recoverability = fractions["conditional_item_recoverability"]
        integrity = fractions["all_snippet_recoverability"]
        mean_snippets = fractions["mean_snippets_per_predicted_fail"]
        lines.append(
            f"| {set_name} | {summary['predicted_fail_outputs']} | "
            f"{coverage['numerator']}/{coverage['denominator']} ({_format_rate(coverage['rate'])}) | "
            f"{recoverability['numerator']}/{recoverability['denominator']} ({_format_rate(recoverability['rate'])}) | "
            f"{integrity['numerator']}/{integrity['denominator']} ({_format_rate(integrity['rate'])}) | "
            f"{mean_snippets['numerator']}/{mean_snippets['denominator']} ({_format_rate(mean_snippets['mean'])}) |"
        )
    lines.extend(
        [
            "",
            "All-snippet recoverability requires non-empty evidence and recovery of every returned snippet.",
            "",
        ]
    )
    out_md.write_text("\n".join(lines), encoding="utf-8")

    print(
        json.dumps(
            {
                "wrote": [str(out_json), str(out_md)],
                "n_gold_cases": len(gold),
                "n_prediction_cases": len(pred),
                "total_rule_pairs_eval": int(overall_eval_pairs),
                "bootstrap_unit": bootstrap_unit,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
