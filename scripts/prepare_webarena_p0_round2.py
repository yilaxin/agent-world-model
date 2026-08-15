#!/usr/bin/env python3
"""Prepare a development split and gate freezing of the second unseen P0 holdout.

The development split may be used for policy iteration.  The second holdout is
written only after a supplied online development report demonstrates non-zero
success, and it excludes every task recorded by the repository plus the dev set.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_world_model.release_fingerprint import (  # noqa: E402
    release_files,
    release_fingerprint,
    sha256_file,
)
from scripts.freeze_webarena_p0_holdout import (  # noqa: E402
    SITES,
    _canonical_sha,
    _historical_task_ids,
)


DEV_SALT = "p0-round2-development-v1"
HOLDOUT_SALT = "p0-round2-holdout-v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--task-source", type=Path, default=ROOT / "tmp/p0_source/test.raw.json"
    )
    parser.add_argument(
        "--source-wheel",
        type=Path,
        default=ROOT / "tmp/p0_source/libwebarena-0.0.4-py3-none-any.whl",
    )
    parser.add_argument("--dev-tasks-per-site", type=int, default=10)
    parser.add_argument("--holdout-tasks-per-site", type=int, default=30)
    parser.add_argument("--step-budget", type=int, default=12)
    parser.add_argument(
        "--dev-output", type=Path, default=ROOT / "configs/webarena_p0_round2_dev.json"
    )
    parser.add_argument(
        "--holdout-output",
        type=Path,
        default=ROOT / "configs/webarena_p0_round2_holdout_frozen.json",
    )
    parser.add_argument(
        "--freeze-holdout",
        action="store_true",
        help="Freeze round-2 holdout after validating --dev-report.",
    )
    parser.add_argument("--dev-report", type=Path)
    return parser.parse_args()


def ranked_ids(rows: list[dict[str, Any]], site: str, excluded: set[int], salt: str) -> list[int]:
    eligible = [
        int(row["task_id"])
        for row in rows
        if row.get("sites") == [site] and int(row["task_id"]) not in excluded
    ]
    return sorted(
        eligible,
        key=lambda task_id: (
            hashlib.sha256(f"{salt}|{site}|{task_id}".encode()).hexdigest(),
            task_id,
        ),
    )


def dev_successes(path: Path) -> tuple[int, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "complete" in payload:
        if not bool(payload["complete"]):
            raise ValueError("development analysis is incomplete; refusing to freeze holdout")
        metrics = payload.get("metrics") or {}
        world_model = metrics.get("world-model") if isinstance(metrics, dict) else None
        if isinstance(world_model, dict) and "successes" in world_model:
            episodes = int(world_model.get("episodes", 0))
            if episodes < 30:
                raise ValueError("development analysis must contain at least 30 W4 episodes")
            return int(world_model["successes"]), episodes
    rows = payload.get("episodes") or payload.get("results") or []
    if rows:
        return sum(bool(row.get("success")) for row in rows), len(rows)
    metrics = payload.get("cell_metrics") or payload.get("summary") or {}
    if isinstance(metrics, dict) and "successes" in metrics:
        return int(metrics["successes"]), int(metrics.get("episodes", 0))
    raise ValueError("development report contains no auditable episode outcomes")


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite frozen/prepared manifest: {path}")
    payload["freeze_sha256"] = _canonical_sha(payload)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    rows = json.loads(args.task_source.read_text(encoding="utf-8"))
    if len(rows) != 812:
        raise RuntimeError("expected the 812-row Classic WebArena task source")
    historical, evidence = _historical_task_ids()
    excluded = set(historical)
    selected_dev: dict[str, list[int]] = {}
    for site in SITES:
        selected_dev[site] = ranked_ids(rows, site, excluded, DEV_SALT)[: args.dev_tasks_per_site]
        excluded.update(selected_dev[site])
    now = datetime.now(timezone.utc).isoformat()
    source = {
        "task_count": len(rows),
        "task_source_sha256": sha256_file(args.task_source),
        "source_wheel_sha256": sha256_file(args.source_wheel),
    }
    if not args.freeze_holdout:
        for site, task_ids in selected_dev.items():
            site_path = args.dev_output.with_name(
                f"{args.dev_output.stem}_{site}{args.dev_output.suffix}"
            )
            write_manifest(
                site_path,
                {
                    "schema_version": 1,
                    "benchmark": "Classic WebArena P0 round-2 development split",
                    "frozen_at_utc": now,
                    "selection_salt": DEV_SALT,
                    "required_sites": [site],
                    "task_ids": task_ids,
                    "task_sites": {str(task_id): site for task_id in task_ids},
                    "seeds": [0],
                    "reactive_step_budget": args.step_budget,
                    "world_model_step_budget": args.step_budget,
                    "episode_max_attempts": 2,
                    "evaluator_smoke_step_budget": 1,
                    "evaluator_smoke_answers": {},
                    "task_feedback_allowed": True,
                    "eligible_for_final_claim": False,
                    "source": source,
                    "scope_limit": (
                        f"Round-2 {site} development tasks; policy iteration is allowed "
                        "and results are not eligible for the final holdout claim."
                    ),
                },
            )
        write_manifest(
            args.dev_output,
            {
                "schema_version": 1,
                "benchmark": "Classic WebArena P0 round-2 development split",
                "frozen_at_utc": now,
                "selection_salt": DEV_SALT,
                "sites": list(SITES),
                "tasks_per_site": args.dev_tasks_per_site,
                "selected_task_ids_by_site": selected_dev,
                "step_budget_per_episode": args.step_budget,
                "task_feedback_allowed": True,
                "eligible_for_final_claim": False,
                "historical_excluded_task_ids": historical,
                "historical_exclusion_evidence": evidence,
                "source": source,
                "gate": "Demonstrate non-zero online SR before freezing round-2 holdout.",
            },
        )
        print(args.dev_output)
        return 0
    if args.dev_report is None or not args.dev_report.exists():
        raise FileNotFoundError("--freeze-holdout requires an existing --dev-report")
    successes, episodes = dev_successes(args.dev_report)
    if successes <= 0:
        raise RuntimeError("round-2 holdout gate failed: online development SR is still zero")
    selected_holdout: dict[str, list[int]] = {}
    for site in SITES:
        chosen = ranked_ids(rows, site, excluded, HOLDOUT_SALT)[: args.holdout_tasks_per_site]
        if len(chosen) != args.holdout_tasks_per_site:
            raise RuntimeError(f"not enough eligible {site} tasks")
        selected_holdout[site] = chosen
        excluded.update(chosen)
    release = release_fingerprint(
        release_files(
            ROOT,
            ROOT / "artifacts/phase4/world_model_ensemble_w4.json",
            ROOT / "artifacts/phase3/structure_aligner_best.pt",
            ROOT / "configs/phase3_planner.json",
        ),
        root=ROOT,
    )
    write_manifest(
        args.holdout_output,
        {
            "schema_version": 1,
            "benchmark": "Classic WebArena P0 round-2 unseen paired holdout",
            "frozen_at_utc": now,
            "frozen_before_any_holdout_episode": True,
            "selection_salt": HOLDOUT_SALT,
            "sites": list(SITES),
            "tasks_per_site": args.holdout_tasks_per_site,
            "selected_task_ids_by_site": selected_holdout,
            "cells": ["reactive_guard_off", "reactive_guard_on", "w4_guard_off", "w4_guard_on"],
            "step_budget_per_episode": args.step_budget,
            "total_planned_episodes": 4 * args.holdout_tasks_per_site * len(SITES),
            "task_feedback_used": False,
            "post_freeze_policy_changes_allowed": False,
            "development_gate": {
                "report": args.dev_report.relative_to(ROOT).as_posix(),
                "report_sha256": sha256_file(args.dev_report),
                "successes": successes,
                "episodes": episodes,
            },
            "release": release,
            "source": source,
            "claim_rule": "Report absolute pp, relative SR, and paired CI; claim +10% only if established here.",
        },
    )
    print(args.holdout_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
