"""Fail-closed projection for canonical Historical Traffic results."""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any, Mapping

from app.analytics.validation import parse_utc

from .traffic_network_ranges import TrafficNetworkRange


class HistoricalTrafficSerializationError(ValueError):
    """Historical Traffic data violates the safe Admin DTO contract."""


_RESULT_COVERAGE = {
    "ok": "complete",
    "partial": "partial",
    "insufficient_data": "none",
}
_BUCKET_STATUSES = frozenset({"complete", "partial", "none"})
_SOURCES = frozenset({"wired", "lan"})
_RANGE_CONSTANTS = {
    "unit": "Mbps",
    "aggregation": "mean_of_complete_site_rate_samples",
    "metric_version": "network_traffic_history.v1",
    "source_kind": "observation_ap_dynamic",
    "sample_timestamp_semantics": "cycle_finished_at",
    "bucket_alignment": "range_start_utc",
    "max_site_history_buckets": 720,
    "max_site_sample_source_skew_seconds": 60,
}
_PRODUCT_RANGES = {
    "24h": (86400, 300, 288),
    "7d": (604800, 900, 672),
}
_COVERAGE_FIELDS = (
    "status", "available_from_utc", "available_through_utc",
    "source_watermark_utc", "source_age_seconds", "bucket_count",
    "complete_bucket_count", "partial_bucket_count", "missing_bucket_count",
    "canonical_cycle_count", "complete_site_sample_count",
    "excluded_site_sample_count", "gap_bucket_count",
    "source_transition_count",
)
_QUALITY_FIELDS = (
    "partial_cycle_count", "failed_cycle_count", "shutdown_cycle_count",
    "abandoned_cycle_count", "running_cycle_count", "no_baseline_count",
    "counter_reset_count", "gap_too_large_count", "invalid_elapsed_count",
    "source_unavailable_count", "source_skew_excluded_sample_count",
    "integrity_failure_count",
)
_BUCKET_COUNT_FIELDS = (
    "complete_site_sample_count", "excluded_site_sample_count",
    "gap_count_over_threshold", "selected_source_skew_excluded_sample_count",
)
_STATISTICS_STATUSES = frozenset({"ok", "partial", "insufficient_data"})
_STATISTICS_CONSTANTS = {
    "metric_version": "network_traffic_period_statistics.v1",
    "average_method": "right_endpoint_sample_hold_time_weighted.v1",
    "peak_method": "max_accepted_complete_site_sample.v1",
    "unit": "Mbps",
}
_STATISTICS_VALUE_FIELDS = ("download_mbps", "upload_mbps", "total_mbps")
_STATISTICS_COUNT_FIELDS = (
    "candidate_interval_count", "accepted_interval_count",
    "excluded_gap_interval_count",
    "excluded_source_transition_interval_count",
    "invalid_period_interval_count", "accepted_peak_sample_count",
)
_AP_STATUSES = frozenset({
    "ok", "partial", "insufficient_data", "unsupported_population",
})
_AP_ITEM_STATUSES = frozenset({"complete", "partial", "insufficient_data"})
_AP_HISTORY_STATUSES = frozenset({"complete", "partial", "insufficient_data"})
_AP_POINT_STATUSES = frozenset({"complete", "partial", "none"})
_AP_NOW_STATUSES = frozenset({"valid", "partial", "unavailable"})
_AP_NAME_SOURCES = frozenset({"current", "historical", "mac_fallback"})
_AP_RATE_REASONS = frozenset({
    "ok", "no_baseline", "counter_reset", "gap_too_large",
    "invalid_elapsed", "source_unavailable",
})
_AP_FRESHNESS = frozenset({"fresh", "stale", "unavailable"})
_AP_FRESHNESS_REASONS = frozenset({
    "within_freshness_window", "within_stale_window", "age_exceeded",
    "clock_anomaly", "no_complete_snapshot", "source_unavailable",
})
_AP_MAC = re.compile(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}")


