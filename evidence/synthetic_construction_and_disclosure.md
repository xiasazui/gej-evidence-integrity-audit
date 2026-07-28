# Synthetic construction, provenance and review disclosure

- The deterministic Python generator uses fixed seed `20251220` for the 80 script-generated synthetic originals.
- It builds records from predefined clinical templates, candidate lists and numeric ranges embedded in the script.
- The archived generator does not read the 20 real records or any other case files during execution, and available provenance does not show case-by-case derivation from real records.
- The historical authorship and knowledge source of the embedded templates and candidate lists were not contemporaneously documented. This release therefore does not claim that template development was independent of all clinical knowledge or records.
- Release-case synthetic names are replaced by package-local `患者XXXX` identifiers; regeneration comparisons normalize this field and universal newlines.
- The archived generator itself contains no network/API/LLM call.
- GPT-5.4 `xhigh` was used in the rule-perturbation workflow.
- Wanzhe Liao and Zhou Junxian, two clinical medicine professionals, jointly completed one review round covering all 80 synthetic originals.
- They checked appropriateness, completeness and internal contradictions.
- Records modified after review: 0. Records excluded after review: 0.
- This does not claim that both reviewers independently reviewed all 80 records.
- More detailed historical implementation or personnel information is not asserted in this release.
