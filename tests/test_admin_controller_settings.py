import ast
import json
import logging
import uuid
from dataclasses import FrozenInstanceError, asdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask

import app.web.web as web
import run
from app.admin_web import create_admin_web_runtime
from app.admin_web.controller_settings import ControllerConfigurationReadService
from app.admin_web.models import AdminPrincipal
from app.admin_web.policy import AdminAccessPolicy, GLOBAL_SETTINGS_CAPABILITIES
from app.controllers.factory import create_controller
from app.controllers.omada_config import build_omada_runtime_config, public_omada_snapshot
from app.settings_control.definitions import SettingsDefinitionRegistry
from tests.admin_web.conftest import enabled_settings, login


SECRET = "AS02_SENTINEL_NEVER_DISCLOSE_z9X7!"
API = "/admin/api/v1/settings/controller"
PAGE = "/admin/settings/controller"


def settings(**overrides):
    values = enabled_settings(web_admin_settings_enabled="true")
    values.update(omada_url=" https://controller.invalid:8043/ ", omada_id=" installation ",
                  client_id=" application ", client_secret=" " + SECRET + " ", verify_ssl=False,
                  portal_counter_enabled=False, portal_counter_api_enabled=False,
                  public_traffic_enabled=False, auth_telemetry_enabled=False, capport_enabled=False)
    values.update(overrides)
    return values


def snapshot():
    return public_omada_snapshot(build_omada_runtime_config(settings()),
        frozenset({"OMADA_URL", "OMADA_ID", "OMADA_CLIENT_ID", "OMADA_CLIENT_SECRET"}))


def controller_app(*, enabled=True, projection=True, authenticated=True, policy=None, store="unavailable"):
    runtime = create_admin_web_runtime(settings(web_admin_settings_enabled=enabled),
        None, None, None, None, logging.getLogger("as02"),
        settings_control=SimpleNamespace(feature_enabled=enabled, store_state=store,
                                        read_service=None, mutation_service=None),
        controller_public_snapshot=snapshot() if projection else None)
    if policy is not None:
        runtime.access_policy = policy
        from app.admin_web.routes import create_admin_web_blueprint
        runtime.blueprint = create_admin_web_blueprint(runtime, logger=logging.getLogger("as02"))
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(runtime.blueprint)
    client = app.test_client()
    if authenticated:
        assert login(client).status_code == 302
    return app, client, runtime


def get(client, path=API):
    return client.get(path, base_url="https://localhost")


def test_config_normalization_immutability_and_injected_provider(monkeypatch, caplog):
    mapping = settings()
    config = build_omada_runtime_config(mapping)
    assert config.controller_url == "https://controller.invalid:8043"
    assert config.controller_id == "installation" and config.client_id == "application"
    assert config.client_secret == SECRET
    with pytest.raises(FrozenInstanceError):
        config.client_secret = "different"
    mapping["client_secret"] = "changed-after-resolution"
    monkeypatch.setattr("app.settings.get_settings", lambda: pytest.fail("second settings read"))
    with caplog.at_level(logging.DEBUG):
        provider = create_controller(config)
    assert provider._client_secret == SECRET and provider._omada_url == config.controller_url
    assert provider._verify_ssl is False
    for value in (repr(config), str(config), repr(provider), str(provider), caplog.text):
        assert SECRET not in value
    import app.controllers.omada as omada
    assert not hasattr(omada, "get_settings")
    with pytest.raises(TypeError):
        create_controller()
    with pytest.raises(TypeError):
        omada.OmadaProvider()


def test_public_projection_provenance_membership_and_secret_absence():
    config = build_omada_runtime_config(settings())
    explicit = public_omada_snapshot(config, frozenset({"OMADA_URL", "OMADA_CLIENT_SECRET"}))
    default = public_omada_snapshot(config, frozenset())
    assert explicit.controller_url == default.controller_url
    assert explicit.controller_url_source == "environment"
    assert default.controller_url_source == "repository_default"
    assert explicit.controller_id_source == "repository_default"
    assert explicit.client_secret_source == "environment"
    assert explicit.tls_certificate_verification_source == "repository_default"
    assert SECRET not in json.dumps(asdict(explicit)) + repr(explicit) + str(explicit)
    assert set(asdict(explicit)) == {"controller_url", "controller_url_source", "controller_id",
        "controller_id_source", "client_id", "client_id_source", "client_secret_presence",
        "client_secret_source", "tls_certificate_verification", "tls_certificate_verification_source"}
    with pytest.raises(FrozenInstanceError):
        explicit.controller_url = "changed"
    with pytest.raises(ValueError):
        ControllerConfigurationReadService(config)


