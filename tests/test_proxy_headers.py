from unittest.mock import patch

from flask import jsonify, request

import app.web.web as web_module


class NoopExecutor:
    def submit(self, *args, **kwargs):
        return None


def create_test_app():
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
        app = web_module.create_app(
            portal_counter_service=None
        )

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
