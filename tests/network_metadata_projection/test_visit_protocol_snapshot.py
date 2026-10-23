"""#296 Visit reads on canonical strict NI02; maintenance stays explicit."""
from contextlib import contextmanager
from datetime import timedelta
import json
import sqlite3
import time

import pytest

from app.analytics.source_gateway import QueryDeadline, AnalyticsQueryDeadlineExceeded
from app.network_metadata.validation import ni_format_utc
from app.network_metadata_projection.models import ProjectionUnavailable, ProjectionValidationError
from app.network_metadata_projection.read_service import DeviceNetworkMetadataReadService
from app.network_metadata_projection.repository import ProjectionRepository
from app.network_metadata_projection.schema import validate_schema
from .support import SITE, MAC, T0
from .test_protocol_evidence_snapshot import state, DEVICE

INDEX = 'idx_projection_mac_family_event_latest'


def read(value, *, start=-60, end=60, now=120, reader=None, **changes):
    args = dict(site_id=SITE, device_id=DEVICE, client_mac=MAC,
        started_at=ni_format_utc(T0+timedelta(seconds=start)),
        ended_at=ni_format_utc(T0+timedelta(seconds=end)),
        evaluated_at=ni_format_utc(T0+timedelta(seconds=now)), deadline=QueryDeadline.after(5))
    args.update(changes)
    return (reader or DeviceNetworkMetadataReadService(value.config.db_path)).read_visit_protocol_snapshot(**args)


def insert(value, *, edge, at, family='dns', site=SITE, mac=MAC):
    c=value.repo.connection
    original=dict(c.execute('SELECT * FROM device_network_metadata_edges WHERE site_id=? AND client_mac=? LIMIT 1', (SITE,MAC)).fetchone())
    original.update(edge_id=edge,event_at=ni_format_utc(T0+timedelta(seconds=at)),
        source_event_family=family,site_id=site,client_mac=mac,source_observation_ref='synthetic-'+edge)
    c.execute('INSERT INTO device_network_metadata_edges('+','.join(original)+') VALUES('+','.join('?' for _ in original)+')',tuple(original.values()))


def trace(reader, monkeypatch):
    statements=[]; original=reader._snapshot
    @contextmanager
    def traced(**kwargs):
        with original(**kwargs) as c:
            c.set_trace_callback(statements.append)
            yield c
    monkeypatch.setattr(reader,'_snapshot',traced)
    return statements


def test_real_visit_intervals_are_not_24h_and_adjacent_visits_do_not_mix(state):
    insert(state,edge='1'*64,at=10,family='tls')
    insert(state,edge='2'*64,at=60,family='quic')
    a=read(state,start=0,end=60,now=180)
    b=read(state,start=60,end=180,now=180)
    assert {f['source_event_family'] for f in a['facts']}=={'dns','tls'}
    assert [f['edge_id'] for f in b['facts']]==['2'*64]
    assert all(f['event_at']<ni_format_utc(T0+timedelta(seconds=60)) for f in a['facts'])
    assert a['historical_completeness_claimed'] is False
    # A later REAL visit is not a future-data corruption of closed A.
    assert read(state,start=0,end=60,now=180)==a


def test_open_evaluation_upper_bound_and_genuine_future_are_excluded(state):
    # The fixture's authoritative Device binding is confirmed at T0+30s.
    # Both real evaluation instants must be AFTER that confirmation.
    insert(state,edge='1'*64,at=40,family='tls')
    insert(state,edge='2'*64,at=50,family='quic')
    insert(state,edge='3'*64,at=200,family='dns')
    before=read(state,start=0,end=40,now=40)
    after=read(state,start=0,end=60,now=60)
    assert [f['source_event_family'] for f in before['facts']]==['dns']
    assert {f['source_event_family'] for f in after['facts']}=={'dns','tls','quic'}
    assert all(f['edge_id']!='3'*64 for f in after['facts'])


