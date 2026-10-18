from __future__ import annotations

import json
import os
import sqlite3
import threading

import pytest

from app.visit_lifecycle import (
    VisitLifecycleService,
    VisitRepository,
    VisitStorageCategory,
    VisitStorageError,
    VisitWriterContention,
    webhook_reader as reader_module,
)
from app.visit_lifecycle.repository import (
    WRITE_OPERATION_READER,
    WRITE_OPERATION_START,
)
from app.visit_lifecycle.webhook_reader import VisitLifecycleWebhookReader

from .conftest import config_with


NOW = "2026-08-13T10:06:00.000Z"


class CapturingTelemetry:
    def __init__(self):
        self.events = []

    def emit(self, event, level="info", **fields):
        self.events.append((event, level, fields))
        return True


def _offline(event_id, **changes):
    value = {
        "event": "omada.client_offline",
        "normalized_event_id": event_id,
        "site_id": "site-a",
        "site_resolution_status": "resolved",
        "client_mac": "02:11:22:33:44:55",
        "controller_timestamp": "2026-08-13T10:05:00.000Z",
        "received_at": "2026-08-13T10:05:01.000Z",
    }
    value.update(changes)
    value.setdefault("raw_text", (
        f'[client:Lab:{value.get("client_mac") or "02:11:22:33:44:55"}] '
        f'(IP: {value.get("client_ip") or "192.0.2.1"}) '
        f'went offline from SSID "{value.get("ssid") or "Lab"}" '
        f'on [ap:Lab:{value.get("ap_mac") or "02:AA:BB:CC:DD:01"}] '
        f'({value.get("reported_connected_seconds", 60)}s connected, '
        f'{value.get("reported_traffic_bytes_estimate", 1234)}B).'
    ))
    return value


def _line(value):
    return json.dumps(value, separators=(",", ":")) + "\n"


@pytest.mark.parametrize("mutation", ["missing-raw", "not-text", "client-name-only", "ap-name-only",
    "ssid-only", "failed-connect", "conflicting-verb", "wrong-client", "wrong-ap", "wrong-ssid",
    "wrong-duration", "wrong-traffic", "wrong-ip", "unclassified-status"])
def test_context230_reader_rejects_false_or_mismatched_legacy_offline_provenance(mutation):
    record = _offline("legacy:0")
    if mutation == "missing-raw":
        record.pop("raw_text")
    elif mutation == "not-text":
        record["raw_text"] = {"event": "went offline"}
    elif mutation in {"client-name-only", "ap-name-only", "ssid-only", "failed-connect"}:
        client = "Guest went offline" if mutation in {"client-name-only", "failed-connect"} else "Guest"
        ap = "AP went offline" if mutation == "ap-name-only" else "AP"
        ssid = "Lab went offline" if mutation == "ssid-only" else "Lab"
        clause = "failed to connect to" if mutation == "failed-connect" else "associated with"
        record["raw_text"] = (f'[client:{client}:02:11:22:33:44:55] {clause} '
            f'[ap:{ap}:02:AA:BB:CC:DD:01] with SSID "{ssid}" '
            'on channel 6 because the password was wrong.(1 time in the last minute)')
    elif mutation == "conflicting-verb":
        record["raw_text"] += " went online"
    else:
        key, value = {
            "wrong-client": ("client_mac", "02:11:22:33:44:99"),
            "wrong-ap": ("ap_mac", "02:AA:BB:CC:DD:99"),
            "wrong-ssid": ("ssid", "Not-Lab"),
            "wrong-duration": ("reported_connected_seconds", 300),
            "wrong-traffic": ("reported_traffic_bytes_estimate", 9876),
            "wrong-ip": ("client_ip", "192.0.2.99"),
            "unclassified-status": ("parse_status", "unclassified"),
        }[mutation]
        record[key] = value
    evidence = reader_module._offline_evidence(record)
    assert evidence is None or evidence.invalid_reason is not None


@pytest.mark.parametrize("parse_status", ["parsed", "partial", None])
def test_context230_legacy_reader_accepts_raw_proof_not_parse_status(parse_status):
    record = _offline("legacy:0", parse_status=parse_status)
    evidence = reader_module._offline_evidence(record)
    assert evidence.invalid_reason is None
    assert evidence.client_mac == "02:11:22:33:44:55"
    assert evidence.event_id == "legacy:0"


