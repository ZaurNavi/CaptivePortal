from __future__ import annotations

import base64
import json
import sqlite3
from dataclasses import FrozenInstanceError, asdict, replace

import pytest

from app.analytics.current_guest_traffic import (
    BOUNDARY_OBSERVATION,
    CONTINUITY_METHOD,
    CURRENT_GUEST_RATE_MAX_GAP_SECONDS,
    METRIC_VERSION,
    SUPPORTED_MAX_POPULATION,
    CurrentGuestTrafficIntegrityUnavailable,
    CurrentGuestTrafficReadService,
    CurrentGuestTrafficValidationError,
)
from app.current_state.models import CurrentStateCycle
from app.current_state.config import current_state_config_from_settings
from app.current_state.normalizer import canonical_scope
from app.current_state.read_service import CurrentStateReadService
from app.current_state.read_service import CurrentGuestRateEvidence
from app.current_state.repository import CurrentStateRepository


SITE = "a" * 24
OTHER_SITE = "b" * 24
SSID = "Zefer_Parki"
BASELINE_AT = "2026-09-01T09:59:00.000Z"
CURRENT_AT = "2026-09-01T10:00:00.000Z"
EVALUATED_AT = "2026-09-01T10:00:30.000Z"


@pytest.fixture
def guest_service(tmp_path):
    config = current_state_config_from_settings({
        "current_state_enabled": "true",
        "current_state_db_path": str(tmp_path / "current_state.sqlite3"),
        "current_state_site_ids": SITE,
        "current_state_client_ssids_json": json.dumps([SSID]),
        "observation_db_path": str(tmp_path / "observations.sqlite3"),
        "visit_lifecycle_db_path": str(tmp_path / "visits.sqlite3"),
        "visitor_registry_db_path": str(tmp_path / "registry.sqlite3"),
        "portal_counter_db_path": str(tmp_path / "portal.sqlite3"),
        "public_traffic_db_path": str(tmp_path / "traffic.sqlite3"),
    })
    repository = CurrentStateRepository(config)
    repository.initialize()
    current_state = CurrentStateReadService(repository)
    return CurrentGuestTrafficReadService(current_state), repository


def _cycle(
    cycle_id: str,
    started: str,
    rows: int,
    *,
    site: str = SITE,
    result: str = "success",
    ssids: tuple[str, ...] = (SSID,),
    items_seen: int | None = None,
) -> CurrentStateCycle:
    scope_json, scope_hash = canonical_scope("client", site, ssids)
    seen = rows if items_seen is None else items_seen
    return CurrentStateCycle(
        cycle_id=cycle_id,
        kind="client",
        site_id=site,
        capture_started_at=started,
        capture_finished_at=started,
        complete=result == "success",
        result=result,
        source_scope_version=1,
        source_scope_json=scope_json,
        source_scope_hash=scope_hash,
        source_rows_reported=seen,
        items_seen=seen,
        items_stored=rows,
        items_skipped=seen - rows,
        unidentified_count=0,
        duplicate_identity_count=0,
        unknown_status_count=0,
        error_count=0 if result == "success" else 1,
        data_quality_warning_count=0,
        page_count=1,
        failure_category=None if result == "success" else "controller_error",
        duration_ms=10,
        created_at=started,
    )


def _row(
    cycle_id: str,
    observed_at: str,
    index: int = 1,
    *,
    site: str = SITE,
    ssid: str = SSID,
    auth: str = "authorized",
    uptime: int | None = 100,
    down: int | None = 1_000,
    up: int | None = 2_000,
    ap_mac: str | None = "10:20:30:40:50:60",
) -> dict[str, object]:
    return {
        "cycle_id": cycle_id,
        "cycle_kind": "client",
        "site_id": site,
        "observed_at": observed_at,
        "client_mac": f"AA:BB:CC:DD:{index // 256:02X}:{index % 256:02X}",
        "name": f"guest-{index}",
        "hostname": None,
        "device_type": None,
        "ip": None,
        "ssid": ssid,
        "ap_name": None,
        "ap_mac": ap_mac,
        "radio_id": None,
        "band": None,
        "channel": None,
        "rssi": None,
        "snr": None,
        "controller_uptime": uptime,
        "auth_status_code": 2 if auth == "authorized" else None,
        "auth_classification": auth,
        "controller_traffic_down": down,
        "controller_traffic_up": up,
        "controller_traffic_total": (
            down + up if down is not None and up is not None else None
        ),
        "active": True,
        "wireless": True,
    }