def serialize_historical_traffic(
    value: Any,
    site_id: str,
    *,
    resolved_range: TrafficNetworkRange,
    include_period_statistics: bool = False,
    include_peak_load: bool = False,
    include_ap_traffic: bool = False,
) -> dict[str, Any]:
    """Validate immutable Analytics output and expose only product-safe fields."""
    if getattr(value, "status", None) not in _RESULT_COVERAGE:
        raise HistoricalTrafficSerializationError("result status is invalid")
    source_range = getattr(value, "range", None)
    if source_range is None or getattr(source_range, "site_id", None) != site_id:
        raise HistoricalTrafficSerializationError("range Site is invalid")
    try:
        expected_duration, expected_bucket_seconds, expected_bucket_count = (
            _PRODUCT_RANGES[resolved_range.id]
        )
    except KeyError as exc:
        raise HistoricalTrafficSerializationError("range id is invalid") from exc
    expected = {
        "from_utc": resolved_range.from_utc,
        "to_utc": resolved_range.to_utc,
        "evaluated_at_utc": resolved_range.evaluated_at_utc,
        "bucket_seconds": expected_bucket_seconds,
        "bucket_count": expected_bucket_count,
        **_RANGE_CONSTANTS,
    }
    if any(getattr(source_range, key, None) != expected_value for key, expected_value in expected.items()):
        raise HistoricalTrafficSerializationError("range contract is invalid")
    start = _utc(source_range.from_utc)
    end = _utc(source_range.to_utc)
    evaluated = _utc(source_range.evaluated_at_utc)
    duration = int((end - start).total_seconds())
    if duration != expected_duration or evaluated != end:
        raise HistoricalTrafficSerializationError("range duration is invalid")

    buckets = tuple(getattr(value, "buckets", ()))
    if len(buckets) != expected_bucket_count or len(buckets) > 720:
        raise HistoricalTrafficSerializationError("bucket count is invalid")
    projected_buckets = []
    bucket_status_counts = {"complete": 0, "partial": 0, "none": 0}
    cursor = start
    for bucket in buckets:
        bucket_start = _utc(getattr(bucket, "bucket_start_utc", None))
        bucket_end = _utc(getattr(bucket, "bucket_end_utc", None))
        if (
            bucket_start != cursor
            or (bucket_end - bucket_start).total_seconds()
            != expected_bucket_seconds
            or bucket_end > end
        ):
            raise HistoricalTrafficSerializationError("bucket boundaries are invalid")
        cursor = bucket_end
        status = getattr(bucket, "status", None)
        if status not in _BUCKET_STATUSES:
            raise HistoricalTrafficSerializationError("bucket status is invalid")
        selected = getattr(bucket, "selected_source", None)
        values = tuple(getattr(bucket, name, None) for name in (
            "download_mbps", "upload_mbps", "total_mbps"
        ))
        counts = {name: _count(getattr(bucket, name, None)) for name in _BUCKET_COUNT_FIELDS}
        if status == "none":
            if (
                any(item is not None for item in values)
                or counts["complete_site_sample_count"] != 0
                or (selected is not None and selected not in _SOURCES)
                or (
                    selected is None
                    and getattr(bucket, "selection_reason", None)
                    != "no_canonical_samples"
                )
            ):
                raise HistoricalTrafficSerializationError("empty bucket is invalid")
        else:
            if selected not in _SOURCES or counts["complete_site_sample_count"] == 0:
                raise HistoricalTrafficSerializationError("usable bucket source is invalid")
            numeric = tuple(_number(item) for item in values)
            if not math.isclose(numeric[2], numeric[0] + numeric[1], rel_tol=1e-9, abs_tol=1e-9):
                raise HistoricalTrafficSerializationError("bucket total is invalid")
            values = numeric
        bucket_status_counts[status] += 1
        projected_buckets.append({
            "bucket_start_utc": bucket.bucket_start_utc,
            "bucket_end_utc": bucket.bucket_end_utc,
            "download_mbps": values[0],
            "upload_mbps": values[1],
            "total_mbps": values[2],
            "status": status,
            "selected_source": selected,
            "selection_reason": _text(getattr(bucket, "selection_reason", None)),
            "source_changed_from_previous": _boolean(getattr(bucket, "source_changed_from_previous", None)),
            **counts,
        })
    if cursor != end:
        raise HistoricalTrafficSerializationError("bucket coverage is incomplete")

    coverage = getattr(value, "coverage", None)
    if coverage is None or getattr(coverage, "status", None) != _RESULT_COVERAGE[value.status]:
        raise HistoricalTrafficSerializationError("coverage status is invalid")
    coverage_result = _project(coverage, _COVERAGE_FIELDS)
    for key in _COVERAGE_FIELDS[5:]:
        coverage_result[key] = _count(coverage_result[key])
    coverage_result["source_age_seconds"] = _optional_number(coverage_result["source_age_seconds"])
    for key in ("available_from_utc", "available_through_utc", "source_watermark_utc"):
        coverage_result[key] = _optional_utc(coverage_result[key])
    if coverage_result["bucket_count"] != len(buckets):
        raise HistoricalTrafficSerializationError("coverage bucket count is invalid")
    if sum(coverage_result[key] for key in (
        "complete_bucket_count", "partial_bucket_count", "missing_bucket_count"
    )) != len(buckets):
        raise HistoricalTrafficSerializationError("coverage bucket sum is invalid")
    aggregate_names = {
        "complete": "complete_bucket_count",
        "partial": "partial_bucket_count",
        "none": "missing_bucket_count",
    }
    if any(coverage_result[aggregate_names[name]] != count for name, count in bucket_status_counts.items()):
        raise HistoricalTrafficSerializationError("coverage aggregate is invalid")
    if coverage_result["complete_site_sample_count"] != sum(
        item["complete_site_sample_count"] for item in projected_buckets
    ):
        raise HistoricalTrafficSerializationError("sample aggregate is invalid")
    if coverage_result["excluded_site_sample_count"] != sum(
        item["excluded_site_sample_count"] for item in projected_buckets
    ):
        raise HistoricalTrafficSerializationError("excluded aggregate is invalid")
    if coverage_result["gap_bucket_count"] != sum(
        item["gap_count_over_threshold"] > 0 for item in projected_buckets
    ):
        raise HistoricalTrafficSerializationError("gap aggregate is invalid")
    if coverage_result["source_transition_count"] != sum(
        item["source_changed_from_previous"] for item in projected_buckets
    ):
        raise HistoricalTrafficSerializationError("transition aggregate is invalid")

    quality = _project(getattr(value, "quality", None), _QUALITY_FIELDS)
    quality = {key: _count(item) for key, item in quality.items()}
    range_result = {"id": resolved_range.id, **expected}
    result = {
        "status": value.status,
        "range": range_result,
        "buckets": projected_buckets,
        "coverage": coverage_result,
        "quality": quality,
    }
    statistics = getattr(value, "period_statistics", None)
    if include_period_statistics:
        result["period_statistics"] = _statistics(
            statistics,
            history_status=value.status,
            range_seconds=float(expected_duration),
            complete_site_sample_count=coverage_result[
                "complete_site_sample_count"
            ],
        )
    elif statistics is not None:
        raise HistoricalTrafficSerializationError(
            "unrequested period Statistics is invalid"
        )
    peak_load = getattr(value, "peak_load", None)
    if include_peak_load:
        if not include_period_statistics:
            raise HistoricalTrafficSerializationError(
                "Peak Load requires period Statistics"
            )
        result["peak_load"] = _peak_load(
            peak_load,
            history_status=value.status,
            range_start=start,
            range_end=end,
            buckets=projected_buckets,
            statistics=result["period_statistics"],
        )
    elif peak_load is not None:
        raise HistoricalTrafficSerializationError(
            "unrequested Peak Load is invalid"
        )
    ap_traffic = getattr(value, "ap_traffic", None)
    if include_ap_traffic:
        result["ap_traffic"] = _ap_traffic(
            ap_traffic,
            bucket_count=len(projected_buckets),
            history_status=value.status,
            site_id=site_id,
        )
    elif ap_traffic is not None:
        raise HistoricalTrafficSerializationError(
            "unrequested AP Traffic is invalid"
        )
    return result


