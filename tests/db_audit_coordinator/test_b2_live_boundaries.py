"""Negative operational-envelope, authority and positive-release canaries."""
import copy
import hashlib
import os
import sys
import uuid

import pytest

from app.db_audit_coordinator import contracts as c
from app.db_audit_coordinator import live_policy as p
from tests.db_audit_coordinator.test_b2_live_policy import policy,profile


def completed():
    value=p.empty_state();item=policy();method,validator,generation=item.metadata()
    job=dict(job_id=str(uuid.uuid4()),seq=1,store_id=item.store_id,scope_hash='1'*64,idempotency_hash='2'*64,
        origin='manual',state='completed',claim_epoch=value['controller_epoch'],attempt_id=str(uuid.uuid4()),
        run_id=str(uuid.uuid4()),created_at=c.utc(),updated_at=c.utc(),reason_code='audit_passed',
        method_version=method,validator_version=validator,source_generation=generation,
        resource_envelope=dict(fixture_only=False,memory_limit_bytes=item.memory_max_bytes,timeout_seconds=5400),
        auth_hash='3'*64,auth_device=1,auth_inode=2,worker_pid=123,audit_result=None)
    metadata=dict(schema_version=2,generation_kind='pinned_file_instance',lineage_sha256='4'*64,
        watermark_sha256='5'*64,page_size=4096,page_count=3)
    job['audit_result']=p.make_result(job,'passed','audit_passed',snapshot=metadata)
    value['jobs']=[job];value['next_sequence']=2
    value['last_attempt_by_store'][item.store_id]=copy.deepcopy(job['audit_result'])
    value['last_verified_success_by_store'][item.store_id]=copy.deepcopy(job['audit_result'])
    p.state(value);return value


@pytest.mark.parametrize('key,value',[('fixture_only',True),('method_version','fixture.sentinel.v1'),
    ('validator_version','fixture.v1'),('result','success'),('reason_code','fixture_passed'),
    ('snapshot_id',None),('duration_ms',True),('duration_ms',-1),('completed_at','yesterday')])
def test_operational_result_cannot_adopt_fixture_or_incomplete_claim_as_pass(key,value):
    record=completed()['jobs'][0]['audit_result'];record[key]=value
    with pytest.raises(Exception):p.result(record)


@pytest.mark.parametrize('key,value',[('schema_version',1),('generation_kind','native_lineage'),
    ('page_size',513),('page_count',0),('lineage_sha256','invalid')])
def test_metadata_is_store_specific_closed_and_bound_to_snapshot_digest(key,value):
    record=completed()['jobs'][0]['audit_result'];record['snapshot_metadata'][key]=value
    record['snapshot_id']=hashlib.sha256(c.encode(record['snapshot_metadata'])).hexdigest()
    with pytest.raises(Exception):p.result(record)


@pytest.mark.parametrize('changes',[{'state':'queued'},{'state':'running','worker_pid':None},
    {'state':'claimed','resource_envelope':None},{'origin':'scheduled'},
    {'source_generation':'bad'},{'reason_code':'fixture_passed'}])
def test_operational_queue_rejects_invalid_state_authority(changes):
    value=completed();value['jobs'][0].update(changes)
    with pytest.raises(Exception):p.state(value)


@pytest.mark.parametrize('changes',[{'enabled':1},{'worker_uid':0},{'operator_uids':(1001,)},
    {'worker_groups':(True,)},{'delegated':'/'},{'blobs':(('app/../bad.py','1'*64),)}])
def test_profile_cannot_expand_root_authority_or_import_scope(changes):
    with pytest.raises(Exception):profile(**changes)


@pytest.mark.skipif(sys.platform!='linux',reason='Linux/POSIX private pipe and sealed-descriptor contract')
@pytest.mark.parametrize('raw',[b'',b'{}',b'x'*4097])
def test_no_private_release_or_invalid_authority_cannot_touch_sqlite(monkeypatch,raw):
    from app.db_audit_coordinator import child_bootstrap as worker
    touched=[];monkeypatch.setattr(worker.live_sqlite,'audit',lambda *a,**kw:touched.append(1))
    read,write=os.pipe()
    try:
        if raw:os.write(write,raw)
        os.close(write);write=None
        assert worker.main([str(read)])==3
        assert touched==[]
    finally:
        for fd in (read,write):
            if fd is not None:
                try:os.close(fd)
                except OSError:pass


@pytest.mark.skipif(sys.platform!='linux',reason='Linux/POSIX exact child wait and pidfd release contract')
def test_missing_positive_reap_blocks_even_when_leaf_appears_empty():
    from app.db_audit_coordinator.live_cgroup import Leaf
    class Alive:
        returncode=None
        def wait(self,**kw):raise AssertionError('must not infer exit')
    class Empty:
        def empty(self):raise AssertionError('no release without positive wait')
    with pytest.raises(c.CoordinatorError):Leaf.released(Empty(),Alive(),-1,1)


@pytest.mark.skipif(sys.platform!='linux',reason='Linux/POSIX native control owner/mode and nofollow contract')
def test_native_control_reader_rejects_writable_wrong_owner_and_symlink(tmp_path):
    from app.db_audit_coordinator.live_receipts import read_at
    target=tmp_path/'memory.max';target.write_text('1024\n');target.chmod(0o644)
    fd=os.open(tmp_path,os.O_RDONLY|os.O_DIRECTORY)
    try:
        assert read_at(fd,'memory.max',trusted_uid=os.geteuid())=='1024\n'
        target.chmod(0o664)
        with pytest.raises(c.CoordinatorError):read_at(fd,'memory.max',trusted_uid=os.geteuid())
        target.chmod(0o644)
        with pytest.raises(c.CoordinatorError):read_at(fd,'memory.max',trusted_uid=os.geteuid()+1)
        (tmp_path/'alias').symlink_to(target)
        with pytest.raises(c.CoordinatorError):read_at(fd,'alias',trusted_uid=os.geteuid())
        assert read_at(fd,'missing',optional=True,trusted_uid=os.geteuid()) is None
    finally:os.close(fd)


@pytest.mark.skipif(sys.platform!='linux',reason='Linux/POSIX active deadline and whole-cgroup cancellation contract')
def test_active_timeout_is_finite_and_idle_has_no_polling(monkeypatch):
    from app.db_audit_coordinator import live_coordinator as runtime
    value=runtime.LiveCoordinator.__new__(runtime.LiveCoordinator)
    value.process=None;assert value.timeout() is None
    value.process=type('Running',(),{'returncode':None})()
    value._abort_at=None;value._deadline=20;value._killed=False;value.cancel_fd=None
    calls=[];value._leaf=type('Leaf',(),{'write':lambda self,*args:calls.append(args)})()
    now=[10];monkeypatch.setattr(runtime.time,'monotonic',lambda:now[0])
    assert value.timeout()==10
    now[0]=20;value.expire();assert value._abort_at==22 and value.timeout()==2
    now[0]=22;value.expire();assert calls==[('cgroup.kill','1')]
    assert value._killed and value.timeout() is None
    value.expire();assert len(calls)==1  # No repeated timer/poll/kill storm.


def test_daemon_has_no_default_install_or_fallback_entry():
    from app.db_audit_coordinator.daemon_cli import main
    assert main([])==2 and main(['install'])==2 and main(['run','--enable'])==2
