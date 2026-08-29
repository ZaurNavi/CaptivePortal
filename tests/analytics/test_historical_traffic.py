from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from app.analytics.historical_traffic import (
    HistoricalTrafficReadService,
    HistoricalTrafficSourceUnavailable,
    HistoricalTrafficValidationError,
    MAX_SITE_SAMPLE_SOURCE_SKEW_SECONDS,
)
from app.analytics.source_gateway import QueryDeadline
from app.analytics.source_gateway import AnalyticsQueryDeadlineExceeded
from app.observations.read_service import ObservationReadService


UTC = timezone.utc
SITE = "site-a"
EVALUATED = "2026-01-01T12:00:00.000Z"


def _service(stack, *, gap=180.0):
    return HistoricalTrafficReadService(
        stack.gateway,
        quality_gap_threshold_seconds=gap,
        clock=lambda: datetime(2026, 1, 1, 12, tzinfo=UTC),
    )


def _row(
    cycle_id, mac, observed, *, wired=(1.0, 2.0), lan=(3.0, 4.0), site=SITE
):
    def values(pair):
        return (
            pair[0], pair[1],
            "ok" if pair[0] is not None else "no_baseline",
            "ok" if pair[1] is not None else "no_baseline",
        )
    wd, wu, wdr, wur = values(wired)
    ld, lu, ldr, lur = values(lan)
    return {
        "cycle_id": cycle_id, "observed_at": observed, "site_id": site,
        "ap_mac": mac, "partial": False, "overview_ok": True,
        "wired_uplink_ok": True, "lan_traffic_ok": True, "radios_ok": True,
        "wired_observed_at": observed, "wired_download_mbps": wd,
        "wired_upload_mbps": wu, "wired_download_rate_reason": wdr,
        "wired_upload_rate_reason": wur, "lan_observed_at": observed,
        "lan_rx_mbps": ld, "lan_tx_mbps": lu,
        "lan_rx_rate_reason": ldr, "lan_tx_rate_reason": lur,
    }


def _cycle(stack, cycle_id, finished, rows=(), *, started=None, result="success",
           complete=True, site=SITE):
    started = started or finished
    stack.observations.create_cycle(
        kind="ap_dynamic", site_id=site, started_at=started, cycle_id=cycle_id
    )
    entries = [(row, ()) for row in rows]
    if entries:
        stack.observations.insert_ap_batch(entries)
    count = len(entries)
    stack.observations.finalize_cycle(
        cycle_id, finished_at=finished, complete=complete, result=result,
        source_rows_reported=count, items_seen=count, items_stored=count,
    )


def _history(stack, **kwargs):
    values = {
        "from_utc": "2026-01-01T11:55:00.000Z",
        "to_utc": EVALUATED,
        "evaluated_at_utc": EVALUATED,
        "bucket_seconds": 300,
    }
    values.update(kwargs)
    return _service(stack).get_site_history(SITE, **values)


def test_complete_wired_bucket_and_canonical_dto(analytics_stack):
    for index, timestamp in enumerate((
        "2026-01-01T11:55:30.000Z",
        "2026-01-01T11:58:00.000Z",
        "2026-01-01T11:59:30.000Z",
    )):
        cycle = f"history-{index}"
        _cycle(analytics_stack, cycle, timestamp, [
            _row(cycle, "02:AA:BB:CC:DD:10", timestamp)
        ])
    result = _history(analytics_stack)
    bucket = result.buckets[0]
    assert result.range.metric_version == "network_traffic_history.v1"
    assert result.range.bucket_alignment == "range_start_utc"
    assert bucket.status == "complete"
    assert bucket.selected_source == "wired"
    assert bucket.selection_reason == "primary_full_coverage"
    assert bucket.download_mbps == 1.0
    assert bucket.upload_mbps == 2.0
    assert bucket.total_mbps == 3.0
    assert bucket.complete_site_sample_count == 3
    assert result.coverage.status == "complete"
    assert result.coverage.source_age_seconds == 30.0
    assert result.status == "ok"


def test_lan_fallback_is_per_bucket_and_never_blends(analytics_stack):
    timestamp = "2026-01-01T11:59:00.000Z"
    _cycle(analytics_stack, "lan-fallback", timestamp, [
        _row("lan-fallback", "02:AA:BB:CC:DD:11", timestamp,
             wired=(None, None), lan=(4.0, 5.0))
    ])
    bucket = _history(analytics_stack).buckets[0]
    assert bucket.selected_source == "lan"
    assert bucket.selection_reason == "fallback_full_coverage"
    assert bucket.total_mbps == 9.0
    assert bucket.source_selection.source_mixing_allowed is False


