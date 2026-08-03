from app.controllers import omada_pending_sessions as subject
from app.models import Result


class Provider:
    def __init__(self):
        self._omada_url = "https://controller.example"
        self._omada_id = "controller-id"
        self._verify_ssl = False
        self.invalidated = []

    def _get_token(self):
        return Result.ok(data={"token": "secret-token"})

    def _invalidate_cached_token(self, token=None):
        self.invalidated.append(token)


class Response:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload


def test_reconnect_uses_hyphen_mac_and_returns_safe_contract(monkeypatch):
    captured = {}

    def post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return Response({"errorCode": 0, "msg": "Success."})

    monkeypatch.setattr(subject.requests, "post", post)
    result = subject.reconnect_client(
        Provider(),
        site_id="site-1",
        client_mac="aa:bb:cc:dd:ee:ff",
        timeout_seconds=5,
    )

    assert result.success is True
    assert result.data == {
        "http_status": 200,
        "error_code": 0,
        "message": "Success.",
        "command_accepted": True,
    }
    assert captured["url"].endswith(
        "/sites/site-1/clients/AA-BB-CC-DD-EE-FF/reconnect"
    )
    assert "secret-token" not in repr(result.to_dict())


def test_reconnect_token_expiry_invalidates_cache(monkeypatch):
    provider = Provider()
    monkeypatch.setattr(
        subject.requests,
        "post",
        lambda *args, **kwargs: Response(
            {"errorCode": -44112, "msg": "expired"}
        ),
    )

    result = subject.reconnect_client(
        provider,
        site_id="site-1",
        client_mac="AA:BB:CC:DD:EE:FF",
        timeout_seconds=5,
    )

    assert result.success is False
    assert result.error == "TOKEN_EXPIRED"
    assert result.data["retryable"] is True
    assert provider.invalidated == ["secret-token"]
