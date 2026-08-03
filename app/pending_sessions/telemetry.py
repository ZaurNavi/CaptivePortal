from __future__ import annotations

from typing import Any

from app.auth_telemetry.service import AuthorizationTelemetry


class CleanerTelemetryAdapter:
    def __init__(self, telemetry: AuthorizationTelemetry):
        self._telemetry = telemetry

    def safe_emit_system(
        self,
        event: str,
        level: str = "info",
        **fields: Any,
    ) -> bool:
        try:
            return self._telemetry.safe_emit_system(
                event,
                level=level,
                component="pending_session_cleaner",
                **fields,
            )
        except Exception:
            return False
