"""One attended three-store pilot. No provisioning, scheduler or restart replay.

The supervisor is the sole durable writer. The unprivileged blocked child gets
sealed copies, independently opens the heavy lock, and never writes queue files.
Only the main event loop adopts a reaped result, AFTER the exact empty-leaf fence.
"""
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
import threading
import time
import uuid

from . import contracts as c
from .coordinator import Coordinator,receive_authorized
from .locks import LockSpec,protected_parent
from .state_store import StateStore
from .protocol import peer_scope,receive,send
from .live_policy import state,make_result,result,require,integer,VALIDATORS
from .live_receipts import directory,filesystem_magic,identity,start_ticks
from .live_cgroup import create_leaf


class OperationalStateStore(StateStore):
    validate=staticmethod(state)
    # Root-only JSON/owner lock, group traversal solely to open heavy.lock.
    # No group write/read-directory permission. Fixture defaults stay 0700.
    parent_access=0o010


class OperationalFilesystem:
    def validate(self,root,uid):
        fd=directory(str(root),uid=uid)
        try:
            info=os.fstat(fd)
            require(uid==0 and info.st_uid==0 and stat.S_IMODE(info.st_mode)==0o710)
            require(filesystem_magic(fd)==0xEF53)  # Qualified local ext4, not tmpfs/NFS/overlay.
        finally:os.close(fd)


class LiveAdmission:
    def __init__(self,profile):self.profile=profile
    def metadata(self,store):return self.profile.metadata(store)


def memory_document(value, *, seal=True):
    import fcntl
    fd=os.memfd_create('audit-private',os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING)
    try:
        if value is not None:fill_document(fd,value,seal=seal)
        return fd
    except Exception:os.close(fd);raise


def fill_document(fd,value, *, seal=True):
    import fcntl
    raw=c.encode(value);offset=0
    require(os.fstat(fd).st_size==0)
    while offset<len(raw):
        n=os.write(fd,raw[offset:]);require(n>0);offset+=n
    os.lseek(fd,0,os.SEEK_SET)
    if seal:
        fcntl.fcntl(fd,fcntl.F_ADD_SEALS,fcntl.F_SEAL_WRITE|fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_SEAL)


