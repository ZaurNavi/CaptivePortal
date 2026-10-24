"""Registry V1 audit-seeded memory count: durability, identity and sampling races."""
from contextlib import closing
from copy import deepcopy
from dataclasses import replace
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
from unittest.mock import Mock

import pytest

from app import operations_verification as proof
from app.visitor_registry.registry_models import ApplyOutcome, RegistrySchemaError, SourceLineRecord, ScanResult
from app.visitor_registry.registry_read_service import VisitorRegistryReadService
from app.visitor_registry.registry_repository import VisitorRegistryRepository
from app.visitor_registry.registry_worker import VisitorRegistryWorker, DisabledVisitorRegistry, UnavailableVisitorRegistry
from tests.visitor_registry.test_device_registry import make_stack, event_for, fixture_event


def line(config, service, index=0):
    return SourceLineRecord('synthetic', config.source_log_path, index*100, (index+1)*100,
                            (index+1)*100, 'synthetic-checkpoint', service.now_iso())


def store(stack, index=0, *, device=0):
    config, service, repo, _, _ = stack
    decision=service.decide(event_for(session_id=f'synthetic-{index}',mac=f'02:11:22:33:44:{device:02x}'))
    result=repo.apply_source_line(line(config,service,index),decision)
    assert result.outcome is ApplyOutcome.STORED
    return result


@pytest.mark.parametrize('count',[0,1,8])
def test_count_requires_full_existing_audit_and_counts_unique_persisted_devices(tmp_path,count):
    stack=make_stack(tmp_path);repo=stack[2]
    for i in range(count):store(stack,i,device=i)
    assert repo.registered_devices_snapshot() is None
    facade=VisitorRegistryReadService(repo,stack[1],configured_enabled=True)
    status=facade.get_status();stats=facade.get_stats()
    assert repo.run_full_audit() is None  # Existing public audit return unchanged.
    assert repo.registered_devices_snapshot()==count
    assert facade.get_status()==status and facade.get_stats()==stats
    assert 'registered_device_count' not in status and 'registered_devices' not in status
    assert stats['total_devices']==count
    with closing(sqlite3.connect(stack[0].db_path)) as c:
        assert c.execute('PRAGMA user_version').fetchone()[0]==1
        assert 'registered_device_count' not in {r[1] for r in c.execute('PRAGMA table_info(registry_state)')}
        assert not list(c.execute("SELECT name FROM sqlite_master WHERE type='trigger'"))


def test_postcommit_create_only_update_duplicate_skip_advance_conflict_and_replay(tmp_path):
    stack=make_stack(tmp_path);config,service,repo,*_=stack
    repo.run_full_audit();assert repo.registered_devices_snapshot()==0
    assert store(stack,0).device_created is True
    assert repo.registered_devices_snapshot()==1
    assert store(stack,1).device_created is False
    assert repo.registered_devices_snapshot()==1
    event=event_for(session_id='synthetic-1',mac='02:11:22:33:44:00')
    decision=service.decide(event)
    assert repo.apply_source_line(line(config,service,2),decision).outcome is ApplyOutcome.DUPLICATE
    conflict=deepcopy(event);conflict['client']['hostname']='changed'
    assert repo.apply_source_line(line(config,service,3),service.decide(conflict)).outcome is ApplyOutcome.CONFLICT
    skipped=event_for(session_id='skip',mac='02:11:22:33:44:01');skipped['schema_version']=99
    assert repo.apply_source_line(line(config,service,4),service.decide(skipped)).outcome is ApplyOutcome.SKIPPED
    assert repo.apply_source_line(line(config,service,5),service.decide({'event':'unrelated'})).outcome is ApplyOutcome.ADVANCED
    assert repo.registered_devices_snapshot()==1
    assert store(stack,6,device=1).device_created is True
    assert repo.registered_devices_snapshot()==2
    assert repo.get_reader_states()['synthetic'].source_offset==700


