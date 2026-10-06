import logging
import uuid
from types import SimpleNamespace
import pytest
from flask import Flask
from app.admin_web import create_admin_web_runtime
from app.admin_web.models import AdminPrincipal
from app.admin_web.policy import AdminAccessPolicy
from app.settings_control.bootstrap import bootstrap_settings_control
from .conftest import enabled_settings, login


def settings_app(tmp_path, *, enabled=True, unavailable=False):
    base = enabled_settings(web_admin_settings_enabled="true" if enabled else "false",
                            settings_db_path=str(tmp_path / ("missing/settings.sqlite3" if unavailable else "settings.sqlite3")))
    boot = bootstrap_settings_control(base_settings=base, explicit_environment_names=set(), logger=logging.getLogger("settings-ui"))
    runtime = create_admin_web_runtime(boot.runtime_settings, None, None, None, None,
                                      logging.getLogger("settings-ui"), settings_control=boot.admin_context)
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(runtime.blueprint)
    if boot.activation_service:
        boot.activation_service.adopt(boot.runtime_settings, runtime)
    client = app.test_client()
    assert login(client).status_code == 302
    session = client.get("/admin/api/v1/session", base_url="https://localhost").json["result"]
    return app, client, runtime, boot, session["csrf_token"]


def post(client, csrf, body, *, etag='"settings-g0"', key=None, **options):
    headers = {"X-CSRF-Token": csrf, "If-Match": etag, "Idempotency-Key": key or str(uuid.uuid4())}
    return client.post("/admin/api/v1/settings/generations", data=body, content_type="application/json",
                       headers=headers, base_url="https://localhost", **options)


VALID = '{"changes":[{"key":"WEB_ADMIN_DEVICE_PAGE_SIZE","operation":"set","value":120}]}'


def test_global_policy_site_independent():
    policy = AdminAccessPolicy(frozenset())
    assert policy.authorize_global(AdminPrincipal("operator"), "admin.read.settings.global")
    assert policy.authorize_global(AdminPrincipal("operator"), "admin.write.settings.global")
    assert not policy.authorize_global(AdminPrincipal("operator", "site_operator"), "admin.write.settings.global")
    assert not policy.authorize_global(None, "admin.read.settings.global")
    assert not policy.authorize_global(AdminPrincipal("operator"), "admin.read.devices")
    assert not policy.authorize(AdminPrincipal("operator"), "admin.read.devices", "0123456789abcdef01234567")


def test_read_mutate_replay_and_etag_without_query_source(tmp_path):
    app, client, runtime, boot, csrf = settings_app(tmp_path)
    assert runtime.query_service is None
    read = client.get("/admin/api/v1/settings", base_url="https://localhost")
    assert read.status_code == 200 and read.headers["ETag"] == '"settings-g0"'
    assert read.headers["Cache-Control"] == "no-store" and len(read.json["settings"]) == 12
    assert [item["group"] for item in read.json["settings"]] == ["pagination"] * 6 + ["refresh"] * 6
    for item, definition in zip(read.json["settings"], boot.admin_context.read_service.registry):
        assert item["validation"] == {"type": "integer", "min": definition.min_value, "max": definition.max_value}
    key = str(uuid.uuid4())
    first = post(client, csrf, VALID, key=key)
    assert first.status_code == 201 and len(first.json["settings"]) == 12
    assert [item["group"] for item in first.json["settings"]] == ["pagination"] * 6 + ["refresh"] * 6
    assert all(set(item["validation"]) == {"type", "min", "max"} for item in first.json["settings"])
    assert post(client, csrf, VALID, key=key).json == first.json
    assert post(client, csrf, VALID).status_code == 412
    assert client.get("/admin/api/v1/settings", base_url="https://localhost").headers["ETag"] == '"settings-g1"'


