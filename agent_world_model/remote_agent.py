"""Thin HTTP client for running the GPU phase-three Agent from BrowserGym."""

from __future__ import annotations

import json
import ipaddress
from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit
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

    def __init__(
        self,
        endpoint: str,
        *,
        timeout_seconds: float = 30.0,
        bearer_token: str | None = None,
        allow_insecure_private_http: bool = True,
    ) -> None:
        self.endpoint = self._validate_endpoint(
            endpoint,
            allow_insecure_private_http=allow_insecure_private_http,
        )
        self.timeout_seconds = timeout_seconds
        self.bearer_token = bearer_token

    @staticmethod
    def _validate_endpoint(
        endpoint: str,
        *,
        allow_insecure_private_http: bool,
    ) -> str:
        parsed = urlsplit(endpoint.rstrip("/"))
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("remote endpoint must be an absolute HTTP(S) URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("remote endpoint must not contain credentials, query, or fragment")
        if parsed.path not in {"", "/"}:
            raise ValueError("remote endpoint must not contain a path")
        if parsed.scheme == "http":
            try:
                address = ipaddress.ip_address(parsed.hostname)
                is_private = address.is_private or address.is_loopback
            except ValueError:
                is_private = parsed.hostname.casefold() == "localhost"
            if not (allow_insecure_private_http and is_private):
                raise ValueError(
                    "plain HTTP is restricted to loopback/private IP endpoints; use HTTPS"
                )
        return endpoint.rstrip("/")

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        return headers

    def health(self) -> dict[str, Any]:
        request = Request(f"{self.endpoint}/health", headers=self._headers())
        with urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("status") != "ok":
            raise RuntimeError(f"remote Agent is not healthy: {payload}")
        return payload

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
            headers={**self._headers(), "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not payload.get("action"):
            raise RuntimeError(f"remote Agent returned no action: {payload}")
        return RemoteAgentDecision(action=str(payload["action"]), payload=payload)

