"""SQLite persistence owner for Current Network State schema v1."""

from __future__ import annotations

import os
import sqlite3
import stat
import threading
import time
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

from app.common.mac import format_mac_colon

from .models import (
    CurrentStateConfig,
    CurrentStateConfigError,
    CurrentStateCycle,
    CurrentStateSchemaError,
    CurrentStateStorageError,
    CurrentStateValidationError,
    SCHEMA_VERSION,
    SCOPE_HASH_PATTERN,
    parse_utc,
    require_cycle_id,
    require_nonnegative,
    require_site_id,
)


CYCLE_KINDS = frozenset({"client", "ap"})
CYCLE_RESULTS = frozenset({"success", "partial", "failed", "shutdown"})
AUTH_CLASSIFICATIONS = frozenset({"authorized", "pending", "other", "unknown"})
AP_STATUS_CLASSIFICATIONS = frozenset({"online", "offline", "other", "unknown"})
_SQLITE_BUSY_PRIMARY_CODE = 5
_SQLITE_LOCKED_PRIMARY_CODE = 6

_CLIENT_COLUMNS = (
    "cycle_id", "cycle_kind", "site_id", "observed_at", "client_mac",
    "name", "hostname", "device_type", "ip", "ssid", "ap_name", "ap_mac",
    "radio_id", "band", "channel", "rssi", "snr", "controller_uptime",
    "auth_status_code", "auth_classification", "controller_traffic_down",
    "controller_traffic_up", "controller_traffic_total", "active", "wireless",
)
_AP_COLUMNS = (
    "cycle_id", "cycle_kind", "site_id", "observed_at", "ap_mac", "name",
    "ip", "model", "firmware_version", "status_code", "status_classification",
    "last_seen_ms", "controller_uptime", "uptime_raw",
)


