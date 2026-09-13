"""Trainable action-conditioned one-step latent world model (W0)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import torch
from torch import Tensor, nn
from torch.nn import functional as F


@dataclass(frozen=True)
class WorldModelConfig:
    state_dim: int = 512
    action_dim: int = 128
    latent_dim: int = 192
    action_latent_dim: int = 64
    hidden_dim: int = 256
    state_delta_dim: int = 5
    task_signal_dim: int = 2
    risk_dim: int = 4
    dropout: float = 0.10
    residual_dynamics: bool = False
    direct_residual_dynamics: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ResidualBlock(nn.Module):
    def __init__(self, dimensions: int, dropout: float) -> None:
        super().__init__()
        self.block = nn.Sequential(
            nn.LayerNorm(dimensions),
            nn.Linear(dimensions, dimensions * 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(dimensions * 2, dimensions),
        )

    def forward(self, value: Tensor) -> Tensor:
        return value + self.block(value)


class ActionConditionedWorldModel(nn.Module):
    """Predict ``z_(t+1)`` and immediate task signals from ``(z_t, a_t)``.

    A posterior encoder is used only as a training target.  Online inference uses
    the transition prior and therefore never peeks at the next observation.
    """

    def __init__(self, config: WorldModelConfig | None = None) -> None:
        super().__init__()
        self.config = config or WorldModelConfig()
        cfg = self.config
        self.state_encoder = nn.Sequential(
            nn.Linear(cfg.state_dim, cfg.hidden_dim),
            nn.LayerNorm(cfg.hidden_dim),
            nn.GELU(),
            ResidualBlock(cfg.hidden_dim, cfg.dropout),
            nn.Linear(cfg.hidden_dim, cfg.latent_dim),
        )
        self.next_state_posterior = nn.Sequential(
            nn.Linear(cfg.state_dim, cfg.hidden_dim),
            nn.LayerNorm(cfg.hidden_dim),
            nn.GELU(),
            nn.Linear(cfg.hidden_dim, cfg.latent_dim),
        )
        self.action_encoder = nn.Sequential(
            nn.Linear(cfg.action_dim, cfg.action_latent_dim),
            nn.LayerNorm(cfg.action_latent_dim),
            nn.GELU(),
        )
        self.transition = nn.GRUCell(
            cfg.latent_dim + cfg.action_latent_dim, cfg.hidden_dim
        )
        self.prior_head = nn.Linear(cfg.hidden_dim, cfg.latent_dim)
        self.state_decoder = nn.Sequential(
            nn.Linear(cfg.latent_dim, cfg.hidden_dim),
            nn.GELU(),
            nn.Linear(cfg.hidden_dim, cfg.state_dim),
        )
        if cfg.direct_residual_dynamics:
            # A direct state/action residual head matches the learned-delta
            # baseline while retaining the shared recurrent heads for planning.
            # It is built only when enabled so legacy checkpoints trained
            # without this head keep loading with strict state_dict semantics.
            self.direct_residual_head = nn.Sequential(
                nn.Linear(cfg.state_dim + cfg.action_dim, cfg.hidden_dim),
                nn.SiLU(),
                nn.Linear(cfg.hidden_dim, cfg.hidden_dim),
                nn.SiLU(),
                nn.Linear(cfg.hidden_dim, cfg.state_dim),
            )
        head_input = cfg.hidden_dim + cfg.latent_dim
        self.shared_head = nn.Sequential(
            nn.LayerNorm(head_input),
            nn.Linear(head_input, cfg.hidden_dim),
            nn.GELU(),
            nn.Dropout(cfg.dropout),
        )
        self.state_delta_head = nn.Linear(cfg.hidden_dim, cfg.state_delta_dim)
        self.task_signal_head = nn.Linear(cfg.hidden_dim, cfg.task_signal_dim)
        self.risk_head = nn.Linear(cfg.hidden_dim, cfg.risk_dim)
        self.progress_head = nn.Linear(cfg.hidden_dim, 1)
        self.reward_head = nn.Linear(cfg.hidden_dim, 1)
        self.log_variance_head = nn.Linear(cfg.hidden_dim, 1)

    def forward(
        self,
        state: Tensor,
        action: Tensor,
        *,
        next_state: Tensor | None = None,
        hidden: Tensor | None = None,
    ) -> dict[str, Tensor]:
        state_latent = self.state_encoder(state)
        action_latent = self.action_encoder(action)
        if hidden is None:
            hidden = torch.zeros(
                state.shape[0],
                self.config.hidden_dim,
                device=state.device,
                dtype=state.dtype,
            )
        next_hidden = self.transition(
            torch.cat([state_latent, action_latent], dim=-1), hidden
        )
        next_latent_prior = self.prior_head(next_hidden)
        predicted_next_state = self.state_decoder(next_latent_prior)
        if self.config.direct_residual_dynamics:
            predicted_next_state = state + self.direct_residual_head(
                torch.cat([state, action], dim=-1)
            )
        elif self.config.residual_dynamics:
            # Predict the one-step residual and add it to the observed state.
            predicted_next_state = state + predicted_next_state
        shared = self.shared_head(torch.cat([next_hidden, state_latent], dim=-1))
        result = {
            "hidden": next_hidden,
            "state_latent": state_latent,
            "next_latent_prior": next_latent_prior,
            "predicted_next_state": predicted_next_state,
            "state_delta_logits": self.state_delta_head(shared),
            "task_signal_logits": self.task_signal_head(shared),
            "risk_logits": self.risk_head(shared),
            "progress_symlog": self.progress_head(shared).squeeze(-1),
            "reward_symlog": self.reward_head(shared).squeeze(-1),
            "log_variance": self.log_variance_head(shared).squeeze(-1).clamp(-8, 6),
        }
        if next_state is not None:
            result["next_latent_posterior"] = self.next_state_posterior(next_state)
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
        """Score candidate actions for W0 online reranking without H>1 rollout."""

        if state.ndim == 1:
            state = state.unsqueeze(0)
        if candidate_actions.ndim != 2:
            raise ValueError("candidate_actions must have shape [candidates, action_dim]")
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
        score = (
            progress
            + reward
            + risks[:, 0]
            - risk_weight * risk
            - uncertainty_weight * uncertainty
        )
        return {
            "score": score,
            "progress": progress,
            "reward": reward,
            "risk_probabilities": risks,
            "task_signal_probabilities": task_signals,
            "uncertainty": uncertainty,
        }
