import json
import logging
import uuid
from types import SimpleNamespace
import pytest
from flask import Flask
from app.admin_web import create_admin_web_runtime
from app.admin_web.capabilities import DEFAULT_GLOBAL_CAPABILITIES, GLOBAL_CAPABILITIES
from app.settings_control.bootstrap import bootstrap_settings_control
from tests.settings_control import CONTROLLER_BASE
from .conftest import enabled_settings, login

READ = "admin.read.settings.portal"
WRITE = "admin.write.settings.portal"
BASE = "/admin/api/v1/settings/portal"
VALID = json.dumps({"changes": [{"key": "PORTAL_UI_TITLE_EN", "operation": "set", "value": "New park"}]})


def portal_app(tmp_path, *, grants=(READ, WRITE), enabled=True, unavailable=False):
    tmp_path.mkdir(parents=True, exist_ok=True)
    base = {**CONTROLLER_BASE, **enabled_settings(web_admin_settings_enabled="true" if enabled else "false",
        web_admin_global_capabilities=",".join(grants) if grants else "admin.read.settings.global",
        settings_db_path=str(tmp_path / "settings.sqlite3"))}
    boot = bootstrap_settings_control(base_settings=base, explicit_environment_names=set(), logger=logging.getLogger("portal-admin-test"))
    runtime = create_admin_web_runtime(boot.runtime_settings, None, None, None, None,
        logging.getLogger("portal-admin-test"), settings_control=boot.admin_context, feature_plan=boot.feature_plan)
    assert runtime.feature_plan is boot.feature_plan
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(runtime.blueprint)
    if boot.activation_service:
        boot.activation_service.adopt(boot.runtime_settings, runtime,
            SimpleNamespace(feature_plan=boot.feature_plan, historical_source_mode="base"), feature_plan=boot.feature_plan)
    if unavailable:
        boot.admin_context.read_service.repository.db_path = str(tmp_path / "missing" / "settings.sqlite3")
    client = app.test_client()
    assert login(client).status_code == 302
    csrf = client.get("/admin/api/v1/session", base_url="https://localhost").json["result"]["csrf_token"]
    return app, client, runtime, boot, csrf


def post(client, csrf, body=VALID, *, etag='"settings-g0"', key=None, **kwargs):
    return client.post(BASE + "/generations", data=body, content_type="application/json",
        headers={"X-CSRF-Token": csrf, "If-Match": etag, "Idempotency-Key": key or str(uuid.uuid4())},
        base_url="https://localhost", **kwargs)


def test_global_capabilities_are_explicit_not_default():
    assert {READ, WRITE} <= GLOBAL_CAPABILITIES
    assert not {READ, WRITE} & DEFAULT_GLOBAL_CAPABILITIES


@pytest.mark.parametrize("grants,read_status,write_status", [((READ, WRITE), 200, 201), ((READ,), 200, 403), ((WRITE,), 403, 403), ((), 403, 403)])
def test_global_read_and_write_authorization(tmp_path, grants, read_status, write_status):
    _app, client, _runtime, _boot, csrf = portal_app(tmp_path, grants=grants)
    assert client.get(BASE, base_url="https://localhost").status_code == read_status
    assert client.get("/admin/settings/portal", base_url="https://localhost").status_code == read_status
    assert post(client, csrf).status_code == write_status


def test_closed_read_model_and_mutation_receipt(tmp_path, monkeypatch):
    _app, client, runtime, boot, csrf = portal_app(tmp_path)
    monkeypatch.setattr(boot.admin_context.mutation_service.secret_repository, "resolve", lambda *a, **k: pytest.fail("Portal secret I/O"))
    assert runtime.query_service is None
    read = client.get(BASE, base_url="https://localhost")
    assert read.status_code == 200
    assert set(read.json) == {"api_version", "request_id", "scope", "store_state", "configured_generation", "effective_generation", "etag", "restart_required", "pending_setting_count", "settings"}
    expected_item = {"key", "display_label", "description", "group", "value_type", "presentation_type", "scope_type", "scope_id", "editable", "secret_class", "default_value", "base_source", "base_value", "persisted_override_value", "configured_value", "effective_value", "pending_value", "configured_generation", "effective_generation", "activation_state", "apply_requirement", "activation_target", "validation", "last_changed_at", "last_changed_by"}
    assert len(read.json["settings"]) == 14
    assert all(set(item) == expected_item and item["scope_id"] is None and item["secret_class"] == "normal" for item in read.json["settings"])
    for response in (read, post(client, csrf)):
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["Pragma"] == "no-cache"
    assert read.headers["ETag"] == '"settings-g0"'
    key = str(uuid.uuid4())
    body = json.dumps({"changes": [{"key": "PORTAL_UI_TITLE_EN", "operation": "set", "value": "Next park"}]})
    first = post(client, csrf, body, etag='"settings-g1"', key=key)
    assert first.status_code == 201 and first.headers["ETag"] == '"settings-g2"'
    assert set(first.json) == {"api_version", "request_id", "scope", "resource", "changed", "changed_keys", "configured_generation", "effective_generation", "activation_state", "restart_required"}
    assert first.json["resource"] == {"type": "guest_portal", "scope": "installation"}
    assert "Next park" not in first.get_data(as_text=True)
    assert post(client, csrf, body, key=key).json == first.json
    assert post(client, csrf, VALID, key=key).status_code == 409
    assert post(client, csrf).status_code == 412
    noop = post(client, csrf, body, etag='"settings-g2"')
    assert noop.status_code == 200 and not noop.json["changed"] and noop.json["restart_required"]
    assert noop.json["activation_state"] == "pending_main_restart"


