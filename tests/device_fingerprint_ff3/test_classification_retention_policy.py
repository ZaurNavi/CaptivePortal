"""Frozen R14 F-F3 schema, initial identity, and synthetic gate proofs."""

from __future__ import annotations

from copy import deepcopy
from inspect import signature

import pytest

from app.device_fingerprint.artifact_content import ArtifactRef, make_artifact_content
from app.device_fingerprint.classification_retention_policy import (
    build_initial_classification_retention_policy_v1,
    make_classification_retention_policy,
)
from app.device_fingerprint.ff3_classification_retention_policy import (
    run_ff3_classification_retention_policy_gate,
)
from app.device_fingerprint.models import DeviceFingerprintValidationError

_DIGEST = "029c3534e076db6f7293c78e8a86c425b10c786d58713e77a077a19dfdda3e72"
_ID = f"ClassificationRetentionPolicy:v1:sha256:{_DIGEST}"
_BASELINE = "295f22b5aed79414d879a65312987d415bf954f2"
_TREE = "c1a30597d4b5474856ff14fa57c5b9cb3ef24b88"
_DECISION = "00000000-0000-4000-8000-000000000001"  # synthetic only
_UNSET = object()
_ANALYSIS = "classification_retention_privacy_storage_analysis"
_REGISTRATION = "classification_retention_owner_decision_registration"


def _payload():
    return build_initial_classification_retention_policy_v1().semantic_payload


def _evidence(label, digit):
    return {"evidence_label": label, "file_sha256": digit * 64,
            "media_type": "text/plain", "path_or_reference": "synthetic://ff3-proof"}


def _required_evidence():
    return [_evidence(_ANALYSIS, "a"), _evidence(_REGISTRATION, "b")]


def _gate(candidate=None, *, evidence=_UNSET, decisions=_UNSET):
    return run_ff3_classification_retention_policy_gate(
        build_initial_classification_retention_policy_v1() if candidate is None else candidate,
        candidate_repository_commit_sha=_BASELINE,
        candidate_repository_tree_sha=_TREE,
        environment_identity="synthetic-ff3",
        retained_evidence_refs=_required_evidence() if evidence is _UNSET else evidence,
        decision_record_refs=[_DECISION] if decisions is _UNSET else decisions,
    )


def _manifest(result):
    return result.gate_result_manifest.semantic_payload


def test_p01_to_p11_exact_initial_schema_identity_and_determinism():
    a = build_initial_classification_retention_policy_v1()
    b = build_initial_classification_retention_policy_v1()
    expected = {
        "retention_policy_version": 1,
        "classification_history_retention_seconds": 7_776_000,
        "co_retain_snapshot_record": True,
        "co_retain_request_result_evaluability_origin": True,
        "privacy_storage_basis": "OPERATIONAL_AUDIT_REPLAY_TROUBLESHOOTING_AND_CONTROLLED_VALIDATION",
        "expiry_behavior": "DELETE_CLASSIFICATION_WHEN_ELIGIBLE",
        "reference_aware_gc": True,
    }
    assert len(a.semantic_payload) == 7
    assert a.semantic_payload == expected
    assert a.artifact_id == b.artifact_id == _ID
    assert a.content_sha256 == b.content_sha256 == _DIGEST
    assert a.semantic_payload_json == b.semantic_payload_json
    assert make_classification_retention_policy(expected).artifact_id == _ID


def test_p12_p13_generic_future_policy_is_valid_without_initial_pinning():
    future = _payload()
    future.update(retention_policy_version=2,
                  classification_history_retention_seconds=15_552_000,
                  privacy_storage_basis="FUTURE_OWNER_BASIS")
    content = make_classification_retention_policy(future)
    assert content.semantic_payload == future
    assert content.artifact_id != _ID


@pytest.mark.parametrize("field,value", [
    ("retention_policy_version", 0),
    ("retention_policy_version", -1),
    ("retention_policy_version", True),
    ("retention_policy_version", 2_147_483_648),
    ("classification_history_retention_seconds", 0),
    ("classification_history_retention_seconds", -1),
    ("classification_history_retention_seconds", True),
    ("classification_history_retention_seconds", 9_223_372_036_854_775_808),
    ("co_retain_snapshot_record", False),
    ("co_retain_snapshot_record", 1),
    ("co_retain_request_result_evaluability_origin", False),
    ("co_retain_request_result_evaluability_origin", 1),
    ("privacy_storage_basis", ""),
    ("privacy_storage_basis", 123),
    ("expiry_behavior", "KEEP_FOREVER"),
    ("reference_aware_gc", False),
    ("reference_aware_gc", 1),
])
def test_n03_to_n19_invalid_field_rejected(field, value):
    payload = _payload()
    payload[field] = value
    with pytest.raises(DeviceFingerprintValidationError):
        make_classification_retention_policy(payload)


def test_n01_n02_missing_and_extra_fields_rejected():
    missing = _payload()
    del missing["reference_aware_gc"]
    extra = _payload()
    extra["classification_policy_ref"] = "forbidden"
    for payload in (missing, extra):
        with pytest.raises(DeviceFingerprintValidationError):
            make_classification_retention_policy(payload)


@pytest.mark.parametrize("seconds,basis", [
    (2_592_000, "OPERATIONAL_AUDIT_REPLAY_TROUBLESHOOTING_AND_CONTROLLED_VALIDATION"),
    (15_552_000, "OPERATIONAL_AUDIT_REPLAY_TROUBLESHOOTING_AND_CONTROLLED_VALIDATION"),
    (7_776_000, "ANOTHER_VALID_BASIS"),
])
def test_p14_n20_to_n22_generic_alternate_is_initial_gate_fail(seconds, basis):
    payload = _payload()
    payload.update(classification_history_retention_seconds=seconds,
                   privacy_storage_basis=basis)
    candidate = make_classification_retention_policy(payload)
    result = _gate(candidate)
    assert _manifest(result)["status"] == "FAIL"
    assert _manifest(result)["output_artifact_refs"] == []
    assert result.failure_reasons == ("initial_classification_retention_policy_identity_mismatch",)


