import sqlite3
import stat
import threading
from datetime import timedelta

import pytest

from app.device_fingerprint.models import (
    DeviceFingerprintConflict, DeviceFingerprintStorageCorrupt,
    DeviceFingerprintStorageLimit, DeviceFingerprintStorageUnavailable,
    DeviceFingerprintWriterUnavailable,
)
from app.device_fingerprint.repository import (
    DeviceFingerprintRepository, _prepare_local_file_target, open_read_only,
    writer_lock,
)
from app.device_fingerprint.schema import (
    EXPECTED_COLUMNS, EXPECTED_INDEXES, REQUIRED_CHECK_FRAGMENTS,
)
from app.device_fingerprint.service import DeviceFingerprintService
from app.device_fingerprint.schema_registry import EvidenceSchemaRegistry
from app.device_fingerprint.validation import format_utc
from tests.device_fingerprint import NOW, config, evidence_event, health_event, producer


def initialized(tmp_path):
    cfg = config(tmp_path)
    repo = DeviceFingerprintRepository(cfg.db_path, max_db_bytes=cfg.max_db_bytes)
    repo.initialize()
    return cfg, repo


def service(tmp_path):
    cfg, repo = initialized(tmp_path)
    registry = EvidenceSchemaRegistry()
    registry.register("dhcp", 1, lambda value: dict(value) if set(value) == {"vendor_class"} else (_ for _ in ()).throw(ValueError()))
    registry.freeze()
    return cfg, repo, DeviceFingerprintService(cfg, repo, registry, now=lambda: NOW)


def test_schema_v2_exact_tables_indexes_pragmas_and_read_only(tmp_path):
    import app.device_fingerprint.config as constants
    assert (constants.BUSY_TIMEOUT_MS, constants.WAL_AUTOCHECKPOINT_PAGES,
            constants.JOURNAL_SIZE_LIMIT_BYTES, constants.RETENTION_DELETE_CHUNK_ROWS,
            constants.MAX_RETENTION_CHUNKS_PER_PASS,
            constants.SOURCE_HEALTH_RETENTION_DAYS) == (500, 1000, 67_108_864, 500, 20, 30)
    cfg, repo = initialized(tmp_path)
    connection = repo.connection
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
    assert {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")} == {"device_fingerprint_evidence", "device_fingerprint_source_health_events", "device_fingerprint_storage_state"}
    assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 500
    assert connection.execute("PRAGMA synchronous").fetchone()[0] == 1
    assert connection.execute("PRAGMA journal_size_limit").fetchone()[0] == 67_108_864
    assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    assert connection.execute("PRAGMA max_page_count").fetchone()[0] == cfg.max_db_bytes // connection.execute("PRAGMA page_size").fetchone()[0]
    expected_indexes = {
        "uq_df_evidence_producer_event": ("producer_id", "source_event_id"),
        "idx_df_evidence_site_mac_time": ("site_id", "observed_mac", "observed_at", "evidence_id"),
        "idx_df_evidence_site_kind_time": ("site_id", "source_kind", "observed_at", "evidence_id"),
        "idx_df_evidence_retention": ("observed_at", "evidence_id"),
    }
    for name, columns in expected_indexes.items():
        assert tuple(row[2] for row in connection.execute(f"PRAGMA index_info({name})")) == columns
    for table, expected in EXPECTED_COLUMNS.items():
        actual = tuple(
            (row[1], row[2].upper(), row[3], row[5])
            for row in connection.execute(f"PRAGMA table_info({table})")
        )
        assert actual == expected
        table_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()[0]
        normalized = "".join(table_sql.lower().split())
        assert all(fragment in normalized for fragment in REQUIRED_CHECK_FRAGMENTS[table])
        actual_indexes = {}
        for row in connection.execute(f"PRAGMA index_list({table})"):
            if row[1].startswith("sqlite_autoindex"):
                continue
            actual_indexes[row[1]] = (
                row[2], tuple(item[2] for item in connection.execute(f"PRAGMA index_info({row[1]})"))
            )
        assert actual_indexes == EXPECTED_INDEXES[table]
    reader = open_read_only(cfg.db_path)
    try:
        assert reader.execute("PRAGMA query_only").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            reader.execute("DELETE FROM device_fingerprint_evidence")
    finally:
        reader.close()


def test_partial_or_newer_schema_fails_closed(tmp_path):
    path = tmp_path / "fingerprint.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE device_fingerprint_evidence (bad TEXT)")
    connection.commit(); connection.close()
    with pytest.raises(DeviceFingerprintStorageCorrupt):
        DeviceFingerprintRepository(str(path), max_db_bytes=67_108_864).initialize()
    path.unlink()
    connection = sqlite3.connect(path); connection.execute("PRAGMA user_version=2"); connection.commit(); connection.close()
    with pytest.raises(DeviceFingerprintStorageCorrupt):
        DeviceFingerprintRepository(str(path), max_db_bytes=67_108_864).initialize()


