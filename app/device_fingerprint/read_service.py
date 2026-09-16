"""Bounded read-only Python API for normalized fingerprint evidence."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from .models import DeviceFingerprintStorageCorrupt, DeviceFingerprintValidationError
from .repository import DeviceFingerprintRepository, open_read_only
from .schema import MAX_INGEST_SEQUENCE
from .validation import parse_utc, validate_mac, validate_machine_id, validate_site_id, validate_source_kind, validate_uuid


@dataclass(frozen=True, slots=True)
class IngestWatermark:
    database_generation_id: str
    max_committed_ingest_sequence: int


class DeviceFingerprintSnapshotReadSession:
    """One immutable Task-01 row universe on a single SQLite read transaction."""

    __slots__ = ("_connection", "_watermark", "_closed")

    def __init__(self, connection: sqlite3.Connection, watermark: IngestWatermark) -> None:
        self._connection = connection
        self._watermark = watermark
        self._closed = False

    @property
    def watermark(self) -> IngestWatermark:
        self._require_open()
        return self._watermark

    def __enter__(self) -> DeviceFingerprintSnapshotReadSession:
        self._require_open()
        return self

    def __exit__(self, _exc_type: Any, _exc: Any, _traceback: Any) -> None:
        self.close()

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            try:
                self._connection.rollback()
            finally:
                self._connection.close()

    def _require_open(self) -> None:
        if self._closed:
            raise DeviceFingerprintValidationError("Fingerprint snapshot read session is closed")

    @staticmethod
    def _cursor(cursor: tuple[str, str] | None, label: str) -> tuple[str, str] | None:
        if cursor is None:
            return None
        if not isinstance(cursor, tuple) or len(cursor) != 2:
            raise DeviceFingerprintValidationError(f"{label} cursor is invalid")
        parse_utc(cursor[0])
        validate_uuid(cursor[1])
        return cursor

    @staticmethod
    def _window(from_utc: str, to_utc: str, label: str) -> None:
        if parse_utc(from_utc) >= parse_utc(to_utc):
            raise DeviceFingerprintValidationError(f"{label} read range is invalid")

    @staticmethod
    def _limit(limit: int, label: str) -> None:
        if type(limit) is not int or not 1 <= limit <= 500:
            raise DeviceFingerprintValidationError(f"{label} read limit is invalid")

    def _page(self, table: str, id_column: str, clauses: list[str],
              parameters: list[Any], limit: int) -> dict[str, Any]:
        rows = self._connection.execute(
            f"SELECT * FROM {table} WHERE " + " AND ".join(clauses)
            + f" ORDER BY observed_at,{id_column} LIMIT ?",
            (*parameters, limit + 1),
        ).fetchall()
        selected = rows[:limit]
        return {
            "items": [dict(row) for row in selected],
            "next_cursor": (
                (selected[-1]["observed_at"], selected[-1][id_column])
                if len(rows) > limit else None
            ),
        }

    def list_evidence(self, site_id: str, observed_mac: str, from_utc: str,
                      to_utc: str, *, source_kind: str | None = None,
                      producer_id: str | None = None,
                      capture_source_id: str | None = None,
                      limit: int = 100,
                      cursor: tuple[str, str] | None = None) -> dict[str, Any]:
        self._require_open()
        try:
            site = validate_site_id(site_id)
            mac = validate_mac(observed_mac)
            self._window(from_utc, to_utc, "Evidence")
            self._limit(limit, "Evidence")
            key = self._cursor(cursor, "Evidence")
            clauses = ["site_id=?", "observed_mac=?", "observed_at>=?", "observed_at<?", "ingest_sequence<=?"]
            parameters: list[Any] = [site, mac, from_utc, to_utc, self._watermark.max_committed_ingest_sequence]
            for column, value, validator in (
                ("source_kind", source_kind, validate_source_kind),
                ("producer_id", producer_id, validate_machine_id),
                ("capture_source_id", capture_source_id, validate_machine_id),
            ):
                if value is not None:
                    clauses.append(f"{column}=?")
                    parameters.append(validator(value))
            if key is not None:
                clauses.append("(observed_at>? OR (observed_at=? AND evidence_id>?))")
                parameters.extend((key[0], key[0], key[1]))
            return self._page("device_fingerprint_evidence", "evidence_id", clauses, parameters, limit)
        except BaseException:
            self.close()
            raise

    def list_source_health(self, site_id: str, producer_id: str,
                           capture_source_id: str, source_kind: str,
                           from_utc: str, to_utc: str, *, limit: int = 100,
                           cursor: tuple[str, str] | None = None) -> dict[str, Any]:
        self._require_open()
        try:
            site = validate_site_id(site_id)
            producer = validate_machine_id(producer_id)
            capture = validate_machine_id(capture_source_id)
            kind = validate_source_kind(source_kind)
            self._window(from_utc, to_utc, "Source health")
            self._limit(limit, "Source health")
            key = self._cursor(cursor, "Source health")
            clauses = [
                "site_id=?", "producer_id=?", "capture_source_id=?", "source_kind=?",
                "observed_at>=?", "observed_at<?", "ingest_sequence<=?",
            ]
            parameters: list[Any] = [
                site, producer, capture, kind, from_utc, to_utc,
                self._watermark.max_committed_ingest_sequence,
            ]
            if key is not None:
                clauses.append("(observed_at>? OR (observed_at=? AND source_health_id>?))")
                parameters.extend((key[0], key[0], key[1]))
            return self._page("device_fingerprint_source_health_events", "source_health_id", clauses, parameters, limit)
        except BaseException:
            self.close()
            raise

    def latest_source_health(self, site_id: str, producer_id: str,
                             capture_source_id: str, source_kind: str,
                             *, through_utc: str) -> dict[str, Any] | None:
        self._require_open()
        try:
            parameters = (
                validate_site_id(site_id), validate_machine_id(producer_id),
                validate_machine_id(capture_source_id), validate_source_kind(source_kind),
                through_utc, self._watermark.max_committed_ingest_sequence,
            )
            parse_utc(through_utc)
            row = self._connection.execute(
                "SELECT * FROM device_fingerprint_source_health_events "
                "WHERE site_id=? AND producer_id=? AND capture_source_id=? AND source_kind=? "
                "AND observed_at<=? AND ingest_sequence<=? "
                "ORDER BY observed_at DESC,source_health_id DESC LIMIT 1",
                parameters,
            ).fetchone()
            return dict(row) if row is not None else None
        except BaseException:
            self.close()
            raise


class DeviceFingerprintReadService:
    def __init__(self, db_path: str, *, retention_days: int) -> None:
        self.db_path = db_path
        self.retention_days = retention_days

    def open_snapshot_read(self) -> DeviceFingerprintSnapshotReadSession:
        connection = open_read_only(self.db_path)
        try:
            connection.execute("BEGIN")
            raw = DeviceFingerprintRepository.read_ingest_watermark(connection)
            generation = raw["database_generation_id"]
            sequence = raw["max_committed_ingest_sequence"]
            try:
                validate_uuid(generation)
                if uuid.UUID(generation).version != 4:
                    raise ValueError
            except (DeviceFingerprintValidationError, ValueError, TypeError) as exc:
                raise DeviceFingerprintStorageCorrupt("Fingerprint generation state is invalid") from exc
            if type(sequence) is not int or not 0 <= sequence <= MAX_INGEST_SEQUENCE:
                raise DeviceFingerprintStorageCorrupt("Fingerprint allocator state is invalid")
            return DeviceFingerprintSnapshotReadSession(connection, IngestWatermark(generation, sequence))
        except BaseException:
            try:
                connection.rollback()
            finally:
                connection.close()
            raise

    def list_evidence(self, site_id: str, observed_mac: str, from_utc: str,
                      to_utc: str, *, source_kind: str | None = None,
                      limit: int = 100, cursor: tuple[str, str] | None = None) -> dict[str, Any]:
        site = validate_site_id(site_id)
        mac = validate_mac(observed_mac)
        start, end = parse_utc(from_utc), parse_utc(to_utc)
        if start >= end or end - start > timedelta(days=self.retention_days):
            raise DeviceFingerprintValidationError("Evidence read range is invalid")
        if type(limit) is not int or not 1 <= limit <= 500:
            raise DeviceFingerprintValidationError("Evidence read limit is invalid")
        kind = validate_source_kind(source_kind) if source_kind is not None else None
        parameters: list[Any] = [site, mac, from_utc, to_utc]
        clauses = ["site_id=?", "observed_mac=?", "observed_at>=?", "observed_at<?"]
        if kind is not None:
            clauses.append("source_kind=?")
            parameters.append(kind)
        if cursor is not None:
            if not isinstance(cursor, tuple) or len(cursor) != 2:
                raise DeviceFingerprintValidationError("Evidence cursor is invalid")
            cursor_time = parse_utc(cursor[0])
            del cursor_time
            validate_uuid(cursor[1])
            clauses.append("(observed_at>? OR (observed_at=? AND evidence_id>?))")
            parameters.extend([cursor[0], cursor[0], cursor[1]])
        parameters.append(limit + 1)
        connection = open_read_only(self.db_path)
        try:
            rows = connection.execute(
                "SELECT * FROM device_fingerprint_evidence WHERE " + " AND ".join(clauses) + " ORDER BY observed_at,evidence_id LIMIT ?",
                parameters,
            ).fetchall()
        finally:
            connection.close()
        more = len(rows) > limit
        selected = rows[:limit]
        items = [dict(row) for row in selected]
        next_cursor = (selected[-1]["observed_at"], selected[-1]["evidence_id"]) if more and selected else None
        return {"items": items, "next_cursor": next_cursor}

    def latest_source_health(self, site_id: str, capture_source_id: str,
                             source_kind: str, *, through_utc: str) -> dict[str, Any] | None:
        site = validate_site_id(site_id)
        capture = validate_machine_id(capture_source_id)
        kind = validate_source_kind(source_kind)
        parse_utc(through_utc)
        connection = open_read_only(self.db_path)
        try:
            row = connection.execute(
                "SELECT * FROM device_fingerprint_source_health_events WHERE site_id=? AND capture_source_id=? AND source_kind=? AND observed_at<=? ORDER BY observed_at DESC,source_health_id DESC LIMIT 1",
                (site, capture, kind, through_utc),
            ).fetchone()
        finally:
            connection.close()
        return dict(row) if row is not None else None
