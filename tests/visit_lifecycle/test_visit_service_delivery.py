"""#296 Cut C: real two-DB durability, synthetic identities and admitted rules."""
from dataclasses import replace
from datetime import datetime,timezone,timedelta
from hashlib import sha256
import logging
import sqlite3
import time
import uuid

import pytest

from app.analytics.source_gateway import QueryDeadline
from app.network_metadata.validation import ni_timestamp
from app.network_metadata.models import NetworkMetadataValidationError
from app.network_metadata_projection.service_delivery_read_service import RecognitionIdentityV1
from app.network_service_recognition.evaluator import ServiceRecognitionEvaluatorV1
from app.network_service_recognition.materialization_repository import (
    ServiceMaterializationRepository,MaterializationConflict,read_visit_delivery_page)
from app.network_service_recognition.materialization_schema import DDL,ALGORITHM,validate_schema,signature,expected_signature,MaterializationUnavailable
from app.visit_lifecycle.reconciliation import VisitLinkReconciler
from app.visit_lifecycle.telemetry import VisitTelemetry
from .conftest import make_request
from tests.network_service_recognition.support import bundle
from tests.network_service_recognition.test_summary import synthetic,SITE,DEVICE,MAC

NOW='2026-10-12T15:25:00.000000Z'
START=datetime(2026,10,12,14,tzinfo=timezone.utc)
SNAPSHOT='40000000-0000-4000-8000-000000000001'


def evaluated(host='www.youtube.com',event='2026-10-12T14:30:00.000001Z',seed='one',b=None,at=NOW):
    projection,source=synthetic(host,event=event)
    ref=str(uuid.uuid5(uuid.NAMESPACE_URL,'296-lab-'+seed))
    fact=replace(projection.facts[0],edge_id=sha256(seed.encode()).hexdigest(),source_observation_ref=ref)
    source=replace(source,observation_id=ref)
    identity=RecognitionIdentityV1(SITE,MAC,DEVICE,'authoritative',1)
    values,_=ServiceRecognitionEvaluatorV1(b or bundle()).evaluate_batch(((fact,identity),),{ref:source},at,deadline=QueryDeadline.after(2))
    assert values[0].observation.resolution_state=='service_resolved'
    return values[0]


@pytest.fixture
def delivery(tmp_path,visit_config,visit_repository,visit_service):
    repo=ServiceMaterializationRepository(str(tmp_path/'ni04.sqlite3'),visit_delivery_db_path=str(visit_repository.db_path),
        clock=lambda:ni_timestamp(NOW,canonical=True)).initialize()
    gen=repo.ensure_generation(bundle(),0,NOW)
    with repo.transaction():repo.connection.execute("UPDATE service_materialization_checkpoints SET backfill_state='complete' WHERE generation_id=?",(gen,))
    repo.promote(gen,NOW,0)
    worker=VisitLinkReconciler(config=visit_config,repository=visit_repository,registry_read_service=None,
        telemetry=VisitTelemetry(logging.getLogger('test296.delivery')),service_history_path=repo.db_path)
    yield repo,gen,worker
    repo.close()


def open_visit(service,repo,at=START):
    outcome=service.submit_authorized(make_request(site_id=SITE,client_mac=MAC,authorized_at=at))
    assert outcome.visit_id
    repo.record_reconciliation_attempt(outcome.visit_id,device_id=DEVICE,initial_snapshot_id=str(uuid.uuid4()),
        attempted_at='2026-10-12T14:00:00.000Z',retry_at='2026-10-12T14:01:00.000Z')
    return repo.get_visit(SITE,outcome.visit_id)


def put(repo,gen,*rows,b=None,at=NOW):
    with repo.transaction():
        for row in rows:repo.put_evaluated(gen,row,b or bundle(),at)


def close_visit(repo,visit,at='2026-10-12T15:20:00.000Z'):
    # Synthetic authoritative closure revision; no services or real webhook IO.
    duration=int((datetime.fromisoformat(at.replace('Z','+00:00'))-datetime.fromisoformat(visit.started_at.replace('Z','+00:00'))).total_seconds())
    with repo._connect() as c:
        c.execute("UPDATE visits SET status='closed',closed_at=?,close_reason='synthetic_offline',close_time_source='controller_timestamp',duration_seconds=?,updated_at=? WHERE visit_id=?",
            (at,duration,at,visit.visit_id))


