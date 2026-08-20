"""Fail-open production composition for the demand-only Analytics API."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping

from app.observations.read_service import ObservationReadService

from .api_config import (
    AnalyticsApiConfig,
    AnalyticsApiConfigError,
    analytics_api_config_from_settings,
)
from .config import AnalyticsConfig, AnalyticsConfigError, analytics_config_from_settings
from .read_service import AnalyticsReadService
from .source_gateway import AnalyticsSourceGateway, SOURCE_SCHEMA_VERSIONS
from .telemetry import AnalyticsTelemetry
from .visits import VisitAnalyticsService
from .wireless import WirelessAnalyticsService


@dataclass(frozen=True, slots=True)
class SourceBoundaryHealth:
    available: bool
    expected_schema_version: int
    actual_schema_version: int | None
    query_only: bool

    def safe_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "expected_schema_version": self.expected_schema_version,
            "actual_schema_version": self.actual_schema_version,
            "query_only": self.query_only,
        }


class AnalyticsRuntime:
    """Composition-owned runtime without a background thread or write path."""

    def __init__(
        self,
        *,
        state: str,
        config: AnalyticsConfig | None,
        api_config: AnalyticsApiConfig | None,
        source_health: Mapping[str, SourceBoundaryHealth] | None = None,
        source_services: Mapping[str, Any] | None = None,
        quality_service: AnalyticsReadService | None = None,
        wireless_service: WirelessAnalyticsService | None = None,
        visit_service: VisitAnalyticsService | None = None,
        logger: logging.Logger,
        register_routes: bool = False,
    ):
        self.state = state
        self.config = config
        self.api_config = api_config
        self.source_health = dict(source_health or {})
        self._source_services = dict(source_services or {})
        self.quality_service = quality_service
        self.wireless_service = wireless_service
        self.visit_service = visit_service
        self.blueprint = None
        if register_routes and api_config is not None:
            from .api import create_analytics_blueprint

            self.blueprint = create_analytics_blueprint(self, logger=logger)

    def health_payload(self) -> dict[str, Any]:
        config = self.config
        return {
            "state": self.state,
            "modules": {
                "quality": bool(config and config.enabled),
                "wireless": bool(config and config.wireless_enabled),
                "visits": bool(config and config.visit_enabled),
            },
            "sources": {
                name: item.safe_dict()
                for name, item in sorted(self.source_health.items())
            },
        }

    def live_health_payload(self) -> tuple[bool, dict[str, Any]]:
        """Recheck source boundaries without reading rows or mutating sources."""
        if not self._source_services:
            return self.state == "active", self.health_payload()
        self.source_health = {
            name: _check_source(name, service)
            for name, service in self._source_services.items()
        }
        sources_healthy = all(
            item.available for item in self.source_health.values()
        )
        services_ready = (
            self.state == "active"
            and self.quality_service is not None
            and self.wireless_service is not None
            and self.visit_service is not None
        )
        healthy = sources_healthy and services_ready
        payload = self.health_payload()
        payload["state"] = "active" if healthy else "unavailable"
        return healthy, payload


def create_analytics_runtime(
    settings: Mapping[str, Any],
    observation_runtime: Any,
    visit_runtime: Any,
    registry_read_service: Any,
    logger: logging.Logger,
) -> AnalyticsRuntime:
    """Create Analytics from existing read boundaries; never initialize them."""
    try:
        api_config = analytics_api_config_from_settings(settings)
    except AnalyticsApiConfigError:
        _event(logger, "analytics.api_runtime_unavailable", "configuration_error")
        return AnalyticsRuntime(
            state="unavailable",
            config=None,
            api_config=None,
            logger=logger,
        )

    try:
        analytics_config = analytics_config_from_settings(settings)
    except AnalyticsConfigError:
        if not api_config.enabled:
            return AnalyticsRuntime(
                state="disabled",
                config=None,
                api_config=api_config,
                logger=logger,
            )
        _event(logger, "analytics.api_runtime_unavailable", "metric_configuration_error")
        return AnalyticsRuntime(
            state="unavailable",
            config=None,
            api_config=api_config,
            logger=logger,
            register_routes=True,
        )

    if not analytics_config.enabled or not api_config.enabled:
        return AnalyticsRuntime(
            state="disabled",
            config=analytics_config,
            api_config=api_config,
            logger=logger,
        )

    observation_read = _observation_read_service(observation_runtime)
    visit_read = _visit_read_service(visit_runtime)
    sources = {
        "observations": observation_read,
        "visits": visit_read,
        "registry": registry_read_service,
    }
    source_health = {
        name: _check_source(name, service)
        for name, service in sources.items()
    }
    if not all(item.available for item in source_health.values()):
        _event(logger, "analytics.api_runtime_unavailable", "source_unavailable")
        return AnalyticsRuntime(
            state="unavailable",
            config=analytics_config,
            api_config=api_config,
            source_health=source_health,
            source_services=sources,
            logger=logger,
            register_routes=True,
        )

    gateway = AnalyticsSourceGateway(
        observation_read,
        visit_read,
        registry_read_service,
    )
    telemetry = AnalyticsTelemetry(logger)
    runtime = AnalyticsRuntime(
        state="active",
        config=analytics_config,
        api_config=api_config,
        source_health=source_health,
        source_services=sources,
        quality_service=AnalyticsReadService(
            analytics_config, gateway, telemetry=telemetry
        ),
        wireless_service=WirelessAnalyticsService(
            analytics_config, gateway, telemetry=telemetry
        ),
        visit_service=VisitAnalyticsService(
            analytics_config, gateway, telemetry=telemetry
        ),
        logger=logger,
        register_routes=True,
    )
    _event(logger, "analytics.api_runtime_active")
    return runtime


def _observation_read_service(runtime: Any) -> Any | None:
    if getattr(runtime, "state", None) not in {"active", "degraded"}:
        return None
    repository = getattr(runtime, "repository", None)
    return ObservationReadService(repository) if repository is not None else None


def _visit_read_service(runtime: Any) -> Any | None:
    if getattr(runtime, "state", None) not in {"active", "degraded"}:
        return None
    return getattr(runtime, "read_service", None)


def _check_source(name: str, service: Any | None) -> SourceBoundaryHealth:
    expected = SOURCE_SCHEMA_VERSIONS[name]
    if service is None or not hasattr(service, "analytics_read_connection"):
        return SourceBoundaryHealth(False, expected, None, False)
    try:
        with service.analytics_read_connection() as connection:
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            query_only = bool(
                int(connection.execute("PRAGMA query_only").fetchone()[0])
            )
    except Exception:
        return SourceBoundaryHealth(False, expected, None, False)
    return SourceBoundaryHealth(
        version == expected and query_only,
        expected,
        version,
        query_only,
    )


def _event(
    logger: logging.Logger,
    event: str,
    category: str | None = None,
) -> None:
    fields = {} if category is None else {"failure_category": category}
    level = logger.info if category is None else logger.warning
    level("%s %s", event, fields)
