"""Deterministic R14 ArtifactContent dependency graphs and schema templates."""

from __future__ import annotations

import heapq
import re
from dataclasses import dataclass, replace
from typing import Iterable

from .artifact_content import ArtifactContent, ArtifactRef, canonical_artifact_json
from .models import DeviceFingerprintValidationError


FOUNDATION_TYPES = frozenset("""
ArchitectureContractReference Task01WatermarkReadContract Task01SchemaMigrationContract
Task01GenerationRecoveryContract Task01HealthRetentionContract TcpSynV2SchemaContract
PortalHeadersV2SchemaContract CapabilityDisposition EvidenceSchemaRegistryContract
EvidenceAdapterContractSet SourceHealthEmitterContract EvidenceSourceBindingTimeline
BindingClockPolicy SourceHealthPolicy OriginRuntimeAdmission SnapshotContentPolicy
SnapshotExecutionPolicy ClassificationTaxonomy AliasMapping K3PortalRuleSet
KnowledgeFreshnessPolicy SourceGovernanceRecord KnowledgeProvenanceManifest
CanonicalKnowledgeRecordSet KnowledgeBundle ClassificationPolicy
ClassificationRetentionPolicy ProductValidationPolicy FoundationAdmissionManifest
FoundationRuntimeProfile RuntimeProfileAdmissionManifest RuntimeProfileActivationRecord
RuntimeProfileValidityRecord GateResultManifest GateProofArtifact K2AConformancePackage
TTLCapturePlacementProof
""".split())

TASK04_SPECIFIC_TYPES = frozenset("""
Task04AcceptanceManifest ClassificationRuntimeProfile ClassifierArtifactManifest
EvidenceSnapshotContent SnapshotRecord SourceEvaluability OriginAssessment
ClassificationRequestManifest ClassificationResult ControlledValidationGroundTruthRecord
ProductValidationComparisonRecord
""".split())


class ArtifactDependencyGraphError(ValueError):
    def __init__(self, reason_code: str, cycle_witness: tuple[str, ...] = ()):
        self.reason_code = reason_code
        self.cycle_witness = cycle_witness
        super().__init__(reason_code)


@dataclass(frozen=True, slots=True)
class ArtifactDependencyNode:
    node_id: str
    artifact_type: str
    node_kind: str
    direct_dependency_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if (not isinstance(self.node_id, str) or not self.node_id
                or not isinstance(self.artifact_type, str) or not self.artifact_type
                or self.node_kind not in ("CONCRETE", "TEMPLATE")
                or (self.node_kind == "TEMPLATE") != self.node_id.startswith("template:")
                or (self.node_kind == "CONCRETE" and re.fullmatch(
                    rf"{re.escape(self.artifact_type)}:v1:sha256:[0-9a-f]{{64}}", self.node_id) is None)
                or not isinstance(self.direct_dependency_ids, tuple)
                or any(not isinstance(item, str) or not item for item in self.direct_dependency_ids)
                or self.node_id in self.direct_dependency_ids
                or tuple(sorted(set(self.direct_dependency_ids))) != self.direct_dependency_ids):
            raise ArtifactDependencyGraphError("artifact_dependency_graph_invalid")


@dataclass(frozen=True, slots=True)
class ArtifactDependencyAnalysis:
    nodes: tuple[ArtifactDependencyNode, ...]
    edges: tuple[tuple[str, str], ...]  # dependent -> dependency
    topological_order: tuple[str, ...]  # dependency before dependent


def _add_ref(refs: dict[str, ArtifactRef], value: dict[str, object]) -> None:
    artifact_id, digest = value.get("artifact_id"), value.get("content_sha256")
    if not isinstance(artifact_id, str) or not isinstance(digest, str):
        raise ArtifactDependencyGraphError("artifact_dependency_graph_invalid")
    if artifact_id in refs and refs[artifact_id].content_sha256 != digest:
        raise ArtifactDependencyGraphError("artifact_dependency_digest_mismatch")
    if (re.fullmatch(r"[A-Za-z][A-Za-z0-9]*:v1:sha256:[0-9a-f]{64}", artifact_id)
            and re.fullmatch(r"[0-9a-f]{64}", digest)
            and artifact_id.rsplit(":", 1)[1] != digest):
        raise ArtifactDependencyGraphError("artifact_dependency_digest_mismatch")
    try:
        refs[artifact_id] = ArtifactRef.from_dict(value)
    except DeviceFingerprintValidationError as exc:
        raise ArtifactDependencyGraphError("artifact_dependency_graph_invalid") from exc


