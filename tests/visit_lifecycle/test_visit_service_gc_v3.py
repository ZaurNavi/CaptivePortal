"""#296 V3: bounded replay-safe GC and exact V6 cutover, disposable SQLite only."""
from contextlib import contextmanager
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
import json
import sqlite3
import time
import uuid

import pytest

from app.analytics.source_gateway import QueryDeadline
from app.network_metadata.validation import ni_timestamp
from app.network_metadata.models import NetworkMetadataValidationError
from app.network_service_recognition.materialization_repository import read_visit_delivery_page, MaterializationConflict
from app.visit_lifecycle.models import VisitSchemaError
from app.visit_lifecycle.repository import VisitRepository, _schema_sql_v4, _schema_sql_v5, _schema_signature, expected_visit_signature
from .test_visit_service_delivery import delivery, evaluated, put, open_visit, summaries, NOW
from .test_visit_service_lifetime import later, member, replay


def rows(repo):
    with repo.read_connection() as c:
        return [dict(r) for r in c.execute('SELECT * FROM visit_service_membership')]


def test_source_retention_never_age_prunes_unacknowledged_delivery(delivery, visit_repository):
    source, gen, worker = delivery
    put(source, gen, evaluated())
    outbox = tuple(tuple(r) for r in source.connection.execute('SELECT * FROM ni04_visit_delivery_outbox ORDER BY outbox_seq'))
    assert visit_repository.service_consumer_cursor() is None
    source.clock = lambda: ni_timestamp(NOW, canonical=True)+timedelta(days=3)
    source.retain()
    assert tuple(tuple(r) for r in source.connection.execute('SELECT * FROM ni04_visit_delivery_outbox ORDER BY outbox_seq')) == outbox
    assert source.connection.execute('SELECT count(*) FROM device_service_rollups').fetchone()[0] == 0
    assert source.connection.execute('PRAGMA foreign_key_check').fetchall() == []


def test_source_cutover_keeps_saved_visit_and_unacknowledged_stream(delivery, visit_repository, visit_service):
    source, gen, worker = delivery
    visit = open_visit(visit_service, visit_repository)
    put(source, gen, evaluated())
    worker.run_services_once(now=NOW)
    saved = summaries(visit_repository, visit)
    assert saved
    source.retain()  # Verified durable ACK can advance only this prefix.
    floor = source.connection.execute('SELECT floor_seq,floor_hash FROM ni04_visit_delivery_outbox WHERE outbox_seq=0').fetchone()
    put(source, gen, evaluated(seed='unacknowledged-before-cutover'))
    pending = tuple(tuple(r) for r in source.connection.execute('SELECT * FROM ni04_visit_delivery_outbox ORDER BY outbox_seq'))
    cursor = visit_repository.service_consumer_cursor()
    source.clock = lambda: ni_timestamp(NOW, canonical=True)+timedelta(days=91)
    source.retain()
    assert tuple(tuple(r) for r in source.connection.execute('SELECT * FROM ni04_visit_delivery_outbox ORDER BY outbox_seq')) == pending
    assert tuple(source.connection.execute('SELECT floor_seq,floor_hash FROM ni04_visit_delivery_outbox WHERE outbox_seq=0').fetchone()) == tuple(floor)
    assert summaries(visit_repository, visit) == saved
    assert visit_repository.service_consumer_cursor() == cursor
    assert source.connection.execute('SELECT count(*) FROM device_service_rollups').fetchone()[0] == 0


@pytest.mark.parametrize('age,eligible',[(3599,True),(3600,False),(3601,False)])
@pytest.mark.parametrize('direct',[False,True])
def test_new_first_credit_event_age_gate_including_direct_visit(delivery,visit_repository,visit_service,age,eligible,direct):
    source,gen,w=delivery
    visit=open_visit(visit_service,visit_repository) if direct else None
    put(source,gen,evaluated(event=later(-age)))
    w.run_services_once(now=NOW)
    assert bool(rows(visit_repository)) is eligible
    if direct:assert bool(summaries(visit_repository,visit)) is eligible
    assert visit_repository.service_consumer_cursor()['last_outbox_seq']==2
    assert w._service_linkage.counts['rejected_old_first_delivery']==int(not eligible)
    source.retain()
    assert source.connection.execute('SELECT count(*) FROM ni04_visit_delivery_outbox').fetchone()[0]==1


