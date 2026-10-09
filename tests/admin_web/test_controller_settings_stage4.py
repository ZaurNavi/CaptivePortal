import json
import logging
import uuid
from pathlib import Path
from dataclasses import replace
from types import SimpleNamespace
import pytest
from flask import Flask
from app.admin_web import create_admin_web_runtime
from app.admin_web.capabilities import DEFAULT_GLOBAL_CAPABILITIES_TEXT, SECRET_WRITE_CAPABILITY
from app.controllers.omada_config import build_omada_runtime_config, public_omada_snapshot
from app.settings_control.models import SettingsError
from tests.settings_control.stage4_helpers import secret_stack, SENTINEL
from .conftest import enabled_settings, login

API = "/admin/api/v1/settings/controller"
POST = API + "/client-secret/generations"


def setup(tmp_path, monkeypatch, *, secret_grant=True, authenticated=True):
    monkeypatch.setattr("requests.sessions.Session.request", lambda *_a, **_k: pytest.fail("Omada/OAuth I/O"))
    grants = "admin.read.settings.controller," + SECRET_WRITE_CAPABILITY if secret_grant else DEFAULT_GLOBAL_CAPABILITIES_TEXT
    boot, filesystem = secret_stack(tmp_path, **enabled_settings(web_admin_settings_enabled=True, web_admin_global_capabilities=grants))
    config = build_omada_runtime_config(boot.runtime_settings, boot.controller_secret_resolution)
    public = public_omada_snapshot(config, frozenset({"OMADA_CLIENT_SECRET"}), boot.resolved_snapshot, boot.controller_secret_resolution)
    runtime = create_admin_web_runtime(boot.runtime_settings, None, None, None, None, logging.getLogger("s4"),
                                      settings_control=boot.admin_context, controller_public_snapshot=public, feature_plan=boot.feature_plan)
    assert runtime.feature_plan is boot.feature_plan
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(runtime.blueprint)
    boot.activation_service.adopt(boot.runtime_settings, runtime,
        SimpleNamespace(feature_plan=boot.feature_plan, historical_source_mode="base"), feature_plan=boot.feature_plan)
    client = app.test_client()
    csrf = ""
    if authenticated:
        assert login(client).status_code == 302
        csrf = client.get("/admin/api/v1/session", base_url="https://localhost").json["result"]["csrf_token"]
    return client, boot, runtime, csrf, filesystem


def post(client, csrf, *, raw=None, key=None, etag='"settings-g0"', headers=None, **kwargs):
    actual_headers = {"X-CSRF-Token": csrf, "If-Match": etag, "Idempotency-Key": key or str(uuid.uuid4()), **(headers or {})}
    content_type = actual_headers.pop("Content-Type", "application/json")
    actual_headers = {name: value for name, value in actual_headers.items() if value is not None}
    return client.post(POST, data=raw if raw is not None else json.dumps({"operation": "replace_secret", "secret": SENTINEL}),
        content_type=content_type, base_url="https://localhost", headers=actual_headers, **kwargs)


