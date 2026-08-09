#!/usr/bin/env python3
"""Export a deterministic, high-risk trajectory review queue to CSV."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_world_model.human_review import (  # noqa: E402
    build_review_queue,
    write_review_csv,
)
from agent_world_model.trajectory import load_trajectory  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "human_review" / "phase2_review_queue.csv",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "data" / "reports" / "phase2_human_review_queue.json",
    )
    return parser.parse_args()


def _files(inputs: list[Path]) -> list[Path]:
    files: set[Path] = set()
    for item in inputs:
        path = item if item.is_absolute() else PROJECT_ROOT / item
        if path.is_dir():
            files.update(
                candidate
                for candidate in path.rglob("*.jsonl")
                if candidate.is_file()
            )
        elif path.is_file():
            files.add(path)
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
    rows = build_review_queue(records, limit=args.limit)
    output = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    write_review_csv(output, rows)
    reasons = Counter(
        reason for row in rows for reason in row["reason_codes"].split(";") if reason
    )
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_file_count": len(files),
        "source_transition_count": len(records),
        "queued_transition_count": len(rows),
        "queue_path": _display_path(output),
        "review_status_counts": dict(Counter(row["review_status"] for row in rows)),
        "reason_counts": dict(reasons),
        "instructions": [
            "Review the state/action/next-state evidence in each CSV row.",
            "Correct the seven label fields as needed, set reviewer, and change review_status to approved.",
            "Only approved rows are accepted by apply_human_review_labels.py.",
        ],
    }
    report_path = args.report if args.report.is_absolute() else PROJECT_ROOT / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
