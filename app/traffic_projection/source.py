"""Read-only authoritative Observation evidence for projection materialization."""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import time
from contextlib import closing, contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from app.analytics.historical_traffic import MAX_SITE_SAMPLE_SOURCE_SKEW_SECONDS
from app.analytics.source_gateway import AnalyticsSourceGateway, QueryDeadline

from .models import (
    RATE_REASONS,
    SOURCE_SCHEMA_VERSION,
    ProjectedCycle,
    TrafficProjectionSourceUnavailable,
)


_MARKER_FIELDS = (
    "cycle_id", "kind", "site_id", "state", "started_at", "finished_at",
    "abandoned_at", "complete", "result", "source_rows_reported", "items_seen",
    "items_stored", "items_skipped", "error_count", "data_quality_warning_count",
    "updated_at",
)
_AP_FIELDS = (
    "site_id", "ap_mac", "name", "partial", "overview_ok", "wired_uplink_ok",
    "lan_traffic_ok", "radios_ok", "wired_observed_at", "lan_observed_at",
    "wired_download_mbps", "wired_upload_mbps", "wired_download_rate_reason",
    "wired_upload_rate_reason", "lan_rx_mbps", "lan_tx_mbps",
    "lan_rx_rate_reason", "lan_tx_rate_reason",
)
_MAC = re.compile(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}")
_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z")


def _digest(values: Any) -> str:
    raw = json.dumps(values, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(raw.encode("ascii")).hexdigest()


def source_revision_marker(cycle: Mapping[str, Any]) -> str:
    return _digest([cycle.get(field) for field in _MARKER_FIELDS])


def source_semantic_fingerprint(
    cycle: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]
) -> str:
    ordered = sorted(rows, key=lambda row: str(row.get("ap_mac", "")))
    return _digest({
        "cycle": [cycle.get(field) for field in _MARKER_FIELDS],
        "aps": [[row.get(field) for field in _AP_FIELDS] for row in ordered],
    })


