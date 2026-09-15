"""Read-only Task-01 evidence export and explicit Task-03A sealing."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from app.device_fingerprint.read_service import DeviceFingerprintReadService
from app.device_fingerprint.repository import open_read_only
from app.device_fingerprint.validation import canonical_json, canonical_sha256

from .format import (
    MATRIX_FORMAT_VERSION,
    MATRIX_REVISION,
    PRODUCTION_SCHEMA_REGISTRY,
    SITE_ID,
    SOURCE_CAPTURE_IDS,
    SOURCE_KINDS,
    MatrixFormatError,
    read_canonical_json,
    read_canonical_jsonl,
    validate_binding,
    validate_device,
    validate_device_state,
    validate_evidence,
    validate_manifest,
    validate_sample,
    validate_source_health,
    write_canonical_json,
    write_canonical_jsonl,
    write_checksums,
)

_MAX_SOURCE_HEALTH_POINTS_PER_SCOPE = 10_000


@dataclass(frozen=True, slots=True)
class ExportResult:
    matrix_id: str
    device_count: int
    sample_count: int
    evidence_count: int
    source_health_count: int


def validate_staging_directory(staging_dir: str | Path) -> dict[str, int]:
    """Validate sealed-ready ground truth and its private binding ledger."""

    staging = Path(staging_dir).resolve(strict=True)
    if not staging.is_dir() or staging.is_symlink():
        raise MatrixFormatError("Staging directory is invalid")
    devices = [validate_device(row) for row in read_canonical_jsonl(staging / "devices.jsonl")]
    states = [validate_device_state(row) for row in read_canonical_jsonl(staging / "device_states.jsonl")]
    samples = [validate_sample(row) for row in read_canonical_jsonl(staging / "samples.jsonl")]
    bindings = [validate_binding(row) for row in read_canonical_jsonl(staging / "collection_bindings.jsonl")]
    _validate_staging_relationships(devices, states, samples, bindings)
    return {
        "device_count": len(devices),
        "device_state_count": len(states),
        "sealed_sample_count": len(samples),
        "binding_count": len(bindings),
    }


def export_unsealed_matrix(
    *,
    db_path: str,
    staging_dir: str | Path,
    output_dir: str | Path,
    authorized_environment_record: str | Path,
    matrix_id: str,
    repository_head: str,
    repository_tree: str,
    collection_procedure_version: str,
    ground_truth_policy_version: str,
    task01_retention_days: int,
    invalid_sample_reason_counts: Mapping[str, int] | None = None,
    known_coverage_limitations: list[str] | None = None,
    supersedes_matrix_id: str | None = None,
) -> ExportResult:
    """Export a deterministic unsealed package without mutating Task-01."""

    database = _absolute_existing_file(db_path, "Task-01 database")
    _absolute_existing_file(authorized_environment_record, "environment authorization record")
    staging = Path(staging_dir).resolve(strict=True)
    output = Path(output_dir).resolve(strict=False)
    _prepare_empty_output(output)

    devices = sorted(
        (validate_device(row) for row in read_canonical_jsonl(staging / "devices.jsonl")),
        key=lambda row: row["lab_device_id"],
    )
    states = sorted(
        (validate_device_state(row) for row in read_canonical_jsonl(staging / "device_states.jsonl")),
        key=lambda row: (row["lab_device_id"], row["state_verified_at"], row["ground_truth_state_id"]),
    )
    samples = sorted(
        (validate_sample(row) for row in read_canonical_jsonl(staging / "samples.jsonl")),
        key=lambda row: row["sample_id"],
    )
    bindings = [validate_binding(row) for row in read_canonical_jsonl(staging / "collection_bindings.jsonl")]
    _validate_staging_relationships(devices, states, samples, bindings)

    before = _durable_database_fingerprint(database)
    evidence_service = DeviceFingerprintReadService(
        str(database),
        retention_days=task01_retention_days,
    )
    exported_evidence: list[dict[str, Any]] = []
    exported_health: list[dict[str, Any]] = []
    assigned_evidence: set[str] = set()
    bindings_by_sample = {row["sample_id"]: row for row in bindings}
    for sample in samples:
        binding = bindings_by_sample[sample["sample_id"]]
        evidence = _read_sample_evidence(evidence_service, sample, binding["observed_mac"])
        for row in evidence:
            if row["evidence_id"] in assigned_evidence:
                raise MatrixFormatError("Evidence is assigned to more than one sample")
            assigned_evidence.add(row["evidence_id"])
            exported_evidence.append(_deidentify_evidence(row, sample))
        exported_health.extend(_read_sample_source_health(database, sample))
    after = _durable_database_fingerprint(database)
    if before != after:
        raise MatrixFormatError("Task-01 database changed during read-only export")

    exported_evidence.sort(key=lambda row: (row["sample_id"], row["observed_at"], row["evidence_id"]))
    exported_health.sort(key=lambda row: (
        row["sample_id"], row["capture_source_id"], row["source_kind"],
        row["observed_at"], row["source_health_id"],
    ))
    write_canonical_jsonl(output / "devices.jsonl", devices)
    write_canonical_jsonl(output / "device_states.jsonl", states)
    write_canonical_jsonl(output / "samples.jsonl", samples)
    write_canonical_jsonl(output / "evidence.jsonl", exported_evidence)
    write_canonical_jsonl(output / "source_health.jsonl", exported_health)

    reasons = dict(invalid_sample_reason_counts or {})
    manifest = validate_manifest({
        "matrix_format_version": MATRIX_FORMAT_VERSION,
        "matrix_id": matrix_id,
        "matrix_revision": MATRIX_REVISION,
        "sealed_at": None,
        "repository_head": repository_head,
        "repository_tree": repository_tree,
        "site_id": SITE_ID,
        "collection_procedure_version": collection_procedure_version,
        "ground_truth_policy_version": ground_truth_policy_version,
        "production_schema_registry": [list(item) for item in PRODUCTION_SCHEMA_REGISTRY],
        "task01_retention_days": task01_retention_days,
        "device_count": len(devices),
        "sealed_sample_count": len(samples),
        "evidence_count": len(exported_evidence),
        "source_health_count": len(exported_health),
        "invalid_sample_count": sum(reasons.values()),
        "invalid_sample_reason_counts": reasons,
        "known_coverage_limitations": sorted(known_coverage_limitations or []),
        "supersedes_matrix_id": supersedes_matrix_id,
    }, sealed=False)
    write_canonical_json(output / "manifest.json", manifest)
    return ExportResult(matrix_id, len(devices), len(samples), len(exported_evidence), len(exported_health))


def seal_matrix(
    matrix_dir: str | Path,
    *,
    sealed_at: str,
    owner_verified: bool,
    require_v1_coverage: bool = True,
) -> dict[str, Any]:
    """Seal only after explicit manual Owner verification."""

    if owner_verified is not True:
        raise MatrixFormatError("Manual Owner verification is required")
    directory = Path(matrix_dir).resolve(strict=True)
    manifest = validate_manifest(read_canonical_json(directory / "manifest.json"), sealed=False)
    manifest["sealed_at"] = sealed_at
    validate_manifest(manifest)
    write_canonical_json(directory / "manifest.json", manifest)
    from .validator import validate_matrix
    try:
        report = validate_matrix(
            directory,
            verify_checksums=False,
            require_v1_coverage=require_v1_coverage,
        )
        write_checksums(directory)
        validate_matrix(directory, verify_checksums=True, require_v1_coverage=require_v1_coverage)
    except Exception:
        # A failed seal must not leave a checksum authority behind.
        checksum_path = directory / "checksums.sha256"
        if checksum_path.exists() and checksum_path.is_file() and not checksum_path.is_symlink():
            checksum_path.unlink()
        manifest["sealed_at"] = None
        write_canonical_json(directory / "manifest.json", manifest)
        raise
    return report


def _read_sample_evidence(
    service: DeviceFingerprintReadService,
    sample: Mapping[str, Any],
    observed_mac: str,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    cursor = None
    while True:
        page = service.list_evidence(
            sample["site_id"],
            observed_mac,
            sample["window_start_utc"],
            sample["window_end_utc"],
            limit=500,
            cursor=cursor,
        )
        result.extend(page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            return result


def _deidentify_evidence(row: Mapping[str, Any], sample: Mapping[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(row["payload_json"])
    except (TypeError, json.JSONDecodeError) as exc:
        raise MatrixFormatError("Stored evidence payload is invalid") from exc
    try:
        canonical_payload = canonical_json(payload)
    except Exception as exc:
        raise MatrixFormatError("Stored evidence payload is invalid") from exc
    if canonical_payload != row["payload_json"] or canonical_sha256(canonical_payload) != row["payload_sha256"]:
        raise MatrixFormatError("Stored evidence payload digest is invalid")
    sealed = {
        "evidence_id": row["evidence_id"],
        "source_event_id": row["source_event_id"],
        "producer_id": row["producer_id"],
        "source_kind": row["source_kind"],
        "source_subtype": row["source_subtype"],
        "extractor_name": row["extractor_name"],
        "extractor_version": row["extractor_version"],
        "feature_schema_version": row["feature_schema_version"],
        "rule_version": row["rule_version"],
        "site_id": row["site_id"],
        "capture_source_id": row["capture_source_id"],
        "observed_at": row["observed_at"],
        "quality_state": row["quality_state"],
        "privacy_class": row["privacy_class"],
        "payload": payload,
        "payload_sha256": row["payload_sha256"],
        "ingested_at": row["ingested_at"],
        "sample_id": sample["sample_id"],
        "lab_device_id": sample["lab_device_id"],
    }
    return validate_evidence(sealed)


def _read_sample_source_health(database: Path, sample: Mapping[str, Any]) -> list[dict[str, Any]]:
    connection = open_read_only(str(database))
    try:
        if connection.execute("PRAGMA query_only").fetchone()[0] != 1:
            raise MatrixFormatError("Task-01 read boundary is not query-only")
        result: list[dict[str, Any]] = []
        for kind in SOURCE_KINDS:
            capture = SOURCE_CAPTURE_IDS[kind]
            rows: dict[tuple[str, str], tuple[dict[str, Any], set[str]]] = {}
            before = connection.execute(
                "SELECT * FROM device_fingerprint_source_health_events "
                "WHERE site_id=? AND capture_source_id=? AND source_kind=? AND observed_at<=? "
                "ORDER BY observed_at DESC,source_health_id DESC LIMIT 1",
                (sample["site_id"], capture, kind, sample["window_start_utc"]),
            ).fetchone()
            if before is not None:
                _health_role(rows, dict(before), "latest_before_start")
            during = connection.execute(
                "SELECT * FROM device_fingerprint_source_health_events "
                "WHERE site_id=? AND capture_source_id=? AND source_kind=? "
                "AND observed_at>=? AND observed_at<? "
                "ORDER BY observed_at,source_health_id LIMIT ?",
                (
                    sample["site_id"], capture, kind, sample["window_start_utc"],
                    sample["window_end_utc"], _MAX_SOURCE_HEALTH_POINTS_PER_SCOPE + 1,
                ),
            ).fetchall()
            if len(during) > _MAX_SOURCE_HEALTH_POINTS_PER_SCOPE:
                raise MatrixFormatError("Source-health sample scope is too large")
            for row in during:
                _health_role(rows, dict(row), "during_window")
            at_end = connection.execute(
                "SELECT * FROM device_fingerprint_source_health_events "
                "WHERE site_id=? AND capture_source_id=? AND source_kind=? AND observed_at<=? "
                "ORDER BY observed_at DESC,source_health_id DESC LIMIT 1",
                (sample["site_id"], capture, kind, sample["window_end_utc"]),
            ).fetchone()
            if at_end is not None:
                _health_role(rows, dict(at_end), "latest_at_end")
            for row, roles in rows.values():
                sealed = {
                    "matrix_format_version": MATRIX_FORMAT_VERSION,
                    "sample_id": sample["sample_id"],
                    "lab_device_id": sample["lab_device_id"],
                    "source_health_id": row["source_health_id"],
                    "source_health_event_id": row["source_health_event_id"],
                    "producer_id": row["producer_id"],
                    "site_id": row["site_id"],
                    "capture_source_id": row["capture_source_id"],
                    "source_kind": row["source_kind"],
                    "status": row["status"],
                    "reason_code": row["reason_code"],
                    "observed_at": row["observed_at"],
                    "ingested_at": row["ingested_at"],
                    "point_roles": [role for role in ("latest_before_start", "during_window", "latest_at_end") if role in roles],
                }
                result.append(validate_source_health(sealed))
        return result
    finally:
        connection.close()


def _health_role(
    rows: dict[tuple[str, str], tuple[dict[str, Any], set[str]]],
    row: dict[str, Any],
    role: str,
) -> None:
    identity = (row["producer_id"], row["source_health_event_id"])
    current = rows.get(identity)
    if current is None:
        current = (row, set())
        rows[identity] = current
    elif current[0] != row:
        raise MatrixFormatError("Source-health identity is inconsistent")
    current[1].add(role)


def _validate_staging_relationships(
    devices: list[dict[str, Any]],
    states: list[dict[str, Any]],
    samples: list[dict[str, Any]],
    bindings: list[dict[str, Any]],
) -> None:
    device_map = _unique(devices, "lab_device_id", "device")
    state_map = _unique(states, "ground_truth_state_id", "device state")
    sample_map = _unique(samples, "sample_id", "sample")
    binding_map = _unique(bindings, "sample_id", "binding")
    if set(binding_map) != set(sample_map):
        raise MatrixFormatError("Every sample requires exactly one private binding")
    for state in states:
        if state["lab_device_id"] not in device_map:
            raise MatrixFormatError("Device state references an unknown device")
    for sample in samples:
        state = state_map.get(sample["ground_truth_state_id"])
        if sample["lab_device_id"] not in device_map or state is None:
            raise MatrixFormatError("Sample references unknown ground truth")
        if state["lab_device_id"] != sample["lab_device_id"]:
            raise MatrixFormatError("Sample state belongs to another device")
        if binding_map[sample["sample_id"]]["lab_device_id"] != sample["lab_device_id"]:
            raise MatrixFormatError("Private binding belongs to another device")
    for index, left in enumerate(samples):
        for right in samples[index + 1:]:
            left_binding = binding_map[left["sample_id"]]
            right_binding = binding_map[right["sample_id"]]
            if (
                left["lab_device_id"] != right["lab_device_id"]
                and left_binding["observed_mac"] == right_binding["observed_mac"]
                and left["window_start_utc"] < right["window_end_utc"]
                and right["window_start_utc"] < left["window_end_utc"]
            ):
                raise MatrixFormatError("Private bindings collide across devices")


def _unique(rows: list[dict[str, Any]], key: str, label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        identity = row[key]
        if identity in result:
            raise MatrixFormatError(f"Duplicate {label} identity")
        result[identity] = row
    return result


def _prepare_empty_output(output: Path) -> None:
    try:
        if output.exists():
            if not output.is_dir() or output.is_symlink() or any(output.iterdir()):
                raise MatrixFormatError("Output directory must be empty and safe")
        else:
            output.mkdir(parents=True)
    except MatrixFormatError:
        raise
    except OSError as exc:
        raise MatrixFormatError("Output directory is unavailable") from exc


def _absolute_existing_file(value: str | Path, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise MatrixFormatError(f"{label} must be an absolute path")
    if path.is_symlink():
        raise MatrixFormatError(f"{label} is unsafe")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise MatrixFormatError(f"{label} is unavailable") from exc
    if not resolved.is_file() or resolved.is_symlink():
        raise MatrixFormatError(f"{label} is unsafe")
    return resolved


def _durable_database_fingerprint(database: Path) -> tuple[tuple[int, str], tuple[int, str]]:
    main = database.read_bytes()
    wal_path = Path(str(database) + "-wal")
    wal = wal_path.read_bytes() if wal_path.exists() else b""
    return (
        (len(main), hashlib.sha256(main).hexdigest()),
        (len(wal), hashlib.sha256(wal).hexdigest()),
    )
