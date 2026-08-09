#!/usr/bin/env python3
"""Validate approved review rows and write human-labelled raw JSONL."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_world_model.human_review import (  # noqa: E402
    apply_approved_reviews,
    read_review_csv,
)
from agent_world_model.trajectory import load_trajectory  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "trajectories_human_reviewed" / "approved.jsonl",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "data" / "reports" / "phase2_human_review_apply.json",
    )
    return parser.parse_args()


def _files(inputs: list[Path]) -> list[Path]:
    files: set[Path] = set()
    for item in inputs:
        path = item if item.is_absolute() else PROJECT_ROOT / item
        files.update(path.rglob("*.jsonl") if path.is_dir() else [path])
    return sorted(files)


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def main() -> int:
    args = parse_args()
    files = _files(args.inputs)
    records = [record for path in files for record in load_trajectory(path)]
    review_path = args.reviews if args.reviews.is_absolute() else PROJECT_ROOT / args.reviews
    reviewed, audit = apply_approved_reviews(records, read_review_csv(review_path))
    output = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as file:
        for record in reviewed:
            file.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "review_csv": _display_path(review_path),
        "source_file_count": len(files),
        "source_transition_count": len(records),
        "output": _display_path(output),
        **audit,
    }
    report_path = args.report if args.report.is_absolute() else PROJECT_ROOT / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