def _publish_pair(
    repository: CurrentStateRepository,
    *,
    baseline_rows: list[dict[str, object]] | None = None,
    current_rows: list[dict[str, object]] | None = None,
    baseline_at: str = BASELINE_AT,
    current_at: str = CURRENT_AT,
    ssids: tuple[str, ...] = (SSID,),
) -> None:
    baseline_rows = baseline_rows if baseline_rows is not None else [
        _row("baseline", baseline_at, uptime=100, down=1_000, up=2_000)
    ]
    current_rows = current_rows if current_rows is not None else [
        _row("current", current_at, uptime=160, down=2_500, up=5_000)
    ]
    repository.publish_cycle(
        _cycle("baseline", baseline_at, len(baseline_rows), ssids=ssids),
        client_rows=baseline_rows,
    )
    repository.publish_cycle(
        _cycle("current", current_at, len(current_rows), ssids=ssids),
        client_rows=current_rows,
    )


def _read(service: CurrentGuestTrafficReadService, **kwargs):
    return service.get_current_guest_traffic(
        SITE, evaluated_at_utc=EVALUATED_AT, **kwargs
    )


def test_metric_identity_and_positive_rates_are_frozen(guest_service):
    service, repository = guest_service
    _publish_pair(repository)

    result = _read(service)

    assert result.metric_version == METRIC_VERSION
    assert result.continuity_method == CONTINUITY_METHOD
    assert result.connection_boundary_observation == BOUNDARY_OBSERVATION
    assert result.elapsed_seconds == 60.0
    assert result.status == "ok"
    assert result.source_health_status == "healthy"
    assert result.rate_evidence_status == "complete"
    assert result.population_count == 1
    assert result.rate_valid_count == 1
    assert result.items[0].download_mbps == pytest.approx(0.0002)
    assert result.items[0].upload_mbps == pytest.approx(0.0004)
    assert result.items[0].total_mbps == pytest.approx(0.0006)
    assert result.items[0].connection_continuity_status == "proven"
    assert result.items[0].continuity_basis == "uptime_progress"
    with pytest.raises(FrozenInstanceError):
        result.status = "partial"  # type: ignore[misc]


def test_complete_cycles_may_skip_out_of_scope_controller_inventory_rows(
    guest_service,
):
    service, repository = guest_service
    baseline_rows = [
        _row("baseline", BASELINE_AT, 1, uptime=100, down=1_000, up=2_000),
        _row("baseline", BASELINE_AT, 2, uptime=100, down=2_000, up=3_000),
    ]
    current_rows = [
        _row("current", CURRENT_AT, 1, uptime=160, down=2_500, up=5_000),
        _row("current", CURRENT_AT, 2, uptime=160, down=4_000, up=6_000),
    ]
    repository.publish_cycle(
        _cycle("baseline", BASELINE_AT, 2, items_seen=5),
        client_rows=baseline_rows,
    )
    repository.publish_cycle(
        _cycle("current", CURRENT_AT, 2, items_seen=5),
        client_rows=current_rows,
    )

    result = _read(service)

    assert result.status == "ok"
    assert result.scoped_client_row_count == 2
    assert result.population_count == 2
    assert result.rate_valid_count == 2
    assert all(item.rate_status == "valid" for item in result.items)


