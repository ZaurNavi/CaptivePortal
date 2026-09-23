"""Frozen R14 F-F4 schema, initial identity, and synthetic gate proofs."""

from __future__ import annotations

from copy import deepcopy
from inspect import signature

import pytest

from app.device_fingerprint.artifact_content import ArtifactRef, make_artifact_content
from app.device_fingerprint.ff4_product_validation_policy import (
    run_ff4_product_validation_policy_gate,
)
from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.product_validation_policy import (
    build_initial_product_validation_policy_v1,
    make_product_validation_policy,
)

_DIGEST = "806779ca1844e55083a2c1c464cf8d94a9bdd0b2f97436d203b63fd03e81bea5"
_ID = f"ProductValidationPolicy:v1:sha256:{_DIGEST}"
_BASELINE = "c259364febe4401983ea5f1ede4a255077b8db84"
_TREE = "19e1ce5cf300e32a6fc37b678463dd4bcd5c83c3"
_DECISION = "00000000-0000-4000-8000-000000000001"  # synthetic only
_UNSET = object()
_REVIEW = "product_validation_policy_review"
_REGISTRATION = "product_validation_owner_decision_registration"


def _payload():
    return build_initial_product_validation_policy_v1().semantic_payload


def _evidence(label, digit):
    return {"evidence_label": label, "file_sha256": digit * 64,
            "media_type": "text/plain", "path_or_reference": "synthetic://ff4-proof"}


def _required_evidence():
    return [_evidence(_REVIEW, "a"), _evidence(_REGISTRATION, "b")]


def _gate(candidate=None, *, evidence=_UNSET, decisions=_UNSET):
    return run_ff4_product_validation_policy_gate(
        build_initial_product_validation_policy_v1() if candidate is None else candidate,
        candidate_repository_commit_sha=_BASELINE,
        candidate_repository_tree_sha=_TREE,
        environment_identity="synthetic-ff4",
        retained_evidence_refs=_required_evidence() if evidence is _UNSET else evidence,
        decision_record_refs=[_DECISION] if decisions is _UNSET else decisions,
    )


def _manifest(result):
    return result.gate_result_manifest.semantic_payload


def test_p01_to_p15_exact_initial_schema_identity_and_determinism():
    first = build_initial_product_validation_policy_v1()
    second = build_initial_product_validation_policy_v1()
    expected = {
        "product_validation_policy_version": 1,
        "known_dimension_wrong_resolved_behavior": "FAIL",
        "false_out_of_scope_behavior": "FAIL",
        "android_required_platform": "android",
        "android_min_support": "medium",
        "windows_required_platform": "windows",
        "windows_min_support": "medium",
        "minimum_correct_device_class_count_across_controlled_devices": 1,
        "device_class_min_support": "medium",
        "ground_truth_must_preexist_result": True,
        "automatic_learning_forbidden": True,
    }
    assert len(first.semantic_payload) == 11
    assert first.semantic_payload == expected
    assert first.artifact_id == second.artifact_id == _ID
    assert first.content_sha256 == second.content_sha256 == _DIGEST
    assert first.semantic_payload_json == second.semantic_payload_json
    assert make_product_validation_policy(expected).artifact_id == _ID


def test_p16_p17_n21_generic_version_two_valid_but_initial_gate_rejects():
    future = _payload()
    future["product_validation_policy_version"] = 2
    candidate = make_product_validation_policy(future)
    assert candidate.semantic_payload == future
    assert candidate.artifact_id != _ID
    result = _gate(candidate)
    assert _manifest(result)["status"] == "FAIL"
    assert _manifest(result)["output_artifact_refs"] == []
    assert result.failure_reasons == ("initial_product_validation_policy_identity_mismatch",)


@pytest.mark.parametrize("field,value", [
    ("product_validation_policy_version", 0),
    ("product_validation_policy_version", -1),
    ("product_validation_policy_version", True),
    ("product_validation_policy_version", 2_147_483_648),
    ("known_dimension_wrong_resolved_behavior", "UNKNOWN"),
    ("false_out_of_scope_behavior", "PASS"),
    ("android_required_platform", "ios"),
    ("android_min_support", "low"),
    ("windows_required_platform", "linux"),
    ("windows_min_support", "low"),
    ("minimum_correct_device_class_count_across_controlled_devices", 0),
    ("minimum_correct_device_class_count_across_controlled_devices", 2),
    ("minimum_correct_device_class_count_across_controlled_devices", True),
    ("device_class_min_support", "low"),
    ("ground_truth_must_preexist_result", False),
    ("ground_truth_must_preexist_result", 1),
    ("automatic_learning_forbidden", False),
    ("automatic_learning_forbidden", 1),
])
def test_n03_to_n20_invalid_field_rejected(field, value):
    payload = _payload()
    payload[field] = value
    with pytest.raises(DeviceFingerprintValidationError):
        make_product_validation_policy(payload)


def test_n01_n02_missing_and_extra_fields_rejected():
    missing = _payload()
    del missing["automatic_learning_forbidden"]
    extra = _payload()
    extra["classification_policy_ref"] = "forbidden"
    for payload in (missing, extra):
        with pytest.raises(DeviceFingerprintValidationError):
            make_product_validation_policy(payload)


