from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.analytics.historical_traffic import (
    HistoricalTrafficReadService,
    _busiest_bucket,
    _busiest_hour,
)
from app.analytics.source_gateway import (
    QueryDeadline,
    _HISTORICAL_PEAK_COMBINED_SQL,
    _HISTORICAL_PEAK_ONLY_COMBINED_SQL,
)

from .test_historical_traffic_statistics import SITE, _cycle


UTC = timezone.utc


def _read(stack, start, end, *, peak=True, statistics=True, bucket_seconds=300):
    return HistoricalTrafficReadService(
        stack.gateway,
        quality_gap_threshold_seconds=180,
        clock=lambda: datetime.fromisoformat(end.replace("Z", "+00:00")),
    ).get_site_history(
        SITE,
        from_utc=start,
        to_utc=end,
        evaluated_at_utc=end,
        bucket_seconds=bucket_seconds,
        include_period_statistics=statistics,
        include_peak_load=peak,
    )


def _minute_series(stack, start, values):
    current = datetime.fromisoformat(start.replace("Z", "+00:00"))
    for index, (download, upload) in enumerate(values):
        finished = current + timedelta(minutes=index)
        _cycle(
            stack,
            f"peak-{index:03d}",
            finished.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            wired=(download, upload),
        )


def test_peak_events_ties_busiest_bucket_and_complete_rolling_hour(analytics_stack):
    values = [(1.0, 2.0)] * 61
    values[10] = (9.0, 1.0)
    values[20] = (1.0, 8.0)
    values[30] = (6.0, 6.0)
    values[40] = (9.0, 1.0)
    values[50] = (4.0, 8.0)
    _minute_series(analytics_stack, "2026-01-01T11:00:00.000Z", values)

    result = _read(
        analytics_stack,
        "2026-01-01T11:00:00.000Z",
        "2026-01-01T12:05:00.000Z",
    )
    peak = result.peak_load
    assert peak is not None and peak.status == "partial"
    assert peak.events["download"].value_mbps == 9
    assert peak.events["download"].sample_at_utc == "2026-01-01T11:10:00.000Z"
    assert peak.events["download"].occurrence_count == 2
    assert peak.events["upload"].value_mbps == 8
    assert peak.events["upload"].sample_at_utc == "2026-01-01T11:20:00.000Z"
    assert peak.events["upload"].occurrence_count == 2
    assert peak.events["total"].value_mbps == 12
    assert peak.events["total"].sample_at_utc == "2026-01-01T11:30:00.000Z"
    assert peak.events["total"].occurrence_count == 2
    assert peak.events["total"].value_mbps != (
        peak.events["download"].value_mbps + peak.events["upload"].value_mbps
    )
    assert peak.events["total"].value_mbps == result.period_statistics.peak.total_mbps
    assert peak.busiest_bucket.status == "ok"
    assert peak.busiest_bucket.method == "max_complete_history_bucket_total_mean.v1"
    assert peak.busiest_hour.status == "ok"
    assert peak.busiest_hour.duration_seconds == 3600
    assert peak.busiest_hour.accepted_interval_seconds == 3600
    assert peak.busiest_hour.selected_source == "wired"
    assert peak.busiest_hour.window_start_utc == "2026-01-01T11:00:00.000Z"
    assert not hasattr(peak.busiest_hour, "occurrence_count")


def test_peak_real_zero_is_not_missing_and_no_samples_are_insufficient(analytics_stack):
    _minute_series(
        analytics_stack,
        "2026-01-01T11:00:00.000Z",
        [(0.0, 0.0)] * 61,
    )
    zero = _read(
        analytics_stack,
        "2026-01-01T11:00:00.000Z",
        "2026-01-01T12:05:00.000Z",
    ).peak_load
    assert tuple(zero.events[name].value_mbps for name in ("download", "upload", "total")) == (0.0, 0.0, 0.0)
    assert zero.busiest_hour.average_total_mbps == 0.0

    empty = _read(
        analytics_stack,
        "2026-01-02T11:00:00.000Z",
        "2026-01-02T12:05:00.000Z",
    ).peak_load
    assert empty.status == "insufficient_data"
    assert all(event.value_mbps is None and event.occurrence_count == 0 for event in empty.events.values())
    assert empty.busiest_bucket.status == "insufficient_data"
    assert empty.busiest_hour.status == "insufficient_data"


