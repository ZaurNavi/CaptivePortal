from __future__ import annotations

from datetime import datetime, timezone

from .models import ProtectionDecision


_ACTIVE_STATES = {
    "WAITING",
    "AUTHORIZING",
    "VERIFYING",
    "RESETTING",
}


class AuthManagerPendingSessionProtection:
    """Read-only fail-closed adapter over AuthSessionManager."""

    def __init__(self, manager) -> None:
        self._manager = manager

    def check(
        self,
        *,
        site_id: str,
        client_mac: str,
        now: datetime,
        grace_seconds: float,
    ) -> ProtectionDecision:
        try:
            snapshot = (
                self._manager.pending_session_protection_snapshot(
                    site_id,
                    client_mac,
                )
            )
        except Exception:
            return ProtectionDecision(
                protected=True,
                reason="protection_check_failed",
                observed_at=_utc(now),
            )

        if snapshot is None:
            return ProtectionDecision(protected=False)

        observed_at = snapshot.get("updated_at")
        if not isinstance(observed_at, datetime):
            observed_at = _utc(now)

        if snapshot.get("worker_active"):
            return ProtectionDecision(
                True,
                "active_auth_run",
                observed_at,
            )
        if snapshot.get("run_active"):
            return ProtectionDecision(
                True,
                "active_auth_run",
                observed_at,
            )

        state = snapshot.get("status")
        if state in _ACTIVE_STATES or snapshot.get("session_active"):
            return ProtectionDecision(
                True,
                "active_auth_session",
                observed_at,
            )
        if snapshot.get("retryable"):
            return ProtectionDecision(
                True,
                "authorization_retry",
                observed_at,
            )

        activity_age = snapshot.get("activity_age_seconds")
        if (
            isinstance(activity_age, (int, float))
            and not isinstance(activity_age, bool)
            and activity_age < float(grace_seconds)
        ):
            reason = (
                "recently_authorized"
                if state == "AUTHORIZED"
                else "recent_portal_activity"
            )
            return ProtectionDecision(
                True,
                reason,
                observed_at,
            )

        return ProtectionDecision(
            protected=False,
            observed_at=observed_at,
        )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
