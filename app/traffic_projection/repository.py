"""SQLite storage owner for the disposable Traffic projection."""

from __future__ import annotations

import sqlite3
import os
import time
from contextlib import closing, contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from .models import (
    BUSY_TIMEOUT_MS,
    HEALTHY_FULL_RECONCILE_MAX_AGE_SECONDS,
    JOURNAL_SIZE_LIMIT_BYTES,
    MAX_BULK_CYCLES_PER_TRANSACTION,
    MAX_BULK_TRANSACTION_SECONDS,
    PROJECTION_VERSION,
    SCHEMA_VERSION,
    SOURCE,
    SOURCE_SCHEMA_VERSION,
    WAL_AUTOCHECKPOINT_PAGES,
    ProjectedCycle,
    TrafficProjectionStorageCorrupt,
    TrafficProjectionStorageUnavailable,
    validate_projection_version,
)


REQUIRED_TABLES = frozenset({
    "traffic_projection_versions",
    "traffic_projection_site_state",
    "traffic_projection_cycles",
    "traffic_projection_ap_cycles",
})
REQUIRED_EXPRESSION_INDEXES = frozenset({
    "idx_projection_one_active",
    "idx_projection_one_target",
})
REQUIRED_COLUMNS = {
    "traffic_projection_versions": (
        "projection_version projection_schema_version source source_schema_version "
        "semantic_contract_sha256 status created_at ready_at activated_at retired_at "
        "build_from_utc build_through_utc last_validation_at"
    ).split(),
    "traffic_projection_site_state": (
        "projection_version site_id projection_revision status fast_checkpoint_started_at "
        "fast_checkpoint_cycle_id source_head_utc source_head_cycle_id projection_head_utc "
        "projection_head_cycle_id last_incremental_scan_at last_incremental_progress_at "
        "reconcile_cursor_started_at reconcile_cursor_cycle_id reconcile_sweep_started_at "
        "reconcile_sweep_source_head_utc reconcile_sweep_source_head_cycle_id "
        "reconcile_sweep_from_utc last_full_reconcile_completed_at "
        "last_full_reconcile_source_head_utc last_full_reconcile_source_head_cycle_id "
        "last_deep_audit_at last_success_at backlog_cycle_count last_error_category "
        "available_from_utc available_through_utc source_watermark_utc "
        "source_boundary_proof_at source_boundary_proof_head_utc "
        "source_boundary_proof_head_cycle_id"
    ).split(),
    "traffic_projection_cycles": (
        "projection_version site_id cycle_id source_kind source_state source_started_at "
        "source_finished_at source_abandoned_at source_complete source_result "
        "source_rows_reported items_seen items_stored items_skipped error_count "
        "data_quality_warning_count source_updated_at source_revision_marker "
        "source_semantic_fingerprint projected_at integrity_ok stored_row_count "
        "bad_site_count bad_mac_count duplicate_mac_count bad_flag_count bad_rate_count "
        "bad_time_count metric_facts_present wired_complete lan_complete wired_pair_count "
        "lan_pair_count wired_oldest_at wired_newest_at lan_oldest_at lan_newest_at "
        "wired_download_mbps wired_upload_mbps lan_download_mbps lan_upload_mbps "
        "wired_no_baseline_count wired_counter_reset_count wired_gap_too_large_count "
        "wired_invalid_elapsed_count wired_source_unavailable_count wired_ok_count "
        "lan_no_baseline_count lan_counter_reset_count lan_gap_too_large_count "
        "lan_invalid_elapsed_count lan_source_unavailable_count lan_ok_count"
    ).split(),
    "traffic_projection_ap_cycles": (
        "projection_version site_id cycle_id ap_mac historical_name partial overview_ok "
        "wired_uplink_ok lan_traffic_ok radios_ok wired_observed_at lan_observed_at "
        "wired_download_mbps wired_upload_mbps wired_download_reason wired_upload_reason "
        "lan_download_mbps lan_upload_mbps lan_download_reason lan_upload_reason projected_at"
    ).split(),
}
REQUIRED_INDEX_COLUMNS = {
    "idx_projection_cycles_started": (
        "projection_version", "site_id", "source_started_at", "cycle_id"
    ),
    "idx_projection_cycles_finished": (
        "projection_version", "site_id", "source_finished_at", "cycle_id"
    ),
    "idx_projection_cycles_lifecycle": (
        "projection_version", "site_id", "source_state", "source_result",
        "source_started_at",
    ),
    "idx_projection_ap_cycle": (
        "projection_version", "site_id", "cycle_id", "ap_mac"
    ),
    "idx_projection_ap_identity": (
        "projection_version", "site_id", "ap_mac", "cycle_id"
    ),
}


def _utc(column: str, nullable: bool = False) -> str:
    shape = (
        f"length({column})=24 AND substr({column},5,1)='-' "
        f"AND substr({column},8,1)='-' AND substr({column},11,1)='T' "
        f"AND substr({column},14,1)=':' AND substr({column},17,1)=':' "
        f"AND substr({column},20,1)='.' AND substr({column},24,1)='Z'"
    )
    return f"({column} IS NULL OR ({shape}))" if nullable else f"({shape})"


