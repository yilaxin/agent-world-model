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


def _attribute(value: Any, *names: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        for name in names:
            if name in value:
                return value[name]
        return default
    for name in names:
        if hasattr(value, name):
            return getattr(value, name)
    return default


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
    if all(hasattr(value, key) for key in ("x_min", "y_min", "x_max", "y_max")):
        return (int(value.x_min), int(value.y_min), int(value.x_max), int(value.y_max))
    return None


def elements_from_observation(observation: Mapping[str, Any]) -> list[AndroidElement]:
    source = (
        observation.get("ui_tree")
        or observation.get("accessibility_tree")
        or observation.get("ui_elements")
        or observation.get("nodes")
        or []
    )
    result: list[AndroidElement] = []
    nodes: Iterable[Any] = _walk_nodes(source) if isinstance(source, (Mapping, list)) else []
    for index, node in enumerate(nodes):
        bounds = _bounds(_attribute(node, "bounds", "bounds_in_screen", "bbox_pixels", "bbox"))
        if bounds is None:
            continue
        name = str(_attribute(node, "text", "content_description", "content-desc", default="") or "")
        class_name = str(_attribute(node, "class", "class_name", default="") or "").lower()
        editable = bool(_attribute(node, "editable", "is_editable", default=False) or "edittext" in class_name)
        clickable = bool(_attribute(node, "clickable", "is_clickable", default=False))
        role = "textbox" if editable else "button" if clickable else "text"
        stable = str(_attribute(node, "resource_id", "resource-id", "resource_name", "id", default=f"node-{index}"))
        bid = "aw-" + hashlib.sha256(f"{stable}:{bounds}".encode()).hexdigest()[:10]
        result.append(AndroidElement(bid=bid, role=role, name=name, bounds=bounds, editable=editable))
    return result


def adapt_androidworld_state(state: Any, *, goal: str, activity: str = "") -> tuple[dict[str, Any], dict[str, tuple[int, int, int, int]]]:
    """Adapt an official ``android_world.env.interface.State`` instance.

    The import stays optional so the core project and its unit tests do not need
    the large AndroidWorld runtime.  Only the documented public State/UIElement
    attributes are consumed.
    """

    ui_elements = list(getattr(state, "ui_elements", []) or [])
    normalized = []
    for item in ui_elements:
        bounds = _bounds(_attribute(item, "bbox_pixels", "bbox"))
        normalized.append(
            {
                "resource_id": _attribute(item, "resource_id", "resource_name"),
                "text": _attribute(item, "text") or _attribute(item, "content_description"),
                "class_name": _attribute(item, "class_name"),
                "editable": bool(_attribute(item, "is_editable", default=False)),
                "clickable": bool(_attribute(item, "is_clickable", default=False)),
                "bounds": bounds,
                "package_name": _attribute(item, "package_name"),
            }
        )
    package = next((item["package_name"] for item in normalized if item.get("package_name")), "unknown")
    observation = {
        "package": package,
        "activity": activity,
        "ui_elements": normalized,
        "screenshot_shape": list(getattr(getattr(state, "pixels", None), "shape", ()) or ()),
    }
    return adapt_android_observation(observation, goal=goal)


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
        "url": f"android://{package}/{activity.lstrip('/.')}",
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
            return [tap, {"action_type": "input_text", "text": quoted[1], "clear_text": action_type == "fill"}]
        return [tap]
    if action_type == "go_back":
        return [{"action_type": "navigate_back"}]
    if action_type == "press":
        key = (quoted[0] if quoted else arguments.strip()).upper()
        supported = {"BACK": "navigate_back", "HOME": "navigate_home", "ENTER": "keyboard_enter"}
        if key not in supported:
            raise ValueError(f"unsupported AndroidWorld key: {key}")
        return [{"action_type": supported[key]}]
    if action_type == "scroll":
        numbers = [int(item) for item in re.findall(r"-?\d+", arguments)]
        dx, dy = (numbers + [0, 600])[:2]
        if abs(dx) > abs(dy):
            direction = "right" if dx > 0 else "left"
        else:
            direction = "down" if dy > 0 else "up"
        return [{"action_type": "scroll", "direction": direction}]
    if action_type == "noop":
        return [{"action_type": "wait"}]
    raise ValueError(f"unsupported AndroidWorld action type: {action_type}")
