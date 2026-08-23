"""Site-scoped read-only boundary for exact Current State snapshots."""

from __future__ import annotations

import base64
import json
import sqlite3
from datetime import datetime
from typing import Any, Mapping

from app.common.mac import format_mac_colon

from .models import (
    CurrentApBucket,
    CurrentApPage,
    CurrentApState,
    CurrentApSummary,
    CurrentClientPage,
    CurrentClientState,
    CurrentClientSummary,
    CurrentHistoryQuality,
    CurrentSnapshotMeta,
    CurrentStateValidationError,
    format_utc,
    parse_utc,
    require_cycle_id,
    require_site_id,
    utc_now,
)
from .repository import AUTH_CLASSIFICATIONS, CurrentStateRepository


CURSOR_VERSION = 1
MAX_CURSOR_LENGTH = 2048
MAX_PAGE_SIZE = 500


class CurrentStateReadService:
    """Read persisted current facts without Omada calls or writes."""

    def __init__(self, repository: CurrentStateRepository):
        self.repository = repository
        self.config = repository.config

    def get_current_client_summary(self, site_id: str, *, evaluated_at_utc: datetime | str | None = None) -> CurrentClientSummary:
        site = require_site_id(site_id)
        evaluated = _evaluated(evaluated_at_utc)
        with self.repository.read_connection() as connection:
            connection.execute("BEGIN")
            attempt, complete, partial = _cycle_selection(connection, site, "client")
            meta = self._meta(site, "client", evaluated, attempt, complete, partial)
            if complete is None or meta.freshness_status == "unavailable":
                return CurrentClientSummary(meta, None, None, None, None, None, None, None, ())
            counts = connection.execute(
                """
                SELECT COUNT(*) AS online,
                       SUM(auth_classification='authorized') AS authorized,
                       SUM(auth_classification='pending') AS pending,
                       SUM(auth_classification='other') AS other_count,
                       SUM(auth_classification='unknown') AS unknown_count,
                       SUM(ap_mac IS NULL) AS ap_unknown
                FROM current_client_state WHERE cycle_id=?
                """,
                (complete["cycle_id"],),
            ).fetchone()
            buckets = connection.execute(
                """
                SELECT ap_mac, COUNT(*) AS client_count
                FROM current_client_state
                WHERE cycle_id=? AND ap_mac IS NOT NULL
                GROUP BY ap_mac ORDER BY ap_mac
                """,
                (complete["cycle_id"],),
            ).fetchall()
        online = int(counts["online"] or 0)
        authorized = int(counts["authorized"] or 0)
        pending = int(counts["pending"] or 0)
        other = int(counts["other_count"] or 0)
        unknown = int(counts["unknown_count"] or 0)
        ap_unknown = int(counts["ap_unknown"] or 0)
        if online != authorized + pending + other + unknown:
            raise CurrentStateValidationError("persisted auth count invariant failed")
        if online != ap_unknown + sum(int(row["client_count"]) for row in buckets):
            raise CurrentStateValidationError("persisted AP count invariant failed")
        return CurrentClientSummary(
            meta, online, authorized, pending, other, unknown, other + unknown,
            ap_unknown,
            tuple(CurrentApBucket(str(row["ap_mac"]), int(row["client_count"])) for row in buckets),
        )

    def list_current_clients(
        self,
        site_id: str,
        *,
        cycle_id: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
        sort: str = "controller_traffic_total_desc",
        auth_classification: str | None = None,
        ap_mac: str | None = None,
        ssid: str | None = None,
        evaluated_at_utc: datetime | str | None = None,
    ) -> CurrentClientPage:
        site = require_site_id(site_id)
        count = _limit(limit)
        filters = _client_filters(auth_classification, ap_mac, ssid)
        if sort not in _SORTS:
            raise CurrentStateValidationError("sort is not allowed")
        decoded = _decode_cursor(cursor, "clients") if cursor is not None else None
        if decoded is not None:
            _cursor_context(decoded, site, sort, filters)
            if cycle_id is not None and cycle_id != decoded["cycle"]:
                raise CurrentStateValidationError("cursor cycle changed")
            cycle_id = decoded["cycle"]
        evaluated = _evaluated(evaluated_at_utc)
        with self.repository.read_connection() as connection:
            connection.execute("BEGIN")
            attempt, latest_complete, partial = _cycle_selection(connection, site, "client")
            selected = latest_complete if cycle_id is None else connection.execute(
                "SELECT * FROM current_state_cycles WHERE cycle_id=? AND site_id=? AND kind='client' AND result='success' AND complete=1",
                (require_cycle_id(cycle_id), site),
            ).fetchone()
            meta = self._meta(site, "client", evaluated, attempt, selected, partial)
            if selected is None or meta.freshness_status == "unavailable":
                return CurrentClientPage(meta, (), None)
            if decoded is not None and decoded["scope"] != selected["source_scope_hash"]:
                raise CurrentStateValidationError("cursor source scope changed")
            clauses = ["cycle_id=?"]
            params: list[Any] = [selected["cycle_id"]]
            if filters["auth"] is not None:
                clauses.append("auth_classification=?")
                params.append(filters["auth"])
            if filters["ap"] is not None:
                clauses.append("ap_mac=?")
                params.append(filters["ap"])
            if filters["ssid"] is not None:
                clauses.append("ssid=?")
                params.append(filters["ssid"])
            keyset, key_params = _client_keyset(sort, decoded.get("last") if decoded else None)
            if keyset:
                clauses.append(keyset)
                params.extend(key_params)
            order = _SORTS[sort]["order"]
            rows = connection.execute(
                f"SELECT * FROM current_client_state WHERE {' AND '.join(clauses)} ORDER BY {order} LIMIT ?",
                (*params, count + 1),
            ).fetchall()
        selected_rows = rows[:count]
        has_more = len(rows) > count
        next_cursor = None
        if has_more and selected_rows:
            next_cursor = _encode_cursor({
                "v": CURSOR_VERSION, "endpoint": "clients", "site": site,
                "cycle": str(selected["cycle_id"]), "scope": str(selected["source_scope_hash"]),
                "sort": sort, "filters": filters,
                "last": _client_last(sort, selected_rows[-1]),
            })
        return CurrentClientPage(meta, tuple(_client(row) for row in selected_rows), next_cursor)

    def get_current_ap_summary(self, site_id: str, *, evaluated_at_utc: datetime | str | None = None) -> CurrentApSummary:
        site = require_site_id(site_id)
        evaluated = _evaluated(evaluated_at_utc)
        with self.repository.read_connection() as connection:
            connection.execute("BEGIN")
            attempt, complete, partial = _cycle_selection(connection, site, "ap")
            meta = self._meta(site, "ap", evaluated, attempt, complete, partial)
            if complete is None or meta.freshness_status == "unavailable":
                return CurrentApSummary(meta, None, None, None, None, None)
            row = connection.execute(
                """
                SELECT COUNT(*) AS total,
                       SUM(status_classification='online') AS online,
                       SUM(status_classification='offline') AS offline,
                       SUM(status_classification='other') AS other_count,
                       SUM(status_classification='unknown') AS unknown_count
                FROM current_ap_state WHERE cycle_id=?
                """,
                (complete["cycle_id"],),
            ).fetchone()
        values = tuple(int(row[name] or 0) for name in ("total", "online", "offline", "other_count", "unknown_count"))
        if values[0] != sum(values[1:]):
            raise CurrentStateValidationError("persisted AP status invariant failed")
        return CurrentApSummary(meta, *values)

    def list_current_aps(self, site_id: str, *, cycle_id: str | None = None, limit: int = 100, cursor: str | None = None, evaluated_at_utc: datetime | str | None = None) -> CurrentApPage:
        site = require_site_id(site_id)
        count = _limit(limit)
        decoded = _decode_cursor(cursor, "aps") if cursor is not None else None
        if decoded is not None:
            if decoded["site"] != site:
                raise CurrentStateValidationError("cursor Site changed")
            if cycle_id is not None and decoded["cycle"] != cycle_id:
                raise CurrentStateValidationError("cursor cycle changed")
            cycle_id = decoded["cycle"]
        evaluated = _evaluated(evaluated_at_utc)
        with self.repository.read_connection() as connection:
            connection.execute("BEGIN")
            attempt, latest_complete, partial = _cycle_selection(connection, site, "ap")
            selected = latest_complete if cycle_id is None else connection.execute(
                "SELECT * FROM current_state_cycles WHERE cycle_id=? AND site_id=? AND kind='ap' AND result='success' AND complete=1",
                (require_cycle_id(cycle_id), site),
            ).fetchone()
            meta = self._meta(site, "ap", evaluated, attempt, selected, partial)
            if selected is None or meta.freshness_status == "unavailable":
                return CurrentApPage(meta, (), None)
            if decoded is not None and decoded["scope"] != selected["source_scope_hash"]:
                raise CurrentStateValidationError("cursor source scope changed")
            last = decoded.get("last") if decoded else None
            clause = " AND ap_mac > ?" if last is not None else ""
            params = (selected["cycle_id"], last, count + 1) if last is not None else (selected["cycle_id"], count + 1)
            rows = connection.execute(
                f"SELECT * FROM current_ap_state WHERE cycle_id=?{clause} ORDER BY ap_mac LIMIT ?",
                params,
            ).fetchall()
        selected_rows = rows[:count]
        next_cursor = None
        if len(rows) > count and selected_rows:
            next_cursor = _encode_cursor({
                "v": CURSOR_VERSION, "endpoint": "aps", "site": site,
                "cycle": str(selected["cycle_id"]), "scope": str(selected["source_scope_hash"]),
                "last": str(selected_rows[-1]["ap_mac"]),
            })
        return CurrentApPage(meta, tuple(_ap(row) for row in selected_rows), next_cursor)

    def get_client_history_quality(self, site_id: str, from_utc: str, to_utc: str, *, source_scope_hash: str) -> CurrentHistoryQuality:
        site = require_site_id(site_id)
        start = parse_utc(from_utc, "from_utc")
        end = parse_utc(to_utc, "to_utc")
        if start > end or (end - start).total_seconds() > 168 * 3600:
            raise CurrentStateValidationError("history window is invalid")
        if not isinstance(source_scope_hash, str) or len(source_scope_hash) != 64:
            raise CurrentStateValidationError("source_scope_hash is invalid")
        with self.repository.read_connection() as connection:
            row = connection.execute(
                """
                WITH selected AS (
                  SELECT * FROM current_state_cycles
                  WHERE kind='client' AND site_id=? AND capture_started_at>=? AND capture_started_at<=?
                ), gaps AS (
                  SELECT capture_started_at,
                         (julianday(capture_started_at)-julianday(LAG(capture_started_at) OVER (ORDER BY capture_started_at)))*86400 AS gap
                  FROM selected WHERE result='success' AND complete=1 AND source_scope_hash=?
                )
                SELECT
                  SUM(result='success' AND complete=1 AND source_scope_hash=?) AS complete_count,
                  SUM(result='partial') AS partial_count,
                  SUM(result IN ('failed','shutdown')) AS failed_count,
                  MIN(CASE WHEN result='success' AND complete=1 AND source_scope_hash=? THEN capture_started_at END) AS first_at,
                  MAX(CASE WHEN result='success' AND complete=1 AND source_scope_hash=? THEN capture_started_at END) AS last_at,
                  (SELECT MAX(gap) FROM gaps) AS max_gap,
                  MAX(source_scope_hash<>?) AS scope_changed
                FROM selected
                """,
                (site, from_utc, to_utc, source_scope_hash, source_scope_hash, source_scope_hash, source_scope_hash, source_scope_hash),
            ).fetchone()
        complete = int(row["complete_count"] or 0)
        scope_changed = bool(row["scope_changed"] or 0)
        coverage = "insufficient_data" if complete == 0 else "incompatible_scope" if scope_changed else "partial" if row["first_at"] > from_utc or row["last_at"] < to_utc else "complete"
        return CurrentHistoryQuality(
            site, from_utc, to_utc, 1, source_scope_hash, complete,
            int(row["partial_count"] or 0), int(row["failed_count"] or 0),
            row["first_at"], row["last_at"], float(row["max_gap"]) if row["max_gap"] is not None else None,
            scope_changed, coverage,
        )

    def _meta(self, site: str, kind: str, evaluated: str, attempt: sqlite3.Row | None, complete: sqlite3.Row | None, partial: sqlite3.Row | None) -> CurrentSnapshotMeta:
        if complete is None:
            return CurrentSnapshotMeta(
                None, site, kind, evaluated, None, None, None, "unavailable", "no_complete_snapshot", False,
                None, None, None, attempt["result"] if attempt else None,
                attempt["capture_started_at"] if attempt else None,
                partial["cycle_id"] if partial else None,
            )
        observed = str(complete["capture_started_at"])
        try:
            observed_dt = parse_utc(observed, "observed_at")
            evaluated_dt = parse_utc(evaluated, "evaluated_at")
            age = (evaluated_dt - observed_dt).total_seconds()
        except CurrentStateValidationError:
            return _meta_from_row(site, kind, evaluated, complete, attempt, partial, None, "unavailable", "invalid_timestamp")
        if age < 0:
            return _meta_from_row(site, kind, evaluated, complete, attempt, partial, 0.0, "unavailable", "clock_anomaly")
        fresh = self.config.client_fresh_max_age_seconds if kind == "client" else self.config.ap_fresh_max_age_seconds
        stale = self.config.client_stale_max_age_seconds if kind == "client" else self.config.ap_stale_max_age_seconds
        if age <= fresh:
            status, reason = "fresh", "within_freshness_window"
        elif age <= stale:
            status, reason = "stale", "older_than_freshness_window"
        else:
            status, reason = "unavailable", "older_than_unavailable_threshold"
        return _meta_from_row(site, kind, evaluated, complete, attempt, partial, age, status, reason)


