"""Disposable focused F01–F30 fixtures, never the original Evidence DB."""
import copy
import errno
import hashlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import stat
import subprocess
import sys
import time
import uuid

import pytest

from app.device_fingerprint import audit_cli, audit_runner as audit
from app.device_fingerprint.models import (
    DeviceFingerprintConflict, DeviceFingerprintMigrationRequired,
    DeviceFingerprintStorageCorrupt, DeviceFingerprintStorageUnavailable,
)
from app.device_fingerprint.repository import DeviceFingerprintRepository, writer_lock
from app.device_fingerprint.schema import SCHEMA_SQL
from tests.device_fingerprint import NOW, config, evidence_event, health_event, producer
from app.device_fingerprint.service import DeviceFingerprintService
from app.device_fingerprint.schema_registry import EvidenceSchemaRegistry
from tests.device_fingerprint.test_repository import provision


def facts(**changes):
    return dict(mem_total=16*audit.GIB, mem_available=12*audit.GIB, cgroup_headroom=12*audit.GIB,
        address_headroom=None, containment=True, swap_active=False, swap_counters=dict(pswpin=0,pswpout=0),
        reclaim_counters=dict(pgscan_direct=0,pgsteal_direct=0),
        peak_rss_bytes=128*1024**2, memory_psi=None, io_psi=None) | changes


def setup(tmp_path, rows=1, page_size=4096):
    path = tmp_path / "fingerprint.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute(f"PRAGMA page_size={page_size}")
    connection.executescript(SCHEMA_SQL)
    connection.execute("INSERT INTO device_fingerprint_storage_state VALUES (1,?,0)", (str(uuid.uuid4()),))
    connection.commit()
    connection.close()
    cfg = config(tmp_path)
    repo = DeviceFingerprintRepository(cfg.db_path, max_db_bytes=cfg.max_db_bytes)
    repo.initialize()
    registry = EvidenceSchemaRegistry()
    registry.register("dhcp", 1, lambda value: dict(value))
    registry.freeze()
    svc = DeviceFingerprintService(cfg, repo, registry, now=lambda:NOW)
    for i in range(rows):
        event = evidence_event(source_event_id=f"{i+1:08d}-1111-4111-8111-111111111111")
        svc.evidence_batch(producer(), dict(producer_id=producer().producer_id, events=[event]))
    svc.source_health_batch(producer(), dict(producer_id=producer().producer_id, events=[health_event()]))
    return cfg, repo, svc


def auditor(tmp_path, source=None, **changes):
    directory = tmp_path / "audit"
    directory.mkdir(mode=0o700, exist_ok=True)
    return audit.EvidenceAuditor(source or tmp_path / "fingerprint.sqlite3",
        status=audit.StatusStore(directory / "fingerprint_evidence.json"), resources=facts, **changes)


def record_evidence(tmp_path, value):
    (tmp_path / "fixture-evidence.json").write_text(json.dumps(value, indent=2), encoding="utf-8")


def windows_sharing_denial(error, windows):
    code = getattr(error, "winerror", None)
    return windows and (code in {5, 32, 33} or code is None and error.errno in {errno.EACCES, errno.EPERM})


def read_after_child_exit(store, *, windows=None, clock=time.monotonic, sleep=time.sleep):
    """Test observation only: never retry the audit or a production write."""
    windows = sys.platform == "win32" if windows is None else windows
    deadline = clock() + 1.0
    while True:
        try:
            return store.read()
        except PermissionError as exc:
            if not windows_sharing_denial(exc, windows) or clock() >= deadline:
                raise
            sleep(.02)


@pytest.mark.parametrize("rows", [0, 500])
def test_F01_F02_fast_start_trace_and_authorizer_never_read_history(tmp_path, monkeypatch, rows):
    cfg, old, _svc = setup(tmp_path, rows)
    old.close()
    real, traces = sqlite3.connect, []
    def connect(*args, **kwargs):
        connection = real(*args, **kwargs)
        connection.set_trace_callback(traces.append)
        def authorize(action, name, _arg, *_other):
            if action == sqlite3.SQLITE_READ and name in {"device_fingerprint_evidence", "device_fingerprint_source_health_events"}:
                return sqlite3.SQLITE_DENY
            if action == sqlite3.SQLITE_PRAGMA and name.lower() in {"quick_check", "integrity_check"}:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        connection.set_authorizer(authorize)
        return connection
    monkeypatch.setattr(sqlite3, "connect", connect)
    repo = DeviceFingerprintRepository(cfg.db_path, max_db_bytes=cfg.max_db_bytes)
    repo.initialize(); repo.close()
    assert not any(any(token in sql.lower() for token in ("quick_check", "integrity_check", "count(*)", " join ", "min(", "max(")) for sql in traces)
    record_evidence(tmp_path, dict(rows=rows, trace=traces, timing="SMALL_FIXTURE_NON_CAUSAL"))


