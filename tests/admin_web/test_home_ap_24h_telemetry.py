from __future__ import annotations

import logging
import threading
import time
from copy import deepcopy
from types import SimpleNamespace

import pytest

from app import config as repository_config
from app.admin_web.home_ap_24h_telemetry import (
    COMPONENT,
    HomeAp24TelemetryConfig,
    HomeAp24TelemetryConfigError,
    HomeAp24TelemetryWorker,
    create_home_ap_24h_telemetry_worker,
    home_ap_24h_telemetry_config_from_settings,
)
from app.admin_web.query_service import AdminQueryBusy, AdminQueryDeadline
from app.analytics.home_ap_24h import HomeAp24SourceUnavailable
from app.analytics.source_gateway import QueryDeadline
from app.settings import get_settings

from .conftest import SITE_ID
from .test_home_ap_24h import result as ap24_result


class Telemetry:
    enabled = True
    available = True

    def __init__(self, *, raise_on_emit: bool = False):
        self.events = []
        self.raise_on_emit = raise_on_emit

    def safe_emit_system(self, event, level="info", **fields):
        if self.raise_on_emit:
            raise OSError("telemetry unavailable")
        self.events.append((event, level, fields))
        return True


class Controls:
    def __init__(self):
        self.calls = 0
        self.deadline = QueryDeadline.after(60)
        self.max_query_duration_seconds = 10

    def run(self, operation):
        self.calls += 1
        return operation(self.deadline)


class Source:
    def __init__(self, value=None, *, error=None):
        self.value = value if value is not None else ap24_result()
        self.error = error
        self.calls = []

    def get_home_ap_24h(self, site_id, **kwargs):
        self.calls.append((site_id, kwargs))
        if self.error is not None:
            raise self.error
        return self.value


def config(*, initial=15, interval=120):
    return HomeAp24TelemetryConfig(True, initial, interval)


def worker(*, value=None, source=None, controls=None, telemetry=None, sites=None):
    return HomeAp24TelemetryWorker(
        config=config(),
        site_ids=sites or (SITE_ID,),
        read_service=source or Source(value),
        execution_controls=controls or Controls(),
        telemetry=telemetry or Telemetry(),
        logger=logging.getLogger("ap24-telemetry-test"),
    )


def two_ap_value(*, has_more=False):
    value = deepcopy(ap24_result(has_more=has_more))
    second = deepcopy(value["items"][0])
    second.update({
        "ap_mac": "AA:BB:CC:DD:EE:02",
        "name": "AP-2",
        "model": "EAP-2",
    })
    value["items"].append(second)
    value["summary"]["ap_count_in_window"] = 2
    for axis in ("current", "history", "observation_quality"):
        value["summary"][axis]["operational"] = 2
    return value


def events(telemetry, name):
    return [fields for event, _level, fields in telemetry.events if event == name]


def test_telemetry_is_disabled_by_default_and_ignores_inactive_optional_values():
    selected = home_ap_24h_telemetry_config_from_settings({
        "web_admin_home_ap_24h_telemetry_interval_seconds": "broken",
    })
    assert selected == HomeAp24TelemetryConfig(False, 15, 120)


def test_repository_settings_expose_all_telemetry_controls():
    settings = get_settings()
    assert settings["web_admin_home_ap_24h_telemetry_enabled"] == (
        repository_config.WEB_ADMIN_HOME_AP_24H_TELEMETRY_ENABLED
    )
    assert settings[
        "web_admin_home_ap_24h_telemetry_initial_delay_seconds"
    ] == repository_config.WEB_ADMIN_HOME_AP_24H_TELEMETRY_INITIAL_DELAY_SECONDS
    assert settings["web_admin_home_ap_24h_telemetry_interval_seconds"] == (
        repository_config.WEB_ADMIN_HOME_AP_24H_TELEMETRY_INTERVAL_SECONDS
    )


