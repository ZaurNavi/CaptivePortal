"""#296 v2: parent-owned history, durable one-hour staging, private aggregates."""
from dataclasses import replace
from datetime import datetime, timedelta
import logging
import sqlite3
import time

import pytest

from app.visit_lifecycle.repository import VisitRepository, _schema_sql_v4, _schema_signature, expected_visit_signature
from app.visit_lifecycle.models import VisitSchemaError
from app.visit_lifecycle.read_service import project_visit_service_history
from app.visit_lifecycle.reconciliation import VisitLinkReconciler
from app.visit_lifecycle.telemetry import VisitTelemetry, VisitServiceLinkageTelemetry, LINKAGE_COUNTER_FIELDS
from .test_visit_service_delivery import delivery, evaluated, open_visit, put, close_visit, summaries, NOW


def later(seconds):
    return (datetime.fromisoformat(NOW.replace('Z','+00:00'))+timedelta(seconds=seconds)).isoformat(timespec='microseconds').replace('+00:00','Z')


def member(repo):
    with repo.read_connection() as c:
        return dict(c.execute('SELECT * FROM visit_service_membership').fetchone())


def replay(source, at):
    from app.network_service_recognition.materialization_repository import VISIT_DELIVERY_FIELDS
    row=source.connection.execute("SELECT * FROM ni04_visit_delivery_outbox WHERE kind='positive' LIMIT 1").fetchone()
    fields={k:row[k] for k in VISIT_DELIVERY_FIELDS if k not in ('outbox_seq','stream_id','kind','created_at','previous_hash')}
    with source.transaction():source.append_visit_delivery('positive',at,**fields)


@pytest.mark.parametrize('seconds,attached',[(3599,True),(3600,False),(3601,False),(86400,False)])
def test_real_visit_late_binding_exact_one_hour_boundary(delivery,visit_repository,visit_service,seconds,attached):
    source,gen,w=delivery;put(source,gen,evaluated());w.run_services_once(now=NOW)
    first=member(visit_repository)['pending_since']
    visit=open_visit(visit_service,visit_repository)
    w.run_services_once(now=later(seconds))
    with visit_repository.read_connection() as c:row=c.execute('SELECT * FROM visit_service_membership').fetchone()
    if attached:
        assert row['pending_since']==first=='2026-10-12T15:25:00.000Z'
        assert row['visit_id']==visit.visit_id and row['status']=='provisional'
    else:assert row is None
    assert bool(summaries(visit_repository,visit)) is attached


@pytest.mark.parametrize('expiry_before_restart',[False,True])
def test_repeat_generation_replay_and_restart_never_restart_pending_clock(delivery,visit_repository,visit_service,expiry_before_restart):
    source,gen,w=delivery;put(source,gen,evaluated());w.run_services_once(now=NOW)
    original=member(visit_repository)
    replay(source,later(100));w.run_services_once(now=later(100))
    assert member(visit_repository)['pending_since']==original['pending_since']
    if expiry_before_restart:w.run_services_once(now=later(3600))
    replacement=VisitLinkReconciler(config=w.config,repository=VisitRepository(w.config),registry_read_service=None,
        telemetry=w.telemetry,service_history_path=source.db_path)
    assert replacement.repository.initialize() is False
    visit=open_visit(visit_service,visit_repository)
    replay(source,later(3600));replacement.run_services_once(now=later(3600))
    with visit_repository.read_connection() as c:assert c.execute('SELECT count(*) FROM visit_service_membership').fetchone()[0]==0
    assert visit_repository.service_consumer_cursor()['detached_count']==0
    assert summaries(visit_repository,visit)==[]
    assert visit_repository.service_consumer_cursor()['last_outbox_seq']==source.connection.execute('SELECT head_seq FROM ni04_visit_delivery_outbox WHERE outbox_seq=0').fetchone()[0]


