"""FAIL-class decision metrics on the public synthetic layer with seed-cluster bootstrap intervals.

Gold NA pairs are excluded; a predicted NA on an applicable pair counts as PASS.
Writes results/public_decision_metrics.csv and results/public_decision_pairwise.csv.
Usage: python code/decision_metrics.py
"""
import itertools

import numpy as np

from public_data import RESULTS, RULES, ITERATIONS, RNG_SEED, cluster_weights, interval, load, ratio, scopes, write_csv


def finite_mean(values, axis=-1):
    values = np.asarray(values, dtype=float)
    return ratio(np.nansum(values, axis=axis), np.isfinite(values).sum(axis=axis))


def decision_values(conf):
    tp, fp, tn, fn = [conf[..., i] for i in range(4)]
    rule_f1 = np.where(tp + fn > 0, ratio(2 * tp, 2 * tp + fp + fn), np.nan)
    return {"macro_f1": finite_mean(rule_f1), "macro_sensitivity": finite_mean(ratio(tp, tp + fn)),
            "macro_specificity": finite_mean(ratio(tn, tn + fp)), "rule_f1": rule_f1}


def main():
    lineage, texts, gold, models = load()
    rows, pairs = [], []
    for scope, cases in scopes(lineage).items():
        seeds = sorted({lineage[c]["synthetic_seed_id"] for c in cases})
        index = {s: i for i, s in enumerate(seeds)}
        weights = cluster_weights(len(seeds))
        dist, point = {}, {}
        for model, outputs in models.items():
            conf = np.zeros((len(seeds), len(RULES), 4), dtype=np.int64)
            for cid in cases:
                si = index[lineage[cid]["synthetic_seed_id"]]
                for result in outputs[cid]["rule_results"]:
                    ri = RULES.index(result["rule_id"])
                    g, fail = gold[cid][result["rule_id"]], result["status"] == "FAIL"
                    if g == "NA":
                        continue
                    conf[si, ri, (0 if fail else 3) if g == "FAIL" else (1 if fail else 2)] += 1
            obs = decision_values(conf.sum(axis=0))
            boot = decision_values((weights @ conf.reshape(len(seeds), -1)).reshape(len(weights), len(RULES), 4))
            row = {"scope": scope, "model": model}
            for name in ["macro_f1", "macro_sensitivity", "macro_specificity"]:
                row[name] = float(obs[name])
                row[name + "_ci95_low"], row[name + "_ci95_high"] = interval(boot[name])
            for i, rule in enumerate(RULES):
                row[f"{rule}_f1"] = float(obs["rule_f1"][i])
            row["macro_f1_without_h6"] = float(finite_mean(obs["rule_f1"][:5]))
            row["macro_f1_without_h6_ci95_low"], row["macro_f1_without_h6_ci95_high"] = interval(finite_mean(boot["rule_f1"][:, :5]))
            row.update(n_seed_clusters=len(seeds), iterations=ITERATIONS, rng_seed=RNG_SEED)
            rows.append(row)
            dist[model], point[model] = boot["macro_f1"], row["macro_f1"]
        if scope == "public_synthetic_560":
            for a, b in itertools.combinations(models, 2):
                low, high = interval(dist[a] - dist[b])
                pairs.append(dict(model_a=a, model_b=b, endpoint="macro_f1", delta_a_minus_b=point[a] - point[b], ci95_low=low, ci95_high=high))
    write_csv(RESULTS / "public_decision_metrics.csv", rows)
    write_csv(RESULTS / "public_decision_pairwise.csv", pairs)
    print(f"Decision metrics written for {len(rows)} system-scope rows.")


if __name__ == "__main__":
    main()
