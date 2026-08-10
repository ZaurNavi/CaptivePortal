import json
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit
from unittest.mock import Mock, patch

from flask import Flask

from app.capport.models import (
    CapportClient,
    CapportConfig,
    CapportState,
)
from app.capport.routes import (
    CAPPORT_MEDIA_TYPE,
    create_capport_blueprint,
)
from app.capport.service import CapportService
from app.controllers.omada import OmadaProvider
from app.models import Result
from app.web.portal_entry import PortalClientContext, PortalEntryResult


class NoopTelemetry:
    def safe_emit_system(self, *args, **kwargs):
        return True


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def config():
    return CapportConfig.from_settings(
        {
            "host": "127.0.0.1",
            "capport_site_id": "site-1",
            "capport_public_base_url": "https://portal.example",
            "capport_api_path": "/capport/api",
            "capport_login_path": "/capport/login",
            "capport_allowed_client_networks": (
                "192.168.1.0/24",
            ),
            "capport_client_cache_ttl_seconds": 2,
            "capport_failure_cache_ttl_seconds": 2,
        }
    )


def state(
    *,
    captive=True,
    found=True,
    allowed=True,
    lookup_failed=False,
    auth_status=0,
):
    client = None
    if found:
        client = CapportClient(
            site_id="site-1",
            client_ip="192.168.1.10",
            client_mac="AA:BB:CC:DD:EE:FF",
            auth_status=auth_status,
            active=True,
        )
    return CapportState(
        allowed=allowed,
        captive=captive,
        client_found=found,
        client_ip="192.168.1.10",
        client=client,
        reason="TEST",
        cache_hit=False,
        lookup_failed=lookup_failed,
        response_time_ms=1.0,
    )


def app_for(service, handler=None):
    template_dir = (
        Path(__file__).parents[1] / "app" / "web" / "templates"
    )
    app = Flask(__name__, template_folder=str(template_dir))
    handler = handler or Mock()
    app.register_blueprint(
        create_capport_blueprint(
            service=service,
            portal_entry_handler=handler,
            config=config(),
            telemetry=NoopTelemetry(),
        )
    )
    app.config["TESTING"] = True
    return app, handler


def javascript_constant(page, name):
    match = re.search(
        rf"const {re.escape(name)}\s*=\s*(.*?);",
        page,
        re.DOTALL,
    )
    assert match is not None, f"Missing JavaScript constant: {name}"
    return json.loads(match.group(1).strip())


def discovery_remaining_seconds(page):
    return javascript_constant(
        page,
        "discoveryInitial",
    )["remaining_seconds"]


def test_unauthorized_api_response_has_rfc_media_and_no_store():
    service = Mock()
    service.resolve.return_value = state(captive=True)
    app, handler = app_for(service)

    response = app.test_client().get(
        "/capport/api",
        environ_base={"REMOTE_ADDR": "192.168.1.10"},
    )

    assert response.status_code == 200
    assert response.content_type == CAPPORT_MEDIA_TYPE
    assert response.headers["Cache-Control"] == "private, no-store"
    assert response.get_json() == {
        "captive": True,
        "user-portal-url": "https://portal.example/capport/login",
    }
    assert response.location is None
    assert "Set-Cookie" not in response.headers
    handler.open_portal.assert_not_called()


def test_authorized_api_response_is_not_captive():
    service = Mock()
    service.resolve.return_value = state(
        captive=False,
        auth_status=2,
    )
    app, _ = app_for(service)

    response = app.test_client().get(
        "/capport/api",
        environ_base={"REMOTE_ADDR": "192.168.1.10"},
    )

    assert response.status_code == 200
    assert response.get_json()["captive"] is False


