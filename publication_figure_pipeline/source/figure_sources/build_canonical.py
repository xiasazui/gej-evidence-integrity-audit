#!/usr/bin/env python3
"""Build canonical per-figure JSON data files.

Every number a figure will render is stored here with full provenance.
Figure scripts (Node) read ONLY these JSONs. Values are never recomputed
except where explicitly marked (e.g. sign-flip orientation of a stored
bootstrap delta, exactly as the previously submitted figure did).
"""
from __future__ import annotations
import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DUMP = ROOT / "source/data_json_or_csv/xlsx_dump"
OUT = ROOT / "source/data_json_or_csv"
AGG = OUT / "public_aggregate/gold_eval_models_summary.json"
XLSX = "Supplementary_Data.xlsx"

def colletter(i):  # 1-based
    s = ""
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s

class Sheet:
    def __init__(self, name):
        self.name = name
        self.rows = list(csv.reader(open(DUMP / f"{name}.csv")))
    def find_row(self, col0_value, start=0):
        for i, r in enumerate(self.rows):
            if i >= start and r and r[0] == col0_value:
                return i
        raise KeyError(col0_value)
    def header_row(self, first_cell):
        return self.find_row(first_cell)
    def ref(self, r, c):
        return f"{self.name}!{colletter(c+1)}{r+1}"

s1, s2, s3, s4, s5, s7, s8 = (Sheet(n) for n in (
    "S1_Rules_Gold", "S2_Model_Summary", "S3_Rule_NA", "S4_Evidence",
    "S5_Bootstrap", "S7_Human_Taxonomy", "S8_Transitions_Real"))

agg = json.loads(AGG.read_text())
AGG_SRC = "public_aggregate/gold_eval_models_summary.json"

# ---- canonical model order (workbook S2 rank column; == unrounded macro-F1 desc) ----
hA = s2.header_row("rank")
order_rows = s2.rows[hA + 1: hA + 12]
MODEL_ORDER_IDS = [r[1] for r in order_rows]
DISPLAY = {
    "gemini-3-pro-preview-thinking": "Gemini", "kimi-k2-thinking": "Kimi",
    "qwen3-235b-a22b-thinking-2507": "Qwen3-235B", "deepseek-v3.2-thinking": "DeepSeek",
    "gpt-oss-120b": "GPT-OSS-120B", "gpt-oss-20b": "GPT-OSS-20B",
    "qwen3-next-80b-a3b-thinking": "Qwen3-Next", "qwen3-30b-a3b-thinking-2507": "Qwen3-30B",
    "MiniMax-M2.1": "MiniMax", "gpt-5.2": "GPT-5.2", "deterministic-baseline": "Regex",
}
MODELS = [DISPLAY[m] for m in MODEL_ORDER_IDS]

VROWS = []  # verification rows

def v(figure, panel, element, metric, model_or_rule, source_file, sheet, loc,
      original, precision, notes=""):
    VROWS.append({
        "figure": figure, "panel": panel, "visual_element": element, "metric": metric,
        "model_or_rule": model_or_rule, "source_file": source_file,
        "source_sheet_or_table": sheet, "source_cell_or_location": loc,
        "original_value": str(original), "rendered_value": "", "decimal_precision": precision,
        "verification_status": "source_verified_pending_render", "notes": notes,
    })

def cell(sheetname):  # small helper closure factory
    sh = {"S1": s1, "S2": s2, "S3": s3, "S4": s4, "S5": s5, "S7": s7, "S8": s8}[sheetname]
    return sh

def row_by(sheet, col0, value, start=0):
    for i, r in enumerate(sheet.rows):
        if i >= start and len(r) > col0 and r[col0] == value:
            return i
    raise KeyError(f"{sheet.name} {value}")

# =============== Figure 1 ===============
f1 = {"panels": {}}
# panel a counts
r_ro = row_by(s1_dummy := s1, 0, "dummy") if False else None
# S6 handled separately (sheet exists in dump; load here)
s6 = Sheet("S6_Source_Layer")
def s6_row(cls):
    h = s6.header_row("source_class")
    for i in range(h + 1, len(s6.rows)):
        r = s6.rows[i]
        if r and r[0] == cls:
            return i
    raise KeyError(cls)
i_ro, i_so, i_rd, i_sd = s6_row("real_original"), s6_row("synthetic_original"), s6_row("real_derived"), s6_row("synthetic_derived")
n_real = int(s6.rows[i_ro][1]); n_synth = int(s6.rows[i_so][1])
n_real_d = int(s6.rows[i_rd][1]); n_synth_d = int(s6.rows[i_sd][1])
# S6 section C: all_700 row -> pairs/applicable/na
hC = None
for i, r in enumerate(s6.rows):
    if r and r[0] == "layer_id":
        hC = i; break
