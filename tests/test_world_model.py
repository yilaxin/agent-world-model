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


if __name__ == "__main__":
    unittest.main()
