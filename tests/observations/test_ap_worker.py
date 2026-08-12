from __future__ import annotations

import json
import logging
from dataclasses import replace
from pathlib import Path

from app.models import Result
from app.observations.ap_worker import APObservationWorker, _rate
from app.observations.telemetry import ObservationTelemetry


FIXTURES = Path(__file__).parent / "fixtures" / "omada"


def raw(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))["result"]


class Clock:
    mono = 0.0
    now = "2026-01-01T00:00:00.000Z"

    def monotonic(self):
        return self.mono

    def utc(self):
        return self.now


class Events:
    def __init__(self):
        self.items = []

    def safe_emit_system(self, event, level="info", **fields):
        self.items.append((event, level, fields))
        return True


class Provider:
    def __init__(self):
        self.calls = []
        self.ap_calls = []
        self.inventory_failure = None
        self.dynamic_failures = set()
        self.inventory_rows = list(raw("01_devices.json")["data"])

    def list_observation_access_points(self, site, page, page_size, timeout):
        self.calls.append(("inventory", site, page, timeout))
        if self.inventory_failure is not None:
            return self.inventory_failure
        return Result.ok(data={
            "access_points": self.inventory_rows,
            "total_rows": len(self.inventory_rows),
            "page": page,
            "page_size": page_size,
            "http_status": 200,
            "error_code": 0,
        })

    def _result(self, name, fixture):
        self.calls.append((name,))
        if name in self.dynamic_failures:
            return Result.fail(error="HTTP_ERROR", data={"failure_category": "timeout"})
        value = raw(fixture)
        if name == "safe_overrides":
            for item in value["ssidOverrides"]:
                item.pop("ssidPassword", None)
        return Result.ok(data={"result": value, "http_status": 200, "error_code": 0})

    def _ap_result(self, name, fixture, args):
        self.ap_calls.append((name, args[1]))
        return self._result(name, fixture)

    def get_observation_ap_overview(self, *args): return self._ap_result("overview", "02_ap_overview.json", args)
    def get_observation_ap_wired_uplink(self, *args): return self._ap_result("wired", "03_wired_uplink.json", args)
    def get_observation_ap_lan_traffic(self, *args): return self._ap_result("lan", "04_lan_traffic_info.json", args)
    def get_observation_ap_radios(self, *args): return self._ap_result("radios", "05_radios.json", args)
    def get_observation_ap_general_config(self, *args): return self._ap_result("general", "06_general_config.json", args)
    def get_observation_ap_ip_setting(self, *args): return self._ap_result("ip", "07_ip_setting.json", args)
    def get_observation_ap_radio_config(self, *args): return self._ap_result("radio_config", "08_radio_config.json", args)
    def get_observation_ap_ofdma(self, *args): return self._ap_result("ofdma", "09_ofdma.json", args)
    def get_observation_ap_available_channels(self, *args): return self._ap_result("channels", "10_available_channel.json", args)
    def get_observation_ap_safe_overrides(self, *args): return self._ap_result("safe_overrides", "11_override_v2.json", args)
    def get_observation_ap_rf_scan_state(self, *args): return self._ap_result("rf", "12_rf_scan_result_v2.json", args)


def make_worker(repository, observation_config, provider=None, clock=None, **updates):
    provider = provider or Provider()
    clock = clock or Clock()
    events = Events()
    values = {
        "client_enabled": False,
        "ap_enabled": True,
        "site_ids": ("site-a",),
        "ap_initial_delay_seconds": 60,
        "ap_interval_seconds": 30,
        "ap_inventory_interval_seconds": 300,
        "ap_inventory_max_stale_seconds": 900,
        "ap_config_interval_seconds": 21600,
        "request_timeout_seconds": 5,
        "ap_page_size": 100,
        "ap_max_pages": 10,
        "ap_max_rows": 500,
        "ap_dynamic_max_requests_per_cycle": 200,
        "ap_config_max_requests_per_cycle": 200,
        "ap_cycle_max_duration_seconds": 120,
        "ap_config_cycle_max_duration_seconds": 180,
        "rate_max_gap_seconds": 180,
    }
    values.update(updates)
    config = replace(observation_config, **values)
    worker = APObservationWorker(
        provider=provider,
        repository=repository,
        config=config,
        telemetry=ObservationTelemetry(events, logging.getLogger("test-ap-worker")),
        now_factory=clock.utc,
        monotonic=clock.monotonic,
    )
    return worker, provider, clock, events