def schema_sql() -> str:
    """Return the complete, deterministic schema-v1 DDL."""
    nonnegative = "CHECK ({name}>=0)"
    reason = (
        "CHECK ({name} IS NULL OR {name} IN "
        "('ok','no_baseline','counter_reset','gap_too_large',"
        "'invalid_elapsed','source_unavailable'))"
    )
    counts = ",\n".join(
        f"            {name} INTEGER NOT NULL {nonnegative.format(name=name)}"
        for family in ("wired", "lan")
        for name in (
            f"{family}_no_baseline_count",
            f"{family}_counter_reset_count",
            f"{family}_gap_too_large_count",
            f"{family}_invalid_elapsed_count",
            f"{family}_source_unavailable_count",
            f"{family}_ok_count",
        )
    )
    return f"""
        BEGIN IMMEDIATE;
        CREATE TABLE traffic_projection_versions (
            projection_version TEXT PRIMARY KEY,
            projection_schema_version INTEGER NOT NULL
              CHECK (projection_schema_version=1),
            source TEXT NOT NULL CHECK (source='observations'),
            source_schema_version INTEGER NOT NULL CHECK (source_schema_version=1),
            semantic_contract_sha256 TEXT NOT NULL
              CHECK (semantic_contract_sha256 GLOB '[0-9a-f]*'
                     AND length(semantic_contract_sha256)=64),
            status TEXT NOT NULL CHECK (status IN
              ('building','ready','active','retired','failed')),
            created_at TEXT NOT NULL CHECK {_utc('created_at')},
            ready_at TEXT CHECK {_utc('ready_at', True)},
            activated_at TEXT CHECK {_utc('activated_at', True)},
            retired_at TEXT CHECK {_utc('retired_at', True)},
            build_from_utc TEXT CHECK {_utc('build_from_utc', True)},
            build_through_utc TEXT CHECK {_utc('build_through_utc', True)},
            last_validation_at TEXT CHECK {_utc('last_validation_at', True)}
        );
        CREATE UNIQUE INDEX idx_projection_one_active
          ON traffic_projection_versions((status='active')) WHERE status='active';
        CREATE UNIQUE INDEX idx_projection_one_target
          ON traffic_projection_versions((status IN ('building','ready')))
          WHERE status IN ('building','ready');

        CREATE TABLE traffic_projection_site_state (
            projection_version TEXT NOT NULL,
            site_id TEXT NOT NULL CHECK (length(trim(site_id))>0),
            projection_revision INTEGER NOT NULL CHECK (projection_revision>=0),
            status TEXT NOT NULL CHECK (status IN
              ('healthy','catching_up','stale','unavailable','rebuilding','diverged')),
            fast_checkpoint_started_at TEXT CHECK {_utc('fast_checkpoint_started_at', True)},
            fast_checkpoint_cycle_id TEXT,
            source_head_utc TEXT CHECK {_utc('source_head_utc', True)},
            source_head_cycle_id TEXT,
            projection_head_utc TEXT CHECK {_utc('projection_head_utc', True)},
            projection_head_cycle_id TEXT,
            last_incremental_scan_at TEXT CHECK {_utc('last_incremental_scan_at', True)},
            last_incremental_progress_at TEXT CHECK {_utc('last_incremental_progress_at', True)},
            reconcile_cursor_started_at TEXT CHECK {_utc('reconcile_cursor_started_at', True)},
            reconcile_cursor_cycle_id TEXT,
            reconcile_sweep_started_at TEXT CHECK {_utc('reconcile_sweep_started_at', True)},
            reconcile_sweep_source_head_utc TEXT CHECK {_utc('reconcile_sweep_source_head_utc', True)},
            reconcile_sweep_source_head_cycle_id TEXT,
            reconcile_sweep_from_utc TEXT CHECK {_utc('reconcile_sweep_from_utc', True)},
            last_full_reconcile_completed_at TEXT CHECK {_utc('last_full_reconcile_completed_at', True)},
            last_full_reconcile_source_head_utc TEXT CHECK {_utc('last_full_reconcile_source_head_utc', True)},
            last_full_reconcile_source_head_cycle_id TEXT,
            last_deep_audit_at TEXT CHECK {_utc('last_deep_audit_at', True)},
            last_success_at TEXT CHECK {_utc('last_success_at', True)},
            backlog_cycle_count INTEGER CHECK (backlog_cycle_count IS NULL OR backlog_cycle_count>=0),
            last_error_category TEXT,
            available_from_utc TEXT CHECK {_utc('available_from_utc', True)},
            available_through_utc TEXT CHECK {_utc('available_through_utc', True)},
            source_watermark_utc TEXT CHECK {_utc('source_watermark_utc', True)},
            source_boundary_proof_at TEXT CHECK {_utc('source_boundary_proof_at', True)},
            source_boundary_proof_head_utc TEXT CHECK {_utc('source_boundary_proof_head_utc', True)},
            source_boundary_proof_head_cycle_id TEXT,
            PRIMARY KEY (projection_version,site_id),
            FOREIGN KEY (projection_version) REFERENCES traffic_projection_versions(projection_version)
              ON DELETE CASCADE
        );

        CREATE TABLE traffic_projection_cycles (
            projection_version TEXT NOT NULL,
            site_id TEXT NOT NULL,
            cycle_id TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            source_state TEXT NOT NULL,
            source_started_at TEXT NOT NULL CHECK {_utc('source_started_at')},
            source_finished_at TEXT CHECK {_utc('source_finished_at', True)},
            source_abandoned_at TEXT CHECK {_utc('source_abandoned_at', True)},
            source_complete INTEGER CHECK (source_complete IS NULL OR source_complete IN (0,1)),
            source_result TEXT,
            source_rows_reported INTEGER CHECK (source_rows_reported IS NULL OR source_rows_reported>=0),
            items_seen INTEGER NOT NULL CHECK (items_seen>=0),
            items_stored INTEGER NOT NULL CHECK (items_stored>=0),
            items_skipped INTEGER NOT NULL CHECK (items_skipped>=0),
            error_count INTEGER NOT NULL CHECK (error_count>=0),
            data_quality_warning_count INTEGER NOT NULL CHECK (data_quality_warning_count>=0),
            source_updated_at TEXT NOT NULL CHECK {_utc('source_updated_at')},
            source_revision_marker TEXT NOT NULL CHECK (length(source_revision_marker)=64),
            source_semantic_fingerprint TEXT CHECK
              (source_semantic_fingerprint IS NULL OR length(source_semantic_fingerprint)=64),
            projected_at TEXT NOT NULL CHECK {_utc('projected_at')},
            integrity_ok INTEGER NOT NULL CHECK (integrity_ok IN (0,1)),
            stored_row_count INTEGER NOT NULL CHECK (stored_row_count>=0),
            bad_site_count INTEGER NOT NULL CHECK (bad_site_count>=0),
            bad_mac_count INTEGER NOT NULL CHECK (bad_mac_count>=0),
            duplicate_mac_count INTEGER NOT NULL CHECK (duplicate_mac_count>=0),
            bad_flag_count INTEGER NOT NULL CHECK (bad_flag_count>=0),
            bad_rate_count INTEGER NOT NULL CHECK (bad_rate_count>=0),
            bad_time_count INTEGER NOT NULL CHECK (bad_time_count>=0),
            metric_facts_present INTEGER NOT NULL CHECK (metric_facts_present IN (0,1)),
            wired_complete INTEGER NOT NULL CHECK (wired_complete IN (0,1)),
            lan_complete INTEGER NOT NULL CHECK (lan_complete IN (0,1)),
            wired_pair_count INTEGER NOT NULL CHECK (wired_pair_count>=0),
            lan_pair_count INTEGER NOT NULL CHECK (lan_pair_count>=0),
            wired_oldest_at TEXT CHECK {_utc('wired_oldest_at', True)},
            wired_newest_at TEXT CHECK {_utc('wired_newest_at', True)},
            lan_oldest_at TEXT CHECK {_utc('lan_oldest_at', True)},
            lan_newest_at TEXT CHECK {_utc('lan_newest_at', True)},
            wired_download_mbps REAL CHECK (wired_download_mbps IS NULL OR wired_download_mbps>=0),
            wired_upload_mbps REAL CHECK (wired_upload_mbps IS NULL OR wired_upload_mbps>=0),
            lan_download_mbps REAL CHECK (lan_download_mbps IS NULL OR lan_download_mbps>=0),
            lan_upload_mbps REAL CHECK (lan_upload_mbps IS NULL OR lan_upload_mbps>=0),
{counts},
            PRIMARY KEY (projection_version,site_id,cycle_id),
            FOREIGN KEY (projection_version,site_id)
              REFERENCES traffic_projection_site_state(projection_version,site_id)
              ON DELETE CASCADE
        );

        CREATE TABLE traffic_projection_ap_cycles (
            projection_version TEXT NOT NULL,
            site_id TEXT NOT NULL,
            cycle_id TEXT NOT NULL,
            ap_mac TEXT NOT NULL,
            historical_name TEXT,
            partial INTEGER NOT NULL CHECK (partial IN (0,1)),
            overview_ok INTEGER NOT NULL CHECK (overview_ok IN (0,1)),
            wired_uplink_ok INTEGER NOT NULL CHECK (wired_uplink_ok IN (0,1)),
            lan_traffic_ok INTEGER NOT NULL CHECK (lan_traffic_ok IN (0,1)),
            radios_ok INTEGER NOT NULL CHECK (radios_ok IN (0,1)),
            wired_observed_at TEXT CHECK {_utc('wired_observed_at', True)},
            lan_observed_at TEXT CHECK {_utc('lan_observed_at', True)},
            wired_download_mbps REAL CHECK (wired_download_mbps IS NULL OR wired_download_mbps>=0),
            wired_upload_mbps REAL CHECK (wired_upload_mbps IS NULL OR wired_upload_mbps>=0),
            wired_download_reason TEXT {reason.format(name='wired_download_reason')},
            wired_upload_reason TEXT {reason.format(name='wired_upload_reason')},
            lan_download_mbps REAL CHECK (lan_download_mbps IS NULL OR lan_download_mbps>=0),
            lan_upload_mbps REAL CHECK (lan_upload_mbps IS NULL OR lan_upload_mbps>=0),
            lan_download_reason TEXT {reason.format(name='lan_download_reason')},
            lan_upload_reason TEXT {reason.format(name='lan_upload_reason')},
            projected_at TEXT NOT NULL CHECK {_utc('projected_at')},
            PRIMARY KEY (projection_version,site_id,cycle_id,ap_mac),
            FOREIGN KEY (projection_version,site_id,cycle_id)
              REFERENCES traffic_projection_cycles(projection_version,site_id,cycle_id)
              ON DELETE CASCADE
        );
        CREATE INDEX idx_projection_cycles_started
          ON traffic_projection_cycles(projection_version,site_id,source_started_at,cycle_id);
        CREATE INDEX idx_projection_cycles_finished
          ON traffic_projection_cycles(projection_version,site_id,source_finished_at,cycle_id);
        CREATE INDEX idx_projection_cycles_lifecycle
          ON traffic_projection_cycles(projection_version,site_id,source_state,source_result,source_started_at);
        CREATE INDEX idx_projection_ap_cycle
          ON traffic_projection_ap_cycles(projection_version,site_id,cycle_id,ap_mac);
        CREATE INDEX idx_projection_ap_identity
          ON traffic_projection_ap_cycles(projection_version,site_id,ap_mac,cycle_id);
        PRAGMA user_version=1;
        COMMIT;
    """


