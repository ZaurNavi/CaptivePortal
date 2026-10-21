"""Atomic immutable closure, replay and reference-aware retention tests."""

from __future__ import annotations

import sqlite3
import uuid
from inspect import getsource
from dataclasses import replace

import pytest

from app.device_fingerprint.artifact_content import ArtifactRef, make_artifact_content
from app.device_fingerprint.artifact_dependency_graph import extract_direct_artifact_refs
from app.device_fingerprint.classification_persistence import (
    ClassificationPersistenceError, DeviceFingerprintClassificationStore, _CORE_FIELDS,
)
from app.device_fingerprint.classification_retention_policy import (
    build_initial_classification_retention_policy_v1, make_classification_retention_policy,
)
from app.device_fingerprint.control_plane_store import ActiveProfilePointerV1, PinnedRuntimeProfile
from app.device_fingerprint.ff5_runtime_profile_atomicity import _Fixture, _synthetic
from app.device_fingerprint.foundation_admission_artifacts import MANDATORY_PRE_ADMISSION_GATES
from app.device_fingerprint.runtime_profile_artifacts import (
    direct_artifact_refs, make_runtime_profile_admission_manifest,
    make_runtime_profile_validity_record,
)
from tests.device_fingerprint_task04_04d_request.test_request_assembly import (
    TIME, candidate_run, prepared, ref,
)
from tests.device_fingerprint_task04_t01.test_snapshot_service import MAC, START, END
from tests.device_fingerprint import SITE


def setup(tmp_path, *, clock=lambda: TIME, fault_hook=None):
    context, control, service, profile = prepared()
    assembly = candidate_run(service, profile)
    retention = build_initial_classification_retention_policy_v1()
    task01 = tmp_path / "task01.sqlite"
    task01.touch()
    store = DeviceFingerprintClassificationStore(
        tmp_path / "classification.sqlite", task01,
        control_plane_store=control, utc_clock=clock, fault_hook=fault_hook)
    store.initialize()
    foundation_manifest = make_artifact_content("FoundationAdmissionManifest", {"synthetic": True})
    foundation_admission = make_runtime_profile_admission_manifest({
        "runtime_profile_admission_contract_version": 1,
        "profile_kind": "foundation", "candidate_profile": ref(assembly.foundation_runtime_profile),
        "previous_active_profile": None,
        "expected_previous_activation_record_id": None,
        "expected_previous_activation_generation_id": None,
        "update_class": "INITIAL_FOUNDATION", "prerequisite_gate_results": [],
        "compatibility_validation_result": "PASS",
        "candidate_repository_commit_sha": "a" * 40,
        "candidate_repository_tree_sha": "b" * 40,
        "foundation_admission_manifest": ref(foundation_manifest),
        "task04_acceptance_manifest": None,
        "foundation_runtime_profile_admission_manifest": None,
    })
    control.contents[foundation_manifest.artifact_id] = foundation_manifest
    control.contents[foundation_admission.artifact_id] = foundation_admission
    store._test_foundation_admission = foundation_admission
    return store, control, assembly, retention


def persist_candidate(store, assembly, retention):
    return store.persist(
        assembly, retention_policy=retention,
        pre_acceptance_foundation_runtime_profile_admission_manifest=store._test_foundation_admission)


