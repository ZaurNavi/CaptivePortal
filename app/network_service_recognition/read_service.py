"""Bounded read-only NI-04 orchestration. All sensitive memory is request-local."""
import threading
from datetime import timedelta

from app.analytics.source_gateway import QueryDeadline, AnalyticsQueryDeadlineExceeded
from app.device_fingerprint.validation import validate_site_id
from app.network_attribution.validation import canonical_mac
from app.network_metadata.validation import canonical_uuid, ni_timestamp, ni_format_utc
from app.network_metadata.recognition_read_service import RecognitionSourceEvidenceV1
from app.network_metadata_projection.recognition_read_service import (
    RecognitionProjectionSnapshotV2, RecognitionProjectionEdgeFactV1)
from .artifacts import RecognitionBundle
from .canonical import canonical_hostname
from .matcher import match_direct_sni_v1, matching_rules, rule_eligible
from .models import (ServiceUnavailable, ServiceValidationError, ServiceBusy, ServiceDeadline,
    ServiceWindowV1, ServiceRecognitionCoverageV2, RecentServiceV1, RecentServiceCategoryV1,
    LastServiceObservationV1, DeviceServiceSummaryV2, service_observation, freshness, evidence_state,
    pipeline_coverage, availability)
from .serialization import serialize_device_service_intelligence
from .evaluator import ServiceRecognitionEvaluatorV1
from app.network_metadata_projection.service_delivery_read_service import RecognitionIdentityV1

_READ_SLOTS = threading.BoundedSemaphore(1)


