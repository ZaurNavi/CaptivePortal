from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime
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
from app.admin_web.traffic_network_ranges import resolve_traffic_network_range
from app.analytics import (
    HistoricalTrafficBusiestBucket,
    HistoricalTrafficBusiestHour,
    HistoricalTrafficPeakEvent,
    HistoricalTrafficPeakLoad,
    HistoricalTrafficPeriodIntervalEvidence,
    HistoricalTrafficPeriodStatistics,
    HistoricalTrafficPeriodValues,
)

from .conftest import SITE_ID, enabled_settings, login
from .test_home_traffic import TrafficSource
from .test_traffic_history import EVALUATED, HistorySource, _result


def _peak_result(base=None):
    base = base or _result()
    first = base.buckets[0]
    winner = base.buckets[1]
    statistics = HistoricalTrafficPeriodStatistics(
        status="ok",
        average=HistoricalTrafficPeriodValues(1.25, .25, 1.5),
        peak=HistoricalTrafficPeriodValues(1.25, .25, 1.5),
        interval_evidence=HistoricalTrafficPeriodIntervalEvidence(
            range_seconds=(duration := (288 * 300 if base.range.bucket_count == 288 else 672 * 900)),
            candidate_interval_count=base.range.bucket_count - 1,
            accepted_interval_count=base.range.bucket_count - 1,
            accepted_interval_seconds=duration - base.range.bucket_seconds,
            interval_coverage_ratio=(duration - base.range.bucket_seconds) / duration,
            excluded_gap_interval_count=0,
            excluded_source_transition_interval_count=0,
            invalid_period_interval_count=0,
            accepted_peak_sample_count=base.range.bucket_count,
            leading_unweighted_seconds=0,
            trailing_unweighted_seconds=base.range.bucket_seconds,
        ),
    )
    peak = HistoricalTrafficPeakLoad(
        status="ok",
        events={
            "download": HistoricalTrafficPeakEvent(1.25, winner.bucket_start_utc, "wired", base.range.bucket_count - 1),
            "upload": HistoricalTrafficPeakEvent(.25, first.bucket_start_utc, "wired", base.range.bucket_count),
            "total": HistoricalTrafficPeakEvent(1.5, winner.bucket_start_utc, "wired", base.range.bucket_count - 1),
        },
        busiest_bucket=HistoricalTrafficBusiestBucket(
            "ok", winner.bucket_start_utc, winner.bucket_end_utc, 1.5,
            "wired", base.range.bucket_count - 1,
        ),
        busiest_hour=HistoricalTrafficBusiestHour(
            "ok", base.range.from_utc,
            base.buckets[11].bucket_end_utc, 3600, 1.5, 3600.0, "wired",
        ),
    )
    return replace(base, period_statistics=statistics, peak_load=peak)


class PeakSource:
    def __init__(self):
        self.calls = []

    def get_site_history(self, site_id, **kwargs):
        self.calls.append((site_id, kwargs))
        evaluated = datetime.fromisoformat(
            kwargs["evaluated_at_utc"].replace("Z", "+00:00")
        )
        duration = (
            datetime.fromisoformat(kwargs["to_utc"].replace("Z", "+00:00"))
            - datetime.fromisoformat(kwargs["from_utc"].replace("Z", "+00:00"))
        )
        base = _result("7d" if duration.days == 7 else "24h", evaluated=evaluated)
        value = _peak_result(base)
        if not kwargs.get("include_peak_load"):
            value = replace(value, peak_load=None)
        if not kwargs.get("include_period_statistics"):
            value = replace(value, period_statistics=None)
        return value


def _app(tmp_path, source, *, peak=True):
    settings = enabled_settings(
        web_admin_traffic_enabled="true",
        web_admin_traffic_history_enabled="true",
        web_admin_traffic_statistics_enabled="true",
        web_admin_traffic_peak_enabled=str(peak).lower(),
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
        logging.getLogger("traffic-peak-test"),
    )
    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    app.register_blueprint(runtime.blueprint)
    app.extensions["admin_web_runtime"] = runtime
    return app


def _url(query, site=SITE_ID):
    return f"/admin/api/v1/sites/{site}/traffic/history?{query}"


def test_peak_flag_defaults_false_and_requires_all_parent_products():
    assert admin_web_config_from_settings({}).traffic_peak_enabled is False
    with pytest.raises(AdminWebConfigError, match="TRAFFIC_PEAK_ENABLED requires"):
        admin_web_config_from_settings(enabled_settings(
            web_admin_traffic_enabled="true",
            web_admin_traffic_history_enabled="true",
            web_admin_traffic_statistics_enabled="false",
            web_admin_traffic_peak_enabled="true",
        ))


