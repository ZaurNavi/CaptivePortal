from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from app.admin_web import create_admin_web_runtime
from app.admin_web.config import admin_web_config_from_settings
from app.admin_web.home_activity_config import (
    HomeActivityConfigError,
    home_activity_config_from_settings,
)
from app.admin_web.query_service import (
    AdminQueryBusy,
    AdminQueryDeadline,
    AdminQueryResponse,
    AdminQueryUnavailable,
)

from .conftest import SITE_ID, enabled_settings, login


UTC = timezone.utc


def activity_settings(**overrides):
    values = enabled_settings(
        web_admin_home_live_enabled="true",
        web_admin_home_activity_enabled="true",
        web_admin_home_activity_site_context_json=json.dumps({
            SITE_ID: {
                "timezone": "Asia/Baku",
                "visits_coverage_from_utc": "2020-01-01T00:00:00.000Z",
                "traffic_coverage_from_utc": "2020-01-01T00:00:00.000Z",
            }
        }),
    )
    values.update(overrides)
    return values


def current_config():
    return SimpleNamespace(
        enabled=True,
        site_ids=(SITE_ID,),
        client_ssids=("Zefer_Parki",),
    )


def test_activity_config_uses_only_current_state_ssid_scope():
    values = activity_settings()
    config = home_activity_config_from_settings(
        values,
        admin_config=admin_web_config_from_settings(values),
        current_state_config=current_config(),
        now_utc=datetime(2026, 8, 25, tzinfo=UTC),
    )
    assert config.guest_ssids == ("Zefer_Parki",)
    assert config.site(SITE_ID).timezone == "Asia/Baku"
    assert not hasattr(config.site(SITE_ID), "guest_ssids")


def test_disabled_activity_ignores_broken_activity_only_configuration():
    values = activity_settings(
        web_admin_home_activity_enabled="false",
        web_admin_home_activity_site_context_json="not-json",
        web_admin_home_activity_refresh_seconds="broken",
        web_admin_home_activity_request_timeout_seconds="broken",
        web_admin_home_activity_traffic_fresh_max_age_seconds="broken",
        web_admin_home_activity_traffic_stale_max_age_seconds="broken",
    )
    config = home_activity_config_from_settings(
        values,
        admin_config=admin_web_config_from_settings(values),
        current_state_config=None,
    )
    assert config.enabled is False
    assert config.sites == {} and config.guest_ssids == ()
    assert (config.refresh_seconds, config.request_timeout_seconds) == (60, 20)


@pytest.mark.parametrize(
    "current",
    (
        SimpleNamespace(enabled=False, site_ids=(SITE_ID,), client_ssids=("Zefer_Parki",)),
        SimpleNamespace(enabled=True, site_ids=(), client_ssids=("Zefer_Parki",)),
        SimpleNamespace(enabled=True, site_ids=(SITE_ID,), client_ssids=()),
        SimpleNamespace(enabled=True, site_ids=("aaaaaaaaaaaaaaaaaaaaaaaa",), client_ssids=("Zefer_Parki",)),
    ),
)
def test_activity_scope_mismatch_is_rejected(current):
    values = activity_settings()
    with pytest.raises(HomeActivityConfigError):
        home_activity_config_from_settings(
            values,
            admin_config=admin_web_config_from_settings(values),
            current_state_config=current,
            now_utc=datetime(2026, 8, 25, tzinfo=UTC),
        )


