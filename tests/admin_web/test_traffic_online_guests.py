from __future__ import annotations

import logging
from dataclasses import replace
from types import SimpleNamespace

import pytest
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from app.admin_web import create_admin_web_runtime
from app.admin_web.config import AdminWebConfigError, admin_web_config_from_settings
from app.admin_web.current_guest_traffic_serialization import (
    CurrentGuestTrafficSerializationError,
    serialize_current_guest_traffic,
)
from app.admin_web.policy import AdminAccessPolicy
from app.analytics import (
    CurrentGuestTrafficItem,
    CurrentGuestTrafficPage,
    CurrentGuestTrafficResult,
    CurrentGuestTrafficSourceUnavailable,
    CurrentGuestTrafficValidationError,
)

from .conftest import SITE_ID, enabled_settings, login


OTHER_SITE = "f" * 24
MAC = "AA:BB:CC:DD:EE:01"


def _item(**overrides):
    values = dict(
        client_mac=MAC,
        name="Guest phone",
        ssid="Zefer_Parki",
        ap_mac="AA:BB:CC:DD:EE:10",
        download_mbps=1.25,
        upload_mbps=0.0,
        total_mbps=1.25,
        source_progress_status="advanced",
        connection_continuity_status="proven",
        continuity_basis="uptime_progress",
        download_reason="valid",
        upload_reason="valid",
        total_reason="valid",
        rate_status="valid",
    )
    values.update(overrides)
    return CurrentGuestTrafficItem(**values)


def _result(*, items=None, status="ok", cursor=None, **overrides):
    items = (_item(),) if items is None else tuple(items)
    values = dict(
        metric_version="network_traffic_online_guest_current_rate.v1",
        population_method="fresh_complete_current_state_authorized_guest_scope.v1",
        rate_method="current_connection_counter_delta_interval_average.v1",
        baseline_method="nearest_previous_complete_same_site_scope_cycle.v1",
        continuity_method="omada_controller_connection_progress_v1",
        connection_boundary_observation="sampled_current_state_evidence_v1",
        unit="Mbps",
        site_id=SITE_ID,
        evaluated_at_utc="2026-09-02T10:00:00.000Z",
        current_cycle_id="11111111-1111-4111-8111-111111111111",
        baseline_cycle_id="22222222-2222-4222-8222-222222222222",
        source_scope_hash="a" * 64,
        current_capture_started_at="2026-09-02T09:59:50.000Z",
        baseline_capture_started_at="2026-09-02T09:58:50.000Z",
        elapsed_seconds=60.0,
        status=status,
        source_health_status="healthy",
        source_health_reason="within_freshness_window",
        rate_evidence_status="complete",
        population_complete=True,
        scoped_client_row_count=len(items),
        known_authorized_count=len(items),
        unknown_auth_count=0,
        population_count=len(items),
        supported_max_population=10_000,
        rate_valid_count=len(items),
        rate_partial_count=0,
        rate_unavailable_count=0,
        items=items,
        page=CurrentGuestTrafficPage(50, len(items), cursor, "total_rate_desc"),
    )
    values.update(overrides)
    return CurrentGuestTrafficResult(**values)


class GuestSource:
    def __init__(self, value=None, error=None):
        self.value = value or _result()
        self.error = error
        self.calls = []

    def get_current_guest_traffic(self, site_id, **kwargs):
        self.calls.append((site_id, kwargs))
        if self.error is not None:
            raise self.error
        return replace(
            self.value,
            page=replace(self.value.page, limit=kwargs["limit"]),
        )


def _app(tmp_path, source=None, *, enabled=True, monkeypatch=None):
    if enabled and monkeypatch is not None:
        monkeypatch.setattr(
            "app.analytics.current_guest_traffic.CurrentGuestTrafficReadService",
            lambda _current: source,
        )
    runtime = create_admin_web_runtime(
        enabled_settings(
            web_admin_traffic_enabled="true",
            web_admin_traffic_online_guests_enabled=str(enabled).lower(),
        ),
        SimpleNamespace(state="active", visit_service=object()),
        SimpleNamespace(repository=SimpleNamespace(
            config=SimpleNamespace(db_path=tmp_path / "registry.sqlite3")
        )),
        SimpleNamespace(repository=SimpleNamespace(db_path=tmp_path / "visits.sqlite3")),
        SimpleNamespace(_repository=SimpleNamespace(db_path=tmp_path / "observations.sqlite3")),
        logging.getLogger("traffic-online-guests-test"),
        current_state_read_service=object(),
    )
    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    app.register_blueprint(runtime.blueprint)
    app.extensions["admin_web_runtime"] = runtime
    return app


