from __future__ import annotations

import unittest

from agent_world_model.androidworld_adapter import adapt_android_observation, map_agent_action


class AndroidWorldAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.observation = {
            "package": "com.example",
            "activity": ".MainActivity",
            "ui_tree": {
                "children": [
                    {"resource_id": "login", "text": "Log in", "clickable": True, "bounds": [10, 20, 110, 80]},
                    {"resource_id": "username", "text": "", "class": "android.widget.EditText", "editable": True, "bounds": [10, 100, 310, 160]},
                ]
            },
        }

    def test_observation_and_click_mapping(self) -> None:
        state, bounds = adapt_android_observation(self.observation, goal="Log in")
        self.assertEqual(state["platform"], "androidworld")
        self.assertEqual(len(bounds), 2)
        button = next(bid for bid, box in bounds.items() if box == (10, 20, 110, 80))
        self.assertEqual(map_agent_action(f'click("{button}", "left")', bounds), [{"action_type": "click", "x": 60, "y": 50}])

    def test_fill_and_navigation_mapping(self) -> None:
        _, bounds = adapt_android_observation(self.observation, goal="Enter alice")
        textbox = next(bid for bid, box in bounds.items() if box == (10, 100, 310, 160))
        actions = map_agent_action(f'fill("{textbox}", "alice")', bounds)
        self.assertEqual(actions[-1]["text"], "alice")
        self.assertTrue(actions[-1]["clear"])
        self.assertEqual(map_agent_action("go_back()", bounds)[0]["key"], "BACK")


if __name__ == "__main__":
    unittest.main()
