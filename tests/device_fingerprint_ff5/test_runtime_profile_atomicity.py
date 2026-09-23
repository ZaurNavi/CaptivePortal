"""Disposable SQLite crash/CAS/pinning proof and F-F5 gate contract."""

from __future__ import annotations

import sqlite3
from dataclasses import replace

import pytest

from app.device_fingerprint.artifact_content import ArtifactRef, make_artifact_content
from app.device_fingerprint.control_plane_store import (
    ControlPlaneOperationError, DeviceFingerprintControlPlaneStore,
)
from app.device_fingerprint.ff5_runtime_profile_atomicity import (
    _Fixture, execute_ff5_runtime_profile_atomicity_scenarios,
    run_ff5_runtime_profile_atomicity_gate,
)
from app.device_fingerprint.gate_proof_artifacts import PROOF_KINDS, make_gate_proof_artifact
from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.runtime_profile_artifacts import make_runtime_profile_validity_record

_SHA = "a" * 40
_TREE = "b" * 40
_LABELS = (
    "runtime_profile_switch_pinning_trace",
    "runtime_profile_transaction_crash_point_trace",
    "runtime_profile_rollback_trace",
    "runtime_profile_cas_race_trace",
    "runtime_profile_restart_recovery_trace",
    "runtime_profile_compatibility_test_fixtures",
)


def _evidence():
    return [
        {"evidence_label": label, "file_sha256": f"{index:x}" * 64,
         "media_type": "application/json", "path_or_reference": "synthetic://ff5-proof"}
        for index, label in enumerate(_LABELS, start=1)
    ]


def _execution(tmp_path):
    return execute_ff5_runtime_profile_atomicity_scenarios(
        working_directory=tmp_path,
        candidate_repository_commit_sha=_SHA,
        candidate_repository_tree_sha=_TREE,
    )


def _gate(execution, evidence=None):
    return run_ff5_runtime_profile_atomicity_gate(
        execution, candidate_repository_commit_sha=_SHA,
        candidate_repository_tree_sha=_TREE,
        environment_identity="synthetic-ff5-windows",
        retained_evidence_refs=_evidence() if evidence is None else evidence,
    )


def test_complete_synthetic_scenarios_and_pass_gate(tmp_path):
    execution = _execution(tmp_path)
    assert set(execution.checks) == {
        "fixture", "dependency", "crash", "pinning", "rollback",
        "validity_cas", "activation_cas", "aba", "recovery",
        "transaction_only_record_visibility", "inactive_active_pointer_fail_closed",
        "standalone_inactive_transition_forbidden",
        "invalidated_activation_cannot_be_reenabled",
        "inactive_predecessor_activation_fail_closed",
    }
    assert all(execution.checks.values())
    assert execution.failure_reasons == ()
    assert all(execution.transaction_crash_point_trace.values())
    assert execution.transaction_crash_point_trace["transaction_only_record_visibility"] is True
    assert execution.restart_recovery_trace["inactive_active_pointer_fail_closed"] is True
    assert execution.restart_recovery_trace["inactive_predecessor_activation_fail_closed"] is True
    assert execution.profile_switch_pinning_trace["standalone_inactive_transition_forbidden"] is True
    assert execution.profile_switch_pinning_trace["invalidated_activation_cannot_be_reenabled"] is True
    assert execution.cas_race_trace["activation"] == [
        "active_profile_precondition_mismatch", "success"]
    assert execution.cas_race_trace["validity"] == [
        "runtime_profile_validity_cas_conflict", "success"]
    assert execution.compatibility_test_fixtures["synthetic_only"] is True
    result = _gate(execution)
    manifest = result.gate_result_manifest.semantic_payload
    proof = result.gate_proof_artifact.semantic_payload
    assert manifest["status"] == "PASS"
    assert result.failure_reasons == ()
    assert proof["proof_kind"] == "RUNTIME_PROFILE_ATOMICITY"
    assert proof["source_gate_id"] == "F-F5"
    assert proof["procedure_or_test_suite_id"] == "F-F5-runtime-profile-atomicity-v1"
    assert manifest["gate_id"] == "F-F5"
    assert manifest["gate_contract_version"] == "R14-F-F5-v1"
    assert manifest["proof_execution_identity"]["procedure_or_test_suite_id"] == (
        "F-F5-runtime-profile-atomicity-gate-v1")
    assert len(manifest["input_artifact_refs"]) > 0
    assert len(manifest["output_artifact_refs"]) == 1
    assert manifest["output_artifact_refs"][0]["artifact_id"] == result.gate_proof_artifact.artifact_id
    assert manifest["decision_record_refs"] == []
    assert set(manifest["trusted_time_inputs"].values()) == {None}
    assert [row["evidence_label"] for row in manifest["retained_evidence_refs"]] == sorted(_LABELS)


