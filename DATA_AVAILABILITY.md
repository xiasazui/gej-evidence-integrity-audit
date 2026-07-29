# Data availability

## Public data and code

The public release contains 80 script-generated synthetic original records, 480 synthetic-derived variants, synthetic-only Gold labels and lineage, normalized frozen outputs for 11 systems, deterministic generation and perturbation code, rule and method files, aggregate analysis data, and publication figures.

Repository: `https://github.com/xiasazui/gej-evidence-integrity-audit`

## Restricted clinical data

The 20 de-identified real original clinical notes, 120 real-derived variants, and all real-source record-level Gold labels, model outputs, evidence, reasons, lineage and patient/seed/provenance mappings are not publicly deposited because public redistribution is restricted by participant privacy and institutional health-data governance requirements. Appendix B and clinical-note excerpts are also excluded.

Requests for access to restricted clinical materials must follow the separately approved institutional process and may require research-ethics review, a data-use agreement, non-commercial research use, and prohibitions on onward sharing and re-identification. This public repository does not itself grant or imply access to those restricted materials.

## Provenance qualification

The archived standalone generator deterministically reproduces the 80 synthetic originals from embedded templates, candidate lists and numeric ranges and does not read the 20 real records during execution. Available provenance does not show case-by-case derivation from real records. The historical knowledge source of the embedded templates and candidate lists was not contemporaneously documented; no broader claim of independence from all clinical knowledge or records is made.

## Repository identifier

The public GitHub repository URL is the current access route. A repository DOI has not been assigned; if one is minted later, it can be added to this file, `CITATION.cff`, and the manuscript data citation.
