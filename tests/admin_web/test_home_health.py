from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from app.admin_web import create_admin_web_runtime
from app.admin_web.home_health import (
    HomeHealthBusy,
    HomeHealthDeadline,
    HomeHealthReadService,
    _aggregate,
    _component,
)
from app.admin_web.home_health_config import (
    HomeHealthConfigError,
    home_health_config_from_settings,
)
from app.admin_web.home_health_serialization import (
    HomeHealthSerializationError,
    serialize_home_health,
)
from app.admin_web.config import admin_web_config_from_settings
from app.auth.health import (
    AuthorizationHealthTracker,
    OUTCOME_BLOCKING_FAILURE,
    OUTCOME_RETRYABLE_FAILURE,
    OUTCOME_VERIFIED_SUCCESS,
)
from app.observations.models import ObservationCycle

from .conftest import SITE_ID, enabled_settings, login


UTC = timezone.utc
NOW = datetime(2026, 8, 27, 12, tzinfo=UTC)


def health_settings(**overrides):
    values = enabled_settings(
        web_admin_home_health_enabled="true",
        web_admin_home_health_refresh_seconds="60",
        web_admin_home_health_request_timeout_seconds="20",
        web_admin_home_health_auth_evidence_max_age_seconds="86400",
    )
    values.update(overrides)
    return values


def _meta(kind="client", freshness="fresh", latest="success"):
    return SimpleNamespace(
        observed_at="2026-08-27T11:59:00.000Z",
        capture_finished_at="2026-08-27T11:59:02.000Z",
        freshness_status=freshness,
        latest_attempt_result=latest,
    )


class CurrentRead:
    def __init__(self, client="fresh", ap="fresh", latest="success"):
        self.client = client
        self.ap = ap
        self.latest = latest

    def get_current_client_summary(self, site_id, **_):
        assert site_id == SITE_ID
        return SimpleNamespace(snapshot=_meta("client", self.client, self.latest))

    def get_current_ap_summary(self, site_id, **_):
        assert site_id == SITE_ID
        return SimpleNamespace(snapshot=_meta("ap", self.ap, self.latest))


def _cycle(kind, finished, *, result="success", complete=True):
    return ObservationCycle(
        f"{kind}-{finished}", kind, SITE_ID, "completed",
        "2026-08-27T11:58:00.000Z", finished, None, complete, result,
        0, 0, 0, 0, 0, 0,
        "2026-08-27T11:58:00.000Z", finished,
    )


class ObservationRepository:
    def __init__(self, values):
        self.values = values

    def get_home_health_cycles(self, site_id, kind):
        assert site_id == SITE_ID
        return self.values[kind]


class Analytics:
    state = "active"
    visit_service = object()
    current_traffic_service = object()
    home_activity_service = object()

    def live_health_payload(self):
        return True, {"state": "active"}


def service(*, tracker=None, current=None, observation=None, visit=None, analytics=None,
            traffic=False, activity=False):
    if tracker is None:
        tracker = AuthorizationHealthTracker((SITE_ID,))
        tracker.record(SITE_ID, OUTCOME_VERIFIED_SUCCESS, NOW - timedelta(seconds=10))
    success = _cycle("client", "2026-08-27T11:59:00.000Z")
    ap_success = _cycle("ap_dynamic", "2026-08-27T11:59:00.000Z")
    config = SimpleNamespace(
        site_ids=(SITE_ID,), client_enabled=True, ap_enabled=True,
        client_interval_seconds=60, client_max_pages=20,
        request_timeout_seconds=5, ap_interval_seconds=30,
        ap_cycle_max_duration_seconds=120,
        ap_config_cycle_max_duration_seconds=180,
    )
    observation = observation or SimpleNamespace(
        state="active", config=config,
        client_worker=SimpleNamespace(running=True),
        ap_worker=SimpleNamespace(running=True),
        repository=ObservationRepository({
            "client": (success, success),
            "ap_dynamic": (ap_success, ap_success),
        }),
    )
    return HomeHealthReadService(
        allowed_site_ids=frozenset({SITE_ID}),
        auth_tracker=tracker,
        current_state_runtime=current or SimpleNamespace(
            state="active", read_service=CurrentRead()
        ),
        observation_runtime=observation,
        visit_runtime=visit or SimpleNamespace(state="active", available=True),
        analytics_runtime=analytics or Analytics(),
        auth_evidence_max_age_seconds=300,
        max_concurrent_queries=2,
        max_query_duration_seconds=10,
        home_traffic_enabled=traffic,
        home_activity_enabled=activity,
    )


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        (("operational",) * 5, "operational"),
        (("unavailable", "operational", "operational", "operational", "operational"), "unavailable"),
        (("degraded", "operational", "operational", "operational", "operational"), "degraded"),
        (("operational", "unavailable", "operational", "operational", "operational"), "degraded"),
        (("operational", "unknown", "operational", "operational", "operational"), "unknown"),
        (("operational", "unknown", "degraded", "operational", "operational"), "degraded"),
    ],
)
def test_aggregate_contract(statuses, expected):
    identities = (
        ("guest_access", "Guest Access", "critical", "site"),
        ("live_network_state", "Live", "feature", "site"),
        ("network_history", "History", "feature", "site"),
        ("visit_tracking", "Visit", "feature", "global"),
        ("analytics_home_data", "Analytics", "feature", "global"),
    )
    reason = {
        "operational": "latest_authorization_verified",
        "degraded": "authorization_transient_failure",
        "unavailable": "authorization_unavailable",
        "unknown": "initializing",
    }
    values = tuple(
        _component(identity, SITE_ID, status, reason[status])
        for identity, status in zip(identities, statuses)
    )
    assert _aggregate(values) == expected


