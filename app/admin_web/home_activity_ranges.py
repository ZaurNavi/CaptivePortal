"""Server-authoritative Home Activity calendar and DST resolution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from app.analytics.validation import format_utc

from .home_activity_config import HomeActivitySiteContext


PRESETS = frozenset({
    "last_24h", "yesterday", "last_48h", "last_7d",
    "current_month", "last_30d", "custom",
})
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_TIME = re.compile(r"\d{2}:\d{2}(?::\d{2})?")


class HomeActivityRangeError(ValueError):
    """The requested local or preset range is invalid."""


@dataclass(frozen=True, slots=True)
class ResolvedActivityRange:
    kind: str
    requested: Mapping[str, Any]
    from_utc: datetime
    to_utc: datetime
    from_local: datetime
    to_local_exclusive: datetime
    timezone: str

    def public_range(self) -> dict[str, Any]:
        return {
            "requested": dict(self.requested),
            "resolved": {
                "from_utc": format_utc(self.from_utc),
                "to_utc": format_utc(self.to_utc),
                "from_local": self.from_local.isoformat(timespec="seconds"),
                "to_local_exclusive": self.to_local_exclusive.isoformat(
                    timespec="seconds"
                ),
                "timezone": self.timezone,
            },
        }


def resolve_today(
    context: HomeActivitySiteContext,
    evaluated_at: datetime,
) -> ResolvedActivityRange:
    evaluated = _utc(evaluated_at)
    zone = ZoneInfo(context.timezone)
    local_now = evaluated.astimezone(zone)
    start_local = _strict_local(local_now.date(), None, zone)
    return _resolved(
        "today", {"kind": "today"}, start_local, local_now, evaluated, context
    )


def resolve_selected(
    context: HomeActivitySiteContext,
    parameters: Mapping[str, str | None],
    evaluated_at: datetime,
) -> ResolvedActivityRange:
    evaluated = _utc(evaluated_at)
    period = parameters.get("period")
    if period not in PRESETS:
        raise HomeActivityRangeError("period is invalid")
    if period == "custom":
        return resolve_custom(context, parameters, evaluated, reject_future=True)
    if any(key != "period" for key in parameters):
        raise HomeActivityRangeError("preset parameters are invalid")
    zone = ZoneInfo(context.timezone)
    local_now = evaluated.astimezone(zone)
    if period in {"last_24h", "last_48h", "last_7d", "last_30d"}:
        hours = {"last_24h": 24, "last_48h": 48, "last_7d": 168,
                 "last_30d": 720}[period]
        start_utc = evaluated - timedelta(hours=hours)
        return _resolved(
            period, {"kind": "preset", "period": period},
            start_utc.astimezone(zone), local_now, evaluated, context,
        )
    if period == "yesterday":
        end_local = _strict_local(local_now.date(), None, zone)
        start_local = _strict_local(local_now.date() - timedelta(days=1), None, zone)
        return _resolved(
            period, {"kind": "preset", "period": period},
            start_local, end_local, evaluated, context,
        )
    start_local = _strict_local(local_now.date().replace(day=1), None, zone)
    return _resolved(
        period, {"kind": "preset", "period": period},
        start_local, local_now, evaluated, context,
    )


def resolve_custom(
    context: HomeActivitySiteContext,
    parameters: Mapping[str, str | None],
    evaluated_at: datetime,
    *,
    reject_future: bool,
) -> ResolvedActivityRange:
    allowed = {"period", "from_date", "from_time", "to_date", "to_time"}
    if any(key not in allowed for key in parameters):
        raise HomeActivityRangeError("custom parameters are invalid")
    if parameters.get("period") not in {None, "custom"}:
        raise HomeActivityRangeError("period is invalid")
    from_date = _parse_date(parameters.get("from_date"))
    to_date = _parse_date(parameters.get("to_date"))
    from_time = _parse_time(parameters.get("from_time"))
    to_time = _parse_time(parameters.get("to_time"))
    zone = ZoneInfo(context.timezone)
    start_local = _strict_local(from_date, from_time, zone)
    if to_time is None:
        end_local = _strict_local(to_date + timedelta(days=1), None, zone)
    else:
        end_local = _strict_local(to_date, to_time, zone)
    requested = {
        "kind": "custom",
        "from_date": from_date.isoformat(),
        "from_time": None if from_time is None else from_time.isoformat(),
        "to_date": to_date.isoformat(),
        "to_time": None if to_time is None else to_time.isoformat(),
        "to_date_inclusive": to_time is None,
    }
    result = _resolved(
        "custom", requested, start_local, end_local, _utc(evaluated_at), context
    )
    if reject_future and result.to_utc > _utc(evaluated_at):
        raise HomeActivityRangeError("range end is in the future")
    return result


def next_site_midnight_utc(
    context: HomeActivitySiteContext,
    evaluated_at: datetime,
) -> str:
    zone = ZoneInfo(context.timezone)
    next_date = _utc(evaluated_at).astimezone(zone).date() + timedelta(days=1)
    return format_utc(_strict_local(next_date, None, zone).astimezone(timezone.utc))


def _resolved(kind, requested, start_local, end_local, evaluated, context):
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    if start_utc >= end_utc:
        raise HomeActivityRangeError("range must be non-empty")
    return ResolvedActivityRange(
        kind, requested, start_utc, end_utc, start_local, end_local,
        context.timezone,
    )


def _strict_local(day: date, value: time | None, zone: ZoneInfo) -> datetime:
    naive = datetime.combine(day, value or time())
    candidates: dict[datetime, datetime] = {}
    for fold in (0, 1):
        local = naive.replace(tzinfo=zone, fold=fold)
        instant = local.astimezone(timezone.utc)
        round_trip = instant.astimezone(zone)
        if round_trip.replace(tzinfo=None) == naive:
            candidates[instant] = local
    if len(candidates) != 1:
        raise HomeActivityRangeError(
            "local time is nonexistent or ambiguous"
        )
    return next(iter(candidates.values()))


def _parse_date(value: Any) -> date:
    if not isinstance(value, str) or _DATE.fullmatch(value) is None:
        raise HomeActivityRangeError("date is invalid")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise HomeActivityRangeError("date is invalid") from exc
    if parsed.isoformat() != value:
        raise HomeActivityRangeError("date is invalid")
    return parsed


def _parse_time(value: Any) -> time | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str) or _TIME.fullmatch(value) is None:
        raise HomeActivityRangeError("time is invalid")
    try:
        parsed = time.fromisoformat(value)
    except ValueError as exc:
        raise HomeActivityRangeError("time is invalid") from exc
    if parsed.microsecond or parsed.tzinfo is not None:
        raise HomeActivityRangeError("time is invalid")
    expected = parsed.isoformat(timespec="minutes" if len(value) == 5 else "seconds")
    if expected != value:
        raise HomeActivityRangeError("time is invalid")
    return parsed


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise HomeActivityRangeError("evaluation time is invalid")
    return value.astimezone(timezone.utc)