@pytest.mark.parametrize('age',[0,-1])
def test_future_delivery_or_invalid_clock_never_advances_checkpoint(delivery,visit_repository,age):
    source,gen,w=delivery
    # Produce normally in the future fixture, then evaluate Visit earlier.
    put(source,gen,evaluated(event=later(1),at=later(2)),at=later(2))
    with pytest.raises(MaterializationConflict):w.run_services_once(now=later(age))
    assert visit_repository.service_consumer_cursor() is None and rows(visit_repository)==[]
    source.retain()
    assert source.connection.execute("SELECT count(*) FROM ni04_visit_delivery_outbox WHERE kind='positive'").fetchone()[0]==1


def test_new_invalid_event_timestamp_rolls_back_without_false_ack(delivery,visit_repository):
    from app.network_service_recognition.materialization_repository import visit_delivery_hash
    source,gen,w=delivery;put(source,gen,evaluated())
    raw=dict(source.connection.execute('SELECT * FROM ni04_visit_delivery_outbox WHERE outbox_seq=2').fetchone())
    raw['observed_at']='not-utc'
    hashed=visit_delivery_hash(raw)
    source.connection.execute('UPDATE ni04_visit_delivery_outbox SET observed_at=?,entry_hash=? WHERE outbox_seq=2',('not-utc',hashed))
    source.connection.execute('UPDATE ni04_visit_delivery_outbox SET head_hash=? WHERE outbox_seq=0',(hashed,))
    with pytest.raises((MaterializationConflict,NetworkMetadataValidationError)):w.run_services_once(now=NOW)
    assert visit_repository.service_consumer_cursor() is None and rows(visit_repository)==[]


@pytest.mark.parametrize('seconds,attached',[(3599,True),(3600,False)])
def test_existing_pending_uses_its_own_p_not_the_older_event_time(delivery,visit_repository,visit_service,seconds,attached):
    source,gen,w=delivery;put(source,gen,evaluated(event=later(-300)));w.run_services_once(now=NOW)
    assert member(visit_repository)['observed_at']==later(-300)
    visit=open_visit(visit_service,visit_repository)
    replay(source,later(seconds));w.run_services_once(now=later(seconds))
    assert bool(summaries(visit_repository,visit)) is attached
    if attached:assert member(visit_repository)['pending_since']=='2026-10-12T15:25:00.000Z'
    else:assert rows(visit_repository)==[]


@pytest.mark.parametrize('point,committed',[('visit_before_commit',False),('visit_after_commit',True)])
def test_gc_and_count_and_cursor_commit_or_rollback_together(delivery,visit_repository,point,committed):
    source,gen,w=delivery;put(source,gen,evaluated());w.run_services_once(now=NOW)
    before=visit_repository.service_consumer_cursor()
    def crash(stage):
        if stage==point:raise RuntimeError('synthetic GC fault')
    with pytest.raises(RuntimeError):w.run_services_once(now=later(3600),crash_point=crash)
    assert len(rows(visit_repository))==int(not committed)
    after=visit_repository.service_consumer_cursor()
    assert after['detached_count']==int(not committed)
    assert (after['last_outbox_seq'],after['last_outbox_hash'])==(before['last_outbox_seq'],before['last_outbox_hash'])
    restarted=VisitRepository(w.config);assert restarted.initialize() is False
    replay(source,later(3601));w.run_services_once(now=later(3601))
    assert rows(restarted)==[] and restarted.service_consumer_cursor()['detached_count']==0


def exact_legacy_copy(repo,path,version):
    with sqlite3.connect(path) as target, repo.read_connection() as source:
        target.row_factory=sqlite3.Row;target.executescript({4:_schema_sql_v4,5:_schema_sql_v5}[version]())
        for (table,) in target.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
            columns=[r[1] for r in target.execute('PRAGMA table_info('+table+')')]
            for row in source.execute('SELECT * FROM '+table):
                values=[37 if k=='history_ttl_days' else row[k] for k in columns]
                target.execute('INSERT INTO '+table+'('+','.join(columns)+') VALUES('+','.join('?' for _ in values)+')',values)
        assert _schema_signature(target)==expected_visit_signature(version)


