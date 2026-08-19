"""Prepare the round-4 recovery config for environment-failed episodes.

Round-4 cell reports may contain episodes recorded as evaluator/environment
failures (e.g. a page navigation timeout across all seeds).  This script writes
a small per-task recovery config with the same frozen budget and seeds so the
affected episodes can be re-executed without touching the frozen policy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def canonical_sha(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", choices=("gitlab", "shopping"), required=True)
    parser.add_argument("--task-ids", type=int, nargs="+", required=True)
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    parser.add_argument(
        "--release-fingerprint",
        default="7e34a1e3c74252e8c3ab6ff6b29e2e40eda934e58d27a589c2e528d37c117f32",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = {
        "schema_version": 1,
        "benchmark": "Classic WebArena P0 round-4 environment-failure recovery",
        "required_sites": [args.site],
        "task_ids": args.task_ids,
        "task_sites": {str(task_id): args.site for task_id in args.task_ids},
        "seeds": args.seeds,
        "reactive_step_budget": 12,
        "world_model_step_budget": 12,
        "episode_max_attempts": 3,
        "evaluator_smoke_step_budget": 1,
        "evaluator_smoke_answers": {},
        "release_fingerprint_sha256": args.release_fingerprint,
        "task_feedback_used": False,
        "eligible_for_final_claim": True,
        "scope_limit": (
            f"Recovery of environment-failed round-4 {args.site} episodes "
            f"(tasks {args.task_ids}, seeds {args.seeds}); same frozen policy "
            "and budgets."
        ),
    }
    payload["freeze_sha256"] = canonical_sha(payload)
    output = args.output or (
        ROOT / "configs" / f"webarena_p0_round4_recovery_{args.site}_{'_'.join(map(str, args.task_ids))}.json"
    )
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(output.relative_to(ROOT))
    print("freeze_sha256:", payload["freeze_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