def _ap_traffic(
    value: Any, *, bucket_count: int, history_status: str, site_id: str,
) -> dict[str, Any]:
    constants = {
        "metric_version": "network_traffic_by_ap.v1",
        "unit": "Mbps",
        "history_series_encoding": "outer_history_bucket_aligned_du.v1",
        "history_bucket_method": (
            "mean_of_accepted_ap_rates_for_canonical_site_bucket_samples.v1"
        ),
        "average_method": "right_endpoint_ap_sample_hold_time_weighted.v1",
        "peak_method": "max_accepted_complete_ap_sample.v1",
        "ap_order_method": "ap_mac_ascending.v1",
    }
    if value is None or getattr(value, "status", None) not in _AP_STATUSES or any(
        getattr(value, key, None) != expected for key, expected in constants.items()
    ):
        raise HistoricalTrafficSerializationError("AP Traffic contract is invalid")
    population = getattr(value, "population", None)
    if population is None or getattr(
        population, "population_method", None
    ) != "current_union_historical_validated.v1":
        raise HistoricalTrafficSerializationError("AP population method is invalid")
    population_result = {
        "population_method": population.population_method,
        "population_count": _count(getattr(population, "population_count", None)),
        "current_population_count": _count(
            getattr(population, "current_population_count", None)
        ),
        "historical_population_count": _count(
            getattr(population, "historical_population_count", None)
        ),
        "supported_max_ap_count": _count(
            getattr(population, "supported_max_ap_count", None)
        ),
        "returned_ap_count": _count(
            getattr(population, "returned_ap_count", None)
        ),
        "population_complete": _boolean(
            getattr(population, "population_complete", None)
        ),
    }
    if (
        population_result["supported_max_ap_count"] != 12
        or population_result["current_population_count"]
        > population_result["population_count"]
        or population_result["historical_population_count"]
        > population_result["population_count"]
    ):
        raise HistoricalTrafficSerializationError("AP population is invalid")
    items = tuple(getattr(value, "items", ()))
    if value.status == "unsupported_population":
        if (
            population_result["population_count"] <= 12
            or population_result["returned_ap_count"] != 0
            or population_result["population_complete"] is not False
            or items
            or getattr(value, "current_snapshot", None) is not None
        ):
            raise HistoricalTrafficSerializationError(
                "unsupported AP population is invalid"
            )
        return {
            "status": value.status,
            **constants,
            "population": population_result,
            "current_snapshot": None,
            "items": [],
        }
    if (
        population_result["population_count"] > 12
        or population_result["returned_ap_count"]
        != population_result["population_count"]
        or population_result["population_complete"] is not True
        or len(items) != population_result["population_count"]
    ):
        raise HistoricalTrafficSerializationError("supported AP population is invalid")
    projected = [_ap_item(item, bucket_count) for item in items]
    macs = [item["ap_mac"] for item in projected]
    if macs != sorted(macs) or len(set(macs)) != len(macs):
        raise HistoricalTrafficSerializationError("AP order is invalid")
    any_numeric = any(
        item["history"]["coverage"]["accepted_sample_count"] > 0
        or item["now"]["download_mbps"] is not None
        or item["now"]["upload_mbps"] is not None
        for item in projected
    )
    snapshot = _ap_snapshot(getattr(value, "current_snapshot", None), site_id)
    for item in projected:
        observed = item["now"]["observed_at"]
        if observed is None:
            continue
        if snapshot is None or snapshot["observed_at"] is None or not (
            _utc(snapshot["observed_at"])
            <= _utc(observed)
            <= _utc(snapshot["newest_observed_at"])
        ):
            raise HistoricalTrafficSerializationError(
                "AP Now snapshot boundary is invalid"
            )
    complete = (
        history_status == "ok"
        and population_result["population_count"] > 0
        and all(item["status"] == "complete" for item in projected)
        and snapshot is not None
        and snapshot["freshness_status"] == "fresh"
    )
    if (
        (value.status == "ok" and not complete)
        or (value.status == "partial" and (complete or not any_numeric))
        or (value.status == "insufficient_data" and any_numeric)
    ):
        raise HistoricalTrafficSerializationError("AP Traffic status is invalid")
    return {
        "status": value.status,
        **constants,
        "population": population_result,
        "current_snapshot": snapshot,
        "items": projected,
    }