@pytest.mark.parametrize('version',[4,5])
def test_populated_cutover_preserves_attached_history_and_checkpoint_fences_removed_pending(delivery,visit_repository,visit_service,tmp_path,version):
    source,gen,w=delivery;put(source,gen,evaluated());w.run_services_once(now=NOW)
    visit=open_visit(visit_service,visit_repository);w.run_services_once(now=NOW)
    # A distinct post-Visit-closure event is still fresh and really detached.
    from .test_visit_service_delivery import close_visit
    close_visit(visit_repository,visit,'2026-10-12T15:20:00.000Z')
    put(source,gen,evaluated(seed='legacy-detached',event=later(-60)));w.run_services_once(now=NOW)
    saved=summaries(visit_repository,visit);before=visit_repository.service_consumer_cursor()
    source_before=tuple(source.connection.iterdump())
    path=tmp_path/('populated-v'+str(version)+'.sqlite3');exact_legacy_copy(visit_repository,path,version)
    cutoff=later(10)
    target=VisitRepository(replace(w.config,db_path=str(path)),migration_clock=lambda:ni_timestamp(cutoff,canonical=True))
    assert target.initialize() is False
    after=target.service_consumer_cursor()
    assert after==dict(before,detached_count=0,first_credit_floor_utc=cutoff)
    assert summaries(target,visit)==saved
    assert len(rows(target))==1 and rows(target)[0]['visit_id']==visit.visit_id
    with target.read_connection() as c:
        assert c.execute('PRAGMA user_version').fetchone()[0]==6
        assert _schema_signature(c)==expected_visit_signature(6)
    assert tuple(source.connection.iterdump())==source_before
    # The floor is durable/idempotent, not recomputed on the next startup.
    target._migration_clock=lambda:ni_timestamp(later(7200),canonical=True)
    assert target.initialize() is False and target.service_consumer_cursor()==after
    from app.visit_lifecycle.reconciliation import VisitLinkReconciler
    replacement=VisitLinkReconciler(config=w.config,repository=target,registry_read_service=None,
        telemetry=w.telemetry,service_history_path=source.db_path)
    # Every already delivered source fact is below F; higher legitimate seq
    # cannot restart removed staging, including a still-fresh source E.
    from app.network_service_recognition.materialization_repository import VISIT_DELIVERY_FIELDS
    raw=source.connection.execute("SELECT * FROM ni04_visit_delivery_outbox WHERE kind='positive' ORDER BY outbox_seq DESC LIMIT 1").fetchone()
    fields={k:raw[k] for k in VISIT_DELIVERY_FIELDS if k not in ('outbox_seq','stream_id','kind','created_at','previous_hash')}
    with source.transaction():source.append_visit_delivery('positive',later(11),**fields)
    replacement.run_services_once(now=later(11))
    assert len(rows(target))==1 and target.service_consumer_cursor()['detached_count']==0
    assert target.service_consumer_cursor()['first_credit_floor_utc']==cutoff