def test_partial_ap_pair_is_excluded_not_undercounted(analytics_stack):
    timestamp = "2026-01-01T11:59:00.000Z"
    _cycle(analytics_stack, "partial-pair", timestamp, [
        _row("partial-pair", "02:AA:BB:CC:DD:12", timestamp,
             wired=(1.0, None), lan=(2.0, None))
    ])
    bucket = _history(analytics_stack).buckets[0]
    assert bucket.status == "none"
    assert bucket.total_mbps is None
    assert bucket.complete_site_sample_count == 0
    assert bucket.excluded_site_sample_count == 1
    assert _history(analytics_stack).status == "insufficient_data"


def test_empty_population_is_exact_numeric_zero(analytics_stack):
    _cycle(analytics_stack, "empty-history", "2026-01-01T11:59:00.000Z")
    bucket = _history(analytics_stack).buckets[0]
    assert bucket.selected_source == "wired"
    assert bucket.selection_reason == "empty_population"
    assert bucket.download_mbps == 0.0
    assert bucket.upload_mbps == 0.0
    assert bucket.total_mbps == 0.0


def test_gap_threshold_boundary_and_partial_numeric(analytics_stack):
    for suffix, timestamp in (("a", "2026-01-01T11:55:00.000Z"),
                              ("b", "2026-01-01T11:58:00.000Z"),
                              ("c", "2026-01-01T12:00:00.000Z")):
        cycle = "gap-" + suffix
        _cycle(analytics_stack, cycle, timestamp, [
            _row(cycle, "02:AA:BB:CC:DD:13", timestamp)
        ])
    exact = _history(analytics_stack).buckets[0]
    assert exact.max_inter_sample_gap_seconds == pytest.approx(180.0, abs=.01)
    assert exact.status == "complete"
    stricter = _service(analytics_stack, gap=179).get_site_history(
        SITE, from_utc="2026-01-01T11:55:00.000Z", to_utc=EVALUATED,
        evaluated_at_utc=EVALUATED, bucket_seconds=300,
    ).buckets[0]
    assert stricter.status == "partial"
    assert stricter.total_mbps == 3.0


@pytest.mark.parametrize(
    ("edge", "offset_seconds", "expected"),
    [
        ("leading", 180, "complete"),
        ("leading", 181, "partial"),
        ("trailing", 180, "complete"),
        ("trailing", 181, "partial"),
    ],
)
def test_leading_and_trailing_gap_threshold_boundaries(
    analytics_stack, edge, offset_seconds, expected
):
    start = datetime(2026, 1, 1, 11, 50, tzinfo=UTC)
    offsets = (
        (offset_seconds, 360, 540)
        if edge == "leading"
        else (60, 240, 600 - offset_seconds)
    )
    for index, offset in enumerate(offsets):
        timestamp = (start + timedelta(seconds=offset)).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z")
        cycle = f"{edge}-{offset_seconds}-{index}"
        _cycle(analytics_stack, cycle, timestamp, [
            _row(cycle, f"02:AA:BB:CC:DE:{40 + index:02X}", timestamp)
        ])
    bucket = _service(analytics_stack).get_site_history(
        SITE, from_utc="2026-01-01T11:50:00.000Z", to_utc=EVALUATED,
        evaluated_at_utc=EVALUATED, bucket_seconds=600,
    ).buckets[0]
    assert bucket.status == expected
    gap = (
        bucket.leading_gap_seconds
        if edge == "leading" else bucket.trailing_gap_seconds
    )
    assert gap == offset_seconds


@pytest.mark.parametrize(
    ("days", "bucket", "count"),
    [(1, 300, 288), (7, 900, 672), (30, 3600, 720), (180, 21600, 720)],
)
def test_auto_bucket_ladder_supports_long_ranges(analytics_stack, days, bucket, count):
    result = _service(analytics_stack).get_site_history(
        "site-without-history", from_utc="2025-07-05T12:00:00.000Z" if days == 180 else
        format_day(days), to_utc=EVALUATED, evaluated_at_utc=EVALUATED,
    )
    assert result.range.bucket_seconds == bucket
    assert result.range.bucket_count == count


