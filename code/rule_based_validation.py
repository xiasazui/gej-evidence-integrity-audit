"""Rule-based validation of format-rescued and residual non-locatable snippets (public layer).

Every snippet classified as field_prefix, ellipsis_join or non_locatable by the primary
categorizer (code/normalization_core.py) is checked deterministically against the parsed
record fields. No model is called.

  Prefix attribution (field_prefix)
     correct_field     the label is the record field that contains the quotation
     correct_inline    the label is an inline sub-heading preceding the quotation in the same field
     misattributed     the label names a different record field
     descriptive_label the label does not occur in the record; the quotation is exact
  Ellipsis joins (ellipsis_join)
     order_preserved   parts occur in source order
     cross_field       parts lie in more than one field (descriptive)
     negation_dropped  omitted text within four characters of a join contains a negation marker
     misleading_join   order not preserved or negation dropped
  Incorrect rescue = misattributed prefix or misleading join; the stricter normalizer becomes
  primary if incorrect rescues reach 10% of rescued snippets.
  Residual non-locatable snippets (first matching class): field_list, field_name_only,
  rule_reference, template_repair, near_copy, absence_statement, other.

Writes results/rule_based_validation_items.csv, results/rule_based_validation_by_system.csv
and results/rule_based_validation_summary.json.
Usage: python code/rule_based_validation.py
"""
import csv
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict

from rapidfuzz import fuzz

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "code"))
from normalization_core import categorize, ws as norm_ws  # noqa: E402
RES = os.path.join(REPO, "results")
CASES = os.path.join(REPO, "data", "synthetic_cases")
PROMPT_SRC = os.path.join(REPO, "code", "frozen_prompt_rule_pipeline.py")


def candidate_items():
    """Every non-verbatim snippet in predicted-FAIL outputs of the public frozen outputs."""
    seeds = {r["case_id"]: r.get("seed_id", "") for r in csv.DictReader(open(os.path.join(REPO, "data", "synthetic_lineage.csv"), encoding="utf-8-sig"))} if os.path.exists(os.path.join(REPO, "data", "synthetic_lineage.csv")) else {}
    texts = {os.path.basename(p)[:-3]: norm_ws(open(p, encoding="utf-8").read()) for p in glob.glob(os.path.join(CASES, "*.md"))}
    items = []
    for f in sorted(glob.glob(os.path.join(REPO, "data", "model_outputs", "*.jsonl"))):
        for line in open(f, encoding="utf-8"):
            d = json.loads(line)
            for r in d["rule_results"]:
                if r["status"] != "FAIL":
                    continue
                for i, e in enumerate(r.get("evidence") or []):
                    e = e if isinstance(e, str) else json.dumps(e, ensure_ascii=False)
                    c = categorize(e, texts[d["case_id"]])
                    if c in ("field_prefix", "ellipsis_join", "non_locatable"):
                        items.append({"model": d["model"], "case_id": d["case_id"], "seed_id": seeds.get(d["case_id"], ""), "rule": r["rule_id"],
                                      "snippet_index": i, "category": c, "source_class": "", "snippet": e})
    return items

PREFIX = re.compile(r"^([^:：]{1,12})[:：](.+)$")
ELLIPSIS = re.compile(r"…+|\.{3,}|⋯+")
RULE_REF = re.compile(r"范围|定义|规定|(?<!不)规则|要求|应为|Siewert ?I{1,3}型?[:：].{0,6}Z线")
ABSENCE = re.compile(r"未.{0,6}(提及|提供|记录|描述|见|找到|标注|单列|出现|注明|包含|列出)|仅见|缺失|缺少|没有|不存在|无.{0,20}(描述|记录|字段|信息|距离|条目)|missing|absent|not (documented|provided|found|mentioned)", re.I)
NEGATION = ("未", "无", "否认", "不伴", "不除外", "非", "可疑", "待排", "除外", "排除", "没有", "阴性")
NEGATION_INITIAL = ("未", "无", "否认", "不伴", "不除外", "非", "可疑", "待排", "除外", "排除", "没有", "阴性", "不")
# Initial rule, reported as a sensitivity check: the bare negation character also matched the word for 'irregular'.
MODEL_SHORT = {
    "MiniMax-M2.1": "MiniMax-M2.1", "deepseek-v3.2-thinking": "DeepSeek-V3.2-Thinking",
    "gemini-3-pro-preview-thinking": "Gemini-3-Pro-Preview-Thinking", "gpt-5.2": "GPT-5.2",
    "gpt-oss-120b": "gpt-oss-120b", "gpt-oss-20b": "gpt-oss-20b",
    "kimi-k2-thinking": "Kimi-K2-Thinking", "qwen3-235b-a22b-thinking-2507": "Qwen3-235B-A22B-Thinking-2507",
    "qwen3-30b-a3b-thinking-2507": "Qwen3-30B-A3B-Thinking-2507", "qwen3-next-80b-a3b-thinking": "Qwen3-Next-80B-A3B-Thinking",
    "deterministic-baseline": "Regex baseline",
}


