"""Read-only Online Guest current-rate semantics over Current State v1."""

from __future__ import annotations

import base64
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from app.current_state.models import (
    CurrentStateSchemaError,
    CurrentStateStorageError,
    CurrentStateValidationError,
    parse_utc,
    require_site_id,
)
from app.current_state.normalizer import canonical_scope
from app.current_state.read_service import (
    CurrentGuestRateCursorExpired,
    CurrentGuestRateEvidence,
    CurrentStateReadService,
)

from .models import (
    CurrentGuestTrafficItem,
    CurrentGuestTrafficPage,
    CurrentGuestTrafficResult,
)


UTC = timezone.utc
METRIC_VERSION = "network_traffic_online_guest_current_rate.v1"
POPULATION_METHOD = "fresh_complete_current_state_authorized_guest_scope.v1"
RATE_METHOD = "current_connection_counter_delta_interval_average.v1"
BASELINE_METHOD = "nearest_previous_complete_same_site_scope_cycle.v1"
CONTINUITY_METHOD = "omada_controller_connection_progress_v1"
BOUNDARY_OBSERVATION = "sampled_current_state_evidence_v1"
UNIT = "Mbps"
CURRENT_GUEST_RATE_MAX_GAP_SECONDS = 180
SUPPORTED_MAX_POPULATION = 10_000
DEFAULT_LIMIT = 50
MAX_LIMIT = 200
SORT = "total_rate_desc"

_CURSOR_VERSION = 2
_CURSOR_KIND = "current_guest_traffic"
_MAX_CURSOR_LENGTH = 2048
_MAC = re.compile(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}")
_AUTH = frozenset({"authorized", "pending", "other", "unknown"})


class CurrentGuestTrafficValidationError(ValueError):
    """Caller input or cursor violates the frozen read contract."""


class CurrentGuestTrafficSourceUnavailable(RuntimeError):
    """Persisted Current State evidence could not be read safely."""


class CurrentGuestTrafficIntegrityUnavailable(CurrentGuestTrafficSourceUnavailable):
    """Persisted evidence is contradictory or malformed."""


@dataclass(frozen=True, slots=True)
class _Projected:
    item: CurrentGuestTrafficItem
    total_delta_bytes: int | None


