from __future__ import annotations

import argparse
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from gej_audit.llm_rule_pipeline import RULE_ORDER


RULES: List[str] = list(RULE_ORDER)


def _is_audit_error(reason: Optional[str]) -> bool:
    if reason is None:
        return False
    s = str(reason).strip()
    if not s:
        return False
    return s.startswith("规则审计失败") or s.startswith("è§???????è???¤±è′￥")


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


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    raw = path.read_text(encoding="utf-8-sig")
    for ln in raw.splitlines():
        line = ln.strip()
        if not line:
            continue
        items.append(json.loads(line))
    return items


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
    for r in rows:
        if not isinstance(r, dict):
            continue
        cid = str(r.get("case_id") or "").strip()
        if not cid:
            continue
        labels = r.get("labels")
        if not isinstance(labels, dict):
            continue

        by_rule: Dict[str, str] = {}
        for rid in RULES:
            v = labels.get(rid)
            if isinstance(v, str):
                st = _normalize_status(v)
            elif isinstance(v, dict):
                st = _normalize_status(v.get("status"))
            else:
                st = ""
            if st:
                by_rule[rid] = st
        if by_rule:
            labels_by_case[cid] = by_rule

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
                values = [x.get("case_id") for x in obj["examples"] if isinstance(x, dict)]
        else:
            values = obj
        if isinstance(values, list):
            out.update(str(x).strip() for x in values if str(x).strip())
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


def _load_pred_dir(results_dir: Path) -> Dict[str, PredCase]:
    if not results_dir.exists() or not results_dir.is_dir():
        raise SystemExit(f"Pred dir not found: {results_dir}")

    items: Dict[str, PredCase] = {}
    for p in results_dir.glob("case_*.json"):
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        rr = payload.get("rule_results") if isinstance(payload, dict) else None
        if not isinstance(rr, list):
            continue

        case_id = p.stem.replace("case_", "", 1)
        by_rule: Dict[str, PredRule] = {}
        for r in rr:
            if not isinstance(r, dict):
                continue
            rid = str(r.get("rule_id") or "").strip()
            if rid not in RULES:
                continue
            st = _normalize_status(r.get("status"))
            if not st:
                continue
            reason = r.get("reason")
            evidence_raw = r.get("evidence")
            if evidence_raw is None:
                evidence_raw = r.get("evidences")
            if evidence_raw is None:
                evidence: List[str] = []
            elif isinstance(evidence_raw, list):
                evidence = [str(x) for x in evidence_raw]
            else:
                evidence = [str(evidence_raw)]
            by_rule[rid] = PredRule(status=st, reason=str(reason) if reason is not None else None, evidence=evidence)

        items[case_id] = PredCase(
            case_id=case_id,
            source_path=str(payload.get("source_path")) if isinstance(payload, dict) and payload.get("source_path") else None,
            by_rule=by_rule,
        )

    return items


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


def _metrics_from_conf(c: Confusion) -> Dict[str, Optional[float]]:
    sens = _safe_div(c.tp, c.tp + c.fn)
    spec = _safe_div(c.tn, c.tn + c.fp)
    ppv = _safe_div(c.tp, c.tp + c.fp)
    npv = _safe_div(c.tn, c.tn + c.fn)
    f1 = _safe_div(2 * c.tp, 2 * c.tp + c.fp + c.fn)
    acc = _safe_div(c.tp + c.tn, c.tp + c.fp + c.tn + c.fn)
    return {"sensitivity": sens, "specificity": spec, "ppv": ppv, "npv": npv, "f1": f1, "accuracy": acc}


def _percentile(xs: List[float], q: float) -> float:
    if not xs:
        raise ValueError("empty")
    ys = sorted(xs)
    if q <= 0:
        return ys[0]
    if q >= 1:
        return ys[-1]
    k = (len(ys) - 1) * q
    f = int(k)
    c = min(f + 1, len(ys) - 1)
    if c == f:
        return ys[f]
    return ys[f] + (ys[c] - ys[f]) * (k - f)


