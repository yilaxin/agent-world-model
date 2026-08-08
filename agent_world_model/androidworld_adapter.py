"""Small, dependency-free AndroidWorld migration boundary.

The adapter translates Android accessibility observations into the state shape
used by the world-model Agent and maps its bounded action language back to
coordinate-based Android actions.  It deliberately does not hide emulator or
ADB availability; the preflight script reports those external requirements.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping


_ACTION_RE = re.compile(r"^\s*([A-Za-z_][\w]*)\s*\((.*)\)\s*$", re.DOTALL)
_QUOTED_RE = re.compile(r'''["']([^"']*)["']''')


@dataclass(frozen=True)
class AndroidElement:
    bid: str
    role: str
    name: str
    bounds: tuple[int, int, int, int]
    editable: bool = False


def _walk_nodes(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for key in ("children", "nodes"):
            children = value.get(key)
            if isinstance(children, list):
                for child in children:
                    yield from _walk_nodes(child)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_nodes(item)


def _bounds(value: Any) -> tuple[int, int, int, int] | None:
    if isinstance(value, Mapping):
        keys = ("left", "top", "right", "bottom")
        if all(key in value for key in keys):
            return tuple(int(value[key]) for key in keys)  # type: ignore[return-value]
    if isinstance(value, (list, tuple)) and len(value) == 4:
        return tuple(int(item) for item in value)  # type: ignore[return-value]
    if isinstance(value, str):
        numbers = [int(item) for item in re.findall(r"-?\d+", value)]
        if len(numbers) >= 4:
            return tuple(numbers[:4])  # type: ignore[return-value]
    return None


def elements_from_observation(observation: Mapping[str, Any]) -> list[AndroidElement]:
    source = observation.get("ui_tree") or observation.get("accessibility_tree") or observation.get("nodes") or []
    result: list[AndroidElement] = []
    for index, node in enumerate(_walk_nodes(source)):
        bounds = _bounds(node.get("bounds") or node.get("bounds_in_screen"))
        if bounds is None:
            continue
        name = str(node.get("text") or node.get("content_description") or node.get("content-desc") or "")
        class_name = str(node.get("class") or node.get("class_name") or "").lower()
        editable = bool(node.get("editable") or "edittext" in class_name)
        clickable = bool(node.get("clickable", False))
        role = "textbox" if editable else "button" if clickable else "text"
        stable = str(node.get("resource_id") or node.get("resource-id") or node.get("id") or f"node-{index}")
        bid = "aw-" + hashlib.sha256(f"{stable}:{bounds}".encode()).hexdigest()[:10]
        result.append(AndroidElement(bid=bid, role=role, name=name, bounds=bounds, editable=editable))
    return result


def adapt_android_observation(observation: Mapping[str, Any], *, goal: str) -> tuple[dict[str, Any], dict[str, tuple[int, int, int, int]]]:
    elements = elements_from_observation(observation)
    axtree = "\n".join(
        f'[{item.bid}] {item.role} {json.dumps(item.name, ensure_ascii=False)}'
        for item in elements
    )
    package = str(observation.get("package") or observation.get("package_name") or "unknown")
    activity = str(observation.get("activity") or observation.get("activity_name") or "")
    state = {
        "goal": goal,
        "url": f"android://{package}/{activity.lstrip('/')}",
        "title": activity or package,
        "axtree": {"text": axtree},
        "dom": {"text": json.dumps(observation.get("ui_tree") or observation.get("nodes") or [], ensure_ascii=False, sort_keys=True)},
        "last_action_error": str(observation.get("last_action_error") or ""),
        "platform": "androidworld",
    }
    return state, {item.bid: item.bounds for item in elements}


def map_agent_action(action: str, bounds_by_bid: Mapping[str, tuple[int, int, int, int]]) -> list[dict[str, Any]]:
    match = _ACTION_RE.match(action)
    if not match:
        raise ValueError(f"invalid action syntax: {action}")
    action_type, arguments = match.group(1).lower(), match.group(2)
    quoted = _QUOTED_RE.findall(arguments)
    if action_type in {"click", "fill", "type", "select_option"}:
        if not quoted or quoted[0] not in bounds_by_bid:
            raise ValueError("target element is absent from the Android accessibility tree")
        left, top, right, bottom = bounds_by_bid[quoted[0]]
        tap = {"action_type": "click", "x": (left + right) // 2, "y": (top + bottom) // 2}
        if action_type in {"fill", "type"}:
            if len(quoted) < 2:
                raise ValueError("text action needs a value")
            return [tap, {"action_type": "input_text", "text": quoted[1], "clear": action_type == "fill"}]
        return [tap]
    if action_type == "go_back":
        return [{"action_type": "press_key", "key": "BACK"}]
    if action_type == "press":
        return [{"action_type": "press_key", "key": quoted[0] if quoted else arguments.strip()}]
    if action_type == "scroll":
        numbers = [int(item) for item in re.findall(r"-?\d+", arguments)]
        dx, dy = (numbers + [0, 600])[:2]
        return [{"action_type": "scroll", "direction": "down" if dy > 0 else "up", "magnitude": abs(dy), "dx": dx}]
    if action_type == "noop":
        return [{"action_type": "wait"}]
    raise ValueError(f"unsupported AndroidWorld action type: {action_type}")
