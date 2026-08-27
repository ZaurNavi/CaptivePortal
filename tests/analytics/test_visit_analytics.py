from __future__ import annotations

import uuid
from contextlib import closing
from datetime import datetime, timezone

import pytest

from app.analytics.config import AnalyticsConfig
from app.analytics.config import (
    AnalyticsConfigError, analytics_config_from_settings,
)
from app.analytics.source_gateway import (
    AnalyticsSourceUnavailable,
    QueryDeadline,
)
from app.analytics.validation import AnalyticsQueryValidationError
from app.analytics.visits import VisitAnalyticsService

from .conftest import CLIENT_A, DEVICE_A, SITE_A, SITE_B


UTC = timezone.utc
FROM = "2026-01-01T09:59:00.000Z"
TO = "2026-01-01T11:00:00.000Z"


def _service(stack, *, minimum=1, clock=None, monotonic=None):
    return VisitAnalyticsService(
        AnalyticsConfig(
            enabled=True, visit_enabled=True,
            visit_min_cohort_size=minimum,
            max_query_window_days=31, visit_max_window_days=90,
            wireless_min_samples=1,
        ),
        stack.gateway,
        clock=clock or (lambda: datetime(2026, 1, 1, 11, tzinfo=UTC)),
        **({} if monotonic is None else {"monotonic": monotonic}),
    )


def test_optional_admin_deadline_can_only_shorten_visit_counts(
    analytics_stack, monkeypatch,
):
    now = lambda: 100.0
    captured = []
    original = analytics_stack.gateway.visit_cohort_summary

    def visit_cohort_summary(**kwargs):
        captured.append(kwargs["deadline"])
        return original(**kwargs)

    monkeypatch.setattr(
        analytics_stack.gateway, "visit_cohort_summary", visit_cohort_summary
    )
    service = _service(analytics_stack, monotonic=now)
    service.get_visit_counts(SITE_A, FROM, TO)
    assert captured[-1].expires_at == 110.0
    service.get_visit_counts(
        SITE_A, FROM, TO, deadline=QueryDeadline(102.0, now)
    )
    assert captured[-1].expires_at == 102.0
    service.get_visit_counts(
        SITE_A, FROM, TO, deadline=QueryDeadline(200.0, now)
    )
    assert captured[-1].expires_at == 110.0


def test_expired_external_deadline_uses_existing_unavailable_semantics(
    analytics_stack,
):
    now = lambda: 100.0
    result = _service(analytics_stack, monotonic=now).get_visit_counts(
        SITE_A, FROM, TO, deadline=QueryDeadline(99.0, now)
    )
    assert result.status == "unavailable"
    assert result.quality.reason == "query_deadline"


def test_device_counts_forwards_effective_external_deadline(
    analytics_stack, monkeypatch,
):
    now = lambda: 100.0
    captured = []
    original = analytics_stack.gateway.visit_device_summary

    def visit_device_summary(**kwargs):
        captured.append(kwargs["deadline"])
        return original(**kwargs)

    monkeypatch.setattr(
        analytics_stack.gateway, "visit_device_summary", visit_device_summary
    )
    result = _service(analytics_stack, monotonic=now).get_device_counts(
        SITE_A, FROM, TO, deadline=QueryDeadline(101.0, now)
    )
    assert result.status == "ok"
    assert captured[0].expires_at == 101.0


def _insert_open(stack, *, site=SITE_A, device=DEVICE_A,
                 started="2026-01-01T10:40:00.000Z", ssid="ssid-b",
                 ap="02:AA:BB:CC:DD:EF"):
    visit_id = str(uuid.uuid4())
    auth_id = str(uuid.uuid4())
    with closing(stack.visits._connect()) as connection:  # noqa: SLF001
        connection.execute("""
          INSERT INTO visits (
            visit_id,site_id,client_mac,device_id,initial_snapshot_id,
            start_auth_session_id,start_auth_run_number,start_final_reason,
            started_at,status,start_ssid,start_ap_mac,created_at,updated_at
          ) VALUES (?,?,?,?,NULL,?,1,'AUTHORIZED',?,'open',?,?,?,?)
        """, (visit_id, site, CLIENT_A, device, auth_id, started,
                ssid, ap, started, started))
        connection.commit()
    return visit_id


