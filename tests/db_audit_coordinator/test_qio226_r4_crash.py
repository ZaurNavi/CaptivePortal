"""Closed R4 policy, IPC and failure fences; no original LAB access."""
from dataclasses import asdict,replace
import copy
import hashlib
import os
from pathlib import Path
import socket
import sqlite3
import json
import sys
import uuid

import pytest

from app.db_audit_coordinator import contracts as c,live_policy as p
from app.db_audit_coordinator.live_profile import PilotProfile,R4Installation
from tests.db_audit_coordinator.test_b2_live_policy import profile,policy,STORES

POSIX=pytest.mark.skipif(sys.platform!='linux',reason='R4 native Unix descriptor/credentials contract')


class BackupTrace:
    """Portable test sink; production still uses the private OwnerTrace FIFO."""
    def __init__(self):self.backup=None;self.stages=[];self.results=[]
    def mark(self,stage):self.stages.append(stage)
    def backup_result(self):self.results.append(copy.deepcopy(self.backup))


@pytest.mark.parametrize('failure',['none','cancel','deadline','post_guard'])
def test_04G_read_view_is_RO_stable_and_closed_on_success_or_guard_abort(tmp_path,failure,record_property):
    import json
    from app.db_audit_coordinator.r4_release import BackupProgress
    path=tmp_path/'synthetic.db';writer=sqlite3.connect(path,isolation_level=None)
    writer.execute('PRAGMA journal_mode=WAL');writer.execute('CREATE TABLE fixture(id INTEGER PRIMARY KEY,value)')
    writer.execute('BEGIN')
    writer.executemany('INSERT INTO fixture VALUES(?,?)',[(i,'x'*4000) for i in range(1,227)])
    writer.execute('COMMIT')
    source=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,isolation_level=None,timeout=0)
    destination=sqlite3.connect(tmp_path/'image.db',isolation_level=None,timeout=0)
    source.execute('PRAGMA query_only=ON');source.execute('PRAGMA busy_timeout=0')
    sql=[];source.set_trace_callback(sql.append)
    source.execute('BEGIN')
    total=source.execute('PRAGMA page_count').fetchone()[0];assert total>128
    # Even accidental application writes remain denied inside the read view.
    with pytest.raises(sqlite3.OperationalError):source.execute('UPDATE fixture SET value=1')
    assert source.in_transaction
    trace=BackupTrace();guards=0;calls=[]
    def guard():
        nonlocal guards
        guards+=1
        if (failure in {'cancel','deadline'} and guards==1) or (failure=='post_guard' and guards==3):
            raise c.CoordinatorError('canceled' if failure=='cancel' else 'not_admitted')
    progress=BackupProgress(trace,guard,lambda:pytest.fail('unexpected transient'),4096,2**26)
    def callback(*values):
        calls.append(values);progress(*values)
        if values[0]==0:writer.execute('UPDATE fixture SET value=? WHERE id=1',('y'*4000,))
    try:
        if failure=='none':
            source.backup(destination,pages=128,progress=callback,sleep=0);progress.finish()
            assert destination.execute('SELECT value FROM fixture WHERE id=1').fetchone()==('x'*4000,)
            assert writer.execute('SELECT value FROM fixture WHERE id=1').fetchone()==('y'*4000,)
            assert len(trace.results)==1
        else:
            with pytest.raises(c.CoordinatorError):
                source.backup(destination,pages=128,progress=callback,sleep=0);progress.finish()
            assert trace.results==[]
            assert trace.backup['check']==('post_backup_guard' if failure=='post_guard' else 'callback_guard')
        assert source.in_transaction
    finally:destination.close();source.close();writer.close()
    with pytest.raises(sqlite3.ProgrammingError):source.execute('SELECT 1')
    assert sql[0]=='BEGIN' and not any(statement in {'COMMIT','ROLLBACK','BEGIN IMMEDIATE'} for statement in sql)
    record_property('04g_read_view',json.dumps(dict(failure=failure,calls=calls,sql=sql,sqlite=sqlite3.sqlite_version)))


@pytest.mark.parametrize('status',[5,6])
def test_04F_native_transient_status_zero_counts_is_not_completion(status):
    from app.db_audit_coordinator.r4_release import BackupProgress
    trace=BackupTrace();guards=[];waits=[]
    progress=BackupProgress(trace,lambda:guards.append(1),lambda:waits.append(1),4096,2**26)
    progress(status,0,0)
    assert not progress.complete and not trace.backup['complete'] and trace.backup['steps']==1
    with pytest.raises(c.CoordinatorError):progress.finish()
    progress(0,1,2);progress(101,0,2);progress.finish()
    assert progress.complete and len(trace.results)==1 and waits==[1]
    assert trace.backup['busy' if status==5 else 'locked']==1
    assert trace.backup['done']==1 and trace.backup['ok']==1 and trace.backup['steps']==3
    assert trace.stages==['backup_progress'] and len(guards)==4


@pytest.mark.parametrize('code,remaining,total,check',[
    (8,0,0,'callback_status'),(11,0,0,'callback_status'),(10,0,0,'callback_status'),
    (True,0,2,'callback_types'),(0,False,2,'callback_types'),(0,1,True,'callback_types'),
    (0,-1,2,'callback_counts'),(0,3,2,'callback_counts'),(0,0,0,'callback_page_budget'),
    (101,1,2,'callback_counts'),(5,0,20000,'callback_page_budget'),
    (0,1,20000,'callback_page_budget'),(0,0,2**31,'callback_counts'),
    ('SECRET',0,2,'callback_types'),(0,'SECRET',2,'callback_types')])
def test_04F_bad_callback_is_closed_and_has_exact_failing_check(code,remaining,total,check):
    from app.db_audit_coordinator.r4_release import BackupProgress
    from app.db_audit_coordinator.r4_release import validate_owner_backup
    trace=BackupTrace();waits=[]
    progress=BackupProgress(trace,lambda:None,lambda:waits.append(1),4096,2**26)
    with pytest.raises(c.CoordinatorError) as error:progress(code,remaining,total)
    assert error.value.code=='not_admitted' and trace.backup['check']==check
    assert not progress.complete and trace.results==[] and waits==[]
    validate_owner_backup(trace.backup)
    assert 'SECRET' not in json_text(trace.backup)


def json_text(value):return c.encode(value).decode('ascii')


def test_04F_original_callback_cap_and_missing_done_cannot_fabricate_success():
    from app.db_audit_coordinator.r4_release import BackupProgress
    trace=BackupTrace();progress=BackupProgress(trace,lambda:None,lambda:None,4096,2**26)
    for _ in range(100000):progress(0,1,2)
    with pytest.raises(c.CoordinatorError):progress(5,0,0)
    assert trace.backup['steps']==100001 and trace.backup['check']=='callback_step_budget'
    with pytest.raises(c.CoordinatorError):progress.finish()
    assert trace.results==[]


@pytest.mark.parametrize('where',['callback_guard','busy_wait','post_backup_guard'])
def test_04F_cancel_deadline_or_guard_failure_remains_a_failure(where):
    from app.db_audit_coordinator.r4_release import BackupProgress
    trace=BackupTrace()
    def stop():raise c.CoordinatorError('not_admitted')
    progress=BackupProgress(trace,stop if where=='callback_guard' else lambda:None,
                            stop if where=='busy_wait' else lambda:None,4096,2**26)
    with pytest.raises(c.CoordinatorError):
        if where=='post_backup_guard':
            progress(101,0,2);progress.guard=stop;progress.finish()
        else:progress(5,0,0)
    assert trace.backup['check']==where and trace.results==[]


def test_04F_real_sqlite_abi_busy_then_done_without_source_writes(tmp_path,record_property):
    import json
    from app.db_audit_coordinator.r4_release import BackupProgress
    path=tmp_path/'source.sqlite3';target=tmp_path/'image.sqlite3'
    writer=sqlite3.connect(path,isolation_level=None)
    writer.execute('PRAGMA journal_mode=WAL');writer.execute('CREATE TABLE synthetic(value)')
    writer.execute("INSERT INTO synthetic VALUES('disposable')")
    source=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,isolation_level=None,timeout=0)
    source.execute('PRAGMA query_only=ON');source.execute('PRAGMA busy_timeout=0')
    destination=sqlite3.connect(target,isolation_level=None,timeout=0)
    blocker=sqlite3.connect(target,isolation_level=None,timeout=0);blocker.execute('BEGIN EXCLUSIVE')
    before=tuple(writer.iterdump());calls=[];trace=BackupTrace()
    def wait():blocker.execute('ROLLBACK')
    progress=BackupProgress(trace,lambda:None,wait,4096,2**26)
    def callback(*values):calls.append(values);progress(*values)
    try:
        source.backup(destination,pages=128,progress=callback,sleep=0);progress.finish()
        assert calls[0]==(5,0,0) and calls[-1]==(101,0,2)
        assert trace.backup['busy']==trace.backup['done']==1 and trace.backup['complete']
        assert destination.execute('SELECT * FROM synthetic').fetchall()==[('disposable',)]
        assert tuple(writer.iterdump())==before
        with pytest.raises(sqlite3.OperationalError):source.execute('INSERT INTO synthetic VALUES(1)')
        record_property('04f_real_backup_callback',json.dumps(dict(sqlite=sqlite3.sqlite_version,calls=calls)))
    finally:blocker.close();destination.close();source.close();writer.close()


@pytest.mark.parametrize('fault',['bool','large','negative_steps','unknown','payload','wrong_sum','false_done','extra_record'])
def test_04F_root_rejects_untrusted_backup_numbers_and_fields(fault):
    from app.db_audit_coordinator.r4_release import owner_trace
    trace=BackupTrace()
    from app.db_audit_coordinator.r4_release import BackupProgress
    BackupProgress(trace,lambda:None,lambda:None,4096,2**26)
    value=trace.backup
    if fault=='bool':value['total']=True
    elif fault=='large':value['status']=2**31
    elif fault=='negative_steps':value['steps']=-1
    elif fault=='unknown':value['check']='SECRET /source'
    elif fault=='payload':value['payload']='SECRET'
    elif fault=='wrong_sum':value['busy']=1
    elif fault=='false_done':value['complete']=True
    marker=c.encode(dict(stage='backup_progress'))+b'\n'
    raw=marker+c.encode(dict(stage='backup_progress',backup=value))+b'\n'
    if fault=='extra_record':raw+=c.encode(dict(stage='backup_progress',backup=value))+b'\n'
    result=owner_trace(raw)
    assert result['report_status']=='invalid' and 'backup' not in result
    assert 'SECRET' not in json_text(result)


