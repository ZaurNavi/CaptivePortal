from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest

from app.analytics.historical_traffic import HistoricalTrafficReadService
from app.analytics.source_gateway import QueryDeadline


UTC = timezone.utc
SITE = "site-a"
START = "2026-01-01T11:55:00.000Z"
END = "2026-01-01T12:00:00.000Z"


def _row(cycle_id, observed, *, wired=(1.0, 2.0), lan=(3.0, 4.0), site=SITE):
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
        "ap_mac": "02:AA:BB:CC:DD:10", "partial": False,
        "overview_ok": True, "wired_uplink_ok": True,
        "lan_traffic_ok": True, "radios_ok": True,
        "wired_observed_at": observed, "wired_download_mbps": wd,
        "wired_upload_mbps": wu, "wired_download_rate_reason": wdr,
        "wired_upload_rate_reason": wur, "lan_observed_at": observed,
        "lan_rx_mbps": ld, "lan_tx_mbps": lu,
        "lan_rx_rate_reason": ldr, "lan_tx_rate_reason": lur,
    }


def _cycle(stack, cycle_id, finished, *, wired=(1.0, 2.0), lan=(3.0, 4.0),
           empty=False, site=SITE):
    stack.observations.create_cycle(
        kind="ap_dynamic", site_id=site, started_at=finished, cycle_id=cycle_id
    )
    if not empty:
        stack.observations.insert_ap_batch([
            (_row(cycle_id, finished, wired=wired, lan=lan, site=site), ())
        ])
    count = 0 if empty else 1
    stack.observations.finalize_cycle(
        cycle_id, finished_at=finished, complete=True, result="success",
        source_rows_reported=count, items_seen=count, items_stored=count,
    )


def _read(stack, *, start=START, end=END, gap=180.0, include=True):
    return HistoricalTrafficReadService(
        stack.gateway,
        quality_gap_threshold_seconds=gap,
        clock=lambda: datetime(2026, 1, 1, 12, tzinfo=UTC),
    ).get_site_history(
        SITE,
        from_utc=start,
        to_utc=end,
        evaluated_at_utc=end,
        bucket_seconds=300,
        include_period_statistics=include,
    )


def test_statistics_are_opt_in_and_time_weight_right_endpoint_samples(analytics_stack):
    _cycle(analytics_stack, "stats-a", "2026-01-01T11:55:00.000Z", wired=(1, 2))
    _cycle(analytics_stack, "stats-b", "2026-01-01T11:55:30.000Z", wired=(1, 2))
    _cycle(analytics_stack, "stats-c", "2026-01-01T11:57:00.000Z", wired=(3, 6))

    assert _read(analytics_stack, include=False).period_statistics is None
    result = _read(analytics_stack)
    statistics = result.period_statistics
    assert statistics is not None and statistics.status == "ok"
    assert statistics.average.download_mbps == pytest.approx(2.5)
    assert statistics.average.upload_mbps == pytest.approx(5.0)
    assert statistics.average.total_mbps == pytest.approx(7.5)
    assert statistics.peak.download_mbps == 3
    assert statistics.peak.upload_mbps == 6
    assert statistics.peak.total_mbps == 9
    assert statistics.average.download_mbps != pytest.approx((1 + 3) / 2)
    assert result.buckets[0].download_mbps == pytest.approx((1 + 1 + 3) / 3)
    assert statistics.average.download_mbps != pytest.approx(
        result.buckets[0].download_mbps
    )
    assert statistics.metric_version == "network_traffic_period_statistics.v1"
    assert statistics.average_method == "right_endpoint_sample_hold_time_weighted.v1"
    assert statistics.peak_method == "max_accepted_complete_site_sample.v1"
    evidence = statistics.interval_evidence
    assert evidence.candidate_interval_count == 2
    assert evidence.accepted_interval_count == 2
    assert evidence.accepted_interval_seconds == 120
    assert evidence.interval_coverage_ratio == pytest.approx(.4)
    assert evidence.leading_unweighted_seconds == 0
    assert evidence.trailing_unweighted_seconds == 180


