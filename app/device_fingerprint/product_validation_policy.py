"""Immutable R14 F-F4 product-validation policy; no classifier execution."""

from __future__ import annotations

from typing import Any

from .artifact_content import ArtifactContent, make_artifact_content
from .models import DeviceFingerprintValidationError

_FIELDS = frozenset({
    "product_validation_policy_version",
    "known_dimension_wrong_resolved_behavior",
    "false_out_of_scope_behavior",
    "android_required_platform",
    "android_min_support",
    "windows_required_platform",
    "windows_min_support",
    "minimum_correct_device_class_count_across_controlled_devices",
    "device_class_min_support",
    "ground_truth_must_preexist_result",
    "automatic_learning_forbidden",
})
_EXACT_VALUES = {
    "known_dimension_wrong_resolved_behavior": "FAIL",
    "false_out_of_scope_behavior": "FAIL",
    "android_required_platform": "android",
    "android_min_support": "medium",
    "windows_required_platform": "windows",
    "windows_min_support": "medium",
    "device_class_min_support": "medium",
    "ground_truth_must_preexist_result": True,
    "automatic_learning_forbidden": True,
}


def make_product_validation_policy(payload: dict[str, Any]) -> ArtifactContent:
    """Validate the exact C.3.25 payload and use shared ArtifactContent identity."""
    if not isinstance(payload, dict) or set(payload) != _FIELDS:
        raise DeviceFingerprintValidationError("Invalid ProductValidationPolicy shape")
    version = payload["product_validation_policy_version"]
    if type(version) is not int or not 1 <= version <= 2_147_483_647:
        raise DeviceFingerprintValidationError("Invalid product validation policy version")
    count = payload["minimum_correct_device_class_count_across_controlled_devices"]
    if type(count) is not int or count != 1:
        raise DeviceFingerprintValidationError("Invalid minimum correct device-class count")
    for field, expected in _EXACT_VALUES.items():
        if type(expected) is bool:
            valid = payload[field] is expected
        else:
            valid = payload[field] == expected
        if not valid:
            raise DeviceFingerprintValidationError(f"Invalid {field}")
    return make_artifact_content("ProductValidationPolicy", payload)


def build_initial_product_validation_policy_v1() -> ArtifactContent:
    """Build the Owner-frozen first policy without external state."""
    return make_product_validation_policy({
        "product_validation_policy_version": 1,
        **_EXACT_VALUES,
        "minimum_correct_device_class_count_across_controlled_devices": 1,
    })
