import builtins
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from app.admin_web import operations_service as ops
from app.admin_web.operations_inventory import SERVICES, STORES
from tests.admin_web.test_operations_inventory import resolved

NOW = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)


def properties(unit, **overrides):
    return dict(Id=unit, LoadState="loaded", ActiveState="active", SubState="running", MainPID="123",
                NRestarts="0", ExecMainStartTimestamp="Sun 2026-10-18 11:00:00 UTC", UnitFileState="enabled", **{}) | overrides


def systemd_text(**overrides):
    return "\n\n".join("\n".join(f"{k}={v}" for k, v in properties(s.unit, **overrides).items()) for s in SERVICES) + "\n"


def missing(_path):
    raise FileNotFoundError()


def regular(path):
    return SimpleNamespace(st_mode=stat.S_IFREG | 0o640, st_size=0 if path.endswith("-wal") else 64,
                           st_ino=sum((i + 1) * ord(c) for i, c in enumerate(path)), st_dev=1)


def service(**kwargs):
    return ops.AdminOperationsReadService(resolved(), acquire=lambda cancel: systemd_text(), now=lambda: NOW,
                                         lstat=missing, **kwargs)


@pytest.mark.parametrize("intent,changes,state,reason", [
    ("run", {}, "running", None),
    ("run", {"ActiveState": "failed", "SubState": "failed", "MainPID": "0"}, "failed", "unit_failed"),
    ("run", {"ActiveState": "inactive", "SubState": "dead", "MainPID": "0"}, "stopped", "expected_stopped"),
    ("run", {"LoadState": "not-found", "ActiveState": "inactive", "SubState": "dead", "MainPID": "0"}, "failed", "unit_unavailable"),
    ("disabled", {}, "degraded", "unexpected_running"),
    ("maintenance", {}, "degraded", "unexpected_running"),
    ("disabled", {"ActiveState": "inactive", "SubState": "dead", "MainPID": "0"}, "disabled", "configured_disabled"),
    ("maintenance", {"ActiveState": "inactive", "SubState": "dead", "MainPID": "0"}, "disabled", "configured_disabled"),
    ("unknown", {}, "unknown", "intent_unknown"),
    ("run", {"MainPID": "-1"}, "unknown", "probe_unavailable"),
    ("run", {"MainPID": "0"}, "unknown", "probe_unavailable"),
    ("run", {"NRestarts": "nope"}, "unknown", "probe_unavailable"),
    ("run", {"SubState": "SYNTHETIC_RAW_CANARY"}, "unknown", "probe_unavailable"),
    ("run", {"ExecMainStartTimestamp": "not a date"}, "unknown", "probe_unavailable"),
    ("run", {"ExecMainStartTimestamp": "Sun 2026-10-18 13:00:00 UTC"}, "unknown", "probe_unavailable"),
])
def test_service_state_and_application_health_not_inferred(intent, changes, state, reason):
    row = ops.service_row(SERVICES[0], intent, properties(SERVICES[0].unit, **changes), NOW)
    assert row["operational_state"] == state and row["reason_code"] == reason
    assert row["application_health"] == "unknown"
    assert row["unit"] == "captive-portal.service"
    if row["main_pid"] is not None:
        assert row["main_pid"] == 123 and row["uptime_seconds"] == 3600
    assert "SYNTHETIC_RAW_CANARY" not in json.dumps(row)


@pytest.mark.parametrize("mode", ["missing-id", "duplicate-id", "missing-property", "duplicate-property", "extra-unit"])
def test_systemd_249_record_isolation(mode):
    text = systemd_text()
    if mode == "missing-id": text = text.replace("Id=captive-portal.service\n", "", 1)
    if mode == "duplicate-id": text += "\n" + text.split("\n\n")[0]
    if mode == "missing-property": text = text.replace("MainPID=123\n", "", 1)
    if mode == "duplicate-property": text = text.replace("MainPID=123", "MainPID=123\nMainPID=9", 1)
    if mode == "extra-unit": text += "\nId=unregistered.service\nLoadState=loaded\n"
    records = ops.parse_systemd(text)
    assert all(s.unit in records for s in SERVICES[1:])
    assert (SERVICES[0].unit in records) is (mode == "extra-unit")
    assert "unregistered.service" not in records