def test_context230_legacy_jsonl_invalid_proof_advances_checkpoint_without_business_evidence(
    visit_config, visit_repository, visit_service,
):
    source = visit_config.webhook_source
    valid = _offline("legacy:valid", parse_status="partial")
    unsupported = _offline("legacy:unsupported", raw_text="went offline")
    missing = _offline("legacy:missing")
    missing.pop("raw_text")
    for record in (unsupported, valid, missing, valid):
        _append(source, record)
    reader = _reader(visit_config, visit_repository, visit_service)
    assert reader.scan_once() is True
    assert _event_count(visit_repository) == 1
    assert _state(visit_repository).source_offset == os.path.getsize(source)
    assert reader.scan_once() is True
    assert _event_count(visit_repository) == 1


def _append(path, value):
    with open(path, "a", encoding="utf-8", newline="") as output:
        output.write(value if isinstance(value, str) else _line(value))


def _reader(config, repository, service, telemetry=None):
    return VisitLifecycleWebhookReader(
        config=config,
        repository=repository,
        service=service,
        telemetry=telemetry or CapturingTelemetry(),
        now_factory=lambda: NOW,
    )


def _event_count(repository):
    with repository._connect(readonly=True) as connection:  # noqa: SLF001
        return connection.execute(
            "SELECT COUNT(*) FROM visit_source_events"
        ).fetchone()[0]


def _state(repository):
    states = repository.get_reader_states()
    assert len(states) == 1
    return next(iter(states.values()))


def test_missing_journal_is_safe_and_pending_recheck_still_runs(
    visit_config,
    visit_repository,
    visit_service,
    monkeypatch,
):
    calls = []
    monkeypatch.setattr(
        visit_service,
        "retry_pending",
        lambda **kwargs: calls.append(kwargs) or 0,
    )
    assert _reader(
        visit_config, visit_repository, visit_service
    ).scan_once() is True
    assert len(calls) == 1
    assert calls[0]["now_utc"] == NOW
    assert isinstance(calls[0]["deadline"], float)
    assert isinstance(calls[0]["cancel_event"], threading.Event)
    assert callable(calls[0]["on_committed_progress"])


def test_busy_reader_preserves_checkpoint_and_recovers_next_scan(visit_config):
    config = config_with(visit_config, reader_writer_slot_wait_ms=25)
    repository = VisitRepository(config)
    repository.initialize()
    telemetry = CapturingTelemetry()
    service = VisitLifecycleService(repository, telemetry)
    health = []
    reader = VisitLifecycleWebhookReader(
        config=config,
        repository=repository,
        service=service,
        telemetry=telemetry,
        now_factory=lambda: NOW,
        health_callback=health.append,
    )
    _append(config.webhook_source, _offline("event:busy-reader"))
    holder_ready = threading.Event()
    release_holder = threading.Event()

    def hold_writer():
        with repository._bounded_write(WRITE_OPERATION_READER):  # noqa: SLF001
            holder_ready.set()
            release_holder.wait(2)

    holder = threading.Thread(target=hold_writer)
    holder.start()
    assert holder_ready.wait(1)
    assert reader.scan_once() is False
    assert repository.get_reader_states() == {}
    assert _event_count(repository) == 0
    failed = [item for item in telemetry.events if item[0] == "visit.reader_scan_failed"]
    assert len(failed) == 1
    assert failed[0][2]["operation"] == "reader"
    assert failed[0][2]["storage_category"] == "busy"
    assert failed[0][2]["retry_exhausted"] is False
    assert health == [False]
    release_holder.set()
    holder.join(1)

    assert reader.scan_once() is True
    assert _event_count(repository) == 1
    assert _state(repository).source_offset == os.path.getsize(
        config.webhook_source
    )
    assert health == [False, True]


def test_foreground_deferral_is_not_immediate_failure_or_health_degradation(
    visit_config,
):
    config = config_with(visit_config, reader_writer_slot_wait_ms=25)
    repository = VisitRepository(config)
    repository.initialize()
    telemetry = CapturingTelemetry()
    service = VisitLifecycleService(repository, telemetry)
    health = []
    reader = VisitLifecycleWebhookReader(
        config=config,
        repository=repository,
        service=service,
        telemetry=telemetry,
        now_factory=lambda: NOW,
        health_callback=health.append,
    )
    _append(config.webhook_source, _offline("event:foreground-deferred"))
    holder_ready = threading.Event()
    release_holder = threading.Event()

    def hold_start():
        with repository._bounded_write(WRITE_OPERATION_START):  # noqa: SLF001
            holder_ready.set()
            release_holder.wait(2)

    holder = threading.Thread(target=hold_start)
    holder.start()
    assert holder_ready.wait(1)
    assert reader.scan_once() is False
    assert health == []
    assert repository.get_reader_states() == {}
    assert not [event for event in telemetry.events if event[0] == "visit.reader_scan_failed"]
    deferred = [event for event in telemetry.events if event[0] == "visit.reader_scan_deferred"]
    assert len(deferred) == 1
    assert deferred[0][2]["contention_layer"] == "coordinator"
    assert deferred[0][2]["holder_operation"] == "start"

    release_holder.set()
    holder.join(1)
    assert reader.scan_once() is True
    assert health == [True]
    assert _event_count(repository) == 1


