"""Single authority; no real adapters, implicit provisioning or service hooks."""
from __future__ import annotations

import copy
from dataclasses import asdict
import hashlib
import os
from pathlib import Path
import selectors
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import uuid

from . import contracts as c
from .admission import Admission, CompletionFence, FilesystemAdmission
from .locks import PermanentLock, protected_parent
from .protocol import peer_scope, receive, send
from .state_store import StateStore, read_json
from .worker import result_for


class Coordinator:
    store_type = StateStore
    def __init__(self,root,owner_spec,gate_spec,*,admission=None,fence=None,filesystem=None,sync=os.fsync):
        self.root,self.uid,self.gate_spec=Path(root),owner_spec.uid,gate_spec
        (filesystem or FilesystemAdmission()).validate(self.root,self.uid)
        self.admission,self.fence=admission or Admission(),fence or CompletionFence()
        self.owner=PermanentLock(owner_spec).acquire()
        self._mutex=threading.RLock();self.process=None;self.active=None;self.cancel_fd=None
        self._halted=False;self._closed=False;self.orphan_hold=False;self._reaped=None
        self._wake_read,self._wake_write=socket.socketpair()
        self._serving=False
        try:
            self.store=self.store_type(self.root/"queue-state.v1.json",self.uid,self.owner,sync=sync)
            state=self.store.read()
            state["controller_epoch"]=str(uuid.uuid4())
            for job in state["jobs"]:
                if job["state"] in {"claimed","running"}:
                    job["reason_code"]="orphan_hold";self.orphan_hold=True
            self.store.commit(state)
        except Exception:
            self.close();raise

    def _state(self):
        if self._halted or self._closed:raise c.CoordinatorError("coordinator_unavailable")
        try:self.owner.check();return self.store.read()
        except Exception:self._halted=True;raise

    def _commit(self,state):
        try:self.store.commit(state)
        except Exception:self._halted=True;raise

    def submit(self,store_id,key,origin,scope_hash):
        c.request(dict(op="submit",store_id=store_id,idempotency_key=key,origin=origin));c.digest(scope_hash)
        with self._mutex:
            state=self._state();hashed=c.idempotency(scope_hash,key)
            # Scope includes store identity: same key on another store is distinct.
            hashed=hashlib.sha256((store_id+":"+hashed).encode()).hexdigest()
            previous=next((job for job in state["jobs"] if job["idempotency_hash"]==hashed),None)
            if previous:return dict(status="duplicate",job=c.public_job(previous))
            # Finite pilot: total retained ACK history saturates before admission.
            # No pruning, rollover, source access, or commit on this read path.
            if len(state["jobs"])>=c.MAX_HISTORY:raise c.CoordinatorError("queue_full")
            if self.orphan_hold:raise c.CoordinatorError("orphan_hold")
            outstanding=[job for job in state["jobs"] if job["state"] in c.OUTSTANDING]
            if any(job["store_id"]==store_id for job in outstanding):raise c.CoordinatorError("store_busy")
            if len(outstanding)>=c.MAX_OUTSTANDING:raise c.CoordinatorError("queue_full")
            now=c.utc()
            metadata=getattr(self.admission,"metadata",None)
            method,validator,generation=metadata(store_id) if metadata is not None else ("fixture.sentinel.v1","fixture.v1",str(uuid.uuid4()))
            job=dict(job_id=str(uuid.uuid4()),seq=state["next_sequence"],store_id=store_id,scope_hash=scope_hash,
                idempotency_hash=hashed,origin=origin,state="queued",claim_epoch=None,attempt_id=None,run_id=None,
                created_at=now,updated_at=now,reason_code="accepted",method_version=method,
                validator_version=validator,source_generation=generation,resource_envelope=None,
                auth_hash=None,auth_device=None,auth_inode=None,worker_pid=None,audit_result=None)
            state["jobs"].append(job);state["next_sequence"]+=1
            self._commit(state)
            return dict(status="queued",job=c.public_job(job))

    def status(self,job_id,scope_hash):
        c.identifier(job_id);c.digest(scope_hash)
        with self._mutex:
            state=self._state()
            job=next((job for job in state["jobs"] if job["job_id"]==job_id and job["scope_hash"]==scope_hash),None)
            if job is None:raise c.CoordinatorError("invalid_request")
            return dict(status="status",job=c.public_job(job),
                last_attempt=copy.deepcopy(state["last_attempt_by_store"].get(job["store_id"])),
                last_verified_success=copy.deepcopy(state["last_verified_success_by_store"].get(job["store_id"])))

    def dispatch_one(self):
        """Called only on request/child events, not a periodic poll."""
        with self._mutex:
            if self.process is not None or self.orphan_hold:return False
            state=self._state()
            job=next((job for job in state["jobs"] if job["state"]=="queued"),None)
            if job is None:return False
            auth_read,auth_write=os.pipe2(os.O_CLOEXEC)
            control_read,control_write=os.pipe2(os.O_CLOEXEC)
            try:
                identity=os.fstat(auth_read);nonce=os.urandom(32).hex()
                try:envelope=self.admission.envelope(job)
                except c.CoordinatorError:envelope=None
                job.update(state="claimed",claim_epoch=state["controller_epoch"],attempt_id=str(uuid.uuid4()),run_id=str(uuid.uuid4()),
                    updated_at=c.utc(),reason_code="claimed",auth_hash=hashlib.sha256(nonce.encode()).hexdigest(),
                    auth_device=identity.st_dev,auth_inode=identity.st_ino,resource_envelope=envelope)
                self._commit(state)  # Claim is durable before ANY spawn.
                plan=getattr(self.admission,"plan",None)
                payload=dict(job_id=job["job_id"],store_id=job["store_id"],claim_epoch=job["claim_epoch"],
                    attempt_id=job["attempt_id"],nonce=nonce,root=str(self.root),uid=self.uid,gate=asdict(self.gate_spec),
                    plan=asdict(plan) if plan is not None else None,cancel_fd=control_read)
                command=[sys.executable,"-m","app.db_audit_coordinator.worker",str(auth_read)]
                env={"PATH":"/usr/bin:/bin","PYTHONDONTWRITEBYTECODE":"1","TMPDIR":tempfile.gettempdir()}
                process=subprocess.Popen(command,cwd=Path(__file__).resolve().parents[2],env=env,
                    stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                    close_fds=True,pass_fds=(auth_read,control_read),shell=False)
                self.process,self.active,self.cancel_fd=process,job["job_id"],control_write
                control_write=None
                def wait_child():
                    code=process.wait()  # Reap, not PID/TTL inference; never writes queue.
                    self._reaped=(process,code)
                    try:self._wake_write.send(b"e")
                    except OSError:pass
                threading.Thread(target=wait_child,name="fixture_audit_reap",daemon=True).start()
                job.update(state="running",worker_pid=process.pid,reason_code="running",updated_at=c.utc())
                self._commit(state)
                raw=c.encode(payload,c.MAX_FRAME)
                if len(raw)>4096 or os.write(auth_write,raw)!=len(raw):raise c.CoordinatorError("coordinator_unavailable")
                return True
            except Exception:
                # A claim or a child may exist. Never erase it or auto-retry.
                self.orphan_hold=True
                raise
            finally:
                for descriptor in (auth_read,auth_write,control_read,control_write):
                    if descriptor is not None:os.close(descriptor)

    def finish(self):
        with self._mutex:
            if self.process is None:return False
            process=self.process
            if self._reaped is None or self._reaped[0] is not process:return False
            state=self._state();job=next(job for job in state["jobs"] if job["job_id"]==self.active)
            if not self.fence.released(job,process):
                self.orphan_hold=True
                if job["reason_code"]!="orphan_hold":job["reason_code"]="orphan_hold";self._commit(state)
                return False
            self._terminal(state,job,process.returncode,"worker_crashed")
            if self.cancel_fd is not None:os.close(self.cancel_fd);self.cancel_fd=None
            self.process=self.active=self._reaped=None;self.orphan_hold=False
            return True

    def _terminal(self,state,job,returncode,fallback):
        try:
            result=c.result(read_json(self.root/(job["job_id"]+".result.json"),self.uid))
            for key in ("job_id","store_id","run_id","attempt_id","claim_epoch","method_version","validator_version","source_generation"):
                if result[key]!=job[key]:raise ValueError()
            if returncode!=0 and result["result"]=="passed":raise ValueError()
            if job["method_version"]==c.FINGERPRINT_METHOD and result["result"] in {"passed","failed"}:
                from .fingerprint_adapter import verify_completed_result
                verify_completed_result(getattr(self.admission,"plan",None),job,result)
        except Exception:result=result_for(job,"incomplete",fallback)
        state_name="completed" if result["result"]=="passed" else "canceled" if result["reason_code"]=="canceled" else "deferred" if result["result"]=="incomplete" else "failed"
        job.update(state=state_name,audit_result=result,reason_code=result["reason_code"],updated_at=c.utc())
        state["last_attempt_by_store"][job["store_id"]]=copy.deepcopy(result)
        if result["result"]=="passed":state["last_verified_success_by_store"][job["store_id"]]=copy.deepcopy(result)
        self._commit(state)  # Next admission only AFTER durable terminal commit.

    def reconcile(self):
        with self._mutex:
            if self.process is not None:return self.finish()
            state=self._state()
            for job in state["jobs"]:
                if job["state"] in {"claimed","running"}:
                    if not self.fence.released(job,None):self.orphan_hold=True;return False
                    self._terminal(state,job,self.fence.exitcode(job,None),"restarted_after_claim")
            self.orphan_hold=False
            return True

    def cancel(self,job_id):
        """Internal G1 hook only; no new public socket cancel operation."""
        with self._mutex:
            state=self._state();job=next((job for job in state["jobs"] if job["job_id"]==job_id),None)
            if job is None:raise c.CoordinatorError("invalid_request")
            if job["state"]=="queued":job.update(state="canceled",reason_code="canceled",updated_at=c.utc());self._commit(state)
            elif job["state"] in {"claimed","running"}:
                job["reason_code"]="canceled";self._commit(state)
                if self.cancel_fd is not None:
                    try:os.write(self.cancel_fd,b"c")
                    except BrokenPipeError:pass
            return c.public_job(job)

    def handle(self,value,scope_hash):
        c.request(value)
        return self.submit(value["store_id"],value["idempotency_key"],value["origin"],scope_hash) if value["op"]=="submit" else self.status(value["job_id"],scope_hash)

    def serve(self,allowed_uids=frozenset(),ready=None):
        """One request per connection, bounded wait. Idle select has no timeout."""
        path=protected_parent(self.root/"coordinator.sock",self.uid)
        listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        selector=selectors.DefaultSelector();identity=None
        self._serving=True
        try:
            listener.bind(str(path));os.chmod(path,0o600);identity=path.lstat().st_ino
            listener.listen(8);selector.register(listener,selectors.EVENT_READ);selector.register(self._wake_read,selectors.EVENT_READ)
            if ready is not None:ready()
            self.dispatch_one()
            while not self._closed and not self._halted:
                for key,_events in selector.select():
                    if key.fileobj is listener:
                        connection,_address=listener.accept()
                        with connection:
                            try:reply=self.handle(receive_authorized(connection,allowed_uids),peer_scope(connection,allowed_uids))
                            except c.CoordinatorError as error:reply=dict(error=error.code)
                            except Exception:reply=dict(error="invalid_request")
                            try:send(connection,reply)
                            except OSError:pass
                    else:
                        self._wake_read.recv(1)
                        if self._closed:break
                        self.finish()
                if not self._closed and not self._halted:self.dispatch_one()
        finally:
            selector.close();listener.close()
            if identity is not None:
                try:
                    info=path.lstat()
                    if stat.S_ISSOCK(info.st_mode) and info.st_ino==identity:path.unlink()
                except FileNotFoundError:pass
            self.close()
            self._serving=False
            self._wake_read.close();self._wake_write.close()

    def close(self):
        with self._mutex:
            self._closed=True
            try:self._wake_write.send(b"x")
            except (OSError,AttributeError):pass
            # Closing the cancellation channel requests cleanup, not terminal
            # adoption. The live child alone still owns the heavy flock.
            if self.cancel_fd is not None:os.close(self.cancel_fd);self.cancel_fd=None
            self.owner.close()
            if not self._serving:
                self._wake_read.close();self._wake_write.close()


def receive_authorized(connection,allowed_uids):
    peer_scope(connection,allowed_uids)  # Reject invalid caller before parsing.
    return receive(connection)
