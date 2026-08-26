"""Explicit public DTO allowlist for Home Activity."""

from __future__ import annotations

from typing import Any

from app.analytics.models import (
    HomeActivityCoverage,
    HomeActivityResult,
    HomeActivityTraffic,
    HomeActivityVisits,
)


class HomeActivitySerializationError(ValueError):
    """An Activity model violates the public response contract."""


_STATUSES = frozenset({"complete", "partial", "unavailable"})
_FRESHNESS = frozenset({"fresh", "stale", "unavailable"})
_QUALITY_REASONS = frozenset({
    "coverage_start_unknown",
    "requested_before_coverage_start",
    "requested_after_coverage_through",
    "source_unavailable",
    "query_deadline",
    "opening_authorization_evidence_missing",
    "authorization_chronology_anomaly",
    "pending_offline_events",
    "invalid_offline_events",
    "missing_reported_traffic",
    "missing_controller_time",
    "semantic_replay_suppressed",
    "unsupported_processing_result",
    "reader_stale",
    "reader_unavailable",
})


def serialize_home_activity(value: HomeActivityResult) -> dict[str, Any]:
    if not isinstance(value, HomeActivityResult):
        raise HomeActivitySerializationError("Activity result is invalid")
    if not value.guest_ssids or any(not item for item in value.guest_ssids):
        raise HomeActivitySerializationError("Activity scope is invalid")
    result = {
        "evaluated_at_utc": value.evaluated_at_utc,
        "timezone": value.timezone,
        "guest_ssids": list(value.guest_ssids),
        "range": {
            "requested": dict(value.range["requested"]),
            "resolved": dict(value.range["resolved"]),
        },
        "authorized_visits": _visits(value.authorized_visits),
        "traffic": _traffic(value.traffic),
        "next_site_midnight_utc": value.next_site_midnight_utc,
    }
    return result


def _coverage(value: HomeActivityCoverage) -> dict[str, Any]:
    if (
        value.status not in _STATUSES
        or value.fully_covered != (value.status == "complete")
        or len(set(value.quality_reasons)) != len(value.quality_reasons)
        or any(reason not in _QUALITY_REASONS for reason in value.quality_reasons)
    ):
        raise HomeActivitySerializationError("Activity coverage is invalid")
    if value.fully_covered and value.quality_reasons:
        raise HomeActivitySerializationError("Activity coverage is invalid")
    return {
        "coverage_from_utc": value.coverage_from_utc,
        "coverage_through_utc": value.coverage_through_utc,
        "covered_from_utc": value.covered_from_utc,
        "covered_through_utc": value.covered_through_utc,
        "fully_covered": value.fully_covered,
        "status": value.status,
        "quality_reasons": list(value.quality_reasons),
    }


def _visits(value: HomeActivityVisits) -> dict[str, Any]:
    if (
        value.status not in _STATUSES
        or value.status != value.coverage.status
        or not (
            (
                value.status == "unavailable"
                and value.value is None
                and value.verified_visit_count is None
            )
            or (
                value.status != "unavailable"
                and type(value.verified_visit_count) is int
                and value.verified_visit_count >= 0
                and value.value == value.verified_visit_count
            )
        )
        or type(value.integrity_anomaly_count) is not int
        or value.integrity_anomaly_count < 0
    ):
        raise HomeActivitySerializationError("Activity Visit metric is invalid")
    return {
        "value": value.value,
        "status": value.status,
        "cohort": value.cohort,
        "source_kind": value.source_kind,
        "verified_visit_count": value.verified_visit_count,
        "integrity_anomaly_count": value.integrity_anomaly_count,
        "coverage": _coverage(value.coverage),
        "earliest_persisted_evidence_at": value.earliest_persisted_evidence_at,
        "latest_persisted_evidence_at": value.latest_persisted_evidence_at,
    }


def _traffic(value: HomeActivityTraffic) -> dict[str, Any]:
    counts = {
        "eligible_terminal_event_count": value.eligible_terminal_event_count,
        "included_fingerprint_count": value.included_fingerprint_count,
        "unmatched_included_event_count": value.unmatched_included_event_count,
        "pending_event_count": value.pending_event_count,
        "invalid_event_count": value.invalid_event_count,
        "missing_traffic_count": value.missing_traffic_count,
        "missing_controller_time_count": value.missing_controller_time_count,
        "semantic_duplicate_count": value.semantic_duplicate_count,
        "other_excluded_event_count": value.other_excluded_event_count,
    }
    if (
        value.status not in _STATUSES
        or value.status != value.coverage.status
        or value.estimated is not True
        or not (
            (value.status == "unavailable" and value.bytes is None)
            or (
                value.status != "unavailable"
                and type(value.bytes) is int
                and value.bytes >= 0
            )
        )
        or value.ingestion_freshness not in _FRESHNESS
        or any(type(item) is not int or item < 0 for item in counts.values())
        or value.included_fingerprint_count > value.eligible_terminal_event_count
        or value.semantic_duplicate_count != (
            value.eligible_terminal_event_count
            - value.included_fingerprint_count
        )
    ):
        raise HomeActivitySerializationError("Activity Traffic metric is invalid")
    return {
        "bytes": value.bytes,
        "status": value.status,
        "estimated": True,
        "attribution": value.attribution,
        "source_kind": value.source_kind,
        **counts,
        "reader_watermark_at": value.reader_watermark_at,
        "ingestion_freshness": value.ingestion_freshness,
        "coverage": _coverage(value.coverage),
        "earliest_persisted_evidence_at": value.earliest_persisted_evidence_at,
        "latest_persisted_evidence_at": value.latest_persisted_evidence_at,
    }
