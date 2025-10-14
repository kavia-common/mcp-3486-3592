from __future__ import annotations

import time
from threading import Lock


class TokenBucket:
    """Thread-safe token bucket for simple rate limiting.

    - rate_per_sec: tokens added per second
    - capacity: max tokens the bucket can hold

    try_consume(n) returns True if n tokens are available and consumes them; otherwise False.
    """

    def __init__(self, rate_per_sec: float, capacity: int) -> None:
        self.rate = float(rate_per_sec)
        self.capacity = int(max(1, capacity))
        self.tokens = float(self.capacity)
        self.updated_at = time.monotonic()
        self._lock = Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.updated_at
        if elapsed <= 0:
            return
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.updated_at = now

    def try_consume(self, n: int = 1) -> bool:
        with self._lock:
            self._refill()
            if self.tokens >= n:
                self.tokens -= n
                return True
            return False
