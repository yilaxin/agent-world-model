#!/usr/bin/env python3
"""Summarise the round-3 AndroidWorld W4 expansion with Wilson 95% CIs."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def wilson_ci(successes: int, episodes: int, z: float = 1.96) -> list[float]:
    if episodes <= 0:
        return [0.0, 0.0]
    p = successes / episodes
    denominator = 1 + z * z / episodes
    centre = (p + z * z / (2 * episodes)) / denominator
    margin = (
        z
        * math.sqrt(p * (1 - p) / episodes + z * z / (4 * episodes * episodes))
        / denominator
    )
    return [max(0.0, centre - margin), min(1.0, centre + margin)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "data/reports/androidworld_task_eval_w4_round3.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data/reports/androidworld_task_eval_w4_round3_analysis.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    summary = report["summary"]["released_w4"]
    per_task = summary["per_task"]
    task_rows = []
    total_successes = 0
    total_episodes = 0
    for task_name in report["tasks"]:
        row = per_task[task_name]
        successes = round(float(row["success_rate"]) * int(row["episodes"]))
        episodes = int(row["episodes"])
        total_successes += successes
        total_episodes += episodes
        task_rows.append(
            {
                "task": task_name,
                "episodes": episodes,
                "successes": successes,
                "success_rate": row["success_rate"],
                "wilson_95ci": wilson_ci(successes, episodes),
                "action_execution_rate": row["action_execution_rate"],
            }
        )
    analysis = {
        "schema_version": 1,
        "source_report": str(args.report.relative_to(ROOT)),
        "agent": "released_w4",
        "episodes_per_task": report.get("episodes_per_task"),
        "platform": report.get("platform"),
        "unified_reset": True,
        "confidence_interval_method": "wilson_95",
        "overall": {
            "episodes": total_episodes,
            "successes": total_successes,
            "success_rate": total_successes / total_episodes,
            "wilson_95ci": wilson_ci(total_successes, total_episodes),
        },
        "per_task": task_rows,
        "interpretation_limits": [
            "AndroidWorld results are a small migration check, not a statistical cross-platform proof.",
            "Success is read from Android system/foreground state via ADB, not an LLM judge.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(analysis, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(analysis, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