def _insert_closed(
    stack, *, started: str, closed: str, client: str = CLIENT_A,
    site: str = SITE_A,
):
    visit_id = str(uuid.uuid4())
    auth_id = str(uuid.uuid4())
    with closing(stack.visits._connect()) as connection:  # noqa: SLF001
        connection.execute("""
          INSERT INTO visits (
            visit_id,site_id,client_mac,device_id,initial_snapshot_id,
            start_auth_session_id,start_auth_run_number,start_final_reason,
            started_at,closed_at,status,close_reason,close_time_source,
            duration_seconds,created_at,updated_at
          ) VALUES (?,?,?,NULL,NULL,?,1,'AUTHORIZED',?,?,'closed',
                    'offline','controller',60,?,?)
        """, (visit_id, site, client, auth_id, started, closed,
                started, closed))
        connection.commit()
    return visit_id


def _insert_client_observation(
    stack, *, cycle: str, timestamp: str, client: str,
    down: int | None, up: int | None,
):
    stack.observations.create_cycle(
        kind="client", site_id=SITE_A, started_at=timestamp,
        cycle_id=cycle)
    stack.observations.insert_client_batch([{
        "cycle_id": cycle, "observed_at": timestamp,
        "site_id": SITE_A, "client_mac": client,
        "source_inventory_complete": True,
        "traffic_down": down, "traffic_up": up,
    }])
    stack.observations.finalize_cycle(
        cycle, finished_at=timestamp, complete=True, result="success",
        source_rows_reported=1, items_seen=1, items_stored=1)


def test_start_cohort_counts_boundaries_and_site_isolation(analytics_stack):
    _insert_open(analytics_stack, site=SITE_B)
    result = _service(analytics_stack).get_visit_counts(SITE_A, FROM, TO)
    assert result.status == "ok"
    assert result.value.total_visit_count == 2
    assert result.value.open_visit_count == 1
    assert result.value.closed_visit_count == 1
    assert result.provenance.filters["population_semantics"].startswith(
        "visit_start_cohort")


def test_device_repeat_and_new_to_site_use_same_site_visit_history(
    analytics_stack,
):
    _insert_open(analytics_stack, device=DEVICE_A)
    _insert_open(analytics_stack, site=SITE_B, device=DEVICE_A)
    service = _service(analytics_stack)
    devices = service.get_device_counts(SITE_A, FROM, TO)
    repeat = service.get_repeat_devices(SITE_A, FROM, TO)
    new = service.get_new_to_site_devices(SITE_A, FROM, TO)
    assert devices.value.unique_linked_devices == 1
    assert devices.value.unlinked_visit_count == 1
    assert repeat.value.repeat_device_count == 1
    assert repeat.value.repeat_device_ratio == 1
    assert new.value.new_to_site_device_count == 1
    assert new.value.known_before_window_device_count == 0


def test_duration_and_authorization_do_not_invent_open_duration(
    analytics_stack,
):
    service = _service(analytics_stack)
    duration = service.get_duration_distribution(SITE_A, FROM, TO)
    auth = service.get_authorization_distribution(SITE_A, FROM, TO)
    assert duration.value.distribution.sample_count == 1
    assert duration.value.distribution.p50 == 300
    assert duration.value.excluded_open_count == 1
    assert auth.value.distribution.sample_count == 2
    assert auth.value.visits_with_exactly_one_authorization == 2
    assert auth.value.visits_with_zero_authorization == 0