@pytest.mark.parametrize("settings", [
    {"web_admin_home_ap_24h_telemetry_enabled": "yes"},
    {
        "web_admin_home_ap_24h_telemetry_enabled": "true",
        "web_admin_home_ap_24h_telemetry_initial_delay_seconds": "-1",
    },
    {
        "web_admin_home_ap_24h_telemetry_enabled": "true",
        "web_admin_home_ap_24h_telemetry_initial_delay_seconds": "3601",
    },
    {
        "web_admin_home_ap_24h_telemetry_enabled": "true",
        "web_admin_home_ap_24h_telemetry_interval_seconds": "59",
    },
    {
        "web_admin_home_ap_24h_telemetry_enabled": "true",
        "web_admin_home_ap_24h_telemetry_interval_seconds": "3601",
    },
])
def test_enabled_telemetry_configuration_is_strict_and_bounded(settings):
    with pytest.raises(HomeAp24TelemetryConfigError):
        home_ap_24h_telemetry_config_from_settings(settings)


def test_invalid_enabled_configuration_fails_worker_composition_closed():
    selected = create_home_ap_24h_telemetry_worker(
        {
            "web_admin_home_ap_24h_telemetry_enabled": "true",
            "web_admin_home_ap_24h_telemetry_interval_seconds": "broken",
        },
        admin_runtime=valid_runtime(),
        telemetry=Telemetry(),
        logger=logging.getLogger("ap24-telemetry-invalid-config"),
    )
    assert selected is None


def valid_runtime():
    return SimpleNamespace(
        state="active",
        home_ap_24h_state="active",
        home_ap_24h_service=Source(),
        query_execution_controls=Controls(),
        config=SimpleNamespace(allowed_site_ids=frozenset({SITE_ID})),
    )


@pytest.mark.parametrize("mutation", [
    lambda runtime, telemetry: setattr(runtime, "state", "unavailable"),
    lambda runtime, telemetry: setattr(runtime, "home_ap_24h_state", "disabled"),
    lambda runtime, telemetry: setattr(runtime, "home_ap_24h_service", None),
    lambda runtime, telemetry: setattr(runtime, "query_execution_controls", None),
    lambda runtime, telemetry: setattr(runtime.config, "allowed_site_ids", frozenset()),
    lambda runtime, telemetry: setattr(telemetry, "enabled", False),
    lambda runtime, telemetry: setattr(telemetry, "available", False),
])
def test_worker_cannot_compose_without_every_active_prerequisite(mutation):
    runtime = valid_runtime()
    telemetry = Telemetry()
    mutation(runtime, telemetry)
    selected = create_home_ap_24h_telemetry_worker(
        {"web_admin_home_ap_24h_telemetry_enabled": "true"},
        admin_runtime=runtime,
        telemetry=telemetry,
        logger=logging.getLogger("ap24-telemetry-prerequisite"),
    )
    assert selected is None


def test_worker_start_stop_is_idempotent_and_initial_wait_is_prompt():
    telemetry = Telemetry()
    selected = HomeAp24TelemetryWorker(
        config=config(initial=3600),
        site_ids=(SITE_ID,),
        read_service=Source(),
        execution_controls=Controls(),
        telemetry=telemetry,
        logger=logging.getLogger("ap24-telemetry-lifecycle"),
    )
    assert selected.start() is True
    assert selected.start() is False
    started = time.monotonic()
    assert selected.stop(timeout_seconds=1) is True
    assert time.monotonic() - started < 0.5
    assert selected.stop(timeout_seconds=1) is True
    started_events = events(telemetry, "home_ap_24h.telemetry_started")
    assert started_events == [{
        "component": COMPONENT,
        "interval_seconds": 120,
        "initial_delay_seconds": 3600,
        "site_count": 1,
    }]


