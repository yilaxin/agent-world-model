#!/usr/bin/env python3
"""Evaluate H=1--3 latent rollouts against observed contiguous trajectories."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import torch  # noqa: E402
from torch.nn import functional as F  # noqa: E402

from agent_world_model.multistep import (  # noqa: E402
    build_horizon_windows,
    multistep_coverage_summary,
)
from agent_world_model.phase2_ensemble import EnsembleWorldModelPredictor  # noqa: E402
from agent_world_model.phase2_schema import RISK_LABELS, TASK_SIGNAL_LABELS, encode_action  # noqa: E402
from agent_world_model.phase2_training import WorldModelPredictor, load_jsonl  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", type=Path, default=PROJECT_ROOT / "data" / "phase2_p1")
    parser.add_argument("--split", default="test")
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--ensemble-manifest", type=Path, default=PROJECT_ROOT / "artifacts" / "phase2" / "world_model_ensemble_p1.json")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--limit-per-horizon", type=int)
    parser.add_argument("--minimum-h2-windows", type=int, default=100)
    parser.add_argument("--minimum-h3-windows", type=int, default=100)
    parser.add_argument("--maximum-h3-to-h1-mse-ratio", type=float, default=4.0)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "data" / "reports" / "phase3_multistep_observed.json")
    return parser.parse_args()


def _mean(values: Sequence[float]) -> float:
    return float(statistics.fmean(values)) if values else 0.0


def _brier(probabilities: Sequence[float], labels: Sequence[float]) -> float:
    return _mean([(probability - label) ** 2 for probability, label in zip(probabilities, labels)])


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


@torch.no_grad()
def evaluate_windows(
    predictor: WorldModelPredictor | EnsembleWorldModelPredictor,
    windows: Mapping[int, Sequence[Sequence[Mapping[str, Any]]]],
    *,
    limit_per_horizon: int | None = None,
) -> dict[str, Any]:
    model = predictor.model
    device = predictor.device
    terminal_index = TASK_SIGNAL_LABELS.index("terminal")
    severe_index = RISK_LABELS.index("severe_failure")
    by_horizon: dict[str, Any] = {}
    for horizon in sorted(windows):
        rows = list(windows[horizon])
        if limit_per_horizon:
            rows = rows[:limit_per_horizon]
        mse: list[float] = []
        cosine: list[float] = []
        persistence_mse: list[float] = []
        terminal_probability: list[float] = []
        terminal_label: list[float] = []
        severe_probability: list[float] = []
        severe_label: list[float] = []
        progress_mae: list[float] = []
        for window in rows:
            state = torch.tensor(
                window[0]["state_vector"], dtype=torch.float32, device=device
            ).unsqueeze(0)
            initial_state = state
            hidden = None
            outputs = None
            for step in window:
                action_vector = encode_action(
                    str(step["action"]), model.config.action_dim
                )[0]
                action = torch.tensor(
                    action_vector, dtype=torch.float32, device=device
                ).unsqueeze(0)
                outputs = model(state, action, hidden=hidden)
                state = outputs["predicted_next_state"]
                hidden = outputs["hidden"]
            assert outputs is not None
            target = torch.tensor(
                window[-1]["next_state_vector"], dtype=torch.float32, device=device
            ).unsqueeze(0)
            mse.append(float(F.mse_loss(state, target)))
            cosine.append(float(F.cosine_similarity(state, target, dim=-1)[0]))
            persistence_mse.append(float(F.mse_loss(initial_state, target)))
            terminal_probability.append(
                float(torch.sigmoid(outputs["task_signal_logits"])[0, terminal_index])
            )
            terminal_label.append(float(window[-1]["task_signals"]["terminal"]))
            severe_probability.append(
                float(torch.sigmoid(outputs["risk_logits"])[0, severe_index])
            )
            severe_label.append(float(window[-1]["risks"]["severe_failure"]))
            predicted_progress = float(
                torch.sign(outputs["progress_symlog"])
                * torch.expm1(outputs["progress_symlog"].abs())
            )
            progress_mae.append(
                abs(predicted_progress - float(window[-1]["task_signals"]["progress"]))
            )
        latent_mse = _mean(mse)
        baseline_mse = _mean(persistence_mse)
        by_horizon[str(horizon)] = {
            "window_count": len(rows),
            "latent_mse": latent_mse,
            "latent_cosine_similarity": _mean(cosine),
            "persistence_baseline_mse": baseline_mse,
            "mse_improvement_over_persistence": (
                (baseline_mse - latent_mse) / baseline_mse if baseline_mse > 0 else 0.0
            ),
            "terminal_brier": _brier(terminal_probability, terminal_label),
            "severe_failure_brier": _brier(severe_probability, severe_label),
            "progress_mae": _mean(progress_mae),
        }
    return by_horizon


def main() -> int:
    args = parse_args()
    dataset_dir = args.dataset_dir if args.dataset_dir.is_absolute() else PROJECT_ROOT / args.dataset_dir
    records = load_jsonl(dataset_dir / f"{args.split}.jsonl")
    windows = build_horizon_windows(records, max_horizon=3)
    coverage = multistep_coverage_summary(windows)
    manifest = args.ensemble_manifest if args.ensemble_manifest.is_absolute() else PROJECT_ROOT / args.ensemble_manifest
    if manifest.exists() and args.checkpoint is None:
        predictor: WorldModelPredictor | EnsembleWorldModelPredictor = EnsembleWorldModelPredictor(manifest, device=args.device)
        model_source = _display_path(manifest)
    else:
        checkpoint = args.checkpoint or PROJECT_ROOT / "artifacts" / "phase2" / "world_model_p1_best.pt"
        checkpoint = checkpoint if checkpoint.is_absolute() else PROJECT_ROOT / checkpoint
        predictor = WorldModelPredictor(checkpoint, device=args.device)
        model_source = _display_path(checkpoint)
    metrics = evaluate_windows(
        predictor, windows, limit_per_horizon=args.limit_per_horizon
    )
    h1_mse = float(metrics.get("1", {}).get("latent_mse", math.inf))
    h3_mse = float(metrics.get("3", {}).get("latent_mse", math.inf))
    gates = {
        "h2_window_count": len(windows.get(2, [])) >= args.minimum_h2_windows,
        "h3_window_count": len(windows.get(3, [])) >= args.minimum_h3_windows,
        "long_horizon_terminal_coverage": coverage["quality_gates"]["long_horizon_terminal_ge_25"],
        "long_horizon_severe_failure_coverage": coverage["quality_gates"]["long_horizon_severe_failure_ge_10"],
        "h3_mse_ratio_bounded": bool(h1_mse > 0 and h3_mse / h1_mse <= args.maximum_h3_to_h1_mse_ratio),
    }
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "phase": 3,
        "evaluation": "observed_contiguous_horizon_1_to_3",
        "dataset": _display_path(dataset_dir / f"{args.split}.jsonl"),
        "model_source": model_source,
        "device": str(predictor.device),
        "coverage": coverage,
        "metrics": metrics,
        "acceptance": {"passed": all(gates.values()), "gates": gates},
        "interpretation_limits": [
            "Every evaluated sequence uses observed consecutive actions and observed final states.",
            "This measures rollout drift on logged behavior; it does not substitute for live WebArena task success.",
            "Horizon is capped at three steps to match the proposal and reduce compounding error.",
        ],
    }
    output = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["acceptance"]["passed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
