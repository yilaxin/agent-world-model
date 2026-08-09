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
    parser.add_argument(
        "--require-counterfactual-p0",
        action="store_true",
        help="Require 1,000 observed pairs and at least 200 informative test pairs.",
    )
    parser.add_argument(
        "--require-multistep-p1",
        action="store_true",
        help="Require held-out H=2/3 windows plus terminal and severe-failure coverage.",
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
    if args.require_counterfactual_p0:
        required = (
            "counterfactual_scale_1000",
            "counterfactual_test_informative_200",
            "counterfactual_tie_rate_le_20pct",
            "no_counterfactual_pair_leakage",
            "no_counterfactual_group_leakage",
        )
        failed = [name for name in required if not card["quality_gates"].get(name)]
        if failed:
            print(
                "Counterfactual P0 gate failed: " + ", ".join(failed),
                file=sys.stderr,
            )
            return 3
    if args.require_multistep_p1:
        required = (
            "multistep_h2_test_100",
            "multistep_h3_test_100",
            "multistep_terminal_test_25",
            "multistep_severe_failure_test_10",
        )
        failed = [name for name in required if not card["quality_gates"].get(name)]
        if failed:
            print(
                "Multistep P1 gate failed: " + ", ".join(failed),
                file=sys.stderr,
            )
            return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
