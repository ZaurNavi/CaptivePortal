"""Final immutable F-A4 policy and SNAPSHOT_PERFORMANCE proof artifacts."""

from __future__ import annotations

import re
import uuid
from typing import Any

from app.device_fingerprint.artifact_content import (
    ArtifactContent,
    ArtifactRef,
    canonical_set,
    make_artifact_content,
)
from app.device_fingerprint.models import DeviceFingerprintValidationError

from .semantic_accounting import (
    ACCEPTED_BINDING_CLOCK_POLICY_ID,
    ACCEPTED_BINDING_TIMELINE_ID,
    ACCEPTED_SCHEMA_REGISTRY_ID,
    ACCEPTED_TTL_PROOF_ID,
)

PRODUCTION_COMPLETE_REPORT_SHA256 = (
    "52852e011b01f502c043e5cb6f412f5b58f35d5c79709903748af20fd289cc34"
)
CONTROLLED_COMPLETE_STRESS_REPORT_SHA256 = (
    "d1746f99df5da958d0a581338c2b2dac29e60016d28f9c7f6cc67b5512c97722"
)
F_A4_PROOF_EXECUTION_ID = "51766ec2-6d38-433a-805a-8e41a5054dd4"
F_A4_PROCEDURE_ID = "task-device-fingerprint-03r2-n3-f-a4-finalization-v1"
FIX2_REPOSITORY_COMMIT_SHA = "4840a1a33af8e968f7b59f2eff61d1b2dd7643a9"
FIX2_REPOSITORY_TREE_SHA = "d1a9047f91d6558a5f584f3e0209e6b2b575ec19"

_GIT_SHA = re.compile(r"[0-9a-f]{40}")
_CONTENT_POLICY_PAYLOAD = {
    "snapshot_content_policy_version": 1,
    "max_authorized_evidence_rows": 40000,
    "max_authorized_health_rows": 10000,
    "max_verified_payload_bytes": 11720000,
    "max_materialized_payload_bytes": 11720000,
    "max_total_semantic_input_bytes": 52922790,
}
_EXECUTION_POLICY_PAYLOAD = {
    "snapshot_execution_policy_version": 1,
    "max_read_transaction_duration_ms": 240000,
    "sqlite_busy_timeout_ms": 500,
    "max_retry_count": 0,
    "process_memory_guard_bytes": 100663296,
}
_CANONICAL_RESULT_SUMMARY = (
    "PASS; production COMPLETE: evidence_rows=7091, health_rows=5340, "
    "total_semantic_input_bytes=9528273, reader_transaction_ms=47399; "
    "controlled COMPLETE: evidence_rows=40000, health_rows=10000, "
    "total_semantic_input_bytes=52922790, reader_transaction_ms=204361, "
    "retention_ms=7112, peak_wal_bytes=177300112, "
    "writer_batch_max_ms=303, process_max_rss_kib=71136, "
    "full_table_scans=0, unsupported_intact_rows=0"
)


def _fail(message: str) -> None:
    raise DeviceFingerprintValidationError(message)


def _git_sha(value: Any) -> str:
    if not isinstance(value, str) or _GIT_SHA.fullmatch(value) is None:
        _fail("Invalid F-A4 candidate Git identity")
    return value


def _ref(artifact_id: str) -> dict[str, str]:
    digest = artifact_id.rsplit(":", 1)[-1]
    return ArtifactRef(artifact_id, digest).as_dict()


def build_snapshot_content_policy() -> ArtifactContent:
    """Materialize the exact accepted controlled F-A4 content envelope."""
    return make_artifact_content("SnapshotContentPolicy", dict(_CONTENT_POLICY_PAYLOAD))


def build_snapshot_execution_policy() -> ArtifactContent:
    """Materialize the exact accepted operational F-A4 execution envelope."""
    return make_artifact_content(
        "SnapshotExecutionPolicy", dict(_EXECUTION_POLICY_PAYLOAD),
    )


def build_snapshot_performance_gate_proof(
    candidate_repository_commit_sha: str,
    candidate_repository_tree_sha: str,
) -> ArtifactContent:
    """Materialize the final proof for one exact final implementation identity."""
    candidate_commit = _git_sha(candidate_repository_commit_sha)
    candidate_tree = _git_sha(candidate_repository_tree_sha)
    content_policy = build_snapshot_content_policy()
    execution_policy = build_snapshot_execution_policy()
    input_refs = canonical_set([
        _ref(ACCEPTED_BINDING_TIMELINE_ID),
        _ref(ACCEPTED_BINDING_CLOCK_POLICY_ID),
        _ref(ACCEPTED_SCHEMA_REGISTRY_ID),
        _ref(ACCEPTED_TTL_PROOF_ID),
        _ref(content_policy.artifact_id),
        _ref(execution_policy.artifact_id),
    ], lambda ref: ref["artifact_id"])
    retained_evidence_refs = canonical_set([
        {
            "evidence_label": "fa4_controlled_complete_disposable_stress",
            "file_sha256": CONTROLLED_COMPLETE_STRESS_REPORT_SHA256,
            "media_type": "application/json",
            "path_or_reference": (
                "fa4-disposable-complete-fix2-40000-10000-20260919.json"
            ),
        },
        {
            "evidence_label": "fa4_production_complete_read_only_measurement",
            "file_sha256": PRODUCTION_COMPLETE_REPORT_SHA256,
            "media_type": "application/json",
            "path_or_reference": "fa4-prod-complete-fix2-20260919.json",
        },
    ], lambda ref: (ref["evidence_label"], ref["file_sha256"]))
    try:
        parsed_execution_id = uuid.UUID(F_A4_PROOF_EXECUTION_ID)
    except ValueError as exc:
        raise DeviceFingerprintValidationError(
            "Invalid F-A4 proof execution identity"
        ) from exc
    if str(parsed_execution_id) != F_A4_PROOF_EXECUTION_ID or parsed_execution_id.version != 4:
        _fail("Invalid F-A4 proof execution identity")
    payload = {
        "proof_kind": "SNAPSHOT_PERFORMANCE",
        "source_gate_id": "F-A4",
        "candidate_repository_commit_sha": candidate_commit,
        "candidate_repository_tree_sha": candidate_tree,
        "input_artifact_refs": input_refs,
        "procedure_or_test_suite_id": F_A4_PROCEDURE_ID,
        "proof_execution_identity": {
            "execution_id": F_A4_PROOF_EXECUTION_ID,
            "executor_kind": "owner_techlead_accepted_fa4_measurement_evidence",
            "repository_commit_sha": FIX2_REPOSITORY_COMMIT_SHA,
            "repository_tree_sha": FIX2_REPOSITORY_TREE_SHA,
            "procedure_or_test_suite_id": F_A4_PROCEDURE_ID,
            "environment_identity": (
                "production-read-only-plus-controlled-disposable-stress-2026-09-19"
            ),
            "execution_artifact_sha256": None,
        },
        "canonical_result_summary": _CANONICAL_RESULT_SUMMARY,
        "retained_evidence_refs": retained_evidence_refs,
    }
    return make_artifact_content("GateProofArtifact", payload)
