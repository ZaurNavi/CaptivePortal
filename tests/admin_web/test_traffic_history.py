from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from app.admin_web import create_admin_web_runtime
from app.admin_web.config import AdminWebConfigError, admin_web_config_from_settings
from app.admin_web.historical_traffic_serialization import (
    HistoricalTrafficSerializationError,
    serialize_historical_traffic,
)
from app.admin_web.query_service import AdminQueryBusy, AdminQueryDeadline
from app.admin_web.traffic_network_ranges import resolve_traffic_network_range
from app.analytics import (
    HistoricalSiteTraffic,
    HistoricalTrafficBucket,
    HistoricalTrafficCoverage,
    HistoricalTrafficQuality,
    HistoricalTrafficRange,
    HistoricalTrafficSourceSelection,
    HistoricalTrafficSourceUnavailable,
    HistoricalTrafficValidationError,
)
from app.analytics.validation import format_utc

from .conftest import SITE_ID, enabled_settings, login
from .test_home_traffic import TrafficSource


UTC = timezone.utc
EVALUATED = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)


def _resolved(range_id="24h", evaluated=EVALUATED):
    return resolve_traffic_network_range(range_id, evaluated)


def _result(
    range_id="24h", *, status="ok", bucket_status="complete",
    evaluated=EVALUATED, canonical_none=False,
):
    resolved = _resolved(range_id, evaluated)
    bucket_seconds, bucket_count = (300, 288) if range_id == "24h" else (900, 672)
    start = datetime.fromisoformat(resolved.from_utc.replace("Z", "+00:00"))
    buckets = []
    for index in range(bucket_count):
        bucket_start = start + timedelta(seconds=index * bucket_seconds)
        bucket_end = bucket_start + timedelta(seconds=bucket_seconds)
        empty = bucket_status == "none"
        canonical = 1 if (not empty or canonical_none) else 0
        selected = "wired" if (not empty or canonical_none) else None
        selection_reason = (
            "primary_preferred_tie_or_higher"
            if empty and canonical_none
            else "no_canonical_samples" if empty
            else "primary_full_coverage"
        )
        buckets.append(HistoricalTrafficBucket(
            bucket_start_utc=format_utc(bucket_start),
            bucket_end_utc=format_utc(bucket_end),
            download_mbps=None if empty else (0.0 if index == 0 else 1.25),
            upload_mbps=None if empty else 0.25,
            total_mbps=None if empty else (0.25 if index == 0 else 1.5),
            status=bucket_status,
            selected_source=selected,
            selection_reason=selection_reason,
            source_changed_from_previous=False,
            canonical_cycle_count=canonical,
            complete_site_sample_count=0 if empty else 1,
            excluded_site_sample_count=canonical if empty else 0,
            total_ap_opportunities=canonical,
            selected_pair_valid_ap_opportunities=0 if empty else 1,
            first_complete_sample_at=None if empty else format_utc(bucket_start),
            last_complete_sample_at=None if empty else format_utc(bucket_end - timedelta(seconds=1)),
            leading_gap_seconds=bucket_seconds if empty else 0.0,
            trailing_gap_seconds=bucket_seconds if empty else 0.0,
            max_inter_sample_gap_seconds=0.0,
            gap_count_over_threshold=1 if empty else 0,
            selected_source_skew_excluded_sample_count=0,
            rate_reason_counts={
                "ok": 1 if not empty else 0,
                "no_baseline": 0,
                "counter_reset": 0,
                "gap_too_large": 0,
                "invalid_elapsed": 0,
                "source_unavailable": 1 if empty else 0,
            },
            source_selection=HistoricalTrafficSourceSelection(
                primary_source="wired",
                selected_source=selected,
                selection_reason=selection_reason,
                wired_complete_site_cycle_count=0 if empty else 1,
                lan_complete_site_cycle_count=0,
                wired_pair_valid_ap_opportunities=0 if empty else 1,
                lan_pair_valid_ap_opportunities=0,
            ),
        ))
    complete = bucket_count if bucket_status == "complete" else 0
    partial = bucket_count if bucket_status == "partial" else 0
    missing = bucket_count if bucket_status == "none" else 0
    canonical_count = bucket_count if (bucket_status != "none" or canonical_none) else 0
    return HistoricalSiteTraffic(
        status=status,
        range=HistoricalTrafficRange(
            site_id=SITE_ID,
            from_utc=resolved.from_utc,
            to_utc=resolved.to_utc,
            evaluated_at_utc=resolved.evaluated_at_utc,
            bucket_seconds=bucket_seconds,
            bucket_count=bucket_count,
            max_site_sample_source_skew_seconds=60,
        ),
        buckets=tuple(buckets),
        coverage=HistoricalTrafficCoverage(
            status={"ok": "complete", "partial": "partial", "insufficient_data": "none"}[status],
            available_from_utc=resolved.from_utc,
            available_through_utc=resolved.to_utc,
            source_watermark_utc=resolved.to_utc,
            source_age_seconds=0.0,
            bucket_count=bucket_count,
            complete_bucket_count=complete,
            partial_bucket_count=partial,
            missing_bucket_count=missing,
            canonical_cycle_count=canonical_count,
            complete_site_sample_count=0 if bucket_status == "none" else bucket_count,
            excluded_site_sample_count=bucket_count if canonical_none else 0,
            gap_bucket_count=missing,
            source_transition_count=0,
        ),
        quality=HistoricalTrafficQuality(
            partial_cycle_count=0, failed_cycle_count=0,
            shutdown_cycle_count=0, abandoned_cycle_count=0,
            running_cycle_count=0, no_baseline_count=0,
            counter_reset_count=0, gap_too_large_count=0,
            invalid_elapsed_count=0, source_unavailable_count=missing,
            source_skew_excluded_sample_count=0, integrity_failure_count=0,
        ),
    )


