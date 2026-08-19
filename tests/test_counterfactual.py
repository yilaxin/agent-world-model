from __future__ import annotations

import importlib.util
import unittest

from agent_world_model.counterfactual import (
    build_counterfactual_pairs,
    counterfactual_pair_summary,
    observed_utility,
)
from agent_world_model.phase2_schema import canonicalize_transition

from test_phase2_schema import sample_record


def paired_records() -> list[dict]:
    records = []
    for role, reward in (("factual", 1.0), ("counterfactual", 0.0)):
        record = sample_record("pair-episode")
        record["reward"] = reward
        record["metadata"] = {
            "counterfactual_pair_id": "pair-1",
            "counterfactual_role": role,
            "intervention": "test",
            "intervention_type": "hard_wrong_target",
            "observed_in_environment": True,
            "initial_state_id": "same-state",
        }
        records.append(canonicalize_transition(record).to_dict())
    return records


class CounterfactualTests(unittest.TestCase):
    def test_observed_pair_is_informative(self) -> None:
        records = paired_records()
        pairs = build_counterfactual_pairs(records)
        self.assertEqual(len(pairs), 1)
        self.assertGreater(pairs[0]["utility_gap"], 0)
        self.assertEqual(pairs[0]["intervention_type"], "hard_wrong_target")
        self.assertGreater(observed_utility(records[0]), observed_utility(records[1]))

    def test_summary_counts_near_ties(self) -> None:
        records = paired_records()
        records[1]["task_signals"] = dict(records[0]["task_signals"])
        records[1]["risks"] = dict(records[0]["risks"])
        summary = counterfactual_pair_summary(records)
        self.assertEqual(summary["observed_pair_count"], 1)
        self.assertEqual(summary["informative_pair_count"], 0)
        self.assertEqual(summary["tied_or_near_tied_pair_count"], 1)


@unittest.skipUnless(importlib.util.find_spec("torch"), "PyTorch is not installed")
class CounterfactualTensorTests(unittest.TestCase):
    def test_pair_tensor_dataset(self) -> None:
        from agent_world_model.phase2_training import CounterfactualPairTensorDataset

        dataset = CounterfactualPairTensorDataset(paired_records())
        self.assertEqual(len(dataset), 1)
        item = dataset[0]
        self.assertEqual(float(item["target"]), 1.0)
        self.assertEqual(item["left_state"].shape, item["right_state"].shape)


if __name__ == "__main__":
    unittest.main()