def _url(site=SITE_ID, query=""):
    suffix = "" if not query else "?" + query
    return f"/admin/api/v1/sites/{site}/traffic/online-guests/current{suffix}"


def test_flag_defaults_false_and_requires_only_admin_traffic():
    assert admin_web_config_from_settings({}).traffic_online_guests_enabled is False
    with pytest.raises(AdminWebConfigError, match="ONLINE_GUESTS_ENABLED requires"):
        admin_web_config_from_settings(enabled_settings(
            web_admin_traffic_enabled="false",
            web_admin_traffic_online_guests_enabled="true",
        ))
    config = admin_web_config_from_settings(enabled_settings(
        web_admin_traffic_enabled="true",
        web_admin_traffic_history_enabled="false",
        web_admin_traffic_online_guests_enabled="true",
    ))
    assert config.traffic_online_guests_enabled is True


def test_runtime_composes_exactly_one_optional_product_and_isolates_failure(tmp_path, monkeypatch):
    source = GuestSource()
    calls = []
    monkeypatch.setattr(
        "app.analytics.current_guest_traffic.CurrentGuestTrafficReadService",
        lambda current: calls.append(current) or source,
    )
    app = _app(tmp_path, source, monkeypatch=None)
    runtime = app.extensions["admin_web_runtime"]
    assert len(calls) == 1
    assert runtime.traffic_online_guests_state == "active"
    assert runtime.traffic_online_guests_service is source
    assert runtime.query_service._current_guest_traffic is source

    monkeypatch.setattr(
        "app.analytics.current_guest_traffic.CurrentGuestTrafficReadService",
        lambda _current: (_ for _ in ()).throw(TypeError("bad dependency")),
    )
    broken = _app(tmp_path, source, monkeypatch=None)
    broken_runtime = broken.extensions["admin_web_runtime"]
    assert broken_runtime.state == "active"
    assert broken_runtime.traffic_online_guests_state == "unavailable"
    client = broken.test_client()
    assert login(client).status_code == 302
    response = client.get(_url(), base_url="https://localhost")
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "source_unavailable"


def test_route_security_feature_and_query_order(tmp_path, monkeypatch):
    source = GuestSource()
    disabled = _app(tmp_path, source, enabled=False).test_client()
    duplicate = _url(query="limit=50&limit=50")
    assert disabled.get(duplicate, base_url="https://localhost").status_code == 401
    assert login(disabled).status_code == 302
    assert disabled.get(duplicate, base_url="https://localhost").status_code == 404
    assert source.calls == []

    app = _app(tmp_path, source, monkeypatch=monkeypatch)
    client = app.test_client()
    assert login(client).status_code == 302
    assert client.get(_url(OTHER_SITE, "limit=50&limit=50"), base_url="https://localhost").status_code == 403
    assert client.get(duplicate, base_url="https://localhost").status_code == 400
    assert source.calls == []


@pytest.mark.parametrize("query", ["bad=1", "limit=50&limit=50", "cursor=x&cursor=x", "limit=0", "limit=201", "limit=050"])
def test_route_rejects_noncanonical_query_before_source(tmp_path, monkeypatch, query):
    source = GuestSource()
    client = _app(tmp_path, source, monkeypatch=monkeypatch).test_client()
    assert login(client).status_code == 302
    response = client.get(_url(query=query), base_url="https://localhost")
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_request"
    assert source.calls == []


@pytest.mark.parametrize("query,limit,cursor", [("", 50, None), ("limit=200", 200, None), ("limit=50&cursor=opaque", 50, "opaque")])
def test_route_uses_product_bounds_and_one_read(tmp_path, monkeypatch, query, limit, cursor):
    source = GuestSource()
    client = _app(tmp_path, source, monkeypatch=monkeypatch).test_client()
    assert login(client).status_code == 302
    response = client.get(_url(query=query), base_url="https://localhost")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["page"]["limit"] == limit
    assert source.calls == [(SITE_ID, {"limit": limit, "cursor": cursor})]
    assert "source_scope_hash" not in payload["result"]
    assert "controller_traffic_down" not in response.get_data(as_text=True)


