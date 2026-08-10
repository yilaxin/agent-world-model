#!/usr/bin/env python3
"""Run a real AndroidWorld reset/action smoke test and preserve raw evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent_world_model.androidworld_adapter import adapt_androidworld_state, map_agent_action  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adb-path", default="adb")
    parser.add_argument("--console-port", type=int, default=5554)
    parser.add_argument("--grpc-port", type=int, default=8554)
    parser.add_argument("--adb-timeout", type=float, default=600.0, help="Long timeout for software-emulated ADB calls")
    parser.add_argument("--perform-emulator-setup", action="store_true")
    parser.add_argument("--goal", default="Verify AndroidWorld environment reset and one safe wait action")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "data" / "reports" / "androidworld_smoke_latest.json")
    parser.add_argument("--artifact-dir", type=Path, default=PROJECT_ROOT / "outputs" / "androidworld_smoke")
    return parser.parse_args()


def _write(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _save_rgb(path: Path, pixels: Any) -> str:
    import cv2

    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), cv2.cvtColor(pixels, cv2.COLOR_RGB2BGR)):
        raise RuntimeError(f"failed to write screenshot: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _package_installed(adb_path: str, console_port: int, package: str) -> bool:
    completed = subprocess.run(
        [adb_path, "-s", f"emulator-{console_port}", "shell", "pm", "list", "packages", package],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return completed.returncode == 0 and f"package:{package}" in completed.stdout


def main() -> int:
    args = parse_args()
    generated = datetime.now(timezone.utc).isoformat()
    try:
        from android_env.components import config_classes
        from android_world.env import android_world_controller, env_launcher, json_action
    except Exception as error:
        report = {"schema_version": 1, "generated_at_utc": generated, "status": "blocked", "error": repr(error)}
        _write(args.output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    env = None
    try:
        original_adb_config = config_classes.AdbControllerConfig

        def _adb_config_with_timeout(*config_args: Any, **config_kwargs: Any) -> Any:
            config_kwargs.setdefault("default_timeout", args.adb_timeout)
            return original_adb_config(*config_args, **config_kwargs)

        config_classes.AdbControllerConfig = _adb_config_with_timeout
        forwarder_package = "com.google.androidenv.accessibilityforwarder"
        reused_forwarder = _package_installed(args.adb_path, args.console_port, forwarder_package)
        if reused_forwarder:
            original_wrapper = android_world_controller.apply_a11y_forwarder_app_wrapper

            def _reuse_installed_forwarder(base_env: Any, _install: bool) -> Any:
                return original_wrapper(base_env, False)

            android_world_controller.apply_a11y_forwarder_app_wrapper = _reuse_installed_forwarder
        env = env_launcher.load_and_setup_env(
            console_port=args.console_port,
            emulator_setup=args.perform_emulator_setup,
            adb_path=args.adb_path,
            grpc_port=args.grpc_port,
        )
        before = env.reset(go_home=True)
        state_before, bounds = adapt_androidworld_state(before, goal=args.goal, activity=env.foreground_activity_name)
        mapped = map_agent_action("noop()", bounds)
        official_action = json_action.JSONAction(**mapped[0])
        env.execute_action(official_action)
        after = env.get_state(wait_to_stabilize=True)
        state_after, _ = adapt_androidworld_state(after, goal=args.goal, activity=env.foreground_activity_name)
        subprocess.run([args.adb_path, "-s", f"emulator-{args.console_port}", "shell", "getprop", "ro.build.version.sdk"], check=True, capture_output=True, text=True)
        before_path = args.artifact_dir / "before.png"
        after_path = args.artifact_dir / "after.png"
        before_sha = _save_rgb(before_path, before.pixels)
        after_sha = _save_rgb(after_path, after.pixels)
        report = {
            "schema_version": 1,
            "generated_at_utc": generated,
            "status": "passed",
            "real_environment_reset": True,
            "real_action_executed": True,
            "a11y_forwarder_reused": reused_forwarder,
            "adb_timeout_seconds": args.adb_timeout,
            "action": mapped[0],
            "before": {"url": state_before["url"], "title": state_before["title"], "element_count": len(bounds), "axtree": state_before["axtree"]["text"], "normalized_ui": state_before["dom"]["text"], "screenshot": str(before_path), "screenshot_sha256": before_sha},
            "after": {"url": state_after["url"], "title": state_after["title"], "axtree": state_after["axtree"]["text"], "normalized_ui": state_after["dom"]["text"], "screenshot": str(after_path), "screenshot_sha256": after_sha},
            "migration_complete": False,
            "completion_note": "This proves real reset/action transport only; task-level baseline and planner success evidence are still required.",
        }
        _write(args.output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception as error:
        report = {"schema_version": 1, "generated_at_utc": generated, "status": "failed", "error": repr(error), "migration_complete": False}
        _write(args.output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1
    finally:
        if env is not None:
            env.close()


if __name__ == "__main__":
    raise SystemExit(main())
