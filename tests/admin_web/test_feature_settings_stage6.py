"""GLOBAL Features HTTP contract and plan-owned route exposure."""
import json
import logging
import uuid
from types import SimpleNamespace

import pytest
from flask import Flask
from app.admin_web import create_admin_web_runtime
from app.admin_web.capabilities import DEFAULT_GLOBAL_CAPABILITIES
from app.settings_control.bootstrap import bootstrap_settings_control
from app.settings_control.definitions import SettingsDefinitionRegistry
from .conftest import enabled_settings, login, SITE_ID
from tests.settings_control import CONTROLLER_BASE

READ = "admin.read.settings.features"
WRITE = "admin.write.settings.features"
API = "/admin/api/v1/settings/features"
KEY = "WEB_ADMIN_TRAFFIC_HISTORY_ENABLED"


def feature_app(tmp_path, capabilities=(READ, WRITE), *, settings_enabled=True, adopted=True, **values):
    settings = {**CONTROLLER_BASE, **enabled_settings(
        web_admin_settings_enabled="true" if settings_enabled else "false",
        web_admin_global_capabilities=",".join(capabilities or ("admin.read.settings.global",)),
        settings_db_path=str(tmp_path / "settings.sqlite3"), **values)}
    boot = bootstrap_settings_control(base_settings=settings, explicit_environment_names=set(),
        logger=logging.getLogger("stage6-http"))
    runtime = create_admin_web_runtime(boot.runtime_settings, None, None, None, None,
        logging.getLogger("stage6-http"), settings_control=boot.admin_context, feature_plan=boot.feature_plan)
    assert runtime.feature_plan is boot.feature_plan
    analytics = SimpleNamespace(feature_plan=boot.feature_plan, historical_source_mode="base")
    if adopted and boot.activation_service:
        boot.activation_service.adopt(boot.runtime_settings, runtime, analytics, feature_plan=boot.feature_plan)
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(runtime.blueprint)
    client = app.test_client()
    assert login(client).status_code == 302
    csrf = client.get("/admin/api/v1/session", base_url="https://localhost").json["result"]["csrf_token"]
    return client, runtime, boot, csrf


def post(client, csrf, *, body=None, key=None, etag='"settings-g0"', **options):
    return client.post(API + "/generations", data=body if body is not None else json.dumps(
        {"changes": [{"key": KEY, "operation": "set", "value": True}]}),
        content_type="application/json", headers={"X-CSRF-Token": csrf,
        "If-Match": etag, "Idempotency-Key": key or str(uuid.uuid4())},
        base_url="https://localhost", **options)


@pytest.mark.parametrize("capabilities,read_status,write_status", [
    ((), 403, 403), ((WRITE,), 403, 403), ((READ,), 200, 403), ((READ, WRITE), 200, 201)])
def test_independent_global_permissions(tmp_path, capabilities, read_status, write_status):
    client, _, _, csrf = feature_app(tmp_path, capabilities)
    assert client.get(API, base_url="https://localhost").status_code == read_status
    assert post(client, csrf).status_code == write_status
    assert READ not in DEFAULT_GLOBAL_CAPABILITIES and WRITE not in DEFAULT_GLOBAL_CAPABILITIES


