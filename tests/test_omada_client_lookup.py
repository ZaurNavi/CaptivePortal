from unittest.mock import Mock, patch

import requests

from app.controllers.omada import OmadaProvider
from app.models import Result


class FakeResponse:
    def __init__(self, payload=None, status_code=200, json_error=None):
        self._payload = payload
        self.status_code = status_code
        self._json_error = json_error

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._payload


def provider():
    instance = object.__new__(OmadaProvider)
    instance._omada_url = "https://controller.example"
    instance._omada_id = "controller-id"
    instance._verify_ssl = True
    instance._get_token = Mock(
        return_value=Result.ok(data={"token": "test-token"})
    )
    return instance


def page(data, **result_fields):
    return FakeResponse(
        {
            "errorCode": 0,
            "msg": "Success",
            "result": {"data": data, **result_fields},
        }
    )


def client(ip, mac, auth_status=0, active=True):
    return {
        "ip": ip,
        "mac": mac,
        "authStatus": auth_status,
        "active": active,
    }


def test_get_clients_one_page_normalizes_fields_and_uses_params():
    omada = provider()
    response = page(
        [client("192.168.1.10", "aa-bb-cc-dd-ee-ff")]
    )

    with patch(
        "app.controllers.omada.requests.get",
        return_value=response,
    ) as request_get:
        result = omada.get_clients("site-1")

    assert result.success
    assert result.data["clients"] == [
        {
            "client_ip": "192.168.1.10",
            "client_mac": "AA:BB:CC:DD:EE:FF",
            "authStatus": 0,
            "active": True,
        }
    ]
    assert request_get.call_args.kwargs["params"] == {
        "page": 1,
        "pageSize": 100,
    }
    omada._get_token.assert_called_once()


def test_get_clients_reads_multiple_pages_with_one_token():
    omada = provider()
    omada.CLIENT_PAGE_SIZE = 2
    responses = [
        page(
            [
                client("192.168.1.10", "00:00:00:00:00:10"),
                client("192.168.1.11", "00:00:00:00:00:11"),
            ],
            totalRows=3,
        ),
        page(
            [client("192.168.1.12", "00:00:00:00:00:12")],
            totalRows=3,
        ),
    ]

    with patch(
        "app.controllers.omada.requests.get",
        side_effect=responses,
    ) as request_get:
        result = omada.get_clients("site-1")

    assert result.success
    assert len(result.data["clients"]) == 3
    assert request_get.call_count == 2
    omada._get_token.assert_called_once()


def test_get_clients_accepts_empty_successful_page():
    omada = provider()
    with patch(
        "app.controllers.omada.requests.get",
        return_value=page([]),
    ):
        result = omada.get_clients("site-1")

    assert result.success
    assert result.data["clients"] == []


def test_get_client_by_ip_uses_exact_normalized_ip():
    omada = provider()
    omada.get_clients = Mock(
        return_value=Result.ok(
            data={
                "clients": [
                    {
                        "client_ip": "192.168.1.1",
                        "client_mac": "AA:AA:AA:AA:AA:01",
                        "authStatus": 0,
                        "active": True,
                    },
                    {
                        "client_ip": "192.168.1.10",
                        "client_mac": "AA:AA:AA:AA:AA:10",
                        "authStatus": 2,
                        "active": True,
                    },
                ],
                "http_status": 200,
            }
        )
    )

    result = omada.get_client_by_ip("site-1", "192.168.1.10")

    assert result.success
    assert result.data["found"] is True
    assert result.data["client_mac"] == "AA:AA:AA:AA:AA:10"
    assert result.data["list_auth_status"] == 2
    assert result.data["list_active"] is True


def test_get_client_by_ip_rejects_invalid_ip_without_controller_call():
    omada = provider()
    omada.get_clients = Mock()

    result = omada.get_client_by_ip("site-1", "not-an-ip")

    assert not result.success
    assert result.error == "INVALID_CLIENT_IP"
    omada.get_clients.assert_not_called()


