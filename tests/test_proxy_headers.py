import threading
from unittest.mock import Mock, patch

from flask import jsonify, request

import app.web.web as web_module
from app.device_fingerprint_portal.config import portal_config_from_env
from app.device_fingerprint_portal.models import DeliveryResult
from app.device_fingerprint_portal.runtime import PortalEvidenceRuntime


class NoopExecutor:
    def submit(self, *args, **kwargs):
        return None


def create_test_app(portal_evidence_sink=None, *, automatic=False):
    settings = {
        "portal_counter_enabled": False,
        "portal_counter_db_path": "unused.db",
        "portal_counter_timezone": "Asia/Baku",
        "portal_counter_api_enabled": False,
        "auth_telemetry_enabled": False,
        "capport_enabled": False,
    }
    with (
        patch.object(
            web_module,
            "get_settings",
            return_value=settings,
        ),
        patch.object(
            web_module,
            "create_controller",
            return_value=object(),
        ),
        patch.object(
            web_module,
            "auth_executor",
            NoopExecutor(),
        ),
    ):
        arguments = {"portal_counter_service": None}
        if not automatic:
            arguments["portal_evidence_sink"] = portal_evidence_sink
        app = web_module.create_app(**arguments)

    @app.get("/_proxy_state")
    def proxy_state():
        return jsonify(
            {
                "remote_addr": request.remote_addr,
                "scheme": request.scheme,
                "host": request.host,
            }
        )

    app.config["TESTING"] = True
    return app


def test_external_portal_guard_precedes_extractor_and_valid_request_plumbs_candidate():
    sink = object()
    app = create_test_app(sink)
    handler = app.extensions["portal_entry_handler"]
    candidate = object()
    handler.open_portal = Mock(return_value="opened")
    extractor = Mock(return_value=candidate)
    with patch.object(web_module, "extract_portal_evidence_candidate", extractor):
        rejected = app.test_client().get("/?clientMac=AA:BB:CC:DD:EE:01")
        accepted = app.test_client().get("/?site=site-1&clientMac=AA:BB:CC:DD:EE:01", headers={"User-Agent": "Firefox/120"})
    assert rejected.status_code == 400
    assert accepted.status_code == 200
    extractor.assert_called_once()
    handler.open_portal.assert_called_once()
    assert handler.open_portal.call_args.kwargs["portal_evidence_candidate"] is candidate


def test_external_portal_extractor_failure_is_contained():
    app = create_test_app(object())
    handler = app.extensions["portal_entry_handler"]
    handler.open_portal = Mock(return_value="opened")
    with patch.object(web_module, "extract_portal_evidence_candidate", side_effect=RuntimeError("secret")):
        response = app.test_client().get("/?site=site-1&clientMac=AA:BB:CC:DD:EE:02")
    assert response.status_code == 200
    handler.open_portal.assert_called_once()


def test_injected_sink_bypasses_auto_composition():
    sink = object()
    with patch.object(web_module, "portal_config_from_env", side_effect=AssertionError("must not read auto config")):
        app = create_test_app(sink)
    assert app.extensions["portal_evidence_sink"] is sink
    assert app.extensions["portal_evidence_runtime"] is None


def test_auto_disabled_and_invalid_config_are_fail_open():
    disabled = web_module.portal_config_from_env({})
    with patch.object(web_module, "portal_config_from_env", return_value=disabled):
        app = create_test_app(automatic=True)
    assert app.extensions["portal_evidence_sink"] is None
    with patch.object(web_module, "portal_config_from_env", side_effect=ValueError("invalid secret-free config")):
        invalid = create_test_app(automatic=True)
    assert invalid.extensions["portal_evidence_sink"] is None


def test_auto_worker_start_failure_is_fail_open():
    enabled = web_module.portal_config_from_env({"DEVICE_FINGERPRINT_PORTAL_ENABLED": "true"})
    runtime = Mock()
    runtime.start.side_effect = RuntimeError("thread unavailable")
    with (
        patch.object(web_module, "portal_config_from_env", return_value=enabled),
        patch.object(web_module, "PortalEvidenceRuntime", return_value=runtime),
    ):
        app = create_test_app(automatic=True)
    assert app.extensions["portal_evidence_sink"] is None
    runtime.start.assert_called_once_with()


def test_auto_enabled_composes_and_starts_exact_runtime():
    enabled = web_module.portal_config_from_env({"DEVICE_FINGERPRINT_PORTAL_ENABLED": "true"})
    runtime = Mock()
    with (
        patch.object(web_module, "portal_config_from_env", return_value=enabled),
        patch.object(web_module, "PortalEvidenceRuntime", return_value=runtime) as constructor,
    ):
        app = create_test_app(automatic=True)
    constructor.assert_called_once()
    runtime.start.assert_called_once_with()
    assert app.extensions["portal_evidence_sink"] is runtime
    assert app.extensions["portal_evidence_runtime"] is runtime


def test_blocked_background_delivery_does_not_block_portal_response():
    entered = threading.Event(); release = threading.Event()

    class BlockingProducer:
        def deliver_evidence(self, events):
            list(events); entered.set(); release.wait()
            return DeliveryResult("success", 0, 200)

        def deliver_source_health(self, events):
            list(events); return DeliveryResult("success", 0, 200)

    runtime = PortalEvidenceRuntime(portal_config_from_env({}), producer=BlockingProducer())
    runtime.start()
    request_result = {}

    def request_portal():
        with app.test_client() as client:
            request_result["response"] = client.get(
                "/?site=6a64f17630da7c70d232187a&clientMac=AA:BB:CC:DD:EE:90&clientIp=192.168.8.10",
                headers={"User-Agent": "Mozilla/5.0 (Android 14) Chrome/120 Mobile"},
            )

    try:
        app = create_test_app(runtime)
        request_thread = threading.Thread(target=request_portal)
        request_thread.start()
        assert entered.wait(timeout=1)
        request_thread.join(timeout=1)
        assert not request_thread.is_alive()
        assert request_result["response"].status_code == 200
        assert not release.is_set()
    finally:
        release.set()
        if "request_thread" in locals():
            request_thread.join(timeout=2)
        runtime.stop()
        runtime.thread.join(timeout=2)


def test_one_forwarded_hop_sets_real_client_ip():
    app = create_test_app()

    response = app.test_client().get(
        "/_proxy_state",
        headers={
            "X-Forwarded-For": "192.168.1.143",
        },
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )

    assert response.get_json()["remote_addr"] == "192.168.1.143"


def test_forwarded_scheme_host_and_port_are_applied():
    app = create_test_app()

    response = app.test_client().get(
        "/_proxy_state",
        headers={
            "X-Forwarded-For": "192.168.1.143",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": (
                "captivportal-navi.duckdns.org"
            ),
            "X-Forwarded-Port": "443",
        },
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    payload = response.get_json()

    assert payload["scheme"] == "https"
    assert payload["host"] == "captivportal-navi.duckdns.org"
