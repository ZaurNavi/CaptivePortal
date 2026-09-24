"""Reusable R14 INITIAL_FOUNDATION admission from caller-supplied exact artifacts."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from .artifact_content import ArtifactContent, ArtifactRef
from .artifact_dependency_graph import (
    ArtifactDependencyNode, analyze_artifact_dependency_graph,
    extract_direct_artifact_refs,
)
from .binding_contracts import make_evidence_source_binding_timeline
from .classification_policy import validate_classification_policy_dependencies
from .control_plane_store import ControlPlaneOperationError, DeviceFingerprintControlPlaneStore
from .evidence_adapter_contracts import validate_evidence_adapter_contract_set_dependencies
from .fe5_external_knowledge import evaluate_external_knowledge_freshness
from .foundation_admission_artifacts import (
    MANDATORY_PRE_ADMISSION_GATES, build_f_admit_input_refs,
    make_architecture_contract_reference, make_foundation_admission_manifest,
    make_origin_runtime_admission, validate_initial_foundation_manifest_lineage,
)
from .foundation_gate_artifacts import make_gate_result_manifest
from .gate_proof_artifacts import make_gate_proof_artifact
from .health_retention_contract import make_task01_health_retention_contract
from .knowledge_bundle import KnowledgeBundleCandidate, validate_knowledge_bundle_dependencies
from .models import DeviceFingerprintValidationError
from .runtime_profile_artifacts import (
    make_foundation_runtime_profile, make_runtime_profile_activation_record,
    make_runtime_profile_admission_manifest, make_runtime_profile_validity_record,
)
from .ttl_capture_placement_proof import make_ttl_capture_placement_proof
from .source_health_policy import make_source_health_policy
from .validation import parse_utc

_SINGLE_INPUTS = {
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
_PROFILE_INPUTS = (
    "evidence_source_binding_timeline", "binding_clock_policy", "source_health_policy",
    "snapshot_content_policy", "snapshot_execution_policy",
    "evidence_schema_registry_contract", "task01_health_retention_contract",
)


def _fail(reason: str) -> None:
    raise DeviceFingerprintValidationError(reason)


def _ref(content: ArtifactContent) -> dict[str, str]:
    if not isinstance(content, ArtifactContent):
        _fail("Missing exact ArtifactContent")
    return ArtifactRef(content.artifact_id, content.content_sha256).as_dict()


def _validated(content: ArtifactContent, kind: str, validator=None) -> ArtifactContent:
    if not isinstance(content, ArtifactContent) or content.artifact_type != kind:
        _fail(f"Missing {kind}")
    if validator is not None and validator(content.semantic_payload).artifact_id != content.artifact_id:
        _fail(f"Noncanonical {kind}")
    return content


def _require_outputs(gates: Mapping[str, ArtifactContent], gate_id: str,
                     contents: Sequence[ArtifactContent]) -> None:
    outputs = {ArtifactRef.from_dict(value) for value in
               gates[gate_id].semantic_payload["output_artifact_refs"]}
    for content in contents:
        expected = ArtifactRef(content.artifact_id, content.content_sha256)
        if expected not in outputs:
            _fail(f"{gate_id} did not admit exact {content.artifact_type}")


def _admission_direct_refs(
    content: ArtifactContent, prerequisite_gate_ids: frozenset[str],
) -> tuple[ArtifactRef, ...]:
    """Historical gate/proof inputs are immutable payload, not current closure edges."""
    if (content.artifact_id in prerequisite_gate_ids
            or content.artifact_type == "GateProofArtifact"):
        return ()
    return extract_direct_artifact_refs(content)


def _admission_graph_nodes(
    contents: Mapping[str, ArtifactContent], prerequisite_gate_ids: frozenset[str],
) -> tuple[ArtifactDependencyNode, ...]:
    nodes = []
    for artifact_id, content in sorted(contents.items()):
        refs = _admission_direct_refs(content, prerequisite_gate_ids)
        for ref in refs:
            target = contents.get(ref.artifact_id)
            if target is None or target.content_sha256 != ref.content_sha256:
                _fail("Unresolved F-ADMIT concrete dependency")
        nodes.append(ArtifactDependencyNode(
            artifact_id, content.artifact_type, "CONCRETE",
            tuple(ref.artifact_id for ref in refs),
        ))
    return tuple(nodes)


@dataclass(frozen=True, slots=True)
class InitialFoundationInputs:
    prerequisite_gates: Mapping[str, ArtifactContent]
    named_artifacts: Mapping[str, ArtifactContent]
    source_health_emitter_contracts: Sequence[ArtifactContent]
    knowledge_candidate: KnowledgeBundleCandidate
    immutable_dependencies: Sequence[ArtifactContent]
    ttl_capture_placement_proof: ArtifactContent
    architecture_document_sha256: str
    foundation_repository_commit_sha: str
    foundation_repository_tree_sha: str
    foundation_knowledge_evaluation_at_utc: str
    classification_foundation_valid_from_utc: str
    task01_database_schema_generation_contract_version: int
    task01_watermark_generation_contract_version: int
    snapshot_contract_version: int
    proof_execution_identity: Mapping[str, Any]
    retained_evidence_refs: Sequence[dict[str, Any]]
    owner_decision_record_refs: Sequence[str]


@dataclass(frozen=True, slots=True)
class InitialFoundationPlan:
    admission_evaluation_at_utc: str
    origin_runtime_admission: ArtifactContent
    foundation_admission_manifest: ArtifactContent
    foundation_runtime_profile: ArtifactContent
    runtime_profile_admission_manifest: ArtifactContent
    activation_record: ArtifactContent
    initial_validity_record: ArtifactContent
    f_admit_gate_result_manifest: ArtifactContent
    immutable_dependencies: tuple[ArtifactContent, ...]


def prepare_initial_foundation_admission(
    inputs: InitialFoundationInputs, *, trusted_admission_clock: Callable[[], str],
    uuid_factory: Callable[[], uuid.UUID] = uuid.uuid4,
) -> InitialFoundationPlan:
    """Build only exact caller-supplied lineage; do not inspect external state."""
    if not isinstance(inputs, InitialFoundationInputs):
        _fail("Invalid F-ADMIT inputs")
    if set(inputs.prerequisite_gates) != set(MANDATORY_PRE_ADMISSION_GATES):
        _fail("Incomplete prerequisite gate set")
    supplied: dict[str, ArtifactContent] = {}
    for content in inputs.immutable_dependencies:
        if not isinstance(content, ArtifactContent):
            _fail("Missing immutable dependency")
        earlier = supplied.get(content.artifact_id)
        if earlier is not None and earlier != content:
            _fail("Conflicting immutable dependency")
        supplied[content.artifact_id] = content
    gate_refs = []
    for gate_id in MANDATORY_PRE_ADMISSION_GATES:
        gate = _validated(inputs.prerequisite_gates[gate_id], "GateResultManifest",
                          make_gate_result_manifest)
        if gate.semantic_payload["gate_id"] != gate_id or gate.semantic_payload["status"] != "PASS":
            _fail(f"Prerequisite gate {gate_id} not PASS")
        if supplied.get(gate.artifact_id) != gate:
            _fail(f"Missing durable prerequisite {gate_id}")
        for output in gate.semantic_payload["output_artifact_refs"]:
            ref = ArtifactRef.from_dict(output)
            if supplied.get(ref.artifact_id) is None or supplied[ref.artifact_id].content_sha256 != ref.content_sha256:
                _fail(f"Unresolved prerequisite output {gate_id}")
        gate_refs.append(_ref(gate))
    fe5_time = inputs.prerequisite_gates["F-E5"].semantic_payload[
        "trusted_time_inputs"]["foundation_knowledge_evaluation_at_utc"]
    fe7_time = inputs.prerequisite_gates["F-E7"].semantic_payload[
        "trusted_time_inputs"]["foundation_knowledge_evaluation_at_utc"]
    if (fe5_time is None or fe5_time != inputs.foundation_knowledge_evaluation_at_utc or
            fe7_time != fe5_time):
        _fail("F-E5/F-E7 trusted knowledge time mismatch")
    parse_utc(fe5_time)

    named = {}
    if set(inputs.named_artifacts) != set(_SINGLE_INPUTS):
        _fail("Incomplete named Foundation artifacts")
    for name, kind in _SINGLE_INPUTS.items():
        content = _validated(inputs.named_artifacts[name], kind)
        if supplied.get(content.artifact_id) != content:
            _fail(f"Missing exact {name}")
        named[name] = content
    architecture = _validated(named["architecture_contract_reference"],
                              "ArchitectureContractReference", make_architecture_contract_reference)
    if architecture.semantic_payload["architecture_document_sha256"] != inputs.architecture_document_sha256:
        _fail("Architecture document SHA256 mismatch")
    ttl = _validated(inputs.ttl_capture_placement_proof, "TTLCapturePlacementProof",
                     make_ttl_capture_placement_proof)
    if supplied.get(ttl.artifact_id) != ttl or ttl.semantic_payload["capture_distance_l3_hops"] != 0:
        _fail("Initial TTL placement proof unavailable")
    if _ref(ttl) not in inputs.prerequisite_gates["F-C3"].semantic_payload["output_artifact_refs"]:
        _fail("F-C3 did not admit exact TTL proof")
    for gate_id, expected_kind in (("F-F5", "RUNTIME_PROFILE_ATOMICITY"),
                                   ("F-F6", "ARTIFACT_GRAPH_ACYCLICITY")):
        outputs = inputs.prerequisite_gates[gate_id].semantic_payload["output_artifact_refs"]
        if not any(
            supplied[ref["artifact_id"]].artifact_type == "GateProofArtifact"
            and _validated(supplied[ref["artifact_id"]], "GateProofArtifact",
                           make_gate_proof_artifact).semantic_payload["proof_kind"] == expected_kind
            for ref in outputs
        ):
            _fail(f"Missing exact {gate_id} proof")

    knowledge = named["knowledge_bundle"]
    if (not isinstance(inputs.knowledge_candidate, KnowledgeBundleCandidate) or
            not validate_knowledge_bundle_dependencies(knowledge, inputs.knowledge_candidate)):
        _fail("KnowledgeBundle dependency mismatch")
    source = inputs.knowledge_candidate
    for emitter in inputs.source_health_emitter_contracts:
        _validated(emitter, "SourceHealthEmitterContract")
        if supplied.get(emitter.artifact_id) != emitter:
            _fail("Missing exact source-health emitter")
    owning_outputs = {
        "F-A4": (named["snapshot_content_policy"], named["snapshot_execution_policy"]),
        "F-A5": (named["evidence_schema_registry_contract"],),
        "F-B0": tuple(inputs.source_health_emitter_contracts),
        "F-B1": (named["evidence_source_binding_timeline"], named["binding_clock_policy"]),
        "F-B2": (named["source_health_policy"],),
        "F-B3": (named["task01_health_retention_contract"],),
        "F-C2": (named["k2a_conformance_package"],),
        "F-C3": (ttl,),
        "F-D1": (named["portal_headers_v2_capability_disposition"],),
        "F-E1": (source.k1_record_set, source.k1_provenance, source.k1_governance,
                 source.k1_freshness_policy),
        "F-E2": (source.k2b_record_set, source.k2b_provenance, source.k2b_governance,
                 source.k2b_freshness_policy),
        "F-E3": (source.k3_portal_rule_set, source.k3_provenance),
        "F-E4": (source.k4_record_set, source.k4_provenance, source.k4_governance,
                 source.k4_freshness_policy),
        "F-E5": tuple(getattr(source, f"{slot}_{kind}")
                      for slot in ("k1", "k2b", "k4")
                      for kind in ("provenance", "governance", "freshness_policy")),
        "F-E6": (source.classification_taxonomy, source.alias_mapping),
        "F-E7": (knowledge,),
        "F-F1": (named["evidence_adapter_contract_set"],),
        "F-F2": (named["classification_policy"],),
        "F-F3": (named["classification_retention_policy"],),
        "F-F4": (named["product_validation_policy"],),
    }
    for gate_id, artifacts in owning_outputs.items():
        _require_outputs(inputs.prerequisite_gates, gate_id, artifacts)
    validate_evidence_adapter_contract_set_dependencies(
        named["evidence_adapter_contract_set"],
        evidence_schema_registry=named["evidence_schema_registry_contract"],
        capability_disposition=named["portal_headers_v2_capability_disposition"],
        k2a_conformance_package=named["k2a_conformance_package"],
        k1_record_set=source.k1_record_set,
        k3_portal_rule_set=source.k3_portal_rule_set,
        k4_record_set=source.k4_record_set,
    )
    validate_classification_policy_dependencies(
        named["classification_policy"],
        classification_taxonomy=source.classification_taxonomy,
        alias_mapping=source.alias_mapping,
        evidence_adapter_contract_set=named["evidence_adapter_contract_set"],
    )
    policy = named["source_health_policy"]
    if make_source_health_policy(policy.semantic_payload, inputs.source_health_emitter_contracts) != policy:
        _fail("SourceHealthPolicy/emitter compatibility mismatch")
    retention = named["task01_health_retention_contract"]
    retention_payload = retention.semantic_payload
    if (make_task01_health_retention_contract(
            policy,
            retained_evidence_horizon_seconds=retention_payload["retained_evidence_horizon_seconds"],
            retained_health_horizon_seconds=retention_payload["retained_health_horizon_seconds"],
    ) != retention):
        _fail("Task01HealthRetentionContract/SourceHealthPolicy mismatch")
    timeline = named["evidence_source_binding_timeline"]
    if make_evidence_source_binding_timeline(
            timeline.semantic_payload, inputs.source_health_emitter_contracts) != timeline:
        _fail("BindingTimeline/emitter compatibility mismatch")
    f_admit_inputs = build_f_admit_input_refs(
        architecture, [inputs.prerequisite_gates[name] for name in MANDATORY_PRE_ADMISSION_GATES])
    for value in f_admit_inputs:
        exact = ArtifactRef.from_dict(value)
        if supplied.get(exact.artifact_id) is None or supplied[exact.artifact_id].content_sha256 != exact.content_sha256:
            _fail("Unresolved F-ADMIT input")

    # This is the sole time capture. Every mandatory external source uses it.
    admitted_at = trusted_admission_clock()
    parse_utc(admitted_at)
    for slot in ("k1", "k2b", "k4"):
        result = evaluate_external_knowledge_freshness(
            getattr(inputs.knowledge_candidate, f"{slot}_provenance"),
            getattr(inputs.knowledge_candidate, f"{slot}_freshness_policy"),
            knowledge_evaluation_at_utc=admitted_at,
        )
        if (result["age_ms"] < 0 or result["failure_code"] is not None
                or result["freshness_state"] == "expired" or not result["claim_eligible"]):
            _fail(f"Mandatory {slot} knowledge unusable")

    origin = make_origin_runtime_admission({
        "origin_runtime_admission_contract_version": 1,
        "tcp_state": "ENABLED", "tcp_reason_code": "TTL_PROOF_VALID",
        "ttl_capture_placement_proof": _ref(ttl),
    })
    manifest_payload = {
        "foundation_manifest_version": 1,
        "architecture_document_sha256": inputs.architecture_document_sha256,
        "foundation_repository_commit_sha": inputs.foundation_repository_commit_sha,
        "foundation_repository_tree_sha": inputs.foundation_repository_tree_sha,
        "foundation_knowledge_evaluation_at_utc": inputs.foundation_knowledge_evaluation_at_utc,
        "foundation_admission_evaluation_at_utc": admitted_at,
        "classification_foundation_valid_from_utc": inputs.classification_foundation_valid_from_utc,
        "task01_database_schema_generation_contract_version": inputs.task01_database_schema_generation_contract_version,
        "task01_watermark_generation_contract_version": inputs.task01_watermark_generation_contract_version,
        "mandatory_pre_admission_foundation_gate_ids": list(MANDATORY_PRE_ADMISSION_GATES),
        "pre_admission_gate_result_manifests": gate_refs,
        "source_health_emitter_contracts": [_ref(item) for item in inputs.source_health_emitter_contracts],
        "knowledge_freshness_policies": [_ref(getattr(source, f"{slot}_freshness_policy"))
                                         for slot in ("k1", "k2b", "k4")],
        "source_governance_records": [_ref(getattr(source, f"{slot}_governance"))
                                      for slot in ("k1", "k2b", "k4")],
        "knowledge_provenance_manifests": [_ref(getattr(source, f"{slot}_provenance"))
                                           for slot in ("k1", "k2b", "k3", "k4")],
        "ttl_capture_placement_proof": _ref(ttl),
        "origin_runtime_admission": _ref(origin),
    }
    manifest_payload.update({field: _ref(named[field]) for field in _SINGLE_INPUTS
                             if field != "task01_health_retention_contract"})
    foundation_manifest = make_foundation_admission_manifest(manifest_payload)
    validate_initial_foundation_manifest_lineage(foundation_manifest, origin, ttl)
    profile_payload = {
        "foundation_profile_contract_version": 1,
        "classification_foundation_valid_from_utc": inputs.classification_foundation_valid_from_utc,
        "source_health_emitter_contracts": manifest_payload["source_health_emitter_contracts"],
        "ttl_capture_placement_proof": _ref(ttl),
        "snapshot_contract_version": inputs.snapshot_contract_version,
        "origin_runtime_admission": _ref(origin),
    }
    profile_payload.update({field: _ref(named[field]) for field in _PROFILE_INPUTS})
    profile = make_foundation_runtime_profile(profile_payload)
    rpm = make_runtime_profile_admission_manifest({
        "runtime_profile_admission_contract_version": 1,
        "profile_kind": "foundation", "candidate_profile": _ref(profile),
        "previous_active_profile": None,
        "expected_previous_activation_record_id": None,
        "expected_previous_activation_generation_id": None,
        "update_class": "INITIAL_FOUNDATION",
        "prerequisite_gate_results": gate_refs,
        "compatibility_validation_result": "PASS",
        "candidate_repository_commit_sha": inputs.foundation_repository_commit_sha,
        "candidate_repository_tree_sha": inputs.foundation_repository_tree_sha,
        "foundation_admission_manifest": _ref(foundation_manifest),
        "task04_acceptance_manifest": None,
        "foundation_runtime_profile_admission_manifest": None,
    })
    activation_id, generation_id, validity_id = (str(uuid_factory()) for _ in range(3))
    activation = make_runtime_profile_activation_record({
        "activation_contract_version": 1,
        "activation_record_id": activation_id,
        "profile_kind": "foundation",
        "runtime_profile_id": profile.artifact_id,
        "runtime_profile_digest": profile.content_sha256,
        "runtime_profile_admission_manifest_id": rpm.artifact_id,
        "runtime_profile_admission_manifest_digest": rpm.content_sha256,
        "previous_activation_record_id": None,
        "previous_active_profile_id": None,
        "previous_active_profile_digest": None,
        "activated_at_utc": admitted_at,
        "activation_reason_update_class": "INITIAL_FOUNDATION",
        "activation_result": "ACTIVE",
        "activation_generation_id": generation_id,
    })
    validity = make_runtime_profile_validity_record({
        "runtime_profile_validity_contract_version": 1,
        "validity_record_id": validity_id,
        "profile_kind": "foundation",
        "runtime_profile_id": profile.artifact_id,
        "runtime_profile_digest": profile.content_sha256,
        "activation_record_id": activation_id,
        "state": "ACTIVE", "reason_code": "ACTIVATED",
        "effective_at_utc": admitted_at,
        "inflight_commit_rule": "ALLOW_PINNED_INFLIGHT",
        "previous_validity_record_id": None,
    })
    if not inputs.retained_evidence_refs or not inputs.owner_decision_record_refs:
        _fail("F-ADMIT evidence and Owner decision required")
    outputs = (origin, foundation_manifest, profile, rpm, activation, validity)
    gate = make_gate_result_manifest({
        "gate_id": "F-ADMIT", "gate_contract_version": "R14-F-ADMIT-v1",
        "status": "PASS",
        "candidate_repository_commit_sha": inputs.foundation_repository_commit_sha,
        "candidate_repository_tree_sha": inputs.foundation_repository_tree_sha,
        "input_artifact_refs": f_admit_inputs,
        "output_artifact_refs": [_ref(item) for item in outputs],
        "retained_evidence_refs": list(inputs.retained_evidence_refs),
        "proof_execution_identity": dict(inputs.proof_execution_identity),
        "trusted_time_inputs": {
            "foundation_knowledge_evaluation_at_utc": inputs.foundation_knowledge_evaluation_at_utc,
            "foundation_admission_evaluation_at_utc": admitted_at,
            "knowledge_evaluation_at_utc": None,
        },
        "decision_record_refs": list(inputs.owner_decision_record_refs),
    })
    if (gate.semantic_payload["proof_execution_identity"]["repository_commit_sha"] !=
            inputs.foundation_repository_commit_sha or
            gate.semantic_payload["proof_execution_identity"]["repository_tree_sha"] !=
            inputs.foundation_repository_tree_sha):
        _fail("F-ADMIT proof candidate mismatch")
    for item in outputs:
        if any(ref.artifact_id == gate.artifact_id for ref in extract_direct_artifact_refs(item)):
            _fail("F-ADMIT output references producing gate")
    if {item.artifact_id for item in outputs} & {value["artifact_id"] for value in f_admit_inputs}:
        _fail("F-ADMIT output appears among prerequisite inputs")

    all_contents = {**supplied, **{item.artifact_id: item for item in
                                     (origin, foundation_manifest, profile, rpm)}}
    graph_contents = dict(all_contents)
    for item in (activation, validity, gate):
        if item.artifact_id in graph_contents:
            _fail("Duplicate F-ADMIT output identity")
        graph_contents[item.artifact_id] = item
    prerequisite_gate_ids = frozenset(item.artifact_id for item in inputs.prerequisite_gates.values())
    graph = analyze_artifact_dependency_graph(
        _admission_graph_nodes(graph_contents, prerequisite_gate_ids))
    ordered = tuple(all_contents[artifact_id] for artifact_id in graph.topological_order
                    if artifact_id in all_contents)
    return InitialFoundationPlan(
        admitted_at, origin, foundation_manifest, profile, rpm,
        activation, validity, gate, ordered,
    )


def execute_initial_foundation_admission(
    inputs: InitialFoundationInputs, store: DeviceFingerprintControlPlaneStore, *,
    trusted_admission_clock: Callable[[], str],
    uuid_factory: Callable[[], uuid.UUID] = uuid.uuid4,
) -> InitialFoundationPlan:
    """Persist full immutable closure before one crash-atomic initial publication."""
    if store.get_active_pointer("foundation") is not None:
        raise ControlPlaneOperationError("active_profile_precondition_mismatch")
    plan = prepare_initial_foundation_admission(
        inputs, trusted_admission_clock=trusted_admission_clock, uuid_factory=uuid_factory)
    prerequisite_gate_ids = frozenset(
        ref["artifact_id"] for ref in plan.foundation_admission_manifest.semantic_payload[
            "pre_admission_gate_result_manifests"])
    for content in plan.immutable_dependencies:
        store.persist_artifact(content, _admission_direct_refs(content, prerequisite_gate_ids))
        if store.load_artifact(content.artifact_id, content.content_sha256) != content:
            raise ControlPlaneOperationError("runtime_profile_dependency_unavailable")
    store.publish_initial_foundation(
        plan.runtime_profile_admission_manifest, plan.activation_record,
        plan.initial_validity_record, plan.f_admit_gate_result_manifest,
    )
    return plan
