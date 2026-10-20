"""Closed R4 policy, IPC and failure fences; no original LAB access."""
from dataclasses import asdict,replace
import copy
import hashlib
import os
from pathlib import Path
import socket
import sqlite3
import sys
import uuid

import pytest

from app.db_audit_coordinator import contracts as c,live_policy as p
from app.db_audit_coordinator.live_profile import PilotProfile,R4Installation
from tests.db_audit_coordinator.test_b2_live_policy import profile,policy,STORES

POSIX=pytest.mark.skipif(sys.platform!='linux',reason='R4 native Unix descriptor/credentials contract')


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
    install=R4Installation(p.R4_METHOD,False,1000,1000,'/run/captive-portal/db-audit/ram-jobs',1,2,8,64)
    assert replace(value,r4=install).metadata('public_traffic')[0]==p.METHOD
    enabled=replace(value,r4=replace(install,enabled=True))
    assert all(enabled.metadata(store)[0]==p.R4_METHOD for store in STORES)
    assert PilotProfile.parse(c.decode(c.encode(asdict(enabled))))==enabled


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
    fields=dict(method=p.R4_METHOD,enabled=True,owner_uid=1000,owner_gid=1000,
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
def test_K10_snapshot_rights_are_new_readonly_cloexec_descriptor(tmp_path):
    from app.db_audit_coordinator import r4_ipc
    left,right=r4_ipc.pair();target=tmp_path/'image';target.write_bytes(b'synthetic')
    fd=os.open(target,os.O_RDONLY);received=None
    try:
        r4_ipc.send(right,'snapshot','1'*64,dict(image='fixture-only'),fd=fd)
        kind,payload,received=r4_ipc.receive(left,'1'*64,os.getuid(),os.getpid(),seconds=1)
        assert kind=='snapshot' and received!=fd and not os.get_inheritable(received)
        assert os.fstat(fd)==os.fstat(received) and os.read(received,9)==b'synthetic'
    finally:
        if received is not None:os.close(received)
        os.close(fd);left.close();right.close()


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
def test_K07_deadline_durably_holds_before_exact_whole_leaf_kill_and_no_repeated_kill():
    from app.db_audit_coordinator.r4_release import Session
    subject=Session.__new__(Session);subject.deadline=0;subject.done=False;subject.kill_sent=False
    ledger=[]
    subject.hold=lambda:ledger.append('durable_orphan_hold')
    class Leaf:
        def write(self,key,value):assert (key,value)==('cgroup.kill','1');ledger.append('exact_leaf_kill')
    subject.leaf=Leaf();subject.expire();subject.expire()
    assert ledger==['durable_orphan_hold','exact_leaf_kill'] and subject.kill_sent


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