def production_setup(tmp_path):
    store, control, candidate, retention = setup(tmp_path)
    profile = candidate.classification_runtime_profile
    foundation_admission = store._test_foundation_admission
    foundation_manifest = control.contents[foundation_admission.semantic_payload[
        "foundation_admission_manifest"]["artifact_id"]]
    accepted = make_artifact_content("Task04AcceptanceManifest", {
        "fixture": "accepted",
        "tested_classification_runtime_profile": ref(profile),
        "classifier_artifact_manifest": ref(candidate.classifier_artifact_manifest),
        "foundation_admission_manifest": ref(foundation_manifest),
        "pre_acceptance_task04_gate_result_manifests": [],
    })
    admission = make_runtime_profile_admission_manifest({
        "runtime_profile_admission_contract_version": 1,
        "profile_kind": "classification", "candidate_profile": ref(profile),
        "previous_active_profile": None,
        "expected_previous_activation_record_id": None,
        "expected_previous_activation_generation_id": None,
        "update_class": "INITIAL_CLASSIFICATION", "prerequisite_gate_results": [],
        "compatibility_validation_result": "PASS",
        "candidate_repository_commit_sha": "a" * 40,
        "candidate_repository_tree_sha": "b" * 40,
        "foundation_admission_manifest": foundation_admission.semantic_payload[
            "foundation_admission_manifest"],
        "task04_acceptance_manifest": ref(accepted),
        "foundation_runtime_profile_admission_manifest": ref(foundation_admission),
    })
    activation_id = "11111111-1111-4111-8111-111111111111"
    activation = make_artifact_content("RuntimeProfileActivationRecord", {
        "activation_record_id": activation_id, "runtime_profile_id": profile.artifact_id,
        "runtime_profile_digest": profile.content_sha256,
        "runtime_profile_admission_manifest_id": admission.artifact_id,
        "runtime_profile_admission_manifest_digest": admission.content_sha256,
        "previous_active_profile_id": None,
        "previous_active_profile_digest": None,
    })
    validity = make_artifact_content("RuntimeProfileValidityRecord", {
        "validity_record_id": "33333333-3333-4333-8333-333333333333",
        "activation_record_id": activation_id, "previous_validity_record_id": None,
        "runtime_profile_id": profile.artifact_id,
        "runtime_profile_digest": profile.content_sha256,
    })
    pointer = ActiveProfilePointerV1(
        "classification", profile.artifact_id, profile.content_sha256,
        activation_id, "22222222-2222-4222-8222-222222222222", TIME)
    control.contents.update({item.artifact_id: item for item in (
        accepted, foundation_admission, admission, activation, validity)})
    control.pinned = PinnedRuntimeProfile(pointer, profile, admission, activation, validity)
    assembly = replace(candidate, execution_context="PRODUCTION",
                       pinned_runtime_profile=control.pinned,
                       runtime_profile_activation_record=activation)
    return store, control, assembly, retention


def real_production_setup(tmp_path):
    store, fake, candidate, retention = setup(tmp_path)
    fixture = _Fixture(tmp_path / "control.sqlite")
    # The disposable F-F5 manifest intentionally contains typed placeholder refs.
    # Materialize those exact placeholders for this full-closure persistence test.
    for gate_id in MANDATORY_PRE_ADMISSION_GATES:
        fixture.store.persist_artifact(_synthetic("GateResultManifest", f"ff5-disposable-{gate_id}"))
    for kind, label in (
        ("ClassificationRetentionPolicy", "retention"),
        ("ProductValidationPolicy", "product-validation"),
        ("KnowledgeFreshnessPolicy", "freshness"),
        ("SourceGovernanceRecord", "governance"),
        ("KnowledgeProvenanceManifest", "provenance"),
        ("K2AConformancePackage", "k2a"),
        ("TTLCapturePlacementProof", "ttl"),
        ("CapabilityDisposition", "portal-v2"),
    ):
        fixture.store.persist_artifact(_synthetic(kind, label))
    persisted = set()

    def persist_candidate(content):
        if content.artifact_id in persisted:
            return
        refs = (direct_artifact_refs(content) if content.artifact_type in (
            "FoundationRuntimeProfile", "ClassificationRuntimeProfile", "RuntimeProfileAdmissionManifest")
                else extract_direct_artifact_refs(content))
        for reference in refs:
            dependency = fake.contents[reference.artifact_id]
            reference.resolve(dependency, dependency.artifact_type)
            persist_candidate(dependency)
        fixture.store.persist_artifact(content, refs)
        persisted.add(content.artifact_id)

    fake_foundation_manifest_id = store._test_foundation_admission.semantic_payload[
        "foundation_admission_manifest"]["artifact_id"]
    for content in fake.contents.values():
        if content.artifact_id not in (fake_foundation_manifest_id,
                                       store._test_foundation_admission.artifact_id):
            persist_candidate(content)
    foundation_admission = fixture.admission("foundation", candidate.foundation_runtime_profile)
    accepted = make_artifact_content("Task04AcceptanceManifest", {
        "fixture": "accepted",
        "tested_classification_runtime_profile": ref(candidate.classification_runtime_profile),
        "classifier_artifact_manifest": ref(candidate.classifier_artifact_manifest),
        "foundation_admission_manifest": ref(fixture.leaves["FoundationAdmissionManifest"]),
        "pre_acceptance_task04_gate_result_manifests": [],
    })
    fixture.store.persist_artifact(accepted, tuple(extract_direct_artifact_refs(accepted)))
    fixture.leaves["Task04AcceptanceManifest"] = accepted
    classification_admission = fixture.admission(
        "classification", candidate.classification_runtime_profile,
        foundation_admission=foundation_admission)
    pointer, activation, active, _ = fixture.activate(classification_admission, 101)
    pinned = fixture.store.pin_active_profile("classification")
    assert pinned.validity_record == active
    assembly = replace(candidate, execution_context="PRODUCTION",
                       pinned_runtime_profile=pinned,
                       runtime_profile_activation_record=activation)
    store._control = fixture.store
    return store, fixture, assembly, retention, pointer, active


