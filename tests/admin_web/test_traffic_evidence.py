from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from app.admin_web import create_admin_web_runtime
from app.admin_web.config import AdminWebConfigError, admin_web_config_from_settings
from app.admin_web.current_traffic_serialization import (
    CurrentTrafficSerializationError,
    serialize_current_traffic_summary,
)
from app.admin_web.query_service import AdminQueryResponse
from app.admin_web.query_service import (
    AdminQueryDeadline,
    AdminQueryIntegrityUnavailable,
    AdminQueryUnavailable,
)
from app.admin_web.traffic_evidence import TrafficEvidenceAggregator
from app.admin_web.traffic_evidence_serialization import (
    PRODUCT_IDS,
    TrafficEvidenceSerializationError,
    project_completed,
    scope_completed,
    scope_current,
    scope_historical,
    scope_online,
    serialize_traffic_evidence,
)
from app.admin_web.traffic_network_ranges import resolve_traffic_network_range
from app.admin_web.policy import AdminAccessPolicy
from app.analytics.source_gateway import (
    AnalyticsQueryDeadlineExceeded,
    QueryDeadline,
)
from app.analytics import (
    CompletedGuestSessionTrafficItem,
    CompletedGuestSessionTrafficPage,
    CompletedGuestSessionTrafficRange,
    CompletedGuestSessionTrafficResult,
    CompletedGuestSessionTrafficSourceHealth,
    CurrentGuestTrafficItem,
    CurrentGuestTrafficPage,
    CurrentGuestTrafficResult,
)

from .conftest import SITE_ID, enabled_settings, login
from .test_home_traffic import TrafficSource, traffic_summary
from .test_traffic_ap_share import (
    ShareSource,
    _app as _ap_share_app,
    _url as _ap_share_url,
)


def _config(**values):
    defaults = dict(
        traffic_history_enabled=False,
        traffic_statistics_enabled=False,
        traffic_peak_enabled=False,
        traffic_by_ap_enabled=False,
        traffic_ap_share_enabled=False,
        traffic_online_guests_enabled=False,
        traffic_completed_sessions_enabled=False,
    )
    defaults.update(values)
    return SimpleNamespace(**defaults)


def _resolved(range_id="24h"):
    return resolve_traffic_network_range(
        range_id, datetime(2026, 9, 7, 10, tzinfo=timezone.utc)
    )


def _current_value():
    raw = traffic_summary(mode="complete")
    return raw, serialize_current_traffic_summary(raw, SITE_ID)


