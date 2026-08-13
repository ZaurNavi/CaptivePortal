"""SQLite repository for Observation Storage Foundation schema v1."""

from __future__ import annotations

import math
import os
import sqlite3
import stat
import threading
import uuid
import hashlib
import json
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Mapping, Sequence

from .models import (
    InitializationResult,
    ObservationConfig,
    ObservationCycle,
    ObservationSchemaError,
    ObservationStorageError,
    ObservationValidationError,
    SCHEMA_VERSION,
    StorageFailureCategory,
    require_mac,
    require_nonnegative_int_or_none,
    require_text,
    require_utc,
    utc_now,
)


BUSY_TIMEOUT_MS = 500
ALLOWED_AUTO_CREATE_ROOT = Path("/opt/CaptivePortal/data")

# Stable primary result codes from the SQLite C API. Python's sqlite3 module
# exposes symbolic result-code constants starting with 3.11, while the
# application supports Python 3.10.
_SQLITE_BUSY = 5
_SQLITE_LOCKED = 6
_SQLITE_READONLY = 8
_SQLITE_IOERR = 10
_SQLITE_CORRUPT = 11
_SQLITE_FULL = 13
_SQLITE_CANTOPEN = 14
_SQLITE_CONSTRAINT = 19
_SQLITE_NOTADB = 26

CYCLE_KINDS = frozenset({"client", "ap_dynamic", "ap_config"})
CYCLE_STATES = frozenset({"running", "completed", "abandoned"})
CYCLE_RESULTS = frozenset({"success", "partial", "failed", "shutdown"})
RATE_REASONS = frozenset({
    "ok",
    "no_baseline",
    "counter_reset",
    "gap_too_large",
    "invalid_elapsed",
    "source_unavailable",
})

REQUIRED_TABLES = frozenset({
    "observation_cycles",
    "client_observations",
    "ap_observations",
    "ap_radio_observations",
    "ap_config_snapshots",
})
REQUIRED_INDEXES: Mapping[str, tuple[str, ...]] = {
    "idx_client_site_mac_time": (
        "site_id", "client_mac", "observed_at", "row_id",
    ),
    "idx_client_site_time": ("site_id", "observed_at", "row_id"),
    "idx_client_site_ap_time": (
        "site_id", "ap_mac", "observed_at", "row_id",
    ),
    "idx_client_site_ssid_time": (
        "site_id", "ssid", "observed_at", "row_id",
    ),
    "idx_client_site_radio_time": (
        "site_id", "radio_id", "observed_at", "row_id",
    ),
    "idx_ap_site_mac_time": (
        "site_id", "ap_mac", "observed_at", "row_id",
    ),
    "idx_ap_site_time": ("site_id", "observed_at", "row_id"),
    "idx_radio_site_ap_band_time": (
        "site_id", "ap_mac", "band", "radio_observed_at", "row_id",
    ),
    "idx_config_site_ap_time": (
        "site_id", "ap_mac", "captured_at", "row_id",
    ),
    "idx_cycles_site_kind_started": ("site_id", "kind", "started_at"),
    "idx_cycles_state_started": ("state", "started_at"),
}
REQUIRED_TRIGGERS = frozenset({
    "trg_client_cycle_site",
    "trg_ap_cycle_site",
    "trg_radio_parent_identity",
    "trg_config_cycle_site",
})
REQUIRED_COLUMNS: Mapping[str, frozenset[str]] = {
    "observation_cycles": frozenset({
        "cycle_id", "kind", "site_id", "state", "started_at",
        "finished_at", "abandoned_at", "complete", "result",
        "source_rows_reported", "items_seen", "items_stored",
        "items_skipped", "error_count", "data_quality_warning_count",
        "created_at", "updated_at",
    }),
    "client_observations": frozenset({
        "row_id", "cycle_id", "observed_at", "site_id", "client_mac",
        "source_inventory_complete", "ssid", "ap_mac", "radio_id",
    }),
    "ap_observations": frozenset({
        "row_id", "cycle_id", "observed_at", "site_id", "ap_mac",
        "partial", "overview_ok", "wired_uplink_ok", "lan_traffic_ok",
        "radios_ok", "overview_observed_at", "wired_observed_at",
        "lan_observed_at",
    }),
    "ap_radio_observations": frozenset({
        "row_id", "cycle_id", "ap_observation_row_id",
        "radio_observed_at", "site_id", "ap_mac", "band",
    }),
    "ap_config_snapshots": frozenset({
        "row_id", "cycle_id", "captured_at", "site_id", "ap_mac",
        "config_sha256", "schema_version", "config_json",
    }),
}
REQUIRED_UNIQUE_KEYS: Mapping[str, tuple[tuple[str, ...], ...]] = {
    "client_observations": (("cycle_id", "client_mac"),),
    "ap_observations": (("cycle_id", "ap_mac"),),
    "ap_radio_observations": (("ap_observation_row_id", "band"),),
    "ap_config_snapshots": (
        ("cycle_id", "ap_mac"),
        ("site_id", "ap_mac", "config_sha256"),
    ),
}

_CLIENT_REQUIRED = (
    "cycle_id",
    "observed_at",
    "site_id",
    "client_mac",
    "source_inventory_complete",
)
_CLIENT_OPTIONAL = (
    "controller_client_id", "name", "hostname", "system_name",
    "device_type", "connect_device_type", "ip", "ipv6_list_json",
    "ssid", "ap_name", "ap_mac", "connect_type", "signal_level",
    "signal_rank", "wifi_mode", "radio_id", "band", "channel",
    "rx_rate", "tx_rate", "rssi", "snr", "vid", "uptime",
    "last_seen_ms", "auth_status", "activity", "wireless",
    "power_save", "blocked", "guest", "active", "manager",
    "traffic_down", "traffic_up", "down_packet", "up_packet",
)
_CLIENT_COLUMNS = _CLIENT_REQUIRED + _CLIENT_OPTIONAL

