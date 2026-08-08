#!/usr/bin/env python3
"""Audit one or more raw trajectory directories without replaying episodes."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_world_model.phase2_schema import canonicalize_transition  # noqa: E402
from agent_world_model.trajectory import load_trajectory  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    files: list[Path] = []
    for item in args.inputs:
        path = item if item.is_absolute() else PROJECT_ROOT / item
        files.extend(path.rglob("*.jsonl") if path.is_dir() else [path])
    records = [record for path in sorted(set(files)) for record in load_trajectory(path)]
    examples = [canonicalize_transition(record) for record in records]
    task_counts = Counter(example.task_id for example in examples)
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_directories": [str(item) for item in args.inputs],
        "trajectory_file_count": len(set(files)),
        "transition_count": len(records),
        "episode_count": len({example.episode_id for example in examples}),
        "task_count": len(task_counts),
        "task_counts": dict(task_counts),
        "positive_label_counts": {
            "success": sum(example.risks["success"] >= 0.5 for example in examples),
            "stalled": sum(example.risks["stalled"] >= 0.5 for example in examples),
            "goal_deviation": sum(example.risks["goal_deviation"] >= 0.5 for example in examples),
            "severe_failure": sum(example.risks["severe_failure"] >= 0.5 for example in examples),
            "invalid_action": sum(example.task_signals["invalid_action"] >= 0.5 for example in examples),
            "terminal": sum(example.task_signals["terminal"] >= 0.5 for example in examples),
        },
        "counterfactual_pair_count": len({
            str(example.metadata.get("counterfactual_pair_id"))
            for example in examples
            if example.metadata.get("counterfactual_pair_id")
        }),
    }
    output = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