@POSIX
@pytest.mark.parametrize('failed',[False,True])
def test_04F_closed_diagnostic_is_finite_and_emitted_only_at_failure_or_finish(failed):
    from app.db_audit_coordinator.r4_release import OwnerTrace,OWNER_STAGES,OWNER_DIAGNOSTIC_LIMIT,owner_trace
    from app.db_audit_coordinator.r4_release import BackupProgress
    read,write=os.pipe2(os.O_CLOEXEC|os.O_NONBLOCK);trace=OwnerTrace(write)
    try:
        for stage in OWNER_STAGES[:OWNER_STAGES.index('backup_progress')]:trace.mark(stage)
        progress=BackupProgress(trace,lambda:None,lambda:None,4096,2**26)
        for _ in range(500):progress(5,0,0)
        if failed:
            with pytest.raises(c.CoordinatorError) as error:progress(8,0,0)
            trace.failure(error.value)
        else:
            progress(101,0,2);progress.finish()
            for stage in OWNER_STAGES[OWNER_STAGES.index('backup_complete'):]:trace.mark(stage)
        raw=os.read(read,OWNER_DIAGNOSTIC_LIMIT+1)
        assert len(raw)<OWNER_DIAGNOSTIC_LIMIT and len(raw.splitlines())<=len(OWNER_STAGES)+2
        value=owner_trace(raw)
        assert value['backup']['busy']==500 and value['backup']['steps']==(501)
        assert value['report_status']==('failure' if failed else 'stage_only')
        assert value['backup']['check']==('callback_status' if failed else 'finished')
    finally:trace.close();os.close(read)


@POSIX
def test_04E_trace_budget_cloexec_first_progress_first_failure_and_no_secret_bytes():
    from app.db_audit_coordinator.r4_release import OwnerTrace,OWNER_STAGES,OWNER_DIAGNOSTIC_LIMIT,owner_trace
    read,write=os.pipe2(os.O_CLOEXEC|os.O_NONBLOCK)
    trace=OwnerTrace(write)
    try:
        assert not os.get_inheritable(write)
        for stage in OWNER_STAGES:
            trace.mark(stage)
            if stage=='backup_progress':
                for _ in range(10000):trace.mark(stage)
        trace.failure(PermissionError(13,'SECRET /original/source SQL nonce payload'))
        trace.failure(RuntimeError('SECOND_SECRET'))
        raw=os.read(read,OWNER_DIAGNOSTIC_LIMIT+1)
        assert len(raw)<OWNER_DIAGNOSTIC_LIMIT and len(raw.splitlines())==len(OWNER_STAGES)+1
        result=owner_trace(raw)
        assert result==dict(report_status='failure',stage='finished',exception_class='PermissionError',
            coordinator_code=None,os_errno=13,stop_reason=None)
        assert not any(word in raw for word in (b'SECRET',b'/original',b'nonce',b'payload',b'SQL'))
    finally:trace.close();os.close(read)


@POSIX
def test_04E_broken_diagnostic_reader_cannot_change_helper_code_or_retry():
    from app.db_audit_coordinator.r4_release import OwnerTrace
    read,write=os.pipe2(os.O_CLOEXEC|os.O_NONBLOCK);os.close(read)
    trace=OwnerTrace(write)
    try:
        trace.mark('auth_document');trace.mark('profile_parse')
        trace.failure(c.CoordinatorError('not_admitted'))
    finally:trace.close()


@pytest.mark.parametrize('fault',['empty','truncated','oversize','unknown','unknown_field','duplicate_stage',
    'backwards','unknown_exception','raw_code','bool_errno','large_errno','unknown_stop','extra_after_failure'])
def test_04E_root_rejects_malformed_private_owner_report_without_echoing_it(fault):
    from app.db_audit_coordinator.r4_release import owner_trace,OWNER_DIAGNOSTIC_LIMIT
    row=dict(stage='source_open',exception_class='PermissionError',coordinator_code=None,os_errno=13,stop_reason=None)
    marker=c.encode(dict(stage='source_open'))+b'\n'
    if fault=='empty':raw=b''
    elif fault=='truncated':raw=marker[:-1]
    elif fault=='oversize':raw=b'x'*(OWNER_DIAGNOSTIC_LIMIT+1)
    elif fault=='unknown':raw=c.encode(dict(stage='SECRET /original/path'))+b'\n'
    elif fault=='duplicate_stage':raw=marker+marker
    elif fault=='backwards':raw=marker+c.encode(dict(stage='auth_document'))+b'\n'
    else:
        if fault=='unknown_field':row['payload']='SECRET'
        elif fault=='unknown_exception':row['exception_class']='SECRET'
        elif fault=='raw_code':row['coordinator_code']='SECRET'
        elif fault=='bool_errno':row['os_errno']=True
        elif fault=='large_errno':row['os_errno']=100000
        elif fault=='unknown_stop':row['stop_reason']='SECRET'
        raw=marker+c.encode(row)+b'\n'
        if fault=='extra_after_failure':raw+=c.encode(dict(stage='finished'))+b'\n'
    result=owner_trace(raw)
    assert result['report_status']==('unavailable' if fault=='empty' else 'invalid')
    assert result['stage']=='unreported' and result['exception_class'] is None
    assert not any(word in c.encode(result).decode() for word in ('SECRET','/original','payload'))


@pytest.mark.parametrize('ready,done,code,stop,expected',[
    (False,False,3,None,'pre_ready_exit'),(True,False,-9,None,'backup_abort'),
    (True,False,3,'canceled','canceled'),(True,False,3,'deadline','deadline'),
    (True,True,0,None,'complete')])
def test_04E_one_root_event_after_positive_reap_does_not_mutate_job_result(ready,done,code,stop,expected,monkeypatch):
    from types import SimpleNamespace
    from app.db_audit_coordinator import r4_release as release
    subject=release.Session.__new__(release.Session)
    subject.job=record();subject.job['seq']=1;before=copy.deepcopy(subject.job)
    subject.owner_trace_fd=None;subject.owner_diagnostic=None
    subject.owner_ready=ready;subject.backup_done=done;subject.canceled=False
    detail=dict(report_status='failure',stage='backup_progress',exception_class='CoordinatorError',
        coordinator_code='canceled' if stop=='canceled' else 'not_admitted',os_errno=None,stop_reason=stop)
    monkeypatch.setattr(release,'owner_trace',lambda raw:detail)
    events=[];monkeypatch.setattr(release,'emit_hold',events.append)
    helper=SimpleNamespace(reaped=lambda:code)
    subject.owner_outcome(helper);subject.owner_outcome(helper)
    assert len(events)==1 and events[0]['outcome']==expected and events[0]['child_exit_code']==code
    assert subject.job==before and subject.owner_trace_fd is None


def test_04E_uncertain_reap_cannot_be_logged_as_a_confirmed_exit(monkeypatch):
    from types import SimpleNamespace
    from app.db_audit_coordinator import r4_release as release
    subject=release.Session.__new__(release.Session);subject.owner_diagnostic=None
    def uncertain():raise c.CoordinatorError('orphan_hold')
    events=[];monkeypatch.setattr(release,'emit_hold',events.append)
    with pytest.raises(c.CoordinatorError):subject.owner_outcome(SimpleNamespace(reaped=uncertain))
    assert events==[]


def test_04K_hold_diagnostic_wait_is_bounded_independently_of_job_age(monkeypatch):
    from types import SimpleNamespace
    from app.db_audit_coordinator import r4_release as release
    job=record();job.update(seq=1,reason_code='running',state='running')
    state=dict(jobs=[copy.deepcopy(job)])
    subject=release.Session.__new__(release.Session);subject.job=job
    subject.owner=SimpleNamespace(_state=lambda:copy.deepcopy(state),_commit=lambda value:None)
    subject.held=False;subject.deadline=0
    waits=[];subject.children=dict(owner=SimpleNamespace(waited=False,exited=SimpleNamespace(wait=waits.append)))
    events=[];monkeypatch.setattr(release,'emit_hold',events.append)
    subject.hold(c.CoordinatorError('not_admitted'))
    assert waits==[.25] and subject.held and subject.owner.orphan_hold
    assert len(events)==1 and events[0]['event']=='qio226_r4_first_hold'


def proof(image=True):
    source=[[1,2,8192],{'-wal':[1,3,4096],'-shm':[1,4,32768],'-journal':None}]
    digest=hashlib.sha256(c.encode(source)).hexdigest()
    return dict(binding_sha256='1'*64,source_pre_sha256=digest,source_post_sha256=digest,
        snapshot=dict(device=1,inode=2,size=8192,sha256='4'*64) if image else None,
        leaf_identity=[1,2],namespace_identity=[3,4],helper_reaped=True,gatekeeper_reaped=True,
        cleanup_complete=True,shmem_zero=True,empty_observations=2,scope='guest_vm_only',
        source_observations=dict(pre=source,post=source),
        memory_observations=dict(maximum=2**26,current_after_backup=2**20,shmem_after_backup=8192,swap_current=0))


def record(method=p.R4_METHOD,store='public_traffic'):
    return dict(job_id=str(uuid.uuid4()),store_id=store,run_id=str(uuid.uuid4()),attempt_id=str(uuid.uuid4()),
        claim_epoch=str(uuid.uuid4()),method_version=method,validator_version=p.VALIDATORS[store],
        source_generation=str(uuid.uuid4()))


def snapshot(store='public_traffic'):
    return dict(schema_version=2 if store=='public_traffic' else 1,
        generation_kind='pinned_file_instance' if store=='public_traffic' else 'native_lineage',
        lineage_sha256='5'*64,watermark_sha256='6'*64,page_size=4096,page_count=2)


