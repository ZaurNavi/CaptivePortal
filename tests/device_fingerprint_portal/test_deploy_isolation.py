from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock
import pytest
import requests

from app.device_fingerprint_portal.config import portal_config_from_env
from app.device_fingerprint_portal.models import PortalEvidenceConfigError
from app.device_fingerprint_portal.producer import PortalEvidenceProducer
from app.device_fingerprint_portal.runtime import PortalEvidenceRuntime
from .test_runtime import Clock, candidate, session
from .test_producer import Session, Response


def custom():
    p = "DEVICE_FINGERPRINT_PORTAL_"
    return portal_config_from_env({p + "ENABLED": "true", p + "SITE_ID": "a" * 24,
        p + "PRODUCER_ID": "lab-portal-02", p + "CAPTURE_SOURCE_ID": "lab-portal-http-02",
        p + "GUEST_CIDRS": "10.20.0.0/24", p + "ALLOWED_SSIDS": "Guest",
        p + "CA_CERT_PATH": "/lab/portal-ca.crt", p + "CREDENTIAL_PATH": "/lab/portal.bearer",
        p + "EVIDENCE_BASE_URL": "https://evidence.example:9443/api/internal/device-fingerprint/v1"})


@pytest.mark.parametrize("status", [200, 401, 403])
def test_T07_T08_T09_portal_exact_transport_tuple_and_verified_ca_injection(monkeypatch, status):
    import ssl
    config = custom()
    def read_credential(path, **_kwargs):
        assert path.as_posix() == config.credential_path
        return "b" * 32
    monkeypatch.setattr(Path, "read_text", read_credential)
    verify_ca = Mock()
    monkeypatch.setattr(ssl, "create_default_context", verify_ca)
    transport = Session(Response(status))
    producer = PortalEvidenceProducer(config, session=transport)
    clock = Clock()
    runtime = PortalEvidenceRuntime(config, producer=producer, now=clock.now, monotonic=clock.monotonic)
    assert runtime.try_submit(session(site_id=config.site_id, client_ip="10.20.0.7", ssid=None), candidate(clock))
    event = runtime.queue.get_nowait().event
    assert event["site_id"] == config.site_id and event["capture_source_id"] == config.capture_source_id
    result = producer.deliver_evidence([event])
    assert result.status == ("success" if status == 200 else "permanent")
    assert len(transport.calls) == 1
    args, options = transport.calls[0]
    assert args == (config.evidence_base_url + "/evidence/batch",)
    assert options["json"] == {"producer_id": config.producer_id, "events": [event]}
    assert options["verify"] == config.ca_cert_path and options["headers"]["Authorization"] == "Bearer " + "b" * 32
    verify_ca.assert_called_once_with(cafile=config.ca_cert_path)
    # Mock status proves no identity fallback, not actual receiver registration/SAN admission.


def test_T03_T09_site_ip_ssid_filter_remains_exact_and_ssid_optional():
    config, clock = custom(), Clock()
    runtime = PortalEvidenceRuntime(config, producer=Mock(), now=clock.now, monotonic=clock.monotonic)
    for changes in ({"site_id": "b" * 24}, {"client_ip": "192.168.8.10"}, {"ssid": "guest"}):
        values = dict(site_id=config.site_id, client_ip="10.20.0.7", ssid="Guest")
        values.update(changes)
        assert not runtime.try_submit(session(**values), candidate(clock))
    assert runtime.try_submit(session(site_id=config.site_id, client_ip="10.20.0.7", ssid=None), candidate(clock))