def _schema_sql() -> str:
    return """
        CREATE TABLE current_state_cycles (
            cycle_id TEXT NOT NULL PRIMARY KEY,
            kind TEXT NOT NULL CHECK(kind IN ('client','ap')),
            site_id TEXT NOT NULL CHECK(length(site_id)=24 AND site_id NOT GLOB '*[^0-9a-f]*'),
            capture_started_at TEXT NOT NULL,
            capture_finished_at TEXT NOT NULL,
            complete INTEGER NOT NULL CHECK(complete IN (0,1)),
            result TEXT NOT NULL CHECK(result IN ('success','partial','failed','shutdown')),
            source_scope_version INTEGER NOT NULL CHECK(source_scope_version > 0),
            source_scope_json TEXT NOT NULL,
            source_scope_hash TEXT NOT NULL CHECK(length(source_scope_hash)=64 AND source_scope_hash NOT GLOB '*[^0-9a-f]*'),
            source_rows_reported INTEGER CHECK(source_rows_reported IS NULL OR source_rows_reported >= 0),
            items_seen INTEGER NOT NULL CHECK(items_seen >= 0),
            items_stored INTEGER NOT NULL CHECK(items_stored >= 0),
            items_skipped INTEGER NOT NULL CHECK(items_skipped >= 0),
            unidentified_count INTEGER NOT NULL CHECK(unidentified_count >= 0),
            duplicate_identity_count INTEGER NOT NULL CHECK(duplicate_identity_count >= 0),
            unknown_status_count INTEGER NOT NULL CHECK(unknown_status_count >= 0),
            error_count INTEGER NOT NULL CHECK(error_count >= 0),
            data_quality_warning_count INTEGER NOT NULL CHECK(data_quality_warning_count >= 0),
            page_count INTEGER NOT NULL CHECK(page_count >= 0),
            failure_category TEXT,
            duration_ms INTEGER NOT NULL CHECK(duration_ms >= 0),
            created_at TEXT NOT NULL,
            UNIQUE(cycle_id, site_id, kind),
            CHECK(items_stored + items_skipped = items_seen),
            CHECK((result='success' AND complete=1) OR (result<>'success' AND complete=0))
        );

        CREATE TABLE current_client_state (
            cycle_id TEXT NOT NULL,
            cycle_kind TEXT NOT NULL DEFAULT 'client' CHECK(cycle_kind='client'),
            site_id TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            client_mac TEXT NOT NULL CHECK(length(client_mac)=17),
            name TEXT,
            hostname TEXT,
            device_type TEXT,
            ip TEXT,
            ssid TEXT NOT NULL,
            ap_name TEXT,
            ap_mac TEXT CHECK(ap_mac IS NULL OR length(ap_mac)=17),
            radio_id INTEGER,
            band TEXT,
            channel INTEGER CHECK(channel IS NULL OR channel >= 0),
            rssi INTEGER,
            snr INTEGER,
            controller_uptime INTEGER CHECK(controller_uptime IS NULL OR controller_uptime >= 0),
            auth_status_code INTEGER,
            auth_classification TEXT NOT NULL CHECK(auth_classification IN ('authorized','pending','other','unknown')),
            controller_traffic_down INTEGER CHECK(controller_traffic_down IS NULL OR controller_traffic_down >= 0),
            controller_traffic_up INTEGER CHECK(controller_traffic_up IS NULL OR controller_traffic_up >= 0),
            controller_traffic_total INTEGER CHECK(controller_traffic_total IS NULL OR controller_traffic_total >= 0),
            active INTEGER NOT NULL CHECK(active=1),
            wireless INTEGER NOT NULL CHECK(wireless=1),
            PRIMARY KEY(cycle_id, client_mac),
            FOREIGN KEY(cycle_id, site_id, cycle_kind)
              REFERENCES current_state_cycles(cycle_id, site_id, kind)
              ON DELETE CASCADE
        );

        CREATE TABLE current_ap_state (
            cycle_id TEXT NOT NULL,
            cycle_kind TEXT NOT NULL DEFAULT 'ap' CHECK(cycle_kind='ap'),
            site_id TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            ap_mac TEXT NOT NULL CHECK(length(ap_mac)=17),
            name TEXT,
            ip TEXT,
            model TEXT,
            firmware_version TEXT,
            status_code INTEGER,
            status_classification TEXT NOT NULL CHECK(status_classification IN ('online','offline','other','unknown')),
            last_seen_ms INTEGER CHECK(last_seen_ms IS NULL OR last_seen_ms >= 0),
            controller_uptime INTEGER CHECK(controller_uptime IS NULL OR controller_uptime >= 0),
            uptime_raw TEXT,
            PRIMARY KEY(cycle_id, ap_mac),
            FOREIGN KEY(cycle_id, site_id, cycle_kind)
              REFERENCES current_state_cycles(cycle_id, site_id, kind)
              ON DELETE CASCADE
        );

        CREATE INDEX idx_current_cycles_kind_site_started
          ON current_state_cycles(kind, site_id, capture_started_at DESC);
        CREATE INDEX idx_current_client_auth
          ON current_client_state(cycle_id, auth_classification, client_mac);
        CREATE INDEX idx_current_client_ap
          ON current_client_state(cycle_id, ap_mac, client_mac);
        CREATE INDEX idx_current_client_uptime
          ON current_client_state(cycle_id, controller_uptime DESC, client_mac);
        CREATE INDEX idx_current_client_traffic
          ON current_client_state(cycle_id, controller_traffic_total DESC, client_mac);
        CREATE INDEX idx_current_ap_status
          ON current_ap_state(cycle_id, status_classification, ap_mac);
        PRAGMA user_version = 1;
    """


