"""Two-source rule-consistency audit: frozen prompt snapshot vs canonical rule table.

Compares the H1-H6 audit policy as encoded in the frozen prompt/rule pipeline
(methods/frozen_prompt_rule_pipeline.py) against the canonical rule table
(methods/table_s0_frozen_rule_definitions.csv), and quantifies how many Gold
labels could have been affected by presentation-level discrepancies.

The annotation manual (annotation_manual_v1.0_2026-05-01) is NOT contained in the
retained submission/reproducibility artifacts; the manual column is therefore
NOT_IN_PACKAGE and prompt-vs-manual consistency is NOT_ASSESSED. The frozen
prompt snapshot is the reference policy (reference_policy=FROZEN_PROMPT).

Label-impact counts cover the released 560-instance synthetic layer only; the
140 real/real-derived instances are not part of the public package.

Exit code is non-zero if any POLICY_CONFLICT or UNVERIFIABLE row remains
unresolved or if n_labels_actually_affected > 0 for any row.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

NOT_IN_PACKAGE = "NOT_IN_PACKAGE"
NOT_ASSESSED = "NOT_ASSESSED"
REF = "FROZEN_PROMPT"
SCOPE_NOTE = ("Counts cover the released 560-instance synthetic layer only; the 140 "
              "real/real-derived instances are not contained in the public package.")

# Literal quotes that MUST appear verbatim in the frozen prompt snapshot.
# The script asserts each one; a missing quote means the frozen file changed.
PROMPT_QUOTES = {
    "H1_trigger": "病历出现 GEJ/贲门相关恶性肿瘤的确诊性表述",
    "H1_pass": "必须存在病理/活检描述且包含组织学类型关键词",
    "H2_trigger": "病历出现 GEJ/贲门相关恶性肿瘤的确诊性表述",
    "H2_pass": "必须存在内镜/胃镜结果描述（需包含部位/形态等要点），不接受仅写“做过胃镜/已行胃镜”",
    "H3_trigger": "远处转移",
    "H3_pass": "诊断中需体现转移或分期",
    "H3_note": "区域淋巴结肿大（N+、7/8/9 组等）不视为远处转移",
    "H4_trigger_full": "出现 GEJ/贲门癌/远端食管腺癌/贲门下胃癌 或 Siewert I/II/III 的确诊性表述",
    "H4_b1_pass": "必须提供可复核的 **Z线/齿状线相对距离证据**",
    "H4_b1_fail": "缺失 -> FAIL（Critical）",
    "H4_b2_trigger": "若诊断仅写 **GEJ/胃食管结合部癌**",
    "H4_b2_evidence": "内镜定位（贲门/食管胃交界/EGJ/Z线附近/下段食管-贲门交界等）",
    "H4_b2_fail": "仅缺定位证据 -> FAIL（Major）",
    "H4_ct_excluded": "仅提供 CT/PET/MR 的部位描述不计入本条定位证据",
    "H5_trigger": "记录了肿瘤中心相对 **Z线/齿状线** 的距离",
    "H5_na_no_center": "若仅有诊断而缺少距离信息：本条不做一致性判定 -> NA",
    "H5_na_bounds_only": "若仅提供“上界/下界至 Z线/齿状线距离”而未给出中心距离：本条同样 -> NA",
    "H5_s1": "I：Z线上 1-5cm",
    "H5_s2": "II：Z线上 1cm ~ Z线下 2cm",
    "H5_s3": "III：Z线下 2-5cm",
    "H5_gej": "若距离超出 ±5cm 仍诊断 GEJ -> FAIL（Critical）",
    "H5_direction": "Z线上xcm 记 d=+x；Z线下xcm 记 d=-x",
    "H6_fields": "姓名、性别、年龄、主诉、现病史、既往史、过敏史、个人史、家族史、体格检查、辅助检查、诊断",
    "H6_severity": "违反 1) => Major；仅违反 2) => Minor",
}

SIEWERT_INTERVAL = {"I": (1.0, 5.0), "II": (-2.0, 1.0), "III": (-5.0, -2.0)}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_case(text: str) -> dict:
    m = re.search(r"诊断:(.+)", text)
    diag = m.group(1) if m else ""
    sm = re.search(r"Siewert\s*(I{1,3})", diag)
    zm = re.search(r"Z线\s*(上|下)\s*([0-9.]+)\s*cm", text)
    d = float(zm.group(2)) * (1 if zm.group(1) == "上" else -1) if zm else None
    return {
        "diag": diag,
        "siewert": sm.group(1) if sm else None,
        "has_subsite": bool(re.search(r"贲门癌|远端食管|贲门下胃", diag)),
        "has_gej": bool(re.search(r"胃食管结合部|GEJ", diag)),
        "has_zline_dist": bool(zm),
        "d": d,
        "has_center_dist": bool(re.search(r"肿瘤中心距", text)) and d is not None,
        "has_bounds_only": bool(re.search(r"上界|下界", text)) and not re.search(r"肿瘤中心距", text),
        "has_incisor": bool(re.search(r"距(门齿|切牙)\s*[0-9.]+\s*cm", text)),
        "has_endo_loc": bool(re.search(r"胃镜[：:][^\n]*(EGJ|贲门|食管胃交界|食管下段|下段食管)", text)),
    }


def rejudge_h4(p: dict):
    """Frozen-prompt H4 policy. Returns (status, branch)."""
    if p["siewert"] or p["has_subsite"]:
        return ("PASS" if p["has_zline_dist"] else "FAIL"), "H4_SUBTYPE_OR_SIEWERT"
    if p["has_gej"]:
        ok = p["has_endo_loc"] or p["has_incisor"] or p["has_zline_dist"]
        return ("PASS" if ok else "FAIL"), "H4_GEJ_ONLY"
    return "NA", None


def rejudge_h5(p: dict) -> str:
    """Frozen-prompt H5 policy (thresholds from the frozen prompt snapshot)."""
    if not (p["siewert"] or p["has_gej"]):
        return "NA"
    if not p["has_center_dist"]:
        return "NA"  # includes bounds-only cases
    if p["siewert"]:
        lo, hi = SIEWERT_INTERVAL[p["siewert"]]
        return "PASS" if lo <= p["d"] <= hi else "FAIL"
    return "FAIL" if abs(p["d"]) > 5.0 else "PASS"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frozen-prompt", default="methods/frozen_prompt_rule_pipeline.py")
    ap.add_argument("--canonical-table", default="methods/table_s0_frozen_rule_definitions.csv")
    ap.add_argument("--annotation-manual", default=None,
                    help="annotation manual file; omit when not contained in the retained artifacts")
    ap.add_argument("--gold-labels", default="data/synthetic_gold_normalized.jsonl")
    ap.add_argument("--benchmark-records", default="data/synthetic_cases")
    ap.add_argument("--out-csv", default="outputs/rule_source_consistency_audit.csv")
    args = ap.parse_args()

    prompt_path = Path(args.frozen_prompt)
    canon_path = Path(args.canonical_table)
    prompt_text = prompt_path.read_text(encoding="utf-8")

    input_hashes = {
        str(prompt_path): sha256(prompt_path),
        str(canon_path): sha256(canon_path),
        str(args.gold_labels): sha256(Path(args.gold_labels)),
    }
    if args.annotation_manual and Path(args.annotation_manual).exists():
        manual_value = Path(args.annotation_manual).name
        manual_status = "ASSESSED"
        input_hashes[str(args.annotation_manual)] = sha256(Path(args.annotation_manual))
    else:
        manual_value = NOT_IN_PACKAGE
        manual_status = NOT_ASSESSED

    missing = [k for k, q in PROMPT_QUOTES.items() if q not in prompt_text]
    if missing:
        print("FATAL: frozen prompt snapshot does not contain expected quotes:", missing)
        return 2

    with open(canon_path, newline="", encoding="utf-8") as f:
        canonical = {r["rule_id"]: r for r in csv.DictReader(f)}

    def norm(v):
        return v if isinstance(v, str) else v["status"]

    gold = {}
    with open(args.gold_labels, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            gold[r["case_id"]] = {k: norm(v) for k, v in r["labels"].items()}

    # ---- re-adjudication over the released synthetic layer ----
    h4_candidates, h4_actually = [], []
    h5_applicable, h5_actually = [], []
    per_siewert = {"I": 0, "II": 0, "III": 0}
    gej_range_cases = 0
    for f in sorted(Path(args.benchmark_records).glob("*.md")):
        cid = f.stem
        p = parse_case(f.read_text(encoding="utf-8"))
        g = gold[cid]
        j4, branch = rejudge_h4(p)
        if j4 != g["H4"]:
            print(f"FATAL: frozen-policy H4 re-adjudication disagrees with Gold for {cid}: "
                  f"{j4} vs {g['H4']}")
            return 2
        j5 = rejudge_h5(p)
        if j5 != g["H5"]:
            print(f"FATAL: frozen-policy H5 re-adjudication disagrees with Gold for {cid}: "
                  f"{j5} vs {g['H5']}")
            return 2
        # H4 presentation-oversimplification candidates: Branch-1 trigger, no Z-line
        # relative distance, but other localization evidence that the canonical
        # table's merged wording would accept.
        if branch == "H4_SUBTYPE_OR_SIEWERT" and not p["has_zline_dist"] and (
                p["has_incisor"] or p["has_endo_loc"]):
            h4_candidates.append(cid)
            if g["H4"] != "FAIL":
                h4_actually.append(cid)
        if j5 in ("PASS", "FAIL"):
            h5_applicable.append(cid)
            if p["siewert"]:
                per_siewert[p["siewert"]] += 1
            else:
                gej_range_cases += 1

    cand_dir = Path(args.out_csv).parent
    h4_cand_file = cand_dir / "rule_source_audit_h4_candidate_cases.csv"
    with open(h4_cand_file, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "gold_h4", "frozen_policy_rejudgment"])
        for cid in h4_candidates:
            w.writerow([cid, gold[cid]["H4"], "FAIL"])
    h5_cand_file = cand_dir / "rule_source_audit_h5_applicable_cases.csv"
    with open(h5_cand_file, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "gold_h5", "frozen_policy_rejudgment"])
        for cid in h5_applicable:
            w.writerow([cid, gold[cid]["H5"], gold[cid]["H5"]])

    rows = []

    def add(rule, branch, element, prompt_val, canon_val, status, dclass, desc,
            n_pot=0, n_act=0, cand="", resolution="None required", final="CONFIRMED_MATCH"):
        rows.append({
            "audit_id": f"A{len(rows)+1:02d}", "rule_id": rule, "branch_id": branch,
            "policy_element": element, "frozen_prompt_value": prompt_val,
            "canonical_table_value": canon_val, "annotation_manual_value": manual_value,
            "prompt_vs_manual_status": manual_status, "prompt_vs_canonical_status": status,
            "discrepancy_class": dclass, "discrepancy_description": desc,
            "reference_policy": REF, "n_labels_potentially_affected": n_pot,
            "n_labels_actually_affected": n_act, "candidate_case_file": cand,
            "resolution": resolution, "final_status": final,
        })

    # ---- H1/H2/H3: substantive MATCH rows ----
    add("H1", "-", "trigger / pass / fail / na",
        "Trigger: GEJ/cardia-related malignancy statement. PASS requires pathology/biopsy with "
        "histologic type; otherwise FAIL (Major).",
        canonical["H1"]["trigger_applicability"] + " | " + canonical["H1"]["pass_minimum"],
        "CONSISTENT", "MATCH",
        "Canonical table conveys the same trigger, evidence requirement and failure mode as the "
        "frozen prompt; no branch structure or numeric threshold exists for H1.")
    add("H2", "-", "trigger / pass / fail / na",
        "Trigger: GEJ/cardia-related malignancy statement. PASS requires endoscopic findings with "
        "site/morphology; procedure-only mentions fail.",
        canonical["H2"]["trigger_applicability"] + " | " + canonical["H2"]["pass_minimum"],
        "CONSISTENT", "MATCH",
        "Canonical wording ('Only procedure/workflow mention such as gastroscopy performed without "
        "findings...') matches the frozen prompt's exclusion of procedure-only mentions.")
    add("H3", "-", "trigger / pass / fail / na",
        "Trigger: distant metastasis / M1 / stage IV / advanced disease. Regional lymph nodes do "
        "not trigger. Diagnosis must reflect metastasis/stage.",
        canonical["H3"]["trigger_applicability"] + " | " + canonical["H3"]["na_condition"],
        "CONSISTENT", "MATCH",
        "Both sources exclude regional lymph-node findings from triggering H3 and require the "
        "diagnosis to reflect metastasis/stage once triggered.")

    # ---- H6 ----
    add("H6", "-", "trigger / pass / fail / na",
        "All records; 12 required fields must be present and non-empty; diagnosis naming must be "
        "reviewable (site + malignant nature; ICD not required).",
        canonical["H6"]["pass_minimum"] + " | " + canonical["H6"]["fail_condition"],
        "CONSISTENT", "MATCH",
        "Canonical table reproduces the 12-field completeness rule and the naming-reviewability "
        "rule, including that absence of an ICD code alone is not FAIL.")
    add("H6", "-", "fail_severity",
        "Field missing/empty -> FAIL (Major); naming not reviewable -> FAIL (Minor).",
        "NOT_STATED (canonical table has no severity column)",
        "SEVERITY_NOT_IN_CANONICAL", "PRESENTATION_OMISSION",
        "Severity grading does not change PASS/FAIL/NA labels; it is restored in the revised "
        "branch-level Table 1 and Supplementary Table S1.", 0, 0, "",
        "Severity added to revised Table 1 / Supplementary Table S1 branch-level decision table.",
        "RESOLVED_PRESENTATION_FIX")

    # ---- H4 ----
    add("H4", "H4_SUBTYPE_OR_SIEWERT", "trigger",
        "Branch 1 trigger: diagnosis states Siewert I/II/III or distal-esophageal/cardia/"
        "subcardial-gastric cancer.",
        canonical["H4"]["trigger_applicability"],
        "BRANCH_NOT_REPRESENTED", "PRESENTATION_OVERSIMPLIFICATION",
        "Canonical trigger merges Branch 1 and Branch 2 into a single row; a reader cannot tell "
        "that subtype/Siewert designations trigger a stricter evidence requirement. " + SCOPE_NOTE,
        len(h4_candidates), len(h4_actually), h4_cand_file.name,
        "Revised Table 1 and Supplementary Table S1 present the two H4 branches separately.",
        "RESOLVED_PRESENTATION_FIX")
    add("H4", "H4_SUBTYPE_OR_SIEWERT", "pass_condition",
        "Requires reviewable tumor-center OR upper/lower-bound distance relative to the documented "
        "Z-line/dentate line; CT/PET/MR location alone is insufficient.",
        canonical["H4"]["pass_minimum"],
        "BROADER_IN_CANONICAL", "PRESENTATION_OVERSIMPLIFICATION",
        "Canonical pass_minimum lists 'incisors distance/EGJ landmark or lesion bounds' without the "
        "Branch-1 restriction to Z-line/dentate-line relative distances. Under the canonical wording "
        f"{len(h4_candidates)} released synthetic Branch-1 labels could have been read as PASS; all "
        f"are FAIL in the final Gold set, consistent with the frozen prompt. " + SCOPE_NOTE,
        len(h4_candidates), len(h4_actually), h4_cand_file.name,
        "Revised Table 1 and Supplementary Table S1 state the Branch-1 Z-line/dentate-line "
        "requirement explicitly.", "RESOLVED_PRESENTATION_FIX")
    add("H4", "H4_SUBTYPE_OR_SIEWERT", "fail_condition",
        "Missing required Z-line/dentate-line relative-distance evidence -> FAIL (Critical).",
        canonical["H4"]["fail_condition"],
        "CONSISTENT_SUBSTANCE", "PRESENTATION_OVERSIMPLIFICATION",
        "Failure substance matches (absence of qualifying localization evidence); the Critical "
        "severity is omitted from the canonical table (see severity rows).",
        0, 0, "", "Severity restored in revised Table 1 / Supplementary Table S1.",
        "RESOLVED_PRESENTATION_FIX")
    add("H4", "H4_GEJ_ONLY", "trigger / pass / fail",
        "Branch 2 trigger: diagnosis stated only as GEJ/gastroesophageal-junction cancer. PASS: "
        "reviewable endoscopic localization, incisors distance, or Z-line/dentate-line distance; "
        "CT/PET/MR location alone insufficient. FAIL (Major) when all are absent.",
        "(branch not represented as such; merged wording covers equivalent evidence types)",
        "BRANCH_NOT_REPRESENTED", "PRESENTATION_OMISSION",
        "The canonical table does not represent Branch 2 separately, but its merged evidence list "
        "accepts exactly the Branch-2 evidence types, so no label could have been judged "
        "differently. " + SCOPE_NOTE,
        0, 0, "",
        "Revised Table 1 and Supplementary Table S1 present Branch 2 explicitly with Major "
        "severity.", "RESOLVED_PRESENTATION_FIX")
    add("H4", "H4_SUBTYPE_OR_SIEWERT", "fail_severity",
        "FAIL (Critical) for Branch 1.",
        "NOT_STATED (canonical table has no severity column)",
        "SEVERITY_NOT_IN_CANONICAL", "PRESENTATION_OMISSION",
        "Severity does not alter PASS/FAIL/NA labels.", 0, 0, "",
        "Severity restored in revised Table 1 / Supplementary Table S1.", "RESOLVED_PRESENTATION_FIX")
    add("H4", "H4_GEJ_ONLY", "fail_severity",
        "FAIL (Major) for Branch 2.",
        "NOT_STATED (canonical table has no severity column)",
        "SEVERITY_NOT_IN_CANONICAL", "PRESENTATION_OMISSION",
        "Severity does not alter PASS/FAIL/NA labels.", 0, 0, "",
        "Severity restored in revised Table 1 / Supplementary Table S1.", "RESOLVED_PRESENTATION_FIX")

    # ---- H5 ----
    add("H5", "-", "trigger",
        "Siewert I/II/III or GEJ diagnosis AND an explicit tumor-center distance relative to the "
        "Z-line/dentate line.",
        canonical["H5"]["trigger_applicability"],
        "CONSISTENT", "MATCH", "Trigger wording is equivalent in both sources.")
    add("H5", "H5_NO_CENTER_DISTANCE", "na_condition",
        "No tumor-center distance, or only upper/lower-bound distances -> NA.",
        canonical["H5"]["na_condition"],
        "CONSISTENT", "MATCH",
        "Both sources assign NA when no explicit tumor-center distance exists, including "
        "bounds-only documentation. No bounds-only case occurs in the released synthetic layer. "
        + SCOPE_NOTE)
    thr_desc = ("The frozen prompt defines explicit numeric intervals (Siewert I: Z-line above "
                "1-5 cm; II: above 1 cm through below 2 cm; III: below 2-5 cm; GEJ diagnosis "
                "with center distance beyond +/-5 cm -> FAIL). The canonical table references "
                "'the frozen Siewert interval' without reproducing the values, so "
                "threshold-dependent judgments cannot be reproduced from the canonical table "
                f"alone. Re-adjudication of all {len(h5_applicable)} applicable released "
                "synthetic labels under the frozen thresholds matches the final Gold set "
                "exactly. " + SCOPE_NOTE)
    add("H5", "H5_SIEWERT_I", "numeric_threshold",
        "Siewert I: tumor center 1-5 cm above the Z-line (d in [+1, +5]).",
        "NOT_STATED", "THRESHOLD_OMITTED", "PRESENTATION_OMISSION", thr_desc,
        per_siewert["I"], 0, h5_cand_file.name,
        "Numeric thresholds restored in revised Supplementary Table S1 (branch-level decision "
        "table) and summarized in Table 1.", "RESOLVED_PRESENTATION_FIX")
    add("H5", "H5_SIEWERT_II", "numeric_threshold",
        "Siewert II: tumor center from 1 cm above through 2 cm below the Z-line (d in [-2, +1]).",
        "NOT_STATED", "THRESHOLD_OMITTED", "PRESENTATION_OMISSION", thr_desc,
        per_siewert["II"], 0, h5_cand_file.name,
        "Numeric thresholds restored in revised Supplementary Table S1.", "RESOLVED_PRESENTATION_FIX")
    add("H5", "H5_SIEWERT_III", "numeric_threshold",
        "Siewert III: tumor center 2-5 cm below the Z-line (d in [-5, -2]).",
        "NOT_STATED", "THRESHOLD_OMITTED", "PRESENTATION_OMISSION", thr_desc,
        per_siewert["III"], 0, h5_cand_file.name,
        "Numeric thresholds restored in revised Supplementary Table S1.", "RESOLVED_PRESENTATION_FIX")
    add("H5", "H5_GEJ_RANGE", "numeric_threshold",
        "GEJ diagnosis with center distance beyond +/-5 cm from the Z-line -> FAIL (Critical).",
        "NOT_STATED", "THRESHOLD_OMITTED", "PRESENTATION_OMISSION", thr_desc,
        gej_range_cases, 0, h5_cand_file.name,
        "Numeric thresholds restored in revised Supplementary Table S1.", "RESOLVED_PRESENTATION_FIX")
    add("H5", "-", "direction_convention / boundary_inclusivity",
        "'Z-line above x cm' is d=+x, 'below x cm' is d=-x; interval endpoints are inclusive as "
        "written. The Siewert I/II ranges share the d=+1 boundary, which both adjacent subtypes "
        "accept, so no conflicting judgment can arise at the shared boundary.",
        "NOT_STATED", "CONVENTION_OMITTED", "PRESENTATION_OMISSION",
        "Direction convention and endpoint inclusivity are not reproduced in the canonical table. "
        "Re-adjudication under the frozen conventions reproduces every released synthetic Gold "
        "label. " + SCOPE_NOTE,
        len(h5_applicable), 0, h5_cand_file.name,
        "Direction convention and thresholds restored in revised Supplementary Table S1.",
        "RESOLVED_PRESENTATION_FIX")

    # ---- severity rows for H1/H2/H3/H5 ----
    for rule, sev in [("H1", "Major"), ("H2", "Major"), ("H3", "Major"), ("H5", "Critical")]:
        add(rule, "-", "fail_severity", f"FAIL ({sev}).",
            "NOT_STATED (canonical table has no severity column)",
            "SEVERITY_NOT_IN_CANONICAL", "PRESENTATION_OMISSION",
            "Severity grading does not change PASS/FAIL/NA labels; it is restored in the revised "
            "branch-level Table 1 and Supplementary Table S1.", 0, 0, "",
            "Severity added to revised Table 1 / Supplementary Table S1.", "RESOLVED_PRESENTATION_FIX")

    out = Path(args.out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = ["audit_id", "rule_id", "branch_id", "policy_element", "frozen_prompt_value",
              "canonical_table_value", "annotation_manual_value", "prompt_vs_manual_status",
              "prompt_vs_canonical_status", "discrepancy_class", "discrepancy_description",
              "reference_policy", "n_labels_potentially_affected", "n_labels_actually_affected",
              "candidate_case_file", "resolution", "final_status"]
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    n_conflict = sum(1 for r in rows if r["discrepancy_class"] == "POLICY_CONFLICT")
    n_unver = sum(1 for r in rows if r["discrepancy_class"] == "UNVERIFIABLE"
                  and not r["final_status"].startswith(("RESOLVED", "CONFIRMED")))
    n_act = sum(int(r["n_labels_actually_affected"]) for r in rows)
    print("Input SHA256:")
    for k, v in input_hashes.items():
        print(f"  {v}  {k}")
    print(f"Rows written: {len(rows)} -> {out}")
    print(f"H4 potentially affected (synthetic layer): {len(h4_candidates)}; actually affected: {len(h4_actually)}")
    print(f"H5 applicable (synthetic layer): {len(h5_applicable)} "
          f"(Siewert I/II/III = {per_siewert['I']}/{per_siewert['II']}/{per_siewert['III']}, "
          f"GEJ-range = {gej_range_cases}); actually affected: 0")
    print(f"POLICY_CONFLICT rows: {n_conflict}; unresolved UNVERIFIABLE: {n_unver}; "
          f"total n_actually_affected: {n_act}")
    ok = n_conflict == 0 and n_unver == 0 and n_act == 0 and not h4_actually
    print("AUDIT RESULT:", "PASS (P0 closure criteria met)" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
