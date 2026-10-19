"""Small real schema2 Fingerprint fixtures; no real store or containment claim."""
import copy
import ctypes
from dataclasses import replace
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import signal
import sqlite3
import sys
import uuid

import pytest

from app.db_audit_coordinator import contracts as c
from app.db_audit_coordinator.admission import FixtureCompletionFence, FixtureFilesystem
from app.db_audit_coordinator.coordinator import Coordinator
from app.db_audit_coordinator.fingerprint_adapter import (
    FingerprintFixtureAdmission, FingerprintFixturePlan, fixture_authority, authorize_auditor,
)
from app.db_audit_coordinator.locks import PermanentLock
from app.db_audit_coordinator.state_store import read_json, atomic_publish
from app.device_fingerprint import audit_runner as audit
from tests.db_audit_coordinator import lab, submit, complete, cleanup, marker
from tests.device_fingerprint.test_qio_evidence_fast_start_ram_audit import setup, facts, corrupt_index

linux = pytest.mark.skipif(sys.platform != "linux", reason="G2 real Linux worker/SQLite/flock/reap contract")


def fingerprint_lab(tmp_path, mode="pass", timeout=5):
    fixture = lab(tmp_path)
    cfg, repository, _service = setup(fixture.root, rows=3)
    generation = repository.read_ingest_watermark(repository.connection)["database_generation_id"]
    repository.close()
    path = Path(cfg.db_path); path.chmod(0o600)
    info = path.stat()
    (fixture.root/"fp-status").mkdir(mode=0o700)
    mark = fixture.root/"fingerprint-fixture.v1"
    mark.write_bytes(b"DISPOSABLE_FINGERPRINT_G2_V1\n"); mark.chmod(0o600)
    plan = FingerprintFixturePlan(str(fixture.root), info.st_dev, info.st_ino, generation, mode, timeout)
    return fixture, plan


def subject_for(fixture, plan, *, fence=None, sync=os.fsync):
    return Coordinator(fixture.root, fixture.owner, fixture.gate,
        admission=FingerprintFixtureAdmission(plan), filesystem=FixtureFilesystem(),
        fence=FixtureCompletionFence() if fence is None else fence, sync=sync)


@pytest.mark.parametrize("authority", [None, {}, "nonce", object()])
def test_direct_run_denies_before_any_geometry_status_lock_or_sqlite(tmp_path, monkeypatch, authority):
    calls = []
    monkeypatch.setattr(audit, "protected_parent", lambda *a: calls.append("path"))
    monkeypatch.setattr(audit, "_identity", lambda *a: calls.append("geometry"))
    value, code = audit.EvidenceAuditor(tmp_path/"missing.sqlite3", authorization=authority,
        connect=lambda *a, **kw:calls.append("connect"), resources=lambda:calls.append("resources")).run()
    assert code == 6 and value == {"status":"incomplete", "category_code":"unauthorized"}
    assert calls == [] and list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("root", ["/opt/CaptivePortal/data", "/var/lib/captivprod-evidence", "/var/lib/captive-portal/db-audit"])
def test_fixture_authority_cannot_authorize_configured_roots(root):
    with pytest.raises(c.CoordinatorError):
        fixture_authority(root, Path(root)/"evidence.sqlite3", Path(root)/"status.json")


def test_fixture_authority_exact_path_not_transferable(tmp_path):
    marker=tmp_path/".fingerprint-audit-fixture-only"
    marker.write_bytes(b"DISPOSABLE_UNIT_AUDIT_ONLY_V1\n");marker.chmod(0o600)
    source,status=tmp_path/"fingerprint.sqlite3",tmp_path/"audit"/"fingerprint_evidence.json"
    permit = fixture_authority(tmp_path, source, status)
    with pytest.raises(c.CoordinatorError): authorize_auditor(permit, tmp_path/"two", status)


@pytest.mark.parametrize("kind", ["absent","wrong-marker","wrong-source","wrong-status"])
def test_unit_authority_needs_explicit_marker_and_exact_disposable_binding(tmp_path,kind):
    marker=tmp_path/".fingerprint-audit-fixture-only"
    if kind!="absent":
        marker.write_bytes(b"wrong" if kind=="wrong-marker" else b"DISPOSABLE_UNIT_AUDIT_ONLY_V1\n");marker.chmod(0o600)
    source=tmp_path/("evidence.sqlite3" if kind=="wrong-source" else "fingerprint.sqlite3")
    status=tmp_path/"audit"/("other.json" if kind=="wrong-status" else "fingerprint_evidence.json")
    with pytest.raises(c.CoordinatorError):fixture_authority(tmp_path,source,status)


