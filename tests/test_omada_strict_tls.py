"""QIO-01B Option B only; real isolated TLS, no Omada or guest mutations."""
import ast
import json
import os
from pathlib import Path
import socket
import ssl
from unittest.mock import Mock

import pytest
import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.controllers import OmadaProvider
from app.controllers.omada import _OmadaVerifiedTransport, OmadaTransportError, _OmadaTlsAdapter
from app.controllers.omada_config import build_omada_runtime_config, public_omada_snapshot
from app.exceptions import ConfigurationError, ControllerError
from app.models import Result
from omada_tls_support import make_anchor, omada_server, tls_settings


ROOT_FIXTURE = pytest.mark.skipif(os.name != "posix" or getattr(os, "geteuid", lambda: -1)() != 0,
                                  reason="isolated root-owned Linux TLS-file fixture")
MAC = "AA-BB-CC-DD-EE-FF"
OPERATIONS = (
    "token", "sites", "clients", "auth", "unauth", "client", "snapshot",
    "pending-list", "pending-state", "pending-reconnect", "observation-clients", "observation-aps",
)
EXTENSION_OPERATIONS = OPERATIONS[7:]


@pytest.fixture
def anchor(tmp_path):
    return make_anchor(tmp_path)


@pytest.fixture
def route_to(monkeypatch):
    original = socket.getaddrinfo

    def install(server):
        def resolve(host, port, *args, **kwargs):
            if str(host).lower() == "omada" and int(port) == 8043:
                return original("127.0.0.1", server.port, *args, **kwargs)
            if host not in ("127.0.0.1", "localhost", b"127.0.0.1"):
                raise AssertionError("non-loopback network forbidden in TLS fixture")
            return original(host, port, *args, **kwargs)
        monkeypatch.setattr(socket, "getaddrinfo", resolve)
    return install


def provider(anchor, operation=None):
    result = OmadaProvider(build_omada_runtime_config(tls_settings(anchor)))
    if operation != "token":
        result._get_token = Mock(return_value=Result.ok(data={"token": "DISPOSABLE_ACCESS_TOKEN"}))
    return result


def operation(subject, name):
    calls = {
        "token": lambda: subject._request_token_uncached(),
        "sites": subject.get_sites,
        "clients": lambda: subject.get_clients("site-1"),
        "auth": lambda: subject.authorize("site-1", MAC),
        "unauth": lambda: subject.unauthorize("site-1", MAC),
        "client": lambda: subject.get_client("site-1", MAC),
        "snapshot": lambda: subject.get_client_snapshot("site-1", MAC, 1),
        "pending-list": lambda: subject.list_active_clients(site_id="site-1", page=1, page_size=100, timeout_seconds=1),
        "pending-state": lambda: subject.get_pending_client_state(site_id="site-1", client_mac=MAC, timeout_seconds=1),
        "pending-reconnect": lambda: subject.reconnect_client(site_id="site-1", client_mac=MAC, timeout_seconds=1),
        "observation-clients": lambda: subject.list_observation_clients("site-1", 1, 100, 1),
        "observation-aps": lambda: subject.list_observation_access_points("site-1", 1, 100, 1),
    }
    return calls[name]()


def assert_unavailable(subject, name):
    if name == "sites":
        with pytest.raises(ControllerError, match="authority unavailable"):
            operation(subject, name)
    else:
        result = operation(subject, name)
        assert result.success is False
        assert not isinstance(result.data, list)
        assert "clients" not in (result.data or {})


@ROOT_FIXTURE
@pytest.mark.parametrize("name", OPERATIONS)
def test_every_request_site_uses_real_verified_tls(anchor, route_to, name):
    with omada_server(anchor) as server:
        route_to(server)
        subject = provider(anchor, name)
        result = operation(subject, name)
        assert result == [] if name == "sites" else result.success
        assert len(server.records) == 1
        assert server.records[0]["headers"]["Host"].lower() == "omada:8043"
        assert server.sni and all(value.lower() == "omada" for value in server.sni)
        assert subject._transport._context.verify_mode == ssl.CERT_REQUIRED
        assert subject._transport._context.check_hostname is True
        assert subject._transport._context.cert_store_stats()["x509"] == 1


