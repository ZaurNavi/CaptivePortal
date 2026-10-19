"""Actual process death/ACK/reap fixtures; never run a real database audit."""
import ctypes
import multiprocessing
import os
import select
import signal
import stat
import sys
import time
import uuid

import pytest

from app.db_audit_coordinator import contracts as c
from app.db_audit_coordinator.admission import FixtureCompletionFence
from app.db_audit_coordinator.locks import PermanentLock
from tests.db_audit_coordinator import lab,submit,complete,cleanup,marker

pytestmark=pytest.mark.skipif(sys.platform!='linux',reason='Actual Linux supervisor/child SIGKILL and waitpid contract')


def supervisor(fixture,connection,mode):
    subject=fixture.coordinator('hold_audit',timeout=8)
    try:
        result=submit(subject)
        if mode=='worker':
            subject.dispatch_one();connection.send((result,subject.process.pid))
            connection.recv()
        else:
            raise AssertionError()
    finally:cleanup(subject)


def enqueue_crash(fixture,connection,phase,key):
    subject=fixture.coordinator()
    if phase=='after_ack':
        reply=submit(subject,key=key);connection.send(('ACK',reply['job']['job_id']));connection.recv();return
    def sync(fd):
        is_directory=stat.S_ISDIR(os.fstat(fd).st_mode)
        if phase=='before_file_sync' and not is_directory:
            connection.send('before');connection.recv()
        os.fsync(fd)
        if phase=='after_directory_sync' and is_directory:
            connection.send('after');connection.recv()
    subject.store.sync=sync
    try:submit(subject,key=key);connection.send('ACK')
    finally:cleanup(subject)


def test_F05_killed_supervisor_cannot_release_stopped_childs_independent_flock(tmp_path):
    fixture=lab(tmp_path)
    libc=ctypes.CDLL(None,use_errno=True);previous=ctypes.c_int()
    assert libc.prctl(37,ctypes.byref(previous),0,0,0)==0  # PR_GET_CHILD_SUBREAPER
    assert libc.prctl(36,1,0,0,0)==0  # Private fixture parent can actually reap its orphan.
    context=multiprocessing.get_context('spawn');parent,child=context.Pipe()
    process=context.Process(target=supervisor,args=(fixture,child,'worker'));worker=None;new=None
    try:
        process.start();child.close()
        assert parent.poll(6);result,worker=parent.recv()
        marker(fixture,result['job']['job_id'],'source_read')
        os.kill(worker,signal.SIGSTOP)
        process.kill();process.join(4);assert process.exitcode is not None
        with pytest.raises(c.CoordinatorError,match='gate_busy'):PermanentLock(fixture.gate).acquire()
        new=fixture.coordinator()
        assert new.orphan_hold and not new.dispatch_one() and not new.reconcile()
        with pytest.raises(c.CoordinatorError,match='orphan_hold'):submit(new,'observations')
        os.kill(worker,signal.SIGCONT)
        reaped,status=os.waitpid(worker,0)
        assert reaped==worker and os.WIFEXITED(status)
        worker=None
        with PermanentLock(fixture.gate):pass
        # No PID/TTL inference: even exited unknown orphan remains held without a receipt.
        assert not new.reconcile()
    finally:
        if worker is not None:
            try:os.kill(worker,signal.SIGKILL)
            except ProcessLookupError:pass
            try:os.waitpid(worker,0)
            except ChildProcessError:pass
        if process.is_alive():process.kill()
        process.join(4);parent.close()
        if new is not None:cleanup(new)
        assert libc.prctl(36,previous.value,0,0,0)==0


