from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import requests

from app.controllers.omada import OmadaProvider


FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "omada"
    / "client_snapshot_success.json"
)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, error=None):
        self.status_code = status_code
        self.payload = payload
        self.error = error

    def json(self):
        if self.error is not None:
            raise self.error
        return self.payload


@pytest.fixture
def provider():
    instance = OmadaProvider.__new__(OmadaProvider)
    instance._omada_url = "https://controller.example"
    instance._omada_id = "controller-id"
    instance._client_id = "client-id"
    instance._client_secret = "client-secret"
    instance._verify_ssl = False
    return instance


@pytest.fixture
def success_payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def install_success_token(monkeypatch):
    monkeypatch.setattr(
        "app.controllers.omada.requests.post",
        lambda *args, **kwargs: FakeResponse(
            200,
            {
                "errorCode": 0,
                "msg": "Success.",
                "result": {"accessToken": "temporary-token"},
            },
        ),
    )


def test_snapshot_provider_returns_a_full_independent_result(
    monkeypatch,
    provider,
    success_payload,
):
    install_success_token(monkeypatch)
    observed = {}

    def fake_get(url, **kwargs):
        observed["url"] = url
        observed.update(kwargs)
        return FakeResponse(200, success_payload)

    monkeypatch.setattr(
        "app.controllers.omada.requests.get",
        fake_get,
    )
    result = provider.get_client_snapshot(
        "site-id",
        "02:11:22:33:44:55",
        4.5,
    )
    assert result.success
    assert result.data["http_status"] == 200
    assert result.data["error_code"] == 0
    assert result.data["raw_result"] == success_payload["result"]
    assert result.data["raw_result"] is not success_payload["result"]
    assert "token" not in result.data
    assert observed["url"].endswith(
        "/sites/site-id/clients/02-11-22-33-44-55"
    )
    assert observed["headers"]["Accept"] == "application/json"
    assert observed["headers"]["Authorization"] == (
        "AccessToken=temporary-token"
    )
    assert observed["timeout"] == (4.5, 4.5)


def test_string_zero_error_code_is_success_for_client_endpoint(
    monkeypatch,
    provider,
    success_payload,
):
    install_success_token(monkeypatch)
    string_code_payload = copy.deepcopy(success_payload)
    string_code_payload["errorCode"] = "0"
    monkeypatch.setattr(
        "app.controllers.omada.requests.get",
        lambda *args, **kwargs: FakeResponse(
            200,
            string_code_payload,
        ),
    )
    result = provider.get_client_snapshot(
        "site-id",
        "02:11:22:33:44:55",
        5,
    )
    assert result.success
    assert result.data["error_code"] == 0
    assert result.data["raw_result"] == success_payload["result"]


@pytest.mark.parametrize(
    ("exception", "category"),
    [
        (requests.Timeout("slow"), "timeout"),
        (requests.ConnectionError("down"), "network_error"),
        (requests.RequestException("bad"), "network_error"),
    ],
)
def test_transport_exception_has_highest_priority(
    monkeypatch,
    provider,
    exception,
    category,
):
    install_success_token(monkeypatch)
    monkeypatch.setattr(
        "app.controllers.omada.requests.get",
        lambda *args, **kwargs: (_ for _ in ()).throw(exception),
    )
    result = provider.get_client_snapshot(
        "site-id",
        "02:11:22:33:44:55",
        5,
    )
    assert not result.success
    assert result.error == "SNAPSHOT_REQUEST_FAILED"
    assert result.data["failure_category"] == category
    assert result.data["retryable"] is True
    assert result.data["http_status"] is None
    assert result.data["error_code"] is None


@pytest.mark.parametrize(
    ("status", "category", "retryable"),
    [
        (408, "timeout", True),
        (429, "http_error", True),
        (500, "http_error", True),
        (599, "http_error", True),
        (400, "http_error", False),
        (401, "http_error", False),
        (403, "http_error", False),
        (404, "http_error", False),
    ],
)
def test_non_2xx_status_precedes_error_code(
    monkeypatch,
    provider,
    status,
    category,
    retryable,
):
    install_success_token(monkeypatch)
    monkeypatch.setattr(
        "app.controllers.omada.requests.get",
        lambda *args, **kwargs: FakeResponse(
            status,
            {"errorCode": -99999, "msg": "controller detail"},
        ),
    )
    result = provider.get_client_snapshot(
        "site-id",
        "02:11:22:33:44:55",
        5,
    )
    assert result.data["failure_category"] == category
    assert result.data["retryable"] is retryable
    assert result.data["error_code"] == -99999
    assert result.data["http_status"] == status


