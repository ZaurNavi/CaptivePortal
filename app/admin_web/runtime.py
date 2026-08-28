"""Fail-open composition boundary for the process-local Admin Web runtime."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping

from .config import AdminWebConfig, AdminWebConfigError, admin_web_config_from_settings
from .policy import AdminAccessPolicy, AdminSiteContextResolver
from .rate_limit import AdminLoginRateLimiter
from .stores import AdminPreAuthCsrfStore, AdminSessionStore
from .home_activity_config import (
    HomeActivityConfig,
    HomeActivityConfigError,
    home_activity_config_from_settings,
)
from .home_health import HomeHealthReadService
from .home_health_config import (
    HomeHealthConfig,
    HomeHealthConfigError,
    home_health_config_from_settings,
)
from .home_ap_24h_config import (
    HomeAp24Config,
    HomeAp24ConfigError,
    home_ap_24h_config_from_settings,
)


@dataclass(slots=True)
class AdminWebRuntime:
    state: str
    config: AdminWebConfig | None = None
    session_store: AdminSessionStore | None = None
    preauth_store: AdminPreAuthCsrfStore | None = None
    rate_limiter: AdminLoginRateLimiter | None = None
    access_policy: AdminAccessPolicy | None = None
    site_resolver: AdminSiteContextResolver | None = None
    query_service: Any | None = None
    query_execution_controls: Any | None = None
    home_activity_config: HomeActivityConfig | None = None
    home_activity_state: str = "disabled"
    home_health_config: HomeHealthConfig | None = None
    home_health_state: str = "disabled"
    home_health_service: HomeHealthReadService | None = None
    home_health_query_service: Any | None = None
    home_ap_24h_config: HomeAp24Config | None = None
    home_ap_24h_state: str = "disabled"
    home_ap_24h_service: Any | None = None
    blueprint: Any | None = None

    def clear(self) -> None:
        if self.session_store is not None:
            self.session_store.clear()
        if self.preauth_store is not None:
            self.preauth_store.clear()
        if self.rate_limiter is not None:
            self.rate_limiter.clear()


def create_admin_web_runtime(
    settings: Mapping[str, Any],
    analytics_runtime: Any,
    registry_read_service: Any,
    visit_read_service: Any,
    observation_read_service: Any,
    logger: logging.Logger,
    *,
    current_state_read_service: Any | None = None,
    authorization_health_tracker: Any | None = None,
    current_state_runtime: Any | None = None,
    observation_runtime: Any | None = None,
    visit_runtime: Any | None = None,
) -> AdminWebRuntime:
    """Create Admin security state without mutating or querying data sources."""
    try:
        config = admin_web_config_from_settings(settings)
    except AdminWebConfigError:
        logger.exception("admin.runtime_configuration_failed")
        return AdminWebRuntime(state="unavailable")
    if not config.enabled:
        return AdminWebRuntime(state="disabled", config=config)

    sessions = AdminSessionStore(
        max_sessions=config.max_sessions,
        idle_seconds=config.session_idle_seconds,
        absolute_seconds=config.session_absolute_seconds,
    )
    preauth = AdminPreAuthCsrfStore(
        max_states=config.max_preauth_states,
        ttl_seconds=config.preauth_csrf_ttl_seconds,
    )
    limiter = AdminLoginRateLimiter(
        window_seconds=config.login_window_seconds,
        max_failures=config.login_max_failures,
        lock_seconds=config.login_lock_seconds,
        max_trackers=config.max_login_trackers,
    )
    source_ready = all(
        source is not None
        for source in (
            registry_read_service,
            visit_read_service,
            observation_read_service,
        )
    )
    activity_requested = settings.get(
        "web_admin_home_activity_enabled", "false"
    ) in (True, "true")
    current_state_config = (
        getattr(current_state_read_service, "config", None)
        if activity_requested
        else None
    )
    try:
        activity_config = home_activity_config_from_settings(
            settings,
            admin_config=config,
            current_state_config=current_state_config,
        )
        activity_state = "active" if activity_config.enabled else "disabled"
    except HomeActivityConfigError as exc:
        activity_config = None
        activity_state = "unavailable"
        logger.error(
            "admin.home_activity_configuration_failed",
            extra={
                "event": "admin.home_activity_configuration_failed",
                "reason": exc.reason,
            },
            exc_info=True,
        )
    try:
        health_config = home_health_config_from_settings(
            settings, admin_config=config
        )
        health_state = "active" if health_config.enabled else "disabled"
    except HomeHealthConfigError:
        health_config = None
        health_state = "unavailable"
        logger.error(
            "admin.home_health_configuration_failed",
            extra={
                "event": "admin.home_health_configuration_failed",
                "failure_category": "configuration_error",
            },
        )
    try:
        ap24_config = home_ap_24h_config_from_settings(
            settings, admin_config=config
        )
        ap24_state = "active" if ap24_config.enabled else "disabled"
    except HomeAp24ConfigError:
        ap24_config = None
        ap24_state = "unavailable"
        logger.error(
            "admin.home_ap_24h_configuration_failed",
            extra={
                "event": "admin.home_ap_24h_configuration_failed",
                "failure_category": "configuration_error",
            },
        )
    ap24_service = None
    if ap24_config is not None and ap24_config.enabled:
        try:
            from app.analytics.home_ap_24h import HomeAp24ReadService

            ap24_service = HomeAp24ReadService(
                current_state_read_service,
                observation_read_service,
                current_state_ap_interval_seconds=int(
                    settings.get("current_state_ap_interval_seconds", 60)
                ),
                quality_gap_seconds=int(
                    settings.get("analytics_quality_gap_threshold_seconds", 180)
                ),
                observation_dynamic_max_requests=int(
                    settings.get("observation_ap_dynamic_max_requests_per_cycle", 200)
                ),
            )
        except (TypeError, ValueError, AttributeError):
            ap24_state = "unavailable"
            logger.error(
                "admin.home_ap_24h_composition_failed",
                extra={
                    "event": "admin.home_ap_24h_composition_failed",
                    "failure_category": "composition_error",
                },
            )
    health_service = None
    if health_config is not None and health_config.enabled:
        try:
            health_service = HomeHealthReadService(
                allowed_site_ids=config.allowed_site_ids,
                auth_tracker=authorization_health_tracker,
                current_state_runtime=current_state_runtime,
                observation_runtime=observation_runtime,
                visit_runtime=visit_runtime,
                analytics_runtime=analytics_runtime,
                auth_evidence_max_age_seconds=(
                    health_config.auth_evidence_max_age_seconds
                ),
                home_traffic_enabled=config.home_traffic_enabled,
                home_activity_enabled=activity_requested,
                logger=logger,
            )
        except Exception:
            health_state = "unavailable"
            logger.error(
                "admin.home_health_composition_failed",
                extra={
                    "event": "admin.home_health_composition_failed",
                    "failure_category": "composition_error",
                },
            )
    from .query_service import (
        AdminHomeHealthQueryService,
        AdminQueryExecutionControls,
    )

    policy = AdminAccessPolicy(config.allowed_site_ids)
    execution_controls = AdminQueryExecutionControls(
        max_concurrent_queries=config.max_concurrent_queries,
        max_query_duration_seconds=config.max_query_duration_seconds,
    )
    health_query_service = (
        AdminHomeHealthQueryService(
            policy=policy,
            read_service=health_service,
            execution_controls=execution_controls,
        )
        if health_service is not None
        else None
    )
    query_service = None
    if getattr(analytics_runtime, "state", None) == "active" and source_ready:
        query_service = _query_service(
            config,
            analytics_runtime,
            registry_read_service,
            visit_read_service,
            observation_read_service,
            current_state_read_service,
            activity_config,
            ap24_service,
            execution_controls,
        )
    runtime = AdminWebRuntime(
        state=(
            "active"
            if query_service is not None
            else "unavailable"
        ),
        config=config,
        session_store=sessions,
        preauth_store=preauth,
        rate_limiter=limiter,
        access_policy=policy,
        site_resolver=AdminSiteContextResolver(
            config.allowed_site_ids,
            config.default_site_id,
        ),
        query_service=query_service,
        query_execution_controls=execution_controls,
        home_activity_config=activity_config,
        home_activity_state=activity_state,
        home_health_config=health_config,
        home_health_state=health_state,
        home_health_service=health_service,
        home_health_query_service=health_query_service,
        home_ap_24h_config=ap24_config,
        home_ap_24h_state=ap24_state,
        home_ap_24h_service=ap24_service,
    )
    from .routes import create_admin_web_blueprint

    runtime.blueprint = create_admin_web_blueprint(runtime, logger=logger)
    return runtime


def _query_service(
    config: AdminWebConfig,
    analytics_runtime: Any,
    registry_read_service: Any,
    visit_read_service: Any,
    observation_read_service: Any,
    current_state_read_service: Any | None = None,
    home_activity_config: HomeActivityConfig | None = None,
    home_ap_24h_service: Any | None = None,
    execution_controls: Any | None = None,
):
    """Build 01B only when concrete read boundaries expose local paths."""
    try:
        registry_repository = registry_read_service.repository
        visit_repository = visit_read_service.repository
        observation_repository = observation_read_service._repository  # noqa: SLF001
        analytics_service = analytics_runtime.visit_service
        from .device_gateway import AdminDeviceReadGateway
        from .query_service import AdminQueryService
        from .read_gateway import AdminSqlReadGateway

        policy = AdminAccessPolicy(config.allowed_site_ids)
        return AdminQueryService(
            config=config,
            policy=policy,
            device_gateway=AdminDeviceReadGateway(
                registry_repository.config.db_path,
                visit_repository.db_path,
            ),
            read_gateway=AdminSqlReadGateway(
                visit_repository.db_path,
                observation_repository.db_path,
            ),
            visit_analytics_service=analytics_service,
            current_state_read_service=current_state_read_service,
            current_traffic_read_service=getattr(
                analytics_runtime, "current_traffic_service", None
            ),
            home_activity_read_service=getattr(
                analytics_runtime, "home_activity_service", None
            ),
            home_activity_config=home_activity_config,
            home_ap_24h_read_service=home_ap_24h_service,
            execution_controls=execution_controls,
        )
    except (AttributeError, TypeError):
        return None
