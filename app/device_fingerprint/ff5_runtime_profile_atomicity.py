"""Executable synthetic F-F5 atomicity proof; never connects to production."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from threading import Barrier
from typing import Any

from .artifact_content import ArtifactContent, ArtifactRef, canonical_set, make_artifact_content
from .control_plane_store import (
    ControlPlaneOperationError, DeviceFingerprintControlPlaneStore,
)
from .foundation_admission_artifacts import (
    MANDATORY_PRE_ADMISSION_GATES, make_architecture_contract_reference,
    make_foundation_admission_manifest,
)
from .foundation_gate_artifacts import make_gate_result_manifest
from .gate_proof_artifacts import make_gate_proof_artifact
from .models import DeviceFingerprintValidationError
from .runtime_profile_artifacts import (
    direct_artifact_refs, make_classification_runtime_profile,
    make_foundation_runtime_profile, make_runtime_profile_activation_record,
    make_runtime_profile_admission_manifest, make_runtime_profile_validity_record,
)

_AT = "2026-09-23T12:00:00.000Z"
_EVIDENCE_LABELS = (
    "runtime_profile_switch_pinning_trace",
    "runtime_profile_transaction_crash_point_trace",
    "runtime_profile_rollback_trace",
    "runtime_profile_cas_race_trace",
    "runtime_profile_restart_recovery_trace",
    "runtime_profile_compatibility_test_fixtures",
)
_CHECK_REASONS = {
    "fixture": "runtime_profile_fixture_invalid",
    "dependency": "runtime_profile_dependency_unavailable",
    "crash": "activation_crash_atomicity_failed",
    "pinning": "runtime_profile_pinning_failed",
    "rollback": "runtime_profile_rollback_failed",
    "validity_cas": "runtime_profile_validity_cas_failed",
    "activation_cas": "runtime_profile_activation_cas_failed",
    "aba": "runtime_profile_aba_protection_failed",
    "recovery": "runtime_profile_restart_recovery_failed",
    "transaction_only_record_visibility": "runtime_profile_transactional_visibility_failed",
    "inactive_active_pointer_fail_closed": "runtime_profile_restart_recovery_failed",
    "standalone_inactive_transition_forbidden": "runtime_profile_validity_cas_failed",
    "invalidated_activation_cannot_be_reenabled": "runtime_profile_pinning_failed",
    "inactive_predecessor_activation_fail_closed": "runtime_profile_restart_recovery_failed",
}


def _uuid(number: int) -> str:
    return str(uuid.UUID(int=number, version=4))


def _ref(content: ArtifactContent) -> dict[str, str]:
    return ArtifactRef(content.artifact_id, content.content_sha256).as_dict()


def _synthetic(kind: str, label: str) -> ArtifactContent:
    return make_artifact_content(kind, {"synthetic_ff5_fixture_only": label})


@dataclass(frozen=True, slots=True)
class FF5ScenarioExecution:
    fixture_artifact_refs: tuple[dict[str, str], ...]
    profile_switch_pinning_trace: dict[str, Any]
    transaction_crash_point_trace: dict[str, Any]
    rollback_trace: dict[str, Any]
    cas_race_trace: dict[str, Any]
    restart_recovery_trace: dict[str, Any]
    compatibility_test_fixtures: dict[str, Any]
    checks: dict[str, bool]
    failure_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FF5GateExecution:
    gate_proof_artifact: ArtifactContent
    gate_result_manifest: ArtifactContent
    failure_reasons: tuple[str, ...]


class _Fixture:
    """Clearly synthetic typed ArtifactContent graph, scoped to one disposable DB."""

    def __init__(self, database_path: Path, *, fault_hook=None):
        self.store = DeviceFingerprintControlPlaneStore(database_path, fault_hook=fault_hook)
        self.store.initialize()
        self.leaves: dict[str, ArtifactContent] = {}
        for kind in (
            "EvidenceSourceBindingTimeline", "BindingClockPolicy", "SourceHealthPolicy",
            "SnapshotContentPolicy", "SnapshotExecutionPolicy", "EvidenceSchemaRegistryContract",
            "Task01HealthRetentionContract", "SourceHealthEmitterContract",
            "KnowledgeBundle", "ClassificationPolicy", "EvidenceAdapterContractSet",
            "ClassifierArtifactManifest", "Task04AcceptanceManifest",
        ):
            content = _synthetic(kind, kind)
            self.leaves[kind] = content
            self.store.persist_artifact(content)
        disabled_origin = make_artifact_content("OriginRuntimeAdmission", {
            "origin_runtime_admission_contract_version": 1,
            "tcp_state": "DISABLED", "tcp_reason_code": "PROFILE_POLICY_DISABLED",
            "ttl_capture_placement_proof": None,
        })
        self.leaves["OriginRuntimeAdmission"] = disabled_origin
        self.store.persist_artifact(disabled_origin)
        architecture = make_architecture_contract_reference({
            "architecture_contract_name": "DEVICE-FINGERPRINT-03A-R2 / TASK-04",
            "architecture_revision": "R14", "architecture_status": "FINAL",
            "architecture_document_sha256": "d" * 64,
        })
        self.leaves["ArchitectureContractReference"] = architecture
        self.store.persist_artifact(architecture)

        def synthetic_ref(kind: str, label: str) -> dict[str, str]:
            return _ref(self.leaves.get(kind) or _synthetic(kind, label))

        manifest = make_foundation_admission_manifest({
            "foundation_manifest_version": 1,
            "architecture_contract_reference": _ref(architecture),
            "architecture_document_sha256": architecture.semantic_payload["architecture_document_sha256"],
            "foundation_repository_commit_sha": "a" * 40,
            "foundation_repository_tree_sha": "b" * 40,
            "foundation_knowledge_evaluation_at_utc": _AT,
            "foundation_admission_evaluation_at_utc": _AT,
            "classification_foundation_valid_from_utc": _AT,
            "task01_database_schema_generation_contract_version": 2,
            "task01_watermark_generation_contract_version": 2,
            "mandatory_pre_admission_foundation_gate_ids": list(MANDATORY_PRE_ADMISSION_GATES),
            "pre_admission_gate_result_manifests": [
                synthetic_ref("GateResultManifest", f"ff5-disposable-{gate_id}")
                for gate_id in MANDATORY_PRE_ADMISSION_GATES
            ],
            "evidence_schema_registry_contract": synthetic_ref("EvidenceSchemaRegistryContract", "registry"),
            "evidence_adapter_contract_set": synthetic_ref("EvidenceAdapterContractSet", "adapter"),
            "knowledge_bundle": synthetic_ref("KnowledgeBundle", "knowledge"),
            "evidence_source_binding_timeline": synthetic_ref("EvidenceSourceBindingTimeline", "binding"),
            "binding_clock_policy": synthetic_ref("BindingClockPolicy", "clock"),
            "source_health_policy": synthetic_ref("SourceHealthPolicy", "health"),
            "source_health_emitter_contracts": [synthetic_ref("SourceHealthEmitterContract", "emitter")],
            "snapshot_content_policy": synthetic_ref("SnapshotContentPolicy", "snapshot-content"),
            "snapshot_execution_policy": synthetic_ref("SnapshotExecutionPolicy", "snapshot-execution"),
            "classification_policy": synthetic_ref("ClassificationPolicy", "classification"),
            "classification_retention_policy": synthetic_ref("ClassificationRetentionPolicy", "retention"),
            "product_validation_policy": synthetic_ref("ProductValidationPolicy", "product-validation"),
            "knowledge_freshness_policies": [synthetic_ref("KnowledgeFreshnessPolicy", "freshness")],
            "source_governance_records": [synthetic_ref("SourceGovernanceRecord", "governance")],
            "knowledge_provenance_manifests": [synthetic_ref("KnowledgeProvenanceManifest", "provenance")],
            "k2a_conformance_package": synthetic_ref("K2AConformancePackage", "k2a"),
            "ttl_capture_placement_proof": synthetic_ref("TTLCapturePlacementProof", "ttl"),
            "origin_runtime_admission": _ref(disabled_origin),
            "portal_headers_v2_capability_disposition": synthetic_ref("CapabilityDisposition", "portal-v2"),
        })
        self.leaves["FoundationAdmissionManifest"] = manifest
        self.store.persist_artifact(manifest)
        second_clock = _synthetic("BindingClockPolicy", "alternate synthetic clock fixture")
        self.store.persist_artifact(second_clock)
        self.leaves["alternate_clock"] = second_clock
        self.foundation_a = self.foundation("A")
        self.foundation_b = self.foundation("B")
        self.foundation_c = self.foundation("C")
        self.classification_a = self.classification(self.foundation_a, "A")
        self.classification_b = self.classification(self.foundation_b, "B")

    def foundation(self, label: str) -> ArtifactContent:
        leaves = self.leaves
        payload = {
            "foundation_profile_contract_version": 1,
            "evidence_source_binding_timeline": _ref(leaves["EvidenceSourceBindingTimeline"]),
            "binding_clock_policy": _ref(leaves["alternate_clock"] if label != "A"
                                         else leaves["BindingClockPolicy"]),
            "source_health_policy": _ref(leaves["SourceHealthPolicy"]),
            "snapshot_content_policy": _ref(leaves["SnapshotContentPolicy"]),
            "snapshot_execution_policy": _ref(leaves["SnapshotExecutionPolicy"]),
            "evidence_schema_registry_contract": _ref(leaves["EvidenceSchemaRegistryContract"]),
            "task01_health_retention_contract": _ref(leaves["Task01HealthRetentionContract"]),
            "origin_runtime_admission": _ref(leaves["OriginRuntimeAdmission"]),
            "classification_foundation_valid_from_utc": _AT,
            "source_health_emitter_contracts": [_ref(leaves["SourceHealthEmitterContract"])],
            "ttl_capture_placement_proof": None,
            "snapshot_contract_version": 2 if label == "C" else 1,
        }
        content = make_foundation_runtime_profile(payload)
        self.store.persist_artifact(content, direct_artifact_refs(content))
        return content

    def classification(self, foundation: ArtifactContent, label: str) -> ArtifactContent:
        content = make_classification_runtime_profile({
            "classification_runtime_profile_contract_version": 1,
            "foundation_runtime_profile": _ref(foundation),
            "knowledge_bundle": _ref(self.leaves["KnowledgeBundle"]),
            "classification_policy": _ref(self.leaves["ClassificationPolicy"]),
            "evidence_adapter_contract_set": _ref(self.leaves["EvidenceAdapterContractSet"]),
            "classifier_artifact_manifest": _ref(self.leaves["ClassifierArtifactManifest"]),
        })
        self.store.persist_artifact(content, direct_artifact_refs(content))
        return content

    def admission(self, kind: str, candidate: ArtifactContent, previous=None,
                  update_class: str | None = None, foundation_admission=None) -> ArtifactContent:
        initial = previous is None
        update = update_class or (f"INITIAL_{kind.upper()}" if initial else "BINDING_TIMELINE_CHANGE")
        content = make_runtime_profile_admission_manifest({
            "runtime_profile_admission_contract_version": 1,
            "profile_kind": kind,
            "candidate_profile": _ref(candidate),
            "previous_active_profile": None if initial else {
                "artifact_id": previous.runtime_profile_id,
                "content_sha256": previous.runtime_profile_digest,
            },
            "expected_previous_activation_record_id": None if initial else previous.activation_record_id,
            "expected_previous_activation_generation_id": None if initial else previous.activation_generation_id,
            "update_class": update,
            "prerequisite_gate_results": [],
            "compatibility_validation_result": "PASS",
            "candidate_repository_commit_sha": "a" * 40,
            "candidate_repository_tree_sha": "b" * 40,
            "foundation_admission_manifest": _ref(self.leaves["FoundationAdmissionManifest"]),
            "task04_acceptance_manifest": (_ref(self.leaves["Task04AcceptanceManifest"])
                                          if kind == "classification" else None),
            "foundation_runtime_profile_admission_manifest": (_ref(foundation_admission)
                                                               if kind == "classification" else None),
        })
        self.store.persist_artifact(content, direct_artifact_refs(content))
        return content

    def records(self, rpm: ArtifactContent, number: int, previous_head=None):
        rp = rpm.semantic_payload
        candidate = rp["candidate_profile"]
        previous = rp["previous_active_profile"]
        activation_id = _uuid(number * 10 + 1)
        activation = make_runtime_profile_activation_record({
            "activation_contract_version": 1,
            "activation_record_id": activation_id,
            "profile_kind": rp["profile_kind"],
            "runtime_profile_id": candidate["artifact_id"],
            "runtime_profile_digest": candidate["content_sha256"],
            "runtime_profile_admission_manifest_id": rpm.artifact_id,
            "runtime_profile_admission_manifest_digest": rpm.content_sha256,
            "previous_activation_record_id": rp["expected_previous_activation_record_id"],
            "previous_active_profile_id": None if previous is None else previous["artifact_id"],
            "previous_active_profile_digest": None if previous is None else previous["content_sha256"],
            "activated_at_utc": _AT,
            "activation_reason_update_class": rp["update_class"],
            "activation_result": "ACTIVE",
            "activation_generation_id": _uuid(number * 10 + 2),
        })
        initial = make_runtime_profile_validity_record({
            "runtime_profile_validity_contract_version": 1,
            "validity_record_id": _uuid(number * 10 + 3),
            "profile_kind": rp["profile_kind"],
            "runtime_profile_id": candidate["artifact_id"],
            "runtime_profile_digest": candidate["content_sha256"],
            "activation_record_id": activation_id,
            "state": "ACTIVE",
            "reason_code": ("ROLLBACK_REACTIVATED" if rp["update_class"] == "ROLLBACK_REACTIVATION"
                            else "ACTIVATED"),
            "effective_at_utc": _AT,
            "inflight_commit_rule": "ALLOW_PINNED_INFLIGHT",
            "previous_validity_record_id": None,
        })
        inactive = None
        if previous_head is not None:
            old = previous_head.semantic_payload
            inactive = make_runtime_profile_validity_record({
                **old,
                "validity_record_id": _uuid(number * 10 + 4),
                "state": "INACTIVE",
                "reason_code": "SUPERSEDED_SAFE",
                "inflight_commit_rule": "ALLOW_PINNED_INFLIGHT",
                "previous_validity_record_id": old["validity_record_id"],
            })
        return activation, initial, inactive

    def activate(self, rpm: ArtifactContent, number: int, previous_head=None):
        activation, initial, inactive = self.records(rpm, number, previous_head)
        pointer = self.store.activate_profile(
            rpm, activation, initial, predecessor_inactive_validity_record=inactive)
        return pointer, activation, initial, inactive


def _success_or_reason(callback) -> str:
    try:
        callback()
        return "success"
    except ControlPlaneOperationError as exc:
        return exc.reason_code


def _transaction_only_rejected(callback) -> bool:
    try:
        callback()
    except DeviceFingerprintValidationError as exc:
        return str(exc) == "Runtime control-plane record requires transactional mutation"
    return False


def _run_scenarios(root: Path) -> tuple[dict[str, bool], dict[str, Any], tuple[dict[str, str], ...]]:
    checks: dict[str, bool] = {}
    trace: dict[str, Any] = {}
    fixture = _Fixture(root / "switch.sqlite")
    store = fixture.store
    rpm_a = fixture.admission("foundation", fixture.foundation_a)
    pointer_a, _, _, _ = fixture.activate(rpm_a, 1)
    old_pin = store.pin_active_profile("foundation")
    rpm_c = fixture.admission("classification", fixture.classification_a,
                              foundation_admission=rpm_a)
    class_pointer, _, _, _ = fixture.activate(rpm_c, 11)
    checks["fixture"] = (
        old_pin.runtime_profile.artifact_id == fixture.foundation_a.artifact_id
        and store.pin_active_profile("classification").pointer == class_pointer
        and "task04_acceptance_manifest" not in fixture.classification_a.semantic_payload
        and "foundation_admission_manifest" not in fixture.foundation_a.semantic_payload)
    rpm_b = fixture.admission("foundation", fixture.foundation_b, pointer_a)
    proof_inputs = (fixture.foundation_a, fixture.foundation_b, fixture.foundation_c,
                    fixture.classification_a, fixture.classification_b, rpm_a, rpm_b, rpm_c)
    pointer_b, _, _, _ = fixture.activate(rpm_b, 2, store.get_validity_head(pointer_a.activation_record_id))
    new_pin = store.pin_active_profile("foundation")
    checks["pinning"] = (old_pin.pointer == pointer_a and new_pin.pointer == pointer_b
                         and store.check_pinned_commit_allowed(old_pin)
                         and store.get_validity_head(pointer_a.activation_record_id).semantic_payload["state"] == "INACTIVE")
    validity_b = store.get_validity_head(pointer_b.activation_record_id)
    invalidated = make_runtime_profile_validity_record({
        **validity_b.semantic_payload,
        "validity_record_id": _uuid(35),
        "state": "SUSPENDED_INVALIDATED", "reason_code": "EXPLICIT_POLICY_SUSPEND",
        "inflight_commit_rule": "REJECT_PINNED_INFLIGHT",
        "previous_validity_record_id": validity_b.semantic_payload["validity_record_id"],
    })
    store.transition_validity(invalidated,
                              expected_head_validity_record_id=validity_b.semantic_payload["validity_record_id"])
    checks["pinning"] &= (_success_or_reason(lambda: store.check_pinned_commit_allowed(new_pin))
                          == "runtime_profile_invalidated")
    trace["pinning"] = {"old": pointer_a.runtime_profile_id, "new": pointer_b.runtime_profile_id,
                        "old_safe": True, "new_invalidated": True}

    visibility = _Fixture(root / "record-visibility.sqlite")
    visibility_rpm = visibility.admission("foundation", visibility.foundation_a)
    activation, initial, _ = visibility.records(visibility_rpm, 51)
    visibility_checks = [
        _transaction_only_rejected(lambda: visibility.store.persist_artifact(activation)),
        _transaction_only_rejected(lambda: visibility.store.persist_artifact(initial)),
        _success_or_reason(lambda: visibility.store.load_artifact(activation.artifact_id))
        == "runtime_profile_dependency_unavailable",
        _success_or_reason(lambda: visibility.store.load_artifact(initial.artifact_id))
        == "runtime_profile_dependency_unavailable",
        visibility.store.get_active_pointer("foundation") is None,
    ]
    visibility_pointer = visibility.store.activate_profile(visibility_rpm, activation, initial)
    visibility_checks.extend([
        visibility.store.load_artifact(activation.artifact_id) == activation,
        visibility.store.load_artifact(initial.artifact_id) == initial,
        visibility.store.get_validity_head(visibility_pointer.activation_record_id) == initial,
        visibility.store.get_active_pointer("foundation") == visibility_pointer,
    ])
    successor = make_runtime_profile_validity_record({
        **initial.semantic_payload,
        "validity_record_id": _uuid(514),
        "state": "SUSPENDED_INVALIDATED", "reason_code": "EXPLICIT_POLICY_SUSPEND",
        "inflight_commit_rule": "REJECT_PINNED_INFLIGHT",
        "previous_validity_record_id": initial.semantic_payload["validity_record_id"],
    })
    visibility_checks.extend([
        _transaction_only_rejected(lambda: visibility.store.persist_artifact(successor)),
        _success_or_reason(lambda: visibility.store.load_artifact(successor.artifact_id))
        == "runtime_profile_dependency_unavailable",
    ])
    visibility.store.transition_validity(
        successor, expected_head_validity_record_id=initial.semantic_payload["validity_record_id"])
    visibility_checks.extend([
        visibility.store.load_artifact(successor.artifact_id) == successor,
        visibility.store.get_validity_head(visibility_pointer.activation_record_id) == successor,
    ])
    checks["transaction_only_record_visibility"] = all(visibility_checks)

    standalone = _Fixture(root / "standalone-inactive.sqlite")
    standalone_rpm_a = standalone.admission("foundation", standalone.foundation_a)
    standalone_a, _, standalone_head, _ = standalone.activate(standalone_rpm_a, 53)
    standalone_pin = standalone.store.pin_active_profile("foundation")
    forbidden_inactive = make_runtime_profile_validity_record({
        **standalone_head.semantic_payload,
        "validity_record_id": _uuid(534),
        "state": "INACTIVE", "reason_code": "SUPERSEDED_SAFE",
        "inflight_commit_rule": "ALLOW_PINNED_INFLIGHT",
        "previous_validity_record_id": standalone_head.semantic_payload["validity_record_id"],
    })
    checks["standalone_inactive_transition_forbidden"] = (
        _success_or_reason(lambda: standalone.store.transition_validity(
            forbidden_inactive, expected_head_validity_record_id=
            standalone_head.semantic_payload["validity_record_id"]))
        == "runtime_profile_validity_cas_conflict"
        and _success_or_reason(lambda: standalone.store.load_artifact(forbidden_inactive.artifact_id))
        == "runtime_profile_dependency_unavailable"
        and standalone.store.get_active_pointer("foundation") == standalone_a
        and standalone.store.get_validity_head(standalone_a.activation_record_id) == standalone_head)
    standalone.store.validate_startup_integrity()
    checks["standalone_inactive_transition_forbidden"] &= (
        standalone.store.pin_active_profile("foundation").pointer == standalone_a)
    suspended = make_runtime_profile_validity_record({
        **standalone_head.semantic_payload,
        "validity_record_id": _uuid(535),
        "state": "SUSPENDED_INVALIDATED", "reason_code": "EXPLICIT_POLICY_SUSPEND",
        "inflight_commit_rule": "REJECT_PINNED_INFLIGHT",
        "previous_validity_record_id": standalone_head.semantic_payload["validity_record_id"],
    })
    standalone.store.transition_validity(
        suspended, expected_head_validity_record_id=standalone_head.semantic_payload["validity_record_id"])
    forbidden_after_suspension = make_runtime_profile_validity_record({
        **suspended.semantic_payload,
        "validity_record_id": _uuid(536),
        "state": "INACTIVE", "reason_code": "SUPERSEDED_SAFE",
        "inflight_commit_rule": "ALLOW_PINNED_INFLIGHT",
        "previous_validity_record_id": suspended.semantic_payload["validity_record_id"],
    })
    checks["invalidated_activation_cannot_be_reenabled"] = (
        _success_or_reason(lambda: standalone.store.check_pinned_commit_allowed(standalone_pin))
        == "runtime_profile_invalidated"
        and _success_or_reason(lambda: standalone.store.transition_validity(
            forbidden_after_suspension, expected_head_validity_record_id=
            suspended.semantic_payload["validity_record_id"]))
        == "runtime_profile_validity_cas_conflict"
        and standalone.store.get_validity_head(standalone_a.activation_record_id) == suspended
        and _success_or_reason(lambda: standalone.store.check_pinned_commit_allowed(standalone_pin))
        == "runtime_profile_invalidated")
    replacement_rpm = standalone.admission("foundation", standalone.foundation_b, standalone_a)
    replacement, _, _, _ = standalone.activate(replacement_rpm, 54)
    checks["invalidated_activation_cannot_be_reenabled"] &= (
        replacement.runtime_profile_id == standalone.foundation_b.artifact_id
        and standalone.store.get_validity_head(standalone_a.activation_record_id) == suspended)
    trace["pinning"].update({
        "standalone_inactive_transition_forbidden": checks["standalone_inactive_transition_forbidden"],
        "invalidated_activation_cannot_be_reenabled": checks["invalidated_activation_cannot_be_reenabled"],
    })

    crash_trace = {}
    for index, stage in enumerate(("BEFORE_BEGIN", "AFTER_BEGIN_BEFORE_WRITES",
                                   "AFTER_WRITES_BEFORE_COMMIT", "AFTER_COMMIT"), start=1):
        f = _Fixture(root / f"crash-{index}.sqlite")
        base = f.admission("foundation", f.foundation_a)
        before, _, _, _ = f.activate(base, 100 + index)
        next_rpm = f.admission("foundation", f.foundation_b, before)
        next_records = f.records(next_rpm, 200 + index, f.store.get_validity_head(before.activation_record_id))

        def fault(observed, expected=stage):
            if observed == expected:
                raise RuntimeError(f"synthetic crash {expected}")

        f.store.fault_hook = fault
        try:
            f.store.activate_profile(next_rpm, next_records[0], next_records[1],
                                     predecessor_inactive_validity_record=next_records[2])
            crash_trace[stage] = False
        except RuntimeError:
            f.store.fault_hook = None
            current = f.store.get_active_pointer("foundation")
            wanted = next_records[0].semantic_payload["activation_record_id"]
            committed = stage == "AFTER_COMMIT"
            crash_trace[stage] = (current.activation_record_id == wanted if committed else current == before)
            crash_trace[stage] &= (f.store.get_validity_head(wanted) is not None) == committed
            f.store.validate_startup_integrity()
    checks["crash"] = all(crash_trace.values())
    trace["crash"] = crash_trace

    rollback_fixture = _Fixture(root / "rollback.sqlite")
    f = rollback_fixture
    rpm_a = f.admission("foundation", f.foundation_a)
    epoch_x, _, _, _ = f.activate(rpm_a, 301)
    stale_rpm = f.admission("foundation", f.foundation_b, epoch_x)
    rpm_b = stale_rpm
    epoch_b, _, _, _ = f.activate(rpm_b, 302, f.store.get_validity_head(epoch_x.activation_record_id))
    rollback_rpm = f.admission("foundation", f.foundation_a, epoch_b,
                               update_class="ROLLBACK_REACTIVATION")
    epoch_y, _, _, _ = f.activate(rollback_rpm, 303, f.store.get_validity_head(epoch_b.activation_record_id))
    checks["rollback"] = (epoch_x.runtime_profile_id == epoch_y.runtime_profile_id
                          and epoch_x.activation_record_id != epoch_y.activation_record_id
                          and epoch_x.activation_generation_id != epoch_y.activation_generation_id)
    stale_activation = f.records(stale_rpm, 304, f.store.get_validity_head(epoch_x.activation_record_id))
    checks["aba"] = (_success_or_reason(lambda: f.store.activate_profile(
        stale_rpm, stale_activation[0], stale_activation[1],
        predecessor_inactive_validity_record=stale_activation[2]))
        == "active_profile_precondition_mismatch")
    rollback_crash = _Fixture(root / "rollback-crash.sqlite")
    crash_a = rollback_crash.admission("foundation", rollback_crash.foundation_a)
    crash_pointer_a, _, _, _ = rollback_crash.activate(crash_a, 311)
    crash_b = rollback_crash.admission("foundation", rollback_crash.foundation_b, crash_pointer_a)
    crash_pointer_b, _, _, _ = rollback_crash.activate(
        crash_b, 312, rollback_crash.store.get_validity_head(crash_pointer_a.activation_record_id))
    crash_rollback = rollback_crash.admission(
        "foundation", rollback_crash.foundation_a, crash_pointer_b,
        update_class="ROLLBACK_REACTIVATION")
    crash_rollback_records = rollback_crash.records(
        crash_rollback, 313, rollback_crash.store.get_validity_head(crash_pointer_b.activation_record_id))

    def rollback_fault(stage):
        if stage == "AFTER_WRITES_BEFORE_COMMIT":
            raise RuntimeError("synthetic rollback crash")

    rollback_crash.store.fault_hook = rollback_fault
    try:
        rollback_crash.store.activate_profile(
            crash_rollback, crash_rollback_records[0], crash_rollback_records[1],
            predecessor_inactive_validity_record=crash_rollback_records[2])
        checks["rollback"] = False
    except RuntimeError:
        rollback_crash.store.fault_hook = None
        checks["rollback"] &= (
            rollback_crash.store.get_active_pointer("foundation") == crash_pointer_b
            and rollback_crash.store.get_validity_head(
                crash_rollback_records[0].semantic_payload["activation_record_id"]) is None)
    trace["rollback"] = {"epoch_x": epoch_x.activation_record_id,
                         "epoch_b": epoch_b.activation_record_id,
                         "epoch_y": epoch_y.activation_record_id}

    race = _Fixture(root / "races.sqlite")
    first_rpm = race.admission("foundation", race.foundation_a)
    first_pointer, _, _, _ = race.activate(first_rpm, 401)
    head = race.store.get_validity_head(first_pointer.activation_record_id)
    race_rpms = [race.admission("foundation", candidate, first_pointer)
                 for candidate in (race.foundation_b, race.foundation_c)]
    race_records = [race.records(rpm, 402 + index, head) for index, rpm in enumerate(race_rpms)]
    barrier = Barrier(2)

    def activation_attempt(index):
        contender = DeviceFingerprintControlPlaneStore(race.store.database_path)
        barrier.wait()
        records = race_records[index]
        return _success_or_reason(lambda: contender.activate_profile(
            race_rpms[index], records[0], records[1],
            predecessor_inactive_validity_record=records[2]))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(activation_attempt, range(2)))
    checks["activation_cas"] = sorted(results) == ["active_profile_precondition_mismatch", "success"]
    for index, result in enumerate(results):
        if result != "success":
            losing_activation = race_records[index][0]
            losing_id = losing_activation.semantic_payload["activation_record_id"]
            checks["activation_cas"] &= race.store.get_validity_head(losing_id) is None
            checks["activation_cas"] &= (_success_or_reason(lambda artifact=losing_activation:
                race.store.load_artifact(artifact.artifact_id))
                == "runtime_profile_dependency_unavailable")
    winning = race.store.get_active_pointer("foundation")
    winning_head = race.store.get_validity_head(winning.activation_record_id)
    successor_payload = winning_head.semantic_payload
    successors = [make_runtime_profile_validity_record({
        **successor_payload,
        "validity_record_id": _uuid(450 + index),
        "state": "SUSPENDED_INVALIDATED", "reason_code": "EXPLICIT_POLICY_SUSPEND",
        "inflight_commit_rule": "REJECT_PINNED_INFLIGHT",
        "previous_validity_record_id": successor_payload["validity_record_id"],
    }) for index in range(2)]
    barrier = Barrier(2)

    def validity_attempt(index):
        contender = DeviceFingerprintControlPlaneStore(race.store.database_path)
        barrier.wait()
        return _success_or_reason(lambda: contender.transition_validity(
            successors[index], expected_head_validity_record_id=successor_payload["validity_record_id"]))

    with ThreadPoolExecutor(max_workers=2) as pool:
        validity_results = list(pool.map(validity_attempt, range(2)))
    checks["validity_cas"] = sorted(validity_results) == ["runtime_profile_validity_cas_conflict", "success"]
    for index, result in enumerate(validity_results):
        if result != "success":
            checks["validity_cas"] &= (_success_or_reason(lambda artifact=successors[index]:
                race.store.load_artifact(artifact.artifact_id))
                == "runtime_profile_dependency_unavailable")
    stale_records = race.records(race_rpms[0], 409, race.store.get_validity_head(first_pointer.activation_record_id))
    checks["activation_cas"] &= (_success_or_reason(lambda: race.store.activate_profile(
        race_rpms[0], stale_records[0], stale_records[1],
        predecessor_inactive_validity_record=stale_records[2]))
        == "active_profile_precondition_mismatch")
    trace["races"] = {"activation": sorted(results), "validity": sorted(validity_results)}

    restarted = DeviceFingerprintControlPlaneStore(race.store.database_path)
    restarted.validate_startup_integrity()
    checks["recovery"] = (restarted.get_active_pointer("foundation") == winning
                          and _success_or_reason(lambda: restarted.pin_active_profile("foundation"))
                          == "runtime_profile_invalidated")
    with sqlite3.connect(race.store.database_path) as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("DELETE FROM validity_heads WHERE activation_record_id=?", (winning.activation_record_id,))
    checks["recovery"] &= (_success_or_reason(restarted.validate_startup_integrity)
                           == "activation_lineage_unavailable")
    missing_activation = _Fixture(root / "missing-activation.sqlite")
    missing_rpm = missing_activation.admission("foundation", missing_activation.foundation_a)
    missing_pointer, _, _, _ = missing_activation.activate(missing_rpm, 460)
    with sqlite3.connect(missing_activation.store.database_path) as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("DELETE FROM activations WHERE activation_record_id=?",
                     (missing_pointer.activation_record_id,))
    checks["recovery"] &= (_success_or_reason(missing_activation.store.validate_startup_integrity)
                           == "activation_lineage_unavailable")
    missing_dependency = _Fixture(root / "missing-dependency-recovery.sqlite")
    dependency_rpm = missing_dependency.admission("foundation", missing_dependency.foundation_a)
    missing_dependency.activate(dependency_rpm, 470)
    with sqlite3.connect(missing_dependency.store.database_path) as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("DELETE FROM artifacts WHERE artifact_id=?",
                     (missing_dependency.leaves["BindingClockPolicy"].artifact_id,))
    checks["recovery"] &= (_success_or_reason(missing_dependency.store.validate_startup_integrity)
                           == "activation_lineage_unavailable")
    inactive = _Fixture(root / "inactive-pointer-corruption.sqlite")
    inactive_rpm_a = inactive.admission("foundation", inactive.foundation_a)
    inactive_a, _, _, _ = inactive.activate(inactive_rpm_a, 480)
    inactive_rpm_b = inactive.admission("foundation", inactive.foundation_b, inactive_a)
    inactive.activate(inactive_rpm_b, 481, inactive.store.get_validity_head(inactive_a.activation_record_id))
    old_head = inactive.store.get_validity_head(inactive_a.activation_record_id)
    with sqlite3.connect(inactive.store.database_path) as conn:
        conn.execute("UPDATE active_pointers SET runtime_profile_id=?, runtime_profile_digest=?, "
                     "activation_record_id=?, activation_generation_id=? WHERE profile_kind=?", (
                         inactive_a.runtime_profile_id, inactive_a.runtime_profile_digest,
                         inactive_a.activation_record_id, inactive_a.activation_generation_id,
                         inactive_a.profile_kind))
    checks["inactive_active_pointer_fail_closed"] = (
        old_head.semantic_payload["state"] == "INACTIVE"
        and _success_or_reason(inactive.store.validate_startup_integrity)
        == "activation_lineage_unavailable"
        and _success_or_reason(lambda: inactive.store.pin_active_profile("foundation"))
        == "activation_lineage_unavailable")
    corrupt_activation, corrupt_initial, _ = inactive.records(inactive_rpm_b, 482)
    checks["inactive_predecessor_activation_fail_closed"] = (
        _success_or_reason(lambda: inactive.store.activate_profile(
            inactive_rpm_b, corrupt_activation, corrupt_initial))
        == "activation_lineage_unavailable"
        and inactive.store.get_active_pointer("foundation") == inactive_a
        and inactive.store.get_validity_head(inactive_a.activation_record_id) == old_head
        and inactive.store.get_validity_head(corrupt_activation.semantic_payload["activation_record_id"]) is None
        and _success_or_reason(lambda: inactive.store.load_artifact(corrupt_activation.artifact_id))
        == "runtime_profile_dependency_unavailable")
    trace["recovery"] = {
        "reopen": True, "missing_head_fail_closed": checks["recovery"],
        "inactive_active_pointer_fail_closed": checks["inactive_active_pointer_fail_closed"],
        "inactive_predecessor_activation_fail_closed": checks["inactive_predecessor_activation_fail_closed"],
    }
    trace["crash"]["transaction_only_record_visibility"] = checks["transaction_only_record_visibility"]

    missing = _Fixture(root / "missing-dependency.sqlite")
    m_rpm = missing.admission("foundation", missing.foundation_a)
    m_records = missing.records(m_rpm, 501)
    with sqlite3.connect(missing.store.database_path) as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("DELETE FROM artifacts WHERE artifact_id=?",
                     (missing.leaves["BindingClockPolicy"].artifact_id,))
    reached_begin = []
    missing.store.fault_hook = reached_begin.append
    checks["dependency"] = (_success_or_reason(lambda: missing.store.activate_profile(
        m_rpm, m_records[0], m_records[1])) == "runtime_profile_dependency_unavailable"
        and not reached_begin and missing.store.get_active_pointer("foundation") is None)
    trace["dependency"] = {"failure_before_begin": checks["dependency"]}

    refs = tuple(ArtifactRef(content.artifact_id, content.content_sha256).as_dict()
                 for content in proof_inputs)
    return checks, trace, refs


def execute_ff5_runtime_profile_atomicity_scenarios(
    *, working_directory: str | Path, candidate_repository_commit_sha: str,
    candidate_repository_tree_sha: str,
) -> FF5ScenarioExecution:
    """Run deterministic disposable DB scenarios; no production path or network."""
    root = Path(working_directory)
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="synthetic-ff5-", dir=root) as ephemeral:
        checks, trace, refs = _run_scenarios(Path(ephemeral))
    ordered_refs = canonical_set(list(refs), lambda ref: ref["artifact_id"])
    reasons = tuple(sorted(_CHECK_REASONS[key] for key, passed in checks.items() if not passed))
    return FF5ScenarioExecution(
        tuple(ordered_refs), trace["pinning"], trace["crash"], trace["rollback"],
        trace["races"], trace["recovery"],
        {"synthetic_only": True, "candidate_commit": candidate_repository_commit_sha,
         "candidate_tree": candidate_repository_tree_sha, **trace["dependency"]},
        checks, reasons,
    )


def run_ff5_runtime_profile_atomicity_gate(
    execution: FF5ScenarioExecution, *, candidate_repository_commit_sha: str,
    candidate_repository_tree_sha: str, environment_identity: str,
    retained_evidence_refs: list[dict[str, Any]],
) -> FF5GateExecution:
    """Materialize proof and F-F5 result; synthetic fixture refs are not admission."""
    if not isinstance(execution, FF5ScenarioExecution):
        raise DeviceFingerprintValidationError("Invalid F-F5 execution")
    if not isinstance(retained_evidence_refs, list):
        raise DeviceFingerprintValidationError("Invalid F-F5 evidence")
    reasons = list(execution.failure_reasons)
    required_checks = set(_CHECK_REASONS)
    if (not isinstance(execution.checks, dict) or set(execution.checks) != required_checks
            or any(type(value) is not bool for value in execution.checks.values())
            or not execution.fixture_artifact_refs
            or not all(isinstance(trace, dict) and trace for trace in (
                execution.profile_switch_pinning_trace,
                execution.transaction_crash_point_trace,
                execution.rollback_trace, execution.cas_race_trace,
                execution.restart_recovery_trace, execution.compatibility_test_fixtures))
            or execution.compatibility_test_fixtures.get("synthetic_only") is not True
            or execution.compatibility_test_fixtures.get("candidate_commit") != candidate_repository_commit_sha
            or execution.compatibility_test_fixtures.get("candidate_tree") != candidate_repository_tree_sha):
        reasons.append("runtime_profile_fixture_invalid")
    if not retained_evidence_refs:
        reasons.append("retained_evidence_required")
    for row in retained_evidence_refs:
        if not isinstance(row, dict) or not isinstance(row.get("evidence_label"), str):
            raise DeviceFingerprintValidationError("Invalid F-F5 evidence")
    for label in _EVIDENCE_LABELS:
        if sum(row["evidence_label"] == label for row in retained_evidence_refs) != 1:
            reasons.append(f"{label}_required")
    if isinstance(execution.checks, dict) and not all(execution.checks.values()):
        reasons.extend(_CHECK_REASONS[key] for key, value in execution.checks.items()
                       if not value and key in _CHECK_REASONS)
    reasons = sorted(set(reasons))
    # Generic manifest validation owns the evidence-row shape. Identical
    # mandatory duplicates must produce FAIL, not a duplicate-SET exception.
    evidence_rows = []
    seen = set()
    for row in retained_evidence_refs:
        identity = (row["evidence_label"], json.dumps(row, sort_keys=True, default=str))
        if row["evidence_label"] in _EVIDENCE_LABELS and identity in seen:
            continue
        seen.add(identity)
        evidence_rows.append(row)
    proof_identity = {
        "execution_id": str(uuid.uuid4()), "executor_kind": "TECHLEAD_GATE_TOOL",
        "repository_commit_sha": candidate_repository_commit_sha,
        "repository_tree_sha": candidate_repository_tree_sha,
        "procedure_or_test_suite_id": "F-F5-runtime-profile-atomicity-v1",
        "environment_identity": environment_identity, "execution_artifact_sha256": None,
    }
    proof = make_gate_proof_artifact({
        "proof_kind": "RUNTIME_PROFILE_ATOMICITY", "source_gate_id": "F-F5",
        "candidate_repository_commit_sha": candidate_repository_commit_sha,
        "candidate_repository_tree_sha": candidate_repository_tree_sha,
        "input_artifact_refs": list(execution.fixture_artifact_refs),
        "procedure_or_test_suite_id": "F-F5-runtime-profile-atomicity-v1",
        "proof_execution_identity": proof_identity,
        "canonical_result_summary": json.dumps({"checks": execution.checks,
                                                "failure_reasons": reasons}, sort_keys=True, separators=(",", ":")),
        "retained_evidence_refs": evidence_rows,
    })
    manifest = make_gate_result_manifest({
        "gate_id": "F-F5", "gate_contract_version": "R14-F-F5-v1",
        "status": "FAIL" if reasons else "PASS",
        "candidate_repository_commit_sha": candidate_repository_commit_sha,
        "candidate_repository_tree_sha": candidate_repository_tree_sha,
        "input_artifact_refs": list(execution.fixture_artifact_refs),
        "output_artifact_refs": [_ref(proof)] if not reasons else [],
        "retained_evidence_refs": evidence_rows,
        "proof_execution_identity": {**proof_identity, "execution_id": str(uuid.uuid4()),
                                     "procedure_or_test_suite_id": "F-F5-runtime-profile-atomicity-gate-v1"},
        "trusted_time_inputs": {
            "foundation_knowledge_evaluation_at_utc": None,
            "foundation_admission_evaluation_at_utc": None,
            "knowledge_evaluation_at_utc": None,
        },
        "decision_record_refs": [],
    })
    return FF5GateExecution(proof, manifest, tuple(reasons))
