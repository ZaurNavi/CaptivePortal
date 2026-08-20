from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.analytics.wireless import WirelessAnalyticsService
from app.analytics.validation import AnalyticsQueryValidationError

from .conftest import AP_A, CLIENT_A, CLIENT_B, SITE_A, SITE_B


UTC = timezone.utc
FROM = "2026-01-01T09:00:00.000Z"
TO = "2026-01-01T11:00:00.000Z"


@pytest.fixture
def wireless_stack(analytics_stack):
    _seed_wireless(analytics_stack.observations)
    config = replace(
        analytics_stack.service.config,
        wireless_min_samples=2,
        rssi_threshold_dbm=-70,
        snr_threshold_db=10,
    )
    service = WirelessAnalyticsService(
        config,
        analytics_stack.gateway,
        clock=lambda: datetime(2026, 1, 1, 11, 0, tzinfo=UTC),
    )
    return analytics_stack, service


def _seed_wireless(repository) -> None:
    client_cycles = (
        ("wireless-client-1", "2026-01-01T10:00:30.000Z", (
            (CLIENT_A, -60, 20, 160, 70, "5GHz", 36),
        )),
        ("wireless-client-2", "2026-01-01T10:01:00.000Z", (
            (CLIENT_A, -70, 10, 220, 90, "5GHz", 36),
            (CLIENT_B, -80, None, 10, 5, "2.4GHz", 11),
        )),
        ("wireless-client-reset", "2026-01-01T10:01:30.000Z", (
            (CLIENT_A, -65, 15, 20, 100, "5GHz", 36),
        )),
        ("wireless-client-b-gap", "2026-01-01T10:04:00.000Z", (
            (CLIENT_B, -75, 8, 70, 15, "2.4GHz", 11),
        )),
        ("wireless-client-a-gap", "2026-01-01T10:04:31.000Z", (
            (CLIENT_A, None, 12, 30, 110, "5GHz", 36),
        )),
    )
    for cycle_id, observed_at, clients in client_cycles:
        repository.create_cycle(
            kind="client", site_id=SITE_A, started_at=observed_at,
            cycle_id=cycle_id,
        )
        repository.insert_client_batch([{
            "cycle_id": cycle_id,
            "observed_at": observed_at,
            "site_id": SITE_A,
            "client_mac": mac,
            "source_inventory_complete": True,
            "ssid": "ssid-a" if mac == CLIENT_A else None,
            "ap_mac": AP_A,
            "radio_id": 1,
            "band": band,
            "channel": channel,
            "rssi": rssi,
            "snr": snr,
            "traffic_down": down,
            "traffic_up": up,
        } for mac, rssi, snr, down, up, band, channel in clients])
        repository.finalize_cycle(
            cycle_id, finished_at=observed_at, complete=True,
            result="success", source_rows_reported=len(clients),
            items_seen=len(clients), items_stored=len(clients),
        )

    ap_cycles = (
        ("wireless-ap-before", "2026-01-01T09:59:50.000Z", 10, 30,
         5, 100, 200, 1, 2, 0, 0, 0, 0, "ok"),
        ("wireless-ap-mid", "2026-01-01T10:01:00.000Z", 30, 50,
         25, 160, 280, 4, 8, 2, 3, 1, 2, "counter_reset"),
        ("wireless-ap-later", "2026-01-01T10:01:30.000Z", 40, 60,
         35, 220, 360, 8, 1, 3, 5, 2, 3, "ok"),
        ("wireless-ap-future", "2026-01-01T10:10:00.000Z", 90, 90,
         80, 300, 500, 10, 4, 4, 6, 3, 4, "ok"),
    )
    for (
        cycle_id, observed_at, cpu, mem, busy, rx_packets, tx_packets,
        rx_retry, tx_retry, rx_error, tx_error, rx_drop, tx_drop,
        wired_reason,
    ) in ap_cycles:
        repository.create_cycle(
            kind="ap_dynamic", site_id=SITE_A, started_at=observed_at,
            cycle_id=cycle_id,
        )
        repository.insert_ap_batch([({
            "cycle_id": cycle_id,
            "observed_at": observed_at,
            "site_id": SITE_A,
            "ap_mac": AP_A,
            "partial": False,
            "overview_ok": True,
            "wired_uplink_ok": True,
            "lan_traffic_ok": True,
            "radios_ok": True,
            "cpu_util": cpu,
            "mem_util": mem,
            "wired_download_mbps": 10.0 if wired_reason == "ok" else None,
            "wired_download_rate_reason": wired_reason,
            "wired_upload_mbps": 5.0,
            "wired_upload_rate_reason": "ok",
            "lan_rx_mbps": 8.0,
            "lan_rx_rate_reason": "ok",
            "lan_tx_mbps": 4.0,
            "lan_tx_rate_reason": "ok",
        }, [{
            "radio_observed_at": observed_at,
            "band": "5GHz",
            "radio_id": 1,
            "tx_util": busy / 2,
            "rx_util": busy / 3,
            "interference_util": busy / 5,
            "busy_util": busy,
            "rx_packets": rx_packets,
            "tx_packets": tx_packets,
            "rx_retry_packets": rx_retry,
            "tx_retry_packets": tx_retry,
            "rx_error_packets": rx_error,
            "tx_error_packets": tx_error,
            "rx_drop_packets": rx_drop,
            "tx_drop_packets": tx_drop,
            "radio_rx_mbps": 3.0,
            "radio_tx_mbps": 2.0,
            "radio_rx_rate_reason": "ok",
            "radio_tx_rate_reason": "ok",
        }])])
        repository.finalize_cycle(
            cycle_id, finished_at=observed_at, complete=True,
            result="success", source_rows_reported=1,
            items_seen=1, items_stored=1,
        )