@ROOT_FIXTURE
@pytest.mark.parametrize("name", OPERATIONS)
def test_every_request_site_rejects_unknown_peer_before_credentials(anchor, tmp_path, route_to, name, caplog):
    unknown = make_anchor(tmp_path, stem="unknown")
    with omada_server(unknown) as server:
        route_to(server)
        subject = provider(anchor, name)
        assert_unavailable(subject, name)
        assert server.records == []
        assert subject.tls_health["state"] == "unavailable"
        assert "DISPOSABLE_CLIENT_SECRET" not in caplog.text
        assert "DISPOSABLE_ACCESS_TOKEN" not in caplog.text


@ROOT_FIXTURE
@pytest.mark.parametrize("name", OPERATIONS)
@pytest.mark.parametrize("location", ["https://foreign.invalid:8043/capture", "http://Omada:8043/capture", "/other"])
def test_every_request_site_rejects_redirect_without_resending(anchor, route_to, name, location):
    with omada_server(anchor, lambda path: (302, {"Location": location}, {})) as server:
        route_to(server)
        subject = provider(anchor, name)
        assert_unavailable(subject, name)
        assert len(server.records) == 1
        assert subject.tls_health["failure_reason"] == "redirect_not_admitted"


@ROOT_FIXTURE
@pytest.mark.parametrize("name", EXTENSION_OPERATIONS)
def test_extension_sites_ignore_environment_proxy_ca_and_netrc(anchor, tmp_path, route_to, monkeypatch, name):
    with omada_server() as proxy, omada_server(anchor) as server:
        route_to(server)
        for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "https_proxy", "http_proxy", "all_proxy"):
            monkeypatch.setenv(key, f"http://127.0.0.1:{proxy.port}")
        monkeypatch.setenv("NO_PROXY", "")
        monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(tmp_path / "unapproved.pem"))
        netrc = tmp_path / "test-netrc"
        netrc.write_text("machine omada login BAD_NETRC_LOGIN password BAD_NETRC_SECRET\n")
        monkeypatch.setenv("NETRC", str(netrc))
        result = operation(provider(anchor, name), name)
        assert result.success
        assert proxy.records == []
        assert len(server.records) == 1
        assert server.records[0]["headers"]["Authorization"] == "AccessToken=DISPOSABLE_ACCESS_TOKEN"


@ROOT_FIXTURE
@pytest.mark.parametrize("name", EXTENSION_OPERATIONS)
def test_each_extension_site_rejects_proxy_failure_safely(anchor, monkeypatch, name, caplog):
    subject = provider(anchor, name)
    request = Mock(side_effect=requests.exceptions.ProxyError("PRIVATE_PROXY_TOKEN_CANARY"))
    monkeypatch.setattr(requests.Session, "request", request)
    assert_unavailable(subject, name)
    assert subject.tls_health["failure_reason"] == "proxy_not_admitted"
    assert "PRIVATE_PROXY_TOKEN_CANARY" not in caplog.text
    assert request.call_args.args[1].startswith("https://Omada:8043/openapi/")
    assert request.call_args.kwargs["allow_redirects"] is False
    assert request.call_args.kwargs["verify"] is True


@ROOT_FIXTURE
@pytest.mark.parametrize("url", ["http://Omada:8043/openapi/v1/x", "https://192.168.0.222:8043/openapi/v1/x",
                                 "https://localhost:8043/openapi/v1/x", "https://Omada:443/openapi/v1/x",
                                 "https://user:private@Omada:8043/openapi/v1/x", "https://Omada:8043/other",
                                 "https://Omada:8043/openapi/v1/../capture", "https://Omada:8043/openapi/v1/%2e%2e/capture"])
def test_unadmitted_origin_or_path_never_sends(anchor, monkeypatch, url):
    request = Mock(side_effect=AssertionError("network forbidden"))
    monkeypatch.setattr(requests.Session, "request", request)
    with pytest.raises(OmadaTransportError):
        provider(anchor)._request("GET", url, headers={"Authorization": "DISPOSABLE_ACCESS_TOKEN"})
    request.assert_not_called()


