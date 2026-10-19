"""Disposable root -> unprivileged subprocess pilot, NOT cgroup admission evidence.

Only kernel cgroup reads/writes are substituted. Actual fork/exec, UID drop,
sealed one-time FDs, independent flock, SQLite backup/T3, fsync, pidfd/wait and
terminal queue ordering run for real. No /sys mutation or real database access.
"""
from dataclasses import asdict,replace
import copy
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import sqlite3
import sys
import subprocess
import tempfile
import time
import uuid

import pytest

from app.db_audit_coordinator import contracts as c
from app.db_audit_coordinator import live_coordinator as runtime
from app.db_audit_coordinator.live_policy import empty_state,make_result
from tests.db_audit_coordinator.test_b2_live_policy import profile,STORES
from tests.db_audit_coordinator.test_b2_live_sqlite import disposable,hashes

pytestmark=pytest.mark.skipif(sys.platform!='linux' or getattr(os,'geteuid',lambda:-1)()!=0,
    reason='Linux/POSIX disposable root-to-unprivileged subprocess and pidfd contract; no real cgroup writes')


class KernelDouble:
    """Explicit test double. It cannot attest any real memory hardcap."""
    def __init__(self,job,ledger):
        self.job,self.ledger=copy.deepcopy(job),ledger
        self.relative='/unit-fixture/job-'+job['attempt_id'];self.identity=(1,2)
    def write(self,name,value):self.ledger.append(('place' if name=='cgroup.procs' else name,self.job['job_id']))
    def contained(self,pid,cap,start):
        assert pid>0 and cap>0 and start>0
        self.ledger.append(('contained',self.job['job_id']))
    def empty(self):
        self.ledger.append(('empty',self.job['job_id']));return self.identity,time.monotonic_ns()
    def released(self,process,pidfd,start):
        from app.db_audit_coordinator.live_cgroup import Leaf
        return Leaf.released(self,process,pidfd,start)
    def close(self):pass


DRIVER=r'''
import os,sys,traceback
from dataclasses import replace
from app.db_audit_coordinator import child_bootstrap as worker
from tests.db_audit_coordinator.test_b2_live_policy import sample
class LocalKernelFixture:
    def __init__(self,*args,**kwargs):pass
    def contained(self,*args):pass
    def check(self):pass
    def samples(self):return sample().nodes
    def close(self):pass
worker.Leaf=LocalKernelFixture
worker.mountpoint=lambda:'/sys/fs/cgroup'
# The source worktree is deliberately not a root-owned installed Git release.
# Code bytes execute unchanged, but this test does NOT qualify live provenance.
worker.verify_origin=lambda profile:None
worker.guest_sample=lambda nodes:replace(sample(),captured_ns=__import__('time').monotonic_ns(),nodes=nodes)
original=worker.live_sqlite.audit
def controlled(policy,guard,admit):
    import fcntl
    from pathlib import Path
    # Opening a second file description must NOT acquire the held heavy flock.
    fd=os.open(sys.argv[2],os.O_RDONLY)
    try:
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:pass
        else:raise AssertionError('source access before independent child flock')
    finally:os.close(fd)
    def corrupt_ram_only(db):
        if policy.store_id==sys.argv[3]:db.execute('DROP TABLE service_materialization_runtime')
    try:return original(policy,guard,admit,after_backup=corrupt_ram_only)
    except Exception:
        traceback.print_exc();raise
worker.live_sqlite.audit=controlled
original_result=worker.make_result
def diagnostic_result(*args,**kwargs):
    if sys.exc_info()[0] is not None:traceback.print_exc()
    return original_result(*args,**kwargs)
worker.make_result=diagnostic_result
try:os._exit(worker.execute(int(sys.argv[1])))
except Exception:traceback.print_exc();os._exit(3)
'''


