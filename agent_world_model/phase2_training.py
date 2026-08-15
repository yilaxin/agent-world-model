"""CUDA-aware training, evaluation, checkpointing and W0 inference."""

from __future__ import annotations

import json
import math
import random
from contextlib import nullcontext
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch
from torch import Tensor
from torch.nn import functional as F
from torch.utils.data import DataLoader, Dataset

from .counterfactual import build_counterfactual_pairs
from .phase2_losses import LossWeights, world_model_loss
from .phase2_metrics import (
    multilabel_metrics,
    regression_metrics,
)
from .phase2_schema import (
    RISK_LABELS,
    STATE_DELTA_LABELS,
    TASK_SIGNAL_LABELS,
    encode_action,
)
from .world_model import ActionConditionedWorldModel, WorldModelConfig


@dataclass(frozen=True)
class TrainingConfig:
    epochs: int = 50
    batch_size: int = 64
    learning_rate: float = 3e-4
    weight_decay: float = 1e-4
    gradient_clip: float = 1.0
    patience: int = 8
    num_workers: int = 0
    seed: int = 42
    device: str = "auto"
    amp: bool = True
    focal_gamma: float = 2.0
    pairwise_rank_weight: float = 0.35
    pairwise_batch_size: int = 32
    pairwise_minimum_utility_gap: float = 0.05


def resolve_device(preference: str = "auto") -> torch.device:
    if preference == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    device = torch.device(preference)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but torch.cuda.is_available() is false")
    return device