def test_route_safe_receipt_v3_secret_pending_and_capability_independence(tmp_path, monkeypatch, caplog):
    client, boot, runtime, csrf, fs = setup(tmp_path, monkeypatch)
    from app.settings_control.controller_secret import ControllerSecretMetadataService
    metadata = runtime.controller_settings_read_service.secret_metadata_service
    assert type(metadata) is ControllerSecretMetadataService
    assert metadata is boot.admin_context.secret_metadata_service
    assert not hasattr(metadata, "_deployment") and not hasattr(metadata, "value")
    initial = client.get(API, base_url="https://localhost")
    assert initial.status_code == 200 and initial.json["api_version"] == "admin.settings.controller.v3"
    assert initial.json["secret_mutation_available"] is True
    page = client.get("/admin/settings/controller", base_url="https://localhost")
    assert 'data-secret-write-allowed="true"' in page.text
    assert 'id="controller-settings-save"' not in page.text
    key = str(uuid.uuid4())
    accepted = post(client, csrf, key=key)
    assert accepted.status_code == 201
    assert set(accepted.json) == {"api_version", "request_id", "scope", "resource", "operation", "changed",
                                 "configured_generation", "effective_generation", "activation_state", "restart_required"}
    assert post(client, csrf, key=key).status_code == 200
    assert post(client, csrf, key=key).json == accepted.json
    assert post(client, csrf).status_code == 412
    current = client.get(API, base_url="https://localhost")
    secret = current.json["fields"]["client_secret"]
    assert set(secret) == {"display_label", "value_type", "management_mode", "configured_presence", "configured_source",
                          "effective_presence", "effective_source", "persisted_secret_override_present", "pending_replacement",
                          "apply_requirement", "activation_target", "secret_store_state"}
    assert secret["configured_source"] == "managed_secret_override" and secret["effective_source"] == "environment"
    assert secret["pending_replacement"] is True and current.json["pending_controller_setting_count"] == 1
    assert SENTINEL not in initial.text + accepted.text + current.text + page.text + caplog.text
    fs.key_valid = False
    outage = client.get(API, base_url="https://localhost")
    assert outage.status_code == 200 and outage.json["mutation_available"] is True
    assert outage.json["secret_mutation_available"] is False
    assert outage.json["fields"]["client_secret"]["effective_presence"] == "configured"
    assert post(client, csrf, etag='"settings-g1"').json["error"]["code"] == "controller_secret_store_unavailable"


def test_unrelated_generation_not_secret_pending_and_db_outage(tmp_path, monkeypatch):
    from tests.settings_control import mutation
    client, boot, runtime, csrf, _ = setup(tmp_path, monkeypatch)
    mutation(boot)
    current = client.get(API, base_url="https://localhost")
    assert current.json["fields"]["client_secret"]["pending_replacement"] is False
    assert current.json["pending_controller_setting_count"] == 0
    boot.admin_context.read_service.repository.db_path = str(tmp_path / "missing" / "bad.sqlite3")
    outage = client.get(API, base_url="https://localhost")
    assert outage.status_code == 200 and outage.json["store_state"] == "unavailable"
    assert outage.json["secret_mutation_available"] is False
    secret = outage.json["fields"]["client_secret"]
    for field in ("configured_presence", "configured_source", "persisted_secret_override_present", "pending_replacement"):
        assert secret[field] is None
    assert secret["effective_presence"] == "configured"


@pytest.mark.parametrize("case,status,code", [("csrf", 400, "invalid_csrf"), ("etag", 400, "invalid_request"),
    ("missing_etag", 428, "precondition_required"), ("uuid", 400, "invalid_request"), ("query", 400, "invalid_request"),
    ("large", 413, "request_too_large"), ("media", 415, "unsupported_media_type"),
    ("json", 400, "invalid_request"), ("secret", 422, "validation_failed")])
def test_transport_validation(tmp_path, monkeypatch, case, status, code):
    client, _, _, csrf, _ = setup(tmp_path, monkeypatch)
    kwargs = {}
    if case == "csrf": csrf = "wrong"
    if case == "etag": kwargs["etag"] = "*"
    if case == "missing_etag": kwargs["headers"] = {"If-Match": None}
    if case == "uuid": kwargs["key"] = str(uuid.uuid1())
    if case == "query": kwargs["query_string"] = {"site_id": "fake"}
    if case == "large": kwargs["raw"] = " " * 32769
    if case == "media": kwargs["headers"] = {"Content-Type": "text/plain"}
    if case == "json": kwargs["raw"] = '{"operation":"replace_secret","secret":"x","secret":"y"}'
    if case == "secret": kwargs["raw"] = '{"operation":"replace_secret","secret":""}'
    response = post(client, csrf, **kwargs)
    assert response.status_code == status and response.json["error"]["code"] == code