def _ap_item(value: Any, bucket_count: int) -> dict[str, Any]:
    mac = getattr(value, "ap_mac", None)
    name = getattr(value, "display_name", None)
    name_source = getattr(value, "display_name_source", None)
    status = getattr(value, "status", None)
    if (
        not isinstance(mac, str) or _AP_MAC.fullmatch(mac) is None
        or not isinstance(name, str) or not name or len(name) > 256
        or any(ord(character) < 32 for character in name)
        or name_source not in _AP_NAME_SOURCES
        or status not in _AP_ITEM_STATUSES
        or (name_source == "mac_fallback" and name != mac)
    ):
        raise HistoricalTrafficSerializationError("AP item identity is invalid")
    series = getattr(value, "series", None)
    if (
        series is None
        or getattr(series, "encoding", None)
        != "outer_history_bucket_aligned_du.v1"
        or getattr(series, "bucket_count", None) != bucket_count
    ):
        raise HistoricalTrafficSerializationError("AP series contract is invalid")
    statuses = tuple(getattr(series, "status", ()))
    downloads = tuple(getattr(series, "download_mbps", ()))
    uploads = tuple(getattr(series, "upload_mbps", ()))
    if not (len(statuses) == len(downloads) == len(uploads) == bucket_count):
        raise HistoricalTrafficSerializationError("AP series length is invalid")
    for point_status, download, upload in zip(statuses, downloads, uploads):
        if point_status not in _AP_POINT_STATUSES:
            raise HistoricalTrafficSerializationError("AP point status is invalid")
        if point_status == "none":
            if download is not None or upload is not None:
                raise HistoricalTrafficSerializationError("AP missing point has values")
        else:
            _number(download)
            _number(upload)
    average = _statistics_values(getattr(value, "average", None))
    peak = _statistics_values(getattr(value, "peak", None))
    coverage = _ap_coverage(getattr(value, "coverage", None), statuses)
    now = _ap_now(getattr(value, "now", None))
    historical_numeric = coverage["accepted_sample_count"] > 0
    current_numeric = now["download_mbps"] is not None or now["upload_mbps"] is not None
    if (
        (coverage["ap_accepted_interval_seconds"] == 0
         and any(item is not None for item in average.values()))
        or (coverage["ap_accepted_interval_seconds"] > 0
            and any(item is None for item in average.values()))
        or (coverage["accepted_sample_count"] == 0
            and any(item is not None for item in peak.values()))
        or (coverage["accepted_sample_count"] > 0
            and any(item is None for item in peak.values()))
    ):
        raise HistoricalTrafficSerializationError("AP aggregate values are invalid")
    if average["download_mbps"] is not None and not math.isclose(
        average["total_mbps"],
        average["download_mbps"] + average["upload_mbps"],
        rel_tol=1e-9,
        abs_tol=1e-9,
    ):
        raise HistoricalTrafficSerializationError("AP Average total is invalid")
    if peak["download_mbps"] is not None and (
        peak["total_mbps"] + 1e-9 < peak["download_mbps"]
        or peak["total_mbps"] + 1e-9 < peak["upload_mbps"]
        or peak["total_mbps"]
        > peak["download_mbps"] + peak["upload_mbps"] + 1e-9
    ):
        raise HistoricalTrafficSerializationError("AP Peak total is invalid")
    complete = coverage["status"] == "complete" and now["status"] == "valid"
    if (
        (status == "complete" and not complete)
        or (status == "partial" and (complete or not (historical_numeric or current_numeric)))
        or (status == "insufficient_data" and (historical_numeric or current_numeric))
    ):
        raise HistoricalTrafficSerializationError("AP item status is invalid")
    return {
        "ap_mac": mac,
        "display_name": name,
        "display_name_source": name_source,
        "status": status,
        "history": {
            "status": coverage["status"],
            "series": {
                "encoding": series.encoding,
                "bucket_count": bucket_count,
                "status": list(statuses),
                "download_mbps": list(downloads),
                "upload_mbps": list(uploads),
            },
            "average": average,
            "peak": peak,
            "coverage": coverage,
        },
        "now": now,
    }