def test_scope_mismatch_isolated_from_admin_and_has_safe_telemetry(
    tmp_path, caplog
):
    values = activity_settings()
    logger = logging.getLogger("activity-scope-mismatch")
    caplog.set_level(logging.ERROR, logger=logger.name)
    runtime = create_admin_web_runtime(
        values,
        SimpleNamespace(state="active", visit_service=object(), home_activity_service=object()),
        SimpleNamespace(repository=SimpleNamespace(config=SimpleNamespace(db_path=tmp_path / "registry.sqlite3"))),
        SimpleNamespace(repository=SimpleNamespace(db_path=tmp_path / "visits.sqlite3")),
        SimpleNamespace(_repository=SimpleNamespace(db_path=tmp_path / "observations.sqlite3")),
        logger,
        current_state_read_service=SimpleNamespace(
            config=SimpleNamespace(
                enabled=True,
                site_ids=("aaaaaaaaaaaaaaaaaaaaaaaa",),
                client_ssids=("Zefer_Parki",),
            )
        ),
    )
    assert runtime.state == "active"
    assert runtime.home_activity_state == "unavailable"
    record = next(
        item for item in caplog.records
        if item.getMessage() == "admin.home_activity_configuration_failed"
    )
    assert record.reason == "scope_mismatch"
    assert "Zefer_Parki" not in record.getMessage()


@pytest.mark.parametrize(
    "payload",
    (
        "not-json",
        "[]",
        json.dumps({SITE_ID: {"timezone": "UTC"}}),
        '{"%s":{"timezone":"UTC","visits_coverage_from_utc":null,'
        '"traffic_coverage_from_utc":null},"%s":{"timezone":"UTC",'
        '"visits_coverage_from_utc":null,"traffic_coverage_from_utc":null}}'
        % (SITE_ID, SITE_ID),
    ),
)
def test_invalid_activity_context_fails_only_activity(payload):
    values = activity_settings(
        web_admin_home_activity_site_context_json=payload
    )
    admin = admin_web_config_from_settings(values)
    assert admin.enabled is True
    with pytest.raises(HomeActivityConfigError):
        home_activity_config_from_settings(
            values,
            admin_config=admin,
            current_state_config=current_config(),
            now_utc=datetime(2026, 8, 25, tzinfo=UTC),
        )


@pytest.fixture
def activity_app(tmp_path):
    current = SimpleNamespace(config=current_config())
    analytics = SimpleNamespace(
        state="active",
        visit_service=object(),
        current_traffic_service=None,
        home_activity_service=object(),
    )
    runtime = create_admin_web_runtime(
        activity_settings(),
        analytics,
        SimpleNamespace(repository=SimpleNamespace(config=SimpleNamespace(db_path=tmp_path / "registry.sqlite3"))),
        SimpleNamespace(repository=SimpleNamespace(db_path=tmp_path / "visits.sqlite3")),
        SimpleNamespace(_repository=SimpleNamespace(db_path=tmp_path / "observations.sqlite3")),
        logging.getLogger("activity-test"),
        current_state_read_service=current,
    )
    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    app.register_blueprint(runtime.blueprint)
    app.extensions["admin_web_runtime"] = runtime
    return app


def test_range_preview_is_authenticated_and_does_not_use_query_service(activity_app):
    client = activity_app.test_client()
    login(client)
    service = activity_app.extensions["admin_web_runtime"].query_service
    service.home_activity = lambda *args, **kwargs: pytest.fail("source query called")
    response = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/home-activity/range-preview"
        "?from_date=2026-08-01&to_date=2026-08-05",
        base_url="https://localhost",
    )
    assert response.status_code == 200
    result = response.get_json()["result"]
    assert result["timezone"] == "Asia/Baku"
    assert result["resolved"]["from_utc"] == "2026-07-31T20:00:00.000Z"
    assert result["resolved"]["to_utc"] == "2026-08-05T20:00:00.000Z"
    duplicate = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/home-activity/range-preview"
        "?from_date=2026-08-01&from_date=2026-08-02&to_date=2026-08-05",
        base_url="https://localhost",
    )
    invalid = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/home-activity/range-preview"
        "?from_date=not-a-date&to_date=2026-08-05",
        base_url="https://localhost",
    )
    assert duplicate.status_code == invalid.status_code == 400


