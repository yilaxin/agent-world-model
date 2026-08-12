"""Unit tests for the launcher app-finding policy."""

from __future__ import annotations

import unittest

from agent_world_model.launcher_app_policy import LauncherAppPolicy


def _launcher_state(lines: list[str]) -> dict[str, object]:
    return {
        "url": "android://com.google.android.apps.nexuslauncher/launcher",
        "axtree": {"text": "\n".join(lines)},
    }


class LauncherAppPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = LauncherAppPolicy()

    def test_clicks_app_on_home_page(self) -> None:
        state = _launcher_state(['[aw-c] button "Chrome"', '[aw-m] button "Messages"'])
        decision = self.policy.decide(state, "Chrome")
        self.assertEqual(decision["action"], 'click("aw-c", "left")')

    def test_opens_drawer_when_app_absent(self) -> None:
        state = _launcher_state(['[aw-m] button "Messages"'])
        decision = self.policy.decide(state, "Calendar")
        self.assertEqual(decision["action"], "scroll(0, -600)")
        self.assertEqual(decision["target"], "open_drawer")

    def test_finds_app_in_drawer_after_scroll(self) -> None:
        state = _launcher_state(['[aw-m] button "Messages"'])
        self.policy.decide(state, "Calendar")  # opens drawer
        state = _launcher_state(['[aw-a] button "Camera"', '[aw-b] button "Calendar"'])
        decision = self.policy.decide(state, "Calendar")
        self.assertEqual(decision["action"], 'click("aw-b", "left")')

    def test_noop_after_click(self) -> None:
        state = _launcher_state(['[aw-c] button "Chrome"'])
        self.policy.decide(state, "Chrome")
        decision = self.policy.decide(state, "Chrome")
        self.assertEqual(decision["action"], "noop()")

    def test_ignores_non_launcher_screens(self) -> None:
        state = {
            "url": "android://com.android.chrome/activity",
            "axtree": {"text": '[aw-x] button "Chrome"'},
        }
        self.assertIsNone(self.policy.decide(state, "Chrome"))


if __name__ == "__main__":
    unittest.main()
