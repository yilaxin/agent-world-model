from __future__ import annotations

import unittest

from agent_world_model.reactive_agent import ReactiveAgent, parse_elements


def state(goal: str, axtree: str) -> dict:
    return {"goal": goal, "axtree": {"text": axtree}}


class ReactiveAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = ReactiveAgent()

    def test_element_parser(self) -> None:
        elements = parse_elements("[13] button 'Click Me!', clickable")
        self.assertEqual(elements[0].bid, "13")
        self.assertEqual(elements[0].role, "button")
        self.assertEqual(elements[0].name, "Click Me!")

    def test_click(self) -> None:
        decision = self.agent.decide(
            state("Click the Submit button.", "[7] button 'Submit', clickable")
        )
        self.assertEqual(decision.action_type, "click")
        self.assertEqual(decision.action, 'click("7", "left")')

    def test_input(self) -> None:
        decision = self.agent.decide(
            state(
                'Enter "phase-one-ok" into the Phase one text field.',
                "[21] textbox 'Phase one text'",
            )
        )
        self.assertEqual(decision.action_type, "input")
        self.assertEqual(decision.action, 'fill("21", "phase-one-ok")')

    def test_scroll_and_back(self) -> None:
        scroll = self.agent.decide(state("Scroll down.", "RootWebArea 'Demo'"))
        back = self.agent.decide(
            state("Go back to the previous page.", "RootWebArea 'Demo'")
        )
        self.assertEqual(scroll.action, "scroll(0, 600)")
        self.assertEqual(back.action, "go_back()")

    def test_direct_answer_uses_evaluator_action(self) -> None:
        decision = self.agent.decide(
            state("Answer the question.", "RootWebArea 'Demo'"),
            direct_answer="0",
        )
        self.assertEqual(decision.action_type, "answer")
        self.assertEqual(decision.action, 'send_msg_to_user("0")')


if __name__ == "__main__":
    unittest.main()
