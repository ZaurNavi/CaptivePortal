"""Private G1 fixture worker. No application auditor or real DB adapter imports."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import select
import stat
import sys
import time

from . import contracts as c
from .admission import FixturePlan
from .locks import LockSpec, PermanentLock, trusted_open
from .state_store import StateStore, atomic_publish

AUTH_KEYS = {"job_id","store_id","claim_epoch","attempt_id","nonce","root","uid","gate","plan","cancel_fd"}


def authorization(descriptor):
    """The private pipe's dev/inode is durable claim authority, not its bytes alone."""
    try:
        info=os.fstat(descriptor)
        if not stat.S_ISFIFO(info.st_mode):raise c.CoordinatorError("unauthorized")
        raw=bytearray();deadline=time.monotonic()+3
        while len(raw)<=c.MAX_FRAME:
            remaining=deadline-time.monotonic()
            if remaining<=0 or not select.select([descriptor],[],[],remaining)[0]:raise c.CoordinatorError("unauthorized")
            chunk=os.read(descriptor,c.MAX_FRAME+1-len(raw))
            if not chunk:break
            raw.extend(chunk)
        data=c.decode(bytes(raw),c.MAX_FRAME);c.closed(data,AUTH_KEYS)
        for key in ("job_id","claim_epoch","attempt_id"):c.identifier(data[key])
        if data["store_id"] not in c.STORES:raise c.CoordinatorError("unauthorized")
        c.digest(data["nonce"]);c.integer(data["uid"],2**32-1);c.integer(data["cancel_fd"],2**20)
        queue=StateStore(Path(data["root"])/"queue-state.v1.json",data["uid"])
        state=queue.read()
        job=next((job for job in state["jobs"] if job["job_id"]==data["job_id"]),None)
        if (job is None or job["state"] not in {"claimed","running"} or job["worker_pid"]!=os.getpid()
                or state["controller_epoch"]!=data["claim_epoch"]
                or any(job[key]!=data[key] for key in ("store_id","claim_epoch","attempt_id"))
                or (info.st_dev,info.st_ino)!=(job["auth_device"],job["auth_inode"])
                or hashlib.sha256(data["nonce"].encode()).hexdigest()!=job["auth_hash"]):
            raise c.CoordinatorError("unauthorized")
        return data,job
    except Exception:
        raise c.CoordinatorError("unauthorized") from None
    finally:
        try:os.close(descriptor)
        except OSError:pass


def result_for(job,kind,reason,snapshot=None):
    return dict(fixture_only=True,**{key:job[key] for key in ("job_id","store_id","run_id","attempt_id",
        "claim_epoch","method_version","validator_version","source_generation")},
        snapshot_id=snapshot,completed_at=c.utc(),result=kind,reason_code=reason)


def _wait_control(descriptor,seconds):
    if not select.select([descriptor],[],[],seconds)[0]:return "timeout"
    return "go" if os.read(descriptor,1)==b"g" else "canceled"


def execute(descriptor, *, offline_hooks=None):
    authority,job=authorization(descriptor)
    # Authorization is checked before even opening the heavy gate, let alone
    # preflight/source geometry/read. The parent never opens this description.
    gate=PermanentLock(LockSpec(**authority["gate"]))
    result=None
    try:
        gate.acquire()
        if authority["plan"] is None:
            from .operational_hooks import probe_after_lock
            probe_after_lock(job, gate, offline_hooks, now_ns=time.monotonic_ns())
            # B1 has NO real adapter. Even simulated success (or a replaced hook)
            # cannot fall through to either of the accepted tiny fixture paths.
            raise c.CoordinatorError("not_admitted")
        if job["method_version"] == c.FINGERPRINT_METHOD and authority["plan"].get("adapter") != "fingerprint_fixture_v1":
            raise c.CoordinatorError("unauthorized")
        if authority["plan"].get("adapter") == "fingerprint_fixture_v1":
            from .fingerprint_adapter import FingerprintFixturePlan, run_fixture
            plan=FingerprintFixturePlan(**authority["plan"])
            if job["resource_envelope"]!={"fixture_only":True,"memory_limit_bytes":64*1024**2,"timeout_seconds":plan.timeout_seconds}:
                raise c.CoordinatorError("not_admitted")
            result,code=run_fixture(plan,job,gate,authority["cancel_fd"])
            gate.check();c.result(result)
            atomic_publish(Path(authority["root"])/(job["job_id"]+".result.json"),result,authority["uid"])
            return code
        if (job["method_version"], job["validator_version"]) != ("fixture.sentinel.v1", "fixture.v1"):
            raise c.CoordinatorError("unauthorized")
        plan=FixturePlan(**authority["plan"]).validate(authority["uid"])
        if job["resource_envelope"]!={"fixture_only":True,"memory_limit_bytes":64*1024**2,"timeout_seconds":plan.timeout_seconds}:
            raise c.CoordinatorError("not_admitted")
        path=Path(plan.root)
        def event(name):
            # Fixture-only sentinel, not production logging/progress persistence.
            target=path/(job["job_id"]+"."+name)
            fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
            os.close(fd)
        event("preflight")
        if plan.mode=="hold_preflight":
            reason=_wait_control(authority["cancel_fd"],plan.timeout_seconds)
            if reason!="go":result=result_for(job,"incomplete",reason)
        gate.check()
        if result is None:
            event("source_read")
            source=trusted_open(path/"source.sentinel",authority["uid"])
            try:
                data=os.read(source,4097)
                if len(data)>4096:raise c.CoordinatorError("not_admitted")
                snapshot=hashlib.sha256(data).hexdigest()
            finally:os.close(source)
            if plan.mode=="crash":os._exit(70)
            if plan.mode in {"hold_audit","timeout"}:
                reason=_wait_control(authority["cancel_fd"],plan.timeout_seconds)
                if reason!="go":result=result_for(job,"incomplete",reason)
            if result is None:
                result=result_for(job,"failed" if plan.mode=="fail" else "passed",
                    "fixture_failed" if plan.mode=="fail" else "fixture_passed",snapshot)
        gate.check()
        c.result(result)
        def status_sync(fd):
            directory=stat.S_ISDIR(os.fstat(fd).st_mode)
            if plan.mode=="crash_before_status_sync" and not directory:os._exit(71)
            os.fsync(fd)
            if plan.mode=="crash_after_status_sync" and directory:os._exit(72)
        atomic_publish(Path(authority["root"])/(job["job_id"]+".result.json"),result,authority["uid"],sync=status_sync)
        return 0
    except c.CoordinatorError as error:
        reason={"not_admitted":"resource_deferred","gate_busy":"gate_busy","unsafe_path":"unsafe_path"}.get(error.code,"status_untrusted")
        # No passed claim after lock, trust, status or admission failure.
        failure=result_for(job,"incomplete",reason)
        try:atomic_publish(Path(authority["root"])/(job["job_id"]+".result.json"),failure,authority["uid"])
        except Exception:pass
        return 2
    except Exception:
        return 3
    finally:
        # A valid worker is a dedicated process, never an in-process adapter.
        # Do not release the heavy FD early, even between Python return/cleanup
        # and actual exit. The kernel closes it at process termination only.
        try:os.close(authority["cancel_fd"])
        except OSError:pass


def main(argv=None):
    argv=sys.argv[1:] if argv is None else argv
    if os.name!="posix" or len(argv)!=1 or not argv[0].isascii() or not argv[0].isdecimal():return 2
    try:return execute(int(argv[0]))
    except Exception:return 2


if __name__=="__main__":raise SystemExit(main())
