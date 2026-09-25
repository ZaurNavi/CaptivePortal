"""Single-transaction R14 T-01 snapshot execution under one supplied Foundation profile."""

from __future__ import annotations

import json
import sqlite3
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from .artifact_content import ArtifactContent, ArtifactRef, canonical_artifact_json
from .binding_contracts import (
    make_binding_clock_policy, make_evidence_source_binding_timeline,
    resolve_authoritative_binding, validate_binding_clock_pair,
)
from .config import BUSY_TIMEOUT_MS
from .foundation_admission_artifacts import make_origin_runtime_admission
from .foundation_schema_artifacts import validate_foundation_payload
from .health_retention_contract import make_task01_health_retention_contract
from .models import DeviceFingerprintStorageUnavailable, DeviceFingerprintValidationError
from .payload_integrity import verify_persisted_payload
from .read_service import DeviceFingerprintReadService
from .runtime_profile_artifacts import make_foundation_runtime_profile
from .schema_registry import EvidenceSchemaRegistry, build_production_schema_registry
from .snapshot_artifacts import make_evidence_snapshot_content, make_snapshot_record
from .source_health_emitter_contracts import make_source_health_emitter_contract
from .source_health_policy import make_source_health_policy
from .ttl_capture_placement_proof import make_ttl_capture_placement_proof
from .validation import format_utc, parse_utc, validate_mac, validate_site_id

_SOURCE_ORIGIN = {
    "dhcp": "dhcp", "portal_headers": "portal", "tcp_syn": "tcp",
    "tls_client": "tls", "quic_client": "quic",
}
_EVIDENCE_FIELDS = (
    "evidence_id", "ingest_sequence", "producer_id", "source_kind", "source_subtype",
    "capture_source_id", "extractor_name", "extractor_version", "feature_schema_version",
    "rule_version", "site_id", "observed_at", "ingested_at", "observed_mac",
    "privacy_class", "quality_state", "payload_sha256",
)
_HEALTH_FIELDS = (
    "source_health_id", "ingest_sequence", "producer_id", "source_kind",
    "capture_source_id", "status", "reason_code", "observed_at", "ingested_at",
    "content_sha256",
)
_CONTENT_POLICY_FIELDS = frozenset({
    "snapshot_content_policy_version", "max_authorized_evidence_rows",
    "max_authorized_health_rows", "max_verified_payload_bytes",
    "max_materialized_payload_bytes", "max_total_semantic_input_bytes",
})
_EXECUTION_POLICY_FIELDS = frozenset({
    "snapshot_execution_policy_version", "max_read_transaction_duration_ms",
    "sqlite_busy_timeout_ms", "max_retry_count", "process_memory_guard_bytes",
})


class SnapshotBuildError(RuntimeError):
    """Typed whole-snapshot failure; no successful artifacts escape this exception."""

    def __init__(self, reason_code: str):
        self.reason_code = reason_code
        super().__init__(reason_code)


@dataclass(frozen=True, slots=True)
class MaterializedEvidenceEntry:
    descriptor: Mapping[str, Any]
    normalized_payload: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class EvidenceSnapshotMaterialization:
    evidence_snapshot_content: ArtifactRef
    ordered_entries: tuple[MaterializedEvidenceEntry, ...]


@dataclass(frozen=True, slots=True)
class SnapshotBuildResult:
    evidence_snapshot_content: ArtifactContent
    materialization: EvidenceSnapshotMaterialization
    snapshot_record: ArtifactContent


def _ref(content: ArtifactContent) -> dict[str, str]:
    return ArtifactRef(content.artifact_id, content.content_sha256).as_dict()


def _content_policy(content: ArtifactContent) -> dict[str, int]:
    if not isinstance(content, ArtifactContent) or content.artifact_type != "SnapshotContentPolicy":
        raise SnapshotBuildError("runtime_profile_incompatible")
    payload = content.semantic_payload
    if (set(payload) != _CONTENT_POLICY_FIELDS or payload["snapshot_content_policy_version"] != 1
            or any(type(value) is not int or not 1 <= value <= 2**63 - 1
                   for value in payload.values())):
        raise SnapshotBuildError("runtime_profile_incompatible")
    return payload