def test_exact_ordered_read_and_receipt_shapes_and_cas(tmp_path, monkeypatch):
    client, runtime, boot, csrf = feature_app(tmp_path)
    def forbidden(*_args, **_kwargs):
        pytest.fail("Features must not resolve secret or source")
    secret_resolution = boot.admin_context.mutation_service.secret_repository.resolve
    monkeypatch.setattr(boot.admin_context.mutation_service.secret_repository, "resolve", forbidden)
    response = client.get(API, base_url="https://localhost")
    assert response.status_code == 200
    assert response.headers["ETag"] == '"settings-g0"'
    assert response.headers["Cache-Control"] == "no-store" and response.headers["Pragma"] == "no-cache"
    assert set(response.json) == set("api_version request_id scope resource store_state configured_generation effective_generation etag restart_required pending_setting_count features".split())
    expected = set("key feature_id display_label description group control_kind public_value_type presentation_type scope_type scope_id editable secret_class default_value base_source base_value persisted_override_value configured_value configured_source effective_value effective_source pending_value configured_generation effective_generation activation_state apply_requirement activation_target parent_feature_keys configured_feature_state configured_blocked_by_feature_keys effective_feature_state effective_blocked_by_feature_keys validation last_changed_at last_changed_by".split())
    rows = response.json["features"]
    assert [row["key"] for row in rows] == [item.key for item in SettingsDefinitionRegistry().for_domain("features")]
    for row in rows:
        assert set(row) == expected and row["validation"] == {"type": "boolean"}
        for field in ("default_value", "base_value", "persisted_override_value", "configured_value", "effective_value", "pending_value"):
            assert row[field] is None or type(row[field]) is bool
    receipt_key = str(uuid.uuid4())
    changed = post(client, csrf, key=receipt_key)
    assert changed.status_code == 201 and changed.headers["ETag"] == '"settings-g1"'
    assert set(changed.json) == set("api_version request_id scope resource changed changed_keys configured_generation effective_generation activation_state restart_required".split())
    assert changed.json["api_version"] == "admin.settings.features.mutation.v1"
    assert changed.json["resource"] == {"type": "admin_product_features", "scope": "installation"}
    assert changed.json["changed_keys"] == [KEY]
    assert post(client, csrf, key=receipt_key).json == changed.json
    assert post(client, csrf).status_code == 412
    current = client.get(API, base_url="https://localhost").json
    history = next(row for row in current["features"] if row["key"] == KEY)
    assert history["configured_feature_state"] == "dormant_parent_disabled"
    assert history["configured_value"] is True and history["pending_value"] is True
    assert history["effective_value"] is False
    assert not runtime.config.traffic_history_enabled  # No request-time hot adoption.
    # Different domains use the same generation CAS but distinct receipt namespace.
    monkeypatch.setattr(boot.admin_context.mutation_service.secret_repository, "resolve", secret_resolution)
    from tests.settings_control.test_features_stage6 import mutate
    assert mutate(boot, [{"key": "WEB_ADMIN_DEVICE_PAGE_SIZE", "operation": "set", "value": 120}],
                  domain="general", generation=1, key=receipt_key).status == 201
    replay = post(client, csrf, key=receipt_key)
    assert replay.json == changed.json and replay.headers["ETag"] == '"settings-g1"'


@pytest.mark.parametrize("body", [
    '{"changes":[],"changes":[]}', '{"changes":[{"key":"WEB_ADMIN_TRAFFIC_HISTORY_ENABLED","key":"WEB_ADMIN_TRAFFIC_ENABLED","operation":"set","value":true}]}',
    '{"changes":[{"key":"WEB_ADMIN_TRAFFIC_ENABLED","operation":"set","value":NaN}]}',
    '{"changes":[{"key":"WEB_ADMIN_TRAFFIC_ENABLED","operation":"set","value":Infinity}]}',
    '{"changes":[{"key":"WEB_ADMIN_TRAFFIC_ENABLED","operation":"set","value":-Infinity}]}',
    '{"changes":[{"key":"WEB_ADMIN_TRAFFIC_ENABLED","operation":"set","value":"true"}]}',
    '{"changes":[{"key":"WEB_ADMIN_TRAFFIC_ENABLED","operation":"set","value":1}]}',
    '{"changes":[{"key":"WEB_ADMIN_ENABLED","operation":"set","value":true}]}',
    '{"changes":[]}', '{"changes":[{"key":"WEB_ADMIN_TRAFFIC_ENABLED","operation":"clear_override","value":false}]}',
    '[]', '{', '{"changes":[{"key":"WEB_ADMIN_TRAFFIC_ENABLED","operation":"set","value":true}],"site_id":"fake"}',
])
def test_strict_json_never_mutates(tmp_path, body):
    client, _, boot, csrf = feature_app(tmp_path)
    response = post(client, csrf, body=body)
    assert response.status_code == 400 and response.json["error"]["code"] == "invalid_request"
    assert response.json["api_version"] == "admin.settings.features.mutation.v1"
    assert boot.admin_context.read_service.repository.configured() == (0, {})


@pytest.mark.parametrize("query,body", [("?site_id=" + SITE_ID, None), ("?unknown=1", None), ("", "{}")])
def test_read_rejects_query_and_body(tmp_path, query, body):
    client, _, _, _ = feature_app(tmp_path)
    response = client.get(API + query, data=body, base_url="https://localhost")
    assert response.status_code == 400


def test_global_shell_no_site_or_other_controller_and_unavailable_tab(tmp_path, monkeypatch):
    client, runtime, boot, csrf = feature_app(tmp_path, (READ,))
    from app.admin_web.policy import AdminSiteContextResolver
    def forbidden(*_args, **_kwargs):
        pytest.fail("Global Features must not resolve Site")
    monkeypatch.setattr(AdminSiteContextResolver, "default", forbidden)
    monkeypatch.setattr(AdminSiteContextResolver, "resolve", forbidden)
    page = client.get("/admin/settings/features", base_url="https://localhost")
    assert page.status_code == 200 and b"features_settings.js" in page.data
    assert b"admin.js" not in page.data and b'/settings.js"' not in page.data
    assert b"data-site-id" not in page.data
    assert b'href="/admin/settings/features"' in page.data
    assert b'href="/admin/settings/controller"' not in page.data
    assert b'href="/admin/settings"' not in page.data
    assert b'data-write-allowed="false"' in page.data
    boot.admin_context.read_service.repository.db_path = str(tmp_path / "missing" / "settings.sqlite3")
    assert client.get(API, base_url="https://localhost").status_code == 503
    assert client.get("/admin/settings/features", base_url="https://localhost").status_code == 200


