"""Journal, per-run idempotency and serial fencing using synthetic worker receipts."""
from contextlib import contextmanager
from dataclasses import replace
import copy
import json
import os
import threading
import time
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
import uuid

import pytest
from app.admin_web.operations_inventory import Inventory, SERVICES, STORES
from app.unified_sqlite_audit.cli import parse_qualifications
from app.unified_sqlite_audit.model import AuditError, catalog, project, validate
from app.unified_sqlite_audit.readiness import ReadyProof
from app.unified_sqlite_audit.runner import AuditCycleRunner, QualifiedManifest, WorkerOutcome
from app.unified_sqlite_audit.snapshot import SourceSnapshotAndT3
from app.unified_sqlite_audit.status import OutcomeJournal, UnifiedSqliteAuditReadService
from test_snapshot import fixture


class MemoryJournal:
    def __init__(self):self.value=None;self.writes=[]
    @contextmanager
    def claim(self):yield
    def read(self):return copy.deepcopy(self.value)
    def write(self,value):
        self.value=project(value);self.writes.append(copy.deepcopy(self.value))


def setup(tmp_path,count=1,*,domain=None):
    jobs=[];writers=[]
    for n in range(count):
        writer,job=fixture(tmp_path,str(n)+'.db');writers.append(writer)
        jobs.append(replace(job,store_id=STORES[n].id,domain_validator_id=domain))
    inventory=Inventory(MappingProxyType({s.id:'run' for s in SERVICES}),
        MappingProxyType({s.id:'expected' for s in STORES}),
        MappingProxyType({s.id:next((j.path for j in jobs if j.store_id==s.id),'/unbound/'+s.filename) for s in STORES}))
    proof=ReadyProof(str(uuid.uuid4()),123,'start','boot',8080)
    return writers,jobs,inventory,proof


class FixtureWorker:
    def __init__(self,*,released=True,validators=None):
        self.calls=[];self.active=0;self.released=released;self.validators=validators
    def run(self,job,cancelled):
        assert self.active==0;self.active+=1;self.calls.append(job.store_id)
        result=SourceSnapshotAndT3(admission=lambda j:True,validators=self.validators).run(job)
        self.active-=1
        return WorkerOutcome(result,self.released,'complete' if self.released else 'release_unproven')


@pytest.mark.skipif(os.name!='posix',reason='POSIX owner metadata admission contract')
@pytest.mark.parametrize('domain,valid',[ (None,None),('accepted',True),('accepted',False)])
def test_serial_cycle_idempotent_and_independent_success_axes(tmp_path,domain,valid):
    writers,jobs,inventory,proof=setup(tmp_path,2,domain=domain)
    validators={(j.store_id,'accepted'):lambda c:valid for j in jobs} if domain else {}
    worker=FixtureWorker(validators=validators);journal=MemoryJournal()
    runner=AuditCycleRunner(journal,worker=worker,inventory_loader=lambda:inventory,
        ready_check=lambda p:p==proof,validators=validators)
    try:
        result=runner.run_once(proof.portal_run_id,QualifiedManifest(proof,tuple(jobs)))
        again=runner.run_once(proof.portal_run_id,QualifiedManifest(proof,tuple(jobs)))
        assert again['audit_cycle_id']==result['audit_cycle_id']
        assert worker.calls==[s.id for s in STORES[:2]]
        assert result['summary']['eligible_physical_count']==2
        assert result['summary']['eligible_domain_count']==(2 if domain else 0)
        assert result['cycle_state']==('PARTIAL' if valid is False else 'COMPLETE')
        for row in result['stores'][:2]:
            assert row['last_verified_physical_success'] is not None
            assert (row['last_verified_success'] is not None)==(valid is True)
            assert row['last_verified_success']==row['last_verified_domain_success']
        assert len(journal.writes)==6  # Start + two start/terminal pairs + final; no page writes.
    finally:
        for writer in writers:writer.close()