def real_preacceptance_setup(tmp_path):
    store, fixture, production, retention, _, _ = real_production_setup(tmp_path)
    foundation_ref = production.pinned_runtime_profile.admission_manifest.semantic_payload[
        "foundation_runtime_profile_admission_manifest"]
    foundation_admission = fixture.store.load_artifact(
        foundation_ref["artifact_id"], foundation_ref["content_sha256"])
    candidate = replace(production, execution_context="PRE_ACCEPTANCE_CANDIDATE",
                        pinned_runtime_profile=None, runtime_profile_activation_record=None)
    return store, fixture, candidate, retention, foundation_admission


def assert_no_dangling_audit_references(store, classification_id):
    with store._connect() as conn:
        artifacts = {row["artifact_id"]: row["content_sha256"] for row in conn.execute(
            "SELECT artifact_id, content_sha256 FROM artifacts")}
        roots = conn.execute("SELECT artifact_id, content_sha256 FROM classification_roots "
                             "WHERE classification_id=?", (classification_id,)).fetchall()
        assert roots
        for root in roots:
            assert artifacts[root["artifact_id"]] == root["content_sha256"]
        for artifact_id, digest in artifacts.items():
            content = store.load_artifact(artifact_id, digest)
            syntactic = extract_direct_artifact_refs(content)
            bounded = content.artifact_type in {
                "RuntimeProfileAdmissionManifest", "FoundationAdmissionManifest",
                "Task04AcceptanceManifest", "RuntimeProfileActivationRecord",
            }
            actual = conn.execute("SELECT dependency_id, dependency_digest "
                                  "FROM artifact_dependencies WHERE owner_id=?", (artifact_id,))
            actual_refs = {(row["dependency_id"], row["dependency_digest"]) for row in actual}
            if not bounded:
                assert actual_refs == {(item.artifact_id, item.content_sha256) for item in syntactic}
            for reference in syntactic:
                if bounded and (reference.artifact_id, reference.content_sha256) not in actual_refs:
                    continue
                assert artifacts[reference.artifact_id] == reference.content_sha256
                target = store.load_artifact(reference.artifact_id, reference.content_sha256)
                reference.resolve(target, target.artifact_type)
                edge = conn.execute("SELECT dependency_digest FROM artifact_dependencies "
                                    "WHERE owner_id=? AND dependency_id=?",
                                    (artifact_id, reference.artifact_id)).fetchone()
                assert edge is not None and edge[0] == reference.content_sha256
        for edge in conn.execute("SELECT dependency_id, dependency_digest FROM artifact_dependencies"):
            assert artifacts[edge["dependency_id"]] == edge["dependency_digest"]


