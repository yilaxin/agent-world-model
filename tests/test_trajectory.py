from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent_world_model.trajectory import TrajectoryLogger, load_trajectory


class TrajectoryLoggerTests(unittest.TestCase):
    def test_complete_transition_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "episode.jsonl"
            with TrajectoryLogger(
                path,
                env_id="browsergym/miniwob.click-test",
                seed=7,
                run_id="testrun",
            ) as logger:
                logger.record_transition(
                    state={"state_id": "before", "url": "page-a"},
                    action='click("13", "left")',
                    next_state={"state_id": "after", "url": "page-b"},
                    reward=1.0,
                    terminated=True,
                    truncated=False,
                    info={"answer": "ok"},
                    metadata={"counterfactual_pair_id": "pair-7"},
                )

            records = load_trajectory(path)
            self.assertEqual(len(records), 1)
            record = records[0]
            self.assertEqual(record["state"]["state_id"], "before")
            self.assertEqual(record["action"], 'click("13", "left")')
            self.assertEqual(record["next_state"]["state_id"], "after")
            self.assertEqual(record["reward"], 1.0)
            self.assertTrue(record["terminated"])
            self.assertFalse(record["truncated"])
            self.assertTrue(record["done"])
            self.assertEqual(record["metadata"]["counterfactual_pair_id"], "pair-7")

    def test_large_arrays_are_replaced_by_metadata(self) -> None:
        class FakeArray:
            shape = (720, 1280, 3)
            dtype = "uint8"
            size = 720 * 1280 * 3

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "episode.jsonl"
            with TrajectoryLogger(path, env_id="test", seed=0) as logger:
                logger.record_transition(
                    state={"state_id": "a"},
                    action="noop()",
                    next_state={"state_id": "b"},
                    reward=0,
                    terminated=False,
                    truncated=False,
                    info={"screenshot": FakeArray()},
                )
            screenshot = load_trajectory(path)[0]["info"]["screenshot"]
            self.assertTrue(screenshot["__array_metadata__"])
            self.assertFalse(screenshot["stored"])

    def test_encoder_vector_is_not_truncated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "episode.jsonl"
            vector = [0.0] * 512
            vector[17] = 1.0
            with TrajectoryLogger(path, env_id="test", seed=0) as logger:
                logger.record_transition(
                    state={"state_id": "a"},
                    action="noop()",
                    next_state={"state_id": "b"},
                    reward=0,
                    terminated=False,
                    truncated=False,
                    encoded_state={"dimensions": 512, "vector": vector},
                    encoded_next_state={"dimensions": 512, "vector": vector},
                    decision={"action_type": "noop"},
                )
            record = load_trajectory(path)[0]
            self.assertEqual(record["schema_version"], 2)
            self.assertEqual(len(record["encoded_state"]["vector"]), 512)
            self.assertEqual(len(record["encoded_next_state"]["vector"]), 512)


if __name__ == "__main__":
    unittest.main()
