"""Exact evidence counts for the clinical-source layer (n = 140) by subtraction.

Clinical-source counts = full-benchmark counts (data/full_benchmark/full_benchmark_counts.csv)
minus public-layer counts recomputed here with the original matching functions
(code/original_scoring.py). The recomputed public counts must equal the public-layer counts
of the original evaluation (data/full_benchmark/public_layer_counts.csv). Lenient item rates
are available only to three decimal places, so compatible integer bounds are reported.
Writes results/clinical_source_counts.csv.
Usage: python code/clinical_source_counts.py
"""
import collections
import csv

import original_scoring as old
from public_data import REPO, RESULTS, load, write_csv

FIELDS = ["predicted_fail_outputs", "outputs_with_nonempty_evidence", "returned_evidence_items",
          "recoverable_evidence_items", "outputs_all_snippets_recoverable",
          "fail_outputs_at_least_one_snippet_recoverable", "fail_outputs_any_nonrecoverable_snippet",
          "fail_outputs_empty_evidence"]


def main():
    lineage, texts, gold, models = load()
    full = {r["model"]: r for r in csv.DictReader((REPO / "data/full_benchmark/full_benchmark_counts.csv").open(encoding="utf-8-sig"))}
    ref = {r["model"]: r for r in csv.DictReader((REPO / "data/full_benchmark/public_layer_counts.csv").open(encoding="utf-8-sig"))}
    rows = []
    for model, outputs in models.items():
        c = collections.Counter({k: 0 for k in FIELDS})
        lenient_public, na_applicable = 0, 0
        for cid, output in outputs.items():
            hay = old._normalize_for_contains(texts[cid])
            lenient_hay = old._normalize_for_lenient_contains(texts[cid])
            for r in output["rule_results"]:
                if gold[cid][r["rule_id"]] == "NA" and r["status"] in ("PASS", "FAIL"):
                    na_applicable += 1
                if r["status"] != "FAIL":
                    continue
                ev = [str(x).strip() for x in (r.get("evidence") or []) if str(x or "").strip()]
                found = [old._normalize_for_contains(x) in hay for x in ev]
                c["predicted_fail_outputs"] += 1
                c["outputs_with_nonempty_evidence"] += bool(ev)
                c["returned_evidence_items"] += len(ev)
                c["recoverable_evidence_items"] += sum(found)
                c["outputs_all_snippets_recoverable"] += bool(ev) and all(found)
                c["fail_outputs_at_least_one_snippet_recoverable"] += any(found)
                c["fail_outputs_any_nonrecoverable_snippet"] += any(not x for x in found)
                c["fail_outputs_empty_evidence"] += not ev
                lenient_public += sum(old._evidence_item_in_text_lenient(x, lenient_hay) for x in ev)
        assert all(c[k] == int(ref[model][k]) for k in FIELDS[:5]), f"public parity failed: {model}"
        d = {k: int(full[model][k]) - c[k] for k in FIELDS}
        assert all(v >= 0 for v in d.values())
        na_fail = d["predicted_fail_outputs"] - int(full[model]["clinical_applicable_tp_plus_fp"])
        assert 0 <= na_fail <= int(full[model]["full_gold_na_predicted_applicable"]) - na_applicable
        assert d["outputs_all_snippets_recoverable"] + d["fail_outputs_any_nonrecoverable_snippet"] == d["outputs_with_nonempty_evidence"]
        assert d["outputs_with_nonempty_evidence"] + d["fail_outputs_empty_evidence"] == d["predicted_fail_outputs"]
        denom, shown = int(full[model]["returned_evidence_items"]), full[model]["full_lenient_item_rate_3dp"]
        allowed = [k - lenient_public for k in range(denom + 1)
                   if f"{k / denom:.3f}" == shown and 0 <= k - lenient_public <= d["returned_evidence_items"]]
        assert allowed
        rows.append(dict(model=model, **d,
                         strict_all=d["outputs_all_snippets_recoverable"] / d["predicted_fail_outputs"],
                         strict_item=d["recoverable_evidence_items"] / d["returned_evidence_items"] if d["returned_evidence_items"] else float("nan"),
                         lenient_item_min=min(allowed) / d["returned_evidence_items"] if d["returned_evidence_items"] else float("nan"),
                         lenient_item_max=max(allowed) / d["returned_evidence_items"] if d["returned_evidence_items"] else float("nan")))
    write_csv(RESULTS / "clinical_source_counts.csv", rows)
    print("Clinical-source counts derived for all 11 systems; all consistency checks passed.")


if __name__ == "__main__":
    main()
