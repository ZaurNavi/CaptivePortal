from __future__ import annotations

from contextlib import closing

import pytest

from app.analytics.validation import AnalyticsQueryValidationError
from app.visit_lifecycle.models import NormalizedVisitStart

from .conftest import CLIENT_A, DEVICE_A, SITE_A, SITE_B, SNAPSHOT_A


FROM = "2026-01-01T09:00:00.000Z"
TO = "2026-01-01T11:00:00.000Z"
EVALUATION = "2026-01-01T11:00:00.000Z"


def test_cycle_quality_has_explicit_states_and_ratio(analytics_stack):
    result = analytics_stack.service.get_observation_cycle_quality(
        SITE_A, "client", FROM, TO
    )
    assert result.status == "ok"
    assert result.value.completed == 3
    assert result.value.completed_complete == 2
    assert result.value.completed_incomplete == 1
    assert result.value.success == 2
    assert result.value.partial == 1
    assert result.value.complete_ratio == pytest.approx(2 / 3)
    assert result.value.latest_accepted_at == "2026-01-01T10:03:30.000Z"


def test_half_open_boundary_excludes_exact_to_cycle(analytics_stack):
    result = analytics_stack.service.get_observation_cycle_quality(
        SITE_A, "client", "2026-01-01T10:59:59.000Z", TO
    )
    assert result.status == "insufficient_data"
    assert result.value.completed == 0


def test_strict_field_completeness_excludes_partial_and_exact_to(
    analytics_stack,
):
    result = analytics_stack.service.get_field_completeness(
        SITE_A,
        "client",
        FROM,
        TO,
        ("ap_mac", "rssi", "traffic_down"),
    )
    assert result.status == "ok"
    assert {item.field: item.row_count for item in result.value} == {
        "ap_mac": 2,
        "rssi": 2,
        "traffic_down": 2,
    }
    assert all(item.missing_count == 0 for item in result.value)
    assert result.provenance.source_rows_rejected == 1


def test_diagnostic_field_completeness_is_explicit_partial(analytics_stack):
    result = analytics_stack.service.get_field_completeness(
        SITE_A,
        "client",
        FROM,
        TO,
        ("ap_mac",),
        quality_mode="diagnostic_including_partial",
    )
    assert result.status == "partial"
    assert result.value[0].row_count == 3
    assert result.value[0].missing_count == 1
    assert result.quality.reason == "diagnostic_partial_rows"


def test_ap_and_radio_missing_fields_use_fixed_allowlist(analytics_stack):
    ap = analytics_stack.service.get_field_completeness(
        SITE_A, "ap", FROM, TO, ("cpu_util", "mem_util")
    )
    assert [(item.field, item.missing_count) for item in ap.value] == [
        ("cpu_util", 0),
        ("mem_util", 1),
    ]
    radio = analytics_stack.service.get_field_completeness(
        SITE_A, "radio", FROM, TO, ("busy_util", "tx_retry_packets")
    )
    assert all(item.row_count == 1 for item in radio.value)


def test_unknown_completeness_field_is_rejected(analytics_stack):
    with pytest.raises(AnalyticsQueryValidationError):
        analytics_stack.service.get_field_completeness(
            SITE_A, "client", FROM, TO, ("hostname",)
        )


def test_visit_quality_is_batched_and_paginated(analytics_stack):
    first = analytics_stack.service.list_visit_quality(
        SITE_A, FROM, TO, limit=1
    )
    assert first.status == "ok"
    assert len(first.value.items) == 1
    assert first.value.items[0].status == "open"
    assert first.value.items[0].authorization_count == 1
    assert first.value.next_cursor is not None

    second = analytics_stack.service.list_visit_quality(
        SITE_A, FROM, TO, limit=1, cursor=first.value.next_cursor
    )
    assert len(second.value.items) == 1
    assert second.value.items[0].status == "closed"
    assert second.value.items[0].snapshot_resolved is True
    assert second.value.next_cursor is None


