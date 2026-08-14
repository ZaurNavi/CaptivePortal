"""SQLite persistence for Visit Lifecycle schema version 1."""

from __future__ import annotations

import os
import sqlite3
import stat
import threading
import uuid
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any, Mapping

from .models import (
    ReconcileCandidate,
    SCHEMA_VERSION,
    VisitLifecycleConfig,
    VisitRecord,
    VisitSchemaError,
    VisitStartOutcome,
    VisitStorageCategory,
    VisitStorageError,
    NormalizedVisitStart,
)


ALLOWED_AUTO_CREATE_ROOT = Path("/opt/CaptivePortal/data")

_SQLITE_BUSY = 5
_SQLITE_LOCKED = 6
_SQLITE_READONLY = 8
_SQLITE_IOERR = 10
_SQLITE_CORRUPT = 11
_SQLITE_FULL = 13
_SQLITE_CANTOPEN = 14
_SQLITE_CONSTRAINT = 19
_SQLITE_NOTADB = 26

REQUIRED_TABLES = frozenset({
    "visits",
    "visit_authorizations",
    "visit_source_events",
    "visit_reader_state",
})

REQUIRED_INDEXES: Mapping[str, tuple[str, ...]] = {
    "uq_visits_open_site_mac": ("site_id", "client_mac"),
    "idx_visits_site_started": ("site_id", "started_at", "visit_id"),
    "idx_visits_site_closed": ("site_id", "closed_at", "visit_id"),
    "idx_visits_site_mac_started": (
        "site_id", "client_mac", "started_at", "visit_id",
    ),
    "idx_visits_site_device_started": (
        "site_id", "device_id", "started_at", "visit_id",
    ),
    "idx_visits_site_status_started": (
        "site_id", "status", "started_at", "visit_id",
    ),
    "idx_visits_site_start_ssid": (
        "site_id", "start_ssid", "started_at", "visit_id",
    ),
    "idx_visits_site_final_ssid": (
        "site_id", "final_ssid", "started_at", "visit_id",
    ),
    "idx_visits_site_start_ap": (
        "site_id", "start_ap_mac", "started_at", "visit_id",
    ),
    "idx_visits_site_final_ap": (
        "site_id", "final_ap_mac", "started_at", "visit_id",
    ),
    "idx_visit_auth_visit_time": ("visit_id", "authorized_at", "row_id"),
    "idx_visit_auth_visit_ssid": ("visit_id", "portal_ssid"),
    "idx_visit_auth_visit_ap": ("visit_id", "portal_ap_mac"),
    "idx_visit_events_site_controller": (
        "site_id", "controller_event_at", "event_id",
    ),
    "idx_visit_events_site_processed": (
        "site_id", "processed_at", "event_id",
    ),
    "idx_visit_events_result_processed": (
        "processing_result", "processed_at",
    ),
    "idx_visit_events_source_offsets": (
        "source_identity", "source_offset_start", "source_offset_end",
    ),
    "idx_visits_reconcile_due": (
        "link_reconcile_next_at", "started_at", "visit_id",
    ),
}

REQUIRED_TRIGGERS = frozenset({"trg_visits_start_evidence_immutable"})

REQUIRED_FOREIGN_KEYS: Mapping[str, frozenset[tuple[str, str, str, str]]] = {
    "visits": frozenset({
        ("offline_event_id", "visit_source_events", "event_id", "SET NULL"),
    }),
    "visit_authorizations": frozenset({
        ("visit_id", "visits", "visit_id", "CASCADE"),
    }),
    "visit_source_events": frozenset({
        ("visit_id", "visits", "visit_id", "SET NULL"),
    }),
}

REQUIRED_NOT_NULL_COLUMNS: Mapping[str, frozenset[str]] = {
    "visits": frozenset({
        "site_id",
        "client_mac",
        "start_auth_session_id",
        "start_auth_run_number",
        "start_final_reason",
        "started_at",
        "status",
        "created_at",
        "updated_at",
    }),
    "visit_authorizations": frozenset({
        "visit_id",
        "auth_session_id",
        "auth_run_number",
        "authorized_at",
        "final_reason",
        "created_at",
    }),
}


