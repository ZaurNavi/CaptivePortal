"""Strict semantic validator and deterministic descriptive matrix report."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from .format import (
    CHECKSUM_FILES,
    SEALED_DATA_FILES,
    SOURCE_KINDS,
    MatrixFormatError,
    read_canonical_json,
    read_canonical_jsonl,
    validate_checksums,
    validate_device,
    validate_device_state,
    validate_evidence,
    validate_manifest,
    validate_sample,
    validate_source_health,
)

_MANDATORY_CELLS = (
    ("smartphone", "android"),
    ("smartphone", "ios"),
    ("tablet", "android"),
    ("tablet", "ipados"),
    ("laptop", "windows"),
    ("laptop", "macos"),
)
_CORE_SOURCES = frozenset({"portal_headers", "dhcp", "tcp_syn", "tls_client"})


def validate_matrix(
    matrix_dir: str | Path,
    *,
    verify_checksums: bool = True,
    require_v1_coverage: bool = True,
) -> dict[str, Any]:
    requested_directory = Path(matrix_dir)
    if requested_directory.is_symlink():
        raise MatrixFormatError("Matrix directory is invalid")
    directory = requested_directory.resolve(strict=True)
    _validate_file_set(directory, verify_checksums=verify_checksums)
    if verify_checksums:
        validate_checksums(directory)

    manifest = validate_manifest(read_canonical_json(directory / "manifest.json"))
    devices = [validate_device(row) for row in read_canonical_jsonl(directory / "devices.jsonl")]
    states = [validate_device_state(row) for row in read_canonical_jsonl(directory / "device_states.jsonl")]
    samples = [validate_sample(row) for row in read_canonical_jsonl(directory / "samples.jsonl")]
    evidence = [validate_evidence(row) for row in read_canonical_jsonl(directory / "evidence.jsonl")]
    health = [validate_source_health(row) for row in read_canonical_jsonl(directory / "source_health.jsonl")]

    if evidence != sorted(
        evidence,
        key=lambda row: (row["sample_id"], row["observed_at"], row["evidence_id"]),
    ):
        raise MatrixFormatError("Evidence ordering is invalid")

    device_map = _unique(devices, "lab_device_id", "device")
    state_map = _unique(states, "ground_truth_state_id", "device state")
    sample_map = _unique(samples, "sample_id", "sample")
    _validate_relationships(device_map, state_map, sample_map, evidence, health)
    _validate_manifest_counts(manifest, devices, samples, evidence, health)
    coverage = _coverage(manifest, device_map, state_map, samples, evidence)
    if require_v1_coverage and not coverage["v1_coverage_pass"]:
        raise MatrixFormatError("Mandatory V1 matrix coverage is incomplete")
    return {
        "status": "pass",
        "matrix_id": manifest["matrix_id"],
        "device_count": len(devices),
        "sealed_sample_count": len(samples),
        "evidence_count": len(evidence),
        "source_health_count": len(health),
        "coverage": coverage,
        "sample_source_summary": source_summary(samples, evidence),
    }


def source_summary(
    samples: list[Mapping[str, Any]],
    evidence: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in evidence:
        grouped[(row["sample_id"], row["source_kind"])].append(row)
    result: list[dict[str, Any]] = []
    for sample in sorted(samples, key=lambda row: row["sample_id"]):
        for kind in SOURCE_KINDS:
            rows = grouped[(sample["sample_id"], kind)]
            quality = Counter(row["quality_state"] for row in rows)
            observed = sorted(row["observed_at"] for row in rows)
            result.append({
                "sample_id": sample["sample_id"],
                "source_kind": kind,
                "evidence_count": len(rows),
                "valid_count": quality["valid"],
                "partial_count": quality["partial"],
                "degraded_count": quality["degraded"],
                "distinct_payload_sha256_count": len({row["payload_sha256"] for row in rows}),
                "first_observed_at": observed[0] if observed else None,
                "last_observed_at": observed[-1] if observed else None,
            })
    return result


def _validate_file_set(directory: Path, *, verify_checksums: bool) -> None:
    if not directory.is_dir() or directory.is_symlink():
        raise MatrixFormatError("Matrix directory is invalid")
    expected = set(SEALED_DATA_FILES if verify_checksums else CHECKSUM_FILES)
    try:
        actual = {entry.name for entry in directory.iterdir()}
    except OSError as exc:
        raise MatrixFormatError("Matrix directory is unavailable") from exc
    if actual != expected:
        raise MatrixFormatError("Matrix file set is invalid")


def _unique(rows: list[dict[str, Any]], key: str, label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        identity = row[key]
        if identity in result:
            raise MatrixFormatError(f"Duplicate {label} identity")
        result[identity] = row
    return result


def _validate_relationships(
    devices: Mapping[str, Mapping[str, Any]],
    states: Mapping[str, Mapping[str, Any]],
    samples: Mapping[str, Mapping[str, Any]],
    evidence: list[Mapping[str, Any]],
    health: list[Mapping[str, Any]],
) -> None:
    state_families: dict[str, set[str]] = defaultdict(set)
    for state in states.values():
        if state["lab_device_id"] not in devices:
            raise MatrixFormatError("Device state references an unknown device")
        state_families[state["lab_device_id"]].add(state["os_family_gt"])
    if any(len(families) != 1 for families in state_families.values()):
        raise MatrixFormatError("One device has conflicting OS families")
    for sample in samples.values():
        state = states.get(sample["ground_truth_state_id"])
        if sample["lab_device_id"] not in devices or state is None:
            raise MatrixFormatError("Sample references unknown ground truth")
        if state["lab_device_id"] != sample["lab_device_id"]:
            raise MatrixFormatError("Sample state belongs to another device")

    evidence_ids: set[str] = set()
    for row in evidence:
        sample = samples.get(row["sample_id"])
        if sample is None or sample["lab_device_id"] != row["lab_device_id"]:
            raise MatrixFormatError("Evidence sample relationship is invalid")
        if row["evidence_id"] in evidence_ids:
            raise MatrixFormatError("Evidence is assigned more than once")
        evidence_ids.add(row["evidence_id"])
        if not sample["window_start_utc"] <= row["observed_at"] < sample["window_end_utc"]:
            raise MatrixFormatError("Evidence is outside its sample window")

    health_ids: set[tuple[str, str, str]] = set()
    latest_roles: set[tuple[str, str, str, str]] = set()
    for row in health:
        sample = samples.get(row["sample_id"])
        if sample is None or sample["lab_device_id"] != row["lab_device_id"]:
            raise MatrixFormatError("Source-health sample relationship is invalid")
        identity = (row["sample_id"], row["producer_id"], row["source_health_event_id"])
        if identity in health_ids:
            raise MatrixFormatError("Source-health event is duplicated within a sample")
        health_ids.add(identity)
        for role in row["point_roles"]:
            if role == "latest_before_start" and row["observed_at"] > sample["window_start_utc"]:
                raise MatrixFormatError("Source-health start role is outside its boundary")
            if role == "during_window" and not sample["window_start_utc"] <= row["observed_at"] < sample["window_end_utc"]:
                raise MatrixFormatError("Source-health window role is outside its boundary")
            if role == "latest_at_end" and row["observed_at"] > sample["window_end_utc"]:
                raise MatrixFormatError("Source-health end role is outside its boundary")
            if role != "during_window":
                role_key = (row["sample_id"], row["capture_source_id"], row["source_kind"], role)
                if role_key in latest_roles:
                    raise MatrixFormatError("Source-health latest role is duplicated")
                latest_roles.add(role_key)


def _validate_manifest_counts(
    manifest: Mapping[str, Any],
    devices: list[Mapping[str, Any]],
    samples: list[Mapping[str, Any]],
    evidence: list[Mapping[str, Any]],
    health: list[Mapping[str, Any]],
) -> None:
    expected = {
        "device_count": len(devices),
        "sealed_sample_count": len(samples),
        "evidence_count": len(evidence),
        "source_health_count": len(health),
    }
    if any(manifest[key] != count for key, count in expected.items()):
        raise MatrixFormatError("Manifest counts do not match matrix files")


def _coverage(
    manifest: Mapping[str, Any],
    devices: Mapping[str, Mapping[str, Any]],
    states: Mapping[str, Mapping[str, Any]],
    samples: list[Mapping[str, Any]],
    evidence: list[Mapping[str, Any]],
) -> dict[str, Any]:
    samples_by_device: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for sample in samples:
        samples_by_device[sample["lab_device_id"]].append(sample)
    family_by_device = {
        state["lab_device_id"]: state["os_family_gt"]
        for state in states.values()
    }
    cell_counts = {
        f"{device_class}:{family}": sum(
            1 for device_id, device in devices.items()
            if device["device_class_gt"] == device_class and family_by_device.get(device_id) == family
        )
        for device_class, family in _MANDATORY_CELLS
    }
    repetition_pass = all(
        len(samples_by_device[device_id]) >= 4
        and len({sample["network_epoch_id"] for sample in samples_by_device[device_id]}) >= 2
        for device_id in devices
    )
    context_pass = True
    for device_id in devices:
        rows = samples_by_device[device_id]
        support_values = {row["context_supported_gt"] for row in rows}
        if len(support_values) > 1:
            context_pass = False
            continue
        contexts = {row["runtime_context_gt"] for row in rows}
        if support_values == {True} and not (
            "normal_browser" in contexts
            and bool({"captive_webview", "captive_helper"} & contexts)
        ):
            context_pass = False
        if support_values == {False} and bool({"captive_webview", "captive_helper"} & contexts):
            context_pass = False

    kinds_by_device: dict[str, set[str]] = defaultdict(set)
    all_valid_kinds: set[str] = set()
    quic_families: set[str] = set()
    sample_map = {sample["sample_id"]: sample for sample in samples}
    for row in evidence:
        device_id = row["lab_device_id"]
        kinds_by_device[device_id].add(row["source_kind"])
        if row["quality_state"] == "valid":
            all_valid_kinds.add(row["source_kind"])
        if row["source_kind"] == "quic_client":
            sample = sample_map[row["sample_id"]]
            quic_families.add(states[sample["ground_truth_state_id"]]["os_family_gt"])
    core_sources_pass = all(_CORE_SOURCES <= kinds_by_device[device_id] for device_id in devices)
    quic_pass = len(quic_families) >= 3 or "quic_sparse" in manifest["known_coverage_limitations"]
    device_count_pass = len(devices) >= 12
    sample_count_pass = len(samples) >= 48
    cell_pass = all(count >= 2 for count in cell_counts.values())
    all_sources_pass = set(SOURCE_KINDS) <= all_valid_kinds
    overall = all((
        device_count_pass,
        sample_count_pass,
        cell_pass,
        repetition_pass,
        context_pass,
        all_sources_pass,
        core_sources_pass,
        quic_pass,
    ))
    return {
        "v1_coverage_pass": overall,
        "device_count_pass": device_count_pass,
        "sealed_sample_count_pass": sample_count_pass,
        "mandatory_cells_pass": cell_pass,
        "minimum_repetition_pass": repetition_pass,
        "runtime_variation_pass": context_pass,
        "all_source_kinds_pass": all_sources_pass,
        "per_device_core_sources_pass": core_sources_pass,
        "quic_coverage_pass": quic_pass,
        "mandatory_cell_device_counts": cell_counts,
        "quic_os_family_count": len(quic_families),
    }
