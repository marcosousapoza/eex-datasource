from __future__ import annotations

import random
import threading
import time
from collections.abc import Callable


class RateLimiter:
    """Thread-safe limiter spacing request starts using a monotonic clock."""

    def __init__(
        self,
        interval: float = 1.0,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.interval = interval
        self._clock = clock
        self._sleep = sleeper
        self._lock = threading.Lock()
        self._next_start = 0.0

    def wait(self) -> None:
        with self._lock:
            now = self._clock()
            delay = max(0.0, self._next_start - now)
            if delay:
                self._sleep(delay)
                now = self._clock()
            self._next_start = max(now, self._next_start) + self.interval


def jitter() -> float:
    return random.random()
