from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta, timezone

import pytest

from app.admin_web.home_activity_config import HomeActivitySiteContext
from app.admin_web.home_activity_ranges import (
    HomeActivityRangeError,
    resolve_custom,
    resolve_selected,
    resolve_today,
)
from app.analytics.home_activity import (
    HomeActivityReadService,
    HomeActivitySourceUnavailable,
)
from app.analytics.source_gateway import (
    AnalyticsQueryDeadlineExceeded,
    QueryDeadline,
)

from .conftest import SITE_A


UTC = timezone.utc
EVALUATED = datetime(2026, 1, 1, 11, 0, tzinfo=UTC)


def context(zone="UTC"):
    return HomeActivitySiteContext(
        SITE_A,
        zone,
        "2025-01-01T00:00:00.000Z",
        "2025-01-01T00:00:00.000Z",
    )


@pytest.mark.parametrize(
    ("period", "hours"),
    (("last_24h", 24), ("last_48h", 48), ("last_7d", 168), ("last_30d", 720)),
)
def test_rolling_presets_are_elapsed_windows(period, hours):
    result = resolve_selected(context(), {"period": period}, EVALUATED)
    assert (result.to_utc - result.from_utc).total_seconds() == hours * 3600


def test_today_is_site_local_midnight_not_last_24_hours():
    result = resolve_today(
        context("Asia/Baku"),
        datetime(2026, 8, 25, 7, 19, 55, tzinfo=UTC),
    )
    assert result.from_local.isoformat() == "2026-08-25T00:00:00+04:00"
    assert result.from_utc.isoformat() == "2026-08-24T20:00:00+00:00"


def test_date_only_to_is_inclusive_and_has_no_duration_cap():
    result = resolve_custom(
        context("Asia/Baku"),
        {"from_date": "2025-01-01", "to_date": "2026-01-01"},
        datetime(2026, 1, 3, tzinfo=UTC),
        reject_future=True,
    )
    assert result.to_local_exclusive.isoformat() == "2026-01-02T00:00:00+04:00"
    assert (result.to_utc - result.from_utc).days == 366


@pytest.mark.parametrize(
    ("values", "from_local", "to_local"),
    (
        (
            {"from_date": "2025-12-01", "to_date": "2025-12-01"},
            "2025-12-01T00:00:00+04:00",
            "2025-12-02T00:00:00+04:00",
        ),
        (
            {
                "from_date": "2025-12-01", "from_time": "04:15",
                "to_date": "2025-12-02",
            },
            "2025-12-01T04:15:00+04:00",
            "2025-12-03T00:00:00+04:00",
        ),
        (
            {
                "from_date": "2025-12-01",
                "to_date": "2025-12-02", "to_time": "20:45",
            },
            "2025-12-01T00:00:00+04:00",
            "2025-12-02T20:45:00+04:00",
        ),
        (
            {
                "from_date": "2025-12-01", "from_time": "04:15:30",
                "to_date": "2025-12-02", "to_time": "20:45:30",
            },
            "2025-12-01T04:15:30+04:00",
            "2025-12-02T20:45:30+04:00",
        ),
    ),
)
def test_custom_calendar_boundaries_are_server_resolved(
    values, from_local, to_local
):
    resolved = resolve_custom(
        context("Asia/Baku"), values,
        datetime(2026, 1, 3, tzinfo=UTC), reject_future=True,
    )
    assert resolved.from_local.isoformat() == from_local
    assert resolved.to_local_exclusive.isoformat() == to_local


@pytest.mark.parametrize(
    "values",
    (
        {"from_date": "2026-01-02", "to_date": "2026-01-01"},
        {"from_date": "bad", "to_date": "2026-01-01"},
        {"from_date": "2026-01-01", "to_date": "2026-01-01", "from_time": "24:00"},
        {"from_date": "2026-01-01", "to_date": "2026-01-01", "to_time": "00:00"},
    ),
)
def test_invalid_or_empty_custom_ranges_are_rejected(values):
    with pytest.raises(HomeActivityRangeError):
        resolve_custom(
            context(), values, datetime(2026, 2, 1, tzinfo=UTC),
            reject_future=True,
        )