class ConnectionProxy:
    def __init__(self,connection,commit):self.connection,self._commit=connection,commit
    def __getattr__(self,key):return getattr(self.connection,key)
    def commit(self):return self._commit(self.connection)


@pytest.mark.parametrize('durable',[False,True])
def test_failed_or_ambiguous_commit_invalidates_and_next_native_audit_recovers(tmp_path,monkeypatch,durable):
    stack=make_stack(tmp_path);config,service,repo,*_=stack
    repo.run_full_audit();original=repo._connect
    def commit(c):
        assert repo._inventory_count==0
        if durable:c.commit()
        raise sqlite3.OperationalError('synthetic lost commit response')
    monkeypatch.setattr(repo,'_connect',lambda **kw:ConnectionProxy(original(**kw),commit))
    with pytest.raises(sqlite3.OperationalError):store(stack)
    assert repo.registered_devices_snapshot() is None
    with closing(sqlite3.connect(config.db_path)) as c:
        assert c.execute('SELECT COUNT(*) FROM visitor_devices').fetchone()[0]==int(durable)
        assert c.execute('SELECT COUNT(*) FROM device_snapshots').fetchone()[0]==int(durable)
    restarted=VisitorRegistryRepository(config);restarted.initialize(service.now_iso())
    assert restarted.registered_devices_snapshot() is None
    restarted.run_full_audit();assert restarted.registered_devices_snapshot()==int(durable)
    states=restarted.get_reader_states()
    assert (states['synthetic'].source_offset if durable else len(states))==(100 if durable else 0)


def test_insert_failure_rolls_back_device_snapshot_processed_event_and_offset(tmp_path,monkeypatch):
    stack=make_stack(tmp_path);repo=stack[2];repo.run_full_audit()
    monkeypatch.setattr(repo,'_insert_processed',Mock(side_effect=sqlite3.OperationalError('synthetic failure')))
    with pytest.raises(sqlite3.OperationalError):store(stack)
    assert repo.registered_devices_snapshot() is None
    with closing(sqlite3.connect(stack[0].db_path)) as c:
        for table in ('visitor_devices','device_snapshots','processed_snapshot_events','reader_state'):
            assert c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]==0


def test_sampler_cannot_observe_postcommit_preincrement_gap(tmp_path,monkeypatch):
    stack=make_stack(tmp_path);repo=stack[2];repo.run_full_audit()
    committed=threading.Event();release=threading.Event();started=threading.Event();done=threading.Event()
    results=[];errors=[];original=repo._connect
    def commit(c):
        assert repo._inventory_count==0
        c.commit();committed.set()
        assert release.wait(3)
    monkeypatch.setattr(repo,'_connect',lambda **kw:ConnectionProxy(original(**kw),commit))
    def writer():
        try:store(stack)
        except BaseException as e:errors.append(e)
    def sampler():
        started.set();results.append(repo.registered_devices_snapshot());done.set()
    writing=threading.Thread(target=writer,daemon=True);sampling=threading.Thread(target=sampler,daemon=True)
    writing.start()
    try:
        assert committed.wait(3)
        with closing(sqlite3.connect(stack[0].db_path)) as c:assert c.execute('SELECT COUNT(*) FROM visitor_devices').fetchone()[0]==1
        sampling.start();assert started.wait(1)
        assert not done.wait(0.05)
    finally:
        release.set();writing.join(3)
        if sampling.ident is not None:sampling.join(3)
    assert not errors and not writing.is_alive() and not sampling.is_alive()
    assert results==[1]


