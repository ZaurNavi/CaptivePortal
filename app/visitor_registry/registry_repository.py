"""SQLite persistence for Visitor Device Registry schema version 1."""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Iterable

from .registry_config import (
    ensure_registry_parent,
    registry_database_exists,
    validate_registry_database_target,
)
from .registry_models import (
    ApplyOutcome,
    ApplyResult,
    DecisionKind,
    ReaderState,
    RegistryConfig,
    RegistryEventDecision,
    RegistrySchemaError,
    RegistrySnapshot,
    RegistryStatus,
    SourceLineRecord,
)


SCHEMA_VERSION = 1
BUSY_TIMEOUT_MS = 250
_REGISTRY_STATES = frozenset({
    "disabled",
    "initializing",
    "backfilling",
    "ready",
    "degraded",
    "unavailable",
    "stopping",
})
_REGISTRY_TABLES = frozenset({
    "visitor_devices",
    "device_snapshots",
    "processed_snapshot_events",
    "reader_state",
    "registry_state",
})
_REQUIRED_INDEXES = frozenset({
    "idx_visitor_devices_last_seen",
    "idx_visitor_devices_hostname",
    "idx_visitor_devices_ip",
    "idx_visitor_devices_ssid",
    "idx_visitor_devices_ap_mac",
    "idx_visitor_devices_controller_id",
    "idx_device_snapshots_device_order",
    "idx_device_snapshots_auth_session",
    "idx_device_snapshots_site_order",
    "idx_device_snapshots_ssid_order",
    "idx_processed_snapshot_source",
})
_PROFILE_COLUMNS = (
    "controller_client_id",
    "name",
    "hostname",
    "system_name",
    "device_type",
)
_COLUMN_TYPES = {
    "visitor_devices": {
        **{
            name: "TEXT"
            for name in (
                "device_id", "mac", "first_seen_at", "last_seen_at",
                "current_authorized_at", "current_captured_at",
                "current_snapshot_id", "last_auth_session_id",
                "last_site_id", "last_known_controller_client_id",
                "last_known_name", "last_known_hostname",
                "last_known_system_name", "last_known_device_type",
                "last_ip", "last_ssid", "last_ap_name", "last_ap_mac",
                "created_at", "updated_at",
            )
        },
        **{
            name: "INTEGER"
            for name in (
                "last_radio_id", "last_channel", "last_rssi",
                "last_snr", "last_active", "last_auth_status",
                "snapshot_count",
            )
        },
    },
    "device_snapshots": {
        **{
            name: "TEXT"
            for name in (
                "snapshot_id", "device_id", "event_sha256",
                "auth_session_id", "site_id", "requested_mac",
                "authorized_at", "captured_at", "auth_final_reason",
                "retry_request_id", "portal_client_ip", "portal_ssid",
                "portal_ap_mac", "portal_radio_id",
                "controller_client_id", "name", "hostname",
                "system_name", "device_type", "ip", "ssid",
                "ap_name", "ap_mac", "auth_context_json",
                "client_json", "raw_controller_snapshot_json",
                "source_identity", "source_path", "processed_at",
            )
        },
        **{
            name: "INTEGER"
            for name in (
                "schema_version", "attempts", "queue_delay_ms",
                "request_duration_ms", "snapshot_lag_ms",
                "auth_run_number", "authorization_attempt",
                "radio_id", "channel", "rssi", "snr",
                "traffic_down", "traffic_up", "uptime",
                "controller_last_seen_ms", "active", "auth_status",
                "source_offset_start", "source_offset_end",
            )
        },
    },
    "processed_snapshot_events": {
        name: "TEXT"
        for name in (
            "snapshot_id", "event_sha256", "processing_result",
            "skip_reason", "source_identity", "source_path",
            "processed_at",
        )
    } | {
        "source_offset_start": "INTEGER",
        "source_offset_end": "INTEGER",
    },
    "reader_state": {
        name: "TEXT"
        for name in (
            "source_identity", "source_path", "source_checkpoint",
            "updated_at",
        )
    } | {
        "source_offset": "INTEGER",
        "last_observed_size": "INTEGER",
        "retired_completed": "INTEGER",
        "missing_warning_emitted": "INTEGER",
    },
    "registry_state": {
        name: "TEXT"
        for name in (
            "state", "state_reason", "state_changed_at",
            "initial_backfill_completed_at",
            "last_successful_scan_at", "last_snapshot_stored_at",
            "created_at", "updated_at",
        )
    } | {
        "singleton_id": "INTEGER",
        "initial_backfill_completed": "INTEGER",
    },
}
_REQUIRED_NOT_NULL = {
    "visitor_devices": {
        "mac", "first_seen_at", "last_seen_at",
        "current_authorized_at", "current_captured_at",
        "current_snapshot_id", "last_auth_session_id",
        "last_site_id", "snapshot_count", "created_at", "updated_at",
    },
    "device_snapshots": {
        "device_id", "event_sha256", "schema_version",
        "auth_session_id", "site_id", "requested_mac",
        "authorized_at", "captured_at", "auth_context_json",
        "client_json", "raw_controller_snapshot_json",
        "source_identity", "source_path", "source_offset_start",
        "source_offset_end", "processed_at",
    },
    "processed_snapshot_events": {
        "event_sha256", "processing_result", "source_identity",
        "source_path", "source_offset_start", "source_offset_end",
        "processed_at",
    },
    "reader_state": {
        "source_path", "source_offset", "retired_completed",
        "missing_warning_emitted", "updated_at",
    },
    "registry_state": {
        "state", "state_changed_at", "initial_backfill_completed",
        "created_at", "updated_at",
    },
}
_PRIMARY_KEYS = {
    "visitor_devices": "device_id",
    "device_snapshots": "snapshot_id",
    "processed_snapshot_events": "snapshot_id",
    "reader_state": "source_identity",
    "registry_state": "singleton_id",
}
_INDEX_COLUMNS = {
    "idx_visitor_devices_last_seen": ("last_seen_at",),
    "idx_visitor_devices_hostname": ("last_known_hostname",),
    "idx_visitor_devices_ip": ("last_ip",),
    "idx_visitor_devices_ssid": ("last_ssid",),
    "idx_visitor_devices_ap_mac": ("last_ap_mac",),
    "idx_visitor_devices_controller_id": (
        "last_known_controller_client_id",
    ),
    "idx_device_snapshots_device_order": (
        "device_id", "authorized_at", "captured_at", "snapshot_id",
    ),
    "idx_device_snapshots_auth_session": ("auth_session_id",),
    "idx_device_snapshots_site_order": (
        "site_id", "authorized_at", "captured_at",
    ),
    "idx_device_snapshots_ssid_order": (
        "ssid", "authorized_at", "captured_at",
    ),
    "idx_processed_snapshot_source": ("source_identity",),
}
_REQUIRED_CHECK_FRAGMENTS = {
    "visitor_devices": (
        "snapshot_count >= 0",
        "last_active in (0, 1)",
    ),
    "device_snapshots": (
        "source_offset_start >= 0",
        "source_offset_end > source_offset_start",
        "attempts is null or attempts >= 0",
        "queue_delay_ms is null or queue_delay_ms >= 0",
        "request_duration_ms is null or request_duration_ms >= 0",
        "snapshot_lag_ms is null or snapshot_lag_ms >= 0",
        "traffic_down is null or traffic_down >= 0",
        "traffic_up is null or traffic_up >= 0",
        "uptime is null or uptime >= 0",
        "controller_last_seen_ms is null or controller_last_seen_ms >= 0",
        "active is null or active in (0, 1)",
    ),
    "processed_snapshot_events": (
        "source_offset_start >= 0",
        "source_offset_end > source_offset_start",
        "processing_result = 'stored' and skip_reason is null",
        "processing_result = 'skipped' and skip_reason is not null",
        "skip_reason in (",
        "'missing_required_field'",
        "'invalid_field_type'",
        "'invalid_field_range'",
        "'invalid_field_format'",
        "'invalid_field_value'",
        "'client_mac_mismatch'",
        "'snapshot_id_mismatch'",
        "'unsupported_schema_version'",
    ),
    "reader_state": (
        "source_offset >= 0",
        "last_observed_size is null or last_observed_size >= 0",
        "retired_completed in (0, 1)",
        "missing_warning_emitted in (0, 1)",
    ),
    "registry_state": (
        "singleton_id = 1",
        "state in (",
        "'disabled'",
        "'initializing'",
        "'backfilling'",
        "'ready'",
        "'degraded'",
        "'unavailable'",
        "'stopping'",
        "initial_backfill_completed = 0 and "
        "initial_backfill_completed_at is null",
        "initial_backfill_completed = 1 and "
        "initial_backfill_completed_at is not null",
    ),
}