def test_calendar_presets_follow_site_timezone_and_dst():
    spring = datetime(2026, 3, 9, 16, tzinfo=UTC)
    yesterday = resolve_selected(
        context("America/New_York"), {"period": "yesterday"}, spring
    )
    assert (yesterday.to_utc - yesterday.from_utc).total_seconds() == 23 * 3600
    month = resolve_selected(
        context("America/New_York"), {"period": "current_month"}, spring
    )
    assert month.from_local.day == 1 and month.from_local.hour == 0
    assert resolve_selected(
        context("America/New_York"), {"period": "last_24h"}, spring
    ).from_utc == spring - timedelta(hours=24)


@pytest.mark.parametrize(
    ("from_date", "from_time"),
    (("2026-03-08", "02:30"), ("2026-11-01", "01:30")),
)
def test_explicit_nonexistent_and_ambiguous_new_york_times_are_rejected(
    from_date, from_time
):
    with pytest.raises(HomeActivityRangeError):
        resolve_custom(
            context("America/New_York"),
            {
                "from_date": from_date,
                "from_time": from_time,
                "to_date": "2026-11-02",
            },
            datetime(2026, 12, 1, tzinfo=UTC),
            reject_future=True,
        )


def test_future_apply_rejected_but_preview_allowed():
    values = {"from_date": "2026-01-01", "to_date": "2026-01-02"}
    assert resolve_custom(
        context(), values, EVALUATED, reject_future=False
    ).to_utc > EVALUATED
    with pytest.raises(HomeActivityRangeError):
        resolve_custom(context(), values, EVALUATED, reject_future=True)


def test_authorized_visits_traffic_replay_and_quality(analytics_stack):
    _seed_activity_events(analytics_stack.visits)
    service = HomeActivityReadService(analytics_stack.gateway)
    result = service.get_activity(
        site_id=SITE_A,
        guest_ssids=("ssid-a",),
        range_payload=resolve_selected(
            context(), {"period": "last_24h"}, EVALUATED
        ).public_range(),
        from_utc="2026-01-01T09:00:00.000Z",
        to_utc="2026-01-01T11:00:00.000Z",
        evaluated_at_utc="2026-01-01T11:00:00.000Z",
        timezone_name="UTC",
        visits_coverage_from_utc="2025-01-01T00:00:00.000Z",
        traffic_coverage_from_utc="2025-01-01T00:00:00.000Z",
        traffic_fresh_max_age_seconds=90,
        traffic_stale_max_age_seconds=180,
        deadline=QueryDeadline.after(5),
    )
    assert result.authorized_visits.value == 2
    assert result.authorized_visits.status == "complete"
    assert result.traffic.bytes == 300
    assert result.traffic.eligible_terminal_event_count == 3
    assert result.traffic.included_fingerprint_count == 2
    assert result.traffic.semantic_duplicate_count == 1
    assert result.traffic.unmatched_included_event_count == 1
    assert result.traffic.pending_event_count == 1
    assert result.traffic.invalid_event_count == 2
    assert result.traffic.missing_traffic_count == 1
    assert result.traffic.missing_controller_time_count == 1
    assert result.traffic.other_excluded_event_count == 1
    assert result.traffic.status == "partial"
    assert "pending_offline_events" in result.traffic.coverage.quality_reasons
    assert "semantic_replay_suppressed" in result.traffic.coverage.quality_reasons


def test_activity_read_is_site_and_ssid_scoped_and_read_only(analytics_stack):
    _seed_activity_events(analytics_stack.visits)
    before = _fingerprint(analytics_stack.visits)
    raw = analytics_stack.gateway.home_activity_data(
        site_id=SITE_A,
        guest_ssids=("other-ssid",),
        from_utc="2026-01-01T09:00:00.000Z",
        to_utc="2026-01-01T11:00:00.000Z",
        deadline=QueryDeadline.after(5),
    )
    after = _fingerprint(analytics_stack.visits)
    assert raw["visits"]["verified_visit_count"] == 0
    assert raw["traffic"]["traffic_bytes"] == 0
    assert before == after


