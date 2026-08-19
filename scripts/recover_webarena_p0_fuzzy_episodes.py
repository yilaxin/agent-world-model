#!/usr/bin/env python3
"""Recover P0 trajectories blocked by BrowserGym's no-answer fuzzy validation.

BrowserGym validates once during reset and after every browser action.  For a
fuzzy string task it substitutes the literal answer ``whatever`` when the
agent has not submitted a message, which unnecessarily calls the external LLM
judge.  This recovery runner short-circuits only that no-answer state to a
deterministic non-terminal score of zero.  If the agent actually submits an
answer, the original official evaluator is called and no local answer judge is
substituted.

The runner is post-freeze evidence orchestration.  It does not change tasks,
the agent release, candidate generation, weights, guard, seed, or step budget.
"""

from __future__ import annotations

import argparse
import hashlib
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


RECOVERY_TASKS = {
    "gitlab": [173],
    "reddit": [723],
    "shopping": [795, 332, 301, 47, 24],
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", choices=tuple(RECOVERY_TASKS), required=True)
    parser.add_argument("--mode", choices=("reactive", "world-model"), required=True)
    parser.add_argument("--navigation-guard", choices=("on", "off"), required=True)
    parser.add_argument("--remote-agent-url", default="http://localhost:18761")
    parser.add_argument(
        "--manifest", type=Path,
        default=ROOT / "configs" / "webarena_p0_holdout_frozen.json",
    )
    parser.add_argument(
        "--output-dir", type=Path,
        default=ROOT / "data" / "trajectories_webarena_p0_recovery",
    )
    parser.add_argument(
        "--report-dir", type=Path, default=ROOT / "data" / "reports",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    expected_ids = RECOVERY_TASKS[args.site]
    if not set(expected_ids).issubset(
        set(manifest["selected_task_ids_by_site"][args.site])
    ):
        raise ValueError("recovery task is not in the frozen holdout")
    if int(manifest["step_budget_per_episode"]) != 12 or manifest["seeds"] != [0]:
        raise ValueError("unexpected frozen budget or seed")
    if manifest["task_feedback_used"] or not manifest["frozen_before_any_holdout_episode"]:
        raise ValueError("manifest is not the intended unseen holdout")

    original_validate = GenericWebArenaTask.validate

    def validate_no_answer_as_zero(
        task: GenericWebArenaTask, page: Any, chat_messages: list[dict[str, Any]]
    ) -> tuple[float, bool, str, dict[str, Any]]:
        if not chat_messages or chat_messages[-1].get("role") not in {
            "assistant", "infeasible"
        }:
            return 0.0, False, "", {
                "p0_no_answer_fuzzy_short_circuit": True,
            }
        return original_validate(task, page, chat_messages)

    GenericWebArenaTask.validate = validate_no_answer_as_zero

    guard_bool = args.navigation_guard == "on"
    agent: Any = ReactiveAgent(navigation_guard=guard_bool)
    remote_health = None
    if args.mode == "world-model":
        agent = RemotePhase3Agent(args.remote_agent_url)
        remote_health = agent.health()
        if remote_health.get("status") != "ok":
            raise ValueError(f"unhealthy remote agent: {remote_health}")
        if remote_health.get("navigation_guard") != args.navigation_guard:
            raise ValueError(f"remote guard mismatch: {remote_health}")
        if bool(remote_health.get("semantic_goal_priority")):
            raise ValueError("semantic goal override must be disabled")
        if (
            remote_health.get("release_fingerprint_sha256")
            != manifest["release"]["sha256"]
        ):
            raise ValueError("remote release fingerprint mismatch")

    rows = []
    failures = []
    trajectory_dir = (
        args.output_dir
        / args.site
        / f"{args.mode}_guard_{args.navigation_guard}"
        / args.mode
    )
    for task_id in expected_ids:
        try:
            row = _run_one(
                f"browsergym/webarena.{task_id}",
                0,
                12,
                trajectory_dir,
                None,
                agent,
                max_attempts=2,
            )
            row.update({
                "mode": args.mode,
                "task_id": task_id,
                "site": args.site,
                "uses_expected_answer": False,
                "recovery_validation_adapter": "no_answer_is_nonterminal_zero",
            })
            rows.append(row)
            print(
                f"mode={args.mode} task={task_id} success={row['success']} "
                f"steps={row['steps']}"
            )
        except Exception as error:
            failures.append({
                "mode": args.mode,
                "task_id": task_id,
                "seed": 0,
                "error": repr(error),
            })

    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "recover trajectories blocked by no-answer fuzzy evaluator initialization",
        "site": args.site,
        "mode": args.mode,
        "navigation_guard": args.navigation_guard,
        "task_ids": expected_ids,
        "seed": 0,
        "step_budget": 12,
        "freeze_sha256": manifest["freeze_sha256"],
        "site_config_freeze_sha256": manifest["site_config_freeze_sha256"][args.site],
        "release_fingerprint_sha256": manifest["release"]["sha256"],
        "remote_agent_health": remote_health,
        "uses_expected_answer": False,
        "validation_adapter": {
            "rule": "Only no-answer validation is short-circuited to score=0, done=false; any submitted answer delegates to the original official evaluator.",
            "reference_answers_read": False,
            "local_answer_judge_used": False,
        },
        "results": rows,
        "failures": failures,
    }
    report_path = args.report_dir / (
        f"webarena_p0_recovery_{args.site}_{args.mode}_guard_"
        f"{args.navigation_guard}.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "report": str(report_path),
        "report_sha256": sha256(report_path),
        "rows": len(rows),
        "failures": len(failures),
    }, ensure_ascii=False, indent=2))
    return 0 if not failures and len(rows) == len(expected_ids) else 2


if __name__ == "__main__":
    raise SystemExit(main())
