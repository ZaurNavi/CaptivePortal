import copy
from dataclasses import asdict
import hashlib
import os
import subprocess
import sys
import uuid

import pytest

from app.db_audit_coordinator import contracts as c
from app.db_audit_coordinator.admission import Admission,FixtureCompletionFence,FixtureFilesystem
from app.db_audit_coordinator.coordinator import Coordinator
from app.db_audit_coordinator.locks import PermanentLock
from app.db_audit_coordinator.worker import authorization,main
from tests.db_audit_coordinator import lab,submit,complete,cleanup,marker

pytestmark=pytest.mark.skipif(sys.platform!='linux',reason='Real Linux private authorization FD and independent worker flock')


def test_F03_new_worker_direct_invocation_without_authority_is_closed(tmp_path):
    fixture=lab(tmp_path)
    result=subprocess.run([sys.executable,'-m','app.db_audit_coordinator.worker'],timeout=4)
    assert result.returncode==2 and not tuple(fixture.root.glob('*.source_read'))
    assert main(['999999'])==2


@pytest.mark.parametrize('kind',['bytes-only','reused','forged-store'])
def test_one_time_descriptor_cannot_be_forged_or_reused(tmp_path,kind):
    fixture=lab(tmp_path);subject=fixture.coordinator('hold_preflight')
    try:
        reply=submit(subject);subject.dispatch_one();marker(fixture,reply['job']['job_id'],'preflight')
        left,right=os.pipe()
        payload={'job_id':reply['job']['job_id'],'store_id':'not_registered' if kind=='forged-store' else 'visits',
            'claim_epoch':subject.store.read()['controller_epoch'],'attempt_id':subject.store.read()['jobs'][0]['attempt_id'],
            'nonce':'0'*64,'root':str(fixture.root),'uid':os.geteuid(),'gate':{},'plan':None,'cancel_fd':0}
        os.write(right,c.encode(payload));os.close(right)
        with pytest.raises(c.CoordinatorError,match='unauthorized'):authorization(left)
        if kind=='reused':
            # The consumed descriptor is closed, so it cannot authorize again.
            with pytest.raises(c.CoordinatorError,match='unauthorized'):authorization(left)
        assert not tuple(fixture.root.glob('*.source_read'))
    finally:cleanup(subject)


@pytest.mark.parametrize('kind',['valid-once','copied-nonce-new-pipe','different-registered-store'])
def test_private_descriptor_identity_and_consumption_not_just_nonce_bytes(tmp_path,kind):
    fixture=lab(tmp_path);subject=fixture.coordinator();read_fd,write_fd=os.pipe();nonce=os.urandom(32).hex()
    descriptor=None
    try:
        reply=submit(subject);state=subject.store.read();job=state['jobs'][0];info=os.fstat(read_fd)
        job.update(state='claimed',claim_epoch=state['controller_epoch'],attempt_id=str(uuid.uuid4()),run_id=str(uuid.uuid4()),
            auth_hash=hashlib.sha256(nonce.encode()).hexdigest(),auth_device=info.st_dev,auth_inode=info.st_ino,worker_pid=os.getpid())
        subject.store.commit(state)
        payload=dict(job_id=reply['job']['job_id'],store_id='settings' if kind=='different-registered-store' else 'visits',
            claim_epoch=job['claim_epoch'],attempt_id=job['attempt_id'],nonce=nonce,root=str(fixture.root),
            uid=os.geteuid(),gate=asdict(fixture.gate),plan=None,cancel_fd=0)
        if kind=='copied-nonce-new-pipe':
            other,other_write=os.pipe();descriptor=other
            os.write(other_write,c.encode(payload));os.close(other_write)
        else:
            descriptor=read_fd;read_fd=None
            os.write(write_fd,c.encode(payload))
        os.close(write_fd);write_fd=None
        if kind=='valid-once':
            authority,claimed=authorization(descriptor)
            assert claimed['job_id']==job['job_id'] and authority['nonce']==nonce
            with pytest.raises(c.CoordinatorError,match='unauthorized'):authorization(descriptor)
        else:
            with pytest.raises(c.CoordinatorError,match='unauthorized'):authorization(descriptor)
        descriptor=None
        assert not tuple(fixture.root.glob('*.preflight')) and not tuple(fixture.root.glob('*.source_read'))
    finally:
        for fd in (read_fd,write_fd,descriptor):
            if fd is not None:
                try:os.close(fd)
                except OSError:pass
        cleanup(subject)


def test_F01_F04_global_lock_before_preflight_and_source_read_across_two_workers(tmp_path):
    first_dir=tmp_path/'one';second_dir=tmp_path/'two';first_dir.mkdir();second_dir.mkdir()
    first,second=lab(first_dir),lab(second_dir)
    one=first.coordinator('hold_preflight');two=second.coordinator()
    two.gate_spec=first.gate
    try:
        a=submit(one,'visits');b=submit(two,'observations')
        one.dispatch_one();marker(first,a['job']['job_id'],'preflight')
        assert one.process.pid!=os.getpid()
        two.dispatch_one();other=two.process;complete(two)
        assert other.pid!=one.process.pid
        assert not tuple(second.root.glob('*.preflight')) and not tuple(second.root.glob('*.source_read'))
        assert two.store.read()['jobs'][0]['reason_code']=='gate_busy'
        with pytest.raises(c.CoordinatorError,match='gate_busy'):PermanentLock(first.gate).acquire()
        os.write(one.cancel_fd,b'g');complete(one)
    finally:cleanup(one);cleanup(two)


@pytest.mark.parametrize('mode',['hold_preflight','hold_audit','timeout'])
def test_F09_cancel_timeout_never_admits_second_worker_before_release(tmp_path,mode):
    fixture=lab(tmp_path);subject=fixture.coordinator(mode,timeout=1)
    try:
        first=submit(subject);second=submit(subject,'observations')
        subject.dispatch_one();marker(fixture,first['job']['job_id'],'preflight')
        if mode!='timeout':subject.cancel(first['job']['job_id'])
        assert not subject.dispatch_one()
        assert not (fixture.root/(second['job']['job_id']+'.source_read')).exists()
        complete(subject)
        job=subject.store.read()['jobs'][0]
        assert job['audit_result']['result']=='incomplete'
        assert job['reason_code']==('timeout' if mode=='timeout' else 'canceled')
    finally:cleanup(subject)


def test_F12_default_production_admission_reads_no_fixture_source(tmp_path):
    fixture=lab(tmp_path);subject=Coordinator(fixture.root,fixture.owner,fixture.gate,fence=FixtureCompletionFence(),filesystem=FixtureFilesystem())
    try:
        submit(subject);subject.dispatch_one();complete(subject)
        assert subject.store.read()['jobs'][0]['reason_code']=='resource_deferred'
        assert not tuple(fixture.root.glob('*.preflight')) and not tuple(fixture.root.glob('*.source_read'))
    finally:cleanup(subject)


def test_F17_live_gate_replacement_before_source_read_fails_closed(tmp_path):
    fixture=lab(tmp_path);subject=fixture.coordinator('hold_preflight')
    try:
        reply=submit(subject);subject.dispatch_one();marker(fixture,reply['job']['job_id'],'preflight')
        target=fixture.root/'replacement.lock';target.write_bytes(b'replacement');target.chmod(0o600)
        os.replace(target,fixture.root/'heavy.lock')
        os.write(subject.cancel_fd,b'g');complete(subject)
        assert not tuple(fixture.root.glob('*.source_read'))
        assert subject.store.read()['jobs'][0]['reason_code']=='unsafe_path'
    finally:cleanup(subject)