@linux
def test_fingerprint_admission_never_registers_another_real_store(tmp_path):
    fixture,plan=fingerprint_lab(tmp_path);subject=subject_for(fixture,plan)
    try:
        for store in sorted(c.STORES-{"fingerprint_evidence"}):
            with pytest.raises(c.CoordinatorError,match="not_admitted"):submit(subject,store)
        assert subject.store.read()["jobs"]==[] and subject.process is None
        assert not tuple(fixture.root.glob("*.source_read"))
    finally:cleanup(subject)


@linux
def test_genuine_online_backup_original_t3_and_both_protected_histories(tmp_path):
    fixture, plan = fingerprint_lab(tmp_path)
    before = plan.source.read_bytes()
    subject = subject_for(fixture, plan)
    try:
        reply = submit(subject, "fingerprint_evidence")
        assert reply["job"]["method_version"] == c.FINGERPRINT_METHOD
        assert reply["job"]["source_generation"] == plan.source_generation
        subject.dispatch_one(); process = complete(subject)
        state = subject.store.read(); result = state["jobs"][0]["audit_result"]
        assert process.returncode == 0 and result["result"] == "passed"
        record = audit.StatusStore(plan.status).read()["last_verified_success"]
        assert record["check_summary"] == {"integrity":"ok", "foreign_keys":"not_applicable", "domain":"passed",
            "rows":{"device_fingerprint_evidence":3, "device_fingerprint_source_health_events":1}}
        assert record["backup_progress_summary"]["completed"] is True
        assert record["run_id"] == result["run_id"] and record["database_generation_id"] == plan.source_generation
        assert record["coordinator_identity"]["schema_version"] == 2
        assert state["last_verified_success_by_store"]["fingerprint_evidence"] == result
        assert plan.source.read_bytes() == before
        assert str(fixture.root) not in json.dumps(subject.status(reply["job"]["job_id"], c.scope(os.geteuid())) )
        assert b"vendor_class" not in c.encode(result)
    finally: cleanup(subject)


@linux
@pytest.mark.parametrize("kind", ["missing", "corrupt", "generation", "source-identity", "wal-mode", "validator"])
def test_bad_fixture_identity_or_validator_never_becomes_passed(tmp_path, kind):
    fixture, plan = fingerprint_lab(tmp_path)
    if kind == "missing": plan.source.unlink()
    elif kind == "corrupt": corrupt_index(plan.source, "N08")
    elif kind == "generation": plan = replace(plan, source_generation=str(uuid.uuid4()))
    elif kind == "source-identity":
        replacement = fixture.root/"replacement.sqlite3"; replacement.write_bytes(plan.source.read_bytes()); replacement.chmod(0o600)
        replacement.replace(plan.source)
    elif kind == "wal-mode":
        with sqlite3.connect(plan.source) as connection: assert connection.execute("PRAGMA journal_mode=DELETE").fetchone()[0] == "delete"
    subject = subject_for(fixture, plan)
    try:
        submit(subject, "fingerprint_evidence")
        if kind == "validator":
            state = subject.store.read(); state["jobs"][0]["validator_version"] = "unapproved"
            with pytest.raises(c.CoordinatorError): subject.store.commit(state)
            assert subject.process is None
            return
        subject.dispatch_one(); complete(subject)
        state = subject.store.read()
        assert state["jobs"][0]["audit_result"]["result"] != "passed"
        assert state["last_verified_success_by_store"] == {}
        if kind in {"missing", "source-identity"}: assert not tuple(fixture.root.glob("*.source_read"))
    finally: cleanup(subject)


