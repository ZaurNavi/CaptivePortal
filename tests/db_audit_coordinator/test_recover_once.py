"""Disposable exact old-epoch fixtures only; never the installed queue."""
import copy
import hashlib
import os
from pathlib import Path
import shutil
import sys
import tempfile
import uuid

import pytest

from app.db_audit_coordinator import contracts as c, live_policy as p
from app.db_audit_coordinator import recover_once as r

BOOT='00000000-0000-0000-0000-000000000001'
NOW=100_000_000_000
native=pytest.mark.skipif(sys.platform!='linux' or getattr(os,'geteuid',lambda:-1)()!=0,
    reason='Linux/POSIX disposable root-owned recovery and permanent flock contract')


def old_queue():
    value=p.empty_state();value['controller_epoch']=r.EPOCH;value['next_sequence']=4
    for seq,store in enumerate(r.STORES,1):
        job=dict(job_id=r.JOB if seq==1 else str(uuid.uuid5(uuid.NAMESPACE_URL,store)),seq=seq,
            store_id=store,scope_hash='1'*64,idempotency_hash=str(seq)*64,origin='manual',
            state='claimed' if seq==1 else 'queued',claim_epoch=r.EPOCH if seq==1 else None,
            attempt_id=r.ATTEMPT if seq==1 else None,run_id=BOOT if seq==1 else None,
            created_at='2026-10-19T15:40:09.602Z',updated_at='2026-10-19T15:40:09.602Z',
            reason_code='claimed' if seq==1 else 'accepted',method_version=p.METHOD,
            validator_version=p.VALIDATORS[store],source_generation=BOOT,
            resource_envelope=dict(fixture_only=False,memory_limit_bytes=2**30,timeout_seconds=300) if seq==1 else None,
            auth_hash='3'*64 if seq==1 else None,auth_device=1 if seq==1 else None,
            auth_inode=2 if seq==1 else None,worker_pid=None,audit_result=None)
        value['jobs'].append(job)
    return p.state(value)


def receipt(raw=None):
    raw=c.encode(old_queue()) if raw is None else raw
    return dict(schema='db_audit_coordinator.abandon.old_epoch.v1',epoch=r.EPOCH,job_id=r.JOB,
        attempt_id=r.ATTEMPT,queue_identity=[1,2],queue_sha256=hashlib.sha256(raw).hexdigest(),
        queue_bytes=len(raw),owner_identity=[1,3],heavy_identity=[1,4],boot_id=BOOT,service=r.SERVICE,
        observations=[dict(captured_ns=NOW-2+i,evidence_sha256=hashlib.sha256(f'observation {i}'.encode()).hexdigest(),
            main_pid=0,checks={key:True for key in r.CHECKS}) for i in range(2)])


def test_exact_administrative_abandonment_preserves_all_ack_history():
    before=old_queue();unchanged=copy.deepcopy(before);after=r.abandon(before)
    assert before==unchanged
    assert p.state(after)==after and after['controller_epoch']==r.EPOCH and after['next_sequence']==4
    assert after['last_verified_success_by_store']=={}
    assert len(after['jobs'])==3
    allowed={'state','reason_code','updated_at','audit_result'}
    for old,new in zip(before['jobs'],after['jobs']):
        assert {k:v for k,v in old.items() if k not in allowed}=={k:v for k,v in new.items() if k not in allowed}
    a,b,cancel=after['jobs']
    assert a['state']=='deferred' and a['audit_result']['result']=='incomplete'
    assert a['audit_result']['reason_code']=='restarted_after_claim'
    assert a['audit_result']['snapshot_id'] is None and a['worker_pid'] is None
    assert after['last_attempt_by_store']=={'public_traffic':a['audit_result']}
    for job in (b,cancel):
        assert job['state']=='canceled' and job['reason_code']=='canceled'
        assert job['audit_result'] is job['attempt_id'] is job['worker_pid'] is None
    with pytest.raises(c.CoordinatorError):r.abandon(after)


@pytest.mark.parametrize('change',['epoch','job','attempt','running','worker','b_claimed','b_wrong_store',
    'sequence','history','success','schema','unknown'])
