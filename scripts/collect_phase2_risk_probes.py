#!/usr/bin/env python3
"""Collect controlled invalid-target transitions for rare risk labels."""

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
os.chdir("/tmp")

import gymnasium as gym  # noqa: E402

from agent_world_model import (  # noqa: E402
    ActionDecision,
    BaselineConfig,
    run_baseline_episode,
)
from agent_world_model.baseline import register_browsergym_environment  # noqa: E402


class InvalidTargetProbeAgent:
    policy_name = "invalid_target_probe_v1"

    def decide(self, state, recent_actions=(), *, direct_answer=None) -> ActionDecision:
        return ActionDecision(
            action='click("phase2-missing-target", "left")',
            action_type="click",
            rationale="Controlled invalid-target probe for the invalid-action risk head.",
            target_bid="phase2-missing-target",
            target_name="<deliberately absent>",
            confidence=1.0,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "trajectories_phase2_risk",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT
        / "data"
        / "reports"
        / "phase2_risk_collection_latest.json",
    )
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--limit-episodes", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = (
        args.output_dir
        if args.output_dir.is_absolute()
        else PROJECT_ROOT / args.output_dir
    )
    report_path = args.report if args.report.is_absolute() else PROJECT_ROOT / args.report
    if not os.environ.get("MINIWOB_URL"):
        raise RuntimeError("MINIWOB_URL is not set; source the phase-one .env first")
    tasks = [
        "browsergym/miniwob.click-button",
        "browsergym/miniwob.click-link",
        "browsergym/miniwob.click-option",
        "browsergym/miniwob.click-test",
        "browsergym/miniwob.click-tab",
        "browsergym/miniwob.enter-text",
        "browsergym/miniwob.focus-text",
        "browsergym/miniwob.choose-list",
        "browsergym/miniwob.search-engine",
        "browsergym/miniwob.login-user",
    ]
    planned = [(task, seed) for task in tasks for seed in range(args.seeds)]
    if args.limit_episodes is not None:
        planned = planned[: args.limit_episodes]
    results, failures = [], []
    for task in tasks:
        runs = [seed for current_task, seed in planned if current_task == task]
        if not runs:
            continue
        register_browsergym_environment(task)
        env = gym.make(task, headless=True)
        try:
            for seed in runs:
                try:
                    result = run_baseline_episode(
                        BaselineConfig(env_id=task, seed=seed, max_steps=1),
                        output_dir=output_dir,
                        env=env,
                        agent=InvalidTargetProbeAgent(),
                    )
                    results.append(result.to_dict())
                except Exception as error:
                    failures.append(
                        {"env_id": task, "seed": seed, "error": repr(error)}
                    )
        finally:
            env.close()
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "planned_episodes": len(planned),
        "completed_episodes": len(results),
        "failed_episodes": len(failures),
        "transition_count": sum(int(item["steps"]) for item in results),
        "results": results,
        "failures": failures,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {key: value for key, value in report.items() if key not in {"results", "failures"}},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
