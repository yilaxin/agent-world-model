"""Small dependency-free rate limiter for the phase-three inference service."""

from __future__ import annotations

import threading
import time


class RateLimiter:
    """Per-client token-bucket rate limiter (requests per second)."""

    def __init__(self, requests_per_second: float) -> None:
        self.rate = max(0.0, float(requests_per_second))
        self.buckets: dict[str, tuple[float, float]] = {}
        self.lock = threading.Lock()

    def allow(self, client_ip: str) -> bool:
        if self.rate <= 0.0:
            return True
        now = time.monotonic()
        with self.lock:
            tokens, last = self.buckets.get(client_ip, (1.0, now))
            tokens = min(1.0, tokens + (now - last) * self.rate)
            if tokens < 1.0:
                self.buckets[client_ip] = (tokens, now)
                return False
            self.buckets[client_ip] = (tokens - 1.0, now)
            return True
