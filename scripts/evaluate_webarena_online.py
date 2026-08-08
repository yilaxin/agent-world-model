#!/usr/bin/env python3
"""Run a reproducible, evaluator-backed WebArena Reddit evaluation.

The report separates an autonomous reactive baseline from an answer-injection
evaluator smoke test.  Only the former is reported as Agent success rate.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir("/tmp")

from agent_world_model import BaselineConfig, run_baseline_episode  # noqa: E402
from agent_world_model.remote_agent import RemotePhase3Agent  # noqa: E402
from agent_world_model.trajectory import load_trajectory  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "configs" / "webarena_reddit_eval.json")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data" / "trajectories_webarena_eval")
    parser.add_argument("--report", type=Path, default=PROJECT_ROOT / "data" / "reports" / "webarena_online_evaluation_latest.json")
    parser.add_argument(
        "--mode",
        choices=("reactive", "phase3", "evaluator-smoke", "both", "all"),
        default="both",
    )
    parser.add_argument("--remote-agent-url", default="http://127.0.0.1:18765")
    return parser.parse_args()


def _run_one(
    env_id: str,
    seed: int,
    max_steps: int,
    output_dir: Path,
    direct_answer: str | None,
    agent: Any | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    result = run_baseline_episode(
        BaselineConfig(
            env_id=env_id,
            seed=seed,
            max_steps=max_steps,
            direct_answer=direct_answer,
        ),
        output_dir=output_dir,
        agent=agent,
    )
    records = load_trajectory(result.trajectory_path)
    action_errors = sum(
        bool(str(row.get("next_state", {}).get("last_action_error", "") or ""))
        or bool(row.get("info", {}).get("action_error"))
        or bool(row.get("info", {}).get("action_exec_error"))
        for row in records
    )
    return {
        **result.to_dict(),
        "elapsed_seconds": time.perf_counter() - started,
        "attempted_actions": len(records),
        "action_execution_successes": len(records) - action_errors,
    }


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_actions = sum(row["attempted_actions"] for row in rows)
    return {
        "episodes": len(rows),
        "successes": sum(bool(row["success"]) for row in rows),
        "success_rate": sum(bool(row["success"]) for row in rows) / max(1, len(rows)),
        "action_execution_rate": sum(row["action_execution_successes"] for row in rows) / max(1, total_actions),
        "average_steps": sum(row["steps"] for row in rows) / max(1, len(rows)),
        "average_latency_seconds": sum(row["elapsed_seconds"] for row in rows) / max(1, len(rows)),
    }


def main() -> int:
    args = parse_args()
    required = [
        "WA_SHOPPING", "WA_SHOPPING_ADMIN", "WA_REDDIT", "WA_GITLAB",
        "WA_WIKIPEDIA", "WA_MAP", "WA_HOMEPAGE",
    ]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"missing WebArena environment variables: {', '.join(missing)}")
    config_path = args.config if args.config.is_absolute() else PROJECT_ROOT / args.config
    output_dir = args.output_dir if args.output_dir.is_absolute() else PROJECT_ROOT / args.output_dir
    report_path = args.report if args.report.is_absolute() else PROJECT_ROOT / args.report
    config = json.loads(config_path.read_text(encoding="utf-8"))
    task_ids = [int(item) for item in config["task_ids"]]
    seeds = [int(item) for item in config["seeds"]]
    if args.mode == "both":
        modes = ["reactive", "evaluator-smoke"]
    elif args.mode == "all":
        modes = ["reactive", "phase3", "evaluator-smoke"]
    else:
        modes = [args.mode]
    remote_agent = RemotePhase3Agent(args.remote_agent_url) if "phase3" in modes else None
    results: dict[str, list[dict[str, Any]]] = {mode: [] for mode in modes}
    failures: list[dict[str, Any]] = []
    for mode in modes:
        for task_id in task_ids:
            for seed in seeds:
                env_id = f"browsergym/webarena.{task_id}"
                direct_answer = None
                max_steps = int(config["reactive_step_budget"])
                episode_agent = remote_agent if mode == "phase3" else None
                if mode == "phase3":
                    max_steps = int(config.get("world_model_step_budget", config["reactive_step_budget"]))
                if mode == "evaluator-smoke":
                    direct_answer = str(config["evaluator_smoke_answers"][str(task_id)])
                    max_steps = int(config["evaluator_smoke_step_budget"])
                try:
                    row = _run_one(
                        env_id,
                        seed,
                        max_steps,
                        output_dir / mode,
                        direct_answer,
                        episode_agent,
                    )
                    row.update({"mode": mode, "task_id": task_id, "uses_expected_answer": direct_answer is not None})
                    results[mode].append(row)
                    print(f"mode={mode} task={task_id} seed={seed} success={row['success']} steps={row['steps']}")
                except Exception as error:
                    failures.append({"mode": mode, "task_id": task_id, "seed": seed, "error": repr(error)})
    metrics = {mode: _summarize(rows) for mode, rows in results.items()}
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "benchmark": config["benchmark"],
        "fixed_task_ids": task_ids,
        "fixed_seeds": seeds,
        "budgets": {
            "reactive_steps": config["reactive_step_budget"],
            "evaluator_smoke_steps": config["evaluator_smoke_step_budget"],
        },
        "agent_metrics": metrics.get("reactive"),
        "world_model_agent_metrics": metrics.get("phase3"),
        "evaluator_integrity_metrics": metrics.get("evaluator-smoke"),
        "agent_success_rate_excludes_answer_injection": True,
        "scope_limit": "Reddit-only retrieval subset; not the full multi-site WebArena benchmark.",
        "results": results,
        "failures": failures,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key not in {"results", "failures"}}, ensure_ascii=False, indent=2))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
