import threading
import time

from app.controllers.omada import OmadaProvider
from app.models import Result


def bare_provider():
    provider = object.__new__(OmadaProvider)
    provider._token_condition = threading.Condition(
        threading.RLock()
    )
    provider._cached_token = None
    provider._cached_token_expires_at = 0.0
    provider._token_refreshing = False
    return provider


def test_concurrent_get_token_performs_one_refresh(monkeypatch):
    provider = bare_provider()
    calls = 0
    lock = threading.Lock()

    def request():
        nonlocal calls
        with lock:
            calls += 1
        time.sleep(0.05)
        return Result.ok(
            data={
                "token": "shared-token",
                "http_status": 200,
                "error_code": 0,
            }
        )

    monkeypatch.setattr(
        provider,
        "_request_token_uncached",
        request,
    )
    results = []

    def worker():
        results.append(provider._get_token())

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(1)

    assert calls == 1
    assert len(results) == 2
    assert {result.data["token"] for result in results} == {
        "shared-token"
    }


def test_refresh_failure_does_not_publish_partial_cache(monkeypatch):
    provider = bare_provider()
    monkeypatch.setattr(
        provider,
        "_request_token_uncached",
        lambda: Result.fail(
            error="TOKEN_FAILED",
            message="failed",
            data={"retryable": True},
        ),
    )

    result = provider._get_token()

    assert result.success is False
    assert provider._cached_token is None
    assert provider._cached_token_expires_at == 0.0



def test_cleaner_recovery_does_not_invalidate_current_token(
    monkeypatch,
):
    """Cleaner recovery must preserve the provider's current token."""
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from app.pending_sessions.cleaner import (
        PendingClientSessionCleaner,
    )
    from app.pending_sessions.models import (
        PendingClientCandidate,
        PendingClientObservation,
    )

    observation = PendingClientObservation(
        mac="AA-BB-CC-DD-EE-FF",
        wireless=True,
        active=True,
        auth_status=1,
        uptime=999,
        ssid="Guest",
        blocked=False,
        client_ip="192.168.1.2",
        ap_mac=None,
        radio_id=None,
        channel=None,
        rssi=None,
        snr=None,
    )
    candidate = PendingClientCandidate(
        observation=observation,
        list_uptime=999,
    )

    class Provider:
        def __init__(self):
            self.invalidated = []
            self.get_calls = 0

        def _invalidate_cached_token(self, token=None):
            self.invalidated.append(token)

        def get_pending_client_state(
            self,
            *,
            site_id,
            client_mac,
            timeout_seconds,
        ):
            self.get_calls += 1
            return Result.ok(
                data={
                    "client": {"placeholder": True},
                    "http_status": 200,
                    "error_code": 0,
                }
            )

    class Protection:
        def __init__(self):
            self.calls = 0

        def check(self, **kwargs):
            self.calls += 1
            return SimpleNamespace(protected=False)

    provider = Provider()
    protection = Protection()

    cleaner = object.__new__(PendingClientSessionCleaner)
    cleaner.provider = provider
    cleaner.protection = protection
    cleaner.config = SimpleNamespace(
        site_id="site-1",
        request_timeout_seconds=1,
        portal_grace_seconds=0,
    )
    cleaner._utcnow = lambda: datetime.now(timezone.utc)
    cleaner._retry_get = (
        lambda operation, deadline=None: operation()
    )

    monkeypatch.setattr(
        cleaner,
        "_preflight_decision",
        lambda _candidate, _raw_client: (observation, ""),
    )

    recovered = cleaner._recover_expired_token(
        candidate,
        deadline=123.0,
    )

    assert recovered is observation
    assert provider.get_calls == 1
    assert protection.calls == 2
    assert provider.invalidated == []
