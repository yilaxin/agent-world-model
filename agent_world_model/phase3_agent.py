"""End-to-end phase-three world-model Agent prototype."""

from __future__ import annotations

import re
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
        semantic_goal_priority: bool = False,
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
        self.semantic_goal_priority = semantic_goal_priority

    @staticmethod
    def _semantic_goal_match(
        goal: str,
        candidates: Sequence[CandidateAction],
    ) -> tuple[str, str] | None:
        """Return (action, target_name) of a candidate whose element name
        strongly matches a task keyword.

        This is the proposal-aligned "semantic goal priority" rule: when the
        goal explicitly names a visible element, exact-name matches are
        preferred over the imagined world-model reranking.  It is opt-in so
        the offline WebArena evaluation is unchanged and the before/after
        effect of the rule can be measured.
        """
        stopwords = {
            "open",
            "the",
            "app",
            "turn",
            "value",
            "settings",
            "android",
            "please",
            "to",
        }
        tokens = {
            token.lower()
            for token in re.findall(r"[A-Za-z\u4e00-\u9fff]+", goal or "")
            if len(token) >= 3 and token.lower() not in stopwords
        }
        if not tokens:
            return None
        for candidate in candidates:
            name = candidate.target_name or ""
            normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", name.lower())
            if not normalized:
                continue
            if candidate.action_type in {"click", "type", "fill"} and any(
                keyword in normalized for keyword in tokens
            ):
                return candidate.action, name
        return None

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
        semantic_action: str | None = None
        semantic_name: str = ""
        if self.semantic_goal_priority:
            match = self._semantic_goal_match(str(state.get("goal") or ""), candidates)
            if match is not None and match[0] != planning.action:
                semantic_action, semantic_name = match
        return AgentDecision(
            action=semantic_action if semantic_action is not None else planning.action,
            mode="semantic_goal_priority" if semantic_action is not None else planning.mode,
            should_execute=planning.should_execute,
            requires_reobservation=planning.requires_reobservation,
            confidence=1.0 if semantic_action is not None else planning.confidence,
            horizon=planning.horizon,
            encoded_state_id=encoded.encoding_id,
            fallback_action=fallback.action,
            candidates=[candidate.to_dict() for candidate in candidates],
            planning=(
                {
                    **planning.to_dict(),
                    "semantic_goal_priority": semantic_action is not None,
                    "semantic_target_name": semantic_name,
                }
                if semantic_action is not None
                else planning.to_dict()
            ),
        )
