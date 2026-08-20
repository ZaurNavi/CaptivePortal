"""Opt-in deterministic HTTP serialization benchmark for Analytics API."""

from __future__ import annotations

import ipaddress
import os
import time
from types import SimpleNamespace

import pytest
from flask import Flask

from app.analytics.api import API_PREFIX, create_analytics_blueprint
from app.analytics.api_config import AnalyticsApiConfig
from app.analytics.models import (
    AnalyticsProvenance,
    AnalyticsQuality,
    AnalyticsResult,
)


SITE = "0123456789abcdef01234567"
TOKEN = "benchmark-analytics-bearer-token-0001"
MAXIMUM = 1_048_576
RUNS = 250


class _Service:
    def __init__(self, result):
        self.result = result

    def get_visit_time_series(self, *args, **kwargs):
        return self.result


@pytest.mark.skipif(
    os.environ.get("RUN_ANALYTICS_API_BENCHMARK") != "1",
    reason="opt-in Analytics HTTP performance benchmark",
)
def test_168_hourly_buckets_250_authenticated_requests_p95_under_100ms():
    buckets = tuple(
        {
            "bucket_start_utc": f"2026-01-{1 + index // 24:02d}T{index % 24:02d}:00:00.000Z",
            "bucket_start_local": f"2026-01-{1 + index // 24:02d}T{index % 24:02d}:00:00+00:00",
            "visit_count": index % 17,
            "device_count": index % 13,
        }
        for index in range(168)
    )
    result = AnalyticsResult(
        status="ok",
        value=buckets,
        quality=AnalyticsQuality("strict_complete", accepted_rows=168),
        provenance=AnalyticsProvenance(
            site_id=SITE,
            from_utc="2026-01-01T00:00:00.000Z",
            to_utc="2026-01-08T00:00:00.000Z",
            evaluation_at_utc="2026-01-08T00:00:00.000Z",
            computed_at_utc="2026-01-08T00:00:00.000Z",
            quality_mode="strict_complete",
            source_names=("visits",),
            source_schema_versions={"visits": 2},
            source_watermarks={"visits": "2026-01-08T00:00:00.000Z"},
            source_rows_examined=168,
            source_rows_accepted=168,
            source_rows_rejected=0,
            sample_size=168,
            missing_count=0,
            partial_cycle_count=0,
            failed_cycle_count=0,
            abandoned_cycle_count=0,
            filters={"granularity": "hour"},
            metric_version="visit-analytics.v1",
            query_duration_ms=1.0,
        ),
    )
    runtime = SimpleNamespace(
        state="active",
        api_config=AnalyticsApiConfig(
            enabled=True,
            bearer_token=TOKEN,
            allowed_networks=(ipaddress.ip_network("127.0.0.1/32"),),
            allowed_site_ids=frozenset({SITE}),
            max_concurrent_requests=2,
            max_response_bytes=MAXIMUM,
        ),
        quality_service=None,
        wireless_service=None,
        visit_service=_Service(result),
    )
    runtime.health_payload = lambda: {"state": "active"}
    app = Flask(__name__)
    app.register_blueprint(create_analytics_blueprint(runtime, logger=app.logger))
    client = app.test_client()
    path = (
        API_PREFIX
        + "/visits/time-series"
        + f"?site_id={SITE}&from_utc=2026-01-01T00:00:00.000Z"
        + "&to_utc=2026-01-08T00:00:00.000Z&granularity=hour"
    )
    headers = {"Authorization": f"Bearer {TOKEN}"}
    durations = []
    response_size = 0
    for _ in range(RUNS):
        started = time.perf_counter_ns()
        response = client.get(path, headers=headers)
        durations.append((time.perf_counter_ns() - started) / 1_000_000)
        assert response.status_code == 200
        response_size = len(response.data)
        assert response_size <= MAXIMUM
    durations.sort()
    p50 = durations[int(RUNS * 0.50) - 1]
    p95 = durations[int(RUNS * 0.95) - 1]
    maximum = durations[-1]
    print(
        "analytics_api_benchmark "
        f"runs={RUNS} buckets=168 p50_ms={p50:.3f} "
        f"p95_ms={p95:.3f} max_ms={maximum:.3f} "
        f"response_bytes={response_size} cap_bytes={MAXIMUM}"
    )
    assert p95 < 100.0
