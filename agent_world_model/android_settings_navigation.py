"""Sequence-level Settings navigation policy for AndroidWorld tasks.

Adds the explicit multi-step plan for settings goals:

    open Settings -> tap the matching section row -> tap the target switch.

The policy is opt-in and auditable (decisions carry mode="settings_sequence").
When the current screen cannot be recognised, it returns None and the caller
delegates to the base policy (reactive or phase-three planner).
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .reactive_agent import ElementRef, parse_elements


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", (text or "").lower())


class SettingsNavigationPolicy:
    """Rule-based sequence navigation for Android Settings."""

    policy_name = "settings_sequence_v1"

    TARGET_ALIASES = {
        "wifi": ("wifi", "wi-fi", "wireless"),
    }

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        # Bids are stable per screen layout; remember which switch we already
        # toggled so a later step does not flip it back.
        self._toggled_bids: set[str] = set()
        # Remember the section row we just tapped so a stale accessibility tree
        # does not make us tap the same coordinates twice and overshoot.
        self._last_section_bid: str | None = None
        # open_app("settings") resumes the last Settings activity; unknown
        # sub-screens are unwound with BACK until a recognisable screen shows.
        self._consecutive_backs = 0

    def decide(
        self,
        state: Mapping[str, Any],
        goal: str,
        recent_actions: Sequence[str] = (),
    ) -> dict[str, Any] | None:
        goal_lower = (goal or "").lower()
        target = "wifi" if ("wifi" in goal_lower or "wi-fi" in goal_lower) else None
        if target is None:
            return None

        url = str(state.get("url") or "")
        if "com.android.settings" not in url:
            return {
                "action": 'open_app("settings")',
                "mode": "settings_sequence",
                "target": "settings",
            }

        elements = parse_elements(str((state.get("axtree") or {}).get("text") or ""))

        # Step 3: toggle the target switch when it is visible.
        for element in elements:
            is_exact_wifi_label = element.role == "text" and _normalize(element.name) == "wifi"
            if (
                element.role in ("switch", "button", "checkbox")
                or is_exact_wifi_label
            ) and self._is_target(element, target):
                if element.bid in self._toggled_bids:
                    return {
                        "action": "noop()",
                        "mode": "settings_sequence",
                        "target": f"toggled:{element.name}",
                    }
                self._toggled_bids.add(element.bid)
                self._consecutive_backs = 0
                return {
                    "action": f'tap_switch("{element.bid}")',
                    "mode": "settings_sequence",
                    "target": f"{element.role}:{element.name}",
                }

        # Step 2a: tap the "Network & internet" section row on the settings
        # home screen (both words must be present so subtitles like
        # "Mobile, Wi-Fi, hotspot" are not mistaken for it).
        for element in elements:
            if element.role in ("button", "link") and self._is_network_section(element):
                if element.bid == self._last_section_bid:
                    return {
                        "action": "noop()",
                        "mode": "settings_sequence",
                        "target": f"settling:{element.name}",
                    }
                self._last_section_bid = element.bid
                self._consecutive_backs = 0
                return {
                    "action": f'click("{element.bid}", "left")',
                    "mode": "settings_sequence",
                    "target": f"section:{element.name}",
                }

        # Step 2b: on the network sub-screen, tap the exact "Internet" row to
        # reach the Wi-Fi toggle (Android 13 nests it under Internet).
        for element in elements:
            name = _normalize(element.name)
            if element.role in ("button", "link") and name == "internet":
                if element.bid == self._last_section_bid:
                    return {
                        "action": "noop()",
                        "mode": "settings_sequence",
                        "target": f"settling:{element.name}",
                    }
                self._last_section_bid = element.bid
                self._consecutive_backs = 0
                return {
                    "action": f'click("{element.bid}", "left")',
                    "mode": "settings_sequence",
                    "target": f"section:{element.name}",
                }

        # Unwind unknown Settings sub-screens (e.g. a resumed Storage activity)
        # back to the Settings home.  Reset the counter whenever a recognised
        # screen emitted a decision above.
        if self._consecutive_backs >= 4:
            return None
        self._consecutive_backs += 1
        return {
            "action": "go_back()",
            "mode": "settings_sequence",
            "target": f"unwind:{self._consecutive_backs}",
        }

        return None

    def _is_target(self, element: ElementRef, target: str) -> bool:
        name = _normalize(element.name)
        if element.role == "switch":
            return any(alias in name for alias in self.TARGET_ALIASES[target])
        # For non-switch elements only an exact name counts, so rows like
        # "Wi-Fi turns back on automatically" are not treated as the toggle.
        return name == "wifi"

    def _is_network_section(self, element: ElementRef) -> bool:
        name = _normalize(element.name)
        return "network" in name and "internet" in name