def _utc_check(column: str, *, nullable: bool = False) -> str:
    expression = (
        f"(length({column}) = 24 "
        f"AND substr({column}, 5, 1) = '-' "
        f"AND substr({column}, 8, 1) = '-' "
        f"AND substr({column}, 11, 1) = 'T' "
        f"AND substr({column}, 14, 1) = ':' "
        f"AND substr({column}, 17, 1) = ':' "
        f"AND substr({column}, 20, 1) = '.' "
        f"AND substr({column}, 24, 1) = 'Z')"
    )
    return f"({column} IS NULL OR {expression})" if nullable else expression


def _schema_sql() -> str:
    return f"""
        BEGIN IMMEDIATE;

        CREATE TABLE visits (
            visit_id TEXT PRIMARY KEY CHECK (length(visit_id) = 36),
            site_id TEXT NOT NULL CHECK (length(trim(site_id)) > 0),
            client_mac TEXT NOT NULL CHECK (length(client_mac) = 17),

            device_id TEXT,
            initial_snapshot_id TEXT,

            start_auth_session_id TEXT NOT NULL
                CHECK (length(trim(start_auth_session_id)) > 0),
            start_auth_run_number INTEGER NOT NULL
                CHECK (start_auth_run_number > 0),
            start_final_reason TEXT NOT NULL
                CHECK (length(trim(start_final_reason)) > 0),

            link_reconcile_attempted_at TEXT
                CHECK {_utc_check('link_reconcile_attempted_at', nullable=True)},
            link_reconcile_next_at TEXT
                CHECK {_utc_check('link_reconcile_next_at', nullable=True)},
            link_reconcile_attempt_count INTEGER NOT NULL DEFAULT 0
                CHECK (link_reconcile_attempt_count >= 0),

            started_at TEXT NOT NULL CHECK {_utc_check('started_at')},
            closed_at TEXT CHECK {_utc_check('closed_at', nullable=True)},
            status TEXT NOT NULL CHECK (status IN ('open', 'closed')),
            close_reason TEXT,
            close_time_source TEXT,

            start_ip TEXT,
            start_ssid TEXT,
            start_ap_mac TEXT CHECK (
                start_ap_mac IS NULL OR length(start_ap_mac) = 17
            ),
            final_ip TEXT,
            final_ssid TEXT,
            final_ap_mac TEXT CHECK (
                final_ap_mac IS NULL OR length(final_ap_mac) = 17
            ),

            reported_connected_seconds INTEGER CHECK (
                reported_connected_seconds IS NULL
                OR reported_connected_seconds >= 0
            ),
            reported_traffic_total_bytes INTEGER CHECK (
                reported_traffic_total_bytes IS NULL
                OR reported_traffic_total_bytes >= 0
            ),
            reported_traffic_up_bytes INTEGER CHECK (
                reported_traffic_up_bytes IS NULL
                OR reported_traffic_up_bytes >= 0
            ),
            reported_traffic_down_bytes INTEGER CHECK (
                reported_traffic_down_bytes IS NULL
                OR reported_traffic_down_bytes >= 0
            ),
            duration_seconds INTEGER CHECK (
                duration_seconds IS NULL OR duration_seconds >= 0
            ),
            offline_event_id TEXT UNIQUE,
            created_at TEXT NOT NULL CHECK {_utc_check('created_at')},
            updated_at TEXT NOT NULL CHECK {_utc_check('updated_at')},

            CHECK (
                (status = 'open'
                 AND closed_at IS NULL
                 AND close_reason IS NULL
                 AND close_time_source IS NULL
                 AND duration_seconds IS NULL
                 AND offline_event_id IS NULL)
                OR
                (status = 'closed'
                 AND closed_at IS NOT NULL
                 AND close_reason IS NOT NULL
                 AND close_time_source IS NOT NULL
                 AND duration_seconds IS NOT NULL
                 AND closed_at >= started_at)
            ),
            FOREIGN KEY (offline_event_id)
                REFERENCES visit_source_events(event_id) ON DELETE SET NULL
        );

        CREATE TABLE visit_authorizations (
            row_id INTEGER PRIMARY KEY,
            visit_id TEXT NOT NULL,
            auth_session_id TEXT NOT NULL
                CHECK (length(trim(auth_session_id)) > 0),
            auth_run_number INTEGER NOT NULL CHECK (auth_run_number > 0),
            authorization_attempt INTEGER CHECK (
                authorization_attempt IS NULL OR authorization_attempt >= 0
            ),
            authorized_at TEXT NOT NULL CHECK {_utc_check('authorized_at')},
            final_reason TEXT NOT NULL CHECK (length(trim(final_reason)) > 0),
            client_ip TEXT,
            portal_ssid TEXT,
            portal_ap_mac TEXT CHECK (
                portal_ap_mac IS NULL OR length(portal_ap_mac) = 17
            ),
            portal_radio_id INTEGER CHECK (
                portal_radio_id IS NULL OR portal_radio_id >= 0
            ),
            created_at TEXT NOT NULL CHECK {_utc_check('created_at')},
            UNIQUE (auth_session_id, auth_run_number),
            FOREIGN KEY (visit_id) REFERENCES visits(visit_id) ON DELETE CASCADE
        );

        CREATE TABLE visit_source_events (
            event_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL CHECK (length(trim(event_type)) > 0),
            site_id TEXT,
            client_mac TEXT CHECK (
                client_mac IS NULL OR length(client_mac) = 17
            ),
            controller_event_at TEXT
                CHECK {_utc_check('controller_event_at', nullable=True)},
            received_at TEXT CHECK {_utc_check('received_at', nullable=True)},
            source_identity TEXT NOT NULL
                CHECK (length(trim(source_identity)) > 0),
            source_offset_start INTEGER NOT NULL
                CHECK (source_offset_start >= 0),
            source_offset_end INTEGER NOT NULL
                CHECK (source_offset_end >= source_offset_start),
            processing_result TEXT NOT NULL CHECK (
                processing_result IN (
                    'pending_match', 'closed', 'unmatched', 'invalid'
                )
            ),
            visit_id TEXT,
            reason TEXT,
            first_processed_at TEXT NOT NULL
                CHECK {_utc_check('first_processed_at')},
            processed_at TEXT NOT NULL CHECK {_utc_check('processed_at')},
            pending_until TEXT CHECK {_utc_check('pending_until', nullable=True)},
            last_match_attempt_at TEXT
                CHECK {_utc_check('last_match_attempt_at', nullable=True)},
            CHECK (
                processing_result != 'pending_match'
                OR pending_until IS NOT NULL
            ),
            FOREIGN KEY (visit_id) REFERENCES visits(visit_id) ON DELETE SET NULL
        );

        CREATE TABLE visit_reader_state (
            source_identity TEXT PRIMARY KEY,
            source_path TEXT NOT NULL CHECK (length(trim(source_path)) > 0),
            source_offset INTEGER NOT NULL CHECK (source_offset >= 0),
            last_observed_size INTEGER CHECK (
                last_observed_size IS NULL OR last_observed_size >= 0
            ),
            checkpoint_offset INTEGER CHECK (
                checkpoint_offset IS NULL OR checkpoint_offset >= 0
            ),
            checkpoint_length INTEGER CHECK (
                checkpoint_length IS NULL OR checkpoint_length >= 0
            ),
            checkpoint_sha256 TEXT CHECK (
                checkpoint_sha256 IS NULL OR length(checkpoint_sha256) = 64
            ),
            retired_completed INTEGER NOT NULL DEFAULT 0
                CHECK (retired_completed IN (0, 1)),
            missing_warning_emitted INTEGER NOT NULL DEFAULT 0
                CHECK (missing_warning_emitted IN (0, 1)),
            updated_at TEXT NOT NULL CHECK {_utc_check('updated_at')},
            CHECK (
                (checkpoint_offset IS NULL
                 AND checkpoint_length IS NULL
                 AND checkpoint_sha256 IS NULL)
                OR
                (checkpoint_offset IS NOT NULL
                 AND checkpoint_length IS NOT NULL
                 AND checkpoint_sha256 IS NOT NULL)
            )
        );

        CREATE TRIGGER trg_visits_start_evidence_immutable
        BEFORE UPDATE OF
            start_auth_session_id,
            start_auth_run_number,
            start_final_reason,
            started_at
        ON visits
        WHEN
            NEW.start_auth_session_id != OLD.start_auth_session_id
            OR NEW.start_auth_run_number != OLD.start_auth_run_number
            OR NEW.start_final_reason != OLD.start_final_reason
            OR NEW.started_at != OLD.started_at
        BEGIN
            SELECT RAISE(ABORT, 'visit start evidence is immutable');
        END;

        CREATE UNIQUE INDEX uq_visits_open_site_mac
            ON visits(site_id, client_mac) WHERE status = 'open';
        CREATE INDEX idx_visits_site_started
            ON visits(site_id, started_at, visit_id);
        CREATE INDEX idx_visits_site_closed
            ON visits(site_id, closed_at, visit_id);
        CREATE INDEX idx_visits_site_mac_started
            ON visits(site_id, client_mac, started_at, visit_id);
        CREATE INDEX idx_visits_site_device_started
            ON visits(site_id, device_id, started_at, visit_id);
        CREATE INDEX idx_visits_site_status_started
            ON visits(site_id, status, started_at, visit_id);
        CREATE INDEX idx_visits_site_start_ssid
            ON visits(site_id, start_ssid, started_at, visit_id);
        CREATE INDEX idx_visits_site_final_ssid
            ON visits(site_id, final_ssid, started_at, visit_id);
        CREATE INDEX idx_visits_site_start_ap
            ON visits(site_id, start_ap_mac, started_at, visit_id);
        CREATE INDEX idx_visits_site_final_ap
            ON visits(site_id, final_ap_mac, started_at, visit_id);
        CREATE INDEX idx_visit_auth_visit_time
            ON visit_authorizations(visit_id, authorized_at, row_id);
        CREATE INDEX idx_visit_auth_visit_ssid
            ON visit_authorizations(visit_id, portal_ssid);
        CREATE INDEX idx_visit_auth_visit_ap
            ON visit_authorizations(visit_id, portal_ap_mac);
        CREATE INDEX idx_visit_events_site_controller
            ON visit_source_events(site_id, controller_event_at, event_id);
        CREATE INDEX idx_visit_events_site_processed
            ON visit_source_events(site_id, processed_at, event_id);
        CREATE INDEX idx_visit_events_result_processed
            ON visit_source_events(processing_result, processed_at);
        CREATE INDEX idx_visit_events_source_offsets
            ON visit_source_events(
                source_identity, source_offset_start, source_offset_end
            );
        CREATE INDEX idx_visits_reconcile_due
            ON visits(link_reconcile_next_at, started_at, visit_id)
            WHERE device_id IS NULL OR initial_snapshot_id IS NULL;

        PRAGMA user_version = 1;
        COMMIT;
    """