_AP_REQUIRED = (
    "cycle_id", "observed_at", "site_id", "ap_mac", "partial",
    "overview_ok", "wired_uplink_ok", "lan_traffic_ok", "radios_ok",
)
_AP_OPTIONAL = (
    "overview_observed_at", "wired_observed_at", "lan_observed_at",
    "name", "ip", "model", "firmware_version", "wlan_id",
    "cpu_util", "mem_util", "uptime_seconds", "wired_rate_raw",
    "wired_duplex_code", "wired_up_bytes", "wired_down_bytes",
    "wired_up_packets", "wired_down_packets", "wired_activity_raw",
    "wired_download_mbps", "wired_upload_mbps",
    "wired_download_rate_reason", "wired_upload_rate_reason",
    "lan_rx_bytes", "lan_tx_bytes", "lan_rx_packets", "lan_tx_packets",
    "lan_rx_drop_packets", "lan_tx_drop_packets",
    "lan_rx_error_packets", "lan_tx_error_packets",
    "lan_rx_mbps", "lan_tx_mbps", "lan_rx_rate_reason",
    "lan_tx_rate_reason",
)
_AP_COLUMNS = _AP_REQUIRED + _AP_OPTIONAL

_RADIO_REQUIRED = ("radio_observed_at", "band")
_RADIO_OPTIONAL = (
    "radio_id", "actual_channel_raw", "actual_channel",
    "frequency_mhz", "channel_width", "max_tx_rate", "tx_power",
    "wireless_mode", "tx_util", "rx_util", "interference_util",
    "busy_util", "rx_bytes", "tx_bytes", "rx_packets", "tx_packets",
    "rx_drop_packets", "tx_drop_packets", "rx_error_packets",
    "tx_error_packets", "rx_retry_packets", "tx_retry_packets",
    "radio_rx_mbps", "radio_tx_mbps", "radio_rx_rate_reason",
    "radio_tx_rate_reason",
)
_RADIO_COLUMNS = (
    "cycle_id", "ap_observation_row_id", "radio_observed_at",
    "site_id", "ap_mac", "band",
) + _RADIO_OPTIONAL

_CONFIG_COLUMNS = (
    "cycle_id", "captured_at", "site_id", "ap_mac", "config_sha256",
    "schema_version", "config_json",
)