class CurrentGuestTrafficReadService:
    """Derive bounded Site-scoped current guest rates without source polling."""

    def __init__(self, current_state: CurrentStateReadService):
        if not isinstance(current_state, CurrentStateReadService):
            raise TypeError("current_state must be CurrentStateReadService")
        self._current_state = current_state

    def get_current_guest_traffic(
        self,
        site_id: str,
        *,
        evaluated_at_utc: datetime | str | None = None,
        limit: int = DEFAULT_LIMIT,
        cursor: str | None = None,
        sort: str = SORT,
    ) -> CurrentGuestTrafficResult:
        site = _site(site_id)
        page_limit = _limit(limit)
        if sort != SORT:
            raise CurrentGuestTrafficValidationError("sort is not allowed")
        decoded = _decode_cursor(cursor) if cursor is not None else None
        _, current_scope_hash = canonical_scope(
            "client", site, self._current_state.config.client_ssids
        )
        if decoded is not None:
            _validate_cursor_context(decoded, site, current_scope_hash, sort)
            if evaluated_at_utc is not None:
                supplied = _evaluated(evaluated_at_utc)
                if supplied != decoded["evaluated_at_utc"]:
                    raise CurrentGuestTrafficValidationError(
                        "cursor evaluated_at changed"
                    )
            evaluated_at_utc = decoded["evaluated_at_utc"]

        try:
            evidence = self._current_state.read_current_guest_rate_evidence(
                site,
                evaluated_at_utc=evaluated_at_utc,
                current_cycle_id=(decoded["current_cycle_id"] if decoded else None),
                baseline_cycle_id=(decoded["baseline_cycle_id"] if decoded else None),
                newer_attempt_cycle_id=(
                    decoded["newer_attempt_cycle_id"] if decoded else None
                ),
                pinned=decoded is not None,
                supported_max_population=SUPPORTED_MAX_POPULATION,
            )
        except CurrentGuestRateCursorExpired as exc:
            raise CurrentGuestTrafficValidationError("cursor_expired") from exc
        except CurrentStateValidationError as exc:
            raise CurrentGuestTrafficValidationError(
                "current guest traffic query is invalid"
            ) from exc
        except (CurrentStateStorageError, CurrentStateSchemaError) as exc:
            raise CurrentGuestTrafficSourceUnavailable(
                "current guest traffic source is unavailable"
            ) from exc

        try:
            if evidence.source_scope_hash != current_scope_hash:
                raise CurrentGuestTrafficIntegrityUnavailable(
                    "current guest traffic source scope is invalid"
                )
            return self._result(evidence, page_limit, decoded)
        except (CurrentGuestTrafficValidationError, CurrentGuestTrafficIntegrityUnavailable):
            raise
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise CurrentGuestTrafficIntegrityUnavailable(
                "current guest traffic source integrity is unavailable"
            ) from exc

    def _result(
        self,
        evidence: CurrentGuestRateEvidence,
        limit: int,
        cursor: Mapping[str, Any] | None,
    ) -> CurrentGuestTrafficResult:
        current = evidence.current_cycle
        if current is None:
            if cursor is not None:
                raise CurrentGuestTrafficValidationError("cursor_expired")
            return _empty_result(
                evidence,
                limit,
                status="unavailable",
                source_health_status="unavailable",
                source_health_reason="no_complete_snapshot",
            )

        current_context = _cycle(
            current,
            evidence.site_id,
            evidence.source_scope_hash,
            evidence.evaluated_at_utc,
        )
        scoped_count = _nonnegative(evidence.scoped_client_row_count, "scoped count")
        authorized_count = _nonnegative(
            evidence.known_authorized_count, "authorized count"
        )
        unknown_count = _nonnegative(evidence.unknown_auth_count, "unknown count")
        if int(current["items_stored"]) != scoped_count:
            raise CurrentGuestTrafficIntegrityUnavailable(
                "current guest traffic row count is invalid"
            )
        if authorized_count + unknown_count > scoped_count:
            raise CurrentGuestTrafficIntegrityUnavailable(
                "current guest traffic population counts are invalid"
            )

        source_health, health_reason = _source_health(
            current_context,
            evidence.newer_attempt,
            evidence.site_id,
            evidence.source_scope_hash,
            evidence.evaluated_at_utc,
            self._current_state.config.client_fresh_max_age_seconds,
            self._current_state.config.client_stale_max_age_seconds,
        )
        if scoped_count > SUPPORTED_MAX_POPULATION:
            return _empty_result(
                evidence,
                limit,
                status="unsupported_population",
                source_health_status=source_health,
                source_health_reason=health_reason,
                current_context=current_context,
                scoped_count=scoped_count,
                authorized_count=authorized_count,
                unknown_count=unknown_count,
            )
        if source_health in {"stale", "unavailable"}:
            return _empty_result(
                evidence,
                limit,
                status=source_health,
                source_health_status=source_health,
                source_health_reason=health_reason,
                current_context=current_context,
                scoped_count=scoped_count,
            )

        current_rows = tuple(dict(row) for row in evidence.current_rows)
        if len(current_rows) != scoped_count:
            raise CurrentGuestTrafficIntegrityUnavailable(
                "current guest traffic row materialization is invalid"
            )
        for row in current_rows:
            _row(row, current, evidence, current_cycle=True)
        actual_authorized = sum(
            row["auth_classification"] == "authorized" for row in current_rows
        )
        actual_unknown = sum(
            row["auth_classification"] == "unknown" for row in current_rows
        )
        if actual_authorized != authorized_count or actual_unknown != unknown_count:
            raise CurrentGuestTrafficIntegrityUnavailable(
                "current guest traffic auth counts are invalid"
            )
        population_complete = unknown_count == 0
        if authorized_count == 0:
            status = "partial" if source_health == "degraded" or not population_complete else "ok"
            return _root_result(
                evidence=evidence,
                limit=limit,
                current_context=current_context,
                baseline_context=None,
                elapsed=None,
                status=status,
                source_health=source_health,
                health_reason=health_reason,
                rate_evidence="not_applicable",
                population_complete=population_complete,
                scoped_count=scoped_count,
                authorized_count=0,
                unknown_count=unknown_count,
                valid_count=0,
                partial_count=0,
                unavailable_count=0,
                items=(),
                next_cursor=None,
            )

        baseline = evidence.baseline_cycle
        baseline_context = None
        elapsed = None
        baseline_rows: dict[str, Mapping[str, Any]] = {}
        if baseline is not None:
            baseline_context = _cycle(
                baseline,
                evidence.site_id,
                evidence.source_scope_hash,
                evidence.evaluated_at_utc,
            )
            if baseline_context["started"] >= current_context["started"]:
                raise CurrentGuestTrafficIntegrityUnavailable(
                    "current guest traffic baseline ordering is invalid"
                )
            elapsed = (
                current_context["started"] - baseline_context["started"]
            ).total_seconds()
            for row in evidence.baseline_rows:
                mapped = dict(row)
                _row(mapped, baseline, evidence, current_cycle=False)
                mac = str(mapped["client_mac"])
                if mac in baseline_rows:
                    raise CurrentGuestTrafficIntegrityUnavailable(
                        "current guest traffic baseline identity is invalid"
                    )
                baseline_rows[mac] = mapped

        projected: list[_Projected] = []
        for row in current_rows:
            if row["auth_classification"] != "authorized":
                continue
            projected.append(
                _project(
                    row,
                    baseline_rows.get(str(row["client_mac"])),
                    elapsed,
                    baseline is not None,
                )
            )
        if len(projected) != authorized_count:
            raise CurrentGuestTrafficIntegrityUnavailable(
                "current guest traffic authorized projection is invalid"
            )
        valid_count = sum(item.item.rate_status == "valid" for item in projected)
        partial_count = sum(item.item.rate_status == "partial" for item in projected)
        unavailable_count = sum(
            item.item.rate_status == "unavailable" for item in projected
        )
        if valid_count + partial_count + unavailable_count != authorized_count:
            raise CurrentGuestTrafficIntegrityUnavailable(
                "current guest traffic rate counts are invalid"
            )
        if valid_count == authorized_count:
            rate_evidence = "complete"
        elif valid_count or partial_count:
            rate_evidence = "partial"
        else:
            rate_evidence = "insufficient_data"
        if source_health == "degraded" or not population_complete or rate_evidence == "partial":
            status = "partial"
        elif rate_evidence == "insufficient_data":
            status = "insufficient_data"
        else:
            status = "ok"

        projected.sort(
            key=lambda value: (
                value.total_delta_bytes is None,
                -(value.total_delta_bytes or 0),
                value.item.client_mac,
            )
        )
        if cursor is not None:
            projected = [value for value in projected if _after(value, cursor)]
        visible = projected[:limit]
        has_more = len(projected) > limit
        next_cursor = None
        if has_more and visible:
            last = visible[-1]
            next_cursor = _encode_cursor(
                evidence,
                baseline,
                last,
                SORT,
            )
        return _root_result(
            evidence=evidence,
            limit=limit,
            current_context=current_context,
            baseline_context=baseline_context,
            elapsed=elapsed,
            status=status,
            source_health=source_health,
            health_reason=health_reason,
            rate_evidence=rate_evidence,
            population_complete=population_complete,
            scoped_count=scoped_count,
            authorized_count=authorized_count,
            unknown_count=unknown_count,
            valid_count=valid_count,
            partial_count=partial_count,
            unavailable_count=unavailable_count,
            items=tuple(value.item for value in visible),
            next_cursor=next_cursor,
        )


