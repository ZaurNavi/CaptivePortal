"""G3 store/evaluator contracts on disposable real SQLite, not a formal gate."""
from dataclasses import replace
from datetime import timedelta
import sqlite3
import pytest

from app.analytics.source_gateway import QueryDeadline
from app.network_metadata.validation import ni_timestamp,ni_format_utc
from app.network_metadata_projection.service_delivery_read_service import RecognitionIdentityV1,AuthoritativeBindingChangeV1
from app.network_service_recognition.evaluator import ServiceRecognitionEvaluatorV1
from app.network_service_recognition.materialization_repository import ServiceMaterializationRepository,MaterializationConflict,MaterializationCapacity
from app.network_service_recognition.materialization_schema import validate_schema,MaterializationUnavailable
from app.network_service_recognition.binding_replay import enqueue_binding_changes
from app.network_service_recognition.models import ServiceUnavailable
from .test_summary import synthetic,SITE,DEVICE,REF,MAC
from .support import bundle,AT


@pytest.fixture
def materialized(tmp_path):
    repo=ServiceMaterializationRepository(str(tmp_path/'ni04.sqlite3'),clock=lambda:ni_timestamp(AT,canonical=True)).initialize()
    gen=repo.ensure_generation(bundle(),0,AT)
    yield repo,gen
    repo.close()


def evaluation(host='www.youtube.com', *, family='tls',device=DEVICE,mac=MAC,event=None):
    snapshot,source=synthetic(host,family,**({} if event is None else {'event':event}))
    identity=RecognitionIdentityV1(SITE,mac,device,'authoritative',1)
    rows,_=ServiceRecognitionEvaluatorV1(bundle()).evaluate_batch(((snapshot.facts[0],identity),),{REF:source},AT,deadline=QueryDeadline.after(5))
    return rows[0]


def batch(repo,gen,row, *, after=0,end=1):
    with repo.transaction():
        if repo.checkpoint(gen)['last_edge_feed_seq']!=after:
            raise MaterializationConflict()
        repo.put_evaluated(gen,row,bundle(),AT)
        repo.connection.execute('UPDATE service_materialization_checkpoints SET last_edge_feed_seq=? WHERE generation_id=?',(end,gen))