def test_K09_old_profiles_are_readable_and_do_not_implicitly_enable_r4():
    value=profile();raw=c.decode(c.encode(asdict(value)));raw.pop('r4')
    old=PilotProfile.parse(raw)
    assert old.r4 is None and old.metadata('public_traffic')[0]==p.METHOD
    install=R4Installation(p.R4_METHOD,False,1000,'/run/captive-portal/db-audit/ram-jobs',1,2,8,64)
    assert replace(value,r4=install).metadata('public_traffic')[0]==p.METHOD
    enabled=replace(value,r4=replace(install,enabled=True))
    assert all(enabled.metadata(store)[0]==p.R4_METHOD for store in STORES)
    assert PilotProfile.parse(c.decode(c.encode(asdict(enabled))))==enabled


def mixed_profile():
    """04C exact original topology, disposable metadata only."""
    gids={'public_traffic':1004,'network_service_intelligence':1004,'traffic_projection':996}
    install=R4Installation(p.R4_METHOD,True,1003,'/run/captive-portal/db-audit/ram-jobs',1,2,16,64)
    return profile(enabled=True,stores=tuple(policy(store,uid=1003,gid=gids[store],inode=number+2)
        for number,store in enumerate(STORES)),r4=install)


def test_04C_strict_mixed_source_gid_roundtrip_has_one_uid_and_no_global_gid():
    value=mixed_profile();raw=c.decode(c.encode(asdict(value)))
    assert 'owner_gid' not in raw['r4']
    parsed=PilotProfile.parse(raw)
    assert parsed==value and parsed.r4.owner_uid==1003 and parsed.r4.enabled
    assert [(item.uid,item.gid) for item in parsed.stores]==[(1003,1004),(1003,1004),(1003,996)]
    assert parsed.worker_gid==1001 and parsed.worker_gid not in {item.gid for item in parsed.stores}
    assert all(parsed.metadata(store)[0]==p.R4_METHOD for store in STORES)
    assert c.encode(asdict(parsed))==c.encode(raw)


@pytest.mark.parametrize('store',STORES)
@pytest.mark.parametrize('fault',['wrong_uid','gid_zero','gid_negative','gid_bool','gid_overflow','gid_string'])
def test_04C_bad_store_owner_or_gid_never_parses(store,fault):
    raw=c.decode(c.encode(asdict(mixed_profile())))
    item=next(item for item in raw['stores'] if item['store_id']==store)
    if fault=='wrong_uid':item['uid']=1005
    else:item['gid']={'gid_zero':0,'gid_negative':-1,'gid_bool':True,'gid_overflow':2**32,'gid_string':'1004'}[fault]
    with pytest.raises(c.CoordinatorError):PilotProfile.parse(raw)


@pytest.mark.parametrize('fault',['obsolete_gid','extra','missing_uid','missing_ram','root_owner','worker_is_owner'])
def test_04C_r4_closed_schema_rejects_obsolete_extra_missing_and_unsafe_identity(fault):
    raw=c.decode(c.encode(asdict(mixed_profile())))
    if fault=='obsolete_gid':raw['r4']['owner_gid']=1004
    elif fault=='extra':raw['r4']['supplementary_groups']=[1004,996]
    elif fault=='missing_uid':raw['r4'].pop('owner_uid')
    elif fault=='missing_ram':raw['r4'].pop('ram_inode')
    elif fault=='root_owner':raw['r4']['owner_uid']=0
    else:raw['worker_uid']=1003
    with pytest.raises(c.CoordinatorError):PilotProfile.parse(raw)


def test_04C_historical_null_r4_and_method_metadata_are_not_migrated():
    raw=c.decode(c.encode(asdict(profile())));before=c.encode(raw)
    assert raw['r4'] is None
    parsed=PilotProfile.parse(raw)
    assert parsed.r4 is None and c.encode(asdict(parsed))==before
    for store in STORES:assert parsed.metadata(store)==parsed.store(store).metadata()


@POSIX
@pytest.mark.parametrize('args',[['1','--gid','1004'],['1','--uid','1003'],['1','--groups','1004,996']])
def test_04C_helper_cli_has_no_untrusted_credential_or_group_override(args):
    from app.db_audit_coordinator.r4_owner_helper import main
    assert main(args)==2


@pytest.mark.skipif(sys.platform!='linux' or getattr(os,'geteuid',lambda:0)()==0,
    reason='actual nonroot Linux sealed worker-claim authorization')
@pytest.mark.parametrize('swapped',[False,True])
def test_04C_sealed_job_store_change_cannot_reuse_another_source_authority(swapped):
    from app.db_audit_coordinator import child_bootstrap as worker
    from app.db_audit_coordinator.live_coordinator import memory_document
    from app.db_audit_coordinator.live_receipts import start_ticks
    value=replace(mixed_profile(),release_root=str(Path(__file__).resolve().parents[2]),
        python=sys.executable,worker_uid=os.getuid(),worker_gid=os.getgid(),worker_groups=tuple(os.getgroups()))
    queue=p.empty_state();job=record(store='public_traffic')
    method,validator,generation=value.metadata(job['store_id'])
    read,write=os.pipe();pipe=os.fstat(read);nonce='1'*64;fds=[write]
    cancel_read,cancel_write=os.pipe();result_read,result_write=os.pipe()
    fds.extend([cancel_read,cancel_write,result_read,result_write])
    job.update(seq=1,state='running',origin='manual',created_at=c.utc(),updated_at=c.utc(),
        reason_code='running',scope_hash='2'*64,idempotency_hash='3'*64,claim_epoch=queue['controller_epoch'],
        method_version=method,validator_version=validator,source_generation=generation,worker_pid=os.getpid(),
        auth_hash=hashlib.sha256(nonce.encode()).hexdigest(),auth_device=pipe.st_dev,auth_inode=pipe.st_ino,
        resource_envelope=dict(fixture_only=False,memory_limit_bytes=2**26,timeout_seconds=30),audit_result=None)
    if swapped:
        job['store_id']='traffic_projection';job['validator_version']=p.VALIDATORS[job['store_id']]
        assert value.metadata(job['store_id'])[2]!=generation
    queue.update(jobs=[job],next_sequence=2)
    claim=memory_document(queue);config=memory_document(asdict(value));fds.extend([claim,config])
    from app.db_audit_coordinator.r4_ipc import pair
    left,right=pair()
    data=dict(job_id=job['job_id'],attempt_id=job['attempt_id'],claim_epoch=job['claim_epoch'],nonce=nonce,
        claim_fd=claim,profile_fd=config,result_fd=result_write,cancel_fd=cancel_read,
        supervisor_pid=os.getppid(),supervisor_start=start_ticks(os.getppid()),leaf='/disposable/job',
        leaf_device=1,leaf_inode=2,gate_device=1,gate_inode=3,started_ns=1,r4_fd=right.fileno())
    try:
        os.write(write,c.encode(data));os.close(write);fds.remove(write)
        if swapped:
            with pytest.raises(c.CoordinatorError):worker.authorize(read)
        else:
            _,selected,parsed,chosen=worker.authorize(read)
            assert selected['store_id']=='public_traffic' and (chosen.uid,chosen.gid)==(1003,1004)
            assert parsed==value
    finally:
        left.close();right.close()
        for fd in fds:os.close(fd)


@pytest.mark.parametrize('field',['epoch','attempt','store','source','code','leaf','namespace'])
def test_K10_one_use_binding_commits_job_code_source_and_kernel_view(field):
    from app.db_audit_coordinator.r4_ipc import claim_binding
    from types import SimpleNamespace
    job=record();job.update(auth_hash='1'*64,worker_pid=123)
    cfg=profile();leaf=SimpleNamespace(relative='/delegated/job',identity=(1,2));namespace=[3,4]
    first=claim_binding(job,cfg,leaf,namespace)
    if field=='epoch':job['claim_epoch']=str(uuid.uuid4())
    elif field=='attempt':job['attempt_id']=str(uuid.uuid4())
    elif field=='store':job['store_id']='traffic_projection'
    elif field=='source':job['source_generation']=str(uuid.uuid4())
    elif field=='code':cfg=replace(cfg,tree='7'*40)
    elif field=='leaf':leaf.identity=(1,3)
    elif field=='namespace':namespace=[3,5]
    assert first!=claim_binding(job,cfg,leaf,namespace)


@pytest.mark.parametrize('field,value',[('method',p.METHOD),('enabled',1),('ram_root','/dev/shm'),
    ('task_limit',7),('nr_inodes',True),('owner_uid',0)])
def test_K10_profile_does_not_accept_implicit_alias_or_unbounded_authority(field,value):
    fields=dict(method=p.R4_METHOD,enabled=True,owner_uid=1000,
        ram_root='/run/captive-portal/db-audit/ram-jobs',ram_device=1,ram_inode=2,task_limit=8,nr_inodes=64)
    fields[field]=value
    with pytest.raises(c.CoordinatorError):R4Installation(**fields)


@pytest.mark.parametrize('field,value',[('helper_reaped',False),('gatekeeper_reaped',1),
    ('cleanup_complete',False),('shmem_zero',False),('empty_observations',1),
    ('empty_observations',True),('namespace_identity',[1,0]),('source_pre_sha256',None),
    ('scope','host'),('unknown','not-allowed')])
def test_K07_unknown_release_or_resource_fact_cannot_create_terminal_success(field,value):
    receipt=proof();receipt[field]=value
    with pytest.raises(c.CoordinatorError):p.make_result(record(),'passed','audit_passed',snapshot=snapshot(),receipt=receipt)


def test_K08_controlled_failed_receipt_is_distinct_from_orphan_and_has_no_fake_image():
    item=p.make_result(record(),'failed','audit_failed',receipt=proof(False))
    assert item['result']=='failed' and item['snapshot_id'] is None
    assert item['r4_receipt']['proof_sha256']==hashlib.sha256(c.encode(proof(False))).hexdigest()
    with pytest.raises(c.CoordinatorError):p.make_result(record(),'passed','audit_passed',snapshot=snapshot(),receipt=proof(False))
    with pytest.raises(c.CoordinatorError):p.make_result(record(),'incomplete','orphan_hold')


