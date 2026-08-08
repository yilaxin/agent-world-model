from __future__ import annotations

import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec("torch"), "PyTorch is not installed")
class Phase2EnsembleTests(unittest.TestCase):
    def test_ensemble_shapes_and_disagreement(self) -> None:
        import torch

        from agent_world_model.phase2_ensemble import ActionConditionedWorldModelEnsemble
        from agent_world_model.world_model import ActionConditionedWorldModel, WorldModelConfig

        torch.manual_seed(5)
        config = WorldModelConfig(
            state_dim=16,
            action_dim=8,
            latent_dim=12,
            action_latent_dim=4,
            hidden_dim=20,
            dropout=0.0,
        )
        models = [ActionConditionedWorldModel(config) for _ in range(3)]
        ensemble = ActionConditionedWorldModelEnsemble(
            models,
            temperatures={
                "state_delta": [1.1] * 5,
                "task_signal": [0.9] * 2,
                "risk": [1.2] * 4,
            },
        )
        state = torch.randn(4, 16)
        action = torch.randn(4, 8)
        next_state = torch.randn(4, 16)
        output = ensemble(state, action, next_state=next_state)
        self.assertEqual(output["predicted_next_state"].shape, (4, 16))
        self.assertEqual(output["risk_logits"].shape, (4, 4))
        self.assertEqual(output["ensemble_disagreement"].shape, (4,))
        self.assertTrue(torch.all(output["ensemble_disagreement"] >= 0))


if __name__ == "__main__":
    unittest.main()
