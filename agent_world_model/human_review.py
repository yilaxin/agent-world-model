"""Auditable review workflow for phase-two trajectory labels.

The world-model dataset contains outcome-derived labels where possible and
heuristics where the environment does not expose a definitive signal.  Human
sign-off and reproducible evidence review are kept as distinct provenance
classes: only a real person's approval is labelled ``human_verified``.
"""

from __future__ import annotations

import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .phase2_schema import canonicalize_transition


BOOLEAN_REVIEW_FIELDS = (
    "task_success",
    "stalled",
    "goal_deviation",
    "severe_failure",
    "invalid_action",
    "terminal",
)
REVIEW_FIELDNAMES = (
    "review_schema_version",
    "example_id",
    "review_status",
    "reviewer",
    "reviewed_at_utc",
    "priority",
    "reason_codes",
    "env_id",
    "task_id",
    "episode_id",
    "step_index",
    "instruction",
    "action",
    "reward",
    "state_url",
    "state_title",
    "state_excerpt",
    "next_state_url",
    "next_state_title",
    "next_state_excerpt",
    "task_success",
    "stalled",
    "goal_deviation",
    "severe_failure",
    "invalid_action",
    "terminal",
    "subgoal_progress_t1",
    "notes",
)

_TEXT_REVIEW_FIELDS = frozenset(
    {
        "reviewer",
        "reason_codes",
        "env_id",
        "task_id",
        "episode_id",
        "instruction",
        "action",
        "state_url",
        "state_title",
        "state_excerpt",
        "next_state_url",
        "next_state_title",
        "next_state_excerpt",
        "notes",
    }
)