@pytest.mark.skipif(os.name!='posix',reason='POSIX owner metadata admission contract')
def test_unproven_release_holds_next_job_and_new_portal_epoch(tmp_path):
    writers,jobs,inventory,proof=setup(tmp_path,2)
    worker=FixtureWorker(released=False);journal=MemoryJournal()
    runner=AuditCycleRunner(journal,worker=worker,inventory_loader=lambda:inventory,ready_check=lambda p:True)
    try:
        result=runner.run_once(proof.portal_run_id,QualifiedManifest(proof,tuple(jobs)))
        assert result['cycle_state']=='ORPHAN_HOLD' and len(worker.calls)==1
        assert all(r['last_verified_physical_success'] is None for r in result['stores'])
        new=replace(proof,portal_run_id=str(uuid.uuid4()))
        assert runner.run_once(new.portal_run_id,QualifiedManifest(new,tuple(jobs)))['cycle_state']=='ORPHAN_HOLD'
        assert len(worker.calls)==1
    finally:
        for writer in writers:writer.close()


def test_no_readiness_no_worker_no_journal(tmp_path):
    journal=MemoryJournal();proof=ReadyProof(str(uuid.uuid4()),1,'start','boot',8080)
    with pytest.raises(AuditError,match='ready_unproven'):
        AuditCycleRunner(journal,ready_check=lambda p:False).run_once(proof.portal_run_id,QualifiedManifest(proof))
    assert journal.writes==[]


def test_previous_running_is_orphan_not_inherited_pass():
    journal=MemoryJournal();proof=ReadyProof(str(uuid.uuid4()),1,'start','boot',8080)
    value=catalog(True,portal_run_id=proof.portal_run_id,bound=True)
    value['cycle_state']='RUNNING';value['stores'][0]['deep'].update(state='RUNNING',physical_verdict='RUNNING')
    journal.write(value)
    result=AuditCycleRunner(journal,ready_check=lambda p:True).run_once(proof.portal_run_id,QualifiedManifest(proof))
    assert result['cycle_state']=='ORPHAN_HOLD'
    assert result['stores'][0]['deep']['physical_verdict']=='INCOMPLETE'


@pytest.mark.parametrize('error',[FileNotFoundError,ValueError,PermissionError])
def test_missing_manifest_runner_has_no_physical_job(error):
    journal=MemoryJournal();proof=ReadyProof(str(uuid.uuid4()),1,'start','boot',8080)
    def absent():raise error()
    worker=FixtureWorker()
    result=AuditCycleRunner(journal,worker=worker,inventory_loader=absent,ready_check=lambda p:True).run_once(
        proof.portal_run_id,QualifiedManifest(proof))
    assert result['cycle_state']=='BLOCKED_NO_TRUSTED_BINDINGS' and worker.calls==[]
    assert result['summary']['eligible_physical_count'] is None


@pytest.mark.skipif(os.name!='posix',reason='POSIX protected atomic journal and flock contract')
def test_protected_atomic_journal_and_partial_file_fail_closed(tmp_path):
    directory=tmp_path/'state';directory.mkdir(mode=0o700)
    journal=OutcomeJournal(directory);value=project(catalog(True))
    with journal.claim():journal.write(value)
    assert journal.read()['stores']==value['stores']
    assert sorted(p.name for p in directory.iterdir())==['cycle.lock','outcome.json']
    assert (journal.path.stat().st_mode & 0o777)==0o600
    journal.path.write_bytes(b'{"partial":')
    with pytest.raises(AuditError):journal.read()
    service=UnifiedSqliteAuditReadService(journal=journal)
    assert service.snapshot()['reason']=='journal_invalid'
    assert service.snapshot()['summary']['evaluated']==0


