"""Strict Admin serialization for Online Guests Traffic."""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any

from app.analytics.current_guest_traffic import (
    BASELINE_METHOD,
    BOUNDARY_OBSERVATION,
    CONTINUITY_METHOD,
    MAX_LIMIT,
    METRIC_VERSION,
    POPULATION_METHOD,
    RATE_METHOD,
    SORT,
    SUPPORTED_MAX_POPULATION,
    UNIT,
)
from app.analytics.models import CurrentGuestTrafficResult


class CurrentGuestTrafficSerializationError(ValueError):
    """The semantic result cannot be exposed through the Admin API."""


_ROOT_STATUSES = frozenset({
    "ok", "partial", "insufficient_data", "stale", "unavailable",
    "unsupported_population",
})
_SOURCE_STATUSES = frozenset({"healthy", "degraded", "stale", "unavailable"})
_SOURCE_REASONS = frozenset({
    "within_freshness_window", "newer_degraded_attempt",
    "older_than_freshness_window", "older_than_unavailable_threshold",
    "clock_anomaly", "no_complete_snapshot",
})
_RATE_EVIDENCE = frozenset({"complete", "partial", "insufficient_data", "not_applicable"})
_RATE_STATUSES = frozenset({"valid", "partial", "unavailable"})
_PROGRESS = frozenset({"advanced", "frozen", "unproven"})
_CONTINUITY = frozenset({"proven", "unproven", "reset"})
_BASES = frozenset({"uptime_progress", "counters_only_diagnostic", "none"})
_ITEM_REASONS = frozenset({
    "valid", "no_baseline", "no_authorized_baseline", "ssid_transition",
    "invalid_elapsed", "baseline_gap_too_large",
    "connection_continuity_unproven", "source_frozen", "connection_reset",
    "counter_missing", "counter_reset",
})
_MAC = re.compile(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}")
_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z")
_HEX64 = re.compile(r"[0-9a-f]{64}")


