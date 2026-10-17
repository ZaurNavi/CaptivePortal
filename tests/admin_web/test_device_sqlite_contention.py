"""Disposable WAL fixtures exercise routes -> service -> real device gateway."""
from dataclasses import replace
import hashlib
import json
import logging
import sqlite3
import threading
import time
from types import SimpleNamespace

import pytest
from flask import Flask

from app.admin_web import device_gateway as gateway_module
from app.admin_web.device_gateway import AdminDeviceReadGateway, AdminDeviceSourceError
from app.admin_web.query_service import AdminQueryExecutionControls
from app.admin_web.routes import create_admin_web_blueprint
from app.analytics.source_gateway import QueryDeadline, AnalyticsQueryDeadlineExceeded
from .conftest import SITE_ID, login
from .test_device_gateway import _databases, _snapshot, _current_database
from .test_device_current_context import DEVICE_ID, MAC, _CurrentState, _Traffic
from .test_device_protocol_intelligence import Reader
from app.network_protocol_intelligence.read_service import DeviceProtocolIntelligenceReadService


@pytest.fixture
def device_http(admin_app, tmp_path):
    registry, visits = _databases(tmp_path)
    _snapshot(registry, device_id=DEVICE_ID, mac=MAC, site_id=SITE_ID,
              captured_at="2026-10-17T12:00:00.000Z")
    for path in (registry, visits):
        conn = sqlite3.connect(path)
        assert conn.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        conn.close()
    runtime = admin_app.extensions["admin_web_runtime"]
    runtime.config = replace(runtime.config, device_current_context_enabled=True,
                             device_protocol_intelligence_enabled=True, device_list_context_enabled=False)
    query = runtime.query_service
    query._config = runtime.config
    query._inventory_timezone_name = "UTC"
    query._devices = AdminDeviceReadGateway(registry, visits)
    query._reads = SimpleNamespace(list_visits=lambda **kwargs: ([], False),
                                   latest_client_observation=lambda **kwargs: None)
    query._current_state, query._current_guest_traffic = _CurrentState(), _Traffic()
    query._protocol_intelligence = DeviceProtocolIntelligenceReadService(Reader())
    query._execution_controls = AdminQueryExecutionControls(max_concurrent_queries=1, max_query_duration_seconds=1)
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(create_admin_web_blueprint(runtime, logger=logging.getLogger("device-contention-test")))
    client = app.test_client()
    login(client)
    return SimpleNamespace(client=client, runtime=runtime, registry=registry, visits=visits,
                           root=f"/admin/api/v1/sites/{SITE_ID}/devices", tmp_path=tmp_path)


class ExclusiveWALWindow:
    """Controlled exclusive-lock episode, NOT ordinary concurrent WAL DML."""
    def __init__(self, path, *, release_after=None, table="visitor_devices"):
        self.path, self.release_after = path, release_after
        self.table = table
        self.ready, self.attempt, self.release = threading.Event(), threading.Event(), threading.Event()
        self.errors = []

    def __enter__(self):
        def writer():
            conn = sqlite3.connect(self.path, isolation_level=None)
            try:
                assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
                conn.execute("PRAGMA locking_mode=EXCLUSIVE")
                conn.execute("BEGIN EXCLUSIVE")
                conn.execute(f"SELECT COUNT(*) FROM {self.table}").fetchone()
                self.ready.set()
                if not self.attempt.wait(3):
                    raise AssertionError("reader never attempted gateway")
                self.release.wait(self.release_after if self.release_after is not None else 3)
                conn.rollback()
            except BaseException as exc:
                self.errors.append(exc)
                self.ready.set()
            finally:
                conn.close()
        self.thread = threading.Thread(target=writer)
        self.thread.start()
        assert self.ready.wait(3)
        assert not self.errors
        return self

    def __exit__(self, *args):
        self.attempt.set()
        self.release.set()
        self.thread.join(4)
        assert not self.thread.is_alive()
        assert not self.errors