def test_extra_column_is_strict_schema_error(tmp_path):
    cfg, repo = initialized(tmp_path); repo.connection.execute("ALTER TABLE device_fingerprint_evidence ADD COLUMN unexpected TEXT"); repo.close()
    with pytest.raises(DeviceFingerprintStorageCorrupt):
        DeviceFingerprintRepository(cfg.db_path, max_db_bytes=cfg.max_db_bytes).initialize()


def test_evidence_atomic_idempotency_and_conflict(tmp_path):
    _cfg, repo, svc = service(tmp_path)
    root = {"producer_id": producer().producer_id, "events": [evidence_event()]}
    assert svc.evidence_batch(producer(), root).inserted == 1
    assert svc.evidence_batch(producer(), root).duplicate_noop == 1
    second = evidence_event(source_event_id="33333333-3333-4333-8333-333333333333")
    assert svc.evidence_batch(producer(), {"producer_id": producer().producer_id, "events": [evidence_event(), second]}).inserted == 1
    conflicting = evidence_event(payload={"vendor_class": "other"})
    new = evidence_event(source_event_id="44444444-4444-4444-8444-444444444444")
    with pytest.raises(DeviceFingerprintConflict):
        svc.evidence_batch(producer(), {"producer_id": producer().producer_id, "events": [new, conflicting]})
    assert repo.connection.execute("SELECT COUNT(*) FROM device_fingerprint_evidence WHERE source_event_id=?", (new["source_event_id"],)).fetchone()[0] == 0
    stored = repo.connection.execute(
        "SELECT payload_json FROM device_fingerprint_evidence WHERE source_event_id=?",
        (conflicting["source_event_id"],),
    ).fetchone()[0]
    assert stored == '{"vendor_class":"android"}'


def test_source_health_idempotency_and_retention_clocks(tmp_path):
    cfg, repo, svc = service(tmp_path)
    root = {"producer_id": producer().producer_id, "events": [health_event()]}
    assert svc.source_health_batch(producer(), root).inserted == 1
    assert svc.source_health_batch(producer(), root).duplicate_noop == 1
    old = format_utc(NOW - timedelta(days=31))
    repo.connection.execute("UPDATE device_fingerprint_source_health_events SET observed_at=?,ingested_at=?", (old, format_utc(NOW)))
    deleted = repo.cleanup(now=NOW, evidence_retention_days=cfg.retention_days)
    assert deleted["device_fingerprint_source_health_events"] == 1


def test_source_health_conflict_rolls_back_new_rows(tmp_path):
    _cfg, repo, svc = service(tmp_path)
    first = health_event()
    svc.source_health_batch(producer(), {"producer_id": producer().producer_id, "events": [first]})
    new = health_event(source_health_event_id="55555555-5555-4555-8555-555555555555")
    conflict = health_event(status="unavailable")
    with pytest.raises(DeviceFingerprintConflict):
        svc.source_health_batch(producer(), {"producer_id": producer().producer_id, "events": [new, conflict]})
    assert repo.connection.execute("SELECT COUNT(*) FROM device_fingerprint_source_health_events").fetchone()[0] == 1


def test_same_payload_with_distinct_transport_ids_is_two_events(tmp_path):
    _cfg, repo, svc = service(tmp_path)
    first = evidence_event()
    second = evidence_event(source_event_id="66666666-6666-4666-8666-666666666666")
    result = svc.evidence_batch(producer(), {"producer_id": producer().producer_id, "events": [first, second]})
    assert result.inserted == 2
    assert repo.connection.execute("SELECT COUNT(*) FROM device_fingerprint_evidence").fetchone()[0] == 2


def test_writer_lock_is_exclusive(tmp_path):
    path = str(tmp_path / "writer.lock")
    with writer_lock(path):
        with pytest.raises(Exception):
            with writer_lock(path):
                pass


def test_sqlite_full_primary_code_maps_to_storage_limit():
    error = sqlite3.OperationalError("database or disk is full")
    error.sqlite_errorcode = 13
    assert isinstance(DeviceFingerprintRepository._sqlite_error(error), DeviceFingerprintStorageLimit)


@pytest.mark.parametrize("code", [5, 6, 8, 10, 14, 261, 262])
def test_temporary_sqlite_primary_and_extended_codes_map_to_unavailable(code):
    error = sqlite3.OperationalError("sensitive sqlite detail")
    error.sqlite_errorcode = code
    assert isinstance(
        DeviceFingerprintRepository._sqlite_error(error),
        DeviceFingerprintStorageUnavailable,
    )


