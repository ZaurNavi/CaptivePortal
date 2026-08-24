"""Bounded, Site-scoped current traffic reads over persisted AP facts."""

from __future__ import annotations

import base64
import json
import math
import re
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Mapping

from .models import (
    CurrentApTrafficItem,
    CurrentApTrafficPage,
    CurrentSiteTraffic,
    CurrentTrafficCoverage,
    CurrentTrafficFreshness,
    CurrentTrafficFreshnessPolicy,
    CurrentTrafficPageMetadata,
    CurrentTrafficSnapshot,
    CurrentTrafficSourceSelection,
    CurrentTrafficTotals,
)
from .source_gateway import (
    AnalyticsQueryDeadlineExceeded,
    AnalyticsSourceGateway,
    AnalyticsSourceUnavailable,
    QueryDeadline,
)
from .validation import AnalyticsQueryValidationError, format_utc, parse_utc, require_site


UTC = timezone.utc
PRIMARY_SOURCE = "wired"
SOURCES = frozenset({"wired", "lan"})
RATE_REASONS = frozenset({
    "ok", "no_baseline", "counter_reset", "gap_too_large",
    "invalid_elapsed", "source_unavailable",
})
_LATEST_STATES = frozenset({"running", "completed", "abandoned"})
_LATEST_RESULTS = frozenset({"success", "partial", "failed", "shutdown"})
_CURSOR_VERSION = 1
_CURSOR_KIND = "current_traffic_aps"
_MAX_CURSOR_LENGTH = 1024
_MAX_PAGE_LIMIT = 250
_MAC_PATTERN = re.compile(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}")


class CurrentTrafficValidationError(ValueError):
    """Caller input does not satisfy the Current Traffic contract."""


class CurrentTrafficSourceUnavailable(RuntimeError):
    """Persisted source facts cannot safely describe current traffic."""