class HistorySource:
    def __init__(self, value=None, error=None):
        self.value = value or _result()
        self.error = error
        self.calls = []

    def get_site_history(self, site_id, **kwargs):
        self.calls.append((site_id, kwargs))
        if self.error:
            raise self.error
        if self.value is not None and self.value.range.evaluated_at_utc == kwargs["evaluated_at_utc"]:
            return self.value
        evaluated = datetime.fromisoformat(kwargs["evaluated_at_utc"].replace("Z", "+00:00"))
        range_id = "7d" if (
            datetime.fromisoformat(kwargs["to_utc"].replace("Z", "+00:00"))
            - datetime.fromisoformat(kwargs["from_utc"].replace("Z", "+00:00"))
        ) == timedelta(days=7) else "24h"
        return _result(range_id, evaluated=evaluated)


def _app(tmp_path, source, *, master=True, history=True, statistics=False):
    settings = enabled_settings(
        web_admin_traffic_enabled=str(master).lower(),
        web_admin_traffic_history_enabled=str(history).lower(),
        web_admin_traffic_statistics_enabled=str(statistics).lower(),
        web_admin_home_live_enabled="false",
        web_admin_home_traffic_enabled="false",
    )
    runtime = create_admin_web_runtime(
        settings,
        SimpleNamespace(
            state="active", visit_service=object(),
            current_traffic_service=TrafficSource(),
            historical_traffic_service=source,
        ),
        SimpleNamespace(repository=SimpleNamespace(config=SimpleNamespace(db_path=tmp_path / "registry.sqlite3"))),
        SimpleNamespace(repository=SimpleNamespace(db_path=tmp_path / "visits.sqlite3")),
        SimpleNamespace(_repository=SimpleNamespace(db_path=tmp_path / "observations.sqlite3")),
        logging.getLogger("traffic-history-test"),
    )
    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    app.register_blueprint(runtime.blueprint)
    app.extensions["admin_web_runtime"] = runtime
    return app


def _url(query="range=24h", site_id=SITE_ID):
    return f"/admin/api/v1/sites/{site_id}/traffic/history?{query}"


def test_history_flag_defaults_false_and_requires_traffic():
    config = admin_web_config_from_settings({})
    assert config.traffic_history_enabled is False
    with pytest.raises(AdminWebConfigError, match="TRAFFIC_HISTORY_ENABLED requires"):
        admin_web_config_from_settings({"web_admin_traffic_history_enabled": "true"})
    with pytest.raises(AdminWebConfigError, match="TRAFFIC_HISTORY_ENABLED requires"):
        admin_web_config_from_settings(enabled_settings(
            web_admin_traffic_enabled="false",
            web_admin_traffic_history_enabled="true",
        ))


