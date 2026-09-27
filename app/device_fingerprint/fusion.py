"""Pure R14 T-04 cross-origin fusion over six immutable OriginAssessments."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .artifact_content import (
    ArtifactContent, ArtifactRef, canonical_artifact_json, canonical_set,
    make_artifact_content,
)
from .classification_policy import (
    make_classification_policy, validate_classification_policy_dependencies,
)
from .evidence_adapter_contracts import DIMENSIONS
from .knowledge_bundle import KnowledgeBundleCandidate, validate_knowledge_bundle_dependencies
from .models import DeviceFingerprintValidationError
from .origin_assessment import ORIGINS, make_origin_assessment
from .validation import validate_mac

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_FUSION_KEYS = (
    "strong_clean_present", "strong_clean_disagree", "strong_internal_conflict_present",
    "supporting_clean_present", "supporting_clean_disagree",
    "supporting_internal_conflict_present",
    "supporting_vs_selected_strong_incompatible_present",
)
_DIMENSION_FIELDS = frozenset({
    "dimension_name", "canonical_value_id", "display_label_ref", "status",
    "support_level", "supporting_origin_groups", "contradicting_origin_groups",
    "not_evaluable_origin_groups", "out_of_scope_taxon_references",
    "explanation_codes", "knowledge_references",
})
def _fail(message: str) -> None:
    raise DeviceFingerprintValidationError(message)


def _ref(content: ArtifactContent, kind: str) -> dict[str, str]:
    if not isinstance(content, ArtifactContent) or content.artifact_type != kind:
        _fail(f"Invalid {kind} artifact")
    return ArtifactRef(content.artifact_id, content.content_sha256).as_dict()


def _primitive_set(values: list[str]) -> list[str]:
    return canonical_set(list(set(values)), lambda value: value)


def _knowledge_set(values: list[dict[str, str]]) -> list[dict[str, str]]:
    unique = {canonical_artifact_json(value): value for value in values}
    return canonical_set(list(unique.values()), lambda value: (
        value["knowledge_provenance_id"], value["canonical_knowledge_record_id"],
        value["rule_or_source_record_identity"],
    ))


def _target(row: dict[str, Any]) -> tuple[str, str] | None:
    if row["internal_state"] == "resolved":
        return ("CANONICAL_VALUE", row["selected_canonical_value_id"])
    if row["internal_state"] == "recognized_out_of_scope":
        return ("OUT_OF_SCOPE_TAXON", row["selected_out_of_scope_taxon_ref"])
    return None


def _fusion_cell(policy: dict[str, Any], bits: tuple[bool, ...]) -> dict[str, Any]:
    """Lookup, rather than recompute, exactly one frozen policy matrix row."""
    if len(bits) != len(_FUSION_KEYS) or any(type(bit) is not bool for bit in bits):
        _fail("Invalid cross-origin fusion key")
    rows = [row for row in policy["cross_origin_fusion_matrix"]
            if tuple(row[key] for key in _FUSION_KEYS) == bits]
    if len(rows) != 1:
        _fail("Cross-origin fusion cell missing or duplicated")
    return rows[0]


def _first_rule(rows: list[dict[str, Any]], conditions: dict[str, bool]) -> str:
    """Execute the validated policy's ordered rules, not a parallel result table."""
    for row in rows:
        if conditions.get(row["condition"], False):
            return row["result"]
    _fail("No matching policy rule")


def _validate_dimension_result(result: dict[str, Any], out_scope: set[str]) -> None:
    if set(result) != _DIMENSION_FIELDS or result["dimension_name"] not in DIMENSIONS:
        _fail("Invalid DimensionResult shape")
    if result["display_label_ref"] is not None:
        _fail("R1 display label must be null")
    status = result["status"]
    selected = status in {"resolved", "recognized_out_of_scope"}
    if selected:
        if result["support_level"] not in {"low", "medium", "high"} or not result["supporting_origin_groups"]:
            _fail("Invalid selected DimensionResult support")
        if status == "resolved" and not result["canonical_value_id"]:
            _fail("Resolved DimensionResult lacks canonical value")
        if status == "recognized_out_of_scope" and (
                result["dimension_name"] not in out_scope or result["canonical_value_id"] is not None
                or not result["out_of_scope_taxon_references"]):
            _fail("Invalid out-of-scope DimensionResult")
    elif status not in {"unknown", "insufficient_evidence", "conflicting_evidence"} or (
            result["canonical_value_id"] is not None or result["support_level"] != "none"):
        _fail("Invalid unselected DimensionResult")
    if status == "conflicting_evidence" and not result["contradicting_origin_groups"]:
        _fail("Conflicting DimensionResult lacks contradicting origin")
    for field in ("supporting_origin_groups", "contradicting_origin_groups",
                  "not_evaluable_origin_groups", "out_of_scope_taxon_references", "explanation_codes"):
        if result[field] != canonical_set(result[field], lambda value: value):
            _fail(f"Noncanonical DimensionResult {field}")
    if result["knowledge_references"] != _knowledge_set(result["knowledge_references"]):
        _fail("Noncanonical DimensionResult knowledge references")


