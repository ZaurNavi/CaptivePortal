import logging
from dataclasses import replace
from types import SimpleNamespace
from pathlib import Path

import pytest
from flask import Flask

from app.admin_web.config import admin_web_config_from_settings, AdminWebConfigError
from app.admin_web.routes import create_admin_web_blueprint
from app.admin_web.query_service import (AdminQueryResponse, AdminQueryUnavailable, AdminRecognitionUnavailable,
    AdminQueryBusy, AdminQueryDeadline, AdminQueryNotFound, AdminQueryForbidden)
from app.admin_web.runtime import create_admin_web_runtime
from app.network_service_recognition.read_service import DeviceServiceRecognitionReadService
from app.network_service_recognition.models import ServiceBusy, ServiceUnavailable, ServiceDeadline
from app.network_metadata_projection.recognition_read_service import RecognitionProjectionSnapshotV2
from app.settings_control.features import AdminFeaturePlanV1
from app.settings_control.models import ResolvedSettingsSnapshot
from tests.network_service_recognition.support import bundle
from tests.network_service_recognition.test_summary import DEVICE, MAC, Projection, Source
from .conftest import SITE_ID, enabled_settings, login

PATH = f"/admin/api/v1/sites/{SITE_ID}/devices/{DEVICE}/service-intelligence"


@pytest.fixture
def service_app(admin_app):
    runtime = admin_app.extensions["admin_web_runtime"]
    runtime.config = replace(runtime.config, device_service_intelligence_enabled=True)
    query = runtime.query_service
    query._config = runtime.config
    query._devices = SimpleNamespace(get_device=lambda **kw: SimpleNamespace(canonical_mac=MAC))
    query._service_intelligence = DeviceServiceRecognitionReadService(
        Projection(RecognitionProjectionSnapshotV2(2, SITE_ID, DEVICE, "authoritative", "usable", None, DEVICE, (), 0)), Source(()), bundle())
    app = Flask(__name__); app.config["TESTING"] = True
    app.register_blueprint(create_admin_web_blueprint(runtime, logger=logging.getLogger("ni04-test")))
    app.extensions["admin_web_runtime"] = runtime
    return app


def test_api_exact_safe_dto_and_headers(service_app):
    client = service_app.test_client(); login(client)
    response = client.get(PATH, base_url="https://localhost")
    assert response.status_code == 200 and len(response.data) <= 16384
    value = response.json
    assert set(value) == {"api_version", "request_id", "site_id", "result", "page"}
    assert value["api_version"] == "admin.device.service-intelligence.v2" and value["page"] is None
    assert value["result"]["evidence_state"] == "no_supported_result_observed_with_sufficient_coverage"
    assert response.headers["Cache-Control"] == "no-store" and response.headers["Pragma"] == "no-cache"
    for private in (MAC, "peer_ip", "source_observation_ref", "edge_id", "sni", "knowledge_ref", "hostname"):
        assert private not in response.get_data(as_text=True)


@pytest.mark.parametrize("authenticated,site,device,suffix,body,status,code", [
    (False, SITE_ID, DEVICE, "", None, 401, "authentication_required"),
    (True, "invalid", DEVICE, "", None, 400, "invalid_request"),
    (True, "f" * 24, DEVICE, "", None, 403, "site_forbidden"),
    (True, SITE_ID, "invalid", "", None, 400, "invalid_request"),
    (True, SITE_ID, DEVICE, "?from_utc=anything", None, 400, "invalid_request"),
    (True, SITE_ID, DEVICE, "", b"{}", 400, "invalid_request"),
    (True, SITE_ID, DEVICE, "", None, 404, "not_found")])
def test_off_and_unauthorized_never_lookup_evidence(admin_app, monkeypatch, authenticated, site, device, suffix, body, status, code):
    query = admin_app.extensions["admin_web_runtime"].query_service
    monkeypatch.setattr(query, "device_service_intelligence", lambda *a, **kw: pytest.fail("unapproved query"))
    client = admin_app.test_client()
    if authenticated: login(client)
    response = client.get(f"/admin/api/v1/sites/{site}/devices/{device}/service-intelligence" + suffix,
        data=body, base_url="https://localhost")
    assert response.status_code == status and response.json["error"]["code"] == code
    assert response.json["api_version"] == "admin.device.service-intelligence.v2"


@pytest.mark.parametrize("error,status,code", [(AdminQueryBusy, 429, "concurrency_limit"),
    (AdminQueryDeadline, 503, "query_deadline"), (AdminQueryUnavailable, 503, "source_unavailable"),
    (AdminRecognitionUnavailable, 503, "recognition_unavailable"), (AdminQueryNotFound, 404, "not_found"),
    (AdminQueryForbidden, 403, "site_forbidden"), (RuntimeError, 500, "internal_error")])
