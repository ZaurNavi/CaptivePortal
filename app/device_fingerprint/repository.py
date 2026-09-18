"""Strict isolated SQLite repository for fingerprint evidence."""

from __future__ import annotations

import os
import sqlite3
import stat
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from .config import (
    BUSY_TIMEOUT_MS,
    JOURNAL_SIZE_LIMIT_BYTES,
    MAX_RETENTION_CHUNKS_PER_PASS,
    RETENTION_DELETE_CHUNK_ROWS,
    SOURCE_HEALTH_RETENTION_MARGIN_SECONDS,
    WAL_AUTOCHECKPOINT_PAGES,
)
from .models import (
    BatchResult,
    DeviceFingerprintConflict,
    DeviceFingerprintMigrationRequired,
    DeviceFingerprintStorageCorrupt,
    DeviceFingerprintStorageLimit,
    DeviceFingerprintStorageUnavailable,
    DeviceFingerprintWriterUnavailable,
    ValidatedEvidence,
    ValidatedSourceHealth,
)
from .schema import (
    EXPECTED_COLUMNS, EXPECTED_INDEXES, MAX_INGEST_SEQUENCE,
    REQUIRED_CHECK_FRAGMENTS, SCHEMA_SQL, SCHEMA_VERSION, STORAGE_STATE_TABLE,
    V1_EXPECTED_COLUMNS, V1_EXPECTED_INDEXES, V1_REQUIRED_CHECK_FRAGMENTS,
)
from .validation import format_utc

UTC = timezone.utc
APPROVED_DATA_ROOT = Path("/opt/CaptivePortal/data")
_IS_POSIX = os.name == "posix"
_SQLITE_BUSY = 5
_SQLITE_LOCKED = 6
_SQLITE_READONLY = 8
_SQLITE_IOERR = 10
_SQLITE_CORRUPT = 11
_SQLITE_FULL = 13
_SQLITE_CANTOPEN = 14
_SQLITE_NOTADB = 26
_SQLITE_TEMPORARY_UNAVAILABLE = frozenset({
    _SQLITE_BUSY, _SQLITE_LOCKED, _SQLITE_READONLY, _SQLITE_IOERR,
    _SQLITE_CANTOPEN,
})
_SQLITE_CORRUPTION = frozenset({_SQLITE_CORRUPT, _SQLITE_NOTADB})


