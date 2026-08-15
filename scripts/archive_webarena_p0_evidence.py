#!/usr/bin/env python3
"""Copy only final, analysis-referenced P0 trajectories into a clean archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--analysis",
        type=Path,
        default=ROOT / "data" / "reports" / "webarena_p0_2x2_analysis.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data" / "trajectories_webarena_p0_evidence",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    analysis = json.loads(args.analysis.read_text(encoding="utf-8"))
    rows = list(analysis["episode_evidence"])
    if len(rows) != int(analysis["judged_total_episodes_in_analysis"]):
        raise ValueError("episode evidence count does not match analysed episodes")

    archive_rows = []
    seen = set()
    for row in rows:
        key = (row["cell"], row["site"], int(row["task_id"]), int(row["seed"]))
        if key in seen:
            raise ValueError(f"duplicate evidence key: {key}")
        seen.add(key)
        source = Path(row["trajectory_path"])
        if not source.is_file():
            raise ValueError(f"missing trajectory: {source}")
        digest = sha256(source)
        if digest != row["trajectory_sha256"]:
            raise ValueError(f"trajectory SHA-256 mismatch: {source}")
        target = (
            args.output_dir
            / str(row["site"])
            / str(row["cell"])
            / f"task_{int(row['task_id']):03d}_seed{int(row['seed'])}_{digest[:12]}.jsonl"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if sha256(target) != digest:
            raise ValueError(f"copied trajectory SHA-256 mismatch: {target}")
        archive_rows.append({
            **{key: value for key, value in row.items() if key != "trajectory_path"},
            "path": str(target.relative_to(ROOT)),
        })

    manifest = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "analysis_path": str(args.analysis),
        "analysis_sha256": sha256(args.analysis),
        "episode_count": len(archive_rows),
        "freeze_sha256": analysis["freeze_sha256"],
        "release_fingerprint_sha256": analysis["release_fingerprint_sha256"],
        "episodes": archive_rows,
    }
    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "manifest": str(manifest_path),
        "episode_count": len(archive_rows),
        "manifest_sha256": sha256(manifest_path),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