@pytest.mark.skipif(os.name!='posix',reason='POSIX protected journal negative symlink/permissions contract')
@pytest.mark.parametrize('bad',['symlink','writable','hardlink'])
def test_unsafe_journal_never_accepted(tmp_path,bad):
    directory=tmp_path/'state';directory.mkdir(mode=0o700)
    journal=OutcomeJournal(directory)
    if bad=='symlink':journal.path.symlink_to(tmp_path/'absent')
    else:
        journal.write(catalog())
        if bad=='writable':journal.path.chmod(0o666)
        else:os.link(journal.path,directory/'other')
    with pytest.raises((AuditError,OSError)):journal.read()


@pytest.mark.parametrize('mutator',[
    lambda v:v.update(reason='/private/path'),
    lambda v:v['stores'][0]['deep'].update(reason='SQLite private row'),
    lambda v:v['stores'][0].update(effective_path_identity='/path'),
    lambda v:v['stores'].pop(),lambda v:v.update(extra='forbidden'),
    lambda v:v['stores'][0]['fast'].update(scopes=['quick_check']),
    lambda v:v['stores'][0]['deep'].update(duration_ms=True),
    lambda v:v['stores'][0].update(eligible_physical=1),
])
def test_closed_public_dto_rejects_payload_unknowns_and_bool_integers(mutator):
    value=project(catalog());mutator(value)
    with pytest.raises(AuditError):validate(value)


def test_read_service_never_claims_current_previous_boot_pass():
    value=catalog(True,portal_run_id=str(uuid.uuid4()),bound=True)
    row=value['stores'][0];row.update(eligible_physical=True)
    row['deep'].update(physical_verdict='PASS')
    result=UnifiedSqliteAuditReadService(value,portal_run_id=str(uuid.uuid4())).snapshot()
    assert result['cycle_state']=='INTERRUPTED'
    assert result['stores'][0]['deep']['physical_verdict']=='STALE'
    assert not result['summary']['physical_coverage_complete']


def test_qualification_uses_only_existing_path_binding_not_supplied_path(tmp_path):
    writers,jobs,inventory,proof=setup(tmp_path)
    job=jobs[0]
    row=dict(store_id=job.store_id,source_id=job.source_id,uid=job.uid,gid=job.gid,
        max_snapshot_bytes=job.max_snapshot_bytes,host_memory_budget_bytes=job.host_memory_budget_bytes,
        no_competing_audit=True,cgroup='/audit.service')
    value=dict(version='audit.owner-qualification.v1',portal_run_id=proof.portal_run_id,stores=[row])
    try:
        assert parse_qualifications(json.dumps(value),inventory,proof.portal_run_id)[0].path==job.path
        row['path']='/guessed/source'
        with pytest.raises(AuditError):parse_qualifications(json.dumps(value),inventory,proof.portal_run_id)
        row.pop('path');row['uid']=True
        with pytest.raises(AuditError):parse_qualifications(json.dumps(value),inventory,proof.portal_run_id)
        row['uid']=job.uid;value['stores'].append(dict(row))
        with pytest.raises(AuditError):parse_qualifications(json.dumps(value),inventory,proof.portal_run_id)
    finally:
        for writer in writers:writer.close()


@pytest.mark.skipif(os.name!='posix',reason='POSIX flock concurrent same-run trigger and real journal contract')
def test_concurrent_trigger_reads_same_cycle_and_never_enqueues(tmp_path):
    writers,jobs,inventory,proof=setup(tmp_path)
    directory=tmp_path/'journal';directory.mkdir(mode=0o700)
    journal=OutcomeJournal(directory)
    entered=threading.Event();release=threading.Event();calls=[];results=[];errors=[]
    class BlockingWorker:
        def run(self,job,cancelled):
            calls.append(job.store_id);entered.set()
            assert release.wait(5)
            return WorkerOutcome(None,True,'cancelled')
    runner=AuditCycleRunner(journal,worker=BlockingWorker(),inventory_loader=lambda:inventory,ready_check=lambda p:True)
    qualified=QualifiedManifest(proof,tuple(jobs))
    def first():
        try:results.append(runner.run_once(proof.portal_run_id,qualified))
        except BaseException as error:errors.append(error)
    thread=threading.Thread(target=first);thread.start()
    try:
        assert entered.wait(5)
        second=runner.run_once(proof.portal_run_id,qualified)
        assert second['cycle_state']=='RUNNING'
        assert len(calls)==1
        release.set();thread.join(5)
        assert not thread.is_alive() and errors==[]
        assert second['audit_cycle_id']==results[0]['audit_cycle_id']
        assert results[0]['cycle_state']=='INTERRUPTED'
        assert results[0]['stores'][0]['last_verified_physical_success'] is None
    finally:
        release.set();thread.join(5)
        for writer in writers:writer.close()