def _historical_value():
    counts = {
        "candidate_interval_count": 2,
        "accepted_interval_count": 2,
        "accepted_interval_seconds": 120.0,
        "interval_coverage_ratio": 120 / 86400,
        "excluded_gap_interval_count": 0,
        "excluded_source_transition_interval_count": 0,
        "invalid_period_interval_count": 0,
        "accepted_peak_sample_count": 3,
        "leading_unweighted_seconds": 86280.0,
        "trailing_unweighted_seconds": 0.0,
    }
    return {
        "status": "ok",
        "range": {
            "metric_version": "network_traffic_history.v1",
            "source_kind": "observation_ap_dynamic",
        },
        "coverage": {
            "source_watermark_utc": "2026-09-07T10:00:00.000Z",
            "source_age_seconds": 0.0,
            "bucket_count": 288,
            "complete_bucket_count": 288,
            "partial_bucket_count": 0,
            "missing_bucket_count": 0,
            "canonical_cycle_count": 3,
            "complete_site_sample_count": 3,
            "excluded_site_sample_count": 0,
            "gap_bucket_count": 0,
            "source_transition_count": 0,
        },
        "quality": {
            name: 0 for name in (
                "partial_cycle_count", "failed_cycle_count",
                "shutdown_cycle_count", "abandoned_cycle_count",
                "running_cycle_count", "no_baseline_count",
                "counter_reset_count", "gap_too_large_count",
                "invalid_elapsed_count", "source_unavailable_count",
                "source_skew_excluded_sample_count", "integrity_failure_count",
            )
        },
        "period_statistics": {
            "status": "ok",
            "metric_version": "network_traffic_period_statistics.v1",
            "average_method": "right_endpoint_sample_hold_time_weighted.v1",
            "peak_method": "max_accepted_complete_site_sample.v1",
            "interval_evidence": counts,
        },
        "peak_load": {
            "status": "ok",
            "metric_version": "network_traffic_peak_load.v1",
            "peak_value_method": "max_accepted_complete_site_sample.v1",
            "peak_tie_break_method": "earliest_peak_sample_at.v1",
            "sample_timestamp_semantics": "cycle_finished_at",
            "events": {
                name: {
                    "value_mbps": 1.0,
                    "sample_at_utc": "2026-09-07T09:59:00.000Z",
                } for name in ("download", "upload", "total")
            },
            "busiest_bucket": {"status": "ok"},
            "busiest_hour": {"status": "ok"},
        },
        "ap_traffic": {
            "status": "ok",
            "metric_version": "network_traffic_by_ap.v1",
            "population": {
                "population_method": "current_union_historical_validated.v1",
                "population_count": 1,
                "current_population_count": 1,
                "historical_population_count": 1,
                "supported_max_ap_count": 12,
                "returned_ap_count": 1,
                "population_complete": True,
            },
            "items": [{"status": "complete"}],
        },
        "ap_traffic_share": {
            "status": "ok",
            "metric_version": "network_traffic_ap_share.v1",
            "share_method": "accepted_site_interval_integrated_ap_contribution_ratio.v1",
            "temporal_method": "right_endpoint_sample_hold_time_weighted.v1",
            "presence_method": "accepted_selected_source_historical_presence_in_range.v1",
            "absence_method": "proven_population_member_absent_from_trusted_complete_site_sample_zero_contribution.v1",
            "population": {
                "population_method": "current_union_historical_validated.v1",
                "population_count": 1,
                "historical_population_count": 1,
                "current_population_status": "available",
                "current_population_count": 1,
                "supported_max_ap_count": 12,
                "returned_ap_count": 1,
                "population_complete": True,
            },
            "coverage": counts,
            "denominators": {
                "download_status": "positive",
                "upload_status": "positive",
                "total_status": "positive",
            },
        },
    }


def _online_insufficient_value(evaluated_at):
    item = CurrentGuestTrafficItem(
        client_mac="AA:BB:CC:DD:EE:01",
        name="Guest phone",
        ssid="Zefer_Parki",
        ap_mac="AA:BB:CC:DD:EE:10",
        download_mbps=None,
        upload_mbps=None,
        total_mbps=None,
        source_progress_status="unproven",
        connection_continuity_status="unproven",
        continuity_basis="none",
        download_reason="no_baseline",
        upload_reason="no_baseline",
        total_reason="no_baseline",
        rate_status="unavailable",
    )
    return CurrentGuestTrafficResult(
        metric_version="network_traffic_online_guest_current_rate.v1",
        population_method="fresh_complete_current_state_authorized_guest_scope.v1",
        rate_method="current_connection_counter_delta_interval_average.v1",
        baseline_method="nearest_previous_complete_same_site_scope_cycle.v1",
        continuity_method="omada_controller_connection_progress_v1",
        connection_boundary_observation="sampled_current_state_evidence_v1",
        unit="Mbps",
        site_id=SITE_ID,
        evaluated_at_utc=evaluated_at,
        current_cycle_id="11111111-1111-4111-8111-111111111111",
        baseline_cycle_id=None,
        source_scope_hash="a" * 64,
        current_capture_started_at="2026-09-07T09:59:50.000Z",
        baseline_capture_started_at=None,
        elapsed_seconds=None,
        status="insufficient_data",
        source_health_status="healthy",
        source_health_reason="within_freshness_window",
        rate_evidence_status="insufficient_data",
        population_complete=True,
        scoped_client_row_count=1,
        known_authorized_count=1,
        unknown_auth_count=0,
        population_count=1,
        supported_max_population=10_000,
        rate_valid_count=0,
        rate_partial_count=0,
        rate_unavailable_count=1,
        items=(item,),
        page=CurrentGuestTrafficPage(1, 1, None, "total_rate_desc"),
    )


