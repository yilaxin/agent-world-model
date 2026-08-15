#!/usr/bin/env python3
"""Run a reproducible, evaluator-backed WebArena multi-site evaluation.

The BrowserGym environment supplies classic WebArena task definitions and URL
evaluation while Verified images supply the local sites.  The report separates
autonomous agents from an answer-injection evaluator smoke test.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir("/tmp")

from agent_world_model import BaselineConfig, ReactiveAgent, run_baseline_episode  # noqa: E402
from agent_world_model.experiment_stats import compare_success_rates  # noqa: E402
from agent_world_model.remote_agent import RemotePhase3Agent  # noqa: E402
from agent_world_model.trajectory import load_trajectory  # noqa: E402


class _WatchdogTimeout(TimeoutError):
    pass


class _EpisodeWatchdog:
    """POSIX SIGALRM-based per-episode wall-clock watchdog.

    Playwright's sync API must run on the main thread, so the watchdog uses a
    main-thread timer signal instead of a helper thread.
    """

    def __init__(self, seconds: float) -> None:
        self.seconds = max(0.0, float(seconds))

    def _alarm(self, signum: int, frame: object) -> None:
        raise _WatchdogTimeout(
            f"episode exceeded {self.seconds:.0f}s watchdog"
        )

    def __enter__(self) -> "_EpisodeWatchdog":
        if self.seconds > 0.0 and hasattr(signal, "SIGALRM"):
            signal.signal(signal.SIGALRM, self._alarm)
            signal.setitimer(signal.ITIMER_REAL, self.seconds)
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if hasattr(signal, "SIGALRM"):
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, signal.SIG_DFL)
        return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "configs" / "webarena_multisite_eval.json")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data" / "trajectories_webarena_eval")
    parser.add_argument("--report", type=Path, default=PROJECT_ROOT / "data" / "reports" / "webarena_online_evaluation_latest.json")
    parser.add_argument(
        "--mode",
        choices=("reactive", "world-model", "phase3", "evaluator-smoke", "both", "all"),
        default="both",
    )
    parser.add_argument("--remote-agent-url", default="http://127.0.0.1:18765")
    parser.add_argument(
        "--navigation-guard",
        choices=("on", "off"),
        required=True,
        help="Frozen 2x2 factor applied identically to reactive and W4.",
    )
    parser.add_argument(
        "--reactive-step-budget",
        type=int,
        default=None,
        help="Optional baseline budget override for matched-benchmark runs.",
    )
    parser.add_argument(
        "--world-model-step-budget",
        type=int,
        default=None,
        help="Optional candidate budget override for matched-benchmark runs.",
    )
    parser.add_argument(
        "--episode-timeout-seconds",
        type=float,
        default=300.0,
        help="Wall-clock watchdog per episode; hung episodes are recorded as failures.",
    )
    return parser.parse_args()


def _run_one(
    env_id: str,
    seed: int,
    max_steps: int,
    output_dir: Path,
    direct_answer: str | None,
    agent: Any | None = None,
    max_attempts: int = 1,
    episode_timeout_seconds: float = 300.0,
) -> dict[str, Any]:
    started = time.perf_counter()
    attempt = 0
    while True:
        attempt += 1
        try:
            with _EpisodeWatchdog(episode_timeout_seconds):
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
            break
        except Exception as error:
            detail = str(error)
            transient_reset = (
                "Page.goto: Timeout" in detail
                or (
                    "Locator.click: Timeout" in detail
                    and 'get_by_role("button", name="Sign in")' in detail
                    and "waiting for scheduled navigations to finish" in detail
                )
            )
            if not transient_reset or attempt >= max_attempts:
                raise
            print(
                f"retrying transient reset env={env_id} seed={seed} "
                f"attempt={attempt + 1}/{max_attempts}: {error!r}"
            )
            time.sleep(2.0)
    records = load_trajectory(result.trajectory_path)
    action_errors = sum(
        bool(
            str(row.get("next_state", {}).get("last_action_error", "") or "")
            and not bool(row.get("reward", 0.0))
        )
        or bool(row.get("info", {}).get("action_error"))
        or bool(row.get("info", {}).get("action_exec_error"))
        for row in records
    )
    return {
        **result.to_dict(),
        "elapsed_seconds": time.perf_counter() - started,
        "attempted_actions": len(records),
        "action_execution_successes": len(records) - action_errors,
        "episode_attempts": attempt,
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


def _summarize_by_site(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    sites = sorted({str(row.get("site", "unknown")) for row in rows})
    return {
        site: _summarize([row for row in rows if str(row.get("site", "unknown")) == site])
        for site in sites
    }


def _paired_success(rows: list[dict[str, Any]]) -> dict[str, float]:
    return {
        f"{row['task_id']}:{row['seed']}": float(bool(row["success"]))
        for row in rows
    }


def main() -> int:
    args = parse_args()
    config_path = args.config if args.config.is_absolute() else PROJECT_ROOT / args.config
    output_dir = args.output_dir if args.output_dir.is_absolute() else PROJECT_ROOT / args.output_dir
    report_path = args.report if args.report.is_absolute() else PROJECT_ROOT / args.report
    config = json.loads(config_path.read_text(encoding="utf-8"))
    freeze_payload = dict(config)
    declared_freeze_sha = str(freeze_payload.pop("freeze_sha256", ""))
    computed_freeze_sha = hashlib.sha256(
        json.dumps(
            freeze_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    if not declared_freeze_sha or declared_freeze_sha != computed_freeze_sha:
        raise RuntimeError(
            "holdout freeze hash mismatch: "
            f"declared={declared_freeze_sha!r}, computed={computed_freeze_sha!r}"
        )
    site_environment_variables = {
        "shopping": "WA_SHOPPING",
        "shopping_admin": "WA_SHOPPING_ADMIN",
        "reddit": "WA_REDDIT",
        "gitlab": "WA_GITLAB",
        "wikipedia": "WA_WIKIPEDIA",
        "map": "WA_MAP",
        "homepage": "WA_HOMEPAGE",
    }
    required_sites = list(config.get("required_sites", []))
    required = [site_environment_variables[site] for site in required_sites]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"missing WebArena environment variables: {', '.join(missing)}")
    invalid_sites = [
        site
        for site in required_sites
        if site not in site_environment_variables
        or os.environ.get(site_environment_variables[site], "").strip().lower()
        in {"", "todo", "unset", "none"}
    ]
    if invalid_sites:
        raise RuntimeError(
            "WebArena sites are not configured with real URLs: " + ", ".join(invalid_sites)
        )
    task_ids = [int(item) for item in config["task_ids"]]
    task_sites = {str(key): str(value) for key, value in config.get("task_sites", {}).items()}
    if task_sites and set(task_sites) != {str(item) for item in task_ids}:
        raise ValueError("task_sites must map every and only configured task_id")
    seeds = [int(item) for item in config["seeds"]]
    if args.mode == "both":
        modes = ["reactive", "world-model"]
    elif args.mode == "all":
        modes = ["reactive", "world-model", "evaluator-smoke"]
    else:
        modes = ["world-model" if args.mode == "phase3" else args.mode]
    navigation_guard = args.navigation_guard == "on"
    reactive_agent = ReactiveAgent(navigation_guard=navigation_guard)
    remote_agent = (
        RemotePhase3Agent(
            args.remote_agent_url,
            bearer_token=os.environ.get("AGENT_WORLD_MODEL_AUTH_TOKEN") or None,
        )
        if "world-model" in modes
        else None
    )
    remote_health = None
    if remote_agent is not None:
        remote_health = remote_agent.health()
        if remote_health.get("navigation_guard") != args.navigation_guard:
            raise RuntimeError(
                "remote navigation_guard does not match experiment label: "
                f"expected={args.navigation_guard!r}, health={remote_health!r}"
            )
        if bool(remote_health.get("semantic_goal_priority")):
            raise RuntimeError(
                "semantic_goal_priority must be disabled for the shared-guard 2x2 design"
            )
        expected_release = str(config.get("release_fingerprint_sha256", ""))
        if remote_health.get("release_fingerprint_sha256") != expected_release:
            raise RuntimeError(
                "remote Agent release fingerprint does not match frozen config: "
                f"expected={expected_release!r}, health={remote_health!r}"
            )
    results: dict[str, list[dict[str, Any]]] = {mode: [] for mode in modes}
    failures: list[dict[str, Any]] = []
    for mode in modes:
        for task_id in task_ids:
            for seed in seeds:
                env_id = f"browsergym/webarena.{task_id}"
                direct_answer = None
                max_steps = int(
                    args.reactive_step_budget
                    if args.reactive_step_budget is not None
                    else config["reactive_step_budget"]
                )
                episode_agent = remote_agent if mode == "world-model" else reactive_agent
                if mode == "world-model":
                    max_steps = int(
                        args.world_model_step_budget
                        if args.world_model_step_budget is not None
                        else config.get("world_model_step_budget", config["reactive_step_budget"])
                    )
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
                    max_attempts=int(config.get("episode_max_attempts", 1)),
                    episode_timeout_seconds=args.episode_timeout_seconds,
                )
                    row.update({
                        "mode": mode,
                        "task_id": task_id,
                        "site": task_sites.get(str(task_id), "unknown"),
                        "uses_expected_answer": direct_answer is not None,
                    })
                    results[mode].append(row)
                    print(f"mode={mode} task={task_id} seed={seed} success={row['success']} steps={row['steps']}")
                except Exception as error:
                    failures.append({"mode": mode, "task_id": task_id, "seed": seed, "error": repr(error)})
    metrics = {mode: _summarize(rows) for mode, rows in results.items()}
    site_metrics = {mode: _summarize_by_site(rows) for mode, rows in results.items()}
    online_comparison = None
    if results.get("reactive") and results.get("world-model"):
        online_comparison = compare_success_rates(
            _paired_success(results["reactive"]),
            _paired_success(results["world-model"]),
        )
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "benchmark": config["benchmark"],
        "fixed_task_ids": task_ids,
        "task_sites": task_sites,
        "required_sites": required_sites,
        "fixed_seeds": seeds,
        "navigation_guard": args.navigation_guard,
        "remote_agent_health": remote_health,
        "freeze_sha256": declared_freeze_sha,
        "budgets": {
            "reactive_steps": (
                args.reactive_step_budget
                if args.reactive_step_budget is not None
                else config["reactive_step_budget"]
            ),
            "world_model_steps": (
                args.world_model_step_budget
                if args.world_model_step_budget is not None
                else config.get("world_model_step_budget", config["reactive_step_budget"])
            ),
            "evaluator_smoke_steps": config["evaluator_smoke_step_budget"],
        },
        "agent_metrics": metrics.get("reactive"),
        "world_model_agent_metrics": metrics.get("world-model"),
        "per_site_metrics": site_metrics,
        "paired_online_comparison": online_comparison,
        "evaluator_integrity_metrics": metrics.get("evaluator-smoke"),
        "agent_success_rate_excludes_answer_injection": True,
        "scope_limit": config.get(
            "scope_limit",
            "Frozen multi-site subset; not the full WebArena benchmark.",
        ),
        "results": results,
        "failures": failures,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key not in {"results", "failures"}}, ensure_ascii=False, indent=2))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