class DeviceFingerprintRepository:
    def __init__(self, db_path: str, *, max_db_bytes: int) -> None:
        self.db_path = str(db_path)
        self.max_db_bytes = max_db_bytes
        self._connection: sqlite3.Connection | None = None
        self._access_lock = threading.RLock()

    def initialize(self) -> None:
        path = _prepare_local_file_target(
            Path(self.db_path),
            error_type=DeviceFingerprintStorageUnavailable,
            label="repository",
        )
        try:
            connection = sqlite3.connect(
                self.db_path,
                timeout=BUSY_TIMEOUT_MS / 1000,
                isolation_level=None,
                check_same_thread=False,
            )
            connection.row_factory = sqlite3.Row
            self._configure_writer(connection)
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            tables = self._application_tables(connection)
            if version > SCHEMA_VERSION or (version == 0 and tables):
                raise DeviceFingerprintStorageCorrupt("Fingerprint schema is incompatible")
            if version == 1:
                raise DeviceFingerprintMigrationRequired("Fingerprint repository migration is required")
            if version == 0:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    _create_v2_schema(connection)
                    connection.execute(
                        f"INSERT INTO {STORAGE_STATE_TABLE} VALUES (1,?,0)",
                        (str(uuid.uuid4()),),
                    )
                    connection.execute("COMMIT")
                except BaseException:
                    connection.execute("ROLLBACK")
                    raise
            self._validate_connection(connection)
            enforce_storage_cap(connection, self.max_db_bytes)
            if _IS_POSIX:
                _enforce_posix_mode(
                    path, 0o640,
                    error_type=DeviceFingerprintStorageUnavailable,
                    label="repository",
                )
            self._connection = connection
        except (DeviceFingerprintStorageCorrupt, DeviceFingerprintStorageLimit,
                DeviceFingerprintStorageUnavailable):
            if "connection" in locals():
                connection.close()
            raise
        except sqlite3.DatabaseError as exc:
            if "connection" in locals():
                connection.close()
            raise self._sqlite_error(exc) from exc
        except OSError as exc:
            if "connection" in locals():
                connection.close()
            raise DeviceFingerprintStorageUnavailable("Fingerprint repository is unavailable") from exc

    def close(self) -> None:
        with self._access_lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    @property
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise DeviceFingerprintStorageUnavailable("Fingerprint repository is unavailable")
        return self._connection

    def validate_runtime_health(self) -> None:
        try:
            with self._access_lock:
                self._validate_connection(self.connection)
        except sqlite3.DatabaseError as exc:
            raise self._sqlite_error(exc) from exc

    def capacity(self) -> Mapping[str, int]:
        with self._access_lock:
            connection = self.connection
            return {
                "page_count": int(connection.execute("PRAGMA page_count").fetchone()[0]),
                "max_page_count": int(connection.execute("PRAGMA max_page_count").fetchone()[0]),
                "freelist_count": int(connection.execute("PRAGMA freelist_count").fetchone()[0]),
            }

    @staticmethod
    def read_ingest_watermark(connection: sqlite3.Connection) -> Mapping[str, int | str]:
        """Read both watermark fields from the caller's existing SQLite snapshot."""
        row = connection.execute(
            f"SELECT database_generation_id,last_ingest_sequence FROM {STORAGE_STATE_TABLE} WHERE singleton_id=1"
        ).fetchone()
        if row is None:
            raise DeviceFingerprintStorageCorrupt("Fingerprint generation state is invalid")
        return {
            "database_generation_id": row[0],
            "max_committed_ingest_sequence": row[1],
        }

    def ingest_evidence(self, events: Sequence[ValidatedEvidence], *, ingested_at: str) -> BatchResult:
        columns = tuple(ValidatedEvidence.__slots__)
        immutable = columns
        return self._ingest(
            table="device_fingerprint_evidence", id_column="evidence_id",
            producer_event_column="source_event_id", values=events,
            immutable=immutable, columns=columns, ingested_at=ingested_at,
        )

    def ingest_source_health(self, events: Sequence[ValidatedSourceHealth], *, ingested_at: str) -> BatchResult:
        columns = tuple(ValidatedSourceHealth.__slots__)
        return self._ingest(
            table="device_fingerprint_source_health_events", id_column="source_health_id",
            producer_event_column="source_health_event_id", values=events,
            immutable=columns, columns=columns, ingested_at=ingested_at,
        )

    def _ingest(self, *, table: str, id_column: str, producer_event_column: str,
                values: Sequence[Any], immutable: Sequence[str], columns: Sequence[str],
                ingested_at: str) -> BatchResult:
        inserted = duplicate = 0
        with self._access_lock:
            connection = self.connection
            try:
                connection.execute("BEGIN IMMEDIATE")
                watermark = self.read_ingest_watermark(connection)
                last_sequence = int(watermark["max_committed_ingest_sequence"])
                pending: dict[tuple[str, str], tuple[Any, ...]] = {}
                new_values: list[tuple[Any, tuple[Any, ...]]] = []
                for value in values:
                    key = (value.producer_id, getattr(value, producer_event_column))
                    expected = tuple(getattr(value, column) for column in immutable)
                    if key in pending:
                        if pending[key] != expected:
                            raise DeviceFingerprintConflict("Immutable fingerprint event conflict")
                        duplicate += 1
                        continue
                    existing = connection.execute(
                        f"SELECT {','.join(immutable)} FROM {table} WHERE producer_id=? AND {producer_event_column}=?",
                        key,
                    ).fetchone()
                    if existing is not None:
                        if tuple(existing[column] for column in immutable) != expected:
                            raise DeviceFingerprintConflict("Immutable fingerprint event conflict")
                        duplicate += 1
                        continue
                    pending[key] = expected
                    new_values.append((value, expected))
                if len(new_values) > MAX_INGEST_SEQUENCE - last_sequence:
                    raise DeviceFingerprintStorageLimit("Fingerprint ingest sequence exhausted")
                for _value, expected in new_values:
                    last_sequence += 1
                    names = (id_column,) + tuple(columns) + ("ingested_at", "ingest_sequence")
                    parameters = (str(uuid.uuid4()),) + expected + (ingested_at, last_sequence)
                    connection.execute(
                        f"INSERT INTO {table} ({','.join(names)}) VALUES ({','.join('?' for _ in names)})",
                        parameters,
                    )
                    inserted += 1
                if inserted:
                    connection.execute(
                        f"UPDATE {STORAGE_STATE_TABLE} SET last_ingest_sequence=? WHERE singleton_id=1",
                        (last_sequence,),
                    )
                connection.execute("COMMIT")
            except sqlite3.DatabaseError as exc:
                try:
                    connection.execute("ROLLBACK")
                except sqlite3.DatabaseError:
                    pass
                raise self._sqlite_error(exc) from exc
            except Exception:
                connection.execute("ROLLBACK")
                raise
        return BatchResult(len(values), inserted, duplicate)

    def cleanup(self, *, now: datetime, evidence_retention_days: int) -> Mapping[str, int]:
        evidence_cutoff = now.astimezone(UTC) - timedelta(days=evidence_retention_days)
        cutoffs = {
            "device_fingerprint_evidence": format_utc(evidence_cutoff),
            "device_fingerprint_source_health_events": format_utc(
                evidence_cutoff - timedelta(seconds=SOURCE_HEALTH_RETENTION_MARGIN_SECONDS)
            ),
        }
        ids = {
            "device_fingerprint_evidence": "evidence_id",
            "device_fingerprint_source_health_events": "source_health_id",
        }
        deleted: dict[str, int] = {}
        for table, cutoff in cutoffs.items():
            count = 0
            for _ in range(MAX_RETENTION_CHUNKS_PER_PASS):
                with self._access_lock:
                    try:
                        self.connection.execute("BEGIN IMMEDIATE")
                        cursor = self.connection.execute(
                            f"DELETE FROM {table} WHERE {ids[table]} IN (SELECT {ids[table]} FROM {table} WHERE observed_at < ? ORDER BY observed_at,{ids[table]} LIMIT ?)",
                            (cutoff, RETENTION_DELETE_CHUNK_ROWS),
                        )
                        chunk = cursor.rowcount
                        self.connection.execute("COMMIT")
                    except sqlite3.DatabaseError as exc:
                        try:
                            self.connection.execute("ROLLBACK")
                        except sqlite3.DatabaseError:
                            pass
                        raise self._sqlite_error(exc) from exc
                count += chunk
                if chunk < RETENTION_DELETE_CHUNK_ROWS:
                    break
            deleted[table] = count
        return deleted

    @staticmethod
    def _configure_writer(connection: sqlite3.Connection) -> None:
        connection.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
        connection.execute("PRAGMA foreign_keys=ON")
        if connection.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() != "wal":
            raise DeviceFingerprintStorageUnavailable("Fingerprint WAL mode is unavailable")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute(f"PRAGMA wal_autocheckpoint={WAL_AUTOCHECKPOINT_PAGES}")
        connection.execute(f"PRAGMA journal_size_limit={JOURNAL_SIZE_LIMIT_BYTES}")

    @staticmethod
    def _application_tables(connection: sqlite3.Connection) -> set[str]:
        return {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}

    @classmethod
    def _validate_connection(cls, connection: sqlite3.Connection) -> None:
        if int(connection.execute("PRAGMA user_version").fetchone()[0]) != SCHEMA_VERSION:
            raise DeviceFingerprintStorageCorrupt("Fingerprint schema version is incompatible")
        quick = connection.execute("PRAGMA quick_check").fetchall()
        if [row[0] for row in quick] != ["ok"]:
            raise DeviceFingerprintStorageCorrupt("Fingerprint repository is corrupt")
        cls._validate_schema_signature(
            connection, EXPECTED_COLUMNS, EXPECTED_INDEXES, REQUIRED_CHECK_FRAGMENTS,
        )
        state = connection.execute(
            f"SELECT singleton_id,database_generation_id,last_ingest_sequence FROM {STORAGE_STATE_TABLE}"
        ).fetchall()
        if len(state) != 1 or state[0][0] != 1 or not _canonical_generation(state[0][1]):
            raise DeviceFingerprintStorageCorrupt("Fingerprint generation state is invalid")
        allocator = state[0][2]
        if type(allocator) is not int or not 0 <= allocator <= MAX_INGEST_SEQUENCE:
            raise DeviceFingerprintStorageCorrupt("Fingerprint allocator state is invalid")
        for table in ("device_fingerprint_evidence", "device_fingerprint_source_health_events"):
            invalid = connection.execute(
                f"SELECT 1 FROM {table} WHERE typeof(ingest_sequence)!='integer' "
                "OR ingest_sequence<1 OR ingest_sequence>? LIMIT 1",
                (allocator,),
            ).fetchone()
            if invalid is not None:
                raise DeviceFingerprintStorageCorrupt("Fingerprint ingest sequence state is invalid")
        duplicate = connection.execute(
            "SELECT 1 FROM device_fingerprint_evidence AS evidence "
            "JOIN device_fingerprint_source_health_events AS health "
            "ON health.ingest_sequence=evidence.ingest_sequence LIMIT 1"
        ).fetchone()
        if duplicate is not None:
            raise DeviceFingerprintStorageCorrupt("Fingerprint ingest sequence state is invalid")

    @classmethod
    def _validate_schema_signature(cls, connection: sqlite3.Connection,
                                   columns: Mapping[str, Any], indexes: Mapping[str, Any],
                                   fragments: Mapping[str, Any]) -> None:
        if cls._application_tables(connection) != frozenset(columns):
            raise DeviceFingerprintStorageCorrupt("Fingerprint table signature is incompatible")
        for table, expected in columns.items():
            actual = tuple((row[1], row[2].upper(), row[3], row[5]) for row in connection.execute(f"PRAGMA table_info({table})"))
            if actual != expected:
                raise DeviceFingerprintStorageCorrupt("Fingerprint column signature is incompatible")
            table_sql = connection.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()[0]
            normalized = "".join(table_sql.lower().split())
            if any(fragment not in normalized for fragment in fragments[table]):
                raise DeviceFingerprintStorageCorrupt("Fingerprint constraints are missing")
            actual_indexes = {}
            for row in connection.execute(f"PRAGMA index_list({table})"):
                name, unique, partial = row[1], row[2], row[4]
                if name.startswith("sqlite_autoindex"):
                    continue
                if partial:
                    raise DeviceFingerprintStorageCorrupt("Fingerprint index signature is incompatible")
                columns = tuple(item[2] for item in connection.execute(f"PRAGMA index_info({name})"))
                actual_indexes[name] = (unique, columns)
            if actual_indexes != indexes[table]:
                raise DeviceFingerprintStorageCorrupt("Fingerprint index signature is incompatible")

    @classmethod
    def validate_v1_for_migration(cls, connection: sqlite3.Connection) -> None:
        if int(connection.execute("PRAGMA user_version").fetchone()[0]) != 1:
            raise DeviceFingerprintStorageCorrupt("Fingerprint migration source is incompatible")
        if [row[0] for row in connection.execute("PRAGMA quick_check")] != ["ok"]:
            raise DeviceFingerprintStorageCorrupt("Fingerprint migration source is corrupt")
        cls._validate_schema_signature(
            connection, V1_EXPECTED_COLUMNS, V1_EXPECTED_INDEXES, V1_REQUIRED_CHECK_FRAGMENTS,
        )

    @staticmethod
    def _sqlite_error(exc: sqlite3.DatabaseError) -> Exception:
        code = getattr(exc, "sqlite_errorcode", None)
        primary = code & 0xFF if isinstance(code, int) else None
        if primary == _SQLITE_FULL:
            return DeviceFingerprintStorageLimit("Fingerprint repository storage limit reached")
        if primary in _SQLITE_CORRUPTION:
            return DeviceFingerprintStorageCorrupt("Fingerprint repository is corrupt")
        if primary in _SQLITE_TEMPORARY_UNAVAILABLE:
            return DeviceFingerprintStorageUnavailable("Fingerprint repository is unavailable")
        message = str(exc).lower()
        if primary is None:
            if "database or disk is full" in message:
                return DeviceFingerprintStorageLimit("Fingerprint repository storage limit reached")
            if "malformed" in message or "corrupt" in message or "not a database" in message:
                return DeviceFingerprintStorageCorrupt("Fingerprint repository is corrupt")
            if "database is locked" in message or "database is busy" in message:
                return DeviceFingerprintStorageUnavailable("Fingerprint repository is unavailable")
        return RuntimeError("Unexpected fingerprint repository failure")


