"""Exact NI-04 ephemeral and public DTOs. Protected source values are absent."""
from dataclasses import dataclass, asdict
from hashlib import sha256
from .canonical import canonical_json


class ServiceUnavailable(RuntimeError):
    def __init__(self, reason="source_unavailable"):
        self.reason = reason if reason in {"source_unavailable", "recognition_unavailable"} else "source_unavailable"
        super().__init__(self.reason)


class ServiceBusy(RuntimeError):
    pass


class ServiceDeadline(RuntimeError):
    pass


class ServiceValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True, order=True)
class RecognitionEvidenceRefV1:
    edge_id: str
    source_observation_ref: str
    signal_type: str
    event_at: str


@dataclass(frozen=True, slots=True)
class ServiceObservationV1:
    schema_version: int
    service_observation_id: str
    site_id: str
    device_id: str
    observed_at: str
    organization_id: str | None
    service_id: str | None
    service_category_id: str | None
    evidence_strength_class: str
    support_state: str
    supporting_signal_types: tuple[str, ...]
    evidence_refs: tuple[RecognitionEvidenceRefV1, ...]
    recognition_ruleset_id: str
    recognition_ruleset_version: int
    recognition_ruleset_digest_sha256: str
    taxonomy_id: str
    taxonomy_version: int
    taxonomy_digest_sha256: str
    resolution_state: str


def service_observation(site, device, fact, matched):
    signal = fact.source_event_family + "_sni"
    support = {"unknown": "insufficient", "ambiguous": "conflicting"}.get(
        matched.resolution_state, "directly_supported")
    values = dict(schema_version=1, site_id=site, device_id=device, observed_at=fact.event_at,
        organization_id=matched.organization_id, service_id=matched.service_id,
        service_category_id=matched.service_category_id,
        evidence_strength_class=matched.evidence_strength_class or "weak_context", support_state=support,
        supporting_signal_types=(signal,), evidence_refs=(RecognitionEvidenceRefV1(
            fact.edge_id, fact.source_observation_ref, signal, fact.event_at),),
        recognition_ruleset_id=matched.ruleset_id, recognition_ruleset_version=matched.ruleset_version,
        recognition_ruleset_digest_sha256=matched.ruleset_digest_sha256, taxonomy_id=matched.taxonomy_id,
        taxonomy_version=matched.taxonomy_version, taxonomy_digest_sha256=matched.taxonomy_digest_sha256)
    encoded = {key: value for key, value in values.items() if key != "evidence_refs"}
    encoded["evidence_refs"] = [asdict(value) for value in values["evidence_refs"]]
    return ServiceObservationV1(**values, service_observation_id=sha256(canonical_json(encoded)).hexdigest(),
                                resolution_state=matched.resolution_state)


@dataclass(frozen=True, slots=True)
class ServiceWindowV1:
    from_utc: str
    to_utc: str
    duration_seconds: int
    recent_from_utc: str
    recent_duration_seconds: int


@dataclass(frozen=True, slots=True)
class RecentServiceV1:
    service_id: str
    display_name: str
    organization_id: str
    organization_display_name: str
    service_category_id: str
    service_category_display_name: str
    last_observed_at: str
    support_state: str


@dataclass(frozen=True, slots=True)
class RecentServiceCategoryV1:
    service_category_id: str
    display_name: str
    last_observed_at: str


@dataclass(frozen=True, slots=True)
class LastServiceObservationV1:
    service_id: str
    display_name: str
    organization_id: str
    organization_display_name: str
    service_category_id: str
    service_category_display_name: str
    observed_at: str
    support_state: str


@dataclass(frozen=True, slots=True)
class ServiceRecognitionCoverageV1:
    scope: str
    source_state: str
    attribution_state: str
    projection_state: str
    recognition_state: str
    historical_window_completeness_claimed: bool


@dataclass(frozen=True, slots=True)
class DeviceServiceSummaryV1:
    schema_version: int
    site_id: str
    device_id: str
    evaluated_at_utc: str
    window: ServiceWindowV1
    availability_state: str
    evidence_state: str
    identity_binding_state: str
    recent_services: tuple[RecentServiceV1, ...]
    service_categories: tuple[RecentServiceCategoryV1, ...]
    last_service_observation: LastServiceObservationV1 | None
    freshness_state: str
    coverage: ServiceRecognitionCoverageV1
    recognition_ruleset_id: str
    recognition_ruleset_version: int
    recognition_ruleset_digest_sha256: str
    taxonomy_id: str
    taxonomy_version: int
    taxonomy_digest_sha256: str


def evidence_state(identity, last, coverage):
    if identity != "authoritative": return "identity_pending"
    if last is not None: return "supported_results_present"
    if coverage.source_state != "usable": return "insufficient_source_coverage"
    if coverage.attribution_state != "usable": return "insufficient_attribution"
    if coverage.recognition_state != "usable": return "recognition_limited"
    return "no_supported_result_observed_with_sufficient_coverage"


def freshness(age, coverage):
    if age is None: return "unavailable"
    if not 0 <= age <= 86400: raise ServiceUnavailable()
    base = "fresh" if age <= 300 else "recent" if age <= 3600 else "stale"
    if coverage.source_state in {"unavailable", "unknown"}: return "stale"
    if base == "fresh" and (coverage.source_state != "usable" or coverage.attribution_state != "usable"
                             or coverage.recognition_state != "usable"): return "recent"
    return base