def test_worker_fixed_delay_wait_is_prompt_after_a_cycle():
    source = Source()
    selected = HomeAp24TelemetryWorker(
        config=config(initial=0, interval=3600),
        site_ids=(SITE_ID,),
        read_service=source,
        execution_controls=Controls(),
        telemetry=Telemetry(),
        logger=logging.getLogger("ap24-telemetry-fixed-delay"),
    )
    assert selected.start() is True
    deadline = time.monotonic() + 1
    while not source.calls and time.monotonic() < deadline:
        time.sleep(0.005)
    assert len(source.calls) == 1
    started = time.monotonic()
    assert selected.stop(timeout_seconds=1) is True
    assert time.monotonic() - started < 0.5


def test_worker_rejects_overlapping_cycles():
    entered = threading.Event()
    release = threading.Event()

    class BlockingSource(Source):
        def get_home_ap_24h(self, site_id, **kwargs):
            entered.set()
            assert release.wait(2)
            return super().get_home_ap_24h(site_id, **kwargs)

    selected = worker(source=BlockingSource())
    result = []
    thread = threading.Thread(target=lambda: result.append(selected.run_once()))
    thread.start()
    assert entered.wait(1)
    assert selected.run_once() is False
    release.set()
    thread.join(2)
    assert result == [True]


def test_cycle_uses_shared_execution_controls_and_canonical_page_bound():
    controls = Controls()
    source = Source()
    selected = worker(source=source, controls=controls)
    assert selected.run_once() is True
    assert controls.calls == 1
    assert source.calls == [(SITE_ID, {
        "evaluated_at_utc": None,
        "after_ap_mac": None,
        "limit": 20,
        "deadline": controls.deadline,
    })]


def test_two_ap_snapshot_maps_existing_contract_without_recalculation():
    value = two_ap_value(has_more=True)
    value["block_status"] = "degraded"
    value["block_reason"] = "source_evidence_degraded"
    value["sources"]["current_state"].update({
        "status": "degraded", "complete_cycle_count": 11,
        "partial_cycle_count": 2, "failed_cycle_count": 3,
        "max_gap_seconds": 77,
    })
    value["sources"]["observations"].update({
        "status": "degraded", "complete_cycle_count": 7,
        "partial_cycle_count": 4, "failed_cycle_count": 5,
        "max_gap_seconds": 88,
    })
    item = value["items"][0]
    item["history"].update({
        "operational_seconds": 86000,
        "unavailable_seconds": 400,
        "authoritative_sample_count": 123,
        "max_gap_seconds": 66,
    })
    item["observation_quality"].update({
        "complete_sample_count": 99,
        "diagnostic_partial_sample_count": 6,
        "section_problem_counts": {
            "overview": 1, "wired_uplink": 2,
            "lan_traffic": 3, "radios": 4,
        },
    })
    telemetry = Telemetry()
    selected = worker(value=value, telemetry=telemetry)
    assert selected.run_once() is True

    snapshots = events(telemetry, "home_ap_24h.snapshot")
    details = events(telemetry, "home_ap_24h.ap_snapshot")
    assert len(snapshots) == 1
    assert len(details) == 2
    snapshot = snapshots[0]
    assert snapshot["snapshot_id"] == details[0]["snapshot_id"] == details[1]["snapshot_id"]
    assert snapshot["evaluated_at_utc"] == details[0]["evaluated_at_utc"] == details[1]["evaluated_at_utc"]
    assert snapshot["block_status"] == "degraded"
    assert snapshot["block_reason"] == "source_evidence_degraded"
    assert snapshot["current_state_complete_cycle_count"] == 11
    assert snapshot["current_state_partial_cycle_count"] == 2
    assert snapshot["current_state_failed_cycle_count"] == 3
    assert snapshot["current_state_max_gap_seconds"] == 77
    assert snapshot["observations_status"] == "degraded"
    assert snapshot["observations_complete_cycle_count"] == 7
    assert snapshot["observations_partial_cycle_count"] == 4
    assert snapshot["observations_failed_cycle_count"] == 5
    assert snapshot["observations_max_gap_seconds"] == 88
    assert snapshot["detail_emitted_count"] == 2
    assert snapshot["detail_truncated"] is True
    first = details[0]
    assert first["ap_mac"] == "AA:BB:CC:DD:EE:01"
    assert first["ap_name"] == "AP"
    assert first["model"] == "EAP"
    assert first["unavailable_seconds"] == 400
    assert first["authoritative_sample_count"] == 123
    assert first["complete_sample_count"] == 99
    assert first["diagnostic_partial_sample_count"] == 6
    assert first["overview_problem_count"] == 1
    assert first["wired_uplink_problem_count"] == 2
    assert first["lan_traffic_problem_count"] == 3
    assert first["radios_problem_count"] == 4