def test_tracker_is_bounded_immutable_thread_safe_and_deterministic():
    tracker = AuthorizationHealthTracker((SITE_ID,))
    older = NOW - timedelta(seconds=1)
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(
            lambda item: tracker.record(SITE_ID, item, NOW),
            (OUTCOME_VERIFIED_SUCCESS, OUTCOME_RETRYABLE_FAILURE, OUTCOME_BLOCKING_FAILURE),
        ))
    assert tracker.snapshot(SITE_ID).outcome == OUTCOME_BLOCKING_FAILURE
    assert tracker.record(SITE_ID, OUTCOME_VERIFIED_SUCCESS, older) is False
    assert tracker.record("ffffffffffffffffffffffff", OUTCOME_VERIFIED_SUCCESS, NOW) is False
    assert tracker.site_count == 1
    with pytest.raises(TypeError):
        tracker.snapshots()[SITE_ID] = None


@pytest.mark.parametrize(
    ("outcome", "age", "expected", "reason"),
    [
        (OUTCOME_VERIFIED_SUCCESS, 299, "operational", "latest_authorization_verified"),
        (OUTCOME_VERIFIED_SUCCESS, 300, "operational", "latest_authorization_verified"),
        (OUTCOME_VERIFIED_SUCCESS, 301, "unknown", "authorization_evidence_old"),
        (OUTCOME_RETRYABLE_FAILURE, 1, "degraded", "authorization_transient_failure"),
        (OUTCOME_BLOCKING_FAILURE, 1, "unavailable", "authorization_unavailable"),
    ],
)
def test_guest_evidence_age_and_outcomes(outcome, age, expected, reason):
    tracker = AuthorizationHealthTracker((SITE_ID,))
    tracker.record(SITE_ID, outcome, NOW - timedelta(seconds=age))
    item = service(tracker=tracker).evaluate(SITE_ID, evaluated_at=NOW).components[0]
    assert (item.status, item.reason_code) == (expected, reason)


def test_no_guest_evidence_and_future_evidence_are_unknown():
    empty = AuthorizationHealthTracker((SITE_ID,))
    first = service(tracker=empty).evaluate(SITE_ID, evaluated_at=NOW).components[0]
    future = AuthorizationHealthTracker((SITE_ID,))
    future.record(SITE_ID, OUTCOME_VERIFIED_SUCCESS, NOW + timedelta(seconds=1))
    second = service(tracker=future).evaluate(SITE_ID, evaluated_at=NOW).components[0]
    assert first.reason_code == "no_authorization_evidence"
    assert second.reason_code == "invalid_authorization_evidence_time"


@pytest.mark.parametrize(
    ("state", "client", "ap", "latest", "expected"),
    [
        ("active", "fresh", "fresh", "success", "operational"),
        ("active", "stale", "fresh", "success", "degraded"),
        ("active", "fresh", "fresh", "partial", "degraded"),
        ("active", "unavailable", "fresh", "success", "unavailable"),
        ("disabled", "fresh", "fresh", "success", "unavailable"),
    ],
)
def test_current_state_reuses_canonical_freshness(state, client, ap, latest, expected):
    current = SimpleNamespace(state=state, read_service=CurrentRead(client, ap, latest))
    item = service(current=current).evaluate(SITE_ID, evaluated_at=NOW).components[1]
    assert item.status == expected
    if state == "disabled":
        assert item.reason_code == "component_disabled"


