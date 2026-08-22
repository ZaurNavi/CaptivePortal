from __future__ import annotations

from pathlib import Path

import pytest
from flask import render_template

from app.admin_web.pages import HOME

from .conftest import SITE_ID, login


DEVICE_ID = "10000000-0000-4000-8000-000000000001"
PAGE_PATHS = (
    f"/admin/sites/{SITE_ID}/",
    f"/admin/sites/{SITE_ID}/devices",
    f"/admin/sites/{SITE_ID}/devices/{DEVICE_ID}",
    f"/admin/sites/{SITE_ID}/visits",
    f"/admin/sites/{SITE_ID}/observations",
)


@pytest.mark.parametrize("path", PAGE_PATHS)
def test_core_page_requires_session_then_renders_site_shell(admin_app, path):
    client = admin_app.test_client()
    unauthenticated = client.get(path, base_url="https://localhost")
    assert unauthenticated.status_code == 302
    assert unauthenticated.headers["Location"].startswith("/admin/login?next=")

    login(client)
    response = client.get(path, base_url="https://localhost")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert "script-src 'self'" in response.headers["Content-Security-Policy"]
    assert b'<script defer src="/admin/static/admin.js"></script>' in response.data
    assert b'<link rel="stylesheet" href="/admin/static/admin.css">' in response.data
    assert f'data-site-id="{SITE_ID}"'.encode() in response.data
    for suffix in ("/", "/devices", "/visits", "/observations"):
        expected = f'/admin/sites/{SITE_ID}{suffix}'.encode()
        assert expected in response.data
    assert b'action="/admin/logout"' in response.data


def test_page_site_and_device_identifiers_are_strict(admin_app):
    client = admin_app.test_client()
    login(client)
    invalid_site = client.get(
        "/admin/sites/ABC/devices", base_url="https://localhost"
    )
    forbidden_site = client.get(
        "/admin/sites/ffffffffffffffffffffffff/devices",
        base_url="https://localhost",
    )
    invalid_device = client.get(
        f"/admin/sites/{SITE_ID}/devices/not-a-uuid",
        base_url="https://localhost",
    )
    assert invalid_site.status_code == 400
    assert forbidden_site.status_code == 403
    assert invalid_device.status_code == 400


def test_jinja_shell_autoescapes_presentation_values(admin_app):
    with admin_app.test_request_context(base_url="https://localhost"):
        rendered = render_template(
            "admin/home.html",
            page=HOME,
            site_id=SITE_ID,
            username='<img src=x onerror="alert(1)">',
            csrf_token="x" * 43,
            runtime_state="active",
            device_id=None,
        )
    assert "<img src=x" not in rendered
    assert "&lt;img src=x" in rendered


def test_static_assets_are_local_csp_compatible_and_secret_free(admin_app):
    client = admin_app.test_client()
    javascript = client.get(
        "/admin/static/admin.js", base_url="https://localhost"
    )
    stylesheet = client.get(
        "/admin/static/admin.css", base_url="https://localhost"
    )
    assert javascript.status_code == 200
    assert stylesheet.status_code == 200
    source = javascript.get_data(as_text=True)
    forbidden = (
        "innerHTML", "localStorage", "sessionStorage", "Bearer",
        "/api/internal/analytics/v1", "grafana", "loki", "omada",
        "setInterval", "setTimeout", "http://", "https://",
    )
    assert all(value not in source for value in forbidden)
    assert "textContent" in source
    assert "replaceChildren" in source
    assert "credentials: \"same-origin\"" in source
    assert "captivportal_admin_session" not in source
    assert "csrf_token" not in source
    assert "toISOString().slice(0, 16)" not in source
    assert source.count("form.elements.to.value = localDatetimeValue(now)") == 2
    assert source.count("form.elements.from.value = localDatetimeValue(from)") == 2


def test_visits_page_has_bounded_optional_filters(admin_app):
    client = admin_app.test_client()
    login(client)
    response = client.get(
        f"/admin/sites/{SITE_ID}/visits", base_url="https://localhost"
    )
    source = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'id="visit-filter-form"' in source
    assert 'name="from" type="datetime-local"' in source
    assert 'name="to" type="datetime-local"' in source
    assert '<option value="all">All</option>' in source
    assert '<option value="open">Open</option>' in source
    assert '<option value="closed">Closed</option>' in source
    assert ">Apply filters</button>" in source
    assert 'id="clear-visit-filters"' in source


def test_templates_have_no_inline_script_or_write_controls():
    root = Path(__file__).parents[2] / "app" / "admin_web"
    templates = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (root / "templates" / "admin").glob("*.html")
    )
    lowered = templates.lower()
    assert "<script>" not in lowered
    for action in (
        "unblock", "reconnect", "rename", "rate-limit", "lock-to-ap"
    ):
        assert action not in lowered
