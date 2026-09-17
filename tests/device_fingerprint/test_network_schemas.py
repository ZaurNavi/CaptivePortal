import pytest

from app.device_fingerprint.models import DeviceFingerprintUnsupportedSchema, DeviceFingerprintValidationError
from app.device_fingerprint.network_schemas import (
    validate_dhcp_v1, validate_quic_v1, validate_tcp_syn_v1,
    validate_tcp_syn_v2, validate_tls_v1,
)
from app.device_fingerprint.schema_registry import build_production_schema_registry


def tls(**changes):
    value = {
        "ja4": "t13d0203h2_0123456789ab_abcdef012345",
        "ja4_a": "t13d0203h2", "ja4_b": "0123456789ab", "ja4_c": "abcdef012345",
        "tls_version_family": "tls1_3", "client_alpns": ["h2", "http/1.1"],
        "ech_extension_present": False, "grease_extension_present": True,
    }
    value.update(changes)
    return value


def quic(**changes):
    value = {
        "ja4": "q13d0203h3_0123456789ab_abcdef012345",
        "ja4_a": "q13d0203h3", "ja4_b": "0123456789ab", "ja4_c": "abcdef012345",
        "quic_version": "0x00000001", "ech_extension_present": None,
        "grease_extension_present": None,
    }
    value.update(changes)
    return value


def tcp_v2(**changes):
    value = {
        "ip_version": 4, "observed_ttl": 64,
        "ip_option_length_bytes": 0, "ip_id_zero": True,
        "ip_df": True, "ip_reserved_flag": False, "ip_ecn_bits": 0,
        "tcp_header_length_bytes": 24, "tcp_window": 65535,
        "tcp_sequence_zero": True, "tcp_ack_number_nonzero": False,
        "tcp_urg_pointer_nonzero": False, "tcp_fin": False,
        "tcp_rst": False, "tcp_push": False, "tcp_urg": False,
        "tcp_ns": False, "tcp_ece": False, "tcp_cwr": False,
        "tcp_payload_present": False,
        "tcp_option_records": [{
            "record_type": "eol", "kind": 0, "declared_length": None,
            "available_value_length": 0, "structure_state": "well_formed",
            "eol_padding_length": 3, "eol_padding_nonzero": False,
            "eol_padding_nonzero_before_final_byte": False,
        }],
    }
    value.update(changes)
    return value


def test_production_registry_contains_exact_task02_schemas():
    registry = build_production_schema_registry()
    assert registry.frozen
    assert registry.validate("tls_client", 1, tls())["ja4_a"].startswith("t")
    assert registry.validate("quic_client", 1, quic())["ja4_a"].startswith("q")
    assert registry.validate("tcp_syn", 2, tcp_v2()) == tcp_v2()


@pytest.mark.parametrize("alpns", [None, ["h2", "http/1.1"], ["h2", "h2"]])
def test_tls_alpns_valid_and_ordered(alpns):
    assert validate_tls_v1(tls(client_alpns=alpns))["client_alpns"] == alpns


@pytest.mark.parametrize("alpns", [["x"] * 17, ["x" * 256], [1], ["bad value"], ["\x7f"]])
def test_tls_alpns_malformed_fails(alpns):
    with pytest.raises(DeviceFingerprintValidationError):
        validate_tls_v1(tls(client_alpns=alpns))


def test_empty_alpn_is_normalizer_only_and_validator_rejects_it():
    with pytest.raises(DeviceFingerprintValidationError):
        validate_tls_v1(tls(client_alpns=[]))


@pytest.mark.parametrize("change", [
    {"ja4_a": "t12d0203h2"}, {"ja4_b": "1123456789ab"},
    {"ja4_c": "bbcdef012345"}, {"ja4_b": "ABCDEF012345"},
    {"ja4": "t13d0203h2*0123456789ab*abcdef012345"},
])
def test_ja4_redundant_fields_must_match(change):
    with pytest.raises(DeviceFingerprintValidationError):
        validate_tls_v1(tls(**change))


def test_family_is_strict():
    with pytest.raises(DeviceFingerprintValidationError):
        validate_quic_v1(quic(ja4="t13d0203h3_0123456789ab_abcdef012345", ja4_a="t13d0203h3"))


def test_quic_version_is_canonical():
    assert validate_quic_v1(quic())["quic_version"] == "0x00000001"
    for value in ("1", "0x1", "0xABCDEF01", 1):
        with pytest.raises(DeviceFingerprintValidationError):
            validate_quic_v1(quic(quic_version=value))


def test_dhcp_exact_payload_contract():
    payload = {
        "message_type": "discover", "parameter_request_list": [1, 3, 6],
        "option_order": [53, 55], "vendor_class": "android-dhcp-13",
        "client_identifier_kind": "mac", "maximum_message_size": 1500,
        "rapid_commit_requested": False, "capport_requested": True,
        "ipv6_only_preferred_requested": False, "hostname_present": True,
    }
    assert validate_dhcp_v1(payload) == payload
    with pytest.raises(DeviceFingerprintValidationError):
        validate_dhcp_v1({**payload, "hostname": "secret"})


