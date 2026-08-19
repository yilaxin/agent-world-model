#!/usr/bin/env python3
"""Report whether a host is ready for a real AndroidWorld smoke run."""

from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import os
import platform
import shutil
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "data" / "reports" / "androidworld_preflight_latest.json")
    parser.add_argument("--adb-path", type=Path)
    parser.add_argument("--adb-connect", help="Optional HOST:PORT for an externally hosted emulator")
    parser.add_argument("--device-serial", help="Require this adb serial instead of selecting the first ready device")
    parser.add_argument("--grpc-host", default="127.0.0.1")
    parser.add_argument("--grpc-port", type=int, default=8554)
    parser.add_argument("--expected-api", type=int, default=33)
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
    roots = [Path(value) for value in (os.environ.get("ANDROID_SDK_ROOT"), os.environ.get("ANDROID_HOME")) if value]
    suffix = ".exe" if os.name == "nt" else ""
    return _first_existing([root.joinpath(*parts, name + suffix) for root in roots])


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.8):
            return True
    except OSError:
        return False


def _run(command: list[str], timeout: int = 15) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, capture_output=True, text=True, timeout=timeout)


def _parse_devices(output: str) -> list[dict[str, Any]]:
    devices: list[dict[str, Any]] = []
    for line in output.splitlines()[1:]:
        columns = line.split()
        if len(columns) < 2 or line.startswith("*"):
            continue
        metadata: dict[str, Any] = {"serial": columns[0], "state": columns[1]}
        for value in columns[2:]:
            if ":" in value:
                key, item = value.split(":", 1)
                metadata[key] = item
        devices.append(metadata)
    return devices


