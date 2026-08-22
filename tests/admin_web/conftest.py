from __future__ import annotations

import re
from types import SimpleNamespace

import pytest
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash

from app.admin_web import create_admin_web_runtime


SITE_ID = "0123456789abcdef01234567"
PASSWORD = "correct horse battery staple"
PASSWORD_HASH = generate_password_hash(
    PASSWORD,
    method="pbkdf2:sha256:100000",
)


def enabled_settings(**overrides):
    values = {
        "web_admin_enabled": "true",
        "web_admin_username": "operator",
        "web_admin_password_hash": PASSWORD_HASH,
        "web_admin_allowed_networks": "127.0.0.1/32,::1/128",
        "web_admin_allowed_site_ids": SITE_ID,
        "web_admin_default_site_id": SITE_ID,
        "web_admin_require_https": "true",
    }
    values.update(overrides)
    return values


@pytest.fixture
def admin_app():
    runtime = create_admin_web_runtime(
        enabled_settings(),
        SimpleNamespace(state="active"),
        object(),
        object(),
        object(),
        __import__("logging").getLogger("admin-web-test"),
    )
    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1,
        x_port=1,
    )
    app.register_blueprint(runtime.blueprint)
    app.extensions["admin_web_runtime"] = runtime
    return app


def csrf_from(response) -> str:
    match = re.search(rb'name="csrf_token" value="([A-Za-z0-9_-]{43})"', response.data)
    assert match is not None
    return match.group(1).decode("ascii")


def login(client, *, username="operator", password=PASSWORD, next_value=None):
    suffix = "" if next_value is None else "?next=" + next_value
    form = client.get("/admin/login" + suffix, base_url="https://localhost")
    token = csrf_from(form)
    return client.post(
        "/admin/login" + suffix,
        data={"username": username, "password": password, "csrf_token": token},
        base_url="https://localhost",
    )