@pytest.mark.parametrize('write_during_audit',[False,True])
def test_slow_audit_does_not_hold_sampling_lock_or_publish_inconsistent_seed(tmp_path,monkeypatch,write_during_audit):
    stack=make_stack(tmp_path);repo=stack[2]
    entered=threading.Event();release=threading.Event();errors=[]
    original=repo._validate_snapshot_counts
    def audit(c):
        count=original(c);entered.set();assert release.wait(3);return count
    monkeypatch.setattr(repo,'_validate_snapshot_counts',audit)
    def run():
        try:repo.run_full_audit()
        except BaseException as e:errors.append(e)
    thread=threading.Thread(target=run,daemon=True);thread.start()
    try:
        assert entered.wait(3)
        for _ in range(20):assert repo.registered_devices_snapshot() is None
        if write_during_audit:store(stack)
    finally:release.set();thread.join(3)
    assert not errors and not thread.is_alive()
    assert repo.registered_devices_snapshot()==(None if write_during_audit else 0)


@pytest.mark.parametrize('fault',['count','foreign-key','schema','integrity'])
def test_failed_audit_never_publishes_number_or_scans_reader(tmp_path,monkeypatch,fault):
    stack=make_stack(tmp_path);config,service,repo,reader,_=stack
    store(stack);repo.run_full_audit();assert repo.registered_devices_snapshot()==1
    with closing(sqlite3.connect(config.db_path)) as c,c:
        if fault=='count':c.execute('UPDATE visitor_devices SET snapshot_count=2')
        elif fault=='foreign-key':c.execute("UPDATE device_snapshots SET device_id='orphan'")
        elif fault=='schema':c.execute('DROP INDEX idx_visitor_devices_last_seen')
    if fault=='integrity':
        original=repo._connect
        class BadIntegrity(ConnectionProxy):
            def execute(self,sql,*args):
                if sql=='PRAGMA integrity_check':return type('Result',(),{'fetchone':lambda self:('synthetic corruption',)})()
                return self.connection.execute(sql,*args)
        monkeypatch.setattr(repo,'_connect',lambda **kw:BadIntegrity(original(**kw),lambda c:c.commit()))
    worker=VisitorRegistryWorker(repository=repo,service=service,reader=reader,telemetry=reader.telemetry)
    scan=Mock(side_effect=AssertionError('no scan after failed audit'));monkeypatch.setattr(reader,'scan',scan)
    worker.run_once()
    assert repo.registered_devices_snapshot() is None and worker.get_registered_devices_snapshot() is None
    assert not worker.available and not worker._full_audit_completed
    assert not scan.called and repo.get_status(True).registry_state=='unavailable'


@pytest.mark.parametrize('bad',[True,False,-1,2**53,1.0,'1'])
def test_invalid_or_overflow_cache_is_unknown_never_plausible_number(tmp_path,bad):
    stack=make_stack(tmp_path);repo=stack[2];repo.run_full_audit()
    repo._inventory_count=bad
    assert repo.registered_devices_snapshot() is None
    assert repo._inventory_count is None


def test_safe_integer_overflow_does_not_change_committed_ingest(tmp_path):
    stack=make_stack(tmp_path);repo=stack[2];repo.run_full_audit()
    repo._inventory_count=2**53-1
    assert store(stack).device_created is True
    assert repo.registered_devices_snapshot() is None
    with closing(sqlite3.connect(stack[0].db_path)) as c:assert c.execute('SELECT COUNT(*) FROM visitor_devices').fetchone()[0]==1


@pytest.mark.parametrize('fault',['path','config-disabled','pid','startup-proof','partial-scope'])
def test_memory_provider_rejects_owner_or_known_source_discontinuity_without_io(tmp_path,monkeypatch,fault):
    stack=make_stack(tmp_path);repo=stack[2];repo.run_full_audit()
    if fault=='path':repo.db_path=Path(str(repo.db_path)+'.different')
    elif fault=='config-disabled':repo.config=replace(repo.config,enabled=False)
    elif fault=='pid':repo._inventory_pid-=1
    elif fault=='startup-proof':
        with proof._lock:proof._rows['visitor_registry']['observed_store_id']='0'*64
    else:
        with proof._lock:proof._rows['visitor_registry']['scope']=['quick_check']
    monkeypatch.setattr(repo,'_connect',Mock(side_effect=AssertionError('snapshot SQL forbidden')))
    monkeypatch.setattr(os,'lstat',Mock(side_effect=AssertionError('snapshot stat forbidden')))
    assert repo.registered_devices_snapshot() is None


