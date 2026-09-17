import ipaddress
import json
import struct

import pytest

from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.network_schemas import validate_tcp_syn_v2
from app.device_fingerprint.repository import DeviceFingerprintRepository
from app.device_fingerprint.schema_registry import build_production_schema_registry
from app.device_fingerprint.service import DeviceFingerprintService
from app.device_fingerprint.validation import canonical_json, canonical_sha256, format_utc
from app.device_fingerprint_sensor.config import sensor_config_from_env
from app.device_fingerprint_sensor.normalizer import NetworkNormalizer
from app.device_fingerprint_sensor.tcp_syn import parse_tcp_syn_frame
from tests.device_fingerprint import NOW, config as task01_config, producer

GUEST = (ipaddress.ip_network("192.168.8.0/22"),)
DEFAULT_OPTIONS = b"\x02\x04\x05\xb4\x04\x02\x08\x0a" + b"\0" * 8
V2_KEYS = {
    "ip_version", "observed_ttl", "ip_option_length_bytes", "ip_id_zero",
    "ip_df", "ip_reserved_flag", "ip_ecn_bits", "tcp_header_length_bytes",
    "tcp_window", "tcp_sequence_zero", "tcp_ack_number_nonzero",
    "tcp_urg_pointer_nonzero", "tcp_fin", "tcp_rst", "tcp_push", "tcp_urg",
    "tcp_ns", "tcp_ece", "tcp_cwr", "tcp_payload_present", "tcp_option_records",
}


