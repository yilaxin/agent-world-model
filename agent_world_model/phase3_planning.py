"""Confidence-adaptive finite-horizon planning over the phase-two world model."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Sequence

import torch
from torch import Tensor
from torch.nn import functional as F

from .phase2_schema import RISK_LABELS, STATE_DELTA_LABELS, TASK_SIGNAL_LABELS, encode_action
from .phase2_training import WorldModelPredictor
from .phase3_candidates import CandidateAction


@dataclass(frozen=True)
class PlanningConfig:
    min_horizon: int = 1
    max_horizon: int = 3
    beam_width: int = 4
    discount: float = 0.85
    long_term_weight: float = 0.80
    uncertainty_weight: float = 0.40
    structure_weight: float = 2.00
    progress_weight: float = 1.00
    reward_weight: float = 0.50
    target_available_weight: float = 0.20
    invalid_action_weight: float = 0.80
    stalled_weight: float = 0.60
    goal_deviation_weight: float = 1.00
    severe_failure_weight: float = 1.50
    high_confidence: float = 0.72
    medium_confidence: float = 0.52
    low_confidence: float = 0.30

    def __post_init__(self) -> None:
        if not 1 <= self.min_horizon <= self.max_horizon <= 3:
            raise ValueError("phase-three rollout horizons must satisfy 1 <= min <= max <= 3")
        if self.beam_width < 1:
            raise ValueError("beam_width must be positive")
        if not 0.0 < self.discount <= 1.0:
            raise ValueError("discount must be in (0, 1]")
        if not 0.0 <= self.low_confidence <= self.medium_confidence <= self.high_confidence <= 1.0:
            raise ValueError("confidence thresholds must be ordered within [0, 1]")


@dataclass(frozen=True)
class RankedPlan:
    action: str
    total_score: float
    short_term_score: float
    long_term_score: float
    uncertainty: float
    structure_score: float
    world_model_influence: float
    action_sequence: list[str]
    rollout_steps: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PlanDecision:
    action: str
    mode: str
    confidence: float
    horizon: int
    should_execute: bool
    requires_reobservation: bool
    rationale: str
    fallback_action: str
    ranked_plans: list[RankedPlan] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return payload


def _symexp(value: Tensor) -> Tensor:
    return torch.sign(value) * torch.expm1(value.abs())


class ConfidenceAdaptivePlanner:
    """Rank first actions with 1--3 step latent rollouts and safe fallback.

    Candidate continuation actions remain fixed during an imagined trajectory
    because W0 predicts a latent state vector, not a rendered AXTree.  After the
    first real action the Agent re-observes the page and generates a fresh set.
    """

    planner_name = "confidence_adaptive_beam_v1"

    def __init__(
        self,
        predictor: WorldModelPredictor,
        config: PlanningConfig | None = None,
    ) -> None:
        self.predictor = predictor
        self.model = predictor.model
        self.device = predictor.device
        self.config = config or PlanningConfig()

    @staticmethod
    def confidence_from_plan(best: RankedPlan, margin: float) -> float:
        uncertainty_confidence = math.exp(-max(0.0, best.uncertainty))
        margin_confidence = 1.0 - math.exp(-max(0.0, margin))
        return max(
            0.0,
            min(
                1.0,
                0.55 * uncertainty_confidence
                + 0.25 * best.structure_score
                + 0.20 * margin_confidence,
            ),
        )

    def _confidence_policy(self, confidence: float) -> tuple[str, int, float, bool, bool]:
        cfg = self.config
        if confidence >= cfg.high_confidence:
            return "planned", cfg.max_horizon, 1.0, True, False
        if confidence >= cfg.medium_confidence:
            return "planned_short", cfg.min_horizon, 0.55, True, False
        if confidence >= cfg.low_confidence:
            return "reobserve", cfg.min_horizon, 0.20, False, True
        return "reactive_fallback", 0, 0.0, True, False

    def plan(
        self,
        state_vector: Sequence[float],
        candidates: Sequence[CandidateAction],
        *,
        fallback_action: str,
    ) -> PlanDecision:
        if not candidates:
            return PlanDecision(
                action=fallback_action,
                mode="reactive_fallback",
                confidence=0.0,
                horizon=0,
                should_execute=True,
                requires_reobservation=False,
                rationale="No valid candidate survived schema and visibility checks.",
                fallback_action=fallback_action,
            )

        preliminary = self._rollout(state_vector, candidates, horizon=1, world_influence=1.0)
        margin = (
            preliminary[0].total_score - preliminary[1].total_score
            if len(preliminary) > 1
            else abs(preliminary[0].total_score)
        )
        confidence = self.confidence_from_plan(preliminary[0], margin)
        mode, horizon, influence, should_execute, requires_reobservation = self._confidence_policy(confidence)

        if mode == "reactive_fallback":
            return PlanDecision(
                action=fallback_action,
                mode=mode,
                confidence=confidence,
                horizon=0,
                should_execute=True,
                requires_reobservation=False,
                rationale="World-model confidence is below the fallback threshold.",
                fallback_action=fallback_action,
                ranked_plans=preliminary,
            )

        ranked = (
            preliminary
            if horizon == 1 and influence == 1.0
            else self._rollout(
                state_vector,
                candidates,
                horizon=horizon,
                world_influence=influence,
            )
        )
        chosen = fallback_action if requires_reobservation else ranked[0].action
        rationale = (
            "Low confidence: request a fresh observation before executing the reactive fallback."
            if requires_reobservation
            else (
                f"Selected after H={horizon} rollout using short/long outcome, uncertainty "
                "and task-element structural consistency."
            )
        )
        return PlanDecision(
            action=chosen,
            mode=mode,
            confidence=confidence,
            horizon=horizon,
            should_execute=should_execute,
            requires_reobservation=requires_reobservation,
            rationale=rationale,
            fallback_action=fallback_action,
            ranked_plans=ranked,
        )

    @torch.no_grad()
    def _rollout(
        self,
        state_vector: Sequence[float],
        candidates: Sequence[CandidateAction],
        *,
        horizon: int,
        world_influence: float,
    ) -> list[RankedPlan]:
        if not 1 <= horizon <= 3:
            raise ValueError("horizon must be in [1, 3]")
        cfg = self.config
        actions = [candidate.action for candidate in candidates]
        action_vectors = torch.tensor(
            [encode_action(action, self.model.config.action_dim)[0] for action in actions],
            dtype=torch.float32,
            device=self.device,
        )
        state = torch.tensor(state_vector, dtype=torch.float32, device=self.device)
        if state.numel() != self.model.config.state_dim:
            raise ValueError(
                f"state vector has {state.numel()} values; expected {self.model.config.state_dim}"
            )
        count = len(actions)
        outputs = self.model(state.unsqueeze(0).expand(count, -1), action_vectors)
        decoded = self._decode(outputs)
        short = decoded["short_step"]
        long_score = decoded["long_step"]
        uncertainty_sum = decoded["uncertainty"]
        uncertainty_weight = torch.ones_like(uncertainty_sum)
        alive = 1.0 - decoded["terminal"]
        first_indices = torch.arange(count, device=self.device)
        sequences: list[list[int]] = [[index] for index in range(count)]
        traces: list[list[dict[str, Any]]] = [
            [self._trace_row(outputs, decoded, index, 1)] for index in range(count)
        ]
        current_state = outputs["predicted_next_state"]
        hidden = outputs["hidden"]

        for depth in range(2, horizon + 1):
            beam_count = current_state.shape[0]
            expanded_state = current_state.repeat_interleave(count, dim=0)
            expanded_hidden = hidden.repeat_interleave(count, dim=0)
            expanded_actions = action_vectors.repeat(beam_count, 1)
            next_outputs = self.model(
                expanded_state,
                expanded_actions,
                hidden=expanded_hidden,
            )
            next_decoded = self._decode(next_outputs)
            expanded_alive = alive.repeat_interleave(count)
            short = short.repeat_interleave(count) + (
                (cfg.discount ** (depth - 1))
                * expanded_alive
                * next_decoded["short_step"]
            )
            long_score = torch.maximum(
                long_score.repeat_interleave(count),
                next_decoded["long_step"],
            )
            uncertainty_sum = uncertainty_sum.repeat_interleave(count) + (
                expanded_alive * next_decoded["uncertainty"]
            )
            uncertainty_weight = uncertainty_weight.repeat_interleave(count) + expanded_alive
            alive = expanded_alive * (1.0 - next_decoded["terminal"])
            first_indices = first_indices.repeat_interleave(count)

            expanded_sequences: list[list[int]] = []
            expanded_traces: list[list[dict[str, Any]]] = []
            for beam_index in range(beam_count):
                for action_index in range(count):
                    row_index = beam_index * count + action_index
                    expanded_sequences.append(sequences[beam_index] + [action_index])
                    expanded_traces.append(
                        traces[beam_index]
                        + [self._trace_row(next_outputs, next_decoded, row_index, depth)]
                    )
            sequences = expanded_sequences
            traces = expanded_traces
            current_state = next_outputs["predicted_next_state"]
            hidden = next_outputs["hidden"]

            proxy = short + cfg.long_term_weight * long_score - cfg.uncertainty_weight * (
                uncertainty_sum / uncertainty_weight.clamp_min(1e-6)
            )
            keep: list[int] = []
            for first_index in range(count):
                group = torch.nonzero(first_indices == first_index, as_tuple=False).flatten()
                width = min(cfg.beam_width, int(group.numel()))
                selected = group[torch.topk(proxy[group], k=width).indices]
                keep.extend(int(index) for index in selected.cpu().tolist())
            keep_tensor = torch.tensor(keep, dtype=torch.long, device=self.device)
            short = short[keep_tensor]
            long_score = long_score[keep_tensor]
            uncertainty_sum = uncertainty_sum[keep_tensor]
            uncertainty_weight = uncertainty_weight[keep_tensor]
            alive = alive[keep_tensor]
            first_indices = first_indices[keep_tensor]
            current_state = current_state[keep_tensor]
            hidden = hidden[keep_tensor]
            sequences = [sequences[index] for index in keep]
            traces = [traces[index] for index in keep]

        mean_uncertainty = uncertainty_sum / uncertainty_weight.clamp_min(1e-6)
        dynamic_score = short + cfg.long_term_weight * long_score - cfg.uncertainty_weight * mean_uncertainty
        structure = torch.tensor(
            [candidate.structure_score for candidate in candidates],
            dtype=torch.float32,
            device=self.device,
        )
        total = world_influence * dynamic_score + cfg.structure_weight * structure[first_indices]

        plans: list[RankedPlan] = []
        for first_index, candidate in enumerate(candidates):
            group = torch.nonzero(first_indices == first_index, as_tuple=False).flatten()
            chosen = int(group[torch.argmax(total[group])])
            sequence = [actions[index] for index in sequences[chosen]]
            plans.append(
                RankedPlan(
                    action=candidate.action,
                    total_score=float(total[chosen]),
                    short_term_score=float(short[chosen]),
                    long_term_score=float(long_score[chosen]),
                    uncertainty=float(mean_uncertainty[chosen]),
                    structure_score=float(candidate.structure_score),
                    world_model_influence=float(world_influence),
                    action_sequence=sequence,
                    rollout_steps=traces[chosen],
                )
            )
        return sorted(plans, key=lambda item: item.total_score, reverse=True)

    def _decode(self, outputs: dict[str, Tensor]) -> dict[str, Tensor]:
        cfg = self.config
        risks = torch.sigmoid(outputs["risk_logits"])
        signals = torch.sigmoid(outputs["task_signal_logits"])
        deltas = torch.sigmoid(outputs["state_delta_logits"])
        progress = _symexp(outputs["progress_symlog"])
        reward = _symexp(outputs["reward_symlog"])
        uncertainty = F.softplus(outputs["log_variance"])
        short_step = (
            cfg.progress_weight * progress
            + cfg.reward_weight * reward
            + cfg.target_available_weight * deltas[:, STATE_DELTA_LABELS.index("target_available")]
            - cfg.invalid_action_weight * signals[:, TASK_SIGNAL_LABELS.index("invalid_action")]
            - cfg.stalled_weight * risks[:, RISK_LABELS.index("stalled")]
        )
        long_step = (
            risks[:, RISK_LABELS.index("success")]
            + 0.20 * signals[:, TASK_SIGNAL_LABELS.index("terminal")]
            - cfg.stalled_weight * risks[:, RISK_LABELS.index("stalled")]
            - cfg.goal_deviation_weight * risks[:, RISK_LABELS.index("goal_deviation")]
            - cfg.severe_failure_weight * risks[:, RISK_LABELS.index("severe_failure")]
        )
        return {
            "state_deltas": deltas,
            "signals": signals,
            "risks": risks,
            "progress": progress,
            "reward": reward,
            "uncertainty": uncertainty,
            "short_step": short_step,
            "long_step": long_step,
            "terminal": signals[:, TASK_SIGNAL_LABELS.index("terminal")],
        }

    @staticmethod
    def _trace_row(
        outputs: dict[str, Tensor],
        decoded: dict[str, Tensor],
        index: int,
        depth: int,
    ) -> dict[str, Any]:
        return {
            "depth": depth,
            "progress": float(decoded["progress"][index]),
            "reward": float(decoded["reward"][index]),
            "uncertainty": float(decoded["uncertainty"][index]),
            "short_step": float(decoded["short_step"][index]),
            "long_step": float(decoded["long_step"][index]),
            "state_delta_probabilities": {
                name: float(decoded["state_deltas"][index, label_index])
                for label_index, name in enumerate(STATE_DELTA_LABELS)
            },
            "task_signal_probabilities": {
                name: float(decoded["signals"][index, label_index])
                for label_index, name in enumerate(TASK_SIGNAL_LABELS)
            },
            "risk_probabilities": {
                name: float(decoded["risks"][index, label_index])
                for label_index, name in enumerate(RISK_LABELS)
            },
        }
