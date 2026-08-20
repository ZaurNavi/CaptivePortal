"""Safe summary-only telemetry for internal Analytics queries."""

from __future__ import annotations

import logging
from typing import Any


_ALLOWED_FIELDS = frozenset({
    "metric", "site_id", "duration_ms", "sample_size", "accepted_rows",
    "rejected_rows", "status", "reason", "quality_mode",
})


class AnalyticsTelemetry:
    def __init__(self, logger: logging.Logger | None = None):
        self._logger = logger or logging.getLogger("analytics")

    def emit(self, event: str, level: str = "info", **fields: Any) -> None:
        safe = {
            key: value for key, value in fields.items()
            if key in _ALLOWED_FIELDS
        }
        getattr(self._logger, level, self._logger.info)(
            "%s %s", event, safe
        )