i_all = next(i for i in range(hC + 1, len(s6.rows)) if s6.rows[i][0] == "all_700")
n_pairs = int(s6.rows[i_all][4]); n_app = int(s6.rows[i_all][5]); n_na = int(s6.rows[i_all][8])
n_systems = len(MODELS)
f1["panels"]["a"] = {
    "title": "Benchmark construction",
    "main_flow": [
        {"node": "100 seeds", "sub": "20 real + 80 synthetic",
         "prov": {"20": s6.ref(i_ro, 1), "80": s6.ref(i_so, 1)}},
        {"node": "600 variants", "sub": "one H1\u2013H6 variant per seed",
         "prov": {"600_total": f"derived: 120 ({s6.ref(i_rd,1)}) + 480 ({s6.ref(i_sd,1)}) = 600"}},
        {"node": "700 instances", "sub": "100 originals + 600 variants",
         "prov": {"700": "100 + 600"}},
    ],
    "aux_flow": [
        {"node": "Frozen audit policy", "sub": "H1\u2013H6 PASS / FAIL / NA"},
        {"node": "Frozen evaluation", "sub": "11 systems \u00b7 4,200 pairs/model",
         "prov": {"11": "S2_Model_Summary section A rows (11 systems)",
                  "4200": s6.ref(i_all, 4)}},
    ],
    "footnote": "Gold-applicable pairs: 3,328/model; Gold-NA pairs: 872/model",
    "footnote_prov": {"3328": s6.ref(i_all, 5), "872": s6.ref(i_all, 8)},
}
# panel b: transitions + off-target
hB = s8.header_row("target_rule")  # section A header (first occurrence)
iH2 = next(i for i in range(hB + 1, len(s8.rows)) if s8.rows[i][0] == "H2")
iH4 = next(i for i in range(hB + 1, len(s8.rows)) if s8.rows[i][0] == "H4")
off = {"H2": (int(s8.rows[iH2][7]), int(s8.rows[iH2][1])),
       "H4": (int(s8.rows[iH4][7]), int(s8.rows[iH4][1]))}
# section B header is the second "target_rule"
hBB = s8.header_row("target_rule")
# find section B (before,after columns): locate row where r[2]=="before"
hSB = next(i for i, r in enumerate(s8.rows) if len(r) > 2 and r[2] == "before")
def trans(t, a, b4, af):
    for i in range(hSB + 1, len(s8.rows)):
        r = s8.rows[i]
        if r and r[0] == t and r[1] == a and r[2] == b4 and r[3] == af:
            return int(r[4]), s8.ref(i, 4)
    raise KeyError((t, a, b4, af))
e1, e1r = trans("H2", "H4", "PASS", "FAIL")
e2, e2r = trans("H2", "H5", "PASS", "NA")
e3, e3r = trans("H4", "H5", "PASS", "NA")
f1["panels"]["b"] = {
    "title": "Operator-induced coupling",
    "off_target_line": "Off-target changes: H2 98/100; H4 85/100",
    "off_target": {"H2": {"n": off["H2"][0], "denom": off["H2"][1], "prov": s8.ref(iH2, 7)},
                   "H4": {"n": off["H4"][0], "denom": off["H4"][1], "prov": s8.ref(iH4, 7)}},
    "nodes": ["H2", "H4", "H5"],
    "edges": [
        {"from": "H2", "to": "H4", "n": e1, "kind": "PASS\u2192FAIL", "prov": e1r},
        {"from": "H2", "to": "H5", "n": e2, "kind": "PASS\u2192NA", "prov": e2r},
        {"from": "H4", "to": "H5", "n": e3, "kind": "PASS\u2192NA", "prov": e3r},
    ],
}
for el, val, loc in [("node count", "100/600/700/20/80", "S6_Source_Layer!B6:B9"),
                     ("systems", n_systems, "S2_Model_Summary section A"),
                     ("pairs per model", n_pairs, s6.ref(i_all, 4)),
                     ("Gold-applicable", n_app, s6.ref(i_all, 5)),
                     ("Gold-NA", n_na, s6.ref(i_all, 8))]:
    v("Figure 1", "a", el, "count", "-", XLSX, "S6_Source_Layer/S2", loc, val, "integer")
for e in f1["panels"]["b"]["edges"]:
    v("Figure 1", "b", f"edge {e['from']}\u2192{e['to']}", e["kind"], f"{e['from']}\u2192{e['to']}",
      XLSX, "S8_Transitions_Real", e["prov"], e["n"], "integer")
