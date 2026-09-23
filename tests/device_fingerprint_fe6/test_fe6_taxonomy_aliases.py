from copy import deepcopy

import pytest

from app.device_fingerprint.artifact_content import ArtifactRef, make_artifact_content
from app.device_fingerprint.fe6_taxonomy_aliases import (
    run_fe6_fixture_proofs, run_fe6_taxonomy_alias_gate,
)
from app.device_fingerprint.k2b_p0f_import import ACCEPTED_P0F_AUDIT
from app.device_fingerprint.k3_portal_rules import build_k3_portal_rule_set_v1
from app.device_fingerprint.taxonomy_artifacts import (
    build_alias_mapping_v1, build_classification_taxonomy_v1,
    make_alias_mapping, make_classification_taxonomy,
    resolve_source_taxonomy_mapping, validate_alias_mapping_against_taxonomy,
)

_DECISION = "22222222-2222-4222-8222-222222222222"  # Synthetic only; never a real admission.
_EVIDENCE = [{"evidence_label": "synthetic-fe6-proof", "file_sha256": "e" * 64,
              "media_type": "application/json", "path_or_reference": "test://fe6"}]


def _gate(taxonomy=None, aliases=None, *, evidence=None, decisions=None):
    return run_fe6_taxonomy_alias_gate(
        taxonomy or build_classification_taxonomy_v1(),
        aliases or build_alias_mapping_v1(),
        candidate_repository_commit_sha="a" * 40,
        candidate_repository_tree_sha="b" * 40,
        environment_identity="synthetic-fe6-test",
        retained_evidence_refs=_EVIDENCE if evidence is None else evidence,
        decision_record_refs=[_DECISION] if decisions is None else decisions,
    )


def test_fixture_proofs_cover_all_six_required_semantics():
    assert run_fe6_fixture_proofs() == {
        "ios_umbrella": True, "broad_values": True,
        "recognized_out_of_scope": True, "unmapped_manufacturer_model": True,
        "multiple_explicit_aliases": True, "no_heuristic_aliasing": True,
    }


def test_synthetic_ipados_and_ios_share_platform_without_device_class_binding():
    taxonomy = build_classification_taxonomy_v1()
    aliases = make_alias_mapping({
        "alias_mapping_version": "alias_mapping_v1",
        "manufacturer_aliases": [], "model_aliases": [],
        "source_taxonomy_mappings": [
            {"source_id": "synthetic_fe6", "dimension_name": "platform_family",
             "source_taxon": source, "mapping_kind": "CANONICAL_VALUE",
             "target_id_or_ref": "ios"}
            for source in ("iOS", "iPadOS")
        ],
    })
    assert validate_alias_mapping_against_taxonomy(taxonomy, aliases)
    assert "ipados" not in taxonomy.semantic_payload["platform_family_values"]
    for source in ("iOS", "iPadOS"):
        row = resolve_source_taxonomy_mapping(
            aliases, source_id="synthetic_fe6", dimension_name="platform_family",
            source_taxon=source,
        )
        assert (row["mapping_kind"], row["target_id_or_ref"]) == ("CANONICAL_VALUE", "ios")
        assert resolve_source_taxonomy_mapping(
            aliases, source_id="synthetic_fe6", dimension_name="device_class",
            source_taxon=source,
        ) is None
    assert {"smartphone", "tablet"} <= set(taxonomy.semantic_payload["device_class_values"])
    assert all(row["source_taxon"] != "iPadOS" for row in
               build_alias_mapping_v1().semantic_payload["source_taxonomy_mappings"])


def test_gate_pass_has_only_two_candidate_input_and_output_refs():
    result = _gate()
    manifest = result.gate_result_manifest.semantic_payload
    assert result.failure_reasons == ()
    assert manifest["status"] == "PASS"
    assert manifest["gate_id"] == "F-E6"
    assert manifest["gate_contract_version"] == "R14-F-E6-v1"
    expected = [ArtifactRef(a.artifact_id, a.content_sha256).as_dict()
                for a in (build_alias_mapping_v1(), build_classification_taxonomy_v1())]
    assert manifest["input_artifact_refs"] == expected
    assert manifest["output_artifact_refs"] == expected
    assert len(manifest["input_artifact_refs"]) == 2
    assert {ref["artifact_id"].split(":")[0] for ref in expected} == {
        "ClassificationTaxonomy", "AliasMapping",
    }
    assert manifest["proof_execution_identity"]["executor_kind"] == "TECHLEAD_GATE_TOOL"
    assert manifest["proof_execution_identity"]["procedure_or_test_suite_id"] == "F-E6-taxonomy-alias-v1"
    assert manifest["trusted_time_inputs"] == {
        "foundation_knowledge_evaluation_at_utc": None,
        "foundation_admission_evaluation_at_utc": None,
        "knowledge_evaluation_at_utc": None,
    }
    assert all(result.fixture_results.values())