def test_zero_keeps_numeric_value_but_coverage_is_independently_partial(
    analytics_stack,
):
    service = HomeActivityReadService(analytics_stack.gateway)
    result = service.get_activity(
        site_id=SITE_A, guest_ssids=("no-such-ssid",),
        range_payload=resolve_selected(
            context(), {"period": "last_24h"}, EVALUATED
        ).public_range(),
        from_utc="2026-01-01T09:00:00.000Z",
        to_utc="2026-01-01T11:00:00.000Z",
        evaluated_at_utc="2026-01-01T11:00:00.000Z",
        timezone_name="UTC",
        visits_coverage_from_utc="2026-01-01T10:00:00.000Z",
        traffic_coverage_from_utc=None,
        traffic_fresh_max_age_seconds=90,
        traffic_stale_max_age_seconds=180,
        deadline=QueryDeadline.after(5),
    )
    assert result.authorized_visits.value == 0
    assert result.authorized_visits.status == "partial"
    assert "requested_before_coverage_start" in result.authorized_visits.coverage.quality_reasons
    assert result.traffic.bytes == 0
    assert result.traffic.status == "partial"
    assert "coverage_start_unknown" in result.traffic.coverage.quality_reasons


@pytest.mark.parametrize(
    ("processing_result", "traffic", "pending", "invalid", "partial"),
    (
        ("closed", 111, 0, 0, False),
        ("unmatched", 111, 0, 0, False),
        ("pending_match", 0, 1, 0, True),
        ("invalid", 0, 0, 1, True),
    ),
)
def test_every_supported_traffic_processing_result_branch(
    analytics_stack, processing_result, traffic, pending, invalid, partial
):
    timestamp = "2026-01-01T10:15:00.000Z"
    _insert_source_event(
        analytics_stack.visits,
        event_id="branch-" + processing_result,
        processing_result=processing_result,
        controller_event_at=timestamp,
        received_at=timestamp,
        traffic=111,
        connected=60,
    )
    raw = analytics_stack.gateway.home_activity_data(
        site_id=SITE_A, guest_ssids=("ssid-a",),
        from_utc="2026-01-01T10:00:00.000Z",
        to_utc="2026-01-01T11:00:00.000Z",
        deadline=QueryDeadline.after(5),
    )
    assert raw["traffic"]["traffic_bytes"] == traffic
    assert raw["traffic"]["pending_event_count"] == pending
    assert raw["traffic"]["invalid_event_count"] == invalid
    service = HomeActivityReadService(analytics_stack.gateway)
    result = service.get_activity(
        site_id=SITE_A, guest_ssids=("ssid-a",),
        range_payload=resolve_selected(
            context(), {"period": "last_24h"}, EVALUATED
        ).public_range(),
        from_utc="2026-01-01T10:00:00.000Z",
        to_utc="2026-01-01T11:00:00.000Z",
        evaluated_at_utc="2026-01-01T11:00:00.000Z", timezone_name="UTC",
        visits_coverage_from_utc="2025-01-01T00:00:00.000Z",
        traffic_coverage_from_utc="2025-01-01T00:00:00.000Z",
        traffic_fresh_max_age_seconds=90,
        traffic_stale_max_age_seconds=180,
        deadline=QueryDeadline.after(5),
    )
    assert (result.traffic.status == "partial") is partial


