# Reproduction and verification scope

## Package-integrity verification

Run `python3 validate_public_release.py`. This verifies file hashes, the 560-case synthetic-only
ID whitelist, 560 Gold and lineage rows, 11 consolidated output files/6,160 output records,
forbidden paths/identifiers, obvious secret patterns, and the explicit pre-publication status.

Run `python3 verify_synthetic_regeneration.py` to regenerate all 80 synthetic originals and all
480 synthetic-derived variants in a temporary directory and compare their normalized text with
the archived release files. This command does not read real-record inputs.

## Synthetic regeneration

The archived deterministic generators and fixed seed reproduce the 80 synthetic originals and
480 synthetic-derived variants text-identically after universal-newline and synthetic-name-field
normalization. The
archived source files use CRLF while regeneration on macOS may use LF; this is a line-ending
difference, not a content difference. See `evidence/synthetic_regeneration_report.md`.

## Frozen-output boundary

The JSONL files reproduce analyses from frozen parsed outputs. They do not support exact reruns of
hosted model endpoints. Provider-side model snapshots and whether requested decoding parameters
were honoured cannot be independently established from this package.

## Aggregate figure reproduction

Install the optional plotting dependencies and regenerate the aggregate-input main figures:

```bash
python3 -m pip install -r requirements.txt
python3 code/generate_main_figures.py --out_dir reproduced_figures
```

This command reads only `data/aggregate/` and writes fresh figure files under the requested output
directory. The package also retains the 5 main and 9 supplementary publication PNG files as frozen
visual outputs. Exact hosted-model endpoint calls and restricted real-source record-level analyses
are outside the public reproduction scope.