def seed_everything(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


class Phase2TensorDataset(Dataset[dict[str, Tensor]]):
    def __init__(self, records: Sequence[Mapping[str, Any]]) -> None:
        if not records:
            raise ValueError("phase-two dataset cannot be empty")
        self.records = list(records)
        self.tensors = {
            "state": torch.tensor(
                [item["state_vector"] for item in self.records], dtype=torch.float32
            ),
            "action": torch.tensor(
                [item["action_vector"] for item in self.records], dtype=torch.float32
            ),
            "next_state": torch.tensor(
                [item["next_state_vector"] for item in self.records], dtype=torch.float32
            ),
            "state_delta": torch.tensor(
                [
                    [float(item["state_delta"][name]) for name in STATE_DELTA_LABELS]
                    for item in self.records
                ],
                dtype=torch.float32,
            ),
            "task_signal": torch.tensor(
                [
                    [float(item["task_signals"][name]) for name in TASK_SIGNAL_LABELS]
                    for item in self.records
                ],
                dtype=torch.float32,
            ),
            "risk": torch.tensor(
                [
                    [float(item["risks"][name]) for name in RISK_LABELS]
                    for item in self.records
                ],
                dtype=torch.float32,
            ),
            "progress": torch.tensor(
                [float(item["task_signals"]["progress"]) for item in self.records],
                dtype=torch.float32,
            ),
            "reward": torch.tensor(
                [float(item["task_signals"]["reward"]) for item in self.records],
                dtype=torch.float32,
            ),
            "sample_weight": torch.tensor(
                [
                    float(item.get("metadata", {}).get("phase4_replay_weight", 1.0))
                    for item in self.records
                ],
                dtype=torch.float32,
            ),
        }

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> dict[str, Tensor]:
        return {name: value[index] for name, value in self.tensors.items()}


class CounterfactualPairTensorDataset(Dataset[dict[str, Tensor]]):
    """Same-state observed action pairs for direct ranking supervision."""

    def __init__(
        self,
        records: Sequence[Mapping[str, Any]],
        *,
        minimum_utility_gap: float = 0.05,
    ) -> None:
        self.pairs = build_counterfactual_pairs(
            records,
            minimum_utility_gap=minimum_utility_gap,
        )
        if self.pairs:
            self.tensors = {
                "left_state": torch.tensor(
                    [pair["left"]["state_vector"] for pair in self.pairs],
                    dtype=torch.float32,
                ),
                "left_action": torch.tensor(
                    [pair["left"]["action_vector"] for pair in self.pairs],
                    dtype=torch.float32,
                ),
                "right_state": torch.tensor(
                    [pair["right"]["state_vector"] for pair in self.pairs],
                    dtype=torch.float32,
                ),
                "right_action": torch.tensor(
                    [pair["right"]["action_vector"] for pair in self.pairs],
                    dtype=torch.float32,
                ),
                "target": torch.tensor(
                    [1.0 if float(pair["utility_gap"]) > 0 else -1.0 for pair in self.pairs],
                    dtype=torch.float32,
                ),
                "weight": torch.tensor(
                    [self._pair_weight(pair) for pair in self.pairs],
                    dtype=torch.float32,
                ),
            }

    @staticmethod
    def _pair_weight(pair: Mapping[str, Any]) -> float:
        left, right = pair["left"], pair["right"]
        gap = float(pair["utility_gap"])
        return min(4.0, max(0.25, abs(gap))) * 0.5 * (
            float(left.get("metadata", {}).get("phase4_replay_weight", 1.0))
            + float(right.get("metadata", {}).get("phase4_replay_weight", 1.0))
        )

    def __len__(self) -> int:
        return len(self.pairs)

    def __getitem__(self, index: int) -> dict[str, Tensor]:
        return {name: value[index] for name, value in self.tensors.items()}


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def _move_batch(batch: Mapping[str, Tensor], device: torch.device) -> dict[str, Tensor]:
    return {name: value.to(device, non_blocking=True) for name, value in batch.items()}


def _symexp_tensor(value: Tensor) -> Tensor:
    return torch.sign(value) * torch.expm1(value.abs())


def predicted_action_score(outputs: Mapping[str, Tensor]) -> Tensor:
    """Differentiable counterpart of the W0 candidate score."""

    risks = torch.sigmoid(outputs["risk_logits"])
    task_signals = torch.sigmoid(outputs["task_signal_logits"])
    progress = _symexp_tensor(outputs["progress_symlog"])
    reward = _symexp_tensor(outputs["reward_symlog"])
    risk = risks[:, 1:].mean(dim=-1) + task_signals[:, 0]
    uncertainty = F.softplus(outputs["log_variance"])
    return progress + reward + risks[:, 0] - risk - 0.25 * uncertainty


def pairwise_rank_loss(
    model: ActionConditionedWorldModel,
    batch: Mapping[str, Tensor],
) -> tuple[Tensor, Tensor]:
    left = model(batch["left_state"], batch["left_action"])
    right = model(batch["right_state"], batch["right_action"])
    score_delta = predicted_action_score(left) - predicted_action_score(right)
    raw = F.softplus(-batch["target"] * score_delta)
    loss = (raw * batch["weight"]).sum() / batch["weight"].sum().clamp_min(1e-6)
    accuracy = ((batch["target"] * score_delta) > 0).float().mean()
    return loss, accuracy


@torch.no_grad()
def evaluate_pairwise_model(
    model: ActionConditionedWorldModel,
    records: Sequence[Mapping[str, Any]],
    *,
    device: torch.device,
    minimum_utility_gap: float = 0.05,
    batch_size: int = 64,
) -> dict[str, float | int]:
    dataset = CounterfactualPairTensorDataset(
        records,
        minimum_utility_gap=minimum_utility_gap,
    )
    if not dataset:
        return {"informative_pair_count": 0, "log_loss": 0.0, "accuracy": 0.0}
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False)
    model.eval()
    losses: list[float] = []
    accuracies: list[float] = []
    counts: list[int] = []
    for raw_batch in loader:
        batch = _move_batch(raw_batch, device)
        loss, accuracy = pairwise_rank_loss(model, batch)
        count = int(batch["target"].shape[0])
        losses.append(float(loss) * count)
        accuracies.append(float(accuracy) * count)
        counts.append(count)
    total = sum(counts)
    return {
        "informative_pair_count": total,
        "log_loss": sum(losses) / total,
        "accuracy": sum(accuracies) / total,
    }