def test_unknown_processing_result_fails_closed_without_exposing_value():
    class Gateway:
        def home_activity_data(self, **_kwargs):
            return {
                "visits": {
                    "verified_visit_count": 0,
                    "integrity_anomaly_count": 0,
                    "earliest_persisted_evidence_at": None,
                    "latest_persisted_evidence_at": None,
                },
                "traffic": {
                    "traffic_bytes": 999,
                    "eligible_terminal_event_count": 1,
                    "included_fingerprint_count": 1,
                    "unmatched_included_event_count": 0,
                    "pending_event_count": 0,
                    "invalid_event_count": 0,
                    "missing_traffic_count": 0,
                    "missing_controller_time_count": 0,
                    "semantic_duplicate_count": 0,
                    "other_excluded_event_count": 0,
                    "unsupported_result_count": 1,
                    "earliest_persisted_evidence_at": None,
                    "latest_persisted_evidence_at": None,
                },
                "reader_watermark_at": "2026-01-01T11:00:00.000Z",
            }

    with pytest.raises(HomeActivitySourceUnavailable):
        HomeActivityReadService(Gateway()).get_activity(
            site_id=SITE_A, guest_ssids=("ssid-a",), range_payload={},
            from_utc="2026-01-01T10:00:00.000Z",
            to_utc="2026-01-01T11:00:00.000Z",
            evaluated_at_utc="2026-01-01T11:00:00.000Z",
            timezone_name="UTC", visits_coverage_from_utc=None,
            traffic_coverage_from_utc=None,
            traffic_fresh_max_age_seconds=90,
            traffic_stale_max_age_seconds=180,
            deadline=QueryDeadline.after(5),
        )


def test_activity_deadline_is_checked_before_sql(analytics_stack):
    with pytest.raises(AnalyticsQueryDeadlineExceeded):
        analytics_stack.gateway.home_activity_data(
            site_id=SITE_A, guest_ssids=("ssid-a",),
            from_utc="2025-01-01T00:00:00.000Z",
            to_utc="2026-01-01T11:00:00.000Z",
            deadline=QueryDeadline.after(0),
        )


def test_visit_opening_evidence_boundaries_and_scope(analytics_stack):
    gateway = analytics_stack.gateway

    def read(start, end, *, site=SITE_A, ssid="ssid-a"):
        return gateway.home_activity_data(
            site_id=site, guest_ssids=(ssid,), from_utc=start, to_utc=end,
            deadline=QueryDeadline.after(5),
        )["visits"]

    first = read(
        "2026-01-01T09:59:00.000Z", "2026-01-01T10:30:00.000Z"
    )
    assert first["verified_visit_count"] == 1
    assert read(
        "2026-01-01T10:30:00.000Z", "2026-01-01T11:00:00.000Z"
    )["verified_visit_count"] == 1
    assert read(
        "2026-01-01T09:00:00.000Z", "2026-01-01T09:59:00.000Z"
    )["verified_visit_count"] == 0
    assert read(
        "2026-01-01T09:00:00.000Z", "2026-01-01T11:00:00.000Z",
        ssid="SSID-A",
    )["verified_visit_count"] == 0
    assert read(
        "2026-01-01T09:00:00.000Z", "2026-01-01T11:00:00.000Z",
        site="site-b",
    )["verified_visit_count"] == 0


