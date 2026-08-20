from __future__ import annotations

from contextlib import closing
from dataclasses import replace
import inspect
import sqlite3

import pytest

import app.analytics.source_gateway
import app.analytics.wireless
from app.analytics.source_gateway import (
    AnalyticsQueryDeadlineExceeded,
    QueryDeadline,
)
from app.analytics.wireless import WirelessAnalyticsService

from .conftest import AP_A, CLIENT_A, CLIENT_B, SITE_A, SITE_B
from .test_wireless_service import FROM, TO, _seed_wireless


@pytest.fixture
def safety_wireless(analytics_stack):
    _seed_wireless(analytics_stack.observations)
    service = WirelessAnalyticsService(
        replace(
            analytics_stack.service.config,
            wireless_min_samples=2,
            max_query_duration_seconds=2,
        ),
        analytics_stack.gateway,
    )
    return analytics_stack, service


def _facts(repository):
    with closing(repository._connect(readonly=True)) as connection:  # noqa: SLF001
        return (
            int(connection.execute("PRAGMA user_version").fetchone()[0]),
            tuple(
                connection.execute(
                    "SELECT type, name, sql FROM sqlite_master "
                    "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
                )
            ),
            int(connection.execute(
                "SELECT COUNT(*) FROM observation_cycles"
            ).fetchone()[0]),
            int(connection.execute(
                "SELECT COUNT(*) FROM client_observations"
            ).fetchone()[0]),
            int(connection.execute(
                "SELECT COUNT(*) FROM ap_observations"
            ).fetchone()[0]),
        )


def test_all_wireless_query_classes_are_source_read_only(safety_wireless):
    stack, service = safety_wireless
    before = _facts(stack.observations)
    service.get_signal_distribution(SITE_A, FROM, TO, "rssi")
    service.get_client_distribution(SITE_A, FROM, TO, "ap_mac")
    service.get_concurrent_client_distribution(SITE_A, FROM, TO)
    service.get_ap_resource_distribution(SITE_A, FROM, TO, "cpu_util")
    service.get_radio_utilization(SITE_A, FROM, TO, "busy_util")
    service.get_throughput_distribution(
        SITE_A, FROM, TO, "client_download_mbps"
    )
    service.get_throughput_distribution(
        SITE_A, FROM, TO, "radio_rx_mbps"
    )
    service.get_counter_quality(SITE_A, FROM, TO)
    service.get_signal_ap_correlation(
        SITE_A, FROM, TO, "rssi", "busy_util"
    )
    assert _facts(stack.observations) == before


def test_wireless_package_has_no_provider_or_polling_dependency():
    source = "\n".join((
        inspect.getsource(app.analytics.wireless),
        inspect.getsource(app.analytics.source_gateway),
    )).lower()
    assert "omadaprovider" not in source
    assert "requests." not in source
    assert "get_clients" not in source
    assert "authorize(" not in source


def test_deadline_is_installed_inside_wireless_sql(safety_wireless, monkeypatch):
    stack, service = safety_wireless

    def expired(*_args, **_kwargs):
        raise AnalyticsQueryDeadlineExceeded("deadline")

    monkeypatch.setattr(
        stack.gateway, "wireless_scalar_distribution", expired
    )
    result = service.get_signal_distribution(SITE_A, FROM, TO, "rssi")
    assert result.status == "unavailable"
    assert result.quality.reason == "query_deadline"

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    try:
        with pytest.raises(AnalyticsQueryDeadlineExceeded):
            stack.gateway._one(  # noqa: SLF001
                connection,
                """
                WITH RECURSIVE count(x) AS (
                  SELECT 1 UNION ALL SELECT x+1 FROM count WHERE x<100000
                ) SELECT SUM(a.x*b.x) FROM count a, count b
                """,
                (), QueryDeadline.after(0.001),
            )
    finally:
        connection.close()


def test_disabled_wireless_is_unavailable_not_zero(safety_wireless):
    stack, service = safety_wireless
    disabled = WirelessAnalyticsService(
        replace(service.config, wireless_enabled=False), stack.gateway
    )
    result = disabled.get_signal_distribution(SITE_A, FROM, TO, "rssi")
    assert result.status == "unavailable"
    assert result.value is None
    assert result.quality.reason == "disabled"


def test_temporal_join_exact_predecessor_gap_site_and_band(safety_wireless):
    stack, service = safety_wireless
    deadline = QueryDeadline.after(2)
    exact = stack.gateway.signal_ap_correlation(
        site_id=SITE_A, signal_metric="rssi", ap_metric="busy_util",
        from_utc="2026-01-01T10:00:59.000Z",
        to_utc="2026-01-01T10:01:01.000Z",
        quality_mode="strict_complete", max_lag_seconds=120,
        deadline=deadline,
    )
    assert exact["client_sample_count"] == 2
    assert exact["matched_count"] == 1  # 2.4 GHz has no matching radio.
    assert exact["lag_max"] == pytest.approx(0, abs=0.001)

    max_lag = stack.gateway.signal_ap_correlation(
        site_id=SITE_A, signal_metric="rssi", ap_metric="busy_util",
        from_utc="2026-01-01T10:03:29.000Z",
        to_utc="2026-01-01T10:03:31.000Z",
        quality_mode="strict_complete", max_lag_seconds=120,
        deadline=QueryDeadline.after(2),
    )
    assert max_lag["matched_count"] == 1
    assert max_lag["lag_max"] == pytest.approx(120, abs=0.01)

    stale = stack.gateway.signal_ap_correlation(
        site_id=SITE_A, signal_metric="snr", ap_metric="busy_util",
        from_utc="2026-01-01T10:04:30.000Z",
        to_utc="2026-01-01T10:04:32.000Z",
        quality_mode="strict_complete", max_lag_seconds=120,
        deadline=QueryDeadline.after(2),
    )
    assert stale["matched_count"] == 0

    other_site = service.get_signal_ap_correlation(
        SITE_B, FROM, TO, "rssi", "cpu_util"
    )
    assert other_site.value.coverage.matched_count == 0


