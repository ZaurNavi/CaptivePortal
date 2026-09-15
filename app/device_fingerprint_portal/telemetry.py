"""Sanitized counter/state-only Task-03 operational telemetry."""

from __future__ import annotations

import json
import logging
import math
from typing import Any

SAFE_FIELDS = frozenset({
    "runtime_state", "reason", "source_kind", "source_subtype", "status",
    "error_category", "http_status", "cooldown_seconds", "batch_size",
    "events_extracted", "events_partial", "events_queued", "events_coalesced",
    "drop_missing_mac", "drop_site_scope", "drop_ip_scope", "drop_ssid_scope",
    "drop_malformed", "drop_coalescer_busy", "drop_queue_full", "drop_queue_stale",
    "delivery_success", "delivery_transient", "delivery_permanent",
    "source_health_transition",
})


class PortalEvidenceTelemetry:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger("captivportal.device_fingerprint_portal")

    def emit(self, event: str, **fields: Any) -> None:
        try:
            payload: dict[str, Any] = {"event": str(event)[:128]}
            for key, value in fields.items():
                if key in SAFE_FIELDS and _safe(value):
                    payload[key] = value
            self.logger.info(
                "%s",
                json.dumps(payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")),
            )
        except Exception:
            return


def safe_emit(telemetry: Any, event: str, **fields: Any) -> None:
    try:
        if telemetry is not None:
            telemetry.emit(event, **fields)
    except Exception:
        return


def _safe(value: Any) -> bool:
    return (
        value is None
        or type(value) in {bool, int}
        or (isinstance(value, float) and math.isfinite(value))
        or (isinstance(value, str) and len(value) <= 128)
    )
