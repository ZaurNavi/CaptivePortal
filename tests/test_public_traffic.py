import json
import logging
import os
import sqlite3
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import run as run_module
from tests.settings_control import CONTROLLER_BASE

from app.portal_counter import (
    PortalCounterRepository,
    PortalCounterService,
)
from app.public_traffic.cli import main as cli_main
from app.public_traffic.models import (
    INT64_MAX,
    BackfillIncompleteError,
    PublicTrafficConfig,
    PublicTrafficConfigError,
    TrafficEvent,
)
from app.public_traffic.reader import PublicTrafficReader
from app.public_traffic import reader as traffic_reader_module
from app.public_traffic.repository import PublicTrafficRepository
from app.public_traffic.service import (
    PublicTrafficService,
    format_traffic_bytes,
)
from app.public_traffic.worker import PublicTrafficWorker
from app.web import web as web_module


UTC = timezone.utc
NOW = datetime(2026, 7, 29, 8, 0, tzinfo=UTC)


class MutableClock:
    def __init__(self, value=NOW):
        self.value = value

    def __call__(self):
        return self.value


def config(tmp_path, **overrides):
    values = {
        "public_traffic_counter_enabled": True,
        "public_traffic_ssid": "Zefer_Parki",
        "public_traffic_db_path": str(tmp_path / "traffic.db"),
        "omada_webhook_normalized_log_file": str(
            tmp_path / "normalized.log"
        ),
        "portal_counter_timezone": "Asia/Baku",
        "public_traffic_scan_interval_seconds": 10,
        "public_traffic_frontend_refresh_seconds": 60,
    }
    values.update(overrides)
    return PublicTrafficConfig.from_settings(values)


def stack(tmp_path, **overrides):
    selected_config = config(tmp_path, **overrides)
    repository = PublicTrafficRepository(selected_config.db_path)
    clock = MutableClock()
    logger = logging.getLogger(f"public-traffic-{id(tmp_path)}")
    service = PublicTrafficService(
        config=selected_config,
        repository=repository,
        logger=logger,
        clock=clock,
    )
    assert service.initialize()
    reader = PublicTrafficReader(
        source_path=selected_config.source_log_path,
        repository=repository,
        service=service,
        logger=logger,
    )
    worker = PublicTrafficWorker(
        reader=reader,
        repository=repository,
        service=service,
        logger=logger,
        scan_interval_seconds=10,
    )
    return selected_config, repository, service, reader, worker, clock


def offline(
    event_id,
    *,
    ssid="Zefer_Parki",
    traffic=1024**3,
    parse_status="parsed",
    controller_timestamp="2026-07-29T07:30:00.000Z",
    received_at="2026-07-29T07:30:01.000Z",
):
    return {
        "event": "omada.client_offline",
        "normalized_event_id": event_id,
        "ssid": ssid,
        "reported_traffic_bytes_estimate": traffic,
        "parse_status": parse_status,
        "controller_timestamp": controller_timestamp,
        "received_at": received_at,
    }


