from dataclasses import asdict
import pytest

from app.device_fingerprint_portal.config import portal_config_from_env
from app.device_fingerprint_portal.models import PortalEvidenceConfigError

P = "DEVICE_FINGERPRINT_PORTAL_"


def test_T01_entire_portal_legacy_defaults_and_disabled_ignore():
    expected = dict(enabled=False, producer_id="portal-zefer-01", capture_source_id="zefer-portal-http-01",
        site_id="6a64f17630da7c70d232187a", guest_cidrs=("192.168.8.0/22",), allowed_ssids=("Zefer_Parki",),
        evidence_base_url="https://192.168.0.202:9443/api/internal/device-fingerprint/v1",
        ca_cert_path="/etc/captive-portal/device-fingerprint/portal-ca.crt",
        credential_path="/etc/captive-portal/device-fingerprint/portal.bearer", queue_max_events=256,
        batch_size=50, queue_max_age_seconds=300, coalesce_seconds=21600, coalesce_max_entries=8192,
        connect_timeout_seconds=0.5, read_timeout_seconds=2.0, transient_cooldown_seconds=30, reject_cooldown_seconds=300)
    def snapshot(config):
        result = asdict(config)
        result["guest_cidrs"] = tuple(str(net) for net in config.guest_cidrs)
        return result
    assert snapshot(portal_config_from_env({})) == expected
    assert snapshot(portal_config_from_env({P + "ENABLED": "true"})) == {**expected, "enabled": True}
    assert snapshot(portal_config_from_env({P + key: None for key in ("SITE_ID", "GUEST_CIDRS", "ALLOWED_SSIDS",
        "CA_CERT_PATH", "CREDENTIAL_PATH", "PRODUCER_ID", "CAPTURE_SOURCE_ID", "EVIDENCE_BASE_URL", "BATCH_SIZE")})) == expected


def test_T03_custom_portal_configuration_and_frozen_tuning():
    config = portal_config_from_env({P + "ENABLED": "true", P + "PRODUCER_ID": "lab-portal-02",
        P + "CAPTURE_SOURCE_ID": "lab-portal-http-02", P + "SITE_ID": "a" * 24,
        P + "GUEST_CIDRS": "10.20.0.0/24,10.21.0.0/24", P + "ALLOWED_SSIDS": "Guest WiFi,Қонақ",
        P + "EVIDENCE_BASE_URL": "https://evidence.example:9443/api/internal/device-fingerprint/v1/",
        P + "CA_CERT_PATH": "/lab/portal-ca.crt", P + "CREDENTIAL_PATH": "/lab/protected/portal.bearer"})
    assert config.producer_id == "lab-portal-02" and config.capture_source_id == "lab-portal-http-02"
    assert config.site_id == "a" * 24 and config.allowed_ssids == ("Guest WiFi", "Қонақ")
    assert tuple(str(net) for net in config.guest_cidrs) == ("10.20.0.0/24", "10.21.0.0/24")
    assert config.evidence_base_url == "https://evidence.example:9443/api/internal/device-fingerprint/v1"
    assert config.ca_cert_path == "/lab/portal-ca.crt" and config.credential_path == "/lab/protected/portal.bearer"
    frozen = portal_config_from_env({})
    for field in ("queue_max_events", "batch_size", "queue_max_age_seconds", "coalesce_seconds", "coalesce_max_entries",
        "connect_timeout_seconds", "read_timeout_seconds", "transient_cooldown_seconds", "reject_cooldown_seconds"):
        assert getattr(config, field) == getattr(frozen, field)


@pytest.mark.parametrize("field", ["QUEUE_MAX_EVENTS", "BATCH_SIZE", "QUEUE_MAX_AGE_SECONDS", "COALESCE_SECONDS",
    "COALESCE_MAX_ENTRIES", "CONNECT_TIMEOUT_SECONDS", "READ_TIMEOUT_SECONDS", "TRANSIENT_COOLDOWN_SECONDS", "REJECT_COOLDOWN_SECONDS"])
def test_T03_all_portal_tuning_remains_pinned(field):
    with pytest.raises(PortalEvidenceConfigError):
        portal_config_from_env({P + "ENABLED": "true", P + field: "51"})


@pytest.mark.parametrize("ssids", [" ", "one,", ",one", "one,,two", "one,one", "*", "Guest*", "a" * 33,
    "é" * 17, "one\x00two", "one\ntwo", "one\x7ftwo", "\ud800", ",".join(str(i) for i in range(17))])
def test_T04_ssid_closed_bounds(ssids):
    with pytest.raises(PortalEvidenceConfigError):
        portal_config_from_env({P + "ENABLED": "true", P + "ALLOWED_SSIDS": ssids})


def test_T03_ssid_utf8_bytes_exact_case_and_sixteen_values():
    for value in ("é" * 16, "Guest,guest", ",".join(f"guest{i}" for i in range(16))):
        config = portal_config_from_env({P + "ENABLED": "true", P + "ALLOWED_SSIDS": value})
        assert config.allowed_ssids == tuple(value.split(","))


@pytest.mark.parametrize("field", ["CA_CERT_PATH", "CREDENTIAL_PATH"])
@pytest.mark.parametrize("path", ["relative/file", " /lab/file", "/lab/file ", "C:\\lab\\file", "/lab/\x00file"])
def test_T04_external_linux_paths_only(field, path):
    with pytest.raises(PortalEvidenceConfigError):
        portal_config_from_env({P + "ENABLED": "true", P + field: path})
