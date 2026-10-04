# GEJ documentation-audit benchmark: public synthetic layer

Code and public data for the article *Exact-match scoring conflates citation format with evidence locatability in LLM clinical documentation audits*.

The benchmark contains 700 Chinese-language outpatient records of gastroesophageal junction (GEJ) and gastric cardia cancer, audited under six rules (H1–H6) by ten large language models and a regex baseline. This repository contains the 560 synthetic records (80 template-generated originals and 480 rule-targeted variants), their Gold labels, the outputs of the 11 systems on these records, and the analysis code. The 140 clinical-source records are not public.

## Contents

| Path | Contents |
| --- | --- |
| `data/synthetic_cases/` | 560 synthetic records |
| `data/synthetic_gold_normalized.jsonl` | Gold PASS/FAIL/NA labels for H1–H6 |
| `data/synthetic_lineage.csv` | Seed, record type and target rule of each record |
| `data/model_outputs/` | Outputs of the 11 systems on the 560 records |
| `data/normalized_prefix_whitelist.json` | Record headings accepted by the stricter normalizer |
| `data/full_benchmark/` | Aggregate counts from the full 700-record evaluation, used to derive clinical-source counts |
| `code/` | Analysis code |

## Running the analyses

Python 3.9 or later. From the repository root:

```bash
pip install -r requirements.txt
python code/locatability.py            # exact and format-normalized evidence locatability
python code/decision_metrics.py        # FAIL-class decision metrics
python code/rule_based_validation.py   # validation of rescued and residual snippets
python code/clinical_source_counts.py  # clinical-source exact counts by subtraction
```

Results are written to `results/`. No model is called. Confidence intervals use 2,000 bootstrap resamples of the 80 seed clusters (NumPy PCG64, seed 20261002).

`code/normalization_core.py` defines the citation-format categories, and `code/original_scoring.py` contains the matching functions of the original evaluation. `code/generate_mock_cases.py` generates the synthetic originals (`python code/generate_mock_cases.py --seed 20251220`; released records carry study identifiers in place of the generated names), and `code/generate_perturbed_cases.py` applies the rule-targeted operators that produce the variants. `code/frozen_prompt_rule_pipeline.py` contains the rule definitions and prompts used in the evaluation and is included for reference.

## Licence

Code is released under the MIT licence and data under CC BY 4.0 (`LICENSE.md`).
