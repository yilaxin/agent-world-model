#!/usr/bin/env python3
"""Run the fixed WebArena smoke task and save its evaluator-backed trajectory."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir("/tmp")

from agent_world_model import BaselineConfig, run_baseline_episode  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-id", default="browsergym/webarena.27")
    parser.add_argument("--answer", default="0")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-steps", type=int, default=2)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "trajectories",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_baseline_episode(
        BaselineConfig(
            env_id=args.env_id,
            seed=args.seed,
            max_steps=args.max_steps,
            direct_answer=args.answer,
        ),
        output_dir=args.output_dir,
    )
    print("Trajectory:", result.trajectory_path)
    print("Evaluator success:", result.success)
    print("Reward:", result.total_reward)
    print("Steps:", result.steps)
    print("Screenshot pixels stored: no")


if __name__ == "__main__":
    main()
