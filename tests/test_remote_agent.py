from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from agent_world_model.remote_agent import RemotePhase3Agent


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self) -> bytes:
        return json.dumps({"action": "scroll(0, 600)", "mode": "planned"}).encode()


class RemoteAgentTests(unittest.TestCase):
    def test_decide_serializes_state_and_returns_a_logger_compatible_decision(self) -> None:
        captured = {}

        def fake_urlopen(request, timeout):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return _Response()

        state = {"state_id": "s1", "axtree": {"text": "[1] link 'Home'"}}
        with patch("agent_world_model.remote_agent.urlopen", side_effect=fake_urlopen):
            decision = RemotePhase3Agent("http://127.0.0.1:8765", timeout_seconds=4.0).decide(
                state,
                ['click("1", "left")'],
            )

        self.assertEqual(decision.action, "scroll(0, 600)")
        self.assertEqual(decision.to_dict()["mode"], "planned")
        self.assertEqual(captured["body"]["state"]["state_id"], "s1")
        self.assertEqual(captured["timeout"], 4.0)


if __name__ == "__main__":
    unittest.main()