def append_lines(path, records, *, newline=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as stream:
        for index, record in enumerate(records):
            if isinstance(record, bytes):
                encoded = record
            else:
                encoded = json.dumps(
                    record,
                    separators=(",", ":"),
                ).encode("utf-8")
            stream.write(encoded)
            if newline or index < len(records) - 1:
                stream.write(b"\n")


def table_rows(db_path, table):
    with closing(sqlite3.connect(db_path)) as connection:
        return connection.execute(
            f"SELECT * FROM {table}"
        ).fetchall()


def complete_backfill(worker):
    worker.run_once()
    assert worker.repository.initial_backfill_completed()


def _h1_retired(tmp_path):
    selected, repository, service, reader, worker, clock = stack(tmp_path)
    archive = Path(selected.source_log_path + ".1")
    append_lines(archive, [offline("h1-seed", traffic=7)])
    complete_backfill(worker)
    clock.value += timedelta(seconds=10)
    return archive, repository, service, reader, worker, clock


def _h1_trace(repository, monkeypatch):
    statements = []
    connect = repository._connect

    def traced_connect():
        connection = connect()
        connection.set_trace_callback(statements.append)
        return connection

    monkeypatch.setattr(repository, "_connect", traced_connect)
    return statements


def _h1_writes(statements):
    return [sql for sql in statements if "INSERT INTO reader_state" in sql]


def test_H1_C01_stable_retired_seven_fields_and_timestamp_unchanged(
    tmp_path, monkeypatch,
):
    _, repository, _, reader, _, _ = _h1_retired(tmp_path)
    before = table_rows(repository.db_path, "reader_state")
    daily = table_rows(repository.db_path, "traffic_daily")
    statements = _h1_trace(repository, monkeypatch)
    assert reader.scan() is True
    assert _h1_writes(statements) == []
    assert not any("UPDATE reader_state" in sql for sql in statements)
    assert statements.count("BEGIN IMMEDIATE") == 1
    assert statements.count("COMMIT") == 1
    assert table_rows(repository.db_path, "reader_state") == before
    assert table_rows(repository.db_path, "traffic_daily") == daily


def test_H1_C02_C03_active_and_new_archive_keep_legacy_writes(
    tmp_path, monkeypatch,
):
    selected, repository, _, reader, _, _ = stack(tmp_path)
    Path(selected.source_log_path).touch()
    Path(selected.source_log_path + ".1").touch()
    statements = _h1_trace(repository, monkeypatch)
    assert reader.scan()
    assert len(_h1_writes(statements)) == 2
    statements.clear()
    assert reader.scan()
    assert len(_h1_writes(statements)) == 1
    assert "retired_completed" in _h1_writes(statements)[0]


@pytest.mark.parametrize("field,value", [
    ("source_identity", "different-identity"),
    ("source_path", "different-path"),
    ("source_offset", 0),
    ("source_checkpoint", None),
    ("source_checkpoint", "0" * 64),
    ("last_observed_size", None),
    ("last_observed_size", 0),
    ("retired_completed", 0),
    ("missing_warning_emitted", 1),
    ("delete", None),
])
def test_H1_C14_current_row_not_scan_snapshot_authorizes_noop(
    tmp_path, monkeypatch, field, value,
):
    _, repository, _, reader, _, _ = _h1_retired(tmp_path)
    original = repository.observe_source

    def changed_before_begin(**kwargs):
        # Runs after scan's state read and EOF calculation, before writer lock.
        with closing(sqlite3.connect(repository.db_path)) as connection:
            if field == "delete":
                connection.execute("DELETE FROM reader_state")
            else:
                connection.execute(f"UPDATE reader_state SET {field} = ?", (value,))
            connection.commit()
        original(**kwargs)

    monkeypatch.setattr(repository, "observe_source", changed_before_begin)
    statements = _h1_trace(repository, monkeypatch)
    assert reader.scan()
    assert len(_h1_writes(statements)) == 1


def test_H1_C14_comparison_and_file_proof_hold_writer_lock(tmp_path, monkeypatch):
    _, repository, _, reader, _, _ = _h1_retired(tmp_path)
    original = traffic_reader_module._verify_stable_retired_eof
    checked = []

    def proof(*args):
        with closing(sqlite3.connect(repository.db_path, timeout=0)) as rival:
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                rival.execute("BEGIN IMMEDIATE")
        checked.append(True)
        return original(*args)

    monkeypatch.setattr(traffic_reader_module, "_verify_stable_retired_eof", proof)
    assert reader.scan()
    assert checked == [True]


def test_H1_C11_proof_uses_bound_descriptor_without_reopening_path(tmp_path, monkeypatch):
    _, repository, _, reader, _, _ = _h1_retired(tmp_path)
    original = traffic_reader_module._verify_stable_retired_eof

    def proof(*args):
        with patch.object(Path, "open", side_effect=AssertionError("must not reopen path")):
            return original(*args)

    monkeypatch.setattr(traffic_reader_module, "_verify_stable_retired_eof", proof)
    statements = _h1_trace(repository, monkeypatch)
    assert reader.scan()
    assert _h1_writes(statements) == []


def test_H1_C01_other_observe_call_keeps_default_legacy_behavior(tmp_path, monkeypatch):
    _, repository, service, _, _, _ = _h1_retired(tmp_path)
    state = next(iter(repository.get_reader_states().values()))
    statements = _h1_trace(repository, monkeypatch)
    repository.observe_source(
        source_identity=state.source_identity, source_path=state.source_path,
        source_offset=state.source_offset, source_checkpoint=state.source_checkpoint,
        observed_size=state.last_observed_size, retired_completed=True,
        now_utc=service.now_iso(),
    )
    assert len(_h1_writes(statements)) == 1
    assert table_rows(repository.db_path, "reader_state")[0][-1] == service.now_iso()


def test_H1_C04_retirement_transitions_are_not_suppressed(tmp_path, monkeypatch):
    archive, repository, _, reader, _, _ = _h1_retired(tmp_path)
    statements = _h1_trace(repository, monkeypatch)
    append_lines(archive, [b'{"event":"unrelated"}'], newline=False)
    assert reader.scan() is False
    assert len(_h1_writes(statements)) == 1
    assert not next(iter(repository.get_reader_states().values())).retired_completed
    with archive.open("ab") as stream:
        stream.write(b"\n")
    statements.clear()
    assert reader.scan()
    assert len(_h1_writes(statements)) == 2
    assert next(iter(repository.get_reader_states().values())).retired_completed


@pytest.mark.parametrize("records,extra_bytes,extra_sessions", [
    ([offline("h1-zero", traffic=0)], 0, 1),
    ([offline("h1-new", traffic=11)], 11, 1),
    ([offline("h1-seed", traffic=7)], 0, 0),
    ([b"not-json", b"\xff", {"event": "other"}, offline("bad", traffic=-1)], 0, 0),
    ([offline("other", ssid="Other", traffic=4)], 0, 0),
])
def test_H1_C05_C06_appends_advance_and_preserve_idempotency(
    tmp_path, records, extra_bytes, extra_sessions,
):
    archive, repository, service, reader, _, _ = _h1_retired(tmp_path)
    append_lines(archive, records)
    assert reader.scan()
    snapshot = service.get_snapshot()
    assert snapshot.total_bytes == 7 + extra_bytes
    assert snapshot.completed_sessions_total == 1 + extra_sessions
    state = next(iter(repository.get_reader_states().values()))
    assert state.source_offset == state.last_observed_size == archive.stat().st_size
    before = table_rows(repository.db_path, "processed_events")
    assert reader.scan()
    assert table_rows(repository.db_path, "processed_events") == before


def test_H1_C07_C15_partial_archive_does_not_complete_global_scan(tmp_path, monkeypatch):
    archive, repository, _, reader, _, _ = _h1_retired(tmp_path)
    other = Path(str(archive)[:-1] + "2")
    append_lines(other, [offline("partial")], newline=False)
    statements = _h1_trace(repository, monkeypatch)
    assert reader.scan() is False
    assert len(_h1_writes(statements)) == 1
    assert any(state.retired_completed for state in repository.get_reader_states().values())
    statements.clear()
    assert reader.scan() is False
    assert len(_h1_writes(statements)) == 1
    with other.open("ab") as stream:
        stream.write(b"\n")
    assert reader.scan()


@pytest.mark.parametrize("operation", ["same_size", "truncate", "replace", "rotate"])
def test_H1_C08_C10_C11_C16_rewrite_and_rotation_recovery(tmp_path, operation):
    archive, repository, service, reader, _, _ = _h1_retired(tmp_path)
    replacement = archive.read_bytes().replace(b"h1-seed", b"h1-next").replace(
        b'"reported_traffic_bytes_estimate":7', b'"reported_traffic_bytes_estimate":9',
    )
    if operation == "truncate":
        archive.write_bytes(b"")
        assert reader.scan()
    if operation in ("replace", "rotate"):
        archive.rename(Path(str(archive) + ".saved"))
    archive.write_bytes(replacement)
    assert reader.scan()
    assert service.get_snapshot().total_bytes == 16
    assert service.get_snapshot().completed_sessions_total == 2
    assert all(state.retired_completed for state in repository.get_reader_states().values())


def test_H1_C09_middle_only_rewrite_is_existing_bounded_checkpoint_limit(tmp_path, monkeypatch):
    archive, repository, _, reader, _, _ = _h1_retired(tmp_path)
    archive.write_bytes(b" " * 10000 + b"\n")
    assert reader.scan()
    before = table_rows(repository.db_path, "reader_state")
    with archive.open("r+b") as stream:
        stream.seek(5000)
        stream.write(b"x")
    statements = _h1_trace(repository, monkeypatch)
    assert reader.scan()
    assert _h1_writes(statements) == []
    assert table_rows(repository.db_path, "reader_state") == before


@pytest.mark.parametrize("when", ["before", "during", "after"])
def test_H1_C12_append_at_final_proof_reconciles_next_scan(tmp_path, monkeypatch, when):
    archive, repository, service, reader, _, _ = _h1_retired(tmp_path)
    original = traffic_reader_module._verify_stable_retired_eof
    checkpoint = traffic_reader_module._source_checkpoint
    injected = []

    def append_once():
        if not injected:
            append_lines(archive, [offline("h1-race", traffic=3)])
            injected.append(True)

    def proof(*args):
        if when == "before":
            append_once()
        result = original(*args)
        if when == "after":
            append_once()
        return result

    def changing_checkpoint(stream, offset):
        result = checkpoint(stream, offset)
        if when == "during" and injected == ["armed"]:
            injected.clear()
            append_once()
        return result

    def armed_proof(*args):
        if when == "during":
            injected.append("armed")
        return proof(*args)

    monkeypatch.setattr(traffic_reader_module, "_verify_stable_retired_eof", armed_proof)
    monkeypatch.setattr(traffic_reader_module, "_source_checkpoint", changing_checkpoint)
    statements = _h1_trace(repository, monkeypatch)
    assert reader.scan()
    assert bool(_h1_writes(statements)) is (when != "after")
    monkeypatch.setattr(traffic_reader_module, "_verify_stable_retired_eof", original)
    assert reader.scan()
    assert service.get_snapshot().total_bytes == 10
    assert service.get_snapshot().completed_sessions_total == 2


@pytest.mark.parametrize("mutation", ["missing", "replace", "rename", "proof_error"])
def test_H1_C11_C13_C16_invalid_file_proof_uses_legacy_write(
    tmp_path, monkeypatch, mutation,
):
    archive, repository, service, reader, _, _ = _h1_retired(tmp_path)
    before = table_rows(repository.db_path, "reader_state")
    original = traffic_reader_module._verify_stable_retired_eof
    proof_results = []

    def verified(*args):
        result = original(*args)
        proof_results.append(result)
        return result

    def proof(*args):
        if mutation == "proof_error":
            with patch.object(Path, "stat", side_effect=OSError("synthetic stat failure")):
                return verified(*args)
        if os.name == "nt":
            # Windows cannot unlink/rename this in-use archive. Inject the
            # equivalent path-validation failure, not a fake validator result.
            if mutation == "missing":
                with patch.object(Path, "stat", side_effect=FileNotFoundError("synthetic missing path")):
                    return verified(*args)
            fields = {
                name: getattr(archive.stat(), name)
                for name in ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")
            }
            if mutation == "replace":
                fields["st_ino"] += 1
            else:
                fields["st_ctime_ns"] += 1
            with patch.object(Path, "stat", return_value=SimpleNamespace(**fields)):
                return verified(*args)
        if mutation in ("replace", "rename"):
            archive.rename(Path(str(archive) + ".saved"))
            if mutation == "replace":
                archive.write_bytes(b"\n")
        else:
            archive.unlink()
        return verified(*args)

    monkeypatch.setattr(traffic_reader_module, "_verify_stable_retired_eof", proof)
    statements = _h1_trace(repository, monkeypatch)
    assert reader.scan()
    assert len(_h1_writes(statements)) == 1
    assert proof_results == [False]
    after = table_rows(repository.db_path, "reader_state")
    assert [row[:-1] for row in after] == [row[:-1] for row in before]
    assert after[0][-1] == service.now_iso()


@pytest.mark.parametrize("phase", ["before_compare", "proof", "upsert", "after_transaction"])
def test_H1_C17_real_process_exit_preserves_durable_state(tmp_path, phase):
    _, repository, _, reader, _, _ = _h1_retired(tmp_path)
    before = table_rows(repository.db_path, "reader_state")
    code = r'''
import os, sys
from app.public_traffic.repository import PublicTrafficRepository
r = PublicTrafficRepository(sys.argv[1])
s = next(iter(r.get_reader_states().values()))
phase = sys.argv[2]
if phase == "before_compare":
    original = r._connect
    def connect():
        c = original()
        def trace(sql):
            if "SELECT source_identity" in sql:
                os._exit(71)
        c.set_trace_callback(trace)
        return c
    r._connect = connect
if phase == "upsert":
    original_upsert = r._upsert_reader_state
    def upsert(*args, **kwargs):
        original_upsert(*args, **kwargs)
        os._exit(71)
    r._upsert_reader_state = upsert
def proof():
    if phase == "proof":
        os._exit(71)
    return phase != "upsert"
r.observe_source(source_identity=s.source_identity, source_path=s.source_path,
    source_offset=s.source_offset, observed_size=s.last_observed_size,
    retired_completed=True, now_utc="2099-01-01T00:00:00.000Z",
    source_checkpoint=s.source_checkpoint, stable_retired_eof=proof)
os._exit(71)
'''
    result = subprocess.run(
        [sys.executable, "-c", code, str(repository.db_path), phase],
        cwd=Path(__file__).resolve().parents[1], check=False,
        capture_output=True, timeout=20,
    )
    assert result.returncode == 71, result.stderr
    assert table_rows(repository.db_path, "reader_state") == before
    assert reader.scan()


def test_H1_C18_restart_reset_replay_and_history_remain_unchanged(tmp_path):
    archive, repository, service, reader, _, _ = _h1_retired(tmp_path)
    service.reset(ssid="Zefer_Parki")
    before = table_rows(repository.db_path, "counter_resets")
    reader = PublicTrafficReader(
        source_path=str(archive)[:-2], repository=repository, service=service,
        logger=reader.logger,
    )
    assert reader.scan()
    assert service.get_snapshot().total_bytes == 0
    archive.write_bytes(b"")
    assert reader.scan()
    append_lines(archive, [offline("h1-seed", traffic=7), offline("new", traffic=4)])
    assert reader.scan()
    assert service.get_snapshot().total_bytes == 4
    assert table_rows(repository.db_path, "counter_resets") == before


def test_H1_C20_busy_and_proof_exception_fail_closed(tmp_path, monkeypatch):
    _, repository, _, reader, _, _ = _h1_retired(tmp_path)
    before = table_rows(repository.db_path, "reader_state")
    repository.busy_timeout_ms = 1
    with closing(sqlite3.connect(repository.db_path)) as blocker:
        blocker.execute("BEGIN IMMEDIATE")
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            reader.scan()
        blocker.rollback()

    def interrupted(*args):
        raise RuntimeError("synthetic interruption")

    monkeypatch.setattr(traffic_reader_module, "_verify_stable_retired_eof", interrupted)
    with pytest.raises(RuntimeError, match="synthetic interruption"):
        reader.scan()
    assert table_rows(repository.db_path, "reader_state") == before


def test_H1_C19_identical_fixture_matches_legacy_persistence_and_counters(
    tmp_path, monkeypatch,
):
    outcomes = []
    for legacy in (True, False):
        selected, repository, service, reader, worker, clock = stack(
            tmp_path / ("legacy" if legacy else "h1"),
        )
        with monkeypatch.context() as scoped:
            if legacy:
                original = repository.observe_source

                def observe(**kwargs):
                    kwargs.pop("stable_retired_eof", None)
                    return original(**kwargs)

                scoped.setattr(repository, "observe_source", observe)
            for i in range(1, 6):
                append_lines(selected.source_log_path + f".{i}", [offline(f"seed-{i}")])
            Path(selected.source_log_path).touch()
            complete_backfill(worker)
            clock.value += timedelta(seconds=10)
            assert reader.scan()
            append_lines(selected.source_log_path, [
                offline("active", traffic=0), offline("seed-1"),
                offline("invalid", traffic=-1), {"event": "other"},
            ])
            clock.value += timedelta(seconds=10)
            assert reader.scan()
        states = sorted(
            (Path(row[1]).name, *row[2:])
            for row in table_rows(repository.db_path, "reader_state")
        )
        events = sorted(
            (*row[:7], Path(row[8]).name, *row[9:])
            for row in table_rows(repository.db_path, "processed_events")
        )
        outcomes.append((states, events, service.get_snapshot(),
            table_rows(repository.db_path, "traffic_daily"),
            table_rows(repository.db_path, "counter_state")))
    legacy, candidate = outcomes
    assert legacy[1:] == candidate[1:]
    assert [row[:-1] for row in legacy[0]] == [row[:-1] for row in candidate[0]]
    for old, new in zip(legacy[0], candidate[0]):
        if old[0].endswith(".log"):
            assert old == new
        else:
            assert old[-1] == "2026-07-29T08:00:20.000Z"
            assert new[-1] == "2026-07-29T08:00:00.000Z"


@pytest.mark.parametrize("parse_status", ["parsed", "partial"])
def test_valid_offline_is_counted_regardless_of_parse_status(
    tmp_path,
    parse_status,
):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [offline("event-1", parse_status=parse_status)],
    )

    complete_backfill(worker)
    snapshot = service.get_snapshot()

    assert snapshot.available
    assert snapshot.today_bytes == 1024**3
    assert snapshot.total_bytes == 1024**3
    assert snapshot.completed_sessions_today == 1
    assert snapshot.completed_sessions_total == 1
    assert len(table_rows(repository.db_path, "processed_events")) == 1