def test_visit_quality_returns_registry_watermark_when_rows_are_read(
    analytics_stack,
):
    result = analytics_stack.service.list_visit_quality(
        SITE_A, FROM, TO, limit=2
    )
    assert result.provenance.source_watermarks["registry"] == (
        "2026-01-01T10:00:01.000Z"
    )


def test_visit_page_rejects_malformed_cursor_and_limit(analytics_stack):
    with pytest.raises(AnalyticsQueryValidationError):
        analytics_stack.service.list_visit_quality(
            SITE_A, FROM, TO, cursor="not-base64"
        )
    with pytest.raises(AnalyticsQueryValidationError):
        analytics_stack.service.list_visit_quality(
            SITE_A, FROM, TO, limit=2001
        )


def test_closed_visit_observation_coverage(analytics_stack):
    result = analytics_stack.service.get_visit_context(
        SITE_A, analytics_stack.visit_id
    )
    assert result.status == "ok"
    coverage = result.value.observation_coverage
    assert coverage.sample_count == 2
    assert coverage.interval_count == 1
    assert coverage.first_observed_at == "2026-01-01T10:00:00.000Z"
    assert coverage.last_observed_at == "2026-01-01T10:03:30.000Z"
    assert coverage.edge_gap_start_seconds == 60
    assert coverage.edge_gap_end_seconds == 30
    assert coverage.max_inter_sample_gap_seconds == pytest.approx(210)
    assert coverage.gap_count_over_threshold == 1
    assert coverage.observed_span_seconds == 210
    assert coverage.observed_span_ratio == pytest.approx(0.7)
    assert coverage.provisional is False


def test_open_visit_uses_provisional_evaluation_window(analytics_stack):
    result = analytics_stack.service.get_visit_context(
        SITE_A,
        analytics_stack.open_visit_id,
        evaluation_to_utc=EVALUATION,
    )
    assert result.status == "insufficient_data"
    assert result.value.observation_coverage.sample_count == 0
    assert result.value.observation_coverage.interval_count == 0
    assert result.value.observation_coverage.observed_span_ratio is None
    assert result.value.observation_coverage.provisional is True


def test_open_visit_context_rejects_window_over_configured_max(
    analytics_stack,
):
    with pytest.raises(
        AnalyticsQueryValidationError,
        match="Visit observation window exceeds hard limit",
    ):
        analytics_stack.service.get_visit_context(
            SITE_A,
            analytics_stack.open_visit_id,
            evaluation_to_utc="2026-02-02T10:30:00.000Z",
        )


def test_closed_visit_context_rejects_window_over_configured_max(
    analytics_stack,
):
    with closing(analytics_stack.visits._connect()) as connection:  # noqa: SLF001
        connection.execute(
            """
            UPDATE visits SET
                status='closed', closed_at='2026-02-02T10:30:00.000Z',
                close_reason='client_offline',
                close_time_source='controller_timestamp',
                duration_seconds=?, updated_at='2026-02-02T10:30:00.000Z'
            WHERE visit_id=?
            """,
            (32 * 24 * 60 * 60, analytics_stack.open_visit_id),
        )
        connection.commit()
    with pytest.raises(
        AnalyticsQueryValidationError,
        match="Visit observation window exceeds hard limit",
    ):
        analytics_stack.service.get_visit_context(
            SITE_A, analytics_stack.open_visit_id
        )


def test_closed_zero_duration_visit_has_null_span_ratio(analytics_stack):
    with closing(analytics_stack.visits._connect()) as connection:  # noqa: SLF001
        connection.execute(
            """
            UPDATE visits
            SET closed_at=started_at, duration_seconds=0
            WHERE visit_id=?
            """,
            (analytics_stack.visit_id,),
        )
        connection.commit()
    result = analytics_stack.service.get_visit_context(
        SITE_A, analytics_stack.visit_id
    )
    assert result.status == "insufficient_data"
    assert result.value.observation_coverage.sample_count == 0
    assert result.value.observation_coverage.observed_span_ratio is None


