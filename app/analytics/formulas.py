"""Deterministic formulas shared by Analytics quality queries."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Iterable, Mapping, Sequence

from .models import (
    ConfiguredThresholdRatio,
    CoverageMetric,
    JoinCoverage,
    NumericDistribution,
    VisitObservationCoverage,
)


def coverage(numerator: int, denominator: int) -> CoverageMetric:
    if numerator < 0 or denominator < 0 or numerator > denominator:
        raise ValueError("coverage counts are inconsistent")
    return CoverageMetric(
        numerator=numerator,
        denominator=denominator,
        ratio=None if denominator == 0 else numerator / denominator,
    )


def observation_coverage(
    *,
    started_at: datetime,
    ended_at: datetime,
    sample_count: int,
    first_observed_at: datetime | None,
    last_observed_at: datetime | None,
    max_gap_seconds: float | None,
    gap_count_over_threshold: int,
    gap_threshold_seconds: float,
    visit_duration_seconds: int | None,
    provisional: bool,
) -> VisitObservationCoverage:
    first_text = _format(first_observed_at)
    last_text = _format(last_observed_at)
    edge_start = (
        None if first_observed_at is None
        else max(0.0, (first_observed_at - started_at).total_seconds())
    )
    edge_end = (
        None if last_observed_at is None
        else max(0.0, (ended_at - last_observed_at).total_seconds())
    )
    span = None
    ratio = None
    if (
        sample_count >= 2
        and first_observed_at is not None
        and last_observed_at is not None
    ):
        span = max(
            0.0, (last_observed_at - first_observed_at).total_seconds()
        )
        if visit_duration_seconds is not None and visit_duration_seconds > 0:
            ratio = min(1.0, span / visit_duration_seconds)
    return VisitObservationCoverage(
        sample_count=sample_count,
        interval_count=max(sample_count - 1, 0),
        first_observed_at=first_text,
        last_observed_at=last_text,
        edge_gap_start_seconds=edge_start,
        edge_gap_end_seconds=edge_end,
        max_inter_sample_gap_seconds=max_gap_seconds,
        gap_count_over_threshold=gap_count_over_threshold,
        gap_threshold_seconds=gap_threshold_seconds,
        observed_span_seconds=span,
        observed_span_ratio=ratio,
        provisional=provisional,
    )


def gap_summary(
    timestamps: Iterable[datetime],
    threshold_seconds: float,
) -> tuple[int, int, float | None, int]:
    ordered = tuple(timestamps)
    gaps = tuple(
        (current - previous).total_seconds()
        for previous, current in zip(ordered, ordered[1:])
    )
    return (
        len(ordered),
        len(gaps),
        max(gaps) if gaps else None,
        sum(1 for value in gaps if value > threshold_seconds),
    )


def percentile_r7(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    if not 0 <= probability <= 1:
        raise ValueError("probability must be between zero and one")
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * probability
    lower_index = math.floor(position)
    fraction = position - lower_index
    if lower_index == len(ordered) - 1:
        return ordered[lower_index]
    return ordered[lower_index] + fraction * (
        ordered[lower_index + 1] - ordered[lower_index]
    )


def interpolate_r7(
    sample_count: int,
    probability: float,
    lower: float | None,
    upper: float | None,
) -> float | None:
    if sample_count <= 0 or lower is None:
        return None
    position = (sample_count - 1) * probability
    fraction = position - math.floor(position)
    high = lower if upper is None else upper
    return float(lower) + fraction * (float(high) - float(lower))


def numeric_distribution(
    raw: Mapping[str, object],
    *,
    min_samples: int,
) -> NumericDistribution:
    count = int(raw.get("sample_count") or 0)
    missing = int(raw.get("missing_count") or 0)
    sufficient = count >= min_samples
    return NumericDistribution(
        sample_count=count,
        missing_count=missing,
        minimum=_number(raw.get("minimum")) if sufficient else None,
        maximum=_number(raw.get("maximum")) if sufficient else None,
        mean=_number(raw.get("mean")) if sufficient else None,
        p10=_raw_percentile(raw, count, "p10", 0.10)
        if sufficient else None,
        p50=_raw_percentile(raw, count, "p50", 0.50)
        if sufficient else None,
        p90=_raw_percentile(raw, count, "p90", 0.90)
        if sufficient else None,
        p95=_raw_percentile(raw, count, "p95", 0.95)
        if sufficient else None,
    )


def configured_threshold_ratio(
    *,
    threshold: float | None,
    sample_count: int,
    below_count: int | None,
) -> ConfiguredThresholdRatio:
    if threshold is None:
        return ConfiguredThresholdRatio(None, None, None)
    below = int(below_count or 0)
    return ConfiguredThresholdRatio(
        threshold=float(threshold),
        below_threshold_count=below,
        below_configured_threshold_ratio=(
            None if sample_count <= 0 else below / sample_count
        ),
    )


def pearson_from_sums(
    *,
    sample_count: int,
    sum_x: float,
    sum_y: float,
    sum_xx: float,
    sum_yy: float,
    sum_xy: float,
    min_samples: int,
) -> float | None:
    if sample_count < min_samples:
        return None
    numerator = sample_count * sum_xy - sum_x * sum_y
    variance_x = sample_count * sum_xx - sum_x * sum_x
    variance_y = sample_count * sum_yy - sum_y * sum_y
    if variance_x <= 0 or variance_y <= 0:
        return None
    return numerator / math.sqrt(variance_x * variance_y)


def join_coverage(raw: Mapping[str, object]) -> JoinCoverage:
    clients = int(raw.get("client_sample_count") or 0)
    matched = int(raw.get("matched_count") or 0)
    return JoinCoverage(
        client_sample_count=clients,
        matched_count=matched,
        unmatched_count=max(clients - matched, 0),
        match_ratio=None if clients == 0 else matched / clients,
        lag_p50=interpolate_r7(
            matched, 0.50,
            _number(raw.get("lag_p50_lower")),
            _number(raw.get("lag_p50_upper")),
        ),
        lag_p95=interpolate_r7(
            matched, 0.95,
            _number(raw.get("lag_p95_lower")),
            _number(raw.get("lag_p95_upper")),
        ),
        lag_max=_number(raw.get("lag_max")),
    )


def _raw_percentile(
    raw: Mapping[str, object],
    count: int,
    prefix: str,
    probability: float,
) -> float | None:
    return interpolate_r7(
        count,
        probability,
        _number(raw.get(f"{prefix}_lower")),
        _number(raw.get(f"{prefix}_upper")),
    )


def _number(value: object) -> float | None:
    return None if value is None else float(value)


def _format(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")