def test_closed_store_and_pragmas(materialized):
    repo,_=materialized
    validate_schema(repo.connection,integrity=True)
    for pragma,value in [('synchronous',2),('foreign_keys',1),('busy_timeout',500),('wal_autocheckpoint',1000)]:
        assert repo.connection.execute('PRAGMA '+pragma).fetchone()[0]==value
    tables=[r[0] for r in repo.connection.execute("SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    assert len(tables)==8 and 'device_category_rollups' not in tables
    schema=' '.join(r[0] for r in repo.connection.execute("SELECT sql FROM sqlite_schema WHERE sql IS NOT NULL")).lower()
    for forbidden in ('sni','dns_name','src_ip','dst_ip','device_ip','peer_ip','packet_payload'):
        assert forbidden not in schema


def test_independent_writer_lock(materialized):
    repo,_=materialized
    second=ServiceMaterializationRepository(repo.db_path)
    with pytest.raises(OSError):second.initialize()
    assert repo.connection.execute('SELECT count(*) FROM service_materialization_schema').fetchone()[0]==1


@pytest.mark.parametrize('point',['materialization_evaluated','before_commit','after_commit'])
def test_atomic_fact_coverage_cursor_crash(materialized,point):
    repo,gen=materialized
    def crash(at):
        if at==point:raise RuntimeError('synthetic_crash')
    repo.crash_point=crash
    with pytest.raises(RuntimeError):batch(repo,gen,evaluation())
    committed=point=='after_commit'
    assert repo.checkpoint(gen)['last_edge_feed_seq']==int(committed)
    assert repo.connection.execute('SELECT count(*) FROM service_recognition_observations').fetchone()[0]==int(committed)
    assert repo.connection.execute('SELECT count(*) FROM device_materialization_state').fetchone()[0]==int(committed)
    repo.crash_point=lambda _:None
    batch(repo,gen,evaluation(),after=int(committed))
    assert repo.connection.execute('SELECT count(*) FROM service_recognition_observations').fetchone()[0]==1
    assert repo.connection.execute('SELECT count(*) FROM device_service_rollups').fetchone()[0]==1


@pytest.mark.parametrize('host,family',[('unmatched.example','tls'),('www.youtube.com','dns'),(None,'quic')])
def test_evaluated_unknown_has_coverage_not_positive(materialized,host,family):
    repo,gen=materialized
    batch(repo,gen,evaluation(host,family=family))
    assert repo.connection.execute('SELECT count(*) FROM device_materialization_state').fetchone()[0]==1
    assert repo.connection.execute('SELECT count(*) FROM service_recognition_observations').fetchone()[0]==0
    assert repo.checkpoint(gen)['last_edge_feed_seq']==1


def test_immutable_no_cross_identity_replay(materialized):
    repo,gen=materialized
    row=evaluation()
    batch(repo,gen,row)
    with pytest.raises(sqlite3.IntegrityError):
        repo.connection.execute("UPDATE service_recognition_observations SET device_id='changed'")
    changed=replace(row,identity=replace(row.identity,client_mac='AA:BB:CC:DD:EE:FF'))
    with pytest.raises(MaterializationConflict):batch(repo,gen,changed,after=1)
    assert repo.connection.execute('SELECT client_mac FROM service_recognition_observations').fetchone()[0]==MAC


def test_latest_rollup_only_advances(materialized):
    repo,gen=materialized
    newer=evaluation()
    batch(repo,gen,newer)
    older=evaluation(event=ni_format_utc(ni_timestamp(newer.observed_at,canonical=True)-timedelta(minutes=5)))
    # A distinct edge/ref is mandatory for a distinct immutable observation.
    obs=older.observation
    from app.network_service_recognition.models import RecognitionEvidenceRefV1
    older=replace(older,observation=replace(obs,service_observation_id='c'*64,evidence_refs=(replace(obs.evidence_refs[0],edge_id='d'*64),)))
    batch(repo,gen,older,after=1,end=2)
    assert repo.connection.execute('SELECT last_observed_at FROM device_service_rollups').fetchone()[0]==newer.observed_at


def test_binding_enqueue_with_closed_schema(materialized):
    repo,gen=materialized
    change=AuthoritativeBindingChangeV1(3,SITE,MAC,DEVICE,AT)
    assert enqueue_binding_changes(repo,gen,0,(change,),AT)
    assert repo.checkpoint(gen)['last_binding_change_seq']==3
    job=repo.connection.execute('SELECT * FROM service_binding_replay_jobs').fetchone()
    assert job['device_id']==DEVICE and job['client_mac']==MAC


def test_promotion_guard_and_atomic_active_switch(materialized):
    repo,gen=materialized
    with pytest.raises(MaterializationConflict):repo.promote(gen,AT,0)
    with repo.transaction():repo.connection.execute("UPDATE service_materialization_checkpoints SET backfill_state='complete' WHERE generation_id=?",(gen,))
    repo.promote(gen,AT,0)
    assert repo.connection.execute('SELECT active_generation_id FROM service_materialization_runtime').fetchone()[0]==gen
    assert repo.connection.execute("SELECT count(*) FROM service_materialization_generations WHERE state='active'").fetchone()[0]==1


def test_unknown_object_fails_without_repair(materialized):
    repo,_=materialized
    repo.connection.execute('CREATE TABLE unauthorized(x)')
    with pytest.raises(MaterializationUnavailable):validate_schema(repo.connection)
    assert repo.connection.execute("SELECT name FROM sqlite_schema WHERE name='unauthorized'").fetchone()


def test_capacity_preserves_checkpoint_and_current_facts(materialized,monkeypatch):
    repo,gen=materialized
    batch(repo,gen,evaluation())
    monkeypatch.setattr(repo,'footprint',lambda:repo.max_db_bytes+1)
    with pytest.raises(MaterializationCapacity):batch(repo,gen,evaluation(),after=1,end=2)
    assert repo.live_state=='capacity_halted'
    assert repo.checkpoint(gen)['last_edge_feed_seq']==1
    assert repo.connection.execute('SELECT count(*) FROM service_recognition_observations').fetchone()[0]==1


def test_validation_entire_batch_before_matching():
    snapshot,source=synthetic()
    identity=RecognitionIdentityV1(SITE,MAC,DEVICE,'authoritative',1)
    def forbidden(**kwargs):raise AssertionError('matcher_must_not_run')
    with pytest.raises(ServiceUnavailable):
        ServiceRecognitionEvaluatorV1(bundle(),matcher=forbidden).evaluate_batch(((snapshot.facts[0],identity),(snapshot.facts[0],identity)),{REF:replace(source,dst_ip='203.0.113.99')},AT,deadline=QueryDeadline.after(5))