def _completed_unavailable_value(resolved):
    return CompletedGuestSessionTrafficResult(
        metric_version="network_traffic_completed_guest_session_observed_bytes.v1",
        session_method="closed_visit_completion_cohort.v1",
        attribution_method="visit_window_observation_counter_interval_sum.v1",
        continuity_method="observation_uptime_progress.v1",
        unit="bytes",
        site_id=SITE_ID,
        range=CompletedGuestSessionTrafficRange(
            resolved.id, resolved.from_utc, resolved.to_utc,
            resolved.evaluated_at_utc,
        ),
        status="unavailable",
        source_health=CompletedGuestSessionTrafficSourceHealth(
            "unavailable", "not_required"
        ),
        page=CompletedGuestSessionTrafficPage(
            100, 0, None, "closed_at_desc_visit_id_desc.v1"
        ),
        items=(),
    )


def _completed_first_page_value(resolved, *, next_cursor):
    item = CompletedGuestSessionTrafficItem(
        visit_id="11111111-1111-4111-8111-111111111111",
        client_mac="AA:BB:CC:DD:EE:01",
        started_at="2026-09-07T09:55:00.000Z",
        closed_at="2026-09-07T09:59:00.000Z",
        duration_seconds=240,
        start_ssid="Zefer_Parki",
        final_ssid="Zefer_Parki",
        start_ap_mac="AA:BB:CC:DD:EE:10",
        final_ap_mac="AA:BB:CC:DD:EE:10",
        observed_download_bytes=500,
        observed_upload_bytes=200,
        observed_total_bytes=700,
        download_evidence_status="complete",
        upload_evidence_status="complete",
        traffic_evidence_status="complete",
        evidence_reason_codes=(),
        sample_count=3,
        accepted_download_interval_count=2,
        accepted_upload_interval_count=2,
        first_observed_at="2026-09-07T09:55:30.000Z",
        last_observed_at="2026-09-07T09:58:30.000Z",
    )
    return CompletedGuestSessionTrafficResult(
        metric_version="network_traffic_completed_guest_session_observed_bytes.v1",
        session_method="closed_visit_completion_cohort.v1",
        attribution_method="visit_window_observation_counter_interval_sum.v1",
        continuity_method="observation_uptime_progress.v1",
        unit="bytes",
        site_id=SITE_ID,
        range=CompletedGuestSessionTrafficRange(
            resolved.id, resolved.from_utc, resolved.to_utc,
            resolved.evaluated_at_utc,
        ),
        status="ok",
        source_health=CompletedGuestSessionTrafficSourceHealth(
            "healthy", "healthy"
        ),
        page=CompletedGuestSessionTrafficPage(
            100, 1, next_cursor, "closed_at_desc_visit_id_desc.v1"
        ),
        items=(item,),
    )


class _OnlineSource:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def get_current_guest_traffic(self, site_id, **kwargs):
        self.calls.append((site_id, kwargs))
        return replace(self.value, page=replace(self.value.page, limit=kwargs["limit"]))


class _CompletedSource:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def get_completed_guest_session_traffic(self, site_id, **kwargs):
        self.calls.append((site_id, kwargs))
        return replace(self.value, page=replace(self.value.page, limit=kwargs["limit"]))


def _app(tmp_path, *, evidence=True, current=None):
    source = current if current is not None else TrafficSource()
    runtime = create_admin_web_runtime(
        enabled_settings(
            web_admin_traffic_enabled="true",
            web_admin_traffic_evidence_enabled="true" if evidence else "false",
        ),
        SimpleNamespace(
            state="active", visit_service=object(), current_traffic_service=source
        ),
        SimpleNamespace(repository=SimpleNamespace(config=SimpleNamespace(db_path=tmp_path / "registry.sqlite3"))),
        SimpleNamespace(repository=SimpleNamespace(db_path=tmp_path / "visits.sqlite3")),
        SimpleNamespace(_repository=SimpleNamespace(db_path=tmp_path / "observations.sqlite3")),
        logging.getLogger("traffic-evidence-test"),
    )
    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    app.register_blueprint(runtime.blueprint)
    app.extensions["admin_web_runtime"] = runtime
    return app, source