@pytest.mark.parametrize('days',[1,15,31,366])
def test_attached_history_has_no_secondary_age_clock_and_parent_cascades(delivery,visit_repository,visit_service,days):
    source,gen,w=delivery;visit=open_visit(visit_service,visit_repository)
    put(source,gen,evaluated());w.run_services_once(now=NOW);close_visit(visit_repository,visit)
    w.run_services_once(now=later(16*60))
    saved=summaries(visit_repository,visit);assert saved and saved[0]['finalized_at']
    w.run_services_once(now=later(days*86400))
    assert summaries(visit_repository,visit)==saved
    current=visit_repository.get_visit(visit.site_id,visit.visit_id)
    dto=project_visit_service_history(current,saved,visit_repository.service_consumer_cursor(),evaluated_now=later(days*86400))
    assert [r['service_id'] for r in dto['services']]==['service.youtube']
    assert member(visit_repository)['visit_id']==visit.visit_id
    # A real NI03 child shares exactly the same physical parent lifetime.
    from app.visit_lifecycle.models import protocol_visit_guard
    with visit_repository._connect() as c:
        c.execute("INSERT INTO visit_network_protocol_summary(visit_id,summary_version,site_id,client_mac,visit_guard,visit_started_at,summary_state,source_coverage,attribution_coverage,partial_reason,evaluated_at) VALUES(?,1,?,?,?,?,'partial','unknown','unknown','bounded_source',?)",
            (visit.visit_id,visit.site_id,visit.client_mac,protocol_visit_guard(current),visit.started_at,NOW))
        c.execute('DELETE FROM visits WHERE visit_id=?',(visit.visit_id,))
    with visit_repository.read_connection() as c:
        for table in ('visit_service_membership','visit_service_summary','visit_network_protocol_summary'):
            assert c.execute('SELECT count(*) FROM '+table).fetchone()[0]==0


@pytest.mark.parametrize('status,reason',[('pending','no_visit'),('ambiguous','conflicting_fact'),('invalidated','binding_changed')])
def test_every_detached_state_expires_but_does_not_delete_other_summary(delivery,visit_repository,visit_service,status,reason):
    source,gen,w=delivery;visit=open_visit(visit_service,visit_repository);put(source,gen,evaluated());w.run_services_once(now=NOW)
    close_visit(visit_repository,visit,'2026-10-12T14:40:00.000Z')
    put(source,gen,evaluated(seed='unrelated',event='2026-10-12T14:45:00.000001Z'));w.run_services_once(now=NOW)
    saved=summaries(visit_repository,visit)
    with visit_repository._connect() as c:
        c.execute('UPDATE visit_service_membership SET status=?,reason=? WHERE visit_id IS NULL',(status,reason))
    w.run_services_once(now=later(3600))
    assert summaries(visit_repository,visit)==saved
    with visit_repository.read_connection() as c:
        assert c.execute('SELECT count(*) FROM visit_service_membership WHERE visit_id IS NULL').fetchone()[0]==0


def as_v4(source_repo, path):
    """Real exact V4 populated copy, not a fake user_version downgrade."""
    with sqlite3.connect(path) as dest, source_repo.read_connection() as src:
        dest.row_factory=sqlite3.Row;dest.executescript(_schema_sql_v4())
        for (table,) in dest.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
            columns=[r[1] for r in dest.execute('PRAGMA table_info('+table+')')]
            for raw in src.execute('SELECT * FROM '+table):
                values=[37 if key=='history_ttl_days' else raw[key] for key in columns]
                dest.execute('INSERT INTO '+table+'('+','.join(columns)+') VALUES('+','.join('?' for _ in values)+')',values)
        assert _schema_signature(dest)==expected_visit_signature(4)


def test_populated_v4_migration_preserves_every_history_and_ack_identity(delivery,visit_repository,visit_service,tmp_path):
    source,gen,w=delivery;visit=open_visit(visit_service,visit_repository);put(source,gen,evaluated());w.run_services_once(now=NOW)
    before=visit_repository.service_consumer_cursor();saved=summaries(visit_repository,visit)
    path=tmp_path/'real-v4.sqlite3';as_v4(visit_repository,path)
    source.visit_delivery_db_path=str(path)
    assert source._visit_acknowledgement() is None  # Old policy must not authorize the new producer.
    migrated=VisitRepository(replace(w.config,db_path=str(path)))
    assert migrated.initialize() is False
    assert migrated.service_consumer_cursor()==before
    assert summaries(migrated,visit)==saved
    assert member(migrated)['pending_since']==member(migrated)['created_at']
    with migrated.read_connection() as c:
        assert c.execute('PRAGMA user_version').fetchone()[0]==6
        assert _schema_signature(c)==expected_visit_signature(6)
        assert not c.execute('PRAGMA foreign_key_check').fetchall()
    source.retain()
    assert source.connection.execute('SELECT count(*) FROM ni04_visit_delivery_outbox').fetchone()[0]==1
    assert migrated.service_consumer_cursor()==before


