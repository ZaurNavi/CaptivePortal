from __future__ import annotations

import math
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.analytics.current_traffic import CurrentTrafficReadService
from app.analytics.historical_traffic import (
    HistoricalTrafficReadService,
    HistoricalTrafficSourceUnavailable,
)

from .test_historical_traffic_ap import END, OTHER_SITE, SITE, START, _cycle, _row


UTC = timezone.utc
A = "02:AA:BB:CC:DD:10"
B = "02:AA:BB:CC:DD:20"


def _share(stack, *, current=True, site=SITE):
    service = HistoricalTrafficReadService(
        stack.gateway,
        quality_gap_threshold_seconds=180,
        clock=lambda: datetime(2026, 1, 1, 12, tzinfo=UTC),
    )
    cycle_id = None
    status = "unavailable"
    if current:
        summary = CurrentTrafficReadService(stack.gateway).get_current_site_traffic(
            site,
            evaluated_at_utc=END,
            fresh_max_age_seconds=90,
            stale_max_age_seconds=180,
            max_ap_skew_seconds=60,
        )
        cycle_id = summary.snapshot.cycle_id
        status = "available"
    return service.get_site_history(
        site,
        from_utc=START,
        to_utc=END,
        evaluated_at_utc=END,
        bucket_seconds=300,
        include_ap_share=True,
        current_population_status=status,
        current_cycle_id=cycle_id,
    )


def _weighted_fixture(stack):
    for cycle_id, observed, rows in (
        ("share-a", "2026-01-01T11:55:00.000Z", [(A, 1, 4), (B, 0, 0)]),
        ("share-b", "2026-01-01T11:56:00.000Z", [(A, 1, 4)]),
        ("share-c", "2026-01-01T11:59:00.000Z", [(A, 1, 4), (B, 3, 0)]),
    ):
        _cycle(stack, cycle_id, SITE, observed, [
            _row(cycle_id, SITE, mac, observed, download, upload)
            for mac, download, upload in rows
        ])


def test_share_reuses_weighted_ap_facts_conserves_and_is_not_sample_count(
    analytics_stack,
):
    _weighted_fixture(analytics_stack)
    product = _share(analytics_stack).ap_traffic_share

    assert product.status == "ok"
    assert product.interval_evidence.accepted_interval_count == 2
    by_mac = {item.ap_mac: item for item in product.items}
    assert by_mac[A].download_weight == pytest.approx(240.0)
    assert by_mac[B].download_weight == pytest.approx(540.0)
    assert by_mac[B].accepted_presence_interval_count == 1
    assert by_mac[B].accepted_presence_seconds == pytest.approx(180.0)
    assert by_mac[B].download_share_fraction == pytest.approx(540 / 780)
    assert by_mac[B].download_share_fraction > by_mac[A].download_share_fraction
    assert by_mac[A].download_share_fraction != pytest.approx(1 / (1 + 3))
    assert by_mac[B].download_share_fraction != pytest.approx(3 / (1 + 3))
    assert math.fsum(item.download_weight for item in product.items) == pytest.approx(
        product.site_download_weight
    )
    assert math.fsum(item.upload_weight for item in product.items) == pytest.approx(
        product.site_upload_weight
    )
    assert math.fsum(item.total_share_fraction for item in product.items) == pytest.approx(1)
    assert by_mac[A].total_share_fraction != pytest.approx(
        (by_mac[A].download_share_fraction + by_mac[A].upload_share_fraction) / 2
    )


def test_current_only_ap_has_unproven_null_share_not_numeric_zero(analytics_stack):
    for cycle_id, observed in (
        ("historical-a", "2026-01-01T11:55:00.000Z"),
        ("historical-b", "2026-01-01T11:59:00.000Z"),
    ):
        _cycle(analytics_stack, cycle_id, SITE, observed, [
            _row(cycle_id, SITE, A, observed, 2, 1),
        ])
    _cycle(analytics_stack, "current-only", SITE, END, [
        _row("current-only", SITE, B, END, 0, 0),
    ])

    product = _share(analytics_stack).ap_traffic_share
    current_only = next(item for item in product.items if item.ap_mac == B)
    assert current_only.range_presence_proven is False
    assert current_only.evidence_status == "insufficient_data"
    assert current_only.accepted_presence_interval_count == 0
    assert current_only.accepted_presence_seconds == 0
    assert current_only.download_weight is None
    assert current_only.upload_weight is None
    assert current_only.download_share_fraction is None
    assert current_only.upload_share_fraction is None
    assert current_only.total_share_fraction is None