for k in ("H2", "H4"):
    o = f1["panels"]["b"]["off_target"][k]
    v("Figure 1", "b", f"off-target {k}", "variants_with_off_target_change/n_variants", k,
      XLSX, "S8_Transitions_Real", o["prov"], f"{o['n']}/{o['denom']}", "integer",
      "variants_with_off_target_change column (not off_target_changes); matches legend wording")

# =============== Figure 2 ===============
def s2A(model_id, colname):
    h = s2.header_row("rank")
    cols = {c: j for j, c in enumerate(s2.rows[h])}
    for i in range(h + 1, h + 12):
        if s2.rows[i][1] == model_id:
            return s2.rows[i][cols[colname]], s2.ref(i, cols[colname])
    raise KeyError(model_id + colname)

def s2C(model_id, colname):
    h = next(i for i, r in enumerate(s2.rows) if r and r[0] == "model" and "evidence_coverage" in r)
    cols = {c: j for j, c in enumerate(s2.rows[h])}
    for i in range(h + 1, h + 12):
        if s2.rows[i][0] == model_id:
            return s2.rows[i][cols[colname]], s2.ref(i, cols[colname])
    raise KeyError(model_id + colname)

f2 = {"panels": {"a": {"title": "FAIL-class F1 among Gold-applicable pairs", "series": []},
                 "b": {"title": "Evidence endpoints on predicted FAIL outputs", "series": []},
                 "c": {"title": "Targeted human review", "groups": []}}}
for mid in MODEL_ORDER_IDS:
    macro, mr = s2A(mid, "macro_f1"); micro, mi = s2A(mid, "micro_f1")
    f2["panels"]["a"]["series"].append({"model": DISPLAY[mid], "model_id": mid,
        "macro_f1": float(macro), "micro_f1": float(micro), "prov": {"macro": mr, "micro": mi}})
    v("Figure 2", "a", "point", "FAIL-class macro-F1", DISPLAY[mid], XLSX, "S2_Model_Summary", mr, macro, "3dp")
    v("Figure 2", "a", "point", "FAIL-class micro-F1", DISPLAY[mid], XLSX, "S2_Model_Summary", mi, micro, "3dp")
for mid in MODEL_ORDER_IDS:
    cov, cr = s2C(mid, "evidence_coverage"); cir, ci = s2C(mid, "conditional_item_recoverability")
    asr, ar = s2C(mid, "all_snippet_recoverability")
    f2["panels"]["b"]["series"].append({"model": DISPLAY[mid], "model_id": mid,
        "evidence_coverage": float(cov), "conditional_item_recoverability": float(cir),
        "all_snippet_recoverability": float(asr),
        "prov": {"coverage": cr, "conditional": ci, "all_snippet": ar}})
    for mname, val, loc in (("evidence coverage", cov, cr), ("conditional item recoverability", cir, ci),
                            ("all-snippet recoverability", asr, ar)):
        v("Figure 2", "b", "point", mname, DISPLAY[mid], XLSX, "S2_Model_Summary", loc, f"{float(val):.6f}", "6dp source, 3dp axis")
# panel c from S7 section C overall row
hC7 = next(i for i, r in enumerate(s7.rows) if r and "lexical_yes" in r)
cols7 = {c: j for j, c in enumerate(s7.rows[hC7])}
i_ov = next(i for i in range(hC7 + 1, len(s7.rows)) if s7.rows[i][0] == "overall")
ov = s7.rows[i_ov]
def g7(name): return int(ov[cols7[name]]), s7.ref(i_ov, cols7[name])
ly, lr = g7("lexical_yes"); lp, lpr = g7("lexical_partial"); ln, lnr = g7("lexical_no")
sy, sr = g7("semantic_sufficient"); sp, spr = g7("semantic_partial"); sn, snr = g7("semantic_not_sufficient")
n96, n96r = g7("n_reviewed")
f2["panels"]["c"]["groups"] = [
    {"group": "Lexical rating", "segments": [
        {"label": "Yes / sufficient", "n": ly, "prov": lr},
        {"label": "Partial", "n": lp, "prov": lpr},
        {"label": "No / insufficient", "n": ln, "prov": lnr}]},
    {"group": "Semantic support", "segments": [
        {"label": "Yes / sufficient", "n": sy, "prov": sr},
        {"label": "Partial", "n": sp, "prov": spr},
        {"label": "No / insufficient", "n": sn, "prov": snr}]},
]
f2["panels"]["c"]["n_total"] = {"value": n96, "prov": n96r}
for grp in f2["panels"]["c"]["groups"]:
    for seg in grp["segments"]:
        v("Figure 2", "c", f"stacked segment ({grp['group']})", seg["label"], "targeted review",
          XLSX, "S7_Human_Taxonomy", seg["prov"], seg["n"], "integer", f"displayed as n/{n96}")
