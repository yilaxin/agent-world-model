from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(importlib.util.find_spec("torch"), "PyTorch is not installed")
class DeltaCheckpointLoadingTests(unittest.TestCase):
    def test_delta_checkpoint_loader_accepts_tensor_schema(self) -> None:
        import torch

        from scripts.evaluate_phase3_multistep import _load_delta_checkpoint

        payload = {
            "schema_version": 1,
            "architecture": "learned_delta_mlp_v1",
            "state_dim": 4,
            "action_dim": 3,
            "hidden_dim": 5,
            "state_dict": {"layer.weight": torch.zeros(5, 7)},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "delta.pt"
            torch.save(payload, path)
            loaded, state_dict = _load_delta_checkpoint(path, device=torch.device("cpu"))

        self.assertEqual(loaded["state_dim"], 4)
        self.assertEqual(tuple(state_dict["layer.weight"].shape), (5, 7))

    def test_delta_checkpoint_loader_rejects_missing_state_dict(self) -> None:
        import torch

        from scripts.evaluate_phase3_multistep import _load_delta_checkpoint

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.pt"
            torch.save({"state_dim": 4, "action_dim": 3, "hidden_dim": 5}, path)
            with self.assertRaises(ValueError):
                _load_delta_checkpoint(path, device=torch.device("cpu"))


if __name__ == "__main__":
    unittest.main()
