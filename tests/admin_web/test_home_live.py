from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
import threading
import sqlite3

import pytest
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from app.admin_web import create_admin_web_runtime
from app.admin_web.config import AdminWebConfigError, admin_web_config_from_settings
from app.admin_web.current_state_serialization import (
    serialize_ap_page,
    serialize_ap_summary,
    serialize_client_page,
    serialize_client_summary,
)
from app.admin_web.models import AdminPrincipal
from app.admin_web.policy import AdminAccessPolicy
from app.admin_web.query_service import (
    AdminQueryService,
    AdminQueryBusy,
    AdminQueryDeadline,
    AdminQueryForbidden,
    AdminQueryUnavailable,
    AdminQueryValidationError,
)
from app.current_state import (
    CurrentApPage,
    CurrentApState,
    CurrentApSummary,
    CurrentClientPage,
    CurrentClientState,
    CurrentClientSummary,
    CurrentSnapshotMeta,
    CurrentStateValidationError,
)

from .conftest import SITE_ID, enabled_settings, login


CYCLE = "10000000-0000-4000-8000-000000000001"
SCOPE_HASH = "a" * 64
NOW = "2026-08-23T10:00:00.000Z"


def snapshot(kind="client", *, status="fresh", cycle_id=CYCLE):
    scope = (
        {"scope_type": "client_ssid_allowlist", "site_id": SITE_ID, "ssids": ["OwnerWiFi"]}
        if kind == "client"
        else {"scope_type": "site_ap_inventory", "site_id": SITE_ID}
    )
    return CurrentSnapshotMeta(
        cycle_id, SITE_ID, kind, NOW, NOW, NOW, 1.0, status,
        "within_freshness_window" if status != "unavailable" else "no_complete_snapshot",
        status != "unavailable", 1 if cycle_id else None,
        SCOPE_HASH if cycle_id else None, scope if cycle_id else None,
        "success", NOW, None,
    )


def client_summary(*, status="fresh"):
    meta = snapshot(status=status, cycle_id=None if status == "unavailable" else CYCLE)
    if status == "unavailable":
        return CurrentClientSummary(meta, None, None, None, None, None, None, None, ())
    return CurrentClientSummary(meta, 2, 1, 1, 0, 0, 0, 0, (SimpleNamespace(ap_mac="11:22:33:44:55:66", client_count=2),))


def client_item(**changes):
    item = CurrentClientState(
        CYCLE, SITE_ID, NOW, "AA:BB:CC:DD:EE:01", "Phone", None, None,
        "192.0.2.10", "OwnerWiFi", "AP-1", "11:22:33:44:55:66", None,
        "5GHz", None, -60, 30, 10, None, "authorized", 4, 5, 9, True, True,
    )
    return replace(item, **changes)


def ap_summary():
    return CurrentApSummary(snapshot("ap"), 3, 1, 1, 0, 1)


def ap_item(status="online"):
    return CurrentApState(CYCLE, SITE_ID, NOW, "11:22:33:44:55:66", "AP-1", None, None, None, None, status, None, None, None)


class CurrentSource:
    def __init__(self):
        self.calls = []

    def get_current_client_summary(self, site):
        self.calls.append(("client-summary", site))
        return client_summary()

    def list_current_clients(self, site, **kwargs):
        self.calls.append(("clients", site, kwargs))
        selected_ssid = kwargs.get("ssid") or "OwnerWiFi"
        selected_snapshot = replace(
            snapshot(),
            source_scope={
                "scope_type": "client_ssid_allowlist",
                "site_id": SITE_ID,
                "ssids": [selected_ssid],
            },
        )
        return CurrentClientPage(
            selected_snapshot,
            (client_item(ssid=selected_ssid),),
            "next",
        )

    def get_current_ap_summary(self, site):
        self.calls.append(("ap-summary", site))
        return ap_summary()

    def list_current_aps(self, site, **kwargs):
        self.calls.append(("aps", site, kwargs))
        return CurrentApPage(snapshot("ap"), (ap_item(),), None)


class Poison:
    def __getattribute__(self, _name):
        raise AssertionError("optional source was dereferenced")


def service(source=None, *, max_queries=2):
    config = admin_web_config_from_settings(enabled_settings(
        web_admin_home_live_enabled="true",
        web_admin_max_concurrent_queries=max_queries,
    ))
    return AdminQueryService(
        config=config,
        policy=AdminAccessPolicy(config.allowed_site_ids),
        device_gateway=object(),
        read_gateway=object(),
        visit_analytics_service=object(),
        current_state_read_service=source,
    )