def test_peak_only_does_not_compute_or_expose_period_average(
    analytics_stack, monkeypatch,
):
    _cycle(analytics_stack, "peak-only", "2026-01-01T11:30:00.000Z")
    service = HistoricalTrafficReadService(
        analytics_stack.gateway,
        clock=lambda: datetime(2026, 1, 1, 12, tzinfo=UTC),
    )
    monkeypatch.setattr(
        service,
        "_period_statistics",
        lambda *_args, **_kwargs: pytest.fail("Peak-only computed Period Average"),
    )
    peak_only = service.get_site_history(
        SITE,
        from_utc="2026-01-01T11:00:00.000Z",
        to_utc="2026-01-01T12:00:00.000Z",
        evaluated_at_utc="2026-01-01T12:00:00.000Z",
        bucket_seconds=300,
        include_peak_load=True,
    )
    assert peak_only.peak_load is not None
    assert peak_only.period_statistics is None
    statistics = _read(
        analytics_stack,
        "2026-01-01T11:00:00.000Z",
        "2026-01-01T12:00:00.000Z",
        peak=False,
    ).period_statistics
    assert statistics is not None
    assert tuple(
        peak_only.peak_load.events[name].value_mbps
        for name in ("download", "upload", "total")
    ) == (
        statistics.peak.download_mbps,
        statistics.peak.upload_mbps,
        statistics.peak.total_mbps,
    )
    assert "THEN download*elapsed_seconds" not in _HISTORICAL_PEAK_ONLY_COMBINED_SQL
    assert "THEN upload*elapsed_seconds" not in _HISTORICAL_PEAK_ONLY_COMBINED_SQL
    assert "THEN download*elapsed_seconds" in _HISTORICAL_PEAK_COMBINED_SQL


def test_statistics_only_stays_unchanged(analytics_stack):
    _cycle(analytics_stack, "statistics-only", "2026-01-01T11:30:00.000Z")
    result = _read(
        analytics_stack,
        "2026-01-01T11:00:00.000Z",
        "2026-01-01T12:00:00.000Z",
        peak=False,
    )
    assert result.period_statistics is not None
    assert result.peak_load is None


def test_peak_combined_projection_preserves_exact_history_and_statistics(analytics_stack):
    _cycle(analytics_stack, "equivalence-a", "2026-01-01T11:56:00.000Z", wired=(2, 1))
    _cycle(analytics_stack, "equivalence-b", "2026-01-01T11:57:00.000Z", wired=(4, 2))
    statistics = _read(
        analytics_stack,
        "2026-01-01T11:55:00.000Z",
        "2026-01-01T12:00:00.000Z",
        peak=False,
    )
    peak = _read(
        analytics_stack,
        "2026-01-01T11:55:00.000Z",
        "2026-01-01T12:00:00.000Z",
    )
    assert replace(peak, peak_load=None) == statistics


def test_lan_fallback_is_valid_peak_and_rolling_hour_source(analytics_stack):
    current = datetime(2026, 1, 1, 11, tzinfo=UTC)
    for index in range(61):
        finished = current + timedelta(minutes=index)
        _cycle(
            analytics_stack,
            f"lan-peak-{index:03d}",
            finished.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            wired=(None, None),
            lan=(2.0, 1.0),
        )
    peak = _read(
        analytics_stack,
        "2026-01-01T11:00:00.000Z",
        "2026-01-01T12:05:00.000Z",
    ).peak_load
    assert all(event.selected_source == "lan" for event in peak.events.values())
    assert peak.busiest_hour.status == "ok"
    assert peak.busiest_hour.selected_source == "lan"


def test_busiest_bucket_ignores_higher_partial_and_ties_choose_earliest(analytics_stack):
    empty = _read(
        analytics_stack,
        "2026-01-01T11:50:00.000Z",
        "2026-01-01T12:00:00.000Z",
    )
    first, second = empty.buckets
    partial = replace(first, status="partial", total_mbps=20.0, selected_source="wired")
    complete = replace(second, status="complete", total_mbps=7.0, selected_source="wired")
    winner = _busiest_bucket((partial, complete))
    assert winner.status == "ok"
    assert winner.average_total_mbps == 7.0
    assert winner.bucket_start_utc == second.bucket_start_utc

    tied_first = replace(first, status="complete", total_mbps=7.0, selected_source="wired")
    tied = _busiest_bucket((tied_first, complete))
    assert tied.bucket_start_utc == first.bucket_start_utc
    assert tied.occurrence_count == 2


def test_valid_peak_events_without_complete_periods_are_partial(analytics_stack):
    _cycle(analytics_stack, "partial-peak-a", "2026-01-01T11:58:01.000Z", wired=(2, 1))
    _cycle(analytics_stack, "partial-peak-b", "2026-01-01T11:59:01.000Z", wired=(4, 2))
    peak = _read(
        analytics_stack,
        "2026-01-01T11:55:00.000Z",
        "2026-01-01T12:00:00.000Z",
    ).peak_load
    assert peak.status == "partial"
    assert peak.events["total"].value_mbps == 6
    assert peak.busiest_bucket.status == "insufficient_data"
    assert peak.busiest_hour.status == "insufficient_data"


