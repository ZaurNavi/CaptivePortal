"""Narrow §120 admission-retention boundary regressions for T-07."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from app.device_fingerprint.artifact_content import ArtifactRef, make_artifact_content
from app.device_fingerprint.classification_persistence import ClassificationPersistenceError
from app.device_fingerprint.runtime_profile_artifacts import make_runtime_profile_admission_manifest
from app.device_fingerprint.validation import format_utc, parse_utc
from tests.device_fingerprint_task04_04d_persistence.test_classification_persistence import (
    persist_candidate, production_setup, setup,
)


def _ref(content):
    return ArtifactRef(content.artifact_id, content.content_sha256).as_dict()


def _historical_gate_fixture(store, control, *, rpm_gate=True, manifest_gate=True,
                             gate_stored=True):
    """The referenced historical input is deliberately absent from control storage."""
    old_rpm = store._test_foundation_admission
    old_manifest = control.contents[old_rpm.semantic_payload[
        "foundation_admission_manifest"]["artifact_id"]]
    missing = make_artifact_content("CanonicalKnowledgeRecordSet", {"historical": "missing"})
    gate = make_artifact_content("GateResultManifest", {
        "input_artifact_refs": [_ref(missing)],
    })
    manifest = make_artifact_content("FoundationAdmissionManifest", {
        **old_manifest.semantic_payload,
        "pre_admission_gate_result_manifests": [_ref(gate)] if manifest_gate else [],
    })
    rpm = make_runtime_profile_admission_manifest({
        **old_rpm.semantic_payload,
        "foundation_admission_manifest": _ref(manifest),
        "prerequisite_gate_results": [_ref(gate)] if rpm_gate else [],
    })
    control.contents[manifest.artifact_id] = manifest
    control.contents[rpm.artifact_id] = rpm
    if gate_stored:
        control.contents[gate.artifact_id] = gate
    store._test_foundation_admission = rpm
    assert missing.artifact_id not in control.contents
    return rpm, manifest, gate, missing


def _audit_ids(store, classification_id):
    with store._connect() as connection:
        roots = {row[0] for row in connection.execute(
            "SELECT artifact_id FROM classification_roots WHERE classification_id=?",
            (classification_id,))}
        artifacts = {row[0] for row in connection.execute("SELECT artifact_id FROM artifacts")}
        edges = {(row[0], row[1]) for row in connection.execute(
            "SELECT owner_id, dependency_id FROM artifact_dependencies")}
    return roots, artifacts, edges


def test_closure_unit_01_rpm_gate_history_is_opaque(tmp_path):
    store, control, assembly, retention = setup(tmp_path)
    rpm, _, gate, missing = _historical_gate_fixture(store, control)
    core = persist_candidate(store, assembly, retention)
    assert store.load_core(core.classification_id) == core
    assert store.load_artifact(rpm.artifact_id, rpm.content_sha256) == rpm
    _, artifacts, _ = _audit_ids(store, core.classification_id)
    assert gate.artifact_id not in artifacts
    assert missing.artifact_id not in artifacts


def test_closure_unit_02_foundation_gate_history_is_opaque(tmp_path):
    store, control, assembly, retention = setup(tmp_path)
    _, manifest, gate, missing = _historical_gate_fixture(
        store, control, rpm_gate=False, gate_stored=False)
    core = persist_candidate(store, assembly, retention)
    assert store.load_artifact(manifest.artifact_id, manifest.content_sha256) == manifest
    _, artifacts, _ = _audit_ids(store, core.classification_id)
    assert gate.artifact_id not in artifacts
    assert missing.artifact_id not in artifacts


def test_closure_unit_03_real_runtime_dependency_still_fails_closed(tmp_path):
    store, control, assembly, retention = setup(tmp_path)
    missing = assembly.foundation_runtime_profile.semantic_payload[
        "source_health_policy"]["artifact_id"]
    del control.contents[missing]
    with pytest.raises(ClassificationPersistenceError) as error:
        persist_candidate(store, assembly, retention)
    assert error.value.reason_code == "persistence_unavailable"


@pytest.mark.parametrize("corrupt", [False, True])
def test_closure_unit_04_missing_or_corrupt_foundation_rpm_is_typed(tmp_path, corrupt):
    store, control, assembly, retention = setup(tmp_path)
    rpm = store._test_foundation_admission
    if corrupt:
        wrong = make_artifact_content(
            "RuntimeProfileAdmissionManifest", {"corrupt": True})
        original_load = control.load_artifact
        control.load_artifact = lambda artifact_id, digest=None: (
            wrong if artifact_id == rpm.artifact_id
            else original_load(artifact_id, digest))
    else:
        del control.contents[rpm.artifact_id]
    with pytest.raises(ClassificationPersistenceError) as error:
        persist_candidate(store, assembly, retention)
    assert error.value.reason_code == "activation_lineage_unavailable"


def test_closure_unit_05_foundation_candidate_mismatch_is_typed(tmp_path):
    store, control, assembly, retention = setup(tmp_path)
    old = store._test_foundation_admission
    other = make_artifact_content("FoundationRuntimeProfile", {"different": True})
    rpm = make_runtime_profile_admission_manifest({
        **old.semantic_payload, "candidate_profile": _ref(other),
    })
    control.contents[rpm.artifact_id] = rpm
    store._test_foundation_admission = rpm
    with pytest.raises(ClassificationPersistenceError) as error:
        persist_candidate(store, assembly, retention)
    assert error.value.reason_code == "activation_lineage_unavailable"


def test_closure_unit_06_opaque_ids_remain_bytes_not_edges_or_roots(tmp_path):
    store, control, assembly, retention = setup(tmp_path)
    rpm, manifest, gate, _ = _historical_gate_fixture(store, control)
    core = persist_candidate(store, assembly, retention)
    roots, artifacts, edges = _audit_ids(store, core.classification_id)
    assert {rpm.artifact_id, manifest.artifact_id} <= roots
    assert gate.artifact_id not in roots | artifacts
    assert (rpm.artifact_id, gate.artifact_id) not in edges
    assert (manifest.artifact_id, gate.artifact_id) not in edges
    assert _ref(gate) in rpm.semantic_payload["prerequisite_gate_results"]
    assert _ref(gate) in manifest.semantic_payload["pre_admission_gate_result_manifests"]
    assert store.load_artifact(rpm.artifact_id, rpm.content_sha256).semantic_payload_json == (
        rpm.semantic_payload_json)


def test_closure_unit_07_shared_bounded_refs_survive_gc_not_gate_only(tmp_path):
    store, control, assembly, retention = setup(tmp_path)
    rpm, manifest, gate, _ = _historical_gate_fixture(store, control)
    first = persist_candidate(store, assembly, retention)
    second = persist_candidate(store, assembly, retention)
    earlier = format_utc(parse_utc(first.classified_at_utc) - timedelta(seconds=1))
    with store._connect() as connection:
        connection.execute("UPDATE classifications SET classified_at_utc=? WHERE classification_id=?",
                           (earlier, first.classification_id))
    expiry = format_utc(parse_utc(earlier) + timedelta(seconds=retention.semantic_payload[
        "classification_history_retention_seconds"]))
    assert store.expire_and_gc(now_utc=expiry) == 1
    assert store.load_core(second.classification_id) == second
    assert store.load_artifact(rpm.artifact_id, rpm.content_sha256) == rpm
    assert store.load_artifact(manifest.artifact_id, manifest.content_sha256) == manifest
    assert store.replay_level_b(second.classification_id) == assembly.classification_result
    _, artifacts, _ = _audit_ids(store, second.classification_id)
    assert gate.artifact_id not in artifacts


def test_closure_unit_08_unadmitted_and_invalidated_production_rejected(tmp_path):
    store, _, assembly, retention = setup(tmp_path)
    with pytest.raises(ClassificationPersistenceError) as unadmitted:
        store.persist(replace(assembly, execution_context="PRODUCTION"),
                      retention_policy=retention)
    assert unadmitted.value.reason_code == "production_profile_not_admitted"
    production_root = tmp_path / "production"
    production_root.mkdir()
    production_store, control, production, retention = production_setup(production_root)
    control.commit_failure = "runtime_profile_invalidated"
    with pytest.raises(ClassificationPersistenceError) as invalidated:
        production_store.persist(production, retention_policy=retention)
    assert invalidated.value.reason_code == "runtime_profile_invalidated"
    with production_store._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM classifications").fetchone()[0] == 0


def test_task04_pre_acceptance_gate_history_is_opaque_in_production(tmp_path):
    store, control, assembly, retention = production_setup(tmp_path)
    pinned = control.pinned
    old_acceptance_ref = pinned.admission_manifest.semantic_payload["task04_acceptance_manifest"]
    old_acceptance = control.contents[old_acceptance_ref["artifact_id"]]
    missing = make_artifact_content("GateResultManifest", {"historical": "T-01"})
    acceptance = make_artifact_content("Task04AcceptanceManifest", {
        **old_acceptance.semantic_payload,
        "pre_acceptance_task04_gate_result_manifests": [_ref(missing)],
    })
    control.contents[acceptance.artifact_id] = acceptance
    admission = make_runtime_profile_admission_manifest({
        **pinned.admission_manifest.semantic_payload,
        "task04_acceptance_manifest": _ref(acceptance),
    })
    control.contents[admission.artifact_id] = admission
    activation = make_artifact_content("RuntimeProfileActivationRecord", {
        **pinned.activation_record.semantic_payload,
        "runtime_profile_admission_manifest_id": admission.artifact_id,
        "runtime_profile_admission_manifest_digest": admission.content_sha256,
    })
    control.contents[activation.artifact_id] = activation
    changed_pin = replace(pinned, admission_manifest=admission, activation_record=activation)
    control.pinned = changed_pin
    assembly = replace(assembly, pinned_runtime_profile=changed_pin,
                       runtime_profile_activation_record=activation)
    core = store.persist(assembly, retention_policy=retention)
    roots, artifacts, edges = _audit_ids(store, core.classification_id)
    assert acceptance.artifact_id in roots
    assert missing.artifact_id not in roots | artifacts
    assert (acceptance.artifact_id, missing.artifact_id) not in edges
    assert _ref(missing) in store.load_artifact(
        acceptance.artifact_id, acceptance.content_sha256).semantic_payload[
            "pre_acceptance_task04_gate_result_manifests"]


@pytest.mark.parametrize("root", [
    "classification_rpm", "activation", "task04_acceptance", "foundation_manifest",
])
def test_bounded_production_admission_roots_are_required(tmp_path, root):
    store, control, assembly, retention = production_setup(tmp_path)
    pinned = control.pinned
    admission = pinned.admission_manifest
    foundation = admission.semantic_payload["foundation_admission_manifest"]
    ids = {
        "classification_rpm": admission.artifact_id,
        "activation": pinned.activation_record.artifact_id,
        "task04_acceptance": admission.semantic_payload[
            "task04_acceptance_manifest"]["artifact_id"],
        "foundation_manifest": foundation["artifact_id"],
    }
    del control.contents[ids[root]]
    with pytest.raises(ClassificationPersistenceError) as error:
        store.persist(assembly, retention_policy=retention)
    assert error.value.reason_code == "activation_lineage_unavailable"
    with store._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM classifications").fetchone()[0] == 0