def syn(*, source="192.168.8.20", flags=0x02, ns=False, options=DEFAULT_OPTIONS,
        ip_options=b"", ip_id=0, fragment=0, ecn=0, sequence=0,
        ack_number=0, urgent_pointer=0, payload=b"", window=65535):
    assert len(ip_options) % 4 == 0
    while len(options) % 4:
        options += b"\x01"
    tcp = bytearray(20 + len(options))
    struct.pack_into("!HH", tcp, 0, 12345, 443)
    struct.pack_into("!II", tcp, 4, sequence, ack_number)
    tcp[12] = (((20 + len(options)) // 4) << 4) | int(ns)
    tcp[13] = flags
    struct.pack_into("!H", tcp, 14, window)
    struct.pack_into("!H", tcp, 18, urgent_pointer)
    tcp[20:] = options
    ip = bytearray(20 + len(ip_options))
    ip[0] = (4 << 4) | ((20 + len(ip_options)) // 4)
    ip[1] = ecn
    ip[8] = 64
    ip[9] = 6
    struct.pack_into("!H", ip, 2, len(ip) + len(tcp) + len(payload))
    struct.pack_into("!H", ip, 4, ip_id)
    struct.pack_into("!H", ip, 6, fragment)
    ip[12:16] = ipaddress.ip_address(source).packed
    ip[16:20] = ipaddress.ip_address("1.1.1.1").packed
    ip[20:] = ip_options
    return bytes.fromhex("aabbccddeeff0011223344550800") + bytes(ip) + bytes(tcp) + payload


def parsed(options=DEFAULT_OPTIONS, **kwargs):
    result = parse_tcp_syn_frame(syn(options=options, **kwargs), GUEST)
    assert result is not None
    assert validate_tcp_syn_v2(result[2]) == result[2]
    return result[2]


def normalizer():
    return NetworkNormalizer(
        sensor_config_from_env({"DEVICE_FINGERPRINT_SENSOR_ENABLED": "true"}),
        monotonic=lambda: 0,
    )


def test_ipv4_guest_syn_v2_exact_protocol_facts_and_minimization():
    mac, ip, value = parse_tcp_syn_frame(syn(), GUEST)
    assert (mac, ip) == ("00:11:22:33:44:55", "192.168.8.20")
    assert set(value) == V2_KEYS
    assert value["ip_version"] == 4
    assert value["observed_ttl"] == 64
    assert value["tcp_header_length_bytes"] == 36
    assert value["tcp_window"] == 65535
    assert value["tcp_payload_present"] is False
    assert [record["record_type"] for record in value["tcp_option_records"]] == [
        "mss", "sack_permitted", "timestamp",
    ]
    assert value["tcp_option_records"][0]["mss"] == 1460
    assert validate_tcp_syn_v2(value) == value
    assert set(value).isdisjoint({
        "ip_id", "tcp_sequence", "ack_number", "urgent_pointer", "mss",
        "window_scale", "sack_permitted", "timestamps_present",
        "tcp_option_order", "raw_packet", "raw_options", "os_guess",
    })


def test_empty_options_and_full_forty_nop_option_area_remain_bounded():
    assert parsed(b"")["tcp_option_records"] == []
    records = parsed(b"\x01" * 40)["tcp_option_records"]
    assert len(records) == 40
    assert all(record["record_type"] == "nop" for record in records)


@pytest.mark.parametrize("ip_id,fragment,ecn,sequence,ack,urgent,flags,payload", [
    (0, 0, 0, 0, 0, 0, 0x02, b""),
    (23, 0xC000, 3, 7, 9, 11, 0xEF, b"x"),
])
def test_ip_tcp_boolean_derivatives_and_ipv4_options(
    ip_id, fragment, ecn, sequence, ack, urgent, flags, payload,
):
    value = parsed(
        ip_options=b"\x01\x01\x01\x01", ip_id=ip_id,
        fragment=fragment, ecn=ecn, sequence=sequence,
        ack_number=ack, urgent_pointer=urgent, flags=flags,
        payload=payload,
    )
    assert value["ip_option_length_bytes"] == 4
    assert value["ip_id_zero"] is (ip_id == 0)
    assert value["ip_df"] is bool(fragment & 0x4000)
    assert value["ip_reserved_flag"] is bool(fragment & 0x8000)
    assert value["ip_ecn_bits"] == ecn
    assert value["tcp_sequence_zero"] is (sequence == 0)
    assert value["tcp_ack_number_nonzero"] is (ack != 0)
    assert value["tcp_urg_pointer_nonzero"] is (urgent != 0)
    assert value["tcp_ns"] is False
    assert value["tcp_payload_present"] is bool(payload)
    for name, bit in (
        ("tcp_fin", 0x01), ("tcp_rst", 0x04), ("tcp_push", 0x08),
        ("tcp_urg", 0x20), ("tcp_ece", 0x40), ("tcp_cwr", 0x80),
    ):
        assert value[name] is bool(flags & bit)


def test_tcp_ns_changes_only_one_canonical_payload_fact():
    assert syn(options=b"", ns=False)[14 + 20 + 12] == 0x50
    assert syn(options=b"", ns=True)[14 + 20 + 12] == 0x51
    absent = parsed(b"", ns=False)
    present = parsed(b"", ns=True)
    assert absent["tcp_header_length_bytes"] == present["tcp_header_length_bytes"] == 20
    assert absent["tcp_ns"] is False
    assert present["tcp_ns"] is True
    assert {**absent, "tcp_ns": True} == present
    assert canonical_json(absent) != canonical_json(present)
    assert canonical_sha256(canonical_json(absent)) != canonical_sha256(canonical_json(present))


@pytest.mark.parametrize("ns,flags,expected", [
    (True, 0x02, (True, False, False)),
    (False, 0x42, (False, True, False)),
    (False, 0x82, (False, False, True)),
])
def test_tcp_ns_ece_cwr_are_independent(ns, flags, expected):
    value = parsed(b"", ns=ns, flags=flags)
    assert (value["tcp_ns"], value["tcp_ece"], value["tcp_cwr"]) == expected
    assert value["ip_ecn_bits"] == 0


@pytest.mark.parametrize("options,expected_type,extra", [
    (b"\x00\0\0\0", "eol", {
        "eol_padding_length": 3, "eol_padding_nonzero": False,
        "eol_padding_nonzero_before_final_byte": False,
    }),
    (b"\x00\0\x01\0", "eol", {
        "eol_padding_length": 3, "eol_padding_nonzero": True,
        "eol_padding_nonzero_before_final_byte": True,
    }),
    (b"\x01\x01\x01\x01", "nop", {}),
    (b"\x02\x04\x05\xb4", "mss", {"mss": 1460}),
    (b"\x03\x03\xff\x01", "window_scale", {"window_scale_raw": 255}),
    (b"\x04\x02\x01\x01", "sack_permitted", {}),
    (b"\x08\x0a" + b"\0" * 8, "timestamp", {
        "timestamp_value_zero": True, "timestamp_echo_nonzero": False,
    }),
    (b"\x08\x0a\0\0\0\x01\0\0\0\x02", "timestamp", {
        "timestamp_value_zero": False, "timestamp_echo_nonzero": True,
    }),
    (b"\x1e\x04\xaa\xbb", "unknown", {"available_value_length": 2}),
])
def test_well_formed_option_variants(options, expected_type, extra):
    records = parsed(options)["tcp_option_records"]
    assert records[0]["record_type"] == expected_type
    assert records[0]["structure_state"] == "well_formed"
    assert all(records[0][name] == expected for name, expected in extra.items())
    if expected_type == "nop":
        assert len(records) == 4
    if expected_type == "window_scale":
        assert records[0]["window_scale_raw"] > 14


@pytest.mark.parametrize("eol_layout,length,nonzero,before_final", [
    (b"\x00", 0, False, False),
    (b"\x00\x00", 1, False, False),
    (b"\x00\x01", 1, True, False),
    (b"\x00\x01\x00\x00", 3, True, True),
    (b"\x00\x00\x00\x01", 3, True, False),
    (b"\x00\x00\x01\x00", 3, True, True),
    (b"\x00\x00\x00\x00", 3, False, False),
])
def test_eol_padding_structural_fact(eol_layout, length, nonzero, before_final):
    options = b"\x01" * (4 - len(eol_layout)) + eol_layout
    records = parsed(options)["tcp_option_records"]
    eol = records[-1]
    assert eol == {
        "record_type": "eol", "kind": 0, "declared_length": None,
        "available_value_length": 0, "structure_state": "well_formed",
        "eol_padding_length": length,
        "eol_padding_nonzero": nonzero,
        "eol_padding_nonzero_before_final_byte": before_final,
    }


def test_oracle_eol_layouts_have_distinct_canonical_tcp_v2_payloads():
    early_nonzero = parsed(b"\x00\x01\x00\x00")
    final_nonzero = parsed(b"\x00\x00\x00\x01")
    assert early_nonzero["tcp_option_records"][0]["eol_padding_nonzero"] is True
    assert final_nonzero["tcp_option_records"][0]["eol_padding_nonzero"] is True
    assert early_nonzero["tcp_option_records"][0]["eol_padding_nonzero_before_final_byte"] is True
    assert final_nonzero["tcp_option_records"][0]["eol_padding_nonzero_before_final_byte"] is False
    assert canonical_json(early_nonzero) != canonical_json(final_nonzero)
    assert canonical_sha256(canonical_json(early_nonzero)) != canonical_sha256(canonical_json(final_nonzero))


@pytest.mark.parametrize("options,expected_type,available,extra", [
    (b"\x02\x03\x01\x01", "mss", 1, {"mss": 257}),
    (b"\x01\x01\x02\x04", "mss", 0, {"mss": None}),
    (b"\x01\x01\x01\x02", "mss", 0, {"declared_length": None}),
    (b"\x03\x02\x01\x01", "window_scale", 0, {"window_scale_raw": 1}),
    (b"\x04\x03\0\x01", "sack_permitted", 1, {}),
    (b"\x08\x09" + b"\0" * 6, "timestamp", 6, {
        "timestamp_value_zero": True, "timestamp_echo_nonzero": None,
    }),
    (b"\x08\x0a" + b"\0" * 6, "timestamp", 6, {
        "timestamp_value_zero": True, "timestamp_echo_nonzero": None,
    }),
    (b"\x1e\x01\x01\x01", "unknown", 0, {}),
    (b"\x1e\x0a\x01\x01", "unknown", 2, {}),
    (b"\x01\x01\x01\x1e", "unknown", 0, {"declared_length": None}),
])
def test_malformed_option_is_retained_as_partial(options, expected_type, available, extra):
    records = parsed(options)["tcp_option_records"]
    record = next(record for record in records if record["record_type"] == expected_type)
    assert record["structure_state"] == "malformed_but_observable"
    assert record["available_value_length"] == available
    assert all(record[name] == expected for name, expected in extra.items())
    events = normalizer().raw(syn(options=options), format_utc(NOW))
    assert len(events) == 1
    assert events[0].document["quality_state"] == "partial"
    assert events[0].document["feature_schema_version"] == 2


@pytest.mark.parametrize("options,declared,available,state,mss,layout", [
    (b"\x01\x01\x02\x01", 1, 0, "malformed_but_observable", None, ["nop", "nop", "mss"]),
    (b"\x01\x02\x01\x04", 1, 0, "malformed_but_observable", None, ["nop", "mss"]),
    (b"\x02\x00\x04\xb0", 0, 0, "malformed_but_observable", 1200, ["mss"]),
    (b"\x02\x01\x04\xb0", 1, 0, "malformed_but_observable", 1200, ["mss"]),
    (b"\x02\x01\x05\xb4", 1, 0, "malformed_but_observable", 1460, ["mss"]),
    (b"\x02\x02\x04\xb0", 2, 0, "malformed_but_observable", 1200, ["mss", "sack_permitted"]),
    (b"\x02\x03\x04\xb0", 3, 1, "malformed_but_observable", 1200, ["mss", "unknown"]),
    (b"\x02\x04\x04\xb0", 4, 2, "well_formed", 1200, ["mss"]),
    (b"\x02\x05\x04\xb0", 5, 2, "malformed_but_observable", 1200, ["mss"]),
])
def test_mss_physical_value_is_independent_of_declared_extent(
    options, declared, available, state, mss, layout,
):
    records = parsed(options)["tcp_option_records"]
    record = next(record for record in records if record["record_type"] == "mss")
    assert (record["declared_length"], record["available_value_length"]) == (declared, available)
    assert (record["structure_state"], record["mss"]) == (state, mss)
    assert [record["record_type"] for record in records] == layout


def test_malformed_mss_oracle_pair_has_distinct_canonical_payloads():
    first = parsed(b"\x02\x01\x04\xb0")
    second = parsed(b"\x02\x01\x05\xb4")
    assert first["tcp_option_records"][0]["mss"] == 1200
    assert second["tcp_option_records"][0]["mss"] == 1460
    assert {**first["tcp_option_records"][0], "mss": 1460} == second["tcp_option_records"][0]
    assert canonical_json(first) != canonical_json(second)
    assert canonical_sha256(canonical_json(first)) != canonical_sha256(canonical_json(second))


@pytest.mark.parametrize("options,expected", [
    (b"\x01\x01\x03\x01", None),
    (b"\x01\x03\x01\xff", 255),
    (b"\x03\x01\xff\x01", 255),
])
def test_malformed_window_scale_uses_physical_byte_without_changing_traversal(options, expected):
    records = parsed(options)["tcp_option_records"]
    record = next(record for record in records if record["record_type"] == "window_scale")
    assert record["declared_length"] == 1
    assert record["available_value_length"] == 0
    assert record["structure_state"] == "malformed_but_observable"
    assert record["window_scale_raw"] == expected


@pytest.mark.parametrize("prefix,value_bytes,expected_zero,expected_echo", [
    (b"\x01" * 3, b"\0" * 3, None, None),
    (b"\x01" * 2, b"\0" * 4, True, None),
    (b"\x01" * 3, b"\0" * 7, True, None),
    (b"\x01" * 2, b"\0" * 8, True, False),
    (b"", b"\0\0\0\x01\0\0\0\x02\x01\x01", False, True),
])
def test_malformed_timestamp_uses_only_bounded_physical_boolean_facts(
    prefix, value_bytes, expected_zero, expected_echo,
):
    options = prefix + b"\x08\x01" + value_bytes
    assert len(options) % 4 == 0
    records = parsed(options)["tcp_option_records"]
    record = next(record for record in records if record["record_type"] == "timestamp")
    assert record["declared_length"] == 1
    assert record["available_value_length"] == 0
    assert record["structure_state"] == "malformed_but_observable"
    assert record["timestamp_value_zero"] is expected_zero
    assert record["timestamp_echo_nonzero"] is expected_echo
    assert set(record) == {
        "record_type", "kind", "declared_length", "available_value_length",
        "structure_state", "timestamp_value_zero", "timestamp_echo_nonzero",
    }


def test_ordered_mixed_options_and_known_mismatch_continue_at_safe_boundary():
    value = parsed(b"\x01\x02\x05\x05\xb4\x00\x03\x03\x0f\x04\x02\x00")
    assert [record["record_type"] for record in value["tcp_option_records"]] == [
        "nop", "mss", "window_scale", "sack_permitted", "eol",
    ]
    assert value["tcp_option_records"][1]["structure_state"] == "malformed_but_observable"
    assert value["tcp_option_records"][1]["mss"] == 1460
    assert value["tcp_option_records"][2]["window_scale_raw"] == 15
    assert value["tcp_option_records"][-1]["eol_padding_length"] == 0


def test_non_guest_ack_fragment_and_header_truncation_emit_nothing():
    assert parse_tcp_syn_frame(syn(flags=0x12), GUEST) is None
    assert parse_tcp_syn_frame(syn(source="192.168.0.20"), GUEST) is None
    assert parse_tcp_syn_frame(syn(fragment=0x2000), GUEST) is None
    assert parse_tcp_syn_frame(syn(fragment=0x0001), GUEST) is None
    complete = syn()
    assert parse_tcp_syn_frame(complete[:30], GUEST) is None
    assert parse_tcp_syn_frame(complete[:-1], GUEST) is None
    assert parse_tcp_syn_frame(syn(ip_options=b"\x01\x01\x01\x01")[:-1], GUEST) is None
    assert parse_tcp_syn_frame(syn(options=b"\x01\x01\x01\x01")[:-1], GUEST) is None


def test_tcp_v2_sensor_to_task01_production_registry_and_persisted_canonical_row(tmp_path):
    cfg = task01_config(tmp_path)
    repository = DeviceFingerprintRepository(cfg.db_path, max_db_bytes=cfg.max_db_bytes)
    repository.initialize()
    registry = build_production_schema_registry()
    svc = DeviceFingerprintService(cfg, repository, registry, now=lambda: NOW)
    events = normalizer().raw(syn(options=b"\x03\x03\xff\x01"), format_utc(NOW))
    assert len(events) == 1
    document = events[0].document
    assert document["source_kind"] == "tcp_syn"
    assert document["source_subtype"] == "ipv4"
    assert document["feature_schema_version"] == 2
    assert document["extractor_name"] == "packet-tcp-syn"
    assert document["extractor_version"] == "2.0.0"
    assert document["quality_state"] == "valid"
    assert registry.validate("tcp_syn", 2, document["payload"]) == document["payload"]
    assert svc.evidence_batch(producer(), {
        "producer_id": producer().producer_id, "events": [document],
    }).inserted == 1
    row = repository.connection.execute(
        "SELECT source_kind,feature_schema_version,payload_json,payload_sha256 "
        "FROM device_fingerprint_evidence"
    ).fetchone()
    assert (row["source_kind"], row["feature_schema_version"]) == ("tcp_syn", 2)
    assert row["payload_json"] == canonical_json(document["payload"])
    assert row["payload_sha256"] == canonical_sha256(row["payload_json"])
    assert json.loads(row["payload_json"]) == document["payload"]
    assert all(token not in row["payload_json"] for token in (
        '"ip_id":', '"tcp_sequence":', '"ack_number":',
        '"tsval":', '"tsecr":', '"raw_options":', '"raw_packet":',
    ))


def test_v2_validator_rejects_raw_or_numeric_sensitive_fields():
    payload = parsed()
    for key, value in (
        ("ip_id", 42), ("tcp_sequence", 3), ("raw_packet", "x"),
        ("tcp_option_order", [2]), ("tsval", 123), ("os_guess", "x"),
    ):
        with pytest.raises(DeviceFingerprintValidationError):
            validate_tcp_syn_v2({**payload, key: value})
    timestamp = parsed(b"\x08\x0a" + b"\0" * 8)
    record = {**timestamp["tcp_option_records"][0], "timestamp_value": 123}
    with pytest.raises(DeviceFingerprintValidationError):
        validate_tcp_syn_v2({**timestamp, "tcp_option_records": [record, *timestamp["tcp_option_records"][1:]]})