def test_duplicate_ip_prefers_only_active_record():
    omada = provider()
    omada.get_clients = Mock(
        return_value=Result.ok(
            data={
                "clients": [
                    {
                        "client_ip": "192.168.1.10",
                        "client_mac": "AA:AA:AA:AA:AA:01",
                        "authStatus": 0,
                        "active": False,
                    },
                    {
                        "client_ip": "192.168.1.10",
                        "client_mac": "AA:AA:AA:AA:AA:02",
                        "authStatus": 2,
                        "active": True,
                    },
                ],
                "http_status": 200,
            }
        )
    )

    result = omada.get_client_by_ip("site-1", "192.168.1.10")

    assert result.success
    assert result.data["client_mac"] == "AA:AA:AA:AA:AA:02"


def test_ambiguous_duplicate_ip_returns_failure():
    omada = provider()
    omada.get_clients = Mock(
        return_value=Result.ok(
            data={
                "clients": [
                    {
                        "client_ip": "192.168.1.10",
                        "client_mac": "AA:AA:AA:AA:AA:01",
                        "authStatus": 0,
                        "active": True,
                    },
                    {
                        "client_ip": "192.168.1.10",
                        "client_mac": "AA:AA:AA:AA:AA:02",
                        "authStatus": 0,
                        "active": True,
                    },
                ],
                "http_status": 200,
            }
        )
    )

    result = omada.get_client_by_ip("site-1", "192.168.1.10")

    assert not result.success
    assert result.error == "DUPLICATE_CLIENT_IP"


def test_token_failure_is_preserved():
    omada = provider()
    omada._get_token = Mock(
        return_value=Result.fail(error="TOKEN_FAILED")
    )

    result = omada.get_clients("site-1")

    assert not result.success
    assert result.error == "TOKEN_FAILED"


def test_http_timeout_returns_http_error():
    omada = provider()
    with patch(
        "app.controllers.omada.requests.get",
        side_effect=requests.exceptions.Timeout("slow"),
    ):
        result = omada.get_clients("site-1")

    assert not result.success
    assert result.error == "HTTP_ERROR"


def test_nonzero_omada_error_code_returns_api_error():
    omada = provider()
    response = FakeResponse(
        {
            "errorCode": -1,
            "msg": "General error",
            "result": {},
        }
    )
    with patch(
        "app.controllers.omada.requests.get",
        return_value=response,
    ):
        result = omada.get_clients("site-1")

    assert not result.success
    assert result.error == "API_ERROR"
    assert result.data["error_code"] == -1


def test_http_failure_with_zero_error_code_is_not_success():
    omada = provider()
    with patch(
        "app.controllers.omada.requests.get",
        return_value=FakeResponse(
            {
                "errorCode": 0,
                "result": {"data": []},
            },
            status_code=500,
        ),
    ):
        result = omada.get_clients("site-1")

    assert not result.success
    assert result.error == "HTTP_ERROR"
    assert result.data["http_status"] == 500


def test_malformed_json_structure_returns_failure():
    omada = provider()
    with patch(
        "app.controllers.omada.requests.get",
        return_value=FakeResponse({"errorCode": 0, "result": []}),
    ):
        result = omada.get_clients("site-1")

    assert not result.success
    assert result.error == "MALFORMED_RESPONSE"


def test_invalid_json_returns_malformed_response():
    omada = provider()
    with patch(
        "app.controllers.omada.requests.get",
        return_value=FakeResponse(json_error=ValueError("bad json")),
    ):
        result = omada.get_clients("site-1")

    assert not result.success
    assert result.error == "MALFORMED_RESPONSE"


def test_pagination_is_bounded():
    omada = provider()
    omada.CLIENT_PAGE_SIZE = 1
    omada.CLIENT_MAX_PAGES = 2
    with patch(
        "app.controllers.omada.requests.get",
        return_value=page(
            [client("192.168.1.10", "00:00:00:00:00:10")]
        ),
    ) as request_get:
        result = omada.get_clients("site-1")

    assert not result.success
    assert result.error == "PAGINATION_LIMIT"
    assert request_get.call_count == 2
