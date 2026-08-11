from __future__ import annotations

import logging
import sqlite3
from dataclasses import replace

from app.models import Result
from app.observations.client_worker import ClientObservationWorker


def eligible(mac="AA:BB:CC:DD:EE:01", **updates):
    row = {
        "mac": mac,
        "wireless": True,
        "active": True,
        "authStatus": 2,
        "ssid": "Zefer_Parki",
        "ip": "192.168.1.10",
        "radioId": 1,
        "trafficDown": 100,
        "trafficUp": 200,
    }
    row.update(updates)
    return row


def page(rows, total, page_number=1):
    return Result.ok(data={
        "clients": rows,
        "total_rows": total,
        "page": page_number,
        "page_size": 500,
        "http_status": 200,
        "error_code": 0,
    })


class Provider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def list_observation_clients(self, site, page_number, page_size, timeout):
        self.calls.append((site, page_number, page_size, timeout))
        response = self.responses.pop(0)
        return response() if callable(response) else response


def worker(repository, observation_config, provider, **updates):
    values = {
        "client_enabled": True,
        "site_ids": ("site-a",),
        "client_ssids": (),
        "client_initial_delay_seconds": 0.01,
        "client_interval_seconds": 0.01,
        "request_timeout_seconds": 5.0,
        "client_page_size": 500,
        "client_max_pages": 20,
        "client_max_rows": 10_000,
    }
    values.update(updates)
    config = replace(observation_config, **values)
    ticks = iter(range(1000))
    return ClientObservationWorker(
        provider=provider,
        repository=repository,
        config=config,
        logger=logging.getLogger(f"test-observation-{id(provider)}"),
        now_factory=lambda: "2026-01-01T00:00:00.000Z",
        monotonic=lambda: float(next(ticks)),
    )


def rows_in_db(repository):
    with repository.read_connection() as connection:
        return connection.execute(
            "SELECT * FROM client_observations ORDER BY row_id"
        ).fetchall()


def test_complete_cycle_persists_only_eligible_rows(repository, observation_config):
    provider = Provider([page([
        eligible(),
        eligible("AA:BB:CC:DD:EE:02", authStatus=1),
        eligible("AA:BB:CC:DD:EE:03", wireless=False),
    ], 3)])
    subject = worker(repository, observation_config, provider)

    outcomes = subject.run_once()

    assert subject.provider is provider
    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert (outcome.result, outcome.complete) == ("success", True)
    assert (outcome.items_seen, outcome.items_stored, outcome.items_skipped) == (3, 1, 2)
    stored = rows_in_db(repository)
    assert len(stored) == 1
    assert stored[0]["source_inventory_complete"] == 1
    cycle = repository.get_cycle(outcome.cycle_id)
    assert cycle.state == "completed"
    assert cycle.source_rows_reported == 3


def test_duplicate_mac_is_never_selected_and_unknown_status_is_counted(
    repository, observation_config, caplog
):
    provider = Provider([page([
        eligible("aa-bb-cc-dd-ee-01"),
        eligible("AA:BB:CC:DD:EE:01"),
        eligible("AA:BB:CC:DD:EE:02"),
        eligible("AA:BB:CC:DD:EE:03", authStatus=77),
    ], 4)])
    subject = worker(repository, observation_config, provider)

    with caplog.at_level(logging.INFO):
        outcome = subject.run_once()[0]

    assert outcome.duplicate_mac_count == 1
    assert outcome.unknown_auth_status_count == 1
    assert [row["client_mac"] for row in rows_in_db(repository)] == [
        "AA:BB:CC:DD:EE:02"
    ]
    assert "observation.client_duplicate_mac" in caplog.text
    assert "trafficDown" not in caplog.text


def test_partial_inventory_is_saved_with_false_marker(repository, observation_config):
    provider = Provider([
        page([eligible()], 2),
        Result.fail(
            error="HTTP_ERROR",
            message="failed",
            data={
                "failure_category": "timeout",
                "http_status": 0,
                "error_code": 0,
            },
        ),
    ])
    subject = worker(
        repository,
        observation_config,
        provider,
        client_page_size=1,
    )

    outcome = subject.run_once()[0]

    assert (outcome.result, outcome.complete) == ("partial", False)
    assert rows_in_db(repository)[0]["source_inventory_complete"] == 0
    cycle = repository.get_cycle(outcome.cycle_id)
    assert cycle.result == "partial"
    assert cycle.error_count == 1