def _ap_coverage(value: Any, statuses: tuple[str, ...]) -> dict[str, Any]:
    if value is None or getattr(value, "status", None) not in _AP_HISTORY_STATUSES:
        raise HistoricalTrafficSerializationError("AP coverage status is invalid")
    count_fields = (
        "bucket_count", "complete_bucket_count", "partial_bucket_count",
        "missing_bucket_count", "sample_opportunity_count", "accepted_sample_count",
        "no_baseline_count", "counter_reset_count", "gap_too_large_count",
        "invalid_elapsed_count", "source_unavailable_count",
        "missing_selected_source_sample_count",
        "source_transition_excluded_interval_count",
    )
    result = {name: _count(getattr(value, name, None)) for name in count_fields}
    result["status"] = value.status
    result["site_accepted_interval_seconds"] = _number(
        getattr(value, "site_accepted_interval_seconds", None)
    )
    result["ap_accepted_interval_seconds"] = _number(
        getattr(value, "ap_accepted_interval_seconds", None)
    )
    ratio = getattr(value, "ap_interval_coverage_ratio", None)
    result["ap_interval_coverage_ratio"] = (
        None if ratio is None else _number(ratio)
    )
    expected_counts = {
        "complete": statuses.count("complete"),
        "partial": statuses.count("partial"),
        "none": statuses.count("none"),
    }
    if (
        result["bucket_count"] != len(statuses)
        or result["complete_bucket_count"] != expected_counts["complete"]
        or result["partial_bucket_count"] != expected_counts["partial"]
        or result["missing_bucket_count"] != expected_counts["none"]
        or result["accepted_sample_count"] > result["sample_opportunity_count"]
        or result["ap_accepted_interval_seconds"]
        > result["site_accepted_interval_seconds"]
    ):
        raise HistoricalTrafficSerializationError("AP coverage evidence is invalid")
    site_seconds = result["site_accepted_interval_seconds"]
    expected_ratio = (
        result["ap_accepted_interval_seconds"] / site_seconds
        if site_seconds else None
    )
    if ratio is None:
        if expected_ratio is not None:
            raise HistoricalTrafficSerializationError("AP coverage ratio is invalid")
    elif expected_ratio is None or not math.isclose(
        float(ratio), expected_ratio, rel_tol=1e-9, abs_tol=1e-9
    ):
        raise HistoricalTrafficSerializationError("AP coverage ratio is invalid")
    return result


def _ap_now(value: Any) -> dict[str, Any]:
    if value is None or getattr(value, "status", None) not in _AP_NOW_STATUSES:
        raise HistoricalTrafficSerializationError("AP Now status is invalid")
    download = _optional_number(getattr(value, "download_mbps", None))
    upload = _optional_number(getattr(value, "upload_mbps", None))
    total = _optional_number(getattr(value, "total_mbps", None))
    download_reason = getattr(value, "download_reason", None)
    upload_reason = getattr(value, "upload_reason", None)
    selected = getattr(value, "selected_source", None)
    observed = _optional_utc(getattr(value, "observed_at", None))
    age = _optional_number(getattr(value, "age_seconds", None))
    if download_reason not in _AP_RATE_REASONS or upload_reason not in _AP_RATE_REASONS:
        raise HistoricalTrafficSerializationError("AP Now reason is invalid")
    if total is not None and (
        download is None or upload is None
        or not math.isclose(total, download + upload, rel_tol=1e-9, abs_tol=1e-9)
    ):
        raise HistoricalTrafficSerializationError("AP Now total is invalid")
    if value.status == "valid" and (
        download is None or upload is None or total is None or selected not in _SOURCES
        or observed is None or age is None
    ):
        raise HistoricalTrafficSerializationError("AP valid Now is invalid")
    if value.status == "partial" and (
        (download is None and upload is None) or selected not in _SOURCES
        or observed is None or age is None
    ):
        raise HistoricalTrafficSerializationError("AP partial Now is invalid")
    if value.status == "unavailable" and any(
        item is not None for item in (download, upload, total)
    ):
        raise HistoricalTrafficSerializationError("AP unavailable Now has values")
    if selected is not None and selected not in _SOURCES:
        raise HistoricalTrafficSerializationError("AP Now source is invalid")
    return {
        "status": value.status,
        "download_mbps": download,
        "upload_mbps": upload,
        "total_mbps": total,
        "download_reason": download_reason,
        "upload_reason": upload_reason,
        "observed_at": observed,
        "age_seconds": age,
        "selected_source": selected,
    }


