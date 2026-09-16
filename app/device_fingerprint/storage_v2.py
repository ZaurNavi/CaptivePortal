"""Explicit offline Task-01 schema migration and controlled generation recovery.

Neither operation is called by normal service startup. The caller must stop the
writer and retain the verified pre-migration backup for pre-v2 rollback.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path

from .config import BUSY_TIMEOUT_MS
from .models import DeviceFingerprintStorageCorrupt, DeviceFingerprintStorageUnavailable
from .repository import (
    DeviceFingerprintRepository, _create_v2_schema, _prepare_local_file_target,
    _enforce_posix_mode, writer_lock,
)
from .schema import (
    BOOTSTRAP_RULE_ID, EXPECTED_INDEXES, MAX_INGEST_SEQUENCE,
    STORAGE_STATE_TABLE, V1_EXPECTED_COLUMNS, V1_EXPECTED_INDEXES,
)

_EVIDENCE = "device_fingerprint_evidence"
_HEALTH = "device_fingerprint_source_health_events"
_LEGACY_EVIDENCE = "df_legacy_evidence"
_LEGACY_HEALTH = "df_legacy_source_health"
RECOVERY_TRIGGERS = frozenset({
    "DATABASE_BACKUP_RESTORE", "VM_SNAPSHOT_ROLLBACK", "FILESYSTEM_ROLLBACK",
    "DATABASE_REBUILD_FROM_OLDER_MATERIAL",
})


@dataclass(frozen=True, slots=True)
class MigrationResult:
    source_path: str
    source_bytes: int
    source_identity: str
    database_generation_id: str
    assigned_rows: int
    backup_sha256: str
    backup_bytes: int
    bootstrap_rule_id: str = BOOTSTRAP_RULE_ID


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    database_generation_id: str
    assigned_rows: int
    bootstrap_rule_id: str = BOOTSTRAP_RULE_ID


def migrate_v1_to_v2(db_path: str, *, writer_lock_path: str,
                     backup_path: str) -> MigrationResult:
    """Migrate a stopped v1 writer, retaining an independently verified v1 backup."""
    source_path = _existing_db(db_path)
    target = _prepare_local_file_target(
        Path(backup_path), error_type=DeviceFingerprintStorageUnavailable,
        label="migration backup",
    )
    if (target.exists()
            or target.resolve(strict=False) == source_path.resolve(strict=False)
            or target.resolve(strict=False) == Path(writer_lock_path).resolve(strict=False)):
        raise DeviceFingerprintStorageUnavailable("Fingerprint migration backup target is invalid")
    source_size = source_path.stat().st_size
    source_stat = source_path.stat()
    source_identity = f"{source_stat.st_dev}:{source_stat.st_ino}"
    wal_path = Path(str(source_path) + "-wal")
    wal_bytes = wal_path.stat().st_size if wal_path.is_file() else 0
    estimated_bytes = source_size + wal_bytes
    if (shutil.disk_usage(target.parent).free < max(16_777_216, estimated_bytes)
            or shutil.disk_usage(source_path.parent).free < max(16_777_216, estimated_bytes * 2)):
        raise DeviceFingerprintStorageUnavailable("Fingerprint migration capacity is insufficient")

    with writer_lock(writer_lock_path):
        locked_stat = source_path.stat()
        if ((locked_stat.st_dev, locked_stat.st_ino, locked_stat.st_size)
                != (source_stat.st_dev, source_stat.st_ino, source_size)):
            raise DeviceFingerprintStorageUnavailable("Fingerprint migration source changed")
        connection = _open_existing(source_path)
        try:
            DeviceFingerprintRepository.validate_v1_for_migration(connection)
            data_version = connection.execute("PRAGMA data_version").fetchone()[0]
            handle = os.open(target, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
            os.close(handle)
            backup = sqlite3.connect(str(target), isolation_level=None)
            try:
                connection.backup(backup)
                DeviceFingerprintRepository.validate_v1_for_migration(backup)
                _integrity_check(backup)
            finally:
                backup.close()
            if os.name == "posix":
                _enforce_posix_mode(
                    target, 0o640, error_type=DeviceFingerprintStorageUnavailable,
                    label="migration backup",
                )
            backup_bytes = target.stat().st_size
            backup_sha256 = _sha256(target)

            connection.execute("BEGIN EXCLUSIVE")
            try:
                if connection.execute("PRAGMA data_version").fetchone()[0] != data_version:
                    raise DeviceFingerprintStorageUnavailable("Fingerprint migration source changed")
                DeviceFingerprintRepository.validate_v1_for_migration(connection)
                _rename_v1_tables(connection)
                _create_v2_schema(connection)
                assigned = _copy_bootstrap_rows(connection)
                generation = str(uuid.uuid4())
                connection.execute(
                    f"INSERT INTO {STORAGE_STATE_TABLE} VALUES (1,?,?)",
                    (generation, assigned),
                )
                _verify_copy(connection, _LEGACY_EVIDENCE, _EVIDENCE)
                _verify_copy(connection, _LEGACY_HEALTH, _HEALTH)
                connection.execute(f"DROP TABLE {_LEGACY_EVIDENCE}")
                connection.execute(f"DROP TABLE {_LEGACY_HEALTH}")
                DeviceFingerprintRepository._validate_connection(connection)
                _integrity_check(connection)
                if _sha256(target) != backup_sha256 or target.stat().st_size != backup_bytes:
                    raise DeviceFingerprintStorageCorrupt("Fingerprint migration backup changed")
                connection.execute("COMMIT")
            except BaseException:
                connection.execute("ROLLBACK")
                raise
            return MigrationResult(
                str(source_path), source_size, source_identity,
                generation, assigned, backup_sha256, backup_bytes,
            )
        finally:
            connection.close()


def recover_database_generation(db_path: str, *, writer_lock_path: str,
                                trigger: str) -> RecoveryResult:
    """Rebaseline a known restored v2 database before admitting its writer."""
    if trigger not in RECOVERY_TRIGGERS:
        raise ValueError("Unsupported fingerprint generation recovery trigger")
    source_path = _existing_db(db_path)
    with writer_lock(writer_lock_path):
        connection = _open_existing(source_path)
        try:
            connection.execute("BEGIN EXCLUSIVE")
            try:
                DeviceFingerprintRepository._validate_connection(connection)
                for table in (_EVIDENCE, _HEALTH):
                    for name in EXPECTED_INDEXES[table]:
                        if name.endswith("_ingest_sequence"):
                            connection.execute(f"DROP INDEX {name}")
                assigned = _assign_sequences(connection, _EVIDENCE, _HEALTH)
                for table in (_EVIDENCE, _HEALTH):
                    for name in EXPECTED_INDEXES[table]:
                        if name.endswith("_ingest_sequence"):
                            connection.execute(f"CREATE UNIQUE INDEX {name} ON {table}(ingest_sequence)")
                previous_generation = connection.execute(
                    f"SELECT database_generation_id FROM {STORAGE_STATE_TABLE} WHERE singleton_id=1"
                ).fetchone()[0]
                generation = str(uuid.uuid4())
                while generation == previous_generation:
                    generation = str(uuid.uuid4())
                connection.execute(
                    f"UPDATE {STORAGE_STATE_TABLE} SET database_generation_id=?,last_ingest_sequence=? WHERE singleton_id=1",
                    (generation, assigned),
                )
                DeviceFingerprintRepository._validate_connection(connection)
                _integrity_check(connection)
                connection.execute("COMMIT")
            except BaseException:
                connection.execute("ROLLBACK")
                raise
            return RecoveryResult(generation, assigned)
        finally:
            connection.close()


def _existing_db(db_path: str) -> Path:
    path = _prepare_local_file_target(
        Path(db_path), error_type=DeviceFingerprintStorageUnavailable,
        label="repository",
    )
    if not path.is_file():
        raise DeviceFingerprintStorageUnavailable("Fingerprint repository is unavailable")
    return path


def _open_existing(path: Path) -> sqlite3.Connection:
    try:
        connection = sqlite3.connect(
            path.as_uri() + "?mode=rw", uri=True,
            timeout=BUSY_TIMEOUT_MS / 1000, isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection
    except sqlite3.DatabaseError as exc:
        raise DeviceFingerprintStorageUnavailable("Fingerprint repository is unavailable") from exc


def _rename_v1_tables(connection: sqlite3.Connection) -> None:
    connection.execute(f"ALTER TABLE {_EVIDENCE} RENAME TO {_LEGACY_EVIDENCE}")
    connection.execute(f"ALTER TABLE {_HEALTH} RENAME TO {_LEGACY_HEALTH}")
    for indexes in V1_EXPECTED_INDEXES.values():
        for name in indexes:
            connection.execute(f"DROP INDEX {name}")


def _ordered_rows(connection: sqlite3.Connection, evidence_table: str,
                  health_table: str):
    return connection.execute(
        f"SELECT ingested_at,0 AS family,evidence_id AS row_id FROM {evidence_table} "
        f"UNION ALL SELECT ingested_at,1 AS family,source_health_id AS row_id FROM {health_table} "
        "ORDER BY ingested_at,family,row_id"
    )


def _copy_bootstrap_rows(connection: sqlite3.Connection) -> int:
    assigned = 0
    for row in _ordered_rows(connection, _LEGACY_EVIDENCE, _LEGACY_HEALTH):
        if assigned >= MAX_INGEST_SEQUENCE:
            raise DeviceFingerprintStorageCorrupt("Fingerprint migration sequence capacity is exhausted")
        assigned += 1
        if row[1] == 0:
            connection.execute(
                f"INSERT INTO {_EVIDENCE} SELECT *,? FROM {_LEGACY_EVIDENCE} WHERE evidence_id=?",
                (assigned, row[2]),
            )
        else:
            connection.execute(
                f"INSERT INTO {_HEALTH} SELECT *,? FROM {_LEGACY_HEALTH} WHERE source_health_id=?",
                (assigned, row[2]),
            )
    return assigned


def _assign_sequences(connection: sqlite3.Connection, evidence_table: str,
                      health_table: str) -> int:
    assigned = 0
    for row in _ordered_rows(connection, evidence_table, health_table):
        if assigned >= MAX_INGEST_SEQUENCE:
            raise DeviceFingerprintStorageCorrupt("Fingerprint recovery sequence capacity is exhausted")
        assigned += 1
        if row[1] == 0:
            connection.execute(
                f"UPDATE {_EVIDENCE} SET ingest_sequence=? WHERE evidence_id=?", (assigned, row[2]),
            )
        else:
            connection.execute(
                f"UPDATE {_HEALTH} SET ingest_sequence=? WHERE source_health_id=?", (assigned, row[2]),
            )
    return assigned


def _verify_copy(connection: sqlite3.Connection, old_table: str, new_table: str) -> None:
    columns = ",".join(column[0] for column in V1_EXPECTED_COLUMNS[new_table])
    if connection.execute(f"SELECT COUNT(*) FROM {old_table}").fetchone()[0] != connection.execute(
        f"SELECT COUNT(*) FROM {new_table}"
    ).fetchone()[0]:
        raise DeviceFingerprintStorageCorrupt("Fingerprint migration row count changed")
    for first, second in ((old_table, new_table), (new_table, old_table)):
        if connection.execute(
            f"SELECT {columns} FROM {first} EXCEPT SELECT {columns} FROM {second} LIMIT 1"
        ).fetchone() is not None:
            raise DeviceFingerprintStorageCorrupt("Fingerprint migration row contents changed")


def _integrity_check(connection: sqlite3.Connection) -> None:
    if [row[0] for row in connection.execute("PRAGMA integrity_check")] != ["ok"]:
        raise DeviceFingerprintStorageCorrupt("Fingerprint repository is corrupt")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
