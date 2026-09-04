"""Projection-backed gateway preserving HistoricalTrafficReadService semantics."""

from __future__ import annotations

import contextvars
import re
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from typing import Any, Collection, Iterator, Mapping

from app.analytics.source_gateway import (
    AnalyticsQueryDeadlineExceeded,
    AnalyticsSourceGateway,
    AnalyticsSourceUnavailable,
    QueryDeadline,
    _statement_deadline,
    _translate_sqlite_error,
)

from .health import classify_projection_health
from .models import (
    SUPPORTED_SEMANTIC_CONTRACTS,
    ProjectedRangeSelection,
    TrafficProjectionDiverged,
    TrafficProjectionStorageUnavailable,
    TrafficProjectionValidationError,
    TrafficProjectionVersionUnavailable,
)
from .repository import TrafficProjectionRepository


_INDEX_HINT = re.compile(r"\s+INDEXED\s+BY\s+[A-Za-z0-9_]+", re.IGNORECASE)
_VALIDATION_CTES = re.compile(
    r"cycle_aggregates AS(?: MATERIALIZED)? \(.*?"
    r"FROM cycle_aggregates\s*\)",
    re.DOTALL,
)
_PROJECTED_VALIDATION_CTES = """cycle_aggregates AS MATERIALIZED (
      SELECT * FROM candidate_cycles
    ),
    validated_cycles AS MATERIALIZED (
      SELECT * FROM candidate_cycles
      WHERE ? IS NOT NULL AND ? IS NOT NULL AND ? IS NOT NULL
    )"""
_PROJECTED_AP_EVIDENCE_SQL = """
    SELECT c.cycle_id,c.source_finished_at AS finished_at,
      a.ap_mac,a.rowid AS row_id,a.historical_name AS name,
      a.wired_download_mbps,a.wired_upload_mbps,
      a.wired_download_reason AS wired_download_rate_reason,
      a.wired_upload_reason AS wired_upload_rate_reason,
      a.lan_download_mbps AS lan_rx_mbps,
      a.lan_upload_mbps AS lan_tx_mbps,
      a.lan_download_reason AS lan_rx_rate_reason,
      a.lan_upload_reason AS lan_tx_rate_reason
    FROM main.traffic_projection_cycles c
    JOIN main.traffic_projection_ap_cycles a
      ON a.projection_version=c.projection_version
     AND a.site_id=c.site_id AND a.cycle_id=c.cycle_id
    WHERE c.projection_version=(
      SELECT projection_version FROM main.traffic_projection_versions
      WHERE status='active'
    )
      AND c.site_id=? AND c.source_kind='ap_dynamic'
      AND c.source_state='completed' AND c.source_complete=1
      AND c.source_result='success' AND c.integrity_ok=1
      AND c.source_finished_at>=? AND c.source_finished_at<?
"""
_PROJECTED_RANGE_CYCLES_SQL = """
    SELECT c.cycle_id,c.source_started_at,c.source_finished_at,
      c.integrity_ok,c.stored_row_count,c.wired_complete,c.lan_complete,
      c.wired_pair_count,c.lan_pair_count,
      c.wired_download_mbps,c.wired_upload_mbps,
      c.lan_download_mbps,c.lan_upload_mbps,
      c.wired_no_baseline_count,c.lan_no_baseline_count,
      c.wired_counter_reset_count,c.lan_counter_reset_count,
      c.wired_gap_too_large_count,c.lan_gap_too_large_count,
      c.wired_invalid_elapsed_count,c.lan_invalid_elapsed_count,
      c.wired_source_unavailable_count,c.lan_source_unavailable_count,
      c.wired_ok_count,c.lan_ok_count
    FROM main.traffic_projection_cycles c
    WHERE c.projection_version=(
      SELECT projection_version FROM main.traffic_projection_versions
      WHERE status='active'
    )
      AND c.site_id=? AND c.source_kind='ap_dynamic'
      AND c.source_state='completed' AND c.source_complete=1
      AND c.source_result='success'
      AND (
        (c.source_started_at>=? AND c.source_started_at<?
         AND (c.source_finished_at IS NULL
              OR (c.source_finished_at>=? AND c.source_finished_at<?)))
        OR
        (c.source_started_at<? AND c.source_finished_at>=?
         AND c.source_finished_at<?)
      )
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")


def _epoch_milliseconds(value: str) -> int:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return int(parsed.timestamp()) * 1000 + parsed.microsecond // 1000


def _select_source(rows: list[Mapping[str, Any]]) -> tuple[str, str]:
    count = len(rows)
    empty_count = sum(int(row["stored_row_count"]) == 0 for row in rows)
    wired_complete = sum(bool(row["wired_complete"]) for row in rows)
    lan_complete = sum(bool(row["lan_complete"]) for row in rows)
    wired_pairs = sum(int(row["wired_pair_count"]) for row in rows)
    lan_pairs = sum(int(row["lan_pair_count"]) for row in rows)
    if empty_count == count:
        return "wired", "empty_population"
    if wired_complete == count:
        return "wired", "primary_full_coverage"
    if lan_complete == count:
        return "lan", "fallback_full_coverage"
    if lan_complete > wired_complete:
        return "lan", "fallback_higher_coverage"
    if wired_complete > lan_complete:
        return "wired", "primary_preferred_tie_or_higher"
    if lan_pairs > wired_pairs:
        return "lan", "fallback_higher_coverage"
    return "wired", "primary_preferred_tie_or_higher"


class _ReadSnapshot:
    """Keep the gateway's nested BEGIN from replacing our coherent snapshot."""

    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection

    def __getattr__(self, name: str):
        return getattr(self._connection, name)

    def execute(self, sql: str, parameters: Any = ()):
        if sql.strip().upper() == "BEGIN":
            return self._connection.execute("SELECT 1 WHERE 0")
        return self._connection.execute(sql, parameters)


