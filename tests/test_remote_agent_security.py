from __future__ import annotations

import unittest

from agent_world_model.remote_agent import RemotePhase3Agent


class _Headers(dict):
    def get(self, key: str, default=None):
        return super().get(key, default)


class _Response:
    def __init__(self, body: bytes, content_length: str | None = None) -> None:
        self.body = body
        self.headers = _Headers()
        if content_length is not None:
            self.headers["Content-Length"] = content_length

    def read(self, amount: int = -1) -> bytes:
        return self.body if amount < 0 else self.body[:amount]


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

    def test_response_size_is_bounded(self) -> None:
        agent = RemotePhase3Agent("https://127.0.0.1")
        response = _Response(b"{}", str(agent.max_response_bytes + 1))
        with self.assertRaises(ValueError):
            agent._read_json_response(response)


if __name__ == "__main__":
    unittest.main()
