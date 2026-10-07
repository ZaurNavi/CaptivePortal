import json
import pytest
from app.network_metadata.config import make_capture_scope_binding, network_metadata_config_from_env
from app.network_metadata.canonical import semantic_digest
from app.network_metadata.models import NetworkMetadataConfigError, NetworkMetadataValidationError
from . import binding_input, configuration


def test_disabled_zero_parsing():
    assert not network_metadata_config_from_env().enabled
    assert not network_metadata_config_from_env({"NETWORK_METADATA_ENABLED": "false", "NETWORK_METADATA_MAX_DB_BYTES": "not-a-number"}).enabled


@pytest.mark.parametrize("value", ["TRUE", "False", "1", " true", "false ", "", [], True])
def test_strict_enabled(value):
    with pytest.raises(NetworkMetadataConfigError):
        network_metadata_config_from_env({"NETWORK_METADATA_ENABLED": value})


@pytest.mark.parametrize("key,value", [("MAX_DB_BYTES", "67108863"), ("MAX_DB_BYTES", "8589934593"),
    ("MAX_RECORD_BYTES", "4095"), ("MAX_RECORD_BYTES", "1048577"), ("BATCH_MAX_RECORDS", "257"),
    ("BATCH_MAX_BYTES", "4096"), ("POLL_INTERVAL_SECONDS", "0"), ("POLL_INTERVAL_SECONDS", "1.0"),
    ("BATCH_MAX_RECORDS", " 1"), ("BATCH_MAX_RECORDS", "+1"), ("BATCH_MAX_RECORDS", "١")])
def test_limits(tmp_path, key, value):
    with pytest.raises(NetworkMetadataConfigError):
        configuration(tmp_path, **{"NETWORK_METADATA_" + key: value})


@pytest.mark.parametrize("value", ["relative", "", "/tmp/\0name"])
def test_absolute_path(tmp_path, value):
    with pytest.raises(NetworkMetadataConfigError):
        configuration(tmp_path, NETWORK_METADATA_SOURCE_PATH=value)


def test_paths_cannot_alias(tmp_path):
    for suffix in ("", ".writer.lock"):
        with pytest.raises(NetworkMetadataConfigError):
            configuration(tmp_path, NETWORK_METADATA_SOURCE_PATH=str(tmp_path / "metadata.sqlite3") + suffix)


def test_binding_digest_order_and_full_configuration(tmp_path):
    value = binding_input()
    value["ipv4_cidrs"] = ["10.74.0.0/24", "10.73.0.0/24"]
    first = make_capture_scope_binding(value)
    value["ipv4_cidrs"].reverse()
    second = make_capture_scope_binding(value)
    assert first == second
    canonical = {**value, "ipv4_cidrs": list(first.ipv4_cidrs)}
    assert first.binding_digest == semantic_digest(canonical)
    cfg = configuration(tmp_path)
    assert cfg.configuration_digest == configuration(tmp_path).configuration_digest
    assert cfg.configuration_digest != configuration(tmp_path, NETWORK_METADATA_POLL_INTERVAL_SECONDS="2").configuration_digest


@pytest.mark.parametrize("field,value", [("site_id", "bad"), ("capture_source_id", "BAD"), ("network_scope_id", "a b"),
    ("ipv4_cidrs", ["10.73.0.1/24"]), ("ipv4_cidrs", ["10.73.0.0/24"] * 2),
    ("ipv4_cidrs", ["10.73.0.0/24", "10.73.0.0/25"]), ("ipv4_cidrs", ["::/64"]),
    ("ipv4_cidrs", [f"10.{index}.0.0/24" for index in range(17)]), ("schema_version", True)])
def test_binding_validation(field, value):
    candidate = binding_input()
    candidate[field] = value
    with pytest.raises(NetworkMetadataValidationError):
        make_capture_scope_binding(candidate)


def test_closed_binding(tmp_path):
    value = binding_input()
    for candidate in ({**value, "extra": 1}, {key: value[key] for key in value if key != "site_id"}):
        with pytest.raises(NetworkMetadataValidationError):
            make_capture_scope_binding(candidate)
    with pytest.raises(NetworkMetadataConfigError):
        configuration(tmp_path, NETWORK_METADATA_CAPTURE_SCOPE_BINDING_JSON='{"x":1,"x":2}')
