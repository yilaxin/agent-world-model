from __future__ import annotations

import unittest
from dataclasses import dataclass, field

from agent_world_model.androidworld_adapter import adapt_android_observation, adapt_androidworld_state, map_agent_action


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
        self.assertTrue(actions[-1]["clear_text"])
        self.assertEqual(map_agent_action("go_back()", bounds), [{"action_type": "navigate_back"}])
        self.assertEqual(map_agent_action('press("ENTER")', bounds), [{"action_type": "keyboard_enter"}])
        self.assertEqual(
            map_agent_action('press("field", "ENTER")', bounds),
            [{"action_type": "keyboard_enter"}],
        )

    def test_official_state_shape_and_action_schema(self) -> None:
        @dataclass
        class Box:
            x_min: int = 5
            x_max: int = 105
            y_min: int = 15
            y_max: int = 65

        @dataclass
        class Element:
            text: str = "Continue"
            content_description: str | None = None
            class_name: str = "android.widget.Button"
            bbox_pixels: Box = field(default_factory=Box)
            is_editable: bool = False
            is_clickable: bool = True
            resource_id: str = "continue"
            resource_name: str | None = None
            package_name: str = "com.example"

        @dataclass
        class Pixels:
            shape: tuple[int, int, int] = (2400, 1080, 3)

        @dataclass
        class State:
            ui_elements: list[Element]
            pixels: Pixels = field(default_factory=Pixels)

        adapted, bounds = adapt_androidworld_state(State([Element()]), goal="Continue", activity=".Main")
        self.assertEqual(adapted["url"], "android://com.example/Main")
        bid = next(iter(bounds))
        self.assertEqual(map_agent_action(f'click("{bid}")', bounds), [{"action_type": "click", "x": 55, "y": 40}])
        with self.assertRaisesRegex(ValueError, "unsupported AndroidWorld key"):
            map_agent_action('press("ESC")', bounds)

    def test_mapped_actions_validate_with_optional_official_runtime(self) -> None:
        try:
            from android_world.env.json_action import JSONAction
        except ImportError:
            self.skipTest("official android_world runtime is not installed")
        _, bounds = adapt_android_observation(self.observation, goal="Validate schema")
        button = next(bid for bid, box in bounds.items() if box == (10, 20, 110, 80))
        textbox = next(bid for bid, box in bounds.items() if box == (10, 100, 310, 160))
        actions = [
            f'click("{button}")',
            f'fill("{textbox}", "alice")',
            "go_back()",
            'press("HOME")',
            "scroll(0, 600)",
            "noop()",
        ]
        for action in actions:
            for mapped in map_agent_action(action, bounds):
                JSONAction(**mapped)


if __name__ == "__main__":
    unittest.main()
