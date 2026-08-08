#!/usr/bin/env python3
"""Report whether the host is ready for a real AndroidWorld smoke run."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "data" / "reports" / "androidworld_preflight_latest.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    adb = shutil.which("adb")
    devices: list[str] = []
    adb_error = ""
    if adb:
        try:
            completed = subprocess.run([adb, "devices"], check=True, capture_output=True, text=True, timeout=10)
            devices = [line.split()[0] for line in completed.stdout.splitlines()[1:] if line.strip().endswith("device")]
        except Exception as error:
            adb_error = repr(error)
    checks = {
        "adb_executable": adb,
        "connected_devices": devices,
        "ANDROID_HOME_set": bool(os.environ.get("ANDROID_HOME")),
        "android_world_package": bool(importlib.util.find_spec("android_world")),
        "grpc_package": bool(importlib.util.find_spec("grpc")),
    }
    blockers = []
    if not adb:
        blockers.append("adb executable not found")
    if not devices:
        blockers.append("no running Android emulator/device")
    if not checks["android_world_package"]:
        blockers.append("android_world Python package not installed")
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "adb_error": adb_error,
        "adapter_implemented": True,
        "runtime_ready": not blockers,
        "blockers": blockers,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["runtime_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