def format_day(days):
    return (
        datetime(2026, 1, 1, 12, tzinfo=UTC)
        - timedelta(days=days)
    ).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def test_explicit_bucket_validation_and_future_as_of(analytics_stack):
    with pytest.raises(HistoricalTrafficValidationError):
        _service(analytics_stack).get_site_history(
            SITE, from_utc="2026-01-01T11:47:59.000Z", to_utc=EVALUATED,
            evaluated_at_utc=EVALUATED, bucket_seconds=1,
        )
    with pytest.raises(HistoricalTrafficValidationError):
        _history(analytics_stack, bucket_seconds=True)
    with pytest.raises(HistoricalTrafficValidationError):
        _history(analytics_stack, to_utc="2026-01-01T12:00:00.001Z")


def test_half_open_range_and_exact_bucket_boundary_use_finished_at(analytics_stack):
    cases = (
        ("at-from", "2026-01-01T11:50:00.000Z"),
        ("before-boundary", "2026-01-01T11:54:59.999Z"),
        ("at-boundary", "2026-01-01T11:55:00.000Z"),
        ("at-to", "2026-01-01T12:00:00.000Z"),
    )
    for index, (cycle, timestamp) in enumerate(cases):
        _cycle(analytics_stack, cycle, timestamp, [
            _row(cycle, f"02:AA:BB:CC:DD:{20 + index:02X}", timestamp)
        ])
    result = _service(analytics_stack, gap=999).get_site_history(
        SITE, from_utc="2026-01-01T11:50:00.000Z", to_utc=EVALUATED,
        evaluated_at_utc=EVALUATED, bucket_seconds=300,
    )
    assert [item.canonical_cycle_count for item in result.buckets] == [2, 1]
    assert result.buckets[0].first_complete_sample_at == cases[0][1]
    assert result.buckets[1].first_complete_sample_at == cases[2][1]
    assert result.coverage.source_watermark_utc == cases[3][1]


def test_cycle_started_before_range_and_finished_inside_is_preserved(analytics_stack):
    timestamp = "2026-01-01T11:55:30.000Z"
    _cycle(
        analytics_stack,
        "straddles-from",
        timestamp,
        [_row("straddles-from", "02:AA:BB:CC:DD:40", timestamp)],
        started="2026-01-01T11:54:59.999Z",
    )

    bucket = _history(analytics_stack).buckets[0]

    assert bucket.canonical_cycle_count == 1
    assert bucket.first_complete_sample_at == timestamp


def test_completed_success_with_null_finish_inside_range_fails_closed(analytics_stack):
    timestamp = "2026-01-01T11:58:00.000Z"
    _cycle(analytics_stack, "null-finish", timestamp)
    with analytics_stack.observations._connect() as connection:
        connection.execute("PRAGMA ignore_check_constraints=ON")
        connection.execute(
            "UPDATE observation_cycles SET finished_at=NULL "
            "WHERE cycle_id='null-finish'"
        )

    with pytest.raises(HistoricalTrafficSourceUnavailable):
        _history(analytics_stack)


def test_cycles_outside_range_do_not_change_historical_result(analytics_stack):
    for suffix, timestamp, wired in (
        ("wired", "2026-01-01T11:55:30.000Z", (1.0, 2.0)),
        ("none", "2026-01-01T11:57:30.000Z", (None, None)),
        ("lan", "2026-01-01T11:59:30.000Z", (None, None)),
    ):
        cycle = "bounded-" + suffix
        lan = (3.0, 4.0) if suffix == "lan" else (None, None)
        _cycle(analytics_stack, cycle, timestamp, [
            _row(
                cycle,
                f"02:AA:BB:CC:DD:{50 + len(suffix):02X}",
                timestamp,
                wired=wired,
                lan=lan,
            )
        ])
    _cycle(
        analytics_stack,
        "bounded-partial",
        "2026-01-01T11:58:00.000Z",
        result="partial",
        complete=False,
    )
    before = _history(analytics_stack)

    for cycle, timestamp, value in (
        ("old-outside", "2025-12-01T00:00:00.000Z", (70.0, 80.0)),
        ("at-to-outside", EVALUATED, (90.0, 100.0)),
        ("after-to-outside", "2026-01-01T12:01:00.000Z", (110.0, 120.0)),
    ):
        _cycle(analytics_stack, cycle, timestamp, [
            _row(cycle, "02:AA:BB:CC:DD:60", timestamp, wired=value)
        ])
    after = _history(analytics_stack)

    assert after.buckets == before.buckets
    assert after.quality == before.quality
    assert after.coverage.canonical_cycle_count == before.coverage.canonical_cycle_count
    assert (
        after.coverage.complete_site_sample_count
        == before.coverage.complete_site_sample_count
    )
    assert (
        after.coverage.excluded_site_sample_count
        == before.coverage.excluded_site_sample_count
    )
    assert after.coverage.source_transition_count == 0
    assert [bucket.status for bucket in after.buckets] == ["partial"]
    assert after.quality.partial_cycle_count == 1