def test_zero_population_is_ok_without_baseline(guest_service):
    service, repository = guest_service
    repository.publish_cycle(_cycle("current", CURRENT_AT, 0))

    result = _read(service)

    assert result.status == "ok"
    assert result.population_count == 0
    assert result.rate_evidence_status == "not_applicable"
    assert (result.rate_valid_count, result.rate_partial_count, result.rate_unavailable_count) == (0, 0, 0)
    assert result.baseline_cycle_id is None
    assert result.items == ()


def test_nonempty_population_without_baseline_is_insufficient(guest_service):
    service, repository = guest_service
    current = [_row("current", CURRENT_AT, uptime=160, down=2_500, up=5_000)]
    repository.publish_cycle(
        _cycle("current", CURRENT_AT, 1), client_rows=current
    )

    result = _read(service)

    assert result.status == "insufficient_data"
    assert result.population_count == 1
    assert result.rate_evidence_status == "insufficient_data"
    assert result.items[0].total_reason == "no_baseline"


def test_missing_or_nonauthorized_client_baseline_is_not_inherited(guest_service):
    service, repository = guest_service
    baseline = [
        _row("baseline", BASELINE_AT, 1, auth="pending"),
        _row("baseline", BASELINE_AT, 3),
    ]
    current = [
        _row("current", CURRENT_AT, 1, uptime=160, down=2_000, up=3_000),
        _row("current", CURRENT_AT, 2, uptime=160, down=2_000, up=3_000),
    ]
    _publish_pair(repository, baseline_rows=baseline, current_rows=current)

    result = _read(service)

    assert {item.total_reason for item in result.items} == {
        "no_authorized_baseline"
    }
    assert result.rate_evidence_status == "insufficient_data"


def test_unknown_auth_is_excluded_and_makes_population_partial(guest_service):
    service, repository = guest_service
    baseline = [_row("baseline", BASELINE_AT)]
    current = [
        _row("current", CURRENT_AT, uptime=160, down=2_000, up=3_000),
        _row("current", CURRENT_AT, 2, auth="unknown", uptime=None, down=None, up=None),
        _row("current", CURRENT_AT, 3, auth="pending"),
        _row("current", CURRENT_AT, 4, auth="other"),
    ]
    _publish_pair(repository, baseline_rows=baseline, current_rows=current)

    result = _read(service)

    assert result.status == "partial"
    assert result.population_count == 1
    assert result.known_authorized_count == 1
    assert result.unknown_auth_count == 1
    assert result.population_complete is False
    assert [item.client_mac for item in result.items] == [current[0]["client_mac"]]


@pytest.mark.parametrize(
    ("evaluated", "status"),
    [
        ("2026-09-01T10:01:00.001Z", "stale"),
        ("2026-09-01T10:03:00.001Z", "unavailable"),
    ],
)
def test_stale_and_unavailable_never_assert_online_population(
    guest_service, evaluated, status
):
    service, repository = guest_service
    _publish_pair(repository)

    result = service.get_current_guest_traffic(SITE, evaluated_at_utc=evaluated)

    assert result.status == status
    assert result.population_count is None
    assert result.rate_valid_count is None
    assert result.items == ()


def test_future_latest_complete_is_unavailable_and_does_not_fallback(guest_service):
    service, repository = guest_service
    _publish_pair(repository)
    future_at = "2026-09-01T10:01:00.000Z"
    repository.publish_cycle(_cycle("future", future_at, 0))

    result = _read(service)

    assert result.current_cycle_id == "future"
    assert result.status == "unavailable"
    assert result.source_health_reason == "clock_anomaly"
    assert result.population_count is None


