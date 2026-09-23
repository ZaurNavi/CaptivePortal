"""Closed R14 runtime-profile and activation-lineage ArtifactContent contracts."""

from __future__ import annotations

import re
from typing import Any

from .artifact_content import ArtifactContent, ArtifactRef, canonical_set, make_artifact_content
from .models import DeviceFingerprintValidationError
from .validation import parse_utc

_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
_GIT = re.compile(r"[0-9a-f]{40}")
_KINDS = {"foundation": "FoundationRuntimeProfile", "classification": "ClassificationRuntimeProfile"}
UPDATE_CLASSES = frozenset({
    "INITIAL_FOUNDATION", "INITIAL_CLASSIFICATION", "KNOWLEDGE_BUNDLE_REFRESH",
    "KNOWLEDGE_FRESHNESS_POLICY_CHANGE", "BINDING_TIMELINE_CHANGE",
    "CAPTURE_TOPOLOGY_CHANGE", "SOURCE_HEALTH_EMITTER_CHANGE",
    "SOURCE_HEALTH_POLICY_CHANGE", "SNAPSHOT_CONTENT_POLICY_CHANGE",
    "SNAPSHOT_EXECUTION_POLICY_CHANGE", "EVIDENCE_SCHEMA_CHANGE",
    "EVIDENCE_ADAPTER_CHANGE", "EVIDENCE_ADAPTER_AND_CLASSIFICATION_POLICY_CHANGE",
    "CLASSIFICATION_POLICY_CHANGE", "CLASSIFIER_ARTIFACT_CHANGE",
    "FOUNDATION_VALID_FROM_LATER", "ROLLBACK_REACTIVATION",
})
_FOUNDATION_REFS = {
    "evidence_source_binding_timeline": "EvidenceSourceBindingTimeline",
    "binding_clock_policy": "BindingClockPolicy",
    "source_health_policy": "SourceHealthPolicy",
    "snapshot_content_policy": "SnapshotContentPolicy",
    "snapshot_execution_policy": "SnapshotExecutionPolicy",
    "evidence_schema_registry_contract": "EvidenceSchemaRegistryContract",
    "task01_health_retention_contract": "Task01HealthRetentionContract",
    "origin_runtime_admission": "OriginRuntimeAdmission",
}
_CLASSIFICATION_REFS = {
    "foundation_runtime_profile": "FoundationRuntimeProfile",
    "knowledge_bundle": "KnowledgeBundle",
    "classification_policy": "ClassificationPolicy",
    "evidence_adapter_contract_set": "EvidenceAdapterContractSet",
    "classifier_artifact_manifest": "ClassifierArtifactManifest",
}
_FOUNDATION_FIELDS = frozenset({
    "foundation_profile_contract_version", "classification_foundation_valid_from_utc",
    "source_health_emitter_contracts", "ttl_capture_placement_proof", "snapshot_contract_version",
    *_FOUNDATION_REFS,
})
_CLASSIFICATION_FIELDS = frozenset({"classification_runtime_profile_contract_version", *_CLASSIFICATION_REFS})
_ADMISSION_FIELDS = frozenset({
    "runtime_profile_admission_contract_version", "profile_kind", "candidate_profile",
    "previous_active_profile", "expected_previous_activation_record_id",
    "expected_previous_activation_generation_id", "update_class", "prerequisite_gate_results",
    "compatibility_validation_result", "candidate_repository_commit_sha",
    "candidate_repository_tree_sha", "foundation_admission_manifest",
    "task04_acceptance_manifest", "foundation_runtime_profile_admission_manifest",
})
_ACTIVATION_FIELDS = frozenset({
    "activation_contract_version", "activation_record_id", "profile_kind", "runtime_profile_id",
    "runtime_profile_digest", "runtime_profile_admission_manifest_id",
    "runtime_profile_admission_manifest_digest", "previous_activation_record_id",
    "previous_active_profile_id", "previous_active_profile_digest", "activated_at_utc",
    "activation_reason_update_class", "activation_result", "activation_generation_id",
})
_VALIDITY_FIELDS = frozenset({
    "runtime_profile_validity_contract_version", "validity_record_id", "profile_kind",
    "runtime_profile_id", "runtime_profile_digest", "activation_record_id", "state",
    "reason_code", "effective_at_utc", "inflight_commit_rule", "previous_validity_record_id",
})


def _fail(label: str) -> None:
    raise DeviceFingerprintValidationError(f"Invalid {label}")