def test_extra_nonopening_authorization_does_not_duplicate_visit(
    analytics_stack,
):
    with closing(analytics_stack.visits._connect()) as connection:  # noqa: SLF001
        connection.execute(
            """
            INSERT INTO visit_authorizations (
              visit_id,auth_session_id,auth_run_number,
              authorization_attempt,authorized_at,final_reason,client_ip,
              portal_ssid,portal_ap_mac,portal_radio_id,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                analytics_stack.visit_id,
                "55555555-5555-4555-8555-555555555555", 2, 2,
                "2026-01-01T10:00:00.000Z", "AUTHORIZED", None,
                "ssid-a", None, None, "2026-01-01T10:00:00.000Z",
            ),
        )
        connection.commit()
    raw = analytics_stack.gateway.home_activity_data(
        site_id=SITE_A, guest_ssids=("ssid-a",),
        from_utc="2026-01-01T09:00:00.000Z",
        to_utc="2026-01-01T11:00:00.000Z",
        deadline=QueryDeadline.after(5),
    )["visits"]
    assert raw["verified_visit_count"] == 2
    assert raw["integrity_anomaly_count"] == 0


def test_missing_opening_authorization_is_integrity_anomaly(analytics_stack):
    with closing(analytics_stack.visits._connect()) as connection:  # noqa: SLF001
        connection.execute(
            "DELETE FROM visit_authorizations WHERE visit_id=?",
            (analytics_stack.visit_id,),
        )
        connection.commit()
    raw = analytics_stack.gateway.home_activity_data(
        site_id=SITE_A, guest_ssids=("ssid-a",),
        from_utc="2026-01-01T09:00:00.000Z",
        to_utc="2026-01-01T11:00:00.000Z",
        deadline=QueryDeadline.after(5),
    )["visits"]
    assert raw["verified_visit_count"] == 1
    assert raw["integrity_anomaly_count"] == 1


def test_traffic_zero_received_only_and_distinct_fingerprints(analytics_stack):
    _insert_source_event(
        analytics_stack.visits, event_id="zero", processing_result="closed",
        controller_event_at="2026-01-01T10:01:00.000Z",
        received_at="2026-01-01T10:01:01.000Z", traffic=0, connected=0,
    )
    _insert_source_event(
        analytics_stack.visits, event_id="same-mac-next-instant",
        processing_result="closed",
        controller_event_at="2026-01-01T10:01:00.001Z",
        received_at="2026-01-01T10:01:02.000Z", traffic=50, connected=0,
    )
    _insert_source_event(
        analytics_stack.visits, event_id="received-only",
        processing_result="closed", controller_event_at=None,
        received_at="2026-01-01T10:02:00.000Z", traffic=900, connected=1,
    )
    raw = analytics_stack.gateway.home_activity_data(
        site_id=SITE_A, guest_ssids=("ssid-a",),
        from_utc="2026-01-01T10:00:00.000Z",
        to_utc="2026-01-01T11:00:00.000Z",
        deadline=QueryDeadline.after(5),
    )["traffic"]
    assert raw["traffic_bytes"] == 50
    assert raw["included_fingerprint_count"] == 2
    assert raw["missing_controller_time_count"] == 1


def test_duplicate_event_id_is_rejected_by_source_schema(analytics_stack):
    import sqlite3

    _insert_source_event(
        analytics_stack.visits, event_id="event-id-once",
        processing_result="closed",
        controller_event_at="2026-01-01T10:05:00.000Z",
        received_at="2026-01-01T10:05:01.000Z", traffic=1, connected=1,
    )
    with pytest.raises(sqlite3.IntegrityError):
        _insert_source_event(
            analytics_stack.visits, event_id="event-id-once",
            processing_result="closed",
            controller_event_at="2026-01-01T10:05:00.000Z",
            received_at="2026-01-01T10:05:02.000Z", traffic=1, connected=1,
        )


def test_activity_explain_uses_site_time_indexes(analytics_stack):
    plans = analytics_stack.gateway.explain_home_activity(
        site_id=SITE_A,
        guest_ssids=("ssid-a",),
        from_utc="2026-01-01T09:00:00.000Z",
        to_utc="2026-01-01T11:00:00.000Z",
        deadline=QueryDeadline.after(5),
    )
    joined = " ".join(plans["authorized_visits"] + plans["traffic"])
    assert "idx_visits_site_start_ssid" in joined
    assert "idx_visit_auth_visit_time" in joined
    assert "idx_visit_events_site_controller" in joined


def _seed_activity_events(repository):
    rows = [
        ("closed-a", "closed", "2026-01-01T10:00:00.000Z", "2026-01-01T10:00:01.000Z", 60, 100, "02:11:22:33:44:55"),
        ("closed-replay", "closed", "2026-01-01T10:00:00.000Z", "2026-01-01T10:00:02.000Z", 60, 100, "02:11:22:33:44:55"),
        ("unmatched-a", "unmatched", "2026-01-01T10:10:00.000Z", "2026-01-01T10:10:01.000Z", 90, 200, "02:11:22:33:44:66"),
        ("pending-a", "pending_match", "2026-01-01T10:20:00.000Z", "2026-01-01T10:20:01.000Z", 1, 9, "02:11:22:33:44:77"),
        ("invalid-a", "invalid", "2026-01-01T10:25:00.000Z", "2026-01-01T10:25:01.000Z", None, None, None),
        ("missing-traffic", "closed", "2026-01-01T10:30:00.000Z", "2026-01-01T10:30:01.000Z", 1, None, "02:11:22:33:44:88"),
        ("missing-time", "invalid", None, "2026-01-01T10:35:00.000Z", None, None, None),
        ("missing-fingerprint", "closed", "2026-01-01T10:40:00.000Z", "2026-01-01T10:40:01.000Z", None, 10, "02:11:22:33:44:99"),
    ]
    with closing(repository._connect()) as connection:  # noqa: SLF001
        for offset, row in enumerate(rows):
            event_id, result, controller, received, connected, traffic, mac = row
            connection.execute(
                """
                INSERT INTO visit_source_events (
                    event_id,event_type,site_id,client_mac,controller_event_at,
                    received_at,source_identity,source_offset_start,
                    source_offset_end,processing_result,visit_id,reason,
                    first_processed_at,processed_at,pending_until,
                    last_match_attempt_at,client_ip,ssid,ap_mac,
                    reported_connected_seconds,reported_traffic_total_bytes
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    event_id, "omada.client_offline", SITE_A, mac, controller,
                    received, "fixture", offset, offset + 1, result, None,
                    None, received, received,
                    received if result == "pending_match" else None,
                    None, None, "ssid-a", None, connected, traffic,
                ),
            )
        connection.execute(
            """
            INSERT INTO visit_reader_state (
                source_identity,source_path,source_offset,last_observed_size,
                checkpoint_offset,checkpoint_length,checkpoint_sha256,
                retired_completed,missing_warning_emitted,updated_at
            ) VALUES ('activity-reader','/fixture',1,1,NULL,NULL,NULL,0,0,?)
            """,
            ("2026-01-01T11:00:00.000Z",),
        )
        connection.commit()