def test_p18_to_p21_p23_p25_initial_gate_pass_and_exact_manifest():
    candidate = build_initial_product_validation_policy_v1()
    result = _gate(candidate)
    manifest = _manifest(result)
    assert result.double_build_bytes_equal
    assert result.build_1_artifact_id == result.build_2_artifact_id == _ID
    assert result.failure_reasons == ()
    assert manifest["gate_id"] == "F-F4"
    assert manifest["gate_contract_version"] == "R14-F-F4-v1"
    assert manifest["status"] == "PASS"
    assert manifest["input_artifact_refs"] == []
    assert manifest["output_artifact_refs"] == [
        ArtifactRef(candidate.artifact_id, candidate.content_sha256).as_dict()]
    assert manifest["decision_record_refs"] == [_DECISION]
    assert set(manifest["trusted_time_inputs"].values()) == {None}
    assert manifest["proof_execution_identity"]["executor_kind"] == "TECHLEAD_GATE_TOOL"
    assert manifest["proof_execution_identity"]["procedure_or_test_suite_id"] == (
        "F-F4-product-validation-policy-v1")


def test_p22_additional_unrelated_retained_evidence_is_allowed():
    evidence = _required_evidence() + [_evidence("other_review_evidence", "c")]
    result = _gate(evidence=evidence)
    assert _manifest(result)["status"] == "PASS"
    assert len(_manifest(result)["retained_evidence_refs"]) == 3


def test_p24_duplicate_identical_decision_uuid_canonicalized():
    result = _gate(decisions=[_DECISION, _DECISION])
    assert _manifest(result)["status"] == "PASS"
    assert _manifest(result)["decision_record_refs"] == [_DECISION]


@pytest.mark.parametrize("evidence,reasons", [
    ([], ("retained_evidence_required",)),
    ([_evidence("unrelated", "c")],
     ("product_validation_owner_decision_registration_required",
      "product_validation_policy_review_required")),
    ([_evidence(_REGISTRATION, "b")], ("product_validation_policy_review_required",)),
    ([_evidence(_REVIEW, "a"), _evidence(_REVIEW, "c"), _evidence(_REGISTRATION, "b")],
     ("product_validation_policy_review_required",)),
    ([_evidence(_REVIEW, "a")],
     ("product_validation_owner_decision_registration_required",)),
    ([_evidence(_REVIEW, "a"), _evidence(_REGISTRATION, "b"), _evidence(_REGISTRATION, "c")],
     ("product_validation_owner_decision_registration_required",)),
])
def test_n22_to_n27_required_evidence_multiplicity_fails(evidence, reasons):
    result = _gate(evidence=evidence)
    assert _manifest(result)["status"] == "FAIL"
    assert _manifest(result)["output_artifact_refs"] == []
    assert result.failure_reasons == tuple(sorted(reasons))


def test_identical_duplicate_mandatory_evidence_still_fails():
    evidence = _required_evidence()
    evidence.append(deepcopy(evidence[0]))
    result = _gate(evidence=evidence)
    assert _manifest(result)["status"] == "FAIL"
    assert result.failure_reasons == ("product_validation_policy_review_required",)


def test_n28_empty_decision_refs_fail_without_output():
    result = _gate(decisions=[])
    assert result.failure_reasons == ("product_validation_owner_decision_required",)
    assert _manifest(result)["status"] == "FAIL"
    assert _manifest(result)["output_artifact_refs"] == []


@pytest.mark.parametrize("decisions", [[None], ["not-a-uuid"], [123]])
def test_n29_n30_malformed_decision_ref_fails_closed(decisions):
    with pytest.raises(DeviceFingerprintValidationError):
        _gate(decisions=decisions)


@pytest.mark.parametrize("evidence", [None, [None], [{"evidence_label": 1}]])
def test_malformed_evidence_fails_closed_without_raw_error(evidence):
    with pytest.raises(DeviceFingerprintValidationError):
        _gate(evidence=evidence)


def test_bad_evidence_row_is_validated_by_generic_manifest():
    evidence = _required_evidence()
    evidence[0]["file_sha256"] = "not-sha256"
    with pytest.raises(DeviceFingerprintValidationError):
        _gate(evidence=evidence)


def test_n32_public_gate_has_no_bypass_parameter():
    names = signature(run_ff4_product_validation_policy_gate).parameters
    assert not {"skip_owner_check", "allow_result_driven_policy",
                "allow_alternate_initial_policy", "initial_admission",
                "bypass_identity"} & set(names)


def test_policy_has_no_classifier_runtime_or_cross_layer_artifact_refs():
    import app.device_fingerprint.product_validation_policy as policy_module

    payload = build_initial_product_validation_policy_v1().semantic_payload
    assert not any(key.endswith("_ref") or key.endswith("_refs") for key in payload)
    forbidden = ("ClassificationPolicy", "ClassificationRetentionPolicy",
                 "ClassificationRuntimeProfile", "Task04AcceptanceManifest",
                 "ControlledValidationGroundTruthRecord", "ClassificationResult")
    serialized = build_initial_product_validation_policy_v1().semantic_payload_json.decode("utf-8")
    assert all(name not in serialized for name in forbidden)
    assert all(name not in policy_module.__dict__ for name in forbidden)


def test_invalid_candidate_payload_yields_deterministic_fail_reason():
    invalid = make_artifact_content("ProductValidationPolicy", {"wrong": "shape"})
    result = _gate(invalid)
    assert _manifest(result)["status"] == "FAIL"
    assert set(result.failure_reasons) == {
        "product_validation_policy_invalid",
        "initial_product_validation_policy_identity_mismatch",
    }
    assert _manifest(result)["output_artifact_refs"] == []