def test_dynamic_fixture_cycle_persists_sections_and_radios(repository, observation_config):
    subject, provider, _, events = make_worker(repository, observation_config)
    outcome = subject.run_dynamic_once()[0]

    assert (outcome.result, outcome.complete) == ("success", True)
    assert outcome.request_count == 5
    with repository.read_connection() as connection:
        ap = connection.execute("SELECT * FROM ap_observations").fetchone()
        radios = connection.execute("SELECT * FROM ap_radio_observations ORDER BY band").fetchall()
    assert ap["ap_mac"] == "02:00:00:00:00:01"
    assert ap["wired_down_bytes"] == 245897982444
    assert ap["wired_download_rate_reason"] == "no_baseline"
    assert [row["band"] for row in radios] == ["2g", "5g"]
    assert all(row["radio_id"] is None for row in radios)
    assert any(item[0] == "observation.ap_cycle_completed" for item in events.items)
    assert provider.calls[0][0] == "inventory"


def test_second_cycle_calculates_independent_rates(repository, observation_config):
    subject, provider, clock, _ = make_worker(repository, observation_config)
    first = subject.run_dynamic_once()[0]
    assert first.result == "success"

    clock.mono = 60
    clock.now = "2026-01-01T00:01:00.000Z"
    original = provider._result

    def increased(name, fixture_name):
        response = original(name, fixture_name)
        value = response.data["result"]
        if name == "wired":
            value["wiredUplink"]["downBytes"] += 7_500_000
            value["wiredUplink"]["upBytes"] -= 1
        if name == "lan":
            value["lanTraffic"]["rx"] += 15_000_000
        return response

    provider._result = increased
    second = subject.run_dynamic_once()[0]
    assert second.result == "success"
    with repository.read_connection() as connection:
        ap = connection.execute("SELECT * FROM ap_observations ORDER BY row_id DESC LIMIT 1").fetchone()
    assert ap["wired_download_mbps"] == 1.0
    assert ap["wired_download_rate_reason"] == "ok"
    assert ap["wired_upload_mbps"] is None
    assert ap["wired_upload_rate_reason"] == "counter_reset"
    assert ap["lan_rx_mbps"] == 2.0


def test_partial_sections_persist_and_all_failed_does_not(repository, observation_config):
    provider = Provider()
    provider.dynamic_failures = {"wired", "lan", "radios"}
    subject, _, _, _ = make_worker(repository, observation_config, provider=provider)
    partial = subject.run_dynamic_once()[0]
    assert (partial.result, partial.complete, partial.items_stored) == ("partial", False, 1)

    provider2 = Provider()
    provider2.dynamic_failures = {"overview", "wired", "lan", "radios"}
    subject2, _, _, _ = make_worker(repository, observation_config, provider=provider2)
    failed = subject2.run_dynamic_once()[0]
    assert failed.result == "failed"
    assert failed.items_stored == 0


def test_overview_failure_does_not_cancel_other_dynamic_sections(
    repository, observation_config
):
    provider = Provider()
    provider.dynamic_failures = {"overview"}
    subject, _, _, _ = make_worker(
        repository, observation_config, provider=provider
    )

    outcome = subject.run_dynamic_once()[0]

    assert (outcome.result, outcome.items_stored, outcome.request_count) == (
        "partial", 1, 5
    )
    assert [name for name, _ in provider.ap_calls] == [
        "overview", "wired", "lan", "radios"
    ]
    with repository.read_connection() as connection:
        ap = connection.execute("SELECT * FROM ap_observations").fetchone()
        radio_count = connection.execute(
            "SELECT COUNT(*) FROM ap_radio_observations"
        ).fetchone()[0]
    assert ap["overview_ok"] == 0
    assert ap["wired_uplink_ok"] == 1
    assert ap["lan_traffic_ok"] == 1
    assert ap["radios_ok"] == 1
    assert ap["wired_down_bytes"] == 245897982444
    assert radio_count == 2


def test_complete_config_is_change_deduplicated(repository, observation_config):
    subject, _, clock, events = make_worker(repository, observation_config)
    first = subject.run_config_once()[0]
    assert (first.result, first.items_stored, first.request_count) == ("success", 1, 8)
    clock.mono = 10
    clock.now = "2026-01-01T00:00:10.000Z"
    second = subject.run_config_once()[0]
    assert (second.result, second.items_stored) == ("success", 0)
    with repository.read_connection() as connection:
        rows = connection.execute("SELECT * FROM ap_config_snapshots").fetchall()
        dump = "\n".join(connection.iterdump())
    assert len(rows) == 1
    assert "TEST_WIFI_PASSWORD_SHOULD_NOT_LEAK" not in dump
    assert any(item[0] == "observation.ap_config_unchanged" for item in events.items)