def test_observation_stale_boundary_and_latest_partial():
    finished = NOW - timedelta(seconds=160)
    stamp = finished.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    client = _cycle("client", stamp)
    ap = _cycle("ap_dynamic", stamp)
    config = SimpleNamespace(
        site_ids=(SITE_ID,), client_enabled=True, ap_enabled=False,
        client_interval_seconds=60, client_max_pages=10,
        request_timeout_seconds=10,
    )
    runtime = SimpleNamespace(
        state="active", config=config,
        client_worker=SimpleNamespace(running=True),
        repository=ObservationRepository({"client": (client, client)}),
    )
    at_boundary = service(observation=runtime).evaluate(
        SITE_ID, evaluated_at=finished + timedelta(seconds=160)
    ).components[2]
    beyond = service(observation=runtime).evaluate(
        SITE_ID, evaluated_at=finished + timedelta(seconds=160, microseconds=1)
    ).components[2]
    assert at_boundary.status == "operational"
    assert (beyond.status, beyond.reason_code) == ("degraded", "stale_evidence")


def test_visit_and_analytics_are_independent_component_states():
    value = service(
        visit=SimpleNamespace(state="degraded", available=True),
        analytics=SimpleNamespace(state="unavailable"),
    ).evaluate(SITE_ID, evaluated_at=NOW)
    assert value.components[3].status == "degraded"
    assert value.components[4].status == "unavailable"
    assert value.status == "degraded"


def test_optional_home_services_are_expectation_gated():
    analytics = Analytics()
    analytics.current_traffic_service = None
    analytics.home_activity_service = None
    not_expected = service(analytics=analytics).evaluate(SITE_ID, evaluated_at=NOW)
    expected = service(analytics=analytics, traffic=True).evaluate(SITE_ID, evaluated_at=NOW)
    assert not_expected.components[4].status == "operational"
    assert expected.components[4].reason_code == "current_traffic_service_unavailable"


def test_component_exception_is_isolated_and_order_serializes():
    current = SimpleNamespace(state="active", read_service=CurrentRead())
    current.read_service.get_current_client_summary = lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("private-path"))
    result = service(current=current).evaluate(SITE_ID, evaluated_at=NOW)
    payload = serialize_home_health(result)
    assert [item["id"] for item in payload["components"]] == [
        "guest_access", "live_network_state", "network_history",
        "visit_tracking", "analytics_home_data",
    ]
    assert payload["components"][1]["reason_code"] == "health_read_failed"
    assert "private-path" not in str(payload)

    forged = replace(
        result,
        components=(
            replace(result.components[0], message="raw internal error"),
            *result.components[1:],
        ),
    )
    with pytest.raises(HomeHealthSerializationError):
        serialize_home_health(forged)


def test_health_query_slot_is_nonblocking_and_deadline_is_checked_between_sources():
    entered = threading.Event()
    release = threading.Event()
    current = SimpleNamespace(state="active", read_service=CurrentRead())
    original = current.read_service.get_current_client_summary

    def blocked(*args, **kwargs):
        entered.set()
        assert release.wait(2)
        return original(*args, **kwargs)

    current.read_service.get_current_client_summary = blocked
    bounded = service(current=current)
    bounded._slots = threading.BoundedSemaphore(1)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(bounded.evaluate, SITE_ID, evaluated_at=NOW)
        assert entered.wait(1)
        with pytest.raises(HomeHealthBusy):
            bounded.evaluate(SITE_ID, evaluated_at=NOW)
        release.set()
        assert future.result().site_id == SITE_ID

    clock = iter((0.0, 0.0, 11.0))
    expired = service()
    expired._monotonic = lambda: next(clock)
    with pytest.raises(HomeHealthDeadline):
        expired.evaluate(SITE_ID, evaluated_at=NOW)


def test_health_config_isolated_and_strict():
    admin = admin_web_config_from_settings(health_settings())
    config = home_health_config_from_settings(health_settings(), admin_config=admin)
    assert (config.refresh_seconds, config.request_timeout_seconds, config.auth_evidence_max_age_seconds) == (60, 20, 86400)
    with pytest.raises(HomeHealthConfigError):
        home_health_config_from_settings(
            health_settings(web_admin_home_health_request_timeout_seconds="10"),
            admin_config=admin,
        )
    disabled = home_health_config_from_settings(
        health_settings(
            web_admin_home_health_enabled="false",
            web_admin_home_health_refresh_seconds="broken",
        ),
        admin_config=admin,
    )
    assert disabled.enabled is False


