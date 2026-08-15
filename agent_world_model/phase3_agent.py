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
        navigation_guard: bool = True,
    ) -> None:
        if checkpoint_path is None and ensemble_manifest is None:
            raise ValueError("provide checkpoint_path or ensemble_manifest")
        self.encoder = StateEncoderV1()
        self.navigation_guard = bool(navigation_guard)
        self.reactive = ReactiveAgent(navigation_guard=self.navigation_guard)
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
            navigation_guard=self.navigation_guard,
        )
        self.planner = ConfidenceAdaptivePlanner(self.predictor, planning_config)
        self.semantic_goal_priority = semantic_goal_priority

    @staticmethod
    def _semantic_goal_match(
        goal: str,
        candidates: Sequence[CandidateAction],
        recent_actions: Sequence[str] = (),
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
        ranked: list[tuple[float, CandidateAction]] = []
        for candidate in candidates:
            name = candidate.target_name or ""
            normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", name.lower())
            if not normalized:
                continue
            matched = {keyword for keyword in tokens if keyword in normalized}
            if candidate.action_type not in {"click", "type", "fill"} or not matched:
                continue
            if candidate.action in recent_actions[-6:]:
                continue
            score = 3.0 * len(matched) + float(candidate.structure_score)
            if name.lower() in goal.lower():
                score += 2.0
            if "trending" in goal.lower() and any(word in normalized for word in ("hot", "top")):
                score += 4.0
            if "newest" in goal.lower() and "new" in normalized:
                score += 4.0
            ranked.append((score, candidate))
        if not ranked:
            return None
        selected = max(ranked, key=lambda item: (item[0], item[1].action))[1]
        return selected.action, selected.target_name

    @staticmethod
    def _interaction_guard(
        goal: str,
        candidates: Sequence[CandidateAction],
        recent_actions: Sequence[str],
        current_url: str = "",
    ) -> tuple[str, str] | None:
        """Force observed two-step site interactions before model reranking.

        Filling a search field is non-terminal; on the next observation the
        now-enabled search button (or an element-scoped ENTER) must be used.
        This guard is action-schema based and never reads evaluator answers.
        """
        lowered = goal.lower()
        forum_match = re.search(
            r"\b(?:forum|subreddit)\s+[\"'](?:r/)?([^\"']+)[\"']",
            goal,
            re.IGNORECASE,
        )
        if forum_match:
            forum = forum_match.group(1).strip().lower()
            on_target_forum = f"/f/{forum}" in current_url.lower()
            if on_target_forum:
                subscribe = next(
                    (
                        candidate
                        for candidate in candidates
                        if candidate.action_type == "click"
                        and (candidate.target_name or "").strip().lower().startswith(
                            "subscribe"
                        )
                        and "rss" not in (candidate.target_name or "").lower()
                    ),
                    None,
                )
                already_subscribed = any(
                    (candidate.target_name or "").strip().lower().startswith(
                        "unsubscribe"
                    )
                    for candidate in candidates
                )
                if subscribe is not None and not already_subscribed:
                    return subscribe.action, subscribe.target_name
                if re.search(r"\b(?:thread|post|trending)\b", lowered):
                    thread = next(
                        (
                            candidate
                            for candidate in candidates
                            if candidate.action_type == "click"
                            and re.search(
                                r"\b(?:no|\d+)\s+comments?\b",
                                candidate.target_name or "",
                                re.IGNORECASE,
                            )
                        ),
                        None,
                    )
                    if thread is not None:
                        return thread.action, thread.target_name
                return None
            if recent_actions and recent_actions[-1].lstrip().startswith("fill("):
                submit = next(
                    (
                        candidate
                        for candidate in candidates
                        if candidate.source == "task_query"
                        and candidate.action.startswith("keyboard_press(")
                    ),
                    None,
                )
                if submit is not None:
                    return submit.action, submit.target_name
            exact_link = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate.action_type == "click"
                    and re.sub(
                        r"^(?:forum\s+|r/)",
                        "",
                        (candidate.target_name or "").strip().lower(),
                    )
                    == forum
                ),
                None,
            )
            if exact_link is not None:
                return exact_link.action, exact_link.target_name
            query_fill = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate.source == "task_query"
                    and candidate.action_type == "fill"
                ),
                None,
            )
            if query_fill is not None:
                return query_fill.action, query_fill.target_name

        if not recent_actions or not recent_actions[-1].lstrip().startswith("fill("):
            return None
        if not re.search(r"\b(?:search|find|look\s+up)\b", lowered):
            return None
        search_buttons = [
            candidate
            for candidate in candidates
            if candidate.action_type == "click"
            and "search" in (candidate.target_name or "").lower()
        ]
        if search_buttons:
            selected = max(search_buttons, key=lambda item: item.structure_score)
            return selected.action, selected.target_name
        enter = next(
            (
                candidate
                for candidate in candidates
                if candidate.action.startswith("keyboard_press(")
            ),
            None,
        )
        if enter is not None:
            return enter.action, enter.target_name
        return None

    @staticmethod
    def _protected_observed_fallback(
        fallback_action: str,
        candidates: Sequence[CandidateAction],
    ) -> CandidateAction | None:
        """Keep a high-precision observed fallback from being model-degraded.

        The offline world model can rank a generic click above an exact forum
        query even when the latter is directly grounded in the visible search
        control, or rank a profile link above an observed exact ``Upvote``
        control.  Such choices discard stronger public-state evidence from the
        shared reactive policy.  Protect only explicit task-query matches or
        exact semantic controls; leave every other ambiguity to the planner.
        """

        for candidate in candidates:
            components = candidate.metadata.get("structure_components", {})
            feature_values = components.get("feature_values", {})
            semantic_overlap = max(
                float(components.get("semantic_overlap", 0.0)),
                float(components.get("rule_semantic_overlap", 0.0)),
                float(feature_values.get("semantic_overlap", 0.0)),
            )
            is_task_query = (
                candidate.source == "task_query"
                and candidate.structure_score >= 0.96
                and float(components.get("task_query_match", 0.0)) >= 1.0
            )
            is_exact_semantic_control = (
                candidate.source == "reactive"
                and candidate.action_type in {"click", "fill", "type"}
                and candidate.structure_score >= 0.99
                and semantic_overlap >= 1.0
            )
            if (
                candidate.action == fallback_action
                and (is_task_query or is_exact_semantic_control)
            ):
                return candidate
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
        if fallback.action_type == "answer" and fallback.action.startswith(
            "send_msg_to_user("
        ):
            return AgentDecision(
                action=fallback.action,
                mode="observed_completion",
                should_execute=True,
                requires_reobservation=False,
                confidence=fallback.confidence,
                horizon=0,
                encoded_state_id=encoded.encoding_id,
                fallback_action=fallback.action,
                candidates=[],
                planning={
                    "reason": fallback.rationale,
                    "observed_completion": True,
                },
            )
        if self.navigation_guard and fallback.navigation_guard_applied:
            return AgentDecision(
                action=fallback.action,
                mode=(
                    "observed_navigation_complete"
                    if fallback.action_type == "answer"
                    else "observed_navigation_guard"
                ),
                should_execute=True,
                requires_reobservation=fallback.action_type != "answer",
                confidence=fallback.confidence,
                horizon=0 if fallback.action_type == "answer" else 1,
                encoded_state_id=encoded.encoding_id,
                fallback_action=fallback.action,
                candidates=[],
                planning={
                    "reason": "Frozen shared navigation guard selected the observed action.",
                    "navigation_guard_applied": True,
                },
            )
        candidates: list[CandidateAction] = self.generator.generate(state, recent_actions)
        planning: PlanDecision = self.planner.plan(
            encoded.vector,
            candidates,
            fallback_action=fallback.action,
        )
        protected = self._protected_observed_fallback(
            fallback.action,
            candidates,
        )
        if protected is not None and protected.action != planning.action:
            return AgentDecision(
                action=protected.action,
                mode="protected_observed_fallback",
                should_execute=True,
                requires_reobservation=False,
                confidence=fallback.confidence,
                horizon=0,
                encoded_state_id=encoded.encoding_id,
                fallback_action=fallback.action,
                candidates=[candidate.to_dict() for candidate in candidates],
                planning={
                    **planning.to_dict(),
                    "protected_observed_fallback": True,
                    "rejected_model_action": planning.action,
                    "protected_structure_score": protected.structure_score,
                    "reason": (
                        "Preserved a visible high-precision task-query action "
                        "from an unrelated model-ranked override."
                    ),
                },
            )
        semantic_action: str | None = None
        semantic_name: str = ""
        if self.semantic_goal_priority:
            goal = str(state.get("goal") or "")
            match = self._interaction_guard(
                goal,
                candidates,
                recent_actions,
                str(state.get("url") or ""),
            )
            if match is None:
                match = self._semantic_goal_match(goal, candidates, recent_actions)
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
