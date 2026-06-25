"""
core/rate_limit.py — Token bucket rate limiter.

Controls how many requests per second are made to any external API.
Thread-safe: multiple background threads share one limiter safely.
"""

import time
import threading


class TokenBucket:
    """
    Token bucket rate limiter.

    Allows bursts up to `capacity` tokens, then enforces a steady
    rate of `rate_per_sec` tokens per second.

    Example:
        limiter = TokenBucket(rate_per_sec=2)
        limiter.wait()          # blocks until a token is available
        response = requests.get(url)
    """

    def __init__(self, rate_per_sec: float, capacity: float = None):
        self.rate = float(rate_per_sec)
        self.capacity = float(capacity or rate_per_sec)
        self.tokens = self.capacity
        self.last = time.monotonic()
        self._lock = threading.Lock()

    def wait(self, tokens: float = 1.0) -> None:
        """Block until `tokens` tokens are available, then consume them."""
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self.last
                self.last = now
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return
            time.sleep(1.0 / self.rate)

    @property
    def available(self) -> float:
        """Current token count (non-consuming peek)."""
        with self._lock:
            elapsed = time.monotonic() - self.last
            return min(self.capacity, self.tokens + elapsed * self.rate)
