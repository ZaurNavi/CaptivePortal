import logging
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask

from app.admin_web.config import admin_web_config_from_settings, AdminWebConfigError
from app.admin_web.models import AdminPrincipal
from app.admin_web.query_service import (
    AdminQueryService, AdminQueryResponse, AdminQueryValidationError, AdminQueryForbidden,
    AdminQueryNotFound, AdminQueryUnavailable, AdminQueryDeadline, AdminQueryBusy,
)
from app.admin_web.routes import create_admin_web_blueprint
from app.admin_web.runtime import create_admin_web_runtime
from app.network_metadata_projection.models import ProjectionConfig
from app.network_protocol_intelligence.read_service import DeviceProtocolIntelligenceReadService
from app.network_protocol_intelligence.models import ProtocolUnavailable, ProtocolDeadline, ProtocolBusy, public_summary
from app.settings_control.features import AdminFeaturePlanV1
from app.settings_control.models import ResolvedSettingsSnapshot
from tests.network_protocol_intelligence.test_read_service import Reader, fact, summary, DEVICE, MAC
from .conftest import SITE_ID, enabled_settings, login

PATH = f"/admin/api/v1/sites/{SITE_ID}/devices/{DEVICE}/protocol-intelligence"


@pytest.fixture
def product_app(admin_app):
    runtime = admin_app.extensions["admin_web_runtime"]
    runtime.config = replace(runtime.config, device_protocol_intelligence_enabled=True)
    query = runtime.query_service
    query._config = runtime.config
    query._devices = SimpleNamespace(get_device=lambda **kwargs: SimpleNamespace(canonical_mac=MAC))
    query._protocol_intelligence = DeviceProtocolIntelligenceReadService(Reader())
    # Fixed narrow snapshot carries no time-dependent facts for API routing tests.
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(create_admin_web_blueprint(runtime, logger=logging.getLogger("ni03-test")))
    app.extensions["admin_web_runtime"] = runtime
    return app


def test_exact_api_success_headers_and_privacy(product_app):
    client = product_app.test_client(); login(client)
    response = client.get(PATH, base_url="https://localhost")
    assert response.status_code == 200
    value = response.json
    assert set(value) == {"api_version", "request_id", "site_id", "result", "page"}
    assert value["api_version"] == "admin.device.protocol-intelligence.v1"
    assert value["result"]["evidence_state"] == "empty"
    assert value["result"]["availability_state"] == "usable"
    assert value["page"] is None
    assert response.headers["Cache-Control"] == "no-store" and response.headers["Pragma"] == "no-cache"
    for private in ("client_mac", "peer_ip", "edge_id", "safe_reason", "attribution_binding_id", "sni"):
        assert private not in response.get_data(as_text=True)


@pytest.mark.parametrize("binding,identity", [("not_yet_registry_resolved", "pending"),
    ("registry_unavailable", "unavailable"), (None, "absent")])
def test_api_usable_projection_without_authoritative_identity_is_degraded(product_app, binding, identity):
    query = product_app.extensions["admin_web_runtime"].query_service
    query._protocol_intelligence = DeviceProtocolIntelligenceReadService(Reader(binding=binding, bound=None))
    client = product_app.test_client(); login(client)
    response = client.get(PATH, base_url="https://localhost")
    assert response.status_code == 200
    value = response.json["result"]
    assert value["availability_state"] == "degraded"
    assert value["coverage"]["projection_state"] == "usable"
    assert value["identity_binding_state"] == identity
    assert value["evidence_state"] == "identity_pending"
    assert value["freshness_state"] == "unavailable"


@pytest.mark.parametrize("authenticated,site,device,suffix,body,status,code", [
    (False, SITE_ID, DEVICE, "", None, 401, "authentication_required"),
    (True, "invalid", DEVICE, "", None, 400, "invalid_request"),
    (True, "f" * 24, DEVICE, "", None, 403, "site_forbidden"),
    (True, SITE_ID, "invalid", "", None, 400, "invalid_request"),
    (True, SITE_ID, "ABCD0000-0000-4000-8000-000000000001", "", None, 400, "invalid_request"),
    (True, SITE_ID, DEVICE, "?extra=1", None, 400, "invalid_request"),
    (True, SITE_ID, DEVICE, "", b"{}", 400, "invalid_request"),
    (True, SITE_ID, DEVICE, "", None, 404, "not_found"),
])
def test_feature_off_preserves_route_gate_precedence_no_read(admin_app, monkeypatch, authenticated, site, device, suffix, body, status, code):
    query = admin_app.extensions["admin_web_runtime"].query_service
    def forbidden(*args, **kwargs):
        pytest.fail("feature OFF must not call query, Device lookup or semantic/projection read")
    monkeypatch.setattr(query, "device_protocol_intelligence", forbidden)
    query._devices = SimpleNamespace(get_device=forbidden)
    query._protocol_intelligence = DeviceProtocolIntelligenceReadService(SimpleNamespace(read_protocol_evidence_snapshot=forbidden))
    client = admin_app.test_client()
    if authenticated: login(client)
    response = client.get(f"/admin/api/v1/sites/{site}/devices/{device}/protocol-intelligence" + suffix,
                          data=body, base_url="https://localhost")
    assert response.status_code == status
    assert response.json["error"]["code"] == code
    assert response.json["api_version"] == "admin.device.protocol-intelligence.v1"