def _site(value: Any) -> str:
    try:
        return require_site_id(value)
    except CurrentStateValidationError as exc:
        raise CurrentGuestTrafficValidationError("site_id is invalid") from exc


def _limit(value: Any) -> int:
    if type(value) is not int or not 1 <= value <= MAX_LIMIT:
        raise CurrentGuestTrafficValidationError("limit is outside bounds")
    return value


def _evaluated(value: datetime | str) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise CurrentGuestTrafficValidationError("evaluated_at must be UTC")
        value = value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:23] + "Z"
    try:
        parse_utc(value, "evaluated_at_utc")
    except CurrentStateValidationError as exc:
        raise CurrentGuestTrafficValidationError("evaluated_at is invalid") from exc
    return value


def _cycle(
    row: Mapping[str, Any],
    site: str,
    scope_hash: str,
    evaluated_at: str,
) -> dict[str, Any]:
    expected_scope, expected_hash = canonical_scope(
        "client", site, tuple(json.loads(row["source_scope_json"])["ssids"])
    )
    try:
        started = parse_utc(row["capture_started_at"], "capture_started_at")
        finished = parse_utc(row["capture_finished_at"], "capture_finished_at")
        evaluated = parse_utc(evaluated_at, "evaluated_at")
    except CurrentStateValidationError as exc:
        raise CurrentGuestTrafficIntegrityUnavailable(
            "current guest traffic cycle timestamp is invalid"
        ) from exc
    if (
        row["site_id"] != site
        or row["kind"] != "client"
        or row["result"] != "success"
        or int(row["complete"]) != 1
        or row["source_scope_hash"] != scope_hash
        or expected_hash != scope_hash
        or row["source_scope_json"] != expected_scope
        or int(row["source_scope_version"]) != 1
        or int(row["unidentified_count"]) != 0
        or int(row["duplicate_identity_count"]) != 0
        or int(row["error_count"]) != 0
        or finished < started
    ):
        raise CurrentGuestTrafficIntegrityUnavailable(
            "current guest traffic cycle integrity is invalid"
        )
    return {"started": started, "finished": finished}


