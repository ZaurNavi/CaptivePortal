from __future__ import annotations

import dataclasses
import inspect
import sqlite3

import pytest

from app.analytics.current_traffic import (
    CurrentTrafficReadService,
    CurrentTrafficSourceUnavailable,
    CurrentTrafficValidationError,
    _encode_cursor,
)
from app.analytics.source_gateway import (
    AnalyticsQueryDeadlineExceeded,
    QueryDeadline,
)


SITE = "site-a"
EVALUATED = "2026-01-01T12:01:00.000Z"
POLICY = {
    "fresh_max_age_seconds": 60,
    "stale_max_age_seconds": 180,
    "max_ap_skew_seconds": 30,
}


def _service(stack):
    return CurrentTrafficReadService(stack.gateway)


def _row(
    cycle_id: str,
    mac: str,
    *,
    observed: str = "2026-01-01T12:00:30.000Z",
    wired=(1.0, 2.0, "ok", "ok"),
    lan=(3.0, 4.0, "ok", "ok"),
    wired_observed: str | None = None,
    lan_observed: str | None = None,
    name: str | None = None,
):
    return {
        "cycle_id": cycle_id,
        "observed_at": observed,
        "site_id": SITE,
        "ap_mac": mac,
        "partial": False,
        "overview_ok": True,
        "wired_uplink_ok": True,
        "lan_traffic_ok": True,
        "radios_ok": True,
        "wired_observed_at": observed if wired_observed is None else wired_observed,
        "wired_download_mbps": wired[0],
        "wired_upload_mbps": wired[1],
        "wired_download_rate_reason": wired[2],
        "wired_upload_rate_reason": wired[3],
        "lan_observed_at": observed if lan_observed is None else lan_observed,
        "lan_rx_mbps": lan[0],
        "lan_tx_mbps": lan[1],
        "lan_rx_rate_reason": lan[2],
        "lan_tx_rate_reason": lan[3],
        "name": name,
    }


def _cycle(
    stack,
    cycle_id: str,
    rows=(),
    *,
    started="2026-01-01T12:00:00.000Z",
    finished="2026-01-01T12:00:40.000Z",
    complete=True,
    result="success",
):
    repository = stack.observations
    repository.create_cycle(
        kind="ap_dynamic", site_id=SITE, started_at=started,
        cycle_id=cycle_id,
    )
    entries = [(item, ()) for item in rows]
    if entries:
        repository.insert_ap_batch(entries)
    count = len(entries)
    repository.finalize_cycle(
        cycle_id, finished_at=finished, complete=complete, result=result,
        source_rows_reported=count, items_seen=count, items_stored=count,
    )


def _summary(stack, **overrides):
    values = dict(POLICY)
    values.update(overrides)
    return _service(stack).get_current_site_traffic(
        SITE, evaluated_at_utc=EVALUATED, **values
    )


def test_no_cycle_and_empty_cycle_have_distinct_exact_semantics(analytics_stack):
    missing = _service(analytics_stack).get_current_site_traffic(
        "site-without-ap", evaluated_at_utc=EVALUATED, **POLICY
    )
    assert missing.snapshot.cycle_id is None
    assert missing.snapshot.complete is False
    assert missing.snapshot.selected_source is None
    assert missing.snapshot.selection_reason == "no_complete_snapshot"
    assert missing.snapshot.empty_population is False
    assert missing.coverage.status == "none"
    assert missing.traffic.total_mbps is None

    _cycle(analytics_stack, "empty")
    empty = _summary(analytics_stack)
    assert empty.snapshot.selected_source == "wired"
    assert empty.snapshot.selection_reason == "empty_population"
    assert empty.snapshot.empty_population is True
    assert empty.coverage.status == "complete"
    assert empty.traffic == dataclasses.replace(
        empty.traffic, download_mbps=0.0, upload_mbps=0.0, total_mbps=0.0
    )


def test_source_selection_and_direction_aggregation(analytics_stack):
    rows = [
        _row("traffic", "02:AA:BB:CC:DD:01"),
        _row(
            "traffic", "02:AA:BB:CC:DD:02",
            wired=(None, 5.0, "no_baseline", "ok"),
            lan=(6.0, 7.0, "ok", "ok"),
        ),
    ]
    _cycle(analytics_stack, "traffic", rows)
    result = _summary(analytics_stack)
    assert result.snapshot.primary_source == "wired"
    assert result.snapshot.selected_source == "lan"
    assert result.snapshot.selection_reason == "fallback_full_coverage"
    assert result.traffic.download_mbps == 9.0
    assert result.traffic.upload_mbps == 11.0
    assert result.traffic.total_mbps == 20.0
    assert result.coverage.valid_rate_ap_count == 2