class CurrentStateRepository:
    """Own schema validation and short atomic SQLite writes."""

    def __init__(self, config: CurrentStateConfig):
        self.config = config
        self.db_path = Path(config.db_path)
        self._write_lock = threading.RLock()

    def initialize(self) -> bool:
        """Create only an absent database, otherwise validate exact schema v1."""
        path = self._validate_path()
        created = not path.exists()
        if created:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o640)
            os.close(descriptor)
            try:
                connection = sqlite3.connect(str(path), timeout=5.0)
                try:
                    connection.execute("PRAGMA foreign_keys=ON")
                    connection.executescript("BEGIN IMMEDIATE;" + _schema_sql() + "COMMIT;")
                finally:
                    connection.close()
            except Exception:
                # Preserve the failed target for diagnosis; never silently recreate it.
                raise
        else:
            self._validate_existing(path)
        try:
            with self._connect(write=True) as connection:
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute("PRAGMA synchronous=NORMAL")
        except sqlite3.OperationalError as exc:
            if _transient_sqlite_contention(exc):
                raise CurrentStateStorageError(
                    "Current State database is temporarily busy"
                ) from exc
            raise
        self._enforce_modes()
        return created

    def _validate_path(self) -> Path:
        path = self.db_path.expanduser()
        if not path.is_absolute():
            raise CurrentStateConfigError("CURRENT_STATE_DB_PATH must be absolute")
        parent = path.parent
        if not parent.exists() or not parent.is_dir() or parent.is_symlink():
            raise CurrentStateConfigError("CURRENT_STATE_DB_PATH parent is unsafe")
        if os.name == "posix" and stat.S_IMODE(parent.stat().st_mode) & 0o007:
            raise CurrentStateConfigError(
                "CURRENT_STATE_DB_PATH parent permits public access"
            )
        if path.exists() or path.is_symlink():
            metadata = path.lstat()
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
                raise CurrentStateConfigError("CURRENT_STATE_DB_PATH target is unsafe")
        resolved = path.resolve(strict=False)
        forbidden = (
            Path(__file__).resolve().parents[1] / "admin_web" / "static",
            Path(__file__).resolve().parents[1] / "admin_web" / "templates",
            Path(__file__).resolve().parents[1] / "web" / "static",
            Path("/var/www"),
            Path("/srv/www"),
        )
        if any(_is_relative_to(resolved, root.resolve(strict=False)) for root in forbidden):
            raise CurrentStateConfigError("CURRENT_STATE_DB_PATH is inside a public web tree")
        for other in self.config.other_sqlite_paths:
            if resolved == Path(other).expanduser().resolve(strict=False):
                raise CurrentStateConfigError("CURRENT_STATE_DB_PATH collides with another SQLite database")
        return path

    def _validate_existing(self, path: Path) -> None:
        uri = f"{path.resolve().as_uri()}?mode=ro"
        quick_check_interrupted = False
        quick_check_started = 0.0

        def quick_check_progress() -> int:
            nonlocal quick_check_interrupted
            quick_check_interrupted = (
                time.monotonic() - quick_check_started > 10.0
            )
            return int(quick_check_interrupted)

        try:
            connection = sqlite3.connect(uri, uri=True, timeout=0.5)
            try:
                connection.row_factory = sqlite3.Row
                connection.execute("PRAGMA query_only=ON")
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if version != SCHEMA_VERSION:
                    raise CurrentStateSchemaError("Current State schema version is incompatible")
                actual = _schema_signature(connection)
                if actual != _expected_schema_signature():
                    raise CurrentStateSchemaError("Current State schema signature is incompatible")
                quick_check_started = time.monotonic()
                connection.set_progress_handler(quick_check_progress, 10_000)
                try:
                    result = connection.execute("PRAGMA quick_check").fetchone()[0]
                finally:
                    connection.set_progress_handler(None, 0)
                if result != "ok":
                    raise CurrentStateSchemaError("Current State integrity check failed")
            finally:
                connection.close()
        except CurrentStateSchemaError:
            raise
        except sqlite3.OperationalError as exc:
            if quick_check_interrupted and "interrupted" in str(exc).lower():
                raise CurrentStateStorageError(
                    "Current State integrity check temporarily timed out"
                ) from exc
            if _transient_sqlite_contention(exc):
                raise CurrentStateStorageError(
                    "Current State database is temporarily busy"
                ) from exc
            raise CurrentStateSchemaError(
                "Current State database is unavailable"
            ) from exc
        except sqlite3.Error as exc:
            raise CurrentStateSchemaError("Current State database is unavailable") from exc

    @contextmanager
    def _connect(self, *, write: bool) -> Iterator[sqlite3.Connection]:
        if write:
            connection = sqlite3.connect(str(self.db_path), timeout=self.config.sqlite_busy_timeout_ms / 1000)
        else:
            uri = f"{self.db_path.resolve().as_uri()}?mode=ro"
            connection = sqlite3.connect(uri, uri=True, timeout=self.config.sqlite_busy_timeout_ms / 1000)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(f"PRAGMA busy_timeout={self.config.sqlite_busy_timeout_ms}")
        if not write:
            connection.execute("PRAGMA query_only=ON")
        try:
            yield connection
        finally:
            connection.close()
            if write:
                self._enforce_modes()

    @contextmanager
    def read_connection(self) -> Iterator[sqlite3.Connection]:
        with self._connect(write=False) as connection:
            yield connection

    def publish_cycle(
        self,
        cycle: CurrentStateCycle,
        *,
        client_rows: Sequence[Mapping[str, Any]] = (),
        ap_rows: Sequence[Mapping[str, Any]] = (),
    ) -> None:
        _validate_cycle(cycle)
        if cycle.kind == "client" and ap_rows:
            raise CurrentStateValidationError("AP rows cannot attach to a client cycle")
        if cycle.kind == "ap" and client_rows:
            raise CurrentStateValidationError("Client rows cannot attach to an AP cycle")
        rows = client_rows if cycle.kind == "client" else ap_rows
        if len(rows) != cycle.items_stored:
            raise CurrentStateValidationError("items_stored does not match published rows")
        for row in rows:
            if row.get("cycle_id") != cycle.cycle_id or row.get("site_id") != cycle.site_id or row.get("cycle_kind") != cycle.kind:
                raise CurrentStateValidationError("row cycle/site/kind does not match parent")
            if cycle.kind == "client":
                _validate_client_row(row, cycle)
            else:
                _validate_ap_row(row, cycle)
        with self._write_lock:
            try:
                with self._connect(write=True) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    connection.execute(
                        """
                        INSERT INTO current_state_cycles (
                            cycle_id, kind, site_id, capture_started_at,
                            capture_finished_at, complete, result,
                            source_scope_version, source_scope_json,
                            source_scope_hash, source_rows_reported,
                            items_seen, items_stored, items_skipped,
                            unidentified_count, duplicate_identity_count,
                            unknown_status_count, error_count,
                            data_quality_warning_count, page_count,
                            failure_category, duration_ms, created_at
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            cycle.cycle_id, cycle.kind, cycle.site_id,
                            cycle.capture_started_at, cycle.capture_finished_at,
                            int(cycle.complete), cycle.result,
                            cycle.source_scope_version, cycle.source_scope_json,
                            cycle.source_scope_hash, cycle.source_rows_reported,
                            cycle.items_seen, cycle.items_stored, cycle.items_skipped,
                            cycle.unidentified_count, cycle.duplicate_identity_count,
                            cycle.unknown_status_count, cycle.error_count,
                            cycle.data_quality_warning_count, cycle.page_count,
                            cycle.failure_category, cycle.duration_ms, cycle.created_at,
                        ),
                    )
                    if client_rows:
                        _insert_rows(connection, "current_client_state", _CLIENT_COLUMNS, client_rows)
                    if ap_rows:
                        _insert_rows(connection, "current_ap_state", _AP_COLUMNS, ap_rows)
                    connection.commit()
            except (CurrentStateValidationError, CurrentStateSchemaError):
                raise
            except sqlite3.Error as exc:
                raise CurrentStateStorageError("Current State publication failed") from exc

    def get_cycle(self, cycle_id: str) -> CurrentStateCycle | None:
        identifier = require_cycle_id(cycle_id)
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM current_state_cycles WHERE cycle_id=?",
                (identifier,),
            ).fetchone()
        return None if row is None else _cycle_from_row(row)

    def protected_cycle_ids(self) -> frozenset[str]:
        with self.read_connection() as connection:
            rows = connection.execute(
                """
                WITH ranked AS (
                    SELECT cycle_id, kind, site_id, result, items_stored,
                           ROW_NUMBER() OVER (PARTITION BY kind, site_id ORDER BY capture_started_at DESC, cycle_id DESC) AS attempt_rank,
                           ROW_NUMBER() OVER (PARTITION BY kind, site_id, CASE WHEN result='success' AND complete=1 THEN 1 ELSE 0 END ORDER BY capture_started_at DESC, cycle_id DESC) AS result_rank,
                           ROW_NUMBER() OVER (PARTITION BY kind, site_id, CASE WHEN result='partial' AND complete=0 AND items_stored>0 THEN 1 ELSE 0 END ORDER BY capture_started_at DESC, cycle_id DESC) AS partial_rank
                    FROM current_state_cycles
                )
                SELECT cycle_id FROM ranked
                WHERE attempt_rank=1
                   OR (result='success' AND result_rank=1)
                   OR (result='partial' AND items_stored>0 AND partial_rank=1)
                """
            ).fetchall()
        return frozenset(str(row[0]) for row in rows)

    def cleanup_candidates(self, *, cutoff_utc: str, protected: frozenset[str], limit: int, client_only: bool = False) -> tuple[tuple[str, int, int], ...]:
        parse_utc(cutoff_utc, "cutoff_utc")
        query = """
            SELECT c.cycle_id,
                   (SELECT COUNT(*) FROM current_client_state x WHERE x.cycle_id=c.cycle_id) AS client_rows,
                   (SELECT COUNT(*) FROM current_ap_state x WHERE x.cycle_id=c.cycle_id) AS ap_rows
            FROM current_state_cycles c
            WHERE c.capture_started_at < ?
        """
        params: list[Any] = [cutoff_utc]
        if client_only:
            query += " AND c.kind='client'"
        if protected:
            placeholders = ",".join("?" for _ in protected)
            query += f" AND c.cycle_id NOT IN ({placeholders})"
            params.extend(sorted(protected))
        query += " ORDER BY c.capture_started_at, c.cycle_id LIMIT ?"
        params.append(limit)
        with self.read_connection() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return tuple((str(row[0]), int(row[1]), int(row[2])) for row in rows)

    def oldest_client_candidates(self, *, protected: frozenset[str], limit: int) -> tuple[tuple[str, int, int], ...]:
        return self.cleanup_candidates(
            cutoff_utc="9999-12-31T23:59:59.999Z",
            protected=protected,
            limit=limit,
            client_only=True,
        )

    def count_client_rows(self) -> int:
        with self.read_connection() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM current_client_state").fetchone()[0])

    def delete_cycles(self, cycle_ids: Sequence[str]) -> tuple[int, int, int]:
        ids = tuple(require_cycle_id(value) for value in cycle_ids)
        if not ids:
            return (0, 0, 0)
        placeholders = ",".join("?" for _ in ids)
        with self._write_lock:
            try:
                with self._connect(write=True) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    client_rows = int(connection.execute(
                        f"SELECT COUNT(*) FROM current_client_state WHERE cycle_id IN ({placeholders})", ids
                    ).fetchone()[0])
                    ap_rows = int(connection.execute(
                        f"SELECT COUNT(*) FROM current_ap_state WHERE cycle_id IN ({placeholders})", ids
                    ).fetchone()[0])
                    cursor = connection.execute(
                        f"DELETE FROM current_state_cycles WHERE cycle_id IN ({placeholders})", ids
                    )
                    deleted = int(cursor.rowcount)
                    connection.commit()
                    return deleted, client_rows, ap_rows
            except sqlite3.Error as exc:
                raise CurrentStateStorageError("Current State cleanup failed") from exc

    def explain(self, sql: str, parameters: Sequence[Any] = ()) -> tuple[str, ...]:
        if not isinstance(sql, str) or not sql.lstrip().upper().startswith("SELECT"):
            raise CurrentStateValidationError("EXPLAIN accepts SELECT only")
        with self.read_connection() as connection:
            rows = connection.execute("EXPLAIN QUERY PLAN " + sql, tuple(parameters)).fetchall()
        return tuple(str(row[3]) for row in rows)

    def _enforce_modes(self) -> None:
        if os.name != "posix":
            return
        for candidate in (self.db_path, Path(str(self.db_path) + "-wal"), Path(str(self.db_path) + "-shm")):
            try:
                metadata = candidate.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISREG(metadata.st_mode):
                os.chmod(candidate, 0o640)


def _insert_rows(connection: sqlite3.Connection, table: str, columns: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    placeholders = ",".join("?" for _ in columns)
    names = ",".join(columns)
    connection.executemany(
        f"INSERT INTO {table} ({names}) VALUES ({placeholders})",
        [tuple(row.get(column) for column in columns) for row in rows],
    )


def _transient_sqlite_contention(exc: sqlite3.OperationalError) -> bool:
    code = getattr(exc, "sqlite_errorcode", None)
    return code in {_SQLITE_BUSY_PRIMARY_CODE, _SQLITE_LOCKED_PRIMARY_CODE} or any(
        marker in str(exc).lower() for marker in ("database is locked", "database is busy")
    )


def _validate_cycle(cycle: CurrentStateCycle) -> None:
    require_cycle_id(cycle.cycle_id)
    require_site_id(cycle.site_id)
    if cycle.kind not in CYCLE_KINDS or cycle.result not in CYCLE_RESULTS:
        raise CurrentStateValidationError("cycle kind/result is invalid")
    if cycle.complete != (cycle.result == "success"):
        raise CurrentStateValidationError("success/complete invariant failed")
    parse_utc(cycle.capture_started_at, "capture_started_at")
    parse_utc(cycle.capture_finished_at, "capture_finished_at")
    parse_utc(cycle.created_at, "created_at")
    if parse_utc(cycle.capture_finished_at) < parse_utc(cycle.capture_started_at):
        raise CurrentStateValidationError("capture interval is invalid")
    if type(cycle.source_scope_version) is not int or cycle.source_scope_version <= 0:
        raise CurrentStateValidationError("scope version is invalid")
    if not isinstance(cycle.source_scope_json, str) or SCOPE_HASH_PATTERN.fullmatch(cycle.source_scope_hash) is None:
        raise CurrentStateValidationError("scope contract is invalid")
    try:
        scope = json.loads(cycle.source_scope_json)
        canonical = json.dumps(scope, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError, json.JSONDecodeError, RecursionError) as exc:
        raise CurrentStateValidationError("scope JSON is invalid") from exc
    if canonical != cycle.source_scope_json or hashlib.sha256(canonical.encode("utf-8")).hexdigest() != cycle.source_scope_hash:
        raise CurrentStateValidationError("scope hash does not match canonical scope")
    if not isinstance(scope, dict):
        raise CurrentStateValidationError("scope JSON must be an object")
    if cycle.kind == "client":
        if set(scope) != {"scope_type", "site_id", "ssids"} or scope.get("scope_type") != "client_ssid_allowlist" or scope.get("site_id") != cycle.site_id:
            raise CurrentStateValidationError("client scope does not match cycle")
        ssids = scope.get("ssids")
        if (
            not isinstance(ssids, list)
            or not ssids
            or any(not _safe_text(item, 32, required=True) for item in ssids)
            or ssids != sorted(set(ssids))
        ):
            raise CurrentStateValidationError("client scope SSIDs are invalid")
    elif set(scope) != {"scope_type", "site_id"} or scope.get("scope_type") != "site_ap_inventory" or scope.get("site_id") != cycle.site_id:
        raise CurrentStateValidationError("AP scope does not match cycle")
    for name in (
        "items_seen", "items_stored", "items_skipped", "unidentified_count",
        "duplicate_identity_count", "unknown_status_count", "error_count",
        "data_quality_warning_count", "page_count", "duration_ms",
    ):
        require_nonnegative(getattr(cycle, name), name)
    require_nonnegative(cycle.source_rows_reported, "source_rows_reported", nullable=True)
    if cycle.items_stored + cycle.items_skipped != cycle.items_seen:
        raise CurrentStateValidationError("cycle item counts are inconsistent")


def _validate_client_row(row: Mapping[str, Any], cycle: CurrentStateCycle) -> None:
    if not _canonical_mac(row.get("client_mac")):
        raise CurrentStateValidationError("client row MAC is invalid")
    ap_mac = row.get("ap_mac")
    if ap_mac is not None and not _canonical_mac(ap_mac):
        raise CurrentStateValidationError("client AP MAC is invalid")
    parse_utc(row.get("observed_at"), "observed_at")
    if row.get("observed_at") != cycle.capture_started_at:
        raise CurrentStateValidationError("client observed_at does not match cycle")
    scope = json.loads(cycle.source_scope_json)
    if row.get("ssid") not in scope["ssids"]:
        raise CurrentStateValidationError("client SSID is outside cycle scope")
    if row.get("active") is not True or row.get("wireless") is not True:
        raise CurrentStateValidationError("client row is not active wireless")
    if row.get("auth_classification") not in AUTH_CLASSIFICATIONS:
        raise CurrentStateValidationError("client auth classification is invalid")


def _validate_ap_row(row: Mapping[str, Any], cycle: CurrentStateCycle) -> None:
    if not _canonical_mac(row.get("ap_mac")):
        raise CurrentStateValidationError("AP row MAC is invalid")
    parse_utc(row.get("observed_at"), "observed_at")
    if row.get("observed_at") != cycle.capture_started_at:
        raise CurrentStateValidationError("AP observed_at does not match cycle")
    if row.get("status_classification") not in AP_STATUS_CLASSIFICATIONS:
        raise CurrentStateValidationError("AP status classification is invalid")


def _canonical_mac(value: Any) -> bool:
    try:
        return isinstance(value, str) and format_mac_colon(value) == value
    except (TypeError, ValueError):
        return False


def _safe_text(value: Any, maximum: int, *, required: bool = False) -> bool:
    if value is None:
        return not required
    if not isinstance(value, str) or (required and value == "") or "\x00" in value:
        return False
    try:
        return len(value.encode("utf-8")) <= maximum
    except UnicodeEncodeError:
        return False


def _cycle_from_row(row: sqlite3.Row) -> CurrentStateCycle:
    return CurrentStateCycle(
        cycle_id=str(row["cycle_id"]), kind=str(row["kind"]), site_id=str(row["site_id"]),
        capture_started_at=str(row["capture_started_at"]), capture_finished_at=str(row["capture_finished_at"]),
        complete=bool(row["complete"]), result=str(row["result"]),
        source_scope_version=int(row["source_scope_version"]), source_scope_json=str(row["source_scope_json"]),
        source_scope_hash=str(row["source_scope_hash"]), source_rows_reported=row["source_rows_reported"],
        items_seen=int(row["items_seen"]), items_stored=int(row["items_stored"]), items_skipped=int(row["items_skipped"]),
        unidentified_count=int(row["unidentified_count"]), duplicate_identity_count=int(row["duplicate_identity_count"]),
        unknown_status_count=int(row["unknown_status_count"]), error_count=int(row["error_count"]),
        data_quality_warning_count=int(row["data_quality_warning_count"]), page_count=int(row["page_count"]),
        failure_category=row["failure_category"], duration_ms=int(row["duration_ms"]), created_at=str(row["created_at"]),
    )


def _schema_signature(connection: sqlite3.Connection) -> tuple[tuple[str, str, str, str], ...]:
    rows = connection.execute(
        "SELECT type, name, tbl_name, COALESCE(sql,'') FROM sqlite_schema "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name, tbl_name, sql"
    ).fetchall()
    return tuple(tuple(str(value) for value in row) for row in rows)


_EXPECTED_SIGNATURE: tuple[tuple[str, str, str, str], ...] | None = None


def _expected_schema_signature() -> tuple[tuple[str, str, str, str], ...]:
    global _EXPECTED_SIGNATURE
    if _EXPECTED_SIGNATURE is None:
        connection = sqlite3.connect(":memory:")
        try:
            connection.executescript(_schema_sql())
            _EXPECTED_SIGNATURE = _schema_signature(connection)
        finally:
            connection.close()
    return _EXPECTED_SIGNATURE


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