def request_in_window(case, monkeypatch, *, delay, suffix="/current", budget=1):
    gateway = case.runtime.query_service._devices
    original = gateway._open
    failures = []
    statements = []
    case.runtime.query_service._execution_controls._max_query_duration_seconds = budget
    with ExclusiveWALWindow(case.registry, release_after=delay) as window:
        def observed_open(deadline):
            window.attempt.set()
            try:
                return original(deadline)
            except AdminDeviceSourceError as exc:
                raw = exc.__context__
                failures.append({"type": type(raw).__name__, "message": str(raw),
                                 "code": getattr(raw, "sqlite_errorcode", None)})
                raise
        with monkeypatch.context() as scoped:
            scoped.setattr(gateway, "_open", observed_open)
            original_execute = gateway_module._DeviceQueryConnection.execute
            def timed_execute(connection, sql, parameters=()):
                started = time.monotonic()
                retries_before = connection._busy_retries_remaining
                try:
                    return original_execute(connection, sql, parameters)
                finally:
                    statements.append({"phase": "attach" if sql.startswith("ATTACH") else "query_or_metadata",
                                       "retries": retries_before - connection._busy_retries_remaining,
                                       "elapsed_ms": (time.monotonic() - started) * 1000})
            scoped.setattr(gateway_module._DeviceQueryConnection, "execute", timed_execute)
            start = time.monotonic()
            path = case.root + (f"/{DEVICE_ID}" + suffix if suffix not in ("", "/inventory-summary") else suffix)
            response = case.client.get(path, base_url="https://localhost")
            elapsed = time.monotonic() - start
            number = len(list(case.tmp_path.glob("request-timing-*.json")))
            (case.tmp_path / f"request-timing-{number}.json").write_text(json.dumps({
                "http_status": response.status_code, "elapsed_seconds": elapsed,
                "query_budget_seconds": budget, "statement_spans": statements}), encoding="utf-8")
    return response, elapsed, failures


def test_zero_wait_reproduces_busy_503_through_real_route(device_http, monkeypatch):
    monkeypatch.setattr(gateway_module, "_SQLITE_BUSY_WAIT_SECONDS", 0.0, raising=False)
    response, elapsed, failures = request_in_window(device_http, monkeypatch, delay=0.05)
    assert response.status_code == 503
    assert response.json["error"]["code"] == "source_unavailable"
    assert failures and "locked" in failures[0]["message"]
    (device_http.tmp_path / "baseline-busy.json").write_text(json.dumps({"status": 503, "elapsed": elapsed, "errors": failures}), encoding="utf-8")


def test_short_exclusive_wal_window_recovers_within_deadline(device_http, monkeypatch):
    response, elapsed, failures = request_in_window(device_http, monkeypatch, delay=0.03)
    assert response.status_code == 200, (response.json, failures)
    assert 0.02 <= elapsed < 0.5
    assert not failures


@pytest.mark.parametrize("suffix", ["", "/inventory-summary", "/detail", "/current", "/protocol-intelligence"])
def test_device_endpoints_short_lock_recover(device_http, monkeypatch, suffix):
    if suffix == "/detail":
        suffix = ""
        # Distinguish Device detail from collection route in the shared driver.
        device_http.root += f"/{DEVICE_ID}"
    response, elapsed, _ = request_in_window(device_http, monkeypatch, delay=0.025, suffix=suffix)
    assert response.status_code == 200, response.json
    assert elapsed < 0.5


@pytest.mark.parametrize("budget", [1.0, 0.02])
def test_long_lock_fails_bounded_and_private_diagnostic(device_http, monkeypatch, caplog, budget):
    caplog.set_level(logging.INFO, logger="device-contention-test")
    response, elapsed, _ = request_in_window(device_http, monkeypatch, delay=None, budget=budget)
    assert response.status_code == 503
    assert response.json["error"]["code"] in {"source_unavailable", "query_deadline"}
    assert elapsed < min(0.35, budget + 0.08)
    records = [r for r in caplog.records if getattr(r, "event", None) == "admin.device_query_unavailable"]
    assert len(records) == 1
    record = records[0]
    assert record.reason in {"sqlite_busy", "query_deadline"}
    assert record.operation == "current_context" and record.status_code == 503
    assert 0 <= record.duration_ms < 350
    for private in (MAC, DEVICE_ID, "database is locked", "registry.sqlite3", "SELECT", "Cookie", "Authorization"):
        assert private not in record.getMessage()
        assert private not in str({k: v for k, v in record.__dict__.items() if k in {
            "operation", "reason", "status_code", "duration_ms"}})
    assert set(response.json["error"]) == {"code", "message"}
    assert "sqlite_busy" not in response.get_data(as_text=True)
    (device_http.tmp_path / "bounded-lock.json").write_text(json.dumps({"budget_seconds": budget,
        "status": response.status_code, "elapsed": elapsed, "reason": record.reason}), encoding="utf-8")