def test_feature_off_capability_denial_precedes_input_and_feature_gate(admin_app, monkeypatch):
    runtime = admin_app.extensions["admin_web_runtime"]
    original = type(runtime.access_policy).authorize
    monkeypatch.setattr(type(runtime.access_policy), "authorize",
        lambda self, principal, capability, site: False if capability == "admin.read.device" else original(self, principal, capability, site))
    monkeypatch.setattr(runtime.query_service, "device_protocol_intelligence", lambda *a, **k: pytest.fail("feature OFF read"))
    client = admin_app.test_client(); login(client)
    response = client.get(PATH.replace(DEVICE, "invalid") + "?extra=1", base_url="https://localhost")
    assert response.status_code == 403 and response.json["error"]["code"] == "site_forbidden"
    assert response.json["api_version"] == "admin.device.protocol-intelligence.v1"


@pytest.mark.parametrize("suffix,body,status", [("?extra=1", None, 400), ("?a=1&a=2", None, 400), ("", b"{}", 400)])
def test_forbidden_request_inputs(product_app, suffix, body, status):
    client = product_app.test_client(); login(client)
    response = client.get(PATH + suffix, data=body, base_url="https://localhost")
    assert response.status_code == status and response.json["error"]["code"] == "invalid_request"
    assert response.json["api_version"] == "admin.device.protocol-intelligence.v1"


def test_authentication_and_site_boundary(product_app):
    client = product_app.test_client()
    assert client.get(PATH, base_url="https://localhost").status_code == 401
    login(client)
    query = product_app.extensions["admin_web_runtime"].query_service
    query._devices = SimpleNamespace(get_device=lambda **kwargs: (_ for _ in ()).throw(AssertionError("no cross-Site lookup")))
    assert client.get(PATH.replace(SITE_ID, "f" * 24), base_url="https://localhost").status_code == 403
    assert client.get(PATH.replace(SITE_ID, "invalid"), base_url="https://localhost").status_code == 400


@pytest.mark.parametrize("exc,status,code", [(AdminQueryBusy, 429, "concurrency_limit"),
    (AdminQueryDeadline, 503, "query_deadline"), (AdminQueryUnavailable, 503, "source_unavailable"),
    (AdminQueryNotFound, 404, "not_found"), (AdminQueryForbidden, 403, "site_forbidden"),
    (RuntimeError, 500, "internal_error")])
def test_api_safe_failure_mapping(product_app, monkeypatch, caplog, exc, status, code):
    query = product_app.extensions["admin_web_runtime"].query_service
    def fail(*args, **kwargs): raise exc("private-device-sentinel")
    monkeypatch.setattr(query, "device_protocol_intelligence", fail)
    client = product_app.test_client(); login(client)
    response = client.get(PATH, base_url="https://localhost")
    assert response.status_code == status and response.json["error"]["code"] == code
    assert response.json["api_version"] == "admin.device.protocol-intelligence.v1"
    if status == 429: assert response.headers["Retry-After"] == "1"
    assert "private-device-sentinel" not in response.get_data(as_text=True) + caplog.text
    assert DEVICE not in caplog.text


def test_response_cap(product_app, monkeypatch):
    query = product_app.extensions["admin_web_runtime"].query_service
    monkeypatch.setattr(query, "device_protocol_intelligence", lambda *a, **k: AdminQueryResponse("a" * 16385))
    client = product_app.test_client(); login(client)
    response = client.get(PATH, base_url="https://localhost")
    assert response.status_code == 503 and response.json["error"]["code"] == "response_too_large"