class TrafficProjectionReadService(AnalyticsSourceGateway):
    """Expose one coherent projected range through the existing semantic owner."""

    def __init__(
        self,
        repository: TrafficProjectionRepository,
        *,
        current_observation_db_path: str | None = None,
        clock=utc_now,
        supported_semantic_contracts: Collection[str] = (
            SUPPORTED_SEMANTIC_CONTRACTS
        ),
    ):
        super().__init__(None, None, None)  # only the historical gateway surface is used
        self._repository = repository
        self._current_path = current_observation_db_path
        self._clock = clock
        self._supported_semantic_contracts = frozenset(
            supported_semantic_contracts
        )
        self._request = contextvars.ContextVar(
            "traffic_projection_request", default=(None, None)
        )
        self._revision = contextvars.ContextVar(
            "traffic_projection_revision", default=None
        )
        self._active_version = contextvars.ContextVar(
            "traffic_projection_active_version", default=None
        )
        self._source_bounds = contextvars.ContextVar(
            "traffic_projection_source_bounds", default=None
        )
        self._ap_evidence = contextvars.ContextVar(
            "traffic_projection_ap_evidence", default=None
        )

    def historical_traffic_data(self, **kwargs: Any) -> Mapping[str, Any]:
        return self.select_range(**kwargs).gateway_payload()

    def select_range(self, **kwargs: Any) -> ProjectedRangeSelection:
        site_id = kwargs.get("site_id")
        from_utc = kwargs.get("from_utc")
        to_utc = kwargs.get("to_utc")
        bucket_seconds = kwargs.get("bucket_seconds")
        if not isinstance(site_id, str) or not site_id:
            raise TrafficProjectionValidationError("site_id is invalid")
        if not isinstance(from_utc, str) or not isinstance(to_utc, str):
            raise TrafficProjectionValidationError("projection range is invalid")
        try:
            start = datetime.fromisoformat(from_utc.replace("Z", "+00:00"))
            end = datetime.fromisoformat(to_utc.replace("Z", "+00:00"))
        except ValueError as exc:
            raise TrafficProjectionValidationError("projection range is invalid") from exc
        if start.tzinfo is None or end.tzinfo is None or start >= end or (end - start).total_seconds() > 7 * 86400:
            raise TrafficProjectionValidationError("projection range exceeds seven days")
        token = self._request.set((site_id, kwargs.get("current_cycle_id")))
        evidence_token = self._ap_evidence.set(None)
        try:
            data = super().historical_traffic_data(**kwargs)
        finally:
            self._ap_evidence.reset(evidence_token)
            self._request.reset(token)
        meta = dict(data.get("meta") or {})
        return ProjectedRangeSelection(
            projection_version=str(meta.pop("projection_version")),
            projection_revision=int(meta.pop("projection_revision")),
            site_id=site_id,
            from_utc=from_utc,
            to_utc=to_utc,
            bucket_seconds=int(bucket_seconds),
            rows=tuple(data["buckets"]),
            statistics=data.get("period_statistics"),
            peak_samples=data.get("peak_samples"),
            ap_population=data.get("ap_population"),
            ap_rows=data.get("ap_rows"),
            meta=meta,
            attempts=dict(data.get("attempts") or {}),
        )

    def _explain(self, method: str, kwargs: Mapping[str, Any]):
        token = self._request.set((kwargs.get("site_id"), None))
        try:
            return getattr(super(), method)(**kwargs)
        finally:
            self._request.reset(token)

    def explain_historical_traffic(self, **kwargs: Any):
        return self._explain("explain_historical_traffic", kwargs)

    def explain_historical_traffic_statistics(self, **kwargs: Any):
        return self._explain("explain_historical_traffic_statistics", kwargs)

    def explain_historical_traffic_combined(self, **kwargs: Any):
        return self._explain("explain_historical_traffic_combined", kwargs)

    @contextmanager
    def _connection(self, source: str, deadline: QueryDeadline) -> Iterator[sqlite3.Connection]:
        if source != "observations":
            raise AnalyticsSourceUnavailable("Projection supports historical observations only")
        deadline.require_remaining()
        site_id, current_cycle_id = self._request.get()
        uri = self._repository.db_path.resolve().as_uri() + "?mode=ro"
        try:
            with closing(sqlite3.connect(uri, uri=True, timeout=0.5)) as connection:
                connection.row_factory = sqlite3.Row
                connection.execute("PRAGMA busy_timeout=500")
                connection.execute("PRAGMA foreign_keys=ON")
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if version != 1:
                    raise TrafficProjectionStorageUnavailable("Projection schema is unavailable")
                if self._current_path:
                    source_uri = sqlite3_uri(self._current_path)
                    connection.execute("ATTACH DATABASE ? AS current_observations", (source_uri,))
                    source_version = int(connection.execute(
                        "PRAGMA current_observations.user_version"
                    ).fetchone()[0])
                    if source_version != 1:
                        raise TrafficProjectionStorageUnavailable("Current AP source is unavailable")
                # TEMP schema preparation uses executescript(), which commits any
                # active transaction.  Build the compatibility views before the
                # one semantic read snapshot is established.
                self._create_views(connection, site_id, current_cycle_id)
                connection.execute("PRAGMA query_only=ON")
                if int(connection.execute("PRAGMA query_only").fetchone()[0]) != 1:
                    raise TrafficProjectionStorageUnavailable(
                        "Projection query-only boundary is unavailable"
                    )
                connection.execute("BEGIN")
                with _statement_deadline(connection, deadline):
                    active = connection.execute(
                        """SELECT projection_version,status,semantic_contract_sha256,
                                  projection_schema_version,source,source_schema_version
                           FROM traffic_projection_versions WHERE status='active'"""
                    ).fetchone()
                    if active is None or (
                        str(active[2]) not in self._supported_semantic_contracts
                        or int(active[3]) != 1
                        or str(active[4]) != "observations"
                        or int(active[5]) != 1
                    ):
                        raise TrafficProjectionVersionUnavailable("Projection version is unavailable")
                    active_version = str(active[0])
                    state = connection.execute(
                        "SELECT * FROM traffic_projection_site_state WHERE projection_version=? AND site_id=?",
                        (active_version, site_id),
                    ).fetchone()
                    state_values = None if state is None else dict(state)
                    current_head = None
                    if state_values is not None and self._current_path:
                        current_head = connection.execute(
                            """SELECT started_at,cycle_id
                               FROM current_observations.observation_cycles
                               WHERE site_id=? AND kind='ap_dynamic'
                               ORDER BY started_at DESC,cycle_id DESC LIMIT 1""",
                            (site_id,),
                        ).fetchone()
                        if current_head is not None:
                            state_values["source_head_utc"] = str(current_head[0])
                            state_values["source_head_cycle_id"] = str(current_head[1])
                    health = classify_projection_health(
                        state_values,
                        now_utc=self._clock(),
                        version_available=True,
                        source_available=current_head is not None,
                        build_state="active",
                    )
                    if health.status == "diverged":
                        raise TrafficProjectionDiverged("Projection Site is diverged")
                    if health.status != "healthy":
                        raise TrafficProjectionStorageUnavailable("Projection Site is not healthy")
                revision_token = self._revision.set(int(state["projection_revision"]))
                version_token = self._active_version.set(active_version)
                bounds_token = self._source_bounds.set({
                    "available_from_utc": state["available_from_utc"],
                    "available_through_utc": state["available_through_utc"],
                    "source_watermark_utc": state["source_watermark_utc"],
                })
                try:
                    yield _ReadSnapshot(connection)
                finally:
                    self._source_bounds.reset(bounds_token)
                    self._active_version.reset(version_token)
                    self._revision.reset(revision_token)
                    connection.rollback()
        except (TrafficProjectionStorageUnavailable, TrafficProjectionVersionUnavailable,
                TrafficProjectionDiverged):
            raise AnalyticsSourceUnavailable("Historical traffic projection is unavailable")
        except AnalyticsQueryDeadlineExceeded:
            raise
        except sqlite3.OperationalError as exc:
            _translate_sqlite_error(exc, deadline)
            raise AnalyticsSourceUnavailable(
                "Historical traffic projection is unavailable"
            ) from exc
        except (sqlite3.Error, OSError, ValueError) as exc:
            raise AnalyticsSourceUnavailable("Historical traffic projection is unavailable") from exc

    def _create_views(self, connection: sqlite3.Connection, site_id: str, current_cycle_id: str | None) -> None:
        site = site_id.replace("'", "''")
        connection.executescript(f"""
          CREATE TEMP VIEW projection_observation_cycles AS
          SELECT c.cycle_id,c.source_kind kind,c.site_id,c.source_state state,
                 c.source_started_at started_at,c.source_finished_at finished_at,
                 c.source_abandoned_at abandoned_at,c.source_complete complete,
                 c.source_result result,c.source_rows_reported,c.items_seen,c.items_stored,
                 c.items_skipped,c.error_count,c.data_quality_warning_count,
                 c.projected_at created_at,c.source_updated_at updated_at,
                 c.stored_row_count,c.integrity_ok,c.wired_complete,c.lan_complete,
                 c.wired_pair_count,c.lan_pair_count,
                 c.wired_oldest_at wired_oldest,c.wired_newest_at wired_newest,
                 c.lan_oldest_at lan_oldest,c.lan_newest_at lan_newest,
                 c.wired_download_mbps wired_download,
                 c.wired_upload_mbps wired_upload,
                 c.lan_download_mbps lan_download,c.lan_upload_mbps lan_upload,
                 c.wired_no_baseline_count wired_no_baseline,
                 c.lan_no_baseline_count lan_no_baseline,
                 c.wired_counter_reset_count wired_counter_reset,
                 c.lan_counter_reset_count lan_counter_reset,
                 c.wired_gap_too_large_count wired_gap_too_large,
                 c.lan_gap_too_large_count lan_gap_too_large,
                 c.wired_invalid_elapsed_count wired_invalid_elapsed,
                 c.lan_invalid_elapsed_count lan_invalid_elapsed,
                 c.wired_source_unavailable_count wired_source_unavailable,
                 c.lan_source_unavailable_count lan_source_unavailable,
                 c.wired_ok_count wired_ok,c.lan_ok_count lan_ok
          FROM main.traffic_projection_cycles c
          JOIN main.traffic_projection_versions v
            ON v.projection_version=c.projection_version AND v.status='active'
          WHERE c.site_id='{site}';
          CREATE TEMP VIEW projection_ap_observations AS
          SELECT a.rowid row_id,a.cycle_id,
                 COALESCE(a.wired_observed_at,a.lan_observed_at) observed_at,
                 a.site_id,a.ap_mac,a.partial,a.overview_ok,a.wired_uplink_ok,
                 a.lan_traffic_ok,a.radios_ok,a.wired_observed_at,a.lan_observed_at,
                 a.historical_name name,a.wired_download_mbps,a.wired_upload_mbps,
                 a.wired_download_reason wired_download_rate_reason,
                 a.wired_upload_reason wired_upload_rate_reason,
                 a.lan_download_mbps lan_rx_mbps,a.lan_upload_mbps lan_tx_mbps,
                 a.lan_download_reason lan_rx_rate_reason,
                 a.lan_upload_reason lan_tx_rate_reason
          FROM main.traffic_projection_ap_cycles a
          JOIN main.traffic_projection_versions v
            ON v.projection_version=a.projection_version AND v.status='active'
          WHERE a.site_id='{site}';
        """)
        if self._current_path and current_cycle_id:
            cycle = current_cycle_id.replace("'", "''")
            connection.executescript(f"""
              CREATE TEMP VIEW projection_current_ap_observations AS
              SELECT row_id,cycle_id,observed_at,site_id,ap_mac,partial,overview_ok,
                     wired_uplink_ok,lan_traffic_ok,radios_ok,wired_observed_at,
                     lan_observed_at,name,wired_download_mbps,wired_upload_mbps,
                     wired_download_rate_reason,wired_upload_rate_reason,
                     lan_rx_mbps,lan_tx_mbps,lan_rx_rate_reason,lan_tx_rate_reason
              FROM projection_ap_observations
              WHERE cycle_id='{cycle}'
              UNION ALL
              SELECT row_id,cycle_id,observed_at,site_id,ap_mac,partial,overview_ok,
                     wired_uplink_ok,lan_traffic_ok,radios_ok,wired_observed_at,
                     lan_observed_at,name,wired_download_mbps,wired_upload_mbps,
                     wired_download_rate_reason,wired_upload_rate_reason,
                     lan_rx_mbps,lan_tx_mbps,lan_rx_rate_reason,lan_tx_rate_reason
              FROM current_observations.ap_observations s
              WHERE s.cycle_id='{cycle}' AND s.site_id='{site}'
                AND NOT EXISTS (SELECT 1 FROM projection_ap_observations p
                                WHERE p.cycle_id='{cycle}' AND p.ap_mac=s.ap_mac);
            """)

    def _rewrite(self, sql: str) -> str:
        rewritten = sql.replace("observation_cycles", "projection_observation_cycles")
        rewritten = rewritten.replace("ap_observations", "projection_ap_observations")
        # The projection stores the exact output of the canonical source-cycle
        # validation.  Reusing those immutable facts avoids rejoining every AP
        # row merely to derive the same request-relative selection again.  The
        # three inert predicates retain the source SQL's parameter contract.
        rewritten = _VALIDATION_CTES.sub(
            _PROJECTED_VALIDATION_CTES,
            rewritten,
            count=1,
        )
        # Current identity comes from the explicit raw current view when available.
        _, current_cycle_id = self._request.get()[:2]
        if (
            "WHERE a.cycle_id=? AND a.site_id=?" in rewritten
            and self._current_path and current_cycle_id
        ):
            rewritten = rewritten.replace(
                "FROM projection_ap_observations a", "FROM projection_current_ap_observations a"
            )
        return _INDEX_HINT.sub("", rewritten)

    def _one(self, connection: sqlite3.Connection, sql: str, parameters: Any, deadline: QueryDeadline):
        with _statement_deadline(connection, deadline):
            try:
                return connection.execute(self._rewrite(sql), tuple(parameters)).fetchone()
            except sqlite3.OperationalError as exc:
                _translate_sqlite_error(exc, deadline)
                raise

    def _all(self, connection: sqlite3.Connection, sql: str, parameters: Any, deadline: QueryDeadline):
        if "ap_support_cycle_id" in sql and "statistics_classified" in sql:
            return self._projected_combined_rows(
                connection,
                parameters=tuple(parameters),
                deadline=deadline,
            )
        if "SELECT c.cycle_id, a.ap_mac" in sql and "candidate_cycles" in sql:
            evidence = self._load_ap_evidence(
                connection,
                site_id=str(parameters[0]),
                from_utc=str(parameters[1]),
                to_utc=str(parameters[2]),
                deadline=deadline,
            )
            identities: dict[str, Mapping[str, str]] = {}
            for row in evidence:
                identities.setdefault(
                    str(row["ap_mac"]),
                    {"cycle_id": str(row["cycle_id"]), "ap_mac": str(row["ap_mac"])},
                )
            return tuple(identities.values())
        if "SELECT c.cycle_id, c.finished_at" in sql and "candidate_cycles" in sql:
            return self._load_ap_evidence(
                connection,
                site_id=str(parameters[0]),
                from_utc=str(parameters[1]),
                to_utc=str(parameters[2]),
                deadline=deadline,
            )
        with _statement_deadline(connection, deadline):
            try:
                return connection.execute(self._rewrite(sql), tuple(parameters)).fetchall()
            except sqlite3.OperationalError as exc:
                _translate_sqlite_error(exc, deadline)
                raise

    def _load_ap_evidence(
        self,
        connection: sqlite3.Connection,
        *,
        site_id: str,
        from_utc: str,
        to_utc: str,
        deadline: QueryDeadline,
    ):
        cached = self._ap_evidence.get()
        if cached is not None:
            return cached
        with _statement_deadline(connection, deadline):
            try:
                rows = tuple(connection.execute(
                    _PROJECTED_AP_EVIDENCE_SQL,
                    (site_id, from_utc, to_utc),
                ).fetchall())
            except sqlite3.OperationalError as exc:
                _translate_sqlite_error(exc, deadline)
                raise
        self._ap_evidence.set(rows)
        return rows

    def _projected_combined_rows(
        self,
        connection: sqlite3.Connection,
        *,
        parameters: tuple[Any, ...],
        deadline: QueryDeadline,
    ) -> tuple[Mapping[str, Any], ...]:
        """Assemble the canonical shared range from materialized cycle facts."""
        site_id = str(parameters[0])
        from_utc = str(parameters[1])
        to_utc = str(parameters[2])
        bucket_seconds = int(parameters[18])
        bucket_gap_seconds = float(parameters[21])
        interval_gap_seconds = float(parameters[22])
        with _statement_deadline(connection, deadline):
            try:
                source_rows = tuple(connection.execute(
                    _PROJECTED_RANGE_CYCLES_SQL,
                    (
                        site_id,
                        from_utc,
                        to_utc,
                        from_utc,
                        to_utc,
                        from_utc,
                        from_utc,
                        to_utc,
                    ),
                ).fetchall())
            except sqlite3.OperationalError as exc:
                _translate_sqlite_error(exc, deadline)
                raise
        deadline.require_remaining()

        from_ms = _epoch_milliseconds(from_utc)
        to_ms = _epoch_milliseconds(to_utc)
        bucket_ms = bucket_seconds * 1000
        integrity_failure_count = 0
        buckets: dict[int, list[Mapping[str, Any]]] = {}
        for source_index, source_row in enumerate(source_rows):
            if source_index % 256 == 0:
                deadline.require_remaining()
            row = dict(source_row)
            finished_at = row["source_finished_at"]
            in_result_range = (
                isinstance(finished_at, str)
                and from_utc <= finished_at < to_utc
            )
            if not bool(row["integrity_ok"]):
                if in_result_range or (
                    finished_at is None
                    and from_utc <= str(row["source_started_at"]) < to_utc
                ):
                    integrity_failure_count += 1
                continue
            if not in_result_range:
                continue
            finished_ms = _epoch_milliseconds(str(finished_at))
            if finished_ms < from_ms or finished_ms >= to_ms:
                continue
            bucket_index = (finished_ms - from_ms) // bucket_ms
            row["finished_at"] = finished_at
            row["finished_ms"] = finished_ms
            row["bucket_index"] = int(bucket_index)
            buckets.setdefault(int(bucket_index), []).append(row)

        bucket_rows: list[dict[str, Any]] = []
        selected_complete: list[dict[str, Any]] = []
        selected_incomplete: list[dict[str, Any]] = []
        for bucket_offset, bucket_index in enumerate(sorted(buckets)):
            if bucket_offset % 64 == 0:
                deadline.require_remaining()
            rows = buckets[bucket_index]
            source, reason = _select_source(rows)
            complete_key = f"{source}_complete"
            download_key = f"{source}_download_mbps"
            upload_key = f"{source}_upload_mbps"
            samples = sorted(
                (row for row in rows if bool(row[complete_key])),
                key=lambda row: (str(row["finished_at"]), str(row["cycle_id"])),
            )
            prior_ms: int | None = None
            gaps: list[float] = []
            for row in samples:
                current_ms = int(row["finished_ms"])
                if prior_ms is not None:
                    gaps.append((current_ms - prior_ms) / 1000.0)
                prior_ms = current_ms
                selected_complete.append({
                    "cycle_id": str(row["cycle_id"]),
                    "bucket_index": bucket_index,
                    "finished_at": str(row["finished_at"]),
                    "finished_ms": current_ms,
                    "selected_source": source,
                    "download": float(row[download_key]),
                    "upload": float(row[upload_key]),
                })
            for row in rows:
                if not bool(row[complete_key]):
                    selected_incomplete.append({
                        "cycle_id": str(row["cycle_id"]),
                        "bucket_index": bucket_index,
                        "finished_at": str(row["finished_at"]),
                        "selected_source": source,
                    })
            pair_key = f"{source}_pair_count"
            bucket_rows.append({
                "bucket_index": bucket_index,
                "canonical_cycle_count": len(rows),
                "wired_complete_count": sum(
                    bool(row["wired_complete"]) for row in rows
                ),
                "lan_complete_count": sum(
                    bool(row["lan_complete"]) for row in rows
                ),
                "wired_pairs": sum(int(row["wired_pair_count"]) for row in rows),
                "lan_pairs": sum(int(row["lan_pair_count"]) for row in rows),
                "total_ap_opportunities": sum(
                    int(row["stored_row_count"]) for row in rows
                ),
                "empty_cycle_count": sum(
                    int(row["stored_row_count"]) == 0 for row in rows
                ),
                "selected_source": source,
                "selection_reason": reason,
                "complete_sample_count": len(samples),
                "download_mbps": (
                    sum(float(row[download_key]) for row in samples) / len(samples)
                    if samples else None
                ),
                "upload_mbps": (
                    sum(float(row[upload_key]) for row in samples) / len(samples)
                    if samples else None
                ),
                "first_sample": (
                    str(samples[0]["finished_at"]) if samples else None
                ),
                "last_sample": (
                    str(samples[-1]["finished_at"]) if samples else None
                ),
                "max_inter_gap": max(gaps, default=0.0),
                "inter_gap_count": sum(
                    gap > bucket_gap_seconds for gap in gaps
                ),
                "no_baseline_count": sum(
                    int(row[f"{source}_no_baseline_count"]) for row in rows
                ),
                "counter_reset_count": sum(
                    int(row[f"{source}_counter_reset_count"]) for row in rows
                ),
                "gap_too_large_count": sum(
                    int(row[f"{source}_gap_too_large_count"]) for row in rows
                ),
                "invalid_elapsed_count": sum(
                    int(row[f"{source}_invalid_elapsed_count"]) for row in rows
                ),
                "source_unavailable_count": sum(
                    int(row[f"{source}_source_unavailable_count"]) for row in rows
                ),
                "ok_count": sum(int(row[f"{source}_ok_count"]) for row in rows),
                "skew_excluded_count": sum(
                    int(row[pair_key]) == int(row["stored_row_count"])
                    and not bool(row[complete_key])
                    for row in rows
                ),
            })

        selected_complete.sort(
            key=lambda row: (str(row["finished_at"]), str(row["cycle_id"]))
        )
        accepted_seconds = weighted_download = weighted_upload = 0.0
        accepted_count = gap_count = transition_count = invalid_count = 0
        previous: dict[str, Any] | None = None
        peak_rows: list[dict[str, Any]] = []
        for sequence_no, row in enumerate(selected_complete, 1):
            if sequence_no % 256 == 0:
                deadline.require_remaining()
            previous_at = None if previous is None else str(previous["finished_at"])
            elapsed = None
            if previous is None:
                interval_result = "first"
            else:
                elapsed = (
                    int(row["finished_ms"]) - int(previous["finished_ms"])
                ) / 1000.0
                if elapsed <= 0:
                    interval_result = "invalid"
                    invalid_count += 1
                elif row["selected_source"] != previous["selected_source"]:
                    interval_result = "source_transition"
                    transition_count += 1
                elif elapsed > interval_gap_seconds:
                    interval_result = "gap"
                    gap_count += 1
                else:
                    interval_result = "accepted"
                    accepted_count += 1
                    accepted_seconds += elapsed
                    weighted_download += float(row["download"]) * elapsed
                    weighted_upload += float(row["upload"]) * elapsed
            peak_rows.append({
                "projection_kind": 1,
                "projection_order": sequence_no,
                "peak_sample_finished_at": row["finished_at"],
                "peak_sample_selected_source": row["selected_source"],
                "peak_sample_download": row["download"],
                "peak_sample_upload": row["upload"],
                "peak_sample_previous_at": previous_at,
                "peak_sample_interval_result": interval_result,
                "ap_support_cycle_id": row["cycle_id"],
                "ap_support_bucket_index": row["bucket_index"],
            })
            previous = row

        statistics = {
            "accepted_peak_sample_count": len(selected_complete),
            "candidate_interval_count": max(len(selected_complete) - 1, 0),
            "accepted_interval_count": accepted_count,
            "accepted_interval_seconds": accepted_seconds,
            "excluded_gap_interval_count": gap_count,
            "excluded_source_transition_interval_count": transition_count,
            "invalid_period_interval_count": invalid_count,
            "weighted_download": weighted_download if accepted_count else None,
            "weighted_upload": weighted_upload if accepted_count else None,
            "peak_download": max(
                (float(row["download"]) for row in selected_complete),
                default=None,
            ),
            "peak_upload": max(
                (float(row["upload"]) for row in selected_complete),
                default=None,
            ),
            "peak_total": max(
                (
                    float(row["download"]) + float(row["upload"])
                    for row in selected_complete
                ),
                default=None,
            ),
            "first_sample_at": (
                str(selected_complete[0]["finished_at"])
                if selected_complete else None
            ),
            "last_sample_at": (
                str(selected_complete[-1]["finished_at"])
                if selected_complete else None
            ),
        }
        empty_bucket = {
            name: None for name in (
                "bucket_index", "canonical_cycle_count", "wired_complete_count",
                "lan_complete_count", "wired_pairs", "lan_pairs",
                "total_ap_opportunities", "empty_cycle_count", "selected_source",
                "selection_reason", "complete_sample_count", "download_mbps",
                "upload_mbps", "first_sample", "last_sample", "max_inter_gap",
                "inter_gap_count", "no_baseline_count", "counter_reset_count",
                "gap_too_large_count", "invalid_elapsed_count",
                "source_unavailable_count", "ok_count", "skew_excluded_count",
            )
        }
        base_rows = bucket_rows or [empty_bucket]
        result: list[Mapping[str, Any]] = []
        for order, row in enumerate(base_rows):
            result.append({
                **row,
                "projection_kind": 0,
                "projection_order": order,
                "integrity_failure_count": integrity_failure_count,
                **statistics,
                "peak_sample_finished_at": None,
                "peak_sample_selected_source": None,
                "peak_sample_download": None,
                "peak_sample_upload": None,
                "peak_sample_previous_at": None,
                "peak_sample_interval_result": None,
                "ap_support_cycle_id": None,
                "ap_support_bucket_index": None,
            })
        result.extend(peak_rows)
        for sequence_no, row in enumerate(sorted(
            selected_incomplete,
            key=lambda item: (str(item["finished_at"]), str(item["cycle_id"])),
        ), 1):
            result.append({
                "projection_kind": 2,
                "projection_order": sequence_no,
                "peak_sample_finished_at": row["finished_at"],
                "peak_sample_selected_source": row["selected_source"],
                "peak_sample_download": None,
                "peak_sample_upload": None,
                "peak_sample_previous_at": None,
                "peak_sample_interval_result": None,
                "ap_support_cycle_id": row["cycle_id"],
                "ap_support_bucket_index": row["bucket_index"],
            })
        deadline.require_remaining()
        return tuple(result)

    def _historical_source_bounds(self, connection: sqlite3.Connection, **kwargs: Any) -> Mapping[str, str | None]:
        result = dict(self._source_bounds.get() or {})
        result["projection_version"] = self._active_version.get()
        result["projection_revision"] = self._revision.get()
        return result


def sqlite3_uri(path: str) -> str:
    from pathlib import Path
    return Path(path).resolve().as_uri() + "?mode=ro"