@pytest.mark.parametrize("days,bucket_seconds", [(1, 300), (7, 900)])
def test_requested_window_bounds_candidate_aggregation(
    analytics_stack, days, bucket_seconds
):
    site = f"bounded-site-{days}d"
    start = datetime(2026, 1, 1, 12, tzinfo=UTC) - timedelta(days=days)
    from_utc = start.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    in_range = "2026-01-01T11:59:00.000Z"
    _cycle(analytics_stack, f"bounded-{days}d", in_range, [
        _row(
            f"bounded-{days}d",
            "02:AA:BB:CC:DD:61",
            in_range,
            site=site,
        )
    ], site=site)
    _cycle(analytics_stack, f"old-{days}d", "2025-01-01T00:00:00.000Z", [
        _row(
            f"old-{days}d",
            "02:AA:BB:CC:DD:62",
            "2025-01-01T00:00:00.000Z",
            site=site,
        )
    ], site=site)

    result = _service(analytics_stack, gap=999_999).get_site_history(
        site,
        from_utc=from_utc,
        to_utc=EVALUATED,
        evaluated_at_utc=EVALUATED,
        bucket_seconds=bucket_seconds,
    )

    assert result.coverage.canonical_cycle_count == 1
    assert result.coverage.available_from_utc == "2025-01-01T00:00:00.000Z"
    assert result.coverage.available_through_utc == in_range
    assert result.coverage.source_watermark_utc == in_range


def test_final_bucket_uses_exact_short_range_end(analytics_stack):
    result = _service(analytics_stack).get_site_history(
        "site-without-history", from_utc="2026-01-01T11:50:00.000Z",
        to_utc="2026-01-01T11:55:01.000Z", evaluated_at_utc=EVALUATED,
        bucket_seconds=300,
    )
    assert result.range.bucket_count == 2
    assert result.buckets[-1].bucket_start_utc == "2026-01-01T11:55:00.000Z"
    assert result.buckets[-1].bucket_end_utc == "2026-01-01T11:55:01.000Z"


@pytest.mark.parametrize(
    ("delta_ms", "accepted"), [(59_999, True), (60_000, True), (60_001, False)],
)
def test_selected_source_skew_boundaries(analytics_stack, delta_ms, accepted):
    finish = "2026-01-01T11:59:30.000Z"
    base = datetime(2026, 1, 1, 11, 58, 0, tzinfo=UTC)
    first = base.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    second = (base + timedelta(milliseconds=delta_ms)).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")
    rows = [
        _row("skew", "02:AA:BB:CC:DD:30", first, lan=(None, None)),
        _row("skew", "02:AA:BB:CC:DD:31", second, lan=(None, None)),
    ]
    _cycle(analytics_stack, "skew", finish, rows,
           started="2026-01-01T11:57:59.000Z")
    bucket = _history(analytics_stack).buckets[0]
    assert (bucket.complete_site_sample_count == 1) is accepted
    assert bucket.selected_source == "wired"
    assert bucket.selected_source_skew_excluded_sample_count == (0 if accepted else 1)


def test_source_family_transition_is_explicit_and_site_scoped(analytics_stack):
    wired_at = "2026-01-01T11:54:30.000Z"
    lan_at = "2026-01-01T11:59:30.000Z"
    _cycle(analytics_stack, "transition-wired", wired_at, [
        _row("transition-wired", "02:AA:BB:CC:DD:32", wired_at)
    ])
    _cycle(analytics_stack, "transition-lan", lan_at, [
        _row("transition-lan", "02:AA:BB:CC:DD:33", lan_at,
             wired=(None, None), lan=(3.0, 4.0))
    ])
    result = _service(analytics_stack, gap=999).get_site_history(
        SITE, from_utc="2026-01-01T11:50:00.000Z", to_utc=EVALUATED,
        evaluated_at_utc=EVALUATED, bucket_seconds=300,
    )
    assert [item.selected_source for item in result.buckets] == ["wired", "lan"]
    assert result.buckets[1].source_changed_from_previous is True
    assert result.coverage.source_transition_count == 1
    other = _service(analytics_stack).get_site_history(
        "site-b", from_utc="2026-01-01T11:50:00.000Z", to_utc=EVALUATED,
        evaluated_at_utc=EVALUATED, bucket_seconds=300,
    )
    assert other.status == "insufficient_data"