def test_contexts_are_separate_and_touched_is_nonexclusive(analytics_stack):
    result = _service(analytics_stack).get_context_distributions(
        SITE_A, FROM, TO)
    assert result.value.start_ssid.dimension == "start_ssid"
    assert result.value.final_ssid.null_context_count == 2
    assert result.value.touched_ssid.grouping_is_non_exclusive is True
    assert result.value.touched_ap_mac.grouping_is_non_exclusive is True


def test_transitions_do_not_label_ap_change_as_fault(analytics_stack):
    result = _service(analytics_stack).get_context_transition(
        SITE_A, FROM, TO)
    ap = next(item for item in result.value if item.context == "ap_mac")
    assert "not a fault" in ap.interpretation
    assert ap.missing_side_count == 2


def test_observation_coverage_is_set_based_and_exact_formula(analytics_stack):
    result = _service(analytics_stack).get_observation_coverage_summary(
        SITE_A, FROM, TO)
    assert result.value.visit_count == 2
    assert result.value.visits_with_one_or_more_client_observations == 1
    assert result.value.visits_with_zero_client_observations == 1
    assert result.value.sample_count_distribution.sample_count == 2
    assert result.provenance.source_names == ("visits", "observations")


def test_traffic_sources_remain_separate_and_null_stays_null(analytics_stack):
    result = _service(analytics_stack).get_visit_traffic_summary(
        SITE_A, FROM, TO)
    assert result.value.reported_total_bytes is None
    assert result.value.reported_up_bytes is None
    assert result.value.observed_counter_delta_down_bytes is None
    assert result.value.observed_delta_coverage.denominator == 2


def test_traffic_uses_accepted_counter_deltas_and_keeps_reported_directions_null(
    analytics_stack,
):
    timestamp = "2026-01-01T10:02:00.000Z"
    analytics_stack.observations.create_cycle(
        kind="client", site_id=SITE_A, started_at=timestamp,
        cycle_id="visit-traffic-cycle")
    analytics_stack.observations.insert_client_batch([{
        "cycle_id": "visit-traffic-cycle", "observed_at": timestamp,
        "site_id": SITE_A, "client_mac": CLIENT_A,
        "source_inventory_complete": True,
        "traffic_down": 160, "traffic_up": 80,
    }])
    analytics_stack.observations.finalize_cycle(
        "visit-traffic-cycle", finished_at=timestamp, complete=True,
        result="success", source_rows_reported=1, items_seen=1,
        items_stored=1)
    with closing(analytics_stack.visits._connect()) as connection:  # noqa: SLF001
        connection.execute(
            "UPDATE visits SET reported_traffic_total_bytes=1000 "
            "WHERE visit_id=?", (analytics_stack.visit_id,))
        connection.commit()
    result = _service(analytics_stack).get_visit_traffic_summary(
        SITE_A, FROM, TO)
    assert result.value.reported_total_bytes == 1000
    assert result.value.reported_up_bytes is None
    assert result.value.reported_down_bytes is None
    assert result.value.observed_counter_delta_down_bytes == 60
    assert result.value.observed_counter_delta_up_bytes == 30
    assert result.value.reconciliation_difference_bytes == -910
    assert result.value.reconciliation_ratio == pytest.approx(-0.91)


def test_same_timestamp_counter_growth_is_not_a_valid_visit_interval(
    analytics_stack,
):
    client = "02:11:22:33:44:77"
    _insert_closed(
        analytics_stack, started="2026-01-01T10:40:00.000Z",
        closed="2026-01-01T10:45:00.000Z", client=client)
    for cycle, down, up in (
        ("same-time-a", 100, 50), ("same-time-b", 200, 100)):
        _insert_client_observation(
            analytics_stack, cycle=cycle,
            timestamp="2026-01-01T10:41:00.000Z", client=client,
            down=down, up=up)
    result = _service(analytics_stack).get_visit_traffic_summary(
        SITE_A, "2026-01-01T10:40:00.000Z",
        "2026-01-01T10:41:00.000Z")
    assert result.value.observed_delta_coverage.numerator == 0
    assert result.value.observed_delta_coverage.denominator == 1
    assert result.value.observed_counter_delta_down_bytes is None
    assert result.value.observed_counter_delta_up_bytes is None
    assert result.provenance.source_rows_examined == 1
    assert result.provenance.source_rows_accepted == 0