def test_continuous_expected_deferral_degrades_once_and_success_recovers(
    visit_config,
    visit_repository,
    visit_service,
):
    class Clock:
        value = 0.0

        def __call__(self):
            return self.value

    clock = Clock()
    telemetry = CapturingTelemetry()
    health = []
    reader = VisitLifecycleWebhookReader(
        config=visit_config,
        repository=visit_repository,
        service=visit_service,
        telemetry=telemetry,
        now_factory=lambda: NOW,
        monotonic=clock,
        health_callback=health.append,
    )
    error = VisitStorageError(
        VisitStorageCategory.BUSY,
        operation="reader_line",
        lock_wait_ms=250,
        contention_layer="coordinator",
        contention=VisitWriterContention(
            holder_operation="start",
            holder_age_ms=250,
            foreground_queue_depth=1,
            background_queue_depth=1,
            waiter_operation="reader_line",
            waiter_wait_ms=250,
        ),
    )
    assert reader._record_expected_deferral(  # noqa: SLF001
        error, started=0.0, processed=0
    ) is False
    clock.value = 30.001
    reader._record_expected_deferral(error, started=30.0, processed=0)  # noqa: SLF001
    clock.value = 35.0
    reader._record_expected_deferral(error, started=35.0, processed=0)  # noqa: SLF001
    failed = [event for event in telemetry.events if event[0] == "visit.reader_scan_failed"]
    assert len(failed) == 1
    assert failed[0][2]["reason"] == "writer_starvation"
    assert health == [False]

    assert reader.scan_once() is True
    assert health == [False, True]
    assert reader._deferral_started_at is None  # noqa: SLF001


def test_quiet_journal_remains_healthy_without_checkpoint_movement(
    visit_config,
    visit_repository,
    visit_service,
):
    health = []
    reader = VisitLifecycleWebhookReader(
        config=visit_config,
        repository=visit_repository,
        service=visit_service,
        telemetry=CapturingTelemetry(),
        now_factory=lambda: NOW,
        health_callback=health.append,
    )
    assert reader.scan_once() is True
    assert reader.scan_once() is True
    assert health == [True, True]


def test_malformed_unrelated_and_missing_event_id_advance_checkpoint_safely(
    visit_config,
    visit_repository,
    visit_service,
):
    _append(visit_config.webhook_source, "{not-json}\n")
    _append(visit_config.webhook_source, {"event": "omada.client_online"})
    _append(
        visit_config.webhook_source,
        _offline(None, normalized_event_id=None),
    )
    reader = _reader(visit_config, visit_repository, visit_service)
    assert reader.scan_once() is True
    assert _event_count(visit_repository) == 0
    assert _state(visit_repository).source_offset == os.path.getsize(
        visit_config.webhook_source
    )


@pytest.mark.parametrize(
    "bad_json",
    [
        '{"event":"omada.client_offline","event":"duplicate"}\n',
        '{"value":NaN}\n',
        '[]\n',
    ],
)
def test_strict_json_rejections_advance_without_source_event(
    visit_config,
    visit_repository,
    visit_service,
    bad_json,
):
    _append(visit_config.webhook_source, bad_json)
    assert _reader(
        visit_config, visit_repository, visit_service
    ).scan_once() is True
    assert _event_count(visit_repository) == 0
    assert _state(visit_repository).source_offset == len(
        bad_json.encode("utf-8")
    )


def test_bounded_lines_resume_from_persisted_checkpoint(
    visit_config,
    visit_repository,
    visit_service,
):
    config = config_with(visit_config, reader_max_lines_per_scan=1)
    _append(config.webhook_source, {"event": "omada.client_online"})
    first_size = os.path.getsize(config.webhook_source)
    _append(config.webhook_source, _offline("event:1"))
    reader = _reader(config, visit_repository, visit_service)

    assert reader.scan_once() is False
    assert _state(visit_repository).source_offset == first_size
    assert _event_count(visit_repository) == 0
    assert reader.scan_once() is True
    assert _event_count(visit_repository) == 1
    assert _state(visit_repository).source_offset == os.path.getsize(
        config.webhook_source
    )


