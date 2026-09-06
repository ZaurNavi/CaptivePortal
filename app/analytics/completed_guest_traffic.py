"""Completed guest Visit traffic from persisted lifecycle and client evidence."""

from __future__ import annotations

import base64
import binascii
import json
import re
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

from .models import (
    CompletedGuestSessionTrafficItem,
    CompletedGuestSessionTrafficPage,
    CompletedGuestSessionTrafficRange,
    CompletedGuestSessionTrafficResult,
    CompletedGuestSessionTrafficSourceHealth,
)
from .source_gateway import (
    AnalyticsQueryDeadlineExceeded,
    AnalyticsSourceGateway,
    AnalyticsSourceUnavailable,
    QueryDeadline,
)
from .validation import AnalyticsQueryValidationError, format_utc, parse_utc, require_site


UTC = timezone.utc
METRIC_VERSION = "network_traffic_completed_guest_session_observed_bytes.v1"
SESSION_METHOD = "closed_visit_completion_cohort.v1"
ATTRIBUTION_METHOD = "visit_window_observation_counter_interval_sum.v1"
CONTINUITY_METHOD = "observation_uptime_progress.v1"
UNIT = "bytes"
SORT = "closed_at_desc_visit_id_desc.v1"
DEFAULT_LIMIT = 100
MAX_LIMIT = 100
MAX_ATTRIBUTION_WINDOW_SECONDS = 86_400
MAX_GAP_SECONDS = 180

_CURSOR_VERSION = 1
_CURSOR_KIND = "completed_guest_session_traffic"
_MAX_CURSOR_LENGTH = 4096
_RANGES = {"24h": timedelta(hours=24), "7d": timedelta(days=7)}
_MAC = re.compile(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}")
_REASON_ORDER = (
    "invalid_elapsed",
    "gap_too_large",
    "authorization_boundary",
    "ssid_transition",
    "ssid_unproven",
    "continuity_frozen",
    "connection_reset",
    "continuity_unproven",
    "counter_missing",
    "counter_reset",
    "start_edge_uncovered",
    "end_edge_uncovered",
    "no_usable_interval",
    "observation_source_unavailable",
    "attribution_window_exceeds_supported_max",
)


class CompletedGuestSessionTrafficValidationError(ValueError):
    """Caller input or cursor violates the frozen product contract."""


class CompletedGuestSessionTrafficSourceUnavailable(RuntimeError):
    """A persisted source cannot provide a safe product result."""


class CompletedGuestSessionTrafficIntegrityUnavailable(
    CompletedGuestSessionTrafficSourceUnavailable
):
    """Persisted cross-source evidence is contradictory or malformed."""