class DeviceServiceRecognitionReadService:
    def __init__(self, projection_reader, source_reader, bundle):
        if type(bundle) is not RecognitionBundle:
            raise ServiceUnavailable("recognition_unavailable")
        self._projection_reader, self._source_reader, self.bundle = projection_reader, source_reader, bundle

    def get_device_service_summary(self, site_id, device_id, client_mac, *, evaluated_at_utc, deadline):
        try:
            validate_site_id(site_id)
            canonical_uuid(device_id)
            if canonical_mac(client_mac) != client_mac: raise ValueError
            at = ni_timestamp(evaluated_at_utc, canonical=True)
        except Exception:
            raise ServiceValidationError() from None
        if not _READ_SLOTS.acquire(blocking=False): raise ServiceBusy()
        try:
            bounded = QueryDeadline(min(deadline.expires_at, deadline.monotonic() + 5), deadline.monotonic)
            bounded.require_remaining()
            start, recent = at - timedelta(days=1), at - timedelta(hours=1)
            snapshot = self._projection_reader.read_service_recognition_snapshot(site_id, device_id, client_mac,
                ni_format_utc(start), evaluated_at_utc, max_rows=5000, deadline=bounded)
            if (type(snapshot) is not RecognitionProjectionSnapshotV2 or type(snapshot.schema_version) is not int or snapshot.schema_version != 2
                    or snapshot.site_id != site_id or snapshot.device_id != device_id
                    or snapshot.historical_window_completeness_claimed is not False
                    or type(snapshot.facts) is not tuple or len(snapshot.facts) > 5000
                    or type(snapshot.device_linked_pending_count) is not int
                    or not 0 <= snapshot.device_linked_pending_count <= 5000):
                raise ServiceUnavailable()
            source, attribution = pipeline_coverage(snapshot.projection_runtime_state, snapshot.projection_safe_reason)
            identity = {"authoritative": "authoritative", "not_yet_registry_resolved": "pending",
                        "registry_unavailable": "unavailable", "absent": "absent"}[snapshot.identity_binding_state]
            if identity != "authoritative" and (snapshot.bound_device_id is not None or snapshot.facts
                                                or snapshot.device_linked_pending_count): raise ServiceUnavailable()
            if identity == "authoritative" and snapshot.bound_device_id != device_id: raise ServiceUnavailable()
            observations, limited = [], False
            if identity == "authoritative":
                # No concurrent source DB transaction while projection snapshot is open.
                refs = sorted({row.source_observation_ref for row in snapshot.facts})
                if len(refs) > 5000: raise ServiceUnavailable()
                evidence = {}
                scalar_count = 0
                for offset in range(0, len(refs), 256):
                    bounded.require_remaining()
                    batch = tuple(refs[offset:offset + 256])
                    values = self._source_reader.read_recognition_evidence(site_id, batch, deadline=bounded)
                    if type(values) is not tuple or len(values) != len(batch): raise ServiceUnavailable()
                    batch_seen = set()
                    for value in values:
                        if type(value) is not RecognitionSourceEvidenceV1 or value.observation_id not in batch or value.observation_id in batch_seen:
                            raise ServiceUnavailable()
                        batch_seen.add(value.observation_id)
                        if value.dns is not None:
                            scalar_count += len(value.dns.queries) + len(value.dns.answers)
                        for sni in (value.tls, value.quic):
                            if sni is not None and sni.sni is not None: scalar_count += 1
                        if scalar_count > 25000: raise ServiceUnavailable()
                        evidence[value.observation_id] = value
                evaluated, limited = ServiceRecognitionEvaluatorV1(
                    self.bundle, matcher=match_direct_sni_v1).evaluate_batch(
                        tuple((fact, RecognitionIdentityV1(site_id, client_mac, device_id,
                            "authoritative", None)) for fact in snapshot.facts),
                        evidence, evaluated_at_utc, deadline=bounded, maximum=5000)
                observations = [row.observation for row in evaluated if row.observation is not None]
                limited |= any(row.limited for row in evaluated)
                if len(observations) > 5000: raise ServiceUnavailable()
            result = self._summary(site_id, device_id, evaluated_at_utc, start, recent, at, identity,
                                   source, attribution, bool(snapshot.device_linked_pending_count), observations, limited)
            serialize_device_service_intelligence(result, self.bundle)
            bounded.require_remaining()
            return result
        except AnalyticsQueryDeadlineExceeded:
            raise ServiceDeadline() from None
        except (ServiceUnavailable, ServiceBusy, ServiceDeadline, ServiceValidationError):
            raise
        except Exception:
            raise ServiceUnavailable() from None
        finally:
            _READ_SLOTS.release()

    def _summary(self, site, device, evaluated, start, recent, at, identity, source, attribution, linked_pending, observations, limited):
        ordered = sorted((row for row in observations if row.resolution_state == "service_resolved"),
                         key=lambda row: (at - ni_timestamp(row.observed_at, canonical=True), row.service_id, row.service_observation_id))
        services = self.bundle.taxonomy.index["services"]
        organizations = {row["organization_id"]: row for row in self.bundle.taxonomy["organizations"]}
        categories = {row["service_category_id"]: row for row in self.bundle.taxonomy["service_categories"]}
        def fields(row):
            service = services[row.service_id]
            return (row.service_id, service["display_name"], row.organization_id, organizations[row.organization_id]["display_name"],
                    row.service_category_id, categories[row.service_category_id]["display_name"], row.observed_at, row.support_state)
        last = LastServiceObservationV1(*fields(ordered[0])) if ordered else None
        latest = {}
        for row in ordered:
            if ni_timestamp(row.observed_at, canonical=True) >= recent:
                latest.setdefault(row.service_id, row)
        if len(latest) > 12: limited = True
        visible = tuple(RecentServiceV1(*fields(row)) for row in list(latest.values())[:12])
        latest_categories = {}
        for row in visible:
            latest_categories.setdefault(row.service_category_id, row.last_observed_at)
        category_rows = tuple(RecentServiceCategoryV1(key, categories[key]["display_name"], event) for key, event in
            sorted(latest_categories.items(), key=lambda pair: (at - ni_timestamp(pair[1], canonical=True), pair[0])))
        coverage = ServiceRecognitionCoverageV2("confirmed_device_evidence", source, attribution,
            "authoritative" if identity == "authoritative" else "none", linked_pending,
            "unavailable" if identity != "authoritative" else "limited" if limited else "usable", False)
        identity_values = {"recognition_" + key: self.bundle.ruleset[key] for key in ("ruleset_id", "ruleset_version", "ruleset_digest_sha256")}
        identity_values.update({key: self.bundle.taxonomy[key] for key in ("taxonomy_id", "taxonomy_version", "taxonomy_digest_sha256")})
        return DeviceServiceSummaryV2(2, site, device, evaluated,
            ServiceWindowV1(ni_format_utc(start), evaluated, 86400, ni_format_utc(recent), 3600),
            availability(identity, coverage),
            evidence_state(identity, last, coverage), identity, visible, category_rows, last,
            freshness(None if last is None else (at - ni_timestamp(last.observed_at, canonical=True)).total_seconds(), coverage),
            coverage, **identity_values)