@pytest.fixture
def health_app(tmp_path):
    tracker = AuthorizationHealthTracker((SITE_ID,))
    runtime = create_admin_web_runtime(
        health_settings(),
        Analytics(),
        SimpleNamespace(repository=SimpleNamespace(config=SimpleNamespace(db_path=tmp_path / "registry.sqlite3"))),
        SimpleNamespace(repository=SimpleNamespace(db_path=tmp_path / "visits.sqlite3")),
        SimpleNamespace(_repository=SimpleNamespace(db_path=tmp_path / "observations.sqlite3")),
        logging.getLogger("home-health-test"),
        authorization_health_tracker=tracker,
        current_state_runtime=SimpleNamespace(state="active", read_service=CurrentRead()),
        observation_runtime=service()._observations,
        visit_runtime=SimpleNamespace(state="active", available=True),
    )
    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    app.register_blueprint(runtime.blueprint)
    app.extensions["admin_web_runtime"] = runtime
    return app


def test_health_route_security_feature_gate_and_component_http_200(health_app):
    client = health_app.test_client()
    url = f"/admin/api/v1/sites/{SITE_ID}/home/health"
    assert client.get(url, base_url="https://localhost").status_code == 401
    login(client)
    assert client.get(url + "?unexpected=1", base_url="https://localhost").status_code == 400
    response = client.get(url, base_url="https://localhost")
    assert response.status_code == 200
    assert response.get_json()["result"]["health_version"] == 1

    runtime = health_app.extensions["admin_web_runtime"]
    runtime.home_health_service._current_state.read_service.get_current_client_summary = (
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            OSError("C:/private/current_state.sqlite3")
        )
    )
    isolated = client.get(url, base_url="https://localhost")
    assert isolated.status_code == 200
    body = isolated.get_json()
    assert body["result"]["components"][1]["reason_code"] == "health_read_failed"
    assert "private" not in str(body)


@pytest.mark.parametrize(
    ("error", "status", "code", "retry_after"),
    [
        (HomeHealthBusy(), 429, "concurrency_limit", "1"),
        (HomeHealthDeadline(), 503, "query_deadline", None),
    ],
)
def test_health_route_bounded_failure_mapping(
    health_app, error, status, code, retry_after
):
    runtime = health_app.extensions["admin_web_runtime"]
    runtime.home_health_service = SimpleNamespace(
        evaluate=lambda *_args, **_kwargs: (_ for _ in ()).throw(error)
    )
    client = health_app.test_client(); login(client)
    response = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/home/health",
        base_url="https://localhost",
    )
    assert response.status_code == status
    assert response.get_json()["error"]["code"] == code
    assert response.headers.get("Retry-After") == retry_after


def test_health_disabled_is_404_without_evaluation(tmp_path):
    runtime = create_admin_web_runtime(
        enabled_settings(), Analytics(),
        SimpleNamespace(repository=SimpleNamespace(config=SimpleNamespace(db_path=tmp_path / "r"))),
        SimpleNamespace(repository=SimpleNamespace(db_path=tmp_path / "v")),
        SimpleNamespace(_repository=SimpleNamespace(db_path=tmp_path / "o")),
        logging.getLogger("health-disabled"),
    )
    app = Flask(__name__); app.config.update(TESTING=True)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    app.register_blueprint(runtime.blueprint)
    client = app.test_client(); login(client)
    assert client.get(
        f"/admin/api/v1/sites/{SITE_ID}/home/health",
        base_url="https://localhost",
    ).status_code == 404


def test_invalid_health_only_config_leaves_admin_active_and_health_503(tmp_path):
    runtime = create_admin_web_runtime(
        health_settings(web_admin_home_health_request_timeout_seconds="10"),
        Analytics(),
        SimpleNamespace(repository=SimpleNamespace(config=SimpleNamespace(db_path=tmp_path / "r"))),
        SimpleNamespace(repository=SimpleNamespace(db_path=tmp_path / "v")),
        SimpleNamespace(_repository=SimpleNamespace(db_path=tmp_path / "o")),
        logging.getLogger("health-invalid-config"),
    )
    assert runtime.state == "active"
    assert runtime.home_health_state == "unavailable"
    app = Flask(__name__); app.config.update(TESTING=True)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    app.register_blueprint(runtime.blueprint)
    client = app.test_client(); login(client)
    response = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/home/health",
        base_url="https://localhost",
    )
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "source_unavailable"
