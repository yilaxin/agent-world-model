#!/usr/bin/env python3
"""Train the phase-two W0 model on CPU or CUDA from one JSON config."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_world_model.phase2_losses import LossWeights  # noqa: E402
from agent_world_model.phase2_training import (  # noqa: E402
    TrainingConfig,
    load_jsonl,
    train_world_model,
)
from agent_world_model.world_model import WorldModelConfig  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "configs" / "phase2_world_model.json",
    )
    parser.add_argument(
        "--allow-small-data",
        action="store_true",
        help="Permit an integration smoke run below the formal 500-transition P0 gate.",
    )
    parser.add_argument("--device", help="Override config: auto, cpu, cuda, cuda:0")
    return parser.parse_args()


def _project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> int:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    data_dir = _project_path(config["data"]["directory"])
    card = json.loads((data_dir / "dataset_card.json").read_text(encoding="utf-8"))
    if not card["quality_gates"]["p0_500_transitions"] and not args.allow_small_data:
        raise RuntimeError(
            "Formal training is blocked by the P0 data gate (<500 transitions). "
            "Collect more data or use --allow-small-data only for a smoke test."
        )
    train_records = load_jsonl(data_dir / "train.jsonl")
    validation_records = load_jsonl(data_dir / "validation.jsonl")
    training_data = dict(config["training"])
    if args.device:
        training_data["device"] = args.device
    report = train_world_model(
        train_records,
        validation_records,
        model_config=WorldModelConfig(**config["model"]),
        training_config=TrainingConfig(**training_data),
        loss_weights=LossWeights(**config.get("loss_weights", {})),
        checkpoint_path=_project_path(config["outputs"]["checkpoint"]),
        report_path=_project_path(config["outputs"]["training_report"]),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
