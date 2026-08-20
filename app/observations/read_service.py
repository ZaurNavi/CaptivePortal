"""Read-only, Site-scoped query service for observation facts."""

from __future__ import annotations

import base64
import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Callable, Iterable, Mapping, Sequence, TypeVar

from .models import (
    ApConfigSnapshot,
    ApObservation,
    ApRadioObservation,
    ClientObservation,
    DEFAULT_QUERY_LIMIT,
    ObservationPage,
    ObservationStorageError,
    ObservationValidationError,
    StorageFailureCategory,
    parse_utc,
    require_limit,
    require_mac,
    require_text,
    require_utc,
)
from .repository import CYCLE_STATES, ObservationRepository, classify_sqlite_error


_CURSOR_VERSION = 1
_MAX_CURSOR_LENGTH = 512
_CLIENT_CORE = frozenset({
    "row_id", "cycle_id", "observed_at", "site_id", "client_mac",
    "source_inventory_complete", "ssid", "ap_mac", "radio_id",
})
_AP_CORE = frozenset({
    "row_id", "cycle_id", "observed_at", "site_id", "ap_mac",
    "partial",
})
_RADIO_CORE = frozenset({
    "row_id", "cycle_id", "ap_observation_row_id", "radio_observed_at",
    "site_id", "ap_mac", "band",
})
_BOOLEAN_DATA_COLUMNS = frozenset({
    "wireless", "power_save", "blocked", "guest", "active", "manager",
    "overview_ok", "wired_uplink_ok", "lan_traffic_ok", "radios_ok",
})

T = TypeVar("T")