def test_same_task01_database_path_is_rejected(tmp_path):
    path = tmp_path / "task01.sqlite"
    with pytest.raises(ClassificationPersistenceError):
        DeviceFingerprintClassificationStore(path, path, control_plane_store=object())


def test_pre_acceptance_core_exact_and_no_future_placeholders(tmp_path):
    store, _, assembly, retention = setup(tmp_path)
    core = persist_candidate(store, assembly, retention)
    assert uuid.UUID(core.classification_id).version == 4
    assert core.classification_id == str(uuid.UUID(core.classification_id))
    assert core.classified_at_utc == TIME
    assert core.execution_context == "PRE_ACCEPTANCE_CANDIDATE"
    assert core.runtime_profile_activation_record_id is None
    assert core.foundation_runtime_profile_id == assembly.foundation_runtime_profile.artifact_id
    assert core.classification_runtime_profile_id == assembly.classification_runtime_profile.artifact_id
    with store._connect() as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(classifications)")}
    assert columns == set(_CORE_FIELDS)
    assert not columns.intersection({
        "task04_acceptance_manifest_id", "runtime_profile_admission_manifest_id",
        "decision_record_id", "gate_result_manifest_id"})
    assert store.load_core(core.classification_id) == core


def test_exact_artifact_bytes_roundtrip_and_transient_not_persisted(tmp_path):
    store, _, assembly, retention = setup(tmp_path)
    core = persist_candidate(store, assembly, retention)
    for artifact in (assembly.classification_result, assembly.classification_request_manifest,
                     assembly.snapshot_record, assembly.evidence_snapshot_content):
        loaded = store.load_artifact(artifact.artifact_id, artifact.content_sha256)
        assert loaded.semantic_payload_json == artifact.semantic_payload_json
    with store._connect() as conn:
        kinds = {row[0] for row in conn.execute("SELECT artifact_type FROM artifacts")}
    assert "EvidenceSnapshotMaterialization" not in kinds
    assert store.load_artifact(core.snapshot_record_id, core.snapshot_record_digest) == (
        assembly.snapshot_record)


def test_atomic_fault_rolls_back_core_and_new_artifacts(tmp_path):
    def fault(stage):
        assert stage == "before_commit"
        raise sqlite3.OperationalError("injected")

    store, _, assembly, retention = setup(tmp_path, fault_hook=fault)
    with pytest.raises(ClassificationPersistenceError) as caught:
        persist_candidate(store, assembly, retention)
    assert caught.value.reason_code == "persistence_unavailable"
    with store._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM classifications").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == 0


def test_level_b_replays_without_task01_and_no_current_clock(tmp_path):
    store, _, assembly, retention = setup(tmp_path)
    core = persist_candidate(store, assembly, retention)
    (tmp_path / "task01.sqlite").unlink()
    with store._connect() as conn:
        before = conn.execute("SELECT semantic_payload_json FROM artifacts WHERE artifact_id=?",
                              (assembly.classification_result.artifact_id,)).fetchone()[0]
    store._clock = lambda: (_ for _ in ()).throw(AssertionError("clock read on replay"))
    replayed = store.replay_level_b(core.classification_id)
    assert replayed == assembly.classification_result
    assert replayed.semantic_payload_json == assembly.classification_result.semantic_payload_json
    assert store.load_core(core.classification_id) == core
    assert store.load_artifact(core.classification_request_manifest_id,
                               core.classification_request_manifest_digest).semantic_payload[
        "knowledge_evaluation_at_utc"] == assembly.knowledge_evaluation_at_utc
    with store._connect() as conn:
        after = conn.execute("SELECT semantic_payload_json FROM artifacts WHERE artifact_id=?",
                             (assembly.classification_result.artifact_id,)).fetchone()[0]
    assert after == before


