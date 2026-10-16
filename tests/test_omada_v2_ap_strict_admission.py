"""Narrow v2 AP GET admission with real local TLS and strict negative gates."""
from unittest.mock import Mock
import os
import socket
import ssl

import pytest
import requests

from app.controllers.omada import _OmadaVerifiedTransport, OmadaTransportError
from app.controllers.omada_config import build_omada_runtime_config
from omada_tls_support import make_anchor, omada_server, tls_settings

C = "68ba0bb73ec9f9f0add0a21382f1b810"
S = "6acbd7ed0e281b36c6c133f5"
M = "AA-BB-CC-DD-EE-FF"
P = f"/openapi/v2/{C}/sites/{S}/aps/{M}"
V2 = "https://Omada:8043" + P
ROOT_FIXTURE = pytest.mark.skipif(
    os.name != "posix" or getattr(os, "geteuid", lambda: -1)() != 0,
    reason="root-owned isolated TLS fixture",
)


@pytest.fixture
def anchor(tmp_path):
    return make_anchor(tmp_path)


def transport(anchor):
    policy = build_omada_runtime_config(tls_settings(anchor)).tls_policy
    return _OmadaVerifiedTransport(policy)


@ROOT_FIXTURE
@pytest.mark.parametrize("suffix", ["/override", "/rf-scan-result"])
def test_documented_v2_get_uses_real_verified_tls_only(anchor, monkeypatch, suffix):
    resolver = socket.getaddrinfo
    with omada_server(anchor) as server:
        def local_only(host, port, *args, **kwargs):
            if str(host).lower() == "omada" and int(port) == 8043:
                return resolver("127.0.0.1", server.port, *args, **kwargs)
            if str(host) not in {"127.0.0.1", "localhost"}:
                raise AssertionError("unapproved network")
            return resolver(host, port, *args, **kwargs)
        monkeypatch.setattr(socket, "getaddrinfo", local_only)
        subject = transport(anchor)
        response = subject.request("GET", V2+suffix, timeout=(5,5))
        assert response.status_code == 200
        assert len(server.records) == 1
        assert server.records[0]["headers"]["Host"].lower() == "omada:8043"
        assert server.sni and all(sni.lower() == "omada" for sni in server.sni)
        assert subject._context.verify_mode == ssl.CERT_REQUIRED
        assert subject._context.check_hostname is True


@ROOT_FIXTURE
@pytest.mark.parametrize("suffix", ["/override", "/rf-scan-result"])
@pytest.mark.parametrize("method", ["POST", "PATCH", "DELETE", "HEAD", "get"])
def test_v2_non_get_never_sends(anchor, monkeypatch, suffix, method):
    send = Mock(side_effect=AssertionError("unapproved network"))
    monkeypatch.setattr(requests.Session, "request", send)
    with pytest.raises(OmadaTransportError, match="origin_not_admitted"):
        transport(anchor).request(method, V2+suffix)
    send.assert_not_called()


@ROOT_FIXTURE
@pytest.mark.parametrize("path", [
    P+"/override/extra",
    P+"/rf-scan-result/extra",
    P+"/general-config",
    P+"/radio-config",
    P+"/override/",
    P+"/OVERRIDE",
    P.replace("/openapi/v2/", "/openapi/v3/")+"/override",
    P.replace(C, "a"*31)+"-X/override",
    P.replace(C, "g"*32)+"/override",
    P.replace(S, "A"*24)+"/override",
    P.replace(S, "a"*23)+"/override",
    P.replace(M, "aa-bb-cc-dd-ee-ff")+"/override",
    P.replace(M, "AA:BB:CC:DD:EE:FF")+"/override",
    P.replace(M, "AA-BB-CC-DD-EE-GG")+"/override",
    P+"/../"+M+"/override",
    P+"/%2e%2e/"+M+"/override",
    P+"/override?foo=bar",
    P+"/rf-scan-result?foo=bar",
])
def test_v2_unapproved_path_never_sends(anchor, monkeypatch, path):
    send = Mock(side_effect=AssertionError("unapproved network"))
    monkeypatch.setattr(requests.Session, "request", send)
    with pytest.raises(OmadaTransportError, match="origin_not_admitted"):
        transport(anchor).request("GET","https://Omada:8043"+path)
    send.assert_not_called()


@ROOT_FIXTURE
@pytest.mark.parametrize("base", [
    "http://Omada:8043",
    "https://Omada:443",
    "https://192.168.0.99:8043",
    "https://localhost:8043",
    "https://user:secret@Omada:8043",
    "https://omada.invalid:8043",
])
def test_v2_origin_never_widens(anchor, monkeypatch, base):
    send = Mock(side_effect=AssertionError("unapproved network"))
    monkeypatch.setattr(requests.Session, "request", send)
    with pytest.raises(OmadaTransportError, match="origin_not_admitted"):
        transport(anchor).request("GET",base+P+"/override")
    send.assert_not_called()


@ROOT_FIXTURE
@pytest.mark.parametrize("suffix", ["/override", "/rf-scan-result"])
def test_v2_query_params_not_admitted(anchor, monkeypatch, suffix):
    send = Mock(side_effect=AssertionError("unapproved network"))
    monkeypatch.setattr(requests.Session, "request", send)
    with pytest.raises(OmadaTransportError, match="origin_not_admitted"):
        transport(anchor).request("GET",V2+suffix,params={"page":1})
    send.assert_not_called()


@ROOT_FIXTURE
@pytest.mark.parametrize("suffix", ["/override", "/rf-scan-result"])
def test_v2_redirect_refused(anchor, monkeypatch, suffix):
    resolver = socket.getaddrinfo
    with omada_server(anchor, lambda path:(302,{"Location":"https://Omada:8043/openapi/v2/other"},{})) as server:
        def route(host,port,*args,**kwargs):
            if str(host).lower()=="omada" and int(port)==8043:
                return resolver("127.0.0.1",server.port,*args,**kwargs)
            return resolver(host,port,*args,**kwargs)
        monkeypatch.setattr(socket,"getaddrinfo",route)
        with pytest.raises(OmadaTransportError,match="redirect_not_admitted"):
            transport(anchor).request("GET",V2+suffix)
        assert len(server.records)==1


@ROOT_FIXTURE
@pytest.mark.parametrize("suffix", ["/override", "/rf-scan-result"])
def test_v2_untrusted_certificate_refused(anchor, tmp_path, monkeypatch, suffix):
    other = make_anchor(tmp_path,stem="other")
    resolver=socket.getaddrinfo
    with omada_server(other) as server:
        def route(host,port,*args,**kwargs):
            if str(host).lower()=="omada" and int(port)==8043:
                return resolver("127.0.0.1",server.port,*args,**kwargs)
            return resolver(host,port,*args,**kwargs)
        monkeypatch.setattr(socket,"getaddrinfo",route)
        with pytest.raises(OmadaTransportError):
            transport(anchor).request("GET",V2+suffix)
        assert server.records==[]
