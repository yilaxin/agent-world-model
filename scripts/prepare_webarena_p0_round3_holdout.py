#!/usr/bin/env python3
"""Freeze the round-3 unseen 3-site holdout after a non-zero dev gate.

Round-3 holdout selection:
1. Excludes every task recorded in the repository (phase-3 smoke, round-1/2
   dev/holdout/recovery, round-3 dev) plus the round-3 dev split itself.
2. Excludes tasks whose official evaluator requires OpenAI fuzzy string
   matching, because this environment has no OPENAI_API_KEY and those tasks
   cannot be judged without an external service.  This is a documented
   methodology choice; the holdout covers program_html/url_match/string_exact
   evaluators that are fully judgeable locally.
3. Freezes only after the supplied round-3 development analysis demonstrates
   at least one real online success (and reports at least 30 W4 episodes).
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


HOLDOUT_SALT = "p0-round3-holdout-v1"


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
    parser.add_argument(
        "--holdout-tasks-per-site",
        type=int,
        default=30,
        help="Target tasks per site; sites with a depleted pool use the maximum available.",
    )
    parser.add_argument("--step-budget", type=int, default=12)
    parser.add_argument("--dev-analysis", type=Path, required=True)
    parser.add_argument(
        "--dev-config", type=Path, default=ROOT / "configs/webarena_p0_round3_dev.json"
    )
    parser.add_argument(
        "--holdout-output",
        type=Path,
        default=ROOT / "configs/webarena_p0_round3_holdout_frozen.json",
    )
    return parser.parse_args()


def ranked_ids(rows: list[dict[str, Any]], site: str, excluded: set[int], salt: str) -> list[int]:
    eligible = [
        int(row["task_id"])
        for row in rows
        if row.get("sites") == [site]
        and int(row["task_id"]) not in excluded
        and not _is_fuzzy(row)
    ]
    return sorted(
        eligible,
        key=lambda task_id: (
            hashlib.sha256(f"{salt}|{site}|{task_id}".encode()).hexdigest(),
            task_id,
        ),
    )


def _is_fuzzy(row: dict[str, Any]) -> bool:
    reference_answers = (row.get("eval") or {}).get("reference_answers") or {}
    return "fuzzy_match" in reference_answers


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite frozen manifest: {path}")
    payload["freeze_sha256"] = _canonical_sha(payload)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dev_gate(analysis_path: Path) -> tuple[int, int]:
    payload = json.loads(analysis_path.read_text(encoding="utf-8"))
    metrics = payload.get("metrics") or {}
    world = metrics.get("world-model") or {}
    episodes = int(world.get("episodes", 0))
    successes = int(world.get("successes", 0))
    if episodes < 25:
        raise ValueError(
            f"development analysis must contain at least 25 judgeable W4 episodes "
            f"(got {episodes})"
        )
    return successes, episodes


def main() -> int:
    args = parse_args()
    rows = json.loads(args.task_source.read_text(encoding="utf-8"))
    if len(rows) != 812:
        raise RuntimeError("expected the 812-row Classic WebArena task source")
    historical, evidence = _historical_task_ids()
    dev_config = json.loads(args.dev_config.read_text(encoding="utf-8"))
    dev_tasks = {
        int(task_id)
        for task_ids in dev_config["selected_task_ids_by_site"].values()
        for task_id in task_ids
    }
    excluded = set(historical) | dev_tasks
    successes, episodes = dev_gate(args.dev_analysis)
    if successes <= 0:
        raise RuntimeError("round-3 holdout gate failed: dev W4 online SR is still zero")

    selected_holdout: dict[str, list[int]] = {}
    actual_counts: dict[str, int] = {}
    for site in SITES:
        eligible = ranked_ids(rows, site, excluded, HOLDOUT_SALT)
        chosen = eligible[: args.holdout_tasks_per_site]
        actual_counts[site] = len(chosen)
        selected_holdout[site] = chosen
        excluded.update(chosen)
    now = datetime.now(timezone.utc).isoformat()
    release = release_fingerprint(
        release_files(
            ROOT,
            ROOT / "artifacts/phase4/world_model_ensemble_w4.json",
            ROOT / "artifacts/phase3/structure_aligner_best.pt",
            ROOT / "configs/phase3_planner.json",
        ),
        root=ROOT,
    )
    source = {
        "task_count": len(rows),
        "task_source_sha256": sha256_file(args.task_source),
        "source_wheel_sha256": sha256_file(args.source_wheel),
    }
    write_manifest(
        args.holdout_output,
        {
            "schema_version": 1,
            "benchmark": "Classic WebArena P0 round-3 unseen paired holdout",
            "frozen_at_utc": now,
            "frozen_before_any_holdout_episode": True,
            "selection_salt": HOLDOUT_SALT,
            "sites": list(SITES),
            "target_tasks_per_site": args.holdout_tasks_per_site,
            "tasks_per_site": actual_counts,
            "depleted_site_note": (
                "Reddit's pool is exhausted by earlier rounds (round-1/2 holdouts, "
                "round-2/3 dev, fuzzy-evaluator exclusion); the third holdout uses "
                "the maximum eligible Reddit tasks instead of 30."
            ),
            "selected_task_ids_by_site": selected_holdout,
            "cells": ["reactive_guard_off", "reactive_guard_on", "w4_guard_off", "w4_guard_on"],
            "step_budget_per_episode": args.step_budget,
            "total_planned_episodes": 4 * sum(actual_counts.values()),
            "task_feedback_used": False,
            "post_freeze_policy_changes_allowed": False,
            "excluded_evaluator_types": ["fuzzy_match"],
            "exclusion_note": (
                "Tasks whose official evaluator requires OpenAI fuzzy matching are "
                "excluded because no OPENAI_API_KEY is available; the holdout is "
                "fully judgeable with local evaluators only."
            ),
            "development_gate": {
                "analysis": args.dev_analysis.relative_to(ROOT).as_posix(),
                "analysis_sha256": sha256_file(args.dev_analysis),
                "successes": successes,
                "episodes": episodes,
            },
            "release": release,
            "source": source,
            "claim_rule": "Report absolute pp, relative SR, and paired CI; claim +10% only if established here.",
        },
    )
    print(
        json.dumps(
            {
                "holdout_salt": HOLDOUT_SALT,
                "selected": selected_holdout,
                "tasks_per_site": actual_counts,
                "total_planned_episodes": 4 * sum(actual_counts.values()),
                "release_sha256": release["sha256"],
                "freeze_sha256": json.loads(
                    args.holdout_output.read_text(encoding="utf-8")
                )["freeze_sha256"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