_SORTS: dict[str, dict[str, str]] = {
    "client_mac": {"column": "client_mac", "direction": "asc", "order": "client_mac ASC"},
    "controller_uptime": {"column": "controller_uptime", "direction": "desc", "order": "controller_uptime IS NULL, controller_uptime DESC, client_mac ASC"},
    "controller_traffic_total_desc": {"column": "controller_traffic_total", "direction": "desc", "order": "controller_traffic_total IS NULL, controller_traffic_total DESC, client_mac ASC"},
    "controller_traffic_total": {"column": "controller_traffic_total", "direction": "desc", "order": "controller_traffic_total IS NULL, controller_traffic_total DESC, client_mac ASC"},
    "controller_traffic_down": {"column": "controller_traffic_down", "direction": "desc", "order": "controller_traffic_down IS NULL, controller_traffic_down DESC, client_mac ASC"},
    "controller_traffic_up": {"column": "controller_traffic_up", "direction": "desc", "order": "controller_traffic_up IS NULL, controller_traffic_up DESC, client_mac ASC"},
    "auth_status": {"column": "auth_classification", "direction": "asc", "order": "auth_classification ASC, client_mac ASC"},
    "ap": {"column": "ap_mac", "direction": "asc", "order": "ap_mac IS NULL, ap_mac ASC, client_mac ASC"},
    "rssi": {"column": "rssi", "direction": "desc", "order": "rssi IS NULL, rssi DESC, client_mac ASC"},
    "snr": {"column": "snr", "direction": "desc", "order": "snr IS NULL, snr DESC, client_mac ASC"},
}