@torch.no_grad()
def evaluate_model(
    model: ActionConditionedWorldModel,
    loader: DataLoader[dict[str, Tensor]],
    *,
    device: torch.device,
    loss_weights: LossWeights | None = None,
    focal_gamma: float = 2.0,
) -> dict[str, Any]:
    model.eval()
    totals: dict[str, float] = {}
    batches = 0
    progress_true: list[float] = []
    progress_pred: list[float] = []
    reward_true: list[float] = []
    reward_pred: list[float] = []
    delta_true: list[list[float]] = []
    delta_pred: list[list[float]] = []
    signal_true: list[list[float]] = []
    signal_pred: list[list[float]] = []
    risk_true: list[list[float]] = []
    risk_pred: list[list[float]] = []
    latent_mse: list[float] = []
    latent_cosine: list[float] = []

    for raw_batch in loader:
        batch = _move_batch(raw_batch, device)
        outputs = model(
            batch["state"], batch["action"], next_state=batch["next_state"]
        )
        total, components = world_model_loss(
            outputs,
            batch,
            weights=loss_weights,
            focal_gamma=focal_gamma,
        )
        totals["total"] = totals.get("total", 0.0) + float(total)
        for name, value in components.items():
            totals[name] = totals.get(name, 0.0) + float(value)
        batches += 1

        progress_true.extend(batch["progress"].cpu().tolist())
        progress_pred.extend(_symexp_tensor(outputs["progress_symlog"]).cpu().tolist())
        reward_true.extend(batch["reward"].cpu().tolist())
        reward_pred.extend(_symexp_tensor(outputs["reward_symlog"]).cpu().tolist())
        delta_true.extend(batch["state_delta"].cpu().tolist())
        delta_pred.extend(torch.sigmoid(outputs["state_delta_logits"]).cpu().tolist())
        signal_true.extend(batch["task_signal"].cpu().tolist())
        signal_pred.extend(torch.sigmoid(outputs["task_signal_logits"]).cpu().tolist())
        risk_true.extend(batch["risk"].cpu().tolist())
        risk_pred.extend(torch.sigmoid(outputs["risk_logits"]).cpu().tolist())
        prior, posterior = (
            outputs["next_latent_prior"],
            outputs["next_latent_posterior"],
        )
        latent_mse.extend((prior - posterior).pow(2).mean(dim=-1).cpu().tolist())
        latent_cosine.extend(
            F.cosine_similarity(prior, posterior, dim=-1).cpu().tolist()
        )

    if not batches:
        raise ValueError("evaluation loader is empty")
    return {
        "loss": {name: value / batches for name, value in totals.items()},
        "progress": regression_metrics(progress_true, progress_pred),
        "reward": regression_metrics(reward_true, reward_pred),
        "state_delta": multilabel_metrics(
            delta_true, delta_pred, STATE_DELTA_LABELS
        ),
        "task_signal": multilabel_metrics(
            signal_true, signal_pred, TASK_SIGNAL_LABELS
        ),
        "risk": multilabel_metrics(risk_true, risk_pred, RISK_LABELS),
        "latent": {
            "mse": sum(latent_mse) / len(latent_mse),
            "cosine_similarity": sum(latent_cosine) / len(latent_cosine),
        },
        "example_count": len(progress_true),
    }