def extract_direct_artifact_refs(content: ArtifactContent) -> tuple[ArtifactRef, ...]:
    """Discover ArtifactRefs and the explicitly frozen raw reference shapes."""
    if not isinstance(content, ArtifactContent):
        raise ArtifactDependencyGraphError("artifact_dependency_graph_invalid")
    refs: dict[str, ArtifactRef] = {}

    def raw_pair(value: dict[str, object], id_field: str, digest_field: str,
                 *, nullable: bool = False, required: bool = False,
                 expected_type: str | None = None) -> None:
        if id_field not in value and digest_field not in value and not required:
            return
        if id_field not in value or digest_field not in value:
            raise ArtifactDependencyGraphError("artifact_dependency_graph_invalid")
        artifact_id, digest = value[id_field], value[digest_field]
        if nullable and artifact_id is None and digest is None:
            return
        if artifact_id is None or digest is None:
            raise ArtifactDependencyGraphError("artifact_dependency_graph_invalid")
        if expected_type is not None and (not isinstance(artifact_id, str)
                                          or not artifact_id.startswith(f"{expected_type}:v1:sha256:")):
            raise ArtifactDependencyGraphError("artifact_dependency_graph_invalid")
        _add_ref(refs, {"artifact_id": artifact_id, "content_sha256": digest})

    def visit(value: object, field: str = "") -> None:
        if isinstance(value, dict):
            if set(value) == {"artifact_id", "content_sha256"}:
                _add_ref(refs, value)
                return
            if field == "origin_runtime_admission":
                raw_pair(value, "artifact_id", "content_sha256", required=True,
                         expected_type="OriginRuntimeAdmission")
            if {"knowledge_bundle_id", "knowledge_bundle_digest",
                    "canonical_knowledge_record_id", "knowledge_provenance_id",
                    "knowledge_provenance_digest", "rule_or_source_record_identity"} == set(value):
                raw_pair(value, "knowledge_bundle_id", "knowledge_bundle_digest", required=True,
                         expected_type="KnowledgeBundle")
                raw_pair(value, "knowledge_provenance_id", "knowledge_provenance_digest",
                         required=True, expected_type="KnowledgeProvenanceManifest")
            if {"evidence_id", "payload_sha256", "feature_schema_version",
                    "adapter_contract_id", "adapter_contract_digest"} == set(value):
                raw_pair(value, "adapter_contract_id", "adapter_contract_digest", required=True)
            for name, child in value.items():
                if field == "origin_runtime_admission" and name in ("artifact_id", "content_sha256"):
                    continue
                visit(child, name)
        elif isinstance(value, list):
            for child in value:
                visit(child, field)

    payload = content.semantic_payload
    visit(payload)
    pairs = ()
    if content.artifact_type == "RuntimeProfileActivationRecord":
        pairs = (
            ("runtime_profile_id", "runtime_profile_digest"),
            ("runtime_profile_admission_manifest_id", "runtime_profile_admission_manifest_digest"),
            ("previous_active_profile_id", "previous_active_profile_digest"),
        )
    elif content.artifact_type == "RuntimeProfileValidityRecord":
        pairs = (("runtime_profile_id", "runtime_profile_digest"),)
    for id_field, digest_field in pairs:
        raw_pair(payload, id_field, digest_field,
                 nullable=id_field == "previous_active_profile_id", required=True)
    return tuple(sorted(refs.values(), key=lambda ref: (
        ref.artifact_id, canonical_artifact_json(ref.as_dict()))))


def build_concrete_artifact_graph(contents: Iterable[ArtifactContent]) -> tuple[ArtifactDependencyNode, ...]:
    by_id: dict[str, ArtifactContent] = {}
    try:
        for content in contents:
            if not isinstance(content, ArtifactContent):
                raise ArtifactDependencyGraphError("artifact_dependency_graph_invalid")
            earlier = by_id.get(content.artifact_id)
            if earlier is not None and earlier != content:
                raise ArtifactDependencyGraphError("artifact_dependency_graph_invalid")
            by_id[content.artifact_id] = content
    except (TypeError, ValueError) as exc:
        if isinstance(exc, ArtifactDependencyGraphError):
            raise
        raise ArtifactDependencyGraphError("artifact_dependency_graph_invalid") from exc
    nodes = []
    for artifact_id, content in sorted(by_id.items()):
        refs = extract_direct_artifact_refs(content)
        for ref in refs:
            target = by_id.get(ref.artifact_id)
            if target is None:
                raise ArtifactDependencyGraphError("artifact_dependency_missing")
            if target.content_sha256 != ref.content_sha256:
                raise ArtifactDependencyGraphError("artifact_dependency_digest_mismatch")
        nodes.append(ArtifactDependencyNode(
            artifact_id, content.artifact_type, "CONCRETE",
            tuple(ref.artifact_id for ref in refs)))
    return tuple(nodes)