@ROOT_FIXTURE
@pytest.mark.parametrize("overrides", [{"verify": False}, {"proxies": {"https": "http://foreign.invalid"}},
                                      {"allow_redirects": True}, {"cert": "private.key"},
                                      {"headers": {"Host": "foreign.invalid"}}])
def test_policy_and_proxy_overrides_rejected_before_send(anchor, monkeypatch, overrides):
    request = Mock(side_effect=AssertionError("network forbidden"))
    monkeypatch.setattr(requests.Session, "request", request)
    with pytest.raises(OmadaTransportError):
        provider(anchor)._request("GET", "https://Omada:8043/openapi/v1/x", **overrides)
    request.assert_not_called()


@ROOT_FIXTURE
@pytest.mark.parametrize("state,expected", [("expired", "certificate_expired"), ("future", "certificate_not_yet_valid"),
                                           ("wrong-name", "name_mismatch"), ("wrong-eku", "certificate_purpose_invalid")])
def test_unusable_certificate_rejected_at_startup(tmp_path, state, expected):
    anchor = make_anchor(tmp_path, name="localhost" if state == "wrong-name" else "Omada",
                         state=state, eku=state != "wrong-eku")
    with pytest.raises(ConfigurationError, match=expected):
        provider(anchor)


@ROOT_FIXTURE
@pytest.mark.parametrize("kind", ["not-self-issued", "invalid-signature"])
def test_chain_or_self_signature_cannot_substitute_for_approved_leaf(tmp_path, kind):
    anchor = make_anchor(tmp_path, self_issued=kind != "not-self-issued",
                         signer=rsa.generate_private_key(public_exponent=65537, key_size=2048)
                         if kind == "invalid-signature" else None)
    with pytest.raises(ConfigurationError):
        provider(anchor)


@ROOT_FIXTURE
def test_general_ca_anchor_is_not_the_selected_leaf_policy(tmp_path):
    anchor = make_anchor(tmp_path, ca=True)
    with pytest.raises(ConfigurationError, match="trust_bundle_not_leaf"):
        provider(anchor)


@ROOT_FIXTURE
@pytest.mark.parametrize("kind", ["missing", "directory", "garbage", "bundle", "digest", "symlink", "writable", "hardlink"])
def test_invalid_or_unapproved_trust_file_fails_before_network(anchor, kind, tmp_path, monkeypatch):
    anchor.path.chmod(0o644)
    if kind == "missing":
        anchor.path.unlink()
    elif kind == "directory":
        anchor.path = tmp_path
    elif kind == "garbage":
        anchor.path.write_bytes(b"invalid certificate; PRIVATE_CANARY")
    elif kind == "bundle":
        anchor.path.write_bytes(anchor.path.read_bytes() + anchor.path.read_bytes())
    elif kind == "digest":
        anchor.sha = "0" * 64
    elif kind == "symlink":
        link = tmp_path / "link.pem"
        link.symlink_to(anchor.path)
        anchor.path = link
    elif kind == "writable":
        anchor.path.chmod(0o666)
    elif kind == "hardlink":
        os.link(anchor.path, tmp_path / "other.pem")
    request = Mock(side_effect=AssertionError("network forbidden"))
    monkeypatch.setattr(requests.Session, "request", request)
    with pytest.raises(ConfigurationError) as error:
        provider(anchor)
    assert "PRIVATE_CANARY" not in str(error.value)
    request.assert_not_called()


@ROOT_FIXTURE
def test_file_rotation_is_not_implicitly_admitted(anchor, tmp_path, route_to):
    subject = provider(anchor)
    replacement = make_anchor(tmp_path, stem="replacement")
    anchor.path.chmod(0o644)
    anchor.path.write_bytes(replacement.path.read_bytes())
    with omada_server(replacement) as server:
        route_to(server)
        with pytest.raises(ControllerError):
            subject.get_sites()
        assert server.records == []
    # Explicit new independently approved policy + new provider can admit it.
    with omada_server(replacement) as server:
        route_to(server)
        assert provider(replacement).get_sites() == []


