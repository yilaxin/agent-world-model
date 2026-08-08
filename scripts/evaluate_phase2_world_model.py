#!/usr/bin/env python3
"""Evaluate a saved W0 checkpoint, including calibration and acceptance gates."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import torch  # noqa: E402
from torch.utils.data import DataLoader  # noqa: E402

from agent_world_model.phase2_metrics import evaluate_thresholds  # noqa: E402
from agent_world_model.phase2_training import (  # noqa: E402
    Phase2TensorDataset,
    evaluate_model,
    load_jsonl,
    resolve_device,
)
from agent_world_model.world_model import (  # noqa: E402
    ActionConditionedWorldModel,
    WorldModelConfig,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "configs" / "phase2_world_model.json",
    )
    parser.add_argument("--split", choices=("validation", "test"), default="test")
    parser.add_argument("--device", default="auto")
    return parser.parse_args()


def _project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> int:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    device = resolve_device(args.device)
    checkpoint_path = _project_path(config["outputs"]["checkpoint"])
    saved = torch.load(checkpoint_path, map_location=device, weights_only=True)
    model = ActionConditionedWorldModel(
        WorldModelConfig(**saved["model_config"])
    ).to(device)
    model.load_state_dict(saved["model_state_dict"])
    records = load_jsonl(
        _project_path(config["data"]["directory"]) / f"{args.split}.jsonl"
    )
    metrics = evaluate_model(
        model,
        DataLoader(
            Phase2TensorDataset(records),
            batch_size=int(config["training"]["batch_size"]),
            shuffle=False,
        ),
        device=device,
    )
    acceptance = evaluate_thresholds(metrics, config["acceptance_thresholds"])
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "split": args.split,
        "device": str(device),
        "metrics": metrics,
        "acceptance": acceptance,
    }
    output = _project_path(
        str(config["outputs"]["evaluation_report"]).format(split=args.split)
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if acceptance["passed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
