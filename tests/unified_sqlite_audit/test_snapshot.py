"""Disposable WAL fixtures, explicitly MOCKED owner/OS admission for algorithms.

These portable tests do not claim native RO/cgroup/no-swap qualification.
"""
from dataclasses import replace
import hashlib
import os
import sqlite3
import threading

import pytest
from app.operations_verification import opaque_identity
from app.unified_sqlite_audit.model import AdmittedStore, AuditError
from app.unified_sqlite_audit.snapshot import SourceSnapshotAndT3, native_admission


def fixture(tmp_path,name='fixture.db',*,foreign_violation=False):
    path=tmp_path/name
    writer=sqlite3.connect(path)
    writer.execute('PRAGMA journal_mode=WAL')
    writer.executescript('CREATE TABLE parent(id INTEGER PRIMARY KEY);'
        'CREATE TABLE child(id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES parent(id));'
        'INSERT INTO parent VALUES(1);')
    writer.execute('INSERT INTO child VALUES(1,?)',(2 if foreign_violation else 1,))
    writer.commit()
    job=AdmittedStore('portal_counter',str(path),opaque_identity(path.stat()),
        getattr(os,'geteuid',lambda:0)(),getattr(os,'getegid',lambda:0)(),16*1024*1024,
        256*1024*1024,True)
    return writer,job


@pytest.mark.parametrize('name',['first.db','second.db'])
def test_full_wal_backup_to_fresh_memory_physical_without_domain(tmp_path,name):
    writer,job=fixture(tmp_path,name)
    before=hashlib.sha256(open(job.path,'rb').read()).hexdigest()
    try:
        result=SourceSnapshotAndT3(admission=lambda j:True).run(job)
        assert result['physical_verdict']=='PASS' and result['domain_verdict']=='NOT_ADMITTED'
        assert result['integrity']==result['fk']=='PASS'
        assert result['verified_at'] is None  # Only parent positive release publishes verification.
        assert hashlib.sha256(open(job.path,'rb').read()).hexdigest()==before
        assert writer.execute('SELECT count(*) FROM child').fetchone()==(1,)
        assert writer.execute('PRAGMA integrity_check').fetchall()==[('ok',)]
    finally:writer.close()


@pytest.mark.parametrize('valid',[True,False])
def test_domain_validator_same_ram_and_independent_physical_axis(tmp_path,valid):
    writer,job=fixture(tmp_path)
    held=[]
    def validator(connection):
        held.append(connection)
        databases=connection.execute('PRAGMA database_list').fetchall()
        assert databases[0]==(0,'main','')
        assert all(row[1] in {'main','temp'} and row[2]=='' for row in databases)
        assert connection.execute('SELECT * FROM parent').fetchall()==[(1,)]
        with pytest.raises(sqlite3.DatabaseError):connection.execute('INSERT INTO parent VALUES(99)')
        return valid
    try:
        result=SourceSnapshotAndT3(admission=lambda j:True,
            validators={('portal_counter','reviewed-test-v1'):validator}).run(replace(job,domain_validator_id='reviewed-test-v1'))
        assert result['physical_verdict']=='PASS'
        assert result['domain_verdict']==('PASS' if valid else 'FAIL')
        with pytest.raises(sqlite3.ProgrammingError):held[0].execute('SELECT 1')
    finally:writer.close()


def test_fk_violation_is_not_physical_pass_or_domain_pass(tmp_path):
    writer,job=fixture(tmp_path,foreign_violation=True)
    try:
        result=SourceSnapshotAndT3(admission=lambda j:True).run(job)
        assert result['integrity']=='PASS' and result['fk']=='FAIL'
        assert result['physical_verdict']=='FK_FAIL' and result['domain_verdict']=='NOT_ADMITTED'
    finally:writer.close()


def test_corrupt_source_is_closed_failure_not_private_sql_text(tmp_path):
    path=tmp_path/'bad.db';path.write_bytes(b'private fixture not a database')
    job=AdmittedStore('portal_counter',str(path),opaque_identity(path.stat()),0,0,1000000,10000000,True)
    with pytest.raises(AuditError,match='^source_unavailable$'):
        SourceSnapshotAndT3(admission=lambda j:True).run(job)


