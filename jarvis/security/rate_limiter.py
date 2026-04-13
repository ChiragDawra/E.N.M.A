"""Token-bucket rate limiting + circuit breaker (Vulnerability #5 cure)."""
from __future__ import annotations

import threading
import time
from collections import defaultdict

from jarvis.core.config import CONFIG


class RateLimiter:
    def __init__(self, limits: dict[str, tuple[int, int]] | None = None) -> None:
        self._limits = dict(limits or CONFIG.rate_limits)
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._failures: list[float] = []
        self._lock = threading.Lock()

    def allow(self, bucket: str) -> bool:
        if bucket not in self._limits:
            return True
        max_calls, window = self._limits[bucket]
        now = time.monotonic()
        with self._lock:
            pruned = [t for t in self._buckets[bucket] if now - t < window]
            if len(pruned) >= max_calls:
                self._buckets[bucket] = pruned
                return False
            pruned.append(now)
            self._buckets[bucket] = pruned
        return True

    def check_all(self, *buckets: str) -> bool:
        """Allow only if every bucket (and the 'total' bucket) permits."""
        buckets = tuple(buckets) + ("total",)
        # Reserve atomically: if any fails, we don't want to half-consume.
        now = time.monotonic()
        with self._lock:
            snapshots = {b: list(self._buckets[b]) for b in buckets}
            for b in buckets:
                if b not in self._limits:
                    continue
                max_calls, window = self._limits[b]
                pruned = [t for t in snapshots[b] if now - t < window]
                snapshots[b] = pruned
                if len(pruned) >= max_calls:
                    # commit pruning but deny
                    for bb in buckets:
                        self._buckets[bb] = snapshots[bb]
                    return False
            for b in buckets:
                if b in self._limits:
                    snapshots[b].append(now)
                self._buckets[b] = snapshots[b]
        return True

    def record_failure(self) -> None:
        with self._lock:
            now = time.monotonic()
            self._failures.append(now)
            self._failures = [t for t in self._failures if now - t < 60]

    def record_success(self) -> None:
        with self._lock:
            self._failures.clear()

    def circuit_open(self, threshold: int = 3) -> bool:
        with self._lock:
            now = time.monotonic()
            self._failures = [t for t in self._failures if now - t < 60]
            return len(self._failures) >= threshold


LIMITER = RateLimiter()
