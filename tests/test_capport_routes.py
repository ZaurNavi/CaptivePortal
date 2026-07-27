from pathlib import Path
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
from app.web.portal_entry import PortalClientContext


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


def test_login_not_found_is_controlled_and_starts_no_worker():
    service = Mock()
    service.resolve_for_login.return_value = state(found=False)
    handler = Mock()
    app, _ = app_for(service, handler)

    response = app.test_client().get(
        "/capport/login",
        environ_base={"REMOTE_ADDR": "192.168.1.10"},
    )

    assert response.status_code == 404
    assert "Не удалось определить устройство" in response.get_data(
        as_text=True
    )
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
    assert "временно недоступен" in response.get_data(as_text=True)
    handler.open_portal.assert_not_called()


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