_BOOL_COLUMNS = frozenset({
    "source_inventory_complete", "partial", "overview_ok",
    "wired_uplink_ok", "lan_traffic_ok", "radios_ok", "wireless",
    "power_save", "blocked", "guest", "active", "manager",
})
_MAC_COLUMNS = frozenset({"client_mac", "ap_mac"})
_TIMESTAMP_COLUMNS = frozenset({
    "observed_at", "overview_observed_at", "wired_observed_at",
    "lan_observed_at", "radio_observed_at", "captured_at",
})
_REAL_COLUMNS = frozenset({
    "cpu_util", "mem_util", "wired_rate_raw", "wired_activity_raw",
    "wired_download_mbps", "wired_upload_mbps", "lan_rx_mbps",
    "lan_tx_mbps", "max_tx_rate", "tx_power", "tx_util", "rx_util",
    "interference_util", "busy_util", "radio_rx_mbps",
    "radio_tx_mbps",
})
_INTEGER_COLUMNS = frozenset({
    "signal_level", "signal_rank", "radio_id", "channel", "rx_rate",
    "tx_rate", "rssi", "snr", "vid", "uptime", "last_seen_ms",
    "auth_status", "activity", "traffic_down", "traffic_up",
    "down_packet", "up_packet", "wlan_id", "uptime_seconds",
    "wired_up_bytes", "wired_down_bytes",
    "wired_up_packets", "wired_down_packets", "lan_rx_bytes",
    "lan_tx_bytes", "lan_rx_packets", "lan_tx_packets",
    "lan_rx_drop_packets", "lan_tx_drop_packets", "lan_rx_error_packets",
    "lan_tx_error_packets", "actual_channel", "frequency_mhz",
    "rx_bytes", "tx_bytes", "rx_packets", "tx_packets",
    "rx_drop_packets", "tx_drop_packets", "rx_error_packets",
    "tx_error_packets", "rx_retry_packets", "tx_retry_packets",
    "schema_version",
})
_NONNEGATIVE_COLUMNS = _INTEGER_COLUMNS - frozenset({
    "signal_level", "signal_rank", "rssi", "snr",
})
_RATE_REASON_COLUMNS = frozenset({
    "wired_download_rate_reason", "wired_upload_rate_reason",
    "lan_rx_rate_reason", "lan_tx_rate_reason", "radio_rx_rate_reason",
    "radio_tx_rate_reason",
})


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

        CREATE TABLE observation_cycles (
            cycle_id TEXT PRIMARY KEY,
            kind TEXT NOT NULL CHECK (kind IN ('client', 'ap_dynamic', 'ap_config')),
            site_id TEXT NOT NULL CHECK (length(trim(site_id)) > 0),
            state TEXT NOT NULL CHECK (state IN ('running', 'completed', 'abandoned')),
            started_at TEXT NOT NULL CHECK {_utc_check('started_at')},
            finished_at TEXT CHECK {_utc_check('finished_at', nullable=True)},
            abandoned_at TEXT CHECK {_utc_check('abandoned_at', nullable=True)},
            complete INTEGER CHECK (complete IS NULL OR complete IN (0, 1)),
            result TEXT CHECK (result IS NULL OR result IN ('success', 'partial', 'failed', 'shutdown')),
            source_rows_reported INTEGER CHECK (source_rows_reported IS NULL OR source_rows_reported >= 0),
            items_seen INTEGER NOT NULL DEFAULT 0 CHECK (items_seen >= 0),
            items_stored INTEGER NOT NULL DEFAULT 0 CHECK (items_stored >= 0),
            items_skipped INTEGER NOT NULL DEFAULT 0 CHECK (items_skipped >= 0),
            error_count INTEGER NOT NULL DEFAULT 0 CHECK (error_count >= 0),
            data_quality_warning_count INTEGER NOT NULL DEFAULT 0 CHECK (data_quality_warning_count >= 0),
            created_at TEXT NOT NULL CHECK {_utc_check('created_at')},
            updated_at TEXT NOT NULL CHECK {_utc_check('updated_at')},
            CHECK (
                (state = 'running' AND finished_at IS NULL AND abandoned_at IS NULL AND complete IS NULL AND result IS NULL)
                OR (state = 'completed' AND finished_at IS NOT NULL AND abandoned_at IS NULL AND complete IN (0, 1) AND result IS NOT NULL)
                OR (state = 'abandoned' AND finished_at IS NULL AND abandoned_at IS NOT NULL AND complete = 0 AND result IS NULL)
            )
        );

        CREATE TABLE client_observations (
            row_id INTEGER PRIMARY KEY,
            cycle_id TEXT NOT NULL,
            observed_at TEXT NOT NULL CHECK {_utc_check('observed_at')},
            site_id TEXT NOT NULL CHECK (length(trim(site_id)) > 0),
            client_mac TEXT NOT NULL,
            source_inventory_complete INTEGER NOT NULL CHECK (source_inventory_complete IN (0, 1)),
            controller_client_id TEXT,
            name TEXT,
            hostname TEXT,
            system_name TEXT,
            device_type TEXT,
            connect_device_type TEXT,
            ip TEXT,
            ipv6_list_json TEXT,
            ssid TEXT,
            ap_name TEXT,
            ap_mac TEXT,
            connect_type TEXT,
            signal_level INTEGER,
            signal_rank INTEGER,
            wifi_mode TEXT,
            radio_id INTEGER,
            band TEXT,
            channel INTEGER,
            rx_rate INTEGER,
            tx_rate INTEGER,
            rssi INTEGER,
            snr INTEGER,
            vid INTEGER,
            uptime INTEGER,
            last_seen_ms INTEGER,
            auth_status INTEGER,
            activity INTEGER,
            wireless INTEGER CHECK (wireless IS NULL OR wireless IN (0, 1)),
            power_save INTEGER CHECK (power_save IS NULL OR power_save IN (0, 1)),
            blocked INTEGER CHECK (blocked IS NULL OR blocked IN (0, 1)),
            guest INTEGER CHECK (guest IS NULL OR guest IN (0, 1)),
            active INTEGER CHECK (active IS NULL OR active IN (0, 1)),
            manager INTEGER CHECK (manager IS NULL OR manager IN (0, 1)),
            traffic_down INTEGER CHECK (traffic_down IS NULL OR traffic_down >= 0),
            traffic_up INTEGER CHECK (traffic_up IS NULL OR traffic_up >= 0),
            down_packet INTEGER CHECK (down_packet IS NULL OR down_packet >= 0),
            up_packet INTEGER CHECK (up_packet IS NULL OR up_packet >= 0),
            UNIQUE (cycle_id, client_mac),
            FOREIGN KEY (cycle_id) REFERENCES observation_cycles(cycle_id) ON DELETE CASCADE
        );

        CREATE TABLE ap_observations (
            row_id INTEGER PRIMARY KEY,
            cycle_id TEXT NOT NULL,
            observed_at TEXT NOT NULL CHECK {_utc_check('observed_at')},
            site_id TEXT NOT NULL CHECK (length(trim(site_id)) > 0),
            ap_mac TEXT NOT NULL,
            partial INTEGER NOT NULL CHECK (partial IN (0, 1)),
            overview_ok INTEGER NOT NULL CHECK (overview_ok IN (0, 1)),
            wired_uplink_ok INTEGER NOT NULL CHECK (wired_uplink_ok IN (0, 1)),
            lan_traffic_ok INTEGER NOT NULL CHECK (lan_traffic_ok IN (0, 1)),
            radios_ok INTEGER NOT NULL CHECK (radios_ok IN (0, 1)),
            overview_observed_at TEXT CHECK {_utc_check('overview_observed_at', nullable=True)},
            wired_observed_at TEXT CHECK {_utc_check('wired_observed_at', nullable=True)},
            lan_observed_at TEXT CHECK {_utc_check('lan_observed_at', nullable=True)},
            name TEXT,
            ip TEXT,
            model TEXT,
            firmware_version TEXT,
            wlan_id INTEGER,
            cpu_util REAL,
            mem_util REAL,
            uptime_seconds INTEGER,
            wired_rate_raw REAL,
            wired_duplex_code TEXT,
            wired_up_bytes INTEGER,
            wired_down_bytes INTEGER,
            wired_up_packets INTEGER,
            wired_down_packets INTEGER,
            wired_activity_raw REAL,
            wired_download_mbps REAL,
            wired_upload_mbps REAL,
            wired_download_rate_reason TEXT CHECK (wired_download_rate_reason IS NULL OR wired_download_rate_reason IN ('ok', 'no_baseline', 'counter_reset', 'gap_too_large', 'invalid_elapsed', 'source_unavailable')),
            wired_upload_rate_reason TEXT CHECK (wired_upload_rate_reason IS NULL OR wired_upload_rate_reason IN ('ok', 'no_baseline', 'counter_reset', 'gap_too_large', 'invalid_elapsed', 'source_unavailable')),
            lan_rx_bytes INTEGER,
            lan_tx_bytes INTEGER,
            lan_rx_packets INTEGER,
            lan_tx_packets INTEGER,
            lan_rx_drop_packets INTEGER,
            lan_tx_drop_packets INTEGER,
            lan_rx_error_packets INTEGER,
            lan_tx_error_packets INTEGER,
            lan_rx_mbps REAL,
            lan_tx_mbps REAL,
            lan_rx_rate_reason TEXT CHECK (lan_rx_rate_reason IS NULL OR lan_rx_rate_reason IN ('ok', 'no_baseline', 'counter_reset', 'gap_too_large', 'invalid_elapsed', 'source_unavailable')),
            lan_tx_rate_reason TEXT CHECK (lan_tx_rate_reason IS NULL OR lan_tx_rate_reason IN ('ok', 'no_baseline', 'counter_reset', 'gap_too_large', 'invalid_elapsed', 'source_unavailable')),
            UNIQUE (cycle_id, ap_mac),
            FOREIGN KEY (cycle_id) REFERENCES observation_cycles(cycle_id) ON DELETE CASCADE
        );

        CREATE TABLE ap_radio_observations (
            row_id INTEGER PRIMARY KEY,
            cycle_id TEXT NOT NULL,
            ap_observation_row_id INTEGER NOT NULL,
            radio_observed_at TEXT NOT NULL CHECK {_utc_check('radio_observed_at')},
            site_id TEXT NOT NULL CHECK (length(trim(site_id)) > 0),
            ap_mac TEXT NOT NULL,
            band TEXT NOT NULL CHECK (length(trim(band)) > 0),
            radio_id INTEGER,
            actual_channel_raw TEXT,
            actual_channel INTEGER,
            frequency_mhz INTEGER,
            channel_width TEXT,
            max_tx_rate REAL,
            tx_power REAL,
            wireless_mode TEXT,
            tx_util REAL,
            rx_util REAL,
            interference_util REAL,
            busy_util REAL,
            rx_bytes INTEGER,
            tx_bytes INTEGER,
            rx_packets INTEGER,
            tx_packets INTEGER,
            rx_drop_packets INTEGER,
            tx_drop_packets INTEGER,
            rx_error_packets INTEGER,
            tx_error_packets INTEGER,
            rx_retry_packets INTEGER,
            tx_retry_packets INTEGER,
            radio_rx_mbps REAL,
            radio_tx_mbps REAL,
            radio_rx_rate_reason TEXT CHECK (radio_rx_rate_reason IS NULL OR radio_rx_rate_reason IN ('ok', 'no_baseline', 'counter_reset', 'gap_too_large', 'invalid_elapsed', 'source_unavailable')),
            radio_tx_rate_reason TEXT CHECK (radio_tx_rate_reason IS NULL OR radio_tx_rate_reason IN ('ok', 'no_baseline', 'counter_reset', 'gap_too_large', 'invalid_elapsed', 'source_unavailable')),
            UNIQUE (ap_observation_row_id, band),
            FOREIGN KEY (cycle_id) REFERENCES observation_cycles(cycle_id) ON DELETE CASCADE,
            FOREIGN KEY (ap_observation_row_id) REFERENCES ap_observations(row_id) ON DELETE CASCADE
        );

        CREATE TABLE ap_config_snapshots (
            row_id INTEGER PRIMARY KEY,
            cycle_id TEXT NOT NULL,
            captured_at TEXT NOT NULL CHECK {_utc_check('captured_at')},
            site_id TEXT NOT NULL CHECK (length(trim(site_id)) > 0),
            ap_mac TEXT NOT NULL,
            config_sha256 TEXT NOT NULL CHECK (length(config_sha256) = 64),
            schema_version INTEGER NOT NULL CHECK (schema_version > 0),
            config_json TEXT NOT NULL CHECK (length(config_json) > 0),
            UNIQUE (cycle_id, ap_mac),
            UNIQUE (site_id, ap_mac, config_sha256),
            FOREIGN KEY (cycle_id) REFERENCES observation_cycles(cycle_id) ON DELETE CASCADE
        );

        CREATE TRIGGER trg_client_cycle_site
        BEFORE INSERT ON client_observations
        WHEN NOT EXISTS (
            SELECT 1 FROM observation_cycles
            WHERE cycle_id = NEW.cycle_id
              AND site_id = NEW.site_id
              AND kind = 'client'
        )
        BEGIN SELECT RAISE(ABORT, 'client cycle identity mismatch'); END;

        CREATE TRIGGER trg_ap_cycle_site
        BEFORE INSERT ON ap_observations
        WHEN NOT EXISTS (
            SELECT 1 FROM observation_cycles
            WHERE cycle_id = NEW.cycle_id
              AND site_id = NEW.site_id
              AND kind = 'ap_dynamic'
        )
        BEGIN SELECT RAISE(ABORT, 'ap cycle identity mismatch'); END;

        CREATE TRIGGER trg_radio_parent_identity
        BEFORE INSERT ON ap_radio_observations
        WHEN NOT EXISTS (
            SELECT 1 FROM ap_observations
            WHERE row_id = NEW.ap_observation_row_id
              AND cycle_id = NEW.cycle_id
              AND site_id = NEW.site_id
              AND ap_mac = NEW.ap_mac
        )
        BEGIN SELECT RAISE(ABORT, 'radio parent identity mismatch'); END;

        CREATE TRIGGER trg_config_cycle_site
        BEFORE INSERT ON ap_config_snapshots
        WHEN NOT EXISTS (
            SELECT 1 FROM observation_cycles
            WHERE cycle_id = NEW.cycle_id
              AND site_id = NEW.site_id
              AND kind = 'ap_config'
        )
        BEGIN SELECT RAISE(ABORT, 'config cycle identity mismatch'); END;

        CREATE INDEX idx_client_site_mac_time
            ON client_observations(site_id, client_mac, observed_at, row_id);
        CREATE INDEX idx_client_site_time
            ON client_observations(site_id, observed_at, row_id);
        CREATE INDEX idx_client_site_ap_time
            ON client_observations(site_id, ap_mac, observed_at, row_id);
        CREATE INDEX idx_client_site_ssid_time
            ON client_observations(site_id, ssid, observed_at, row_id);
        CREATE INDEX idx_client_site_radio_time
            ON client_observations(site_id, radio_id, observed_at, row_id);
        CREATE INDEX idx_ap_site_mac_time
            ON ap_observations(site_id, ap_mac, observed_at, row_id);
        CREATE INDEX idx_ap_site_time
            ON ap_observations(site_id, observed_at, row_id);
        CREATE INDEX idx_radio_site_ap_band_time
            ON ap_radio_observations(site_id, ap_mac, band, radio_observed_at, row_id);
        CREATE INDEX idx_config_site_ap_time
            ON ap_config_snapshots(site_id, ap_mac, captured_at, row_id);
        CREATE INDEX idx_cycles_site_kind_started
            ON observation_cycles(site_id, kind, started_at);
        CREATE INDEX idx_cycles_state_started
            ON observation_cycles(state, started_at);

        PRAGMA user_version = 1;
        COMMIT;
    """


class ObservationRepository:
    """Own schema v1 and short serialized write transactions."""

    def __init__(
        self,
        config: ObservationConfig,
        *,
        busy_timeout_ms: int = BUSY_TIMEOUT_MS,
    ):
        self.config = config
        self.db_path = Path(config.db_path)
        self.busy_timeout_ms = max(1, min(int(busy_timeout_ms), 60_000))
        self._write_lock = threading.RLock()

    def initialize(self, now_utc: str | None = None) -> InitializationResult:
        """Create/validate schema and abandon stale running cycles."""
        now = require_utc(now_utc or utc_now(), "now_utc")
        self._ensure_parent()
        existed = self._database_exists()
        created = False
        try:
            with self._write_lock, closing(self._connect()) as connection:
                version = int(
                    connection.execute("PRAGMA user_version").fetchone()[0]
                )
                tables = self._table_names(connection)
                if version > SCHEMA_VERSION:
                    raise ObservationSchemaError(
                        "Observation schema is newer than this code"
                    )
                if version == 0:
                    if tables.intersection(REQUIRED_TABLES):
                        raise ObservationSchemaError(
                            "Observation schema version 0 is partial"
                        )
                    connection.executescript(_schema_sql())
                    created = True
                elif version != SCHEMA_VERSION:
                    raise ObservationSchemaError(
                        f"Unsupported Observation schema version: {version}"
                    )
                self._startup_check(connection)
                if os.name == "posix":
                    os.chmod(self.db_path, 0o640)
                connection.execute("BEGIN IMMEDIATE")
                updated = connection.execute(
                    """
                    UPDATE observation_cycles
                    SET state = 'abandoned',
                        abandoned_at = ?,
                        complete = 0,
                        result = NULL,
                        updated_at = ?
                    WHERE state = 'running'
                    """,
                    (now, now),
                ).rowcount
                connection.commit()
        except ObservationSchemaError:
            raise
        except sqlite3.Error as exc:
            raise _storage_error(exc) from exc
        except OSError as exc:
            raise ObservationStorageError(
                StorageFailureCategory.UNAVAILABLE
            ) from exc
        if not existed and not created:
            raise ObservationSchemaError(
                "Observation database creation did not complete"
            )
        return InitializationResult(
            created=created,
            abandoned_cycles=max(0, int(updated)),
        )

    def validate_runtime_health(self) -> None:
        try:
            with closing(self._connect(readonly=True)) as connection:
                self._startup_check(connection)
        except ObservationSchemaError:
            raise
        except sqlite3.Error as exc:
            raise _storage_error(exc) from exc

    def create_cycle(
        self,
        *,
        kind: str,
        site_id: str,
        started_at: str,
        cycle_id: str | None = None,
    ) -> ObservationCycle:
        if kind not in CYCLE_KINDS:
            raise ObservationValidationError("Unsupported observation cycle kind")
        site = require_text(site_id, "site_id")
        started = require_utc(started_at, "started_at")
        identifier = require_text(
            cycle_id or str(uuid.uuid4()),
            "cycle_id",
        )

        def operation(connection: sqlite3.Connection) -> None:
            connection.execute(
                """
                INSERT INTO observation_cycles (
                    cycle_id, kind, site_id, state, started_at,
                    items_seen, items_stored, items_skipped,
                    error_count, data_quality_warning_count,
                    created_at, updated_at
                ) VALUES (?, ?, ?, 'running', ?, 0, 0, 0, 0, 0, ?, ?)
                """,
                (identifier, kind, site, started, started, started),
            )

        self._write(operation)
        cycle = self.get_cycle(identifier)
        assert cycle is not None
        return cycle

    def finalize_cycle(
        self,
        cycle_id: str,
        *,
        finished_at: str,
        complete: bool,
        result: str,
        source_rows_reported: int | None = None,
        items_seen: int = 0,
        items_stored: int = 0,
        items_skipped: int = 0,
        error_count: int = 0,
        data_quality_warning_count: int = 0,
    ) -> ObservationCycle:
        identifier = require_text(cycle_id, "cycle_id")
        finished = require_utc(finished_at, "finished_at")
        if type(complete) is not bool:
            raise ObservationValidationError("complete must be boolean")
        if result not in CYCLE_RESULTS:
            raise ObservationValidationError("Unsupported cycle result")
        counters = tuple(
            require_nonnegative_int_or_none(value, name)
            for name, value in (
                ("source_rows_reported", source_rows_reported),
                ("items_seen", items_seen),
                ("items_stored", items_stored),
                ("items_skipped", items_skipped),
                ("error_count", error_count),
                (
                    "data_quality_warning_count",
                    data_quality_warning_count,
                ),
            )
        )

        def operation(connection: sqlite3.Connection) -> None:
            updated = connection.execute(
                """
                UPDATE observation_cycles
                SET state = 'completed', finished_at = ?,
                    abandoned_at = NULL, complete = ?, result = ?,
                    source_rows_reported = ?, items_seen = ?,
                    items_stored = ?, items_skipped = ?, error_count = ?,
                    data_quality_warning_count = ?, updated_at = ?
                WHERE cycle_id = ? AND state = 'running'
                """,
                (
                    finished,
                    int(complete),
                    result,
                    *counters,
                    finished,
                    identifier,
                ),
            ).rowcount
            if updated != 1:
                raise ObservationValidationError(
                    "Only a running cycle can be finalized"
                )

        self._write(operation)
        cycle = self.get_cycle(identifier)
        assert cycle is not None
        return cycle

    def get_cycle(self, cycle_id: str) -> ObservationCycle | None:
        identifier = require_text(cycle_id, "cycle_id")
        try:
            with self.read_connection() as connection:
                row = connection.execute(
                    "SELECT * FROM observation_cycles WHERE cycle_id = ?",
                    (identifier,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise _storage_error(exc) from exc
        return None if row is None else _cycle_from_row(row)

    def insert_client_batch(
        self,
        rows: Iterable[Mapping[str, Any]],
    ) -> int:
        prepared = [
            _prepare_row(row, _CLIENT_REQUIRED, _CLIENT_OPTIONAL)
            for row in rows
        ]
        if not prepared:
            return 0

        sql = _insert_ignore_sql("client_observations", _CLIENT_COLUMNS)

        def operation(connection: sqlite3.Connection) -> int:
            inserted = 0
            for row in prepared:
                inserted += max(
                    0,
                    connection.execute(
                        sql,
                        tuple(row.get(column) for column in _CLIENT_COLUMNS),
                    ).rowcount,
                )
            return inserted

        return int(self._write(operation))

    def insert_ap_batch(
        self,
        entries: Iterable[
            tuple[Mapping[str, Any], Iterable[Mapping[str, Any]]]
        ],
    ) -> tuple[int, int]:
        prepared: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
        for ap_row, radio_rows in entries:
            ap = _prepare_row(ap_row, _AP_REQUIRED, _AP_OPTIONAL)
            radios = [
                _prepare_row(row, _RADIO_REQUIRED, _RADIO_OPTIONAL)
                for row in radio_rows
            ]
            prepared.append((ap, radios))
        if not prepared:
            return (0, 0)

        ap_sql = _insert_ignore_sql("ap_observations", _AP_COLUMNS)
        radio_sql = _insert_ignore_sql(
            "ap_radio_observations",
            _RADIO_COLUMNS,
        )

        def operation(connection: sqlite3.Connection) -> tuple[int, int]:
            ap_inserted = 0
            radio_inserted = 0
            for ap, radios in prepared:
                cursor = connection.execute(
                    ap_sql,
                    tuple(ap.get(column) for column in _AP_COLUMNS),
                )
                ap_inserted += max(0, cursor.rowcount)
                ap_row = connection.execute(
                    """
                    SELECT row_id FROM ap_observations
                    WHERE cycle_id = ? AND ap_mac = ?
                    """,
                    (ap["cycle_id"], ap["ap_mac"]),
                ).fetchone()
                if ap_row is None:
                    raise ObservationValidationError(
                        "AP observation could not be resolved"
                    )
                ap_row_id = int(ap_row[0])
                for radio in radios:
                    complete_radio = {
                        **radio,
                        "cycle_id": ap["cycle_id"],
                        "ap_observation_row_id": ap_row_id,
                        "site_id": ap["site_id"],
                        "ap_mac": ap["ap_mac"],
                    }
                    radio_inserted += max(
                        0,
                        connection.execute(
                            radio_sql,
                            tuple(
                                complete_radio.get(column)
                                for column in _RADIO_COLUMNS
                            ),
                        ).rowcount,
                    )
            return ap_inserted, radio_inserted

        return self._write(operation)

    def insert_ap_config_batch(
        self,
        rows: Iterable[Mapping[str, Any]],
    ) -> int:
        prepared = [
            _prepare_row(row, _CONFIG_COLUMNS, ())
            for row in rows
        ]
        if not prepared:
            return 0
        sql = _insert_ignore_sql("ap_config_snapshots", _CONFIG_COLUMNS)

        def operation(connection: sqlite3.Connection) -> int:
            inserted = 0
            for row in prepared:
                inserted += max(
                    0,
                    connection.execute(
                        sql,
                        tuple(row.get(column) for column in _CONFIG_COLUMNS),
                    ).rowcount,
                )
            return inserted

        return int(self._write(operation))

    def get_latest_ap_rate_sample(
        self,
        *,
        site_id: str,
        ap_mac: str,
        timestamp_column: str,
        counter_column: str,
    ) -> tuple[str, int] | None:
        """Return one bounded completed-cycle AP counter baseline."""
        allowed = {
            "wired_observed_at": {"wired_up_bytes", "wired_down_bytes"},
            "lan_observed_at": {"lan_rx_bytes", "lan_tx_bytes"},
        }
        if counter_column not in allowed.get(timestamp_column, set()):
            raise ObservationValidationError("Unsupported AP rate baseline")
        site = require_text(site_id, "site_id")
        mac = require_mac(ap_mac, "ap_mac")
        try:
            with self.read_connection() as connection:
                row = connection.execute(
                    f"""
                    SELECT o.{timestamp_column}, o.{counter_column}
                    FROM ap_observations AS o
                    JOIN observation_cycles AS c ON c.cycle_id = o.cycle_id
                    WHERE o.site_id = ? AND o.ap_mac = ?
                      AND c.state = 'completed'
                      AND o.{timestamp_column} IS NOT NULL
                      AND o.{counter_column} IS NOT NULL
                    ORDER BY o.{timestamp_column} DESC, o.row_id DESC
                    LIMIT 1
                    """,
                    (site, mac),
                ).fetchone()
        except sqlite3.Error as exc:
            raise _storage_error(exc) from exc
        return None if row is None else (str(row[0]), int(row[1]))

    def get_latest_radio_rate_sample(
        self,
        *,
        site_id: str,
        ap_mac: str,
        band: str,
        counter_column: str,
    ) -> tuple[str, int] | None:
        """Return one bounded completed-cycle radio counter baseline."""
        if counter_column not in {"rx_bytes", "tx_bytes"}:
            raise ObservationValidationError("Unsupported radio rate baseline")
        site = require_text(site_id, "site_id")
        mac = require_mac(ap_mac, "ap_mac")
        canonical_band = require_text(band, "band")
        try:
            with self.read_connection() as connection:
                row = connection.execute(
                    f"""
                    SELECT o.radio_observed_at, o.{counter_column}
                    FROM ap_radio_observations AS o
                    JOIN observation_cycles AS c ON c.cycle_id = o.cycle_id
                    WHERE o.site_id = ? AND o.ap_mac = ? AND o.band = ?
                      AND c.state = 'completed'
                      AND o.radio_observed_at IS NOT NULL
                      AND o.{counter_column} IS NOT NULL
                    ORDER BY o.radio_observed_at DESC, o.row_id DESC
                    LIMIT 1
                    """,
                    (site, mac, canonical_band),
                ).fetchone()
        except sqlite3.Error as exc:
            raise _storage_error(exc) from exc
        return None if row is None else (str(row[0]), int(row[1]))

    def get_latest_complete_config_hash(
        self,
        *,
        site_id: str,
        ap_mac: str,
    ) -> str | None:
        """Return the newest complete configuration hash for one AP."""
        site = require_text(site_id, "site_id")
        mac = require_mac(ap_mac, "ap_mac")
        try:
            with self.read_connection() as connection:
                row = connection.execute(
                    """
                    SELECT s.config_sha256
                    FROM ap_config_snapshots AS s
                    JOIN observation_cycles AS c ON c.cycle_id = s.cycle_id
                    WHERE s.site_id = ? AND s.ap_mac = ?
                      AND c.state = 'completed' AND c.complete = 1
                    ORDER BY s.captured_at DESC, s.row_id DESC
                    LIMIT 1
                    """,
                    (site, mac),
                ).fetchone()
        except sqlite3.Error as exc:
            raise _storage_error(exc) from exc
        return None if row is None else str(row[0])

    def delete_expired_cycles(
        self,
        *,
        kinds: Sequence[str],
        cutoff_utc: str,
        limit: int,
    ) -> int:
        selected = tuple(kinds)
        if not selected or any(kind not in CYCLE_KINDS for kind in selected):
            raise ObservationValidationError("Cleanup kinds are invalid")
        cutoff = require_utc(cutoff_utc, "cutoff_utc")
        if type(limit) is not int or limit <= 0:
            raise ObservationValidationError("Cleanup limit must be positive")
        placeholders = ",".join("?" for _ in selected)

        def operation(connection: sqlite3.Connection) -> int:
            identifiers = [
                str(row[0])
                for row in connection.execute(
                    f"""
                    SELECT cycle_id
                    FROM observation_cycles
                    WHERE kind IN ({placeholders})
                      AND state != 'running'
                      AND started_at < ?
                    ORDER BY started_at, cycle_id
                    LIMIT ?
                    """,
                    (*selected, cutoff, limit),
                ).fetchall()
            ]
            if not identifiers:
                return 0
            id_placeholders = ",".join("?" for _ in identifiers)
            connection.execute(
                f"DELETE FROM observation_cycles "
                f"WHERE cycle_id IN ({id_placeholders})",
                tuple(identifiers),
            )
            return len(identifiers)

        return int(self._write(operation))

    def optimize(self) -> None:
        try:
            with self._write_lock, closing(self._connect()) as connection:
                connection.execute("PRAGMA optimize")
        except sqlite3.Error as exc:
            raise _storage_error(exc) from exc

    @contextmanager
    def read_connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect(readonly=True)
        try:
            yield connection
        finally:
            connection.close()

    def _write(self, operation: Callable[[sqlite3.Connection], Any]) -> Any:
        try:
            with self._write_lock, closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    result = operation(connection)
                    connection.commit()
                    return result
                except Exception:
                    connection.rollback()
                    raise
        except (ObservationValidationError, ObservationSchemaError):
            raise
        except sqlite3.Error as exc:
            raise _storage_error(exc) from exc

    def _startup_check(self, connection: sqlite3.Connection) -> None:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version > SCHEMA_VERSION:
            raise ObservationSchemaError(
                "Observation schema is newer than this code"
            )
        if version != SCHEMA_VERSION:
            raise ObservationSchemaError("Observation schema version mismatch")
        quick = connection.execute("PRAGMA quick_check").fetchone()
        if not quick or str(quick[0]) != "ok":
            raise ObservationSchemaError(
                "Observation startup health check failed"
            )
        self._validate_schema(connection)

    def _validate_schema(self, connection: sqlite3.Connection) -> None:
        tables = self._table_names(connection)
        if not REQUIRED_TABLES.issubset(tables):
            raise ObservationSchemaError(
                "Observation schema is missing required tables"
            )
        indexes = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
        if not set(REQUIRED_INDEXES).issubset(indexes):
            raise ObservationSchemaError(
                "Observation schema is missing required indexes"
            )
        for name, expected in REQUIRED_INDEXES.items():
            actual = tuple(
                str(row[2])
                for row in connection.execute(f"PRAGMA index_info({name})")
            )
            if actual != expected:
                raise ObservationSchemaError(
                    f"Observation index definition is invalid: {name}"
                )
        for table, required_columns in REQUIRED_COLUMNS.items():
            actual_columns = {
                str(row[1])
                for row in connection.execute(f"PRAGMA table_info({table})")
            }
            if not required_columns.issubset(actual_columns):
                raise ObservationSchemaError(
                    f"Observation table is incomplete: {table}"
                )
        for table, expected_keys in REQUIRED_UNIQUE_KEYS.items():
            actual_keys = {
                tuple(
                    str(column[2])
                    for column in connection.execute(
                        f"PRAGMA index_info({index_row[1]})"
                    )
                )
                for index_row in connection.execute(
                    f"PRAGMA index_list({table})"
                )
                if int(index_row[2]) == 1
            }
            if not set(expected_keys).issubset(actual_keys):
                raise ObservationSchemaError(
                    f"Observation UNIQUE constraint is invalid: {table}"
                )
        triggers = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger'"
            )
        }
        if not REQUIRED_TRIGGERS.issubset(triggers):
            raise ObservationSchemaError(
                "Observation schema is missing site identity triggers"
            )
        expected_foreign_keys = {
            "client_observations": {("observation_cycles", "cycle_id")},
            "ap_observations": {("observation_cycles", "cycle_id")},
            "ap_radio_observations": {
                ("observation_cycles", "cycle_id"),
                ("ap_observations", "ap_observation_row_id"),
            },
            "ap_config_snapshots": {("observation_cycles", "cycle_id")},
        }
        for table, expected in expected_foreign_keys.items():
            actual = {
                (str(row[2]), str(row[3]))
                for row in connection.execute(
                    f"PRAGMA foreign_key_list({table})"
                )
                if str(row[6]).upper() == "CASCADE"
            }
            if not expected.issubset(actual):
                raise ObservationSchemaError(
                    f"Observation foreign key is invalid: {table}"
                )
        violations = connection.execute("PRAGMA foreign_key_check").fetchone()
        if violations is not None:
            raise ObservationSchemaError(
                "Observation foreign key validation failed"
            )

    @staticmethod
    def _table_names(connection: sqlite3.Connection) -> set[str]:
        return {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
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

    def _ensure_parent(self) -> None:
        parent = self.db_path.parent
        if parent.exists():
            if not parent.is_dir() or not os.access(parent, os.W_OK):
                raise ObservationStorageError(
                    StorageFailureCategory.UNAVAILABLE,
                    "Observation database parent is unavailable",
                )
            return
        resolved = parent.resolve(strict=False)
        allowed = ALLOWED_AUTO_CREATE_ROOT.resolve(strict=False)
        try:
            is_allowed = resolved == allowed or allowed in resolved.parents
        except OSError:
            is_allowed = False
        if not is_allowed:
            raise ObservationStorageError(
                StorageFailureCategory.UNAVAILABLE,
                "Missing Observation database parent is not approved",
            )
        try:
            parent.mkdir(parents=True, mode=0o750, exist_ok=True)
            if os.name == "posix":
                os.chmod(parent, 0o750)
        except OSError as exc:
            raise ObservationStorageError(
                StorageFailureCategory.UNAVAILABLE,
                "Observation database parent could not be created",
            ) from exc

    def _database_exists(self) -> bool:
        return self._validate_database_target(require_exists=False)

    def _validate_database_target(self, *, require_exists: bool) -> bool:
        try:
            target = os.lstat(self.db_path)
        except FileNotFoundError:
            if require_exists:
                raise ObservationStorageError(
                    StorageFailureCategory.UNAVAILABLE,
                    "Observation database does not exist",
                )
            return False
        except OSError as exc:
            raise ObservationStorageError(
                StorageFailureCategory.UNAVAILABLE,
                "Observation database target is inaccessible",
            ) from exc
        if stat.S_ISLNK(target.st_mode) or not stat.S_ISREG(target.st_mode):
            raise ObservationStorageError(
                StorageFailureCategory.UNAVAILABLE,
                "Observation database target must be a regular file",
            )
        return True


def classify_sqlite_error(exc: sqlite3.Error) -> StorageFailureCategory:
    """Classify SQLite without exposing controller or client payloads."""
    code = getattr(exc, "sqlite_errorcode", None)
    primary = (code & 0xFF) if isinstance(code, int) else None
    if primary in {_SQLITE_BUSY, _SQLITE_LOCKED}:
        return StorageFailureCategory.BUSY
    if primary == _SQLITE_FULL:
        return StorageFailureCategory.FULL
    if primary == _SQLITE_IOERR:
        return StorageFailureCategory.IO_ERROR
    if primary in {_SQLITE_CORRUPT, _SQLITE_NOTADB}:
        return StorageFailureCategory.CORRUPT
    if primary in {_SQLITE_READONLY, _SQLITE_CANTOPEN}:
        return StorageFailureCategory.UNAVAILABLE
    if primary == _SQLITE_CONSTRAINT:
        return StorageFailureCategory.CONSTRAINT
    message = str(exc).lower()
    for fragment, category in (
        ("database is locked", StorageFailureCategory.BUSY),
        ("database table is locked", StorageFailureCategory.BUSY),
        ("database or disk is full", StorageFailureCategory.FULL),
        ("disk i/o error", StorageFailureCategory.IO_ERROR),
        ("database disk image is malformed", StorageFailureCategory.CORRUPT),
        ("file is not a database", StorageFailureCategory.CORRUPT),
        ("readonly database", StorageFailureCategory.UNAVAILABLE),
        ("unable to open database file", StorageFailureCategory.UNAVAILABLE),
        ("constraint failed", StorageFailureCategory.CONSTRAINT),
        ("identity mismatch", StorageFailureCategory.CONSTRAINT),
    ):
        if fragment in message:
            return category
    return StorageFailureCategory.DEGRADED


def _storage_error(exc: sqlite3.Error) -> ObservationStorageError:
    return ObservationStorageError(classify_sqlite_error(exc))


def _insert_ignore_sql(table: str, columns: Sequence[str]) -> str:
    names = ", ".join(columns)
    placeholders = ", ".join("?" for _ in columns)
    return (
        f"INSERT INTO {table} ({names}) VALUES ({placeholders}) "
        "ON CONFLICT DO NOTHING"
    )


def _prepare_row(
    source: Mapping[str, Any],
    required: Sequence[str],
    optional: Sequence[str],
) -> dict[str, Any]:
    if not isinstance(source, Mapping):
        raise ObservationValidationError("Observation row must be a mapping")
    allowed = set(required) | set(optional)
    unknown = set(source) - allowed
    if unknown:
        raise ObservationValidationError(
            "Observation row contains unsupported fields"
        )
    missing = [name for name in required if name not in source]
    if missing:
        raise ObservationValidationError(
            "Observation row is missing required fields"
        )
    result = {name: source.get(name) for name in (*required, *optional)}
    for name in ("cycle_id", "site_id"):
        if name in result:
            result[name] = require_text(result[name], name)
    for name in _MAC_COLUMNS.intersection(result):
        if result[name] is not None:
            result[name] = require_mac(result[name], name)
    for name in _TIMESTAMP_COLUMNS.intersection(result):
        if result[name] is not None:
            result[name] = require_utc(result[name], name)
    for name in _BOOL_COLUMNS.intersection(result):
        value = result[name]
        if value is not None and type(value) is not bool:
            raise ObservationValidationError(f"{name} must be boolean or null")
        result[name] = None if value is None else int(value)
    for name in _INTEGER_COLUMNS.intersection(result):
        value = result[name]
        if value is not None and type(value) is not int:
            raise ObservationValidationError(f"{name} must be integer or null")
        if value is not None and name in _NONNEGATIVE_COLUMNS and value < 0:
            raise ObservationValidationError(
                f"{name} must be non-negative or null"
            )
    for name in _REAL_COLUMNS.intersection(result):
        value = result[name]
        if value is None:
            continue
        if type(value) not in {int, float} or not math.isfinite(float(value)):
            raise ObservationValidationError(f"{name} must be finite or null")
        result[name] = float(value)
    for name in _RATE_REASON_COLUMNS.intersection(result):
        value = result[name]
        if value is not None and value not in RATE_REASONS:
            raise ObservationValidationError(f"{name} is invalid")
    if "band" in result and result["band"] is not None:
        result["band"] = require_text(result["band"], "band")
    if "config_sha256" in result:
        value = result["config_sha256"]
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise ObservationValidationError(
                "config_sha256 must be lowercase SHA-256"
            )
    if "config_json" in result:
        config_json = require_text(
            result["config_json"],
            "config_json",
        )
        canonical = _canonical_json_object(config_json)
        if canonical != config_json:
            raise ObservationValidationError(
                "config_json must use canonical strict JSON"
            )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if result.get("config_sha256") != digest:
            raise ObservationValidationError(
                "config_sha256 does not match config_json"
            )
        result["config_json"] = canonical
    return result


def _canonical_json_object(value: str) -> str:
    def reject_constant(token: str) -> None:
        raise ValueError(f"Invalid JSON constant: {token}")

    def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = item
        return result

    try:
        parsed = json.loads(
            value,
            parse_constant=reject_constant,
            object_pairs_hook=strict_object,
        )
        if not isinstance(parsed, dict):
            raise ValueError("Config JSON root must be an object")
        return json.dumps(
            parsed,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ObservationValidationError(
            "config_json must be a strict JSON object"
        ) from exc


def _cycle_from_row(row: sqlite3.Row) -> ObservationCycle:
    return ObservationCycle(
        cycle_id=str(row["cycle_id"]),
        kind=str(row["kind"]),
        site_id=str(row["site_id"]),
        state=str(row["state"]),
        started_at=str(row["started_at"]),
        finished_at=row["finished_at"],
        abandoned_at=row["abandoned_at"],
        complete=(
            None if row["complete"] is None else bool(row["complete"])
        ),
        result=row["result"],
        source_rows_reported=row["source_rows_reported"],
        items_seen=int(row["items_seen"]),
        items_stored=int(row["items_stored"]),
        items_skipped=int(row["items_skipped"]),
        error_count=int(row["error_count"]),
        data_quality_warning_count=int(
            row["data_quality_warning_count"]
        ),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )
