"""Read-only Authorized Visit and completed-session Traffic aggregates."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

from .models import (
    HomeActivityCoverage,
    HomeActivityResult,
    HomeActivityTraffic,
    HomeActivityVisits,
)
from .source_gateway import (
    AnalyticsQueryDeadlineExceeded,
    AnalyticsSourceError,
    AnalyticsSourceGateway,
    QueryDeadline,
)
from .validation import format_utc, parse_utc, require_site


class HomeActivityValidationError(ValueError):
    """Caller supplied an invalid Activity query context."""


class HomeActivitySourceUnavailable(RuntimeError):
    """Persisted Activity evidence cannot be read safely."""


class HomeActivityReadService:
    """Aggregate persisted Visit v2 facts without any provider path."""

    def __init__(
        self,
        gateway: AnalyticsSourceGateway,
        *,
        visit_source_available: Callable[[], bool] | None = None,
    ):
        self._gateway = gateway
        self._visit_source_available = visit_source_available or (lambda: True)

    def get_activity(
        self,
        *,
        site_id: str,
        guest_ssids: Sequence[str],
        range_payload: Mapping[str, Any],
        from_utc: str,
        to_utc: str,
        evaluated_at_utc: str,
        timezone_name: str,
        visits_coverage_from_utc: str | None,
        traffic_coverage_from_utc: str | None,
        traffic_fresh_max_age_seconds: int,
        traffic_stale_max_age_seconds: int,
        deadline: QueryDeadline,
        next_site_midnight_utc: str | None = None,
    ) -> HomeActivityResult:
        try:
            selected_site = require_site(site_id)
            start = parse_utc(from_utc, "from_utc")
            end = parse_utc(to_utc, "to_utc")
            evaluated = parse_utc(evaluated_at_utc, "evaluated_at_utc")
        except Exception as exc:
            raise HomeActivityValidationError("Activity range is invalid") from exc
        if start >= end or end > evaluated:
            raise HomeActivityValidationError("Activity range is invalid")
        scope = _scope(guest_ssids)
        if (
            type(traffic_fresh_max_age_seconds) is not int
            or type(traffic_stale_max_age_seconds) is not int
            or traffic_fresh_max_age_seconds < 1
            or traffic_stale_max_age_seconds <= traffic_fresh_max_age_seconds
        ):
            raise HomeActivityValidationError("Activity freshness policy is invalid")
        visits_from = _optional_utc(visits_coverage_from_utc, "visits coverage")
        traffic_from = _optional_utc(traffic_coverage_from_utc, "traffic coverage")
        try:
            raw = self._gateway.home_activity_data(
                site_id=selected_site,
                guest_ssids=scope,
                from_utc=from_utc,
                to_utc=to_utc,
                deadline=deadline,
            )
        except AnalyticsQueryDeadlineExceeded:
            raise
        except AnalyticsSourceError as exc:
            raise HomeActivitySourceUnavailable(
                "Activity persisted source is unavailable"
            ) from exc

        visits_raw = _mapping(raw.get("visits"))
        traffic_raw = _mapping(raw.get("traffic"))
        try:
            visits_available = bool(self._visit_source_available())
        except Exception:
            visits_available = False
        visits = _visits(
            visits_raw, start, end, visits_from, evaluated, visits_available
        )
        traffic = _traffic(
            traffic_raw,
            raw.get("reader_watermark_at"),
            start,
            end,
            traffic_from,
            evaluated,
            traffic_fresh_max_age_seconds,
            traffic_stale_max_age_seconds,
        )
        return HomeActivityResult(
            evaluated_at_utc=format_utc(evaluated),
            timezone=timezone_name,
            guest_ssids=scope,
            range=range_payload,
            authorized_visits=visits,
            traffic=traffic,
            next_site_midnight_utc=next_site_midnight_utc,
        )

    def explain(
        self,
        *,
        site_id: str,
        guest_ssids: Sequence[str],
        from_utc: str,
        to_utc: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, tuple[str, ...]]:
        return self._gateway.explain_home_activity(
            site_id=require_site(site_id),
            guest_ssids=_scope(guest_ssids),
            from_utc=from_utc,
            to_utc=to_utc,
            deadline=deadline,
        )


def _visits(raw, start, end, coverage_from, evaluated, source_available):
    verified = _count(raw, "verified_visit_count")
    anomalies = _count(raw, "integrity_anomaly_count")
    if not source_available:
        coverage = _unavailable_coverage(
            _coverage(
                start, end, coverage_from, None, ("source_unavailable",)
            ),
            "source_unavailable",
        )
        return HomeActivityVisits(
            value=None,
            status="unavailable",
            cohort="visit_opening_authorization",
            source_kind="visit_lifecycle",
            verified_visit_count=None,
            integrity_anomaly_count=0,
            coverage=coverage,
            earliest_persisted_evidence_at=None,
            latest_persisted_evidence_at=None,
        )
    reasons = []
    if anomalies:
        reasons.append("opening_authorization_evidence_missing")
    coverage = _coverage(
        start, end, coverage_from, evaluated, reasons
    )
    earliest = _evidence(raw.get("earliest_persisted_evidence_at"))
    latest = _evidence(raw.get("latest_persisted_evidence_at"))
    return HomeActivityVisits(
        value=verified,
        status=coverage.status,
        cohort="visit_opening_authorization",
        source_kind="visit_lifecycle",
        verified_visit_count=verified,
        integrity_anomaly_count=anomalies,
        coverage=coverage,
        earliest_persisted_evidence_at=earliest,
        latest_persisted_evidence_at=latest,
    )


def _traffic(raw, watermark_value, start, end, coverage_from, evaluated, fresh, stale):
    unsupported = _count(raw, "unsupported_result_count")
    watermark = _evidence(watermark_value)
    freshness = "unavailable"
    reader_reason = "reader_unavailable"
    coverage_through = None
    if watermark is not None:
        watermark_time = parse_utc(watermark, "reader watermark")
        age = (evaluated - watermark_time).total_seconds()
        if age < 0:
            reader_reason = "reader_unavailable"
        elif age <= fresh:
            coverage_through = watermark_time
            freshness = "fresh"
            reader_reason = ""
        elif age <= stale:
            coverage_through = watermark_time
            freshness = "stale"
            reader_reason = "reader_stale"
        else:
            coverage_through = watermark_time
            reader_reason = "reader_unavailable"

    pending = _count(raw, "pending_event_count")
    invalid = _count(raw, "invalid_event_count")
    missing_traffic = _count(raw, "missing_traffic_count")
    missing_time = _count(raw, "missing_controller_time_count")
    duplicates = _count(raw, "semantic_duplicate_count")
    other = _count(raw, "other_excluded_event_count")
    reasons = []
    # Reader freshness describes the current ingestion process.  A historical
    # range already ending at/before the durable watermark remains complete.
    if coverage_through is None or end > coverage_through:
        if reader_reason:
            reasons.append(reader_reason)
    if pending:
        reasons.append("pending_offline_events")
    if invalid:
        reasons.append("invalid_offline_events")
    if missing_traffic:
        reasons.append("missing_reported_traffic")
    if missing_time:
        reasons.append("missing_controller_time")
    if other:
        reasons.append("missing_reported_traffic")
    coverage = _coverage(start, end, coverage_from, coverage_through, reasons)
    if unsupported:
        coverage = _unavailable_coverage(
            coverage, "unsupported_processing_result"
        )
    return HomeActivityTraffic(
        bytes=None if unsupported else _count(raw, "traffic_bytes"),
        status=coverage.status,
        estimated=True,
        attribution="completed_session_end",
        source_kind="om" + "ada_offline_reported_traffic",
        eligible_terminal_event_count=_count(
            raw, "eligible_terminal_event_count"
        ),
        included_fingerprint_count=_count(raw, "included_fingerprint_count"),
        unmatched_included_event_count=_count(
            raw, "unmatched_included_event_count"
        ),
        pending_event_count=pending,
        invalid_event_count=invalid,
        missing_traffic_count=missing_traffic,
        missing_controller_time_count=missing_time,
        semantic_duplicate_count=duplicates,
        other_excluded_event_count=other,
        reader_watermark_at=watermark,
        ingestion_freshness=freshness,
        coverage=coverage,
        earliest_persisted_evidence_at=_evidence(
            raw.get("earliest_persisted_evidence_at")
        ),
        latest_persisted_evidence_at=_evidence(
            raw.get("latest_persisted_evidence_at")
        ),
    )


def _coverage(start, end, coverage_from, coverage_through, extra_reasons):
    reasons = list(dict.fromkeys(extra_reasons))
    if coverage_from is None:
        reasons.append("coverage_start_unknown")
    elif start < coverage_from:
        reasons.append("requested_before_coverage_start")
    if coverage_through is None:
        if "reader_unavailable" not in reasons:
            reasons.append("source_unavailable")
    elif end > coverage_through:
        reasons.append("requested_after_coverage_through")
    covered_from = (
        None if coverage_from is None else max(start, coverage_from)
    )
    covered_through = (
        None if coverage_through is None else min(end, coverage_through)
    )
    if (
        covered_from is None
        or covered_through is None
        or covered_from >= covered_through
    ):
        covered_from_text = covered_through_text = None
    else:
        covered_from_text = format_utc(covered_from)
        covered_through_text = format_utc(covered_through)
    reasons = list(dict.fromkeys(reasons))
    complete = not reasons
    return HomeActivityCoverage(
        coverage_from_utc=(
            None if coverage_from is None else format_utc(coverage_from)
        ),
        coverage_through_utc=(
            None if coverage_through is None else format_utc(coverage_through)
        ),
        covered_from_utc=covered_from_text,
        covered_through_utc=covered_through_text,
        fully_covered=complete,
        status="complete" if complete else "partial",
        quality_reasons=tuple(reasons),
    )


def _unavailable_coverage(
    value: HomeActivityCoverage, reason: str
) -> HomeActivityCoverage:
    reasons = tuple(dict.fromkeys((*value.quality_reasons, reason)))
    return HomeActivityCoverage(
        coverage_from_utc=value.coverage_from_utc,
        coverage_through_utc=value.coverage_through_utc,
        covered_from_utc=value.covered_from_utc,
        covered_through_utc=value.covered_through_utc,
        fully_covered=False,
        status="unavailable",
        quality_reasons=reasons,
    )


def _scope(values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise HomeActivityValidationError("Activity guest scope is invalid")
    result = tuple(values)
    if (
        not result
        or len(set(result)) != len(result)
        or any(
            not isinstance(value, str)
            or not value
            or value.strip() != value
            for value in result
        )
    ):
        raise HomeActivityValidationError("Activity guest scope is invalid")
    return result


def _mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise HomeActivitySourceUnavailable("Activity aggregate is malformed")
    return value


def _count(value: Mapping[str, Any], name: str) -> int:
    item = value.get(name)
    if type(item) is not int or item < 0:
        raise HomeActivitySourceUnavailable("Activity aggregate is malformed")
    return item


def _optional_utc(value: str | None, name: str) -> datetime | None:
    if value is None:
        return None
    try:
        return parse_utc(value, name)
    except Exception as exc:
        raise HomeActivityValidationError("Activity coverage is invalid") from exc


def _evidence(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return format_utc(parse_utc(value, "Activity evidence timestamp"))
    except Exception as exc:
        raise HomeActivitySourceUnavailable(
            "Activity evidence timestamp is invalid"
        ) from exc
