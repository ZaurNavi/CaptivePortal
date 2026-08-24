from __future__ import annotations

import logging
import threading
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from app.admin_web import create_admin_web_runtime
from app.admin_web.config import AdminWebConfigError, admin_web_config_from_settings
from app.admin_web.current_traffic_serialization import (
    CurrentTrafficSerializationError,
    serialize_current_ap_traffic_page,
    serialize_current_traffic_summary,
)
from app.admin_web.models import AdminPrincipal
from app.admin_web.policy import AdminAccessPolicy
from app.admin_web.query_service import (
    AdminQueryForbidden,
    AdminQueryBusy,
    AdminQueryDeadline,
    AdminQueryService,
    AdminQueryUnavailable,
    AdminQueryValidationError,
)
from app.analytics.models import (
    CurrentApTrafficItem,
    CurrentApTrafficPage,
    CurrentSiteTraffic,
    CurrentTrafficCoverage,
    CurrentTrafficFreshness,
    CurrentTrafficFreshnessPolicy,
    CurrentTrafficPageMetadata,
    CurrentTrafficSnapshot,
    CurrentTrafficSourceSelection,
    CurrentTrafficTotals,
)
from app.analytics.source_gateway import QueryDeadline
from app.analytics.source_gateway import AnalyticsQueryDeadlineExceeded
from app.analytics import CurrentTrafficValidationError

from .conftest import SITE_ID, enabled_settings, login


CYCLE = "10000000-0000-4000-8000-000000000001"
NOW = "2026-08-24T13:00:00.000Z"
OBSERVED = "2026-08-24T12:59:42.000Z"
NEWEST = "2026-08-24T12:59:55.000Z"


def traffic_snapshot(**overrides):
    values = dict(
        source_kind="observation_ap_dynamic",
        site_id=SITE_ID,
        cycle_id=CYCLE,
        started_at="2026-08-24T12:59:00.000Z",
        finished_at="2026-08-24T12:59:57.000Z",
        complete=True,
        evaluated_at=NOW,
        observed_at=OBSERVED,
        newest_observed_at=NEWEST,
        age_seconds=18.0,
        source_skew_seconds=13.0,
        freshness_status="fresh",
        freshness_reason="within_freshness_window",
        primary_source="wired",
        selected_source="wired",
        selection_reason="primary_full_coverage",
        empty_population=False,
        latest_attempt_state="completed",
        latest_attempt_result="success",
        latest_attempt_at="2026-08-24T12:59:57.000Z",
        using_previous_complete_snapshot=False,
    )
    values.update(overrides)
    return CurrentTrafficSnapshot(**values)


