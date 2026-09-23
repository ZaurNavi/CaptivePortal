"""Frozen R14 F-F2 ClassificationPolicy data; no classification runtime."""

from __future__ import annotations

from copy import deepcopy
from itertools import product
from typing import Any

from .artifact_content import ArtifactContent, ArtifactRef, canonical_set, make_artifact_content
from .evidence_adapter_contracts import make_evidence_adapter_contract_set
from .models import DeviceFingerprintValidationError
from .taxonomy_artifacts import (
    make_alias_mapping, make_classification_taxonomy,
    validate_alias_mapping_against_taxonomy,
)

_FIELDS = frozenset({
    "policy_schema_version", "classification_taxonomy", "alias_mapping",
    "evidence_adapter_contract_set", "claim_derivation_semantics",
    "claim_strength_semantics", "same_origin_ambiguity_conflict_rules",
    "same_origin_conflict_strength_rules", "cross_origin_fusion_matrix",
    "support_level_rules", "dimension_result_rules",
    "recognized_out_of_scope_applicability", "global_status_derivation",
    "knowledge_freshness_policy_execution_semantics",
})
_CROSS_LAYER_FIELDS = frozenset({
    "ClassificationRetentionPolicy", "ProductValidationPolicy", "SnapshotExecutionPolicy",
    "SnapshotContentPolicy", "SourceHealthPolicy", "runtime_profile_pointer",
    "production_activation_identity", "database_retention", "ui_policy",
    "task04_implementation_identity",
})
_DERIVATIONS = {
    name: "PROVENANCE_ONLY_NO_AUTHORITY_ORDER" for name in (
        "declared", "deterministic_mapping", "fingerprint_match", "registry_mapping"
    )
}
_STRENGTHS = {"supporting": 1, "strong": 2}
_AMBIGUITY = [{
    "rule": "COMPATIBLE_CANDIDATE_VARIATION", "projection_mode": "PER_DIMENSION",
    "compatible_multi_candidate_outcome": "AMBIGUOUS_NOT_CONFLICT",
}]
_CONFLICT = [
    {"left_strength": left, "right_strength": right,
     "compatibility": compatibility, "outcome": outcome}
    for left, right, compatibility, outcome in (
        ("strong", "strong", "SAME", "RESOLVED_STRONG"),
        ("strong", "strong", "INCOMPATIBLE", "CONFLICT_STRONG"),
        ("strong", "supporting", "SAME", "RESOLVED_STRONG"),
        ("strong", "supporting", "INCOMPATIBLE",
         "RESOLVED_STRONG_WITH_SUPPORTING_CONTRADICTION"),
        ("supporting", "supporting", "SAME", "RESOLVED_SUPPORTING"),
        ("supporting", "supporting", "INCOMPATIBLE", "CONFLICT_SUPPORTING"),
    )
]
_FUSION_INPUTS = (
    "strong_clean_present", "strong_clean_disagree", "strong_internal_conflict_present",
    "supporting_clean_present", "supporting_clean_disagree",
    "supporting_internal_conflict_present",
    "supporting_vs_selected_strong_incompatible_present",
)
_FUSION_FIELDS = frozenset((*_FUSION_INPUTS, "outcome",
                            "record_supporting_contradiction", "support_cap"))
