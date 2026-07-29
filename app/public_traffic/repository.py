"""SQLite persistence and atomic aggregation for public traffic."""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import closing
from pathlib import Path
from typing import Callable

from .models import (
    INT64_MAX,
    AggregateOverflowError,
    BackfillIncompleteError,
    ProcessOutcome,
    ReaderState,
    ResetSummary,
    TrafficEvent,
    TrafficSnapshot,
)


SCHEMA_VERSION = 2
DEFAULT_BUSY_TIMEOUT_MS = 250


class PublicTrafficRepository:
    def __init__(
        self,
        db_path: str,
        *,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    ):
        self.db_path = Path(db_path)
        self.busy_timeout_ms = max(1, int(busy_timeout_ms))

    def migrate(self, now_utc: str) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            version = connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0]
            if version > SCHEMA_VERSION:
                raise RuntimeError(
                    "Public traffic database schema is newer "
                    "than this application"
                )
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS traffic_daily (
                    local_date TEXT NOT NULL,
                    ssid TEXT NOT NULL,
                    traffic_bytes INTEGER NOT NULL DEFAULT 0,
                    completed_sessions INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (local_date, ssid),
                    CHECK (traffic_bytes >= 0),
                    CHECK (completed_sessions >= 0)
                );

                CREATE TABLE IF NOT EXISTS processed_events (
                    normalized_event_id TEXT PRIMARY KEY,
                    ssid TEXT,
                    event_type TEXT NOT NULL,
                    event_local_date TEXT,
                    event_traffic_bytes INTEGER,
                    counted INTEGER NOT NULL,
                    skip_reason TEXT,
                    source_identity TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    source_offset_start INTEGER NOT NULL,
                    source_offset_end INTEGER NOT NULL,
                    processed_at TEXT NOT NULL,
                    CHECK (counted IN (0, 1))
                );

                CREATE TABLE IF NOT EXISTS reader_state (
                    source_identity TEXT PRIMARY KEY,
                    source_path TEXT NOT NULL,
                    source_offset INTEGER NOT NULL DEFAULT 0,
                    source_checkpoint TEXT,
                    last_observed_size INTEGER,
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

                CREATE TABLE IF NOT EXISTS counter_state (
                    singleton_id INTEGER PRIMARY KEY
                        CHECK (singleton_id = 1),
                    initial_backfill_completed INTEGER NOT NULL DEFAULT 0,
                    initial_backfill_completed_at TEXT,
                    updated_at TEXT NOT NULL,
                    CHECK (initial_backfill_completed IN (0, 1))
                );

                CREATE TABLE IF NOT EXISTS counter_resets (
                    reset_id TEXT PRIMARY KEY,
                    reset_scope TEXT NOT NULL,
                    ssid TEXT,
                    reset_at TEXT NOT NULL,
                    previous_today_bytes INTEGER,
                    previous_total_bytes INTEGER,
                    previous_sessions_today INTEGER,
                    previous_sessions_total INTEGER,
                    affected_ssids INTEGER,
                    CHECK (reset_scope IN ('ssid', 'all'))
                );

                CREATE INDEX IF NOT EXISTS
                    idx_traffic_daily_ssid
                    ON traffic_daily(ssid);

                CREATE INDEX IF NOT EXISTS
                    idx_processed_events_source
                    ON processed_events(source_identity);
                """
            )
            reader_state_columns = {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(reader_state)"
                ).fetchall()
            }
            if "source_checkpoint" not in reader_state_columns:
                connection.execute(
                    """
                    ALTER TABLE reader_state
                    ADD COLUMN source_checkpoint TEXT
                    """
                )
            connection.execute(
                """
                INSERT INTO counter_state (
                    singleton_id,
                    initial_backfill_completed,
                    initial_backfill_completed_at,
                    updated_at
                )
                VALUES (1, 0, NULL, ?)
                ON CONFLICT(singleton_id) DO NOTHING
                """,
                (now_utc,),
            )
            connection.execute(
                f"PRAGMA user_version={SCHEMA_VERSION}"
            )
            connection.commit()

    def initial_backfill_completed(self) -> bool:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT initial_backfill_completed
                FROM counter_state
                WHERE singleton_id = 1
                """
            ).fetchone()
        return bool(row and row[0] == 1)

    def mark_initial_backfill_completed(self, now_utc: str) -> None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE counter_state
                SET initial_backfill_completed = 1,
                    initial_backfill_completed_at = ?,
                    updated_at = ?
                WHERE singleton_id = 1
                """,
                (now_utc, now_utc),
            )
            connection.commit()

    def get_reader_states(self) -> dict[str, ReaderState]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT
                    source_identity,
                    source_path,
                    source_offset,
                    source_checkpoint,
                    last_observed_size,
                    retired_completed,
                    missing_warning_emitted
                FROM reader_state
                """
            ).fetchall()
        return {
            row[0]: ReaderState(
                source_identity=row[0],
                source_path=row[1],
                source_offset=int(row[2]),
                source_checkpoint=row[3],
                last_observed_size=(
                    None if row[4] is None else int(row[4])
                ),
                retired_completed=bool(row[5]),
                missing_warning_emitted=bool(row[6]),
            )
            for row in rows
        }

    def advance_source(
        self,
        *,
        source_identity: str,
        source_path: str,
        offset_end: int,
        observed_size: int,
        now_utc: str,
        source_checkpoint: str | None,
    ) -> None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._upsert_reader_state(
                connection,
                source_identity=source_identity,
                source_path=source_path,
                source_offset=offset_end,
                source_checkpoint=source_checkpoint,
                last_observed_size=observed_size,
                retired_completed=False,
                now_utc=now_utc,
            )
            connection.commit()

    def process_offline_event(
        self,
        *,
        event: TrafficEvent,
        source_identity: str,
        source_path: str,
        offset_start: int,
        offset_end: int,
        observed_size: int,
        processed_at: str,
        source_checkpoint: str | None = None,
    ) -> ProcessOutcome:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            duplicate = connection.execute(
                """
                SELECT 1
                FROM processed_events
                WHERE normalized_event_id = ?
                """,
                (event.normalized_event_id,),
            ).fetchone()
            if duplicate is not None:
                self._upsert_reader_state(
                    connection,
                    source_identity=source_identity,
                    source_path=source_path,
                    source_offset=offset_end,
                    source_checkpoint=source_checkpoint,
                    last_observed_size=observed_size,
                    retired_completed=False,
                    now_utc=processed_at,
                )
                connection.commit()
                return ProcessOutcome(
                    duplicate=True,
                    counted=False,
                    skip_reason="duplicate",
                )

            counted = False
            skip_reason = event.skip_reason
            if event.valid:
                if (
                    event.ssid is None
                    or event.local_date is None
                    or event.traffic_bytes is None
                ):
                    raise ValueError("valid event fields are required")
                if self._would_overflow(connection, event):
                    skip_reason = "aggregate_overflow"
                else:
                    self._add_to_daily(
                        connection,
                        event=event,
                        processed_at=processed_at,
                    )
                    counted = True

            connection.execute(
                """
                INSERT INTO processed_events (
                    normalized_event_id,
                    ssid,
                    event_type,
                    event_local_date,
                    event_traffic_bytes,
                    counted,
                    skip_reason,
                    source_identity,
                    source_path,
                    source_offset_start,
                    source_offset_end,
                    processed_at
                )
                VALUES (?, ?, 'omada.client_offline', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.normalized_event_id,
                    event.ssid,
                    event.local_date,
                    event.traffic_bytes,
                    1 if counted else 0,
                    skip_reason,
                    source_identity,
                    source_path,
                    offset_start,
                    offset_end,
                    processed_at,
                ),
            )
            self._upsert_reader_state(
                connection,
                source_identity=source_identity,
                source_path=source_path,
                source_offset=offset_end,
                source_checkpoint=source_checkpoint,
                last_observed_size=observed_size,
                retired_completed=False,
                now_utc=processed_at,
            )
            connection.commit()
            return ProcessOutcome(
                duplicate=False,
                counted=counted,
                skip_reason=skip_reason,
            )

    def observe_source(
        self,
        *,
        source_identity: str,
        source_path: str,
        source_offset: int,
        observed_size: int,
        retired_completed: bool,
        now_utc: str,
        source_checkpoint: str | None,
    ) -> None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._upsert_reader_state(
                connection,
                source_identity=source_identity,
                source_path=source_path,
                source_offset=source_offset,
                source_checkpoint=source_checkpoint,
                last_observed_size=observed_size,
                retired_completed=retired_completed,
                now_utc=now_utc,
            )
            connection.commit()

    def reset_source_after_truncate(
        self,
        *,
        source_identity: str,
        source_path: str,
        observed_size: int,
        now_utc: str,
        source_checkpoint: str | None = None,
    ) -> None:
        self.observe_source(
            source_identity=source_identity,
            source_path=source_path,
            source_offset=0,
            source_checkpoint=source_checkpoint,
            observed_size=observed_size,
            retired_completed=False,
            now_utc=now_utc,
        )

    def mark_missing_warning_emitted(
        self,
        source_identity: str,
        now_utc: str,
    ) -> None:
        with closing(self._connect()) as connection:
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

    def delete_reader_state(self, source_identity: str) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                DELETE FROM reader_state
                WHERE source_identity = ?
                """,
                (source_identity,),
            )
            connection.commit()

    def reset_source_after_reappearance(
        self,
        *,
        source_identity: str,
        source_path: str,
        observed_size: int,
        now_utc: str,
    ) -> None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE reader_state
                SET source_path = ?,
                    source_offset = 0,
                    source_checkpoint = NULL,
                    last_observed_size = ?,
                    retired_completed = 0,
                    missing_warning_emitted = 0,
                    updated_at = ?
                WHERE source_identity = ?
                """,
                (
                    source_path,
                    observed_size,
                    now_utc,
                    source_identity,
                ),
            )
            connection.commit()

    def get_snapshot(
        self,
        *,
        ssid: str,
        local_date: str,
    ) -> TrafficSnapshot:
        with closing(self._connect()) as connection:
            completed = connection.execute(
                """
                SELECT initial_backfill_completed
                FROM counter_state
                WHERE singleton_id = 1
                """
            ).fetchone()
            if completed is None or completed[0] != 1:
                return TrafficSnapshot(available=False, ssid=ssid)
            rows = connection.execute(
                """
                SELECT
                    local_date,
                    traffic_bytes,
                    completed_sessions,
                    updated_at
                FROM traffic_daily
                WHERE ssid = ?
                ORDER BY local_date
                """,
                (ssid,),
            ).fetchall()

        today_bytes = 0
        today_sessions = 0
        total_bytes = 0
        total_sessions = 0
        updated_at = None
        for day, traffic, sessions, row_updated_at in rows:
            traffic_value = _strict_db_integer(traffic)
            session_value = _strict_db_integer(sessions)
            total_bytes = _safe_add(total_bytes, traffic_value)
            total_sessions = _safe_add(total_sessions, session_value)
            if day == local_date:
                today_bytes = traffic_value
                today_sessions = session_value
            if updated_at is None or row_updated_at > updated_at:
                updated_at = row_updated_at
        return TrafficSnapshot(
            available=True,
            ssid=ssid,
            today_bytes=today_bytes,
            total_bytes=total_bytes,
            completed_sessions_today=today_sessions,
            completed_sessions_total=total_sessions,
            updated_at=updated_at,
        )

    def get_all_ssid_snapshots(
        self,
        local_date: str,
    ) -> list[TrafficSnapshot]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT
                    ssid,
                    local_date,
                    traffic_bytes,
                    completed_sessions,
                    updated_at
                FROM traffic_daily
                ORDER BY ssid, local_date
                """
            ).fetchall()
        grouped: dict[str, list[tuple]] = {}
        for ssid, day, traffic, sessions, updated_at in rows:
            grouped.setdefault(ssid, []).append((
                day,
                traffic,
                sessions,
                updated_at,
            ))
        return [
            _snapshot_from_rows(ssid, local_date, ssid_rows)
            for ssid, ssid_rows in grouped.items()
        ]

    def reset(
        self,
        *,
        ssid: str | None,
        local_date: str,
        reset_at: str,
        reset_id: str | None = None,
        before_commit: Callable[[], None] | None = None,
    ) -> ResetSummary:
        scope = "all" if ssid is None else "ssid"
        reset_id = reset_id or str(uuid.uuid4())
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            completed = connection.execute(
                """
                SELECT initial_backfill_completed
                FROM counter_state
                WHERE singleton_id = 1
                """
            ).fetchone()
            if completed is None or completed[0] != 1:
                connection.rollback()
                raise BackfillIncompleteError(
                    "Initial public traffic backfill is not complete"
                )

            if ssid is None:
                affected = connection.execute(
                    "SELECT COUNT(DISTINCT ssid) FROM traffic_daily"
                ).fetchone()[0]
                connection.execute("DELETE FROM traffic_daily")
                summary = ResetSummary(
                    reset_id=reset_id,
                    scope=scope,
                    ssid=None,
                    reset_at=reset_at,
                    previous_today_bytes=None,
                    previous_total_bytes=None,
                    previous_sessions_today=None,
                    previous_sessions_total=None,
                    affected_ssids=int(affected),
                )
            else:
                rows = connection.execute(
                    """
                    SELECT
                        local_date,
                        traffic_bytes,
                        completed_sessions,
                        updated_at
                    FROM traffic_daily
                    WHERE ssid = ?
                    ORDER BY local_date
                    """,
                    (ssid,),
                ).fetchall()
                snapshot = _snapshot_from_rows(ssid, local_date, rows)
                connection.execute(
                    "DELETE FROM traffic_daily WHERE ssid = ?",
                    (ssid,),
                )
                summary = ResetSummary(
                    reset_id=reset_id,
                    scope=scope,
                    ssid=ssid,
                    reset_at=reset_at,
                    previous_today_bytes=snapshot.today_bytes,
                    previous_total_bytes=snapshot.total_bytes,
                    previous_sessions_today=(
                        snapshot.completed_sessions_today
                    ),
                    previous_sessions_total=(
                        snapshot.completed_sessions_total
                    ),
                    affected_ssids=None,
                )

            connection.execute(
                """
                INSERT INTO counter_resets (
                    reset_id,
                    reset_scope,
                    ssid,
                    reset_at,
                    previous_today_bytes,
                    previous_total_bytes,
                    previous_sessions_today,
                    previous_sessions_total,
                    affected_ssids
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    summary.reset_id,
                    summary.scope,
                    summary.ssid,
                    summary.reset_at,
                    summary.previous_today_bytes,
                    summary.previous_total_bytes,
                    summary.previous_sessions_today,
                    summary.previous_sessions_total,
                    summary.affected_ssids,
                ),
            )
            if before_commit is not None:
                before_commit()
            connection.commit()
            return summary

    def _would_overflow(
        self,
        connection: sqlite3.Connection,
        event: TrafficEvent,
    ) -> bool:
        day_row = connection.execute(
            """
            SELECT traffic_bytes, completed_sessions
            FROM traffic_daily
            WHERE local_date = ? AND ssid = ?
            """,
            (event.local_date, event.ssid),
        ).fetchone()
        daily_traffic = 0 if day_row is None else int(day_row[0])
        daily_sessions = 0 if day_row is None else int(day_row[1])
        rows = connection.execute(
            """
            SELECT traffic_bytes, completed_sessions
            FROM traffic_daily
            WHERE ssid = ?
            """,
            (event.ssid,),
        ).fetchall()
        total_traffic = 0
        total_sessions = 0
        for traffic, sessions in rows:
            total_traffic = _safe_add(
                total_traffic,
                _strict_db_integer(traffic),
            )
            total_sessions = _safe_add(
                total_sessions,
                _strict_db_integer(sessions),
            )
        value = event.traffic_bytes
        assert value is not None
        return any((
            daily_traffic > INT64_MAX - value,
            total_traffic > INT64_MAX - value,
            daily_sessions >= INT64_MAX,
            total_sessions >= INT64_MAX,
        ))

    @staticmethod
    def _add_to_daily(
        connection: sqlite3.Connection,
        *,
        event: TrafficEvent,
        processed_at: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO traffic_daily (
                local_date,
                ssid,
                traffic_bytes,
                completed_sessions,
                updated_at
            )
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(local_date, ssid) DO UPDATE SET
                traffic_bytes = traffic_bytes + excluded.traffic_bytes,
                completed_sessions = completed_sessions + 1,
                updated_at = excluded.updated_at
            """,
            (
                event.local_date,
                event.ssid,
                event.traffic_bytes,
                processed_at,
            ),
        )

    @staticmethod
    def _upsert_reader_state(
        connection: sqlite3.Connection,
        *,
        source_identity: str,
        source_path: str,
        source_offset: int,
        source_checkpoint: str | None,
        last_observed_size: int,
        retired_completed: bool,
        now_utc: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO reader_state (
                source_identity,
                source_path,
                source_offset,
                source_checkpoint,
                last_observed_size,
                retired_completed,
                missing_warning_emitted,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 0, ?)
            ON CONFLICT(source_identity) DO UPDATE SET
                source_path = excluded.source_path,
                source_offset = excluded.source_offset,
                source_checkpoint = excluded.source_checkpoint,
                last_observed_size = excluded.last_observed_size,
                retired_completed = excluded.retired_completed,
                updated_at = excluded.updated_at
            """,
            (
                source_identity,
                source_path,
                source_offset,
                source_checkpoint,
                last_observed_size,
                1 if retired_completed else 0,
                now_utc,
            ),
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.db_path,
            timeout=self.busy_timeout_ms / 1000,
        )
        try:
            connection.execute(
                f"PRAGMA busy_timeout={self.busy_timeout_ms}"
            )
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
        except Exception:
            connection.close()
            raise
        return connection


def _strict_db_integer(value: object) -> int:
    if type(value) is not int or not 0 <= value <= INT64_MAX:
        raise AggregateOverflowError(
            "Stored public traffic aggregate is invalid"
        )
    return value


def _safe_add(current: int, value: int) -> int:
    if current > INT64_MAX - value:
        raise AggregateOverflowError(
            "Stored public traffic aggregate exceeds INT64"
        )
    return current + value


def _snapshot_from_rows(
    ssid: str,
    local_date: str,
    rows: list[tuple],
) -> TrafficSnapshot:
    today_bytes = 0
    today_sessions = 0
    total_bytes = 0
    total_sessions = 0
    updated_at = None
    for day, traffic, sessions, row_updated_at in rows:
        traffic_value = _strict_db_integer(traffic)
        session_value = _strict_db_integer(sessions)
        total_bytes = _safe_add(total_bytes, traffic_value)
        total_sessions = _safe_add(total_sessions, session_value)
        if day == local_date:
            today_bytes = _safe_add(today_bytes, traffic_value)
            today_sessions = _safe_add(today_sessions, session_value)
        if updated_at is None or row_updated_at > updated_at:
            updated_at = row_updated_at
    return TrafficSnapshot(
        available=True,
        ssid=ssid,
        today_bytes=today_bytes,
        total_bytes=total_bytes,
        completed_sessions_today=today_sessions,
        completed_sessions_total=total_sessions,
        updated_at=updated_at,
    )