def test_api_exact_contract_no_secret_or_store_dependency(monkeypatch, caplog):
    _, client, runtime = controller_app()
    monkeypatch.setattr("requests.sessions.Session.request", lambda *a, **k: pytest.fail("network"))
    monkeypatch.setattr("app.settings.get_settings", lambda: pytest.fail("request settings read"))
    response = get(client)
    assert response.status_code == 200
    model = response.json
    assert model["api_version"] == "admin.settings.controller.v1"
    assert str(uuid.UUID(model["request_id"])) == model["request_id"]
    assert model["scope"] == {"type": "global"}
    assert model["resource"] == {"type": "omada_controller", "scope": "installation"}
    assert model["management_mode"] == "deployment_controlled"
    assert model["configuration_state"] == "configured"
    assert model["fields"] == {
        "controller_url": {"display_label": "Controller URL", "value_type": "url",
            "effective_value": "https://controller.invalid:8043", "effective_source": "environment"},
        "controller_id": {"display_label": "Controller ID", "value_type": "string",
            "effective_value": "installation", "effective_source": "environment"},
        "client_id": {"display_label": "Client / Application ID", "value_type": "string",
            "effective_value": "application", "effective_source": "environment"},
        "client_secret": {"display_label": "Client Secret", "value_type": "secret_presence",
            "effective_presence": "configured", "effective_source": "environment"},
        "tls_certificate_verification": {"display_label": "TLS certificate verification", "value_type": "boolean",
            "effective_value": False, "effective_source": "repository_default"}}
    assert runtime.settings_store_state == "unavailable" and runtime.controller_settings_state == "active"
    assert response.mimetype == "application/json"
    assert response.headers["Cache-Control"] == "no-store" and response.headers["Pragma"] == "no-cache"
    page = get(client, PAGE)
    assert page.status_code == 200
    assert SECRET not in response.text + page.text + caplog.text
    assert "data-site-id" not in page.text and "/admin/sites/" not in page.text
    assert "controller_settings.js" in page.text
    assert "filename=settings.js" not in page.text and 'src="/admin/static/settings.js"' not in page.text
    assert 'src="/admin/static/admin.js"' not in page.text
    assert "Save changes" not in page.text


@pytest.mark.parametrize("authenticated,enabled,projection,status,code", [
    (False, True, True, 401, "authentication_required"),
    (True, False, True, 404, "feature_disabled"),
    (True, True, False, 503, "controller_settings_read_unavailable"),
])
def test_bounded_api_errors(authenticated, enabled, projection, status, code, caplog):
    _, client, _ = controller_app(authenticated=authenticated, enabled=enabled, projection=projection)
    response = get(client)
    assert response.status_code == status and response.json["error"]["code"] == code
    assert SECRET not in response.text + caplog.text
    if not enabled:
        assert get(client, PAGE).status_code == 404


def test_query_rejection_and_no_mutation_route():
    app, client, _ = controller_app()
    for query in ("site_id=fake", "foo=1", "foo=1&foo=2"):
        response = get(client, API + "?" + query)
        assert response.status_code == 400 and response.json["error"]["code"] == "invalid_request"
    rules = [rule for rule in app.url_map.iter_rules() if rule.rule == API]
    assert len(rules) == 1 and rules[0].methods == {"GET", "HEAD", "OPTIONS"}
    assert get(client, "/admin/api/v1/sites/fake/settings/controller").status_code != 200


@pytest.mark.parametrize("body,content_type", [
    (b"body", "application/octet-stream"),
    (b"{not-json", "application/json"),
    (SECRET.encode(), "text/plain"),
])
def test_controller_get_rejects_nonempty_body_without_parsing_or_reading_config(body, content_type, caplog):
    _, client, runtime = controller_app()
    service = runtime.controller_settings_read_service
    read = Mock(side_effect=AssertionError("body must be rejected before configuration read"))
    runtime.controller_settings_read_service = SimpleNamespace(read=read)
    response = client.get(API, data=body, content_type=content_type, base_url="https://localhost")
    assert response.status_code == 400 and response.json["error"]["code"] == "invalid_request"
    assert response.json["api_version"] == "admin.settings.controller.v1"
    assert response.headers["Cache-Control"] == "no-store" and response.headers["Pragma"] == "no-cache"
    assert SECRET not in response.text + caplog.text
    read.assert_not_called()
    runtime.controller_settings_read_service = service
    assert get(client).status_code == 200