def _cycle_witness(by_id: dict[str, ArtifactDependencyNode], unresolved: set[str]) -> tuple[str, ...]:
    visited: set[str] = set()
    stack: list[str] = []
    positions: dict[str, int] = {}

    def walk(node_id: str) -> tuple[str, ...]:
        visited.add(node_id)
        positions[node_id] = len(stack)
        stack.append(node_id)
        for dependency in by_id[node_id].direct_dependency_ids:
            if dependency not in unresolved:
                continue
            if dependency in positions:
                return tuple(stack[positions[dependency]:] + [dependency])
            if dependency not in visited:
                witness = walk(dependency)
                if witness:
                    return witness
        stack.pop()
        del positions[node_id]
        return ()

    for node_id in sorted(unresolved):
        if node_id not in visited:
            witness = walk(node_id)
            if witness:
                return witness
    return ()


def analyze_artifact_dependency_graph(
    nodes: Iterable[ArtifactDependencyNode],
) -> ArtifactDependencyAnalysis:
    by_id: dict[str, ArtifactDependencyNode] = {}
    try:
        for node in nodes:
            if not isinstance(node, ArtifactDependencyNode) or node.node_id in by_id:
                raise ArtifactDependencyGraphError("artifact_dependency_graph_invalid")
            by_id[node.node_id] = node
    except TypeError as exc:
        raise ArtifactDependencyGraphError("artifact_dependency_graph_invalid") from exc
    dependents: dict[str, list[str]] = {node_id: [] for node_id in by_id}
    pending = {}
    for node_id, node in by_id.items():
        pending[node_id] = len(node.direct_dependency_ids)
        for dependency in node.direct_dependency_ids:
            if dependency not in by_id:
                raise ArtifactDependencyGraphError("artifact_dependency_missing")
            dependents[dependency].append(node_id)
    eligible = [node_id for node_id, count in pending.items() if count == 0]
    heapq.heapify(eligible)
    order = []
    while eligible:
        node_id = heapq.heappop(eligible)
        order.append(node_id)
        for dependent in sorted(dependents[node_id]):
            pending[dependent] -= 1
            if pending[dependent] == 0:
                heapq.heappush(eligible, dependent)
    if len(order) != len(by_id):
        unresolved = set(by_id).difference(order)
        raise ArtifactDependencyGraphError(
            "artifact_dependency_cycle", _cycle_witness(by_id, unresolved))
    inventory = tuple(by_id[node_id] for node_id in sorted(by_id))
    edges = tuple(sorted((node.node_id, dependency) for node in inventory
                         for dependency in node.direct_dependency_ids))
    return ArtifactDependencyAnalysis(inventory, edges, tuple(order))


def _template_nodes(definitions: dict[str, tuple[str, Iterable[str]]]) -> tuple[ArtifactDependencyNode, ...]:
    return tuple(ArtifactDependencyNode(node_id, artifact_type, "TEMPLATE",
                                        tuple(sorted(set(dependencies))))
                 for node_id, (artifact_type, dependencies) in sorted(definitions.items()))


