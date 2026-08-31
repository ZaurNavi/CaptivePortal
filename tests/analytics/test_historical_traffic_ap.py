from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.analytics.current_traffic import CurrentTrafficReadService
from app.analytics.historical_traffic import HistoricalTrafficReadService


UTC = timezone.utc
SITE = "site-a"
OTHER_SITE = "site-b"
START = "2026-01-01T11:55:00.000Z"
END = "2026-01-01T12:00:00.000Z"


def _row(
    cycle_id, site, ap_mac, observed, download, upload, *, name=None, **changes,
):
    value = {
        "cycle_id": cycle_id,
        "observed_at": observed,
        "site_id": site,
        "ap_mac": ap_mac,
        "name": name,
        "partial": False,
        "overview_ok": True,
        "wired_uplink_ok": True,
        "lan_traffic_ok": True,
        "radios_ok": True,
        "wired_observed_at": observed,
        "wired_download_mbps": download,
        "wired_upload_mbps": upload,
        "wired_download_rate_reason": "ok",
        "wired_upload_rate_reason": "ok",
        "lan_observed_at": observed,
        "lan_rx_mbps": None if download is None else download + 10,
        "lan_tx_mbps": None if upload is None else upload + 10,
        "lan_rx_rate_reason": "ok" if download is not None else "no_baseline",
        "lan_tx_rate_reason": "ok" if upload is not None else "no_baseline",
    }
    value.update(changes)
    return value


def _cycle(stack, cycle_id, site, finished, rows, *, started=None):
    stack.observations.create_cycle(
        kind="ap_dynamic", site_id=site, started_at=started or finished,
        cycle_id=cycle_id,
    )
    stack.observations.insert_ap_batch([
        (row, ()) for row in rows
    ])
    stack.observations.finalize_cycle(
        cycle_id,
        finished_at=finished,
        complete=True,
        result="success",
        source_rows_reported=len(rows),
        items_seen=len(rows),
        items_stored=len(rows),
    )


def _services(stack):
    current = CurrentTrafficReadService(stack.gateway)
    history = HistoricalTrafficReadService(
        stack.gateway,
        quality_gap_threshold_seconds=180,
        clock=lambda: datetime(2026, 1, 1, 12, tzinfo=UTC),
    )
    return current, history


def _read(
    stack, site=SITE, *, start=START, end=END, bucket_seconds=300,
):
    current, history = _services(stack)
    summary = current.get_current_site_traffic(
        site,
        evaluated_at_utc=end,
        fresh_max_age_seconds=90,
        stale_max_age_seconds=180,
        max_ap_skew_seconds=60,
    )
    current_items = ()
    if summary.snapshot.cycle_id is not None and summary.coverage.total_ap_count <= 12:
        current_items = current.list_current_ap_traffic(
            site,
            cycle_id=summary.snapshot.cycle_id,
            evaluated_at_utc=end,
            fresh_max_age_seconds=90,
            stale_max_age_seconds=180,
            max_ap_skew_seconds=60,
            limit=12,
        ).items
    result = history.get_site_history(
        site,
        from_utc=start,
        to_utc=end,
        evaluated_at_utc=end,
        bucket_seconds=bucket_seconds,
        include_ap_traffic=True,
        current_cycle_id=summary.snapshot.cycle_id,
    )
    return history.compose_current_ap_traffic(
        result,
        current_snapshot=summary.snapshot,
        current_population_count=summary.coverage.total_ap_count,
        current_items=current_items,
    )


def test_ap_population_unions_current_only_and_historical_only(analytics_stack):
    historical_mac = "02:AA:BB:CC:DD:10"
    current_mac = "02:AA:BB:CC:DD:20"
    _cycle(analytics_stack, "history", SITE, "2026-01-01T11:56:00.000Z", [
        _row("history", SITE, historical_mac, "2026-01-01T11:56:00.000Z", 2, 1, name="Old AP"),
    ])
    _cycle(analytics_stack, "current", SITE, END, [
        _row("current", SITE, current_mac, END, 4, 2, name="New AP"),
    ])

    result = _read(analytics_stack)
    product = result.ap_traffic
    assert product.population.population_count == 2
    assert product.population.current_population_count == 1
    assert product.population.historical_population_count == 1
    assert tuple(item.ap_mac for item in product.items) == (
        historical_mac, current_mac,
    )
    historical, current = product.items
    assert historical.display_name == "Old AP"
    assert historical.now.status == "unavailable"
    assert historical.coverage.accepted_sample_count == 1
    assert current.display_name == "New AP"
    assert current.display_name_source == "current"
    assert current.now.status == "valid"
    assert current.series.status == ("none",)
    assert current.series.download_mbps == (None,)
    assert current.coverage.status == "insufficient_data"