def test_null_rf_scan_result_creates_complete_config_snapshot(
    repository, observation_config
):
    provider = Provider()
    provider.get_observation_ap_rf_scan_state = lambda *args: Result.ok(
        data={"result": None, "http_status": 200, "error_code": 0}
    )
    subject, _, _, _ = make_worker(
        repository, observation_config, provider=provider
    )

    outcome = subject.run_config_once()[0]

    assert (outcome.result, outcome.complete, outcome.items_stored) == (
        "success", True, 1
    )
    with repository.read_connection() as connection:
        row = connection.execute(
            "SELECT config_json FROM ap_config_snapshots"
        ).fetchone()
    assert json.loads(row["config_json"])["rf_scan"] is None


def test_stale_cache_is_bounded_and_refresh_failure_is_partial(repository, observation_config):
    subject, provider, clock, _ = make_worker(repository, observation_config)
    assert subject.run_dynamic_once()[0].result == "success"
    clock.mono = 400
    clock.now = "2026-01-01T00:06:40.000Z"
    provider.inventory_failure = Result.fail(error="HTTP_ERROR", data={"failure_category": "timeout"})
    stale = subject.run_dynamic_once()[0]
    assert stale.result == "partial"
    assert stale.items_stored == 1

    clock.mono = 1000
    expired = subject.run_dynamic_once()[0]
    assert expired.result == "failed"
    assert expired.items_stored == 0
    assert expired.failure_category == "inventory_stale_expired"


def test_request_budget_stops_new_calls_and_rotates_cursor(repository, observation_config):
    provider = Provider()
    provider.inventory_rows.append({
        **provider.inventory_rows[0],
        "mac": "02-00-00-00-00-02",
        "name": "TEST_AP_2",
    })
    subject, _, _, _ = make_worker(
        repository,
        observation_config,
        provider=provider,
        ap_dynamic_max_requests_per_cycle=2,
    )
    outcome = subject.run_dynamic_once()[0]
    assert outcome.request_count == 2
    assert outcome.result == "partial"
    assert subject._cursor[("site-a", "ap_dynamic")] == 1
    first_cycle_calls = len(provider.ap_calls)
    second = subject.run_dynamic_once()[0]
    assert second.result == "partial"
    assert provider.ap_calls[first_cycle_calls][1] == "02:00:00:00:00:02"


def test_inventory_pagination_is_complete_and_bounded(repository, observation_config):
    provider = Provider()
    second = {
        **provider.inventory_rows[0],
        "mac": "02-00-00-00-00-02",
        "name": "TEST_AP_2",
    }
    pages = [[provider.inventory_rows[0]], [second]]

    def page(site, page_number, page_size, timeout):
        provider.calls.append(("inventory", site, page_number, timeout))
        return Result.ok(data={
            "access_points": pages[page_number - 1],
            "total_rows": 2,
            "page": page_number,
            "page_size": page_size,
        })

    provider.list_observation_access_points = page
    subject, _, _, _ = make_worker(
        repository, observation_config, provider=provider, ap_page_size=1
    )
    outcome = subject.run_dynamic_once()[0]
    assert (outcome.result, outcome.items_seen) == ("success", 2)
    assert [call[2] for call in provider.calls if call[0] == "inventory"] == [1, 2]


def test_inventory_row_and_page_limits_never_poll_partial_inventory(
    repository, observation_config
):
    provider = Provider()
    provider.inventory_rows.append({
        **provider.inventory_rows[0],
        "mac": "02-00-00-00-00-02",
    })
    row_limited, _, _, _ = make_worker(
        repository,
        observation_config,
        provider=provider,
        ap_page_size=2,
        ap_max_rows=1,
    )
    outcome = row_limited.run_dynamic_once()[0]
    assert (outcome.result, outcome.request_count) == ("failed", 1)
    assert provider.ap_calls == []

    provider2 = Provider()
    provider2.inventory_rows.append({
        **provider2.inventory_rows[0],
        "mac": "02-00-00-00-00-02",
    })

    def first_page(site, page_number, page_size, timeout):
        provider2.calls.append(("inventory", site, page_number, timeout))
        return Result.ok(data={
            "access_points": [provider2.inventory_rows[0]],
            "total_rows": 2,
            "page": page_number,
            "page_size": page_size,
        })

    provider2.list_observation_access_points = first_page
    page_limited, _, _, _ = make_worker(
        repository,
        observation_config,
        provider=provider2,
        ap_page_size=1,
        ap_max_pages=1,
    )
    outcome2 = page_limited.run_dynamic_once()[0]
    assert (outcome2.result, outcome2.request_count) == ("failed", 1)
    assert provider2.ap_calls == []