@pytest.fixture
def pilot(monkeypatch):
    # Explicitly disposable path; never root/profile installation locations.
    root=Path(tempfile.mkdtemp(prefix='qio226-b2-runtime-',dir='/tmp'))
    owner=Path(__file__).stat();worker_uid,worker_gid=owner.st_uid,owner.st_gid
    assert worker_uid!=0 and worker_gid!=0  # Never substitute privileged worker.
    os.chown(root,0,worker_gid);root.chmod(0o750)
    queue=root/'queue';queue.mkdir(mode=0o710);os.chown(queue,0,worker_gid)
    (queue/'queue-state.v1.json').write_bytes(c.encode(empty_state()));(queue/'queue-state.v1.json').chmod(0o600)
    for name,mode in (('coordinator.lock',0o600),('heavy.lock',0o640)):
        file=queue/name;file.touch(mode=mode);os.chown(file,0,worker_gid)
    writers=[];policies=[]
    for store in STORES:
        path=root/store;path.mkdir(mode=0o750);os.chown(path,0,worker_gid)
        writer,policy=disposable(path,store);writers.append(writer)
        for file in path.iterdir():os.chown(file,0,worker_gid);file.chmod(0o440)
        policies.append(replace(policy,gid=worker_gid))
    value=profile(enabled=True,root=str(queue),release_root=str(Path(__file__).resolve().parents[2]),
        python=sys.executable,worker_uid=worker_uid,worker_gid=worker_gid,worker_groups=(),stores=tuple(policies))
    monkeypatch.setattr(runtime.LiveCoordinator,'qualify',lambda self,profile:None)
    monkeypatch.setattr(type(value),'artifact',lambda self:None)
    ledger=[]
    monkeypatch.setattr(runtime,'create_leaf',lambda delegated,expected,job,cap,**kw:KernelDouble(job,ledger))
    monkeypatch.setattr(runtime.LiveCoordinator,'command',lambda self,fd:[sys.executable,'-B','-E','-s','-c',DRIVER,
        str(fd),str(queue/'heavy.lock'),'network_service_intelligence'])
    popen=runtime.subprocess.Popen
    diagnostic=open(root/'synthetic-child.log','wb')
    def captured(*args,**kwargs):
        kwargs['stderr']=diagnostic;return popen(*args,**kwargs)
    monkeypatch.setattr(runtime.subprocess,'Popen',captured)
    subject=runtime.LiveCoordinator(value)
    try:yield subject,ledger,policies
    finally:
        if subject.process is not None:
            subject._notify_cancel()
            try:subject.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Test-owned process only; not the production cancellation path.
                subject.process.kill();subject.process.wait(timeout=5)
        subject.close()
        diagnostic.close()
        for writer in writers:writer.close()
        assert str(root).startswith('/tmp/qio226-b2-runtime-')
        shutil.rmtree(root)


def batch(subject,scope=None):
    caller=c.scope(1002) if scope is None else scope
    items=[dict(store_id=store,idempotency_key=str(uuid.uuid4())) for store in STORES]
    return subject.submit_batch(items,caller),items


def complete(subject):
    assert select.select([subject._wake_read],[],[],10)[0]
    subject._wake_read.recv(1)
    assert subject.finish()


def test_three_durable_acks_A_pass_B_contained_domain_failure_C_pass(pilot):
    subject,ledger,policies=pilot;before=[hashes(policy.source) for policy in policies]
    replies,items=batch(subject)
    assert len(replies['jobs'])==3 and subject.process is None
    durable=subject.store.read();assert [j['state'] for j in durable['jobs']]==['queued']*3
    ids=[j['job']['job_id'] for j in replies['jobs']]
    for position,job_id in enumerate(ids):
        assert subject.dispatch_one() and subject.active==job_id
        if position:
            old=subject.store.read()['jobs'][position-1]
            assert old['state'] in {'completed','failed'},(subject.root.parent/'synthetic-child.log').read_text()
            assert ledger.count(('empty',ids[position-1]))==2
        complete(subject)
    finished=subject.store.read()
    assert [j['state'] for j in finished['jobs']]==['completed','failed','completed']
    assert [j['audit_result']['reason_code'] for j in finished['jobs']]==['audit_passed','audit_failed','audit_passed']
    assert all(j['audit_result']['fixture_only'] is False for j in finished['jobs'])
    assert all(ledger.count(('empty',job_id))==2 for job_id in ids)
    assert [hashes(policy.source) for policy in policies]==before
    assert set(finished['last_verified_success_by_store'])=={'public_traffic','traffic_projection'}
    assert not subject.dispatch_one()
    assert subject.submit(STORES[0],items[0]['idempotency_key'],'manual',c.scope(1002))['status']=='duplicate'
    with pytest.raises(c.CoordinatorError):subject.submit(STORES[0],str(uuid.uuid4()),'manual',c.scope(1002))


