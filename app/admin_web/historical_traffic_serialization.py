"""Fail-closed projection for canonical Historical Traffic results."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

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


def serialize_historical_traffic(
    value: Any,
    site_id: str,
    *,
    resolved_range: TrafficNetworkRange,
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
    return {
        "status": value.status,
        "range": range_result,
        "buckets": projected_buckets,
        "coverage": coverage_result,
        "quality": quality,
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