v("Figure 2", "c", "denominator", "n reviewed", "targeted review", XLSX, "S7_Human_Taxonomy", n96r, n96, "integer")

# =============== Figure 3 ===============
f3 = {"panels": {"a": {"title": "Per-rule FAIL-class F1", "matrix": []},
                 "b": {"title": "Gold-applicable discrimination", "points": []},
                 "c": {"title": "Applicability classification", "points": [], "expanded_y": True}}}
rules = ["H1", "H2", "H3", "H4", "H5", "H6"]
for mid in MODEL_ORDER_IDS:
    row = {"model": DISPLAY[mid], "model_id": mid, "f1": {}, "prov": {}}
    for rl in rules:
        val, ref = s2A(mid, f"{rl}_f1")
        row["f1"][rl] = float(val); row["prov"][rl] = ref
        v("Figure 3", "a", "heatmap cell", "FAIL-class F1", f"{DISPLAY[mid]} \u00d7 {rl}",
          XLSX, "S2_Model_Summary", ref, val, "3dp source and display")
    f3["panels"]["a"]["matrix"].append(row)
# macro sens/spec from aggregate JSON (model order there is alphabetical)
agg_idx = {m: i for i, m in enumerate(agg["models"])}
for mid in MODEL_ORDER_IDS:
    j = agg_idx[mid]
    sens = agg["macro"]["sensitivity"][j]; spec = agg["macro"]["specificity"][j]
    f3["panels"]["b"]["points"].append({"model": DISPLAY[mid], "model_id": mid,
        "x_specificity": float(spec), "y_sensitivity": float(sens),
        "prov": f"macro.specificity[{j}] / macro.sensitivity[{j}]"})
    v("Figure 3", "b", "point x", "FAIL-class macro-specificity", DISPLAY[mid], AGG_SRC,
      "gold_eval_models_summary.json", f"macro.specificity[{j}]", f"{float(spec):.6f}", "6dp")
    v("Figure 3", "b", "point y", "FAIL-class macro-sensitivity", DISPLAY[mid], AGG_SRC,
      "gold_eval_models_summary.json", f"macro.sensitivity[{j}]", f"{float(sens):.6f}", "6dp")
# applicability from S2 section B
hB2 = next(i for i, r in enumerate(s2.rows) if r and r[0] == "model" and "na_specificity" in r)
colsB = {c: j for j, c in enumerate(s2.rows[hB2])}
for mid in MODEL_ORDER_IDS:
    i = next(i for i in range(hB2 + 1, hB2 + 12) if s2.rows[i][1] == mid)
    x = s2.rows[i][colsB["na_specificity"]]; y = s2.rows[i][colsB["applicability_sensitivity"]]
    f3["panels"]["c"]["points"].append({"model": DISPLAY[mid], "model_id": mid,
        "x_na_specificity": float(x), "y_applicability_sensitivity": float(y),
        "prov": {"x": s2.ref(i, colsB["na_specificity"]), "y": s2.ref(i, colsB["applicability_sensitivity"])}})
    v("Figure 3", "c", "point x", "Gold-NA specificity", DISPLAY[mid], XLSX, "S2_Model_Summary",
      s2.ref(i, colsB["na_specificity"]), x, "6dp")
    v("Figure 3", "c", "point y", "Gold-applicable sensitivity", DISPLAY[mid], XLSX, "S2_Model_Summary",
      s2.ref(i, colsB["applicability_sensitivity"]), y, "6dp",
      "expanded y-axis retained with in-panel annotation (per spec)")

# =============== Figure S1 ===============
fS1 = {"panels": {"a": {"title": "Case-level audit burden", "bars": []},
                  "b": {"title": "Gold label composition by rule", "rows": []}}}
hC1 = next(i for i, r in enumerate(s1.rows) if r and r[0] == "Gold FAIL rules per case")
for i in range(hC1 + 1, hC1 + 6):
    k, n = s1.rows[i][0], int(s1.rows[i][1])
    fS1["panels"]["a"]["bars"].append({"fail_rules": int(k), "cases": n, "prov": s1.ref(i, 1)})
    v("Figure S1", "a", "bar", "cases", f"{k} Gold FAIL rules", XLSX, "S1_Rules_Gold", s1.ref(i, 1), n, "integer")
