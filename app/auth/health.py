"""Bounded, product-safe authorization health evidence."""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Mapping


OUTCOME_VERIFIED_SUCCESS = "verified_success"
OUTCOME_RETRYABLE_FAILURE = "retryable_system_failure"
OUTCOME_BLOCKING_FAILURE = "blocking_system_failure"
OUTCOMES = frozenset(
    {
        OUTCOME_VERIFIED_SUCCESS,
        OUTCOME_RETRYABLE_FAILURE,
        OUTCOME_BLOCKING_FAILURE,
    }
)
_PRECEDENCE = {
    OUTCOME_VERIFIED_SUCCESS: 0,
    OUTCOME_RETRYABLE_FAILURE: 1,
    OUTCOME_BLOCKING_FAILURE: 2,
}
_SITE_ID = re.compile(r"^[0-9a-f]{24}$")


@dataclass(frozen=True, slots=True)
class AuthorizationHealthSnapshot:
    """Immutable evidence for one configured Site."""

    site_id: str
    outcome: str | None
    observed_at: datetime | None
    last_success_at: datetime | None


class AuthorizationHealthTracker:
    """One bounded record per composition-approved Site."""

    def __init__(self, site_ids: tuple[str, ...] | frozenset[str]):
        canonical = tuple(dict.fromkeys(site_ids))
        self._records: dict[str, AuthorizationHealthSnapshot] = {
            site_id: AuthorizationHealthSnapshot(site_id, None, None, None)
            for site_id in canonical
        }
        self._lock = threading.RLock()

    @property
    def site_count(self) -> int:
        return len(self._records)

    def record(self, site_id: str, outcome: str, observed_at: datetime) -> bool:
        if outcome not in OUTCOMES:
            return False
        timestamp = _utc_datetime(observed_at)
        if timestamp is None:
            return False
        with self._lock:
            current = self._records.get(site_id)
            if current is None:
                return False
            if current.observed_at is not None:
                if timestamp < current.observed_at:
                    return False
                if (
                    timestamp == current.observed_at
                    and _PRECEDENCE[outcome]
                    < _PRECEDENCE.get(current.outcome, -1)
                ):
                    return False
            last_success = current.last_success_at
            if outcome == OUTCOME_VERIFIED_SUCCESS and (
                last_success is None or timestamp > last_success
            ):
                last_success = timestamp
            self._records[site_id] = AuthorizationHealthSnapshot(
                site_id, outcome, timestamp, last_success
            )
            return True

    def snapshot(self, site_id: str) -> AuthorizationHealthSnapshot | None:
        with self._lock:
            return self._records.get(site_id)

    def snapshots(self) -> Mapping[str, AuthorizationHealthSnapshot]:
        with self._lock:
            return MappingProxyType(dict(self._records))


class DisabledAuthorizationHealthTracker:
    site_count = 0

    def record(self, site_id: str, outcome: str, observed_at: datetime) -> bool:
        return False

    def snapshot(self, site_id: str) -> AuthorizationHealthSnapshot | None:
        return None

    def snapshots(self) -> Mapping[str, AuthorizationHealthSnapshot]:
        return MappingProxyType({})


DISABLED_AUTHORIZATION_HEALTH_TRACKER = DisabledAuthorizationHealthTracker()


def authorization_health_tracker_from_settings(
    settings: Mapping[str, object],
) -> AuthorizationHealthTracker | DisabledAuthorizationHealthTracker:
    """Create a bounded tracker without making auth depend on Admin config."""
    raw = settings.get("web_admin_allowed_site_ids", "")
    if not isinstance(raw, str) or not raw:
        return DISABLED_AUTHORIZATION_HEALTH_TRACKER
    values = raw.split(",")
    if any(
        not value or value.strip() != value or _SITE_ID.fullmatch(value) is None
        for value in values
    ):
        return DISABLED_AUTHORIZATION_HEALTH_TRACKER
    return AuthorizationHealthTracker(tuple(values))


def _utc_datetime(value: object) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        return value.astimezone(timezone.utc)
    except (OverflowError, ValueError):
        return None
