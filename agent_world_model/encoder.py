"""Deterministic, CPU-only state encoder used by the phase-one baseline."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, Iterable, Mapping, Sequence

if TYPE_CHECKING:
    from .state import StateSnapshot


_TOKEN_RE = re.compile(r"[\w.-]+", re.UNICODE)


@dataclass(frozen=True)
class EncoderConfig:
    """Configuration for the first structured-text state encoder."""

    dimensions: int = 512
    recent_action_count: int = 5
    max_text_chars: int = 48_000
    include_dom: bool = True

    def __post_init__(self) -> None:
        if self.dimensions < 32:
            raise ValueError("dimensions must be at least 32")
        if self.recent_action_count < 0:
            raise ValueError("recent_action_count cannot be negative")
        if self.max_text_chars < 1_000:
            raise ValueError("max_text_chars must be at least 1000")


@dataclass(frozen=True)
class EncodedState:
    """JSON-serializable representation of ``z_t``."""

    schema_version: int
    encoder_name: str
    encoding_id: str
    source_state_id: str
    dimensions: int
    recent_actions: list[str]
    structured_text: str
    vector: list[float]
    nonzero_features: int
    truncated: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_compact_dict(self) -> dict[str, Any]:
        """Keep the trainable vector while omitting duplicated source text."""

        data = self.to_dict()
        data.pop("structured_text")
        return data


def _snapshot_dict(state: StateSnapshot | Mapping[str, Any]) -> Mapping[str, Any]:
    return state if isinstance(state, Mapping) else state.to_dict()


def _nested_text(value: Any) -> str:
    if isinstance(value, Mapping):
        return str(value.get("text", ""))
    return str(getattr(value, "text", "") or "")


def _bounded_actions(actions: Iterable[str], count: int) -> list[str]:
    if count == 0:
        return []
    return [str(action) for action in list(actions)[-count:]]


class StateEncoderV1:
    """Encode task, URL, DOM/AXTree and the five latest actions into ``z_t``.

    Feature hashing keeps the representation deterministic and trainable without
    requiring a GPU, a downloaded language model, or a fitted vocabulary.
    """

    name = "structured_text_feature_hash_v1"

    def __init__(self, config: EncoderConfig | None = None) -> None:
        self.config = config or EncoderConfig()

    def build_structured_text(
        self,
        state: StateSnapshot | Mapping[str, Any],
        recent_actions: Sequence[str] = (),
    ) -> tuple[str, list[str], bool]:
        data = _snapshot_dict(state)
        actions = _bounded_actions(recent_actions, self.config.recent_action_count)
        tabs = data.get("tabs", [])
        tab_lines = []
        if isinstance(tabs, Sequence) and not isinstance(tabs, (str, bytes)):
            for tab in tabs:
                if isinstance(tab, Mapping):
                    tab_lines.append(
                        f"{tab.get('index', '')}: {tab.get('title', '')} "
                        f"<{tab.get('url', '')}>"
                    )

        sections = [
            "[TASK]\n" + str(data.get("goal", "")),
            "[URL]\n" + str(data.get("url", "")),
            "[TITLE]\n" + str(data.get("title", "")),
            "[TABS]\n" + ("\n".join(tab_lines) or "<none>"),
            "[RECENT_ACTIONS]\n"
            + (
                "\n".join(f"{index + 1}. {action}" for index, action in enumerate(actions))
                or "<none>"
            ),
            "[AXTREE]\n" + _nested_text(data.get("axtree", "")),
        ]
        if self.config.include_dom:
            sections.append("[DOM]\n" + _nested_text(data.get("dom", "")))

        text = "\n\n".join(sections)
        truncated = len(text) > self.config.max_text_chars
        if truncated:
            text = text[: self.config.max_text_chars - 1] + "…"
        return text, actions, truncated

    def _feature_hash(self, text: str) -> tuple[list[float], int]:
        vector = [0.0] * self.config.dimensions
        tokens = [token.lower() for token in _TOKEN_RE.findall(text)]
        features = tokens + [
            f"{tokens[index]}::{tokens[index + 1]}"
            for index in range(max(0, len(tokens) - 1))
        ]
        for feature in features:
            digest = hashlib.blake2b(
                feature.encode("utf-8"), digest_size=8, person=b"awm-state-v1"
            ).digest()
            bucket = int.from_bytes(digest[:4], "little") % self.config.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[bucket] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [round(value / norm, 8) for value in vector]
        return vector, sum(value != 0.0 for value in vector)

    def encode(
        self,
        state: StateSnapshot | Mapping[str, Any],
        recent_actions: Sequence[str] = (),
    ) -> EncodedState:
        data = _snapshot_dict(state)
        text, actions, truncated = self.build_structured_text(state, recent_actions)
        vector, nonzero = self._feature_hash(text)
        encoding_id = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        return EncodedState(
            schema_version=1,
            encoder_name=self.name,
            encoding_id=encoding_id,
            source_state_id=str(data.get("state_id", "")),
            dimensions=self.config.dimensions,
            recent_actions=actions,
            structured_text=text,
            vector=vector,
            nonzero_features=nonzero,
            truncated=truncated,
        )
