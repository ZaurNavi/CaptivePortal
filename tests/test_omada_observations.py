from __future__ import annotations

import json

import pytest
import requests

from app.controllers import OmadaProvider
from app.controllers import omada_observations as subject
from app.models import Result


ACCESS_MARKER = "TEST_ACCESS_TOKEN_SHOULD_NOT_LEAK"
SECRET_MARKER = "TEST_CLIENT_SECRET_SHOULD_NOT_LEAK"


class FakeProvider:
    def __init__(self):
        self._omada_url = "https://controller.example"
        self._omada_id = "controller-id"
        self._verify_ssl = False
        self.tokens = [ACCESS_MARKER]
        self.token_calls: list[bool] = []
        self.invalidated: list[str] = []

    def _get_token(self, *, force_refresh=False):
        self.token_calls.append(force_refresh)
        token = self.tokens[min(len(self.token_calls) - 1, len(self.tokens) - 1)]
        return Result.ok(data={"token": token})

    def _invalidate_cached_token(self, token):
        self.invalidated.append(token)


class FakeResponse:
    def __init__(self, payload=None, *, status_code=200, error=None):
        self.payload = payload
        self.status_code = status_code
        self.error = error

    def json(self):
        if self.error is not None:
            raise self.error
        return self.payload


def success_payload(rows=None, total=0, **updates):
    result = {"data": [] if rows is None else rows, "totalRows": total}
    result.update(updates)
    return {"errorCode": 0, "msg": "Success.", "result": result}


def test_method_is_installed_on_shared_provider_class():
    assert OmadaProvider.list_observation_clients is subject.list_observation_clients


def test_success_is_bounded_and_defensively_copied(monkeypatch):
    provider = FakeProvider()
    raw = [{"mac": "AA-BB-CC-DD-EE-FF"}]
    captured = {}

    def get(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse(
            success_payload(raw, 1, currentPage=2, currentSize=1)
        )

    monkeypatch.setattr(subject.requests, "get", get)
    result = subject.list_observation_clients(provider, " site-1 ", 2, 500, 5)

    assert result.success is True
    assert result.data["clients"] == raw
    assert result.data["total_rows"] == 1
    assert captured["params"] == {"page": 2, "pageSize": 500}
    assert captured["timeout"] == (5.0, 5.0)
    assert captured["url"].endswith("/sites/site-1/clients")
    raw[0]["mac"] = "changed"
    assert result.data["clients"][0]["mac"] == "AA-BB-CC-DD-EE-FF"


def test_exact_token_expiry_gets_one_guarded_shared_refresh(monkeypatch):
    provider = FakeProvider()
    provider.tokens = [ACCESS_MARKER, "fresh-token"]
    responses = [
        FakeResponse({"errorCode": -44112, "msg": SECRET_MARKER}),
        FakeResponse(success_payload([], 0)),
    ]
    monkeypatch.setattr(subject.requests, "get", lambda *a, **k: responses.pop(0))

    result = subject.list_observation_clients(provider, "site", 1, 10, 5)

    assert result.success is True
    assert provider.token_calls == [False, True]
    assert provider.invalidated == [ACCESS_MARKER]


def test_second_token_expiry_is_not_retried(monkeypatch):
    provider = FakeProvider()
    provider.tokens = [ACCESS_MARKER, "fresh-token"]
    calls = 0

    def get(*args, **kwargs):
        nonlocal calls
        calls += 1
        return FakeResponse({"errorCode": -44112})

    monkeypatch.setattr(subject.requests, "get", get)
    result = subject.list_observation_clients(provider, "site", 1, 10, 5)
    assert result.success is False
    assert result.error == "TOKEN_EXPIRED"
    assert calls == 2
    assert provider.invalidated == [ACCESS_MARKER, "fresh-token"]


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"errorCode": "0"},
        {"errorCode": 0, "result": []},
        {"errorCode": 0, "result": {"data": {}, "totalRows": 0}},
        {"errorCode": 0, "result": {"data": [], "totalRows": True}},
        success_payload([], 0, currentPage=2),
        success_payload([], 0, currentPage=True),
    ],
)
def test_response_contract_is_strict(monkeypatch, payload):
    monkeypatch.setattr(
        subject.requests,
        "get",
        lambda *a, **k: FakeResponse(payload),
    )
    result = subject.list_observation_clients(FakeProvider(), "site", 1, 10, 5)
    assert result.success is False
    assert result.error == "MALFORMED_RESPONSE"


def test_controller_current_size_is_not_assumed_to_equal_returned_rows(monkeypatch):
    monkeypatch.setattr(
        subject.requests,
        "get",
        lambda *a, **k: FakeResponse(
            success_payload([], 0, currentPage=1, currentSize=500)
        ),
    )
    result = subject.list_observation_clients(FakeProvider(), "site", 1, 500, 5)
    assert result.success is True


def test_http_json_network_and_unknown_code_are_classified(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr(
        subject.requests, "get", lambda *a, **k: FakeResponse({}, status_code=503)
    )
    http = subject.list_observation_clients(provider, "site", 1, 10, 5)
    assert http.data["failure_category"] == "http_error"
    assert http.data["retryable"] is True

    monkeypatch.setattr(
        subject.requests,
        "get",
        lambda *a, **k: FakeResponse(error=ValueError(SECRET_MARKER)),
    )
    malformed = subject.list_observation_clients(provider, "site", 1, 10, 5)
    assert malformed.data["failure_category"] == "malformed_response"

    def timeout(*args, **kwargs):
        raise requests.exceptions.Timeout(ACCESS_MARKER)

    monkeypatch.setattr(subject.requests, "get", timeout)
    timed_out = subject.list_observation_clients(provider, "site", 1, 10, 5)
    assert timed_out.data["failure_category"] == "timeout"

    monkeypatch.setattr(
        subject.requests,
        "get",
        lambda *a, **k: FakeResponse({"errorCode": -99999, "msg": SECRET_MARKER}),
    )
    unknown = subject.list_observation_clients(provider, "site", 1, 10, 5)
    assert unknown.error == "API_ERROR"
    assert unknown.data["error_code"] == -99999
    assert unknown.data["retryable"] is False

    serialized = json.dumps([
        http.to_dict(), malformed.to_dict(), timed_out.to_dict(), unknown.to_dict()
    ])
    assert ACCESS_MARKER not in serialized
    assert SECRET_MARKER not in serialized


@pytest.mark.parametrize(
    "args",
    [
        ("", 1, 10, 5),
        ("site", True, 10, 5),
        ("site", 1, 0, 5),
        ("site", 1, 501, 5),
        ("site", 1, 10, float("nan")),
        ("site", 1, 10, 61),
    ],
)
def test_invalid_arguments_make_no_request(monkeypatch, args):
    monkeypatch.setattr(
        subject.requests,
        "get",
        lambda *a, **k: pytest.fail("network must not be called"),
    )
    result = subject.list_observation_clients(FakeProvider(), *args)
    assert result.success is False
    assert result.data["failure_category"] == "invalid_argument"