def _ap_snapshot(value: Any, site_id: str) -> dict[str, Any] | None:
    if value is None:
        return None
    cycle_id = getattr(value, "cycle_id", None)
    freshness = getattr(value, "freshness_status", None)
    reason = getattr(value, "freshness_reason", None)
    selected = getattr(value, "selected_source", None)
    if (
        not isinstance(cycle_id, str) or not cycle_id
        or getattr(value, "source_kind", None) != "observation_ap_dynamic"
        or getattr(value, "site_id", None) != site_id
        or getattr(value, "complete", None) is not True
        or freshness not in _AP_FRESHNESS
        or reason not in _AP_FRESHNESS_REASONS
        or selected not in _SOURCES
    ):
        raise HistoricalTrafficSerializationError("AP current snapshot is invalid")
    evaluated = getattr(value, "evaluated_at", None)
    _utc(evaluated)
    observed = _optional_utc(getattr(value, "observed_at", None))
    newest = _optional_utc(getattr(value, "newest_observed_at", None))
    if (observed is None) != (newest is None):
        raise HistoricalTrafficSerializationError("AP snapshot timestamps are invalid")
    if observed is not None and not (
        _utc(observed) <= _utc(newest) <= _utc(evaluated)
    ):
        raise HistoricalTrafficSerializationError("AP snapshot timestamps are invalid")
    return {
        "source_kind": "observation_ap_dynamic",
        "cycle_id": cycle_id,
        "evaluated_at": evaluated,
        "observed_at": observed,
        "newest_observed_at": newest,
        "freshness_status": freshness,
        "freshness_reason": reason,
        "selected_source": selected,
    }


def _peak_load(
    value: Any,
    *,
    history_status: str,
    range_start: datetime,
    range_end: datetime,
    buckets: list[dict[str, Any]],
    statistics: dict[str, Any],
) -> dict[str, Any]:
    constants = {
        "metric_version": "network_traffic_peak_load.v1",
        "unit": "Mbps",
        "peak_value_method": "max_accepted_complete_site_sample.v1",
        "peak_tie_break_method": "earliest_peak_sample_at.v1",
        "sample_timestamp_semantics": "cycle_finished_at",
    }
    status = getattr(value, "status", None)
    if status not in _STATISTICS_STATUSES or any(
        getattr(value, key, None) != expected
        for key, expected in constants.items()
    ):
        raise HistoricalTrafficSerializationError("Peak Load contract is invalid")
    raw_events = getattr(value, "events", None)
    if not isinstance(raw_events, Mapping) or set(raw_events) != {"download", "upload", "total"}:
        raise HistoricalTrafficSerializationError("Peak events are invalid")
    events = {
        name: _peak_event(raw_events[name], range_start, range_end)
        for name in ("download", "upload", "total")
    }
    for name, statistic_name in (
        ("download", "download_mbps"),
        ("upload", "upload_mbps"),
        ("total", "total_mbps"),
    ):
        event_value = events[name]["value_mbps"]
        statistics_value = statistics["peak"][statistic_name]
        if event_value is None or statistics_value is None:
            if event_value is not statistics_value:
                raise HistoricalTrafficSerializationError("Peak value identity is invalid")
        elif not math.isclose(event_value, statistics_value, rel_tol=1e-9, abs_tol=1e-9):
            raise HistoricalTrafficSerializationError("Peak value identity is invalid")
    busiest_bucket = _peak_bucket(
        getattr(value, "busiest_bucket", None),
        buckets,
    )
    busiest_hour = _peak_hour(
        getattr(value, "busiest_hour", None),
        range_start,
        range_end,
    )
    numeric_events = all(event["value_mbps"] is not None for event in events.values())
    complete = (
        history_status == "ok"
        and statistics["status"] == "ok"
        and numeric_events
        and busiest_bucket["status"] == "ok"
        and busiest_hour["status"] == "ok"
    )
    if status == "ok" and not complete:
        raise HistoricalTrafficSerializationError("Peak Load ok state is invalid")
    if status == "partial" and (complete or not numeric_events):
        raise HistoricalTrafficSerializationError("Peak Load partial state is invalid")
    if status == "insufficient_data" and (
        numeric_events
        or any(event["value_mbps"] is not None for event in events.values())
        or busiest_bucket["status"] != "insufficient_data"
        or busiest_hour["status"] != "insufficient_data"
    ):
        raise HistoricalTrafficSerializationError("Peak Load insufficient state is invalid")
    return {
        "status": status,
        **constants,
        "events": events,
        "busiest_bucket": busiest_bucket,
        "busiest_hour": busiest_hour,
    }


def _peak_event(value: Any, start: datetime, end: datetime) -> dict[str, Any]:
    if value is None:
        raise HistoricalTrafficSerializationError("Peak event is missing")
    raw_value = getattr(value, "value_mbps", None)
    sample_text = getattr(value, "sample_at_utc", None)
    source = getattr(value, "selected_source", None)
    occurrences = _count(getattr(value, "occurrence_count", None))
    if raw_value is None:
        if sample_text is not None or source is not None or occurrences != 0:
            raise HistoricalTrafficSerializationError("Peak null event is invalid")
        return {"value_mbps": None, "sample_at_utc": None, "selected_source": None, "occurrence_count": 0}
    number = _number(raw_value)
    sample = _utc(sample_text)
    if not start <= sample < end or source not in _SOURCES or occurrences < 1:
        raise HistoricalTrafficSerializationError("Peak event is invalid")
    return {"value_mbps": number, "sample_at_utc": sample_text, "selected_source": source, "occurrence_count": occurrences}


