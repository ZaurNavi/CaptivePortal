from __future__ import annotations

import base64
import json
import sqlite3
from dataclasses import FrozenInstanceError
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.current_state.cleanup import CurrentStateCleanup
from app.current_state.models import CurrentStateValidationError
from app.current_state.normalizer import canonical_scope
from app.current_state.read_service import CurrentStateReadService
from app.current_state.repository import CurrentStateRepository

from .conftest import NOW, OTHER_SITE, SITE, ap_row, client_row, cycle


UTC = timezone.utc
EVALUATED = datetime(2026, 8, 23, 10, 0, 30, tzinfo=UTC)


@pytest.fixture
def service(config):
    repository = CurrentStateRepository(config)
    repository.initialize()
    return CurrentStateReadService(repository)


def publish_clients(service, cycle_id="client", started=NOW, result="success", rows=None, site=SITE, scope_ssids=("Zefer_Parki",)):
    rows = rows if rows is not None else [
        client_row(cycle_id=cycle_id, site_id=site, observed_at=started, ssid=scope_ssids[0], mac="AA:BB:CC:DD:EE:01", auth_status_code=2, auth_classification="authorized", ap_mac="11:22:33:44:55:66", controller_traffic_total=100, controller_uptime=20),
        client_row(cycle_id=cycle_id, site_id=site, observed_at=started, ssid=scope_ssids[0], mac="AA:BB:CC:DD:EE:02", auth_status_code=1, auth_classification="pending", ap_mac=None, controller_traffic_total=None, controller_uptime=None),
        client_row(cycle_id=cycle_id, site_id=site, observed_at=started, ssid=scope_ssids[0], mac="AA:BB:CC:DD:EE:03", auth_status_code=0, auth_classification="other", ap_mac="11:22:33:44:55:66", controller_traffic_total=50, controller_uptime=10),
        client_row(cycle_id=cycle_id, site_id=site, observed_at=started, ssid=scope_ssids[0], mac="AA:BB:CC:DD:EE:04", auth_classification="unknown", ap_mac="22:33:44:55:66:77", controller_traffic_total=0, controller_uptime=0),
    ]
    parent = cycle(kind="client", cycle_id=cycle_id, site_id=site, started=started, result=result, items_stored=len(rows), items_seen=len(rows))
    scope_json, scope_hash = canonical_scope("client", site, scope_ssids)
    parent = replace(parent, source_scope_json=scope_json, source_scope_hash=scope_hash)
    service.repository.publish_cycle(parent, client_rows=rows)
    return parent


def test_client_summary_uses_one_complete_cycle_and_invariants(service):
    publish_clients(service)
    summary = service.get_current_client_summary(SITE, evaluated_at_utc=EVALUATED)
    assert summary.snapshot.cycle_id == "client"
    assert summary.snapshot.freshness_status == "fresh"
    assert (summary.online_count, summary.authorized_count, summary.pending_count, summary.other_count, summary.unknown_count) == (4, 1, 1, 1, 1)
    assert summary.other_unknown_count == 2
    assert summary.ap_unknown_count == 1
    assert [(item.ap_mac, item.client_count) for item in summary.devices_by_ap] == [("11:22:33:44:55:66", 2), ("22:33:44:55:66:77", 1)]


def test_fresh_partial_never_replaces_complete(service):
    publish_clients(service, cycle_id="complete", started="2026-08-23T09:59:30.000Z")
    partial_rows = [client_row(cycle_id="partial")]
    publish_clients(service, cycle_id="partial", started=NOW, result="partial", rows=partial_rows)
    summary = service.get_current_client_summary(SITE, evaluated_at_utc=EVALUATED)
    assert summary.snapshot.cycle_id == "complete"
    assert summary.snapshot.latest_attempt_result == "partial"
    assert summary.snapshot.latest_partial_cycle_id == "partial"
    assert summary.online_count == 4


def test_failed_latest_attempt_does_not_erase_complete(service):
    publish_clients(service, cycle_id="complete", started="2026-08-23T09:59:30.000Z")
    service.repository.publish_cycle(cycle(cycle_id="failed", started=NOW, result="failed", items_seen=0))
    summary = service.get_current_client_summary(SITE, evaluated_at_utc=EVALUATED)
    assert summary.snapshot.cycle_id == "complete"
    assert summary.snapshot.latest_attempt_result == "failed"