def test_not_exact_old_queue_never_becomes_terminal(change):
    value=old_queue();first=value['jobs'][0]
    if change=='epoch':value['controller_epoch']=BOOT
    elif change=='job':first['job_id']=BOOT
    elif change=='attempt':first['attempt_id']=BOOT
    elif change=='running':first.update(state='running',worker_pid=99)
    elif change=='worker':first['worker_pid']=99
    elif change=='b_claimed':value['jobs'][1]['state']='claimed'
    elif change=='b_wrong_store':value['jobs'][1]['store_id']='fingerprint_evidence'
    elif change=='sequence':value['next_sequence']=5
    elif change=='history':value['jobs'].pop()
    elif change=='success':value['last_verified_success_by_store']={'public_traffic':{}}
    elif change=='schema':value['schema_version']=c.SCHEMA
    else:value['extra']=True
    before=copy.deepcopy(value)
    with pytest.raises(Exception):r.abandon(value)
    assert value==before


def test_closed_two_distinct_fresh_operator_observations():
    value=receipt();assert r.attestation(value,now_ns=NOW,boot_id=BOOT) is value


@pytest.mark.parametrize('check',sorted(r.CHECKS))
def test_any_unknown_current_nonexistence_or_launch_fence_is_hold(check):
    value=receipt();value['observations'][1]['checks'][check]=False
    with pytest.raises(c.CoordinatorError):r.attestation(value,now_ns=NOW,boot_id=BOOT)


@pytest.mark.parametrize('change',['missing','same','stale','future','boot','unit','epoch','pid',
    'bool_pid','unknown_check','unknown_top','bad_hash','same_evidence','bool_check','same_locks'])
def test_untrusted_or_incomplete_receipt_is_not_admission(change):
    value=receipt();one,two=value['observations']
    if change=='missing':value['observations'].pop()
    elif change=='same':two['captured_ns']=one['captured_ns']
    elif change=='stale':one['captured_ns']=0
    elif change=='future':two['captured_ns']=NOW+1
    elif change=='boot':value['boot_id']=r.EPOCH
    elif change=='unit':value['service']='other.service'
    elif change=='epoch':value['epoch']=BOOT
    elif change=='pid':two['main_pid']=123
    elif change=='bool_pid':two['main_pid']=False
    elif change=='unknown_check':two['checks']['assume_reaped']=True
    elif change=='unknown_top':value['assume_pass']=True
    elif change=='bad_hash':value['queue_sha256']='bad'
    elif change=='same_evidence':two['evidence_sha256']=one['evidence_sha256']
    elif change=='bool_check':two['checks'][next(iter(r.CHECKS))]=1
    else:value['heavy_identity']=value['owner_identity']
    with pytest.raises(c.CoordinatorError):r.attestation(value,now_ns=NOW,boot_id=BOOT)


def test_cli_has_no_path_reset_force_or_socket_override():
    for args in ([],['reset'],['recover'],['abandon-old-epoch','--force'],['--root','/tmp/other']):
        assert r.main(args)==2


def test_cli_nonroot_denial_has_only_sanitized_hold(monkeypatch,capsys):
    monkeypatch.setattr(r.os,'geteuid',lambda:1000,raising=False)
    monkeypatch.setattr(r,'_recover',lambda *a,**kw:pytest.fail('must not open queue'))
    assert r.main(['abandon-old-epoch'])==3
    assert capsys.readouterr().err=='db_audit_coordinator stage=operator_abandonment reason_code=orphan_hold\n'


