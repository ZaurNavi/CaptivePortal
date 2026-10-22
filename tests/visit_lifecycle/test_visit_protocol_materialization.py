"""#296 Cut A: disposable Visit authority + bounded source, no live services."""
from datetime import datetime, timezone
from dataclasses import replace
import logging
import sqlite3
import time
import uuid

import pytest

from app.visit_lifecycle.models import protocol_visit_guard, VisitSchemaError
from app.visit_lifecycle.repository import VisitRepository, expected_visit_signature, _schema_signature
from app.visit_lifecycle.read_service import VisitLifecycleReadService
from app.visit_lifecycle.reconciliation import VisitLinkReconciler
from app.visit_lifecycle.telemetry import VisitTelemetry
from app.visit_lifecycle.recovery import backup_database, RecoveryError
from .conftest import make_request
from .test_repository import _close_visit

DEVICE='10000000-0000-4000-8000-000000000001'
SNAPSHOT='20000000-0000-4000-8000-000000000001'


class Source:
    def __init__(self):
        self.facts=[];self.calls=[];self.fail=False;self.after_read=lambda:None
    def read_visit_protocol_snapshot(self,site,device,mac,start,end,**kw):
        self.calls.append((site,device,mac,start,end,kw['evaluated_at']))
        if self.fail:raise OSError('private-source-canary')
        facts=[]
        for family in ('dns','tls','quic'):
            rows=[f for f in self.facts if f['source_event_family']==family and start<=f['event_at']<end]
            if rows:facts.append(sorted(rows,key=lambda f:(-datetime.fromisoformat(f['event_at'].replace('Z','+00:00')).timestamp(),f['edge_id']))[0])
        self.after_read()
        return dict(runtime_state='usable',binding_state='authoritative',bound_device_id=device,
            binding_confirmed_at='2026-08-13T09:00:00.000000Z',facts=tuple(facts))


def fact(at,family='dns',edge='a'):
    return dict(event_at='2026-08-13T'+at+'.000000Z',source_event_family=family,edge_id=edge*64)


def begin(service,repo,*,at=None,linked=True):
    request=make_request(authorized_at=at)
    outcome=service.submit_authorized(request)
    assert outcome.visit_id is not None
    if linked:repo.record_reconciliation_attempt(outcome.visit_id,device_id=DEVICE,initial_snapshot_id=SNAPSHOT,
        attempted_at='2026-08-13T10:00:00.000Z',retry_at='2026-08-13T10:01:00.000Z')
    return repo.get_visit('site-a',outcome.visit_id)


def worker(config,repo,source):
    return VisitLinkReconciler(config=config,repository=repo,registry_read_service=None,
        telemetry=VisitTelemetry(logging.getLogger('test.296')),protocol_reader=source)


def test_open_visit_materializes_before_close_and_idle_pass_does_not_write(visit_config,visit_repository,visit_service,monkeypatch):
    repo=visit_repository;visit=begin(visit_service,repo);source=Source();w=worker(visit_config,repo,source)
    assert w.run_protocol_once(now='2026-08-13T10:01:00.000Z')==1
    source.facts=[fact('10:00:01'),fact('10:00:02','tls','b'),fact('10:00:03','quic','c')]
    assert w.run_protocol_once(now='2026-08-13T10:02:00.000Z')==1
    dto=VisitLifecycleReadService(repo).visit_protocol_summary('site-a',DEVICE,visit.visit_id)
    assert dto['visit_status']=='open' and dto['closed_at'] is None and len(dto['protocols'])==3
    assert dto['summary_state']=='active' and dto['historical_completeness_claimed'] is False
    assert not any(key in str(dto) for key in ('client_mac','edge_id','snapshot_id','24h','recent_protocols'))
    statements=[];original=repo._connect
    def traced(**kwargs):
        c=original(**kwargs);c.set_trace_callback(statements.append);return c
    monkeypatch.setattr(repo,'_connect',traced)
    assert w.run_protocol_once(now='2026-08-13T10:03:00.000Z')==0
    assert not any(s.startswith(('INSERT','UPDATE','DELETE','COMMIT','BEGIN IMMEDIATE')) for s in statements)
    assert VisitLifecycleReadService(repo).visit_protocol_summary('site-a',DEVICE,visit.visit_id)==dto


