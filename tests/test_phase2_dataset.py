from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from agent_world_model.phase2_dataset import (
    audit_examples,
    split_episodes,
    write_dataset_bundle,
)
from agent_world_model.phase2_schema import canonicalize_transition

from test_phase2_schema import sample_record


class Phase2DatasetTests(unittest.TestCase):
    def test_episode_split_has_no_leakage(self) -> None:
        episodes = [f"episode-{index}" for index in range(10)]
        mapping = split_episodes(episodes, seed=7)
        self.assertEqual(set(mapping), set(episodes))
        self.assertEqual(set(mapping.values()), {"train", "validation", "test"})

    def test_dataset_bundle_and_audit(self) -> None:
        examples = []
        for index in range(6):
            base = canonicalize_transition(sample_record(f"episode-{index}", index))
            examples.append(replace(base, split=("train", "validation", "test")[index % 3]))
        with tempfile.TemporaryDirectory() as directory:
            card = write_dataset_bundle(directory, examples)
            self.assertEqual(card["transition_count"], 6)
            self.assertTrue(card["quality_gates"]["no_episode_leakage"])
            self.assertFalse(card["quality_gates"]["p0_500_transitions"])
            for split in ("train", "validation", "test"):
                self.assertTrue((Path(directory) / f"{split}.jsonl").exists())

    def test_audit_detects_episode_leakage(self) -> None:
        example = canonicalize_transition(sample_record())
        leaked = [replace(example, split="train"), replace(example, split="test")]
        card = audit_examples(leaked)
        self.assertEqual(card["episode_split_leakage"], ["episode-1"])

    def test_counterfactual_pair_audit(self) -> None:
        rows = []
        for role, action in (("factual", 'click("42", "left")'), ("counterfactual", 'click("41", "left")')):
            record = sample_record("pair-episode")
            record["action"] = action
            record["metadata"] = {
                "counterfactual_pair_id": "pair-1",
                "counterfactual_role": role,
                "observed_in_environment": True,
                "initial_state_id": "same-state",
            }
            rows.append(replace(canonicalize_transition(record), split="test"))
        card = audit_examples(rows)
        self.assertEqual(card["counterfactual_audit"]["valid_observed_pair_count"], 1)
        self.assertEqual(card["counterfactual_audit"]["pair_split_leakage"], [])

    def test_counterfactual_group_leakage_is_detected(self) -> None:
        rows = []
        for index, split in enumerate(("train", "test")):
            record = sample_record(f"episode-{index}", index)
            record["metadata"] = {
                "counterfactual_pair_id": f"pair-{index}",
                "counterfactual_group_id": "shared-state-group",
                "counterfactual_role": "factual",
                "observed_in_environment": True,
                "initial_state_id": "same-state",
            }
            rows.append(replace(canonicalize_transition(record), split=split))
        card = audit_examples(rows)
        self.assertEqual(
            card["counterfactual_audit"]["group_split_leakage"],
            ["shared-state-group"],
        )
        self.assertFalse(card["quality_gates"]["no_counterfactual_group_leakage"])

    def test_dataset_card_reports_real_multistep_windows(self) -> None:
        examples = []
        for step in range(3):
            record = sample_record("multi-episode", step)
            record["terminated"] = step == 2
            record["reward"] = 1.0 if step == 2 else 0.0
            examples.append(canonicalize_transition(record, split="test"))
        card = audit_examples(examples)
        self.assertEqual(
            card["multistep_audit"]["by_split"]["test"]["by_horizon"]["3"]["window_count"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
