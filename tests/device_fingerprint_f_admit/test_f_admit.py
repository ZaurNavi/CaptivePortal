"""Disposable-only R14 F-ADMIT construction and publication tests."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import replace

import pytest

from app.device_fingerprint.artifact_content import ArtifactRef, make_artifact_content
from app.device_fingerprint.classification_policy import build_initial_classification_policy_v1
from app.device_fingerprint.control_plane_store import (
    ActiveProfilePointerV1, ControlPlaneOperationError, DeviceFingerprintControlPlaneStore,
)
from app.device_fingerprint.evidence_adapter_contracts import (
    build_initial_evidence_adapter_contract_set_v1, make_evidence_adapter_contract_set,
)
from app.device_fingerprint.f_admit_foundation import (
    InitialFoundationInputs, _admission_direct_refs, execute_initial_foundation_admission,
    prepare_initial_foundation_admission,
)
from app.device_fingerprint.foundation_admission_artifacts import (
    MANDATORY_PRE_ADMISSION_GATES, build_f_admit_input_refs,
    make_architecture_contract_reference, make_foundation_admission_manifest,
    make_origin_runtime_admission, validate_initial_foundation_manifest_lineage,
)
from app.device_fingerprint.foundation_gate_artifacts import make_gate_result_manifest
from app.device_fingerprint.foundation_schema_artifacts import build_foundation_schema_artifacts
from app.device_fingerprint.gate_proof_artifacts import make_gate_proof_artifact
from app.device_fingerprint.health_retention_contract import (
    final_source_health_policy, make_task01_health_retention_contract,
)
from app.device_fingerprint.k2a_conformance_artifacts import build_k2a_conformance_package
from app.device_fingerprint.knowledge_artifacts import (
    make_external_knowledge_provenance_manifest, make_knowledge_freshness_policy,
)
from app.device_fingerprint.knowledge_bundle import build_initial_knowledge_bundle_v1
from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.source_health_emitter_contracts import (
    build_network_sensor_source_health_emitter_contract,
    build_periodic_portal_source_health_emitter_contract,
    build_portal_source_health_emitter_contract,
)
from app.device_fingerprint.ttl_capture_placement_proof import make_ttl_capture_placement_proof
from tests.device_fingerprint.test_binding_contracts import _pair as binding_pair
from tests.device_fingerprint.test_ttl_capture_placement_proof import proof_payload
from tests.device_fingerprint_fe7.test_knowledge_bundle import candidate as knowledge_candidate

_AT = "2026-09-23T00:00:00.000Z"
_KNOWLEDGE_AT = "2026-09-22T22:30:34.464Z"
_SHA = "a" * 40
_TREE = "b" * 40
_EVIDENCE = [{"evidence_label": "synthetic", "file_sha256": "c" * 64,
              "media_type": "application/json", "path_or_reference": "test://f-admit"}]
_NAMED_TYPES = {
    "architecture_contract_reference": "ArchitectureContractReference",
    "evidence_schema_registry_contract": "EvidenceSchemaRegistryContract",
    "evidence_adapter_contract_set": "EvidenceAdapterContractSet",
    "knowledge_bundle": "KnowledgeBundle",
    "evidence_source_binding_timeline": "EvidenceSourceBindingTimeline",
    "binding_clock_policy": "BindingClockPolicy",
    "source_health_policy": "SourceHealthPolicy",
    "snapshot_content_policy": "SnapshotContentPolicy",
    "snapshot_execution_policy": "SnapshotExecutionPolicy",
    "classification_policy": "ClassificationPolicy",
    "classification_retention_policy": "ClassificationRetentionPolicy",
    "product_validation_policy": "ProductValidationPolicy",
    "k2a_conformance_package": "K2AConformancePackage",
    "portal_headers_v2_capability_disposition": "CapabilityDisposition",
    "task01_health_retention_contract": "Task01HealthRetentionContract",
}


def ref(content):
    return ArtifactRef(content.artifact_id, content.content_sha256).as_dict()


def execution(label):
    return {
        "execution_id": str(uuid.uuid4()), "executor_kind": "TECHLEAD_GATE_TOOL",
        "repository_commit_sha": _SHA, "repository_tree_sha": _TREE,
        "procedure_or_test_suite_id": label, "environment_identity": "synthetic-disposable",
        "execution_artifact_sha256": None,
    }


def gate(gate_id, outputs=(), status="PASS"):
    return make_gate_result_manifest({
        "gate_id": gate_id, "gate_contract_version": f"R14-{gate_id}-v1", "status": status,
        "candidate_repository_commit_sha": _SHA, "candidate_repository_tree_sha": _TREE,
        "input_artifact_refs": [], "output_artifact_refs": [ref(item) for item in outputs],
        "retained_evidence_refs": _EVIDENCE, "proof_execution_identity": execution(gate_id),
        "trusted_time_inputs": {
            "foundation_knowledge_evaluation_at_utc": (
                _KNOWLEDGE_AT if gate_id in ("F-E5", "F-E7") else None),
            "foundation_admission_evaluation_at_utc": None,
            "knowledge_evaluation_at_utc": None,
        },
        "decision_record_refs": [],
    })


def proof(gate_id, kind):
    return make_gate_proof_artifact({
        "proof_kind": kind, "source_gate_id": gate_id,
        "candidate_repository_commit_sha": _SHA, "candidate_repository_tree_sha": _TREE,
        "input_artifact_refs": [], "procedure_or_test_suite_id": f"synthetic-{gate_id}",
        "proof_execution_identity": execution(f"synthetic-{gate_id}"),
        "canonical_result_summary": "synthetic PASS", "retained_evidence_refs": _EVIDENCE,
    })


def inputs():
    knowledge = knowledge_candidate()
    bundle = build_initial_knowledge_bundle_v1(knowledge)
    ttl = make_ttl_capture_placement_proof(proof_payload())
    ff5 = proof("F-F5", "RUNTIME_PROFILE_ATOMICITY")
    ff6 = proof("F-F6", "ARTIFACT_GRAPH_ACYCLICITY")
    schema = build_foundation_schema_artifacts()
    emitter, old_portal, periodic_portal = (
        build_network_sensor_source_health_emitter_contract(),
        build_portal_source_health_emitter_contract(),
        build_periodic_portal_source_health_emitter_contract(),
    )
    emitters = (emitter, old_portal, periodic_portal)
    timeline, clock, _ = binding_pair()
    health = final_source_health_policy()
    retention = make_task01_health_retention_contract(
        health, retained_evidence_horizon_seconds=2_592_000,
        retained_health_horizon_seconds=2_592_600)
    adapter = build_initial_evidence_adapter_contract_set_v1(
        schema["EvidenceSchemaRegistryContract"])
    classification = build_initial_classification_policy_v1(
        knowledge.classification_taxonomy, knowledge.alias_mapping, adapter)
    architecture = make_architecture_contract_reference({
        "architecture_contract_name": "DEVICE-FINGERPRINT-03A-R2 / TASK-04",
        "architecture_revision": "R14", "architecture_status": "FINAL",
        "architecture_document_sha256": "d" * 64,
    })
    named = {name: make_artifact_content(kind, {"synthetic": name})
             for name, kind in _NAMED_TYPES.items() if name not in {
                 "architecture_contract_reference", "evidence_schema_registry_contract",
                 "evidence_adapter_contract_set", "knowledge_bundle", "evidence_source_binding_timeline",
                 "binding_clock_policy", "source_health_policy", "classification_policy",
                 "k2a_conformance_package", "portal_headers_v2_capability_disposition",
                 "task01_health_retention_contract",
             }}
    named.update({
        "architecture_contract_reference": architecture,
        "evidence_schema_registry_contract": schema["EvidenceSchemaRegistryContract"],
        "evidence_adapter_contract_set": adapter,
        "knowledge_bundle": bundle,
        "evidence_source_binding_timeline": timeline,
        "binding_clock_policy": clock,
        "source_health_policy": health,
        "classification_policy": classification,
        "k2a_conformance_package": build_k2a_conformance_package(),
        "portal_headers_v2_capability_disposition": schema["CapabilityDisposition"],
        "task01_health_retention_contract": retention,
    })
    selected = {
        "F-A4": (named["snapshot_content_policy"], named["snapshot_execution_policy"]),
        "F-A5": (named["evidence_schema_registry_contract"],),
        "F-B0": emitters,
        "F-B1": (timeline, clock), "F-B2": (health,), "F-B3": (retention,),
        "F-C2": (named["k2a_conformance_package"],), "F-C3": (ttl,),
        "F-D1": (schema["CapabilityDisposition"],),
        "F-E1": (knowledge.k1_record_set, knowledge.k1_provenance,
                 knowledge.k1_governance, knowledge.k1_freshness_policy),
        "F-E2": (knowledge.k2b_record_set, knowledge.k2b_provenance,
                 knowledge.k2b_governance, knowledge.k2b_freshness_policy),
        "F-E3": (knowledge.k3_portal_rule_set, knowledge.k3_provenance),
        "F-E4": (knowledge.k4_record_set, knowledge.k4_provenance,
                 knowledge.k4_governance, knowledge.k4_freshness_policy),
        "F-E5": tuple(getattr(knowledge, f"{slot}_{kind}")
                      for slot in ("k1", "k2b", "k4")
                      for kind in ("provenance", "governance", "freshness_policy")),
        "F-E6": (knowledge.classification_taxonomy, knowledge.alias_mapping),
        "F-E7": (bundle,), "F-F1": (adapter,), "F-F2": (classification,),
        "F-F3": (named["classification_retention_policy"],),
        "F-F4": (named["product_validation_policy"],),
        "F-F5": (ff5,), "F-F6": (ff6,),
    }
    gates = {name: gate(name, selected.get(name, ())) for name in MANDATORY_PRE_ADMISSION_GATES}
    contents = list(gates.values()) + list(named.values()) + list(schema.values())
    contents.extend((ttl, ff5, ff6, *emitters))
    contents.extend(getattr(knowledge, field) for field in knowledge.__dataclass_fields__)
    return InitialFoundationInputs(
        prerequisite_gates=gates, named_artifacts=named,
        source_health_emitter_contracts=emitters, knowledge_candidate=knowledge,
        immutable_dependencies=tuple(contents), ttl_capture_placement_proof=ttl,
        architecture_document_sha256="d" * 64,
        foundation_repository_commit_sha=_SHA, foundation_repository_tree_sha=_TREE,
        foundation_knowledge_evaluation_at_utc=_KNOWLEDGE_AT,
        classification_foundation_valid_from_utc=_AT,
        task01_database_schema_generation_contract_version=2,
        task01_watermark_generation_contract_version=2,
        snapshot_contract_version=1,
        proof_execution_identity=execution("F-ADMIT-initial-foundation"),
        retained_evidence_refs=_EVIDENCE,
        owner_decision_record_refs=(str(uuid.uuid4()),),
    )


def changed_gate(value, gate_id, *, outputs=None, knowledge_time=None, extra=()):
    gates = dict(value.prerequisite_gates)
    payload = gates[gate_id].semantic_payload
    if outputs is not None:
        payload["output_artifact_refs"] = [ref(item) for item in outputs]
    if knowledge_time is not None:
        payload["trusted_time_inputs"]["foundation_knowledge_evaluation_at_utc"] = knowledge_time
    gates[gate_id] = make_gate_result_manifest(payload)
    return replace(value, prerequisite_gates=gates,
                   immutable_dependencies=(*value.immutable_dependencies, gates[gate_id], *extra))


def fixed_clock(value=_AT):
    calls = []

    def clock():
        calls.append(True)
        return value

    return clock, calls


def test_origin_closed_states_and_matching_ttl():
    ttl = make_ttl_capture_placement_proof(proof_payload())
    enabled = {"origin_runtime_admission_contract_version": 1, "tcp_state": "ENABLED",
               "tcp_reason_code": "TTL_PROOF_VALID", "ttl_capture_placement_proof": ref(ttl)}
    origin = make_origin_runtime_admission(enabled)
    assert origin.semantic_payload["ttl_capture_placement_proof"] == ref(ttl)
    with pytest.raises(DeviceFingerprintValidationError):
        make_origin_runtime_admission({**enabled, "ttl_capture_placement_proof": None})
    with pytest.raises(DeviceFingerprintValidationError):
        make_origin_runtime_admission({**enabled, "tcp_state": "DISABLED",
                                       "tcp_reason_code": "PROFILE_POLICY_DISABLED"})
    assert make_origin_runtime_admission({**enabled, "tcp_state": "DISABLED",
                                          "tcp_reason_code": "TTL_PROOF_INVALID",
                                          "ttl_capture_placement_proof": None}).semantic_payload["tcp_state"] == "DISABLED"


@pytest.mark.parametrize("field,value", [
    ("origin_runtime_admission_contract_version", 2),
    ("origin_runtime_admission_contract_version", True),
    ("tcp_state", "UNKNOWN"),
    ("tcp_reason_code", "PROFILE_POLICY_DISABLED"),
])
def test_origin_rejects_non_v1_or_invalid_enabled_state(field, value):
    ttl = make_ttl_capture_placement_proof(proof_payload())
    payload = {"origin_runtime_admission_contract_version": 1, "tcp_state": "ENABLED",
               "tcp_reason_code": "TTL_PROOF_VALID", "ttl_capture_placement_proof": ref(ttl)}
    payload[field] = value
    with pytest.raises(DeviceFingerprintValidationError):
        make_origin_runtime_admission(payload)


def test_manifest_shape_gate_exclusion_and_origin_ttl_mismatch():
    value = inputs()
    plan = prepare_initial_foundation_admission(value, trusted_admission_clock=lambda: _AT)
    manifest = plan.foundation_admission_manifest
    payload = manifest.semantic_payload
    assert len(payload) == 31
    assert payload["mandatory_pre_admission_foundation_gate_ids"] == list(MANDATORY_PRE_ADMISSION_GATES)
    assert "F-ADMIT" not in payload["mandatory_pre_admission_foundation_gate_ids"]
    assert validate_initial_foundation_manifest_lineage(
        manifest, plan.origin_runtime_admission, value.ttl_capture_placement_proof)
    for wrong in ({**payload, "extra": "forbidden"},
                  {**payload, "mandatory_pre_admission_foundation_gate_ids":
                   [*payload["mandatory_pre_admission_foundation_gate_ids"], "F-ADMIT"]}):
        with pytest.raises(DeviceFingerprintValidationError):
            make_foundation_admission_manifest(wrong)
    other = make_ttl_capture_placement_proof({**proof_payload(),
                                               "capture_topology_identity": "other-topology",
                                               "proof_valid_for_topology_identity": "other-topology"})
    with pytest.raises(DeviceFingerprintValidationError):
        validate_initial_foundation_manifest_lineage(manifest, plan.origin_runtime_admission, other)


@pytest.mark.parametrize("field,value", [
    ("foundation_manifest_version", 2),
    ("foundation_manifest_version", True),
    ("mandatory_pre_admission_foundation_gate_ids", [{"gate": "F-A1"}]),
])
def test_manifest_rejects_non_v1_or_malformed_gate_inventory(field, value):
    plan = prepare_initial_foundation_admission(inputs(), trusted_admission_clock=lambda: _AT)
    payload = plan.foundation_admission_manifest.semantic_payload
    payload[field] = value
    with pytest.raises(DeviceFingerprintValidationError):
        make_foundation_admission_manifest(payload)


@pytest.mark.parametrize("mode", ["missing", "failed"])
def test_prerequisite_gate_failure_has_no_admission(mode):
    value = inputs()
    gates = dict(value.prerequisite_gates)
    if mode == "missing":
        gates.pop("F-A1")
    else:
        gates["F-A1"] = gate("F-A1", status="FAIL")
    with pytest.raises(DeviceFingerprintValidationError):
        prepare_initial_foundation_admission(replace(value, prerequisite_gates=gates),
                                             trusted_admission_clock=lambda: _AT)


def test_prerequisite_output_must_resolve_to_supplied_content():
    value = inputs()
    gates = dict(value.prerequisite_gates)
    gates["F-C3"] = gate("F-C3")
    dependencies = tuple(value.immutable_dependencies) + (gates["F-C3"],)
    with pytest.raises(DeviceFingerprintValidationError):
        prepare_initial_foundation_admission(replace(value, prerequisite_gates=gates,
                                                     immutable_dependencies=dependencies),
                                             trusted_admission_clock=lambda: _AT)


def historical_ff5_inputs():
    value = inputs()
    old_gate = value.prerequisite_gates["F-F5"]
    old_proof_id = old_gate.semantic_payload["output_artifact_refs"][0]["artifact_id"]
    old_proof = next(item for item in value.immutable_dependencies
                     if item.artifact_id == old_proof_id)
    missing_gate_input = make_artifact_content("SnapshotContentPolicy", {"historical": "gate"})
    missing_proof_input = make_artifact_content("SnapshotExecutionPolicy", {"historical": "proof"})
    proof_payload = old_proof.semantic_payload
    proof_payload["input_artifact_refs"] = [ref(missing_proof_input)]
    historical_proof = make_gate_proof_artifact(proof_payload)
    gate_payload = old_gate.semantic_payload
    gate_payload["input_artifact_refs"] = [ref(missing_gate_input)]
    gate_payload["output_artifact_refs"] = [ref(historical_proof)]
    historical_gate = make_gate_result_manifest(gate_payload)
    gates = dict(value.prerequisite_gates)
    gates["F-F5"] = historical_gate
    dependencies = tuple(item for item in value.immutable_dependencies
                         if item.artifact_id not in (old_gate.artifact_id, old_proof.artifact_id))
    return replace(value, prerequisite_gates=gates,
                   immutable_dependencies=(*dependencies, historical_proof, historical_gate)), (
                       historical_proof, historical_gate, missing_gate_input, missing_proof_input)


def test_historical_ff5_inputs_are_opaque_but_exact_output_is_persisted(tmp_path):
    value, (historical_proof, historical_gate, missing_gate_input, missing_proof_input) = (
        historical_ff5_inputs())
    plan = prepare_initial_foundation_admission(value, trusted_admission_clock=lambda: _AT)
    assert historical_gate in plan.immutable_dependencies
    assert historical_proof in plan.immutable_dependencies
    assert missing_gate_input not in plan.immutable_dependencies
    assert missing_proof_input not in plan.immutable_dependencies
    store = DeviceFingerprintControlPlaneStore(tmp_path / "historical.sqlite")
    store.initialize()
    published = execute_initial_foundation_admission(
        value, store, trusted_admission_clock=lambda: _AT)
    assert store.get_published_gate_result("F-ADMIT") == published.f_admit_gate_result_manifest
    assert store.load_artifact(historical_gate.artifact_id, historical_gate.content_sha256) == historical_gate
    assert store.load_artifact(historical_proof.artifact_id, historical_proof.content_sha256) == historical_proof
    with store._connect() as conn:
        for item in (historical_gate, historical_proof):
            assert conn.execute("SELECT count(*) FROM artifact_dependencies WHERE owner_id=?",
                                (item.artifact_id,)).fetchone()[0] == 0


@pytest.mark.parametrize("gate_id", ["F-F5", "F-F6", "F-C3"])
def test_missing_required_prerequisite_output_fails(gate_id):
    value = changed_gate(inputs(), gate_id, outputs=())
    with pytest.raises(DeviceFingerprintValidationError):
        prepare_initial_foundation_admission(value, trusted_admission_clock=lambda: _AT)


def test_wrong_ff5_proof_digest_fails_closed():
    value = inputs()
    other_proof = proof("F-F5", "RUNTIME_PROFILE_ATOMICITY")
    other_payload = other_proof.semantic_payload
    other_payload["canonical_result_summary"] = "different historical proof digest"
    other_proof = make_gate_proof_artifact(other_payload)
    value = changed_gate(value, "F-F5", outputs=(other_proof,))
    with pytest.raises(DeviceFingerprintValidationError, match="Unresolved prerequisite output F-F5"):
        prepare_initial_foundation_admission(value, trusted_admission_clock=lambda: _AT)


@pytest.mark.parametrize("mode", ["negative", "expired", "ineligible"])
def test_external_unusable_source_fails(mode):
    value = inputs()
    source = value.knowledge_candidate
    provenance_payload = source.k1_provenance.semantic_payload
    if mode == "negative":
        provenance_payload["retrieved_at_utc"] = "2026-09-23T00:00:00.001Z"
    elif mode == "expired":
        provenance_payload["retrieved_at_utc"] = "2010-01-01T00:00:00.000Z"
    else:
        policy_payload = source.k1_freshness_policy.semantic_payload
        policy_payload["freshness_state_rules"][0].update(
            claim_eligible=False, claim_strength_cap="NONE",
            required_explanation_code="synthetic_ineligible")
        policy = make_knowledge_freshness_policy(policy_payload)
        source = replace(source, k1_freshness_policy=policy)
        provenance_payload["knowledge_freshness_policy"] = ref(policy)
    provenance = make_external_knowledge_provenance_manifest(provenance_payload)
    source = replace(source, k1_provenance=provenance)
    # Failure must come from the final freshness check, not a stale bundle ref.
    from app.device_fingerprint.knowledge_artifacts import make_canonical_k1_record_set
    records_payload = source.k1_record_set.semantic_payload
    records_payload["knowledge_provenance"] = ref(provenance)
    source = replace(source, k1_record_set=make_canonical_k1_record_set(records_payload))
    bundle = build_initial_knowledge_bundle_v1(source)
    named = dict(value.named_artifacts)
    named["knowledge_bundle"] = bundle
    contents = tuple(value.immutable_dependencies) + (provenance, source.k1_record_set,
                                                        bundle, source.k1_freshness_policy)
    value = replace(value, knowledge_candidate=source, named_artifacts=named,
                    immutable_dependencies=contents)
    value = changed_gate(value, "F-E1", outputs=(source.k1_record_set, source.k1_provenance,
                                                 source.k1_governance, source.k1_freshness_policy))
    value = changed_gate(value, "F-E5", outputs=tuple(
        getattr(source, f"{slot}_{kind}") for slot in ("k1", "k2b", "k4")
        for kind in ("provenance", "governance", "freshness_policy")))
    value = changed_gate(value, "F-E7", outputs=(bundle,))
    with pytest.raises(DeviceFingerprintValidationError, match="Mandatory k1 knowledge unusable"):
        prepare_initial_foundation_admission(value, trusted_admission_clock=lambda: _AT)


def test_trusted_admission_clock_called_once_for_all_sources(monkeypatch):
    value = inputs()
    clock, calls = fixed_clock()
    observed = []
    import app.device_fingerprint.f_admit_foundation as module
    original = module.evaluate_external_knowledge_freshness

    def observe(*args, **kwargs):
        observed.append(kwargs["knowledge_evaluation_at_utc"])
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "evaluate_external_knowledge_freshness", observe)
    plan = prepare_initial_foundation_admission(value, trusted_admission_clock=clock)
    assert len(calls) == 1
    assert observed == [_AT, _AT, _AT]
    assert plan.admission_evaluation_at_utc == _AT
    assert plan.runtime_profile_admission_manifest.semantic_payload["profile_kind"] == "foundation"
    assert plan.runtime_profile_admission_manifest.semantic_payload["update_class"] == "INITIAL_FOUNDATION"
    assert all(plan.runtime_profile_admission_manifest.semantic_payload[field] is None for field in (
        "previous_active_profile", "expected_previous_activation_record_id",
        "expected_previous_activation_generation_id"))
    assert plan.f_admit_gate_result_manifest.semantic_payload["status"] == "PASS"
    assert plan.f_admit_gate_result_manifest.artifact_id not in str(
        [item.semantic_payload for item in (
            plan.origin_runtime_admission, plan.foundation_admission_manifest,
            plan.foundation_runtime_profile, plan.runtime_profile_admission_manifest,
            plan.activation_record, plan.initial_validity_record)])


@pytest.mark.parametrize("field", ["retained_evidence_refs", "owner_decision_record_refs"])
def test_final_gate_requires_retained_evidence_and_owner_decision(field):
    value = inputs()
    with pytest.raises(DeviceFingerprintValidationError):
        prepare_initial_foundation_admission(replace(value, **{field: ()}),
                                             trusted_admission_clock=lambda: _AT)


def test_fe5_trusted_time_must_equal_supplied_and_fe7():
    value = changed_gate(inputs(), "F-E5", knowledge_time="2026-09-22T22:30:34.465Z")
    with pytest.raises(DeviceFingerprintValidationError, match="trusted knowledge time mismatch"):
        prepare_initial_foundation_admission(value, trusted_admission_clock=lambda: _AT)
    value = changed_gate(inputs(), "F-E7", knowledge_time="2026-09-22T22:30:34.465Z")
    with pytest.raises(DeviceFingerprintValidationError, match="trusted knowledge time mismatch"):
        prepare_initial_foundation_admission(value, trusted_admission_clock=lambda: _AT)


def test_fe7_pass_gate_must_output_exact_selected_bundle():
    value = inputs()
    wrong = make_artifact_content("KnowledgeBundle", {"synthetic": "wrong-bundle"})
    value = changed_gate(value, "F-E7", outputs=(wrong,), extra=(wrong,))
    with pytest.raises(DeviceFingerprintValidationError, match="F-E7 did not admit exact KnowledgeBundle"):
        prepare_initial_foundation_admission(value, trusted_admission_clock=lambda: _AT)


def test_correct_type_artifact_from_wrong_gate_is_not_admitted():
    value = inputs()
    named = dict(value.named_artifacts)
    other = make_artifact_content("SnapshotContentPolicy", {"synthetic": "not-F-A4-output"})
    named["snapshot_content_policy"] = other
    value = replace(value, named_artifacts=named,
                    immutable_dependencies=(*value.immutable_dependencies, other))
    with pytest.raises(DeviceFingerprintValidationError, match="F-A4 did not admit exact"):
        prepare_initial_foundation_admission(value, trusted_admission_clock=lambda: _AT)


def test_architecture_document_sha_matches_exact_selected_reference():
    value = replace(inputs(), architecture_document_sha256="e" * 64)
    with pytest.raises(DeviceFingerprintValidationError, match="Architecture document SHA256 mismatch"):
        prepare_initial_foundation_admission(value, trusted_admission_clock=lambda: _AT)


def test_architecture_reference_must_be_r14_final():
    value = inputs()
    named = dict(value.named_artifacts)
    original = named["architecture_contract_reference"].semantic_payload
    named["architecture_contract_reference"] = make_artifact_content(
        "ArchitectureContractReference", {**original, "architecture_status": "DRAFT"})
    value = replace(value, named_artifacts=named,
                    immutable_dependencies=(*value.immutable_dependencies,
                                            named["architecture_contract_reference"]))
    with pytest.raises(DeviceFingerprintValidationError, match="ArchitectureContractReference authority"):
        prepare_initial_foundation_admission(value, trusted_admission_clock=lambda: _AT)


def test_evidence_adapter_dependency_mismatch_blocks_compatibility_pass():
    value = inputs()
    named = dict(value.named_artifacts)
    payload = named["evidence_adapter_contract_set"].semantic_payload
    other_registry = make_artifact_content("EvidenceSchemaRegistryContract", {"synthetic": "other"})
    payload["evidence_schema_registry"] = ref(other_registry)
    named["evidence_adapter_contract_set"] = make_evidence_adapter_contract_set(payload)
    value = replace(value, named_artifacts=named,
                    immutable_dependencies=(*value.immutable_dependencies,
                                            named["evidence_adapter_contract_set"], other_registry))
    value = changed_gate(value, "F-F1", outputs=(named["evidence_adapter_contract_set"],))
    with pytest.raises(DeviceFingerprintValidationError):
        prepare_initial_foundation_admission(value, trusted_admission_clock=lambda: _AT)


def test_classification_policy_dependency_mismatch_blocks_compatibility_pass():
    value = inputs()
    named = dict(value.named_artifacts)
    other_alias = make_artifact_content("AliasMapping", {"synthetic": "other"})
    named["classification_policy"] = build_initial_classification_policy_v1(
        value.knowledge_candidate.classification_taxonomy, other_alias,
        named["evidence_adapter_contract_set"])
    value = replace(value, named_artifacts=named,
                    immutable_dependencies=(*value.immutable_dependencies,
                                            named["classification_policy"], other_alias))
    value = changed_gate(value, "F-F2", outputs=(named["classification_policy"],))
    with pytest.raises(DeviceFingerprintValidationError):
        prepare_initial_foundation_admission(value, trusted_admission_clock=lambda: _AT)


def test_task01_retention_policy_mismatch_blocks_compatibility_pass():
    value = inputs()
    named = dict(value.named_artifacts)
    payload = named["task01_health_retention_contract"].semantic_payload
    wrong_policy = make_artifact_content("SourceHealthPolicy", {"synthetic": "wrong"})
    payload["source_health_policy"] = ref(wrong_policy)
    named["task01_health_retention_contract"] = make_artifact_content(
        "Task01HealthRetentionContract", payload)
    value = replace(value, named_artifacts=named,
                    immutable_dependencies=(*value.immutable_dependencies,
                                            named["task01_health_retention_contract"], wrong_policy))
    value = changed_gate(value, "F-B3", outputs=(named["task01_health_retention_contract"],))
    with pytest.raises(DeviceFingerprintValidationError):
        prepare_initial_foundation_admission(value, trusted_admission_clock=lambda: _AT)


def test_f_admit_inputs_complete_and_exclude_all_new_outputs():
    value = inputs()
    plan = prepare_initial_foundation_admission(value, trusted_admission_clock=lambda: _AT)
    expected = build_f_admit_input_refs(
        value.named_artifacts["architecture_contract_reference"],
        [value.prerequisite_gates[name] for name in MANDATORY_PRE_ADMISSION_GATES])
    assert plan.f_admit_gate_result_manifest.semantic_payload["input_artifact_refs"] == expected
    assert ref(value.named_artifacts["architecture_contract_reference"]) in expected
    assert all(ref(gate) in expected for gate in value.prerequisite_gates.values())
    assert all(output in expected for gate in value.prerequisite_gates.values()
               for output in gate.semantic_payload["output_artifact_refs"])
    assert not {item.artifact_id for item in (
        plan.origin_runtime_admission, plan.foundation_admission_manifest,
        plan.foundation_runtime_profile, plan.runtime_profile_admission_manifest,
        plan.activation_record, plan.initial_validity_record)} & {
            item["artifact_id"] for item in expected}


def test_active_pointer_requires_nonnull_updated_at():
    with pytest.raises(TypeError):
        ActiveProfilePointerV1("foundation", "profile", "digest", "activation", "generation")
    with pytest.raises(DeviceFingerprintValidationError):
        ActiveProfilePointerV1("foundation", "profile", "digest", "activation", "generation", None)


def test_control_plane_rejects_noncanonical_new_admission_artifacts(tmp_path):
    store = DeviceFingerprintControlPlaneStore(tmp_path / "validation.sqlite")
    store.initialize()
    for kind in ("OriginRuntimeAdmission", "FoundationAdmissionManifest"):
        invalid = make_artifact_content(kind, {"synthetic": "wrong-shape"})
        with pytest.raises(DeviceFingerprintValidationError):
            store.persist_artifact(invalid)


def state(store):
    with store._connect() as conn:
        return {table: conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                for table in ("activations", "validities", "validity_heads",
                              "f_admit_publications", "active_pointers")}


@pytest.mark.parametrize("field,wrong", [
    ("gate_contract_version", "R14-F-ADMIT-v2"),
    ("foundation_knowledge_evaluation_at_utc", "2026-09-22T22:30:34.465Z"),
    ("foundation_admission_evaluation_at_utc", "2026-09-23T00:00:00.001Z"),
    ("candidate_repository_commit_sha", "c" * 40),
    ("candidate_repository_tree_sha", "d" * 40),
])
def test_direct_publication_rejects_wrong_gate_lineage_without_mutation(tmp_path, field, wrong):
    value = inputs()
    plan = prepare_initial_foundation_admission(value, trusted_admission_clock=lambda: _AT)
    store = DeviceFingerprintControlPlaneStore(tmp_path / "direct-guard.sqlite")
    store.initialize()
    prerequisite_gate_ids = frozenset(item.artifact_id for item in value.prerequisite_gates.values())
    for content in plan.immutable_dependencies:
        store.persist_artifact(content, _admission_direct_refs(content, prerequisite_gate_ids))
    payload = plan.f_admit_gate_result_manifest.semantic_payload
    if field in payload["trusted_time_inputs"]:
        payload["trusted_time_inputs"][field] = wrong
    else:
        payload[field] = wrong
    invalid_gate = make_gate_result_manifest(payload)
    with pytest.raises(ControlPlaneOperationError, match="f_admit_gate_invalid"):
        store.publish_initial_foundation(
            plan.runtime_profile_admission_manifest, plan.activation_record,
            plan.initial_validity_record, invalid_gate)
    assert set(state(store).values()) == {0}


def test_atomic_success_and_restart_load(tmp_path):
    path = tmp_path / "isolated.sqlite"
    store = DeviceFingerprintControlPlaneStore(path)
    store.initialize()
    plan = execute_initial_foundation_admission(inputs(), store, trusted_admission_clock=lambda: _AT)
    assert set(state(store).values()) == {1}
    pointer = store.get_active_pointer("foundation")
    assert pointer.updated_at_utc == _AT
    with store._connect() as conn:
        row = conn.execute("SELECT updated_at_utc FROM validity_heads").fetchone()
    assert row[0] == _AT
    assert store.get_published_gate_result("F-ADMIT") == plan.f_admit_gate_result_manifest
    restarted = DeviceFingerprintControlPlaneStore(path)
    restarted.initialize()
    gate_result, pinned, manifest, origin = restarted.load_published_initial_foundation()
    assert gate_result == plan.f_admit_gate_result_manifest
    assert pinned.runtime_profile == plan.foundation_runtime_profile
    assert manifest == plan.foundation_admission_manifest
    assert origin == plan.origin_runtime_admission
    with pytest.raises(ControlPlaneOperationError):
        execute_initial_foundation_admission(inputs(), restarted, trusted_admission_clock=lambda: _AT)
    assert set(state(restarted).values()) == {1}


def test_migrated_pointer_and_head_backfill_canonical_utc(tmp_path):
    path = tmp_path / "legacy-control-plane.sqlite"
    store = DeviceFingerprintControlPlaneStore(path)
    store.initialize()
    execute_initial_foundation_admission(inputs(), store, trusted_admission_clock=lambda: _AT)
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("ALTER TABLE active_pointers DROP COLUMN updated_at_utc")
        conn.execute("ALTER TABLE validity_heads DROP COLUMN updated_at_utc")
    migrated = DeviceFingerprintControlPlaneStore(path)
    migrated.initialize()
    assert migrated.get_active_pointer("foundation").updated_at_utc == _AT
    with migrated._connect() as conn:
        assert conn.execute("SELECT updated_at_utc FROM validity_heads").fetchone()[0] == _AT
        assert conn.execute("SELECT updated_at_utc FROM active_pointers").fetchone()[0] == _AT


@pytest.mark.parametrize("stage,committed", [
    ("BEFORE_BEGIN", False), ("AFTER_BEGIN_BEFORE_WRITES", False),
    ("AFTER_VALIDITY_BEFORE_GATE", False), ("BEFORE_POINTER_WRITE", False),
    ("AFTER_WRITES_BEFORE_COMMIT", False), ("AFTER_COMMIT", True),
])
def test_injected_failure_is_empty_or_complete(tmp_path, stage, committed):
    def fault(actual):
        if actual == stage:
            raise RuntimeError(stage)

    store = DeviceFingerprintControlPlaneStore(tmp_path / "isolated.sqlite", fault_hook=fault)
    store.initialize()
    with pytest.raises(RuntimeError, match=stage):
        execute_initial_foundation_admission(inputs(), store, trusted_admission_clock=lambda: _AT)
    assert set(state(store).values()) == ({1} if committed else {0})


def test_existing_pointer_fails_without_mutation(tmp_path):
    store = DeviceFingerprintControlPlaneStore(tmp_path / "isolated.sqlite")
    store.initialize()
    execute_initial_foundation_admission(inputs(), store, trusted_admission_clock=lambda: _AT)
    before = state(store)
    with pytest.raises(ControlPlaneOperationError):
        execute_initial_foundation_admission(inputs(), store, trusted_admission_clock=lambda: _AT)
    assert state(store) == before