@pytest.mark.parametrize(
    "response",
    [
        FakeResponse(200, error=ValueError("bad json")),
        FakeResponse(200, ["not", "object"]),
    ],
)
def test_malformed_2xx_payload_is_retryable(
    monkeypatch,
    provider,
    response,
):
    install_success_token(monkeypatch)
    monkeypatch.setattr(
        "app.controllers.omada.requests.get",
        lambda *args, **kwargs: response,
    )
    result = provider.get_client_snapshot(
        "site-id",
        "02:11:22:33:44:55",
        5,
    )
    assert result.data["failure_category"] == "malformed_response"
    assert result.data["retryable"] is True


def test_minus_41011_is_temporarily_unavailable(
    monkeypatch,
    provider,
):
    install_success_token(monkeypatch)
    monkeypatch.setattr(
        "app.controllers.omada.requests.get",
        lambda *args, **kwargs: FakeResponse(
            200,
            {"errorCode": -41011, "msg": "not found"},
        ),
    )
    result = provider.get_client_snapshot(
        "site-id",
        "02:11:22:33:44:55",
        5,
    )
    assert result.data["failure_category"] == (
        "client_not_available"
    )
    assert result.data["retryable"] is True


def test_unknown_2xx_error_code_is_permanent(
    monkeypatch,
    provider,
):
    install_success_token(monkeypatch)
    monkeypatch.setattr(
        "app.controllers.omada.requests.get",
        lambda *args, **kwargs: FakeResponse(
            200,
            {"errorCode": -99999, "msg": "unknown"},
        ),
    )
    result = provider.get_client_snapshot(
        "site-id",
        "02:11:22:33:44:55",
        5,
    )
    assert result.data["failure_category"] == "controller_error"
    assert result.data["retryable"] is False


@pytest.mark.parametrize(
    "payload",
    [
        {"result": {"mac": "02-11-22-33-44-55"}},
        {"errorCode": None, "result": {}},
        {"errorCode": True, "result": {}},
        {"errorCode": {}, "result": {}},
    ],
)
def test_missing_or_invalid_error_code_is_malformed_and_retryable(
    monkeypatch,
    provider,
    payload,
):
    install_success_token(monkeypatch)
    monkeypatch.setattr(
        "app.controllers.omada.requests.get",
        lambda *args, **kwargs: FakeResponse(200, payload),
    )
    result = provider.get_client_snapshot(
        "site-id",
        "02:11:22:33:44:55",
        5,
    )
    assert result.data["failure_category"] == "malformed_response"
    assert result.data["retryable"] is True


@pytest.mark.parametrize(
    ("raw_result", "category"),
    [
        (None, "client_not_available"),
        ([], "malformed_response"),
        ({}, "client_not_available"),
        ({"mac": "bad"}, "client_not_available"),
    ],
)
def test_result_shape_is_classified(
    monkeypatch,
    provider,
    raw_result,
    category,
):
    install_success_token(monkeypatch)
    monkeypatch.setattr(
        "app.controllers.omada.requests.get",
        lambda *args, **kwargs: FakeResponse(
            200,
            {"errorCode": 0, "result": raw_result},
        ),
    )
    result = provider.get_client_snapshot(
        "site-id",
        "02:11:22:33:44:55",
        5,
    )
    assert result.data["failure_category"] == category
    assert result.data["retryable"] is True


