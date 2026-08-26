# GEJ audit analysis code

This is a code-only repository package. It contains analysis, bootstrap,
synthetic-generation, table-generation, and independent plotting source code.

## Deliberately excluded

This package does not contain:

- a manuscript, cover letter, submission files, or editable article source;
- rendered figures or publication-figure assets;
- generated tables or frozen aggregate results;
- synthetic or real record text;
- Gold labels, lineage, model outputs, evidence artifacts, or review files;
- real-source or real-derived case-level materials;
- API credentials, endpoint configuration, or private data.

The analysis scripts therefore require caller-supplied inputs. Their command-line
help describes the expected paths and output locations.

## Included code

- `code/evaluate_gold_dataset.py`: Gold-label evaluation and evidence endpoints.
- `code/seed_cluster_bootstrap.py`: paired synthetic seed-cluster bootstrap.
- `code/evidence_seed_cluster_bootstrap.py`: evidence-endpoint seed-cluster bootstrap.
- `code/generate_mock_cases.py`: deterministic synthetic-seed generator.
- `code/generate_perturbed_cases.py`: H1-H6 perturbation generator.
- `code/generate_paper_tables.py`: table-generation utilities.
- `code/generate_paper_figures.py`: aggregate-input plotting utilities.
- `code/generate_main_figures.py`: independent main-figure plotting utilities.
- `code/generate_supplementary_figures_compact.py`: independent supplementary plotting utilities.
- `code/test_evaluate_gold_dataset.py`: evaluator unit tests.
- `methods/frozen_prompt_rule_pipeline.f79e92dd.py`: frozen method snapshot for code inspection; it is not a standalone executable and requires the original private runtime modules and endpoint configuration.

Rendered publication figures and the publication-figure asset pipeline are not
included in this code-only route.

## Environment and checks

Optional numerical and plotting dependencies are listed in `requirements.txt`.
The standard-library evaluator tests can be run with:

```bash
python3 code/test_evaluate_gold_dataset.py
```

The two self-contained tests run in this package. The record-level regression
test is skipped because its data, Gold, lineage, and frozen-output fixtures are
deliberately excluded.

All Python files can be syntax-checked with:

```bash
python3 -m compileall -q code methods
```

## Licence

The source code in this package is released under the MIT License. See
`LICENSE`.