@pytest.mark.parametrize("failed_check,reason", [
    ("pinning", "runtime_profile_pinning_failed"),
    ("transaction_only_record_visibility", "runtime_profile_transactional_visibility_failed"),
    ("inactive_active_pointer_fail_closed", "runtime_profile_restart_recovery_failed"),
    ("standalone_inactive_transition_forbidden", "runtime_profile_validity_cas_failed"),
    ("invalidated_activation_cannot_be_reenabled", "runtime_profile_pinning_failed"),
    ("inactive_predecessor_activation_fail_closed", "runtime_profile_restart_recovery_failed"),
])
def test_forced_scenario_failure_emits_no_gate_output(tmp_path, failed_check, reason):
    execution = _execution(tmp_path)
    failed = replace(execution, checks={**execution.checks, failed_check: False})
    result = _gate(failed)
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []
    assert reason in result.failure_reasons


def test_missing_or_mismatched_execution_proof_cannot_pass(tmp_path):
    execution = _execution(tmp_path)
    for invalid in (replace(execution, checks={}),
                    replace(execution, compatibility_test_fixtures={
                        **execution.compatibility_test_fixtures, "candidate_commit": "c" * 40})):
        result = _gate(invalid)
        assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
        assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []
        assert "runtime_profile_fixture_invalid" in result.failure_reasons


@pytest.mark.parametrize("evidence,reason", [
    ([], "retained_evidence_required"),
    ([_evidence()[0]], "runtime_profile_cas_race_trace_required"),
    (_evidence() + [_evidence()[0]], "runtime_profile_switch_pinning_trace_required"),
])
def test_required_retained_evidence_multiplicity_fails(tmp_path, evidence, reason):
    execution = _execution(tmp_path)
    result = _gate(execution, evidence)
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []
    assert reason in result.failure_reasons


def test_additional_unrelated_evidence_is_permitted(tmp_path):
    execution = _execution(tmp_path)
    evidence = _evidence() + [{"evidence_label": "other", "file_sha256": "e" * 64,
                              "media_type": "text/plain", "path_or_reference": None}]
    assert _gate(execution, evidence).gate_result_manifest.semantic_payload["status"] == "PASS"


def test_gate_proof_schema_closed_full_enum_and_generic_validation(tmp_path):
    execution = _execution(tmp_path)
    proof = _gate(execution).gate_proof_artifact
    assert len(PROOF_KINDS) == 13
    assert make_gate_proof_artifact(proof.semantic_payload).artifact_id == proof.artifact_id
    missing = proof.semantic_payload
    missing.pop("canonical_result_summary")
    with pytest.raises(DeviceFingerprintValidationError):
        make_gate_proof_artifact(missing)
    extra = {**proof.semantic_payload, "extra": "forbidden"}
    with pytest.raises(DeviceFingerprintValidationError):
        make_gate_proof_artifact(extra)
    wrong = {**proof.semantic_payload, "proof_kind": "USER_DEFINED"}
    with pytest.raises(DeviceFingerprintValidationError):
        make_gate_proof_artifact(wrong)
    wrong = {**proof.semantic_payload, "input_artifact_refs": [{"artifact_id": "invalid",
                                                                  "content_sha256": "a" * 64}]}
    with pytest.raises(DeviceFingerprintValidationError):
        make_gate_proof_artifact(wrong)


