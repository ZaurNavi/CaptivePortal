from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from app.admin_web import create_admin_web_runtime
from app.admin_web.config import AdminWebConfigError, admin_web_config_from_settings

from .conftest import SITE_ID, enabled_settings, login


def _app(tmp_path, *, traffic_enabled: bool) -> Flask:
    runtime = create_admin_web_runtime(
        enabled_settings(
            web_admin_traffic_enabled="true" if traffic_enabled else "false",
        ),
        SimpleNamespace(state="active", visit_service=object()),
        SimpleNamespace(
            repository=SimpleNamespace(
                config=SimpleNamespace(db_path=tmp_path / "registry.sqlite3")
            )
        ),
        SimpleNamespace(repository=SimpleNamespace(db_path=tmp_path / "visits.sqlite3")),
        SimpleNamespace(
            _repository=SimpleNamespace(db_path=tmp_path / "observations.sqlite3")
        ),
        logging.getLogger("traffic-foundation-test"),
    )
    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    app.register_blueprint(runtime.blueprint)
    app.extensions["admin_web_runtime"] = runtime
    return app


def test_traffic_config_defaults_and_env_example_are_safe():
    config = admin_web_config_from_settings({"web_admin_enabled": "false"})
    assert config.traffic_enabled is False
    assert config.traffic_refresh_seconds == 60
    assert config.traffic_request_timeout_seconds == 30

    example = (Path(__file__).parents[2] / ".env.example").read_text(encoding="utf-8")
    assert "WEB_ADMIN_TRAFFIC_ENABLED=false\n" in example
    assert "WEB_ADMIN_TRAFFIC_REFRESH_SECONDS=60\n" in example
    assert "WEB_ADMIN_TRAFFIC_REQUEST_TIMEOUT_SECONDS=30\n" in example


@pytest.mark.parametrize(
    "key,value",
    [
        ("web_admin_traffic_refresh_seconds", "59"),
        ("web_admin_traffic_refresh_seconds", "301"),
        ("web_admin_traffic_request_timeout_seconds", "4"),
        ("web_admin_traffic_request_timeout_seconds", "61"),
        ("web_admin_traffic_request_timeout_seconds", "10"),
    ],
)
def test_traffic_config_rejects_out_of_bounds_or_non_deadline_safe_values(key, value):
    with pytest.raises(AdminWebConfigError):
        admin_web_config_from_settings(enabled_settings(**{key: value}))


def test_traffic_enabled_requires_admin_enabled():
    with pytest.raises(AdminWebConfigError, match="requires WEB_ADMIN_ENABLED"):
        admin_web_config_from_settings(
            {"web_admin_enabled": "false", "web_admin_traffic_enabled": "true"}
        )


@pytest.mark.parametrize("path", ["", "devices", "visits", "observations"])
def test_disabled_traffic_hides_navigation_and_authorized_page_is_404(tmp_path, path):
    app = _app(tmp_path, traffic_enabled=False)
    client = app.test_client()
    login(client)
    suffix = "/" if not path else f"/{path}"
    page = client.get(
        f"/admin/sites/{SITE_ID}{suffix}", base_url="https://localhost"
    )
    assert page.status_code == 200
    assert f'/admin/sites/{SITE_ID}/traffic'.encode() not in page.data
    direct = client.get(
        f"/admin/sites/{SITE_ID}/traffic", base_url="https://localhost"
    )
    assert direct.status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        "",
        "devices",
        "devices/00000000-0000-0000-0000-000000000000",
        "visits",
        "observations",
        "traffic",
    ],
)
def test_enabled_traffic_navigation_is_shared_and_active_only_on_traffic(
    tmp_path, path
):
    app = _app(tmp_path, traffic_enabled=True)
    client = app.test_client()
    login(client)
    suffix = "/" if not path else f"/{path}"
    response = client.get(
        f"/admin/sites/{SITE_ID}{suffix}", base_url="https://localhost"
    )
    assert response.status_code == 200
    marker = f'href="/admin/sites/{SITE_ID}/traffic"'.encode()
    assert marker in response.data
    traffic_link = response.data.split(marker, 1)[0].rsplit(b"<a", 1)[-1]
    assert (b"is-active" in traffic_link) is (path == "traffic")


def test_traffic_route_preserves_auth_site_policy_and_feature_order(tmp_path):
    app = _app(tmp_path, traffic_enabled=False)
    anonymous = app.test_client().get(
        f"/admin/sites/{SITE_ID}/traffic", base_url="https://localhost"
    )
    assert anonymous.status_code == 302

    client = app.test_client()
    login(client)
    invalid = client.get("/admin/sites/not-a-site/traffic", base_url="https://localhost")
    forbidden = client.get(
        f"/admin/sites/{'f' * 24}/traffic", base_url="https://localhost"
    )
    assert invalid.status_code == 400
    assert forbidden.status_code == 403


def test_traffic_shell_has_only_safe_page_context_and_foundation_hooks(tmp_path):
    app = _app(tmp_path, traffic_enabled=True)
    client = app.test_client()
    login(client)
    response = client.get(
        f"/admin/sites/{SITE_ID}/traffic", base_url="https://localhost"
    )
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert 'data-page="traffic"' in body
    assert 'data-traffic-enabled="true"' in body
    assert 'data-traffic-refresh-seconds="60"' in body
    assert 'data-traffic-request-timeout-seconds="30"' in body
    assert 'id="traffic-global-state"' in body
    assert 'id="traffic-empty-state"' in body
    assert 'id="traffic-panels"' in body
    assert 'id="refresh-button" class="button" type="button" disabled' in body
    assert "0 Mbps" not in body
    assert "No Traffic" not in body
    assert "No Clients" not in body
    assert "No History" not in body
    assert "<script>" not in body
    assert "/admin/api/v1/sites/" in body
    assert "password_hash" not in body
    assert "sqlite3" not in body
    assert "omada" not in body.lower()


def test_traffic_runtime_dataset_is_not_emitted_on_other_pages(tmp_path):
    app = _app(tmp_path, traffic_enabled=True)
    client = app.test_client()
    login(client)
    home = client.get(f"/admin/sites/{SITE_ID}/", base_url="https://localhost")
    assert home.status_code == 200
    assert b"data-traffic-enabled" not in home.data
    assert b"data-traffic-refresh-seconds" not in home.data
    assert b"data-traffic-request-timeout-seconds" not in home.data