@linux
def test_two_pids_fingerprint_backup_and_other_fixture_never_overlap(tmp_path):
    a,b=tmp_path/"a",tmp_path/"b";a.mkdir();b.mkdir()
    fixture,plan=fingerprint_lab(a,"hold_backup",10);other=lab(b)
    one=subject_for(fixture,plan);two=other.coordinator();two.gate_spec=fixture.gate
    try:
        first=submit(one,"fingerprint_evidence");second=submit(two)
        one.dispatch_one();marker(fixture,first["job"]["job_id"],"backup")
        two.dispatch_one();other_process=complete(two)
        assert other_process.pid != one.process.pid
        assert two.store.read()["jobs"][0]["reason_code"] == "gate_busy"
        assert not tuple(other.root.glob("*.preflight")) and not tuple(other.root.glob("*.source_read"))
        with pytest.raises(c.CoordinatorError,match="gate_busy"): PermanentLock(fixture.gate).acquire()
        os.write(one.cancel_fd,b"g");complete(one)
        assert one.store.read()["jobs"][0]["audit_result"]["result"] == "passed"
    finally: cleanup(one);cleanup(two)


@linux
@pytest.mark.parametrize("mode", ["crash_backup","crash_after_snapshot","crash_before_result"])
def test_worker_crashes_never_promote_private_status_or_replay(tmp_path, mode):
    fixture,plan=fingerprint_lab(tmp_path,mode);subject=subject_for(fixture,plan);restarted=None
    try:
        submit(subject,"fingerprint_evidence");subject.dispatch_one();process=complete(subject)
        assert process.returncode == 81
        state=subject.store.read()
        assert state["jobs"][0]["audit_result"]["result"] == "incomplete"
        assert state["last_verified_success_by_store"] == {}
        subject.close();restarted=subject_for(fixture,replace(plan,mode="pass"))
        assert not restarted.dispatch_one()
        assert restarted.store.read()["last_verified_success_by_store"] == {}
    finally:
        cleanup(subject)
        if restarted is not None:cleanup(restarted)


@linux
@pytest.mark.parametrize("mode,cancel", [("hold_backup",True),("hold_after_snapshot",True),("hold_before_result",True),("hold_backup",False)])
def test_cancel_or_timeout_keeps_lock_until_real_worker_exit(tmp_path,mode,cancel):
    fixture,plan=fingerprint_lab(tmp_path,mode,2);subject=subject_for(fixture,plan)
    try:
        reply=submit(subject,"fingerprint_evidence");subject.dispatch_one()
        marker(fixture,reply["job"]["job_id"],{"hold_backup":"backup","hold_after_snapshot":"snapshot","hold_before_result":"auditor_returned"}[mode])
        if cancel:subject.cancel(reply["job"]["job_id"])
        assert not subject.dispatch_one()
        complete(subject)
        state=subject.store.read()
        assert state["jobs"][0]["audit_result"]["result"] == "incomplete"
        assert state["last_verified_success_by_store"] == {}
        with PermanentLock(fixture.gate):pass
    finally:cleanup(subject)


@linux
def test_hundred_idle_status_and_duplicate_do_not_rewrite_either_history(tmp_path):
    fixture,plan=fingerprint_lab(tmp_path);syncs=[]
    def sync(fd):syncs.append(1);os.fsync(fd)
    subject=subject_for(fixture,plan,sync=sync);key=str(uuid.uuid4())
    try:
        reply=submit(subject,"fingerprint_evidence",key=key);subject.dispatch_one();complete(subject)
        before=len(syncs);private=plan.status.read_bytes();queue=(fixture.root/"queue-state.v1.json").read_bytes()
        for _ in range(100):
            assert subject.status(reply["job"]["job_id"],c.scope(os.geteuid()))["job"]["state"] == "completed"
            assert submit(subject,"fingerprint_evidence",key=key)["status"] == "duplicate"
        assert len(syncs)==before and plan.status.read_bytes()==private and (fixture.root/"queue-state.v1.json").read_bytes()==queue
    finally:cleanup(subject)


@linux
@pytest.mark.parametrize("field", ["run_id","source_generation","validator_version","schema_version"])
def test_reaped_worker_result_requires_matching_fingerprint_protected_status(tmp_path,field):
    fixture,plan=fingerprint_lab(tmp_path);subject=subject_for(fixture,plan)
    try:
        submit(subject,"fingerprint_evidence");subject.dispatch_one()
        subject._wake_read.settimeout(6);subject._wake_read.recv(1)
        assert subject.process.returncode==0
        document=audit.StatusStore(plan.status).read()
        document["last_attempt"]["coordinator_identity"][field]=0 if field=="schema_version" else str(uuid.uuid4())
        audit.StatusStore(plan.status).write(document)
        assert subject.finish()
        assert subject.store.read()["jobs"][0]["audit_result"]["result"]=="incomplete"
        assert subject.store.read()["last_verified_success_by_store"]=={}
    finally:cleanup(subject)