class CompletedGuestSessionTrafficReadService:
    """Derive page-bounded completed Visit bytes without polling or writes."""

    def __init__(self, gateway: AnalyticsSourceGateway, *, clock=lambda: datetime.now(UTC)):
        self._gateway = gateway
        self._clock = clock

    def get_completed_guest_session_traffic(
        self,
        site_id: str,
        *,
        range_id: str,
        limit: int = DEFAULT_LIMIT,
        cursor: str | None = None,
        evaluated_at_utc: str | datetime | None = None,
        deadline: QueryDeadline | None = None,
    ) -> CompletedGuestSessionTrafficResult:
        site = _site(site_id)
        selected_range = _range_id(range_id)
        selected_limit = _limit(limit)
        decoded = _decode_cursor(cursor) if cursor is not None else None
        if decoded is None:
            evaluated = _evaluated(evaluated_at_utc, self._clock)
            absolute_to = evaluated
            absolute_from = evaluated - _RANGES[selected_range]
        else:
            evaluated, absolute_from, absolute_to = _cursor_context(
                decoded, site, selected_range
            )
            if evaluated_at_utc is not None and _evaluated(
                evaluated_at_utc, self._clock
            ) != evaluated:
                raise CompletedGuestSessionTrafficValidationError(
                    "cursor evaluated_at changed"
                )
        range_value = CompletedGuestSessionTrafficRange(
            selected_range,
            format_utc(absolute_from),
            format_utc(absolute_to),
            format_utc(evaluated),
        )
        query_deadline = deadline or QueryDeadline.after(10.0)
        after = None if decoded is None else (
            str(decoded["last_closed_at"]), str(decoded["last_visit_id"])
        )
        try:
            rows = self._gateway.completed_visit_page(
                site_id=site,
                from_utc=range_value.from_utc,
                to_utc=range_value.to_utc,
                after=after,
                limit=selected_limit + 1,
                deadline=query_deadline,
            )
        except AnalyticsQueryDeadlineExceeded:
            raise
        except AnalyticsSourceUnavailable:
            return _root(
                site,
                range_value,
                selected_limit,
                "unavailable",
                "unavailable",
                "not_required",
                (),
                None,
            )

        try:
            visits = [_visit(dict(row), site, range_value) for row in rows]
            _unique_visits(visits)
        except CompletedGuestSessionTrafficIntegrityUnavailable:
            raise
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise CompletedGuestSessionTrafficIntegrityUnavailable(
                "completed Visit cohort integrity is unavailable"
            ) from exc
        if len(visits) > selected_limit + 1:
            raise CompletedGuestSessionTrafficIntegrityUnavailable(
                "completed Visit page exceeded its bound"
            )
        has_more = len(visits) > selected_limit
        visible = visits[:selected_limit]
        if not visible:
            return _root(
                site,
                range_value,
                selected_limit,
                "ok",
                "healthy",
                "not_required",
                (),
                None,
            )

        supported = [item for item in visible if item["supported"]]
        boundaries: dict[str, tuple[datetime, ...]] = {}
        if supported:
            windows = tuple(_window(item) for item in supported)
            try:
                boundary_rows = self._gateway.completed_visit_authorization_boundaries_batch(
                    site_id=site,
                    windows=windows,
                    deadline=query_deadline,
                )
            except AnalyticsQueryDeadlineExceeded:
                raise
            except AnalyticsSourceUnavailable:
                return _root(
                    site,
                    range_value,
                    selected_limit,
                    "unavailable",
                    "unavailable",
                    "not_required",
                    (),
                    None,
                )
            boundaries = _boundaries(boundary_rows, supported)
            try:
                evidence_rows = self._gateway.completed_visit_traffic_evidence_batch(
                    site_id=site,
                    windows=windows,
                    deadline=query_deadline,
                )
            except AnalyticsQueryDeadlineExceeded:
                raise
            except AnalyticsSourceUnavailable:
                items = tuple(_observation_unavailable(item) for item in visible)
                return _root(
                    site,
                    range_value,
                    selected_limit,
                    "partial",
                    "healthy",
                    "unavailable",
                    items,
                    _next_cursor(site, range_value, items[-1]) if has_more else None,
                )
            grouped = _evidence(evidence_rows, supported)
        else:
            grouped = {}

        items = tuple(
            _long_visit(item)
            if not item["supported"]
            else _project(item, grouped.get(item["visit_id"], ()), boundaries.get(item["visit_id"], ()))
            for item in visible
        )
        observation_health = "healthy" if supported else "not_required"
        item_statuses = tuple(item.traffic_evidence_status for item in items)
        if all(status == "complete" for status in item_statuses):
            status = "ok"
        elif all(status == "insufficient_data" for status in item_statuses):
            status = "insufficient_data"
        else:
            status = "partial"
        return _root(
            site,
            range_value,
            selected_limit,
            status,
            "healthy",
            observation_health,
            items,
            _next_cursor(site, range_value, items[-1]) if has_more else None,
        )


def _site(value: Any) -> str:
    try:
        return require_site(value)
    except AnalyticsQueryValidationError as exc:
        raise CompletedGuestSessionTrafficValidationError("site_id is invalid") from exc


def _range_id(value: Any) -> str:
    if value not in _RANGES:
        raise CompletedGuestSessionTrafficValidationError("range is invalid")
    return str(value)


def _limit(value: Any) -> int:
    if type(value) is not int or not 1 <= value <= MAX_LIMIT:
        raise CompletedGuestSessionTrafficValidationError("limit is outside bounds")
    return value