@pytest.mark.parametrize(
    ("wired", "lan", "expected", "reason"),
    [
        ((1.0, 2.0, "ok", "ok"), (3.0, 4.0, "ok", "ok"), "wired", "primary_full_coverage"),
        ((None, None, "no_baseline", "no_baseline"), (3.0, 4.0, "ok", "ok"), "lan", "fallback_full_coverage"),
        ((None, 2.0, "no_baseline", "ok"), (3.0, None, "ok", "no_baseline"), "wired", "primary_preferred_tie_or_higher"),
    ],
)
def test_canonical_lowercase_source_selection(
    analytics_stack, wired, lan, expected, reason
):
    _cycle(analytics_stack, "selection", [
        _row("selection", "02:AA:BB:CC:DD:11", wired=wired, lan=lan)
    ])
    result = _summary(analytics_stack)
    assert result.snapshot.selected_source == expected
    assert result.snapshot.selection_reason == reason
    assert result.snapshot.selected_source not in {"LAN", "Wired", "Lan"}


def test_partial_direction_is_not_coerced_to_zero(analytics_stack):
    _cycle(analytics_stack, "partial-direction", [
        _row(
            "partial-direction", "02:AA:BB:CC:DD:12",
            wired=(None, 0.0, "no_baseline", "ok"),
            lan=(None, None, "no_baseline", "no_baseline"),
        )
    ])
    result = _summary(analytics_stack)
    assert result.traffic.download_mbps is None
    assert result.traffic.upload_mbps == 0.0
    assert result.traffic.total_mbps is None
    assert result.coverage.status == "partial"
    assert result.coverage.valid_upload_ap_count == 1


def test_lan_higher_partial_coverage_wins_without_blending(analytics_stack):
    rows = [
        _row(
            "higher", "02:AA:BB:CC:DD:40",
            wired=(1.0, 1.0, "ok", "ok"),
            lan=(2.0, 2.0, "ok", "ok"),
        ),
        _row(
            "higher", "02:AA:BB:CC:DD:41",
            wired=(None, None, "no_baseline", "no_baseline"),
            lan=(3.0, 3.0, "ok", "ok"),
        ),
        _row(
            "higher", "02:AA:BB:CC:DD:42",
            wired=(None, None, "no_baseline", "no_baseline"),
            lan=(None, None, "no_baseline", "no_baseline"),
        ),
    ]
    _cycle(analytics_stack, "higher", rows)
    result = _summary(analytics_stack)
    assert result.snapshot.selected_source == "lan"
    assert result.snapshot.selection_reason == "fallback_higher_coverage"
    assert result.source_selection.wired_pair_valid_ap_count == 1
    assert result.source_selection.lan_pair_valid_ap_count == 2
    assert result.traffic.total_mbps == 10.0


def test_reason_counters_are_nonexclusive_per_ap(analytics_stack):
    _cycle(analytics_stack, "reasons", [
        _row(
            "reasons", "02:AA:BB:CC:DD:43",
            wired=(None, None, "counter_reset", "gap_too_large"),
            lan=(None, None, "source_unavailable", "invalid_elapsed"),
        )
    ])
    result = _summary(analytics_stack)
    assert result.snapshot.selected_source == "wired"
    assert result.coverage.reset_ap_count == 1
    assert result.coverage.gap_rejected_ap_count == 1
    assert result.coverage.valid_rate_ap_count == 0
    assert result.coverage.missing_rate_ap_count == 1


@pytest.mark.parametrize(
    "wired",
    [
        (None, 1.0, "ok", "ok"),
        (-1.0, 1.0, "ok", "ok"),
        (1.0, 1.0, "no_baseline", "ok"),
        (None, 1.0, None, "ok"),
    ],
)
def test_rate_matrix_contradictions_are_source_unavailable(
    analytics_stack, wired
):
    _cycle(analytics_stack, "bad-rate", [
        _row("bad-rate", "02:AA:BB:CC:DD:13", wired=wired)
    ])
    with pytest.raises(CurrentTrafficSourceUnavailable):
        _summary(analytics_stack)


