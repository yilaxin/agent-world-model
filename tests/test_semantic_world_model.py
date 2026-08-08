from __future__ import annotations

import json
import unittest

from agent_world_model.semantic_world_model import (
    LLMSemanticWorldModel,
    parse_semantic_prediction,
)


class SemanticWorldModelTests(unittest.TestCase):
    def test_strict_json_output_is_parsed(self) -> None:
        payload = {
            "next_page_type": "search_results",
            "state_changes": ["url_changed"],
            "progress": 0.5,
            "invalid_action_probability": 0.1,
            "risk_probability": 0.2,
            "terminal_probability": 0.0,
            "success_probability": 0.1,
            "confidence": 0.8,
            "rationale": "The query is expected to submit.",
        }
        result = parse_semantic_prediction(json.dumps(payload))
        self.assertEqual(result.next_page_type, "search_results")

    def test_invalid_probability_is_rejected(self) -> None:
        payload = {
            "next_page_type": "other",
            "state_changes": [],
            "progress": 0,
            "invalid_action_probability": 2,
            "risk_probability": 0,
            "terminal_probability": 0,
            "success_probability": 0,
            "confidence": 0,
        }
        with self.assertRaises(ValueError):
            parse_semantic_prediction(json.dumps(payload))

    def test_provider_neutral_backend_receives_structured_prompt(self) -> None:
        captured = {}

        def complete(*, system: str, user: str) -> str:
            captured["system"] = system
            captured["user"] = json.loads(user)
            return json.dumps(
                {
                    "next_page_type": "other",
                    "state_changes": [],
                    "progress": 0,
                    "invalid_action_probability": 0,
                    "risk_probability": 0,
                    "terminal_probability": 0,
                    "success_probability": 0,
                    "confidence": 0.5,
                    "rationale": "uncertain",
                }
            )

        model = LLMSemanticWorldModel(complete)
        model.predict(
            instruction="Click submit",
            state={"url": "https://example.test"},
            action='click("1", "left")',
        )
        self.assertEqual(captured["user"]["proposed_action"], 'click("1", "left")')
        self.assertIn("one-step world model", captured["system"])


if __name__ == "__main__":
    unittest.main()