@pytest.mark.parametrize("mode", ["disabled", "invalid", "delivery_failed"])
@pytest.mark.parametrize("context", ["omada_external_portal", "capport_login"])
def test_T10_optional_producer_never_changes_guest_auth(mode, context, monkeypatch):
    import app.web.web as web
    from app.auth.manager import AuthSessionManager
    from app.models import Result
    from tests.test_proxy_headers import CapturingExecutor
    manager, executor = AuthSessionManager(), CapturingExecutor()
    runtime = PortalEvidenceRuntime(custom(), producer=Mock())
    runtime.start = Mock()  # No worker thread or external I/O in this Auth-isolation fixture.
    runtime.producer.deliver_evidence.side_effect = requests.ConnectionError("synthetic unavailable")
    monkeypatch.setattr(web, "PortalEvidenceRuntime", lambda *_a, **_k: runtime)
    if mode == "invalid":
        def invalid():
            raise PortalEvidenceConfigError("synthetic invalid configuration")
        monkeypatch.setattr(web, "portal_config_from_env", invalid)
    else:
        monkeypatch.setattr(web, "portal_config_from_env", lambda: portal_config_from_env({}) if mode == "disabled" else custom())
    controller = Mock()
    controller.get_clients.return_value = Result.ok(data={"clients": [{"client_ip": "10.20.0.7",
        "client_mac": "AA:BB:CC:DD:EE:77", "ssid": None}]})
    controller.get_client.return_value = Result.ok(data={"authStatus": 0, "active": True})
    settings = dict(portal_counter_enabled=False, portal_counter_db_path="unused.db",
        portal_counter_timezone="Asia/Baku", portal_counter_api_enabled=False, auth_telemetry_enabled=False,
        capport_enabled=True, capport_site_id="a" * 24, capport_public_base_url="https://portal.example",
        capport_allowed_client_networks=("10.20.0.0/24",), capport_api_path="/capport/api",
        capport_login_path="/capport/login", capport_client_cache_ttl_seconds=2, capport_failure_cache_ttl_seconds=2)
    monkeypatch.setattr(web, "get_settings", lambda: settings)
    monkeypatch.setattr(web, "auth_manager", manager)
    monkeypatch.setattr(web, "auth_executor", executor)
    app = web.create_app(controller=controller, portal_counter_service=None)
    uri = "/capport/login" if context == "capport_login" else (
        "/?site=" + "a" * 24 + "&clientMac=AA:BB:CC:DD:EE:77&clientIp=10.20.0.7")
    response = app.test_client().get(uri, environ_base={"REMOTE_ADDR": "10.20.0.7"},
        base_url="https://portal.example", headers={"User-Agent": "Mozilla/5.0 (Android 14) Chrome/120 Mobile"})
    assert response.status_code == 200
    stored = manager.get_by_client("a" * 24, "AA:BB:CC:DD:EE:77")
    assert stored is not None and stored.current_run_number == 1 and len(executor.submissions) == 1
    if context == "capport_login":
        controller.get_clients.assert_called_once_with("a" * 24)
        controller.get_client.assert_called_once_with("a" * 24, "AA:BB:CC:DD:EE:77")
    else:
        controller.get_clients.assert_not_called()
        controller.get_client.assert_not_called()
    if mode == "delivery_failed":
        runtime.start.assert_called_once()
        assert runtime.process_once() == 1
        assert runtime.producer.deliver_evidence.call_count == 1
        assert manager.get_by_client("a" * 24, "AA:BB:CC:DD:EE:77") is stored
    else:
        runtime.start.assert_not_called()
        assert app.extensions["portal_evidence_runtime"] is None


def test_T08_portal_tls_failure_uses_ca_and_is_contained(monkeypatch):
    import ssl
    config = custom()
    monkeypatch.setattr(Path, "read_text", lambda *_a, **_k: "b" * 32)
    monkeypatch.setattr(ssl, "create_default_context", lambda **kwargs: None)
    transport = Session(requests.exceptions.SSLError("synthetic peer trust failure"))
    result = PortalEvidenceProducer(config, session=transport).deliver_evidence([{"safe": True}])
    assert result.status == "transient"
    assert transport.calls[0][1]["verify"] == config.ca_cert_path
