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
