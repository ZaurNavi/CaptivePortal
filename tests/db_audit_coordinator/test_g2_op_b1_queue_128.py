import copy
import hashlib
import os
import sys
import threading
from uuid import UUID

import pytest

from app.db_audit_coordinator import contracts as c
from app.db_audit_coordinator.admission import Admission
from app.db_audit_coordinator.coordinator import Coordinator
from app.db_audit_coordinator.worker import result_for
from tests.db_audit_coordinator import cleanup, complete, lab


SCOPE = c.scope(1234)


def history(size=128, *, last='canceled', scope=SCOPE):
    state = c.empty_state(); keys = []
    for seq in range(1, size+1):
        key = str(UUID(int=seq)); keys.append(key)
        job = dict.fromkeys(c.JOB_KEYS)
        job.update(job_id=str(UUID(int=1000+seq)), seq=seq, store_id='fingerprint_evidence', scope_hash=scope,
            idempotency_hash=hashlib.sha256(('fingerprint_evidence:'+c.idempotency(scope, key)).encode()).hexdigest(),
            source_generation=str(UUID(int=2000)), origin='manual', state='canceled',
            created_at='2026-10-19T00:00:00.000Z', updated_at='2026-10-19T00:00:00.000Z',
            reason_code='canceled', method_version='fixture.sentinel.v1', validator_version='fixture.v1')
        if seq == 1 or seq == size and last in {'claimed', 'running'}:
            job.update(claim_epoch=state['controller_epoch'], attempt_id=str(UUID(int=3000+seq)),
                run_id=str(UUID(int=4000+seq)), auth_hash='a'*64, auth_device=1, auth_inode=2,
                worker_pid=12345, state='claimed', reason_code='claimed')
            if seq == 1:
                result = result_for(job, 'passed', 'fixture_passed', 'b'*64)
                job.update(state='completed', reason_code='fixture_passed', audit_result=result)
                state['last_attempt_by_store']['fingerprint_evidence'] = copy.deepcopy(result)
                state['last_verified_success_by_store']['fingerprint_evidence'] = copy.deepcopy(result)
        if seq == size:
            job['state'] = last
            job['reason_code'] = 'accepted' if last == 'queued' else last
        state['jobs'].append(job)
    state['next_sequence'] = size+1
    c.state(state)
    return state, keys


def model(state, *, orphan=False):
    subject = object.__new__(Coordinator)
    subject._mutex = threading.RLock(); subject.orphan_hold = orphan; subject.admission = Admission()
    subject._state = lambda: copy.deepcopy(state)
    def forbidden(_): pytest.fail('no commit allowed at saturation')
    subject._commit = forbidden
    return subject


@pytest.mark.parametrize('last', ['canceled', 'queued', 'claimed', 'running'])
@pytest.mark.parametrize('orphan', [False, True])
def test_129th_distinct_has_deterministic_queue_full_before_busy_or_orphan(last, orphan):
    state, keys = history(last=last); before = c.encode(state); subject = model(state, orphan=orphan)
    for store in ('fingerprint_evidence', 'visits'):
        for origin in ('manual', 'scheduled'):
            with pytest.raises(c.CoordinatorError, match='^queue_full$'):
                subject.submit(store, str(UUID(int=99999)), origin, SCOPE)
    for index in (0, 127):
        duplicate = subject.submit('fingerprint_evidence', keys[index], 'manual', SCOPE)
        assert duplicate == dict(status='duplicate', job=c.public_job(state['jobs'][index]))
        assert subject.status(duplicate['job']['job_id'], SCOPE)['last_verified_success'] == state['last_verified_success_by_store']['fingerprint_evidence']
    assert c.encode(state) == before


def test_128th_is_durable_accepted_and_the_next_never_commits_or_prunes():
    state, _ = history(127); subject = model(state); committed = []
    def commit(value):
        c.state(value); committed.append(c.encode(value)); state.clear(); state.update(copy.deepcopy(value))
    subject._commit = commit
    key = str(UUID(int=50000))
    reply = subject.submit('fingerprint_evidence', key, 'manual', SCOPE)
    assert reply['status'] == 'queued' and reply['job']['seq'] == 128 and len(committed) == 1
    saved = committed[0]
    for _ in range(100):
        with pytest.raises(c.CoordinatorError, match='queue_full'):
            subject.submit('visits', str(UUID(int=60000)), 'scheduled', SCOPE)
        assert subject.submit('fingerprint_evidence', key, 'manual', SCOPE)['status'] == 'duplicate'
    assert len(committed) == 1 and c.encode(state) == saved and state['next_sequence'] == 129


@pytest.mark.skipif(sys.platform != 'linux', reason='Linux durable queue/fsync/restart fixture contract')
@pytest.mark.parametrize('last', ['canceled', 'queued', 'claimed', 'running'])
def test_file_backed_preloaded_128_restart_and_status_have_zero_admission_writes(tmp_path, last):
    fixture = lab(tmp_path); syncs = []
    def sync(fd): syncs.append(1); os.fsync(fd)
    subject = fixture.coordinator(sync=sync)
    try:
        state, keys = history(last=last, scope=c.scope(os.geteuid()))
        subject.store.commit(state); cleanup(subject)
        subject = fixture.coordinator(sync=sync)
        before = (fixture.root/'queue-state.v1.json').read_bytes(); count = len(syncs)
        for _ in range(5):
            with pytest.raises(c.CoordinatorError, match='queue_full'):
                subject.submit('fingerprint_evidence', str(UUID(int=99999)), 'manual', c.scope(os.geteuid()))
            assert subject.submit('fingerprint_evidence', keys[0], 'manual', c.scope(os.geteuid()))['status'] == 'duplicate'
            status = subject.status(state['jobs'][0]['job_id'], c.scope(os.geteuid()))
            assert status['last_verified_success'] == state['last_verified_success_by_store']['fingerprint_evidence']
        assert len(syncs) == count and (fixture.root/'queue-state.v1.json').read_bytes() == before
        assert not tuple(fixture.root.glob('*.source_read')) and subject.process is None
        if last in {'claimed', 'running'}:
            assert subject.orphan_hold and not subject.reconcile() and not subject.dispatch_one()
        elif last == 'queued':
            # Saturation stops NEW jobs, not safe completion of already ACKed work.
            assert subject.dispatch_one(); complete(subject)
            assert len(subject.store.read()['jobs']) == 128
        else:
            assert not subject.dispatch_one()
    finally:
        cleanup(subject)
