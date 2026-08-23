from __future__ import annotations

import threading
import time
from dataclasses import replace

import pytest

from app.current_state.ap_worker import CurrentApWorker
from app.current_state.client_worker import CurrentClientWorker
from app.current_state.repository import CurrentStateRepository
from app.current_state.telemetry import CurrentStateTelemetry
from app.models import Result

from .conftest import SITE


class Telemetry:
    def __init__(self):
        self.events = []

    def safe_emit_system(self, event, **fields):
        self.events.append((event, fields))
        return True


class Logger:
    def log(self, *args, **kwargs):
        pass


class Provider:
    def __init__(self, *, clients=None, aps=None):
        self.clients = clients or {}
        self.aps = aps or {}
        self.client_calls = []
        self.ap_calls = []

    def list_observation_clients(self, site_id, page, page_size, timeout):
        self.client_calls.append((site_id, page, page_size, timeout))
        value = self.clients.get(page)
        if isinstance(value, Exception):
            raise value
        return value

    def list_observation_access_points(self, site_id, page, page_size, timeout):
        self.ap_calls.append((site_id, page, page_size, timeout))
        value = self.aps.get(page)
        if isinstance(value, Exception):
            raise value
        return value


def client(mac, **updates):
    row = {"mac": mac, "wireless": True, "active": True, "ssid": "Zefer_Parki", "authStatus": 2}
    row.update(updates)
    return row


def page(key, rows, total, number=1):
    return Result.ok(data={key: rows, "total_rows": total, "page": number, "page_size": 2, "http_status": 200, "error_code": 0})


def failed(category="timeout"):
    return Result.fail("FAILED", data={"failure_category": category, "http_status": 503, "error_code": 0})


@pytest.fixture
def repo(config):
    repository = CurrentStateRepository(config)
    repository.initialize()
    return repository


def worker_telemetry():
    raw = Telemetry()
    return raw, CurrentStateTelemetry(raw, Logger())


def test_telemetry_drops_raw_identity_and_secret_fields():
    raw, telemetry = worker_telemetry()
    assert telemetry.emit(
        "current_state.client_cycle_failed",
        site_id=SITE,
        client_mac="AA:BB:CC:DD:EE:FF",
        raw_payload={"secret": "value"},
        token="secret",
    )
    fields = raw.events[-1][1]
    assert fields["site_id"] == SITE
    assert "client_mac" not in fields
    assert "raw_payload" not in fields
    assert "token" not in fields


def test_client_one_page_complete_includes_all_auth_states(config, repo):
    raw, telemetry = worker_telemetry()
    provider = Provider(clients={1: page("clients", [client("AA:BB:CC:DD:EE:01", authStatus=1), client("AA:BB:CC:DD:EE:02", authStatus=9)], 2)})
    worker = CurrentClientWorker(provider=provider, repository=repo, config=replace(config, client_page_size=2), telemetry=telemetry)
    outcome = worker.run_once()[0]
    assert outcome.result == "success" and outcome.items_stored == 2
    with repo.read_connection() as connection:
        assert {row[0] for row in connection.execute("SELECT auth_classification FROM current_client_state")} == {"pending", "other"}
    assert provider.client_calls == [(SITE, 1, 2, 5.0)]
    assert raw.events[-1][0] == "current_state.client_cycle_completed"


def test_client_multi_page_complete(config, repo):
    provider = Provider(clients={
        1: page("clients", [client("AA:BB:CC:DD:EE:01"), client("AA:BB:CC:DD:EE:02")], 3, 1),
        2: page("clients", [client("AA:BB:CC:DD:EE:03")], 3, 2),
    })
    _, telemetry = worker_telemetry()
    outcome = CurrentClientWorker(provider=provider, repository=repo, config=replace(config, client_page_size=2), telemetry=telemetry).run_once()[0]
    assert outcome.complete and outcome.page_count == 2 and outcome.items_stored == 3


@pytest.mark.parametrize(
    "pages,category",
    [
        ({1: page("clients", [client("AA:BB:CC:DD:EE:01"), client("AA:BB:CC:DD:EE:02")], 3, 1), 2: page("clients", [client("AA:BB:CC:DD:EE:03")], 4, 2)}, "malformed_response"),
        ({1: page("clients", [client("AA:BB:CC:DD:EE:01")], 3, 1)}, "inconsistent_total"),
        ({1: failed("timeout")}, "timeout"),
        ({1: RuntimeError("network")}, "network_error"),
    ],
)
def test_client_inventory_failures_are_bounded(config, repo, pages, category):
    _, telemetry = worker_telemetry()
    outcome = CurrentClientWorker(provider=Provider(clients=pages), repository=repo, config=replace(config, client_page_size=2), telemetry=telemetry).run_once()[0]
    assert outcome.complete is False
    assert outcome.failure_category == category


def test_returned_page_mismatch_is_partial(config, repo):
    provider = Provider(clients={
        1: page("clients", [client("AA:BB:CC:DD:EE:01"), client("AA:BB:CC:DD:EE:02")], 3, 2),
    })
    _, telemetry = worker_telemetry()
    outcome = CurrentClientWorker(
        provider=provider,
        repository=repo,
        config=replace(config, client_page_size=2),
        telemetry=telemetry,
    ).run_once()[0]
    assert outcome.complete is False
    assert outcome.failure_category == "malformed_response"