def test_frozen_ninety_day_expiry_and_shared_artifact_protection(tmp_path):
    store, _, assembly, retention = setup(tmp_path)
    a = persist_candidate(store, assembly, retention)
    b = persist_candidate(store, assembly, retention)
    assert store.expire_and_gc(now_utc="2026-12-21T22:30:34.463Z") == 0
    assert store.load_artifact(assembly.classification_policy.artifact_id,
                               assembly.classification_policy.content_sha256)
    with store._connect() as conn:
        conn.execute("UPDATE classifications SET classified_at_utc=? WHERE classification_id=?",
                     ("2026-09-01T00:00:00.000Z", a.classification_id))
    assert store.expire_and_gc(now_utc="2026-12-01T22:30:34.464Z") == 1
    assert store.load_artifact(assembly.classification_policy.artifact_id,
                               assembly.classification_policy.content_sha256)
    assert store.replay_level_b(b.classification_id) == assembly.classification_result
    assert store.expire_and_gc(now_utc="2027-01-01T00:00:00.000Z") == 1
    with store._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == 0


def test_exact_ninety_day_boundary(tmp_path):
    store, _, assembly, retention = setup(tmp_path)
    core = persist_candidate(store, assembly, retention)
    assert retention.semantic_payload["classification_history_retention_seconds"] == 7_776_000
    assert store.expire_and_gc(now_utc="2026-12-21T22:30:34.463Z") == 0
    assert store.load_core(core.classification_id) == core
    assert store.expire_and_gc(now_utc="2026-12-21T22:30:34.464Z") == 1
    with store._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM classification_roots").fetchone()[0] == 0


def test_cross_field_profile_and_activation_rules(tmp_path):
    store, _, assembly, retention = setup(tmp_path)
    other = make_artifact_content("FoundationRuntimeProfile", {"synthetic": True})
    with pytest.raises(ClassificationPersistenceError):
        store.persist(replace(assembly, foundation_runtime_profile=other), retention_policy=retention)
    with pytest.raises(ClassificationPersistenceError) as caught:
        store.persist(replace(assembly, execution_context="PRODUCTION"), retention_policy=retention)
    assert caught.value.reason_code == "production_profile_not_admitted"


def test_immutable_artifact_conflict_rejected(tmp_path):
    store, _, assembly, retention = setup(tmp_path)
    persist_candidate(store, assembly, retention)
    with store._connect() as conn:
        conn.execute("UPDATE artifacts SET semantic_payload_json=? WHERE artifact_id=?",
                     (b"{}", assembly.classification_policy.artifact_id))
    with pytest.raises(ClassificationPersistenceError):
        persist_candidate(store, assembly, retention)


def test_dependency_edges_are_complete_and_no_dangling_digest(tmp_path):
    store, _, assembly, retention = setup(tmp_path)
    persist_candidate(store, assembly, retention)
    with store._connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM artifact_dependencies").fetchone()[0]
        dangling = conn.execute("SELECT COUNT(*) FROM artifact_dependencies d "
                                "LEFT JOIN artifacts a ON a.artifact_id=d.dependency_id "
                                "WHERE a.artifact_id IS NULL OR a.content_sha256<>d.dependency_digest"
                                ).fetchone()[0]
        roots = conn.execute("SELECT COUNT(*) FROM classification_roots").fetchone()[0]
    assert total > 0
    assert roots > 0
    assert dangling == 0


def test_missing_runtime_dependency_fails_before_classification_commit(tmp_path):
    store, control, assembly, retention = setup(tmp_path)
    missing_id = assembly.foundation_runtime_profile.semantic_payload[
        "source_health_policy"]["artifact_id"]
    del control.contents[missing_id]
    with pytest.raises(ClassificationPersistenceError) as caught:
        persist_candidate(store, assembly, retention)
    assert caught.value.reason_code == "persistence_unavailable"
    with store._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM classifications").fetchone()[0] == 0


def test_production_commit_checks_exact_pin_immediately_before_commit(tmp_path):
    store, control, assembly, retention = production_setup(tmp_path)
    core = store.persist(assembly, retention_policy=retention)
    assert core.execution_context == "PRODUCTION"
    assert core.runtime_profile_activation_record_id == control.pinned.pointer.activation_record_id
    assert control.commit_checks == [control.pinned]
    assert store.replay_level_b(core.classification_id) == assembly.classification_result