def test_visit_traffic_accepts_exact_max_gap_and_keeps_directions_independent(
    analytics_stack,
):
    client = "02:11:22:33:44:88"
    _insert_closed(
        analytics_stack, started="2026-01-01T10:40:00.000Z",
        closed="2026-01-01T10:50:00.000Z", client=client)
    _insert_client_observation(
        analytics_stack, cycle="gap-base",
        timestamp="2026-01-01T10:41:00.000Z", client=client,
        down=100, up=100)
    _insert_client_observation(
        analytics_stack, cycle="gap-exact",
        timestamp="2026-01-01T10:44:00.000Z", client=client,
        down=150, up=None)
    _insert_client_observation(
        analytics_stack, cycle="gap-reset",
        timestamp="2026-01-01T10:45:00.000Z", client=client,
        down=140, up=200)
    result = _service(analytics_stack).get_visit_traffic_summary(
        SITE_A, "2026-01-01T10:40:00.000Z",
        "2026-01-01T10:41:00.000Z")
    assert result.value.observed_counter_delta_down_bytes == 50
    assert result.value.observed_counter_delta_up_bytes is None
    assert result.value.observed_delta_coverage.numerator == 1
    assert result.value.observed_delta_coverage.denominator == 1


def test_single_visit_wireless_reuses_wireless_signal_contract(analytics_stack):
    result = _service(analytics_stack).get_visit_wireless_summary(
        SITE_A, analytics_stack.visit_id)
    assert result.value.visit_id == analytics_stack.visit_id
    assert result.value.observation_coverage.sample_count == 2
    assert set(result.value.signal) == {"rssi", "snr"}


def test_time_series_has_zero_buckets_and_explicit_timezone(analytics_stack):
    result = _service(analytics_stack).get_visit_time_series(
        SITE_A, FROM, TO, "hour", display_timezone="UTC")
    assert result.value.display_timezone == "UTC"
    assert sum(item.count for item in result.value.items) == 2
    assert all("+00:00" in item.bucket_start for item in result.value.items)
    assert all(item.bucket_start[14:16] == "00"
               for item in result.value.items)


def test_hour_series_starts_from_local_bucket_for_fractional_offset(
    analytics_stack,
):
    _insert_closed(
        analytics_stack, started="2026-01-02T10:15:00.000Z",
        closed="2026-01-02T10:16:00.000Z")
    _insert_closed(
        analytics_stack, started="2026-01-02T11:45:00.000Z",
        closed="2026-01-02T11:46:00.000Z")
    result = _service(analytics_stack).get_visit_time_series(
        SITE_A, "2026-01-02T10:10:00.000Z",
        "2026-01-02T12:10:00.000Z", "hour",
        display_timezone="Asia/Kolkata")
    assert result.value.items[0].bucket_start.startswith(
        "2026-01-02T15:00:00.000+05:30")
    assert all(item.bucket_start[14:16] == "00"
               for item in result.value.items)
    assert sum(item.count for item in result.value.items) == 2


@pytest.mark.parametrize("zone", ["Europe/Berlin", "America/New_York"])
def test_time_series_dst_boundaries_have_explicit_offsets(
    analytics_stack, zone,
):
    result = _service(analytics_stack).get_visit_time_series(
        SITE_A, FROM, TO, "day", display_timezone=zone)
    assert result.status == "ok"
    assert all(item.bucket_start[-6] in {"+", "-"}
               for item in result.value.items)