def test_peak_include_security_feature_gate_and_exact_forms(tmp_path):
    source = PeakSource()
    anonymous = _app(tmp_path, source).test_client()
    assert anonymous.get(_url("range=24h&include=statistics,peak"), base_url="https://localhost").status_code == 401

    disabled_source = PeakSource()
    disabled = _app(tmp_path, disabled_source, peak=False).test_client()
    assert login(disabled).status_code == 302
    assert disabled.get(_url("range=24h&include=statistics,peak"), base_url="https://localhost").status_code == 404
    assert disabled.get(_url("range=24h&include=statistics"), base_url="https://localhost").status_code == 200

    client = _app(tmp_path, source).test_client()
    assert login(client).status_code == 302
    assert client.get(_url("range=24h&include=statistics,peak", "f" * 24), base_url="https://localhost").status_code == 403
    for include in ("peak", "peak,statistics", "statistics,peak,peak", "statistics, peak", "unknown"):
        assert client.get(_url(f"range=24h&include={include}"), base_url="https://localhost").status_code == 400
    response = client.get(_url("range=24h&include=statistics,peak"), base_url="https://localhost")
    assert response.status_code == 200
    assert response.get_json()["result"]["peak_load"]["status"] == "ok"
    assert source.calls[-1][1]["include_period_statistics"] is True
    assert source.calls[-1][1]["include_peak_load"] is True


def test_peak_serializer_exact_methods_identity_and_no_hour_occurrence_count():
    resolved = resolve_traffic_network_range("24h", EVALUATED)
    result = serialize_historical_traffic(
        _peak_result(), SITE_ID, resolved_range=resolved,
        include_period_statistics=True, include_peak_load=True,
    )
    peak = result["peak_load"]
    assert peak["events"]["total"]["value_mbps"] == result["period_statistics"]["peak"]["total_mbps"]
    assert peak["busiest_bucket"]["method"] == "max_complete_history_bucket_total_mean.v1"
    assert peak["busiest_hour"]["method"] == "max_complete_rolling_3600s_average_total_sample_hold.v1"
    assert "occurrence_count" not in peak["busiest_hour"]


def test_peak_serializer_accepts_exact_insufficient_bucket_and_hour_shapes():
    resolved = resolve_traffic_network_range("24h", EVALUATED)
    base = _peak_result()
    missing_bucket = HistoricalTrafficBusiestBucket(
        "insufficient_data", None, None, None, None, 0,
    )
    missing_hour = HistoricalTrafficBusiestHour(
        "insufficient_data", None, None, 3600, None, None, None,
    )
    bucket_result = replace(
        base,
        peak_load=replace(
            base.peak_load, status="partial", busiest_bucket=missing_bucket,
        ),
    )
    hour_result = replace(
        base,
        peak_load=replace(
            base.peak_load, status="partial", busiest_hour=missing_hour,
        ),
    )
    assert serialize_historical_traffic(
        bucket_result, SITE_ID, resolved_range=resolved,
        include_period_statistics=True, include_peak_load=True,
    )["peak_load"]["busiest_bucket"]["status"] == "insufficient_data"
    assert serialize_historical_traffic(
        hour_result, SITE_ID, resolved_range=resolved,
        include_period_statistics=True, include_peak_load=True,
    )["peak_load"]["busiest_hour"]["status"] == "insufficient_data"


def test_peak_serializer_rejects_insufficient_load_with_mixed_ok_products():
    resolved = resolve_traffic_network_range("24h", EVALUATED)
    base = _peak_result()
    invalid = replace(base, peak_load=replace(base.peak_load, status="insufficient_data"))
    with pytest.raises(HistoricalTrafficSerializationError):
        serialize_historical_traffic(
            invalid, SITE_ID, resolved_range=resolved,
            include_period_statistics=True, include_peak_load=True,
        )


@pytest.mark.parametrize("invalid_number", [float("nan"), float("inf"), float("-inf"), -1.0])
def test_peak_serializer_rejects_malformed_numeric_values(invalid_number):
    resolved = resolve_traffic_network_range("24h", EVALUATED)
    base = _peak_result()
    events = dict(base.peak_load.events)
    events["download"] = replace(events["download"], value_mbps=invalid_number)
    invalid = replace(base, peak_load=replace(base.peak_load, events=events))
    with pytest.raises(HistoricalTrafficSerializationError):
        serialize_historical_traffic(
            invalid, SITE_ID, resolved_range=resolved,
            include_period_statistics=True, include_peak_load=True,
        )


def test_peak_template_is_subordinate_and_absent_when_disabled(tmp_path):
    source = HistorySource(_peak_result())
    enabled = _app(tmp_path, source).test_client()
    assert login(enabled).status_code == 302
    body = enabled.get(f"/admin/sites/{SITE_ID}/traffic", base_url="https://localhost").get_data(as_text=True)
    assert 'id="traffic-peak-panel"' in body and "Busiest 60 Minutes" in body
    assert body.count("Average Total") >= 2
    assert 'id="traffic-peak-source-transitions"' in body
    disabled = _app(tmp_path, source, peak=False).test_client()
    assert login(disabled).status_code == 302
    body = disabled.get(f"/admin/sites/{SITE_ID}/traffic", base_url="https://localhost").get_data(as_text=True)
    assert 'id="traffic-peak-panel"' not in body
