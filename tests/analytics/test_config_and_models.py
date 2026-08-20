from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from app.analytics.config import (
    AnalyticsConfigError,
    analytics_config_from_settings,
)
from app.analytics.formulas import coverage, gap_summary
from app.analytics.models import (
    AnalyticsProvenance,
    AnalyticsQuality,
    AnalyticsResult,
)


def test_config_defaults_are_disabled_and_bounded():
    config = analytics_config_from_settings({})
    assert config.enabled is False
    assert config.default_limit == 500
    assert config.max_limit == 2_000
    assert config.max_query_window_days == 31
    assert config.max_query_duration_seconds == 10
    assert config.quality_gap_threshold_seconds == 180


@pytest.mark.parametrize("value", ["TRUE", "1", 1, None])
def test_config_boolean_is_exact(value):
    with pytest.raises(AnalyticsConfigError):
        analytics_config_from_settings({
            "analytics_foundation_enabled": value,
        })


@pytest.mark.parametrize(
    "settings",
    [
        {"analytics_default_limit": "0"},
        {"analytics_default_limit": "501", "analytics_max_limit": "500"},
        {"analytics_max_limit": "2001"},
        {"analytics_max_query_window_days": "32"},
        {"analytics_max_query_duration_seconds": "0"},
        {"analytics_quality_gap_threshold_seconds": "-1"},
    ],
)
def test_config_rejects_unbounded_values(settings):
    with pytest.raises(AnalyticsConfigError):
        analytics_config_from_settings(settings)


def test_coverage_zero_denominator_is_null_not_zero():
    result = coverage(0, 0)
    assert result.ratio is None


def test_coverage_rejects_inconsistent_counts():
    with pytest.raises(ValueError):
        coverage(2, 1)


def test_gap_formula_is_deterministic():
    from app.analytics.validation import parse_utc

    values = [
        parse_utc("2026-01-01T00:00:00.000Z", "value"),
        parse_utc("2026-01-01T00:01:00.000Z", "value"),
        parse_utc("2026-01-01T00:05:00.000Z", "value"),
    ]
    assert gap_summary(values, 180) == (3, 2, 240.0, 1)


def test_result_and_nested_mappings_are_immutable():
    provenance = AnalyticsProvenance(
        site_id="site-a",
        from_utc="2026-01-01T00:00:00.000Z",
        to_utc="2026-01-02T00:00:00.000Z",
        evaluation_at_utc="2026-01-02T00:00:00.000Z",
        computed_at_utc="2026-01-02T00:00:00.000Z",
        quality_mode="strict_complete",
        source_names=("observations",),
        source_schema_versions={"observations": 1},
        source_watermarks={"observations": None},
        source_rows_examined=0,
        source_rows_accepted=0,
        source_rows_rejected=0,
        sample_size=0,
        missing_count=0,
        partial_cycle_count=0,
        failed_cycle_count=0,
        abandoned_cycle_count=0,
        filters={"nested": {"value": 1}},
        metric_version="v1",
        query_duration_ms=0,
    )
    result = AnalyticsResult(
        status="ok",
        value={"items": [{"value": 1}]},
        quality=AnalyticsQuality("strict_complete"),
        provenance=provenance,
    )
    with pytest.raises(TypeError):
        result.value["items"][0]["value"] = 2
    with pytest.raises(TypeError):
        result.provenance.filters["nested"]["value"] = 2
    with pytest.raises(FrozenInstanceError):
        result.status = "partial"
