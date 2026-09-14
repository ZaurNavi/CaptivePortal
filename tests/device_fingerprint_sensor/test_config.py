import pytest

from app.device_fingerprint_sensor.config import sensor_config_from_env
from app.device_fingerprint_sensor.models import SensorConfigError


def enabled(**values):
    return {"DEVICE_FINGERPRINT_SENSOR_ENABLED": "true", **values}


def test_disabled_is_a_strict_noop_configuration():
    assert sensor_config_from_env({"DEVICE_FINGERPRINT_SENSOR_ENABLED": "false"}).enabled is False


def test_frozen_defaults_are_sensor_only():
    config = sensor_config_from_env(enabled(CREDENTIALS_DIRECTORY="/run/credentials/unit"))
    assert config.interface == "enp8s0"
    assert str(config.guest_cidrs[0]) == "192.168.8.0/22"
    assert config.raw_dedup_horizon_ms == 0.25
    assert config.credential_path.endswith("device-fingerprint-bearer")


@pytest.mark.parametrize("values", [
    {"DEVICE_FINGERPRINT_SENSOR_INTERFACE": "enp1s0"},
    {"DEVICE_FINGERPRINT_SENSOR_PRODUCER_ID": "sensor-zefer-02"},
    {"DEVICE_FINGERPRINT_SENSOR_CAPTURE_SOURCE_ID": "zefer-span-02"},
    {"DEVICE_FINGERPRINT_SENSOR_SITE_ID": "aaaaaaaaaaaaaaaaaaaaaaaa"},
    {"DEVICE_FINGERPRINT_SENSOR_GUEST_CIDRS": "192.168.8.1/22"},
    {"DEVICE_FINGERPRINT_SENSOR_EVIDENCE_BASE_URL": "http://192.168.0.202"},
    {"DEVICE_FINGERPRINT_SENSOR_RAW_DEDUP_HORIZON_MS": "nan"},
])
def test_invalid_sensor_configuration_fails_closed(values):
    with pytest.raises(SensorConfigError):
        sensor_config_from_env(enabled(**values))


def test_sensor_package_does_not_import_main_settings():
    import app.device_fingerprint_sensor.config as module
    source = open(module.__file__, encoding="utf-8").read()
    assert "app.settings" not in source
    assert "app.config" not in source