@pytest.mark.parametrize("attempt_result", ["partial", "failed", "shutdown"])
def test_newer_same_scope_degraded_attempt_preserves_previous_complete(
    guest_service, attempt_result
):
    service, repository = guest_service
    _publish_pair(repository, current_at="2026-09-01T09:59:30.000Z")
    partial_at = CURRENT_AT
    partial = (
        [_row("partial", partial_at, uptime=170, down=3_000, up=6_000)]
        if attempt_result == "partial"
        else []
    )
    repository.publish_cycle(
        _cycle("partial", partial_at, len(partial), result=attempt_result),
        client_rows=partial,
    )

    result = _read(service)

    assert result.current_cycle_id == "current"
    assert result.source_health_status == "degraded"
    assert result.status == "partial"
    assert result.items[0].rate_status == "valid"


def test_newer_different_scope_attempt_does_not_degrade(guest_service):
    service, repository = guest_service
    _publish_pair(repository)
    other_scope = ("OtherGuest",)
    row = _row("other-scope", "2026-09-01T10:00:10.000Z", ssid="OtherGuest")
    repository.publish_cycle(
        _cycle(
            "other-scope", "2026-09-01T10:00:10.000Z", 1,
            result="partial", ssids=other_scope,
        ),
        client_rows=[row],
    )

    assert _read(service).source_health_status == "healthy"


def test_newer_partial_does_not_turn_stale_previous_complete_into_population(
    guest_service,
):
    service, repository = guest_service
    old_current = "2026-09-01T09:58:00.000Z"
    old_baseline = "2026-09-01T09:57:00.000Z"
    _publish_pair(
        repository, baseline_at=old_baseline, current_at=old_current
    )
    partial = [_row("partial", CURRENT_AT)]
    repository.publish_cycle(
        _cycle("partial", CURRENT_AT, 1, result="partial"),
        client_rows=partial,
    )

    result = _read(service)

    assert result.status == "stale"
    assert result.population_count is None
    assert result.items == ()


@pytest.mark.parametrize("field", ["unidentified_count", "duplicate_identity_count"])
def test_selected_complete_impossible_identity_metadata_fails_closed(
    guest_service, field
):
    service, repository = guest_service
    _publish_pair(repository)
    with sqlite3.connect(repository.config.db_path) as connection:
        connection.execute(
            f"UPDATE current_state_cycles SET {field}=1 WHERE cycle_id='current'"
        )
        connection.commit()

    with pytest.raises(CurrentGuestTrafficIntegrityUnavailable):
        _read(service)


@pytest.mark.parametrize(
    ("baseline_uptime", "current_uptime", "progress", "continuity", "reason"),
    [
        (100, 100, "frozen", "unproven", "source_frozen"),
        (100, 99, "unproven", "reset", "connection_reset"),
        (None, 160, "advanced", "unproven", "connection_continuity_unproven"),
        (100, None, "advanced", "unproven", "connection_continuity_unproven"),
    ],
)
def test_uptime_boundaries_never_fabricate_zero(
    guest_service, baseline_uptime, current_uptime, progress, continuity, reason
):
    service, repository = guest_service
    _publish_pair(
        repository,
        baseline_rows=[_row("baseline", BASELINE_AT, uptime=baseline_uptime)],
        current_rows=[
            _row("current", CURRENT_AT, uptime=current_uptime, down=2_000, up=3_000)
        ],
    )

    item = _read(service).items[0]

    assert item.source_progress_status == progress
    assert item.connection_continuity_status == continuity
    assert item.total_mbps is None
    assert item.total_reason == reason


def test_true_zero_requires_advanced_proven_continuity(guest_service):
    service, repository = guest_service
    _publish_pair(
        repository,
        baseline_rows=[_row("baseline", BASELINE_AT, uptime=100, down=1_000, up=2_000)],
        current_rows=[_row("current", CURRENT_AT, uptime=160, down=1_000, up=2_000)],
    )

    item = _read(service).items[0]

    assert item.source_progress_status == "advanced"
    assert item.connection_continuity_status == "proven"
    assert (item.download_mbps, item.upload_mbps, item.total_mbps) == (0.0, 0.0, 0.0)
    assert item.rate_status == "valid"