def test_signal_distribution_r7_threshold_null_and_half_open(wireless_stack):
    _, service = wireless_stack
    result = service.get_signal_distribution(SITE_A, FROM, TO, "rssi")
    assert result.status == "ok"
    assert result.value.distribution.sample_count == 7
    assert result.value.distribution.missing_count == 1
    assert result.value.distribution.minimum == -80
    assert result.value.distribution.maximum == -55
    assert result.value.threshold.threshold == -70
    assert result.value.threshold.below_threshold_count == 2
    assert result.value.threshold.below_configured_threshold_ratio == 2 / 7
    assert result.provenance.to_utc == TO
    assert result.provenance.source_watermarks["observations"] != TO


def test_threshold_is_strict_and_unset_is_explicit(wireless_stack):
    _, service = wireless_stack
    strict = service.get_signal_distribution(
        SITE_A, FROM, TO, "rssi", threshold=-70
    )
    assert strict.value.threshold.below_threshold_count == 2
    unset_service = WirelessAnalyticsService(
        replace(service.config, rssi_threshold_dbm=None),
        service.gateway,
    )
    unset = unset_service.get_signal_distribution(
        SITE_A, FROM, TO, "rssi"
    )
    assert unset.value.threshold.threshold is None
    assert unset.value.threshold.below_threshold_count is None


@pytest.mark.parametrize("dimension", ["ap_mac", "ssid", "band", "channel"])
def test_client_context_distribution_is_site_scoped_and_counts_facts(
    wireless_stack, dimension
):
    _, service = wireless_stack
    result = service.get_client_distribution(SITE_A, FROM, TO, dimension)
    assert result.status == "ok"
    assert sum(item.observation_count for item in result.value.items) == 8
    assert any(
        item.observation_count > item.distinct_client_count
        for item in result.value.items
    )
    other = service.get_client_distribution(SITE_B, FROM, TO, dimension)
    assert sum(item.observation_count for item in other.value.items) == 1


def test_null_context_is_an_explicit_bucket(wireless_stack):
    _, service = wireless_stack
    result = service.get_client_distribution(SITE_A, FROM, TO, "ssid")
    null_bucket = next(
        item for item in result.value.items if item.context is None
    )
    assert null_bucket.observation_count == 2
    assert result.value.missing_context_count == 2