@pytest.mark.parametrize("kind", ["missing", "vanished", "empty", "version0", "partial", "wrong-column", "index", "generation", "allocator", "singleton", "v1", "unsafe-parent", "symlink"])
def test_F03_F04_existing_store_only_no_bootstrap_or_connection(tmp_path, monkeypatch, kind):
    cfg = config(tmp_path)
    path = Path(cfg.db_path)
    if kind not in {"missing", "unsafe-parent"}:
        provision(path)
        if kind == "vanished": path.unlink()
        elif kind == "empty": path.write_bytes(b"")
        elif kind == "symlink":
            real_lstat = Path.lstat
            monkeypatch.setattr(Path, "lstat", lambda self: type("M", (), dict(st_mode=stat.S_IFLNK))() if self == path else real_lstat(self))
        else:
            changes = {"version0":"PRAGMA user_version=0", "partial":"DROP TABLE device_fingerprint_evidence",
                "wrong-column":"ALTER TABLE device_fingerprint_evidence ADD COLUMN bad TEXT", "index":"DROP INDEX idx_df_evidence_retention",
                "generation":"UPDATE device_fingerprint_storage_state SET database_generation_id='11111111-1111-1111-1111-111111111111'",
                "allocator":"UPDATE device_fingerprint_storage_state SET last_ingest_sequence=-1", "singleton":"DELETE FROM device_fingerprint_storage_state",
                "v1":"PRAGMA user_version=1"}
            with sqlite3.connect(path) as connection:
                connection.execute("PRAGMA ignore_check_constraints=ON")
                connection.execute(changes[kind])
    if kind == "unsafe-parent": path = tmp_path / "absent-parent/db.sqlite3"
    before = path.read_bytes() if path.exists() and kind != "symlink" else None
    repo = DeviceFingerprintRepository(str(path), max_db_bytes=cfg.max_db_bytes)
    error = DeviceFingerprintStorageUnavailable if kind in {"missing", "vanished", "unsafe-parent", "symlink"} else DeviceFingerprintMigrationRequired if kind == "v1" else DeviceFingerprintStorageCorrupt
    with pytest.raises(error): repo.initialize()
    assert repo._connection is None
    if before is None and kind != "symlink": assert not path.exists()
    elif kind != "symlink": assert path.read_bytes() == before


def test_F04_vanish_between_check_and_sqlite_open_does_not_create(tmp_path, monkeypatch):
    path = tmp_path / "fingerprint.sqlite3"; provision(path)
    real = sqlite3.connect
    def vanished(target, **kwargs):
        assert target.endswith("?mode=rw") and kwargs["uri"] is True
        path.unlink()
        return real(target, **kwargs)
    monkeypatch.setattr(sqlite3, "connect", vanished)
    repo = DeviceFingerprintRepository(str(path), max_db_bytes=64*1024**2)
    with pytest.raises(DeviceFingerprintStorageUnavailable): repo.initialize()
    assert not path.exists() and repo._connection is None


@pytest.mark.parametrize("page_size", [1024,4096,8192])
def test_F10_F11_F12_full_ram_backup_page_size_committed_wal_and_no_source_writes(tmp_path, page_size):
    cfg, repo, _svc = setup(tmp_path, 3, page_size)
    before = Path(cfg.db_path).read_bytes()
    wal_before = Path(cfg.db_path+"-wal").read_bytes()
    opened, closed, trace = [], [], []
    class Connection(sqlite3.Connection):
        def close(self): closed.append(self); super().close()
    def connect(name, **kwargs):
        opened.append(name)
        connection = sqlite3.connect(name, factory=Connection, **kwargs)
        connection.set_trace_callback(lambda sql: trace.append((name, sql)))
        return connection
    subject = auditor(tmp_path, connect=connect)
    result, code = subject.run()
    assert code == 0 and result["status"] == "passed", result
    assert opened == [Path(cfg.db_path).as_uri()+"?mode=ro", ":memory:"] and len(closed) == 2
    assert result["source_page_size"] == page_size
    assert result["snapshot_last_ingest_sequence"] == 4
    assert result["backup_progress_summary"]["completed"] is True
    assert result["check_summary"]["foreign_keys"] == "not_applicable"
    assert result["logical_snapshot_bytes"] > 0
    assert Path(cfg.db_path).read_bytes() == before
    assert Path(cfg.db_path+"-wal").read_bytes() == wal_before
    source_sql = [sql.lower() for name,sql in trace if name != ":memory:"]
    assert not any(any(token in sql for token in ("begin", "integrity_check", "quick_check", "insert", "update", "delete", "checkpoint", "journal_mode")) for sql in source_sql)
    assert {path.name for path in tmp_path.glob("*.sqlite3")} == {"fingerprint.sqlite3"}
    assert len(list((tmp_path / "audit").iterdir())) == 2
    record_evidence(tmp_path, result)
    repo.close()


@pytest.mark.parametrize("changes", [dict(mem_available=1), dict(containment=False), dict(cgroup_headroom=1),
    dict(address_headroom=1), dict(swap_active=True), dict(mem_total=True), dict(mem_available=-1),
    dict(peak_rss_bytes=True), dict(containment=None), dict(mem_total=2**63)])
