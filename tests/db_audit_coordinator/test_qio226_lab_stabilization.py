"""04A only: disposable queue/socket, canonical imports and PID/proc identity.

No real source, cgroup, service, snapshot transport or recovery invocation.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import uuid

import pytest

from app.db_audit_coordinator import contracts as c,live_policy as p,operator_cli as cli
from app.db_audit_coordinator.live_coordinator import LiveCoordinator,LiveAdmission
from app.db_audit_coordinator.protocol import receive,receive_response,send,peer_scope
from tests.db_audit_coordinator.test_b2_live_policy import profile,STORES,policy

ROOT=Path(__file__).resolve().parents[2]
LINUX=pytest.mark.skipif(sys.platform!='linux',reason='Linux/POSIX parent authority and native proc contract')
NATIVE=pytest.mark.skipif(sys.platform!='linux' or getattr(os,'geteuid',lambda:-1)()!=0,
    reason='Linux/POSIX root-owned private operator socket / PID-mount namespace fixture')


def items():return [dict(store_id=store,idempotency_key=str(uuid.uuid4())) for store in STORES]


def memory_subject():
    value=LiveCoordinator.__new__(LiveCoordinator)
    current=p.empty_state();commits=[]
    value._mutex=threading.RLock();value.profile=profile()
    value.admission=LiveAdmission(value.profile)
    value.orphan_hold=False
    value._inherited_pending=False;value._stopped=False;value._submitted=[];value._batch_scope=None;value._batch=()
    value._state=lambda:copy.deepcopy(current)
    def commit(changed):
        p.state(changed);current.clear();current.update(copy.deepcopy(changed));commits.append(copy.deepcopy(changed))
    value._commit=commit
    return value,current,commits


def lookup(subject,item,scope):return subject.handle(dict(op='status_by_key',**item),scope)


def test_batch_ack_exact_hash_and_read_only_scoped_reconciliation():
    subject,current,commits=memory_subject();request=items();scope=c.scope(1000)
    reply=subject.submit_batch(request,scope)
    assert len(commits)==3 and len(c.encode(reply,c.MAX_FRAME))<c.MAX_FRAME
    assert cli.response_shape(reply,dict(op='submit_batch',items=request))==reply
    original=copy.deepcopy(current)
    for item,accepted in zip(request,reply['jobs']):
        found=lookup(subject,item,scope)
        assert found==dict(status='found',job=accepted['job'])
        assert subject.status(found['job']['job_id'],scope)['job']==found['job']
        persisted=next(j for j in current['jobs'] if j['job_id']==found['job']['job_id'])
        expected=hashlib.sha256((item['store_id']+':'+c.idempotency(scope,item['idempotency_key'])).encode()).hexdigest()
        assert persisted['idempotency_hash']==expected
        assert lookup(subject,item,c.scope(1001))==dict(status='not_found',outcome='outcome_unresolved')
        assert lookup(subject,dict(item,idempotency_key=str(uuid.uuid4())),scope)['status']=='not_found'
        encoded=c.encode(found)
        for private in (b'scope_hash',b'idempotency_hash',b'auth_hash',b'nonce',b'/opt/',b'source_path'):
            assert private not in encoded
    assert len(commits)==3 and current==original
    again=subject.submit_batch(request,scope)
    assert [j['job']['job_id'] for j in again['jobs']]==[j['job']['job_id'] for j in reply['jobs']]
    assert all(j['status']=='duplicate' for j in again['jobs']) and len(commits)==3


def test_same_key_separate_store_scope_and_full_historical_lookup():
    subject,current,commits=memory_subject();request=items();scope=c.scope(1000)
    for item in request:item['idempotency_key']=request[0]['idempotency_key']
    reply=subject.submit_batch(request,scope)
    assert len({j['job']['job_id'] for j in reply['jobs']})==3
    for job in current['jobs']:job.update(state='canceled',reason_code='canceled')
    for seq in range(4,129):
        job=copy.deepcopy(current['jobs'][0]);job.update(seq=seq,job_id=str(uuid.uuid4()),
            idempotency_hash=hashlib.sha256(str(seq).encode()).hexdigest())
        current['jobs'].append(job)
    current['next_sequence']=129;p.state(current);before=c.encode(current)
    for item,accepted in zip(request,reply['jobs']):
        found=lookup(subject,item,scope)
        assert found['job']['job_id']==accepted['job']['job_id'] and found['job']['state']=='canceled'
        assert subject.submit(item['store_id'],item['idempotency_key'],'manual',scope)['status']=='duplicate'
    assert c.encode(current)==before and len(commits)==3
    with pytest.raises(c.CoordinatorError,match='queue_full'):
        subject.submit(STORES[0],str(uuid.uuid4()),'manual',scope)


def test_all_three_terminal_duplicates_still_fit_bounded_frame(record_property):
    subject,current,commits=memory_subject();request=items();scope=c.scope(1000)
    subject.submit_batch(request,scope)
    for job in current['jobs']:
        job.update(state='completed',claim_epoch=current['controller_epoch'],attempt_id=str(uuid.uuid4()),
            run_id=str(uuid.uuid4()),worker_pid=123,auth_hash='3'*64,auth_device=1,auth_inode=2,
            reason_code='audit_passed',resource_envelope=dict(fixture_only=False,memory_limit_bytes=c.MAX_INTEGER,timeout_seconds=5400))
        snapshot=dict(schema_version=policy(job['store_id']).schema_version,
            generation_kind='pinned_file_instance' if job['store_id']=='public_traffic' else 'native_lineage',
            lineage_sha256='4'*64,watermark_sha256='5'*64,page_size=65536,page_count=c.MAX_INTEGER)
        job['audit_result']=p.make_result(job,'passed','audit_passed',snapshot=snapshot,duration_ms=c.MAX_INTEGER)
        current['last_attempt_by_store'][job['store_id']]=copy.deepcopy(job['audit_result'])
        current['last_verified_success_by_store'][job['store_id']]=copy.deepcopy(job['audit_result'])
    p.state(current);reply=subject.submit_batch(request,scope)
    encoded=c.encode(reply,c.MAX_FRAME)
    assert len(encoded)<c.MAX_FRAME and all(item['status']=='duplicate' for item in reply['jobs'])
    assert len(commits)==3 and cli.response_shape(reply,dict(op='submit_batch',items=request))==reply
    record_property('three_completed_duplicate_reply_bytes',len(encoded))


@pytest.mark.parametrize('fault',['extra','missing','bad_uuid','same_store','count','store'])
def test_entire_batch_static_input_rejected_before_any_publication(fault):
    subject,current,commits=memory_subject();request=items()
    if fault=='extra':request[2]['extra']='forbidden'
    elif fault=='missing':request[2].pop('idempotency_key')
    elif fault=='bad_uuid':request[2]['idempotency_key']='not-uuid'
    elif fault=='same_store':request[2]['store_id']=request[0]['store_id']
    elif fault=='count':request.pop()
    else:request[2]['store_id']='invalid_store'
    with pytest.raises(c.CoordinatorError):subject.submit_batch(request,c.scope(1000))
    assert current['jobs']==[] and commits==[]


@pytest.mark.parametrize('accepted',[1,2])
def test_partial_batch_is_unknown_not_transaction_atomic_or_invalid(accepted):
    subject,current,commits=memory_subject();request=items();scope=c.scope(1000);original=subject._commit
    def crash(changed):
        if len(commits)==accepted:raise OSError('synthetic crash, no retry')
        original(changed)
    subject._commit=crash
    with pytest.raises(c.CoordinatorError,match='coordinator_unavailable'):subject.submit_batch(request,scope)
    assert len(commits)==accepted and len(current['jobs'])==accepted
    for index,item in enumerate(request):
        found=lookup(subject,item,scope)
        assert found['status']==('found' if index<accepted else 'not_found')
        if index>=accepted:assert found['outcome']=='outcome_unresolved'
    assert len(commits)==accepted  # No replay/repair/resubmit on reconciliation.


def test_post_commit_response_encoding_failure_is_unknown(monkeypatch):
    subject,current,commits=memory_subject();encode=c.encode
    def fail(value,*args):
        if type(value) is dict and value.get('status')=='batch':raise c.CoordinatorError('invalid_request')
        return encode(value,*args)
    monkeypatch.setattr(c,'encode',fail)
    with pytest.raises(c.CoordinatorError,match='coordinator_unavailable'):subject.submit_batch(items(),c.scope(1000))
    assert len(commits)==3 and len(current['jobs'])==3


@pytest.mark.parametrize('mutation',['extra','missing','bad_key','unknown_store'])
def test_status_by_key_closed_input_and_no_mutation(mutation):
    subject,current,commits=memory_subject();value=dict(op='status_by_key',**items()[0])
    if mutation=='extra':value['scope_hash']='forged'
    elif mutation=='missing':value.pop('idempotency_key')
    elif mutation=='bad_key':value['idempotency_key']=True
    else:value['store_id']='forged'
    with pytest.raises(c.CoordinatorError):subject.handle(value,c.scope(1000))
    assert current['jobs']==[] and commits==[]


@pytest.mark.parametrize('raw',[b'',b'\0\0\0\0',struct.pack('!I',8193),struct.pack('!I',2)+b'{',
    struct.pack('!I',2)+b'[]',struct.pack('!I',13)+b'{"x":1,"x":2}'])
def test_broken_response_never_becomes_definite_invalid_request(raw):
    left,right=socket.socketpair()
    try:
        left.sendall(raw);left.shutdown(socket.SHUT_WR)
        try:
            reply=receive_response(right)
            with pytest.raises(c.CoordinatorError):cli.response_shape(reply,dict(op='submit_batch',items=items()))
        except c.CoordinatorError as error:assert error.code=='coordinator_unavailable'
    finally:left.close();right.close()


def test_response_timeout_is_bounded_unknown_not_invalid():
    left,right=socket.socketpair();start=time.monotonic()
    try:
        with pytest.raises(c.CoordinatorError,match='coordinator_unavailable'):receive_response(right,seconds=.02)
        assert time.monotonic()-start<1
    finally:left.close();right.close()


def test_cli_unknown_output_does_not_resubmit_or_leak(monkeypatch,capsys):
    calls=[]
    def lost(value):calls.append(value);raise c.CoordinatorError('coordinator_unavailable')
    monkeypatch.setattr(cli,'request',lost)
    args=['submit-batch']
    for letter,item in zip('abc',items()):args.extend(['--'+letter+'-store',item['store_id'],'--'+letter+'-key',item['idempotency_key']])
    assert cli.main(args)==2
    assert json.loads(capsys.readouterr().out)==dict(error='coordinator_unavailable',outcome='ACK_OUTCOME_UNKNOWN')
    assert len(calls)==1


def test_cli_explicit_validation_reject_and_status_by_key_command(monkeypatch,capsys):
    calls=[]
    def reply(value):calls.append(value);return dict(error='invalid_request')
    monkeypatch.setattr(cli,'request',reply)
    item=items()[0]
    assert cli.main(['status-by-key','--store',item['store_id'],'--key',item['idempotency_key']])==2
    assert calls==[dict(op='status_by_key',**item)]
    assert json.loads(capsys.readouterr().out)==dict(error='invalid_request')


@NATIVE
@pytest.mark.parametrize('mode',['delayed','lost','partial1','partial2','malformed','short_frame','oversize','wrong_shape'])
def test_real_socket_durable_fsync_ack_and_key_reconciliation(monkeypatch,mode,record_property):
    from app.db_audit_coordinator.state_store import StateStore,atomic_publish
    from app.db_audit_coordinator.locks import LockSpec,PermanentLock
    class OperationalFixtureStore(StateStore):validate=staticmethod(p.state)
    with tempfile.TemporaryDirectory(prefix='qio04a-') as temporary:
        root=Path(temporary);root.chmod(0o700);owner_path=root/'owner.lock';owner_path.touch(mode=0o600)
        info=owner_path.stat();owner=PermanentLock(LockSpec(str(owner_path),0,info.st_dev,info.st_ino)).acquire()
        atomic_publish(root/'queue-state.v1.json',p.empty_state(),0)
        subject,_,_=memory_subject();syncs=[]
        def sync(fd):
            os.fsync(fd);syncs.append(time.monotonic())
            if mode=='delayed':time.sleep(.22)  # SIX durable syncs exceed historical one-second reply limit.
        subject.store=OperationalFixtureStore(root/'queue-state.v1.json',0,owner,sync=sync)
        subject._closed=subject._halted=False;subject.owner=owner
        subject._state=lambda:subject.store.read()
        commits=[]
        def commit(value):
            if mode.startswith('partial') and len(commits)==int(mode[-1]):raise OSError('fixture crash before next publication')
            subject.store.commit(value);commits.append(copy.deepcopy(value))
        subject._commit=commit
        endpoint=str(root/'operator.sock');listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        listener.bind(endpoint);os.chmod(endpoint,0o660);listener.listen(4);listener.settimeout(5)
        monkeypatch.setattr(cli,'SOCKET',endpoint)
        errors=[];calls=[];request=items();scope=c.scope(0)
        if mode=='malformed':request[2]['idempotency_key']='invalid'
        def serve():
            try:
                for turn in range(1 if mode=='malformed' else 4):
                    connection,_=listener.accept()
                    with connection:
                        caller=peer_scope(connection,{0});value=receive(connection);calls.append(value)
                        try:reply=subject.handle(value,caller)
                        except c.CoordinatorError as error:reply=dict(error=error.code)
                        if mode=='lost' and turn==0:continue
                        if turn==0 and mode in {'short_frame','oversize','wrong_shape'}:
                            if mode=='short_frame':connection.sendall(struct.pack('!I',2)+b'{')
                            elif mode=='oversize':connection.sendall(struct.pack('!I',c.MAX_FRAME+1))
                            else:send(connection,dict(status='batch',jobs=[]))
                            continue
                        send(connection,reply)
            except Exception as error:errors.append(type(error).__name__)
        thread=threading.Thread(target=serve);thread.start();start=time.monotonic()
        try:
            if mode=='malformed':
                # Bypass local prevalidation to prove server rejects a bad third input before first commit.
                with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as connection:
                    connection.connect(endpoint);send(connection,dict(op='submit_batch',items=request))
                    assert receive_response(connection)==dict(error='invalid_request')
                assert syncs==[] and commits==[]
            else:
                if mode in {'lost','short_frame','oversize','wrong_shape'}:
                    with pytest.raises(c.CoordinatorError,match='coordinator_unavailable'):
                        cli.request(dict(op='submit_batch',items=request))
                else:
                    reply=cli.request(dict(op='submit_batch',items=request))
                    if mode=='delayed':
                        assert reply['status']=='batch' and time.monotonic()-start>1
                    else:assert reply==dict(error='coordinator_unavailable')
                accepted=int(mode[-1]) if mode.startswith('partial') else 3
                before=(root/'queue-state.v1.json').read_bytes()
                assert len(commits)==accepted and len(syncs)==2*accepted
                for index,item in enumerate(request):
                    found=cli.request(dict(op='status_by_key',**item))
                    assert found['status']==('found' if index<accepted else 'not_found')
                    if index<accepted:assert found['job']['job_id']==commits[index]['jobs'][index]['job_id']
                assert (root/'queue-state.v1.json').read_bytes()==before and len(syncs)==2*accepted
        finally:
            thread.join(6);listener.close();owner.close()
        assert not thread.is_alive() and errors==[]
        record_property('elapsed_seconds',time.monotonic()-start)
        record_property('durable_records',len(commits));record_property('file_directory_fsyncs',len(syncs))
        assert len(calls)==(1 if mode=='malformed' else 4)


@pytest.mark.parametrize('store',STORES)
def test_clean_dependency_complete_worker_exact_domain_t3_and_negative_schema(store):
    script='''
import json,sqlite3,sys
from tests.db_audit_coordinator.test_b2_live_sqlite import initialize
from tests.db_audit_coordinator.test_b2_live_policy import policy
from app.db_audit_coordinator.live_sqlite import validate_snapshot
db=sqlite3.connect(':memory:',isolation_level=None);db.row_factory=sqlite3.Row
try:
 initialize(db,sys.argv[1]);result=validate_snapshot(db,policy(sys.argv[1]),lambda:None)
 db.execute('PRAGMA user_version=99')
 try:validate_snapshot(db,policy(sys.argv[1]),lambda:None)
 except Exception:negative=True
 else:negative=False
 db.execute('PRAGMA user_version='+str(policy(sys.argv[1]).schema_version))
 if sys.argv[1]=='public_traffic':
  db.execute('PRAGMA ignore_check_constraints=ON');db.execute('UPDATE traffic_daily SET traffic_bytes=-1')
 elif sys.argv[1]=='network_service_intelligence':
  db.execute("UPDATE service_materialization_generations SET ruleset_digest_sha256='invalid'")
 else:
  db.execute("INSERT INTO traffic_projection_versions(projection_version,projection_schema_version,source,source_schema_version,semantic_contract_sha256,status,created_at) VALUES('invalid-generation',1,'observations',1,?,'building',?)",('0'*64,'2026-10-19T00:00:00.000Z'))
 try:validate_snapshot(db,policy(sys.argv[1]),lambda:None)
 except Exception:domain=True
 else:domain=False
 print(json.dumps(dict(schema=result['schema_version'],negative_rejected=negative,domain_rejected=domain)))
finally:db.close()
'''
    process=subprocess.run([sys.executable,'-B','-E','-s','-c',script,store],cwd=ROOT,
        capture_output=True,text=True,timeout=20)
    assert process.returncode==0,process.stderr
    assert json.loads(process.stdout)==dict(schema=policy(store).schema_version,negative_rejected=True,domain_rejected=True)


@LINUX
def test_real_parent_proc_authority_and_wrong_start_ticks():
    # No store/source access happens in this authorization-only child.
    from app.db_audit_coordinator.live_receipts import start_ticks
    start=start_ticks(os.getpid())
    script='''
import json,os,sys
from app.db_audit_coordinator.child_bootstrap import verify_parent
from app.db_audit_coordinator.contracts import CoordinatorError
verify_parent(int(sys.argv[1]),int(sys.argv[2]))
try:verify_parent(int(sys.argv[1]),int(sys.argv[2])+1)
except CoordinatorError as error:denied=error.code=='unauthorized'
else:denied=False
print(json.dumps(dict(parent_matches=os.getppid()==int(sys.argv[1]),wrong_start_denied=denied)))
'''
    process=subprocess.run([sys.executable,'-B','-E','-s','-c',script,str(os.getpid()),str(start)],cwd=ROOT,
        capture_output=True,text=True,timeout=10)
    assert process.returncode==0,process.stderr
    assert json.loads(process.stdout)==dict(parent_matches=True,wrong_start_denied=True)


@NATIVE
@pytest.mark.parametrize('own_proc',[True,False])
def test_disposable_pid_namespace_with_correct_and_mismatched_proc(own_proc,record_property):
    script='''
import json,os,subprocess,sys
from app.db_audit_coordinator.live_receipts import start_ticks
parent=os.getpid();start=start_ticks(parent)
child="""
import json,os,sys
from app.db_audit_coordinator.child_bootstrap import verify_parent
from app.db_audit_coordinator.contracts import CoordinatorError
try:verify_parent(int(sys.argv[1]),int(sys.argv[2]));result='accepted'
except CoordinatorError as error:result=error.code
print(json.dumps(dict(result=result,pid=os.getpid(),ppid=os.getppid(),proc_self=os.readlink('/proc/self'),
 nspid=[line.strip() for line in open('/proc/self/status') if line.startswith('NSpid:')],
 namespace=os.readlink('/proc/self/ns/pid'))))