def _shape(payload: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != fields:
        _fail(label)
    return payload


def _positive(value: Any, label: str) -> int:
    if type(value) is not int or not 1 <= value <= 2_147_483_647:
        _fail(label)
    return value


def _match(value: Any, pattern: re.Pattern[str], label: str, *, nullable: bool = False) -> Any:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        _fail(label)
    return value


def _kind(value: Any) -> str:
    if not isinstance(value, str) or value not in _KINDS:
        _fail("profile kind")
    return value


def _ref(value: Any, target: str, *, nullable: bool = False) -> dict[str, str] | None:
    if value is None and nullable:
        return None
    ref = ArtifactRef.from_dict(value)
    if not ref.artifact_id.startswith(f"{target}:v1:sha256:"):
        _fail(f"{target} reference")
    return ref.as_dict()


def _ref_pair(artifact_id: Any, digest: Any, target: str, *, nullable: bool = False) -> None:
    if artifact_id is None and digest is None and nullable:
        return
    _ref({"artifact_id": artifact_id, "content_sha256": digest}, target)


def _refs(values: Any, target: str) -> list[dict[str, str]]:
    if not isinstance(values, list):
        _fail(f"{target} references")
    return canonical_set([_ref(value, target) for value in values], lambda ref: ref["artifact_id"])


def make_foundation_runtime_profile(payload: dict[str, Any]) -> ArtifactContent:
    value = _shape(payload, _FOUNDATION_FIELDS, "FoundationRuntimeProfile shape")
    _positive(value["foundation_profile_contract_version"], "foundation profile version")
    _positive(value["snapshot_contract_version"], "snapshot contract version")
    parse_utc(value["classification_foundation_valid_from_utc"])
    normalized = dict(value)
    for field, target in _FOUNDATION_REFS.items():
        normalized[field] = _ref(value[field], target)
    normalized["source_health_emitter_contracts"] = _refs(
        value["source_health_emitter_contracts"], "SourceHealthEmitterContract")
    normalized["ttl_capture_placement_proof"] = _ref(
        value["ttl_capture_placement_proof"], "TTLCapturePlacementProof", nullable=True)
    return make_artifact_content("FoundationRuntimeProfile", normalized)


def make_classification_runtime_profile(payload: dict[str, Any]) -> ArtifactContent:
    value = _shape(payload, _CLASSIFICATION_FIELDS, "ClassificationRuntimeProfile shape")
    _positive(value["classification_runtime_profile_contract_version"], "classification profile version")
    normalized = dict(value)
    for field, target in _CLASSIFICATION_REFS.items():
        normalized[field] = _ref(value[field], target)
    return make_artifact_content("ClassificationRuntimeProfile", normalized)


def make_runtime_profile_admission_manifest(payload: dict[str, Any]) -> ArtifactContent:
    value = _shape(payload, _ADMISSION_FIELDS, "RuntimeProfileAdmissionManifest shape")
    _positive(value["runtime_profile_admission_contract_version"], "admission version")
    kind = _kind(value["profile_kind"])
    normalized = dict(value)
    normalized["candidate_profile"] = _ref(value["candidate_profile"], _KINDS[kind])
    normalized["previous_active_profile"] = _ref(
        value["previous_active_profile"], _KINDS[kind], nullable=True)
    for field in ("expected_previous_activation_record_id", "expected_previous_activation_generation_id"):
        _match(value[field], _UUID, field, nullable=True)
    update = value["update_class"]
    if not isinstance(update, str) or update not in UPDATE_CLASSES:
        _fail("update class")
    initial = update in {"INITIAL_FOUNDATION", "INITIAL_CLASSIFICATION"}
    if initial:
        if update != f"INITIAL_{kind.upper()}" or any(value[field] is not None for field in (
                "previous_active_profile", "expected_previous_activation_record_id",
                "expected_previous_activation_generation_id")):
            _fail("initial predecessor")
    elif any(value[field] is None for field in (
            "previous_active_profile", "expected_previous_activation_record_id",
            "expected_previous_activation_generation_id")):
        _fail("non-initial predecessor")
    normalized["prerequisite_gate_results"] = _refs(value["prerequisite_gate_results"], "GateResultManifest")
    if value["compatibility_validation_result"] != "PASS":
        _fail("compatibility result")
    for field in ("candidate_repository_commit_sha", "candidate_repository_tree_sha"):
        _match(value[field], _GIT, field)
    normalized["foundation_admission_manifest"] = _ref(
        value["foundation_admission_manifest"], "FoundationAdmissionManifest")
    normalized["task04_acceptance_manifest"] = _ref(
        value["task04_acceptance_manifest"], "Task04AcceptanceManifest", nullable=True)
    normalized["foundation_runtime_profile_admission_manifest"] = _ref(
        value["foundation_runtime_profile_admission_manifest"], "RuntimeProfileAdmissionManifest", nullable=True)
    if kind == "foundation" and (normalized["task04_acceptance_manifest"] is not None
                                 or normalized["foundation_runtime_profile_admission_manifest"] is not None):
        _fail("foundation admission lineage")
    if kind == "classification" and (normalized["task04_acceptance_manifest"] is None
                                     or normalized["foundation_runtime_profile_admission_manifest"] is None):
        _fail("classification admission lineage")
    return make_artifact_content("RuntimeProfileAdmissionManifest", normalized)


def make_runtime_profile_activation_record(payload: dict[str, Any]) -> ArtifactContent:
    value = _shape(payload, _ACTIVATION_FIELDS, "RuntimeProfileActivationRecord shape")
    _positive(value["activation_contract_version"], "activation version")
    kind = _kind(value["profile_kind"])
    for field in ("activation_record_id", "activation_generation_id"):
        _match(value[field], _UUID, field)
    if value["activation_record_id"] == value["activation_generation_id"]:
        _fail("separate activation identities")
    _match(value["previous_activation_record_id"], _UUID, "previous activation", nullable=True)
    _ref_pair(value["runtime_profile_id"], value["runtime_profile_digest"], _KINDS[kind])
    _ref_pair(value["runtime_profile_admission_manifest_id"],
              value["runtime_profile_admission_manifest_digest"], "RuntimeProfileAdmissionManifest")
    _ref_pair(value["previous_active_profile_id"], value["previous_active_profile_digest"],
              _KINDS[kind], nullable=True)
    if (not isinstance(value["activation_reason_update_class"], str)
            or value["activation_reason_update_class"] not in UPDATE_CLASSES):
        _fail("activation update class")
    initial = value["activation_reason_update_class"] in {"INITIAL_FOUNDATION", "INITIAL_CLASSIFICATION"}
    if initial and (value["activation_reason_update_class"] != f"INITIAL_{kind.upper()}" or
                    value["previous_activation_record_id"] is not None or
                    value["previous_active_profile_id"] is not None):
        _fail("initial activation predecessor")
    if not initial and (value["previous_activation_record_id"] is None or
                        value["previous_active_profile_id"] is None):
        _fail("activation predecessor")
    if value["previous_activation_record_id"] == value["activation_record_id"]:
        _fail("self activation predecessor")
    if value["activation_result"] != "ACTIVE":
        _fail("activation result")
    parse_utc(value["activated_at_utc"])
    return make_artifact_content("RuntimeProfileActivationRecord", value)


def make_runtime_profile_validity_record(payload: dict[str, Any]) -> ArtifactContent:
    value = _shape(payload, _VALIDITY_FIELDS, "RuntimeProfileValidityRecord shape")
    _positive(value["runtime_profile_validity_contract_version"], "validity version")
    kind = _kind(value["profile_kind"])
    for field in ("validity_record_id", "activation_record_id"):
        _match(value[field], _UUID, field)
    if value["validity_record_id"] == value["activation_record_id"]:
        _fail("separate validity identity")
    _match(value["previous_validity_record_id"], _UUID, "previous validity", nullable=True)
    if value["previous_validity_record_id"] == value["validity_record_id"]:
        _fail("self validity predecessor")
    _ref_pair(value["runtime_profile_id"], value["runtime_profile_digest"], _KINDS[kind])
    permitted = {
        "ACTIVE": ({"ACTIVATED", "ROLLBACK_REACTIVATED"}, "ALLOW_PINNED_INFLIGHT"),
        "INACTIVE": ({"SUPERSEDED_SAFE"}, "ALLOW_PINNED_INFLIGHT"),
        "SUSPENDED_INVALIDATED": ({"TTL_CAPTURE_PROOF_INVALIDATED", "EXPLICIT_POLICY_SUSPEND",
                                   "PROFILE_COMPATIBILITY_INVALIDATED"}, "REJECT_PINNED_INFLIGHT"),
    }
    if not isinstance(value["state"], str) or value["state"] not in permitted:
        _fail("validity state")
    reasons, inflight = permitted[value["state"]]
    if value["reason_code"] not in reasons or value["inflight_commit_rule"] != inflight:
        _fail("validity state rule")
    parse_utc(value["effective_at_utc"])
    return make_artifact_content("RuntimeProfileValidityRecord", value)


def direct_artifact_refs(content: ArtifactContent) -> tuple[ArtifactRef, ...]:
    """Return only explicitly declared semantic ArtifactRefs in canonical order."""
    if not isinstance(content, ArtifactContent):
        _fail("artifact content")
    payload = content.semantic_payload
    refs: list[dict[str, str]] = []
    if content.artifact_type == "FoundationRuntimeProfile":
        make_foundation_runtime_profile(payload)
        refs.extend(payload[field] for field in _FOUNDATION_REFS)
        refs.extend(payload["source_health_emitter_contracts"])
        if payload["ttl_capture_placement_proof"] is not None:
            refs.append(payload["ttl_capture_placement_proof"])
    elif content.artifact_type == "ClassificationRuntimeProfile":
        make_classification_runtime_profile(payload)
        refs.extend(payload[field] for field in _CLASSIFICATION_REFS)
    elif content.artifact_type == "RuntimeProfileAdmissionManifest":
        make_runtime_profile_admission_manifest(payload)
        refs.extend([payload["candidate_profile"], payload["foundation_admission_manifest"]])
        refs.extend(payload["prerequisite_gate_results"])
        for field in ("previous_active_profile", "task04_acceptance_manifest",
                      "foundation_runtime_profile_admission_manifest"):
            if payload[field] is not None:
                refs.append(payload[field])
    else:
        return ()
    unique = {ref["artifact_id"]: ref for ref in refs}
    if len(unique) < len(refs) and any(
            ref != unique[ref["artifact_id"]] for ref in refs):
        _fail("conflicting artifact reference")
    ordered = canonical_set(list(unique.values()), lambda ref: ref["artifact_id"])
    return tuple(ArtifactRef.from_dict(ref) for ref in ordered)
