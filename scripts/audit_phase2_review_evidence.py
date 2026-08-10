#!/usr/bin/env python3
"""Audit a phase-two review queue against its raw trajectory evidence.

This command is deliberately read-only: it never changes review statuses or
labels.  Its compact JSON report is suitable for deciding which rows can be
evidence-reviewed and which still require a person to inspect them.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_world_model.human_review import read_review_csv  # noqa: E402
from agent_world_model.phase2_schema import canonicalize_transition  # noqa: E402
from agent_world_model.trajectory import iter_trajectory  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sample-limit", type=int, default=12)
    return parser.parse_args()


def _files(inputs: list[Path]) -> list[Path]:
    files: set[Path] = set()
    for item in inputs:
        path = item if item.is_absolute() else PROJECT_ROOT / item
        if path.is_dir():
            files.update(path.rglob("*.jsonl"))
        elif path.is_file():
            files.add(path)
    return sorted(path for path in files if path.is_file())


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _selected_info(info: Any) -> dict[str, Any]:
    if not isinstance(info, Mapping):
        return {}
    selected: dict[str, Any] = {}
    for key, value in info.items():
        lowered = str(key).lower()
        if any(token in lowered for token in ("success", "fail", "error", "invalid", "reward")):
            if value is None or isinstance(value, (bool, int, float, str)):
                selected[str(key)] = value
    return selected


def main() -> int:
    args = parse_args()
    review_path = args.reviews if args.reviews.is_absolute() else PROJECT_ROOT / args.reviews
    output_path = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    rows = read_review_csv(review_path)
    wanted = {row["example_id"] for row in rows}
    matches: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    transition_count = 0
    files = _files(args.inputs)
    for path in files:
        for record in iter_trajectory(path):
            transition_count += 1
            example_id = canonicalize_transition(record).example_id
            if example_id in wanted:
                matches[example_id].append((str(path), record))

    condition_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    intervention_counts: Counter[str] = Counter()
    env_counts: Counter[str] = Counter()
    info_key_counts: Counter[str] = Counter()
    failure_reasons: Counter[str] = Counter()
    samples: list[dict[str, Any]] = []
    evidence_ready_ids: list[str] = []

    for row in rows:
        example_id = row["example_id"]
        found = matches.get(example_id, [])
        if len(found) == 0:
            condition_counts["unmatched"] += 1
            failure_reasons["raw_record_not_found"] += 1
            continue
        if len(found) > 1:
            condition_counts["duplicate_match"] += 1
            failure_reasons["raw_record_not_unique"] += 1
            continue
        source_path, record = found[0]
        metadata = record.get("metadata") if isinstance(record.get("metadata"), Mapping) else {}
        terminated = _truthy(record.get("terminated"))
        truncated = _truthy(record.get("truncated"))
        done = _truthy(record.get("done", terminated or truncated))
        reward = float(record.get("reward", 0.0) or 0.0)
        observed = _truthy(metadata.get("observed_in_environment"))
        pair_id = str(metadata.get("counterfactual_pair_id", "")).strip()
        role = str(metadata.get("counterfactual_role", "")).strip() or "<missing>"
        intervention = str(metadata.get("intervention_type", "")).strip() or "<missing>"
        raw_labels = record.get("labels") if isinstance(record.get("labels"), Mapping) else {}
        label_terminal = _truthy(raw_labels.get("terminal", done))
        label_success = _truthy(raw_labels.get("task_success", terminated and reward > 0.0))
        label_severe = _truthy(raw_labels.get("severe_failure", done and reward <= 0.0))
        info = _selected_info(record.get("info"))
        for key in info:
            info_key_counts[key] += 1
        role_counts[role] += 1
        intervention_counts[intervention] += 1
        env_counts[str(record.get("env_id", ""))] += 1

        checks = {
            "unique_raw_match": True,
            "observed_in_environment": observed,
            "counterfactual_pair_id_present": bool(pair_id),
            "terminal_outcome": bool(done and label_terminal),
            "non_success": not label_success,
            "non_positive_reward": reward <= 0.0,
            "severe_failure_label": label_severe,
            "queue_labels_match_raw": all(
                str(row.get(name, "")).strip() == ("1" if _truthy(raw_labels.get(name, fallback)) else "0")
                for name, fallback in {
                    "task_success": label_success,
                    "stalled": False,
                    "goal_deviation": reward < 0.0,
                    "severe_failure": label_severe,
                    "invalid_action": False,
                    "terminal": label_terminal,
                }.items()
            ),
        }
        ready = all(checks.values())
        if ready:
            evidence_ready_ids.append(example_id)
            condition_counts["evidence_ready"] += 1
        else:
            condition_counts["needs_human"] += 1
            for name, passed in checks.items():
                if not passed:
                    failure_reasons[name] += 1

        if len(samples) < max(0, args.sample_limit):
            samples.append(
                {
                    "example_id": example_id,
                    "source_file": source_path,
                    "env_id": record.get("env_id", ""),
                    "action": record.get("action", ""),
                    "reward": reward,
                    "terminated": terminated,
                    "truncated": truncated,
                    "done": done,
                    "counterfactual_role": role,
                    "intervention_type": intervention,
                    "observed_in_environment": observed,
                    "pair_id": pair_id,
                    "raw_labels": raw_labels,
                    "selected_info": info,
                    "checks": checks,
                }
            )

    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "review_csv": str(review_path),
        "source_file_count": len(files),
        "source_transition_count": transition_count,
        "queue_row_count": len(rows),
        "matched_example_count": len(matches),
        "match_multiplicity": dict(Counter(len(value) for value in matches.values())),
        "condition_counts": dict(condition_counts),
        "failure_reasons": dict(failure_reasons),
        "counterfactual_role_counts": dict(role_counts),
        "intervention_type_counts": dict(intervention_counts),
        "environment_counts": dict(env_counts),
        "selected_info_key_counts": dict(info_key_counts),
        "evidence_ready_example_ids": evidence_ready_ids,
        "samples": samples,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key not in {"samples", "evidence_ready_example_ids"}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