hB1 = next(i for i, r in enumerate(s1.rows) if r and r[0] == "rule" and "PASS" in r)
for i in range(hB1 + 1, hB1 + 7):
    r = s1.rows[i]
    row = {"rule": r[0], "PASS": int(r[1]), "FAIL": int(r[2]), "NA": int(r[3]),
           "prov": {"PASS": s1.ref(i, 1), "FAIL": s1.ref(i, 2), "NA": s1.ref(i, 3)}}
    fS1["panels"]["b"]["rows"].append(row)
    for j, lab in enumerate(("PASS", "FAIL", "NA")):
        v("Figure S1", "b", "stacked segment", lab, r[0], XLSX, "S1_Rules_Gold", s1.ref(i, j + 1), row[lab], "integer")

# =============== Figure S2 ===============
fS2 = {"panels": {"a": {"title": "Model-level discrimination", "points": []},
                  "b": {"title": "FAIL sensitivity by model and rule", "matrix": []},
                  "c": {"title": "FAIL specificity by model and rule", "matrix": []}}}
for mid in MODEL_ORDER_IDS:
    j = agg_idx[mid]
    fS2["panels"]["a"]["points"].append({"model": DISPLAY[mid], "model_id": mid,
        "x_specificity": float(agg["macro"]["specificity"][j]),
        "y_sensitivity": float(agg["macro"]["sensitivity"][j]),
        "prov": f"macro.specificity[{j}] / macro.sensitivity[{j}]"})
    v("Figure S2", "a", "point", "macro sens/spec", DISPLAY[mid], AGG_SRC, "gold_eval_models_summary.json",
      f"macro.*[{j}]", f"{float(agg['macro']['sensitivity'][j]):.6f}/{float(agg['macro']['specificity'][j]):.6f}", "6dp")
    rowb = {"model": DISPLAY[mid], "model_id": mid, "values": {}, "prov": {}}
    rowc = {"model": DISPLAY[mid], "model_id": mid, "values": {}, "prov": {}}
    for k, rl in enumerate(rules):
        sv = float(agg["matrix"]["sensitivity"][j][k]); pv = float(agg["matrix"]["specificity"][j][k])
        rowb["values"][rl] = sv; rowb["prov"][rl] = f"matrix.sensitivity[{j}][{k}]"
        rowc["values"][rl] = pv; rowc["prov"][rl] = f"matrix.specificity[{j}][{k}]"
        v("Figure S2", "b", "heatmap cell", "FAIL sensitivity", f"{DISPLAY[mid]} \u00d7 {rl}", AGG_SRC,
          "gold_eval_models_summary.json", f"matrix.sensitivity[{j}][{k}]", f"{sv:.10f}", "2dp display")
        v("Figure S2", "c", "heatmap cell", "FAIL specificity", f"{DISPLAY[mid]} \u00d7 {rl}", AGG_SRC,
          "gold_eval_models_summary.json", f"matrix.specificity[{j}][{k}]", f"{pv:.10f}", "2dp display")
    fS2["panels"]["b"]["matrix"].append(rowb)
    fS2["panels"]["c"]["matrix"].append(rowc)

# =============== Figure S3 ===============
fS3 = {"panels": {"a": {"title": "Predicted NA rate on Gold-applicable pairs", "matrix": []},
                  "b": {"title": "Applicability discrimination", "points": []},
                  "c": {"title": "Predicted-NA policy sensitivity", "series": []}}}
hB3 = next(i for i, r in enumerate(s3.rows) if r and r[0] == "model" and "pred_na_rate_on_gold_applicable" in r)
colB3 = {c: j for j, c in enumerate(s3.rows[hB3])}
na_max = 0.0
for mid in MODEL_ORDER_IDS:
    row = {"model": DISPLAY[mid], "model_id": mid, "values": {}, "prov": {}}
    for rl in rules:
        i = next(i for i in range(hB3 + 1, len(s3.rows))
                 if s3.rows[i][0] == mid and s3.rows[i][1] == rl)
        val = float(s3.rows[i][colB3["pred_na_rate_on_gold_applicable"]])
        na_max = max(na_max, val)
        row["values"][rl] = val
        row["prov"][rl] = s3.ref(i, colB3["pred_na_rate_on_gold_applicable"])
        v("Figure S3", "a", "heatmap cell", "predicted-NA rate (Gold-applicable)", f"{DISPLAY[mid]} \u00d7 {rl}",
          XLSX, "S3_Rule_NA", s3.ref(i, colB3["pred_na_rate_on_gold_applicable"]), f"{val:.3f}", "3dp display (source precision; original figure showed 2dp)")
    fS3["panels"]["a"]["matrix"].append(row)
fS3["panels"]["a"]["colorbar_max"] = na_max
v("Figure S3", "a", "colorbar max", "max predicted-NA rate", "Regex \u00d7 H3", XLSX, "S3_Rule_NA",
  "section B max", f"{na_max:.3f}", "3dp", "colorbar spans 0 to true data maximum")