@pytest.mark.parametrize("code", [11, 26, 267])
def test_corrupt_and_notadb_primary_codes_map_to_corrupt(code):
    error = sqlite3.DatabaseError("opaque")
    error.sqlite_errorcode = code
    assert isinstance(
        DeviceFingerprintRepository._sqlite_error(error),
        DeviceFingerprintStorageCorrupt,
    )


def test_constraint_and_unexpected_sqlite_codes_do_not_masquerade_as_unavailable():
    for code in (19, 1):
        error = sqlite3.IntegrityError("constraint failed")
        error.sqlite_errorcode = code
        mapped = DeviceFingerprintRepository._sqlite_error(error)
        assert isinstance(mapped, RuntimeError)
        assert not isinstance(mapped, DeviceFingerprintStorageUnavailable)


def test_message_fallback_is_used_only_without_result_code():
    locked = sqlite3.OperationalError("database is locked")
    corrupt = sqlite3.DatabaseError("database disk image is malformed")
    assert isinstance(DeviceFingerprintRepository._sqlite_error(locked), DeviceFingerprintStorageUnavailable)
    assert isinstance(DeviceFingerprintRepository._sqlite_error(corrupt), DeviceFingerprintStorageCorrupt)
    coded = sqlite3.OperationalError("database is locked")
    coded.sqlite_errorcode = 19
    assert isinstance(DeviceFingerprintRepository._sqlite_error(coded), RuntimeError)


def test_missing_unapproved_parent_and_unsafe_targets_fail_closed(tmp_path, monkeypatch):
    import app.device_fingerprint.repository as module
    missing = tmp_path / "unapproved" / "nested" / "db.sqlite3"
    with pytest.raises(DeviceFingerprintStorageUnavailable):
        _prepare_local_file_target(
            missing, error_type=DeviceFingerprintStorageUnavailable, label="repository"
        )
    assert not missing.parent.exists()

    unsafe_parent = tmp_path / "not-a-directory"
    unsafe_parent.write_text("x", encoding="utf-8")
    with pytest.raises(DeviceFingerprintStorageUnavailable):
        _prepare_local_file_target(
            unsafe_parent / "db.sqlite3",
            error_type=DeviceFingerprintStorageUnavailable,
            label="repository",
        )

    target = tmp_path / "target.sqlite3"
    target.write_text("x", encoding="utf-8")
    real_lstat = module.os.lstat
    monkeypatch.setattr(
        module.os, "lstat",
        lambda path: type("Metadata", (), {"st_mode": stat.S_IFLNK})()
        if str(path) == str(target) else real_lstat(path),
    )
    with pytest.raises(DeviceFingerprintStorageUnavailable):
        _prepare_local_file_target(
            target, error_type=DeviceFingerprintStorageUnavailable, label="repository"
        )


def test_missing_parent_may_be_created_only_inside_approved_root(tmp_path, monkeypatch):
    import app.device_fingerprint.repository as module
    approved = tmp_path / "approved-data"
    monkeypatch.setattr(module, "APPROVED_DATA_ROOT", approved)
    target = approved / "nested" / "fingerprint.sqlite3"
    assert _prepare_local_file_target(
        target, error_type=DeviceFingerprintStorageUnavailable, label="repository"
    ) == target
    assert target.parent.is_dir()
    escaped = approved / ".." / "escaped" / "fingerprint.sqlite3"
    with pytest.raises(DeviceFingerprintStorageUnavailable):
        _prepare_local_file_target(
            escaped, error_type=DeviceFingerprintStorageUnavailable, label="repository"
        )


def test_posix_database_mode_failure_fails_closed(tmp_path, monkeypatch):
    import app.device_fingerprint.repository as module
    cfg = config(tmp_path)
    monkeypatch.setattr(module, "_IS_POSIX", True)
    monkeypatch.setattr(module.os, "chmod", lambda *_args: (_ for _ in ()).throw(OSError("denied")))
    with pytest.raises(DeviceFingerprintStorageUnavailable):
        DeviceFingerprintRepository(cfg.db_path, max_db_bytes=cfg.max_db_bytes).initialize()


def test_posix_writer_lock_mode_failure_fails_closed(tmp_path, monkeypatch):
    import app.device_fingerprint.repository as module
    monkeypatch.setattr(module, "_IS_POSIX", True)
    monkeypatch.setattr(module.os, "chmod", lambda *_args: (_ for _ in ()).throw(OSError("denied")))
    with pytest.raises(DeviceFingerprintWriterUnavailable):
        with writer_lock(str(tmp_path / "writer.lock")):
            pass