def test_p15_to_p18_p20_p22_initial_gate_pass_and_exact_manifest():
    candidate = build_initial_classification_retention_policy_v1()
    result = _gate(candidate)
    manifest = _manifest(result)
    assert result.double_build_bytes_equal
    assert result.build_1_artifact_id == result.build_2_artifact_id == _ID
    assert result.failure_reasons == ()
    assert manifest["gate_id"] == "F-F3"
    assert manifest["gate_contract_version"] == "R14-F-F3-v1"
    assert manifest["status"] == "PASS"
    assert manifest["input_artifact_refs"] == []
    assert manifest["output_artifact_refs"] == [
        ArtifactRef(candidate.artifact_id, candidate.content_sha256).as_dict()]
    assert manifest["decision_record_refs"] == [_DECISION]
    assert set(manifest["trusted_time_inputs"].values()) == {None}
    assert manifest["proof_execution_identity"]["executor_kind"] == "TECHLEAD_GATE_TOOL"
    assert manifest["proof_execution_identity"]["procedure_or_test_suite_id"] == (
        "F-F3-classification-retention-policy-v1")


def test_p19_additional_unrelated_retained_evidence_is_allowed():
    evidence = _required_evidence() + [_evidence("other_review_evidence", "c")]
    result = _gate(evidence=evidence)
    assert _manifest(result)["status"] == "PASS"
    assert len(_manifest(result)["retained_evidence_refs"]) == 3


def test_p21_duplicate_identical_decision_uuid_canonicalized():
    result = _gate(decisions=[_DECISION, _DECISION])
    assert _manifest(result)["status"] == "PASS"
    assert _manifest(result)["decision_record_refs"] == [_DECISION]


@pytest.mark.parametrize("evidence,reasons", [
    ([], ("retained_evidence_required",)),
    ([_evidence("unrelated", "c")],
     ("classification_retention_owner_decision_registration_required",
      "classification_retention_privacy_storage_analysis_required")),
    ([_evidence(_REGISTRATION, "b")],
     ("classification_retention_privacy_storage_analysis_required",)),
    ([_evidence(_ANALYSIS, "a"), _evidence(_ANALYSIS, "c"), _evidence(_REGISTRATION, "b")],
     ("classification_retention_privacy_storage_analysis_required",)),
    ([_evidence(_ANALYSIS, "a")],
     ("classification_retention_owner_decision_registration_required",)),
    ([_evidence(_ANALYSIS, "a"), _evidence(_REGISTRATION, "b"), _evidence(_REGISTRATION, "c")],
     ("classification_retention_owner_decision_registration_required",)),
])
def test_n23_to_n28_required_evidence_multiplicity_fails(evidence, reasons):
    result = _gate(evidence=evidence)
    assert _manifest(result)["status"] == "FAIL"
    assert _manifest(result)["output_artifact_refs"] == []
    assert result.failure_reasons == tuple(sorted(reasons))


def test_n26_identical_duplicate_mandatory_evidence_still_fails():
    evidence = _required_evidence()
    evidence.append(deepcopy(evidence[0]))
    result = _gate(evidence=evidence)
    assert _manifest(result)["status"] == "FAIL"
    assert result.failure_reasons == ("classification_retention_privacy_storage_analysis_required",)


def test_n29_empty_decision_refs_fail_without_output():
    result = _gate(decisions=[])
    assert result.failure_reasons == ("classification_retention_owner_decision_required",)
    assert _manifest(result)["status"] == "FAIL"
    assert _manifest(result)["output_artifact_refs"] == []


@pytest.mark.parametrize("decisions", [[None], ["not-a-uuid"], [123]])
def test_n30_n31_malformed_decision_ref_fails_closed(decisions):
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


def test_n33_public_gate_has_no_bypass_parameter():
    names = signature(run_ff3_classification_retention_policy_gate).parameters
    assert not {"initial_admission", "skip_owner_check", "allow_alternate_policy",
                "bypass_initial_identity"} & set(names)


def test_retention_and_classification_policy_have_no_hidden_reference_coupling():
    import app.device_fingerprint.classification_retention_policy as retention_module

    initial = build_initial_classification_retention_policy_v1()
    alternate_payload = _payload()
    alternate_payload["classification_history_retention_seconds"] = 15_552_000
    alternate = make_classification_retention_policy(alternate_payload)
    assert initial.artifact_id != alternate.artifact_id
    assert "ClassificationPolicy" not in retention_module.__dict__
    assert "ClassificationPolicy" not in initial.semantic_payload_json.decode("utf-8")
    assert "ClassificationPolicy" not in alternate.semantic_payload_json.decode("utf-8")
    assert not any(key.endswith("_ref") or key.endswith("_refs")
                   for key in initial.semantic_payload)


def test_invalid_candidate_payload_yields_deterministic_fail_reason():
    invalid = make_artifact_content("ClassificationRetentionPolicy", {"wrong": "shape"})
    result = _gate(invalid)
    assert _manifest(result)["status"] == "FAIL"
    assert set(result.failure_reasons) == {
        "classification_retention_policy_invalid",
        "initial_classification_retention_policy_identity_mismatch",
    }
    assert _manifest(result)["output_artifact_refs"] == []
