from __future__ import annotations

import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec("torch"), "PyTorch is not installed")
class Phase3PlanningTests(unittest.TestCase):
    def setUp(self) -> None:
        import torch

        from agent_world_model.phase3_candidates import CandidateAction
        from agent_world_model.phase3_planning import ConfidenceAdaptivePlanner, PlanningConfig
        from agent_world_model.world_model import ActionConditionedWorldModel, WorldModelConfig

        torch.manual_seed(7)
        model = ActionConditionedWorldModel(
            WorldModelConfig(
                state_dim=32,
                action_dim=16,
                latent_dim=12,
                action_latent_dim=8,
                hidden_dim=24,
                dropout=0.0,
            )
        ).eval()
        predictor = type("Predictor", (), {"model": model, "device": torch.device("cpu")})()
        self.planner = ConfidenceAdaptivePlanner(
            predictor,
            PlanningConfig(max_horizon=3, beam_width=2),
        )
        self.state = [0.0] * 32
        self.candidates = [
            CandidateAction('click("11", "left")', "click", "a", "test", structure_score=1.0),
            CandidateAction("scroll(0, 600)", "scroll", "b", "test", structure_score=0.2),
            CandidateAction("go_back()", "go_back", "c", "test", structure_score=0.1),
        ]

    def test_rollout_produces_one_plan_per_first_action(self) -> None:
        plans = self.planner._rollout(
            self.state,
            self.candidates,
            horizon=3,
            world_influence=1.0,
        )
        self.assertEqual(len(plans), len(self.candidates))
        self.assertTrue(all(len(plan.action_sequence) == 3 for plan in plans))
        self.assertTrue(all(len(plan.rollout_steps) == 3 for plan in plans))

    def test_decision_is_explainable_and_horizon_bounded(self) -> None:
        decision = self.planner.plan(
            self.state,
            self.candidates,
            fallback_action="scroll(0, 600)",
        )
        self.assertIn(decision.mode, {"planned", "planned_short", "reobserve", "reactive_fallback"})
        self.assertIn(decision.horizon, {0, 1, 2, 3})
        self.assertTrue(decision.rationale)

    def test_empty_candidates_fall_back_without_imagination(self) -> None:
        decision = self.planner.plan(self.state, [], fallback_action="go_back()")
        self.assertEqual(decision.action, "go_back()")
        self.assertEqual(decision.mode, "reactive_fallback")
        self.assertEqual(decision.horizon, 0)


if __name__ == "__main__":
    unittest.main()
