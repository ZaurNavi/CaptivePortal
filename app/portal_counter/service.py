"""Business rules for the Public Portal Open Counter."""

import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .exceptions import PortalCounterUnavailableError
from .models import CounterSnapshot, RecordOpenResult
from .repository import PortalCounterRepository


class PortalCounterService:
    def __init__(
        self,
        repository: PortalCounterRepository,
        timezone_name: str = "Asia/Baku",
        logger: logging.Logger | None = None,
    ):
        self.repository = repository
        self.timezone_name = timezone_name
        self.timezone: ZoneInfo | None = None
        self.logger = logger or logging.getLogger(__name__)
        self.available = False

    def initialize(self) -> bool:
        try:
            self.timezone = ZoneInfo(self.timezone_name)
            self.repository.migrate()
        except Exception:
            self.timezone = None
            self.available = False
            self.logger.exception(
                "portal_counter.initialization_failed"
            )
            return False

        self.available = True
        self.logger.info("portal_counter.migration_completed")
        return True

    def record_open(
        self,
        session_id: str,
        opened_at: datetime,
    ) -> RecordOpenResult:
        self._require_available()

        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id is required")

        utc_time = self._as_utc(opened_at)
        opened_day = utc_time.astimezone(
            self.timezone
        ).date().isoformat()
        result = self.repository.insert_open(
            session_id=session_id.strip(),
            opened_at=utc_time.isoformat(),
            opened_day=opened_day,
        )

        event = (
            "portal_counter.open_recorded"
            if result.recorded
            else "portal_counter.duplicate_ignored"
        )
        self.logger.info("%s session_id=%s", event, session_id)
        return result

    def get_snapshot(
        self,
        now: datetime | None = None,
    ) -> CounterSnapshot:
        self._require_available()

        utc_now = self._as_utc(
            now or datetime.now(timezone.utc)
        )
        day = utc_now.astimezone(
            self.timezone
        ).date().isoformat()

        opened_today, opened_total = (
            self.repository.get_counts(day)
        )

        return CounterSnapshot(
            opened_today=opened_today,
            opened_total=opened_total,
            day=day,
            timezone=self.timezone_name,
        )

    def _require_available(self) -> None:
        if not self.available or self.timezone is None:
            raise PortalCounterUnavailableError(
                "Portal counter storage is unavailable"
            )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if not isinstance(value, datetime):
            raise TypeError("datetime value is required")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime must be timezone-aware")
        return value.astimezone(timezone.utc)
