"""Final F-A4 policy and SNAPSHOT_PERFORMANCE artifact proofs."""

import hashlib
from dataclasses import replace

import pytest

from app.device_fingerprint.artifact_content import canonical_artifact_json
from app.device_fingerprint.models import DeviceFingerprintValidationError
from research.device_fingerprint_fa4.finalization import (
    CONTROLLED_COMPLETE_STRESS_REPORT_SHA256,
    PRODUCTION_COMPLETE_REPORT_SHA256,
    build_snapshot_content_policy,
    build_snapshot_execution_policy,
    build_snapshot_performance_gate_proof,
)
from research.device_fingerprint_fa4.semantic_accounting import (
    ACCEPTED_BINDING_CLOCK_POLICY_ID,
    ACCEPTED_BINDING_TIMELINE_ID,
    ACCEPTED_SCHEMA_REGISTRY_ID,
    ACCEPTED_TTL_PROOF_ID,
)

_CANDIDATE_COMMIT = "1" * 40
_CANDIDATE_TREE = "2" * 40


def _assert_identity_recomputes(content) -> None:
    digest = hashlib.sha256(content.digest_input_json).hexdigest()
    assert content.content_sha256 == digest
    assert content.artifact_id == f"{content.artifact_type}:v1:sha256:{digest}"


def test_final_snapshot_policies_are_exact_deterministic_and_recomputable():
    content_first = build_snapshot_content_policy()
    content_second = build_snapshot_content_policy()
    execution_first = build_snapshot_execution_policy()
    execution_second = build_snapshot_execution_policy()
    assert content_first == content_second
    assert execution_first == execution_second
    assert content_first.semantic_payload == {
        "snapshot_content_policy_version": 1,
        "max_authorized_evidence_rows": 40000,
        "max_authorized_health_rows": 10000,
        "max_verified_payload_bytes": 11720000,
        "max_materialized_payload_bytes": 11720000,
        "max_total_semantic_input_bytes": 52922790,
    }
    assert execution_first.semantic_payload == {
        "snapshot_execution_policy_version": 1,
        "max_read_transaction_duration_ms": 240000,
        "sqlite_busy_timeout_ms": 500,
        "max_retry_count": 0,
        "process_memory_guard_bytes": 100663296,
    }
    _assert_identity_recomputes(content_first)
    _assert_identity_recomputes(execution_first)


def test_snapshot_performance_proof_is_exact_deterministic_and_private():
    first = build_snapshot_performance_gate_proof(_CANDIDATE_COMMIT, _CANDIDATE_TREE)
    second = build_snapshot_performance_gate_proof(_CANDIDATE_COMMIT, _CANDIDATE_TREE)
    assert first == second
    payload = first.semantic_payload
    assert payload["proof_kind"] == "SNAPSHOT_PERFORMANCE"
    assert payload["source_gate_id"] == "F-A4"
    assert payload["candidate_repository_commit_sha"] == _CANDIDATE_COMMIT
    assert payload["candidate_repository_tree_sha"] == _CANDIDATE_TREE
    assert [ref["artifact_id"] for ref in payload["input_artifact_refs"]] == sorted([
        ACCEPTED_BINDING_TIMELINE_ID,
        ACCEPTED_BINDING_CLOCK_POLICY_ID,
        ACCEPTED_SCHEMA_REGISTRY_ID,
        ACCEPTED_TTL_PROOF_ID,
        build_snapshot_content_policy().artifact_id,
        build_snapshot_execution_policy().artifact_id,
    ])
    assert {
        (ref["evidence_label"], ref["file_sha256"])
        for ref in payload["retained_evidence_refs"]
    } == {
        (
            "fa4_production_complete_read_only_measurement",
            PRODUCTION_COMPLETE_REPORT_SHA256,
        ),
        (
            "fa4_controlled_complete_disposable_stress",
            CONTROLLED_COMPLETE_STRESS_REPORT_SHA256,
        ),
    }
    serialized = canonical_artifact_json(payload)
    for forbidden in (
        b"observed_mac", b"observed_ip", b"payload_json", b"User-Agent",
        b"Sec-CH-UA", b"Bearer", b"Authorization",
    ):
        assert forbidden not in serialized
    _assert_identity_recomputes(first)


@pytest.mark.parametrize("candidate", ["", "A" * 40, "0" * 39, None])
def test_snapshot_performance_proof_rejects_invalid_candidate_identity(candidate):
    with pytest.raises(DeviceFingerprintValidationError, match="Git identity"):
        build_snapshot_performance_gate_proof(candidate, _CANDIDATE_TREE)


def test_tampered_artifact_identity_fails_closed():
    content = build_snapshot_content_policy()
    with pytest.raises(DeviceFingerprintValidationError, match="identity mismatch"):
        replace(content, content_sha256="0" * 64)