def test_no_spawn_until_third_durable_request(pilot):
    subject,_,_=pilot
    for store in STORES[:2]:
        subject.submit(store,str(uuid.uuid4()),'manual',c.scope(1002))
        assert not subject.dispatch_one() and subject.process is None
    subject.submit(STORES[2],str(uuid.uuid4()),'manual',c.scope(1002))
    assert subject.dispatch_one();complete(subject)


def test_uncertain_empty_fence_holds_C_and_does_not_adopt_success(pilot,monkeypatch):
    subject,ledger,_=pilot;batch(subject)
    assert subject.dispatch_one()
    monkeypatch.setattr(KernelDouble,'released',lambda *args:(_ for _ in ()).throw(c.CoordinatorError('orphan_hold')))
    assert select.select([subject._wake_read],[],[],10)[0];subject._wake_read.recv(1)
    assert not subject.finish() and subject.orphan_hold and not subject.dispatch_one()
    assert [job['state'] for job in subject.store.read()['jobs']]==['running','queued','queued']
    assert not subject.store.read()['last_verified_success_by_store']
    assert not any(event[1]==subject.store.read()['jobs'][2]['job_id'] for event in ledger)


def test_scoped_cancel_and_stop_reject_other_uid_stale_epoch_attempt(pilot):
    subject,_,_=pilot;replies,_=batch(subject);job=replies['jobs'][0]['job']
    epoch=subject.store.read()['controller_epoch'];before=subject.store.path.read_bytes()
    for args in ((job['job_id'],None,epoch,c.scope(9999)),
            (job['job_id'],str(uuid.uuid4()),epoch,c.scope(1002)),
            (job['job_id'],None,str(uuid.uuid4()),c.scope(1002))):
        with pytest.raises(c.CoordinatorError):subject.cancel_scoped(*args)
    with pytest.raises(c.CoordinatorError):subject.stop_scoped(epoch,c.scope(9999))
    assert subject.store.path.read_bytes()==before
    assert subject.stop_scoped(epoch,c.scope(1002))['status']=='stopped'
    assert not subject.dispatch_one()
    assert [j['state'] for j in subject.store.read()['jobs']]==['canceled']*3


def test_restart_with_pending_has_no_automatic_batch_or_replay(pilot):
    subject,_,_=pilot;batch(subject);value=subject.profile
    subject.close()
    second=runtime.LiveCoordinator(value)
    try:
        assert second._inherited_pending and not second.dispatch_one()
        with pytest.raises(c.CoordinatorError):second.submit(STORES[0],str(uuid.uuid4()),'manual',c.scope(1002))
    finally:second.close()


def test_lost_supervisor_receipt_after_real_child_exit_is_orphan_not_C(pilot):
    subject,ledger,_=pilot;batch(subject);assert subject.dispatch_one()
    value=subject.profile;subject.close()
    subject.process.wait(timeout=10)
    second=runtime.LiveCoordinator(value)
    try:
        assert second.orphan_hold and not second.reconcile() and not second.dispatch_one()
        jobs=second.store.read()['jobs']
        assert [j['state'] for j in jobs]==['running','queued','queued']
        assert jobs[0]['reason_code']=='orphan_hold'
        assert not second.store.read()['last_verified_success_by_store']
        assert not any(event[1]==jobs[2]['job_id'] for event in ledger)
    finally:second.close()


def test_busy_global_flock_never_reads_or_passes_source(pilot):
    import fcntl
    subject,_,policies=pilot;before=[hashes(policy.source) for policy in policies];batch(subject)
    fd=os.open(subject.root/'heavy.lock',os.O_RDONLY)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        assert subject.dispatch_one();complete(subject)
        job=subject.store.read()['jobs'][0]
        assert job['audit_result']['result']=='incomplete' and job['reason_code']=='gate_busy'
        assert [hashes(policy.source) for policy in policies]==before
    finally:os.close(fd)


