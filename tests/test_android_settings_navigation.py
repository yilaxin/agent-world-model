"""Unit tests for the sequence-level Settings navigation policy."""

from __future__ import annotations

import unittest

from agent_world_model.android_settings_navigation import SettingsNavigationPolicy


def _state(url: str, axtree_lines: list[str]) -> dict[str, object]:
    return {"url": url, "axtree": {"text": "\n".join(axtree_lines)}}


class SettingsNavigationPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = SettingsNavigationPolicy()

    def test_opens_settings_from_launcher(self) -> None:
        state = _state(
            "android://com.google.android.apps.nexuslauncher/launcher",
            ['[aw-a] button "Chrome"'],
        )
        decision = self.policy.decide(state, "Turn wifi on.")
        self.assertEqual(decision["action"], 'open_app("settings")')

    def test_clicks_network_section_on_main_screen(self) -> None:
        state = _state(
            "android://com.android.settings/Settings",
            [
                '[aw-b] button "Network & internet"',
                '[aw-c] text "Mobile, Wi-Fi, hotspot"',
            ],
        )
        decision = self.policy.decide(state, "Turn wifi on.")
        self.assertEqual(decision["action"], 'click("aw-b", "left")')
        self.assertEqual(decision["target"], "section:Network & internet")

    def test_does_not_click_subtitle(self) -> None:
        state = _state(
            "android://com.android.settings/Settings",
            ['[aw-c] button "Mobile, Wi-Fi, hotspot"'],
        )
        decision = self.policy.decide(state, "Turn wifi on.")
        self.assertNotEqual(decision["action"], 'click("aw-c", "left")')
        # An unrecognised Settings screen is unwound instead of clicking noise.
        self.assertEqual(decision["action"], "go_back()")

    def test_clicks_internet_row_then_toggles_wifi(self) -> None:
        state = _state(
            "android://com.android.settings/SubSettings",
            ['[aw-i] button "Internet"'],
        )
        decision = self.policy.decide(state, "Turn wifi on.")
        self.assertEqual(decision["action"], 'click("aw-i", "left")')

        state = _state(
            "android://com.android.settings/SubSettings",
            ['[aw-w] button "Wi-Fi"'],
        )
        decision = self.policy.decide(state, "Turn wifi on.")
        self.assertEqual(decision["action"], 'tap_switch("aw-w")')

        decision = self.policy.decide(state, "Turn wifi on.")
        self.assertEqual(decision["action"], "noop()")

    def test_unwinds_unknown_settings_screen(self) -> None:
        state = _state(
            "android://com.android.settings/Settings$StorageUseActivity",
            ['[aw-x] text "Storage"'],
        )
        decision = self.policy.decide(state, "Turn wifi on.")
        self.assertEqual(decision["action"], "go_back()")


if __name__ == "__main__":
    unittest.main()
