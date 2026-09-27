"""Pure R14 T-03 origin assessment over already materialized T-01 evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
import uuid

from .artifact_content import (
    ArtifactContent, ArtifactRef, canonical_artifact_json, canonical_set,
    make_artifact_content,
)
from .evidence_adapter_contracts import (
    DIMENSIONS, make_evidence_adapter_contract_set, task01_contract_claim_eligible,
)
from .fe5_external_knowledge import evaluate_external_knowledge_freshness
from .k4_ieee_import import match_k4_records
from .knowledge_artifacts import match_k1_records
from .knowledge_bundle import KnowledgeBundleCandidate, validate_knowledge_bundle_dependencies
from .models import DeviceFingerprintValidationError
from .p0f_semantics import adapt_tcp_syn_v2, match_request, parse_request_signature
from .snapshot_service import EvidenceSnapshotMaterialization
from .validation import parse_utc, validate_uuid

ORIGINS = ("dhcp", "portal", "tcp", "tls", "quic", "mac_registry")
_SOURCE_ORIGIN = {
    "dhcp": "dhcp", "portal_headers": "portal", "tcp_syn": "tcp",
    "tls_client": "tls", "quic_client": "quic",
}
_STATES = frozenset({
    "resolved", "recognized_out_of_scope", "ambiguous", "conflicting",
    "no_claim", "not_evaluable",
})
_STRENGTHS = frozenset({"strong", "supporting"})
_DERIVATIONS = frozenset({
    "declared", "deterministic_mapping", "fingerprint_match", "registry_mapping",
})
_TOP = frozenset({
    "origin_assessment_contract_version", "evidence_snapshot_content",
    "source_evaluability", "origin_group", "dimension_assessments",
    "evidence_refs", "knowledge_refs", "explanation_codes",
})
_DIMENSION = frozenset({
    "dimension_name", "internal_state", "selected_canonical_value_id",
    "selected_out_of_scope_taxon_ref", "effective_claim_strength",
    "claim_derivations", "candidate_set", "conflict_strength",
    "same_origin_contradiction_records", "broad_unresolved_taxon_refs",
    "knowledge_refs", "evidence_refs", "explanation_codes",
})
_CANDIDATE = frozenset({
    "candidate_kind", "candidate_value_id", "out_of_scope_taxon_ref",
    "claim_strength", "claim_derivation", "knowledge_refs", "evidence_refs",
})
_EVIDENCE_REF = frozenset({
    "evidence_id", "payload_sha256", "feature_schema_version",
    "adapter_contract_id", "adapter_contract_digest",
})
_KNOWLEDGE_REF = frozenset({
    "knowledge_bundle_id", "knowledge_bundle_digest",
    "canonical_knowledge_record_id", "knowledge_provenance_id",
    "knowledge_provenance_digest", "rule_or_source_record_identity",
})
_CONTRADICTION = frozenset({
    "dimension_name", "conflict_strength", "retained_candidate_key",
    "incompatible_candidate_keys", "evidence_refs", "knowledge_refs",
    "explanation_code",
})
_BROAD = frozenset({
    "reference_kind", "canonical_taxon_or_source_ref", "evidence_refs",
    "knowledge_refs", "explanation_code",
})


def _fail(message: str) -> None:
    raise DeviceFingerprintValidationError(message)


def _shape(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        _fail(f"Invalid {label} shape")
    return value


def _text(value: Any, label: str, *, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        _fail(f"Invalid {label}")
    return value


def _strings(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        _fail(f"Invalid {label} SET")
    return canonical_set([_text(row, label) for row in value], lambda row: row)


def _reference(value: Any, kind: str, *, content: ArtifactContent | None = None) -> dict[str, str]:
    reference = ArtifactRef.from_dict(value)
    if not reference.artifact_id.startswith(f"{kind}:v1:sha256:"):
        _fail(f"Invalid {kind} reference")
    if content is not None:
        reference.resolve(content, kind)
    return reference.as_dict()


def _ref(content: ArtifactContent) -> dict[str, str]:
    return ArtifactRef(content.artifact_id, content.content_sha256).as_dict()


def _unique(rows: list[Any]) -> list[Any]:
    """Collapse identical runtime contributions before constructing strict SETs."""
    return list({canonical_artifact_json(row): row for row in rows}.values())


def _evidence_ref(raw: Any) -> dict[str, Any]:
    row = dict(_shape(raw, _EVIDENCE_REF, "EvidenceRef"))
    validate_uuid(row["evidence_id"])
    if uuid.UUID(row["evidence_id"]).version != 4:
        _fail("EvidenceRef requires UUIDv4")
    if not isinstance(row["payload_sha256"], str) or len(row["payload_sha256"]) != 64 or any(
            letter not in "0123456789abcdef" for letter in row["payload_sha256"]):
        _fail("Invalid EvidenceRef payload digest")
    _reference({"artifact_id": row["adapter_contract_id"],
                "content_sha256": row["adapter_contract_digest"]}, "EvidenceAdapterContractSet")
    if (type(row["feature_schema_version"]) is not int or
            not 1 <= row["feature_schema_version"] <= 2147483647):
        _fail("Invalid EvidenceRef schema version")
    return row


def _knowledge_ref(raw: Any) -> dict[str, str]:
    row = dict(_shape(raw, _KNOWLEDGE_REF, "KnowledgeRef"))
    _reference({"artifact_id": row["knowledge_bundle_id"],
                "content_sha256": row["knowledge_bundle_digest"]}, "KnowledgeBundle")
    _reference({"artifact_id": row["knowledge_provenance_id"],
                "content_sha256": row["knowledge_provenance_digest"]}, "KnowledgeProvenanceManifest")
    for field in ("canonical_knowledge_record_id", "rule_or_source_record_identity"):
        _text(row[field], field)
    return row


def _evidence_set(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        _fail("Invalid EvidenceRef SET")
    return canonical_set([_evidence_ref(row) for row in raw], lambda row: row["evidence_id"])


def _knowledge_set(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        _fail("Invalid KnowledgeRef SET")
    return canonical_set([_knowledge_ref(row) for row in raw], lambda row: (
        row["knowledge_provenance_id"], row["canonical_knowledge_record_id"],
        row["rule_or_source_record_identity"],
    ))


def _candidate(raw: Any) -> dict[str, Any]:
    row = dict(_shape(raw, _CANDIDATE, "CandidateEntry"))
    kind = row["candidate_kind"]
    if kind not in {"CANONICAL_VALUE", "OUT_OF_SCOPE_TAXON"}:
        _fail("Invalid candidate kind")
    value = _text(row["candidate_value_id"], "candidate value", nullable=True)
    outside = _text(row["out_of_scope_taxon_ref"], "out-of-scope taxon", nullable=True)
    if (kind == "CANONICAL_VALUE") != (value is not None) or (kind == "OUT_OF_SCOPE_TAXON") != (outside is not None):
        _fail("Invalid candidate target")
    if row["claim_strength"] not in _STRENGTHS or row["claim_derivation"] not in _DERIVATIONS:
        _fail("Invalid candidate authority")
    row["knowledge_refs"] = _knowledge_set(row["knowledge_refs"])
    row["evidence_refs"] = _evidence_set(row["evidence_refs"])
    return row


def _candidate_set(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        _fail("Invalid candidate SET")
    return canonical_set([_candidate(row) for row in raw], lambda row: (
        row["candidate_kind"], row["candidate_value_id"] or "",
        row["out_of_scope_taxon_ref"] or "", row["claim_strength"],
        row["claim_derivation"],
    ))


def _contradiction(raw: Any, dimension: str) -> dict[str, Any]:
    row = dict(_shape(raw, _CONTRADICTION, "SameOriginContradictionRecord"))
    if row["dimension_name"] != dimension or row["conflict_strength"] not in _STRENGTHS:
        _fail("Invalid contradiction dimension/strength")
    _text(row["retained_candidate_key"], "retained candidate", nullable=True)
    row["incompatible_candidate_keys"] = _strings(row["incompatible_candidate_keys"], "candidate key")
    if not row["incompatible_candidate_keys"]:
        _fail("Empty incompatible candidate keys")
    row["evidence_refs"] = _evidence_set(row["evidence_refs"])
    row["knowledge_refs"] = _knowledge_set(row["knowledge_refs"])
    _text(row["explanation_code"], "contradiction explanation")
    return row


def _broad(raw: Any) -> dict[str, Any]:
    row = dict(_shape(raw, _BROAD, "BroadUnresolvedRef"))
    if row["reference_kind"] not in {"BROAD_TAXON", "UNMAPPED_TAXON"}:
        _fail("Invalid broad/unmapped reference kind")
    _text(row["canonical_taxon_or_source_ref"], "broad/unmapped taxon")
    row["evidence_refs"] = _evidence_set(row["evidence_refs"])
    row["knowledge_refs"] = _knowledge_set(row["knowledge_refs"])
    _text(row["explanation_code"], "broad/unmapped explanation")
    return row


def _dimension(raw: Any, origin: str) -> dict[str, Any]:
    row = dict(_shape(raw, _DIMENSION, "OriginDimensionAssessment"))
    dimension = row["dimension_name"]
    if dimension not in DIMENSIONS or row["internal_state"] not in _STATES:
        _fail("Invalid origin dimension/state")
    selected = _text(row["selected_canonical_value_id"], "selected value", nullable=True)
    outside = _text(row["selected_out_of_scope_taxon_ref"], "selected outside taxon", nullable=True)
    strength = row["effective_claim_strength"]
    conflict = row["conflict_strength"]
    if strength is not None and strength not in _STRENGTHS:
        _fail("Invalid effective claim strength")
    if conflict is not None and conflict not in _STRENGTHS:
        _fail("Invalid conflict strength")
    if row["internal_state"] == "resolved":
        if selected is None or outside is not None or strength is None:
            _fail("Invalid resolved dimension")
    elif row["internal_state"] == "recognized_out_of_scope":
        if outside is None or selected is not None or strength is None or dimension not in {"platform_family", "device_class"}:
            _fail("Invalid out-of-scope dimension")
    elif selected is not None or outside is not None or strength is not None:
        _fail("Unselected dimension has a selected claim")
    row["claim_derivations"] = _strings(row["claim_derivations"], "claim derivation")
    if any(value not in _DERIVATIONS for value in row["claim_derivations"]):
        _fail("Invalid claim derivation")
    row["candidate_set"] = _candidate_set(row["candidate_set"])
    contradictions = row["same_origin_contradiction_records"]
    if not isinstance(contradictions, list):
        _fail("Invalid contradiction SET")
    row["same_origin_contradiction_records"] = canonical_set(
        [_contradiction(value, dimension) for value in contradictions],
        lambda value: (value["dimension_name"], value["conflict_strength"],
                       value["retained_candidate_key"] or ""),
    )
    broad = row["broad_unresolved_taxon_refs"]
    if not isinstance(broad, list):
        _fail("Invalid broad/unresolved SET")
    row["broad_unresolved_taxon_refs"] = canonical_set(
        [_broad(value) for value in broad],
        lambda value: (value["reference_kind"], value["canonical_taxon_or_source_ref"]),
    )
    row["knowledge_refs"] = _knowledge_set(row["knowledge_refs"])
    row["evidence_refs"] = _evidence_set(row["evidence_refs"])
    row["explanation_codes"] = _strings(row["explanation_codes"], "explanation code")
    derivations = sorted({candidate["claim_derivation"] for candidate in row["candidate_set"]})
    if row["claim_derivations"] != derivations:
        _fail("Claim derivations do not match candidate set")
    if row["internal_state"] in {"no_claim", "not_evaluable"}:
        if row["candidate_set"] or conflict is not None or row["same_origin_contradiction_records"]:
            _fail("Unclaimed dimension contains semantic claims")
    else:
        expected = _reduce_claims(dimension, row["candidate_set"], k1_ambiguous=origin == "dhcp")
        for field in ("internal_state", "selected_canonical_value_id",
                      "selected_out_of_scope_taxon_ref", "effective_claim_strength",
                      "conflict_strength", "same_origin_contradiction_records"):
            if row[field] != expected[field]:
                _fail(f"Incoherent OriginDimensionAssessment {field}")
    return row


def _make_origin_assessment(
    payload: dict[str, Any], *, evidence_snapshot_content: ArtifactContent,
    source_evaluability: ArtifactContent,
    evidence_adapter_contract_set: ArtifactContent, knowledge_bundle: ArtifactContent,
    knowledge: KnowledgeBundleCandidate,
) -> ArtifactContent:
    """Validate C.3.30/§101 exact closed schemas and canonical total order."""
    row = dict(_shape(payload, _TOP, "OriginAssessment"))
    if type(row["origin_assessment_contract_version"]) is not int or row["origin_assessment_contract_version"] != 1:
        _fail("Unsupported OriginAssessment version")
    row["evidence_snapshot_content"] = _reference(
        row["evidence_snapshot_content"], "EvidenceSnapshotContent", content=evidence_snapshot_content)
    row["source_evaluability"] = _reference(
        row["source_evaluability"], "SourceEvaluability", content=source_evaluability)
    if source_evaluability.semantic_payload["evidence_snapshot_content"] != row["evidence_snapshot_content"]:
        _fail("SourceEvaluability/snapshot identity mismatch")
    if row["origin_group"] not in ORIGINS:
        _fail("Invalid origin group")
    dimensions = row["dimension_assessments"]
    if not isinstance(dimensions, list):
        _fail("Invalid dimension SET")
    row["dimension_assessments"] = canonical_set([_dimension(value, row["origin_group"]) for value in dimensions],
                                                 lambda value: value["dimension_name"])
    if len(row["dimension_assessments"]) != len(DIMENSIONS) or {
            value["dimension_name"] for value in row["dimension_assessments"]} != set(DIMENSIONS):
        _fail("OriginAssessment requires exactly four dimensions")
    row["evidence_refs"] = _evidence_set(row["evidence_refs"])
    row["knowledge_refs"] = _knowledge_set(row["knowledge_refs"])
    row["explanation_codes"] = _strings(row["explanation_codes"], "explanation code")
    _validate_reference_lineage(row, evidence_snapshot_content=evidence_snapshot_content,
                                evidence_adapter_contract_set=evidence_adapter_contract_set,
                                knowledge_bundle=knowledge_bundle, knowledge=knowledge)
    return make_artifact_content("OriginAssessment", row)


def make_origin_assessment(
    payload: dict[str, Any], *, evidence_snapshot_content: ArtifactContent,
    source_evaluability: ArtifactContent,
    evidence_adapter_contract_set: ArtifactContent, knowledge_bundle: ArtifactContent,
    knowledge: KnowledgeBundleCandidate,
) -> ArtifactContent:
    """Construct a closed R14 assessment with typed malformed-input failures."""
    try:
        return _make_origin_assessment(
            payload, evidence_snapshot_content=evidence_snapshot_content,
            source_evaluability=source_evaluability,
            evidence_adapter_contract_set=evidence_adapter_contract_set,
            knowledge_bundle=knowledge_bundle, knowledge=knowledge)
    except (AttributeError, KeyError, TypeError, ValueError, IndexError) as exc:
        raise DeviceFingerprintValidationError("Malformed OriginAssessment") from exc


def _validate_reference_lineage(
    assessment: dict[str, Any], *, evidence_snapshot_content: ArtifactContent,
    evidence_adapter_contract_set: ArtifactContent, knowledge_bundle: ArtifactContent,
    knowledge: KnowledgeBundleCandidate,
) -> None:
    if (make_evidence_adapter_contract_set(evidence_adapter_contract_set.semantic_payload)
            != evidence_adapter_contract_set):
        _fail("Noncanonical adapter contract set")
    if not validate_knowledge_bundle_dependencies(knowledge_bundle, knowledge):
        _fail("Unresolved KnowledgeBundle")
    descriptor_by_id = {row["evidence_id"]: row for row in
                        evidence_snapshot_content.semantic_payload["evidence_descriptors"]}
    allowed_slot = {"dhcp": "k1", "portal": "k3", "tcp": "k2b",
                    "mac_registry": "k4", "tls": None, "quic": None}[assessment["origin_group"]]
    record_by_key: dict[tuple[str, str, str], str] = {}
    for slot in ("k1", "k2b", "k4"):
        provenance = getattr(knowledge, f"{slot}_provenance")
        for record in getattr(knowledge, f"{slot}_record_set").semantic_payload["records"]:
            record_by_key[(provenance.artifact_id, record["canonical_record_id"],
                           record["source_record_identity"])] = slot
    for rule in knowledge.k3_portal_rule_set.semantic_payload["rules"]:
        record_by_key[(knowledge.k3_provenance.artifact_id, rule["rule_id"], rule["rule_id"])] = "k3"

    def check_evidence(reference: dict[str, Any]) -> None:
        descriptor = descriptor_by_id.get(reference["evidence_id"])
        if (descriptor is None or reference["payload_sha256"] != descriptor["payload_sha256"]
                or reference["feature_schema_version"] != descriptor["feature_schema_version"]
                or reference["adapter_contract_id"] != evidence_adapter_contract_set.artifact_id
                or reference["adapter_contract_digest"] != evidence_adapter_contract_set.content_sha256
                or _SOURCE_ORIGIN[descriptor["source_kind"]] != assessment["origin_group"]):
            _fail("EvidenceRef does not resolve to exact origin/adapter lineage")

    def check_knowledge(reference: dict[str, str]) -> None:
        if allowed_slot is None:
            _fail("No admitted semantic knowledge for this origin")
        key = (reference["knowledge_provenance_id"], reference["canonical_knowledge_record_id"],
               reference["rule_or_source_record_identity"])
        if (reference["knowledge_bundle_id"] != knowledge_bundle.artifact_id
                or reference["knowledge_bundle_digest"] != knowledge_bundle.content_sha256
                or record_by_key.get(key) != allowed_slot):
            _fail("KnowledgeRef does not resolve to exact origin/bundle lineage")
        provenance = getattr(knowledge, f"{allowed_slot}_provenance")
        if reference["knowledge_provenance_digest"] != provenance.content_sha256:
            _fail("KnowledgeRef provenance digest mismatch")

    def check_refs(value: dict[str, Any]) -> None:
        for reference in value["evidence_refs"]:
            check_evidence(reference)
        for reference in value["knowledge_refs"]:
            check_knowledge(reference)

    check_refs(assessment)
    for dimension in assessment["dimension_assessments"]:
        check_refs(dimension)
        for candidate in dimension["candidate_set"]:
            check_refs(candidate)
        for contradiction in dimension["same_origin_contradiction_records"]:
            check_refs(contradiction)
        for broad in dimension["broad_unresolved_taxon_refs"]:
            check_refs(broad)


def _cap(*strengths: str) -> str:
    return "supporting" if "supporting" in strengths else "strong"


def _candidate_key(row: dict[str, Any]) -> str:
    return canonical_artifact_json([
        row["candidate_kind"], row["candidate_value_id"], row["out_of_scope_taxon_ref"],
    ]).decode("utf-8")


def _task_adapter_compatible(adapter: dict[str, Any], descriptor: dict[str, Any]) -> bool:
    """Check the row-wide F-F1 contract before invoking any semantic matcher."""
    if (adapter["adapter_kind"] != "TASK01_EVIDENCE"
            or adapter["source_kind"] != descriptor["source_kind"]
            or adapter["feature_schema_version"] != descriptor["feature_schema_version"]
            or descriptor["source_subtype"] not in adapter["supported_source_subtypes"]
            or descriptor["quality_state"] not in {"valid", "partial", "degraded"}):
        return False
    for field, constraint in (("extractor_name", "extractor_name_constraints"),
                              ("extractor_version", "extractor_version_constraints"),
                              ("rule_version", "rule_version_constraints")):
        allowed = adapter[constraint]
        if allowed:
            if descriptor[field] not in allowed:
                return False
        elif field == "rule_version" and descriptor[field] is not None:
            return False
    return True


def _merge_contributions(
    rows: list[tuple[str, str, dict[str, Any]]], *, broad: bool = False,
) -> list[dict[str, Any]]:
    """Merge exact post-evaluation semantic atoms; keep canonical provenance unions."""
    merged: dict[tuple[str, ...], dict[str, Any]] = {}
    for projection, dimension, row in rows:
        if broad:
            key = (projection, dimension, row["reference_kind"],
                   row["canonical_taxon_or_source_ref"], row["explanation_code"])
        else:
            key = (projection, dimension, row["candidate_kind"],
                   row["candidate_value_id"] or "", row["out_of_scope_taxon_ref"] or "",
                   row["claim_strength"], row["claim_derivation"])
        if key not in merged:
            merged[key] = {**row, "evidence_refs": [], "knowledge_refs": []}
        target = merged[key]
        target["evidence_refs"].extend(row["evidence_refs"])
        target["knowledge_refs"].extend(row["knowledge_refs"])
    for row in merged.values():
        row["evidence_refs"] = _evidence_set(_unique(row["evidence_refs"]))
        row["knowledge_refs"] = _knowledge_set(_unique(row["knowledge_refs"]))
    return list(merged.values())


def _reduce_claims(
    dimension: str, candidates: list[dict[str, Any]], *,
    broad: list[dict[str, Any]] = (), explanations: list[str] = (),
    k1_ambiguous: bool = False, not_evaluable: bool = False,
    evaluated_evidence_refs: Sequence[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Apply §102-104 without row counts, arrival order, or derivation priority."""
    candidates = _candidate_set(_unique(candidates))
    broad = canonical_set(list(broad), lambda row: (
        row["reference_kind"], row["canonical_taxon_or_source_ref"]))
    strong = [row for row in candidates if row["claim_strength"] == "strong"]
    supporting = [row for row in candidates if row["claim_strength"] == "supporting"]
    selected: dict[str, Any] | None = None
    contradictions: list[dict[str, Any]] = []
    state = "not_evaluable" if not_evaluable else "no_claim"
    conflict_strength = None
    groups = strong if strong else supporting
    distinct = {_candidate_key(row) for row in groups}
    if groups and k1_ambiguous and len(distinct) > 1:
        per_observation: dict[str, set[str]] = {}
        for candidate in groups:
            for evidence_ref in candidate["evidence_refs"]:
                per_observation.setdefault(evidence_ref["evidence_id"], set()).add(
                    _candidate_key(candidate))
        if per_observation and set.intersection(*per_observation.values()):
            state = "ambiguous"
        else:
            state = "conflicting"
            conflict_strength = "strong" if strong else "supporting"
            contradictions.append({
                "dimension_name": dimension, "conflict_strength": conflict_strength,
                "retained_candidate_key": None,
                "incompatible_candidate_keys": sorted(distinct),
                "evidence_refs": _evidence_set(_unique([
                    ref for row in groups for ref in row["evidence_refs"]])),
                "knowledge_refs": _knowledge_set(_unique([
                    ref for row in groups for ref in row["knowledge_refs"]])),
                "explanation_code": "same_origin_incompatible_claims",
            })
    elif len(distinct) > 1:
        state = "conflicting"
        conflict_strength = "strong" if strong else "supporting"
        contradictions.append({
            "dimension_name": dimension, "conflict_strength": conflict_strength,
            "retained_candidate_key": None,
            "incompatible_candidate_keys": sorted(distinct),
            "evidence_refs": _evidence_set(_unique([ref for row in groups for ref in row["evidence_refs"]])),
            "knowledge_refs": _knowledge_set(_unique([ref for row in groups for ref in row["knowledge_refs"]])),
            "explanation_code": "same_origin_incompatible_claims",
        })
    elif groups:
        selected = groups[0]
        state = "resolved" if selected["candidate_kind"] == "CANONICAL_VALUE" else "recognized_out_of_scope"
        if strong:
            incompatible = [row for row in supporting if _candidate_key(row) != _candidate_key(selected)]
            if incompatible:
                conflict_strength = "supporting"
                contradictions.append({
                    "dimension_name": dimension, "conflict_strength": "supporting",
                    "retained_candidate_key": _candidate_key(selected),
                    "incompatible_candidate_keys": sorted({_candidate_key(row) for row in incompatible}),
                    "evidence_refs": _evidence_set(_unique([
                        ref for row in [selected, *incompatible] for ref in row["evidence_refs"]])),
                    "knowledge_refs": _knowledge_set(_unique([
                        ref for row in [selected, *incompatible] for ref in row["knowledge_refs"]])),
                    "explanation_code": "same_origin_supporting_contradiction",
                })
    reasons = list(explanations)
    if state in {"ambiguous", "conflicting"}:
        reasons.append(f"same_origin_{state}")
    if contradictions:
        reasons.extend(row["explanation_code"] for row in contradictions)
    return {
        "dimension_name": dimension, "internal_state": state,
        "selected_canonical_value_id": selected["candidate_value_id"] if selected else None,
        "selected_out_of_scope_taxon_ref": selected["out_of_scope_taxon_ref"] if selected else None,
        "effective_claim_strength": selected["claim_strength"] if selected else None,
        "claim_derivations": _strings(list({row["claim_derivation"] for row in candidates}), "derivation")
        if candidates else [],
        "candidate_set": candidates, "conflict_strength": conflict_strength,
        "same_origin_contradiction_records": contradictions,
        "broad_unresolved_taxon_refs": broad,
        "knowledge_refs": _knowledge_set(_unique([ref for row in candidates for ref in row["knowledge_refs"]])),
        "evidence_refs": _evidence_set(_unique([
            *evaluated_evidence_refs,
            *(ref for row in candidates for ref in row["evidence_refs"]),
            *(ref for row in broad for ref in row["evidence_refs"]),
            *(ref for row in contradictions for ref in row["evidence_refs"]),
        ])),
        "explanation_codes": _strings(list(set(reasons)), "explanation"),
    }