@pytest.mark.parametrize('version',[4,5])
@pytest.mark.parametrize('fault',['future','invalid','before-commit','after-commit'])
def test_cutover_faults_leave_atomic_schema_fence_and_unlinked_cleanup(delivery,visit_repository,tmp_path,monkeypatch,version,fault):
    source,gen,w=delivery;put(source,gen,evaluated());w.run_services_once(now=NOW)
    path=tmp_path/(str(version)+'-'+fault+'.sqlite3');exact_legacy_copy(visit_repository,path,version)
    with sqlite3.connect(path) as c:
        if fault in ('future','invalid'):
            c.execute('UPDATE visit_service_membership SET observed_at=?',
                (later(200) if fault=='future' else 'invalid',))
        original=tuple(c.iterdump())
    target=VisitRepository(replace(w.config,db_path=str(path)),migration_clock=lambda:ni_timestamp(NOW,canonical=True))
    if fault in ('before-commit','after-commit'):
        original_check=target._startup_check;checks=[]
        def check(c):
            original_check(c);checks.append(1)
            if len(checks)==(1 if fault=='before-commit' else 2):raise RuntimeError('cutover fault')
        monkeypatch.setattr(target,'_startup_check',check)
    with pytest.raises((VisitSchemaError,RuntimeError)):target.initialize()
    with sqlite3.connect(path) as c:
        if fault=='after-commit':
            assert c.execute('PRAGMA user_version').fetchone()[0]==6
            assert c.execute('SELECT first_credit_floor_utc,detached_count FROM visit_service_consumer_state').fetchone()==(NOW,0)
            assert c.execute('SELECT count(*) FROM visit_service_membership').fetchone()[0]==0
        else:
            assert c.execute('PRAGMA user_version').fetchone()[0]==version
            assert tuple(c.iterdump())==original


def test_fresh_v6_has_no_gratuitous_floor(delivery,visit_repository):
    source,gen,w=delivery;put(source,gen,evaluated());w.run_services_once(now=NOW)
    assert visit_repository.service_consumer_cursor()['first_credit_floor_utc'] is None
    with visit_repository.read_connection() as c:assert _schema_signature(c)==expected_visit_signature(6)


def seed_detached(repo,template,count,offset,at):
    """State stress fixture, NOT a claim that all rows came through source IO."""
    columns=tuple(template)
    def values():
        for i in range(offset,offset+count):
            row=dict(template,edge_id=sha256(('296-v3-cap-'+str(i)).encode()).hexdigest(),
                source_ref=str(uuid.uuid5(uuid.NAMESPACE_URL,'296-v3-cap-'+str(i))),
                source_observation_id=sha256(('296-v3-observation-'+str(i)).encode()).hexdigest(),
                observed_at=later(at-1),pending_since=later(at)[:23]+'Z',created_at=later(at)[:23]+'Z',
                updated_at=later(at)[:23]+'Z')
            row['fact_key']=repo._service_fact_key(row)
            yield tuple(row[k] for k in columns)
    with repo._connect() as c:
        c.execute('BEGIN IMMEDIATE')
        c.executemany('INSERT INTO visit_service_membership('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')',values())
        c.execute('UPDATE visit_service_consumer_state SET detached_count=detached_count+?',(count,));c.commit()


def gc_page(source,repo,at,interruptions=None):
    for attempt in range(5):
        cursor=repo.service_consumer_cursor()
        page=read_visit_delivery_page(source.db_path,cursor,deadline=QueryDeadline.after(2))
        assert page['entries']==()
        try:
            repo.consume_service_delivery(page,cursor,now=later(at)[:23]+'Z',deadline=time.monotonic()+2)
        except sqlite3.OperationalError as error:
            # The unchanged 50ms priority-writer guard may cancel a chunk.
            # Prove rollback before a finite next-tick retry; never extend it.
            if str(error)!='interrupted' or attempt==4:raise
            assert repo.service_consumer_cursor()==cursor
            if interruptions is not None:interruptions.append(attempt+1)
            continue
        # The public result also counts bounded corrective review. Measure
        # physical removals, not total transitions, for the GC batch contract.
        return cursor['detached_count']-repo.service_consumer_cursor()['detached_count']


