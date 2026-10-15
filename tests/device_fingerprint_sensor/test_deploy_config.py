"""DEPLOY-CONFIG-02 T01–T04: disposable syntactic claims, never admission."""
from dataclasses import asdict
import pytest

from app.device_fingerprint_sensor.config import sensor_config_from_env
from app.device_fingerprint_sensor.models import SensorConfigError
from app.device_fingerprint_portal.config import portal_config_from_env
from app.device_fingerprint_portal.models import PortalEvidenceConfigError


PREFIX = "/api/internal/device-fingerprint/v1"
SENSOR = "DEVICE_FINGERPRINT_SENSOR_"
PORTAL = "DEVICE_FINGERPRINT_PORTAL_"


def parse(kind, **values):
    prefix, parser = (SENSOR, sensor_config_from_env) if kind == "sensor" else (PORTAL, portal_config_from_env)
    return parser({prefix + "ENABLED": "true", **{prefix + key: value for key, value in values.items()}})


def snapshot(config):
    result = asdict(config)
    result["guest_cidrs"] = tuple(str(network) for network in config.guest_cidrs)
    return result


def test_T01_entire_sensor_legacy_defaults_enabled_and_disabled():
    expected = dict(enabled=False, interface="enp8s0", producer_id="sensor-zefer-01", capture_source_id="zefer-span-01",
        site_id="6a64f17630da7c70d232187a", guest_cidrs=("192.168.8.0/22",),
        dhcp_server_authority="192.168.10.1", dhcp_option54_authority="192.168.10.1",
        evidence_base_url="https://192.168.0.202:9443" + PREFIX,
        ca_cert_path="/etc/captive-portal/device-fingerprint/sensor-ca.crt", credential_path=None,
        spool_path="/var/lib/captive-portal/fingerprint-sensor/spool.sqlite3", spool_total_budget_bytes=134217728,
        spool_main_db_max_bytes=117440512, spool_write_headroom_bytes=16777216, spool_max_events=100000,
        delivery_batch_size=100, http_timeout_seconds=5.0, raw_dedup_max_entries=65536, raw_dedup_horizon_ms=0.25,
        core_ready_host="127.0.0.1", core_ready_port=8088, core_ready_connect_timeout_seconds=1.0,
        core_ready_poll_interval_seconds=10.0, core_ready_max_wait_seconds=1800.0, eve_max_datagram_bytes=262144,
        eve_socket_path="/run/captive-portal/fingerprint-sensor/suricata-eve.sock", eve_socket_wait_seconds=1830,
        io_stale_purge_gate_enabled=False, io_telemetry_aggregation_enabled=False, io_ingress_coalesce_enabled=False)
    assert snapshot(sensor_config_from_env({})) == expected
    assert snapshot(parse("sensor")) == {**expected, "enabled": True}
    bad = {SENSOR + key: None for key in ("INTERFACE", "SITE_ID", "PRODUCER_ID", "CAPTURE_SOURCE_ID",
        "GUEST_CIDRS", "DHCP_SERVER_AUTHORITY", "DHCP_OPTION54_AUTHORITY", "EVIDENCE_BASE_URL",
        "CORE_READY_HOST", "CORE_READY_PORT", "CA_CERT_PATH", "SPOOL_PATH", "EVE_SOCKET_PATH")}
    assert snapshot(sensor_config_from_env(bad)) == expected


@pytest.mark.parametrize("flag", ["IO_STALE_PURGE_GATE_ENABLED", "IO_TELEMETRY_AGGREGATION_ENABLED", "IO_INGRESS_COALESCE_ENABLED"])
def test_T01_disabled_still_validates_original_wave2_booleans(flag):
    with pytest.raises(SensorConfigError):
        sensor_config_from_env({SENSOR + flag: "not-a-boolean"})
    config = sensor_config_from_env({SENSOR + flag: "true", SENSOR + "SITE_ID": "bad"})
    assert not config.enabled and getattr(config, flag.lower()) is True


