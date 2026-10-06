"""Advisory Admin projection of retained PRODUCTION results; never classifies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.device_fingerprint.classification_read import (
    ClassificationReadRecord, DeviceFingerprintClassificationReadService, MAX_PRODUCTION_READ_MACS,
)
from app.device_fingerprint.validation import parse_utc, validate_mac, validate_site_id

_DIMENSIONS = {
    "device_class_result": "device_class", "platform_result": "platform_family",
    "manufacturer_result": "manufacturer_family", "model_result": "model_family",
}
_TEXT_SETS = (
    "supporting_origin_groups", "contradicting_origin_groups", "not_evaluable_origin_groups",
    "out_of_scope_taxon_references", "explanation_codes",
)
_LABELS = {"ios": "iOS", "macos": "macOS", "chromeos": "ChromeOS"}


@dataclass(frozen=True, slots=True)
class FingerprintDimensionPresentation:
    canonical_value_id: str | None
    status: str
    support_level: str
    supporting_origin_groups: tuple[str, ...]
    contradicting_origin_groups: tuple[str, ...]
    not_evaluable_origin_groups: tuple[str, ...]
    out_of_scope_taxon_references: tuple[str, ...]
    explanation_codes: tuple[str, ...]
    knowledge_references: tuple[dict[str, str], ...]
    value: str

    def as_dict(self) -> dict[str, Any]:
        return {"canonical_value_id": self.canonical_value_id, "status": self.status,
                "support_level": self.support_level, "value": self.value,
                **{name: list(getattr(self, name)) for name in _TEXT_SETS},
                "knowledge_references": [dict(ref) for ref in self.knowledge_references]}


@dataclass(frozen=True, slots=True)
class FingerprintPresentation:
    state: str
    global_classification_status: str | None = None
    classified_at_utc: str | None = None
    device_class_result: FingerprintDimensionPresentation | None = None
    platform_result: FingerprintDimensionPresentation | None = None
    manufacturer_result: FingerprintDimensionPresentation | None = None
    model_result: FingerprintDimensionPresentation | None = None

    def compact_type(self) -> dict[str, Any]:
        dimension = self.device_class_result
        return {"state": self.state,
                "status": dimension.status if dimension else None,
                "canonical_value_id": dimension.canonical_value_id if dimension else None,
                "value": dimension.value if dimension else "—"}

    def compact_platform(self) -> dict[str, Any]:
        platform = self.platform_result
        return {"state": self.state,
                "status": platform.status if platform else None,
                "canonical_value_id": platform.canonical_value_id if platform else None,
                "value": platform.value if platform else "—"}

    def as_dict(self) -> dict[str, Any]:
        return {"state": self.state, "global_classification_status": self.global_classification_status,
                "classified_at_utc": self.classified_at_utc,
                **{name: getattr(self, name).as_dict() if getattr(self, name) else None
                   for name in _DIMENSIONS}}


def effective_platform_presentation(
    controller_value: str | None, controller_key: str | None,
    fingerprint_platform: dict[str, Any],
) -> dict[str, Any]:
    """Shared list precedence; Device Card continues to expose separate sources."""
    if controller_key is not None and controller_key != "unknown":
        return {"source": "controller", "value": controller_value, "key": controller_key}
    if (fingerprint_platform["state"] == "classified"
            and fingerprint_platform["status"] == "resolved"
            and fingerprint_platform["canonical_value_id"] is not None):
        return {"source": "fingerprint", "value": fingerprint_platform["value"],
                "key": fingerprint_platform["canonical_value_id"]}
    unresolved = controller_key == "unknown" or fingerprint_platform["state"] == "classified"
    return {"source": "none", "value": "Unknown" if unresolved else "—", "key": None}


def present_classification(record: ClassificationReadRecord | None) -> FingerprintPresentation:
    if record is None:
        return FingerprintPresentation("no_result")
    if record.core.execution_context != "PRODUCTION" or record.result.artifact_type != "ClassificationResult":
        raise ValueError("Fingerprint presentation requires a production result")
    parse_utc(record.core.classified_at_utc)
    payload = record.result.semantic_payload
    global_status = payload["global_classification_status"]
    if global_status not in {"classified", "partial", "unknown", "recognized_out_of_scope", "insufficient_evidence", "conflicting_evidence"}:
        raise ValueError("Invalid fingerprint global status")
    dimensions = {}
    for name, dimension in _DIMENSIONS.items():
        row = payload[name]
        if (not isinstance(row, dict) or set(row) != {
                "dimension_name", "display_label_ref", "canonical_value_id", "status", "support_level",
                *_TEXT_SETS, "knowledge_references"} or row["dimension_name"] != dimension):
            raise ValueError("Invalid fingerprint dimension")
        status, canonical = row["status"], row["canonical_value_id"]
        if status not in {"resolved", "unknown", "insufficient_evidence", "conflicting_evidence", "recognized_out_of_scope"}:
            raise ValueError("Invalid fingerprint dimension status")
        if (canonical is not None and (not isinstance(canonical, str) or not canonical)
                or status == "resolved" and canonical is None
                or status != "resolved" and canonical is not None
                or row["support_level"] not in {"none", "low", "medium", "high"}):
            raise ValueError("Invalid fingerprint dimension value/support")
        if dimension == "device_class" and status == "resolved" and canonical not in {"smartphone", "tablet", "laptop"}:
            raise ValueError("Invalid fingerprint device class")
        for key in _TEXT_SETS:
            if not isinstance(row[key], list) or any(not isinstance(item, str) or not item for item in row[key]):
                raise ValueError("Invalid fingerprint diagnostic metadata")
        refs = row["knowledge_references"]
        if not isinstance(refs, list) or any(
                not isinstance(ref, dict) or set(ref) != {
                    "knowledge_provenance_id", "knowledge_provenance_digest",
                    "knowledge_bundle_id", "knowledge_bundle_digest",
                    "canonical_knowledge_record_id", "rule_or_source_record_identity"}
                or any(not isinstance(value, str) or not value for value in ref.values()) for ref in refs):
            raise ValueError("Invalid fingerprint knowledge references")
        dimensions[name] = FingerprintDimensionPresentation(
            canonical, status, row["support_level"],
            *(tuple(row[key]) for key in _TEXT_SETS), tuple(dict(ref) for ref in refs),
            _LABELS.get(canonical, canonical.replace("_", " ").title()) if status == "resolved" else "Unknown")
    return FingerprintPresentation("classified", global_status, record.core.classified_at_utc, **dimensions)


class DeviceFingerprintPresentationService:
    def __init__(self, reader: DeviceFingerprintClassificationReadService | None) -> None:
        self._reader = reader

    def get_many(self, site_id: str, macs: list[str] | tuple[str, ...]) -> dict[str, FingerprintPresentation]:
        site = validate_site_id(site_id)
        if not isinstance(macs, (list, tuple)) or len(macs) > MAX_PRODUCTION_READ_MACS:
            raise ValueError("Invalid fingerprint presentation batch")
        canonical = tuple(sorted({validate_mac(mac) for mac in macs}))
        if not canonical:
            return {}
        try:
            if self._reader is None:
                raise ValueError("Fingerprint read service unavailable")
            records = self._reader.get_current_production_many(site, canonical)
            if set(records) != set(canonical):
                raise ValueError("Fingerprint batch scope mismatch")
            projections = {}
            for mac, record in records.items():
                if record is not None and (record.core.site_id != site or record.core.observed_mac != mac):
                    raise ValueError("Fingerprint record scope mismatch")
                projections[mac] = present_classification(record)
            return projections
        except Exception:
            # Fingerprint is optional. Never substitute controller values or fail the core page.
            return {mac: FingerprintPresentation("unavailable") for mac in canonical}

    def get(self, site_id: str, mac: str) -> FingerprintPresentation:
        canonical = validate_mac(mac)
        return self.get_many(site_id, (canonical,))[canonical]