def test_safe_failure_mappings(service_app, monkeypatch, caplog, error, status, code):
    def fail(*a, **kw): raise error("raw-private-canary")
    monkeypatch.setattr(service_app.extensions["admin_web_runtime"].query_service, "device_service_intelligence", fail)
    client = service_app.test_client(); login(client)
    response = client.get(PATH, base_url="https://localhost")
    assert response.status_code == status and response.json["error"]["code"] == code
    if status == 429: assert response.headers["Retry-After"] == "1"
    assert "raw-private-canary" not in response.get_data(as_text=True) + caplog.text


@pytest.mark.parametrize("error,mapped", [(ServiceBusy(), AdminQueryBusy), (ServiceDeadline(), AdminQueryDeadline),
    (ServiceUnavailable(), AdminQueryUnavailable), (ServiceUnavailable("recognition_unavailable"), AdminRecognitionUnavailable)])
def test_query_semantic_mapping_and_site_device_gateway(service_app, error, mapped):
    from app.admin_web.models import AdminPrincipal
    query = service_app.extensions["admin_web_runtime"].query_service
    calls = []
    def fail(site, device, mac, **kw):
        calls.append((site, device, mac)); raise error
    query._service_intelligence = SimpleNamespace(get_device_service_summary=fail)
    with pytest.raises(mapped): query.device_service_intelligence(AdminPrincipal("operator"), SITE_ID, DEVICE)
    assert calls == [(SITE_ID, DEVICE, MAC)]


def test_missing_device_before_optional_dependency(service_app):
    from app.admin_web.models import AdminPrincipal
    query = service_app.extensions["admin_web_runtime"].query_service
    query._service_intelligence = None
    query._devices = SimpleNamespace(get_device=lambda **kw: None)
    with pytest.raises(AdminQueryNotFound): query.device_service_intelligence(AdminPrincipal("operator"), SITE_ID, DEVICE)
    query._devices = SimpleNamespace(get_device=lambda **kw: SimpleNamespace(canonical_mac=MAC))
    with pytest.raises(AdminRecognitionUnavailable): query.device_service_intelligence(AdminPrincipal("operator"), SITE_ID, DEVICE)


def test_response_size_and_readonly_methods(service_app, monkeypatch):
    client = service_app.test_client(); login(client)
    for method in ("post", "put", "patch", "delete"):
        # Valid form transport passes the existing Admin POST preflight, then
        # the GET-only router rejects the method. Do not weaken that preflight.
        assert getattr(client, method)(PATH, data={"unsupported": "1"}, base_url="https://localhost").status_code == 405
    monkeypatch.setattr(service_app.extensions["admin_web_runtime"].query_service, "device_service_intelligence",
        lambda *a, **kw: AdminQueryResponse("x" * 16385))
    response = client.get(PATH, base_url="https://localhost")
    assert response.status_code == 503 and response.json["error"]["code"] == "response_too_large"


def test_page_feature_gate_independent_of_ni03(service_app, admin_app):
    for app, enabled in ((service_app, True), (admin_app, False)):
        client = app.test_client(); login(client)
        response = client.get(f"/admin/sites/{SITE_ID}/devices/{DEVICE}", base_url="https://localhost")
        text = response.get_data(as_text=True)
        assert response.status_code == 200
        assert ('id="device-service-intelligence"' in text) is enabled
        assert 'id="device-protocol-intelligence"' not in text
        if enabled: assert "Recognized Service-specific web hostname evidence" in text


@pytest.mark.parametrize("flag,expected", [("true", True), ("false", False)])
def test_flag_exact_default_off(flag, expected):
    assert admin_web_config_from_settings(enabled_settings(web_admin_device_service_intelligence_enabled=flag)).device_service_intelligence_enabled is expected
    assert admin_web_config_from_settings(enabled_settings()).device_service_intelligence_enabled is False


@pytest.mark.parametrize("flag", ["True", "1", "", True, None])
def test_invalid_flag_rejected(flag):
    with pytest.raises(AdminWebConfigError): admin_web_config_from_settings(enabled_settings(web_admin_device_service_intelligence_enabled=flag))


def test_invalid_bundle_optional_composition_does_not_change_admin(tmp_path, monkeypatch, caplog):
    from app.network_service_recognition import artifacts
    monkeypatch.setattr(artifacts, "load_local_bundle", lambda: (_ for _ in ()).throw(ValueError("private-file-canary")))
    settings = enabled_settings(web_admin_device_service_intelligence_enabled="true")
    plan = AdminFeaturePlanV1.from_snapshot(ResolvedSettingsSnapshot(None, settings, {}, {}, {}))
    runtime = create_admin_web_runtime(settings, SimpleNamespace(state="active", visit_service=object()),
        SimpleNamespace(repository=SimpleNamespace(config=SimpleNamespace(db_path=tmp_path / "registry.db"))),
        SimpleNamespace(repository=SimpleNamespace(db_path=tmp_path / "visits.db")),
        SimpleNamespace(_repository=SimpleNamespace(db_path=tmp_path / "observations.db")),
        logging.getLogger("ni04-composition"), feature_plan=plan)
    assert runtime.state == "active" and runtime.query_service is not None
    assert runtime.query_service._service_intelligence is None and "private-file-canary" not in caplog.text