def test_K09_128_retained_mixed_methods_fit_unchanged_public_size_and_old_25_untouched():
    state=p.empty_state();old=[]
    for number in range(128):
        store=STORES[number%3];base=record(p.METHOD if number<25 else p.R4_METHOD,store)
        base['claim_epoch']=state['controller_epoch']
        result=p.make_result(base,'passed','audit_passed',snapshot=snapshot(store),
            receipt=None if number<25 else proof())
        job=dict(**base,seq=number+1,created_at=c.utc(),updated_at=c.utc(),state='completed',origin='manual',
            scope_hash='8'*64,idempotency_hash=hashlib.sha256(str(number).encode()).hexdigest(),
            auth_hash='9'*64,auth_device=1,auth_inode=2,worker_pid=123,
            resource_envelope=dict(fixture_only=False,memory_limit_bytes=2**26,timeout_seconds=5400),
            reason_code='audit_passed',audit_result=result)
        state['jobs'].append(job)
        state['last_attempt_by_store'][store]=copy.deepcopy(result)
        state['last_verified_success_by_store'][store]=copy.deepcopy(result)
        if number<25:old.append(c.encode(job))
    state['next_sequence']=129
    assert p.state(state) is state and len(c.encode(state))<=c.MAX_BYTES
    assert [c.encode(job) for job in state['jobs'][:25]]==old
    assert c.MAX_HISTORY==128 and c.MAX_OUTSTANDING==32