def _is_sqlite_busy(error: BaseException) -> bool:
    """Recognize only SQLite BUSY/LOCKED, including Task-01's open-time wrapper."""
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, sqlite3.Error):
            code = getattr(current, "sqlite_errorcode", None)
            if type(code) is int:
                return (code & 0xFF) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
            message = str(current).lower()
            return message in (
                "database is locked", "database is busy", "database table is locked",
                "database schema is locked",
            )
        current = current.__cause__
    return False


def _execution_policy(content: ArtifactContent) -> dict[str, int]:
    if not isinstance(content, ArtifactContent) or content.artifact_type != "SnapshotExecutionPolicy":
        raise SnapshotBuildError("runtime_profile_incompatible")
    payload = content.semantic_payload
    if (set(payload) != _EXECUTION_POLICY_FIELDS or payload["snapshot_execution_policy_version"] != 1
            or any(type(value) is not int or value < 0 or value > 2**63 - 1
                   for value in payload.values())
            or payload["max_read_transaction_duration_ms"] == 0
            or payload["process_memory_guard_bytes"] == 0
            or payload["sqlite_busy_timeout_ms"] != BUSY_TIMEOUT_MS):
        raise SnapshotBuildError("runtime_profile_incompatible")
    return payload


class DeviceFingerprintSnapshotService:
    """Build one completed-window snapshot without rereading active control-plane state."""

    def __init__(
        self, read_service: DeviceFingerprintReadService, *,
        foundation_runtime_profile: ArtifactContent,
        artifact_resolver: Callable[[ArtifactRef], ArtifactContent],
        utc_clock: Callable[[], str] = lambda: format_utc(datetime.now(timezone.utc)),
        monotonic_clock: Callable[[], float] = time.monotonic,
        process_memory_guard: Callable[[int], bool] | None = None,
        page_size: int = 500,
    ) -> None:
        if not callable(getattr(read_service, "open_snapshot_read", None)) or not callable(artifact_resolver):
            raise SnapshotBuildError("runtime_profile_incompatible")
        if type(page_size) is not int or not 1 <= page_size <= 500:
            raise SnapshotBuildError("runtime_profile_incompatible")
        self._read_service = read_service
        self._profile = foundation_runtime_profile
        self._resolve = artifact_resolver
        self._utc_clock = utc_clock
        self._monotonic = monotonic_clock
        self._memory_guard = process_memory_guard
        self._page_size = page_size

    def _dependency(self, value: dict[str, str], kind: str) -> ArtifactContent:
        try:
            ref = ArtifactRef.from_dict(value)
            if not ref.artifact_id.startswith(f"{kind}:v1:sha256:"):
                raise DeviceFingerprintValidationError("Wrong Foundation dependency kind")
            content = self._resolve(ref)
            ref.resolve(content, kind)
            return content
        except (DeviceFingerprintValidationError, LookupError, KeyError, TypeError) as exc:
            raise SnapshotBuildError("runtime_profile_incompatible") from exc

    def _pinned_dependencies(self) -> dict[str, Any]:
        try:
            profile = make_foundation_runtime_profile(self._profile.semantic_payload)
            if profile != self._profile:
                raise DeviceFingerprintValidationError("Noncanonical Foundation profile")
            payload = profile.semantic_payload
            contents = {field: self._dependency(payload[field], kind) for field, kind in (
                ("evidence_source_binding_timeline", "EvidenceSourceBindingTimeline"),
                ("binding_clock_policy", "BindingClockPolicy"),
                ("source_health_policy", "SourceHealthPolicy"),
                ("snapshot_content_policy", "SnapshotContentPolicy"),
                ("snapshot_execution_policy", "SnapshotExecutionPolicy"),
                ("evidence_schema_registry_contract", "EvidenceSchemaRegistryContract"),
                ("task01_health_retention_contract", "Task01HealthRetentionContract"),
                ("origin_runtime_admission", "OriginRuntimeAdmission"),
            )}
            emitters = [self._dependency(ref, "SourceHealthEmitterContract")
                        for ref in payload["source_health_emitter_contracts"]]
            if len({item.artifact_id for item in emitters}) != len(emitters):
                raise DeviceFingerprintValidationError("Duplicate Foundation emitter")
            if (make_evidence_source_binding_timeline(
                    contents["evidence_source_binding_timeline"].semantic_payload, emitters)
                    != contents["evidence_source_binding_timeline"]
                    or make_binding_clock_policy(contents["binding_clock_policy"].semantic_payload)
                    != contents["binding_clock_policy"]):
                raise DeviceFingerprintValidationError("Invalid binding contract")
            validate_binding_clock_pair(contents["evidence_source_binding_timeline"],
                                        contents["binding_clock_policy"])
            for emitter in emitters:
                if make_source_health_emitter_contract(emitter.semantic_payload) != emitter:
                    raise DeviceFingerprintValidationError("Invalid emitter contract")
            if make_source_health_policy(contents["source_health_policy"].semantic_payload, emitters) != contents[
                    "source_health_policy"]:
                raise DeviceFingerprintValidationError("Invalid source-health policy")
            retention_payload = contents["task01_health_retention_contract"].semantic_payload
            if make_task01_health_retention_contract(
                    contents["source_health_policy"],
                    retained_evidence_horizon_seconds=retention_payload["retained_evidence_horizon_seconds"],
                    retained_health_horizon_seconds=retention_payload["retained_health_horizon_seconds"],
            ) != contents["task01_health_retention_contract"]:
                raise DeviceFingerprintValidationError("Invalid health retention")
            if validate_foundation_payload(
                    "EvidenceSchemaRegistryContract",
                    contents["evidence_schema_registry_contract"].semantic_payload,
            ) != contents["evidence_schema_registry_contract"]:
                raise DeviceFingerprintValidationError("Invalid schema registry")
            origin = contents["origin_runtime_admission"]
            if make_origin_runtime_admission(origin.semantic_payload) != origin:
                raise DeviceFingerprintValidationError("Invalid OriginRuntimeAdmission")
            proof_ref = payload["ttl_capture_placement_proof"]
            if origin.semantic_payload["ttl_capture_placement_proof"] != proof_ref:
                raise DeviceFingerprintValidationError("Origin/TTL profile mismatch")
            if proof_ref is not None:
                proof = self._dependency(proof_ref, "TTLCapturePlacementProof")
                if make_ttl_capture_placement_proof(proof.semantic_payload) != proof:
                    raise DeviceFingerprintValidationError("Invalid TTL proof")
                contents["ttl_capture_placement_proof"] = proof
            elif origin.semantic_payload["tcp_state"] == "ENABLED":
                raise DeviceFingerprintValidationError("Enabled TCP without TTL proof")
            contents["content_limits"] = _content_policy(contents["snapshot_content_policy"])
            contents["execution_limits"] = _execution_policy(contents["snapshot_execution_policy"])
            contents["profile"] = profile
            contents["registry"] = build_production_schema_registry()
            return contents
        except SnapshotBuildError:
            raise
        except (DeviceFingerprintValidationError, KeyError, TypeError, AttributeError) as exc:
            raise SnapshotBuildError("runtime_profile_incompatible") from exc

    @staticmethod
    def _binding_epochs(timeline: ArtifactContent, site_id: str,
                        start: str, end: str) -> list[dict[str, Any]]:
        window_start, window_end = parse_utc(start), parse_utc(end)
        selected = []
        for epoch in timeline.semantic_payload["binding_epochs"]:
            if epoch["site_id"] != site_id:
                continue
            epoch_start = parse_utc(epoch["effective_from_utc"])
            epoch_end = (parse_utc(epoch["effective_to_utc"])
                         if epoch["effective_to_utc"] is not None else None)
            if epoch_start < window_end and (epoch_end is None or window_start < epoch_end):
                selected.append(epoch)
        if not selected:
            raise SnapshotBuildError("binding_unavailable")
        return selected

    @staticmethod
    def _authority(row: Mapping[str, Any], timeline: ArtifactContent,
                   clock: ArtifactContent) -> tuple[dict[str, Any] | None, str | None]:
        source_kind = row["source_kind"]
        origin = _SOURCE_ORIGIN.get(source_kind)
        if origin is None:
            return None, "binding_scope_mismatch"
        result = resolve_authoritative_binding(
            timeline, clock, row["site_id"], origin, source_kind, row["observed_at"])
        if result["status"] == "CUTOVER_AMBIGUOUS":
            return None, "binding_cutover_ambiguous"
        epoch = result["binding_epoch"]
        if (result["status"] != "AUTHORIZED" or epoch is None
                or row["producer_id"] != epoch["producer_id"]
                or row["capture_source_id"] != epoch["capture_source_id"]):
            return None, "binding_scope_mismatch"
        return epoch, None

    @staticmethod
    def _check_limit(value: int, limit: int) -> None:
        if value > limit:
            raise SnapshotBuildError("resource_limited")

    def _build_once(self, site_id: str, observed_mac: str, start: str, end: str,
                    dependencies: dict[str, Any], captured_at: str) -> SnapshotBuildResult:
        profile = dependencies["profile"]
        timeline = dependencies["evidence_source_binding_timeline"]
        clock = dependencies["binding_clock_policy"]
        limits = dependencies["content_limits"]
        execution = dependencies["execution_limits"]
        elapsed_start = self._monotonic()

        def operational_guard() -> None:
            if (self._monotonic() - elapsed_start) * 1000 > execution["max_read_transaction_duration_ms"]:
                raise SnapshotBuildError("snapshot_timeout")
            if self._memory_guard is None:
                raise SnapshotBuildError("snapshot_memory_guard_unavailable")
            if self._memory_guard(execution["process_memory_guard_bytes"]) is not True:
                raise SnapshotBuildError("snapshot_memory_pressure")

        operational_guard()
        bindings = self._binding_epochs(timeline, site_id, start, end)
        binding_ids = {item["binding_epoch_id"] for item in bindings}
        evidence: list[dict[str, Any]] = []
        health: list[dict[str, Any]] = []
        normalized_by_id: dict[str, Mapping[str, Any]] = {}
        anomalies: Counter[str] = Counter()
        verified_bytes = materialized_bytes = 0
        generic_only_registry = EvidenceSchemaRegistry().freeze()
        registry = dependencies["registry"]
        scopes = sorted({(item["producer_id"], item["capture_source_id"], item["source_kind"])
                         for item in bindings})
        with self._read_service.open_snapshot_read() as session:
            watermark = session.watermark
            cursor = None
            seen_cursors: set[tuple[str, str]] = set()
            while True:
                operational_guard()
                page = session.list_evidence(
                    site_id, observed_mac, start, end, limit=self._page_size, cursor=cursor)
                for row in page["items"]:
                    if (row["site_id"] != site_id or row["observed_mac"] != observed_mac
                            or row["ingest_sequence"] > watermark.max_committed_ingest_sequence):
                        anomalies["binding_scope_mismatch"] += 1
                        continue
                    epoch, anomaly = self._authority(row, timeline, clock)
                    if epoch is None or epoch["binding_epoch_id"] not in binding_ids:
                        anomalies[anomaly or "binding_scope_mismatch"] += 1
                        continue
                    descriptor = {field: row[field] for field in _EVIDENCE_FIELDS}
                    descriptor["binding_epoch_id"] = epoch["binding_epoch_id"]
                    evidence.append(descriptor)
                    self._check_limit(len(evidence), limits["max_authorized_evidence_rows"])
                    try:
                        verified = verify_persisted_payload(
                            row["source_kind"], row["feature_schema_version"],
                            row["payload_json"], row["payload_sha256"], generic_only_registry)
                    except DeviceFingerprintValidationError as exc:
                        reason = ("payload_hash_mismatch" if "digest mismatch" in str(exc)
                                  else "corrupt_payload")
                        raise SnapshotBuildError(reason) from exc
                    verified_bytes += verified.verified_payload_bytes
                    self._check_limit(verified_bytes, limits["max_verified_payload_bytes"])
                    if registry.supports(row["source_kind"], row["feature_schema_version"]):
                        try:
                            normalized = registry.validate(
                                row["source_kind"], row["feature_schema_version"],
                                json.loads(row["payload_json"]))
                        except DeviceFingerprintValidationError as exc:
                            raise SnapshotBuildError("schema_validation_failure") from exc
                        normalized_by_id[row["evidence_id"]] = dict(normalized)
                        materialized_bytes += verified.verified_payload_bytes
                        self._check_limit(materialized_bytes, limits["max_materialized_payload_bytes"])
                next_cursor = page["next_cursor"]
                if next_cursor is None:
                    break
                if next_cursor in seen_cursors:
                    raise SnapshotBuildError("retryable_sqlite_busy")
                seen_cursors.add(next_cursor)
                cursor = next_cursor
            anchor_rows: list[tuple[dict[str, Any], str]] = []
            for epoch in bindings:
                operational_guard()
                segment_start = format_utc(max(
                    parse_utc(start), parse_utc(epoch["effective_from_utc"])))
                anchor = session.latest_source_health(
                    site_id, epoch["producer_id"], epoch["capture_source_id"],
                    epoch["source_kind"], through_utc=segment_start)
                if anchor is not None:
                    anchor_rows.append((anchor, epoch["binding_epoch_id"]))
            ordinary_rows: list[dict[str, Any]] = []
            for producer, capture, source in scopes:
                operational_guard()
                cursor = None
                seen_cursors = set()
                while True:
                    operational_guard()
                    page = session.list_source_health(
                        site_id, producer, capture, source, start, end,
                        limit=self._page_size, cursor=cursor)
                    ordinary_rows.extend(page["items"])
                    next_cursor = page["next_cursor"]
                    if next_cursor is None:
                        break
                    if next_cursor in seen_cursors:
                        raise SnapshotBuildError("retryable_sqlite_busy")
                    seen_cursors.add(next_cursor)
                    cursor = next_cursor
            seen_health_rows: dict[str, tuple[Any, ...]] = {}
            included_health_ids: set[str] = set()
            for row, target_epoch_id in (
                    [(anchor, epoch_id) for anchor, epoch_id in anchor_rows]
                    + [(row, None) for row in ordinary_rows]):
                identity = tuple(row[field] for field in (*_HEALTH_FIELDS, "site_id"))
                health_id = row["source_health_id"]
                previous = seen_health_rows.setdefault(health_id, identity)
                if previous != identity:
                    raise SnapshotBuildError("corrupt_source_health")
                if (row["site_id"] != site_id
                        or row["ingest_sequence"] > watermark.max_committed_ingest_sequence):
                    if target_epoch_id is None:
                        anomalies["binding_scope_mismatch"] += 1
                    continue
                epoch, anomaly = self._authority(row, timeline, clock)
                if (epoch is None or epoch["binding_epoch_id"] not in binding_ids
                        or (target_epoch_id is not None
                            and epoch["binding_epoch_id"] != target_epoch_id)):
                    if target_epoch_id is None:
                        anomalies[anomaly or "binding_scope_mismatch"] += 1
                    continue
                if health_id in included_health_ids:
                    continue
                included_health_ids.add(health_id)
                descriptor = {field: row[field] for field in _HEALTH_FIELDS}
                descriptor["binding_epoch_id"] = epoch["binding_epoch_id"]
                health.append(descriptor)
                self._check_limit(len(health), limits["max_authorized_health_rows"])
            operational_guard()
            origin = dependencies["origin_runtime_admission"]
            origin_payload = origin.semantic_payload
            semantic_refs = {
                "evidence_source_binding_timeline": _ref(timeline),
                "binding_clock_policy": _ref(clock),
                "evidence_schema_registry_contract": _ref(
                    dependencies["evidence_schema_registry_contract"]),
                "origin_runtime_admission": {
                    "artifact_id": origin.artifact_id, "content_sha256": origin.content_sha256,
                    "tcp_state": origin_payload["tcp_state"],
                    "tcp_reason_code": origin_payload["tcp_reason_code"],
                    "ttl_capture_placement_proof": origin_payload["ttl_capture_placement_proof"],
                },
                "classification_foundation_valid_from_utc": profile.semantic_payload[
                    "classification_foundation_valid_from_utc"],
            }
            content = make_evidence_snapshot_content({
                "snapshot_contract_version": profile.semantic_payload["snapshot_contract_version"],
                "site_id": site_id, "observed_mac": observed_mac,
                "window_start_utc": start, "window_end_utc": end,
                "database_generation_id": watermark.database_generation_id,
                "max_committed_ingest_sequence": watermark.max_committed_ingest_sequence,
                **semantic_refs,
                "binding_epoch_descriptors": bindings,
                "evidence_descriptors": evidence,
                "source_health_descriptors": health,
            }, foundation_runtime_profile=profile, binding_timeline=timeline,
                binding_clock_policy=clock,
                schema_registry_contract=dependencies["evidence_schema_registry_contract"],
                origin_runtime_admission=origin)
            content_payload = content.semantic_payload
            ordered_evidence = content_payload["evidence_descriptors"]
            ordered_health = content_payload["source_health_descriptors"]
            ordered_bindings = content_payload["binding_epoch_descriptors"]
            total_bytes = (
                verified_bytes + materialized_bytes
                + sum(len(canonical_artifact_json(row)) for row in ordered_evidence)
                + sum(len(canonical_artifact_json(row)) for row in ordered_health)
                + sum(len(canonical_artifact_json(row)) for row in ordered_bindings)
                + len(canonical_artifact_json(semantic_refs))
            )
            self._check_limit(total_bytes, limits["max_total_semantic_input_bytes"])
            entries = tuple(MaterializedEvidenceEntry(
                descriptor=row, normalized_payload=normalized_by_id[row["evidence_id"]])
                for row in ordered_evidence if row["evidence_id"] in normalized_by_id)
            materialization = EvidenceSnapshotMaterialization(
                ArtifactRef(content.artifact_id, content.content_sha256), entries)
            record = make_snapshot_record({
                "evidence_snapshot_content": _ref(content),
                "foundation_runtime_profile": _ref(profile),
                "snapshot_captured_at_utc": captured_at,
                "snapshot_content_policy": _ref(dependencies["snapshot_content_policy"]),
                "snapshot_execution_policy": _ref(dependencies["snapshot_execution_policy"]),
                "verified_evidence_row_count": len(ordered_evidence),
                "verified_payload_bytes": verified_bytes,
                "materialized_evidence_row_count": len(entries),
                "materialized_payload_bytes": materialized_bytes,
                "total_semantic_input_bytes": total_bytes,
                "scope_anomaly_count": sum(anomalies.values()),
                "scope_anomaly_reason_counts": [
                    {"reason_code": reason, "count": count} for reason, count in sorted(anomalies.items())],
                "build_outcome": "success",
            }, evidence_snapshot_content=content, foundation_runtime_profile=profile,
                snapshot_content_policy=dependencies["snapshot_content_policy"],
                snapshot_execution_policy=dependencies["snapshot_execution_policy"])
            operational_guard()
            return SnapshotBuildResult(content, materialization, record)

    def build(self, site_id: str, observed_mac: str, window_start_utc: str,
              window_end_utc: str) -> SnapshotBuildResult:
        """One complete successful attempt uses exactly one Task-01 snapshot session."""
        try:
            site_id = validate_site_id(site_id)
            mac = validate_mac(observed_mac)
            if mac != observed_mac:
                raise DeviceFingerprintValidationError("Noncanonical observed MAC")
            start, end = parse_utc(window_start_utc), parse_utc(window_end_utc)
        except DeviceFingerprintValidationError as exc:
            raise SnapshotBuildError("invalid_window") from exc
        dependencies = self._pinned_dependencies()
        if start >= end or start < parse_utc(dependencies["profile"].semantic_payload[
                "classification_foundation_valid_from_utc"]):
            raise SnapshotBuildError("invalid_window")
        execution = dependencies["execution_limits"]
        for attempt in range(execution["max_retry_count"] + 1):
            captured_at = self._utc_clock()
            if end > parse_utc(captured_at):
                raise SnapshotBuildError("invalid_window")
            try:
                return self._build_once(site_id, mac, window_start_utc, window_end_utc,
                                        dependencies, captured_at)
            except (sqlite3.DatabaseError, DeviceFingerprintStorageUnavailable) as exc:
                if not _is_sqlite_busy(exc):
                    raise SnapshotBuildError("storage_unavailable") from exc
                if attempt == execution["max_retry_count"]:
                    raise SnapshotBuildError("retryable_sqlite_busy") from exc
            except DeviceFingerprintValidationError as exc:
                raise SnapshotBuildError("runtime_profile_incompatible") from exc
        raise SnapshotBuildError("retryable_sqlite_busy")
