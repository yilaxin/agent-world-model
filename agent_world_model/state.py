"""BrowserGym observation extraction with lightweight DOM/AXTree pruning."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Any, Mapping

_WORD_RE = re.compile(r"[a-z0-9_]{3,}", re.IGNORECASE)
_BID_RE = re.compile(r"\[(?:[^\]]+)\]|\bbid=[\"'][^\"']+[\"']", re.IGNORECASE)
_INTERACTIVE_RE = re.compile(
    r"\b(?:button|link|textbox|searchbox|combobox|checkbox|radio|menuitem|"
    r"option|tab|input|textarea|select)\b|clickable",
    re.IGNORECASE,
)
_SEMANTIC_RE = re.compile(
    r"\b(?:main|navigation|form|heading|article|dialog|listitem|alert)\b|"
    r"<(?:main|nav|form|h[1-6]|article|dialog|label)\b",
    re.IGNORECASE,
)
_HEAVY_DOM_ATTRIBUTE_RE = re.compile(
    r"""\s(?:style|class|src|srcset|data-[\w:-]+)=(?:"[^"]*"|'[^']*')""",
    re.IGNORECASE,
)
_STOPWORDS = {
    "and",
    "are",
    "for",
    "from",
    "have",
    "into",
    "latest",
    "more",
    "that",
    "the",
    "their",
    "this",
    "than",
    "tell",
    "user",
    "what",
    "when",
    "where",
    "which",
    "with",
}


@dataclass(frozen=True)
class ExtractionLimits:
    """Size limits chosen to keep long experiments laptop-friendly."""

    axtree_max_chars: int = 16_000
    axtree_max_lines: int = 220
    dom_max_chars: int = 24_000
    dom_max_lines: int = 320
    max_line_chars: int = 600
    context_lines: int = 1
    max_tabs: int = 10
    include_dom: bool = True


@dataclass(frozen=True)
class PrunedText:
    """A pruned text view plus enough metadata to audit information loss."""

    text: str
    original_char_count: int
    original_line_count: int
    kept_char_count: int
    kept_line_count: int
    truncated: bool


@dataclass(frozen=True)
class StateSnapshot:
    """A JSON-serializable, screenshot-free representation of one page state."""

    schema_version: int
    state_id: str
    goal: str
    url: str
    title: str
    tabs: list[dict[str, Any]]
    active_page_index: int
    focused_element_bid: str
    last_action: str
    last_action_error: str
    elapsed_time: float | None
    screenshot: dict[str, Any]
    axtree: PrunedText
    dom: PrunedText

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _as_python(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "tolist"):
        try:
            return value.tolist()
        except Exception:
            pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def _as_text(value: Any, max_chars: int = 4_000) -> str:
    value = _as_python(value)
    if value is None:
        return ""
    if isinstance(value, (list, tuple)) and len(value) == 1:
        value = value[0]
    text = str(value)
    if len(text) > max_chars:
        return text[: max_chars - 1] + "…"
    return text


def _as_int(value: Any, default: int = 0) -> int:
    value = _as_python(value)
    if isinstance(value, list) and value:
        value = value[0]
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any) -> float | None:
    value = _as_python(value)
    if isinstance(value, list) and value:
        value = value[0]
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _goal_terms(goal: str) -> set[str]:
    return {
        token.lower()
        for token in _WORD_RE.findall(goal)
        if token.lower() not in _STOPWORDS
    }


def _compact_line(line: str, *, kind: str, max_chars: int) -> str:
    stripped = line.lstrip(" \t")
    depth = len(line[: len(line) - len(stripped)].expandtabs(2)) // 2
    if kind == "dom":
        stripped = _HEAVY_DOM_ATTRIBUTE_RE.sub("", stripped)
    stripped = re.sub(r"[ \t]+", " ", stripped).strip()
    compact = ("  " * min(depth, 12)) + stripped
    if len(compact) > max_chars:
        compact = compact[: max_chars - 1] + "…"
    return compact


def _line_score(line: str, goal_terms: set[str], index: int) -> int:
    lowered = line.lower()
    score = 1
    if index == 0:
        score += 1_000
    if _BID_RE.search(line):
        score += 25
    if _INTERACTIVE_RE.search(line):
        score += 80
    if _SEMANTIC_RE.search(line):
        score += 12
    score += 30 * sum(term in lowered for term in goal_terms)
    if re.fullmatch(r"</[^>]+>", line.strip()):
        score -= 5
    return score


