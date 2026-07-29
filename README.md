# GEJ evidence-integrity benchmark: synthetic and aggregate public release

This repository accompanies **A constructed challenge benchmark for diagnostic evidence-integrity auditing in gastroesophageal junction and cardia cancer notes**.

## Public scope

- 80 script-generated synthetic original records;
- 480 synthetic-derived H1-H6 variants;
- synthetic-only lineage and normalized Gold labels;
- normalized frozen parsed outputs for 11 models/systems (6,160 records, consolidated as one JSONL per system);
- deterministic generators, evaluation/figure/table code, rule definitions, public model-run metadata, and synthetic construction evidence;
- aggregate data and publication figures supporting the manuscript.

The package contains **no real or real-derived case text**, real-source case-level Gold or model outputs, patient/seed provenance mapping, Appendix B, API credentials, private endpoints, source clinical notes, or author-review worklists. The synthetic IDs are limited to `gold_0021`-`gold_0100` and `gold_0221`-`gold_0700`.

The release-case `姓名` field is normalized to a package-local `患者XXXX` identifier. The deterministic generator produces random synthetic names, so regeneration identity is evaluated after universal-newline and synthetic-name-field normalization.

## Contents

- `data/synthetic_cases/`, `data/synthetic_gold_normalized.jsonl` and `data/synthetic_lineage.csv`: the 560-record synthetic-only benchmark layer.
- `outputs/frozen_parsed_jsonl/`: 11 consolidated synthetic-only model/system output files.
- `data/aggregate/`, `data/tables/` and `data/tables_supp/`: privacy-minimized aggregate inputs and manuscript tables.
- `figures/`: 5 main and 9 supplementary publication PNG files.
- `code/`: deterministic generators, evaluation/table code and aggregate-input figure reproduction code.
- `methods/` and `evidence/`: rules, prompt/pipeline snapshot and construction/review evidence.
- `release_manifest.json` and `MANIFEST.sha256`: complete file inventory and checksums.

## Provenance boundary

The 80 synthetic originals are reproduced deterministically from the archived standalone Python generator using predefined clinical templates, candidate lists and numeric ranges. The archived generator does not read the 20 real records during execution, and the available provenance does not show case-by-case derivation from them. The original authorship and knowledge source of the embedded templates and candidate lists were not contemporaneously documented; this release therefore does not claim that the templates were developed without reference to any clinical knowledge or records.

GPT-5.4 `xhigh` was used in the rule-perturbation workflow. Wanzhe Liao and Zhou Junxian, two clinical medicine professionals, jointly completed one review round covering all 80 synthetic originals, checking appropriateness, completeness and internal contradictions; 0 records were modified and 0 were excluded. This does not imply two independent reviews of the 80 records.

## Validate locally

```bash
python3 validate_public_release.py
python3 verify_synthetic_regeneration.py
python3 code/generate_main_figures.py --out_dir reproduced_figures
```

The two validation commands use only the Python standard library. Figure regeneration requires the packages listed in `requirements.txt`. See `REPRODUCE.md` for the reproduction scope, `DATA_AVAILABILITY.md` for the public/restricted data map, and `NON_AUTHOR_TEST_PROTOCOL.md` for anonymous access verification.

## Licences

- Software in `code/` and Python files in `methods/`: **MIT**.
- Synthetic data, Gold/lineage, frozen outputs, evidence and documentation: **CC BY 4.0**.

See `LICENSE.md`, `LICENSE-CODE-MIT.txt` and `LICENSE-DATA-DOCS-CC-BY-4.0.md` for the exact scope, terms and attribution guidance.

## Citation

Cite the associated manuscript and this public repository. Provisional citation metadata are provided in `CITATION.cff`; update the citation to the journal article DOI when assigned.