def test_evidence_flag_defaults_off_and_depends_only_on_admin_traffic():
    assert admin_web_config_from_settings({"web_admin_enabled": "false"}).traffic_evidence_enabled is False
    config = admin_web_config_from_settings(enabled_settings(
        web_admin_traffic_enabled="true", web_admin_traffic_evidence_enabled="true"
    ))
    assert config.traffic_evidence_enabled is True
    with pytest.raises(AdminWebConfigError):
        admin_web_config_from_settings(enabled_settings(
            web_admin_traffic_enabled="false", web_admin_traffic_evidence_enabled="true"
        ))


def test_route_returns_current_evidence_and_fixed_disabled_inventory(tmp_path):
    app, source = _app(tmp_path)
    client = app.test_client()
    assert login(client).status_code == 302
    response = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/traffic/evidence?range=24h",
        base_url="https://localhost",
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["api_version"] == "admin.read.v1" and payload["page"] is None
    assert set(payload["result"]["products"]) == set(PRODUCT_IDS)
    assert payload["result"]["products"]["current"]["delivery_status"] == "available"
    assert all(
        payload["result"]["products"][name]["delivery_status"] == "not_attempted"
        for name in PRODUCT_IDS[1:]
    )
    assert len(source.calls) == 1
    assert source.calls[0][2]["evaluated_at_utc"] == payload["result"]["evaluated_at_utc"]
    assert len(response.data) <= 65_536


def test_security_and_feature_gate_precede_query_validation(
    tmp_path, monkeypatch,
):
    app, source = _app(tmp_path, evidence=False)
    url = f"/admin/api/v1/sites/{SITE_ID}/traffic/evidence?range=24h&range=7d"
    assert app.test_client().get(url, base_url="https://localhost").status_code == 401
    client = app.test_client(); assert login(client).status_code == 302
    monkeypatch.setattr(
        AdminAccessPolicy,
        "authorize",
        lambda *_args, **_kwargs: pytest.fail(
            "disabled Evidence must not evaluate capabilities"
        ),
    )
    assert client.get(url, base_url="https://localhost").status_code == 404
    assert source.calls == []


def test_evidence_requires_both_site_scoped_capabilities(
    tmp_path, monkeypatch,
):
    app, source = _app(tmp_path)
    client = app.test_client()
    assert login(client).status_code == 302
    original = AdminAccessPolicy.authorize

    def deny_devices(self, principal, capability, site_id):
        return capability != "admin.read.devices" and original(
            self, principal, capability, site_id
        )

    monkeypatch.setattr(AdminAccessPolicy, "authorize", deny_devices)
    response = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/traffic/evidence?range=24h",
        base_url="https://localhost",
    )
    assert response.status_code == 403
    assert source.calls == []


def test_evidence_composition_failure_is_fail_open_for_existing_traffic(
    tmp_path, monkeypatch,
):
    def fail(*_args, **_kwargs):
        raise TypeError("composition failed")
    monkeypatch.setattr(TrafficEvidenceAggregator, "__init__", fail)
    app, source = _app(tmp_path)
    runtime = app.extensions["admin_web_runtime"]
    assert runtime.state == "active"
    assert runtime.traffic_evidence_state == "unavailable"
    client = app.test_client(); assert login(client).status_code == 302
    current = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/traffic/current",
        base_url="https://localhost",
    )
    evidence = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/traffic/evidence?range=24h",
        base_url="https://localhost",
    )
    assert current.status_code == 200
    assert evidence.status_code == 503
    assert evidence.get_json()["error"]["code"] == "source_unavailable"
    assert len(source.calls) == 1


