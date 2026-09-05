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
    HomeHealthReadService,
    _aggregate,
    _component,
)
from app.analytics.source_gateway import (
    AnalyticsQueryDeadlineExceeded,
    QueryDeadline,
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
from app.admin_web.models import AdminPrincipal
from app.admin_web.query_service import AdminQueryBusy
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
        web_admin_home_health_request_timeout_seconds="30",
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
        self.deadlines = []

    def get_home_health_cycles(self, site_id, kind, *, deadline=None):
        assert site_id == SITE_ID
        self.deadlines.append(deadline)
        if deadline is not None:
            deadline.require_remaining()
        return self.values[kind]


class Analytics:
    state = "active"
    visit_service = object()
    current_traffic_service = object()
    home_activity_service = object()

    def live_health_payload(self):
        return True, {"state": "active"}


def service(*, tracker=None, current=None, observation=None, visit=None, analytics=None,
            traffic=False, activity=False, now_factory=None,
            cycle_finished_at="2026-08-27T11:59:00.000Z"):
    if tracker is None:
        tracker = AuthorizationHealthTracker((SITE_ID,))
        tracker.record(SITE_ID, OUTCOME_VERIFIED_SUCCESS, NOW - timedelta(seconds=10))
    success = _cycle("client", cycle_finished_at)
    ap_success = _cycle("ap_dynamic", cycle_finished_at)
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
        home_traffic_enabled=traffic,
        home_activity_enabled=activity,
        now_factory=now_factory,
    )


def evaluate(value, *, at=NOW, deadline=None):
    return value.evaluate(
        SITE_ID,
        deadline=deadline or QueryDeadline.after(60),
        evaluated_at=at,
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
    assert tracker.snapshot(SITE_ID).last_success_at == NOW
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
    item = evaluate(service(tracker=tracker)).components[0]
    assert (item.status, item.reason_code) == (expected, reason)


def test_no_guest_evidence_and_future_evidence_are_unknown():
    empty = AuthorizationHealthTracker((SITE_ID,))
    first = evaluate(service(tracker=empty)).components[0]
    future = AuthorizationHealthTracker((SITE_ID,))
    future.record(SITE_ID, OUTCOME_VERIFIED_SUCCESS, NOW + timedelta(seconds=1))
    second = evaluate(service(tracker=future)).components[0]
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
    item = evaluate(service(current=current)).components[1]
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
    at_boundary = evaluate(
        service(observation=runtime),
        at=finished + timedelta(seconds=160),
    ).components[2]
    beyond = evaluate(
        service(observation=runtime),
        at=finished + timedelta(seconds=160, microseconds=1),
    ).components[2]
    assert at_boundary.status == "operational"
    assert (beyond.status, beyond.reason_code) == ("degraded", "stale_evidence")


def test_visit_and_analytics_are_independent_component_states():
    value = evaluate(service(
        visit=SimpleNamespace(state="degraded", available=True),
        analytics=SimpleNamespace(state="unavailable"),
    ))
    assert value.components[3].status == "degraded"
    assert value.components[4].status == "unavailable"
    assert value.status == "degraded"


def test_no_recent_visits_and_empty_successful_observation_are_healthy():
    value = evaluate(service())
    assert value.components[2].reason_code == "observation_operational"
    assert value.components[3].reason_code == "visit_operational"


def test_optional_home_services_are_expectation_gated():
    analytics = Analytics()
    analytics.current_traffic_service = None
    analytics.home_activity_service = None
    not_expected = evaluate(service(analytics=analytics))
    expected = evaluate(service(analytics=analytics, traffic=True))
    assert not_expected.components[4].status == "operational"
    assert expected.components[4].reason_code == "current_traffic_service_unavailable"


def test_component_exception_is_isolated_and_order_serializes():
    current = SimpleNamespace(state="active", read_service=CurrentRead())
    current.read_service.get_current_client_summary = lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("private-path"))
    result = evaluate(service(current=current))
    payload = serialize_home_health(result)
    assert [item["id"] for item in payload["components"]] == [
        "guest_access", "live_network_state", "network_history",
        "visit_tracking", "analytics_home_data",
    ]
    assert payload["components"][1]["reason_code"] == "health_read_failed"
    assert "private-path" not in str(payload)
    assert payload["components"][0]["scope"] == {
        "type": "site", "site_id": SITE_ID,
    }
    assert payload["components"][3]["scope"] == {"type": "global"}
    assert payload["components"][4]["scope"] == {"type": "global"}

    forged = replace(
        result,
        components=(
            replace(result.components[0], message="raw internal error"),
            *result.components[1:],
        ),
    )
    with pytest.raises(HomeHealthSerializationError):
        serialize_home_health(forged)


def test_analytics_evidence_is_actual_boundary_evaluation_time():
    boundary_time = NOW + timedelta(seconds=7)
    result = evaluate(
        service(now_factory=lambda: boundary_time),
        at=NOW - timedelta(days=30),
    )
    analytics = result.components[4]
    assert analytics.evidence_at == boundary_time
    assert analytics.evidence_at != result.evaluated_at
    assert analytics.last_success_at is None