def test_initial_pointer_activation_and_reopen_exact_chain(tmp_path):
    fixture = _Fixture(tmp_path / "initial.sqlite")
    rpm = fixture.admission("foundation", fixture.foundation_a)
    pointer, activation, validity, _ = fixture.activate(rpm, 11)
    assert pointer.runtime_profile_id == fixture.foundation_a.artifact_id
    assert fixture.store.get_validity_head(pointer.activation_record_id) == validity
    assert fixture.store.pin_active_profile("foundation").activation_record == activation
    restarted = DeviceFingerprintControlPlaneStore(fixture.store.database_path)
    restarted.validate_startup_integrity()
    assert restarted.pin_active_profile("foundation").pointer == pointer
    with restarted._connect() as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA synchronous").fetchone()[0] == 2  # FULL


def test_control_plane_records_are_visible_only_after_transactional_mutation(tmp_path):
    fixture = _Fixture(tmp_path / "record-visibility-test.sqlite")
    rpm = fixture.admission("foundation", fixture.foundation_a)
    activation, initial, _ = fixture.records(rpm, 61)
    for record in (activation, initial):
        with pytest.raises(DeviceFingerprintValidationError,
                           match="^Runtime control-plane record requires transactional mutation$"):
            fixture.store.persist_artifact(record)
        with pytest.raises(ControlPlaneOperationError) as error:
            fixture.store.load_artifact(record.artifact_id)
        assert error.value.reason_code == "runtime_profile_dependency_unavailable"
    assert fixture.store.get_active_pointer("foundation") is None

    pointer = fixture.store.activate_profile(rpm, activation, initial)
    assert fixture.store.load_artifact(activation.artifact_id) == activation
    assert fixture.store.load_artifact(initial.artifact_id) == initial
    assert fixture.store.get_validity_head(pointer.activation_record_id) == initial
    assert fixture.store.get_active_pointer("foundation") == pointer

    successor = make_runtime_profile_validity_record({
        **initial.semantic_payload,
        "validity_record_id": "00000000-0000-4000-8000-000000000620",
        "state": "SUSPENDED_INVALIDATED", "reason_code": "EXPLICIT_POLICY_SUSPEND",
        "inflight_commit_rule": "REJECT_PINNED_INFLIGHT",
        "previous_validity_record_id": initial.semantic_payload["validity_record_id"],
    })
    with pytest.raises(DeviceFingerprintValidationError,
                       match="^Runtime control-plane record requires transactional mutation$"):
        fixture.store.persist_artifact(successor)
    with pytest.raises(ControlPlaneOperationError):
        fixture.store.load_artifact(successor.artifact_id)
    fixture.store.transition_validity(
        successor, expected_head_validity_record_id=initial.semantic_payload["validity_record_id"])
    assert fixture.store.load_artifact(successor.artifact_id) == successor
    assert fixture.store.get_validity_head(pointer.activation_record_id) == successor