def _cycle_selection(connection: sqlite3.Connection, site: str, kind: str) -> tuple[sqlite3.Row | None, sqlite3.Row | None, sqlite3.Row | None]:
    attempt = connection.execute(
        "SELECT * FROM current_state_cycles WHERE site_id=? AND kind=? ORDER BY capture_started_at DESC, cycle_id DESC LIMIT 1",
        (site, kind),
    ).fetchone()
    complete = connection.execute(
        "SELECT * FROM current_state_cycles WHERE site_id=? AND kind=? AND result='success' AND complete=1 ORDER BY capture_started_at DESC, cycle_id DESC LIMIT 1",
        (site, kind),
    ).fetchone()
    partial = connection.execute(
        "SELECT * FROM current_state_cycles WHERE site_id=? AND kind=? AND result='partial' AND complete=0 AND items_stored>0 ORDER BY capture_started_at DESC, cycle_id DESC LIMIT 1",
        (site, kind),
    ).fetchone()
    return attempt, complete, partial


def _meta_from_row(site: str, kind: str, evaluated: str, row: sqlite3.Row, attempt: sqlite3.Row | None, partial: sqlite3.Row | None, age: float | None, status: str, reason: str) -> CurrentSnapshotMeta:
    try:
        source_scope = json.loads(row["source_scope_json"])
        if not isinstance(source_scope, dict):
            raise ValueError
    except (TypeError, ValueError, json.JSONDecodeError):
        source_scope = None
        status, reason = "unavailable", "invalid_source_scope"
    return CurrentSnapshotMeta(
        str(row["cycle_id"]), site, kind, evaluated, str(row["capture_started_at"]),
        str(row["capture_finished_at"]), age, status, reason, bool(row["complete"]),
        int(row["source_scope_version"]), str(row["source_scope_hash"]), source_scope,
        str(attempt["result"]) if attempt else None,
        str(attempt["capture_started_at"]) if attempt else None,
        str(partial["cycle_id"]) if partial else None,
    )


