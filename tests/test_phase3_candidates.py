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

    def test_validation_rejects_multi_action_payloads(self) -> None:
        self.assertFalse(
            validate_action('click("11") goto("https://example.invalid")', {"11"})[0]
        )

    def test_disabled_controls_are_not_click_candidates(self) -> None:
        state = {
            "goal": 'Search for "usb wifi"',
            "axtree": {
                "text": (
                    "RootWebArea 'Shop'\n"
                    "  [386] combobox 'Search', clickable\n"
                    "  [391] button 'Search', disabled=True"
                )
            },
        }
        actions = [
            row.action for row in AXTreeCandidateGenerator(max_candidates=6).generate(state)
        ]
        self.assertNotIn('click("391", "left")', actions)

    def test_unrequested_logout_is_removed_from_candidate_pool(self) -> None:
        state = {
            "goal": "Change the delivery address for my most recent order.",
            "axtree": {
                "text": (
                    "RootWebArea 'Shop'\n"
                    "  [227] link 'My Account', clickable\n"
                    "  [231] link 'Sign Out', clickable"
                )
            },
        }
        rows = AXTreeCandidateGenerator(max_candidates=6).generate(state)
        self.assertIn('click("227", "left")', [row.action for row in rows])
        self.assertNotIn('click("231", "left")', [row.action for row in rows])

    def test_recent_generic_action_is_suppressed(self) -> None:
        rows = AXTreeCandidateGenerator(max_candidates=6).generate(
            STATE, ('click("13", "left")',)
        )
        self.assertNotIn('click("13", "left")', [row.action for row in rows])

    def test_learned_alignment_cannot_erase_observed_semantic_match(self) -> None:
        class FlatAlignment:
            def score(self, state, action, recent_actions):
                return 0.57, {"learned": True}

        state = {
            "goal": "Change my account address.",
            "axtree": {
                "text": (
                    "RootWebArea 'Shop'\n"
                    "  [227] link 'My Account', clickable\n"
                    "  [618] link 'Sports & Outdoors', clickable"
                )
            },
        }
        rows = AXTreeCandidateGenerator(
            max_candidates=4, alignment_scorer=FlatAlignment()
        ).generate(state)
        by_action = {row.action: row for row in rows}
        self.assertGreater(
            by_action['click("227", "left")'].structure_score,
            by_action['click("618", "left")'].structure_score,
        )
        self.assertEqual(
            by_action['click("227", "left")'].metadata["structure_components"][
                "combined_by"
            ],
            "max_preserve_observed_semantics",
        )

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

    def test_webarena_forum_query_is_generated_and_submitted(self) -> None:
        state = {
            "goal": "Tell me the count for the user on the Showerthoughts forum.",
            "axtree": {
                "text": (
                    "RootWebArea 'Postmill'\n"
                    "  [54] searchbox 'Search query', clickable\n"
                    "  [42] link 'Forums', clickable"
                )
            },
        }
        generator = AXTreeCandidateGenerator(max_candidates=6)
        initial = generator.generate(state)
        query = next(
            row
            for row in initial
            if row.action == 'fill("54", "Showerthoughts")'
        )
        self.assertEqual(query.source, "task_query")
        self.assertGreaterEqual(query.structure_score, 0.98)
        follow_up = generator.generate(
            state, ('fill("54", "Showerthoughts")',)
        )
        self.assertIn(
            'keyboard_press("Enter")', [row.action for row in follow_up]
        )


if __name__ == "__main__":
    unittest.main()
