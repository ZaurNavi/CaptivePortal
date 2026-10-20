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