def test_cursor_expired_has_explicit_public_error(tmp_path, monkeypatch):
    source = GuestSource(error=CurrentGuestTrafficValidationError("cursor_expired"))
    client = _app(tmp_path, source, monkeypatch=monkeypatch).test_client()
    assert login(client).status_code == 302
    response = client.get(_url(query="cursor=opaque"), base_url="https://localhost")
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "cursor_expired"


def test_source_failure_is_product_local_503(tmp_path, monkeypatch):
    source = GuestSource(error=CurrentGuestTrafficSourceUnavailable("private"))
    client = _app(tmp_path, source, monkeypatch=monkeypatch).test_client()
    assert login(client).status_code == 302
    response = client.get(_url(), base_url="https://localhost")
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "source_unavailable"
    assert "private" not in response.get_data(as_text=True)


def test_shared_deadline_wraps_exactly_one_read_without_deadline_argument(tmp_path, monkeypatch):
    source = GuestSource()
    app = _app(tmp_path, source, monkeypatch=monkeypatch)
    checks = []
    class Deadline:
        def require_remaining(self):
            checks.append("check")
    class Controls:
        def run(self, operation):
            return operation(Deadline())
    app.extensions["admin_web_runtime"].query_service._execution_controls = Controls()
    client = app.test_client()
    assert login(client).status_code == 302
    assert client.get(_url(), base_url="https://localhost").status_code == 200
    assert checks == ["check", "check"]
    assert len(source.calls) == 1
    assert "deadline" not in source.calls[0][1]


def test_capability_is_rechecked_by_route_and_query(tmp_path, monkeypatch):
    source = GuestSource()
    calls = []
    original = AdminAccessPolicy.authorize
    def record(self, principal, capability, site):
        calls.append((capability, site))
        return original(self, principal, capability, site)
    monkeypatch.setattr(AdminAccessPolicy, "authorize", record)
    client = _app(tmp_path, source, monkeypatch=monkeypatch).test_client()
    assert login(client).status_code == 302
    assert client.get(_url(), base_url="https://localhost").status_code == 200
    assert calls[-2:] == [("admin.read.devices", SITE_ID), ("admin.read.devices", SITE_ID)]


def test_serializer_preserves_zero_null_and_exact_page():
    partial = _item(
        download_mbps=0.0, upload_mbps=None, total_mbps=None,
        upload_reason="counter_missing", total_reason="counter_missing",
        rate_status="partial",
    )
    value = _result(
        items=(partial,), status="partial", rate_evidence_status="partial",
        rate_valid_count=0, rate_partial_count=1, rate_unavailable_count=0,
    )
    result, page = serialize_current_guest_traffic(value, SITE_ID)
    assert result["items"][0]["download_mbps"] == 0.0
    assert result["items"][0]["upload_mbps"] is None
    assert page == {"limit": 50, "returned_count": 1, "next_cursor": None, "sort": "total_rate_desc"}


@pytest.mark.parametrize(
    "value,expected_status",
    [
        (_result(items=(), baseline_cycle_id=None, baseline_capture_started_at=None, elapsed_seconds=None, rate_evidence_status="not_applicable", scoped_client_row_count=0, known_authorized_count=0, population_count=0, rate_valid_count=0), "ok"),
        (_result(status="partial", source_health_status="degraded", source_health_reason="newer_degraded_attempt"), "partial"),
        (_result(status="partial", scoped_client_row_count=2, unknown_auth_count=1, population_complete=False), "partial"),
        (_result(items=(_item(download_mbps=1.0, upload_mbps=None, total_mbps=None, upload_reason="counter_missing", total_reason="counter_missing", rate_status="partial"),), status="partial", rate_evidence_status="partial", rate_valid_count=0, rate_partial_count=1), "partial"),
        (_result(items=(), status="partial", source_health_status="degraded", source_health_reason="newer_degraded_attempt", baseline_cycle_id=None, baseline_capture_started_at=None, elapsed_seconds=None, rate_evidence_status="not_applicable", scoped_client_row_count=0, known_authorized_count=0, population_count=0, rate_valid_count=0), "partial"),
        (_result(items=(_item(download_mbps=None, upload_mbps=None, total_mbps=None, download_reason="no_baseline", upload_reason="no_baseline", total_reason="no_baseline", source_progress_status="unproven", connection_continuity_status="unproven", continuity_basis="none", rate_status="unavailable"),), status="insufficient_data", baseline_cycle_id=None, baseline_capture_started_at=None, elapsed_seconds=None, rate_evidence_status="insufficient_data", rate_valid_count=0, rate_unavailable_count=1), "insufficient_data"),
    ],
)
def test_serializer_accepts_asserted_root_status_matrix(value, expected_status):
    result, _page = serialize_current_guest_traffic(value, SITE_ID)
    assert result["status"] == expected_status