class ObservationReadService:
    """Return immutable DTOs and never expose ``sqlite3.Row``."""

    def __init__(self, repository: ObservationRepository):
        self._repository = repository

    @contextmanager
    def analytics_read_connection(self):
        """Yield the existing repository's URI-mode read-only connection."""
        with self._repository.read_connection() as connection:
            yield connection

    def get_client_observations(
        self,
        site_id: str,
        client_mac: str,
        from_utc: str,
        to_utc: str,
        limit: int = DEFAULT_QUERY_LIMIT,
        cursor: str | None = None,
        *,
        cycle_states: Sequence[str] = ("completed",),
    ) -> ObservationPage[ClientObservation]:
        site, start, end, count, states = _common_query(
            site_id, from_utc, to_utc, limit, cycle_states
        )
        mac = require_mac(client_mac, "client_mac")
        return self._paged(
            table="client_observations",
            alias="o",
            order_column="observed_at",
            where=(
                "o.site_id = ? AND o.client_mac = ? "
                "AND o.observed_at >= ? AND o.observed_at <= ?"
            ),
            parameters=(site, mac, start, end),
            limit=count,
            cursor=cursor,
            cycle_states=states,
            converter=_client_dto,
        )

    def get_site_client_observations(
        self,
        site_id: str,
        from_utc: str,
        to_utc: str,
        *,
        ssid: str | None = None,
        ap_mac: str | None = None,
        radio_id: int | None = None,
        limit: int = DEFAULT_QUERY_LIMIT,
        cursor: str | None = None,
        cycle_states: Sequence[str] = ("completed",),
    ) -> ObservationPage[ClientObservation]:
        site, start, end, count, states = _common_query(
            site_id, from_utc, to_utc, limit, cycle_states
        )
        clauses = [
            "o.site_id = ?",
            "o.observed_at >= ?",
            "o.observed_at <= ?",
        ]
        parameters: list[Any] = [site, start, end]
        if ssid is not None:
            clauses.append("o.ssid = ?")
            parameters.append(require_text(ssid, "ssid"))
        if ap_mac is not None:
            clauses.append("o.ap_mac = ?")
            parameters.append(require_mac(ap_mac, "ap_mac"))
        if radio_id is not None:
            if type(radio_id) is not int:
                raise ObservationValidationError("radio_id must be integer")
            clauses.append("o.radio_id = ?")
            parameters.append(radio_id)
        return self._paged(
            table="client_observations",
            alias="o",
            order_column="observed_at",
            where=" AND ".join(clauses),
            parameters=tuple(parameters),
            limit=count,
            cursor=cursor,
            cycle_states=states,
            converter=_client_dto,
        )

    def get_latest_client_observation(
        self,
        site_id: str,
        client_mac: str,
        *,
        cycle_states: Sequence[str] = ("completed",),
    ) -> ClientObservation | None:
        return self._latest(
            table="client_observations",
            order_column="observed_at",
            where="o.site_id = ? AND o.client_mac = ?",
            parameters=(
                require_text(site_id, "site_id"),
                require_mac(client_mac, "client_mac"),
            ),
            cycle_states=_cycle_states(cycle_states),
            converter=_client_dto,
        )

    def get_ap_observations(
        self,
        site_id: str,
        ap_mac: str,
        from_utc: str,
        to_utc: str,
        limit: int = DEFAULT_QUERY_LIMIT,
        cursor: str | None = None,
        *,
        cycle_states: Sequence[str] = ("completed",),
    ) -> ObservationPage[ApObservation]:
        site, start, end, count, states = _common_query(
            site_id, from_utc, to_utc, limit, cycle_states
        )
        return self._paged(
            table="ap_observations",
            alias="o",
            order_column="observed_at",
            where=(
                "o.site_id = ? AND o.ap_mac = ? "
                "AND o.observed_at >= ? AND o.observed_at <= ?"
            ),
            parameters=(
                site,
                require_mac(ap_mac, "ap_mac"),
                start,
                end,
            ),
            limit=count,
            cursor=cursor,
            cycle_states=states,
            converter=_ap_dto,
        )

    def get_ap_radio_observations(
        self,
        site_id: str,
        ap_mac: str,
        from_utc: str,
        to_utc: str,
        *,
        band: str | None = None,
        limit: int = DEFAULT_QUERY_LIMIT,
        cursor: str | None = None,
        cycle_states: Sequence[str] = ("completed",),
    ) -> ObservationPage[ApRadioObservation]:
        site, start, end, count, states = _common_query(
            site_id, from_utc, to_utc, limit, cycle_states
        )
        clauses = [
            "o.site_id = ?",
            "o.ap_mac = ?",
            "o.radio_observed_at >= ?",
            "o.radio_observed_at <= ?",
        ]
        parameters: list[Any] = [
            site,
            require_mac(ap_mac, "ap_mac"),
            start,
            end,
        ]
        if band is not None:
            clauses.append("o.band = ?")
            parameters.append(require_text(band, "band"))
        return self._paged(
            table="ap_radio_observations",
            alias="o",
            order_column="radio_observed_at",
            where=" AND ".join(clauses),
            parameters=tuple(parameters),
            limit=count,
            cursor=cursor,
            cycle_states=states,
            converter=_radio_dto,
        )

    def get_latest_ap_observation(
        self,
        site_id: str,
        ap_mac: str,
        *,
        cycle_states: Sequence[str] = ("completed",),
    ) -> ApObservation | None:
        return self._latest(
            table="ap_observations",
            order_column="observed_at",
            where="o.site_id = ? AND o.ap_mac = ?",
            parameters=(
                require_text(site_id, "site_id"),
                require_mac(ap_mac, "ap_mac"),
            ),
            cycle_states=_cycle_states(cycle_states),
            converter=_ap_dto,
        )

    def get_latest_ap_radio_observations(
        self,
        site_id: str,
        ap_mac: str,
        *,
        cycle_states: Sequence[str] = ("completed",),
    ) -> tuple[ApRadioObservation, ...]:
        site = require_text(site_id, "site_id")
        mac = require_mac(ap_mac, "ap_mac")
        states = _cycle_states(cycle_states)
        placeholders = ",".join("?" for _ in states)
        try:
            with self._repository.read_connection() as connection:
                rows = connection.execute(
                    f"""
                    WITH ranked AS (
                        SELECT o.row_id,
                               ROW_NUMBER() OVER (
                                   PARTITION BY o.band
                                   ORDER BY o.radio_observed_at DESC,
                                            o.row_id DESC
                               ) AS latest_rank
                        FROM ap_radio_observations AS o
                        JOIN observation_cycles AS c
                          ON c.cycle_id = o.cycle_id
                        WHERE o.site_id = ? AND o.ap_mac = ?
                          AND c.state IN ({placeholders})
                    )
                    SELECT o.*
                    FROM ranked
                    JOIN ap_radio_observations AS o
                      ON o.row_id = ranked.row_id
                    WHERE ranked.latest_rank = 1
                    ORDER BY o.band
                    """,
                    (site, mac, *states),
                ).fetchall()
        except sqlite3.Error as exc:
            raise ObservationStorageError(classify_sqlite_error(exc)) from exc
        return tuple(_radio_dto(row) for row in rows)

    def get_latest_ap_config(
        self,
        site_id: str,
        ap_mac: str,
    ) -> ApConfigSnapshot | None:
        return self._latest(
            table="ap_config_snapshots",
            order_column="captured_at",
            where=(
                "o.site_id = ? AND o.ap_mac = ? "
                "AND c.state = 'completed' AND c.complete = 1"
            ),
            parameters=(
                require_text(site_id, "site_id"),
                require_mac(ap_mac, "ap_mac"),
            ),
            cycle_states=("completed",),
            converter=_config_dto,
        )

    def _paged(
        self,
        *,
        table: str,
        alias: str,
        order_column: str,
        where: str,
        parameters: tuple[Any, ...],
        limit: int,
        cursor: str | None,
        cycle_states: tuple[str, ...],
        converter: Callable[[sqlite3.Row], T],
    ) -> ObservationPage[T]:
        cursor_value = _decode_cursor(cursor)
        cursor_clause = ""
        cursor_parameters: tuple[Any, ...] = ()
        if cursor_value is not None:
            cursor_clause = (
                f" AND ({alias}.{order_column} > ? OR "
                f"({alias}.{order_column} = ? AND {alias}.row_id > ?))"
            )
            cursor_parameters = (
                cursor_value[0],
                cursor_value[0],
                cursor_value[1],
            )
        placeholders = ",".join("?" for _ in cycle_states)
        query = f"""
            SELECT {alias}.*
            FROM {table} AS {alias}
            JOIN observation_cycles AS c ON c.cycle_id = {alias}.cycle_id
            WHERE {where}
              AND c.state IN ({placeholders})
              {cursor_clause}
            ORDER BY {alias}.{order_column}, {alias}.row_id
            LIMIT ?
        """
        try:
            with self._repository.read_connection() as connection:
                rows = connection.execute(
                    query,
                    (
                        *parameters,
                        *cycle_states,
                        *cursor_parameters,
                        limit + 1,
                    ),
                ).fetchall()
        except sqlite3.Error as exc:
            raise ObservationStorageError(classify_sqlite_error(exc)) from exc
        has_more = len(rows) > limit
        selected = rows[:limit]
        items = tuple(converter(row) for row in selected)
        next_cursor = None
        if has_more and selected:
            last = selected[-1]
            next_cursor = _encode_cursor(
                str(last[order_column]),
                int(last["row_id"]),
            )
        return ObservationPage(items=items, next_cursor=next_cursor)

    def _latest(
        self,
        *,
        table: str,
        order_column: str,
        where: str,
        parameters: tuple[Any, ...],
        cycle_states: tuple[str, ...],
        converter: Callable[[sqlite3.Row], T],
    ) -> T | None:
        placeholders = ",".join("?" for _ in cycle_states)
        try:
            with self._repository.read_connection() as connection:
                row = connection.execute(
                    f"""
                    SELECT o.*
                    FROM {table} AS o
                    JOIN observation_cycles AS c ON c.cycle_id = o.cycle_id
                    WHERE {where} AND c.state IN ({placeholders})
                    ORDER BY o.{order_column} DESC, o.row_id DESC
                    LIMIT 1
                    """,
                    (*parameters, *cycle_states),
                ).fetchone()
        except sqlite3.Error as exc:
            category = classify_sqlite_error(exc)
            raise ObservationStorageError(category) from exc
        return None if row is None else converter(row)


