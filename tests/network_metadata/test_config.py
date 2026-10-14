import json
import pytest
from app.network_metadata.config import make_capture_scope_binding, network_metadata_config_from_env
from app.network_metadata.canonical import semantic_digest
from app.network_metadata.models import NetworkMetadataConfig, NetworkMetadataConfigError, NetworkMetadataValidationError
from . import binding_input, configuration


def test_disabled_zero_parsing():
    assert not network_metadata_config_from_env().enabled
    assert not network_metadata_config_from_env({"NETWORK_METADATA_ENABLED": "false", "NETWORK_METADATA_MAX_DB_BYTES": "not-a-number"}).enabled


def test_default_max_db_bytes(tmp_path):
    assert NetworkMetadataConfig().max_db_bytes == 8589934592
    assert configuration(tmp_path).max_db_bytes == 8589934592


@pytest.mark.parametrize("value", [8589934593, 51539607552, 68719476736])
def test_admitted_max_db_bytes(tmp_path, value):
    assert configuration(tmp_path, NETWORK_METADATA_MAX_DB_BYTES=str(value)).max_db_bytes == value


@pytest.mark.parametrize("value", ["TRUE", "False", "1", " true", "false ", "", [], True])
def test_strict_enabled(value):
    with pytest.raises(NetworkMetadataConfigError):
        network_metadata_config_from_env({"NETWORK_METADATA_ENABLED": value})


@pytest.mark.parametrize("key,value", [("MAX_DB_BYTES", "67108863"), ("MAX_DB_BYTES", "68719476737"),
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


@pytest.mark.parametrize("value", ["TRUE", "False", "1", "", " true", "false ", True, 1, None, []])
def test_io_hotpath_strict_flag_and_disabled_short_circuit(tmp_path, value):
    with pytest.raises(NetworkMetadataConfigError):
        configuration(tmp_path, NETWORK_METADATA_IO_HOTPATH_V1_ENABLED=value)
    disabled = network_metadata_config_from_env({
        "NETWORK_METADATA_ENABLED": "false", "NETWORK_METADATA_IO_HOTPATH_V1_ENABLED": value,
    })
    assert disabled == NetworkMetadataConfig()


@pytest.mark.parametrize("coalesce,aggregation", [(False, False), (True, False), (False, True), (True, True)])
def test_io_hotpath_default_off_preserves_frozen_digest(tmp_path, coalesce, aggregation):
    from dataclasses import asdict, FrozenInstanceError
    from app.network_metadata.models import LOGICAL_SOURCE_ID, NORMALIZER_VERSION, SOURCE_CONTRACT_VERSION
    variables = {}
    if coalesce:
        variables.update(NETWORK_METADATA_INGEST_COALESCE_ENABLED="true", NETWORK_METADATA_INGEST_COALESCE_MAX_MS="100")
    if aggregation:
        variables["NETWORK_METADATA_TELEMETRY_AGGREGATION_ENABLED"] = "true"
    default = configuration(tmp_path, **variables)
    off = configuration(tmp_path, **variables, NETWORK_METADATA_IO_HOTPATH_V1_ENABLED="false")
    on = configuration(tmp_path, **variables, NETWORK_METADATA_IO_HOTPATH_V1_ENABLED="true")
    binding = asdict(default.capture_scope_binding)
    binding["ipv4_cidrs"] = list(default.capture_scope_binding.ipv4_cidrs)
    legacy = dict(capture_scope_binding=binding, db_path=default.db_path,
        logical_source_id=LOGICAL_SOURCE_ID, max_db_bytes=default.max_db_bytes,
        max_record_bytes=default.max_record_bytes, batch_max_records=default.batch_max_records,
        batch_max_bytes=default.batch_max_bytes, normalizer_version=NORMALIZER_VERSION,
        poll_interval_seconds=default.poll_interval_seconds, source_contract_version=SOURCE_CONTRACT_VERSION,
        source_path=default.source_path)
    if coalesce:
        legacy.update(ingest_coalesce_enabled=True, ingest_coalesce_max_ms=100)
    if aggregation:
        legacy["telemetry_aggregation_enabled"] = True
    assert default == off
    assert default.io_hotpath_v1_enabled is off.io_hotpath_v1_enabled is False
    assert default.configuration_digest == semantic_digest(legacy)
    assert on.io_hotpath_v1_enabled is True
    assert on.configuration_digest == semantic_digest({**legacy, "io_hotpath_v1_enabled": True})
    assert on.configuration_digest != off.configuration_digest
    with pytest.raises(FrozenInstanceError):
        on.io_hotpath_v1_enabled = False


@pytest.mark.parametrize("value", ["TRUE", "False", "1", "", " true", "false ", True, 1, None, []])
def test_b_retention_strict_flag_disabled_ignores_it(tmp_path, value):
    with pytest.raises(NetworkMetadataConfigError):
        configuration(tmp_path, NETWORK_METADATA_RETENTION_INDEXED_V1_ENABLED=value)
    assert network_metadata_config_from_env({"NETWORK_METADATA_ENABLED": "false",
        "NETWORK_METADATA_RETENTION_INDEXED_V1_ENABLED": value}) == NetworkMetadataConfig()


@pytest.mark.parametrize("a,b", [(False, False), (True, False), (False, True), (True, True)])
def test_b_independent_flags_frozen_digest(tmp_path, a, b):
    from dataclasses import asdict, FrozenInstanceError
    from app.network_metadata.models import LOGICAL_SOURCE_ID, NORMALIZER_VERSION, SOURCE_CONTRACT_VERSION
    variables = {"NETWORK_METADATA_IO_HOTPATH_V1_ENABLED": str(a).lower()}
    default = configuration(tmp_path, **variables)
    off = configuration(tmp_path, **variables, NETWORK_METADATA_RETENTION_INDEXED_V1_ENABLED="false")
    candidate = configuration(tmp_path, **variables,
        NETWORK_METADATA_RETENTION_INDEXED_V1_ENABLED=str(b).lower())
    binding = asdict(candidate.capture_scope_binding)
    binding["ipv4_cidrs"] = list(candidate.capture_scope_binding.ipv4_cidrs)
    frozen = dict(capture_scope_binding=binding, db_path=candidate.db_path,
        logical_source_id=LOGICAL_SOURCE_ID, max_db_bytes=candidate.max_db_bytes,
        max_record_bytes=candidate.max_record_bytes, batch_max_records=candidate.batch_max_records,
        batch_max_bytes=candidate.batch_max_bytes, normalizer_version=NORMALIZER_VERSION,
        poll_interval_seconds=candidate.poll_interval_seconds, source_contract_version=SOURCE_CONTRACT_VERSION,
        source_path=candidate.source_path)
    if a:
        frozen["io_hotpath_v1_enabled"] = True
    assert default == off
    assert off.configuration_digest == semantic_digest(frozen)
    if b:
        frozen["retention_indexed_v1_enabled"] = True
        assert candidate.configuration_digest != off.configuration_digest
    assert candidate.configuration_digest == semantic_digest(frozen)
    assert candidate.io_hotpath_v1_enabled is a
    assert candidate.retention_indexed_v1_enabled is b
    with pytest.raises(FrozenInstanceError):
        candidate.retention_indexed_v1_enabled = not b