def summaries(repo,visit):
    with repo.read_connection() as c:
        return [dict(r) for r in c.execute('SELECT * FROM visit_service_summary WHERE visit_id=? ORDER BY service_id',(visit.visit_id,))]


def test_open_visit_three_facts_two_services_count_and_idle_zero_write(delivery,visit_repository,visit_service,monkeypatch,tmp_path):
    source,gen,w=delivery;visit=open_visit(visit_service,visit_repository)
    rows=[evaluated(seed='one'),evaluated(event='2026-10-12T15:19:00.000001Z',seed='two'),evaluated('web.whatsapp.com',seed='three')]
    put(source,gen,*rows)
    assert source.connection.execute('SELECT count(*) FROM ni04_visit_delivery_outbox WHERE kind=\'positive\'').fetchone()[0]==3
    assert w.run_services_once(now=NOW)==3
    values=summaries(visit_repository,visit)
    assert len(values)==2
    assert {r['service_id']:r['distinct_observation_count'] for r in values}=={'service.youtube':2,'service.whatsapp':1}
    assert all(r['status']=='processing' for r in values)
    before=visit_repository.service_consumer_cursor()
    put(source,gen,*rows)  # Same positive replay does not enqueue or count again.
    def saved_bytes():
        from pathlib import Path
        return {suffix:sha256(path.read_bytes()).hexdigest() for suffix in ('','-wal')
            if (path:=Path(str(visit_repository.db_path)+suffix)).exists() and path.stat().st_size>0}
    durable_before=saved_bytes()
    statements=[];original=visit_repository._connect
    def traced(**kw):
        c=original(**kw);c.set_trace_callback(statements.append);return c
    monkeypatch.setattr(visit_repository,'_connect',traced)
    assert w.run_services_once(now='2026-10-12T15:26:00.000000Z')==0
    assert summaries(visit_repository,visit)==values and visit_repository.service_consumer_cursor()==before
    assert not any(sql.startswith(('INSERT','UPDATE','DELETE','COMMIT')) for sql in statements)
    assert saved_bytes()==durable_before
    import json
    (tmp_path/'idle-visit-write-evidence.json').write_text(json.dumps(dict(main_and_nonempty_wal_unchanged=True,
        dml_statements=0,commit_statements=0,begin_immediate=sum(sql=='BEGIN IMMEDIATE' for sql in statements),
        native_sidecar_creation_not_counted_as_application_write=True),indent=2),encoding='utf-8')
    source.retain()
    assert source.connection.execute('SELECT count(*) FROM ni04_visit_delivery_outbox').fetchone()[0]==1
    assert w.run_services_once(now='2026-10-12T15:27:00.000000Z')==0


@pytest.mark.parametrize('point,committed', [('visit_membership_applied',False),('visit_checkpoint_applied',False),('visit_before_commit',False),('visit_after_commit',True)])
def test_visit_membership_summary_checkpoint_atomic_crashes(delivery,visit_repository,visit_service,point,committed):
    source,gen,w=delivery;visit=open_visit(visit_service,visit_repository);put(source,gen,evaluated())
    class Crash(BaseException):pass
    def crash(stage):
        if stage==point:raise Crash()
    with pytest.raises(Crash):w.run_services_once(now=NOW,crash_point=crash)
    assert bool(summaries(visit_repository,visit)) is committed
    assert (visit_repository.service_consumer_cursor() is not None) is committed
    if not committed:
        source.retain()
        assert source.connection.execute('SELECT count(*) FROM ni04_visit_delivery_outbox').fetchone()[0]==3
    w.run_services_once(now=NOW)
    assert summaries(visit_repository,visit)[0]['distinct_observation_count']==1


@pytest.mark.parametrize('point,committed',[('visit_delivery_appended',False),('before_commit',False),('after_commit',True)])
def test_source_positive_and_outbox_share_same_transaction(delivery,point,committed):
    source,gen,_=delivery
    def crash(stage):
        if stage==point:raise RuntimeError('synthetic-crash')
    source.crash_point=crash
    with pytest.raises(RuntimeError):put(source,gen,evaluated())
    assert source.connection.execute('SELECT count(*) FROM service_recognition_observations').fetchone()[0]==int(committed)
    assert source.connection.execute("SELECT count(*) FROM ni04_visit_delivery_outbox WHERE kind='positive'").fetchone()[0]==int(committed)