def test_exact_180_second_gap_is_accepted(guest_service):
    service, repository = guest_service
    baseline_at = "2026-09-01T09:57:00.000Z"
    _publish_pair(
        repository,
        baseline_at=baseline_at,
        baseline_rows=[_row("baseline", baseline_at, uptime=100)],
    )

    result = _read(service)

    assert result.elapsed_seconds == 180.0
    assert result.items[0].rate_status == "valid"


def test_ap_roam_is_allowed_but_ssid_transition_is_rejected(guest_service):
    _service, repository = guest_service
    two_scope = (SSID, "Guest2")
    scoped_repository = CurrentStateRepository(
        replace(repository.config, client_ssids=two_scope)
    )
    service = CurrentGuestTrafficReadService(CurrentStateReadService(scoped_repository))
    _publish_pair(
        scoped_repository,
        baseline_rows=[
            _row("baseline", BASELINE_AT, ap_mac="10:20:30:40:50:60"),
            _row("baseline", BASELINE_AT, 2, ssid="Guest2", ap_mac="10:20:30:40:50:60"),
        ],
        current_rows=[
            _row("current", CURRENT_AT, uptime=160, down=2_000, up=4_000, ap_mac="10:20:30:40:50:61"),
            _row("current", CURRENT_AT, 2, uptime=160, down=2_000, up=4_000),
        ],
        ssids=two_scope,
    )

    result = _read(service)
    by_mac = {item.client_mac: item for item in result.items}

    assert by_mac["AA:BB:CC:DD:00:01"].rate_status == "valid"
    assert by_mac["AA:BB:CC:DD:00:02"].total_reason == "ssid_transition"


def test_excessive_elapsed_is_conservative(guest_service):
    service, repository = guest_service
    _publish_pair(repository, baseline_at="2026-09-01T09:56:59.000Z")

    result = _read(service)

    assert result.items[0].total_reason == "baseline_gap_too_large"
    assert result.rate_evidence_status == "insufficient_data"
    assert CURRENT_GUEST_RATE_MAX_GAP_SECONDS == 180


def test_capture_finished_is_not_rate_denominator(guest_service):
    service, repository = guest_service
    _publish_pair(repository)
    with sqlite3.connect(repository.config.db_path) as connection:
        connection.execute(
            "UPDATE current_state_cycles SET capture_finished_at=? WHERE cycle_id='baseline'",
            ("2026-09-01T09:59:59.000Z",),
        )
        connection.commit()

    assert _read(service).elapsed_seconds == 60.0


@pytest.mark.parametrize("cycle_id", ["current", "baseline"])
def test_row_observed_at_must_equal_parent_capture_start(guest_service, cycle_id):
    service, repository = guest_service
    _publish_pair(repository)
    with sqlite3.connect(repository.config.db_path) as connection:
        connection.execute(
            "UPDATE current_client_state SET observed_at=? WHERE cycle_id=?",
            ("2026-09-01T09:58:00.000Z", cycle_id),
        )
        connection.commit()

    with pytest.raises(CurrentGuestTrafficIntegrityUnavailable):
        _read(service)


@pytest.mark.parametrize(
    ("baseline_down", "current_down", "baseline_up", "current_up", "status"),
    [
        (1_000, 900, 2_000, 3_000, "partial"),
        (None, None, 2_000, 3_000, "partial"),
        (None, None, None, None, "unavailable"),
    ],
)
def test_direction_counter_failures_are_not_clamped(
    guest_service, baseline_down, current_down, baseline_up, current_up, status
):
    service, repository = guest_service
    _publish_pair(
        repository,
        baseline_rows=[
            _row("baseline", BASELINE_AT, down=baseline_down, up=baseline_up)
        ],
        current_rows=[
            _row(
                "current", CURRENT_AT, uptime=160,
                down=current_down, up=current_up,
            )
        ],
    )

    item = _read(service).items[0]

    assert item.rate_status == status
    assert item.total_mbps is None
    if baseline_down is not None and current_down is not None and current_down < baseline_down:
        assert item.download_reason == "counter_reset"


