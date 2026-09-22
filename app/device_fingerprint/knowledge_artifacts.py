"""Closed R14 external-knowledge and K1 DHCP artifact foundations."""

from __future__ import annotations

import re
from typing import Any, Iterable

from .artifact_content import (
    ArtifactContent,
    ArtifactRef,
    canonical_artifact_json,
    canonical_set,
    make_artifact_content,
)
from .models import DeviceFingerprintValidationError
from .p0f_semantics import RUNTIME_CONTRACT, parse_request_signature
from .validation import parse_utc

_SHA256 = re.compile(r"[0-9a-f]{64}")
_GIT_SHA = re.compile(r"[0-9a-f]{40}")
_SOURCE_FAMILY = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
_DIMENSIONS = frozenset({
    "platform_family", "device_class", "manufacturer_family", "model_family",
})
_CLAIM_STRENGTHS = frozenset({"strong", "supporting"})
_FRESHNESS_CAPS = frozenset({"NO_ADDITIONAL_CAP", "strong", "supporting", "NONE"})
_FRESHNESS_STATES = frozenset({"fresh", "stale", "expired"})
_FRESHNESS_STATE_ORDER = {"fresh": 0, "stale": 1, "expired": 2}
_OUTCOME_KINDS = frozenset({
    "CANONICAL_VALUE", "BROAD_UNRESOLVED", "RECOGNIZED_OUT_OF_SCOPE",
    "UNMAPPED", "NO_CLAIM",
})
_MESSAGE_TYPES = frozenset({"discover", "request", "inform", "decline", "release"})
_CLIENT_IDENTIFIER_KINDS = frozenset({"absent", "mac", "opaque"})
_DHCP_FIELDS = (
    "message_type", "parameter_request_list", "option_order", "vendor_class",
    "client_identifier_kind", "maximum_message_size", "rapid_commit_requested",
    "capport_requested", "ipv6_only_preferred_requested", "hostname_present",
)
_FRESHNESS_POLICY_FIELDS = frozenset({
    "knowledge_freshness_policy_version", "source_family_id", "fresh_max_age_ms",
    "stale_max_age_ms", "freshness_state_rules",
})
_FRESHNESS_RULE_FIELDS = frozenset({
    "freshness_state", "claim_eligible", "claim_strength_cap",
    "required_explanation_code", "dimension_overrides",
})
_DIMENSION_OVERRIDE_FIELDS = frozenset({
    "dimension_name", "claim_eligible", "claim_strength_cap",
    "required_explanation_code",
})
_EXTERNAL_PROVENANCE_FIELDS = frozenset({
    "provenance_contract_version", "provenance_kind", "source_artifact_sha256",
    "source_governance_record", "retrieved_at_utc",
    "source_provider_version_metadata", "knowledge_freshness_policy",
    "importer_identity", "importer_version",
})
_INTERNAL_PROVENANCE_FIELDS = frozenset({
    "provenance_contract_version", "provenance_kind", "rule_set_artifact",
    "repository_commit_sha", "repository_tree_sha", "source_artifact_identity",
    "input_schema_compatibility", "taxonomy_compatibility", "rule_set_version",
})
_RECORD_SET_FIELDS = frozenset({
    "record_set_contract_version", "knowledge_slot", "knowledge_provenance", "records",
})
_K1_RECORD_FIELDS = frozenset({
    "record_type", "canonical_record_id", "dhcp_predicates",
    "candidate_taxonomy_refs", "source_record_identity",
})
_K2B_RECORD_FIELDS = frozenset({
    "record_type", "canonical_record_id", "rule_representation",
    "canonical_match_rule", "dimension_claims", "source_character",
    "source_record_identity",
})
_TAXONOMY_OUTCOME_FIELDS = frozenset({
    "dimension_name", "outcome_kind", "canonical_target_id", "broad_taxon_ref",
    "out_of_scope_taxon_ref", "base_claim_strength",
})


def _fail(message: str = "Invalid knowledge artifact") -> None:
    raise DeviceFingerprintValidationError(message)