@pytest.mark.parametrize("query", ["", "range=1h", "range=24h&bad=1", "range=24h&range=7d"])
def test_enabled_route_rejects_noncanonical_query(tmp_path, query):
    app, source = _app(tmp_path)
    client = app.test_client(); assert login(client).status_code == 302
    suffix = f"?{query}" if query else ""
    response = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/traffic/evidence{suffix}",
        base_url="https://localhost",
    )
    assert response.status_code == 400
    assert source.calls == []


def test_historical_five_share_one_read_and_one_prefetched_current():
    current_calls = []
    historical_calls = []
    raw, current = _current_value()
    def read_current(*args, **kwargs):
        current_calls.append((args, kwargs)); return raw, current
    def read_historical(*args, **kwargs):
        historical_calls.append((args, kwargs)); return AdminQueryResponse(_historical_value())
    aggregator = TrafficEvidenceAggregator(
        config=_config(
            traffic_history_enabled=True, traffic_statistics_enabled=True,
            traffic_peak_enabled=True, traffic_by_ap_enabled=True,
            traffic_ap_share_enabled=True,
        ),
        read_current=read_current,
        read_historical=read_historical,
        online_service=None,
        completed_service=None,
        current_available=True,
        historical_available=True,
    )
    result = aggregator.get_evidence(
        SITE_ID, resolved_range=_resolved(), deadline=QueryDeadline.after(10)
    )
    assert len(current_calls) == len(historical_calls) == 1
    assert historical_calls[0][1]["prefetched_current"] is raw
    assert historical_calls[0][1]["requested_products"] == (
        "history", "statistics", "peak", "aps", "apshare"
    )
    assert all(result["products"][name]["delivery_status"] == "available" for name in PRODUCT_IDS[:6])


def test_ordinary_historical_ap_path_does_not_use_current_summary_serializer(
    tmp_path, monkeypatch,
):
    source = ShareSource()
    app = _ap_share_app(tmp_path, source, share=False, by_ap=True)
    client = app.test_client()
    assert login(client).status_code == 302

    def fail_if_called(*_args, **_kwargs):
        raise CurrentTrafficSerializationError(
            "ordinary Historical must not serialize Current summary"
        )

    monkeypatch.setattr(
        "app.admin_web.query_service.serialize_current_traffic_summary",
        fail_if_called,
    )
    response = client.get(
        _ap_share_url("range=24h&products=history,aps"),
        base_url="https://localhost",
    )
    assert response.status_code == 200
    assert len(source.calls) == 1
    assert source.calls[0][1]["include_ap_traffic"] is True


def test_group_failure_is_safe_and_independent():
    def fail_current(*_args, **_kwargs):
        from app.admin_web.query_service import AdminQueryUnavailable
        raise AdminQueryUnavailable()
    aggregator = TrafficEvidenceAggregator(
        config=_config(traffic_history_enabled=True),
        read_current=fail_current,
        read_historical=lambda *_args, **_kwargs: AdminQueryResponse(_historical_value()),
        online_service=None,
        completed_service=None,
        current_available=True,
        historical_available=True,
    )
    result = aggregator.get_evidence(
        SITE_ID, resolved_range=_resolved(), deadline=QueryDeadline.after(10)
    )
    assert result["products"]["current"]["failure_category"] == "source_unavailable"
    assert result["products"]["history"]["delivery_status"] == "available"


def test_completed_projection_counts_first_page_and_rejects_private_reason():
    base = {
        "status": "partial",
        "metric_version": "network_traffic_completed_guest_session_observed_bytes.v1",
        "session_method": "closed_visit_completion_cohort.v1",
        "attribution_method": "visit_window_observation_counter_interval_sum.v1",
        "continuity_method": "observation_uptime_progress.v1",
        "source_health": {"visits": "healthy", "observations": "healthy"},
        "items": [
            {"traffic_evidence_status": "complete", "evidence_reason_codes": []},
            {"traffic_evidence_status": "partial", "evidence_reason_codes": ["counter_reset"]},
        ],
    }
    result = project_completed(base)
    assert result["complete_count"] == result["partial_count"] == 1
    assert result["reason_counts"] == {"counter_reset": 1}
    base["items"][1]["evidence_reason_codes"] = ["private_database_detail"]
    with pytest.raises(TrafficEvidenceSerializationError):
        project_completed(base)