def test_population_wide_rate_counts_precede_pagination(guest_service):
    service, repository = guest_service
    baseline = [
        _row("baseline", BASELINE_AT, index, uptime=100, down=1_000, up=2_000)
        for index in range(1, 5)
    ]
    current = [
        _row("current", CURRENT_AT, 1, uptime=160, down=4_000, up=5_000),
        _row("current", CURRENT_AT, 2, uptime=160, down=3_000, up=None),
        _row("current", CURRENT_AT, 3, uptime=100, down=3_000, up=4_000),
        _row("current", CURRENT_AT, 4, uptime=160, down=1_000, up=2_000),
    ]
    _publish_pair(repository, baseline_rows=baseline, current_rows=current)

    first = _read(service, limit=1)
    second = _read(service, limit=2, cursor=first.page.next_cursor)

    assert first.rate_evidence_status == second.rate_evidence_status == "partial"
    assert first.status == second.status == "partial"
    assert (first.rate_valid_count, first.rate_partial_count, first.rate_unavailable_count) == (2, 1, 1)
    assert (second.rate_valid_count, second.rate_partial_count, second.rate_unavailable_count) == (2, 1, 1)
    assert first.population_count == second.population_count == 4


def test_global_integer_sort_numeric_then_null_and_cursor_has_no_float(guest_service):
    service, repository = guest_service
    baseline = [_row("baseline", BASELINE_AT, index) for index in range(1, 5)]
    current = [
        _row("current", CURRENT_AT, 1, uptime=160, down=2_000, up=4_000),
        _row("current", CURRENT_AT, 2, uptime=160, down=3_000, up=5_000),
        _row("current", CURRENT_AT, 3, uptime=100, down=4_000, up=6_000),
        _row("current", CURRENT_AT, 4, uptime=100, down=4_000, up=6_000),
    ]
    _publish_pair(repository, baseline_rows=baseline, current_rows=current)

    first = _read(service, limit=2)
    raw = first.page.next_cursor
    assert raw is not None
    decoded = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    second = _read(service, limit=2, cursor=raw)

    assert [item.client_mac for item in first.items] == [
        "AA:BB:CC:DD:00:02", "AA:BB:CC:DD:00:01"
    ]
    assert [item.client_mac for item in second.items] == [
        "AA:BB:CC:DD:00:03", "AA:BB:CC:DD:00:04"
    ]
    assert "total_mbps" not in decoded
    assert decoded["total_delta_bytes"] == 3_000


def test_cursor_pins_cycles_evaluation_scope_and_new_cycles_do_not_repin(guest_service):
    service, repository = guest_service
    rows = [_row("baseline", BASELINE_AT, index) for index in range(1, 3)]
    current = [
        _row("current", CURRENT_AT, index, uptime=160, down=2_000 + index, up=4_000)
        for index in range(1, 3)
    ]
    _publish_pair(repository, baseline_rows=rows, current_rows=current)
    first = _read(service, limit=1)
    repository.publish_cycle(
        _cycle("future", "2026-09-01T10:01:00.000Z", 0)
    )

    second = _read(service, limit=1, cursor=first.page.next_cursor)

    assert second.current_cycle_id == first.current_cycle_id == "current"
    assert second.baseline_cycle_id == first.baseline_cycle_id == "baseline"
    assert second.evaluated_at_utc == first.evaluated_at_utc == EVALUATED_AT


def _root_semantics(result):
    return (
        result.source_health_status,
        result.rate_evidence_status,
        result.population_complete,
        result.status,
        result.rate_valid_count,
        result.rate_partial_count,
        result.rate_unavailable_count,
    )