def test_normal_wal_writer_does_not_cause_503(device_http, monkeypatch):
    monkeypatch.setattr(gateway_module, "_SQLITE_BUSY_WAIT_SECONDS", 0.0)
    conn = sqlite3.connect(device_http.registry, isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("UPDATE visitor_devices SET mac=mac")
        response = device_http.client.get(f"{device_http.root}/{DEVICE_ID}/current", base_url="https://localhost")
        assert response.status_code == 200
    finally:
        conn.rollback()
        conn.close()


def test_busy_wait_recomputed_for_each_statement_and_expiry_is_closed(device_http, monkeypatch):
    clock = [0.0]
    deadline = QueryDeadline(0.08, lambda: clock[0])
    conn = device_http.runtime.query_service._devices._open(deadline)
    try:
        conn.execute("SELECT 1")
        first = sqlite3.Connection.execute(conn, "PRAGMA busy_timeout").fetchone()[0]
        clock[0] = 0.07
        conn.execute("SELECT 1")
        second = sqlite3.Connection.execute(conn, "PRAGMA busy_timeout").fetchone()[0]
        assert first == second == 0  # Native waiting stays disabled, including on Windows.
        assert conn._busy_expires_at == 0.08
        sleeps, attempts = [], []
        original_execute = conn._execute_once
        def busy(sql, parameters):
            if sql == "SELECT 2":
                attempts.append(clock[0])
                raise sqlite3.OperationalError("database is locked")
            return original_execute(sql, parameters)
        def sleep(seconds):
            sleeps.append(seconds)
            clock[0] += seconds
        monkeypatch.setattr(conn, "_execute_once", busy)
        monkeypatch.setattr(gateway_module.time, "sleep", sleep)
        with pytest.raises(AnalyticsQueryDeadlineExceeded):
            conn.execute("SELECT 2")
        assert 0 < sum(sleeps) <= 0.010001  # No fresh 100 ms allowance for later statements.
        assert len(attempts) <= 3
        before = len(attempts)
        clock[0] = 0.081
        with pytest.raises(AnalyticsQueryDeadlineExceeded):
            conn.execute("SELECT 2")
        assert len(attempts) == before
    finally:
        conn.close()


@pytest.mark.parametrize("failure", ["schema", "identity", "missing"])
def test_invalid_sources_still_fail_closed_with_safe_diagnostics(device_http, failure, caplog):
    caplog.set_level(logging.INFO, logger="device-contention-test")
    if failure == "missing":
        device_http.registry.rename(device_http.tmp_path / "preserved-registry.sqlite3")
    else:
        with sqlite3.connect(device_http.registry) as conn:
            if failure == "schema":
                conn.execute("PRAGMA user_version=999")
            else:
                conn.execute("UPDATE visitor_devices SET mac='not-a-canonical-mac'")
        conn.close()
    response = device_http.client.get(f"{device_http.root}/{DEVICE_ID}/current", base_url="https://localhost")
    assert response.status_code == 503
    assert response.json["error"]["code"] == "source_unavailable"
    record = next(r for r in caplog.records if getattr(r, "event", None) == "admin.device_query_unavailable")
    assert record.reason == ("source_unavailable" if failure == "missing" else "integrity_failure")


def test_slot_exhaustion_is_429_not_hidden_by_sqlite_wait(device_http, caplog):
    caplog.set_level(logging.INFO, logger="device-contention-test")
    slots = device_http.runtime.query_service._execution_controls._slots
    assert slots.acquire(blocking=False)
    try:
        response = device_http.client.get(f"{device_http.root}/{DEVICE_ID}/current", base_url="https://localhost")
        assert response.status_code == 429
        assert response.headers["Retry-After"] == "1"
        assert response.json["error"]["code"] == "concurrency_limit"
        record = next(r for r in caplog.records if getattr(r, "event", None) == "admin.device_query_unavailable")
        assert record.reason == "concurrency_limit"
    finally:
        slots.release()


def test_read_only_source_bytes_unchanged_no_query_writes(device_http, monkeypatch):
    before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (device_http.registry, device_http.visits)}
    gateway = device_http.runtime.query_service._devices
    original, changes = gateway._open, []
    def checked(deadline):
        conn = original(deadline)
        assert conn.execute("PRAGMA query_only").fetchone()[0] == 1
        changes.append(conn.total_changes)
        return conn
    monkeypatch.setattr(gateway, "_open", checked)
    for _ in range(3):
        response = device_http.client.get(f"{device_http.root}/{DEVICE_ID}/current", base_url="https://localhost")
        assert response.status_code == 200
    assert changes == [0, 0, 0]
    assert before == {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (device_http.registry, device_http.visits)}