class CurrentTrafficReadService:
    """Derive current AP traffic without polling or writing source storage."""

    def __init__(self, gateway: AnalyticsSourceGateway):
        self._gateway = gateway

    def get_current_site_traffic(
        self,
        site_id: str,
        *,
        evaluated_at_utc: str | None = None,
        fresh_max_age_seconds: float,
        stale_max_age_seconds: float,
        max_ap_skew_seconds: float,
        deadline: QueryDeadline | None = None,
    ) -> CurrentSiteTraffic:
        site = _site(site_id)
        evaluated, evaluated_text = _evaluation(evaluated_at_utc)
        policy = _policy(
            fresh_max_age_seconds,
            stale_max_age_seconds,
            max_ap_skew_seconds,
        )
        query_deadline = deadline or QueryDeadline.after(10.0)
        data = self._read(
            site_id=site,
            cycle_id=None,
            evaluated_at_utc=evaluated_text,
            after_ap_mac=None,
            page_limit=None,
            deadline=query_deadline,
        )
        cycle = data["cycle"]
        latest = data["latest"]
        if cycle is None:
            return _no_snapshot(site, latest, policy, evaluated_text)

        rows = tuple(dict(row) for row in data["rows"])
        context = _context_or_unavailable(
            site, dict(cycle), dict(data["stats"]), rows,
            latest, evaluated, evaluated_text, policy,
        )
        return _site_result(context, rows)

    def list_current_ap_traffic(
        self,
        site_id: str,
        *,
        cycle_id: str,
        evaluated_at_utc: str | None = None,
        fresh_max_age_seconds: float,
        stale_max_age_seconds: float,
        max_ap_skew_seconds: float,
        limit: int = 100,
        cursor: str | None = None,
        deadline: QueryDeadline | None = None,
    ) -> CurrentApTrafficPage:
        site = _site(site_id)
        cycle = _cycle_id(cycle_id)
        page_limit = _limit(limit)
        evaluated, evaluated_text = _evaluation(evaluated_at_utc)
        policy = _policy(
            fresh_max_age_seconds,
            stale_max_age_seconds,
            max_ap_skew_seconds,
        )
        cursor_data = _decode_cursor(cursor) if cursor is not None else None
        if cursor_data is not None:
            if cursor_data["site_id"] != site or cursor_data["cycle_id"] != cycle:
                raise CurrentTrafficValidationError("traffic cursor context mismatch")
            after_ap_mac = str(cursor_data["last_ap_mac"])
        else:
            after_ap_mac = None
        data = self._read(
            site_id=site,
            cycle_id=cycle,
            evaluated_at_utc=evaluated_text,
            after_ap_mac=after_ap_mac,
            page_limit=page_limit,
            deadline=deadline or QueryDeadline.after(10.0),
        )
        if data["cycle"] is None:
            raise CurrentTrafficValidationError("traffic cycle is unavailable")
        rows = tuple(dict(row) for row in data["rows"])
        context = _context_or_unavailable(
            site, dict(data["cycle"]), dict(data["stats"]), rows,
            data["latest"], evaluated, evaluated_text, policy,
            validate_page_rows_only=True,
        )
        selected = context["selected_source"]
        if cursor_data is not None and cursor_data["selected_source"] != selected:
            raise CurrentTrafficValidationError("traffic cursor source mismatch")
        has_more = len(rows) > page_limit
        visible = rows[:page_limit]
        items = tuple(_ap_item(row, selected, context) for row in visible)
        next_cursor = None
        if has_more:
            next_cursor = _encode_cursor(
                site, cycle, selected, str(visible[-1]["ap_mac"])
            )
        return CurrentApTrafficPage(
            snapshot=context["snapshot"],
            freshness_policy=policy,
            source_selection=context["source_selection"],
            items=items,
            page=CurrentTrafficPageMetadata(
                limit=page_limit,
                next_cursor=next_cursor,
                cycle_id=cycle,
                selected_source=selected,
            ),
        )

    def _read(self, **kwargs: Any) -> Mapping[str, Any]:
        try:
            return self._gateway.current_traffic_data(**kwargs)
        except AnalyticsQueryDeadlineExceeded:
            raise
        except AnalyticsSourceUnavailable as exc:
            raise CurrentTrafficSourceUnavailable(
                "Current traffic source is unavailable"
            ) from exc


def _context_or_unavailable(*args: Any, **kwargs: Any) -> dict[str, Any]:
    try:
        return _validated_context(*args, **kwargs)
    except CurrentTrafficSourceUnavailable:
        raise
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise CurrentTrafficSourceUnavailable(
            "Current traffic source integrity is unavailable"
        ) from exc


def _validated_context(
    site: str,
    cycle: Mapping[str, Any],
    stats: Mapping[str, Any],
    rows: tuple[Mapping[str, Any], ...],
    latest_row: Any,
    evaluated: datetime,
    evaluated_text: str,
    policy: CurrentTrafficFreshnessPolicy,
    *,
    validate_page_rows_only: bool = False,
) -> dict[str, Any]:
    try:
        started = parse_utc(cycle["started_at"], "cycle started_at")
        finished = parse_utc(cycle["finished_at"], "cycle finished_at")
    except (KeyError, AnalyticsQueryValidationError) as exc:
        raise CurrentTrafficSourceUnavailable(
            "Current traffic cycle timestamp is invalid"
        ) from exc
    expected_count = int(cycle["items_stored"])
    if (
        finished < started
        or int(cycle["complete"]) != 1
        or cycle["state"] != "completed"
        or cycle["result"] != "success"
        or int(cycle["items_seen"]) != expected_count
        or int(cycle["items_skipped"]) != 0
        or int(cycle["error_count"]) != 0
        or int(cycle["data_quality_warning_count"]) != 0
        or cycle["source_rows_reported"] is None
        or int(cycle["source_rows_reported"]) != int(cycle["items_seen"])
        or int(stats["stored_row_count"]) != expected_count
        or any(int(stats[name]) != 0 for name in (
            "bad_site_count", "bad_mac_count", "duplicate_mac_count",
            "bad_flag_count", "bad_rate_count", "missing_wired_time_count",
            "missing_lan_time_count",
        ))
    ):
        raise CurrentTrafficSourceUnavailable(
            "Current traffic source integrity is unavailable"
        )
    for row in rows:
        _validate_row(row, site, str(cycle["cycle_id"]))

    total = int(stats["stored_row_count"])
    wired_pairs = int(stats["wired_pair_valid_count"])
    lan_pairs = int(stats["lan_pair_valid_count"])
    selected, selection_reason = _select_source(total, wired_pairs, lan_pairs)
    source_selection = CurrentTrafficSourceSelection(
        primary_source=PRIMARY_SOURCE,
        selected_source=selected,
        selection_reason=selection_reason,
        wired_pair_valid_ap_count=wired_pairs,
        lan_pair_valid_ap_count=lan_pairs,
    )
    latest = dict(latest_row) if latest_row is not None else None
    snapshot = _snapshot(
        site, cycle, latest, selected, selection_reason, total == 0,
        evaluated_text,
    )
    oldest_text = stats[f"{selected}_oldest"]
    newest_text = stats[f"{selected}_newest"]
    temporal_anomaly = finished > evaluated
    oldest = newest = None
    if total:
        try:
            oldest = parse_utc(oldest_text, "traffic observed_at")
            newest = parse_utc(newest_text, "traffic newest_observed_at")
        except AnalyticsQueryValidationError as exc:
            raise CurrentTrafficSourceUnavailable(
                "Current traffic timestamp is invalid"
            ) from exc
        temporal_anomaly = temporal_anomaly or not (
            started <= oldest <= newest <= finished
        )
    context = {
        "site": site,
        "cycle": cycle,
        "snapshot": snapshot,
        "source_selection": source_selection,
        "selected_source": selected,
        "selection_reason": selection_reason,
        "total": total,
        "wired_pairs": wired_pairs,
        "lan_pairs": lan_pairs,
        "started": started,
        "finished": finished,
        "oldest": oldest,
        "newest": newest,
        "oldest_text": oldest_text,
        "newest_text": newest_text,
        "evaluated": evaluated,
        "evaluated_text": evaluated_text,
        "policy": policy,
        "temporal_anomaly": temporal_anomaly,
    }
    if total == 0:
        snapshot_freshness = _freshness(finished, finished, context, temporal_anomaly)
        skew = 0.0
    else:
        snapshot_freshness = _freshness(oldest, newest, context, temporal_anomaly)
        skew = (newest - oldest).total_seconds()
    context["snapshot"] = replace(
        snapshot,
        observed_at=snapshot_freshness.observed_at,
        newest_observed_at=snapshot_freshness.newest_observed_at,
        age_seconds=snapshot_freshness.age_seconds,
        source_skew_seconds=skew,
        freshness_status=snapshot_freshness.status,
        freshness_reason=snapshot_freshness.reason,
    )
    return context


def _site_result(
    context: Mapping[str, Any], rows: tuple[Mapping[str, Any], ...]
) -> CurrentSiteTraffic:
    total = int(context["total"])
    policy = context["policy"]
    if total == 0:
        return CurrentSiteTraffic(
            snapshot=context["snapshot"], freshness_policy=policy,
            source_selection=context["source_selection"],
            coverage=CurrentTrafficCoverage(
                status="complete", reasons=("empty_population",),
                empty_population=True,
                total_ap_count=0, valid_rate_ap_count=0,
                valid_download_ap_count=0, valid_upload_ap_count=0,
                missing_rate_ap_count=0, stale_ap_count=0,
                unavailable_ap_count=0, reset_ap_count=0,
                gap_rejected_ap_count=0, no_baseline_ap_count=0,
                source_unavailable_ap_count=0, invalid_elapsed_ap_count=0,
                observed_at=context["cycle"]["finished_at"],
                newest_observed_at=context["cycle"]["finished_at"],
                source_skew_seconds=0.0,
            ),
            freshness=_freshness(
                context["finished"], context["finished"], context, False
            ),
            traffic=CurrentTrafficTotals(0.0, 0.0, 0.0),
        )

    source = str(context["selected_source"])
    down_values: list[float] = []
    up_values: list[float] = []
    pair_count = 0
    stale = unavailable = 0
    reset = gap = baseline = source_unavailable = invalid_elapsed = 0
    for row in rows:
        down, up, down_reason, up_reason, observed_text = _source_values(row, source)
        observed = _source_datetime(observed_text)
        if not (
            context["started"] <= observed <= context["finished"]
            <= context["evaluated"]
        ):
            down = up = None
        if down is not None:
            down_values.append(down)
        if up is not None:
            up_values.append(up)
        if down is not None and up is not None:
            pair_count += 1
        reasons = {down_reason, up_reason}
        reset += int("counter_reset" in reasons)
        gap += int("gap_too_large" in reasons)
        baseline += int("no_baseline" in reasons)
        source_unavailable += int("source_unavailable" in reasons)
        invalid_elapsed += int("invalid_elapsed" in reasons)
        age = (context["evaluated"] - observed).total_seconds()
        if (
            observed < context["started"] or observed > context["finished"]
            or age < 0 or age > policy.stale_max_age_seconds
        ):
            unavailable += 1
        elif age > policy.fresh_max_age_seconds:
            stale += 1
    expected_pairs = (
        int(context["wired_pairs"])
        if source == "wired" else int(context["lan_pairs"])
    )
    if pair_count != expected_pairs:
        raise CurrentTrafficSourceUnavailable(
            "Current traffic source integrity is unavailable"
        )
    download = sum(down_values) if down_values else None
    upload = sum(up_values) if up_values else None
    total_value = download + upload if download is not None and upload is not None else None
    skew = (context["newest"] - context["oldest"]).total_seconds()
    reasons: list[str] = []
    if len(down_values) != total or len(up_values) != total:
        reasons.append("missing_direction")
    if pair_count != total:
        reasons.append("missing_pair")
    if skew > policy.max_ap_skew_seconds:
        reasons.append("temporal_skew")
    if download is None and upload is None:
        reasons.append("no_valid_rate")
    complete = pair_count == total and skew <= policy.max_ap_skew_seconds
    status = "complete" if complete else ("partial" if total_value is not None or download is not None or upload is not None else "none")
    freshness = _freshness(context["oldest"], context["newest"], context, context["temporal_anomaly"])
    if freshness.status == "unavailable":
        download = upload = total_value = None
    return CurrentSiteTraffic(
        snapshot=context["snapshot"], freshness_policy=policy,
        source_selection=context["source_selection"],
        coverage=CurrentTrafficCoverage(
            status=status, reasons=tuple(reasons), total_ap_count=total,
            empty_population=False,
            valid_rate_ap_count=pair_count,
            valid_download_ap_count=len(down_values),
            valid_upload_ap_count=len(up_values),
            missing_rate_ap_count=total - pair_count,
            stale_ap_count=stale, unavailable_ap_count=unavailable,
            reset_ap_count=reset, gap_rejected_ap_count=gap,
            no_baseline_ap_count=baseline,
            source_unavailable_ap_count=source_unavailable,
            invalid_elapsed_ap_count=invalid_elapsed,
            observed_at=context["oldest_text"],
            newest_observed_at=context["newest_text"],
            source_skew_seconds=skew,
        ),
        freshness=freshness,
        traffic=CurrentTrafficTotals(download, upload, total_value),
    )


