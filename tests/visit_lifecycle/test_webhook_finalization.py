from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pytest

from app.visit_lifecycle.webhook_reader import VisitLifecycleWebhookReader

from .conftest import config_with, make_request


NOW = "2026-08-13T10:06:00.000Z"
MAC = "02:11:22:33:44:55"


class CapturingTelemetry:
    def __init__(self):
        self.events = []

    def emit(self, event, level="info", **fields):
        self.events.append((event, level, fields))
        return True


def _record(event_id="webhook:0", **changes):
    value = {
        "event": "omada.client_offline",
        "normalized_event_id": event_id,
        "site_id": "site-a",
        "site_resolution_status": "resolved",
        "client_mac": MAC,
        "controller_timestamp": "2026-08-13T10:05:00.000Z",
        "received_at": "2026-08-13T10:05:01.000Z",
        "client_ip": "192.0.2.20",
        "ssid": "Zefer_Parki",
        "ap_mac": "02:FF:EE:DD:CC:BB",
        "reported_connected_seconds": 300,
        "reported_traffic_bytes_estimate": 123456,
    }
    value.update(changes)
    return value


def _write(path, *records):
    with open(path, "w", encoding="utf-8", newline="") as output:
        for record in records:
            output.write(json.dumps(record, separators=(",", ":")) + "\n")


def _reader(config, repository, service, telemetry=None, now=NOW):
    return VisitLifecycleWebhookReader(
        config=config,
        repository=repository,
        service=service,
        telemetry=telemetry or CapturingTelemetry(),
        now_factory=lambda: now,
    )


def _source(repository, event_id):
    with repository._connect(readonly=True) as connection:  # noqa: SLF001
        return connection.execute(
            "SELECT * FROM visit_source_events WHERE event_id=?",
            (event_id,),
        ).fetchone()


def test_resolved_offline_closes_exact_site_mac_with_reported_context(
    visit_config,
    visit_repository,
    visit_service,
):
    opened = visit_service.submit_authorized(make_request())
    _write(visit_config.webhook_source, _record())

    assert _reader(
        visit_config, visit_repository, visit_service
    ).scan_once() is True

    visit = visit_repository.get_visit("site-a", opened.visit_id)
    assert visit.status == "closed"
    assert visit.closed_at == "2026-08-13T10:05:00.000Z"
    assert visit.close_time_source == "controller"
    assert visit.duration_seconds == 300
    assert visit.final_ip == "192.0.2.20"
    assert visit.final_ssid == "Zefer_Parki"
    assert visit.final_ap_mac == "02:FF:EE:DD:CC:BB"
    assert visit.reported_connected_seconds == 300
    assert visit.reported_traffic_total_bytes == 123456
    assert visit.reported_traffic_up_bytes is None
    assert visit.reported_traffic_down_bytes is None
    source = _source(visit_repository, "webhook:0")
    assert source["processing_result"] == "closed"
    assert source["visit_id"] == opened.visit_id
    assert source["client_ip"] == "192.0.2.20"
    assert source["ssid"] == "Zefer_Parki"
    assert source["ap_mac"] == "02:FF:EE:DD:CC:BB"


@pytest.mark.parametrize(
    "status",
    ["site_missing", "site_unresolved", "mapping_invalid"],
)
def test_unresolved_site_is_invalid_and_never_pending_or_closed(
    visit_config,
    visit_repository,
    visit_service,
    status,
):
    opened = visit_service.submit_authorized(make_request())
    _write(
        visit_config.webhook_source,
        _record(site_id=None, site_resolution_status=status),
    )
    _reader(visit_config, visit_repository, visit_service).scan_once()

    assert visit_repository.get_visit("site-a", opened.visit_id).status == "open"
    source = _source(visit_repository, "webhook:0")
    assert source["processing_result"] == "invalid"
    assert source["reason"] == "site_unresolved"
    assert source["pending_until"] is None