def test_unacknowledged_outbox_survives_source_pruning_and_missing_consumer(delivery,visit_repository,visit_service):
    source,gen,w=delivery;visit=open_visit(visit_service,visit_repository);put(source,gen,evaluated())
    source.clock=lambda:ni_timestamp('2026-11-02T00:00:00.000000Z',canonical=True)
    source.retain()
    assert source.connection.execute('SELECT count(*) FROM service_recognition_observations').fetchone()[0]==0
    assert source.connection.execute("SELECT count(*) FROM ni04_visit_delivery_outbox WHERE kind='positive'").fetchone()[0]==1
    w.run_services_once(now=NOW)
    assert summaries(visit_repository,visit)[0]['distinct_observation_count']==1


def test_missing_visit_stages_durably_then_links_without_replaying_source(delivery,visit_repository,visit_service):
    source,gen,w=delivery;put(source,gen,evaluated());w.run_services_once(now=NOW)
    cursor=visit_repository.service_consumer_cursor()
    with visit_repository.read_connection() as c:
        row=c.execute('SELECT * FROM visit_service_membership').fetchone()
        assert row['visit_id'] is None and row['status']=='pending' and row['reason']=='no_visit'
    visit=open_visit(visit_service,visit_repository)
    for _ in range(2):w.run_services_once(now=NOW)
    assert summaries(visit_repository,visit)[0]['distinct_observation_count']==1
    assert visit_repository.service_consumer_cursor()['last_outbox_seq']==cursor['last_outbox_seq']


def test_checkpoint_rollback_and_source_reset_fail_closed_no_pruning(delivery,visit_repository,visit_service):
    source,gen,w=delivery;open_visit(visit_service,visit_repository);put(source,gen,evaluated());w.run_services_once(now=NOW)
    cursor=visit_repository.service_consumer_cursor();source.retain()
    with pytest.raises(MaterializationConflict):read_visit_delivery_page(source.db_path,None,deadline=QueryDeadline.after(1))
    for bad in (dict(cursor,last_outbox_seq=0),dict(cursor,last_outbox_hash='f'*64),dict(cursor,source_stream_id=str(uuid.uuid4())),dict(cursor,consumer_id=str(uuid.uuid4()))):
        with pytest.raises(MaterializationConflict):read_visit_delivery_page(source.db_path,bad,deadline=QueryDeadline.after(1))
    with visit_repository._connect() as c:c.execute("UPDATE visit_service_consumer_state SET last_outbox_seq=0")
    put(source,gen,evaluated(seed='new'));source.retain()
    assert source.connection.execute("SELECT count(*) FROM ni04_visit_delivery_outbox WHERE kind='positive'").fetchone()[0]==1


def test_exact_ni04_v1_to_v2_upgrade_preserves_existing_rows(tmp_path):
    path=str(tmp_path/'legacy.sqlite3')
    with sqlite3.connect(path) as c:
        c.execute('PRAGMA journal_mode=WAL');c.execute('PRAGMA foreign_keys=ON')
        for statement in DDL:c.execute(statement)
        c.execute('PRAGMA user_version=1')
        c.execute('INSERT INTO service_materialization_schema VALUES(1,1,1,?,?)',(ALGORITHM,NOW))
        c.execute("INSERT INTO service_materialization_runtime(singleton_id,runtime_state,updated_at_utc) VALUES(1,'initializing',?)",(NOW,))
        validate_schema(c,integrity=True)
    repo=ServiceMaterializationRepository(path).initialize()
    try:
        assert repo.connection.execute('PRAGMA user_version').fetchone()[0]==2
        assert signature(repo.connection)==expected_signature(2)
        assert repo.connection.execute('SELECT created_at_utc FROM service_materialization_schema').fetchone()[0]==NOW
        assert repo.visit_delivery_db_path is None
        assert tuple(repo.connection.execute('SELECT head_seq,floor_seq FROM ni04_visit_delivery_outbox').fetchone())==(0,0)
    finally:repo.close()