def test_concurrent_clients_are_per_complete_cycle(wireless_stack):
    stack, service = wireless_stack
    empty_at = "2026-01-01T10:05:00.000Z"
    stack.observations.create_cycle(
        kind="client", site_id=SITE_A, started_at=empty_at,
        cycle_id="wireless-empty-cycle",
    )
    stack.observations.finalize_cycle(
        "wireless-empty-cycle", finished_at=empty_at, complete=True,
        result="success", source_rows_reported=0,
    )
    result = service.get_concurrent_client_distribution(
        SITE_A, FROM, TO
    )
    assert result.status == "ok"
    assert result.value[0].minimum == 0
    assert result.value[0].maximum == 2
    assert result.value[0].cycle_sample_count == 8


def test_grouped_concurrency_uses_zero_for_every_accepted_cycle(
    wireless_stack,
):
    stack, service = wireless_stack
    empty_at = "2026-01-01T10:05:00.000Z"
    stack.observations.create_cycle(
        kind="client", site_id=SITE_A, started_at=empty_at,
        cycle_id="wireless-group-empty",
    )
    stack.observations.finalize_cycle(
        "wireless-group-empty", finished_at=empty_at, complete=True,
        result="success", source_rows_reported=0,
    )
    result = service.get_concurrent_client_distribution(
        SITE_A, FROM, TO, group_by="ap_mac"
    )
    assert result.status == "ok"
    assert result.provenance.source_rows_accepted == 8
    assert {item.context for item in result.value} == {AP_A}
    assert result.value[0].cycle_sample_count == 8
    assert result.value[0].minimum == 0


def test_grouped_concurrency_keeps_real_null_context_distinct(
    wireless_stack,
):
    stack, service = wireless_stack
    observed_at = "2026-01-01T10:05:30.000Z"
    stack.observations.create_cycle(
        kind="client", site_id=SITE_A, started_at=observed_at,
        cycle_id="wireless-real-null-context",
    )
    stack.observations.insert_client_batch([{
        "cycle_id": "wireless-real-null-context",
        "observed_at": observed_at, "site_id": SITE_A,
        "client_mac": CLIENT_A, "source_inventory_complete": True,
        "ap_mac": None,
    }])
    stack.observations.finalize_cycle(
        "wireless-real-null-context", finished_at=observed_at,
        complete=True, result="success", source_rows_reported=1,
        items_seen=1, items_stored=1,
    )
    result = service.get_concurrent_client_distribution(
        SITE_A, FROM, TO, group_by="ap_mac"
    )
    null_group = next(item for item in result.value if item.context is None)
    assert null_group.cycle_sample_count == 8
    assert null_group.minimum == 0
    assert null_group.maximum == 1


def test_grouped_concurrency_sufficiency_is_not_sum_of_groups(
    wireless_stack,
):
    stack, service = wireless_stack
    observed_at = "2026-01-01T10:05:30.000Z"
    stack.observations.create_cycle(
        kind="client", site_id=SITE_A, started_at=observed_at,
        cycle_id="wireless-second-ap-group",
    )
    stack.observations.insert_client_batch([{
        "cycle_id": "wireless-second-ap-group",
        "observed_at": observed_at, "site_id": SITE_A,
        "client_mac": CLIENT_A, "source_inventory_complete": True,
        "ap_mac": "02:AA:BB:CC:DD:99",
    }])
    stack.observations.finalize_cycle(
        "wireless-second-ap-group", finished_at=observed_at,
        complete=True, result="success", source_rows_reported=1,
        items_seen=1, items_stored=1,
    )
    strict = WirelessAnalyticsService(
        replace(service.config, wireless_min_samples=9), stack.gateway
    )
    result = strict.get_concurrent_client_distribution(
        SITE_A, FROM, TO, group_by="ap_mac"
    )
    assert len(result.value) == 2
    assert sum(item.cycle_sample_count for item in result.value) == 16
    assert result.provenance.sample_size == 8
    assert result.status == "insufficient_data"