@pytest.mark.parametrize('fault',['schema','foreign-key','migration-crash'])
def test_v4_invalid_or_interrupted_migration_rolls_back_without_checkpoint_reset(delivery,visit_repository,visit_service,tmp_path,monkeypatch,fault):
    source,gen,w=delivery;put(source,gen,evaluated());w.run_services_once(now=NOW)
    path=tmp_path/'bad-v4.sqlite3';as_v4(visit_repository,path)
    with sqlite3.connect(path) as c:
        if fault=='schema':c.execute('CREATE TABLE unexpected(x)')
        elif fault=='foreign-key':c.execute("UPDATE visit_service_membership SET visit_id='missing',visit_guard='bad'")
        old=c.execute('SELECT * FROM visit_service_consumer_state').fetchone()
    target=VisitRepository(replace(w.config,db_path=str(path)))
    if fault=='migration-crash':
        def fail(c):raise RuntimeError('synthetic migration crash')
        monkeypatch.setattr(target,'_startup_check',fail)
    with pytest.raises((VisitSchemaError,RuntimeError)):target.initialize()
    with sqlite3.connect(path) as c:
        assert c.execute('PRAGMA user_version').fetchone()[0]==4
        assert c.execute('SELECT * FROM visit_service_consumer_state').fetchone()==old
        assert 'pending_since' not in [r[1] for r in c.execute('PRAGMA table_info(visit_service_membership)')]


@pytest.mark.parametrize('point,committed',[('visit_before_commit',False),('visit_after_commit',True)])
def test_linkage_counters_count_only_committed_transitions(delivery,visit_repository,point,committed):
    source,gen,w=delivery;put(source,gen,evaluated())
    def crash(stage):
        if stage==point:raise RuntimeError('synthetic crash')
    with pytest.raises(RuntimeError):w.run_services_once(now=NOW,crash_point=crash)
    assert w._service_linkage.counts['newly_staged_unique']==int(committed)
    assert w._service_linkage.counts['rejected_identity']==int(committed)
    w.run_services_once(now=NOW)
    assert w._service_linkage.counts['newly_staged_unique']==1
    w.run_services_once(now=NOW)
    assert w._service_linkage.counts['newly_staged_unique']==1


@pytest.mark.parametrize('seconds,bucket',[(30,'lag_le_30s'),(60,'lag_le_60s'),(300,'lag_le_300s'),(900,'lag_le_900s'),(1800,'lag_le_1800s'),(3599,'lag_lt_3600s')])
def test_real_committed_linkage_latency_disjoint_buckets(delivery,visit_repository,visit_service,seconds,bucket):
    source,gen,w=delivery;put(source,gen,evaluated());w.run_services_once(now=NOW)
    open_visit(visit_service,visit_repository);w.run_services_once(now=later(seconds));w.run_services_once(now=later(seconds))
    counts=w._service_linkage.counts
    assert counts['newly_staged_unique']==counts['later_attached_unique']==1
    assert counts['expired_detached_unique']==0
    assert {k:v for k,v in counts.items() if k.startswith('lag_') and v}=={bucket:1}


