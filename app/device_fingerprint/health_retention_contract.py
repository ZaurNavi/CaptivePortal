"""Immutable F-B3 Task-01 health-retention capability and admission check."""

from __future__ import annotations

from .artifact_content import ArtifactContent, ArtifactRef, make_artifact_content
from .config import SOURCE_HEALTH_RETENTION_MARGIN_SECONDS
from .models import DeviceFingerprintValidationError
from .source_health_policy import build_current_source_health_policy

_FROZEN_FRESHNESS_MS = frozenset({0, 180_000, 600_000})
_CLOCK_UNCERTAINTY_MS = 0


def final_source_health_policy() -> ArtifactContent:
    """Construct the current F-B3 candidate, without activating it."""
    return build_current_source_health_policy(
        health_anchor_margin_seconds=SOURCE_HEALTH_RETENTION_MARGIN_SECONDS,
    )


def derive_health_anchor_margin_seconds(policy: ArtifactContent) -> int:
    """Prove the frozen freshness maximum plus accepted clock uncertainty."""
    if not isinstance(policy, ArtifactContent) or policy.artifact_type != "SourceHealthPolicy":
        raise DeviceFingerprintValidationError("Invalid SourceHealthPolicy")
    timeouts = {rule["freshness"]["freshness_timeout_ms"]
                for rule in policy.semantic_payload["emitter_source_family_rules"]}
    if timeouts != _FROZEN_FRESHNESS_MS:
        raise DeviceFingerprintValidationError("SourceHealthPolicy freshness mismatch")
    required_ms = max(timeouts) + _CLOCK_UNCERTAINTY_MS
    if required_ms % 1000:
        raise DeviceFingerprintValidationError("Health retention margin is not whole seconds")
    required_seconds = required_ms // 1000
    if required_seconds != SOURCE_HEALTH_RETENTION_MARGIN_SECONDS:
        raise DeviceFingerprintValidationError("Task-01 health retention capability mismatch")
    return required_seconds


def make_task01_health_retention_contract(
        policy: ArtifactContent, *, retained_evidence_horizon_seconds: int,
        retained_health_horizon_seconds: int,
) -> ArtifactContent:
    """Bind explicit retained horizons to the final policy and actual cleanup."""
    final = final_source_health_policy()
    if (not isinstance(policy, ArtifactContent)
            or policy.artifact_id != final.artifact_id
            or policy.content_sha256 != final.content_sha256):
        raise DeviceFingerprintValidationError("Task-01 contract requires final SourceHealthPolicy")
    margin = derive_health_anchor_margin_seconds(policy)
    for value in (retained_evidence_horizon_seconds, retained_health_horizon_seconds):
        if type(value) is not int or not 0 <= value <= 2**63 - 1:
            raise DeviceFingerprintValidationError("Invalid retained horizon")
    if retained_health_horizon_seconds < retained_evidence_horizon_seconds + margin:
        raise DeviceFingerprintValidationError("Insufficient retained health history")
    if retained_health_horizon_seconds != retained_evidence_horizon_seconds + margin:
        raise DeviceFingerprintValidationError("Retained horizon differs from Task-01 cleanup")
    return make_artifact_content("Task01HealthRetentionContract", {
        "contract_version": 1,
        "source_health_policy": ArtifactRef(policy.artifact_id, policy.content_sha256).as_dict(),
        "required_health_anchor_margin_seconds": margin,
        "preserve_predecessor_anchor": True,
        "retained_evidence_horizon_seconds": retained_evidence_horizon_seconds,
        "retained_health_horizon_seconds": retained_health_horizon_seconds,
        "retention_compatibility_status": "PASS",
    })


def activation_margin_compatible(
        candidate_required_margin_seconds: int, preserved_margin_capability_seconds: int,
) -> bool:
    """A later policy cannot claim predecessor history already cleaned up."""
    for value in (candidate_required_margin_seconds, preserved_margin_capability_seconds):
        if type(value) is not int or not 0 <= value <= 2**63 - 1:
            raise DeviceFingerprintValidationError("Invalid health retention margin")
    return candidate_required_margin_seconds <= preserved_margin_capability_seconds