@ROOT_FIXTURE
def test_new_self_signed_certificate_with_same_key_is_not_admitted(anchor, tmp_path, route_to):
    key = serialization.load_pem_private_key(anchor.key.read_bytes(), password=None)
    renewed = make_anchor(tmp_path, stem="renewed", key=key)
    assert renewed.sha != anchor.sha
    with omada_server(renewed) as server:
        route_to(server)
        subject = provider(anchor)
        with pytest.raises(ControllerError):
            subject.get_sites()
        assert server.records == []


@ROOT_FIXTURE
@pytest.mark.parametrize("exception,category", [(requests.Timeout("synthetic timeout"), "timeout"),
                                               (requests.ConnectionError("synthetic network"), "network_error")])
def test_unchanged_token_transport_failure_classification(anchor, monkeypatch, exception, category):
    subject = provider(anchor, "token")
    monkeypatch.setattr(requests.Session, "request", Mock(side_effect=exception))
    result = subject._get_token()
    assert result.success is False
    assert result.error == "HTTP_ERROR"
    assert result.data["failure_category"] == category and result.data["retryable"] is True
    assert subject._cached_token is None


@ROOT_FIXTURE
def test_first_failure_transitions_repeated_audit_and_recovery_are_visible(anchor, route_to, monkeypatch, caplog):
    subject = provider(anchor)
    with omada_server(anchor, lambda path: (302, {"Location": "https://private.invalid"}, {})) as server:
        route_to(server)
        for _ in range(3):
            with pytest.raises(ControllerError):
                subject.get_sites()
        assert caplog.text.count("reason=redirect_not_admitted") == 1
        assert subject.tls_health["repeated_failures"] == 2
        subject._transport._last_log -= 61  # deterministic heartbeat, no sleep/retry-until-green
        with pytest.raises(ControllerError):
            subject.get_sites()
        assert caplog.text.count("reason=redirect_not_admitted") == 2
        assert "repeated_failures=2" in caplog.text
    with omada_server(anchor) as server:
        route_to(server)
        assert subject.get_sites() == []
        assert subject.tls_health["state"] == "verified_last_connection"
        assert "state=verified" in caplog.text
    assert "DISPOSABLE_ACCESS_TOKEN" not in caplog.text


@ROOT_FIXTURE
def test_sites_token_tls_failure_is_not_authoritative_empty(anchor):
    subject = provider(anchor)
    subject._get_token = Mock(return_value=Result.fail(error="OMADA_TLS_UNAVAILABLE"))
    with pytest.raises(ControllerError):
        subject.get_sites()


@ROOT_FIXTURE
@pytest.mark.parametrize("case", ["token-network", "timeout", "network", "http", "api", "shape"])
def test_sites_failed_authority_is_never_a_zero_site_snapshot(anchor, monkeypatch, case):
    subject = provider(anchor)
    if case == "token-network":
        subject._get_token = Mock(return_value=Result.fail(error="HTTP_ERROR"))
    elif case in {"timeout", "network"}:
        exception = requests.Timeout("disposable timeout") if case == "timeout" else requests.ConnectionError("disposable DNS error")
        monkeypatch.setattr(requests.Session, "request", Mock(side_effect=exception))
    else:
        response = Mock(status_code=500 if case == "http" else 200)
        response.json.return_value = {"errorCode": 5 if case == "api" else 0,
                                      "result": {} if case == "shape" else {"data": []}}
        subject._request = Mock(return_value=response)
    with pytest.raises(ControllerError, match="authority unavailable"):
        subject.get_sites()


@ROOT_FIXTURE
@pytest.mark.parametrize("code,success", [(False, False), ("0", True)])
def test_sites_uses_canonical_typed_error_code_boundary(anchor, code, success):
    subject = provider(anchor)
    response = Mock(status_code=200)
    response.json.return_value = {"errorCode": code, "result": {"data": []}}
    subject._request = Mock(return_value=response)
    if success:
        assert subject.get_sites() == []
    else:
        with pytest.raises(ControllerError):
            subject.get_sites()