def test_F14_F16_memory_refusal_before_destination_created(tmp_path, changes):
    _cfg, repo, _svc = setup(tmp_path)
    subject = auditor(tmp_path)
    subject.resources = lambda: facts(**changes)
    opened = []
    def connect(name, **kwargs): opened.append(name); return sqlite3.connect(name, **kwargs)
    subject.connect = connect
    record, code = subject.run()
    assert code == 3 and record["status"] == "incomplete" and record["category_code"] == "resource_deferred"
    assert ":memory:" not in opened
    repo.close()


@pytest.mark.parametrize("kind", ["canceled", "deadline", "memory-drop", "swap", "reclaim", "busy", "ioerr", "partial", "allocation", "wrong-page-size"])
def test_F11_F15_F17_F26_interrupted_or_partial_backup_never_passes(tmp_path, kind):
    _cfg, repo, _svc = setup(tmp_path, 4)
    closed, calls, clock = [], [], [0]
    class Connection(sqlite3.Connection):
        def close(self): closed.append(1); super().close()
        def backup(self, target, **kwargs):
            assert kwargs["pages"] == 256 and kwargs["sleep"] == .05
            if kind == "partial": kwargs["progress"](0, 1, 20); return
            if kind == "allocation": raise MemoryError()
            if kind == "ioerr": raise sqlite3.OperationalError("SYNTHETIC_PRIVATE_IOERR")
            if kind == "busy": kwargs["progress"](5, 1, 20); return
            if kind == "wrong-page-size": return super().backup(target, **kwargs)
            clock[0] = 7201 if kind == "deadline" else 1
            kwargs["progress"](0, 1, 20)
        def execute(self, sql, *args):
            if kind == "wrong-page-size" and sql.startswith("PRAGMA page_size="): return super().execute("PRAGMA page_size=8192")
            return super().execute(sql, *args)
    def resources():
        calls.append(1)
        if kind == "reclaim" and len(calls)>2: return facts(reclaim_counters=dict(pgscan_direct=1,pgsteal_direct=0))
        return facts(mem_available=1) if kind == "memory-drop" and len(calls)>2 else facts(swap_counters=dict(pswpin=1, pswpout=0)) if kind == "swap" and len(calls)>2 else facts()
    subject = auditor(tmp_path, connect=lambda *args, **kwargs: sqlite3.connect(*args, factory=Connection, **kwargs), monotonic=lambda:clock[0], canceled=lambda:kind == "canceled" and clock[0]>0)
    subject.resources = resources
    result, code = subject.run()
    assert code != 0 and result["status"] == "incomplete", result
    assert subject.store.read()["last_verified_success"] is None
    assert len(closed) == 2
    assert "SYNTHETIC_PRIVATE" not in json.dumps(result)
    repo.close()


def corrupt_index(path, kind):
    table, index = "device_fingerprint_evidence", "uq_df_evidence_ingest_sequence"
    with sqlite3.connect(path) as connection:
        if kind == "N08":
            connection.execute(f"DROP INDEX {index}")
            connection.execute(f"UPDATE {table} SET ingest_sequence=1")
            connection.execute(f"CREATE INDEX {index} ON {table}(ingest_sequence)")
            connection.execute("PRAGMA writable_schema=ON")
            connection.execute("UPDATE sqlite_master SET sql=replace(sql,'CREATE INDEX','CREATE UNIQUE INDEX') WHERE name=?", (index,))
            return
        connection.execute("PRAGMA ignore_check_constraints=ON")
        connection.execute(f"UPDATE {table} SET ingest_sequence=1.5")
        page = connection.execute("SELECT rootpage FROM sqlite_master WHERE name=?", (index,)).fetchone()[0]
        size = connection.execute("PRAGMA page_size").fetchone()[0]
    raw = bytearray(path.read_bytes()); offset = (page-1)*size
    assert raw[offset] == 10
    empty = bytearray(size); empty[0] = 10; empty[5:7] = size.to_bytes(2,"big")
    raw[offset:offset+size] = empty
    path.write_bytes(raw)  # Disposable fixture ONLY, never production repair.


@pytest.mark.parametrize("kind", ["N08", "N11"])
def test_F07_F19_real_corrupt_index_passes_fast_gate_but_ram_t3_rejects(tmp_path, kind):
    cfg, old, _svc = setup(tmp_path, 2 if kind == "N08" else 1); old.close()
    path = Path(cfg.db_path); corrupt_index(path, kind)
    raw_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    repo = DeviceFingerprintRepository(str(path), max_db_bytes=cfg.max_db_bytes)
    repo.initialize(); repo.close()  # Intentionally weaker historical admission.
    result, code = auditor(tmp_path).run()
    assert code != 0 and result["status"] == "failed" and result["category_code"] == "integrity_suspect", result
    assert hashlib.sha256(path.read_bytes()).hexdigest() == raw_hash
    record_evidence(tmp_path, dict(kind=kind, fast="operational_metadata_only", audit=result))


