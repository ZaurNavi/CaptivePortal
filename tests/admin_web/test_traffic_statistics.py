from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest

from app.admin_web.config import AdminWebConfigError, admin_web_config_from_settings
from app.admin_web.historical_traffic_serialization import (
    HistoricalTrafficSerializationError,
    serialize_historical_traffic,
)
from app.analytics import (
    HistoricalTrafficPeriodIntervalEvidence,
    HistoricalTrafficPeriodStatistics,
    HistoricalTrafficPeriodValues,
)

from .conftest import SITE_ID, enabled_settings, login
from .test_traffic_history import HistorySource, _app, _resolved, _result, _url


def _statistics(value, *, status="ok", average=(1.0, .5, 1.5), peak=(4.0, 2.0, 5.0),
                accepted=None, gap=0, transition=0, invalid=0):
    peak_count = value.coverage.complete_site_sample_count
    candidate = max(peak_count - 1, 0)
    accepted_count = (
        candidate - gap - transition - invalid if accepted is None else accepted
    )
    seconds = float(accepted_count * value.range.bucket_seconds)
    duration = (
        datetime.fromisoformat(value.range.to_utc.replace("Z", "+00:00"))
        - datetime.fromisoformat(value.range.from_utc.replace("Z", "+00:00"))
    ).total_seconds()
    return HistoricalTrafficPeriodStatistics(
        status=status,
        average=HistoricalTrafficPeriodValues(*average),
        peak=HistoricalTrafficPeriodValues(*peak),
        interval_evidence=HistoricalTrafficPeriodIntervalEvidence(
            range_seconds=duration,
            candidate_interval_count=candidate,
            accepted_interval_count=accepted_count,
            accepted_interval_seconds=seconds,
            interval_coverage_ratio=seconds / duration,
            excluded_gap_interval_count=gap,
            excluded_source_transition_interval_count=transition,
            invalid_period_interval_count=invalid,
            accepted_peak_sample_count=peak_count,
            leading_unweighted_seconds=0,
            trailing_unweighted_seconds=value.range.bucket_seconds,
        ),
    )


def _with_statistics(value=None, **kwargs):
    value = value or _result()
    return replace(value, period_statistics=_statistics(value, **kwargs))


class StatisticsSource(HistorySource):
    def get_site_history(self, site_id, **kwargs):
        value = super().get_site_history(site_id, **kwargs)
        if not kwargs.get("include_period_statistics"):
            return value
        return _with_statistics(value)


def test_statistics_flag_defaults_false_and_requires_full_hierarchy():
    assert admin_web_config_from_settings({}).traffic_statistics_enabled is False
    for overrides in (
        {"web_admin_traffic_statistics_enabled": "true"},
        {
            "web_admin_traffic_enabled": "false",
            "web_admin_traffic_history_enabled": "true",
            "web_admin_traffic_statistics_enabled": "true",
        },
        {
            "web_admin_traffic_enabled": "true",
            "web_admin_traffic_history_enabled": "false",
            "web_admin_traffic_statistics_enabled": "true",
        },
    ):
        with pytest.raises(AdminWebConfigError):
            admin_web_config_from_settings(enabled_settings(**overrides))


def test_statistics_serializer_projects_six_metrics_and_real_zero():
    value = _result()
    statistics = _statistics(
        value, average=(0.0, .5, .5), peak=(0.0, 2.0, 2.0)
    )
    result = serialize_historical_traffic(
        replace(value, period_statistics=statistics),
        SITE_ID,
        resolved_range=_resolved(),
        include_period_statistics=True,
    )
    assert result["period_statistics"]["average"] == {
        "download_mbps": 0.0, "upload_mbps": .5, "total_mbps": .5,
    }
    assert result["period_statistics"]["peak"] == {
        "download_mbps": 0.0, "upload_mbps": 2.0, "total_mbps": 2.0,
    }
    assert result["period_statistics"]["average_method"] == (
        "right_endpoint_sample_hold_time_weighted.v1"
    )


def test_statistics_serializer_accepts_partial_and_all_null_insufficient():
    partial_history = _result(status="partial", bucket_status="partial")
    partial = _with_statistics(partial_history, status="partial")
    projected = serialize_historical_traffic(
        partial, SITE_ID, resolved_range=_resolved(),
        include_period_statistics=True,
    )
    assert projected["period_statistics"]["status"] == "partial"

    empty_history = _result(status="insufficient_data", bucket_status="none")
    empty = _with_statistics(
        empty_history,
        status="insufficient_data",
        average=(None, None, None),
        peak=(None, None, None),
        accepted=0,
    )
    projected = serialize_historical_traffic(
        empty, SITE_ID, resolved_range=_resolved(),
        include_period_statistics=True,
    )
    assert projected["period_statistics"]["average"]["total_mbps"] is None