def test_887_bytes_is_accepted_by_existing_public_traffic_contract(tmp_path):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [offline("bytes-887", traffic=887)],
    )

    complete_backfill(worker)
    snapshot = service.get_snapshot()

    assert snapshot.total_bytes == 887
    assert snapshot.today_bytes == 887
    assert snapshot.completed_sessions_total == 1
    assert len(table_rows(repository.db_path, "processed_events")) == 1


def test_multiple_ssids_are_aggregated_separately(tmp_path):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [
            offline("z-1", traffic=100),
            offline("w-1", ssid="Welcome", traffic=250),
            offline("z-2", traffic=50),
        ],
    )

    complete_backfill(worker)

    assert service.get_snapshot().total_bytes == 150
    welcome = repository.get_snapshot(
        ssid="Welcome",
        local_date=service.local_date(),
    )
    assert welcome.total_bytes == 250
    assert welcome.completed_sessions_total == 1


def test_zero_traffic_counts_completed_session_and_updates_time(
    tmp_path,
):
    selected, _, service, _, worker, _ = stack(tmp_path)
    append_lines(selected.source_log_path, [offline("zero", traffic=0)])

    complete_backfill(worker)
    snapshot = service.get_snapshot()

    assert snapshot.total_bytes == 0
    assert snapshot.completed_sessions_total == 1
    assert snapshot.updated_at == "2026-07-29T08:00:00.000Z"


@pytest.mark.parametrize(
    "traffic",
    [True, 1.0, "1", None, -1, INT64_MAX + 1],
)
def test_invalid_traffic_is_finally_skipped(tmp_path, traffic):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [offline("invalid", traffic=traffic)],
    )

    complete_backfill(worker)
    snapshot = service.get_snapshot()
    rows = table_rows(repository.db_path, "processed_events")

    assert snapshot.total_bytes == 0
    assert snapshot.completed_sessions_total == 0
    assert len(rows) == 1
    assert rows[0][5] == 0
    assert rows[0][6] == "invalid_traffic_value"


def test_int64_max_is_allowed(tmp_path):
    selected, _, service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [offline("max", traffic=INT64_MAX)],
    )

    complete_backfill(worker)

    assert service.get_snapshot().total_bytes == INT64_MAX


def test_daily_overflow_is_finally_skipped_and_offset_advances(
    tmp_path,
):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [
            offline("max", traffic=INT64_MAX),
            offline("overflow", traffic=1),
        ],
    )

    complete_backfill(worker)
    rows = table_rows(repository.db_path, "processed_events")
    states = repository.get_reader_states()

    assert service.get_snapshot().total_bytes == INT64_MAX
    assert rows[1][5] == 0
    assert rows[1][6] == "aggregate_overflow"
    assert next(iter(states.values())).source_offset == Path(
        selected.source_log_path
    ).stat().st_size


def test_total_across_days_cannot_overflow(tmp_path):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [
            offline(
                "day-1",
                traffic=INT64_MAX,
                controller_timestamp="2026-07-28T07:00:00Z",
            ),
            offline(
                "day-2",
                traffic=1,
                controller_timestamp="2026-07-29T07:00:00Z",
            ),
        ],
    )

    complete_backfill(worker)
    rows = table_rows(repository.db_path, "processed_events")

    assert service.get_snapshot().total_bytes == INT64_MAX
    assert rows[1][6] == "aggregate_overflow"