def build_foundation_schema_template_graph() -> tuple[ArtifactDependencyNode, ...]:
    prefix = "template:foundation:"
    node = lambda name: prefix + name
    definitions: dict[str, tuple[str, Iterable[str]]] = {
        node(kind): (kind, ()) for kind in FOUNDATION_TYPES.difference({
            "KnowledgeProvenanceManifest", "CanonicalKnowledgeRecordSet",
            "SourceGovernanceRecord", "KnowledgeFreshnessPolicy",
            "SourceHealthEmitterContract"})
    }
    for kind, slots in (
        ("KnowledgeProvenanceManifest", ("K1", "K2B", "K3", "K4")),
        ("CanonicalKnowledgeRecordSet", ("K1", "K2B", "K4")),
        ("SourceGovernanceRecord", ("K1", "K2B", "K4")),
        ("KnowledgeFreshnessPolicy", ("K1", "K2B", "K4")),
        ("SourceHealthEmitterContract", ("NETWORK", "PORTAL_HISTORICAL", "PORTAL_PERIODIC")),
    ):
        for slot in slots:
            definitions[node(f"{kind}:{slot}")] = (kind, ())

    def bind(name: str, *dependencies: str) -> None:
        artifact_type = name.split(":", 1)[0]
        definitions[node(name)] = (artifact_type, tuple(node(dependency) for dependency in dependencies))

    definitions[node("PrerequisiteGateResultManifest")] = (
        "GateResultManifest", (node("CapabilityDisposition"),))
    bind("OriginRuntimeAdmission", "TTLCapturePlacementProof")
    for slot in ("K1", "K2B", "K4"):
        bind(f"KnowledgeProvenanceManifest:{slot}",
             f"KnowledgeFreshnessPolicy:{slot}", f"SourceGovernanceRecord:{slot}")
        bind(f"CanonicalKnowledgeRecordSet:{slot}", f"KnowledgeProvenanceManifest:{slot}")
    bind("KnowledgeProvenanceManifest:K3", "K3PortalRuleSet", "ClassificationTaxonomy")
    bind("KnowledgeBundle", "ClassificationTaxonomy", "AliasMapping", "K3PortalRuleSet",
         *(f"KnowledgeProvenanceManifest:{slot}" for slot in ("K1", "K2B", "K3", "K4")),
         *(f"SourceGovernanceRecord:{slot}" for slot in ("K1", "K2B", "K4")),
         *(f"KnowledgeFreshnessPolicy:{slot}" for slot in ("K1", "K2B", "K4")),
         *(f"CanonicalKnowledgeRecordSet:{slot}" for slot in ("K1", "K2B", "K4")))
    bind("ClassificationPolicy", "ClassificationTaxonomy", "AliasMapping",
         "EvidenceAdapterContractSet")
    bind("EvidenceSchemaRegistryContract", "TcpSynV2SchemaContract", "PortalHeadersV2SchemaContract",
         "CapabilityDisposition")
    bind("EvidenceAdapterContractSet", "EvidenceSchemaRegistryContract")
    bind("Task01HealthRetentionContract", "SourceHealthPolicy")
    bind("EvidenceSourceBindingTimeline", *(f"SourceHealthEmitterContract:{slot}" for slot in (
        "NETWORK", "PORTAL_HISTORICAL", "PORTAL_PERIODIC")))
    bind("SourceHealthPolicy", *(f"SourceHealthEmitterContract:{slot}" for slot in (
        "NETWORK", "PORTAL_HISTORICAL", "PORTAL_PERIODIC")))
    bind("FoundationAdmissionManifest",
         "ArchitectureContractReference", "PrerequisiteGateResultManifest",
         "EvidenceSchemaRegistryContract", "EvidenceAdapterContractSet", "KnowledgeBundle",
         "EvidenceSourceBindingTimeline", "BindingClockPolicy", "SourceHealthPolicy",
         *(f"SourceHealthEmitterContract:{slot}" for slot in (
             "NETWORK", "PORTAL_HISTORICAL", "PORTAL_PERIODIC")),
         "SnapshotContentPolicy", "SnapshotExecutionPolicy",
         "ClassificationPolicy", "ClassificationRetentionPolicy", "ProductValidationPolicy",
         *(f"KnowledgeFreshnessPolicy:{slot}" for slot in ("K1", "K2B", "K4")),
         *(f"SourceGovernanceRecord:{slot}" for slot in ("K1", "K2B", "K4")),
         *(f"KnowledgeProvenanceManifest:{slot}" for slot in ("K1", "K2B", "K3", "K4")),
         "K2AConformancePackage", "TTLCapturePlacementProof", "OriginRuntimeAdmission",
         "CapabilityDisposition")
    bind("FoundationRuntimeProfile", "EvidenceSourceBindingTimeline", "BindingClockPolicy",
         "SourceHealthPolicy", "SnapshotContentPolicy", "SnapshotExecutionPolicy",
         "EvidenceSchemaRegistryContract", "Task01HealthRetentionContract", "OriginRuntimeAdmission",
         *(f"SourceHealthEmitterContract:{slot}" for slot in (
             "NETWORK", "PORTAL_HISTORICAL", "PORTAL_PERIODIC")),
         "TTLCapturePlacementProof")
    bind("RuntimeProfileAdmissionManifest", "FoundationRuntimeProfile", "FoundationAdmissionManifest",
         "PrerequisiteGateResultManifest")
    bind("RuntimeProfileActivationRecord", "FoundationRuntimeProfile", "RuntimeProfileAdmissionManifest")
    bind("RuntimeProfileValidityRecord", "FoundationRuntimeProfile")
    bind("GateResultManifest", "PrerequisiteGateResultManifest", "CapabilityDisposition",
         "FoundationAdmissionManifest", "OriginRuntimeAdmission",
         "FoundationRuntimeProfile", "RuntimeProfileAdmissionManifest",
         "RuntimeProfileActivationRecord", "RuntimeProfileValidityRecord")
    return _template_nodes(definitions)