@pytest.mark.parametrize("mutation", [
    "UPDATE device_fingerprint_evidence SET ingest_sequence=99",
    "UPDATE device_fingerprint_source_health_events SET ingest_sequence=1",
    "UPDATE device_fingerprint_evidence SET payload_sha256=printf('%064d',0)",
    "UPDATE device_fingerprint_source_health_events SET content_sha256=printf('%064d',0)",
    "UPDATE device_fingerprint_evidence SET evidence_id='zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz'",
])
def test_F18_F20_domains_reject_without_logging_payload(tmp_path, mutation):
    _cfg, repo, _svc = setup(tmp_path)
    repo.connection.execute(mutation)
    result, code = auditor(tmp_path).run()
    assert code != 0 and result["status"] == "failed", result
    assert result["category_code"] == "integrity_suspect"
    assert "vendor_class" not in json.dumps(result) and "aa:bb" not in json.dumps(result)
    repo.close()


def test_F13_F20_F22_concurrent_commit_and_retention_gap_snapshot_watermark(tmp_path):
    cfg, repo, svc = setup(tmp_path, 1500)
    repo.connection.execute("DELETE FROM device_fingerprint_evidence WHERE ingest_sequence=2")
    committed = []
    class Connection(sqlite3.Connection):
        def backup(self, target, **kwargs):
            original = kwargs["progress"]
            def progress(code, remaining, total):
                original(code, remaining, total)
                if not committed and remaining > 0:
                    svc.evidence_batch(producer(), dict(producer_id=producer().producer_id, events=[evidence_event(source_event_id=str(uuid.uuid4()))]))
                    committed.append(True)
            super().backup(target, **(kwargs | dict(progress=progress)))
    result, code = auditor(tmp_path, connect=lambda *args, **kwargs: sqlite3.connect(*args, factory=Connection, **kwargs)).run()
    assert code == 0 and committed and result["snapshot_last_ingest_sequence"] in {1501,1502}, result
    assert result["backup_progress_summary"]["steps"] > 1
    frozen = result["snapshot_last_ingest_sequence"]
    svc.evidence_batch(producer(), dict(producer_id=producer().producer_id, events=[evidence_event(source_event_id=str(uuid.uuid4()))]))
    assert repo.read_ingest_watermark(repo.connection)["max_committed_ingest_sequence"] == 1503
    assert result["snapshot_last_ingest_sequence"] == frozen
    record_evidence(tmp_path, result)
    repo.close()


def test_F09_F21_F26_singleton_writer_lock_independence_and_old_success(tmp_path):
    cfg, repo, _svc = setup(tmp_path)
    subject = auditor(tmp_path)
    with writer_lock(cfg.writer_lock_path):
        first, code = subject.run()
        assert code == 0
        with writer_lock(str(subject.store.path.with_suffix(".audit.lock"))):
            second, code = subject.run()
            assert code == 2 and second["category_code"] == "already_running"
    for _ in range(3):
        subject.canceled = lambda:True
        result, code = subject.run()
        assert code != 0 and result["status"] == "incomplete"
        assert subject.store.read()["last_verified_success"] == first
    repo.close()


