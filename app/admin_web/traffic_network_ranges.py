"""Server-owned product ranges for Network Traffic panels."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.analytics.validation import format_utc


UTC = timezone.utc


class TrafficNetworkRangeError(ValueError):
    """The requested product range is not part of the public contract."""


@dataclass(frozen=True, slots=True)
class TrafficNetworkRange:
    id: str
    from_utc: str
    to_utc: str
    evaluated_at_utc: str


_RANGES = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
}


def resolve_traffic_network_range(
    range_id: str, evaluated_at: datetime
) -> TrafficNetworkRange:
    """Resolve a bounded range from one captured server UTC instant."""
    if not isinstance(range_id, str) or range_id not in _RANGES:
        raise TrafficNetworkRangeError("range is invalid")
    if not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None:
        raise TrafficNetworkRangeError("evaluation instant is invalid")
    evaluated = evaluated_at.astimezone(UTC)
    duration = _RANGES[range_id]
    end = format_utc(evaluated)
    return TrafficNetworkRange(
        id=range_id,
        from_utc=format_utc(evaluated - duration),
        to_utc=end,
        evaluated_at_utc=end,
    )