@pytest.mark.parametrize("kind", [
    "missing_platform", "extra_platform", "ipados", "missing_class", "extra_class",
    "manufacturer", "model", "manufacturer_alias", "model_alias", "satori_changed",
    "satori_missing", "satori_extra", "tablet_collapsed", "broad_narrowed",
    "bad_canonical_target", "wrong_taxonomy_type", "wrong_alias_type",
])
def test_gate_semantic_candidate_failures_return_fail_manifest(kind):
    taxonomy = build_classification_taxonomy_v1()
    aliases = build_alias_mapping_v1()
    tax = taxonomy.semantic_payload
    mapping = aliases.semantic_payload
    if kind == "missing_platform":
        tax["platform_family_values"].remove("ios")
    elif kind == "extra_platform":
        tax["platform_family_values"].append("other")
    elif kind == "ipados":
        tax["platform_family_values"].append("ipados")
    elif kind == "missing_class":
        tax["device_class_values"].remove("tablet")
    elif kind == "extra_class":
        tax["device_class_values"].append("desktop")
    elif kind == "manufacturer":
        tax["manufacturer_records"].append({"manufacturer_id": "fixture", "display_label": "Fixture"})
    elif kind == "model":
        tax["model_family_records"].append({"model_family_id": "fixture",
                                             "manufacturer_id": None, "display_label": "Fixture"})
    elif kind == "manufacturer_alias":
        mapping["manufacturer_aliases"].append({"source_id": "fixture", "source_value": "Maker",
                                                 "manufacturer_id": "fixture"})
    elif kind == "model_alias":
        mapping["model_aliases"].append({"source_id": "fixture", "source_value": "Model",
                                          "model_family_id": "fixture"})
    elif kind == "satori_changed":
        mapping["source_taxonomy_mappings"][0]["target_id_or_ref"] = "different"
    elif kind == "satori_missing":
        mapping["source_taxonomy_mappings"].pop()
    elif kind == "satori_extra":
        extra = deepcopy(mapping["source_taxonomy_mappings"][0])
        extra["source_taxon"] = "Phone"
        mapping["source_taxonomy_mappings"].append(extra)
    elif kind == "tablet_collapsed":
        mapping["source_taxonomy_mappings"] = [
            row for row in mapping["source_taxonomy_mappings"] if row["source_taxon"] != "tablet"
        ]
    elif kind == "broad_narrowed":
        mapping["source_taxonomy_mappings"].append({
            "source_id": "satori_dhcp", "dimension_name": "device_class", "source_taxon": "Phone",
            "mapping_kind": "BROAD_UNRESOLVED", "target_id_or_ref": "smartphone",
        })
    elif kind == "bad_canonical_target":
        mapping["source_taxonomy_mappings"][0]["target_id_or_ref"] = "not-admitted"
    elif kind == "wrong_taxonomy_type":
        taxonomy = make_artifact_content("WrongTaxonomy", tax)
    elif kind == "wrong_alias_type":
        aliases = make_artifact_content("WrongAlias", mapping)
    if kind not in {"wrong_taxonomy_type", "wrong_alias_type"}:
        taxonomy = make_artifact_content("ClassificationTaxonomy", tax)
        aliases = make_artifact_content("AliasMapping", mapping)
    result = _gate(taxonomy, aliases)
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []
    assert result.failure_reasons


@pytest.mark.parametrize("evidence,decisions", [([], [_DECISION]), (_EVIDENCE, [])])
def test_gate_requires_real_admission_evidence_and_owner_decision(evidence, decisions):
    result = _gate(evidence=evidence, decisions=decisions)
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []


def test_k2b_and_k3_canonical_outputs_fit_taxonomy_without_gate_dependencies():
    tax = build_classification_taxonomy_v1().semantic_payload
    admitted_k2b = {platform for platform, count in ACCEPTED_P0F_AUDIT.platform_counts if count > 0}
    assert admitted_k2b == {"android", "ios", "linux", "macos", "windows"}
    assert admitted_k2b <= set(tax["platform_family_values"])
    rules = build_k3_portal_rule_set_v1().semantic_payload["rules"]
    canonical = [row for row in rules if row["outcome_kind"] == "CANONICAL_VALUE"]
    assert {row["outcome_id_or_ref"] for row in canonical if row["dimension_name"] == "platform_family"} <= set(
        tax["platform_family_values"]
    )
    assert any(row["dimension_name"] == "device_class" and row["outcome_id_or_ref"] == "tablet"
               for row in canonical)
    manifest = _gate().gate_result_manifest.semantic_payload
    assert all(ref["artifact_id"].split(":")[0] in {"ClassificationTaxonomy", "AliasMapping"}
               for ref in manifest["input_artifact_refs"])