class VisitRepository:
    """Own Visit schema v1 and short serialized write transactions."""

    def __init__(
        self,
        config: VisitLifecycleConfig,
        *,
        busy_timeout_ms: int | None = None,
    ):
        self.config = config
        self.db_path = Path(config.db_path)
        timeout = (
            config.start_busy_timeout_ms
            if busy_timeout_ms is None
            else busy_timeout_ms
        )
        self.busy_timeout_ms = max(1, min(int(timeout), 60_000))
        self._write_lock = threading.RLock()

    def initialize(self) -> bool:
        self._ensure_parent()
        existed = self._database_exists()
        created = False
        try:
            with self._bounded_write(), closing(self._connect()) as connection:
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if version > SCHEMA_VERSION:
                    raise VisitSchemaError("Visit schema is newer than this code")
                if version == 0:
                    if self._user_schema_objects(connection):
                        raise VisitSchemaError(
                            "Visit schema version 0 is non-empty"
                        )
                    connection.executescript(_schema_sql())
                    created = True
                elif version != SCHEMA_VERSION:
                    raise VisitSchemaError(
                        f"Unsupported Visit schema version: {version}"
                    )
                self._startup_check(connection)
                if os.name == "posix":
                    os.chmod(self.db_path, 0o640)
        except VisitSchemaError:
            raise
        except sqlite3.Error as exc:
            raise _storage_error(exc) from exc
        except OSError as exc:
            raise VisitStorageError(VisitStorageCategory.UNAVAILABLE) from exc
        if not existed and not created:
            raise VisitSchemaError("Visit database creation did not complete")
        return created

    def create_or_reuse_start(
        self,
        start: NormalizedVisitStart,
        *,
        now_utc: str,
    ) -> VisitStartOutcome:
        try:
            with self._bounded_write(), closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    """
                    SELECT a.visit_id
                    FROM visit_authorizations AS a
                    WHERE a.auth_session_id = ? AND a.auth_run_number = ?
                    """,
                    (start.auth_session_id, start.auth_run_number),
                ).fetchone()
                if existing is not None:
                    connection.commit()
                    return VisitStartOutcome(
                        status="duplicate",
                        visit_id=str(existing["visit_id"]),
                    )

                row = connection.execute(
                    """
                    SELECT visit_id
                    FROM visits
                    WHERE site_id = ? AND client_mac = ? AND status = 'open'
                    """,
                    (start.site_id, start.client_mac),
                ).fetchone()
                created = row is None
                if created:
                    visit_id = str(uuid.uuid4())
                    connection.execute(
                        """
                        INSERT INTO visits (
                            visit_id, site_id, client_mac,
                            start_auth_session_id, start_auth_run_number,
                            start_final_reason, started_at, status,
                            start_ip, start_ssid, start_ap_mac,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)
                        """,
                        (
                            visit_id,
                            start.site_id,
                            start.client_mac,
                            start.auth_session_id,
                            start.auth_run_number,
                            start.final_reason,
                            start.authorized_at,
                            start.client_ip,
                            start.portal_ssid,
                            start.portal_ap_mac,
                            now_utc,
                            now_utc,
                        ),
                    )
                else:
                    visit_id = str(row["visit_id"])
                connection.execute(
                    """
                    INSERT INTO visit_authorizations (
                        visit_id, auth_session_id, auth_run_number,
                        authorization_attempt, authorized_at, final_reason,
                        client_ip, portal_ssid, portal_ap_mac,
                        portal_radio_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        visit_id,
                        start.auth_session_id,
                        start.auth_run_number,
                        start.authorization_attempt,
                        start.authorized_at,
                        start.final_reason,
                        start.client_ip,
                        start.portal_ssid,
                        start.portal_ap_mac,
                        start.portal_radio_id,
                        now_utc,
                    ),
                )
                connection.commit()
                return VisitStartOutcome(
                    status="opened" if created else "reused",
                    visit_id=visit_id,
                    created=created,
                    authorization_attached=True,
                )
        except sqlite3.Error as exc:
            raise _storage_error(exc) from exc

    def get_visit(self, site_id: str, visit_id: str) -> VisitRecord | None:
        with closing(self._connect(readonly=True)) as connection:
            row = connection.execute(
                "SELECT * FROM visits WHERE site_id = ? AND visit_id = ?",
                (site_id, visit_id),
            ).fetchone()
        return _visit_row(row) if row is not None else None

    def get_open_visit(
        self,
        site_id: str,
        client_mac: str,
    ) -> VisitRecord | None:
        with closing(self._connect(readonly=True)) as connection:
            row = connection.execute(
                """
                SELECT * FROM visits
                WHERE site_id = ? AND client_mac = ? AND status = 'open'
                """,
                (site_id, client_mac),
            ).fetchone()
        return _visit_row(row) if row is not None else None

    def list_visit_rows(
        self,
        *,
        site_id: str,
        from_utc: str | None,
        to_utc: str | None,
        status: str | None,
        client_mac: str | None,
        device_id: str | None,
        ssid: str | None,
        ap_mac: str | None,
        cursor: tuple[str, str] | None,
        limit: int,
    ) -> list[VisitRecord]:
        clauses = ["v.site_id = ?"]
        params: list[Any] = [site_id]
        if from_utc is not None:
            clauses.append("(v.closed_at IS NULL OR v.closed_at > ?)")
            params.append(from_utc)
        if to_utc is not None:
            clauses.append("v.started_at < ?")
            params.append(to_utc)
        if status is not None:
            clauses.append("v.status = ?")
            params.append(status)
        if client_mac is not None:
            clauses.append("v.client_mac = ?")
            params.append(client_mac)
        if device_id is not None:
            clauses.append("v.device_id = ?")
            params.append(device_id)
        if ssid is not None:
            clauses.append(
                """(
                    v.start_ssid = ? OR v.final_ssid = ? OR EXISTS (
                        SELECT 1 FROM visit_authorizations AS a
                        WHERE a.visit_id = v.visit_id AND a.portal_ssid = ?
                    )
                )"""
            )
            params.extend((ssid, ssid, ssid))
        if ap_mac is not None:
            clauses.append(
                """(
                    v.start_ap_mac = ? OR v.final_ap_mac = ? OR EXISTS (
                        SELECT 1 FROM visit_authorizations AS a
                        WHERE a.visit_id = v.visit_id AND a.portal_ap_mac = ?
                    )
                )"""
            )
            params.extend((ap_mac, ap_mac, ap_mac))
        if cursor is not None:
            clauses.append(
                "(v.started_at < ? OR (v.started_at = ? AND v.visit_id < ?))"
            )
            params.extend((cursor[0], cursor[0], cursor[1]))
        params.append(limit)
        with closing(self._connect(readonly=True)) as connection:
            rows = connection.execute(
                f"""
                SELECT v.* FROM visits AS v
                WHERE {' AND '.join(clauses)}
                ORDER BY v.started_at DESC, v.visit_id DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [_visit_row(row) for row in rows]

    def list_unmatched_rows(
        self,
        *,
        site_id: str,
        from_utc: str,
        to_utc: str,
        reason: str | None,
        cursor: tuple[str, str] | None,
        limit: int,
    ) -> list[sqlite3.Row]:
        clauses = [
            "site_id = ?",
            "processing_result = 'unmatched'",
            "processed_at >= ?",
            "processed_at < ?",
        ]
        params: list[Any] = [site_id, from_utc, to_utc]
        if reason is not None:
            clauses.append("reason = ?")
            params.append(reason)
        if cursor is not None:
            clauses.append(
                "(processed_at < ? OR (processed_at = ? AND event_id < ?))"
            )
            params.extend((cursor[0], cursor[0], cursor[1]))
        params.append(limit)
        with closing(self._connect(readonly=True)) as connection:
            return connection.execute(
                f"""
                SELECT * FROM visit_source_events
                WHERE {' AND '.join(clauses)}
                ORDER BY processed_at DESC, event_id DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()

    def list_due_reconciliation(
        self,
        now_utc: str,
        limit: int,
    ) -> tuple[ReconcileCandidate, ...]:
        with closing(self._connect(readonly=True)) as connection:
            rows = connection.execute(
                """
                SELECT visit_id, site_id, client_mac,
                       start_auth_session_id, device_id, initial_snapshot_id
                FROM visits
                WHERE (device_id IS NULL OR initial_snapshot_id IS NULL)
                  AND (
                    link_reconcile_next_at IS NULL
                    OR link_reconcile_next_at <= ?
                  )
                ORDER BY
                    COALESCE(link_reconcile_next_at, created_at) ASC,
                    started_at ASC,
                    visit_id ASC
                LIMIT ?
                """,
                (now_utc, limit),
            ).fetchall()
        return tuple(ReconcileCandidate(**dict(row)) for row in rows)

    def record_reconciliation_attempt(
        self,
        visit_id: str,
        *,
        device_id: str | None,
        initial_snapshot_id: str | None,
        attempted_at: str,
        retry_at: str,
    ) -> tuple[bool, bool]:
        try:
            with self._bounded_write(), closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                before = connection.execute(
                    """
                    SELECT device_id, initial_snapshot_id
                    FROM visits WHERE visit_id = ?
                    """,
                    (visit_id,),
                ).fetchone()
                if before is None:
                    connection.commit()
                    return False, True
                new_device = before["device_id"] or device_id
                new_snapshot = before["initial_snapshot_id"] or initial_snapshot_id
                complete = new_device is not None and new_snapshot is not None
                changed = (
                    new_device != before["device_id"]
                    or new_snapshot != before["initial_snapshot_id"]
                )
                connection.execute(
                    """
                    UPDATE visits
                    SET device_id = ?, initial_snapshot_id = ?,
                        link_reconcile_attempted_at = ?,
                        link_reconcile_next_at = ?,
                        link_reconcile_attempt_count =
                            link_reconcile_attempt_count + 1,
                        updated_at = CASE WHEN ? THEN ? ELSE updated_at END
                    WHERE visit_id = ?
                    """,
                    (
                        new_device,
                        new_snapshot,
                        attempted_at,
                        None if complete else retry_at,
                        int(changed),
                        attempted_at,
                        visit_id,
                    ),
                )
                connection.commit()
                return changed, complete
        except sqlite3.Error as exc:
            raise _storage_error(exc) from exc

    def authorization_count(self, visit_id: str) -> int:
        with closing(self._connect(readonly=True)) as connection:
            return int(connection.execute(
                "SELECT COUNT(*) FROM visit_authorizations WHERE visit_id = ?",
                (visit_id,),
            ).fetchone()[0])

    def _startup_check(self, connection: sqlite3.Connection) -> None:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version != SCHEMA_VERSION:
            raise VisitSchemaError("Visit schema version mismatch")
        quick = connection.execute("PRAGMA quick_check").fetchone()
        if not quick or str(quick[0]) != "ok":
            raise VisitSchemaError("Visit startup health check failed")
        self._validate_schema(connection)

    def _validate_schema(self, connection: sqlite3.Connection) -> None:
        if not REQUIRED_TABLES.issubset(self._table_names(connection)):
            raise VisitSchemaError("Visit schema is missing required tables")
        indexes = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
        if not set(REQUIRED_INDEXES).issubset(indexes):
            raise VisitSchemaError("Visit schema is missing required indexes")
        for name, expected in REQUIRED_INDEXES.items():
            actual = tuple(
                str(row[2])
                for row in connection.execute(f"PRAGMA index_info({name})")
            )
            if actual != expected:
                raise VisitSchemaError(f"Visit index is invalid: {name}")
        triggers = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger'"
            )
        }
        if not REQUIRED_TRIGGERS.issubset(triggers):
            raise VisitSchemaError("Visit schema is missing required triggers")
        for table, expected in REQUIRED_FOREIGN_KEYS.items():
            actual = {
                (str(row[3]), str(row[2]), str(row[4]), str(row[6]))
                for row in connection.execute(
                    f"PRAGMA foreign_key_list({table})"
                )
            }
            if not expected.issubset(actual):
                raise VisitSchemaError(
                    f"Visit foreign key contract is invalid: {table}"
                )
        for table, expected in REQUIRED_NOT_NULL_COLUMNS.items():
            actual = {
                str(row[1])
                for row in connection.execute(f"PRAGMA table_info({table})")
                if int(row[3]) == 1
            }
            if not expected.issubset(actual):
                raise VisitSchemaError(
                    f"Visit required-column contract is invalid: {table}"
                )
        open_index = next(
            (
                row
                for row in connection.execute("PRAGMA index_list(visits)")
                if str(row[1]) == "uq_visits_open_site_mac"
            ),
            None,
        )
        if (
            open_index is None
            or int(open_index[2]) != 1
            or int(open_index[4]) != 1
        ):
            raise VisitSchemaError("Visit open invariant index is invalid")
        violations = connection.execute("PRAGMA foreign_key_check").fetchone()
        if violations is not None:
            raise VisitSchemaError("Visit foreign key validation failed")

    @staticmethod
    def _table_names(connection: sqlite3.Connection) -> set[str]:
        return {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    @staticmethod
    def _user_schema_objects(connection: sqlite3.Connection) -> set[str]:
        return {
            str(row[0])
            for row in connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE name NOT LIKE 'sqlite_%'
                  AND type IN ('table', 'index', 'view', 'trigger')
                """
            )
        }

    def _connect(self, *, readonly: bool = False) -> sqlite3.Connection:
        self._validate_database_target(require_exists=readonly)
        if readonly:
            uri = f"{self.db_path.resolve(strict=False).as_uri()}?mode=ro"
            connection = sqlite3.connect(
                uri,
                uri=True,
                timeout=self.busy_timeout_ms / 1000,
            )
        else:
            connection = sqlite3.connect(
                str(self.db_path),
                timeout=self.busy_timeout_ms / 1000,
            )
        connection.row_factory = sqlite3.Row
        try:
            connection.execute(f"PRAGMA busy_timeout={self.busy_timeout_ms}")
            connection.execute("PRAGMA foreign_keys=ON")
            if readonly:
                connection.execute("PRAGMA query_only=ON")
            else:
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute("PRAGMA synchronous=NORMAL")
        except Exception:
            connection.close()
            raise
        return connection

    @contextmanager
    def _bounded_write(self):
        acquired = self._write_lock.acquire(
            timeout=self.busy_timeout_ms / 1000
        )
        if not acquired:
            raise VisitStorageError(
                VisitStorageCategory.BUSY,
                "Visit write slot is busy",
            )
        try:
            yield
        finally:
            self._write_lock.release()

    def _ensure_parent(self) -> None:
        parent = self.db_path.parent
        if parent.exists():
            if not parent.is_dir() or not os.access(parent, os.W_OK):
                raise VisitStorageError(
                    VisitStorageCategory.UNAVAILABLE,
                    "Visit database parent is unavailable",
                )
            return
        resolved = parent.resolve(strict=False)
        allowed = ALLOWED_AUTO_CREATE_ROOT.resolve(strict=False)
        if not (resolved == allowed or allowed in resolved.parents):
            raise VisitStorageError(
                VisitStorageCategory.UNAVAILABLE,
                "Missing Visit database parent is not approved",
            )
        try:
            parent.mkdir(parents=True, mode=0o750, exist_ok=True)
            if os.name == "posix":
                os.chmod(parent, 0o750)
        except OSError as exc:
            raise VisitStorageError(VisitStorageCategory.UNAVAILABLE) from exc

    def _database_exists(self) -> bool:
        return self._validate_database_target(require_exists=False)

    def _validate_database_target(self, *, require_exists: bool) -> bool:
        try:
            target = os.lstat(self.db_path)
        except FileNotFoundError:
            if require_exists:
                raise VisitStorageError(
                    VisitStorageCategory.UNAVAILABLE,
                    "Visit database does not exist",
                )
            return False
        except OSError as exc:
            raise VisitStorageError(VisitStorageCategory.UNAVAILABLE) from exc
        if stat.S_ISLNK(target.st_mode) or not stat.S_ISREG(target.st_mode):
            raise VisitStorageError(
                VisitStorageCategory.UNAVAILABLE,
                "Visit database target must be a regular file",
            )
        return True


