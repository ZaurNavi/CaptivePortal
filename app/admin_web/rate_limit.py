"""Bounded in-memory login failure limiter keyed by canonical source IP."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable


@dataclass(slots=True)
class _Tracker:
    failures: deque[float] = field(default_factory=deque)
    locked_until: float = 0.0
    active_attempts: int = 0


class AdminLoginRateLimiter:
    """Thread-safe rolling-window limiter with fail-closed map capacity."""

    def __init__(
        self,
        *,
        window_seconds: int,
        max_failures: int,
        lock_seconds: int,
        max_trackers: int,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._window_seconds = window_seconds
        self._max_failures = max_failures
        self._lock_seconds = lock_seconds
        self._max_trackers = max_trackers
        self._clock = clock
        self._trackers: dict[str, _Tracker] = {}
        self._lock = threading.RLock()

    def begin_attempt(self, source_ip: str) -> str:
        """Atomically reserve source capacity and return the admission result."""
        with self._lock:
            now = self._clock()
            self._cleanup_locked(now)
            tracker = self._trackers.get(source_ip)
            if tracker is None:
                if len(self._trackers) >= self._max_trackers:
                    return "capacity"
                self._trackers[source_ip] = _Tracker(active_attempts=1)
                return "allowed"
            self._trim_failures(tracker, now)
            if now < tracker.locked_until:
                return "locked"
            tracker.active_attempts += 1
            return "allowed"

    def finish_attempt(self, source_ip: str, outcome: str) -> None:
        """Complete one admitted attempt as failure, success, or neutral."""
        if outcome not in {"failure", "success", "neutral"}:
            raise ValueError("invalid login attempt outcome")
        with self._lock:
            now = self._clock()
            tracker = self._trackers.get(source_ip)
            if tracker is None or tracker.active_attempts <= 0:
                return
            tracker.active_attempts -= 1
            if outcome == "failure":
                self._trim_failures(tracker, now)
                tracker.failures.append(now)
                if len(tracker.failures) >= self._max_failures:
                    tracker.locked_until = max(
                        tracker.locked_until,
                        now + self._lock_seconds,
                    )
            elif outcome == "success":
                tracker.failures.clear()
                tracker.locked_until = 0.0
            if (
                tracker.active_attempts == 0
                and not tracker.failures
                and now >= tracker.locked_until
            ):
                self._trackers.pop(source_ip, None)

    def clear(self) -> None:
        with self._lock:
            self._trackers.clear()

    def size(self) -> int:
        with self._lock:
            self._cleanup_locked(self._clock())
            return len(self._trackers)

    def _trim_failures(self, tracker: _Tracker, now: float) -> None:
        boundary = now - self._window_seconds
        while tracker.failures and tracker.failures[0] <= boundary:
            tracker.failures.popleft()

    def _cleanup_locked(self, now: float) -> None:
        stale = []
        for source, tracker in self._trackers.items():
            self._trim_failures(tracker, now)
            if (
                tracker.active_attempts == 0
                and not tracker.failures
                and now >= tracker.locked_until
            ):
                stale.append(source)
        for source in stale:
            self._trackers.pop(source, None)