def test_missing_ok_timestamp_is_unavailable_and_non_ok_null_is_valid(
    analytics_stack,
):
    row = _row("missing-time", "02:AA:BB:CC:DD:30")
    row["wired_observed_at"] = None
    _cycle(analytics_stack, "missing-time", [row])
    with pytest.raises(CurrentTrafficSourceUnavailable):
        _summary(analytics_stack)


def test_cycle_tie_breaks_by_cycle_id_descending(analytics_stack):
    _cycle(analytics_stack, "tie-a", [
        _row("tie-a", "02:AA:BB:CC:DD:31", wired=(1.0, 1.0, "ok", "ok"))
    ])
    _cycle(analytics_stack, "tie-z", [
        _row("tie-z", "02:AA:BB:CC:DD:32", wired=(9.0, 9.0, "ok", "ok"))
    ])
    result = _summary(analytics_stack)
    assert result.snapshot.cycle_id == "tie-z"
    assert result.traffic.total_mbps == 18.0


def test_newer_non_success_attempt_does_not_replace_canonical(analytics_stack):
    _cycle(analytics_stack, "good", [
        _row("good", "02:AA:BB:CC:DD:14")
    ], started="2026-01-01T11:59:00.000Z",
       finished="2026-01-01T11:59:40.000Z")
    _cycle(
        analytics_stack, "failed", (),
        started="2026-01-01T12:00:50.000Z",
        finished="2026-01-01T12:00:55.000Z",
        complete=False, result="failed",
    )
    result = _summary(analytics_stack)
    assert result.snapshot.cycle_id == "good"
    assert result.snapshot.latest_attempt_state == "completed"
    assert result.snapshot.latest_attempt_result == "failed"
    assert result.snapshot.using_previous_complete_snapshot is True


@pytest.mark.parametrize("result_name", ["partial", "failed", "shutdown"])
def test_each_newer_completed_non_success_is_latest_only(
    analytics_stack, result_name
):
    _cycle(analytics_stack, "stable", [
        _row("stable", "02:AA:BB:CC:DD:44")
    ], started="2026-01-01T11:59:00.000Z",
       finished="2026-01-01T11:59:40.000Z")
    _cycle(
        analytics_stack, "attempt", (),
        started="2026-01-01T12:00:50.000Z",
        finished="2026-01-01T12:00:55.000Z",
        complete=False, result=result_name,
    )
    result = _summary(analytics_stack)
    assert result.snapshot.cycle_id == "stable"
    assert result.snapshot.latest_attempt_result == result_name
    assert result.snapshot.using_previous_complete_snapshot is True


def test_newer_running_attempt_is_latest_only(analytics_stack):
    _cycle(analytics_stack, "stable-running", [
        _row("stable-running", "02:AA:BB:CC:DD:45")
    ], started="2026-01-01T11:59:00.000Z",
       finished="2026-01-01T11:59:40.000Z")
    analytics_stack.observations.create_cycle(
        kind="ap_dynamic", site_id=SITE,
        started_at="2026-01-01T12:00:50.000Z", cycle_id="running",
    )
    result = _summary(analytics_stack)
    assert result.snapshot.cycle_id == "stable-running"
    assert result.snapshot.latest_attempt_state == "running"
    assert result.snapshot.latest_attempt_result is None
    assert result.snapshot.latest_attempt_at == "2026-01-01T12:00:50.000Z"


def test_integrity_counter_contradiction_is_source_unavailable(analytics_stack):
    _cycle(analytics_stack, "bad-count", [
        _row("bad-count", "02:AA:BB:CC:DD:15")
    ])
    with sqlite3.connect(analytics_stack.observations.db_path) as connection:
        connection.execute(
            "UPDATE observation_cycles SET items_seen=2 WHERE cycle_id='bad-count'"
        )
    with pytest.raises(CurrentTrafficSourceUnavailable):
        _summary(analytics_stack)


def test_temporal_clock_anomaly_hides_aggregate_traffic(analytics_stack):
    _cycle(analytics_stack, "future", [
        _row(
            "future", "02:AA:BB:CC:DD:16",
            observed="2026-01-01T12:02:00.000Z",
        )
    ], finished="2026-01-01T12:02:10.000Z")
    result = _summary(analytics_stack)
    assert result.freshness.status == "unavailable"
    assert result.freshness.reason == "clock_anomaly"
    assert result.freshness.age_seconds == 0.0
    assert result.traffic.total_mbps is None


