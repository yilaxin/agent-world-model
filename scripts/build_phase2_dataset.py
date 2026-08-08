#!/usr/bin/env python3
"""Upgrade trajectory JSONL files into leakage-safe phase-two datasets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_world_model.phase2_dataset import (  # noqa: E402
    load_phase2_examples,
    write_dataset_bundle,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "inputs",
        nargs="*",
        type=Path,
        default=[PROJECT_ROOT / "data" / "trajectories"],
        help="JSONL files or directories (recursive).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "phase2",
    )
    parser.add_argument("--state-dim", type=int, default=512)
    parser.add_argument("--action-dim", type=int, default=128)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--require-p0",
        action="store_true",
        help="Return a failure status unless at least 500 transitions are present.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    examples, files = load_phase2_examples(
        args.inputs,
        state_dimensions=args.state_dim,
        action_dimensions=args.action_dim,
        seed=args.seed,
    )
    if not examples:
        raise RuntimeError("No trajectory transitions were found")
    card = write_dataset_bundle(args.output_dir, examples, source_files=files)
    print(json.dumps(card, ensure_ascii=False, indent=2))
    if args.require_p0 and not card["quality_gates"]["p0_500_transitions"]:
        print(
            "P0 gate failed: collect at least 500 valid transitions before formal training.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