def _peak_bucket(value: Any, buckets: list[dict[str, Any]]) -> dict[str, Any]:
    constants = {
        "method": "max_complete_history_bucket_total_mean.v1",
        "tie_break_method": "earliest_bucket_start.v1",
    }
    if value is None or any(getattr(value, key, None) != expected for key, expected in constants.items()):
        raise HistoricalTrafficSerializationError("Peak bucket method is invalid")
    status = getattr(value, "status", None)
    occurrences = _count(getattr(value, "occurrence_count", None))
    if status == "insufficient_data":
        if any(getattr(value, key, None) is not None for key in (
            "bucket_start_utc", "bucket_end_utc", "average_total_mbps", "selected_source"
        )) or occurrences != 0:
            raise HistoricalTrafficSerializationError("Peak bucket null shape is invalid")
        return {"status": status, "bucket_start_utc": None, "bucket_end_utc": None, "average_total_mbps": None, "selected_source": None, "occurrence_count": 0, **constants}
    if status != "ok":
        raise HistoricalTrafficSerializationError("Peak bucket status is invalid")
    start = getattr(value, "bucket_start_utc", None)
    end = getattr(value, "bucket_end_utc", None)
    total = _number(getattr(value, "average_total_mbps", None))
    source = getattr(value, "selected_source", None)
    complete = [item for item in buckets if item["status"] == "complete"]
    maximum = max((item["total_mbps"] for item in complete), default=None)
    winners = [item for item in complete if item["total_mbps"] == maximum]
    canonical = winners[0] if winners else None
    if (
        canonical is None
        or start != canonical["bucket_start_utc"]
        or end != canonical["bucket_end_utc"]
        or source != canonical["selected_source"]
        or total != maximum
        or source not in _SOURCES
        or occurrences != len(winners)
    ):
        raise HistoricalTrafficSerializationError("Peak bucket is invalid")
    return {"status": status, "bucket_start_utc": start, "bucket_end_utc": end, "average_total_mbps": total, "selected_source": source, "occurrence_count": occurrences, **constants}


def _peak_hour(value: Any, start: datetime, end: datetime) -> dict[str, Any]:
    constants = {
        "duration_seconds": 3600,
        "method": "max_complete_rolling_3600s_average_total_sample_hold.v1",
        "average_method": "right_endpoint_sample_hold_time_weighted.v1",
        "tie_break_method": "earliest_window_start.v1",
    }
    if value is None or any(getattr(value, key, None) != expected for key, expected in constants.items()):
        raise HistoricalTrafficSerializationError("Peak hour method is invalid")
    if hasattr(value, "occurrence_count"):
        raise HistoricalTrafficSerializationError("Peak hour occurrence count is forbidden")
    status = getattr(value, "status", None)
    if status == "insufficient_data":
        if any(getattr(value, key, None) is not None for key in (
            "window_start_utc", "window_end_utc", "average_total_mbps", "accepted_interval_seconds", "selected_source"
        )):
            raise HistoricalTrafficSerializationError("Peak hour null shape is invalid")
        return {"status": status, "window_start_utc": None, "window_end_utc": None, "average_total_mbps": None, "accepted_interval_seconds": None, "selected_source": None, **constants}
    if status != "ok":
        raise HistoricalTrafficSerializationError("Peak hour status is invalid")
    window_start = _utc(getattr(value, "window_start_utc", None))
    window_end = _utc(getattr(value, "window_end_utc", None))
    average = _number(getattr(value, "average_total_mbps", None))
    accepted = _number(getattr(value, "accepted_interval_seconds", None))
    source = getattr(value, "selected_source", None)
    if not start <= window_start < window_end <= end or (window_end-window_start).total_seconds() != 3600 or accepted != 3600 or source not in _SOURCES:
        raise HistoricalTrafficSerializationError("Peak hour is invalid")
    return {"status": status, "window_start_utc": getattr(value, "window_start_utc"), "window_end_utc": getattr(value, "window_end_utc"), "average_total_mbps": average, "accepted_interval_seconds": accepted, "selected_source": source, **constants}


