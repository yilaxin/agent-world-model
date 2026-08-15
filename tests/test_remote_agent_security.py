from __future__ import annotations

import unittest

from agent_world_model.remote_agent import RemotePhase3Agent


class RemoteAgentSecurityTests(unittest.TestCase):
    def test_remote_endpoint_rejects_unsafe_forms(self) -> None:
        endpoints = [
        "ftp://127.0.0.1:8765",
        "http://user:password@127.0.0.1:8765",
        "http://127.0.0.1:8765/path",
        "http://127.0.0.1:8765?query=yes",
        "http://example.com:8765",
        ]
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                RemotePhase3Agent(endpoint)


    def test_remote_endpoint_accepts_private_tunnel_and_https(self) -> None:
        self.assertTrue(RemotePhase3Agent("http://127.0.0.1:18765").endpoint.endswith("18765"))
        self.assertTrue(RemotePhase3Agent("http://10.0.0.2:8765").endpoint.endswith("8765"))
        self.assertTrue(RemotePhase3Agent("https://agent.example.com").endpoint.startswith("https"))


    def test_bearer_header_is_optional_and_not_embedded_in_endpoint(self) -> None:
        agent = RemotePhase3Agent("http://127.0.0.1:18765", bearer_token="secret")
        self.assertEqual(agent._headers()["Authorization"], "Bearer secret")
        self.assertNotIn("secret", agent.endpoint)


if __name__ == "__main__":
    unittest.main()
