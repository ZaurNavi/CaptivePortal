"""Focused Task-01 storage-v2 migration, sequence and recovery proofs."""

import hashlib
import sqlite3
import uuid
from datetime import timedelta
from pathlib import Path

import pytest

from app.device_fingerprint.models import (
    DeviceFingerprintConflict, DeviceFingerprintMigrationRequired,
    DeviceFingerprintStorageCorrupt, DeviceFingerprintStorageLimit,
    DeviceFingerprintWriterUnavailable,
)
from app.device_fingerprint.repository import DeviceFingerprintRepository, open_read_only, writer_lock
from app.device_fingerprint.schema import (
    BOOTSTRAP_RULE_ID, MAX_INGEST_SEQUENCE, SCHEMA_SQL, V1_EXPECTED_COLUMNS,
)
from app.device_fingerprint.storage_v2 import (
    migrate_v1_to_v2, recover_database_generation,
)
from app.device_fingerprint.validation import format_utc
from tests.device_fingerprint import NOW, evidence_event, health_event, producer
from tests.device_fingerprint.test_repository import service


def _watermark(repo):
    return DeviceFingerprintRepository.read_ingest_watermark(repo.connection)


def _batch_evidence(svc, *events):
    return svc.evidence_batch(producer(), {"producer_id": producer().producer_id, "events": list(events)})


def _batch_health(svc, *events):
    return svc.source_health_batch(producer(), {"producer_id": producer().producer_id, "events": list(events)})


def _generation(value):
    parsed = uuid.UUID(value)
    assert parsed.version == 4
    assert str(parsed) == value


def _assert_storage_cap(connection, max_db_bytes):
    page_size = connection.execute("PRAGMA page_size").fetchone()[0]
    page_count = connection.execute("PRAGMA page_count").fetchone()[0]
    effective_max_pages = connection.execute("PRAGMA max_page_count").fetchone()[0]
    assert page_size * page_count <= max_db_bytes
    assert effective_max_pages <= max_db_bytes // page_size


def _v1_sql():
    statements = []
    for statement in SCHEMA_SQL.split(";"):
        if not statement.strip():
            continue
        if "device_fingerprint_storage_state" in statement:
            continue
        if "_ingest_sequence" in statement and "CREATE UNIQUE INDEX" in statement:
            continue
        if "PRAGMA user_version" in statement:
            statements.append("PRAGMA user_version=1")
            continue
        statements.append(statement.replace(
            ",\n ingest_sequence INTEGER NOT NULL CHECK(ingest_sequence BETWEEN 1 AND 9223372036854775807)",
            "",
        ))
    return ";".join(statements) + ";"


def _representative_v1(tmp_path):
    _cfg, seed, svc = service(tmp_path)
    _batch_evidence(svc, evidence_event())
    _batch_health(svc, health_event())
    _batch_evidence(svc, evidence_event(source_event_id="33333333-3333-4333-8333-333333333333"))
    legacy = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(legacy)
    connection.executescript(_v1_sql())
    for table in ("device_fingerprint_evidence", "device_fingerprint_source_health_events"):
        columns = tuple(item[0] for item in V1_EXPECTED_COLUMNS[table])
        rows = seed.connection.execute(f"SELECT {','.join(columns)} FROM {table}").fetchall()
        connection.executemany(
            f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
            [tuple(row) for row in rows],
        )
    # The second evidence row is historically ingested earliest, followed by
    # evidence then health at an equal time (family rank breaks the tie).
    connection.execute(
        "UPDATE device_fingerprint_evidence SET ingested_at='2026-09-14T11:59:59.000Z' "
        "WHERE source_event_id='33333333-3333-4333-8333-333333333333'"
    )
    connection.commit()
    before = {
        table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY 1")]
        for table in V1_EXPECTED_COLUMNS
    }
    connection.close()
    seed.close()
    return legacy, before