def test_unadmitted_production_profile_fails_without_commit(tmp_path):
    store, control, assembly, retention = production_setup(tmp_path)
    bad_admission = make_artifact_content("RuntimeProfileAdmissionManifest", {
        **control.pinned.admission_manifest.semantic_payload,
        "task04_acceptance_manifest": None,
    })
    bad_pin = replace(control.pinned, admission_manifest=bad_admission)
    with pytest.raises(ClassificationPersistenceError) as caught:
        store.persist(replace(assembly, pinned_runtime_profile=bad_pin), retention_policy=retention)
    assert caught.value.reason_code == "production_profile_not_admitted"
    with store._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM classifications").fetchone()[0] == 0


def test_missing_durable_production_admission_is_not_accepted(tmp_path):
    store, control, assembly, retention = production_setup(tmp_path)
    del control.contents[control.pinned.admission_manifest.artifact_id]
    with pytest.raises(ClassificationPersistenceError) as caught:
        store.persist(assembly, retention_policy=retention)
    assert caught.value.reason_code == "activation_lineage_unavailable"
    with store._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM classifications").fetchone()[0] == 0


@pytest.mark.parametrize("failure", ["runtime_profile_invalidated", "ttl_capture_proof_invalidated"])
def test_inflight_invalidated_or_ttl_suspension_rolls_back(tmp_path, failure):
    store, control, assembly, retention = production_setup(tmp_path)
    control.commit_failure = failure
    with pytest.raises(ClassificationPersistenceError) as caught:
        store.persist(assembly, retention_policy=retention)
    assert caught.value.reason_code == "runtime_profile_invalidated"
    assert control.commit_checks == [control.pinned]
    with store._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM classifications").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == 0


def test_real_control_plane_safe_deactivation_retains_current_head(tmp_path):
    store, fixture, assembly, retention, pointer, active = real_production_setup(tmp_path)
    new_foundation_admission = fixture.admission("foundation", fixture.foundation_b)
    replacement_admission = fixture.admission(
        "classification", fixture.classification_b, pointer,
        foundation_admission=new_foundation_admission)
    fixture.activate(replacement_admission, 102, active)
    current_head = fixture.store.get_validity_head(pointer.activation_record_id)
    assert fixture.store.capture_pinned_commit_lineage(assembly.pinned_runtime_profile) == (
        active, current_head)
    core = store.persist(assembly, retention_policy=retention)
    assert core.execution_context == "PRODUCTION"
    with store._connect() as conn:
        retained = {row[0] for row in conn.execute(
            "SELECT artifact_id FROM classification_roots WHERE classification_id=?",
            (core.classification_id,))}
        predecessor = conn.execute(
            "SELECT dependency_id FROM artifact_dependencies WHERE owner_id=? AND dependency_id=?",
            (current_head.artifact_id, active.artifact_id)).fetchone()
    assert {active.artifact_id, current_head.artifact_id} <= retained
    assert predecessor[0] == active.artifact_id


@pytest.mark.parametrize("reason", ["EXPLICIT_POLICY_SUSPEND", "TTL_CAPTURE_PROOF_INVALIDATED"])
def test_real_control_plane_invalidation_rolls_back_everything(tmp_path, reason):
    store, fixture, assembly, retention, _, active = real_production_setup(tmp_path)
    invalidated = make_runtime_profile_validity_record({
        **active.semantic_payload,
        "validity_record_id": str(uuid.uuid4()),
        "state": "SUSPENDED_INVALIDATED", "reason_code": reason,
        "inflight_commit_rule": "REJECT_PINNED_INFLIGHT",
        "previous_validity_record_id": active.semantic_payload["validity_record_id"],
    })
    fixture.store.transition_validity(
        invalidated, expected_head_validity_record_id=active.semantic_payload["validity_record_id"])
    with pytest.raises(ClassificationPersistenceError) as error:
        store.persist(assembly, retention_policy=retention)
    assert error.value.reason_code == "runtime_profile_invalidated"
    with store._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM classifications").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == 0