@pytest.mark.parametrize("case", ["valid", "timeout", "stdout-overflow", "stderr-overflow", "bad-exit"])
def test_real_bounded_pipe_acquisition_fixed_argv_and_reaping(monkeypatch, case):
    # Real systemd exists only in POSIX deployment; Windows exercises fail-closed
    # native admission, while identical captured parsing/state tests run there.
    if os.name != "posix":
        with pytest.raises(ops.OperationsError): ops.acquire_systemd()
        return
    actual = subprocess.Popen
    processes = []
    code = {
        "valid": "print('Id=captive-portal.service')",
        "timeout": "import time; time.sleep(5)",
        "stdout-overflow": "import sys; sys.stdout.write('x'*20000); sys.stdout.flush()",
        "stderr-overflow": "import sys; sys.stderr.write('x'*2000); sys.stderr.flush()",
        "bad-exit": "raise SystemExit(3)",
    }[case]
    def spawn(argv, **kwargs):
        assert argv == ops.SYSTEMD_ARGV
        assert len(argv) == 13 and argv[-9:] == tuple(s.unit for s in SERVICES)
        assert kwargs["shell"] is False
        assert kwargs["env"] == ops.SYSTEMD_ENV
        assert "HTTP_PROXY" not in kwargs["env"] and "DBUS_SESSION_BUS_ADDRESS" not in kwargs["env"]
        process = actual([sys.executable, "-c", code], **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr(ops.subprocess, "Popen", spawn)
    started = time.monotonic()
    if case == "valid": assert ops.acquire_systemd() == "Id=captive-portal.service\n"
    else:
        with pytest.raises(ops.OperationsError): ops.acquire_systemd()
    assert time.monotonic() - started < 2
    assert len(processes) == 1 and processes[0].poll() is not None
    assert processes[0].stdout.closed and processes[0].stderr.closed


def sampled(lstat, intent="expected", monotonic=lambda: 0):
    return ops.store_row(STORES[0], intent, "/safe/main.db", NOW, lstat, deadline=1,
        monotonic=monotonic, cancel=threading.Event())[0]


@pytest.mark.parametrize("intent,state", [("expected", "present_unverified"), ("optional_disabled", "disabled"), ("unknown", "unknown")])
def test_present_file_is_never_verified_health(intent, state):
    row = sampled(regular, intent)
    assert row["operational_state"] == state and row["file_presence"] == "present"
    assert (row["main_file_bytes"], row["wal_bytes"], row["shm_bytes"], row["total_footprint_bytes"]) == (64, 0, 64, 128)
    assert row["schema_observed_version"] is None and row["schema_expected_version"] is None
    assert row["health_evidence"] == "none" and row["health_checked_at_utc"] is None


@pytest.mark.parametrize("intent,state", [("expected", "unavailable"), ("optional_disabled", "not_provisioned"), ("unknown", "unknown")])
def test_proven_absence_zero_footprint(intent, state):
    row = sampled(missing, intent)
    assert row["operational_state"] == state and row["file_presence"] == "absent"
    assert row["total_footprint_bytes"] == 0


@pytest.mark.parametrize("kind", ["symlink", "dangling", "directory", "denied", "bad-size", "orphan", "sidecar-denied", "disappeared"])
def test_unsafe_and_racing_file_components(kind):
    def probe(path):
        main = path == "/safe/main.db"
        if (kind in {"orphan", "disappeared"} and main) or (kind == "disappeared" and path.endswith("-shm")):
            raise FileNotFoundError()
        if kind == "denied" or (kind == "sidecar-denied" and path.endswith("-wal")):
            raise PermissionError("SYNTHETIC_PRIVATE_PATH")
        metadata = regular(path)
        if main and kind in {"symlink", "dangling"}: metadata.st_mode = stat.S_IFLNK
        if main and kind == "directory": metadata.st_mode = stat.S_IFDIR
        if main and kind == "bad-size": metadata.st_size = -1
        return metadata
    row = sampled(probe)
    if kind in {"symlink", "dangling", "directory"}: assert row["operational_state"] == "unavailable"
    if kind in {"denied", "bad-size"}: assert row["operational_state"] == "unknown"
    if kind in {"orphan", "disappeared"}: assert row["reason_code"] == "orphan_sidecar_possible"
    if kind in {"symlink", "dangling", "directory", "denied", "bad-size", "sidecar-denied"}: assert row["total_footprint_bytes"] is None
    assert "SYNTHETIC_PRIVATE_PATH" not in json.dumps(row)


def test_budget_stops_remaining_stats_and_unknown_total():
    clock = [0]
    calls = []
    def probe(path):
        calls.append(path)
        clock[0] = 2
        return regular(path)
    row = sampled(probe, monotonic=lambda: clock[0])
    assert calls == ["/safe/main.db"]
    assert row["reason_code"] == "sample_timeout" and row["total_footprint_bytes"] is None


def test_full_snapshot_exact_shapes_no_sqlite_open_or_file_content_read(monkeypatch):
    reads, acquisitions = [], []
    def blocked(*args, **kwargs): raise AssertionError("content/SQLite open forbidden")
    def probe(path): reads.append(path); return regular(path)
    subject = ops.AdminOperationsReadService(resolved(), acquire=lambda cancel: acquisitions.append(1) or systemd_text(),
        lstat=probe, now=lambda: NOW)
    with monkeypatch.context() as scoped:
        scoped.setattr(sqlite3, "connect", blocked)
        scoped.setattr(builtins, "open", blocked)
        model = subject.read("synthetic-request")
    subject.close()
    assert len(reads) == len(set(reads)) == 51 and acquisitions == [1]
    assert len(model["services"]) == 9 and len(model["databases"]) == 17
    assert model["summary"]["databases"]["available"] == 0
    assert model["summary"]["databases"]["present_unverified"] == 17
    assert model["summary"]["services"]["running"] == 9
    assert model["summary"]["storage"]["known_footprint_bytes"] == 17 * 128
    assert model["summary"]["problems"] == {"established": 0, "unknown_or_stale": 0}
    assert model["snapshot_state"] == "complete"
    assert set(model) == {"api_version", "request_id", "scope", "snapshot_state", "generated_at_utc", "sampling_started_at_utc",
        "sampling_completed_at_utc", "freshness_seconds", "sample_status", "summary", "services", "databases", "topology", "partial_failures"}
    assert len(model["topology"]["nodes"]) == 31 and len(model["topology"]["edges"]) == 45
    assert len(json.dumps(model).encode()) < 48000
    assert "/opt/" not in json.dumps(model) and "/var/lib/" not in json.dumps(model)


def test_duplicate_inode_not_double_counted_and_storage_is_partial():
    bound = resolved()
    collision = {bound.paths[STORES[0].id], bound.paths[STORES[1].id]}
    def probe(path):
        row = regular(path)
        if path in collision: row.st_ino = 777
        return row
    subject = ops.AdminOperationsReadService(bound, acquire=lambda c: systemd_text(), lstat=probe, now=lambda: NOW)
    model = subject.read("test")
    subject.close()
    assert all(r["operational_state"] == "unknown" and r["total_footprint_bytes"] is None for r in model["databases"][:2])
    assert model["summary"]["storage"]["known_footprint_bytes"] == 15 * 128
    assert model["summary"]["storage"]["total_complete"] is False
    assert model["snapshot_state"] == "partial"


def test_subprocess_failure_retains_independent_db_evidence():
    def fail(_cancel): raise OSError("SYNTHETIC_PRIVATE_STDERR")
    subject = ops.AdminOperationsReadService(resolved(), acquire=fail, lstat=regular, now=lambda: NOW)
    model = subject.read("test")
    subject.close()
    assert len(model["partial_failures"]) == 9
    assert model["summary"]["databases"]["present_unverified"] == 17
    assert model["snapshot_state"] == "partial"
    assert "SYNTHETIC_PRIVATE_STDERR" not in json.dumps(model)


def test_cache_coalesces_twenty_callers_ttl_and_stale_projection():
    clock, calls = [0.0], []
    def acquire(_cancel): calls.append(1); return systemd_text()
    subject = ops.AdminOperationsReadService(resolved(), acquire=acquire, lstat=regular, now=lambda: NOW, monotonic=lambda: clock[0])
    with ThreadPoolExecutor(max_workers=20) as pool:
        models = list(pool.map(lambda i: subject.read(str(i)), range(20)))
    assert calls == [1] and len({m["request_id"] for m in models}) == 20
    clock[0] = 29.99
    assert subject.read("manual")["freshness_seconds"] == 29.99 and calls == [1]
    # Keep refresh blocked, while the existing snapshot ages past the limit.
    entered, release = threading.Event(), threading.Event()
    def held(cancel): entered.set(); release.wait(2); return systemd_text()
    subject._acquire = held
    clock[0] = 30
    subject.read("refresh")
    assert entered.wait(1)
    clock[0] = 91
    stale = subject.read("old")
    assert stale["sample_status"] == "stale" and stale["summary"]["services"]["running"] == 0
    assert all(r["operational_state"] == "stale" for r in stale["services"] + stale["databases"])
    # Mutating a response cannot poison the actual cache.
    stale["services"][0]["unit"] = "bad"
    assert subject.read("copy")["services"][0]["unit"] == "captive-portal.service"
    started = time.monotonic()
    subject.close()
    assert time.monotonic() - started < .1
    release.set()


def test_first_wait_hung_job_no_replacement_and_close_nonblocking():
    entered, release, calls = threading.Event(), threading.Event(), []
    clock = [0]
    def held(cancel): calls.append(1); entered.set(); release.wait(3); return systemd_text()
    subject = ops.AdminOperationsReadService(resolved(), acquire=held, lstat=regular, now=lambda: NOW, monotonic=lambda: clock[0])
    started = time.monotonic()
    with pytest.raises(ops.OperationsError, match="snapshot_pending"): subject.read("first")
    assert entered.is_set() and time.monotonic() - started < .4
    clock[0] = 1000
    with pytest.raises(ops.OperationsError): subject.read("second")
    assert calls == [1]
    subject.close()
    release.set()
    with pytest.raises(ops.OperationsError): subject.read("closed")


def test_failed_sample_throttled_no_queued_jobs_and_cap():
    clock, calls = [0], []
    def fail(cancel): calls.append(1); raise OSError()
    def denied(path): raise PermissionError()
    subject = ops.AdminOperationsReadService(resolved(), acquire=fail, lstat=denied, now=lambda: NOW, monotonic=lambda: clock[0])
    for _ in range(3):
        with pytest.raises(ops.OperationsError, match="operations_unavailable"): subject.read("test")
    assert calls == [1]
    clock[0] = 30
    with pytest.raises(ops.OperationsError): subject.read("test")
    assert calls == [1, 1]
    subject.close()


def test_summary_denominator_disabled_files_zero_and_established_dedup():
    services = [dict(operational_state="degraded", expected_mode="disabled"),
                dict(operational_state="stopped", expected_mode="run"), dict(operational_state="unknown", expected_mode="run")]
    databases = [dict(operational_state="disabled", total_footprint_bytes=10), dict(operational_state="not_provisioned", total_footprint_bytes=0),
                 dict(operational_state="unknown", total_footprint_bytes=None)]
    summary = ops.summarize(services, databases)
    assert summary["services"]["expected_running"] == 2 and summary["services"]["running"] == 0
    assert summary["problems"] == {"established": 2, "unknown_or_stale": 2}
    assert summary["storage"] == {"known_footprint_bytes": 10, "total_complete": False, "unknown_store_count": 1, "coverage": "partial"}


def test_operations_source_contains_no_sql_discovery_or_mutation():
    for name in ("operations_inventory.py", "operations_service.py"):
        source = (Path(ops.__file__).parent / name).read_text(encoding="utf-8")
        for forbidden in ("sqlite3.connect", "PRAGMA", "quick_check", "integrity_check", "systemctl start", "systemctl stop", "systemctl restart", "shell=True", "glob(", "list-units"):
            assert forbidden not in source


def test_slow_failure_retry_is_throttled_from_completion_not_start():
    clock, calls = [0], []
    def fail(cancel): calls.append(1); clock[0] += 10; raise OSError()
    def denied(path): raise PermissionError()
    subject = ops.AdminOperationsReadService(resolved(), acquire=fail, lstat=denied, now=lambda: NOW, monotonic=lambda: clock[0])
    with pytest.raises(ops.OperationsError): subject.read("first")
    assert calls == [1]
    clock[0] = 39
    with pytest.raises(ops.OperationsError): subject.read("too soon")
    assert calls == [1]
    clock[0] = 40
    with pytest.raises(ops.OperationsError): subject.read("next")
    assert calls == [1, 1]
    subject.close()


def test_component_path_alias_sampled_only_once_and_not_double_counted():
    from tests.admin_web.test_operations_inventory import manifest
    from app.admin_web.operations_inventory import parse_inventory
    value = manifest()
    value["databases"][0]["path"] = "/opt/CaptivePortal/data/alias.db"
    value["databases"][1]["path"] = "/opt/CaptivePortal/data/alias.db-wal"
    paths = []
    def probe(path): paths.append(path); return regular(path)
    subject = ops.AdminOperationsReadService(parse_inventory(json.dumps(value).encode()), acquire=lambda c: systemd_text(),
                                            lstat=probe, now=lambda: NOW)
    model = subject.read("aliases")
    subject.close()
    assert len(paths) == len(set(paths)) == 50
    assert all(r["total_footprint_bytes"] is None for r in model["databases"][:2])


def test_oversize_read_model_cannot_be_reported_as_success():
    subject = service()
    subject.read("first")
    with subject._condition:
        subject._cache[0]["services"][0]["label"] = "SYNTHETIC" * 7000
    with pytest.raises(ops.OperationsError): subject.read("oversize")
    subject.close()