def serialize_current_guest_traffic(
    value: CurrentGuestTrafficResult,
    site_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(value, CurrentGuestTrafficResult):
        raise CurrentGuestTrafficSerializationError("result type is invalid")
    expected = {
        "metric_version": METRIC_VERSION,
        "population_method": POPULATION_METHOD,
        "rate_method": RATE_METHOD,
        "baseline_method": BASELINE_METHOD,
        "continuity_method": CONTINUITY_METHOD,
        "connection_boundary_observation": BOUNDARY_OBSERVATION,
        "unit": UNIT,
    }
    for field, required in expected.items():
        if getattr(value, field) != required:
            raise CurrentGuestTrafficSerializationError(f"{field} is invalid")
    if value.site_id != site_id:
        raise CurrentGuestTrafficSerializationError("Site identity is invalid")
    evaluated = _timestamp(value.evaluated_at_utc)
    current_at = _timestamp(value.current_capture_started_at, optional=True)
    baseline_at = _timestamp(value.baseline_capture_started_at, optional=True)
    current_cycle = _identity(value.current_cycle_id, optional=True)
    baseline_cycle = _identity(value.baseline_cycle_id, optional=True)
    scope_hash = value.source_scope_hash
    if scope_hash is not None and (
        not isinstance(scope_hash, str) or _HEX64.fullmatch(scope_hash) is None
    ):
        raise CurrentGuestTrafficSerializationError("source scope is invalid")
    elapsed = _number(value.elapsed_seconds, optional=True, positive=True)
    if (current_cycle is None) != (current_at is None):
        raise CurrentGuestTrafficSerializationError("current evidence is incomplete")
    if (baseline_cycle is None) != (baseline_at is None):
        raise CurrentGuestTrafficSerializationError("baseline evidence is incomplete")
    if baseline_cycle is None:
        if elapsed is not None:
            raise CurrentGuestTrafficSerializationError("elapsed evidence is invalid")
    elif current_cycle is None or elapsed is None:
        raise CurrentGuestTrafficSerializationError("baseline evidence is invalid")
    if value.status not in _ROOT_STATUSES:
        raise CurrentGuestTrafficSerializationError("root status is invalid")
    if value.source_health_status not in _SOURCE_STATUSES:
        raise CurrentGuestTrafficSerializationError("source health is invalid")
    if value.source_health_reason not in _SOURCE_REASONS:
        raise CurrentGuestTrafficSerializationError("source health reason is invalid")
    _source_health_pair(value.source_health_status, value.source_health_reason)
    if value.rate_evidence_status not in _RATE_EVIDENCE:
        raise CurrentGuestTrafficSerializationError("rate evidence is invalid")
    if type(value.population_complete) is not bool:
        raise CurrentGuestTrafficSerializationError("population completeness is invalid")
    if value.supported_max_population != SUPPORTED_MAX_POPULATION:
        raise CurrentGuestTrafficSerializationError("population bound is invalid")

    counts = {
        name: _count(getattr(value, name), optional=True)
        for name in (
            "scoped_client_row_count", "known_authorized_count",
            "unknown_auth_count", "population_count", "rate_valid_count",
            "rate_partial_count", "rate_unavailable_count",
        )
    }
    page = value.page
    if (
        type(page.limit) is not int or not 1 <= page.limit <= MAX_LIMIT
        or type(page.returned_count) is not int or page.returned_count < 0
        or page.sort != SORT
        or page.returned_count != len(value.items)
        or page.returned_count > page.limit
        or (page.returned_count == 0 and page.next_cursor is not None)
        or (
            page.next_cursor is not None
            and (
                not isinstance(page.next_cursor, str)
                or not page.next_cursor
                or len(page.next_cursor) > 2048
            )
        )
    ):
        raise CurrentGuestTrafficSerializationError("page is invalid")

    _root_shape(value, current_cycle, baseline_cycle, scope_hash, counts)
    items = [_item(item) for item in value.items]
    macs = [item["client_mac"] for item in items]
    if len(macs) != len(set(macs)):
        raise CurrentGuestTrafficSerializationError("item identity is duplicated")
    if counts["population_count"] is not None and len(items) > counts["population_count"]:
        raise CurrentGuestTrafficSerializationError("page exceeds population")

    result = {**expected,
        "site_id": site_id,
        "evaluated_at_utc": evaluated,
        "current_cycle_id": current_cycle,
        "baseline_cycle_id": baseline_cycle,
        "current_capture_started_at": current_at,
        "baseline_capture_started_at": baseline_at,
        "elapsed_seconds": elapsed,
        "status": value.status,
        "source_health_status": value.source_health_status,
        "source_health_reason": value.source_health_reason,
        "rate_evidence_status": value.rate_evidence_status,
        "population_complete": value.population_complete,
        **counts,
        "supported_max_population": value.supported_max_population,
        "items": items,
    }
    return result, {
        "limit": page.limit,
        "returned_count": page.returned_count,
        "next_cursor": page.next_cursor,
        "sort": page.sort,
    }


def _root_shape(value, current, baseline, scope_hash, counts) -> None:
    asserted = value.status in {"ok", "partial", "insufficient_data", "unsupported_population"}
    rate_counts = tuple(counts[name] for name in (
        "rate_valid_count", "rate_partial_count", "rate_unavailable_count"
    ))
    population_counts = tuple(counts[name] for name in (
        "scoped_client_row_count", "known_authorized_count",
        "unknown_auth_count", "population_count",
    ))
    terminal = value.status in {"stale", "unavailable"}
    if asserted:
        if current is None or scope_hash is None or any(item is None for item in population_counts):
            raise CurrentGuestTrafficSerializationError("asserted population is incomplete")
        scoped, authorized, unknown, population = population_counts
        if population != authorized or authorized + unknown > scoped:
            raise CurrentGuestTrafficSerializationError("population counts are inconsistent")
        if value.status == "unsupported_population":
            if (
                scoped <= SUPPORTED_MAX_POPULATION or baseline is not None
                or any(item is not None for item in rate_counts)
                or value.rate_evidence_status != "insufficient_data"
                or value.population_complete is not False
                or value.source_health_status not in {"healthy", "degraded"}
            ):
                raise CurrentGuestTrafficSerializationError("unsupported population is invalid")
        else:
            if any(item is None for item in rate_counts):
                raise CurrentGuestTrafficSerializationError("rate counts are incomplete")
            if sum(rate_counts) != population:
                raise CurrentGuestTrafficSerializationError("rate counts are inconsistent")
            if value.population_complete != (unknown == 0):
                raise CurrentGuestTrafficSerializationError("population completeness is inconsistent")
            if population == 0:
                if baseline is not None or value.rate_evidence_status != "not_applicable" or any(rate_counts):
                    raise CurrentGuestTrafficSerializationError("zero population is invalid")
            else:
                if value.rate_evidence_status == "not_applicable":
                    raise CurrentGuestTrafficSerializationError("nonzero rate evidence is invalid")
                valid, partial, unavailable = rate_counts
                expected_evidence = (
                    "complete" if valid == population
                    else "partial" if valid or partial
                    else "insufficient_data"
                )
                if value.rate_evidence_status != expected_evidence:
                    raise CurrentGuestTrafficSerializationError("rate evidence counts are inconsistent")
            if value.status == "ok" and (
                value.source_health_status != "healthy" or not value.population_complete
                or value.rate_evidence_status not in {"complete", "not_applicable"}
                or (population > 0 and baseline is None)
            ):
                raise CurrentGuestTrafficSerializationError("ok status is invalid")
            if value.status == "insufficient_data" and (
                population <= 0 or value.source_health_status != "healthy"
                or not value.population_complete
                or value.rate_evidence_status != "insufficient_data"
            ):
                raise CurrentGuestTrafficSerializationError("insufficient status is invalid")
            if value.status == "partial" and not (
                value.source_health_status == "degraded"
                or not value.population_complete
                or value.rate_evidence_status == "partial"
            ):
                raise CurrentGuestTrafficSerializationError("partial status is invalid")
            if value.status == "partial" and value.source_health_status not in {"healthy", "degraded"}:
                raise CurrentGuestTrafficSerializationError("partial source health is invalid")
    elif terminal:
        if any(item is not None for item in population_counts + rate_counts):
            raise CurrentGuestTrafficSerializationError("unasserted counts must be null")
        if (
            baseline is not None or value.population_complete
            or (current is None) != (scope_hash is None)
        ):
            raise CurrentGuestTrafficSerializationError("unasserted evidence is invalid")
        if value.status == "stale" and (
            current is None or value.source_health_status != "stale"
            or value.rate_evidence_status != "insufficient_data"
        ):
            raise CurrentGuestTrafficSerializationError("stale status is invalid")
        if value.status == "unavailable" and (
            value.source_health_status != "unavailable"
            or value.rate_evidence_status != "insufficient_data"
        ):
            raise CurrentGuestTrafficSerializationError("unavailable status is invalid")
    if value.status in {"stale", "unavailable", "unsupported_population"} and (
        value.items or value.page.returned_count != 0 or value.page.next_cursor is not None
    ):
        raise CurrentGuestTrafficSerializationError("terminal page is invalid")


def _item(value: Any) -> dict[str, Any]:
    if not isinstance(value.client_mac, str) or _MAC.fullmatch(value.client_mac) is None:
        raise CurrentGuestTrafficSerializationError("client MAC is invalid")
    if value.name is not None and not isinstance(value.name, str):
        raise CurrentGuestTrafficSerializationError("client name is invalid")
    if not isinstance(value.ssid, str) or not value.ssid:
        raise CurrentGuestTrafficSerializationError("SSID is invalid")
    if value.ap_mac is not None and (
        not isinstance(value.ap_mac, str) or _MAC.fullmatch(value.ap_mac) is None
    ):
        raise CurrentGuestTrafficSerializationError("AP MAC is invalid")
    if value.source_progress_status not in _PROGRESS:
        raise CurrentGuestTrafficSerializationError("progress status is invalid")
    if value.connection_continuity_status not in _CONTINUITY:
        raise CurrentGuestTrafficSerializationError("continuity status is invalid")
    if value.continuity_basis not in _BASES:
        raise CurrentGuestTrafficSerializationError("continuity basis is invalid")
    reasons = (value.download_reason, value.upload_reason, value.total_reason)
    if any(reason not in _ITEM_REASONS for reason in reasons):
        raise CurrentGuestTrafficSerializationError("rate reason is invalid")
    if value.rate_status not in _RATE_STATUSES:
        raise CurrentGuestTrafficSerializationError("rate status is invalid")
    rates = (
        _number(value.download_mbps, optional=True),
        _number(value.upload_mbps, optional=True),
        _number(value.total_mbps, optional=True),
    )
    numeric = sum(item is not None for item in rates)
    if any(
        (rate is not None) != (reason == "valid")
        for rate, reason in zip(rates, reasons)
    ):
        raise CurrentGuestTrafficSerializationError("rate evidence is invalid")
    has_download = rates[0] is not None
    has_upload = rates[1] is not None
    has_total = rates[2] is not None
    if (
        (value.rate_status == "valid" and numeric != 3)
        or (
            value.rate_status == "partial"
            and (has_download == has_upload or has_total)
        )
        or (value.rate_status == "unavailable" and numeric != 0)
        or (has_total and not (has_download and has_upload))
    ):
        raise CurrentGuestTrafficSerializationError("rate shape is invalid")
    if numeric and (
        value.source_progress_status != "advanced"
        or value.connection_continuity_status != "proven"
        or value.continuity_basis != "uptime_progress"
    ):
        raise CurrentGuestTrafficSerializationError("rate continuity is invalid")
    return {
        "client_mac": value.client_mac,
        "name": value.name,
        "ssid": value.ssid,
        "ap_mac": value.ap_mac,
        "download_mbps": rates[0],
        "upload_mbps": rates[1],
        "total_mbps": rates[2],
        "source_progress_status": value.source_progress_status,
        "connection_continuity_status": value.connection_continuity_status,
        "continuity_basis": value.continuity_basis,
        "download_reason": value.download_reason,
        "upload_reason": value.upload_reason,
        "total_reason": value.total_reason,
        "rate_status": value.rate_status,
    }


def _source_health_pair(status: str, reason: str) -> None:
    pairs = {
        "healthy": {"within_freshness_window"},
        "degraded": {"newer_degraded_attempt"},
        "stale": {"older_than_freshness_window"},
        "unavailable": {
            "older_than_unavailable_threshold", "clock_anomaly",
            "no_complete_snapshot",
        },
    }
    if reason not in pairs[status]:
        raise CurrentGuestTrafficSerializationError("source health pair is invalid")


def _timestamp(value: Any, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or _UTC.fullmatch(value) is None:
        raise CurrentGuestTrafficSerializationError("timestamp is invalid")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError as exc:
        raise CurrentGuestTrafficSerializationError("timestamp is invalid") from exc
    return value


def _identity(value: Any, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value or len(value) > 128:
        raise CurrentGuestTrafficSerializationError("cycle identity is invalid")
    return value


def _count(value: Any, *, optional: bool = False) -> int | None:
    if value is None and optional:
        return None
    if type(value) is not int or value < 0:
        raise CurrentGuestTrafficSerializationError("count is invalid")
    return value


def _number(value: Any, *, optional: bool = False, positive: bool = False) -> float | None:
    if value is None and optional:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CurrentGuestTrafficSerializationError("number is invalid")
    number = float(value)
    if not math.isfinite(number) or number < 0 or (positive and number <= 0):
        raise CurrentGuestTrafficSerializationError("number is invalid")
    return number
