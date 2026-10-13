"""Closed typed publication boundary; no reflection of protected read DTOs."""
from dataclasses import asdict
from datetime import timedelta
from app.device_fingerprint.validation import validate_site_id
from app.network_metadata.validation import canonical_uuid, ni_timestamp
from .models import (DeviceServiceSummaryV2, ServiceWindowV1, ServiceRecognitionCoverageV2,
    RecentServiceV1, RecentServiceCategoryV1, LastServiceObservationV1, ServiceUnavailable, freshness, evidence_state, availability)
from .models import DeviceServiceSummaryV3, ServiceMaterializationV1, materialized_evidence_state, materialized_availability


def serialize_device_service_intelligence(value, bundle):
    try:
        v3 = type(value) is DeviceServiceSummaryV3
        if type(value) not in {DeviceServiceSummaryV2, DeviceServiceSummaryV3} or type(value.window) is not ServiceWindowV1 or type(value.coverage) is not ServiceRecognitionCoverageV2:
            raise ValueError
        validate_site_id(value.site_id)
        canonical_uuid(value.device_id)
        at = ni_timestamp(value.evaluated_at_utc, canonical=True)
        window, coverage = value.window, value.coverage
        start = ni_timestamp(window.from_utc, canonical=True)
        recent = ni_timestamp(window.recent_from_utc, canonical=True)
        if (type(value.schema_version) is not int or value.schema_version != (3 if v3 else 2)
                or window.to_utc != value.evaluated_at_utc
                or type(window.duration_seconds) is not int or window.duration_seconds != 86400
                or type(window.recent_duration_seconds) is not int or window.recent_duration_seconds != 3600
                or at - start != timedelta(days=1) or at - recent != timedelta(hours=1)
                or coverage.scope != "confirmed_device_evidence" or coverage.historical_window_completeness_claimed is not False
                or coverage.source_state not in {"usable", "degraded", "unavailable", "unknown"}
                or coverage.pipeline_attribution_state not in {"usable", "degraded", "unavailable", "unknown"}
                or coverage.device_evidence_binding_state != ("authoritative" if value.identity_binding_state == "authoritative" else "none")
                or type(coverage.device_linked_pending) is not bool
                or (value.identity_binding_state != "authoritative" and coverage.device_linked_pending)
                or coverage.recognition_state not in {"usable", "limited", "unavailable"}
                or value.identity_binding_state not in {"authoritative", "pending", "unavailable", "absent"}
                or type(value.recent_services) is not tuple or len(value.recent_services) > 12
                or type(value.service_categories) is not tuple or len(value.service_categories) > 10):
            raise ValueError
        for kind, parent in (("recognition_ruleset", bundle.ruleset), ("taxonomy", bundle.taxonomy)):
            original = "ruleset" if kind == "recognition_ruleset" else kind
            for suffix in ("_id", "_version", "_digest_sha256"):
                if type(getattr(value, kind + suffix)) is not type(parent[original + suffix]) or getattr(value, kind + suffix) != parent[original + suffix]:
                    raise ValueError
        organizations = {row["organization_id"]: row for row in bundle.taxonomy["organizations"]}
        categories = {row["service_category_id"]: row for row in bundle.taxonomy["service_categories"]}
        def check_service(item, cls, time_key, lower):
            if type(item) is not cls: raise ValueError
            service = bundle.taxonomy.index["services"][item.service_id]
            if (service["lifecycle_state"] != "active" or item.display_name != service["display_name"]
                    or item.organization_id != service["organization_id"]
                    or item.service_category_id != service["service_category_id"]
                    or item.organization_display_name != organizations[item.organization_id]["display_name"]
                    or item.service_category_display_name != categories[item.service_category_id]["display_name"]
                    or item.support_state != "directly_supported"): raise ValueError
            event = ni_timestamp(getattr(item, time_key), canonical=True)
            if not lower <= event < at: raise ValueError
            return event
        seen, ordered, category_latest = set(), [], {}
        for row in value.recent_services:
            event = check_service(row, RecentServiceV1, "last_observed_at", recent)
            if row.service_id in seen: raise ValueError
            seen.add(row.service_id)
            ordered.append((at - event, row.service_id))
            category_latest[row.service_category_id] = max(event, category_latest.get(row.service_category_id, event))
        if ordered != sorted(ordered): raise ValueError
        category_order = []
        category_seen = set()
        for row in value.service_categories:
            if type(row) is not RecentServiceCategoryV1 or row.service_category_id in category_seen: raise ValueError
            event = ni_timestamp(row.last_observed_at, canonical=True)
            if event != category_latest[row.service_category_id] or row.display_name != categories[row.service_category_id]["display_name"]: raise ValueError
            category_seen.add(row.service_category_id)
            category_order.append((at - event, row.service_category_id))
        if category_seen != set(category_latest) or category_order != sorted(category_order): raise ValueError
        last = value.last_service_observation
        if v3:
            mat = value.materialization
            if (type(mat) is not ServiceMaterializationV1 or mat.state not in {"current","backfilling","lagging","unavailable","capacity_halted","conflict"}
                    or mat.window_coverage_state not in {"complete","partial","unknown"}
                    or mat.lag_seconds is not None and (type(mat.lag_seconds) is not int or mat.lag_seconds < 0)
                    or mat.last_successful_update_at_utc is not None and ni_timestamp(mat.last_successful_update_at_utc,canonical=True)>at
                    or mat.state == "current" and mat.lag_seconds is None):
                raise ValueError
        age = None
        if last is not None:
            event = check_service(last, LastServiceObservationV1, "observed_at", start)
            age = (at - event).total_seconds()
            if event >= recent:
                if not value.recent_services or (last.service_id, last.observed_at) != (value.recent_services[0].service_id, value.recent_services[0].last_observed_at): raise ValueError
            elif value.recent_services: raise ValueError
        elif value.recent_services or value.service_categories: raise ValueError
        if value.identity_binding_state != "authoritative" and (last is not None or value.recent_services): raise ValueError
        expected_evidence = materialized_evidence_state(value.identity_binding_state,last,coverage,value.materialization) if v3 else evidence_state(value.identity_binding_state,last,coverage)
        if value.freshness_state != freshness(age, coverage) or value.evidence_state != expected_evidence: raise ValueError
        if coverage.recognition_state == "unavailable" and last is not None: raise ValueError
        expected_availability = materialized_availability(value.identity_binding_state,coverage,value.materialization) if v3 else availability(value.identity_binding_state,coverage)
        if value.availability_state != expected_availability: raise ValueError
        result = asdict(value)
        result["recent_services"] = list(result["recent_services"])
        result["service_categories"] = list(result["service_categories"])
        # The HTTP envelope owns the 16-KiB bound and its response_too_large code.
        return result
    except Exception:
        raise ServiceUnavailable("recognition_unavailable") from None