def test_zero_is_present_but_null_is_missing(analytics_stack):
    with closing(analytics_stack.observations._connect()) as connection:  # noqa: SLF001
        connection.execute(
            """
            UPDATE client_observations
            SET traffic_down=0, traffic_up=NULL
            WHERE site_id=? AND observed_at='2026-01-01T10:00:00.000Z'
            """,
            (SITE_A,),
        )
        connection.commit()
    result = analytics_stack.service.get_field_completeness(
        SITE_A, "client", FROM, TO, ("traffic_down", "traffic_up")
    )
    by_field = {item.field: item for item in result.value}
    assert by_field["traffic_down"].non_null_count == 2
    assert by_field["traffic_down"].missing_count == 0
    assert by_field["traffic_up"].non_null_count == 1
    assert by_field["traffic_up"].missing_count == 1


def test_registry_global_last_context_does_not_leak_across_sites(
    analytics_stack,
):
    with closing(analytics_stack.registry._connect()) as connection:  # noqa: SLF001
        connection.execute(
            """
            UPDATE visitor_devices SET
                last_site_id='site-b',
                last_ip='198.51.100.9',
                last_ssid='other',
                last_ap_name='OTHER',
                last_ap_mac='02:00:00:00:00:99',
                last_rssi=-10,
                last_snr=99
            """
        )
        connection.commit()
    result = analytics_stack.service.get_visit_context(
        SITE_A, analytics_stack.visit_id
    )
    device = result.value.device
    assert device.site_context_available is False
    assert device.last_ip is None
    assert device.last_ssid is None
    assert device.last_ap_name is None
    assert device.last_ap_mac is None
    assert device.last_rssi is None
    assert device.last_snr is None


def test_safe_snapshot_contract_omits_raw_json(analytics_stack):
    result = analytics_stack.service.get_visit_context(
        SITE_A, analytics_stack.visit_id
    )
    snapshot = result.value.snapshot
    assert snapshot.site_id == SITE_A
    assert not hasattr(snapshot, "raw_controller_snapshot_json")
    assert not hasattr(snapshot, "client_json")
    assert not hasattr(snapshot, "auth_context_json")


def test_source_quality_fixes_evaluation_and_watermarks(analytics_stack):
    result = analytics_stack.service.get_source_quality(
        SITE_A, FROM, TO, EVALUATION
    )
    assert result.status == "ok"
    value = result.value
    assert value.device_link_coverage.ratio == 0.5
    assert value.initial_snapshot_link_coverage.ratio == 0.5
    assert value.resolved_snapshot_coverage.ratio == 1.0
    assert value.authorization_attachment_coverage.ratio == 1.0
    assert value.closed_visit_coverage.ratio == 0.5
    assert value.open_visit_count == 1
    assert result.provenance.evaluation_at_utc == EVALUATION
    assert set(result.provenance.source_watermarks) == {
        "observations", "visits", "registry",
    }
    assert result.provenance.source_watermarks["observations"] == (
        "2026-01-01T10:03:30.000Z"
    )
    assert value.freshness["observations"].freshness_seconds == 3390
    assert value.freshness["visits"].freshness_seconds == 1800
    assert value.freshness["registry"].freshness_seconds == 3599
    assert all(item.status == "ok" for item in value.freshness.values())


def test_source_freshness_without_accepted_timestamp_is_insufficient(
    analytics_stack,
):
    result = analytics_stack.service.get_source_quality(
        SITE_B, FROM, TO, EVALUATION
    )
    assert result.value.freshness["observations"].status == "ok"
    assert result.value.freshness["visits"].status == "insufficient_data"
    assert result.value.freshness["registry"].status == "insufficient_data"
    assert result.value.freshness["visits"].latest_timestamp is None
    assert result.value.freshness["visits"].freshness_seconds is None