def _visit_row(row: sqlite3.Row) -> VisitRecord:
    return VisitRecord(**dict(row))


def classify_sqlite_error(exc: sqlite3.Error) -> VisitStorageCategory:
    code = getattr(exc, "sqlite_errorcode", None)
    primary = (code & 0xFF) if isinstance(code, int) else None
    if primary in {_SQLITE_BUSY, _SQLITE_LOCKED}:
        return VisitStorageCategory.BUSY
    if primary == _SQLITE_FULL:
        return VisitStorageCategory.FULL
    if primary == _SQLITE_IOERR:
        return VisitStorageCategory.IO_ERROR
    if primary in {_SQLITE_CORRUPT, _SQLITE_NOTADB}:
        return VisitStorageCategory.CORRUPT
    if primary in {_SQLITE_READONLY, _SQLITE_CANTOPEN}:
        return VisitStorageCategory.UNAVAILABLE
    if primary == _SQLITE_CONSTRAINT:
        return VisitStorageCategory.CONSTRAINT
    message = str(exc).lower()
    for fragment, category in (
        ("database is locked", VisitStorageCategory.BUSY),
        ("database table is locked", VisitStorageCategory.BUSY),
        ("database or disk is full", VisitStorageCategory.FULL),
        ("disk i/o error", VisitStorageCategory.IO_ERROR),
        ("database disk image is malformed", VisitStorageCategory.CORRUPT),
        ("file is not a database", VisitStorageCategory.CORRUPT),
        ("readonly database", VisitStorageCategory.UNAVAILABLE),
        ("unable to open database file", VisitStorageCategory.UNAVAILABLE),
        ("constraint failed", VisitStorageCategory.CONSTRAINT),
    ):
        if fragment in message:
            return category
    return VisitStorageCategory.UNKNOWN


def _storage_error(exc: sqlite3.Error) -> VisitStorageError:
    return VisitStorageError(classify_sqlite_error(exc))
