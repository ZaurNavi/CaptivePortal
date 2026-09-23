"""Frozen R14 F-E6 taxonomy and exact alias ArtifactContent contracts."""

from __future__ import annotations

import unicodedata
from typing import Any, Callable

from .artifact_content import ArtifactContent, canonical_set, make_artifact_content
from .k1_satori_import import (
    SATORI_DEVICE_CLASS_TAXONOMY_MAPPING,
    SATORI_PLATFORM_TAXONOMY_MAPPING,
)
from .models import DeviceFingerprintValidationError

PLATFORM_FAMILIES = frozenset({"android", "ios", "windows", "macos", "chromeos", "linux"})
DEVICE_CLASSES = frozenset({"smartphone", "tablet", "laptop"})
OUT_OF_SCOPE_DIMENSIONS = frozenset({"platform_family", "device_class"})
DIMENSIONS = frozenset({"platform_family", "device_class", "manufacturer_family", "model_family"})
MAPPING_KINDS = frozenset({
    "CANONICAL_VALUE", "BROAD_UNRESOLVED", "RECOGNIZED_OUT_OF_SCOPE", "UNMAPPED",
})

_TAXONOMY_FIELDS = frozenset({
    "taxonomy_version", "platform_family_values", "device_class_values",
    "manufacturer_records", "model_family_records", "recognized_out_of_scope_dimensions",
})
_ALIAS_FIELDS = frozenset({
    "alias_mapping_version", "manufacturer_aliases", "model_aliases", "source_taxonomy_mappings",
})


def _fail(message: str) -> None:
    raise DeviceFingerprintValidationError(message)