def test_same_fixture_before_after_latency_and_process_io(device_http, monkeypatch):
    def counters():
        try:
            from pathlib import Path
            return {k: int(v) for k, v in (line.split(":", 1) for line in Path("/proc/self/io").read_text().splitlines())}
        except OSError:
            return None
    observations = []
    source_before = hashlib.sha256(device_http.registry.read_bytes()).hexdigest()
    for wait in (0.0, 0.1):
        monkeypatch.setattr(gateway_module, "_SQLITE_BUSY_WAIT_SECONDS", wait)
        before = counters()
        response, elapsed, failures = request_in_window(device_http, monkeypatch, delay=0.04)
        after = counters()
        observations.append({"wait_cap_seconds": wait, "http_status": response.status_code,
                             "elapsed_seconds": elapsed, "errors": failures,
                             "process_io_delta": {k: after[k] - before[k] for k in before} if before and after else None})
    assert [r["http_status"] for r in observations] == [503, 200]
    assert 0.03 <= observations[1]["elapsed_seconds"] < 0.5
    uncontended = []
    for wait in (0.0, 0.1):
        monkeypatch.setattr(gateway_module, "_SQLITE_BUSY_WAIT_SECONDS", wait)
        before, started = counters(), time.monotonic()
        response = device_http.client.get(f"{device_http.root}/{DEVICE_ID}/current", base_url="https://localhost")
        elapsed, after = time.monotonic() - started, counters()
        assert response.status_code == 200
        uncontended.append({"wait_cap_seconds": wait, "elapsed_seconds": elapsed,
                            "process_io_delta": {k: after[k] - before[k] for k in before} if before and after else None})
    assert hashlib.sha256(device_http.registry.read_bytes()).hexdigest() == source_before
    (device_http.tmp_path / "before-after.json").write_text(json.dumps({"source_sha256": source_before,
        "scenario": "same synthetic WAL exclusive lock, release 40ms after gateway attempt",
        "observations": observations, "uncontended_success_controls": uncontended,
        "physical_io_claim": "NOT_MEASURED"}), encoding="utf-8")


@pytest.mark.parametrize("release_after,budget,success", [(0.025, 1.0, True), (None, 0.02, False)])
def test_context_third_attachment_uses_same_remaining_deadline(device_http, release_after, budget, success):
    current = _current_database(device_http.tmp_path)
    conn = sqlite3.connect(current)
    assert conn.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    conn.close()
    gateway = AdminDeviceReadGateway(device_http.registry, device_http.visits, current)
    with ExclusiveWALWindow(current, release_after=release_after, table="current_state_cycles") as window:
        deadline = QueryDeadline.after(budget)
        window.attempt.set()
        start = time.monotonic()
        if success:
            conn = gateway._open_context(deadline)
            conn.close()
        else:
            with pytest.raises((AdminDeviceSourceError, AnalyticsQueryDeadlineExceeded)):
                gateway._open_context(deadline)
        elapsed = time.monotonic() - start
        (device_http.tmp_path / "third-attachment.json").write_text(json.dumps({
            "release_after_seconds": release_after, "query_budget_seconds": budget,
            "outcome": "opened" if success else "refused", "elapsed_seconds": elapsed}), encoding="utf-8")
        assert elapsed < min(0.4, budget + 0.08)


def test_deadline_during_attachment_closes_connection(device_http, monkeypatch):
    clock, connections = [0.0], []
    class ExpiresAfterAttach(gateway_module._DeviceQueryConnection):
        def execute(self, sql, parameters=()):
            result = super().execute(sql, parameters)
            if sql.startswith("ATTACH"):
                clock[0] = 2.0
            return result
    original = sqlite3.connect
    def observed(*args, **kwargs):
        kwargs["factory"] = lambda *a, **kw: ExpiresAfterAttach(*a, deadline=deadline, **kw)
        conn = original(*args, **kwargs)
        connections.append(conn)
        return conn
    deadline = QueryDeadline(1.0, lambda: clock[0])
    monkeypatch.setattr(gateway_module.sqlite3, "connect", observed)
    with pytest.raises(AnalyticsQueryDeadlineExceeded):
        device_http.runtime.query_service._devices._open(deadline)
    assert len(connections) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        sqlite3.Connection.execute(connections[0], "SELECT 1")


