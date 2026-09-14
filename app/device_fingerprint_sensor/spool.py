"""Bounded DELETE-journal SQLite transport spool."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from app.device_fingerprint.validation import format_utc

from .models import NormalizedEvent, SensorSpoolError

UTC = timezone.utc
SCHEMA_VERSION = 1
MAX_TRANSACTION_ROWS = 100


class SensorSpool:
    def __init__(self, path: str, *, total_budget_bytes: int, main_db_max_bytes: int,
                 max_events: int, write_headroom_bytes: int = 0, now=None) -> None:
        self.path = Path(path)
        self.total_budget_bytes = total_budget_bytes
        self.main_db_max_bytes = main_db_max_bytes
        self.max_events = max_events
        self.write_headroom_bytes = write_headroom_bytes
        self.now = now or (lambda: datetime.now(UTC))
        self.connection: sqlite3.Connection | None = None
        self.capacity_blocked = False
        self.stale_dropped = 0
        self.evicted = 0
        self._lock = threading.RLock()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
        connection = sqlite3.connect(str(self.path), timeout=0.5, isolation_level=None, check_same_thread=False)
        try:
            connection.execute("PRAGMA journal_mode=DELETE")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA busy_timeout=500")
            page_size = int(connection.execute("PRAGMA page_size").fetchone()[0])
            connection.execute(f"PRAGMA max_page_count={max(1, self.main_db_max_bytes // page_size)}")
            connection.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS sensor_spool (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    endpoint TEXT NOT NULL CHECK(endpoint IN ('evidence','source_health')),
                    event_id TEXT NOT NULL UNIQUE,
                    source_kind TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_sensor_spool_endpoint_sequence
                    ON sensor_spool(endpoint, sequence);
                CREATE INDEX IF NOT EXISTS idx_sensor_spool_observed
                    ON sensor_spool(observed_at, sequence);
                PRAGMA user_version=1;
                COMMIT;
            """)
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            quick = connection.execute("PRAGMA quick_check").fetchone()[0]
            if version != SCHEMA_VERSION or quick != "ok":
                raise SensorSpoolError("spool schema is unavailable")
            os.chmod(self.path, 0o640)
        except Exception:
            connection.close()
            raise
        self.connection = connection

    def enqueue(self, events: Iterable[NormalizedEvent]) -> int:
        with self._lock:
            return self._enqueue(events)

    def _enqueue(self, events: Iterable[NormalizedEvent]) -> int:
        values = list(events)
        if not values:
            return 0
        if len(values) > MAX_TRANSACTION_ROWS:
            raise SensorSpoolError("spool transaction is too large")
        self.purge_stale()
        threshold = format_utc(self.now() - timedelta(seconds=86400))
        fresh = [event for event in values if event.observed_at >= threshold]
        self.stale_dropped += len(values) - len(fresh)
        values = fresh
        if not values:
            return 0
        self._make_room(len(values))
        if self.capacity_blocked:
            return 0
        now = format_utc(self.now())
        rows = [(
            event.endpoint, event.event_id, event.source_kind, event.observed_at,
            json.dumps(event.document, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")), now,
        ) for event in values]
        connection = self._connection()
        before = int(connection.execute("SELECT COUNT(*) FROM sensor_spool").fetchone()[0])
        try:
            with connection:
                connection.executemany(
                    "INSERT OR IGNORE INTO sensor_spool(endpoint,event_id,source_kind,observed_at,payload_json,created_at) VALUES(?,?,?,?,?,?)",
                    rows,
                )
        except sqlite3.Error as exc:
            raise SensorSpoolError("spool enqueue failed") from exc
        if self.physical_bytes() > self.total_budget_bytes:
            self.capacity_blocked = True
        after = int(connection.execute("SELECT COUNT(*) FROM sensor_spool").fetchone()[0])
        return after - before

    def batch(self, limit: int) -> tuple[str, list[tuple[int, dict[str, object]]]] | None:
        with self._lock:
            while self._purge_stale() == MAX_TRANSACTION_ROWS:
                pass
            self._refresh_capacity_blocked()
            threshold = format_utc(self.now() - timedelta(seconds=86400))
            return self._batch(limit, threshold)

    def _batch(self, limit: int, threshold: str) -> tuple[str, list[tuple[int, dict[str, object]]]] | None:
        connection = self._connection()
        first = connection.execute(
            "SELECT endpoint FROM sensor_spool WHERE observed_at>=? ORDER BY sequence LIMIT 1",
            (threshold,),
        ).fetchone()
        if first is None:
            return None
        endpoint = str(first[0])
        rows = connection.execute(
            "SELECT sequence,payload_json FROM sensor_spool WHERE endpoint=? AND observed_at>=? ORDER BY sequence LIMIT ?",
            (endpoint, threshold, min(limit, MAX_TRANSACTION_ROWS)),
        ).fetchall()
        return endpoint, [(int(row[0]), json.loads(row[1])) for row in rows]

    def acknowledge(self, sequences: Iterable[int]) -> int:
        with self._lock:
            return self._acknowledge(sequences)

    def _acknowledge(self, sequences: Iterable[int]) -> int:
        values = list(sequences)
        if not values or len(values) > MAX_TRANSACTION_ROWS:
            return 0
        connection = self._connection()
        marks = ",".join("?" for _ in values)
        with connection:
            cursor = connection.execute(f"DELETE FROM sensor_spool WHERE sequence IN ({marks})", values)
        self._refresh_capacity_blocked()
        return int(cursor.rowcount)

    def purge_stale(self) -> int:
        with self._lock:
            return self._purge_stale()

    def _purge_stale(self) -> int:
        threshold = format_utc(self.now() - timedelta(seconds=86400))
        connection = self._connection()
        with connection:
            cursor = connection.execute(
                "DELETE FROM sensor_spool WHERE sequence IN (SELECT sequence FROM sensor_spool WHERE observed_at < ? ORDER BY observed_at,sequence LIMIT 100)",
                (threshold,),
            )
        self.stale_dropped += int(cursor.rowcount)
        self._refresh_capacity_blocked()
        return int(cursor.rowcount)

    def _make_room(self, incoming: int) -> None:
        connection = self._connection()
        count = int(connection.execute("SELECT COUNT(*) FROM sensor_spool").fetchone()[0])
        needed = max(0, count + incoming - self.max_events)
        if needed:
            amount = min(needed, MAX_TRANSACTION_ROWS)
            with connection:
                cursor = connection.execute(
                    "DELETE FROM sensor_spool WHERE sequence IN (SELECT sequence FROM sensor_spool WHERE endpoint='evidence' ORDER BY sequence LIMIT ?)",
                    (amount,),
                )
            self.evicted += int(cursor.rowcount)
            if cursor.rowcount < needed:
                self.capacity_blocked = True
        if self.physical_bytes() + self.write_headroom_bytes > self.total_budget_bytes:
            with connection:
                cursor = connection.execute(
                    "DELETE FROM sensor_spool WHERE sequence IN (SELECT sequence FROM sensor_spool WHERE endpoint='evidence' ORDER BY sequence LIMIT 100)"
                )
            self.evicted += int(cursor.rowcount)
            if self.physical_bytes() + self.write_headroom_bytes > self.total_budget_bytes:
                self.capacity_blocked = True
        self._refresh_capacity_blocked(incoming)

    def _refresh_capacity_blocked(self, incoming: int = 0) -> None:
        if not self.capacity_blocked:
            return
        count = int(self._connection().execute("SELECT COUNT(*) FROM sensor_spool").fetchone()[0])
        if (
            count + incoming <= self.max_events
            and self.physical_bytes() + self.write_headroom_bytes <= self.total_budget_bytes
        ):
            self.capacity_blocked = False

    def physical_bytes(self) -> int:
        return sum(path.stat().st_size for path in (self.path, Path(str(self.path) + "-journal")) if path.exists())

    def metrics(self) -> dict[str, int | bool]:
        with self._lock:
            connection = self._connection()
            row = connection.execute("SELECT COUNT(*),MIN(observed_at) FROM sensor_spool").fetchone()
            oldest_age = 0
            if row[1]:
                parsed = datetime.strptime(row[1], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
                oldest_age = max(0, int((self.now() - parsed).total_seconds()))
            return {"rows": int(row[0]), "spool_bytes": self.physical_bytes(), "oldest_spool_age": oldest_age, "capacity_blocked": self.capacity_blocked}

    def close(self) -> None:
        with self._lock:
            if self.connection is not None:
                self.connection.close()
                self.connection = None

    def _connection(self) -> sqlite3.Connection:
        if self.connection is None:
            raise SensorSpoolError("spool is closed")
        return self.connection