def test_ip_mac_only_list_plus_get_client_returns_not_captive_api():
    omada = object.__new__(OmadaProvider)
    omada._omada_url = "https://controller.example"
    omada._omada_id = "controller-id"
    omada._verify_ssl = True
    omada._get_token = Mock(
        return_value=Result.ok(data={"token": "test-token"})
    )
    list_response = Mock(status_code=200)
    list_response.json.return_value = {
        "errorCode": 0,
        "result": {
            "data": [
                {
                    "ip": "192.168.1.10",
                    "mac": "aa-bb-cc-dd-ee-ff",
                }
            ]
        },
    }
    detail_response = Mock(status_code=200)
    detail_response.json.return_value = {
        "errorCode": 0,
        "result": {
            "authStatus": 2,
            "active": True,
        },
    }
    service = CapportService(
        omada,
        config(),
        NoopTelemetry(),
    )
    app, _ = app_for(service)

    with patch(
        "app.controllers.omada.requests.get",
        side_effect=[list_response, detail_response],
    ):
        response = app.test_client().get(
            "/capport/api",
            environ_base={"REMOTE_ADDR": "192.168.1.10"},
        )

    assert response.status_code == 200
    assert response.get_json()["captive"] is False


def test_not_found_and_timeout_states_are_fail_safe():
    service = Mock()
    app, _ = app_for(service)
    client = app.test_client()

    service.resolve.return_value = state(found=False, captive=True)
    not_found = client.get(
        "/capport/api",
        environ_base={"REMOTE_ADDR": "192.168.1.10"},
    )
    service.resolve.return_value = state(
        found=False,
        captive=True,
        lookup_failed=True,
    )
    timeout = client.get(
        "/capport/api",
        environ_base={"REMOTE_ADDR": "192.168.1.10"},
    )

    assert not_found.status_code == 200
    assert not_found.get_json()["captive"] is True
    assert timeout.status_code == 200
    assert timeout.get_json()["captive"] is True


def test_outside_network_returns_403():
    service = Mock()
    service.resolve.return_value = state(
        found=False,
        allowed=False,
    )
    app, handler = app_for(service)

    response = app.test_client().get(
        "/capport/api",
        environ_base={"REMOTE_ADDR": "10.0.0.1"},
    )

    assert response.status_code == 403
    assert response.get_json() == {"error": "client_not_allowed"}
    handler.open_portal.assert_not_called()


def test_api_is_read_only_and_never_enters_authorization_flow():
    controller = Mock()
    controller.get_clients.return_value = Result.ok(
        data={
            "clients": [
                {
                    "client_ip": "192.168.1.10",
                    "client_mac": "AA:BB:CC:DD:EE:FF",
                }
            ],
        }
    )
    controller.get_client.return_value = Result.ok(
        data={
            "authStatus": 0,
            "active": True,
        }
    )
    service = CapportService(
        controller,
        config(),
        NoopTelemetry(),
    )
    app, handler = app_for(service)

    response = app.test_client().get(
        "/capport/api",
        environ_base={"REMOTE_ADDR": "192.168.1.10"},
    )

    assert response.status_code == 200
    controller.authorize.assert_not_called()
    controller.unauthorize.assert_not_called()
    handler.open_portal.assert_not_called()


def test_login_found_client_calls_shared_entry_handler():
    service = Mock()
    service.resolve_for_login.return_value = state()
    handler = Mock()
    handler.open_portal.return_value = ("opened", 200)
    app, _ = app_for(service, handler)

    response = app.test_client().get(
        "/capport/login",
        environ_base={"REMOTE_ADDR": "192.168.1.10"},
    )

    assert response.status_code == 200
    handler.open_portal.assert_called_once_with(
        PortalClientContext(
            site_id="site-1",
            client_mac="AA:BB:CC:DD:EE:FF",
            client_ip="192.168.1.10",
        )
    )


