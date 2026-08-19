"""Calibrated multi-seed ensemble for phase-two and phase-three inference."""

from __future__ import annotations

import json
import itertools
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch
from torch import Tensor, nn
from torch.nn import functional as F
from torch.utils.data import DataLoader

from .phase2_schema import encode_action
from .counterfactual import build_counterfactual_pairs
from .phase2_training import Phase2TensorDataset, predicted_action_score, resolve_device
from .world_model import ActionConditionedWorldModel, WorldModelConfig


_LOGIT_GROUPS = ("state_delta_logits", "task_signal_logits", "risk_logits")
_TEMPERATURE_KEYS = {
    "state_delta_logits": "state_delta",
    "task_signal_logits": "task_signal",
    "risk_logits": "risk",
}
_TARGET_KEYS = {
    "state_delta_logits": "state_delta",
    "task_signal_logits": "task_signal",
    "risk_logits": "risk",
}


def _inverse_softplus(value: Tensor) -> Tensor:
    value = value.clamp_min(1e-6)
    return value + torch.log(-torch.expm1(-value))


def _resolve_member_path(manifest_path: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    cwd_candidate = Path.cwd() / candidate
    if cwd_candidate.exists():
        return cwd_candidate
    for parent in (manifest_path.parent, *manifest_path.parents):
        nested = parent / candidate
        if nested.exists():
            return nested
    return cwd_candidate


def load_world_model(checkpoint_path: str | Path, device: torch.device) -> ActionConditionedWorldModel:
    saved = torch.load(Path(checkpoint_path), map_location=device, weights_only=True)
    model = ActionConditionedWorldModel(WorldModelConfig(**saved["model_config"])).to(device)
    model.load_state_dict(saved["model_state_dict"])
    model.eval()
    return model


class ActionConditionedWorldModelEnsemble(nn.Module):
    """Average calibrated predictions and expose model disagreement as uncertainty."""

    def __init__(
        self,
        models: Sequence[ActionConditionedWorldModel],
        *,
        temperatures: Mapping[str, Sequence[float]] | None = None,
        member_weights: Sequence[float] | None = None,
    ) -> None:
        super().__init__()
        if len(models) < 2:
            raise ValueError("an ensemble requires at least two world models")
        shape_keys = (
            "state_dim",
            "action_dim",
            "latent_dim",
            "action_latent_dim",
            "hidden_dim",
            "state_delta_dim",
            "task_signal_dim",
            "risk_dim",
        )
        configs = [model.config.to_dict() for model in models]
        reference_shape = {key: configs[0][key] for key in shape_keys}
        if any(
            {key: config[key] for key in shape_keys} != reference_shape
            for config in configs[1:]
        ):
            raise ValueError("all ensemble members must share one model shape")
        self.models = nn.ModuleList(models)
        self.config = models[0].config
        raw_weights = list(member_weights or [1.0] * len(models))
        if len(raw_weights) != len(models) or any(weight < 0 for weight in raw_weights):
            raise ValueError("member_weights must be non-negative and match models")
        weight_tensor = torch.tensor(raw_weights, dtype=torch.float32)
        if float(weight_tensor.sum()) <= 0:
            raise ValueError("member_weights must have a positive sum")
        self.register_buffer("member_weights", weight_tensor / weight_tensor.sum())
        temperatures = temperatures or {}
        for key, dimensions in (
            ("state_delta", self.config.state_delta_dim),
            ("task_signal", self.config.task_signal_dim),
            ("risk", self.config.risk_dim),
        ):
            values = list(temperatures.get(key, [1.0] * dimensions))
            if len(values) != dimensions or any(value <= 0 for value in values):
                raise ValueError(f"invalid temperature vector for {key}")
            self.register_buffer(f"temperature_{key}", torch.tensor(values, dtype=torch.float32))

    def _temperature(self, logit_key: str, logits: Tensor) -> Tensor:
        key = _TEMPERATURE_KEYS[logit_key]
        return getattr(self, f"temperature_{key}").to(logits)

    def _weighted_mean(self, values: Tensor) -> Tensor:
        shape = (len(self.models),) + (1,) * (values.ndim - 1)
        return (values * self.member_weights.to(values).view(shape)).sum(dim=0)

    def _weighted_variance(self, values: Tensor) -> Tensor:
        mean = self._weighted_mean(values)
        shape = (len(self.models),) + (1,) * (values.ndim - 1)
        return (
            (values - mean.unsqueeze(0)).pow(2)
            * self.member_weights.to(values).view(shape)
        ).sum(dim=0)

    def forward(
        self,
        state: Tensor,
        action: Tensor,
        *,
        next_state: Tensor | None = None,
        hidden: Tensor | None = None,
    ) -> dict[str, Tensor]:
        member_outputs = [
            model(state, action, next_state=next_state, hidden=hidden)
            for model in self.models
        ]
        mean_keys = (
            "hidden",
            "state_latent",
            "next_latent_prior",
            "predicted_next_state",
            "progress_symlog",
            "reward_symlog",
        )
        result = {
            key: self._weighted_mean(torch.stack([output[key] for output in member_outputs]))
            for key in mean_keys
        }
        if next_state is not None:
            result["next_latent_posterior"] = self._weighted_mean(
                torch.stack([output["next_latent_posterior"] for output in member_outputs])
            )

        probability_members: list[Tensor] = []
        for key in _LOGIT_GROUPS:
            logits = torch.stack([output[key] for output in member_outputs])
            calibrated = self._weighted_mean(logits) / self._temperature(key, logits)
            result[key] = calibrated
            probability_members.append(torch.sigmoid(logits))

        latent_members = torch.stack(
            [output["next_latent_prior"] for output in member_outputs]
        )
        latent_disagreement = self._weighted_variance(latent_members).mean(dim=-1)
        probability_disagreement = self._weighted_variance(
            torch.cat(probability_members, dim=-1)
        ).mean(dim=-1)
        numeric_members = torch.stack(
            [
                torch.stack(
                    [output["progress_symlog"], output["reward_symlog"]], dim=-1
                )
                for output in member_outputs
            ]
        )
        numeric_disagreement = self._weighted_variance(numeric_members).mean(dim=-1)
        disagreement = latent_disagreement + probability_disagreement + 0.25 * numeric_disagreement
        aleatoric = self._weighted_mean(
            torch.stack([F.softplus(output["log_variance"]) for output in member_outputs])
        )
        combined_uncertainty = aleatoric + disagreement
        result["log_variance"] = _inverse_softplus(combined_uncertainty)
        result["ensemble_disagreement"] = disagreement
        return result

    @torch.no_grad()
    def score_candidates(
        self,
        state: Tensor,
        candidate_actions: Tensor,
        *,
        risk_weight: float = 1.0,
        uncertainty_weight: float = 0.25,
    ) -> dict[str, Tensor]:
        if state.ndim == 1:
            state = state.unsqueeze(0)
        expanded_state = state.expand(candidate_actions.shape[0], -1)
        outputs = self(expanded_state, candidate_actions)
        risks = torch.sigmoid(outputs["risk_logits"])
        task_signals = torch.sigmoid(outputs["task_signal_logits"])
        progress = torch.sign(outputs["progress_symlog"]) * torch.expm1(
            outputs["progress_symlog"].abs()
        )
        reward = torch.sign(outputs["reward_symlog"]) * torch.expm1(
            outputs["reward_symlog"].abs()
        )
        risk = risks[:, 1:].mean(dim=-1) + task_signals[:, 0]
        uncertainty = F.softplus(outputs["log_variance"])
        score = progress + reward + risks[:, 0] - risk_weight * risk - uncertainty_weight * uncertainty
        return {
            "score": score,
            "progress": progress,
            "reward": reward,
            "risk_probabilities": risks,
            "task_signal_probabilities": task_signals,
            "uncertainty": uncertainty,
            "ensemble_disagreement": outputs["ensemble_disagreement"],
        }


@torch.no_grad()
def fit_ensemble_temperatures(
    models: Sequence[ActionConditionedWorldModel],
    loader: DataLoader[dict[str, Tensor]],
    *,
    device: torch.device,
    minimum: float = 0.50,
    maximum: float = 3.00,
    steps: int = 101,
) -> dict[str, list[float]]:
    """Fit per-label temperatures on validation data using a deterministic grid."""

    logits_by_group: dict[str, list[Tensor]] = {key: [] for key in _LOGIT_GROUPS}
    targets_by_group: dict[str, list[Tensor]] = {key: [] for key in _LOGIT_GROUPS}
    for raw_batch in loader:
        batch = {name: value.to(device) for name, value in raw_batch.items()}
        outputs = [model(batch["state"], batch["action"]) for model in models]
        for key in _LOGIT_GROUPS:
            logits_by_group[key].append(
                torch.stack([output[key] for output in outputs]).mean(dim=0).cpu()
            )
            targets_by_group[key].append(batch[_TARGET_KEYS[key]].cpu())

    grid = torch.linspace(minimum, maximum, steps=steps)
    fitted: dict[str, list[float]] = {}
    for logit_key in _LOGIT_GROUPS:
        logits = torch.cat(logits_by_group[logit_key], dim=0)
        targets = torch.cat(targets_by_group[logit_key], dim=0)
        values: list[float] = []
        for label_index in range(logits.shape[1]):
            label_logits = logits[:, label_index]
            label_targets = targets[:, label_index]
            losses = torch.stack(
                [
                    F.binary_cross_entropy_with_logits(
                        label_logits / temperature, label_targets
                    )
                    for temperature in grid
                ]
            )
            values.append(float(grid[int(torch.argmin(losses))]))
        fitted[_TEMPERATURE_KEYS[logit_key]] = values
    return fitted


@torch.no_grad()
def fit_ensemble_rank_weights(
    models: Sequence[ActionConditionedWorldModel],
    records: Sequence[Mapping[str, Any]],
    *,
    device: torch.device,
    minimum_utility_gap: float = 0.05,
    grid_steps: int = 10,
) -> list[float]:
    """Fit simplex-constrained member weights on validation pairwise log loss."""

    pairs = build_counterfactual_pairs(
        records,
        minimum_utility_gap=minimum_utility_gap,
    )
    member_count = len(models)
    if not pairs:
        return [1.0 / member_count] * member_count

    differences: list[list[float]] = []
    targets: list[float] = []
    for pair in pairs:
        rows = [pair["left"], pair["right"]]
        state = torch.tensor(
            [row["state_vector"] for row in rows],
            dtype=torch.float32,
            device=device,
        )
        action = torch.tensor(
            [row["action_vector"] for row in rows],
            dtype=torch.float32,
            device=device,
        )
        member_differences: list[float] = []
        for model in models:
            scores = predicted_action_score(model(state, action))
            member_differences.append(float(scores[0] - scores[1]))
        differences.append(member_differences)
        targets.append(1.0 if float(pair["utility_gap"]) > 0 else -1.0)

    diff_tensor = torch.tensor(differences, dtype=torch.float32)
    target_tensor = torch.tensor(targets, dtype=torch.float32)
    candidates = [
        values
        for values in itertools.product(range(grid_steps + 1), repeat=member_count)
        if sum(values) == grid_steps
    ]
    best_weights = [1.0 / member_count] * member_count
    best_key = (float("inf"), float("inf"))
    for values in candidates:
        weights = torch.tensor(values, dtype=torch.float32) / grid_steps
        score_delta = diff_tensor @ weights
        loss = float(F.softplus(-target_tensor * score_delta).mean())
        accuracy = float(((target_tensor * score_delta) > 0).float().mean())
        regularisation = float((weights - 1.0 / member_count).pow(2).mean())
        key = (loss + 0.01 * regularisation, -accuracy)
        if key < best_key:
            best_key = key
            best_weights = [float(value) for value in weights]
    return best_weights


class EnsembleWorldModelPredictor:
    """Load an ensemble manifest and expose the same planner-facing API as W0."""

    def __init__(self, manifest_path: str | Path, device: str = "auto") -> None:
        self.device = resolve_device(device)
        self.manifest_path = Path(manifest_path)
        self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        members = self.manifest.get("members", [])
        if len(members) < 2:
            raise ValueError("ensemble manifest must list at least two members")
        models = [
            load_world_model(
                _resolve_member_path(self.manifest_path, str(member["checkpoint"])),
                self.device,
            )
            for member in members
        ]
        self.model = ActionConditionedWorldModelEnsemble(
            models,
            temperatures=self.manifest.get("temperatures"),
            member_weights=self.manifest.get("member_weights"),
        ).to(self.device)
        self.model.eval()

    @torch.no_grad()
    def rank_actions(
        self, state_vector: Sequence[float], actions: Sequence[str]
    ) -> list[dict[str, Any]]:
        if not actions:
            return []
        state = torch.tensor(state_vector, dtype=torch.float32, device=self.device)
        candidates = torch.tensor(
            [encode_action(action, self.model.config.action_dim)[0] for action in actions],
            dtype=torch.float32,
            device=self.device,
        )
        result = self.model.score_candidates(state, candidates)
        rows: list[dict[str, Any]] = []
        for index, action in enumerate(actions):
            rows.append(
                {
                    "action": action,
                    "score": float(result["score"][index]),
                    "progress": float(result["progress"][index]),
                    "reward": float(result["reward"][index]),
                    "uncertainty": float(result["uncertainty"][index]),
                    "ensemble_disagreement": float(result["ensemble_disagreement"][index]),
                    "risk_probabilities": result["risk_probabilities"][index].cpu().tolist(),
                    "task_signal_probabilities": result["task_signal_probabilities"][index].cpu().tolist(),
                }
            )
        return sorted(rows, key=lambda row: row["score"], reverse=True)


def validation_loader(
    records: Sequence[Mapping[str, Any]], *, batch_size: int
) -> DataLoader[dict[str, Tensor]]:
    return DataLoader(
        Phase2TensorDataset(records),
        batch_size=batch_size,
        shuffle=False,
    )