def test_missing_source_is_never_created(tmp_path):
    path=tmp_path/'missing.db'
    job=AdmittedStore('portal_counter',str(path),'0'*64,0,0,1000000,10000000,True)
    with pytest.raises(AuditError):SourceSnapshotAndT3(admission=lambda j:True).run(job)
    assert not path.exists()


@pytest.mark.parametrize('reason',['resource_unqualified','cancelled'])
def test_rejection_before_open_has_zero_connections(tmp_path,monkeypatch,reason):
    job=AdmittedStore('portal_counter',str(tmp_path/'unopened'),'0'*64,0,0,1,1,True)
    def denied(job):raise AuditError(reason)
    def forbidden(*a,**k):pytest.fail('unqualified source opened')
    monkeypatch.setattr(sqlite3,'connect',forbidden)
    with pytest.raises(AuditError,match=reason):SourceSnapshotAndT3(admission=denied).run(job)


def test_native_unqualified_lab_shell_fails_closed_without_sqlite(tmp_path,monkeypatch):
    job=AdmittedStore('portal_counter',str(tmp_path/'unopened'),'0'*64,0,0,1,1,True)
    monkeypatch.setattr(sqlite3,'connect',lambda *a,**k:pytest.fail('unqualified source opened'))
    with pytest.raises(AuditError):native_admission(job)


def test_memory_ceiling_and_cancel_close_all_handles(tmp_path,monkeypatch):
    writer,job=fixture(tmp_path)
    original=sqlite3.connect;opened=[]
    def connect(*args,**kwargs):
        connection=original(*args,**kwargs);opened.append(connection);return connection
    monkeypatch.setattr(sqlite3,'connect',connect)
    try:
        with pytest.raises(AuditError,match='resource_unqualified'):
            SourceSnapshotAndT3(admission=lambda j:True).run(replace(job,max_snapshot_bytes=1))
        for connection in opened:
            with pytest.raises(sqlite3.ProgrammingError):connection.execute('SELECT 1')
        with pytest.raises(AuditError,match='cancelled'):
            SourceSnapshotAndT3(admission=lambda j:True,cancelled=lambda:True).run(job)
    finally:writer.close()


def test_monotonic_jump_is_duration_only_not_acceptance_deadline(tmp_path):
    writer,job=fixture(tmp_path);times=iter([1,10**8])
    try:
        result=SourceSnapshotAndT3(admission=lambda j:True,clock=lambda:next(times)).run(job)
        assert result['physical_verdict']=='PASS' and result['duration_ms']==99999999000
    finally:writer.close()


def test_live_wal_writes_preserve_frozen_snapshot_pass_not_current_live_assurance(tmp_path):
    writer,job=fixture(tmp_path)
    def mutate_source(image):
        for value in range(2,12):
            writer.execute('INSERT INTO parent VALUES(?)',(value,));writer.commit()
            assert image.execute('SELECT count(*) FROM parent').fetchone()==(1,)
        return True
    try:
        result=SourceSnapshotAndT3(admission=lambda j:True,validators={('portal_counter','fixture'):mutate_source}).run(
            replace(job,domain_validator_id='fixture'))
        assert result['physical_verdict']==result['domain_verdict']=='PASS'
        assert result['assurance_scope']=='SNAPSHOT_ONLY' and result['live_freshness']=='ADVANCED'
        assert result['source_generation'] is None
        assert result['source_observation_before']!=result['source_observation_after']
        assert writer.execute('SELECT count(*) FROM parent').fetchone()==(11,)
    finally:writer.close()


def test_replaced_main_inode_is_rejected_unlike_ordinary_wal_advance(tmp_path):
    writer,job=fixture(tmp_path)
    def replace_main(_):
        writer.close()
        new=tmp_path/'replacement.db'
        connection=sqlite3.connect(new)
        connection.execute('CREATE TABLE unrelated(id INTEGER)');connection.commit();connection.close()
        new.replace(job.path)
        return True
    with pytest.raises(AuditError,match='source_changed'):
        SourceSnapshotAndT3(admission=lambda j:True,validators={('portal_counter','fixture'):replace_main}).run(
            replace(job,domain_validator_id='fixture'))


