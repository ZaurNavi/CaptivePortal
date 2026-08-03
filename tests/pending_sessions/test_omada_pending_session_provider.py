import pytest
import requests

from app.controllers import omada_pending_sessions as subject
from app.models import Result


SECRET = "test-access-token-do-not-leak"


class FakeProvider:
    def __init__(self, token_result=None):
        self._omada_url = "https://controller.example"
        self._omada_id = "controller-id"
        self._verify_ssl = False
        self.token_result = token_result or Result.ok(data={"token": SECRET})

    def _get_token(self):
        return self.token_result


class FakeResponse:
    def __init__(self, payload=None, *, status_code=200, json_error=None):
        self.status_code = status_code
        self.payload = payload
        self.json_error = json_error

    def json(self):
        if self.json_error is not None:
            raise self.json_error
        return self.payload


def test_list_active_clients_success_contract_and_defensive_copy(monkeypatch):
    payload = {
        "errorCode": 0,
        "msg": "Success.",
        "result": {
            "data": [{"mac": "AA-BB-CC-DD-EE-FF"}],
            "totalRows": 1,
        },
    }
    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse(payload)

    monkeypatch.setattr(subject.requests, "get", fake_get)

    result = subject.list_active_clients(
        FakeProvider(),
        site_id="site-1",
        page=2,
        page_size=500,
        timeout_seconds=4.5,
    )

    assert result.success is True
    assert result.data == {
        "http_status": 200,
        "error_code": 0,
        "message": "Success.",
        "page": 2,
        "page_size": 500,
        "total_rows": 1,
        "clients": [{"mac": "AA-BB-CC-DD-EE-FF"}],
    }
    assert captured["url"].endswith(
        "/openapi/v1/controller-id/sites/site-1/clients"
    )
    assert captured["params"] == {"page": 2, "pageSize": 500}
    assert captured["timeout"] == (4.5, 4.5)
    assert captured["headers"] == {"Authorization": f"AccessToken={SECRET}"}

    payload["result"]["data"][0]["mac"] = "changed"
    assert result.data["clients"][0]["mac"] == "AA-BB-CC-DD-EE-FF"


def test_get_pending_client_state_formats_mac_and_copies_result(monkeypatch):
    client = {"mac": "AA-BB-CC-DD-EE-FF", "authStatus": 1}
    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse(
            {"errorCode": 0, "msg": "Success.", "result": client}
        )

    monkeypatch.setattr(subject.requests, "get", fake_get)

    result = subject.get_pending_client_state(
        FakeProvider(),
        site_id="site-1",
        client_mac="aa:bb:cc:dd:ee:ff",
        timeout_seconds=5,
    )

    assert result.success is True
    assert captured["url"].endswith(
        "/sites/site-1/clients/AA-BB-CC-DD-EE-FF"
    )
    client["authStatus"] = 2
    assert result.data["client"]["authStatus"] == 1


def test_token_expired_is_retryable(monkeypatch):
    monkeypatch.setattr(
        subject.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(
            {"errorCode": -44112, "msg": "Access token expired"}
        ),
    )

    result = subject.list_active_clients(
        FakeProvider(),
        site_id="site-1",
        page=1,
        page_size=100,
        timeout_seconds=5,
    )

    assert result.success is False
    assert result.error == "TOKEN_EXPIRED"
    assert result.data["failure_category"] == "token_expired"
    assert result.data["retryable"] is True
    assert result.data["error_code"] == -44112


@pytest.mark.parametrize(
    ("payload", "expected_error"),
    [
        ([], "MALFORMED_RESPONSE"),
        ({"errorCode": "0"}, "MALFORMED_RESPONSE"),
        ({"errorCode": 0, "result": []}, "MALFORMED_RESPONSE"),
        (
            {"errorCode": 0, "result": {"data": {}, "totalRows": 0}},
            "MALFORMED_RESPONSE",
        ),
        (
            {"errorCode": 0, "result": {"data": [], "totalRows": True}},
            "MALFORMED_RESPONSE",
        ),
    ],
)
def test_list_response_validation_is_strict(monkeypatch, payload, expected_error):
    monkeypatch.setattr(
        subject.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(payload),
    )

    result = subject.list_active_clients(
        FakeProvider(),
        site_id="site-1",
        page=1,
        page_size=100,
        timeout_seconds=5,
    )

    assert result.success is False
    assert result.error == expected_error
    assert result.data["retryable"] is True