def train_world_model(
    train_records: Sequence[Mapping[str, Any]],
    validation_records: Sequence[Mapping[str, Any]],
    *,
    model_config: WorldModelConfig,
    training_config: TrainingConfig,
    checkpoint_path: str | Path,
    report_path: str | Path,
    loss_weights: LossWeights | None = None,
    initial_checkpoint_path: str | Path | None = None,
) -> dict[str, Any]:
    if not validation_records:
        raise ValueError("validation split cannot be empty")
    seed_everything(training_config.seed)
    device = resolve_device(training_config.device)
    use_amp = bool(training_config.amp and device.type == "cuda")
    model = ActionConditionedWorldModel(model_config).to(device)
    if initial_checkpoint_path is not None:
        initial = torch.load(
            Path(initial_checkpoint_path), map_location=device, weights_only=True
        )
        initial_config = WorldModelConfig(**initial["model_config"])
        if initial_config != model_config:
            raise ValueError("initial checkpoint model config does not match training config")
        model.load_state_dict(initial["model_state_dict"])
    train_loader = DataLoader(
        Phase2TensorDataset(train_records),
        batch_size=training_config.batch_size,
        shuffle=True,
        num_workers=training_config.num_workers,
        pin_memory=device.type == "cuda",
    )
    validation_loader = DataLoader(
        Phase2TensorDataset(validation_records),
        batch_size=training_config.batch_size,
        shuffle=False,
        num_workers=training_config.num_workers,
        pin_memory=device.type == "cuda",
    )
    train_pair_dataset = CounterfactualPairTensorDataset(
        train_records,
        minimum_utility_gap=training_config.pairwise_minimum_utility_gap,
    )
    validation_pair_count = len(
        CounterfactualPairTensorDataset(
            validation_records,
            minimum_utility_gap=training_config.pairwise_minimum_utility_gap,
        )
    )
    train_pair_loader = (
        DataLoader(
            train_pair_dataset,
            batch_size=training_config.pairwise_batch_size,
            shuffle=True,
            num_workers=training_config.num_workers,
            pin_memory=device.type == "cuda",
        )
        if train_pair_dataset and training_config.pairwise_rank_weight > 0
        else None
    )
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=training_config.learning_rate,
        weight_decay=training_config.weight_decay,
    )
    # torch.amp.GradScaler gained the device argument in newer PyTorch releases.
    # AutoDL's CUDA image currently ships PyTorch 2.1, where the equivalent API
    # still lives under torch.cuda.amp. Keep both paths so the same bundle runs
    # on the GPU server and on newer local environments.
    grad_scaler = getattr(torch.amp, "GradScaler", None)
    if grad_scaler is not None:
        scaler = grad_scaler("cuda", enabled=use_amp)
    else:
        scaler = torch.cuda.amp.GradScaler(enabled=use_amp)
    checkpoint = Path(checkpoint_path)
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    best_loss = math.inf
    stale_epochs = 0
    history: list[dict[str, Any]] = []

    for epoch in range(1, training_config.epochs + 1):
        model.train()
        train_total = 0.0
        train_pair_total = 0.0
        batches = 0
        pair_batches = 0
        pair_iterator = iter(train_pair_loader) if train_pair_loader is not None else None
        for raw_batch in train_loader:
            batch = _move_batch(raw_batch, device)
            optimizer.zero_grad(set_to_none=True)
            amp_context = (
                torch.autocast(device_type="cuda", dtype=torch.float16)
                if use_amp
                else nullcontext()
            )
            with amp_context:
                outputs = model(
                    batch["state"], batch["action"], next_state=batch["next_state"]
                )
                total, _ = world_model_loss(
                    outputs,
                    batch,
                    weights=loss_weights,
                    focal_gamma=training_config.focal_gamma,
                )
                if pair_iterator is not None:
                    try:
                        raw_pair_batch = next(pair_iterator)
                    except StopIteration:
                        pair_iterator = iter(train_pair_loader)
                        raw_pair_batch = next(pair_iterator)
                    pair_batch = _move_batch(raw_pair_batch, device)
                    rank_loss, _ = pairwise_rank_loss(model, pair_batch)
                    total = total + training_config.pairwise_rank_weight * rank_loss
                    train_pair_total += float(rank_loss.detach())
                    pair_batches += 1
            scaler.scale(total).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(
                model.parameters(), training_config.gradient_clip
            )
            scaler.step(optimizer)
            scaler.update()
            train_total += float(total.detach())
            batches += 1

        validation = evaluate_model(
            model,
            validation_loader,
            device=device,
            loss_weights=loss_weights,
            focal_gamma=training_config.focal_gamma,
        )
        pair_validation = evaluate_pairwise_model(
            model,
            validation_records,
            device=device,
            minimum_utility_gap=training_config.pairwise_minimum_utility_gap,
            batch_size=training_config.pairwise_batch_size,
        )
        validation["pairwise_ranking"] = pair_validation
        validation_loss = float(validation["loss"]["total"])
        if int(pair_validation["informative_pair_count"]) > 0:
            validation_loss += (
                training_config.pairwise_rank_weight
                * float(pair_validation["log_loss"])
            )
        history.append(
            {
                "epoch": epoch,
                "train_loss": train_total / max(1, batches),
                "train_pairwise_rank_loss": train_pair_total / max(1, pair_batches),
                "validation_loss": validation_loss,
                "validation_pairwise_accuracy": pair_validation["accuracy"],
            }
        )
        if validation_loss < best_loss - 1e-6:
            best_loss = validation_loss
            stale_epochs = 0
            torch.save(
                {
                    "schema_version": 1,
                    "model_config": model_config.to_dict(),
                    "training_config": asdict(training_config),
                    "model_state_dict": model.state_dict(),
                    "epoch": epoch,
                    "validation_loss": validation_loss,
                },
                checkpoint,
            )
        else:
            stale_epochs += 1
            if stale_epochs >= training_config.patience:
                break

    saved = torch.load(checkpoint, map_location=device, weights_only=True)
    model.load_state_dict(saved["model_state_dict"])
    final_validation = evaluate_model(
        model,
        validation_loader,
        device=device,
        loss_weights=loss_weights,
        focal_gamma=training_config.focal_gamma,
    )
    final_validation["pairwise_ranking"] = evaluate_pairwise_model(
        model,
        validation_records,
        device=device,
        minimum_utility_gap=training_config.pairwise_minimum_utility_gap,
        batch_size=training_config.pairwise_batch_size,
    )
    try:
        checkpoint_display = str(
            checkpoint.resolve().relative_to(Path.cwd().resolve())
        )
    except ValueError:
        checkpoint_display = str(checkpoint)
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "device": str(device),
        "cuda_available": torch.cuda.is_available(),
        "cuda_device_name": (
            torch.cuda.get_device_name(device) if device.type == "cuda" else None
        ),
        "amp_enabled": use_amp,
        "model_config": model_config.to_dict(),
        "training_config": asdict(training_config),
        "loss_weights": asdict(loss_weights or LossWeights()),
        "initial_checkpoint": str(initial_checkpoint_path) if initial_checkpoint_path else None,
        "train_examples": len(train_records),
        "validation_examples": len(validation_records),
        "train_counterfactual_pairs": len(train_pair_dataset),
        "validation_counterfactual_pairs": validation_pair_count,
        "best_epoch": int(saved["epoch"]),
        "history": history,
        "validation": final_validation,
        "checkpoint": checkpoint_display,
    }
    report_output = Path(report_path)
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


