from dataclasses import replace

import pytest
import requests

from app.device_fingerprint_portal.config import portal_config_from_env
from app.device_fingerprint_portal.producer import PortalEvidenceProducer


class Response:
    def __init__(self, status, retry_after=None):
        self.status_code = status
        self.headers = {} if retry_after is None else {"Retry-After": retry_after}


class Session:
    def __init__(self, result): self.result=result; self.calls=[]
    def post(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if isinstance(self.result, Exception): raise self.result
        return self.result


def producer(tmp_path, result, monkeypatch):
    credential = tmp_path / "portal.bearer"; credential.write_text("a" * 32, encoding="ascii")
    ca = tmp_path / "portal-ca.crt"; ca.write_text("certificate", encoding="ascii")
    config = replace(portal_config_from_env({}), credential_path=str(credential), ca_cert_path=str(ca))
    session = Session(result); value = PortalEvidenceProducer(config, session=session)
    monkeypatch.setattr(value, "_validate_ca", lambda: None)
    return value, session


@pytest.mark.parametrize("response,status,cooldown", [
    (Response(200), "success", 0), (Response(500), "transient", 30),
    (Response(503), "transient", 30), (Response(429, "7"), "transient", 7),
    (Response(429, "bad"), "transient", 30), (Response(400), "permanent", 300),
    (Response(401), "permanent", 300), (Response(403), "permanent", 300),
    (Response(404), "permanent", 300), (Response(405), "permanent", 300),
    (Response(409), "permanent", 300), (Response(413), "permanent", 300),
    (requests.Timeout(), "transient", 30),
])
def test_delivery_classification_and_exact_https_contract(tmp_path, monkeypatch, response, status, cooldown):
    value, session = producer(tmp_path, response, monkeypatch)
    result = value.deliver_evidence([{"safe": True}])
    assert (result.status, result.cooldown_seconds) == (status, cooldown)
    if session.calls:
        _args, kwargs = session.calls[0]
        assert kwargs["timeout"] == (0.5, 2.0)
        assert kwargs["verify"] == value.config.ca_cert_path
        assert kwargs["headers"]["Authorization"] == "Bearer " + "a" * 32


@pytest.mark.parametrize("failure", [
    "credential_missing",
    "credential_invalid",
    "ca_missing",
    "ca_invalid",
])
def test_local_producer_config_failures_are_contained_without_http(tmp_path, failure):
    credential = tmp_path / "portal.bearer"
    ca = tmp_path / "portal-ca.crt"
    credential.write_text("a" * 32, encoding="ascii")
    if failure == "credential_missing":
        credential = tmp_path / "missing-credential"
    elif failure == "credential_invalid":
        credential.write_text("invalid", encoding="ascii")
    elif failure == "ca_missing":
        ca = tmp_path / "missing-ca"
    else:
        ca.write_text("not a certificate", encoding="ascii")
    config = replace(
        portal_config_from_env({}),
        credential_path=str(credential),
        ca_cert_path=str(ca),
    )
    session = Session(Response(200))
    result = PortalEvidenceProducer(config, session=session).deliver_evidence([{}])
    assert result.status == "config_unavailable"
    assert result.cooldown_seconds == 300
    assert session.calls == []
