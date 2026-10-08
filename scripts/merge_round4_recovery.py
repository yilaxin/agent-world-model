"""Merge recovery rows back into a round-4 cell report.

Environment failures (tunnel drops, page navigation timeouts) are recovered by
re-executing the affected task/seed pairs under the same frozen policy.  This
script replaces those failures with the judged recovery rows and recomputes the
cell-level metrics.  It does not change the policy, model, tasks, or budgets.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--recovery-report", type=Path, action="append", required=True)
    parser.add_argument("--mode", choices=("reactive", "world-model"), required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    episodes = len(rows)
    successes = sum(1 for row in rows if row.get("success"))
    execution = [row.get("action_execution_successes", 0) for row in rows]
    attempts = [row.get("attempted_actions", 0) for row in rows]
    steps = [row.get("steps", 0) for row in rows]
    latency = [row.get("elapsed_seconds", 0.0) for row in rows]
    return {
        "episodes": episodes,
        "successes": successes,
        "success_rate": successes / episodes if episodes else 0.0,
        "action_execution_rate": (
            sum(execution) / sum(attempts) if sum(attempts) else 0.0
        ),
        "average_steps": sum(steps) / len(steps) if steps else 0.0,
        "average_latency_seconds": sum(latency) / len(latency) if latency else 0.0,
    }


def main() -> int:
    args = parse_args()
    report_path = Path(args.report)
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    rows = list(payload.get("results", {}).get(args.mode, []))
    failures = list(payload.get("failures", []))

    recovered: dict[tuple[int, int], dict[str, Any]] = {}
    recovery_sources: list[str] = []
    for recovery_path in args.recovery_report:
        recovery = json.loads(Path(recovery_path).read_text(encoding="utf-8"))
        recovery_sources.append(Path(recovery_path).name)
        for row in recovery.get("results", {}).get(args.mode, []):
            key = (int(row["task_id"]), int(row["seed"]))
            recovered[key] = row
        for failure in recovery.get("failures", []):
            key = (int(failure["task_id"]), int(failure.get("seed", -1)))
            recovered[key] = {
                "task_id": key[0],
                "seed": key[1],
                "success": False,
                "recovery_still_failed": str(failure.get("error", ""))[:200],
            }

    merged: dict[tuple[int, int], dict[str, Any]] = {}
    for row in rows:
        merged[(int(row["task_id"]), int(row["seed"]))] = row
    for key, row in recovered.items():
        merged[key] = row

    merged_rows = [merged[key] for key in sorted(merged)]
    merged_failures = [
        failure
        for failure in failures
        if (int(failure["task_id"]), int(failure.get("seed", -1))) not in recovered
    ]

    site_keys = {str(row.get("site", "unknown")) for row in merged_rows}
    per_site = {
        site: _metrics([row for row in merged_rows if str(row.get("site")) == site])
        for site in sorted(site_keys)
    }
    payload["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    payload["results"][args.mode] = merged_rows
    payload["failures"] = merged_failures
    if args.mode == "world-model":
        payload["world_model_agent_metrics"] = _metrics(merged_rows)
    else:
        payload["agent_metrics"] = _metrics(merged_rows)
    payload["per_site_metrics"] = {args.mode: per_site}
    payload["recovery"] = {
        "recovery_reports": recovery_sources,
        "recovered_pairs": sorted((key[0], key[1]) for key in recovered),
        "remaining_failures": len(merged_failures),
    }

    output = Path(args.output) if args.output else report_path
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "rows": len(merged_rows),
                "successes": sum(1 for row in merged_rows if row.get("success")),
                "remaining_failures": len(merged_failures),
                "recovered_pairs": len(recovered),
                "output": str(output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
