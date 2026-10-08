"""Controller V2 + bounded mutation route integration, all inputs disposable."""
import json
import logging
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask

from app.admin_web import create_admin_web_runtime
from app.admin_web.models import AdminPrincipal
from app.admin_web.routes import create_admin_web_blueprint
from app.controllers.omada_config import build_omada_runtime_config, public_omada_snapshot
from app.settings_control.bootstrap import bootstrap_settings_control
from app.settings_control.models import SettingsError
from tests.settings_control import CONTROLLER_BASE
from .conftest import enabled_settings, login

API = "/admin/api/v1/settings/controller"
POST = API + "/generations"
SECRET = "AS03_HTTP_SENTINEL_secret_NOT_DISCLOSED_123"


def setup(tmp_path, monkeypatch, *, authenticated=True):
    monkeypatch.setattr("requests.sessions.Session.request", lambda *a, **k: pytest.fail("Controller/OAuth I/O"))
    base = {**enabled_settings(web_admin_settings_enabled=True), **CONTROLLER_BASE,
            "client_secret": SECRET, "settings_db_path": str(tmp_path / "settings.sqlite3")}
    boot = bootstrap_settings_control(base_settings=base, explicit_environment_names={"OMADA_URL"}, logger=logging.getLogger("as03"))
    safe = public_omada_snapshot(build_omada_runtime_config(boot.runtime_settings, boot.controller_secret_resolution), frozenset({"OMADA_URL"}), boot.resolved_snapshot, boot.controller_secret_resolution)
    runtime = create_admin_web_runtime(boot.runtime_settings, None, None, None, None, logging.getLogger("as03"),
        settings_control=boot.admin_context, controller_public_snapshot=safe)
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(runtime.blueprint)
    boot.activation_service.adopt(boot.runtime_settings, runtime)
    client = app.test_client()
    csrf = ""
    if authenticated:
        assert login(client).status_code == 302
        csrf = client.get("/admin/api/v1/session", base_url="https://localhost").json["result"]["csrf_token"]
    return client, boot, runtime, csrf


def post(client, csrf, changes=None, *, body=None, key=None, etag='"settings-g0"', **kwargs):
    data = body if body is not None else json.dumps({"changes": changes or [{"key": "OMADA_ID", "operation": "set", "value": "new-installation"}]})
    return client.post(POST, data=data, content_type="application/json", base_url="https://localhost",
        headers={"X-CSRF-Token": csrf, "If-Match": etag, "Idempotency-Key": key or str(uuid.uuid4())}, **kwargs)


def test_route_changed_noop_replay_global_etag_and_secret_isolation(tmp_path, monkeypatch, caplog):
    client, boot, runtime, csrf = setup(tmp_path, monkeypatch)
    key = str(uuid.uuid4())
    initial = client.get(API, base_url="https://localhost")
    assert initial.status_code == 200 and initial.headers["ETag"] == '"settings-g0"'
    assert initial.json["effective_generation"] == 0
    assert initial.json["mutation_available"] is True
    first = post(client, csrf, key=key)
    assert first.status_code == 201 and first.json["api_version"] == "admin.settings.controller.mutation.v1"
    assert first.json["changed_keys"] == ["OMADA_ID"] and first.headers["ETag"] == '"settings-g1"'
    assert "new-installation" not in first.text
    assert post(client, csrf, key=key).json == first.json
    assert post(client, csrf).status_code == 412
    noop = post(client, csrf, etag='"settings-g1"')
    assert noop.status_code == 200 and not noop.json["changed"]
    current = client.get(API, base_url="https://localhost")
    assert current.json["fields"]["controller_id"]["configured_value"] == "new-installation"
    assert current.json["fields"]["controller_id"]["effective_value"] == "installation"
    assert current.json["pending_controller_setting_count"] == 1
    page = client.get("/admin/settings/controller", base_url="https://localhost")
    assert b'id="controller-settings-save"' in page.data
    assert b'data-write-allowed="true"' in page.data
    assert "new-installation" not in page.text
    assert SECRET not in initial.text + first.text + current.text + page.text + caplog.text
    runtime.site_resolver = SimpleNamespace(default=lambda: pytest.fail("Site"), resolve=lambda _: pytest.fail("Site"))
    assert client.get(API, base_url="https://localhost").status_code == 200