def _evaluated(value: Any, clock: Any) -> datetime:
    if value is None:
        value = clock()
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise CompletedGuestSessionTrafficValidationError("evaluated_at is invalid")
        return parse_utc(format_utc(value), "evaluated_at_utc")
    try:
        return parse_utc(value, "evaluated_at_utc")
    except AnalyticsQueryValidationError as exc:
        raise CompletedGuestSessionTrafficValidationError("evaluated_at is invalid") from exc


def _visit(
    row: Mapping[str, Any], site: str, selected_range: CompletedGuestSessionTrafficRange
) -> dict[str, Any]:
    visit_id = _visit_id(row.get("visit_id"))
    client_mac = _mac(row.get("client_mac"), "client_mac")
    started = _timestamp(row.get("started_at"), "started_at")
    closed = _timestamp(row.get("closed_at"), "closed_at")
    duration = row.get("duration_seconds")
    if (
        row.get("site_id") != site
        or row.get("status") != "closed"
        or closed < started
        or not (
            parse_utc(selected_range.from_utc, "from_utc")
            <= closed
            < parse_utc(selected_range.to_utc, "to_utc")
        )
        or type(duration) is not int
        or duration < 0
    ):
        raise CompletedGuestSessionTrafficIntegrityUnavailable(
            "completed Visit row is invalid"
        )
    for name in ("start_ssid", "final_ssid"):
        value = row.get(name)
        if value is not None and (not isinstance(value, str) or not value):
            raise CompletedGuestSessionTrafficIntegrityUnavailable(
                "completed Visit SSID is invalid"
            )
    for name in ("start_ap_mac", "final_ap_mac"):
        _mac(row.get(name), name, optional=True)
    elapsed = (closed - started).total_seconds()
    return {
        **row,
        "visit_id": visit_id,
        "client_mac": client_mac,
        "started": started,
        "closed": closed,
        "supported": elapsed <= MAX_ATTRIBUTION_WINDOW_SECONDS,
    }


def _unique_visits(visits: Sequence[Mapping[str, Any]]) -> None:
    identities = [str(item["visit_id"]) for item in visits]
    if len(identities) != len(set(identities)):
        raise CompletedGuestSessionTrafficIntegrityUnavailable(
            "completed Visit identity is duplicated"
        )
    keys = [(item["closed"], item["visit_id"]) for item in visits]
    if any(left <= right for left, right in zip(keys, keys[1:])):
        raise CompletedGuestSessionTrafficIntegrityUnavailable(
            "completed Visit ordering is invalid"
        )


def _window(item: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "visit_id": item["visit_id"],
        "client_mac": item["client_mac"],
        "started_at": item["started_at"],
        "closed_at": item["closed_at"],
    }


def _boundaries(
    rows: Sequence[Mapping[str, Any]], visits: Sequence[Mapping[str, Any]]
) -> dict[str, tuple[datetime, ...]]:
    expected = {str(item["visit_id"]): item for item in visits}
    grouped: dict[str, list[datetime]] = defaultdict(list)
    identities: set[int] = set()
    for raw in rows:
        row = dict(raw)
        visit_id = str(row.get("visit_id"))
        row_id = row.get("row_id")
        if visit_id not in expected:
            raise CompletedGuestSessionTrafficIntegrityUnavailable(
                "authorization boundary Visit is invalid"
            )
        if type(row_id) is not int or row_id <= 0 or row_id in identities:
            raise CompletedGuestSessionTrafficIntegrityUnavailable(
                "authorization boundary identity is invalid"
            )
        identities.add(row_id)
        authorized = _timestamp(row.get("authorized_at"), "authorized_at")
        visit = expected[visit_id]
        if not visit["started"] < authorized < visit["closed"]:
            raise CompletedGuestSessionTrafficIntegrityUnavailable(
                "authorization boundary timestamp is invalid"
            )
        grouped[visit_id].append(authorized)
    return {key: tuple(sorted(values)) for key, values in grouped.items()}