def test_controller_canonical_heading_provider_and_status_wording():
    _, client, _ = controller_app()
    page = get(client, PAGE)
    assert page.status_code == 200
    assert "<h1>Controller</h1>" in page.text
    assert "Omada Controller" in page.text
    assert "Loading Controller configuration…" in page.text
    assert "<h1>Controller Settings</h1>" not in page.text
    _, client, _ = controller_app(projection=False)
    unavailable = get(client, PAGE)
    assert unavailable.status_code == 200
    assert "Controller configuration is unavailable." in unavailable.text
    root = Path(__file__).resolve().parents[1]
    source = (root / "app/admin_web/static/controller_settings.js").read_text(encoding="utf-8")
    assert 'state.textContent = "Read-only effective startup configuration.";' in source
    assert 'state.textContent = "Controller configuration is unavailable.";' in source


class SelectivePolicy:
    def __init__(self, allowed):
        self.allowed = allowed

    def authorize_global(self, principal, capability):
        return capability in self.allowed

    def authorize(self, *args):
        return False


@pytest.mark.parametrize("general,controller", [(True, True), (True, False), (False, True), (False, False)])
def test_independent_capabilities_and_navigation(general, controller):
    allowed = set()
    if general:
        allowed.add("admin.read.settings.global")
    if controller:
        allowed.add("admin.read.settings.controller")
    _, client, _ = controller_app(policy=SelectivePolicy(allowed))
    response = get(client, PAGE if controller or not general else "/admin/settings")
    if general or controller:
        assert response.status_code == 200
        assert ('href="/admin/settings"' in response.text) == general
        assert ('href="/admin/settings/controller"' in response.text) == controller
        target = "/admin/settings" if general else PAGE
        assert f'href="{target}">Settings</a>' in response.text
    else:
        assert response.status_code == 403
    if not controller:
        assert get(client).json["error"]["code"] == "controller_settings_forbidden"


def test_global_policy_and_no_site_resolution(monkeypatch):
    policy = AdminAccessPolicy(frozenset())
    assert policy.authorize_global(AdminPrincipal("operator"), "admin.read.settings.controller")
    assert not policy.authorize_global(AdminPrincipal("operator", "site_operator"), "admin.read.settings.controller")
    assert not policy.authorize_global(None, "admin.read.settings.controller")
    assert "admin.write.settings.controller" not in GLOBAL_SETTINGS_CAPABILITIES
    _, client, _ = controller_app()
    monkeypatch.setattr("app.admin_web.policy.AdminSiteContextResolver.resolve", lambda *a: pytest.fail("site"))
    monkeypatch.setattr("app.admin_web.policy.AdminSiteContextResolver.default", lambda *a: pytest.fail("site"))
    assert get(client).status_code == get(client, PAGE).status_code == 200


def test_read_failure_is_sanitized_and_provider_still_usable(monkeypatch, caplog):
    provider = create_controller(build_omada_runtime_config(settings()))
    _, client, runtime = controller_app()
    def fail(*args):
        raise RuntimeError(SECRET)
    runtime.controller_settings_read_service = SimpleNamespace(read=fail)
    response = get(client)
    assert response.status_code == 503 and SECRET not in response.text + caplog.text
    assert provider._client_id == "application"
    app = web.create_app(controller=provider, settings=settings(), portal_counter_service=None,
                         public_traffic_service=None, portal_evidence_sink=None, client_hints_probe=None)
    assert app.test_client().get("/").status_code != 500
    monkeypatch.setattr("app.admin_web.controller_settings.ControllerConfigurationReadService", fail)
    runtime = create_admin_web_runtime(settings(), None, None, None, None, logging.getLogger("as02"),
                                      controller_public_snapshot=snapshot())
    assert runtime.controller_settings_state == "unavailable" and runtime.blueprint is not None
    assert SECRET not in caplog.text


def test_internal_response_failure_is_sanitized():
    _, client, runtime = controller_app()
    runtime.controller_settings_read_service = SimpleNamespace(read=lambda _: {"invalid": object()})
    response = get(client)
    assert response.status_code == 500 and response.json["error"]["code"] == "internal_error"
    assert response.json["api_version"] == "admin.settings.controller.v1"


