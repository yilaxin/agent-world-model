from __future__ import annotations

import unittest

from agent_world_model.phase2_metrics import (
    binary_metrics,
    coverage_risk_curve,
    evaluate_thresholds,
    expected_calibration_error,
    regression_metrics,
)


class Phase2MetricTests(unittest.TestCase):
    def test_perfect_binary_predictions(self) -> None:
        result = binary_metrics([0, 1, 1, 0], [0.01, 0.9, 0.8, 0.1])
        self.assertEqual(result["f1"], 1.0)
        self.assertEqual(result["auroc"], 1.0)
        self.assertEqual(result["auprc"], 1.0)
        self.assertLess(result["brier"], 0.03)
        self.assertLess(result["nll"], 0.2)
        self.assertEqual(result["coverage_risk"]["points"][-1]["risk"], 0.0)

    def test_coverage_risk_prioritizes_confident_examples(self) -> None:
        result = coverage_risk_curve(
            [1, 0, 1, 0],
            [0.99, 0.01, 0.49, 0.51],
            coverages=(0.5, 1.0),
        )
        self.assertEqual(result["points"][0]["risk"], 0.0)
        self.assertEqual(result["points"][1]["risk"], 0.5)

    def test_ece_is_zero_for_balanced_calibrated_bin(self) -> None:
        self.assertAlmostEqual(expected_calibration_error([0, 1], [0.5, 0.5]), 0.0)

    def test_regression_and_thresholds(self) -> None:
        metrics = {"progress": regression_metrics([0, 1], [0, 1])}
        self.assertEqual(metrics["progress"]["mae"], 0.0)
        gate = evaluate_thresholds(
            {"risk": {"macro_f1": 0.75, "ece": 0.05}},
            {
                "risk.macro_f1": {"op": ">=", "value": 0.6},
                "risk.ece": {"op": "<=", "value": 0.1},
            },
        )
        self.assertTrue(gate["passed"])


if __name__ == "__main__":
    unittest.main()
