"""Launcher paging policy for AndroidWorld open-app tasks.

Some launcher apps (e.g. Calendar) are not on the default home page and can
only be reached through the app drawer.  This opt-in policy finds the app
button on the visible page and, when absent, opens the app drawer and scrolls
it until the exact label is found.  Decisions are auditable
(mode="launcher_app").
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from .reactive_agent import ElementRef, parse_elements


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", (text or "").lower())


class LauncherAppPolicy:
    """Rule-based app-finding policy for the Android launcher."""

    policy_name = "launcher_app_paging_v1"

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._drawer_opened = False
        self._drawer_scrolls = 0
        self._clicked_bid: str | None = None

    def decide(self, state: Mapping[str, Any], label: str) -> dict[str, Any] | None:
        url = str(state.get("url") or "")
        if "nexuslauncher" not in url:
            return None

        elements = parse_elements(str((state.get("axtree") or {}).get("text") or ""))
        target = _normalize(label)

        for element in elements:
            if element.role in ("button", "link") and _normalize(element.name) == target:
                if element.bid == self._clicked_bid:
                    return {
                        "action": "noop()",
                        "mode": "launcher_app",
                        "target": f"settling:{element.name}",
                    }
                self._clicked_bid = element.bid
                return {
                    "action": f'click("{element.bid}", "left")',
                    "mode": "launcher_app",
                    "target": f"button:{element.name}",
                }

        if self._clicked_bid is not None:
            return {
                "action": "noop()",
                "mode": "launcher_app",
                "target": "settling",
            }

        if self._drawer_opened:
            if self._drawer_scrolls < 5:
                self._drawer_scrolls += 1
                return {
                    "action": "scroll(0, 600)",
                    "mode": "launcher_app",
                    "target": f"drawer_scroll:{self._drawer_scrolls}",
                }
            return None

        # Open the app drawer with an upward swipe and look for the app there.
        self._drawer_opened = True
        return {
            "action": "scroll(0, -600)",
            "mode": "launcher_app",
            "target": "open_drawer",
        }