@linux
def test_last_success_preserved_in_both_histories_after_new_corruption(tmp_path):
    fixture,plan=fingerprint_lab(tmp_path);subject=subject_for(fixture,plan)
    try:
        submit(subject,"fingerprint_evidence");subject.dispatch_one();complete(subject)
        queue_success=copy.deepcopy(subject.store.read()["last_verified_success_by_store"])
        fp_success=copy.deepcopy(audit.StatusStore(plan.status).read()["last_verified_success"])
        corrupt_index(plan.source,"N08")
        submit(subject,"fingerprint_evidence");subject.dispatch_one();complete(subject)
        assert subject.store.read()["jobs"][-1]["audit_result"]["result"]=="failed"
        assert subject.store.read()["last_verified_success_by_store"]==queue_success
        assert audit.StatusStore(plan.status).read()["last_verified_success"]==fp_success
    finally:cleanup(subject)


@linux
def test_worker_capability_needs_live_independent_gate_and_is_single_use(tmp_path):
    from app.db_audit_coordinator.fingerprint_adapter import _Permit,_PERMIT_KEY
    fixture,plan=fingerprint_lab(tmp_path);gate=PermanentLock(fixture.gate)
    job=dict(job_id=str(uuid.uuid4()),run_id=str(uuid.uuid4()),attempt_id=str(uuid.uuid4()),
        claim_epoch=str(uuid.uuid4()),source_generation=plan.source_generation)
    permit=_Permit(_PERMIT_KEY,plan.root,plan.source,plan.status,gate=gate,job=job,identity=(plan.source_device,plan.source_inode))
    with pytest.raises(c.CoordinatorError):authorize_auditor(permit,plan.source,plan.status)
    gate.acquire()
    try:
        value=authorize_auditor(permit,plan.source,plan.status)
        assert value["job_id"]==job["job_id"]
        with pytest.raises(c.CoordinatorError):authorize_auditor(permit,plan.source,plan.status)
    finally:gate.close()
    with pytest.raises(c.CoordinatorError):authorize_auditor(permit,plan.source,plan.status)


def fingerprint_supervisor(fixture,plan,connection):
    subject=subject_for(fixture,plan)
    try:
        reply=submit(subject,"fingerprint_evidence");subject.dispatch_one()
        connection.send((reply,subject.process.pid));connection.recv()
    finally:cleanup(subject)


@linux
def test_supervisor_sigkill_during_real_backup_keeps_worker_flock_and_orphan_hold(tmp_path):
    fixture,plan=fingerprint_lab(tmp_path,"hold_backup",8)
    libc=ctypes.CDLL(None);previous=ctypes.c_int()
    assert libc.prctl(37,ctypes.byref(previous),0,0,0)==0 and libc.prctl(36,1,0,0,0)==0
    context=multiprocessing.get_context("spawn");parent,child=context.Pipe()
    supervisor=context.Process(target=fingerprint_supervisor,args=(fixture,plan,child));pid=None;restarted=None
    try:
        supervisor.start();child.close();assert parent.poll(6);reply,pid=parent.recv()
        marker(fixture,reply["job"]["job_id"],"backup");os.kill(pid,signal.SIGSTOP)
        supervisor.kill();supervisor.join(4);assert supervisor.exitcode is not None
        with pytest.raises(c.CoordinatorError,match="gate_busy"):PermanentLock(fixture.gate).acquire()
        restarted=subject_for(fixture,replace(plan,mode="pass"))
        assert restarted.orphan_hold and not restarted.reconcile() and not restarted.dispatch_one()
        os.kill(pid,signal.SIGCONT);reaped,status=os.waitpid(pid,0);assert reaped==pid
        pid=None
        assert not restarted.reconcile()  # No PID-absence proof or blind replay.
    finally:
        if pid is not None:
            try:os.kill(pid,signal.SIGKILL)
            except ProcessLookupError:pass
            try:os.waitpid(pid,0)
            except ChildProcessError:pass
        if supervisor.is_alive():supervisor.kill()
        supervisor.join(4);parent.close()
        if restarted is not None:cleanup(restarted)
        assert libc.prctl(36,previous.value,0,0,0)==0