def test_true_zero_is_numeric_when_contribution_presence_is_proven(analytics_stack):
    for cycle_id, observed in (
        ("zero-a", "2026-01-01T11:56:00.000Z"),
        ("zero-b", "2026-01-01T11:59:00.000Z"),
    ):
        _cycle(analytics_stack, cycle_id, SITE, observed, [
            _row(cycle_id, SITE, A, observed, 2, 1),
            _row(cycle_id, SITE, B, observed, 0, 0),
        ])
    zero = next(
        item for item in _share(analytics_stack).ap_traffic_share.items
        if item.ap_mac == B
    )
    assert zero.range_presence_proven is True
    assert zero.download_weight == 0
    assert zero.upload_weight == 0
    assert zero.download_share_fraction == 0
    assert zero.upload_share_fraction == 0
    assert zero.total_share_fraction == 0


def test_unavailable_current_context_retains_historical_share_as_partial(
    analytics_stack,
):
    for cycle_id, observed in (
        ("offline-a", "2026-01-01T11:56:00.000Z"),
        ("offline-b", "2026-01-01T11:59:00.000Z"),
    ):
        _cycle(analytics_stack, cycle_id, SITE, observed, [
            _row(cycle_id, SITE, A, observed, 2, 1),
        ])
    available = _share(analytics_stack).ap_traffic_share
    product = _share(analytics_stack, current=False).ap_traffic_share
    assert product.status == "partial"
    assert product.population.current_population_status == "unavailable"
    assert product.population.current_population_count is None
    assert product.population.population_complete is False
    assert product.items[0].total_share_fraction == 1
    assert product.site_download_weight == available.site_download_weight
    assert product.site_upload_weight == available.site_upload_weight


def test_empty_unavailable_current_context_does_not_claim_known_empty_site(
    analytics_stack,
):
    product = _share(analytics_stack, current=False).ap_traffic_share
    assert product.status == "insufficient_data"
    assert product.population.population_count == 0
    assert product.population.current_population_count is None
    assert product.population.population_complete is False
    assert product.items == ()


def test_share_population_over_twelve_is_unsupported_without_truncation(
    analytics_stack,
):
    observed = "2026-01-01T11:59:00.000Z"
    _cycle(analytics_stack, "share-many", SITE, observed, [
        _row(
            "share-many", SITE, f"02:AA:BB:CC:DD:{index:02X}",
            observed, index, index,
        )
        for index in range(13)
    ])
    product = _share(analytics_stack).ap_traffic_share
    assert product.status == "unsupported_population"
    assert product.population.population_count == 13
    assert product.population.returned_ap_count == 0
    assert product.population.population_complete is False
    assert product.items == ()


def test_unproven_numeric_weight_conflict_fails_closed(analytics_stack, monkeypatch):
    _weighted_fixture(analytics_stack)
    original = analytics_stack.gateway.historical_traffic_data

    def corrupted(**kwargs):
        data = dict(original(**kwargs))
        rows = [dict(row) for row in data["ap_rows"]]
        target = next(row for row in rows if row["ap_mac"] == B)
        target["ap_accepted_sample_count"] = 0
        target["ap_accepted_interval_count"] = 0
        target["ap_accepted_interval_seconds"] = 0.0
        target["ap_weighted_download"] = 0.0
        target["ap_weighted_upload"] = 0.0
        data["ap_rows"] = tuple(rows)
        return data

    monkeypatch.setattr(analytics_stack.gateway, "historical_traffic_data", corrupted)
    with pytest.raises(HistoricalTrafficSourceUnavailable):
        _share(analytics_stack)