@pytest.mark.skipif(os.name!='posix',reason='POSIX qualified source metadata and post-release identity contract')
def test_wal_advance_after_worker_result_keeps_snapshot_pass_and_live_stale(tmp_path):
    writers,jobs,inventory,proof=setup(tmp_path)
    class ChangingWorker(FixtureWorker):
        def run(self,job,cancelled):
            result=super().run(job,cancelled)
            writers[0].execute('INSERT INTO parent VALUES(99)');writers[0].commit()
            return result
    try:
        value=AuditCycleRunner(MemoryJournal(),worker=ChangingWorker(),inventory_loader=lambda:inventory,
            ready_check=lambda p:True).run_once(proof.portal_run_id,QualifiedManifest(proof,tuple(jobs)))
        assert value['stores'][0]['deep']['physical_verdict']=='PASS'
        assert value['stores'][0]['deep']['snapshot_receipt'] is not None
        assert value['stores'][0]['freshness']=='STALE'
        assert value['summary']['live_integrity_verified'] is False
        assert value['stores'][0]['last_verified_physical_success'] is None
    finally:
        for writer in writers:writer.close()


@pytest.mark.skipif(os.name!='posix',reason='Linux PID/start/boot journal crash provenance contract')
def test_replaced_executor_identity_is_orphan_not_running_or_pass(tmp_path):
    directory=tmp_path/'state';directory.mkdir(mode=0o700)
    journal=OutcomeJournal(directory);value=catalog(True,bound=True)
    value.update(cycle_state='RUNNING')
    value['stores'][0]['deep'].update(state='RUNNING',physical_verdict='RUNNING')
    journal.write(value)
    envelope=json.loads(journal.path.read_text())
    envelope['executor']['start']='0'  # PID reuse / prior process instance, not current executor.
    journal.path.write_text(json.dumps(envelope))
    result=journal.read()
    assert result['cycle_state']=='ORPHAN_HOLD'
    assert result['stores'][0]['deep']['physical_verdict']=='INCOMPLETE'
    assert result['stores'][0]['last_verified_physical_success'] is None


@pytest.mark.parametrize('mutator',[
    lambda v:v['stores'][0]['deep'].update(physical_verdict='PASS'),
    lambda v:v['stores'][0]['deep'].update(domain_verdict='PASS'),
    lambda v:v['summary'].update(registered_logical=True),
])
def test_provisional_or_forged_pass_without_positive_release_receipt_rejected(mutator):
    value=project(catalog(True,bound=True));mutator(value)
    with pytest.raises(AuditError):validate(value)


