from __future__ import annotations

from pathlib import Path

import pytest

from research.device_fingerprint_03a.exporter import export_unsealed_matrix, seal_matrix
from research.device_fingerprint_03a.format import MatrixFormatError
from research.device_fingerprint_03a.validator import validate_matrix

from . import create_source_database, sealed_evidence, uid, write_matrix, write_staging


def _export_private_canary(tmp_path):
    mac = "AA:BB:CC:DD:EE:01"
    ip = "192.168.8.10"
    staging = tmp_path / "staging"
    write_staging(staging)
    source = sealed_evidence()
    source["observed_mac"] = mac
    source["observed_ip"] = ip
    database = tmp_path / "fingerprint.sqlite3"
    create_source_database(database, [source])
    authorization = tmp_path / "authorized-environment.txt"
    authorization.write_text("owner approved lab environment\n", encoding="utf-8")
    output = tmp_path / "matrix"
    export_unsealed_matrix(
        db_path=str(database.resolve()),
        staging_dir=staging.resolve(),
        output_dir=output.resolve(),
        authorized_environment_record=authorization.resolve(),
        matrix_id=uid(901),
        repository_head="a" * 40,
        repository_tree="b" * 40,
        collection_procedure_version="1.0.0",
        ground_truth_policy_version="1.0.0",
        task01_retention_days=30,
        known_coverage_limitations=["quic_sparse"],
    )
    return output, mac, ip


def test_private_binding_identifiers_never_enter_unsealed_or_sealed_matrix(tmp_path):
    output, mac, ip = _export_private_canary(tmp_path)
    unsealed = b"".join(path.read_bytes() for path in output.iterdir())
    assert mac.encode() not in unsealed
    assert ip.encode() not in unsealed
    assert b"collection_bindings" not in unsealed

    seal_matrix(
        output,
        sealed_at="2026-09-15T13:00:00.000Z",
        owner_verified=True,
        require_v1_coverage=False,
    )
    sealed = b"".join(path.read_bytes() for path in output.iterdir())
    assert mac.encode() not in sealed
    assert ip.encode() not in sealed
    assert validate_matrix(output, require_v1_coverage=False)["status"] == "pass"


@pytest.mark.parametrize(
    "private_value",
    [
        "AA:BB:CC:DD:EE:01",
        "192.168.8.10",
        "controlled device at 192.168.8.10",
        "Mozilla/5.0 synthetic raw UA",
        "Authorization: Bearer private-token",
    ],
)
def test_sealed_ground_truth_rejects_private_or_raw_values(tmp_path, private_value):
    matrix = tmp_path / "matrix"
    from . import device
    write_matrix(matrix, devices=[device(model=private_value)])

    with pytest.raises(MatrixFormatError, match="Private value"):
        validate_matrix(matrix, require_v1_coverage=False)


def test_sealed_payload_rejects_private_field_names(tmp_path):
    matrix = tmp_path / "matrix"
    evidence = sealed_evidence()
    evidence["payload"]["observed_mac"] = "not-even-a-mac"
    write_matrix(matrix, evidence=[evidence])

    with pytest.raises(MatrixFormatError):
        validate_matrix(matrix, require_v1_coverage=False)


def test_research_namespace_is_not_imported_by_production_runtime():
    repository = Path(__file__).resolve().parents[2]
    production_paths = [repository / "app", repository / "run.py", repository / "deploy"]
    matches = []
    for root in production_paths:
        paths = [root] if root.is_file() else [path for path in root.rglob("*") if path.is_file()]
        for path in paths:
            if path.suffix not in {".py", ".service", ".timer", ".sh", ".ps1", ".cmd"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if "device_fingerprint_03a" in text:
                matches.append(str(path.relative_to(repository)))
    assert matches == []


def test_repository_contains_no_collected_matrix_artifact():
    repository = Path(__file__).resolve().parents[2]
    assert _forbidden_repository_artifacts(repository) == []


_APPROVED_NON_MATRIX_JSONL = frozenset({
    "research/device_fingerprint_k2a/evidence/conformance_manifest.jsonl",
})


def _forbidden_repository_artifacts(repository: Path) -> list[str]:
    forbidden = []
    for root_name in ("research", "docs"):
        forbidden.extend(
            path.relative_to(repository).as_posix()
            for path in (repository / root_name).rglob("*.jsonl")
            if path.relative_to(repository).as_posix() not in _APPROVED_NON_MATRIX_JSONL
        )
        forbidden.extend(
            path.relative_to(repository).as_posix()
            for path in (repository / root_name).rglob("checksums.sha256")
        )
    return sorted(forbidden)


def test_only_exact_k2a_manifest_is_exempt_from_matrix_artifact_policy(tmp_path):
    approved = tmp_path / "research/device_fingerprint_k2a/evidence/conformance_manifest.jsonl"
    approved.parent.mkdir(parents=True)
    approved.write_text("{}\n", encoding="utf-8")
    assert _forbidden_repository_artifacts(tmp_path) == []

    other_k2a = approved.with_name("other.jsonl")
    other_k2a.write_text("{}\n", encoding="utf-8")
    research_other = tmp_path / "research/other/collected.jsonl"
    research_other.parent.mkdir()
    research_other.write_text("{}\n", encoding="utf-8")
    docs_other = tmp_path / "docs/collected.jsonl"
    docs_other.parent.mkdir()
    docs_other.write_text("{}\n", encoding="utf-8")
    checksum = approved.with_name("checksums.sha256")
    checksum.write_text("hash\n", encoding="utf-8")
    assert _forbidden_repository_artifacts(tmp_path) == [
        "docs/collected.jsonl",
        "research/device_fingerprint_k2a/evidence/checksums.sha256",
        "research/device_fingerprint_k2a/evidence/other.jsonl",
        "research/other/collected.jsonl",
    ]


def test_validator_output_contains_no_classifier_or_training_contract(tmp_path):
    matrix = tmp_path / "matrix"
    write_matrix(matrix)
    report = validate_matrix(matrix, require_v1_coverage=False)
    rendered = repr(report).lower()

    assert "classifier" not in rendered
    assert "confidence" not in rendered
    assert "feature_vector" not in rendered
    assert "weight" not in rendered