def _ap_item(
    row: Mapping[str, Any], source: str, context: Mapping[str, Any]
) -> CurrentApTrafficItem:
    down, up, down_reason, up_reason, observed_text = _source_values(row, source)
    observed = _source_datetime(observed_text)
    age = (context["evaluated"] - observed).total_seconds()
    temporal_bad = (
        observed < context["started"] or observed > context["finished"]
        or age < 0 or age > context["policy"].stale_max_age_seconds
    )
    if temporal_bad:
        down = up = None
    total = down + up if down is not None and up is not None else None
    status = "valid" if total is not None else (
        "partial" if down is not None or up is not None else "unavailable"
    )
    return CurrentApTrafficItem(
        ap_mac=str(row["ap_mac"]), name=row["name"],
        download_mbps=down, upload_mbps=up, total_mbps=total,
        download_reason=str(down_reason), upload_reason=str(up_reason),
        rate_status=status, observed_at=str(observed_text),
        age_seconds=max(age, 0.0), selected_source=source,
    )


def _source_values(
    row: Mapping[str, Any], source: str
) -> tuple[float | None, float | None, str, str, str]:
    if source == "wired":
        keys = (
            "wired_download_mbps", "wired_upload_mbps",
            "wired_download_rate_reason", "wired_upload_rate_reason",
            "wired_observed_at",
        )
    else:
        keys = (
            "lan_rx_mbps", "lan_tx_mbps", "lan_rx_rate_reason",
            "lan_tx_rate_reason", "lan_observed_at",
        )
    down_reason, up_reason = str(row[keys[2]]), str(row[keys[3]])
    down = float(row[keys[0]]) if down_reason == "ok" else None
    up = float(row[keys[1]]) if up_reason == "ok" else None
    return down, up, down_reason, up_reason, str(row[keys[4]])


def _validate_row(row: Mapping[str, Any], site: str, cycle_id: str) -> None:
    if (
        row.get("site_id") != site or row.get("cycle_id") != cycle_id
        or not isinstance(row.get("ap_mac"), str)
        or _MAC_PATTERN.fullmatch(str(row["ap_mac"])) is None
        or any(int(row[name]) != expected for name, expected in (
            ("partial", 0), ("overview_ok", 1), ("wired_uplink_ok", 1),
            ("lan_traffic_ok", 1), ("radios_ok", 1),
        ))
    ):
        raise CurrentTrafficSourceUnavailable(
            "Current traffic AP identity is unavailable"
        )
    for source in SOURCES:
        _source_values(row, source)


def _select_source(total: int, wired: int, lan: int) -> tuple[str, str]:
    if total == 0:
        return "wired", "empty_population"
    if wired == total:
        return "wired", "primary_full_coverage"
    if lan == total:
        return "lan", "fallback_full_coverage"
    if lan > wired:
        return "lan", "fallback_higher_coverage"
    return "wired", "primary_preferred_tie_or_higher"


def _freshness(
    oldest: datetime,
    newest: datetime,
    context: Mapping[str, Any],
    temporal_anomaly: bool,
) -> CurrentTrafficFreshness:
    age = (context["evaluated"] - oldest).total_seconds()
    if temporal_anomaly or age < 0:
        status, reason, public_age = "unavailable", "clock_anomaly", 0.0
    elif age <= context["policy"].fresh_max_age_seconds:
        status, reason, public_age = "fresh", "within_freshness_window", age
    elif age <= context["policy"].stale_max_age_seconds:
        status, reason, public_age = "stale", "within_stale_window", age
    else:
        status, reason, public_age = "unavailable", "age_exceeded", age
    return CurrentTrafficFreshness(
        status=status, reason=reason,
        evaluated_at_utc=context["evaluated_text"],
        observed_at=format_utc(oldest), newest_observed_at=format_utc(newest),
        age_seconds=public_age,
    )