def prune_text(
    text: str,
    *,
    goal: str,
    kind: str,
    max_chars: int,
    max_lines: int,
    max_line_chars: int,
    context_lines: int,
) -> PrunedText:
    """Keep visible, interactive and task-relevant lines under a fixed budget."""

    raw_lines = text.splitlines()
    compact_lines = [
        _compact_line(line, kind=kind, max_chars=max_line_chars)
        for line in raw_lines
        if line.strip()
    ]
    original_chars = len(text)
    original_lines = len(raw_lines)

    if not compact_lines:
        return PrunedText(
            text="",
            original_char_count=original_chars,
            original_line_count=original_lines,
            kept_char_count=0,
            kept_line_count=0,
            truncated=bool(text),
        )

    compact_text = "\n".join(compact_lines)
    if len(compact_text) <= max_chars and len(compact_lines) <= max_lines:
        content_was_pruned = (
            len(compact_lines) < len([line for line in raw_lines if line.strip()])
            or any(len(line) > max_line_chars for line in raw_lines)
            or (kind == "dom" and compact_text != text.strip())
        )
        return PrunedText(
            text=compact_text,
            original_char_count=original_chars,
            original_line_count=original_lines,
            kept_char_count=len(compact_text),
            kept_line_count=len(compact_lines),
            truncated=content_was_pruned,
        )

    terms = _goal_terms(goal)
    scores = [
        _line_score(line, terms, index) for index, line in enumerate(compact_lines)
    ]
    ranked = sorted(range(len(compact_lines)), key=lambda i: (-scores[i], i))

    selected: set[int] = {0}
    for index in ranked:
        neighborhood = range(
            max(0, index - context_lines),
            min(len(compact_lines), index + context_lines + 1),
        )
        for nearby in neighborhood:
            if len(selected) >= max_lines:
                break
            selected.add(nearby)
        if len(selected) >= max_lines:
            break

    def output_size(indices: set[int]) -> int:
        return sum(len(compact_lines[index]) + 1 for index in indices)

    while output_size(selected) > max_chars and len(selected) > 1:
        removable = min(
            (index for index in selected if index != 0),
            key=lambda index: (scores[index], -index),
        )
        selected.remove(removable)

    kept_lines = [compact_lines[index] for index in sorted(selected)]
    result = "\n".join(kept_lines)
    if len(result) > max_chars:
        result = result[: max_chars - 1] + "…"

    return PrunedText(
        text=result,
        original_char_count=original_chars,
        original_line_count=original_lines,
        kept_char_count=len(result),
        kept_line_count=len(kept_lines),
        truncated=True,
    )


class StateExtractor:
    """Convert a raw BrowserGym observation into a bounded text snapshot."""

    def __init__(self, limits: ExtractionLimits | None = None) -> None:
        self.limits = limits or ExtractionLimits()

    def extract(self, observation: Mapping[str, Any]) -> StateSnapshot:
        try:
            from browsergym.utils.obs import flatten_axtree_to_str, flatten_dom_to_str
        except ImportError as error:
            raise RuntimeError(
                "StateExtractor requires BrowserGym; install the phase-one browser dependencies"
            ) from error
        goal = _as_text(observation.get("goal"))
        extra_properties = observation.get("extra_element_properties")

        axtree_raw = ""
        axtree_object = observation.get("axtree_object")
        if axtree_object:
            axtree_raw = flatten_axtree_to_str(
                axtree_object,
                extra_properties=extra_properties,
                with_clickable=True,
                skip_generic=True,
                filter_visible_only=True,
            )

        dom_raw = ""
        dom_object = observation.get("dom_object")
        if self.limits.include_dom and dom_object:
            dom_raw = flatten_dom_to_str(
                dom_object,
                extra_properties=extra_properties,
                with_clickable=True,
                filter_visible_only=True,
            )

        axtree = prune_text(
            axtree_raw,
            goal=goal,
            kind="axtree",
            max_chars=self.limits.axtree_max_chars,
            max_lines=self.limits.axtree_max_lines,
            max_line_chars=self.limits.max_line_chars,
            context_lines=self.limits.context_lines,
        )
        dom = prune_text(
            dom_raw,
            goal=goal,
            kind="dom",
            max_chars=self.limits.dom_max_chars,
            max_lines=self.limits.dom_max_lines,
            max_line_chars=self.limits.max_line_chars,
            context_lines=self.limits.context_lines,
        )

        urls = list(_as_python(observation.get("open_pages_urls")) or [])
        titles = list(_as_python(observation.get("open_pages_titles")) or [])
        active_page_index = _as_int(observation.get("active_page_index"))
        tabs = [
            {
                "index": index,
                "url": _as_text(url),
                "title": _as_text(titles[index] if index < len(titles) else ""),
            }
            for index, url in enumerate(urls[: self.limits.max_tabs])
        ]
        title = ""
        if 0 <= active_page_index < len(titles):
            title = _as_text(titles[active_page_index])

        screenshot = observation.get("screenshot")
        screenshot_metadata: dict[str, Any] = {"stored": False}
        if screenshot is not None:
            shape = getattr(screenshot, "shape", None)
            screenshot_metadata.update(
                {
                    "available": True,
                    "shape": list(shape) if shape is not None else [],
                    "dtype": str(getattr(screenshot, "dtype", "")),
                }
            )
        else:
            screenshot_metadata["available"] = False

        url = _as_text(observation.get("url"))
        state_material = "\0".join(
            [goal, url, title, axtree.text, dom.text]
        ).encode("utf-8")
        state_id = hashlib.sha256(state_material).hexdigest()[:16]

        return StateSnapshot(
            schema_version=1,
            state_id=state_id,
            goal=goal,
            url=url,
            title=title,
            tabs=tabs,
            active_page_index=active_page_index,
            focused_element_bid=_as_text(observation.get("focused_element_bid")),
            last_action=_as_text(observation.get("last_action")),
            last_action_error=_as_text(observation.get("last_action_error")),
            elapsed_time=_as_float(observation.get("elapsed_time")),
            screenshot=screenshot_metadata,
            axtree=axtree,
            dom=dom,
        )