def test_section_outside_capture_interval_is_clock_anomaly(analytics_stack):
    row = _row("bad-time", "02:AA:BB:CC:DD:33")
    row["wired_observed_at"] = "2026-01-01T11:59:59.000Z"
    _cycle(analytics_stack, "bad-time", [row])
    result = _summary(analytics_stack)
    assert result.freshness.status == "unavailable"
    assert result.freshness.reason == "clock_anomaly"
    assert result.coverage.unavailable_ap_count == 1


def test_skew_boundary_is_inclusive(analytics_stack):
    _cycle(analytics_stack, "skew", [
        _row(
            "skew", "02:AA:BB:CC:DD:34",
            observed="2026-01-01T12:00:10.000Z",
        ),
        _row(
            "skew", "02:AA:BB:CC:DD:35",
            observed="2026-01-01T12:00:40.000Z",
        ),
    ])
    assert _summary(analytics_stack).coverage.status == "complete"
    narrow = _summary(analytics_stack, max_ap_skew_seconds=29)
    assert narrow.coverage.status == "partial"
    assert "temporal_skew" in narrow.coverage.reasons


def test_fresh_stale_and_unavailable_boundaries(analytics_stack):
    _cycle(analytics_stack, "age", [
        _row("age", "02:AA:BB:CC:DD:17")
    ])
    assert _summary(analytics_stack).freshness.status == "fresh"
    assert _summary(
        analytics_stack, fresh_max_age_seconds=29
    ).freshness.status == "stale"
    assert _summary(
        analytics_stack, fresh_max_age_seconds=10,
        stale_max_age_seconds=29,
    ).freshness.status == "unavailable"


def test_ap_page_derives_source_and_cursor_is_bound(analytics_stack):
    _cycle(analytics_stack, "page", [
        _row(
            "page", f"02:AA:BB:CC:DD:{suffix:02X}",
            wired=(None, None, "no_baseline", "no_baseline"),
        )
        for suffix in range(1, 4)
    ])
    service = _service(analytics_stack)
    assert "selected_source" not in inspect.signature(
        service.list_current_ap_traffic
    ).parameters
    first = service.list_current_ap_traffic(
        SITE, cycle_id="page", evaluated_at_utc=EVALUATED,
        limit=2, **POLICY,
    )
    assert first.page.selected_source == "lan"
    assert [item.ap_mac for item in first.items] == [
        "02:AA:BB:CC:DD:01", "02:AA:BB:CC:DD:02"
    ]
    assert first.page.next_cursor is not None
    second = service.list_current_ap_traffic(
        SITE, cycle_id="page", evaluated_at_utc=EVALUATED,
        limit=2, cursor=first.page.next_cursor, **POLICY,
    )
    assert [item.ap_mac for item in second.items] == ["02:AA:BB:CC:DD:03"]
    assert second.page.next_cursor is None


def test_cursor_and_explicit_cycle_validation(analytics_stack):
    service = _service(analytics_stack)
    with pytest.raises(CurrentTrafficValidationError):
        service.list_current_ap_traffic(
            SITE, cycle_id="missing", evaluated_at_utc=EVALUATED, **POLICY
        )
    with pytest.raises(CurrentTrafficValidationError):
        service.list_current_ap_traffic(
            SITE, cycle_id="missing", evaluated_at_utc=EVALUATED,
            cursor="not-a-cursor", **POLICY,
        )


def test_cursor_source_mismatch_and_cross_site_are_rejected(analytics_stack):
    _cycle(analytics_stack, "bound", [
        _row(
            "bound", "02:AA:BB:CC:DD:19",
            wired=(None, None, "no_baseline", "no_baseline"),
        )
    ])
    service = _service(analytics_stack)
    forged = _encode_cursor(
        SITE, "bound", "wired", "02:AA:BB:CC:DD:19"
    )
    with pytest.raises(CurrentTrafficValidationError):
        service.list_current_ap_traffic(
            SITE, cycle_id="bound", evaluated_at_utc=EVALUATED,
            cursor=forged, **POLICY,
        )
    with pytest.raises(CurrentTrafficValidationError):
        service.list_current_ap_traffic(
            "site-b", cycle_id="bound", evaluated_at_utc=EVALUATED, **POLICY
        )


