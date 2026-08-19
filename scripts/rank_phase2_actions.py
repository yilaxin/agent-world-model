#!/usr/bin/env python3
"""Demonstrate W0 candidate action reranking from a phase-two sample."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_world_model.phase2_training import (  # noqa: E402
    WorldModelPredictor,
    load_jsonl,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=PROJECT_ROOT / "artifacts" / "phase2" / "world_model_best.pt",
    )
    parser.add_argument(
        "--sample",
        type=Path,
        default=PROJECT_ROOT / "data" / "phase2" / "test.jsonl",
    )
    parser.add_argument("--device", default="auto")
    parser.add_argument(
        "--action",
        action="append",
        default=[],
        help="Candidate BrowserGym action; pass multiple times.",
    )
    parser.add_argument(
        "--candidate-file",
        type=Path,
        help="Optional UTF-8 JSON array of candidate action strings.",
    )
    parser.add_argument("--output", type=Path, help="Optional JSON report path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sample = load_jsonl(args.sample)[0]
    candidates = list(args.action)
    if args.candidate_file:
        candidates.extend(json.loads(args.candidate_file.read_text(encoding="utf-8")))
    if not candidates:
        raise ValueError("Pass --action or --candidate-file")
    ranked = WorldModelPredictor(args.checkpoint, args.device).rank_actions(
        sample["state_vector"], candidates
    )
    report = {
        "task_id": sample["task_id"],
        "example_id": sample["example_id"],
        "source_action": sample["action"],
        "ranked_candidates": ranked,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