def test_100001_cumulative_gc_is_bounded_and_next_genuine_source_event_progresses(delivery,visit_repository,tmp_path):
    source,gen,w=delivery;put(source,gen,evaluated());w.run_services_once(now=NOW)
    template=member(visit_repository);assert gc_page(source,visit_repository,3600)==1
    calls=[];interruptions=[]
    # 1 real original + 4 x 25000 distinct state-seeded facts. Every removal
    # uses the real bounded Visit writer; no direct DELETE/cap reset.
    # Keep an idle RO connection (no read transaction) to avoid forcing a
    # last-connection WAL checkpoint on each of 4000 synthetic batches. WAL/
    # FULL and each real writer commit remain unchanged; this is not an IOPS
    # benchmark or a claim about the production connection population.
    with visit_repository.read_connection():
        for window in range(4):
            seed_detached(visit_repository,template,25000,window*25000,7200*(window+1))
            while visit_repository.service_consumer_cursor()['detached_count']:
                assert len(calls)<4100
                removed=gc_page(source,visit_repository,7200*(window+1)+3600,interruptions)
                assert 1<=removed<=25;calls.append(removed)
            assert rows(visit_repository)==[]
    at=36000
    put(source,gen,evaluated(seed='genuine-after-100001',event=later(at-1),at=later(at)),at=later(at))
    w.run_services_once(now=later(at))
    assert len(rows(visit_repository))==1 and visit_repository.service_consumer_cursor()['detached_count']==1
    assert visit_repository.service_consumer_cursor()['last_outbox_seq']==3
    (tmp_path/'cumulative-gc-evidence.json').write_text(json.dumps(dict(
        cumulative_removed=100001,synthetic_membership_rows=100000,real_initial_fact=1,
        real_boundary_source_event=True,gc_calls=len(calls)+1,max_batch=max(calls),
        final_detached_count=1,guard_interrupted_rolled_back_attempts=len(interruptions),
        idle_ro_connection_without_read_transaction=True,
        physical_host_hdd_io='NOT_MEASURED'),indent=2),encoding='utf-8')


def test_100000_concurrent_live_rows_halt_without_ack_then_gc_reopens(delivery,visit_repository):
    source,gen,w=delivery;put(source,gen,evaluated());w.run_services_once(now=NOW)
    seed_detached(visit_repository,member(visit_repository),99999,200000,0)
    before=visit_repository.service_consumer_cursor()
    put(source,gen,evaluated(seed='over-live-cap'))
    with pytest.raises(VisitSchemaError,match='capacity'):w.run_services_once(now=NOW)
    assert visit_repository.service_consumer_cursor()==before
    source.retain()
    assert source.connection.execute("SELECT count(*) FROM ni04_visit_delivery_outbox WHERE kind='positive'").fetchone()[0]==1
    # Exactly 25 expired rows can be reclaimed per transaction. Old queued
    # delivery is age-rejected, while a fresh real source fact can now enter.
    put(source,gen,evaluated(seed='new-live-after-gc',event=later(3600),at=later(3601)),at=later(3601))
    w.run_services_once(now=later(3601))
    after=visit_repository.service_consumer_cursor()
    assert after['last_outbox_seq']==source.connection.execute('SELECT head_seq FROM ni04_visit_delivery_outbox WHERE outbox_seq=0').fetchone()[0]
    with visit_repository.read_connection() as c:
        actual=c.execute('SELECT count(*) FROM visit_service_membership WHERE visit_id IS NULL').fetchone()[0]
    assert after['detached_count']==actual<100000


