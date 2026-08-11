#!/usr/bin/env python3
"""Run AndroidWorld deterministic task-level evaluation.

Compares the reactive rule baseline against the phase-three world-model
planner on AndroidWorld deterministic system tasks (wifi on/off) whose success
is read back from Android system settings via ADB, so no LLM judge is needed.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from android_world.env import env_launcher, json_action  # noqa: E402
from android_world.task_evals.single import system as system_tasks  # noqa: E402

from agent_world_model.androidworld_adapter import adapt_androidworld_state, map_agent_action  # noqa: E402
from agent_world_model.phase3_agent import Phase3WorldModelAgent  # noqa: E402
from agent_world_model.phase3_planning import PlanningConfig  # noqa: E402
from agent_world_model.reactive_agent import ReactiveAgent  # noqa: E402


TASK_CLASSES = {
    "wifi_on": system_tasks.SystemWifiTurnOn,
    "wifi_off": system_tasks.SystemWifiTurnOff,
}


class OpenChromeTask:
    """Deterministic task: open the Chrome app from the launcher.

    Success is read from the foreground activity name, so no LLM judge is
    needed.  The launcher exposes Chrome as a real button, giving both
    policies a basic tap-to-open capability check.
    """

    name = "open_chrome"
    goal = "Open the Chrome app."

    def initialize_task(self, env: Any) -> None:
        return None

    def is_successful(self, env: Any) -> float:
        foreground = str(getattr(env, "foreground_activity_name", "") or "")
        return 1.0 if "com.android.chrome" in foreground else 0.0


TASK_CLASSES["open_chrome"] = OpenChromeTask


@dataclass
class EpisodeResult:
    task: str
    agent: str
    episode: int
    goal: str
    success: float
    steps: int
    actions: int
    invalid_actions: int
    terminal: bool
    duration_sec: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adb-path", default="C:\\AndroidSdk\\platform-tools\\adb.exe")
    parser.add_argument("--console-port", type=int, default=5554)
    parser.add_argument("--grpc-port", type=int, default=8554)
    parser.add_argument("--max-steps", type=int, default=12)
    parser.add_argument("--episodes", type=int, default=3)
    parser.add_argument("--tasks", default="wifi_on,wifi_off")
    parser.add_argument("--agents", default="reactive,phase3")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "data" / "reports" / "androidworld_task_eval_latest.json")
    return parser.parse_args()


def build_agents(args: argparse.Namespace) -> dict[str, Any]:
    agents: dict[str, Any] = {}
    names = [item.strip() for item in args.agents.split(",") if item.strip()]
    if "reactive" in names:
        agents["reactive"] = ReactiveAgent()
    if "phase3" in names:
        config = json.loads((PROJECT_ROOT / "configs" / "phase3_planner.json").read_text(encoding="utf-8"))
        agents["phase3"] = Phase3WorldModelAgent(
            ensemble_manifest=PROJECT_ROOT / "artifacts" / "phase2" / "world_model_ensemble_p1.json",
            alignment_checkpoint=PROJECT_ROOT / "artifacts" / "phase3" / "structure_aligner_best.pt",
            device="cpu",
            planning_config=PlanningConfig(**config["planning"]),
            max_candidates=int(config["candidate_generation"]["max_candidates"]),
        )
    return agents


def run_episode(
    env: Any,
    task_name: str,
    task_cls: type[Any],
    agent_name: str,
    agent: Any,
    episode: int,
    max_steps: int,
) -> EpisodeResult:
    if task_name == "open_chrome":
        task = OpenChromeTask()
    else:
        task = task_cls(params={"on_or_off": "off" if task_name.endswith("off") else "on"})
    task.initialize_task(env)
    env.reset(go_home=True)
    foreground = str(getattr(env, "foreground_activity_name", "") or "")
    if "nexuslauncher" not in foreground:
        env.execute_action(json_action.JSONAction(action_type="navigate_home"))
    goal = task.goal
    target_app = "com.android.settings" if task_name in ("wifi_on", "wifi_off") else None
    recent_actions: list[str] = []
    steps = 0
    actions = 0
    invalid = 0
    started = time.time()

    for _ in range(max_steps):
        state, bounds, _ = stable_state(env, goal)
        try:
            decision = decide_policy(agent, state, recent_actions, target_app=target_app)
            action = str(decision.action)
        except Exception:  # a policy crash is an invalid decision, not a crash of the eval
            invalid += 1
            steps += 1
            recent_actions.append("invalid()")
            continue
        steps += 1
        try:
            mapped = map_agent_action(action, bounds)
        except ValueError:
            invalid += 1
            recent_actions.append(action)
            continue
        for item in mapped:
            env.execute_action(json_action.JSONAction(**item))
            actions += 1
        recent_actions.append(action)

    success = float(task.is_successful(env))
    return EpisodeResult(
        task=task_name,
        agent=agent_name,
        episode=episode,
        goal=goal,
        success=success,
        steps=steps,
        actions=actions,
        invalid_actions=invalid,
        terminal=False,
        duration_sec=time.time() - started,
    )


def stable_state(env: Any, goal: str) -> tuple[dict[str, Any], dict[str, tuple[int, int, int, int]], Any]:
    """Fetch a state with enough actionable elements.

    The accessibility forwarder occasionally hiccups right after navigation and
    returns a sparse tree; retrying for a short window keeps the environment
    flakiness from being attributed to either policy.
    """
    for _ in range(3):
        raw = env.get_state(wait_to_stabilize=True)
        state, bounds = adapt_androidworld_state(
            raw,
            goal=goal,
            activity=env.foreground_activity_name,
        )
        lines = [line for line in state["axtree"]["text"].splitlines() if line.strip()]
        if len(lines) >= 6:
            return state, bounds, raw
        time.sleep(2.0)
    return state, bounds, raw


def decide_policy(agent: Any, state: dict[str, Any], recent_actions: list[str], *, target_app: str | None) -> Any:
    """Open the task's app first, then delegate to the underlying policy.

    AndroidWorld official agents open the target app before interacting; we do
    the same for both the reactive baseline and the phase-three planner so the
    comparison starts from the same app context.
    """
    url = str(state.get("url") or "")
    if target_app and target_app not in url:
        return type(
            "AppOpenDecision",
            (),
            {"action": f'open_app("{target_app}")', "to_dict": lambda self: {"action": self.action}},
        )()
    return agent.decide(state, recent_actions)


def main() -> int:
    args = parse_args()
    env = env_launcher.load_and_setup_env(
        console_port=args.console_port,
        adb_path=args.adb_path,
        grpc_port=args.grpc_port,
        emulator_setup=False,
    )
    agents = build_agents(args)
    tasks = [item.strip() for item in args.tasks.split(",") if item.strip()]
    results: list[EpisodeResult] = []

    try:
        for agent_name, agent in agents.items():
            for task_name in tasks:
                for episode in range(1, args.episodes + 1):
                    result = run_episode(
                        env,
                        task_name,
                        TASK_CLASSES[task_name],
                        agent_name,
                        agent,
                        episode,
                        args.max_steps,
                    )
                    results.append(result)
                    print(
                        f"[{agent_name}/{task_name}/ep{episode}] success={result.success} "
                        f"steps={result.steps} actions={result.actions} invalid={result.invalid_actions}",
                        flush=True,
                    )
    finally:
        env.close()

    rows: dict[str, Any] = {}
    for agent_name in agents:
        agent_rows = [r for r in results if r.agent == agent_name]
        per_task: dict[str, Any] = {}
        for task_name in tasks:
            subset = [r for r in agent_rows if r.task == task_name]
            if not subset:
                continue
            per_task[task_name] = {
                "episodes": len(subset),
                "success_rate": statistics.mean(r.success for r in subset),
                "avg_steps": statistics.mean(r.steps for r in subset),
                "action_execution_rate": statistics.mean(
                    r.actions / max(r.steps, 1) for r in subset
                ),
                "invalid_actions_total": sum(r.invalid_actions for r in subset),
            }
        rows[agent_name] = {
            "success_rate": statistics.mean(r.success for r in agent_rows),
            "avg_steps": statistics.mean(r.steps for r in agent_rows),
            "action_execution_rate": statistics.mean(
                r.actions / max(r.steps, 1) for r in agent_rows
            ),
            "per_task": per_task,
        }

    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "platform": "androidworld_api33_whpx_local",
        "tasks": tasks,
        "agents": list(agents),
        "max_steps": args.max_steps,
        "episodes_per_task": args.episodes,
        "summary": rows,
        "episodes": [vars(r) for r in results],
        "notes": [
            "Success is read from Android system settings (wifi_on) via ADB; no LLM judge.",
            "Phase-three planner uses the local CPU ensemble and structure aligner.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