def _shape(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        _fail(f"Invalid {label} shape")
    return value


def _positive(value: Any, label: str) -> int:
    if type(value) is not int or not 1 <= value <= 9223372036854775807:
        _fail(f"Invalid {label}")
    return value


def _nonnegative(value: Any, label: str) -> int:
    if type(value) is not int or not 0 <= value <= 9223372036854775807:
        _fail(f"Invalid {label}")
    return value


def _int32_positive(value: Any, label: str) -> int:
    if type(value) is not int or not 1 <= value <= 2147483647:
        _fail(f"Invalid {label}")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(f"Invalid {label}")
    canonical_artifact_json(value)
    return value


def _nullable_text(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _text(value, label)


def _artifact_ref(value: Any, expected_type: str) -> dict[str, str]:
    reference = ArtifactRef.from_dict(value)
    if not reference.artifact_id.startswith(f"{expected_type}:v1:sha256:"):
        _fail(f"Invalid {expected_type} reference")
    return reference.as_dict()


def _claim_rule(value: dict[str, Any], *, expired: bool, label: str) -> dict[str, Any]:
    eligible = value["claim_eligible"]
    cap = value["claim_strength_cap"]
    explanation = value["required_explanation_code"]
    if type(eligible) is not bool or cap not in _FRESHNESS_CAPS:
        _fail(f"Invalid {label}")
    _nullable_text(explanation, f"{label} explanation")
    if (not eligible and cap != "NONE") or (eligible and cap == "NONE"):
        _fail(f"Invalid {label} claim eligibility")
    if expired and (
        eligible or cap != "NONE" or explanation != "knowledge_source_expired"
    ):
        _fail("Invalid expired knowledge behavior")
    return value


def _canonical_freshness_rules(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply the frozen R14 enum order without changing generic SET semantics."""
    return sorted(
        rules,
        key=lambda rule: (
            _FRESHNESS_STATE_ORDER[rule["freshness_state"]],
            canonical_artifact_json(rule),
        ),
    )


def make_knowledge_freshness_policy(payload: dict[str, Any]) -> ArtifactContent:
    """Validate and materialize exact R14 KnowledgeFreshnessPolicy V1."""
    value = _shape(payload, _FRESHNESS_POLICY_FIELDS, "knowledge freshness policy")
    _int32_positive(value["knowledge_freshness_policy_version"], "policy version")
    family = value["source_family_id"]
    if not isinstance(family, str) or _SOURCE_FAMILY.fullmatch(family) is None:
        _fail("Invalid source family")
    fresh = _nonnegative(value["fresh_max_age_ms"], "fresh maximum age")
    stale = _nonnegative(value["stale_max_age_ms"], "stale maximum age")
    if fresh > stale:
        _fail("Invalid knowledge freshness range")
    rules = value["freshness_state_rules"]
    if not isinstance(rules, list) or len(rules) != 3:
        _fail("Invalid freshness state rule set")
    seen_states: set[str] = set()
    normalized_rules = []
    for raw_rule in rules:
        rule = dict(_shape(raw_rule, _FRESHNESS_RULE_FIELDS, "freshness state rule"))
        state = rule["freshness_state"]
        if state not in _FRESHNESS_STATES or state in seen_states:
            _fail("Invalid freshness state rule identity")
        seen_states.add(state)
        _claim_rule(rule, expired=state == "expired", label="freshness state rule")
        overrides = rule["dimension_overrides"]
        if not isinstance(overrides, list):
            _fail("Invalid freshness dimension overrides")
        seen_dimensions: set[str] = set()
        normalized_overrides = []
        for raw_override in overrides:
            override = dict(_shape(
                raw_override, _DIMENSION_OVERRIDE_FIELDS, "freshness dimension override",
            ))
            dimension = override["dimension_name"]
            if dimension not in _DIMENSIONS or dimension in seen_dimensions:
                _fail("Invalid freshness dimension override identity")
            seen_dimensions.add(dimension)
            _claim_rule(
                override,
                expired=state == "expired",
                label="freshness dimension override",
            )
            normalized_overrides.append(override)
        rule["dimension_overrides"] = canonical_set(
            normalized_overrides, lambda row: row["dimension_name"],
        )
        normalized_rules.append(rule)
    if seen_states != _FRESHNESS_STATES:
        _fail("Incomplete freshness state rule set")
    normalized_rules = _canonical_freshness_rules(normalized_rules)
    return make_artifact_content("KnowledgeFreshnessPolicy", {
        **value, "freshness_state_rules": normalized_rules,
    })


def make_external_knowledge_provenance_manifest(
    payload: dict[str, Any],
) -> ArtifactContent:
    """Validate the exact external arm of R14 KnowledgeProvenanceManifest V1."""
    value = _shape(payload, _EXTERNAL_PROVENANCE_FIELDS, "external provenance")
    _int32_positive(value["provenance_contract_version"], "provenance version")
    if value["provenance_kind"] != "external":
        _fail("Invalid external provenance kind")
    digest = value["source_artifact_sha256"]
    if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
        _fail("Invalid source artifact digest")
    parse_utc(value["retrieved_at_utc"])
    for field in (
        "source_provider_version_metadata", "importer_identity", "importer_version",
    ):
        _text(value[field], field)
    governance = _artifact_ref(value["source_governance_record"], "SourceGovernanceRecord")
    freshness = _artifact_ref(
        value["knowledge_freshness_policy"], "KnowledgeFreshnessPolicy",
    )
    return make_artifact_content("KnowledgeProvenanceManifest", {
        **value,
        "source_governance_record": governance,
        "knowledge_freshness_policy": freshness,
    })


def make_internal_knowledge_provenance_manifest(
    payload: dict[str, Any],
) -> ArtifactContent:
    """Validate the exact internal arm of R14 KnowledgeProvenanceManifest V1."""
    value = _shape(payload, _INTERNAL_PROVENANCE_FIELDS, "internal provenance")
    _int32_positive(value["provenance_contract_version"], "provenance version")
    if value["provenance_kind"] != "internal":
        _fail("Invalid internal provenance kind")
    rule_ref = ArtifactRef.from_dict(value["rule_set_artifact"]).as_dict()
    taxonomy_ref = _artifact_ref(value["taxonomy_compatibility"], "ClassificationTaxonomy")
    commit = value["repository_commit_sha"]
    tree = value["repository_tree_sha"]
    source = value["source_artifact_identity"]
    if commit is not None and (not isinstance(commit, str) or _GIT_SHA.fullmatch(commit) is None):
        _fail("Invalid repository commit SHA")
    if tree is not None and (not isinstance(tree, str) or _GIT_SHA.fullmatch(tree) is None):
        _fail("Invalid repository tree SHA")
    if source is not None and (not isinstance(source, str) or _SHA256.fullmatch(source) is None):
        _fail("Invalid source artifact identity")
    if not ((commit is not None and tree is not None) != (source is not None)):
        _fail("Invalid internal provenance identity")
    _text(value["rule_set_version"], "rule set version")
    rows = value["input_schema_compatibility"]
    if not isinstance(rows, list) or not rows:
        _fail("Invalid input schema compatibility")
    normalized = []
    for raw in rows:
        row = _shape(raw, frozenset({"source_kind", "feature_schema_version"}),
                     "schema compatibility")
        normalized.append({
            "source_kind": _text(row["source_kind"], "source kind"),
            "feature_schema_version": _int32_positive(
                row["feature_schema_version"], "feature schema version",
            ),
        })
    compatibility = canonical_set(
        normalized, lambda row: (row["source_kind"], row["feature_schema_version"]),
    )
    return make_artifact_content("KnowledgeProvenanceManifest", {
        **value,
        "rule_set_artifact": rule_ref,
        "taxonomy_compatibility": taxonomy_ref,
        "input_schema_compatibility": compatibility,
    })


def _taxonomy_primary_key(value: dict[str, Any]) -> str:
    return canonical_artifact_json([
        value["dimension_name"], value["outcome_kind"],
        value["canonical_target_id"], value["broad_taxon_ref"],
        value["out_of_scope_taxon_ref"], value["base_claim_strength"],
    ]).decode("utf-8")


def _taxonomy_outcome(raw: Any) -> dict[str, Any]:
    value = dict(_shape(raw, _TAXONOMY_OUTCOME_FIELDS, "taxonomy claim outcome"))
    dimension = value["dimension_name"]
    kind = value["outcome_kind"]
    canonical = _nullable_text(value["canonical_target_id"], "canonical taxonomy target")
    broad = _nullable_text(value["broad_taxon_ref"], "broad taxonomy reference")
    outside = _nullable_text(value["out_of_scope_taxon_ref"], "out-of-scope taxonomy reference")
    strength = value["base_claim_strength"]
    if dimension not in _DIMENSIONS or kind not in _OUTCOME_KINDS:
        _fail("Invalid taxonomy claim outcome")
    if strength is not None and strength not in _CLAIM_STRENGTHS:
        _fail("Invalid taxonomy claim strength")
    if kind == "CANONICAL_VALUE":
        valid = canonical is not None and broad is None and outside is None and strength is not None
    elif kind == "RECOGNIZED_OUT_OF_SCOPE":
        valid = (
            dimension in {"platform_family", "device_class"}
            and outside is not None and canonical is None and broad is None
            and strength is not None
        )
    elif kind == "BROAD_UNRESOLVED":
        valid = broad is not None and canonical is None and outside is None and strength is None
    else:
        valid = canonical is None and broad is None and outside is None and strength is None
    if not valid:
        _fail("Invalid taxonomy claim invariant")
    return value


def _scalar_predicate(raw: Any, validator: Any, label: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("mode") not in {"ANY", "EXACT_VALUE"}:
        _fail(f"Invalid {label} predicate")
    mode = raw["mode"]
    fields = {"mode"} if mode == "ANY" else {"mode", "value"}
    if set(raw) != fields:
        _fail(f"Invalid {label} predicate shape")
    if mode == "EXACT_VALUE":
        validator(raw["value"])
    return dict(raw)


def _nullable_scalar_predicate(raw: Any, validator: Any, label: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("mode") not in {
        "ANY", "EXACT_NULL", "EXACT_VALUE",
    }:
        _fail(f"Invalid {label} predicate")
    mode = raw["mode"]
    fields = {"mode", "value"} if mode == "EXACT_VALUE" else {"mode"}
    if set(raw) != fields:
        _fail(f"Invalid {label} predicate shape")
    if mode == "EXACT_VALUE":
        validator(raw["value"])
    return dict(raw)


def _sequence_predicate(raw: Any, label: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("mode") not in {"ANY", "EXACT_SEQUENCE"}:
        _fail(f"Invalid {label} predicate")
    mode = raw["mode"]
    fields = {"mode"} if mode == "ANY" else {"mode", "value"}
    if set(raw) != fields:
        _fail(f"Invalid {label} predicate shape")
    if mode == "EXACT_SEQUENCE":
        _byte_sequence(raw["value"], label)
    return dict(raw)


def _enum_validator(allowed: frozenset[Any], label: str):
    def validate(value: Any) -> None:
        if value not in allowed or type(value) not in {str, bool}:
            _fail(f"Invalid {label}")
    return validate


def _printable_ascii(value: Any) -> None:
    if (not isinstance(value, str) or not 1 <= len(value) <= 128
            or any(not 0x20 <= ord(character) <= 0x7E for character in value)):
        _fail("Invalid printable ASCII value")


def _message_size(value: Any) -> None:
    if type(value) is not int or not 576 <= value <= 65535:
        _fail("Invalid maximum message size")


def _byte_sequence(value: Any, label: str) -> None:
    if (not isinstance(value, list) or len(value) > 64
            or any(type(item) is not int or not 0 <= item <= 255 for item in value)):
        _fail(f"Invalid {label} sequence")


def validate_dhcp_v1_predicate_set(raw: Any) -> dict[str, Any]:
    """Validate the complete closed ten-field R14 DhcpV1PredicateSet."""
    value = _shape(raw, frozenset(_DHCP_FIELDS), "DHCP predicate set")
    return {
        "message_type": _scalar_predicate(
            value["message_type"], _enum_validator(_MESSAGE_TYPES, "message type"),
            "message type",
        ),
        "parameter_request_list": _sequence_predicate(
            value["parameter_request_list"], "parameter request list",
        ),
        "option_order": _sequence_predicate(value["option_order"], "option order"),
        "vendor_class": _nullable_scalar_predicate(
            value["vendor_class"], _printable_ascii, "vendor class",
        ),
        "client_identifier_kind": _scalar_predicate(
            value["client_identifier_kind"],
            _enum_validator(_CLIENT_IDENTIFIER_KINDS, "client identifier kind"),
            "client identifier kind",
        ),
        "maximum_message_size": _nullable_scalar_predicate(
            value["maximum_message_size"], _message_size, "maximum message size",
        ),
        "rapid_commit_requested": _scalar_predicate(
            value["rapid_commit_requested"], _enum_validator(frozenset({True, False}), "boolean"),
            "rapid commit",
        ),
        "capport_requested": _scalar_predicate(
            value["capport_requested"], _enum_validator(frozenset({True, False}), "boolean"),
            "CAPPORT",
        ),
        "ipv6_only_preferred_requested": _scalar_predicate(
            value["ipv6_only_preferred_requested"],
            _enum_validator(frozenset({True, False}), "boolean"),
            "IPv6-only preferred",
        ),
        "hostname_present": _scalar_predicate(
            value["hostname_present"], _enum_validator(frozenset({True, False}), "boolean"),
            "hostname present",
        ),
    }


def _k1_record(raw: Any) -> dict[str, Any]:
    value = dict(_shape(raw, _K1_RECORD_FIELDS, "K1 DHCP record"))
    if value["record_type"] != "K1_DHCP":
        _fail("Invalid K1 record type")
    _text(value["canonical_record_id"], "canonical record identity")
    _text(value["source_record_identity"], "source record identity")
    value["dhcp_predicates"] = validate_dhcp_v1_predicate_set(value["dhcp_predicates"])
    outcomes = value["candidate_taxonomy_refs"]
    if not isinstance(outcomes, list):
        _fail("Invalid candidate taxonomy set")
    value["candidate_taxonomy_refs"] = canonical_set(
        [_taxonomy_outcome(outcome) for outcome in outcomes], _taxonomy_primary_key,
    )
    return value


def make_canonical_k1_record_set(payload: dict[str, Any]) -> ArtifactContent:
    """Validate and materialize exact R14 CanonicalKnowledgeRecordSet(K1)."""
    value = _shape(payload, _RECORD_SET_FIELDS, "canonical K1 record set")
    _int32_positive(value["record_set_contract_version"], "record set version")
    if value["knowledge_slot"] != "K1":
        _fail("Invalid K1 knowledge slot")
    provenance = _artifact_ref(
        value["knowledge_provenance"], "KnowledgeProvenanceManifest",
    )
    records = value["records"]
    if not isinstance(records, list):
        _fail("Invalid K1 records")
    normalized_records = []
    identities: set[tuple[str, str]] = set()
    for raw_record in records:
        record = _k1_record(raw_record)
        identity = (record["record_type"], record["canonical_record_id"])
        if identity in identities:
            _fail("Duplicate canonical K1 record identity")
        identities.add(identity)
        normalized_records.append(record)
    normalized_records = canonical_set(
        normalized_records,
        lambda record: (record["record_type"], record["canonical_record_id"]),
    )
    return make_artifact_content("CanonicalKnowledgeRecordSet", {
        **value,
        "knowledge_provenance": provenance,
        "records": normalized_records,
    })


def canonical_k2b_match_rule(text: str) -> str:
    """Validate a source token with K2A's pinned request grammar and round trip."""
    if not isinstance(text, str) or not text:
        _fail("Invalid K2B match rule")
    canonical = text.strip()
    if not canonical:
        _fail("Invalid K2B match rule")
    try:
        first = parse_request_signature(
            canonical, signature_id="k2b-rule", generic=False, userland=False,
        )
        second = parse_request_signature(
            canonical.strip(), signature_id="k2b-rule", generic=False, userland=False,
        )
    except ValueError as exc:
        raise DeviceFingerprintValidationError("Invalid K2B match rule") from exc
    if first != second or canonical.strip() != canonical:
        _fail("K2B match rule does not round trip")
    return canonical


def _k2b_record(raw: Any) -> dict[str, Any]:
    value = dict(_shape(raw, _K2B_RECORD_FIELDS, "K2B TCP record"))
    if value["record_type"] != "K2B_TCP":
        _fail("Invalid K2B record type")
    _text(value["canonical_record_id"], "canonical record identity")
    _text(value["source_record_identity"], "source record identity")
    if value["rule_representation"] != RUNTIME_CONTRACT:
        _fail("Invalid K2B rule representation")
    rule = value["canonical_match_rule"]
    if canonical_k2b_match_rule(rule) != rule:
        _fail("Noncanonical K2B match rule")
    if value["source_character"] not in {"current", "legacy"}:
        _fail("Invalid K2B source character")
    claims = value["dimension_claims"]
    if not isinstance(claims, list):
        _fail("Invalid K2B dimension claims")
    value["dimension_claims"] = canonical_set(
        [_taxonomy_outcome(claim) for claim in claims], _taxonomy_primary_key,
    )
    return value


def make_canonical_k2b_record_set(payload: dict[str, Any]) -> ArtifactContent:
    """Validate and materialize R14 CanonicalKnowledgeRecordSet(K2B)."""
    value = _shape(payload, _RECORD_SET_FIELDS, "canonical K2B record set")
    _int32_positive(value["record_set_contract_version"], "record set version")
    if value["knowledge_slot"] != "K2B":
        _fail("Invalid K2B knowledge slot")
    provenance = _artifact_ref(
        value["knowledge_provenance"], "KnowledgeProvenanceManifest",
    )
    records = value["records"]
    if not isinstance(records, list):
        _fail("Invalid K2B records")
    normalized_records = []
    identities: set[tuple[str, str]] = set()
    for raw_record in records:
        record = _k2b_record(raw_record)
        identity = (record["record_type"], record["canonical_record_id"])
        if identity in identities:
            _fail("Duplicate canonical K2B record identity")
        identities.add(identity)
        normalized_records.append(record)
    normalized_records = canonical_set(
        normalized_records,
        lambda record: (record["record_type"], record["canonical_record_id"]),
    )
    return make_artifact_content("CanonicalKnowledgeRecordSet", {
        **value, "knowledge_provenance": provenance, "records": normalized_records,
    })


def _validated_dhcp_evidence(raw: Any) -> dict[str, Any]:
    value = _shape(raw, frozenset(_DHCP_FIELDS), "DHCP evidence projection")
    if value["message_type"] not in _MESSAGE_TYPES:
        _fail("Invalid DHCP evidence message type")
    _byte_sequence(value["parameter_request_list"], "parameter request list")
    _byte_sequence(value["option_order"], "option order")
    if value["vendor_class"] is not None:
        _printable_ascii(value["vendor_class"])
    if value["client_identifier_kind"] not in _CLIENT_IDENTIFIER_KINDS:
        _fail("Invalid DHCP evidence client identifier kind")
    if value["maximum_message_size"] is not None:
        _message_size(value["maximum_message_size"])
    for field in (
        "rapid_commit_requested", "capport_requested",
        "ipv6_only_preferred_requested", "hostname_present",
    ):
        if type(value[field]) is not bool:
            _fail("Invalid DHCP evidence boolean")
    return value


def _predicate_matches(predicate: dict[str, Any], observed: Any) -> bool:
    mode = predicate["mode"]
    if mode == "ANY":
        return True
    if mode == "EXACT_NULL":
        return observed is None
    return predicate["value"] == observed


def match_k1_records(
    record_set: ArtifactContent,
    dhcp_evidence: dict[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Enumerate every compatible K1 record without ranking or scoring."""
    if not isinstance(record_set, ArtifactContent) or record_set.artifact_type != (
        "CanonicalKnowledgeRecordSet"
    ):
        _fail("Invalid K1 record-set artifact")
    payload = record_set.semantic_payload
    rematerialized = make_canonical_k1_record_set(payload)
    if rematerialized.artifact_id != record_set.artifact_id:
        _fail("Invalid K1 record-set identity")
    observed = _validated_dhcp_evidence(dhcp_evidence)
    matches = []
    for record in payload["records"]:
        predicates = record["dhcp_predicates"]
        if all(_predicate_matches(predicates[field], observed[field]) for field in _DHCP_FIELDS):
            matches.append(record)
    return tuple(matches)


def project_k1_candidate_dimensions(
    candidates: Iterable[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Project complete candidates per dimension without collapsing disagreement."""
    materialized = list(candidates)
    result: dict[str, dict[str, Any]] = {}
    for dimension in sorted(_DIMENSIONS):
        values = sorted({
            outcome["canonical_target_id"]
            for candidate in materialized
            for outcome in candidate["candidate_taxonomy_refs"]
            if outcome["dimension_name"] == dimension
            and outcome["outcome_kind"] == "CANONICAL_VALUE"
        })
        if not materialized:
            status = "empty_candidate_set"
        elif len(values) == 1:
            status = "resolved"
        elif len(values) > 1:
            status = "ambiguous"
        else:
            status = "no_canonical_claim"
        result[dimension] = {"status": status, "canonical_values": values}
    return result
