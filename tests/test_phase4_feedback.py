from __future__ import annotations

import unittest

from agent_world_model.phase4_feedback import (
    FeedbackPriorityConfig,
    build_replay_view,
    feedback_components,
    replay_weights,
)


def row(example_id: str, role: str, utility: str) -> dict:
    success = utility == "good"
    return {
        "example_id": example_id,
        "task_signals": {
            "reward": float(success),
            "progress": float(success),
            "invalid_action": float(not success),
        },
        "risks": {
            "success": float(success),
            "stalled": float(not success),
            "goal_deviation": float(not success),
            "severe_failure": 0.0,
        },
        "metadata": {
            "counterfactual_pair_id": "pair-1",
            "counterfactual_role": role,
            "observed_in_environment": True,
            "initial_state_id": "state-1",
            "intervention_type": "wrong_action_type" if not success else "recorded",
        },
    }


def test_feedback_detects_rank_flip_and_regret() -> None:
    records = [row("good", "factual", "good"), row("bad", "counterfactual", "bad")]
    feedback = feedback_components(
        records,
        predicted_scores={"good": -1.0, "bad": 1.0},
        prediction_errors={"good": 0.1, "bad": 0.9},
    )
    assert feedback[0]["rank_flip"] == 1.0
    assert feedback[1]["regret"] > 0
    assert feedback[1]["stall"] == 1.0
    assert feedback[1]["struct_error"] == 1.0


def test_priority_replay_keeps_uniform_floor_and_equal_budget() -> None:
    feedback = [
        {"prediction_error": 0.1, "regret": 0, "rank_flip": 0, "stall": 0, "struct_error": 0},
        {"prediction_error": 0.9, "regret": 4, "rank_flip": 1, "stall": 1, "struct_error": 1},
    ]
    weights = replay_weights(
        feedback,
        strategy="priority",
        config=FeedbackPriorityConfig(uniform_fraction=0.25),
    )
    assert weights[0] > 0
    assert weights[1] > weights[0]
    assert unittest.TestCase().assertAlmostEqual(sum(weights) / len(weights), 1.0) is None


def test_replay_view_does_not_mutate_source() -> None:
    records = [row("good", "factual", "good"), row("bad", "counterfactual", "bad")]
    feedback = feedback_components(
        records,
        predicted_scores={"good": 1.0, "bad": -1.0},
        prediction_errors={"good": 0.1, "bad": 0.9},
    )
    view = build_replay_view(records, feedback, strategy="prediction_error")
    assert "phase4_replay_weight" not in records[0]["metadata"]
    assert view[0]["metadata"]["phase4_replay_weight"] > 0
