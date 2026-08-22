"""Site-aware, permissions-ready read policy for Admin Web v1."""

from __future__ import annotations

from dataclasses import dataclass

from .config import SITE_ID_PATTERN
from .models import AdminPrincipal


READ_CAPABILITIES = frozenset(
    {
        "admin.read.context",
        "admin.read.overview",
        "admin.read.devices",
        "admin.read.device",
        "admin.read.visits",
        "admin.read.observations",
    }
)


class AdminSiteContextError(ValueError):
    pass


class AdminAccessDenied(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class AdminSiteContextResolver:
    allowed_site_ids: frozenset[str]
    default_site_id: str

    def resolve(self, site_id: object) -> str:
        if not isinstance(site_id, str) or SITE_ID_PATTERN.fullmatch(site_id) is None:
            raise AdminSiteContextError("invalid Site syntax")
        if site_id not in self.allowed_site_ids:
            raise AdminAccessDenied("Site is not allowed")
        return site_id

    def default(self) -> str:
        return self.resolve(self.default_site_id)


@dataclass(frozen=True, slots=True)
class AdminAccessPolicy:
    allowed_site_ids: frozenset[str]

    def authorize(
        self,
        principal: AdminPrincipal,
        capability: str,
        site_id: str,
    ) -> bool:
        return (
            isinstance(principal, AdminPrincipal)
            and principal.principal_type == "platform_operator"
            and capability in READ_CAPABILITIES
            and SITE_ID_PATTERN.fullmatch(site_id) is not None
            and site_id in self.allowed_site_ids
        )
