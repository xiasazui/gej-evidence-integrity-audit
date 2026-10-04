"""Exact and format-normalized evidence locatability on the public synthetic layer.

Writes results/public_evidence_locatability.csv (one row per system) and
results/public_locatability_pairwise.csv (paired seed-cluster bootstrap differences).
Usage: python code/locatability.py
"""
import itertools
import json

import numpy as np

from normalization_core import RECOVERABLE, categorize, categorize_strict, snippets, ws
from public_data import REPO, RESULTS, ITERATIONS, RNG_SEED, cluster_weights, interval, load, ratio, write_csv

FIELDS = ["predicted_fail_outputs", "nonempty_outputs", "strict_all_count", "normalized_all_count",
          "normalized_strict_count", "returned_nonempty_items", "verbatim", "field_prefix",
          "ellipsis_join", "non_locatable", "empty_outputs"]
ENDPOINTS = {"strict_all": ("strict_all_count", "predicted_fail_outputs"),
             "normalized_all": ("normalized_all_count", "predicted_fail_outputs"),
             "normalized_strict_all": ("normalized_strict_count", "predicted_fail_outputs"),
             "empty_evidence_rate": ("empty_outputs", "predicted_fail_outputs")}


def main():
    lineage, texts, gold, models = load()
    whitelist = set(json.loads((REPO / "data/normalized_prefix_whitelist.json").read_text())["prefixes"])
    seeds = sorted({r["synthetic_seed_id"] for r in lineage.values()})
    index = {s: i for i, s in enumerate(seeds)}
    weights = cluster_weights(len(seeds))
    rows, dists = [], {}
    for model, outputs in models.items():
        counts = np.zeros((len(seeds), len(FIELDS)), dtype=np.int64)
        for cid, output in outputs.items():
            source = ws(texts[cid])
            i = index[lineage[cid]["synthetic_seed_id"]]
            for result in output["rule_results"]:
                if result["status"] != "FAIL":
                    continue
                ev = snippets(result)
                cats = [categorize(x, source) for x in ev]
                strict = [categorize_strict(x, source, whitelist) for x in ev]
                n = sum(c != "empty" for c in cats)
                counts[i] += [1, int(n > 0), int(bool(ev) and all(c == "verbatim" for c in cats)),
                              int(bool(ev) and all(c in RECOVERABLE for c in cats)),
                              int(bool(ev) and all(c in RECOVERABLE for c in strict)), n,
                              cats.count("verbatim"), cats.count("field_prefix"), cats.count("ellipsis_join"),
                              cats.count("non_locatable"), int(n == 0)]
        observed, draws = counts.sum(axis=0), weights @ counts
        row = {"model": model, **dict(zip(FIELDS, observed.tolist()))}
        dists[model] = {}
        for name, (num, den) in ENDPOINTS.items():
            n, d = FIELDS.index(num), FIELDS.index(den)
            row[name] = float(ratio(observed[n], observed[d]))
            dists[model][name] = ratio(draws[:, n], draws[:, d])
            row[name + "_ci95_low"], row[name + "_ci95_high"] = interval(dists[model][name])
        row["non_locatable_item_rate"] = float(ratio(observed[FIELDS.index("non_locatable")], observed[FIELDS.index("returned_nonempty_items")]))
        rows.append(row)
    for row in rows:
        for name in ["strict_all", "normalized_all", "normalized_strict_all"]:
            row[name + "_rank"] = 1 + sum(other[name] > row[name] for other in rows)
        row["rank_gain"] = row["strict_all_rank"] - row["normalized_all_rank"]
        row.update(n_seed_clusters=len(seeds), iterations=ITERATIONS, rng_seed=RNG_SEED)
    pairs = []
    point = {r["model"]: r for r in rows}
    for a, b in itertools.combinations(models, 2):
        for name in ["strict_all", "normalized_all"]:
            low, high = interval(dists[a][name] - dists[b][name])
            pairs.append(dict(model_a=a, model_b=b, endpoint=name, delta_a_minus_b=point[a][name] - point[b][name], ci95_low=low, ci95_high=high))
    write_csv(RESULTS / "public_evidence_locatability.csv", rows)
    write_csv(RESULTS / "public_locatability_pairwise.csv", pairs)
    print(f"Evidence locatability written for {len(rows)} systems.")


if __name__ == "__main__":
    main()