@pytest.mark.parametrize("stage", ["preflight", "backup", "integrity", "complete"])
def test_F23_real_process_termination_releases_lock_reconciles_attempt(tmp_path, stage):
    _cfg, repo, _svc = setup(tmp_path); repo.close()
    subject = auditor(tmp_path)
    code = r'''
import sys,time,json,faulthandler
faulthandler.dump_traceback_later(5)
from pathlib import Path
from app.device_fingerprint.audit_runner import EvidenceAuditor,StatusStore
def facts(): return json.loads(sys.argv[4])
Path(sys.argv[5]).write_text("child_imports_complete",encoding="ascii")
class Store(StatusStore):
 def write(self,value):
  super().write(value)
  if value["last_attempt"].get("stage")==sys.argv[3]:
   print("BLOCKED_AT_STAGE",flush=True)
   time.sleep(30)
EvidenceAuditor(Path(sys.argv[1]),status=Store(Path(sys.argv[2])),resources=facts).run()
'''
    ready = tmp_path/"child-ready.txt"
    child = subprocess.Popen([sys.executable,"-c",code,str(subject.source),str(subject.store.path),stage,json.dumps(facts()),str(ready)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        # Separate cold native Python/UNC import preparation from the actual
        # eight-second stage-reach assertion. No audit deadline is extended.
        startup_deadline = time.monotonic()+30
        while not ready.exists() and child.poll() is None and time.monotonic()<startup_deadline:
            time.sleep(.02)
        assert ready.exists(), "child interpreter did not initialize"
        deadline = time.monotonic()+8
        while time.monotonic()<deadline:
            try:
                attempt = subject.store.read()["last_attempt"]
                if attempt.get("stage") == stage: break
            except (FileNotFoundError, audit.AuditStop): pass
            except PermissionError as exc:
                if not windows_sharing_denial(exc, sys.platform == "win32"): raise
            time.sleep(.02)
        else:
            child.terminate()
            out, err = child.communicate(timeout=5)
            pytest.fail("child did not reach requested stage: " + out + err)
        child.terminate(); child.communicate(timeout=5)
        assert child.poll() is not None
        before = read_after_child_exit(subject.store)
        assert before["last_attempt"]["status"] == ("passed" if stage == "complete" else "running")
        result, code = subject.run()
        assert code == 0 and result["status"] == "passed"
        assert result["run_id"] != before["last_attempt"]["run_id"]
        if stage != "complete": assert result["previous_attempt_recovery"]["category_code"] == "previous_owner_interrupted"
    finally:
        if child.poll() is None: child.kill(); child.communicate(timeout=5)


def test_F21_atomic_publication_fault_keeps_prior_success_and_no_temp_leak(tmp_path, monkeypatch):
    _cfg, repo, _svc = setup(tmp_path)
    subject = auditor(tmp_path)
    result, code = subject.run(); assert code == 0
    old = subject.store.path.read_bytes()
    monkeypatch.setattr(audit.os, "replace", lambda *args: (_ for _ in ()).throw(OSError("PRIVATE_PATH_CANARY")))
    failed, code = subject.run()
    assert code == 5 and failed["category_code"] == "report_unavailable"
    assert subject.store.path.read_bytes() == old
    assert not list(subject.store.path.parent.glob("*.tmp"))
    repo.close()


def test_F21_open_reader_allows_atomic_update_or_bounded_fail_closed_refusal(tmp_path):
    subject = auditor(tmp_path)
    before = subject.store.read()
    subject.store.write(before)
    descriptor = audit._status_read_descriptor(subject.store.path)
    try:
        newer = copy.deepcopy(before)
        newer["last_attempt"]["reader_canary"] = "new revision"
        started = time.monotonic()
        try:
            subject.store.write(newer)
            assert subject.store.read() == newer
        except PermissionError:
            assert os.name == "nt" and time.monotonic()-started < .5
            assert subject.store.read() == before
        assert json.loads(os.read(descriptor, audit.REPORT_MAX)) == before
    finally: os.close(descriptor)
    subject.store.write(newer)
    assert subject.store.read() == newer


def test_F03_F06_corrupt_header_and_capacity_fail_without_published_connection(tmp_path):
    from app.device_fingerprint.models import DeviceFingerprintStorageLimit
    path = tmp_path/"fingerprint.sqlite3"
    path.write_bytes(b"not a SQLite database"*100)
    repo = DeviceFingerprintRepository(str(path), max_db_bytes=64*1024**2)
    with pytest.raises(DeviceFingerprintStorageCorrupt): repo.initialize()
    assert repo._connection is None
    path.unlink(); provision(path)
    repo = DeviceFingerprintRepository(str(path), max_db_bytes=1)
    with pytest.raises(DeviceFingerprintStorageLimit): repo.initialize()
    assert repo._connection is None


def test_F04_failed_initialize_cannot_publish_ready_or_accept_ingest(tmp_path):
    from types import SimpleNamespace
    from app.device_fingerprint.service import DeviceFingerprintRuntime
    cfg = config(tmp_path)
    repo = DeviceFingerprintRepository(cfg.db_path,max_db_bytes=cfg.max_db_bytes)
    runtime = DeviceFingerprintRuntime(cfg,repo,None,artifact_identity=None,telemetry=SimpleNamespace(emit=lambda *args,**kwargs:None))
    with pytest.raises(DeviceFingerprintStorageUnavailable): runtime.initialize()
    assert runtime.state == "initializing" and not runtime.accepting_writes
    assert not runtime.begin_ingest() and repo._connection is None


def test_F05_real_commit_global_allocator_replay_and_conflict_rollback(tmp_path):
    cfg, repo, svc = setup(tmp_path)
    watermark = repo.read_ingest_watermark(repo.connection)
    assert watermark["max_committed_ingest_sequence"] == 2
    health = dict(producer_id=producer().producer_id,events=[health_event()])
    assert svc.source_health_batch(producer(),health).duplicate_noop == 1
    with pytest.raises(DeviceFingerprintConflict):
        svc.evidence_batch(producer(),dict(producer_id=producer().producer_id,events=[evidence_event(source_event_id=str(uuid.uuid4())), evidence_event(source_event_id="00000001-1111-4111-8111-111111111111",payload={"vendor_class":"different"})]))
    assert repo.read_ingest_watermark(repo.connection) == watermark
    repo.close()
    with sqlite3.connect(cfg.db_path) as reader:
        assert reader.execute("SELECT last_ingest_sequence FROM device_fingerprint_storage_state").fetchone()[0] == 2
        assert reader.execute("SELECT COUNT(*) FROM device_fingerprint_evidence").fetchone()[0] == 1
        assert reader.execute("SELECT COUNT(*) FROM device_fingerprint_source_health_events").fetchone()[0] == 1


def test_F21_F25_no_disk_snapshot_even_with_unusable_scratch(tmp_path, monkeypatch):
    _cfg, repo, _svc = setup(tmp_path)
    monkeypatch.setenv("SQLITE_TMPDIR", str(tmp_path/"nonexistent-scratch"))
    subject = auditor(tmp_path)
    assert subject.store.read()["last_attempt"] == {"status":"never_run"}
    result, code = subject.run()
    assert code == 0 and result["status"] == "passed"
    assert not (tmp_path/"nonexistent-scratch").exists()
    assert sorted(path.name for path in tmp_path.iterdir()) == ["audit","fingerprint.sqlite3","fingerprint.sqlite3-shm","fingerprint.sqlite3-wal"]
    repo.close()


def test_F26_F27_cleanup_fault_prevents_success_and_status_writes_are_milestone_only(tmp_path):
    _cfg, repo, _svc = setup(tmp_path)
    subject = auditor(tmp_path)
    stages = []
    original = subject.store.write
    def publish(value): stages.append(value["last_attempt"]["stage"]); original(value)
    subject.store.write = publish
    class Connection(sqlite3.Connection):
        def close(self): super().close(); raise OSError("SYNTHETIC_PRIVATE_CLEANUP")
    subject.connect = lambda *args, **kwargs: sqlite3.connect(*args, factory=Connection, **kwargs)
    result, code = subject.run()
    assert code != 0 and result["status"] == "incomplete" and result["cleanup_error"] is True
    assert subject.store.read()["last_verified_success"] is None
    assert stages == ["preflight","backup","integrity","domain","complete"]
    assert "SYNTHETIC_PRIVATE_CLEANUP" not in json.dumps(result)
    repo.close()


@pytest.mark.parametrize("argv", [["run","--store-id","network_metadata"],["run","--store-id","fingerprint_evidence","--db-path","/arbitrary"],["run","--store-id","fingerprint_evidence","--sql","SELECT 1"]])
def test_F08_cli_rejects_arbitrary_targets_without_configuration_read(argv, monkeypatch):
    monkeypatch.setattr(audit_cli, "EvidenceAuditor", lambda *args, **kwargs: pytest.fail("must not construct auditor"))
    with pytest.raises(SystemExit) as error: audit_cli.main(argv)
    assert error.value.code == 2


def test_F08_F16_F27_real_unsupported_probes_fail_closed_and_report_is_bounded(monkeypatch):
    monkeypatch.setattr(audit.os, "name", "nt")
    with pytest.raises(audit.AuditStop, match="resource_deferred"): audit.resource_facts()


@pytest.mark.parametrize("mode", ["two-ok", "error-row", "no-rows", "fk-violation"])
def test_F18_integrity_requires_exact_complete_ok_and_declared_fk_validation(tmp_path, mode):
    _cfg, repo, _svc = setup(tmp_path)
    class Proxy:
        def execute(self, sql, *args):
            if sql == "PRAGMA integrity_check":
                return iter([("ok",),("ok",)] if mode == "two-ok" else [("SYNTHETIC_ERROR",)] if mode == "error-row" else [] if mode == "no-rows" else [("ok",)])
            if mode == "fk-violation" and sql.startswith("PRAGMA foreign_key_list"): return iter([(0,)])
            if sql == "PRAGMA foreign_key_check": return iter([("SYNTHETIC_VIOLATION",)])
            return repo.connection.execute(sql, *args)
    with pytest.raises(audit.AuditStop, match="integrity_suspect"):
        audit.validate_snapshot(Proxy(), lambda:None)
    repo.close()


@pytest.mark.parametrize("kind", ["missing", "nonregular", "hardlink", "unsafe-source", "unsafe-wal"])
def test_F08_F10_source_admission_precedes_sqlite_connect(tmp_path, monkeypatch, kind):
    path = tmp_path/"fingerprint.sqlite3"
    if kind == "nonregular": path.mkdir()
    elif kind != "missing": provision(path)
    real = Path.lstat
    if kind in {"hardlink", "unsafe-source", "unsafe-wal"}:
        if kind == "unsafe-wal": Path(str(path)+"-wal").write_bytes(b"synthetic")
        def lstat(self):
            original = real(self)
            if self == path and kind == "hardlink":
                class Metadata:
                    def __getattr__(self, key): return getattr(original,key)
                    st_nlink = 2
                return Metadata()
            if self == Path(str(path)+"-wal") and kind == "unsafe-wal":
                class Metadata:
                    def __getattr__(self,key): return getattr(original,key)
                    st_mode = stat.S_IFLNK|0o777
                return Metadata()
            if self == path and kind == "unsafe-source" and os.name == "posix":
                class Metadata:
                    def __getattr__(self,key): return getattr(original,key)
                    st_mode = stat.S_IFREG|0o666
                return Metadata()
            return original
        monkeypatch.setattr(Path,"lstat",lstat)
    if kind == "unsafe-source" and os.name != "posix":
        # Native Windows ACL verification is not an admitted real runtime;
        # use unsupported real resource admission, not a fabricated Unix mode.
        subject = auditor(tmp_path)
        subject.resources = lambda: (_ for _ in ()).throw(audit.AuditStop("resource_deferred"))
    else:
        subject = auditor(tmp_path, connect=lambda *_args, **_kwargs: pytest.fail("must refuse before SQLite open"))
    result, code = subject.run()
    assert code != 0 and result["status"] == "incomplete", result


@pytest.mark.parametrize("raw", [b"[]", b"{}", b'{"audit_contract_version":NaN}', b'{"last_attempt":{},"last_attempt":{}}', b"x"*32769], ids=["array","empty","nan","duplicate","oversize"])
def test_F21_F27_untrusted_status_refuses_and_does_not_promote_success(tmp_path, raw):
    subject = auditor(tmp_path)
    subject.store.path.write_bytes(raw)
    if os.name == "posix": subject.store.path.chmod(0o600)
    result, code = subject.run()
    assert code == 5 and result["category_code"] == "report_unavailable"


def test_F08_manual_cli_stopped_configuration_and_cooperative_signal(tmp_path, monkeypatch, capsys):
    from types import SimpleNamespace
    monkeypatch.setitem(sys.modules,"app.settings",SimpleNamespace(get_settings=lambda:{"device_fingerprint_evidence_enabled":"false","device_fingerprint_db_path":str(tmp_path/"fingerprint.sqlite3")}))
    from app.artifact_identity import LoadedArtifactIdentity
    monkeypatch.setattr(audit_cli,"capture_loaded_artifact_identity",lambda _name: LoadedArtifactIdentity(
        "a"*40, "b"*40, "fingerprint-evidence-manual-audit", "2026-10-18T00:00:00.000Z"))
    def construct(source, **kwargs):
        assert source == str(tmp_path/"fingerprint.sqlite3")
        def run():
            assert not kwargs["canceled"]()
            signal.getsignal(signal.SIGTERM)(signal.SIGTERM,None)
            assert kwargs["canceled"]()
            return dict(status="incomplete",category_code="canceled"),4
        return SimpleNamespace(run=run)
    monkeypatch.setattr(audit_cli,"EvidenceAuditor",construct)
    assert audit_cli.main(["run","--store-id","fingerprint_evidence"]) == 4
    text = capsys.readouterr().out
    assert "canceled" in text and str(tmp_path) not in text


def test_F28_F29_F30_scope_and_no_automatic_audit_import():
    root = Path(__file__).resolve().parents[2]
    for name in ("cli.py", "service.py", "repository.py"):
        assert "audit_runner" not in (root/"app/device_fingerprint"/name).read_text(encoding="utf-8")
    source = (root/"app/device_fingerprint/audit_runner.py").read_text(encoding="utf-8")
    for forbidden in ("VACUUM INTO", "shutil.copy", "iterdump", "wal_checkpoint", "ATTACH DATABASE"):
        assert forbidden not in source
    assert audit.BACKUP_PAGES == 256 and audit.BACKUP_SLEEP == .05 and audit.RUN_SECONDS == 7200


@pytest.mark.parametrize("mode", ["transient", "persistent", "other-error", "posix"])
def test_R2_C_child_exit_observer_retries_only_bounded_windows_sharing(mode):
    from types import SimpleNamespace
    calls, sleeps, clock = [], [], [0.0]
    expected = {"last_attempt": {"status": "passed"}}
    def read():
        calls.append(1)
        if mode == "transient" and len(calls) == 3: return expected
        raise PermissionError(errno.EIO if mode == "other-error" else errno.EACCES, "synthetic reader refusal")
    def sleep(seconds): sleeps.append(seconds); clock[0] += seconds
    store = SimpleNamespace(read=read)
    if mode == "transient":
        assert read_after_child_exit(store, windows=True, clock=lambda:clock[0], sleep=sleep) == expected
        assert len(calls) == 3 and sleeps == [.02, .02]
    else:
        with pytest.raises(PermissionError):
            read_after_child_exit(store, windows=mode != "posix", clock=lambda:clock[0], sleep=sleep)
        if mode == "persistent":
            assert 1 <= clock[0] < 1.03 and len(calls) <= 52
        else:
            assert len(calls) == 1 and sleeps == []


@pytest.mark.parametrize("status", ["", " M changed-audit.py\n", "?? untracked-audit.py\n"])
def test_R2_D_cli_trusts_only_verified_clean_head_tree_without_filesystem_mutation(monkeypatch, capsys, status):
    from types import SimpleNamespace
    import app.artifact_identity as artifact
    calls, constructed = [], []
    def git(_root, *arguments):
        calls.append(arguments)
        return {("rev-parse", "--verify", "HEAD"):"a"*40,
            ("rev-parse", "--verify", "HEAD^{tree}"):"b"*40,
            ("status", "--porcelain=v1", "--untracked-files=normal"):status}[arguments]
    monkeypatch.setattr(artifact, "_git", git)
    def settings():
        assert not status, "dirty identity must refuse before configuration or DB access"
        return {"device_fingerprint_evidence_enabled":"false", "device_fingerprint_db_path":"/synthetic-unused.sqlite3"}
    monkeypatch.setitem(sys.modules, "app.settings", SimpleNamespace(get_settings=settings))
    def construct(_source, **kwargs):
        constructed.append(kwargs)
        return SimpleNamespace(run=lambda:(dict(status="passed", category_code="snapshot_passed"), 0))
    monkeypatch.setattr(audit_cli, "EvidenceAuditor", construct)
    code = audit_cli.main(["run", "--store-id", audit.STORE_ID])
    record = json.loads(capsys.readouterr().out)
    assert calls == [("rev-parse", "--verify", "HEAD"), ("rev-parse", "--verify", "HEAD^{tree}"),
        ("status", "--porcelain=v1", "--untracked-files=normal")]
    if status:
        assert code == 5 and record["category_code"] == "artifact_identity_unavailable"
        assert constructed == [] and status.strip() not in json.dumps(record)
    else:
        assert code == 0 and record["status"] == "passed"
        assert constructed[0]["source_commit"] == "a"*40


@pytest.mark.parametrize("kind", ["quiet", "swap-in", "swap-out", "reclaim-scan", "reclaim-steal",
    "counter-reset", "missing-counter", "unsafe-containment", "short-observation", "snapshot-failure", "counter-bool"])
def test_R2_E_real_interval_counter_observation_is_measured_or_deferred(monkeypatch, kind):
    first = facts(swap_counters=dict(pswpin=1,pswpout=1), reclaim_counters=dict(pgscan_direct=1,pgsteal_direct=1))
    first.pop("swap_active")
    second = copy.deepcopy(first)
    fields = {"swap-in":("swap_counters","pswpin"), "swap-out":("swap_counters","pswpout"),
        "reclaim-scan":("reclaim_counters","pgscan_direct"), "reclaim-steal":("reclaim_counters","pgsteal_direct")}
    if kind in fields: name,key = fields[kind]; second[name][key] += 1
    if kind == "counter-reset": second["swap_counters"]["pswpin"] = 0
    if kind == "missing-counter": del second["swap_counters"]["pswpout"]
    if kind == "counter-bool": second["swap_counters"]["pswpin"] = True
    if kind == "unsafe-containment": second["containment"] = False
    snapshots, sleeps, clock = [], [], [0.0]
    def snapshot():
        snapshots.append(1)
        if kind == "snapshot-failure": raise OSError("synthetic unavailable counters")
        return copy.deepcopy(first if len(snapshots) == 1 else second)
    def sleep(seconds):
        sleeps.append(seconds)
        if kind != "short-observation": clock[0] += seconds
    monkeypatch.setattr(audit, "_resource_snapshot", snapshot)
    monkeypatch.setattr(audit.time, "sleep", sleep)
    monkeypatch.setattr(audit.time, "monotonic", lambda:clock[0])
    if kind == "quiet":
        result = audit.resource_facts()
        assert result["swap_active"] is False
        assert result["observation_interval_seconds"] == audit.RESOURCE_OBSERVATION_SECONDS == .25
        assert len(snapshots) == 2 and sleeps == [.25]
    else:
        with pytest.raises(audit.AuditStop, match="resource_deferred"): audit.resource_facts()


@pytest.mark.parametrize("kind", ["swap", "reclaim", "low-headroom"])
def test_R2_E_measured_activity_or_low_headroom_refuses_before_ram_allocation(tmp_path, monkeypatch, kind):
    _cfg, repo, _svc = setup(tmp_path)
    snapshots, opened, clock = [], [], [0.0]
    def snapshot():
        snapshots.append(1)
        result = facts(mem_available=1 if kind == "low-headroom" else 12*audit.GIB)
        result.pop("swap_active")
        if len(snapshots) > 1:
            if kind == "swap": result["swap_counters"]["pswpout"] = 1
            if kind == "reclaim": result["reclaim_counters"]["pgscan_direct"] = 1
        return result
    monkeypatch.setattr(audit, "_resource_snapshot", snapshot)
    monkeypatch.setattr(audit.time, "sleep", lambda seconds:clock.__setitem__(0,clock[0]+seconds))
    monkeypatch.setattr(audit.time, "monotonic", lambda:clock[0])
    def connect(name, **kwargs): opened.append(name); return sqlite3.connect(name, **kwargs)
    subject = auditor(tmp_path, connect=connect)
    subject.resources = audit.resource_facts
    record, code = subject.run()
    assert code == 3 and record["category_code"] == "resource_deferred"
    assert record["status"] == "incomplete" and ":memory:" not in opened
    repo.close()


@pytest.mark.parametrize("kind", ["canceled", "deadline"])
def test_R2_E_probe_completion_rechecks_cancellation_and_deadline_before_allocating(tmp_path, kind):
    _cfg, repo, _svc = setup(tmp_path)
    opened, clock, cancel = [], [0.0], [False]
    def resources():
        if kind == "canceled": cancel[0] = True
        else: clock[0] = audit.RUN_SECONDS
        return facts()
    def connect(name, **kwargs): opened.append(name); return sqlite3.connect(name, **kwargs)
    subject = auditor(tmp_path, connect=connect, monotonic=lambda:clock[0], canceled=lambda:cancel[0])
    subject.resources = resources
    record, code = subject.run()
    assert code != 0 and record["status"] == "incomplete" and record["category_code"] == kind
    assert ":memory:" not in opened
    repo.close()


def test_R2_E_ongoing_counter_reset_is_unreliable_and_not_quiet(tmp_path):
    _cfg, repo, _svc = setup(tmp_path)
    clock = [0.0]
    class Connection(sqlite3.Connection):
        def backup(self, target, **kwargs):
            clock[0] = 1
            kwargs["progress"](0, 1, 20)
    subject = auditor(tmp_path, monotonic=lambda:clock[0],
        connect=lambda *args,**kwargs:sqlite3.connect(*args, factory=Connection, **kwargs))
    subject.resources = lambda:facts(swap_counters=dict(pswpin=0 if clock[0] else 1,pswpout=0))
    record, code = subject.run()
    assert code == 3 and record["status"] == "incomplete"
    assert record["category_code"] == "resource_deferred"
    repo.close()
