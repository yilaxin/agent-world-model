"""Canonical phase-two transition schema and deterministic weak supervision.

The phase-one logger stores browser observations faithfully.  Phase two adds the
task signals required by the proposal while retaining traceability to the source
episode.  Labels inferred here are explicitly marked ``heuristic``; human or LLM
labels can override them before training.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence


STATE_DELTA_LABELS = (
    "url_changed",
    "title_changed",
    "axtree_changed",
    "dom_changed",
    "target_available",
)
TASK_SIGNAL_LABELS = ("invalid_action", "terminal")
RISK_LABELS = ("success", "stalled", "goal_deviation", "severe_failure")

_ACTION_RE = re.compile(r"^\s*([A-Za-z_][\w]*)\s*\((.*)\)\s*$", re.DOTALL)
_BID_RE = re.compile(r"""['"]([A-Za-z0-9_.:-]+)['"]""")


def symlog(value: float) -> float:
    """Dreamer-style signed log transform for unbounded task signals."""

    return math.copysign(math.log1p(abs(float(value))), float(value))


def symexp(value: float) -> float:
    """Inverse of :func:`symlog`, numerically stable for ordinary labels."""

    return math.copysign(math.expm1(abs(float(value))), float(value))


def _nested_text(value: Any) -> str:
    if isinstance(value, Mapping):
        return str(value.get("text", ""))
    return str(value or "")


def _normalised_lines(value: Any) -> set[str]:
    return {
        " ".join(line.split())
        for line in _nested_text(value).splitlines()
        if line.strip()
    }


def _stable_vector(text: str, dimensions: int, *, person: bytes) -> list[float]:
    """Signed feature hashing without a fitted vocabulary or external package."""

    vector = [0.0] * dimensions
    tokens = re.findall(r"[\w./:=+-]+", text.lower(), re.UNICODE)
    for index, token in enumerate(tokens):
        features = [token]
        if index + 1 < len(tokens):
            features.append(f"{token}::{tokens[index + 1]}")
        for feature in features:
            digest = hashlib.blake2b(
                feature.encode("utf-8"), digest_size=8, person=person
            ).digest()
            bucket = int.from_bytes(digest[:4], "little") % dimensions
            vector[bucket] += 1.0 if digest[4] & 1 else -1.0
    norm = math.sqrt(sum(item * item for item in vector))
    return [round(item / norm, 8) for item in vector] if norm else vector


def encode_action(action: str, dimensions: int = 128) -> tuple[list[float], dict[str, Any]]:
    """Encode an action and expose its parsed type/target for auditing."""

    match = _ACTION_RE.match(str(action))
    action_type = match.group(1).lower() if match else "unknown"
    arguments = match.group(2) if match else str(action)
    target_match = _BID_RE.search(arguments)
    target_id = target_match.group(1) if target_match else ""
    structured = f"[TYPE] {action_type}\n[TARGET] {target_id}\n[RAW] {action}"
    return _stable_vector(structured, dimensions, person=b"awm-action-v2"), {
        "action_type": action_type,
        "target_element_ids": [target_id] if target_id else [],
    }


def _state_vector(record: Mapping[str, Any], key: str, dimensions: int) -> list[float]:
    encoded = record.get(key)
    if isinstance(encoded, Mapping):
        vector = encoded.get("vector")
        if isinstance(vector, Sequence) and not isinstance(vector, (str, bytes)):
            values = [float(item) for item in vector]
            if len(values) == dimensions:
                return values
    state_key = "state" if key == "encoded_state" else "next_state"
    state = record.get(state_key, {})
    return _stable_vector(
        json.dumps(state, ensure_ascii=False, sort_keys=True),
        dimensions,
        person=b"awm-state-v2",
    )


def _label_override(
    record: Mapping[str, Any], name: str, default: float | bool
) -> float | bool:
    labels = record.get("labels")
    if isinstance(labels, Mapping) and name in labels:
        return labels[name]
    if name in record:
        return record[name]
    return default


