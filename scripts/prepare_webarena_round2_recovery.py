#!/usr/bin/env python3
"""Create an auditable development recovery config from environment failures."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.freeze_webarena_p0_holdout import _canonical_sha  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.resolve().read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    config = _load(args.config)
    report = _load(args.report)
    if bool(config.get("eligible_for_final_claim")):
        raise ValueError("this recovery helper is restricted to development configs")
    original_ids = [int(task_id) for task_id in config.get("task_ids", [])]
    failures = report.get("failures") or []
    failed_ids = {
        int(row["task_id"])
        for row in failures
        if row.get("task_id") is not None and row.get("error")
    }
    task_ids = [task_id for task_id in original_ids if task_id in failed_ids]
    if not task_ids:
        raise ValueError("report contains no failed task IDs from the development config")
    unknown = failed_ids.difference(original_ids)
    if unknown:
        raise ValueError(f"report contains task IDs outside the config: {sorted(unknown)}")

    payload = dict(config)
    payload.pop("freeze_sha256", None)
    payload["benchmark"] = f"{config['benchmark']} environment recovery"
    payload["frozen_at_utc"] = datetime.now(timezone.utc).isoformat()
    payload["task_ids"] = task_ids
    payload["task_sites"] = {
        str(task_id): config["task_sites"][str(task_id)] for task_id in task_ids
    }
    payload["parent_development_report"] = args.report.resolve().relative_to(ROOT).as_posix()
    payload["recovery_reason"] = "Retry only episodes with recorded environment/transport failures."
    payload["scope_limit"] = (
        "Development-only recovery of recorded environment failures; merge by task ID "
        "with the parent report and never treat it as an independent benchmark."
    )
    payload["freeze_sha256"] = _canonical_sha(payload)

    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite recovery config: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(output)
    print(f"RECOVERY_TASKS={len(task_ids)} IDS={','.join(map(str, task_ids))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
