#!/usr/bin/env python3
"""Combine clean-reset, single-mode WebArena reports into one formal report."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=PROJECT_ROOT / "configs" / "webarena_multisite_eval.json",
    )
    parser.add_argument("--report", type=Path, action="append", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "reports" / "webarena_online_evaluation_w4.json",
    )
    return parser.parse_args()


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    actions = sum(int(row["attempted_actions"]) for row in rows)
    return {
        "episodes": len(rows),
        "successes": sum(bool(row["success"]) for row in rows),
        "success_rate": sum(bool(row["success"]) for row in rows) / max(1, len(rows)),
        "action_execution_rate": sum(
            int(row["action_execution_successes"]) for row in rows
        ) / max(1, actions),
        "average_steps": sum(int(row["steps"]) for row in rows) / max(1, len(rows)),
        "average_latency_seconds": sum(float(row["elapsed_seconds"]) for row in rows)
        / max(1, len(rows)),
    }


def _source_record(path: Path) -> dict[str, Any]:
    content = path.read_bytes()
    return {
        "path": str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def main() -> int:
    args = parse_args()
    manifest_path = _resolve(args.manifest)
    output_path = _resolve(args.output)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    task_ids = [int(value) for value in manifest["task_ids"]]
    task_sites = {int(key): str(value) for key, value in manifest["task_sites"].items()}
    seeds = [int(value) for value in manifest["seeds"]]
    expected = {(mode, task_id, seed) for mode in ("reactive", "world-model") for task_id in task_ids for seed in seeds}

    combined: dict[str, list[dict[str, Any]]] = {"reactive": [], "world-model": []}
    seen: set[tuple[str, int, int]] = set()
    sources: list[dict[str, Any]] = []
    for raw_path in args.report:
        path = _resolve(raw_path)
        report = json.loads(path.read_text(encoding="utf-8"))
        if report.get("failures"):
            raise ValueError(f"source report contains failures: {path}")
        if report.get("benchmark") != manifest["benchmark"]:
            raise ValueError(f"source benchmark mismatch: {path}")
        if not bool(report.get("agent_success_rate_excludes_answer_injection")):
            raise ValueError(f"source does not attest answer-injection exclusion: {path}")
        sources.append(_source_record(path))
        for mode in ("reactive", "world-model"):
            for row in report.get("results", {}).get(mode, []):
                key = (mode, int(row["task_id"]), int(row["seed"]))
                if key in seen:
                    raise ValueError(f"duplicate formal episode: {key}")
                if key not in expected:
                    raise ValueError(f"unexpected formal episode: {key}")
                if bool(row.get("uses_expected_answer")):
                    raise ValueError(f"answer injection is forbidden in formal episode: {key}")
                if str(row.get("mode")) != mode:
                    raise ValueError(f"row mode mismatch in formal episode: {key}")
                if str(row.get("site")) != task_sites[key[1]]:
                    raise ValueError(f"row site mismatch in formal episode: {key}")
                attempts = int(row.get("episode_attempts", 0))
                if not 1 <= attempts <= int(manifest.get("episode_max_attempts", 1)):
                    raise ValueError(f"invalid episode attempt count: {key}")
                if int(row["steps"]) > int(
                    manifest[f"{'reactive' if mode == 'reactive' else 'world_model'}_step_budget"]
                ):
                    raise ValueError(f"episode exceeded fixed step budget: {key}")
                attempted_actions = int(row["attempted_actions"])
                execution_successes = int(row["action_execution_successes"])
                if not 0 <= execution_successes <= attempted_actions:
                    raise ValueError(f"invalid action execution counts: {key}")
                trajectory_path = _resolve(Path(str(row["trajectory_path"])))
                if not trajectory_path.is_file():
                    raise ValueError(f"archived trajectory is unavailable: {key}")
                expected_digest = str(row.get("trajectory_sha256", ""))
                actual_digest = hashlib.sha256(trajectory_path.read_bytes()).hexdigest()
                if not expected_digest or actual_digest != expected_digest:
                    raise ValueError(f"archived trajectory digest mismatch: {key}")
                seen.add(key)
                combined[mode].append(row)
    missing = sorted(expected - seen)
    if missing:
        raise ValueError(f"formal reports are incomplete; missing: {missing}")

    reactive_budget = int(manifest["reactive_step_budget"])
    world_model_budget = int(manifest["world_model_step_budget"])
    for source in args.report:
        report = json.loads(_resolve(source).read_text(encoding="utf-8"))
        budgets = report["budgets"]
        if int(budgets["reactive_steps"]) != reactive_budget:
            raise ValueError(f"reactive budget mismatch in {source}")
        if int(budgets["world_model_steps"]) != world_model_budget:
            raise ValueError(f"world-model budget mismatch in {source}")

    from agent_world_model.experiment_stats import compare_success_rates

    paired = compare_success_rates(
        {f"{row['task_id']}:{row['seed']}": float(bool(row["success"])) for row in combined["reactive"]},
        {f"{row['task_id']}:{row['seed']}": float(bool(row["success"])) for row in combined["world-model"]},
    )
    per_site: dict[str, dict[str, dict[str, Any]]] = {}
    for mode, rows in combined.items():
        for site in sorted({str(row["site"]) for row in rows}):
            per_site.setdefault(site, {})[mode] = _summarize(
                [row for row in rows if str(row["site"]) == site]
            )
    payload = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "benchmark": manifest["benchmark"],
        "protocol": "Each mode ran in a separately recreated site container from the same immutable image.",
        "evaluation_status": manifest.get("evaluation_status", "unspecified"),
        "task_feedback_used": bool(manifest.get("task_feedback_used", False)),
        "shared_navigation_guard": bool(manifest.get("shared_navigation_guard", False)),
        "world_model_attribution_claim": False,
        "methodology_notes": list(manifest.get("notes", [])),
        "fixed_task_ids": task_ids,
        "fixed_seeds": seeds,
        "budgets": {"reactive_steps": reactive_budget, "world_model_steps": world_model_budget},
        "agent_metrics": _summarize(combined["reactive"]),
        "world_model_agent_metrics": _summarize(combined["world-model"]),
        "per_site_metrics": per_site,
        "paired_online_comparison": paired,
        "agent_success_rate_excludes_answer_injection": True,
        "scope_limit": manifest["scope_limit"],
        "source_reports": sources,
        "results": combined,
        "failures": [],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in payload.items() if key != "results"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