def _statistics(
    value: Any,
    *,
    history_status: str,
    range_seconds: float,
    complete_site_sample_count: int,
) -> dict[str, Any]:
    if value is None or getattr(value, "status", None) not in _STATISTICS_STATUSES:
        raise HistoricalTrafficSerializationError("Statistics status is invalid")
    if any(
        getattr(value, key, None) != expected
        for key, expected in _STATISTICS_CONSTANTS.items()
    ):
        raise HistoricalTrafficSerializationError("Statistics method is invalid")
    average = _statistics_values(getattr(value, "average", None))
    peak = _statistics_values(getattr(value, "peak", None))
    evidence = getattr(value, "interval_evidence", None)
    if evidence is None:
        raise HistoricalTrafficSerializationError(
            "Statistics interval evidence is missing"
        )
    counts = {
        name: _count(getattr(evidence, name, None))
        for name in _STATISTICS_COUNT_FIELDS
    }
    durations = {
        name: _number(getattr(evidence, name, None))
        for name in (
            "range_seconds", "accepted_interval_seconds",
            "leading_unweighted_seconds", "trailing_unweighted_seconds",
        )
    }
    ratio = _number(getattr(evidence, "interval_coverage_ratio", None))
    if (
        not math.isclose(
            durations["range_seconds"], range_seconds,
            rel_tol=0.0, abs_tol=1e-9,
        )
        or durations["accepted_interval_seconds"] > range_seconds
        or durations["leading_unweighted_seconds"] > range_seconds
        or durations["trailing_unweighted_seconds"] > range_seconds
        or ratio > 1
        or not math.isclose(
            ratio,
            durations["accepted_interval_seconds"] / range_seconds,
            rel_tol=1e-9,
            abs_tol=1e-9,
        )
    ):
        raise HistoricalTrafficSerializationError(
            "Statistics interval duration is invalid"
        )
    if (
        counts["candidate_interval_count"]
        != max(counts["accepted_peak_sample_count"] - 1, 0)
        or counts["candidate_interval_count"]
        != counts["accepted_interval_count"]
        + counts["invalid_period_interval_count"]
        + counts["excluded_source_transition_interval_count"]
        + counts["excluded_gap_interval_count"]
        or counts["accepted_interval_count"]
        > counts["candidate_interval_count"]
        or counts["accepted_peak_sample_count"] != complete_site_sample_count
    ):
        raise HistoricalTrafficSerializationError(
            "Statistics interval accounting is invalid"
        )
    average_numeric = average["download_mbps"] is not None
    peak_numeric = peak["download_mbps"] is not None
    if average_numeric:
        if (
            counts["accepted_interval_count"] == 0
            or durations["accepted_interval_seconds"] <= 0
            or not math.isclose(
                average["total_mbps"],
                average["download_mbps"] + average["upload_mbps"],
                rel_tol=1e-9,
                abs_tol=1e-9,
            )
        ):
            raise HistoricalTrafficSerializationError(
                "Statistics Average is invalid"
            )
    elif (
        counts["accepted_interval_count"] != 0
        or durations["accepted_interval_seconds"] != 0
    ):
        raise HistoricalTrafficSerializationError(
            "Statistics Average evidence is invalid"
        )
    if peak_numeric:
        if (
            counts["accepted_peak_sample_count"] == 0
            or peak["total_mbps"] + 1e-9 < peak["download_mbps"]
            or peak["total_mbps"] + 1e-9 < peak["upload_mbps"]
            or peak["total_mbps"]
            > peak["download_mbps"] + peak["upload_mbps"] + 1e-9
        ):
            raise HistoricalTrafficSerializationError("Statistics Peak is invalid")
    elif counts["accepted_peak_sample_count"] != 0:
        raise HistoricalTrafficSerializationError(
            "Statistics Peak evidence is invalid"
        )
    complete = (
        history_status == "ok"
        and average_numeric
        and peak_numeric
        and counts["excluded_gap_interval_count"] == 0
        and counts["excluded_source_transition_interval_count"] == 0
        and counts["invalid_period_interval_count"] == 0
    )
    status = value.status
    if status == "ok" and not complete:
        raise HistoricalTrafficSerializationError("Statistics ok state is invalid")
    if status == "partial" and (complete or not (average_numeric or peak_numeric)):
        raise HistoricalTrafficSerializationError(
            "Statistics partial state is invalid"
        )
    if status == "insufficient_data" and (
        average_numeric or peak_numeric
        or counts["accepted_interval_count"] != 0
        or counts["accepted_peak_sample_count"] != 0
    ):
        raise HistoricalTrafficSerializationError(
            "Statistics insufficient state is invalid"
        )
    return {
        "status": status,
        **_STATISTICS_CONSTANTS,
        "average": average,
        "peak": peak,
        "interval_evidence": {
            **counts,
            **durations,
            "interval_coverage_ratio": ratio,
        },
    }


def _statistics_values(value: Any) -> dict[str, float | None]:
    if value is None:
        raise HistoricalTrafficSerializationError("Statistics values are missing")
    raw = tuple(getattr(value, name, None) for name in _STATISTICS_VALUE_FIELDS)
    if all(item is None for item in raw):
        return {name: None for name in _STATISTICS_VALUE_FIELDS}
    if any(item is None for item in raw):
        raise HistoricalTrafficSerializationError(
            "Statistics metric family is incomplete"
        )
    return {
        name: _number(item)
        for name, item in zip(_STATISTICS_VALUE_FIELDS, raw)
    }


def _project(value: Any, names: tuple[str, ...]) -> dict[str, Any]:
    if value is None:
        raise HistoricalTrafficSerializationError("object is missing")
    return {name: getattr(value, name, None) for name in names}


def _utc(value: Any) -> datetime:
    if not isinstance(value, str):
        raise HistoricalTrafficSerializationError("timestamp is invalid")
    try:
        return parse_utc(value, "timestamp")
    except Exception as exc:
        raise HistoricalTrafficSerializationError("timestamp is invalid") from exc


def _optional_utc(value: Any) -> str | None:
    if value is None:
        return None
    _utc(value)
    return value


def _count(value: Any) -> int:
    if type(value) is not int or value < 0:
        raise HistoricalTrafficSerializationError("count is invalid")
    return value


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HistoricalTrafficSerializationError("number is invalid")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise HistoricalTrafficSerializationError("number is invalid")
    return result


def _optional_number(value: Any) -> float | None:
    return None if value is None else _number(value)


def _text(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 64:
        raise HistoricalTrafficSerializationError("text is invalid")
    return value


def _boolean(value: Any) -> bool:
    if type(value) is not bool:
        raise HistoricalTrafficSerializationError("boolean is invalid")
    return value