def test_oversized_complete_line_is_skipped_and_next_line_is_processed(
    visit_config,
    visit_repository,
    visit_service,
):
    config = config_with(visit_config, max_line_bytes=512)
    _append(config.webhook_source, "x" * 600 + "\n")
    _append(config.webhook_source, _offline("event:1"))
    assert _reader(config, visit_repository, visit_service).scan_once() is True
    assert _event_count(visit_repository) == 1


def test_strict_rotated_names_and_oldest_first_order(
    visit_config,
    visit_repository,
    visit_service,
):
    base = visit_config.webhook_source
    _append(base + ".2", _offline("event:2"))
    _append(base + ".1", _offline("event:1"))
    _append(base, _offline("event:0"))
    for suffix in (".tmp", ".11", ".1.gz", ".bak"):
        _append(base + suffix, _offline(f"ignored{suffix}"))

    _reader(visit_config, visit_repository, visit_service).scan_once()
    with visit_repository._connect(readonly=True) as connection:  # noqa: SLF001
        ids = {
            row[0]
            for row in connection.execute(
                "SELECT event_id FROM visit_source_events"
            )
        }
    assert ids == {"event:0", "event:1", "event:2"}


def test_nonregular_candidate_is_ignored(
    visit_config,
    visit_repository,
    visit_service,
):
    os.mkdir(visit_config.webhook_source)
    assert _reader(
        visit_config, visit_repository, visit_service
    ).scan_once() is True
    assert visit_repository.get_reader_states() == {}


def test_retired_inode_identity_reused_by_active_resets_before_reading(
    visit_config,
    visit_repository,
    visit_service,
    monkeypatch,
):
    monkeypatch.setattr(
        reader_module,
        "_source_identity",
        lambda _stat: "fixed:identity",
    )
    rotated = visit_config.webhook_source + ".1"
    _append(rotated, {"event": "omada.client_online", "padding": "old"})
    reader = _reader(visit_config, visit_repository, visit_service)
    reader.scan_once()
    assert _state(visit_repository).retired_completed is True

    os.unlink(rotated)
    _append(visit_config.webhook_source, _offline("new:0"))
    reader.scan_once()
    assert _event_count(visit_repository) == 1
    assert _state(visit_repository).retired_completed is False


def test_truncate_fast_regrow_above_old_offset_restarts_at_zero(
    visit_config,
    visit_repository,
    visit_service,
):
    path = visit_config.webhook_source
    _append(path, {"event": "omada.client_online", "padding": "a" * 50})
    reader = _reader(visit_config, visit_repository, visit_service)
    reader.scan_once()
    old_offset = _state(visit_repository).source_offset

    replacement = _line(_offline("new:0", padding="b" * old_offset))
    with open(path, "w", encoding="utf-8", newline="") as output:
        output.write(replacement)
    assert os.path.getsize(path) > old_offset
    reader.scan_once()

    assert _event_count(visit_repository) == 1
    with visit_repository._connect(readonly=True) as connection:  # noqa: SLF001
        assert connection.execute(
            "SELECT event_id FROM visit_source_events"
        ).fetchone()[0] == "new:0"


def test_incomplete_rotated_file_disappearance_warns_once(
    visit_config,
    visit_repository,
    visit_service,
):
    telemetry = CapturingTelemetry()
    path = visit_config.webhook_source
    _append(path, '{"event":"omada.client_offline"')
    reader = _reader(visit_config, visit_repository, visit_service, telemetry)
    assert reader.scan_once() is False
    os.replace(path, path + ".1")
    assert reader.scan_once() is False
    os.unlink(path + ".1")
    reader.scan_once()
    reader.scan_once()

    warnings = [
        event for event in telemetry.events
        if event[0] == "visit.reader_source_missing"
    ]
    assert len(warnings) == 1
    assert _state(visit_repository).missing_warning_emitted is True


def test_storage_failure_rolls_back_event_and_checkpoint_then_replays(
    visit_config,
    visit_repository,
    visit_service,
    monkeypatch,
):
    _append(visit_config.webhook_source, _offline("event:0"))
    original = visit_repository._upsert_reader_progress  # noqa: SLF001

    def fail_after_event(*args, **kwargs):
        raise sqlite3.OperationalError("injected checkpoint failure")

    monkeypatch.setattr(
        visit_repository,
        "_upsert_reader_progress",
        fail_after_event,
    )
    reader = _reader(visit_config, visit_repository, visit_service)
    assert reader.scan_once() is False
    assert _event_count(visit_repository) == 0
    assert visit_repository.get_reader_states() == {}

    monkeypatch.setattr(
        visit_repository,
        "_upsert_reader_progress",
        original,
    )
    assert reader.scan_once() is True
    assert _event_count(visit_repository) == 1
