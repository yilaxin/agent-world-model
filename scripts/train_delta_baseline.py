#!/usr/bin/env python3
"""Train a small learned-delta baseline for multi-step latent dynamics.

The baseline maps (state, action) to the one-step state residual
(next_state - state).  During evaluation the trajectory is rolled forward by
accumulating predicted deltas.  It is deliberately simple: a single MLP trained
with MSE on the same phase-2 split as the world model, so it can serve as a
fair comparison for H=1..3 rollout drift.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import torch
from torch import Tensor, nn
from torch.nn import functional as F
from torch.utils.data import DataLoader, TensorDataset


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_world_model.phase2_training import load_jsonl  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", type=Path, default=PROJECT_ROOT / "data" / "phase2_p2")
    parser.add_argument("--state-dim", type=int, default=512)
    parser.add_argument("--action-dim", type=int, default=128)
    parser.add_argument("--hidden-dim", type=int, default=256)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--patience", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="auto")
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "artifacts" / "phase3" / "learned_delta_baseline.pt",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "data" / "reports" / "phase3_learned_delta_baseline.json",
    )
    return parser.parse_args()


class LearnedDeltaBaseline(nn.Module):
    def __init__(self, state_dim: int, action_dim: int, hidden_dim: int) -> None:
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(state_dim + action_dim, hidden_dim),
            nn.SiLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.SiLU(),
        )
        self.head = nn.Linear(hidden_dim, state_dim)

    def forward(self, state: Tensor, action: Tensor) -> Tensor:
        features = self.encoder(torch.cat([state, action], dim=-1))
        return self.head(features)


def _tensor_dataset(
    records: list[dict],
    state_dim: int,
    action_dim: int,
) -> TensorDataset:
    states: list[Tensor] = []
    actions: list[Tensor] = []
    deltas: list[Tensor] = []
    for record in records:
        state = torch.tensor(record["state_vector"], dtype=torch.float32)
        if len(state) != state_dim:
            raise ValueError(f"unexpected state vector dim: {len(state)}")
        action = torch.tensor(record["action_vector"], dtype=torch.float32)
        if len(action) != action_dim:
            raise ValueError(f"unexpected action vector dim: {len(action)}")
        next_state = torch.tensor(record["next_state_vector"], dtype=torch.float32)
        states.append(state)
        actions.append(action)
        deltas.append(next_state - state)
    return TensorDataset(torch.stack(states), torch.stack(actions), torch.stack(deltas))


def main() -> int:
    args = parse_args()
    torch.manual_seed(args.seed)
    device = torch.device(args.device if args.device != "auto" else ("cuda" if torch.cuda.is_available() else "cpu"))
    dataset_dir = args.dataset_dir if args.dataset_dir.is_absolute() else PROJECT_ROOT / args.dataset_dir
    train = load_jsonl(dataset_dir / "train.jsonl")
    validation = load_jsonl(dataset_dir / "validation.jsonl")
    train_data = _tensor_dataset(train, args.state_dim, args.action_dim)
    validation_data = _tensor_dataset(validation, args.state_dim, args.action_dim)
    train_loader = DataLoader(train_data, batch_size=args.batch_size, shuffle=True, drop_last=False)
    validation_loader = DataLoader(validation_data, batch_size=args.batch_size, shuffle=False)

    model = LearnedDeltaBaseline(args.state_dim, args.action_dim, args.hidden_dim).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=args.learning_rate,
        weight_decay=args.weight_decay,
    )
    best_validation = float("inf")
    best_state = None
    best_epoch = 0
    epochs_without_improvement = 0
    history: list[dict] = []

    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss = 0.0
        total_rows = 0
        for states, actions, deltas in train_loader:
            states, actions, deltas = (
                states.to(device),
                actions.to(device),
                deltas.to(device),
            )
            optimizer.zero_grad()
            predicted = model(states, actions)
            loss = F.mse_loss(predicted, deltas)
            loss.backward()
            optimizer.step()
            total_loss += float(loss) * len(states)
            total_rows += len(states)

        model.eval()
        validation_loss = 0.0
        validation_rows = 0
        with torch.no_grad():
            for states, actions, deltas in validation_loader:
                states, actions, deltas = (
                    states.to(device),
                    actions.to(device),
                    deltas.to(device),
                )
                predicted = model(states, actions)
                validation_loss += float(F.mse_loss(predicted, deltas)) * len(states)
                validation_rows += len(states)
        validation_loss /= max(1, validation_rows)
        history.append(
            {
                "epoch": epoch,
                "train_mse": total_loss / max(1, total_rows),
                "validation_mse": validation_loss,
            }
        )
        if validation_loss < best_validation * (1.0 - 1e-4):
            best_validation = validation_loss
            best_epoch = epoch
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= args.patience:
                break

    model.load_state_dict(best_state)
    output = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "schema_version": 1,
            "architecture": "learned_delta_mlp_v1",
            "state_dim": args.state_dim,
            "action_dim": args.action_dim,
            "hidden_dim": args.hidden_dim,
            "state_dict": model.state_dict(),
        },
        output,
    )
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "device": str(device),
        "dataset": str(dataset_dir),
        "train_examples": len(train),
        "validation_examples": len(validation),
        "best_epoch": best_epoch,
        "best_validation_mse": best_validation,
        "history": history,
        "checkpoint": str(output.relative_to(PROJECT_ROOT)),
        "interpretation_limits": [
            "Learned-delta is a baseline for rollout-drift comparison, not a WebArena online policy.",
            "It is trained only on observed one-step deltas and evaluated on observed trajectories.",
        ],
    }
    report_path = args.report if args.report.is_absolute() else PROJECT_ROOT / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
