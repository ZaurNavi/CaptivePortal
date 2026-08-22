"""Secure Site-aware Admin Web foundation."""

from .config import AdminWebConfig, AdminWebConfigError, admin_web_config_from_settings
from .models import AdminPrincipal, AdminSession
from .policy import AdminAccessPolicy, AdminSiteContextResolver
from .rate_limit import AdminLoginRateLimiter
from .query_service import AdminQueryService
from .runtime import AdminWebRuntime, create_admin_web_runtime
from .stores import AdminPreAuthCsrfStore, AdminSessionStore

__all__ = [
    "AdminAccessPolicy",
    "AdminLoginRateLimiter",
    "AdminQueryService",
    "AdminPreAuthCsrfStore",
    "AdminPrincipal",
    "AdminSession",
    "AdminSessionStore",
    "AdminSiteContextResolver",
    "AdminWebConfig",
    "AdminWebConfigError",
    "AdminWebRuntime",
    "admin_web_config_from_settings",
    "create_admin_web_runtime",
]