def traffic_summary(*, mode="complete", snapshot=None):
    selected_snapshot = snapshot or traffic_snapshot()
    coverage = CurrentTrafficCoverage(
        status="complete",
        reasons=(),
        empty_population=False,
        total_ap_count=2,
        valid_rate_ap_count=2,
        valid_download_ap_count=2,
        valid_upload_ap_count=2,
        missing_rate_ap_count=0,
        stale_ap_count=0,
        unavailable_ap_count=0,
        reset_ap_count=0,
        gap_rejected_ap_count=0,
        no_baseline_ap_count=0,
        source_unavailable_ap_count=0,
        invalid_elapsed_ap_count=0,
        observed_at=OBSERVED,
        newest_observed_at=NEWEST,
        source_skew_seconds=13.0,
    )
    totals = CurrentTrafficTotals(42.125, 6.25, 48.375)
    if mode == "partial":
        coverage = replace(
            coverage,
            status="partial",
            reasons=("missing_direction",),
            valid_rate_ap_count=1,
            valid_upload_ap_count=1,
            missing_rate_ap_count=1,
        )
        totals = CurrentTrafficTotals(42.125, None, None)
    elif mode == "empty":
        selected_snapshot = traffic_snapshot(
            selection_reason="empty_population",
            empty_population=True,
            observed_at="2026-08-24T12:59:57.000Z",
            newest_observed_at="2026-08-24T12:59:57.000Z",
            source_skew_seconds=0.0,
            age_seconds=3.0,
        )
        coverage = replace(
            coverage,
            reasons=("empty_population",),
            empty_population=True,
            total_ap_count=0,
            valid_rate_ap_count=0,
            valid_download_ap_count=0,
            valid_upload_ap_count=0,
            missing_rate_ap_count=0,
            observed_at="2026-08-24T12:59:57.000Z",
            newest_observed_at="2026-08-24T12:59:57.000Z",
            source_skew_seconds=0.0,
        )
        totals = CurrentTrafficTotals(0.0, 0.0, 0.0)
    elif mode == "none":
        selected_snapshot = traffic_snapshot(
            cycle_id=None,
            started_at=None,
            finished_at=None,
            complete=False,
            observed_at=None,
            newest_observed_at=None,
            age_seconds=None,
            source_skew_seconds=None,
            freshness_status="unavailable",
            freshness_reason="no_complete_snapshot",
            selected_source=None,
            selection_reason="no_complete_snapshot",
            latest_attempt_state="none",
            latest_attempt_result=None,
            latest_attempt_at=None,
        )
        coverage = replace(
            coverage,
            status="none",
            total_ap_count=0,
            valid_rate_ap_count=0,
            valid_download_ap_count=0,
            valid_upload_ap_count=0,
            missing_rate_ap_count=0,
            observed_at=None,
            newest_observed_at=None,
            source_skew_seconds=None,
        )
        totals = CurrentTrafficTotals(None, None, None)
    policy = CurrentTrafficFreshnessPolicy(90.0, 180.0, 60.0)
    selection = CurrentTrafficSourceSelection(
        primary_source="wired",
        selected_source=selected_snapshot.selected_source,
        selection_reason=selected_snapshot.selection_reason,
        wired_pair_valid_ap_count=coverage.valid_rate_ap_count,
        lan_pair_valid_ap_count=coverage.valid_rate_ap_count,
    )
    freshness = CurrentTrafficFreshness(
        status=selected_snapshot.freshness_status,
        reason=selected_snapshot.freshness_reason,
        evaluated_at_utc=selected_snapshot.evaluated_at,
        observed_at=selected_snapshot.observed_at,
        newest_observed_at=selected_snapshot.newest_observed_at,
        age_seconds=selected_snapshot.age_seconds,
    )
    return CurrentSiteTraffic(
        selected_snapshot, policy, selection, coverage, freshness, totals
    )


def invalid_population_summary(case):
    mode = "complete" if case == "nonempty_empty_reason" else "empty"
    value = traffic_summary(mode=mode)
    if case == "empty_lan":
        return replace(
            value,
            snapshot=replace(value.snapshot, selected_source="lan"),
            source_selection=replace(value.source_selection, selected_source="lan"),
        )
    if case == "empty_wrong_reason":
        return replace(
            value,
            snapshot=replace(value.snapshot, selection_reason="primary_full_coverage"),
            source_selection=replace(
                value.source_selection,
                selection_reason="primary_full_coverage",
            ),
        )
    if case == "nonempty_empty_reason":
        return replace(
            value,
            snapshot=replace(value.snapshot, selection_reason="empty_population"),
            source_selection=replace(
                value.source_selection,
                selection_reason="empty_population",
            ),
        )
    if case == "empty_nonzero_count":
        return replace(
            value,
            coverage=replace(
                value.coverage,
                total_ap_count=1,
                missing_rate_ap_count=1,
            ),
        )
    if case == "empty_null_traffic":
        return replace(value, traffic=CurrentTrafficTotals(None, 0.0, None))
    if case == "empty_nonzero_traffic":
        return replace(value, traffic=CurrentTrafficTotals(1.0, 0.0, 1.0))
    raise AssertionError(f"unknown test case: {case}")


