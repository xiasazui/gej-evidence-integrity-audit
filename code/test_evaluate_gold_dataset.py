from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, Optional


ROOT = Path(__file__).resolve().parents[1]
EVALUATOR = ROOT / "code" / "evaluate_gold_dataset.py"


def _run_evaluator(
    gold: Path,
    *,
    pred_jsonl: Optional[Path] = None,
    pred_dir: Optional[Path] = None,
    cases_dir: Optional[Path] = None,
    lineage: Optional[Path] = None,
    out_dir: Path,
    bootstrap: int = 0,
) -> Dict[str, Any]:
    command = [
        "python3",
        str(EVALUATOR),
        "--gold_labels",
        str(gold),
        "--bootstrap",
        str(bootstrap),
        "--out_json",
        str(out_dir / "eval.json"),
        "--out_md",
        str(out_dir / "eval.md"),
    ]
    if pred_jsonl is not None:
        command.extend(["--pred_jsonl", str(pred_jsonl)])
    else:
        assert pred_dir is not None
        command.extend(["--pred_dir", str(pred_dir)])
    if cases_dir is not None:
        command.extend(["--cases_dir", str(cases_dir)])
    if lineage is not None:
        command.extend(["--lineage_csv", str(lineage)])
    completed = subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
    assert completed.stdout.strip()
    return json.loads((out_dir / "eval.json").read_text(encoding="utf-8"))


def _write_small_fixture(directory: Path) -> tuple[Path, Path, Path, Path]:
    cases_dir = directory / "cases"
    cases_dir.mkdir()
    gold_path = directory / "gold.jsonl"
    pred_path = directory / "pred.jsonl"
    pred_dir = directory / "pred_dir"
    pred_dir.mkdir()

    labels = {rule: "PASS" for rule in ("H1", "H2", "H3", "H4", "H5", "H6")}
    gold_rows = []
    prediction_rows = []
    for case_id, evidence in (
        ("case_a", []),
        ("case_b", ["not present"]),
        ("case_c", ["fact"]),
    ):
        case_labels = dict(labels)
        case_labels["H1"] = "FAIL"
        gold_rows.append({"case_id": case_id, "labels": case_labels})
        prediction_rows.append(
            {
                "case_id": case_id,
                "rule_results": [
                    {
                        "rule_id": rule,
                        "status": "FAIL" if rule == "H1" else "PASS",
                        "evidence": evidence if rule == "H1" else [],
                    }
                    for rule in labels
                ],
            }
        )
        (cases_dir / f"{case_id}.md").write_text("fact\n", encoding="utf-8")

    gold_path.write_text("\n".join(json.dumps(row) for row in gold_rows) + "\n", encoding="utf-8")
    pred_path.write_text("\n".join(json.dumps(row) for row in prediction_rows) + "\n", encoding="utf-8")
    (pred_dir / "case_case_a.json").write_text(json.dumps(prediction_rows[0]), encoding="utf-8")
    (pred_dir / "case_case_b.json").write_text(json.dumps(prediction_rows[1]), encoding="utf-8")
    (pred_dir / "case_case_c.json").write_text(json.dumps(prediction_rows[2]), encoding="utf-8")
    return gold_path, pred_path, pred_dir, cases_dir


class PublicEvaluatorTest(unittest.TestCase):
    def test_public_deterministic_baseline_jsonl_and_seed_bootstrap(self) -> None:
        required_release_inputs = [
            ROOT / "data" / "synthetic_gold_normalized.jsonl",
            ROOT / "outputs" / "frozen_parsed_jsonl" / "deterministic-baseline.jsonl",
            ROOT / "data" / "synthetic_cases",
            ROOT / "data" / "synthetic_lineage.csv",
        ]
        if not all(path.exists() for path in required_release_inputs):
            self.skipTest("record-level release inputs are intentionally absent from the code-only package")

        with tempfile.TemporaryDirectory() as temporary:
            output = _run_evaluator(
                ROOT / "data" / "synthetic_gold_normalized.jsonl",
                pred_jsonl=ROOT / "outputs" / "frozen_parsed_jsonl" / "deterministic-baseline.jsonl",
                cases_dir=ROOT / "data" / "synthetic_cases",
                lineage=ROOT / "data" / "synthetic_lineage.csv",
                out_dir=Path(temporary),
                bootstrap=5,
            )

        self.assertEqual(output["rules"], ["H1", "H2", "H3", "H4", "H5", "H6"])
        self.assertEqual(output["n_gold_cases"], 560)
        self.assertEqual(output["n_prediction_cases"], 560)
        self.assertEqual(output["total_rule_pairs_eval"], 2720)
        self.assertEqual(output["bootstrap_unit"], "seed_cluster")

        for analysis_set in ("all_predicted_fail", "gold_applicable_predicted_fail"):
            metrics = output["evidence_analysis"]["analysis_sets"][analysis_set]
            self.assertEqual(metrics["predicted_fail_outputs"], 480)
            self.assertEqual(metrics["outputs_with_nonempty_evidence"], 320)
            self.assertEqual(metrics["returned_evidence_items"], 320)
            self.assertEqual(metrics["recoverable_evidence_items"], 320)
            self.assertEqual(metrics["outputs_all_snippets_recoverable"], 320)
            self.assertEqual(metrics["endpoint_fractions"]["all_snippet_recoverability"]["denominator"], 480)
            self.assertEqual(
                metrics["ci95_seed_cluster_bootstrap"]["all_snippet_recoverability"]["valid_replicates"],
                5,
            )

    def test_empty_and_unrecoverable_evidence_fail_strict_integrity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            gold, predictions, _pred_dir, cases = _write_small_fixture(Path(temporary))
            output = _run_evaluator(
                gold,
                pred_jsonl=predictions,
                cases_dir=cases,
                out_dir=Path(temporary),
            )

        metrics = output["evidence_analysis"]["all_predicted_fail"]
        self.assertEqual(metrics["predicted_fail_outputs"], 3)
        self.assertEqual(metrics["outputs_with_nonempty_evidence"], 2)
        self.assertEqual(metrics["returned_evidence_items"], 2)
        self.assertEqual(metrics["recoverable_evidence_items"], 1)
        self.assertEqual(metrics["outputs_all_snippets_recoverable"], 1)
        self.assertEqual(metrics["endpoint_fractions"]["evidence_coverage"]["denominator"], 3)
        self.assertEqual(metrics["endpoint_fractions"]["conditional_item_recoverability"]["denominator"], 2)
        self.assertFalse(metrics["endpoint_fractions"]["all_snippet_recoverability"]["empty_evidence_passes"])
        self.assertEqual(output["bootstrap_unit"], "case")
        self.assertNotIn("ci95_seed_cluster_bootstrap", metrics)

    def test_legacy_prediction_directory_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            gold, _predictions, pred_dir, cases = _write_small_fixture(Path(temporary))
            output = _run_evaluator(
                gold,
                pred_dir=pred_dir,
                cases_dir=cases,
                out_dir=Path(temporary),
            )
        self.assertIsNone(output["pred_jsonl"])
        self.assertEqual(output["n_prediction_cases"], 3)
        self.assertEqual(output["evidence_analysis"]["all_predicted_fail"]["predicted_fail_outputs"], 3)


if __name__ == "__main__":
    unittest.main()