def test_concurrent_cycle_provenance_is_factual(wireless_stack):
    stack, service = wireless_stack
    failed_at = "2026-01-01T10:06:00.000Z"
    stack.observations.create_cycle(
        kind="client", site_id=SITE_A, started_at=failed_at,
        cycle_id="wireless-failed-cycle",
    )
    stack.observations.finalize_cycle(
        "wireless-failed-cycle", finished_at=failed_at,
        complete=False, result="failed", error_count=1,
    )
    running_at = "2026-01-01T10:07:00.000Z"
    stack.observations.create_cycle(
        kind="client", site_id=SITE_A, started_at=running_at,
        cycle_id="wireless-abandoned-cycle",
    )
    stack.observations.initialize("2026-01-01T10:08:00.000Z")
    result = service.get_concurrent_client_distribution(SITE_A, FROM, TO)
    assert result.provenance.source_rows_examined == 10
    assert result.provenance.source_rows_accepted == 7
    assert result.provenance.source_rows_rejected == 3
    assert result.quality.partial_cycle_count == 1
    assert result.quality.failed_cycle_count == 1
    assert result.quality.abandoned_cycle_count == 1


def test_partial_cycle_excluded_default_and_diagnostic_is_partial(
    wireless_stack,
):
    _, service = wireless_stack
    strict = service.get_signal_distribution(SITE_A, FROM, TO, "rssi")
    diagnostic = service.get_signal_distribution(
        SITE_A, FROM, TO, "rssi",
        quality_mode="diagnostic_including_partial",
    )
    assert strict.status == "ok"
    assert diagnostic.status == "partial"
    assert diagnostic.provenance.quality_mode == "diagnostic_including_partial"
    assert diagnostic.provenance.source_rows_examined >= (
        strict.provenance.source_rows_examined
    )


@pytest.mark.parametrize("metric", ["cpu_util", "mem_util"])
def test_ap_resource_distribution_uses_overview_only(wireless_stack, metric):
    _, service = wireless_stack
    result = service.get_ap_resource_distribution(
        SITE_A, FROM, TO, metric
    )
    assert result.status == "ok"
    assert result.value.distribution.sample_count >= 4


@pytest.mark.parametrize(
    "metric", ["tx_util", "rx_util", "interference_util", "busy_util"]
)
def test_radio_utilization_keeps_band_and_ap_identity(wireless_stack, metric):
    _, service = wireless_stack
    result = service.get_radio_utilization(
        SITE_A, FROM, TO, metric, band="5GHz"
    )
    assert result.status == "ok"
    assert len(result.value.items) == 1
    assert result.value.items[0].band == "5GHz"
    assert result.value.items[0].ap_mac == AP_A
    assert result.value.distinct_ap_count == 1


def test_stored_rate_uses_only_reason_ok(wireless_stack):
    _, service = wireless_stack
    result = service.get_throughput_distribution(
        SITE_A, FROM, TO, "wired_download_mbps"
    )
    assert result.value.reason_counts["counter_reset"] == 1
    assert result.value.valid_rate_sample_count == 3
    assert result.value.excluded_rate_sample_count >= 2
    assert result.value.distribution.minimum == 10


def test_client_counter_rates_classify_positive_reset_exact_gap_and_large_gap(
    wireless_stack,
):
    stack, service = wireless_stack
    observed_at = "2026-01-01T10:08:00.000Z"
    stack.observations.create_cycle(
        kind="client", site_id=SITE_A, started_at=observed_at,
        cycle_id="wireless-client-large-gap",
    )
    stack.observations.insert_client_batch([{
        "cycle_id": "wireless-client-large-gap",
        "observed_at": observed_at, "site_id": SITE_A,
        "client_mac": CLIENT_A, "source_inventory_complete": True,
        "ap_mac": AP_A, "band": "5GHz", "traffic_down": 40,
        "traffic_up": 120,
    }])
    stack.observations.finalize_cycle(
        "wireless-client-large-gap", finished_at=observed_at,
        complete=True, result="success", source_rows_reported=1,
        items_seen=1, items_stored=1,
    )
    result = service.get_throughput_distribution(
        SITE_A, FROM, TO, "client_download_mbps"
    )
    reasons = result.value.reason_counts
    assert reasons["no_baseline"] == 2
    assert reasons["counter_reset"] >= 1
    assert reasons["gap_too_large"] >= 1
    assert result.value.valid_rate_sample_count >= 3
    assert result.value.distribution.minimum >= 0


