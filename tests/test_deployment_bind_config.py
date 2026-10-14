"""Pure deployment validation and fresh-process startup; no sockets or real providers."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from app.config import (_parse_bind_host, _parse_bind_port, _validate_capport_site_id,
    _normalize_capport_public_base_url, _validate_capport_allowed_network_values,
    _parse_capport_allowed_networks_csv)
from app.capport.models import CapportConfig


KEYS = ("HOST", "PORT", "CAPPORT_SITE_ID", "CAPPORT_PUBLIC_BASE_URL", "CAPPORT_ALLOWED_CLIENT_NETWORKS")
READ = '''
import json, sys
try:
    import app.config as config
    from app.settings import get_settings
    from app.capport.models import CapportConfig
except ValueError as error:
    print(str(error), file=sys.stderr)
    raise SystemExit(3)
settings = get_settings()
capport = CapportConfig.from_settings(settings)
names = ("host", "port", "capport_site_id", "capport_public_base_url", "capport_allowed_client_networks")
print(json.dumps(dict(config={key:getattr(config,key) for key in %r}, settings={key:settings[key] for key in names},
    types=[type(settings[key]).__name__ for key in names], login_url=capport.login_url,
    networks=[str(net) for net in capport.allowed_networks])))
''' % (KEYS,)


def _startup(variables=None, snippet=READ):
    env = os.environ.copy()
    for key in KEYS:
        env.pop(key, None)
    env.update(variables or {})
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run([sys.executable, "-c", snippet], cwd=Path(__file__).parents[1],
        env=env, capture_output=True, text=True, timeout=30)


def _typed(**changes):
    settings = dict(host="172.18.0.1", capport_site_id="a" * 24,
        capport_public_base_url="https://portal.example", capport_api_path="/capport/api",
        capport_login_path="/capport/login", capport_allowed_client_networks=("192.168.8.0/22",),
        capport_client_cache_ttl_seconds=2, capport_failure_cache_ttl_seconds=2)
    settings.update(changes)
    return CapportConfig.from_settings(settings)


def test_T01_absent_keys_exact_defaults_and_typed_mapping():
    result = _startup()
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    defaults = dict(HOST="127.0.0.1", PORT=8088, CAPPORT_SITE_ID="6a64f17630da7c70d232187a",
        CAPPORT_PUBLIC_BASE_URL="https://captivportal-navi.duckdns.org",
        CAPPORT_ALLOWED_CLIENT_NETWORKS=["192.168.1.0/24", "192.168.8.0/22"])
    assert data["config"] == defaults
    assert list(data["settings"].values()) == list(defaults.values())
    assert data["types"] == ["str", "int", "str", "str", "tuple"]
    assert data["login_url"] == "https://captivportal-navi.duckdns.org/capport/login"
    assert data["networks"] == defaults["CAPPORT_ALLOWED_CLIENT_NETWORKS"]


CAPTURE = '''
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch
import run
captured = {}
class NoListenApp:
    extensions = {}
    def run(self, **kwargs):
        captured.update(kwargs)
def bootstrap(**kwargs):
    return SimpleNamespace(runtime_settings=kwargs["base_settings"], controller_secret_resolution=None,
        activation_service=None, resolved_snapshot=None, feature_plan=object(), admin_context=None)
def create_app(controller, visitor_snapshot_collector, settings):
    return NoListenApp()
identity = Mock(return_value=SimpleNamespace(json_line=lambda:"synthetic-identity"))
with patch.multiple(run, capture_loaded_artifact_identity=identity, logger=Mock(),
    bootstrap_settings_control=bootstrap, build_omada_runtime_config=Mock(return_value=object()),
    create_controller=Mock(return_value=object()), public_omada_snapshot=Mock(return_value=None),
    create_visitor_snapshot_collector=Mock(return_value=Mock()),
    create_visit_lifecycle=Mock(return_value=Mock()), create_app=create_app,
    create_observation_foundation=Mock(return_value=Mock()),
    create_pending_session_cleaner=Mock(return_value=Mock()),
    create_visitor_registry=Mock(return_value=SimpleNamespace(available=False, start=Mock())),
    _configure_current_state=Mock(), _configure_analytics=Mock(), _configure_admin_web=Mock(),
    _start_public_traffic_worker=Mock(), shutdown_handler=Mock()), \
    patch.object(run.signal,"signal"), patch.object(run.atexit,"register"):
    run.main()
identity.assert_called_once_with("captive-portal.service")
print(json.dumps(captured))
'''


@pytest.mark.parametrize("variables,host,port", [({}, "127.0.0.1", 8088),
    ({"HOST": "172.18.0.1", "PORT": "18089"}, "172.18.0.1", 18089)])
def test_T02_actual_unchanged_run_main_capture_no_listen(variables, host, port):
    result = _startup(variables, CAPTURE)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == dict(host=host, port=port, debug=False, use_reloader=False)


def test_T02_artifact_identity_failure_still_precedes_bootstrap_and_listen():
    code = '''
from unittest.mock import Mock, patch
import run
with patch.object(run,"logger",Mock()), patch.object(run,"capture_loaded_artifact_identity",side_effect=run.ArtifactIdentityError()), \
    patch.object(run,"bootstrap_settings_control") as bootstrap, patch.object(run,"create_app") as app:
    try:
        run.main()
    except SystemExit as error:
        assert error.code == 1
    else:
        raise AssertionError("identity guard bypassed")
    bootstrap.assert_not_called()
    app.assert_not_called()
'''
    result = _startup(snippet=code)
    assert result.returncode == 0, result.stderr


HOST_INVALID = ["", " ", " 172.18.0.1", "172.18.0.1 ", "0.0.0.0", "127.0.0.2", "127.1.2.3",
    "::", "::1", "localhost", "eth0", "8.8.8.8", "169.254.1.1", "224.1.1.1", "172.32.0.1",
    "172.18.00.1", "127.1", "172.18.0.1,127.0.0.1", "172.18.0.999"]
PORT_INVALID = ["", "0", "80", "1023", "65536", "+18089", "-1", " 18089", "18089 ",
    "018089", "18089.0", "١٨٠٨٩", "１８０８９", "12345678901234567890"]
SITE_INVALID = ["", " ", "a" * 23, "a" * 25, "A" * 24, "g" * 24, "a" * 24 + " ", "site-1", "<site>"]
URL_INVALID = ["", "http://portal.example", "HTTPS://portal.example", "https://user:pass@portal.example",
    "https://portal.example/a", "https://portal.example?", "https://portal.example#", "https://portal.example//",
    "https://portal.example:0", "https://portal.example:65536", "https://portal.example:abc", "https://portal.example:",
    "https://portal.example:0443", "https://portal_example", "https://[::1]", "https://192.168.0.1",
    "https://%65xample.com", "https://portal.example\\evil", "https://portal.example\n", "https://por\ttal.example",
    " https://portal.example", "https://éxample.com", "https://portal.example.", "https://.portal.example",
    "https://portal..example", "https://-portal.example", "https://portal-.example", "https://999.1.2.3",
    "https://" + "a" * 64 + ".example", "https://" + ".".join(["a" * 63] * 4), "https://portal.example\x7f",
    "https://2130706433", "https://0x7f000001", "https://0X7F000001", "https://0x7f.0.0.1",
    "https://0x7f.0.0.0x1", "https://0x", "https://0X", "https://012345", "https://192.168.1", "https://portal.123"]
NETWORK_INVALID = ["", "192.168.8.2/22", "192.168.8.0/22,", ",192.168.8.0/22",
    "192.168.8.0/22, 192.168.1.0/24", "192.168.8.0/22,192.168.8.0/22", "0.0.0.0/0", "::/0",
    "192.168.8.1", "192.168.008.0/22", "2001:0db8::/64", "2001:DB8::/64", "2001:db8::1/64",
    "192.168.8.0/255.255.252.0", ",".join(f"10.0.{i}.0/24" for i in range(17))]


@pytest.mark.parametrize("key,values", [("HOST", HOST_INVALID), ("PORT", PORT_INVALID),
    ("CAPPORT_SITE_ID", SITE_INVALID), ("CAPPORT_PUBLIC_BASE_URL", URL_INVALID),
    ("CAPPORT_ALLOWED_CLIENT_NETWORKS", NETWORK_INVALID)])
def test_T03_T07_invalid_explicit_startup_no_fallback(key, values):
    for value in values:
        result = _startup({key: value})
        assert result.returncode != 0
        assert result.stdout == ""
        assert result.stderr.startswith(key + " ")
        assert "Traceback" not in result.stderr


@pytest.mark.parametrize("key,value", [("HOST", "0.0.0.0"), ("HOST", ""), ("PORT", "80"), ("PORT", ""),
    ("CAPPORT_SITE_ID", ""), ("CAPPORT_PUBLIC_BASE_URL", "http://portal.example"),
    ("CAPPORT_ALLOWED_CLIENT_NETWORKS", "0.0.0.0/0")])
def test_invalid_bind_eager_even_disabled_capport_test_fixture(key, value):
    # Isolated synthetic config module: only CAPPORT_ENABLED literal is False.
    # Clear inputs before package import, then execute the real parser/startup AST.
    snippet = '''
import ast, os, sys
from pathlib import Path
keys = %r
explicit = {key:os.environ.pop(key) for key in keys if key in os.environ}
import app.config
os.environ.update(explicit)
tree = ast.parse(Path("app/config.py").read_text())
for node in tree.body:
    if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=="CAPPORT_ENABLED" for target in node.targets):
        node.value = ast.Constant(False)
ast.fix_missing_locations(tree)
try:
    exec(compile(tree,"app/config.py","exec"), {"__name__":"app.config","__package__":"app"})
except ValueError as error:
    print(str(error),file=sys.stderr)
    raise SystemExit(3)
raise AssertionError("invalid bind survived")
''' % (KEYS,)
    result = _startup({key: value}, snippet)
    assert result.returncode == 3
    assert result.stderr.startswith(key + " ") and result.stdout == ""


@pytest.mark.parametrize("host", ["127.0.0.1", "10.0.0.0", "10.255.255.255", "172.16.0.0", "172.31.255.255", "192.168.0.0", "192.168.255.255"])
def test_T03_exact_rfc1918_not_interface_existence(host):
    assert _parse_bind_host(host) == host


@pytest.mark.parametrize("port", ["1024", "8088", "18089", "65535"])
def test_T04_valid_ports(port):
    assert _parse_bind_port(port) == int(port)


@pytest.mark.parametrize("origin,expected", [("https://portal.example", "https://portal.example"),
    ("https://PORTAL.Example/", "https://portal.example"), ("https://portal.example:8443/", "https://portal.example:8443"),
    ("https://portal.example:1", "https://portal.example:1"), ("https://portal.example:65535", "https://portal.example:65535"),
    ("https://xn--example.test/", "https://xn--example.test"), ("https://portal", "https://portal"),
    ("https://abc123", "https://abc123"), ("https://PORTAL.abc123:8443/", "https://portal.abc123:8443")])
def test_T06_exact_origin_canonicalization(origin, expected):
    assert _normalize_capport_public_base_url(origin) == expected
    assert _typed(capport_public_base_url=origin).login_url == expected + "/capport/login"


@pytest.mark.parametrize("origin", [
    "https://2130706433", "https://0x7f000001", "https://0X7F000001", "https://0x7f.0.0.1",
    "https://0x7f.0.0.0x1", "https://0x", "https://0X", "https://012345", "https://192.168.1", "https://portal.123",
])
def test_R1_numeric_ip_alias_pure_and_typed_generic_rejection(origin):
    message = "CAPPORT_PUBLIC_BASE_URL must be a canonical HTTPS DNS origin"
    for validate in (
        lambda: _normalize_capport_public_base_url(origin),
        lambda: _typed(capport_public_base_url=origin),
    ):
        with pytest.raises(ValueError) as caught:
            validate()
        assert str(caught.value) == message
        assert origin not in str(caught.value)
        assert caught.value.__cause__ is None
    # Every vector also goes through the fresh-process URL_INVALID startup matrix.
    assert origin in URL_INVALID


@pytest.mark.parametrize("key,values", [("capport_site_id", SITE_INVALID), ("capport_public_base_url", URL_INVALID),
    ("capport_allowed_client_networks", NETWORK_INVALID)])
def test_T05_T07_typed_inputs_same_closed_policy(key, values):
    for value in values:
        with pytest.raises(ValueError):
            _typed(**{key: value})


@pytest.mark.parametrize("value", [None, True, 123, [], {}])
def test_non_string_and_untyped_values_rejected_without_coercion(value):
    for validator in (_parse_bind_host, _parse_bind_port, _validate_capport_site_id,
                      _normalize_capport_public_base_url, _parse_capport_allowed_networks_csv):
        with pytest.raises(ValueError):
            validator(value)
    for key in ("capport_site_id", "capport_public_base_url", "capport_allowed_client_networks"):
        with pytest.raises(ValueError):
            _typed(**{key: value})


@pytest.mark.parametrize("networks", [("192.168.8.0/22",), ("192.168.1.0/24", "192.168.8.0/22"),
    ("192.168.8.0/22", "2001:db8::/64"), tuple(f"10.0.{i}.0/24" for i in range(16))])
def test_T07_valid_csv_and_typed_networks_preserve_order(networks):
    assert _validate_capport_allowed_network_values(networks) == networks
    assert _parse_capport_allowed_networks_csv(",".join(networks)) == networks
    assert tuple(str(net) for net in _typed(capport_allowed_client_networks=networks).allowed_networks) == networks
    result = _startup({"CAPPORT_ALLOWED_CLIENT_NETWORKS": ",".join(networks)})
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["types"][-1] == "tuple"
    assert data["networks"] == list(networks)


def test_T05_T07_custom_environment_mapping_and_single_cidr_typed_compatibility():
    result = _startup({"HOST": "172.18.0.1", "PORT": "18089", "CAPPORT_SITE_ID": "b" * 24,
        "CAPPORT_PUBLIC_BASE_URL": "https://CAPTIVPROD-navi.duckdns.org:8443/",
        "CAPPORT_ALLOWED_CLIENT_NETWORKS": "10.20.0.0/24,2001:db8::/64"})
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["settings"] == dict(host="172.18.0.1", port=18089, capport_site_id="b" * 24,
        capport_public_base_url="https://captivprod-navi.duckdns.org:8443",
        capport_allowed_client_networks=["10.20.0.0/24", "2001:db8::/64"])
    assert data["login_url"] == "https://captivprod-navi.duckdns.org:8443/capport/login"
    assert tuple(str(net) for net in _typed(capport_allowed_client_networks="192.168.8.0/22").allowed_networks) == ("192.168.8.0/22",)
    with pytest.raises(ValueError):
        _typed(capport_allowed_client_networks=["192.168.8.0/22"])


def test_invalid_values_error_messages_do_not_echo_submitted_bytes():
    for validator, value, key in [(_parse_bind_host, "HOST_CANARY.invalid", "HOST"),
        (_parse_bind_port, "PORT_CANARY.invalid", "PORT"), (_validate_capport_site_id, "SITE_CANARY.invalid", "CAPPORT_SITE_ID"),
        (_normalize_capport_public_base_url, "https://SECRET_CANARY:credential@portal.example", "CAPPORT_PUBLIC_BASE_URL"),
        (_parse_capport_allowed_networks_csv, "NETWORK_CANARY.invalid", "CAPPORT_ALLOWED_CLIENT_NETWORKS")]:
        with pytest.raises(ValueError) as caught:
            validator(value)
        assert str(caught.value).startswith(key + " ")
        assert value not in str(caught.value) and caught.value.__cause__ is None