class TrafficProjectionSource:
    """Never writes the Observation database and never contacts Omada."""

    def __init__(self, db_path: str, *, busy_timeout_ms: int = 500):
        self.db_path = Path(db_path)
        self.busy_timeout_ms = int(busy_timeout_ms)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        uri = self.db_path.resolve().as_uri() + "?mode=ro"
        try:
            with closing(sqlite3.connect(uri, uri=True, timeout=self.busy_timeout_ms / 1000)) as connection:
                connection.row_factory = sqlite3.Row
                connection.execute(f"PRAGMA busy_timeout={self.busy_timeout_ms}")
                connection.execute("PRAGMA query_only=ON")
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if version != SOURCE_SCHEMA_VERSION:
                    raise TrafficProjectionSourceUnavailable(
                        "Observation source schema is unavailable"
                    )
                yield connection
        except TrafficProjectionSourceUnavailable:
            raise
        except (sqlite3.Error, OSError) as exc:
            raise TrafficProjectionSourceUnavailable(
                "Observation source is unavailable"
            ) from exc

    def head(self, site_id: str) -> tuple[str, str] | None:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT started_at,cycle_id FROM observation_cycles
                   INDEXED BY idx_cycles_site_kind_started
                   WHERE site_id=? AND kind='ap_dynamic'
                   ORDER BY started_at DESC,cycle_id DESC LIMIT 1""",
                (site_id,),
            ).fetchone()
            return None if row is None else (str(row[0]), str(row[1]))

    def metadata(
        self, site_id: str, *, from_utc: str, through: tuple[str, str],
        after: tuple[str, str] | None = None, limit: int = 500,
    ) -> tuple[Mapping[str, Any], ...]:
        clause = ""
        parameters: list[Any] = [site_id, from_utc, through[0], through[0], through[1]]
        if after is not None:
            clause = "AND (started_at>? OR (started_at=? AND cycle_id>?))"
            parameters.extend((after[0], after[0], after[1]))
        parameters.append(limit)
        with self.connection() as connection:
            return tuple(dict(row) for row in connection.execute(
                f"""SELECT * FROM observation_cycles INDEXED BY idx_cycles_site_kind_started
                    WHERE site_id=? AND kind='ap_dynamic' AND started_at>=?
                      AND (started_at<? OR (started_at=? AND cycle_id<=?)) {clause}
                    ORDER BY started_at,cycle_id LIMIT ?""",
                parameters,
            ))

    def cycle(self, site_id: str, cycle_id: str) -> ProjectedCycle | None:
        rows = self.cycles(site_id, (cycle_id,))
        return None if not rows else rows[0][1]

    def cycles(
        self,
        site_id: str,
        cycle_ids: Sequence[str],
        *,
        work_deadline_monotonic: float | None = None,
        monotonic=time.monotonic,
    ) -> tuple[tuple[str, ProjectedCycle | None], ...]:
        """Load one bounded cycle batch from one coherent source snapshot."""
        ordered_ids = tuple(dict.fromkeys(str(value) for value in cycle_ids))
        if not ordered_ids:
            return ()
        if len(ordered_ids) > 100:
            raise ValueError("source cycle batch exceeds the bounded maximum")
        if (
            work_deadline_monotonic is not None
            and monotonic() >= work_deadline_monotonic
        ):
            return ()
        placeholders = ",".join("?" for _ in ordered_ids)
        with self.connection() as connection:
            connection.execute("BEGIN")
            try:
                cycle_rows = connection.execute(
                    f"""SELECT * FROM observation_cycles
                        WHERE site_id=? AND kind='ap_dynamic'
                          AND cycle_id IN ({placeholders})""",
                    (site_id, *ordered_ids),
                ).fetchall()
                cycles_by_id = {
                    str(row["cycle_id"]): dict(row) for row in cycle_rows
                }
                ap_rows = connection.execute(
                    f"""SELECT cycle_id,{','.join(_AP_FIELDS)}
                        FROM ap_observations
                        WHERE cycle_id IN ({placeholders})
                        ORDER BY cycle_id,ap_mac""",
                    ordered_ids,
                ).fetchall()
                aps_by_cycle: dict[str, list[Mapping[str, Any]]] = {
                    cycle_id: [] for cycle_id in ordered_ids
                }
                for row in ap_rows:
                    raw = dict(row)
                    cycle_id = str(raw.pop("cycle_id"))
                    if cycle_id in aps_by_cycle:
                        aps_by_cycle[cycle_id].append(raw)
                result: list[tuple[str, ProjectedCycle | None]] = []
                for cycle_id in ordered_ids:
                    if (
                        work_deadline_monotonic is not None
                        and monotonic() >= work_deadline_monotonic
                    ):
                        break
                    cycle = cycles_by_id.get(cycle_id)
                    result.append((
                        cycle_id,
                        None if cycle is None else project_source_cycle(
                            cycle, aps_by_cycle[cycle_id]
                        ),
                    ))
                return tuple(result)
            finally:
                connection.rollback()

    def cycle_count(
        self, site_id: str, *, from_utc: str, through: tuple[str, str]
    ) -> int:
        with self.connection() as connection:
            return int(connection.execute(
                """SELECT COUNT(*) FROM observation_cycles
                   INDEXED BY idx_cycles_site_kind_started
                   WHERE site_id=? AND kind='ap_dynamic' AND started_at>=?
                     AND (started_at<? OR (started_at=? AND cycle_id<=?))""",
                (site_id, from_utc, through[0], through[0], through[1]),
            ).fetchone()[0])

    def boundaries(
        self, site_id: str, *, evaluated_at_utc: str
    ) -> Mapping[str, str | None]:
        """Capture canonical raw Historical source boundaries for persistence."""
        gateway = AnalyticsSourceGateway(None, None, None)
        try:
            with self.connection() as connection:
                connection.execute("BEGIN")
                try:
                    return gateway._historical_source_bounds(  # noqa: SLF001
                        connection,
                        site_id=site_id,
                        evaluated_at_utc=evaluated_at_utc,
                        max_skew_milliseconds=(
                            MAX_SITE_SAMPLE_SOURCE_SKEW_SECONDS * 1000
                        ),
                        deadline=QueryDeadline(float("inf")),
                    )
                finally:
                    connection.rollback()
        except Exception as exc:
            if isinstance(exc, TrafficProjectionSourceUnavailable):
                raise
            raise TrafficProjectionSourceUnavailable(
                "Observation source boundary is unavailable"
            ) from exc


def project_source_cycle(
    cycle: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]
) -> ProjectedCycle:
    marker = source_revision_marker(cycle)
    fingerprint = source_semantic_fingerprint(cycle, rows)
    site = cycle.get("site_id")
    started = _time(cycle.get("started_at"))
    finished = _time(cycle.get("finished_at"))
    deep = (
        cycle.get("state") == "completed" and cycle.get("complete") == 1
        and cycle.get("result") == "success" and finished is not None
        and started is not None and finished >= started
    )
    macs = [row.get("ap_mac") for row in rows]
    counts = {
        "stored_row_count": len(rows),
        "bad_site_count": sum(row.get("site_id") != site for row in rows),
        "bad_mac_count": sum(not isinstance(mac, str) or _MAC.fullmatch(mac) is None for mac in macs),
        "duplicate_mac_count": len(macs) - len(set(macs)),
        "bad_flag_count": 0,
        "bad_rate_count": 0,
        "bad_time_count": 0,
    }
    families = {
        "wired": ("wired_observed_at", "wired_download_mbps", "wired_upload_mbps",
                  "wired_download_rate_reason", "wired_upload_rate_reason"),
        "lan": ("lan_observed_at", "lan_rx_mbps", "lan_tx_mbps",
                "lan_rx_rate_reason", "lan_tx_rate_reason"),
    }
    pair: dict[str, int] = {"wired": 0, "lan": 0}
    times: dict[str, list[str]] = {"wired": [], "lan": []}
    sums: dict[str, list[float]] = {"wired": [0.0, 0.0], "lan": [0.0, 0.0]}
    reasons = {family: {reason: 0 for reason in RATE_REASONS} for family in families}
    ap_rows: list[Mapping[str, Any]] = []
    for row in rows:
        expected_flags = {
            "partial": 0,
            "overview_ok": 1,
            "wired_uplink_ok": 1,
            "lan_traffic_ok": 1,
            "radios_ok": 1,
        }
        if any(
            type(row.get(flag)) is not int or row.get(flag) != expected
            for flag, expected in expected_flags.items()
        ):
            counts["bad_flag_count"] += 1
        projected_row = {
            "ap_mac": row.get("ap_mac"), "historical_name": row.get("name"),
            "partial": row.get("partial"), "overview_ok": row.get("overview_ok"),
            "wired_uplink_ok": row.get("wired_uplink_ok"),
            "lan_traffic_ok": row.get("lan_traffic_ok"), "radios_ok": row.get("radios_ok"),
            "wired_observed_at": row.get("wired_observed_at"),
            "lan_observed_at": row.get("lan_observed_at"),
            "wired_download_mbps": row.get("wired_download_mbps"),
            "wired_upload_mbps": row.get("wired_upload_mbps"),
            "wired_download_reason": row.get("wired_download_rate_reason"),
            "wired_upload_reason": row.get("wired_upload_rate_reason"),
            "lan_download_mbps": row.get("lan_rx_mbps"),
            "lan_upload_mbps": row.get("lan_tx_mbps"),
            "lan_download_reason": row.get("lan_rx_rate_reason"),
            "lan_upload_reason": row.get("lan_tx_rate_reason"),
        }
        ap_rows.append(projected_row)
        row_bad_rate = False
        row_bad_time = False
        for family, fields in families.items():
            timestamp, down, up, down_reason, up_reason = (row.get(name) for name in fields)
            valid_time = _time(timestamp)
            if valid_time is None or started is None or finished is None or not (started <= valid_time <= finished):
                row_bad_time = True
            valid = True
            for value, reason in ((down, down_reason), (up, up_reason)):
                if reason not in RATE_REASONS or (
                    (reason == "ok" and not _rate(value))
                    or (reason != "ok" and value is not None)
                ):
                    row_bad_rate = True
                    valid = False
                if reason in RATE_REASONS:
                    reasons[family][reason] += 1
            if valid and down_reason == up_reason == "ok" and valid_time is not None and started is not None and finished is not None and started <= valid_time <= finished:
                pair[family] += 1
                times[family].append(str(timestamp))
                sums[family][0] += float(down)
                sums[family][1] += float(up)
        counts["bad_rate_count"] += int(row_bad_rate)
        counts["bad_time_count"] += int(row_bad_time)
    metadata_ok = (
        deep and cycle.get("source_rows_reported") == cycle.get("items_seen")
        and cycle.get("items_seen") == cycle.get("items_stored")
        and cycle.get("items_skipped") == 0 and cycle.get("error_count") == 0
        and cycle.get("data_quality_warning_count") == 0
        and cycle.get("items_stored") == len(rows)
    )
    integrity_ok = bool(metadata_ok and not any(counts[key] for key in counts if key != "stored_row_count"))
    metric_facts = integrity_ok
    facts: dict[str, Any] = {}
    for family in families:
        complete = metric_facts and (
            not rows
            or (
                pair[family] == len(rows)
                and _spread_seconds(times[family]) <= 60.0
            )
        )
        facts.update({
            f"{family}_complete": int(complete), f"{family}_pair_count": pair[family],
            f"{family}_oldest_at": min(times[family]) if times[family] else None,
            f"{family}_newest_at": max(times[family]) if times[family] else None,
            f"{family}_download_mbps": sums[family][0] if metric_facts else None,
            f"{family}_upload_mbps": sums[family][1] if metric_facts else None,
        })
        for reason in RATE_REASONS:
            facts[f"{family}_{reason}_count"] = reasons[family][reason]
    return ProjectedCycle(
        cycle=dict(cycle), ap_rows=tuple(ap_rows) if metric_facts else (),
        source_revision_marker=marker, source_semantic_fingerprint=fingerprint,
        integrity_ok=integrity_ok, metric_facts_present=metric_facts,
        integrity_counts=counts, family_facts=facts,
    )


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str) or _UTC.fullmatch(value) is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else None
    except ValueError:
        return None


def _rate(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _spread_seconds(values: Sequence[str]) -> float:
    if not values:
        return 0.0
    parsed = [_time(value) for value in values]
    if any(value is None for value in parsed):
        return float("inf")
    return (max(parsed) - min(parsed)).total_seconds()  # type: ignore[type-var,operator]
