"""Bounded, read-only SQL composition behind existing source read services."""

from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterable, Iterator, Mapping, Sequence

from app.observations.read_service import ObservationReadService
from app.visit_lifecycle.read_service import VisitLifecycleReadService
from app.visitor_registry.registry_read_service import (
    VisitorRegistryReadService,
)


SOURCE_SCHEMA_VERSIONS = {
    "observations": 1,
    "visits": 2,
    "registry": 1,
}
MAX_CROSS_SOURCE_IDENTIFIERS = 250_000
_SQLITE_PROGRESS_OPCODES = 100
_SNAPSHOT_BATCH_SIZE = 800

CLIENT_FIELDS = frozenset({
    "ap_mac", "radio_id", "band", "channel", "rssi", "snr",
    "traffic_down", "traffic_up",
})
AP_FIELDS = frozenset({"cpu_util", "mem_util"})
RADIO_FIELDS = frozenset({
    "busy_util", "tx_util", "rx_util", "interference_util",
    "rx_retry_packets", "tx_retry_packets",
    "rx_error_packets", "tx_error_packets",
    "rx_drop_packets", "tx_drop_packets",
    "radio_rx_mbps", "radio_tx_mbps",
})
FIELD_ALLOWLIST = {
    "client": CLIENT_FIELDS,
    "ap": AP_FIELDS,
    "radio": RADIO_FIELDS,
}


class AnalyticsSourceError(RuntimeError):
    """A source cannot satisfy the read-only Analytics contract."""


class AnalyticsSourceUnavailable(AnalyticsSourceError):
    """A source database or its schema is unavailable."""


class AnalyticsQueryDeadlineExceeded(AnalyticsSourceError):
    """The hard monotonic query deadline interrupted SQLite."""


class AnalyticsPerformanceBudgetExceeded(AnalyticsSourceError):
    """A cross-source query would exceed the bounded materialization cap."""


@dataclass(frozen=True, slots=True)
class QueryDeadline:
    expires_at: float
    monotonic: Any = time.monotonic

    @classmethod
    def after(
        cls,
        seconds: float,
        *,
        monotonic=time.monotonic,
    ) -> "QueryDeadline":
        return cls(monotonic() + seconds, monotonic)

    def expired(self) -> bool:
        return self.monotonic() >= self.expires_at

    def require_remaining(self) -> None:
        if self.expired():
            raise AnalyticsQueryDeadlineExceeded(
                "Analytics query deadline exceeded"
            )


@dataclass(frozen=True, slots=True)
class ResolvedSnapshotLinks:
    resolved_links: frozenset[tuple[str, str]]
    matched_link_count: int
    watermark: str | None