def _shape(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        _fail(f"Invalid {label} shape")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(f"Invalid {label}")
    return value


def _set_rows(
    values: Any, fields: frozenset[str], key: Callable[[dict[str, Any]], Any],
    label: str,
) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        _fail(f"Invalid {label}")
    rows = [dict(_shape(row, fields, label)) for row in values]
    keys = []
    for row in rows:
        primary = key(row)
        parts = primary if isinstance(primary, tuple) else (primary,)
        if not parts or any(not isinstance(part, str) or not part for part in parts):
            _fail(f"Invalid {label} primary key")
        keys.append(tuple(unicodedata.normalize("NFC", part) for part in parts))
    if len(keys) != len(set(keys)):
        _fail(f"Duplicate {label} primary key")
    return canonical_set(rows, key)


def _string_set(values: Any, allowed: frozenset[str], label: str) -> list[str]:
    if not isinstance(values, list):
        _fail(f"Invalid {label}")
    for value in values:
        _text(value, label)
        if value not in allowed:
            _fail(f"Unknown {label}")
    if len(values) != len(set(values)):
        _fail(f"Duplicate {label}")
    if set(values) != allowed:
        _fail(f"Incomplete {label}")
    return canonical_set(values, lambda value: value)


def make_classification_taxonomy(payload: dict[str, Any]) -> ArtifactContent:
    """Validate the closed classification_taxonomy_v1 schema and its SETs."""
    value = _shape(payload, _TAXONOMY_FIELDS, "ClassificationTaxonomy")
    if value["taxonomy_version"] != "classification_taxonomy_v1":
        _fail("Invalid taxonomy version")
    platforms = _string_set(value["platform_family_values"], PLATFORM_FAMILIES, "platform family")
    classes = _string_set(value["device_class_values"], DEVICE_CLASSES, "device class")
    out_of_scope = _string_set(
        value["recognized_out_of_scope_dimensions"], OUT_OF_SCOPE_DIMENSIONS,
        "recognized out-of-scope dimension",
    )
    manufacturers = _set_rows(
        value["manufacturer_records"], frozenset({"manufacturer_id", "display_label"}),
        lambda row: row["manufacturer_id"], "ManufacturerRecord",
    )
    for row in manufacturers:
        _text(row["manufacturer_id"], "manufacturer ID")
        _text(row["display_label"], "manufacturer label")
    models = _set_rows(
        value["model_family_records"],
        frozenset({"model_family_id", "manufacturer_id", "display_label"}),
        lambda row: row["model_family_id"], "ModelFamilyRecord",
    )
    for row in models:
        _text(row["model_family_id"], "model family ID")
        _text(row["display_label"], "model family label")
        if row["manufacturer_id"] is not None:
            _text(row["manufacturer_id"], "model manufacturer ID")
    return make_artifact_content("ClassificationTaxonomy", {
        "taxonomy_version": value["taxonomy_version"],
        "platform_family_values": platforms,
        "device_class_values": classes,
        "manufacturer_records": manufacturers,
        "model_family_records": models,
        "recognized_out_of_scope_dimensions": out_of_scope,
    })


def build_classification_taxonomy_v1() -> ArtifactContent:
    return make_classification_taxonomy({
        "taxonomy_version": "classification_taxonomy_v1",
        "platform_family_values": list(PLATFORM_FAMILIES),
        "device_class_values": list(DEVICE_CLASSES),
        "manufacturer_records": [], "model_family_records": [],
        "recognized_out_of_scope_dimensions": list(OUT_OF_SCOPE_DIMENSIONS),
    })


def make_alias_mapping(payload: dict[str, Any]) -> ArtifactContent:
    """Validate exact V1 aliases without normalizing source identity strings."""
    value = _shape(payload, _ALIAS_FIELDS, "AliasMapping")
    if value["alias_mapping_version"] != "alias_mapping_v1":
        _fail("Invalid alias mapping version")
    manufacturers = _set_rows(
        value["manufacturer_aliases"],
        frozenset({"source_id", "source_value", "manufacturer_id"}),
        lambda row: (row["source_id"], row["source_value"]), "ManufacturerAlias",
    )
    for row in manufacturers:
        for field in ("source_id", "source_value", "manufacturer_id"):
            _text(row[field], field)
    models = _set_rows(
        value["model_aliases"],
        frozenset({"source_id", "source_value", "model_family_id"}),
        lambda row: (row["source_id"], row["source_value"]), "ModelAlias",
    )
    for row in models:
        for field in ("source_id", "source_value", "model_family_id"):
            _text(row[field], field)
    mappings = _set_rows(
        value["source_taxonomy_mappings"],
        frozenset({"source_id", "dimension_name", "source_taxon", "mapping_kind", "target_id_or_ref"}),
        lambda row: (row["source_id"], row["dimension_name"], row["source_taxon"]),
        "SourceTaxonomyMapping",
    )
    for row in mappings:
        _text(row["source_id"], "source ID")
        _text(row["source_taxon"], "source taxon")
        dimension = _text(row["dimension_name"], "mapping dimension")
        if dimension not in DIMENSIONS:
            _fail("Unknown mapping dimension")
        kind = _text(row["mapping_kind"], "mapping kind")
        if kind not in MAPPING_KINDS:
            _fail("Unknown mapping kind")
        target = row["target_id_or_ref"]
        if kind == "UNMAPPED":
            if target is not None:
                _fail("UNMAPPED mapping cannot have a target")
        else:
            _text(target, "mapping target")
        if kind == "RECOGNIZED_OUT_OF_SCOPE" and dimension not in OUT_OF_SCOPE_DIMENSIONS:
            _fail("Invalid recognized-out-of-scope dimension")
    return make_artifact_content("AliasMapping", {
        "alias_mapping_version": value["alias_mapping_version"],
        "manufacturer_aliases": manufacturers, "model_aliases": models,
        "source_taxonomy_mappings": mappings,
    })


def build_alias_mapping_v1() -> ArtifactContent:
    mappings = []
    for dimension, accepted in (
        ("platform_family", SATORI_PLATFORM_TAXONOMY_MAPPING),
        ("device_class", SATORI_DEVICE_CLASS_TAXONOMY_MAPPING),
    ):
        mappings.extend({
            "source_id": "satori_dhcp", "dimension_name": dimension,
            "source_taxon": source, "mapping_kind": "CANONICAL_VALUE",
            "target_id_or_ref": target,
        } for source, target in accepted.items())
    return make_alias_mapping({
        "alias_mapping_version": "alias_mapping_v1",
        "manufacturer_aliases": [], "model_aliases": [],
        "source_taxonomy_mappings": mappings,
    })


def _payload(content: ArtifactContent, kind: str, builder: Callable[[dict[str, Any]], ArtifactContent]) -> dict[str, Any]:
    if not isinstance(content, ArtifactContent) or content.artifact_type != kind:
        _fail(f"Expected {kind} artifact")
    validated = builder(content.semantic_payload)
    if validated.artifact_id != content.artifact_id:
        _fail(f"Noncanonical {kind} artifact")
    return validated.semantic_payload


def _exact_row(
    alias_mapping: ArtifactContent, rows_name: str, fields: tuple[str, ...],
    expected: tuple[str, ...],
) -> dict[str, Any] | None:
    rows = _payload(alias_mapping, "AliasMapping", make_alias_mapping)[rows_name]
    return next((row for row in rows if tuple(row[field] for field in fields) == expected), None)


def resolve_manufacturer_alias(
    alias_mapping: ArtifactContent, *, source_id: str, source_value: str,
) -> dict[str, Any] | None:
    return _exact_row(alias_mapping, "manufacturer_aliases", ("source_id", "source_value"),
                      (source_id, source_value))


def resolve_model_alias(
    alias_mapping: ArtifactContent, *, source_id: str, source_value: str,
) -> dict[str, Any] | None:
    return _exact_row(alias_mapping, "model_aliases", ("source_id", "source_value"),
                      (source_id, source_value))


def resolve_source_taxonomy_mapping(
    alias_mapping: ArtifactContent, *, source_id: str,
    dimension_name: str, source_taxon: str,
) -> dict[str, Any] | None:
    return _exact_row(
        alias_mapping, "source_taxonomy_mappings",
        ("source_id", "dimension_name", "source_taxon"),
        (source_id, dimension_name, source_taxon),
    )


def validate_alias_mapping_against_taxonomy(
    taxonomy: ArtifactContent, alias_mapping: ArtifactContent,
) -> bool:
    tax = _payload(taxonomy, "ClassificationTaxonomy", make_classification_taxonomy)
    aliases = _payload(alias_mapping, "AliasMapping", make_alias_mapping)
    admitted = {
        "platform_family": set(tax["platform_family_values"]),
        "device_class": set(tax["device_class_values"]),
        "manufacturer_family": {row["manufacturer_id"] for row in tax["manufacturer_records"]},
        "model_family": {row["model_family_id"] for row in tax["model_family_records"]},
    }
    for row in aliases["manufacturer_aliases"]:
        if row["manufacturer_id"] not in admitted["manufacturer_family"]:
            _fail("Manufacturer alias target is not admitted")
    for row in aliases["model_aliases"]:
        if row["model_family_id"] not in admitted["model_family"]:
            _fail("Model alias target is not admitted")
    for row in aliases["source_taxonomy_mappings"]:
        kind, dimension, target = row["mapping_kind"], row["dimension_name"], row["target_id_or_ref"]
        if kind == "CANONICAL_VALUE" and target not in admitted[dimension]:
            _fail("Canonical mapping target is not admitted")
        if kind == "BROAD_UNRESOLVED" and target in admitted[dimension]:
            _fail("Broad mapping cannot resolve to a canonical value")
        if kind == "RECOGNIZED_OUT_OF_SCOPE" and dimension not in OUT_OF_SCOPE_DIMENSIONS:
            _fail("Out-of-scope mapping dimension is not admitted")
        if kind == "UNMAPPED" and target is not None:
            _fail("Unmapped source cannot have a target")
    return True