def _insert_source_event(
    repository,
    *,
    event_id,
    processing_result,
    controller_event_at,
    received_at,
    traffic,
    connected,
    site_id=SITE_A,
    ssid="ssid-a",
    mac="02:11:22:33:44:AA",
):
    with closing(repository._connect()) as connection:  # noqa: SLF001
        connection.execute(
            """
            INSERT INTO visit_source_events (
              event_id,event_type,site_id,client_mac,controller_event_at,
              received_at,source_identity,source_offset_start,source_offset_end,
              processing_result,visit_id,reason,first_processed_at,processed_at,
              pending_until,last_match_attempt_at,client_ip,ssid,ap_mac,
              reported_connected_seconds,reported_traffic_total_bytes
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                event_id, "omada.client_offline", site_id, mac,
                controller_event_at, received_at, "branch-fixture", 100, 101,
                processing_result, None, None, received_at, received_at,
                received_at if processing_result == "pending_match" else None,
                None, None, ssid, None, connected, traffic,
            ),
        )
        connection.execute(
            """
            INSERT OR REPLACE INTO visit_reader_state (
              source_identity,source_path,source_offset,last_observed_size,
              checkpoint_offset,checkpoint_length,checkpoint_sha256,
              retired_completed,missing_warning_emitted,updated_at
            ) VALUES ('branch-reader','/fixture',1,1,NULL,NULL,NULL,0,0,?)
            """,
            ("2026-01-01T11:00:00.000Z",),
        )
        connection.commit()


def _fingerprint(repository):
    with closing(repository._connect(readonly=True)) as connection:  # noqa: SLF001
        return (
            int(connection.execute("PRAGMA user_version").fetchone()[0]),
            int(connection.execute("SELECT COUNT(*) FROM visits").fetchone()[0]),
            int(connection.execute("SELECT COUNT(*) FROM visit_authorizations").fetchone()[0]),
            int(connection.execute("SELECT COUNT(*) FROM visit_source_events").fetchone()[0]),
        )
