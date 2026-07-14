# Redacted Taxonomy Tables

These CSV files retain package-local release case IDs, model/rule identifiers, error labels, and taxonomy/actionability labels. They intentionally remove original gold case IDs, source paths, model reasons, evidence snippets, free-text notes, annotator names, and other fields that may contain protected clinical text or local identifiers.

The `release_case_id` values are stable only within this public package. The internal mapping from gold case IDs to release IDs is not written to disk.