def test_low_frequency_aggregate_export_is_private_and_never_a_sqlite_write(delivery,visit_repository,monkeypatch):
    source,gen,w=delivery;clock=[0.0];exports=[]
    class Sink:
        def emit(self,event,**fields):exports.append((event,fields));return True
    w._service_linkage=VisitServiceLinkageTelemetry(Sink(),monotonic=lambda:clock[0])
    put(source,gen,evaluated());w.run_services_once(now=NOW)
    trace=[];original=visit_repository._connect
    def traced(**kw):
        c=original(**kw);c.set_trace_callback(trace.append);return c
    monkeypatch.setattr(visit_repository,'_connect',traced)
    clock[0]=60;w.run_services_once(now=NOW)
    assert len(exports)==1
    event,fields=exports[0];assert event=='visit.service_linkage_sample'
    assert fields['newly_staged_unique']==fields['still_unresolved']==fields['rejected_identity']==1
    assert fields['first_process_sample'] and fields['restart_gap_possible'] and fields['sample_interval_seconds']==60
    assert set(fields)==set(LINKAGE_COUNTER_FIELDS)|{'still_unresolved','unresolved_sample_valid','sample_interval_seconds','restart_gap_possible','first_process_sample','counters_saturated','population_capped'}
    assert all(type(v) in (int,bool) for v in fields.values())
    assert not any(s.startswith(('INSERT','UPDATE','DELETE','COMMIT')) for s in trace)
    clock[0]=119;w.run_services_once(now=NOW);assert len(exports)==1
    clock[0]=120;w.run_services_once(now=NOW)
    assert exports[-1][1]['newly_staged_unique']==0 and not exports[-1][1]['first_process_sample']


def test_live_capacity_and_expiry_use_bounded_indexed_work(delivery,visit_repository,monkeypatch):
    source,gen,w=delivery;put(source,gen,evaluated());w.run_services_once(now=NOW)
    import app.visit_lifecycle.repository as module
    monkeypatch.setattr(module,'SERVICE_DETACHED_CAPACITY',1)
    put(source,gen,evaluated(seed='second'))
    before=visit_repository.service_consumer_cursor()
    with pytest.raises(VisitSchemaError,match='capacity'):w.run_services_once(now=NOW)
    assert visit_repository.service_consumer_cursor()==before
    source.retain()
    assert source.connection.execute('SELECT count(*) FROM ni04_visit_delivery_outbox WHERE outbox_seq>0').fetchone()[0]==1
    with visit_repository.read_connection() as c:
        plan=c.execute("EXPLAIN QUERY PLAN SELECT * FROM visit_service_membership INDEXED BY idx_visit_service_detached_expiry WHERE visit_id IS NULL AND pending_since<=? ORDER BY pending_since,fact_key LIMIT 25",(NOW,)).fetchall()
        assert any('idx_visit_service_detached_expiry' in row[3] for row in plan)
        assert not any('TEMP B-TREE' in row[3] for row in plan)


def test_linkage_event_rejects_unknown_fields_identifiers_and_non_integer_counts():
    telemetry=VisitTelemetry(logging.getLogger('test296.linkage'))
    fields=dict.fromkeys(LINKAGE_COUNTER_FIELDS,0)
    fields.update(still_unresolved=0,unresolved_sample_valid=1,sample_interval_seconds=60,
        restart_gap_possible=True,first_process_sample=True,counters_saturated=False,population_capped=False)
    assert telemetry.emit('visit.service_linkage_sample',**fields)
    for invalid in ({'visit_id':'private'},{'raw_payload':'secret'},{'newly_staged_unique':True},
                    {'newly_staged_unique':-1},{'newly_staged_unique':1.1},{'newly_staged_unique':10**13}):
        assert telemetry.emit('visit.service_linkage_sample',**dict(fields,**invalid)) is False


def test_failed_export_and_population_sample_are_explicit_not_silent_zero():
    clock=[0.0];sent=[]
    class Sink:
        def emit(self,event,**fields):sent.append(fields);return len(sent)>1
    class Unavailable:
        def service_unresolved_sample(self,**kw):raise sqlite3.OperationalError('synthetic outage')
    observer=VisitServiceLinkageTelemetry(Sink(),monotonic=lambda:clock[0])
    observer.failed();clock[0]=60;observer.sample(Unavailable(),deadline=time.monotonic()+1)
    assert observer.counts['failed_passes']==observer.counts['export_failures']==1
    assert sent[0]['unresolved_sample_valid']==0 and sent[0]['sample_failures']==1
    clock[0]=120;observer.sample(Unavailable(),deadline=time.monotonic()+1)
    assert sent[-1]['sample_interval_seconds']==120 and sent[-1]['sample_failures']==2
    assert sent[-1]['export_failures']==1 and sent[-1]['failed_passes']==1
    assert observer.counts==dict.fromkeys(LINKAGE_COUNTER_FIELDS,0)


