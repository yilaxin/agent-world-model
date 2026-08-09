from __future__ import annotations

import unittest

from agent_world_model.phase2_schema import (
    canonicalize_transition,
    encode_action,
    symlog,
    symexp,
)


def sample_record(episode_id: str = "episode-1", step: int = 0) -> dict:
    return {
        "schema_version": 2,
        "episode_id": episode_id,
        "env_id": "browsergym/miniwob.click-test",
        "step_index": step,
        "state": {
            "goal": "Click Submit",
            "url": "http://example/start",
            "title": "Start",
            "axtree": {"text": "[42] button 'Submit'"},
            "dom": {"text": "<button bid='42'>Submit</button>"},
        },
        "action": 'click("42", "left")',
        "next_state": {
            "goal": "Click Submit",
            "url": "http://example/done",
            "title": "Done",
            "axtree": {"text": "[42] button 'Submitted'"},
            "dom": {"text": "<button bid='42'>Submitted</button>"},
            "last_action_error": "",
        },
        "reward": 1.0,
        "terminated": True,
        "truncated": False,
    }


class Phase2SchemaTests(unittest.TestCase):
    def test_symlog_round_trip(self) -> None:
        for value in (-100.0, -1.0, 0.0, 0.25, 9.0):
            self.assertAlmostEqual(symexp(symlog(value)), value)

    def test_action_encoding_is_deterministic_and_parsed(self) -> None:
        first, info = encode_action('click("42", "left")', 32)
        second, _ = encode_action('click("42", "left")', 32)
        self.assertEqual(first, second)
        self.assertEqual(info["action_type"], "click")
        self.assertEqual(info["target_element_ids"], ["42"])
        self.assertEqual(len(first), 32)

    def test_legacy_transition_is_upgraded(self) -> None:
        example = canonicalize_transition(
            sample_record(), state_dimensions=64, action_dimensions=32
        )
        self.assertEqual(example.schema_version, 3)
        self.assertEqual(len(example.state_vector), 64)
        self.assertEqual(len(example.next_state_vector), 64)
        self.assertEqual(len(example.action_vector), 32)
        self.assertEqual(example.state_delta["url_changed"], 1.0)
        self.assertEqual(example.state_delta["target_available"], 1.0)
        self.assertEqual(example.task_signals["terminal"], 1.0)
        self.assertEqual(example.risks["success"], 1.0)
        self.assertEqual(example.label_source, "heuristic")

    def test_explicit_labels_override_heuristics(self) -> None:
        record = sample_record()
        record["labels"] = {"stalled": True, "task_success": False}
        example = canonicalize_transition(record)
        self.assertEqual(example.risks["stalled"], 1.0)
        self.assertEqual(example.risks["success"], 0.0)
        self.assertEqual(example.label_source, "provided")

    def test_counterfactual_metadata_is_preserved(self) -> None:
        record = sample_record()
        record["metadata"] = {
            "counterfactual_pair_id": "pair-1",
            "counterfactual_group_id": "group-1",
            "counterfactual_role": "counterfactual",
            "intervention": "visible wrong target",
            "intervention_type": "hard_wrong_target",
        }
        example = canonicalize_transition(record)
        self.assertEqual(example.metadata["counterfactual_pair_id"], "pair-1")
        self.assertEqual(example.metadata["counterfactual_role"], "counterfactual")
        self.assertEqual(example.metadata["counterfactual_group_id"], "group-1")
        self.assertEqual(example.metadata["intervention_type"], "hard_wrong_target")

    def test_terminal_zero_reward_is_observed_severe_failure(self) -> None:
        record = sample_record()
        record["reward"] = 0.0
        example = canonicalize_transition(record)
        self.assertEqual(example.risks["success"], 0.0)
        self.assertEqual(example.risks["severe_failure"], 1.0)

    def test_human_review_provenance_is_preserved(self) -> None:
        record = sample_record()
        record["label_source"] = "human_verified"
        record["metadata"] = {
            "human_review": {
                "review_schema_version": 1,
                "reviewer": "reviewer-a",
                "reviewed_at_utc": "2026-08-09T00:00:00+00:00",
                "notes": "checked against the final page",
            }
        }
        example = canonicalize_transition(record)
        self.assertEqual(example.label_source, "human_verified")
        self.assertEqual(example.metadata["human_review"]["reviewer"], "reviewer-a")


if __name__ == "__main__":
    unittest.main()