@pytest.mark.parametrize(
    ("first", "second", "zero_direction"),
    [((0, 3), (0, 1), "download"), ((3, 0), (1, 0), "upload")],
)
def test_total_share_uses_exact_combined_weight_when_one_direction_is_zero(
    analytics_stack, first, second, zero_direction,
):
    for cycle_id, observed in (
        ("direction-a", "2026-01-01T11:56:00.000Z"),
        ("direction-b", "2026-01-01T11:59:00.000Z"),
    ):
        _cycle(analytics_stack, cycle_id, SITE, observed, [
            _row(cycle_id, SITE, A, observed, *first),
            _row(cycle_id, SITE, B, observed, *second),
        ])
    product = _share(analytics_stack).ap_traffic_share
    by_mac = {item.ap_mac: item for item in product.items}
    assert getattr(product.denominators, f"{zero_direction}_status") == "zero_traffic"
    assert getattr(by_mac[A], f"{zero_direction}_share_fraction") is None
    nonzero_direction = "upload" if zero_direction == "download" else "download"
    assert by_mac[A].total_share_fraction == pytest.approx(
        getattr(by_mac[A], f"{nonzero_direction}_share_fraction")
    )
    assert by_mac[B].total_share_fraction == pytest.approx(
        getattr(by_mac[B], f"{nonzero_direction}_share_fraction")
    )


def test_proven_ap_structural_absence_contributes_numeric_zero(analytics_stack):
    _cycle(analytics_stack, "present", SITE, "2026-01-01T11:56:00.000Z", [
        _row("present", SITE, A, "2026-01-01T11:56:00.000Z", 2, 1),
        _row("present", SITE, B, "2026-01-01T11:56:00.000Z", 4, 2),
    ])
    _cycle(analytics_stack, "absent", SITE, "2026-01-01T11:59:00.000Z", [
        _row("absent", SITE, A, "2026-01-01T11:59:00.000Z", 2, 1),
    ])
    product = _share(analytics_stack).ap_traffic_share
    absent = next(item for item in product.items if item.ap_mac == B)
    assert absent.range_presence_proven is True
    assert absent.accepted_presence_interval_count == 0
    assert absent.accepted_presence_seconds == 0
    assert absent.download_weight == 0
    assert absent.upload_weight == 0
    assert absent.total_share_fraction == 0


def test_share_and_ap_product_reuse_exact_population_and_weighted_facts(
    analytics_stack,
):
    _weighted_fixture(analytics_stack)
    current = CurrentTrafficReadService(
        analytics_stack.gateway
    ).get_current_site_traffic(
        SITE,
        evaluated_at_utc=END,
        fresh_max_age_seconds=90,
        stale_max_age_seconds=180,
        max_ap_skew_seconds=60,
    )
    result = HistoricalTrafficReadService(
        analytics_stack.gateway,
        quality_gap_threshold_seconds=180,
    ).get_site_history(
        SITE,
        from_utc=START,
        to_utc=END,
        evaluated_at_utc=END,
        bucket_seconds=300,
        include_period_statistics=True,
        include_ap_traffic=True,
        include_ap_share=True,
        current_population_status="available",
        current_cycle_id=current.snapshot.cycle_id,
    )
    share = result.ap_traffic_share
    by_ap = result.ap_traffic
    assert share.interval_evidence == result.period_statistics.interval_evidence
    assert share.population.population_count == by_ap.population.population_count
    assert {item.ap_mac for item in share.items} == {
        item.ap_mac for item in by_ap.items
    }
    by_mac = {item.ap_mac: item for item in by_ap.items}
    for item in share.items:
        ap_item = by_mac[item.ap_mac]
        assert item.accepted_presence_seconds == pytest.approx(
            ap_item.coverage.ap_accepted_interval_seconds
        )
        if item.range_presence_proven:
            assert item.download_weight == pytest.approx(
                (ap_item.average.download_mbps or 0)
                * ap_item.coverage.ap_accepted_interval_seconds
            )
            assert item.upload_weight == pytest.approx(
                (ap_item.average.upload_mbps or 0)
                * ap_item.coverage.ap_accepted_interval_seconds
            )


def test_share_population_and_denominator_are_site_isolated(analytics_stack):
    for cycle_id, observed in (
        ("site-a-1", "2026-01-01T11:56:00.000Z"),
        ("site-a-2", "2026-01-01T11:59:00.000Z"),
    ):
        _cycle(analytics_stack, cycle_id, SITE, observed, [
            _row(cycle_id, SITE, A, observed, 2, 1),
        ])
    for cycle_id, observed in (
        ("site-b-1", "2026-01-01T11:56:00.000Z"),
        ("site-b-2", "2026-01-01T11:59:00.000Z"),
    ):
        _cycle(analytics_stack, cycle_id, OTHER_SITE, observed, [
            _row(cycle_id, OTHER_SITE, B, observed, 1000, 1000),
        ])
    product = _share(analytics_stack, site=SITE).ap_traffic_share
    assert product.population.population_count == 1
    assert [item.ap_mac for item in product.items] == [A]
    assert product.items[0].total_share_fraction == 1