class LiveCoordinator(Coordinator):
    store_type=OperationalStateStore
    diagnostic_stage='serve'
    _r4=None

    def qualify(self,profile):profile.installed()

    def __init__(self,profile, *, sync=os.fsync):
        self.qualify(profile)
        self.profile=profile
        root=Path(profile.root)
        require(root.lstat().st_gid==profile.worker_gid,'unsafe_path')
        def spec(name,mode):
            target=root/name;protected_parent(target,0);info=target.lstat()
            require(stat.S_ISREG(info.st_mode) and info.st_uid==0 and info.st_nlink==1
                and stat.S_IMODE(info.st_mode)==mode,'unsafe_path')
            if mode==0o640:require(info.st_gid==profile.worker_gid,'unsafe_path')
            return LockSpec(str(target),0,info.st_dev,info.st_ino)
        self._batch_scope=None;self._submitted=[];self._batch=();self._stopped=False
        self._leaf=None;self._pidfd=None;self._start=None;self._result_fd=None
        self._deadline=None;self._abort_at=None;self._killed=False
        self._r4=None;self.r4_proofs=[]
        super().__init__(root,spec('coordinator.lock',0o600),spec('heavy.lock',0o640),
            admission=LiveAdmission(profile),filesystem=OperationalFilesystem(),sync=sync)
        # No approval survives restart, even for merely queued work. Operators
        # must review/close old jobs; this daemon cannot auto-reset or adopt them.
        self._inherited_pending=any(job['state'] in c.OUTSTANDING for job in self.store.read()['jobs'])

    def submit(self,store_id,key,origin,scope_hash):
        require(origin=='manual','invalid_request');self.profile.store(store_id)
        with self._mutex:
            current=self._state()
            hashed=hashlib.sha256((store_id+':'+c.idempotency(scope_hash,key)).encode()).hexdigest()
            old=next((job for job in current['jobs'] if job['idempotency_hash']==hashed),None)
            if old:return dict(status='duplicate',job=c.public_job(old))
            # Duplicate-first, including after saturation/STOP. No write on #129.
            require(len(current['jobs'])<c.MAX_HISTORY,'queue_full')
            require(not self._inherited_pending and not self._stopped and len(self._submitted)<3
                and self._batch_scope in {None,scope_hash},'not_admitted')
            reply=super().submit(store_id,key,origin,scope_hash)
            self._batch_scope=scope_hash;self._submitted.append(reply['job']['job_id'])
            if len(self._submitted)==3:self._batch=tuple(self._submitted)
            return reply

    def submit_batch(self,items,scope_hash):
        require(type(items) is list and len(items)==3,'invalid_request')
        for item in items:
            c.closed(item,{'store_id','idempotency_key'});self.profile.store(item['store_id']);c.identifier(item['idempotency_key'])
        require(len({item['store_id'] for item in items})==3,'invalid_request')
        c.digest(scope_hash)
        c.encode(dict(op='submit_batch',items=items),c.MAX_FRAME)
        with self._mutex:
            # No execution can start while this handler is durably appending all
            # three requests. A partial fsync error returns NO batch ACK and halts.
            replies=[]
            try:
                for item in items:
                    replies.append(self.submit(item['store_id'],item['idempotency_key'],'manual',scope_hash))
                reply=dict(status='batch',jobs=replies)
                c.encode(reply,c.MAX_FRAME)  # Detect response failure at the acceptance boundary.
                return reply
            except Exception as error:
                if not replies and isinstance(error,c.CoordinatorError) and error.code in {
                        'invalid_request','store_busy','queue_full','not_admitted','unauthorized'}:
                    raise  # Known pre-publication rejection of the first item.
                # 1/2/3 durable records OR an unknown fsync may already exist.
                raise c.CoordinatorError('coordinator_unavailable') from None

    def status_by_key(self,store_id,key,scope_hash):
        require(type(store_id) is str and store_id in VALIDATORS,'invalid_request')
        c.identifier(key);c.digest(scope_hash)
        hashed=hashlib.sha256((store_id+':'+c.idempotency(scope_hash,key)).encode()).hexdigest()
        with self._mutex:
            job=next((job for job in self._state()['jobs'] if job['idempotency_hash']==hashed
                and job['scope_hash']==scope_hash and job['store_id']==store_id),None)
            if job is None:return dict(status='not_found',outcome='outcome_unresolved')
            return dict(status='found',job=c.public_job(job))

    def command(self,auth_fd):
        return [self.profile.python,'-B','-E','-s','-m','app.db_audit_coordinator.child_bootstrap',str(auth_fd)]

    def _watch(self,process):
        def reap():
            code=process.wait()  # Sole waiter; no durable writes in this thread.
            self._reaped=(process,code)
            try:self._wake_write.send(b'e')
            except OSError:pass
        threading.Thread(target=reap,name='audit_child_reap',daemon=True).start()

    def dispatch_one(self):
        with self._mutex:
            if self.process is not None or self.orphan_hold or self._stopped or not self._batch:return False
            current=self._state()
            job=next((job for job in current['jobs'] if job['job_id'] in self._batch and job['state']=='queued'),None)
            if job is None:return False
            # Parent verifies only immutable CODE, not source geometry/SQLite.
            self.profile.artifact();policy=self.profile.store(job['store_id'])
            from .live_policy import R4_METHOD
            if job['method_version']==R4_METHOD:
                from .r4_release import Session
                self._r4=Session(self,job,current)
                self._r4.start()
                return True
            ar,aw=os.pipe2(os.O_CLOEXEC);cr,cw=os.pipe2(os.O_CLOEXEC);rr,rw=os.pipe2(os.O_CLOEXEC)
            claim=profile_fd=None
            try:
                nonce=os.urandom(32).hex();pipe=os.fstat(ar);started=time.monotonic_ns()
                job.update(state='claimed',claim_epoch=current['controller_epoch'],attempt_id=str(uuid.uuid4()),
                    run_id=str(uuid.uuid4()),updated_at=c.utc(),reason_code='claimed',
                    auth_hash=hashlib.sha256(nonce.encode()).hexdigest(),auth_device=pipe.st_dev,auth_inode=pipe.st_ino,
                    resource_envelope=dict(fixture_only=False,memory_limit_bytes=policy.memory_max_bytes,
                        timeout_seconds=policy.attempt_seconds))
                self.diagnostic_stage='claim_publish'
                self._commit(current)  # MUST precede create/spawn/release.
                self.diagnostic_stage='post_claim_leaf_attestation'
                self._leaf=create_leaf(self.profile.delegated,
                    (self.profile.delegated_device,self.profile.delegated_inode),job,policy.memory_max_bytes,
                    worker_gid=self.profile.worker_gid)
                claim=memory_document(None);profile_fd=memory_document(asdict(self.profile))
                self.diagnostic_stage='child_spawn'
                child=subprocess.Popen(self.command(ar),cwd=self.profile.release_root,
                    env={'PATH':'/usr/bin:/bin','HOME':'/nonexistent','LANG':'C.UTF-8'},
                    stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                    close_fds=True,pass_fds=(ar,cr,rw,claim,profile_fd),shell=False,
                    user=self.profile.worker_uid,group=self.profile.worker_gid,extra_groups=self.profile.worker_groups)
                self.process,self.active,self.cancel_fd,self._result_fd=child,job['job_id'],cw,rr
                cw=rr=None
                self._watch(child)
                self._pidfd=os.pidfd_open(child.pid,0);self._start=start_ticks(child.pid)
                self._leaf.write('cgroup.procs',str(child.pid))
                self.diagnostic_stage='child_containment'
                self._leaf.contained(child.pid,policy.memory_max_bytes,self._start)
                job.update(state='running',worker_pid=child.pid,reason_code='running',updated_at=c.utc())
                self.diagnostic_stage='running_publish'
                self._commit(current)
                # Copy only the exact queue just read back after durable commit.
                fill_document(claim,self.store.read())
                payload=dict(job_id=job['job_id'],attempt_id=job['attempt_id'],claim_epoch=job['claim_epoch'],nonce=nonce,
                    claim_fd=claim,profile_fd=profile_fd,result_fd=rw,cancel_fd=cr,
                    supervisor_pid=os.getpid(),supervisor_start=start_ticks(os.getpid()),
                    leaf=self._leaf.relative,leaf_device=self._leaf.identity[0],leaf_inode=self._leaf.identity[1],
                    gate_device=self.gate_spec.device,gate_inode=self.gate_spec.inode,started_ns=started)
                raw=c.encode(payload,4096)
                self.diagnostic_stage='child_release'
                require(os.write(aw,raw)==len(raw))
                self._deadline=started/1e9+policy.attempt_seconds
                self.diagnostic_stage='serve'
                return True
            except Exception:
                self.orphan_hold=True
                # The blocked worker receives EOF, never a partial permission to
                # run. Even an apparently dead process needs the positive fence.
                raise
            finally:
                for fd in (ar,aw,cr,cw,rr,rw,claim,profile_fd):
                    if fd is not None:os.close(fd)

    def _notify_cancel(self):
        if self._r4 is not None:
            self._r4.cancel();return
        if self.cancel_fd is not None:
            try:os.write(self.cancel_fd,b'c')
            except BrokenPipeError:pass
        if self.process is not None and self._abort_at is None:self._abort_at=time.monotonic()+2

    def cancel_scoped(self,job_id,attempt,epoch,scope_hash):
        c.identifier(job_id);c.identifier(epoch)
        if attempt is not None:c.identifier(attempt)
        with self._mutex:
            current=self._state()
            job=next((j for j in current['jobs'] if j['job_id']==job_id and j['scope_hash']==scope_hash),None)
            require(job is not None and epoch==current['controller_epoch']
                and job['attempt_id']==attempt,'unauthorized')
            if job['state']=='queued':
                job.update(state='canceled',reason_code='canceled',updated_at=c.utc());self._commit(current)
            elif job['state'] in {'claimed','running'}:
                require(self.active==job_id and self.process is not None,'orphan_hold')
                self._notify_cancel()  # Do not change truth to terminal before reap.
            return dict(status='cancel_requested',job=c.public_job(job))

    def stop_scoped(self,epoch,scope_hash):
        with self._mutex:
            current=self._state();c.identifier(epoch)
            require(epoch==current['controller_epoch'] and scope_hash==self._batch_scope,'unauthorized')
            self._stopped=True
            for job in list(current['jobs']):
                if job['job_id'] in self._submitted and job['state'] in c.OUTSTANDING:
                    self.cancel_scoped(job['job_id'],job['attempt_id'],epoch,scope_hash)
            return dict(status='stopped',controller_epoch=epoch)

    def timeout(self):
        if self._r4 is not None:
            return None if self._r4.kill_sent else max(0,(self._r4.deadline-time.monotonic_ns())/1e9)
        if self.process is None:return None  # Idle selector blocks indefinitely.
        target=self._abort_at if self._abort_at is not None else self._deadline
        return None if target is None or self._killed else max(0,target-time.monotonic())

    def expire(self):
        if self._r4 is not None:
            self._r4.expire();return
        if self.process is None or self.process.returncode is not None:return
        now=time.monotonic()
        if self._abort_at is None and self._deadline is not None and now>=self._deadline:self._notify_cancel()
        if self._abort_at is not None and now>=self._abort_at and not self._killed:
            self._leaf.write('cgroup.kill','1');self._killed=True
            # No arbitrary PID signal; no claim until exact wait/empty proof.

    def finish(self):
        with self._mutex:
            if self._r4 is not None:
                if not self._r4.pump():return False
                self.r4_proofs.append(self._r4.proof)
                self._r4=None
                return True
            if self.process is None or self._reaped is None or self._reaped[0] is not self.process:return False
            current=self._state();job=next(j for j in current['jobs'] if j['job_id']==self.active)
            try:
                require(self._leaf is not None and self._pidfd is not None)
                self._leaf.released(self.process,self._pidfd,self._start)
            except Exception:
                self.orphan_hold=True
                if job['reason_code']!='orphan_hold':job['reason_code']='orphan_hold';self._commit(current)
                return False
            try:
                os.set_blocking(self._result_fd,False)
                raw=os.read(self._result_fd,4097);require(0<len(raw)<=4096)
                require(os.read(self._result_fd,1)==b'')
                output=result(c.decode(raw,4096))
                require(all(output[k]==job[k] for k in ('job_id','store_id','run_id','attempt_id','claim_epoch',
                    'method_version','validator_version','source_generation')))
                require(self.process.returncode==0 or output['result']!='passed')
            except Exception:output=make_result(job,'incomplete','worker_crashed')
            if output['result']=='passed' and (self._deadline is None or time.monotonic()>=self._deadline):
                output=make_result(job,'incomplete','timeout')
            status='completed' if output['result']=='passed' else 'failed' if output['result']=='failed' else 'canceled' if output['reason_code']=='canceled' else 'deferred'
            job.update(state=status,audit_result=output,reason_code=output['reason_code'],updated_at=c.utc())
            current['last_attempt_by_store'][job['store_id']]=copy.deepcopy(output)
            if output['result']=='passed':current['last_verified_success_by_store'][job['store_id']]=copy.deepcopy(output)
            self._commit(current)  # Positive release, then terminal fsync, THEN C.
            for fd in (self.cancel_fd,self._pidfd,self._result_fd):
                if fd is not None:os.close(fd)
            self._leaf.close();self._leaf=None
            self.cancel_fd=self._pidfd=self._result_fd=None
            self.process=self.active=self._reaped=self._deadline=self._abort_at=None
            self._killed=False;self.orphan_hold=False
            return True

    def reconcile(self):
        # Missing live Popen/pidfd is never repaired by PID absence/TTL/status.
        if self.process is not None:return self.finish()
        with self._mutex:
            if any(j['state'] in {'claimed','running'} for j in self._state()['jobs']):
                self.orphan_hold=True;return False
            return not self.orphan_hold

    def close(self):
        # Shutdown is not a positive release receipt. No terminal fabrication,
        # mount detach or next FIFO while an R4 owner may still be alive.
        if self._r4 is not None and not self._r4.done:
            self._r4.hold();self._r4.cancel()
        super().close()

    def handle(self,value,scope_hash):
        require(type(value) is dict,'invalid_request');op=value.get('op')
        if op=='submit_batch':
            c.closed(value,{'op','items'});return self.submit_batch(value['items'],scope_hash)
        if op=='submit':
            c.request(value);return self.submit(value['store_id'],value['idempotency_key'],value['origin'],scope_hash)
        if op=='status':c.request(value);return self.status(value['job_id'],scope_hash)
        if op=='status_by_key':
            c.closed(value,{'op','store_id','idempotency_key'})
            return self.status_by_key(value['store_id'],value['idempotency_key'],scope_hash)
        if op=='cancel':
            c.closed(value,{'op','job_id','attempt_id','controller_epoch'})
            return self.cancel_scoped(value['job_id'],value['attempt_id'],value['controller_epoch'],scope_hash)
        if op=='stop':
            c.closed(value,{'op','controller_epoch'});return self.stop_scoped(value['controller_epoch'],scope_hash)
        raise c.CoordinatorError('invalid_request')

    def serve(self):
        path=Path(self.profile.socket);fd=directory(str(path.parent),uid=0)
        try:
            info=os.fstat(fd);require(info.st_uid==0 and info.st_gid==self.profile.operator_gid
                and stat.S_IMODE(info.st_mode)==0o750,'unsafe_path')
        finally:os.close(fd)
        listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);selector=selectors.DefaultSelector();stamp=None
        self._serving=True
        try:
            listener.bind(str(path));os.chown(path,0,self.profile.operator_gid);os.chmod(path,0o660)
            stamp=identity(path.lstat());listener.listen(8)
            selector.register(listener,selectors.EVENT_READ);selector.register(self._wake_read,selectors.EVENT_READ)
            while not self._closed and not self._halted:
                for key,_ in selector.select(self.timeout()):
                    if key.fileobj is listener:
                        connection,_=listener.accept()
                        with connection:
                            try:
                                caller=peer_scope(connection,set(self.profile.operator_uids))
                                reply=self.handle(receive(connection),caller)
                            except c.CoordinatorError as error:reply=dict(error=error.code)
                            except Exception:reply=dict(error='coordinator_unavailable')
                            try:send(connection,reply)  # All batch ACKs after durable fsync, before dispatch.
                            except (OSError,c.CoordinatorError):pass  # Lost reply never erases durable acceptance.
                    else:self._wake_read.recv(1)
                self.expire();self.finish()
                if not self._closed and not self._halted:self.dispatch_one()
        finally:
            selector.close();listener.close()
            if stamp is not None:
                try:
                    info=path.lstat()
                    if stat.S_ISSOCK(info.st_mode) and identity(info)==stamp:path.unlink()
                except FileNotFoundError:pass
            self.close();self._serving=False
            self._wake_read.close();self._wake_write.close()
