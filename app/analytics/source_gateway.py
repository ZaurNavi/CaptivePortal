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
_VISIT_WINDOW_BATCH_SIZE = 100

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
WIRELESS_SCALAR_FIELDS = {
    "client": frozenset({"rssi", "snr"}),
    "ap": frozenset({"cpu_util", "mem_util"}),
    "radio": frozenset({
        "tx_util", "rx_util", "interference_util", "busy_util",
    }),
}
CLIENT_CONTEXT_FIELDS = frozenset({"ap_mac", "ssid", "band", "channel"})
STORED_RATE_FIELDS = {
    "wired_download_mbps": ("ap", "wired_download_rate_reason"),
    "wired_upload_mbps": ("ap", "wired_upload_rate_reason"),
    "lan_rx_mbps": ("ap", "lan_rx_rate_reason"),
    "lan_tx_mbps": ("ap", "lan_tx_rate_reason"),
    "radio_rx_mbps": ("radio", "radio_rx_rate_reason"),
    "radio_tx_mbps": ("radio", "radio_tx_rate_reason"),
}
CLIENT_COUNTER_FIELDS = {
    "client_download_mbps": "traffic_down",
    "client_upload_mbps": "traffic_up",
}
RADIO_COUNTER_FIELDS = {
    "rx_retry_delta": ("rx_retry_packets", "rx_packets"),
    "tx_retry_delta": ("tx_retry_packets", "tx_packets"),
    "rx_error_delta": ("rx_error_packets", "rx_packets"),
    "tx_error_delta": ("tx_error_packets", "tx_packets"),
    "rx_drop_delta": ("rx_drop_packets", "rx_packets"),
    "tx_drop_delta": ("tx_drop_packets", "tx_packets"),
    "rx_packet_delta": ("rx_packets", "rx_packets"),
    "tx_packet_delta": ("tx_packets", "tx_packets"),
}
FIELD_ALLOWLIST = {
    "client": CLIENT_FIELDS,
    "ap": AP_FIELDS,
    "radio": RADIO_FIELDS,
}

_NON_OK_RATE_REASONS_SQL = (
    "'no_baseline','counter_reset','gap_too_large','invalid_elapsed',"
    "'source_unavailable'"
)
_CANONICAL_MAC_SQL = (
    "ap_mac GLOB "
    "'[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:"
    "[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]'"
)


def _rate_ok_sql(value: str, reason: str, timestamp: str) -> str:
    return (
        f"({reason}='ok' AND {timestamp} IS NOT NULL "
        f"AND typeof({value}) IN ('integer','real') AND {value}>=0 "
        f"AND abs({value})<=1.7976931348623157e308)"
    )


def _rate_valid_sql(value: str, reason: str, timestamp: str) -> str:
    return (
        f"COALESCE(({_rate_ok_sql(value, reason, timestamp)} OR "
        f"({reason} IN ({_NON_OK_RATE_REASONS_SQL}) AND {value} IS NULL)),0)"
    )


