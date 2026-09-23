"""Deterministic F-E6 taxonomy/alias proofs and formal gate execution."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from .artifact_content import ArtifactContent, ArtifactRef
from .foundation_gate_artifacts import make_gate_result_manifest
from .models import DeviceFingerprintValidationError
from .taxonomy_artifacts import (
    build_alias_mapping_v1, build_classification_taxonomy_v1,
    make_alias_mapping, make_classification_taxonomy,
    resolve_manufacturer_alias, resolve_model_alias, resolve_source_taxonomy_mapping,
    validate_alias_mapping_against_taxonomy,
)


@dataclass(frozen=True, slots=True)
class FE6GateExecution:
    taxonomy_artifact_id: str
    taxonomy_content_sha256: str
    alias_mapping_artifact_id: str
    alias_mapping_content_sha256: str
    fixture_results: dict[str, bool]
    gate_result_manifest: ArtifactContent
    failure_reasons: tuple[str, ...]


def _mapping(source_taxon: str, dimension: str, kind: str, target: str | None) -> dict[str, Any]:
    return {
        "source_id": "synthetic_fe6", "dimension_name": dimension,
        "source_taxon": source_taxon, "mapping_kind": kind,
        "target_id_or_ref": target,
    }


def _synthetic_alias_mapping(
    mappings: list[dict[str, Any]], *, manufacturers: list[dict[str, str]] | None = None,
    models: list[dict[str, str]] | None = None,
) -> ArtifactContent:
    return make_alias_mapping({
        "alias_mapping_version": "alias_mapping_v1",
        "manufacturer_aliases": manufacturers or [], "model_aliases": models or [],
        "source_taxonomy_mappings": mappings,
    })


def run_fe6_fixture_proofs() -> dict[str, bool]:
    """Run retained, entirely synthetic F-E6 semantic fixtures."""
    taxonomy = build_classification_taxonomy_v1()
    tax = taxonomy.semantic_payload
    apple_mobile = _synthetic_alias_mapping([
        _mapping(raw, "platform_family", "CANONICAL_VALUE", "ios")
        for raw in ("iOS", "iPadOS")
    ])
    ios_umbrella = (
        "ios" in tax["platform_family_values"]
        and "ipados" not in tax["platform_family_values"]
        and "smartphone" in tax["device_class_values"]
        and "tablet" in tax["device_class_values"]
        and validate_alias_mapping_against_taxonomy(taxonomy, apple_mobile)
        and all(
            (row := resolve_source_taxonomy_mapping(
                apple_mobile, source_id="synthetic_fe6",
                dimension_name="platform_family", source_taxon=raw,
            )) is not None and row["mapping_kind"] == "CANONICAL_VALUE"
            and row["target_id_or_ref"] == "ios"
            and resolve_source_taxonomy_mapping(
                apple_mobile, source_id="synthetic_fe6",
                dimension_name="device_class", source_taxon=raw,
            ) is None
            for raw in ("iOS", "iPadOS")
        )
    )

    broad = _synthetic_alias_mapping([
        _mapping(raw, "device_class", "BROAD_UNRESOLVED", "synthetic-broad:" + raw)
        for raw in ("Phone", "Mobile", "Desktop")
    ])
    broad_values = validate_alias_mapping_against_taxonomy(taxonomy, broad) and all(
        (row := resolve_source_taxonomy_mapping(
            broad, source_id="synthetic_fe6", dimension_name="device_class", source_taxon=raw,
        )) is not None and row["mapping_kind"] == "BROAD_UNRESOLVED"
        and row["target_id_or_ref"] not in tax["device_class_values"]
        for raw in ("Phone", "Mobile", "Desktop")
    )

    out_of_scope_rows = [
        _mapping(raw, "device_class", "RECOGNIZED_OUT_OF_SCOPE", "synthetic-oos:" + raw)
        for raw in ("TV", "printer", "camera", "watch/wearable", "desktop workstation", "IoT class")
    ] + [_mapping("unsupported platform family", "platform_family",
                  "RECOGNIZED_OUT_OF_SCOPE", "synthetic-oos:platform")]
    out_of_scope = _synthetic_alias_mapping(out_of_scope_rows)
    recognized_out_of_scope = validate_alias_mapping_against_taxonomy(taxonomy, out_of_scope) and all(
        row["mapping_kind"] == "RECOGNIZED_OUT_OF_SCOPE"
        for row in out_of_scope.semantic_payload["source_taxonomy_mappings"]
    )
    for forbidden in ("manufacturer_family", "model_family"):
        try:
            _synthetic_alias_mapping([_mapping("synthetic", forbidden,
                                              "RECOGNIZED_OUT_OF_SCOPE", "synthetic-oos")])
        except DeviceFingerprintValidationError:
            pass
        else:
            recognized_out_of_scope = False

    unmapped = _synthetic_alias_mapping([
        _mapping("unknown manufacturer", "manufacturer_family", "UNMAPPED", None),
        _mapping("unknown model", "model_family", "UNMAPPED", None),
    ])
    unmapped_manufacturer_model = validate_alias_mapping_against_taxonomy(taxonomy, unmapped) and all(
        row["target_id_or_ref"] is None and row["mapping_kind"] == "UNMAPPED"
        for row in unmapped.semantic_payload["source_taxonomy_mappings"]
    )

    fixture_tax = make_classification_taxonomy({
        **tax,
        "manufacturer_records": [{"manufacturer_id": "fixture-maker", "display_label": "Fixture Maker"}],
        "model_family_records": [{"model_family_id": "fixture-model",
                                  "manufacturer_id": "fixture-maker", "display_label": "Fixture Model"}],
    })
    explicit = _synthetic_alias_mapping([], manufacturers=[
        {"source_id": "synthetic_fe6", "source_value": raw, "manufacturer_id": "fixture-maker"}
        for raw in ("Apple Inc.", "Apple Corporation")
    ], models=[
        {"source_id": "synthetic_fe6", "source_value": raw, "model_family_id": "fixture-model"}
        for raw in ("Model A", "Model A (2026)")
    ])
    multiple_explicit_aliases = validate_alias_mapping_against_taxonomy(fixture_tax, explicit) and all(
        resolve_manufacturer_alias(explicit, source_id="synthetic_fe6", source_value=raw)["manufacturer_id"]
        == "fixture-maker" for raw in ("Apple Inc.", "Apple Corporation")
    ) and all(
        resolve_model_alias(explicit, source_id="synthetic_fe6", source_value=raw)["model_family_id"]
        == "fixture-model" for raw in ("Model A", "Model A (2026)")
    )
    no_heuristic_aliasing = all(
        resolve_manufacturer_alias(explicit, source_id="synthetic_fe6", source_value=raw) is None
        for raw in ("apple inc.", "Apple Inc", "Apple", "Apple Corp")
    ) and all(
        resolve_model_alias(explicit, source_id="synthetic_fe6", source_value=raw) is None
        for raw in ("model a", "Model-A", "Model", "Model B")
    ) and resolve_source_taxonomy_mapping(
        broad, source_id="synthetic_fe6", dimension_name="device_class", source_taxon="phone",
    ) is None
    return {
        "ios_umbrella": bool(ios_umbrella),
        "broad_values": bool(broad_values),
        "recognized_out_of_scope": bool(recognized_out_of_scope),
        "unmapped_manufacturer_model": bool(unmapped_manufacturer_model),
        "multiple_explicit_aliases": bool(multiple_explicit_aliases),
        "no_heuristic_aliasing": bool(no_heuristic_aliasing),
    }


def _ref(content: ArtifactContent) -> dict[str, str]:
    if not isinstance(content, ArtifactContent):
        raise DeviceFingerprintValidationError("Invalid F-E6 input artifact")
    return ArtifactRef(content.artifact_id, content.content_sha256).as_dict()


def run_fe6_taxonomy_alias_gate(
    taxonomy: ArtifactContent,
    alias_mapping: ArtifactContent,
    *,
    candidate_repository_commit_sha: str,
    candidate_repository_tree_sha: str,
    environment_identity: str,
    retained_evidence_refs: list[dict[str, Any]],
    decision_record_refs: list[str],
) -> FE6GateExecution:
    """Evaluate the frozen V1 production candidate and emit PASS/FAIL manifest."""
    input_refs = [_ref(taxonomy), _ref(alias_mapping)]
    reasons: list[str] = []
    try:
        if taxonomy.artifact_type != "ClassificationTaxonomy":
            raise DeviceFingerprintValidationError("Wrong taxonomy artifact type")
        expected = make_classification_taxonomy(taxonomy.semantic_payload)
        if expected.artifact_id != taxonomy.artifact_id:
            raise DeviceFingerprintValidationError("Noncanonical taxonomy")
    except DeviceFingerprintValidationError:
        reasons.append("taxonomy_invalid")
    try:
        if alias_mapping.artifact_type != "AliasMapping":
            raise DeviceFingerprintValidationError("Wrong alias artifact type")
        expected = make_alias_mapping(alias_mapping.semantic_payload)
        if expected.artifact_id != alias_mapping.artifact_id:
            raise DeviceFingerprintValidationError("Noncanonical aliases")
    except DeviceFingerprintValidationError:
        reasons.append("alias_mapping_invalid")
    if "taxonomy_invalid" not in reasons:
        tax = taxonomy.semantic_payload
        if tax["manufacturer_records"] or tax["model_family_records"]:
            reasons.append("production_manufacturer_model_records_not_empty")
    if "alias_mapping_invalid" not in reasons:
        aliases = alias_mapping.semantic_payload
        if aliases["manufacturer_aliases"] or aliases["model_aliases"]:
            reasons.append("production_aliases_not_empty")
        if aliases["source_taxonomy_mappings"] != build_alias_mapping_v1().semantic_payload["source_taxonomy_mappings"]:
            reasons.append("satori_mapping_set_mismatch")
    if not ("taxonomy_invalid" in reasons or "alias_mapping_invalid" in reasons):
        try:
            validate_alias_mapping_against_taxonomy(taxonomy, alias_mapping)
        except DeviceFingerprintValidationError:
            reasons.append("alias_taxonomy_incompatible")
    try:
        fixtures = run_fe6_fixture_proofs()
    except DeviceFingerprintValidationError:
        fixtures = {name: False for name in (
            "ios_umbrella", "broad_values", "recognized_out_of_scope",
            "unmapped_manufacturer_model", "multiple_explicit_aliases", "no_heuristic_aliasing",
        )}
    reasons.extend(f"fixture_{name}_failed" for name, passed in fixtures.items() if not passed)
    if not retained_evidence_refs:
        reasons.append("retained_evidence_required")
    if not decision_record_refs:
        reasons.append("owner_decision_required")
    status = "FAIL" if reasons else "PASS"
    manifest = make_gate_result_manifest({
        "gate_id": "F-E6", "gate_contract_version": "R14-F-E6-v1", "status": status,
        "candidate_repository_commit_sha": candidate_repository_commit_sha,
        "candidate_repository_tree_sha": candidate_repository_tree_sha,
        "input_artifact_refs": input_refs,
        "output_artifact_refs": input_refs if status == "PASS" else [],
        "retained_evidence_refs": retained_evidence_refs,
        "proof_execution_identity": {
            "execution_id": str(uuid.uuid4()), "executor_kind": "TECHLEAD_GATE_TOOL",
            "repository_commit_sha": candidate_repository_commit_sha,
            "repository_tree_sha": candidate_repository_tree_sha,
            "procedure_or_test_suite_id": "F-E6-taxonomy-alias-v1",
            "environment_identity": environment_identity,
            "execution_artifact_sha256": None,
        },
        "trusted_time_inputs": {
            "foundation_knowledge_evaluation_at_utc": None,
            "foundation_admission_evaluation_at_utc": None,
            "knowledge_evaluation_at_utc": None,
        },
        "decision_record_refs": decision_record_refs,
    })
    return FE6GateExecution(
        taxonomy.artifact_id, taxonomy.content_sha256,
        alias_mapping.artifact_id, alias_mapping.content_sha256,
        fixtures, manifest, tuple(reasons),
    )