def test_deterministic_ties_last_per_family_and_no_payload(state,monkeypatch):
    insert(state,edge='b'*64,at=10,family='tls')
    insert(state,edge='a'*64,at=10,family='tls')
    insert(state,edge='c'*64,at=9,family='tls')
    reader=DeviceNetworkMetadataReadService(state.config.db_path);statements=trace(reader,monkeypatch)
    result=read(state,reader=reader)
    assert next(f['edge_id'] for f in result['facts'] if f['source_event_family']=='tls')=='a'*64
    queries=[s for s in statements if 'FROM device_network_metadata_edges' in s]
    assert len(queries)==3 and all(INDEX in q and 'LIMIT 1' in q for q in queries)
    assert all(set(f)=={'edge_id','event_at','source_event_family'} for f in result['facts'])
    assert not any(s.startswith(('UPDATE','INSERT','DELETE','CREATE','PRAGMA wal_checkpoint')) for s in statements)


@pytest.mark.parametrize('binding',[None,'not_yet_registry_resolved','registry_unavailable'])
def test_unverified_identity_never_looks_at_edges(state,monkeypatch,binding):
    c=state.repo.connection
    if binding is None:
        c.execute('DELETE FROM projection_site_mac_bindings WHERE site_id=? AND client_mac=?',(SITE,MAC))
    else:
        c.execute('UPDATE projection_site_mac_bindings SET binding_state=?,device_id=NULL,authoritative_bound_at=NULL WHERE site_id=? AND client_mac=?',(binding,SITE,MAC))
    reader=DeviceNetworkMetadataReadService(state.config.db_path);statements=trace(reader,monkeypatch)
    assert read(state,reader=reader)['facts']==()
    assert not any('FROM device_network_metadata_edges' in s for s in statements)


def test_different_device_and_future_binding_fail_closed(state):
    with pytest.raises(ProjectionUnavailable):read(state,device_id='20000000-0000-4000-8000-000000000002')
    state.repo.connection.execute('UPDATE projection_site_mac_bindings SET authoritative_bound_at=? WHERE site_id=? AND client_mac=?',
        (ni_format_utc(T0+timedelta(days=1)),SITE,MAC))
    with pytest.raises(ProjectionUnavailable):read(state)


@pytest.mark.parametrize('changes',[dict(started_at='bad'),dict(ended_at='bad'),dict(evaluated_at='bad'),
    dict(site_id='bad'),dict(device_id='bad'),dict(client_mac='BAD'),
    dict(started_at=ni_format_utc(T0+timedelta(seconds=60))),
    dict(ended_at=ni_format_utc(T0+timedelta(seconds=121)))])
def test_bad_or_future_interval_is_rejected_before_open(state,monkeypatch,changes):
    def forbidden(*args,**kwargs):raise AssertionError('must validate before opening')
    reader=DeviceNetworkMetadataReadService(state.config.db_path)
    monkeypatch.setattr(reader,'_snapshot',forbidden)
    with pytest.raises(ProjectionValidationError):read(state,reader=reader,**changes)


def test_indexless_canonical_schema_rejects_startup_without_implicit_repair(state):
    from app.network_metadata_projection.ni03_top1_migration import migrate
    c=state.repo.connection;c.execute('DROP INDEX '+INDEX)
    with pytest.raises(ProjectionUnavailable):validate_schema(c)
    with pytest.raises(ProjectionUnavailable):read(state)
    count=c.execute('SELECT count(*) FROM device_network_metadata_edges').fetchone()[0]
    state.repo.close()
    with pytest.raises(ProjectionUnavailable):ProjectionRepository(state.config,clock=state.clock).initialize()
    with sqlite3.connect(state.config.db_path) as stored:
        assert stored.execute('SELECT 1 FROM sqlite_schema WHERE name=?',(INDEX,)).fetchone() is None
        assert stored.execute('SELECT count(*) FROM device_network_metadata_edges').fetchone()[0]==count
    assert migrate(state.config,direction='up',maintenance_confirmed=True) is True
    state.repo=ProjectionRepository(state.config,clock=state.clock).initialize()
    assert len(read(state)['facts'])==1
    assert state.repo.connection.execute('SELECT count(*) FROM device_network_metadata_edges').fetchone()[0]==count
    assert len(state.repo.connection.execute('SELECT 1 FROM sqlite_schema WHERE name=?',(INDEX,)).fetchall())==1
    state.repo.close()
    state.repo=ProjectionRepository(state.config,clock=state.clock).initialize()
    assert len(read(state)['facts'])==1  # already installed: no duplicate CREATE


