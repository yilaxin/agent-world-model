"""A small, auditable ReAct-style policy for phase-one browser baselines."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, Mapping, Sequence

if TYPE_CHECKING:
    from .state import StateSnapshot


_ELEMENT_RE = re.compile(
    r"""^\s*\[([^\]]+)\]\s+([A-Za-z][\w-]*)(?:\s+['"]([^'"]*)['"])?(.*)$"""
)
_WORD_RE = re.compile(r"[\w.-]+", re.UNICODE)
_INPUT_WORDS = re.compile(
    r"\b(?:enter|type|input|fill|write)\b|输入|填写|键入", re.IGNORECASE
)
_BACK_WORDS = re.compile(
    r"\b(?:go\s+back|back\s+to|previous\s+page)\b|返回|上一页", re.IGNORECASE
)
_SCROLL_WORDS = re.compile(
    r"\b(?:scroll|page\s+down|page\s+up)\b|滚动|向下|向上", re.IGNORECASE
)
_UP_WORDS = re.compile(r"\b(?:up|above|top)\b|向上|顶部", re.IGNORECASE)
_CLICK_WORDS = re.compile(
    r"\b(?:click|open|choose|select|press)\b|点击|打开|选择", re.IGNORECASE
)
_ROLE_PRIORITY = {
    "button": 30,
    "link": 24,
    "textbox": 20,
    "searchbox": 20,
    "combobox": 18,
    "checkbox": 16,
    "radio": 16,
    "option": 14,
    "menuitem": 14,
    "tab": 14,
}
_INPUT_ROLES = {"textbox", "searchbox", "combobox"}
_CLICK_ROLES = {
    "button",
    "link",
    "checkbox",
    "radio",
    "option",
    "menuitem",
    "tab",
}


@dataclass(frozen=True)
class ElementRef:
    bid: str
    role: str
    name: str
    raw_line: str
    depth: int = 0


@dataclass(frozen=True)
class ActionDecision:
    """One auditable reactive decision."""

    action: str
    action_type: str
    rationale: str
    target_bid: str = ""
    target_name: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _snapshot_value(state: StateSnapshot | Mapping[str, Any], key: str) -> Any:
    if isinstance(state, Mapping):
        return state.get(key)
    return getattr(state, key, None)


def _axtree_text(state: StateSnapshot | Mapping[str, Any]) -> str:
    value = _snapshot_value(state, "axtree")
    if isinstance(value, Mapping):
        return str(value.get("text", ""))
    return str(getattr(value, "text", "") or "")


def parse_elements(axtree_text: str) -> list[ElementRef]:
    """Extract BrowserGym element IDs, roles and accessible names."""

    elements = []
    for line in axtree_text.splitlines():
        match = _ELEMENT_RE.match(line)
        if not match:
            continue
        elements.append(
            ElementRef(
                bid=match.group(1),
                role=match.group(2).lower(),
                name=match.group(3) or "",
                raw_line=line.strip(),
                depth=max(0, (len(line) - len(line.lstrip())) // 2),
            )
        )
    return elements


def _json_arg(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _goal_tokens(goal: str) -> set[str]:
    ignored = {
        "the",
        "a",
        "an",
        "to",
        "into",
        "in",
        "on",
        "please",
        "click",
        "open",
        "enter",
        "type",
        "input",
        "fill",
        "button",
        "link",
        "textbox",
        "field",
        "text",
    }
    return {
        token.lower()
        for token in _WORD_RE.findall(goal)
        if len(token) > 1 and token.lower() not in ignored
    }


def _extract_input_value(goal: str) -> str:
    quoted = re.findall(r"""["'“”‘’]([^"'“”‘’]+)["'“”‘’]""", goal)
    if quoted:
        return quoted[0].strip()
    patterns = [
        r"\b(?:enter|type|input|fill|write)\s+(.+?)\s+(?:into|in)\b",
        r"(?:输入|填写|键入)\s*(.+?)(?:到|进|至)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, goal, re.IGNORECASE)
        if match:
            return match.group(1).strip(" .。")
    return ""


def _best_element(
    elements: Sequence[ElementRef],
    *,
    goal: str,
    allowed_roles: set[str],
    history: Sequence[str],
) -> ElementRef | None:
    candidates = [element for element in elements if element.role in allowed_roles]
    if not candidates:
        return None
    terms = _goal_tokens(goal)

    def score(element: ElementRef) -> tuple[int, int, str]:
        name_tokens = _goal_tokens(element.name)
        overlap = len(terms & name_tokens)
        repeated = any(
            f'"{element.bid}"' in action or f"'{element.bid}'" in action
            for action in history[-5:]
        )
        value = 100 * overlap + _ROLE_PRIORITY.get(element.role, 0)
        if element.name and element.name.lower() in goal.lower():
            value += 80
        if repeated:
            value -= 120
        return value, -len(element.name), element.bid

    return max(candidates, key=score)


class ReactiveAgent:
    """Choose one BrowserGym action from the current structured state.

    The policy is intentionally rule-based: it provides a reproducible baseline
    and a stable trajectory producer before any learned world model is added.
    """

    policy_name = "reactive_rules_v1"

    def decide(
        self,
        state: StateSnapshot | Mapping[str, Any],
        recent_actions: Sequence[str] = (),
        *,
        direct_answer: str | None = None,
    ) -> ActionDecision:
        goal = str(_snapshot_value(state, "goal") or "")
        elements = parse_elements(_axtree_text(state))

        if direct_answer is not None:
            return ActionDecision(
                action=f"send_msg_to_user({_json_arg(str(direct_answer))})",
                action_type="answer",
                rationale="Use the fixed smoke-task answer to exercise the official evaluator.",
                confidence=1.0,
            )

        if _BACK_WORDS.search(goal):
            return ActionDecision(
                action="go_back()",
                action_type="back",
                rationale="The instruction explicitly requests returning to the previous page.",
                confidence=0.98,
            )

        if _SCROLL_WORDS.search(goal):
            delta = -600 if _UP_WORDS.search(goal) else 600
            return ActionDecision(
                action=f"scroll(0, {delta})",
                action_type="scroll",
                rationale="The requested content requires a vertical page movement.",
                confidence=0.95,
            )

        if _INPUT_WORDS.search(goal):
            target = _best_element(
                elements,
                goal=goal,
                allowed_roles=_INPUT_ROLES,
                history=recent_actions,
            )
            value = _extract_input_value(goal)
            if target is not None and value:
                return ActionDecision(
                    action=f"fill({_json_arg(target.bid)}, {_json_arg(value)})",
                    action_type="input",
                    rationale="Match the requested text value to the visible input control.",
                    target_bid=target.bid,
                    target_name=target.name,
                    confidence=0.92,
                )

        target = _best_element(
            elements,
            goal=goal,
            allowed_roles=_CLICK_ROLES,
            history=recent_actions,
        )
        if target is not None and (_CLICK_WORDS.search(goal) or len(elements) == 1):
            return ActionDecision(
                action=f"click({_json_arg(target.bid)}, \"left\")",
                action_type="click",
                rationale="Choose the visible interactive element with the best task overlap.",
                target_bid=target.bid,
                target_name=target.name,
                confidence=0.88,
            )

        if target is not None:
            return ActionDecision(
                action=f"click({_json_arg(target.bid)}, \"left\")",
                action_type="click",
                rationale="No explicit verb matched; use the highest-scoring untried control.",
                target_bid=target.bid,
                target_name=target.name,
                confidence=0.55,
            )

        return ActionDecision(
            action="scroll(0, 600)",
            action_type="scroll",
            rationale="No actionable element is visible; reveal more page content.",
            confidence=0.35,
        )
