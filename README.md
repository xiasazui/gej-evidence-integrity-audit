# GEJ diagnostic-evidence audit: public reproducibility package

This repository accompanies **Retrospective offline benchmark for diagnostic evidence integrity in gastroesophageal junction and cardia cancer notes**.

It contains publication-level aggregate data, redacted taxonomy tables, figures, and code that regenerates the four main figures derived entirely from public aggregate inputs. It does **not** contain source clinical notes, case-level labels, case-level model outputs, Appendix B excerpts, reviewer worklists, API credentials, private endpoints, or local configuration.

## Contents

- `data/aggregate/`: privacy-minimized aggregate JSON and a public model-run manifest.
- `data/tables/` and `data/tables_supp/`: manuscript and supplementary aggregate tables.
- `data/taxonomy_redacted/`: 214 human-reviewed taxonomy rows with package-local release IDs and no clinical text, source path, notes, or reviewer identity.
- `figures/`: publication PNG files.
- `code/generate_main_figures.py`: regenerates aggregate-input main figures.
- `release_manifest.json` and `MANIFEST.sha256`: file inventory and SHA256 checksums.

## Reproducibility scope

This is **aggregate/frozen-output reproducibility**, not a public case-level benchmark and not an exact rerun of hosted model endpoints. Each model/baseline was evaluated on 3,328 gold-applicable rule-case pairs. The primary prediction-NA policy was `as_pass`; the frozen outputs contain 0 missing predictions, 0 audit-error rule outputs, and 37 predicted-NA outputs on gold-applicable pairs across all models and rules.

Run:

```bash
python3 -m pip install -r requirements.txt
python3 code/generate_main_figures.py \
  --gold_dataset_summary_json data/aggregate/gold_dataset_summary.json \
  --gold_eval_viz_json data/aggregate/gold_eval_models_summary.json \
  --kappa_json data/aggregate/kappa_summary.json \
  --taxonomy_dir data/taxonomy_redacted \
  --out_dir reproduced_figures
python3 code/validate_release.py
```

The regeneration command writes case-level burden, F1-versus-grounding, rule-distribution/kappa, and taxonomy figures in PNG/PDF/SVG/TIFF formats. Figures 2 and 4 are retained as frozen publication figures because their original renderer is outside this minimal package.

## Data availability

The source clinical notes and case-level derived artifacts are not publicly available because they contain confidential patient information and institutional restrictions prohibit public release. This repository exposes only aggregate statistics, privacy-scanned redacted taxonomy data, publication figures, and reproducibility code. Any request for additional de-identified material remains subject to a separately approved institutional access process; no such public access route is implied by this repository.

## Licenses and citation

The final code and data licenses must be approved by the corresponding author/institution before public release. See `LICENSES_PENDING.md`. Cite the associated paper and the immutable GitHub release/archival DOI once assigned; provisional citation metadata are in `CITATION.cff`.