class WorldModelPredictor:
    """Load a checkpoint and expose single-step candidate ranking."""

    def __init__(self, checkpoint_path: str | Path, device: str = "auto") -> None:
        self.device = resolve_device(device)
        saved = torch.load(
            Path(checkpoint_path), map_location=self.device, weights_only=True
        )
        self.model = ActionConditionedWorldModel(
            WorldModelConfig(**saved["model_config"])
        ).to(self.device)
        self.model.load_state_dict(saved["model_state_dict"])
        self.model.eval()

    @torch.no_grad()
    def rank_actions(
        self, state_vector: Sequence[float], actions: Sequence[str]
    ) -> list[dict[str, Any]]:
        if not actions:
            return []
        action_vectors = [
            encode_action(action, self.model.config.action_dim)[0] for action in actions
        ]
        state = torch.tensor(state_vector, dtype=torch.float32, device=self.device)
        candidates = torch.tensor(
            action_vectors, dtype=torch.float32, device=self.device
        )
        result = self.model.score_candidates(state, candidates)
        rows = []
        for index, action in enumerate(actions):
            rows.append(
                {
                    "action": action,
                    "score": float(result["score"][index]),
                    "progress": float(result["progress"][index]),
                    "reward": float(result["reward"][index]),
                    "uncertainty": float(result["uncertainty"][index]),
                    "risk_probabilities": result["risk_probabilities"][index]
                    .cpu()
                    .tolist(),
                    "task_signal_probabilities": result[
                        "task_signal_probabilities"
                    ][index]
                    .cpu()
                    .tolist(),
                }
            )
        return sorted(rows, key=lambda row: row["score"], reverse=True)