class AnalyticsSourceGateway:
    """Read persisted facts without owning, migrating, or mutating sources."""

    def __init__(
        self,
        observation_read_service: ObservationReadService,
        visit_read_service: VisitLifecycleReadService,
        registry_read_service: VisitorRegistryReadService,
    ):
        self._observations = observation_read_service
        self._visits = visit_read_service
        self._registry = registry_read_service

    def cycle_quality(
        self,
        *,
        site_id: str,
        kind: str,
        from_utc: str,
        to_utc: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        if kind not in {"client", "ap_dynamic", "ap_config"}:
            raise ValueError("unsupported observation cycle kind")
        with self._connection("observations", deadline) as connection:
            row = self._one(
                connection,
                """
                SELECT
                    COUNT(*) AS row_count,
                    COALESCE(SUM(state='running'), 0) AS running,
                    COALESCE(SUM(state='completed'), 0) AS completed,
                    COALESCE(SUM(state='abandoned'), 0) AS abandoned,
                    COALESCE(SUM(
                        state='completed' AND complete=1
                    ), 0) AS completed_complete,
                    COALESCE(SUM(
                        state='completed' AND complete=0
                    ), 0) AS completed_incomplete,
                    COALESCE(SUM(
                        state='completed' AND result='success'
                    ), 0) AS success,
                    COALESCE(SUM(
                        state='completed' AND result='partial'
                    ), 0) AS partial,
                    COALESCE(SUM(
                        state='completed' AND result='failed'
                    ), 0) AS failed,
                    COALESCE(SUM(
                        state='completed' AND result='shutdown'
                    ), 0) AS shutdown,
                    MAX(CASE
                        WHEN state='completed'
                         AND complete=1
                         AND result='success'
                        THEN finished_at
                    END) AS latest_accepted_at
                FROM observation_cycles
                WHERE site_id=? AND kind=?
                  AND started_at>=? AND started_at<?
                """,
                (site_id, kind, from_utc, to_utc),
                deadline,
            )
        return dict(row)

    def field_completeness(
        self,
        *,
        site_id: str,
        source: str,
        from_utc: str,
        to_utc: str,
        fields: Sequence[str],
        quality_mode: str,
        deadline: QueryDeadline,
    ) -> tuple[Mapping[str, Any], ...]:
        allowed = FIELD_ALLOWLIST.get(source)
        selected = tuple(dict.fromkeys(fields))
        if allowed is None or not selected or any(
            field not in allowed for field in selected
        ):
            raise ValueError("fields are outside the approved allowlist")
        spec = _field_source_spec(source)
        strict = spec["strict"]
        accepted = strict if quality_mode == "strict_complete" else "1"
        projections = ",\n".join(
            f"COALESCE(SUM(CASE WHEN ({accepted}) "
            f"AND o.{field} IS NOT NULL THEN 1 ELSE 0 END), 0) "
            f"AS non_null_{field}"
            for field in selected
        )
        with self._connection("observations", deadline) as connection:
            row = self._one(
                connection,
                f"""
                SELECT
                    COUNT(*) AS rows_examined,
                    COALESCE(SUM(CASE WHEN ({accepted}) THEN 1 ELSE 0 END), 0)
                        AS rows_accepted,
                    COUNT(*) - COALESCE(SUM(
                        CASE WHEN ({accepted}) THEN 1 ELSE 0 END
                    ), 0) AS rows_rejected,
                    COUNT(DISTINCT CASE
                        WHEN c.state='completed'
                         AND (c.complete<>1 OR c.result<>'success')
                        THEN c.cycle_id END
                    ) AS partial_cycle_count,
                    {projections},
                    MAX(CASE WHEN ({accepted}) THEN {spec["time"]} END)
                        AS latest_accepted_at
                FROM {spec["from"]}
                WHERE o.site_id=? AND {spec["time"]}>=? AND {spec["time"]}<?
                """,
                (site_id, from_utc, to_utc),
                deadline,
            )
        common = dict(row)
        return tuple({
            "field": field,
            "row_count": int(common["rows_accepted"]),
            "non_null_count": int(common[f"non_null_{field}"]),
            "rows_examined": int(common["rows_examined"]),
            "rows_rejected": int(common["rows_rejected"]),
            "partial_cycle_count": int(common["partial_cycle_count"]),
            "latest_accepted_at": common["latest_accepted_at"],
        } for field in selected)

    def visit_population(
        self,
        *,
        site_id: str,
        from_utc: str,
        to_utc: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        where = _visit_overlap_where()
        with self._connection("visits", deadline) as connection:
            row = self._one(
                connection,
                f"""
                SELECT
                    COUNT(*) AS total,
                    COALESCE(SUM(v.device_id IS NOT NULL), 0) AS linked,
                    COALESCE(SUM(v.initial_snapshot_id IS NOT NULL), 0)
                        AS snapshot_linked,
                    COALESCE(SUM(v.status='open'), 0) AS open_count,
                    COALESCE(SUM(v.status='closed'), 0) AS closed_count,
                    COALESCE(SUM(EXISTS(
                        SELECT 1 FROM visit_authorizations a
                        WHERE a.visit_id=v.visit_id
                    )), 0) AS authorization_attached,
                    MAX(COALESCE(v.closed_at, v.started_at)) AS watermark
                FROM visits v
                WHERE {where}
                """,
                (site_id, from_utc, to_utc),
                deadline,
            )
        return dict(row)

    def initial_snapshot_links(
        self,
        *,
        site_id: str,
        from_utc: str,
        to_utc: str,
        deadline: QueryDeadline,
    ) -> tuple[tuple[str, str], ...]:
        with self._connection("visits", deadline) as connection:
            rows = self._all(
                connection,
                f"""
                SELECT initial_snapshot_id, client_mac
                FROM visits v
                WHERE {_visit_overlap_where()}
                  AND initial_snapshot_id IS NOT NULL
                ORDER BY started_at, visit_id
                LIMIT ?
                """,
                (
                    site_id,
                    from_utc,
                    to_utc,
                    MAX_CROSS_SOURCE_IDENTIFIERS + 1,
                ),
                deadline,
            )
        if len(rows) > MAX_CROSS_SOURCE_IDENTIFIERS:
            raise AnalyticsPerformanceBudgetExceeded(
                "snapshot link population exceeds materialization budget"
            )
        return tuple(
            (str(row["initial_snapshot_id"]), str(row["client_mac"]))
            for row in rows
        )

    def resolved_snapshot_links(
        self,
        *,
        site_id: str,
        links: Sequence[tuple[str, str]],
        deadline: QueryDeadline,
    ) -> ResolvedSnapshotLinks:
        if not links:
            return ResolvedSnapshotLinks(frozenset(), 0, None)
        resolved: set[tuple[str, str]] = set()
        expected = frozenset(links)
        identifiers = tuple(dict.fromkeys(link[0] for link in links))
        watermark: str | None = None
        with self._connection("registry", deadline) as connection:
            for offset in range(0, len(identifiers), _SNAPSHOT_BATCH_SIZE):
                deadline.require_remaining()
                batch = identifiers[offset:offset + _SNAPSHOT_BATCH_SIZE]
                placeholders = ",".join("?" for _ in batch)
                rows = self._all(
                    connection,
                    f"""
                    SELECT snapshot_id, requested_mac, captured_at
                    FROM device_snapshots
                    WHERE site_id=? AND snapshot_id IN ({placeholders})
                    """,
                    (site_id, *batch),
                    deadline,
                )
                for row in rows:
                    captured_at = str(row["captured_at"])
                    watermark = max(watermark or captured_at, captured_at)
                    link = (
                        str(row["snapshot_id"]),
                        str(row["requested_mac"]),
                    )
                    if link in expected:
                        resolved.add(link)
        return ResolvedSnapshotLinks(
            resolved_links=frozenset(resolved),
            matched_link_count=sum(1 for link in links if link in resolved),
            watermark=watermark,
        )

    def visit_quality_page(
        self,
        *,
        site_id: str,
        from_utc: str,
        to_utc: str,
        status: str | None,
        cursor: tuple[str, str] | None,
        limit: int,
        deadline: QueryDeadline,
    ) -> tuple[Mapping[str, Any], ...]:
        clauses = [_visit_overlap_where()]
        parameters: list[Any] = [site_id, from_utc, to_utc]
        if status is not None:
            clauses.append("v.status=?")
            parameters.append(status)
        if cursor is not None:
            clauses.append(
                "(v.started_at<? OR "
                "(v.started_at=? AND v.visit_id<?))"
            )
            parameters.extend((cursor[0], cursor[0], cursor[1]))
        parameters.append(limit)
        with self._connection("visits", deadline) as connection:
            rows = self._all(
                connection,
                f"""
                SELECT
                    v.visit_id, v.site_id, v.client_mac, v.device_id,
                    v.initial_snapshot_id, v.started_at, v.closed_at,
                    v.status, v.duration_seconds,
                    COUNT(a.row_id) AS authorization_count
                FROM visits v
                LEFT JOIN visit_authorizations a ON a.visit_id=v.visit_id
                WHERE {' AND '.join(clauses)}
                GROUP BY v.visit_id
                ORDER BY v.started_at DESC, v.visit_id DESC
                LIMIT ?
                """,
                tuple(parameters),
                deadline,
            )
        return tuple(dict(row) for row in rows)

    def visit_by_id(
        self,
        *,
        site_id: str,
        visit_id: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any] | None:
        with self._connection("visits", deadline) as connection:
            row = self._one(
                connection,
                """
                SELECT v.*, COUNT(a.row_id) AS authorization_count
                FROM visits v
                LEFT JOIN visit_authorizations a ON a.visit_id=v.visit_id
                WHERE v.site_id=? AND v.visit_id=?
                GROUP BY v.visit_id
                """,
                (site_id, visit_id),
                deadline,
            )
        return None if row is None else dict(row)

    def snapshot_by_id(
        self,
        *,
        site_id: str,
        snapshot_id: str,
        requested_mac: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any] | None:
        with self._connection("registry", deadline) as connection:
            row = self._one(
                connection,
                """
                SELECT snapshot_id, device_id, auth_session_id, site_id,
                       requested_mac, authorized_at, captured_at,
                       device_type, ssid, ap_mac, radio_id, channel,
                       rssi, snr, traffic_down, traffic_up
                FROM device_snapshots
                WHERE site_id=? AND snapshot_id=? AND requested_mac=?
                LIMIT 1
                """,
                (site_id, snapshot_id, requested_mac),
                deadline,
            )
        return None if row is None else dict(row)

    def registry_device(
        self,
        *,
        device_id: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any] | None:
        with self._connection("registry", deadline) as connection:
            row = self._one(
                connection,
                """
                SELECT device_id, mac, first_seen_at, last_seen_at,
                       last_site_id, last_ip, last_ssid, last_ap_name,
                       last_ap_mac, last_rssi, last_snr, snapshot_count
                FROM visitor_devices WHERE device_id=? LIMIT 1
                """,
                (device_id,),
                deadline,
            )
        return None if row is None else dict(row)

    def observation_coverage(
        self,
        *,
        site_id: str,
        client_mac: str,
        from_utc: str,
        to_utc: str,
        gap_threshold_seconds: float,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        with self._connection("observations", deadline) as connection:
            row = self._one(
                connection,
                """
                WITH accepted AS (
                    SELECT o.observed_at, o.row_id
                    FROM client_observations o
                    JOIN observation_cycles c ON c.cycle_id=o.cycle_id
                    WHERE o.site_id=? AND o.client_mac=?
                      AND o.observed_at>=? AND o.observed_at<?
                      AND c.state='completed' AND c.complete=1
                      AND c.result='success'
                      AND o.source_inventory_complete=1
                ),
                ordered AS (
                    SELECT observed_at, row_id,
                           LAG(observed_at) OVER (
                               ORDER BY observed_at, row_id
                           ) AS previous_at
                    FROM accepted
                ),
                gaps AS (
                    SELECT observed_at,
                           CASE WHEN previous_at IS NULL THEN NULL ELSE
                             (julianday(observed_at)-julianday(previous_at))
                             * 86400.0
                           END AS gap_seconds
                    FROM ordered
                )
                SELECT COUNT(*) AS sample_count,
                       MIN(observed_at) AS first_observed_at,
                       MAX(observed_at) AS last_observed_at,
                       MAX(gap_seconds) AS max_gap_seconds,
                       COALESCE(SUM(gap_seconds>?), 0)
                           AS gap_count_over_threshold
                FROM gaps
                """,
                (
                    site_id,
                    client_mac,
                    from_utc,
                    to_utc,
                    gap_threshold_seconds,
                ),
                deadline,
            )
        return dict(row)

    def source_event_quality(
        self,
        *,
        site_id: str,
        from_utc: str,
        to_utc: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Mapping[str, int]]:
        with self._connection("visits", deadline) as connection:
            rows = self._all(
                connection,
                """
                SELECT processing_result, reason, COUNT(*) AS count
                FROM visit_source_events
                WHERE site_id=? AND processed_at>=? AND processed_at<?
                GROUP BY processing_result, reason
                """,
                (site_id, from_utc, to_utc),
                deadline,
            )
        by_result: dict[str, int] = {}
        by_reason: dict[str, int] = {}
        for row in rows:
            result = str(row["processing_result"])
            count = int(row["count"])
            by_result[result] = by_result.get(result, 0) + count
            if row["reason"] is not None:
                reason = str(row["reason"])
                by_reason[reason] = by_reason.get(reason, 0) + count
        return {
            "by_processing_result": by_result,
            "by_reason": by_reason,
        }

    def observation_watermarks(
        self,
        *,
        site_id: str,
        from_utc: str,
        to_utc: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, str | None]:
        with self._connection("observations", deadline) as connection:
            row = self._one(
                connection,
                """
                SELECT
                  (SELECT MAX(o.observed_at)
                   FROM client_observations o
                   JOIN observation_cycles c ON c.cycle_id=o.cycle_id
                   WHERE o.site_id=? AND o.observed_at>=? AND o.observed_at<?
                     AND c.state='completed' AND c.complete=1
                     AND c.result='success'
                     AND o.source_inventory_complete=1) AS client,
                  (SELECT MAX(o.observed_at)
                   FROM ap_observations o
                   JOIN observation_cycles c ON c.cycle_id=o.cycle_id
                   WHERE o.site_id=? AND o.observed_at>=? AND o.observed_at<?
                     AND c.state='completed' AND c.complete=1
                     AND c.result='success' AND o.partial=0) AS ap,
                  (SELECT MAX(r.radio_observed_at)
                   FROM ap_radio_observations r
                   JOIN ap_observations o
                     ON o.row_id=r.ap_observation_row_id
                   JOIN observation_cycles c ON c.cycle_id=r.cycle_id
                   WHERE r.site_id=? AND r.radio_observed_at>=?
                     AND r.radio_observed_at<?
                     AND c.state='completed' AND c.complete=1
                     AND c.result='success' AND o.partial=0
                     AND o.radios_ok=1) AS radio
                """,
                (
                    site_id, from_utc, to_utc,
                    site_id, from_utc, to_utc,
                    site_id, from_utc, to_utc,
                ),
                deadline,
            )
        return dict(row)

    def registry_watermark(
        self,
        *,
        site_id: str,
        from_utc: str,
        to_utc: str,
        deadline: QueryDeadline,
    ) -> str | None:
        with self._connection("registry", deadline) as connection:
            row = self._one(
                connection,
                """
                SELECT MAX(captured_at) AS watermark
                FROM device_snapshots
                WHERE site_id=? AND captured_at>=? AND captured_at<?
                """,
                (site_id, from_utc, to_utc),
                deadline,
            )
        return None if row is None else row["watermark"]

    @contextmanager
    def _connection(
        self,
        source: str,
        deadline: QueryDeadline,
    ) -> Iterator[sqlite3.Connection]:
        deadline.require_remaining()
        service = {
            "observations": self._observations,
            "visits": self._visits,
            "registry": self._registry,
        }[source]
        try:
            with service.analytics_read_connection() as connection:
                connection.execute("PRAGMA query_only=ON")
                version = self._one(
                    connection, "PRAGMA user_version", (), deadline
                )
                if version is None or int(version[0]) != SOURCE_SCHEMA_VERSIONS[source]:
                    raise AnalyticsSourceUnavailable(
                        f"{source} schema version is unavailable"
                    )
                yield connection
        except AnalyticsSourceError:
            raise
        except (sqlite3.Error, OSError, ValueError) as exc:
            raise AnalyticsSourceUnavailable(
                f"{source} read is unavailable"
            ) from exc

    def _one(
        self,
        connection: sqlite3.Connection,
        sql: str,
        parameters: Iterable[Any],
        deadline: QueryDeadline,
    ) -> sqlite3.Row | None:
        with _statement_deadline(connection, deadline):
            try:
                return connection.execute(sql, tuple(parameters)).fetchone()
            except sqlite3.OperationalError as exc:
                _translate_sqlite_error(exc, deadline)
                raise

    def _all(
        self,
        connection: sqlite3.Connection,
        sql: str,
        parameters: Iterable[Any],
        deadline: QueryDeadline,
    ) -> list[sqlite3.Row]:
        with _statement_deadline(connection, deadline):
            try:
                return connection.execute(sql, tuple(parameters)).fetchall()
            except sqlite3.OperationalError as exc:
                _translate_sqlite_error(exc, deadline)
                raise


@contextmanager
def _statement_deadline(
    connection: sqlite3.Connection,
    deadline: QueryDeadline,
) -> Iterator[None]:
    deadline.require_remaining()

    def interrupted() -> int:
        return int(deadline.expired())

    connection.set_progress_handler(interrupted, _SQLITE_PROGRESS_OPCODES)
    try:
        yield
    finally:
        connection.set_progress_handler(None, 0)


def _translate_sqlite_error(
    exc: sqlite3.OperationalError,
    deadline: QueryDeadline,
) -> None:
    if deadline.expired() or "interrupted" in str(exc).lower():
        raise AnalyticsQueryDeadlineExceeded(
            "Analytics SQLite statement exceeded its deadline"
        ) from exc


def _visit_overlap_where() -> str:
    return (
        "v.site_id=? AND (v.closed_at IS NULL OR v.closed_at>?) "
        "AND v.started_at<?"
    )


def _field_source_spec(source: str) -> Mapping[str, str]:
    if source == "client":
        return {
            "from": (
                "client_observations o "
                "JOIN observation_cycles c ON c.cycle_id=o.cycle_id"
            ),
            "time": "o.observed_at",
            "strict": (
                "c.state='completed' AND c.complete=1 "
                "AND c.result='success' "
                "AND o.source_inventory_complete=1"
            ),
        }
    if source == "ap":
        return {
            "from": (
                "ap_observations o "
                "JOIN observation_cycles c ON c.cycle_id=o.cycle_id"
            ),
            "time": "o.observed_at",
            "strict": (
                "c.state='completed' AND c.complete=1 "
                "AND c.result='success' AND o.partial=0 "
                "AND o.overview_ok=1"
            ),
        }
    return {
        "from": (
            "ap_radio_observations o "
            "JOIN ap_observations p ON p.row_id=o.ap_observation_row_id "
            "JOIN observation_cycles c ON c.cycle_id=o.cycle_id"
        ),
        "time": "o.radio_observed_at",
        "strict": (
            "c.state='completed' AND c.complete=1 "
            "AND c.result='success' AND p.partial=0 "
            "AND p.radios_ok=1 AND p.site_id=o.site_id "
            "AND p.ap_mac=o.ap_mac AND p.cycle_id=o.cycle_id"
        ),
    }
