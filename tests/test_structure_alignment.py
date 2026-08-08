from __future__ import annotations

import importlib.util
import unittest

@unittest.skipUnless(importlib.util.find_spec("torch"), "PyTorch is not installed")
class StructureFeatureTests(unittest.TestCase):
    def test_exact_target_and_history_are_encoded(self) -> None:
        from agent_world_model.reactive_agent import ElementRef
        from agent_world_model.structure_alignment import FEATURE_NAMES, alignment_features

        element = ElementRef("7", "button", "Submit", "[7] button 'Submit'", depth=4)
        values, named = alignment_features(
            "Click the Submit button",
            element,
            "click",
            step_index=2,
            recent_actions=('click("7", "left")',),
        )
        self.assertEqual(len(values), len(FEATURE_NAMES))
        self.assertEqual(named["exact_name"], 1.0)
        self.assertEqual(named["role_compatible"], 1.0)
        self.assertEqual(named["history_repeat"], 1.0)


@unittest.skipUnless(importlib.util.find_spec("torch"), "PyTorch is not installed")
class StructureModelTests(unittest.TestCase):
    def test_model_shape(self) -> None:
        import torch

        from agent_world_model.structure_alignment import FEATURE_NAMES, StructureAlignmentModel

        output = StructureAlignmentModel()(torch.randn(5, len(FEATURE_NAMES)))
        self.assertEqual(output.shape, (5,))


if __name__ == "__main__":
    unittest.main()