@dataclass(frozen=True, slots=True)
class OriginAssessmentInputs:
    """All dependency objects are supplied in memory; no resolver is used at runtime."""

    evidence_snapshot_content: ArtifactContent
    materialization: EvidenceSnapshotMaterialization
    source_evaluability: ArtifactContent
    evidence_adapter_contract_set: ArtifactContent
    knowledge_bundle: ArtifactContent
    knowledge: KnowledgeBundleCandidate
    knowledge_evaluation_at_utc: str


class DeviceFingerprintOriginAssessmentBuilder:
    """Build six isolated origin artifacts from one exact in-memory lineage."""

    def __init__(self, inputs: OriginAssessmentInputs) -> None:
        if not isinstance(inputs, OriginAssessmentInputs):
            _fail("Invalid OriginAssessment inputs")
        self._inputs = inputs
        snapshot = inputs.evidence_snapshot_content
        source = inputs.source_evaluability
        if snapshot.artifact_type != "EvidenceSnapshotContent" or source.artifact_type != "SourceEvaluability":
            _fail("Invalid snapshot/evaluability artifacts")
        snap = snapshot.semantic_payload
        if source.semantic_payload.get("evidence_snapshot_content") != _ref(snapshot):
            _fail("SourceEvaluability/snapshot mismatch")
        if not isinstance(inputs.materialization, EvidenceSnapshotMaterialization):
            _fail("Invalid materialization")
        inputs.materialization.evidence_snapshot_content.resolve(snapshot, "EvidenceSnapshotContent")
        if (make_evidence_adapter_contract_set(inputs.evidence_adapter_contract_set.semantic_payload)
                != inputs.evidence_adapter_contract_set):
            _fail("Noncanonical adapter contract set")
        if not validate_knowledge_bundle_dependencies(inputs.knowledge_bundle, inputs.knowledge):
            _fail("Invalid KnowledgeBundle closure")
        parse_utc(inputs.knowledge_evaluation_at_utc)
        descriptors = {row["evidence_id"]: row for row in snap["evidence_descriptors"]}
        materialized: dict[str, Mapping[str, Any]] = {}
        for entry in inputs.materialization.ordered_entries:
            if not isinstance(entry.descriptor, Mapping) or not isinstance(entry.normalized_payload, Mapping):
                _fail("Invalid materialized entry")
            identifier = entry.descriptor.get("evidence_id")
            if identifier in materialized or descriptors.get(identifier) != dict(entry.descriptor):
                _fail("Materialization descriptor mismatch")
            materialized[identifier] = entry.normalized_payload
        self._descriptors = descriptors
        self._materialized = materialized
        self._entries = inputs.evidence_adapter_contract_set.semantic_payload["adapter_entries"]
        self._knowledge_freshness: dict[tuple[str, str], dict[str, Any]] = {}
        for slot in ("k1", "k2b", "k4"):
            for dimension in DIMENSIONS:
                result = evaluate_external_knowledge_freshness(
                    getattr(inputs.knowledge, f"{slot}_provenance"),
                    getattr(inputs.knowledge, f"{slot}_freshness_policy"),
                    knowledge_evaluation_at_utc=inputs.knowledge_evaluation_at_utc,
                    dimension_name=dimension)
                if result["failure_code"] == "negative_knowledge_age":
                    _fail("Negative knowledge age")
                self._knowledge_freshness[(slot, dimension)] = result

    def _knowledge_ref(self, slot: str, record_id: str, source_id: str) -> dict[str, str]:
        provenance = getattr(self._inputs.knowledge, f"{slot}_provenance")
        bundle = self._inputs.knowledge_bundle
        return {
            "knowledge_bundle_id": bundle.artifact_id,
            "knowledge_bundle_digest": bundle.content_sha256,
            "canonical_knowledge_record_id": record_id,
            "knowledge_provenance_id": provenance.artifact_id,
            "knowledge_provenance_digest": provenance.content_sha256,
            "rule_or_source_record_identity": source_id,
        }

    def _evidence_ref(self, descriptor: dict[str, Any]) -> dict[str, Any]:
        contract = self._inputs.evidence_adapter_contract_set
        return {
            "evidence_id": descriptor["evidence_id"],
            "payload_sha256": descriptor["payload_sha256"],
            "feature_schema_version": descriptor["feature_schema_version"],
            "adapter_contract_id": contract.artifact_id,
            "adapter_contract_digest": contract.content_sha256,
        }

    def _claim(self, outcome: dict[str, Any], *, adapter: dict[str, Any],
               slot: str, record_id: str, source_id: str,
               evidence: dict[str, Any] | None, quality: str = "valid",
               derivation: str | None = None) -> dict[str, Any] | None:
        dimension = outcome["dimension_name"]
        freshness = self._knowledge_freshness[(slot, dimension)] if slot != "k3" else None
        if freshness is not None and not freshness["claim_eligible"]:
            return None
        kind = outcome["outcome_kind"]
        if kind not in {"CANONICAL_VALUE", "RECOGNIZED_OUT_OF_SCOPE"}:
            return None
        if kind == "RECOGNIZED_OUT_OF_SCOPE" and dimension not in {"platform_family", "device_class"}:
            return None
        strength = _cap(outcome["base_claim_strength"], adapter["base_claim_strength_ceiling"])
        if quality == "partial" or (freshness is not None and freshness["claim_strength_cap"] == "supporting"):
            strength = "supporting"
        knowledge_ref = self._knowledge_ref(slot, record_id, source_id)
        return {
            "candidate_kind": "CANONICAL_VALUE" if kind == "CANONICAL_VALUE" else "OUT_OF_SCOPE_TAXON",
            "candidate_value_id": outcome.get("canonical_target_id") if kind == "CANONICAL_VALUE" else None,
            "out_of_scope_taxon_ref": (outcome.get("out_of_scope_taxon_ref") or outcome.get("outcome_id_or_ref"))
            if kind == "RECOGNIZED_OUT_OF_SCOPE" else None,
            "claim_strength": strength,
            "claim_derivation": derivation or adapter["claim_derivation"],
            "knowledge_refs": [knowledge_ref],
            "evidence_refs": [evidence] if evidence is not None else [],
        }

    def _task_rows(self, origin: str) -> tuple[list[tuple[dict[str, Any], Mapping[str, Any] | None,
                                                  dict[str, Any] | None]], list[str]]:
        rows = []
        explanations = []
        for descriptor in self._inputs.evidence_snapshot_content.semantic_payload["evidence_descriptors"]:
            if _SOURCE_ORIGIN[descriptor["source_kind"]] != origin:
                continue
            adapter = next((entry for entry in self._entries if entry["adapter_kind"] == "TASK01_EVIDENCE"
                            and entry["source_kind"] == descriptor["source_kind"]
                            and entry["feature_schema_version"] == descriptor["feature_schema_version"]), None)
            if adapter is None:
                explanations.append("unsupported_evidence_contract")
            rows.append((descriptor, self._materialized.get(descriptor["evidence_id"]), adapter))
        return rows, explanations

    def build(self, origin: str) -> ArtifactContent:
        if origin not in ORIGINS:
            _fail("Unknown origin")
        inputs = self._inputs
        candidates: dict[str, list[tuple[str, str, dict[str, Any]]]] = {
            dimension: [] for dimension in DIMENSIONS}
        broad: dict[str, list[tuple[str, str, dict[str, Any]]]] = {
            dimension: [] for dimension in DIMENSIONS}
        evaluated_evidence_refs: dict[str, list[dict[str, Any]]] = {
            dimension: [] for dimension in DIMENSIONS}
        explanations: list[str] = []
        evidence_refs: list[dict[str, Any]] = []
        knowledge_refs: list[dict[str, str]] = []
        tcp_disabled = False
        if origin == "mac_registry":
            adapter = next(entry for entry in self._entries if entry["adapter_kind"] == "MAC_REGISTRY")
            freshness = self._knowledge_freshness[("k4", "manufacturer_family")]
            if freshness["required_explanation_code"]:
                explanations.append(freshness["required_explanation_code"])
            if freshness["claim_eligible"]:
                mac = inputs.evidence_snapshot_content.semantic_payload["observed_mac"].lower()
                matched = match_k4_records(inputs.knowledge.k4_record_set, mac)
                if not matched:
                    explanations.append("no_ieee_assignment_claim")
                for record in matched:
                    knowledge_refs.append(self._knowledge_ref(
                        "k4", record["canonical_record_id"], record["source_record_identity"]))
                    mapping = record["manufacturer_mapping"]
                    if mapping is None:
                        explanations.append("mac_assignment_org_not_manufacturer")
                        continue
                    outcome = {"dimension_name": "manufacturer_family", "outcome_kind": "CANONICAL_VALUE",
                               "canonical_target_id": mapping["manufacturer_id"],
                               "base_claim_strength": mapping["base_claim_strength"]}
                    claim = self._claim(outcome, adapter=adapter, slot="k4",
                                        record_id=record["canonical_record_id"],
                                        source_id=record["source_record_identity"], evidence=None)
                    if claim:
                        candidates["manufacturer_family"].append((
                            adapter["semantic_projection_id"], "manufacturer_family", claim))
        else:
            rows, row_explanations = self._task_rows(origin)
            explanations.extend(row_explanations)
            tcp_disabled = origin == "tcp" and inputs.evidence_snapshot_content.semantic_payload[
                "origin_runtime_admission"]["tcp_state"] != "ENABLED"
            if tcp_disabled:
                explanations.append("origin_runtime_disabled")
            for descriptor, payload, adapter in rows:
                source_entry = next((entry for entry in inputs.source_evaluability.semantic_payload["source_entries"]
                                     if entry["binding_epoch_id"] == descriptor["binding_epoch_id"]), None)
                if source_entry is None:
                    _fail("Evidence lacks exact SourceEvaluability binding epoch")
                observed = parse_utc(descriptor["observed_at"])
                interval = next((interval for interval in source_entry["coverage_intervals"]
                                 if parse_utc(interval["start_utc"]) <= observed < parse_utc(interval["end_utc"])), None)
                if interval is None:
                    _fail("Evidence lies outside evaluability partition")
                if interval["coverage_class"] != "covered_available":
                    explanations.append("evidence_present_during_" + interval["coverage_class"])
                eref = self._evidence_ref(descriptor)
                evidence_refs.append(eref)
                if adapter is None:
                    continue
                if not _task_adapter_compatible(adapter, descriptor):
                    explanations.append("unsupported_evidence_contract")
                    continue
                if tcp_disabled:
                    continue
                if payload is None:
                    explanations.append("unsupported_evidence_contract")
                    continue
                if descriptor["quality_state"] == "degraded":
                    explanations.append("degraded_evidence_no_claim")
                    continue
                if adapter["legacy_current_role"] == "LEGACY_NON_FUSION":
                    explanations.append("legacy_tcp_schema_insufficient_for_exact_k2a_contract")
                    continue
                if adapter["quality_valid_behavior"].startswith("AUDIT_ONLY_"):
                    explanations.append("ja4_no_semantic_claim")
                    continue
                eligible_dimensions: set[str] = set()
                for dimension in DIMENSIONS:
                    if task01_contract_claim_eligible(
                            adapter, source_kind=descriptor["source_kind"],
                            feature_schema_version=descriptor["feature_schema_version"],
                            source_subtype=descriptor["source_subtype"],
                            extractor_name=descriptor["extractor_name"],
                            extractor_version=descriptor["extractor_version"],
                            rule_version=descriptor["rule_version"],
                            quality_state=descriptor["quality_state"],
                            normalized_payload=dict(payload), dimension_name=dimension):
                        evaluated_evidence_refs[dimension].append(eref)
                        eligible_dimensions.add(dimension)
                if not eligible_dimensions:
                    continue
                if origin == "dhcp":
                    records = match_k1_records(inputs.knowledge.k1_record_set, dict(payload))
                    if not records:
                        explanations.append("k1_empty_candidate_set")
                    for record in records:
                        kref = self._knowledge_ref("k1", record["canonical_record_id"], record["source_record_identity"])
                        knowledge_refs.append(kref)
                        for outcome in record["candidate_taxonomy_refs"]:
                            dimension = outcome["dimension_name"]
                            if not task01_contract_claim_eligible(
                                    adapter, source_kind=descriptor["source_kind"],
                                    feature_schema_version=descriptor["feature_schema_version"],
                                    source_subtype=descriptor["source_subtype"],
                                    extractor_name=descriptor["extractor_name"],
                                    extractor_version=descriptor["extractor_version"],
                                    rule_version=descriptor["rule_version"],
                                    quality_state=descriptor["quality_state"],
                                    normalized_payload=dict(payload), dimension_name=dimension):
                                continue
                            freshness = self._knowledge_freshness[("k1", dimension)]
                            if freshness["required_explanation_code"]:
                                explanations.append(freshness["required_explanation_code"])
                            if not freshness["claim_eligible"]:
                                continue
                            if outcome["outcome_kind"] in {"BROAD_UNRESOLVED", "UNMAPPED"}:
                                broad[dimension].append((adapter["semantic_projection_id"], dimension, {
                                    "reference_kind": "BROAD_TAXON" if outcome["outcome_kind"] == "BROAD_UNRESOLVED"
                                    else "UNMAPPED_TAXON",
                                    "canonical_taxon_or_source_ref": outcome["broad_taxon_ref"]
                                    if outcome["outcome_kind"] == "BROAD_UNRESOLVED"
                                    else record["source_record_identity"],
                                    "evidence_refs": [eref], "knowledge_refs": [kref],
                                    "explanation_code": "k1_broad_unresolved" if outcome["outcome_kind"] == "BROAD_UNRESOLVED"
                                    else "k1_unmapped_taxon",
                                }))
                                continue
                            claim = self._claim(outcome, adapter=adapter, slot="k1",
                                                record_id=record["canonical_record_id"],
                                                source_id=record["source_record_identity"], evidence=eref,
                                                quality=descriptor["quality_state"])
                            if claim:
                                candidates[dimension].append((adapter["semantic_projection_id"], dimension, claim))
                elif origin == "portal":
                    from .k3_portal_rules import evaluate_k3_rules
                    portal_result = evaluate_k3_rules(
                        inputs.knowledge.k3_portal_rule_set,
                        descriptor["feature_schema_version"], payload)
                    matched_ids = set(portal_result["matched_rule_ids"])
                    matches = [rule for rule in inputs.knowledge.k3_portal_rule_set.semantic_payload["rules"]
                               if rule["rule_id"] in matched_ids]
                    for rule in matches:
                        dimension = rule["dimension_name"]
                        if not task01_contract_claim_eligible(
                                adapter, source_kind=descriptor["source_kind"],
                                feature_schema_version=descriptor["feature_schema_version"],
                                source_subtype=descriptor["source_subtype"],
                                extractor_name=descriptor["extractor_name"],
                                extractor_version=descriptor["extractor_version"],
                                rule_version=descriptor["rule_version"],
                                quality_state=descriptor["quality_state"],
                                normalized_payload=dict(payload), dimension_name=dimension):
                            continue
                        kref = self._knowledge_ref("k3", rule["rule_id"], rule["rule_id"])
                        knowledge_refs.append(kref)
                        if rule["outcome_kind"] == "BROAD_UNRESOLVED":
                            broad[dimension].append((adapter["semantic_projection_id"], dimension, {
                                "reference_kind": "BROAD_TAXON",
                                "canonical_taxon_or_source_ref": rule["outcome_id_or_ref"],
                                "evidence_refs": [eref], "knowledge_refs": [kref],
                                "explanation_code": rule["explanation_code"],
                            }))
                        elif rule["outcome_kind"] in {"CANONICAL_VALUE", "RECOGNIZED_OUT_OF_SCOPE"}:
                            outcome = {"dimension_name": dimension, "outcome_kind": rule["outcome_kind"],
                                       "canonical_target_id": rule["outcome_id_or_ref"],
                                       "outcome_id_or_ref": rule["outcome_id_or_ref"],
                                       "base_claim_strength": rule["base_claim_strength"]}
                            claim = self._claim(outcome, adapter=adapter, slot="k3",
                                                record_id=rule["rule_id"], source_id=rule["rule_id"],
                                                evidence=eref, quality=descriptor["quality_state"],
                                                derivation=rule["claim_derivation"])
                            if claim:
                                candidates[dimension].append((adapter["semantic_projection_id"], dimension, claim))
                        explanations.append(rule["explanation_code"])
                elif origin == "tcp":
                    if not task01_contract_claim_eligible(
                            adapter, source_kind=descriptor["source_kind"],
                            feature_schema_version=descriptor["feature_schema_version"],
                            source_subtype=descriptor["source_subtype"],
                            extractor_name=descriptor["extractor_name"],
                            extractor_version=descriptor["extractor_version"],
                            rule_version=descriptor["rule_version"],
                            quality_state=descriptor["quality_state"],
                            normalized_payload=dict(payload), dimension_name="platform_family"):
                        continue
                    runtime = adapt_tcp_syn_v2(payload)
                    records = inputs.knowledge.k2b_record_set.semantic_payload["records"]
                    signatures = [parse_request_signature(record["canonical_match_rule"],
                                    signature_id=record["canonical_record_id"])
                                  for record in records]
                    matched = match_request(runtime, signatures)
                    if matched.status != "MATCH":
                        explanations.append("k2a_no_match")
                        continue
                    record = next(record for record in records if record["canonical_record_id"] == matched.signature_id)
                    for outcome in record["dimension_claims"]:
                        freshness = self._knowledge_freshness[("k2b", outcome["dimension_name"])]
                        if freshness["required_explanation_code"]:
                            explanations.append(freshness["required_explanation_code"])
                        claim = self._claim(outcome, adapter=adapter, slot="k2b",
                                            record_id=record["canonical_record_id"],
                                            source_id=record["source_record_identity"], evidence=eref,
                                            quality=descriptor["quality_state"])
                        if claim:
                            candidates[outcome["dimension_name"]].append((
                                adapter["semantic_projection_id"], outcome["dimension_name"], claim))
        source_entries = [entry for entry in inputs.source_evaluability.semantic_payload["source_entries"]
                          if entry["origin_group"] == origin]
        coverage_not_evaluable = bool(source_entries) and all(
            entry["aggregate_evaluability_state"] == "not_evaluable" for entry in source_entries)
        dimensions = [_reduce_claims(
            dimension, _merge_contributions(candidates[dimension]),
            broad=_merge_contributions(broad[dimension], broad=True), explanations=explanations,
            k1_ambiguous=origin == "dhcp",
            evaluated_evidence_refs=evaluated_evidence_refs[dimension],
            not_evaluable=(origin != "mac_registry" and not rows and coverage_not_evaluable
                           and not tcp_disabled),
        ) for dimension in DIMENSIONS]
        knowledge_refs.extend(ref for dimension in dimensions for ref in dimension["knowledge_refs"])
        payload = {
            "origin_assessment_contract_version": 1,
            "evidence_snapshot_content": _ref(inputs.evidence_snapshot_content),
            "source_evaluability": _ref(inputs.source_evaluability),
            "origin_group": origin,
            "dimension_assessments": dimensions,
            "evidence_refs": _evidence_set(_unique(evidence_refs)),
            "knowledge_refs": _knowledge_set(_unique(knowledge_refs)),
            "explanation_codes": _strings(list(set(explanations)), "explanation"),
        }
        return make_origin_assessment(payload, evidence_snapshot_content=inputs.evidence_snapshot_content,
                                      source_evaluability=inputs.source_evaluability,
                                      evidence_adapter_contract_set=inputs.evidence_adapter_contract_set,
                                      knowledge_bundle=inputs.knowledge_bundle,
                                      knowledge=inputs.knowledge)

    def build_all(self) -> tuple[ArtifactContent, ...]:
        return tuple(self.build(origin) for origin in ORIGINS)