@pytest.mark.parametrize(
    ("response", "category", "retryable"),
    [
        (
            FakeResponse(
                500,
                {"errorCode": -99999, "msg": "temporary"},
            ),
            "http_error",
            True,
        ),
        (
            FakeResponse(
                200,
                {"errorCode": -99999, "msg": "permanent"},
            ),
            "token_error",
            False,
        ),
        (
            FakeResponse(200, error=ValueError("bad json")),
            "malformed_response",
            True,
        ),
        (
            FakeResponse(
                200,
                {"errorCode": 0, "result": {}},
            ),
            "malformed_response",
            True,
        ),
    ],
)
def test_token_result_has_additive_machine_classification(
    monkeypatch,
    provider,
    response,
    category,
    retryable,
):
    monkeypatch.setattr(
        "app.controllers.omada.requests.post",
        lambda *args, **kwargs: response,
    )
    result = provider._get_token()
    assert not result.success
    assert result.data["failure_category"] == category
    assert result.data["retryable"] is retryable


def test_string_zero_error_code_is_success_for_token_endpoint(
    monkeypatch,
    provider,
):
    monkeypatch.setattr(
        "app.controllers.omada.requests.post",
        lambda *args, **kwargs: FakeResponse(
            200,
            {
                "errorCode": "0",
                "msg": "Success.",
                "result": {"accessToken": "temporary-token"},
            },
        ),
    )
    result = provider._get_token()
    assert result.success
    assert result.data == {
        "token": "temporary-token",
        "http_status": 200,
        "error_code": 0,
    }


@pytest.mark.parametrize(
    "exception",
    [
        requests.Timeout("slow"),
        requests.ConnectionError("down"),
        requests.RequestException("bad"),
    ],
)
def test_token_transport_failure_is_retryable(
    monkeypatch,
    provider,
    exception,
):
    monkeypatch.setattr(
        "app.controllers.omada.requests.post",
        lambda *args, **kwargs: (_ for _ in ()).throw(exception),
    )
    result = provider._get_token()
    assert not result.success
    expected = (
        "timeout"
        if isinstance(exception, requests.Timeout)
        else "network_error"
    )
    assert result.data["failure_category"] == expected
    assert result.data["retryable"] is True


@pytest.mark.parametrize(
    ("exception", "category"),
    [
        (requests.Timeout("slow"), "timeout"),
        (requests.ConnectionError("down"), "network_error"),
    ],
)
def test_public_snapshot_clears_legacy_token_transport_codes(
    monkeypatch,
    provider,
    exception,
    category,
):
    monkeypatch.setattr(
        "app.controllers.omada.requests.post",
        lambda *args, **kwargs: (_ for _ in ()).throw(exception),
    )
    monkeypatch.setattr(
        "app.controllers.omada.requests.get",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("client GET must not run")
        ),
    )
    result = provider.get_client_snapshot(
        "site-id",
        "02:11:22:33:44:55",
        5,
    )
    assert not result.success
    assert result.data["failure_category"] == category
    assert result.data["retryable"] is True
    assert result.data["http_status"] is None
    assert result.data["error_code"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {"result": {"accessToken": "token"}},
        {"errorCode": None, "result": {}},
        {"errorCode": False, "result": {}},
    ],
)
def test_token_missing_or_invalid_error_code_is_malformed(
    monkeypatch,
    provider,
    payload,
):
    monkeypatch.setattr(
        "app.controllers.omada.requests.post",
        lambda *args, **kwargs: FakeResponse(200, payload),
    )
    result = provider._get_token()
    assert not result.success
    assert result.data["failure_category"] == "malformed_response"
    assert result.data["retryable"] is True


def test_invalid_snapshot_input_does_not_call_http(
    monkeypatch,
    provider,
):
    calls = []
    monkeypatch.setattr(
        "app.controllers.omada.requests.post",
        lambda *args, **kwargs: calls.append("post"),
    )
    assert not provider.get_client_snapshot(
        "",
        "02:11:22:33:44:55",
        5,
    ).success
    assert not provider.get_client_snapshot(
        "site-id",
        "bad",
        5,
    ).success
    assert not provider.get_client_snapshot(
        "site-id",
        "02:11:22:33:44:55",
        0,
    ).success
    assert not provider.get_client_snapshot(
        "site-id",
        "02:11:22:33:44:55",
        float("nan"),
    ).success
    assert not provider.get_client_snapshot(
        "site-id",
        "02:11:22:33:44:55",
        float("inf"),
    ).success
    assert calls == []
