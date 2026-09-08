# Reproduction scope

## Install optional analysis dependencies

Synthetic rescoring, the seed-cluster bootstrap, and figure rendering require NumPy/Matplotlib:

```bash
python3 -m pip install -r requirements.txt
```

## Synthetic record-level rescoring

The released Gold, lineage, and frozen parsed output files support synthetic record-level rescoring for exactly 560 instances. They do not contain the 140 real/real-derived instances needed for a 700-instance rerun. `code/seed_cluster_bootstrap.py` provides a complete paired F1 rescoring path for the public synthetic layer; `code/evidence_seed_cluster_bootstrap.py` provides synthetic-only evidence endpoint rescoring and seed-cluster intervals.

For synthetic evidence endpoints, run:

```bash
python3 code/evidence_seed_cluster_bootstrap.py \
  --cases_dir data/synthetic_cases \
  --seed_map data/synthetic_lineage.csv \
  --gold data/synthetic_gold_normalized.jsonl \
  --pred_dir outputs/frozen_parsed_jsonl \
  --iterations 2000 \
  --rng_seed 20260810 \
  --out_csv reproduced_synthetic_evidence_bootstrap.csv \
  --out_json reproduced_synthetic_evidence_bootstrap.json
```

These outputs are new synthetic-only results. They are not replacements for manuscript tables whose analysis set is the full 700-instance benchmark.

## Synthetic seed-cluster bootstrap

This command recomputes one paired comparison on the public 80-seed/560-instance synthetic layer:

```bash
python3 code/seed_cluster_bootstrap.py \
  --gold data/synthetic_gold_normalized.jsonl \
  --seed_map data/synthetic_lineage.csv \
  --pred_a outputs/frozen_parsed_jsonl/gemini-3-pro-preview-thinking.jsonl \
  --pred_b outputs/frozen_parsed_jsonl/kimi-k2-thinking.jsonl \
  --iterations 2000 \
  --rng_seed 20460720 \
  --out_json reproduced_synthetic_gemini_vs_kimi.json
```

The command enforces 80 seed clusters, seven instances per cluster, 560 unique cases, and complete Gold/prediction coverage. It uses PCG64 multinomial cluster weights and the frozen predicted-NA-as-PASS policy. The expected synthetic-layer regression values are:

- macro-F1 delta: `-0.0005003033`; 95% percentile CI: `[-0.0045035747, 0.0039664832]`
- micro-F1 delta: `-0.0035397643`; 95% percentile CI: `[-0.0088181755, 0.0017730286]`

The output declares `analysis_scope` as `public synthetic layer only` and `ordinary_mcnemar_used` as `false`. It cannot regenerate the pooled 100-seed, real-20-seed, or all-pair full-benchmark results in S01/S20 because their record-level inputs and full mapping are restricted.

## Frozen aggregate tables

The following are frozen aggregate results rather than public record-level recomputations:

- 700-instance manuscript macro/micro and rule-level results;
- pooled 100-seed and real-20-seed bootstrap results in S01/S20;
- full-700 evidence coverage, conditional item recoverability, and all-snippet recoverability endpoints;
- human-review, kappa, taxonomy, and restricted-source descriptive aggregates.

These files may be audited, compared with the manuscript, and used as plotting inputs. The public package does not contain the restricted rows needed to regenerate them.

## Canonical publication-figure rendering

Run:

```bash
cd publication_figure_pipeline/source/figure_sources
python3 build_canonical.py
node fig1.mjs && node fig2.mjs && node fig3.mjs
node figS1.mjs && node figS2.mjs && node figS3.mjs && node figS4.mjs && node figS5.mjs
```

This pipeline reads the included frozen CSV/JSON inputs and regenerates exactly eight editable SVGs: three main figures and five composite supplementary figures.

To render one SVG to vector PDF and 600 dpi PNG:

```bash
node render.mjs ../../main_figures/Figure_1.svg ../../main_figures/Figure_1.pdf \
  ../../main_figures/Figure_1_600dpi.png 180 68
```

`render.mjs` requires Google Chrome and PyMuPDF. See `publication_figure_pipeline/README.md` for all eight exact dimensions and the mapping to `figures/`.

## Independent aggregate-input plotting utilities

The older Matplotlib utilities remain available for independent replotting:

```bash
python3 code/generate_main_figures.py --out_dir reproduced_figures/main
python3 code/generate_supplementary_figures_compact.py --out_dir reproduced_figures/supplementary
```

These scripts are independent aggregate-input plotting utilities and may differ stylistically from the canonical Node.js/SVG publication pipeline. Neither route regenerates restricted record-level derivations of the supplied aggregate inputs.

## Hosted-model boundary

The frozen JSONL outputs do not support exact hosted-endpoint reruns. Provider-side model snapshots, credentials, private endpoints, and independent confirmation that requested decoding parameters were honoured are outside the public reproduction scope.