@pytest.mark.parametrize("secret_grant,authenticated,status", [(False, True, 403), (True, False, 401)])
def test_default_secret_denied_and_auth_required(tmp_path, monkeypatch, secret_grant, authenticated, status):
    client, _, runtime, csrf, _ = setup(tmp_path, monkeypatch, secret_grant=secret_grant, authenticated=authenticated)
    response = post(client, csrf)
    assert response.status_code == status
    if status == 403: assert response.json["error"]["code"] == "controller_secret_forbidden"


def test_session_grant_immutable_and_no_site_authority(tmp_path, monkeypatch):
    client, boot, runtime, csrf, _ = setup(tmp_path, monkeypatch, secret_grant=False)
    runtime.config = replace(runtime.config, global_capabilities=runtime.config.global_capabilities | {SECRET_WRITE_CAPABILITY})
    assert post(client, csrf).status_code == 403
    monkeypatch.setattr("app.admin_web.policy.AdminSiteContextResolver.resolve", lambda *_a: pytest.fail("site context"))
    assert client.get(API, base_url="https://localhost").status_code == 200


def test_missing_length_feature_disabled_and_internal_error_are_safe(tmp_path, monkeypatch):
    client, boot, runtime, csrf, _ = setup(tmp_path, monkeypatch)
    response = post(client, csrf, environ_overrides={"CONTENT_LENGTH": None})
    assert response.status_code == 411 and response.json["error"]["code"] == "length_required"
    runtime.settings_feature_enabled = False
    assert post(client, csrf).status_code == 404
    runtime.settings_feature_enabled = True
    def fail(*_args, **_kwargs):
        raise RuntimeError(SENTINEL)
    monkeypatch.setattr(boot.admin_context.secret_mutation_service, "mutate", fail)
    response = post(client, csrf)
    assert response.status_code == 500 and SENTINEL not in response.text


def test_http_noop_clear_conflict_and_invalid_secret_remain_write_only(tmp_path, monkeypatch):
    client, _, _, csrf, _ = setup(tmp_path, monkeypatch)
    key = str(uuid.uuid4())
    assert post(client, csrf, key=key).status_code == 201
    assert post(client, csrf, etag='"settings-g1"').status_code == 200
    different = json.dumps({"operation": "replace_secret", "secret": "different-disposable-value"})
    response = post(client, csrf, key=key, raw=different)
    assert response.status_code == 409 and response.json["error"]["code"] == "idempotency_conflict"
    assert "different-disposable-value" not in response.text
    response = post(client, csrf, etag='"settings-g1"', raw=json.dumps({"operation": "replace_secret", "secret": "x" * 4097}))
    assert response.status_code == 422
    clear = json.dumps({"operation": "clear_secret_override"})
    assert post(client, csrf, etag='"settings-g1"', raw=clear).status_code == 201
    assert post(client, csrf, etag='"settings-g2"', raw=clear).status_code == 200


def test_internal_decryption_category_is_not_a_public_secret_api_error(tmp_path, monkeypatch):
    client, _, _, csrf, filesystem = setup(tmp_path, monkeypatch)
    assert post(client, csrf).status_code == 201
    filesystem.master = bytes(32)
    response = post(client, csrf, etag='"settings-g1"')
    assert response.status_code == 503
    assert response.json["error"] == {"code": "controller_secret_store_unavailable", "details": []}
    assert SENTINEL not in response.text


def test_write_only_browser_source_contract():
    root = Path(__file__).resolve().parents[2]
    source = (root / "app/admin_web/static/controller_settings.js").read_text()
    template = (root / "app/admin_web/templates/admin/settings_controller.html").read_text()
    assert template.count('type="password"') == 2 and template.count('autocomplete="new-password"') == 2
    assert "secretNew.value !== secretRepeat.value" in source and "finally" in source and "wipeSecret();" in source
    assert "uncertainKey = key" in source and "uncertainKey = null" in source
    assert "response.status === 412" in source and 'await load("Client Secret saved.' in source
    for forbidden in ("localStorage", "sessionStorage", "console.", "innerHTML", "systemctl"):
        assert forbidden not in source + template
    assert "payload = value = body = null" in source