def test_noncanonical_and_overlong_cursors_are_rejected(analytics_stack):
    _cycle(analytics_stack, "cursor", [
        _row("cursor", "02:AA:BB:CC:DD:36")
    ])
    service = _service(analytics_stack)
    canonical = _encode_cursor(
        SITE, "cursor", "wired", "02:AA:BB:CC:DD:36"
    )
    for token in (canonical + "=", "x" * 1025):
        with pytest.raises(CurrentTrafficValidationError):
            service.list_current_ap_traffic(
                SITE, cycle_id="cursor", evaluated_at_utc=EVALUATED,
                cursor=token, **POLICY,
            )


def test_retained_older_complete_cycle_remains_pageable(analytics_stack):
    _cycle(analytics_stack, "old", [
        _row("old", "02:AA:BB:CC:DD:20")
    ], started="2026-01-01T11:58:00.000Z",
       finished="2026-01-01T11:58:30.000Z")
    _cycle(analytics_stack, "new", [
        _row("new", "02:AA:BB:CC:DD:21")
    ])
    page = _service(analytics_stack).list_current_ap_traffic(
        SITE, cycle_id="old", evaluated_at_utc=EVALUATED, **POLICY
    )
    assert page.snapshot.cycle_id == "old"
    assert page.items[0].ap_mac == "02:AA:BB:CC:DD:20"
    assert page.snapshot.using_previous_complete_snapshot is True


def test_expired_deadline_is_propagated(analytics_stack):
    with pytest.raises(AnalyticsQueryDeadlineExceeded):
        _service(analytics_stack).get_current_site_traffic(
            SITE, evaluated_at_utc=EVALUATED,
            deadline=QueryDeadline.after(0), **POLICY,
        )


def test_250_ap_page_is_bounded_and_indexed(analytics_stack):
    rows = []
    for value in range(250):
        mac = f"02:AA:BB:{(value >> 16) & 255:02X}:{(value >> 8) & 255:02X}:{value & 255:02X}"
        rows.append(_row("capacity", mac))
    _cycle(analytics_stack, "capacity", rows)
    page = _service(analytics_stack).list_current_ap_traffic(
        SITE, cycle_id="capacity", evaluated_at_utc=EVALUATED,
        limit=250, **POLICY,
    )
    assert len(page.items) == 250
    assert page.page.next_cursor is None
    with analytics_stack.observations.read_connection() as connection:
        cycle_plan = connection.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM observation_cycles "
            "WHERE site_id=? AND kind='ap_dynamic' AND state='completed' "
            "AND complete=1 AND result='success' "
            "ORDER BY started_at DESC, cycle_id DESC LIMIT 1",
            (SITE,),
        ).fetchall()
        page_plan = connection.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM ap_observations "
            "WHERE cycle_id=? AND ap_mac>? ORDER BY ap_mac ASC LIMIT ?",
            ("capacity", "00:00:00:00:00:00", 251),
        ).fetchall()
    assert "idx_cycles_site_kind_started" in repr([tuple(row) for row in cycle_plan])
    assert "sqlite_autoindex_ap_observations_1" in repr([tuple(row) for row in page_plan])


def test_models_are_immutable_and_reads_do_not_mutate_storage(analytics_stack):
    _cycle(analytics_stack, "readonly", [
        _row("readonly", "02:AA:BB:CC:DD:18")
    ])
    with sqlite3.connect(analytics_stack.observations.db_path) as connection:
        before_counts = connection.execute(
            "SELECT (SELECT COUNT(*) FROM observation_cycles),"
            " (SELECT COUNT(*) FROM ap_observations)"
        ).fetchone()
        before = (*before_counts, connection.execute(
            "PRAGMA user_version"
        ).fetchone()[0])
    result = _summary(analytics_stack)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.snapshot.cycle_id = "changed"
    with sqlite3.connect(analytics_stack.observations.db_path) as connection:
        after_counts = connection.execute(
            "SELECT (SELECT COUNT(*) FROM observation_cycles),"
            " (SELECT COUNT(*) FROM ap_observations)"
        ).fetchone()
        after = (*after_counts, connection.execute(
            "PRAGMA user_version"
        ).fetchone()[0])
    assert before == after