@pytest.mark.parametrize(("next_cursor", "has_more"), [(None, False), ("next", True)])
def test_completed_available_scope_uses_accepted_first_page(
    next_cursor, has_more,
):
    resolved = _resolved()
    raw, current = _current_value()
    completed = _CompletedSource(
        _completed_first_page_value(resolved, next_cursor=next_cursor)
    )
    aggregator = TrafficEvidenceAggregator(
        config=_config(traffic_completed_sessions_enabled=True),
        read_current=lambda *_args, **_kwargs: (raw, current),
        read_historical=lambda *_args, **_kwargs: None,
        online_service=None,
        completed_service=completed,
        current_available=True,
        historical_available=False,
    )
    result = aggregator.get_evidence(
        SITE_ID, resolved_range=resolved, deadline=QueryDeadline.after(10)
    )
    scope = result["products"]["completed_sessions"]["scope"]
    assert set(scope) == {
        "kind", "range_id", "from_utc", "to_utc", "evaluated_at_utc",
        "limit", "returned_count", "has_more",
    }
    assert scope == scope_completed(
        resolved, limit=100, returned_count=1, has_more=has_more
    )
    assert "cursor" not in scope
    assert "next_cursor" not in scope
    assert "page_limit" not in scope
    assert len(completed.calls) == 1
    broken = deepcopy(result)
    broken["products"]["completed_sessions"]["scope"]["returned_count"] = 0
    with pytest.raises(TrafficEvidenceSerializationError):
        serialize_traffic_evidence(broken, resolved_range=resolved)


def test_completed_disabled_and_failed_before_page_have_null_scope():
    resolved = _resolved()
    raw, current = _current_value()
    disabled = TrafficEvidenceAggregator(
        config=_config(),
        read_current=lambda *_args, **_kwargs: (raw, current),
        read_historical=lambda *_args, **_kwargs: None,
        online_service=None,
        completed_service=None,
        current_available=True,
        historical_available=False,
    ).get_evidence(SITE_ID, resolved_range=resolved, deadline=QueryDeadline.after(10))
    assert disabled["products"]["completed_sessions"]["scope"] is None

    class FailedCompleted:
        def get_completed_guest_session_traffic(self, *_args, **_kwargs):
            raise AdminQueryUnavailable("private source")

    failed = TrafficEvidenceAggregator(
        config=_config(traffic_completed_sessions_enabled=True),
        read_current=lambda *_args, **_kwargs: (raw, current),
        read_historical=lambda *_args, **_kwargs: None,
        online_service=None,
        completed_service=FailedCompleted(),
        current_available=True,
        historical_available=False,
    ).get_evidence(SITE_ID, resolved_range=resolved, deadline=QueryDeadline.after(10))
    completed = failed["products"]["completed_sessions"]
    assert completed["delivery_status"] == "failed"
    assert completed["scope"] is None


def test_outer_serializer_rejects_identifiers_and_impossible_wrapper():
    resolved = _resolved()
    raw, current = _current_value()
    scopes = {
        "current": scope_current(resolved.evaluated_at_utc),
        "online_guests": scope_online(resolved.evaluated_at_utc),
        "completed_sessions": None,
    }
    scopes.update({name: scope_historical(resolved) for name in PRODUCT_IDS[1:6]})
    products = {
        name: {
            "product_id": name,
            "exposure_status": "disabled",
            "delivery_status": "not_attempted",
            "scope": scopes[name],
            "evidence": None,
            "failure_category": None,
        } for name in PRODUCT_IDS
    }
    value = {
        "contract_version": "admin.traffic.evidence.v1",
        "evaluated_at_utc": resolved.evaluated_at_utc,
        "evidence_range": {"id": resolved.id, "from_utc": resolved.from_utc, "to_utc": resolved.to_utc},
        "products": products,
    }
    assert serialize_traffic_evidence(value, resolved_range=resolved)["products"]
    broken = deepcopy(value); broken["products"]["history"]["client_mac"] = "AA:BB:CC:DD:EE:FF"
    with pytest.raises(TrafficEvidenceSerializationError):
        serialize_traffic_evidence(broken, resolved_range=resolved)