def _common_query(
    site_id: str,
    from_utc: str,
    to_utc: str,
    limit: int,
    cycle_states: Sequence[str],
) -> tuple[str, str, str, int, tuple[str, ...]]:
    site = require_text(site_id, "site_id")
    start = require_utc(from_utc, "from_utc")
    end = require_utc(to_utc, "to_utc")
    if parse_utc(start, "from_utc") > parse_utc(end, "to_utc"):
        raise ObservationValidationError("from_utc must not exceed to_utc")
    return site, start, end, require_limit(limit), _cycle_states(cycle_states)


def _cycle_states(values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, str):
        raise ObservationValidationError("cycle_states must be a sequence")
    result = tuple(values)
    if not result or any(value not in CYCLE_STATES for value in result):
        raise ObservationValidationError("cycle_states contains invalid state")
    return tuple(dict.fromkeys(result))


def _encode_cursor(timestamp: str, row_id: int) -> str:
    payload = json.dumps(
        {"v": _CURSOR_VERSION, "t": timestamp, "i": row_id},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_cursor(value: str | None) -> tuple[str, int] | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value or len(value) > _MAX_CURSOR_LENGTH:
        raise ObservationValidationError("cursor is malformed")
    try:
        padding = "=" * (-len(value) % 4)
        raw = base64.b64decode(
            value + padding,
            altchars=b"-_",
            validate=True,
        )
        payload = json.loads(raw.decode("ascii"))
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise ObservationValidationError("cursor is malformed") from exc
    if (
        not isinstance(payload, dict)
        or set(payload) != {"v", "t", "i"}
        or payload.get("v") != _CURSOR_VERSION
        or type(payload.get("i")) is not int
        or payload["i"] <= 0
    ):
        raise ObservationValidationError("cursor is malformed")
    timestamp = require_utc(payload.get("t"), "cursor timestamp")
    return timestamp, int(payload["i"])


def _data(row: sqlite3.Row, excluded: Iterable[str]) -> Mapping[str, Any]:
    values = dict(row)
    for name in excluded:
        values.pop(name, None)
    for name in _BOOLEAN_DATA_COLUMNS.intersection(values):
        if values[name] is not None:
            values[name] = bool(values[name])
    return values


def _client_dto(row: sqlite3.Row) -> ClientObservation:
    return ClientObservation(
        row_id=int(row["row_id"]),
        cycle_id=str(row["cycle_id"]),
        observed_at=str(row["observed_at"]),
        site_id=str(row["site_id"]),
        client_mac=str(row["client_mac"]),
        source_inventory_complete=bool(row["source_inventory_complete"]),
        ssid=row["ssid"],
        ap_mac=row["ap_mac"],
        radio_id=row["radio_id"],
        data=_data(row, _CLIENT_CORE),
    )


def _ap_dto(row: sqlite3.Row) -> ApObservation:
    return ApObservation(
        row_id=int(row["row_id"]),
        cycle_id=str(row["cycle_id"]),
        observed_at=str(row["observed_at"]),
        site_id=str(row["site_id"]),
        ap_mac=str(row["ap_mac"]),
        partial=bool(row["partial"]),
        data=_data(row, _AP_CORE),
    )


def _radio_dto(row: sqlite3.Row) -> ApRadioObservation:
    return ApRadioObservation(
        row_id=int(row["row_id"]),
        cycle_id=str(row["cycle_id"]),
        ap_observation_row_id=int(row["ap_observation_row_id"]),
        radio_observed_at=str(row["radio_observed_at"]),
        site_id=str(row["site_id"]),
        ap_mac=str(row["ap_mac"]),
        band=str(row["band"]),
        data=_data(row, _RADIO_CORE),
    )


def _config_dto(row: sqlite3.Row) -> ApConfigSnapshot:
    return ApConfigSnapshot(
        row_id=int(row["row_id"]),
        cycle_id=str(row["cycle_id"]),
        captured_at=str(row["captured_at"]),
        site_id=str(row["site_id"]),
        ap_mac=str(row["ap_mac"]),
        config_sha256=str(row["config_sha256"]),
        schema_version=int(row["schema_version"]),
        config_json=str(row["config_json"]),
    )