def _nested_text(value: Any) -> str:
    if isinstance(value, Mapping):
        if "text" in value:
            return str(value.get("text") or "")
        return " ".join(_nested_text(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return " ".join(_nested_text(item) for item in value)
    return str(value or "")


def _excerpt(value: Any, limit: int = 900) -> str:
    text = " ".join(_nested_text(value).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _bool_cell(value: float | bool) -> str:
    return "1" if bool(float(value)) else "0"


def _review_priority(record: Mapping[str, Any], example: Any) -> tuple[int, list[str]]:
    reasons: list[str] = []
    score = 0
    env_id = str(record.get("env_id", "")).lower()
    metadata = record.get("metadata") if isinstance(record.get("metadata"), Mapping) else {}
    if "webarena" in env_id:
        score += 10
        reasons.append("webarena")
    if metadata.get("observed_in_environment") and metadata.get("counterfactual_pair_id"):
        score += 8
        reasons.append("observed_counterfactual")
    if example.risks["severe_failure"] >= 0.5:
        score += 7
        reasons.append("severe_failure")
    if example.task_signals["terminal"] >= 0.5:
        score += 5
        reasons.append("terminal")
    if example.task_signals["invalid_action"] >= 0.5:
        score += 4
        reasons.append("invalid_action")
    if example.risks["stalled"] >= 0.5:
        score += 3
        reasons.append("stalled")
    if example.risks["goal_deviation"] >= 0.5:
        score += 3
        reasons.append("goal_deviation")
    if not reasons:
        reasons.append("coverage_sample")
    return score, reasons


def build_review_row(record: Mapping[str, Any]) -> dict[str, str]:
    """Create one editable queue row with current labels pre-filled."""

    example = canonicalize_transition(record)
    state = record.get("state") if isinstance(record.get("state"), Mapping) else {}
    next_state = (
        record.get("next_state")
        if isinstance(record.get("next_state"), Mapping)
        else {}
    )
    priority, reasons = _review_priority(record, example)
    return {
        "review_schema_version": "1",
        "example_id": example.example_id,
        "review_status": "pending",
        "reviewer": "",
        "reviewed_at_utc": "",
        "priority": str(priority),
        "reason_codes": ";".join(reasons),
        "env_id": str(record.get("env_id", "")),
        "task_id": example.task_id,
        "episode_id": example.episode_id,
        "step_index": str(example.step_index),
        "instruction": example.instruction,
        "action": example.action,
        "reward": str(float(record.get("reward", 0.0) or 0.0)),
        "state_url": str(state.get("url", "")),
        "state_title": str(state.get("title", "")),
        "state_excerpt": _excerpt(state.get("axtree") or state.get("dom")),
        "next_state_url": str(next_state.get("url", "")),
        "next_state_title": str(next_state.get("title", "")),
        "next_state_excerpt": _excerpt(
            next_state.get("axtree") or next_state.get("dom")
        ),
        "task_success": _bool_cell(example.risks["success"]),
        "stalled": _bool_cell(example.risks["stalled"]),
        "goal_deviation": _bool_cell(example.risks["goal_deviation"]),
        "severe_failure": _bool_cell(example.risks["severe_failure"]),
        "invalid_action": _bool_cell(example.task_signals["invalid_action"]),
        "terminal": _bool_cell(example.task_signals["terminal"]),
        "subgoal_progress_t1": str(example.task_signals["progress"]),
        "notes": "",
    }


def build_review_queue(
    records: Iterable[Mapping[str, Any]], *, limit: int | None = None
) -> list[dict[str, str]]:
    """Prioritise unique transitions deterministically for manual review."""

    by_id: dict[str, dict[str, str]] = {}
    for record in records:
        row = build_review_row(record)
        by_id.setdefault(row["example_id"], row)
    rows = sorted(
        by_id.values(),
        key=lambda row: (
            -int(row["priority"]),
            hashlib.sha256(row["example_id"].encode("utf-8")).hexdigest(),
        ),
    )
    return rows if limit is None else rows[: max(0, limit)]


def write_review_csv(path: str | Path, rows: Iterable[Mapping[str, Any]]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=REVIEW_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            cells: dict[str, Any] = {}
            for name in REVIEW_FIELDNAMES:
                value = row.get(name, "")
                if name in _TEXT_REVIEW_FIELDS and isinstance(value, str):
                    # Keep page/trajectory text inert when opened by spreadsheet software.
                    if value.lstrip().startswith(("=", "+", "-", "@")):
                        value = "'" + value
                cells[name] = value
            writer.writerow(cells)


def read_review_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        missing = set(REVIEW_FIELDNAMES) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"review CSV is missing columns: {sorted(missing)}")
        return [dict(row) for row in reader]


def _parse_binary(value: Any, *, field: str) -> bool:
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    raise ValueError(f"{field} must be 0/1 or true/false, got {value!r}")


def _validated_labels(
    row: Mapping[str, Any], *, expected_status: str
) -> dict[str, float | bool]:
    if str(row.get("review_status", "")).strip().lower() != expected_status:
        raise ValueError(f"review_status must be {expected_status}")
    if not str(row.get("reviewer", "")).strip():
        raise ValueError(f"{expected_status} review rows require a reviewer")
    labels: dict[str, float | bool] = {
        field: _parse_binary(row.get(field), field=field)
        for field in BOOLEAN_REVIEW_FIELDS
    }
    progress = float(row.get("subgoal_progress_t1", 0.0))
    if not -1.0 <= progress <= 1.0:
        raise ValueError("subgoal_progress_t1 must be in [-1, 1]")
    labels["subgoal_progress_t1"] = progress
    return labels


def validated_human_labels(row: Mapping[str, Any]) -> dict[str, float | bool]:
    """Validate labels from one explicitly human-approved review row."""

    return _validated_labels(row, expected_status="approved")


def validated_evidence_labels(row: Mapping[str, Any]) -> dict[str, float | bool]:
    """Validate labels approved by the reproducible evidence-review protocol."""

    return _validated_labels(row, expected_status="evidence_approved")


def apply_approved_reviews(
    records: Iterable[Mapping[str, Any]],
    review_rows: Iterable[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Return approved records while preserving human/evidence provenance."""

    approved: dict[str, tuple[str, Mapping[str, Any]]] = {}
    pending = 0
    status_counts: dict[str, int] = {"approved": 0, "evidence_approved": 0}
    for row in review_rows:
        status = str(row.get("review_status", "")).strip().lower()
        if status not in status_counts:
            pending += 1
            continue
        example_id = str(row.get("example_id", "")).strip()
        if not example_id:
            raise ValueError("approved review row is missing example_id")
        if example_id in approved:
            raise ValueError(f"duplicate approved review for {example_id}")
        if status == "approved":
            validated_human_labels(row)
        else:
            validated_evidence_labels(row)
        approved[example_id] = (status, row)
        status_counts[status] += 1

    output: list[dict[str, Any]] = []
    matched: set[str] = set()
    for source in records:
        example_id = canonicalize_transition(source).example_id
        approval = approved.get(example_id)
        if approval is None:
            continue
        status, row = approval
        labels = (
            validated_human_labels(row)
            if status == "approved"
            else validated_evidence_labels(row)
        )
        record = dict(source)
        record["labels"] = labels
        metadata = dict(source.get("metadata") or {})
        review_metadata = {
            "review_schema_version": int(row.get("review_schema_version", 1) or 1),
            "reviewer": str(row["reviewer"]).strip(),
            "reviewed_at_utc": str(row.get("reviewed_at_utc", "")).strip()
            or datetime.now(timezone.utc).isoformat(),
            "notes": str(row.get("notes", "")).strip(),
        }
        if status == "approved":
            record["label_source"] = "human_verified"
            metadata["human_review"] = review_metadata
        else:
            record["label_source"] = "evidence_verified"
            review_metadata["review_method"] = "codex_evidence_review_v1"
            review_metadata["human_signoff"] = False
            metadata["evidence_review"] = review_metadata
        record["metadata"] = metadata
        output.append(record)
        matched.add(example_id)

    missing = set(approved) - matched
    if missing:
        raise ValueError(
            f"{len(missing)} approved review rows did not match raw trajectories: "
            f"{sorted(missing)[:5]}"
        )
    return output, {
        "approved_rows": len(approved),
        "human_approved_rows": status_counts["approved"],
        "evidence_approved_rows": status_counts["evidence_approved"],
        "pending_or_rejected_rows": pending,
        "matched_records": len(output),
    }