def test_actual_supervisor_sigkill_loses_receipts_and_must_not_start_C(pilot):
    subject,_,_=pilot;value=subject.profile;subject.close()
    script=r'''
import json,os,signal,sys
from app.db_audit_coordinator import live_coordinator as runtime
from app.db_audit_coordinator.live_profile import PilotProfile
from tests.db_audit_coordinator.test_b2_live_runtime import KernelDouble,DRIVER,batch
value=PilotProfile.parse(json.loads(sys.argv[1]))
runtime.LiveCoordinator.qualify=lambda self,profile:None
PilotProfile.artifact=lambda self:None
runtime.create_leaf=lambda delegated,expected,job,cap,**kw:KernelDouble(job,[])
held=DRIVER.replace('    def corrupt_ram_only(db):',
    '    for _ in range(1000):\n        guard();__import__("time").sleep(.01)\n    def corrupt_ram_only(db):')
runtime.LiveCoordinator.command=lambda self,fd:[sys.executable,'-B','-E','-s','-c',held,str(fd),
    str(self.root/'heavy.lock'),'network_service_intelligence']
subject=runtime.LiveCoordinator(value);batch(subject);subject.dispatch_one()
print(json.dumps({'worker':subject.process.pid}),flush=True)
while True:signal.pause()
'''
    supervisor=subprocess.Popen([sys.executable,'-B','-E','-s','-c',script,json.dumps(asdict(value))],
        cwd=value.release_root,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    pidfd=None
    try:
        assert select.select([supervisor.stdout],[],[],10)[0]
        line=supervisor.stdout.readline();assert line,supervisor.stderr.read()
        worker=json.loads(line)['worker'];pidfd=os.pidfd_open(worker,0)
        supervisor.kill();assert supervisor.wait(timeout=5)<0  # Exact test-owned supervisor only.
        poll=select.poll();poll.register(pidfd,select.POLLIN);assert poll.poll(10000)
        # Kernel exit alone does NOT transfer the lost supervisor's wait receipt.
        second=runtime.LiveCoordinator(value)
        try:
            assert second.orphan_hold and not second.reconcile() and not second.dispatch_one()
            assert [j['state'] for j in second.store.read()['jobs']]==['running','queued','queued']
        finally:second.close()
    finally:
        if supervisor.poll() is None:supervisor.kill();supervisor.wait(timeout=5)
        if pidfd is not None:os.close(pidfd)


def test_129_rejects_without_write_but_existing_key_still_resolves(pilot):
    subject,_,_=pilot;key=str(uuid.uuid4());first=subject.submit(STORES[0],key,'manual',c.scope(1002))
    current=subject.store.read();template=current['jobs'][0];template['state']='canceled';template['reason_code']='canceled'
    for seq in range(2,129):
        job=copy.deepcopy(template);job.update(job_id=str(uuid.uuid4()),idempotency_hash=hashlib.sha256(str(seq).encode()).hexdigest(),seq=seq)
        current['jobs'].append(job)
    current['next_sequence']=129;subject.store.commit(current)
    before=subject.store.path.read_bytes()
    with pytest.raises(c.CoordinatorError,match='queue_full'):subject.submit(STORES[1],str(uuid.uuid4()),'manual',c.scope(1002))
    assert subject.submit(STORES[0],key,'manual',c.scope(1002))['status']=='duplicate'
    assert subject.store.path.read_bytes()==before
    assert subject.status(first['job']['job_id'],c.scope(1002))['job']['state']=='canceled'


def test_sealed_private_snapshot_cannot_be_modified_or_inject_queue_authority():
    from app.db_audit_coordinator.child_bootstrap import readonly_document,main
    fd=runtime.memory_document({'not':'queue-authority'})
    try:
        assert readonly_document(fd,sealed=True)=={'not':'queue-authority'}
        with pytest.raises(OSError):os.write(fd,b'x')
    finally:os.close(fd)
    assert main([])==2


def test_claim_is_durable_before_spawn_failure_and_remains_hold(pilot,monkeypatch):
    subject,_,_=pilot;batch(subject)
    def denied(*args,**kwargs):
        assert subject.store.read()['jobs'][0]['state']=='claimed'
        raise OSError('synthetic spawn denial')
    monkeypatch.setattr(runtime.subprocess,'Popen',denied)
    with pytest.raises(OSError):subject.dispatch_one()
    assert subject.orphan_hold and not subject.dispatch_one()
    assert subject.store.read()['jobs'][0]['state']=='claimed'
