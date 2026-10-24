"""Verified ACK snapshot reused within routine retention, with no new source read."""
import os
import uuid
from unittest.mock import Mock
import pytest
from app.network_service_recognition.materialization_repository import ServiceMaterializationRepository
from app.network_metadata.validation import ni_timestamp
from .support import AT


@pytest.fixture
def delivery(tmp_path):
    repo=ServiceMaterializationRepository(str(tmp_path/'ni04.db'),visit_delivery_db_path=str(tmp_path/'visits.db'),
        clock=lambda:ni_timestamp(AT,canonical=True)).initialize()
    yield repo
    repo.close()


def append(repo,n):
    with repo.transaction():
        for _ in range(n):repo.append_visit_delivery('generation',AT,generation_id=str(uuid.uuid4()))


def ack(repo,seq):
    anchor=repo.connection.execute('SELECT * FROM ni04_visit_delivery_outbox WHERE outbox_seq=0').fetchone()
    hashed=anchor['floor_hash'] if seq==anchor['floor_seq'] else repo.connection.execute(
        'SELECT entry_hash FROM ni04_visit_delivery_outbox WHERE outbox_seq=?',(seq,)).fetchone()[0]
    return dict(consumer_id=str(uuid.uuid4()),source_stream_id=anchor['stream_id'],last_outbox_seq=seq,last_outbox_hash=hashed)


@pytest.mark.parametrize('head,seq',[(0,0),(3,0),(3,2),(3,3),(300,300)])
def test_verified_zero_positive_no_prune_and_bounded_256(delivery,head,seq):
    r=delivery;append(r,head);proof=ack(r,seq)
    def source():
        assert not r.connection.in_transaction
        return proof
    r._visit_acknowledgement=Mock(side_effect=source)
    assert r.visit_outbox_workload() is None
    r.retain();assert r.visit_outbox_workload()==head-seq
    assert r._visit_acknowledgement.call_count==1
    assert r.connection.execute('SELECT COUNT(*) FROM ni04_visit_delivery_outbox WHERE outbox_seq>0').fetchone()[0]==head-min(seq,256)
    # Pure report getter must issue no SQL; repeat at already-pruned floor.
    sql=[];r.connection.set_trace_callback(sql.append)
    assert r.visit_outbox_workload()==head-seq and sql==[]
    r.retain();assert r.visit_outbox_workload()==head-seq


@pytest.mark.parametrize('fault',['missing','stream','hash','consumer','below-floor','above-head','bool','retained-row-missing','version','before_commit','after_commit','visit_delivery_pruned','expired','pid','path','close'])
def test_bad_or_uncertain_pass_never_retains_previous_number(delivery,monkeypatch,fault):
    r=delivery;append(r,3);proof=ack(r,2);r._visit_acknowledgement=lambda:proof
    r.retain();assert r.visit_outbox_workload()==1
    if fault in {'before_commit','after_commit','visit_delivery_pruned'}:
        if fault=='visit_delivery_pruned':
            proof.update(last_outbox_seq=3,last_outbox_hash=r.connection.execute('SELECT entry_hash FROM ni04_visit_delivery_outbox WHERE outbox_seq=3').fetchone()[0])
        def crash(point):
            if point==fault:raise RuntimeError('injected')
        r.crash_point=crash
        with pytest.raises(RuntimeError):r.retain()
    elif fault=='expired':monkeypatch.setattr('app.network_service_recognition.materialization_repository.time.monotonic',lambda:r._visit_workload[2]+181)
    elif fault=='pid':monkeypatch.setattr('app.network_service_recognition.materialization_repository.os.getpid',lambda:-1)
    elif fault=='path':r.visit_delivery_db_path+='-replacement'
    elif fault=='close':r.close()
    else:
        if fault=='missing':r._visit_acknowledgement=lambda:None
        elif fault=='stream':proof['source_stream_id']=str(uuid.uuid4())
        elif fault=='consumer':proof['consumer_id']=str(uuid.uuid4())
        elif fault=='hash':proof['last_outbox_hash']='0'*64
        elif fault=='below-floor':proof['last_outbox_seq']=0
        elif fault=='above-head':proof['last_outbox_seq']=4
        elif fault=='bool':proof['last_outbox_seq']=True
        elif fault=='retained-row-missing':
            proof.update(last_outbox_seq=3,last_outbox_hash=r.connection.execute('SELECT entry_hash FROM ni04_visit_delivery_outbox WHERE outbox_seq=3').fetchone()[0])
            with r.transaction(retention=True):r.connection.execute('DELETE FROM ni04_visit_delivery_outbox WHERE outbox_seq=3')
        elif fault=='version':r.connection.execute('PRAGMA user_version=3')
        r.retain()
    assert r.visit_outbox_workload() is None


def test_restart_requires_new_successful_pass(delivery):
    r=delivery;proof=ack(r,0);r._visit_acknowledgement=lambda:proof;r.retain()
    assert r.visit_outbox_workload()==0
    r.close();r.initialize();assert r.visit_outbox_workload() is None
    r.retain();assert r.visit_outbox_workload()==0