def test_wrong_same_name_index_and_unknown_extra_schema_are_rejected(state):
    c=state.repo.connection;c.execute('DROP INDEX '+INDEX)
    c.execute('CREATE INDEX '+INDEX+' ON device_network_metadata_edges(site_id,client_mac,event_at)')
    with pytest.raises(ProjectionUnavailable):validate_schema(c)
    with pytest.raises(ProjectionUnavailable):read(state)


def test_index_migration_rolls_back_on_injected_crash_then_retries(state):
    from app.network_metadata_projection.ni03_top1_migration import migrate
    state.repo.connection.execute('DROP INDEX '+INDEX);state.repo.close()
    def crash(point):
        if point=='index_changed':raise RuntimeError('synthetic crash')
    with pytest.raises(RuntimeError):migrate(state.config,direction='up',maintenance_confirmed=True,crash_point=crash)
    with sqlite3.connect(state.config.db_path) as c:
        assert c.execute('SELECT 1 FROM sqlite_schema WHERE name=?',(INDEX,)).fetchone() is None
    assert migrate(state.config,direction='up',maintenance_confirmed=True) is True
    state.repo=ProjectionRepository(state.config,clock=state.clock).initialize()
    assert len(read(state)['facts'])==1


def test_deadline_and_disabled_boundaries(state):
    with pytest.raises(AnalyticsQueryDeadlineExceeded):read(state,deadline=QueryDeadline.after(-1))
    with pytest.raises(ProjectionUnavailable):
        read(state,reader=DeviceNetworkMetadataReadService(state.config.db_path,enabled=False))


def test_100k_source_constant_result_and_index_plan(state,monkeypatch,record_property):
    c=state.repo.connection
    original=dict(c.execute('SELECT * FROM device_network_metadata_edges WHERE client_mac=? LIMIT 1',(MAC,)).fetchone())
    sql='INSERT INTO device_network_metadata_edges('+','.join(original)+') VALUES('+','.join('?' for _ in original)+')'
    c.execute('BEGIN IMMEDIATE')
    try:
        for n in range(100000):
            row=dict(original,edge_id=f'{n:064x}',source_observation_ref=f'synthetic-100k-{n}',
                source_event_family=('dns','tls','quic')[n%3],event_at=ni_format_utc(T0+timedelta(microseconds=n)))
            c.execute(sql,tuple(row.values()))
        c.execute('COMMIT')
    except BaseException:
        c.execute('ROLLBACK');raise
    assert c.execute('SELECT count(*) FROM device_network_metadata_edges').fetchone()[0]>=100000
    reader=DeviceNetworkMetadataReadService(state.config.db_path);statements=trace(reader,monkeypatch)
    started=time.monotonic();result=read(state,reader=reader);elapsed=time.monotonic()-started
    queries=[s for s in statements if 'FROM device_network_metadata_edges' in s]
    plans=[tuple(tuple(r) for r in c.execute('EXPLAIN QUERY PLAN '+q)) for q in queries]
    assert len(queries)==3 and len(result['facts'])==3
    assert all(any('SEARCH' in row[3] and INDEX in row[3] for row in plan) for plan in plans)
    assert all(not any('SCAN ' in row[3] or 'TEMP B-TREE' in row[3] for row in plan) for plan in plans)
    record_property('visit_protocol_100k',json.dumps(dict(kind='DISPOSABLE_LAB_ONLY_NOT_HDD_BENEFIT',
        rows=100002,queries=queries,plans=plans,result_count=len(result['facts']),read_seconds=elapsed)))