def build_task04_schema_template_graph() -> tuple[ArtifactDependencyNode, ...]:
    foundation = build_foundation_schema_template_graph()
    prefix = "template:task04:"
    node = lambda name: prefix + name
    foundation_node = lambda name: "template:foundation:" + name
    definitions: dict[str, tuple[str, Iterable[str]]] = {
        item.node_id: (item.artifact_type, item.direct_dependency_ids) for item in foundation
    }
    definitions.update({node(kind): (kind, ()) for kind in TASK04_SPECIFIC_TYPES})
    definitions[node("PrerequisiteGateResultManifest")] = (
        "GateResultManifest", ())
    definitions[node("GateProofArtifact")] = ("GateProofArtifact", ())

    def bind(name: str, *dependencies: str) -> None:
        definitions[node(name)] = (name, dependencies)

    bind("ClassificationRuntimeProfile", *(foundation_node(name) for name in (
        "FoundationRuntimeProfile", "KnowledgeBundle", "ClassificationPolicy",
        "EvidenceAdapterContractSet")), node("ClassifierArtifactManifest"))
    bind("EvidenceSnapshotContent", *(foundation_node(name) for name in (
        "EvidenceSourceBindingTimeline", "BindingClockPolicy", "EvidenceSchemaRegistryContract",
        "OriginRuntimeAdmission", "TTLCapturePlacementProof",
        "SourceHealthEmitterContract:NETWORK", "SourceHealthEmitterContract:PORTAL_HISTORICAL",
        "SourceHealthEmitterContract:PORTAL_PERIODIC")))
    bind("SnapshotRecord", node("EvidenceSnapshotContent"), *(foundation_node(name) for name in (
        "FoundationRuntimeProfile", "SnapshotContentPolicy", "SnapshotExecutionPolicy")))
    bind("SourceEvaluability", node("EvidenceSnapshotContent"), foundation_node("SourceHealthPolicy"))
    bind("OriginAssessment", node("EvidenceSnapshotContent"), node("SourceEvaluability"),
         foundation_node("KnowledgeBundle"), foundation_node("EvidenceAdapterContractSet"),
         *(foundation_node(f"KnowledgeProvenanceManifest:{slot}") for slot in (
             "K1", "K2B", "K3", "K4")))
    bind("ClassificationRequestManifest", node("EvidenceSnapshotContent"), node("SourceEvaluability"),
         node("ClassifierArtifactManifest"), *(foundation_node(name) for name in (
             "KnowledgeBundle", "ClassificationPolicy", "EvidenceAdapterContractSet")))
    bind("ClassificationResult", node("EvidenceSnapshotContent"), node("SourceEvaluability"),
         node("OriginAssessment"), node("ClassifierArtifactManifest"),
         foundation_node("KnowledgeBundle"), foundation_node("ClassificationPolicy"),
         *(foundation_node(f"KnowledgeProvenanceManifest:{slot}") for slot in (
             "K1", "K2B", "K3", "K4")))
    bind("ProductValidationComparisonRecord", node("ControlledValidationGroundTruthRecord"),
         node("ClassificationRequestManifest"), node("ClassificationResult"))
    bind("Task04AcceptanceManifest", foundation_node("FoundationAdmissionManifest"),
         node("ClassifierArtifactManifest"), node("ClassificationRuntimeProfile"),
         node("PrerequisiteGateResultManifest"), node("ProductValidationComparisonRecord"))
    bind("RuntimeProfileAdmissionManifest", node("ClassificationRuntimeProfile"),
         foundation_node("FoundationAdmissionManifest"), node("Task04AcceptanceManifest"),
         foundation_node("RuntimeProfileAdmissionManifest"), node("PrerequisiteGateResultManifest"))
    bind("GateResultManifest", node("PrerequisiteGateResultManifest"),
         node("ProductValidationComparisonRecord"), node("Task04AcceptanceManifest"),
         node("RuntimeProfileAdmissionManifest"))
    return _template_nodes(definitions)