@pytest.mark.parametrize(
    "reason",
    ["no_baseline", "counter_reset", "gap_too_large", "invalid_elapsed",
     "source_unavailable"],
)
def test_selected_source_rate_reason_counts_without_false_zero(analytics_stack, reason):
    timestamp = "2026-01-01T11:59:00.000Z"
    row = _row("reason", "02:AA:BB:CC:DD:34", timestamp,
               wired=(None, None), lan=(None, None))
    row["wired_download_rate_reason"] = reason
    _cycle(analytics_stack, "reason", timestamp, [row])
    result = _history(analytics_stack)
    bucket = result.buckets[0]
    assert bucket.total_mbps is None
    expected = 2 if reason == "no_baseline" else 1
    assert bucket.rate_reason_counts[reason] == expected
    assert getattr(result.quality, reason + "_count") == expected


def test_lan_higher_coverage_and_wired_tie_preference(analytics_stack):
    timestamp = "2026-01-01T11:59:00.000Z"
    _cycle(analytics_stack, "higher-lan", timestamp, [
        _row("higher-lan", "02:AA:BB:CC:DD:35", timestamp,
             wired=(None, None), lan=(2.0, 3.0))
    ])
    higher = _history(analytics_stack).buckets[0]
    assert higher.selection_reason == "fallback_full_coverage"
    assert higher.selected_source == "lan"

    tie_time = "2026-01-01T11:54:00.000Z"
    _cycle(analytics_stack, "tie", tie_time, [
        _row("tie", "02:AA:BB:CC:DD:38", tie_time,
             wired=(1.0, None), lan=(2.0, None))
    ])
    tie = _service(analytics_stack).get_site_history(
        SITE, from_utc="2026-01-01T11:50:00.000Z", to_utc=EVALUATED,
        evaluated_at_utc=EVALUATED, bucket_seconds=300,
    ).buckets[0]
    assert tie.selected_source == "wired"
    assert tie.selection_reason == "primary_preferred_tie_or_higher"


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("source_rows_reported", 2), ("items_seen", 2),
        ("items_skipped", 1), ("error_count", 1),
        ("data_quality_warning_count", 1),
    ],
)
def test_cycle_integrity_contradictions_fail_closed(analytics_stack, column, value):
    timestamp = "2026-01-01T11:59:00.000Z"
    _cycle(analytics_stack, "cycle-corrupt", timestamp, [
        _row("cycle-corrupt", "02:AA:BB:CC:DD:36", timestamp)
    ])
    with analytics_stack.observations._connect() as connection:
        connection.execute(
            f"UPDATE observation_cycles SET {column}=? WHERE cycle_id=?",
            (value, "cycle-corrupt"),
        )
    with pytest.raises(HistoricalTrafficSourceUnavailable):
        _history(analytics_stack)


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("site_id", "other-site"), ("ap_mac", "bad-mac"),
        ("partial", 1), ("overview_ok", 0), ("wired_uplink_ok", 0),
        ("lan_traffic_ok", 0), ("radios_ok", 0),
        ("wired_download_rate_reason", None),
    ],
)
def test_ap_integrity_contradictions_fail_closed(analytics_stack, column, value):
    timestamp = "2026-01-01T11:59:00.000Z"
    _cycle(analytics_stack, "row-corrupt", timestamp, [
        _row("row-corrupt", "02:AA:BB:CC:DD:37", timestamp)
    ])
    with analytics_stack.observations._connect() as connection:
        connection.execute("PRAGMA ignore_check_constraints=ON")
        connection.execute(
            f"UPDATE ap_observations SET {column}=? WHERE cycle_id=?",
            (value, "row-corrupt"),
        )
    with pytest.raises(HistoricalTrafficSourceUnavailable):
        _history(analytics_stack)