def principal():
    return AdminPrincipal("operator")


@pytest.mark.parametrize("value", ["true", True])
def test_home_live_exact_boolean_is_accepted(value):
    config = admin_web_config_from_settings(enabled_settings(web_admin_home_live_enabled=value))
    assert config.home_live_enabled is True


def test_home_live_safe_defaults():
    config = admin_web_config_from_settings(enabled_settings())
    assert config.home_live_enabled is False
    assert config.home_live_refresh_seconds == 60
    assert config.home_live_request_timeout_seconds == 20
    assert config.current_state_page_size == 100
    assert "correct horse" not in repr(config)


@pytest.mark.parametrize(
    "key,value",
    [
        ("web_admin_home_live_refresh_seconds", 59),
        ("web_admin_home_live_refresh_seconds", 301),
        ("web_admin_home_live_request_timeout_seconds", 4),
        ("web_admin_home_live_request_timeout_seconds", 61),
        ("web_admin_current_state_page_size", 0),
        ("web_admin_current_state_page_size", 251),
    ],
)
def test_home_live_numeric_bounds(key, value):
    with pytest.raises(AdminWebConfigError):
        admin_web_config_from_settings(enabled_settings(**{key: value}))


@pytest.mark.parametrize("value", ["TRUE", "1", 1, None])
def test_home_live_non_exact_boolean_is_rejected(value):
    with pytest.raises(AdminWebConfigError):
        admin_web_config_from_settings(enabled_settings(web_admin_home_live_enabled=value))


def test_home_live_cross_field_and_parent_feature_contracts():
    with pytest.raises(AdminWebConfigError, match="must exceed"):
        admin_web_config_from_settings(enabled_settings(web_admin_home_live_enabled="true", web_admin_home_live_request_timeout_seconds=10))
    with pytest.raises(AdminWebConfigError, match="requires"):
        admin_web_config_from_settings(enabled_settings(web_admin_enabled="false", web_admin_home_live_enabled="true"))


def test_optional_source_does_not_join_runtime_readiness_gate(tmp_path):
    runtime = create_admin_web_runtime(
        enabled_settings(),
        SimpleNamespace(state="active", visit_service=object()),
        SimpleNamespace(repository=SimpleNamespace(config=SimpleNamespace(db_path=tmp_path / "r"))),
        SimpleNamespace(repository=SimpleNamespace(db_path=tmp_path / "v")),
        SimpleNamespace(_repository=SimpleNamespace(db_path=tmp_path / "o")),
        __import__("logging").getLogger("home-live-runtime"),
        current_state_read_service=Poison(),
    )
    assert runtime.state == "active"


def test_client_serializers_minimize_and_preserve_zero():
    summary = serialize_client_summary(client_summary(), SITE_ID)
    assert summary["counts"]["other"] == 0
    assert set(summary["snapshot"]["source_scope"]) == {"scope_type", "site_id", "ssids"}
    result, page = serialize_client_page(CurrentClientPage(snapshot(), (client_item(controller_uptime=0),), None), SITE_ID, limit=100, explicit_cycle_id=CYCLE, explicit_cursor=None)
    assert result["items"][0]["controller_uptime"] == 0
    assert set(result["items"][0]) == {
        "client_mac", "name", "hostname", "ip", "ssid", "ap_name", "ap_mac",
        "band", "rssi", "snr", "controller_uptime", "controller_traffic_down",
        "controller_traffic_up", "controller_traffic_total", "auth_classification",
    }
    assert page["cycle_id"] == CYCLE


def test_client_serializer_rejects_cross_site_scope_and_item():
    with pytest.raises(CurrentStateValidationError):
        serialize_client_summary(replace(client_summary(), snapshot=replace(snapshot(), source_scope={"scope_type": "client_ssid_allowlist", "site_id": "f" * 24, "ssids": ["OwnerWiFi"]})), SITE_ID)
    with pytest.raises(CurrentStateValidationError):
        serialize_client_page(CurrentClientPage(snapshot(), (client_item(site_id="f" * 24),), None), SITE_ID, limit=100, explicit_cycle_id=None, explicit_cursor=None)


@pytest.mark.parametrize("source_status,product", [("online", "Online"), ("unknown", "Unknown"), ("offline", "Other"), ("future", "Other")])
def test_ap_product_mapping_never_exposes_offline(source_status, product):
    result, _ = serialize_ap_page(CurrentApPage(snapshot("ap"), (ap_item(source_status),), None), SITE_ID, limit=100, explicit_cycle_id=None, explicit_cursor=None)
    assert result["items"][0]["product_status_classification"] == product
    assert "status_classification" not in result["items"][0]