def test_login_refreshes_not_found_state_from_immediate_api_poll():
    controller = Mock()
    controller.get_clients.side_effect = [
        Result.ok(data={"clients": []}),
        Result.ok(
            data={
                "clients": [
                    {
                        "client_ip": "192.168.1.10",
                        "client_mac": "AA:BB:CC:DD:EE:FF",
                    }
                ],
            }
        ),
    ]
    controller.get_client.return_value = Result.ok(
        data={"authStatus": 0, "active": True}
    )
    service = CapportService(
        controller,
        config(),
        NoopTelemetry(),
        sleep=lambda _seconds: None,
    )
    handler = Mock()
    handler.open_portal.return_value = ("opened", 200)
    app, _ = app_for(service, handler)
    client = app.test_client()

    api_response = client.get(
        "/capport/api",
        environ_base={"REMOTE_ADDR": "192.168.1.10"},
    )
    login_response = client.get(
        "/capport/login",
        environ_base={"REMOTE_ADDR": "192.168.1.10"},
    )

    assert api_response.get_json()["captive"] is True
    assert login_response.status_code == 200
    handler.open_portal.assert_called_once()
    assert controller.get_clients.call_count == 2
    controller.get_client.assert_called_once()


def test_login_uses_new_mac_after_identity_snapshot_expires():
    controller = Mock()
    controller.get_clients.side_effect = [
        Result.ok(
            data={
                "clients": [
                    {
                        "client_ip": "192.168.1.10",
                        "client_mac": "AA:BB:CC:DD:EE:01",
                    }
                ]
            }
        ),
        Result.ok(
            data={
                "clients": [
                    {
                        "client_ip": "192.168.1.10",
                        "client_mac": "AA:BB:CC:DD:EE:02",
                    }
                ]
            }
        ),
    ]
    controller.get_client.side_effect = [
        Result.ok(data={"authStatus": 2, "active": True}),
        Result.ok(data={"authStatus": 0, "active": True}),
    ]
    clock = FakeClock()
    service = CapportService(
        controller,
        config(),
        NoopTelemetry(),
        monotonic=clock.monotonic,
    )
    handler = Mock()
    handler.open_portal.return_value = ("opened", 200)
    app, _ = app_for(service, handler)
    client = app.test_client()

    api_response = client.get(
        "/capport/api",
        environ_base={"REMOTE_ADDR": "192.168.1.10"},
    )
    clock.advance(3)
    login_response = client.get(
        "/capport/login",
        environ_base={"REMOTE_ADDR": "192.168.1.10"},
    )

    assert api_response.get_json()["captive"] is False
    assert login_response.status_code == 200
    handler.open_portal.assert_called_once_with(
        PortalClientContext(
            site_id="site-1",
            client_mac="AA:BB:CC:DD:EE:02",
            client_ip="192.168.1.10",
        )
    )


def test_login_not_found_renders_discovery_and_starts_no_worker():
    service = Mock()
    service.resolve_for_login.return_value = state(found=False)
    handler = Mock()
    app, _ = app_for(service, handler)

    with patch("app.capport.routes.time.time", return_value=1000):
        response = app.test_client().get(
            "/capport/login",
            environ_base={"REMOTE_ADDR": "192.168.1.10"},
        )

    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "<html" in page
    assert "CAPPORT_DISCOVERY" in page
    assert "DISCOVERING_CLIENT" in page
    assert response.headers["Cache-Control"] == "private, no-store"
    assert response.headers["Pragma"] == "no-cache"
    assert javascript_constant(
        page,
        "discoveryInitial",
    )["auto_retry"] is True
    assert discovery_remaining_seconds(page) == 60
    handler.open_portal.assert_not_called()