def test_inactive_head_corrupt_active_pointer_fails_closed(tmp_path):
    fixture = _Fixture(tmp_path / "inactive-pointer.sqlite")
    rpm_a = fixture.admission("foundation", fixture.foundation_a)
    pointer_a, _, _, _ = fixture.activate(rpm_a, 71)
    rpm_b = fixture.admission("foundation", fixture.foundation_b, pointer_a)
    fixture.activate(rpm_b, 72, fixture.store.get_validity_head(pointer_a.activation_record_id))
    assert fixture.store.get_validity_head(pointer_a.activation_record_id).semantic_payload["state"] == "INACTIVE"
    with sqlite3.connect(fixture.store.database_path) as conn:
        conn.execute("UPDATE active_pointers SET runtime_profile_id=?, runtime_profile_digest=?, "
                     "activation_record_id=?, activation_generation_id=? WHERE profile_kind=?", (
                         pointer_a.runtime_profile_id, pointer_a.runtime_profile_digest,
                         pointer_a.activation_record_id, pointer_a.activation_generation_id,
                         pointer_a.profile_kind))
    for operation in (fixture.store.validate_startup_integrity,
                      lambda: fixture.store.pin_active_profile("foundation")):
        with pytest.raises(ControlPlaneOperationError) as error:
            operation()
        assert error.value.reason_code == "activation_lineage_unavailable"
    corrupt_activation, corrupt_initial, _ = fixture.records(rpm_b, 73)
    with pytest.raises(ControlPlaneOperationError) as error:
        fixture.store.activate_profile(rpm_b, corrupt_activation, corrupt_initial)
    assert error.value.reason_code == "activation_lineage_unavailable"
    assert fixture.store.get_active_pointer("foundation") == pointer_a
    assert fixture.store.get_validity_head(pointer_a.activation_record_id).semantic_payload["state"] == "INACTIVE"
    assert fixture.store.get_validity_head(corrupt_activation.semantic_payload["activation_record_id"]) is None
    for record in (corrupt_activation, corrupt_initial):
        with pytest.raises(ControlPlaneOperationError):
            fixture.store.load_artifact(record.artifact_id)


def test_active_to_standalone_inactive_is_rejected_without_any_durable_change(tmp_path):
    fixture = _Fixture(tmp_path / "standalone-inactive.sqlite")
    rpm_a = fixture.admission("foundation", fixture.foundation_a)
    pointer_a, _, active, _ = fixture.activate(rpm_a, 74)
    forbidden = make_runtime_profile_validity_record({
        **active.semantic_payload,
        "validity_record_id": "00000000-0000-4000-8000-000000000741",
        "state": "INACTIVE", "reason_code": "SUPERSEDED_SAFE",
        "inflight_commit_rule": "ALLOW_PINNED_INFLIGHT",
        "previous_validity_record_id": active.semantic_payload["validity_record_id"],
    })
    with pytest.raises(ControlPlaneOperationError) as error:
        fixture.store.transition_validity(
            forbidden, expected_head_validity_record_id=active.semantic_payload["validity_record_id"])
    assert error.value.reason_code == "runtime_profile_validity_cas_conflict"
    with pytest.raises(ControlPlaneOperationError):
        fixture.store.load_artifact(forbidden.artifact_id)
    assert fixture.store.get_active_pointer("foundation") == pointer_a
    assert fixture.store.get_validity_head(pointer_a.activation_record_id) == active
    fixture.store.validate_startup_integrity()
    assert fixture.store.pin_active_profile("foundation").pointer == pointer_a
    rpm_b = fixture.admission("foundation", fixture.foundation_b, pointer_a)
    fixture.activate(rpm_b, 75, active)
    old_head = fixture.store.get_validity_head(pointer_a.activation_record_id).semantic_payload
    assert (old_head["state"], old_head["reason_code"], old_head["inflight_commit_rule"]) == (
        "INACTIVE", "SUPERSEDED_SAFE", "ALLOW_PINNED_INFLIGHT")


