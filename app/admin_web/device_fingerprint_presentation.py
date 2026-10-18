"""Advisory Admin projection of retained PRODUCTION results; never classifies."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from app.device_fingerprint.classification_read import (
    ClassificationReadRecord, DeviceFingerprintClassificationReadService, MAX_PRODUCTION_READ_MACS,
)
from app.device_fingerprint.validation import parse_utc, validate_mac, validate_site_id
from app.device_fingerprint.artifact_content import ArtifactRef

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
    origin_diagnostics: dict[str, Any] | None = None

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
                   for name in _DIMENSIONS},
                **({"origin_diagnostics": self.origin_diagnostics} if self.origin_diagnostics is not None else {})}


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


def _origin_diagnostics(artifacts) -> dict[str, Any]:
    """Project retained metadata only; do not rerun reduction/freshness/lineage engines."""
    if len(artifacts) != 6:
        raise ValueError("Incomplete diagnostic origins")
    origins = []
    for artifact in artifacts:
        payload = artifact.semantic_payload
        if (set(payload) != {"origin_assessment_contract_version", "evidence_snapshot_content",
                "source_evaluability", "origin_group", "dimension_assessments", "evidence_refs",
                "knowledge_refs", "explanation_codes"}
                or type(payload["origin_assessment_contract_version"]) is not int
                or payload["origin_assessment_contract_version"] != 1):
            raise ValueError("Unsupported diagnostic assessment")

        def codes(value):
            if not isinstance(value, list) or any(not isinstance(code, str) or not code for code in value):
                raise ValueError("Invalid diagnostic codes")
            return list(value)

        dimensions = payload["dimension_assessments"]
        if (not isinstance(dimensions, list) or len(dimensions) != 4
                or {row["dimension_name"] for row in dimensions} != set(_DIMENSIONS.values())):
            raise ValueError("Invalid diagnostic dimensions")
        rows = []
        for row in dimensions:
            state, selected, strength = row["internal_state"], row["selected_canonical_value_id"], row["effective_claim_strength"]
            if (state not in {"resolved", "recognized_out_of_scope", "ambiguous", "conflicting", "no_claim", "not_evaluable"}
                    or selected is not None and (not isinstance(selected, str) or not selected)
                    or strength not in {None, "strong", "supporting"}
                    or state == "resolved" and (selected is None or strength is None)
                    or state != "resolved" and selected is not None):
                raise ValueError("Invalid diagnostic claim metadata")
            refs = row["knowledge_refs"]
            if not isinstance(refs, list):
                raise ValueError("Invalid diagnostic knowledge references")
            for item in refs:
                if set(item) != {"knowledge_provenance_id", "knowledge_provenance_digest",
                        "knowledge_bundle_id", "knowledge_bundle_digest", "canonical_knowledge_record_id",
                        "rule_or_source_record_identity"} or any(not isinstance(v, str) or not v for v in item.values()):
                    raise ValueError("Invalid diagnostic knowledge reference")
                for kind, prefix in (("KnowledgeBundle", "knowledge_bundle"), ("KnowledgeProvenanceManifest", "knowledge_provenance")):
                    reference = ArtifactRef(item[prefix + "_id"], item[prefix + "_digest"])
                    if not reference.artifact_id.startswith(kind + ":v1:sha256:"):
                        raise ValueError("Invalid diagnostic knowledge identity")
            rows.append({"dimension_name": row["dimension_name"], "internal_state": state,
                         "selected_canonical_value_id": selected, "effective_claim_strength": strength,
                         "explanation_codes": codes(row["explanation_codes"]),
                         "knowledge_references": [dict(item) for item in refs]})
        origins.append({"origin_group": payload["origin_group"],
                        "assessment": ArtifactRef(artifact.artifact_id, artifact.content_sha256).as_dict(),
                        "explanation_codes": codes(payload["explanation_codes"]), "dimensions": rows})
    if {row["origin_group"] for row in origins} != {"dhcp", "portal", "tcp", "tls", "quic", "mac_registry"}:
        raise ValueError("Unsupported diagnostic origins")
    return {"state": "available", "origins": sorted(origins, key=lambda row: row["origin_group"])}


class DeviceFingerprintPresentationService:
    def __init__(self, reader: DeviceFingerprintClassificationReadService | None) -> None:
        self._reader = reader

    def get_many(self, site_id: str, macs: list[str] | tuple[str, ...]) -> dict[str, FingerprintPresentation]:
        return self._get_many(site_id, macs, include_diagnostics=False)

    def _get_many(self, site_id, macs, *, include_diagnostics):
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
                if include_diagnostics and record is not None:
                    try:
                        artifacts = self._reader.get_origin_assessments(
                            site, mac, record.core.classification_id,
                            expected_result=ArtifactRef(record.result.artifact_id, record.result.content_sha256))
                        diagnostics = _origin_diagnostics(artifacts)
                    except Exception:
                        diagnostics = {"state": "unavailable"}
                    projections[mac] = replace(projections[mac], origin_diagnostics=diagnostics)
            return projections
        except Exception:
            # Fingerprint is optional. Never substitute controller values or fail the core page.
            return {mac: FingerprintPresentation("unavailable") for mac in canonical}

    def get(self, site_id: str, mac: str) -> FingerprintPresentation:
        canonical = validate_mac(mac)
        return self.get_many(site_id, (canonical,))[canonical]

    def get_detail(self, site_id: str, mac: str) -> FingerprintPresentation:
        canonical = validate_mac(mac)
        return self._get_many(site_id, (canonical,), include_diagnostics=True)[canonical]


# Display-only allowlists. Schema validation remains exclusively in the existing
# evidence registry; these are not alternative evidence validators or classifiers.
_OBSERVED_FIELDS = {
    "portal_headers/1": "platform_family mobile_boolean browser_runtime_family webview_or_captive_context model_family os_major platform_source mobile_source runtime_source context_source model_source os_major_source ua_present sec_ch_ua_present sec_ch_ua_platform_present sec_ch_ua_mobile_present",
    "portal_headers/2": "model_family os_major form_factor_mobile form_factor_tablet form_factor_desktop model_source os_major_source form_factors_source",
    "dhcp/1": "message_type parameter_request_list option_order vendor_class client_identifier_kind maximum_message_size rapid_commit_requested capport_requested ipv6_only_preferred_requested hostname_present",
    "tcp_syn/1": "ip_version observed_ttl tcp_window mss window_scale sack_permitted timestamps_present tcp_option_order",
    "tcp_syn/2": "ip_version observed_ttl ip_option_length_bytes ip_id_zero ip_df ip_reserved_flag ip_ecn_bits tcp_header_length_bytes tcp_window tcp_sequence_zero tcp_ack_number_nonzero tcp_ack_first_octet_lsb_set tcp_urg_pointer_nonzero tcp_fin tcp_rst tcp_push tcp_urg tcp_ns tcp_ece tcp_cwr tcp_payload_present tcp_option_records",
    "tls_client/1": "ja4 ja4_a ja4_b ja4_c tls_version_family client_alpns ech_extension_present grease_extension_present",
    "quic_client/1": "ja4 ja4_a ja4_b ja4_c quic_version ech_extension_present grease_extension_present",
}


class ObservedDeviceHintsPresentationService:
    """Optional bounded observations, never a canonical Fingerprint fallback."""

    def __init__(self, reader) -> None:
        self._reader = reader

    @staticmethod
    def unavailable() -> dict[str, Any]:
        return {"state": "unavailable", "coverage": "bounded_latest_256", "trust": "observed_unverified",
                "reported_model": None, "reported_os": None, "sources": []}

    def get(self, site_id, mac, *, site_first_seen_at, as_of_utc, deadline) -> dict[str, Any]:
        from app.device_fingerprint.validation import canonical_json
        try:
            if self._reader is None:
                return self.unavailable()
            result = self._reader.latest_observed_hints(
                site_id, mac, site_first_seen_at=site_first_seen_at, as_of_utc=as_of_utc, deadline=deadline)
            for group in result["sources"]:
                allowed = _OBSERVED_FIELDS.get(group["schema"], "").split()
                group["fields"] = {key: group["fields"][key] for key in allowed if key in group["fields"]}
            # Five exact schema-bounded groups (including all 40 TCP options)
            # fit below this response cap, independent of retained history size.
            if len(canonical_json(result).encode("utf-8")) > 65_536:
                return self.unavailable()
            deadline.require_remaining()
            return result
        except Exception:
            return self.unavailable()