def _source_health(
    context: Mapping[str, Any],
    newer: Mapping[str, Any] | None,
    site: str,
    scope_hash: str,
    evaluated_at: str,
    fresh_seconds: int,
    stale_seconds: int,
) -> tuple[str, str]:
    evaluated = parse_utc(evaluated_at, "evaluated_at")
    age = (evaluated - context["started"]).total_seconds()
    if age < 0:
        return "unavailable", "clock_anomaly"
    if age > stale_seconds:
        return "unavailable", "older_than_unavailable_threshold"
    if age > fresh_seconds:
        return "stale", "older_than_freshness_window"
    if newer is not None:
        try:
            newer_started = parse_utc(newer["capture_started_at"], "newer attempt")
        except CurrentStateValidationError as exc:
            raise CurrentGuestTrafficIntegrityUnavailable(
                "current guest traffic newer attempt is invalid"
            ) from exc
        if (
            newer["site_id"] != site
            or newer["kind"] != "client"
            or newer["source_scope_hash"] != scope_hash
            or newer_started > evaluated
            or newer["result"] not in {"partial", "failed", "shutdown"}
            or int(newer["complete"]) != 0
        ):
            raise CurrentGuestTrafficIntegrityUnavailable(
                "current guest traffic newer attempt is invalid"
            )
        return "degraded", "newer_degraded_attempt"
    return "healthy", "within_freshness_window"


def _row(
    row: Mapping[str, Any],
    cycle: Mapping[str, Any],
    evidence: CurrentGuestRateEvidence,
    *,
    current_cycle: bool,
) -> None:
    mac = row.get("client_mac")
    if (
        row.get("cycle_id") != cycle["cycle_id"]
        or row.get("cycle_kind") != "client"
        or row.get("site_id") != evidence.site_id
        or row.get("observed_at") != cycle["capture_started_at"]
        or not isinstance(mac, str)
        or _MAC.fullmatch(mac) is None
        or row.get("auth_classification") not in _AUTH
        or int(row.get("active")) != 1
        or int(row.get("wireless")) != 1
        or row.get("ssid") not in evidence_scope_ssids(cycle)
    ):
        raise CurrentGuestTrafficIntegrityUnavailable(
            "current guest traffic row integrity is invalid"
        )
    for name in (
        "controller_uptime",
        "controller_traffic_down",
        "controller_traffic_up",
        "controller_traffic_total",
    ):
        value = row.get(name)
        if value is not None and (type(value) is not int or value < 0):
            raise CurrentGuestTrafficIntegrityUnavailable(
                "current guest traffic counter integrity is invalid"
            )


