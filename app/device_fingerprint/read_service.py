"""Bounded read-only Python API for normalized fingerprint evidence."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from .models import DeviceFingerprintValidationError
from .repository import open_read_only
from .validation import parse_utc, validate_mac, validate_machine_id, validate_site_id, validate_source_kind, validate_uuid


class DeviceFingerprintReadService:
    def __init__(self, db_path: str, *, retention_days: int) -> None:
        self.db_path = db_path
        self.retention_days = retention_days

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