@pytest.mark.parametrize("body", [
    '{"changes":[],"changes":[]}',
    '{"changes":[{"key":"WEB_ADMIN_DEVICE_PAGE_SIZE","key":"WEB_ADMIN_VISIT_PAGE_SIZE","operation":"set","value":100}]}',
    '{"changes":[{"key":"WEB_ADMIN_DEVICE_PAGE_SIZE","operation":"set","operation":"set","value":100}]}',
    '{"changes":[{"key":"WEB_ADMIN_DEVICE_PAGE_SIZE","operation":"set","value":100,"value":101}]}',
    *['{"changes":[{"key":"WEB_ADMIN_DEVICE_PAGE_SIZE","operation":"set","value":' + value + '}]}' for value in ("NaN", "Infinity", "-Infinity", "true", '"100"')],
    '{"changes":[]}', '[]', '{',
    '{"changes":[{"key":"WEB_ADMIN_ENABLED","operation":"set","value":100}]}',
    '{"changes":[{"key":"WEB_ADMIN_DEVICE_PAGE_SIZE","operation":"clear_override","value":100}]}',
    '{"changes":[{"key":"WEB_ADMIN_DEVICE_PAGE_SIZE","operation":"set","value":100}],"site_id":"fake"}',
])
def test_strict_json_rejected_before_any_mutation(tmp_path, body):
    _app, client, _runtime, boot, csrf = settings_app(tmp_path)
    response = post(client, csrf, body)
    assert response.status_code == 400 and response.json["error"]["code"] == "invalid_request"
    assert response.json["api_version"] == "admin.settings.v1"
    assert boot.admin_context.read_service.repository.configured() == (0, {})


def test_headers_csrf_and_json_carveout(tmp_path):
    _app, client, runtime, _boot, csrf = settings_app(tmp_path)
    assert post(client, "invalid", VALID).json["error"]["code"] == "invalid_csrf"
    assert post(client, csrf, VALID, etag="*").status_code == 400
    assert post(client, csrf, VALID, key="not-uuid").status_code == 400
    response = client.post("/admin/api/v1/settings/generations", data=VALID, content_type="application/json",
                           headers={"X-CSRF-Token": csrf}, base_url="https://localhost")
    assert response.status_code == 428
    large_valid = VALID + " " * (runtime.config.max_post_bytes + 1)
    assert len(large_valid) < 32768
    assert post(client, csrf, large_valid).status_code == 201
    assert post(client, csrf, VALID + " " * 32768).status_code == 413
    # Existing form-only login/logout security is not widened.
    assert client.post("/admin/logout", json={"csrf_token": csrf}, base_url="https://localhost").status_code == 415


@pytest.mark.parametrize("disabled", [False, True])
def test_disabled_and_unavailable_are_bounded(tmp_path, disabled):
    _app, client, runtime, _boot, csrf = settings_app(tmp_path, enabled=not disabled, unavailable=not disabled)
    page = client.get("/admin/settings", base_url="https://localhost")
    api = client.get("/admin/api/v1/settings", base_url="https://localhost")
    assert page.status_code == (404 if disabled else 200)
    assert api.status_code == (404 if disabled else 503)
    assert post(client, csrf, VALID).status_code == (404 if disabled else 503)
    assert str(tmp_path).encode() not in api.data
    shell = client.get("/admin/sites/0123456789abcdef01234567/", base_url="https://localhost")
    assert (b'href="/admin/settings"' in shell.data) is not disabled


def test_global_route_never_resolves_site(tmp_path, monkeypatch):
    _app, client, runtime, _boot, _csrf = settings_app(tmp_path)
    def forbidden(*_args):
        pytest.fail("Settings resolved a Site")
    runtime.site_resolver = SimpleNamespace(default=forbidden, resolve=forbidden)
    # Closure holds the original resolver, so also replace its class methods.
    from app.admin_web.policy import AdminSiteContextResolver
    monkeypatch.setattr(AdminSiteContextResolver, "default", forbidden)
    monkeypatch.setattr(AdminSiteContextResolver, "resolve", forbidden)
    page = client.get("/admin/settings", base_url="https://localhost")
    assert page.status_code == 200
    assert b"data-site-id" not in page.data and b"/admin/api/v1/sites/" not in page.data
    assert client.get("/admin/api/v1/settings", base_url="https://localhost").status_code == 200