def _publish_two_page_pair(repository, *, current_at=CURRENT_AT):
    baseline = [
        _row("baseline", BASELINE_AT, index, uptime=100, down=1_000, up=2_000)
        for index in range(1, 3)
    ]
    current = [
        _row(
            "current", current_at, index, uptime=160,
            down=2_000 + index, up=4_000 + index,
        )
        for index in range(1, 3)
    ]
    _publish_pair(
        repository,
        baseline_rows=baseline,
        current_rows=current,
        current_at=current_at,
    )


@pytest.mark.parametrize("late_result", ["partial", "success"])
def test_late_published_cycle_before_evaluation_does_not_change_cursor_snapshot(
    guest_service, late_result
):
    service, repository = guest_service
    _publish_two_page_pair(repository)
    first = _read(service, limit=1)
    assert first.page.next_cursor is not None
    decoded = json.loads(base64.urlsafe_b64decode(
        first.page.next_cursor + "=" * (-len(first.page.next_cursor) % 4)
    ))
    assert decoded["newer_attempt_cycle_id"] is None

    late_at = "2026-09-01T10:00:15.000Z"
    late_rows = (
        [_row("late", late_at, uptime=170, down=3_000, up=6_000)]
        if late_result == "partial"
        else []
    )
    repository.publish_cycle(
        _cycle("late", late_at, len(late_rows), result=late_result),
        client_rows=late_rows,
    )

    second = _read(service, limit=1, cursor=first.page.next_cursor)

    assert second.current_cycle_id == first.current_cycle_id == "current"
    assert _root_semantics(second) == _root_semantics(first)
    assert second.source_health_status == "healthy"


def test_cursor_pins_original_degraded_attempt_identity(guest_service):
    service, repository = guest_service
    current_at = "2026-09-01T09:59:30.000Z"
    _publish_two_page_pair(repository, current_at=current_at)
    partial_at = "2026-09-01T10:00:00.000Z"
    repository.publish_cycle(
        _cycle("original-partial", partial_at, 1, result="partial"),
        client_rows=[_row("original-partial", partial_at)],
    )
    first = _read(service, limit=1)
    assert first.page.next_cursor is not None
    decoded = json.loads(base64.urlsafe_b64decode(
        first.page.next_cursor + "=" * (-len(first.page.next_cursor) % 4)
    ))
    assert decoded["newer_attempt_cycle_id"] == "original-partial"
    assert first.source_health_status == "degraded"

    later_at = "2026-09-01T10:00:15.000Z"
    repository.publish_cycle(
        _cycle("later-failed", later_at, 0, result="failed")
    )
    second = _read(service, limit=1, cursor=first.page.next_cursor)

    assert _root_semantics(second) == _root_semantics(first)
    assert second.source_health_status == "degraded"


def test_pinned_newer_attempt_retention_deletion_expires_cursor(guest_service):
    service, repository = guest_service
    current_at = "2026-09-01T09:59:30.000Z"
    _publish_two_page_pair(repository, current_at=current_at)
    partial_at = "2026-09-01T10:00:00.000Z"
    repository.publish_cycle(
        _cycle("pinned-partial", partial_at, 1, result="partial"),
        client_rows=[_row("pinned-partial", partial_at)],
    )
    cursor = _read(service, limit=1).page.next_cursor
    assert cursor is not None
    with sqlite3.connect(repository.config.db_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            "DELETE FROM current_state_cycles WHERE cycle_id='pinned-partial'"
        )
        connection.commit()

    with pytest.raises(CurrentGuestTrafficValidationError, match="cursor_expired"):
        _read(service, limit=1, cursor=cursor)