def test_radio_counter_directions_are_independent(wireless_stack):
    _, service = wireless_stack
    result = service.get_counter_quality(
        SITE_A, FROM, TO, ap_mac=AP_A, band="5GHz"
    )
    rx = result.value.metrics["rx_retry_delta"]
    tx = result.value.metrics["tx_retry_delta"]
    assert rx.valid_interval_count >= 2
    assert tx.reset_interval_count >= 1
    assert rx.total_delta >= 0
    assert rx.controller_events_per_1000_packets is not None
    assert tx.controller_events_per_1000_packets is None


def test_counter_ratio_uses_only_jointly_valid_packet_intervals(
    wireless_stack,
):
    stack, service = wireless_stack
    ap_mac = "02:AA:BB:CC:DD:99"
    samples = (
        ("ratio-1", "2026-01-01T10:20:00.000Z", 10, 100),
        ("ratio-2", "2026-01-01T10:21:00.000Z", 20, 150),
        ("ratio-3", "2026-01-01T10:22:00.000Z", 30, 20),
        ("ratio-4", "2026-01-01T10:23:00.000Z", 40, None),
    )
    for cycle_id, observed_at, retry_packets, packets in samples:
        stack.observations.create_cycle(
            kind="ap_dynamic", site_id=SITE_A, started_at=observed_at,
            cycle_id=cycle_id,
        )
        stack.observations.insert_ap_batch([({
            "cycle_id": cycle_id, "observed_at": observed_at,
            "site_id": SITE_A, "ap_mac": ap_mac, "partial": False,
            "overview_ok": True, "wired_uplink_ok": True,
            "lan_traffic_ok": True, "radios_ok": True,
        }, [{
            "radio_observed_at": observed_at, "band": "5GHz",
            "rx_retry_packets": retry_packets, "rx_packets": packets,
        }])])
        stack.observations.finalize_cycle(
            cycle_id, finished_at=observed_at, complete=True,
            result="success", source_rows_reported=1,
            items_seen=1, items_stored=1,
        )
    result = service.get_counter_quality(
        SITE_A, FROM, TO, ap_mac=ap_mac, band="5GHz"
    )
    metric = result.value.metrics["rx_retry_delta"]
    assert metric.valid_interval_count == 3
    assert metric.total_delta == 30
    assert metric.ratio_event_delta == 10
    assert metric.packet_delta == 50
    assert metric.controller_events_per_1000_packets == 200


def test_radio_bands_are_never_merged(wireless_stack):
    stack, service = wireless_stack
    observed_at = "2026-01-01T10:06:00.000Z"
    stack.observations.create_cycle(
        kind="ap_dynamic", site_id=SITE_A, started_at=observed_at,
        cycle_id="wireless-two-bands",
    )
    stack.observations.insert_ap_batch([({
        "cycle_id": "wireless-two-bands", "observed_at": observed_at,
        "site_id": SITE_A, "ap_mac": AP_A, "partial": False,
        "overview_ok": True, "wired_uplink_ok": True,
        "lan_traffic_ok": True, "radios_ok": True,
    }, [
        {"radio_observed_at": observed_at, "band": "5GHz",
         "busy_util": 20},
        {"radio_observed_at": observed_at, "band": "2.4GHz",
         "busy_util": 90},
    ])])
    stack.observations.finalize_cycle(
        "wireless-two-bands", finished_at=observed_at, complete=True,
        result="success", source_rows_reported=1,
        items_seen=1, items_stored=1,
    )
    five = service.get_radio_utilization(
        SITE_A, FROM, TO, "busy_util", band="5GHz"
    )
    two = service.get_radio_utilization(
        SITE_A, FROM, TO, "busy_util", band="2.4GHz"
    )
    combined = service.get_radio_utilization(
        SITE_A, FROM, TO, "busy_util"
    )
    five_item = five.value.items[0]
    two_item = two.value.items[0]
    assert five_item.distribution.sample_count > 2
    assert two_item.distribution.sample_count == 1
    assert two_item.distribution.maximum is None  # min_samples=2
    assert {(item.ap_mac, item.band) for item in combined.value.items} == {
        (AP_A, "2.4GHz"), (AP_A, "5GHz")
    }
    assert next(
        item for item in combined.value.items if item.band == "2.4GHz"
    ).distribution.sample_count == 1
    bundle = service.get_wireless_evidence_bundle(SITE_A, FROM, TO)
    assert {
        item.band for item in bundle.radio_utilization["busy_util"].value.items
    } == {"2.4GHz", "5GHz"}