def _evidence(
    rows: Sequence[Mapping[str, Any]], visits: Sequence[Mapping[str, Any]]
) -> dict[str, tuple[Mapping[str, Any], ...]]:
    expected = {str(item["visit_id"]): item for item in visits}
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    row_owners: dict[int, str] = {}
    for raw in rows:
        row = dict(raw)
        visit_id = str(row.get("visit_id"))
        visit = expected.get(visit_id)
        row_id = row.get("row_id")
        observed = _timestamp(row.get("observed_at"), "observed_at")
        if (
            visit is None
            or type(row_id) is not int
            or row_id <= 0
            or row.get("site_id") != visit.get("site_id")
            or row.get("client_mac") != visit["client_mac"]
            or not visit["started"] <= observed < visit["closed"]
            or row.get("cycle_kind") != "client"
            or row.get("cycle_state") != "completed"
            or row.get("cycle_result") != "success"
            or type(row.get("cycle_complete")) is not int
            or row.get("cycle_complete") != 1
            or type(row.get("source_inventory_complete")) is not int
            or row.get("source_inventory_complete") != 1
        ):
            raise CompletedGuestSessionTrafficIntegrityUnavailable(
                "client Observation evidence is invalid"
            )
        if row_id in row_owners:
            raise CompletedGuestSessionTrafficIntegrityUnavailable(
                "client Observation identity is duplicated"
            )
        row_owners[row_id] = visit_id
        for name in ("uptime", "traffic_down", "traffic_up"):
            value = row.get(name)
            if value is not None and (type(value) is not int or value < 0):
                raise CompletedGuestSessionTrafficIntegrityUnavailable(
                    "client Observation counter is invalid"
                )
        ssid = row.get("ssid")
        if ssid is not None and (not isinstance(ssid, str) or not ssid):
            raise CompletedGuestSessionTrafficIntegrityUnavailable(
                "client Observation SSID is invalid"
            )
        mapped = {**row, "observed": observed}
        grouped[visit_id].append(mapped)
    return {
        key: tuple(sorted(values, key=lambda item: (item["observed"], item["row_id"])))
        for key, values in grouped.items()
    }


def _project(
    visit: Mapping[str, Any],
    samples: Sequence[Mapping[str, Any]],
    boundaries: Sequence[datetime],
) -> CompletedGuestSessionTrafficItem:
    reasons: set[str] = set()
    down_total = 0
    up_total = 0
    down_count = 0
    up_count = 0
    down_rejected = False
    up_rejected = False
    shared_rejected = False
    for previous, current in zip(samples, samples[1:]):
        elapsed = (current["observed"] - previous["observed"]).total_seconds()
        reason = None
        if elapsed <= 0:
            reason = "invalid_elapsed"
        elif elapsed > MAX_GAP_SECONDS:
            reason = "gap_too_large"
        elif any(previous["observed"] < value <= current["observed"] for value in boundaries):
            reason = "authorization_boundary"
        elif previous.get("ssid") is None or current.get("ssid") is None:
            reason = "ssid_unproven"
        elif previous.get("ssid") != current.get("ssid"):
            reason = "ssid_transition"
        elif previous.get("uptime") is None or current.get("uptime") is None:
            reason = "continuity_unproven"
        elif current["uptime"] == previous["uptime"]:
            reason = "continuity_frozen"
        elif current["uptime"] < previous["uptime"]:
            reason = "connection_reset"
        if reason is not None:
            reasons.add(reason)
            shared_rejected = True
            continue
        down, down_reason = _delta(previous.get("traffic_down"), current.get("traffic_down"))
        up, up_reason = _delta(previous.get("traffic_up"), current.get("traffic_up"))
        if down is None:
            reasons.add(down_reason)
            down_rejected = True
        else:
            down_total += down
            down_count += 1
        if up is None:
            reasons.add(up_reason)
            up_rejected = True
        else:
            up_total += up
            up_count += 1

    first = samples[0]["observed"] if samples else None
    last = samples[-1]["observed"] if samples else None
    edge_rejected = False
    if first is not None and (first - visit["started"]).total_seconds() > MAX_GAP_SECONDS:
        reasons.add("start_edge_uncovered")
        edge_rejected = True
    if last is not None and (visit["closed"] - last).total_seconds() > MAX_GAP_SECONDS:
        reasons.add("end_edge_uncovered")
        edge_rejected = True
    if down_count == 0 and up_count == 0:
        reasons.add("no_usable_interval")
    download_status = _direction_status(
        down_count, shared_rejected or edge_rejected or down_rejected
    )
    upload_status = _direction_status(
        up_count, shared_rejected or edge_rejected or up_rejected
    )
    if download_status == upload_status == "complete":
        traffic_status = "complete"
    elif down_count == 0 and up_count == 0:
        traffic_status = "insufficient_data"
    else:
        traffic_status = "partial"
    download = down_total if down_count else None
    upload = up_total if up_count else None
    total = download + upload if download is not None and upload is not None else None
    return _item(
        visit,
        download,
        upload,
        total,
        download_status,
        upload_status,
        traffic_status,
        reasons,
        len(samples),
        down_count,
        up_count,
        format_utc(first) if first is not None else None,
        format_utc(last) if last is not None else None,
    )


