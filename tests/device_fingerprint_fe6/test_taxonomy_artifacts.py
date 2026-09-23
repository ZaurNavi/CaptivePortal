from copy import deepcopy

import pytest

from app.device_fingerprint.k1_satori_import import (
    ACCEPTED_SATORI_AUDIT,
    SATORI_DEVICE_CLASS_TAXONOMY_MAPPING,
    SATORI_PLATFORM_TAXONOMY_MAPPING,
    _candidate_taxonomy,
)
from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.taxonomy_artifacts import (
    build_alias_mapping_v1, build_classification_taxonomy_v1,
    make_alias_mapping, make_classification_taxonomy,
    resolve_manufacturer_alias, resolve_model_alias, resolve_source_taxonomy_mapping,
    validate_alias_mapping_against_taxonomy,
)


def _tax():
    return build_classification_taxonomy_v1().semantic_payload


def _aliases():
    return build_alias_mapping_v1().semantic_payload


def test_frozen_production_taxonomy_exact_sets_order_and_empty_identity_records():
    artifact = build_classification_taxonomy_v1()
    payload = artifact.semantic_payload
    assert payload == {
        "taxonomy_version": "classification_taxonomy_v1",
        "platform_family_values": ["android", "chromeos", "ios", "linux", "macos", "windows"],
        "device_class_values": ["laptop", "smartphone", "tablet"],
        "manufacturer_records": [], "model_family_records": [],
        "recognized_out_of_scope_dimensions": ["device_class", "platform_family"],
    }
    assert artifact.artifact_id == build_classification_taxonomy_v1().artifact_id
    assert "ipados" not in payload["platform_family_values"]
    reversed_payload = {**payload,
        "platform_family_values": list(reversed(payload["platform_family_values"])),
        "device_class_values": list(reversed(payload["device_class_values"])),
        "recognized_out_of_scope_dimensions": list(reversed(payload["recognized_out_of_scope_dimensions"]))}
    assert make_classification_taxonomy(reversed_payload).artifact_id == artifact.artifact_id


@pytest.mark.parametrize("mutation", [
    lambda p: p.update(unexpected=True),
    lambda p: p.update(taxonomy_version="other"),
    lambda p: p["platform_family_values"].remove("ios"),
    lambda p: p["platform_family_values"].append("ipados"),
    lambda p: p["platform_family_values"].append("android"),
    lambda p: p["device_class_values"].remove("tablet"),
    lambda p: p["device_class_values"].append("desktop"),
    lambda p: p["recognized_out_of_scope_dimensions"].append("manufacturer_family"),
])
def test_taxonomy_rejects_non_frozen_shape_or_values(mutation):
    payload = _tax()
    mutation(payload)
    with pytest.raises(DeviceFingerprintValidationError):
        make_classification_taxonomy(payload)


def test_manufacturer_and_model_primary_keys_are_unique_without_parent_requirement():
    payload = _tax()
    payload["manufacturer_records"] = [{"manufacturer_id": "maker", "display_label": "Maker"}]
    payload["model_family_records"] = [{
        "model_family_id": "model", "manufacturer_id": "maker", "display_label": "Model",
    }]
    assert make_classification_taxonomy(payload).semantic_payload["model_family_records"] == payload["model_family_records"]
    duplicate = deepcopy(payload)
    duplicate["manufacturer_records"].append({"manufacturer_id": "maker", "display_label": "Other"})
    with pytest.raises(DeviceFingerprintValidationError):
        make_classification_taxonomy(duplicate)
    duplicate = deepcopy(payload)
    duplicate["model_family_records"].append({
        "model_family_id": "model", "manufacturer_id": None, "display_label": "Other",
    })
    with pytest.raises(DeviceFingerprintValidationError):
        make_classification_taxonomy(duplicate)
    unregistered_parent = deepcopy(payload)
    unregistered_parent["model_family_records"][0]["manufacturer_id"] = "unknown"
    assert make_classification_taxonomy(unregistered_parent).semantic_payload[
        "model_family_records"
    ][0]["manufacturer_id"] == "unknown"
    empty_parent = deepcopy(payload)
    empty_parent["model_family_records"][0]["manufacturer_id"] = ""
    with pytest.raises(DeviceFingerprintValidationError):
        make_classification_taxonomy(empty_parent)
    nfc_duplicate = deepcopy(payload)
    nfc_duplicate["manufacturer_records"].extend([
        {"manufacturer_id": "caf\u00e9", "display_label": "First"},
        {"manufacturer_id": "cafe\u0301", "display_label": "Second"},
    ])
    with pytest.raises(DeviceFingerprintValidationError):
        make_classification_taxonomy(nfc_duplicate)


def test_production_aliases_are_ten_exact_k1_mappings_and_no_broad_rows():
    mapping = build_alias_mapping_v1()
    payload = mapping.semantic_payload
    assert payload["alias_mapping_version"] == "alias_mapping_v1"
    assert payload["manufacturer_aliases"] == payload["model_aliases"] == []
    assert len(payload["source_taxonomy_mappings"]) == 10
    expected = {
        ("platform_family", source, target)
        for source, target in SATORI_PLATFORM_TAXONOMY_MAPPING.items()
    } | {
        ("device_class", source, target)
        for source, target in SATORI_DEVICE_CLASS_TAXONOMY_MAPPING.items()
    }
    assert {(row["dimension_name"], row["source_taxon"], row["target_id_or_ref"])
            for row in payload["source_taxonomy_mappings"]} == expected
    assert all(row["source_id"] == "satori_dhcp" and row["mapping_kind"] == "CANONICAL_VALUE"
               for row in payload["source_taxonomy_mappings"])
    assert all(row["source_taxon"] not in {"Phone", "Mobile", "Desktop"}
               for row in payload["source_taxonomy_mappings"])
    assert validate_alias_mapping_against_taxonomy(build_classification_taxonomy_v1(), mapping)


def test_k1_uses_the_same_mapping_constants_and_accepted_audit_is_unchanged():
    for source, target in SATORI_PLATFORM_TAXONOMY_MAPPING.items():
        row = _candidate_taxonomy({"os_class": source})[0]
        assert row["canonical_target_id"] == target
        assert resolve_source_taxonomy_mapping(
            build_alias_mapping_v1(), source_id="satori_dhcp",
            dimension_name="platform_family", source_taxon=source,
        )["target_id_or_ref"] == target
    for source, target in SATORI_DEVICE_CLASS_TAXONOMY_MAPPING.items():
        row = _candidate_taxonomy({"device_type": source})[1]
        assert row["canonical_target_id"] == target
    assert (
        ACCEPTED_SATORI_AUDIT.fingerprints_total,
        ACCEPTED_SATORI_AUDIT.source_tests_total,
        ACCEPTED_SATORI_AUDIT.source_tests_accepted,
        ACCEPTED_SATORI_AUDIT.source_tests_rejected,
        ACCEPTED_SATORI_AUDIT.canonical_records_unique,
        ACCEPTED_SATORI_AUDIT.predicate_groups_total,
        ACCEPTED_SATORI_AUDIT.ambiguous_predicate_groups,
        ACCEPTED_SATORI_AUDIT.records_in_ambiguous_groups,
    ) == (481, 2787, 903, 1884, 903, 448, 164, 619)


@pytest.mark.parametrize("mutation", [
    lambda p: p.update(extra=True),
    lambda p: p.update(alias_mapping_version="wrong"),
    lambda p: p["source_taxonomy_mappings"].append(deepcopy(p["source_taxonomy_mappings"][0])),
    lambda p: p["source_taxonomy_mappings"][0].update(mapping_kind="UNMAPPED"),
    lambda p: p["source_taxonomy_mappings"][0].update(mapping_kind="BROAD_UNRESOLVED", target_id_or_ref=None),
    lambda p: p["source_taxonomy_mappings"][0].update(mapping_kind="RECOGNIZED_OUT_OF_SCOPE", dimension_name="model_family"),
    lambda p: p["source_taxonomy_mappings"][0].update(mapping_kind="unknown"),
])
def test_alias_mapping_closed_shape_keys_and_cross_field_rules(mutation):
    payload = _aliases()
    mutation(payload)
    with pytest.raises(DeviceFingerprintValidationError):
        make_alias_mapping(payload)