def test_old_scope_complete_plus_current_scope_partial_is_unavailable(service):
    publish_clients(
        service,
        cycle_id="old-complete",
        started="2026-08-23T09:59:30.000Z",
        scope_ssids=("OldSSID",),
    )
    publish_clients(
        service,
        cycle_id="current-partial",
        started=NOW,
        result="partial",
        rows=[client_row(cycle_id="current-partial")],
    )

    summary = service.get_current_client_summary(SITE, evaluated_at_utc=EVALUATED)

    assert summary.snapshot.cycle_id is None
    assert summary.snapshot.freshness_status == "unavailable"
    assert summary.snapshot.latest_partial_cycle_id == "current-partial"
    assert summary.online_count is None


def test_old_scope_complete_plus_current_scope_failed_is_unavailable(service):
    publish_clients(
        service,
        cycle_id="old-complete",
        started="2026-08-23T09:59:30.000Z",
        scope_ssids=("OldSSID",),
    )
    publish_clients(service, cycle_id="current-failed", started=NOW, result="failed", rows=[])

    summary = service.get_current_client_summary(SITE, evaluated_at_utc=EVALUATED)

    assert summary.snapshot.cycle_id is None
    assert summary.snapshot.latest_attempt_result == "failed"
    assert summary.online_count is None


def test_current_scope_complete_wins_over_old_scope_complete(service):
    publish_clients(service, cycle_id="old-complete", started=NOW, scope_ssids=("OldSSID",))
    publish_clients(service, cycle_id="current-complete", started="2026-08-23T09:59:30.000Z")

    summary = service.get_current_client_summary(SITE, evaluated_at_utc=EVALUATED)

    assert summary.snapshot.cycle_id == "current-complete"
    assert summary.online_count == 4


def test_old_scope_explicit_cycle_and_cursor_are_not_current(service):
    publish_clients(service, cycle_id="old-complete", started=NOW, scope_ssids=("OldSSID",))
    old_repository = CurrentStateRepository(replace(service.config, client_ssids=("OldSSID",)))
    old_service = CurrentStateReadService(old_repository)
    old_page = old_service.list_current_clients(SITE, limit=1, evaluated_at_utc=EVALUATED)
    assert old_page.next_cursor is not None

    explicit = service.list_current_clients(
        SITE, cycle_id="old-complete", evaluated_at_utc=EVALUATED,
    )
    assert explicit.snapshot.freshness_status == "unavailable"
    assert explicit.items == ()
    with pytest.raises(CurrentStateValidationError, match="no longer current"):
        service.list_current_clients(SITE, cursor=old_page.next_cursor, evaluated_at_utc=EVALUATED)


def test_old_complete_plus_fresh_partial_is_unavailable(service):
    publish_clients(service, cycle_id="complete", started="2026-08-23T09:50:00.000Z")
    publish_clients(service, cycle_id="partial", started=NOW, result="partial", rows=[client_row(cycle_id="partial")])
    summary = service.get_current_client_summary(SITE, evaluated_at_utc=EVALUATED)
    assert summary.snapshot.freshness_status == "unavailable"
    assert summary.online_count is None


def test_complete_zero_is_exact_zero(service):
    publish_clients(service, rows=[])
    summary = service.get_current_client_summary(SITE, evaluated_at_utc=EVALUATED)
    assert summary.online_count == 0
    assert summary.devices_by_ap == ()


def test_partial_zero_is_not_exact_zero(service):
    publish_clients(service, result="partial", rows=[])
    summary = service.get_current_client_summary(SITE, evaluated_at_utc=EVALUATED)
    assert summary.snapshot.freshness_reason == "no_complete_snapshot"
    assert summary.online_count is None


def test_site_isolation(service):
    publish_clients(service)
    summary = service.get_current_client_summary(OTHER_SITE, evaluated_at_utc=EVALUATED)
    assert summary.online_count is None
    assert summary.snapshot.cycle_id is None


def test_fresh_stale_unavailable_boundaries(service):
    publish_clients(service)
    assert service.get_current_client_summary(SITE, evaluated_at_utc="2026-08-23T10:01:00.000Z").snapshot.freshness_status == "fresh"
    assert service.get_current_client_summary(SITE, evaluated_at_utc="2026-08-23T10:01:00.001Z").snapshot.freshness_status == "stale"
    assert service.get_current_client_summary(SITE, evaluated_at_utc="2026-08-23T10:03:00.001Z").snapshot.freshness_status == "unavailable"


