"""Deterministic formulas shared by Analytics quality queries."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from .models import CoverageMetric, VisitObservationCoverage


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


def _format(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")