@pytest.fixture
def disposable():
    root=Path(tempfile.mkdtemp(prefix='qio226-recovery-',dir='/tmp'))
    queue=root/'queue';queue.mkdir(mode=0o710)
    evidence=root/'evidence';evidence.mkdir(mode=0o700)
    raw=c.encode(old_queue());(queue/'queue-state.v1.json').write_bytes(raw)
    for name,mode in (('queue-state.v1.json',0o600),('coordinator.lock',0o600),('heavy.lock',0o640)):
        path=queue/name
        if not path.exists():path.touch()
        path.chmod(mode)
    value=receipt(raw)
    for key,name in (('queue_identity','queue-state.v1.json'),('owner_identity','coordinator.lock'),('heavy_identity','heavy.lock')):
        info=(queue/name).lstat();value[key]=[info.st_dev,info.st_ino]
    def save():
        (evidence/r.RECEIPT).write_bytes(c.encode(value));(evidence/r.RECEIPT).chmod(0o600)
    save()
    for i in range(2):
        target=evidence/f'observation-{i+1}.txt';target.write_bytes(f'observation {i}'.encode());target.chmod(0o400)
    try:yield queue,evidence,value,save
    finally:
        assert root.parent==Path('/tmp') and root.name.startswith('qio226-recovery-')
        shutil.rmtree(root)


def run_fixture(disposable):
    queue,evidence,_,_=disposable
    return r._recover(queue,evidence,boot_id=BOOT,now=lambda:NOW)


@native
def test_atomic_disposable_recovery_evidence_lock_inodes_and_repeat(disposable):
    queue,evidence,value,_=disposable
    before=(queue/'queue-state.v1.json').read_bytes()
    assert run_fixture(disposable)=='administratively_abandoned_unverified'
    after=p.state(c.decode((queue/'queue-state.v1.json').read_bytes()))
    assert after['jobs'][0]['audit_result']['reason_code']=='restarted_after_claim'
    assert [job['state'] for job in after['jobs']]==['deferred','canceled','canceled']
    assert (evidence/r.BACKUP).read_bytes()==before
    assert stat_mode(evidence/r.BACKUP)==0o400
    for key,name in (('owner_identity','coordinator.lock'),('heavy_identity','heavy.lock')):
        info=(queue/name).lstat();assert [info.st_dev,info.st_ino]==value[key]
    fingerprint={f.name:(f.stat().st_ino,f.read_bytes()) for f in evidence.iterdir()}
    published=(queue/'queue-state.v1.json').read_bytes()
    with pytest.raises(c.CoordinatorError):run_fixture(disposable)
    assert (queue/'queue-state.v1.json').read_bytes()==published
    assert {f.name:(f.stat().st_ino,f.read_bytes()) for f in evidence.iterdir()}==fingerprint


def stat_mode(path):return path.stat().st_mode&0o777


@native
@pytest.mark.parametrize('name',['coordinator.lock','heavy.lock'])
def test_either_held_permanent_lock_prevents_any_recovery(disposable,name):
    import fcntl
    queue,evidence,_,_=disposable
    original=(queue/'queue-state.v1.json').read_bytes()
    fd=os.open(queue/name,os.O_RDONLY)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(c.CoordinatorError):run_fixture(disposable)
    finally:os.close(fd)
    assert (queue/'queue-state.v1.json').read_bytes()==original and not (evidence/r.BACKUP).exists()


@native
@pytest.mark.parametrize('change',['queue_hash','queue_inode','owner_inode','heavy_inode','live_child',
    'nonempty_owner','nonempty_heavy','symlink_queue','bad_queue','backup_exists','wrong_observation'])
def test_native_negative_recovery_never_changes_queue(disposable,change):
    queue,evidence,value,save=disposable
    target=queue/'queue-state.v1.json'
    if change=='queue_hash':value['queue_sha256']='0'*64;save()
    elif change in {'queue_inode','owner_inode','heavy_inode'}:
        value[change.replace('_inode','_identity')][1]+=1;save()
    elif change=='live_child':value['observations'][1]['checks']['coordinator_and_worker_absent']=False;save()
    elif change=='nonempty_owner':(queue/'coordinator.lock').write_bytes(b'unexpected owner')
    elif change=='nonempty_heavy':(queue/'heavy.lock').write_bytes(b'unexpected owner')
    elif change=='symlink_queue':
        target.rename(queue/'original.json');target.symlink_to(queue/'original.json')
    elif change=='bad_queue':
        target.write_bytes(b'{');value['queue_sha256']=hashlib.sha256(b'{').hexdigest();value['queue_bytes']=1;save()
    elif change=='backup_exists':(evidence/r.BACKUP).write_bytes(b'preserve evidence')
    else:(evidence/'observation-2.txt').write_bytes(b'altered evidence')
    original=target.read_bytes()
    with pytest.raises(Exception):run_fixture(disposable)
    assert target.read_bytes()==original