def test_closed_A_next_B_exact_boundary_and_late_closure_correction(delivery,visit_repository,visit_service):
    source,gen,w=delivery;a=open_visit(visit_service,visit_repository)
    put(source,gen,evaluated(seed='a'),evaluated(event='2026-10-12T15:19:00.000000Z',seed='last-a'),
        evaluated('web.whatsapp.com',event='2026-10-12T15:20:00.000000Z',seed='boundary'))
    w.run_services_once(now=NOW)
    assert len(summaries(visit_repository,a))==2
    close_visit(visit_repository,a)
    w.run_services_once(now=NOW)
    from app.visit_lifecycle.read_service import project_visit_service_history
    closed=visit_repository.get_visit(SITE,a.visit_id)
    projected=project_visit_service_history(closed,summaries(visit_repository,closed),visit_repository.service_consumer_cursor(),evaluated_now=NOW)
    assert projected['services'] and projected['history_state']=='incomplete'
    b=open_visit(visit_service,visit_repository,datetime(2026,10,12,15,20,tzinfo=timezone.utc))
    for _ in range(3):w.run_services_once(now=NOW)
    assert [(r['service_id'],r['distinct_observation_count']) for r in summaries(visit_repository,a)]==[('service.youtube',2)]
    assert [(r['service_id'],r['distinct_observation_count']) for r in summaries(visit_repository,b)]==[('service.whatsapp',1)]
    assert summaries(visit_repository,b)[0]['first_observed_at']=='2026-10-12T15:20:00.000000Z'
    # A late shortened closure removes the provisional fact; it is not shifted
    # to B merely because B shares today's MAC.
    close_visit(visit_repository,a,'2026-10-12T15:00:00.000Z')
    for _ in range(3):w.run_services_once(now=NOW)
    assert summaries(visit_repository,a)[0]['distinct_observation_count']==1
    assert summaries(visit_repository,b)[0]['distinct_observation_count']==1


def test_future_fails_closed_and_wrong_device_never_credits_another_visit(delivery,visit_repository,visit_service):
    source,gen,w=delivery;visit=open_visit(visit_service,visit_repository)
    put(source,gen,evaluated(event='2026-10-12T15:19:00.000000Z'))
    with pytest.raises(MaterializationConflict):w.run_services_once(now='2026-10-12T15:00:00.000000Z')
    assert visit_repository.service_consumer_cursor() is None
    assert summaries(visit_repository,visit)==[]
    with visit_repository._connect() as c:
        c.execute('UPDATE visits SET device_id=? WHERE visit_id=?',(str(uuid.uuid4()),visit.visit_id))
    for _ in range(3):w.run_services_once(now=NOW)
    assert summaries(visit_repository,visit)==[]
    with visit_repository.read_connection() as c:
        row=c.execute('SELECT status,reason,visit_id FROM visit_service_membership').fetchone()
        assert tuple(row)==('pending','identity_pending',None)


def test_generation_replay_is_one_canonical_observation_not_double_count(delivery,visit_repository,visit_service):
    from tests.network_service_recognition.support import documents,encode
    from app.network_service_recognition.artifacts import load_bundle
    source,gen,w=delivery;visit=open_visit(visit_service,visit_repository)
    put(source,gen,evaluated());w.run_services_once(now=NOW)
    docs=documents();docs[0]['taxonomy_version']+=1;docs[2]['ruleset_version']+=1
    next_bundle=load_bundle(*encode(docs));next_gen=source.ensure_generation(next_bundle,0,NOW)
    put(source,next_gen,evaluated(b=next_bundle),b=next_bundle)
    with source.transaction():source.connection.execute("UPDATE service_materialization_checkpoints SET backfill_state='complete' WHERE generation_id=?",(next_gen,))
    source.promote(next_gen,NOW,0)
    w.run_services_once(now=NOW)
    rows=summaries(visit_repository,visit)
    assert len(rows)==1 and rows[0]['distinct_observation_count']==1 and rows[0]['taxonomy_version']==2
    with visit_repository.read_connection() as c:assert c.execute('SELECT count(*) FROM visit_service_membership').fetchone()[0]==1


