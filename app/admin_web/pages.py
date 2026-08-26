"""Pure presentation helpers for the read-only Admin UI."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from flask import Response, make_response, render_template


@dataclass(frozen=True, slots=True)
class AdminPage:
    key: str
    title: str
    template: str


HOME = AdminPage("home", "Overview", "admin/home.html")
DEVICES = AdminPage("devices", "Devices", "admin/devices.html")
DEVICE = AdminPage("device", "Device details", "admin/device.html")
VISITS = AdminPage("visits", "Visits", "admin/visits.html")
OBSERVATIONS = AdminPage(
    "observations", "Observations", "admin/observations.html"
)


def render_admin_page(
    page: AdminPage,
    *,
    site_id: str,
    username: str,
    csrf_token: str,
    runtime_state: str,
    device_id: str | None = None,
    home_live_enabled: bool = False,
    home_live_refresh_seconds: int = 60,
    home_live_request_timeout_seconds: int = 20,
    current_state_page_size: int = 100,
    home_traffic_enabled: bool = False,
    home_traffic_refresh_seconds: int = 60,
    home_traffic_request_timeout_seconds: int = 20,
    home_traffic_page_size: int = 100,
    home_activity_state: str = "disabled",
    home_activity_config: object | None = None,
) -> Response:
    """Render only canonical server context; business data is API-loaded."""
    return make_response(
        render_template(
            page.template,
            page=page,
            site_id=site_id,
            username=username,
            csrf_token=csrf_token,
            runtime_state=runtime_state,
            device_id=device_id,
            home_live_enabled=home_live_enabled,
            home_live_refresh_seconds=home_live_refresh_seconds,
            home_live_request_timeout_seconds=home_live_request_timeout_seconds,
            current_state_page_size=current_state_page_size,
            home_traffic_enabled=home_traffic_enabled,
            home_traffic_refresh_seconds=home_traffic_refresh_seconds,
            home_traffic_request_timeout_seconds=home_traffic_request_timeout_seconds,
            home_traffic_page_size=home_traffic_page_size,
            home_activity_enabled=(
                home_activity_state == "active"
                and bool(getattr(home_activity_config, "enabled", False))
            ),
            home_activity_unavailable=home_activity_state == "unavailable",
            home_activity_refresh_seconds=getattr(
                home_activity_config, "refresh_seconds", 60
            ),
            home_activity_request_timeout_seconds=getattr(
                home_activity_config, "request_timeout_seconds", 20
            ),
        )
    )


def canonical_device_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        canonical = str(uuid.UUID(value))
    except (AttributeError, ValueError):
        return None
    return value if value == canonical else None
