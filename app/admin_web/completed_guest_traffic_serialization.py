"""Strict Admin serialization for Completed Guest Session Traffic."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta
from typing import Any

from app.analytics.completed_guest_traffic import (
    ATTRIBUTION_METHOD,
    CONTINUITY_METHOD,
    MAX_LIMIT,
    METRIC_VERSION,
    SESSION_METHOD,
    SORT,
    UNIT,
)
from app.analytics.models import CompletedGuestSessionTrafficResult


class CompletedGuestSessionTrafficSerializationError(ValueError):
    """The completed-session result is unsafe for the Admin API."""


_ROOT_STATUSES = frozenset({"ok", "partial", "insufficient_data", "unavailable"})
_SOURCE_VISITS = frozenset({"healthy", "unavailable"})
_SOURCE_OBSERVATIONS = frozenset({"healthy", "unavailable", "not_required"})
_EVIDENCE = frozenset({"complete", "partial", "insufficient_data", "unavailable"})
_REASONS = frozenset({
    "invalid_elapsed", "gap_too_large", "authorization_boundary",
    "ssid_transition", "ssid_unproven", "continuity_frozen",
    "connection_reset", "continuity_unproven", "counter_missing",
    "counter_reset", "start_edge_uncovered", "end_edge_uncovered",
    "no_usable_interval", "observation_source_unavailable",
    "attribution_window_exceeds_supported_max",
})
_MAC = re.compile(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}")
_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z")


def serialize_completed_guest_session_traffic(
    value: CompletedGuestSessionTrafficResult,
    site_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(value, CompletedGuestSessionTrafficResult):
        raise CompletedGuestSessionTrafficSerializationError("result type is invalid")
    expected = {
        "metric_version": METRIC_VERSION,
        "session_method": SESSION_METHOD,
        "attribution_method": ATTRIBUTION_METHOD,
        "continuity_method": CONTINUITY_METHOD,
        "unit": UNIT,
    }
    if any(getattr(value, key) != item for key, item in expected.items()):
        raise CompletedGuestSessionTrafficSerializationError("method contract is invalid")
    if value.site_id != site_id:
        raise CompletedGuestSessionTrafficSerializationError("Site identity is invalid")
    if value.status not in _ROOT_STATUSES:
        raise CompletedGuestSessionTrafficSerializationError("root status is invalid")

    selected_range = value.range
    if selected_range.id not in {"24h", "7d"}:
        raise CompletedGuestSessionTrafficSerializationError("range is invalid")
    start = _timestamp(selected_range.from_utc)
    end = _timestamp(selected_range.to_utc)
    evaluated = _timestamp(selected_range.evaluated_at_utc)
    expected_seconds = 86_400 if selected_range.id == "24h" else 604_800
    if end != evaluated or end - start != timedelta(seconds=expected_seconds):
        raise CompletedGuestSessionTrafficSerializationError("range boundary is invalid")

    health = value.source_health
    if health.visits not in _SOURCE_VISITS or health.observations not in _SOURCE_OBSERVATIONS:
        raise CompletedGuestSessionTrafficSerializationError("source health is invalid")
    page = value.page
    if (
        type(page.limit) is not int
        or not 1 <= page.limit <= MAX_LIMIT
        or type(page.returned_count) is not int
        or page.returned_count != len(value.items)
        or not 0 <= page.returned_count <= page.limit
        or page.sort != SORT
        or (
            page.next_cursor is not None
            and (
                not isinstance(page.next_cursor, str)
                or not page.next_cursor
                or len(page.next_cursor) > 4096
                or not value.items
            )
        )
    ):
        raise CompletedGuestSessionTrafficSerializationError("page is invalid")

    items = [_item(item, site_id, start, end) for item in value.items]
    identities = [item["visit_id"] for item in items]
    if len(identities) != len(set(identities)):
        raise CompletedGuestSessionTrafficSerializationError("Visit identity is duplicated")
    keys = [(item["closed_at"], item["visit_id"]) for item in items]
    if any(left <= right for left, right in zip(keys, keys[1:])):
        raise CompletedGuestSessionTrafficSerializationError("Visit ordering is invalid")
    _root_shape(value, items)

    result = {
        **expected,
        "site_id": site_id,
        "range": {
            "id": selected_range.id,
            "from_utc": selected_range.from_utc,
            "to_utc": selected_range.to_utc,
            "evaluated_at_utc": selected_range.evaluated_at_utc,
        },
        "status": value.status,
        "source_health": {
            "visits": health.visits,
            "observations": health.observations,
        },
        "page": {
            "limit": page.limit,
            "returned_count": page.returned_count,
            "next_cursor": page.next_cursor,
            "sort": page.sort,
        },
        "items": items,
    }
    return result, result["page"]


def _root_shape(value: CompletedGuestSessionTrafficResult, items: list[dict[str, Any]]) -> None:
    health = value.source_health
    if health.visits == "unavailable":
        valid = (
            value.status == "unavailable"
            and health.observations == "not_required"
            and not items
            and value.page.next_cursor is None
        )
    elif not items:
        valid = (
            value.status == "ok"
            and health.observations == "not_required"
            and value.page.next_cursor is None
        )
    elif health.observations == "unavailable":
        valid = value.status == "partial" and all(
            item["traffic_evidence_status"] == "unavailable"
            and item["evidence_reason_codes"] in (
                ["observation_source_unavailable"],
                ["attribution_window_exceeds_supported_max"],
            )
            for item in items
        )
    elif health.observations in {"healthy", "not_required"}:
        expected = (
            "ok" if all(item["traffic_evidence_status"] == "complete" for item in items)
            else "insufficient_data" if all(
                item["traffic_evidence_status"] == "insufficient_data"
                for item in items
            )
            else "partial"
        )
        valid = value.status == expected
        if health.observations == "not_required":
            valid = valid and all(
                item["evidence_reason_codes"]
                == ["attribution_window_exceeds_supported_max"]
                for item in items
            )
    else:
        valid = False
    if not valid:
        raise CompletedGuestSessionTrafficSerializationError("root shape is invalid")


def _item(value: Any, site_id: str, start: datetime, end: datetime) -> dict[str, Any]:
    visit_id = _visit_id(value.visit_id)
    client_mac = _mac(value.client_mac)
    started = _timestamp(value.started_at)
    closed = _timestamp(value.closed_at)
    if not start <= closed < end or closed < started:
        raise CompletedGuestSessionTrafficSerializationError("Visit timestamps are invalid")
    if type(value.duration_seconds) is not int or value.duration_seconds < 0:
        raise CompletedGuestSessionTrafficSerializationError("Visit duration is invalid")
    start_ssid = _text(value.start_ssid, optional=True)
    final_ssid = _text(value.final_ssid, optional=True)
    start_ap = _mac(value.start_ap_mac, optional=True)
    final_ap = _mac(value.final_ap_mac, optional=True)
    values = (
        _bytes(value.observed_download_bytes, optional=True),
        _bytes(value.observed_upload_bytes, optional=True),
        _bytes(value.observed_total_bytes, optional=True),
    )
    statuses = (
        value.download_evidence_status,
        value.upload_evidence_status,
        value.traffic_evidence_status,
    )
    if any(item not in _EVIDENCE for item in statuses):
        raise CompletedGuestSessionTrafficSerializationError("evidence status is invalid")
    reasons = value.evidence_reason_codes
    if (
        not isinstance(reasons, tuple)
        or len(reasons) != len(set(reasons))
        or any(reason not in _REASONS for reason in reasons)
    ):
        raise CompletedGuestSessionTrafficSerializationError("evidence reason is invalid")
    counts = (
        _count(value.sample_count),
        _count(value.accepted_download_interval_count),
        _count(value.accepted_upload_interval_count),
    )
    first = _optional_timestamp(value.first_observed_at)
    last = _optional_timestamp(value.last_observed_at)
    if (
        (first is None) != (last is None)
        or (counts[0] == 0) != (first is None)
        or counts[1] > max(counts[0] - 1, 0)
        or counts[2] > max(counts[0] - 1, 0)
        or (first is not None and not started <= first <= last < closed)
    ):
        raise CompletedGuestSessionTrafficSerializationError("sample evidence is invalid")
    _evidence_shape(values, statuses, reasons, counts)
    return {
        "visit_id": visit_id,
        "client_mac": client_mac,
        "started_at": value.started_at,
        "closed_at": value.closed_at,
        "duration_seconds": value.duration_seconds,
        "start_ssid": start_ssid,
        "final_ssid": final_ssid,
        "start_ap_mac": start_ap,
        "final_ap_mac": final_ap,
        "observed_download_bytes": values[0],
        "observed_upload_bytes": values[1],
        "observed_total_bytes": values[2],
        "download_evidence_status": statuses[0],
        "upload_evidence_status": statuses[1],
        "traffic_evidence_status": statuses[2],
        "evidence_reason_codes": list(reasons),
        "sample_count": counts[0],
        "accepted_download_interval_count": counts[1],
        "accepted_upload_interval_count": counts[2],
        "first_observed_at": value.first_observed_at,
        "last_observed_at": value.last_observed_at,
    }


def _evidence_shape(values, statuses, reasons, counts) -> None:
    download, upload, total = values
    down_status, up_status, traffic_status = statuses
    if (download is None) != (counts[1] == 0) or (upload is None) != (counts[2] == 0):
        raise CompletedGuestSessionTrafficSerializationError("direction evidence is invalid")
    if total is not None and (download is None or upload is None or total != download + upload):
        raise CompletedGuestSessionTrafficSerializationError("total evidence is invalid")
    if total is None and download is not None and upload is not None:
        raise CompletedGuestSessionTrafficSerializationError("total evidence is missing")
    unavailable = set(reasons) & {
        "observation_source_unavailable", "attribution_window_exceeds_supported_max"
    }
    if traffic_status == "unavailable":
        valid = (
            all(item is None for item in values)
            and down_status == up_status == "unavailable"
            and len(unavailable) == len(reasons) == 1
            and counts == (0, 0, 0)
        )
    elif traffic_status == "complete":
        valid = (
            down_status == up_status == "complete"
            and all(item is not None for item in values)
            and not reasons
        )
    elif traffic_status == "insufficient_data":
        valid = (
            counts[1] == counts[2] == 0
            and all(item is None for item in values)
            and down_status == up_status == "insufficient_data"
            and "no_usable_interval" in reasons
            and not unavailable
        )
    else:
        valid = (
            (download is not None or upload is not None)
            and down_status != "unavailable"
            and up_status != "unavailable"
            and (down_status == "partial" or up_status == "partial"
                 or download is None or upload is None)
            and bool(reasons)
            and not unavailable
        )
    for status, item in ((down_status, download), (up_status, upload)):
        valid = valid and (
            (status in {"complete", "partial"} and item is not None)
            or (status in {"insufficient_data", "unavailable"} and item is None)
        )
    if not valid:
        raise CompletedGuestSessionTrafficSerializationError("evidence shape is invalid")


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or _UTC.fullmatch(value) is None:
        raise CompletedGuestSessionTrafficSerializationError("timestamp is invalid")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError as exc:
        raise CompletedGuestSessionTrafficSerializationError("timestamp is invalid") from exc


def _optional_timestamp(value: Any) -> datetime | None:
    return None if value is None else _timestamp(value)


def _visit_id(value: Any) -> str:
    if not isinstance(value, str):
        raise CompletedGuestSessionTrafficSerializationError("Visit identity is invalid")
    try:
        if str(uuid.UUID(value)) != value:
            raise ValueError
    except ValueError as exc:
        raise CompletedGuestSessionTrafficSerializationError("Visit identity is invalid") from exc
    return value


def _mac(value: Any, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or _MAC.fullmatch(value) is None:
        raise CompletedGuestSessionTrafficSerializationError("MAC is invalid")
    return value


def _text(value: Any, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value or value.strip() != value:
        raise CompletedGuestSessionTrafficSerializationError("text is invalid")
    return value


def _bytes(value: Any, *, optional: bool = False) -> int | None:
    if value is None and optional:
        return None
    if type(value) is not int or value < 0:
        raise CompletedGuestSessionTrafficSerializationError("bytes are invalid")
    return value


def _count(value: Any) -> int:
    if type(value) is not int or value < 0:
        raise CompletedGuestSessionTrafficSerializationError("count is invalid")
    return value