def _snapshot(
    site: str,
    cycle: Mapping[str, Any],
    latest: Mapping[str, Any] | None,
    selected: str,
    reason: str,
    empty: bool,
    evaluated_text: str,
) -> CurrentTrafficSnapshot:
    latest_state, latest_result, latest_at = _latest_attempt(latest)
    using_previous = False
    if latest:
        cycle_key = (str(cycle["started_at"]), str(cycle["cycle_id"]))
        latest_key = (str(latest["started_at"]), str(latest["cycle_id"]))
        using_previous = latest_key > cycle_key and latest["cycle_id"] != cycle["cycle_id"]
    return CurrentTrafficSnapshot(
        source_kind="observation_ap_dynamic",
        site_id=site, cycle_id=str(cycle["cycle_id"]),
        started_at=str(cycle["started_at"]), finished_at=str(cycle["finished_at"]),
        complete=True, evaluated_at=evaluated_text,
        observed_at=None, newest_observed_at=None, age_seconds=None,
        source_skew_seconds=None, freshness_status="unavailable",
        freshness_reason="no_complete_snapshot", primary_source=PRIMARY_SOURCE,
        selected_source=selected, selection_reason=reason,
        empty_population=empty, latest_attempt_state=latest_state,
        latest_attempt_result=latest_result, latest_attempt_at=latest_at,
        using_previous_complete_snapshot=using_previous,
    )


def _no_snapshot(
    site: str,
    latest_row: Any,
    policy: CurrentTrafficFreshnessPolicy,
    evaluated_text: str,
) -> CurrentSiteTraffic:
    latest = dict(latest_row) if latest_row is not None else None
    latest_state, latest_result, latest_at = _latest_attempt(latest)
    snapshot = CurrentTrafficSnapshot(
        source_kind="observation_ap_dynamic",
        site_id=site, cycle_id=None, started_at=None, finished_at=None,
        complete=False, evaluated_at=evaluated_text,
        observed_at=None, newest_observed_at=None, age_seconds=None,
        source_skew_seconds=None, freshness_status="unavailable",
        freshness_reason="no_complete_snapshot",
        primary_source=PRIMARY_SOURCE, selected_source=None,
        selection_reason="no_complete_snapshot", empty_population=False,
        latest_attempt_state=latest_state, latest_attempt_result=latest_result,
        latest_attempt_at=latest_at, using_previous_complete_snapshot=False,
    )
    return CurrentSiteTraffic(
        snapshot=snapshot, freshness_policy=policy,
        source_selection=CurrentTrafficSourceSelection(
            PRIMARY_SOURCE, None, "no_complete_snapshot", 0, 0
        ),
        coverage=CurrentTrafficCoverage(
            "none", ("no_valid_rate",), False, 0, 0, 0, 0, 0, 0, 0, 0, 0,
            0, 0, 0, None, None, None,
        ),
        freshness=CurrentTrafficFreshness(
            "unavailable", "no_complete_snapshot", evaluated_text,
            None, None, None,
        ),
        traffic=CurrentTrafficTotals(None, None, None),
    )


def _latest_attempt(
    latest: Mapping[str, Any] | None,
) -> tuple[str, str | None, str | None]:
    if latest is None:
        return "none", None, None
    try:
        state = latest["state"]
        result = latest["result"]
        started_text = latest["started_at"]
        finished_text = latest["finished_at"]
    except KeyError as exc:
        raise CurrentTrafficSourceUnavailable(
            "Current traffic latest attempt is unavailable"
        ) from exc
    if not isinstance(state, str) or state not in _LATEST_STATES:
        raise CurrentTrafficSourceUnavailable(
            "Current traffic latest attempt is unavailable"
        )
    if result is not None and (
        not isinstance(result, str) or result not in _LATEST_RESULTS
    ):
        raise CurrentTrafficSourceUnavailable(
            "Current traffic latest attempt is unavailable"
        )
    try:
        started = parse_utc(started_text, "latest attempt started_at")
        finished = (
            parse_utc(finished_text, "latest attempt finished_at")
            if finished_text is not None else None
        )
    except AnalyticsQueryValidationError as exc:
        raise CurrentTrafficSourceUnavailable(
            "Current traffic latest attempt is unavailable"
        ) from exc
    valid_combination = (
        (state == "running" and result is None and finished is None)
        or (
            state == "completed" and result in _LATEST_RESULTS
            and finished is not None and finished >= started
        )
        or (state == "abandoned" and result is None and finished is None)
    )
    if not valid_combination:
        raise CurrentTrafficSourceUnavailable(
            "Current traffic latest attempt is unavailable"
        )
    attempt_at = finished_text if finished_text is not None else started_text
    return state, result, str(attempt_at)