@pytest.mark.parametrize("body", [
    '{"changes":[],"changes":[]}', '{"changes":[]}', '[]', '{',
    '{"changes":[{"key":"OMADA_ID","key":"OMADA_URL","operation":"set","value":"x"}]}',
    '{"changes":[{"key":"OMADA_ID","operation":"set","value":"x","extra":1}]}',
    '{"changes":[{"key":"OMADA_ID","operation":"clear_override","value":"x"}]}',
    '{"changes":[{"key":"OMADA_ID","operation":"set","value":NaN}]}',
    '{"changes":[{"key":"OMADA_ID","operation":"set","value":Infinity}]}',
    '{"changes":[{"key":"OMADA_ID","operation":"set","value":-Infinity}]}',
    '{"changes":[{"key":"OMADA_ID","operation":"set","value":false}]}',
    '{"changes":[{"key":"OMADA_ID","operation":"set","value":"x"}],"site_id":"fake"}',
    *[json.dumps({"changes": [{"key": key, "operation": "set", "value": SECRET}]}) for key in
      ("OMADA_CLIENT_SECRET", "VERIFY_SSL", "WEB_ADMIN_DEVICE_PAGE_SIZE")],
    json.dumps({"changes": [{"key": "OMADA_ID", "operation": "set", "value": "x"}] * 2}),
    json.dumps({"changes": [{"key": "OMADA_ID", "operation": "set", "value": "x"}] * 4}),
])
def test_strict_controller_json_and_domain_rejected_atomically(tmp_path, monkeypatch, body):
    client, boot, runtime, csrf = setup(tmp_path, monkeypatch)
    response = post(client, csrf, body=body)
    assert response.status_code == 400 and response.json["error"]["code"] == "invalid_request"
    assert SECRET not in response.text
    assert boot.admin_context.read_service.repository.configured() == (0, {})


def test_csrf_headers_auth_permission_and_request_limits(tmp_path, monkeypatch):
    client, boot, runtime, csrf = setup(tmp_path, monkeypatch)
    assert post(client, "wrong").status_code == 400
    assert post(client, csrf, etag="*").status_code == 400
    assert post(client, csrf, key="wrong").status_code == 400
    assert post(client, csrf, query_string={"unexpected": "x"}).status_code == 400
    assert post(client, csrf, body=" " * 32769).status_code == 413
    assert client.post(POST, json={"changes": []}, base_url="https://localhost",
        headers={"X-CSRF-Token": csrf}).status_code == 428
    assert client.post("/admin/logout", json={}, base_url="https://localhost").status_code == 415
    # Deliberately independent read/write permissions; General write does not grant Controller write.
    policy = runtime.access_policy
    runtime.access_policy = SimpleNamespace(authorize_global=lambda principal, cap:
        cap != "admin.write.settings.controller" and policy.authorize_global(principal, cap))
    # Blueprint captured policy, so construct it on a fresh app before any request.
    app = Flask("controller-no-write")
    app.register_blueprint(create_admin_web_blueprint(runtime, logger=logging.getLogger("as03")))
    other = app.test_client()
    login(other)
    read_only = other.get(API, base_url="https://localhost")
    assert read_only.status_code == 200
    assert read_only.json["mutation_available"] is True
    page = other.get("/admin/settings/controller", base_url="https://localhost")
    assert b'id="controller-settings-save"' not in page.data
    assert post(other, csrf).json["error"]["code"] == "controller_settings_forbidden"
    unauthenticated, _, _, _ = setup(tmp_path, monkeypatch, authenticated=False)
    assert post(unauthenticated, csrf).status_code == 401


