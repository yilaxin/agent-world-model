"""Structured LLM semantic world model with an offline deterministic baseline."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Callable, Mapping, Protocol, Sequence

from .phase2_schema import canonicalize_transition


@dataclass(frozen=True)
class SemanticPrediction:
    next_page_type: str
    state_changes: list[str]
    progress: float
    invalid_action_probability: float
    risk_probability: float
    terminal_probability: float
    success_probability: float
    confidence: float
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "SemanticPrediction":
        probabilities = (
            "invalid_action_probability",
            "risk_probability",
            "terminal_probability",
            "success_probability",
            "confidence",
        )
        for name in probabilities:
            number = float(value[name])
            if not 0.0 <= number <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        progress = float(value["progress"])
        if not -1.0 <= progress <= 1.0:
            raise ValueError("progress must be in [-1, 1]")
        return cls(
            next_page_type=str(value["next_page_type"]),
            state_changes=[str(item) for item in value.get("state_changes", [])],
            progress=progress,
            invalid_action_probability=float(value["invalid_action_probability"]),
            risk_probability=float(value["risk_probability"]),
            terminal_probability=float(value["terminal_probability"]),
            success_probability=float(value["success_probability"]),
            confidence=float(value["confidence"]),
            rationale=str(value.get("rationale", "")),
        )


class CompletionBackend(Protocol):
    def __call__(self, *, system: str, user: str) -> str: ...


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def parse_semantic_prediction(text: str) -> SemanticPrediction:
    """Strictly parse one JSON object and reject free-form output."""

    match = _JSON_FENCE_RE.search(text)
    payload = match.group(1).strip() if match else text.strip()
    value = json.loads(payload)
    if not isinstance(value, Mapping):
        raise ValueError("semantic model output must be a JSON object")
    return SemanticPrediction.from_mapping(value)


class LLMSemanticWorldModel:
    """Provider-neutral LLM wrapper; inject any synchronous completion backend."""

    SYSTEM_PROMPT = """\
You are an action-conditioned one-step world model for a browser agent.
Predict only the immediate outcome of the proposed action. Return exactly one
JSON object with keys: next_page_type, state_changes, progress,
invalid_action_probability, risk_probability, terminal_probability,
success_probability, confidence, rationale. Probabilities must be in [0,1],
progress in [-1,1]. Do not propose another action and do not claim observations
that are absent from the supplied state."""

    def __init__(self, completion: CompletionBackend) -> None:
        self.completion = completion

    def build_prompt(
        self,
        *,
        instruction: str,
        state: Mapping[str, Any],
        action: str,
        history: Sequence[str] = (),
    ) -> str:
        payload = {
            "instruction": instruction,
            "state": {
                "url": state.get("url", ""),
                "title": state.get("title", ""),
                "axtree": state.get("axtree", {}),
                "dom": state.get("dom", {}),
                "last_action_error": state.get("last_action_error", ""),
            },
            "recent_actions": list(history[-5:]),
            "proposed_action": action,
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    def predict(
        self,
        *,
        instruction: str,
        state: Mapping[str, Any],
        action: str,
        history: Sequence[str] = (),
    ) -> SemanticPrediction:
        response = self.completion(
            system=self.SYSTEM_PROMPT,
            user=self.build_prompt(
                instruction=instruction,
                state=state,
                action=action,
                history=history,
            ),
        )
        return parse_semantic_prediction(response)


class HeuristicSemanticWorldModel:
    """Auditable zero-network baseline used for data checks and smoke tests."""

    def predict_transition(self, record: Mapping[str, Any]) -> SemanticPrediction:
        example = canonicalize_transition(record)
        changes = [
            name
            for name, value in example.state_delta.items()
            if value >= 0.5 and name.endswith("changed")
        ]
        risks = example.risks
        signals = example.task_signals
        next_state = record.get("next_state", {})
        url = str(next_state.get("url", "")) if isinstance(next_state, Mapping) else ""
        page_type = "other"
        if any(token in url.lower() for token in ("login", "signin", "auth")):
            page_type = "authentication"
        elif any(token in url.lower() for token in ("search", "query")):
            page_type = "search_results"
        elif signals["terminal"] >= 0.5:
            page_type = "terminal"
        return SemanticPrediction(
            next_page_type=page_type,
            state_changes=changes,
            progress=float(signals["progress"]),
            invalid_action_probability=float(signals["invalid_action"]),
            risk_probability=max(
                float(risks["stalled"]),
                float(risks["goal_deviation"]),
                float(risks["severe_failure"]),
            ),
            terminal_probability=float(signals["terminal"]),
            success_probability=float(risks["success"]),
            confidence=0.55,
            rationale="Deterministic weak-supervision baseline; not an LLM result.",
        )