def test_duplicate_does_not_change_totals_but_advances_new_inode(
    tmp_path,
):
    selected, repository, service, reader, worker, _ = stack(tmp_path)
    active = Path(selected.source_log_path)
    append_lines(active, [offline("same", traffic=100)])
    complete_backfill(worker)

    active.rename(Path(f"{active}.1"))
    append_lines(active, [offline("same", traffic=100)])
    reader.scan()

    assert service.get_snapshot().total_bytes == 100
    states = repository.get_reader_states()
    active_identity = f"{active.stat().st_dev}:{active.stat().st_ino}"
    assert states[active_identity].source_offset == active.stat().st_size
    assert len(table_rows(repository.db_path, "processed_events")) == 1


@pytest.mark.parametrize(
    "event_name",
    [
        "omada.client_online",
        "omada.client_authentication_expired",
    ],
)
def test_non_target_events_advance_without_processed_event(
    tmp_path,
    event_name,
):
    selected, repository, _, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [{
            "event": event_name,
            "normalized_event_id": "ignored-1",
        }],
    )

    complete_backfill(worker)

    assert table_rows(repository.db_path, "processed_events") == []
    state = next(iter(repository.get_reader_states().values()))
    assert state.source_offset == Path(
        selected.source_log_path
    ).stat().st_size


@pytest.mark.parametrize("invalid_ssid", [None, "", "   "])
def test_invalid_offline_ssid_is_stored_as_skipped(
    tmp_path,
    invalid_ssid,
):
    selected, repository, _, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [offline("missing-ssid", ssid=invalid_ssid)],
    )

    complete_backfill(worker)
    row = table_rows(repository.db_path, "processed_events")[0]

    assert row[1] is None
    assert row[5] == 0
    assert row[6] == "missing_ssid"


def test_missing_event_id_warns_and_only_advances_offset(
    tmp_path,
    caplog,
):
    selected, repository, _, _, worker, _ = stack(tmp_path)
    record = offline("")
    append_lines(selected.source_log_path, [record])

    with caplog.at_level(logging.WARNING):
        complete_backfill(worker)

    assert table_rows(repository.db_path, "processed_events") == []
    assert "missing_normalized_event_id" in caplog.text
    state = next(iter(repository.get_reader_states().values()))
    assert state.source_offset == Path(
        selected.source_log_path
    ).stat().st_size


def test_controller_timestamp_precedes_received_at(tmp_path):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [offline(
            "time",
            controller_timestamp="2026-07-28T19:59:59Z",
            received_at="2026-07-28T20:00:01Z",
        )],
    )

    complete_backfill(worker)

    previous_day = repository.get_snapshot(
        ssid="Zefer_Parki",
        local_date="2026-07-28",
    )
    assert previous_day.today_bytes == 1024**3
    assert service.get_snapshot().today_bytes == 0


def test_invalid_controller_uses_received_at(tmp_path):
    selected, repository, _, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [offline(
            "received",
            controller_timestamp="invalid",
            received_at="2026-07-28T20:00:00Z",
        )],
    )

    complete_backfill(worker)

    snapshot = repository.get_snapshot(
        ssid="Zefer_Parki",
        local_date="2026-07-29",
    )
    assert snapshot.today_bytes == 1024**3


@pytest.mark.parametrize(
    "extreme_controller_timestamp",
    [
        "0001-01-01T00:00:00+14:00",
        "9999-12-31T23:59:59-14:00",
    ],
)
def test_extreme_controller_timestamp_uses_received_at_and_advances(
    tmp_path,
    extreme_controller_timestamp,
):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [offline(
            "extreme-controller",
            traffic=7,
            controller_timestamp=extreme_controller_timestamp,
            received_at="2026-07-29T07:30:01Z",
        )],
    )

    complete_backfill(worker)

    assert service.get_snapshot().total_bytes == 7
    assert len(table_rows(repository.db_path, "processed_events")) == 1
    state = next(iter(repository.get_reader_states().values()))
    assert state.source_offset == Path(
        selected.source_log_path
    ).stat().st_size


def test_extreme_controller_and_received_timestamps_use_clock(
    tmp_path,
    caplog,
):
    selected, _, service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [offline(
            "extreme-clock-fallback",
            traffic=9,
            controller_timestamp="0001-01-01T00:00:00+14:00",
            received_at="9999-12-31T23:59:59-14:00",
        )],
    )

    with caplog.at_level(logging.WARNING):
        complete_backfill(worker)

    assert service.get_snapshot().total_bytes == 9
    assert "public_traffic_timestamp_fallback" in caplog.text


def test_last_timestamp_fallback_warns_and_counts(tmp_path, caplog):
    selected, _, service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [offline(
            "fallback",
            controller_timestamp=None,
            received_at="invalid",
        )],
    )

    with caplog.at_level(logging.WARNING):
        complete_backfill(worker)

    assert service.get_snapshot().today_bytes == 1024**3
    assert "public_traffic_timestamp_fallback" in caplog.text


def test_incomplete_line_waits_for_newline_and_backfill_stays_false(
    tmp_path,
):
    selected, repository, service, reader, worker, _ = stack(tmp_path)
    active = Path(selected.source_log_path)
    append_lines(
        active,
        [offline("partial")],
        newline=False,
    )

    worker.run_once()

    assert not repository.initial_backfill_completed()
    assert table_rows(repository.db_path, "processed_events") == []
    with active.open("ab") as stream:
        stream.write(b"\n")
    worker.run_once()

    assert repository.initial_backfill_completed()
    assert service.get_snapshot().total_bytes == 1024**3
    assert reader.scan()


def test_invalid_json_advances_and_next_line_is_counted(
    tmp_path,
    caplog,
):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [b'{"broken":', offline("valid")],
    )

    with caplog.at_level(logging.WARNING):
        complete_backfill(worker)

    assert "reason=invalid_json" in caplog.text
    assert service.get_snapshot().completed_sessions_total == 1
    state = next(iter(repository.get_reader_states().values()))
    assert state.source_offset == Path(
        selected.source_log_path
    ).stat().st_size


def test_invalid_utf8_advances_and_next_line_is_counted(
    tmp_path,
    caplog,
):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [b"\xff\xfe", offline("valid")],
    )

    with caplog.at_level(logging.WARNING):
        complete_backfill(worker)

    assert "public_traffic_invalid_utf8" in caplog.text
    assert service.get_snapshot().completed_sessions_total == 1
    state = next(iter(repository.get_reader_states().values()))
    assert state.source_offset == Path(
        selected.source_log_path
    ).stat().st_size


def test_transaction_failure_rolls_back_aggregate_event_and_offset(
    tmp_path,
    monkeypatch,
):
    selected, repository, _, reader, _, _ = stack(tmp_path)
    append_lines(selected.source_log_path, [offline("rollback")])

    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("forced failure")

    monkeypatch.setattr(repository, "_add_to_daily", fail)

    with pytest.raises(sqlite3.OperationalError):
        reader.scan()

    assert table_rows(repository.db_path, "traffic_daily") == []
    assert table_rows(repository.db_path, "processed_events") == []
    assert repository.get_reader_states() == {}


def test_empty_installation_becomes_ready_with_zero_stats(tmp_path):
    _, repository, service, _, worker, _ = stack(tmp_path)

    complete_backfill(worker)
    snapshot = service.get_snapshot()

    assert snapshot.available
    assert snapshot.total_bytes == 0
    assert snapshot.updated_at is None


def test_backfill_reads_oldest_rotation_first(tmp_path):
    selected, repository, _, _, worker, _ = stack(tmp_path)
    active = Path(selected.source_log_path)
    append_lines(f"{active}.2", [offline("oldest", traffic=1)])
    append_lines(f"{active}.1", [offline("middle", traffic=2)])
    append_lines(active, [offline("newest", traffic=3)])

    complete_backfill(worker)
    with closing(sqlite3.connect(repository.db_path)) as connection:
        ids = [
            row[0]
            for row in connection.execute(
                """
                SELECT normalized_event_id
                FROM processed_events
                ORDER BY rowid
                """
            )
        ]

    assert ids == ["oldest", "middle", "newest"]


def test_live_rotation_finishes_old_inode_then_new_active(tmp_path):
    selected, repository, service, reader, worker, _ = stack(tmp_path)
    active = Path(selected.source_log_path)
    append_lines(active, [offline("first", traffic=1)])
    complete_backfill(worker)
    old_identity = f"{active.stat().st_dev}:{active.stat().st_ino}"

    active.rename(Path(f"{active}.1"))
    append_lines(
        f"{active}.1",
        [offline("old-tail", traffic=2)],
    )
    append_lines(active, [offline("new-active", traffic=4)])
    reader.scan()

    assert service.get_snapshot().total_bytes == 7
    assert repository.get_reader_states()[
        old_identity
    ].retired_completed