def test_json_login_not_found_returns_bounded_discovery_contract():
    service = Mock()
    service.resolve_for_login.return_value = state(found=False)
    handler = Mock()
    app, _ = app_for(service, handler)

    with patch("app.capport.routes.time.time", return_value=1000):
        response = app.test_client().get(
            "/capport/login?source=capport",
            headers={"Accept": "application/json"},
            environ_base={"REMOTE_ADDR": "192.168.1.10"},
        )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["mode"] == "CAPPORT_DISCOVERY"
    assert payload["state"] == "DISCOVERING_CLIENT"
    assert payload["terminal"] is False
    assert payload["retryable"] is True
    assert payload["auto_retry"] is True
    assert payload["remaining_seconds"] == 60
    assert payload["retry_interval_ms"] == 2000
    assert "wait_until=1060" in payload["retry_url"]
    assert "wait_until" not in payload["restart_url"]
    assert "session_id" not in payload
    assert response.headers["Cache-Control"] == "private, no-store"
    assert response.headers["Pragma"] == "no-cache"
    handler.prepare_portal.assert_not_called()
    handler.open_portal.assert_not_called()


def test_json_expired_deadline_stops_auto_retry_but_keeps_restart():
    service = Mock()
    service.resolve_for_login.return_value = state(found=False)
    handler = Mock()
    app, _ = app_for(service, handler)

    with patch("app.capport.routes.time.time", return_value=1000):
        response = app.test_client().get(
            "/capport/login?source=capport&wait_until=990",
            headers={"Accept": "application/json"},
            environ_base={"REMOTE_ADDR": "192.168.1.10"},
        )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["auto_retry"] is False
    assert payload["retryable"] is True
    assert payload["remaining_seconds"] == 0
    assert "wait_until=990" in payload["retry_url"]
    assert "source=capport" in payload["restart_url"]
    assert "wait_until" not in payload["restart_url"]
    handler.prepare_portal.assert_not_called()


def test_explicit_application_json_is_required_for_json_mode():
    service = Mock()
    service.resolve_for_login.return_value = state(found=False)
    app, _ = app_for(service, Mock())
    client = app.test_client()

    explicit = client.get(
        "/capport/login",
        headers={"Accept": "application/json, */*"},
        environ_base={"REMOTE_ADDR": "192.168.1.10"},
    )
    wildcard = client.get(
        "/capport/login",
        headers={"Accept": "*/*"},
        environ_base={"REMOTE_ADDR": "192.168.1.10"},
    )
    disabled = client.get(
        "/capport/login",
        headers={"Accept": "application/json;q=0"},
        environ_base={"REMOTE_ADDR": "192.168.1.10"},
    )

    assert explicit.is_json
    assert "<html" in wildcard.get_data(as_text=True)
    assert "<html" in disabled.get_data(as_text=True)


def test_login_expired_discovery_deadline_stops_auto_retry():
    service = Mock()
    service.resolve_for_login.return_value = state(found=False)
    handler = Mock()
    app, _ = app_for(service, handler)

    with patch("app.capport.routes.time.time", return_value=1000):
        response = app.test_client().get(
            "/capport/login?source=capport&wait_until=990",
            environ_base={"REMOTE_ADDR": "192.168.1.10"},
        )

    page = response.get_data(as_text=True)
    discovery = javascript_constant(page, "discoveryInitial")
    retry_url = discovery["retry_url"]
    restart_url = discovery["restart_url"]

    assert response.status_code == 200
    assert discovery["auto_retry"] is False
    assert discovery_remaining_seconds(page) == 0
    assert ("wait_until", "990") in parse_qsl(
        urlsplit(retry_url).query,
        keep_blank_values=True,
    )
    assert ("source", "capport") in parse_qsl(
        urlsplit(restart_url).query,
        keep_blank_values=True,
    )
    assert "wait_until" not in urlsplit(restart_url).query
    handler.open_portal.assert_not_called()