_WIRED_DOWN_OK = _rate_ok_sql(
    "wired_download_mbps", "wired_download_rate_reason", "wired_observed_at"
)
_WIRED_UP_OK = _rate_ok_sql(
    "wired_upload_mbps", "wired_upload_rate_reason", "wired_observed_at"
)
_LAN_DOWN_OK = _rate_ok_sql(
    "lan_rx_mbps", "lan_rx_rate_reason", "lan_observed_at"
)
_LAN_UP_OK = _rate_ok_sql(
    "lan_tx_mbps", "lan_tx_rate_reason", "lan_observed_at"
)
_CURRENT_TRAFFIC_STATS_SQL = f"""
    SELECT
      COUNT(*) AS stored_row_count,
      COALESCE(SUM(site_id!=?),0) AS bad_site_count,
      COALESCE(SUM(NOT ({_CANONICAL_MAC_SQL})),0) AS bad_mac_count,
      COUNT(*)-COUNT(DISTINCT ap_mac) AS duplicate_mac_count,
      COALESCE(SUM(partial!=0 OR overview_ok!=1 OR wired_uplink_ok!=1
                   OR lan_traffic_ok!=1 OR radios_ok!=1),0) AS bad_flag_count,
      COALESCE(SUM(NOT ({_rate_valid_sql('wired_download_mbps', 'wired_download_rate_reason', 'wired_observed_at')})),0)
        + COALESCE(SUM(NOT ({_rate_valid_sql('wired_upload_mbps', 'wired_upload_rate_reason', 'wired_observed_at')})),0)
        + COALESCE(SUM(NOT ({_rate_valid_sql('lan_rx_mbps', 'lan_rx_rate_reason', 'lan_observed_at')})),0)
        + COALESCE(SUM(NOT ({_rate_valid_sql('lan_tx_mbps', 'lan_tx_rate_reason', 'lan_observed_at')})),0)
        AS bad_rate_count,
      COALESCE(SUM(wired_observed_at IS NULL),0) AS missing_wired_time_count,
      COALESCE(SUM(lan_observed_at IS NULL),0) AS missing_lan_time_count,
      MIN(wired_observed_at) AS wired_oldest,
      MAX(wired_observed_at) AS wired_newest,
      MIN(lan_observed_at) AS lan_oldest,
      MAX(lan_observed_at) AS lan_newest,
      COALESCE(SUM(({_WIRED_DOWN_OK}) AND ({_WIRED_UP_OK})),0)
        AS wired_pair_valid_count,
      COALESCE(SUM(({_LAN_DOWN_OK}) AND ({_LAN_UP_OK})),0)
        AS lan_pair_valid_count
    FROM ap_observations
    WHERE cycle_id=?
"""


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

    def current_traffic_data(
        self,
        *,
        site_id: str,
        cycle_id: str | None,
        after_ap_mac: str | None,
        page_limit: int | None,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        """Read one AP traffic snapshot in a single SQLite transaction."""
        with self._connection("observations", deadline) as connection:
            connection.execute("BEGIN")
            try:
                if cycle_id is None:
                    cycle = self._one(
                        connection,
                        """
                        SELECT * FROM observation_cycles
                        WHERE site_id=? AND kind='ap_dynamic'
                          AND state='completed' AND complete=1
                          AND result='success'
                        ORDER BY started_at DESC, cycle_id DESC
                        LIMIT 1
                        """,
                        (site_id,),
                        deadline,
                    )
                else:
                    cycle = self._one(
                        connection,
                        """
                        SELECT * FROM observation_cycles
                        WHERE site_id=? AND cycle_id=? AND kind='ap_dynamic'
                          AND state='completed' AND complete=1
                          AND result='success'
                        LIMIT 1
                        """,
                        (site_id, cycle_id),
                        deadline,
                    )
                latest = self._one(
                    connection,
                    """
                    SELECT cycle_id, state, result, started_at, finished_at
                    FROM observation_cycles
                    WHERE site_id=? AND kind='ap_dynamic'
                    ORDER BY started_at DESC, cycle_id DESC
                    LIMIT 1
                    """,
                    (site_id,),
                    deadline,
                )
                if cycle is None:
                    return {"cycle": None, "latest": latest, "stats": None,
                            "rows": ()}

                selected_cycle_id = str(cycle["cycle_id"])
                stats = self._one(
                    connection,
                    _CURRENT_TRAFFIC_STATS_SQL,
                    (site_id, selected_cycle_id),
                    deadline,
                )
                parameters: list[Any] = [selected_cycle_id]
                where = "cycle_id=?"
                if after_ap_mac is not None:
                    where += " AND ap_mac>?"
                    parameters.append(after_ap_mac)
                suffix = ""
                if page_limit is not None:
                    suffix = " LIMIT ?"
                    parameters.append(page_limit + 1)
                rows = self._all(
                    connection,
                    f"""
                    SELECT cycle_id, site_id, ap_mac, name,
                           partial, overview_ok, wired_uplink_ok,
                           lan_traffic_ok, radios_ok,
                           wired_observed_at, wired_download_mbps,
                           wired_upload_mbps,
                           wired_download_rate_reason,
                           wired_upload_rate_reason,
                           lan_observed_at, lan_rx_mbps, lan_tx_mbps,
                           lan_rx_rate_reason, lan_tx_rate_reason
                    FROM ap_observations
                    WHERE {where}
                    ORDER BY ap_mac ASC{suffix}
                    """,
                    parameters,
                    deadline,
                )
                deadline.require_remaining()
                return {
                    "cycle": cycle,
                    "latest": latest,
                    "stats": stats,
                    "rows": tuple(rows),
                }
            finally:
                connection.rollback()

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

    def source_event_watermark(
        self, *, site_id: str, from_utc: str, to_utc: str,
        deadline: QueryDeadline,
    ) -> str | None:
        with self._connection("visits", deadline) as connection:
            row = self._one(connection, """
              SELECT MAX(processed_at) watermark FROM visit_source_events
              WHERE site_id=? AND processed_at>=? AND processed_at<?
            """, (site_id, from_utc, to_utc), deadline)
        return None if row is None else row["watermark"]

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

    def visit_cohort_summary(
        self, *, site_id: str, from_utc: str, to_utc: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        with self._connection("visits", deadline) as connection:
            row = self._one(connection, """
                SELECT COUNT(*) total_visit_count,
                       COALESCE(SUM(status='open'),0) open_visit_count,
                       COALESCE(SUM(status='closed'),0) closed_visit_count,
                       MAX(started_at) watermark
                FROM visits
                WHERE site_id=? AND started_at>=? AND started_at<?
            """, (site_id, from_utc, to_utc), deadline)
        return dict(row)

    def visit_start_timestamps(
        self, *, site_id: str, from_utc: str, to_utc: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        with self._connection("visits", deadline) as connection:
            rows = self._all(connection, """
                SELECT started_at
                FROM visits
                WHERE site_id=? AND started_at>=? AND started_at<?
                ORDER BY started_at, visit_id LIMIT ?
            """, (site_id, from_utc, to_utc,
                    MAX_CROSS_SOURCE_IDENTIFIERS + 1), deadline)
        if len(rows) > MAX_CROSS_SOURCE_IDENTIFIERS:
            raise AnalyticsPerformanceBudgetExceeded(
                "Visit time-series cohort exceeds materialization budget")
        return {"rows": tuple(dict(row) for row in rows),
                "watermark": (None if not rows
                              else str(rows[-1]["started_at"]))}

    def visit_device_summary(
        self, *, site_id: str, from_utc: str, to_utc: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        with self._connection("visits", deadline) as connection:
            row = self._one(connection, """
                WITH cohort AS (
                  SELECT device_id, started_at FROM visits
                  WHERE site_id=? AND started_at>=? AND started_at<?
                ), grouped AS (
                  SELECT device_id, COUNT(*) visit_count FROM cohort
                  WHERE device_id IS NOT NULL GROUP BY device_id
                )
                SELECT (SELECT COUNT(DISTINCT device_id) FROM cohort
                        WHERE device_id IS NOT NULL) unique_linked_devices,
                       (SELECT COUNT(*) FROM cohort
                        WHERE device_id IS NOT NULL) linked_visit_count,
                       (SELECT COUNT(*) FROM cohort
                        WHERE device_id IS NULL) unlinked_visit_count,
                       (SELECT COUNT(*) FROM grouped
                        WHERE visit_count>=2) repeat_device_count,
                       (SELECT COUNT(*) FROM cohort) rows_examined,
                       (SELECT MAX(started_at) FROM cohort) watermark
            """, (site_id, from_utc, to_utc), deadline)
        return dict(row)

    def visit_new_to_site_summary(
        self, *, site_id: str, from_utc: str, to_utc: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        with self._connection("visits", deadline) as connection:
            row = self._one(connection, """
                WITH firsts AS (
                  SELECT device_id, MIN(started_at) first_started_at
                  FROM visits WHERE site_id=? AND device_id IS NOT NULL
                  GROUP BY device_id
                ), cohort_devices AS (
                  SELECT DISTINCT device_id FROM visits
                  WHERE site_id=? AND started_at>=? AND started_at<?
                    AND device_id IS NOT NULL
                ), cohort AS (
                  SELECT device_id, started_at FROM visits
                  WHERE site_id=? AND started_at>=? AND started_at<?
                )
                SELECT COUNT(cd.device_id) unique_linked_devices_in_window,
                       COALESCE(SUM(f.first_started_at>=?
                                AND f.first_started_at<?),0)
                           new_to_site_device_count,
                       COALESCE(SUM(f.first_started_at<?),0)
                           known_before_window_device_count,
                       (SELECT COUNT(*) FROM cohort WHERE device_id IS NULL)
                           unlinked_visit_count,
                       (SELECT COUNT(*) FROM cohort) rows_examined,
                       (SELECT MAX(started_at) FROM cohort) watermark
                FROM cohort_devices cd JOIN firsts f USING(device_id)
            """, (site_id, site_id, from_utc, to_utc,
                    site_id, from_utc, to_utc,
                    from_utc, to_utc, from_utc), deadline)
        return dict(row)

    def visit_duration_distribution(
        self, *, site_id: str, from_utc: str, to_utc: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        base = """
          SELECT rowid row_id, NULL cycle_id, NULL ap_mac,
                 started_at observed_at, duration_seconds value,
                 CASE WHEN status='closed' THEN 1 ELSE 0 END accepted,
                 NULL reason
          FROM visits WHERE site_id=? AND started_at>=? AND started_at<?
        """
        with self._connection("visits", deadline) as connection:
            result = dict(self._distribution_from_base(
                connection, base_sql=base,
                parameters=(site_id, from_utc, to_utc), threshold=None,
                deadline=deadline))
            excluded = self._one(connection, """
              SELECT COALESCE(SUM(status='open'),0) excluded_open_count,
                     COALESCE(SUM(status='closed' AND duration_seconds IS NULL),0)
                       excluded_missing_duration_count
              FROM visits WHERE site_id=? AND started_at>=? AND started_at<?
            """, (site_id, from_utc, to_utc), deadline)
        result.update(dict(excluded))
        return result

    def visit_authorization_distribution(
        self, *, site_id: str, from_utc: str, to_utc: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        base = """
          SELECT v.rowid row_id, NULL cycle_id, NULL ap_mac,
                 v.started_at observed_at, COUNT(a.row_id) value,
                 1 accepted, NULL reason
          FROM visits v LEFT JOIN visit_authorizations a
            ON a.visit_id=v.visit_id
          WHERE v.site_id=? AND v.started_at>=? AND v.started_at<?
          GROUP BY v.visit_id
        """
        with self._connection("visits", deadline) as connection:
            result = dict(self._distribution_from_base(
                connection, base_sql=base,
                parameters=(site_id, from_utc, to_utc), threshold=None,
                deadline=deadline))
            counts = self._one(connection, """
              WITH cohort AS (
                SELECT v.visit_id, COUNT(a.row_id) n FROM visits v
                LEFT JOIN visit_authorizations a ON a.visit_id=v.visit_id
                WHERE v.site_id=? AND v.started_at>=? AND v.started_at<?
                GROUP BY v.visit_id)
              SELECT COALESCE(SUM(n=1),0) exactly_one,
                     COALESCE(SUM(n>1),0) multiple,
                     COALESCE(SUM(n=0),0) zero FROM cohort
            """, (site_id, from_utc, to_utc), deadline)
        result.update(dict(counts))
        return result

    def visit_closure_summary(
        self, *, site_id: str, from_utc: str, to_utc: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        base = """
          SELECT rowid row_id, NULL cycle_id, NULL ap_mac,
                 started_at observed_at,
                 CASE WHEN reported_connected_seconds IS NOT NULL
                       AND duration_seconds IS NOT NULL
                      THEN reported_connected_seconds-duration_seconds END value,
                 CASE WHEN status='closed' THEN 1 ELSE 0 END accepted,
                 NULL reason
          FROM visits WHERE site_id=? AND started_at>=? AND started_at<?
        """
        with self._connection("visits", deadline) as connection:
            groups = self._all(connection, """
              SELECT close_reason, close_time_source, COUNT(*) count
              FROM visits WHERE site_id=? AND started_at>=? AND started_at<?
                AND status='closed'
              GROUP BY close_reason, close_time_source
            """, (site_id, from_utc, to_utc), deadline)
            dist = dict(self._distribution_from_base(
                connection, base_sql=base,
                parameters=(site_id, from_utc, to_utc), threshold=None,
                deadline=deadline))
        reasons: dict[str, int] = {}
        sources: dict[str, int] = {}
        for row in groups:
            n = int(row["count"])
            reasons[str(row["close_reason"])] = (
                reasons.get(str(row["close_reason"]), 0) + n)
            sources[str(row["close_time_source"])] = (
                sources.get(str(row["close_time_source"]), 0) + n)
        return {"close_reasons": reasons, "close_time_sources": sources,
                "closed_visit_count": sum(reasons.values()),
                "duration_difference": dist}

    def visit_context_distribution(
        self, *, site_id: str, from_utc: str, to_utc: str,
        dimension: str, deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        columns = {
            "start_ssid": ("v.start_ssid", False),
            "final_ssid": ("v.final_ssid", False),
            "start_ap_mac": ("v.start_ap_mac", False),
            "final_ap_mac": ("v.final_ap_mac", False),
            "touched_ssid": ("a.portal_ssid", True),
            "touched_ap_mac": ("a.portal_ap_mac", True),
        }
        if dimension not in columns:
            raise ValueError("unsupported Visit context dimension")
        column, touched = columns[dimension]
        join = "JOIN visit_authorizations a ON a.visit_id=v.visit_id" if touched else ""
        count = "COUNT(DISTINCT v.visit_id)" if touched else "COUNT(*)"
        with self._connection("visits", deadline) as connection:
            rows = self._all(connection, f"""
              SELECT {column} context, {count} visit_count
              FROM visits v {join}
              WHERE v.site_id=? AND v.started_at>=? AND v.started_at<?
              GROUP BY {column} ORDER BY visit_count DESC, context
            """, (site_id, from_utc, to_utc), deadline)
            meta = self._one(connection, """
              SELECT COUNT(*) rows_examined, MAX(started_at) watermark
              FROM visits WHERE site_id=? AND started_at>=? AND started_at<?
            """, (site_id, from_utc, to_utc), deadline)
        return {"rows": tuple(dict(row) for row in rows),
                "rows_examined": int(meta["rows_examined"]),
                "watermark": meta["watermark"]}

    def visit_context_transitions(
        self, *, site_id: str, from_utc: str, to_utc: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        with self._connection("visits", deadline) as connection:
            row = self._one(connection, """
              SELECT COUNT(*) rows_examined, MAX(started_at) watermark,
                COALESCE(SUM(start_ssid IS NOT NULL AND final_ssid IS NOT NULL),0) ssid_comparable,
                COALESCE(SUM(start_ssid IS NOT NULL AND final_ssid IS NOT NULL AND start_ssid<>final_ssid),0) ssid_changed,
                COALESCE(SUM(start_ssid IS NOT NULL AND final_ssid IS NOT NULL AND start_ssid=final_ssid),0) ssid_unchanged,
                COALESCE(SUM(start_ssid IS NULL OR final_ssid IS NULL),0) ssid_missing,
                COALESCE(SUM(start_ap_mac IS NOT NULL AND final_ap_mac IS NOT NULL),0) ap_comparable,
                COALESCE(SUM(start_ap_mac IS NOT NULL AND final_ap_mac IS NOT NULL AND start_ap_mac<>final_ap_mac),0) ap_changed,
                COALESCE(SUM(start_ap_mac IS NOT NULL AND final_ap_mac IS NOT NULL AND start_ap_mac=final_ap_mac),0) ap_unchanged,
                COALESCE(SUM(start_ap_mac IS NULL OR final_ap_mac IS NULL),0) ap_missing
              FROM visits WHERE site_id=? AND started_at>=? AND started_at<?
            """, (site_id, from_utc, to_utc), deadline)
        return dict(row)

    def visit_windows(
        self, *, site_id: str, from_utc: str, to_utc: str,
        evaluation_at_utc: str, deadline: QueryDeadline,
    ) -> tuple[Mapping[str, Any], ...]:
        with self._connection("visits", deadline) as connection:
            rows = self._all(connection, """
              SELECT visit_id, client_mac, device_id, started_at, closed_at,
                     CASE WHEN closed_at IS NULL THEN ? ELSE closed_at END
                       evaluation_end,
                     reported_traffic_total_bytes,
                     reported_traffic_up_bytes,
                     reported_traffic_down_bytes
              FROM visits
              WHERE site_id=? AND started_at>=? AND started_at<?
              ORDER BY started_at, visit_id LIMIT ?
            """, (evaluation_at_utc, site_id, from_utc, to_utc,
                    MAX_CROSS_SOURCE_IDENTIFIERS + 1), deadline)
        if len(rows) > MAX_CROSS_SOURCE_IDENTIFIERS:
            raise AnalyticsPerformanceBudgetExceeded(
                "Visit cohort exceeds materialization budget")
        return tuple(dict(row) for row in rows)

    def visit_observation_coverage_batch(
        self, *, site_id: str, windows: Sequence[Mapping[str, Any]],
        gap_threshold_seconds: float, deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        if not windows:
            return {"rows": (), "rows_examined": 0, "rows_accepted": 0,
                    "watermark": None}
        results: list[Mapping[str, Any]] = []
        examined = 0
        accepted = 0
        watermark: str | None = None
        with self._connection("observations", deadline) as connection:
            for offset in range(0, len(windows), _VISIT_WINDOW_BATCH_SIZE):
                deadline.require_remaining()
                batch = windows[offset:offset + _VISIT_WINDOW_BATCH_SIZE]
                values = ",".join("(?,?,?,?,?)" for _ in batch)
                parameters: list[Any] = []
                for row in batch:
                    parameters.extend((row["visit_id"], site_id,
                                       row["client_mac"], row["started_at"],
                                       row["evaluation_end"]))
                parameters.append(gap_threshold_seconds)
                rows = self._all(connection, f"""
                  WITH windows(visit_id,site_id,client_mac,start_at,end_at) AS (
                    VALUES {values}
                  ), accepted AS (
                    SELECT w.visit_id, w.start_at, w.end_at,
                           o.observed_at, o.row_id
                    FROM windows w
                    LEFT JOIN client_observations o
                      ON o.site_id=w.site_id AND o.client_mac=w.client_mac
                     AND o.observed_at>=w.start_at AND o.observed_at<w.end_at
                    LEFT JOIN observation_cycles c ON c.cycle_id=o.cycle_id
                    WHERE o.row_id IS NULL OR (
                      c.state='completed' AND c.complete=1
                      AND c.result='success'
                      AND o.source_inventory_complete=1)
                  ), ordered AS (
                    SELECT *, LAG(observed_at) OVER (
                      PARTITION BY visit_id ORDER BY observed_at,row_id
                    ) previous_at FROM accepted
                  ), gaps AS (
                    SELECT *, CASE WHEN previous_at IS NULL THEN NULL ELSE
                      (julianday(observed_at)-julianday(previous_at))*86400.0
                    END gap_seconds FROM ordered
                  )
                  SELECT visit_id, MIN(start_at) start_at, MIN(end_at) end_at,
                         COUNT(observed_at) sample_count,
                         MIN(observed_at) first_observed_at,
                         MAX(observed_at) last_observed_at,
                         MAX(gap_seconds) max_gap_seconds,
                         COALESCE(SUM(gap_seconds>?),0)
                           gap_count_over_threshold
                  FROM gaps GROUP BY visit_id ORDER BY visit_id
                """, (*parameters,), deadline)
                for row in rows:
                    item = dict(row)
                    results.append(item)
                    examined += int(item["sample_count"])
                    accepted += int(item["sample_count"])
                    observed = item["last_observed_at"]
                    if observed is not None:
                        watermark = max(watermark or str(observed), str(observed))
        return {"rows": tuple(results), "rows_examined": examined,
                "rows_accepted": accepted, "watermark": watermark}

    def visit_observed_traffic_batch(
        self, *, site_id: str, windows: Sequence[Mapping[str, Any]],
        max_gap_seconds: float, deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        if not windows:
            return {"rows": (), "rows_examined": 0, "rows_accepted": 0,
                    "watermark": None}
        output: list[Mapping[str, Any]] = []
        examined = accepted = 0
        watermark: str | None = None
        with self._connection("observations", deadline) as connection:
            for offset in range(0, len(windows), _VISIT_WINDOW_BATCH_SIZE):
                batch = windows[offset:offset + _VISIT_WINDOW_BATCH_SIZE]
                values = ",".join("(?,?,?,?,?)" for _ in batch)
                parameters: list[Any] = []
                for row in batch:
                    parameters.extend((row["visit_id"], site_id,
                                       row["client_mac"], row["started_at"],
                                       row["evaluation_end"]))
                rows = self._all(connection, f"""
                  WITH windows(visit_id,site_id,client_mac,start_at,end_at) AS (
                    VALUES {values}
                  ), samples AS (
                    SELECT w.visit_id,o.observed_at,o.row_id,
                           o.traffic_down,o.traffic_up
                    FROM windows w JOIN client_observations o
                      ON o.site_id=w.site_id AND o.client_mac=w.client_mac
                     AND o.observed_at>=w.start_at AND o.observed_at<w.end_at
                    JOIN observation_cycles c ON c.cycle_id=o.cycle_id
                    WHERE c.state='completed' AND c.complete=1
                      AND c.result='success' AND o.source_inventory_complete=1
                  ), pairs AS (
                    SELECT *, LAG(observed_at) OVER (
                      PARTITION BY visit_id ORDER BY observed_at,row_id) prev_at,
                      LAG(traffic_down) OVER (
                      PARTITION BY visit_id ORDER BY observed_at,row_id) prev_down,
                      LAG(traffic_up) OVER (
                      PARTITION BY visit_id ORDER BY observed_at,row_id) prev_up
                    FROM samples
                  ), deltas AS (
                    SELECT *,
                      (julianday(observed_at)-julianday(prev_at))*86400.0 elapsed,
                      CASE WHEN prev_down IS NOT NULL AND traffic_down>=prev_down
                             AND ROUND((julianday(observed_at)-julianday(prev_at))*86400.0,3)>0
                             AND ROUND((julianday(observed_at)-julianday(prev_at))*86400.0,3)<=?
                           THEN traffic_down-prev_down END down_delta,
                      CASE WHEN prev_up IS NOT NULL AND traffic_up>=prev_up
                             AND ROUND((julianday(observed_at)-julianday(prev_at))*86400.0,3)>0
                             AND ROUND((julianday(observed_at)-julianday(prev_at))*86400.0,3)<=?
                           THEN traffic_up-prev_up END up_delta
                    FROM pairs
                  )
                  SELECT visit_id, COUNT(*) sample_count,
                         COALESCE(SUM(down_delta IS NOT NULL OR up_delta IS NOT NULL),0)
                           valid_interval_count,
                         SUM(down_delta) down_delta,
                         SUM(up_delta) up_delta,
                         MAX(observed_at) watermark
                  FROM deltas GROUP BY visit_id
                """, (*parameters, max_gap_seconds, max_gap_seconds), deadline)
                for row in rows:
                    item = dict(row); output.append(item)
                    examined += max(int(item["sample_count"]) - 1, 0)
                    accepted += int(item["valid_interval_count"])
                    observed = item["watermark"]
                    if observed is not None:
                        watermark = max(watermark or str(observed), str(observed))
        return {"rows": tuple(output), "rows_examined": examined,
                "rows_accepted": accepted,
                "rows_rejected": max(examined-accepted, 0),
                "watermark": watermark}

    def visit_return_intervals(
        self, *, site_id: str, from_utc: str, to_utc: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        base = """
          SELECT row_id, NULL cycle_id, NULL ap_mac,
                 started_at observed_at, interval_seconds value,
                 CASE WHEN interval_seconds>=0 THEN 1 ELSE 0 END accepted,
                 NULL reason
          FROM (
            SELECT rowid row_id, started_at,
              (julianday(started_at)-julianday(LAG(started_at) OVER (
                PARTITION BY device_id ORDER BY started_at,visit_id)))*86400.0
                interval_seconds
            FROM visits
            WHERE site_id=? AND device_id IS NOT NULL AND started_at<?
          ) WHERE started_at>=? AND started_at<? AND interval_seconds IS NOT NULL
        """
        with self._connection("visits", deadline) as connection:
            return self._distribution_from_base(
                connection, base_sql=base,
                parameters=(site_id, to_utc, from_utc, to_utc),
                threshold=None, deadline=deadline)

    def wireless_scalar_distribution(
        self,
        *,
        site_id: str,
        source: str,
        metric: str,
        from_utc: str,
        to_utc: str,
        quality_mode: str,
        filters: Mapping[str, Any],
        threshold: float | None,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        if metric not in WIRELESS_SCALAR_FIELDS.get(source, frozenset()):
            raise ValueError("unsupported wireless scalar metric")
        spec = _wireless_source_spec(source)
        filter_sql, filter_parameters = _wireless_filters(
            source, filters, alias="o"
        )
        accepted = (
            spec["strict"]
            if quality_mode == "strict_complete"
            else spec["diagnostic"]
        )
        base_sql = f"""
            SELECT o.row_id, o.cycle_id, o.ap_mac,
                   {spec['time']} AS observed_at,
                   o.{metric} AS value,
                   CASE WHEN ({accepted}) THEN 1 ELSE 0 END AS accepted,
                   NULL AS reason
            FROM {spec['from']}
            WHERE o.site_id=? AND {spec['time']}>=? AND {spec['time']}<?
              {filter_sql}
        """
        with self._connection("observations", deadline) as connection:
            return self._distribution_from_base(
                connection,
                base_sql=base_sql,
                parameters=(
                    site_id, from_utc, to_utc, *filter_parameters,
                ),
                threshold=threshold,
                deadline=deadline,
            )

    def client_context_distribution(
        self,
        *,
        site_id: str,
        dimension: str,
        from_utc: str,
        to_utc: str,
        quality_mode: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        if dimension not in CLIENT_CONTEXT_FIELDS:
            raise ValueError("unsupported client context dimension")
        spec = _wireless_source_spec("client")
        accepted = (
            spec["strict"]
            if quality_mode == "strict_complete"
            else spec["diagnostic"]
        )
        with self._connection("observations", deadline) as connection:
            rows = self._all(
                connection,
                f"""
                WITH base AS (
                    SELECT o.{dimension} AS context, o.client_mac,
                           CASE WHEN ({accepted}) THEN 1 ELSE 0 END accepted,
                           o.observed_at
                    FROM {spec['from']}
                    WHERE o.site_id=? AND o.observed_at>=?
                      AND o.observed_at<?
                ), accepted AS (
                    SELECT * FROM base WHERE accepted=1
                ), grouped AS (
                    SELECT context, COUNT(*) observation_count,
                           COUNT(DISTINCT client_mac) distinct_client_count
                    FROM accepted GROUP BY context
                )
                SELECT context, observation_count, distinct_client_count,
                       (SELECT COUNT(*) FROM base) rows_examined,
                       (SELECT COUNT(*) FROM accepted) rows_accepted,
                       (SELECT COUNT(*) FROM base WHERE accepted=0)
                           rows_rejected,
                       (SELECT COUNT(*) FROM accepted WHERE context IS NULL)
                           missing_context_count,
                       (SELECT MAX(observed_at) FROM accepted) watermark
                FROM grouped
                ORDER BY context IS NOT NULL, context
                """,
                (site_id, from_utc, to_utc),
                deadline,
            )
            if rows:
                first = rows[0]
                return {
                    "items": tuple(dict(row) for row in rows),
                    "rows_examined": int(first["rows_examined"]),
                    "rows_accepted": int(first["rows_accepted"]),
                    "rows_rejected": int(first["rows_rejected"]),
                    "missing_context_count": int(
                        first["missing_context_count"]
                    ),
                    "watermark": first["watermark"],
                }
            summary = self._one(
                connection,
                f"""
                SELECT COUNT(*) rows_examined,
                       COALESCE(SUM(({accepted})), 0) rows_accepted,
                       COUNT(*)-COALESCE(SUM(({accepted})), 0) rows_rejected,
                       MAX(CASE WHEN ({accepted}) THEN o.observed_at END)
                           watermark
                FROM {spec['from']}
                WHERE o.site_id=? AND o.observed_at>=? AND o.observed_at<?
                """,
                (site_id, from_utc, to_utc),
                deadline,
            )
        return {
            "items": (),
            "rows_examined": int(summary["rows_examined"]),
            "rows_accepted": int(summary["rows_accepted"]),
            "rows_rejected": int(summary["rows_rejected"]),
            "missing_context_count": 0,
            "watermark": summary["watermark"],
        }

    def concurrent_client_distribution(
        self,
        *,
        site_id: str,
        from_utc: str,
        to_utc: str,
        quality_mode: str,
        group_by: str | None,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        if group_by is not None and group_by not in {
            "ap_mac", "ssid", "band"
        }:
            raise ValueError("unsupported concurrent-client grouping")
        cycle_acceptance = (
            "c.state='completed' AND c.complete=1 AND c.result='success'"
            if quality_mode == "strict_complete"
            else "c.state='completed'"
        )
        row_acceptance = (
            "o.source_inventory_complete=1"
            if quality_mode == "strict_complete" else "1"
        )
        with self._connection("observations", deadline) as connection:
            summary = self._one(
                connection,
                f"""
                SELECT COUNT(*) rows_examined,
                       COALESCE(SUM({cycle_acceptance}), 0) rows_accepted,
                       COUNT(*)-COALESCE(SUM({cycle_acceptance}), 0)
                         rows_rejected,
                       COALESCE(SUM(c.state='completed'
                         AND c.result='partial'), 0) partial_cycle_count,
                       COALESCE(SUM(c.state='completed'
                         AND c.result='failed'), 0) failed_cycle_count,
                       COALESCE(SUM(c.state='abandoned'), 0)
                         abandoned_cycle_count,
                       MAX(CASE WHEN {cycle_acceptance}
                         THEN c.started_at END) watermark
                FROM observation_cycles c
                WHERE c.site_id=? AND c.kind='client'
                  AND c.started_at>=? AND c.started_at<?
                """,
                (site_id, from_utc, to_utc),
                deadline,
            )
            if group_by is None:
                samples = f"""
                    SELECT c.cycle_id, NULL context,
                           COUNT(o.row_id) value,
                           c.started_at observed_at
                    FROM accepted_cycles c
                    LEFT JOIN client_observations o
                      ON o.cycle_id=c.cycle_id AND ({row_acceptance})
                    GROUP BY c.cycle_id
                """
            else:
                # Groups originate only in real accepted observations.  The
                # cross product then supplies an explicit zero for every
                # accepted cycle in which that real group was absent.  This
                # keeps an actual NULL context distinct from an empty cycle.
                samples = f"""
                    SELECT c.cycle_id, g.context,
                           COUNT(o.row_id) value,
                           c.started_at observed_at
                    FROM accepted_cycles c
                    CROSS JOIN (
                      SELECT DISTINCT o.{group_by} context
                      FROM accepted_cycles present_cycle
                      JOIN client_observations o
                        ON o.cycle_id=present_cycle.cycle_id
                       AND ({row_acceptance})
                    ) g
                    LEFT JOIN client_observations o
                      ON o.cycle_id=c.cycle_id AND ({row_acceptance})
                     AND o.{group_by} IS g.context
                    GROUP BY c.cycle_id, g.context
                """
            rows = self._all(
                connection,
                f"""
                WITH accepted_cycles AS MATERIALIZED (
                    SELECT cycle_id, started_at
                    FROM observation_cycles c
                    WHERE c.site_id=? AND c.kind='client'
                      AND c.started_at>=? AND c.started_at<?
                      AND ({cycle_acceptance})
                ), samples AS ({samples}), ranked AS (
                    SELECT context, value, observed_at,
                           ROW_NUMBER() OVER (
                             PARTITION BY context ORDER BY value, cycle_id
                           )-1 AS rank_index,
                           COUNT(*) OVER (PARTITION BY context) AS n
                    FROM samples
                )
                SELECT context, MAX(n) cycle_sample_count,
                       MIN(value) minimum, AVG(value) mean,
                       MAX(value) maximum,
                       {_percentile_columns('p50', 0.50)},
                       {_percentile_columns('p95', 0.95)},
                       MAX(observed_at) watermark
                FROM ranked GROUP BY context
                ORDER BY context IS NOT NULL, context
                """,
                (site_id, from_utc, to_utc),
                deadline,
            )
        return {
            "items": tuple(dict(row) for row in rows),
            "rows_examined": int(summary["rows_examined"]),
            "rows_accepted": int(summary["rows_accepted"]),
            "rows_rejected": int(summary["rows_rejected"]),
            "partial_cycle_count": int(summary["partial_cycle_count"]),
            "failed_cycle_count": int(summary["failed_cycle_count"]),
            "abandoned_cycle_count": int(summary["abandoned_cycle_count"]),
            "watermark": summary["watermark"],
        }

    def radio_utilization_distributions(
        self,
        *,
        site_id: str,
        metric: str,
        from_utc: str,
        to_utc: str,
        quality_mode: str,
        ap_mac: str | None,
        band: str | None,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        if metric not in WIRELESS_SCALAR_FIELDS["radio"]:
            raise ValueError("unsupported radio utilization metric")
        spec = _wireless_source_spec("radio")
        accepted = (
            spec["strict"]
            if quality_mode == "strict_complete"
            else spec["diagnostic"]
        )
        filter_sql, filter_parameters = _wireless_filters(
            "radio", {"ap_mac": ap_mac, "band": band}, alias="o"
        )
        parameters = (site_id, from_utc, to_utc, *filter_parameters)
        with self._connection("observations", deadline) as connection:
            summary = self._one(
                connection,
                f"""
                SELECT COUNT(*) rows_examined,
                       COALESCE(SUM({accepted}), 0) rows_accepted,
                       COUNT(*)-COALESCE(SUM({accepted}), 0) rows_rejected,
                       COUNT(DISTINCT CASE WHEN {accepted}
                         THEN o.ap_mac END) distinct_ap_count,
                       COUNT(DISTINCT CASE WHEN NOT ({accepted})
                         THEN o.cycle_id END) partial_cycle_count,
                       MAX(CASE WHEN {accepted}
                         THEN o.radio_observed_at END) watermark
                FROM {spec['from']}
                WHERE o.site_id=? AND o.radio_observed_at>=?
                  AND o.radio_observed_at<? {filter_sql}
                """,
                parameters,
                deadline,
            )
            rows = self._all(
                connection,
                f"""
                WITH base AS MATERIALIZED (
                  SELECT o.ap_mac, o.band, o.{metric} value,
                         o.radio_observed_at observed_at
                  FROM {spec['from']}
                  WHERE o.site_id=? AND o.radio_observed_at>=?
                    AND o.radio_observed_at<? {filter_sql}
                    AND ({accepted})
                ), group_stats AS (
                  SELECT ap_mac, band, COUNT(*) rows_accepted,
                         COALESCE(SUM(value IS NULL), 0) missing_count,
                         MAX(observed_at) watermark
                  FROM base GROUP BY ap_mac, band
                ), histogram AS (
                  SELECT ap_mac, band, value, COUNT(*) frequency
                  FROM base WHERE value IS NOT NULL
                  GROUP BY ap_mac, band, value
                ), ranked AS (
                  SELECT ap_mac, band, value, frequency,
                         SUM(frequency) OVER (
                           PARTITION BY ap_mac, band ORDER BY value
                           ROWS UNBOUNDED PRECEDING
                         ) cumulative_count,
                         SUM(frequency) OVER (
                           PARTITION BY ap_mac, band
                         ) n
                  FROM histogram
                ), value_stats AS (
                  SELECT ap_mac, band,
                         COALESCE(SUM(frequency), 0) sample_count,
                         MIN(value) minimum, MAX(value) maximum,
                         SUM(value*frequency)*1.0/SUM(frequency) mean,
                         {_histogram_percentile_columns('p10', 0.10)},
                         {_histogram_percentile_columns('p50', 0.50)},
                         {_histogram_percentile_columns('p90', 0.90)},
                         {_histogram_percentile_columns('p95', 0.95)}
                  FROM ranked GROUP BY ap_mac, band
                )
                SELECT g.ap_mac, g.band, g.rows_accepted,
                       g.missing_count, g.watermark,
                       COALESCE(v.sample_count, 0) sample_count,
                       v.minimum, v.maximum, v.mean,
                       v.p10_lower, v.p10_upper,
                       v.p50_lower, v.p50_upper,
                       v.p90_lower, v.p90_upper,
                       v.p95_lower, v.p95_upper
                FROM group_stats g
                LEFT JOIN value_stats v
                  ON v.ap_mac=g.ap_mac AND v.band IS g.band
                ORDER BY g.ap_mac, g.band
                """,
                parameters,
                deadline,
            )
        return {
            "items": tuple(dict(row) for row in rows),
            "rows_examined": int(summary["rows_examined"]),
            "rows_accepted": int(summary["rows_accepted"]),
            "rows_rejected": int(summary["rows_rejected"]),
            "distinct_ap_count": int(summary["distinct_ap_count"]),
            "partial_cycle_count": int(summary["partial_cycle_count"]),
            "watermark": summary["watermark"],
        }

    def stored_rate_distribution(
        self,
        *,
        site_id: str,
        metric: str,
        from_utc: str,
        to_utc: str,
        quality_mode: str,
        ap_mac: str | None,
        band: str | None,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        try:
            source, reason_field = STORED_RATE_FIELDS[metric]
        except KeyError as exc:
            raise ValueError("unsupported stored rate metric") from exc
        spec = _wireless_source_spec(source)
        filters = {"ap_mac": ap_mac, "band": band}
        filter_sql, filter_parameters = _wireless_filters(
            source, filters, alias="o"
        )
        accepted_source = (
            spec["strict"]
            if quality_mode == "strict_complete"
            else spec["diagnostic"]
        )
        base_sql = f"""
            SELECT o.row_id, o.cycle_id, o.ap_mac,
                   {spec['time']} observed_at,
                   CASE WHEN ({accepted_source})
                         AND o.{reason_field}='ok'
                        THEN o.{metric} END value,
                   CASE WHEN ({accepted_source}) THEN 1 ELSE 0 END accepted,
                   CASE WHEN ({accepted_source})
                        THEN COALESCE(o.{reason_field}, 'source_missing')
                        ELSE 'source_rejected' END reason
            FROM {spec['from']}
            WHERE o.site_id=? AND {spec['time']}>=? AND {spec['time']}<?
              {filter_sql}
        """
        parameters = (site_id, from_utc, to_utc, *filter_parameters)
        with self._connection("observations", deadline) as connection:
            summary = self._distribution_from_base(
                connection, base_sql=base_sql, parameters=parameters,
                threshold=None, deadline=deadline,
            )
        result = dict(summary)
        result["reason_counts"] = _reason_counts(result)
        result["valid_rate_sample_count"] = int(
            result["reason_counts"].get("ok", 0)
        )
        result["excluded_rate_sample_count"] = (
            int(result["rows_accepted"])
            - result["valid_rate_sample_count"]
        )
        return result

    def client_counter_rate_distribution(
        self,
        *,
        site_id: str,
        metric: str,
        from_utc: str,
        to_utc: str,
        quality_mode: str,
        max_gap_seconds: float,
        client_mac: str | None,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        try:
            counter = CLIENT_COUNTER_FIELDS[metric]
        except KeyError as exc:
            raise ValueError("unsupported client counter rate") from exc
        spec = _wireless_source_spec("client")
        accepted = (
            spec["strict"]
            if quality_mode == "strict_complete"
            else spec["diagnostic"]
        )
        client_filter = "" if client_mac is None else "AND o.client_mac=?"
        parameters: tuple[Any, ...] = (
            site_id, from_utc, to_utc,
            *((client_mac,) if client_mac is not None else ()),
            max_gap_seconds,
        )
        base_sql = f"""
            WITH all_rows AS MATERIALIZED (
                SELECT o.row_id, o.cycle_id, o.observed_at, o.client_mac,
                       o.{counter} counter_value,
                       CASE WHEN ({accepted}) THEN 1 ELSE 0 END
                         source_accepted
                FROM {spec['from']}
                WHERE o.site_id=? AND o.observed_at>=? AND o.observed_at<?
                  {client_filter}
            ), accepted_rows AS (
                SELECT * FROM all_rows WHERE source_accepted=1
            ), ordered AS (
                SELECT *,
                       LAG(counter_value) OVER (
                         PARTITION BY client_mac
                         ORDER BY observed_at, row_id
                       ) previous_value,
                       LAG(observed_at) OVER (
                         PARTITION BY client_mac
                         ORDER BY observed_at, row_id
                       ) previous_at
                FROM accepted_rows
            ), classified AS (
                SELECT row_id, cycle_id, NULL ap_mac, observed_at, 1 accepted,
                       CASE
                         WHEN previous_at IS NULL THEN 'no_baseline'
                         WHEN counter_value IS NULL OR previous_value IS NULL
                           THEN 'source_missing'
                         WHEN ROUND(
                           (julianday(observed_at)-julianday(previous_at))
                           *86400.0, 3)<=0 THEN 'invalid_elapsed'
                         WHEN ROUND(
                           (julianday(observed_at)-julianday(previous_at))
                           *86400.0, 3)>? THEN 'gap_too_large'
                         WHEN counter_value<previous_value THEN 'counter_reset'
                         ELSE 'ok' END reason,
                       CASE WHEN previous_at IS NOT NULL
                         AND counter_value IS NOT NULL
                         AND previous_value IS NOT NULL
                         AND counter_value>=previous_value
                         AND ROUND(
                           (julianday(observed_at)-julianday(previous_at))
                           *86400.0, 3)>0
                         AND ROUND(
                           (julianday(observed_at)-julianday(previous_at))
                           *86400.0, 3)<=?
                       THEN (counter_value-previous_value)*8.0/
                            ROUND(
                              (julianday(observed_at)-julianday(previous_at))
                              *86400.0, 3)/1000000.0 END value
                FROM ordered
            )
            SELECT * FROM classified
            UNION ALL
            SELECT row_id, cycle_id, NULL ap_mac, observed_at, 0 accepted,
                   'source_rejected' reason, NULL value
            FROM all_rows WHERE source_accepted=0
        """
        distribution_parameters = (*parameters, max_gap_seconds)
        with self._connection("observations", deadline) as connection:
            summary = self._distribution_from_base(
                connection, base_sql=base_sql,
                parameters=distribution_parameters,
                threshold=None, deadline=deadline,
            )
        result = dict(summary)
        result["reason_counts"] = _reason_counts(result)
        result["valid_rate_sample_count"] = int(
            result["reason_counts"].get("ok", 0)
        )
        result["excluded_rate_sample_count"] = (
            int(result["rows_accepted"])
            - result["valid_rate_sample_count"]
        )
        return result

    def radio_counter_quality(
        self,
        *,
        site_id: str,
        from_utc: str,
        to_utc: str,
        quality_mode: str,
        max_gap_seconds: float,
        ap_mac: str | None,
        band: str | None,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        spec = _wireless_source_spec("radio")
        accepted = (
            spec["strict"]
            if quality_mode == "strict_complete"
            else spec["diagnostic"]
        )
        filter_sql, filter_parameters = _wireless_filters(
            "radio", {"ap_mac": ap_mac, "band": band}, alias="o"
        )
        fields = tuple(sorted({
            field for pair in RADIO_COUNTER_FIELDS.values() for field in pair
        }))
        previous_fields = ",\n".join(
            f"previous.{field} previous_{field}"
            for field in fields
        )
        metric_projections: list[str] = []
        for output_name, (counter, packet) in RADIO_COUNTER_FIELDS.items():
            previous_counter = f"previous_{counter}"
            previous_packet = f"previous_{packet}"
            valid = (
                f"previous_at IS NOT NULL AND {counter} IS NOT NULL "
                f"AND {previous_counter} IS NOT NULL AND elapsed>0 "
                "AND elapsed<=max_gap "
                f"AND {counter}>={previous_counter}"
            )
            ratio_valid = (
                f"{valid} AND {packet} IS NOT NULL "
                f"AND {previous_packet} IS NOT NULL "
                f"AND {packet}>={previous_packet}"
            )
            metric_projections.extend((
                f"COALESCE(SUM({valid}),0) AS {output_name}_valid_count",
                "COALESCE(SUM(previous_at IS NOT NULL "
                f"AND {counter} IS NOT NULL "
                f"AND {previous_counter} IS NOT NULL "
                "AND elapsed>0 AND elapsed<=max_gap "
                f"AND {counter}<{previous_counter}),0) "
                f"AS {output_name}_reset_count",
                "COALESCE(SUM(previous_at IS NOT NULL "
                f"AND elapsed>max_gap),0) AS {output_name}_gap_count",
                "COALESCE(SUM(previous_at IS NULL "
                f"OR {counter} IS NULL OR {previous_counter} IS NULL "
                f"OR elapsed<=0),0) AS {output_name}_missing_count",
                f"COALESCE(SUM(CASE WHEN {valid} THEN "
                f"{counter}-{previous_counter} ELSE 0 END),0) "
                f"AS {output_name}_total_delta",
                f"COALESCE(SUM(CASE WHEN {ratio_valid} THEN "
                f"{counter}-{previous_counter} ELSE 0 END),0) "
                f"AS {output_name}_ratio_event_delta",
                f"COALESCE(SUM(CASE WHEN {ratio_valid} THEN "
                f"{packet}-{previous_packet} ELSE 0 END),0) "
                f"AS {output_name}_packet_delta",
            ))
        projections = ",\n".join(metric_projections)
        with self._connection("observations", deadline) as connection:
            row = self._one(
                connection,
                f"""
                WITH limits(max_gap) AS (SELECT ?), base_rows AS MATERIALIZED (
                  SELECT o.row_id, o.radio_observed_at, o.ap_mac, o.band,
                         o.cycle_id,
                         {', '.join(f'o.{field}' for field in fields)},
                         CASE WHEN ({accepted}) THEN 1 ELSE 0 END accepted
                  FROM {spec['from']}
                  WHERE o.site_id=? AND o.radio_observed_at>=?
                    AND o.radio_observed_at<? {filter_sql}
                ), accepted_rows AS (
                  SELECT * FROM base_rows WHERE accepted=1
                ), ordered AS (
                  SELECT *,
                    LAG(row_id) OVER (
                      PARTITION BY ap_mac, band
                      ORDER BY radio_observed_at, row_id
                    ) previous_row_id,
                    LAG(radio_observed_at) OVER (
                      PARTITION BY ap_mac, band
                      ORDER BY radio_observed_at, row_id
                    ) previous_at
                  FROM accepted_rows
                ), intervals AS (
                  SELECT current.*, {previous_fields}, ROUND(
                    (julianday(current.radio_observed_at)
                     -julianday(current.previous_at))
                    *86400.0, 3
                  ) elapsed, (SELECT max_gap FROM limits) max_gap
                  FROM ordered current
                  LEFT JOIN ap_radio_observations previous
                    ON previous.row_id=current.previous_row_id
                )
                SELECT (SELECT COUNT(*) FROM base_rows) rows_examined,
                       COUNT(*) rows_accepted,
                       (SELECT COUNT(*) FROM base_rows WHERE accepted=0)
                         rows_rejected,
                       (SELECT COUNT(DISTINCT cycle_id) FROM base_rows
                         WHERE accepted=0) partial_cycle_count,
                       {projections}, MAX(radio_observed_at) watermark
                FROM intervals
                """,
                (
                    max_gap_seconds, site_id, from_utc, to_utc,
                    *filter_parameters,
                ),
                deadline,
            )
        common = dict(row)
        metrics = {
            output_name: {
                "rows_accepted": int(common["rows_accepted"]),
                "valid_count": int(common[f"{output_name}_valid_count"]),
                "reset_count": int(common[f"{output_name}_reset_count"]),
                "gap_count": int(common[f"{output_name}_gap_count"]),
                "missing_count": int(common[f"{output_name}_missing_count"]),
                "total_delta": int(common[f"{output_name}_total_delta"]),
                "ratio_event_delta": int(
                    common[f"{output_name}_ratio_event_delta"]
                ),
                "packet_delta": int(common[f"{output_name}_packet_delta"]),
                "watermark": common["watermark"],
            }
            for output_name in RADIO_COUNTER_FIELDS
        }
        rows_accepted = int(common["rows_accepted"])
        return {
            "metrics": metrics,
            "rows_examined": int(common["rows_examined"]),
            "rows_accepted": rows_accepted,
            "rows_rejected": int(common["rows_rejected"]),
            "partial_cycle_count": int(common["partial_cycle_count"]),
            "watermark": common["watermark"],
        }

    def signal_ap_correlation(
        self,
        *,
        site_id: str,
        signal_metric: str,
        ap_metric: str,
        from_utc: str,
        to_utc: str,
        quality_mode: str,
        max_lag_seconds: float,
        deadline: QueryDeadline,
        client_mac: str | None = None,
    ) -> Mapping[str, Any]:
        if signal_metric not in {"rssi", "snr"}:
            raise ValueError("unsupported signal correlation metric")
        if ap_metric not in {"busy_util", "cpu_util"}:
            raise ValueError("unsupported AP correlation metric")
        client_spec = _wireless_source_spec("client")
        target_source = "radio" if ap_metric == "busy_util" else "ap"
        client_accepted = (
            client_spec["strict"] if quality_mode == "strict_complete"
            else client_spec["diagnostic"]
        )
        client_filter = "" if client_mac is None else "AND o.client_mac=?"
        client_parameters: tuple[Any, ...] = (
            () if client_mac is None else (client_mac,)
        )
        if target_source == "radio":
            lookup_identity = (
                "lt.ap_mac=k.ap_mac AND lt.band=k.band"
            )
            key_columns = "observed_at, ap_mac, band"
            key_join = (
                "ch.observed_at=cg.observed_at AND ch.ap_mac=cg.ap_mac "
                "AND ch.band IS cg.band"
            )
            target_time = "t.radio_observed_at"
            target_table = "ap_radio_observations"
            lookup_from = "ap_radio_observations lt"
            lookup_time = "lt.radio_observed_at"
            lookup_accepted = (
                "EXISTS (SELECT 1 FROM ap_observations lp "
                "JOIN observation_cycles lc ON lc.cycle_id=lt.cycle_id "
                "WHERE lp.row_id=lt.ap_observation_row_id "
                "AND lp.radios_ok=1 AND lp.site_id=lt.site_id "
                "AND lp.ap_mac=lt.ap_mac AND lp.cycle_id=lt.cycle_id"
            )
            if quality_mode == "strict_complete":
                lookup_accepted += (
                    " AND lc.complete=1 AND lc.result='success' "
                    "AND lp.partial=0"
                )
            lookup_accepted += ")"
        else:
            lookup_identity = "lt.ap_mac=k.ap_mac"
            key_columns = "observed_at, ap_mac"
            key_join = (
                "ch.observed_at=cg.observed_at AND ch.ap_mac=cg.ap_mac"
            )
            target_time = "t.observed_at"
            target_table = "ap_observations"
            lookup_from = "ap_observations lt"
            lookup_time = "lt.observed_at"
            lookup_accepted = (
                "lt.overview_ok=1 AND EXISTS (SELECT 1 "
                "FROM observation_cycles lc WHERE lc.cycle_id=lt.cycle_id "
                "AND lc.state='completed'"
            )
            if quality_mode == "strict_complete":
                lookup_accepted += (
                    " AND lc.complete=1 AND lc.result='success' "
                    "AND lt.partial=0"
                )
            lookup_accepted += ")"
        with self._connection("observations", deadline) as connection:
            row = self._one(
                connection,
                f"""
                WITH clients AS MATERIALIZED (
                  SELECT o.row_id client_row_id, o.observed_at,
                         o.ap_mac, o.band, o.{signal_metric} signal_value
                  FROM {client_spec['from']}
                  WHERE o.site_id=? AND o.observed_at>=? AND o.observed_at<?
                    AND ({client_accepted}) AND o.ap_mac IS NOT NULL
                    {client_filter}
                ), client_groups AS MATERIALIZED (
                  SELECT {key_columns}, signal_value, COUNT(*) weight
                  FROM clients GROUP BY {key_columns}, signal_value
                ), client_keys AS MATERIALIZED (
                  SELECT DISTINCT {key_columns} FROM client_groups
                ), chosen AS MATERIALIZED (
                  SELECT k.*,
                    (SELECT lt.row_id FROM {lookup_from}
                     WHERE lt.site_id=? AND ({lookup_identity})
                       AND {lookup_time}<=k.observed_at
                       AND ({lookup_accepted})
                     ORDER BY {lookup_time} DESC, lt.row_id DESC
                     LIMIT 1) target_row_id
                  FROM client_keys k
                ), paired AS (
                  SELECT cg.*, ch.target_row_id
                  FROM client_groups cg JOIN chosen ch ON {key_join}
                ), selected AS (
                  SELECT ch.*, {target_time} target_at,
                    t.{ap_metric} target_value,
                    CASE WHEN {target_time} IS NULL THEN NULL ELSE
                    ROUND(
                      (julianday(ch.observed_at)-julianday({target_time}))
                      *86400.0,
                      3
                    )
                    END lag_seconds
                  FROM paired ch
                  LEFT JOIN {target_table} t ON t.row_id=ch.target_row_id
                ), bounded AS (
                  SELECT *, CASE WHEN target_row_id IS NOT NULL
                    AND lag_seconds>=0 AND lag_seconds<=?
                    THEN 1 ELSE 0 END matched
                  FROM selected
                ), lag_histogram AS (
                  SELECT lag_seconds, SUM(weight) frequency
                  FROM bounded WHERE matched=1 GROUP BY lag_seconds
                ), lag_ranked AS (
                  SELECT lag_seconds, frequency,
                    SUM(frequency) OVER (
                      ORDER BY lag_seconds ROWS UNBOUNDED PRECEDING
                    ) cumulative_count,
                    SUM(frequency) OVER() n
                  FROM lag_histogram
                )
                SELECT (SELECT COALESCE(SUM(weight),0) FROM client_groups)
                    client_sample_count,
                  (SELECT COALESCE(SUM(weight*matched),0) FROM bounded)
                    matched_count,
                  (SELECT COALESCE(SUM(weight),0) FROM bounded
                    WHERE matched=1 AND signal_value IS NOT NULL
                      AND target_value IS NOT NULL) sample_count,
                  (SELECT COALESCE(SUM(signal_value*weight),0) FROM bounded
                    WHERE matched=1 AND signal_value IS NOT NULL
                      AND target_value IS NOT NULL) sum_x,
                  (SELECT COALESCE(SUM(target_value*weight),0) FROM bounded
                    WHERE matched=1 AND signal_value IS NOT NULL
                      AND target_value IS NOT NULL) sum_y,
                  (SELECT COALESCE(SUM(
                    signal_value*signal_value*weight),0)
                    FROM bounded WHERE matched=1
                      AND signal_value IS NOT NULL AND target_value IS NOT NULL)
                    sum_xx,
                  (SELECT COALESCE(SUM(
                    target_value*target_value*weight),0)
                    FROM bounded WHERE matched=1
                      AND signal_value IS NOT NULL AND target_value IS NOT NULL)
                    sum_yy,
                  (SELECT COALESCE(SUM(
                    signal_value*target_value*weight),0)
                    FROM bounded WHERE matched=1
                      AND signal_value IS NOT NULL AND target_value IS NOT NULL)
                    sum_xy,
                  (SELECT MAX(lag_seconds) FROM lag_ranked) lag_max,
                  (SELECT MIN(CASE WHEN cumulative_count>
                    CAST((n-1)*0.50 AS INTEGER) THEN lag_seconds END)
                    FROM lag_ranked) lag_p50_lower,
                  (SELECT MIN(CASE WHEN cumulative_count>
                    CAST((n-1)*0.50+0.999999999999 AS INTEGER)
                    THEN lag_seconds END) FROM lag_ranked) lag_p50_upper,
                  (SELECT MIN(CASE WHEN cumulative_count>
                    CAST((n-1)*0.95 AS INTEGER) THEN lag_seconds END)
                    FROM lag_ranked) lag_p95_lower,
                  (SELECT MIN(CASE WHEN cumulative_count>
                    CAST((n-1)*0.95+0.999999999999 AS INTEGER)
                    THEN lag_seconds END) FROM lag_ranked) lag_p95_upper,
                  (SELECT MAX(observed_at) FROM client_groups) watermark
                """,
                (site_id, from_utc, to_utc, *client_parameters,
                 site_id, max_lag_seconds),
                deadline,
            )
        return dict(row)

    def _distribution_from_base(
        self,
        connection: sqlite3.Connection,
        *,
        base_sql: str,
        parameters: Iterable[Any],
        threshold: float | None,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        row = self._one(
            connection,
            f"""
            WITH base AS MATERIALIZED ({base_sql}),
            values_only AS (
              SELECT value FROM base
              WHERE accepted=1 AND value IS NOT NULL
            ), histogram AS (
              SELECT value, COUNT(*) frequency
              FROM values_only GROUP BY value
            ), ranked AS (
              SELECT value, frequency,
                SUM(frequency) OVER (
                  ORDER BY value ROWS UNBOUNDED PRECEDING
                ) cumulative_count,
                SUM(frequency) OVER () n
              FROM histogram
            ), base_stats AS (
              SELECT COUNT(*) rows_examined,
                COALESCE(SUM(accepted=1), 0) rows_accepted,
                COALESCE(SUM(accepted=0), 0) rows_rejected,
                COUNT(DISTINCT CASE WHEN accepted=1 THEN ap_mac END)
                  distinct_ap_count,
                MAX(CASE WHEN accepted=1 THEN observed_at END) watermark,
                COUNT(DISTINCT CASE WHEN accepted=0 THEN cycle_id END)
                  partial_cycle_count,
                COALESCE(SUM(reason='ok'),0) reason_ok,
                COALESCE(SUM(reason='no_baseline'),0) reason_no_baseline,
                COALESCE(SUM(reason='counter_reset'),0)
                  reason_counter_reset,
                COALESCE(SUM(reason='gap_too_large'),0)
                  reason_gap_too_large,
                COALESCE(SUM(reason='invalid_elapsed'),0)
                  reason_invalid_elapsed,
                COALESCE(SUM(reason='source_missing'),0)
                  reason_source_missing,
                COALESCE(SUM(reason='source_unavailable'),0)
                  reason_source_unavailable,
                COALESCE(SUM(reason='source_rejected'),0)
                  reason_source_rejected
              FROM base
            ), value_stats AS (
              SELECT COALESCE(SUM(frequency),0) sample_count,
                MIN(value) minimum, MAX(value) maximum,
                SUM(value*frequency)*1.0/SUM(frequency) mean,
                {_histogram_percentile_columns('p10', 0.10)},
                {_histogram_percentile_columns('p50', 0.50)},
                {_histogram_percentile_columns('p90', 0.90)},
                {_histogram_percentile_columns('p95', 0.95)},
                CASE WHEN ? IS NULL THEN NULL ELSE
                  COALESCE(SUM(
                    CASE WHEN value<? THEN frequency ELSE 0 END
                  ), 0) END below_threshold_count
              FROM ranked
            )
            SELECT b.*, v.*,
              b.rows_accepted-v.sample_count missing_count
            FROM base_stats b CROSS JOIN value_stats v
            """,
            (*tuple(parameters), threshold, threshold),
            deadline,
        )
        return dict(row)

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


def _wireless_source_spec(source: str) -> Mapping[str, str]:
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
            "diagnostic": "c.state='completed'",
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
            "diagnostic": (
                "c.state='completed' AND o.overview_ok=1"
            ),
        }
    if source == "radio":
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
            "diagnostic": (
                "c.state='completed' AND p.radios_ok=1 "
                "AND p.site_id=o.site_id AND p.ap_mac=o.ap_mac "
                "AND p.cycle_id=o.cycle_id"
            ),
        }
    raise ValueError("unsupported wireless source")


def _wireless_filters(
    source: str,
    filters: Mapping[str, Any],
    *,
    alias: str,
) -> tuple[str, tuple[Any, ...]]:
    allowed = {
        "client": frozenset({
            "client_mac", "ap_mac", "ssid", "band", "channel",
        }),
        "ap": frozenset({"ap_mac"}),
        "radio": frozenset({"ap_mac", "band"}),
    }[source]
    clauses: list[str] = []
    parameters: list[Any] = []
    for key, value in filters.items():
        if key not in allowed:
            if value is not None:
                raise ValueError("unsupported wireless filter")
            continue
        if value is not None:
            clauses.append(f"AND {alias}.{key}=?")
            parameters.append(value)
    return " ".join(clauses), tuple(parameters)


def _percentile_columns(prefix: str, probability: float) -> str:
    return (
        "MAX(CASE WHEN rank_index="
        f"CAST((n-1)*{probability:.2f} AS INTEGER) "
        f"THEN value END) {prefix}_lower, "
        "MAX(CASE WHEN rank_index="
        f"CAST((n-1)*{probability:.2f}+0.999999999999 AS INTEGER) "
        f"THEN value END) {prefix}_upper"
    )


def _histogram_percentile_columns(prefix: str, probability: float) -> str:
    return (
        "MIN(CASE WHEN cumulative_count>"
        f"CAST((n-1)*{probability:.2f} AS INTEGER) "
        f"THEN value END) {prefix}_lower, "
        "MIN(CASE WHEN cumulative_count>"
        f"CAST((n-1)*{probability:.2f}+0.999999999999 AS INTEGER) "
        f"THEN value END) {prefix}_upper"
    )


def _reason_counts(raw: Mapping[str, Any]) -> Mapping[str, int]:
    names = (
        "ok", "no_baseline", "counter_reset", "gap_too_large",
        "invalid_elapsed", "source_missing", "source_unavailable",
        "source_rejected",
    )
    return {
        name: int(raw.get(f"reason_{name}") or 0)
        for name in names
        if int(raw.get(f"reason_{name}") or 0) > 0
    }