_SUPPORT = [
    {"rule_order": order, "condition": condition, "result": result}
    for order, condition, result in (
        (1, "HIGH_ALL_REQUIREMENTS", "high"),
        (2, "MEDIUM_STRONG_NO_DECISIVE_CONFLICT", "medium"),
        (3, "LOW_SUPPORTING_ONLY_ALL_AGREE", "low"),
        (4, "NONE_UNRESOLVED", "none"),
    )
]
_DIMENSION = [
    {"precedence": order, "condition": condition, "result": result}
    for order, condition, result in (
        (1, "DECISIVE_CONFLICT", "conflicting_evidence"),
        (2, "SELECTABLE_IN_SCOPE", "resolved"),
        (3, "SELECTABLE_OUT_OF_SCOPE_WHERE_ALLOWED", "recognized_out_of_scope"),
        (4, "SEMANTIC_INFO_UNRESOLVED", "insufficient_evidence"),
        (5, "SUPPORTED_EVIDENCE_NO_USABLE_SEMANTIC_KNOWLEDGE", "unknown"),
        (6, "NO_ADEQUATE_SUPPORTED_EVIDENCE_PATH", "insufficient_evidence"),
    )
]
_GLOBAL = [
    {"precedence": order, "condition": condition, "result": result}
    for order, condition, result in (
        (1, "ANY_DIMENSION_CONFLICTING", "conflicting_evidence"),
        (2, "ALL_FOUR_DIMENSIONS_RESOLVED", "classified"),
        (3, "ANY_DIMENSION_RESOLVED", "partial"),
        (4, "ANY_PLATFORM_OR_DEVICE_CLASS_OUT_OF_SCOPE", "recognized_out_of_scope"),
        (5, "ANY_DIMENSION_INSUFFICIENT", "insufficient_evidence"),
        (6, "OTHERWISE", "unknown"),
    )
]
_FRESHNESS = {
    "evaluation_time_source": "CLASSIFICATION_REQUEST_KNOWLEDGE_EVALUATION_AT_UTC",
    "negative_age_behavior": "REQUEST_FAIL",
    "policy_source": "KNOWLEDGE_PROVENANCE_REFERENCED_POLICY",
    "dimension_override_precedence": "MATCHING_DIMENSION_OVERRIDE_REPLACES_GENERAL_STATE_RULE",
    "strength_cap_mode": "MINIMUM_AUTHORITY",
    "expired_behavior": "NO_NEW_CLAIM",
}


class _PolicyMatrixIncomplete(DeviceFingerprintValidationError):
    """A required canonical matrix cell is missing."""


class _PolicyMatrixMismatch(DeviceFingerprintValidationError):
    """A matrix cell is invalid, duplicated, or semantically different."""


class _PolicyCrossLayerContamination(DeviceFingerprintValidationError):
    """Policy payload contains a field owned by another layer."""


def _fail(message: str) -> None:
    raise DeviceFingerprintValidationError(message)


