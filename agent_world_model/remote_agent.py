"""Thin HTTP client for running the GPU phase-three Agent from BrowserGym."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class RemoteAgentDecision:
    action: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return dict(self.payload)


class RemotePhase3Agent:
    """Expose the normal ``decide`` API while inference runs on the GPU host."""

    policy_name = "remote_phase3_world_model_v1"

    def __init__(self, endpoint: str, *, timeout_seconds: float = 30.0) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def decide(
        self,
        state: Any,
        recent_actions: Sequence[str] = (),
        *,
        direct_answer: str | None = None,
    ) -> RemoteAgentDecision:
        state_payload: Mapping[str, Any]
        if isinstance(state, Mapping):
            state_payload = state
        else:
            state_payload = state.to_dict()
        body = json.dumps(
            {
                "state": state_payload,
                "recent_actions": list(recent_actions),
                "direct_answer": direct_answer,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = Request(
            f"{self.endpoint}/decide",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not payload.get("action"):
            raise RuntimeError(f"remote Agent returned no action: {payload}")
        return RemoteAgentDecision(action=str(payload["action"]), payload=payload)