def _rolling_samples(
    values,
    *,
    source="wired",
    start=None,
    step=timedelta(minutes=1),
):
    origin = start or datetime(2026, 1, 1, 9, tzinfo=UTC)
    result = []
    previous = None
    for index, value in enumerate(values):
        sample_at = origin + index * step
        result.append({
            "sample_at": sample_at,
            "sample_at_utc": sample_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "selected_source": source,
            "download": value,
            "upload": 0.0,
            "total": value,
            "previous_at": previous,
            "interval_result": "first" if previous is None else "accepted",
        })
        previous = sample_at
    return result


def _busiest_hour_oracle(samples):
    window_seconds = 3600.0
    chains = []
    current = []
    for sample in samples:
        if sample["interval_result"] != "accepted":
            if current:
                chains.append(current)
                current = []
            continue
        interval = (
            sample["previous_at"].timestamp(),
            sample["sample_at"].timestamp(),
            float(sample["total"]),
            sample["selected_source"],
        )
        if current and (
            current[-1][1] != interval[0]
            or current[-1][3] != interval[3]
        ):
            chains.append(current)
            current = []
        current.append(interval)
    if current:
        chains.append(current)

    winner = None
    for chain in chains:
        chain_start = chain[0][0]
        chain_end = chain[-1][1]
        if chain_end - chain_start < window_seconds:
            continue
        latest_start = chain_end - window_seconds
        candidates = {
            boundary
            for interval in chain
            for boundary in (interval[0], interval[1] - window_seconds)
            if chain_start <= boundary <= latest_start
        }
        candidates.update((chain_start, latest_start))
        for candidate in sorted(candidates):
            window_end = candidate + window_seconds
            area = sum(
                max(
                    min(interval[1], window_end)
                    - max(interval[0], candidate),
                    0.0,
                ) * interval[2]
                for interval in chain
            )
            possible = (area / window_seconds, candidate, chain[0][3])
            if winner is None or possible[0] > winner[0] or (
                possible[0] == winner[0] and possible[1] < winner[1]
            ):
                winner = possible
    return winner