@contextmanager
def writer_lock(path: str) -> Iterator[Any]:
    lock_path = _prepare_local_file_target(
        Path(path),
        error_type=DeviceFingerprintWriterUnavailable,
        label="writer lock",
    )
    try:
        handle = open(lock_path, "a+b")  # noqa: SIM115
    except OSError as exc:
        raise DeviceFingerprintWriterUnavailable("Fingerprint writer lock is unavailable") from exc
    locked = False
    try:
        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        try:
            if _IS_POSIX:
                _enforce_posix_mode(
                    lock_path, 0o640,
                    error_type=DeviceFingerprintWriterUnavailable,
                    label="writer lock",
                )
        except DeviceFingerprintWriterUnavailable:
            raise
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError as exc:
            raise DeviceFingerprintWriterUnavailable("Fingerprint writer is already active") from exc
        yield handle
    finally:
        if locked:
            try:
                if os.name == "nt":
                    import msvcrt
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        handle.close()


def open_read_only(db_path: str) -> sqlite3.Connection:
    try:
        uri = Path(db_path).resolve(strict=True).as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=BUSY_TIMEOUT_MS / 1000)
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA query_only=ON")
        return connection
    except (OSError, sqlite3.DatabaseError) as exc:
        raise DeviceFingerprintStorageUnavailable("Fingerprint repository is unavailable") from exc