def test_device_lookup_precedes_optional_dependency_and_no_fallback(product_app):
    query = product_app.extensions["admin_web_runtime"].query_service
    principal = AdminPrincipal("operator")
    query._protocol_intelligence = None
    query._devices = SimpleNamespace(get_device=lambda **kwargs: None)
    with pytest.raises(AdminQueryNotFound): query.device_protocol_intelligence(principal, SITE_ID, DEVICE)
    query._devices = SimpleNamespace(get_device=lambda **kwargs: SimpleNamespace(canonical_mac=MAC))
    with pytest.raises(AdminQueryUnavailable): query.device_protocol_intelligence(principal, SITE_ID, DEVICE)
    with pytest.raises(AdminQueryValidationError): query.device_protocol_intelligence(principal, SITE_ID, DEVICE.upper().replace("1000", "ABCD", 1))


@pytest.mark.parametrize("error,mapped", [(ProtocolBusy, AdminQueryBusy), (ProtocolDeadline, AdminQueryDeadline),
    (ProtocolUnavailable, AdminQueryUnavailable)])
def test_real_query_translates_semantic_failures(product_app, error, mapped):
    query = product_app.extensions["admin_web_runtime"].query_service
    def fail(*a, **k): raise error()
    query._protocol_intelligence = SimpleNamespace(get_device_protocol_summary=fail)
    with pytest.raises(mapped): query.device_protocol_intelligence(AdminPrincipal("operator"), SITE_ID, DEVICE)


def test_page_section_and_script_only_enabled(product_app, admin_app):
    for app, enabled in [(product_app, True), (admin_app, False)]:
        client = app.test_client(); login(client)
        response = client.get(f"/admin/sites/{SITE_ID}/devices/{DEVICE}", base_url="https://localhost")
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert ('id="device-protocol-intelligence"' in html) is enabled
        assert ('filename=\"device_protocol_intelligence.js\"' in html or 'device_protocol_intelligence.js' in html) is enabled
        if enabled:
            for label in ("Network / Protocol Intelligence", "Recent protocol evidence derived from device-relative network metadata.", "device-protocol-refresh"):
                assert label in html
        else:
            response = client.get(PATH, base_url="https://localhost")
            assert response.status_code == 404


def test_flag_default_outer_gate_and_registry_independence():
    assert not admin_web_config_from_settings({}).device_protocol_intelligence_enabled
    settings = {"web_admin_enabled": "false", "web_admin_device_protocol_intelligence_enabled": "true"}
    config = admin_web_config_from_settings(settings)
    assert not config.enabled and config.device_protocol_intelligence_enabled
    plan = AdminFeaturePlanV1.from_snapshot(ResolvedSettingsSnapshot(None, settings, {}, {}, {}))
    assert plan.composition_settings(settings)["web_admin_device_protocol_intelligence_enabled"] == "true"
    from app.settings_control.definitions import SettingsDefinitionRegistry
    registry = SettingsDefinitionRegistry()
    assert all(item.settings_dict_key != "web_admin_device_protocol_intelligence_enabled" for item in registry)
    assert len(registry.for_domain("features")) == 17
    assert all(item.settings_dict_key != "web_admin_device_protocol_intelligence_enabled" for item in plan.registry)
    with pytest.raises(AdminWebConfigError):
        admin_web_config_from_settings({"web_admin_device_protocol_intelligence_enabled": "TRUE"})


@pytest.mark.parametrize("enabled,projection", [(False, "unused"), (True, "disabled"), (True, "invalid"), (True, "valid")])
def test_composition_uses_only_canonical_projection_config(admin_app, monkeypatch, tmp_path, enabled, projection):
    import app.network_metadata_projection.config as configuration
    import app.network_metadata_projection.read_service as reads
    values = enabled_settings(web_admin_device_protocol_intelligence_enabled="true" if enabled else "false")
    plan = AdminFeaturePlanV1.from_snapshot(ResolvedSettingsSnapshot(None, values, {}, {}, {}))
    calls = []
    path = str(tmp_path / "canonical.sqlite3")
    def get_config():
        calls.append("config")
        if projection == "invalid": raise ValueError("safe config failure")
        return ProjectionConfig(enabled=projection == "valid", db_path=path)
    original = reads.DeviceNetworkMetadataReadService
    def reader(**kwargs):
        calls.append(kwargs)
        return original(**kwargs)
    monkeypatch.setattr(configuration, "projection_config_from_env", get_config)
    monkeypatch.setattr(reads, "DeviceNetworkMetadataReadService", reader)
    runtime = create_admin_web_runtime(values, SimpleNamespace(state="active", visit_service=object()),
        SimpleNamespace(repository=SimpleNamespace(config=SimpleNamespace(db_path=tmp_path / "r"))),
        SimpleNamespace(repository=SimpleNamespace(db_path=tmp_path / "v")),
        SimpleNamespace(_repository=SimpleNamespace(db_path=tmp_path / "o")), logging.getLogger("ni03"), feature_plan=plan)
    assert runtime.state == "active" and runtime.feature_plan is plan and not Path(path).exists()
    if not enabled: assert calls == []
    elif projection == "invalid": assert calls == ["config"] and runtime.query_service._protocol_intelligence is None
    else:
        assert calls[1]["db_path"] == path and calls[1]["enabled"] is (projection == "valid")