def test_statistics_peak_total_is_one_sample_not_directional_peak_sum(analytics_stack):
    _cycle(analytics_stack, "peak-a", "2026-01-01T11:56:00.000Z", wired=(9, 1))
    _cycle(analytics_stack, "peak-b", "2026-01-01T11:57:00.000Z", wired=(1, 8))
    _cycle(analytics_stack, "peak-c", "2026-01-01T11:58:00.000Z", wired=(6, 6))
    peak = _read(analytics_stack).period_statistics.peak
    assert (peak.download_mbps, peak.upload_mbps, peak.total_mbps) == (9, 8, 12)


def test_source_transition_precedes_overlapping_excessive_gap(analytics_stack):
    _cycle(analytics_stack, "source-a", "2026-01-01T11:54:00.000Z", wired=(2, 1))
    _cycle(
        analytics_stack, "source-b", "2026-01-01T11:57:01.000Z",
        wired=(None, None), lan=(4, 2),
    )
    result = _read(
        analytics_stack, start="2026-01-01T11:50:00.000Z"
    )
    stats = result.period_statistics
    assert stats.status == "partial"
    assert stats.average.download_mbps is None
    assert stats.peak.total_mbps == 6
    assert stats.interval_evidence.excluded_source_transition_interval_count == 1
    assert stats.interval_evidence.excluded_gap_interval_count == 0
    assert stats.interval_evidence.invalid_period_interval_count == 0
    assert stats.interval_evidence.accepted_peak_sample_count == 2
    assert stats.interval_evidence.candidate_interval_count == (
        stats.interval_evidence.accepted_interval_count
        + stats.interval_evidence.invalid_period_interval_count
        + stats.interval_evidence.excluded_source_transition_interval_count
        + stats.interval_evidence.excluded_gap_interval_count
    )
    assert result.coverage.source_transition_count == 1


def test_lan_fallback_samples_are_accepted_without_degrading_statistics(analytics_stack):
    _cycle(
        analytics_stack, "fallback-a", "2026-01-01T11:56:00.000Z",
        wired=(None, None), lan=(2, 1),
    )
    _cycle(
        analytics_stack, "fallback-b", "2026-01-01T11:57:00.000Z",
        wired=(None, None), lan=(4, 2),
    )
    result = _read(analytics_stack)
    statistics = result.period_statistics
    assert result.status == "ok"
    assert result.buckets[0].selected_source == "lan"
    assert statistics.status == "ok"
    assert statistics.average.download_mbps == 4
    assert statistics.average.upload_mbps == 2
    assert statistics.peak.download_mbps == 4
    assert statistics.peak.upload_mbps == 2
    assert statistics.peak.total_mbps == 6
    assert statistics.interval_evidence.accepted_interval_count == 1
    assert statistics.interval_evidence.excluded_source_transition_interval_count == 0


def test_consecutive_accepted_zero_samples_are_numeric_not_missing(analytics_stack):
    _cycle(
        analytics_stack, "zero-a", "2026-01-01T11:56:00.000Z",
        wired=(0.0, 0.0),
    )
    _cycle(
        analytics_stack, "zero-b", "2026-01-01T11:57:00.000Z",
        wired=(0.0, 0.0),
    )
    result = _read(analytics_stack)
    statistics = result.period_statistics
    assert result.status == "ok"
    assert statistics.status == "ok"
    assert (
        statistics.average.download_mbps,
        statistics.average.upload_mbps,
        statistics.average.total_mbps,
    ) == (0.0, 0.0, 0.0)
    assert (
        statistics.peak.download_mbps,
        statistics.peak.upload_mbps,
        statistics.peak.total_mbps,
    ) == (0.0, 0.0, 0.0)
    assert statistics.interval_evidence.accepted_interval_count > 0


def test_partial_history_is_inherited_while_numeric_statistics_remain(analytics_stack):
    _cycle(
        analytics_stack, "partial-history-a", "2026-01-01T11:58:01.000Z",
        wired=(2, 1),
    )
    _cycle(
        analytics_stack, "partial-history-b", "2026-01-01T11:59:01.000Z",
        wired=(4, 2),
    )
    result = _read(analytics_stack)
    statistics = result.period_statistics
    assert result.status == "partial"
    assert result.buckets[0].status == "partial"
    assert statistics.status == "partial"
    assert statistics.average.download_mbps == 4
    assert statistics.average.upload_mbps == 2
    assert statistics.peak.total_mbps == 6
    assert statistics.interval_evidence.accepted_interval_count == 1