def test_fresh_v2_empty_generation_and_atomic_existing_snapshot(tmp_path):
    cfg, repo, svc = service(tmp_path)
    initial = _watermark(repo)
    _generation(initial["database_generation_id"])
    assert initial["max_committed_ingest_sequence"] == 0
    assert repo.connection.execute("PRAGMA user_version").fetchone()[0] == 2
    _assert_storage_cap(repo.connection, cfg.max_db_bytes)
    reader = open_read_only(repo.db_path)
    try:
        reader.execute("BEGIN")
        assert DeviceFingerprintRepository.read_ingest_watermark(reader) == initial
        _batch_evidence(svc, evidence_event())
        assert DeviceFingerprintRepository.read_ingest_watermark(reader) == initial
        reader.execute("COMMIT")
        assert DeviceFingerprintRepository.read_ingest_watermark(reader)["max_committed_ingest_sequence"] == 1
    finally:
        reader.close()


def test_shared_sequence_duplicates_conflict_cleanup_and_exhaustion(tmp_path):
    cfg, repo, svc = service(tmp_path)
    generation = _watermark(repo)["database_generation_id"]
    first = evidence_event()
    second = evidence_event(source_event_id="33333333-3333-4333-8333-333333333333")
    assert _batch_evidence(svc, first).inserted == 1
    assert _batch_health(svc, health_event()).inserted == 1
    result = _batch_evidence(svc, first, second)
    assert (result.inserted, result.duplicate_noop) == (1, 1)
    assert _watermark(repo) == {
        "database_generation_id": generation, "max_committed_ingest_sequence": 3,
    }
    assert [row[0] for row in repo.connection.execute(
        "SELECT ingest_sequence FROM device_fingerprint_evidence ORDER BY ingest_sequence"
    )] == [1, 3]
    assert repo.connection.execute(
        "SELECT ingest_sequence FROM device_fingerprint_source_health_events"
    ).fetchone()[0] == 2
    third = evidence_event(source_event_id="44444444-4444-4444-8444-444444444444")
    with pytest.raises(DeviceFingerprintConflict):
        _batch_evidence(svc, third, evidence_event(payload={"vendor_class": "conflict"}))
    assert _watermark(repo)["max_committed_ingest_sequence"] == 3
    assert repo.connection.execute(
        "SELECT COUNT(*) FROM device_fingerprint_evidence WHERE source_event_id=?",
        (third["source_event_id"],),
    ).fetchone()[0] == 0
    repo.connection.execute(
        "UPDATE device_fingerprint_evidence SET observed_at=? WHERE ingest_sequence=1",
        (format_utc(NOW - timedelta(days=31)),),
    )
    deleted = repo.cleanup(now=NOW, evidence_retention_days=cfg.retention_days)
    assert deleted["device_fingerprint_evidence"] == 1
    assert _watermark(repo)["max_committed_ingest_sequence"] == 3
    _batch_evidence(svc, third)
    assert _watermark(repo)["max_committed_ingest_sequence"] == 4
    repo.connection.execute(
        "UPDATE device_fingerprint_storage_state SET last_ingest_sequence=?",
        (MAX_INGEST_SEQUENCE - 1,),
    )
    with pytest.raises(DeviceFingerprintStorageLimit):
        _batch_evidence(
            svc,
            evidence_event(source_event_id="55555555-5555-4555-8555-555555555555"),
            evidence_event(source_event_id="66666666-6666-4666-8666-666666666666"),
        )
    assert _watermark(repo)["max_committed_ingest_sequence"] == MAX_INGEST_SEQUENCE - 1
    assert repo.connection.execute("SELECT COUNT(*) FROM device_fingerprint_evidence").fetchone()[0] == 2
    _batch_evidence(svc, evidence_event(source_event_id="55555555-5555-4555-8555-555555555555"))
    assert _batch_evidence(svc, second).duplicate_noop == 1
    with pytest.raises(DeviceFingerprintStorageLimit):
        _batch_evidence(svc, evidence_event(source_event_id="66666666-6666-4666-8666-666666666666"))
    assert _watermark(repo)["max_committed_ingest_sequence"] == MAX_INGEST_SEQUENCE
    assert repo.connection.execute("SELECT COUNT(*) FROM device_fingerprint_evidence").fetchone()[0] == 3
    repo.close()
    reopened = DeviceFingerprintRepository(cfg.db_path, max_db_bytes=cfg.max_db_bytes)
    reopened.initialize()
    reopened.close()