def _site(value: Any) -> str:
    try:
        return require_site(value)
    except AnalyticsQueryValidationError as exc:
        raise CurrentTrafficValidationError("site_id is invalid") from exc


def _cycle_id(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 128:
        raise CurrentTrafficValidationError("cycle_id is invalid")
    return value.strip()


def _limit(value: Any) -> int:
    if type(value) is not int or not 1 <= value <= _MAX_PAGE_LIMIT:
        raise CurrentTrafficValidationError("limit must be between 1 and 250")
    return value


def _policy(fresh: Any, stale: Any, skew: Any) -> CurrentTrafficFreshnessPolicy:
    values: list[float] = []
    for value in (fresh, stale, skew):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise CurrentTrafficValidationError("traffic freshness policy is invalid")
        number = float(value)
        if not math.isfinite(number) or number < 0:
            raise CurrentTrafficValidationError("traffic freshness policy is invalid")
        values.append(number)
    if values[0] > values[1]:
        raise CurrentTrafficValidationError("traffic freshness policy is invalid")
    return CurrentTrafficFreshnessPolicy(*values)


def _evaluation(value: Any | None) -> tuple[datetime, str]:
    if value is None:
        now = datetime.now(UTC)
        return now, format_utc(now)
    try:
        parsed = parse_utc(value, "evaluated_at_utc")
    except AnalyticsQueryValidationError as exc:
        raise CurrentTrafficValidationError("evaluated_at_utc is invalid") from exc
    return parsed, str(value)


def _source_datetime(value: str) -> datetime:
    try:
        return parse_utc(value, "source observed_at")
    except AnalyticsQueryValidationError as exc:
        raise CurrentTrafficSourceUnavailable(
            "Current traffic timestamp is invalid"
        ) from exc


def _encode_cursor(site: str, cycle: str, source: str, mac: str) -> str:
    payload = {
        "cycle_id": cycle, "kind": _CURSOR_KIND, "last_ap_mac": mac,
        "selected_source": source, "site_id": site, "version": _CURSOR_VERSION,
    }
    raw = json.dumps(payload, ensure_ascii=True, allow_nan=False,
                     sort_keys=True, separators=(",", ":")).encode("ascii")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, str) or not value or len(value) > _MAX_CURSOR_LENGTH:
        raise CurrentTrafficValidationError("traffic cursor is malformed")
    try:
        raw = base64.b64decode(value + "=" * (-len(value) % 4),
                               altchars=b"-_", validate=True)
        payload = json.loads(raw.decode("ascii"))
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise CurrentTrafficValidationError("traffic cursor is malformed") from exc
    expected = {"version", "kind", "site_id", "cycle_id", "selected_source", "last_ap_mac"}
    if (
        not isinstance(payload, dict) or set(payload) != expected
        or type(payload["version"]) is not int
        or payload["version"] != _CURSOR_VERSION
        or not isinstance(payload["kind"], str)
        or payload["kind"] != _CURSOR_KIND
        or not isinstance(payload["selected_source"], str)
        or payload["selected_source"] not in SOURCES
        or not isinstance(payload["site_id"], str) or not payload["site_id"]
        or not isinstance(payload["cycle_id"], str) or not payload["cycle_id"]
        or not isinstance(payload["last_ap_mac"], str)
        or _MAC_PATTERN.fullmatch(payload["last_ap_mac"]) is None
        or _encode_cursor(payload["site_id"], payload["cycle_id"],
                          payload["selected_source"], payload["last_ap_mac"]) != value
    ):
        raise CurrentTrafficValidationError("traffic cursor is malformed")
    return payload