def _create_v2_schema(connection: sqlite3.Connection) -> None:
    for statement in SCHEMA_SQL.split(";"):
        if statement.strip():
            connection.execute(statement)


def _canonical_generation(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        return False
    return parsed.version == 4 and str(parsed) == value


def enforce_storage_cap(connection: sqlite3.Connection, max_db_bytes: int) -> None:
    """Reject oversized storage and verify SQLite accepted the configured cap."""
    page_size = int(connection.execute("PRAGMA page_size").fetchone()[0])
    max_pages = max_db_bytes // page_size
    page_count = int(connection.execute("PRAGMA page_count").fetchone()[0])
    if max_pages < 1 or page_count > max_pages:
        raise DeviceFingerprintStorageLimit("Fingerprint repository storage limit reached")
    effective = int(connection.execute(f"PRAGMA max_page_count={max_pages}").fetchone()[0])
    if effective > max_pages or page_count > effective:
        raise DeviceFingerprintStorageLimit("Fingerprint repository storage limit reached")


def _prepare_local_file_target(path: Path, *, error_type: type[Exception], label: str) -> Path:
    if not path.is_absolute():
        raise error_type(f"Fingerprint {label} target is invalid")
    parent = path.parent
    try:
        created = not parent.exists()
        if created:
            _create_approved_parent(parent, error_type=error_type, label=label)
        if not parent.is_dir() or parent.is_symlink():
            raise error_type(f"Fingerprint {label} parent is unsafe")
        _reject_symlink_components(parent, error_type=error_type, label=label)
        if created and _IS_POSIX:
            _enforce_posix_mode(parent, 0o750, error_type=error_type, label=label)
        try:
            metadata = os.lstat(path)
        except FileNotFoundError:
            return path
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise error_type(f"Fingerprint {label} target is unsafe")
        return path
    except error_type:
        raise
    except OSError as exc:
        raise error_type(f"Fingerprint {label} target is unavailable") from exc


def _create_approved_parent(parent: Path, *, error_type: type[Exception], label: str) -> None:
    approved = APPROVED_DATA_ROOT.resolve(strict=False)
    resolved_parent = parent.resolve(strict=False)
    try:
        resolved_parent.relative_to(approved)
    except ValueError as exc:
        raise error_type(f"Fingerprint {label} parent is not approved") from exc

    missing: list[Path] = []
    current = parent
    while not current.exists():
        missing.append(current)
        if current == current.parent:
            raise error_type(f"Fingerprint {label} parent is unavailable")
        current = current.parent
    _reject_symlink_components(current, error_type=error_type, label=label)
    for directory in reversed(missing):
        directory.mkdir(mode=0o750)
        if directory.is_symlink() or not directory.is_dir():
            raise error_type(f"Fingerprint {label} parent is unsafe")
        if _IS_POSIX:
            _enforce_posix_mode(directory, 0o750, error_type=error_type, label=label)


def _reject_symlink_components(path: Path, *, error_type: type[Exception], label: str) -> None:
    current = path
    while current != current.parent:
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            current = current.parent
            continue
        if stat.S_ISLNK(metadata.st_mode):
            raise error_type(f"Fingerprint {label} parent is unsafe")
        current = current.parent


def _enforce_posix_mode(path: Path, mode: int, *, error_type: type[Exception], label: str) -> None:
    try:
        os.chmod(path, mode)
        if stat.S_IMODE(os.stat(path).st_mode) != mode:
            raise OSError("required mode was not established")
    except OSError as exc:
        raise error_type(f"Fingerprint {label} mode is unavailable") from exc