@dataclass(frozen=True)
class Phase2Example:
    """One action-conditioned transition ready for a one-step world model."""

    schema_version: int
    example_id: str
    task_id: str
    episode_id: str
    split: str
    instruction: str
    step_index: int
    action: str
    action_type: str
    target_element_ids: list[str]
    state_vector: list[float]
    action_vector: list[float]
    next_state_vector: list[float]
    state_delta: dict[str, float]
    task_signals: dict[str, float]
    risks: dict[str, float]
    label_source: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def canonicalize_transition(
    record: Mapping[str, Any],
    *,
    split: str = "unassigned",
    state_dimensions: int = 512,
    action_dimensions: int = 128,
) -> Phase2Example:
    """Convert phase-one/v2 JSONL or proposal-aligned records into v3."""

    state = record.get("state") if isinstance(record.get("state"), Mapping) else {}
    next_state = (
        record.get("next_state")
        if isinstance(record.get("next_state"), Mapping)
        else {}
    )
    action = str(record.get("action", ""))
    action_vector, action_info = encode_action(action, action_dimensions)
    source_state = _state_vector(record, "encoded_state", state_dimensions)
    target_state = _state_vector(record, "encoded_next_state", state_dimensions)

    before_ax = _normalised_lines(state.get("axtree", ""))
    after_ax = _normalised_lines(next_state.get("axtree", ""))
    before_dom = _normalised_lines(state.get("dom", ""))
    after_dom = _normalised_lines(next_state.get("dom", ""))
    ax_union = max(1, len(before_ax | after_ax))
    dom_union = max(1, len(before_dom | after_dom))
    added_ratio = len(after_ax - before_ax) / ax_union
    removed_ratio = len(before_ax - after_ax) / ax_union

    target_ids = action_info["target_element_ids"]
    next_search_text = f"{_nested_text(next_state.get('axtree'))}\n{_nested_text(next_state.get('dom'))}"
    target_available = bool(target_ids and any(item in next_search_text for item in target_ids))
    last_error = str(next_state.get("last_action_error", "") or "")
    info = record.get("info") if isinstance(record.get("info"), Mapping) else {}
    invalid_action = bool(
        last_error
        or info.get("action_error")
        or info.get("action_exec_error")
        or info.get("invalid_action")
    )
    terminated = bool(record.get("terminated", False))
    truncated = bool(record.get("truncated", False))
    terminal = bool(record.get("done", terminated or truncated))
    reward = float(record.get("reward", 0.0) or 0.0)
    success = bool(terminated and not truncated and reward > 0.0)
    unchanged = (
        state.get("url") == next_state.get("url")
        and state.get("title") == next_state.get("title")
        and before_ax == after_ax
        and before_dom == after_dom
    )
    stalled = bool(not terminal and unchanged and reward <= 0.0)
    goal_deviation = bool(invalid_action or reward < 0.0)
    # MiniWoB normalises unsuccessful terminal outcomes to reward 0.  Treat a
    # terminal non-success as a severe task failure even when the environment
    # does not expose a negative scalar reward.  This remains outcome-derived:
    # it is never inferred from the world-model prediction.
    severe_failure = bool(
        (terminal and not success and reward <= 0.0)
        or (invalid_action and terminal)
        or reward < -0.5
    )
    heuristic_progress = 1.0 if success else max(-1.0, min(1.0, reward))

    state_delta = {
        "url_changed": float(state.get("url") != next_state.get("url")),
        "title_changed": float(state.get("title") != next_state.get("title")),
        "axtree_changed": float(before_ax != after_ax),
        "dom_changed": float(before_dom != after_dom),
        "target_available": float(target_available),
        "key_elements_added_ratio": float(added_ratio),
        "key_elements_removed_ratio": float(removed_ratio),
        "dom_change_ratio": float(
            (len(after_dom - before_dom) + len(before_dom - after_dom)) / dom_union
        ),
    }
    task_signals = {
        "reward": float(_label_override(record, "reward", reward)),
        "progress": float(
            _label_override(record, "subgoal_progress_t1", heuristic_progress)
        ),
        "invalid_action": float(
            bool(_label_override(record, "invalid_action", invalid_action))
        ),
        "terminal": float(bool(_label_override(record, "terminal", terminal))),
    }
    risks = {
        "success": float(bool(_label_override(record, "task_success", success))),
        "stalled": float(bool(_label_override(record, "stalled", stalled))),
        "goal_deviation": float(
            bool(_label_override(record, "goal_deviation", goal_deviation))
        ),
        "severe_failure": float(
            bool(_label_override(record, "severe_failure", severe_failure))
        ),
    }

    episode_id = str(
        record.get("episode_id")
        or record.get("run_id")
        or record.get("task_id")
        or "unknown-episode"
    )
    task_id = str(record.get("task_id") or record.get("env_id") or "unknown-task")
    step_index = int(record.get("step_index", 0) or 0)
    source_key = f"{episode_id}:{step_index}:{action}"
    example_id = hashlib.sha256(source_key.encode("utf-8")).hexdigest()[:20]
    explicit_label_source = record.get("label_source")
    if explicit_label_source:
        label_source = str(explicit_label_source)
    elif isinstance(record.get("labels"), Mapping):
        label_source = "provided"
    else:
        label_source = "heuristic"

    return Phase2Example(
        schema_version=3,
        example_id=example_id,
        task_id=task_id,
        episode_id=episode_id,
        split=split,
        instruction=str(record.get("instruction") or state.get("goal") or ""),
        step_index=step_index,
        action=action,
        action_type=action_info["action_type"],
        target_element_ids=list(target_ids),
        state_vector=source_state,
        action_vector=action_vector,
        next_state_vector=target_state,
        state_delta=state_delta,
        task_signals=task_signals,
        risks=risks,
        label_source=label_source,
        metadata={
            "env_id": str(record.get("env_id", "")),
            "run_id": str(record.get("run_id", "")),
            "seed": int(record.get("seed", 0) or 0),
            "truncated": truncated,
            "source_schema_version": int(record.get("schema_version", 1) or 1),
            **(
                {
                    "human_review": {
                        "review_schema_version": int(
                            record["metadata"]["human_review"].get(
                                "review_schema_version", 1
                            )
                            or 1
                        ),
                        "reviewer": str(
                            record["metadata"]["human_review"].get("reviewer", "")
                        ),
                        "reviewed_at_utc": str(
                            record["metadata"]["human_review"].get(
                                "reviewed_at_utc", ""
                            )
                        ),
                        "notes": str(
                            record["metadata"]["human_review"].get("notes", "")
                        ),
                    }
                }
                if isinstance(record.get("metadata"), Mapping)
                and isinstance(record["metadata"].get("human_review"), Mapping)
                else {}
            ),
            **(
                {
                    "counterfactual_pair_id": str(record["metadata"].get("counterfactual_pair_id", "")),
                    "counterfactual_group_id": str(record["metadata"].get("counterfactual_group_id", "")),
                    "counterfactual_role": str(record["metadata"].get("counterfactual_role", "")),
                    "intervention": str(record["metadata"].get("intervention", "")),
                    "intervention_type": str(record["metadata"].get("intervention_type", "unspecified")),
                    "observed_in_environment": bool(record["metadata"].get("observed_in_environment", False)),
                    "initial_state_id": str(record["metadata"].get("initial_state_id", "")),
                }
                if isinstance(record.get("metadata"), Mapping)
                and record["metadata"].get("counterfactual_pair_id")
                else {}
            ),
        },
    )