def test_binding_marker_invalidates_provisional_without_silent_reassignment(delivery,visit_repository,visit_service):
    source,gen,w=delivery;visit=open_visit(visit_service,visit_repository);put(source,gen,evaluated());w.run_services_once(now=NOW)
    with source.transaction():source.append_visit_delivery('binding',NOW,site_id=SITE,device_id=str(uuid.uuid4()),client_mac=MAC,binding_seq=2)
    w.run_services_once(now=NOW)
    assert summaries(visit_repository,visit)==[]
    with visit_repository.read_connection() as c:
        row=c.execute('SELECT status,reason,binding_seq,visit_id FROM visit_service_membership').fetchone()
        assert tuple(row)==('invalidated','binding_changed',2,None)


def test_sealed_history_survives_source_prune_and_does_not_silently_rewrite(delivery,visit_repository,visit_service):
    source,gen,w=delivery;visit=open_visit(visit_service,visit_repository);put(source,gen,evaluated());w.run_services_once(now=NOW)
    close_visit(visit_repository,visit)
    for _ in range(3):w.run_services_once(now='2026-10-12T15:36:00.000000Z')
    before=summaries(visit_repository,visit)
    assert before[0]['finalized_at'] is not None and before[0]['status']=='confirmed'
    source.clock=lambda:ni_timestamp('2026-10-27T00:00:00.000000Z',canonical=True);source.retain()
    w.run_services_once(now='2026-10-27T00:00:00.000000Z')
    assert summaries(visit_repository,visit)==before
    with visit_repository._connect() as c:c.execute('DELETE FROM visits WHERE visit_id=?',(visit.visit_id,))
    with visit_repository.read_connection() as c:
        assert c.execute('SELECT count(*) FROM visit_service_membership').fetchone()[0]==0
        assert c.execute('SELECT count(*) FROM visit_service_summary').fetchone()[0]==0


def test_missing_source_records_one_unavailable_transition_not_repeated_writes(delivery,visit_repository,visit_service,monkeypatch):
    source,gen,w=delivery;open_visit(visit_service,visit_repository);put(source,gen,evaluated());w.run_services_once(now=NOW)
    w.service_history_path=source.db_path+'.absent'
    with pytest.raises(sqlite3.Error):w.run_services_once(now=NOW)
    assert visit_repository.service_consumer_cursor()['status']=='unavailable'
    trace=[];original=visit_repository._connect
    def traced(**kw):
        c=original(**kw);c.set_trace_callback(trace.append);return c
    monkeypatch.setattr(visit_repository,'_connect',traced)
    with pytest.raises(sqlite3.Error):w.run_services_once(now=NOW)
    assert not any(s.startswith(('UPDATE','INSERT','DELETE','COMMIT')) for s in trace)


def test_detached_expires_at_one_hour_and_physically_reclaims_capacity(delivery,visit_repository,visit_service):
    source,gen,w=delivery;put(source,gen,evaluated());w.run_services_once(now=NOW)
    w.run_services_once(now='2026-10-27T00:00:00.000000Z')
    with visit_repository.read_connection() as c:
        assert c.execute('SELECT count(*) FROM visit_service_membership').fetchone()[0]==0
    assert visit_repository.service_consumer_cursor()['detached_count']==0
    assert not hasattr(w,'service_history_ttl_days')


@pytest.mark.parametrize('mutation',['hash','stream','sequence-gap','unknown-schema'])
def test_corrupt_source_page_never_advances_visit_checkpoint(delivery,visit_repository,visit_service,mutation):
    source,gen,w=delivery;visit=open_visit(visit_service,visit_repository);put(source,gen,evaluated())
    if mutation=='hash':source.connection.execute("UPDATE ni04_visit_delivery_outbox SET entry_hash=? WHERE outbox_seq=2",('f'*64,))
    elif mutation=='stream':source.connection.execute('UPDATE ni04_visit_delivery_outbox SET stream_id=? WHERE outbox_seq=2',(str(uuid.uuid4()),))
    elif mutation=='sequence-gap':source.connection.execute('DELETE FROM ni04_visit_delivery_outbox WHERE outbox_seq=1')
    else:source.connection.execute('PRAGMA user_version=99')
    with pytest.raises((MaterializationConflict,MaterializationUnavailable)):w.run_services_once(now=NOW)
    assert visit_repository.service_consumer_cursor() is None and summaries(visit_repository,visit)==[]


