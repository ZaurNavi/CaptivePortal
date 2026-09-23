"""Immutable R14 F-F3 retention policy; no persistence or GC runtime."""

from __future__ import annotations

from typing import Any

from .artifact_content import ArtifactContent, make_artifact_content
from .models import DeviceFingerprintValidationError

_FIELDS = frozenset({
    "retention_policy_version", "classification_history_retention_seconds",
    "co_retain_snapshot_record", "co_retain_request_result_evaluability_origin",
    "privacy_storage_basis", "expiry_behavior", "reference_aware_gc",
})
_INITIAL_BASIS = "OPERATIONAL_AUDIT_REPLAY_TROUBLESHOOTING_AND_CONTROLLED_VALIDATION"
_EXPIRY_BEHAVIOR = "DELETE_CLASSIFICATION_WHEN_ELIGIBLE"


def _positive_int(value: Any, maximum: int, label: str) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise DeviceFingerprintValidationError(f"Invalid {label}")
    return value


def make_classification_retention_policy(payload: dict[str, Any]) -> ArtifactContent:
    """Validate exact R14 C.3.24 shape and use shared ArtifactContent identity."""
    if not isinstance(payload, dict) or set(payload) != _FIELDS:
        raise DeviceFingerprintValidationError("Invalid ClassificationRetentionPolicy shape")
    _positive_int(payload["retention_policy_version"], 2_147_483_647, "retention policy version")
    _positive_int(payload["classification_history_retention_seconds"], 9_223_372_036_854_775_807,
                  "classification history retention seconds")
    for name in ("co_retain_snapshot_record", "co_retain_request_result_evaluability_origin",
                 "reference_aware_gc"):
        if payload[name] is not True:
            raise DeviceFingerprintValidationError(f"Invalid {name}")
    if not isinstance(payload["privacy_storage_basis"], str) or not payload["privacy_storage_basis"]:
        raise DeviceFingerprintValidationError("Invalid privacy storage basis")
    if payload["expiry_behavior"] != _EXPIRY_BEHAVIOR:
        raise DeviceFingerprintValidationError("Invalid expiry behavior")
    return make_artifact_content("ClassificationRetentionPolicy", payload)


def build_initial_classification_retention_policy_v1() -> ArtifactContent:
    """Build Owner-frozen first policy without clock, repository, or environment."""
    return make_classification_retention_policy({
        "retention_policy_version": 1,
        "classification_history_retention_seconds": 7_776_000,
        "co_retain_snapshot_record": True,
        "co_retain_request_result_evaluability_origin": True,
        "privacy_storage_basis": _INITIAL_BASIS,
        "expiry_behavior": _EXPIRY_BEHAVIOR,
        "reference_aware_gc": True,
    })