def test_truncate_restarts_at_zero_without_double_count(tmp_path):
    selected, repository, service, reader, worker, _ = stack(tmp_path)
    active = Path(selected.source_log_path)
    append_lines(active, [offline("same", traffic=5)])
    complete_backfill(worker)
    active.write_bytes(b"")
    append_lines(
        active,
        [
            offline("same", traffic=5),
            offline("new", traffic=7),
        ],
    )

    reader.scan()

    assert service.get_snapshot().total_bytes == 12
    assert len(table_rows(repository.db_path, "processed_events")) == 2


def test_missing_active_inode_warns_only_once_across_restart(
    tmp_path,
    caplog,
):
    selected, repository, _, reader, worker, _ = stack(tmp_path)
    active = Path(selected.source_log_path)
    append_lines(active, [offline("event")])
    complete_backfill(worker)
    active.unlink()

    with caplog.at_level(logging.WARNING):
        reader.scan()
        reader.scan()
        restarted = PublicTrafficReader(
            source_path=selected.source_log_path,
            repository=repository,
            service=reader.service,
            logger=reader.logger,
        )
        restarted.scan()

    assert caplog.text.count(
        "public_traffic_old_inode_not_found"
    ) == 1


def test_missing_completed_retired_inode_does_not_warn(
    tmp_path,
    caplog,
):
    selected, _, _, reader, worker, _ = stack(tmp_path)
    active = Path(selected.source_log_path)
    rotated = Path(f"{active}.1")
    append_lines(rotated, [offline("retired")])
    complete_backfill(worker)
    rotated.unlink()

    with caplog.at_level(logging.WARNING):
        reader.scan()

    assert "public_traffic_old_inode_not_found" not in caplog.text


@pytest.mark.parametrize(
    ("value", "display"),
    [
        (0, "0 MB"),
        (1024**2, "1 MB"),
        (812 * 1024**2, "812 MB"),
        (3 * 1024**3 + 182 * 1024**2, "3.18 GB"),
        (int(Decimal("4.5") * (1024**3)), "4.5 GB"),
        (int(Decimal("1.24") * (1024**4)), "1.24 TB"),
    ],
)
def test_binary_formatting_uses_half_up(value, display):
    assert format_traffic_bytes(value) == display


def test_reset_is_forbidden_before_backfill(tmp_path):
    _, repository, service, _, _, _ = stack(tmp_path)

    with pytest.raises(BackfillIncompleteError):
        service.reset(ssid="Zefer_Parki")

    assert table_rows(repository.db_path, "counter_resets") == []


def test_reset_one_ssid_preserves_state_and_other_ssids(tmp_path):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [
            offline("z", traffic=10),
            offline("w", ssid="Welcome", traffic=20),
        ],
    )
    complete_backfill(worker)
    states_before = repository.get_reader_states()

    summary = service.reset(ssid="Zefer_Parki")

    assert summary.previous_total_bytes == 10
    assert service.get_snapshot().total_bytes == 0
    welcome = repository.get_snapshot(
        ssid="Welcome",
        local_date=service.local_date(),
    )
    assert welcome.total_bytes == 20
    assert len(table_rows(repository.db_path, "processed_events")) == 2
    assert repository.get_reader_states() == states_before
    assert repository.initial_backfill_completed()
    assert len(table_rows(repository.db_path, "counter_resets")) == 1


def test_reset_all_preserves_processed_events_and_state(tmp_path):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [
            offline("z", traffic=10),
            offline("w", ssid="Welcome", traffic=20),
        ],
    )
    complete_backfill(worker)

    summary = service.reset(ssid=None)

    assert summary.affected_ssids == 2
    assert table_rows(repository.db_path, "traffic_daily") == []
    assert len(table_rows(repository.db_path, "processed_events")) == 2
    assert repository.initial_backfill_completed()


def test_reset_transaction_failure_rolls_back_delete_and_audit(
    tmp_path,
):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    append_lines(selected.source_log_path, [offline("z", traffic=10)])
    complete_backfill(worker)

    with pytest.raises(RuntimeError):
        service.reset(
            ssid="Zefer_Parki",
            before_commit=lambda: (_ for _ in ()).throw(
                RuntimeError("forced")
            ),
        )

    assert service.get_snapshot().total_bytes == 10
    assert table_rows(repository.db_path, "counter_resets") == []


def test_old_events_do_not_restore_after_reset_and_truncate(
    tmp_path,
):
    selected, _, service, reader, worker, _ = stack(tmp_path)
    active = Path(selected.source_log_path)
    original = offline("old", traffic=10)
    append_lines(active, [original])
    complete_backfill(worker)
    service.reset(ssid="Zefer_Parki")
    active.write_bytes(b"")
    append_lines(active, [original, offline("new", traffic=4)])

    reader.scan()

    assert service.get_snapshot().total_bytes == 4


def test_cli_without_yes_does_not_reset(tmp_path, capsys):
    selected, _, service, _, worker, _ = stack(tmp_path)
    append_lines(selected.source_log_path, [offline("z", traffic=10)])
    complete_backfill(worker)
    settings = {
        "public_traffic_counter_enabled": True,
        "public_traffic_ssid": selected.ssid,
        "public_traffic_db_path": selected.db_path,
        "omada_webhook_normalized_log_file": (
            selected.source_log_path
        ),
        "portal_counter_timezone": selected.timezone_name,
        "public_traffic_scan_interval_seconds": 10,
        "public_traffic_frontend_refresh_seconds": 60,
    }

    with patch(
        "app.public_traffic.cli.get_settings",
        return_value=settings,
    ):
        exit_code = cli_main(["reset", "--ssid", selected.ssid])

    assert exit_code == 2
    assert service.get_snapshot().total_bytes == 10
    assert "--yes" in capsys.readouterr().err


def test_cli_rejects_reset_during_backfill(tmp_path, capsys):
    selected, _, _, _, _, _ = stack(tmp_path)
    settings = {
        "public_traffic_counter_enabled": True,
        "public_traffic_ssid": selected.ssid,
        "public_traffic_db_path": selected.db_path,
        "omada_webhook_normalized_log_file": (
            selected.source_log_path
        ),
        "portal_counter_timezone": selected.timezone_name,
        "public_traffic_scan_interval_seconds": 10,
        "public_traffic_frontend_refresh_seconds": 60,
    }

    with patch(
        "app.public_traffic.cli.get_settings",
        return_value=settings,
    ):
        exit_code = cli_main([
            "reset",
            "--ssid",
            selected.ssid,
            "--yes",
        ])

    assert exit_code == 1
    assert "backfill is not complete" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("public_traffic_ssid", ""),
        ("public_traffic_db_path", ""),
        ("portal_counter_timezone", ""),
        ("public_traffic_scan_interval_seconds", 0),
        ("public_traffic_frontend_refresh_seconds", -1),
    ],
)
def test_invalid_enabled_configuration_is_rejected(
    tmp_path,
    key,
    value,
):
    values = {
        "public_traffic_counter_enabled": True,
        "public_traffic_ssid": "Zefer_Parki",
        "public_traffic_db_path": str(tmp_path / "db.sqlite"),
        "omada_webhook_normalized_log_file": str(tmp_path / "log"),
        "portal_counter_timezone": "Asia/Baku",
        "public_traffic_scan_interval_seconds": 10,
        "public_traffic_frontend_refresh_seconds": 60,
    }
    values[key] = value

    with pytest.raises(PublicTrafficConfigError):
        PublicTrafficConfig.from_settings(values)


def test_invalid_timezone_is_a_fail_safe_configuration_error(
    tmp_path,
    caplog,
):
    selected = config(
        tmp_path,
        portal_counter_timezone="Not/A-Timezone",
    )
    service = PublicTrafficService(
        config=selected,
        repository=PublicTrafficRepository(selected.db_path),
        logger=logging.getLogger("invalid-traffic-timezone"),
    )

    with caplog.at_level(logging.ERROR):
        assert not service.initialize()

    assert not service.available
    assert "public_traffic_configuration_error" in caplog.text
    assert not Path(selected.db_path).exists()