def test_source_event_quality_groups_result_and_reason_by_site(
    analytics_stack,
):
    with closing(analytics_stack.visits._connect()) as connection:  # noqa: SLF001
        connection.executemany(
            """
            INSERT INTO visit_source_events (
                event_id, event_type, site_id, source_identity,
                source_offset_start, source_offset_end,
                processing_result, reason, first_processed_at, processed_at
            ) VALUES (?, 'omada.client_offline', ?, ?, ?, ?, 'invalid', ?, ?, ?)
            """,
            (
                (
                    "quality-event-a", SITE_A, "quality-source-a", 0, 1,
                    "invalid_mac", "2026-01-01T10:10:00.000Z",
                    "2026-01-01T10:10:00.000Z",
                ),
                (
                    "quality-event-b", SITE_A, "quality-source-b", 0, 1,
                    "invalid_time", "2026-01-01T10:11:00.000Z",
                    "2026-01-01T10:11:00.000Z",
                ),
                (
                    "quality-event-null-site", None, "quality-source-c", 0, 1,
                    "must_not_leak", "2026-01-01T10:12:00.000Z",
                    "2026-01-01T10:12:00.000Z",
                ),
            ),
        )
        connection.commit()
    result = analytics_stack.service.get_source_quality(
        SITE_A, FROM, TO, EVALUATION
    )
    assert result.value.source_event_quality["by_processing_result"] == {
        "invalid": 2,
    }
    assert result.value.source_event_quality["by_reason"] == {
        "invalid_mac": 1,
        "invalid_time": 1,
    }


def test_resolved_snapshot_coverage_counts_repeated_visit_links(
    analytics_stack,
):
    outcome = analytics_stack.visits.create_or_reuse_start(
        NormalizedVisitStart(
            auth_session_id="55555555-5555-4555-8555-555555555555",
            site_id=SITE_A,
            client_mac=CLIENT_A,
            authorized_at="2026-01-01T10:20:00.000Z",
            auth_run_number=1,
            authorization_attempt=1,
            final_reason="AUTHORIZED",
            client_ip=None,
            portal_ssid="ssid-a",
            portal_ap_mac=None,
            portal_radio_id=None,
        ),
        now_utc="2026-01-01T10:20:00.000Z",
    )
    with closing(analytics_stack.visits._connect()) as connection:  # noqa: SLF001
        connection.execute(
            """
            UPDATE visits SET
                device_id=?, initial_snapshot_id=?, status='closed',
                closed_at='2026-01-01T10:21:00.000Z',
                close_reason='client_offline',
                close_time_source='controller_timestamp',
                duration_seconds=60,
                updated_at='2026-01-01T10:21:00.000Z'
            WHERE visit_id=?
            """,
            (DEVICE_A, SNAPSHOT_A, outcome.visit_id),
        )
        connection.commit()
    result = analytics_stack.service.get_source_quality(
        SITE_A, FROM, TO, EVALUATION
    )
    assert result.value.initial_snapshot_link_coverage.numerator == 2
    assert result.value.resolved_snapshot_coverage.numerator == 2
    assert result.value.resolved_snapshot_coverage.denominator == 2
    assert result.value.resolved_snapshot_coverage.ratio == 1.0


def test_site_isolation_is_mandatory(analytics_stack):
    result = analytics_stack.service.get_source_quality(
        SITE_B, FROM, TO, EVALUATION
    )
    assert result.status == "insufficient_data"
    assert result.value.device_link_coverage.denominator == 0
    assert result.value.cycle_quality["client"].completed == 1
    assert result.value.cycle_quality["client"].success == 1


def test_window_is_strict_utc_half_open_and_max_31_days(analytics_stack):
    service = analytics_stack.service
    with pytest.raises(AnalyticsQueryValidationError):
        service.get_source_quality(
            SITE_A,
            "2026-01-01T00:00:00Z",
            "2026-01-02T00:00:00.000Z",
            EVALUATION,
        )
    with pytest.raises(AnalyticsQueryValidationError):
        service.get_source_quality(
            SITE_A,
            "2026-01-01T00:00:00.000Z",
            "2026-02-01T00:00:00.001Z",
            EVALUATION,
        )
    accepted = service.get_source_quality(
        SITE_A,
        "2026-01-01T00:00:00.000Z",
        "2026-02-01T00:00:00.000Z",
        "2026-02-01T00:00:00.000Z",
    )
    assert accepted.status in {"ok", "insufficient_data"}