def test_login_preserves_or_clamps_discovery_deadline():
    service = Mock()
    service.resolve_for_login.return_value = state(found=False)
    app, handler = app_for(service, Mock())
    client = app.test_client()

    with patch("app.capport.routes.time.time", return_value=1000):
        future = client.get(
            "/capport/login?tag=a&tag=b&wait_until=1030",
            environ_base={"REMOTE_ADDR": "192.168.1.10"},
        )
        excessive = client.get(
            "/capport/login?wait_until=4600",
            environ_base={"REMOTE_ADDR": "192.168.1.10"},
        )

    future_page = future.get_data(as_text=True)
    future_retry_url = javascript_constant(
        future_page,
        "discoveryInitial",
    )["retry_url"]
    future_query = parse_qsl(
        urlsplit(future_retry_url).query,
        keep_blank_values=True,
    )
    excessive_page = excessive.get_data(as_text=True)
    excessive_retry_url = javascript_constant(
        excessive_page,
        "discoveryInitial",
    )["retry_url"]

    assert future_query == [
        ("tag", "a"),
        ("tag", "b"),
        ("wait_until", "1030"),
    ]
    assert discovery_remaining_seconds(future_page) == 30
    assert parse_qsl(urlsplit(excessive_retry_url).query) == [
        ("wait_until", "1060")
    ]
    assert discovery_remaining_seconds(excessive_page) == 60
    handler.open_portal.assert_not_called()


def test_login_controller_failure_returns_controlled_503():
    service = Mock()
    service.resolve_for_login.return_value = state(
        found=False,
        lookup_failed=True,
    )
    handler = Mock()
    app, _ = app_for(service, handler)

    response = app.test_client().get(
        "/capport/login",
        environ_base={"REMOTE_ADDR": "192.168.1.10"},
    )

    assert response.status_code == 503
    page = response.get_data(as_text=True)
    assert "<html" in page
    assert "временно недоступен" in page
    assert "const initialState" in page
    assert javascript_constant(page, "initialState")["state"] == "FAILED"
    handler.open_portal.assert_not_called()


def test_json_lookup_failure_preserves_deadline_and_is_retryable():
    service = Mock()
    service.resolve_for_login.return_value = state(
        found=False,
        lookup_failed=True,
    )
    handler = Mock()
    app, _ = app_for(service, handler)

    with patch("app.capport.routes.time.time", return_value=1000):
        active = app.test_client().get(
            "/capport/login?wait_until=1030",
            headers={"Accept": "application/json"},
            environ_base={"REMOTE_ADDR": "192.168.1.10"},
        )
        expired = app.test_client().get(
            "/capport/login?wait_until=990",
            headers={"Accept": "application/json"},
            environ_base={"REMOTE_ADDR": "192.168.1.10"},
        )

    active_payload = active.get_json()
    expired_payload = expired.get_json()
    assert active.status_code == 503
    assert active_payload["error"] == "lookup_failed"
    assert active_payload["state"] == "DISCOVERING_CLIENT"
    assert active_payload["auto_retry"] is True
    assert active_payload["remaining_seconds"] == 30
    assert "wait_until=1030" in active_payload["retry_url"]
    assert expired.status_code == 503
    assert expired_payload["auto_retry"] is False
    assert expired_payload["remaining_seconds"] == 0
    assert expired_payload["restart_url"] == "/capport/login"
    assert "session_id" not in active_payload
    assert "session_id" not in expired_payload
    handler.prepare_portal.assert_not_called()


def test_login_outside_network_returns_403():
    service = Mock()
    service.resolve_for_login.return_value = state(
        found=False,
        allowed=False,
    )
    handler = Mock()
    app, _ = app_for(service, handler)

    response = app.test_client().get(
        "/capport/login",
        environ_base={"REMOTE_ADDR": "10.0.0.1"},
    )

    assert response.status_code == 403
    handler.open_portal.assert_not_called()


def test_json_login_outside_network_is_terminal_discovery_error():
    service = Mock()
    service.resolve_for_login.return_value = state(
        found=False,
        allowed=False,
    )
    handler = Mock()
    app, _ = app_for(service, handler)

    response = app.test_client().get(
        "/capport/login",
        headers={"Accept": "application/json"},
        environ_base={"REMOTE_ADDR": "10.0.0.1"},
    )

    payload = response.get_json()
    assert response.status_code == 403
    assert payload == {
        "mode": "CAPPORT_DISCOVERY",
        "state": "FAILED",
        "status": "FAILED",
        "progress": 100,
        "terminal": True,
        "retryable": False,
        "auto_retry": False,
        "remaining_seconds": 0,
        "retry_interval_ms": 2000,
        "retry_url": None,
        "restart_url": None,
        "error": "client_not_allowed",
    }
    assert "session_id" not in payload
    handler.prepare_portal.assert_not_called()