@pytest.mark.parametrize(
    "mutation",
    [
        lambda s: replace(s, average_method="wrong"),
        lambda s: replace(s, average=replace(s.average, total_mbps=99.0)),
        lambda s: replace(s, peak=replace(s.peak, total_mbps=99.0)),
        lambda s: replace(s, average=replace(s.average, download_mbps=float("nan"))),
        lambda s: replace(s, peak=replace(s.peak, upload_mbps=-1.0)),
        lambda s: replace(s, interval_evidence=replace(
            s.interval_evidence, interval_coverage_ratio=.1,
        )),
        lambda s: replace(s, interval_evidence=replace(
            s.interval_evidence, accepted_interval_seconds=999999,
        )),
        lambda s: replace(s, interval_evidence=replace(
            s.interval_evidence, candidate_interval_count=1,
        )),
        lambda s: replace(s, interval_evidence=replace(
            s.interval_evidence, accepted_interval_count=1,
        )),
        lambda s: replace(s, status="insufficient_data"),
    ],
)
def test_statistics_serializer_fails_closed_on_cross_field_corruption(mutation):
    value = _result()
    damaged = replace(value, period_statistics=mutation(_statistics(value)))
    with pytest.raises(HistoricalTrafficSerializationError):
        serialize_historical_traffic(
            damaged, SITE_ID, resolved_range=_resolved(),
            include_period_statistics=True,
        )


def test_statistics_route_flag_query_shape_security_and_single_service_call(tmp_path):
    source = StatisticsSource()
    disabled = _app(tmp_path, source).test_client()
    assert login(disabled).status_code == 302
    assert disabled.get(_url(), base_url="https://localhost").status_code == 200
    assert disabled.get(
        _url("range=24h&include=statistics"), base_url="https://localhost"
    ).status_code == 404
    assert len(source.calls) == 1

    source = StatisticsSource()
    client = _app(tmp_path, source, statistics=True).test_client()
    assert login(client).status_code == 302
    history = client.get(_url(), base_url="https://localhost")
    assert history.status_code == 200
    assert "period_statistics" not in history.get_json()["result"]
    combined = client.get(
        _url("range=24h&include=statistics"), base_url="https://localhost"
    )
    assert combined.status_code == 200
    assert combined.get_json()["result"]["period_statistics"]["status"] == "ok"
    seven_days = client.get(
        _url("range=7d&include=statistics"), base_url="https://localhost"
    )
    assert seven_days.status_code == 200
    assert seven_days.get_json()["result"]["range"]["id"] == "7d"
    assert len(source.calls) == 3
    assert source.calls[-1][1]["include_period_statistics"] is True
    assert source.calls[-1][1]["deadline"].expired() is False
    for query in (
        "range=24h&include=statistics&include=statistics",
        "range=24h&include=other",
        "range=24h&include=statistics&bad=1",
    ):
        assert client.get(_url(query), base_url="https://localhost").status_code == 400
    assert client.get(
        _url("range=24h&include=statistics", "f" * 24),
        base_url="https://localhost",
    ).status_code == 403
    assert len(source.calls) == 3


def test_statistics_serializer_failure_maps_combined_request_to_503(tmp_path):
    source = StatisticsSource()
    original = source.get_site_history

    def corrupted(site_id, **kwargs):
        value = original(site_id, **kwargs)
        if kwargs.get("include_period_statistics"):
            value = replace(
                value,
                period_statistics=replace(
                    value.period_statistics,
                    average=replace(value.period_statistics.average, total_mbps=99),
                ),
            )
        return value

    source.get_site_history = corrupted
    client = _app(tmp_path, source, statistics=True).test_client()
    assert login(client).status_code == 302
    response = client.get(
        _url("range=24h&include=statistics"), base_url="https://localhost"
    )
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "source_unavailable"


def test_statistics_template_is_feature_gated_without_second_range(tmp_path):
    enabled = _app(tmp_path, StatisticsSource(), statistics=True).test_client()
    assert login(enabled).status_code == 302
    body = enabled.get(
        f"/admin/sites/{SITE_ID}/traffic", base_url="https://localhost"
    ).get_data(as_text=True)
    assert 'id="traffic-statistics-panel"' in body
    assert body.count('id="traffic-network-range-24h"') == 1
    disabled = _app(tmp_path, StatisticsSource()).test_client()
    assert login(disabled).status_code == 302
    body = disabled.get(
        f"/admin/sites/{SITE_ID}/traffic", base_url="https://localhost"
    ).get_data(as_text=True)
    assert "traffic-statistics-panel" not in body