def _bootstrap_ci(
    case_ids: List[str],
    by_case: Dict[str, Tuple[str, str]],
    n: int,
    rng: random.Random,
) -> Dict[str, Optional[Tuple[float, float]]]:
    samples: Dict[str, List[float]] = {"sensitivity": [], "specificity": [], "ppv": [], "npv": [], "f1": [], "accuracy": []}

    for _ in range(n):
        tp = fp = tn = fn = 0
        for _j in range(len(case_ids)):
            cid = rng.choice(case_ids)
            gold, pred = by_case[cid]
            if gold == "FAIL" and pred == "FAIL":
                tp += 1
            elif gold == "FAIL" and pred == "PASS":
                fn += 1
            elif gold == "PASS" and pred == "FAIL":
                fp += 1
            elif gold == "PASS" and pred == "PASS":
                tn += 1

        m = _metrics_from_conf(Confusion(tp=tp, fp=fp, tn=tn, fn=fn))
        for k, v in m.items():
            if v is not None:
                samples[k].append(float(v))

    ci: Dict[str, Optional[Tuple[float, float]]] = {}
    for k, xs in samples.items():
        if not xs:
            ci[k] = None
            continue
        lo = _percentile(xs, 0.025)
        hi = _percentile(xs, 0.975)
        ci[k] = (float(lo), float(hi))
    return ci


def _normalize_for_contains(text: str) -> str:
    s = str(text or "")
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"\s+", "", s)
    return s