def test_shutdown_between_pages_publishes_shutdown_attempt(config, repo):
    _, telemetry = worker_telemetry()

    class StoppingProvider(Provider):
        worker = None

        def list_observation_clients(self, site_id, page_number, page_size, timeout):
            result = super().list_observation_clients(site_id, page_number, page_size, timeout)
            self.worker.stop_event.set()
            return result

    provider = StoppingProvider(clients={
        1: page("clients", [client("AA:BB:CC:DD:EE:01"), client("AA:BB:CC:DD:EE:02")], 3, 1),
    })
    worker = CurrentClientWorker(
        provider=provider,
        repository=repo,
        config=replace(config, client_page_size=2),
        telemetry=telemetry,
    )
    provider.worker = worker
    outcome = worker.run_once()[0]
    assert outcome.result == "shutdown"
    assert outcome.items_stored == 2
    assert repo.get_cycle(outcome.cycle_id).complete is False


def test_client_page_and_row_limits(config, repo):
    _, telemetry = worker_telemetry()
    provider = Provider(clients={1: page("clients", [client("AA:BB:CC:DD:EE:01"), client("AA:BB:CC:DD:EE:02")], 3, 1)})
    outcome = CurrentClientWorker(provider=provider, repository=repo, config=replace(config, client_page_size=2, client_max_pages=1), telemetry=telemetry).run_once()[0]
    assert outcome.failure_category == "page_limit"
    provider = Provider(clients={1: page("clients", [client("AA:BB:CC:DD:EE:03"), client("AA:BB:CC:DD:EE:04")], 3, 1)})
    outcome = CurrentClientWorker(provider=provider, repository=repo, config=replace(config, client_page_size=2, client_max_rows=1), telemetry=telemetry).run_once()[0]
    assert outcome.failure_category == "row_limit"


def test_zero_client_inventory_is_complete(config, repo):
    _, telemetry = worker_telemetry()
    outcome = CurrentClientWorker(provider=Provider(clients={1: page("clients", [], 0)}), repository=repo, config=config, telemetry=telemetry).run_once()[0]
    assert outcome.result == "success" and outcome.items_stored == 0


def test_duplicate_and_invalid_relevant_clients_make_partial(config, repo):
    rows = [client("AA:BB:CC:DD:EE:01"), client("AA-BB-CC-DD-EE-01"), client("invalid")]
    _, telemetry = worker_telemetry()
    outcome = CurrentClientWorker(provider=Provider(clients={1: page("clients", rows, 3)}), repository=repo, config=config, telemetry=telemetry).run_once()[0]
    assert outcome.result == "partial" and outcome.items_stored == 0
    stored = repo.get_cycle(outcome.cycle_id)
    assert stored.duplicate_identity_count == 1
    assert stored.unidentified_count == 1


def test_client_shutdown_before_request(config, repo):
    provider = Provider()
    _, telemetry = worker_telemetry()
    worker = CurrentClientWorker(provider=provider, repository=repo, config=config, telemetry=telemetry)
    worker.stop_event.set()
    assert worker.run_once() == ()
    assert provider.client_calls == []


def test_ap_complete_filters_non_ap_and_keeps_unknown_status(config, repo):
    rows = [
        {"type": "switch", "mac": "AA:BB:CC:DD:EE:01"},
        {"type": "ap", "mac": "11:22:33:44:55:66", "status": 1},
        {"type": "ap", "mac": "22:33:44:55:66:77"},
    ]
    raw, telemetry = worker_telemetry()
    outcome = CurrentApWorker(provider=Provider(aps={1: page("access_points", rows, 3)}), repository=repo, config=config, telemetry=telemetry).run_once()[0]
    assert outcome.result == "success" and outcome.items_stored == 2
    with repo.read_connection() as connection:
        states = {row[0] for row in connection.execute("SELECT status_classification FROM current_ap_state")}
    assert states == {"online", "unknown"}
    assert raw.events[-1][0] == "current_state.ap_cycle_completed"


def test_ap_duplicate_identity_makes_partial(config, repo):
    rows = [{"type": "ap", "mac": "11:22:33:44:55:66"}, {"type": "ap", "mac": "11-22-33-44-55-66"}]
    _, telemetry = worker_telemetry()
    outcome = CurrentApWorker(provider=Provider(aps={1: page("access_points", rows, 2)}), repository=repo, config=config, telemetry=telemetry).run_once()[0]
    assert outcome.result == "partial" and outcome.items_stored == 0


def test_ap_zero_inventory_is_complete(config, repo):
    _, telemetry = worker_telemetry()
    outcome = CurrentApWorker(provider=Provider(aps={1: page("access_points", [], 0)}), repository=repo, config=config, telemetry=telemetry).run_once()[0]
    assert outcome.complete and outcome.items_stored == 0


def test_non_overlapping_run_once(config, repo):
    _, telemetry = worker_telemetry()
    worker = CurrentClientWorker(provider=Provider(), repository=repo, config=config, telemetry=telemetry)
    assert worker._cycle_lock.acquire(blocking=False)
    try:
        assert worker.run_once() == ()
    finally:
        worker._cycle_lock.release()


def test_background_schedule_is_fixed_delay_not_overlap(config, repo):
    call_finished = []

    class TimedProvider(Provider):
        def list_observation_clients(self, *args):
            time.sleep(0.03)
            call_finished.append(time.monotonic())
            return page("clients", [], 0)

    _, telemetry = worker_telemetry()
    worker = CurrentClientWorker(
        provider=TimedProvider(),
        repository=repo,
        config=replace(
            config,
            client_initial_delay_seconds=0,
            client_interval_seconds=0.04,
        ),
        telemetry=telemetry,
    )
    assert worker.start()
    time.sleep(0.13)
    assert worker.stop(1.0)
    assert len(call_finished) == 2
    assert call_finished[1] - call_finished[0] >= 0.04