def test_proved_empty_current_population_preserves_exact_zero(analytics_stack):
    _cycle(analytics_stack, "empty-current", SITE, END, [])
    product = _share(analytics_stack).ap_traffic_share
    assert product.status == "insufficient_data"
    assert product.population.population_count == 0
    assert product.population.current_population_status == "available"
    assert product.population.current_population_count == 0
    assert product.population.population_complete is True
    assert product.items == ()


def test_conservation_mismatch_fails_closed_without_renormalizing(
    analytics_stack, monkeypatch,
):
    _weighted_fixture(analytics_stack)
    original = analytics_stack.gateway.historical_traffic_data

    def corrupted(**kwargs):
        data = dict(original(**kwargs))
        rows = [dict(row) for row in data["ap_rows"]]
        target = next(row for row in rows if row["ap_mac"] == A)
        target["ap_weighted_download"] += 1
        data["ap_rows"] = tuple(rows)
        return data

    monkeypatch.setattr(analytics_stack.gateway, "historical_traffic_data", corrupted)
    with pytest.raises(HistoricalTrafficSourceUnavailable):
        _share(analytics_stack)


def test_historical_identity_without_accepted_contribution_stays_unproven(
    analytics_stack,
):
    _cycle(analytics_stack, "identity-only", SITE, "2026-01-01T11:55:00.000Z", [
        _row(
            "identity-only", SITE, B, "2026-01-01T11:55:00.000Z",
            None, None, name="Old AP",
            wired_download_rate_reason="source_unavailable",
            wired_upload_rate_reason="source_unavailable",
        ),
    ])
    for cycle_id, observed in (
        ("accepted-a", "2026-01-01T11:56:00.000Z"),
        ("accepted-b", "2026-01-01T11:59:00.000Z"),
    ):
        _cycle(analytics_stack, cycle_id, SITE, observed, [
            _row(cycle_id, SITE, A, observed, 2, 1),
        ])
    product = _share(analytics_stack).ap_traffic_share
    identity_only = next(item for item in product.items if item.ap_mac == B)
    assert identity_only.display_name == "Old AP"
    assert identity_only.display_name_source == "historical"
    assert identity_only.range_presence_proven is False
    assert identity_only.download_weight is None
    assert identity_only.upload_weight is None
    assert identity_only.total_share_fraction is None


def test_present_invalid_weighting_fails_closed(analytics_stack, monkeypatch):
    _weighted_fixture(analytics_stack)
    original = analytics_stack.gateway.historical_traffic_data

    def corrupted(**kwargs):
        data = dict(original(**kwargs))
        rows = [dict(row) for row in data["ap_rows"]]
        target = next(row for row in rows if row["ap_mac"] == A)
        target["ap_weighted_download"] = None
        data["ap_rows"] = tuple(rows)
        return data

    monkeypatch.setattr(analytics_stack.gateway, "historical_traffic_data", corrupted)
    with pytest.raises(HistoricalTrafficSourceUnavailable):
        _share(analytics_stack)


def test_twelve_ap_population_is_complete_and_not_truncated(analytics_stack):
    for cycle_id, observed in (
        ("twelve-a", "2026-01-01T11:56:00.000Z"),
        ("twelve-b", "2026-01-01T11:59:00.000Z"),
    ):
        _cycle(analytics_stack, cycle_id, SITE, observed, [
            _row(
                cycle_id, SITE, f"02:AA:BB:CC:DD:{index:02X}",
                observed, index, index,
            )
            for index in range(12)
        ])
    product = _share(analytics_stack).ap_traffic_share
    assert product.status == "ok"
    assert product.population.population_count == 12
    assert product.population.returned_ap_count == 12
    assert product.population.population_complete is True
    assert len(product.items) == 12
    assert [item.ap_mac for item in product.items] == sorted(
        (item.ap_mac for item in product.items),
        key=lambda mac: (
            -next(
                item.total_share_fraction
                for item in product.items if item.ap_mac == mac
            ),
            mac,
        ),
    )