class VisitorRegistryRepository:
    """Own short SQLite connections and the atomic line transaction."""

    def __init__(
        self,
        config: RegistryConfig,
        *,
        busy_timeout_ms: int = BUSY_TIMEOUT_MS,
    ):
        self.config = config
        self.db_path = Path(config.db_path)
        self.busy_timeout_ms = max(1, int(busy_timeout_ms))

    def initialize(self, now_utc: str) -> bool:
        ensure_registry_parent(self.config)
        existed = registry_database_exists(self.db_path)
        migrated = False
        try:
            with closing(self._connect()) as connection:
                if os.name == "posix":
                    os.chmod(self.db_path, 0o640)
                version = int(
                    connection.execute(
                        "PRAGMA user_version"
                    ).fetchone()[0]
                )
                tables = self._table_names(connection)
                if version > SCHEMA_VERSION:
                    raise RegistrySchemaError(
                        "Visitor Registry schema is newer than this code"
                    )
                if version == 0:
                    if tables.intersection(_REGISTRY_TABLES):
                        raise RegistrySchemaError(
                            "Visitor Registry schema version 0 is partial"
                        )
                    self._create_schema(connection, now_utc)
                    migrated = True
                elif version == SCHEMA_VERSION:
                    self._validate_schema(connection)
                else:
                    raise RegistrySchemaError(
                        f"Unsupported Registry schema version: {version}"
                    )

                quick_check = connection.execute(
                    "PRAGMA quick_check"
                ).fetchone()
                if not quick_check or quick_check[0] != "ok":
                    raise RegistrySchemaError(
                        "Visitor Registry startup health check failed"
                    )
                self._validate_schema(connection)
        except Exception:
            if not existed and self.db_path.exists():
                # A failed first migration is evidence.  Preserve it for
                # diagnosis instead of deleting or silently recreating it.
                pass
            raise
        return migrated

    def run_full_audit(self) -> None:
        """Run expensive integrity and aggregate checks off the HTTP path."""
        with closing(self._connect(readonly=True)) as connection:
            integrity = connection.execute(
                "PRAGMA integrity_check"
            ).fetchone()
            if not integrity or integrity[0] != "ok":
                raise RegistrySchemaError(
                    "Visitor Registry integrity check failed"
                )
            self._validate_schema(
                connection,
                audit_snapshot_counts=True,
            )

    def validate_runtime_health(self) -> None:
        """Reopen and validate the database after an ambiguous I/O error."""
        with closing(self._connect(readonly=True)) as connection:
            version = int(
                connection.execute("PRAGMA user_version").fetchone()[0]
            )
            if version != SCHEMA_VERSION:
                raise RegistrySchemaError(
                    "Visitor Registry schema version changed at runtime"
                )
            quick_check = connection.execute(
                "PRAGMA quick_check"
            ).fetchone()
            if not quick_check or quick_check[0] != "ok":
                raise RegistrySchemaError(
                    "Visitor Registry runtime health check failed"
                )
            self._validate_schema(connection)

    def _create_schema(
        self,
        connection: sqlite3.Connection,
        now_utc: str,
    ) -> None:
        connection.executescript(
            """
            BEGIN IMMEDIATE;

            CREATE TABLE visitor_devices (
                device_id TEXT PRIMARY KEY,
                mac TEXT NOT NULL UNIQUE,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                current_authorized_at TEXT NOT NULL,
                current_captured_at TEXT NOT NULL,
                current_snapshot_id TEXT NOT NULL,
                last_auth_session_id TEXT NOT NULL,
                last_site_id TEXT NOT NULL,
                last_known_controller_client_id TEXT,
                last_known_name TEXT,
                last_known_hostname TEXT,
                last_known_system_name TEXT,
                last_known_device_type TEXT,
                last_ip TEXT,
                last_ssid TEXT,
                last_ap_name TEXT,
                last_ap_mac TEXT,
                last_radio_id INTEGER,
                last_channel INTEGER,
                last_rssi INTEGER,
                last_snr INTEGER,
                last_active INTEGER,
                last_auth_status INTEGER,
                snapshot_count INTEGER NOT NULL DEFAULT 0
                    CHECK (snapshot_count >= 0),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                CHECK (
                    last_active IS NULL
                    OR last_active IN (0, 1)
                )
            );

            CREATE TABLE device_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                event_sha256 TEXT NOT NULL,
                schema_version INTEGER NOT NULL,
                auth_session_id TEXT NOT NULL,
                site_id TEXT NOT NULL,
                requested_mac TEXT NOT NULL,
                authorized_at TEXT NOT NULL,
                captured_at TEXT NOT NULL,
                attempts INTEGER,
                queue_delay_ms INTEGER,
                request_duration_ms INTEGER,
                snapshot_lag_ms INTEGER,
                auth_final_reason TEXT,
                auth_run_number INTEGER,
                authorization_attempt INTEGER,
                retry_request_id TEXT,
                portal_client_ip TEXT,
                portal_ssid TEXT,
                portal_ap_mac TEXT,
                portal_radio_id TEXT,
                controller_client_id TEXT,
                name TEXT,
                hostname TEXT,
                system_name TEXT,
                device_type TEXT,
                ip TEXT,
                ssid TEXT,
                ap_name TEXT,
                ap_mac TEXT,
                radio_id INTEGER,
                channel INTEGER,
                rssi INTEGER,
                snr INTEGER,
                traffic_down INTEGER,
                traffic_up INTEGER,
                uptime INTEGER,
                controller_last_seen_ms INTEGER,
                active INTEGER,
                auth_status INTEGER,
                auth_context_json TEXT NOT NULL,
                client_json TEXT NOT NULL,
                raw_controller_snapshot_json TEXT NOT NULL,
                source_identity TEXT NOT NULL,
                source_path TEXT NOT NULL,
                source_offset_start INTEGER NOT NULL,
                source_offset_end INTEGER NOT NULL,
                processed_at TEXT NOT NULL,
                FOREIGN KEY (device_id)
                    REFERENCES visitor_devices(device_id)
                    ON DELETE CASCADE,
                CHECK (source_offset_start >= 0),
                CHECK (source_offset_end > source_offset_start),
                CHECK (attempts IS NULL OR attempts >= 0),
                CHECK (
                    queue_delay_ms IS NULL
                    OR queue_delay_ms >= 0
                ),
                CHECK (
                    request_duration_ms IS NULL
                    OR request_duration_ms >= 0
                ),
                CHECK (
                    snapshot_lag_ms IS NULL
                    OR snapshot_lag_ms >= 0
                ),
                CHECK (
                    traffic_down IS NULL
                    OR traffic_down >= 0
                ),
                CHECK (traffic_up IS NULL OR traffic_up >= 0),
                CHECK (uptime IS NULL OR uptime >= 0),
                CHECK (
                    controller_last_seen_ms IS NULL
                    OR controller_last_seen_ms >= 0
                ),
                CHECK (active IS NULL OR active IN (0, 1))
            );

            CREATE TABLE processed_snapshot_events (
                snapshot_id TEXT PRIMARY KEY,
                event_sha256 TEXT NOT NULL,
                processing_result TEXT NOT NULL,
                skip_reason TEXT,
                source_identity TEXT NOT NULL,
                source_path TEXT NOT NULL,
                source_offset_start INTEGER NOT NULL,
                source_offset_end INTEGER NOT NULL,
                processed_at TEXT NOT NULL,
                CHECK (source_offset_start >= 0),
                CHECK (source_offset_end > source_offset_start),
                CHECK (
                    (
                        processing_result = 'stored'
                        AND skip_reason IS NULL
                    )
                    OR
                    (
                        processing_result = 'skipped'
                        AND skip_reason IS NOT NULL
                        AND skip_reason IN (
                            'missing_required_field',
                            'invalid_field_type',
                            'invalid_field_range',
                            'invalid_field_format',
                            'invalid_field_value',
                            'client_mac_mismatch',
                            'snapshot_id_mismatch',
                            'unsupported_schema_version'
                        )
                    )
                )
            );

            CREATE TABLE reader_state (
                source_identity TEXT PRIMARY KEY,
                source_path TEXT NOT NULL,
                source_offset INTEGER NOT NULL DEFAULT 0,
                last_observed_size INTEGER,
                source_checkpoint TEXT,
                retired_completed INTEGER NOT NULL DEFAULT 0,
                missing_warning_emitted INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                CHECK (source_offset >= 0),
                CHECK (
                    last_observed_size IS NULL
                    OR last_observed_size >= 0
                ),
                CHECK (retired_completed IN (0, 1)),
                CHECK (missing_warning_emitted IN (0, 1))
            );

            CREATE TABLE registry_state (
                singleton_id INTEGER PRIMARY KEY
                    CHECK (singleton_id = 1),
                state TEXT NOT NULL,
                state_reason TEXT,
                state_changed_at TEXT NOT NULL,
                initial_backfill_completed INTEGER NOT NULL DEFAULT 0,
                initial_backfill_completed_at TEXT,
                last_successful_scan_at TEXT,
                last_snapshot_stored_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                CHECK (
                    state IN (
                        'disabled',
                        'initializing',
                        'backfilling',
                        'ready',
                        'degraded',
                        'unavailable',
                        'stopping'
                    )
                ),
                CHECK (
                    (
                        initial_backfill_completed = 0
                        AND initial_backfill_completed_at IS NULL
                    )
                    OR
                    (
                        initial_backfill_completed = 1
                        AND initial_backfill_completed_at IS NOT NULL
                    )
                )
            );

            CREATE INDEX idx_visitor_devices_last_seen
            ON visitor_devices(last_seen_at DESC);
            CREATE INDEX idx_visitor_devices_hostname
            ON visitor_devices(last_known_hostname COLLATE NOCASE);
            CREATE INDEX idx_visitor_devices_ip
            ON visitor_devices(last_ip);
            CREATE INDEX idx_visitor_devices_ssid
            ON visitor_devices(last_ssid);
            CREATE INDEX idx_visitor_devices_ap_mac
            ON visitor_devices(last_ap_mac);
            CREATE INDEX idx_visitor_devices_controller_id
            ON visitor_devices(last_known_controller_client_id);
            CREATE INDEX idx_device_snapshots_device_order
            ON device_snapshots(
                device_id,
                authorized_at DESC,
                captured_at DESC,
                snapshot_id DESC
            );
            CREATE INDEX idx_device_snapshots_auth_session
            ON device_snapshots(auth_session_id);
            CREATE INDEX idx_device_snapshots_site_order
            ON device_snapshots(
                site_id,
                authorized_at DESC,
                captured_at DESC
            );
            CREATE INDEX idx_device_snapshots_ssid_order
            ON device_snapshots(
                ssid,
                authorized_at DESC,
                captured_at DESC
            );
            CREATE INDEX idx_processed_snapshot_source
            ON processed_snapshot_events(source_identity);

            """
        )
        try:
            self._migration_checkpoint("before_registry_state_insert")
            connection.execute(
                """
                INSERT INTO registry_state (
                    singleton_id,
                    state,
                    state_reason,
                    state_changed_at,
                    initial_backfill_completed,
                    initial_backfill_completed_at,
                    last_successful_scan_at,
                    last_snapshot_stored_at,
                    created_at,
                    updated_at
                )
                VALUES (
                    1, 'initializing', NULL, ?,
                    0, NULL, NULL, NULL, ?, ?
                )
                """,
                (now_utc, now_utc, now_utc),
            )
            self._migration_checkpoint("after_registry_state_insert")
            connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    def _migration_checkpoint(self, stage: str) -> None:
        """Test seam for proving that schema creation is crash-atomic."""
        return None

    def _validate_schema(
        self,
        connection: sqlite3.Connection,
        *,
        audit_snapshot_counts: bool = False,
    ) -> None:
        tables = self._table_names(connection)
        if not _REGISTRY_TABLES.issubset(tables):
            raise RegistrySchemaError(
                "Visitor Registry schema is missing required tables"
            )
        required_columns = {
            "visitor_devices": {
                "device_id", "mac", "first_seen_at", "last_seen_at",
                "current_authorized_at", "current_captured_at",
                "current_snapshot_id", "last_auth_session_id",
                "last_site_id", "snapshot_count", "created_at",
                "updated_at",
            },
            "device_snapshots": {
                "snapshot_id", "device_id", "event_sha256",
                "schema_version", "auth_session_id", "site_id",
                "requested_mac", "authorized_at", "captured_at",
                "auth_context_json", "client_json",
                "raw_controller_snapshot_json", "source_identity",
                "source_path", "source_offset_start",
                "source_offset_end", "processed_at",
            },
            "processed_snapshot_events": {
                "snapshot_id", "event_sha256", "processing_result",
                "skip_reason", "source_identity", "source_path",
                "source_offset_start", "source_offset_end",
                "processed_at",
            },
            "reader_state": {
                "source_identity", "source_path", "source_offset",
                "last_observed_size", "source_checkpoint",
                "retired_completed", "missing_warning_emitted",
                "updated_at",
            },
            "registry_state": {
                "singleton_id", "state", "state_reason",
                "state_changed_at", "initial_backfill_completed",
                "initial_backfill_completed_at",
                "last_successful_scan_at",
                "last_snapshot_stored_at", "created_at", "updated_at",
            },
        }
        for table, columns in required_columns.items():
            table_rows = connection.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()
            actual = {str(row[1]): row for row in table_rows}
            if not columns.issubset(actual):
                raise RegistrySchemaError(
                    f"Visitor Registry table {table} is incomplete"
                )
            expected_types = _COLUMN_TYPES[table]
            for column, expected_type in expected_types.items():
                row = actual.get(column)
                if row is None or str(row[2]).upper() != expected_type:
                    raise RegistrySchemaError(
                        "Visitor Registry column type mismatch: "
                        f"{table}.{column}"
                    )
            for column in _REQUIRED_NOT_NULL[table]:
                if int(actual[column][3]) != 1:
                    raise RegistrySchemaError(
                        "Visitor Registry NOT NULL constraint missing: "
                        f"{table}.{column}"
                    )
            primary_key = _PRIMARY_KEYS[table]
            if int(actual[primary_key][5]) != 1:
                raise RegistrySchemaError(
                    "Visitor Registry primary key is invalid: "
                    f"{table}.{primary_key}"
                )
            sql_row = connection.execute(
                """
                SELECT sql
                FROM sqlite_master
                WHERE type = 'table' AND name = ?
                """,
                (table,),
            ).fetchone()
            normalized_sql = _normalize_schema_sql(
                "" if sql_row is None else str(sql_row[0])
            )
            for fragment in _REQUIRED_CHECK_FRAGMENTS[table]:
                if _normalize_schema_sql(fragment) not in normalized_sql:
                    raise RegistrySchemaError(
                        "Visitor Registry CHECK constraint missing: "
                        f"{table}"
                    )
        indexes = {
            str(row[0])
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'index'
                """
            )
        }
        if not _REQUIRED_INDEXES.issubset(indexes):
            raise RegistrySchemaError(
                "Visitor Registry schema is missing required indexes"
            )
        for index_name, expected_columns in _INDEX_COLUMNS.items():
            actual_columns = tuple(
                str(row[2])
                for row in connection.execute(
                    f"PRAGMA index_info({index_name})"
                )
            )
            if actual_columns != expected_columns:
                raise RegistrySchemaError(
                    "Visitor Registry index definition is invalid: "
                    f"{index_name}"
                )
        mac_unique = any(
            int(index_row[2]) == 1
            and tuple(
                str(column_row[2])
                for column_row in connection.execute(
                    f"PRAGMA index_info({index_row[1]})"
                )
            ) == ("mac",)
            for index_row in connection.execute(
                "PRAGMA index_list(visitor_devices)"
            )
        )
        if not mac_unique:
            raise RegistrySchemaError(
                "Visitor Registry MAC uniqueness constraint is missing"
            )
        singleton = connection.execute(
            """
            SELECT COUNT(*),
                   SUM(CASE WHEN singleton_id = 1 THEN 1 ELSE 0 END),
                   MAX(CASE WHEN singleton_id = 1 THEN state END)
            FROM registry_state
            """
        ).fetchone()
        if (
            singleton is None
            or tuple(singleton[:2]) != (1, 1)
            or singleton[2] not in _REGISTRY_STATES
        ):
            raise RegistrySchemaError(
                "Visitor Registry state singleton is invalid"
            )
        foreign_keys = connection.execute(
            "PRAGMA foreign_key_list(device_snapshots)"
        ).fetchall()
        expected_fk = any(
            str(row[2]) == "visitor_devices"
            and str(row[3]) == "device_id"
            and str(row[4]) == "device_id"
            and str(row[6]).upper() == "CASCADE"
            for row in foreign_keys
        )
        if not expected_fk:
            raise RegistrySchemaError(
                "Visitor Registry snapshot foreign key is invalid"
            )
        if audit_snapshot_counts:
            if connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchone() is not None:
                raise RegistrySchemaError(
                    "Visitor Registry foreign-key validation failed"
                )
            self._validate_snapshot_counts(connection)

    def _validate_snapshot_counts(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        mismatch = connection.execute(
            """
            SELECT d.device_id
            FROM visitor_devices AS d
            LEFT JOIN device_snapshots AS s
              ON s.device_id = d.device_id
            GROUP BY d.device_id
            HAVING d.snapshot_count != COUNT(s.snapshot_id)
            LIMIT 1
            """
        ).fetchone()
        if mismatch is not None:
            raise RegistrySchemaError(
                "Visitor Registry snapshot_count invariant failed"
            )

    @staticmethod
    def _table_names(connection: sqlite3.Connection) -> set[str]:
        return {
            str(row[0])
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            )
        }

    def apply_source_line(
        self,
        record: SourceLineRecord,
        decision: RegistryEventDecision,
    ) -> ApplyResult:
        """Atomically apply one complete source line and its reader offset."""
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            if decision.kind is DecisionKind.ADVANCE:
                self._upsert_reader_state(
                    connection,
                    record,
                    retired_completed=False,
                    missing_warning_emitted=False,
                )
                connection.commit()
                return ApplyResult(ApplyOutcome.ADVANCED)

            if not decision.snapshot_id or not decision.event_sha256:
                connection.rollback()
                raise ValueError(
                    "Processed decisions require snapshot ID and hash"
                )
            existing = connection.execute(
                """
                SELECT event_sha256
                FROM processed_snapshot_events
                WHERE snapshot_id = ?
                """,
                (decision.snapshot_id,),
            ).fetchone()
            if existing is not None:
                outcome = (
                    ApplyOutcome.DUPLICATE
                    if existing[0] == decision.event_sha256
                    else ApplyOutcome.CONFLICT
                )
                self._upsert_reader_state(
                    connection,
                    record,
                    retired_completed=False,
                    missing_warning_emitted=False,
                )
                connection.commit()
                return ApplyResult(
                    outcome,
                    snapshot_id=decision.snapshot_id,
                )

            if decision.kind is DecisionKind.SKIP:
                if decision.skip_reason is None:
                    connection.rollback()
                    raise ValueError("Skipped decision needs skip_reason")
                self._insert_processed(
                    connection,
                    record,
                    snapshot_id=decision.snapshot_id,
                    event_sha256=decision.event_sha256,
                    processing_result="skipped",
                    skip_reason=decision.skip_reason,
                )
                self._upsert_reader_state(
                    connection,
                    record,
                    retired_completed=False,
                    missing_warning_emitted=False,
                )
                connection.commit()
                return ApplyResult(
                    ApplyOutcome.SKIPPED,
                    snapshot_id=decision.snapshot_id,
                    skip_reason=decision.skip_reason,
                )

            snapshot = decision.snapshot
            if snapshot is None:
                connection.rollback()
                raise ValueError("Stored decision needs a snapshot")
            device_created = self._store_snapshot(
                connection,
                record,
                snapshot,
            )
            self._insert_processed(
                connection,
                record,
                snapshot_id=snapshot.snapshot_id,
                event_sha256=snapshot.event_sha256,
                processing_result="stored",
                skip_reason=None,
            )
            self._upsert_reader_state(
                connection,
                record,
                retired_completed=False,
                missing_warning_emitted=False,
            )
            connection.execute(
                """
                UPDATE registry_state
                SET last_snapshot_stored_at = ?,
                    updated_at = ?
                WHERE singleton_id = 1
                """,
                (record.processing_now, record.processing_now),
            )
            connection.commit()
            return ApplyResult(
                ApplyOutcome.STORED,
                snapshot_id=snapshot.snapshot_id,
                device_id=snapshot.device_id,
                device_created=device_created,
            )

    def _store_snapshot(
        self,
        connection: sqlite3.Connection,
        record: SourceLineRecord,
        snapshot: RegistrySnapshot,
    ) -> bool:
        existing = connection.execute(
            """
            SELECT device_id
            FROM visitor_devices
            WHERE mac = ?
            """,
            (snapshot.mac,),
        ).fetchone()
        if existing is not None and existing[0] != snapshot.device_id:
            raise RegistrySchemaError(
                "Stored device identity does not match UUID namespace"
            )
        if existing is None:
            connection.execute(
                """
                INSERT INTO visitor_devices (
                    device_id, mac,
                    first_seen_at, last_seen_at,
                    current_authorized_at, current_captured_at,
                    current_snapshot_id,
                    last_auth_session_id, last_site_id,
                    last_known_controller_client_id,
                    last_known_name, last_known_hostname,
                    last_known_system_name, last_known_device_type,
                    last_ip, last_ssid, last_ap_name, last_ap_mac,
                    last_radio_id, last_channel, last_rssi, last_snr,
                    last_active, last_auth_status,
                    snapshot_count, created_at, updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    0, ?, ?
                )
                """,
                (
                    snapshot.device_id, snapshot.mac,
                    snapshot.authorized_at, snapshot.authorized_at,
                    snapshot.authorized_at, snapshot.captured_at,
                    snapshot.snapshot_id,
                    snapshot.auth_session_id, snapshot.site_id,
                    snapshot.controller_client_id, snapshot.name,
                    snapshot.hostname, snapshot.system_name,
                    snapshot.device_type, snapshot.ip, snapshot.ssid,
                    snapshot.ap_name, snapshot.ap_mac,
                    snapshot.radio_id, snapshot.channel,
                    snapshot.rssi, snapshot.snr,
                    _db_bool(snapshot.active), snapshot.auth_status,
                    record.processing_now, record.processing_now,
                ),
            )
        connection.execute(
            """
            INSERT INTO device_snapshots (
                snapshot_id, device_id, event_sha256,
                schema_version, auth_session_id, site_id, requested_mac,
                authorized_at, captured_at,
                attempts, queue_delay_ms, request_duration_ms,
                snapshot_lag_ms,
                auth_final_reason, auth_run_number,
                authorization_attempt, retry_request_id,
                portal_client_ip, portal_ssid, portal_ap_mac,
                portal_radio_id,
                controller_client_id, name, hostname,
                system_name, device_type,
                ip, ssid, ap_name, ap_mac,
                radio_id, channel, rssi, snr,
                traffic_down, traffic_up, uptime,
                controller_last_seen_ms, active, auth_status,
                auth_context_json, client_json,
                raw_controller_snapshot_json,
                source_identity, source_path,
                source_offset_start, source_offset_end,
                processed_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                snapshot.snapshot_id, snapshot.device_id,
                snapshot.event_sha256, snapshot.schema_version,
                snapshot.auth_session_id, snapshot.site_id,
                snapshot.requested_mac, snapshot.authorized_at,
                snapshot.captured_at, snapshot.attempts,
                snapshot.queue_delay_ms, snapshot.request_duration_ms,
                snapshot.snapshot_lag_ms, snapshot.auth_final_reason,
                snapshot.auth_run_number,
                snapshot.authorization_attempt,
                snapshot.retry_request_id, snapshot.portal_client_ip,
                snapshot.portal_ssid, snapshot.portal_ap_mac,
                snapshot.portal_radio_id,
                snapshot.controller_client_id, snapshot.name,
                snapshot.hostname, snapshot.system_name,
                snapshot.device_type, snapshot.ip, snapshot.ssid,
                snapshot.ap_name, snapshot.ap_mac, snapshot.radio_id,
                snapshot.channel, snapshot.rssi, snapshot.snr,
                snapshot.traffic_down, snapshot.traffic_up,
                snapshot.uptime, snapshot.controller_last_seen_ms,
                _db_bool(snapshot.active), snapshot.auth_status,
                snapshot.auth_context_json, snapshot.client_json,
                snapshot.raw_controller_snapshot_json,
                record.source_identity, record.source_path,
                record.source_offset_start, record.source_offset_end,
                record.processing_now,
            ),
        )
        self._recompute_device(
            connection,
            snapshot.device_id,
            record.processing_now,
        )
        return existing is None

    def _recompute_device(
        self,
        connection: sqlite3.Connection,
        device_id: str,
        processing_now: str,
    ) -> None:
        current = connection.execute(
            """
            SELECT *
            FROM device_snapshots
            WHERE device_id = ?
            ORDER BY authorized_at DESC,
                     captured_at DESC,
                     snapshot_id DESC
            LIMIT 1
            """,
            (device_id,),
        ).fetchone()
        bounds = connection.execute(
            """
            SELECT
                MIN(authorized_at),
                MAX(authorized_at),
                COUNT(*)
            FROM device_snapshots
            WHERE device_id = ?
            """,
            (device_id,),
        ).fetchone()
        if current is None or bounds is None:
            raise RegistrySchemaError(
                "Snapshot insert did not produce a device history"
            )
        profile: dict[str, str | None] = {}
        for column in _PROFILE_COLUMNS:
            row = connection.execute(
                f"""
                SELECT {column}
                FROM device_snapshots
                WHERE device_id = ?
                  AND {column} IS NOT NULL
                  AND TRIM({column}) != ''
                ORDER BY authorized_at DESC,
                         captured_at DESC,
                         snapshot_id DESC
                LIMIT 1
                """,
                (device_id,),
            ).fetchone()
            profile[column] = None if row is None else row[0]

        connection.execute(
            """
            UPDATE visitor_devices
            SET first_seen_at = ?,
                last_seen_at = ?,
                current_authorized_at = ?,
                current_captured_at = ?,
                current_snapshot_id = ?,
                last_auth_session_id = ?,
                last_site_id = ?,
                last_known_controller_client_id = ?,
                last_known_name = ?,
                last_known_hostname = ?,
                last_known_system_name = ?,
                last_known_device_type = ?,
                last_ip = ?,
                last_ssid = ?,
                last_ap_name = ?,
                last_ap_mac = ?,
                last_radio_id = ?,
                last_channel = ?,
                last_rssi = ?,
                last_snr = ?,
                last_active = ?,
                last_auth_status = ?,
                snapshot_count = ?,
                updated_at = ?
            WHERE device_id = ?
            """,
            (
                bounds[0], bounds[1],
                current["authorized_at"], current["captured_at"],
                current["snapshot_id"], current["auth_session_id"],
                current["site_id"],
                profile["controller_client_id"], profile["name"],
                profile["hostname"], profile["system_name"],
                profile["device_type"],
                current["ip"], current["ssid"], current["ap_name"],
                current["ap_mac"], current["radio_id"],
                current["channel"], current["rssi"], current["snr"],
                current["active"], current["auth_status"],
                int(bounds[2]), processing_now, device_id,
            ),
        )

    @staticmethod
    def _insert_processed(
        connection: sqlite3.Connection,
        record: SourceLineRecord,
        *,
        snapshot_id: str,
        event_sha256: str,
        processing_result: str,
        skip_reason: str | None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO processed_snapshot_events (
                snapshot_id, event_sha256,
                processing_result, skip_reason,
                source_identity, source_path,
                source_offset_start, source_offset_end,
                processed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id, event_sha256,
                processing_result, skip_reason,
                record.source_identity, record.source_path,
                record.source_offset_start, record.source_offset_end,
                record.processing_now,
            ),
        )

    @staticmethod
    def _upsert_reader_state(
        connection: sqlite3.Connection,
        record: SourceLineRecord,
        *,
        retired_completed: bool,
        missing_warning_emitted: bool,
    ) -> None:
        connection.execute(
            """
            INSERT INTO reader_state (
                source_identity, source_path, source_offset,
                last_observed_size, source_checkpoint,
                retired_completed, missing_warning_emitted,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_identity) DO UPDATE SET
                source_path = excluded.source_path,
                source_offset = excluded.source_offset,
                last_observed_size = excluded.last_observed_size,
                source_checkpoint = excluded.source_checkpoint,
                retired_completed = excluded.retired_completed,
                missing_warning_emitted = excluded.missing_warning_emitted,
                updated_at = excluded.updated_at
            """,
            (
                record.source_identity, record.source_path,
                record.source_offset_end, record.last_observed_size,
                record.source_checkpoint,
                int(retired_completed), int(missing_warning_emitted),
                record.processing_now,
            ),
        )

    def observe_source(
        self,
        *,
        source_identity: str,
        source_path: str,
        source_offset: int,
        last_observed_size: int,
        source_checkpoint: str,
        retired_completed: bool,
        missing_warning_emitted: bool,
        now_utc: str,
    ) -> None:
        record = SourceLineRecord(
            source_identity=source_identity,
            source_path=source_path,
            source_offset_start=max(0, source_offset - 1),
            source_offset_end=source_offset,
            last_observed_size=last_observed_size,
            source_checkpoint=source_checkpoint,
            processing_now=now_utc,
        )
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO reader_state (
                    source_identity, source_path, source_offset,
                    last_observed_size, source_checkpoint,
                    retired_completed, missing_warning_emitted,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_identity) DO UPDATE SET
                    source_path = excluded.source_path,
                    source_offset = excluded.source_offset,
                    last_observed_size = excluded.last_observed_size,
                    source_checkpoint = excluded.source_checkpoint,
                    retired_completed = excluded.retired_completed,
                    missing_warning_emitted = excluded.missing_warning_emitted,
                    updated_at = excluded.updated_at
                """,
                (
                    record.source_identity, record.source_path,
                    source_offset, record.last_observed_size,
                    record.source_checkpoint, int(retired_completed),
                    int(missing_warning_emitted), now_utc,
                ),
            )
            connection.commit()

    def reset_source(
        self,
        *,
        source_identity: str,
        source_path: str,
        observed_size: int,
        checkpoint_at_zero: str,
        now_utc: str,
    ) -> None:
        self.observe_source(
            source_identity=source_identity,
            source_path=source_path,
            source_offset=0,
            last_observed_size=observed_size,
            source_checkpoint=checkpoint_at_zero,
            retired_completed=False,
            missing_warning_emitted=False,
            now_utc=now_utc,
        )

    def get_reader_states(self) -> dict[str, ReaderState]:
        if not self.db_path.exists():
            return {}
        with closing(self._connect(readonly=True)) as connection:
            rows = connection.execute(
                """
                SELECT
                    source_identity, source_path, source_offset,
                    last_observed_size, source_checkpoint,
                    retired_completed, missing_warning_emitted
                FROM reader_state
                """
            ).fetchall()
        return {
            row["source_identity"]: ReaderState(
                source_identity=row["source_identity"],
                source_path=row["source_path"],
                source_offset=int(row["source_offset"]),
                last_observed_size=(
                    None
                    if row["last_observed_size"] is None
                    else int(row["last_observed_size"])
                ),
                source_checkpoint=row["source_checkpoint"],
                retired_completed=bool(row["retired_completed"]),
                missing_warning_emitted=bool(
                    row["missing_warning_emitted"]
                ),
            )
            for row in rows
        }

    def delete_reader_state(self, source_identity: str) -> None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM reader_state WHERE source_identity = ?",
                (source_identity,),
            )
            connection.commit()

    def mark_missing_warning(
        self,
        source_identity: str,
        now_utc: str,
    ) -> None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE reader_state
                SET missing_warning_emitted = 1,
                    updated_at = ?
                WHERE source_identity = ?
                """,
                (now_utc, source_identity),
            )
            connection.commit()

    def set_state(
        self,
        state: str,
        reason: str | None,
        now_utc: str,
    ) -> bool:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            previous = connection.execute(
                """
                SELECT state, state_reason
                FROM registry_state
                WHERE singleton_id = 1
                """
            ).fetchone()
            changed = (
                previous is None
                or previous["state"] != state
                or previous["state_reason"] != reason
            )
            if changed:
                connection.execute(
                    """
                    UPDATE registry_state
                    SET state = ?,
                        state_reason = ?,
                        state_changed_at = ?,
                        updated_at = ?
                    WHERE singleton_id = 1
                    """,
                    (state, reason, now_utc, now_utc),
                )
            connection.commit()
            return changed

    def initial_backfill_completed(self) -> bool:
        with closing(self._connect(readonly=True)) as connection:
            row = connection.execute(
                """
                SELECT initial_backfill_completed
                FROM registry_state
                WHERE singleton_id = 1
                """
            ).fetchone()
        return bool(row and row[0] == 1)

    def mark_backfill_completed(self, now_utc: str) -> None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE registry_state
                SET initial_backfill_completed = 1,
                    initial_backfill_completed_at = ?,
                    updated_at = ?
                WHERE singleton_id = 1
                  AND initial_backfill_completed = 0
                """,
                (now_utc, now_utc),
            )
            connection.commit()

    def mark_successful_scan(self, now_utc: str) -> None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE registry_state
                SET last_successful_scan_at = ?,
                    updated_at = ?
                WHERE singleton_id = 1
                """,
                (now_utc, now_utc),
            )
            connection.commit()

    def get_status(self, configured_enabled: bool) -> RegistryStatus:
        database_exists = bool(
            self.config.db_path.strip()
        ) and registry_database_exists(self.db_path)
        if not database_exists:
            return RegistryStatus(
                configured_enabled=configured_enabled,
                database_exists=False,
                database_ready=False,
                schema_version=None,
                registry_state=(
                    "initializing" if configured_enabled else "disabled"
                ),
                state_reason="database_absent",
                initial_backfill_completed=False,
                initial_backfill_completed_at=None,
                last_successful_scan_at=None,
                last_snapshot_stored_at=None,
                reader_states=(),
            )
        with closing(self._connect(readonly=True)) as connection:
            version = int(
                connection.execute("PRAGMA user_version").fetchone()[0]
            )
            row = connection.execute(
                "SELECT * FROM registry_state WHERE singleton_id = 1"
            ).fetchone()
            reader_rows = connection.execute(
                """
                SELECT *
                FROM reader_state
                ORDER BY source_path, source_identity
                """
            ).fetchall()
        if row is None:
            raise RegistrySchemaError("Registry state row is missing")
        return RegistryStatus(
            configured_enabled=configured_enabled,
            database_exists=True,
            database_ready=version == SCHEMA_VERSION,
            schema_version=version,
            registry_state=row["state"],
            state_reason=row["state_reason"],
            initial_backfill_completed=bool(
                row["initial_backfill_completed"]
            ),
            initial_backfill_completed_at=(
                row["initial_backfill_completed_at"]
            ),
            last_successful_scan_at=row["last_successful_scan_at"],
            last_snapshot_stored_at=row["last_snapshot_stored_at"],
            reader_states=tuple(
                _reader_state_row(item) for item in reader_rows
            ),
        )

    def get_stats(
        self,
        day_start_utc: str,
        next_day_start_utc: str,
    ) -> dict[str, int]:
        with closing(self._connect(readonly=True)) as connection:
            row = connection.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM visitor_devices),
                    (SELECT COUNT(*) FROM device_snapshots),
                    (
                        SELECT COUNT(*)
                        FROM visitor_devices
                        WHERE first_seen_at >= ?
                          AND first_seen_at < ?
                    ),
                    (
                        SELECT COUNT(DISTINCT device_id)
                        FROM device_snapshots
                        WHERE authorized_at >= ?
                          AND authorized_at < ?
                    ),
                    (
                        SELECT COUNT(*)
                        FROM device_snapshots
                        WHERE authorized_at >= ?
                          AND authorized_at < ?
                    )
                """,
                (
                    day_start_utc, next_day_start_utc,
                    day_start_utc, next_day_start_utc,
                    day_start_utc, next_day_start_utc,
                ),
            ).fetchone()
        return {
            "total_devices": int(row[0]),
            "total_snapshots": int(row[1]),
            "new_devices": int(row[2]),
            "authorized_devices": int(row[3]),
            "snapshots": int(row[4]),
        }

    def get_device_by_id(self, device_id: str) -> dict[str, Any] | None:
        return self._one_device("device_id = ?", (device_id,))

    def get_device_by_mac(self, mac: str) -> dict[str, Any] | None:
        return self._one_device("mac = ?", (mac,))

    def _one_device(
        self,
        where: str,
        params: tuple[Any, ...],
    ) -> dict[str, Any] | None:
        with closing(self._connect(readonly=True)) as connection:
            row = connection.execute(
                f"SELECT * FROM visitor_devices WHERE {where}",
                params,
            ).fetchone()
        return None if row is None else _device_row(row)

    def list_devices(
        self,
        *,
        filters: dict[str, Any],
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        columns = {
            "mac": ("mac = ?", False),
            "hostname": (
                "last_known_hostname COLLATE NOCASE "
                "LIKE ? ESCAPE '\\'",
                True,
            ),
            "ip": ("last_ip = ?", False),
            "ssid": ("last_ssid = ?", False),
            "ap_mac": ("last_ap_mac = ?", False),
            "device_type": (
                "last_known_device_type = ? COLLATE NOCASE",
                False,
            ),
            "controller_client_id": (
                "last_known_controller_client_id = ?",
                False,
            ),
            "seen_from": ("last_seen_at >= ?", False),
            "seen_to": ("last_seen_at <= ?", False),
        }
        for key, value in filters.items():
            if value is None or key not in columns:
                continue
            clause, contains = columns[key]
            clauses.append(clause)
            params.append(
                _like_contains(str(value)) if contains else value
            )
        where = (
            " WHERE " + " AND ".join(clauses)
            if clauses
            else ""
        )
        params.extend((limit, offset))
        with closing(self._connect(readonly=True)) as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM visitor_devices
                {where}
                ORDER BY last_seen_at DESC, device_id ASC
                LIMIT ? OFFSET ?
                """,
                tuple(params),
            ).fetchall()
        return [_device_row(row) for row in rows]

    def list_device_snapshots(
        self,
        device_id: str,
        *,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        # Raw JSON is deliberately omitted from all administrative reads.
        with closing(self._connect(readonly=True)) as connection:
            rows = connection.execute(
                """
                SELECT
                    snapshot_id, device_id, schema_version,
                    auth_session_id, site_id, requested_mac,
                    authorized_at, captured_at,
                    attempts, queue_delay_ms, request_duration_ms,
                    snapshot_lag_ms, auth_final_reason,
                    auth_run_number, authorization_attempt,
                    retry_request_id, portal_client_ip, portal_ssid,
                    portal_ap_mac, portal_radio_id,
                    controller_client_id, name, hostname,
                    system_name, device_type,
                    ip, ssid, ap_name, ap_mac,
                    radio_id, channel, rssi, snr,
                    traffic_down, traffic_up, uptime,
                    controller_last_seen_ms, active, auth_status,
                    source_identity, source_path,
                    source_offset_start, source_offset_end,
                    processed_at
                FROM device_snapshots
                WHERE device_id = ?
                ORDER BY authorized_at DESC,
                         captured_at DESC,
                         snapshot_id DESC
                LIMIT ? OFFSET ?
                """,
                (device_id, limit, offset),
            ).fetchall()
        return [_snapshot_row(row) for row in rows]

    def _connect(self, *, readonly: bool = False) -> sqlite3.Connection:
        validate_registry_database_target(self.db_path)
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
        connection.execute(
            f"PRAGMA busy_timeout={self.busy_timeout_ms}"
        )
        connection.execute("PRAGMA foreign_keys=ON")
        if readonly:
            connection.execute("PRAGMA query_only=ON")
        else:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
        return connection


def _db_bool(value: bool | None) -> int | None:
    return None if value is None else int(value)


def _normalize_schema_sql(value: str) -> str:
    return " ".join(value.lower().split())


def _like_contains(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
    return f"%{escaped}%"


def _device_row(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    if result.get("last_active") is not None:
        result["last_active"] = bool(result["last_active"])
    return result


def _snapshot_row(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    if result.get("active") is not None:
        result["active"] = bool(result["active"])
    return result


def _reader_state_row(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["retired_completed"] = bool(result["retired_completed"])
    result["missing_warning_emitted"] = bool(
        result["missing_warning_emitted"]
    )
    return result
