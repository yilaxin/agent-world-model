#!/usr/bin/env python3
"""Freeze the unseen three-site P0 holdout before any evaluation runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_world_model.release_fingerprint import (  # noqa: E402
    release_files,
    release_fingerprint,
    sha256_file,
)


SITES = ("gitlab", "reddit", "shopping")
SELECTION_SALT = "p0-holdout-v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--task-source",
        type=Path,
        default=PROJECT_ROOT / "tmp" / "p0_source" / "test.raw.json",
    )
    parser.add_argument(
        "--source-wheel",
        type=Path,
        default=PROJECT_ROOT
        / "tmp"
        / "p0_source"
        / "libwebarena-0.0.4-py3-none-any.whl",
    )
    parser.add_argument(
        "--master",
        type=Path,
        default=PROJECT_ROOT / "configs" / "webarena_p0_holdout_frozen.json",
    )
    parser.add_argument("--tasks-per-site", type=int, default=30)
    parser.add_argument("--step-budget", type=int, default=12)
    return parser.parse_args()


def _canonical_sha(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _historical_task_ids() -> tuple[list[int], dict[str, list[str]]]:
    evidence: dict[int, set[str]] = defaultdict(set)
    paths = list((PROJECT_ROOT / "configs").glob("webarena*.json"))
    paths += list((PROJECT_ROOT / "data" / "reports").glob("webarena*.json"))
    for path in paths:
        if path.name.startswith("webarena_p0_holdout"):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        def walk(value: Any, key: str = "") -> None:
            if isinstance(value, dict):
                for nested_key, nested_value in value.items():
                    walk(nested_value, str(nested_key))
            elif isinstance(value, list):
                if key in {"task_ids", "fixed_task_ids"}:
                    for item in value:
                        if isinstance(item, int):
                            evidence[item].add(path.relative_to(PROJECT_ROOT).as_posix())
                for item in value:
                    walk(item, key)
            elif key == "task_id" and isinstance(value, int):
                evidence[value].add(path.relative_to(PROJECT_ROOT).as_posix())

        walk(payload)
    for base in (PROJECT_ROOT / "data").glob("trajectories_webarena*"):
        for path in base.rglob("*.jsonl"):
            match = re.search(r"webarena[._](\d+)", path.name)
            if match:
                evidence[int(match.group(1))].add(
                    path.relative_to(PROJECT_ROOT).as_posix()
                )
    return sorted(evidence), {
        str(task_id): sorted(paths) for task_id, paths in sorted(evidence.items())
    }


def _freeze(payload: dict[str, Any]) -> dict[str, Any]:
    frozen = dict(payload)
    frozen["freeze_sha256"] = _canonical_sha(payload)
    return frozen


def main() -> int:
    args = parse_args()
    if args.master.exists():
        raise FileExistsError(
            f"refusing to overwrite an existing frozen manifest: {args.master}"
        )
    source_rows = json.loads(args.task_source.read_text(encoding="utf-8"))
    by_id = {int(row["task_id"]): row for row in source_rows}
    if len(source_rows) != 812 or len(by_id) != 812:
        raise RuntimeError("expected the 812-row Classic WebArena task source")
    excluded_ids, exclusion_evidence = _historical_task_ids()
    excluded = set(excluded_ids)
    release = release_fingerprint(
        release_files(
            PROJECT_ROOT,
            PROJECT_ROOT / "artifacts" / "phase4" / "world_model_ensemble_w4.json",
            PROJECT_ROOT / "artifacts" / "phase3" / "structure_aligner_best.pt",
            PROJECT_ROOT / "configs" / "phase3_planner.json",
        ),
        root=PROJECT_ROOT,
    )
    frozen_at = datetime.now(timezone.utc).isoformat()
    selected_by_site: dict[str, list[int]] = {}
    site_config_hashes: dict[str, str] = {}
    site_config_paths: dict[str, str] = {}
    task_audit: dict[str, Any] = {}
    for site in SITES:
        eligible = [
            int(row["task_id"])
            for row in source_rows
            if row.get("sites") == [site] and int(row["task_id"]) not in excluded
        ]
        ranked = sorted(
            eligible,
            key=lambda task_id: (
                hashlib.sha256(
                    f"{SELECTION_SALT}|{site}|{task_id}".encode("utf-8")
                ).hexdigest(),
                task_id,
            ),
        )
        selected = ranked[: args.tasks_per_site]
        if len(selected) != args.tasks_per_site:
            raise RuntimeError(f"not enough eligible {site} tasks")
        selected_by_site[site] = selected
        for task_id in selected:
            row = by_id[task_id]
            task_audit[str(task_id)] = {
                "site": site,
                "task_record_sha256": _canonical_sha(row),
                "intent_template_id": row.get("intent_template_id"),
                "eval_types": list(row.get("eval", {}).get("eval_types", [])),
                "require_login": bool(row.get("require_login")),
                "require_reset": bool(row.get("require_reset")),
            }
        site_payload = {
            "schema_version": 2,
            "benchmark": "Classic WebArena P0 unseen hash-selected three-site holdout",
            "frozen_at_utc": frozen_at,
            "selection_salt": SELECTION_SALT,
            "selection_rule": (
                "Single-site tasks only; exclude every historical config/report/trajectory "
                "task ID; sort by SHA256(salt|site|task_id); take first N."
            ),
            "source": {
                "browsergym_webarena_version": "0.14.3",
                "libwebarena_version": "0.0.4",
                "webarena_verified_version": "1.2.3",
                "task_count": 812,
                "task_source_sha256": sha256_file(args.task_source),
                "source_wheel_sha256": sha256_file(args.source_wheel),
            },
            "required_sites": [site],
            "task_ids": selected,
            "task_sites": {str(task_id): site for task_id in selected},
            "task_audit": {str(task_id): task_audit[str(task_id)] for task_id in selected},
            "historical_excluded_task_ids": excluded_ids,
            "seeds": [0],
            "reactive_step_budget": args.step_budget,
            "world_model_step_budget": args.step_budget,
            "episode_max_attempts": 2,
            "evaluator_smoke_step_budget": 1,
            "evaluator_smoke_answers": {},
            "release_fingerprint_sha256": release["sha256"],
            "task_feedback_used": False,
            "post_freeze_policy_changes_allowed": False,
            "scope_limit": (
                f"Thirty unseen, hash-selected, single-site {site} tasks; paired 2x2 "
                "evaluation only, not the full 812-task WebArena benchmark."
            ),
        }
        frozen_site = _freeze(site_payload)
        site_path = args.master.with_name(f"webarena_p0_holdout_{site}_frozen.json")
        if site_path.exists():
            raise FileExistsError(f"refusing to overwrite {site_path}")
        site_path.write_text(
            json.dumps(frozen_site, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        site_config_hashes[site] = frozen_site["freeze_sha256"]
        site_config_paths[site] = site_path.relative_to(PROJECT_ROOT).as_posix()
    master_payload = {
        "schema_version": 2,
        "benchmark": "Classic WebArena P0 unseen 2x2 holdout",
        "frozen_at_utc": frozen_at,
        "frozen_before_any_holdout_episode": True,
        "task_feedback_used": False,
        "sites": list(SITES),
        "tasks_per_site": args.tasks_per_site,
        "total_unique_tasks": sum(len(items) for items in selected_by_site.values()),
        "seeds": [0],
        "step_budget_per_episode": args.step_budget,
        "cells": [
            "reactive_guard_off",
            "reactive_guard_on",
            "w4_guard_off",
            "w4_guard_on",
        ],
        "total_planned_episodes": 4
        * sum(len(items) for items in selected_by_site.values()),
        "selection_salt": SELECTION_SALT,
        "selected_task_ids_by_site": selected_by_site,
        "task_audit": task_audit,
        "historical_excluded_task_ids": excluded_ids,
        "historical_exclusion_evidence": exclusion_evidence,
        "source": {
            "browsergym_webarena_version": "0.14.3",
            "libwebarena_version": "0.0.4",
            "webarena_verified_version": "1.2.3",
            "task_count": 812,
            "task_source_sha256": sha256_file(args.task_source),
            "source_wheel_sha256": sha256_file(args.source_wheel),
        },
        "release": release,
        "site_config_paths": site_config_paths,
        "site_config_freeze_sha256": site_config_hashes,
        "claim_rule": (
            "Relative SR +10% may be declared only from this frozen holdout, "
            "with absolute percentage-point and relative changes both reported."
        ),
        "post_freeze_rule": (
            "No task replacement, task-feedback repair, policy tuning, guard change, "
            "weight change, or budget change after this timestamp."
        ),
    }
    master = _freeze(master_payload)
    args.master.write_text(
        json.dumps(master, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "master": str(args.master),
                "freeze_sha256": master["freeze_sha256"],
                "release_fingerprint_sha256": release["sha256"],
                "selected_task_ids_by_site": selected_by_site,
                "historical_excluded_task_ids": excluded_ids,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
