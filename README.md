# GEJ evidence-traceability benchmark: synthetic public release

This repository accompanies **Evidence traceability distinguishes large language models in a constructed gastroesophageal junction cancer benchmark**.

## Contents

- `data/`: the 560-instance synthetic benchmark layer (80 originals + 480 H1–H6 variants), normalized Gold labels, lineage map, frozen aggregate tables, and manuscript table inputs.
- `outputs/frozen_parsed_jsonl/`: 6,160 frozen parsed outputs (560 instances × 11 systems).
- `outputs/rule_source_consistency_audit.csv`: result of the rule-source consistency audit (`code/audit_rule_source_consistency.py`).
- `figures/`, `publication_figure_pipeline/`: the locked publication figures and their deterministic SVG source.
- `code/`: evaluation, bootstrap, audit, and plotting utilities. `methods/`: the frozen prompt/rule pipeline snapshot.

## Scope

The release is synthetic-only: no real or real-derived case text, real-source record-level labels or outputs, or patient/seed mapping. Manuscript 700-instance results are released as frozen aggregates and cannot be publicly recomputed from the record-level files. Hosted model endpoints cannot be rerun; provider snapshots and credentials are not included. See `DATA_AVAILABILITY.md` for details.

## Reproduce

See `REPRODUCE.md` for synthetic-layer rescoring and seed-cluster bootstrap commands. Regeneration identity of the synthetic originals is evaluated after universal-newline and synthetic-name-field normalization (the patient-name field uses package-local `患者XXXX` identifiers).

## Provenance

The 80 synthetic originals are generated deterministically by the archived generator (`code/generate_mock_cases.py`) from embedded clinical templates and candidate lists; the generator does not read the 20 real records, and the historical knowledge source of the embedded templates was not contemporaneously documented. GPT-5.4 `xhigh` assisted rule-targeted variant construction; variants were finalized before the reported model-evaluation runs, and exact run timestamps are not recoverable from the retained artifacts. The annotation manual dated 1 May 2026 codifies the pre-existing frozen audit policy and did not change the PASS/FAIL/NA decision criteria or the released Gold labels. Two clinical reviewers (Wanzhe Liao, Zhou Junxian) jointly completed one review round of the 80 originals; 0 records were modified or excluded.

## Licences

- Software in `code/` and `methods/`: **MIT**.
- Synthetic data, Gold/lineage, frozen outputs, and documentation: **CC BY 4.0**.

See `LICENSE.md` for exact scope and attribution.

## Citation

Cite the associated manuscript and this repository. Provisional metadata in `CITATION.cff`; update to the journal article DOI when assigned.