class TrafficProjectionRepository:
    """Own only the disposable derived database and its schema."""

    def __init__(
        self,
        db_path: str,
        *,
        projection_version: str = PROJECTION_VERSION,
        busy_timeout_ms: int = BUSY_TIMEOUT_MS,
    ):
        self.db_path = Path(db_path)
        self.projection_version = validate_projection_version(projection_version)
        self.busy_timeout_ms = int(busy_timeout_ms)

    def initialize(self) -> bool:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        existed = self.db_path.exists()
        try:
            with closing(self._connect(False)) as connection:
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                tables = self._tables(connection)
                if version == 0 and not (tables & REQUIRED_TABLES):
                    connection.executescript(schema_sql())
                elif version != SCHEMA_VERSION or not REQUIRED_TABLES <= tables:
                    raise TrafficProjectionStorageCorrupt(
                        "Traffic projection schema is incompatible"
                    )
                self._validate(connection, deep=True)
                try:
                    os.chmod(self.db_path, 0o600)
                except OSError:
                    pass
        except TrafficProjectionStorageCorrupt:
            raise
        except (sqlite3.Error, OSError) as exc:
            raise TrafficProjectionStorageUnavailable(
                "Traffic projection storage is unavailable"
            ) from exc
        return not existed

    @contextmanager
    def read_connection(self) -> Iterator[sqlite3.Connection]:
        uri = self.db_path.resolve().as_uri() + "?mode=ro"
        try:
            with closing(sqlite3.connect(uri, uri=True, timeout=self.busy_timeout_ms / 1000)) as connection:
                connection.row_factory = sqlite3.Row
                connection.execute(f"PRAGMA busy_timeout={self.busy_timeout_ms}")
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("PRAGMA query_only=ON")
                self._validate(connection, deep=False)
                yield connection
        except TrafficProjectionStorageCorrupt:
            raise
        except (sqlite3.Error, OSError) as exc:
            raise TrafficProjectionStorageUnavailable(
                "Traffic projection read is unavailable"
            ) from exc

    @contextmanager
    def write_connection(self) -> Iterator[sqlite3.Connection]:
        try:
            with closing(self._connect(False)) as connection:
                try:
                    yield connection
                finally:
                    self.secure_files()
        except (sqlite3.Error, OSError) as exc:
            raise TrafficProjectionStorageUnavailable(
                "Traffic projection write is unavailable"
            ) from exc

    def ensure_version(self, semantic_sha256: str, now_utc: str) -> None:
        with self.write_connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """INSERT OR IGNORE INTO traffic_projection_versions
                   (projection_version,projection_schema_version,source,
                    source_schema_version,semantic_contract_sha256,status,created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (self.projection_version, SCHEMA_VERSION, SOURCE,
                 SOURCE_SCHEMA_VERSION, semantic_sha256, "building", now_utc),
            )
            row = connection.execute(
                "SELECT semantic_contract_sha256 FROM traffic_projection_versions WHERE projection_version=?",
                (self.projection_version,),
            ).fetchone()
            if row is None or row[0] != semantic_sha256:
                connection.rollback()
                raise TrafficProjectionStorageCorrupt(
                    "Traffic projection semantic contract is incompatible"
                )
            connection.commit()

    def ensure_site(self, site_id: str, *, status: str = "rebuilding") -> None:
        with self.write_connection() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO traffic_projection_site_state
                   (projection_version,site_id,projection_revision,status)
                   VALUES (?,?,0,?)""",
                (self.projection_version, site_id, status),
            )
            connection.commit()

    def active_version(self, connection: sqlite3.Connection | None = None) -> str | None:
        if connection is not None:
            row = connection.execute(
                "SELECT projection_version FROM traffic_projection_versions WHERE status='active'"
            ).fetchone()
            return None if row is None else str(row[0])
        with self.read_connection() as read:
            return self.active_version(read)

    def version_status(self, projection_version: str | None = None) -> str | None:
        version = projection_version or self.projection_version
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT status FROM traffic_projection_versions WHERE projection_version=?",
                (version,),
            ).fetchone()
            return None if row is None else str(row[0])

    def version_record(
        self, projection_version: str | None = None
    ) -> Mapping[str, Any] | None:
        version = projection_version or self.projection_version
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM traffic_projection_versions WHERE projection_version=?",
                (version,),
            ).fetchone()
            return None if row is None else dict(row)

    def worker_version_records(self) -> tuple[Mapping[str, Any], ...]:
        """Return the single-writer active/target set in maintenance order."""
        with self.read_connection() as connection:
            rows = connection.execute(
                """SELECT * FROM traffic_projection_versions
                   WHERE status IN ('active','building','ready')
                   ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END,
                            created_at,projection_version"""
            ).fetchall()
            return tuple(dict(row) for row in rows)

    def fail_version(self, now_utc: str) -> None:
        """Persist an unrecoverable target-build failure without touching active."""
        with self.write_connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            changed = connection.execute(
                """UPDATE traffic_projection_versions
                   SET status='failed',last_validation_at=?
                   WHERE projection_version=? AND status IN ('building','ready')""",
                (now_utc, self.projection_version),
            ).rowcount
            if changed != 1:
                connection.rollback()
                raise TrafficProjectionStorageCorrupt(
                    "Traffic projection version cannot become failed"
                )
            connection.commit()

    def activate(
        self,
        now_utc: str,
        configured_sites: Sequence[str],
        current_source_heads: Mapping[str, tuple[str, str]],
    ) -> None:
        with self.write_connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._validate(connection, deep=True)
            states = connection.execute(
                """SELECT * FROM traffic_projection_site_state
                   WHERE projection_version=?""",
                (self.projection_version,),
            ).fetchall()
            by_site = {str(row["site_id"]): dict(row) for row in states}
            if (
                not configured_sites
                or any(
                    site not in by_site
                    or site not in current_source_heads
                    or not self._site_ready(
                        by_site[site], current_source_heads[site], now_utc
                    )
                    for site in configured_sites
                )
            ):
                connection.rollback()
                raise TrafficProjectionStorageCorrupt(
                    "Traffic projection version cannot be activated"
                )
            connection.execute(
                "UPDATE traffic_projection_versions SET status='retired',retired_at=? WHERE status='active'",
                (now_utc,),
            )
            changed = connection.execute(
                """UPDATE traffic_projection_versions
                   SET status='active',activated_at=?,
                       last_validation_at=? WHERE projection_version=? AND status='ready'""",
                (now_utc, now_utc, self.projection_version),
            ).rowcount
            if changed != 1:
                connection.rollback()
                raise TrafficProjectionStorageCorrupt(
                    "Traffic projection version cannot be activated"
                )
            connection.commit()

    def mark_ready(
        self,
        now_utc: str,
        configured_sites: Sequence[str],
        current_source_heads: Mapping[str, tuple[str, str]],
    ) -> None:
        """Mark a globally built version ready; activation remains a separate action."""
        if not configured_sites:
            raise TrafficProjectionStorageCorrupt(
                "Traffic projection build is not ready"
            )
        with self.write_connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._validate(connection, deep=True)
            states = connection.execute(
                """SELECT *
                   FROM traffic_projection_site_state WHERE projection_version=?""",
                (self.projection_version,),
            ).fetchall()
            by_site = {str(row["site_id"]): dict(row) for row in states}
            if any(
                site not in by_site
                or site not in current_source_heads
                or not self._site_ready(
                    by_site[site], current_source_heads[site], now_utc
                )
                for site in configured_sites
            ):
                connection.rollback()
                raise TrafficProjectionStorageCorrupt(
                    "Traffic projection build is not ready"
                )
            changed = connection.execute(
                """UPDATE traffic_projection_versions
                   SET status='ready',ready_at=?,last_validation_at=?
                   WHERE projection_version=? AND status='building'""",
                (now_utc, now_utc, self.projection_version),
            ).rowcount
            if changed != 1:
                connection.rollback()
                raise TrafficProjectionStorageCorrupt(
                    "Traffic projection version cannot become ready"
                )
            connection.commit()

    @staticmethod
    def _site_ready(
        state: Mapping[str, Any], current_source_head: tuple[str, str], now_utc: str
    ) -> bool:
        try:
            now = datetime.fromisoformat(now_utc.replace("Z", "+00:00"))
            reconciled = datetime.fromisoformat(
                str(state["last_full_reconcile_completed_at"]).replace("Z", "+00:00")
            )
            audited = datetime.fromisoformat(
                str(state["last_deep_audit_at"]).replace("Z", "+00:00")
            )
        except (KeyError, TypeError, ValueError):
            return False
        source_head = (state.get("source_head_utc"), state.get("source_head_cycle_id"))
        projection_head = (
            state.get("projection_head_utc"), state.get("projection_head_cycle_id")
        )
        reconcile_head = (
            state.get("last_full_reconcile_source_head_utc"),
            state.get("last_full_reconcile_source_head_cycle_id"),
        )
        boundary_head = (
            state.get("source_boundary_proof_head_utc"),
            state.get("source_boundary_proof_head_cycle_id"),
        )
        available_from = state.get("available_from_utc")
        available_through = state.get("available_through_utc")
        source_watermark = state.get("source_watermark_utc")
        boundary_values_coherent = bool(
            (available_from is None) == (available_through is None)
            and (
                available_from is None
                or (
                    source_watermark is not None
                    and str(available_from) <= str(available_through)
                    and str(available_through) <= str(source_watermark)
                )
            )
        )
        return bool(
            state.get("status") == "healthy"
            and source_head == current_source_head
            and all(isinstance(value, str) and value for value in projection_head)
            and projection_head >= current_source_head
            and all(isinstance(value, str) and value for value in reconcile_head)
            and reconcile_head <= current_source_head
            and 0 <= (now - reconciled).total_seconds()
            <= HEALTHY_FULL_RECONCILE_MAX_AGE_SECONDS
            and 0 <= (now - audited).total_seconds()
            <= HEALTHY_FULL_RECONCILE_MAX_AGE_SECONDS
            and audited >= reconciled
            and state.get("reconcile_sweep_started_at") is None
            and state.get("reconcile_cursor_started_at") is None
            and state.get("backlog_cycle_count") in (0, None)
            and state.get("last_error_category") is None
            and isinstance(state.get("source_boundary_proof_at"), str)
            and boundary_head == current_source_head
            and boundary_values_coherent
        )

    def source_marker(self, site_id: str, cycle_id: str) -> str | None:
        with self.read_connection() as connection:
            row = connection.execute(
                """SELECT source_revision_marker FROM traffic_projection_cycles
                   WHERE projection_version=? AND site_id=? AND cycle_id=?""",
                (self.projection_version, site_id, cycle_id),
            ).fetchone()
            return None if row is None else str(row[0])

    def source_markers(
        self, site_id: str, cycle_ids: Sequence[str]
    ) -> Mapping[str, str]:
        if not cycle_ids:
            return {}
        result: dict[str, str] = {}
        with self.read_connection() as connection:
            for offset in range(0, len(cycle_ids), 800):
                batch = cycle_ids[offset:offset + 800]
                placeholders = ",".join("?" for _ in batch)
                rows = connection.execute(
                    f"""SELECT cycle_id,source_revision_marker
                        FROM traffic_projection_cycles
                        WHERE projection_version=? AND site_id=?
                          AND cycle_id IN ({placeholders})""",
                    (self.projection_version, site_id, *batch),
                ).fetchall()
                result.update({str(row[0]): str(row[1]) for row in rows})
        return result

    def cycle_count(
        self, site_id: str, *, from_utc: str, through: tuple[str, str]
    ) -> int:
        with self.read_connection() as connection:
            return int(connection.execute(
                """SELECT COUNT(*) FROM traffic_projection_cycles
                   WHERE projection_version=? AND site_id=? AND source_started_at>=?
                     AND (source_started_at<? OR
                          (source_started_at=? AND cycle_id<=?))""",
                (self.projection_version, site_id, from_utc,
                 through[0], through[0], through[1]),
            ).fetchone()[0])

    def upsert_cycle(self, projected: ProjectedCycle, now_utc: str) -> bool:
        results = self.upsert_cycles((projected,), now_utc)
        if len(results) != 1:
            raise TrafficProjectionStorageUnavailable(
                "Traffic projection cycle write did not complete"
            )
        return results[0][1]

    def upsert_cycles(
        self,
        projected_cycles: Sequence[ProjectedCycle],
        now_utc: str,
        *,
        work_deadline_monotonic: float | None = None,
        monotonic=time.monotonic,
    ) -> tuple[tuple[str, bool], ...]:
        """Write one bounded cycle batch in one restart-safe transaction."""
        cycles = tuple(projected_cycles)
        if len(cycles) > MAX_BULK_CYCLES_PER_TRANSACTION:
            raise ValueError("projection cycle batch exceeds the bounded maximum")
        if not cycles:
            return ()
        if (
            work_deadline_monotonic is not None
            and monotonic() >= work_deadline_monotonic
        ):
            return ()
        transaction_deadline = monotonic() + MAX_BULK_TRANSACTION_SECONDS
        if work_deadline_monotonic is not None:
            transaction_deadline = min(
                transaction_deadline, work_deadline_monotonic
            )
        results: list[tuple[str, bool]] = []
        with self.write_connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for projected in cycles:
                if results and monotonic() >= transaction_deadline:
                    break
                changed = self._upsert_cycle(connection, projected, now_utc)
                results.append((str(projected.cycle["cycle_id"]), changed))
            connection.commit()
        return tuple(results)

    def _upsert_cycle(
        self,
        connection: sqlite3.Connection,
        projected: ProjectedCycle,
        now_utc: str,
    ) -> bool:
        cycle = dict(projected.cycle)
        counts = projected.integrity_counts
        facts = projected.family_facts
        names = (
            "projection_version site_id cycle_id source_kind source_state "
            "source_started_at source_finished_at source_abandoned_at source_complete "
            "source_result source_rows_reported items_seen items_stored items_skipped "
            "error_count data_quality_warning_count source_updated_at source_revision_marker "
            "source_semantic_fingerprint projected_at integrity_ok stored_row_count "
            "bad_site_count bad_mac_count duplicate_mac_count bad_flag_count bad_rate_count "
            "bad_time_count metric_facts_present wired_complete lan_complete wired_pair_count "
            "lan_pair_count wired_oldest_at wired_newest_at lan_oldest_at lan_newest_at "
            "wired_download_mbps wired_upload_mbps lan_download_mbps lan_upload_mbps "
            "wired_no_baseline_count wired_counter_reset_count wired_gap_too_large_count "
            "wired_invalid_elapsed_count wired_source_unavailable_count wired_ok_count "
            "lan_no_baseline_count lan_counter_reset_count lan_gap_too_large_count "
            "lan_invalid_elapsed_count lan_source_unavailable_count lan_ok_count"
        ).split()
        values = [
            self.projection_version, cycle["site_id"], cycle["cycle_id"], cycle["kind"],
            cycle["state"], cycle["started_at"], cycle.get("finished_at"),
            cycle.get("abandoned_at"), cycle.get("complete"), cycle.get("result"),
            cycle.get("source_rows_reported"), cycle["items_seen"], cycle["items_stored"],
            cycle["items_skipped"], cycle["error_count"],
            cycle["data_quality_warning_count"], cycle["updated_at"],
            projected.source_revision_marker, projected.source_semantic_fingerprint,
            now_utc, int(projected.integrity_ok), counts["stored_row_count"],
            counts["bad_site_count"], counts["bad_mac_count"], counts["duplicate_mac_count"],
            counts["bad_flag_count"], counts["bad_rate_count"], counts["bad_time_count"],
            int(projected.metric_facts_present),
            *[facts[name] for name in names[29:]],
        ]
        previous = connection.execute(
            """SELECT source_semantic_fingerprint FROM traffic_projection_cycles
               WHERE projection_version=? AND site_id=? AND cycle_id=?""",
            (self.projection_version, cycle["site_id"], cycle["cycle_id"]),
        ).fetchone()
        connection.execute(
            "DELETE FROM traffic_projection_cycles WHERE projection_version=? AND site_id=? AND cycle_id=?",
            (self.projection_version, cycle["site_id"], cycle["cycle_id"]),
        )
        connection.execute(
            f"INSERT INTO traffic_projection_cycles ({','.join(names)}) VALUES ({','.join('?' for _ in names)})",
            values,
        )
        if projected.metric_facts_present:
            ap_names = (
                "projection_version site_id cycle_id ap_mac historical_name partial overview_ok "
                "wired_uplink_ok lan_traffic_ok radios_ok wired_observed_at lan_observed_at "
                "wired_download_mbps wired_upload_mbps wired_download_reason wired_upload_reason "
                "lan_download_mbps lan_upload_mbps lan_download_reason lan_upload_reason projected_at"
            ).split()
            connection.executemany(
                f"INSERT INTO traffic_projection_ap_cycles ({','.join(ap_names)}) VALUES ({','.join('?' for _ in ap_names)})",
                [tuple([self.projection_version, cycle["site_id"], cycle["cycle_id"]]
                 + [row.get(name) for name in ap_names[3:-1]] + [now_utc])
                 for row in projected.ap_rows],
            )
        semantic_changed = previous is None or previous[0] != projected.source_semantic_fingerprint
        connection.execute(
            """UPDATE traffic_projection_site_state
               SET projection_revision=projection_revision+?,
                   projection_head_utc=CASE
                     WHEN projection_head_utc IS NULL
                       OR projection_head_utc<?
                       OR (projection_head_utc=? AND projection_head_cycle_id<?)
                     THEN ? ELSE projection_head_utc END,
                   projection_head_cycle_id=CASE
                     WHEN projection_head_utc IS NULL
                       OR projection_head_utc<?
                       OR (projection_head_utc=? AND projection_head_cycle_id<?)
                     THEN ? ELSE projection_head_cycle_id END,
                   fast_checkpoint_started_at=?,fast_checkpoint_cycle_id=?,
                   last_incremental_progress_at=?,last_success_at=?,last_error_category=NULL
               WHERE projection_version=? AND site_id=?""",
            (int(semantic_changed), cycle["started_at"], cycle["started_at"],
             cycle["cycle_id"], cycle["started_at"], cycle["started_at"],
             cycle["started_at"], cycle["cycle_id"], cycle["cycle_id"],
             cycle["started_at"], cycle["cycle_id"],
             now_utc, now_utc, self.projection_version, cycle["site_id"]),
        )
        return semantic_changed

    def update_site(self, site_id: str, **fields: Any) -> None:
        allowed = {
            "status", "fast_checkpoint_started_at", "fast_checkpoint_cycle_id",
            "source_head_utc", "source_head_cycle_id", "last_incremental_scan_at",
            "last_incremental_progress_at", "reconcile_cursor_started_at",
            "reconcile_cursor_cycle_id", "reconcile_sweep_started_at",
            "reconcile_sweep_source_head_utc", "reconcile_sweep_source_head_cycle_id",
            "reconcile_sweep_from_utc", "last_full_reconcile_completed_at",
            "last_full_reconcile_source_head_utc", "last_full_reconcile_source_head_cycle_id",
            "last_deep_audit_at", "backlog_cycle_count", "last_error_category",
            "available_from_utc", "available_through_utc", "source_watermark_utc",
            "source_boundary_proof_at", "source_boundary_proof_head_utc",
            "source_boundary_proof_head_cycle_id",
        }
        if not fields or not set(fields) <= allowed:
            raise ValueError("invalid projection Site state update")
        with self.write_connection() as connection:
            sql = ",".join(f"{name}=?" for name in fields)
            connection.execute(
                f"UPDATE traffic_projection_site_state SET {sql} WHERE projection_version=? AND site_id=?",
                (*fields.values(), self.projection_version, site_id),
            )
            connection.commit()

    def begin_site_repair(self, site_id: str) -> None:
        """Durably invalidate every projection proof before deleting Site facts."""
        with self.write_connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            changed = connection.execute(
                """UPDATE traffic_projection_site_state
                   SET status='rebuilding',projection_revision=projection_revision+1,
                       fast_checkpoint_started_at=NULL,fast_checkpoint_cycle_id=NULL,
                       projection_head_utc=NULL,projection_head_cycle_id=NULL,
                       last_incremental_scan_at=NULL,last_incremental_progress_at=NULL,
                       reconcile_cursor_started_at=NULL,reconcile_cursor_cycle_id=NULL,
                       reconcile_sweep_started_at=NULL,
                       reconcile_sweep_source_head_utc=NULL,
                       reconcile_sweep_source_head_cycle_id=NULL,
                       reconcile_sweep_from_utc=NULL,
                       last_full_reconcile_completed_at=NULL,
                       last_full_reconcile_source_head_utc=NULL,
                        last_full_reconcile_source_head_cycle_id=NULL,
                        last_deep_audit_at=NULL,last_success_at=NULL,
                        backlog_cycle_count=NULL,last_error_category='repair_delete',
                        available_from_utc=NULL,available_through_utc=NULL,
                        source_watermark_utc=NULL,source_boundary_proof_at=NULL,
                        source_boundary_proof_head_utc=NULL,
                        source_boundary_proof_head_cycle_id=NULL
                   WHERE projection_version=? AND site_id=?""",
                (self.projection_version, site_id),
            ).rowcount
            if changed != 1:
                connection.rollback()
                raise TrafficProjectionStorageCorrupt(
                    "Traffic projection Site repair cannot start"
                )
            connection.commit()

    def delete_site_cycles(self, site_id: str, *, limit: int = 100) -> int:
        """Delete one bounded repair chunk for one Site/version."""
        bounded = max(1, min(int(limit), MAX_BULK_CYCLES_PER_TRANSACTION))
        with self.write_connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cycle_ids = tuple(
                str(row[0])
                for row in connection.execute(
                    """SELECT cycle_id FROM traffic_projection_cycles
                       WHERE projection_version=? AND site_id=?
                       ORDER BY cycle_id LIMIT ?""",
                    (self.projection_version, site_id, bounded),
                )
            )
            if cycle_ids:
                connection.executemany(
                    """DELETE FROM traffic_projection_cycles
                       WHERE projection_version=? AND site_id=? AND cycle_id=?""",
                    (
                        (self.projection_version, site_id, cycle_id)
                        for cycle_id in cycle_ids
                    ),
                )
            connection.commit()
            return len(cycle_ids)

    def site_state(self, site_id: str, connection: sqlite3.Connection | None = None) -> Mapping[str, Any] | None:
        if connection is not None:
            row = connection.execute(
                "SELECT * FROM traffic_projection_site_state WHERE projection_version=? AND site_id=?",
                (self.projection_version, site_id),
            ).fetchone()
            return None if row is None else dict(row)
        with self.read_connection() as read:
            return self.site_state(site_id, read)

    def delete_before(
        self, site_id: str, before_utc: str, *, limit: int = 100
    ) -> int:
        with self.write_connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            keys = tuple(connection.execute(
                """SELECT cycle_id FROM traffic_projection_cycles
                   WHERE projection_version=? AND site_id=?
                     AND source_state IN ('completed','abandoned')
                     AND source_started_at<?
                     AND (source_finished_at IS NULL OR source_finished_at<?)
                     AND (source_abandoned_at IS NULL OR source_abandoned_at<?)
                   ORDER BY source_started_at,cycle_id LIMIT ?""",
                (
                    self.projection_version,
                    site_id,
                    before_utc,
                    before_utc,
                    before_utc,
                    max(1, min(int(limit), MAX_BULK_CYCLES_PER_TRANSACTION)),
                ),
            ))
            connection.executemany(
                """DELETE FROM traffic_projection_cycles
                   WHERE projection_version=? AND site_id=? AND cycle_id=?""",
                (
                    (self.projection_version, site_id, str(row[0]))
                    for row in keys
                ),
            )
            connection.commit()
            return len(keys)

    def checkpoint_passive(self) -> tuple[int, int, int]:
        with self.write_connection() as connection:
            row = connection.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
            return tuple(int(value) for value in row)

    def secure_files(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            path = Path(str(self.db_path) + suffix)
            if path.exists():
                try:
                    os.chmod(path, 0o600)
                except OSError:
                    pass

    def _connect(self, query_only: bool) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=self.busy_timeout_ms / 1000)
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout={self.busy_timeout_ms}")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute(f"PRAGMA wal_autocheckpoint={WAL_AUTOCHECKPOINT_PAGES}")
        connection.execute(f"PRAGMA journal_size_limit={JOURNAL_SIZE_LIMIT_BYTES}")
        if query_only:
            connection.execute("PRAGMA query_only=ON")
        return connection

    @staticmethod
    def _tables(connection: sqlite3.Connection) -> set[str]:
        return {str(row[0]) for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}

    @staticmethod
    def _validate(connection: sqlite3.Connection, *, deep: bool) -> None:
        if int(connection.execute("PRAGMA user_version").fetchone()[0]) != SCHEMA_VERSION:
            raise TrafficProjectionStorageCorrupt("Traffic projection schema is incompatible")
        if not REQUIRED_TABLES <= TrafficProjectionRepository._tables(connection):
            raise TrafficProjectionStorageCorrupt("Traffic projection schema is incomplete")
        for table, expected in REQUIRED_COLUMNS.items():
            actual = tuple(
                str(row[1]) for row in connection.execute(
                    f"PRAGMA table_info({table})"
                )
            )
            if actual != tuple(expected):
                raise TrafficProjectionStorageCorrupt(
                    "Traffic projection schema signature is incompatible"
                )
        for index, expected in REQUIRED_INDEX_COLUMNS.items():
            actual = tuple(
                str(row[2]) for row in connection.execute(
                    f"PRAGMA index_info({index})"
                )
            )
            if actual != expected:
                raise TrafficProjectionStorageCorrupt(
                    "Traffic projection index signature is incompatible"
                )
        indexes = {
            str(row[0]) for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
        }
        if not REQUIRED_EXPRESSION_INDEXES <= indexes:
            raise TrafficProjectionStorageCorrupt(
                "Traffic projection lifecycle index is incompatible"
            )
        if deep:
            if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise TrafficProjectionStorageCorrupt(
                    "Traffic projection foreign-key integrity is unavailable"
                )
            if str(connection.execute("PRAGMA quick_check").fetchone()[0]).lower() != "ok":
                raise TrafficProjectionStorageCorrupt("Traffic projection database is corrupt")