def ws(text):
    return re.sub(r"\s+", "", text)


def unify(text):
    return text.replace("：", ":")


def parse_record(path):
    """Return whitespace-free source and a list of (field, start, end) spans."""
    src, spans = "", []
    for line in open(path, encoding="utf-8"):
        line = ws(line)
        if not line:
            continue
        m = re.match(r"^([^:：]{1,8})[:：]", line)
        start = len(src)
        src += line
        if m:
            spans.append((m.group(1), start, len(src)))
        elif spans:
            f, s, _ = spans[-1]
            spans[-1] = (f, s, len(src))
    return src, spans


def field_at(spans, pos):
    for f, s, e in spans:
        if s <= pos < e:
            return f
    return None


def prompt_corpus():
    text = open(PROMPT_SRC, encoding="utf-8").read()
    lits = re.findall(r'"((?:[^"\\]|\\.)*)"', text)
    corpus = "".join(lits).replace("\\n", "")
    return ws(re.sub(r"\*\*", "", corpus))


def collapse_dupes(text):
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"(.{2,4})\1", r"\1", text)
    return text


def classify_prefix(snip, src, spans, fields):
    m = PREFIX.match(snip)
    pre, rest = m.group(1), m.group(2)
    if unify(pre + ":" + rest) in unify(src):
        pos = unify(src).find(unify(pre + ":" + rest))
        return "correct_field" if field_at(spans, pos) == pre else "correct_inline"
    hits = [m2.start() for m2 in re.finditer(re.escape(rest), src)]
    if pre in fields:
        owners = {field_at(spans, h) for h in hits}
        return "correct_field" if pre in owners else "misattributed"
    for h in hits:
        window = unify(src[max(0, h - 40):h])
        if unify(pre) in window and field_at(spans, h) == field_at(spans, h - 1 - window[::-1].find(unify(pre)[::-1])):
            return "correct_inline"
    return "descriptive_label"


def strip_prefix(part, src):
    if part in src:
        return part
    m = PREFIX.match(part)
    if m and m.group(2) in src:
        return m.group(2)
    return part


def classify_join(snip, src, spans):
    parts = [strip_prefix(p, src) for p in ELLIPSIS.split(snip) if p]
    cursor, order_ok, locs = 0, True, []
    for p in parts:
        pos = src.find(p, cursor)
        if pos < 0:
            order_ok = False
            pos = src.find(p)
        else:
            cursor = pos + len(p)
        locs.append((pos, pos + len(p)))
    fields_hit = {field_at(spans, s) for s, _ in locs}
    neg = neg_initial = False
    if order_ok:
        for (s1, e1_), (s2, _) in zip(locs, locs[1:]):
            gap = src[e1_:s2]
            if any(t in gap[:4] or t in gap[-4:] for t in NEGATION):
                neg = True
            if any(t in gap[:4] or t in gap[-4:] for t in NEGATION_INITIAL):
                neg_initial = True
    return {
        "order_preserved": int(order_ok),
        "cross_field": int(len(fields_hit) > 1),
        "negation_dropped": int(neg),
        "misleading_join": int((not order_ok) or neg),
        "misleading_join_initial_rule": int((not order_ok) or neg_initial),
        "n_parts": len(parts),
    }


def numbers(text):
    return set(re.findall(r"\d+(?:\.\d+)?", text))


def classify_residual(snip, src, fields, corpus):
    core = snip
    m = PREFIX.match(core)
    if m and m.group(1) in fields:
        core = m.group(2)
    r_prompt = fuzz.partial_ratio(snip, corpus) if len(snip) >= 6 else 0
    r_src = fuzz.partial_ratio(core, src)
    if sum(1 for f in fields if f in snip) >= 3:
        return "field_list", r_src
    bare = re.sub(r"[:：]?(缺失|未提及|无|空)?$", "", snip)
    if bare in fields:
        return "field_name_only", r_src
    if RULE_REF.search(snip) or ((snip in corpus or core in corpus or r_prompt >= 90) and r_prompt > r_src):
        return "rule_reference", r_src
    if core in collapse_dupes(src) or collapse_dupes(core) in collapse_dupes(src):
        return "template_repair", r_src
    if r_src >= 90:
        return "near_copy", r_src
    if ABSENCE.search(snip):
        return "absence_statement", r_src
    if numbers(core) - numbers(src):
        return "new_number", r_src
    return "other", r_src


def main():
    corpus = prompt_corpus()
    records = {}
    for p in glob.glob(os.path.join(CASES, "*.md")):
        records[os.path.basename(p)[:-3]] = parse_record(p)
    fields = sorted({f for _, sp in records.values() for f, _, _ in sp})
    os.makedirs(RES, exist_ok=True)
    items = candidate_items()
    rows = []
    for it in items:
        src, spans = records[it["case_id"]]
        snip = ws(it["snippet"])
        row = {k: it[k] for k in ("model", "case_id", "seed_id", "rule", "snippet_index", "category", "source_class", "snippet")}
        row["model_label"] = MODEL_SHORT.get(it["model"], it["model"])
        row.update(prefix_class="", order_preserved="", cross_field="", negation_dropped="", misleading_join="", misleading_join_initial_rule="", n_parts="", residual_class="", src_partial_ratio="")
        if it["category"] == "field_prefix":
            row["prefix_class"] = classify_prefix(snip, src, spans, fields)
        elif it["category"] == "ellipsis_join":
            row.update(classify_join(snip, src, spans))
        elif it["category"] == "non_locatable":
            cls, r = classify_residual(snip, src, fields, corpus)
            row["residual_class"], row["src_partial_ratio"] = cls, round(r, 1)
        rows.append(row)

    out = os.path.join(RES, "rule_based_validation_items.csv")
    with open(out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    pref = [r for r in rows if r["category"] == "field_prefix"]
    ell = [r for r in rows if r["category"] == "ellipsis_join"]
    res = [r for r in rows if r["category"] == "non_locatable"]
    e1c = Counter(r["prefix_class"] for r in pref)
    mis_join = sum(int(r["misleading_join"]) for r in ell)
    incorrect = e1c["misattributed"] + mis_join
    rescued = len(pref) + len(ell)
    summary = {
        "rescued_items": rescued,
        "prefix_items": len(pref),
        "prefix_attribution": dict(e1c),
        "ellipsis_items": len(ell),
        "joins_order_preserved": sum(int(r["order_preserved"]) for r in ell),
        "joins_cross_field": sum(int(r["cross_field"]) for r in ell),
        "joins_negation_dropped": sum(int(r["negation_dropped"]) for r in ell),
        "joins_misleading": mis_join,
        "incorrect_rescues": incorrect,
        "incorrect_rescues_initial_rule": e1c["misattributed"] + sum(int(r["misleading_join_initial_rule"]) for r in ell),
        "incorrect_rescue_proportion": incorrect / rescued,
        "switch_to_strict": incorrect / rescued >= 0.10,
        "residual_items": len(res),
        "residual_classes": dict(Counter(r["residual_class"] for r in res)),
    }
    json.dump(summary, open(os.path.join(RES, "rule_based_validation_summary.json"), "w"), ensure_ascii=False, indent=2)

    by_model = defaultdict(Counter)
    for r in rows:
        key = r["prefix_class"] or ("misleading_join" if r["misleading_join"] == 1 else ("join_ok" if r["category"] == "ellipsis_join" else "")) or r["residual_class"]
        by_model[r["model_label"]][f'{r["category"]}:{key}'] += 1
    cats = sorted({k for c in by_model.values() for k in c})
    with open(os.path.join(RES, "rule_based_validation_by_system.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["model"] + cats)
        for m in sorted(by_model):
            w.writerow([m] + [by_model[m][c] for c in cats])
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
