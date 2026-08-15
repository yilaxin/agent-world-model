#!/usr/bin/env python3
"""Fail closed if a frozen P0 manifest or Agent release has drifted."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_world_model.release_fingerprint import (  # noqa: E402
    release_fingerprint,
)


def canonical_sha(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def verify_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    declared = str(payload.pop("freeze_sha256", ""))
    computed = canonical_sha(payload)
    if not declared or declared != computed:
        raise RuntimeError(
            f"freeze hash mismatch for {path}: declared={declared}, computed={computed}"
        )
    payload["freeze_sha256"] = declared
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--master",
        type=Path,
        default=PROJECT_ROOT / "configs" / "webarena_p0_holdout_frozen.json",
    )
    args = parser.parse_args()
    master = verify_manifest(args.master)
    for site, relative_path in master["site_config_paths"].items():
        site_payload = verify_manifest(PROJECT_ROOT / relative_path)
        if site_payload["freeze_sha256"] != master["site_config_freeze_sha256"][site]:
            raise RuntimeError(f"master/site freeze mismatch for {site}")
    release = release_fingerprint(
        [PROJECT_ROOT / row["path"] for row in master["release"]["files"]],
        root=PROJECT_ROOT,
    )
    if release["sha256"] != master["release"]["sha256"]:
        raise RuntimeError(
            "Agent release drifted after holdout freeze: "
            f"expected={master['release']['sha256']}, actual={release['sha256']}"
        )
    print(
        json.dumps(
            {
                "status": "verified",
                "freeze_sha256": master["freeze_sha256"],
                "release_fingerprint_sha256": release["sha256"],
                "total_unique_tasks": master["total_unique_tasks"],
                "total_planned_episodes": master["total_planned_episodes"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