def test_tcp_exact_payload_contract():
    payload = {
        "ip_version": 4, "observed_ttl": 64, "tcp_window": 65535,
        "mss": 1460, "window_scale": 8, "sack_permitted": True,
        "timestamps_present": True, "tcp_option_order": [2, 4, 8, 1, 3],
    }
    assert validate_tcp_syn_v1(payload) == payload
    with pytest.raises(DeviceFingerprintValidationError):
        validate_tcp_syn_v1({**payload, "window_scale": 15})


def test_tcp_v1_and_v2_coexist_without_latest_schema_selection():
    v1 = {
        "ip_version": 4, "observed_ttl": 64, "tcp_window": 65535,
        "mss": 1460, "window_scale": 8, "sack_permitted": True,
        "timestamps_present": True, "tcp_option_order": [2, 4, 8, 1, 3],
    }
    registry = build_production_schema_registry()
    assert registry.validate("tcp_syn", 1, v1) == v1
    assert registry.validate("tcp_syn", 2, tcp_v2()) == tcp_v2()
    with pytest.raises(DeviceFingerprintUnsupportedSchema):
        registry.validate("tcp_syn", 3, tcp_v2())
    with pytest.raises(DeviceFingerprintValidationError):
        registry.validate("tcp_syn", 1, tcp_v2())
    with pytest.raises(DeviceFingerprintValidationError):
        registry.validate("tcp_syn", 2, v1)


@pytest.mark.parametrize("change", [
    {"ip_version": True}, {"observed_ttl": 256},
    {"ip_option_length_bytes": 3}, {"ip_ecn_bits": 4},
    {"tcp_header_length_bytes": 22}, {"tcp_header_length_bytes": 64},
    {"tcp_window": -1}, {"tcp_fin": 1}, {"tcp_ns": 1},
    {"ip_id": 42}, {"raw_packet": "secret"},
])
def test_tcp_v2_top_level_contract_is_closed_and_bounded(change):
    with pytest.raises(DeviceFingerprintValidationError):
        validate_tcp_syn_v2(tcp_v2(**change))


@pytest.mark.parametrize("change", [
    {"record_type": "unknown"}, {"kind": 256},
    {"declared_length": 2}, {"available_value_length": 1},
    {"structure_state": "malformed_but_observable"},
    {"eol_padding_length": 2}, {"eol_padding_nonzero": 1},
    {"raw_options": "secret"}, {"timestamp_value": 1},
    {"eol_padding_bitmap": "010"}, {"p0f_opt_plus": True},
])
def test_tcp_v2_record_contract_rejects_impossible_or_private_fields(change):
    record = {**tcp_v2()["tcp_option_records"][0], **change}
    with pytest.raises(DeviceFingerprintValidationError):
        validate_tcp_syn_v2(tcp_v2(tcp_option_records=[record]))


@pytest.mark.parametrize("padding_length, padding_nonzero, before_final, accepted", [
    (0, False, False, True),
    (0, True, False, False),
    (0, False, True, False),
    (1, False, False, True),
    (1, True, False, True),
    (1, True, True, False),
    (3, False, False, True),
    (3, False, True, False),
    (3, True, False, True),
    (3, True, True, True),
])
def test_tcp_v2_eol_padding_consistency(padding_length, padding_nonzero, before_final, accepted):
    eol = {
        **tcp_v2()["tcp_option_records"][0],
        "eol_padding_length": padding_length,
        "eol_padding_nonzero": padding_nonzero,
        "eol_padding_nonzero_before_final_byte": before_final,
    }
    nop = {
        "record_type": "nop", "kind": 1, "declared_length": None,
        "available_value_length": 0, "structure_state": "well_formed",
    }
    records = [dict(nop) for _ in range(3 - padding_length)] + [eol]
    payload = tcp_v2(tcp_option_records=records)
    if accepted:
        assert validate_tcp_syn_v2(payload) == payload
    else:
        with pytest.raises(DeviceFingerprintValidationError):
            validate_tcp_syn_v2(payload)


def test_tcp_v2_eol_requires_new_structural_field():
    eol = dict(tcp_v2()["tcp_option_records"][0])
    del eol["eol_padding_nonzero_before_final_byte"]
    with pytest.raises(DeviceFingerprintValidationError):
        validate_tcp_syn_v2(tcp_v2(tcp_option_records=[eol]))


def test_tcp_v2_missing_keys_and_impossible_option_sequence_fail():
    missing_ns = tcp_v2()
    del missing_ns["tcp_ns"]
    with pytest.raises(DeviceFingerprintValidationError):
        validate_tcp_syn_v2(missing_ns)
    missing = tcp_v2()
    del missing["tcp_option_records"]
    with pytest.raises(DeviceFingerprintValidationError):
        validate_tcp_syn_v2(missing)
    with pytest.raises(DeviceFingerprintValidationError):
        validate_tcp_syn_v2(tcp_v2(tcp_option_records=[]))
    with pytest.raises(DeviceFingerprintValidationError):
        validate_tcp_syn_v2(tcp_v2(tcp_option_records=tcp_v2()["tcp_option_records"] * 2))


