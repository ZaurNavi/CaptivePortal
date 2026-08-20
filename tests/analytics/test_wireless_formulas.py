from __future__ import annotations

import math

import pytest

from app.analytics.config import (
    AnalyticsConfigError,
    analytics_config_from_settings,
)
from app.analytics.formulas import (
    configured_threshold_ratio,
    numeric_distribution,
    pearson_from_sums,
    percentile_r7,
)


def test_r7_percentiles_are_exact_and_deterministic():
    values = [15, 0, 20, 5, 10]
    assert percentile_r7(values, 0.10) == 2
    assert percentile_r7(values, 0.50) == 10
    assert percentile_r7(values, 0.90) == 18
    assert percentile_r7(values, 0.95) == 19
    assert percentile_r7([7], 0.95) == 7


def test_distribution_enforces_minimum_and_preserves_counts():
    raw = {
        "sample_count": 1,
        "missing_count": 2,
        "minimum": 5,
        "maximum": 5,
        "mean": 5,
        "p10_lower": 5,
        "p10_upper": 5,
        "p50_lower": 5,
        "p50_upper": 5,
        "p90_lower": 5,
        "p90_upper": 5,
        "p95_lower": 5,
        "p95_upper": 5,
    }
    result = numeric_distribution(raw, min_samples=2)
    assert result.sample_count == 1
    assert result.missing_count == 2
    assert result.mean is None
    assert result.p95 is None


def test_threshold_ratio_is_optional_strict_and_has_no_denominator_value():
    unset = configured_threshold_ratio(
        threshold=None, sample_count=3, below_count=2
    )
    assert unset.below_threshold_count is None
    assert unset.below_configured_threshold_ratio is None
    empty = configured_threshold_ratio(
        threshold=-70, sample_count=0, below_count=0
    )
    assert empty.threshold == -70
    assert empty.below_configured_threshold_ratio is None


def test_pearson_known_vector_and_zero_variance():
    values = [(1.0, 2.0), (2.0, 4.0), (3.0, 6.0)]
    kwargs = {
        "sample_count": 3,
        "sum_x": sum(x for x, _ in values),
        "sum_y": sum(y for _, y in values),
        "sum_xx": sum(x * x for x, _ in values),
        "sum_yy": sum(y * y for _, y in values),
        "sum_xy": sum(x * y for x, y in values),
        "min_samples": 3,
    }
    assert pearson_from_sums(**kwargs) == pytest.approx(1.0)
    assert pearson_from_sums(
        sample_count=3, sum_x=3, sum_y=6, sum_xx=3,
        sum_yy=14, sum_xy=6, min_samples=3,
    ) is None


def test_wireless_config_defaults_and_validation():
    config = analytics_config_from_settings({})
    assert config.wireless_enabled is True
    assert config.wireless_min_samples == 20
    assert config.wireless_max_window_days == 7
    assert config.counter_max_gap_seconds == 180
    assert config.ap_join_max_lag_seconds == 120
    assert config.rssi_threshold_dbm is None
    assert config.snr_threshold_db is None

    configured = analytics_config_from_settings({
        "analytics_rssi_threshold_dbm": "-70.5",
        "analytics_snr_threshold_db": "10",
    })
    assert configured.rssi_threshold_dbm == -70.5
    assert configured.snr_threshold_db == 10


@pytest.mark.parametrize(
    "settings",
    [
        {"analytics_wireless_min_samples": 1},
        {"analytics_wireless_max_window_days": 32},
        {"analytics_wireless_max_window_days": 8,
         "analytics_max_query_window_days": 7},
        {"analytics_counter_max_gap_seconds": 0},
        {"analytics_ap_join_max_lag_seconds": -1},
        {"analytics_rssi_threshold_dbm": "NaN"},
        {"analytics_snr_threshold_db": math.inf},
    ],
)
def test_wireless_config_rejects_unsafe_values(settings):
    with pytest.raises(AnalyticsConfigError):
        analytics_config_from_settings(settings)