@contextmanager
def real_source_chain(tmp_path,visit_repository):
    from tests.network_metadata import source_event,record,outcome
    from tests.network_service_recognition.test_protected_readers import store
    from tests.network_metadata_projection.support import stack,RegistryEvaluation,MAC
    from tests.network_service_recognition.test_summary import DEVICE
    from app.network_metadata.projection_source import NetworkMetadataProjectionSourceReadService
    from app.network_service_recognition.source_adapter import WorkerSourceReadService
    from app.network_metadata_projection.service_extension import install_service_recognition_extension
    from app.network_metadata_projection.service_delivery_read_service import ServiceRecognitionDeliveryReadService
    from app.network_service_recognition.materialization_repository import ServiceMaterializationRepository
    from app.network_service_recognition.worker import ServiceMaterializationWorker
    from tests.network_service_recognition.support import bundle
    event=source_event('tls',timestamp=later(-300),dest_ip='203.0.113.93',proto='TCP')
    event['tls']['sni']='www.youtube.com';data=record(event)
    with store(tmp_path,source=data+b'\n') as ni01:
        ni01.clock.value=ni_timestamp(NOW,canonical=True)
        ni01.repo.ingest_batch([outcome(ni01.config.capture_scope_binding,data,generation=ni01.generation.source_generation_id)],ni01.run,ni01.health,ni01.anchor)
        source_ref=ni01.repo.connection.execute('SELECT observation_id FROM network_metadata_observations').fetchone()[0]
        original=NetworkMetadataProjectionSourceReadService(ni01.config.db_path).get_projection_source_record(source_ref)
        ni02=stack(tmp_path,[original]);ni02.clock.value=ni_timestamp(NOW,canonical=True)
        install_service_recognition_extension(ni02.repo)
        resolve=ni02.attribution.resolve_ipv4
        def authority(*args):
            value=resolve(*args)
            return replace(value,valid_from='2026-10-12T00:00:00.000Z',valid_until='2026-10-13T00:00:00.000Z') if value.state=='resolved' else value
        ni02.attribution.resolve_ipv4=authority
        ni02.attribution.states['203.0.113.93']='endpoint_absent'
        ni02.registry.values[MAC]=RegistryEvaluation('authoritative',DEVICE)
        ni02.service.poll()
        with pytest.raises(sqlite3.IntegrityError,match='immutable_projection_fact'):
            ni02.repo.connection.execute('UPDATE device_network_metadata_edges SET event_at=?',(later(-60),))
        ni04=ServiceMaterializationRepository(str(tmp_path/'real-ni04.sqlite3'),
            visit_delivery_db_path=str(visit_repository.db_path),clock=lambda:ni_timestamp(NOW,canonical=True)).initialize()
        projection=ServiceRecognitionDeliveryReadService(ni02.config.db_path,clock=lambda:ni_timestamp(NOW,canonical=True))
        source=WorkerSourceReadService(ni01.config.db_path)
        worker=ServiceMaterializationWorker(ni04,projection,source,bundle(),clock=lambda:ni_timestamp(NOW,canonical=True))
        try:yield ni01,ni02,ni04,worker,original
        finally:ni04.close();ni02.repo.close()


