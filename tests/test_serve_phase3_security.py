from __future__ import annotations

import unittest

from agent_world_model.rate_limiter import RateLimiter


class RateLimiterTests(unittest.TestCase):
    def test_disabled_rate_limit_always_allows(self) -> None:
        limiter = RateLimiter(0.0)
        self.assertTrue(limiter.allow("127.0.0.1"))
        self.assertTrue(limiter.allow("127.0.0.1"))

    def test_rate_limit_rejects_burst_after_tokens_exhausted(self) -> None:
        limiter = RateLimiter(10.0)  # 10 requests/second, 1 token initial
        self.assertTrue(limiter.allow("10.0.0.1"))
        self.assertFalse(limiter.allow("10.0.0.1"))

    def test_rate_limit_is_per_client(self) -> None:
        limiter = RateLimiter(1.0)
        self.assertTrue(limiter.allow("10.0.0.1"))
        self.assertFalse(limiter.allow("10.0.0.1"))
        self.assertTrue(limiter.allow("10.0.0.2"))


if __name__ == "__main__":
    unittest.main()
