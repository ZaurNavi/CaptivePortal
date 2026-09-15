from __future__ import annotations

import json

import pytest

from research.device_fingerprint_03a.format import (
    CHECKSUM_FILES,
    MatrixFormatError,
    canonical_json_line,
    canonical_json_text,
    checksum_text,
    read_canonical_jsonl,
    validate_binding,
    validate_device,
    validate_device_state,
    validate_evidence,
    validate_manifest,
    validate_sample,
    validate_source_health,
    write_canonical_jsonl,
    write_checksums,
)

from . import (
    binding,
    device,
    device_state,
    manifest,
    sample,
    sealed_evidence,
    source_health,
    uid,
    write_matrix,
)


@pytest.mark.parametrize("kind", ["dhcp", "tcp_syn", "tls_client", "quic_client", "portal_headers"])
def test_exact_production_schema_payloads_are_accepted(kind):
    assert validate_evidence(sealed_evidence(kind=kind))["source_kind"] == kind


@pytest.mark.parametrize(
    ("validator", "row"),
    [
        (validate_device, device()),
        (validate_device_state, device_state()),
        (validate_sample, sample()),
        (validate_binding, binding()),
        (validate_source_health, source_health()),
        (validate_manifest, manifest()),
    ],
)
def test_canonical_rows_validate_without_mutation(validator, row):
    before = json.loads(json.dumps(row))
    assert validator(row) == before
    assert row == before


def test_records_fail_closed_on_extra_or_missing_fields():
    extra = device()
    extra["nickname"] = "private alias"
    missing = sample()
    del missing["network_epoch_id"]

    with pytest.raises(MatrixFormatError):
        validate_device(extra)
    with pytest.raises(MatrixFormatError):
        validate_sample(missing)


def test_ids_timestamps_and_sample_window_are_strict():
    upper_uuid = device()
    upper_uuid["lab_device_id"] = uid(0xABCDEF).upper()
    no_milliseconds = sample()
    no_milliseconds["window_start_utc"] = "2026-09-15T12:00:00Z"
    too_long = sample()
    too_long["window_end_utc"] = "2026-09-15T12:10:00.001Z"
    unsealed = sample()
    unsealed["sample_status"] = "collecting"

    for row, validator in (
        (upper_uuid, validate_device),
        (no_milliseconds, validate_sample),
        (too_long, validate_sample),
        (unsealed, validate_sample),
    ):
        with pytest.raises(MatrixFormatError):
            validator(row)


def test_evidence_payload_must_be_canonical_current_production_schema():
    wrong_hash = sealed_evidence()
    wrong_hash["payload_sha256"] = "0" * 64
    extra_payload_field = sealed_evidence()
    extra_payload_field["payload"]["raw_packet"] = "forbidden"
    wrong_capture = sealed_evidence()
    wrong_capture["capture_source_id"] = "zefer-portal-http-01"

    for row in (wrong_hash, extra_payload_field, wrong_capture):
        with pytest.raises(MatrixFormatError):
            validate_evidence(row)


def test_canonical_json_is_sorted_compact_ascii_and_lf(tmp_path):
    row = {"z": "caf\u00e9", "a": [2, 1]}
    assert canonical_json_text(row) == '{"a":[2,1],"z":"caf\\u00e9"}'
    assert canonical_json_line(row).endswith(b"\n")

    path = tmp_path / "values.jsonl"
    write_canonical_jsonl(path, [row])
    assert path.read_bytes() == b'{"a":[2,1],"z":"caf\\u00e9"}\n'
    assert read_canonical_jsonl(path) == [row]


@pytest.mark.parametrize(
    "raw",
    [
        b'{"a":1,"a":2}\n',
        b'{"a": 1}\n',
        b'{"a":1}\r\n',
        b'{"a":1}',
        b'{"a":NaN}\n',
    ],
)
def test_noncanonical_jsonl_fails_closed(tmp_path, raw):
    path = tmp_path / "values.jsonl"
    path.write_bytes(raw)
    with pytest.raises(MatrixFormatError):
        read_canonical_jsonl(path)


def test_checksum_manifest_is_exact_sorted_and_does_not_hash_itself(tmp_path):
    matrix = tmp_path / "matrix"
    write_matrix(matrix)
    expected_lines = checksum_text(matrix).splitlines()

    assert [line.split("  ", 1)[1] for line in expected_lines] == list(CHECKSUM_FILES)
    assert all(len(line.split("  ", 1)[0]) == 64 for line in expected_lines)
    assert "checksums.sha256" not in checksum_text(matrix)

    (matrix / "checksums.sha256").write_text("bad\n", encoding="ascii")
    with pytest.raises(MatrixFormatError):
        from research.device_fingerprint_03a.format import validate_checksums
        validate_checksums(matrix)
    write_checksums(matrix)


def test_ground_truth_rejects_person_identity_and_unverified_collection():
    private = device(model="192.168.8.10")
    unauthorized = device()
    unauthorized["collection_authorized"] = False

    with pytest.raises(MatrixFormatError):
        validate_device(private)
    with pytest.raises(MatrixFormatError):
        validate_device(unauthorized)


def test_ground_truth_labels_require_printable_ascii():
    unicode_row = device(manufacturer="Example \u00c9", model="Model \u03a9")
    ascii_row = device(manufacturer="Example Corp.", model="Model A-1")

    with pytest.raises(MatrixFormatError):
        validate_device(unicode_row)
    assert validate_device(ascii_row) == ascii_row


@pytest.mark.parametrize(
    ("validator", "row", "wrong_producer"),
    [
        (validate_evidence, sealed_evidence(kind="dhcp"), "portal-zefer-01"),
        (validate_evidence, sealed_evidence(kind="portal_headers"), "sensor-zefer-01"),
        (validate_source_health, source_health(kind="dhcp"), "portal-zefer-01"),
        (validate_source_health, source_health(kind="portal_headers"), "sensor-zefer-01"),
    ],
)
def test_source_producer_provenance_is_exact(validator, row, wrong_producer):
    row["producer_id"] = wrong_producer
    with pytest.raises(MatrixFormatError, match="producer"):
        validator(row)


def test_manifest_invalid_reason_counts_are_structured_and_reconciled():
    valid = manifest()
    valid["invalid_sample_count"] = 3
    valid["invalid_sample_reason_counts"] = {"binding_uncertain": 1, "operator_abort": 2}
    assert validate_manifest(valid)["invalid_sample_count"] == 3

    mismatch = dict(valid)
    mismatch["invalid_sample_count"] = 4
    unknown = dict(valid)
    unknown["invalid_sample_reason_counts"] = {"free_text": 3}
    for row in (mismatch, unknown):
        with pytest.raises(MatrixFormatError):
            validate_manifest(row)