def test_activity_query_parameters_are_strict_after_security_gates(activity_app):
    client = activity_app.test_client()
    login(client)
    base = f"/admin/api/v1/sites/{SITE_ID}/home-activity"
    assert client.get(base + "/today?extra=1", base_url="https://localhost").status_code == 400
    assert client.get(base + "/selected", base_url="https://localhost").status_code == 400
    assert client.get(base + "/selected?period=last_24h&period=last_7d", base_url="https://localhost").status_code == 400


def test_activity_security_and_feature_gate_order(activity_app):
    client = activity_app.test_client()
    base = f"/admin/api/v1/sites/{SITE_ID}/home-activity/today"
    assert client.get(base, base_url="https://localhost").status_code == 401
    login(client)
    assert client.get(
        "/admin/api/v1/sites/not-a-site/home-activity/today",
        base_url="https://localhost",
    ).status_code == 400
    assert client.get(
        "/admin/api/v1/sites/aaaaaaaaaaaaaaaaaaaaaaaa/home-activity/today",
        base_url="https://localhost",
    ).status_code == 403
    runtime = activity_app.extensions["admin_web_runtime"]
    runtime.home_activity_state = "disabled"
    disabled = client.get(base, base_url="https://localhost")
    assert disabled.status_code == 404
    assert disabled.get_json()["error"]["code"] == "not_found"


@pytest.mark.parametrize(
    ("failure", "status", "code", "retry_after"),
    (
        (AdminQueryBusy(), 429, "concurrency_limit", "1"),
        (AdminQueryDeadline(), 503, "query_deadline", None),
        (AdminQueryUnavailable(), 503, "source_unavailable", None),
    ),
)
def test_activity_controlled_query_failures(
    activity_app, failure, status, code, retry_after
):
    client = activity_app.test_client()
    login(client)
    service = activity_app.extensions["admin_web_runtime"].query_service

    def fail(*_args, **_kwargs):
        raise failure

    service.home_activity = fail
    response = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/home-activity/today",
        base_url="https://localhost",
    )
    assert response.status_code == status
    assert response.get_json()["error"] == {
        "code": code,
        "message": "The request could not be completed.",
    }
    assert response.headers.get("Retry-After") == retry_after


def test_today_and_selected_call_independent_query_operations(activity_app):
    client = activity_app.test_client()
    login(client)
    service = activity_app.extensions["admin_web_runtime"].query_service
    seen = []

    def fake(_principal, _site, *, resolved_range, evaluated_at, next_site_midnight_utc=None):
        seen.append((resolved_range.kind, evaluated_at, next_site_midnight_utc))
        return AdminQueryResponse({"kind": resolved_range.kind})

    service.home_activity = fake
    base = f"/admin/api/v1/sites/{SITE_ID}/home-activity"
    today = client.get(base + "/today", base_url="https://localhost")
    selected = client.get(base + "/selected?period=last_24h", base_url="https://localhost")
    assert today.status_code == selected.status_code == 200
    assert [item[0] for item in seen] == ["today", "last_24h"]
    assert seen[0][2] is not None and seen[1][2] is None


def test_selected_failure_does_not_change_independent_today_result(activity_app):
    client = activity_app.test_client()
    login(client)
    service = activity_app.extensions["admin_web_runtime"].query_service
    calls = []

    def fake(_principal, _site, *, resolved_range, **_kwargs):
        calls.append(resolved_range.kind)
        if resolved_range.kind == "last_30d":
            raise AdminQueryDeadline()
        return AdminQueryResponse({"marker": "today-authoritative"})

    service.home_activity = fake
    base = f"/admin/api/v1/sites/{SITE_ID}/home-activity"
    today = client.get(base + "/today", base_url="https://localhost")
    selected = client.get(
        base + "/selected?period=last_30d", base_url="https://localhost"
    )
    assert today.status_code == 200
    assert today.get_json()["result"] == {"marker": "today-authoritative"}
    assert selected.status_code == 503
    assert selected.get_json()["error"]["code"] == "query_deadline"
    assert calls == ["today", "last_30d"]


