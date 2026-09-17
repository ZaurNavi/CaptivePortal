from __future__ import annotations

import hashlib
import sqlite3
import uuid
from pathlib import Path

import pytest

from research.device_fingerprint_03a.exporter import (
    export_unsealed_matrix,
    seal_matrix,
    validate_staging_directory,
)
from research.device_fingerprint_03a.format import (
    CHECKSUM_FILES,
    MatrixFormatError,
    read_canonical_json,
    read_canonical_jsonl,
)
from research.device_fingerprint_03a.validator import validate_matrix

from . import (
    binding,
    create_source_database,
    device,
    device_state,
    sample,
    sealed_evidence,
    source_health,
    uid,
    write_staging,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _export(tmp_path, *, evidence_rows=None, health_rows=None, samples=None, bindings=None):
    staging = tmp_path / "staging"
    write_staging(staging, samples=samples, bindings=bindings)
    database = tmp_path / "fingerprint.sqlite3"
    create_source_database(
        database,
        evidence_rows if evidence_rows is not None else [sealed_evidence()],
        health_rows if health_rows is not None else [],
    )
    environment = tmp_path / "authorized-environment.json"
    environment.write_text("{}\n", encoding="utf-8")
    output = tmp_path / "matrix"
    result = export_unsealed_matrix(
        db_path=str(database.resolve()),
        staging_dir=staging.resolve(),
        output_dir=output.resolve(),
        authorized_environment_record=environment.resolve(),
        matrix_id=uid(901),
        repository_head="a" * 40,
        repository_tree="b" * 40,
        collection_procedure_version="1.0.0",
        ground_truth_policy_version="1.0.0",
        task01_retention_days=30,
        known_coverage_limitations=["quic_sparse"],
    )
    return database, output, result


def test_synthetic_v2_database_has_shared_deterministic_watermark_and_generation(tmp_path):
    database = tmp_path / "mixed.sqlite3"
    create_source_database(
        database,
        [sealed_evidence(identity=501), sealed_evidence(identity=502)],
        [source_health(identity=601), source_health(identity=602)],
    )
    with sqlite3.connect(database) as connection:
        evidence_sequences = [row[0] for row in connection.execute(
            "SELECT ingest_sequence FROM device_fingerprint_evidence ORDER BY ingest_sequence"
        )]
        health_sequences = [row[0] for row in connection.execute(
            "SELECT ingest_sequence FROM device_fingerprint_source_health_events ORDER BY ingest_sequence"
        )]
        generation, watermark = connection.execute(
            "SELECT database_generation_id, last_ingest_sequence "
            "FROM device_fingerprint_storage_state WHERE singleton_id=1"
        ).fetchone()
    assert evidence_sequences == [1, 2]
    assert health_sequences == [3, 4]
    assert len(set(evidence_sequences + health_sequences)) == 4
    assert uuid.UUID(generation).version == 4
    assert watermark == 4

    empty = tmp_path / "empty.sqlite3"
    create_source_database(empty, [], [])
    with sqlite3.connect(empty) as connection:
        empty_generation, empty_watermark = connection.execute(
            "SELECT database_generation_id, last_ingest_sequence "
            "FROM device_fingerprint_storage_state WHERE singleton_id=1"
        ).fetchone()
    assert empty_generation == generation
    assert empty_watermark == 0


def test_staging_requires_exact_relationships_and_private_binding(tmp_path):
    staging = tmp_path / "staging"
    write_staging(staging)

    assert validate_staging_directory(staging) == {
        "device_count": 1,
        "device_state_count": 1,
        "sealed_sample_count": 1,
        "binding_count": 1,
    }


def test_export_is_read_only_half_open_and_deidentified(tmp_path):
    inside = sealed_evidence(observed_at="2026-09-15T12:04:59.999Z")
    at_end = sealed_evidence(identity=502, observed_at="2026-09-15T12:05:00.000Z")
    database, output, result = _export(tmp_path, evidence_rows=[inside, at_end])
    del database
    rows = read_canonical_jsonl(output / "evidence.jsonl")

    assert result.evidence_count == 1
    assert [row["evidence_id"] for row in rows] == [inside["evidence_id"]]
    assert "observed_mac" not in rows[0]
    assert "observed_ip" not in rows[0]
    assert "payload_json" not in rows[0]
    assert not (output / "collection_bindings.jsonl").exists()
    assert set(path.name for path in output.iterdir()) == set(CHECKSUM_FILES)
    assert read_canonical_json(output / "manifest.json")["sealed_at"] is None


def test_export_preserves_task01_database_bytes(tmp_path):
    staging = tmp_path / "staging"
    write_staging(staging)
    database = tmp_path / "fingerprint.sqlite3"
    create_source_database(database, [sealed_evidence()])
    environment = tmp_path / "authorization.txt"
    environment.write_text("authorized\n", encoding="utf-8")
    before = (database.stat().st_size, _sha(database))

    export_unsealed_matrix(
        db_path=str(database.resolve()),
        staging_dir=staging.resolve(),
        output_dir=(tmp_path / "matrix").resolve(),
        authorized_environment_record=environment.resolve(),
        matrix_id=uid(902),
        repository_head="a" * 40,
        repository_tree="b" * 40,
        collection_procedure_version="1.0.0",
        ground_truth_policy_version="1.0.0",
        task01_retention_days=30,
    )

    assert (database.stat().st_size, _sha(database)) == before


def test_source_health_uses_boundary_snapshots_and_deduplicated_roles(tmp_path):
    before = source_health(identity=601, observed_at="2026-09-15T11:59:00.000Z", roles=["latest_before_start"])
    during = source_health(identity=602, observed_at="2026-09-15T12:02:00.000Z", roles=["during_window"])
    at_end = source_health(identity=603, observed_at="2026-09-15T12:05:00.000Z", roles=["latest_at_end"])
    database, output, result = _export(
        tmp_path,
        evidence_rows=[sealed_evidence()],
        health_rows=[before, during, at_end],
    )
    del database
    rows = read_canonical_jsonl(output / "source_health.jsonl")
    by_id = {row["source_health_id"]: row for row in rows}

    assert result.source_health_count == 3
    assert by_id[before["source_health_id"]]["point_roles"] == ["latest_before_start"]
    assert by_id[during["source_health_id"]]["point_roles"] == ["during_window"]
    assert by_id[at_end["source_health_id"]]["point_roles"] == ["latest_at_end"]


def test_one_source_health_event_can_serve_all_three_point_roles(tmp_path):
    point = source_health(observed_at="2026-09-15T12:00:00.000Z")
    _, output, result = _export(tmp_path, health_rows=[point])
    rows = read_canonical_jsonl(output / "source_health.jsonl")

    assert result.source_health_count == 1
    assert rows[0]["point_roles"] == ["latest_before_start", "during_window", "latest_at_end"]


def test_export_revalidates_payload_against_production_registry(tmp_path):
    invalid = sealed_evidence()
    invalid["payload"] = {"message_type": "discover", "unexpected": "not allowed"}
    with pytest.raises(MatrixFormatError):
        _export(tmp_path, evidence_rows=[invalid])


def test_overlapping_cross_device_binding_collision_fails_closed(tmp_path):
    staging = tmp_path / "staging"
    devices = [device(1), device(2)]
    states = [device_state(101, device_id=1), device_state(102, device_id=2)]
    samples = [
        sample(201, device_id=1, state_id=101),
        sample(202, device_id=2, state_id=102, start="2026-09-15T12:01:00.000Z", end="2026-09-15T12:04:00.000Z"),
    ]
    bindings = [binding(201, device_id=1), binding(202, device_id=2)]
    write_staging(staging, devices=devices, states=states, samples=samples, bindings=bindings)

    with pytest.raises(MatrixFormatError):
        validate_staging_directory(staging)


def test_same_evidence_cannot_be_assigned_to_overlapping_samples(tmp_path):
    samples = [
        sample(201),
        sample(202, start="2026-09-15T12:01:00.000Z", end="2026-09-15T12:04:00.000Z"),
    ]
    bindings = [binding(201), binding(202)]
    with pytest.raises(MatrixFormatError):
        _export(tmp_path, samples=samples, bindings=bindings)


def test_seal_requires_owner_verification_and_creates_exact_checksum_authority(tmp_path):
    _, output, _ = _export(tmp_path)
    with pytest.raises(MatrixFormatError):
        seal_matrix(output, sealed_at="2026-09-15T13:00:00.000Z", owner_verified=False)

    report = seal_matrix(
        output,
        sealed_at="2026-09-15T13:00:00.000Z",
        owner_verified=True,
        require_v1_coverage=False,
    )

    assert report["status"] == "pass"
    assert read_canonical_json(output / "manifest.json")["sealed_at"] == "2026-09-15T13:00:00.000Z"
    assert (output / "checksums.sha256").is_file()
    assert validate_matrix(output, require_v1_coverage=False)["status"] == "pass"


def test_export_requires_absolute_existing_environment_authorization(tmp_path):
    staging = tmp_path / "staging"
    write_staging(staging)
    database = tmp_path / "fingerprint.sqlite3"
    create_source_database(database, [sealed_evidence()])

    with pytest.raises(MatrixFormatError):
        export_unsealed_matrix(
            db_path=str(database.resolve()),
            staging_dir=staging.resolve(),
            output_dir=(tmp_path / "output").resolve(),
            authorized_environment_record=tmp_path / "missing.json",
            matrix_id=uid(903),
            repository_head="a" * 40,
            repository_tree="b" * 40,
            collection_procedure_version="1.0.0",
            ground_truth_policy_version="1.0.0",
            task01_retention_days=30,
        )
