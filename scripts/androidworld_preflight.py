#!/usr/bin/env python3
"""Report whether the host is ready for a real AndroidWorld smoke run."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "data" / "reports" / "androidworld_preflight_latest.json")
    return parser.parse_args()


def _first_existing(candidates: list[Path]) -> str | None:
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def _sdk_tool(name: str, *parts: str) -> str | None:
    executable = shutil.which(name)
    if executable:
        return executable
    roots = [
        Path(value)
        for value in (os.environ.get("ANDROID_SDK_ROOT"), os.environ.get("ANDROID_HOME"))
        if value
    ]
    suffix = ".exe" if os.name == "nt" else ""
    return _first_existing([root.joinpath(*parts, name + suffix) for root in roots])


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def main() -> int:
    args = parse_args()
    adb = _sdk_tool("adb", "platform-tools")
    emulator = _sdk_tool("emulator", "emulator")
    devices: list[dict[str, str]] = []
    adb_error = ""
    if adb:
        try:
            completed = subprocess.run([adb, "devices"], check=True, capture_output=True, text=True, timeout=10)
            for line in completed.stdout.splitlines()[1:]:
                columns = line.split()
                if len(columns) >= 2:
                    devices.append({"serial": columns[0], "state": columns[1]})
        except Exception as error:
            adb_error = repr(error)
    ready_devices = [device for device in devices if device["state"] == "device"]
    kvm_available = Path("/dev/kvm").exists() if os.name != "nt" else None
    docker = shutil.which("docker")
    checks = {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "adb_executable": adb,
        "connected_devices": devices,
        "ready_device_count": len(ready_devices),
        "emulator_executable": emulator,
        "ANDROID_HOME": os.environ.get("ANDROID_HOME"),
        "ANDROID_SDK_ROOT": os.environ.get("ANDROID_SDK_ROOT"),
        "android_world_package": bool(importlib.util.find_spec("android_world")),
        "grpc_package": bool(importlib.util.find_spec("grpc")),
        "grpc_forwarding_port_8554_open": _port_open("127.0.0.1", 8554),
        "docker_executable": docker,
        "kvm_available": kvm_available,
    }
    blockers = []
    if not adb:
        blockers.append("adb executable not found")
    if not ready_devices:
        blockers.append("no running Android emulator/device")
    if not checks["android_world_package"]:
        blockers.append("android_world Python package not installed")
    if emulator and not checks["grpc_forwarding_port_8554_open"]:
        blockers.append("Android emulator gRPC port 8554 is not reachable")
    native_runtime_ready = not blockers
    container_runtime_possible = bool(docker and (kvm_available is not False))
    if os.name != "nt" and kvm_available is False:
        recommended_architecture = "local_emulator_remote_gpu_inference"
    else:
        recommended_architecture = "native_androidworld_runtime"
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "adb_error": adb_error,
        "adapter_implemented": True,
        "runtime_ready": native_runtime_ready,
        "native_runtime_ready": native_runtime_ready,
        "experimental_docker_runtime_possible": container_runtime_possible,
        "recommended_architecture": recommended_architecture,
        "blockers": blockers,
        "next_actions": [
            "Use Python 3.11+, install the official google-research/android_world requirements, and expose adb on PATH.",
            "Launch the Android 13/API 33 emulator with -grpc 8554 and verify adb devices reports state=device.",
            "Run the official first-time setup with --perform_emulator_setup before collecting migration evidence.",
            "If the GPU host has no /dev/kvm, run the emulator locally and keep only model inference on the GPU server.",
        ],
        "official_setup": "https://github.com/google-research/android_world#installation",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["runtime_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
