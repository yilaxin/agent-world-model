#!/usr/bin/env python3
"""Run the fixed phase-one baseline suite and emit a machine-readable report."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# NLTK's safe-path guard rejects an in-project virtualenv as the import CWD.
os.chdir("/tmp")

from agent_world_model import (  # noqa: E402
    BaselineConfig,
    EncoderConfig,
    StateEncoderV1,
    run_baseline_episode,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--suite",
        choices=("all", "miniwob", "webarena"),
        default="all",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "configs" / "phase1_baseline.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "trajectories",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "data" / "reports" / "phase1_latest.json",
    )
    return parser.parse_args()


def _required_environment(task_name: str) -> str | None:
    if task_name == "miniwob":
        return "MINIWOB_URL"
    if task_name == "webarena":
        return "WA_REDDIT"
    return None


def main() -> int:
    args = parse_args()
    config_data = json.loads(args.config.read_text(encoding="utf-8"))
    task_names = (
        ["miniwob", "webarena"] if args.suite == "all" else [args.suite]
    )
    encoder_data = config_data["state_encoder"]
    encoder = StateEncoderV1(
        EncoderConfig(
            dimensions=int(encoder_data["dimensions"]),
            recent_action_count=int(encoder_data["recent_action_count"]),
        )
    )

    results = []
    for task_name in task_names:
        required_key = _required_environment(task_name)
        if required_key and not os.environ.get(required_key):
            raise RuntimeError(
                f"{required_key} is not set. Source the matching .env file first."
            )
        task = config_data["tasks"][task_name]
        result = run_baseline_episode(
            BaselineConfig(
                env_id=task["env_id"],
                seed=int(task["seed"]),
                max_steps=int(task["max_steps"]),
                headless=bool(config_data["runtime"]["headless"]),
                direct_answer=task.get("direct_answer"),
            ),
            output_dir=args.output_dir,
            encoder=encoder,
        )
        results.append(result.to_dict())
        print(
            f"{task_name}: success={result.success}, reward={result.total_reward}, "
            f"steps={result.steps}, trajectory={result.trajectory_path}"
        )

    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": config_data,
        "results": results,
        "all_passed": all(result["success"] for result in results),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Report: {args.report}")
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