@pytest.mark.parametrize("code,message,retry", [
    (5, "synthetic busy", True), (6, "synthetic locked", True),
    (261, "extended busy", True), (11, "database is locked", False),
    (None, "database is locked", True), (None, "database table is locked", True),
    (None, "database table is locked: fixture", True),
    (None, "syntax error near database is locked", False),
])
def test_retry_unit_only_confirmed_busy_and_finite_even_with_static_clock(monkeypatch, code, message, retry):
    deadline = QueryDeadline(1.0, lambda: 0.0)
    conn = gateway_module._DeviceQueryConnection(":memory:", deadline=deadline)
    attempts, sleeps = [], []
    error = sqlite3.OperationalError(message)
    if code is not None:
        error.sqlite_errorcode = code
    def fail(sql, parameters):
        attempts.append(sql)
        raise error
    monkeypatch.setattr(conn, "_execute_once", fail)
    monkeypatch.setattr(gateway_module.time, "sleep", sleeps.append)
    try:
        assert sqlite3.Connection.execute(conn, "PRAGMA busy_timeout").fetchone()[0] == 0
        with pytest.raises(sqlite3.OperationalError) as caught:
            conn.execute("SELECT 1")
        assert caught.value is error
        assert len(attempts) == (21 if retry else 1)
        assert len(sleeps) == (20 if retry else 0)
        assert all(0 < seconds <= 0.005 for seconds in sleeps)
        assert conn.total_changes == 0
    finally:
        conn.close()


def test_retry_unit_count_is_shared_across_statements(monkeypatch):
    conn = gateway_module._DeviceQueryConnection(":memory:", deadline=QueryDeadline(1.0, lambda: 0.0))
    attempts, sleeps = {"SELECT 1": 0, "SELECT 2": 0}, []
    once = conn._execute_once
    def execute(sql, parameters):
        attempts[sql] += 1
        if sql == "SELECT 1" and attempts[sql] == 3:
            return once(sql, parameters)
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(conn, "_execute_once", execute)
    monkeypatch.setattr(gateway_module.time, "sleep", sleeps.append)
    try:
        assert conn.execute("SELECT 1").fetchone() == (1,)
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("SELECT 2")
        assert attempts == {"SELECT 1": 3, "SELECT 2": 19}
        assert len(sleeps) == 20
    finally:
        conn.close()


def test_retry_unit_late_success_closes_cursor_instead_of_returning_it(monkeypatch):
    clock, cursors = [0.0], []
    conn = gateway_module._DeviceQueryConnection(":memory:", deadline=QueryDeadline(0.02, lambda: clock[0]))
    once = conn._execute_once
    def late(sql, parameters):
        cursor = once(sql, parameters)
        cursors.append(cursor)
        clock[0] = 0.03
        return cursor
    monkeypatch.setattr(conn, "_execute_once", late)
    try:
        with pytest.raises(AnalyticsQueryDeadlineExceeded):
            conn.execute("SELECT 1")
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            cursors[0].fetchone()
    finally:
        conn.close()


@pytest.mark.parametrize("release_after,success", [(0.025, True), (None, False)])
def test_retry_unit_attachment_aliases_and_failure_connection_cleanup(device_http, monkeypatch, release_after, success):
    gateway = device_http.runtime.query_service._devices
    connections, attempts = [], []
    connect, execute_once = sqlite3.connect, gateway_module._DeviceQueryConnection._execute_once
    def tracked_connect(*args, **kwargs):
        conn = connect(*args, **kwargs)
        connections.append(conn)
        return conn
    def tracked_execute(conn, sql, parameters):
        if sql.startswith("ATTACH"):
            attempts.append(sql)
        return execute_once(conn, sql, parameters)
    monkeypatch.setattr(gateway_module.sqlite3, "connect", tracked_connect)
    monkeypatch.setattr(gateway_module._DeviceQueryConnection, "_execute_once", tracked_execute)
    with ExclusiveWALWindow(device_http.registry, release_after=release_after) as window:
        window.attempt.set()
        if success:
            conn = gateway._open(QueryDeadline.after(1.0))
            try:
                aliases = [row[1] for row in conn.execute("PRAGMA database_list")]
                assert aliases.count("registry_db") == aliases.count("visit_db") == 1
                assert conn.total_changes == 0
            finally:
                conn.close()
        else:
            with pytest.raises(AdminDeviceSourceError):
                gateway._open(QueryDeadline.after(1.0))
        # The writer is connections[0]; the only gateway connection must be closed.
        assert len(connections) == 2
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            sqlite3.Connection.execute(connections[1], "SELECT 1")
        assert 2 <= len(attempts) <= (22 if success else 21)