def test_retention_is_strict_observed_time_and_bounded(tmp_path, monkeypatch):
    import app.device_fingerprint.repository as module
    cfg, repo, svc = service(tmp_path)
    cutoff = format_utc(NOW - timedelta(days=cfg.retention_days))
    old = format_utc(NOW - timedelta(days=cfg.retention_days, milliseconds=1))
    rows = []
    for number, observed in enumerate((old, old, cutoff), 1):
        item = evidence_event(source_event_id=f"{number:08d}-7777-4777-8777-777777777777", observed_at=observed)
        # Directly validate against a matching service clock so late-ingest rules do not obscure retention.
        svc._now = lambda observed=observed: NOW - timedelta(days=cfg.retention_days) if observed == cutoff else NOW - timedelta(days=cfg.retention_days, milliseconds=1)
        svc.evidence_batch(producer(), {"producer_id": producer().producer_id, "events": [item]})
    repo.connection.execute("UPDATE device_fingerprint_evidence SET ingested_at=?", (format_utc(NOW),))
    monkeypatch.setattr(module, "RETENTION_DELETE_CHUNK_ROWS", 1)
    monkeypatch.setattr(module, "MAX_RETENTION_CHUNKS_PER_PASS", 1)
    deleted = repo.cleanup(now=NOW, evidence_retention_days=cfg.retention_days)
    assert deleted["device_fingerprint_evidence"] == 1
    assert repo.connection.execute("SELECT COUNT(*) FROM device_fingerprint_evidence").fetchone()[0] == 2


def test_threaded_ingest_uses_one_serial_repository_boundary(tmp_path):
    _cfg, repo, svc = service(tmp_path); errors = []
    def write(number):
        try:
            item = evidence_event(source_event_id=f"{number:08d}-8888-4888-8888-888888888888")
            svc.evidence_batch(producer(), {"producer_id": producer().producer_id, "events": [item]})
        except Exception as exc:
            errors.append(exc)
    threads = [threading.Thread(target=write, args=(number,)) for number in (1, 2)]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    assert errors == []
    assert repo.connection.execute("SELECT COUNT(*) FROM device_fingerprint_evidence").fetchone()[0] == 2


def test_retention_uses_500_row_chunks_and_20_chunks_for_each_table(tmp_path):
    cfg, repo = initialized(tmp_path)
    calls = {"device_fingerprint_evidence": 0, "device_fingerprint_source_health_events": 0}
    real_execute = repo.connection.execute

    class Cursor:
        rowcount = 500

    def execute(sql, parameters=()):
        if sql.startswith("DELETE FROM "):
            table = sql.split()[2]
            assert parameters[1] == 500
            calls[table] += 1
            return Cursor()
        return real_execute(sql, parameters)

    class ConnectionProxy:
        def execute(self, sql, parameters=()):
            return execute(sql, parameters)

    real_connection = repo._connection
    repo._connection = ConnectionProxy()
    try:
        deleted = repo.cleanup(now=NOW, evidence_retention_days=cfg.retention_days)
    finally:
        repo._connection = real_connection
    assert calls == {
        "device_fingerprint_evidence": 20,
        "device_fingerprint_source_health_events": 20,
    }
    assert deleted == {
        "device_fingerprint_evidence": 10_000,
        "device_fingerprint_source_health_events": 10_000,
    }


def test_retention_never_uses_vacuum_and_journal_limit_does_not_block_cleanup(tmp_path):
    cfg, repo = initialized(tmp_path)
    unrelated = tmp_path / "unrelated.sqlite3"
    unrelated.write_bytes(b"unrelated-database-sentinel")
    before = unrelated.read_bytes()
    statements = []
    repo.connection.set_trace_callback(statements.append)
    repo.cleanup(now=NOW, evidence_retention_days=cfg.retention_days)
    assert all("vacuum" not in statement.lower() for statement in statements)
    assert repo.connection.execute("PRAGMA journal_size_limit").fetchone()[0] == 67_108_864
    assert unrelated.read_bytes() == before


def test_journal_size_limit_is_not_a_transient_wal_write_ceiling(tmp_path):
    cfg, repo, svc = service(tmp_path)
    repo.connection.execute("PRAGMA wal_autocheckpoint=0")
    repo.connection.execute("PRAGMA journal_size_limit=1")
    for number in range(1, 21):
        item = evidence_event(
            source_event_id=f"{number:08d}-9999-4999-8999-999999999999",
            payload={"vendor_class": "x" * 7000},
        )
        assert svc.evidence_batch(
            producer(), {"producer_id": producer().producer_id, "events": [item]}
        ).inserted == 1
    wal_path = cfg.db_path + "-wal"
    assert __import__("os").path.getsize(wal_path) > 1
    final = evidence_event(
        source_event_id="00000021-9999-4999-8999-999999999999",
        payload={"vendor_class": "still-writable"},
    )
    assert svc.evidence_batch(
        producer(), {"producer_id": producer().producer_id, "events": [final]}
    ).inserted == 1
    repo.cleanup(now=NOW, evidence_retention_days=cfg.retention_days)