@pytest.mark.parametrize("failure,category", [
    (AdminQueryBusy(), "concurrency_limit"),
    (AdminQueryDeadline(), "query_deadline"),
    (HomeAp24SourceUnavailable(), "source_unavailable"),
])
def test_bounded_query_failures_emit_stable_category(failure, category):
    class FailingControls:
        max_query_duration_seconds = 10

        def run(self, _operation):
            raise failure

    telemetry = Telemetry()
    selected = worker(controls=FailingControls(), telemetry=telemetry)
    assert selected.run_once() is True
    failed = events(telemetry, "home_ap_24h.snapshot_failed")
    assert failed == [{
        "component": COMPONENT,
        "site_id": SITE_ID,
        "failure_category": category,
    }]


def test_serialization_failure_is_bounded_and_worker_continues():
    value = ap24_result()
    value["contract_version"] = "broken"
    telemetry = Telemetry()
    selected = worker(value=value, telemetry=telemetry)
    assert selected.run_once() is True
    assert selected.run_once() is True
    assert [item["failure_category"] for item in events(
        telemetry, "home_ap_24h.snapshot_failed"
    )] == ["serialization_error", "serialization_error"]


def test_internal_failure_is_bounded_and_later_site_still_runs():
    other = "ffffffffffffffffffffffff"

    class PerSiteSource(Source):
        def get_home_ap_24h(self, site_id, **kwargs):
            if site_id == SITE_ID:
                self.calls.append((site_id, kwargs))
                raise RuntimeError("private source detail")
            return super().get_home_ap_24h(site_id, **kwargs)

    source = PerSiteSource()
    telemetry = Telemetry()
    selected = worker(
        source=source,
        telemetry=telemetry,
        sites=(SITE_ID, other),
    )
    assert selected.run_once() is True
    assert events(telemetry, "home_ap_24h.snapshot_failed") == [{
        "component": COMPONENT,
        "site_id": SITE_ID,
        "failure_category": "internal_error",
    }]
    assert len(events(telemetry, "home_ap_24h.snapshot")) == 1
    assert [site for site, _kwargs in source.calls] == [SITE_ID, other]


def test_telemetry_emit_failure_is_fail_open_and_next_cycle_runs():
    source = Source()
    selected = worker(source=source, telemetry=Telemetry(raise_on_emit=True))
    assert selected.run_once() is True
    assert selected.run_once() is True
    assert len(source.calls) == 2


def test_cycle_does_not_mutate_service_result_or_expose_raw_timeline():
    value = two_ap_value()
    before = deepcopy(value)
    telemetry = Telemetry()
    selected = worker(value=value, telemetry=telemetry)
    assert selected.run_once() is True
    assert value == before
    assert events(telemetry, "home_ap_24h.snapshot")[0][
        "detail_truncated"
    ] is False
    for _event, _level, fields in telemetry.events:
        assert "timeline" not in fields
        assert "raw" not in fields


def test_factory_composes_sorted_sites_only_when_enabled():
    runtime = valid_runtime()
    other = "ffffffffffffffffffffffff"
    runtime.config.allowed_site_ids = frozenset({other, SITE_ID})
    selected = create_home_ap_24h_telemetry_worker(
        {"web_admin_home_ap_24h_telemetry_enabled": "true"},
        admin_runtime=runtime,
        telemetry=Telemetry(),
        logger=logging.getLogger("ap24-telemetry-factory"),
    )
    assert selected is not None
    assert selected._site_ids == (SITE_ID, other)  # noqa: SLF001