@ROOT_FIXTURE
def test_adopted_policy_is_immutable_and_public_projection_is_secret_free(anchor, monkeypatch):
    from app.admin_web.controller_settings import ControllerConfigurationReadService
    from app.settings_control.models import SettingsError
    config = build_omada_runtime_config(tls_settings(anchor))
    OmadaProvider(config)  # local file admission only, no connection
    monkeypatch.setenv("OMADA_TLS_TRUST_ANCHOR_PATH", "/unapproved/later.pem")
    snapshot = public_omada_snapshot(config, frozenset({"OMADA_TLS_TRUST_ANCHOR_PATH", "OMADA_TLS_TRUST_ANCHOR_SHA256"}))
    class Unavailable:
        def read_controller(self):
            raise SettingsError("settings_store_unavailable")
    response = ControllerConfigurationReadService(snapshot, Unavailable()).read("request-1")
    tls = response["fields"]["tls_certificate_verification"]
    assert tls["effective_value"] is True and tls["editable"] is False
    assert tls["verification_mode"] == "strict"
    assert tls["trust_anchor_source"] == "environment"
    assert tls["certificate_status"] == "verification_required_on_every_connection"
    text = json.dumps(response)
    assert str(anchor.path) not in text and "BEGIN CERTIFICATE" not in text
    assert "DISPOSABLE_CLIENT_SECRET" not in text


def test_pure_config_builder_requires_explicit_strict_policy_and_does_not_open_files(tmp_path, monkeypatch):
    from types import SimpleNamespace
    anchor = SimpleNamespace(path=tmp_path / "public.pem", sha="a" * 64)
    monkeypatch.setattr(os, "open", Mock(side_effect=AssertionError("builder must remain pure")))
    assert build_omada_runtime_config(tls_settings(anchor)).tls_policy.verification_mode == "strict"
    for overrides in ({"verify_ssl": False}, {"omada_tls_trust_anchor_path": ""},
                      {"omada_tls_trust_anchor_sha256": ""}, {"omada_url": "http://Omada:8043"}):
        with pytest.raises(ConfigurationError):
            build_omada_runtime_config(tls_settings(anchor, **overrides))


@ROOT_FIXTURE
def test_every_operation_establishes_fresh_verified_connection(anchor, route_to):
    subject = provider(anchor)
    with omada_server(anchor) as server:
        route_to(server)
        assert subject.get_sites() == []
        assert subject.get_sites() == []
        assert len(server.sni) == len(server.records) == 2


def test_inventory_covers_all_twelve_sites_without_global_trust_changes():
    root = Path(__file__).resolve().parents[1]
    counts = {}
    for name in ("omada", "omada_pending_sessions", "omada_observations"):
        source = (root / "app/controllers" / (name + ".py")).read_text(encoding="utf-8")
        tree = ast.parse(source)
        counts[name] = sum(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                           and node.func.attr == "_request" for node in ast.walk(tree))
        assert "requests.get(" not in source and "requests.post(" not in source
        assert "disable_warnings" not in source and "assert_hostname=False" not in source
        assert "verify=False" not in source
    assert counts == {"omada": 7, "omada_pending_sessions": 3, "omada_observations": 2}
    with requests.Session() as independent:
        assert independent.trust_env is True  # Omada policy has no process-global effect


def test_requests_new_and_old_adapter_paths_use_only_owned_context():
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    adapter = _OmadaTlsAdapter(context)
    request = requests.Request("GET", "https://Omada:8043/openapi/v1/x").prepare()
    host, policy = adapter.build_connection_pool_key_attributes(request, True)
    assert policy == {"ssl_context": context, "cert_reqs": "CERT_REQUIRED"}
    assert host["host"] == "omada" and adapter.poolmanager.connection_pool_kw["ssl_context"] is context
    with pytest.raises(OmadaTransportError):
        adapter.proxy_manager_for("http://unapproved.invalid")
    adapter.close()
