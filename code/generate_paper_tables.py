from __future__ import annotations

import argparse
import csv
import difflib
import shutil
import itertools
import json
import math
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


_RULES: List[str] = ["H1", "H2", "H3", "H4", "H5", "H6"]
_TAXONOMY_DISPLAY_LABELS: Dict[str, str] = {
    "RULE_TRIGGER_BRANCH": "Rule-trigger/branch boundary misunderstanding",
    "NUMERIC_REASONING": "Numeric reasoning failure",
    "FORMAT_STRUCTURED": "Structured-output failure",
    "EVIDENCE_MISS": "Evidence miss",
    "EVIDENCE_HALLUCINATION": "Evidence hallucination",
}
_ACTIONABILITY_DISPLAY_LABELS: Dict[str, str] = {
    "rule_text": "Rule-text clarification",
    "parser": "Parser/output handling",
    "label_guideline": "Guideline revision",
}


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_csv(path: Path, fieldnames: List[str], rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _fmt_float(value: Any, digits: int = 3) -> str:
    if not isinstance(value, (int, float)):
        return ""
    return f"{float(value):.{digits}f}"


def _taxonomy_display_name(label: str) -> str:
    return _TAXONOMY_DISPLAY_LABELS.get(label, label.replace("_", " ").title())


def _actionability_display_name(label: str) -> str:
    return _ACTIONABILITY_DISPLAY_LABELS.get(label, label.replace("_", " ").title())


def _clean_csvs(out_dir: Path) -> None:
    if not out_dir.exists():
        return
    for csv_path in sorted(out_dir.glob("*.csv")):
        csv_path.unlink()


def _normalize_status(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip().upper()
    if s in ("PASS", "FAIL", "NA"):
        return s
    if s in ("N/A", "NOT_APPLICABLE", "NOTAPPLICABLE", "NOT-APPLICABLE"):
        return "NA"
    if s in ("OK", "YES", "TRUE", "Y", "1"):
        return "PASS"
    if s in ("NO", "FALSE", "N", "0"):
        return "FAIL"
    if s in ("通过", "合格", "满足", "是", "符合"):
        return "PASS"
    if s in ("不通过", "不合格", "不满足", "否", "不符合"):
        return "FAIL"
    if s in ("不适用", "未触发", "不触发"):
        return "NA"
    return ""


def _apply_pred_na_policy(status: str, policy: str) -> Optional[str]:
    if status != "NA":
        return status
    if policy == "exclude":
        return None
    if policy == "as_fail":
        return "FAIL"
    return "PASS"


def _load_gold_labels(path: Path) -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    for ln in path.read_text(encoding="utf-8-sig").splitlines():
        line = ln.strip()
        if not line:
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            continue
        cid = str(row.get("case_id") or "").strip()
        labels = row.get("labels")
        if not cid or not isinstance(labels, dict):
            continue
        by_rule: Dict[str, str] = {}
        for rid in _RULES:
            v = labels.get(rid)
            if isinstance(v, dict):
                st = _normalize_status(v.get("status"))
            else:
                st = _normalize_status(v)
            if st:
                by_rule[rid] = st
        if by_rule:
            out[cid] = by_rule
    return out


def _is_audit_error(reason: Optional[str]) -> bool:
    if reason is None:
        return False
    s = str(reason).strip()
    if not s:
        return False
    return s.startswith("规则审计失败") or s.startswith("è§???????è???¤±è′￥")


def _normalize_for_contains(text: str) -> str:
    s = str(text or "")
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\s+", "", s)


def _normalize_for_lenient_contains(text: str) -> str:
    s = str(text or "")
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    out_chars: List[str] = []
    for ch in s:
        if ch.isspace():
            continue
        if unicodedata.category(ch).startswith("P"):
            continue
        out_chars.append(ch)
    return "".join(out_chars)


def _split_evidence_parts(evidence_item: str) -> List[str]:
    s = str(evidence_item or "").strip()
    if not s:
        return []
    # Some models concatenate multiple snippets in a single evidence item.
    parts = re.split(r"\s*(?:\|\||｜｜)\s*", s)
    out: List[str] = []
    for part in parts:
        for ln in str(part).splitlines():
            t = ln.strip()
            if t:
                out.append(t)
    return out or [s]


def _loose_part_in_text(part: str, hay_lenient: str, min_lcs_ratio: float = 0.8) -> bool:
    ev = _normalize_for_lenient_contains(part)
    if not ev or not hay_lenient:
        return False
    if ev in hay_lenient:
        return True
    # For very short strings, fuzzy matching is too error-prone.
    if len(ev) < 12:
        return False
    sm = difflib.SequenceMatcher(None, ev, hay_lenient, autojunk=False)
    m = sm.find_longest_match(0, len(ev), 0, len(hay_lenient))
    if m.size < 12:
        return False
    return (float(m.size) / float(len(ev))) >= float(min_lcs_ratio)


def _evidence_item_in_text_lenient(evidence_item: str, hay_lenient: str) -> bool:
    parts = _split_evidence_parts(evidence_item)
    if not parts:
        return False
    return all(_loose_part_in_text(part, hay_lenient) for part in parts)


def _discover_summary_jsons(summaries_dir: Path) -> List[Path]:
    if not summaries_dir.exists() or not summaries_dir.is_dir():
        return []
    return sorted(summaries_dir.glob("gold_audit_summary_*.json"))


def _model_name_from_summary_path(path: Path) -> str:
    stem = path.stem
    return stem.replace("gold_audit_summary_", "", 1)


def _load_model_preds_from_summary(path: Path) -> Dict[str, Dict[str, str]]:
    obj = _load_json(path)
    cases = obj.get("cases") if isinstance(obj, dict) else None
    if not isinstance(cases, list):
        raise SystemExit(f"Invalid summary JSON (missing cases list): {path}")
    out: Dict[str, Dict[str, str]] = {}
    for row in cases:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("case_id") or "").strip()
        rs = row.get("rule_status")
        if not cid or not isinstance(rs, dict):
            continue
        by_rule: Dict[str, str] = {}
        for rid in _RULES:
            st = _normalize_status(rs.get(rid))
            if st:
                by_rule[rid] = st
        if by_rule:
            out[cid] = by_rule
    return out


class _Confusion:
    __slots__ = ("tp", "fp", "tn", "fn")

    def __init__(self, tp: int = 0, fp: int = 0, tn: int = 0, fn: int = 0) -> None:
        self.tp = int(tp)
        self.fp = int(fp)
        self.tn = int(tn)
        self.fn = int(fn)


def _safe_div(num: int, den: int) -> Optional[float]:
    if den <= 0:
        return None
    return float(num) / float(den)


def _metrics_from_conf(c: _Confusion) -> Dict[str, Optional[float]]:
    sens = _safe_div(c.tp, c.tp + c.fn)
    spec = _safe_div(c.tn, c.tn + c.fp)
    ppv = _safe_div(c.tp, c.tp + c.fp)
    npv = _safe_div(c.tn, c.tn + c.fn)
    acc = _safe_div(c.tp + c.tn, c.tp + c.fp + c.tn + c.fn)
    f1 = _safe_div(2 * c.tp, 2 * c.tp + c.fp + c.fn)
    return {
        "sensitivity": sens,
        "specificity": spec,
        "ppv": ppv,
        "npv": npv,
        "accuracy": acc,
        "f1": f1,
    }


def _confusion_for_rule(
    gold: Dict[str, Dict[str, str]],
    pred: Dict[str, Dict[str, str]],
    rid: str,
    pred_na_policy: str,
    case_ids: List[str],
) -> tuple[_Confusion, int]:
    tp = fp = tn = fn = 0
    n_eval = 0
    for cid in case_ids:
        g = gold.get(cid, {}).get(rid)
        if g is None or g == "NA":
            continue
        if g not in ("PASS", "FAIL"):
            continue

        p_raw = pred.get(cid, {}).get(rid)
        if not p_raw:
            continue
        p = _apply_pred_na_policy(p_raw, pred_na_policy)
        if p is None:
            continue
        if p not in ("PASS", "FAIL"):
            continue

        n_eval += 1
        if g == "FAIL" and p == "FAIL":
            tp += 1
        elif g == "FAIL" and p == "PASS":
            fn += 1
        elif g == "PASS" and p == "FAIL":
            fp += 1
        elif g == "PASS" and p == "PASS":
            tn += 1
    return _Confusion(tp=tp, fp=fp, tn=tn, fn=fn), n_eval


def _eval_model(
    gold: Dict[str, Dict[str, str]],
    pred: Dict[str, Dict[str, str]],
    pred_na_policy: str,
    case_ids: List[str],
) -> Dict[str, Any]:
    macro_f1_vals: List[float] = []
    micro_tp = micro_fp = micro_tn = micro_fn = 0
    total_pairs = 0
    for rid in _RULES:
        conf, n_eval = _confusion_for_rule(gold, pred, rid, pred_na_policy, case_ids)
        m = _metrics_from_conf(conf)
        if isinstance(m.get("f1"), (int, float)):
            macro_f1_vals.append(float(m["f1"]))
        micro_tp += conf.tp
        micro_fp += conf.fp
        micro_tn += conf.tn
        micro_fn += conf.fn
        total_pairs += n_eval
    micro = _metrics_from_conf(_Confusion(tp=micro_tp, fp=micro_fp, tn=micro_tn, fn=micro_fn))
    macro_f1 = sum(macro_f1_vals) / len(macro_f1_vals) if macro_f1_vals else None
    return {
        "macro_f1": macro_f1,
        "micro_f1": micro.get("f1"),
        "total_rule_pairs_eval": int(total_pairs),
    }


def _log_sum_exp(xs: List[float]) -> float:
    if not xs:
        return float("-inf")
    m = max(xs)
    if not math.isfinite(m):
        return m
    s = sum(math.exp(x - m) for x in xs)
    return m + math.log(s)


def _mcnemar_exact_p(n01: int, n10: int) -> Optional[float]:
    # Exact two-sided McNemar via binomial test with p=0.5 on discordant pairs.
    n = int(n01 + n10)
    if n <= 0:
        return None
    x = int(min(n01, n10))
    log_half = math.log(0.5)
    logs: List[float] = []
    for k in range(x + 1):
        log_c = math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
        logs.append(log_c + n * log_half)  # log(C(n,k) * 0.5^n)
    log_p_one = _log_sum_exp(logs)
    p_one = math.exp(log_p_one) if math.isfinite(log_p_one) else 0.0
    return float(min(1.0, 2.0 * p_one))


def _bh_fdr(p_values: List[Optional[float]]) -> List[Optional[float]]:
    idx_p = [(i, float(p)) for i, p in enumerate(p_values) if isinstance(p, (int, float))]
    if not idx_p:
        return [None for _ in p_values]
    m = len(idx_p)
    idx_p.sort(key=lambda x: x[1])
    q: List[Optional[float]] = [None for _ in p_values]
    prev = 1.0
    for rank, (i, p) in reversed(list(enumerate(idx_p, start=1))):
        v = min(prev, (p * m) / float(rank))
        q[i] = float(v)
        prev = v
    return q


def _write_pred_na_policy_sensitivity(
    gold: Dict[str, Dict[str, str]],
    preds_by_model: Dict[str, Dict[str, Dict[str, str]]],
    case_ids: List[str],
    out_dir: Path,
) -> str:
    policies = ["as_pass", "exclude", "as_fail"]
    rows: List[Dict[str, Any]] = []
    for model in sorted(preds_by_model.keys()):
        pred = preds_by_model[model]
        for policy in policies:
            ev = _eval_model(gold, pred, policy, case_ids)
            rows.append(
                {
                    "model": model,
                    "pred_na_policy": policy,
                    "macro_f1": _fmt_float(ev.get("macro_f1"), 3),
                    "micro_f1": _fmt_float(ev.get("micro_f1"), 3),
                    "total_rule_pairs_eval": ev.get("total_rule_pairs_eval"),
                }
            )
    out_path = out_dir / "table_pred_na_policy_sensitivity.csv"
    _write_csv(out_path, ["model", "pred_na_policy", "macro_f1", "micro_f1", "total_rule_pairs_eval"], rows)
    return str(out_path)


def _write_predicted_na_rates(
    gold: Dict[str, Dict[str, str]],
    preds_by_model: Dict[str, Dict[str, Dict[str, str]]],
    case_ids: List[str],
    out_dir: Path,
) -> str:
    rows: List[Dict[str, Any]] = []
    n_cases = len(case_ids)
    for model in sorted(preds_by_model.keys()):
        pred = preds_by_model[model]
        for rid in _RULES:
            gold_na = 0
            gold_applicable = 0
            pred_na_all = 0
            pred_na_on_applicable = 0
            for cid in case_ids:
                g = gold.get(cid, {}).get(rid)
                if g == "NA":
                    gold_na += 1
                elif g in ("PASS", "FAIL"):
                    gold_applicable += 1
                p = pred.get(cid, {}).get(rid)
                if p == "NA":
                    pred_na_all += 1
                    if g in ("PASS", "FAIL"):
                        pred_na_on_applicable += 1
            rows.append(
                {
                    "model": model,
                    "rule": rid,
                    "total_cases": n_cases,
                    "gold_na_count": gold_na,
                    "gold_applicable_count": gold_applicable,
                    "pred_na_count_all": pred_na_all,
                    "pred_na_rate_all": _fmt_float(pred_na_all / n_cases if n_cases else None, 3),
                    "pred_na_count_on_gold_applicable": pred_na_on_applicable,
                    "pred_na_rate_on_gold_applicable": _fmt_float(
                        pred_na_on_applicable / gold_applicable if gold_applicable else None, 3
                    ),
                }
            )
    out_path = out_dir / "table_predicted_na_rates.csv"
    _write_csv(
        out_path,
        [
            "model",
            "rule",
            "total_cases",
            "gold_na_count",
            "gold_applicable_count",
            "pred_na_count_all",
            "pred_na_rate_all",
            "pred_na_count_on_gold_applicable",
            "pred_na_rate_on_gold_applicable",
        ],
        rows,
    )
    return str(out_path)


def _percentiles(values: List[float], ps: List[float]) -> Dict[str, float]:
    if not values:
        return {str(p): float("nan") for p in ps}
    xs = sorted(values)
    n = len(xs)
    out: Dict[str, float] = {}
    for p in ps:
        if n == 1:
            out[str(p)] = float(xs[0])
            continue
        q = float(p) / 100.0
        idx = q * (n - 1)
        lo = int(math.floor(idx))
        hi = int(math.ceil(idx))
        if lo == hi:
            out[str(p)] = float(xs[lo])
        else:
            w = idx - lo
            out[str(p)] = float(xs[lo] * (1 - w) + xs[hi] * w)
    return out


def _write_rule_conditioned_snippet_stats(case_dir: Path, out_dir_supp: Path) -> str:
    from gej_audit.llm_rule_pipeline import _case_snippet_for_rule  # type: ignore

    case_paths = sorted(case_dir.glob("gold_*.md"))
    if not case_paths:
        raise SystemExit(f"No gold case files found under: {case_dir}")

    fieldnames = [
        "rule_id",
        "n_cases",
        "orig_chars_mean",
        "snippet_chars_mean",
        "chars_reduction_mean",
        "chars_ratio_mean",
        "orig_chars_p50",
        "snippet_chars_p50",
        "chars_ratio_p50",
        "orig_lines_mean",
        "snippet_lines_mean",
        "lines_reduction_mean",
        "lines_ratio_mean",
        "orig_lines_p50",
        "snippet_lines_p50",
        "lines_ratio_p50",
    ]

    rows: List[Dict[str, Any]] = []
    for rid in _RULES:
        orig_chars: List[float] = []
        snip_chars: List[float] = []
        orig_lines: List[float] = []
        snip_lines: List[float] = []

        for p in case_paths:
            s = p.read_text(encoding="utf-8")
            snippet = _case_snippet_for_rule(rid, s)
            orig_chars.append(float(len(s)))
            snip_chars.append(float(len(snippet)))
            orig_lines.append(float(len([ln for ln in s.splitlines() if ln.strip()])))
            snip_lines.append(float(len([ln for ln in snippet.splitlines() if ln.strip()])))

        n = len(orig_chars)
        chars_ratio = [b / a if a > 0 else float("nan") for a, b in zip(orig_chars, snip_chars)]
        lines_ratio = [b / a if a > 0 else float("nan") for a, b in zip(orig_lines, snip_lines)]

        pc_chars = _percentiles(orig_chars, [50.0])
        pc_snip_chars = _percentiles(snip_chars, [50.0])
        pc_lines = _percentiles(orig_lines, [50.0])
        pc_snip_lines = _percentiles(snip_lines, [50.0])
        pc_chars_ratio = _percentiles(chars_ratio, [50.0])
        pc_lines_ratio = _percentiles(lines_ratio, [50.0])

        rows.append(
            {
                "rule_id": rid,
                "n_cases": n,
                "orig_chars_mean": f"{sum(orig_chars) / n:.1f}",
                "snippet_chars_mean": f"{sum(snip_chars) / n:.1f}",
                "chars_reduction_mean": f"{(1.0 - (sum(snip_chars) / sum(orig_chars))):.3f}",
                "chars_ratio_mean": f"{(sum(snip_chars) / sum(orig_chars)):.3f}",
                "orig_chars_p50": f"{pc_chars['50.0']:.1f}",
                "snippet_chars_p50": f"{pc_snip_chars['50.0']:.1f}",
                "chars_ratio_p50": f"{pc_chars_ratio['50.0']:.3f}",
                "orig_lines_mean": f"{sum(orig_lines) / n:.1f}",
                "snippet_lines_mean": f"{sum(snip_lines) / n:.1f}",
                "lines_reduction_mean": f"{(1.0 - (sum(snip_lines) / sum(orig_lines))):.3f}",
                "lines_ratio_mean": f"{(sum(snip_lines) / sum(orig_lines)):.3f}",
                "orig_lines_p50": f"{pc_lines['50.0']:.1f}",
                "snippet_lines_p50": f"{pc_snip_lines['50.0']:.1f}",
                "lines_ratio_p50": f"{pc_lines_ratio['50.0']:.3f}",
            }
        )

    out_path = out_dir_supp / "table_rule_conditioned_snippet_stats.csv"
    _write_csv(out_path, fieldnames, rows)
    return str(out_path)


def _write_evidence_recoverability_stats(
    eval_viz: Dict[str, Any],
    gold: Dict[str, Dict[str, str]],
    gold_runs_dir: Path,
    cases_dir: Path,
    out_dir_supp: Path,
) -> str:
    models = [str(value) for value in (eval_viz.get("models") or [])]
    macro_f1 = [float(value) for value in ((eval_viz.get("macro") or {}).get("f1") or [])]
    order = sorted(range(len(models)), key=lambda idx: macro_f1[idx], reverse=True)

    case_texts: Dict[str, str] = {}
    for p in sorted(cases_dir.glob("gold_*.md")):
        case_texts[p.stem] = p.read_text(encoding="utf-8")
    if not case_texts:
        raise SystemExit(f"No gold case files found under: {cases_dir}")

    fieldnames = [
        "rank",
        "model",
        "fail_applicable_evidence_items_total",
        "fail_applicable_evidence_in_text_strict_rate",
        "fail_applicable_evidence_in_text_lenient_rate",
        "all_evidence_items_total",
        "all_evidence_in_text_strict_rate",
        "all_evidence_in_text_lenient_rate",
        "pass_or_na_evidence_items_total",
    ]

    rows: List[Dict[str, Any]] = []
    for rank, model_index in enumerate(order, start=1):
        model = models[model_index]
        pred_dir = gold_runs_dir / model
        if not pred_dir.exists():
            raise SystemExit(f"Pred dir not found for model={model}: {pred_dir}")

        fail_app_total = fail_app_in_strict = fail_app_in_lenient = 0
        all_total = all_in_strict = all_in_lenient = 0
        pass_na_total = 0

        for p in sorted(pred_dir.glob("case_*.json")):
            case_id = p.stem.replace("case_", "", 1)
            case_text = case_texts.get(case_id)
            if case_text is None:
                continue
            hay_strict = _normalize_for_contains(case_text)
            hay_lenient = _normalize_for_lenient_contains(case_text)
            payload = _load_json(p)
            rr = payload.get("rule_results") if isinstance(payload, dict) else None
            if not isinstance(rr, list):
                continue

            for r in rr:
                if not isinstance(r, dict):
                    continue
                rid = str(r.get("rule_id") or "").strip()
                if rid not in _RULES:
                    continue
                st = _normalize_status(r.get("status"))
                if not st:
                    continue
                reason = r.get("reason")
                is_audit_error = st == "FAIL" and _is_audit_error(str(reason) if reason is not None else None)

                evidence_raw = r.get("evidence")
                if evidence_raw is None:
                    evidence_raw = r.get("evidences")
                if evidence_raw is None:
                    evidence_items: List[str] = []
                elif isinstance(evidence_raw, list):
                    evidence_items = [str(x) for x in evidence_raw]
                else:
                    evidence_items = [str(evidence_raw)]

                if not evidence_items:
                    continue

                gold_st = (gold.get(case_id) or {}).get(rid)
                gold_applicable = gold_st in ("PASS", "FAIL")

                for ev in evidence_items:
                    e = str(ev or "").strip()
                    if not e:
                        continue

                    all_total += 1
                    if _normalize_for_contains(e) in hay_strict:
                        all_in_strict += 1
                    if _evidence_item_in_text_lenient(e, hay_lenient):
                        all_in_lenient += 1

                    if st in ("PASS", "NA"):
                        pass_na_total += 1

                    if st == "FAIL" and (not is_audit_error) and gold_applicable:
                        fail_app_total += 1
                        if _normalize_for_contains(e) in hay_strict:
                            fail_app_in_strict += 1
                        if _evidence_item_in_text_lenient(e, hay_lenient):
                            fail_app_in_lenient += 1

        def _rate(num: int, den: int) -> str:
            return _fmt_float((float(num) / float(den)) if den else None, 3)

        rows.append(
            {
                "rank": rank,
                "model": model,
                "fail_applicable_evidence_items_total": int(fail_app_total),
                "fail_applicable_evidence_in_text_strict_rate": _rate(fail_app_in_strict, fail_app_total),
                "fail_applicable_evidence_in_text_lenient_rate": _rate(fail_app_in_lenient, fail_app_total),
                "all_evidence_items_total": int(all_total),
                "all_evidence_in_text_strict_rate": _rate(all_in_strict, all_total),
                "all_evidence_in_text_lenient_rate": _rate(all_in_lenient, all_total),
                "pass_or_na_evidence_items_total": int(pass_na_total),
            }
        )

    out_path = out_dir_supp / "table_evidence_recoverability_strict_vs_lenient.csv"
    _write_csv(out_path, fieldnames, rows)
    return str(out_path)


def _write_dataset_audit_burden(dataset: Dict[str, Any], out_dir: Path) -> str:
    n_cases = int(dataset.get("n_labeled_cases") or dataset.get("n_case_files") or 0)
    blocked_rate = float(dataset.get("gold_blocked_rate_any_fail") or 0.0)
    blocked_cases = int(dataset.get("gold_blocked_cases_any_fail") or round(n_cases * blocked_rate))

    age = dataset.get("age_summary") if isinstance(dataset.get("age_summary"), dict) else {}
    sex_counts = dataset.get("sex_counts") if isinstance(dataset.get("sex_counts"), dict) else {}
    case_summary = dataset.get("case_level_summary") if isinstance(dataset.get("case_level_summary"), dict) else {}
    required_fields = dataset.get("required_fields") if isinstance(dataset.get("required_fields"), dict) else {}

    fail_distribution_raw = case_summary.get("fail_rules_per_case_distribution") if isinstance(case_summary.get("fail_rules_per_case_distribution"), dict) else {}
    fail_distribution = {int(key): int(value) for key, value in fail_distribution_raw.items()}
    exactly_one = fail_distribution.get(1, 0)
    at_least_two = sum(count for fail_count, count in fail_distribution.items() if fail_count >= 2)
    h3_na = int(((dataset.get("labels_distribution") or {}).get("H3") or {}).get("NA") or 0)
    h5_na = int(((dataset.get("labels_distribution") or {}).get("H5") or {}).get("NA") or 0)

    field_rows = []
    for field_name in ["现病史", "既往史", "过敏史"]:
        row = required_fields.get(field_name) if isinstance(required_fields.get(field_name), dict) else {}
        field_rows.append((field_name, row))

    rows: List[Dict[str, Any]] = [
        {"domain": "Cohort", "metric": "Gold cases", "value": str(n_cases)},
        {
            "domain": "Cohort",
            "metric": "Age, years",
            "value": f"n={int(age.get('n') or 0)}; mean {float(age.get('mean') or 0):.1f}; median {float(age.get('median') or 0):.1f}; IQR {float(age.get('p25') or 0):.1f}-{float(age.get('p75') or 0):.1f}",
        },
        {
            "domain": "Cohort",
            "metric": "Sex",
            "value": f"Male {int(sex_counts.get('男') or 0)}; Female {int(sex_counts.get('女') or 0)}; Missing {int(sex_counts.get('(missing)') or 0)}",
        },
        {
            "domain": "Audit burden",
            "metric": "Any hard FAIL",
            "value": f"{blocked_cases}/{n_cases} ({blocked_rate * 100:.1f}%)",
        },
        {
            "domain": "Audit burden",
            "metric": "Failed rules per case",
            "value": f"mean {float(case_summary.get('fail_rules_per_case_mean') or 0):.2f}; median {float(case_summary.get('fail_rules_per_case_median') or 0):.1f}",
        },
        {
            "domain": "Audit burden",
            "metric": "Exactly one failed rule",
            "value": f"{exactly_one}/{n_cases} ({(exactly_one / n_cases * 100) if n_cases else 0:.1f}%)",
        },
        {
            "domain": "Audit burden",
            "metric": ">=2 failed rules",
            "value": f"{at_least_two}/{n_cases} ({(at_least_two / n_cases * 100) if n_cases else 0:.1f}%)",
        },
        {
            "domain": "Rule applicability",
            "metric": "H3 not applicable",
            "value": f"{h3_na}/{n_cases} ({(h3_na / n_cases * 100) if n_cases else 0:.1f}%)",
        },
        {
            "domain": "Rule applicability",
            "metric": "H5 not applicable",
            "value": f"{h5_na}/{n_cases} ({(h5_na / n_cases * 100) if n_cases else 0:.1f}%)",
        },
    ]
    for field_name, row in field_rows:
        rows.append(
            {
                "domain": "Field completeness",
                "metric": field_name,
                "value": f"non-empty rate {_fmt_float(row.get('non_empty_rate'), 3)}",
            }
        )

    out_path = out_dir / "table_dataset_audit_burden.csv"
    _write_csv(out_path, ["domain", "metric", "value"], rows)
    return str(out_path)


def _write_model_performance_summary(eval_viz: Dict[str, Any], out_dir: Path) -> str:
    models = [str(value) for value in (eval_viz.get("models") or [])]
    rules = [str(value) for value in (eval_viz.get("rules") or [])]
    macro_f1 = [float(value) for value in ((eval_viz.get("macro") or {}).get("f1") or [])]
    micro_f1 = [float(value) for value in ((eval_viz.get("micro") or {}).get("f1") or [])]
    evidence_rates = [float(value) for value in (eval_viz.get("evidence_in_text_rate") or [])]
    per_rule_f1 = (eval_viz.get("matrix") or {}).get("f1") or []

    order = sorted(range(len(models)), key=lambda idx: macro_f1[idx], reverse=True)
    rows: List[Dict[str, Any]] = []
    for rank, model_index in enumerate(order, start=1):
        row_values = [float(value) for value in per_rule_f1[model_index]]
        worst_rule_index = min(range(len(row_values)), key=lambda idx: row_values[idx])
        rows.append(
            {
                "rank": rank,
                "model": models[model_index],
                "macro_f1": _fmt_float(macro_f1[model_index], 3),
                "micro_f1": _fmt_float(micro_f1[model_index], 3),
                "evidence_in_text_rate": _fmt_float(evidence_rates[model_index], 3),
                "worst_rule": rules[worst_rule_index],
                "worst_rule_f1": _fmt_float(row_values[worst_rule_index], 3),
            }
        )

    out_path = out_dir / "table_model_performance_summary.csv"
    _write_csv(
        out_path,
        ["rank", "model", "macro_f1", "micro_f1", "evidence_in_text_rate", "worst_rule", "worst_rule_f1"],
        rows,
    )
    return str(out_path)


def _write_rule_audit_characteristics(dataset: Dict[str, Any], kappa: Dict[str, Any], out_dir: Path) -> str:
    distribution = dataset.get("labels_distribution") if isinstance(dataset.get("labels_distribution"), dict) else {}
    per_rule_kappa = kappa.get("per_rule") if isinstance(kappa.get("per_rule"), dict) else {}

    rows: List[Dict[str, Any]] = []
    for rule_id in _RULES:
        dist_row = distribution.get(rule_id, {}) if isinstance(distribution.get(rule_id), dict) else {}
        kappa_row = per_rule_kappa.get(rule_id, {}) if isinstance(per_rule_kappa.get(rule_id), dict) else {}
        rows.append(
            {
                "Rule": rule_id,
                "PASS": int(dist_row.get("PASS") or 0),
                "FAIL": int(dist_row.get("FAIL") or 0),
                "NA": int(dist_row.get("NA") or 0),
                "FAIL rate (applicable)": _fmt_float(dist_row.get("fail_rate_eval_only"), 3),
                "NA rate": _fmt_float(dist_row.get("na_rate"), 3),
                "Cohen's κ": _fmt_float(kappa_row.get("kappa"), 3),
                "Agreement rate (AR)": _fmt_float(kappa_row.get("agree_rate"), 3),
            }
        )

    out_path = out_dir / "table_rule_audit_characteristics.csv"
    _write_csv(out_path, ["Rule", "PASS", "FAIL", "NA", "FAIL rate (applicable)", "NA rate", "Cohen's κ", "Agreement rate (AR)"], rows)
    return str(out_path)


def _write_model_rule_performance_full(eval_viz: Dict[str, Any], out_dir: Path) -> str:
    models = [str(value) for value in (eval_viz.get("models") or [])]
    rules = [str(value) for value in (eval_viz.get("rules") or [])]
    macro_f1 = [float(value) for value in ((eval_viz.get("macro") or {}).get("f1") or [])]
    micro_f1 = [float(value) for value in ((eval_viz.get("micro") or {}).get("f1") or [])]
    evidence_rates = [float(value) for value in (eval_viz.get("evidence_in_text_rate") or [])]
    total_pairs = [int(value) for value in (eval_viz.get("total_rule_pairs_eval") or [])]
    per_rule_f1 = (eval_viz.get("matrix") or {}).get("f1") or []

    order = sorted(range(len(models)), key=lambda idx: macro_f1[idx], reverse=True)
    fieldnames = ["rank", "model", "macro_f1", "micro_f1", "evidence_in_text_rate", "total_rule_pairs_eval"] + [f"{rule_id}_f1" for rule_id in rules]
    rows: List[Dict[str, Any]] = []
    for rank, model_index in enumerate(order, start=1):
        row: Dict[str, Any] = {
            "rank": rank,
            "model": models[model_index],
            "macro_f1": _fmt_float(macro_f1[model_index], 3),
            "micro_f1": _fmt_float(micro_f1[model_index], 3),
            "evidence_in_text_rate": _fmt_float(evidence_rates[model_index], 3),
            "total_rule_pairs_eval": total_pairs[model_index],
        }
        for rule_index, rule_id in enumerate(rules):
            row[f"{rule_id}_f1"] = _fmt_float(per_rule_f1[model_index][rule_index], 3)
        rows.append(row)

    out_path = out_dir / "table_model_rule_performance_full.csv"
    _write_csv(out_path, fieldnames, rows)
    return str(out_path)


def _write_taxonomy_tables(taxonomy_summary: Dict[str, Any], out_dir: Path) -> List[str]:
    counts = taxonomy_summary.get("counts") if isinstance(taxonomy_summary.get("counts"), dict) else {}
    output_paths: List[str] = []

    taxonomy_l1_counts = counts.get("taxonomy_l1") if isinstance(counts.get("taxonomy_l1"), dict) else {}
    rows = [{"Primary error mechanism": _taxonomy_display_name(key), "n": int(value)} for key, value in taxonomy_l1_counts.items()]
    path = out_dir / "table_taxonomy_l1_counts.csv"
    _write_csv(path, ["Primary error mechanism", "n"], rows)
    output_paths.append(str(path))

    actionability_counts = counts.get("actionability") if isinstance(counts.get("actionability"), dict) else {}
    rows = [{"Actionability category": _actionability_display_name(key), "n": int(value)} for key, value in actionability_counts.items()]
    path = out_dir / "table_taxonomy_actionability_counts.csv"
    _write_csv(path, ["Actionability category", "n"], rows)
    output_paths.append(str(path))
    return output_paths


def _write_pairwise_comparisons(
    gold: Dict[str, Dict[str, str]],
    preds_by_model: Dict[str, Dict[str, Dict[str, str]]],
    pred_na_policy: str,
    case_ids: List[str],
    out_dir: Path,
) -> List[str]:
    models = sorted(preds_by_model.keys())
    eval_by_model: Dict[str, Dict[str, Any]] = {
        model: _eval_model(gold, preds_by_model[model], pred_na_policy, case_ids) for model in models
    }
    rows: List[Dict[str, Any]] = []
    by_rule_rows: List[Dict[str, Any]] = []

    for model_a, model_b in itertools.combinations(models, 2):
        pred_a = preds_by_model[model_a]
        pred_b = preds_by_model[model_b]
        significant_rules: List[str] = []
        min_q: Optional[float] = None
        pvals: List[Optional[float]] = []

        pair_rule_rows: List[Dict[str, Any]] = []
        for rid in _RULES:
            n_eval = 0
            a_correct = 0
            b_correct = 0
            n01 = n10 = 0
            a_tp = a_fp = a_tn = a_fn = 0
            b_tp = b_fp = b_tn = b_fn = 0
            for cid in case_ids:
                g = gold.get(cid, {}).get(rid)
                if g is None or g == "NA" or g not in ("PASS", "FAIL"):
                    continue
                pa_raw = pred_a.get(cid, {}).get(rid)
                pb_raw = pred_b.get(cid, {}).get(rid)
                if not pa_raw or not pb_raw:
                    continue
                pa = _apply_pred_na_policy(pa_raw, pred_na_policy)
                pb = _apply_pred_na_policy(pb_raw, pred_na_policy)
                if pa not in ("PASS", "FAIL") or pb not in ("PASS", "FAIL"):
                    continue
                n_eval += 1
                ca = pa == g
                cb = pb == g
                a_correct += 1 if ca else 0
                b_correct += 1 if cb else 0
                if (not ca) and cb:
                    n01 += 1
                elif ca and (not cb):
                    n10 += 1
                if g == "FAIL" and pa == "FAIL":
                    a_tp += 1
                elif g == "FAIL" and pa == "PASS":
                    a_fn += 1
                elif g == "PASS" and pa == "FAIL":
                    a_fp += 1
                elif g == "PASS" and pa == "PASS":
                    a_tn += 1
                if g == "FAIL" and pb == "FAIL":
                    b_tp += 1
                elif g == "FAIL" and pb == "PASS":
                    b_fn += 1
                elif g == "PASS" and pb == "FAIL":
                    b_fp += 1
                elif g == "PASS" and pb == "PASS":
                    b_tn += 1
            pval = _mcnemar_exact_p(n01, n10)
            pvals.append(pval)
            metrics_a = _metrics_from_conf(_Confusion(tp=a_tp, fp=a_fp, tn=a_tn, fn=a_fn))
            metrics_b = _metrics_from_conf(_Confusion(tp=b_tp, fp=b_fp, tn=b_tn, fn=b_fn))
            acc_a = _safe_div(a_correct, n_eval)
            acc_b = _safe_div(b_correct, n_eval)
            f1_a = metrics_a.get("f1")
            f1_b = metrics_b.get("f1")
            pair_rule_rows.append(
                {
                    "model_a": model_a,
                    "model_b": model_b,
                    "rule": rid,
                    "n_evaluable": n_eval,
                    "n01_a_wrong_b_right": n01,
                    "n10_a_right_b_wrong": n10,
                    "accuracy_a": _fmt_float(acc_a, 6),
                    "accuracy_b": _fmt_float(acc_b, 6),
                    "accuracy_delta_a_minus_b": _fmt_float((float(acc_a) - float(acc_b)) if isinstance(acc_a, (int, float)) and isinstance(acc_b, (int, float)) else None, 6),
                    "f1_a": _fmt_float(f1_a, 6),
                    "f1_b": _fmt_float(f1_b, 6),
                    "f1_delta_a_minus_b": _fmt_float((float(f1_a) - float(f1_b)) if isinstance(f1_a, (int, float)) and isinstance(f1_b, (int, float)) else None, 6),
                    "mcnemar_p_exact": _fmt_float(pval, 6),
                }
            )

        qvals = _bh_fdr(pvals)
        for rid, q in zip(_RULES, qvals):
            if isinstance(q, (int, float)):
                min_q = float(q) if min_q is None else min(min_q, float(q))
                if float(q) < 0.05:
                    significant_rules.append(rid)
        for row, q in zip(pair_rule_rows, qvals):
            row["bh_fdr_q_within_pair"] = _fmt_float(q, 6)
            row["significant_q_lt_0_05"] = "yes" if isinstance(q, (int, float)) and float(q) < 0.05 else "no"
            row["pred_na_policy"] = pred_na_policy
            by_rule_rows.append(row)

        eval_a = eval_by_model.get(model_a, {})
        eval_b = eval_by_model.get(model_b, {})
        macro_a = eval_a.get("macro_f1")
        macro_b = eval_b.get("macro_f1")
        micro_a = eval_a.get("micro_f1")
        micro_b = eval_b.get("micro_f1")
        rows.append(
            {
                "model_a": model_a,
                "model_b": model_b,
                "macro_f1_a": _fmt_float(macro_a, 3),
                "macro_f1_b": _fmt_float(macro_b, 3),
                "macro_f1_delta": _fmt_float((float(macro_a) - float(macro_b)) if isinstance(macro_a, (int, float)) and isinstance(macro_b, (int, float)) else None, 3),
                "micro_f1_a": _fmt_float(micro_a, 3),
                "micro_f1_b": _fmt_float(micro_b, 3),
                "micro_f1_delta": _fmt_float((float(micro_a) - float(micro_b)) if isinstance(micro_a, (int, float)) and isinstance(micro_b, (int, float)) else None, 3),
                "sig_rules_fdr_q_lt_0_05": ",".join(significant_rules),
                "min_fdr_q": _fmt_float(min_q, 3),
            }
        )

    out_path = out_dir / "table_pairwise_comparisons.csv"
    _write_csv(
        out_path,
        [
            "model_a",
            "model_b",
            "macro_f1_a",
            "macro_f1_b",
            "macro_f1_delta",
            "micro_f1_a",
            "micro_f1_b",
            "micro_f1_delta",
            "sig_rules_fdr_q_lt_0_05",
            "min_fdr_q",
        ],
        rows,
    )
    by_rule_path = out_dir / "table_pairwise_comparisons_by_rule.csv"
    _write_csv(
        by_rule_path,
        [
            "model_a",
            "model_b",
            "rule",
            "n_evaluable",
            "n01_a_wrong_b_right",
            "n10_a_right_b_wrong",
            "accuracy_a",
            "accuracy_b",
            "accuracy_delta_a_minus_b",
            "f1_a",
            "f1_b",
            "f1_delta_a_minus_b",
            "mcnemar_p_exact",
            "bh_fdr_q_within_pair",
            "significant_q_lt_0_05",
            "pred_na_policy",
        ],
        by_rule_rows,
    )
    return [str(out_path), str(by_rule_path)]


def _write_semantic_sufficiency_tables(source_dir: Path, out_dir: Path) -> List[str]:
    mapping = {
        "table_semantic_sufficiency_overall.csv": "table_s12_semantic_sufficiency_overall.csv",
        "table_semantic_sufficiency_by_model.csv": "table_s13_semantic_sufficiency_by_model.csv",
        "table_semantic_sufficiency_by_rule.csv": "table_s14_semantic_sufficiency_by_rule.csv",
    }
    wrote: List[str] = []
    for src_name, dst_name in mapping.items():
        src = source_dir / src_name
        if not src.exists():
            continue
        dst = out_dir / dst_name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        wrote.append(str(dst))
    agreement = source_dir / "semantic_sufficiency_agreement.json"
    if agreement.exists():
        dst = out_dir / "semantic_sufficiency_agreement.json"
        shutil.copy2(agreement, dst)
        wrote.append(str(dst))
        obj = _load_json(agreement)
        if isinstance(obj, dict):
            row = {key: obj.get(key, "") for key in sorted(obj.keys())}
            table = out_dir / "table_s15_semantic_sufficiency_agreement.csv"
            _write_csv(table, list(row.keys()), [row])
            wrote.append(str(table))
    return wrote


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold_dataset_summary_json", default="results/paper/gold_dataset_summary.json")
    parser.add_argument("--gold_eval_viz_json", default="data/gold/gold_700/gold_eval_viz/gold_eval_models_summary.json")
    parser.add_argument("--kappa_json", default="results/gold_eval/kappa_final_vs_b.json")
    parser.add_argument("--gold_labels_jsonl", default="data/gold/labels/labels_final.jsonl")
    parser.add_argument("--summaries_dir", default="data/gold/gold_700/gold_700/summaries")
    parser.add_argument("--gold_runs_dir", default="data/gold/gold_700/gold_700/runs")
    parser.add_argument("--cases_dir", default="data/gold/cases")
    parser.add_argument("--pred_na_policy", default="as_pass", choices=("exclude", "as_pass", "as_fail"))
    parser.add_argument("--taxonomy_summary_json", default="results/paper/error_taxonomy/taxonomy_summary.json")
    parser.add_argument("--semantic_sufficiency_dir", default="results/paper/semantic_sufficiency")
    # NOTE: We always export taxonomy summary tables when taxonomy_summary.json is present,
    # because the manuscript references Supplementary Tables S5–S6. This flag is kept for
    # backward compatibility and has no effect.
    parser.add_argument("--include_taxonomy", action="store_true")
    parser.add_argument("--out_dir", default="results/paper/tables")
    parser.add_argument("--out_dir_supp", default="results/paper/tables_supp")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir_supp = Path(args.out_dir_supp)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_dir_supp.mkdir(parents=True, exist_ok=True)
    _clean_csvs(out_dir)
    _clean_csvs(out_dir_supp)

    dataset = _load_json(Path(args.gold_dataset_summary_json))
    eval_viz = _load_json(Path(args.gold_eval_viz_json))
    kappa = _load_json(Path(args.kappa_json))
    gold = _load_gold_labels(Path(args.gold_labels_jsonl))
    case_ids = sorted(gold.keys())

    summary_paths = _discover_summary_jsons(Path(args.summaries_dir))
    if not summary_paths:
        raise SystemExit(f"No summary JSONs found under: {args.summaries_dir}")
    preds_by_model: Dict[str, Dict[str, Dict[str, str]]] = {}
    for p in summary_paths:
        preds_by_model[_model_name_from_summary_path(p)] = _load_model_preds_from_summary(p)

    wrote = [
        _write_dataset_audit_burden(dataset, out_dir),
        _write_model_performance_summary(eval_viz, out_dir),
        _write_rule_audit_characteristics(dataset, kappa, out_dir),
        _write_model_rule_performance_full(eval_viz, out_dir_supp),
        _write_pred_na_policy_sensitivity(gold, preds_by_model, case_ids, out_dir_supp),
        _write_predicted_na_rates(gold, preds_by_model, case_ids, out_dir_supp),
        _write_rule_conditioned_snippet_stats(Path(args.cases_dir), out_dir_supp),
        _write_evidence_recoverability_stats(
            eval_viz=eval_viz,
            gold=gold,
            gold_runs_dir=Path(args.gold_runs_dir),
            cases_dir=Path(args.cases_dir),
            out_dir_supp=out_dir_supp,
        ),
    ]
    wrote.extend(_write_pairwise_comparisons(gold, preds_by_model, str(args.pred_na_policy), case_ids, out_dir_supp))

    taxonomy_path = Path(args.taxonomy_summary_json)
    if taxonomy_path.exists():
        wrote.extend(_write_taxonomy_tables(_load_json(taxonomy_path), out_dir_supp))

    wrote.extend(_write_semantic_sufficiency_tables(Path(args.semantic_sufficiency_dir), out_dir_supp))

    print(json.dumps({"wrote": wrote}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
