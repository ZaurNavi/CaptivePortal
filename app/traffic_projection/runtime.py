"""Fail-open composition for the separately activated projection worker."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping

from .config import traffic_projection_config_from_settings
from .models import TrafficProjectionConfig
from .service import TrafficProjectionService


@dataclass(slots=True)
class TrafficProjectionRuntime:
    state: str
    config: TrafficProjectionConfig | None
    service: TrafficProjectionService | None

    def health_payload(self, site_id: str | None = None) -> Mapping[str, Any]:
        if self.state != "active" or self.service is None or site_id is None:
            return {"state": self.state}
        return {"state": self.state, "projection": self.service.health(site_id)}


def create_traffic_projection_runtime(
    settings: Mapping[str, Any], logger: logging.Logger
) -> TrafficProjectionRuntime:
    try:
        config = traffic_projection_config_from_settings(settings)
    except Exception:
        logger.error("traffic_projection_runtime_unavailable error_category=configuration")
        return TrafficProjectionRuntime("unavailable", None, None)
    if not config.enabled:
        return TrafficProjectionRuntime("disabled", config, None)
    try:
        service = TrafficProjectionService(config, logger=logger)
        service.initialize()
        return TrafficProjectionRuntime("active", config, service)
    except Exception:
        logger.error("traffic_projection_runtime_unavailable error_category=storage")
        return TrafficProjectionRuntime("unavailable", config, None)