def test_same_mac_other_site_is_untouched_and_pending_is_site_scoped(
    visit_config,
    visit_repository,
    visit_service,
):
    opened = visit_service.submit_authorized(make_request(site_id="site-a"))
    _write(visit_config.webhook_source, _record(site_id="site-b"))
    _reader(visit_config, visit_repository, visit_service).scan_once()

    assert visit_repository.get_visit("site-a", opened.visit_id).status == "open"
    source = _source(visit_repository, "webhook:0")
    assert source["processing_result"] == "pending_match"
    assert source["site_id"] == "site-b"


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"ssid": "Other_Network"}, "ssid_changed"),
        ({"controller_timestamp": "2026-08-13T09:50:00.000Z"},
         "stale_or_ambiguous"),
        ({"reported_connected_seconds": 1800}, "stale_or_ambiguous"),
    ],
)
def test_safeguard_rejections_are_durable_unmatched(
    visit_config,
    visit_repository,
    visit_service,
    changes,
    reason,
):
    opened = visit_service.submit_authorized(make_request())
    _write(visit_config.webhook_source, _record(**changes))
    _reader(visit_config, visit_repository, visit_service).scan_once()

    assert visit_repository.get_visit("site-a", opened.visit_id).status == "open"
    source = _source(visit_repository, "webhook:0")
    assert source["processing_result"] == "unmatched"
    assert source["reason"] == reason


def test_received_clock_fallback_never_applies_reported_duration_drift(
    visit_config,
    visit_repository,
    visit_service,
):
    opened = visit_service.submit_authorized(make_request())
    _write(
        visit_config.webhook_source,
        _record(
            controller_timestamp="2026-08-13T09:59:30.000Z",
            reported_connected_seconds=999999,
        ),
    )
    _reader(visit_config, visit_repository, visit_service).scan_once()

    visit = visit_repository.get_visit("site-a", opened.visit_id)
    assert visit.status == "closed"
    assert visit.closed_at == "2026-08-13T10:05:01.000Z"
    assert visit.close_time_source == "received_clock_fallback"
    assert visit.reported_connected_seconds == 999999


def test_duplicate_event_is_idempotent_and_checkpoint_advances(
    visit_config,
    visit_repository,
    visit_service,
):
    telemetry = CapturingTelemetry()
    opened = visit_service.submit_authorized(make_request())
    _write(visit_config.webhook_source, _record(), _record())
    _reader(
        visit_config, visit_repository, visit_service, telemetry
    ).scan_once()

    with visit_repository._connect(readonly=True) as connection:  # noqa: SLF001
        assert connection.execute(
            "SELECT COUNT(*) FROM visit_source_events"
        ).fetchone()[0] == 1
        state = connection.execute(
            "SELECT source_offset FROM visit_reader_state"
        ).fetchone()[0]
    assert state == os.path.getsize(visit_config.webhook_source)
    assert visit_repository.get_visit("site-a", opened.visit_id).status == "closed"


def test_pending_recheck_uses_only_durable_context_after_journal_disappears(
    visit_config,
    visit_repository,
    visit_service,
    monkeypatch,
):
    _write(visit_config.webhook_source, _record(ssid="Other_Network"))
    first = _reader(
        visit_config,
        visit_repository,
        visit_service,
        now="2026-08-13T10:00:01.000Z",
    )
    first.scan_once()
    pending = _source(visit_repository, "webhook:0")
    assert pending["processing_result"] == "pending_match"
    original_deadline = pending["pending_until"]

    os.unlink(visit_config.webhook_source)
    monkeypatch.setattr(
        "app.visit_lifecycle.service.utc_now",
        lambda: "2026-08-13T10:00:02.000Z",
    )
    opened = visit_service.submit_authorized(make_request())
    restarted = _reader(
        visit_config,
        visit_repository,
        visit_service,
        now="2026-08-13T10:00:02.000Z",
    )
    restarted.scan_once()

    source = _source(visit_repository, "webhook:0")
    assert source["processing_result"] == "unmatched"
    assert source["reason"] == "ssid_changed"
    assert source["pending_until"] == original_deadline
    assert visit_repository.get_visit("site-a", opened.visit_id).status == "open"


