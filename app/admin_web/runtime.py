"""Fail-open composition boundary for the process-local Admin Web runtime."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping

from .config import AdminWebConfig, AdminWebConfigError, admin_web_config_from_settings
from .policy import AdminAccessPolicy, AdminSiteContextResolver
from .rate_limit import AdminLoginRateLimiter
from .stores import AdminPreAuthCsrfStore, AdminSessionStore


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
    query_service = None
    if getattr(analytics_runtime, "state", None) == "active" and source_ready:
        query_service = _query_service(
            config,
            analytics_runtime,
            registry_read_service,
            visit_read_service,
            observation_read_service,
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
        access_policy=AdminAccessPolicy(config.allowed_site_ids),
        site_resolver=AdminSiteContextResolver(
            config.allowed_site_ids,
            config.default_site_id,
        ),
        query_service=query_service,
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
        )
    except (AttributeError, TypeError):
        return None