@pytest.mark.parametrize('fault',['runtime-recheck','version','missing-state','unavailable-state','absent-file'])
def test_existing_native_validation_observations_invalidate_without_new_reads(tmp_path,fault):
    stack=make_stack(tmp_path);config,_,repo,*_=stack;repo.run_full_audit()
    assert repo.registered_devices_snapshot()==0
    if fault=='runtime-recheck':repo.validate_runtime_health()
    elif fault=='absent-file':
        Path(config.db_path).rename(Path(config.db_path).with_suffix('.saved'))
        assert not repo.get_status(True).database_exists
    else:
        with closing(sqlite3.connect(config.db_path)) as c,c:
            if fault=='version':c.execute('PRAGMA user_version=2')
            elif fault=='missing-state':c.execute('DELETE FROM registry_state')
            else:c.execute("UPDATE registry_state SET state='unavailable'")
        if fault=='missing-state':
            with pytest.raises(RegistrySchemaError):repo.get_status(True)
        else:repo.get_status(True)
    assert repo.registered_devices_snapshot() is None


def test_native_open_observes_replacement_and_invalidates_without_extra_probe(tmp_path):
    stack=make_stack(tmp_path);config,service,repo,*_=stack
    store(stack);repo.run_full_audit();path=Path(config.db_path)
    saved=path.with_suffix('.saved');path.rename(saved)
    import shutil
    shutil.copyfile(saved,path)
    # No on-demand probing in the getter: replacement is observed by the next
    # normal owner open. Stage3B must apply its existing sampler fingerprint.
    with closing(repo._connect(readonly=True)):pass
    assert repo.registered_devices_snapshot() is None
    repo.run_full_audit();assert repo.registered_devices_snapshot() is None  # Old startup identity cannot bless replacement.
    new=VisitorRegistryRepository(config);new.initialize(service.now_iso());new.run_full_audit()
    assert new.registered_devices_snapshot()==1


def test_worker_exposes_only_running_audited_owner_and_no_sampling_io(tmp_path,monkeypatch):
    stack=make_stack(tmp_path);config,service,repo,reader,_=stack
    entered=threading.Event();release=threading.Event()
    def scan(**kwargs):entered.set();assert release.wait(3);return ScanResult(True)
    monkeypatch.setattr(reader,'scan',scan)
    worker=VisitorRegistryWorker(repository=repo,service=service,reader=reader,telemetry=reader.telemetry)
    assert worker.get_registered_devices_snapshot() is None
    try:
        assert worker.start() and entered.wait(3)
        with monkeypatch.context() as m:
            m.setattr(repo,'_connect',Mock(side_effect=AssertionError('sampler SQL forbidden')))
            m.setattr(os,'lstat',Mock(side_effect=AssertionError('sampler stat forbidden')))
            for _ in range(20):assert worker.get_registered_devices_snapshot()==0
            worker.available=False;assert worker.get_registered_devices_snapshot() is None
            worker.available=True;worker._owner_pid-=1;assert worker.get_registered_devices_snapshot() is None
            worker._owner_pid+=1
    finally:release.set();worker.stop(timeout=2,final_scan=False)
    assert worker.get_registered_devices_snapshot() is None and repo.registered_devices_snapshot() is None
    assert DisabledVisitorRegistry().get_registered_devices_snapshot() is None
    assert UnavailableVisitorRegistry().get_registered_devices_snapshot() is None


