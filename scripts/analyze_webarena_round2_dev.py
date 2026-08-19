#!/usr/bin/env python3
"""Merge round-2 development reports into one task-paired audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_world_model.experiment_stats import compare_success_rates  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, action="append", required=True)
    parser.add_argument("--reactive-report", type=Path, action="append", default=[])
    parser.add_argument("--world-model-report", type=Path, action="append", default=[])
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data/reports/webarena_p0_round2_dev_analysis.json",
    )
    parser.add_argument("--allow-incomplete", action="store_true")
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def result_rows(report: dict[str, Any], mode: str) -> list[dict[str, Any]]:
    raw = report.get("results") or []
    if isinstance(raw, dict):
        key = "world-model" if mode == "world-model" else mode
        rows = raw.get(key) or []
    elif isinstance(raw, list):
        rows = raw
    else:
        raise ValueError("report results must be an object or list")
    return [row for row in rows if str(row.get("mode", mode)) == mode]


def report_records(paths: Iterable[Path], mode: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    for raw_path in paths:
        path = resolve(raw_path)
        report = load(path)
        extracted = result_rows(report, mode)
        rows.extend(extracted)
        records.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256(path),
                "mode": mode,
                "result_rows": len(extracted),
                "failure_rows": len(report.get("failures") or []),
                "remote_agent_health": report.get("remote_agent_health"),
                "validation_adapter": report.get("validation_adapter"),
            }
        )
    return rows, records


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    attempted = sum(int(row.get("attempted_actions", row.get("steps", 0))) for row in rows)
    executed = sum(int(row.get("action_execution_successes", 0)) for row in rows)
    successes = sum(bool(row.get("success")) for row in rows)
    return {
        "episodes": len(rows),
        "successes": successes,
        "success_rate": successes / len(rows) if rows else 0.0,
        "action_execution_rate": executed / attempted if attempted else None,
        "average_steps": sum(int(row.get("steps", 0)) for row in rows) / len(rows) if rows else 0.0,
    }


def main() -> int:
    args = parse_args()
    configs: list[tuple[Path, dict[str, Any]]] = []
    expected: dict[int, str] = {}
    release_by_task: dict[int, str] = {}
    budgets_by_task: dict[int, int] = {}
    for raw_path in args.config:
        path = resolve(raw_path)
        config = load(path)
        configs.append((path, config))
        for raw_task_id in config["task_ids"]:
            task_id = int(raw_task_id)
            if task_id in expected:
                raise ValueError(f"duplicate task ID across configs: {task_id}")
            expected[task_id] = str(config["task_sites"][str(task_id)])
            release_by_task[task_id] = str(config.get("release_fingerprint_sha256", ""))
            budgets_by_task[task_id] = int(config["world_model_step_budget"])

    reactive_rows, reactive_records = report_records(args.reactive_report, "reactive")
    world_rows, world_records = report_records(args.world_model_report, "world-model")
    by_mode: dict[str, dict[int, dict[str, Any]]] = {"reactive": {}, "world-model": {}}
    for mode, rows in (("reactive", reactive_rows), ("world-model", world_rows)):
        for row in rows:
            task_id = int(row["task_id"])
            if task_id not in expected:
                raise ValueError(f"{mode} report contains unexpected task ID {task_id}")
            if task_id in by_mode[mode]:
                raise ValueError(f"duplicate {mode} result for task ID {task_id}")
            site = str(row.get("site") or expected[task_id])
            if site != expected[task_id]:
                raise ValueError(f"site mismatch for task {task_id}: {site}")
            if int(row.get("steps", 0)) > budgets_by_task[task_id]:
                raise ValueError(f"step budget exceeded for task {task_id}")
            trajectory = Path(str(row["trajectory_path"]))
            if not trajectory.is_file():
                raise FileNotFoundError(trajectory)
            by_mode[mode][task_id] = {
                **row,
                "site": site,
                "trajectory_sha256": sha256(trajectory),
            }

    # Every W4 source report that contributed rows must expose the frozen release.
    for record in world_records:
        if not record["result_rows"]:
            continue
        health = record.get("remote_agent_health") or {}
        release = str(health.get("release_fingerprint_sha256", ""))
        contributed = [
            row for row in world_rows
            if str(row.get("trajectory_path", ""))
        ]
        if contributed and release not in set(release_by_task.values()):
            raise ValueError(f"W4 release fingerprint mismatch: {record['path']}")

    expected_ids = set(expected)
    missing = {
        mode: sorted(expected_ids.difference(rows)) for mode, rows in by_mode.items()
    }
    complete = not missing["reactive"] and not missing["world-model"]
    shared = sorted(set(by_mode["reactive"]) & set(by_mode["world-model"]))
    comparison = None
    if shared:
        comparison = compare_success_rates(
            {str(task_id): float(by_mode["reactive"][task_id]["success"]) for task_id in shared},
            {str(task_id): float(by_mode["world-model"][task_id]["success"]) for task_id in shared},
        )
        comparison["scope"] = (
            "complete_30_task_development_pair"
            if complete
            else "partial_intersection_only_not_a_complete_development_result"
        )

    output = resolve(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Round-2 development split; policy iteration allowed; never a holdout claim.",
        "complete": complete,
        "expected_task_count": len(expected),
        "missing_task_ids": missing,
        "configs": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256(path),
                "freeze_sha256": config.get("freeze_sha256"),
                "task_count": len(config["task_ids"]),
            }
            for path, config in configs
        ],
        "source_reports": reactive_records + world_records,
        "metrics": {
            "reactive": summarize(list(by_mode["reactive"].values())),
            "world-model": summarize(list(by_mode["world-model"].values())),
        },
        "paired_online_comparison": comparison,
        "paired_rows": [
            {
                "task_id": task_id,
                "site": expected[task_id],
                "reactive_success": bool(by_mode["reactive"][task_id]["success"]),
                "world_model_success": bool(by_mode["world-model"][task_id]["success"]),
                "reactive_trajectory_sha256": by_mode["reactive"][task_id]["trajectory_sha256"],
                "world_model_trajectory_sha256": by_mode["world-model"][task_id]["trajectory_sha256"],
            }
            for task_id in shared
        ],
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in payload.items() if key != "paired_rows"}, ensure_ascii=False, indent=2))
    if not complete and not args.allow_incomplete:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