def test_failed_first_page_creates_and_finalizes_failed_cycle(
    repository, observation_config
):
    provider = Provider([Result.fail(
        error="API_ERROR",
        message="secret body is ignored",
        data={"failure_category": "controller_error", "error_code": -1},
    )])
    subject = worker(repository, observation_config, provider)
    outcome = subject.run_once()[0]
    assert outcome.result == "failed"
    assert outcome.items_seen == 0
    assert rows_in_db(repository) == []
    assert repository.get_cycle(outcome.cycle_id).result == "failed"


def test_inconsistent_total_and_row_limit_are_partial(repository, observation_config):
    inconsistent = Provider([
        page([eligible()], 2),
        page([eligible("AA:BB:CC:DD:EE:02")], 3, page_number=2),
    ])
    first = worker(
        repository, observation_config, inconsistent, client_page_size=1
    ).run_once()[0]
    assert first.failure_category == "malformed_response"
    assert first.complete is False

    limited = Provider([page([eligible("AA:BB:CC:DD:EE:03")], 2)])
    second = worker(
        repository,
        observation_config,
        limited,
        client_page_size=1,
        client_max_rows=1,
    ).run_once()[0]
    assert second.failure_category == "row_limit"
    assert second.complete is False


def test_shutdown_during_pagination_preserves_partial_rows(
    repository, observation_config
):
    holder = {}

    def first_page():
        holder["worker"]._stop_event.set()
        return page([eligible()], 2)

    provider = Provider([first_page])
    subject = worker(
        repository, observation_config, provider, client_page_size=1
    )
    holder["worker"] = subject
    outcome = subject.run_once()[0]
    assert outcome.result == "shutdown"
    assert outcome.complete is False
    assert len(provider.calls) == 1
    assert rows_in_db(repository)[0]["source_inventory_complete"] == 0


def test_disabled_and_overlapping_run_make_zero_provider_calls(
    repository, observation_config
):
    provider = Provider([])
    disabled = ClientObservationWorker(
        provider=provider,
        repository=repository,
        config=replace(observation_config, enabled=False, client_enabled=True),
        logger=logging.getLogger("disabled-observation"),
    )
    assert disabled.start() is False
    assert disabled.run_once() == ()

    enabled = worker(repository, observation_config, provider)
    enabled._cycle_lock.acquire()
    try:
        assert enabled.run_once() == ()
    finally:
        enabled._cycle_lock.release()
    assert provider.calls == []


def test_initial_delay_is_interruptible_and_start_is_idempotent(
    repository, observation_config
):
    provider = Provider([])
    subject = worker(
        repository,
        observation_config,
        provider,
        client_initial_delay_seconds=60.0,
    )
    assert subject.start() is True
    assert subject.start() is False
    assert subject.stop(timeout=1.0) is True
    assert subject.running is False
    assert provider.calls == []


def test_next_successful_cycle_clears_degraded_state(
    repository, observation_config
):
    provider = Provider([
        Result.fail(
            error="HTTP_ERROR",
            data={"failure_category": "timeout"},
        ),
        page([], 0),
    ])
    subject = worker(repository, observation_config, provider)
    assert subject.run_once()[0].result == "failed"
    assert subject.degraded is True
    assert subject.run_once()[0].result == "success"
    assert subject.degraded is False
    assert subject.last_error is None


def test_storage_create_failure_is_fail_open_and_skips_network(
    observation_config, caplog
):
    class BrokenRepository:
        def create_cycle(self, **kwargs):
            raise sqlite3.OperationalError("database is full")

    provider = Provider([])
    config = replace(
        observation_config,
        client_enabled=True,
        site_ids=("site-a",),
    )
    subject = ClientObservationWorker(
        provider=provider,
        repository=BrokenRepository(),
        config=config,
        logger=logging.getLogger("broken-observation"),
    )
    with caplog.at_level(logging.INFO):
        outcome = subject.run_once()[0]
    assert outcome.failure_category == "storage_error"
    assert subject.degraded is True
    assert provider.calls == []
    assert "observation.storage_error" in caplog.text


def test_security_markers_absent_from_sqlite_telemetry_and_stdout(
    repository, observation_config, caplog, capsys
):
    markers = [
        "TEST_ACCESS_TOKEN_SHOULD_NOT_LEAK",
        "TEST_CLIENT_SECRET_SHOULD_NOT_LEAK",
        "TEST_WIFI_PASSWORD_SHOULD_NOT_LEAK",
    ]
    raw = eligible(password=markers[2], token=markers[0], clientSecret=markers[1])
    provider = Provider([page([raw], 1)])
    subject = worker(repository, observation_config, provider)
    with caplog.at_level(logging.INFO):
        subject.run_once()
    with repository.read_connection() as connection:
        dump = "\n".join(connection.iterdump())
    captured = capsys.readouterr()
    surfaces = dump + caplog.text + captured.out + captured.err
    for marker in markers:
        assert marker not in surfaces
