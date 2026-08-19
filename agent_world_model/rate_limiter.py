"""Small dependency-free rate limiter for the phase-three inference service."""

from __future__ import annotations

import threading
import time


class RateLimiter:
    """Per-client token-bucket rate limiter (requests per second)."""

    def __init__(
        self,
        requests_per_second: float,
        *,
        max_clients: int = 4096,
        idle_seconds: float = 600.0,
    ) -> None:
        self.rate = max(0.0, float(requests_per_second))
        self.max_clients = max(1, int(max_clients))
        self.idle_seconds = max(1.0, float(idle_seconds))
        self.buckets: dict[str, tuple[float, float]] = {}
        self.lock = threading.Lock()

    def allow(self, client_ip: str) -> bool:
        if self.rate <= 0.0:
            return True
        now = time.monotonic()
        with self.lock:
            if client_ip not in self.buckets and len(self.buckets) >= self.max_clients:
                stale = [
                    key for key, (_, last) in self.buckets.items()
                    if now - last > self.idle_seconds
                ]
                for key in stale:
                    self.buckets.pop(key, None)
                if len(self.buckets) >= self.max_clients:
                    oldest = min(self.buckets, key=lambda key: self.buckets[key][1])
                    self.buckets.pop(oldest, None)
            tokens, last = self.buckets.get(client_ip, (1.0, now))
            tokens = min(1.0, tokens + (now - last) * self.rate)
            if tokens < 1.0:
                self.buckets[client_ip] = (tokens, now)
                return False
            self.buckets[client_ip] = (tokens - 1.0, now)
            return True
