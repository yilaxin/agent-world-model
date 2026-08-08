"""End-to-end phase-three world-model Agent prototype."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from .encoder import StateEncoderV1
from .phase2_ensemble import EnsembleWorldModelPredictor
from .phase2_training import WorldModelPredictor
from .phase3_candidates import AXTreeCandidateGenerator, CandidateAction
from .phase3_planning import ConfidenceAdaptivePlanner, PlanDecision, PlanningConfig
from .reactive_agent import ReactiveAgent
from .structure_alignment import StructureAlignmentPredictor
if TYPE_CHECKING:
    from .state import StateSnapshot


@dataclass(frozen=True)
class AgentDecision:
    """One complete, explainable phase-three decision."""

    action: str
    mode: str
    should_execute: bool
    requires_reobservation: bool
    confidence: float
    horizon: int
    encoded_state_id: str
    fallback_action: str
    candidates: list[dict[str, Any]]
    planning: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Phase3WorldModelAgent:
    """Generate, imagine, score and select browser actions.

    This prototype intentionally stops at the phase-three boundary: it does not
    update model parameters or fit a feedback/regret controller after execution.
    """

    agent_name = "world_model_agent_phase3_v1"

    def __init__(
        self,
        checkpoint_path: str | Path | None = None,
        *,
        ensemble_manifest: str | Path | None = None,
        alignment_checkpoint: str | Path | None = None,
        device: str = "auto",
        planning_config: PlanningConfig | None = None,
        max_candidates: int = 8,
    ) -> None:
        if checkpoint_path is None and ensemble_manifest is None:
            raise ValueError("provide checkpoint_path or ensemble_manifest")
        self.encoder = StateEncoderV1()
        self.reactive = ReactiveAgent()
        self.predictor = (
            EnsembleWorldModelPredictor(ensemble_manifest, device=device)
            if ensemble_manifest is not None
            else WorldModelPredictor(checkpoint_path, device=device)
        )
        alignment = (
            StructureAlignmentPredictor(
                alignment_checkpoint,
                device=str(self.predictor.device),
            )
            if alignment_checkpoint is not None
            else None
        )
        self.generator = AXTreeCandidateGenerator(
            max_candidates=max_candidates,
            alignment_scorer=alignment,
        )
        self.planner = ConfidenceAdaptivePlanner(self.predictor, planning_config)

    def decide(
        self,
        state: StateSnapshot | Mapping[str, Any],
        recent_actions: Sequence[str] = (),
        *,
        direct_answer: str | None = None,
    ) -> AgentDecision:
        if direct_answer is not None:
            fallback = self.reactive.decide(
                state,
                recent_actions,
                direct_answer=direct_answer,
            )
            return AgentDecision(
                action=fallback.action,
                mode="direct_answer",
                should_execute=True,
                requires_reobservation=False,
                confidence=1.0,
                horizon=0,
                encoded_state_id="not_encoded",
                fallback_action=fallback.action,
                candidates=[],
                planning={"reason": "Evaluator-smoke direct answer bypasses planning."},
            )
        encoded = self.encoder.encode(state, recent_actions)
        fallback = self.reactive.decide(state, recent_actions)
        candidates: list[CandidateAction] = self.generator.generate(state, recent_actions)
        planning: PlanDecision = self.planner.plan(
            encoded.vector,
            candidates,
            fallback_action=fallback.action,
        )
        return AgentDecision(
            action=planning.action,
            mode=planning.mode,
            should_execute=planning.should_execute,
            requires_reobservation=planning.requires_reobservation,
            confidence=planning.confidence,
            horizon=planning.horizon,
            encoded_state_id=encoded.encoding_id,
            fallback_action=fallback.action,
            candidates=[candidate.to_dict() for candidate in candidates],
            planning=planning.to_dict(),
        )