def test_real_control_plane_missing_canonical_head_rolls_back(tmp_path):
    store, fixture, assembly, retention, pointer, _ = real_production_setup(tmp_path)
    with fixture.store._connect() as conn:
        conn.execute("DELETE FROM validity_heads WHERE activation_record_id=?",
                     (pointer.activation_record_id,))
    with pytest.raises(ClassificationPersistenceError) as error:
        store.persist(assembly, retention_policy=retention)
    assert error.value.reason_code == "activation_lineage_unavailable"
    with store._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM classifications").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == 0


def test_persistence_uses_public_control_plane_lineage_only():
    source = getsource(DeviceFingerprintClassificationStore)
    assert "self._control._connect" not in source
    assert "FROM validities" not in source
    assert "FROM validity_heads" not in source


def test_pre_acceptance_retains_exact_foundation_admission_closure(tmp_path):
    store, fixture, assembly, retention, foundation_admission = real_preacceptance_setup(tmp_path)
    future_classification_admission = fixture.store.pin_active_profile(
        "classification").admission_manifest
    core = store.persist(
        assembly, retention_policy=retention,
        pre_acceptance_foundation_runtime_profile_admission_manifest=foundation_admission)
    assert core.runtime_profile_activation_record_id is None
    with store._connect() as conn:
        retained = {row[0] for row in conn.execute(
            "SELECT artifact_id FROM classification_roots WHERE classification_id=?",
            (core.classification_id,))}
        assert not any(row[0] in retained for row in conn.execute(
            "SELECT artifact_id FROM artifacts WHERE artifact_type IN "
            "('Task04AcceptanceManifest', 'RuntimeProfileActivationRecord')"))
    foundation_manifest_ref = foundation_admission.semantic_payload["foundation_admission_manifest"]
    foundation_manifest = fixture.store.load_artifact(
        foundation_manifest_ref["artifact_id"], foundation_manifest_ref["content_sha256"])
    assert {assembly.foundation_runtime_profile.artifact_id, foundation_admission.artifact_id,
            foundation_manifest.artifact_id} <= retained
    assert future_classification_admission.artifact_id not in retained
    assert store.load_artifact(foundation_admission.artifact_id,
                               foundation_admission.content_sha256) == foundation_admission
    assert store.load_artifact(foundation_manifest.artifact_id,
                               foundation_manifest.content_sha256) == foundation_manifest
    assert_no_dangling_audit_references(store, core.classification_id)


def test_pre_acceptance_requires_exact_durable_foundation_admission(tmp_path):
    store, fixture, assembly, retention, foundation_admission = real_preacceptance_setup(tmp_path)
    other_admission = fixture.admission("foundation", fixture.foundation_b)
    for supplied in (None, other_admission):
        with pytest.raises(ClassificationPersistenceError) as error:
            store.persist(
                assembly, retention_policy=retention,
                pre_acceptance_foundation_runtime_profile_admission_manifest=supplied)
        assert error.value.reason_code == "activation_lineage_unavailable"
    with store._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM classifications").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == 0


def test_pre_acceptance_missing_transitive_foundation_lineage_fails_closed(tmp_path):
    store, fixture, assembly, retention, foundation_admission = real_preacceptance_setup(tmp_path)
    foundation_manifest_id = foundation_admission.semantic_payload[
        "foundation_admission_manifest"]["artifact_id"]
    with sqlite3.connect(fixture.store.database_path) as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("DELETE FROM artifacts WHERE artifact_id=?", (foundation_manifest_id,))
    with pytest.raises(ClassificationPersistenceError) as error:
        store.persist(
            assembly, retention_policy=retention,
            pre_acceptance_foundation_runtime_profile_admission_manifest=foundation_admission)
    assert error.value.reason_code == "activation_lineage_unavailable"
    with store._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM classifications").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == 0