def test_T02_custom_sensor_fields_typed_and_no_io(monkeypatch):
    import socket
    from pathlib import Path
    def forbidden(*_args, **_kwargs):
        pytest.fail("configuration must never perform socket/filesystem I/O")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "exists", forbidden)
    values = dict(INTERFACE="enp1s0", PRODUCER_ID="lab-sensor-02", CAPTURE_SOURCE_ID="lab-span-02",
        SITE_ID="a" * 24, GUEST_CIDRS="10.20.0.0/24,10.21.0.0/24", DHCP_SERVER_AUTHORITY="203.0.113.1",
        DHCP_OPTION54_AUTHORITY="198.51.100.1", EVIDENCE_BASE_URL="https://evidence.example:9443" + PREFIX + "/",
        CORE_READY_HOST="172.18.0.1", CORE_READY_PORT="18089", CA_CERT_PATH="/lab/sensor-ca.crt",
        SPOOL_PATH="/lab/new-empty-spool.sqlite3", EVE_SOCKET_PATH="/lab/eve.sock")
    config = parse("sensor", **values)
    for key in ("INTERFACE", "PRODUCER_ID", "CAPTURE_SOURCE_ID", "SITE_ID", "DHCP_SERVER_AUTHORITY",
                "DHCP_OPTION54_AUTHORITY", "CORE_READY_HOST", "CA_CERT_PATH", "SPOOL_PATH", "EVE_SOCKET_PATH"):
        assert getattr(config, key.lower()) == values[key]
    assert type(config.core_ready_port) is int and config.core_ready_port == 18089
    assert tuple(str(network) for network in config.guest_cidrs) == ("10.20.0.0/24", "10.21.0.0/24")
    assert config.evidence_base_url == values["EVIDENCE_BASE_URL"][:-1]
    assert config.credential_path is None


URL_BAD = ["http://evidence.example" + PREFIX, "https://evidence.example", "https://user:secret@evidence.example" + PREFIX,
    "https://evidence.example" + PREFIX + "?", "https://evidence.example" + PREFIX + "#",
    "https://evidence.example" + PREFIX + "//", "https://evidence.example" + PREFIX + "/extra",
    "https://evidence.example/x/../" + PREFIX.lstrip("/"), "https://%65vidence.example" + PREFIX,
    "https://evidence.example:0" + PREFIX, "https://evidence.example:65536" + PREFIX,
    "https://evidence.example:0443" + PREFIX, "https://evidence.example:" + PREFIX,
    "https://evidence_example" + PREFIX, "https://[::1]" + PREFIX, "https://evidence.example\\evil" + PREFIX,
    "https://2130706433" + PREFIX, "https://0x7f000001" + PREFIX, "https://127.1" + PREFIX,
    "https://0x" + PREFIX, "https://portal.123" + PREFIX, "https://127.0.0.2" + PREFIX,
    "https://8.8.8.8" + PREFIX, "https://0.0.0.0" + PREFIX, "https://169.254.0.1" + PREFIX,
    "https://192.168.000.1" + PREFIX, "https://evidence.example." + PREFIX,
    "https://evidence.example\n" + PREFIX, "https://évidence.example" + PREFIX]
CIDR_BAD = ["0.0.0.0/0", "10.20.0.1/24", "10.20.0.0/24,", ",10.20.0.0/24", "10.20.0.0/24, 10.21.0.0/24",
    "10.20.0.0/24,10.20.0.0/24", "10.20.0.0/24,10.20.0.0/25", "2001:db8::/64", "10.20.00.0/24",
    "10.20.0.0/255.255.255.0", "10.20.0.1", ",".join(f"10.{i}.0.0/16" for i in range(17))]


@pytest.mark.parametrize("kind", ["sensor", "portal"])
@pytest.mark.parametrize("url", URL_BAD)
def test_T04_same_strict_endpoint_policy(kind, url):
    with pytest.raises((SensorConfigError, PortalEvidenceConfigError)) as caught:
        parse(kind, EVIDENCE_BASE_URL=url)
    assert url not in str(caught.value) and caught.value.__cause__ is None


@pytest.mark.parametrize("kind", ["sensor", "portal"])
@pytest.mark.parametrize("url", ["https://evidence.example" + PREFIX, "https://127.0.0.1:9443" + PREFIX,
    "https://172.18.0.1:1" + PREFIX + "/", "https://evidence.example:65535" + PREFIX,
    "https://xn--example.test" + PREFIX])