fS3["panels"]["b"]["points"] = f3["panels"]["c"]["points"]  # same source values
for p in f3["panels"]["c"]["points"]:
    v("Figure S3", "b", "point", "Gold-NA specificity / Gold-applicable sensitivity", p["model"],
      XLSX, "S2_Model_Summary", p["prov"]["x"] + ";" + p["prov"]["y"],
      f"{p['x_na_specificity']:.6f}/{p['y_applicability_sensitivity']:.6f}", "6dp",
      "same data as Figure 3c; expanded axis annotated")
hA3 = next(i for i, r in enumerate(s3.rows) if r and r[0] == "model" and "pred_na_policy" in r)
colA3 = {c: j for j, c in enumerate(s3.rows[hA3])}
policies = ["as_pass", "exclude", "as_fail"]
for mid in MODEL_ORDER_IDS:
    ser = {"model": DISPLAY[mid], "model_id": mid, "values": {}, "prov": {}}
    for pol in policies:
        i = next(i for i in range(hA3 + 1, len(s3.rows))
                 if s3.rows[i][0] == mid and s3.rows[i][1] == pol)
        val = float(s3.rows[i][colA3["macro_f1"]])
        ser["values"][pol] = val; ser["prov"][pol] = s3.ref(i, colA3["macro_f1"])
        v("Figure S3", "c", "line point", f"macro-F1 (NA {pol})", DISPLAY[mid], XLSX, "S3_Rule_NA",
          s3.ref(i, colA3["macro_f1"]), f"{val:.3f}", "3dp")
    fS3["panels"]["c"]["series"].append(ser)

# =============== Figure S4 ===============
fS4 = {"panels": {"a": {"title": "Seed-cluster uncertainty", "rows": []},
                  "b": {"title": "Evidence-traceability endpoints", "series": f2["panels"]["b"]["series"]},
                  "c": {"title": "Recoverability by returned-snippet count", "lines": []}}}
hS5 = s5.header_row("bootstrap_scope")
cS5 = {c: j for j, c in enumerate(s5.rows[hS5])}
forest_specs = [
    ("all_100_seeds", "gemini-3-pro-preview-thinking", "kimi-k2-thinking", False, "all 100: Gemini \u2212 Kimi"),
    ("all_100_seeds", "gemini-3-pro-preview-thinking", "qwen3-235b-a22b-thinking-2507", False, "all 100: Gemini \u2212 Qwen3-235B"),
    ("all_100_seeds", "deterministic-baseline", "gemini-3-pro-preview-thinking", True, "all 100: Gemini \u2212 Regex"),
    ("real_20_seeds", "gemini-3-pro-preview-thinking", "kimi-k2-thinking", False, "real 20: Gemini \u2212 Kimi"),
    ("real_20_seeds", "gemini-3-pro-preview-thinking", "qwen3-235b-a22b-thinking-2507", False, "real 20: Gemini \u2212 Qwen3-235B"),
    ("real_20_seeds", "deterministic-baseline", "gemini-3-pro-preview-thinking", True, "real 20: Gemini \u2212 Regex"),
    ("synthetic_80_seeds", "gemini-3-pro-preview-thinking", "kimi-k2-thinking", False, "synthetic 80: Gemini \u2212 Kimi"),
    ("synthetic_80_seeds", "gemini-3-pro-preview-thinking", "qwen3-235b-a22b-thinking-2507", False, "synthetic 80: Gemini \u2212 Qwen3-235B"),
    ("synthetic_80_seeds", "deterministic-baseline", "gemini-3-pro-preview-thinking", True, "synthetic 80: Gemini \u2212 Regex"),
]
for scope, ma, mb, flip, label in forest_specs:
    i = next(i for i in range(hS5 + 1, len(s5.rows))
             if s5.rows[i][cS5["bootstrap_scope"]] == scope
             and s5.rows[i][cS5["model_a"]] == ma and s5.rows[i][cS5["model_b"]] == mb)
    r = s5.rows[i]
    d0 = float(r[cS5["macro_f1_delta_a_minus_b"]]); lo = float(r[cS5["macro_f1_delta_ci95_low"]]); hi = float(r[cS5["macro_f1_delta_ci95_high"]])
    if flip:
        delta, lo2, hi2 = -d0, -hi, -lo
        note = f"stored as {ma} \u2212 {mb} = {d0:.5f} [{lo:.5f}, {hi:.5f}]; sign-flipped for display orientation exactly as the previously submitted figure"
    else:
        delta, lo2, hi2 = d0, lo, hi
        note = ""
    fS4["panels"]["a"]["rows"].append({"label": label, "delta": delta, "ci_lo": lo2, "ci_hi": hi2,
        "prov": {k: s5.ref(i, cS5[k]) for k in ("macro_f1_delta_a_minus_b", "macro_f1_delta_ci95_low", "macro_f1_delta_ci95_high")}})
    v("Figure S4", "a", "forest point+CI", "macro-F1 difference", label, XLSX, "S5_Bootstrap",
      s5.ref(i, cS5["macro_f1_delta_a_minus_b"]), f"{delta:.5f} [{lo2:.5f}, {hi2:.5f}]", "5dp", note)
