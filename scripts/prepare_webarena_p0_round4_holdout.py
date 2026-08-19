"""Freeze the round-4 unseen 3-site holdout after improved dev gates.

Round-4 expands the prior design in two ways: more tasks per site (target 40)
and three frozen seeds (0/1/2) instead of seed 0 only.  It excludes every task
recorded in the repository (all dev/holdout/recovery/regression rounds), plus
tasks whose official evaluator needs OpenAI fuzzy matching, which cannot be
judged locally without an external API key.

Two gates must pass before freezing:
1. The round-3 development W4 analysis reports at least one online success and
   at least 25 judgeable W4 episodes (the round-3 gate).
2. The round-4 reactive development reports beat the round-3 dev baseline
   (2/28) with at least 4 judgeable successes, demonstrating that the base
   strategy improved on the same development split.
"""

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
from scripts.prepare_webarena_p0_round3_holdout import (  # noqa: E402
    ranked_ids,
    _is_fuzzy,
)


HOLDOUT_SALT = "p0-round4-holdout-v1"
DEFAULT_SEEDS = [0, 1, 2]


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
    parser.add_argument("--holdout-tasks-per-site", type=int, default=40)
    parser.add_argument("--step-budget", type=int, default=12)
    parser.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=DEFAULT_SEEDS,
        help="Frozen seeds; each seed multiplies the four 2x2 cells.",
    )
    parser.add_argument(
        "--dev-analysis",
        type=Path,
        default=ROOT / "data/reports/webarena_p0_round3_dev_analysis.json",
    )
    parser.add_argument(
        "--dev-config",
        type=Path,
        default=ROOT / "configs/webarena_p0_round3_dev.json",
    )
    parser.add_argument(
        "--v5-reactive-reports",
        type=Path,
        nargs="+",
        default=[
            ROOT / "data/reports/webarena_r3dev_v5_gitlab_reactive.json",
            ROOT / "data/reports/webarena_r3dev_v5_reddit_reactive.json",
            ROOT / "data/reports/webarena_r3dev_v5_shopping_reactive.json",
        ],
    )
    parser.add_argument(
        "--holdout-output",
        type=Path,
        default=ROOT / "configs/webarena_p0_round4_holdout_frozen.json",
    )
    return parser.parse_args()


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite frozen manifest: {path}")
    payload["freeze_sha256"] = _canonical_sha(payload)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def dev_gate_round3(analysis_path: Path) -> tuple[int, int]:
    payload = json.loads(analysis_path.read_text(encoding="utf-8"))
    metrics = payload.get("metrics") or {}
    world = metrics.get("world-model") or {}
    episodes = int(world.get("episodes", 0))
    successes = int(world.get("successes", 0))
    if episodes < 25:
        raise ValueError(
            f"round-3 dev analysis must contain at least 25 W4 episodes (got {episodes})"
        )
    if successes <= 0:
        raise ValueError("round-3 dev gate failed: W4 online SR is still zero")
    return successes, episodes


def dev_gate_reactive_v5(report_paths: list[Path]) -> tuple[int, int]:
    judged = 0
    successes = 0
    for path in report_paths:
        report = json.loads(path.read_text(encoding="utf-8"))
        rows = report.get("results", {}).get("reactive", [])
        judged += len(rows)
        successes += sum(1 for row in rows if row.get("success"))
    if judged < 25:
        raise ValueError(
            f"round-4 reactive dev must judge at least 25 episodes (got {judged})"
        )
    if successes < 4:
        raise ValueError(
            "round-4 reactive dev gate failed: base strategy must reach at least "
            f"4 successes on the dev split (got {successes}/{judged})"
        )
    return successes, judged


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
    w4_successes, w4_episodes = dev_gate_round3(args.dev_analysis)
    reactive_successes, reactive_episodes = dev_gate_reactive_v5(
        args.v5_reactive_reports
    )

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
    seeds = list(args.seeds)
    total_tasks = sum(actual_counts.values())
    write_manifest(
        args.holdout_output,
        {
            "schema_version": 1,
            "benchmark": (
                "Classic WebArena P0 round-4 unseen paired holdout "
                "(expanded tasks and seeds)"
            ),
            "frozen_at_utc": now,
            "frozen_before_any_holdout_episode": True,
            "selection_salt": HOLDOUT_SALT,
            "sites": list(SITES),
            "target_tasks_per_site": args.holdout_tasks_per_site,
            "tasks_per_site": actual_counts,
            "seeds": seeds,
            "depleted_site_note": (
                "Reddit's pool is exhausted by earlier rounds (round-1/2/3 "
                "holdouts, round-2/3 dev, regression rounds, fuzzy-evaluator "
                "exclusion); round-4 uses the maximum eligible Reddit tasks "
                "instead of 40."
            ),
            "selected_task_ids_by_site": selected_holdout,
            "cells": [
                "reactive_guard_off",
                "reactive_guard_on",
                "w4_guard_off",
                "w4_guard_on",
            ],
            "step_budget_per_episode": args.step_budget,
            "total_planned_episodes": 4 * len(seeds) * total_tasks,
            "task_feedback_used": False,
            "post_freeze_policy_changes_allowed": False,
            "excluded_evaluator_types": ["fuzzy_match"],
            "exclusion_note": (
                "Tasks whose official evaluator requires OpenAI fuzzy matching are "
                "excluded because no OPENAI_API_KEY is available; the holdout is "
                "fully judgeable with local evaluators only."
            ),
            "development_gate": {
                "round3_w4_analysis": args.dev_analysis.relative_to(ROOT).as_posix(),
                "round3_w4_successes": w4_successes,
                "round3_w4_episodes": w4_episodes,
                "round4_reactive_reports": [
                    path.relative_to(ROOT).as_posix()
                    for path in args.v5_reactive_reports
                ],
                "round4_reactive_successes": reactive_successes,
                "round4_reactive_episodes": reactive_episodes,
            },
            "release": release,
            "source": source,
            "claim_rule": "Report absolute pp, relative SR, and paired CI per seed and pooled; claim +10% only if established on this frozen holdout.",
        },
    )
    print(
        json.dumps(
            {
                "holdout_salt": HOLDOUT_SALT,
                "seeds": seeds,
                "selected": selected_holdout,
                "tasks_per_site": actual_counts,
                "total_tasks": total_tasks,
                "total_planned_episodes": 4 * len(seeds) * total_tasks,
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