@pytest.mark.parametrize(
    ("reported_seconds", "expected_result", "expected_reason"),
    [
        (300, "closed", None),
        (1800, "unmatched", "stale_or_ambiguous"),
    ],
)
def test_pending_restart_rechecks_durable_duration_and_can_close(
    visit_config,
    visit_repository,
    visit_service,
    monkeypatch,
    reported_seconds,
    expected_result,
    expected_reason,
):
    _write(
        visit_config.webhook_source,
        _record(reported_connected_seconds=reported_seconds),
    )
    _reader(
        visit_config,
        visit_repository,
        visit_service,
        now="2026-08-13T10:00:01.000Z",
    ).scan_once()
    assert _source(visit_repository, "webhook:0")["processing_result"] == (
        "pending_match"
    )
    os.unlink(visit_config.webhook_source)
    monkeypatch.setattr(
        "app.visit_lifecycle.service.utc_now",
        lambda: "2026-08-13T10:00:02.000Z",
    )
    opened = visit_service.submit_authorized(make_request())

    _reader(
        visit_config,
        visit_repository,
        visit_service,
        now="2026-08-13T10:00:03.000Z",
    ).scan_once()

    source = _source(visit_repository, "webhook:0")
    assert source["processing_result"] == expected_result
    assert source["reason"] == expected_reason
    visit = visit_repository.get_visit("site-a", opened.visit_id)
    assert visit.status == ("closed" if expected_result == "closed" else "open")
    if expected_result == "closed":
        assert visit.reported_connected_seconds == reported_seconds


def test_pending_deadline_is_absolute_and_never_reconstructs_visit(
    visit_config,
    visit_repository,
    visit_service,
):
    _write(visit_config.webhook_source, _record())
    _reader(
        visit_config,
        visit_repository,
        visit_service,
        now="2026-08-13T10:00:00.000Z",
    ).scan_once()
    pending = _source(visit_repository, "webhook:0")
    assert pending["pending_until"] == "2026-08-13T10:00:30.000Z"

    os.unlink(visit_config.webhook_source)
    changed = config_with(visit_config, offline_match_grace_seconds=900)
    _reader(
        changed,
        visit_repository,
        visit_service,
        now="2026-08-13T10:00:31.000Z",
    ).scan_once()
    final = _source(visit_repository, "webhook:0")
    assert final["processing_result"] == "unmatched"
    assert final["reason"] == "no_open_visit"
    with visit_repository._connect(readonly=True) as connection:  # noqa: SLF001
        assert connection.execute("SELECT COUNT(*) FROM visits").fetchone()[0] == 0


def test_old_offline_cannot_close_later_new_visit(
    visit_config,
    visit_repository,
    visit_service,
    monkeypatch,
):
    _write(
        visit_config.webhook_source,
        _record(
            controller_timestamp="2026-08-13T10:00:30.000Z",
            received_at="2026-08-13T10:00:31.000Z",
            reported_connected_seconds=30,
        ),
    )
    _reader(
        visit_config,
        visit_repository,
        visit_service,
        now="2026-08-13T10:00:00.000Z",
    ).scan_once()
    monkeypatch.setattr(
        "app.visit_lifecycle.service.utc_now",
        lambda: "2026-08-13T10:00:01.000Z",
    )
    opened = visit_service.submit_authorized(make_request(
        authorized_at=datetime(2026, 8, 13, 10, 1, tzinfo=timezone.utc),
    ))
    os.unlink(visit_config.webhook_source)
    _reader(
        visit_config,
        visit_repository,
        visit_service,
        now="2026-08-13T10:00:02.000Z",
    ).scan_once()
    assert visit_repository.get_visit("site-a", opened.visit_id).status == "open"
    assert _source(visit_repository, "webhook:0")["reason"] == (
        "stale_or_ambiguous"
    )