def test_ap_history_inherits_site_source_and_preserves_additive_identity(analytics_stack):
    first = "02:AA:BB:CC:DD:10"
    second = "02:AA:BB:CC:DD:20"
    for index, observed in enumerate((
        "2026-01-01T11:55:00.000Z",
        "2026-01-01T11:57:30.000Z",
        "2026-01-01T11:59:00.000Z",
    )):
        cycle_id = f"complete-{index}"
        _cycle(analytics_stack, cycle_id, SITE, observed, [
            _row(cycle_id, SITE, first, observed, 1 + index, 2 + index),
            _row(cycle_id, SITE, second, observed, 0, 0),
        ])

    result = _read(analytics_stack)
    product = result.ap_traffic
    assert product.population.population_count == 2
    assert all(item.series.status == ("complete",) for item in product.items)
    assert sum(item.series.download_mbps[0] for item in product.items) == pytest.approx(
        result.buckets[0].download_mbps
    )
    assert sum(item.series.upload_mbps[0] for item in product.items) == pytest.approx(
        result.buckets[0].upload_mbps
    )
    zero = product.items[1]
    assert zero.average.download_mbps == 0
    assert zero.average.upload_mbps == 0
    assert zero.average.total_mbps == 0
    assert zero.peak.download_mbps == 0
    assert zero.peak.upload_mbps == 0
    assert zero.peak.total_mbps == 0
    assert zero.coverage.ap_accepted_interval_seconds > 0


def test_population_over_twelve_is_exact_and_never_truncated(analytics_stack):
    rows = [
        _row(
            "too-many", SITE, f"02:AA:BB:CC:DD:{index:02X}",
            "2026-01-01T11:59:00.000Z", index, index,
        )
        for index in range(13)
    ]
    _cycle(
        analytics_stack, "too-many", SITE,
        "2026-01-01T11:59:00.000Z", rows,
    )

    result = _read(analytics_stack)
    product = result.ap_traffic
    assert product.status == "unsupported_population"
    assert product.population.population_count == 13
    assert product.population.current_population_count == 13
    assert product.population.historical_population_count == 13
    assert product.population.returned_ap_count == 0
    assert product.population.population_complete is False
    assert product.items == ()


def test_population_and_metrics_are_isolated_to_requested_site(analytics_stack):
    site_a_mac = "02:AA:BB:CC:DD:10"
    _cycle(analytics_stack, "site-a", SITE, "2026-01-01T11:59:00.000Z", [
        _row("site-a", SITE, site_a_mac, "2026-01-01T11:59:00.000Z", 2, 1),
    ])
    _cycle(analytics_stack, "site-b", OTHER_SITE, "2026-01-01T11:59:30.000Z", [
        _row(
            "site-b", OTHER_SITE, f"02:BB:CC:DD:EE:{index:02X}",
            "2026-01-01T11:59:30.000Z", 9, 9,
        )
        for index in range(13)
    ])

    result = _read(analytics_stack, SITE)
    assert result.ap_traffic.population.population_count == 1
    assert tuple(item.ap_mac for item in result.ap_traffic.items) == (site_a_mac,)
    assert result.ap_traffic.items[0].series.download_mbps == (2.0,)


def test_ap_never_falls_back_inside_a_wired_site_bucket(analytics_stack):
    mac = "02:AA:BB:CC:DD:10"
    first = "2026-01-01T11:56:00.000Z"
    second = "2026-01-01T11:58:00.000Z"
    _cycle(analytics_stack, "wired-only", SITE, first, [
        _row(
            "wired-only", SITE, mac, first, 2, 1,
            lan_rx_mbps=None, lan_tx_mbps=None,
            lan_rx_rate_reason="no_baseline", lan_tx_rate_reason="no_baseline",
        ),
    ])
    _cycle(analytics_stack, "lan-only", SITE, second, [
        _row(
            "lan-only", SITE, mac, second, None, None,
            wired_download_rate_reason="no_baseline",
            wired_upload_rate_reason="no_baseline",
            lan_rx_mbps=40, lan_tx_mbps=20,
            lan_rx_rate_reason="ok",
            lan_tx_rate_reason="ok",
        ),
    ])
    # Keep the Current owner on a separate valid half-open boundary cycle.
    # The historical bucket still sees only the two intentionally mixed cycles.
    _cycle(analytics_stack, "current-valid", SITE, END, [
        _row("current-valid", SITE, mac, END, 5, 2),
    ])

    result = _read(analytics_stack)
    bucket = result.buckets[0]
    item = result.ap_traffic.items[0]
    assert result.ap_traffic.population.population_count == 1
    assert bucket.selected_source == "wired"
    assert bucket.complete_site_sample_count == 1
    assert bucket.excluded_site_sample_count == 1
    assert item.series.download_mbps == (2.0,)
    assert item.series.upload_mbps == (1.0,)
    assert item.average.download_mbps is None
    assert item.peak.download_mbps == 2
    assert item.coverage.no_baseline_count == 2