def test_native_unavailable_partial_and_unsupported_states_remain_available():
    resolved = _resolved()
    raw, current = _current_value()
    historical = _historical_value()
    historical["status"] = "partial"
    historical["ap_traffic_share"]["status"] = "unsupported_population"
    historical["ap_traffic_share"]["population"].update({
        "population_count": 13,
        "historical_population_count": 13,
        "current_population_status": "unavailable",
        "current_population_count": None,
        "returned_ap_count": 0,
        "population_complete": False,
    })
    online = _OnlineSource(_online_insufficient_value(resolved.evaluated_at_utc))
    completed = _CompletedSource(_completed_unavailable_value(resolved))
    current_calls = []
    historical_calls = []

    def read_current(*args, **kwargs):
        current_calls.append((args, kwargs))
        return raw, current

    def read_historical(*args, **kwargs):
        historical_calls.append((args, kwargs))
        return AdminQueryResponse(historical)

    aggregator = TrafficEvidenceAggregator(
        config=_config(
            traffic_history_enabled=True,
            traffic_ap_share_enabled=True,
            traffic_online_guests_enabled=True,
            traffic_completed_sessions_enabled=True,
        ),
        read_current=read_current,
        read_historical=read_historical,
        online_service=online,
        completed_service=completed,
        current_available=True,
        historical_available=True,
    )
    result = aggregator.get_evidence(
        SITE_ID, resolved_range=resolved, deadline=QueryDeadline.after(10)
    )

    expected = {
        "history": "partial",
        "apshare": "unsupported_population",
        "online_guests": "insufficient_data",
        "completed_sessions": "unavailable",
    }
    for product_id, native_status in expected.items():
        product = result["products"][product_id]
        assert product["delivery_status"] == "available", (product_id, product)
        assert product["failure_category"] is None
        assert product["evidence"]["status"] == native_status
    assert len(current_calls) == len(historical_calls) == 1
    assert online.calls == [(SITE_ID, {
        "evaluated_at_utc": resolved.evaluated_at_utc,
        "limit": 1,
        "cursor": None,
    })]
    assert completed.calls[0][1]["limit"] == 100
    assert completed.calls[0][1]["cursor"] is None
    assert completed.calls[0][1]["range_id"] == resolved.id
    assert completed.calls[0][1]["evaluated_at_utc"] == resolved.evaluated_at_utc
    serialized = repr(result)
    assert "AA:BB:CC" not in serialized
    assert "client_mac" not in serialized


@pytest.mark.parametrize(
    ("error", "category"),
    [
        (AdminQueryUnavailable("private source path"), "source_unavailable"),
        (AdminQueryDeadline("private deadline detail"), "query_deadline"),
        (AdminQueryIntegrityUnavailable("private row detail"), "integrity_unavailable"),
        (RuntimeError("private stack detail"), "unexpected"),
    ],
)
def test_failure_categories_are_safe_and_preserve_independent_history(
    error, category,
):
    def fail_current(*_args, **_kwargs):
        raise error

    aggregator = TrafficEvidenceAggregator(
        config=_config(traffic_history_enabled=True),
        read_current=fail_current,
        read_historical=lambda *_args, **_kwargs: AdminQueryResponse(
            _historical_value()
        ),
        online_service=None,
        completed_service=None,
        current_available=True,
        historical_available=True,
    )
    result = aggregator.get_evidence(
        SITE_ID, resolved_range=_resolved(), deadline=QueryDeadline.after(10)
    )
    current = result["products"]["current"]
    assert current["delivery_status"] == "failed"
    assert current["evidence"] is None
    assert current["failure_category"] == category
    assert "private" not in repr(current)
    assert result["products"]["history"]["delivery_status"] == "available"