def test_unusable_database_path_is_a_fail_safe_database_error(
    tmp_path,
    caplog,
):
    db_directory = tmp_path / "database-is-a-directory"
    db_directory.mkdir()
    selected = config(
        tmp_path,
        public_traffic_db_path=str(db_directory),
    )
    service = PublicTrafficService(
        config=selected,
        repository=PublicTrafficRepository(selected.db_path),
        logger=logging.getLogger("invalid-traffic-database"),
    )

    with caplog.at_level(logging.ERROR):
        assert not service.initialize()

    assert not service.available
    assert "public_traffic_database_error" in caplog.text


def test_worker_start_is_immediate_idempotent_and_stops(tmp_path):
    _, _, _, _, worker, _ = stack(tmp_path)

    started_at = time.monotonic()
    assert worker.start()
    assert time.monotonic() - started_at < 0.5
    assert not worker.start()
    worker.stop()

    assert not worker.running


def test_backfill_lifecycle_logs_once_across_repeated_scans(
    tmp_path,
    caplog,
):
    selected, repository, _, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [offline("unfinished-backfill")],
        newline=False,
    )

    caplog.set_level(logging.INFO)
    worker.run_once()
    worker.run_once()

    assert caplog.text.count("public_traffic_backfill_started") == 1
    assert "public_traffic_backfill_completed" not in caplog.text
    with Path(selected.source_log_path).open("ab") as stream:
        stream.write(b"\n")
    worker.run_once()
    worker.run_once()

    assert repository.initial_backfill_completed()
    assert caplog.text.count("public_traffic_backfill_started") == 1
    assert caplog.text.count("public_traffic_backfill_completed") == 1
    assert "public_traffic_reconciliation_started" not in caplog.text


def test_startup_reconciliation_logs_once_then_scans_silently(
    tmp_path,
    caplog,
):
    selected, repository, service, _, first_worker, _ = stack(
        tmp_path
    )
    complete_backfill(first_worker)
    restarted_reader = PublicTrafficReader(
        source_path=selected.source_log_path,
        repository=repository,
        service=service,
        logger=logging.getLogger("reconciliation-reader"),
    )
    restarted_worker = PublicTrafficWorker(
        reader=restarted_reader,
        repository=repository,
        service=service,
        logger=logging.getLogger("reconciliation-worker"),
        scan_interval_seconds=10,
    )

    with caplog.at_level(logging.INFO):
        restarted_worker.run_once()
        restarted_worker.run_once()
        restarted_worker.run_once()

    assert (
        caplog.text.count("public_traffic_reconciliation_started")
        == 1
    )
    assert (
        caplog.text.count("public_traffic_reconciliation_completed")
        == 1
    )
    assert "public_traffic_backfill_started" not in caplog.text


def test_worker_start_failure_does_not_prevent_flask_start(
    caplog,
):
    class FailingWorker:
        def start(self):
            raise RuntimeError("cannot create thread")

    class TrafficService:
        available = True

    class FakeApp:
        def __init__(self):
            self.extensions = {
                "public_traffic_worker": FailingWorker(),
                "public_traffic_service": TrafficService(),
            }
            self.ran = False

        def run(self, **_kwargs):
            self.ran = True

    app = FakeApp()
    settings = {
        **CONTROLLER_BASE,
        "host": "127.0.0.1",
        "port": 8088,
        "debug": False,
        "client_secret": "fixture-secret",
    }
    with (
        # Composition-only startup: no loaded-artifact attestation is claimed.
        patch.object(run_module, "capture_loaded_artifact_identity", return_value=SimpleNamespace(
            json_line=lambda: "synthetic Public Traffic composition identity")),
        patch.object(run_module, "create_app", return_value=app),
        patch.object(
            run_module,
            "create_controller",
            return_value=object(),
        ),
        patch.object(run_module, "get_settings", return_value=settings),
        patch.object(run_module.atexit, "register"),
        patch.object(run_module.signal, "signal"),
        patch.object(run_module, "shutdown_handler"),
        caplog.at_level(logging.ERROR),
    ):
        run_module.main()

    assert app.ran
    assert not app.extensions["public_traffic_service"].available
    assert run_module._public_traffic_worker is None
    assert "public_traffic_counter_start_failed" in caplog.text


def test_api_keeps_open_counter_when_traffic_is_unavailable(
    tmp_path,
):
    open_service = PortalCounterService(
        PortalCounterRepository(str(tmp_path / "open.db"))
    )
    assert open_service.initialize()
    settings = {
        "portal_counter_enabled": True,
        "portal_counter_db_path": str(tmp_path / "open.db"),
        "portal_counter_timezone": "Asia/Baku",
        "portal_counter_api_enabled": True,
    }
    with (
        patch.object(
            web_module,
            "get_settings",
            return_value=settings,
        ),
        patch.object(
            web_module,
            "create_controller",
            return_value=object(),
        ),
    ):
        app = web_module.create_app(open_service, controller=object())
    client = app.test_client()

    response = client.get("/api/public/portal-counter")

    assert response.status_code == 200
    assert response.get_json()["opened_total"] == 0
    assert response.get_json()["traffic"] == {
        "available": False,
        "ssid": "",
    }


def test_api_returns_traffic_and_preserves_old_fields(tmp_path):
    selected, _, traffic_service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [offline("api", traffic=3_407_872_000)],
    )
    complete_backfill(worker)
    open_service = PortalCounterService(
        PortalCounterRepository(str(tmp_path / "open.db"))
    )
    assert open_service.initialize()
    settings = {
        "portal_counter_enabled": True,
        "portal_counter_db_path": str(tmp_path / "open.db"),
        "portal_counter_timezone": "Asia/Baku",
        "portal_counter_api_enabled": True,
    }
    with (
        patch.object(
            web_module,
            "get_settings",
            return_value=settings,
        ),
        patch.object(
            web_module,
            "create_controller",
            return_value=object(),
        ),
    ):
        app = web_module.create_app(
            open_service,
            controller=object(),
            public_traffic_service=traffic_service,
        )

    payload = app.test_client().get(
        "/api/public/portal-counter"
    ).get_json()

    assert set(payload) == {
        "opened_today",
        "opened_total",
        "day",
        "timezone",
        "traffic",
    }
    assert payload["traffic"] == {
        "available": True,
        "ssid": "Zefer_Parki",
        "today_bytes": 3_407_872_000,
        "today_display": "3.17 GB",
        "total_bytes": 3_407_872_000,
        "total_display": "3.17 GB",
        "completed_sessions_today": 1,
        "completed_sessions_total": 1,
        "updated_at": "2026-07-29T08:00:00.000Z",
    }


def test_corrupt_aggregate_hides_only_traffic_from_api(tmp_path):
    selected, repository, traffic_service, _, worker, _ = stack(
        tmp_path
    )
    append_lines(selected.source_log_path, [offline("api")])
    complete_backfill(worker)
    with closing(sqlite3.connect(repository.db_path)) as connection:
        connection.execute(
            "UPDATE traffic_daily SET traffic_bytes = 1.5"
        )
        connection.commit()
    open_service = PortalCounterService(
        PortalCounterRepository(str(tmp_path / "open.db"))
    )
    assert open_service.initialize()
    settings = {
        "portal_counter_enabled": True,
        "portal_counter_db_path": str(tmp_path / "open.db"),
        "portal_counter_timezone": "Asia/Baku",
        "portal_counter_api_enabled": True,
    }
    with (
        patch.object(
            web_module,
            "get_settings",
            return_value=settings,
        ),
        patch.object(
            web_module,
            "create_controller",
            return_value=object(),
        ),
    ):
        app = web_module.create_app(
            open_service,
            controller=object(),
            public_traffic_service=traffic_service,
        )

    response = app.test_client().get(
        "/api/public/portal-counter"
    )

    assert response.status_code == 200
    assert response.get_json()["opened_total"] == 0
    assert response.get_json()["traffic"] == {
        "available": False,
        "ssid": "Zefer_Parki",
    }


def test_existing_database_is_available_before_reconciliation(
    tmp_path,
):
    selected, repository, _, _, worker, clock = stack(tmp_path)
    append_lines(selected.source_log_path, [offline("saved", traffic=9)])
    complete_backfill(worker)
    restarted = PublicTrafficService(
        config=selected,
        repository=PublicTrafficRepository(selected.db_path),
        logger=logging.getLogger("restarted-public-traffic"),
        clock=clock,
    )

    assert restarted.initialize()
    assert restarted.get_snapshot().available
    assert restarted.get_snapshot().total_bytes == 9
    assert repository.initial_backfill_completed()


