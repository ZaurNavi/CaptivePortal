import json
import importlib

import pytest

from app.device_fingerprint.config import device_fingerprint_config_from_settings
from app.device_fingerprint.models import DeviceFingerprintConfigError
from tests.device_fingerprint import SITE, TOKEN


def enabled_settings(tmp_path):
    return {
        "device_fingerprint_evidence_enabled": "true",
        "device_fingerprint_db_path": str(tmp_path / "db.sqlite3"),
        "device_fingerprint_writer_lock_path": str(tmp_path / "db.lock"),
        "device_fingerprint_bind_address": "127.0.0.1",
        "device_fingerprint_tls_cert_path": str(tmp_path / "cert"),
        "device_fingerprint_tls_key_path": str(tmp_path / "key"),
        "device_fingerprint_api_allowed_networks": "127.0.0.0/8",
        "device_fingerprint_producers_json": json.dumps([{
            "producer_id": "sensor-zefer-01", "bearer_token": TOKEN,
            "capture_source_id": "zefer-span-01", "site_id": SITE,
            "allowed_guest_cidrs": ["192.168.8.0/22"],
            "allowed_source_kinds": ["dhcp"],
        }]),
    }


def test_disabled_default_requires_no_secret_or_tls(tmp_path):
    result = device_fingerprint_config_from_settings({})
    assert result.enabled is False
    assert result.producers == ()


def test_enabled_exact_defaults_and_redacts_secret(tmp_path):
    result = device_fingerprint_config_from_settings(enabled_settings(tmp_path))
    assert result.port == 9443
    assert result.retention_days == 30
    assert (
        result.max_future_skew_seconds,
        result.max_delayed_event_age_seconds,
        result.max_db_bytes,
        result.max_http_request_bytes,
        result.max_events_per_batch,
        result.max_payload_bytes,
        result.max_concurrent_ingest_requests,
    ) == (120, 86_400, 1_073_741_824, 1_048_576, 100, 8_192, 2)
    assert TOKEN not in repr(result)
    assert TOKEN not in repr(result.producers[0])


@pytest.mark.parametrize("key,value", [
    ("device_fingerprint_retention_days", "0"),
    ("device_fingerprint_max_future_skew_seconds", "601"),
    ("device_fingerprint_max_delayed_event_age_seconds", "59"),
    ("device_fingerprint_max_db_bytes", "67108863"),
    ("device_fingerprint_max_http_request_bytes", "65535"),
    ("device_fingerprint_max_events_per_batch", "501"),
    ("device_fingerprint_max_payload_bytes", "255"),
    ("device_fingerprint_max_concurrent_ingest_requests", "9"),
    ("device_fingerprint_port", "0"),
    ("device_fingerprint_retention_days", "91"),
    ("device_fingerprint_max_future_skew_seconds", "-1"),
    ("device_fingerprint_max_delayed_event_age_seconds", "604801"),
    ("device_fingerprint_max_db_bytes", "8589934593"),
    ("device_fingerprint_max_http_request_bytes", "4194305"),
    ("device_fingerprint_max_events_per_batch", "0"),
    ("device_fingerprint_max_payload_bytes", "65537"),
    ("device_fingerprint_max_concurrent_ingest_requests", "0"),
    ("device_fingerprint_port", "65536"),
])
def test_strict_resource_bounds(tmp_path, key, value):
    settings = enabled_settings(tmp_path)
    settings[key] = value
    with pytest.raises(DeviceFingerprintConfigError):
        device_fingerprint_config_from_settings(settings)


@pytest.mark.parametrize("key,minimum,maximum", [
    ("device_fingerprint_retention_days", 1, 90),
    ("device_fingerprint_max_future_skew_seconds", 0, 600),
    ("device_fingerprint_max_delayed_event_age_seconds", 60, 604800),
    ("device_fingerprint_max_db_bytes", 67_108_864, 8_589_934_592),
    ("device_fingerprint_max_http_request_bytes", 65_536, 4_194_304),
    ("device_fingerprint_max_events_per_batch", 1, 500),
    ("device_fingerprint_max_payload_bytes", 256, 65_536),
    ("device_fingerprint_max_concurrent_ingest_requests", 1, 8),
    ("device_fingerprint_port", 1, 65_535),
])
def test_resource_bounds_are_inclusive(tmp_path, key, minimum, maximum):
    for value in (minimum, maximum):
        settings = enabled_settings(tmp_path)
        settings[key] = str(value)
        device_fingerprint_config_from_settings(settings)


def test_duplicate_secrets_and_extra_producer_keys_fail(tmp_path):
    settings = enabled_settings(tmp_path)
    item = json.loads(settings["device_fingerprint_producers_json"])[0]
    settings["device_fingerprint_producers_json"] = json.dumps([item, {**item, "producer_id": "sensor-two", "capture_source_id": "span-two"}])
    with pytest.raises(DeviceFingerprintConfigError):
        device_fingerprint_config_from_settings(settings)
    settings = enabled_settings(tmp_path)
    item = json.loads(settings["device_fingerprint_producers_json"])[0]
    item["extra"] = True
    settings["device_fingerprint_producers_json"] = json.dumps([item])
    with pytest.raises(DeviceFingerprintConfigError):
        device_fingerprint_config_from_settings(settings)