def _delta(previous: Any, current: Any) -> tuple[int | None, str]:
    if previous is None or current is None:
        return None, "counter_missing"
    if current < previous:
        return None, "counter_reset"
    return current - previous, ""


def _direction_status(accepted: int, rejected: bool) -> str:
    if accepted == 0:
        return "insufficient_data"
    return "partial" if rejected else "complete"


def _long_visit(visit: Mapping[str, Any]) -> CompletedGuestSessionTrafficItem:
    return _item(
        visit, None, None, None, "unavailable", "unavailable", "unavailable",
        {"attribution_window_exceeds_supported_max"}, 0, 0, 0, None, None,
    )


def _observation_unavailable(
    visit: Mapping[str, Any]
) -> CompletedGuestSessionTrafficItem:
    if not visit["supported"]:
        return _long_visit(visit)
    return _item(
        visit, None, None, None, "unavailable", "unavailable", "unavailable",
        {"observation_source_unavailable"}, 0, 0, 0, None, None,
    )


def _item(
    visit: Mapping[str, Any],
    download: int | None,
    upload: int | None,
    total: int | None,
    download_status: str,
    upload_status: str,
    traffic_status: str,
    reasons: set[str],
    sample_count: int,
    down_count: int,
    up_count: int,
    first: str | None,
    last: str | None,
) -> CompletedGuestSessionTrafficItem:
    return CompletedGuestSessionTrafficItem(
        visit_id=str(visit["visit_id"]),
        client_mac=str(visit["client_mac"]),
        started_at=format_utc(visit["started"]),
        closed_at=format_utc(visit["closed"]),
        duration_seconds=int(visit["duration_seconds"]),
        start_ssid=visit.get("start_ssid"),
        final_ssid=visit.get("final_ssid"),
        start_ap_mac=visit.get("start_ap_mac"),
        final_ap_mac=visit.get("final_ap_mac"),
        observed_download_bytes=download,
        observed_upload_bytes=upload,
        observed_total_bytes=total,
        download_evidence_status=download_status,
        upload_evidence_status=upload_status,
        traffic_evidence_status=traffic_status,
        evidence_reason_codes=tuple(reason for reason in _REASON_ORDER if reason in reasons),
        sample_count=sample_count,
        accepted_download_interval_count=down_count,
        accepted_upload_interval_count=up_count,
        first_observed_at=first,
        last_observed_at=last,
    )


def _root(
    site: str,
    selected_range: CompletedGuestSessionTrafficRange,
    limit: int,
    status: str,
    visits: str,
    observations: str,
    items: tuple[CompletedGuestSessionTrafficItem, ...],
    next_cursor: str | None,
) -> CompletedGuestSessionTrafficResult:
    return CompletedGuestSessionTrafficResult(
        metric_version=METRIC_VERSION,
        session_method=SESSION_METHOD,
        attribution_method=ATTRIBUTION_METHOD,
        continuity_method=CONTINUITY_METHOD,
        unit=UNIT,
        site_id=site,
        range=selected_range,
        status=status,
        source_health=CompletedGuestSessionTrafficSourceHealth(visits, observations),
        page=CompletedGuestSessionTrafficPage(
            limit, len(items), next_cursor, SORT
        ),
        items=items,
    )