def test_hour_series_handles_dst_forward_and_repeated_fall_hour(
    analytics_stack,
):
    service = _service(analytics_stack)
    _insert_closed(
        analytics_stack, started="2026-03-08T06:30:00.000Z",
        closed="2026-03-08T06:31:00.000Z")
    _insert_closed(
        analytics_stack, started="2026-03-08T07:30:00.000Z",
        closed="2026-03-08T07:31:00.000Z")
    spring = service.get_visit_time_series(
        SITE_A, "2026-03-08T06:00:00.000Z", "2026-03-08T09:00:00.000Z",
        "hour", display_timezone="America/New_York")
    assert [item.bucket_start[11:16] for item in spring.value.items] == [
        "01:00", "03:00", "04:00"]
    assert sum(item.count for item in spring.value.items) == 2
    _insert_closed(
        analytics_stack, started="2026-11-01T05:30:00.000Z",
        closed="2026-11-01T05:31:00.000Z")
    _insert_closed(
        analytics_stack, started="2026-11-01T06:30:00.000Z",
        closed="2026-11-01T06:31:00.000Z")
    fall = service.get_visit_time_series(
        SITE_A, "2026-11-01T05:00:00.000Z", "2026-11-01T08:00:00.000Z",
        "hour", display_timezone="America/New_York")
    assert [item.bucket_start[11:16] for item in fall.value.items] == [
        "01:00", "01:00", "02:00"]
    assert fall.value.items[0].bucket_start.endswith("-04:00")
    assert fall.value.items[1].bucket_start.endswith("-05:00")
    assert all(item.bucket_start[14:16] == "00"
               for item in fall.value.items)
    assert sum(item.count for item in fall.value.items) == 2


def test_invalid_timezone_and_90_day_bound_are_rejected(analytics_stack):
    service = _service(analytics_stack)
    with pytest.raises(AnalyticsQueryValidationError):
        service.get_visit_time_series(SITE_A, FROM, TO, "day",
                                      display_timezone="Not/AZone")
    with pytest.raises(AnalyticsQueryValidationError):
        service.get_visit_counts(
            SITE_A, "2025-01-01T00:00:00.000Z",
            "2026-01-01T00:00:00.000Z")


def test_return_intervals_are_site_scoped_and_minimum_bounded(analytics_stack):
    _insert_open(analytics_stack, device=DEVICE_A)
    enough = _service(analytics_stack, minimum=1).get_return_intervals(
        SITE_A, FROM, TO)
    insufficient = _service(analytics_stack, minimum=2).get_return_intervals(
        SITE_A, FROM, TO)
    assert enough.value.distribution.sample_count == 1
    assert enough.status == "ok"
    assert insufficient.status == "insufficient_data"


def test_aggregate_results_have_no_identifier_lists(analytics_stack):
    result = _service(analytics_stack).get_visit_analytics_bundle(
        SITE_A, FROM, TO)
    text = repr(result)
    assert CLIENT_A not in text
    assert DEVICE_A not in text


def test_source_event_quality_excludes_null_site_and_returns_watermark(
    analytics_stack,
):
    with closing(analytics_stack.visits._connect()) as connection:  # noqa: SLF001
        for event_id, site, result, reason, offset in (
            ("event-site", SITE_A, "unmatched", "no_open_visit", 10),
            ("event-null", None, "invalid", "site_unresolved", 20),
        ):
            connection.execute("""
              INSERT INTO visit_source_events (
                event_id,event_type,site_id,client_mac,controller_event_at,
                received_at,source_identity,source_offset_start,
                source_offset_end,processing_result,visit_id,reason,
                first_processed_at,processed_at,pending_until,
                last_match_attempt_at
              ) VALUES (?,'offline',?,NULL,NULL,NULL,'fixture',?,?,?,NULL,?,
                        '2026-01-01T10:10:00.000Z',
                        '2026-01-01T10:10:00.000Z',NULL,NULL)
            """, (event_id, site, offset, offset+1, result, reason))
        connection.commit()
    result = _service(analytics_stack).get_source_event_quality(
        SITE_A, FROM, TO)
    assert result.value.by_processing_result["unmatched"] == 1
    assert result.value.by_processing_result["invalid"] == 0
    assert result.value.by_reason == {"no_open_visit": 1}
    assert result.provenance.source_watermarks["visits"] == \
        "2026-01-01T10:10:00.000Z"