def _shape(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        _fail(f"Invalid {label} shape")
    return value


def _ref(value: Any, kind: str) -> dict[str, str]:
    ref = ArtifactRef.from_dict(value)
    if not ref.artifact_id.startswith(f"{kind}:v1:sha256:"):
        _fail(f"Invalid {kind} reference")
    return ref.as_dict()


def _valid_fusion_input(bits: tuple[bool, ...]) -> bool:
    strong, strong_disagree, strong_conflict, supporting, supporting_disagree, _, opposed = bits
    return not (
        strong_disagree and not strong
        or supporting_disagree and not supporting
        or opposed and (not strong or strong_disagree or strong_conflict or not supporting)
    )


def _fusion_outcome(bits: tuple[bool, ...]) -> tuple[str, bool, str]:
    strong, strong_disagree, strong_conflict, supporting, supporting_disagree, supporting_conflict, opposed = bits
    if strong_conflict or strong_disagree:
        return "CONFLICTING_EVIDENCE", False, "NONE"
    if strong:
        contradiction = supporting_conflict or opposed
        return "SELECT_STRONG", contradiction, "MEDIUM" if contradiction else "NONE"
    if supporting_conflict or supporting_disagree:
        return "CONFLICTING_EVIDENCE", False, "NONE"
    if supporting:
        return "SELECT_SUPPORTING", False, "NONE"
    return "NO_CONCRETE_SELECTION", False, "NONE"


def _fusion_cells() -> list[dict[str, Any]]:
    rows = []
    for bits in product((False, True), repeat=len(_FUSION_INPUTS)):
        if _valid_fusion_input(bits):
            outcome, contradiction, cap = _fusion_outcome(bits)
            rows.append(dict(zip(_FUSION_INPUTS, bits)) | {
                "outcome": outcome, "record_supporting_contradiction": contradiction,
                "support_cap": cap,
            })
    if len(rows) != 40:
        _fail("Frozen fusion-state count mismatch")
    return canonical_set(rows, lambda row: tuple(row[name] for name in _FUSION_INPUTS))


def _exact_set(value: Any, expected: list[Any], fields: frozenset[str] | None,
               key_fields: tuple[str, ...] | None, label: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(f"Invalid {label} SET")
    if fields is not None:
        for row in value:
            _shape(row, fields, label)
    key = (lambda row: tuple(row[name] for name in key_fields)) if key_fields else (lambda row: row)
    try:
        keys = [key(row) for row in value]
        unique_keys = set(keys)
    except (KeyError, TypeError) as exc:
        raise DeviceFingerprintValidationError(f"Invalid {label} primary key") from exc
    if len(keys) != len(unique_keys):
        raise _PolicyMatrixMismatch(f"Duplicate {label} primary key")
    ordered = canonical_set(value, key)
    canonical_expected = canonical_set(expected, key)
    if len(ordered) < len(canonical_expected):
        raise _PolicyMatrixIncomplete(f"Incomplete {label}")
    if ordered != canonical_expected:
        raise _PolicyMatrixMismatch(f"Incorrect {label}")
    return ordered


def make_classification_policy(payload: dict[str, Any]) -> ArtifactContent:
    """Validate closed R14 C.3.23 semantic data and materialize its identity."""
    if isinstance(payload, dict) and set(payload) & _CROSS_LAYER_FIELDS:
        raise _PolicyCrossLayerContamination("Cross-layer field in ClassificationPolicy")
    value = _shape(payload, _FIELDS, "ClassificationPolicy")
    if type(value["policy_schema_version"]) is not int or value["policy_schema_version"] != 1:
        _fail("Invalid policy schema version")
    refs = {
        field: _ref(value[field], kind) for field, kind in (
            ("classification_taxonomy", "ClassificationTaxonomy"),
            ("alias_mapping", "AliasMapping"),
            ("evidence_adapter_contract_set", "EvidenceAdapterContractSet"),
        )
    }
    if value["claim_derivation_semantics"] != _DERIVATIONS:
        _fail("Invalid claim derivation semantics")
    if (not isinstance(value["claim_strength_semantics"], dict)
            or set(value["claim_strength_semantics"]) != set(_STRENGTHS)
            or any(type(value["claim_strength_semantics"][name]) is not int
                   or value["claim_strength_semantics"][name] != expected
                   for name, expected in _STRENGTHS.items())):
        _fail("Invalid claim strength semantics")
    ambiguity = _exact_set(
        value["same_origin_ambiguity_conflict_rules"], _AMBIGUITY,
        frozenset(_AMBIGUITY[0]), ("rule",), "same-origin ambiguity")
    conflict = _exact_set(
        value["same_origin_conflict_strength_rules"], _CONFLICT,
        frozenset(_CONFLICT[0]),
        ("left_strength", "right_strength", "compatibility"), "same-origin conflict")
    fusion = value["cross_origin_fusion_matrix"]
    if not isinstance(fusion, list):
        _fail("Invalid cross-origin fusion SET")
    for row in fusion:
        _shape(row, _FUSION_FIELDS, "CrossOriginFusionCell")
        if any(type(row[name]) is not bool for name in _FUSION_INPUTS):
            raise _PolicyMatrixMismatch("Invalid fusion input type")
        if type(row["record_supporting_contradiction"]) is not bool:
            raise _PolicyMatrixMismatch("Invalid fusion contradiction type")
        bits = tuple(row[name] for name in _FUSION_INPUTS)
        if not _valid_fusion_input(bits):
            raise _PolicyMatrixMismatch("Invalid fusion input tuple")
        if (row["outcome"], row["record_supporting_contradiction"], row["support_cap"]) != _fusion_outcome(bits):
            raise _PolicyMatrixMismatch("Invalid fusion outcome")
    fusion = _exact_set(fusion, _fusion_cells(), _FUSION_FIELDS, _FUSION_INPUTS,
                        "cross-origin fusion")
    for name, expected, order_key in (
        ("support_level_rules", _SUPPORT, "rule_order"),
        ("dimension_result_rules", _DIMENSION, "precedence"),
        ("global_status_derivation", _GLOBAL, "precedence"),
    ):
        rows = value[name]
        if not isinstance(rows, list) or len(rows) != len(expected):
            _fail(f"Invalid {name} sequence")
        for row, required in zip(rows, expected):
            _shape(row, frozenset(required), name)
            if type(row[order_key]) is not int or row != required:
                _fail(f"Invalid {name} sequence order or value")
    out_of_scope = _exact_set(
        value["recognized_out_of_scope_applicability"],
        ["platform_family", "device_class"], None, None,
        "recognized out-of-scope applicability")
    if value["knowledge_freshness_policy_execution_semantics"] != _FRESHNESS:
        _fail("Invalid freshness execution semantics")
    _shape(value["knowledge_freshness_policy_execution_semantics"],
           frozenset(_FRESHNESS), "freshness execution semantics")
    return make_artifact_content("ClassificationPolicy", {
        **value, **refs,
        "claim_derivation_semantics": deepcopy(_DERIVATIONS),
        "claim_strength_semantics": deepcopy(_STRENGTHS),
        "same_origin_ambiguity_conflict_rules": ambiguity,
        "same_origin_conflict_strength_rules": conflict,
        "cross_origin_fusion_matrix": fusion,
        "support_level_rules": deepcopy(_SUPPORT),
        "dimension_result_rules": deepcopy(_DIMENSION),
        "recognized_out_of_scope_applicability": out_of_scope,
        "global_status_derivation": deepcopy(_GLOBAL),
        "knowledge_freshness_policy_execution_semantics": deepcopy(_FRESHNESS),
    })


def build_initial_classification_policy_v1(
    classification_taxonomy: ArtifactContent, alias_mapping: ArtifactContent,
    evidence_adapter_contract_set: ArtifactContent,
) -> ArtifactContent:
    """Build the timeless policy from the three supplied prerequisite artifacts."""
    payload = {
        "policy_schema_version": 1,
        "classification_taxonomy": ArtifactRef(
            classification_taxonomy.artifact_id, classification_taxonomy.content_sha256).as_dict(),
        "alias_mapping": ArtifactRef(
            alias_mapping.artifact_id, alias_mapping.content_sha256).as_dict(),
        "evidence_adapter_contract_set": ArtifactRef(
            evidence_adapter_contract_set.artifact_id,
            evidence_adapter_contract_set.content_sha256).as_dict(),
        "claim_derivation_semantics": deepcopy(_DERIVATIONS),
        "claim_strength_semantics": deepcopy(_STRENGTHS),
        "same_origin_ambiguity_conflict_rules": deepcopy(_AMBIGUITY),
        "same_origin_conflict_strength_rules": deepcopy(_CONFLICT),
        "cross_origin_fusion_matrix": _fusion_cells(),
        "support_level_rules": deepcopy(_SUPPORT),
        "dimension_result_rules": deepcopy(_DIMENSION),
        "recognized_out_of_scope_applicability": ["platform_family", "device_class"],
        "global_status_derivation": deepcopy(_GLOBAL),
        "knowledge_freshness_policy_execution_semantics": deepcopy(_FRESHNESS),
    }
    return make_classification_policy(payload)


def validate_classification_policy_dependencies(
    policy: ArtifactContent, *, classification_taxonomy: ArtifactContent,
    alias_mapping: ArtifactContent, evidence_adapter_contract_set: ArtifactContent,
) -> bool:
    """Validate supplied exact refs and reusable prerequisite content, not initial IDs."""
    if not isinstance(policy, ArtifactContent) or policy.artifact_type != "ClassificationPolicy":
        _fail("Invalid ClassificationPolicy artifact")
    validated = make_classification_policy(policy.semantic_payload)
    if validated.artifact_id != policy.artifact_id:
        _fail("Noncanonical ClassificationPolicy artifact")
    for field, content, kind, builder in (
        ("classification_taxonomy", classification_taxonomy, "ClassificationTaxonomy",
         make_classification_taxonomy),
        ("alias_mapping", alias_mapping, "AliasMapping", make_alias_mapping),
        ("evidence_adapter_contract_set", evidence_adapter_contract_set,
         "EvidenceAdapterContractSet", make_evidence_adapter_contract_set),
    ):
        ArtifactRef.from_dict(validated.semantic_payload[field]).resolve(content, kind)
        if builder(content.semantic_payload).artifact_id != content.artifact_id:
            _fail(f"Noncanonical {kind} dependency")
    validate_alias_mapping_against_taxonomy(classification_taxonomy, alias_mapping)
    return True
