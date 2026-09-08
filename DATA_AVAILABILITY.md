# Data availability

## Public record-level data

The publicly releasable record-level layer contains 80 script-generated synthetic original records, 480 synthetic-derived variants, synthetic-only Gold labels and lineage, and 6,160 normalized frozen parsed outputs from 11 systems. This 560-record layer supports synthetic record-level rescoring and synthetic 80-seed cluster-bootstrap comparisons.

It does not support record-level recomputation of the full 700-instance benchmark.

## Public frozen aggregates

The release also contains privacy-minimized frozen aggregate tables and publication figures. These include 700-instance manuscript results, pooled 100-seed and real-20-seed bootstrap summaries, full-benchmark evidence endpoints, and human-review/kappa/taxonomy summaries. They are provided for result inspection, manuscript reconciliation, and aggregate-input plotting. They are not publicly recomputable from the released record-level layer.

S01 contains nine selected seed-cluster comparisons and S20 contains 165 rows (55 model pairs x three scopes), each with 2,000 bootstrap iterations and `ordinary_mcnemar_used=false`. These tables contain no case ID, patient identifier, source path, or note text.

The files `data/aggregate/evidence_seed_cluster_bootstrap_public_synthetic.csv` and `.json` are separately recomputed synthetic-only evidence endpoint summaries for the same 80 seed clusters. They do not replace the full-700 evidence endpoint table, which remains frozen aggregate-only.

## Restricted clinical data

The 20 de-identified real original clinical notes, 120 real-derived variants, and all real-source record-level Gold labels, model outputs, evidence, reasons, lineage, and patient/seed/provenance mappings are not publicly deposited because public redistribution is restricted by participant privacy and institutional health-data governance requirements. Appendix B and clinical-note excerpts are also excluded.

Scientifically justified requests for restricted clinical materials should be sent to Wang Pengyuan at `pengyuan_wang@bjmu.edu.cn`. Requests will be answered within 30 working days and reviewed for scientific purpose, ethics compatibility, and data-security safeguards. Approved access requires an institutional data use agreement and prohibits redistribution. Where ethically and legally permitted, relevant controlled materials can be provided confidentially to journal editors and peer reviewers for manuscript assessment. This repository does not itself grant, promise, or imply access to restricted materials.

## Provenance qualification

The archived standalone generator deterministically reproduces the 80 synthetic originals from embedded templates, candidate lists, and numeric ranges and does not read the 20 real records during execution. Available provenance does not show case-by-case derivation from real records. The historical knowledge source of the embedded templates and candidate lists was not contemporaneously documented; no broader claim of independence from all clinical knowledge or records is made.

## Repository route

Intended public repository: `https://github.com/xiasazui/gej-evidence-integrity-audit`

The repository route is listed above for public access. A repository DOI has not been assigned; if one is minted later, it can be added to this file, `CITATION.cff`, and the manuscript data citation.