def test_invalid_json_is_retryable_malformed_response(monkeypatch):
    monkeypatch.setattr(
        subject.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(
            status_code=200,
            json_error=ValueError("bad json"),
        ),
    )

    result = subject.get_pending_client_state(
        FakeProvider(),
        site_id="site-1",
        client_mac="AA:BB:CC:DD:EE:FF",
        timeout_seconds=5,
    )

    assert result.success is False
    assert result.error == "MALFORMED_RESPONSE"
    assert result.data["failure_category"] == "malformed_response"
    assert result.data["retryable"] is True


def test_http_and_timeout_failures_are_classified(monkeypatch):
    monkeypatch.setattr(
        subject.requests,
        "get",
        lambda *args, **kwargs: FakeResponse({}, status_code=503),
    )
    unavailable = subject.list_active_clients(
        FakeProvider(),
        site_id="site-1",
        page=1,
        page_size=100,
        timeout_seconds=5,
    )

    assert unavailable.success is False
    assert unavailable.error == "HTTP_ERROR"
    assert unavailable.data["retryable"] is True
    assert unavailable.data["http_status"] == 503

    def timeout(*args, **kwargs):
        raise requests.exceptions.Timeout("slow")

    monkeypatch.setattr(subject.requests, "get", timeout)
    timed_out = subject.list_active_clients(
        FakeProvider(),
        site_id="site-1",
        page=1,
        page_size=100,
        timeout_seconds=5,
    )

    assert timed_out.success is False
    assert timed_out.data["failure_category"] == "timeout"
    assert timed_out.data["retryable"] is True


@pytest.mark.parametrize(
    "kwargs",
    [
        {"site_id": "", "page": 1, "page_size": 100, "timeout_seconds": 5},
        {"site_id": "site-1", "page": 0, "page_size": 100, "timeout_seconds": 5},
        {"site_id": "site-1", "page": 1, "page_size": True, "timeout_seconds": 5},
        {
            "site_id": "site-1",
            "page": 1,
            "page_size": 100,
            "timeout_seconds": float("inf"),
        },
    ],
)
def test_list_arguments_are_validated_without_network(monkeypatch, kwargs):
    def forbidden(*args, **kwargs):
        raise AssertionError("network must not be called")

    monkeypatch.setattr(subject.requests, "get", forbidden)

    result = subject.list_active_clients(FakeProvider(), **kwargs)

    assert result.success is False
    assert result.data["failure_category"] == "invalid_argument"
    assert result.data["retryable"] is False


def test_missing_token_is_failure_and_secret_never_appears_in_result():
    provider = FakeProvider(Result.ok(data={"token": "   "}))

    result = subject.list_active_clients(
        provider,
        site_id="site-1",
        page=1,
        page_size=100,
        timeout_seconds=5,
    )

    assert result.success is False
    assert result.error == "TOKEN_ERROR"
    assert SECRET not in repr(result.to_dict())


def test_success_and_failure_results_do_not_expose_access_token(monkeypatch):
    monkeypatch.setattr(
        subject.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(
            {
                "errorCode": 0,
                "msg": "Success.",
                "result": {"data": [], "totalRows": 0},
            }
        ),
    )

    success = subject.list_active_clients(
        FakeProvider(),
        site_id="site-1",
        page=1,
        page_size=100,
        timeout_seconds=5,
    )
    assert SECRET not in repr(success.to_dict())

    monkeypatch.setattr(
        subject.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(
            {"errorCode": -44112, "msg": "expired"}
        ),
    )
    failure = subject.list_active_clients(
        FakeProvider(),
        site_id="site-1",
        page=1,
        page_size=100,
        timeout_seconds=5,
    )
    assert SECRET not in repr(failure.to_dict())


def test_installer_adds_methods_to_provider_class():
    class Provider:
        pass

    subject.install_pending_session_methods(Provider)

    assert Provider.list_active_clients is subject.list_active_clients
    assert Provider.get_pending_client_state is subject.get_pending_client_state