@pytest.mark.parametrize("range_id,count,bucket,duration", [("24h", 288, 300, 86400), ("7d", 672, 900, 604800)])
def test_range_resolver_and_serializer_exact_contract(range_id, count, bucket, duration):
    resolved = _resolved(range_id)
    value = _result(range_id)
    result = serialize_historical_traffic(value, SITE_ID, resolved_range=resolved)
    assert result["range"]["id"] == range_id
    assert result["range"]["bucket_count"] == count
    assert result["range"]["bucket_seconds"] == bucket
    assert len(result["buckets"]) == count
    assert datetime.fromisoformat(result["range"]["to_utc"].replace("Z", "+00:00")) - datetime.fromisoformat(result["range"]["from_utc"].replace("Z", "+00:00")) == timedelta(seconds=duration)
    assert result["buckets"][0]["download_mbps"] == 0.0


@pytest.mark.parametrize(
    "status,bucket_status,coverage",
    [("ok", "complete", "complete"), ("partial", "partial", "partial"), ("insufficient_data", "none", "none")],
)
def test_serializer_preserves_result_and_missing_semantics(status, bucket_status, coverage):
    result = serialize_historical_traffic(
        _result(status=status, bucket_status=bucket_status),
        SITE_ID,
        resolved_range=_resolved(),
    )
    assert result["status"] == status and result["coverage"]["status"] == coverage
    if bucket_status == "none":
        assert result["buckets"][0]["selected_source"] is None
        assert result["buckets"][0]["download_mbps"] is None


def test_none_bucket_preserves_selected_source_provenance_when_canonical_cycles_exist():
    result = serialize_historical_traffic(
        _result(
            status="insufficient_data",
            bucket_status="none",
            canonical_none=True,
        ),
        SITE_ID,
        resolved_range=_resolved(),
    )
    assert result["buckets"][0]["status"] == "none"
    assert result["buckets"][0]["selected_source"] == "wired"
    assert result["buckets"][0]["selection_reason"] == "primary_preferred_tie_or_higher"
    assert result["buckets"][0]["download_mbps"] is None


def test_serializer_rejects_cross_field_corruption():
    value = _result()
    bad_total = replace(value.buckets[0], total_mbps=99.0)
    with pytest.raises(HistoricalTrafficSerializationError):
        serialize_historical_traffic(replace(value, buckets=(bad_total, *value.buckets[1:])), SITE_ID, resolved_range=_resolved())
    with pytest.raises(HistoricalTrafficSerializationError):
        serialize_historical_traffic(replace(value, range=replace(value.range, unit="MBps")), SITE_ID, resolved_range=_resolved())
    with pytest.raises(HistoricalTrafficSerializationError):
        serialize_historical_traffic(replace(value, coverage=replace(value.coverage, missing_bucket_count=1)), SITE_ID, resolved_range=_resolved())


@pytest.mark.parametrize(
    "field",
    [
        "complete_site_sample_count",
        "excluded_site_sample_count",
        "gap_bucket_count",
        "source_transition_count",
    ],
)
def test_serializer_rejects_derived_coverage_aggregate_mismatch(field):
    value = _result()
    damaged = replace(
        value.coverage,
        **{field: getattr(value.coverage, field) + 1},
    )
    with pytest.raises(HistoricalTrafficSerializationError):
        serialize_historical_traffic(
            replace(value, coverage=damaged),
            SITE_ID,
            resolved_range=_resolved(),
        )


@pytest.mark.parametrize("invalid", [-1.0, float("nan"), float("inf")])
def test_serializer_rejects_invalid_numeric_values(invalid):
    value = _result()
    damaged = replace(value.buckets[0], download_mbps=invalid)
    with pytest.raises(HistoricalTrafficSerializationError):
        serialize_historical_traffic(
            replace(value, buckets=(damaged, *value.buckets[1:])),
            SITE_ID,
            resolved_range=_resolved(),
        )


