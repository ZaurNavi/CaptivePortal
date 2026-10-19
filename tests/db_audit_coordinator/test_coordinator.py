import copy
import os
import stat
import sys
import uuid

import pytest

from app.db_audit_coordinator import contracts as c
from app.db_audit_coordinator.admission import FixturePlan,FixtureAdmission,CompletionFence
from tests.db_audit_coordinator import lab,submit,complete,cleanup,marker

pytestmark=pytest.mark.skipif(sys.platform!='linux',reason='Real Linux queue/worker coordination fixture contract')


def test_F02_F16_manual_scheduled_share_durable_fifo_and_scoped_idempotency(tmp_path):
    fixture=lab(tmp_path);subject=fixture.coordinator();key=str(uuid.uuid4())
    try:
        first=submit(subject,'visits','scheduled',key)
        second=submit(subject,'observations','manual')
        assert first['job']['seq']<second['job']['seq']
        duplicate=submit(subject,'visits','scheduled',key)
        assert duplicate['status']=='duplicate' and duplicate['job']==first['job']
        with pytest.raises(c.CoordinatorError,match='store_busy'):submit(subject,'visits')
        assert subject.dispatch_one() and subject.active==first['job']['job_id']
        complete(subject)
        assert subject.dispatch_one() and subject.active==second['job']['job_id']
        complete(subject)
        assert not subject.dispatch_one()
        retry=submit(subject,'visits','manual',key)
        assert retry['status']=='duplicate' and retry['job']['state']=='completed'
        with pytest.raises(c.CoordinatorError):subject.status(first['job']['job_id'],c.scope(os.geteuid()+1))
    finally:cleanup(subject)


def test_F19_hundred_idle_status_and_duplicate_requests_have_zero_queue_writes(tmp_path):
    fixture=lab(tmp_path);calls=[]
    def sync(fd):calls.append(1);os.fsync(fd)
    subject=fixture.coordinator(sync=sync);key=str(uuid.uuid4())
    try:
        reply=submit(subject,key=key);before=len(calls)
        for _ in range(100):
            assert subject.status(reply['job']['job_id'],c.scope(os.geteuid()))['job']['state']=='queued'
            assert submit(subject,key=key)['status']=='duplicate'
        assert len(calls)==before
        assert subject.process is None and not tuple(fixture.root.glob('*.source_read'))
    finally:cleanup(subject)


def test_F16_bounded_history_never_evicts_acked_key_or_reexecutes_unknown_old_key(tmp_path):
    fixture=lab(tmp_path);subject=fixture.coordinator();keys=[]
    try:
        for _ in range(c.MAX_HISTORY):
            key=str(uuid.uuid4());reply=submit(subject,key=key);keys.append((key,reply['job']['job_id']))
            subject.cancel(reply['job']['job_id'])
        assert len(subject.store.read()['jobs'])==128
        with pytest.raises(c.CoordinatorError,match='queue_full'):submit(subject)
        for key,job in (keys[0],keys[-1]):
            assert submit(subject,key=key)['job']['job_id']==job
        assert not tuple(fixture.root.glob('*.source_read'))
    finally:cleanup(subject)


def test_F08_unknown_release_keeps_orphan_hold_even_after_child_exit(tmp_path):
    fixture=lab(tmp_path);subject=fixture.coordinator(fence=CompletionFence())
    try:
        first=submit(subject,'visits');second=submit(subject,'observations')
        assert subject.dispatch_one()
        subject._wake_read.settimeout(5);subject._wake_read.recv(1)
        assert subject.process.returncode==0
        assert not subject.finish() and subject.orphan_hold
        assert not subject.dispatch_one()
        assert not (fixture.root/(second['job']['job_id']+'.source_read')).exists()
        assert subject.store.read()['last_verified_success_by_store']=={}
    finally:cleanup(subject)


def test_F18_failed_later_attempt_preserves_specific_old_success(tmp_path):
    fixture=lab(tmp_path);subject=fixture.coordinator()
    try:
        first=submit(subject);subject.dispatch_one();complete(subject)
        success=copy.deepcopy(subject.store.read()['last_verified_success_by_store']['visits'])
        assert success['fixture_only'] is True and success['job_id']==first['job']['job_id']
        subject.admission=FixtureAdmission(FixturePlan(str(fixture.root),'fail'),os.geteuid())
        later=submit(subject);subject.dispatch_one();complete(subject)
        state=subject.store.read()
        assert state['last_verified_success_by_store']['visits']==success
        assert state['last_attempt_by_store']['visits']['job_id']==later['job']['job_id']
        assert state['last_attempt_by_store']['visits']['result']=='failed'
        status=subject.status(later['job']['job_id'],c.scope(os.geteuid()))
        assert status['last_verified_success']==success
        assert status['job']['resource_domain']==c.DOMAIN
        assert status['job']['run_id']==state['jobs'][-1]['run_id']
        assert not {'scope_hash','idempotency_hash','auth_hash','auth_device','auth_inode','worker_pid'}&status['job'].keys()
    finally:cleanup(subject)


def test_claim_fsync_failure_prevents_spawn_and_all_future_admission(tmp_path,monkeypatch):
    fixture=lab(tmp_path);subject=fixture.coordinator();submit(subject)
    spawned=[]
    monkeypatch.setattr('app.db_audit_coordinator.coordinator.subprocess.Popen',lambda *a,**k:spawned.append(1))
    def broken(_fd):raise OSError('synthetic')
    subject.store.sync=broken
    try:
        with pytest.raises(c.CoordinatorError):subject.dispatch_one()
        assert spawned==[]
        with pytest.raises(c.CoordinatorError):submit(subject,'observations')
        assert not tuple(fixture.root.glob('*.preflight'))
    finally:cleanup(subject)
