"""Deadline-aware direct read boundaries for Admin Web v1."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, TypeVar

from app.analytics.source_gateway import (
    AnalyticsQueryDeadlineExceeded,
    QueryDeadline,
)


_T = TypeVar("_T")
_PROGRESS_OPCODE_INTERVAL = 10_000

_VISIT_FIELDS = (
    "visit_id", "device_id", "client_mac", "started_at", "closed_at",
    "status", "duration_seconds", "start_ssid", "final_ssid",
    "start_ap_mac", "final_ap_mac", "reported_traffic_total_bytes",
)
_VISIT_DETAIL_EXTRA = (
    "close_reason", "close_time_source", "start_ip", "final_ip",
    "reported_connected_seconds", "reported_traffic_up_bytes",
    "reported_traffic_down_bytes",
)
_CLIENT_FIELDS = (
    "observed_at", "client_mac", "ip", "ssid", "ap_name", "ap_mac",
    "radio_id", "band", "channel", "rssi", "snr", "rx_rate", "tx_rate",
    "traffic_down", "traffic_up", "uptime", "auth_status", "active",
)
_AP_FIELDS = (
    "observed_at", "ap_mac", "name", "ip", "model", "firmware_version",
    "cpu_util", "mem_util", "uptime_seconds", "wired_download_mbps",
    "wired_upload_mbps", "lan_rx_mbps", "lan_tx_mbps", "partial",
)
_RADIO_FIELDS = (
    "radio_observed_at", "ap_mac", "band", "radio_id", "actual_channel",
    "frequency_mhz", "channel_width", "tx_power", "tx_util", "rx_util",
    "interference_util", "busy_util", "radio_rx_mbps", "radio_tx_mbps",
)


class AdminReadSourceError(RuntimeError):
    """Sanitized source read failure."""


class AdminSqlReadGateway:
    """Execute bounded Site-scoped SELECTs with real SQLite cancellation."""

    def __init__(self, visit_db_path: str | Path, observation_db_path: str | Path):
        self._visit_path = Path(visit_db_path)
        self._observation_path = Path(observation_db_path)

    def list_visits(
        self,
        *,
        site_id: str,
        limit: int,
        deadline: QueryDeadline,
        from_utc: str | None = None,
        to_utc: str | None = None,
        status: str | None = None,
        client_mac: str | None = None,
        device_id: str | None = None,
        ssid: str | None = None,
        ap_mac: str | None = None,
        cursor: tuple[str, str] | None = None,
    ) -> tuple[tuple[dict[str, Any], ...], bool]:
        clauses = ["v.site_id = ?"]
        parameters: list[Any] = [site_id]
        if from_utc is not None:
            clauses.append("(v.closed_at IS NULL OR v.closed_at > ?)")
            parameters.append(from_utc)
        if to_utc is not None:
            clauses.append("v.started_at < ?")
            parameters.append(to_utc)
        for column, value in (
            ("status", status),
            ("client_mac", client_mac),
            ("device_id", device_id),
        ):
            if value is not None:
                clauses.append(f"v.{column} = ?")
                parameters.append(value)
        if ssid is not None:
            clauses.append(
                "(v.start_ssid = ? OR v.final_ssid = ? OR EXISTS ("
                "SELECT 1 FROM visit_authorizations AS a "
                "WHERE a.visit_id = v.visit_id AND a.portal_ssid = ?))"
            )
            parameters.extend((ssid, ssid, ssid))
        if ap_mac is not None:
            clauses.append(
                "(v.start_ap_mac = ? OR v.final_ap_mac = ? OR EXISTS ("
                "SELECT 1 FROM visit_authorizations AS a "
                "WHERE a.visit_id = v.visit_id AND a.portal_ap_mac = ?))"
            )
            parameters.extend((ap_mac, ap_mac, ap_mac))
        if cursor is not None:
            clauses.append(
                "(v.started_at < ? OR (v.started_at = ? AND v.visit_id < ?))"
            )
            parameters.extend((cursor[0], cursor[0], cursor[1]))
        parameters.append(limit + 1)
        columns = ", ".join(f"v.{name}" for name in _VISIT_FIELDS)
        sql = (
            f"SELECT {columns} FROM visits AS v "
            f"WHERE {' AND '.join(clauses)} "
            "ORDER BY v.started_at DESC, v.visit_id DESC LIMIT ?"
        )

        def read(connection: sqlite3.Connection):
            return connection.execute(sql, tuple(parameters)).fetchall()

        rows = self._read(self._visit_path, 2, deadline, read)
        return self._page(rows, limit, _VISIT_FIELDS)

    def get_visit(
        self,
        *,
        site_id: str,
        visit_id: str,
        deadline: QueryDeadline,
    ) -> dict[str, Any] | None:
        fields = _VISIT_FIELDS + _VISIT_DETAIL_EXTRA
        columns = ", ".join(fields)

        def read(connection: sqlite3.Connection):
            return connection.execute(
                f"SELECT {columns} FROM visits WHERE site_id=? AND visit_id=?",
                (site_id, visit_id),
            ).fetchone()

        row = self._read(self._visit_path, 2, deadline, read)
        return None if row is None else self._safe_row(row, fields)

    def latest_client_observation(
        self,
        *,
        site_id: str,
        client_mac: str,
        deadline: QueryDeadline,
    ) -> dict[str, Any] | None:
        columns = ", ".join(f"o.{field}" for field in _CLIENT_FIELDS)

        def read(connection: sqlite3.Connection):
            return connection.execute(
                f"""
                SELECT {columns}
                FROM client_observations AS o
                JOIN observation_cycles AS c ON c.cycle_id=o.cycle_id
                WHERE o.site_id=? AND o.client_mac=? AND c.state='completed'
                ORDER BY o.observed_at DESC, o.row_id DESC
                LIMIT 1
                """,
                (site_id, client_mac),
            ).fetchone()

        row = self._read(self._observation_path, 1, deadline, read)
        return None if row is None else self._observation(row, _CLIENT_FIELDS)

    def list_client_observations(
        self,
        *,
        site_id: str,
        client_mac: str,
        from_utc: str,
        to_utc: str,
        limit: int,
        deadline: QueryDeadline,
        cursor: tuple[str, int] | None = None,
    ) -> tuple[tuple[dict[str, Any], ...], bool]:
        cursor_sql = ""
        parameters: list[Any] = [site_id, client_mac, from_utc, to_utc]
        if cursor is not None:
            cursor_sql = (
                "AND (o.observed_at < ? OR "
                "(o.observed_at = ? AND o.row_id < ?))"
            )
            parameters.extend((cursor[0], cursor[0], cursor[1]))
        parameters.append(limit + 1)
        columns = ", ".join(f"o.{field}" for field in _CLIENT_FIELDS)

        def read(connection: sqlite3.Connection):
            return connection.execute(
                f"""
                SELECT o.row_id, {columns}
                FROM client_observations AS o
                JOIN observation_cycles AS c ON c.cycle_id=o.cycle_id
                WHERE o.site_id=? AND o.client_mac=?
                  AND o.observed_at>=? AND o.observed_at<=?
                  AND c.state='completed' {cursor_sql}
                ORDER BY o.observed_at DESC, o.row_id DESC
                LIMIT ?
                """,
                tuple(parameters),
            ).fetchall()

        rows = self._read(self._observation_path, 1, deadline, read)
        return self._observation_page(rows, limit, _CLIENT_FIELDS)

    def list_ap_observations(
        self,
        *,
        site_id: str,
        ap_mac: str,
        from_utc: str,
        to_utc: str,
        limit: int,
        deadline: QueryDeadline,
        cursor: tuple[str, int] | None = None,
    ) -> tuple[tuple[dict[str, Any], ...], bool]:
        cursor_sql = ""
        parameters: list[Any] = [site_id, ap_mac, from_utc, to_utc]
        if cursor is not None:
            cursor_sql = (
                "AND (o.observed_at < ? OR "
                "(o.observed_at = ? AND o.row_id < ?))"
            )
            parameters.extend((cursor[0], cursor[0], cursor[1]))
        parameters.append(limit + 1)
        columns = ", ".join(f"o.{field}" for field in _AP_FIELDS)

        def read(connection: sqlite3.Connection):
            rows = connection.execute(
                f"""
                SELECT o.row_id, {columns}
                FROM ap_observations AS o
                JOIN observation_cycles AS c ON c.cycle_id=o.cycle_id
                WHERE o.site_id=? AND o.ap_mac=?
                  AND o.observed_at>=? AND o.observed_at<=?
                  AND c.state='completed' {cursor_sql}
                ORDER BY o.observed_at DESC, o.row_id DESC
                LIMIT ?
                """,
                tuple(parameters),
            ).fetchall()
            visible = rows[:limit]
            radios: dict[int, list[dict[str, Any]]] = {}
            if visible:
                identities = [int(row["row_id"]) for row in visible]
                placeholders = ",".join("?" for _ in identities)
                radio_columns = ", ".join(
                    f"r.{field}" for field in _RADIO_FIELDS
                )
                radio_rows = connection.execute(
                    f"""
                    SELECT r.ap_observation_row_id, {radio_columns}
                    FROM ap_radio_observations AS r
                    WHERE r.site_id=? AND r.ap_mac=?
                      AND r.ap_observation_row_id IN ({placeholders})
                    ORDER BY r.ap_observation_row_id, r.band, r.row_id
                    """,
                    (site_id, ap_mac, *identities),
                ).fetchall()
                for radio in radio_rows:
                    radios.setdefault(
                        int(radio["ap_observation_row_id"]), []
                    ).append(self._safe_row(radio, _RADIO_FIELDS))
            return rows, radios

        rows, radios = self._read(self._observation_path, 1, deadline, read)
        has_more = len(rows) > limit
        values = []
        for row in rows[:limit]:
            value = self._observation(row, _AP_FIELDS)
            value["radios"] = radios.get(int(row["row_id"]), [])
            value["_row_id"] = int(row["row_id"])
            values.append(value)
        return tuple(values), has_more

    def _read(
        self,
        path: Path,
        expected_version: int,
        deadline: QueryDeadline,
        action: Callable[[sqlite3.Connection], _T],
    ) -> _T:
        try:
            with self._connection(path, expected_version, deadline) as connection:
                return action(connection)
        except AnalyticsQueryDeadlineExceeded:
            raise
        except sqlite3.Error as exc:
            if deadline.expired() or "interrupt" in str(exc).lower():
                raise AnalyticsQueryDeadlineExceeded(
                    "Admin query deadline exceeded"
                ) from None
            raise AdminReadSourceError("Admin source unavailable") from None
        except OSError:
            raise AdminReadSourceError("Admin source unavailable") from None

    @contextmanager
    def _connection(
        self,
        path: Path,
        expected_version: int,
        deadline: QueryDeadline,
    ) -> Iterator[sqlite3.Connection]:
        deadline.require_remaining()
        uri = f"{path.resolve(strict=False).as_uri()}?mode=ro"
        connection = sqlite3.connect(
            uri,
            uri=True,
            isolation_level=None,
            timeout=0.0,
        )
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA query_only=ON")
            connection.execute("BEGIN")
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if version != expected_version:
                raise AdminReadSourceError("Admin source unavailable")
            connection.set_progress_handler(
                lambda: 1 if deadline.expired() else 0,
                _PROGRESS_OPCODE_INTERVAL,
            )
            yield connection
        finally:
            connection.set_progress_handler(None, 0)
            try:
                connection.rollback()
            finally:
                connection.close()

    @classmethod
    def _page(cls, rows, limit: int, fields: tuple[str, ...]):
        return tuple(cls._safe_row(row, fields) for row in rows[:limit]), (
            len(rows) > limit
        )

    @classmethod
    def _observation_page(cls, rows, limit: int, fields: tuple[str, ...]):
        values = []
        for row in rows[:limit]:
            value = cls._observation(row, fields)
            value["_row_id"] = int(row["row_id"])
            values.append(value)
        return tuple(values), len(rows) > limit

    @staticmethod
    def _safe_row(row: Mapping[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
        return {field: row[field] for field in fields}

    @classmethod
    def _observation(
        cls,
        row: Mapping[str, Any],
        fields: tuple[str, ...],
    ) -> dict[str, Any]:
        value = cls._safe_row(row, fields)
        for field in ("active", "partial"):
            if field in value and value[field] is not None:
                value[field] = bool(value[field])
        return value
