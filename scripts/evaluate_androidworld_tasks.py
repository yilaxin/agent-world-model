#!/usr/bin/env python3
"""Run AndroidWorld deterministic task-level evaluation.

Compares the reactive rule baseline against the phase-three world-model
planner on AndroidWorld deterministic system tasks (wifi on/off) whose success
is read back from Android system settings via ADB, so no LLM judge is needed.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
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
from agent_world_model.android_settings_navigation import SettingsNavigationPolicy  # noqa: E402
from agent_world_model.launcher_app_policy import LauncherAppPolicy  # noqa: E402
from agent_world_model.phase3_agent import Phase3WorldModelAgent  # noqa: E402
from agent_world_model.phase3_planning import PlanningConfig  # noqa: E402
from agent_world_model.reactive_agent import ReactiveAgent  # noqa: E402


TASK_CLASSES = {
    "wifi_on": system_tasks.SystemWifiTurnOn,
    "wifi_off": system_tasks.SystemWifiTurnOff,
}

OPEN_APPS = {
    "open_chrome": ("com.android.chrome", "Chrome"),
    "open_calendar": ("com.google.android.calendar", "Calendar"),
    "open_gallery": ("com.simplemobiletools.gallery.pro", "Gallery"),
    "open_messages": ("com.google.android.apps.messaging", "Messages"),
    "open_gmail": ("com.google.android.gm", "Gmail"),
}


class OpenAppTask:
    """Deterministic task: open a launcher app.

    Success is read from the foreground activity name, so no LLM judge is
    needed.  The launcher exposes these apps as real buttons, giving both
    policies a basic tap-to-open capability check.
    """

    def __init__(self, package: str, label: str) -> None:
        self.name = f"open_{label.lower()}"
        self.goal = f"Open the {label} app."
        self._package = package

    def initialize_task(self, env: Any) -> None:
        return None

    def is_successful(self, env: Any) -> float:
        foreground = str(getattr(env, "foreground_activity_name", "") or "")
        return 1.0 if self._package in foreground else 0.0


for _task_name, (_package, _label) in OPEN_APPS.items():
    TASK_CLASSES[_task_name] = type(
        f"Open{_label}Task",
        (OpenAppTask,),
        {},
    )


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
    semantic_overrides: int
    sequence_steps: int
    launcher_steps: int
    sparse_states: int
    recoveries: int
    terminal: bool
    duration_sec: float
    trajectory_file: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adb-path", default="C:\\AndroidSdk\\platform-tools\\adb.exe")
    parser.add_argument("--console-port", type=int, default=5554)
    parser.add_argument("--grpc-port", type=int, default=8554)
    parser.add_argument("--max-steps", type=int, default=12)
    parser.add_argument("--episodes", type=int, default=5)
    parser.add_argument("--tasks", default="wifi_on,wifi_off,open_chrome,open_calendar,open_photos,open_messages,open_gmail")
    parser.add_argument("--agents", default="reactive,phase3")
    parser.add_argument("--settings-navigation", action="store_true")
    parser.add_argument("--launcher-paging", action="store_true")
    parser.add_argument("--trajectory-dir", type=Path, default=PROJECT_ROOT / "data" / "trajectories_androidworld")
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
            semantic_goal_priority=True,
        )
    return agents


def build_settings_policy(args: argparse.Namespace) -> SettingsNavigationPolicy | None:
    return SettingsNavigationPolicy() if args.settings_navigation else None


def build_launcher_policy(args: argparse.Namespace) -> LauncherAppPolicy | None:
    return LauncherAppPolicy() if args.launcher_paging else None


def run_episode(
    env: Any,
    task_name: str,
    task_cls: type[Any],
    agent_name: str,
    agent: Any,
    episode: int,
    max_steps: int,
    adb_path: str,
    console_port: int,
    settings_policy: SettingsNavigationPolicy | None,
    launcher_policy: LauncherAppPolicy | None,
    trajectory_dir: Path,
) -> EpisodeResult:
    trajectory_dir.mkdir(parents=True, exist_ok=True)
    trajectory_file = trajectory_dir / f"{agent_name}_{task_name}_ep{episode}.jsonl"
    trajectory_rows: list[dict[str, Any]] = []
    target_app = "com.android.settings" if task_name in ("wifi_on", "wifi_off") else None
    recent_actions: list[str] = []
    steps = 0
    actions = 0
    invalid = 0
    semantic_overrides = 0
    sequence_steps = 0
    launcher_steps = 0
    sparse_states = 0
    recoveries = 0
    started = time.time()
    success = 0.0

    for attempt in range(3):
        try:
            if settings_policy is not None:
                settings_policy.reset()
            if launcher_policy is not None:
                launcher_policy.reset()
                # Restarting the forwarder drops its in-memory gRPC flags, so
                # only recover it when the process actually died between
                # episodes; a live forwarder keeps the existing connection.
                if not forwarder_alive(adb_path, console_port):
                    recover_forwarder_fast(env, adb_path, console_port)
            if task_name in OPEN_APPS:
                package, label = OPEN_APPS[task_name]
                task = OpenAppTask(package=package, label=label)
            else:
                task = task_cls(params={"on_or_off": "off" if task_name.endswith("off") else "on"})
            goal = task.goal
            task.initialize_task(env)
            env.reset(go_home=True)
            if settings_policy is not None:
                # Resume-proof the Settings app: launch it from its home
                # activity instead of whatever sub-screen a previous episode
                # left open.
                try:
                    subprocess.run(
                        [adb_path, "-s", f"emulator-{console_port}", "shell", "am", "force-stop", "com.android.settings"],
                        capture_output=True,
                        text=True,
                        timeout=20,
                    )
                except Exception:
                    pass
            foreground = str(getattr(env, "foreground_activity_name", "") or "")
            if "nexuslauncher" not in foreground:
                env.execute_action(json_action.JSONAction(action_type="navigate_home"))
            recent_actions = []
            steps = 0
            actions = 0
            invalid = 0
            semantic_overrides = 0
            sparse_states = 0
            for _ in range(max_steps):
                state, bounds, _, retries = stable_state(env, goal)
                sparse_states += retries
                try:
                    decision = decide_policy(
                        agent,
                        state,
                        recent_actions,
                        target_app=target_app,
                        goal=goal,
                        settings_policy=settings_policy,
                        launcher_policy=launcher_policy,
                        launcher_label=OPEN_APPS.get(task_name, (None, None))[1],
                    )
                    action = str(decision.action)
                    if str(getattr(decision, "mode", "")) == "semantic_goal_priority":
                        semantic_overrides += 1
                    if str(getattr(decision, "mode", "")) == "settings_sequence":
                        sequence_steps += 1
                    if str(getattr(decision, "mode", "")) == "launcher_app":
                        launcher_steps += 1
                except Exception:  # a policy crash is an invalid decision, not a crash of the eval
                    trajectory_rows.append(
                        {
                            "agent": agent_name,
                            "task": task_name,
                            "episode": episode,
                            "step": steps + 1,
                            "url": str(state.get("url") or ""),
                            "action": "invalid()",
                            "mode": "policy_error",
                            "invalid": True,
                            "element_count": len(bounds),
                        }
                    )
                    invalid += 1
                    steps += 1
                    recent_actions.append("invalid()")
                    continue
                steps += 1
                decision_detail: dict[str, Any] = {}
                try:
                    decision_detail = dict(getattr(decision, "to_dict", lambda: {})() or {})
                    if "candidates" in decision_detail:
                        decision_detail["candidates"] = decision_detail["candidates"][:8]
                except Exception:
                    decision_detail = {}
                try:
                    mapped = map_agent_action(action, bounds)
                except ValueError:
                    trajectory_rows.append(
                        {
                            "agent": agent_name,
                            "task": task_name,
                            "episode": episode,
                            "step": steps,
                            "url": str(state.get("url") or ""),
                            "goal": goal,
                            "action": action,
                            "mode": str(getattr(decision, "mode", "")),
                            "invalid": True,
                            "reason": "unmappable_action",
                            "element_count": len(bounds),
                            "decision": decision_detail,
                        }
                    )
                    invalid += 1
                    recent_actions.append(action)
                    continue
                trajectory_rows.append(
                    {
                        "agent": agent_name,
                        "task": task_name,
                        "episode": episode,
                        "step": steps,
                        "url": str(state.get("url") or ""),
                        "goal": goal,
                        "action": action,
                        "mode": str(getattr(decision, "mode", "")),
                        "target": str(getattr(decision, "target", "") or ""),
                        "invalid": False,
                        "element_count": len(bounds),
                        "axtree": str((state.get("axtree") or {}).get("text") or "")[:2500],
                        "decision": decision_detail,
                    }
                )
                for item in mapped:
                    env.execute_action(json_action.JSONAction(**item))
                    actions += 1
                recent_actions.append(action)
            success = float(task.is_successful(env))
            trajectory_rows.append(
                {
                    "agent": agent_name,
                    "task": task_name,
                    "episode": episode,
                    "step": "done",
                    "success": success,
                    "actions": actions,
                    "invalid_actions": invalid,
                    "duration_sec": time.time() - started,
                }
            )
            with trajectory_file.open("w", encoding="utf-8") as handle:
                for row in trajectory_rows:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            break
        except RuntimeError as error:
            if "a11y" not in str(error).lower() and "tree" not in str(error).lower():
                raise
            recoveries += 1
            recover_forwarder_fast(env, adb_path, console_port)
            if attempt == 2:
                success = 0.0

    return EpisodeResult(
        task=task_name,
        agent=agent_name,
        episode=episode,
        goal=goal,
        success=success,
        steps=steps,
        actions=actions,
        invalid_actions=invalid,
        semantic_overrides=semantic_overrides,
        sequence_steps=sequence_steps,
        launcher_steps=launcher_steps,
        sparse_states=sparse_states,
        recoveries=recoveries,
        terminal=False,
        duration_sec=time.time() - started,
        trajectory_file=str(trajectory_file),
    )


def recover_forwarder(adb_path: str, console_port: int) -> None:
    """Restart the accessibility forwarder service after an a11y failure."""
    serial = f"emulator-{console_port}"
    commands = [
        [adb_path, "-s", serial, "shell", "am", "force-stop", "com.google.androidenv.accessibilityforwarder"],
        [
            adb_path,
            "-s",
            serial,
            "shell",
            "settings",
            "put",
            "secure",
            "enabled_accessibility_services",
            "com.google.androidenv.accessibilityforwarder/com.google.androidenv.accessibilityforwarder.AccessibilityForwarder",
        ],
        [adb_path, "-s", serial, "shell", "settings", "put", "secure", "accessibility_enabled", "1"],
    ]
    for command in commands:
        try:
            subprocess.run(command, capture_output=True, text=True, timeout=20)
        except Exception:
            pass
    time.sleep(3)


def recover_forwarder_fast(env: Any, adb_path: str, console_port: int) -> None:
    """Restart the forwarder AND re-broadcast the gRPC flags immediately.

    The wrapper's flags live in the forwarder process memory, so a plain
    restart leaves it silent until android_env's slow internal refresh.  This
    fast path re-broadcasts the current wrapper port so recovery takes seconds
    instead of minutes.
    """
    serial = f"emulator-{console_port}"
    wrapper_port: int | None = None
    try:
        wrapper = getattr(env, "_env", None)
        if wrapper is not None and hasattr(wrapper, "get_port"):
            wrapper_port = int(wrapper.get_port())
    except Exception:
        wrapper_port = None

    recover_forwarder(adb_path, console_port)
    if wrapper_port is None:
        return

    component = "com.google.androidenv.accessibilityforwarder/.FlagsBroadcastReceiver"
    broadcasts = [
        [
            adb_path, "-s", serial, "shell", "am", "broadcast",
            "-a", "accessibility_forwarder.intent.action.SET_GRPC",
            "--es", "host", "10.0.2.2", "--ei", "port", str(wrapper_port),
            "-n", component,
        ],
        [
            adb_path, "-s", serial, "shell", "am", "broadcast",
            "-a", "accessibility_forwarder.intent.action.ENABLE_ACCESSIBILITY_TREE_LOGS",
            "-n", component,
        ],
        [
            adb_path, "-s", serial, "shell", "am", "broadcast",
            "-a", "accessibility_forwarder.intent.action.ENABLE_GRPC",
            "-n", component,
        ],
    ]
    for command in broadcasts:
        try:
            subprocess.run(command, capture_output=True, text=True, timeout=20)
        except Exception:
            pass


def forwarder_alive(adb_path: str, console_port: int) -> bool:
    serial = f"emulator-{console_port}"
    try:
        completed = subprocess.run(
            [adb_path, "-s", serial, "shell", "ps", "-A"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        return "com.google.androidenv.accessibilityforwarder" in completed.stdout
    except Exception:
        return False


def stable_state(env: Any, goal: str) -> tuple[dict[str, Any], dict[str, tuple[int, int, int, int]], Any, int]:
    """Fetch a state with enough actionable elements.

    The accessibility forwarder occasionally hiccups right after navigation and
    returns a sparse tree; retrying for a short window keeps the environment
    flakiness from being attributed to either policy.
    """
    retries = 0
    for _ in range(5):
        raw = env.get_state(wait_to_stabilize=True)
        state, bounds = adapt_androidworld_state(
            raw,
            goal=goal,
            activity=env.foreground_activity_name,
        )
        lines = [line for line in state["axtree"]["text"].splitlines() if line.strip()]
        if len(lines) >= 6:
            return state, bounds, raw, retries
        retries += 1
        time.sleep(2.0)
    return state, bounds, raw, retries


def decide_policy(
    agent: Any,
    state: dict[str, Any],
    recent_actions: list[str],
    *,
    target_app: str | None,
    goal: str,
    settings_policy: SettingsNavigationPolicy | None,
    launcher_policy: LauncherAppPolicy | None,
    launcher_label: str | None,
) -> Any:
    """Open the task's app first, then delegate to the underlying policy.

    AndroidWorld official agents open the target app before interacting; we do
    the same for both the reactive baseline and the phase-three planner so the
    comparison starts from the same app context.
    """
    url = str(state.get("url") or "")
    if target_app and target_app not in url:
        if os.environ.get("AW_DEBUG"):
            print(f"[aw-debug] app_open url={url}", flush=True)
        return type(
            "AppOpenDecision",
            (),
            {"action": f'open_app("{target_app}")', "to_dict": lambda self: {"action": self.action}},
        )()
    if settings_policy is not None:
        sequence = settings_policy.decide(state, goal, recent_actions)
        if os.environ.get("AW_DEBUG"):
            print(f"[aw-debug] seq={sequence} url={url} goal={goal}", flush=True)
        if sequence is not None:
            return type(
                "SettingsSequenceDecision",
                (),
                {
                    "action": sequence["action"],
                    "mode": sequence["mode"],
                    "to_dict": lambda self: {"action": self.action, "mode": self.mode},
                },
            )()
    if launcher_policy is not None and launcher_label:
        launcher_decision = launcher_policy.decide(state, launcher_label)
        if launcher_decision is not None:
            return type(
                "LauncherDecision",
                (),
                {
                    "action": launcher_decision["action"],
                    "mode": launcher_decision["mode"],
                    "to_dict": lambda self: {"action": self.action, "mode": self.mode},
                },
            )()
    return agent.decide(state, recent_actions)


def main() -> int:
    args = parse_args()
    # The emulator's monkey-based app launch is slow under WHPX; give the ADB
    # controller a generous default timeout.  The dataclass default factory
    # captures the original class, so patch the controller method directly.
    import android_env.components.adb_controller as adb_controller  # noqa: E402

    _original_execute_command = adb_controller.AdbController.execute_command

    def _execute_command_with_timeout(self: Any, command_args: list[str], timeout: float | None = None, **kwargs: Any) -> Any:
        return _original_execute_command(
            self,
            command_args,
            timeout=timeout if timeout is not None else 60.0,
            **kwargs,
        )

    adb_controller.AdbController.execute_command = _execute_command_with_timeout

    # Reuse the accessibility forwarder already installed in the AVD instead of
    # re-downloading its APK on every run (same approach as the smoke script).
    import subprocess as _subprocess
    from android_world.env import android_world_controller  # noqa: E402

    _installed = _subprocess.run(
        [args.adb_path, "-s", f"emulator-{args.console_port}", "shell", "pm", "list", "packages", "com.google.androidenv.accessibilityforwarder"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if _installed.returncode == 0 and "package:com.google.androidenv.accessibilityforwarder" in _installed.stdout:
        _original_wrapper = android_world_controller.apply_a11y_forwarder_app_wrapper

        def _reuse_installed_forwarder(base_env: Any, _install: bool) -> Any:
            return _original_wrapper(base_env, False)

        android_world_controller.apply_a11y_forwarder_app_wrapper = _reuse_installed_forwarder

    env = env_launcher.load_and_setup_env(
        console_port=args.console_port,
        adb_path=args.adb_path,
        grpc_port=args.grpc_port,
        emulator_setup=False,
    )
    agents = build_agents(args)
    settings_policy = build_settings_policy(args)
    launcher_policy = build_launcher_policy(args)
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
                        args.adb_path,
                        args.console_port,
                        settings_policy,
                        launcher_policy,
                        Path(args.trajectory_dir),
                    )
                    results.append(result)
                    print(
                        f"[{agent_name}/{task_name}/ep{episode}] success={result.success} "
                        f"steps={result.steps} actions={result.actions} invalid={result.invalid_actions} "
                        f"semantic_override={result.semantic_overrides}",
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
                "semantic_overrides_total": sum(r.semantic_overrides for r in subset),
                "sequence_steps_total": sum(r.sequence_steps for r in subset),
                "launcher_steps_total": sum(r.launcher_steps for r in subset),
                "sparse_states_total": sum(r.sparse_states for r in subset),
                "recoveries_total": sum(r.recoveries for r in subset),
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
        "trajectory_dir": str(args.trajectory_dir),
        "trajectory_files": len(list(Path(args.trajectory_dir).glob("*.jsonl"))),
        "notes": [
            "Success is read from Android system settings (wifi_on) via ADB; no LLM judge.",
            "Phase-three planner uses the local CPU ensemble and structure aligner.",
        ]
        + (
            ["Sequence-level Settings navigation policy enabled (settings_sequence)."]
            if settings_policy is not None
            else []
        )
        + (
            ["Launcher paging policy enabled (launcher_app): opens the app drawer for apps not on the home page."]
            if launcher_policy is not None
            else []
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