def test_clock_regression_is_unavailable(service):
    publish_clients(service)
    summary = service.get_current_client_summary(SITE, evaluated_at_utc="2026-08-23T09:59:59.000Z")
    assert summary.snapshot.freshness_reason == "clock_anomaly"
    assert summary.snapshot.age_seconds == 0
    assert summary.online_count is None


def test_invalid_persisted_timestamp_is_unavailable(service):
    publish_clients(service)
    connection = sqlite3.connect(service.repository.config.db_path)
    connection.execute("UPDATE current_state_cycles SET capture_started_at='invalid'")
    connection.commit()
    connection.close()
    summary = service.get_current_client_summary(SITE, evaluated_at_utc=EVALUATED)
    assert summary.snapshot.freshness_reason == "invalid_timestamp"
    assert summary.snapshot.age_seconds is None


@pytest.mark.parametrize("capture_finished_at", ["invalid", "2026-08-23T09:59:59.999Z"])
def test_invalid_or_reversed_capture_finish_is_unavailable(service, capture_finished_at):
    publish_clients(service)
    connection = sqlite3.connect(service.repository.config.db_path)
    connection.execute(
        "UPDATE current_state_cycles SET capture_finished_at=?",
        (capture_finished_at,),
    )
    connection.commit()
    connection.close()

    summary = service.get_current_client_summary(SITE, evaluated_at_utc=EVALUATED)

    assert summary.snapshot.freshness_status == "unavailable"
    assert summary.snapshot.freshness_reason == "invalid_timestamp"
    assert summary.snapshot.age_seconds is None


def test_keyset_pagination_pins_cycle_scope_sort_and_filters(service):
    publish_clients(service)
    first = service.list_current_clients(SITE, limit=2, sort="controller_traffic_total_desc", auth_classification=None, evaluated_at_utc=EVALUATED)
    assert [item.client_mac for item in first.items] == ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:03"]
    assert first.next_cursor
    publish_clients(
        service,
        cycle_id="new",
        started="2026-08-23T10:00:10.000Z",
        rows=[client_row(
            cycle_id="new",
            observed_at="2026-08-23T10:00:10.000Z",
            mac="AA:BB:CC:DD:EE:99",
        )],
    )
    second = service.list_current_clients(SITE, limit=2, cursor=first.next_cursor, sort="controller_traffic_total_desc", evaluated_at_utc=EVALUATED)
    assert second.snapshot.cycle_id == "client"
    assert [item.client_mac for item in second.items] == ["AA:BB:CC:DD:EE:04", "AA:BB:CC:DD:EE:02"]
    with pytest.raises(CurrentStateValidationError):
        service.list_current_clients(SITE, limit=2, cursor=first.next_cursor, sort="client_mac", evaluated_at_utc=EVALUATED)
    with pytest.raises(CurrentStateValidationError):
        service.list_current_clients(OTHER_SITE, limit=2, cursor=first.next_cursor, sort="controller_traffic_total_desc", evaluated_at_utc=EVALUATED)


@pytest.mark.parametrize("sort", ["client_mac", "controller_uptime", "controller_traffic_total", "controller_traffic_down", "controller_traffic_up", "auth_status", "ap", "rssi", "snr"])
def test_sort_allowlist_is_bounded(service, sort):
    publish_clients(service)
    page = service.list_current_clients(SITE, limit=3, sort=sort, evaluated_at_utc=EVALUATED)
    assert len(page.items) == 3
    assert all(item.cycle_id == "client" for item in page.items)


def test_filters_are_exact_and_cursor_bound(service):
    publish_clients(service)
    page = service.list_current_clients(SITE, limit=1, auth_classification="authorized", ap_mac="11-22-33-44-55-66", ssid="Zefer_Parki", evaluated_at_utc=EVALUATED)
    assert [item.auth_classification for item in page.items] == ["authorized"]
    with pytest.raises(CurrentStateValidationError):
        service.list_current_clients(SITE, auth_classification="invented", evaluated_at_utc=EVALUATED)


def test_cursor_is_opaque_and_malformed_rejected(service):
    publish_clients(service)
    with pytest.raises(CurrentStateValidationError):
        service.list_current_clients(SITE, cursor="not-base64!", evaluated_at_utc=EVALUATED)


