"""Validation, time rules and public representation for traffic data."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable
from zoneinfo import ZoneInfo

from .models import (
    INT64_MAX,
    ClassifiedRecord,
    PublicTrafficConfig,
    ResetSummary,
    TrafficEvent,
    TrafficSnapshot,
)
from .repository import PublicTrafficRepository


Clock = Callable[[], datetime]


class PublicTrafficService:
    def __init__(
        self,
        *,
        config: PublicTrafficConfig,
        repository: PublicTrafficRepository,
        logger: logging.Logger,
        clock: Clock | None = None,
    ):
        self.config = config
        self.repository = repository
        self.logger = logger
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.timezone: ZoneInfo | None = None
        self.available = False
        self.ssid = config.ssid
        self.frontend_refresh_seconds = (
            config.frontend_refresh_seconds
        )

    def initialize(self) -> bool:
        try:
            self.timezone = ZoneInfo(self.config.timezone_name)
        except Exception:
            self.timezone = None
            self.available = False
            self.logger.exception(
                "public_traffic_configuration_error"
            )
            return False
        try:
            self.repository.migrate(self.now_iso())
        except Exception:
            self.available = False
            self.logger.exception("public_traffic_database_error")
            return False
        self.available = True
        return True

    def classify_record(
        self,
        record: dict[str, Any],
    ) -> ClassifiedRecord:
        if record.get("event") != "omada.client_offline":
            return ClassifiedRecord(target=False)

        raw_event_id = record.get("normalized_event_id")
        if not isinstance(raw_event_id, str) or not raw_event_id.strip():
            return ClassifiedRecord(
                target=True,
                warning_code="missing_normalized_event_id",
            )
        event_id = raw_event_id.strip()

        raw_ssid = record.get("ssid")
        ssid = (
            raw_ssid
            if isinstance(raw_ssid, str) and raw_ssid.strip()
            else None
        )
        raw_traffic = record.get(
            "reported_traffic_bytes_estimate"
        )
        traffic = (
            raw_traffic
            if (
                type(raw_traffic) is int
                and 0 <= raw_traffic <= INT64_MAX
            )
            else None
        )

        event_time, timestamp_fallback = self._event_time(record)
        local_date = event_time.astimezone(
            self._require_timezone()
        ).date().isoformat()

        skip_reason = None
        if ssid is None:
            skip_reason = "missing_ssid"
        elif traffic is None:
            skip_reason = "invalid_traffic_value"

        return ClassifiedRecord(
            target=True,
            event=TrafficEvent(
                normalized_event_id=event_id,
                ssid=ssid,
                local_date=local_date,
                traffic_bytes=traffic,
                skip_reason=skip_reason,
            ),
            warning_code=skip_reason,
            timestamp_fallback=timestamp_fallback,
        )

    def get_snapshot(
        self,
        now: datetime | None = None,
    ) -> TrafficSnapshot:
        if not self.available:
            return TrafficSnapshot(
                available=False,
                ssid=self.ssid,
            )
        local_date = self.local_date(now)
        return self.repository.get_snapshot(
            ssid=self.ssid,
            local_date=local_date,
        )

    def snapshot_payload(
        self,
        snapshot: TrafficSnapshot | None = None,
    ) -> dict[str, Any]:
        snapshot = snapshot or self.get_snapshot()
        if not snapshot.available:
            return {
                "available": False,
                "ssid": snapshot.ssid,
            }
        return {
            "available": True,
            "ssid": snapshot.ssid,
            "today_bytes": snapshot.today_bytes,
            "today_display": format_traffic_bytes(
                snapshot.today_bytes
            ),
            "total_bytes": snapshot.total_bytes,
            "total_display": format_traffic_bytes(
                snapshot.total_bytes
            ),
            "completed_sessions_today": (
                snapshot.completed_sessions_today
            ),
            "completed_sessions_total": (
                snapshot.completed_sessions_total
            ),
            "updated_at": snapshot.updated_at,
        }

    def reset(
        self,
        *,
        ssid: str | None,
        before_commit: Callable[[], None] | None = None,
    ) -> ResetSummary:
        return self.repository.reset(
            ssid=ssid,
            local_date=self.local_date(),
            reset_at=self.now_iso(),
            before_commit=before_commit,
        )

    def local_date(self, now: datetime | None = None) -> str:
        value = self._as_utc(now or self.clock())
        return value.astimezone(
            self._require_timezone()
        ).date().isoformat()

    def now_iso(self) -> str:
        return _format_utc(self._as_utc(self.clock()))

    def _event_time(
        self,
        record: dict[str, Any],
    ) -> tuple[datetime, bool]:
        local_timezone = self._require_timezone()
        controller = _parse_timestamp(
            record.get("controller_timestamp"),
            local_timezone,
        )
        if controller is not None:
            return controller, False
        received = _parse_timestamp(
            record.get("received_at"),
            local_timezone,
        )
        if received is not None:
            return received, False
        return self._as_utc(self.clock()), True

    def _require_timezone(self) -> ZoneInfo:
        if self.timezone is None:
            raise RuntimeError("Public traffic service is unavailable")
        return self.timezone

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if not isinstance(value, datetime):
            raise TypeError("clock must return datetime")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime must be timezone-aware")
        return value.astimezone(timezone.utc)


class UnavailablePublicTrafficService:
    """Fail-safe API surface when traffic configuration is invalid."""

    available = False

    def __init__(
        self,
        *,
        ssid: str = "",
        frontend_refresh_seconds: int = 60,
    ):
        self.ssid = ssid if isinstance(ssid, str) else ""
        self.frontend_refresh_seconds = frontend_refresh_seconds

    def get_snapshot(self) -> TrafficSnapshot:
        return TrafficSnapshot(available=False, ssid=self.ssid)

    def snapshot_payload(
        self,
        snapshot: TrafficSnapshot | None = None,
    ) -> dict[str, Any]:
        return {
            "available": False,
            "ssid": self.ssid,
        }


def format_traffic_bytes(value: int) -> str:
    if type(value) is not int or not 0 <= value <= INT64_MAX:
        raise ValueError("traffic bytes must be an INT64 integer")
    if value < 1024**3:
        amount = (
            Decimal(value) / Decimal(1024**2)
        ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return f"{amount} MB"
    if value < 1024**4:
        amount = (
            Decimal(value) / Decimal(1024**3)
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return f"{_trim_decimal(amount)} GB"
    amount = (
        Decimal(value) / Decimal(1024**4)
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{_trim_decimal(amount)} TB"


def _trim_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _parse_timestamp(
    value: Any,
    local_timezone: ZoneInfo,
) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        normalized = parsed.astimezone(timezone.utc)
        normalized.astimezone(local_timezone)
    except (ValueError, OverflowError, OSError):
        return None
    return normalized


def _format_utc(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )
