"""Candidate-action generation and structural consistency for phase three.

The generator is deliberately provider-neutral.  A deterministic AXTree policy
keeps experiments reproducible, while :class:`LLMCandidateGenerator` accepts a
strict JSON-producing callable when an LLM/VLM backend is available.
"""

from __future__ import annotations

import ast
import json
import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Mapping, Sequence

from .phase2_schema import encode_action
from .reactive_agent import (
    ReactiveAgent,
    _CART_WORDS,
    _NO_SUBMIT_WORDS,
    _PRODUCT_VERBS,
    _WISHLIST_WORDS,
    _extract_product_phrase,
    _named_control,
    _page_contains,
    _prefixed_control,
    goal_conflicts_with_control,
    parse_elements,
)


_ALLOWED_ACTION_TYPES = {
    "click",
    "fill",
    "go_back",
    "keyboard_press",
    "noop",
    "press",
    "send_msg_to_user",
    "scroll",
    "select_option",
    "type",
}
_TARGETED_ACTION_TYPES = {"click", "fill", "select_option"}
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
_WORD_RE = re.compile(r"[\w.-]+", re.UNICODE)
_QUOTED_RE = re.compile(r'''["'“”‘’]([^"'“”‘’]+)["'“”‘’]''')
_INPUT_RE = re.compile(
    r"\b(?:enter|type|input|fill|write|search|password|username)\b|输入|填写|键入|搜索|密码|用户名",
    re.IGNORECASE,
)
_SCROLL_RE = re.compile(r"\b(?:scroll|below|down|above|up)\b|滚动|向下|向上", re.IGNORECASE)
_BACK_RE = re.compile(r"\b(?:go\s+back|back|previous\s+page)\b|返回|上一页", re.IGNORECASE)
_STOPWORDS = {
    "a", "an", "and", "button", "click", "field", "fill", "in", "into",
    "link", "on", "open", "please", "select", "text", "the", "to", "type",
}


_FORUM_QUERY_PATTERNS = (
    re.compile(
        r"\b(?:on|in|from)\s+(?:the\s+)?(?:r/)?([A-Za-z0-9_-]+)\s+(?:forum|subreddit)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:forum|subreddit)\s+[\"'](?:r/)?([^\"']+)[\"']",
        re.IGNORECASE,
    ),
    re.compile(r"\br/([A-Za-z0-9_-]+)\b", re.IGNORECASE),
)


def _snapshot_value(state: Mapping[str, Any] | Any, key: str) -> Any:
    if isinstance(state, Mapping):
        return state.get(key)
    return getattr(state, key, None)


def _nested_text(value: Any) -> str:
    if isinstance(value, Mapping):
        return str(value.get("text", ""))
    return str(getattr(value, "text", "") or value or "")


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in _WORD_RE.findall(text)
        if len(token) > 1 and token.lower() not in _STOPWORDS
    }