def test_health_has_no_private_query_slot_and_deadline_stops_remaining_sources():
    current = SimpleNamespace(state="active", read_service=CurrentRead())
    calls = []
    current.read_service.get_current_client_summary = (
        lambda *_args, **_kwargs: calls.append("client")
    )

    class Deadline:
        def __init__(self):
            self.calls = 0

        def require_remaining(self):
            self.calls += 1
            if self.calls == 3:
                raise AnalyticsQueryDeadlineExceeded("expired")

    value = service(current=current)
    assert not hasattr(value, "_slots")
    deadline = Deadline()
    with pytest.raises(AnalyticsQueryDeadlineExceeded):
        evaluate(value, deadline=deadline)
    assert deadline.calls == 3
    assert calls == []


def test_one_request_deadline_reaches_each_observation_read():
    value = service()
    deadline = QueryDeadline.after(60)
    evaluate(value, deadline=deadline)
    assert value._observations.repository.deadlines == [deadline, deadline]


def test_health_config_isolated_and_strict():
    admin = admin_web_config_from_settings(health_settings())
    config = home_health_config_from_settings(health_settings(), admin_config=admin)
    assert (config.refresh_seconds, config.request_timeout_seconds, config.auth_evidence_max_age_seconds) == (60, 30, 86400)
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


def _health_app(
    tmp_path,
    *,
    analytics=None,
    registry_source=True,
    setting_updates=None,
):
    now = datetime.now(UTC)
    tracker = AuthorizationHealthTracker((SITE_ID,))
    tracker.record(
        SITE_ID,
        OUTCOME_VERIFIED_SUCCESS,
        now - timedelta(seconds=10),
    )
    cycle_finished_at = now.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    registry = (
        SimpleNamespace(
            repository=SimpleNamespace(
                config=SimpleNamespace(
                    db_path=tmp_path / "registry.sqlite3"
                )
            )
        )
        if registry_source
        else None
    )
    runtime = create_admin_web_runtime(
        health_settings(**(setting_updates or {})),
        analytics or Analytics(),
        registry,
        SimpleNamespace(repository=SimpleNamespace(db_path=tmp_path / "visits.sqlite3")),
        SimpleNamespace(_repository=SimpleNamespace(db_path=tmp_path / "observations.sqlite3")),
        logging.getLogger("home-health-test"),
        authorization_health_tracker=tracker,
        current_state_runtime=SimpleNamespace(state="active", read_service=CurrentRead()),
        observation_runtime=service(cycle_finished_at=cycle_finished_at)._observations,
        visit_runtime=SimpleNamespace(state="active", available=True),
    )
    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    app.register_blueprint(runtime.blueprint)
    app.extensions["admin_web_runtime"] = runtime
    return app


@pytest.fixture
def health_app(tmp_path):
    return _health_app(tmp_path)


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

    legacy = client.get("/admin/api/v1/health", base_url="https://localhost")
    assert legacy.status_code == 200
    assert legacy.get_json()["result"] == {"status": "active"}


def test_unavailable_analytics_is_one_component_not_health_503(tmp_path):
    app = _health_app(tmp_path, analytics=SimpleNamespace(state="unavailable"))
    runtime = app.extensions["admin_web_runtime"]
    assert runtime.state == "unavailable"
    assert runtime.query_service is None
    assert runtime.home_health_query_service is not None

    client = app.test_client(); login(client)
    response = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/home/health",
        base_url="https://localhost",
    )
    assert response.status_code == 200
    result = response.get_json()["result"]
    assert [item["status"] for item in result["components"]] == [
        "operational", "operational", "operational", "operational",
        "unavailable",
    ]
    assert result["components"][4]["reason_code"] == (
        "analytics_source_unavailable"
    )
    assert result["status"] == "degraded"

    legacy = client.get("/admin/api/v1/health", base_url="https://localhost")
    assert legacy.status_code == 503
    assert legacy.get_json()["result"] == {"status": "unavailable"}


def test_missing_normal_admin_source_does_not_block_home_health(tmp_path):
    app = _health_app(tmp_path, registry_source=False)
    runtime = app.extensions["admin_web_runtime"]
    assert runtime.state == "unavailable"
    assert runtime.query_service is None
    assert runtime.home_health_query_service is not None

    client = app.test_client(); login(client)
    response = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/home/health",
        base_url="https://localhost",
    )
    assert response.status_code == 200
    assert len(response.get_json()["result"]["components"]) == 5