def _evaluated(value: datetime | str | None) -> str:
    if value is None:
        return utc_now()
    if isinstance(value, datetime):
        return format_utc(value)
    parse_utc(value, "evaluated_at_utc")
    return value


def _limit(value: Any) -> int:
    if type(value) is not int or not 1 <= value <= MAX_PAGE_SIZE:
        raise CurrentStateValidationError("limit is outside bounds")
    return value


def _client_filters(auth: str | None, ap_mac: str | None, ssid: str | None) -> dict[str, str | None]:
    if auth is not None and auth not in AUTH_CLASSIFICATIONS:
        raise CurrentStateValidationError("auth_classification is invalid")
    canonical_ap = None
    if ap_mac is not None:
        try:
            canonical_ap = format_mac_colon(ap_mac)
        except (TypeError, ValueError) as exc:
            raise CurrentStateValidationError("ap_mac is invalid") from exc
    if ssid is not None and (not isinstance(ssid, str) or ssid == ""):
        raise CurrentStateValidationError("ssid is invalid")
    return {"auth": auth, "ap": canonical_ap, "ssid": ssid}


def _client_keyset(sort: str, last: Any) -> tuple[str, tuple[Any, ...]]:
    if last is None:
        return "", ()
    if not isinstance(last, dict) or set(last) != {"value", "mac", "null"}:
        raise CurrentStateValidationError("cursor is malformed")
    column = _SORTS[sort]["column"]
    direction = _SORTS[sort]["direction"]
    mac = last["mac"]
    if not isinstance(mac, str):
        raise CurrentStateValidationError("cursor is malformed")
    if column == "client_mac":
        return "client_mac > ?", (mac,)
    if last["null"] is True:
        return f"{column} IS NULL AND client_mac > ?", (mac,)
    value = last["value"]
    operator = "<" if direction == "desc" else ">"
    return (
        f"(({column} IS NOT NULL AND ({column} {operator} ? OR ({column}=? AND client_mac>?))) OR {column} IS NULL)",
        (value, value, mac),
    )