@dataclass(frozen=True, slots=True)
class FusionInputs:
    classification_request_digest: str
    classification_policy: ArtifactContent
    classification_taxonomy: ArtifactContent
    alias_mapping: ArtifactContent
    evidence_adapter_contract_set: ArtifactContent
    knowledge_bundle: ArtifactContent
    knowledge: KnowledgeBundleCandidate
    classifier_artifact_manifest: ArtifactContent
    evidence_snapshot_content: ArtifactContent
    source_evaluability: ArtifactContent
    origin_assessments: tuple[ArtifactContent, ...]


class DeviceFingerprintFusionCore:
    def __init__(self, inputs: FusionInputs) -> None:
        if not isinstance(inputs, FusionInputs):
            _fail("Invalid fusion inputs")
        self._inputs = inputs
        try:
            self._validate()
        except (AttributeError, KeyError, TypeError, ValueError, IndexError) as exc:
            raise DeviceFingerprintValidationError("Malformed fusion input") from exc

    def _validate(self) -> None:
        value = self._inputs
        if not isinstance(value.classification_request_digest, str) or not _DIGEST.fullmatch(
                value.classification_request_digest):
            _fail("Invalid classification request digest")
        _ref(value.classification_policy, "ClassificationPolicy")
        if make_classification_policy(value.classification_policy.semantic_payload) != value.classification_policy:
            _fail("Noncanonical ClassificationPolicy")
        validate_classification_policy_dependencies(
            value.classification_policy, classification_taxonomy=value.classification_taxonomy,
            alias_mapping=value.alias_mapping,
            evidence_adapter_contract_set=value.evidence_adapter_contract_set)
        validate_knowledge_bundle_dependencies(value.knowledge_bundle, value.knowledge)
        bundle = value.knowledge_bundle.semantic_payload
        if bundle["classification_taxonomy"] != _ref(value.classification_taxonomy, "ClassificationTaxonomy") or (
                bundle["alias_mapping"] != _ref(value.alias_mapping, "AliasMapping")):
            _fail("KnowledgeBundle/ClassificationPolicy dependency mismatch")
        _ref(value.classifier_artifact_manifest, "ClassifierArtifactManifest")
        snapshot = _ref(value.evidence_snapshot_content, "EvidenceSnapshotContent")
        _ref(value.source_evaluability, "SourceEvaluability")
        if value.source_evaluability.semantic_payload["evidence_snapshot_content"] != snapshot:
            _fail("SourceEvaluability/snapshot mismatch")
        if not isinstance(value.origin_assessments, tuple) or len(value.origin_assessments) != len(ORIGINS):
            _fail("Exactly six OriginAssessments are required")
        by_origin: dict[str, ArtifactContent] = {}
        for assessment in value.origin_assessments:
            _ref(assessment, "OriginAssessment")
            payload = assessment.semantic_payload
            rebuilt = make_origin_assessment(
                payload, evidence_snapshot_content=value.evidence_snapshot_content,
                source_evaluability=value.source_evaluability,
                evidence_adapter_contract_set=value.evidence_adapter_contract_set,
                knowledge_bundle=value.knowledge_bundle, knowledge=value.knowledge)
            if rebuilt != assessment:
                _fail("Noncanonical OriginAssessment")
            origin = payload["origin_group"]
            if origin in by_origin:
                _fail("Duplicate origin")
            by_origin[origin] = assessment
        if set(by_origin) != set(ORIGINS):
            _fail("Missing or extra origin")
        self._origins = by_origin
        self._policy = value.classification_policy.semantic_payload

    def _applicable_path(self, dimension: str, origin: str, row: dict[str, Any]) -> bool:
        """Consume T-03's evaluated dimension lineage; do not revisit payloads."""
        if row["internal_state"] != "no_claim":
            return False
        if origin == "mac_registry":
            mac = self._inputs.evidence_snapshot_content.semantic_payload["observed_mac"]
            if validate_mac(mac) != mac:
                _fail("Noncanonical observed MAC")
            return dimension == "manufacturer_family" and not (int(mac[:2], 16) & 0x02)
        return bool(row["evidence_refs"])

    def _dimension(self, dimension: str) -> dict[str, Any]:
        rows = {origin: next(row for row in assessment.semantic_payload["dimension_assessments"]
                             if row["dimension_name"] == dimension)
                for origin, assessment in self._origins.items()}
        clean = {origin: (_target(row), row["effective_claim_strength"])
                 for origin, row in rows.items() if _target(row) is not None}
        strong = {origin: target for origin, (target, strength) in clean.items() if strength == "strong"}
        supporting = {origin: target for origin, (target, strength) in clean.items() if strength == "supporting"}
        strong_conflicts = {origin for origin, row in rows.items()
                            if row["internal_state"] == "conflicting" and row["conflict_strength"] == "strong"}
        supporting_conflicts = {origin for origin, row in rows.items()
                                if row["internal_state"] == "conflicting" and row["conflict_strength"] == "supporting"}
        unique_strong = next(iter(set(strong.values()))) if strong and len(set(strong.values())) == 1 else None
        same_origin_contradictions = {origin for origin, row in rows.items()
                                      if origin in strong and strong[origin] == unique_strong and any(
                                          item["conflict_strength"] == "supporting"
                                          for item in row["same_origin_contradiction_records"])}
        # This matrix bit is exclusively cross-origin. A retained same-origin
        # contradiction is recorded separately and independently prevents HIGH.
        incompatible = bool(unique_strong and not strong_conflicts and supporting and (
            any(target != unique_strong for target in supporting.values())))
        bits = (bool(strong), len(set(strong.values())) > 1, bool(strong_conflicts),
                bool(supporting), len(set(supporting.values())) > 1,
                bool(supporting_conflicts), incompatible)
        cell = _fusion_cell(self._policy, bits)
        outcome = cell["outcome"]
        if outcome == "SELECT_STRONG":
            selected = unique_strong
        elif outcome == "SELECT_SUPPORTING":
            selected = next(iter(set(supporting.values())))
        elif outcome in {"CONFLICTING_EVIDENCE", "NO_CONCRETE_SELECTION"}:
            selected = None
        else:
            _fail("Invalid fusion outcome")
        if outcome.startswith("SELECT_") and selected is None:
            _fail("Fusion cell selected no target")
        support_origins = {origin for origin, (target, _) in clean.items() if target == selected} if selected else set()
        if selected:
            contradiction_origins = {origin for origin, (target, _) in clean.items() if target != selected}
            contradiction_origins.update(supporting_conflicts)
            contradiction_origins.update(same_origin_contradictions)
        elif outcome == "CONFLICTING_EVIDENCE":
            contradiction_origins = strong_conflicts | (set(strong) if bits[1] else set())
            if not strong and not strong_conflicts:
                contradiction_origins |= supporting_conflicts | (set(supporting) if bits[4] else set())
        else:
            contradiction_origins = set()
        explanations: list[str] = []
        knowledge: list[dict[str, str]] = []
        out_scope: list[str] = []
        for row in rows.values():
            explanations.extend(row["explanation_codes"])
            knowledge.extend(row["knowledge_refs"])
            for candidate in row["candidate_set"]:
                knowledge.extend(candidate["knowledge_refs"])
                if candidate["candidate_kind"] == "OUT_OF_SCOPE_TAXON":
                    out_scope.append(candidate["out_of_scope_taxon_ref"])
            for record in row["same_origin_contradiction_records"]:
                explanations.append(record["explanation_code"])
                knowledge.extend(record["knowledge_refs"])
            for broad in row["broad_unresolved_taxon_refs"]:
                explanations.append(broad["explanation_code"])
                knowledge.extend(broad["knowledge_refs"])
        if outcome == "CONFLICTING_EVIDENCE":
            explanations.append("cross_origin_conflicting_evidence")
        if selected and cell["record_supporting_contradiction"]:
            explanations.append("cross_origin_supporting_contradiction")
        unresolved = any(row["internal_state"] == "ambiguous" or row["broad_unresolved_taxon_refs"]
                         or (dimension in {"manufacturer_family", "model_family"}
                             and "mac_assignment_org_not_manufacturer" in row["explanation_codes"])
                         for row in rows.values())
        no_usable = any(self._applicable_path(dimension, origin, row)
                        for origin, row in rows.items())
        conditions = {
            "DECISIVE_CONFLICT": outcome == "CONFLICTING_EVIDENCE",
            "SELECTABLE_IN_SCOPE": selected is not None and selected[0] == "CANONICAL_VALUE",
            "SELECTABLE_OUT_OF_SCOPE_WHERE_ALLOWED": selected is not None and selected[0] == "OUT_OF_SCOPE_TAXON"
            and dimension in self._policy["recognized_out_of_scope_applicability"],
            "SEMANTIC_INFO_UNRESOLVED": selected is None and unresolved,
            "SUPPORTED_EVIDENCE_NO_USABLE_SEMANTIC_KNOWLEDGE": selected is None and not unresolved and no_usable,
            "NO_ADEQUATE_SUPPORTED_EVIDENCE_PATH": selected is None and not unresolved and not no_usable,
        }
        if selected is not None and selected[0] == "OUT_OF_SCOPE_TAXON" and dimension not in (
                self._policy["recognized_out_of_scope_applicability"]):
            _fail("Out-of-scope target for inapplicable dimension")
        status = _first_rule(self._policy["dimension_result_rules"], conditions)
        if outcome == "NO_CONCRETE_SELECTION":
            explanations.append({
                "SEMANTIC_INFO_UNRESOLVED": "fusion_semantic_information_unresolved",
                "SUPPORTED_EVIDENCE_NO_USABLE_SEMANTIC_KNOWLEDGE": "fusion_no_usable_semantic_knowledge",
                "NO_ADEQUATE_SUPPORTED_EVIDENCE_PATH": "fusion_no_adequate_supported_evidence_path",
            }[next(name for name in (
                "SEMANTIC_INFO_UNRESOLVED", "SUPPORTED_EVIDENCE_NO_USABLE_SEMANTIC_KNOWLEDGE",
                "NO_ADEQUATE_SUPPORTED_EVIDENCE_PATH") if conditions[name])])
        high = (selected is not None and len(strong) >= 2
                and len({target for target in strong.values()}) == 1
                and len(support_origins) >= 2 and not contradiction_origins
                and not supporting_conflicts and not same_origin_contradictions
                and cell["support_cap"] != "MEDIUM")
        support = _first_rule(self._policy["support_level_rules"], {
            "HIGH_ALL_REQUIREMENTS": high,
            "MEDIUM_STRONG_NO_DECISIVE_CONFLICT": selected is not None and bool(set(strong) & support_origins),
            "LOW_SUPPORTING_ONLY_ALL_AGREE": selected is not None and not strong and bool(support_origins),
            "NONE_UNRESOLVED": selected is None,
        })
        result = {
            "dimension_name": dimension,
            "canonical_value_id": selected[1] if status == "resolved" else None,
            "display_label_ref": None,
            "status": status,
            "support_level": support,
            "supporting_origin_groups": _primitive_set(list(support_origins)),
            "contradicting_origin_groups": _primitive_set(list(contradiction_origins)),
            "not_evaluable_origin_groups": _primitive_set([
                origin for origin, row in rows.items() if row["internal_state"] == "not_evaluable"]),
            "out_of_scope_taxon_references": _primitive_set(out_scope),
            "explanation_codes": _primitive_set(explanations),
            "knowledge_references": _knowledge_set(knowledge),
        }
        _validate_dimension_result(result, set(self._policy["recognized_out_of_scope_applicability"]))
        return result

    def fuse(self) -> ArtifactContent:
        dimensions = {dimension: self._dimension(dimension) for dimension in DIMENSIONS}
        statuses = {dimension: row["status"] for dimension, row in dimensions.items()}
        global_status = _first_rule(self._policy["global_status_derivation"], {
            "ANY_DIMENSION_CONFLICTING": "conflicting_evidence" in statuses.values(),
            "ALL_FOUR_DIMENSIONS_RESOLVED": all(status == "resolved" for status in statuses.values()),
            "ANY_DIMENSION_RESOLVED": "resolved" in statuses.values(),
            "ANY_PLATFORM_OR_DEVICE_CLASS_OUT_OF_SCOPE": any(
                statuses[dimension] == "recognized_out_of_scope"
                for dimension in ("platform_family", "device_class")),
            "ANY_DIMENSION_INSUFFICIENT": "insufficient_evidence" in statuses.values(),
            "OTHERWISE": True,
        })
        value = self._inputs
        return make_artifact_content("ClassificationResult", {
            "classification_request_digest": value.classification_request_digest,
            "classification_policy": _ref(value.classification_policy, "ClassificationPolicy"),
            "knowledge_bundle": _ref(value.knowledge_bundle, "KnowledgeBundle"),
            "classifier_artifact_manifest": _ref(value.classifier_artifact_manifest, "ClassifierArtifactManifest"),
            "evidence_snapshot_content": _ref(value.evidence_snapshot_content, "EvidenceSnapshotContent"),
            "source_evaluability": _ref(value.source_evaluability, "SourceEvaluability"),
            "platform_result": dimensions["platform_family"],
            "device_class_result": dimensions["device_class"],
            "manufacturer_result": dimensions["manufacturer_family"],
            "model_result": dimensions["model_family"],
            "global_classification_status": global_status,
            "origin_assessments": canonical_set([
                _ref(assessment, "OriginAssessment") for assessment in value.origin_assessments],
                lambda reference: reference["artifact_id"]),
        })


def fuse_classification(inputs: FusionInputs) -> ArtifactContent:
    """Build the same deterministic artifact as DeviceFingerprintFusionCore.fuse."""
    return DeviceFingerprintFusionCore(inputs).fuse()
