"""Loading and bootstrap helpers shared by the public-layer analyses."""
import csv
import json
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
RESULTS = REPO / "results"
RULES = [f"H{i}" for i in range(1, 7)]
ITERATIONS = 2000
RNG_SEED = 20261002


def jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def load(repo=REPO):
    lineage = {r["case_id"]: r for r in csv.DictReader((repo / "data/synthetic_lineage.csv").open(encoding="utf-8-sig"))}
    assert len(lineage) == 560
    texts = {cid: (repo / r["case_filename"]).read_text(encoding="utf-8-sig") for cid, r in lineage.items()}
    gold = {r["case_id"]: {k: v.get("status") if isinstance(v, dict) else v for k, v in r["labels"].items()}
            for r in jsonl(repo / "data/synthetic_gold_normalized.jsonl")}
    models = {}
    for path in sorted((repo / "data/model_outputs").glob("*.jsonl")):
        rows = jsonl(path)
        assert len(rows) == len({r["case_id"] for r in rows}) == 560 and {r["case_id"] for r in rows} == set(lineage)
        models[path.stem] = {r["case_id"]: r for r in rows}
    assert len(models) == 11
    return lineage, texts, gold, models


def scopes(lineage):
    return {
        "public_synthetic_560": sorted(lineage),
        "synthetic_original_80": sorted(c for c, r in lineage.items() if r["source_class"] == "synthetic_original"),
        "synthetic_derived_480": sorted(c for c, r in lineage.items() if r["source_class"] == "synthetic_derived"),
    }


def cluster_weights(n, iterations=ITERATIONS, seed=RNG_SEED):
    """Seed-cluster multinomial resampling weights; identical draws are shared by all systems."""
    return np.random.Generator(np.random.PCG64(seed)).multinomial(n, np.full(n, 1 / n), size=iterations)


def ratio(a, b):
    a, b = np.broadcast_arrays(np.asarray(a, dtype=float), np.asarray(b, dtype=float))
    return np.divide(a, b, out=np.full_like(a, np.nan), where=b != 0)


def interval(samples):
    valid = np.asarray(samples, dtype=float)
    valid = valid[np.isfinite(valid)]
    if not len(valid):
        return np.nan, np.nan
    low, high = np.quantile(valid, [0.025, 0.975])
    return float(low), float(high)


def write_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for r in rows for k in r))
    clean = lambda v: "" if isinstance(v, float) and not np.isfinite(v) else v
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows({k: clean(v) for k, v in r.items()} for r in rows)