def test_pre_acceptance_never_reads_active_foundation_pointer(tmp_path):
    store, fixture, assembly, retention, foundation_admission = real_preacceptance_setup(tmp_path)
    calls = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("active Foundation selection is forbidden")

    fixture.store.pin_active_profile = forbidden
    fixture.store.get_active_pointer = forbidden
    store.persist(
        assembly, retention_policy=retention,
        pre_acceptance_foundation_runtime_profile_admission_manifest=foundation_admission)
    assert calls == []


@pytest.mark.parametrize("changed", [
    {"privacy_storage_basis": "OTHER_VALID_AUDIT_BASIS"},
    {"retention_policy_version": 2},
])
def test_only_exact_frozen_retention_policy_is_accepted(tmp_path, changed):
    store, _, assembly, retention = setup(tmp_path)
    assert retention == build_initial_classification_retention_policy_v1()
    assert retention.content_sha256 == (
        "029c3534e076db6f7293c78e8a86c425b10c786d58713e77a077a19dfdda3e72")
    alternate = make_classification_retention_policy({**retention.semantic_payload, **changed})
    assert alternate.semantic_payload["classification_history_retention_seconds"] == 7_776_000
    with pytest.raises(ClassificationPersistenceError) as error:
        persist_candidate(store, assembly, alternate)
    assert error.value.reason_code == "persistence_unavailable"
    with store._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM classifications").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == 0


@pytest.mark.parametrize("missing", [
    "classification_admission", "task04_acceptance", "foundation_admission",
    "foundation_manifest",
])
def test_real_production_missing_admission_lineage_is_typed_and_atomic(tmp_path, missing):
    store, fixture, assembly, retention, _, _ = real_production_setup(tmp_path)
    admission = assembly.pinned_runtime_profile.admission_manifest
    foundation_ref = admission.semantic_payload["foundation_runtime_profile_admission_manifest"]
    foundation_admission = fixture.store.load_artifact(
        foundation_ref["artifact_id"], foundation_ref["content_sha256"])
    missing_ids = {
        "classification_admission": admission.artifact_id,
        "task04_acceptance": admission.semantic_payload["task04_acceptance_manifest"]["artifact_id"],
        "foundation_admission": foundation_admission.artifact_id,
        "foundation_manifest": foundation_admission.semantic_payload[
            "foundation_admission_manifest"]["artifact_id"],
    }
    with sqlite3.connect(fixture.store.database_path) as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("DELETE FROM artifacts WHERE artifact_id=?", (missing_ids[missing],))
    with pytest.raises(ClassificationPersistenceError) as error:
        store.persist(assembly, retention_policy=retention)
    assert error.value.reason_code == "activation_lineage_unavailable"
    with store._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM classifications").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == 0


def test_production_rejects_acceptance_only_foundation_selector(tmp_path):
    store, _, assembly, retention, _, _ = real_production_setup(tmp_path)
    with pytest.raises(ClassificationPersistenceError) as error:
        store.persist(
            assembly, retention_policy=retention,
            pre_acceptance_foundation_runtime_profile_admission_manifest=store._test_foundation_admission)
    assert error.value.reason_code == "persistence_unavailable"


def test_production_audit_references_resolve_exactly(tmp_path):
    store, _, assembly, retention, _, _ = real_production_setup(tmp_path)
    core = store.persist(assembly, retention_policy=retention)
    assert_no_dangling_audit_references(store, core.classification_id)


def test_classification_sqlite_open_failure_is_persistence_unavailable(tmp_path):
    store, _, assembly, retention = setup(tmp_path)

    def unavailable():
        raise sqlite3.OperationalError("unable to open database file")

    store._connect = unavailable
    with pytest.raises(ClassificationPersistenceError) as error:
        persist_candidate(store, assembly, retention)
    assert error.value.reason_code == "persistence_unavailable"
    with sqlite3.connect(store.database_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM classifications").fetchone()[0] == 0