def test_disabled_admin_never_composes_projection(monkeypatch):
    import app.network_metadata_projection.config as configuration
    monkeypatch.setattr(configuration, "projection_config_from_env", lambda: pytest.fail("outer gate"))
    values = {"web_admin_enabled": "false", "web_admin_device_protocol_intelligence_enabled": "true"}
    plan = AdminFeaturePlanV1.from_snapshot(ResolvedSettingsSnapshot(None, values, {}, {}, {}))
    runtime = create_admin_web_runtime(values, None, None, None, None, logging.getLogger("ni03"), feature_plan=plan)
    assert runtime.state == "disabled" and runtime.feature_plan is plan


def test_deployment_artifact_exact_and_no_settings_write_scope():
    root = Path(__file__).parents[2]
    assert (root / "deploy/network-metadata-projection/captive-portal-network-metadata-projection-read.conf").read_text() == "[Service]\nEnvironmentFile=-/etc/captive-portal/network-metadata-projection.env\n"
    document = (root / "deploy/network-metadata-projection/README.md").read_text()
    for token in ("20-network-metadata-projection-read.conf", "ACTIVATION=HOLD", "semantically", "/etc/default/captive-portal"):
        assert token in document


def test_denied_device_capability_hides_panel_and_forbids_api(product_app, monkeypatch):
    policy = product_app.extensions["admin_web_runtime"].access_policy
    original = type(policy).authorize
    monkeypatch.setattr(type(policy), "authorize", lambda self, principal, capability, site: False if capability == "admin.read.device" else original(self, principal, capability, site))
    client = product_app.test_client(); login(client)
    page = client.get(f"/admin/sites/{SITE_ID}/devices/{DEVICE}", base_url="https://localhost")
    assert page.status_code == 200 and b'device-protocol-intelligence' not in page.data
    assert client.get(PATH, base_url="https://localhost").status_code == 403


def test_shared_admin_slot_and_exact_device_not_found(product_app):
    query = product_app.extensions["admin_web_runtime"].query_service
    semaphore = query._slots
    for _ in range(query._config.max_concurrent_queries): assert semaphore.acquire(False)
    try:
        client = product_app.test_client(); login(client)
        response = client.get(PATH, base_url="https://localhost")
        assert response.status_code == 429 and response.headers["Retry-After"] == "1"
    finally:
        for _ in range(query._config.max_concurrent_queries): semaphore.release()
    requested = []
    def missing(**kwargs):
        requested.append(kwargs)
        return None
    query._devices = SimpleNamespace(get_device=missing)
    assert client.get(PATH, base_url="https://localhost").status_code == 404
    assert requested[0]["site_id"] == SITE_ID and requested[0]["device_id"] == DEVICE


@pytest.mark.parametrize("state,source,attribution,expected", [("attribution_unavailable", "usable", "degraded", "recent"),
    ("source_unavailable", "unavailable", "unknown", "stale"), ("capacity_halted", "degraded", "degraded", "recent")])
def test_committed_evidence_degraded_returns_200(product_app, state, source, attribution, expected):
    from datetime import datetime, timezone, timedelta
    from app.network_metadata.validation import ni_format_utc
    class CurrentReader:
        def read_protocol_evidence_snapshot(self, *args, **kwargs):
            return dict(runtime_state=state, binding_state="authoritative", bound_device_id=DEVICE,
                facts=({"edge_id": "a" * 64, "source_event_family": "dns", "event_at": ni_format_utc(datetime.now(timezone.utc) - timedelta(seconds=1))},))
    product_app.extensions["admin_web_runtime"].query_service._protocol_intelligence = DeviceProtocolIntelligenceReadService(CurrentReader())
    client = product_app.test_client(); login(client)
    response = client.get(PATH, base_url="https://localhost")
    assert response.status_code == 200
    value = response.json["result"]
    assert value["availability_state"] == "degraded" and value["freshness_state"] == expected
    assert value["coverage"]["source_state"] == source and value["coverage"]["attribution_state"] == attribution