def test_health_without_general_query_service_keeps_shared_gate_and_deadline(
    tmp_path,
):
    app = _health_app(
        tmp_path,
        registry_source=False,
        setting_updates={"web_admin_max_concurrent_queries": 1},
    )
    runtime = app.extensions["admin_web_runtime"]
    client = app.test_client(); login(client)
    url = f"/admin/api/v1/sites/{SITE_ID}/home/health"
    controls = runtime.query_execution_controls
    assert runtime.query_service is None
    assert runtime.home_health_query_service._execution_controls is controls

    assert controls._slots.acquire(blocking=False)
    busy = client.get(url, base_url="https://localhost")
    controls._slots.release()
    assert busy.status_code == 429
    assert busy.get_json()["error"]["code"] == "concurrency_limit"
    assert busy.headers["Retry-After"] == "1"

    received = []

    def expired(_site_id, *, deadline):
        received.append(deadline)
        raise AnalyticsQueryDeadlineExceeded("expired")

    original = runtime.home_health_query_service._home_health
    runtime.home_health_query_service._home_health = SimpleNamespace(
        evaluate=expired
    )
    deadline = client.get(url, base_url="https://localhost")
    runtime.home_health_query_service._home_health = original
    assert deadline.status_code == 503
    assert deadline.get_json()["error"]["code"] == "query_deadline"
    assert len(received) == 1 and isinstance(received[0], QueryDeadline)
    assert controls._slots.acquire(blocking=False)
    controls._slots.release()


def test_missing_health_query_composition_remains_whole_feature_503(
    health_app,
):
    runtime = health_app.extensions["admin_web_runtime"]
    runtime.home_health_query_service = None
    client = health_app.test_client(); login(client)
    response = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/home/health",
        base_url="https://localhost",
    )
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "source_unavailable"


def test_health_route_uses_shared_query_slot_and_deadline_mapping(health_app):
    runtime = health_app.extensions["admin_web_runtime"]
    client = health_app.test_client(); login(client)
    url = f"/admin/api/v1/sites/{SITE_ID}/home/health"
    runtime.query_service._slots = threading.BoundedSemaphore(1)

    assert runtime.query_service._slots.acquire(blocking=False)
    busy = client.get(url, base_url="https://localhost")
    runtime.query_service._slots.release()
    assert busy.status_code == 429
    assert busy.get_json()["error"]["code"] == "concurrency_limit"
    assert busy.headers["Retry-After"] == "1"

    health_queries = runtime.home_health_query_service
    original = health_queries._home_health
    health_queries._home_health = SimpleNamespace(
        evaluate=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AnalyticsQueryDeadlineExceeded("expired")
        )
    )
    deadline = client.get(url, base_url="https://localhost")
    assert deadline.status_code == 503
    assert deadline.get_json()["error"]["code"] == "query_deadline"
    assert runtime.query_service._slots.acquire(blocking=False)
    runtime.query_service._slots.release()

    health_queries._home_health = SimpleNamespace(
        evaluate=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            OSError("private path")
        )
    )
    unavailable = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/home/health",
        base_url="https://localhost",
    )
    assert unavailable.status_code == 503
    assert unavailable.get_json()["error"]["code"] == "source_unavailable"
    assert runtime.query_service._slots.acquire(blocking=False)
    runtime.query_service._slots.release()
    health_queries._home_health = original


def test_health_occupies_shared_slot_and_passes_one_deadline(health_app):
    runtime = health_app.extensions["admin_web_runtime"]
    query_service = runtime.query_service
    health_queries = runtime.home_health_query_service
    assert query_service._execution_controls is runtime.query_execution_controls
    assert health_queries._execution_controls is runtime.query_execution_controls
    original = health_queries._home_health
    entered = threading.Event()
    release = threading.Event()
    captured = []

    class BlockingHealth:
        def evaluate(self, site_id, *, deadline):
            captured.append(deadline)
            entered.set()
            assert release.wait(2)
            return original.evaluate(site_id, deadline=deadline)

    health_queries._home_health = BlockingHealth()
    query_service._slots = threading.BoundedSemaphore(1)
    principal = AdminPrincipal("operator")
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(health_queries.home_health, principal, SITE_ID)
        assert entered.wait(1)
        with pytest.raises(AdminQueryBusy):
            query_service.current_client_summary(principal, SITE_ID)
        release.set()
        assert future.result().result["health_version"] == 1
    assert len(captured) == 1
    assert isinstance(captured[0], QueryDeadline)
    assert query_service._slots.acquire(blocking=False)
    query_service._slots.release()
    health_queries._home_health = original


def test_health_query_creates_exactly_one_shared_deadline(
    health_app, monkeypatch
):
    runtime = health_app.extensions["admin_web_runtime"]
    health_queries = runtime.home_health_query_service
    original_source = health_queries._home_health
    original_after = QueryDeadline.after
    created = []
    received = []

    def after(cls, seconds, **kwargs):
        deadline = original_after(seconds, **kwargs)
        created.append(deadline)
        return deadline

    class CapturingHealth:
        def evaluate(self, site_id, *, deadline):
            received.append(deadline)
            return original_source.evaluate(site_id, deadline=deadline)

    monkeypatch.setattr(QueryDeadline, "after", classmethod(after))
    health_queries._home_health = CapturingHealth()
    result = health_queries.home_health(AdminPrincipal("operator"), SITE_ID)
    assert result.result["health_version"] == 1
    assert len(created) == 1
    assert received == created
    health_queries._home_health = original_source


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