def traffic_page(*, source="wired", cursor=None):
    snapshot = traffic_snapshot(
        selected_source=source,
        selection_reason=(
            "primary_full_coverage" if source == "wired" else "fallback_full_coverage"
        ),
    )
    policy = CurrentTrafficFreshnessPolicy(90.0, 180.0, 60.0)
    selection = CurrentTrafficSourceSelection(
        "wired", source, snapshot.selection_reason, 2, 2
    )
    item = CurrentApTrafficItem(
        "AA:BB:CC:DD:EE:FF", "AP-1", 20.0, 3.0, 23.0,
        "ok", "ok", "valid", OBSERVED, 18.0, source,
    )
    metadata = CurrentTrafficPageMetadata(100, cursor, CYCLE, source)
    return CurrentApTrafficPage(snapshot, policy, selection, (item,), metadata)


class TrafficSource:
    def __init__(self):
        self.calls = []
        self.summary = traffic_summary()
        self.page = traffic_page()

    def get_current_site_traffic(self, site_id, **kwargs):
        self.calls.append(("summary", site_id, kwargs))
        return self.summary

    def list_current_ap_traffic(self, site_id, **kwargs):
        self.calls.append(("page", site_id, kwargs))
        return self.page


def query_service(source, **settings):
    config = admin_web_config_from_settings(enabled_settings(
        web_admin_home_live_enabled="true",
        web_admin_home_traffic_enabled="true",
        **settings,
    ))
    return AdminQueryService(
        config=config,
        policy=AdminAccessPolicy(config.allowed_site_ids),
        device_gateway=object(),
        read_gateway=object(),
        visit_analytics_service=object(),
        current_traffic_read_service=source,
    )


def traffic_app(tmp_path, source, logger, *, traffic="true"):
    runtime = create_admin_web_runtime(
        enabled_settings(
            web_admin_home_live_enabled="true",
            web_admin_home_traffic_enabled=traffic,
        ),
        SimpleNamespace(
            state="active",
            visit_service=object(),
            current_traffic_service=source,
        ),
        SimpleNamespace(repository=SimpleNamespace(config=SimpleNamespace(db_path=tmp_path / "registry.sqlite3"))),
        SimpleNamespace(repository=SimpleNamespace(db_path=tmp_path / "visits.sqlite3")),
        SimpleNamespace(_repository=SimpleNamespace(db_path=tmp_path / "observations.sqlite3")),
        logger,
    )
    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    app.register_blueprint(runtime.blueprint)
    app.extensions["admin_web_runtime"] = runtime
    return app


def test_home_traffic_defaults_bounds_and_parent_contract():
    config = admin_web_config_from_settings(enabled_settings())
    assert config.home_traffic_enabled is False
    assert (
        config.home_traffic_refresh_seconds,
        config.home_traffic_request_timeout_seconds,
        config.home_traffic_page_size,
        config.home_traffic_fresh_max_age_seconds,
        config.home_traffic_stale_max_age_seconds,
        config.home_traffic_max_ap_skew_seconds,
    ) == (60, 20, 100, 90, 180, 60)
    for key, value in (
        ("web_admin_home_traffic_refresh_seconds", 59),
        ("web_admin_home_traffic_request_timeout_seconds", 61),
        ("web_admin_home_traffic_page_size", 251),
        ("web_admin_home_traffic_fresh_max_age_seconds", 29),
        ("web_admin_home_traffic_stale_max_age_seconds", 601),
        ("web_admin_home_traffic_max_ap_skew_seconds", 9),
    ):
        with pytest.raises(AdminWebConfigError):
            admin_web_config_from_settings(enabled_settings(**{key: value}))
    with pytest.raises(AdminWebConfigError):
        admin_web_config_from_settings(enabled_settings(
            web_admin_home_live_enabled="true",
            web_admin_home_traffic_enabled="true",
            web_admin_home_traffic_request_timeout_seconds=10,
        ))
    with pytest.raises(AdminWebConfigError):
        admin_web_config_from_settings(enabled_settings(
            web_admin_home_live_enabled="true",
            web_admin_home_traffic_enabled="true",
            web_admin_home_traffic_fresh_max_age_seconds=200,
            web_admin_home_traffic_stale_max_age_seconds=199,
        ))
    with pytest.raises(AdminWebConfigError):
        admin_web_config_from_settings(enabled_settings(
            web_admin_home_live_enabled="false",
            web_admin_home_traffic_enabled="true",
        ))