def test_suspended_to_standalone_inactive_cannot_reenable_pinned_commit(tmp_path):
    fixture = _Fixture(tmp_path / "suspended-inactive.sqlite")
    rpm_a = fixture.admission("foundation", fixture.foundation_a)
    pointer_a, _, active, _ = fixture.activate(rpm_a, 76)
    pinned = fixture.store.pin_active_profile("foundation")
    suspended = make_runtime_profile_validity_record({
        **active.semantic_payload,
        "validity_record_id": "00000000-0000-4000-8000-000000000761",
        "state": "SUSPENDED_INVALIDATED", "reason_code": "EXPLICIT_POLICY_SUSPEND",
        "inflight_commit_rule": "REJECT_PINNED_INFLIGHT",
        "previous_validity_record_id": active.semantic_payload["validity_record_id"],
    })
    fixture.store.transition_validity(
        suspended, expected_head_validity_record_id=active.semantic_payload["validity_record_id"])
    with pytest.raises(ControlPlaneOperationError) as error:
        fixture.store.check_pinned_commit_allowed(pinned)
    assert error.value.reason_code == "runtime_profile_invalidated"
    forbidden = make_runtime_profile_validity_record({
        **suspended.semantic_payload,
        "validity_record_id": "00000000-0000-4000-8000-000000000762",
        "state": "INACTIVE", "reason_code": "SUPERSEDED_SAFE",
        "inflight_commit_rule": "ALLOW_PINNED_INFLIGHT",
        "previous_validity_record_id": suspended.semantic_payload["validity_record_id"],
    })
    with pytest.raises(ControlPlaneOperationError) as error:
        fixture.store.transition_validity(
            forbidden, expected_head_validity_record_id=suspended.semantic_payload["validity_record_id"])
    assert error.value.reason_code == "runtime_profile_validity_cas_conflict"
    with pytest.raises(ControlPlaneOperationError):
        fixture.store.load_artifact(forbidden.artifact_id)
    assert fixture.store.get_validity_head(pointer_a.activation_record_id) == suspended
    with pytest.raises(ControlPlaneOperationError) as error:
        fixture.store.check_pinned_commit_allowed(pinned)
    assert error.value.reason_code == "runtime_profile_invalidated"
    rpm_b = fixture.admission("foundation", fixture.foundation_b, pointer_a)
    pointer_b, _, _, _ = fixture.activate(rpm_b, 77)
    assert fixture.store.get_active_pointer("foundation") == pointer_b
    assert fixture.store.get_validity_head(pointer_a.activation_record_id) == suspended


def test_suspended_current_pointer_preserves_auditable_lineage(tmp_path):
    fixture = _Fixture(tmp_path / "suspended-pointer.sqlite")
    rpm = fixture.admission("foundation", fixture.foundation_a)
    pointer, _, initial, _ = fixture.activate(rpm, 81)
    suspended = make_runtime_profile_validity_record({
        **initial.semantic_payload,
        "validity_record_id": "00000000-0000-4000-8000-000000000820",
        "state": "SUSPENDED_INVALIDATED", "reason_code": "EXPLICIT_POLICY_SUSPEND",
        "inflight_commit_rule": "REJECT_PINNED_INFLIGHT",
        "previous_validity_record_id": initial.semantic_payload["validity_record_id"],
    })
    fixture.store.transition_validity(
        suspended, expected_head_validity_record_id=initial.semantic_payload["validity_record_id"])
    fixture.store.validate_startup_integrity()
    assert fixture.store.get_active_pointer("foundation") == pointer
    with pytest.raises(ControlPlaneOperationError) as error:
        fixture.store.pin_active_profile("foundation")
    assert error.value.reason_code == "runtime_profile_invalidated"


def test_immutable_artifact_cannot_be_overwritten(tmp_path):
    fixture = _Fixture(tmp_path / "immutable.sqlite")
    original = fixture.leaves["BindingClockPolicy"]
    with sqlite3.connect(fixture.store.database_path) as conn:
        conn.execute("UPDATE artifacts SET semantic_payload_json=? WHERE artifact_id=?",
                     (b'{}', original.artifact_id))
    with pytest.raises(ControlPlaneOperationError) as error:
        fixture.store.persist_artifact(original)
    assert error.value.reason_code == "artifact_immutable_conflict"
    assert error.value.reason_code in str(error.value)


def test_prebegin_missing_dependency_does_not_publish_activation(tmp_path):
    fixture = _Fixture(tmp_path / "dependency.sqlite")
    rpm = fixture.admission("foundation", fixture.foundation_a)
    activation, validity, _ = fixture.records(rpm, 21)
    with sqlite3.connect(fixture.store.database_path) as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("DELETE FROM artifacts WHERE artifact_id=?",
                     (fixture.leaves["BindingClockPolicy"].artifact_id,))
    stages = []
    fixture.store.fault_hook = stages.append
    with pytest.raises(ControlPlaneOperationError) as error:
        fixture.store.activate_profile(rpm, activation, validity)
    assert error.value.reason_code == "runtime_profile_dependency_unavailable"
    assert stages == []
    assert fixture.store.get_active_pointer("foundation") is None
    with pytest.raises(ControlPlaneOperationError):
        fixture.store.load_artifact(activation.artifact_id)