for srow in f2["panels"]["b"]["series"]:
    for mname, key in (("evidence coverage", "evidence_coverage"),
                       ("conditional item recoverability", "conditional_item_recoverability"),
                       ("all-snippet recoverability", "all_snippet_recoverability")):
        v("Figure S4", "b", "point", mname, srow["model"], XLSX, "S2_Model_Summary",
          srow["prov"][{"evidence_coverage": "coverage", "conditional_item_recoverability": "conditional",
                        "all_snippet_recoverability": "all_snippet"}[key]],
          f"{srow[key]:.6f}", "6dp", "identical data and encoding as Figure 2b")
# S4c from S4 section C
hC4 = next(i for i, r in enumerate(s4.rows) if r and r[0] == "model" and "snippet_count" in r)
cC4 = {c: j for j, c in enumerate(s4.rows[hC4])}
for mid in MODEL_ORDER_IDS:
    disp = DISPLAY[mid]
    line = {"model": disp, "model_id": mid, "points": {"0": {}, "1": {}, "2": {}, "3+": {}}, "prov": {}}
    for sc in ("0", "1", "2", "3+"):
        i = next(i for i in range(hC4 + 1, len(s4.rows))
                 if s4.rows[i][cC4["model_identifier"]] == mid and s4.rows[i][cC4["snippet_count"]] == sc)
        r = s4.rows[i]
        n_out = int(r[cC4["predicted_fail_outputs"]])
        def val(col):
            t = r[cC4[col]]
            return None if t == "" else float(t)
        pt = {"first_snippet": val("first_snippet_recoverability"),
              "all_snippets": val("all_snippet_recoverability"),
              "mean_proportion": val("mean_recoverable_proportion"),
              "n_outputs": n_out}
        line["points"][sc] = pt
        line["prov"][sc] = s4.ref(i, cC4["first_snippet_recoverability"])
        for mname, key in (("first-snippet recoverability", "first_snippet"),
                           ("all-snippet recoverability", "all_snippets"),
                           ("mean recoverable proportion", "mean_proportion")):
            vv = pt[key]
            note = "UNDEFINED (empty in source) \u2014 rendered as gap, never 0" if vv is None else ""
            v("Figure S4", "c", f"line point x={sc}", mname, disp, XLSX, "S4_Evidence",
              s4.ref(i, cC4[{"first_snippet": "first_snippet_recoverability", "all_snippets": "all_snippet_recoverability",
                             "mean_proportion": "mean_recoverable_proportion"}[key]]),
              "undefined" if vv is None else f"{vv:.6f}", "6dp", note)
    fS4["panels"]["c"]["lines"].append(line)
# aggregate mean-across-systems lines (same construction as the previously submitted
# figure: unweighted mean over systems with a defined value at that snippet count;
# if no system is defined, the point is omitted entirely -- never plotted as 0)
means = {"points": {}, "definition": ("unweighted mean across systems with a defined value at that "
                                      "snippet count; snippet groups where a metric is undefined for "
                                      "every system are omitted (gap), matching the frozen analysis code")}
for sc in ("0", "1", "2", "3+"):
    mp = {}
    for key in ("first_snippet", "all_snippets", "mean_proportion"):
        vals = [l["points"][sc][key] for l in fS4["panels"]["c"]["lines"] if l["points"][sc][key] is not None]
        mp[key] = (sum(vals) / len(vals)) if vals else None
        mp[key + "_n_systems"] = len(vals)
    means["points"][sc] = mp
fS4["panels"]["c"]["aggregate_mean"] = means
for sc in ("0", "1", "2", "3+"):
    for key, mname in (("first_snippet", "first-snippet recoverability"),
                       ("all_snippets", "all-snippet recoverability"),
                       ("mean_proportion", "mean recoverable proportion")):
        mv = means["points"][sc][key]
        v("Figure S4", "c", f"mean line point x={sc}", mname, "mean across systems", XLSX, "S4_Evidence",
          f"section C, {means['points'][sc][key + '_n_systems']} systems with defined values",
          "undefined (omitted)" if mv is None else f"{mv:.6f}", "6dp",
          "derived exactly as the frozen figure code: unweighted mean over defined values; gaps never plotted as 0")