def _device_property(adb: str, serial: str, name: str) -> str | None:
    try:
        return _run([adb, "-s", serial, "shell", "getprop", name]).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _device_shell(adb: str, serial: str, *args: str) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [adb, "-s", serial, "shell", *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        output = "\n".join(value.strip() for value in (completed.stdout, completed.stderr) if value.strip())
        return {"returncode": completed.returncode, "output": output}
    except Exception as error:
        return {"returncode": None, "output": repr(error)}


def _host_bridge_route_ready(route: dict[str, Any] | None) -> bool:
    if not route or route["returncode"] != 0:
        return False
    output = route["output"].lower()
    return "10.0.2.2" in output and "unreachable" not in output


def _package_version() -> str | None:
    if not importlib.util.find_spec("android_world"):
        return None
    try:
        return importlib.metadata.version("android_world")
    except importlib.metadata.PackageNotFoundError:
        return "importable-unversioned"


def _acceleration_probe(emulator: str | None) -> dict[str, Any] | None:
    if not emulator:
        return None
    try:
        completed = subprocess.run([emulator, "-accel-check"], check=False, capture_output=True, text=True, timeout=15)
        return {
            "returncode": completed.returncode,
            "supported": completed.returncode == 0,
            "output": "\n".join(value.strip() for value in (completed.stdout, completed.stderr) if value.strip()),
        }
    except Exception as error:
        return {"returncode": None, "supported": False, "output": repr(error)}


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    adb = str(args.adb_path) if args.adb_path else _sdk_tool("adb", "platform-tools")
    emulator = _sdk_tool("emulator", "emulator")
    adb_error = ""
    connect_result = ""
    devices: list[dict[str, Any]] = []
    if adb:
        try:
            if args.adb_connect:
                connect_result = _run([adb, "connect", args.adb_connect]).stdout.strip()
            devices = _parse_devices(_run([adb, "devices", "-l"]).stdout)
        except Exception as error:  # report diagnostics instead of hiding an external failure
            adb_error = repr(error)
    ready_devices = [device for device in devices if device["state"] == "device"]
    selected = next((item for item in ready_devices if item["serial"] == args.device_serial), None) if args.device_serial else (ready_devices[0] if ready_devices else None)
    properties: dict[str, str | None] = {}
    emulator_host_route: dict[str, Any] | None = None
    if adb and selected:
        properties = {
            "api_level": _device_property(adb, selected["serial"], "ro.build.version.sdk"),
            "model": _device_property(adb, selected["serial"], "ro.product.model"),
            "abi": _device_property(adb, selected["serial"], "ro.product.cpu.abi"),
            "boot_completed": _device_property(adb, selected["serial"], "sys.boot_completed"),
            "is_emulator": _device_property(adb, selected["serial"], "ro.kernel.qemu"),
        }
        if properties["is_emulator"] == "1":
            emulator_host_route = _device_shell(adb, selected["serial"], "ip", "route", "get", "10.0.2.2")
    expected_api = str(args.expected_api)
    api_compatible = properties.get("api_level") == expected_api
    boot_completed = properties.get("boot_completed") == "1"
    grpc_open = _port_open(args.grpc_host, args.grpc_port)
    android_world_version = _package_version()
    kvm_available = Path("/dev/kvm").exists() if os.name != "nt" else None
    acceleration = _acceleration_probe(emulator)
    checks = {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "adb_executable": adb,
        "adb_connect_result": connect_result,
        "connected_devices": devices,
        "ready_device_count": len(ready_devices),
        "selected_device": selected,
        "selected_device_properties": properties,
        "emulator_host_bridge_route": emulator_host_route,
        "expected_api_level": args.expected_api,
        "api_level_compatible": api_compatible,
        "boot_completed": boot_completed,
        "emulator_executable": emulator,
        "ANDROID_HOME": os.environ.get("ANDROID_HOME"),
        "ANDROID_SDK_ROOT": os.environ.get("ANDROID_SDK_ROOT"),
        "android_world_package": android_world_version is not None,
        "android_world_version": android_world_version,
        "grpc_package": bool(importlib.util.find_spec("grpc")),
        "grpc_host": args.grpc_host,
        "grpc_port": args.grpc_port,
        "grpc_forwarding_reachable": grpc_open,
        "docker_executable": shutil.which("docker"),
        "kvm_available": kvm_available,
        "emulator_acceleration_probe": acceleration,
    }
    blockers = []
    if not adb:
        blockers.append("adb executable not found")
    if not selected:
        blockers.append("no selected Android emulator in adb state=device")
    if selected and not boot_completed:
        blockers.append("selected Android device has not completed boot")
    if selected and not api_compatible:
        blockers.append(f"selected Android device is not API {args.expected_api}")
    if not android_world_version:
        blockers.append("android_world Python package not installed")
    if selected and not grpc_open:
        blockers.append(f"Android emulator gRPC endpoint {args.grpc_host}:{args.grpc_port} is not reachable")
    if selected and properties.get("is_emulator") == "1" and not _host_bridge_route_ready(emulator_host_route):
        blockers.append("Android guest has no route to emulator host bridge 10.0.2.2 required by the accessibility gRPC forwarder")
    runtime_ready = not blockers
    software_stack_ready = bool(adb and android_world_version)
    if os.name != "nt" and kvm_available is False and selected:
        recommended_architecture = "native_software_emulation_diagnostic"
    elif os.name != "nt" and kvm_available is False:
        recommended_architecture = "external_api33_emulator_remote_gpu_inference"
    else:
        recommended_architecture = "native_androidworld_runtime"
    next_actions = []
    if not android_world_version:
        next_actions.append("Install the official google-research/android_world package in Python 3.11+.")
    if not selected:
        next_actions.append("Expose one Pixel 6 Android 13/API 33 emulator through adb and gRPC port 8554.")
    elif not boot_completed:
        next_actions.append("Wait for sys.boot_completed=1 before starting AndroidWorld.")
    elif not grpc_open:
        next_actions.append(f"Expose the Android emulator gRPC endpoint at {args.grpc_host}:{args.grpc_port}.")
    elif blockers:
        next_actions.append("Restore the Android emulator guest network route to 10.0.2.2 before starting AndroidWorld.")
    else:
        next_actions.append("Run scripts/androidworld_smoke.py --perform-emulator-setup once, then rerun without that flag.")
    if kvm_available is False:
        next_actions.append("Move the AVD to a KVM-capable host for practical task-level evaluation; software emulation is diagnostic-only.")
    return {
        "schema_version": 2,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "adb_error": adb_error,
        "adapter_implemented": True,
        "software_stack_ready": software_stack_ready,
        "runtime_ready": runtime_ready,
        "native_accelerated_emulator_possible": bool(acceleration and acceleration["supported"]),
        "recommended_architecture": recommended_architecture,
        "blockers": blockers,
        "next_actions": next_actions,
        "official_setup": "https://github.com/google-research/android_world#installation",
    }


def main() -> int:
    args = parse_args()
    report = build_report(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["runtime_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