@pytest.mark.parametrize('durable',[False,True])
def test_real_process_crash_before_after_commit_recovers_only_on_new_full_audit(tmp_path,durable):
    stack=make_stack(tmp_path);config,service,repo,*_=stack
    program='''
import os,sys
from pathlib import Path
from tests.visitor_registry.test_device_registry import make_stack,fixture_event
from tests.visitor_registry.test_registered_devices_cache import ConnectionProxy,line
config,service,repo,reader,_=make_stack(Path(sys.argv[1]));repo.run_full_audit()
original=repo._connect
def commit(c):
    if sys.argv[2]=='True':c.commit()
    os._exit(92 if sys.argv[2]=='True' else 91)
repo._connect=lambda **kw:ConnectionProxy(original(**kw),commit)
repo.apply_source_line(line(config,service),service.decide(fixture_event()))
'''
    result=subprocess.run([sys.executable,'-B','-c',program,str(tmp_path),str(durable)],
        capture_output=True,text=True,timeout=10)
    assert result.returncode==(92 if durable else 91),result.stdout+result.stderr
    new=VisitorRegistryRepository(config);new.initialize(service.now_iso())
    assert new.registered_devices_snapshot() is None
    new.run_full_audit();assert new.registered_devices_snapshot()==int(durable)


@pytest.mark.parametrize('state',['disabled','unavailable','stopping','initializing'])
def test_native_invalidating_state_discards_count_until_next_mandatory_audit(tmp_path,state):
    stack=make_stack(tmp_path);repo=stack[2];repo.run_full_audit()
    assert repo.registered_devices_snapshot()==0
    repo.set_state(state,'synthetic',stack[1].now_iso())
    assert repo.registered_devices_snapshot() is None


def test_no_inventory_sql_or_repeated_audits_and_exact_postcommit_transition(tmp_path,monkeypatch):
    stack=make_stack(tmp_path);repo=stack[2]
    statements=[];original=repo._connect
    def traced(**kw):
        c=original(**kw);c.set_trace_callback(statements.append);return c
    monkeypatch.setattr(repo,'_connect',traced)
    repo.run_full_audit()
    aggregate=[q for q in statements if 'GROUP BY d.device_id' in q]
    assert len(aggregate)==1 and 'COALESCE(MAX(mismatch), 0)' in aggregate[0]
    assert not any(q.lstrip().upper().startswith(('UPDATE','INSERT','DELETE','BEGIN','COMMIT')) for q in statements)
    statements.clear();stored=store(stack)
    assert statements.count('BEGIN IMMEDIATE')==statements.count('COMMIT')==1
    counts=[' '.join(q.split()) for q in statements if 'COUNT(' in q.upper()]
    # Preserve the pre-existing per-device history aggregate, not a new
    # inventory/table count. It is part of the unchanged business write path.
    assert counts==[f"SELECT MIN(authorized_at), MAX(authorized_at), COUNT(*) FROM device_snapshots WHERE device_id = '{stored.device_id}'"]
    assert sum('UPDATE registry_state' in q for q in statements)==1
    statements.clear()
    for _ in range(100):assert repo.registered_devices_snapshot()==1
    assert statements==[]


@pytest.mark.skipif(os.name!='posix',reason='Linux/POSIX forked-owner lock contract')
def test_forked_process_cannot_reuse_parent_count_or_wait_on_inherited_lock(tmp_path):
    import select
    import signal
    stack=make_stack(tmp_path);repo=stack[2];repo.run_full_audit()
    read,write=os.pipe()
    with repo._inventory_lock:
        pid=os.fork()
        if pid==0:
            try:
                os.close(read)
                os.write(write,json.dumps(repo.registered_devices_snapshot()).encode())
            finally:os._exit(0)
        os.close(write)
        ready=False
        try:
            ready=bool(select.select([read],[],[],3)[0])
            assert ready,'child must reject PID before touching inherited lock'
            assert os.read(read,128)==b'null'
        finally:
            os.close(read)
            if not ready:os.kill(pid,signal.SIGKILL)
            _,status=os.waitpid(pid,0)
        assert status==0
    assert repo.registered_devices_snapshot()==0
