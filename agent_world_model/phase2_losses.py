"""Multi-task objectives for the one-step world model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import torch
from torch import Tensor
from torch.nn import functional as F


def tensor_symlog(value: Tensor) -> Tensor:
    return torch.sign(value) * torch.log1p(value.abs())


def focal_binary_cross_entropy(
    logits: Tensor,
    targets: Tensor,
    *,
    gamma: float = 2.0,
    reduction: str = "mean",
) -> Tensor:
    raw = F.binary_cross_entropy_with_logits(logits, targets, reduction="none")
    probability = torch.sigmoid(logits)
    probability_true = probability * targets + (1.0 - probability) * (1.0 - targets)
    loss = (1.0 - probability_true).pow(gamma) * raw
    if reduction == "none":
        return loss
    if reduction == "mean":
        return loss.mean()
    raise ValueError(f"unsupported reduction: {reduction}")


def _weighted_mean(loss: Tensor, sample_weight: Tensor) -> Tensor:
    """Reduce a per-example loss without changing the uniform-training result."""

    while loss.ndim > 1:
        loss = loss.mean(dim=-1)
    weight = sample_weight.to(loss).reshape(-1)
    return (loss * weight).sum() / weight.sum().clamp_min(1e-6)


@dataclass(frozen=True)
class LossWeights:
    reconstruction: float = 1.0
    dynamics: float = 1.0
    uncertainty: float = 0.05
    state_delta: float = 0.75
    task_signal: float = 1.0
    risk: float = 1.0
    progress: float = 1.0
    reward: float = 0.50


def world_model_loss(
    outputs: Mapping[str, Tensor],
    batch: Mapping[str, Tensor],
    *,
    weights: LossWeights | None = None,
    focal_gamma: float = 2.0,
) -> tuple[Tensor, dict[str, Tensor]]:
    weights = weights or LossWeights()
    sample_weight = batch.get("sample_weight")
    if sample_weight is None:
        sample_weight = torch.ones(
            outputs["predicted_next_state"].shape[0],
            device=outputs["predicted_next_state"].device,
        )
    reconstruction = _weighted_mean(
        F.mse_loss(
            outputs["predicted_next_state"], batch["next_state"], reduction="none"
        ),
        sample_weight,
    )
    dynamics = _weighted_mean(
        F.mse_loss(
            outputs["next_latent_prior"],
            outputs["next_latent_posterior"].detach(),
            reduction="none",
        ),
        sample_weight,
    )
    latent_error = (
        outputs["next_latent_prior"]
        - outputs["next_latent_posterior"].detach()
    ).pow(2).mean(dim=-1)
    uncertainty = _weighted_mean(
        torch.exp(-outputs["log_variance"]) * latent_error
        + outputs["log_variance"],
        sample_weight,
    )
    state_delta = _weighted_mean(
        F.binary_cross_entropy_with_logits(
            outputs["state_delta_logits"], batch["state_delta"], reduction="none"
        ),
        sample_weight,
    )
    task_signal = _weighted_mean(
        focal_binary_cross_entropy(
            outputs["task_signal_logits"],
            batch["task_signal"],
            gamma=focal_gamma,
            reduction="none",
        ),
        sample_weight,
    )
    risk = _weighted_mean(
        focal_binary_cross_entropy(
            outputs["risk_logits"],
            batch["risk"],
            gamma=focal_gamma,
            reduction="none",
        ),
        sample_weight,
    )
    progress = _weighted_mean(
        F.smooth_l1_loss(
            outputs["progress_symlog"],
            tensor_symlog(batch["progress"]),
            reduction="none",
        ),
        sample_weight,
    )
    reward = _weighted_mean(
        F.smooth_l1_loss(
            outputs["reward_symlog"],
            tensor_symlog(batch["reward"]),
            reduction="none",
        ),
        sample_weight,
    )
    components = {
        "reconstruction": reconstruction,
        "dynamics": dynamics,
        "uncertainty": uncertainty,
        "state_delta": state_delta,
        "task_signal": task_signal,
        "risk": risk,
        "progress": progress,
        "reward": reward,
    }
    total = sum(
        components[name] * float(getattr(weights, name)) for name in components
    )
    return total, components
