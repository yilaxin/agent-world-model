"""Streaming JSONL trajectory logging for BrowserGym experiments."""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Mapping

if TYPE_CHECKING:
    from .state import StateSnapshot


def _json_safe(
    value: Any,
    *,
    depth: int = 0,
    max_depth: int = 7,
    max_string_chars: int = 4_000,
    max_items: int = 1_024,
) -> Any:
    if depth > max_depth:
        return "<max-depth>"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        if len(value) > max_string_chars:
            return value[: max_string_chars - 1] + "…"
        return value
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, Mapping):
        items = list(value.items())
        result = {
            str(key): _json_safe(
                item,
                depth=depth + 1,
                max_depth=max_depth,
                max_string_chars=max_string_chars,
                max_items=max_items,
            )
            for key, item in items[:max_items]
        }
        if len(items) > max_items:
            result["__omitted_items__"] = len(items) - max_items
        return result
    if isinstance(value, (list, tuple, set)):
        values = list(value)
        result = [
            _json_safe(
                item,
                depth=depth + 1,
                max_depth=max_depth,
                max_string_chars=max_string_chars,
                max_items=max_items,
            )
            for item in values[:max_items]
        ]
        if len(values) > max_items:
            result.append({"__omitted_items__": len(values) - max_items})
        return result
    if hasattr(value, "shape") and hasattr(value, "dtype"):
        size = int(getattr(value, "size", max_items + 1))
        if size > max_items:
            return {
                "__array_metadata__": True,
                "shape": list(getattr(value, "shape", [])),
                "dtype": str(getattr(value, "dtype", "")),
                "stored": False,
            }
    if hasattr(value, "tolist"):
        try:
            return _json_safe(
                value.tolist(),
                depth=depth + 1,
                max_depth=max_depth,
                max_string_chars=max_string_chars,
                max_items=max_items,
            )
        except Exception:
            pass
    return str(value)


def _state_dict(state: StateSnapshot | Mapping[str, Any]) -> dict[str, Any]:
    if hasattr(state, "to_dict"):
        return dict(state.to_dict())
    return dict(state)


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_.") or "trajectory"


def make_trajectory_path(
    output_dir: str | Path,
    *,
    env_id: str,
    seed: int,
    run_id: str,
) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = _safe_filename(f"{timestamp}_{env_id}_seed{seed}_{run_id}.jsonl")
    return Path(output_dir) / filename


class TrajectoryLogger:
    """Append one complete transition per line without buffering an episode."""

    def __init__(
        self,
        path: str | Path,
        *,
        env_id: str,
        seed: int,
        run_id: str | None = None,
        episode_id: str | None = None,
        fsync: bool = False,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.env_id = env_id
        self.seed = int(seed)
        self.run_id = run_id or uuid.uuid4().hex[:8]
        self.episode_id = episode_id or f"{self.run_id}-episode-0"
        self.fsync = fsync
        self.step_count = 0
        self.total_reward = 0.0
        self._file = self.path.open("a", encoding="utf-8", buffering=1)

    @classmethod
    def create(
        cls,
        output_dir: str | Path,
        *,
        env_id: str,
        seed: int,
        run_id: str | None = None,
        episode_id: str | None = None,
        fsync: bool = False,
    ) -> "TrajectoryLogger":
        actual_run_id = run_id or uuid.uuid4().hex[:8]
        path = make_trajectory_path(
            output_dir,
            env_id=env_id,
            seed=seed,
            run_id=actual_run_id,
        )
        return cls(
            path,
            env_id=env_id,
            seed=seed,
            run_id=actual_run_id,
            episode_id=episode_id,
            fsync=fsync,
        )

    def record_transition(
        self,
        *,
        state: StateSnapshot | Mapping[str, Any],
        action: str,
        next_state: StateSnapshot | Mapping[str, Any],
        reward: float,
        terminated: bool,
        truncated: bool,
        info: Mapping[str, Any] | None = None,
        encoded_state: Mapping[str, Any] | None = None,
        encoded_next_state: Mapping[str, Any] | None = None,
        decision: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self._file.closed:
            raise RuntimeError("Cannot record to a closed trajectory logger.")

        record = {
            "schema_version": 2 if encoded_state is not None else 1,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "episode_id": self.episode_id,
            "env_id": self.env_id,
            "seed": self.seed,
            "step_index": self.step_count,
            "state": _state_dict(state),
            "action": str(action),
            "next_state": _state_dict(next_state),
            "reward": float(reward),
            "terminated": bool(terminated),
            "truncated": bool(truncated),
            "done": bool(terminated or truncated),
            "info": _json_safe(info or {}),
        }
        if encoded_state is not None:
            record["encoded_state"] = _json_safe(encoded_state)
        if encoded_next_state is not None:
            record["encoded_next_state"] = _json_safe(encoded_next_state)
        if decision is not None:
            record["decision"] = _json_safe(decision)
        if metadata is not None:
            record["metadata"] = _json_safe(metadata)
        self._file.write(
            json.dumps(
                _json_safe(record),
                ensure_ascii=False,
                separators=(",", ":"),
            )
            + "\n"
        )
        self._file.flush()
        if self.fsync:
            os.fsync(self._file.fileno())

        self.step_count += 1
        self.total_reward += float(reward)
        return record

    def summary(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "env_id": self.env_id,
            "seed": self.seed,
            "run_id": self.run_id,
            "episode_id": self.episode_id,
            "step_count": self.step_count,
            "total_reward": self.total_reward,
        }

    def close(self) -> None:
        if not self._file.closed:
            self._file.close()

    def __enter__(self) -> "TrajectoryLogger":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()


def load_trajectory(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def iter_trajectory(path: str | Path) -> Iterable[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                yield json.loads(line)