def test_page_bounds_no_offset_and_immutable_dtos(service):
    publish_clients(service)
    with pytest.raises(CurrentStateValidationError):
        service.list_current_clients(SITE, limit=0, evaluated_at_utc=EVALUATED)
    with pytest.raises(CurrentStateValidationError):
        service.list_current_clients(SITE, limit=501, evaluated_at_utc=EVALUATED)
    page = service.list_current_clients(SITE, limit=1, evaluated_at_utc=EVALUATED)
    with pytest.raises(FrozenInstanceError):
        page.items[0].name = "changed"
    import inspect
    assert "OFFSET" not in inspect.getsource(CurrentStateReadService).upper()


def test_ap_summary_and_page_keep_zero_client_inventory(service):
    publish_clients(service)
    rows = [
        ap_row(cycle_id="aps", mac="11:22:33:44:55:66", status_code=1, status_classification="online"),
        ap_row(cycle_id="aps", mac="22:33:44:55:66:77", status_code=0, status_classification="other"),
        ap_row(cycle_id="aps", mac="33:44:55:66:77:88", status_classification="unknown"),
    ]
    parent = cycle(kind="ap", cycle_id="aps", items_stored=3)
    service.repository.publish_cycle(parent, ap_rows=rows)
    summary = service.get_current_ap_summary(SITE, evaluated_at_utc=EVALUATED)
    assert (summary.ap_total, summary.online_count, summary.offline_count, summary.other_count, summary.unknown_count) == (3, 1, 0, 1, 1)
    page = service.list_current_aps(SITE, limit=2, evaluated_at_utc=EVALUATED)
    assert len(page.items) == 2 and page.next_cursor
    second = service.list_current_aps(SITE, limit=2, cursor=page.next_cursor, evaluated_at_utc=EVALUATED)
    assert [item.ap_mac for item in second.items] == ["33:44:55:66:77:88"]


def test_history_quality_never_merges_scope_hashes(service):
    first = publish_clients(service, cycle_id="one", started="2026-08-23T09:00:00.000Z")
    publish_clients(service, cycle_id="two", started="2026-08-23T09:30:00.000Z")
    other_json, other_hash = canonical_scope("client", SITE, ("OtherSSID",))
    other = replace(
        cycle(cycle_id="other-scope", started="2026-08-23T09:45:00.000Z"),
        source_scope_json=other_json,
        source_scope_hash=other_hash,
    )
    service.repository.publish_cycle(other)
    quality = service.get_client_history_quality(
        SITE, "2026-08-23T09:00:00.000Z", "2026-08-23T10:00:00.000Z", source_scope_hash=first.source_scope_hash,
    )
    assert quality.complete_cycle_count == 2
    assert quality.scope_changed is True
    assert quality.retention_pressure is False
    assert quality.coverage_status == "incompatible_scope"


def test_history_quality_reports_retention_pressure_over_cap_with_protected_cycle(service):
    current = publish_clients(service)
    pressure_config = replace(
        service.config,
        history_max_client_rows=1,
    )
    pressure_repository = CurrentStateRepository(pressure_config)
    cleanup_result = CurrentStateCleanup(pressure_repository, pressure_config).run_once(
        now_utc="2026-08-23T10:00:30.000Z",
    )
    assert cleanup_result.retention_pressure is True
    assert pressure_repository.get_cycle(current.cycle_id) is not None
    pressure_service = CurrentStateReadService(pressure_repository)

    quality = pressure_service.get_client_history_quality(
        SITE,
        "2026-08-23T09:00:00.000Z",
        "2026-08-23T10:00:00.000Z",
        source_scope_hash=current.source_scope_hash,
    )

    assert quality.complete_cycle_count == 1
    assert quality.retention_pressure is True


@pytest.mark.parametrize("source_scope_hash", ["A" * 64, "g" * 64, "a" * 63, "a" * 65])
def test_history_quality_rejects_noncanonical_scope_hash(service, source_scope_hash):
    with pytest.raises(CurrentStateValidationError, match="source_scope_hash is invalid"):
        service.get_client_history_quality(
            SITE,
            "2026-08-23T09:00:00.000Z",
            "2026-08-23T10:00:00.000Z",
            source_scope_hash=source_scope_hash,
        )