"""
process=subprocess.run([sys.executable,'-B','-E','-s','-c',child,str(parent),str(start)],capture_output=True,text=True,timeout=5)
assert process.returncode==0,process.stderr
print(process.stdout.strip())
'''
    command=['/usr/bin/unshare','--pid','--fork']
    if own_proc:command.extend(['--mount','--mount-proc'])
    command.extend([sys.executable,'-B','-E','-s','-c',script])
    process=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=15)
    assert process.returncode==0,process.stderr  # Native capability failure is not silently skipped.
    value=json.loads(process.stdout)
    assert value['ppid']==1 and value['result']==('accepted' if own_proc else 'unauthorized')
    assert (value['proc_self']==str(value['pid']))==own_proc
    record_property('synthetic_namespace_observation',json.dumps(value,sort_keys=True))


@LINUX
@pytest.mark.parametrize('fault',['missing_proc','replaced_parent','wrong_ppid','wrong_nspid'])
def test_parent_proc_missing_or_race_remains_closed(monkeypatch,fault):
    from app.db_audit_coordinator import child_bootstrap as worker
    parent=os.getppid();start=worker.start_ticks(parent)
    original=worker.proc_text
    if fault=='missing_proc':
        def missing(*args):raise FileNotFoundError('/private/DO_NOT_LOG')
        monkeypatch.setattr(worker,'proc_text',missing)
    elif fault=='replaced_parent':monkeypatch.setattr(worker,'start_ticks',lambda pid:start+1)
    else:
        def changed(pid,name):
            text=original(pid,name)
            return '\n'.join(('PPid:\t0' if line.startswith('PPid:') and fault=='wrong_ppid'
                else 'NSpid:\t999\t'+str(os.getpid()) if line.startswith('NSpid:') and fault=='wrong_nspid' else line)
                for line in text.splitlines())
        monkeypatch.setattr(worker,'proc_text',changed)
    with pytest.raises(c.CoordinatorError,match='unauthorized'):worker.verify_parent(parent,start)