def test_inventory_filters_non_ap_rows_without_losing_valid_aps(
    repository, observation_config
):
    provider = Provider()
    provider.inventory_rows.append({
        "type": "switch",
        "mac": "02-00-00-00-00-99",
    })
    subject, _, _, _ = make_worker(
        repository, observation_config, provider=provider
    )
    outcome = subject.run_dynamic_once()[0]
    assert (outcome.result, outcome.items_seen, outcome.items_stored) == (
        "success", 1, 1
    )


def test_new_worker_has_no_stale_inventory_cache(repository, observation_config):
    provider = Provider()
    provider.inventory_failure = Result.fail(
        error="HTTP_ERROR", data={"failure_category": "timeout"}
    )
    subject, _, _, _ = make_worker(
        repository, observation_config, provider=provider
    )
    outcome = subject.run_dynamic_once()[0]
    assert (outcome.result, outcome.items_stored) == ("failed", 0)
    assert provider.ap_calls == []


def test_expired_deadline_starts_no_provider_request(repository, observation_config):
    provider = Provider()
    ticks = iter([0.0, 6.0, 6.0, 6.0, 6.0])
    events = Events()
    config = replace(
        observation_config,
        client_enabled=False,
        ap_enabled=True,
        site_ids=("site-a",),
        ap_cycle_max_duration_seconds=5,
    )
    subject = APObservationWorker(
        provider=provider,
        repository=repository,
        config=config,
        telemetry=ObservationTelemetry(events, logging.getLogger("deadline")),
        now_factory=lambda: "2026-01-01T00:00:00.000Z",
        monotonic=lambda: next(ticks),
    )
    outcome = subject.run_dynamic_once()[0]
    assert outcome.result == "failed"
    assert outcome.request_count == 0
    assert outcome.failure_category == "deadline"
    assert provider.calls == []


def test_duplicate_inventory_mac_excludes_all_copies(repository, observation_config):
    provider = Provider()
    provider.inventory_rows.append(dict(provider.inventory_rows[0]))
    subject, _, _, _ = make_worker(repository, observation_config, provider=provider)
    outcome = subject.run_dynamic_once()[0]
    assert outcome.result == "failed"
    assert outcome.items_seen == 0
    assert [call for call in provider.calls if call[0] != "inventory"] == []


def test_duplicate_inventory_is_reported_and_makes_other_results_partial(
    repository, observation_config
):
    provider = Provider()
    provider.inventory_rows.extend([
        dict(provider.inventory_rows[0]),
        {**provider.inventory_rows[0], "mac": "02-00-00-00-00-02"},
    ])
    subject, _, _, events = make_worker(
        repository, observation_config, provider=provider
    )
    outcome = subject.run_dynamic_once()[0]
    assert (outcome.result, outcome.items_seen, outcome.items_stored) == (
        "partial", 1, 1
    )
    completed = [
        fields for event, _, fields in events.items
        if event == "observation.ap_cycle_failed"
    ]
    assert completed[-1]["duplicate_ap_mac_count"] == 1


def test_nonempty_inventory_with_storage_failure_is_failed(
    repository, observation_config, monkeypatch
):
    subject, _, _, _ = make_worker(repository, observation_config)
    monkeypatch.setattr(
        repository,
        "insert_ap_batch",
        lambda entries: (_ for _ in ()).throw(RuntimeError("storage failed")),
    )
    outcome = subject.run_dynamic_once()[0]
    assert (outcome.result, outcome.items_stored) == ("failed", 0)


def test_incomplete_config_writes_no_row_or_latest_hash(
    repository, observation_config
):
    provider = Provider()
    provider.dynamic_failures.add("ofdma")
    subject, _, _, _ = make_worker(
        repository, observation_config, provider=provider
    )
    outcome = subject.run_config_once()[0]
    assert (outcome.result, outcome.items_stored) == ("failed", 0)
    assert repository.get_latest_complete_config_hash(
        site_id="site-a", ap_mac="02:00:00:00:00:01"
    ) is None


def test_stop_prevents_new_requests_and_start_is_idempotent(repository, observation_config):
    subject, provider, _, _ = make_worker(repository, observation_config)
    assert subject.start() is True
    assert subject.start() is False
    assert subject.stop(1) is True
    assert subject.run_dynamic_once() == ()
    assert provider.calls == []


def test_rate_reasons_cover_gap_invalid_and_unavailable():
    assert _rate(None, 1, None, 180) == (None, "source_unavailable")
    assert _rate("2026-01-01T00:00:00.000Z", 1, ("2026-01-01T00:00:00.000Z", 0), 180) == (None, "invalid_elapsed")
    assert _rate("2026-01-01T00:10:00.000Z", 1, ("2026-01-01T00:00:00.000Z", 0), 180) == (None, "gap_too_large")