def test_explicit_v1_migration_preserves_rows_backup_and_bootstrap_order(tmp_path):
    legacy, before = _representative_v1(tmp_path)
    with pytest.raises(DeviceFingerprintMigrationRequired, match="migration is required"):
        DeviceFingerprintRepository(str(legacy), max_db_bytes=67_108_864).initialize()
    assert sqlite3.connect(legacy).execute("PRAGMA user_version").fetchone()[0] == 1
    backup = tmp_path / "verified-v1-backup.sqlite3"
    result = migrate_v1_to_v2(
        str(legacy), writer_lock_path=str(tmp_path / "offline.lock"),
        backup_path=str(backup), max_db_bytes=67_108_864,
    )
    assert result.assigned_rows == 3
    assert result.bootstrap_rule_id == BOOTSTRAP_RULE_ID
    assert result.source_path == str(legacy)
    assert result.source_bytes > 0
    assert result.source_identity
    _generation(result.database_generation_id)
    assert hashlib.sha256(backup.read_bytes()).hexdigest() == result.backup_sha256
    assert len(backup.read_bytes()) == result.backup_bytes
    preserved_backup = sqlite3.connect(backup)
    DeviceFingerprintRepository.validate_v1_for_migration(preserved_backup)
    assert preserved_backup.execute("PRAGMA user_version").fetchone()[0] == 1
    preserved_backup.close()
    repo = DeviceFingerprintRepository(str(legacy), max_db_bytes=67_108_864)
    repo.initialize()
    _assert_storage_cap(repo.connection, 67_108_864)
    assert _watermark(repo) == {
        "database_generation_id": result.database_generation_id,
        "max_committed_ingest_sequence": 3,
    }
    for table in V1_EXPECTED_COLUMNS:
        columns = ",".join(column[0] for column in V1_EXPECTED_COLUMNS[table])
        after = [tuple(row) for row in repo.connection.execute(f"SELECT {columns} FROM {table} ORDER BY 1")]
        assert after == before[table]
    ordered = [tuple(row) for row in repo.connection.execute(
        "SELECT ingested_at,0 AS family,evidence_id AS row_id,ingest_sequence FROM device_fingerprint_evidence "
        "UNION ALL SELECT ingested_at,1,source_health_id,ingest_sequence "
        "FROM device_fingerprint_source_health_events ORDER BY ingested_at,family,row_id"
    )]
    assert [row[3] for row in ordered] == [1, 2, 3]
    # Bootstrap follows retained ingested_at, not the historical insert order.
    assert repo.connection.execute(
        "SELECT ingest_sequence FROM device_fingerprint_evidence WHERE source_event_id=?",
        ("33333333-3333-4333-8333-333333333333",),
    ).fetchone()[0] == 1
    assert repo.connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    assert repo.connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    repo.close()


def test_empty_v1_migration_has_new_generation_and_zero_watermark(tmp_path):
    legacy = tmp_path / "empty-v1.sqlite3"
    connection = sqlite3.connect(legacy)
    connection.executescript(_v1_sql())
    connection.close()
    result = migrate_v1_to_v2(
        str(legacy), writer_lock_path=str(tmp_path / "offline.lock"),
        backup_path=str(tmp_path / "empty-v1-backup.sqlite3"),
        max_db_bytes=67_108_864,
    )
    assert result.assigned_rows == 0
    _generation(result.database_generation_id)
    repo = DeviceFingerprintRepository(str(legacy), max_db_bytes=67_108_864)
    repo.initialize()
    _assert_storage_cap(repo.connection, 67_108_864)
    assert _watermark(repo) == {
        "database_generation_id": result.database_generation_id,
        "max_committed_ingest_sequence": 0,
    }
    repo.close()


