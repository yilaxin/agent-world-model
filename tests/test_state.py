from __future__ import annotations

import unittest

from agent_world_model.state import prune_text


class PruneTextTests(unittest.TestCase):
    def test_small_text_is_preserved(self) -> None:
        text = "RootWebArea 'Demo'\n  [12] button 'Submit', clickable"
        result = prune_text(
            text,
            goal="Submit the form",
            kind="axtree",
            max_chars=1_000,
            max_lines=20,
            max_line_chars=200,
            context_lines=1,
        )
        self.assertIn("Submit", result.text)
        self.assertFalse(result.truncated)

    def test_interactive_and_goal_lines_survive_pruning(self) -> None:
        lines = ["RootWebArea 'Demo'"]
        lines.extend(f"  StaticText 'unrelated row {index}'" for index in range(80))
        lines.append("  [99] button 'Open books forum', clickable")
        result = prune_text(
            "\n".join(lines),
            goal="Open the books forum",
            kind="axtree",
            max_chars=500,
            max_lines=8,
            max_line_chars=120,
            context_lines=1,
        )
        self.assertTrue(result.truncated)
        self.assertLessEqual(result.kept_line_count, 8)
        self.assertLessEqual(result.kept_char_count, 500)
        self.assertIn("RootWebArea", result.text)
        self.assertIn("Open books forum", result.text)

    def test_heavy_dom_attributes_are_removed(self) -> None:
        text = (
            '<button bid="12" class="many utility classes" '
            'style="width: 100px" data-test="x" clickable="">Submit</button>'
        )
        result = prune_text(
            text,
            goal="Submit",
            kind="dom",
            max_chars=1_000,
            max_lines=20,
            max_line_chars=300,
            context_lines=1,
        )
        self.assertNotIn("class=", result.text)
        self.assertNotIn("style=", result.text)
        self.assertNotIn("data-test=", result.text)
        self.assertIn('bid="12"', result.text)
        self.assertIn("Submit", result.text)


if __name__ == "__main__":
    unittest.main()