def _json_arg(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _input_value(goal: str) -> str:
    quoted = _QUOTED_RE.findall(goal)
    if quoted:
        return quoted[0].strip()
    patterns = (
        r"\b(?:enter|type|input|fill|write|search\s+for)\s+(.+?)\s+(?:into|in)\b",
        r"(?:输入|填写|键入|搜索)\s*(.+?)(?:到|进|至)",
    )
    for pattern in patterns:
        match = re.search(pattern, goal, re.IGNORECASE)
        if match:
            return match.group(1).strip(" .。")
    return ""


def _forum_query(goal: str) -> str:
    ordered = (
        _FORUM_QUERY_PATTERNS[1],
        _FORUM_QUERY_PATTERNS[0],
        *_FORUM_QUERY_PATTERNS[2:],
    )
    for pattern in ordered:
        match = pattern.search(goal)
        if match:
            forum = match.group(1).strip()
            if len(forum) >= 2 and forum.lower() not in {"a", "an", "the"}:
                return forum
    return ""


def validate_action(action: str, visible_element_ids: set[str] | None = None) -> tuple[bool, str]:
    """Validate the supported BrowserGym subset without executing an action."""

    try:
        parsed_ast = ast.parse(str(action).strip(), mode="eval")
    except SyntaxError:
        return False, "action must be one Python-style function call"
    if not isinstance(parsed_ast.body, ast.Call) or not isinstance(parsed_ast.body.func, ast.Name):
        return False, "action must be one Python-style function call"
    _, parsed = encode_action(action)
    action_type = parsed["action_type"]
    if action_type not in _ALLOWED_ACTION_TYPES:
        return False, f"unsupported action type: {action_type}"
    targets = parsed["target_element_ids"]
    if action_type in _TARGETED_ACTION_TYPES and not targets:
        return False, "targeted action has no element id"
    if (
        visible_element_ids is not None
        and action_type in _TARGETED_ACTION_TYPES
        and targets
    ):
        if any(target not in visible_element_ids for target in targets):
            return False, "target element is not visible in the current AXTree"
    return True, ""


@dataclass(frozen=True)
class CandidateAction:
    action: str
    action_type: str
    rationale: str
    source: str
    target_bid: str = ""
    target_name: str = ""
    structure_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def structural_consistency(
    goal: str,
    axtree_text: str,
    action: str,
) -> tuple[float, dict[str, Any]]:
    """Compute proposal-aligned task/element/action structural consistency.

    The score combines target visibility, action-role compatibility and semantic
    overlap between the task and accessible element name.  It is bounded to
    ``[0, 1]`` and exposes its components for auditing.
    """

    elements = {element.bid: element for element in parse_elements(axtree_text)}
    _, parsed = encode_action(action)
    action_type = parsed["action_type"]
    targets = parsed["target_element_ids"]
    goal_terms = _tokens(goal)

    if not targets:
        intent_match = 0.0
        if action_type == "scroll" and _SCROLL_RE.search(goal):
            intent_match = 1.0
        elif action_type == "go_back" and _BACK_RE.search(goal):
            intent_match = 1.0
        elif action_type in {"noop", "scroll"}:
            intent_match = 0.2
        score = 0.15 + 0.45 * intent_match
        return min(1.0, score), {
            "target_visible": None,
            "role_compatible": None,
            "semantic_overlap": 0.0,
            "intent_match": intent_match,
        }

    element = elements.get(targets[0])
    if element is None:
        return 0.0, {
            "target_visible": False,
            "role_compatible": False,
            "semantic_overlap": 0.0,
            "intent_match": 0.0,
        }

    compatible = (
        (action_type in {"fill", "type"} and element.role in _INPUT_ROLES)
        or (action_type == "click" and element.role in _CLICK_ROLES)
        or (action_type == "select_option" and element.role in {"combobox", "option"})
    )
    name_terms = _tokens(element.name)
    overlap = len(goal_terms & name_terms) / max(1, len(name_terms))
    exact_name = bool(element.name and element.name.lower() in goal.lower())
    semantic = max(overlap, 1.0 if exact_name else 0.0)
    score = 0.45 + 0.25 * float(compatible) + 0.30 * semantic
    return min(1.0, score), {
        "target_visible": True,
        "role_compatible": compatible,
        "semantic_overlap": semantic,
        "intent_match": 0.0,
        "target_role": element.role,
        "target_name": element.name,
    }


class AXTreeCandidateGenerator:
    """Generate a bounded, deterministic candidate set from visible controls."""

    generator_name = "axtree_structure_v2_task_query"

    def __init__(
        self,
        max_candidates: int = 8,
        alignment_scorer: Any | None = None,
        *,
        navigation_guard: bool = True,
    ) -> None:
        if not 2 <= max_candidates <= 32:
            raise ValueError("max_candidates must be in [2, 32]")
        self.max_candidates = max_candidates
        self.navigation_guard = bool(navigation_guard)
        self.reactive = ReactiveAgent(navigation_guard=self.navigation_guard)
        self.alignment_scorer = alignment_scorer

    def generate(
        self,
        state: Mapping[str, Any] | Any,
        recent_actions: Sequence[str] = (),
    ) -> list[CandidateAction]:
        goal = str(_snapshot_value(state, "goal") or "")
        current_url = str(_snapshot_value(state, "url") or "")
        axtree = _nested_text(_snapshot_value(state, "axtree"))
        elements = parse_elements(axtree)
        visible_ids = {element.bid for element in elements}
        raw: list[tuple[str, str, str, str, str]] = []
        forum_query = _forum_query(goal)

        baseline = self.reactive.decide(state, recent_actions)
        raw.append(
            (
                baseline.action,
                (
                    "task_query"
                    if forum_query
                    and baseline.action_type in {"input", "press"}
                    else "reactive"
                ),
                baseline.rationale,
                baseline.target_bid,
                baseline.target_name,
            )
        )

        # Product search / add-to-wish-list / add-to-cart flow (One Stop Market).
        lowered_goal = goal.casefold()
        product_phrase = _extract_product_phrase(goal)
        if product_phrase and _PRODUCT_VERBS.search(lowered_goal):
            if not _NO_SUBMIT_WORDS.search(goal):
                completion = self.reactive._completion_decision(goal, current_url, elements)
                if completion is not None and completion.action.startswith(
                    "send_msg_to_user("
                ):
                    raw.append(
                        (
                            completion.action,
                            "task_query",
                            completion.rationale,
                            "",
                            "Done",
                        )
                    )
            if _WISHLIST_WORDS.search(lowered_goal) or _CART_WORDS.search(lowered_goal):
                add_name = (
                    "Add to Wish List" if _WISHLIST_WORDS.search(lowered_goal) else "Add to Cart"
                )
                add_button = _named_control(elements, add_name) or _prefixed_control(
                    elements, add_name
                )
                if add_button is not None:
                    raw.append(
                        (
                            f"click({_json_arg(add_button.bid)}, \"left\")",
                            "task_query",
                            f"Add the visible product via {add_name}.",
                            add_button.bid,
                            add_button.name,
                        )
                    )
            searchboxes = [
                element for element in elements if element.role in _INPUT_ROLES
            ]
            if (
                recent_actions
                and recent_actions[-1].lstrip().startswith("fill(")
                and searchboxes
            ):
                raw.append(
                    (
                        'keyboard_press("Enter")',
                        "task_query",
                        "Submit the product query entered in the previous step.",
                        searchboxes[0].bid,
                        searchboxes[0].name,
                    )
                )
            elif searchboxes:
                raw.append(
                    (
                        f"fill({_json_arg(searchboxes[0].bid)}, {_json_arg(product_phrase)})",
                        "task_query",
                        "Fill the site search with the product requested by the task.",
                        searchboxes[0].bid,
                        searchboxes[0].name,
                    )
                )

        value = _input_value(goal)
        if value and _INPUT_RE.search(goal):
            for element in elements:
                if element.role in _INPUT_ROLES:
                    raw.append(
                        (
                            f"fill({_json_arg(element.bid)}, {_json_arg(value)})",
                            "structure",
                            "Fill a visible input whose role is compatible with the task.",
                            element.bid,
                            element.name,
                        )
                    )

        if forum_query:
            for element in elements:
                if element.role == "searchbox":
                    raw.append(
                        (
                            f"fill({_json_arg(element.bid)}, {_json_arg(forum_query)})",
                            "task_query",
                            "Search for the forum explicitly named in the retrieval task.",
                            element.bid,
                            element.name,
                        )
                    )
            if recent_actions and recent_actions[-1].lstrip().startswith("fill("):
                for element in elements:
                    if element.role == "searchbox":
                        raw.append(
                            (
                                'keyboard_press("Enter")',
                                "task_query",
                                "Submit the previously filled forum query.",
                                element.bid,
                                element.name,
                            )
                        )

            if (
                self.navigation_guard
                and f"/f/{forum_query.lower()}" in current_url.lower()
            ):
                for element in elements:
                    normalized_name = element.name.strip().lower()
                    is_subscribe = (
                        normalized_name.startswith("subscribe")
                        and "rss" not in normalized_name
                    )
                    if is_subscribe or re.search(
                        r"\b(?:no|\d+)\s+comments?\b", normalized_name
                    ):
                        raw.append(
                            (
                                f"click({_json_arg(element.bid)}, \"left\")",
                                "task_query",
                                "Advance the observed forum subscribe-and-open-thread workflow.",
                                element.bid,
                                element.name,
                            )
                        )

        for element in elements:
            if (
                element.role in _CLICK_ROLES
                and "disabled" not in element.raw_line.lower()
                and not goal_conflicts_with_control(goal, element.name)
            ):
                raw.append(
                    (
                        f"click({_json_arg(element.bid)}, \"left\")",
                        "structure",
                        "Activate a visible control and let the world model compare outcomes.",
                        element.bid,
                        element.name,
                    )
                )

        if _BACK_RE.search(goal):
            raw.append(("go_back()", "structure", "The task explicitly requests back navigation.", "", ""))
        raw.extend(
            [
                ("scroll(0, 600)", "exploration", "Reveal controls below the current viewport.", "", ""),
                ("scroll(0, -600)", "exploration", "Reveal controls above the current viewport.", "", ""),
            ]
        )

        candidates: list[CandidateAction] = []
        seen: set[str] = set()
        recent = set(recent_actions[-6:])
        for action, source, rationale, target_bid, target_name in raw:
            if action in seen:
                continue
            if action in recent and source not in {"task_query"}:
                continue
            valid, reason = validate_action(action, visible_ids)
            if not valid:
                continue
            seen.add(action)
            _, parsed = encode_action(action)
            rule_score, rule_components = structural_consistency(goal, axtree, action)
            if self.alignment_scorer is None:
                score, components = rule_score, rule_components
            else:
                learned_score, learned_components = self.alignment_scorer.score(
                    state, action, recent_actions
                )
                # The learned alignment head is useful as an additional signal,
                # but must not erase exact visible task/control matches.  The P0
                # failure set exposed near-identical learned scores for
                # "My Account", "Sign Out" and unrelated product categories.
                score = max(float(learned_score), float(rule_score))
                components = {
                    **learned_components,
                    "learned_score": float(learned_score),
                    "rule_score": float(rule_score),
                    "rule_semantic_overlap": rule_components.get(
                        "semantic_overlap", 0.0
                    ),
                    "combined_by": "max_preserve_observed_semantics",
                }
            if source == "task_query":
                normalized_target = target_name.strip().lower()
                if (
                    normalized_target.startswith("subscribe")
                    and "rss" not in normalized_target
                ):
                    task_query_score = 1.0
                elif re.search(r"\b(?:no|\d+)\s+comments?\b", normalized_target):
                    task_query_score = 0.99
                else:
                    task_query_score = 0.98 if parsed["action_type"] == "fill" else 0.96
                score = max(score, task_query_score)
                components = {**components, "task_query_match": 1.0}
            candidates.append(
                CandidateAction(
                    action=action,
                    action_type=parsed["action_type"],
                    rationale=rationale,
                    source=source,
                    target_bid=target_bid,
                    target_name=target_name,
                    structure_score=score,
                    metadata={"structure_components": components},
                )
            )

        candidates.sort(
            key=lambda item: (
                item.source != "reactive",
                -item.structure_score,
                item.action,
            )
        )
        return candidates[: self.max_candidates]


class LLMCandidateGenerator:
    """Strict adapter for an LLM/VLM that returns candidate actions as JSON."""

    generator_name = "llm_json_v1"

    def __init__(
        self,
        completion: Callable[[str], str],
        *,
        max_candidates: int = 8,
    ) -> None:
        self.completion = completion
        self.max_candidates = max_candidates

    def generate(
        self,
        state: Mapping[str, Any] | Any,
        recent_actions: Sequence[str] = (),
    ) -> list[CandidateAction]:
        goal = str(_snapshot_value(state, "goal") or "")
        axtree = _nested_text(_snapshot_value(state, "axtree"))
        elements = parse_elements(axtree)
        visible_ids = {element.bid for element in elements}
        prompt = json.dumps(
            {
                "instruction": goal,
                "axtree": axtree,
                "recent_actions": list(recent_actions)[-5:],
                "output_schema": {
                    "candidates": [
                        {"action": "BrowserGym action", "rationale": "short reason"}
                    ]
                },
                "allowed_action_types": sorted(_ALLOWED_ACTION_TYPES),
                "action_syntax_examples": [
                    'click("VISIBLE_BID", "left")',
                    'fill("VISIBLE_BID", "text to enter")',
                    'keyboard_press("Enter")',
                    "scroll(0, 600)",
                    "go_back()",
                ],
                "syntax_rule": "The action field must be a complete BrowserGym function call, never a bare verb.",
            },
            ensure_ascii=False,
        )
        try:
            payload = json.loads(self.completion(prompt))
        except (TypeError, json.JSONDecodeError) as error:
            raise ValueError("candidate model did not return valid JSON") from error
        if not isinstance(payload, Mapping) or set(payload) != {"candidates"}:
            raise ValueError("candidate JSON must contain only the 'candidates' field")
        rows = payload["candidates"]
        if not isinstance(rows, list) or not rows:
            raise ValueError("candidates must be a non-empty JSON array")

        result: list[CandidateAction] = []
        seen: set[str] = set()
        for row in rows[: self.max_candidates]:
            if not isinstance(row, Mapping) or not isinstance(row.get("action"), str):
                raise ValueError("each candidate needs a string action")
            action = row["action"].strip()
            if action in seen:
                continue
            valid, reason = validate_action(action, visible_ids)
            if not valid:
                raise ValueError(f"invalid candidate '{action}': {reason}")
            seen.add(action)
            _, parsed = encode_action(action)
            score, components = structural_consistency(goal, axtree, action)
            targets = parsed["target_element_ids"]
            target = next((element for element in elements if targets and element.bid == targets[0]), None)
            result.append(
                CandidateAction(
                    action=action,
                    action_type=parsed["action_type"],
                    rationale=str(row.get("rationale", "LLM/VLM candidate")),
                    source="llm",
                    target_bid=targets[0] if targets else "",
                    target_name=target.name if target else "",
                    structure_score=score,
                    metadata={"structure_components": components},
                )
            )
        return result


class LLMConstrainedCandidateGenerator:
    """Use an LLM to select/reorder a structurally valid candidate pool.

    This production-safe binding prevents a small local model from inventing
    element ids or malformed BrowserGym syntax while still letting semantic
    reasoning change the candidate set presented to the world model.
    """

    generator_name = "llm_constrained_json_v1"

    def __init__(
        self,
        completion: Callable[[str], str],
        *,
        max_candidates: int = 8,
        pool_size: int = 24,
    ) -> None:
        if pool_size < max_candidates:
            raise ValueError("pool_size must be at least max_candidates")
        self.completion = completion
        self.max_candidates = max_candidates
        self.base = AXTreeCandidateGenerator(max_candidates=pool_size)

    def generate(
        self,
        state: Mapping[str, Any] | Any,
        recent_actions: Sequence[str] = (),
    ) -> list[CandidateAction]:
        goal = str(_snapshot_value(state, "goal") or "")
        pool = self.base.generate(state, recent_actions)
        prompt = json.dumps(
            {
                "instruction": goal,
                "candidate_pool": [
                    {
                        "index": index,
                        "action": item.action,
                        "target_name": item.target_name,
                        "structure_score": item.structure_score,
                    }
                    for index, item in enumerate(pool)
                ],
                "task": "Select and order the most useful candidate actions. Use only listed indices.",
                "output_schema": {"indices": [0, 1]},
                "maximum_indices": self.max_candidates,
            },
            ensure_ascii=False,
        )
        try:
            payload = json.loads(self.completion(prompt))
        except (TypeError, json.JSONDecodeError) as error:
            raise ValueError("candidate selector did not return valid JSON") from error
        if not isinstance(payload, Mapping) or set(payload) != {"indices"}:
            raise ValueError("selector JSON must contain only the 'indices' field")
        indices = payload["indices"]
        if not isinstance(indices, list) or not indices:
            raise ValueError("indices must be a non-empty array")
        selected: list[CandidateAction] = []
        seen: set[int] = set()
        for raw_index in indices:
            if not isinstance(raw_index, int) or raw_index < 0 or raw_index >= len(pool):
                raise ValueError(f"candidate index out of range: {raw_index!r}")
            if raw_index in seen:
                continue
            seen.add(raw_index)
            item = pool[raw_index]
            selected.append(
                CandidateAction(
                    action=item.action,
                    action_type=item.action_type,
                    rationale=item.rationale,
                    source="llm_constrained",
                    target_bid=item.target_bid,
                    target_name=item.target_name,
                    structure_score=item.structure_score,
                    metadata={**item.metadata, "selected_pool_index": raw_index},
                )
            )
            if len(selected) >= self.max_candidates:
                break
        return selected


def candidate_set_entropy(candidates: Sequence[CandidateAction]) -> float:
    """Normalised action-type entropy used as a candidate-diversity diagnostic."""

    if len(candidates) < 2:
        return 0.0
    counts: dict[str, int] = {}
    for candidate in candidates:
        counts[candidate.action_type] = counts.get(candidate.action_type, 0) + 1
    entropy = -sum(
        (count / len(candidates)) * math.log(count / len(candidates))
        for count in counts.values()
    )
    return entropy / math.log(len(candidates))