def test_adjacent_visits_separate_boundary_and_sealed_history_survives_prune(visit_config,visit_repository,visit_service):
    repo=visit_repository;a=begin(visit_service,repo);_close_visit(repo,a.visit_id)
    b=begin(visit_service,repo,at=datetime(2026,8,13,10,5,tzinfo=timezone.utc))
    source=Source();source.facts=[fact('10:04:00','dns','a'),fact('10:05:00','tls','b'),fact('10:06:00','quic','c')]
    w=worker(visit_config,repo,source)
    assert w.run_protocol_once(now='2026-08-13T10:07:00.000Z')==2
    reads=VisitLifecycleReadService(repo)
    assert [r['protocol_id'] for r in reads.visit_protocol_summary('site-a',DEVICE,a.visit_id)['protocols']]==['dns']
    assert {r['protocol_id'] for r in reads.visit_protocol_summary('site-a',DEVICE,b.visit_id)['protocols']}=={'tls','quic'}
    w.run_protocol_once(now='2026-08-13T10:21:00.000Z')
    sealed=reads.visit_protocol_summary('site-a',DEVICE,a.visit_id)
    assert sealed['summary_state']=='finalized' and sealed['partial_reason']=='grace_elapsed_partial'
    source.facts=[fact('10:04:59','quic','d')]
    w.run_protocol_once(now='2026-09-13T10:21:00.000Z')
    assert reads.visit_protocol_summary('site-a',DEVICE,a.visit_id)==sealed
    assert reads.visit_protocol_summary('other-site',DEVICE,a.visit_id) is None
    assert reads.visit_protocol_summary('site-a',str(uuid.uuid4()),a.visit_id) is None


def test_identity_pending_and_source_failure_do_not_guess_or_erase_confirmed(visit_config,visit_repository,visit_service):
    repo=visit_repository;visit=begin(visit_service,repo,linked=False);source=Source();w=worker(visit_config,repo,source)
    w.run_protocol_once(now='2026-08-13T10:01:00.000Z')
    assert source.calls==[] and repo.saved_protocol_summary(visit)['summary_state']=='pending'
    repo.record_reconciliation_attempt(visit.visit_id,device_id=DEVICE,initial_snapshot_id=SNAPSHOT,
        attempted_at='2026-08-13T10:01:00.000Z',retry_at='2026-08-13T10:02:00.000Z')
    source.facts=[fact('10:00:01')];w.run_protocol_once(now='2026-08-13T10:02:00.000Z')
    source.fail=True;w.run_protocol_once(now='2026-08-13T10:03:00.000Z')
    dto=VisitLifecycleReadService(repo).visit_protocol_summary('site-a',DEVICE,visit.visit_id)
    assert dto['summary_state']=='partial' and dto['source_coverage']=='unavailable' and len(dto['protocols'])==1
    assert 'private-source-canary' not in str(dto)


def test_visit_close_race_rejects_stale_source_result(visit_config,visit_repository,visit_service):
    repo=visit_repository;visit=begin(visit_service,repo);source=Source();source.facts=[fact('10:00:01')]
    source.after_read=lambda:_close_visit(repo,visit.visit_id)
    assert worker(visit_config,repo,source).run_protocol_once(now='2026-08-13T10:06:00.000Z')==0
    assert repo.saved_protocol_summary(visit) is None


@pytest.mark.parametrize('version',[2,3,4])
def test_exact_migration_and_recovery_backup_each_supported_stage(visit_config,visit_repository,visit_service,tmp_path,version):
    repo=visit_repository;visit=begin(visit_service,repo)
    if version in (2,3):
        with repo._connect() as c:
            for table in ('visit_service_membership','visit_service_summary','visit_service_consumer_state'):
                c.execute('DROP TABLE '+table)
            if version==2:c.execute('DROP TABLE visit_network_protocol_summary')
            c.execute('PRAGMA user_version='+str(version))
    destination=tmp_path/('backup-'+str(version)+'.sqlite3')
    result=backup_database(db_path=str(repo.db_path),backup_to=str(destination))
    assert result['source_schema_version']==result['backup_schema_version']==version
    with sqlite3.connect(destination) as c:
        assert _schema_signature(c)==expected_visit_signature(version)
        assert c.execute('SELECT device_id FROM visits WHERE visit_id=?',(visit.visit_id,)).fetchone()[0]==DEVICE
    assert repo.initialize() is False
    with repo._connect(readonly=True) as c:
        assert c.execute('PRAGMA user_version').fetchone()[0]==4
    assert repo.get_visit('site-a',visit.visit_id).device_id==DEVICE


@pytest.mark.parametrize('fault',['unknown-version','tampered-schema','bad-FK'])
def test_migration_or_recovery_refuses_incompatible_or_corrupt_source(visit_repository,tmp_path,fault):
    repo=visit_repository
    with repo._connect() as c:
        if fault=='unknown-version':c.execute('PRAGMA user_version=99')
        elif fault=='tampered-schema':c.execute('CREATE TABLE unexpected(value)')
        else:
            c.execute('PRAGMA foreign_keys=OFF')
            c.execute("INSERT INTO visit_network_protocol_summary(visit_id,summary_version,site_id,client_mac,visit_guard,visit_started_at,summary_state,source_coverage,attribution_coverage,partial_reason,evaluated_at) VALUES('orphan',1,'site-a','02:11:22:33:44:55','g','2026-08-13T10:00:00.000Z','pending','unknown','unknown','identity_unconfirmed','2026-08-13T10:00:00.000Z')")
    with pytest.raises(RecoveryError):backup_database(db_path=str(repo.db_path),backup_to=str(tmp_path/'rejected.sqlite3'))
    assert not (tmp_path/'rejected.sqlite3').exists()