_VARIANT_TYPES = {
    "KnowledgeProvenanceManifest": ("K1", "K2B", "K3", "K4"),
    "CanonicalKnowledgeRecordSet": ("K1", "K2B", "K4"),
    "SourceGovernanceRecord": ("K1", "K2B", "K4"),
    "KnowledgeFreshnessPolicy": ("K1", "K2B", "K4"),
    "SourceHealthEmitterContract": ("NETWORK", "PORTAL_HISTORICAL", "PORTAL_PERIODIC"),
}
_FOUNDATION_SINGLETON_AUTHORITY = frozenset("""
ArchitectureContractReference Task01WatermarkReadContract Task01SchemaMigrationContract
Task01GenerationRecoveryContract Task01HealthRetentionContract TcpSynV2SchemaContract
PortalHeadersV2SchemaContract CapabilityDisposition EvidenceSchemaRegistryContract
EvidenceAdapterContractSet EvidenceSourceBindingTimeline BindingClockPolicy SourceHealthPolicy
OriginRuntimeAdmission SnapshotContentPolicy SnapshotExecutionPolicy ClassificationTaxonomy
AliasMapping K3PortalRuleSet KnowledgeBundle ClassificationPolicy ClassificationRetentionPolicy
ProductValidationPolicy FoundationAdmissionManifest FoundationRuntimeProfile
RuntimeProfileAdmissionManifest RuntimeProfileActivationRecord RuntimeProfileValidityRecord
GateResultManifest GateProofArtifact K2AConformancePackage TTLCapturePlacementProof
""".split())
_TASK04_SINGLETON_AUTHORITY = frozenset("""
Task04AcceptanceManifest ClassificationRuntimeProfile ClassifierArtifactManifest
EvidenceSnapshotContent SnapshotRecord SourceEvaluability OriginAssessment
ClassificationRequestManifest ClassificationResult ControlledValidationGroundTruthRecord
ProductValidationComparisonRecord
""".split())


def _foundation_authority() -> tuple[frozenset[tuple[str, str]], frozenset[tuple[str, str]]]:
    """Independent, immutable R14 node and direct-edge inventory for F-ADMIT."""
    prefix = "template:foundation:"
    inventory = {(prefix + kind, kind) for kind in _FOUNDATION_SINGLETON_AUTHORITY}
    inventory.add((prefix + "PrerequisiteGateResultManifest", "GateResultManifest"))
    for kind, slots in _VARIANT_TYPES.items():
        inventory.update((prefix + f"{kind}:{slot}", kind) for slot in slots)
    direct: dict[str, tuple[str, ...]] = {
        "PrerequisiteGateResultManifest": ("CapabilityDisposition",),
        "OriginRuntimeAdmission": ("TTLCapturePlacementProof",),
        "EvidenceSchemaRegistryContract": (
            "TcpSynV2SchemaContract", "PortalHeadersV2SchemaContract", "CapabilityDisposition"),
        "EvidenceAdapterContractSet": ("EvidenceSchemaRegistryContract",),
        "Task01HealthRetentionContract": ("SourceHealthPolicy",),
        "ClassificationPolicy": (
            "ClassificationTaxonomy", "AliasMapping", "EvidenceAdapterContractSet"),
        "KnowledgeProvenanceManifest:K3": ("K3PortalRuleSet", "ClassificationTaxonomy"),
        "KnowledgeBundle": (
            "ClassificationTaxonomy", "AliasMapping", "K3PortalRuleSet",
            *(f"KnowledgeProvenanceManifest:{slot}" for slot in ("K1", "K2B", "K3", "K4")),
            *(f"SourceGovernanceRecord:{slot}" for slot in ("K1", "K2B", "K4")),
            *(f"KnowledgeFreshnessPolicy:{slot}" for slot in ("K1", "K2B", "K4")),
            *(f"CanonicalKnowledgeRecordSet:{slot}" for slot in ("K1", "K2B", "K4"))),
        "FoundationAdmissionManifest": (
            "ArchitectureContractReference", "PrerequisiteGateResultManifest",
            "EvidenceSchemaRegistryContract", "EvidenceAdapterContractSet", "KnowledgeBundle",
            "EvidenceSourceBindingTimeline", "BindingClockPolicy", "SourceHealthPolicy",
            *(f"SourceHealthEmitterContract:{slot}" for slot in _VARIANT_TYPES[
                "SourceHealthEmitterContract"]),
            "SnapshotContentPolicy", "SnapshotExecutionPolicy", "ClassificationPolicy",
            "ClassificationRetentionPolicy", "ProductValidationPolicy",
            *(f"KnowledgeFreshnessPolicy:{slot}" for slot in ("K1", "K2B", "K4")),
            *(f"SourceGovernanceRecord:{slot}" for slot in ("K1", "K2B", "K4")),
            *(f"KnowledgeProvenanceManifest:{slot}" for slot in ("K1", "K2B", "K3", "K4")),
            "K2AConformancePackage", "TTLCapturePlacementProof", "OriginRuntimeAdmission",
            "CapabilityDisposition"),
        "FoundationRuntimeProfile": (
            "EvidenceSourceBindingTimeline", "BindingClockPolicy", "SourceHealthPolicy",
            "SnapshotContentPolicy", "SnapshotExecutionPolicy", "EvidenceSchemaRegistryContract",
            "Task01HealthRetentionContract", "OriginRuntimeAdmission",
            *(f"SourceHealthEmitterContract:{slot}" for slot in _VARIANT_TYPES[
                "SourceHealthEmitterContract"]),
            "TTLCapturePlacementProof"),
        "RuntimeProfileAdmissionManifest": (
            "FoundationRuntimeProfile", "FoundationAdmissionManifest",
            "PrerequisiteGateResultManifest"),
        "RuntimeProfileActivationRecord": (
            "FoundationRuntimeProfile", "RuntimeProfileAdmissionManifest"),
        "RuntimeProfileValidityRecord": ("FoundationRuntimeProfile",),
        "GateResultManifest": (
            "PrerequisiteGateResultManifest", "CapabilityDisposition",
            "FoundationAdmissionManifest", "OriginRuntimeAdmission", "FoundationRuntimeProfile",
            "RuntimeProfileAdmissionManifest", "RuntimeProfileActivationRecord",
            "RuntimeProfileValidityRecord"),
    }
    for slot in ("K1", "K2B", "K4"):
        direct[f"KnowledgeProvenanceManifest:{slot}"] = (
            f"KnowledgeFreshnessPolicy:{slot}", f"SourceGovernanceRecord:{slot}")
        direct[f"CanonicalKnowledgeRecordSet:{slot}"] = (f"KnowledgeProvenanceManifest:{slot}",)
    emitters = tuple(f"SourceHealthEmitterContract:{slot}" for slot in _VARIANT_TYPES[
        "SourceHealthEmitterContract"])
    direct["EvidenceSourceBindingTimeline"] = emitters
    direct["SourceHealthPolicy"] = emitters
    edges = frozenset((prefix + owner, prefix + dependency)
                      for owner, dependencies in direct.items() for dependency in dependencies)
    return frozenset(inventory), edges