def test_disabled_store_feature_and_headers(tmp_path):
    client, _, _, csrf = feature_app(tmp_path, settings_enabled=False)
    assert client.get(API, base_url="https://localhost").status_code == 404
    assert post(client, csrf).status_code == 404
    assert client.get("/admin/settings/features", base_url="https://localhost").status_code == 404


def test_headers_canonical_uuid_csrf_and_noop(tmp_path):
    client, _, boot, csrf = feature_app(tmp_path)
    assert post(client, "invalid").status_code == 400
    assert post(client, csrf, etag="*").status_code == 400
    assert post(client, csrf, key="{00000000-0000-1000-8000-000000000001}").status_code == 400
    assert post(client, csrf, body=" " * 32769).status_code == 413
    missing = client.post(API + "/generations", json={"changes": []},
        headers={"X-CSRF-Token": csrf}, base_url="https://localhost")
    assert missing.status_code == 428
    noop = post(client, csrf, body=json.dumps({"changes": [{"key": KEY, "operation": "clear_override"}]}))
    assert noop.status_code == 200 and noop.json["changed"] is False
    with boot.admin_context.read_service.repository.transaction() as db:
        assert db.execute("SELECT COUNT(*) FROM settings_generations").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM settings_mutation_audit").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM settings_idempotency WHERE mutation_domain='features'").fetchone()[0] == 1


@pytest.mark.parametrize("key", [
    "00000000-0000-1000-8000-000000000001",
    "00000000-0000-3000-8000-000000000001",
    "00000000-0000-5000-8000-000000000001",
    "00000000-0000-0000-0000-000000000000",
])
def test_features_accepts_canonical_non_v4_uuid_and_replays(tmp_path, key):
    assert str(uuid.UUID(key)) == key and uuid.UUID(key).version != 4
    client, _, boot, csrf = feature_app(tmp_path)
    changed = post(client, csrf, key=key)
    assert changed.status_code == 201
    replay = post(client, csrf, key=key)
    assert replay.status_code == 201 and replay.json == changed.json
    with boot.admin_context.read_service.repository.transaction() as db:
        assert db.execute("SELECT COUNT(*) FROM settings_generations").fetchone()[0] == 2
        assert db.execute("SELECT idempotency_key FROM settings_idempotency WHERE mutation_domain='features'").fetchone()[0] == key


@pytest.mark.parametrize("suffix", [
    "current-state/clients/summary", "current-state/clients", "current-state/aps/summary", "current-state/aps",
    "current-traffic/summary", "current-traffic/aps", "home-activity/today", "home-activity/selected?period=today",
    "home-activity/range-preview", "home/health", "traffic/history?range=24h",
    "traffic/online-guests/current", "traffic/completed-sessions", "traffic/evidence",
    "devices/11111111-1111-4111-8111-111111111111/current"])
def test_disabled_and_dormant_routes_fail_before_source(tmp_path, suffix):
    client, runtime, _, _ = feature_app(tmp_path,
        web_admin_home_traffic_enabled="true", web_admin_home_activity_enabled="true",
        web_admin_home_activity_site_context_json="invalid dormant prerequisite",
        web_admin_traffic_history_enabled="true", web_admin_traffic_statistics_enabled="true",
        web_admin_traffic_peak_enabled="true", web_admin_traffic_by_ap_enabled="true",
        web_admin_traffic_ap_share_enabled="true", web_admin_traffic_online_guests_enabled="true",
        web_admin_traffic_completed_sessions_enabled="true", web_admin_traffic_evidence_enabled="true")
    class Forbidden:
        def __getattr__(self, name):
            pytest.fail("disabled product source query: " + name)
    runtime.query_service = Forbidden()
    response = client.get("/admin/api/v1/sites/" + SITE_ID + "/" + suffix, base_url="https://localhost")
    assert response.status_code == 404
    assert response.json["error"]["code"] == "not_found"


def test_absent_source_does_not_change_adoption_or_features(tmp_path):
    client, runtime, boot, _ = feature_app(tmp_path)
    assert runtime.query_service is None
    response = client.get(API, base_url="https://localhost").json
    assert response["effective_generation"] == 0
    assert all(row["activation_state"] == "active" for row in response["features"])
    assert all(row["effective_feature_state"] == "disabled" for row in response["features"])
    assert boot.admin_context.read_service._adopted
