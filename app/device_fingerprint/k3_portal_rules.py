"""Immutable R14 K3 rules over already-normalized portal evidence."""

from __future__ import annotations

import unicodedata
from typing import Any, Mapping

from .artifact_content import ArtifactContent, canonical_artifact_json, canonical_set, make_artifact_content
from .models import DeviceFingerprintValidationError
from .knowledge_artifacts import make_internal_knowledge_provenance_manifest
from .portal_schemas import (
    PORTAL_HEADER_KEYS, PORTAL_HEADER_V2_KEYS,
    validate_portal_headers_v1, validate_portal_headers_v2,
)

_DIMENSIONS = ("platform_family", "device_class", "manufacturer_family", "model_family")
_PLATFORMS = ("android", "ios", "windows", "macos", "chromeos", "linux")
_RULE_FIELDS = frozenset({
    "rule_id", "dimension_name", "input_predicates", "outcome_kind",
    "outcome_id_or_ref", "claim_derivation", "base_claim_strength", "explanation_code",
})
_PREDICATE_FIELDS = frozenset({"field_name", "operator", "value", "values"})
_VECTOR_FIELDS = frozenset({
    "test_vector_id", "feature_schema_version", "normalized_input",
    "expected_rule_ids", "expected_dimension_outcomes",
})
_RULE_SET_FIELDS = frozenset({
    "k3_rule_set_version", "portal_schema_family", "admitted_feature_schema_versions",
    "rules", "test_vectors",
})
_RAW_FIELDS = frozenset({
    "user_agent", "ua", "raw_user_agent", "sec_ch_ua", "raw_headers", "headers",
    "http_headers", "client_hints", "raw_client_hints",
})
_SCHEMA_FIELDS = {1: PORTAL_HEADER_KEYS, 2: PORTAL_HEADER_V2_KEYS}


def _fail(message: str) -> None:
    raise DeviceFingerprintValidationError(message)