def test_tcp_v2_malformed_mss_validator_uses_physical_remaining_bytes():
    mss = {
        "record_type": "mss", "kind": 2, "declared_length": 1,
        "available_value_length": 0, "structure_state": "malformed_but_observable",
        "mss": 1200,
    }
    assert validate_tcp_syn_v2(tcp_v2(tcp_option_records=[mss]))["tcp_option_records"] == [mss]
    for invalid in (None, True, 65536):
        with pytest.raises(DeviceFingerprintValidationError):
            validate_tcp_syn_v2(tcp_v2(tcp_option_records=[{**mss, "mss": invalid}]))
    nop = {
        "record_type": "nop", "kind": 1, "declared_length": None,
        "available_value_length": 0, "structure_state": "well_formed",
    }
    for prefix in ([nop], [nop, nop]):
        missing = {**mss, "mss": None}
        assert validate_tcp_syn_v2(tcp_v2(tcp_option_records=[*prefix, missing]))
        with pytest.raises(DeviceFingerprintValidationError):
            validate_tcp_syn_v2(tcp_v2(tcp_option_records=[*prefix, mss]))


def test_tcp_v2_malformed_window_scale_validator_uses_physical_remaining_byte():
    ws = {
        "record_type": "window_scale", "kind": 3, "declared_length": 1,
        "available_value_length": 0, "structure_state": "malformed_but_observable",
        "window_scale_raw": 255,
    }
    assert validate_tcp_syn_v2(tcp_v2(tcp_option_records=[ws]))["tcp_option_records"] == [ws]
    with pytest.raises(DeviceFingerprintValidationError):
        validate_tcp_syn_v2(tcp_v2(tcp_option_records=[{**ws, "window_scale_raw": None}]))
    nop = {
        "record_type": "nop", "kind": 1, "declared_length": None,
        "available_value_length": 0, "structure_state": "well_formed",
    }
    missing = {**ws, "window_scale_raw": None}
    assert validate_tcp_syn_v2(tcp_v2(tcp_option_records=[nop, nop, missing]))
    with pytest.raises(DeviceFingerprintValidationError):
        validate_tcp_syn_v2(tcp_v2(tcp_option_records=[nop, nop, ws]))


@pytest.mark.parametrize("nop_count,header_length,zero,echo", [
    (3, 28, None, None),
    (2, 28, True, None),
    (2, 32, True, False),
])
def test_tcp_v2_malformed_timestamp_validator_uses_physical_remaining_bytes(
    nop_count, header_length, zero, echo,
):
    nop = {
        "record_type": "nop", "kind": 1, "declared_length": None,
        "available_value_length": 0, "structure_state": "well_formed",
    }
    timestamp = {
        "record_type": "timestamp", "kind": 8, "declared_length": 1,
        "available_value_length": 0, "structure_state": "malformed_but_observable",
        "timestamp_value_zero": zero, "timestamp_echo_nonzero": echo,
    }
    def payload(record):
        return tcp_v2(
            tcp_header_length_bytes=header_length,
            tcp_option_records=[*[nop] * nop_count, record],
        )
    assert validate_tcp_syn_v2(payload(timestamp))
    for name, value in (("timestamp_value_zero", zero), ("timestamp_echo_nonzero", echo)):
        wrong = False if value is None else None
        with pytest.raises(DeviceFingerprintValidationError):
            validate_tcp_syn_v2(payload({**timestamp, name: wrong}))


@pytest.mark.parametrize("kind,record_type,fields,invalid_field", [
    (2, "mss", {"mss": None}, {"mss": 1200}),
    (3, "window_scale", {"window_scale_raw": None}, {"window_scale_raw": 255}),
    (8, "timestamp", {"timestamp_value_zero": None, "timestamp_echo_nonzero": None},
     {"timestamp_value_zero": True}),
])
def test_tcp_v2_known_option_without_length_has_no_semantic_value(
    kind, record_type, fields, invalid_field,
):
    nop = {
        "record_type": "nop", "kind": 1, "declared_length": None,
        "available_value_length": 0, "structure_state": "well_formed",
    }
    record = {
        "record_type": record_type, "kind": kind, "declared_length": None,
        "available_value_length": 0, "structure_state": "malformed_but_observable",
        **fields,
    }
    records = [nop, nop, nop, record]
    assert validate_tcp_syn_v2(tcp_v2(tcp_option_records=records))
    with pytest.raises(DeviceFingerprintValidationError):
        validate_tcp_syn_v2(tcp_v2(tcp_option_records=[*records[:-1], {**record, **invalid_field}]))
