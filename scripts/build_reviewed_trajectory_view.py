#!/usr/bin/env python3
"""Build a same-size trajectory view with reviewed records replacing originals."""

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

from agent_world_model.phase2_schema import canonicalize_transition  # noqa: E402
from agent_world_model.trajectory import iter_trajectory  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--reviewed-jsonl", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


def _path(value: Path) -> Path:
    return value if value.is_absolute() else PROJECT_ROOT / value


def _files(inputs: list[Path]) -> list[Path]:
    files: set[Path] = set()
    for item in inputs:
        path = _path(item)
        if path.is_dir():
            files.update(candidate for candidate in path.rglob("*.jsonl") if candidate.is_file())
        elif path.is_file():
            files.add(path)
    return sorted(files)


def main() -> int:
    args = parse_args()
    reviewed_path = _path(args.reviewed_jsonl)
    reviewed: dict[str, dict] = {}
    for record in iter_trajectory(reviewed_path):
        example_id = canonicalize_transition(record).example_id
        if example_id in reviewed:
            raise ValueError(f"duplicate reviewed record: {example_id}")
        reviewed[example_id] = record

    files = _files(args.inputs)
    output = _path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    source_count = 0
    replaced_count = 0
    matched: set[str] = set()
    label_sources: Counter[str] = Counter()
    with output.open("w", encoding="utf-8") as destination:
        for path in files:
            for source in iter_trajectory(path):
                source_count += 1
                example_id = canonicalize_transition(source).example_id
                record = reviewed.get(example_id, source)
                if example_id in reviewed:
                    if example_id in matched:
                        raise ValueError(f"reviewed record matches multiple originals: {example_id}")
                    matched.add(example_id)
                    replaced_count += 1
                label_sources[str(canonicalize_transition(record).label_source)] += 1
                destination.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

    missing = set(reviewed) - matched
    if missing:
        raise ValueError(f"{len(missing)} reviewed records were not matched: {sorted(missing)[:5]}")
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_file_count": len(files),
        "source_transition_count": source_count,
        "reviewed_record_count": len(reviewed),
        "replaced_transition_count": replaced_count,
        "output_transition_count": source_count,
        "transition_count_preserved": source_count > 0,
        "output": str(output),
        "label_source_counts": dict(label_sources),
    }
    report_path = _path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