@pytest.mark.parametrize('conflict',[None,'ni02_digest','ni01_time','generation_replay_after_gc'])
def test_supported_end_to_end_source_boundary_not_private_helper_forgery(tmp_path,visit_repository,visit_service,visit_config,monkeypatch,conflict):
    from app.network_metadata_projection.service_delivery_read_service import ServiceRecognitionDeliveryReadService
    from app.network_metadata_projection.models import ProjectionUnavailable
    from app.network_service_recognition.models import ServiceUnavailable
    from app.visit_lifecycle.reconciliation import VisitLinkReconciler
    from app.visit_lifecycle.telemetry import VisitTelemetry
    import logging
    with real_source_chain(tmp_path,visit_repository) as (ni01,ni02,ni04,worker,original):
        visit=None if conflict=='generation_replay_after_gc' else open_visit(visit_service,visit_repository)
        if conflict=='ni02_digest':
            checked=ServiceRecognitionDeliveryReadService._candidate
            def corrupted(cls,row):
                return checked(dict(row,edge_semantic_digest='f'*64))
            monkeypatch.setattr(ServiceRecognitionDeliveryReadService,'_candidate',classmethod(corrupted))
        elif conflict=='ni01_time':
            checked=worker.source.read_recognition_evidence
            def mismatch(*args,**kwargs):return tuple(replace(row,event_at=later(-60)) for row in checked(*args,**kwargs))
            monkeypatch.setattr(worker.source,'read_recognition_evidence',mismatch)
        if conflict in ('ni02_digest','ni01_time'):
            with pytest.raises((ProjectionUnavailable,ServiceUnavailable)):worker.cycle()
            assert ni04.connection.execute('SELECT count(*) FROM service_recognition_observations').fetchone()[0]==0
            assert ni04.connection.execute("SELECT count(*) FROM ni04_visit_delivery_outbox WHERE kind='positive'").fetchone()[0]==0
            assert visit_repository.service_consumer_cursor() is None and summaries(visit_repository,visit)==[]
        else:
            for _ in range(3):worker.cycle()
            fact=ni04.connection.execute('SELECT observed_at,source_observation_ref FROM service_recognition_observations').fetchone()
            assert tuple(fact)==(original.event_at,original.observation_id)
            consumer=VisitLinkReconciler(config=visit_config,repository=visit_repository,registry_read_service=None,
                telemetry=VisitTelemetry(logging.getLogger('test296.real-chain')),service_history_path=ni04.db_path)
            consumer.run_services_once(now=NOW)
            if visit is not None:
                assert summaries(visit_repository,visit)[0]['distinct_observation_count']==1
                assert summaries(visit_repository,visit)[0]['first_observed_at']==original.event_at
            else:
                assert len(rows(visit_repository))==1
                consumer.run_services_once(now=later(3600));assert rows(visit_repository)==[]
                # A new admitted knowledge generation invokes the actual
                # binding replay/backfill paths against the same protected
                # NI02/NI01 stores. No forged helper input or changed E.
                from tests.network_service_recognition.support import documents,encode
                from app.network_service_recognition.artifacts import load_bundle
                from app.network_service_recognition.worker import ServiceMaterializationWorker
                docs=documents();docs[0]['taxonomy_version']+=1;docs[2]['ruleset_version']+=1
                admitted=load_bundle(*encode(docs))
                prior_head=ni04.connection.execute('SELECT head_seq FROM ni04_visit_delivery_outbox WHERE outbox_seq=0').fetchone()[0]
                replacement=ServiceMaterializationWorker(ni04,worker.projection,worker.source,admitted,
                    clock=lambda:ni_timestamp(later(3601),canonical=True))
                for _ in range(3):replacement.cycle()
                positives=ni04.connection.execute("SELECT observed_at FROM ni04_visit_delivery_outbox WHERE kind='positive'").fetchall()
                assert positives and {r[0] for r in positives}=={original.event_at}
                observations=ni04.connection.execute('SELECT generation_id,observed_at FROM service_recognition_observations').fetchall()
                assert len(observations)==2 and len({r[0] for r in observations})==2
                assert {r[1] for r in observations}=={original.event_at}
                assert ni04.connection.execute('SELECT head_seq FROM ni04_visit_delivery_outbox WHERE outbox_seq=0').fetchone()[0]>prior_head
                assert ni04.connection.execute("SELECT count(*) FROM service_binding_replay_jobs WHERE generation_id=? AND state='complete'",(replacement.generation_id,)).fetchone()[0]>=1
                consumer.run_services_once(now=later(3601))
                assert rows(visit_repository)==[] and visit_repository.service_consumer_cursor()['detached_count']==0
                assert consumer._service_linkage.counts['rejected_old_first_delivery']>=1


@pytest.mark.parametrize('offset,accepted',[(0,False),(1,True)])
def test_cutover_floor_equality_rejects_but_newer_first_credit_works(delivery,visit_repository,tmp_path,offset,accepted):
    source,gen,w=delivery;put(source,gen,evaluated());w.run_services_once(now=NOW)
    path=tmp_path/'floor-v5.sqlite3';exact_legacy_copy(visit_repository,path,5)
    target=VisitRepository(replace(w.config,db_path=str(path)),migration_clock=lambda:ni_timestamp(NOW,canonical=True))
    target.initialize()
    from app.visit_lifecycle.reconciliation import VisitLinkReconciler
    consumer=VisitLinkReconciler(config=w.config,repository=target,registry_read_service=None,
        telemetry=w.telemetry,service_history_path=source.db_path)
    put(source,gen,evaluated(seed='floor-boundary',event=later(offset),at=later(2)),at=later(2))
    consumer.run_services_once(now=later(2))
    assert bool(rows(target)) is accepted
    assert target.service_consumer_cursor()['first_credit_floor_utc']==NOW


def test_corrupt_pending_clock_rolls_back_gc_and_does_not_ack(delivery,visit_repository):
    source,gen,w=delivery;put(source,gen,evaluated());w.run_services_once(now=NOW)
    before=visit_repository.service_consumer_cursor()
    with visit_repository._connect() as c:c.execute('UPDATE visit_service_membership SET pending_since=?',(later(-3599)[:23]+'Z',))
    with pytest.raises(VisitSchemaError,match='clock'):w.run_services_once(now=later(3600))
    assert visit_repository.service_consumer_cursor()==before and len(rows(visit_repository))==1