def test_ap_summary_maps_offline_to_other_and_checks_product_invariant():
    result = serialize_ap_summary(ap_summary(), SITE_ID)
    assert result["counts"] == {"total": 3, "online": 1, "other": 1, "unknown": 1}


def test_query_service_pre_post_deadline_and_exact_arguments():
    source = CurrentSource()
    query = service(source)
    response = query.list_current_clients(principal(), SITE_ID, cycle_id=CYCLE, limit="100", sort="client_mac", ssid=" OwnerWiFi ")
    assert response.page["limit"] == 100
    assert source.calls[-1][2]["ssid"] == " OwnerWiFi "


@pytest.mark.parametrize("limit", ["0", "01", "+1", "1.0", " 1", "251", 1])
def test_current_page_limit_is_canonical_and_bounded(limit):
    with pytest.raises(AdminQueryValidationError):
        service(CurrentSource()).list_current_aps(principal(), SITE_ID, limit=limit)


@pytest.mark.parametrize("limit", ["1", "100", "101", "250"])
def test_current_page_limit_accepts_full_contract(limit):
    response = service(CurrentSource()).list_current_aps(principal(), SITE_ID, limit=limit)
    assert response.page["limit"] == int(limit)


def test_missing_source_and_integrity_errors_are_unavailable():
    with pytest.raises(AdminQueryUnavailable):
        service().current_client_summary(principal(), SITE_ID)
    source = CurrentSource()
    source.get_current_client_summary = lambda _site: (_ for _ in ()).throw(CurrentStateValidationError("persisted auth count invariant failed"))
    with pytest.raises(AdminQueryUnavailable):
        service(source).current_client_summary(principal(), SITE_ID)


def test_page_source_validation_uses_strict_caller_reason_allowlist():
    source = CurrentSource()
    source.list_current_aps = lambda _site, **_kwargs: (_ for _ in ()).throw(CurrentStateValidationError("cursor is malformed"))
    with pytest.raises(AdminQueryValidationError):
        service(source).list_current_aps(principal(), SITE_ID, cursor="opaque")
    source.list_current_aps = lambda _site, **_kwargs: (_ for _ in ()).throw(CurrentStateValidationError("persisted AP status invariant failed"))
    with pytest.raises(AdminQueryUnavailable):
        service(source).list_current_aps(principal(), SITE_ID)


def test_current_source_sqlite_failure_is_unavailable():
    source = CurrentSource()
    source.get_current_ap_summary = lambda _site: (_ for _ in ()).throw(sqlite3.OperationalError("private path"))
    with pytest.raises(AdminQueryUnavailable):
        service(source).current_ap_summary(principal(), SITE_ID)


def test_current_capability_mapping_rejects_non_platform_principal():
    outsider = AdminPrincipal("operator", principal_type="other")
    query = service(CurrentSource())
    for operation in (
        lambda: query.current_client_summary(outsider, SITE_ID),
        lambda: query.current_ap_summary(outsider, SITE_ID),
        lambda: query.list_current_clients(outsider, SITE_ID),
        lambda: query.list_current_aps(outsider, SITE_ID),
    ):
        with pytest.raises(AdminQueryForbidden):
            operation()


def test_current_source_post_call_deadline_is_enforced(monkeypatch):
    from app.analytics.source_gateway import AnalyticsQueryDeadlineExceeded
    import app.admin_web.query_service as module

    class Deadline:
        calls = 0
        def require_remaining(self):
            self.calls += 1
            if self.calls == 2:
                raise AnalyticsQueryDeadlineExceeded()

    deadline = Deadline()
    monkeypatch.setattr(module.QueryDeadline, "after", lambda _seconds: deadline)
    source = CurrentSource()
    with pytest.raises(AdminQueryDeadline):
        service(source).current_client_summary(principal(), SITE_ID)
    assert source.calls == [("client-summary", SITE_ID)]
    assert deadline.calls == 2


@pytest.mark.parametrize("kind", ["client-summary", "client-page", "ap-summary", "ap-page"])
def test_each_current_method_checks_deadline_before_source(monkeypatch, kind):
    from app.analytics.source_gateway import AnalyticsQueryDeadlineExceeded
    import app.admin_web.query_service as module

    class Deadline:
        def require_remaining(self):
            raise AnalyticsQueryDeadlineExceeded()

    monkeypatch.setattr(module.QueryDeadline, "after", lambda _seconds: Deadline())
    source = CurrentSource()
    query = service(source)
    calls = {
        "client-summary": lambda: query.current_client_summary(principal(), SITE_ID),
        "client-page": lambda: query.list_current_clients(principal(), SITE_ID),
        "ap-summary": lambda: query.current_ap_summary(principal(), SITE_ID),
        "ap-page": lambda: query.list_current_aps(principal(), SITE_ID),
    }
    with pytest.raises(AdminQueryDeadline):
        calls[kind]()
    assert source.calls == []