def test_exact_source_lookup_distinguishes_case_punctuation_substring_and_missing():
    mapping = build_alias_mapping_v1()
    assert resolve_source_taxonomy_mapping(
        mapping, source_id="satori_dhcp", dimension_name="device_class", source_taxon="Tablet",
    )["target_id_or_ref"] == "tablet"
    assert resolve_source_taxonomy_mapping(
        mapping, source_id="satori_dhcp", dimension_name="device_class", source_taxon="tablet",
    )["target_id_or_ref"] == "tablet"
    for wrong in ("TABLET", "Table", "Tablet!", "tablet "):
        assert resolve_source_taxonomy_mapping(
            mapping, source_id="satori_dhcp", dimension_name="device_class", source_taxon=wrong,
        ) is None
    assert resolve_source_taxonomy_mapping(
        mapping, source_id="other", dimension_name="device_class", source_taxon="Tablet",
    ) is None
    assert resolve_source_taxonomy_mapping(
        mapping, source_id="satori_dhcp", dimension_name="platform_family", source_taxon="Mac OS",
    )["target_id_or_ref"] == "macos"
    assert resolve_source_taxonomy_mapping(
        mapping, source_id="satori_dhcp", dimension_name="platform_family", source_taxon="macOS",
    ) is None


def test_fixture_aliases_and_canonical_targets_are_explicit_only():
    taxonomy = make_classification_taxonomy({
        **_tax(),
        "manufacturer_records": [{"manufacturer_id": "maker", "display_label": "Maker"}],
        "model_family_records": [{"model_family_id": "model", "manufacturer_id": "maker",
                                  "display_label": "Model"}],
    })
    payload = _aliases()
    payload["manufacturer_aliases"] = [
        {"source_id": "fixture", "source_value": raw, "manufacturer_id": "maker"}
        for raw in ("Apple Inc.", "Apple Corporation")
    ]
    payload["model_aliases"] = [
        {"source_id": "fixture", "source_value": raw, "model_family_id": "model"}
        for raw in ("Model A", "Model A 2026")
    ]
    mapping = make_alias_mapping(payload)
    assert validate_alias_mapping_against_taxonomy(taxonomy, mapping)
    assert resolve_manufacturer_alias(mapping, source_id="fixture", source_value="Apple Inc.")["manufacturer_id"] == "maker"
    assert resolve_model_alias(mapping, source_id="fixture", source_value="Model A")["model_family_id"] == "model"
    for wrong in ("apple inc.", "Apple Inc", "Apple", "Apple Corp"):
        assert resolve_manufacturer_alias(mapping, source_id="fixture", source_value=wrong) is None
    for wrong in ("model a", "Model-A", "Model", "Model B"):
        assert resolve_model_alias(mapping, source_id="fixture", source_value=wrong) is None
    duplicate = deepcopy(payload)
    duplicate["manufacturer_aliases"].append({
        "source_id": "fixture", "source_value": "Apple Inc.", "manufacturer_id": "other",
    })
    with pytest.raises(DeviceFingerprintValidationError):
        make_alias_mapping(duplicate)
    duplicate = deepcopy(payload)
    duplicate["model_aliases"].append({
        "source_id": "fixture", "source_value": "Model A", "model_family_id": "other",
    })
    with pytest.raises(DeviceFingerprintValidationError):
        make_alias_mapping(duplicate)


def test_compatibility_rejects_missing_canonical_targets_and_broad_narrowing():
    taxonomy = build_classification_taxonomy_v1()
    payload = _aliases()
    payload["source_taxonomy_mappings"][0]["target_id_or_ref"] = "unknown-platform"
    with pytest.raises(DeviceFingerprintValidationError):
        validate_alias_mapping_against_taxonomy(taxonomy, make_alias_mapping(payload))
    payload = _aliases()
    payload["source_taxonomy_mappings"][0].update(
        mapping_kind="BROAD_UNRESOLVED", target_id_or_ref="tablet",
    )
    if payload["source_taxonomy_mappings"][0]["dimension_name"] == "platform_family":
        payload["source_taxonomy_mappings"][0]["target_id_or_ref"] = "ios"
    with pytest.raises(DeviceFingerprintValidationError):
        validate_alias_mapping_against_taxonomy(taxonomy, make_alias_mapping(payload))
    payload = _aliases()
    payload["manufacturer_aliases"] = [{
        "source_id": "fixture", "source_value": "Maker", "manufacturer_id": "maker",
    }]
    with pytest.raises(DeviceFingerprintValidationError):
        validate_alias_mapping_against_taxonomy(taxonomy, make_alias_mapping(payload))