def test_controlled_restore_recovery_rebaselines_both_families(tmp_path):
    cfg, repo, svc = service(tmp_path)
    _batch_evidence(svc, evidence_event())
    _batch_health(svc, health_event())
    _batch_evidence(svc, evidence_event(source_event_id="33333333-3333-4333-8333-333333333333"))
    old_generation = _watermark(repo)["database_generation_id"]
    repo.connection.execute(
        "UPDATE device_fingerprint_evidence SET ingested_at='2026-09-14T11:59:59.000Z' "
        "WHERE source_event_id='33333333-3333-4333-8333-333333333333'"
    )
    repo.close()
    result = recover_database_generation(
        cfg.db_path, writer_lock_path=cfg.writer_lock_path,
        trigger="DATABASE_BACKUP_RESTORE", max_db_bytes=cfg.max_db_bytes,
    )
    assert result.assigned_rows == 3
    assert result.database_generation_id != old_generation
    _generation(result.database_generation_id)
    repo.initialize()
    assert _watermark(repo)["max_committed_ingest_sequence"] == 3
    assert _watermark(repo)["database_generation_id"] == result.database_generation_id
    ordered = [row[0] for row in repo.connection.execute(
        "SELECT ingest_sequence FROM device_fingerprint_evidence "
        "UNION ALL SELECT ingest_sequence FROM device_fingerprint_source_health_events "
        "ORDER BY ingest_sequence"
    )]
    assert ordered == [1, 2, 3]
    assert repo.connection.execute(
        "SELECT ingest_sequence FROM device_fingerprint_evidence WHERE source_event_id=?",
        ("33333333-3333-4333-8333-333333333333",),
    ).fetchone()[0] == 1
    assert repo.connection.execute(
        "SELECT ingest_sequence FROM device_fingerprint_source_health_events"
    ).fetchone()[0] == 3
    repo.close()