def test_frontend_read_only_and_allowlist_unchanged():
    root = Path(__file__).resolve().parents[1]
    source = (root / "app/admin_web/static/controller_settings.js").read_text(encoding="utf-8")
    for forbidden in ("innerHTML", "localStorage", "sessionStorage", "POST", "systemctl", "console."):
        assert forbidden not in source
    assert source.count("fetch(") == 1 and f'fetch("{API}"' in source
    assert 'method: "GET"' in source and 'credentials: "same-origin"' in source
    assert "Configured" in source and "Not configured" in source
    registry = tuple(SettingsDefinitionRegistry())
    assert len(registry) == 12
    assert all("OMADA" not in item.key for item in registry)


@pytest.mark.parametrize("injected_settings", [True, False])
def test_create_app_fallback_same_local_mapping_once(monkeypatch, injected_settings):
    values = settings()
    getter = Mock(return_value=values)
    factory = Mock(return_value=object())
    monkeypatch.setattr(web, "get_settings", getter)
    monkeypatch.setattr(web, "create_controller", factory)
    web.create_app(controller=None, settings=values if injected_settings else None,
        portal_counter_service=None, public_traffic_service=None, portal_evidence_sink=None, client_hints_probe=None)
    assert getter.call_count == (0 if injected_settings else 1)
    factory.assert_called_once()
    assert factory.call_args.args == (build_omada_runtime_config(values),)


def test_create_app_injected_controller_does_not_build_or_create(monkeypatch):
    def forbidden(*args):
        pytest.fail("injected controller rebuilt")
    monkeypatch.setattr(web, "build_omada_runtime_config", forbidden)
    monkeypatch.setattr(web, "create_controller", forbidden)
    monkeypatch.setattr(web, "get_settings", forbidden)
    web.create_app(controller=object(), settings=settings(), portal_counter_service=None,
        public_traffic_service=None, portal_evidence_sink=None, client_hints_probe=None)


def test_no_zero_argument_production_factory_calls():
    root = Path(__file__).resolve().parents[1]
    for path in (root / "run.py", root / "app/web/web.py"):
        parsed = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(parsed):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "create_controller":
                assert len(node.args) == 1


@pytest.mark.parametrize("projection_failure", [False, True])
def test_main_shared_config_single_environment_capture_and_projection_isolation(monkeypatch, projection_failure):
    # Composition-only unit test: no real startup identity, service or network execution.
    from tests.visitor_registry.test_snapshot_runtime import _prepare_main
    for name in ("_visitor_snapshot_collector", "_visitor_registry", "_pending_session_cleaner",
                 "_observation_foundation", "_current_state_runtime", "_analytics_runtime", "_admin_web_runtime"):
        monkeypatch.setattr(run, name, None)
    _, controller, _, _, app, observed = _prepare_main(monkeypatch)
    monkeypatch.setattr(run, "capture_loaded_artifact_identity",
                        lambda _: SimpleNamespace(json_line=lambda: "unit-composition-identity"))
    values = settings(host="127.0.0.1", port=8088, debug=False, web_admin_settings_enabled=False)
    monkeypatch.setattr(run, "get_settings", Mock(return_value=values))
    captured = {}
    bootstrap = run.bootstrap_settings_control
    def capture_bootstrap(**kwargs):
        captured["environment_names"] = kwargs["explicit_environment_names"]
        return bootstrap(**kwargs)
    monkeypatch.setattr(run, "bootstrap_settings_control", capture_bootstrap)
    def factory(config):
        captured["config"] = config
        return controller
    monkeypatch.setattr(run, "create_controller", factory)
    projector = public_omada_snapshot
    def project(config, names):
        assert config is captured["config"]
        assert names is captured["environment_names"]
        if projection_failure:
            raise RuntimeError(SECRET)
        return projector(config, names)
    monkeypatch.setattr(run, "public_omada_snapshot", project)
    def admin(actual_app, actual_settings, registry, context, public_snapshot):
        captured["public_snapshot"] = public_snapshot
    monkeypatch.setattr(run, "_configure_admin_web", admin)
    run.main()
    run.get_settings.assert_called_once()
    assert captured["config"].client_secret == SECRET
    assert observed["app_controller"] is controller and observed["collector_provider"] is controller
    assert app.run_calls
    if projection_failure:
        assert captured["public_snapshot"] is None
    else:
        assert captured["public_snapshot"].controller_url == captured["config"].controller_url