@pytest.mark.parametrize("body", ['{"changes":[],"changes":[]}', *['{"changes":[{"key":"PORTAL_UI_TITLE_EN","operation":"set","value":' + value + '}]}' for value in ("NaN", "Infinity", "-Infinity", "true", "42", "null")],
    '{"changes":[{"key":"PORTAL_UI_TITLE_EN","operation":"set","value":"x","value":"y"}]}',
    '{"changes":[{"key":"OMADA_URL","operation":"set","value":"https://other.invalid"}]}',
    '{"changes":[{"key":"PORTAL_UI_TITLE_EN","operation":"clear_override","value":"x"}]}',
    '{"changes":[],"site_id":"fake"}', '[]', '{'])
def test_strict_request_errors_are_atomic(tmp_path, body):
    _app, client, _runtime, boot, csrf = portal_app(tmp_path)
    response = post(client, csrf, body)
    assert response.status_code == 400 and response.json["error"]["code"] == "invalid_request"
    assert response.json["api_version"] == "admin.settings.portal.mutation.v1"
    assert boot.admin_context.read_service.repository.configured() == (0, {})


def test_security_transport_and_safe_validation_error(tmp_path):
    _app, client, _runtime, boot, csrf = portal_app(tmp_path)
    assert post(client, "bad").status_code == 400
    assert post(client, "bad").json["error"]["code"] == "invalid_csrf"
    assert post(client, csrf, etag="*").status_code == 400
    assert post(client, csrf, key="invalid").status_code == 400
    missing = client.post(BASE + "/generations", json=json.loads(VALID), headers={"X-CSRF-Token": csrf}, base_url="https://localhost")
    assert missing.status_code == 428
    assert post(client, csrf, VALID + " " * 32768).status_code == 413
    assert post(client, csrf, query_string={"site": "fake"}).status_code == 400
    assert client.get(BASE + "?site=fake", base_url="https://localhost").status_code == 400
    assert client.get(BASE, data="body", base_url="https://localhost").status_code == 400
    assert client.post(BASE + "/generations", data=VALID, headers={"X-CSRF-Token": csrf, "If-Match": '"settings-g0"', "Idempotency-Key": str(uuid.uuid4())}, content_type="text/plain", base_url="https://localhost").status_code == 415
    invalid = VALID.replace("New park", "<script>secretish</script> ")
    error = post(client, csrf, invalid)
    assert error.status_code == 422 and "secretish" not in error.get_data(as_text=True)
    assert boot.admin_context.read_service.repository.configured() == (0, {})


@pytest.mark.parametrize("enabled,unavailable", [(False, False), (True, True)])
def test_unavailable_store_is_safe(tmp_path, enabled, unavailable):
    _app, client, _runtime, _boot, csrf = portal_app(tmp_path, enabled=enabled, unavailable=unavailable)
    for response in (client.get(BASE, base_url="https://localhost"), post(client, csrf)):
        assert response.status_code == (503 if enabled else 404)
        assert response.json["error"]["code"] == ("settings_store_unavailable" if enabled else "feature_disabled")
        assert response.json["api_version"] == ("admin.settings.portal.mutation.v1" if response.request.method == "POST" else "admin.settings.portal.v1")
        assert response.headers["Cache-Control"] == "no-store"


def test_portal_shell_is_global_and_navigation_is_capability_bound(tmp_path):
    _app, client, _runtime, _boot, _csrf = portal_app(tmp_path, grants=(*DEFAULT_GLOBAL_CAPABILITIES, READ, WRITE))
    page = client.get("/admin/settings/portal", base_url="https://localhost").get_data(as_text=True)
    assert "Guest Portal" in page and "Global guest-facing presentation settings" in page
    assert "portal_settings.js" in page and "admin.js" not in page and "controller_settings.js" not in page
    assert 'data-site-id="' not in page and 'data-write-allowed="true"' in page
    assert page.index('href="/admin/settings"') < page.index('href="/admin/settings/controller"') < page.index('href="/admin/settings/portal"')
    assert 'aria-current="page">Portal</a>' in page
    for required in ('class="state-dot"', 'id="portal-settings-state-title"',
                     'id="portal-settings-state-message"', 'id="portal-settings-generation"',
                     'role="status"', 'aria-live="polite"', 'class="settings-actions portal-settings-actions"'):
        assert required in page
    assert '>Refresh</button>' in page and '>Save changes</button>' in page
    assert "external captive-portal.service restart" in page
    for forbidden in ("Read current settings", "Apply now", "Reload service", "systemctl"):
        assert forbidden not in page
    _app, client, _runtime, _boot, _csrf = portal_app(tmp_path / "readonly", grants=(READ,))
    page = client.get("/admin/settings/portal", base_url="https://localhost").get_data(as_text=True)
    assert 'data-write-allowed="false"' in page and 'href="/admin/settings/controller"' not in page
