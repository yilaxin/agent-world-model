#!/usr/bin/env python3
"""Recover development tasks blocked by no-answer fuzzy evaluator startup."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir("/tmp")

from agent_world_model import ReactiveAgent  # noqa: E402
from agent_world_model.remote_agent import RemotePhase3Agent  # noqa: E402
from browsergym.webarena.task import GenericWebArenaTask  # noqa: E402
from scripts.evaluate_webarena_online import _run_one  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--task-ids", type=int, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--mode", choices=("reactive", "world-model"), default="reactive"
    )
    parser.add_argument("--remote-agent-url", default="http://127.0.0.1:18761")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data/trajectories_webarena_round2_dev_recovery",
    )
    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    config = json.loads(config_path.read_text(encoding="utf-8"))
    configured = {int(item) for item in config["task_ids"]}
    if not set(args.task_ids).issubset(configured):
        raise ValueError("recovery task is not in the development config")

    original_validate = GenericWebArenaTask.validate

    def validate_no_answer_as_zero(
        task: GenericWebArenaTask, page: Any, chat_messages: list[dict[str, Any]]
    ) -> tuple[float, bool, str, dict[str, Any]]:
        if not chat_messages or chat_messages[-1].get("role") not in {
            "assistant", "infeasible"
        }:
            return 0.0, False, "", {"round2_dev_no_answer_short_circuit": True}
        return original_validate(task, page, chat_messages)

    GenericWebArenaTask.validate = validate_no_answer_as_zero
    remote_health = None
    if args.mode == "world-model":
        agent = RemotePhase3Agent(
            args.remote_agent_url,
            bearer_token=os.environ.get("AGENT_WORLD_MODEL_AUTH_TOKEN") or None,
        )
        remote_health = agent.health()
        if remote_health.get("navigation_guard") != "on":
            raise RuntimeError("remote navigation guard must be on for this dev recovery")
        if bool(remote_health.get("semantic_goal_priority")):
            raise RuntimeError("semantic_goal_priority must remain disabled")
        expected_release = str(config.get("release_fingerprint_sha256", ""))
        if remote_health.get("release_fingerprint_sha256") != expected_release:
            raise RuntimeError("remote release fingerprint mismatch")
    else:
        agent = ReactiveAgent(navigation_guard=True)
    rows, failures = [], []
    out_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    max_steps = int(
        config["world_model_step_budget"]
        if args.mode == "world-model"
        else config["reactive_step_budget"]
    )
    for task_id in args.task_ids:
        try:
            row = _run_one(
                f"browsergym/webarena.{task_id}", 0,
                max_steps, out_dir, None, agent,
                max_attempts=int(config.get("episode_max_attempts", 2)),
            )
            row.update({"task_id": task_id, "mode": args.mode, "site": "shopping"})
            rows.append(row)
            print(f"task={task_id} success={row['success']} steps={row['steps']}")
        except Exception as error:
            failures.append({"task_id": task_id, "error": repr(error)})
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "development-only recovery of no-answer fuzzy evaluator initialization",
        "validation_adapter": (
            "No-answer validation returns score=0, done=false; submitted answers use the official evaluator."
        ),
        "uses_reference_answers": False,
        "mode": args.mode,
        "freeze_sha256": config.get("freeze_sha256"),
        "release_fingerprint_sha256": config.get("release_fingerprint_sha256"),
        "remote_agent_health": remote_health,
        "results": rows,
        "failures": failures,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
