"""Small in-memory sliding-window rate limiter.

NOTE: per-process. If the API runs on several workers/instances, replace with a shared
store (e.g. Redis) - the interface is `allow(key)`.
"""

import threading
import time
from collections import defaultdict, deque
from typing import Callable, Deque, Dict


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float, clock: Callable[[], float] = time.monotonic):
        self.limit = limit
        self.window = window_seconds
        self._clock = clock
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Record a hit and return True if it is within the limit."""
        now = self._clock()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


HOUR = 3600
DAY = 86400

otp_per_phone = SlidingWindowLimiter(3, 15 * 60)
otp_per_ip = SlidingWindowLimiter(10, 15 * 60)
verify_per_ip = SlidingWindowLimiter(20, 15 * 60)
draft_per_victim = SlidingWindowLimiter(60, HOUR)
submit_per_victim = SlidingWindowLimiter(3, DAY)
submit_per_ip = SlidingWindowLimiter(10, DAY)
upload_per_victim = SlidingWindowLimiter(30, HOUR)
lookup_per_ip = SlidingWindowLimiter(120, HOUR)

ALL = (otp_per_phone, otp_per_ip, verify_per_ip, draft_per_victim, submit_per_victim,
       submit_per_ip, upload_per_victim, lookup_per_ip)


def reset_all() -> None:
    for limiter in ALL:
        limiter.reset()