@pytest.mark.parametrize('fields',[{'binding_seq':True},{'binding_seq':0},{'binding_seq':1.5},{'payload':'private-sni'}, {'device_id':'invalid'}])
def test_outbox_closed_provenance_rejects_types_and_payload(delivery,fields):
    source,gen,_=delivery
    before=source.connection.execute('SELECT head_seq,head_hash FROM ni04_visit_delivery_outbox WHERE outbox_seq=0').fetchone()
    value=dict(site_id=SITE,device_id=DEVICE,client_mac=MAC,binding_seq=2);value.update(fields)
    with pytest.raises((MaterializationConflict,NetworkMetadataValidationError)):
        with source.transaction():source.append_visit_delivery('binding',NOW,**value)
    after=source.connection.execute('SELECT head_seq,head_hash FROM ni04_visit_delivery_outbox WHERE outbox_seq=0').fetchone()
    assert tuple(after)==tuple(before)


def test_no_additional_commit_per_positive_and_source_lock_closed_before_visit_write(delivery,visit_repository,visit_service,monkeypatch):
    from contextlib import contextmanager
    import app.network_service_recognition.materialization_repository as module
    source,gen,w=delivery;open_visit(visit_service,visit_repository)
    trace=[];source.connection.set_trace_callback(trace.append)
    put(source,gen,evaluated(seed='one'),evaluated(seed='two'),evaluated(seed='three'))
    assert trace.count('BEGIN IMMEDIATE')==trace.count('COMMIT')==1
    assert sum(sql.startswith('INSERT INTO ni04_visit_delivery_outbox') for sql in trace)==3
    held=False;original=module._visit_readonly;connect=visit_repository._connect
    @contextmanager
    def guarded(*a,**kw):
        nonlocal held
        with original(*a,**kw) as c:
            held=True
            try:yield c
            finally:held=False
    def connection(**kw):
        if not kw.get('readonly',False):assert not held,'Source lock leaked into Visit writer'
        return connect(**kw)
    monkeypatch.setattr(module,'_visit_readonly',guarded);monkeypatch.setattr(visit_repository,'_connect',connection)
    assert w.run_services_once(now=NOW)==3


def test_concurrent_append_and_close_between_source_snapshot_and_visit_write(delivery,visit_repository,visit_service,monkeypatch):
    import app.network_service_recognition.materialization_repository as module
    source,gen,w=delivery;visit=open_visit(visit_service,visit_repository)
    put(source,gen,evaluated(event='2026-10-12T15:20:00.000000Z',seed='at-close'))
    original=module.read_visit_delivery_page
    def interleave(*a,**kw):
        page=original(*a,**kw)
        close_visit(visit_repository,visit)
        put(source,gen,evaluated(seed='late-in-A'))
        monkeypatch.setattr(module,'read_visit_delivery_page',original)
        return page
    monkeypatch.setattr(module,'read_visit_delivery_page',interleave)
    w.run_services_once(now=NOW)
    # The bounded drain may already fetch the second committed source page;
    # it must credit ONLY the in-A fact, never the exact-close boundary fact.
    assert summaries(visit_repository,visit)[0]['distinct_observation_count']==1
    assert summaries(visit_repository,visit)[0]['last_observed_at']=='2026-10-12T14:30:00.000001Z'
    w.run_services_once(now=NOW)
    assert summaries(visit_repository,visit)[0]['distinct_observation_count']==1
    assert summaries(visit_repository,visit)[0]['last_observed_at']=='2026-10-12T14:30:00.000001Z'


def test_incompatible_schema_and_corrupt_visit_ack_never_prune(delivery,visit_repository,visit_service):
    source,gen,w=delivery;open_visit(visit_service,visit_repository);put(source,gen,evaluated());w.run_services_once(now=NOW)
    with visit_repository._connect() as c:c.execute('PRAGMA user_version=99')
    source.retain();assert source.connection.execute('SELECT count(*) FROM ni04_visit_delivery_outbox').fetchone()[0]==3
    with visit_repository._connect() as c:
        c.execute('PRAGMA user_version=6');c.execute("UPDATE visit_service_consumer_state SET last_outbox_hash='invalid'")
    source.retain();assert source.connection.execute('SELECT count(*) FROM ni04_visit_delivery_outbox').fetchone()[0]==3


