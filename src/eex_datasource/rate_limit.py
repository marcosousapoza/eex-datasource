"""Small, thread-safe request pacing helper."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable


class RateLimiter:
    """Space request starts by at least ``interval`` seconds."""

    def __init__(
        self,
        interval: float = 1.05,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if interval < 0:
            raise ValueError("interval must not be negative")
        self.interval = interval
        self._clock = clock
        self._sleep = sleep
        self._last_request: float | None = None
        self._lock = threading.Lock()

    def wait(self) -> None:
        """Block until the next request start is allowed by the shared clock."""
        with self._lock:
            now = self._clock()
            if self._last_request is not None:
                remaining = self.interval - (now - self._last_request)
                if remaining > 0:
                    self._sleep(remaining)
                    now = self._clock()
            self._last_request = now