def test_later_store_outage_retains_effective_but_cannot_mutate(tmp_path, monkeypatch):
    client, boot, runtime, csrf = setup(tmp_path, monkeypatch)
    assert post(client, csrf).status_code == 201
    boot.admin_context.read_service.repository.db_path = str(tmp_path / "missing" / "bad.sqlite3")
    response = client.get(API, base_url="https://localhost")
    assert response.status_code == 200 and "ETag" not in response.headers
    assert response.json["store_state"] == "unavailable"
    assert response.json["mutation_available"] is False
    assert response.json["fields"]["controller_id"]["configured_value"] is None
    assert response.json["fields"]["controller_id"]["effective_value"] == "installation"
    assert post(client, csrf).json["error"]["code"] == "settings_store_unavailable"


@pytest.mark.parametrize("error,status", [
    (SettingsError("settings_store_unavailable"), 200),
    (RuntimeError(SECRET), 503),
    (SettingsError("validation_failed", 422), 503),
])
def test_configured_read_degrades_only_for_store_unavailability(tmp_path, monkeypatch, caplog, error, status):
    client, boot, runtime, _ = setup(tmp_path, monkeypatch)

    def fail():
        raise error

    monkeypatch.setattr(boot.admin_context.read_service, "read_controller", fail)
    response = client.get(API, base_url="https://localhost")
    assert response.status_code == status
    if status == 200:
        assert response.json["store_state"] == "unavailable"
        assert response.json["mutation_available"] is False
        assert response.json["effective_generation"] == 0
        assert response.json["fields"]["controller_id"]["effective_value"] == "installation"
    else:
        assert response.json["error"]["code"] == "controller_settings_read_unavailable"
        assert "store_state" not in response.json
    assert SECRET not in response.text + caplog.text


@pytest.mark.parametrize("boundary", [None, SimpleNamespace(read_controller=None)])
def test_missing_or_malformed_configured_boundary_is_read_surface_unavailable(tmp_path, monkeypatch, boundary):
    _, boot, original, _ = setup(tmp_path, monkeypatch)
    runtime = create_admin_web_runtime(boot.runtime_settings, None, None, None, None, logging.getLogger("as03"),
        settings_control=SimpleNamespace(feature_enabled=True, store_state="available",
            read_service=boundary, mutation_service=boot.admin_context.mutation_service),
        controller_public_snapshot=original.controller_settings_read_service.snapshot)
    assert runtime.controller_settings_state == "unavailable"
    app = Flask("controller-missing-configured-boundary")
    app.register_blueprint(runtime.blueprint)
    client = app.test_client()
    assert login(client).status_code == 302
    response = client.get(API, base_url="https://localhost")
    assert response.status_code == 503
    assert response.json["error"]["code"] == "controller_settings_read_unavailable"
    assert "store_state" not in response.json


@pytest.mark.parametrize("projection", [None, {}])
def test_malformed_configured_projection_is_not_a_store_outage(tmp_path, monkeypatch, projection):
    client, boot, _, _ = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(boot.admin_context.read_service, "read_controller", lambda: projection)
    response = client.get(API, base_url="https://localhost")
    assert response.status_code == 503
    assert response.json["error"]["code"] == "controller_settings_read_unavailable"
    assert "store_state" not in response.json


def test_controller_validation_and_internal_errors_never_echo_secret(tmp_path, monkeypatch, caplog):
    client, boot, runtime, csrf = setup(tmp_path, monkeypatch)
    invalid = post(client, csrf, changes=[{"key": "OMADA_URL", "operation": "set", "value": "https://user:" + SECRET + "@bad.invalid"}])
    assert invalid.status_code == 422 and SECRET not in invalid.text
    def fail(*args, **kwargs):
        raise RuntimeError(SECRET)
    monkeypatch.setattr(runtime.settings_mutation_service, "mutate", fail)
    response = post(client, csrf)
    assert response.status_code == 500 and response.json["error"]["code"] == "internal_error"
    assert SECRET not in response.text + caplog.text