def test_interrupted_backfill_resumes_without_duplicate(tmp_path):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    active = Path(selected.source_log_path)
    complete = json.dumps(offline("first", traffic=2)).encode()
    partial = json.dumps(offline("second", traffic=3)).encode()
    active.write_bytes(complete + b"\n" + partial)

    worker.run_once()

    assert not repository.initial_backfill_completed()
    assert len(table_rows(repository.db_path, "processed_events")) == 1
    with active.open("ab") as stream:
        stream.write(b"\n")
    worker.run_once()

    assert repository.initial_backfill_completed()
    assert service.get_snapshot().total_bytes == 5
    assert len(table_rows(repository.db_path, "processed_events")) == 2


def test_multiple_rotations_while_stopped_are_reconciled(tmp_path):
    selected, _, service, reader, worker, _ = stack(tmp_path)
    active = Path(selected.source_log_path)
    append_lines(active, [offline("before-stop", traffic=1)])
    complete_backfill(worker)

    active.rename(Path(f"{active}.2"))
    append_lines(f"{active}.1", [offline("during-stop", traffic=2)])
    append_lines(active, [offline("after-stop", traffic=4)])
    reader.scan()

    assert service.get_snapshot().total_bytes == 7


def test_never_existing_source_does_not_warn(tmp_path, caplog):
    _, _, _, reader, worker, _ = stack(tmp_path)
    complete_backfill(worker)

    with caplog.at_level(logging.WARNING):
        reader.scan()

    assert "public_traffic_old_inode_not_found" not in caplog.text


def test_reader_state_tracks_observed_size_and_retired_status(
    tmp_path,
):
    selected, repository, _, _, worker, _ = stack(tmp_path)
    active = Path(selected.source_log_path)
    rotated = Path(f"{active}.1")
    append_lines(rotated, [offline("retired")])
    append_lines(active, [offline("active")])

    complete_backfill(worker)
    states = repository.get_reader_states()
    active_identity = f"{active.stat().st_dev}:{active.stat().st_ino}"
    retired_identity = (
        f"{rotated.stat().st_dev}:{rotated.stat().st_ino}"
    )

    assert states[active_identity].last_observed_size == active.stat().st_size
    assert not states[active_identity].retired_completed
    assert states[retired_identity].retired_completed


def test_disappeared_completed_retired_inode_is_safe_when_reused(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.public_traffic.reader._source_identity",
        lambda _stat: "fixed:retired",
    )
    selected, repository, service, reader, worker, _ = stack(
        tmp_path
    )
    active = Path(selected.source_log_path)
    rotated = Path(f"{active}.1")
    append_lines(rotated, [offline("old-retired", traffic=2)])
    complete_backfill(worker)

    assert repository.get_reader_states()[
        "fixed:retired"
    ].retired_completed
    rotated.unlink()
    reader.scan()

    assert "fixed:retired" not in repository.get_reader_states()
    append_lines(active, [offline("reused-retired", traffic=3)])
    reader.scan()

    assert service.get_snapshot().total_bytes == 5


def test_retired_inode_reused_by_active_before_missing_scan(
    tmp_path,
    monkeypatch,
    caplog,
):
    monkeypatch.setattr(
        "app.public_traffic.reader._source_identity",
        lambda _stat: "fixed:instant-reuse",
    )
    selected, repository, service, reader, worker, _ = stack(
        tmp_path
    )
    active = Path(selected.source_log_path)
    rotated = Path(f"{active}.1")
    append_lines(rotated, [offline("old-instant", traffic=2)])
    complete_backfill(worker)
    old_offset = repository.get_reader_states()[
        "fixed:instant-reuse"
    ].source_offset

    rotated.unlink()
    append_lines(
        active,
        [
            offline("new-instant", traffic=3),
            {
                "event": "omada.client_online",
                "padding": "x" * (old_offset + 100),
            },
        ],
    )
    assert active.stat().st_size > old_offset
    with caplog.at_level(logging.WARNING):
        reader.scan()

    assert service.get_snapshot().total_bytes == 5
    assert "reason=retired_identity_reused" in caplog.text


def test_missing_inode_reappearance_restarts_from_zero(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.public_traffic.reader._source_identity",
        lambda _stat: "fixed:missing",
    )
    selected, repository, service, reader, worker, _ = stack(
        tmp_path
    )
    active = Path(selected.source_log_path)
    append_lines(active, [offline("old-active", traffic=2)])
    complete_backfill(worker)
    old_offset = repository.get_reader_states()[
        "fixed:missing"
    ].source_offset

    active.unlink()
    reader.scan()
    assert repository.get_reader_states()[
        "fixed:missing"
    ].missing_warning_emitted

    append_lines(
        active,
        [
            offline("reappeared", traffic=3),
            {
                "event": "omada.client_online",
                "padding": "x" * (old_offset + 100),
            },
        ],
    )
    assert active.stat().st_size > old_offset
    reader.scan()

    assert service.get_snapshot().total_bytes == 5
    state = repository.get_reader_states()["fixed:missing"]
    assert not state.missing_warning_emitted
    assert state.source_offset == active.stat().st_size


def test_same_inode_truncate_and_regrow_above_offset_restarts_zero(
    tmp_path,
    monkeypatch,
    caplog,
):
    monkeypatch.setattr(
        "app.public_traffic.reader._source_identity",
        lambda _stat: "fixed:truncate-regrow",
    )
    selected, _, service, reader, worker, _ = stack(tmp_path)
    active = Path(selected.source_log_path)
    append_lines(active, [offline("before-rewrite", traffic=2)])
    complete_backfill(worker)
    old_offset = active.stat().st_size

    active.write_bytes(b"")
    append_lines(
        active,
        [
            offline("after-rewrite-1", traffic=3),
            offline("after-rewrite-2", traffic=4),
            {
                "event": "omada.client_online",
                "padding": "x" * (old_offset + 100),
            },
        ],
    )
    assert active.stat().st_size > old_offset
    with caplog.at_level(logging.WARNING):
        reader.scan()

    assert service.get_snapshot().total_bytes == 9
    assert "reason=checkpoint_mismatch" in caplog.text


