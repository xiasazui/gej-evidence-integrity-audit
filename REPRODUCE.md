# Reproduction notes

The public package supports aggregate/frozen-output checks only. It intentionally cannot reconstruct source-note labeling, case-level model evaluation, endpoint calls, retries, or private model outputs.

## Expected constants

- cases: 700
- models/baselines: 11
- gold-applicable rule-case pairs per model: 3,328
- primary predicted-NA policy: `as_pass`
- predicted NA on gold-applicable pairs across models/rules: 37
- missing prediction rule outputs: 0
- audit-error rule outputs: 0
- redacted taxonomy rows: 214

## Commands

Use the commands in `README.md`. `code/validate_release.py` verifies the manifest, expected constants, file boundaries, and absence of obvious secrets/local paths/internal case identifiers.