def test_ap_aligned_series_distinguishes_partial_none_and_zero(analytics_stack):
    first_mac = "02:AA:BB:CC:DD:10"
    second_mac = "02:AA:BB:CC:DD:20"
    _cycle(analytics_stack, "first-bucket", SITE, "2026-01-01T11:52:00.000Z", [
        _row(
            "first-bucket", SITE, first_mac,
            "2026-01-01T11:52:00.000Z", 0, 0,
        ),
    ])
    _cycle(analytics_stack, "second-bucket", SITE, "2026-01-01T11:57:00.000Z", [
        _row(
            "second-bucket", SITE, second_mac,
            "2026-01-01T11:57:00.000Z", 4, 2,
        ),
    ])

    result = _read(
        analytics_stack,
        start="2026-01-01T11:50:00.000Z",
        bucket_seconds=300,
    )
    first = result.ap_traffic.items[0]
    assert first.ap_mac == first_mac
    assert first.series.status == ("complete", "none")
    assert first.series.download_mbps == (0.0, None)
    assert first.series.upload_mbps == (0.0, None)
    assert first.coverage.complete_bucket_count == 1
    assert first.coverage.missing_bucket_count == 1
    assert first.coverage.status == "partial"


def test_ap_average_is_time_weighted_and_peak_total_uses_one_sample(analytics_stack):
    mac = "02:AA:BB:CC:DD:10"
    for cycle_id, observed, download, upload in (
        ("weighted-a", "2026-01-01T11:55:00.000Z", 1, 1),
        ("weighted-b", "2026-01-01T11:55:30.000Z", 1, 8),
        ("weighted-c", "2026-01-01T11:57:00.000Z", 3, 2),
    ):
        _cycle(analytics_stack, cycle_id, SITE, observed, [
            _row(cycle_id, SITE, mac, observed, download, upload),
        ])

    item = _read(analytics_stack).ap_traffic.items[0]
    assert item.average.download_mbps == pytest.approx(2.5)
    assert item.average.upload_mbps == pytest.approx(3.5)
    assert item.average.total_mbps == pytest.approx(6.0)
    assert item.average.download_mbps != pytest.approx(
        sum(value for value in item.series.download_mbps if value is not None)
        / item.coverage.complete_bucket_count
    )
    assert item.peak.download_mbps == 3
    assert item.peak.upload_mbps == 8
    assert item.peak.total_mbps == 9
    assert item.peak.total_mbps != (
        item.peak.download_mbps + item.peak.upload_mbps
    )


@pytest.mark.parametrize(
    ("start", "bucket_seconds", "expected_count"),
    [
        ("2025-12-31T12:00:00.000Z", 300, 288),
        ("2025-12-25T12:00:00.000Z", 900, 672),
    ],
)
def test_ap_series_aligns_to_every_24h_and_7d_bucket(
    analytics_stack, start, bucket_seconds, expected_count,
):
    site = f"traffic-ap-range-{expected_count}"
    mac = "02:AA:BB:CC:DD:10"
    observed = "2026-01-01T11:59:00.000Z"
    _cycle(analytics_stack, "aligned", site, observed, [
        _row("aligned", site, mac, observed, 1, 1),
    ])

    item = _read(
        analytics_stack, site, start=start, bucket_seconds=bucket_seconds,
    ).ap_traffic.items[0]
    assert item.series.bucket_count == expected_count
    assert len(item.series.status) == expected_count
    assert len(item.series.download_mbps) == expected_count
    assert len(item.series.upload_mbps) == expected_count
    assert item.series.status[-1] == "complete"
    assert all(status == "none" for status in item.series.status[:-1])


def test_twelve_aps_are_all_returned_in_mac_order_without_pagination(analytics_stack):
    observed = "2026-01-01T11:59:00.000Z"
    rows = [
        _row(
            "supported", SITE, f"02:AA:BB:CC:DD:{index:02X}",
            observed, index, index,
        )
        for index in reversed(range(12))
    ]
    _cycle(analytics_stack, "supported", SITE, observed, rows)

    product = _read(analytics_stack).ap_traffic
    assert product.population.population_count == 12
    assert product.population.returned_ap_count == 12
    assert product.population.population_complete is True
    assert len(product.items) == 12
    assert tuple(item.ap_mac for item in product.items) == tuple(sorted(
        row["ap_mac"] for row in rows
    ))
