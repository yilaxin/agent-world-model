from __future__ import annotations

import math
import unittest

from agent_world_model.encoder import EncoderConfig, StateEncoderV1


class StateEncoderV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = {
            "state_id": "state-1",
            "goal": "Click Submit",
            "url": "http://example.test/form",
            "title": "Form",
            "tabs": [{"index": 0, "title": "Form", "url": "http://example.test/form"}],
            "axtree": {"text": "RootWebArea 'Form'\n  [7] button 'Submit'"},
            "dom": {"text": '<button bid="7">Submit</button>'},
        }

    def test_encoder_is_deterministic_and_normalized(self) -> None:
        encoder = StateEncoderV1(EncoderConfig(dimensions=128))
        first = encoder.encode(self.state, ["noop()"])
        second = encoder.encode(self.state, ["noop()"])
        self.assertEqual(first.encoding_id, second.encoding_id)
        self.assertEqual(first.vector, second.vector)
        self.assertEqual(len(first.vector), 128)
        self.assertAlmostEqual(
            math.sqrt(sum(value * value for value in first.vector)),
            1.0,
            places=6,
        )

    def test_only_the_latest_five_actions_are_encoded(self) -> None:
        encoder = StateEncoderV1(EncoderConfig(dimensions=64, recent_action_count=5))
        encoded = encoder.encode(
            self.state,
            [f"action-{index}" for index in range(7)],
        )
        self.assertEqual(
            encoded.recent_actions,
            ["action-2", "action-3", "action-4", "action-5", "action-6"],
        )
        self.assertNotIn("action-0", encoded.structured_text)
        self.assertIn("[TASK]", encoded.structured_text)
        self.assertIn("[URL]", encoded.structured_text)
        self.assertIn("[AXTREE]", encoded.structured_text)
        self.assertIn("[DOM]", encoded.structured_text)


if __name__ == "__main__":
    unittest.main()