def test_closure_keeps_reported_and_lifecycle_duration_separate(
    analytics_stack,
):
    with closing(analytics_stack.visits._connect()) as connection:  # noqa: SLF001
        connection.execute(
            "UPDATE visits SET reported_connected_seconds=360 "
            "WHERE visit_id=?", (analytics_stack.visit_id,))
        connection.commit()
    result = _service(analytics_stack).get_closure_distribution(
        SITE_A, FROM, TO)
    assert result.value.close_reasons == {"client_offline": 1}
    assert result.value.duration_difference_seconds.p50 == 60


def test_recovered_close_reason_remains_auditable_in_visit_analytics(
    analytics_stack,
):
    with closing(analytics_stack.visits._connect()) as connection:  # noqa: SLF001
        connection.execute(
            "UPDATE visits SET close_reason='omada_client_offline_recovered' "
            "WHERE visit_id=?",
            (analytics_stack.visit_id,),
        )
        connection.commit()

    result = _service(analytics_stack).get_closure_distribution(
        SITE_A, FROM, TO
    )

    assert result.value.close_reasons == {
        "omada_client_offline_recovered": 1
    }


def test_coverage_summary_does_not_issue_per_visit_queries(
    analytics_stack, monkeypatch,
):
    calls = {"batch": 0, "single": 0}
    original_batch = analytics_stack.gateway.visit_observation_coverage_batch
    original_single = analytics_stack.gateway.observation_coverage

    def batch(**kwargs):
        calls["batch"] += 1
        return original_batch(**kwargs)

    def single(**kwargs):
        calls["single"] += 1
        return original_single(**kwargs)

    monkeypatch.setattr(
        analytics_stack.gateway, "visit_observation_coverage_batch", batch)
    monkeypatch.setattr(
        analytics_stack.gateway, "observation_coverage", single)
    _service(analytics_stack).get_observation_coverage_summary(
        SITE_A, FROM, TO)
    assert calls == {"batch": 1, "single": 0}


def test_unavailable_source_does_not_synthesize_zero_series(
    analytics_stack, monkeypatch,
):
    def unavailable(**_kwargs):
        raise AnalyticsSourceUnavailable("visits unavailable")

    monkeypatch.setattr(
        analytics_stack.gateway, "visit_start_timestamps", unavailable)
    result = _service(analytics_stack).get_visit_time_series(
        SITE_A, FROM, TO, "hour")
    assert result.status == "unavailable"
    assert result.value is None


def test_visit_configuration_defaults_and_bounds():
    config = analytics_config_from_settings({})
    assert config.visit_enabled is True
    assert config.visit_min_cohort_size == 20
    assert config.visit_max_window_days == 90
    configured = analytics_config_from_settings({
        "analytics_visit_enabled": "false",
        "analytics_visit_min_cohort_size": "25",
        "analytics_visit_max_window_days": "30",
    })
    assert configured.visit_enabled is False
    assert configured.visit_min_cohort_size == 25
    assert configured.visit_max_window_days == 30
    with pytest.raises(AnalyticsConfigError):
        analytics_config_from_settings({
            "analytics_visit_max_window_days": 91})


def test_visit_queries_are_read_only_and_do_not_change_schema(analytics_stack):
    repositories = (
        analytics_stack.observations, analytics_stack.visits,
        analytics_stack.registry)
    before = []
    for repository in repositories:
        with closing(repository._connect()) as connection:  # noqa: SLF001
            before.append((connection.execute("PRAGMA user_version").fetchone()[0],
                           connection.total_changes))
    service = _service(analytics_stack)
    service.get_visit_analytics_bundle(SITE_A, FROM, TO)
    after = []
    for repository in repositories:
        with closing(repository._connect()) as connection:  # noqa: SLF001
            after.append((connection.execute("PRAGMA user_version").fetchone()[0],
                          connection.total_changes))
    assert before == after