def test_history_route_security_flags_and_query_validation(tmp_path):
    source = HistorySource()
    anonymous = _app(tmp_path, source).test_client()
    assert anonymous.get(_url("range=24h&range=7d"), base_url="https://localhost").status_code == 401
    disabled = _app(tmp_path, source, history=False).test_client()
    assert login(disabled).status_code == 302
    assert disabled.get(_url("range=24h&range=7d"), base_url="https://localhost").status_code == 404
    assert source.calls == []

    master_disabled = _app(tmp_path, source, master=False, history=False).test_client()
    assert login(master_disabled).status_code == 302
    assert master_disabled.get(
        _url("range=24h&range=7d"), base_url="https://localhost"
    ).status_code == 404
    assert source.calls == []
    client = _app(tmp_path, source).test_client()
    assert login(client).status_code == 302
    assert client.get(_url("range=24h", "f" * 24), base_url="https://localhost").status_code == 403
    for query in ("", "range=30d", "range=24h&range=7d", "range=24h&bad=1"):
        assert client.get(_url(query), base_url="https://localhost").status_code == 400
    assert source.calls == []


def test_history_route_calls_read_service_with_server_range_and_deadline(tmp_path):
    source = HistorySource()
    client = _app(tmp_path, source).test_client()
    assert login(client).status_code == 302
    response = client.get(_url(), base_url="https://localhost")
    assert response.status_code == 200
    assert response.get_json()["result"]["range"]["id"] == "24h"
    seven_days = client.get(_url("range=7d"), base_url="https://localhost")
    assert seven_days.status_code == 200
    assert seven_days.get_json()["result"]["range"]["id"] == "7d"
    assert len(seven_days.data) < 1_048_576
    assert len(source.calls) == 2
    site, kwargs = source.calls[0]
    assert site == SITE_ID
    assert kwargs["evaluated_at_utc"] == kwargs["to_utc"]
    assert "bucket_seconds" not in kwargs
    assert kwargs["deadline"].expired() is False
    assert "bucket_seconds" not in source.calls[1][1]


@pytest.mark.parametrize(
    "error,code,status,retry",
    [
        (HistoricalTrafficValidationError("bad"), "invalid_request", 400, None),
        (HistoricalTrafficSourceUnavailable("bad"), "source_unavailable", 503, None),
        (AdminQueryBusy(), "concurrency_limit", 429, "1"),
        (AdminQueryDeadline(), "query_deadline", 503, None),
    ],
)
def test_history_error_mapping(tmp_path, monkeypatch, error, code, status, retry):
    source = HistorySource(error=error)
    app = _app(tmp_path, source)
    if isinstance(error, (AdminQueryBusy, AdminQueryDeadline)):
        monkeypatch.setattr(app.extensions["admin_web_runtime"].query_service, "historical_traffic_history", lambda *_args, **_kwargs: (_ for _ in ()).throw(error))
    client = app.test_client()
    assert login(client).status_code == 302
    response = client.get(_url(), base_url="https://localhost")
    assert response.status_code == status
    assert response.get_json()["error"]["code"] == code
    assert response.headers.get("Retry-After") == retry


def test_history_absent_source_and_template_flag_boundary(tmp_path):
    enabled_app = _app(tmp_path, None)
    assert enabled_app.extensions["admin_web_runtime"].state == "active"
    enabled = enabled_app.test_client()
    assert login(enabled).status_code == 302
    assert enabled.get(_url(), base_url="https://localhost").status_code == 503
    assert enabled.get(
        f"/admin/api/v1/sites/{SITE_ID}/traffic/current",
        base_url="https://localhost",
    ).status_code == 200
    body = enabled.get(f"/admin/sites/{SITE_ID}/traffic", base_url="https://localhost").get_data(as_text=True)
    assert 'id="traffic-history-panel"' in body
    assert 'id="traffic-network-range-24h"' in body
    disabled = _app(tmp_path, None, history=False).test_client()
    assert login(disabled).status_code == 302
    body = disabled.get(f"/admin/sites/{SITE_ID}/traffic", base_url="https://localhost").get_data(as_text=True)
    assert "traffic-history-panel" not in body and "traffic-network-range-24h" not in body