def test_failed_migration_rolls_back_to_untouched_v1(tmp_path, monkeypatch):
    import app.device_fingerprint.storage_v2 as storage

    legacy, before = _representative_v1(tmp_path)

    def fail_verification(*_args):
        raise DeviceFingerprintStorageCorrupt("Fingerprint migration validation failed")

    monkeypatch.setattr(storage, "_verify_copy", fail_verification)
    backup = tmp_path / "pre-migration-backup.sqlite3"
    with pytest.raises(DeviceFingerprintStorageCorrupt):
        migrate_v1_to_v2(
            str(legacy), writer_lock_path=str(tmp_path / "offline.lock"),
            backup_path=str(backup), max_db_bytes=67_108_864,
        )
    connection = sqlite3.connect(legacy)
    DeviceFingerprintRepository.validate_v1_for_migration(connection)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
    for table in V1_EXPECTED_COLUMNS:
        assert [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY 1")] == before[table]
    connection.close()
    assert backup.is_file()


def test_wal_backed_v1_migration_preserves_committed_evidence_and_health(tmp_path):
    legacy, _before = _representative_v1(tmp_path)
    holder = sqlite3.connect(legacy)
    try:
        assert holder.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() == "wal"
        holder.execute(
            "UPDATE device_fingerprint_source_health_events "
            "SET ingested_at='2026-09-14T11:59:58.000Z'"
        )
        holder.commit()
        wal_path = Path(str(legacy) + "-wal")
        assert wal_path.is_file() and wal_path.stat().st_size > 0
        before = {
            table: [tuple(row) for row in holder.execute(f"SELECT * FROM {table} ORDER BY 1")]
            for table in V1_EXPECTED_COLUMNS
        }
        backup = tmp_path / "wal-v1-backup.sqlite3"
        result = migrate_v1_to_v2(
            str(legacy), writer_lock_path=str(tmp_path / "offline.lock"),
            backup_path=str(backup), max_db_bytes=67_108_864,
        )
    finally:
        holder.close()
    _generation(result.database_generation_id)
    assert result.assigned_rows == 3
    saved = sqlite3.connect(backup)
    try:
        DeviceFingerprintRepository.validate_v1_for_migration(saved)
        assert saved.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        for table in V1_EXPECTED_COLUMNS:
            assert [tuple(row) for row in saved.execute(f"SELECT * FROM {table} ORDER BY 1")] == before[table]
    finally:
        saved.close()
    repo = DeviceFingerprintRepository(str(legacy), max_db_bytes=67_108_864)
    repo.initialize()
    try:
        assert repo.connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert repo.connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert repo.connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert repo.connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert _watermark(repo) == {
            "database_generation_id": result.database_generation_id,
            "max_committed_ingest_sequence": 3,
        }
        for table in V1_EXPECTED_COLUMNS:
            columns = ",".join(column[0] for column in V1_EXPECTED_COLUMNS[table])
            assert [tuple(row) for row in repo.connection.execute(
                f"SELECT {columns} FROM {table} ORDER BY 1"
            )] == before[table]
        assert repo.connection.execute(
            "SELECT ingest_sequence FROM device_fingerprint_source_health_events"
        ).fetchone()[0] == 1
        assert repo.connection.execute(
            "SELECT ingest_sequence FROM device_fingerprint_evidence WHERE source_event_id=?",
            ("33333333-3333-4333-8333-333333333333",),
        ).fetchone()[0] == 2
        _assert_storage_cap(repo.connection, 67_108_864)
    finally:
        repo.close()


def test_migration_over_cap_rolls_back_and_retains_verified_v1_backup(tmp_path):
    legacy, _before = _representative_v1(tmp_path)
    connection = sqlite3.connect(legacy)
    connection.row_factory = sqlite3.Row
    columns = tuple(column[0] for column in V1_EXPECTED_COLUMNS["device_fingerprint_evidence"])
    template = dict(connection.execute("SELECT * FROM device_fingerprint_evidence LIMIT 1").fetchone())
    for index in range(80):
        row = dict(template)
        row["evidence_id"] = str(uuid.uuid4())
        row["source_event_id"] = str(uuid.uuid4())
        row["payload_json"] = '{"blob":"' + "x" * 3000 + str(index) + '"}'
        row["payload_sha256"] = hashlib.sha256(row["payload_json"].encode()).hexdigest()
        connection.execute(
            "INSERT INTO device_fingerprint_evidence (" + ",".join(columns) + ") "
            "VALUES (" + ",".join("?" for _ in columns) + ")",
            tuple(row[column] for column in columns),
        )
    connection.commit()
    connection.execute("VACUUM")
    page_size = connection.execute("PRAGMA page_size").fetchone()[0]
    original_pages = connection.execute("PRAGMA page_count").fetchone()[0]
    before_count = connection.execute("SELECT COUNT(*) FROM device_fingerprint_evidence").fetchone()[0]
    connection.close()
    cap = page_size * original_pages
    backup = tmp_path / "over-cap-v1-backup.sqlite3"
    with pytest.raises(DeviceFingerprintStorageLimit):
        migrate_v1_to_v2(
            str(legacy), writer_lock_path=str(tmp_path / "offline.lock"),
            backup_path=str(backup), max_db_bytes=cap,
        )
    original = sqlite3.connect(legacy)
    saved = sqlite3.connect(backup)
    try:
        DeviceFingerprintRepository.validate_v1_for_migration(original)
        DeviceFingerprintRepository.validate_v1_for_migration(saved)
        assert original.execute("PRAGMA user_version").fetchone()[0] == 1
        assert saved.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert original.execute("SELECT COUNT(*) FROM device_fingerprint_evidence").fetchone()[0] == before_count
        assert saved.execute("SELECT COUNT(*) FROM device_fingerprint_evidence").fetchone()[0] == before_count
    finally:
        original.close()
        saved.close()


def test_existing_oversized_v2_fails_startup_and_recovery_without_cap_expansion(tmp_path):
    cfg, repo, svc = service(tmp_path)
    _batch_evidence(svc, evidence_event())
    generation = _watermark(repo)["database_generation_id"]
    page_size = repo.connection.execute("PRAGMA page_size").fetchone()[0]
    page_count = repo.connection.execute("PRAGMA page_count").fetchone()[0]
    assert page_count > 1
    repo.close()
    too_small = page_size * (page_count - 1)
    with pytest.raises(DeviceFingerprintStorageLimit):
        DeviceFingerprintRepository(cfg.db_path, max_db_bytes=too_small).initialize()
    with pytest.raises(DeviceFingerprintStorageLimit):
        recover_database_generation(
            cfg.db_path, writer_lock_path=cfg.writer_lock_path,
            trigger="DATABASE_BACKUP_RESTORE", max_db_bytes=too_small,
        )
    repo.initialize()
    try:
        assert _watermark(repo)["database_generation_id"] == generation
        _assert_storage_cap(repo.connection, cfg.max_db_bytes)
    finally:
        repo.close()


def test_recovery_growth_past_cap_rolls_back_without_generation_change(tmp_path, monkeypatch):
    import app.device_fingerprint.storage_v2 as storage

    cfg, repo, svc = service(tmp_path)
    _batch_evidence(svc, evidence_event())
    old_generation = _watermark(repo)["database_generation_id"]
    old_payload = repo.connection.execute(
        "SELECT payload_json FROM device_fingerprint_evidence"
    ).fetchone()[0]
    page_size = repo.connection.execute("PRAGMA page_size").fetchone()[0]
    cap = page_size * repo.connection.execute("PRAGMA page_count").fetchone()[0]
    repo.close()
    original_assign = storage._assign_sequences

    def simulate_growth(connection, evidence_table, health_table):
        assigned = original_assign(connection, evidence_table, health_table)
        payload = '{"blob":"' + "x" * (cap * 3) + '"}'
        connection.execute(
            "UPDATE device_fingerprint_evidence SET payload_json=?,payload_sha256=?",
            (payload, hashlib.sha256(payload.encode()).hexdigest()),
        )
        return assigned

    monkeypatch.setattr(storage, "_assign_sequences", simulate_growth)
    with pytest.raises(DeviceFingerprintStorageLimit):
        recover_database_generation(
            cfg.db_path, writer_lock_path=cfg.writer_lock_path,
            trigger="DATABASE_BACKUP_RESTORE", max_db_bytes=cap,
        )
    repo = DeviceFingerprintRepository(cfg.db_path, max_db_bytes=cap)
    repo.initialize()
    try:
        assert _watermark(repo)["database_generation_id"] == old_generation
        assert repo.connection.execute(
            "SELECT payload_json FROM device_fingerprint_evidence"
        ).fetchone()[0] == old_payload
        _assert_storage_cap(repo.connection, cap)
    finally:
        repo.close()


def test_offline_migration_requires_writer_lock(tmp_path):
    legacy, _before = _representative_v1(tmp_path)
    lock_path = str(tmp_path / "offline.lock")
    backup = tmp_path / "backup.sqlite3"
    with writer_lock(lock_path):
        with pytest.raises(DeviceFingerprintWriterUnavailable):
            migrate_v1_to_v2(
                str(legacy), writer_lock_path=lock_path,
                backup_path=str(backup), max_db_bytes=67_108_864,
            )
    assert not backup.exists()
    connection = sqlite3.connect(legacy)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
    connection.close()


def test_missing_singleton_and_newer_schema_fail_closed(tmp_path):
    cfg, repo, _svc = service(tmp_path)
    repo.close()
    connection = sqlite3.connect(cfg.db_path)
    connection.execute("DELETE FROM device_fingerprint_storage_state")
    connection.commit()
    connection.close()
    with pytest.raises(DeviceFingerprintStorageCorrupt):
        DeviceFingerprintRepository(cfg.db_path, max_db_bytes=cfg.max_db_bytes).initialize()
    connection = sqlite3.connect(cfg.db_path)
    connection.execute("PRAGMA user_version=3")
    connection.commit()
    connection.close()
    with pytest.raises(DeviceFingerprintStorageCorrupt):
        DeviceFingerprintRepository(cfg.db_path, max_db_bytes=cfg.max_db_bytes).initialize()


@pytest.mark.parametrize("corruption", ["invalid_generation", "low_allocator", "cross_family_duplicate"])
def test_corrupt_generation_or_sequence_fails_closed(tmp_path, corruption):
    cfg, repo, svc = service(tmp_path)
    _batch_evidence(svc, evidence_event())
    _batch_health(svc, health_event())
    repo.close()
    connection = sqlite3.connect(cfg.db_path)
    if corruption == "invalid_generation":
        connection.execute("UPDATE device_fingerprint_storage_state SET database_generation_id=?", (str(uuid.uuid1()),))
    elif corruption == "low_allocator":
        connection.execute("UPDATE device_fingerprint_storage_state SET last_ingest_sequence=1")
    else:
        connection.execute("UPDATE device_fingerprint_source_health_events SET ingest_sequence=1")
    connection.commit()
    connection.close()
    with pytest.raises(DeviceFingerprintStorageCorrupt):
        DeviceFingerprintRepository(cfg.db_path, max_db_bytes=cfg.max_db_bytes).initialize()