def test_schema_v1_migrates_reader_checkpoint_to_v2(tmp_path):
    db_path = tmp_path / "traffic-v1.db"
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute(
            """
            CREATE TABLE reader_state (
                source_identity TEXT PRIMARY KEY,
                source_path TEXT NOT NULL,
                source_offset INTEGER NOT NULL DEFAULT 0,
                last_observed_size INTEGER,
                retired_completed INTEGER NOT NULL DEFAULT 0,
                missing_warning_emitted INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute("PRAGMA user_version=1")
        connection.commit()
    repository = PublicTrafficRepository(str(db_path))

    repository.migrate("2026-07-29T08:00:00.000Z")

    with closing(sqlite3.connect(db_path)) as connection:
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(reader_state)"
            )
        }
        version = connection.execute(
            "PRAGMA user_version"
        ).fetchone()[0]
    assert "source_checkpoint" in columns
    assert version == 2


def test_sqlite_uses_wal_and_busy_timeout(tmp_path):
    selected, repository, _, _, _, _ = stack(tmp_path)
    with closing(repository._connect()) as connection:
        journal_mode = connection.execute(
            "PRAGMA journal_mode"
        ).fetchone()[0]
        busy_timeout = connection.execute(
            "PRAGMA busy_timeout"
        ).fetchone()[0]

    assert journal_mode.lower() == "wal"
    assert busy_timeout == 250
    assert Path(selected.db_path).exists()


def test_concurrent_reads_and_single_writer_do_not_lock(tmp_path):
    _, repository, service, _, _, _ = stack(tmp_path)
    repository.mark_initial_backfill_completed(service.now_iso())

    def write_events():
        for index in range(30):
            repository.process_offline_event(
                event=TrafficEvent(
                    normalized_event_id=f"parallel-{index}",
                    ssid="Zefer_Parki",
                    local_date=service.local_date(),
                    traffic_bytes=1,
                    skip_reason=None,
                ),
                source_identity="1:1",
                source_path="parallel.log",
                offset_start=index,
                offset_end=index + 1,
                observed_size=30,
                processed_at=service.now_iso(),
            )

    def read_snapshots():
        for _ in range(60):
            service.get_snapshot()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(write_events),
            executor.submit(read_snapshots),
        ]
        for future in futures:
            future.result()

    assert service.get_snapshot().total_bytes == 30


def test_updated_at_ignores_duplicate_invalid_and_overflow(
    tmp_path,
):
    selected, _, service, reader, worker, clock = stack(tmp_path)
    active = Path(selected.source_log_path)
    append_lines(active, [offline("max", traffic=INT64_MAX)])
    complete_backfill(worker)
    first_updated = service.get_snapshot().updated_at
    clock.value = datetime(2026, 7, 29, 9, 0, tzinfo=UTC)
    append_lines(
        active,
        [
            offline("max", traffic=INT64_MAX),
            offline("invalid-later", traffic=True),
            offline("overflow-later", traffic=1),
        ],
    )

    reader.scan()

    assert service.get_snapshot().updated_at == first_updated


def test_invalid_offline_warning_is_not_repeated_after_truncate(
    tmp_path,
    caplog,
):
    selected, _, _, reader, worker, _ = stack(tmp_path)
    active = Path(selected.source_log_path)
    invalid = offline("invalid-once", traffic=True)
    append_lines(active, [invalid])

    with caplog.at_level(logging.WARNING):
        complete_backfill(worker)
        active.write_bytes(b"")
        append_lines(active, [invalid])
        reader.scan()

    assert caplog.text.count("reason=invalid_traffic_value") == 1


def test_new_event_after_reset_starts_from_zero(tmp_path):
    selected, _, service, reader, worker, _ = stack(tmp_path)
    append_lines(selected.source_log_path, [offline("old", traffic=8)])
    complete_backfill(worker)
    service.reset(ssid="Zefer_Parki")
    append_lines(selected.source_log_path, [offline("new", traffic=3)])

    reader.scan()

    assert service.get_snapshot().total_bytes == 3
    assert service.get_snapshot().completed_sessions_total == 1


def test_cli_success_resets_and_writes_audit(tmp_path, capsys):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    append_lines(selected.source_log_path, [offline("cli", traffic=10)])
    complete_backfill(worker)
    settings = {
        "public_traffic_counter_enabled": True,
        "public_traffic_ssid": selected.ssid,
        "public_traffic_db_path": selected.db_path,
        "omada_webhook_normalized_log_file": (
            selected.source_log_path
        ),
        "portal_counter_timezone": selected.timezone_name,
        "public_traffic_scan_interval_seconds": 10,
        "public_traffic_frontend_refresh_seconds": 60,
    }

    with patch(
        "app.public_traffic.cli.get_settings",
        return_value=settings,
    ):
        exit_code = cli_main([
            "reset",
            "--ssid",
            selected.ssid,
            "--yes",
        ])

    assert exit_code == 0
    assert service.get_snapshot().total_bytes == 0
    assert len(table_rows(repository.db_path, "counter_resets")) == 1
    assert "Reset completed" in capsys.readouterr().out


def test_cli_reset_all_handles_cross_ssid_sum_above_int64(
    tmp_path,
    capsys,
):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    complete_backfill(worker)
    per_ssid = INT64_MAX // 2 + 1
    with closing(repository._connect()) as connection:
        connection.executemany(
            """
            INSERT INTO traffic_daily (
                local_date,
                ssid,
                traffic_bytes,
                completed_sessions,
                updated_at
            )
            VALUES (?, ?, ?, 1, ?)
            """,
            [
                (
                    service.local_date(),
                    "SSID-A",
                    per_ssid,
                    service.now_iso(),
                ),
                (
                    service.local_date(),
                    "SSID-B",
                    per_ssid,
                    service.now_iso(),
                ),
            ],
        )
        connection.commit()
    settings = {
        "public_traffic_counter_enabled": True,
        "public_traffic_ssid": selected.ssid,
        "public_traffic_db_path": selected.db_path,
        "omada_webhook_normalized_log_file": (
            selected.source_log_path
        ),
        "portal_counter_timezone": selected.timezone_name,
        "public_traffic_scan_interval_seconds": 10,
        "public_traffic_frontend_refresh_seconds": 60,
    }

    with patch(
        "app.public_traffic.cli.get_settings",
        return_value=settings,
    ):
        exit_code = cli_main(["reset", "--all", "--yes"])

    assert exit_code == 0
    assert table_rows(repository.db_path, "traffic_daily") == []
    reset = table_rows(repository.db_path, "counter_resets")[0]
    assert reset[-1] == 2
    output = capsys.readouterr().out
    assert 'SSID "SSID-A"' in output
    assert 'SSID "SSID-B"' in output


def test_cli_rejects_ssid_and_all_together():
    with pytest.raises(SystemExit) as raised:
        cli_main([
            "reset",
            "--ssid",
            "Zefer_Parki",
            "--all",
            "--yes",
        ])

    assert raised.value.code == 2


def test_disabled_component_creates_no_database_or_worker(tmp_path):
    open_service = PortalCounterService(
        PortalCounterRepository(str(tmp_path / "open.db"))
    )
    assert open_service.initialize()
    traffic_path = tmp_path / "disabled-traffic.db"
    settings = {
        "portal_counter_enabled": True,
        "portal_counter_db_path": str(tmp_path / "open.db"),
        "portal_counter_timezone": "Asia/Baku",
        "portal_counter_api_enabled": True,
        "public_traffic_counter_enabled": False,
        "public_traffic_ssid": "Zefer_Parki",
        "public_traffic_db_path": str(traffic_path),
        "omada_webhook_normalized_log_file": str(tmp_path / "log"),
        "public_traffic_scan_interval_seconds": 10,
        "public_traffic_frontend_refresh_seconds": 60,
    }
    with (
        patch.object(
            web_module,
            "get_settings",
            return_value=settings,
        ),
        patch.object(
            web_module,
            "create_controller",
            return_value=object(),
        ),
    ):
        app = web_module.create_app(open_service, controller=object())

    assert app.extensions["public_traffic_worker"] is None
    assert not traffic_path.exists()
    assert app.test_client().get(
        "/api/public/portal-counter"
    ).get_json()["traffic"]["available"] is False


def test_invalid_traffic_config_is_fail_safe_for_app(tmp_path):
    open_service = PortalCounterService(
        PortalCounterRepository(str(tmp_path / "open.db"))
    )
    assert open_service.initialize()
    settings = {
        "portal_counter_enabled": True,
        "portal_counter_db_path": str(tmp_path / "open.db"),
        "portal_counter_timezone": "Asia/Baku",
        "portal_counter_api_enabled": True,
        "public_traffic_counter_enabled": True,
        "public_traffic_ssid": "SafeSSID",
        "public_traffic_db_path": str(tmp_path / "traffic.db"),
        "omada_webhook_normalized_log_file": str(tmp_path / "log"),
        "public_traffic_scan_interval_seconds": 0,
        "public_traffic_frontend_refresh_seconds": 60,
    }
    with (
        patch.object(
            web_module,
            "get_settings",
            return_value=settings,
        ),
        patch.object(
            web_module,
            "create_controller",
            return_value=object(),
        ),
    ):
        app = web_module.create_app(open_service, controller=object())

    payload = app.test_client().get(
        "/api/public/portal-counter"
    ).get_json()
    assert payload["opened_total"] == 0
    assert payload["traffic"] == {
        "available": False,
        "ssid": "SafeSSID",
    }
    assert app.extensions["public_traffic_worker"] is None


def test_create_app_constructs_but_does_not_start_worker(tmp_path):
    open_service = PortalCounterService(
        PortalCounterRepository(str(tmp_path / "open.db"))
    )
    assert open_service.initialize()
    settings = {
        "portal_counter_enabled": True,
        "portal_counter_db_path": str(tmp_path / "open.db"),
        "portal_counter_timezone": "Asia/Baku",
        "portal_counter_api_enabled": True,
        "public_traffic_counter_enabled": True,
        "public_traffic_ssid": "Zefer_Parki",
        "public_traffic_db_path": str(tmp_path / "traffic.db"),
        "omada_webhook_normalized_log_file": str(tmp_path / "log"),
        "public_traffic_scan_interval_seconds": 10,
        "public_traffic_frontend_refresh_seconds": 60,
    }
    with (
        patch.object(
            web_module,
            "get_settings",
            return_value=settings,
        ),
        patch.object(
            web_module,
            "create_controller",
            return_value=object(),
        ),
    ):
        first = web_module.create_app(open_service, controller=object())
        second = web_module.create_app(open_service, controller=object())

    assert not first.extensions["public_traffic_worker"].running
    assert not second.extensions["public_traffic_worker"].running