def evidence_scope_ssids(cycle: Mapping[str, Any]) -> frozenset[str]:
    try:
        payload = json.loads(cycle["source_scope_json"])
        ssids = payload["ssids"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise CurrentGuestTrafficIntegrityUnavailable(
            "current guest traffic source scope is invalid"
        ) from exc
    if not isinstance(ssids, list) or any(not isinstance(value, str) for value in ssids):
        raise CurrentGuestTrafficIntegrityUnavailable(
            "current guest traffic source scope is invalid"
        )
    return frozenset(ssids)


def _project(
    current: Mapping[str, Any],
    baseline: Mapping[str, Any] | None,
    elapsed: float | None,
    has_baseline_cycle: bool,
) -> _Projected:
    common = {
        "client_mac": str(current["client_mac"]),
        "name": current.get("name"),
        "ssid": str(current["ssid"]),
        "ap_mac": current.get("ap_mac"),
    }
    if not has_baseline_cycle:
        return _unavailable(common, "no_baseline")
    if baseline is None or baseline.get("auth_classification") != "authorized":
        return _unavailable(common, "no_authorized_baseline")
    if baseline.get("ssid") != current.get("ssid"):
        return _unavailable(common, "ssid_transition")
    if elapsed is None or not math.isfinite(elapsed) or elapsed <= 0:
        return _unavailable(common, "invalid_elapsed")
    if elapsed > CURRENT_GUEST_RATE_MAX_GAP_SECONDS:
        return _unavailable(common, "baseline_gap_too_large")

    current_uptime = current.get("controller_uptime")
    baseline_uptime = baseline.get("controller_uptime")
    if current_uptime is None or baseline_uptime is None:
        growth = _has_counter_growth(current, baseline)
        return _unavailable(
            common,
            "connection_continuity_unproven",
            progress="advanced" if growth else "unproven",
            basis="counters_only_diagnostic" if growth else "none",
        )
    if current_uptime == baseline_uptime:
        return _unavailable(common, "source_frozen", progress="frozen")
    if current_uptime < baseline_uptime:
        return _unavailable(
            common,
            "connection_reset",
            progress="unproven",
            continuity="reset",
        )

    down, down_delta, down_reason = _direction(
        current.get("controller_traffic_down"),
        baseline.get("controller_traffic_down"),
        elapsed,
    )
    up, up_delta, up_reason = _direction(
        current.get("controller_traffic_up"),
        baseline.get("controller_traffic_up"),
        elapsed,
    )
    total = None if down is None or up is None else down + up
    total_delta = None if down_delta is None or up_delta is None else down_delta + up_delta
    if total is not None:
        total_reason = "valid"
    elif "counter_reset" in {down_reason, up_reason}:
        total_reason = "counter_reset"
    elif "counter_missing" in {down_reason, up_reason}:
        total_reason = "counter_missing"
    else:
        total_reason = "connection_continuity_unproven"
    numeric_count = sum(value is not None for value in (down, up, total))
    rate_status = "valid" if numeric_count == 3 else "partial" if numeric_count else "unavailable"
    item = CurrentGuestTrafficItem(
        **common,
        download_mbps=down,
        upload_mbps=up,
        total_mbps=total,
        source_progress_status="advanced",
        connection_continuity_status="proven",
        continuity_basis="uptime_progress",
        download_reason=down_reason,
        upload_reason=up_reason,
        total_reason=total_reason,
        rate_status=rate_status,
    )
    return _Projected(item, total_delta)


def _direction(current: Any, baseline: Any, elapsed: float) -> tuple[float | None, int | None, str]:
    if current is None or baseline is None:
        return None, None, "counter_missing"
    if current < baseline:
        return None, None, "counter_reset"
    delta = current - baseline
    rate = delta * 8 / elapsed / 1_000_000
    if not math.isfinite(rate) or rate < 0:
        raise CurrentGuestTrafficIntegrityUnavailable(
            "current guest traffic rate is invalid"
        )
    return rate, delta, "valid"


def _has_counter_growth(current: Mapping[str, Any], baseline: Mapping[str, Any]) -> bool:
    for name in ("controller_traffic_down", "controller_traffic_up"):
        current_value = current.get(name)
        baseline_value = baseline.get(name)
        if (
            isinstance(current_value, int)
            and isinstance(baseline_value, int)
            and current_value > baseline_value
        ):
            return True
    return False


def _unavailable(
    common: Mapping[str, Any],
    reason: str,
    *,
    progress: str = "unproven",
    continuity: str = "unproven",
    basis: str = "none",
) -> _Projected:
    return _Projected(
        CurrentGuestTrafficItem(
            **common,
            download_mbps=None,
            upload_mbps=None,
            total_mbps=None,
            source_progress_status=progress,
            connection_continuity_status=continuity,
            continuity_basis=basis,
            download_reason=reason,
            upload_reason=reason,
            total_reason=reason,
            rate_status="unavailable",
        ),
        None,
    )


def _empty_result(
    evidence: CurrentGuestRateEvidence,
    limit: int,
    *,
    status: str,
    source_health_status: str,
    source_health_reason: str,
    current_context: Mapping[str, Any] | None = None,
    scoped_count: int | None = None,
    authorized_count: int | None = None,
    unknown_count: int | None = None,
) -> CurrentGuestTrafficResult:
    current = evidence.current_cycle
    asserted = status == "unsupported_population"
    return CurrentGuestTrafficResult(
        metric_version=METRIC_VERSION,
        population_method=POPULATION_METHOD,
        rate_method=RATE_METHOD,
        baseline_method=BASELINE_METHOD,
        continuity_method=CONTINUITY_METHOD,
        connection_boundary_observation=BOUNDARY_OBSERVATION,
        unit=UNIT,
        site_id=evidence.site_id,
        evaluated_at_utc=evidence.evaluated_at_utc,
        current_cycle_id=str(current["cycle_id"]) if current is not None else None,
        baseline_cycle_id=None,
        source_scope_hash=evidence.source_scope_hash if current is not None else None,
        current_capture_started_at=(
            str(current["capture_started_at"]) if current is not None else None
        ),
        baseline_capture_started_at=None,
        elapsed_seconds=None,
        status=status,
        source_health_status=source_health_status,
        source_health_reason=source_health_reason,
        rate_evidence_status="insufficient_data",
        population_complete=False,
        scoped_client_row_count=scoped_count if asserted else None,
        known_authorized_count=authorized_count if asserted else None,
        unknown_auth_count=unknown_count if asserted else None,
        population_count=authorized_count if asserted else None,
        supported_max_population=SUPPORTED_MAX_POPULATION,
        rate_valid_count=None,
        rate_partial_count=None,
        rate_unavailable_count=None,
        items=(),
        page=CurrentGuestTrafficPage(limit, 0, None, SORT),
    )


def _root_result(
    *,
    evidence: CurrentGuestRateEvidence,
    limit: int,
    current_context: Mapping[str, Any],
    baseline_context: Mapping[str, Any] | None,
    elapsed: float | None,
    status: str,
    source_health: str,
    health_reason: str,
    rate_evidence: str,
    population_complete: bool,
    scoped_count: int,
    authorized_count: int,
    unknown_count: int,
    valid_count: int,
    partial_count: int,
    unavailable_count: int,
    items: tuple[CurrentGuestTrafficItem, ...],
    next_cursor: str | None,
) -> CurrentGuestTrafficResult:
    current = evidence.current_cycle
    baseline = evidence.baseline_cycle
    assert current is not None
    return CurrentGuestTrafficResult(
        metric_version=METRIC_VERSION,
        population_method=POPULATION_METHOD,
        rate_method=RATE_METHOD,
        baseline_method=BASELINE_METHOD,
        continuity_method=CONTINUITY_METHOD,
        connection_boundary_observation=BOUNDARY_OBSERVATION,
        unit=UNIT,
        site_id=evidence.site_id,
        evaluated_at_utc=evidence.evaluated_at_utc,
        current_cycle_id=str(current["cycle_id"]),
        baseline_cycle_id=str(baseline["cycle_id"]) if baseline is not None else None,
        source_scope_hash=evidence.source_scope_hash,
        current_capture_started_at=str(current["capture_started_at"]),
        baseline_capture_started_at=(
            str(baseline["capture_started_at"]) if baseline is not None else None
        ),
        elapsed_seconds=elapsed,
        status=status,
        source_health_status=source_health,
        source_health_reason=health_reason,
        rate_evidence_status=rate_evidence,
        population_complete=population_complete,
        scoped_client_row_count=scoped_count,
        known_authorized_count=authorized_count,
        unknown_auth_count=unknown_count,
        population_count=authorized_count,
        supported_max_population=SUPPORTED_MAX_POPULATION,
        rate_valid_count=valid_count,
        rate_partial_count=partial_count,
        rate_unavailable_count=unavailable_count,
        items=items,
        page=CurrentGuestTrafficPage(limit, len(items), next_cursor, SORT),
    )


def _nonnegative(value: Any, name: str) -> int:
    if type(value) is not int or value < 0:
        raise CurrentGuestTrafficIntegrityUnavailable(f"{name} is invalid")
    return value


def _encode_cursor(
    evidence: CurrentGuestRateEvidence,
    baseline: Mapping[str, Any] | None,
    last: _Projected,
    sort: str,
) -> str:
    current = evidence.current_cycle
    assert current is not None
    payload = {
        "v": _CURSOR_VERSION,
        "kind": _CURSOR_KIND,
        "site_id": evidence.site_id,
        "current_cycle_id": current["cycle_id"],
        "baseline_cycle_id": baseline["cycle_id"] if baseline is not None else None,
        "newer_attempt_cycle_id": (
            evidence.newer_attempt["cycle_id"]
            if evidence.newer_attempt is not None
            else None
        ),
        "source_scope_hash": evidence.source_scope_hash,
        "sort": sort,
        "evaluated_at_utc": evidence.evaluated_at_utc,
        "sort_class": "numeric" if last.total_delta_bytes is not None else "null",
        "total_delta_bytes": last.total_delta_bytes,
        "client_mac": last.item.client_mac,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _decode_cursor(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, str) or not value or len(value) > _MAX_CURSOR_LENGTH:
        raise CurrentGuestTrafficValidationError("cursor is malformed")
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        decoded = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise CurrentGuestTrafficValidationError("cursor is malformed") from exc
    required = {
        "v", "kind", "site_id", "current_cycle_id", "baseline_cycle_id",
        "newer_attempt_cycle_id", "source_scope_hash", "sort",
        "evaluated_at_utc", "sort_class", "total_delta_bytes", "client_mac",
    }
    if not isinstance(decoded, dict) or set(decoded) != required:
        raise CurrentGuestTrafficValidationError("cursor is malformed")
    if (
        decoded["v"] != _CURSOR_VERSION
        or decoded["kind"] != _CURSOR_KIND
        or decoded["sort_class"] not in {"numeric", "null"}
        or not isinstance(decoded["client_mac"], str)
        or _MAC.fullmatch(decoded["client_mac"]) is None
        or (
            decoded["sort_class"] == "numeric"
            and (type(decoded["total_delta_bytes"]) is not int or decoded["total_delta_bytes"] < 0)
        )
        or (
            decoded["sort_class"] == "null"
            and decoded["total_delta_bytes"] is not None
        )
    ):
        raise CurrentGuestTrafficValidationError("cursor is malformed")
    return decoded


def _validate_cursor_context(
    cursor: Mapping[str, Any], site: str, scope_hash: str, sort: str
) -> None:
    if cursor["site_id"] != site:
        raise CurrentGuestTrafficValidationError("cursor Site changed")
    if cursor["source_scope_hash"] != scope_hash:
        raise CurrentGuestTrafficValidationError("cursor source scope changed")
    if cursor["sort"] != sort:
        raise CurrentGuestTrafficValidationError("cursor sort changed")
    if not isinstance(cursor["current_cycle_id"], str) or not cursor["current_cycle_id"]:
        raise CurrentGuestTrafficValidationError("cursor current cycle is invalid")
    baseline = cursor["baseline_cycle_id"]
    if baseline is not None and (not isinstance(baseline, str) or not baseline):
        raise CurrentGuestTrafficValidationError("cursor baseline cycle is invalid")
    newer = cursor["newer_attempt_cycle_id"]
    if newer is not None and (not isinstance(newer, str) or not newer):
        raise CurrentGuestTrafficValidationError(
            "cursor newer attempt is invalid"
        )
    _evaluated(cursor["evaluated_at_utc"])


def _after(value: _Projected, cursor: Mapping[str, Any]) -> bool:
    if cursor["sort_class"] == "numeric":
        if value.total_delta_bytes is None:
            return True
        last_delta = int(cursor["total_delta_bytes"])
        return value.total_delta_bytes < last_delta or (
            value.total_delta_bytes == last_delta
            and value.item.client_mac > cursor["client_mac"]
        )
    return (
        value.total_delta_bytes is None
        and value.item.client_mac > cursor["client_mac"]
    )