def _shape(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        _fail(f"Invalid {label} shape")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or unicodedata.normalize("NFC", value) != value:
        _fail(f"Invalid {label}")
    return value


def _scalar(value: Any, *, nullable: bool = False) -> Any:
    if value is None and nullable:
        return None
    if type(value) is bool:
        return value
    if type(value) is int and -(2**63) <= value <= 2**63 - 1:
        return value
    if isinstance(value, str) and unicodedata.normalize("NFC", value) == value:
        return value
    _fail("Invalid K3 scalar")


def _predicate(raw: Any) -> dict[str, Any]:
    value = dict(_shape(raw, _PREDICATE_FIELDS, "K3 predicate"))
    field = _text(value["field_name"], "K3 predicate field")
    if field in _RAW_FIELDS or not any(field in fields for fields in _SCHEMA_FIELDS.values()):
        _fail("Unknown or raw K3 predicate field")
    operator = value["operator"]
    if not isinstance(operator, str) or operator not in {"EQ", "IS_TRUE", "IS_FALSE", "IS_NULL", "IS_NOT_NULL", "IN"}:
        _fail("Invalid K3 predicate operator")
    if not isinstance(value["values"], list):
        _fail("Invalid K3 predicate values")
    if operator == "EQ":
        if value["value"] is None or value["values"]:
            _fail("Invalid EQ predicate")
        _scalar(value["value"])
    elif operator == "IN":
        if value["value"] is not None or not value["values"]:
            _fail("Invalid IN predicate")
        value["values"] = canonical_set(
            [_scalar(item) for item in value["values"]],
            lambda item: (type(item).__name__, item),
        )
    elif value["value"] is not None or value["values"]:
        _fail("Invalid unary predicate")
    return value


def _rule(raw: Any, versions: list[int]) -> dict[str, Any]:
    value = dict(_shape(raw, _RULE_FIELDS, "K3 rule"))
    _text(value["rule_id"], "K3 rule ID")
    _text(value["explanation_code"], "K3 explanation code")
    if not isinstance(value["dimension_name"], str) or value["dimension_name"] not in _DIMENSIONS:
        _fail("Invalid K3 dimension")
    if not isinstance(value["claim_derivation"], str) or value["claim_derivation"] not in {"declared", "deterministic_mapping"}:
        _fail("Invalid K3 claim derivation")
    kind = value["outcome_kind"]
    target = value["outcome_id_or_ref"]
    strength = value["base_claim_strength"]
    if not isinstance(kind, str) or kind not in {"CANONICAL_VALUE", "BROAD_UNRESOLVED", "RECOGNIZED_OUT_OF_SCOPE", "NO_CLAIM"}:
        _fail("Invalid K3 outcome kind")
    if kind == "CANONICAL_VALUE" or kind == "RECOGNIZED_OUT_OF_SCOPE":
        _text(target, "K3 outcome target")
        if not isinstance(strength, str) or strength not in {"strong", "supporting"}:
            _fail("Invalid K3 claim strength")
        if kind == "RECOGNIZED_OUT_OF_SCOPE" and value["dimension_name"] not in {"platform_family", "device_class"}:
            _fail("Invalid out-of-scope dimension")
    elif kind == "BROAD_UNRESOLVED":
        _text(target, "K3 broad target")
        if strength is not None:
            _fail("Invalid broad claim strength")
    elif target is not None or strength is not None:
        _fail("Invalid no-claim outcome")
    if strength == "strong":
        _fail("K3 V1 cannot emit a strong claim")
    raw_predicates = value["input_predicates"]
    if not isinstance(raw_predicates, list) or not raw_predicates:
        _fail("Invalid K3 predicate set")
    predicates = [_predicate(item) for item in raw_predicates]
    fields = {item["field_name"] for item in predicates}
    if not any(fields <= _SCHEMA_FIELDS[version] for version in versions):
        _fail("K3 rule spans incompatible portal schemas")
    value["input_predicates"] = canonical_set(predicates, lambda item: (
        item["field_name"], item["operator"],
        canonical_artifact_json(item["value"]).decode("utf-8"),
        canonical_artifact_json(item["values"]).decode("utf-8"),
    ))
    return value


def _validated_input(version: Any, normalized_input: Any) -> dict[str, Any]:
    if type(version) is not int or version not in _SCHEMA_FIELDS:
        _fail("Unsupported K3 portal schema version")
    if not isinstance(normalized_input, Mapping):
        _fail("Invalid K3 normalized input")
    for key, value in normalized_input.items():
        _text(key, "normalized field name")
        if isinstance(value, list):
            for item in value:
                _scalar(item, nullable=True)
        else:
            _scalar(value, nullable=True)
    validator = validate_portal_headers_v1 if version == 1 else validate_portal_headers_v2
    return dict(validator(normalized_input))


def _equal(first: Any, second: Any) -> bool:
    return type(first) is type(second) and first == second


def _matches(predicate: dict[str, Any], row: dict[str, Any]) -> bool:
    actual = row[predicate["field_name"]]
    operator = predicate["operator"]
    if operator == "EQ":
        return _equal(actual, predicate["value"])
    if operator == "IN":
        return any(_equal(actual, item) for item in predicate["values"])
    if operator == "IS_TRUE":
        return actual is True
    if operator == "IS_FALSE":
        return actual is False
    if operator == "IS_NULL":
        return actual is None
    return actual is not None


def _evaluate(rules: list[dict[str, Any]], version: int, normalized_input: Any) -> dict[str, Any]:
    row = _validated_input(version, normalized_input)
    matches = [rule for rule in rules if all(
        predicate["field_name"] in row and _matches(predicate, row)
        for predicate in rule["input_predicates"]
    )]
    outcomes: dict[str, str | None] = {dimension: None for dimension in _DIMENSIONS}
    for dimension in _DIMENSIONS:
        concrete = {rule["outcome_id_or_ref"] for rule in matches
                    if rule["dimension_name"] == dimension
                    and rule["outcome_kind"] == "CANONICAL_VALUE"}
        if len(concrete) == 1:
            outcomes[dimension] = next(iter(concrete))
    return {"matched_rule_ids": [rule["rule_id"] for rule in matches],
            "dimension_outcomes": outcomes}


def evaluate_k3_rules(
    rule_set: ArtifactContent, feature_schema_version: int, normalized_input: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate one admitted normalized portal observation without source priority."""
    if not isinstance(rule_set, ArtifactContent) or rule_set.artifact_type != "K3PortalRuleSet":
        _fail("Invalid K3 rule-set artifact")
    payload = rule_set.semantic_payload
    if feature_schema_version not in payload["admitted_feature_schema_versions"]:
        _fail("Unadmitted K3 portal schema version")
    return _evaluate(payload["rules"], feature_schema_version, normalized_input)


def build_k3_internal_provenance(
    rule_set_artifact: ArtifactContent, *, repository_commit_sha: str,
    repository_tree_sha: str, taxonomy_compatibility: dict[str, str],
) -> ArtifactContent:
    """Bind K3 to caller-supplied final repository and taxonomy identities."""
    if not isinstance(rule_set_artifact, ArtifactContent) or rule_set_artifact.artifact_type != "K3PortalRuleSet":
        _fail("Invalid K3 rule-set artifact")
    rule_set = rule_set_artifact.semantic_payload
    if rule_set["portal_schema_family"] != "portal_headers" or rule_set["admitted_feature_schema_versions"] != [1, 2]:
        _fail("Invalid K3 schema compatibility")
    return make_internal_knowledge_provenance_manifest({
        "provenance_contract_version": 1,
        "provenance_kind": "internal",
        "rule_set_artifact": {
            "artifact_id": rule_set_artifact.artifact_id,
            "content_sha256": rule_set_artifact.content_sha256,
        },
        "repository_commit_sha": repository_commit_sha,
        "repository_tree_sha": repository_tree_sha,
        "source_artifact_identity": None,
        "input_schema_compatibility": [
            {"source_kind": "portal_headers", "feature_schema_version": version}
            for version in (1, 2)
        ],
        "taxonomy_compatibility": taxonomy_compatibility,
        "rule_set_version": rule_set["k3_rule_set_version"],
    })


def make_k3_portal_rule_set(payload: dict[str, Any]) -> ArtifactContent:
    """Validate closed R14 K3PortalRuleSet V1 and every retained vector."""
    value = _shape(payload, _RULE_SET_FIELDS, "K3 rule set")
    if value["k3_rule_set_version"] != "k3_portal_rules_v1":
        _fail("Invalid K3 rule-set version")
    if value["portal_schema_family"] != "portal_headers":
        _fail("Invalid K3 portal schema family")
    versions = value["admitted_feature_schema_versions"]
    if not isinstance(versions, list) or not versions or any(type(v) is not int or v not in _SCHEMA_FIELDS for v in versions):
        _fail("Invalid admitted K3 schema versions")
    versions = canonical_set(versions, lambda item: item)
    if versions != [1, 2]:
        _fail("Incomplete K3 V1 portal schema compatibility")
    raw_rules = value["rules"]
    if not isinstance(raw_rules, list) or not raw_rules:
        _fail("Invalid K3 rules")
    rules = canonical_set([_rule(rule, versions) for rule in raw_rules], lambda rule: rule["rule_id"])
    if len({rule["rule_id"] for rule in rules}) != len(rules):
        _fail("Duplicate K3 rule ID")
    raw_vectors = value["test_vectors"]
    if not isinstance(raw_vectors, list):
        _fail("Invalid K3 vectors")
    vectors = []
    for raw in raw_vectors:
        vector = dict(_shape(raw, _VECTOR_FIELDS, "K3 test vector"))
        _text(vector["test_vector_id"], "K3 vector ID")
        version = vector["feature_schema_version"]
        if type(version) is not int or version not in versions:
            _fail("Invalid K3 vector schema version")
        vector["normalized_input"] = _validated_input(version, vector["normalized_input"])
        expected = vector["expected_rule_ids"]
        if not isinstance(expected, list) or any(not isinstance(item, str) or not item for item in expected):
            _fail("Invalid K3 expected rule IDs")
        vector["expected_rule_ids"] = canonical_set(expected, lambda item: item)
        outcomes = vector["expected_dimension_outcomes"]
        if not isinstance(outcomes, dict) or set(outcomes) != set(_DIMENSIONS):
            _fail("Invalid K3 expected dimension outcomes")
        for result in outcomes.values():
            if result is not None:
                _text(result, "K3 expected outcome")
        actual = _evaluate(rules, version, vector["normalized_input"])
        if actual["matched_rule_ids"] != vector["expected_rule_ids"] or actual["dimension_outcomes"] != outcomes:
            _fail("K3 test vector does not match rules")
        vectors.append(vector)
    vectors = canonical_set(vectors, lambda vector: vector["test_vector_id"])
    if len({vector["test_vector_id"] for vector in vectors}) != len(vectors):
        _fail("Duplicate K3 vector ID")
    return make_artifact_content("K3PortalRuleSet", {
        **value, "admitted_feature_schema_versions": versions,
        "rules": rules, "test_vectors": vectors,
    })


def _predicate_row(field: str, operator: str, value: Any = None) -> dict[str, Any]:
    return {"field_name": field, "operator": operator, "value": value, "values": []}


def _portal_v1(**changes: Any) -> dict[str, Any]:
    row = dict.fromkeys(PORTAL_HEADER_KEYS)
    row.update({key: False for key in (
        "ua_present", "sec_ch_ua_present", "sec_ch_ua_platform_present", "sec_ch_ua_mobile_present",
    )})
    row.update(changes)
    return row


def _portal_v2(**changes: Any) -> dict[str, Any]:
    row = dict.fromkeys(PORTAL_HEADER_V2_KEYS)
    row.update(changes)
    return row


def build_k3_portal_rule_set_v1() -> ArtifactContent:
    """Build the 13 conservative K3 rules and their synthetic proof vectors."""
    rules = []
    vectors = []
    for platform in _PLATFORMS:
        for source, presence, derivation, explanation in (
            ("sec_ch_ua_platform", "sec_ch_ua_platform_present", "declared", "portal_platform_declared"),
            ("user_agent", "ua_present", "deterministic_mapping", "portal_platform_user_agent_mapping"),
        ):
            rule_id = f"k3.portal.platform.{platform}.{source}.v1"
            rules.append({
                "rule_id": rule_id, "dimension_name": "platform_family",
                "input_predicates": [
                    _predicate_row("platform_family", "EQ", platform),
                    _predicate_row("platform_source", "EQ", source),
                    _predicate_row(presence, "IS_TRUE"),
                ],
                "outcome_kind": "CANONICAL_VALUE", "outcome_id_or_ref": platform,
                "claim_derivation": derivation, "base_claim_strength": "supporting",
                "explanation_code": explanation,
            })
            sample = _portal_v1(platform_family=platform, platform_source=source)
            sample[presence] = True
            vectors.append(_vector(f"k3.vector.platform.{platform}.{source}.v1", 1, sample,
                                   [rule_id], platform_family=platform))
    tablet_id = "k3.portal.device_class.tablet.sec_ch_ua_form_factors.v1"
    rules.append({
        "rule_id": tablet_id, "dimension_name": "device_class",
        "input_predicates": [
            _predicate_row("form_factor_tablet", "IS_TRUE"),
            _predicate_row("form_factor_desktop", "IS_FALSE"),
            _predicate_row("form_factors_source", "EQ", "sec_ch_ua_form_factors"),
        ],
        "outcome_kind": "CANONICAL_VALUE", "outcome_id_or_ref": "tablet",
        "claim_derivation": "declared", "base_claim_strength": "supporting",
        "explanation_code": "portal_tablet_form_factor_declared",
    })
    vectors.extend([
        _vector("k3.vector.mobile_boolean.no_class.v1", 1, _portal_v1(
            mobile_boolean=True, mobile_source="sec_ch_ua_mobile", sec_ch_ua_mobile_present=True,
        ), []),
        _vector("k3.vector.android_webview.no_class.v1", 1, _portal_v1(
            browser_runtime_family="android_webview", runtime_source="sec_ch_ua", sec_ch_ua_present=True,
        ), []),
        _vector("k3.vector.captive_helper.no_class.v1", 1, _portal_v1(
            webview_or_captive_context="captive_helper", context_source="user_agent", ua_present=True,
        ), []),
        _vector("k3.vector.unknown_model_ua.no_claim.v1", 1, _portal_v1(
            model_family="Example Model", model_source="user_agent", ua_present=True,
        ), []),
        _vector("k3.vector.unknown_model_ch.no_claim.v2", 2, _portal_v2(
            model_family="Example Model", model_source="sec_ch_ua_model",
        ), []),
        _vector("k3.vector.tablet.declared.v2", 2, _portal_v2(
            form_factor_mobile=False, form_factor_tablet=True, form_factor_desktop=False,
            form_factors_source="sec_ch_ua_form_factors",
        ), [tablet_id], device_class="tablet"),
        _vector("k3.vector.tablet_desktop.no_class.v2", 2, _portal_v2(
            form_factor_mobile=False, form_factor_tablet=True, form_factor_desktop=True,
            form_factors_source="sec_ch_ua_form_factors",
        ), []),
        _vector("k3.vector.mobile_form_factor.no_class.v2", 2, _portal_v2(
            form_factor_mobile=True, form_factor_tablet=False, form_factor_desktop=False,
            form_factors_source="sec_ch_ua_form_factors",
        ), []),
        _vector("k3.vector.desktop_form_factor.no_class.v2", 2, _portal_v2(
            form_factor_mobile=False, form_factor_tablet=False, form_factor_desktop=True,
            form_factors_source="sec_ch_ua_form_factors",
        ), []),
    ])
    return make_k3_portal_rule_set({
        "k3_rule_set_version": "k3_portal_rules_v1", "portal_schema_family": "portal_headers",
        "admitted_feature_schema_versions": [1, 2], "rules": rules, "test_vectors": vectors,
    })


def _vector(vector_id: str, version: int, sample: dict[str, Any],
            rule_ids: list[str], **outcomes: str) -> dict[str, Any]:
    return {
        "test_vector_id": vector_id, "feature_schema_version": version,
        "normalized_input": sample, "expected_rule_ids": rule_ids,
        "expected_dimension_outcomes": {dimension: outcomes.get(dimension) for dimension in _DIMENSIONS},
    }