# =============== Figure S5 ===============
fS5 = {"panels": {"a": {"title": "Targeted semantic review", "bars": []},
                  "b": {"title": "Primary error mechanism and actionability", "groups": []},
                  "c": {"title": "Reviewer-facing audit workflow", "steps": [
                      {"n": 1, "title": "Read the record", "sub": "Apply frozen H1\u2013H6 rules"},
                      {"n": 2, "title": "Inspect predicted FAIL", "sub": "Check rule branch and applicability"},
                      {"n": 3, "title": "Verify evidence", "sub": "Confirm verifiable record support"},
                      {"n": 4, "title": "Resolve action", "sub": "Accept, correct, or escalate"}],
                      "note": "Evidence traceability supports correction; it does not replace clinical review."}}}
rate_l = float(ov[cols7["lexical_recoverability_rate"]])
rate_s = float(ov[cols7["semantic_sufficiency_rate"]])
rate_r = float(ov[cols7["recoverable_but_not_sufficient_rate"]])
n_rns = round(rate_r * n96)  # 0.010*96 -> 1; cross-checked against by-model rows (Gemini=1, others=0)
fS5["panels"]["a"]["bars"] = [
    {"label": "Lexically recoverable", "rate": rate_l, "n": ly, "prov": s7.ref(i_ov, cols7["lexical_recoverability_rate"])},
    {"label": "Semantically sufficient", "rate": rate_s, "n": sy, "prov": s7.ref(i_ov, cols7["semantic_sufficiency_rate"])},
    {"label": "Recoverable but insufficient", "rate": rate_r, "n": n_rns, "prov": s7.ref(i_ov, cols7["recoverable_but_not_sufficient_rate"])},
]
fS5["panels"]["a"]["n_total"] = n96
for b in fS5["panels"]["a"]["bars"]:
    v("Figure S5", "a", "bar", "proportion of 96 reviewed citations", b["label"], XLSX, "S7_Human_Taxonomy",
      b["prov"], f"{b['rate']:.3f} ({b['n']}/{n96})", "3dp rate + integer count")
hA7 = next(i for i, r in enumerate(s7.rows) if r and r[0] == "Primary error mechanism")
mech = []
for i in range(hA7 + 1, hA7 + 6):
    mech.append({"label": s7.rows[i][0], "n": int(s7.rows[i][1]), "prov": s7.ref(i, 1)})
hB7 = next(i for i, r in enumerate(s7.rows) if r and r[0] == "Actionability category")
act = []
for i in range(hB7 + 1, hB7 + 4):
    act.append({"label": s7.rows[i][0], "n": int(s7.rows[i][1]), "prov": s7.ref(i, 1)})
fS5["panels"]["b"]["groups"] = [
    {"group": "Primary error mechanism", "n_total": 214, "bars": mech},
    {"group": "Actionability", "n_total": 214, "bars": act},
]
for g in fS5["panels"]["b"]["groups"]:
    for b in g["bars"]:
        v("Figure S5", "b", f"bar ({g['group']})", "count", b["label"], XLSX, "S7_Human_Taxonomy",
          b["prov"], b["n"], "integer", "n = 214 targeted sample")
v("Figure S5", "b", "denominator", "targeted sample size", "-", XLSX, "S7_Human_Taxonomy",
  "sections A/B", 214, "integer", "178+18+11+5+2 = 214")

# =============== write everything ===============
meta = {
    "canonical_model_order": [{"rank": i + 1, "model_id": mid, "display": DISPLAY[mid]}
                              for i, mid in enumerate(MODEL_ORDER_IDS)],
    "order_note": ("Order = Supplementary_Data.xlsx S2_Model_Summary rank column (FAIL-class macro-F1, "
                   "descending; Regex always last). Cross-checked against unrounded macro_f1 in "
                   "gold_eval_models_summary.json: identical ordering (kimi 0.9829064509 > qwen3-235b 0.9826282817)."),
    "legend_note": "In-figure label 'Regex' = the deterministic baseline (stated once in each legend).",
}
(OUT / "canonical_model_order.json").write_text(json.dumps(meta, indent=2))
for name, obj in [("fig1", f1), ("fig2", f2), ("fig3", f3),
                  ("figS1", fS1), ("figS2", fS2), ("figS3", fS3), ("figS4", fS4), ("figS5", fS5)]:
    (OUT / f"{name}.json").write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")
    print("wrote", name + ".json")

print("canonical figure data written")
