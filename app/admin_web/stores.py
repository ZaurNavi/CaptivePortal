"""Bounded process-local Admin session and pre-auth CSRF stores."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, replace
from typing import Callable

from .models import AdminPrincipal, AdminSession
from .tokens import new_token


@dataclass(frozen=True, slots=True)
class LoginCapacityReservation:
    reservation_id: str


@dataclass(frozen=True, slots=True)
class PreAuthState:
    csrf_token: str
    created_at_monotonic: float
    expires_at_monotonic: float


class AdminSessionStore:
    """Thread-safe store with credential-oracle-safe capacity reservation."""

    def __init__(
        self,
        *,
        max_sessions: int,
        idle_seconds: int,
        absolute_seconds: int,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
    ):
        self._max_sessions = max_sessions
        self._idle_seconds = idle_seconds
        self._absolute_seconds = absolute_seconds
        self._clock = clock
        self._wall_clock = wall_clock
        self._sessions: dict[str, AdminSession] = {}
        self._reservations: set[str] = set()
        self._lock = threading.RLock()

    def reserve(self) -> LoginCapacityReservation | None:
        with self._lock:
            self._cleanup_locked(self._clock())
            if len(self._sessions) + len(self._reservations) >= self._max_sessions:
                return None
            reservation_id = new_token()
            self._reservations.add(reservation_id)
            return LoginCapacityReservation(reservation_id)

    def release(self, reservation: LoginCapacityReservation | None) -> None:
        if reservation is None:
            return
        with self._lock:
            self._reservations.discard(reservation.reservation_id)

    def commit(
        self,
        reservation: LoginCapacityReservation,
        principal: AdminPrincipal,
    ) -> tuple[str, AdminSession]:
        with self._lock:
            if reservation.reservation_id not in self._reservations:
                raise ValueError("login capacity reservation is not active")
            now = self._clock()
            session = AdminSession(
                principal=principal,
                csrf_token=new_token(),
                created_at_monotonic=now,
                created_at_wall=self._wall_clock(),
                last_seen_monotonic=now,
            )
            token = new_token()
            while token in self._sessions:  # pragma: no cover - cryptographic collision
                token = new_token()
            self._reservations.remove(reservation.reservation_id)
            self._sessions[token] = session
            return token, session

    def get(self, token: object, *, touch: bool = True) -> AdminSession | None:
        if not isinstance(token, str):
            return None
        with self._lock:
            now = self._clock()
            self._cleanup_locked(now)
            session = self._sessions.get(token)
            if session is None:
                return None
            if touch:
                session = replace(session, last_seen_monotonic=now)
                self._sessions[token] = session
            return session

    def revoke(self, token: object) -> bool:
        if not isinstance(token, str):
            return False
        with self._lock:
            return self._sessions.pop(token, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()
            self._reservations.clear()

    def counts(self) -> tuple[int, int]:
        with self._lock:
            self._cleanup_locked(self._clock())
            return len(self._sessions), len(self._reservations)

    def _cleanup_locked(self, now: float) -> None:
        expired = [
            token
            for token, session in self._sessions.items()
            if now - session.last_seen_monotonic >= self._idle_seconds
            or now - session.created_at_monotonic >= self._absolute_seconds
        ]
        for token in expired:
            self._sessions.pop(token, None)


class AdminPreAuthCsrfStore:
    """One-time, bounded and thread-safe login CSRF state."""

    def __init__(
        self,
        *,
        max_states: int,
        ttl_seconds: int,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._max_states = max_states
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._states: dict[str, PreAuthState] = {}
        self._lock = threading.RLock()

    def issue(self) -> tuple[str, str] | None:
        with self._lock:
            now = self._clock()
            self._cleanup_locked(now)
            if len(self._states) >= self._max_states:
                return None
            handle = new_token()
            while handle in self._states:  # pragma: no cover - cryptographic collision
                handle = new_token()
            state = PreAuthState(
                csrf_token=new_token(),
                created_at_monotonic=now,
                expires_at_monotonic=now + self._ttl_seconds,
            )
            self._states[handle] = state
            return handle, state.csrf_token

    def consume(self, handle: object) -> str | None:
        if not isinstance(handle, str):
            return None
        with self._lock:
            now = self._clock()
            self._cleanup_locked(now)
            state = self._states.pop(handle, None)
            return None if state is None else state.csrf_token

    def clear(self) -> None:
        with self._lock:
            self._states.clear()

    def size(self) -> int:
        with self._lock:
            self._cleanup_locked(self._clock())
            return len(self._states)

    def _cleanup_locked(self, now: float) -> None:
        expired = [
            handle
            for handle, state in self._states.items()
            if now >= state.expires_at_monotonic
        ]
        for handle in expired:
            self._states.pop(handle, None)