FOUNDATION_EXPECTED_NODES, FOUNDATION_EXPECTED_EDGES = _foundation_authority()


def _task04_authority() -> tuple[frozenset[tuple[str, str]], frozenset[tuple[str, str]]]:
    """Independent exact inventory for the future Task-04 build template."""
    prefix = "template:task04:"
    foundation = "template:foundation:"
    inventory = set(FOUNDATION_EXPECTED_NODES)
    inventory.update((prefix + kind, kind) for kind in _TASK04_SINGLETON_AUTHORITY)
    inventory.update((prefix + kind, kind) for kind in (
        "GateResultManifest", "GateProofArtifact", "RuntimeProfileAdmissionManifest"))
    inventory.add((prefix + "PrerequisiteGateResultManifest", "GateResultManifest"))
    direct: dict[str, tuple[str, ...]] = {
        "ClassificationRuntimeProfile": (
            *(foundation + kind for kind in (
                "FoundationRuntimeProfile", "KnowledgeBundle", "ClassificationPolicy",
                "EvidenceAdapterContractSet")), prefix + "ClassifierArtifactManifest"),
        "EvidenceSnapshotContent": (
            *(foundation + kind for kind in (
                "EvidenceSourceBindingTimeline", "BindingClockPolicy", "EvidenceSchemaRegistryContract",
                "OriginRuntimeAdmission", "TTLCapturePlacementProof",
                "SourceHealthEmitterContract:NETWORK", "SourceHealthEmitterContract:PORTAL_HISTORICAL",
                "SourceHealthEmitterContract:PORTAL_PERIODIC")),),
        "SnapshotRecord": (
            prefix + "EvidenceSnapshotContent", *(foundation + kind for kind in (
                "FoundationRuntimeProfile", "SnapshotContentPolicy", "SnapshotExecutionPolicy"))),
        "SourceEvaluability": (prefix + "EvidenceSnapshotContent", foundation + "SourceHealthPolicy"),
        "OriginAssessment": (
            prefix + "EvidenceSnapshotContent", prefix + "SourceEvaluability",
            foundation + "KnowledgeBundle", foundation + "EvidenceAdapterContractSet",
            *(foundation + f"KnowledgeProvenanceManifest:{slot}" for slot in (
                "K1", "K2B", "K3", "K4"))),
        "ClassificationRequestManifest": (
            prefix + "EvidenceSnapshotContent", prefix + "SourceEvaluability",
            prefix + "ClassifierArtifactManifest", *(foundation + kind for kind in (
                "KnowledgeBundle", "ClassificationPolicy", "EvidenceAdapterContractSet"))),
        "ClassificationResult": (
            prefix + "EvidenceSnapshotContent", prefix + "SourceEvaluability",
            prefix + "OriginAssessment", prefix + "ClassifierArtifactManifest",
            foundation + "KnowledgeBundle", foundation + "ClassificationPolicy",
            *(foundation + f"KnowledgeProvenanceManifest:{slot}" for slot in (
                "K1", "K2B", "K3", "K4"))),
        "ProductValidationComparisonRecord": (
            prefix + "ControlledValidationGroundTruthRecord",
            prefix + "ClassificationRequestManifest", prefix + "ClassificationResult"),
        "Task04AcceptanceManifest": (
            foundation + "FoundationAdmissionManifest", prefix + "ClassifierArtifactManifest",
            prefix + "ClassificationRuntimeProfile", prefix + "PrerequisiteGateResultManifest",
            prefix + "ProductValidationComparisonRecord"),
        "RuntimeProfileAdmissionManifest": (
            prefix + "ClassificationRuntimeProfile", foundation + "FoundationAdmissionManifest",
            prefix + "Task04AcceptanceManifest", foundation + "RuntimeProfileAdmissionManifest",
            prefix + "PrerequisiteGateResultManifest"),
        "GateResultManifest": (
            prefix + "PrerequisiteGateResultManifest", prefix + "ProductValidationComparisonRecord",
            prefix + "Task04AcceptanceManifest", prefix + "RuntimeProfileAdmissionManifest"),
    }
    edges = FOUNDATION_EXPECTED_EDGES | frozenset((prefix + owner, dependency)
        for owner, dependencies in direct.items() for dependency in dependencies)
    return frozenset(inventory), edges


