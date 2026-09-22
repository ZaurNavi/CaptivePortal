"""Exact R14 GateResultManifest V1 ArtifactContent validation."""

from __future__ import annotations

import re
from typing import Any

from .artifact_content import ArtifactContent, ArtifactRef, canonical_set, make_artifact_content
from .models import DeviceFingerprintValidationError
from .validation import parse_utc

_GIT_SHA = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_UUID_V4 = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
_FIELDS = frozenset({
    "gate_id", "gate_contract_version", "status",
    "candidate_repository_commit_sha", "candidate_repository_tree_sha",
    "input_artifact_refs", "output_artifact_refs", "retained_evidence_refs",
    "proof_execution_identity", "trusted_time_inputs", "decision_record_refs",
})
_PROOF_FIELDS = frozenset({
    "execution_id", "executor_kind", "repository_commit_sha",
    "repository_tree_sha", "procedure_or_test_suite_id", "environment_identity",
    "execution_artifact_sha256",
})
_EVIDENCE_FIELDS = frozenset({
    "evidence_label", "file_sha256", "media_type", "path_or_reference",
})
_TIME_FIELDS = frozenset({
    "foundation_knowledge_evaluation_at_utc",
    "foundation_admission_evaluation_at_utc", "knowledge_evaluation_at_utc",
})


def _fail(message: str) -> None:
    raise DeviceFingerprintValidationError(message)


def _shape(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        _fail(f"Invalid {label} shape")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(f"Invalid {label}")
    return value


def _nullable_match(value: Any, pattern: re.Pattern[str], label: str) -> Any:
    if value is not None and (not isinstance(value, str) or pattern.fullmatch(value) is None):
        _fail(f"Invalid {label}")
    return value


def _refs(value: Any, label: str) -> list[dict[str, str]]:
    if not isinstance(value, list):
        _fail(f"Invalid {label}")
    return canonical_set([ArtifactRef.from_dict(ref).as_dict() for ref in value],
                         lambda ref: ref["artifact_id"])


def make_gate_result_manifest(payload: dict[str, Any]) -> ArtifactContent:
    """Materialize the closed generic V1 gate-result schema and ordered SETs."""
    value = _shape(payload, _FIELDS, "GateResultManifest")
    _text(value["gate_id"], "gate ID")
    _text(value["gate_contract_version"], "gate contract version")
    if value["status"] not in ("PASS", "FAIL"):
        _fail("Invalid gate status")
    _nullable_match(value["candidate_repository_commit_sha"], _GIT_SHA, "candidate commit")
    _nullable_match(value["candidate_repository_tree_sha"], _GIT_SHA, "candidate tree")
    inputs = _refs(value["input_artifact_refs"], "gate input refs")
    outputs = _refs(value["output_artifact_refs"], "gate output refs")
    evidence = value["retained_evidence_refs"]
    if not isinstance(evidence, list):
        _fail("Invalid retained evidence refs")
    normalized_evidence = []
    for raw in evidence:
        ref = dict(_shape(raw, _EVIDENCE_FIELDS, "retained evidence ref"))
        _text(ref["evidence_label"], "evidence label")
        _nullable_match(ref["file_sha256"], _SHA256, "evidence SHA256")
        if ref["file_sha256"] is None:
            _fail("Missing evidence SHA256")
        _text(ref["media_type"], "evidence media type")
        if ref["path_or_reference"] is not None:
            _text(ref["path_or_reference"], "evidence path or reference")
        normalized_evidence.append(ref)
    normalized_evidence = canonical_set(
        normalized_evidence, lambda ref: (ref["evidence_label"], ref["file_sha256"]),
    )
    proof = dict(_shape(value["proof_execution_identity"], _PROOF_FIELDS,
                        "proof execution identity"))
    _nullable_match(proof["execution_id"], _UUID_V4, "execution UUIDv4")
    if proof["execution_id"] is None:
        _fail("Missing execution UUIDv4")
    for key in ("executor_kind", "procedure_or_test_suite_id", "environment_identity"):
        _text(proof[key], key)
    for key in ("repository_commit_sha", "repository_tree_sha"):
        _nullable_match(proof[key], _GIT_SHA, key)
    _nullable_match(proof["execution_artifact_sha256"], _SHA256, "execution artifact SHA256")
    times = dict(_shape(value["trusted_time_inputs"], _TIME_FIELDS, "trusted time inputs"))
    for timestamp in times.values():
        if timestamp is not None:
            parse_utc(timestamp)
    decisions = value["decision_record_refs"]
    if not isinstance(decisions, list):
        _fail("Invalid decision record refs")
    for decision in decisions:
        if not isinstance(decision, str) or _UUID_V4.fullmatch(decision) is None:
            _fail("Invalid decision UUIDv4")
    decisions = canonical_set(decisions, lambda decision: decision)
    return make_artifact_content("GateResultManifest", {
        **value,
        "input_artifact_refs": inputs, "output_artifact_refs": outputs,
        "retained_evidence_refs": normalized_evidence,
        "proof_execution_identity": proof, "trusted_time_inputs": times,
        "decision_record_refs": decisions,
    })
