from __future__ import annotations

import json
import unittest

from agent_world_model.phase3_candidates import (
    AXTreeCandidateGenerator,
    LLMConstrainedCandidateGenerator,
    LLMCandidateGenerator,
    structural_consistency,
    validate_action,
)


STATE = {
    "goal": 'Enter "Ada" into the name field and click Submit.',
    "axtree": {
        "text": (
            "RootWebArea 'Form'\n"
            "  [11] textbox 'name', clickable\n"
            "  [12] button 'Submit', clickable\n"
            "  [13] button 'Cancel', clickable"
        )
    },
}


class CandidateGenerationTests(unittest.TestCase):
    def test_generator_is_bounded_valid_and_deduplicated(self) -> None:
        candidates = AXTreeCandidateGenerator(max_candidates=6).generate(STATE)
        actions = [candidate.action for candidate in candidates]
        self.assertLessEqual(len(candidates), 6)
        self.assertEqual(len(actions), len(set(actions)))
        self.assertIn('fill("11", "Ada")', actions)
        self.assertIn('click("12", "left")', actions)
        self.assertTrue(all(validate_action(action, {"11", "12", "13"})[0] for action in actions))

    def test_structure_suppresses_missing_target(self) -> None:
        good, components = structural_consistency(
            STATE["goal"], STATE["axtree"]["text"], 'click("12", "left")'
        )
        bad, bad_components = structural_consistency(
            STATE["goal"], STATE["axtree"]["text"], 'click("999", "left")'
        )
        self.assertGreater(good, bad)
        self.assertTrue(components["target_visible"])
        self.assertFalse(bad_components["target_visible"])

    def test_llm_adapter_requires_strict_json_and_visible_targets(self) -> None:
        payload = json.dumps(
            {
                "candidates": [
                    {"action": 'click("12", "left")', "rationale": "submit"}
                ]
            }
        )
        rows = LLMCandidateGenerator(lambda _: payload).generate(STATE)
        self.assertEqual(rows[0].source, "llm")
        with self.assertRaises(ValueError):
            LLMCandidateGenerator(
                lambda _: json.dumps(
                    {"candidates": [{"action": 'click("999", "left")'}]}
                )
            ).generate(STATE)

    def test_constrained_llm_selects_only_from_valid_pool(self) -> None:
        generator = LLMConstrainedCandidateGenerator(
            lambda _: json.dumps({"indices": [1, 0]}),
            max_candidates=2,
            pool_size=6,
        )
        rows = generator.generate(STATE)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row.source == "llm_constrained" for row in rows))
        self.assertTrue(all(validate_action(row.action, {"11", "12", "13"})[0] for row in rows))


if __name__ == "__main__":
    unittest.main()
