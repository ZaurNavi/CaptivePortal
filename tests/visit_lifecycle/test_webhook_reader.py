from __future__ import annotations

import json
import os
import sqlite3

import pytest

from app.visit_lifecycle import webhook_reader as reader_module
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
    return value


def _line(value):
    return json.dumps(value, separators=(",", ":")) + "\n"


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
    assert calls == [{"now_utc": NOW}]


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
