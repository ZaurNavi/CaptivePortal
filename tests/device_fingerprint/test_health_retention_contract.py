"""Exact F-B3 immutable policy and Task-01 retention capability."""

import pytest

from app.device_fingerprint.config import SOURCE_HEALTH_RETENTION_MARGIN_SECONDS
from app.device_fingerprint.health_retention_contract import (
    activation_margin_compatible, derive_health_anchor_margin_seconds,
    final_source_health_policy, make_task01_health_retention_contract,
)
from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.source_health_policy import build_current_source_health_policy


def test_final_policy_margin_and_exact_task01_contract_shape():
    policy = final_source_health_policy()
    assert SOURCE_HEALTH_RETENTION_MARGIN_SECONDS == 600
    assert derive_health_anchor_margin_seconds(policy) == 600
    assert policy.semantic_payload["health_anchor_margin_seconds"] == 600
    assert {rule["freshness"]["freshness_timeout_ms"] for rule in
            policy.semantic_payload["emitter_source_family_rules"]} == {0, 180_000, 600_000}
    assert policy.semantic_payload["task01_timestamp_skew_contract_ref"] == (
        "Task01TimestampSkewContract:v1:max_future_source_event_skew_seconds=120")
    assert policy.semantic_payload["task01_delayed_event_contract_ref"] == (
        "Task01DelayedEventContract:v1:max_delayed_event_age_seconds=86400")
    contract = make_task01_health_retention_contract(
        policy, retained_evidence_horizon_seconds=2_592_000,
        retained_health_horizon_seconds=2_592_600,
    )
    assert contract.semantic_payload == {
        "contract_version": 1,
        "source_health_policy": {
            "artifact_id": policy.artifact_id, "content_sha256": policy.content_sha256,
        },
        "required_health_anchor_margin_seconds": 600,
        "preserve_predecessor_anchor": True,
        "retained_evidence_horizon_seconds": 2_592_000,
        "retained_health_horizon_seconds": 2_592_600,
        "retention_compatibility_status": "PASS",
    }


def test_old_test_candidate_remains_reproducible_but_is_not_final():
    old = build_current_source_health_policy(health_anchor_margin_seconds=0)
    assert old.artifact_id == (
        "SourceHealthPolicy:v1:sha256:"
        "6b16ae4496a5d87679045daa88b9a32f5059782febf2019e6a8edf6076118157")
    assert old.artifact_id != final_source_health_policy().artifact_id
    with pytest.raises(DeviceFingerprintValidationError):
        make_task01_health_retention_contract(
            old, retained_evidence_horizon_seconds=2_592_000,
            retained_health_horizon_seconds=2_592_600,
        )


def test_ninety_day_horizon_is_exact_and_insufficient_history_fails_closed():
    policy = final_source_health_policy()
    contract = make_task01_health_retention_contract(
        policy, retained_evidence_horizon_seconds=7_776_000,
        retained_health_horizon_seconds=7_776_600,
    )
    assert contract.semantic_payload["retained_evidence_horizon_seconds"] == 7_776_000
    assert contract.semantic_payload["retained_health_horizon_seconds"] == 7_776_600
    for health_horizon in (7_776_599, 7_776_601):
        with pytest.raises(DeviceFingerprintValidationError):
            make_task01_health_retention_contract(
                policy, retained_evidence_horizon_seconds=7_776_000,
                retained_health_horizon_seconds=health_horizon,
            )


@pytest.mark.parametrize("required,preserved,expected", [
    (0, 600, True), (180, 600, True), (600, 600, True), (601, 600, False),
])
def test_future_activation_margin_is_bounded_by_preserved_history(required, preserved, expected):
    assert activation_margin_compatible(required, preserved) is expected


@pytest.mark.parametrize("required,preserved", [(-1, 600), (600, -1), (True, 600),
                                                (600, 2**63)])
def test_activation_margin_invalid_inputs_fail_closed(required, preserved):
    with pytest.raises(DeviceFingerprintValidationError):
        activation_margin_compatible(required, preserved)
