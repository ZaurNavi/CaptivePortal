"""Closed, purely semantic R14 ClassificationRequestManifest."""

from __future__ import annotations

from typing import Any

from .artifact_content import ArtifactContent, ArtifactRef, make_artifact_content
from .models import DeviceFingerprintValidationError
from .validation import parse_utc


_FIELDS = {
    "evidence_snapshot_content": "EvidenceSnapshotContent",
    "source_evaluability": "SourceEvaluability",
    "knowledge_bundle": "KnowledgeBundle",
    "classification_policy": "ClassificationPolicy",
    "evidence_adapter_contract_set": "EvidenceAdapterContractSet",
    "classifier_artifact_manifest": "ClassifierArtifactManifest",
}


def make_classification_request_manifest(
    payload: dict[str, Any], *,
    evidence_snapshot_content: ArtifactContent,
    source_evaluability: ArtifactContent,
    knowledge_bundle: ArtifactContent,
    classification_policy: ArtifactContent,
    evidence_adapter_contract_set: ArtifactContent,
    classifier_artifact_manifest: ArtifactContent,
) -> ArtifactContent:
    """Resolve every exact typed input; never incorporate execution lineage."""
    if not isinstance(payload, dict) or set(payload) != set(_FIELDS) | {"knowledge_evaluation_at_utc"}:
        raise DeviceFingerprintValidationError("Invalid ClassificationRequestManifest shape")
    supplied = locals()
    normalized: dict[str, Any] = {}
    for field, kind in _FIELDS.items():
        ref = ArtifactRef.from_dict(payload[field])
        ref.resolve(supplied[field], kind)
        normalized[field] = ref.as_dict()
    instant = payload["knowledge_evaluation_at_utc"]
    parse_utc(instant)
    normalized["knowledge_evaluation_at_utc"] = instant
    if source_evaluability.semantic_payload.get("evidence_snapshot_content") != normalized[
            "evidence_snapshot_content"]:
        raise DeviceFingerprintValidationError("SourceEvaluability/snapshot mismatch")
    if classification_policy.semantic_payload.get("evidence_adapter_contract_set") != normalized[
            "evidence_adapter_contract_set"]:
        raise DeviceFingerprintValidationError("ClassificationPolicy/adapter mismatch")
    return make_artifact_content("ClassificationRequestManifest", normalized)
