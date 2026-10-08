"""Immutable Admin Web security identities."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AdminPrincipal:
    username: str
    principal_type: str = "platform_operator"
    global_capabilities: frozenset[str] = frozenset()

    def __post_init__(self):
        object.__setattr__(self, "global_capabilities", frozenset(self.global_capabilities))


@dataclass(frozen=True, slots=True)
class AdminSession:
    principal: AdminPrincipal
    csrf_token: str
    created_at_monotonic: float
    created_at_wall: float
    last_seen_monotonic: float