def test_ap_cpu_join_is_safe_without_matching_client_band(safety_wireless):
    _, service = safety_wireless
    result = service.get_signal_ap_correlation(
        SITE_A,
        "2026-01-01T10:00:59.000Z",
        "2026-01-01T10:01:01.000Z",
        "rssi",
        "cpu_util",
    )
    assert result.value.coverage.matched_count == 2


def test_temporal_join_rejects_ap_identity_mismatch(safety_wireless):
    stack, _ = safety_wireless
    observed_at = "2026-01-01T10:07:00.000Z"
    stack.observations.create_cycle(
        kind="client", site_id=SITE_A, started_at=observed_at,
        cycle_id="wireless-other-ap-client",
    )
    stack.observations.insert_client_batch([{
        "cycle_id": "wireless-other-ap-client",
        "observed_at": observed_at, "site_id": SITE_A,
        "client_mac": CLIENT_A, "source_inventory_complete": True,
        "ap_mac": "02:AA:BB:CC:DD:99", "band": "5GHz", "rssi": -50,
    }])
    stack.observations.finalize_cycle(
        "wireless-other-ap-client", finished_at=observed_at,
        complete=True, result="success", source_rows_reported=1,
        items_seen=1, items_stored=1,
    )
    raw = stack.gateway.signal_ap_correlation(
        site_id=SITE_A, signal_metric="rssi", ap_metric="cpu_util",
        from_utc="2026-01-01T10:06:59.000Z",
        to_utc="2026-01-01T10:07:01.000Z",
        quality_mode="strict_complete", max_lag_seconds=120,
        deadline=QueryDeadline.after(2),
    )
    assert raw["client_sample_count"] == 1
    assert raw["matched_count"] == 0


def test_invalid_elapsed_and_exact_counter_gap_are_classified(safety_wireless):
    stack, service = safety_wireless
    timestamp = "2026-01-01T10:06:00.000Z"
    for index, value in enumerate((100, 120), 1):
        cycle_id = f"same-time-{index}"
        stack.observations.create_cycle(
            kind="client", site_id=SITE_A, started_at=timestamp,
            cycle_id=cycle_id,
        )
        stack.observations.insert_client_batch([{
            "cycle_id": cycle_id, "observed_at": timestamp,
            "site_id": SITE_A, "client_mac": CLIENT_B,
            "source_inventory_complete": True, "ap_mac": AP_A,
            "band": "2.4GHz", "traffic_down": value,
            "traffic_up": value,
        }])
        stack.observations.finalize_cycle(
            cycle_id, finished_at=timestamp, complete=True,
            result="success", source_rows_reported=1,
            items_seen=1, items_stored=1,
        )
    result = service.get_throughput_distribution(
        SITE_A, FROM, TO, "client_download_mbps"
    )
    assert result.value.reason_counts["invalid_elapsed"] == 1
    # CLIENT_B has an interval from 10:01 to 10:04: exactly 180 seconds.
    assert result.value.valid_rate_sample_count >= 1


def test_aggregate_telemetry_and_results_do_not_expose_client_identifiers(
    safety_wireless,
):
    stack, service = safety_wireless
    events = []

    class Telemetry:
        def emit(self, event, **fields):
            events.append((event, fields))

    service.telemetry = Telemetry()
    result = service.get_signal_distribution(SITE_A, FROM, TO, "rssi")
    rendered = repr(result)
    assert CLIENT_A not in rendered
    assert CLIENT_B not in rendered
    assert "192.0.2." not in rendered
    assert "hostname" not in rendered.lower()
    assert "raw_controller_snapshot" not in rendered
    assert all("client_mac" not in fields for _, fields in events)
    assert all("device_id" not in fields for _, fields in events)


def test_wireless_query_plans_use_site_time_indexes(safety_wireless):
    stack, _ = safety_wireless
    with stack.observations.read_connection() as connection:
        client_plan = " ".join(str(row[-1]) for row in connection.execute(
            """
            EXPLAIN QUERY PLAN SELECT row_id, rssi
            FROM client_observations
            WHERE site_id=? AND observed_at>=? AND observed_at<?
            ORDER BY observed_at, row_id
            """,
            (SITE_A, FROM, TO),
        ))
        radio_plan = " ".join(str(row[-1]) for row in connection.execute(
            """
            EXPLAIN QUERY PLAN SELECT row_id, busy_util
            FROM ap_radio_observations
            WHERE site_id=? AND ap_mac=? AND band=?
              AND radio_observed_at>=? AND radio_observed_at<?
            ORDER BY radio_observed_at, row_id
            """,
            (SITE_A, AP_A, "5GHz", FROM, TO),
        ))
    assert "idx_client_site_time" in client_plan
    assert "idx_radio_site_ap_band_time" in radio_plan