@pytest.mark.parametrize("mode", ["complete", "partial", "empty", "none"])
def test_summary_serializer_explicit_contract(mode):
    result = serialize_current_traffic_summary(traffic_summary(mode=mode), SITE_ID)
    assert set(result) == {
        "snapshot", "freshness_policy", "traffic", "source_selection", "coverage"
    }
    assert result["traffic"]["unit"] == "Mbps"
    assert "site_id" not in result["snapshot"]
    assert result["freshness_policy"] == {
        "fresh_max_age_seconds": 90.0,
        "unavailable_after_seconds": 180.0,
        "max_ap_skew_seconds": 60.0,
    }
    if mode == "empty":
        assert result["traffic"] == {
            "download_mbps": 0.0,
            "upload_mbps": 0.0,
            "total_mbps": 0.0,
            "unit": "Mbps",
        }
    if mode == "none":
        assert result["snapshot"]["selected_source"] is None
        assert result["coverage"]["coverage_status"] == "none"


@pytest.mark.parametrize(
    "case",
    [
        "empty_lan",
        "empty_wrong_reason",
        "nonempty_empty_reason",
        "empty_nonzero_count",
        "empty_null_traffic",
        "empty_nonzero_traffic",
    ],
)
def test_summary_serializer_rejects_invalid_empty_population_combinations(case):
    with pytest.raises(CurrentTrafficSerializationError):
        serialize_current_traffic_summary(invalid_population_summary(case), SITE_ID)


def test_serializers_reject_site_source_and_arithmetic_mismatch():
    wrong_site = replace(traffic_summary(), snapshot=traffic_snapshot(site_id="f" * 24))
    with pytest.raises(CurrentTrafficSerializationError):
        serialize_current_traffic_summary(wrong_site, SITE_ID)
    wrong_source = replace(
        traffic_summary(),
        snapshot=traffic_snapshot(selected_source="LAN"),
    )
    with pytest.raises(CurrentTrafficSerializationError):
        serialize_current_traffic_summary(wrong_source, SITE_ID)
    wrong_total = replace(
        traffic_summary(), traffic=CurrentTrafficTotals(1.0, 2.0, 4.0)
    )
    with pytest.raises(CurrentTrafficSerializationError):
        serialize_current_traffic_summary(wrong_total, SITE_ID)


def test_ap_page_serializer_is_pinned_and_allowlisted():
    result, page = serialize_current_ap_traffic_page(
        traffic_page(source="lan"), SITE_ID, cycle_id=CYCLE, limit=100
    )
    assert page == {
        "limit": 100,
        "next_cursor": None,
        "cycle_id": CYCLE,
        "selected_source": "lan",
    }
    assert set(result["items"][0]) == {
        "ap_mac", "name", "download_mbps", "upload_mbps", "total_mbps",
        "download_reason", "upload_reason", "rate_status", "observed_at",
        "age_seconds", "selected_source",
    }
    with pytest.raises(CurrentTrafficSerializationError):
        serialize_current_ap_traffic_page(
            traffic_page(), SITE_ID, cycle_id=str(__import__("uuid").uuid4()), limit=100
        )


def test_page_size_100_fits_admin_response_budget():
    base = traffic_page().items[0]
    items = tuple(
        replace(
            base,
            ap_mac=f"02:00:00:{index // 65536:02X}:{(index // 256) % 256:02X}:{index % 256:02X}",
            name=f"AP-{index:03d}",
        )
        for index in range(100)
    )
    value = replace(traffic_page(), items=items)
    result, page = serialize_current_ap_traffic_page(
        value, SITE_ID, cycle_id=CYCLE, limit=100
    )
    body = json.dumps(
        {"api_version": "admin.read.v1", "site_id": SITE_ID, "result": result, "page": page},
        separators=(",", ":"),
    ).encode("utf-8")
    assert len(result["items"]) == 100
    assert len(body) < 1_048_576