@pytest.mark.parametrize(
    "item",
    [
        _item(download_mbps=0.0, upload_mbps=0.0, total_mbps=0.0),
        _item(download_mbps=1.0, upload_mbps=None, total_mbps=None, upload_reason="counter_missing", total_reason="counter_missing", rate_status="partial"),
        _item(download_mbps=None, upload_mbps=1.0, total_mbps=None, download_reason="counter_reset", total_reason="counter_reset", rate_status="partial"),
        _item(download_mbps=None, upload_mbps=None, total_mbps=None, download_reason="source_frozen", upload_reason="source_frozen", total_reason="source_frozen", source_progress_status="frozen", connection_continuity_status="unproven", continuity_basis="none", rate_status="unavailable"),
    ],
)
def test_serializer_accepts_frozen_item_rate_shapes(item):
    rate_status = "complete" if item.rate_status == "valid" else "partial" if item.rate_status == "partial" else "insufficient_data"
    value = _result(
        items=(item,),
        status="ok" if item.rate_status == "valid" else "partial" if item.rate_status == "partial" else "insufficient_data",
        rate_evidence_status=rate_status,
        rate_valid_count=1 if item.rate_status == "valid" else 0,
        rate_partial_count=1 if item.rate_status == "partial" else 0,
        rate_unavailable_count=1 if item.rate_status == "unavailable" else 0,
    )
    result, _page = serialize_current_guest_traffic(value, SITE_ID)
    assert result["items"][0]["rate_status"] == item.rate_status


@pytest.mark.parametrize(
    "health,reason",
    [
        ("healthy", "within_freshness_window"),
        ("degraded", "newer_degraded_attempt"),
        ("stale", "older_than_freshness_window"),
        ("unavailable", "older_than_unavailable_threshold"),
        ("unavailable", "clock_anomaly"),
        ("unavailable", "no_complete_snapshot"),
    ],
)
def test_serializer_accepts_only_frozen_source_health_pairs(health, reason):
    if health == "healthy":
        value = _result()
    elif health == "degraded":
        value = _result(status="partial", source_health_status=health, source_health_reason=reason)
    elif health == "stale":
        value = _result(status="stale", items=(), baseline_cycle_id=None, baseline_capture_started_at=None, elapsed_seconds=None, source_health_status=health, source_health_reason=reason, rate_evidence_status="insufficient_data", population_complete=False, scoped_client_row_count=None, known_authorized_count=None, unknown_auth_count=None, population_count=None, rate_valid_count=None, rate_partial_count=None, rate_unavailable_count=None, page=CurrentGuestTrafficPage(50, 0, None, "total_rate_desc"))
    else:
        current = None if reason == "no_complete_snapshot" else "current"
        value = _result(status="unavailable", items=(), current_cycle_id=current, source_scope_hash=None if current is None else "a" * 64, current_capture_started_at=None if current is None else "2026-09-02T09:59:50.000Z", baseline_cycle_id=None, baseline_capture_started_at=None, elapsed_seconds=None, source_health_status=health, source_health_reason=reason, rate_evidence_status="insufficient_data", population_complete=False, scoped_client_row_count=None, known_authorized_count=None, unknown_auth_count=None, population_count=None, rate_valid_count=None, rate_partial_count=None, rate_unavailable_count=None, page=CurrentGuestTrafficPage(50, 0, None, "total_rate_desc"))
    assert serialize_current_guest_traffic(value, SITE_ID)[0]["source_health_reason"] == reason