def test_json_found_client_returns_authoritative_entry_result_once():
    service = Mock()
    service.resolve_for_login.return_value = state(found=True)
    handler = Mock()
    snapshot = {
        "session_id": "session-1",
        "state": "WAITING",
        "status": "WAITING",
        "progress": 0,
        "terminal": False,
    }
    handler.prepare_portal.return_value = PortalEntryResult(
        session_id="session-1",
        redirect_url=None,
        initial_state=snapshot,
    )
    app, _ = app_for(service, handler)

    response = app.test_client().get(
        "/capport/login",
        headers={"Accept": "application/json"},
        environ_base={"REMOTE_ADDR": "192.168.1.10"},
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "mode": "AUTH_SESSION",
        "session_id": "session-1",
        "redirect_url": None,
        "initial_state": snapshot,
    }
    handler.prepare_portal.assert_called_once_with(
        PortalClientContext(
            site_id="site-1",
            client_mac="AA:BB:CC:DD:EE:FF",
            client_ip="192.168.1.10",
        )
    )
    handler.open_portal.assert_not_called()
    assert response.headers["Cache-Control"] == "private, no-store"


def test_json_worker_failure_keeps_authoritative_session_envelope():
    service = Mock()
    service.resolve_for_login.return_value = state(found=True)
    handler = Mock()
    snapshot = {
        "session_id": "session-1",
        "state": "FAILED",
        "status": "FAILED",
        "progress": 100,
        "retryable": True,
        "terminal": False,
    }
    handler.prepare_portal.return_value = PortalEntryResult(
        session_id="session-1",
        redirect_url=None,
        initial_state=snapshot,
        status_code=500,
        error_code="worker_start_failed",
    )
    app, _ = app_for(service, handler)

    response = app.test_client().get(
        "/capport/login",
        headers={"Accept": "application/json"},
        environ_base={"REMOTE_ADDR": "192.168.1.10"},
    )

    assert response.status_code == 500
    payload = response.get_json()
    assert payload["mode"] == "AUTH_SESSION"
    assert payload["session_id"] == "session-1"
    assert payload["initial_state"] == snapshot
    assert payload["error"] == "worker_start_failed"


def test_json_invalid_context_has_no_session_id():
    service = Mock()
    service.resolve_for_login.return_value = state(found=True)
    handler = Mock()
    handler.prepare_portal.return_value = PortalEntryResult(
        session_id=None,
        redirect_url=None,
        initial_state={
            "state": "FAILED",
            "status": "FAILED",
            "terminal": True,
            "retryable": False,
        },
        status_code=400,
        error_code="invalid_context",
    )
    app, _ = app_for(service, handler)

    response = app.test_client().get(
        "/capport/login",
        headers={"Accept": "application/json"},
        environ_base={"REMOTE_ADDR": "192.168.1.10"},
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["error"] == "invalid_context"
    assert payload["state"] == "FAILED"
    assert payload["terminal"] is True
    assert "session_id" not in payload


def test_already_authorized_login_enters_shared_handler_once():
    service = Mock()
    service.resolve_for_login.return_value = state(
        captive=False,
        auth_status=2,
    )
    handler = Mock()
    handler.open_portal.return_value = ("opened", 200)
    app, _ = app_for(service, handler)

    response = app.test_client().get(
        "/capport/login",
        environ_base={"REMOTE_ADDR": "192.168.1.10"},
    )

    assert response.status_code == 200
    handler.open_portal.assert_called_once()