def test_selected_telemetry_has_safe_duration_and_coverage_categories(
    activity_app, caplog
):
    client = activity_app.test_client()
    login(client)
    service = activity_app.extensions["admin_web_runtime"].query_service
    service.home_activity = lambda *_args, **_kwargs: AdminQueryResponse({
        "authorized_visits": {"status": "complete", "coverage": {"status": "complete"}},
        "traffic": {"status": "partial", "coverage": {"status": "partial"}},
    })
    caplog.set_level(logging.INFO, logger="activity-test")
    response = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/home-activity/selected"
        "?period=custom&from_date=2025-01-01&to_date=2026-01-01",
        base_url="https://localhost",
    )
    assert response.status_code == 200
    record = next(
        item for item in caplog.records
        if item.getMessage() == "admin.home_activity_selected_query_completed"
    )
    assert record.range_duration_category == "over_365d"
    assert record.visits_coverage_status == "complete"
    assert record.traffic_coverage_status == "partial"
    assert record.period == "custom"
    rendered = repr(record.__dict__)
    assert "2025-01-01" not in rendered and "2026-01-01" not in rendered


def test_activity_response_size_cap_is_enforced(activity_app):
    client = activity_app.test_client()
    login(client)
    service = activity_app.extensions["admin_web_runtime"].query_service
    service.home_activity = lambda *_args, **_kwargs: AdminQueryResponse(
        {"oversized": "x" * 1_100_000}
    )
    response = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/home-activity/today",
        base_url="https://localhost",
    )
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "response_too_large"


def test_activity_page_contains_no_secret_or_browser_storage_contract(activity_app):
    client = activity_app.test_client()
    login(client)
    response = client.get(
        f"/admin/sites/{SITE_ID}/", base_url="https://localhost"
    )
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert "Visits and Traffic" in text
    assert "WEB_ADMIN_HOME_ACTIVITY_SITE_CONTEXT_JSON" not in text
    assert "localStorage" not in text
    assert "sessionStorage" not in text


@pytest.mark.parametrize(
    ("traffic_enabled", "activity_enabled"),
    ((False, False), (True, False), (False, True), (True, True)),
)
def test_all_home_traffic_and_activity_feature_combinations_render(
    tmp_path, traffic_enabled, activity_enabled
):
    values = activity_settings(
        web_admin_home_traffic_enabled=str(traffic_enabled).lower(),
        web_admin_home_activity_enabled=str(activity_enabled).lower(),
        web_admin_home_activity_site_context_json=(
            activity_settings()["web_admin_home_activity_site_context_json"]
            if activity_enabled else "broken-but-disabled"
        ),
    )
    current = SimpleNamespace(config=current_config())
    analytics = SimpleNamespace(
        state="active", visit_service=object(), current_traffic_service=None,
        home_activity_service=object(),
    )
    runtime = create_admin_web_runtime(
        values, analytics,
        SimpleNamespace(repository=SimpleNamespace(config=SimpleNamespace(db_path=tmp_path / "registry.sqlite3"))),
        SimpleNamespace(repository=SimpleNamespace(db_path=tmp_path / "visits.sqlite3")),
        SimpleNamespace(_repository=SimpleNamespace(db_path=tmp_path / "observations.sqlite3")),
        logging.getLogger("activity-combination-test"),
        current_state_read_service=current,
    )
    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    app.register_blueprint(runtime.blueprint)
    client = app.test_client()
    login(client)
    text = client.get(
        f"/admin/sites/{SITE_ID}/", base_url="https://localhost"
    ).get_data(as_text=True)
    assert f'data-home-traffic-enabled="{str(traffic_enabled).lower()}"' in text
    assert f'data-home-activity-enabled="{str(activity_enabled).lower()}"' in text
    assert ("Traffic Now" in text) is traffic_enabled
    assert ("Visits and Traffic" in text) is activity_enabled
