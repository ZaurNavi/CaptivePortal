from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class ActionGuardDecision:
    allowed: bool
    reason: str | None = None


class ActionGuard:
    """Thread-safe bounded cooldown and per-MAC hourly limiter."""

    def __init__(
        self,
        *,
        cooldown_seconds: float,
        max_actions_per_mac_per_hour: int,
        max_cache_entries: int = 10_000,
        clock=time.monotonic,
    ) -> None:
        self._cooldown_seconds = float(cooldown_seconds)
        self._hourly_limit = int(max_actions_per_mac_per_hour)
        self._max_cache_entries = int(max_cache_entries)
        self._clock = clock
        self._lock = threading.RLock()
        self._last_attempt: dict[str, float] = {}
        self._attempts: dict[str, deque[float]] = {}

    def check(
        self,
        *,
        client_mac: str,
        actions_this_scan: int,
        max_actions_per_scan: int,
        stopping: bool,
        inventory_complete: bool,
        budget_exhausted: bool,
        journal_available: bool,
    ) -> ActionGuardDecision:
        if stopping:
            return ActionGuardDecision(False, "shutdown_started")
        if not inventory_complete:
            return ActionGuardDecision(False, "incomplete_inventory")
        if budget_exhausted:
            return ActionGuardDecision(
                False,
                "scan_time_budget_exceeded",
            )
        if not journal_available:
            return ActionGuardDecision(False, "audit_unavailable")
        if actions_this_scan >= max_actions_per_scan:
            return ActionGuardDecision(False, "scan_action_limit")

        now = self._clock()
        with self._lock:
            self._prune_locked(now)
            last = self._last_attempt.get(client_mac)
            if (
                last is not None
                and now - last < self._cooldown_seconds
            ):
                return ActionGuardDecision(False, "cooldown_active")
            attempts = self._attempts.get(client_mac)
            if attempts is not None and len(attempts) >= self._hourly_limit:
                return ActionGuardDecision(
                    False,
                    "hourly_action_limit",
                )
        return ActionGuardDecision(True)

    def record_attempt(self, client_mac: str) -> None:
        """Record at the exact moment a POST is about to be sent."""
        now = self._clock()
        with self._lock:
            self._prune_locked(now)
            attempts = self._attempts.setdefault(
                client_mac,
                deque(),
            )
            attempts.append(now)
            self._last_attempt[client_mac] = now
            self._bound_locked()

    def _prune_locked(self, now: float) -> None:
        cutoff = now - 3600.0
        expired = []
        for mac, attempts in self._attempts.items():
            while attempts and attempts[0] <= cutoff:
                attempts.popleft()
            if not attempts:
                expired.append(mac)
        for mac in expired:
            self._attempts.pop(mac, None)
            last = self._last_attempt.get(mac)
            if last is not None and now - last >= self._cooldown_seconds:
                self._last_attempt.pop(mac, None)

    def _bound_locked(self) -> None:
        excess = len(self._attempts) - self._max_cache_entries
        if excess <= 0:
            return
        oldest = sorted(
            self._attempts,
            key=lambda mac: (
                self._attempts[mac][-1]
                if self._attempts[mac]
                else float("-inf")
            ),
        )
        for mac in oldest[:excess]:
            self._attempts.pop(mac, None)
            self._last_attempt.pop(mac, None)