def test_runtime_unavailable_is_failed_without_invoking_current_reader():
    calls = []
    aggregator = TrafficEvidenceAggregator(
        config=_config(),
        read_current=lambda *_args, **_kwargs: calls.append(1),
        read_historical=lambda *_args, **_kwargs: None,
        online_service=None,
        completed_service=None,
        current_available=False,
        historical_available=False,
    )
    result = aggregator.get_evidence(
        SITE_ID, resolved_range=_resolved(), deadline=QueryDeadline.after(10)
    )
    assert calls == []
    assert result["products"]["current"]["failure_category"] == "runtime_unavailable"


def test_shared_deadline_stops_remaining_groups_without_owner_reads():
    raw, current = _current_value()
    historical_calls = []
    online = _OnlineSource(_online_insufficient_value(_resolved().evaluated_at_utc))
    completed = _CompletedSource(_completed_unavailable_value(_resolved()))

    class Deadline:
        calls = 0

        def require_remaining(self):
            self.calls += 1
            if self.calls > 1:
                raise AnalyticsQueryDeadlineExceeded("private deadline")

    aggregator = TrafficEvidenceAggregator(
        config=_config(
            traffic_history_enabled=True,
            traffic_online_guests_enabled=True,
            traffic_completed_sessions_enabled=True,
        ),
        read_current=lambda *_args, **_kwargs: (raw, current),
        read_historical=lambda *_args, **_kwargs: historical_calls.append(1),
        online_service=online,
        completed_service=completed,
        current_available=True,
        historical_available=True,
    )
    result = aggregator.get_evidence(
        SITE_ID, resolved_range=_resolved(), deadline=Deadline()
    )
    assert result["products"]["current"]["delivery_status"] == "available"
    for product_id in ("history", "online_guests", "completed_sessions"):
        assert result["products"][product_id]["failure_category"] == "query_deadline"
    assert historical_calls == []
    assert online.calls == []
    assert completed.calls == []


def test_route_resolves_range_once_and_uses_one_admin_execution_slot(
    tmp_path, monkeypatch,
):
    from app.admin_web import query_service as query_service_module

    app, _source = _app(tmp_path)
    runtime = app.extensions["admin_web_runtime"]
    original_controls = runtime.query_service._execution_controls
    original_resolver = query_service_module.resolve_traffic_network_range
    calls = {"run": 0, "resolve": 0}

    class CountingControls:
        def run(self, operation):
            calls["run"] += 1
            return original_controls.run(operation)

    def resolve_once(*args, **kwargs):
        calls["resolve"] += 1
        return original_resolver(*args, **kwargs)

    runtime.query_service._execution_controls = CountingControls()
    monkeypatch.setattr(
        query_service_module, "resolve_traffic_network_range", resolve_once
    )
    client = app.test_client()
    assert login(client).status_code == 302
    response = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/traffic/evidence?range=7d",
        base_url="https://localhost",
    )
    assert response.status_code == 200
    assert calls == {"run": 1, "resolve": 1}
    result = response.get_json()["result"]
    assert result["evidence_range"]["id"] == "7d"
    evaluated = result["evaluated_at_utc"]
    assert result["products"]["current"]["scope"]["evaluated_at_utc"] == evaluated
    assert result["products"]["online_guests"]["scope"]["evaluated_at_utc"] == evaluated
    assert all(
        result["products"][name]["scope"] == {
            "kind": "historical_range",
            "range_id": "7d",
            "from_utc": result["evidence_range"]["from_utc"],
            "to_utc": result["evidence_range"]["to_utc"],
            "evaluated_at_utc": evaluated,
        }
        for name in ("history", "statistics", "peak", "aps", "apshare")
    )