@pytest.mark.parametrize("duplicate_field,replacement", [
    ("bearer_token", {"producer_id": "sensor-two", "capture_source_id": "span-two"}),
    ("producer_id", {"bearer_token": "B" * 32, "capture_source_id": "span-two"}),
    ("capture_source_id", {"bearer_token": "B" * 32, "producer_id": "sensor-two"}),
])
def test_duplicate_producer_authorities_are_rejected_independently(
    tmp_path, duplicate_field, replacement
):
    settings = enabled_settings(tmp_path)
    first = json.loads(settings["device_fingerprint_producers_json"])[0]
    second = {**first, **replacement}
    second[duplicate_field] = first[duplicate_field]
    settings["device_fingerprint_producers_json"] = json.dumps([first, second])
    with pytest.raises(DeviceFingerprintConfigError):
        device_fingerprint_config_from_settings(settings)


def test_exact_environment_and_settings_key_mapping(monkeypatch):
    expected = {
        "DEVICE_FINGERPRINT_EVIDENCE_ENABLED": "true",
        "DEVICE_FINGERPRINT_DB_PATH": "/absolute/evidence.sqlite3",
        "DEVICE_FINGERPRINT_WRITER_LOCK_PATH": "/absolute/evidence.lock",
        "DEVICE_FINGERPRINT_BIND_ADDRESS": "127.0.0.2",
        "DEVICE_FINGERPRINT_PORT": "10443",
        "DEVICE_FINGERPRINT_TLS_CERT_PATH": "/absolute/server.crt",
        "DEVICE_FINGERPRINT_TLS_KEY_PATH": "/absolute/server.key",
        "DEVICE_FINGERPRINT_API_ALLOWED_NETWORKS": "127.0.0.0/8",
        "DEVICE_FINGERPRINT_PRODUCERS_JSON": "[]",
        "DEVICE_FINGERPRINT_RETENTION_DAYS": "31",
        "DEVICE_FINGERPRINT_MAX_FUTURE_SKEW_SECONDS": "121",
        "DEVICE_FINGERPRINT_MAX_DELAYED_EVENT_AGE_SECONDS": "86401",
        "DEVICE_FINGERPRINT_MAX_DB_BYTES": "1073741825",
        "DEVICE_FINGERPRINT_MAX_HTTP_REQUEST_BYTES": "1048577",
        "DEVICE_FINGERPRINT_MAX_EVENTS_PER_BATCH": "101",
        "DEVICE_FINGERPRINT_MAX_PAYLOAD_BYTES": "8193",
        "DEVICE_FINGERPRINT_MAX_CONCURRENT_INGEST_REQUESTS": "3",
    }
    import app.config as environment
    import app.settings as settings_module
    with monkeypatch.context() as environment_values:
        for key, value in expected.items():
            environment_values.setenv(key, value)
        importlib.reload(environment)
        importlib.reload(settings_module)
        mapped = settings_module.get_settings()
        for environment_key, expected_value in expected.items():
            settings_key = environment_key.lower()
            assert getattr(environment, environment_key) == expected_value
            assert mapped[settings_key] == expected_value
        assert "device_fingerprint_source_health_retention_days" not in mapped
    importlib.reload(environment)
    importlib.reload(settings_module)


@pytest.mark.parametrize("key", [
    "device_fingerprint_db_path",
    "device_fingerprint_writer_lock_path",
    "device_fingerprint_bind_address",
    "device_fingerprint_tls_cert_path",
    "device_fingerprint_tls_key_path",
    "device_fingerprint_api_allowed_networks",
    "device_fingerprint_producers_json",
])
def test_enabled_endpoint_tls_network_and_producer_values_are_required(tmp_path, key):
    settings = enabled_settings(tmp_path)
    settings[key] = ""
    with pytest.raises(DeviceFingerprintConfigError):
        device_fingerprint_config_from_settings(settings)


@pytest.mark.parametrize("mutation", [
    lambda item: item.update(producer_id="Upper"),
    lambda item: item.update(bearer_token="short"),
    lambda item: item.update(site_id="A" * 24),
    lambda item: item.update(allowed_guest_cidrs=["192.168.8.1/24"]),
    lambda item: item.update(allowed_source_kinds=["bad-kind"]),
])
def test_producer_contract_is_strict(tmp_path, mutation):
    settings = enabled_settings(tmp_path)
    item = json.loads(settings["device_fingerprint_producers_json"])[0]
    mutation(item)
    settings["device_fingerprint_producers_json"] = json.dumps([item])
    with pytest.raises(DeviceFingerprintConfigError):
        device_fingerprint_config_from_settings(settings)


def test_db_and_lock_and_tls_pairs_are_distinct_absolute(tmp_path):
    settings = enabled_settings(tmp_path)
    settings["device_fingerprint_writer_lock_path"] = settings["device_fingerprint_db_path"]
    with pytest.raises(DeviceFingerprintConfigError):
        device_fingerprint_config_from_settings(settings)
    settings = enabled_settings(tmp_path)
    settings["device_fingerprint_tls_key_path"] = settings["device_fingerprint_tls_cert_path"]
    with pytest.raises(DeviceFingerprintConfigError):
        device_fingerprint_config_from_settings(settings)
    settings = enabled_settings(tmp_path)
    settings["device_fingerprint_db_path"] = "relative.sqlite3"
    with pytest.raises(DeviceFingerprintConfigError):
        device_fingerprint_config_from_settings(settings)
