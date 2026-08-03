from datetime import datetime, timezone

from app.pending_sessions.protection import (
    AuthManagerPendingSessionProtection,
)


class Manager:
    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error

    def pending_session_protection_snapshot(self, site_id, mac):
        if self.error:
            raise self.error
        return self.value


def decision(value):
    return AuthManagerPendingSessionProtection(
        Manager(value)
    ).check(
        site_id="site",
        client_mac="AA:BB:CC:DD:EE:FF",
        now=datetime.now(timezone.utc),
        grace_seconds=45,
    )


def test_no_local_session_is_not_protected():
    assert decision(None).protected is False


def test_active_run_and_recent_authorization_are_protected():
    active = decision(
        {
            "worker_active": True,
            "run_active": True,
            "status": "AUTHORIZING",
            "activity_age_seconds": 100,
            "updated_at": datetime.now(timezone.utc),
        }
    )
    assert active.protected is True
    assert active.reason == "active_auth_run"

    recent = decision(
        {
            "worker_active": False,
            "run_active": False,
            "session_active": False,
            "retryable": False,
            "status": "AUTHORIZED",
            "activity_age_seconds": 10,
            "updated_at": datetime.now(timezone.utc),
        }
    )
    assert recent.protected is True
    assert recent.reason == "recently_authorized"


def test_old_finished_session_is_not_protected():
    result = decision(
        {
            "worker_active": False,
            "run_active": False,
            "session_active": False,
            "retryable": False,
            "status": "AUTHORIZED",
            "activity_age_seconds": 100,
            "updated_at": datetime.now(timezone.utc),
        }
    )
    assert result.protected is False


def test_adapter_failure_protects_client():
    adapter = AuthManagerPendingSessionProtection(
        Manager(error=RuntimeError("boom"))
    )
    result = adapter.check(
        site_id="site",
        client_mac="AA:BB:CC:DD:EE:FF",
        now=datetime.now(timezone.utc),
        grace_seconds=45,
    )
    assert result.protected is True
    assert result.reason == "protection_check_failed"