def test_real_sql_deadline_interrupt_remains_distinct(analytics_stack):
    with pytest.raises(AnalyticsQueryDeadlineExceeded):
        _service(analytics_stack).get_site_history(
            SITE, from_utc="2026-01-01T11:55:00.000Z", to_utc=EVALUATED,
            evaluated_at_utc=EVALUATED, bucket_seconds=300,
            deadline=QueryDeadline.after(-1),
        )


def test_attempt_categories_are_nonoverlapping_as_of(analytics_stack):
    for result, suffix in (("partial", "partial"), ("failed", "failed"),
                           ("shutdown", "shutdown")):
        _cycle(
            analytics_stack, "quality-" + suffix,
            "2026-01-01T11:57:00.000Z", result=result, complete=False,
        )
    analytics_stack.observations.create_cycle(
        kind="ap_dynamic", site_id=SITE,
        started_at="2026-01-01T11:58:00.000Z", cycle_id="quality-running",
    )
    analytics_stack.observations.create_cycle(
        kind="ap_dynamic", site_id=SITE,
        started_at="2026-01-01T11:56:00.000Z", cycle_id="quality-abandoned",
    )
    with analytics_stack.observations._connect() as connection:
        connection.execute(
            """UPDATE observation_cycles
               SET state='abandoned', abandoned_at=?, complete=0
               WHERE cycle_id='quality-abandoned'""",
            ("2026-01-01T11:56:30.000Z",),
        )
    quality = _history(analytics_stack).quality
    assert quality.partial_cycle_count == 1
    assert quality.failed_cycle_count == 1
    assert quality.shutdown_cycle_count == 1
    assert quality.abandoned_cycle_count == 1
    assert quality.running_cycle_count == 1


def test_future_terminal_attempts_are_running_as_of_evaluation(analytics_stack):
    _cycle(
        analytics_stack, "completed-after-evaluation",
        "2026-01-01T12:00:30.000Z", result="partial", complete=False,
        started="2026-01-01T11:59:30.000Z",
    )
    analytics_stack.observations.create_cycle(
        kind="ap_dynamic", site_id=SITE,
        started_at="2026-01-01T11:59:20.000Z",
        cycle_id="abandoned-after-evaluation",
    )
    with analytics_stack.observations._connect() as connection:
        connection.execute(
            """UPDATE observation_cycles
               SET state='abandoned', abandoned_at=?, complete=0
               WHERE cycle_id='abandoned-after-evaluation'""",
            ("2026-01-01T12:00:40.000Z",),
        )
    quality = _history(analytics_stack).quality
    assert quality.running_cycle_count == 2
    assert quality.partial_cycle_count == 0
    assert quality.abandoned_cycle_count == 0


def test_dynamic_whole_day_fallback_is_deterministic(analytics_stack):
    end = datetime(2026, 1, 1, 12, tzinfo=UTC)
    start = end - timedelta(days=5000)
    result = _service(analytics_stack).get_site_history(
        "site-without-history",
        from_utc=start.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        to_utc=EVALUATED, evaluated_at_utc=EVALUATED,
    )
    required = __import__("math").ceil((end - start).total_seconds() / 720)
    expected = __import__("math").ceil(required / 86400) * 86400
    assert result.range.bucket_seconds == expected
    assert result.range.bucket_count <= 720


def test_source_timestamp_outside_cycle_is_integrity_failure(analytics_stack):
    finish = "2026-01-01T11:59:00.000Z"
    row = _row("bad-time", "02:AA:BB:CC:DD:39",
               "2026-01-01T11:58:00.000Z")
    _cycle(analytics_stack, "bad-time", finish, [row],
           started="2026-01-01T11:58:30.000Z")
    with pytest.raises(HistoricalTrafficSourceUnavailable):
        _history(analytics_stack)


def test_future_cycles_are_invisible_to_values_bounds_and_watermark(analytics_stack):
    past = "2026-01-01T11:59:00.000Z"
    _cycle(analytics_stack, "past", past, [
        _row("past", "02:AA:BB:CC:DD:14", past,
             wired=(7.0, 8.0), lan=(9.0, 10.0))
    ])
    timestamp = "2026-01-01T12:01:00.000Z"
    _cycle(analytics_stack, "future", timestamp, [
        _row("future", "02:AA:BB:CC:DD:15", timestamp,
             wired=(70.0, 80.0), lan=(90.0, 100.0))
    ])
    result = _history(analytics_stack)
    assert result.coverage.canonical_cycle_count == 1
    assert result.coverage.available_from_utc == past
    assert result.coverage.available_through_utc == past
    assert result.coverage.source_watermark_utc == past
    assert result.coverage.source_age_seconds == 60.0
    assert result.buckets[0].download_mbps == 7.0
    assert result.buckets[0].upload_mbps == 8.0
    assert result.buckets[0].total_mbps == 15.0


