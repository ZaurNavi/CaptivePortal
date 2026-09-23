"""Closed R14 KnowledgeBundle V1 and exact canonical dependency validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .artifact_content import ArtifactContent, ArtifactRef, canonical_set, make_artifact_content
from .k2a_conformance_artifacts import make_source_governance_record
from .k3_portal_rules import make_k3_portal_rule_set
from .knowledge_artifacts import (
    make_canonical_k1_record_set, make_canonical_k2b_record_set,
    make_canonical_k4_record_set, make_external_knowledge_provenance_manifest,
    make_internal_knowledge_provenance_manifest, make_knowledge_freshness_policy,
)
from .models import DeviceFingerprintValidationError
from .taxonomy_artifacts import (
    make_alias_mapping, make_classification_taxonomy,
    validate_alias_mapping_against_taxonomy,
)

_FIELDS = frozenset({
    "bundle_schema_version", "classification_taxonomy", "alias_mapping",
    "knowledge_provenance_manifests", "source_governance_records",
    "knowledge_freshness_policies", "k1_record_set", "k2b_record_set",
    "k3_portal_rule_set", "k4_record_set",
})


def _fail(message: str) -> None:
    raise DeviceFingerprintValidationError(message)


def _ref(content: ArtifactContent, kind: str) -> dict[str, str]:
    if not isinstance(content, ArtifactContent) or content.artifact_type != kind:
        _fail(f"Expected {kind} dependency")
    return ArtifactRef(content.artifact_id, content.content_sha256).as_dict()


def _typed_ref(value: Any, kind: str) -> dict[str, str]:
    ref = ArtifactRef.from_dict(value)
    if not ref.artifact_id.startswith(f"{kind}:v1:sha256:"):
        _fail(f"Invalid {kind} reference")
    return ref.as_dict()


def _ref_set(value: Any, kind: str) -> list[dict[str, str]]:
    if not isinstance(value, list):
        _fail(f"Invalid {kind} reference SET")
    refs = [_typed_ref(row, kind) for row in value]
    if len({ref["artifact_id"] for ref in refs}) != len(refs):
        _fail(f"Duplicate {kind} reference")
    return canonical_set(refs, lambda ref: ref["artifact_id"])


def make_knowledge_bundle(payload: dict[str, Any]) -> ArtifactContent:
    """Validate the exact closed KnowledgeBundle payload and canonical SETs."""
    if not isinstance(payload, dict) or set(payload) != _FIELDS:
        _fail("Invalid KnowledgeBundle shape")
    version = payload["bundle_schema_version"]
    if type(version) is not int or not 1 <= version <= 2147483647:
        _fail("Invalid KnowledgeBundle schema version")
    return make_artifact_content("KnowledgeBundle", {
        "bundle_schema_version": version,
        "classification_taxonomy": _typed_ref(payload["classification_taxonomy"], "ClassificationTaxonomy"),
        "alias_mapping": _typed_ref(payload["alias_mapping"], "AliasMapping"),
        "knowledge_provenance_manifests": _ref_set(
            payload["knowledge_provenance_manifests"], "KnowledgeProvenanceManifest",
        ),
        "source_governance_records": _ref_set(
            payload["source_governance_records"], "SourceGovernanceRecord",
        ),
        "knowledge_freshness_policies": _ref_set(
            payload["knowledge_freshness_policies"], "KnowledgeFreshnessPolicy",
        ),
        "k1_record_set": _typed_ref(payload["k1_record_set"], "CanonicalKnowledgeRecordSet"),
        "k2b_record_set": _typed_ref(payload["k2b_record_set"], "CanonicalKnowledgeRecordSet"),
        "k3_portal_rule_set": _typed_ref(payload["k3_portal_rule_set"], "K3PortalRuleSet"),
        "k4_record_set": _typed_ref(payload["k4_record_set"], "CanonicalKnowledgeRecordSet"),
    })


@dataclass(frozen=True, slots=True)
class KnowledgeBundleCandidate:
    classification_taxonomy: ArtifactContent
    alias_mapping: ArtifactContent
    k1_record_set: ArtifactContent
    k1_provenance: ArtifactContent
    k1_governance: ArtifactContent
    k1_freshness_policy: ArtifactContent
    k2b_record_set: ArtifactContent
    k2b_provenance: ArtifactContent
    k2b_governance: ArtifactContent
    k2b_freshness_policy: ArtifactContent
    k3_portal_rule_set: ArtifactContent
    k3_provenance: ArtifactContent
    k4_record_set: ArtifactContent
    k4_provenance: ArtifactContent
    k4_governance: ArtifactContent
    k4_freshness_policy: ArtifactContent


def _distinct_refs(refs: list[dict[str, str]]) -> list[dict[str, str]]:
    return list({ref["artifact_id"]: ref for ref in refs}.values())


def build_initial_knowledge_bundle_v1(candidate: KnowledgeBundleCandidate) -> ArtifactContent:
    """Build only the admitted four-slot, reference-only initial bundle."""
    if not isinstance(candidate, KnowledgeBundleCandidate):
        _fail("Invalid KnowledgeBundle candidate")
    external = ("k1", "k2b", "k4")
    provenance = [_ref(getattr(candidate, f"{slot}_provenance"), "KnowledgeProvenanceManifest")
                  for slot in ("k1", "k2b", "k3", "k4")]
    governance = _distinct_refs([
        _ref(getattr(candidate, f"{slot}_governance"), "SourceGovernanceRecord")
        for slot in external
    ])
    freshness = _distinct_refs([
        _ref(getattr(candidate, f"{slot}_freshness_policy"), "KnowledgeFreshnessPolicy")
        for slot in external
    ])
    return make_knowledge_bundle({
        "bundle_schema_version": 1,
        "classification_taxonomy": _ref(candidate.classification_taxonomy, "ClassificationTaxonomy"),
        "alias_mapping": _ref(candidate.alias_mapping, "AliasMapping"),
        "knowledge_provenance_manifests": provenance,
        "source_governance_records": governance,
        "knowledge_freshness_policies": freshness,
        "k1_record_set": _ref(candidate.k1_record_set, "CanonicalKnowledgeRecordSet"),
        "k2b_record_set": _ref(candidate.k2b_record_set, "CanonicalKnowledgeRecordSet"),
        "k3_portal_rule_set": _ref(candidate.k3_portal_rule_set, "K3PortalRuleSet"),
        "k4_record_set": _ref(candidate.k4_record_set, "CanonicalKnowledgeRecordSet"),
    })


def _validated(
    content: ArtifactContent, kind: str,
    validator: Callable[[dict[str, Any]], ArtifactContent],
) -> dict[str, Any]:
    _ref(content, kind)
    validated = validator(content.semantic_payload)
    if validated.artifact_id != content.artifact_id:
        _fail(f"Noncanonical {kind} dependency")
    return validated.semantic_payload


def _exact_set(actual: list[dict[str, str]], expected: list[dict[str, str]], label: str) -> None:
    if actual != canonical_set(_distinct_refs(expected), lambda ref: ref["artifact_id"]):
        _fail(f"Incorrect {label} inventory")


def validate_knowledge_bundle_dependencies(
    bundle: ArtifactContent, candidate: KnowledgeBundleCandidate,
) -> bool:
    """Resolve every direct/transitive ref against actual supplied artifacts."""
    if not isinstance(candidate, KnowledgeBundleCandidate):
        _fail("Invalid KnowledgeBundle candidate")
    payload = _validated(bundle, "KnowledgeBundle", make_knowledge_bundle)
    if payload["bundle_schema_version"] != 1:
        _fail("Unexpected initial KnowledgeBundle schema version")
    _validated(candidate.classification_taxonomy, "ClassificationTaxonomy", make_classification_taxonomy)
    _validated(candidate.alias_mapping, "AliasMapping", make_alias_mapping)
    validate_alias_mapping_against_taxonomy(candidate.classification_taxonomy, candidate.alias_mapping)
    if payload["classification_taxonomy"] != _ref(candidate.classification_taxonomy, "ClassificationTaxonomy"):
        _fail("Taxonomy reference mismatch")
    if payload["alias_mapping"] != _ref(candidate.alias_mapping, "AliasMapping"):
        _fail("AliasMapping reference mismatch")

    record_validators = {
        "k1": ("K1", make_canonical_k1_record_set),
        "k2b": ("K2B", make_canonical_k2b_record_set),
        "k4": ("K4", make_canonical_k4_record_set),
    }
    for slot, (expected_slot, validator) in record_validators.items():
        record_set = getattr(candidate, f"{slot}_record_set")
        records = _validated(record_set, "CanonicalKnowledgeRecordSet", validator)
        if records["knowledge_slot"] != expected_slot or not records["records"]:
            _fail(f"Missing concrete {slot} records")
        if payload[f"{slot}_record_set"] != _ref(record_set, "CanonicalKnowledgeRecordSet"):
            _fail(f"Incorrect {slot} record-set reference")
        if records["knowledge_provenance"] != _ref(
            getattr(candidate, f"{slot}_provenance"), "KnowledgeProvenanceManifest",
        ):
            _fail(f"Incorrect {slot} record-set provenance")

    rules = _validated(candidate.k3_portal_rule_set, "K3PortalRuleSet", make_k3_portal_rule_set)
    if not rules["rules"] or not rules["test_vectors"]:
        _fail("Missing concrete K3 rules or vectors")
    if payload["k3_portal_rule_set"] != _ref(candidate.k3_portal_rule_set, "K3PortalRuleSet"):
        _fail("Incorrect K3 rule-set reference")
    internal = _validated(candidate.k3_provenance, "KnowledgeProvenanceManifest",
                          make_internal_knowledge_provenance_manifest)
    if (internal["provenance_kind"] != "internal"
            or internal["rule_set_artifact"] != _ref(candidate.k3_portal_rule_set, "K3PortalRuleSet")
            or internal["taxonomy_compatibility"] != _ref(candidate.classification_taxonomy, "ClassificationTaxonomy")):
        _fail("Incorrect K3 internal provenance")

    expected_provenance = [_ref(candidate.k3_provenance, "KnowledgeProvenanceManifest")]
    expected_governance = []
    expected_freshness = []
    for slot in ("k1", "k2b", "k4"):
        provenance = getattr(candidate, f"{slot}_provenance")
        governance = getattr(candidate, f"{slot}_governance")
        freshness = getattr(candidate, f"{slot}_freshness_policy")
        external = _validated(provenance, "KnowledgeProvenanceManifest",
                              make_external_knowledge_provenance_manifest)
        _validated(governance, "SourceGovernanceRecord", make_source_governance_record)
        policy = _validated(freshness, "KnowledgeFreshnessPolicy", make_knowledge_freshness_policy)
        if policy["source_family_id"] != {
            "k1": "satori_dhcp", "k2b": "p0f3_legacy_tcp", "k4": "ieee_ra_mac",
        }[slot]:
            _fail(f"Incorrect {slot} source family")
        if (external["provenance_kind"] != "external"
                or external["source_governance_record"] != _ref(governance, "SourceGovernanceRecord")
                or external["knowledge_freshness_policy"] != _ref(freshness, "KnowledgeFreshnessPolicy")):
            _fail(f"Incorrect {slot} external provenance dependencies")
        expected_provenance.append(_ref(provenance, "KnowledgeProvenanceManifest"))
        expected_governance.append(external["source_governance_record"])
        expected_freshness.append(external["knowledge_freshness_policy"])
    if len({row["artifact_id"] for row in expected_provenance}) != 4:
        _fail("Mandatory provenance identities are not distinct")
    if len({row["artifact_id"] for row in expected_governance}) != 3:
        _fail("Mandatory governance identities are not distinct")
    if len({row["artifact_id"] for row in expected_freshness}) != 3:
        _fail("Mandatory freshness identities are not distinct")
    _exact_set(payload["knowledge_provenance_manifests"], expected_provenance, "provenance")
    _exact_set(payload["source_governance_records"], expected_governance, "governance")
    _exact_set(payload["knowledge_freshness_policies"], expected_freshness, "freshness")
    return True