def test_concurrent_wal_writer_during_full_integrity_check_keeps_ram_snapshot(tmp_path,monkeypatch):
    writer,job=fixture(tmp_path)
    writer.executemany('INSERT INTO parent VALUES(?)',[(n,) for n in range(2,10002)])
    writer.commit()
    started=threading.Event();written=threading.Event();errors=[];callbacks=[];images=[]
    original=sqlite3.connect
    class ObservedRAM(sqlite3.Connection):
        def set_progress_handler(self,callback,instructions):
            def physical_progress():
                callbacks.append(1)
                if not started.is_set():
                    started.set()
                    assert written.wait(5), 'writer did not overlap full SQLite check'
                return callback()
            super().set_progress_handler(physical_progress,instructions)
    def connect(database,**kwargs):
        if database==':memory:':
            connection=original(database,factory=ObservedRAM,**kwargs);images.append(connection);return connection
        return original(database,**kwargs)
    def advance():
        connection=None
        try:
            assert started.wait(5)
            connection=original(job.path,timeout=1)
            for n in range(20000,20020):
                connection.execute('INSERT INTO parent VALUES(?)',(n,));connection.commit()
        except BaseException as error:errors.append(error)
        finally:
            if connection is not None:connection.close()
            written.set()
    monkeypatch.setattr(sqlite3,'connect',connect)
    thread=threading.Thread(target=advance);thread.start()
    try:
        def domain(image):
            assert image is images[0]
            assert image.execute('SELECT count(*) FROM parent').fetchone()==(10001,)
            return True
        result=SourceSnapshotAndT3(admission=lambda j:True,validators={('portal_counter','fixture'):domain}).run(
            replace(job,domain_validator_id='fixture'))
        thread.join(5)
        assert not thread.is_alive() and errors==[] and callbacks
        assert result['physical_verdict']==result['domain_verdict']=='PASS'
        assert result['live_freshness']=='ADVANCED' and result['source_generation'] is None
        assert writer.execute('SELECT count(*) FROM parent').fetchone()==(10021,)
    finally:
        started.set();thread.join(5);writer.close()


@pytest.mark.parametrize('integrity,foreign_keys,verdict',[
    ([('ok',),('private second integrity row',)],[], 'INTEGRITY_FAIL'),
    ([('ok',)],[(i,'private-table',1,2) for i in range(4)],'FK_FAIL'),
    ([],[],'INTEGRITY_FAIL')])
def test_full_enumeration_not_just_first_integrity_or_fk_row(tmp_path,monkeypatch,integrity,foreign_keys,verdict):
    writer,job=fixture(tmp_path)
    seen=[];closed=[]
    class Cursor:
        def __init__(self,rows,label):self.rows=rows;self.label=label
        def fetchone(self):return self.rows[0]
        def __iter__(self):
            for row in self.rows:seen.append(self.label);yield row
        def close(self):closed.append(self.label)
    class Connection:
        def __init__(self,source):self.source=source
        def set_authorizer(self,*a):pass
        def set_progress_handler(self,*a):pass
        def backup(self,target,**kwargs):kwargs['progress'](0,0,1)
        def execute(self,sql):
            if sql=='PRAGMA page_size':return Cursor([(4096,)],'size')
            if sql=='PRAGMA integrity_check':return Cursor(integrity,'integrity')
            if sql=='PRAGMA foreign_key_check':return Cursor(foreign_keys,'fk')
            assert sql=='PRAGMA temp_store=MEMORY'
        def close(self):closed.append('source' if self.source else 'target')
    monkeypatch.setattr(sqlite3,'connect',lambda database,**kwargs:Connection(database!=':memory:'))
    try:
        result=SourceSnapshotAndT3(admission=lambda j:True).run(job)
        assert result['physical_verdict']==verdict
        assert seen.count('integrity')==len(integrity) and seen.count('fk')==len(foreign_keys)
        assert {'source','target','integrity','fk'}<=set(closed)
        assert 'private' not in str(result)
    finally:writer.close()