def test_current_methods_share_existing_nonblocking_query_slot():
    entered = threading.Event()
    release = threading.Event()
    source = CurrentSource()
    original = source.get_current_client_summary
    def blocked(site):
        entered.set()
        assert release.wait(2)
        return original(site)
    source.get_current_client_summary = blocked
    query = service(source, max_queries=1)
    thread = threading.Thread(target=lambda: query.current_client_summary(principal(), SITE_ID))
    thread.start()
    assert entered.wait(1)
    with pytest.raises(AdminQueryBusy):
        query.current_ap_summary(principal(), SITE_ID)
    release.set()
    thread.join(2)
    assert not thread.is_alive()


def test_explicit_missing_cycle_is_invalid_request():
    source = CurrentSource()
    source.list_current_clients = lambda _site, **_kwargs: CurrentClientPage(snapshot(status="unavailable", cycle_id=None), (), None)
    with pytest.raises(AdminQueryValidationError):
        service(source).list_current_clients(principal(), SITE_ID, cycle_id=CYCLE)


def test_explicit_expired_cycle_and_cursor_are_invalid_request():
    expired = replace(snapshot(), freshness_status="unavailable")
    source = CurrentSource()
    source.list_current_clients = lambda _site, **_kwargs: CurrentClientPage(expired, (), None)
    with pytest.raises(AdminQueryValidationError):
        service(source).list_current_clients(principal(), SITE_ID, cycle_id=CYCLE)
    with pytest.raises(AdminQueryValidationError):
        service(source).list_current_clients(principal(), SITE_ID, cursor="opaque")


def test_home_template_feature_delivery_and_legacy_fallback(admin_app):
    client = admin_app.test_client()
    assert login(client).status_code == 302
    response = client.get(f"/admin/sites/{SITE_ID}/", base_url="https://localhost")
    text = response.get_data(as_text=True)
    assert 'data-home-live-enabled="false"' in text
    assert "Health and a compact 24-hour Site summary." in text
    assert "Online Devices" not in text


def live_app(tmp_path, source, logger, *, home_live="true"):
    runtime = create_admin_web_runtime(
        enabled_settings(web_admin_home_live_enabled=home_live),
        SimpleNamespace(state="active", visit_service=object()),
        SimpleNamespace(repository=SimpleNamespace(config=SimpleNamespace(db_path=tmp_path / "registry.sqlite3"))),
        SimpleNamespace(repository=SimpleNamespace(db_path=tmp_path / "visits.sqlite3")),
        SimpleNamespace(_repository=SimpleNamespace(db_path=tmp_path / "observations.sqlite3")),
        logger,
        current_state_read_service=source,
    )
    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    app.register_blueprint(runtime.blueprint)
    app.extensions["admin_web_runtime"] = runtime
    return app


def test_disabled_endpoint_hides_query_schema_after_security(admin_app):
    client = admin_app.test_client()
    assert client.get(f"/admin/api/v1/sites/{SITE_ID}/current-state/clients?bad=1", base_url="https://localhost").status_code == 401
    assert login(client).status_code == 302
    response = client.get(f"/admin/api/v1/sites/{SITE_ID}/current-state/clients?bad=1", base_url="https://localhost")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"
    duplicate = client.get(f"/admin/api/v1/sites/{SITE_ID}/current-state/clients?limit=1&limit=2", base_url="https://localhost")
    assert duplicate.status_code == 404


def test_live_routes_return_minimized_dtos_and_emit_completion(tmp_path, caplog):
    import logging
    logger = logging.getLogger("admin-home-live-route")
    app = live_app(tmp_path, CurrentSource(), logger)
    client = app.test_client()
    assert login(client).status_code == 302
    home = client.get(f"/admin/sites/{SITE_ID}/", base_url="https://localhost").get_data(as_text=True)
    assert 'data-home-live-enabled="true"' in home
    assert "Current network state for the selected Site." in home
    assert "Health and a compact 24-hour Site summary." not in home
    assert "Online Devices" in home
    caplog.set_level(logging.INFO, logger=logger.name)
    summary = client.get(f"/admin/api/v1/sites/{SITE_ID}/current-state/clients/summary", base_url="https://localhost")
    assert summary.status_code == 200
    assert summary.get_json()["result"]["counts"]["online"] == 2
    page = client.get(f"/admin/api/v1/sites/{SITE_ID}/current-state/clients?cycle_id={CYCLE}&limit=100&sort=client_mac", base_url="https://localhost")
    assert page.status_code == 200
    assert page.get_json()["page"]["cycle_id"] == CYCLE
    records = [record for record in caplog.records if record.getMessage() == "admin.current_state_query_completed"]
    assert len(records) == 2
    assert records[-1].route_name == "current_client_page"
    assert records[-1].item_count == 1
    assert not hasattr(records[-1], "cursor")


