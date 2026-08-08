#!/usr/bin/env python3
"""Create one inspectable decision from the complete phase-three Agent."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_world_model.phase3_agent import Phase3WorldModelAgent  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=PROJECT_ROOT / "artifacts" / "phase2" / "world_model_best_gpu.pt",
    )
    parser.add_argument("--device", default="auto")
    parser.add_argument("--trajectory", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "reports" / "phase3_demo_latest.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    trajectory = args.trajectory
    if trajectory is None:
        trajectory = next((PROJECT_ROOT / "data" / "trajectories_phase2").glob("*.jsonl"))
    record = json.loads(trajectory.read_text(encoding="utf-8").splitlines()[0])
    agent = Phase3WorldModelAgent(args.checkpoint, device=args.device)
    decision = agent.decide(record["state"])
    report = {
        "trajectory": str(trajectory),
        "task_id": record["env_id"],
        "instruction": record["state"]["goal"],
        "recorded_action": record["action"],
        "decision": decision.to_dict(),
        "phase_boundary": "No feedback/regret parameter update is performed in phase three.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