@POSIX
@pytest.mark.parametrize('fault',['uid','pid','binding','unknown','missing_fd','extra_fd','oversize','truncated_fd'])
def test_K10_authenticated_packets_reject_forged_or_malformed_capabilities_without_fd_leak(fault,tmp_path):
    from app.db_audit_coordinator import r4_ipc
    left,right=r4_ipc.pair();fd=os.open(tmp_path/'capability',os.O_RDWR|os.O_CREAT|os.O_EXCL,0o600)
    before=len(os.listdir('/proc/self/fd'))
    try:
        if fault=='unknown':right.send(c.encode(dict(kind='unknown',binding='1'*64,payload={})))
        elif fault=='missing_fd':right.send(c.encode(dict(kind='snapshot',binding='1'*64,payload={})))
        elif fault=='extra_fd':
            import array
            right.sendmsg([c.encode(dict(kind='release',binding='1'*64,payload={}))],
                [(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',[fd]))])
        elif fault in {'oversize','truncated_fd'}:
            import array
            right.sendmsg([b'x'*9000],[] if fault=='oversize' else
                [(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',[fd]*8))])
        else:r4_ipc.send(right,'begin','1'*64,{})
        with pytest.raises(c.CoordinatorError):r4_ipc.receive(left,'2'*64 if fault=='binding' else '1'*64,
            os.getuid()+1 if fault=='uid' else os.getuid(),os.getpid()+1 if fault=='pid' else os.getpid(),seconds=1)
        assert len(os.listdir('/proc/self/fd'))==before
    finally:os.close(fd);left.close();right.close()


@POSIX
def test_K10_snapshot_rights_are_two_ordered_new_readonly_cloexec_descriptors(tmp_path):
    from app.db_audit_coordinator import r4_ipc
    left,right=r4_ipc.pair();target=tmp_path/'image';target.write_bytes(b'synthetic')
    fd=os.open(target,os.O_RDONLY);folder=os.open(tmp_path,os.O_RDONLY|os.O_DIRECTORY);received=None
    try:
        r4_ipc.send(right,'snapshot','1'*64,dict(image='fixture-only'),fds=(fd,folder))
        kind,payload,received=r4_ipc.receive(left,'1'*64,os.getuid(),os.getpid(),seconds=1,allow_snapshot=True)
        assert kind=='snapshot' and len(received)==2 and set(received).isdisjoint({fd,folder})
        assert all(not os.get_inheritable(opened) for opened in received)
        assert os.fstat(fd)==os.fstat(received[0]) and os.read(received[0],9)==b'synthetic'
        assert os.fstat(folder)==os.fstat(received[1])
    finally:
        if received is not None:
            for opened in received:os.close(opened)
        os.close(fd);os.close(folder);left.close();right.close()


@POSIX
@pytest.mark.parametrize('fault',['zero','one','three','duplicate','swapped','writable','opath',
    'anonymous','uid','pid','binding','unrequested','extra_rights','bad_credentials'])
def test_04D_two_fd_packet_rejects_every_wrong_capability_and_closes_received_slots(fault,tmp_path):
    import array
    import struct
    from app.db_audit_coordinator import r4_ipc
    left,right=r4_ipc.pair();target=tmp_path/'image';target.write_bytes(b'synthetic')
    image=os.open(target,os.O_RDONLY);folder=os.open(tmp_path,os.O_RDONLY|os.O_DIRECTORY)
    writable=os.open(target,os.O_RDWR);opath=os.open(tmp_path,os.O_PATH|os.O_DIRECTORY)
    anonymous=os.memfd_create('04d-synthetic',os.MFD_CLOEXEC)
    slots={'zero':[],'one':[image],'three':[image,folder,folder],'duplicate':[image,image],
        'swapped':[folder,image],'writable':[writable,folder],'opath':[image,opath],
        'anonymous':[anonymous,folder],'extra_rights':[image,folder]*8}.get(fault,[image,folder])
    count=len(os.listdir('/proc/self/fd'))
    try:
        ancillary=[] if not slots else [(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',slots))]
        if fault=='bad_credentials':
            # Kernel cannot forge another PID, including root: reject send or
            # reject the packet if a future kernel ever delivered it.
            ancillary.append((socket.SOL_SOCKET,socket.SCM_CREDENTIALS,struct.pack('3i',os.getpid()+100000,os.getuid(),os.getgid())))
        try:right.sendmsg([c.encode(dict(kind='snapshot',binding='1'*64,payload={}))],ancillary)
        except OSError as error:
            import errno
            assert fault=='bad_credentials' and error.errno in {errno.EPERM,errno.ESRCH}
        else:
            with pytest.raises(c.CoordinatorError):
                r4_ipc.receive(left,'2'*64 if fault=='binding' else '1'*64,
                    os.getuid()+1 if fault=='uid' else os.getuid(),
                    os.getpid()+1 if fault=='pid' else os.getpid(),seconds=1,
                    allow_snapshot=fault!='unrequested')
        assert len(os.listdir('/proc/self/fd'))==count
    finally:
        for opened in (image,folder,writable,opath,anonymous):os.close(opened)
        left.close();right.close()


@pytest.mark.parametrize('gate,subphase',[
    ('claim_publish','claim'),('worker_bootstrap','spawn'),('worker_reap','reap'),
    ('gate_owner','identity'),('resource_leaf','tmpfs'),('owner_helper','source_open'),
    ('snapshot_promotion','promote'),('snapshot_dirfd','pin_final'),('t3','ready'),
    ('release_cleanup','unmount'),('channel_closed','wait')])
def test_04D_every_first_root_predicate_has_one_closed_event_and_cannot_dispatch_BC(gate,subphase,monkeypatch):
    from app.db_audit_coordinator import r4_release as release
    class Owner:
        orphan_hold=False
        def __init__(self):
            self.value=dict(jobs=[dict(job_id=job,attempt_id=attempt,seq=25,state='running',reason_code='running'),
                dict(state='queued'),dict(state='queued')]);self.writes=0
        def _state(self):return copy.deepcopy(self.value)
        def _commit(self,value):self.value=value;self.writes+=1
    job,attempt=str(uuid.uuid4()),str(uuid.uuid4())
    subject=release.Session.__new__(release.Session);subject.owner=Owner()
    subject.job=copy.deepcopy(subject.owner.value['jobs'][0]);subject.phase='owner'
    subject.held=subject.done=False;subject.children={}
    subject.source_gate_verified=True;subject.source_open_started=gate not in {'gate_owner','worker_bootstrap'}
    events=[];monkeypatch.setattr(release,'emit_hold',events.append)
    def predicate():
        subject.at(gate,subphase)
        raise PermissionError(13,'SECRET SQL /source/path nonce CANARY')
    subject.guard=predicate
    assert subject.pump() is False
    assert subject.pump() is False
    subject.hold(RuntimeError('SECOND SECRET'))
    assert len(events)==1 and subject.owner.writes==1
    diagnostic=events[0]
    assert diagnostic==dict(event='qio226_r4_first_hold',version=1,job_id=job,attempt_id=attempt,seq=25,
        phase='owner',gate_id=gate,subphase=subphase,exception_class='PermissionError',
        coordinator_code=None,os_errno=13,child_role=None,child_exit_code=None,
        source_gate_verified=True,source_open_started=subject.source_open_started)
    assert not any(word in c.encode(diagnostic).decode() for word in ('SECRET','/source','nonce','SQL'))
    assert [item['state'] for item in subject.owner.value['jobs']]==['running','queued','queued']
    assert subject.owner.value['jobs'][0]['reason_code']=='orphan_hold'
    assert subject.owner.orphan_hold and subject.held and not subject.done


def test_04D_diagnostic_whitelist_never_serializes_untrusted_error_text_or_uncertain_reap():
    from types import SimpleNamespace
    from app.db_audit_coordinator.r4_release import hold_diagnostic
    subject=SimpleNamespace(job=dict(job_id=str(uuid.uuid4()),attempt_id=str(uuid.uuid4()),seq=25),
        phase='unknown-secret',gate_id='raw-path',subphase='secret',children={},
        source_gate_verified=False,source_open_started=False)
    class Untrusted(Exception):pass
    error=Untrusted('SQL SECRET');error.code='secret-code';error.errno=17
    diagnostic=hold_diagnostic(subject,error)
    assert diagnostic['exception_class']=='unknown' and diagnostic['coordinator_code'] is None
    assert diagnostic['os_errno'] is None and diagnostic['child_exit_code'] is None
    assert diagnostic['phase']=='claim' and diagnostic['subphase']=='wait'
    assert not any(word in c.encode(diagnostic).decode() for word in ('SQL','SECRET','raw-path'))
    subject.children['worker']=SimpleNamespace(waited=False,reaped=lambda:-9)
    assert hold_diagnostic(subject,error,'worker')['child_exit_code'] is None
    subject.children['worker'].waited=True
    assert hold_diagnostic(subject,c.CoordinatorError('unsafe_path'),'worker')['child_exit_code']==-9
    assert hold_diagnostic(subject,c.CoordinatorError('unsafe_path'))['coordinator_code']=='unsafe_path'


@POSIX
def test_04D_start_resource_exception_is_not_a_child_exit_and_never_crosses_source_gate(monkeypatch):
    from app.db_audit_coordinator import r4_release,live_cgroup
    class Owner:
        profile=mixed_profile()
        orphan_hold=False
        def __init__(self):
            item=record();item.update(seq=25,state='queued',reason_code='queued')
            self.value=dict(controller_epoch=str(uuid.uuid4()),jobs=[item,dict(state='queued'),dict(state='queued')])
        def _state(self):return copy.deepcopy(self.value)
        def _commit(self,value):self.value=copy.deepcopy(value)
    owner=Owner();session=r4_release.Session(owner,owner.value['jobs'][0],owner.value)
    events=[];monkeypatch.setattr(r4_release,'emit_hold',events.append)
    def denied(*args,**kwargs):raise PermissionError(13,'untrusted path SECRET')
    monkeypatch.setattr(live_cgroup,'create_leaf',denied)
    count=len(os.listdir('/proc/self/fd'))
    with pytest.raises(PermissionError):session.start()
    assert len(os.listdir('/proc/self/fd'))==count
    assert len(events)==1 and events[0]['gate_id']=='resource_leaf' and events[0]['subphase']=='leaf_create'
    assert events[0]['child_role']=='worker' and events[0]['child_exit_code'] is None
    assert events[0]['exception_class']=='PermissionError' and events[0]['os_errno']==13
    assert not events[0]['source_open_started'] and not events[0]['source_gate_verified']
    assert session.children=={} and session.held and owner.orphan_hold
    assert [item['state'] for item in owner.value['jobs']]==['claimed','queued','queued']
    assert owner.value['jobs'][0]['reason_code']=='orphan_hold'


@POSIX
@pytest.mark.parametrize('fact',['helper_death','validator_death','supervisor_death','deadline','oom','cleanup','mount','residual_fd'])
def test_K07_unknown_failure_holds_running_job_and_never_enables_next_fifo(fact):
    from app.db_audit_coordinator.r4_release import Session
    class Owner:
        orphan_hold=False
        def __init__(self):self.value=dict(jobs=[dict(job_id='fixture',reason_code='running',state='running'),dict(state='queued')]);self.writes=0
        def _state(self):return copy.deepcopy(self.value)
        def _commit(self,value):self.value=value;self.writes+=1
    subject=Session.__new__(Session);subject.owner=Owner();subject.job=dict(job_id='fixture')
    subject.held=False;subject.done=False
    def fail():raise RuntimeError(fact)
    subject.guard=fail
    assert subject.pump() is False and subject.held and subject.owner.orphan_hold
    assert subject.owner.value['jobs'][0]['state']=='running'
    assert subject.owner.value['jobs'][0]['reason_code']=='orphan_hold'
    assert subject.owner.value['jobs'][1]['state']=='queued' and subject.owner.writes==1
    assert subject.pump() is False and subject.owner.writes==1


@pytest.mark.parametrize('extra',['DirectMap4k: 1024 kB','DirectMap2M: 2048 kB','DirectMap1G: 0 kB'])
def test_K03_native_meminfo_numeric_field_names_do_not_invent_missing_reserve(extra):
    from app.db_audit_coordinator.live_receipts import meminfo
    assert meminfo('MemTotal: 8192 kB\nMemAvailable: 4096 kB\n'+extra)==4096*1024


@pytest.mark.parametrize('text',['MemTotal: 1 kB\nMemAvailable: 2 kB',
    'MemTotal: 8 kB\nMemAvailable: 4 kB\nDirectMap4k: -1 kB',
    'MemTotal: 8 kB\nMemAvailable: 4 kB\nDirectMap4k: 1 MB',
    'MemTotal: 8 kB\nMemAvailable: 4 kB\nMemAvailable: 4 kB',
    'MemTotal: 8 kB\nMemAvailable: 4 kB\n4Wrong: 1 kB'])
def test_K03_malformed_or_duplicate_kernel_fields_are_still_fail_closed(text):
    from app.db_audit_coordinator.live_receipts import meminfo
    with pytest.raises(c.CoordinatorError):meminfo(text)


@POSIX
@pytest.mark.parametrize('elapsed',[1201,5401])
def test_04K_R4_age_never_holds_or_kills_and_legacy_deadline_still_expires(monkeypatch,elapsed):
    from types import SimpleNamespace
    from app.db_audit_coordinator import live_coordinator as runtime
    from app.db_audit_coordinator.r4_release import Session
    subject=Session.__new__(Session);subject.deadline=None;subject.done=False
    ledger=[]
    subject.hold=lambda:ledger.append('durable_orphan_hold')
    class Leaf:
        def write(self,key,value):assert (key,value)==('cgroup.kill','1');ledger.append('exact_leaf_kill')
    subject.leaf=Leaf()
    monkeypatch.setattr(runtime.time,'monotonic',lambda:elapsed)
    monkeypatch.setattr(runtime.time,'monotonic_ns',lambda:elapsed*10**9)
    root=runtime.LiveCoordinator.__new__(runtime.LiveCoordinator);root._r4=subject
    assert root.timeout() is None
    subject.expire();root.expire();root.expire()
    assert ledger==[] and not subject.done
    # Exact unchanged non-R4 branch still signals cancellation, then kills only
    # its own leaf after the existing two-second grace. No R4 path is involved.
    root._r4=None;root.process=SimpleNamespace(returncode=None)
    root._deadline=1200;root._abort_at=None;root._killed=False;root._leaf=Leaf()
    def cancel():ledger.append('cancel');root._abort_at=elapsed+2
    root._notify_cancel=cancel
    assert root.timeout()==0
    root.expire();assert ledger==['cancel'] and root.timeout()==2
    monkeypatch.setattr(runtime.time,'monotonic',lambda:elapsed+2)
    root.expire();root.expire()
    assert ledger==['cancel','exact_leaf_kill'] and root._killed


@pytest.mark.skipif(sys.platform!='linux' or getattr(os,'geteuid',lambda:0)()==0,
    reason='requires actual nonroot Linux caller; separate root mechanics suite')
def test_K10_nonroot_cannot_enter_mount_bootstrap_or_owner_helper():
    from app.db_audit_coordinator.r4_sandbox import MountNamespace
    from app.db_audit_coordinator.r4_owner_helper import run
    with pytest.raises(c.CoordinatorError):MountNamespace().enter()
    with pytest.raises(c.CoordinatorError):run(0)


@pytest.mark.parametrize('store',STORES)
@pytest.mark.parametrize('fault',['positive','user_version','missing_table','index','domain'])
def test_K06_dependency_complete_clean_python_uses_exact_canonical_store_t3(store,fault):
    from tests.db_audit_coordinator.test_b2_live_sqlite import initialize
    from app.db_audit_coordinator.live_sqlite import validate_snapshot
    db=sqlite3.connect(':memory:',isolation_level=None);db.row_factory=sqlite3.Row
    try:
        initialize(db,store)
        if fault=='user_version':db.execute('PRAGMA user_version=99')
        elif fault=='missing_table':
            table={'public_traffic':'counter_state','network_service_intelligence':'service_materialization_runtime',
                'traffic_projection':'traffic_projection_runtime'}[store]
            # Exact first required table is discovered solely from the fixture,
            # never a production/source selector or validator relaxation.
            if db.execute('SELECT 1 FROM sqlite_master WHERE type=? AND name=?',('table',table)).fetchone() is None:
                table=db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchone()[0]
            db.execute('DROP TABLE '+table)
        elif fault=='index':
            index=db.execute("SELECT name FROM sqlite_master WHERE type='index' AND sql IS NOT NULL ORDER BY name").fetchone()
            assert index is not None
            db.execute('DROP INDEX '+index[0])
        elif fault=='domain':
            if store=='public_traffic':
                db.execute('PRAGMA ignore_check_constraints=ON');db.execute('UPDATE traffic_daily SET traffic_bytes=-1')
            elif store=='network_service_intelligence':
                db.execute("UPDATE service_materialization_generations SET ruleset_digest_sha256='bad'")
            else:
                # Unknown extra schema is a canonical schema/domain violation,
                # even though PRAGMA integrity_check reports ok.
                db.execute('CREATE TABLE forbidden_extra(value)')
        if fault=='positive':assert validate_snapshot(db,policy(store),lambda:None)['schema_version']==policy(store).schema_version
        else:
            with pytest.raises(Exception):validate_snapshot(db,policy(store),lambda:None)
    finally:db.close()


@pytest.mark.parametrize('check',[
    'sqlite_user_version','sqlite_integrity','sqlite_foreign_key','pt_schema_signature','pt_counter_singleton',
    'pt_traffic_daily_date','pt_traffic_daily_numeric','pt_event_type','pt_event_offset_order',
    'pt_event_counted_fields','pt_event_event_date','pt_reader_offset','pt_reader_flags',
    'pt_reset_scope','pt_reset_numeric','pt_watermark_encode'])
def test_04H_closed_A_predicates_keep_canonical_rejection_and_no_row_leak(check,record_property):
    from app.db_audit_coordinator.live_sqlite import T3Trace,validate_snapshot
    from app.db_audit_coordinator.adapter_public_traffic import validate
    from tests.db_audit_coordinator.test_b2_live_sqlite import initialize,AT
    db=sqlite3.connect(':memory:',isolation_level=None);db.row_factory=sqlite3.Row
    initialize(db,'public_traffic');trace=T3Trace()
    # Only disposable fixtures. Canonical full integrity stays enabled and can
    # legitimately reject CHECK violations BEFORE a later adapter assertion.
    db.execute('PRAGMA ignore_check_constraints=ON')
    if check=='sqlite_user_version':db.execute('PRAGMA user_version=99')
    elif check=='sqlite_integrity':db.execute('UPDATE traffic_daily SET traffic_bytes=-1')
    elif check=='sqlite_foreign_key':
        db.execute('CREATE TABLE fixture_parent(id PRIMARY KEY)')
        db.execute('CREATE TABLE fixture_child(id REFERENCES fixture_parent(id))')
        db.execute('INSERT INTO fixture_child VALUES(1)')
    elif check=='pt_schema_signature':db.execute('CREATE TABLE forbidden_extra(x)')
    elif check=='pt_counter_singleton':db.execute('DELETE FROM counter_state')
    elif check=='pt_traffic_daily_date':db.execute("UPDATE traffic_daily SET local_date='bad-secret-date'")
    elif check=='pt_traffic_daily_numeric':
        db.execute('UPDATE traffic_daily SET traffic_bytes=?',(2**63-1,))
        db.execute('INSERT INTO traffic_daily VALUES(?,?,?,?,?)',('2026-10-18','synthetic-ssid',1,1,AT))
    elif check.startswith('pt_event_'):
        event=dict(normalized_event_id='secret-id',ssid='secret-ssid',event_type='omada.client_offline',event_local_date='2026-10-19',
            event_traffic_bytes=1,counted=1,skip_reason=None,source_identity='source-secret',source_path='/secret/source',
            source_offset_start=0,source_offset_end=1,processed_at=AT)
        if check=='pt_event_type':event['event_type']='secret-event'
        elif check=='pt_event_offset_order':event['source_offset_start']=2
        elif check=='pt_event_counted_fields':event['skip_reason']='secret-reason'
        else:event['event_local_date']='invalid-secret-date'
        db.execute('INSERT INTO processed_events('+','.join(event)+') VALUES('+','.join('?' for _ in event)+')',tuple(event.values()))
    elif check in ('pt_reader_offset','pt_reader_flags'):
        db.execute('INSERT INTO reader_state(source_identity,source_path,source_offset,retired_completed,updated_at) VALUES(?,?,?,?,?)',
            ('secret-id','/secret/path',-1 if check=='pt_reader_offset' else 0,2 if check=='pt_reader_flags' else 0,AT))
    elif check in ('pt_reset_scope','pt_reset_numeric'):
        db.execute('INSERT INTO counter_resets(reset_id,reset_scope,reset_at,previous_today_bytes) VALUES(?,?,?,?)',
            (str(uuid.uuid4()),'invalid-secret' if check=='pt_reset_scope' else 'all',AT,-1 if check=='pt_reset_numeric' else 0))
    else:db.execute('UPDATE traffic_daily SET updated_at=?',(b'private-blob',))
    db.execute('PRAGMA ignore_check_constraints=OFF')
    try:
        if check.startswith('pt_'):
            with pytest.raises(Exception):validate(db,lambda:None,check=trace.mark)
            assert trace.check==check
        full=T3Trace()
        with pytest.raises(Exception) as caught:validate_snapshot(db,policy('public_traffic'),lambda:None,trace=full)
        full.fail(caught.value,'domain')
        # CHECK-protected malformed reader/reset-scope rows are correctly
        # caught by full SQLite integrity first. Do NOT bypass it to force a
        # more convenient later diagnostic or claim that later check executed.
        expected='sqlite_integrity' if check in {'pt_reader_offset','pt_reader_flags','pt_reset_scope'} else check
        assert full.check==expected
        output=full.document();assert output['category']=='domain'
        assert not any(value in c.encode(output).decode() for value in ('secret','private-blob','/source','SELECT','UPDATE'))
        record_property('04h_A_closed_predicate',json.dumps(dict(adapter_check=trace.check,actual_full_check=full.check,diagnostic=output)))
    finally:db.close()


@pytest.mark.parametrize('fault',[{'check':'SELECT private'},{'stage':'secret'},{'exception_class':'secret'},
    {'guard_fast_count':True},{'guard_fast_count':100001},{'digest_full_count':4},{'elapsed_ms':-1},
    {'adapter_validate_ms':1.2},{'extra':'private-row'},{'category':'audit_passed'}])
def test_04H_root_private_T3_diagnostic_is_closed_non_authoritative_and_not_durable(fault,monkeypatch):
    from app.db_audit_coordinator import r4_release
    from app.db_audit_coordinator.live_sqlite import T3Trace
    subject=r4_release.Session.__new__(r4_release.Session);subject.decision=None
    logs=[];monkeypatch.setattr(r4_release,'emit_hold',logs.append)
    payload=dict(result='failed',reason_code='audit_failed',snapshot_metadata=None,
        t3_diagnostic=dict(T3Trace().document(),**fault))
    with pytest.raises(Exception):subject.t3_outcome(payload)
    assert subject.decision is None and logs==[]


def test_04H_exact_one_optional_private_report_never_changes_legacy_result(monkeypatch):
    from app.db_audit_coordinator import r4_release
    from app.db_audit_coordinator.live_sqlite import T3Trace
    logs=[];monkeypatch.setattr(r4_release,'emit_hold',logs.append)
    for reported in (False,True):
        subject=r4_release.Session.__new__(r4_release.Session);subject.decision=None
        payload=dict(result='failed',reason_code='audit_failed',snapshot_metadata=None)
        if reported:payload['t3_diagnostic']=T3Trace().document()
        subject.t3_outcome(payload)
        assert subject.decision==dict(result='failed',reason_code='audit_failed',snapshot_metadata=None)
        with pytest.raises(c.CoordinatorError):subject.t3_outcome(payload)
    assert len(logs)==2 and logs[0]['check']=='unreported'
    assert not any(word in c.encode(logs).decode() for word in ('snapshot_metadata','job_id','source_path'))


def test_04H_trace_clamps_counts_and_never_relabels_resource_interrupt_as_domain():
    from app.db_audit_coordinator.live_sqlite import T3Trace
    trace=T3Trace()
    for key in ('guard_fast_count','progress_callbacks'):trace.count(key,200000)
    trace.mark('resource_guard');trace.fail(c.CoordinatorError('canceled'),'resource_guard')
    trace.fail(sqlite3.OperationalError('private SQL interrupted'),'domain')
    document=trace.document()
    assert document['guard_fast_count']==document['progress_callbacks']==100000
    assert document['category']=='resource_guard' and document['check']=='resource_guard'
    assert document['exception_class']=='CoordinatorError'


def test_04H_broken_root_diagnostic_sink_cannot_promote_or_change_T3_result(monkeypatch):
    from app.db_audit_coordinator import r4_release
    from app.db_audit_coordinator.live_sqlite import T3Trace
    def broken(_):raise OSError('private log unavailable')
    monkeypatch.setattr(r4_release,'emit_hold',broken)
    subject=r4_release.Session.__new__(r4_release.Session);subject.decision=None
    subject.t3_outcome(dict(result='failed',reason_code='audit_failed',snapshot_metadata=None,t3_diagnostic=T3Trace().document()))
    assert subject.decision==dict(result='failed',reason_code='audit_failed',snapshot_metadata=None)


def test_04I_same_connection_full_integrity_and_FK_once_before_structural_adapter(monkeypatch):
    from app.db_audit_coordinator.live_sqlite import validate_snapshot,T3Trace
    from app.traffic_projection.repository import TrafficProjectionRepository
    from tests.db_audit_coordinator.test_b2_live_sqlite import initialize
    db=sqlite3.connect(':memory:',isolation_level=None);db.row_factory=sqlite3.Row
    initialize(db,'traffic_projection');statements=[];calls=[]
    original=TrafficProjectionRepository._validate
    def canonical(connection,*,deep):
        assert connection is db
        assert [s for s in statements if s in {'PRAGMA integrity_check','PRAGMA foreign_key_check'}]==[
            'PRAGMA integrity_check','PRAGMA foreign_key_check']
        calls.append(deep);return original(connection,deep=deep)
    monkeypatch.setattr(TrafficProjectionRepository,'_validate',staticmethod(canonical))
    db.set_trace_callback(statements.append)
    try:
        output=validate_snapshot(db,policy('traffic_projection'),lambda:None,trace=T3Trace())
        assert output['schema_version']==1 and calls==[False]
        assert statements.count('PRAGMA integrity_check')==statements.count('PRAGMA foreign_key_check')==1
        assert 'PRAGMA quick_check' not in statements
        assert any(s.startswith('PRAGMA table_info(') for s in statements)
        assert any(s.startswith('PRAGMA index_info(') for s in statements)
    finally:db.close()


def test_04I_normal_repository_deep_validation_retains_its_original_scans():
    from app.traffic_projection.repository import TrafficProjectionRepository
    from tests.db_audit_coordinator.test_b2_live_sqlite import initialize
    db=sqlite3.connect(':memory:',isolation_level=None);initialize(db,'traffic_projection')
    statements=[];db.set_trace_callback(statements.append)
    try:
        TrafficProjectionRepository._validate(db,deep=True)
        assert statements.count('PRAGMA foreign_key_check')==statements.count('PRAGMA quick_check')==1
    finally:db.close()


@pytest.mark.parametrize('fault',['CHECK','FK','index_content','UNIQUE','schema','domain'])
def test_04I_original_full_gates_reject_corruption_before_any_domain_downgrade(tmp_path,fault,monkeypatch,record_property):
    from app.db_audit_coordinator.live_sqlite import validate_snapshot,T3Trace
    from app.traffic_projection.repository import schema_sql
    from app.traffic_projection.models import PROJECTION_VERSION,SEMANTIC_CONTRACT_SHA256
    from app.db_audit_coordinator import adapter_traffic_projection as adapter
    path=tmp_path/'disposable-C.db';db=sqlite3.connect(path,isolation_level=None)
    db.executescript(schema_sql());at='2026-10-19T00:00:00.000Z'
    insert='INSERT INTO traffic_projection_versions(projection_version,projection_schema_version,source,source_schema_version,semantic_contract_sha256,status,created_at) VALUES(?,1,?,1,?,?,?)'
    db.execute(insert,(PROJECTION_VERSION,'observations',SEMANTIC_CONTRACT_SHA256,'active',at))
    if fault=='CHECK':
        db.execute('PRAGMA ignore_check_constraints=ON')
        db.execute("INSERT INTO traffic_projection_site_state(projection_version,site_id,projection_revision,status) VALUES(?,?,-1,'healthy')",(PROJECTION_VERSION,'fixture'))
        db.execute('PRAGMA ignore_check_constraints=OFF')
    elif fault=='FK':
        db.execute("INSERT INTO traffic_projection_site_state(projection_version,site_id,projection_revision,status) VALUES('missing-parent','fixture',0,'healthy')")
    elif fault=='index_content':
        # Physical index/table inconsistency, not a relaxed schema predicate.
        db.execute("INSERT INTO traffic_projection_site_state(projection_version,site_id,projection_revision,status) VALUES(?, 'fixture',0,'healthy')",(PROJECTION_VERSION,))
        target=db.execute("SELECT rootpage FROM sqlite_schema WHERE name='idx_projection_ap_identity'").fetchone()[0]
        db.execute('PRAGMA writable_schema=ON')
        db.execute("UPDATE sqlite_schema SET rootpage=? WHERE name='sqlite_autoindex_traffic_projection_site_state_1'",(target,))
        db.execute('PRAGMA writable_schema=OFF')
    elif fault=='UNIQUE':
        original=db.execute("SELECT sql FROM sqlite_schema WHERE name='idx_projection_one_active'").fetchone()[0]
        db.execute('DROP INDEX idx_projection_one_active')
        db.execute(original.replace('CREATE UNIQUE INDEX','CREATE INDEX'))
        db.execute(insert,('fixture-second-version','observations',SEMANTIC_CONTRACT_SHA256,'active',at))
        db.execute('PRAGMA writable_schema=ON')
        db.execute("UPDATE sqlite_schema SET sql=? WHERE name='idx_projection_one_active'",(original,))
        db.execute('PRAGMA writable_schema=OFF')
    elif fault=='schema':db.execute('DROP INDEX idx_projection_cycles_started')
    else:
        db.execute(insert,('invalid version!','observations',SEMANTIC_CONTRACT_SHA256,'retired',at))
    db.close()
    # Read-only reopen forces SQLite to load the fixture's real on-disk index
    # flags/schema. No source production DB or custom result stub is involved.
    before=path.read_bytes();db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,isolation_level=None)
    db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON');db.execute('PRAGMA foreign_keys=ON')
    # Native SQLite 3.37.2 may not diagnose this CHECK after a mode=ro reopen.
    # Establish that quick_check has NO extra coverage on that same connection;
    # the unchanged adapter numeric guard must still reject it in that case.
    native_check_detected=True
    if fault=='CHECK':
        full=tuple(tuple(row) for row in db.execute('PRAGMA integrity_check'))
        quick=tuple(tuple(row) for row in db.execute('PRAGMA quick_check'))
        assert full==quick
        native_check_detected=full!=(('ok',),)
    trace=T3Trace();entered=[];validate=adapter.validate
    def observed(*args,**kwargs):entered.append(True);return validate(*args,**kwargs)
    monkeypatch.setattr(adapter,'validate',observed)
    try:
        with pytest.raises(Exception):validate_snapshot(db,policy('traffic_projection'),lambda:None,trace=trace)
        expected='sqlite_foreign_key' if fault=='FK' else 'tp_canonical_deep' if fault=='schema' else 'tp_versions' if fault=='domain' else 'tp_site_state' if fault=='CHECK' and not native_check_detected else 'sqlite_integrity'
        assert trace.check==expected,(fault,trace.check)
        assert bool(entered)==(fault in {'schema','domain'} or fault=='CHECK' and not native_check_detected)
        record_property('04i_corruption_gate',json.dumps(dict(fault=fault,check=trace.check,adapter_entered=bool(entered),native_check_detected=native_check_detected)))
    finally:db.close()
    assert path.read_bytes()==before


def proposed_04I_ddl_tokens(sql):
    """TEST/PROPOSAL ONLY. No production adapter imports this comparator.

    Drop only whitespace BETWEEN lexical tokens; retain case, token spelling,
    quoted literal/identifier bytes, comments and operators. Uncertain syntax
    is refused, never accepted through generic split()/regex normalization.
    """
    import re
    if type(sql) is not str or not 0<len(sql)<=32768:raise ValueError('unsupported DDL')
    tokens=[];position=0
    while position<len(sql):
        char=sql[position]
        if char in ' \t\n\r\f':position+=1;continue
        start=position
        if char in "'\"`[":
            end=']' if char=='[' else char;position+=1
            while position<len(sql):
                if sql[position]==end:
                    if end!=']' and position+1<len(sql) and sql[position+1]==end:position+=2;continue
                    position+=1;break
                position+=1
            else:raise ValueError('unsupported DDL')
        elif sql.startswith('--',position):
            end=sql.find('\n',position);position=len(sql) if end<0 else end
        elif sql.startswith('/*',position):
            end=sql.find('*/',position+2)
            if end<0:raise ValueError('unsupported DDL')
            position=end+2
        else:
            match=re.match(r'(?:[A-Za-z_][A-Za-z0-9_$]*|0[xX][0-9a-fA-F]+|(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?|->>|->|>=|<=|<>|!=|==|\|\||<<|>>|[(),;.+*/%<>=!~&|?:-])',sql[position:])
            if match is None:raise ValueError('unsupported DDL')
            position+=len(match.group())
        tokens.append(sql[start:position])
        if len(tokens)>4096:raise ValueError('unsupported DDL')
    return tuple(tokens)


def proposed_04I_schema_diff(expected,actual):
    """Closed classifications/digests only, never return raw SQL or unknown names."""
    expected_by={(row[0],row[1],row[2]):row for row in expected}
    actual_by={(row[0],row[1],row[2]):row for row in actual}
    assert len(expected_by)==len(expected) and len(actual_by)==len(actual)
    differences=[]
    for key in sorted(expected_by.keys() & actual_by.keys()):
        left,right=expected_by[key],actual_by[key]
        if left==right:continue
        try:kind='whitespace_only_candidate' if proposed_04I_ddl_tokens(left[3])==proposed_04I_ddl_tokens(right[3]) else 'structural_or_literal_difference'
        except ValueError:kind='unsupported_lexical_form'
        differences.append(dict(type=key[0],name=key[1],classification=kind,
            expected_sha256=hashlib.sha256(c.encode(left)).hexdigest(),actual_sha256=hashlib.sha256(c.encode(right)).hexdigest()))
    return dict(missing=len(expected_by.keys()-actual_by.keys()),extra=len(actual_by.keys()-expected_by.keys()),
        different=len(differences),objects=differences,expected_sha256=hashlib.sha256(c.encode(expected)).hexdigest(),
        actual_sha256=hashlib.sha256(c.encode(actual)).hexdigest())


def test_04I_A_seven_object_lexical_proposal_never_changes_current_exact_predicate(record_property):
    from app.db_audit_coordinator.adapter_public_traffic import expected_signature,signature,validate
    expected=expected_signature()
    actual=tuple((*row[:3], ' \n '.join(proposed_04I_ddl_tokens(row[3]))) for row in expected)
    report=proposed_04I_schema_diff(expected,actual)
    assert report['missing']==report['extra']==0 and report['different']==7
    assert all(row['classification']=='whitespace_only_candidate' for row in report['objects'])
    # Generate real disposable tables/indexes from the variant DDL. Current
    # canonical acceptance still rejects it, as required pending adjudication.
    db=sqlite3.connect(':memory:',isolation_level=None);db.row_factory=sqlite3.Row
    try:
        for kind,name,table,sql in actual:
            if kind=='table':db.execute(sql)
        for kind,name,table,sql in actual:
            if kind=='index':db.execute(sql)
        db.execute('PRAGMA user_version=2')
        assert signature(db)!=expected
        with pytest.raises(c.CoordinatorError):validate(db,lambda:None)
        record_property('04i_A_schema_proposal',json.dumps(report,sort_keys=True))
    finally:db.close()


@pytest.mark.parametrize('left,right',[
    ("CHECK(x='a  b')","CHECK(x='a b')"),('CREATE TABLE "a  b"(x)','CREATE TABLE "a b"(x)'),
    ('CHECK(x>=1)','CHECK(x> =1)'),('CHECK(x IS NOT NULL)','CHECK(x IS NOTNULL)'),
    ('CHECK(x=1)','CHECK(x=1.0)'),('CHECK(x=1)','CHECK(x=2)'),
    ("CHECK(x='it''s  x')","CHECK(x='it''s x')"),('CHECK(x COLLATE BINARY)','CHECK(x COLLATE NOCASE)'),
    ('CHECK(x /* a  b */ =1)','CHECK(x /* a b */ =1)'),
    ('CREATE TABLE t(x INTEGER)','CREATE TABLE t(x TEXT)'),
])
def test_04I_A_lexical_proposal_preserves_literals_identifiers_types_and_operators(left,right):
    assert proposed_04I_ddl_tokens(left)!=proposed_04I_ddl_tokens(right)


@pytest.mark.parametrize('sql',["CREATE TABLE t(x DEFAULT 'unterminated)",'CREATE TABLE [unclosed(x)',
    'CREATE TABLE t(x /* never closed)','CREATE\u00a0TABLE t(x)',None,'','x'*32769],
    ids=['unclosed_string','unclosed_identifier','unclosed_comment','non_SQL_whitespace','none','empty','oversize'])
def test_04I_A_lexical_uncertainty_is_not_equivalence(sql):
    with pytest.raises(ValueError):proposed_04I_ddl_tokens(sql)


def compile_04J_guard(namespace):
    """Execute the actual nested body, without adding a production test seam."""
    import ast
    source=Path(__file__).resolve().parents[2]/'app/db_audit_coordinator/child_bootstrap.py'
    tree=ast.parse(source.read_text(encoding='utf-8'))
    outer=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='execute_r4')
    guard=next(n for n in outer.body if isinstance(n,ast.FunctionDef) and n.name=='guard')
    exec(compile(ast.Module(body=[guard],type_ignores=[]),str(source),'exec'),namespace)
    return namespace['guard']


@pytest.mark.parametrize('fault',['none','gate','leaf','cancel','membership',
    'memory_max','swap_max','swap_current','ancestor'])
def test_04J_each_guard_uses_one_fresh_complete_sample_and_exact_failure(fault):
    from types import SimpleNamespace
    trace=[];observations=[];received=[]
    def check(name):
        trace.append(name)
        if fault==name:raise c.CoordinatorError('unsafe_path' if name in {'gate','leaf'} else 'not_admitted')
    def samples():
        trace.append('samples')
        nodes=(object(),SimpleNamespace(maximum=1 if fault=='memory_max' else 128,
            swap_max=1 if fault=='swap_max' else 0,swap_current=1 if fault=='swap_current' else 0))
        observations.append(nodes);return nodes
    def guest(nodes):
        trace.append('guest');received.append(nodes)
        def validate():
            trace.append('sample_check')
            if fault=='ancestor':raise c.CoordinatorError('not_admitted')
        return SimpleNamespace(check=validate)
    def member(pid):trace.append('membership');return '/wrong' if fault=='membership' else '/leaf'
    def select_ready(*args):trace.append('cancel');return ([7] if fault=='cancel' else [],[],[])
    namespace=dict(deadline=SimpleNamespace(check=lambda:check('deadline')),
        gate=SimpleNamespace(check=lambda:check('gate')),leaf=SimpleNamespace(check=lambda:check('leaf'),
        samples=samples,relative='/leaf'),data={'cancel_fd':7},policy=SimpleNamespace(memory_max_bytes=128),
        os=SimpleNamespace(getpid=lambda:42),select=SimpleNamespace(select=select_ready),
        membership=member,guest_sample=guest,require=p.require,c=c)
    guard=compile_04J_guard(namespace)
    if fault=='none':
        guard();guard()
        one=['gate','leaf','cancel','membership','samples','guest','sample_check']
        assert trace==one*2 and observations[0] is not observations[1]
        assert all(actual is supplied for actual,supplied in zip(observations,received))
    else:
        with pytest.raises(c.CoordinatorError) as error:guard()
        # Existing closed CoordinatorError normalizes the internal 'canceled'
        # token; the runtime's result mapping still emits canceled separately.
        expected='coordinator_unavailable' if fault=='cancel' else 'unauthorized' if fault=='membership' else 'unsafe_path' if fault in {'gate','leaf'} else 'not_admitted'
        assert error.value.code==expected and error.value.code!='audit_failed'
        assert len(observations)==int(fault in {'memory_max','swap_max','swap_current','ancestor'})


def test_04J_cancel_false_preserves_cleanup_checks_but_does_not_read_cancel_pipe():
    from types import SimpleNamespace
    calls=[];nodes=(SimpleNamespace(maximum=128,swap_max=0,swap_current=0),)
    namespace=dict(deadline=SimpleNamespace(check=lambda:calls.append('deadline')),
        gate=SimpleNamespace(check=lambda:calls.append('gate')),leaf=SimpleNamespace(
            check=lambda:calls.append('leaf'),samples=lambda:calls.append('samples') or nodes,relative='/leaf'),
        policy=SimpleNamespace(memory_max_bytes=128),data={'cancel_fd':7},os=SimpleNamespace(getpid=lambda:42),
        select=SimpleNamespace(select=lambda *a:pytest.fail('cleanup cancel=False must not poll pipe')),
        membership=lambda pid:'/leaf',guest_sample=lambda sample:SimpleNamespace(check=lambda:calls.append('full_check')),
        require=p.require,c=c)
    compile_04J_guard(namespace)(cancel=False)
    assert calls==['gate','leaf','samples','full_check']


@POSIX
@pytest.mark.parametrize('peer',['packet','EOF'])
@pytest.mark.parametrize('elapsed',[1201,5401])
def test_04K_no_deadline_authenticated_socket_wait_uses_actual_packet_or_EOF(monkeypatch,peer,elapsed):
    import threading
    import time
    from app.db_audit_coordinator import r4_ipc
    left,right=r4_ipc.pair();entered=threading.Event();done=threading.Event();outcomes=[]
    monkeypatch.setattr(time,'monotonic_ns',lambda:elapsed*10**9)
    def receive():
        try:
            entered.set()
            outcomes.append(r4_ipc.receive(left,'a'*64,os.geteuid(),os.getpid(),seconds=None))
        except c.CoordinatorError as error:outcomes.append(error.code)
        finally:done.set()
    reader=threading.Thread(target=receive,daemon=True);reader.start()
    try:
        assert entered.wait(1)
        if peer=='packet':r4_ipc.send(right,'cancel','a'*64,{})
        else:right.close()
        assert done.wait(1)
        reader.join(1);assert not reader.is_alive()
        assert outcomes==[('cancel',{},None)] if peer=='packet' else outcomes==['unauthorized']
        assert left.gettimeout() is None
    finally:
        right.close();left.close()


def test_04K_R1_all_R4_send_and_receive_sites_are_explicitly_unbounded():
    import ast
    root=Path(__file__).resolve().parents[2]/'app/db_audit_coordinator'
    sends=[];receives=[]
    for filename in ('child_bootstrap.py','r4_release.py','r4_owner_helper.py'):
        tree=ast.parse((root/filename).read_text(encoding='utf-8'))
        if filename=='child_bootstrap.py':
            tree=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='execute_r4')
        for node in ast.walk(tree):
            if not (isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
                    and isinstance(node.func.value,ast.Name) and node.func.value.id=='r4_ipc'):continue
            if node.func.attr not in {'send','receive'}:continue
            seconds=[kw.value for kw in node.keywords if kw.arg=='seconds']
            assert len(seconds)==1 and isinstance(seconds[0],ast.Constant) and seconds[0].value is None
            if node.func.attr=='send':sends.append(node.args[1].value)
            else:receives.append(filename)
    assert sorted(sends)==sorted(['gate_ready','t3_done','released','cancel','begin','snapshot','cancel',
                                  'release','owner_ready','owner_done'])
    assert len(receives)==4
    tree=ast.parse((root/'r4_release.py').read_text())
    joins=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='join']
    assert len(joins)==1 and joins[0].args==[] and joins[0].keywords==[]


@POSIX
@pytest.mark.parametrize('peer',['alive','closed'])
def test_04K_R1_delayed_authenticated_cancel_send_has_no_one_second_cap(peer,record_property):
    from app.db_audit_coordinator import r4_ipc
    left,right=r4_ipc.pair();clock=[0.0];settings=[]
    class DelayedEndpoint:
        def settimeout(self,value):settings.append(value);left.settimeout(value)
        def sendmsg(self,*args):
            clock[0]+=2.0  # Controlled scheduling delay, not a real wall wait.
            assert left.gettimeout() is None and clock[0]>1
            return left.sendmsg(*args)  # Actual authenticated kernel transport.
    try:
        if peer=='closed':right.close()
        if peer=='alive':
            r4_ipc.send(DelayedEndpoint(),'cancel','a'*64,{},seconds=None)
            assert r4_ipc.receive(right,'a'*64,os.geteuid(),os.getpid(),seconds=None)==('cancel',{},None)
        else:
            with pytest.raises(OSError):r4_ipc.send(DelayedEndpoint(),'cancel','a'*64,{},seconds=None)
        assert settings==[None]
        record_property('04k_r1_delayed_send',json.dumps(dict(simulated_delay=clock[0],seconds=None,peer=peer)))
    finally:left.close();right.close()


@POSIX
@pytest.mark.parametrize('possible_method',['R4','legacy'])
def test_04K_R1_pre_auth_300s_is_unresolved_before_method_can_be_trusted(monkeypatch,possible_method,record_property):
    """Exact existing FIFO reader: same entry capability cannot distinguish jobs.

    The bytes are deliberately not adopted as authorization; r4_fd presence
    must NEVER act as a trusted timeout switch. No protocol/source alteration.
    """
    from app.db_audit_coordinator import child_bootstrap as worker
    read,write=os.pipe();clock=[0.0];payload=c.encode({'r4_fd':42} if possible_method=='R4' else {})
    native_select=worker.select.select;decoded=[]
    monkeypatch.setattr(worker.time,'monotonic',lambda:clock[0])
    def delayed_ready(*args):
        clock[0]=301.0  # Scheduling resumes after the fixed bootstrap budget.
        return native_select(*args[:-1],0)
    monkeypatch.setattr(worker.select,'select',delayed_ready)
    decode=worker.c.decode
    monkeypatch.setattr(worker.c,'decode',lambda *args:decoded.append(True) or decode(*args))
    try:
        os.write(write,payload);os.close(write);write=None
        with pytest.raises(c.CoordinatorError) as error:worker.pipe_data(read,300)
        assert error.value.code=='unauthorized' and decoded==[]
        record_property('04k_r1_bootstrap_hold',json.dumps(dict(method_not_yet_trusted=possible_method,
            resumed_seconds=clock[0],result=error.value.code,status='UNRESOLVED_PRE_ADMISSION')))
    finally:
        os.close(read)
        if write is not None:os.close(write)


@pytest.mark.skipif(sys.platform!='linux' or getattr(os,'geteuid',lambda:0)()==0,
    reason='actual nonroot sealed worker claim; root cannot impersonate its worker profile')
def test_04K_R1_eligible_sealed_R4_claim_rejected_only_after_bootstrap_clock_jump(monkeypatch,record_property):
    from app.db_audit_coordinator import child_bootstrap as worker
    # Existing genuine sealed-claim fixture first proves this method is eligible,
    # including current UID/GID, parent, nonce, pipe identity and exact metadata.
    test_04C_sealed_job_store_change_cannot_reuse_another_source_authority(False)
    native_select=worker.select.select;clock=[0.0]
    monkeypatch.setattr(worker.time,'monotonic',lambda:clock[0])
    def late(*args):clock[0]=301.0;return native_select(*args[:-1],0)
    monkeypatch.setattr(worker.select,'select',late)
    before=set(os.listdir('/proc/self/fd'))
    try:
        with pytest.raises(c.CoordinatorError) as error:
            test_04C_sealed_job_store_change_cannot_reuse_another_source_authority(False)
        assert error.value.code=='unauthorized'
        record_property('04k_r1_eligible_bootstrap_hold',json.dumps(dict(
            genuine_sealed_R4_without_jump='AUTHORIZED',clock_jump_s=301,
            with_jump='unauthorized_before_auth',status='UNRESOLVED_PRE_ADMISSION')))
    finally:
        # authorize closes auth FD only after pipe_data returns. The deliberate
        # pre-read failure retains that one fixture-owned FIFO; close it here.
        for number in set(os.listdir('/proc/self/fd'))-before:
            try:os.close(int(number))
            except OSError:pass