@pytest.mark.parametrize('phase',['before_file_sync','after_directory_sync','after_ack'])
def test_F06_real_crash_before_ack_reconciles_durable_idempotency(tmp_path,phase):
    fixture=lab(tmp_path);key=str(uuid.uuid4());context=multiprocessing.get_context('spawn')
    parent,child=context.Pipe();process=context.Process(target=enqueue_crash,args=(fixture,child,phase,key))
    restarted=None
    try:
        process.start();child.close();assert parent.poll(6)
        observed=parent.recv()
        assert (isinstance(observed,tuple) and observed[0]=='ACK') if phase=='after_ack' else observed==('before' if phase=='before_file_sync' else 'after')
        process.kill();process.join(4);assert process.exitcode is not None
        restarted=fixture.coordinator();response=submit(restarted,key=key)
        assert response['status']==('queued' if phase=='before_file_sync' else 'duplicate')
        if phase=='after_ack':assert response['job']['job_id']==observed[1]
        assert len(restarted.store.read()['jobs'])==1
        assert not tuple(fixture.root.glob('*.source_read'))
    finally:
        if process.is_alive():process.kill()
        process.join(4);parent.close()
        if restarted is not None:cleanup(restarted)


def test_F07_crash_mid_fixture_no_pass_and_no_automatic_replay_on_restart(tmp_path):
    fixture=lab(tmp_path);subject=fixture.coordinator('crash');restarted=None
    try:
        reply=submit(subject);subject.dispatch_one();worker=subject.process
        subject._wake_read.settimeout(5);subject._wake_read.recv(1)
        assert worker.returncode==70 and worker.wait(timeout=0)==70
        job=subject.store.read()['jobs'][0]
        subject.close()
        fence=FixtureCompletionFence()
        restarted=fixture.coordinator(fence=fence)
        assert restarted.orphan_hold and not restarted.dispatch_one()
        assert not restarted.reconcile()
        fence.reaped[worker.pid]=(job['attempt_id'],worker.returncode)  # Actual reap, not PID absence.
        assert restarted.reconcile()
        state=restarted.store.read()
        assert state['jobs'][0]['audit_result']['result']=='incomplete'
        assert state['jobs'][0]['reason_code']=='restarted_after_claim'
        assert state['last_verified_success_by_store']=={}
        assert not restarted.dispatch_one()
        assert submit(restarted,key=reply['job'].get('idempotency_key',str(uuid.uuid4())))['status']=='queued'
    finally:
        cleanup(subject)
        if restarted is not None:cleanup(restarted)


@pytest.mark.parametrize('mode,code',[('crash_before_status_sync',71),('crash_after_status_sync',72)])
def test_F07_crash_during_durable_status_never_adopts_false_pass(tmp_path,mode,code):
    fixture=lab(tmp_path);subject=fixture.coordinator(mode)
    try:
        submit(subject);subject.dispatch_one();worker=subject.process;complete(subject)
        assert worker.returncode==code
        state=subject.store.read()
        assert state['last_verified_success_by_store']=={}
        assert state['jobs'][0]['audit_result']['result']=='incomplete'
        assert state['jobs'][0]['reason_code']=='worker_crashed'
    finally:cleanup(subject)


@pytest.mark.parametrize('tampered',[False,True])
def test_restarted_claim_needs_matching_durable_status_and_positive_successful_reap(tmp_path,tampered):
    from app.db_audit_coordinator.state_store import atomic_publish,read_json
    fixture=lab(tmp_path);subject=fixture.coordinator();restarted=None
    try:
        submit(subject);subject.dispatch_one();worker=subject.process
        subject._wake_read.settimeout(5);subject._wake_read.recv(1)
        assert worker.returncode==0 and worker.wait(timeout=0)==0
        job=subject.store.read()['jobs'][0];subject.close()
        if tampered:
            path=fixture.root/(job['job_id']+'.result.json');value=read_json(path,os.geteuid())
            value['source_generation']=str(uuid.uuid4());atomic_publish(path,value,os.geteuid())
        fence=FixtureCompletionFence();fence.reaped[worker.pid]=(job['attempt_id'],0)
        restarted=fixture.coordinator(fence=fence)
        assert restarted.reconcile()
        value=restarted.store.read()
        assert value['jobs'][0]['audit_result']['result']==('incomplete' if tampered else 'passed')
        assert bool(value['last_verified_success_by_store']) is (not tampered)
    finally:
        cleanup(subject)
        if restarted is not None:cleanup(restarted)
