from __future__ import annotations

import shutil

import pytest

from research.device_fingerprint_03a.format import (
    MatrixFormatError,
    read_canonical_json,
    read_canonical_jsonl,
    write_canonical_json,
    write_canonical_jsonl,
    write_checksums,
)
from research.device_fingerprint_03a.validator import source_summary, validate_matrix

from . import (
    device,
    device_state,
    manifest,
    sample,
    sealed_evidence,
    source_health,
    write_matrix,
)


def test_calibration_matrix_validates_and_summary_has_every_source_cell(tmp_path):
    matrix = tmp_path / "matrix"
    write_matrix(matrix)

    report = validate_matrix(matrix, require_v1_coverage=False)

    assert report["status"] == "pass"
    assert len(report["sample_source_summary"]) == 5
    assert {row["source_kind"] for row in report["sample_source_summary"]} == {
        "dhcp", "tcp_syn", "tls_client", "quic_client", "portal_headers",
    }
    assert sum(row["evidence_count"] for row in report["sample_source_summary"]) == 1
    assert report["coverage"]["v1_coverage_pass"] is False


def test_sample_window_is_half_open_for_evidence(tmp_path):
    matrix = tmp_path / "matrix"
    end = sealed_evidence(observed_at="2026-09-15T12:05:00.000Z")
    write_matrix(matrix, evidence=[end])

    with pytest.raises(MatrixFormatError, match="outside its sample window"):
        validate_matrix(matrix, require_v1_coverage=False)


def test_manifest_counts_are_exact(tmp_path):
    matrix = tmp_path / "matrix"
    wrong = manifest(evidence=2)
    write_matrix(matrix, manifest_row=wrong)

    with pytest.raises(MatrixFormatError, match="counts"):
        validate_matrix(matrix, require_v1_coverage=False)


def test_checksum_tamper_order_and_extra_files_fail_closed(tmp_path):
    matrix = tmp_path / "matrix"
    write_matrix(matrix)
    original = (matrix / "checksums.sha256").read_text(encoding="ascii")

    (matrix / "checksums.sha256").write_text("\n".join(reversed(original.splitlines())) + "\n", encoding="ascii")
    with pytest.raises(MatrixFormatError):
        validate_matrix(matrix, require_v1_coverage=False)

    write_checksums(matrix)
    (matrix / "notes.txt").write_text("not sealed data\n", encoding="utf-8")
    with pytest.raises(MatrixFormatError, match="file set"):
        validate_matrix(matrix, require_v1_coverage=False)


def test_duplicate_evidence_assignment_fails_closed(tmp_path):
    matrix = tmp_path / "matrix"
    second = sample(202)
    duplicate = sealed_evidence(sample_id=202)
    write_matrix(
        matrix,
        samples=[sample(), second],
        evidence=[sealed_evidence(), duplicate],
        manifest_row=manifest(samples=2, evidence=2),
    )

    rows = read_canonical_jsonl(matrix / "evidence.jsonl")
    rows[1]["evidence_id"] = rows[0]["evidence_id"]
    write_canonical_jsonl(matrix / "evidence.jsonl", rows)
    write_checksums(matrix)
    with pytest.raises(MatrixFormatError, match="assigned more than once"):
        validate_matrix(matrix, require_v1_coverage=False)


def test_evidence_order_is_canonical_and_stable(tmp_path):
    matrix = tmp_path / "matrix"
    later = sealed_evidence(identity=502, observed_at="2026-09-15T12:02:00.000Z")
    earlier = sealed_evidence(identity=501, observed_at="2026-09-15T12:01:00.000Z")
    write_matrix(matrix, evidence=[later, earlier], manifest_row=manifest(evidence=2))

    with pytest.raises(MatrixFormatError, match="ordering"):
        validate_matrix(matrix, require_v1_coverage=False)


def test_source_health_roles_obey_sample_boundaries(tmp_path):
    matrix = tmp_path / "matrix"
    invalid = source_health(observed_at="2026-09-15T12:05:00.001Z", roles=["latest_at_end"])
    write_matrix(matrix, health=[invalid])

    with pytest.raises(MatrixFormatError, match="outside its boundary"):
        validate_matrix(matrix, require_v1_coverage=False)


def test_source_health_event_identity_is_unique_within_sample(tmp_path):
    matrix = tmp_path / "matrix"
    first = source_health(identity=601)
    second = source_health(identity=602)
    second["source_health_event_id"] = first["source_health_event_id"]
    write_matrix(
        matrix,
        health=[first, second],
        manifest_row=manifest(health=2),
    )

    with pytest.raises(MatrixFormatError, match="duplicated within a sample"):
        validate_matrix(matrix, require_v1_coverage=False)


def test_source_summary_is_deterministic_and_descriptive_only():
    rows = [
        sealed_evidence(identity=502, kind="dhcp", observed_at="2026-09-15T12:02:00.000Z"),
        sealed_evidence(identity=501, kind="dhcp", observed_at="2026-09-15T12:01:00.000Z"),
    ]
    rows[1]["quality_state"] = "partial"

    report = source_summary([sample()], rows)
    dhcp = next(row for row in report if row["source_kind"] == "dhcp")

    assert dhcp == {
        "sample_id": sample()["sample_id"],
        "source_kind": "dhcp",
        "evidence_count": 2,
        "valid_count": 1,
        "partial_count": 1,
        "degraded_count": 0,
        "distinct_payload_sha256_count": 1,
        "first_observed_at": "2026-09-15T12:01:00.000Z",
        "last_observed_at": "2026-09-15T12:02:00.000Z",
    }
    assert not ({"classification", "feature", "weight", "score"} & set(dhcp))


