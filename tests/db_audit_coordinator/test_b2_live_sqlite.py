"""RAM domain bridges and disposable source backup, never a real store audit."""
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import sqlite3
import sys
import uuid

import pytest

from app.db_audit_coordinator import live_sqlite as audit
from tests.db_audit_coordinator.test_b2_live_policy import policy,STORES

AT='2026-10-19T00:00:00.000000Z'
POSIX=pytest.mark.skipif(sys.platform!='linux',reason='Linux/POSIX source inode and read-only WAL I/O contract')


def initialize(db,store):
    """Owner DDL runs ONLY during disposable fixture construction."""
    if store=='network_service_intelligence':
        from app.network_service_recognition.materialization_schema import create_schema
        from app.network_service_recognition.artifacts import IDS
        create_schema(db,AT)
        gen='00000000-0000-4000-8000-000000000001'
        db.execute('''INSERT INTO service_materialization_generations
            (generation_id,state,taxonomy_id,taxonomy_version,taxonomy_digest_sha256,
            knowledge_manifest_id,knowledge_manifest_version,knowledge_manifest_digest_sha256,
            ruleset_id,ruleset_version,ruleset_digest_sha256,build_started_at_utc,backfill_from_utc,
            live_feed_start_seq,publishable_until_utc) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (gen,'building',IDS['taxonomy'],1,'1'*64,IDS['knowledge_manifest'],1,'2'*64,
                IDS['ruleset'],1,'3'*64,AT,AT,0,'2027-01-01T00:00:00.000000Z'))
        db.execute('INSERT INTO service_recognition_observations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            ('4'*64,gen,'5'*64,'00000000-0000-5000-8000-000000000002','0123456789abcdef01234567',
                '00000000-0000-4000-8000-000000000003','02:00:00:00:00:04',1,AT,'tls',
                'service.youtube','org.google','category.video_streaming','strong','directly_supported','rule.synthetic',AT))
    elif store=='traffic_projection':
        from app.traffic_projection.repository import schema_sql
        db.executescript(schema_sql())
    else:
        from app.db_audit_coordinator.adapter_public_traffic import expected_signature
        for kind,name,table,sql in expected_signature():
            if kind=='table':db.execute(sql)
        for kind,name,table,sql in expected_signature():
            if kind=='index':db.execute(sql)
        db.execute('PRAGMA user_version=2')
        db.execute('INSERT INTO counter_state VALUES(1,0,NULL,?)',(AT,))
        db.execute('INSERT INTO traffic_daily VALUES(?,?,?,?,?)',('2026-10-19','synthetic-ssid',1234,1,AT))
    db.commit()


@pytest.mark.parametrize('store',STORES)
def test_completed_ram_snapshot_gets_real_store_specific_t3(store):
    db=sqlite3.connect(':memory:',isolation_level=None);db.row_factory=sqlite3.Row
    try:
        initialize(db,store);db.execute('PRAGMA foreign_keys=ON')
        result=audit.validate_snapshot(db,policy(store),lambda:None)
        assert result['schema_version']==policy(store).schema_version
        assert result['page_count']>0
        assert result['generation_kind']==('pinned_file_instance' if store=='public_traffic' else 'native_lineage')
        assert all(len(result[key])==64 for key in ('lineage_sha256','watermark_sha256'))
    finally:db.close()


def test_existing_fingerprint_full_t3_bridge_remains_available_on_tiny_ram_fixture():
    from app.device_fingerprint.schema import SCHEMA_SQL
    db=sqlite3.connect(':memory:',isolation_level=None);db.row_factory=sqlite3.Row
    try:
        db.executescript(SCHEMA_SQL)
        db.execute('INSERT INTO device_fingerprint_storage_state VALUES(1,?,0)',(str(uuid.uuid4()),))
        output=audit.validate_snapshot(db,policy('fingerprint_evidence'),lambda:None)
        assert output['schema_version']==2 and output['generation_kind']=='native_lineage'
        db.execute('PRAGMA ignore_check_constraints=ON')  # RAM fault injection only.
        db.execute('UPDATE device_fingerprint_storage_state SET last_ingest_sequence=-1')
        db.execute('PRAGMA ignore_check_constraints=OFF')
        with pytest.raises(Exception):audit.validate_snapshot(db,policy('fingerprint_evidence'),lambda:None)
    finally:db.close()


@pytest.mark.parametrize('store',STORES)
def test_wrong_schema_or_missing_required_table_never_passes(store):
    db=sqlite3.connect(':memory:',isolation_level=None);db.row_factory=sqlite3.Row
    try:
        initialize(db,store);db.execute('PRAGMA user_version=99')
        with pytest.raises(Exception):audit.validate_snapshot(db,policy(store),lambda:None)
    finally:db.close()


@pytest.mark.parametrize('fault',['extra_schema','generation_digest','fact_digest','source_uuid','mac','FK','category','service_id'])
def test_ni04_nonempty_domain_and_foreign_key_canaries(fault):
    db=sqlite3.connect(':memory:',isolation_level=None);db.row_factory=sqlite3.Row
    try:
        initialize(db,'network_service_intelligence')
        # Fault injection is confined to disposable RAM. Immutable fact trigger
        # is retained; invalid inserts use a new fact, not production mutation.
        if fault=='extra_schema':db.execute('CREATE TABLE forbidden_extra(value)')
        elif fault=='generation_digest':db.execute("UPDATE service_materialization_generations SET ruleset_digest_sha256='bad'")
        else:
            row=dict(db.execute('SELECT * FROM service_recognition_observations').fetchone())
            row.update(service_observation_id='6'*64,edge_id='7'*64)
            field,value={'fact_digest':('service_observation_id','not-a-digest'),
                'source_uuid':('source_observation_ref','not-a-uuid'),
                'mac':('client_mac','invalid'), 'FK':('generation_id',str(uuid.uuid4())),
                'category':('service_category_id','category.unknown'), 'service_id':('service_id','invalid')}[fault]
            row[field]=value
            db.execute('INSERT INTO service_recognition_observations VALUES('+','.join('?' for _ in row)+')',tuple(row.values()))
        with pytest.raises(Exception):audit.validate_snapshot(db,policy('network_service_intelligence'),lambda:None)
    finally:db.close()


def test_public_t3_accepts_real_reset_semantics_not_resummed_history():
    db=sqlite3.connect(':memory:',isolation_level=None);db.row_factory=sqlite3.Row
    try:
        initialize(db,'public_traffic')
        db.execute('INSERT INTO processed_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
            ('synthetic-id','synthetic-ssid','omada.client_offline','2026-10-19',98765,1,None,'source','/fixture/log',0,123,AT))
        db.execute('INSERT INTO counter_resets VALUES(?,?,?,?,?,?,?,?,?)',
            (str(uuid.uuid4()),'all',None,AT,1234,1234,1,1,1))
        db.execute('UPDATE traffic_daily SET traffic_bytes=0,completed_sessions=0')
        assert audit.validate_snapshot(db,policy(),lambda:None)['schema_version']==2
        db.execute('UPDATE processed_events SET source_offset_start=999')
        with pytest.raises(Exception):audit.validate_snapshot(db,policy(),lambda:None)
    finally:db.close()


def disposable(tmp_path,store):
    source=tmp_path/(store+'.db');db=sqlite3.connect(source,isolation_level=None)
    db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA synchronous=FULL')
    initialize(db,store)
    # Fixtures deliberately retain the writer connection and native sidecars.
    for target in tmp_path.iterdir():target.chmod(0o600)
    info=source.stat()
    return db,policy(store,source=str(source),device=info.st_dev,inode=info.st_ino,uid=info.st_uid,gid=info.st_gid)


def hashes(source):
    return {suffix:hashlib.sha256(Path(source+suffix).read_bytes()).hexdigest() for suffix in ('','-wal')}


@POSIX
@pytest.mark.parametrize('store',STORES)
def test_real_online_backup_and_full_t3_never_change_source_or_wal(tmp_path,store):
    writer,value=disposable(tmp_path,store);before=hashes(value.source);admissions=[];guards=[]
    try:
        output=audit.audit(value,lambda:guards.append(1),lambda image,wal:admissions.append((image,wal)))
        assert output['schema_version']==value.schema_version and len(guards)>3 and admissions
        assert hashes(value.source)==before
        assert writer.execute('PRAGMA journal_mode').fetchone()[0]=='wal'
        assert writer.execute('PRAGMA synchronous').fetchone()[0]==2
    finally:writer.close()


@POSIX
def test_missing_source_is_not_created(tmp_path):
    value=policy(source=str(tmp_path/'missing.db'),uid=os.geteuid(),gid=os.getegid())
    with pytest.raises(Exception):audit.audit(value,lambda:None,lambda *args:None)
    assert not tuple(tmp_path.iterdir())


@POSIX
def test_checkpointed_wal_without_sidecars_is_denied_before_sqlite_open(tmp_path):
    writer,value=disposable(tmp_path,'public_traffic');writer.close()
    assert not Path(value.source+'-wal').exists()
    before=Path(value.source).read_bytes()
    with pytest.raises(Exception):audit.audit(value,lambda:None,lambda *args:None)
    assert Path(value.source).read_bytes()==before and not Path(value.source+'-wal').exists()


@POSIX
@pytest.mark.parametrize('fault',['identity','cap','guard','domain','shm_budget'])
def test_source_identity_budget_cancel_and_domain_failure_are_closed(tmp_path,fault):
    writer,value=disposable(tmp_path,'public_traffic');before=hashes(value.source)
    try:
        if fault=='identity':value=replace(value,inode=value.inode+1)
        if fault=='cap':value=replace(value,image_max_bytes=value.source_max_bytes)
        if fault=='shm_budget':value=replace(value,backup_overhead_bytes=1)
        def guard():
            if fault=='guard':raise RuntimeError('synthetic interruption')
        def admission(*_):
            if fault=='cap':raise RuntimeError('insufficient guest headroom')
        def after(db):
            if fault=='domain':db.execute('DROP TABLE traffic_daily')
        with pytest.raises(Exception):audit.audit(value,guard,admission,after_backup=after)
        assert hashes(value.source)==before
    finally:writer.close()


@POSIX
def test_live_writer_post_backup_commit_not_misreported_as_audit_mutation(tmp_path):
    writer,value=disposable(tmp_path,'public_traffic')
    def append(_destination):writer.execute('UPDATE traffic_daily SET traffic_bytes=5678')
    try:
        result=audit.audit(value,lambda:None,lambda *_:None,after_backup=append)
        assert result['page_count']>0
        assert writer.execute('SELECT traffic_bytes FROM traffic_daily').fetchone()[0]==5678
        assert writer.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    finally:writer.close()