def test_partial_ap_and_radio_are_excluded_unless_diagnostic(wireless_stack):
    stack, service = wireless_stack
    observed_at = "2026-01-01T10:06:30.000Z"
    stack.observations.create_cycle(
        kind="ap_dynamic", site_id=SITE_A, started_at=observed_at,
        cycle_id="wireless-partial-ap",
    )
    stack.observations.insert_ap_batch([({
        "cycle_id": "wireless-partial-ap", "observed_at": observed_at,
        "site_id": SITE_A, "ap_mac": AP_A, "partial": True,
        "overview_ok": True, "wired_uplink_ok": False,
        "lan_traffic_ok": False, "radios_ok": True, "cpu_util": 999,
    }, [{"radio_observed_at": observed_at, "band": "5GHz",
         "busy_util": 999}])])
    stack.observations.finalize_cycle(
        "wireless-partial-ap", finished_at=observed_at, complete=False,
        result="partial", source_rows_reported=1,
        items_seen=1, items_stored=1,
    )
    strict = service.get_ap_resource_distribution(
        SITE_A, FROM, TO, "cpu_util"
    )
    diagnostic = service.get_ap_resource_distribution(
        SITE_A, FROM, TO, "cpu_util",
        quality_mode="diagnostic_including_partial",
    )
    assert strict.value.distribution.maximum < 999
    assert diagnostic.status == "partial"
    assert diagnostic.value.distribution.maximum == 999
    assert strict.provenance.source_rows_rejected >= 1


@pytest.mark.parametrize(
    "signal,target", [
        ("rssi", "busy_util"), ("snr", "busy_util"),
        ("rssi", "cpu_util"), ("snr", "cpu_util"),
    ]
)
def test_temporal_join_uses_predecessor_and_returns_coverage(
    wireless_stack, signal, target
):
    _, service = wireless_stack
    result = service.get_signal_ap_correlation(
        SITE_A, FROM, TO, signal, target
    )
    assert result.value.coverage.client_sample_count > 0
    assert result.value.coverage.matched_count > 0
    assert result.value.coverage.lag_max <= service.config.ap_join_max_lag_seconds
    assert result.value.coverage.match_ratio <= 1


def test_join_exact_max_lag_is_accepted_and_future_is_not(wireless_stack):
    stack, service = wireless_stack
    # The 10:04 client has no radio predecessor within 120 seconds; the
    # 10:10 future sample must never be used to fill that gap.
    result = service.get_signal_ap_correlation(
        SITE_A, FROM, TO, "rssi", "busy_util"
    )
    assert result.value.coverage.unmatched_count >= 1

    exact = replace(service.config, ap_join_max_lag_seconds=180)
    exact_result = WirelessAnalyticsService(exact, stack.gateway).get_signal_ap_correlation(
        SITE_A, FROM, TO, "rssi", "busy_util"
    )
    assert exact_result.value.coverage.matched_count >= (
        result.value.coverage.matched_count
    )


def test_wireless_window_is_hard_bounded_and_site_required(wireless_stack):
    _, service = wireless_stack
    with pytest.raises(AnalyticsQueryValidationError):
        service.get_signal_distribution(
            SITE_A, "2026-01-01T00:00:00.000Z",
            "2026-01-09T00:00:00.000Z", "rssi",
        )
    with pytest.raises(AnalyticsQueryValidationError):
        service.get_signal_distribution("", FROM, TO, "rssi")


def test_evidence_bundle_has_no_placement_recommendation(wireless_stack):
    _, service = wireless_stack
    bundle = service.get_wireless_evidence_bundle(SITE_A, FROM, TO)
    rendered = repr(bundle).lower()
    assert "needs_second_ap" not in rendered
    assert "move_ap" not in rendered
    assert "bad_ap" not in rendered
    assert "192.0.2." not in rendered