def test_post_activation_cannot_reactivate_same_validity_chain(tmp_path):
    fixture = _Fixture(tmp_path / "validity-reactivation.sqlite")
    rpm = fixture.admission("foundation", fixture.foundation_a)
    pointer, _, _, _ = fixture.activate(rpm, 31)
    head = fixture.store.get_validity_head(pointer.activation_record_id)
    from app.device_fingerprint.runtime_profile_artifacts import make_runtime_profile_validity_record
    active_successor = make_runtime_profile_validity_record({
        **head.semantic_payload,
        "validity_record_id": "00000000-0000-4000-8000-000000000099",
        "previous_validity_record_id": head.semantic_payload["validity_record_id"],
    })
    with pytest.raises(ControlPlaneOperationError) as error:
        fixture.store.transition_validity(
            active_successor,
            expected_head_validity_record_id=head.semantic_payload["validity_record_id"])
    assert error.value.reason_code == "runtime_profile_validity_cas_conflict"
    assert fixture.store.get_validity_head(pointer.activation_record_id) == head


def test_classification_foundation_admission_must_match_pinned_foundation(tmp_path):
    fixture = _Fixture(tmp_path / "foundation-lineage.sqlite")
    admitted_a = fixture.admission("foundation", fixture.foundation_a)
    wrong = fixture.admission("classification", fixture.classification_b,
                              foundation_admission=admitted_a)
    activation, validity, _ = fixture.records(wrong, 41)
    with pytest.raises(ControlPlaneOperationError) as error:
        fixture.store.activate_profile(wrong, activation, validity)
    assert error.value.reason_code == "runtime_profile_dependency_unavailable"
    assert fixture.store.get_active_pointer("classification") is None


def test_foundation_enabled_tcp_requires_exact_durable_ttl_proof_before_begin(tmp_path):
    from app.device_fingerprint.runtime_profile_artifacts import (
        direct_artifact_refs, make_foundation_runtime_profile,
    )

    fixture = _Fixture(tmp_path / "ttl-lineage.sqlite")
    ttl = make_artifact_content("TTLCapturePlacementProof", {"synthetic_ff5_fixture_only": "ttl"})
    fixture.store.persist_artifact(ttl)
    origin = make_artifact_content("OriginRuntimeAdmission", {
        "origin_runtime_admission_contract_version": 1,
        "tcp_state": "ENABLED", "tcp_reason_code": "TTL_PROOF_VALID",
        "ttl_capture_placement_proof": ArtifactRef(ttl.artifact_id, ttl.content_sha256).as_dict(),
    })
    fixture.store.persist_artifact(origin)
    payload = fixture.foundation_a.semantic_payload
    payload["origin_runtime_admission"] = ArtifactRef(origin.artifact_id, origin.content_sha256).as_dict()
    missing_ttl = make_foundation_runtime_profile(payload)
    fixture.store.persist_artifact(missing_ttl, direct_artifact_refs(missing_ttl))
    missing_rpm = fixture.admission("foundation", missing_ttl)
    missing_records = fixture.records(missing_rpm, 51)
    stages = []
    fixture.store.fault_hook = stages.append
    with pytest.raises(ControlPlaneOperationError) as error:
        fixture.store.activate_profile(missing_rpm, missing_records[0], missing_records[1])
    assert error.value.reason_code == "runtime_profile_dependency_unavailable"
    assert stages == []
    payload["ttl_capture_placement_proof"] = ArtifactRef(ttl.artifact_id, ttl.content_sha256).as_dict()
    valid = make_foundation_runtime_profile(payload)
    fixture.store.persist_artifact(valid, direct_artifact_refs(valid))
    rpm = fixture.admission("foundation", valid)
    pointer, _, _, _ = fixture.activate(rpm, 52)
    assert pointer.runtime_profile_id == valid.artifact_id