def test_gap_and_invalid_elapsed_are_mutually_exclusive(analytics_stack):
    _cycle(analytics_stack, "gap-a", "2026-01-01T11:55:00.000Z")
    _cycle(analytics_stack, "gap-b", "2026-01-01T11:58:01.000Z")
    gap = _read(analytics_stack).period_statistics.interval_evidence
    assert gap.excluded_gap_interval_count == 1
    assert gap.invalid_period_interval_count == 0
    assert gap.accepted_interval_seconds == 0

    duplicate_stack = analytics_stack
    _cycle(duplicate_stack, "gap-c", "2026-01-01T11:58:01.000Z")
    duplicate = _read(duplicate_stack).period_statistics.interval_evidence
    assert duplicate.invalid_period_interval_count == 1
    assert duplicate.candidate_interval_count == (
        duplicate.accepted_interval_count
        + duplicate.invalid_period_interval_count
        + duplicate.excluded_source_transition_interval_count
        + duplicate.excluded_gap_interval_count
    )


def test_no_sample_is_insufficient_but_empty_population_is_real_zero(analytics_stack):
    none = _read(analytics_stack).period_statistics
    assert none.status == "insufficient_data"
    assert none.average.download_mbps is None and none.peak.total_mbps is None
    assert none.interval_evidence.accepted_peak_sample_count == 0

    _cycle(analytics_stack, "empty-stats", "2026-01-01T11:59:00.000Z", empty=True)
    empty = _read(analytics_stack).period_statistics
    assert empty.status == "partial"
    assert empty.average.total_mbps is None
    assert empty.peak.download_mbps == 0
    assert empty.peak.upload_mbps == 0
    assert empty.peak.total_mbps == 0


def test_site_isolation_and_half_open_boundary_are_preserved(analytics_stack):
    _cycle(analytics_stack, "other-site", "2026-01-01T11:56:00.000Z", site="site-b", wired=(99, 99))
    _cycle(analytics_stack, "at-start", START, wired=(1, 2))
    _cycle(analytics_stack, "at-end", END, wired=(100, 100))
    stats = _read(analytics_stack).period_statistics
    assert stats.interval_evidence.accepted_peak_sample_count == 1
    assert stats.peak.total_mbps == 3
    assert stats.interval_evidence.leading_unweighted_seconds == 0
    assert stats.interval_evidence.trailing_unweighted_seconds == 300


def test_statistics_projection_plan_uses_existing_site_and_cycle_indexes(analytics_stack):
    plan = analytics_stack.gateway.explain_historical_traffic_statistics(
        site_id=SITE,
        from_utc=START,
        to_utc=END,
        evaluated_at_utc=END,
        bucket_seconds=300,
        gap_threshold_seconds=180,
        max_site_sample_source_skew_seconds=60,
        deadline=QueryDeadline.after(10),
    )
    text = "\n".join(plan)
    assert "idx_cycles_site_kind_started" in text
    assert "sqlite_autoindex_ap_observations_1" in text


def test_statistics_share_query_only_snapshot_without_source_mutation(analytics_stack):
    _cycle(analytics_stack, "readonly-a", "2026-01-01T11:58:00.000Z")
    _cycle(analytics_stack, "readonly-b", "2026-01-01T11:59:00.000Z")
    path = analytics_stack.observations.db_path
    with analytics_stack.observations._connect() as connection:
        before_version = connection.execute("PRAGMA user_version").fetchone()[0]
        before_counts = tuple(connection.execute(
            "SELECT (SELECT COUNT(*) FROM observation_cycles), "
            "(SELECT COUNT(*) FROM ap_observations)"
        ).fetchone())
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    assert _read(analytics_stack).period_statistics.status == "ok"
    after = hashlib.sha256(path.read_bytes()).hexdigest()
    with analytics_stack.observations._connect() as connection:
        after_version = connection.execute("PRAGMA user_version").fetchone()[0]
        after_counts = tuple(connection.execute(
            "SELECT (SELECT COUNT(*) FROM observation_cycles), "
            "(SELECT COUNT(*) FROM ap_observations)"
        ).fetchone())
    assert (after, after_version, after_counts) == (
        before, before_version, before_counts,
    )
    assert before_version == 1