def test_corrupt_detached_key_is_not_silently_purged(delivery,visit_repository):
    source,gen,w=delivery;put(source,gen,evaluated());w.run_services_once(now=NOW)
    before=visit_repository.service_consumer_cursor()
    with visit_repository._connect() as c:c.execute("UPDATE visit_service_membership SET fact_key=?",('f'*64,))
    with pytest.raises(VisitSchemaError,match='identity'):w.run_services_once(now=later(3600))
    assert visit_repository.service_consumer_cursor()==before and len(rows(visit_repository))==1


def test_v5_cutover_count_conflict_rolls_back_without_cleanup(delivery,visit_repository,tmp_path):
    source,gen,w=delivery;put(source,gen,evaluated());w.run_services_once(now=NOW)
    path=tmp_path/'count-conflict.sqlite3';exact_legacy_copy(visit_repository,path,5)
    with sqlite3.connect(path) as c:
        c.execute('UPDATE visit_service_consumer_state SET detached_count=detached_count+1');c.commit()
        original=tuple(c.iterdump())
    target=VisitRepository(replace(w.config,db_path=str(path)),migration_clock=lambda:ni_timestamp(NOW,canonical=True))
    with pytest.raises(VisitSchemaError,match='count'):target.initialize()
    with sqlite3.connect(path) as c:
        assert tuple(c.iterdump())==original and c.execute('PRAGMA user_version').fetchone()[0]==5


@pytest.mark.parametrize('version',[4,5])
def test_disposable_paired_backup_restore_retains_old_source_floor_and_visit_checkpoint(delivery,visit_repository,tmp_path,version):
    source,gen,w=delivery;put(source,gen,evaluated());w.run_services_once(now=NOW)
    path=tmp_path/'cutover-visits.sqlite3';exact_legacy_copy(visit_repository,path,version)
    source_backup=tmp_path/'paired-ni04.sqlite3';visit_backup=tmp_path/'paired-visits.sqlite3'
    with sqlite3.connect(source_backup) as backup:source.connection.backup(backup)
    with sqlite3.connect(path) as before,sqlite3.connect(visit_backup) as backup:before.backup(backup)
    cursor=visit_repository.service_consumer_cursor()
    target=VisitRepository(replace(w.config,db_path=str(path)),migration_clock=lambda:ni_timestamp(NOW,canonical=True))
    target.initialize();source.visit_delivery_db_path=str(path)
    source.retain()
    assert source.connection.execute('SELECT floor_seq FROM ni04_visit_delivery_outbox WHERE outbox_seq=0').fetchone()[0]==cursor['last_outbox_seq']
    # Restore BOTH snapshots to new disposable paths. Never downgrade a schema
    # marker or clear SQLite native sidecars; no file-level live replacement.
    restored_source=tmp_path/'restored-ni04.sqlite3';restored_visit=tmp_path/'restored-visits.sqlite3'
    for backup,path in ((source_backup,restored_source),(visit_backup,restored_visit)):
        with sqlite3.connect(backup) as before,sqlite3.connect(path) as restored:before.backup(restored)
    with sqlite3.connect(restored_visit) as c:
        assert c.execute('PRAGMA user_version').fetchone()[0]==version
        assert _schema_signature(c)==expected_visit_signature(version)
        last=c.execute('SELECT consumer_id,source_stream_id,last_outbox_seq,last_outbox_hash FROM visit_service_consumer_state').fetchone()
        assert last==tuple(cursor[k] for k in ('consumer_id','source_stream_id','last_outbox_seq','last_outbox_hash'))
        assert c.execute('SELECT count(*) FROM visit_service_membership').fetchone()[0]==1
    with sqlite3.connect(restored_source) as c:
        assert c.execute('SELECT floor_seq FROM ni04_visit_delivery_outbox WHERE outbox_seq=0').fetchone()[0]==0
    page=read_visit_delivery_page(str(restored_source),cursor,deadline=QueryDeadline.after(2))
    assert page['after_seq']==cursor['last_outbox_seq'] and page['entries']==()