def test_cursor_expiry_and_cross_site_replay_are_explicit(guest_service):
    service, repository = guest_service
    _publish_pair(
        repository,
        baseline_rows=[_row("baseline", BASELINE_AT, index) for index in range(1, 3)],
        current_rows=[
            _row("current", CURRENT_AT, index, uptime=160, down=2_000, up=4_000)
            for index in range(1, 3)
        ],
    )
    cursor = _read(service, limit=1).page.next_cursor
    assert cursor is not None

    with pytest.raises(CurrentGuestTrafficValidationError, match="Site"):
        service.get_current_guest_traffic(
            OTHER_SITE, evaluated_at_utc=EVALUATED_AT, cursor=cursor
        )
    with sqlite3.connect(repository.config.db_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("DELETE FROM current_state_cycles WHERE cycle_id='baseline'")
        connection.commit()
    with pytest.raises(CurrentGuestTrafficValidationError, match="cursor_expired"):
        _read(service, cursor=cursor)


def test_cursor_scope_change_rejected_before_source_read(guest_service):
    service, repository = guest_service
    _publish_pair(
        repository,
        baseline_rows=[_row("baseline", BASELINE_AT, index) for index in range(1, 3)],
        current_rows=[
            _row("current", CURRENT_AT, index, uptime=160, down=2_000, up=4_000)
            for index in range(1, 3)
        ],
    )
    cursor = _read(service, limit=1).page.next_cursor
    changed = CurrentStateReadService(
        CurrentStateRepository(replace(repository.config, client_ssids=("Other",)))
    )

    with pytest.raises(CurrentGuestTrafficValidationError, match="scope"):
        CurrentGuestTrafficReadService(changed).get_current_guest_traffic(
            SITE, cursor=cursor
        )


def test_unconfigured_site_is_rejected_before_any_cross_site_read(guest_service):
    service, _repository = guest_service

    with pytest.raises(CurrentGuestTrafficValidationError):
        service.get_current_guest_traffic(
            OTHER_SITE, evaluated_at_utc=EVALUATED_AT
        )


@pytest.mark.parametrize("limit", [0, 201, True, "50"])
def test_limit_is_strictly_bounded(guest_service, limit):
    service, _repository = guest_service
    with pytest.raises(CurrentGuestTrafficValidationError):
        _read(service, limit=limit)


def test_scoped_population_over_cap_is_unsupported_without_truncation(guest_service):
    service, repository = guest_service
    # The source read is intentionally stubbed at its narrow evidence boundary;
    # the 10k+10k production-size fixture belongs to the separate PERF artifact.
    base = _cycle("current", CURRENT_AT, SUPPORTED_MAX_POPULATION + 1)

    def evidence(*_args, **_kwargs):
        _scope_json, scope_hash = canonical_scope("client", SITE, (SSID,))
        return CurrentGuestRateEvidence(
            SITE,
            scope_hash,
            EVALUATED_AT,
            asdict(base),
            None,
            None,
            SUPPORTED_MAX_POPULATION + 1,
            1,
            0,
            (),
            (),
        )

    service._current_state.read_current_guest_rate_evidence = evidence  # type: ignore[method-assign]
    result = _read(service)

    assert result.status == "unsupported_population"
    assert result.scoped_client_row_count == SUPPORTED_MAX_POPULATION + 1
    assert result.items == ()


def test_selected_row_count_mismatch_is_integrity_failure(guest_service):
    service, repository = guest_service
    _publish_pair(repository)
    with sqlite3.connect(repository.config.db_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            "DELETE FROM current_client_state WHERE cycle_id='current'"
        )
        connection.commit()

    with pytest.raises(CurrentGuestTrafficIntegrityUnavailable):
        _read(service)


def test_one_read_only_transaction_and_no_provider_dependency(guest_service):
    service, repository = guest_service
    _publish_pair(repository)
    entered = 0
    original = repository.read_connection

    class Wrapped:
        def __enter__(self):
            nonlocal entered
            entered += 1
            self.inner = original()
            connection = self.inner.__enter__()
            assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
            return connection

        def __exit__(self, *args):
            return self.inner.__exit__(*args)

    repository.read_connection = lambda: Wrapped()  # type: ignore[method-assign]

    assert _read(service).status == "ok"
    assert entered == 1
    assert not hasattr(service, "omada")
    assert not hasattr(service, "provider")