def test_explicit_consumer_path_required_and_default_off_never_enqueues(tmp_path):
    from app.network_service_recognition.materialization_schema import MaterializationUnavailable
    for value in ('relative.sqlite3',0,True,1.5):
        with pytest.raises(MaterializationUnavailable):ServiceMaterializationRepository(str(tmp_path/'ni04'),visit_delivery_db_path=value)
    repo=ServiceMaterializationRepository(str(tmp_path/'inert.sqlite3'),clock=lambda:ni_timestamp(NOW,canonical=True)).initialize()
    try:
        gen=repo.ensure_generation(bundle(),0,NOW);put(repo,gen,evaluated())
        assert repo.connection.execute('SELECT count(*) FROM ni04_visit_delivery_outbox').fetchone()[0]==1
        assert repo.connection.execute('SELECT count(*) FROM service_recognition_observations').fetchone()[0]==1
    finally:repo.close()


def test_100k_outbox_page_is_bounded_primary_key_seek_and_capacity_fails_closed(delivery,tmp_path):
    import json
    from app.network_service_recognition.materialization_repository import VISIT_DELIVERY_FIELDS,visit_delivery_hash,MaterializationCapacity
    source,gen,_=delivery;put(source,gen,evaluated())
    seed=source.connection.execute('SELECT * FROM ni04_visit_delivery_outbox WHERE outbox_seq=2').fetchone()
    template={k:seed[k] for k in VISIT_DELIVERY_FIELDS};tail=seed['entry_hash'];total=100002
    columns=(*VISIT_DELIVERY_FIELDS,'entry_hash')
    def values():
        nonlocal tail
        for seq in range(3,total+1):
            row=dict(template,outbox_seq=seq,previous_hash=tail,edge_id=sha256(str(seq).encode()).hexdigest(),
                source_ref=str(uuid.uuid5(uuid.NAMESPACE_URL,'296-scale-'+str(seq))),source_observation_id=sha256(('obs'+str(seq)).encode()).hexdigest())
            tail=visit_delivery_hash(row)
            yield (*[row[k] for k in VISIT_DELIVERY_FIELDS],tail)
    # Disposable seed simulates retained delivery AFTER raw source expiry;
    # it does not change production capacity or invoke extra writer commits.
    with source.transaction():
        source.connection.executemany('INSERT INTO ni04_visit_delivery_outbox('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')',values())
        source.connection.execute('UPDATE ni04_visit_delivery_outbox SET head_seq=?,head_hash=? WHERE outbox_seq=0',(total,tail))
    seq=total-30;hashed=source.connection.execute('SELECT entry_hash FROM ni04_visit_delivery_outbox WHERE outbox_seq=?',(seq,)).fetchone()[0]
    cursor=dict(consumer_id=str(uuid.uuid4()),source_stream_id=seed['stream_id'],last_outbox_seq=seq,last_outbox_hash=hashed)
    plan=source.connection.execute('EXPLAIN QUERY PLAN SELECT * FROM ni04_visit_delivery_outbox WHERE outbox_seq>? ORDER BY outbox_seq LIMIT 25',(seq,)).fetchall()
    assert any('SEARCH' in row[3] and 'INTEGER PRIMARY KEY' in row[3] for row in plan)
    assert not any('SCAN ' in row[3] or 'TEMP B-TREE' in row[3] for row in plan)
    start=time.perf_counter();page=read_visit_delivery_page(source.db_path,cursor,deadline=QueryDeadline.after(2));elapsed=time.perf_counter()-start
    assert len(page['entries'])==25 and page['entries'][0]['outbox_seq']==seq+1 and page['entries'][-1]['outbox_seq']==seq+25
    before=source.connection.execute('SELECT count(*) FROM service_recognition_observations').fetchone()[0]
    with pytest.raises(MaterializationCapacity):put(source,gen,evaluated(seed='over-cap'))
    assert source.connection.execute('SELECT count(*) FROM service_recognition_observations').fetchone()[0]==before
    (tmp_path/'outbox-scale-evidence.json').write_text(json.dumps(dict(rows=total,page_rows=len(page['entries']),
        read_seconds=elapsed,sqlite=sqlite3.sqlite_version,explain=[tuple(r) for r in plan],footprint_bytes=source.footprint(),
        physical_hdd_io='NOT_MEASURED',source_capacity='FAIL_CLOSED_NO_DROP'),indent=2),encoding='utf-8')