def test_query_service_passes_policy_deadline_and_never_source_choice():
    source = TrafficSource()
    service = query_service(source)
    principal = AdminPrincipal("operator")
    service.current_traffic_summary(principal, SITE_ID)
    service.list_current_ap_traffic(
        principal, SITE_ID, cycle_id=CYCLE, limit="100", cursor=None
    )
    summary_kwargs = source.calls[0][2]
    page_kwargs = source.calls[1][2]
    for kwargs in (summary_kwargs, page_kwargs):
        assert isinstance(kwargs.pop("deadline"), QueryDeadline)
        assert kwargs["fresh_max_age_seconds"] == 90
        assert kwargs["stale_max_age_seconds"] == 180
        assert kwargs["max_ap_skew_seconds"] == 60
        assert "selected_source" not in kwargs
    assert page_kwargs["cycle_id"] == CYCLE
    assert page_kwargs["limit"] == 100


def test_query_service_capabilities_validation_and_optional_source():
    outsider = AdminPrincipal("operator", principal_type="other")
    service = query_service(TrafficSource())
    with pytest.raises(AdminQueryForbidden):
        service.current_traffic_summary(outsider, SITE_ID)
    with pytest.raises(AdminQueryForbidden):
        service.list_current_ap_traffic(outsider, SITE_ID, cycle_id=CYCLE)
    with pytest.raises(AdminQueryValidationError):
        service.list_current_ap_traffic(AdminPrincipal("operator"), SITE_ID, cycle_id=None)
    with pytest.raises(AdminQueryUnavailable):
        query_service(None).current_traffic_summary(AdminPrincipal("operator"), SITE_ID)


def test_traffic_queries_share_nonblocking_admin_slot():
    source = TrafficSource()
    entered = threading.Event()
    release = threading.Event()
    original = source.get_current_site_traffic

    def blocked(site_id, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(site_id, **kwargs)

    source.get_current_site_traffic = blocked
    service = query_service(source, web_admin_max_concurrent_queries=1)
    principal = AdminPrincipal("operator")
    thread = threading.Thread(
        target=lambda: service.current_traffic_summary(principal, SITE_ID)
    )
    thread.start(); assert entered.wait(2)
    with pytest.raises(AdminQueryBusy):
        service.list_current_ap_traffic(principal, SITE_ID, cycle_id=CYCLE)
    release.set(); thread.join(5)
    assert not thread.is_alive()


def test_traffic_deadline_and_expired_cycle_mapping():
    source = TrafficSource()
    source.get_current_site_traffic = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AnalyticsQueryDeadlineExceeded()
    )
    with pytest.raises(AdminQueryDeadline):
        query_service(source).current_traffic_summary(AdminPrincipal("operator"), SITE_ID)
    source = TrafficSource()
    source.list_current_ap_traffic = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        CurrentTrafficValidationError("traffic cycle is unavailable")
    )
    with pytest.raises(AdminQueryValidationError):
        query_service(source).list_current_ap_traffic(
            AdminPrincipal("operator"), SITE_ID, cycle_id=CYCLE
        )


def test_routes_feature_security_query_and_wire_contract(tmp_path, caplog):
    source = TrafficSource()
    logger = logging.getLogger("admin-home-traffic-route")
    app = traffic_app(tmp_path, source, logger)
    client = app.test_client()
    base = f"/admin/api/v1/sites/{SITE_ID}/current-traffic"
    assert client.get(f"{base}/summary?bad=1", base_url="https://localhost").status_code == 401
    assert login(client).status_code == 302
    summary = client.get(f"{base}/summary", base_url="https://localhost")
    assert summary.status_code == 200
    assert summary.get_json()["result"]["traffic"]["download_mbps"] == 42.125
    page = client.get(f"{base}/aps?cycle_id={CYCLE}&limit=100", base_url="https://localhost")
    assert page.status_code == 200
    assert page.get_json()["page"]["selected_source"] == "wired"
    before = len(source.calls)
    for suffix in (
        "/summary?selected_source=wired",
        f"/aps?cycle_id={CYCLE}&source=lan",
        f"/aps?cycle_id={CYCLE}&limit=1&limit=2",
        "/aps?cursor=opaque",
    ):
        assert client.get(base + suffix, base_url="https://localhost").status_code == 400
    assert len(source.calls) == before
    records = [record for record in caplog.records if record.getMessage() == "admin.current_traffic_query_completed"]
    assert all(not hasattr(record, "cycle_id") and not hasattr(record, "cursor") for record in records)