@pytest.mark.skipif(os.name!='posix',reason='Qualified CLI invocation uses POSIX metadata; OS admission explicitly mocked')
@pytest.mark.parametrize('qualified',[True,False])
def test_canonical_cli_passes_effective_port_and_current_qualification_to_real_disposable_job(tmp_path,monkeypatch,capsys,qualified):
    import importlib
    from app.unified_sqlite_audit import cli
    import sqlite3
    writers,jobs,inventory,proof=setup(tmp_path)
    journal=MemoryJournal();worker=FixtureWorker();seen=[];ready=[]
    settings_module=importlib.import_module('app.settings')
    monkeypatch.setattr(settings_module,'get_settings',lambda:{'sqlite_unified_audit_enabled':'true','port':18088})
    monkeypatch.setattr(cli,'OutcomeJournal',lambda directory:journal)
    monkeypatch.setattr(cli,'load_inventory',lambda:inventory)
    def probe(port,seconds,**kwargs):ready.append((port,seconds));return proof
    monkeypatch.setattr(cli,'wait_ready',probe)
    def load(path,loaded,run_id):
        seen.append((path,loaded,run_id));return tuple(jobs)
    monkeypatch.setattr(cli,'load_qualifications',load)
    def runner(journal,**kwargs):
        return AuditCycleRunner(journal,worker=worker,ready_check=lambda p:p==proof,**kwargs)
    monkeypatch.setattr(cli,'AuditCycleRunner',runner)
    if not qualified:
        monkeypatch.setattr(sqlite3,'connect',lambda *a,**k:pytest.fail('unqualified CLI opened source'))
    try:
        args=['run-once','--wait-ready-seconds=60']
        if qualified:args+=['--qualifications','/root-attested-explicit-policy']
        assert cli.main(args)==0
        value=json.loads(capsys.readouterr().out)
        assert ready==[(18088,60)]  # No hard-coded 8080 and no independent env flag.
        if qualified:
            assert seen==[('/root-attested-explicit-policy',inventory,proof.portal_run_id)]
            assert worker.calls==[jobs[0].store_id]
            assert value['stores'][0]['deep']['physical_verdict']=='PASS'
        else:
            assert seen==[] and worker.calls==[]
            assert value['summary']['eligible_physical_count']==0
    finally:
        for writer in writers:writer.close()


def test_candidate_unit_has_activation_readiness_and_explicit_qualification_wiring():
    import configparser
    root=Path(__file__).resolve().parents[2]
    unit=configparser.ConfigParser(interpolation=None)
    unit.read(root/'deploy/unified-sqlite-audit/captivportal-unified-sqlite-audit.service')
    assert unit['Install']['WantedBy']=='captive-portal.service'
    assert unit['Unit']['After']==unit['Unit']['PartOf']==unit['Unit']['Requisite']=='captive-portal.service'
    assert unit['Service']['Type']=='oneshot' and unit['Service']['RemainAfterExit']=='yes'
    assert unit['Service']['EnvironmentFile']=='/etc/default/captive-portal'
    invocation=unit['Service']['ExecStart']
    assert '--wait-ready-seconds=60' in invocation
    assert '--qualifications=${SQLITE_UNIFIED_AUDIT_QUALIFICATIONS}' in invocation
    assert unit['Service']['TimeoutStartSec']=='infinity'  # No deadline on audit/T3.


@pytest.mark.skipif(os.name!='posix',reason='Qualified source metadata and live-WAL snapshot receipt contract')
def test_verified_domain_snapshot_with_live_advance_does_not_promote_legacy_success(tmp_path):
    writers,jobs,inventory,proof=setup(tmp_path,domain='reviewed')
    def domain(image):
        for value in range(2,6):
            writers[0].execute('INSERT INTO parent VALUES(?)',(value,));writers[0].commit()
            assert image.execute('SELECT count(*) FROM parent').fetchone()==(1,)
        return True
    validators={(jobs[0].store_id,'reviewed'):domain}
    try:
        value=AuditCycleRunner(MemoryJournal(),worker=FixtureWorker(validators=validators),
            validators=validators,inventory_loader=lambda:inventory,ready_check=lambda p:True).run_once(
                proof.portal_run_id,QualifiedManifest(proof,tuple(jobs)))
        row=value['stores'][0]
        assert row['deep']['physical_verdict']==row['deep']['domain_verdict']=='PASS'
        assert row['deep']['snapshot_receipt']['snapshot_id']==row['deep']['snapshot_id']
        assert row['deep']['assurance_scope']=='SNAPSHOT_ONLY' and row['freshness']=='STALE'
        assert row['last_verified_success'] is row['last_verified_domain_success'] is row['last_verified_physical_success'] is None
        assert value['summary']['live_integrity_verified'] is False
    finally:
        for writer in writers:writer.close()