def _v1_rows():
    device_rows = []
    state_rows = []
    sample_rows = []
    evidence_rows = []
    cells = [
        ("smartphone", "android", "14"),
        ("smartphone", "ios", "17"),
        ("tablet", "android", "14"),
        ("tablet", "ipados", "17"),
        ("laptop", "windows", "11"),
        ("laptop", "macos", "14"),
    ]
    next_evidence_id = 10_000
    quic_added_for = set()
    for device_index, (device_class, family, version) in enumerate(cells * 2, start=1):
        state_id = 100 + device_index
        device_rows.append(device(device_index, device_class=device_class, model=f"Model {device_index}"))
        state_rows.append(device_state(state_id, device_id=device_index, family=family, version=version))
        first_sample_id = None
        for repetition in range(4):
            sample_id = 1_000 + device_index * 10 + repetition
            first_sample_id = first_sample_id or sample_id
            context = "normal_browser" if repetition % 2 == 0 else "captive_webview"
            sample_rows.append(sample(
                sample_id,
                device_id=device_index,
                state_id=state_id,
                epoch_id=2_000 + device_index * 2 + repetition % 2,
                context=context,
                supported=True,
            ))
        for kind in ("portal_headers", "dhcp", "tcp_syn", "tls_client"):
            evidence_rows.append(sealed_evidence(
                next_evidence_id,
                sample_id=first_sample_id,
                device_id=device_index,
                kind=kind,
            ))
            next_evidence_id += 1
        if family in {"android", "ios", "windows"} and family not in quic_added_for:
            evidence_rows.append(sealed_evidence(
                next_evidence_id,
                sample_id=first_sample_id,
                device_id=device_index,
                kind="quic_client",
            ))
            quic_added_for.add(family)
            next_evidence_id += 1
    return device_rows, state_rows, sample_rows, evidence_rows


def _write_v1_matrix(matrix, *, evidence_mutator=None):
    device_rows, state_rows, sample_rows, evidence_rows = _v1_rows()
    if evidence_mutator is not None:
        evidence_mutator(device_rows, evidence_rows)

    write_matrix(
        matrix,
        devices=device_rows,
        states=state_rows,
        samples=sample_rows,
        evidence=evidence_rows,
        health=[],
        manifest_row=manifest(
            devices=len(device_rows),
            samples=len(sample_rows),
            evidence=len(evidence_rows),
            health=0,
            limitations=[],
        ),
    )
    return device_rows, evidence_rows


def test_complete_v1_coverage_contract_passes(tmp_path):
    matrix = tmp_path / "matrix"
    _write_v1_matrix(matrix)

    report = validate_matrix(matrix)

    assert report["coverage"] == {
        "v1_coverage_pass": True,
        "device_count_pass": True,
        "sealed_sample_count_pass": True,
        "mandatory_cells_pass": True,
        "minimum_repetition_pass": True,
        "runtime_variation_pass": True,
        "all_source_kinds_pass": True,
        "per_device_core_sources_pass": True,
        "quic_coverage_pass": True,
        "mandatory_cell_device_counts": {
            "smartphone:android": 2,
            "smartphone:ios": 2,
            "tablet:android": 2,
            "tablet:ipados": 2,
            "laptop:windows": 2,
            "laptop:macos": 2,
        },
        "quic_os_family_count": 3,
    }


def test_partial_and_degraded_core_evidence_still_counts_as_device_presence(tmp_path):
    matrix = tmp_path / "matrix"

    def mutate(device_rows, evidence_rows):
        target = device_rows[0]["lab_device_id"]
        target_core = [
            row for row in evidence_rows
            if row["lab_device_id"] == target
            and row["source_kind"] in {"portal_headers", "dhcp", "tcp_syn", "tls_client"}
        ]
        for index, row in enumerate(target_core):
            row["quality_state"] = "partial" if index % 2 == 0 else "degraded"

    _write_v1_matrix(matrix, evidence_mutator=mutate)
    report = validate_matrix(matrix)

    assert report["coverage"]["per_device_core_sources_pass"] is True
    assert report["coverage"]["all_source_kinds_pass"] is True
    assert report["coverage"]["v1_coverage_pass"] is True


def test_nonvalid_quic_counts_by_family_but_not_as_matrix_wide_valid_source(tmp_path):
    matrix = tmp_path / "matrix"

    def mutate(_device_rows, evidence_rows):
        quic_rows = [row for row in evidence_rows if row["source_kind"] == "quic_client"]
        for index, row in enumerate(quic_rows):
            row["quality_state"] = "partial" if index % 2 == 0 else "degraded"

    _write_v1_matrix(matrix, evidence_mutator=mutate)
    report = validate_matrix(matrix, require_v1_coverage=False)

    assert report["coverage"]["quic_os_family_count"] == 3
    assert report["coverage"]["quic_coverage_pass"] is True
    assert report["coverage"]["all_source_kinds_pass"] is False
    assert report["coverage"]["v1_coverage_pass"] is False


def test_matrix_copy_remains_byte_identical_after_validation(tmp_path):
    matrix = tmp_path / "matrix"
    copy = tmp_path / "copy"
    write_matrix(matrix)
    shutil.copytree(matrix, copy)
    before = {path.name: path.read_bytes() for path in copy.iterdir()}

    validate_matrix(copy, require_v1_coverage=False)

    assert {path.name: path.read_bytes() for path in copy.iterdir()} == before