@native
def test_publish_requires_fsync_and_post_commit_independent_parse(disposable,monkeypatch):
    from app.db_audit_coordinator import state_store
    queue,evidence,_,_=disposable;original=(queue/'queue-state.v1.json').read_bytes()
    calls=[];real_sync=os.fsync
    def sync(fd):calls.append(fd);real_sync(fd)
    monkeypatch.setattr(r.os,'fsync',sync)
    publish=state_store.atomic_publish
    def observed(*args,**kwargs):
        kwargs['sync']=sync;return publish(*args,**kwargs)
    monkeypatch.setattr(state_store,'atomic_publish',observed)
    run_fixture(disposable)
    assert len(calls)==6 and p.state(c.decode((queue/'queue-state.v1.json').read_bytes()))
    assert (evidence/r.BACKUP).read_bytes()==original


@native
def test_evidence_sync_failure_blocks_terminal_and_never_deletes_evidence(disposable,monkeypatch):
    queue,evidence,_,_=disposable;original=(queue/'queue-state.v1.json').read_bytes()
    def fail(fd):raise OSError('synthetic fsync failure')
    monkeypatch.setattr(r.os,'fsync',fail)
    with pytest.raises(OSError):run_fixture(disposable)
    assert (queue/'queue-state.v1.json').read_bytes()==original
    assert (evidence/r.BACKUP).exists()


@native
@pytest.mark.parametrize('phase',['file_sync','directory_sync'])
def test_queue_publication_fault_never_reports_success_or_retries(disposable,monkeypatch,phase):
    from app.db_audit_coordinator import state_store
    queue,evidence,_,_=disposable;original=(queue/'queue-state.v1.json').read_bytes()
    real_sync=os.fsync;publish=state_store.atomic_publish;calls=[]
    def fault(fd):
        calls.append(fd)
        if len(calls)==(1 if phase=='file_sync' else 2):raise OSError('synthetic commit fault')
        real_sync(fd)
    def observed(*args,**kwargs):
        kwargs['sync']=fault;return publish(*args,**kwargs)
    monkeypatch.setattr(state_store,'atomic_publish',observed)
    with pytest.raises(c.CoordinatorError) as error:run_fixture(disposable)
    assert error.value.code==('queue_unavailable' if phase=='file_sync' else 'queue_unknown')
    assert (evidence/r.BACKUP).read_bytes()==original
    if phase=='file_sync':assert (queue/'queue-state.v1.json').read_bytes()==original
    after=(queue/'queue-state.v1.json').read_bytes()
    with pytest.raises(Exception):run_fixture(disposable)
    assert (queue/'queue-state.v1.json').read_bytes()==after


@native
def test_identity_drift_after_backup_blocks_publication(disposable,monkeypatch):
    queue,evidence,_,_=disposable;target=queue/'queue-state.v1.json';original=target.read_bytes()
    real=r._evidence
    def changed(fd,name,raw):
        real(fd,name,raw)
        if name.endswith('.attestation.json'):
            other=queue/'replacement';other.write_bytes(original);other.chmod(0o600);os.replace(other,target)
    monkeypatch.setattr(r,'_evidence',changed)
    with pytest.raises(c.CoordinatorError):run_fixture(disposable)
    assert target.read_bytes()==original


@native
@pytest.mark.parametrize('bad_index',[0,1])
def test_unqualified_queue_or_evidence_filesystem_cannot_publish(disposable,monkeypatch,bad_index):
    queue,evidence,_,_=disposable;original=(queue/'queue-state.v1.json').read_bytes()
    calls=[]
    def filesystem(fd):
        index=len(calls);calls.append(fd);return 0 if index==bad_index else 0xEF53
    monkeypatch.setattr(r,'filesystem_magic',filesystem)
    with pytest.raises(c.CoordinatorError):run_fixture(disposable)
    assert (queue/'queue-state.v1.json').read_bytes()==original and not (evidence/r.BACKUP).exists()
