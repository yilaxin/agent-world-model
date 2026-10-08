#!/usr/bin/env python3
"""Freeze the W1 baseline working set.

The W1 loop needs a task set that is (a) never used for tuning before, (b) never
part of any frozen holdout, and (c) small enough to re-run weekly.  Because
earlier rounds consumed almost the whole pool, the working set is simply *all*
remaining eligible tasks: the selection is forced, not sampled, so there is no
selection freedom to abuse.

Eligibility follows scripts/prepare_webarena_p0_round3_holdout.py:
``sites == [site]``, the official evaluator is not ``fuzzy_match``, and the task
id does not appear in any config, report or trajectory already in the project.

Results on this set are explicitly *not* eligible for the final claim; they
exist to steer strategy work.  The confirmatory set is frozen separately by
scripts/freeze_webarena_round5_confirmatory.py.
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

from scripts.freeze_webarena_p0_holdout import (  # noqa: E402
    _canonical_sha,
    _historical_task_ids,
)
from scripts.prepare_webarena_p0_round3_holdout import _is_fuzzy  # noqa: E402


SALT = "w1-workingset-v1"
DEFAULT_SITES = ["gitlab", "shopping"]
RELEASE_FINGERPRINT = "7e34a1e3c74252e8c3ab6ff6b29e2e40eda934e58d27a589c2e528d37c117f32"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--task-source", type=Path, default=ROOT / "tmp/p0_source/test.raw.json"
    )
    parser.add_argument("--output-dir", type=Path, default=ROOT / "configs")
    parser.add_argument("--sites", nargs="+", default=DEFAULT_SITES)
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    parser.add_argument("--step-budget", type=int, default=12)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = json.loads(args.task_source.read_text(encoding="utf-8"))
    if len(rows) != 812:
        raise RuntimeError("expected the 812-row Classic WebArena task source")
    used, evidence = _historical_task_ids()
    used_set = set(int(task) for task in used)
    # `_historical_task_ids` scans configs/*.json, which includes the working-set
    # and confirmatory manifests this script family produces.  Ignore their own
    # declared task ids, otherwise a second run would consume its own output and
    # report an empty pool.
    for pattern in (
        "webarena_w1_workingset_*.json",
        "webarena_p0_round5_confirmatory*.json",
    ):
        for path in (ROOT / "configs").glob(pattern):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for value in payload.get("task_ids") or []:
                used_set.discard(int(value))
            for values in (payload.get("selected_task_ids_by_site") or {}).values():
                for value in values or []:
                    used_set.discard(int(value))
    print(f"tasks recorded anywhere in the repository: {len(used_set)}")

    frozen_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    summary: dict[str, Any] = {"sites": {}, "frozen_at_utc": frozen_at, "salt": SALT}
    for site in args.sites:
        eligible = [
            int(row["task_id"])
            for row in rows
            if row.get("sites") == [site]
            and int(row["task_id"]) not in used_set
            and not _is_fuzzy(row)
        ]
        eligible.sort()
        if not eligible:
            raise RuntimeError(f"{site}: no eligible task left for the working set")
        payload: dict[str, Any] = {
            "schema_version": 1,
            "benchmark": f"W1 baseline working set ({site}, seed 0/1/2)",
            "frozen_at_utc": frozen_at,
            "selection_salt": SALT,
            "required_sites": [site],
            "task_ids": eligible,
            "task_sites": {str(task): site for task in eligible},
            "seeds": list(args.seeds),
            "reactive_step_budget": args.step_budget,
            "world_model_step_budget": args.step_budget,
            "episode_max_attempts": 3,
            "task_feedback_allowed": True,
            "eligible_for_final_claim": False,
            "evaluator_smoke_step_budget": 1,
            "evaluator_smoke_answers": {},
            "release_fingerprint_sha256": RELEASE_FINGERPRINT,
            "source": {
                "task_count": len(rows),
                "task_source": args.task_source.name,
            },
            "selection_rule": (
                "All remaining eligible tasks: sites == [site], evaluator is not "
                "fuzzy_match, and the task id is absent from every config, report "
                "and trajectory already recorded in the project. The selection is "
                "forced by exhaustion, so no sampling freedom exists."
            ),
            "scope_limit": (
                "Working set for W1 strategy iteration. Results steer development and "
                "are NOT eligible for the final +10% claim; the confirmatory set is "
                "configs/webarena_p0_round5_confirmatory_frozen.json."
            ),
        }
        payload["freeze_sha256"] = _canonical_sha(payload)
        path = args.output_dir / f"webarena_w1_workingset_{site}.json"
        if path.exists() and not args.force:
            raise FileExistsError(f"refusing to overwrite {path}; pass --force to replace")
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary["sites"][site] = {
            "tasks": len(eligible),
            "seeds": len(args.seeds),
            "episodes_per_arm": len(eligible) * len(args.seeds),
            "config": path.relative_to(ROOT).as_posix(),
            "freeze_sha256": payload["freeze_sha256"],
        }
        print(
            f"{site}: {len(eligible)} tasks x {len(args.seeds)} seeds = "
            f"{len(eligible) * len(args.seeds)} episodes per arm -> {path.name}"
        )
        print(f"    freeze_sha256 {payload['freeze_sha256']}")

    total = sum(entry["episodes_per_arm"] for entry in summary["sites"].values())
    print(f"total episodes per arm across sites: {total}")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
