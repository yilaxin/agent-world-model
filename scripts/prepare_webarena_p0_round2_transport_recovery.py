#!/usr/bin/env python3
"""Freeze a subset containing only recorded holdout transport failures.

This is evidence recovery, not task selection: task order, seed, budgets,
release fingerprint, policy, and guard remain identical to the parent config.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_TRANSPORT_MARKERS = (
    "Connection refused",
    "RemoteDisconnected",
    "timed out",
    "Temporary failure in name resolution",
)


def canonical_sha(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_frozen(path: Path, label: str) -> tuple[dict[str, Any], str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    unfrozen = dict(payload)
    declared = str(unfrozen.pop("freeze_sha256", ""))
    actual = canonical_sha(unfrozen)
    if not declared or declared != actual:
        raise ValueError(f"{label} freeze mismatch: {declared!r} != {actual!r}")
    return payload, declared


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = args.config.resolve()
    report_path = args.report.resolve()
    output_path = args.output.resolve()
    config, config_freeze = load_frozen(config_path, "site config")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("freeze_sha256") != config_freeze:
        raise ValueError("report does not belong to the frozen site config")
    if bool(config.get("task_feedback_used")) or bool(
        config.get("post_freeze_policy_changes_allowed")
    ):
        raise ValueError("invalid holdout policy flags")

    original_ids = [int(value) for value in config["task_ids"]]
    transport_ids: set[int] = set()
    rejected: list[dict[str, Any]] = []
    for failure in report.get("failures", []):
        detail = str(failure.get("error", ""))
        task_id = int(failure["task_id"])
        if any(marker in detail for marker in ALLOWED_TRANSPORT_MARKERS):
            transport_ids.add(task_id)
        else:
            rejected.append({"task_id": task_id, "error": detail})
    task_ids = [task_id for task_id in original_ids if task_id in transport_ids]
    if not task_ids:
        raise ValueError("report contains no eligible transport failures")
    if not transport_ids.issubset(set(original_ids)):
        raise ValueError("report contains a task outside the frozen config")

    payload = dict(config)
    payload.pop("freeze_sha256", None)
    payload["benchmark"] = f"{config['benchmark']} transport recovery"
    payload["frozen_at_utc"] = datetime.now(timezone.utc).isoformat()
    payload["task_ids"] = task_ids
    payload["task_sites"] = {
        str(task_id): config["task_sites"][str(task_id)] for task_id in task_ids
    }
    payload["parent_holdout_report"] = {
        "path": report_path.relative_to(ROOT).as_posix(),
        "sha256": file_sha(report_path),
        "site_config_freeze_sha256": config_freeze,
    }
    payload["recovery_reason"] = (
        "Retry only episodes whose parent report recorded an allowed transport failure."
    )
    payload["non_transport_failures_excluded"] = rejected
    payload["scope_limit"] = (
        "Frozen holdout transport recovery; merge by task ID with the parent report. "
        "It is not an independent benchmark and permits no policy feedback."
    )
    payload["freeze_sha256"] = canonical_sha(payload)
    if output_path.exists():
        existing = json.loads(output_path.read_text(encoding="utf-8"))
        if existing != payload:
            raise FileExistsError(f"refusing to overwrite non-identical {output_path}")
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(output_path)
    print(f"TRANSPORT_RECOVERY_TASKS={len(task_ids)} IDS={','.join(map(str, task_ids))}")
    print(f"RECOVERY_FREEZE_SHA256={payload['freeze_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
