"""Read-only rolling 24-hour AP evidence model for the Admin Home page."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from app.current_state.ap_status import classify_ap_status_code

from .source_gateway import AnalyticsQueryDeadlineExceeded, QueryDeadline
from .validation import format_utc, require_site


UTC = timezone.utc
CONTRACT_VERSION = "admin.home_ap_24h.v1"
WINDOW_SECONDS = 86400
BUCKET_SECONDS = 900
BUCKET_COUNT = 96
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 20
CURRENT_SCHEMA_VERSION = 1
OBSERVATION_SCHEMA_VERSION = 1
# Match the existing bounded Admin read gateways: frequent enough for prompt
# cancellation without turning every large read into millions of Python calls.
_PROGRESS_OPCODES = 10_000


class HomeAp24Error(RuntimeError):
    pass


class HomeAp24ValidationError(HomeAp24Error):
    pass


class HomeAp24SourceUnavailable(HomeAp24Error):
    pass


def _parse(value: object) -> datetime:
    if not isinstance(value, str):
        raise HomeAp24SourceUnavailable("source timestamp is invalid")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError as exc:
        raise HomeAp24SourceUnavailable("source timestamp is invalid") from exc
    return parsed.replace(tzinfo=UTC)


def _seconds(start: datetime, end: datetime) -> int:
    return max(0, int(round((end - start).total_seconds())))


def _max_gap(values: Iterable[datetime]) -> int | None:
    ordered = sorted(set(values))
    if len(ordered) < 2:
        return None
    return max(_seconds(left, right) for left, right in zip(ordered, ordered[1:]))


class HomeAp24ReadService:
    """Compose persisted AP state and diagnostic evidence without writes."""

    def __init__(
        self,
        current_state_read_service: Any,
        observation_read_service: Any,
        *,
        current_state_ap_interval_seconds: int,
        quality_gap_seconds: int,
        observation_dynamic_max_requests: int,
    ):
        if current_state_read_service is None or observation_read_service is None:
            raise TypeError("AP-24H read sources are required")
        if type(current_state_ap_interval_seconds) is not int or current_state_ap_interval_seconds <= 0:
            raise ValueError("Current State interval is invalid")
        if type(quality_gap_seconds) is not int or quality_gap_seconds <= 0:
            raise ValueError("quality gap is invalid")
        if type(observation_dynamic_max_requests) is not int or observation_dynamic_max_requests <= 0:
            raise ValueError("Observation request budget is invalid")
        self._current = current_state_read_service
        self._observations = observation_read_service
        self._current_interval = current_state_ap_interval_seconds
        self._cs_gap = max(3 * current_state_ap_interval_seconds, quality_gap_seconds)
        self._obs_gap = quality_gap_seconds
        self._obs_capacity = observation_dynamic_max_requests // 4

    def get_home_ap_24h(
        self,
        site_id: str,
        *,
        evaluated_at_utc: datetime | None = None,
        after_ap_mac: str | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
        deadline: QueryDeadline,
    ) -> dict[str, Any]:
        try:
            site = require_site(site_id)
        except Exception as exc:
            raise HomeAp24ValidationError("Site is invalid") from exc
        if type(limit) is not int or not 1 <= limit <= MAX_PAGE_SIZE:
            raise HomeAp24ValidationError("limit is outside bounds")
        anchor = evaluated_at_utc or datetime.now(UTC)
        if anchor.tzinfo is None:
            raise HomeAp24ValidationError("evaluation time must be timezone-aware")
        anchor = anchor.astimezone(UTC).replace(microsecond=(anchor.microsecond // 1000) * 1000)
        start = anchor - timedelta(seconds=WINDOW_SECONDS)
        cs_start = start - timedelta(seconds=self._cs_gap)
        current = observation = None
        current_error = observation_error = None
        try:
            current = self._read_current(site, cs_start, anchor, deadline)
        except AnalyticsQueryDeadlineExceeded:
            raise
        except (sqlite3.Error, OSError, HomeAp24SourceUnavailable) as exc:
            current_error = exc
        try:
            observation = self._read_observations(
                site,
                start,
                anchor,
                deadline,
                current_roster=() if current is None else current["roster"],
                after_ap_mac=after_ap_mac,
                limit=limit,
            )
        except AnalyticsQueryDeadlineExceeded:
            raise
        except (sqlite3.Error, OSError, HomeAp24SourceUnavailable) as exc:
            observation_error = exc
        if current is None and observation is None:
            raise HomeAp24SourceUnavailable("AP-24H sources are unavailable") from (
                current_error or observation_error
            )

        roster = sorted(
            set(() if current is None else current["roster"])
            | set(() if observation is None else observation["roster"])
        )
        if observation is not None and len(roster) > self._obs_capacity:
            observation["source"]["status"] = "degraded"
            reasons = observation["source"].setdefault("reason_codes", [])
            if "observation_cycle_capacity_exceeded" not in reasons:
                reasons.append("observation_cycle_capacity_exceeded")
        selected_macs = [mac for mac in roster if after_ap_mac is None or mac > after_ap_mac]
        page_macs = selected_macs[:limit]
        page_set = set(page_macs)
        all_items = []
        for ap_index, mac in enumerate(roster):
            if ap_index % 25 == 0:
                deadline.require_remaining()
            deadline.require_remaining()
            all_items.append(
                self._ap_item(
                    mac, start, anchor, current, observation,
                    include_timeline=mac in page_set,
                )
            )
        summary = self._summary(all_items)
        by_mac = {item["ap_mac"]: item for item in all_items}
        page_items = [by_mac[mac] for mac in page_macs]
        has_more = len(selected_macs) > limit
        sources = {
            "current_state": self._source_payload(None if current is None else current["source"]),
            "observations": self._source_payload(None if observation is None else observation["source"]),
        }
        if not roster:
            block_status, block_reason = "unknown", "no_historical_evidence"
        elif current is None or observation is None:
            block_status, block_reason = "degraded", "source_partially_unavailable"
        elif any(value["status"] != "operational" for value in sources.values()):
            block_status, block_reason = "degraded", "source_evidence_degraded"
        else:
            block_status, block_reason = "operational", None
        return {
            "contract_version": CONTRACT_VERSION,
            "window": {
                "kind": "rolling_24h",
                "evaluated_at_utc": format_utc(anchor),
                "from_utc": format_utc(start),
                "to_utc": format_utc(anchor),
                "bucket_seconds": BUCKET_SECONDS,
                "bucket_count": BUCKET_COUNT,
            },
            "block_status": block_status,
            "block_reason": block_reason,
            "sources": sources,
            "summary": summary,
            "items": page_items,
            "page": {"limit": limit, "has_more": has_more},
        }

    def _read_current(self, site: str, start: datetime, end: datetime, deadline: QueryDeadline):
        with self._current.analytics_read_connection() as connection:
            with _read_snapshot(connection, deadline, CURRENT_SCHEMA_VERSION):
                cycles = connection.execute(
                    """
                    SELECT cycle_id, capture_started_at, capture_finished_at,
                           complete, result
                    FROM current_state_cycles
                    WHERE kind='ap' AND site_id=?
                      AND capture_started_at>=? AND capture_started_at<?
                    ORDER BY capture_started_at, cycle_id
                    """,
                    (site, format_utc(start), format_utc(end)),
                ).fetchall()
                authoritative = [
                    row for row in cycles
                    if row["result"] == "success" and row["complete"] == 1
                ]
                cycle_times = {
                    str(row["cycle_id"]): _parse(row["capture_started_at"])
                    for row in authoritative
                }
                rows_by_cycle: dict[str, dict[str, tuple[Any, ...]]] = defaultdict(dict)
                roster: set[str] = set()
                identity: dict[str, tuple[datetime, str | None, str | None]] = {}
                first_evidence: dict[str, datetime] = {}
                cursor = connection.execute(
                    """
                    SELECT a.cycle_id, a.observed_at, a.ap_mac, a.name, a.model,
                           a.status_code, c.capture_started_at
                    FROM current_ap_state a
                    JOIN current_state_cycles c ON c.cycle_id=a.cycle_id
                    WHERE a.site_id=? AND c.kind='ap'
                      AND c.result='success' AND c.complete=1
                      AND c.capture_started_at>=? AND c.capture_started_at<?
                    """,
                    (site, format_utc(start), format_utc(end)),
                )
                for index, row in enumerate(cursor):
                    if index % 10000 == 0:
                        deadline.require_remaining()
                    cycle_id = str(row["cycle_id"])
                    mac = str(row["ap_mac"])
                    timestamp = cycle_times[cycle_id]
                    roster.add(mac)
                    rows_by_cycle[cycle_id][mac] = (
                        row["status_code"], str(row["observed_at"])
                    )
                    if mac not in first_evidence or timestamp < first_evidence[mac]:
                        first_evidence[mac] = timestamp
                    if mac not in identity or timestamp >= identity[mac][0]:
                        identity[mac] = (timestamp, row["name"], row["model"])
                latest_inventory_rows = connection.execute(
                    """
                    SELECT a.cycle_id, a.observed_at, a.ap_mac, a.name, a.model,
                           a.status_code, c.capture_started_at
                    FROM current_ap_state a
                    JOIN current_state_cycles c ON c.cycle_id=a.cycle_id
                    WHERE a.site_id=? AND c.kind='ap'
                      AND c.result='success' AND c.complete=1
                      AND c.cycle_id=(
                          SELECT latest.cycle_id
                          FROM current_state_cycles latest
                          WHERE latest.kind='ap' AND latest.site_id=?
                            AND latest.result='success' AND latest.complete=1
                            AND latest.capture_started_at<?
                          ORDER BY latest.capture_started_at DESC, latest.cycle_id DESC
                          LIMIT 1
                      )
                    """,
                    (site, site, format_utc(end)),
                ).fetchall()
                # The roster contract includes the latest trustworthy Site
                # inventory even when it predates the rolling history window.
                # Such rows provide identity/membership only.
                for index, row in enumerate(latest_inventory_rows):
                    if index % 10000 == 0:
                        deadline.require_remaining()
                    mac = str(row["ap_mac"])
                    timestamp = _parse(row["capture_started_at"])
                    roster.add(mac)
                    if mac not in identity or timestamp >= identity[mac][0]:
                        identity[mac] = (timestamp, row["name"], row["model"])
                deadline.require_remaining()
        timestamps = list(cycle_times.values())
        samples_by_ap = {}
        for ap_index, mac in enumerate(roster):
            if ap_index % 25 == 0:
                deadline.require_remaining()
            first = first_evidence.get(mac)
            if first is None:
                samples_by_ap[mac] = []
                continue
            samples = []
            for cycle in authoritative:
                cycle_id = str(cycle["cycle_id"])
                timestamp = cycle_times[cycle_id]
                if timestamp < first:
                    continue
                evidence = rows_by_cycle.get(cycle_id, {}).get(mac)
                if evidence is None:
                    samples.append((timestamp, "unknown", "not_in_complete_inventory", format_utc(timestamp)))
                    continue
                status_code, observed_at = evidence
                mapped = classify_ap_status_code(status_code)
                state = {"online": "operational", "offline": "unavailable"}.get(mapped, "unknown")
                reason = {
                    "online": "fresh_online_evidence",
                    "offline": "controller_reported_offline",
                    "other": "controller_status_other",
                    "unknown": "controller_status_unknown",
                }[mapped]
                samples.append((timestamp, state, reason, observed_at))
            samples_by_ap[mac] = samples
        partial = sum(1 for row in cycles if row["result"] == "partial")
        failed = sum(1 for row in cycles if row["result"] in {"failed", "shutdown"})
        source_status = "unknown" if not cycles else (
            "degraded" if partial or failed or (_max_gap(timestamps) or 0) > self._cs_gap else "operational"
        )
        return {
            "samples": samples_by_ap,
            "roster": roster,
            "identity": identity,
            "source": {
                "status": source_status,
                "schema_version": CURRENT_SCHEMA_VERSION,
                "first_evidence_at": format_utc(min(timestamps)) if timestamps else None,
                "last_evidence_at": format_utc(max(timestamps)) if timestamps else None,
                "complete_cycle_count": len(authoritative),
                "partial_cycle_count": partial,
                "failed_cycle_count": failed,
                "max_gap_seconds": _max_gap(timestamps),
            },
        }

    def _read_observations(
        self,
        site: str,
        start: datetime,
        end: datetime,
        deadline: QueryDeadline,
        *,
        current_roster: Iterable[str],
        after_ap_mac: str | None,
        limit: int,
    ):
        row_start = start - timedelta(seconds=self._obs_gap)
        start_text = format_utc(start)
        end_text = format_utc(end)
        page_candidates = set(sorted(
            mac for mac in current_roster
            if after_ap_mac is None or mac > after_ap_mac
        )[:limit])
        with self._observations.analytics_read_connection() as connection:
            with _read_snapshot(connection, deadline, OBSERVATION_SCHEMA_VERSION):
                cycles = connection.execute(
                    """
                    SELECT cycle_id, started_at, finished_at, complete, result, state
                    FROM observation_cycles
                    WHERE site_id=? AND kind='ap_dynamic'
                      AND started_at>=? AND started_at<?
                    ORDER BY started_at, cycle_id
                    """,
                    (site, start_text, end_text),
                ).fetchall()
                cursor = connection.execute(
                    """
                    SELECT o.observed_at,
                           CAST(ROUND((julianday(o.observed_at)-2440587.5)*86400000.0)
                                AS INTEGER) AS observed_epoch_ms,
                           o.ap_mac, o.name, o.model, o.partial,
                           o.overview_ok, o.wired_uplink_ok,
                           o.lan_traffic_ok, o.radios_ok
                    FROM ap_observations o
                    JOIN observation_cycles c ON c.cycle_id=o.cycle_id
                    WHERE o.site_id=? AND c.kind='ap_dynamic'
                      AND c.state='completed'
                      AND c.result IN ('success', 'partial')
                      AND o.observed_at>=? AND o.observed_at<?
                    ORDER BY o.observed_at
                    """,
                    (site, format_utc(row_start), end_text),
                )
                aggregates: dict[str, dict[str, Any]] = {}
                rows_by_ap: dict[str, list[tuple[Any, ...]]] = defaultdict(list)
                carry_by_ap: dict[str, list[tuple[Any, ...]]] = defaultdict(list)
                roster: set[str] = set()
                for index, row in enumerate(cursor):
                    if index % 10000 == 0:
                        deadline.require_remaining()
                    mac = str(row["ap_mac"])
                    value = aggregates.setdefault(mac, {
                        "ap_mac": mac,
                        "name": None,
                        "model": None,
                        "identity_at": None,
                        "row_count": 0,
                        "complete_count": 0,
                        "partial_count": 0,
                        "overview_problem_count": 0,
                        "wired_problem_count": 0,
                        "lan_problem_count": 0,
                        "radios_problem_count": 0,
                        "first_complete_at": None,
                        "last_complete_at": None,
                        "last_complete_epoch_ms": None,
                        "max_complete_gap_seconds": None,
                    })
                    timestamp = str(row["observed_at"])
                    compact_row = (
                        timestamp,
                        row["partial"],
                        row["overview_ok"],
                        row["wired_uplink_ok"],
                        row["lan_traffic_ok"],
                        row["radios_ok"],
                    )
                    complete = (
                        row["partial"] == 0
                        and row["overview_ok"] == 1
                        and row["wired_uplink_ok"] == 1
                        and row["lan_traffic_ok"] == 1
                        and row["radios_ok"] == 1
                    )
                    if complete:
                        epoch_ms = int(row["observed_epoch_ms"])
                        previous_ms = value["last_complete_epoch_ms"]
                        if previous_ms is not None:
                            gap = max(0.0, (epoch_ms - previous_ms) / 1000.0)
                            previous_gap = value["max_complete_gap_seconds"]
                            value["max_complete_gap_seconds"] = (
                                gap if previous_gap is None else max(previous_gap, gap)
                            )
                        value["last_complete_epoch_ms"] = epoch_ms
                        value["last_complete_at"] = timestamp
                        if value["first_complete_at"] is None:
                            value["first_complete_at"] = timestamp
                    if timestamp < start_text:
                        if mac in page_candidates:
                            rows_by_ap[mac].append(compact_row)
                        else:
                            carry_by_ap[mac].append(compact_row)
                        continue
                    if mac not in roster:
                        roster.add(mac)
                        if after_ap_mac is None or mac > after_ap_mac:
                            previous_candidates = page_candidates
                            page_candidates = set(sorted(page_candidates | {mac})[:limit])
                            for evicted in previous_candidates - page_candidates:
                                rows_by_ap.pop(evicted, None)
                            if mac in page_candidates and mac not in previous_candidates:
                                rows_by_ap[mac].extend(carry_by_ap.get(mac, ()))
                        carry_by_ap.pop(mac, None)
                    if mac in page_candidates:
                        rows_by_ap[mac].append(compact_row)
                    value["row_count"] += 1
                    value["complete_count" if complete else "partial_count"] += 1
                    value["overview_problem_count"] += int(row["overview_ok"] != 1)
                    value["wired_problem_count"] += int(row["wired_uplink_ok"] != 1)
                    value["lan_problem_count"] += int(row["lan_traffic_ok"] != 1)
                    value["radios_problem_count"] += int(row["radios_ok"] != 1)
                    if row["overview_ok"] == 1:
                        value["name"] = row["name"]
                        value["model"] = row["model"]
                        value["identity_at"] = timestamp
                deadline.require_remaining()
        identity: dict[str, tuple[datetime, str | None, str | None]] = {}
        for mac, value in aggregates.items():
            value.pop("last_complete_epoch_ms", None)
            if value["identity_at"] is not None:
                identity[mac] = (
                    _parse(value["identity_at"]), value["name"], value["model"]
                )
        completed = [row for row in cycles if row["state"] == "completed"]
        timestamps = [_parse(row["started_at"]) for row in completed]
        partial = sum(1 for row in completed if row["result"] == "partial")
        failed = sum(1 for row in completed if row["result"] in {"failed", "shutdown"})
        abandoned = any(row["state"] == "abandoned" for row in cycles)
        successful = sum(
            1 for row in completed
            if row["result"] == "success" and row["complete"] == 1
        )
        inconsistent_completed = any(
            row["result"] == "success" and row["complete"] != 1
            for row in completed
        )
        capacity = len(roster) > self._obs_capacity
        if not completed and not abandoned:
            # No completed history exists yet.  A normal in-flight cycle is
            # not degradation evidence, but it is not operational history.
            source_status = "unknown"
        elif (
            partial
            or failed
            or abandoned
            or inconsistent_completed
            or capacity
            or (_max_gap(timestamps) or 0) > self._obs_gap
        ):
            source_status = "degraded"
        else:
            source_status = "operational" if successful else "unknown"
        reasons = ["observation_cycle_capacity_exceeded"] if capacity else []
        return {
            "rows": rows_by_ap,
            "aggregates": aggregates,
            "roster": roster,
            "identity": identity,
            "source": {
                "status": source_status,
                "schema_version": OBSERVATION_SCHEMA_VERSION,
                "first_evidence_at": format_utc(min(timestamps)) if timestamps else None,
                "last_evidence_at": format_utc(max(timestamps)) if timestamps else None,
                "complete_cycle_count": successful,
                "partial_cycle_count": partial,
                "failed_cycle_count": failed,
                "max_gap_seconds": _max_gap(timestamps),
                "reason_codes": reasons,
            },
        }

    def _ap_item(self, mac, start, end, current, observation, *, include_timeline):
        identity = None
        identity_source = None
        if current is not None:
            identity = current["identity"].get(mac)
            if identity is not None:
                identity_source = "current_state"
        if identity is None and observation is not None:
            identity = observation["identity"].get(mac)
            if identity is not None:
                identity_source = "observations"
        timeline, history, current_value = self._state_timeline(
            mac, start, end, current, include_timeline=include_timeline
        )
        obs_value, obs_buckets = self._observation_timeline(
            mac, start, end, observation, include_timeline=include_timeline
        )
        if include_timeline:
            for bucket, quality in zip(timeline, obs_buckets):
                bucket.update(quality)
        history["current_vs_24h"] = _comparison(current_value["status"], history["status"], history["coverage_status"])
        return {
            "ap_mac": mac,
            "name": None if identity is None else identity[1],
            "model": None if identity is None else identity[2],
            "identity_source": identity_source,
            "current": current_value,
            "history": history,
            "observation_quality": obs_value,
            "timeline": timeline,
        }

    def _state_timeline(self, mac, start, end, current, *, include_timeline):
        buckets = (
            [_empty_bucket(start + timedelta(seconds=i * BUCKET_SECONDS)) for i in range(BUCKET_COUNT)]
            if include_timeline else []
        )
        if current is None:
            for bucket in buckets:
                bucket["ap_state_reason"] = "source_unavailable"
                bucket["unknown_evidence_seconds"] = BUCKET_SECONDS
            history = _empty_history()
            history.update({
                "reason_code": "source_unavailable",
                "unknown_evidence_seconds": WINDOW_SECONDS,
                "short_history_seconds": 0,
            })
            return buckets, history, _unknown_current("source_unavailable")
        samples = current["samples"].get(mac, [])
        if not samples:
            known_identity = current["identity"].get(mac)
            if known_identity is not None and known_identity[0] < start:
                for bucket in buckets:
                    bucket["ap_state_reason"] = "current_state_source_gap"
                    bucket["unknown_evidence_seconds"] = BUCKET_SECONDS
                    bucket["short_history_seconds"] = 0
                evidence_at = format_utc(known_identity[0])
                history = _empty_history()
                history.update({
                    "reason_code": "current_state_source_gap",
                    "history_eligible_from": format_utc(start),
                    "first_evidence_at": evidence_at,
                    "last_evidence_at": evidence_at,
                    "unknown_evidence_seconds": WINDOW_SECONDS,
                    "short_history_seconds": 0,
                })
                return (
                    buckets,
                    history,
                    _unknown_current("current_state_source_gap"),
                )
            for bucket in buckets:
                bucket["short_history_seconds"] = BUCKET_SECONDS
            return buckets, _empty_history(), _unknown_current("no_current_state_evidence")
        first = samples[0][0]
        has_source_gap = False
        operational = unavailable = unknown = 0
        sample_count = 0
        max_gap_seconds = None
        previous_distinct_at = None
        for index, sample in enumerate(samples):
            sample_at, state, reason, _ = sample
            if start <= sample_at < end:
                sample_count += 1
            if previous_distinct_at is not None and sample_at != previous_distinct_at:
                gap = _seconds(previous_distinct_at, sample_at)
                max_gap_seconds = gap if max_gap_seconds is None else max(max_gap_seconds, gap)
            if previous_distinct_at is None or sample_at != previous_distinct_at:
                previous_distinct_at = sample_at
            next_at = samples[index + 1][0] if index + 1 < len(samples) else end
            valid_to = min(next_at, sample_at + timedelta(seconds=self._cs_gap), end)
            valid_from = max(sample_at, start)
            if valid_to > valid_from:
                duration = _seconds(valid_from, valid_to)
                if state == "operational":
                    operational += duration
                elif state == "unavailable":
                    unavailable += duration
                else:
                    unknown += duration
                if include_timeline:
                    _apply_interval(buckets, start, valid_from, valid_to, state, reason)
            gap_to = min(next_at, end)
            if gap_to > valid_to:
                unknown += _seconds(valid_to, gap_to)
                has_source_gap = True
                if include_timeline:
                    _apply_interval(
                        buckets,
                        start,
                        valid_to,
                        gap_to,
                        "unknown",
                        "current_state_source_gap",
                    )
        short_to = min(max(first, start), end)
        if include_timeline and short_to > start:
            _apply_interval(buckets, start, start, short_to, "short", "before_first_evidence")
        if include_timeline:
            for sample_at, _state, _reason, _observed_at in samples:
                if start <= sample_at < end:
                    bucket_index = int((sample_at - start).total_seconds() // BUCKET_SECONDS)
                    buckets[bucket_index]["authoritative_state_sample_count"] += 1
            for bucket in buckets:
                _reduce_state_bucket(bucket)
        eligible = max(0, _seconds(max(first, start), end))
        covered = operational + unavailable + unknown
        coverage = "insufficient_data" if not samples else (
            "complete" if covered >= eligible and not has_source_gap else "partial"
        )
        if coverage != "complete" or unknown:
            status, reason = "unknown", "history_evidence_incomplete" if coverage != "complete" else "unknown_state_evidence"
        elif operational and unavailable:
            status, reason = "degraded", "mixed_operational_unavailable"
        elif unavailable and not operational:
            status, reason = "unavailable", "controller_reported_offline"
        elif operational:
            status, reason = "operational", "operational_history"
        else:
            status, reason = "unknown", "no_historical_evidence"
        last = samples[-1] if samples else None
        if last is None or _seconds(last[0], end) > self._cs_gap:
            current_value = _unknown_current("current_state_source_gap")
        else:
            age = _seconds(last[0], end)
            freshness = "fresh" if age <= 2 * self._current_interval else "stale"
            current_value = {
                "status": last[1], "reason_code": last[2],
                "observed_at": last[3], "freshness_status": freshness,
            }
        history = {
            "status": status, "reason_code": reason,
            "coverage_status": coverage,
            "history_eligible_from": format_utc(max(first, start)),
            "first_evidence_at": format_utc(first),
            "last_evidence_at": last[3] if last else None,
            "authoritative_sample_count": sample_count,
            "operational_seconds": operational,
            "unavailable_seconds": unavailable,
            "unknown_evidence_seconds": unknown,
            "short_history_seconds": _seconds(start, short_to),
            "max_gap_seconds": max_gap_seconds,
        }
        return buckets, history, current_value

    def _observation_timeline(self, mac, start, end, observation, *, include_timeline):
        empty = (
            [_empty_observation_bucket() for _ in range(BUCKET_COUNT)]
            if include_timeline else []
        )
        if observation is None:
            for bucket in empty:
                bucket["observation_quality"] = "unavailable"
                bucket["observation_reason_codes"] = ["source_unavailable"]
            return _empty_observation("unavailable", "source_unavailable"), empty
        rows = observation["rows"].get(mac, [])
        aggregate = observation["aggregates"].get(mac)
        if aggregate is None:
            return _empty_observation("unknown", "no_observation_evidence"), empty
        if not include_timeline:
            complete_count = int(aggregate["complete_count"])
            partial_count = int(aggregate["partial_count"])
            section_counts = {
                "overview": int(aggregate["overview_problem_count"]),
                "wired_uplink": int(aggregate["wired_problem_count"]),
                "lan_traffic": int(aggregate["lan_problem_count"]),
                "radios": int(aggregate["radios_problem_count"]),
            }
            if partial_count:
                status, reason = "degraded", "ap_local_evidence_degraded"
            elif complete_count and _aggregate_observation_continuous(
                aggregate, start, end, self._obs_gap
            ):
                status, reason = "operational", None
            elif complete_count:
                status, reason = "unknown", "observation_source_gap"
            else:
                status, reason = "unknown", "no_observation_evidence"
            return {
                "status": status,
                "reason_code": reason,
                "complete_sample_count": complete_count,
                "diagnostic_partial_sample_count": partial_count,
                "section_problem_counts": section_counts,
            }, empty
        section_counts = {"overview": 0, "wired_uplink": 0, "lan_traffic": 0, "radios": 0}
        complete_count = partial_count = 0
        by_bucket: dict[int, list[tuple[datetime, bool, list[str]]]] = defaultdict(list)
        complete_times = []
        for row in rows:
            (
                observed_at,
                partial,
                overview_ok,
                wired_uplink_ok,
                lan_traffic_ok,
                radios_ok,
            ) = row
            timestamp = _parse(observed_at)
            index = int((timestamp - start).total_seconds() // BUCKET_SECONDS)
            if not 0 <= index < BUCKET_COUNT:
                if (
                    timestamp < start
                    and partial == 0
                    and overview_ok == wired_uplink_ok == lan_traffic_ok == radios_ok == 1
                ):
                    complete_times.append(timestamp)
                continue
            reasons = []
            for value, label in (
                (overview_ok, "overview"),
                (wired_uplink_ok, "wired_uplink"),
                (lan_traffic_ok, "lan_traffic"),
                (radios_ok, "radios"),
            ):
                if value != 1:
                    section_counts[label] += 1
                    reasons.append(f"{label}_unobserved")
            complete = partial == 0 and not reasons
            if complete:
                complete_times.append(timestamp)
            if complete:
                complete_count += 1
            else:
                partial_count += 1
                if partial == 1 and not reasons:
                    reasons.append("rate_quality_degraded")
            if include_timeline:
                by_bucket[index].append((timestamp, complete, reasons))
        for index, bucket in enumerate(empty):
            samples = by_bucket.get(index, [])
            bucket["complete_observation_sample_count"] = sum(1 for _, ok, _ in samples if ok)
            bucket["diagnostic_partial_observation_sample_count"] = sum(1 for _, ok, _ in samples if not ok)
            degraded = sorted({reason for _, ok, reasons in samples if not ok for reason in reasons})
            if degraded:
                bucket["observation_quality"] = "degraded"
                bucket["observation_reason_codes"] = degraded
            elif _continuous_observation_bucket(
                complete_times,
                start + timedelta(seconds=index * BUCKET_SECONDS),
                start + timedelta(seconds=(index + 1) * BUCKET_SECONDS),
                self._obs_gap,
            ):
                bucket["observation_quality"] = "operational"
            else:
                bucket["observation_quality"] = "unknown"
                bucket["observation_reason_codes"] = ["observation_source_gap"]
        if partial_count:
            status, reason = "degraded", "ap_local_evidence_degraded"
        elif complete_count and (
            all(bucket["observation_quality"] == "operational" for bucket in empty)
            if include_timeline
            else _continuous_observation_bucket(complete_times, start, end, self._obs_gap)
        ):
            status, reason = "operational", None
        elif complete_count:
            status, reason = "unknown", "observation_source_gap"
        else:
            status, reason = "unknown", "no_observation_evidence"
        return {
            "status": status, "reason_code": reason,
            "complete_sample_count": complete_count,
            "diagnostic_partial_sample_count": partial_count,
            "section_problem_counts": section_counts,
        }, empty

    @staticmethod
    def _summary(items):
        summary = {
            "ap_count_in_window": len(items),
            "current": {key: 0 for key in ("operational", "degraded", "unavailable", "unknown")},
            "history": {key: 0 for key in ("operational", "degraded", "unavailable", "unknown")},
            "observation_quality": {key: 0 for key in ("operational", "degraded", "unavailable", "unknown")},
            "short_history_ap_count": 0,
            "status_gap_ap_count": 0,
            "observation_problem_ap_count": 0,
        }
        for item in items:
            summary["current"][item["current"]["status"]] += 1
            summary["history"][item["history"]["status"]] += 1
            summary["observation_quality"][item["observation_quality"]["status"]] += 1
            summary["short_history_ap_count"] += int(item["history"]["short_history_seconds"] > 0)
            summary["status_gap_ap_count"] += int(item["history"]["unknown_evidence_seconds"] > 0)
            summary["observation_problem_ap_count"] += int(item["observation_quality"]["status"] != "operational")
        return summary

    @staticmethod
    def _source_payload(source):
        if source is not None:
            return dict(source)
        return {
            "status": "unavailable", "schema_version": None,
            "first_evidence_at": None, "last_evidence_at": None,
            "complete_cycle_count": 0, "partial_cycle_count": 0,
            "failed_cycle_count": 0, "max_gap_seconds": None,
        }


@contextmanager
def _read_snapshot(connection, deadline, expected_version):
    deadline.require_remaining()
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version != expected_version:
        raise HomeAp24SourceUnavailable("source schema is incompatible")
    connection.execute("PRAGMA query_only=ON")
    connection.execute("BEGIN")
    connection.set_progress_handler(lambda: 1 if deadline.expired() else 0, _PROGRESS_OPCODES)
    try:
        yield
        deadline.require_remaining()
    except sqlite3.OperationalError as exc:
        if deadline.expired() and "interrupted" in str(exc).lower():
            raise AnalyticsQueryDeadlineExceeded("Analytics query deadline exceeded") from exc
        raise
    finally:
        connection.set_progress_handler(None, 0)
        if connection.in_transaction:
            connection.rollback()


def _empty_bucket(start):
    return {
        "from_utc": format_utc(start),
        "to_utc": format_utc(start + timedelta(seconds=BUCKET_SECONDS)),
        "ap_state": "unknown", "ap_state_reason": "before_first_evidence",
        "observation_quality": "unknown", "observation_reason_codes": [],
        "operational_seconds": 0, "unavailable_seconds": 0,
        "unknown_evidence_seconds": 0, "short_history_seconds": 0,
        "authoritative_state_sample_count": 0,
        "complete_observation_sample_count": 0,
        "diagnostic_partial_observation_sample_count": 0,
    }


def _empty_observation_bucket():
    return {
        "observation_quality": "unknown", "observation_reason_codes": [],
        "complete_observation_sample_count": 0,
        "diagnostic_partial_observation_sample_count": 0,
    }


def _apply_interval(buckets, window_start, left, right, state, reason):
    if right <= left:
        return
    first = max(0, int((left - window_start).total_seconds() // BUCKET_SECONDS))
    final = min(
        len(buckets) - 1,
        int(((right - window_start).total_seconds() - 0.000001) // BUCKET_SECONDS),
    )
    for index in range(first, final + 1):
        bucket = buckets[index]
        bucket_start = window_start + timedelta(seconds=index * BUCKET_SECONDS)
        bucket_end = bucket_start + timedelta(seconds=BUCKET_SECONDS)
        overlap = _seconds(max(left, bucket_start), min(right, bucket_end))
        if overlap <= 0:
            continue
        if state == "short":
            bucket["short_history_seconds"] += overlap
        elif state == "operational":
            bucket["operational_seconds"] += overlap
        elif state == "unavailable":
            bucket["unavailable_seconds"] += overlap
        else:
            bucket["unknown_evidence_seconds"] += overlap
            bucket.setdefault("_unknown_reasons", set()).add(reason)
        bucket.setdefault("_reasons", set()).add(reason)


def _reduce_state_bucket(bucket):
    reasons = bucket.pop("_reasons", set())
    unknown_reasons = bucket.pop("_unknown_reasons", set())
    if bucket["unknown_evidence_seconds"]:
        bucket["ap_state"], bucket["ap_state_reason"] = "unknown", next(iter(sorted(unknown_reasons)), "current_state_source_gap")
    elif bucket["operational_seconds"] and bucket["unavailable_seconds"]:
        bucket["ap_state"], bucket["ap_state_reason"] = "degraded", "mixed_state_within_bucket"
    elif bucket["unavailable_seconds"]:
        bucket["ap_state"], bucket["ap_state_reason"] = "unavailable", "controller_reported_offline"
    elif bucket["operational_seconds"]:
        bucket["ap_state"], bucket["ap_state_reason"] = "operational", "operational_evidence"
    else:
        bucket["ap_state"], bucket["ap_state_reason"] = "unknown", "before_first_evidence"


def _empty_history():
    return {
        "status": "unknown", "reason_code": "no_historical_evidence",
        "coverage_status": "insufficient_data", "history_eligible_from": None,
        "first_evidence_at": None, "last_evidence_at": None,
        "authoritative_sample_count": 0, "operational_seconds": 0,
        "unavailable_seconds": 0, "unknown_evidence_seconds": 0,
        "short_history_seconds": WINDOW_SECONDS, "max_gap_seconds": None,
        "current_vs_24h": "history_insufficient",
    }


def _unknown_current(reason):
    return {"status": "unknown", "reason_code": reason, "observed_at": None, "freshness_status": "unavailable"}


def _empty_observation(status, reason):
    return {
        "status": status, "reason_code": reason, "complete_sample_count": 0,
        "diagnostic_partial_sample_count": 0,
        "section_problem_counts": {"overview": 0, "wired_uplink": 0, "lan_traffic": 0, "radios": 0},
    }


def _comparison(current, history, coverage):
    if coverage != "complete":
        return "history_insufficient"
    if current == "operational" and history == "operational":
        return "consistent_with_24h_online_evidence"
    if current == "unknown" and history == "operational":
        return "current_less_certain_than_24h"
    return "historical_state_mixed_or_unknown"


def _continuous_observation_bucket(values, start, end, gap_seconds):
    ordered = sorted(set(values))
    before = [value for value in ordered if value <= start]
    if not before or _seconds(before[-1], start) > gap_seconds:
        return False
    relevant = [before[-1], *[value for value in ordered if start < value < end]]
    if any(_seconds(left, right) > gap_seconds for left, right in zip(relevant, relevant[1:])):
        return False
    return _seconds(relevant[-1], end) <= gap_seconds


def _aggregate_observation_continuous(value, start, end, gap_seconds):
    first = value["first_complete_at"]
    last = value["last_complete_at"]
    if first is None or last is None:
        return False
    first_at = _parse(first)
    last_at = _parse(last)
    max_gap = value["max_complete_gap_seconds"]
    return (
        first_at <= start
        and _seconds(first_at, start) <= gap_seconds
        and last_at < end
        and _seconds(last_at, end) <= gap_seconds
        and (max_gap is None or float(max_gap) <= gap_seconds + 0.001)
    )