def _client_last(sort: str, row: sqlite3.Row) -> dict[str, Any]:
    column = _SORTS[sort]["column"]
    value = row[column]
    return {"value": value, "mac": str(row["client_mac"]), "null": value is None}


def _cursor_context(payload: Mapping[str, Any], site: str, sort: str, filters: Mapping[str, Any]) -> None:
    if payload.get("site") != site or payload.get("sort") != sort or payload.get("filters") != filters:
        raise CurrentStateValidationError("cursor context changed")


def _encode_cursor(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("ascii")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(value: str, endpoint: str) -> dict[str, Any]:
    if not isinstance(value, str) or not value or len(value) > MAX_CURSOR_LENGTH:
        raise CurrentStateValidationError("cursor is malformed")
    try:
        raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        payload = json.loads(raw.decode("ascii"))
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise CurrentStateValidationError("cursor is malformed") from exc
    required = {"v", "endpoint", "site", "cycle", "scope", "last"}
    if not isinstance(payload, dict) or not required.issubset(payload) or payload.get("v") != CURSOR_VERSION or payload.get("endpoint") != endpoint:
        raise CurrentStateValidationError("cursor is malformed")
    if endpoint == "clients" and not {"sort", "filters"}.issubset(payload):
        raise CurrentStateValidationError("cursor is malformed")
    return payload


def _client(row: sqlite3.Row) -> CurrentClientState:
    return CurrentClientState(
        cycle_id=str(row["cycle_id"]), site_id=str(row["site_id"]), observed_at=str(row["observed_at"]),
        client_mac=str(row["client_mac"]), name=row["name"], hostname=row["hostname"], device_type=row["device_type"],
        ip=row["ip"], ssid=str(row["ssid"]), ap_name=row["ap_name"], ap_mac=row["ap_mac"], radio_id=row["radio_id"],
        band=row["band"], channel=row["channel"], rssi=row["rssi"], snr=row["snr"], controller_uptime=row["controller_uptime"],
        auth_status_code=row["auth_status_code"], auth_classification=str(row["auth_classification"]),
        controller_traffic_down=row["controller_traffic_down"], controller_traffic_up=row["controller_traffic_up"],
        controller_traffic_total=row["controller_traffic_total"], active=bool(row["active"]), wireless=bool(row["wireless"]),
    )


def _ap(row: sqlite3.Row) -> CurrentApState:
    return CurrentApState(
        cycle_id=str(row["cycle_id"]), site_id=str(row["site_id"]), observed_at=str(row["observed_at"]),
        ap_mac=str(row["ap_mac"]), name=row["name"], ip=row["ip"], model=row["model"], firmware_version=row["firmware_version"],
        status_code=row["status_code"], status_classification=str(row["status_classification"]), last_seen_ms=row["last_seen_ms"],
        controller_uptime=row["controller_uptime"], uptime_raw=row["uptime_raw"],
    )