@pytest.mark.parametrize(
    "value",
    [
        _result(status="stale", items=(), current_cycle_id="x", baseline_cycle_id=None, baseline_capture_started_at=None, elapsed_seconds=None, source_health_status="stale", source_health_reason="older_than_freshness_window", rate_evidence_status="insufficient_data", population_complete=False, scoped_client_row_count=None, known_authorized_count=None, unknown_auth_count=None, population_count=None, rate_valid_count=None, rate_partial_count=None, rate_unavailable_count=None, page=CurrentGuestTrafficPage(50, 0, None, "total_rate_desc")),
        _result(status="unavailable", items=(), current_cycle_id=None, baseline_cycle_id=None, source_scope_hash=None, current_capture_started_at=None, baseline_capture_started_at=None, elapsed_seconds=None, source_health_status="unavailable", source_health_reason="no_complete_snapshot", rate_evidence_status="insufficient_data", population_complete=False, scoped_client_row_count=None, known_authorized_count=None, unknown_auth_count=None, population_count=None, rate_valid_count=None, rate_partial_count=None, rate_unavailable_count=None, page=CurrentGuestTrafficPage(50, 0, None, "total_rate_desc")),
        _result(status="unsupported_population", items=(), baseline_cycle_id=None, baseline_capture_started_at=None, elapsed_seconds=None, rate_evidence_status="insufficient_data", population_complete=False, scoped_client_row_count=10001, known_authorized_count=10001, unknown_auth_count=0, population_count=10001, rate_valid_count=None, rate_partial_count=None, rate_unavailable_count=None, page=CurrentGuestTrafficPage(50, 0, None, "total_rate_desc")),
    ],
)
def test_serializer_accepts_terminal_status_matrix(value):
    result, page = serialize_current_guest_traffic(value, SITE_ID)
    assert result["items"] == [] and page["next_cursor"] is None


def test_serializer_fails_closed_on_unknown_reason_and_impossible_shape():
    with pytest.raises(CurrentGuestTrafficSerializationError):
        serialize_current_guest_traffic(_result(items=(_item(download_reason="new_reason"),)), SITE_ID)
    with pytest.raises(CurrentGuestTrafficSerializationError):
        serialize_current_guest_traffic(_result(population_count=2), SITE_ID)


@pytest.mark.parametrize(
    "item",
    [
        _item(download_reason="counter_missing"),
        _item(upload_reason="counter_reset"),
        _item(total_mbps=None, rate_status="partial"),
        _item(source_progress_status="frozen"),
        _item(connection_continuity_status="reset"),
        _item(continuity_basis="none"),
    ],
)
def test_serializer_rejects_impossible_frozen_read_item_combinations(item):
    with pytest.raises(CurrentGuestTrafficSerializationError):
        serialize_current_guest_traffic(_result(items=(item,)), SITE_ID)


def test_panel_absent_when_disabled_and_visible_when_product_unavailable(tmp_path, monkeypatch):
    client = _app(tmp_path, GuestSource(), enabled=False).test_client()
    assert login(client).status_code == 302
    body = client.get(f"/admin/sites/{SITE_ID}/traffic", base_url="https://localhost").get_data(as_text=True)
    assert 'id="traffic-online-guests-panel"' not in body

    monkeypatch.setattr(
        "app.analytics.current_guest_traffic.CurrentGuestTrafficReadService",
        lambda _current: (_ for _ in ()).throw(TypeError("bad")),
    )
    unavailable = _app(tmp_path, GuestSource(), monkeypatch=None).test_client()
    assert login(unavailable).status_code == 302
    body = unavailable.get(f"/admin/sites/{SITE_ID}/traffic", base_url="https://localhost").get_data(as_text=True)
    assert 'id="traffic-online-guests-panel"' in body
    assert 'data-traffic-online-guests-enabled="false"' in body
    assert "product read service could not be composed" in body


def test_active_panel_contract_and_200_item_payload_budget(tmp_path, monkeypatch):
    def mac(index):
        return f"02:00:00:{(index >> 8) & 255:02X}:{index & 255:02X}:01"
    items = tuple(replace(_item(), client_mac=mac(index), name=f"Guest {index}") for index in range(200))
    source = GuestSource(_result(
        items=items,
        scoped_client_row_count=200,
        known_authorized_count=200,
        population_count=200,
        rate_valid_count=200,
        page=CurrentGuestTrafficPage(200, 200, None, "total_rate_desc"),
    ))
    client = _app(tmp_path, source, monkeypatch=monkeypatch).test_client()
    assert login(client).status_code == 302
    page = client.get(f"/admin/sites/{SITE_ID}/traffic", base_url="https://localhost")
    body = page.get_data(as_text=True)
    assert 'id="traffic-online-guests-panel"' in body
    assert 'data-traffic-online-guests-enabled="true"' in body
    response = client.get(_url(query="limit=200"), base_url="https://localhost")
    assert response.status_code == 200
    assert len(response.data) <= 256 * 1024
    assert len(response.get_json()["result"]["items"]) == 200