def test_feature_false_never_touches_injected_current_source(tmp_path):
    import logging
    source = CurrentSource()
    app = live_app(tmp_path, source, logging.getLogger("admin-home-live-off"), home_live="false")
    client = app.test_client()
    assert login(client).status_code == 302
    response = client.get(f"/admin/api/v1/sites/{SITE_ID}/current-state/clients/summary", base_url="https://localhost")
    assert response.status_code == 404
    assert source.calls == []


@pytest.mark.parametrize("policy_failure,expected_status", [("rejected", 403), ("exception", 500)])
def test_completion_telemetry_does_not_claim_unauthorized_site(
    tmp_path, caplog, monkeypatch, policy_failure, expected_status
):
    import logging

    logger = logging.getLogger(f"admin-home-live-policy-{policy_failure}")
    app = live_app(tmp_path, CurrentSource(), logger)
    client = app.test_client()
    assert login(client).status_code == 302
    if policy_failure == "rejected":
        monkeypatch.setattr(AdminAccessPolicy, "authorize", lambda *_args: False)
    else:
        def fail_policy(*_args):
            raise RuntimeError("policy failure")
        monkeypatch.setattr(AdminAccessPolicy, "authorize", fail_policy)
    caplog.set_level(logging.INFO, logger=logger.name)

    response = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/current-state/clients/summary",
        base_url="https://localhost",
    )

    assert response.status_code == expected_status
    records = [
        record for record in caplog.records
        if record.getMessage() == "admin.current_state_query_completed"
    ]
    assert len(records) == 1
    assert not hasattr(records[0], "site_id")


def test_live_route_missing_source_is_503_without_disabling_legacy_admin(tmp_path):
    import logging
    app = live_app(tmp_path, None, logging.getLogger("admin-home-live-missing"))
    runtime = app.extensions["admin_web_runtime"]
    assert runtime.state == "active"
    client = app.test_client()
    assert login(client).status_code == 302
    response = client.get(f"/admin/api/v1/sites/{SITE_ID}/current-state/aps/summary", base_url="https://localhost")
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "source_unavailable"


def test_live_page_rejects_unknown_duplicate_and_noncanonical_limit(tmp_path):
    import logging
    app = live_app(tmp_path, CurrentSource(), logging.getLogger("admin-home-live-input"))
    client = app.test_client()
    assert login(client).status_code == 302
    base = f"/admin/api/v1/sites/{SITE_ID}/current-state/aps"
    assert client.get(base + "?unknown=1", base_url="https://localhost").status_code == 400
    assert client.get(base + "?limit=1&limit=2", base_url="https://localhost").status_code == 400
    assert client.get(base + "?limit=01", base_url="https://localhost").status_code == 400


def test_unexpected_current_source_failure_is_sanitized_500(tmp_path, caplog):
    import logging
    sentinel = "PRIVATE_DB_PATH_SENTINEL"
    source = CurrentSource()
    source.get_current_client_summary = lambda _site: (_ for _ in ()).throw(RuntimeError(sentinel))
    logger = logging.getLogger("admin-home-live-programming")
    app = live_app(tmp_path, source, logger)
    client = app.test_client()
    assert login(client).status_code == 302
    caplog.set_level(logging.ERROR, logger=logger.name)
    response = client.get(f"/admin/api/v1/sites/{SITE_ID}/current-state/clients/summary", base_url="https://localhost")
    assert response.status_code == 500
    assert sentinel not in response.get_data(as_text=True)
    assert sentinel not in " ".join(record.getMessage() for record in caplog.records)


def test_home_live_static_contract_has_safe_dom_and_no_storage_or_interval():
    text = (__import__("pathlib").Path(__file__).parents[2] / "app/admin_web/static/admin.js").read_text(encoding="utf-8")
    assert "innerHTML" not in text
    assert "localStorage" not in text
    assert "sessionStorage" not in text
    assert "setInterval" not in text
    assert "AbortController" in text
    assert "performance.now()" in text
    assert "pagehide" in text