def test_attempts_are_provenance_and_do_not_degrade_complete_bucket(analytics_stack):
    for suffix, timestamp in (("a", "2026-01-01T11:55:30.000Z"),
                              ("b", "2026-01-01T11:58:00.000Z"),
                              ("c", "2026-01-01T11:59:30.000Z")):
        cycle = "attempt-good-" + suffix
        _cycle(analytics_stack, cycle, timestamp, [
            _row(cycle, "02:AA:BB:CC:DD:15", timestamp)
        ])
    _cycle(analytics_stack, "attempt-failed", "2026-01-01T11:57:00.000Z",
           result="failed", complete=False)
    result = _history(analytics_stack)
    assert result.buckets[0].status == "complete"
    assert result.quality.failed_cycle_count == 1


def test_attempt_with_unacceptable_evidence_gap_is_partial(analytics_stack):
    for suffix, timestamp in (
        ("a", "2026-01-01T11:55:00.000Z"),
        ("b", "2026-01-01T11:58:01.000Z"),
        ("c", "2026-01-01T11:59:59.000Z"),
    ):
        cycle = "gap-evidence-" + suffix
        _cycle(analytics_stack, cycle, timestamp, [
            _row(cycle, "02:AA:BB:CC:DD:17", timestamp)
        ])
    _cycle(
        analytics_stack, "gap-evidence-partial",
        "2026-01-01T11:57:00.000Z", result="partial", complete=False,
    )
    result = _history(analytics_stack)
    assert result.quality.partial_cycle_count == 1
    assert result.buckets[0].max_inter_sample_gap_seconds == 181.0
    assert result.buckets[0].status == "partial"


def test_claimed_complete_integrity_contradiction_is_terminal(analytics_stack):
    timestamp = "2026-01-01T11:59:00.000Z"
    _cycle(analytics_stack, "corrupt", timestamp, [
        _row("corrupt", "02:AA:BB:CC:DD:16", timestamp)
    ])
    with analytics_stack.observations._connect() as connection:
        connection.execute(
            "UPDATE observation_cycles SET source_rows_reported=2 "
            "WHERE cycle_id='corrupt'"
        )
    with pytest.raises(HistoricalTrafficSourceUnavailable):
        _history(analytics_stack)


def test_read_is_query_only_and_preserves_database_fingerprint(analytics_stack):
    path = analytics_stack.observations.db_path
    with analytics_stack.observations._connect() as connection:
        before_version = connection.execute("PRAGMA user_version").fetchone()[0]
        before_counts = tuple(connection.execute(
            "SELECT (SELECT COUNT(*) FROM observation_cycles), "
            "(SELECT COUNT(*) FROM ap_observations)"
        ).fetchone())
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    _history(analytics_stack)
    after = hashlib.sha256(path.read_bytes()).hexdigest()
    with analytics_stack.observations._connect() as connection:
        after_version = connection.execute("PRAGMA user_version").fetchone()[0]
        after_counts = tuple(connection.execute(
            "SELECT (SELECT COUNT(*) FROM observation_cycles), "
            "(SELECT COUNT(*) FROM ap_observations)"
        ).fetchone())
    with ObservationReadService(
        analytics_stack.observations
    ).analytics_read_connection() as connection:
        assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
    assert after == before
    assert after_counts == before_counts
    assert after_version == before_version == 1


def test_explain_uses_existing_site_time_and_cycle_ap_indexes(analytics_stack):
    plan = analytics_stack.gateway.explain_historical_traffic(
        site_id=SITE, from_utc="2026-01-01T11:55:00.000Z", to_utc=EVALUATED,
        evaluated_at_utc=EVALUATED, bucket_seconds=300,
        gap_threshold_seconds=180,
        max_site_sample_source_skew_seconds=(
            MAX_SITE_SAMPLE_SOURCE_SKEW_SECONDS
        ),
        deadline=QueryDeadline.after(2),
    )
    text = "\n".join(plan)
    assert "idx_cycles_site_kind_started" in text
    assert "sqlite_autoindex_ap_observations_1" in text
    assert "CROSS JOIN" not in text