def _resolve_case_text(case_id: str, pred: PredCase, cases_dir: Optional[Path]) -> Optional[str]:
    if cases_dir is not None:
        candidates = list(cases_dir.glob(f"{case_id}.*"))
        if candidates:
            try:
                return candidates[0].read_text(encoding="utf-8")
            except Exception:
                return None

    if pred.source_path:
        sp = Path(pred.source_path)
        if not sp.is_absolute():
            sp = Path(".") / sp
        if sp.exists():
            try:
                return sp.read_text(encoding="utf-8")
            except Exception:
                return None

    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold_labels", required=True, help="Gold labels file (.jsonl recommended)")
    parser.add_argument("--pred_dir", required=True, help="Directory containing case_*.json predictions")
    parser.add_argument("--cases_dir", default="", help="Optional cases dir for evidence-in-text check")
    parser.add_argument("--exclude_case_ids", default="", help="Optional TXT/JSON file with case IDs to exclude from evaluation")
    parser.add_argument(
        "--pred_na_policy",
        default="as_pass",
        choices=("exclude", "as_pass", "as_fail"),
        help="How to handle prediction NA when gold is PASS/FAIL",
    )
    parser.add_argument("--exclude_audit_errors", action="store_true", help="Exclude audit_error FAIL from accuracy eval")
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260117)
    parser.add_argument("--out_json", default="results/gold_eval/eval_gold.json")
    parser.add_argument("--out_md", default="results/gold_eval/eval_gold.md")
    args = parser.parse_args()

    gold_path = Path(args.gold_labels)
    pred_dir = Path(args.pred_dir)
    cases_dir = Path(args.cases_dir) if str(args.cases_dir).strip() else None
    exclude_case_ids = _load_case_id_set(Path(args.exclude_case_ids)) if str(args.exclude_case_ids).strip() else set()

    gold = _load_gold_labels(gold_path)
    if exclude_case_ids:
        gold = {cid: labels for cid, labels in gold.items() if cid not in exclude_case_ids}
    pred = _load_pred_dir(pred_dir)

    rng = random.Random(int(args.seed))

    per_rule: Dict[str, Any] = {}
    overall_audit_error = 0
    overall_eval_pairs = 0

    evidence_total = 0
    evidence_in_text = 0
    evidence_cases_checked = 0

    for rid in RULES:
        pairs: Dict[str, Tuple[str, str]] = {}
        skipped_gold_na = 0
        skipped_pred_missing = 0
        skipped_pred_audit_error = 0
        skipped_pred_na = 0

        for cid, gold_by_rule in gold.items():
            g = gold_by_rule.get(rid)
            if g is None:
                continue
            if g == "NA":
                skipped_gold_na += 1
                continue
            if g not in ("PASS", "FAIL"):
                continue

            pr = pred.get(cid)
            if pr is None:
                skipped_pred_missing += 1
                continue
            rr = pr.by_rule.get(rid)
            if rr is None:
                skipped_pred_missing += 1
                continue

            if rr.status == "FAIL" and _is_audit_error(rr.reason):
                overall_audit_error += 1
                if args.exclude_audit_errors:
                    skipped_pred_audit_error += 1
                    continue

            p = rr.status
            if p == "NA":
                if args.pred_na_policy == "exclude":
                    skipped_pred_na += 1
                    continue
                if args.pred_na_policy == "as_fail":
                    p = "FAIL"
                else:
                    p = "PASS"

            if p not in ("PASS", "FAIL"):
                skipped_pred_missing += 1
                continue

            pairs[cid] = (g, p)

            if rr.status == "FAIL" and (not _is_audit_error(rr.reason)):
                case_text = _resolve_case_text(cid, pr, cases_dir)
                if case_text is not None:
                    evidence_cases_checked += 1
                    hay = _normalize_for_contains(case_text)
                    for ev in rr.evidence:
                        e = str(ev or "").strip()
                        if not e:
                            continue
                        evidence_total += 1
                        if _normalize_for_contains(e) in hay:
                            evidence_in_text += 1

        case_ids = sorted(pairs)
        overall_eval_pairs += len(case_ids)

        tp = fp = tn = fn = 0
        for cid in case_ids:
            g, p = pairs[cid]
            if g == "FAIL" and p == "FAIL":
                tp += 1
            elif g == "FAIL" and p == "PASS":
                fn += 1
            elif g == "PASS" and p == "FAIL":
                fp += 1
            elif g == "PASS" and p == "PASS":
                tn += 1

        conf = Confusion(tp=tp, fp=fp, tn=tn, fn=fn)
        m = _metrics_from_conf(conf)
        ci = _bootstrap_ci(case_ids=case_ids, by_case=pairs, n=int(args.bootstrap), rng=rng) if case_ids else {}

        per_rule[rid] = {
            "n_eval": len(case_ids),
            "confusion": conf.__dict__,
            "metrics": m,
            "ci95_bootstrap": ci,
            "skipped": {
                "gold_na": skipped_gold_na,
                "pred_missing": skipped_pred_missing,
                "pred_audit_error": skipped_pred_audit_error,
                "pred_na": skipped_pred_na,
            },
        }

    evidence_in_text_rate = (float(evidence_in_text) / float(evidence_total)) if evidence_total else None

    out = {
        "gold_labels": str(gold_path),
        "pred_dir": str(pred_dir),
        "rules": RULES,
        "pred_na_policy": str(args.pred_na_policy),
        "exclude_audit_errors": bool(args.exclude_audit_errors),
        "bootstrap": int(args.bootstrap),
        "seed": int(args.seed),
        "excluded_case_ids": sorted(exclude_case_ids),
        "per_rule": per_rule,
        "audit_error_rules_in_eval_scan": int(overall_audit_error),
        "total_rule_pairs_eval": int(overall_eval_pairs),
        "evidence_in_text": {
            "cases_checked": int(evidence_cases_checked),
            "evidence_items_total": int(evidence_total),
            "evidence_items_in_text": int(evidence_in_text),
            "evidence_in_text_rate": evidence_in_text_rate,
        },
    }

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines: List[str] = []
    lines.append("# D_gold 评测汇总")
    lines.append("")
    lines.append(f"- gold_labels: `{gold_path}`")
    lines.append(f"- pred_dir: `{pred_dir}`")
    lines.append(f"- pred_na_policy: `{args.pred_na_policy}`")
    lines.append(f"- exclude_audit_errors: `{bool(args.exclude_audit_errors)}`")
    lines.append(f"- bootstrap: `{int(args.bootstrap)}`")
    if exclude_case_ids:
        lines.append(f"- excluded_case_ids: `{len(exclude_case_ids)}`")
    lines.append("")

    lines.append("## 规则级诊断准确性")
    lines.append("")
    lines.append("| 规则 | n | Sens | Spec | PPV | NPV | F1 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for rid in RULES:
        pr = per_rule.get(rid, {})
        n = int(pr.get("n_eval") or 0)
        m = pr.get("metrics") or {}

        def _cell(key: str) -> str:
            v = m.get(key)
            return f"{float(v):.3f}" if isinstance(v, (int, float)) else "NA"

        lines.append(f"| {rid} | {n} | {_cell('sensitivity')} | {_cell('specificity')} | {_cell('ppv')} | {_cell('npv')} | {_cell('f1')} |")

    lines.append("")
    eit = out["evidence_in_text"]
    lines.append("## Evidence-in-text")
    lines.append("")
    lines.append(
        f"- cases_checked={eit['cases_checked']}; evidence_items_in_text={eit['evidence_items_in_text']}/{eit['evidence_items_total']}; rate={eit['evidence_in_text_rate']}"
    )
    lines.append("")

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"wrote": [str(out_json), str(out_md)]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
