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

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> dict[str, Tensor]:
        item = self.records[index]
        delta = item["state_delta"]
        signals = item["task_signals"]
        risks = item["risks"]
        return {
            "state": torch.tensor(item["state_vector"], dtype=torch.float32),
            "action": torch.tensor(item["action_vector"], dtype=torch.float32),
            "next_state": torch.tensor(
                item["next_state_vector"], dtype=torch.float32
            ),
            "state_delta": torch.tensor(
                [float(delta[name]) for name in STATE_DELTA_LABELS],
                dtype=torch.float32,
            ),
            "task_signal": torch.tensor(
                [float(signals[name]) for name in TASK_SIGNAL_LABELS],
                dtype=torch.float32,
            ),
            "risk": torch.tensor(
                [float(risks[name]) for name in RISK_LABELS],
                dtype=torch.float32,
            ),
            "progress": torch.tensor(float(signals["progress"]), dtype=torch.float32),
            "reward": torch.tensor(float(signals["reward"]), dtype=torch.float32),
        }


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def _move_batch(batch: Mapping[str, Tensor], device: torch.device) -> dict[str, Tensor]:
    return {name: value.to(device, non_blocking=True) for name, value in batch.items()}


def _symexp_tensor(value: Tensor) -> Tensor:
    return torch.sign(value) * torch.expm1(value.abs())


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
) -> dict[str, Any]:
    if not validation_records:
        raise ValueError("validation split cannot be empty")
    seed_everything(training_config.seed)
    device = resolve_device(training_config.device)
    use_amp = bool(training_config.amp and device.type == "cuda")
    model = ActionConditionedWorldModel(model_config).to(device)
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
        batches = 0
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
        validation_loss = float(validation["loss"]["total"])
        history.append(
            {
                "epoch": epoch,
                "train_loss": train_total / max(1, batches),
                "validation_loss": validation_loss,
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
        "train_examples": len(train_records),
        "validation_examples": len(validation_records),
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
