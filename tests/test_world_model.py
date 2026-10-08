from __future__ import annotations

import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec("torch"), "PyTorch is not installed")
class WorldModelTests(unittest.TestCase):
    def test_forward_shapes_and_loss(self) -> None:
        import torch

        from agent_world_model.phase2_losses import world_model_loss
        from agent_world_model.world_model import (
            ActionConditionedWorldModel,
            WorldModelConfig,
        )

        config = WorldModelConfig(
            state_dim=16,
            action_dim=8,
            latent_dim=12,
            action_latent_dim=4,
            hidden_dim=20,
        )
        model = ActionConditionedWorldModel(config)
        batch = {
            "state": torch.randn(3, 16),
            "action": torch.randn(3, 8),
            "next_state": torch.randn(3, 16),
            "state_delta": torch.zeros(3, 5),
            "task_signal": torch.zeros(3, 2),
            "risk": torch.zeros(3, 4),
            "progress": torch.zeros(3),
            "reward": torch.zeros(3),
        }
        outputs = model(
            batch["state"], batch["action"], next_state=batch["next_state"]
        )
        self.assertEqual(outputs["predicted_next_state"].shape, (3, 16))
        self.assertEqual(outputs["risk_logits"].shape, (3, 4))
        total, components = world_model_loss(outputs, batch)
        self.assertTrue(torch.isfinite(total))
        self.assertEqual(set(components), {
            "reconstruction",
            "dynamics",
            "uncertainty",
            "state_delta",
            "task_signal",
            "risk",
            "progress",
            "reward",
        })

    def test_direct_residual_dynamics_preserves_state_plus_delta_contract(self) -> None:
        import torch

        from agent_world_model.world_model import (
            ActionConditionedWorldModel,
            WorldModelConfig,
        )

        config = WorldModelConfig(
            state_dim=16,
            action_dim=8,
            latent_dim=12,
            action_latent_dim=4,
            hidden_dim=20,
            direct_residual_dynamics=True,
        )
        model = ActionConditionedWorldModel(config)
        state = torch.randn(3, 16)
        action = torch.randn(3, 8)
        outputs = model(state, action)
        expected = state + model.direct_residual_head(torch.cat([state, action], dim=-1))
        self.assertTrue(torch.allclose(outputs["predicted_next_state"], expected))

    def test_legacy_config_has_no_direct_residual_head(self) -> None:
        import torch

        from agent_world_model.world_model import (
            ActionConditionedWorldModel,
            WorldModelConfig,
        )

        config = WorldModelConfig(
            state_dim=16,
            action_dim=8,
            latent_dim=12,
            action_latent_dim=4,
            hidden_dim=20,
        )
        model = ActionConditionedWorldModel(config)
        self.assertFalse(hasattr(model, "direct_residual_head"))
        state = torch.randn(2, 16)
        action = torch.randn(2, 8)
        outputs = model(state, action)
        self.assertEqual(outputs["predicted_next_state"].shape, (2, 16))


if __name__ == "__main__":
    unittest.main()