def test_stale_or_stopping_producer_is_unavailable_without_erasing_saved_history(delivery,visit_repository,visit_service):
    from app.visit_lifecycle.read_service import project_visit_service_history
    source,gen,w=delivery;visit=open_visit(visit_service,visit_repository);put(source,gen,evaluated());w.run_services_once(now=NOW)
    source.connection.execute("UPDATE service_materialization_runtime SET runtime_state='stopping'")
    w.run_services_once(now=NOW)
    state=visit_repository.service_consumer_cursor();assert state['status']=='unavailable'
    value=project_visit_service_history(visit,summaries(visit_repository,visit),state,evaluated_now=NOW)
    assert value['history_state']=='unavailable' and len(value['services'])==1
    source.connection.execute("UPDATE service_materialization_runtime SET runtime_state='usable'")
    w.run_services_once(now='2026-10-12T15:31:00.000000Z')
    assert visit_repository.service_consumer_cursor()['status']=='unavailable'
    source.connection.execute('UPDATE service_materialization_runtime SET updated_at_utc=?',('2026-10-12T15:31:00.000000Z',))
    w.run_services_once(now='2026-10-12T15:31:00.000000Z')
    assert visit_repository.service_consumer_cursor()['status']=='incomplete'


def test_tomorrow_visit_same_device_has_only_its_own_new_fact(delivery,visit_repository,visit_service):
    source,gen,w=delivery;a=open_visit(visit_service,visit_repository);put(source,gen,evaluated());w.run_services_once(now=NOW)
    close_visit(visit_repository,a);w.run_services_once(now='2026-10-12T15:36:00.000000Z')
    old=summaries(visit_repository,a)
    b=open_visit(visit_service,visit_repository,START+timedelta(days=1))
    at='2026-10-13T15:25:00.000000Z'
    w.run_services_once(now=at)
    assert summaries(visit_repository,b)==[]
    put(source,gen,evaluated('web.whatsapp.com',event='2026-10-13T14:30:00.000001Z',seed='only-B',at=at),at=at)
    with source.transaction():source.runtime('usable',at,poll=at,commit=at)
    w.run_services_once(now=at)
    assert [(r['service_id'],r['distinct_observation_count']) for r in summaries(visit_repository,b)]==[('service.whatsapp',1)]
    assert summaries(visit_repository,a)==old


@pytest.mark.parametrize('flag,policy,enabled',[
    (False,None,False),(False,'true',False),('false','true',False),
    (True,None,False),(True,'',False),(True,'0',False),(True,'366',False),
    (True,'True',True),(True,'２０',False),(True,'20.0',False),
    (True,'true',True),('true','true',True),(True,'false',False),
])
def test_composition_requires_explicit_bounded_policy_without_starting_workers(
    visit_config,monkeypatch,tmp_path,flag,policy,enabled,
):
    from app.visit_lifecycle.runtime import create_visit_lifecycle
    import app.network_metadata_projection.config as config_module
    source=tmp_path/'ni04.sqlite3'
    if policy is None:monkeypatch.delenv('VISIT_SERVICE_HISTORY_ENABLED',raising=False)
    else:monkeypatch.setenv('VISIT_SERVICE_HISTORY_ENABLED',policy)
    monkeypatch.setenv('VISIT_SERVICE_HISTORY_RETENTION_DAYS','1')  # Obsolete: not an activation input.
    # Protocol source failure is independent; it cannot create a second source
    # or prevent the explicit NI04 configuration from being validated.
    def unavailable():raise ValueError('synthetic unavailable protocol source')
    monkeypatch.setattr(config_module,'projection_config_from_env',unavailable)
    runtime=create_visit_lifecycle(dict(visit_lifecycle_enabled=True,
        visit_lifecycle_db_path=visit_config.db_path,visit_lifecycle_webhook_source=visit_config.webhook_source,
        web_admin_device_protocol_intelligence_enabled=flag,network_service_materialization_db_path=str(source)),
        logger=logging.getLogger('test296.composition'))
    try:
        assert runtime.enabled and runtime.available and runtime.webhook_reader.running is False
        assert runtime._reconciler is None and runtime.protocol_reader is None
        assert runtime.service_history_path==(str(source) if enabled else None)
        assert not hasattr(runtime,'service_history_ttl_days')
        assert not source.exists()  # Startup does not create/write the source DB.
    finally:assert runtime.close()