@pytest.mark.parametrize(
    "case",
    (
        "sustained",
        "separated_equal",
        "continuous_plateau",
        "source_transition",
        "gap",
        "exact_hour",
        "24h_boundary",
        "7d_boundary",
    ),
)
def test_linear_rolling_hour_matches_canonical_oracle(case):
    step = timedelta(minutes=1)
    values = [3.0] * 61
    if case == "sustained":
        values = [0.0] * 181
        values[61:121] = [10.0] * 60
    elif case == "separated_equal":
        values = [0.0] + [10.0] * 60 + [1.0] * 60 + [10.0] * 60
    elif case == "continuous_plateau":
        values = [5.0] * 121
    elif case in {"source_transition", "gap"}:
        values = [3.0] * 121
    elif case == "24h_boundary":
        step = timedelta(minutes=30)
        values = [float((index * 7) % 11) for index in range(49)]
    elif case == "7d_boundary":
        step = timedelta(minutes=30)
        values = [float((index * 7) % 11) for index in range(337)]

    samples = _rolling_samples(values, step=step)
    if case in {"source_transition", "gap"}:
        samples[len(samples) // 2]["interval_result"] = case
    expected = _busiest_hour_oracle(samples)
    actual = _busiest_hour(tuple(samples))
    if expected is None:
        assert actual.status == "insufficient_data"
    else:
        average, window_start, source = expected
        assert actual.status == "ok"
        assert actual.average_total_mbps == pytest.approx(average)
        assert actual.window_start_utc == (
            datetime.fromtimestamp(window_start, UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )
        assert actual.selected_source == source


def test_rolling_hour_prefers_sustained_load_and_plateau_earliest_start():
    values = [0.0] * 181
    values[10] = 100.0
    values[61:121] = [10.0] * 60
    winner = _busiest_hour(tuple(_rolling_samples(values)))
    assert winner.status == "ok"
    assert winner.window_start_utc == "2026-01-01T10:00:00.000Z"
    assert winner.average_total_mbps == pytest.approx(10.0)
    assert winner.accepted_interval_seconds == 3600
    assert not hasattr(winner, "occurrence_count")


def test_rolling_hour_equal_separated_maxima_choose_earliest_start():
    values = [0.0] + [10.0] * 60 + [1.0] * 60 + [10.0] * 60
    winner = _busiest_hour(tuple(_rolling_samples(values)))
    assert winner.status == "ok"
    assert winner.average_total_mbps == pytest.approx(10.0)
    assert winner.window_start_utc == "2026-01-01T09:00:00.000Z"


@pytest.mark.parametrize(
    ("duration", "bucket_seconds"),
    ((timedelta(hours=24), 300), (timedelta(days=7), 900)),
)
def test_peak_products_share_half_open_history_range_boundaries(
    analytics_stack, duration, bucket_seconds,
):
    end = datetime(2026, 1, 8, 12, tzinfo=UTC)
    start = end - duration
    for index in range(61):
        sample_at = start + timedelta(minutes=index)
        value = (5.0, 1.0) if index == 30 else (1.0, 1.0)
        _cycle(
            analytics_stack,
            f"boundary-{bucket_seconds}-{index:03d}",
            sample_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            wired=value,
        )
    _cycle(
        analytics_stack,
        f"boundary-{bucket_seconds}-at-end",
        end.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        wired=(100.0, 100.0),
    )
    start_text = start.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    end_text = end.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    result = _read(
        analytics_stack, start_text, end_text, bucket_seconds=bucket_seconds,
    )
    peak = result.peak_load
    assert result.range.from_utc == start_text
    assert result.range.to_utc == result.range.evaluated_at_utc == end_text
    assert peak.events["total"].value_mbps == 6.0
    assert start_text <= peak.events["total"].sample_at_utc < end_text
    assert peak.events["total"].sample_at_utc != end_text
    assert start_text <= peak.busiest_bucket.bucket_start_utc
    assert peak.busiest_bucket.bucket_end_utc <= end_text
    assert start_text <= peak.busiest_hour.window_start_utc
    assert peak.busiest_hour.window_end_utc <= end_text


@pytest.mark.parametrize("break_result", ["gap", "source_transition", "invalid"])
def test_rolling_hour_rejects_any_nonaccepted_interval_inside_window(break_result):
    samples = _rolling_samples([1.0] * 61)
    samples[30]["interval_result"] = break_result
    assert _busiest_hour(tuple(samples)).status == "insufficient_data"


def test_peak_projection_reuses_one_materialized_requested_range_validation(analytics_stack):
    plan = analytics_stack.gateway.explain_historical_traffic_combined(
        site_id=SITE,
        from_utc="2026-01-01T11:55:00.000Z",
        to_utc="2026-01-01T12:00:00.000Z",
        evaluated_at_utc="2026-01-01T12:00:00.000Z",
        bucket_seconds=300,
        gap_threshold_seconds=180,
        max_site_sample_source_skew_seconds=60,
        deadline=QueryDeadline.after(10),
        include_peak_load=True,
    )
    text = "\n".join(plan)
    assert text.count("MATERIALIZE candidate_cycles") == 1
    assert text.count("MATERIALIZE cycle_aggregates") == 1
    assert text.count("MATERIALIZE validated_cycles") == 1
    assert text.count("MATERIALIZE ranged") == 1
    assert text.count("MATERIALIZE bucket_selection") == 1
    assert "idx_cycles_site_kind_started" in text
    assert "sqlite_autoindex_ap_observations_1" in text
    assert "MATERIALIZE statistics_classified" in text
    assert text.count("SCAN statistics_ordered") == 1


def test_peak_projection_returns_ordered_typed_rows_without_text_payload(
    analytics_stack,
):
    _cycle(
        analytics_stack,
        "typed-peak-a",
        "2026-01-01T11:56:00.000Z",
        wired=(2, 1),
    )
    _cycle(
        analytics_stack,
        "typed-peak-b",
        "2026-01-01T11:57:00.000Z",
        wired=(4, 2),
    )
    data = analytics_stack.gateway.historical_traffic_data(
        site_id=SITE,
        from_utc="2026-01-01T11:55:00.000Z",
        to_utc="2026-01-01T12:00:00.000Z",
        evaluated_at_utc="2026-01-01T12:00:00.000Z",
        bucket_seconds=300,
        gap_threshold_seconds=180,
        max_site_sample_source_skew_seconds=60,
        deadline=QueryDeadline.after(10),
        include_period_statistics=True,
        include_peak_load=True,
    )
    samples = data["peak_samples"]
    assert tuple(sample["finished_at"] for sample in samples) == (
        "2026-01-01T11:56:00.000Z",
        "2026-01-01T11:57:00.000Z",
    )
    assert samples[1]["previous_at"] == samples[0]["finished_at"]
    assert type(samples[0]["download"]) in {int, float}
    assert "GROUP_CONCAT" not in _HISTORICAL_PEAK_COMBINED_SQL
    assert "peak_samples_payload" not in _HISTORICAL_PEAK_COMBINED_SQL
