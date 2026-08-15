#!/usr/bin/env python3
"""Derive evaluator-ready site configs from the frozen round-2 master manifest.

This is mechanical post-freeze orchestration: it does not select or replace
tasks and it copies the frozen release fingerprint and budget verbatim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SITES = ("gitlab", "reddit", "shopping")


def canonical_sha(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "configs" / "webarena_p0_round2_holdout_frozen.json",
    )
    parser.add_argument("--output-dir", type=Path, default=ROOT / "configs")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    frozen = dict(manifest)
    declared = str(frozen.pop("freeze_sha256", ""))
    computed = canonical_sha(frozen)
    if not declared or declared != computed:
        raise ValueError(
            f"round-2 master freeze mismatch: declared={declared!r}, computed={computed!r}"
        )
    if not bool(manifest.get("frozen_before_any_holdout_episode")):
        raise ValueError("manifest was not frozen before holdout execution")
    if bool(manifest.get("task_feedback_used")):
        raise ValueError("task feedback is forbidden for the holdout")
    if manifest.get("sites") != list(SITES):
        raise ValueError("unexpected site set or ordering")
    if int(manifest.get("tasks_per_site", 0)) != 30:
        raise ValueError("round-2 holdout must contain 30 tasks per site")
    if int(manifest.get("step_budget_per_episode", 0)) != 12:
        raise ValueError("round-2 holdout must retain the frozen 12-step budget")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    parent_path = args.manifest.resolve().relative_to(ROOT).as_posix()
    outputs: dict[str, Any] = {}
    for site in SITES:
        task_ids = [
            int(task_id)
            for task_id in manifest["selected_task_ids_by_site"][site]
        ]
        if len(task_ids) != 30 or len(set(task_ids)) != 30:
            raise ValueError(f"{site} task selection is not 30 unique IDs")
        payload: dict[str, Any] = {
            "schema_version": 1,
            "benchmark": "Classic WebArena P0 round-2 unseen paired holdout",
            "frozen_at_utc": manifest["frozen_at_utc"],
            "selection_salt": manifest["selection_salt"],
            "required_sites": [site],
            "task_ids": task_ids,
            "task_sites": {str(task_id): site for task_id in task_ids},
            "seeds": [0],
            "reactive_step_budget": 12,
            "world_model_step_budget": 12,
            "episode_max_attempts": 2,
            "evaluator_smoke_step_budget": 1,
            "evaluator_smoke_answers": {},
            "release_fingerprint_sha256": manifest["release"]["sha256"],
            "task_feedback_used": False,
            "post_freeze_policy_changes_allowed": False,
            "parent_manifest": {
                "path": parent_path,
                "file_sha256": file_sha(args.manifest),
                "freeze_sha256": declared,
            },
            "source": manifest["source"],
            "scope_limit": (
                f"Thirty unseen frozen round-2 {site} tasks; paired 2x2 holdout "
                "only, not the full 812-task WebArena benchmark."
            ),
        }
        payload["freeze_sha256"] = canonical_sha(payload)
        output = args.output_dir / f"webarena_p0_round2_holdout_{site}_frozen.json"
        if output.exists():
            existing = json.loads(output.read_text(encoding="utf-8"))
            if existing != payload:
                raise FileExistsError(f"refusing to overwrite non-identical {output}")
        else:
            output.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        outputs[site] = {
            "path": output.resolve().relative_to(ROOT).as_posix(),
            "freeze_sha256": payload["freeze_sha256"],
            "file_sha256": file_sha(output),
        }
    print(json.dumps({"master_freeze_sha256": declared, "sites": outputs}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