def test_expired_during_source_outage_cannot_attach_when_source_returns(delivery,visit_repository,visit_service):
    source,gen,w=delivery;put(source,gen,evaluated());w.run_services_once(now=NOW)
    path=w.service_history_path;w.service_history_path=path+'.absent'
    with pytest.raises(sqlite3.Error):w.run_services_once(now=later(3600))
    visit=open_visit(visit_service,visit_repository);w.service_history_path=path
    w.run_services_once(now=later(3601))
    with visit_repository.read_connection() as c:assert c.execute('SELECT count(*) FROM visit_service_membership').fetchone()[0]==0
    assert summaries(visit_repository,visit)==[]
    assert w._service_linkage.counts['expired_detached_unique']==1
    assert w._service_linkage.counts['later_attached_unique']==0


def test_later_reattachment_is_not_a_second_unique_linkage(delivery,visit_repository,visit_service):
    source,gen,w=delivery;put(source,gen,evaluated());w.run_services_once(now=NOW)
    open_visit(visit_service,visit_repository);w.run_services_once(now=later(30))
    with source.transaction():source.append_visit_delivery('binding',later(40),site_id=member(visit_repository)['site_id'],
        device_id=member(visit_repository)['device_id'],client_mac=member(visit_repository)['client_mac'],binding_seq=2)
    w.run_services_once(now=later(40))
    from app.network_service_recognition.materialization_repository import VISIT_DELIVERY_FIELDS
    raw=source.connection.execute("SELECT * FROM ni04_visit_delivery_outbox WHERE kind='positive' LIMIT 1").fetchone()
    fields={k:raw[k] for k in VISIT_DELIVERY_FIELDS if k not in ('outbox_seq','stream_id','kind','created_at','previous_hash')}
    fields['binding_seq']=2
    with source.transaction():source.append_visit_delivery('positive',later(50),**fields)
    w.run_services_once(now=later(50))
    assert member(visit_repository)['visit_id'] is not None
    assert w._service_linkage.counts['later_attached_unique']==1
    assert w._service_linkage.counts['newly_staged_unique']==1


def test_first_pending_clock_starts_on_actual_detachment_not_direct_attachment(delivery,visit_repository,visit_service):
    source,gen,w=delivery;open_visit(visit_service,visit_repository);put(source,gen,evaluated());w.run_services_once(now=NOW)
    assert member(visit_repository)['pending_since'] is None
    old=member(visit_repository)
    with source.transaction():source.append_visit_delivery('binding',later(7200),site_id=old['site_id'],
        device_id=old['device_id'],client_mac=old['client_mac'],binding_seq=2)
    w.run_services_once(now=later(7200))
    assert member(visit_repository)['pending_since']=='2026-10-12T17:25:00.000Z'
    assert member(visit_repository)['status']=='invalidated'
    assert w._service_linkage.counts['newly_staged_unique']==1
    w.run_services_once(now=later(10799));assert member(visit_repository)['status']=='invalidated'
    w.run_services_once(now=later(10800))
    with visit_repository.read_connection() as c:assert c.execute('SELECT count(*) FROM visit_service_membership').fetchone()[0]==0


def test_missing_durable_pending_clock_fails_closed_without_ack_or_credit(delivery,visit_repository,visit_service):
    source,gen,w=delivery;put(source,gen,evaluated());w.run_services_once(now=NOW)
    before=visit_repository.service_consumer_cursor()
    with visit_repository._connect() as c:c.execute('UPDATE visit_service_membership SET pending_since=NULL')
    visit=open_visit(visit_service,visit_repository)
    replay(source,later(60))
    with pytest.raises(VisitSchemaError,match='clock'):w.run_services_once(now=later(60))
    assert visit_repository.service_consumer_cursor()==before and summaries(visit_repository,visit)==[]
