"""G2 disposable Fingerprint adapter; no production store/resource admission.

All paths are private fixture bindings, never accepted from the public protocol.
This module is not imported by service startup. Production admission stays deny.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import select
import sqlite3
import stat
import tempfile
import time

from . import contracts as c
from .locks import PermanentLock, protected_parent, trusted_open

MAX_FIXTURE_BYTES = 8 * 1024**2
_PERMIT_KEY = object()


def _temporary(root):
    path = Path(root)
    temporary = Path(tempfile.gettempdir()).resolve()
    if (not path.is_absolute() or str(path) != str(root) or ".." in path.parts
            or temporary not in path.parents or os.name == "posix" and not (
                Path("/tmp") in path.parents or Path("/var/tmp") in path.parents)):
        raise c.CoordinatorError("not_admitted")
    return path


class _Permit:
    def __init__(self, key, root, source, status, *, gate=None, job=None, identity=None):
        if key is not _PERMIT_KEY:
            raise c.CoordinatorError("unauthorized")
        self._key, self.root = key, _temporary(root)
        self.source, self.status = Path(source), Path(status)
        self.pid, self.gate, self.job, self.identity = os.getpid(), gate, job, identity
        self.used = False


def fixture_authority(root, source, status):
    """Explicit NON-production injection for existing tiny disposable unit tests.

    Never used by CLI, coordinator or production configuration. Unlike worker
    authority this cannot attest a coordinated run, and carries no run context.
    """
    _unit_fixture(root, source, status)
    return _Permit(_PERMIT_KEY, root, source, status)


def _unit_fixture(root, source, status):
    root = _temporary(root)
    if Path(source) != root/"fingerprint.sqlite3" or Path(status) != root/"audit"/"fingerprint_evidence.json":
        raise c.CoordinatorError("unauthorized")
    path = root/".fingerprint-audit-fixture-only"
    descriptor = None
    try:
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise c.CoordinatorError("unauthorized")
        if os.name == "posix" and (before.st_uid != os.geteuid() or before.st_mode & 0o077):
            raise c.CoordinatorError("unauthorized")
        descriptor = os.open(path, os.O_RDONLY|getattr(os,"O_NOFOLLOW",0)|getattr(os,"O_NONBLOCK",0))
        after = os.fstat(descriptor)
        if (before.st_dev,before.st_ino) != (after.st_dev,after.st_ino) or os.read(descriptor,64) != b"DISPOSABLE_UNIT_AUDIT_ONLY_V1\n":
            raise c.CoordinatorError("unauthorized")
    except OSError:
        raise c.CoordinatorError("unauthorized") from None
    finally:
        if descriptor is not None: os.close(descriptor)


def authorize_auditor(permit, source, status):
    if (type(permit) is not _Permit or permit._key is not _PERMIT_KEY
            or permit.pid != os.getpid() or Path(source) != permit.source or Path(status) != permit.status):
        raise c.CoordinatorError("unauthorized")
    root = _temporary(permit.root)
    for path in (Path(source), Path(status)):
        if (not path.is_absolute() or ".." in path.parts or root not in path.parents
                or path == root):
            raise c.CoordinatorError("unauthorized")
    if permit.job is None:
        # The only exception to a real heavy gate is explicit tiny fixture-only
        # unit injection. It cannot authorize any configured /opt or /var DB.
        _unit_fixture(root, source, status)
        return dict(fixture_only=True, max_image_bytes=MAX_FIXTURE_BYTES)
    if permit.used or type(permit.gate) is not PermanentLock:
        raise c.CoordinatorError("unauthorized")
    permit.gate.check()
    permit.used = True
    return dict(fixture_only=True, max_image_bytes=MAX_FIXTURE_BYTES,
        job_id=permit.job["job_id"], run_id=permit.job["run_id"], attempt_id=permit.job["attempt_id"],
        claim_epoch=permit.job["claim_epoch"], source_generation=permit.job["source_generation"],
        source_device=permit.identity[0], source_inode=permit.identity[1], validator_version=c.FINGERPRINT_VALIDATOR)


@dataclass(frozen=True)
class FingerprintFixturePlan:
    root: str
    source_device: int
    source_inode: int
    source_generation: str
    mode: str = "pass"
    timeout_seconds: int = 5
    adapter: str = "fingerprint_fixture_v1"

    @property
    def source(self): return Path(self.root) / "fingerprint.sqlite3"

    @property
    def status(self): return Path(self.root) / "fp-status" / "fingerprint_evidence.json"

    def metadata(self, store_id):
        if store_id != "fingerprint_evidence" or self.adapter != "fingerprint_fixture_v1":
            raise c.CoordinatorError("not_admitted")
        _temporary(self.root)
        c.integer(self.source_device); c.integer(self.source_inode); c.identifier(self.source_generation)
        c.integer(self.timeout_seconds, 10)
        if self.timeout_seconds < 1 or self.mode not in {
            "pass", "hold_backup", "crash_backup", "crash_after_snapshot", "hold_after_snapshot",
            "crash_before_result", "hold_before_result"}:
            raise c.CoordinatorError("not_admitted")
        return c.FINGERPRINT_METHOD, c.FINGERPRINT_VALIDATOR, self.source_generation

    def preflight(self, job, gate):
        method, validator, generation = self.metadata(job["store_id"])
        if (job["method_version"], job["validator_version"], job["source_generation"]) != (method, validator, generation):
            raise c.CoordinatorError("unauthorized")
        gate.check()  # Called ONLY after private worker authority and heavy flock.
        protected_parent(self.status, os.geteuid())
        marker = trusted_open(Path(self.root) / "fingerprint-fixture.v1", os.geteuid())
        try:
            if os.read(marker, 64) != b"DISPOSABLE_FINGERPRINT_G2_V1\n":
                raise c.CoordinatorError("not_admitted")
        finally: os.close(marker)
        _marker(self.root, job["job_id"]+".preflight")
        source = trusted_open(self.source, os.geteuid(), identity=(self.source_device, self.source_inode))
        try:
            if not 0 < os.fstat(source).st_size <= MAX_FIXTURE_BYTES:
                raise c.CoordinatorError("not_admitted")
        finally: os.close(source)


class FingerprintFixtureAdmission:
    def __init__(self, plan): self.plan = plan

    def metadata(self, store_id): return self.plan.metadata(store_id)

    def envelope(self, job):
        self.plan.metadata(job["store_id"])
        return dict(fixture_only=True, memory_limit_bytes=64*1024**2, timeout_seconds=self.plan.timeout_seconds)


def _fixture_facts():
    # Synthetic facts for the unchanged historical validator's admission math;
    # NOT a live 16-GiB or 64-MiB profile and NOT an enforced cgroup limit.
    gib = 1024**3
    return dict(fixture_only=True, mem_total=16*gib, mem_available=12*gib,
        cgroup_headroom=12*gib, address_headroom=None, containment=True, swap_active=False,
        swap_counters=dict(pswpin=0, pswpout=0), reclaim_counters=dict(pgscan_direct=0, pgsteal_direct=0),
        peak_rss_bytes=0, memory_psi=None, io_psi=None)


def _marker(root, name):
    descriptor = os.open(Path(root)/name, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC, 0o600)
    os.close(descriptor)


def _status_result(plan, job):
    from app.device_fingerprint.audit_runner import StatusStore, METHOD, CONTRACT
    document = StatusStore(plan.status).read()
    record = document["last_attempt"]
    expected = {key:job[key] for key in ("job_id", "run_id", "attempt_id", "claim_epoch", "source_generation", "validator_version")}
    expected["schema_version"] = 2
    if (record.get("coordinator_identity") != expected or record.get("run_id") != job["run_id"]
            or record.get("audit_method_version") != METHOD or METHOD != c.FINGERPRINT_METHOD
            or record.get("audit_contract_version") != CONTRACT or record.get("store_id") != "fingerprint_evidence"):
        raise c.CoordinatorError("unauthorized")
    status = record.get("status")
    snapshot = None
    reason = "status_untrusted"
    if status in {"passed", "failed"}:
        identity = record.get("source_path_identity") or {}
        if (identity.get("path") != str(plan.source) or identity.get("device") != plan.source_device
                or identity.get("inode") != plan.source_inode):
            raise c.CoordinatorError("unauthorized")
    if status == "passed":
        if (record.get("database_generation_id") != job["source_generation"]
                or record.get("category_code") != "snapshot_passed"
                or record.get("check_summary", {}).get("domain") != "passed"
                or record.get("check_summary", {}).get("integrity") != "ok"
                or record.get("check_summary", {}).get("foreign_keys") not in {"checked", "not_applicable"}
                or record.get("backup_progress_summary", {}).get("completed") is not True
                or record.get("backup_progress_summary", {}).get("remaining") != 0
                or record.get("cleanup_error") or document["last_verified_success"] != record):
            raise c.CoordinatorError("unauthorized")
        c.integer(record.get("snapshot_last_ingest_sequence"))
        c.timestamp(record.get("snapshot_at_utc"))
        snapshot = hashlib.sha256(c.encode(record)).hexdigest()
        reason = "fingerprint_snapshot_passed"
    elif status == "failed" and record.get("category_code") == "integrity_suspect":
        reason = "fingerprint_integrity_suspect"
    elif status == "incomplete":
        reason = {"resource_deferred":"resource_deferred", "canceled":"canceled", "deadline":"timeout"}.get(record.get("category_code"), "status_untrusted")
    else:
        raise c.CoordinatorError("unauthorized")
    return dict(fixture_only=True, **{key:job[key] for key in (
        "job_id", "store_id", "run_id", "attempt_id", "claim_epoch", "method_version", "validator_version", "source_generation")},
        snapshot_id=snapshot, completed_at=record["finished_at_utc"],
        result="passed" if status == "passed" else "failed" if status == "failed" else "incomplete", reason_code=reason)


def verify_completed_result(plan, job, result):
    """Coordinator checks ONLY protected JSON AFTER positive reap/release proof.

    No source stat/open/preflight/SQLite in this function.
    """
    if type(plan) is not FingerprintFixturePlan or _status_result(plan, job) != result:
        raise c.CoordinatorError("unauthorized")


def run_fixture(plan, job, gate, control):
    from app.device_fingerprint.audit_runner import EvidenceAuditor, StatusStore
    plan.preflight(job, gate)
    deadline = time.monotonic() + plan.timeout_seconds
    stopped, released = [False], [False]
    def canceled():
        gate.check()
        if time.monotonic() >= deadline: stopped[0] = True
        if select.select([control], [], [], 0)[0]:
            if os.read(control, 1) == b"g": released[0] = True
            else: stopped[0] = True
        return stopped[0]
    def boundary(name, hold, crash):
        _marker(plan.root, job["job_id"]+"."+name)
        if crash: os._exit(81)
        if hold:
            released[0] = False
            while not canceled() and not released[0]:
                select.select([control], [], [], min(.02, max(0, deadline-time.monotonic())))
    class Connection(sqlite3.Connection):
        def backup(self, target, **kwargs):
            original = kwargs["progress"]; first = [True]
            def progress(code, remaining, total):
                if first[0]:
                    first[0] = False
                    boundary("backup", plan.mode == "hold_backup", plan.mode == "crash_backup")
                original(code, remaining, total)
            return super().backup(target, **{**kwargs, "progress":progress})
    class Store(StatusStore):
        def write(self, document):
            super().write(document)
            if (document["last_attempt"].get("stage") == "integrity"
                    and document["last_attempt"].get("coordinator_identity", {}).get("job_id") == job["job_id"]):
                boundary("snapshot", plan.mode == "hold_after_snapshot", plan.mode == "crash_after_snapshot")
    permit = _Permit(_PERMIT_KEY, plan.root, plan.source, plan.status,
        gate=gate, job=job, identity=(plan.source_device, plan.source_inode))
    def connect(name, **kwargs):
        if name != ":memory:": _marker(plan.root, job["job_id"]+".source_read")
        connection = sqlite3.connect(name, factory=Connection, **kwargs)
        if name != ":memory:":
            try:
                if connection.execute("PRAGMA journal_mode").fetchone()[0] != "wal":
                    from app.device_fingerprint.audit_runner import AuditStop
                    raise AuditStop("source_changed")
            except BaseException:
                connection.close()
                raise
        return connection
    record, code = EvidenceAuditor(plan.source, status=Store(plan.status), resources=_fixture_facts,
        connect=connect,
        canceled=canceled, authorization=permit).run()
    boundary("auditor_returned", plan.mode == "hold_before_result", plan.mode == "crash_before_result")
    if stopped[0] or time.monotonic() >= deadline:
        from .worker import result_for
        return result_for(job, "incomplete", "timeout" if time.monotonic() >= deadline else "canceled"), 2
    try:
        result = _status_result(plan, job)
        c.result(result)
        if code != 0 and result["result"] == "passed": raise c.CoordinatorError("unauthorized")
        return result, code
    except (c.CoordinatorError, ValueError, OSError, KeyError):
        from .worker import result_for
        return result_for(job, "incomplete", "gate_busy" if record.get("category_code") == "already_running" else "status_untrusted"), 2