def test_T02_T03_valid_direct_tls_endpoint(kind, url):
    assert parse(kind, EVIDENCE_BASE_URL=url).evidence_base_url == url.removesuffix("/")


@pytest.mark.parametrize("kind", ["sensor", "portal"])
@pytest.mark.parametrize("cidrs", CIDR_BAD)
def test_T04_cidr_never_widens_or_overlaps(kind, cidrs):
    with pytest.raises((SensorConfigError, PortalEvidenceConfigError)):
        parse(kind, GUEST_CIDRS=cidrs)


@pytest.mark.parametrize("kind", ["sensor", "portal"])
def test_T02_T03_sixteen_canonical_nonoverlapping_networks(kind):
    values = tuple(f"10.{i}.0.0/16" for i in range(16))
    assert tuple(str(network) for network in parse(kind, GUEST_CIDRS=",".join(values)).guest_cidrs) == values


SENSOR_FIELDS = ("INTERFACE", "CORE_READY_HOST", "CORE_READY_PORT", "PRODUCER_ID", "CAPTURE_SOURCE_ID", "SITE_ID",
    "GUEST_CIDRS", "DHCP_SERVER_AUTHORITY", "DHCP_OPTION54_AUTHORITY", "EVIDENCE_BASE_URL")
PORTAL_FIELDS = ("PRODUCER_ID", "CAPTURE_SOURCE_ID", "SITE_ID", "GUEST_CIDRS", "ALLOWED_SSIDS",
    "EVIDENCE_BASE_URL", "CA_CERT_PATH", "CREDENTIAL_PATH")


@pytest.mark.parametrize("kind,fields", [("sensor", SENSOR_FIELDS), ("portal", PORTAL_FIELDS)])
@pytest.mark.parametrize("value", ["", None, True, 42, [], {}, "\n", "\x00"])
def test_T04_enabled_empty_wrong_types_controls_fail_closed(kind, fields, value):
    for field in fields:
        with pytest.raises((SensorConfigError, PortalEvidenceConfigError)):
            parse(kind, **{field: value})


@pytest.mark.parametrize("field,values", [
    ("INTERFACE", ["lo", "any", "*", "/dev/eth0", "../eth0", ".eth0", "-eth0", "enp 1", "enp1s0 ", "еnp1s0", "a" * 16]),
    ("CORE_READY_HOST", ["0.0.0.0", "127.0.0.2", "8.8.8.8", "224.0.0.1", "255.255.255.255", "169.254.1.1", "core.example", "::1", "127.1", "2130706433", "0x7f000001", "172.018.0.1", "172.18.0.1 "]),
    ("CORE_READY_PORT", ["80", "1023", "65536", "08088", "+8088", "8088 ", " 8088", "٨٠٨٨", "8088.0"]),
    ("DHCP_SERVER_AUTHORITY", ["0.0.0.0", "255.255.255.255", "224.0.0.1", "dhcp.example", "192.168.010.1", "::1", "2130706433"]),
    ("DHCP_OPTION54_AUTHORITY", ["0.0.0.0", "255.255.255.255", "224.0.0.1", "dhcp.example", "192.168.010.1", "::1", "2130706433"]),
])
def test_T04_sensor_negative_deployment_fields(field, values):
    for value in values:
        with pytest.raises(SensorConfigError):
            parse("sensor", **{field: value})


@pytest.mark.parametrize("kind", ["sensor", "portal"])
@pytest.mark.parametrize("field", ["PRODUCER_ID", "CAPTURE_SOURCE_ID", "SITE_ID"])
def test_T04_identity_exact_not_casefolded_or_trimmed(kind, field):
    values = ["-bad", "Uppercase", "bad/path", "identity ", " identity", "а" * 24, "a" * 65]
    if field == "SITE_ID":
        values += ["a" * 23, "a" * 25, "A" * 24, "g" * 24]
    for value in values:
        with pytest.raises((SensorConfigError, PortalEvidenceConfigError)):
            parse(kind, **{field: value})