TASK04_EXPECTED_NODES, TASK04_EXPECTED_EDGES = _task04_authority()


def matches_exact_template_authority(nodes: Iterable[ArtifactDependencyNode], scope: str) -> bool:
    expected = {
        "foundation": (FOUNDATION_EXPECTED_NODES, FOUNDATION_EXPECTED_EDGES),
        "task04": (TASK04_EXPECTED_NODES, TASK04_EXPECTED_EDGES),
    }.get(scope)
    if expected is None:
        raise ArtifactDependencyGraphError("artifact_dependency_graph_invalid")
    actual = tuple(nodes)
    inventory = frozenset((node.node_id, node.artifact_type) for node in actual)
    edges = frozenset((node.node_id, dependency) for node in actual
                      for dependency in node.direct_dependency_ids)
    return (len(actual) == len(inventory) and inventory == expected[0] and edges == expected[1])


def build_required_cycle_regression_fixtures() -> dict[str, tuple[ArtifactDependencyNode, ...]]:
    """Mutate one forbidden edge in each real positive template."""
    foundation = build_foundation_schema_template_graph()
    task04 = build_task04_schema_template_graph()
    f = lambda name: "template:foundation:" + name
    t = lambda name: "template:task04:" + name

    def inject(positive: tuple[ArtifactDependencyNode, ...], owner: str,
               dependency: str) -> tuple[ArtifactDependencyNode, ...]:
        return tuple(replace(item, direct_dependency_ids=tuple(sorted((
            *item.direct_dependency_ids, dependency)))) if item.node_id == owner else item
            for item in positive)

    left, right = "template:cycle:mutual_artifact:A", "template:cycle:mutual_artifact:B"
    return {
        "gate_output": inject(foundation, f("FoundationAdmissionManifest"), f("GateResultManifest")),
        "runtime_profile_lineage": inject(
            task04, t("ClassificationRuntimeProfile"), t("Task04AcceptanceManifest")),
        "foundation_profile_lineage": inject(
            foundation, f("FoundationRuntimeProfile"), f("FoundationAdmissionManifest")),
        "capability_gate": inject(
            foundation, f("CapabilityDisposition"), f("PrerequisiteGateResultManifest")),
        "knowledge_freshness_provenance": inject(
            foundation, f("KnowledgeFreshnessPolicy:K1"), f("KnowledgeProvenanceManifest:K1")),
        "mutual_artifact": (
            ArtifactDependencyNode(left, "SyntheticArtifactA", "TEMPLATE", (right,)),
            ArtifactDependencyNode(right, "SyntheticArtifactB", "TEMPLATE", (left,))),
    }
