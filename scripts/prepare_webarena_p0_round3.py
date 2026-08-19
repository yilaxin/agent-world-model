#!/usr/bin/env python3
"""Prepare the round-3 development split for strategy iteration.

Round-3 uses a fresh development salt and excludes every task recorded in the
repository (phase-3 smoke, round-1 regression/holdout, round-2 dev/holdout and
recovery episodes).  The holdout for round-3 is intentionally NOT frozen here:
it may only be frozen after the round-3 development split demonstrates non-zero
online success under the improved strategy.
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

from scripts.freeze_webarena_p0_holdout import (  # noqa: E402
    SITES,
    _canonical_sha,
    _historical_task_ids,
)


DEV_SALT = "p0-round3-development-v1"


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
    parser.add_argument("--step-budget", type=int, default=12)
    parser.add_argument(
        "--dev-output", type=Path, default=ROOT / "configs/webarena_p0_round3_dev.json"
    )
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


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite prepared manifest: {path}")
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
        selected_dev[site] = ranked_ids(rows, site, excluded, DEV_SALT)[
            : args.dev_tasks_per_site
        ]
        excluded.update(selected_dev[site])
    now = datetime.now(timezone.utc).isoformat()
    source = {
        "task_count": len(rows),
        "task_source_sha256": hashlib.sha256(args.task_source.read_bytes()).hexdigest(),
        "source_wheel_sha256": hashlib.sha256(args.source_wheel.read_bytes()).hexdigest(),
    }
    for site, task_ids in selected_dev.items():
        site_path = args.dev_output.with_name(
            f"{args.dev_output.stem}_{site}{args.dev_output.suffix}"
        )
        write_manifest(
            site_path,
            {
                "schema_version": 1,
                "benchmark": "Classic WebArena P0 round-3 development split",
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
                    f"Round-3 {site} development tasks; policy iteration is allowed "
                    "and results are not eligible for the final holdout claim."
                ),
            },
        )
    write_manifest(
        args.dev_output,
        {
            "schema_version": 1,
            "benchmark": "Classic WebArena P0 round-3 development split",
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
            "gate": "Demonstrate non-zero online SR before freezing round-3 holdout.",
        },
    )
    print(json.dumps({"dev_salt": DEV_SALT, "selected": selected_dev}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
