#!/usr/bin/env python3
"""Run observed counterfactual collection in independent task shards."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = PROJECT_ROOT / "scripts" / "collect_phase2_counterfactuals.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks-config", type=Path, required=True)
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--seed-offset", type=int, default=1000)
    parser.add_argument(
        "--strategies",
        default="hard_wrong_target,wrong_action_type,missing_target",
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


def split_tasks(tasks: list[str], workers: int) -> list[list[str]]:
    if workers < 1:
        raise ValueError("workers must be at least 1")
    worker_count = min(workers, len(tasks))
    return [tasks[index::worker_count] for index in range(worker_count)]


def aggregate_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    planned_pairs = sum(int(report["planned_pairs"]) for report in reports)
    valid_pairs = sum(int(report["valid_pairs"]) for report in reports)
    informative_pairs = sum(int(report["informative_pairs"]) for report in reports)
    failed_pairs = sum(int(report["failed_pairs"]) for report in reports)
    strategies = list(reports[0].get("strategies", [])) if reports else []
    rows = [row for report in reports for row in report.get("rows", [])]
    failures = [
        failure for report in reports for failure in report.get("failures", [])
    ]
    completed_pairs = max(0, planned_pairs - failed_pairs)
    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "planned_pairs": planned_pairs,
        "valid_pairs": valid_pairs,
        "informative_pairs": informative_pairs,
        "informative_pair_rate": informative_pairs / max(1, valid_pairs),
        "failed_pairs": failed_pairs,
        "transition_count": sum(int(report["transition_count"]) for report in reports),
        "counterfactual_invalid_action_positives": sum(
            int(report["counterfactual_invalid_action_positives"])
            for report in reports
        ),
        "counterfactual_severe_failure_positives": sum(
            int(report["counterfactual_severe_failure_positives"])
            for report in reports
        ),
        "counterfactual_successes": sum(
            int(report["counterfactual_successes"]) for report in reports
        ),
        "pair_state_match_rate": valid_pairs / max(1, completed_pairs),
        "task_count": sum(int(report["task_count"]) for report in reports),
        "strategies": strategies,
        "strategy_counts": {
            strategy: sum(
                int(report.get("strategy_counts", {}).get(strategy, 0))
                for report in reports
            )
            for strategy in strategies
        },
        "observed_outcomes_only": all(
            bool(report.get("observed_outcomes_only")) for report in reports
        ),
        "shard_count": len(reports),
        "rows": rows,
        "failures": failures,
    }


def main() -> int:
    args = parse_args()
    tasks_path = (
        args.tasks_config
        if args.tasks_config.is_absolute()
        else PROJECT_ROOT / args.tasks_config
    )
    config = json.loads(tasks_path.read_text(encoding="utf-8"))
    tasks = [str(task) for task in config.get("tasks", [])]
    if not tasks:
        raise ValueError("tasks-config must contain a non-empty tasks list")

    output_dir = (
        args.output_dir
        if args.output_dir.is_absolute()
        else PROJECT_ROOT / args.output_dir
    )
    report_path = (
        args.report if args.report.is_absolute() else PROJECT_ROOT / args.report
    )
    shard_root = report_path.parent / f"{report_path.stem}_shards"
    shard_root.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    processes: list[tuple[subprocess.Popen[bytes], Path]] = []
    for index, shard_tasks in enumerate(split_tasks(tasks, args.workers)):
        shard_config = shard_root / f"shard_{index:02d}_tasks.json"
        shard_report = shard_root / f"shard_{index:02d}_report.json"
        shard_config.write_text(
            json.dumps({"schema_version": 1, "tasks": shard_tasks}, indent=2) + "\n",
            encoding="utf-8",
        )
        command = [
            sys.executable,
            str(COLLECTOR),
            "--tasks-config",
            str(shard_config),
            "--seeds",
            str(args.seeds),
            "--seed-offset",
            str(args.seed_offset),
            "--strategies",
            args.strategies,
            "--output-dir",
            str(output_dir / f"shard_{index:02d}"),
            "--report",
            str(shard_report),
        ]
        print(f"[counterfactual] starting shard {index + 1}: {len(shard_tasks)} tasks")
        processes.append((subprocess.Popen(command), shard_report))

    return_codes = [process.wait() for process, _ in processes]
    reports = [
        json.loads(path.read_text(encoding="utf-8"))
        for (_, path), code in zip(processes, return_codes, strict=True)
        if code == 0 and path.is_file()
    ]
    if len(reports) != len(processes):
        failed = [index for index, code in enumerate(return_codes) if code != 0]
        print(f"Counterfactual shard collection failed: {failed}", file=sys.stderr)
        return 2

    aggregate = aggregate_reports(reports)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                key: value
                for key, value in aggregate.items()
                if key not in {"rows", "failures"}
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if aggregate["valid_pairs"] and not aggregate["failed_pairs"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