def test_feature_disabled_is_404_after_security_and_does_not_touch_source(tmp_path):
    source = TrafficSource()
    app = traffic_app(tmp_path, source, logging.getLogger("traffic-disabled"), traffic="false")
    client = app.test_client()
    url = f"/admin/api/v1/sites/{SITE_ID}/current-traffic/summary?bad=1"
    assert client.get(url, base_url="https://localhost").status_code == 401
    assert login(client).status_code == 302
    assert client.get(url, base_url="https://localhost").status_code == 404
    assert source.calls == []


def test_ap_capability_403_preserves_summary_boundary_and_hides_site_in_telemetry(
    tmp_path, monkeypatch, caplog,
):
    original = AdminAccessPolicy.authorize

    def selective(self, principal, capability, site_id):
        return capability != "admin.read.observations" and original(
            self, principal, capability, site_id
        )

    monkeypatch.setattr(AdminAccessPolicy, "authorize", selective)
    source = TrafficSource()
    logger = logging.getLogger("traffic-capability")
    app = traffic_app(tmp_path, source, logger)
    client = app.test_client(); assert login(client).status_code == 302
    base = f"/admin/api/v1/sites/{SITE_ID}/current-traffic"
    assert client.get(f"{base}/summary", base_url="https://localhost").status_code == 200
    with caplog.at_level(logging.INFO):
        response = client.get(
            f"{base}/aps?cycle_id={CYCLE}", base_url="https://localhost"
        )
    assert response.status_code == 403
    assert [call[0] for call in source.calls] == ["summary"]
    denied = [
        record for record in caplog.records
        if record.getMessage() == "admin.current_traffic_query_completed"
        and getattr(record, "route_name", None) == "current_traffic_ap_page"
    ]
    assert denied and not hasattr(denied[-1], "site_id")


def test_traffic_source_absence_isolated_from_admin_runtime(tmp_path):
    app = traffic_app(tmp_path, None, logging.getLogger("traffic-missing"))
    runtime = app.extensions["admin_web_runtime"]
    assert runtime.state == "active"
    client = app.test_client()
    assert login(client).status_code == 302
    response = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/current-traffic/summary",
        base_url="https://localhost",
    )
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "source_unavailable"
    assert client.get(f"/admin/sites/{SITE_ID}/", base_url="https://localhost").status_code == 200


def test_home_template_delivers_traffic_only_when_enabled(tmp_path):
    source = TrafficSource()
    enabled = traffic_app(tmp_path, source, logging.getLogger("traffic-template"))
    client = enabled.test_client(); assert login(client).status_code == 302
    text = client.get(f"/admin/sites/{SITE_ID}/", base_url="https://localhost").get_data(as_text=True)
    assert 'data-home-traffic-enabled="true"' in text
    assert "Download Now" in text and "not an Internet-only measurement" in text
    disabled = traffic_app(tmp_path, source, logging.getLogger("traffic-template-off"), traffic="false")
    other = disabled.test_client(); assert login(other).status_code == 302
    text = other.get(f"/admin/sites/{SITE_ID}/", base_url="https://localhost").get_data(as_text=True)
    assert 'data-home-traffic-enabled="false"' in text
    assert "Download Now" not in text


def test_task_b_has_no_omada_or_observation_write_dependency():
    paths = [
        "app/admin_web/current_traffic_serialization.py",
        "app/admin_web/query_service.py",
        "app/admin_web/routes.py",
        "app/admin_web/static/admin.js",
    ]
    combined = "\n".join(open(path, encoding="utf-8").read() for path in paths)
    assert "OmadaProvider" not in combined
    assert "app.integrations.omada" not in combined
    assert "create_cycle(" not in combined
    assert "store_ap" not in combined
