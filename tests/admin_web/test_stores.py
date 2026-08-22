from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from app.admin_web.models import AdminPrincipal
from app.admin_web.rate_limit import AdminLoginRateLimiter
from app.admin_web.stores import AdminPreAuthCsrfStore, AdminSessionStore
from app.admin_web.tokens import is_canonical_token, token_matches


class Clock:
    value = 100.0

    def __call__(self):
        return self.value


def test_session_reservation_is_bounded_and_concurrent():
    store = AdminSessionStore(max_sessions=1, idle_seconds=60, absolute_seconds=300)
    with ThreadPoolExecutor(max_workers=8) as pool:
        reservations = list(pool.map(lambda _: store.reserve(), range(32)))
    assert sum(item is not None for item in reservations) == 1
    assert store.counts() == (0, 1)


def test_concurrent_get_touch_and_revoke_are_safe():
    store = AdminSessionStore(max_sessions=1, idle_seconds=60, absolute_seconds=300)
    reservation = store.reserve()
    token, _ = store.commit(reservation, AdminPrincipal("operator"))
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(
            pool.map(
                lambda action: (
                    store.get(token)
                    if action % 3
                    else store.revoke(token)
                ),
                range(64),
            )
        )
    assert any(result is True for result in results)
    assert store.counts() == (0, 0)


def test_reservation_commit_is_atomic_and_release_is_idempotent():
    store = AdminSessionStore(max_sessions=1, idle_seconds=60, absolute_seconds=300)
    reservation = store.reserve()
    token, session = store.commit(reservation, AdminPrincipal("operator"))
    store.release(reservation)
    assert is_canonical_token(token)
    assert is_canonical_token(session.csrf_token)
    assert store.counts() == (1, 0)
    assert store.reserve() is None


def test_idle_and_absolute_expiry_are_independent():
    clock = Clock()
    store = AdminSessionStore(
        max_sessions=2,
        idle_seconds=10,
        absolute_seconds=20,
        clock=clock,
    )
    reservation = store.reserve()
    token, _ = store.commit(reservation, AdminPrincipal("operator"))
    clock.value = 109
    assert store.get(token) is not None
    clock.value = 118
    assert store.get(token) is not None
    clock.value = 120
    assert store.get(token) is None


def test_preauth_is_one_time_bounded_and_expires():
    clock = Clock()
    store = AdminPreAuthCsrfStore(max_states=1, ttl_seconds=10, clock=clock)
    handle, token = store.issue()
    assert store.issue() is None
    assert store.consume(handle) == token
    assert store.consume(handle) is None
    handle, _ = store.issue()
    clock.value = 111
    assert store.consume(handle) is None


def test_preauth_concurrent_issue_never_exceeds_capacity():
    store = AdminPreAuthCsrfStore(max_states=4, ttl_seconds=60)
    with ThreadPoolExecutor(max_workers=16) as pool:
        issued = list(pool.map(lambda _: store.issue(), range(64)))
    assert sum(item is not None for item in issued) == 4
    assert store.size() == 4


def test_token_comparison_rejects_unicode_padding_and_wrong_length():
    store = AdminPreAuthCsrfStore(max_states=1, ttl_seconds=60)
    _, token = store.issue()
    assert token_matches(token, token)
    assert not token_matches("é" * 43, token)
    assert not token_matches(token + "=", token)
    assert not token_matches(token[:-1], token)


def test_rate_limiter_window_lock_capacity_and_success_reset():
    clock = Clock()
    limiter = AdminLoginRateLimiter(
        window_seconds=10,
        max_failures=2,
        lock_seconds=20,
        max_trackers=1,
        clock=clock,
    )
    assert limiter.begin_attempt("127.0.0.1") == "allowed"
    limiter.finish_attempt("127.0.0.1", "failure")
    assert limiter.begin_attempt("127.0.0.2") == "capacity"
    assert limiter.begin_attempt("127.0.0.1") == "allowed"
    limiter.finish_attempt("127.0.0.1", "failure")
    assert limiter.begin_attempt("127.0.0.1") == "locked"
    clock.value = 121
    assert limiter.begin_attempt("127.0.0.1") == "allowed"
    limiter.finish_attempt("127.0.0.1", "success")
    assert limiter.size() == 0


def test_rate_limiter_concurrent_failures_never_lose_lock_state():
    limiter = AdminLoginRateLimiter(
        window_seconds=60,
        max_failures=5,
        lock_seconds=60,
        max_trackers=16,
    )

    def fail_attempt(_):
        if limiter.begin_attempt("127.0.0.1") == "allowed":
            limiter.finish_attempt("127.0.0.1", "failure")

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(fail_attempt, range(64)))
    assert limiter.begin_attempt("127.0.0.1") == "locked"


def test_rate_limiter_reserves_distinct_source_capacity_atomically():
    limiter = AdminLoginRateLimiter(
        window_seconds=60,
        max_failures=5,
        lock_seconds=60,
        max_trackers=1,
    )
    assert limiter.begin_attempt("192.0.2.1") == "allowed"
    assert limiter.begin_attempt("192.0.2.2") == "capacity"
    limiter.finish_attempt("192.0.2.1", "neutral")
    assert limiter.begin_attempt("192.0.2.2") == "allowed"
    limiter.finish_attempt("192.0.2.2", "neutral")
    assert limiter.size() == 0


def test_rate_limiter_concurrent_distinct_sources_admit_only_capacity():
    limiter = AdminLoginRateLimiter(
        window_seconds=60,
        max_failures=5,
        lock_seconds=60,
        max_trackers=1,
    )
    sources = [f"192.0.2.{number}" for number in range(1, 33)]
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(limiter.begin_attempt, sources))
    assert results.count("allowed") == 1
    assert results.count("capacity") == len(sources) - 1
    admitted = sources[results.index("allowed")]
    limiter.finish_attempt(admitted, "neutral")
    assert limiter.size() == 0


def test_rate_limiter_reserved_failure_cannot_be_lost():
    limiter = AdminLoginRateLimiter(
        window_seconds=60,
        max_failures=1,
        lock_seconds=60,
        max_trackers=1,
    )
    assert limiter.begin_attempt("192.0.2.1") == "allowed"
    assert limiter.begin_attempt("192.0.2.2") == "capacity"
    limiter.finish_attempt("192.0.2.1", "failure")
    assert limiter.begin_attempt("192.0.2.1") == "locked"
    assert limiter.begin_attempt("192.0.2.2") == "capacity"


def test_rate_limiter_neutral_completion_is_not_a_password_failure():
    limiter = AdminLoginRateLimiter(
        window_seconds=60,
        max_failures=1,
        lock_seconds=60,
        max_trackers=1,
    )
    assert limiter.begin_attempt("192.0.2.1") == "allowed"
    limiter.finish_attempt("192.0.2.1", "neutral")
    assert limiter.size() == 0
    assert limiter.begin_attempt("192.0.2.1") == "allowed"
    limiter.finish_attempt("192.0.2.1", "neutral")