def _next_cursor(
    site: str,
    selected_range: CompletedGuestSessionTrafficRange,
    last: CompletedGuestSessionTrafficItem,
) -> str:
    payload = {
        "version": _CURSOR_VERSION,
        "kind": _CURSOR_KIND,
        "site_id": site,
        "range_id": selected_range.id,
        "evaluated_at_utc": selected_range.evaluated_at_utc,
        "absolute_from_utc": selected_range.from_utc,
        "absolute_to_utc": selected_range.to_utc,
        "sort": SORT,
        "last_closed_at": last.closed_at,
        "last_visit_id": last.visit_id,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _decode_cursor(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, str) or not value or len(value) > _MAX_CURSOR_LENGTH:
        raise CompletedGuestSessionTrafficValidationError("cursor is malformed")
    try:
        raw = base64.b64decode(
            value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
        )
        payload = json.loads(raw.decode("ascii"))
    except (binascii.Error, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise CompletedGuestSessionTrafficValidationError("cursor is malformed") from exc
    required = {
        "version", "kind", "site_id", "range_id", "evaluated_at_utc",
        "absolute_from_utc", "absolute_to_utc", "sort", "last_closed_at",
        "last_visit_id",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise CompletedGuestSessionTrafficValidationError("cursor is malformed")
    return payload


def _cursor_context(
    cursor: Mapping[str, Any], site: str, range_id: str
) -> tuple[datetime, datetime, datetime]:
    if (
        cursor.get("version") != _CURSOR_VERSION
        or cursor.get("kind") != _CURSOR_KIND
        or cursor.get("site_id") != site
        or cursor.get("range_id") != range_id
        or cursor.get("sort") != SORT
    ):
        raise CompletedGuestSessionTrafficValidationError("cursor context changed")
    try:
        evaluated = parse_utc(cursor.get("evaluated_at_utc"), "evaluated_at_utc")
        absolute_from = parse_utc(cursor.get("absolute_from_utc"), "absolute_from_utc")
        absolute_to = parse_utc(cursor.get("absolute_to_utc"), "absolute_to_utc")
        last_closed = parse_utc(cursor.get("last_closed_at"), "last_closed_at")
        _visit_id(cursor.get("last_visit_id"))
    except (AnalyticsQueryValidationError, CompletedGuestSessionTrafficIntegrityUnavailable) as exc:
        raise CompletedGuestSessionTrafficValidationError("cursor is malformed") from exc
    expected_from = evaluated - _RANGES[range_id]
    if (
        absolute_to != evaluated
        or absolute_from != expected_from
        or not absolute_from <= last_closed < absolute_to
    ):
        raise CompletedGuestSessionTrafficValidationError("cursor range changed")
    return evaluated, absolute_from, absolute_to


def _visit_id(value: Any) -> str:
    if not isinstance(value, str):
        raise CompletedGuestSessionTrafficIntegrityUnavailable("visit_id is invalid")
    try:
        canonical = str(uuid.UUID(value))
    except ValueError as exc:
        raise CompletedGuestSessionTrafficIntegrityUnavailable("visit_id is invalid") from exc
    if canonical != value:
        raise CompletedGuestSessionTrafficIntegrityUnavailable("visit_id is invalid")
    return value


def _mac(value: Any, name: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or _MAC.fullmatch(value) is None:
        raise CompletedGuestSessionTrafficIntegrityUnavailable(f"{name} is invalid")
    return value


def _timestamp(value: Any, name: str) -> datetime:
    try:
        return parse_utc(value, name)
    except AnalyticsQueryValidationError as exc:
        raise CompletedGuestSessionTrafficIntegrityUnavailable(
            f"{name} is invalid"
        ) from exc
