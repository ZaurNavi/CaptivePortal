"""Phase2 closed API, same sampler/read count and legacy exact projection."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
from unittest.mock import Mock
import pytest
from app.admin_web import operations_service as ops
from app.admin_web.operations_schema import validate_v4,validate_v5,core_workload
from app.operations_health import NI04_UNIT,CLASSIFICATION_UNIT,TRAFFIC_UNIT
from app.operations_app_health import phase2_workload
from .test_operations_v4 import phase1_service,WorkloadReader
from .test_operations_owner_health import OwnerReader
from .test_db_services_routes import operations_app,logged_in
from .test_operations_service import NOW

API='/admin/api/v5/operations/db-services'


def phase2_service(monkeypatch,count=7):
    s,sensor,owner,ni02,calls,tick,boot=phase1_service(monkeypatch)
    owner.workload=phase2_workload(NI04_UNIT,dict(feed_backlog_entries=None,visit_outbox_unacked=count))
    readers={'network_service_recognition':owner}
    for key,unit,native,w in [('fingerprint_classification',CLASSIFICATION_UNIT,'ready',None),
            ('traffic_projection',TRAFFIC_UNIT,None,dict(incremental_backlog_present=1))]:
        reader=OwnerReader(unit,native) if unit==CLASSIFICATION_UNIT else WorkloadReader(OwnerReader(unit,native),phase2_workload(unit,w))
        s._owner_health_readers[key]=reader;s._owner_health[key].reader=reader;readers[key]=reader
    return s,readers,calls,tick,boot


@pytest.mark.parametrize('count',[None,0,7,2**53-1])
def test_v5_full_v4_projection_one_sampler_and_no_sql(monkeypatch,count):
    import sqlite3
    s,readers,calls,*_=phase2_service(monkeypatch,count)
    monkeypatch.setattr(sqlite3,'connect',Mock(side_effect=AssertionError('Admin SQL forbidden')))
    try:
        old=[s.read('same',version=v) for v in (1,2,3,4)]
        model=validate_v5(s.read('same',version=5));w=model['workload']
        assert w['network_service_recognition']==dict(feed_backlog_entries=None,visit_outbox_unacked=count)
        assert w['fingerprint_classification']==phase2_workload(CLASSIFICATION_UNIT)
        assert w['portal_core']==core_workload()
        assert w['traffic_projection']==dict(incremental_backlog_present=1)
        projected=dict(model,api_version=ops.API_VERSION_V4,workload={k:old[3]['workload'][k] for k in old[3]['workload']})
        assert validate_v4(projected)==old[3]
        assert calls==[1] and all(r.calls==1 for r in readers.values())
        assert all(len(r['application_health_evidence'])==7 for r in model['services'])
        assert (len(model['services']),len(model['databases']),len(model['topology']['nodes']),len(model['topology']['edges']))==(9,17,31,45)
        assert len(json.dumps(model).encode())<ops.RESPONSE_LIMIT
    finally:s.close()


@pytest.mark.parametrize('count',[0,7,2**53-1])
@pytest.mark.parametrize('injection',['decoded-fake','cached-private-record'])
def test_classification_v1_health_and_v5_nulls_ignore_forged_numbers(monkeypatch,count,injection):
    import sqlite3
    s,readers,calls,*_=phase2_service(monkeypatch)
    forged=dict(integration_jobs_pending=count,integration_jobs_leased=count)
    if injection=='decoded-fake':
        fake=WorkloadReader(readers['fingerprint_classification'],forged)
        s._owner_health_readers['fingerprint_classification']=fake
        s._owner_health['fingerprint_classification'].reader=fake
    monkeypatch.setattr(sqlite3,'connect',Mock(side_effect=AssertionError('Admin SQL forbidden')))
    try:
        first=s.read('initial',version=5)
        if injection=='cached-private-record':
            s._cache[0]['_health_records']['fingerprint_classification']['workload']=forged
        else:
            assert 'workload' not in s._cache[0]['_health_records']['fingerprint_classification']
        result=validate_v5(s.read('same',version=5))
        assert first['workload']['fingerprint_classification']==dict(integration_jobs_pending=None,integration_jobs_leased=None)
        assert result['workload']['fingerprint_classification']==dict(integration_jobs_pending=None,integration_jobs_leased=None)
        row=next(r for r in result['services'] if r['id']=='fingerprint_classification')
        assert row['application_health']=='healthy' and row['application_health_evidence']['state']=='healthy'
        assert calls==[1] and readers['fingerprint_classification'].calls==1
        for version in (1,2,3,4):
            legacy=s.read('same',version=version)
            assert 'fingerprint_classification' not in legacy.get('workload',{})
    finally:s.close()


@pytest.mark.parametrize('source',['network_service_recognition','fingerprint_classification','traffic_projection'])
@pytest.mark.parametrize('fault',['missing','invalid','before-start','wrong-pid','start-changed','stale-cache','expired','degraded-cache'])
def test_v5_cannot_carry_old_numeric(monkeypatch,source,fault):
    s,readers,calls,tick,boot=phase2_service(monkeypatch)
    units={'network_service_recognition':NI04_UNIT,'fingerprint_classification':CLASSIFICATION_UNIT,'traffic_projection':TRAFFIC_UNIT}
    try:
        s.read('first',version=5)
        if fault=='stale-cache':tick[0]=91;s._last_attempt=91
        elif fault=='expired':boot[0]+=180_000_000_001
        else:
            row=next(r for r in s._cache[0]['services'] if r['id']==source)
            report=readers[source].read(row,NOW);collector=s._owner_health[source]
            if fault=='missing':report={'status':'unknown'}
            elif fault=='invalid':report['workload']={'private':1}
            elif fault=='before-start':report['observed_at']='2000-01-01T00:00:00.000Z'
            elif fault=='wrong-pid':report['producer']=dict(report['producer'],pid=999)
            elif fault=='start-changed':row['started_at_utc']='2099-01-01T00:00:00.000Z'
            elif fault=='degraded-cache':
                report['health']=dict(state='degraded',reason='source_degraded');collector.collect(report,row,NOW)
                report={'status':'unknown'}
            s._cache[0]['_health_records'][source]=collector.collect(report,row,NOW)
        assert validate_v5(s.read('after',version=5))['workload'][source]==phase2_workload(units[source])
        assert calls==[1]
    finally:s.close()


@pytest.mark.parametrize('fault',['fresh','cache-stale','expired','pid-changed'])
def test_core_sampler_once_with_pid_bound_workload_and_no_database(monkeypatch,fault):
    s,_,calls,tick,boot=phase2_service(monkeypatch)
    monkeypatch.setattr(ops.os,'getpid',lambda:123)
    w=dict(portal_evidence_queue_depth=3,visit_writer_foreground_waiters=2,visit_writer_background_waiters=4)
    provider=Mock(return_value=dict(health=dict(state='healthy',reason='core_composed'),observed_at=NOW,workload=w))
    s.set_core_snapshot_provider(provider)
    try:
        assert s.read('initial',version=5)['workload']['portal_core']==w
        if fault=='cache-stale':tick[0]=91;s._last_attempt=91
        elif fault=='expired':boot[0]+=180_000_000_001
        elif fault=='pid-changed':s._cache[0]['services'][0]['main_pid']=999
        # Locate by ID instead of relying on catalog order for PID mismatch.
        if fault=='pid-changed':next(r for r in s._cache[0]['services'] if r['id']=='portal_core')['main_pid']=999
        result=s.read('after',version=5)['workload']['portal_core']
        assert result==(w if fault=='fresh' else core_workload())
        assert calls==[1] and provider.call_count==1
    finally:s.close()


FIELDS=[('network_service_recognition','visit_outbox_unacked'),('network_service_recognition','feed_backlog_entries'),
    ('fingerprint_classification','integration_jobs_pending'),('fingerprint_classification','integration_jobs_leased'),
    ('portal_core','portal_evidence_queue_depth'),('portal_core','visit_writer_foreground_waiters'),
    ('portal_core','visit_writer_background_waiters'),('traffic_projection','incremental_backlog_present')]


@pytest.mark.parametrize('source,field',FIELDS)
@pytest.mark.parametrize('bad',[True,-1,2**53,1.5,'1',{},[]])
def test_v5_rejects_invalid_counts(monkeypatch,source,field,bad):
    s,*_=phase2_service(monkeypatch)
    try:model=s.read('fixture',version=5)
    finally:s.close()
    model['workload'][source][field]=bad
    with pytest.raises(ops.OperationsError):validate_v5(model)


@pytest.mark.parametrize('count',[0,7,2**53-1])
def test_v5_schema_accepts_complete_bounded_pairs_without_claiming_live_classification_proof(monkeypatch,count):
    s,*_=phase2_service(monkeypatch)
    try:model=s.read('fixture',version=5)
    finally:s.close()
    model['workload']['portal_core']=dict.fromkeys(core_workload(),count)
    # DTO validation only: actual Classification publisher remains null-only.
    model['workload']['fingerprint_classification']=dict(integration_jobs_pending=count,integration_jobs_leased=count)
    model['workload']['traffic_projection']['incremental_backlog_present']=0
    assert validate_v5(model)==model


@pytest.mark.parametrize('fault',['root','service','database','extra-source','extra-field','missing','null-object','feed-number','traffic-two','mixed-jobs','mixed-waiters'])
def test_v5_closed_privacy_and_coherence(monkeypatch,fault):
    s,*_=phase2_service(monkeypatch)
    try:model=s.read('fixture',version=5)
    finally:s.close()
    w=model['workload']
    if fault=='root':model['private']='PRIVATE'
    elif fault=='service':model['services'][0]['application_health_evidence']['private']='PRIVATE'
    elif fault=='database':model['databases'][0]['private']='PRIVATE'
    elif fault=='extra-source':w['private']={}
    elif fault=='extra-field':w['portal_core']['private']=1
    elif fault=='missing':w.pop('portal_core')
    elif fault=='null-object':w['portal_core']=None
    elif fault=='feed-number':w['network_service_recognition']['feed_backlog_entries']=0
    elif fault=='traffic-two':w['traffic_projection']['incremental_backlog_present']=2
    elif fault=='mixed-jobs':w['fingerprint_classification']['integration_jobs_pending']=0
    else:w['portal_core']['visit_writer_foreground_waiters']=0
    with pytest.raises(ops.OperationsError):validate_v5(model)


@pytest.mark.parametrize('fault',['ok','query','body','http','network','permission','disabled','pending','size','post','unauth'])
def test_v5_same_authenticated_read_only_route(monkeypatch,fault):
    app,runtime,_=operations_app(monkeypatch,flag='false' if fault=='disabled' else 'true',
        grants='admin.read.settings.global' if fault=='permission' else 'admin.read.operations')
    s,*_=phase2_service(monkeypatch)
    try:model=s.read('fixture',version=5)
    finally:s.close()
    if runtime.operations_service:runtime.operations_service.close()
    runtime.operations_service=Mock();runtime.operations_service.read.return_value=model
    if fault=='pending':runtime.operations_service.read.side_effect=ops.OperationsError('snapshot_pending')
    if fault=='size':monkeypatch.setattr(ops,'RESPONSE_LIMIT',10)
    kwargs=dict(base_url='https://localhost');path=API
    if fault=='query':path+='?PRIVATE=1'
    if fault=='body':kwargs['data']=b'PRIVATE'
    if fault=='http':kwargs['base_url']='http://localhost'
    if fault=='network':kwargs['environ_overrides']={'REMOTE_ADDR':'203.0.113.1'}
    client=app.test_client() if fault=='unauth' else logged_in(app)
    try:
        response=getattr(client,'post' if fault=='post' else 'get')(path,**kwargs)
        assert response.status_code==dict(ok=200,query=400,body=400,http=403,network=403,permission=403,
            disabled=404,pending=503,size=503,post=405,unauth=401)[fault]
        if fault=='ok':validate_v5(response.json)
        elif fault!='post':assert response.json['api_version']==ops.API_VERSION_V5
        assert b'PRIVATE' not in response.data
    finally:runtime.clear()


@pytest.mark.parametrize('scenario',['valid','zero','core-known','traffic-zero','unknown','stale','refresh-failure','fallback-v4','fallback-v3','fallback-v2','fallback-v1',
    '401','403','500','503','bad-json','bad-version','bad-count','bad-feed','bad-pair','bad-check','extra-workload'])
def test_v5_existing_cards_and_topology_strict_browser_contract(monkeypatch,tmp_path,scenario):
    s,*_=phase2_service(monkeypatch,0 if scenario=='zero' else 7)
    try:model=s.read('fixture',version=5)
    finally:s.close()
    if scenario=='unknown':
        for key,unit in [('network_service_recognition',NI04_UNIT),('fingerprint_classification',CLASSIFICATION_UNIT),('traffic_projection',TRAFFIC_UNIT)]:
            model['workload'][key]=phase2_workload(unit)
    if scenario=='stale':model['sample_status']='stale'
    if scenario=='core-known':model['workload']['portal_core']=dict(portal_evidence_queue_depth=3,visit_writer_foreground_waiters=2,visit_writer_background_waiters=4)
    if scenario=='traffic-zero':model['workload']['traffic_projection']['incremental_backlog_present']=0
    fixture=tmp_path/'v5.json';fixture.write_text(json.dumps(model),encoding='utf-8')
    root=Path(__file__).parents[2];node=shutil.which('node');assert node
    result=subprocess.run([node,str(Path(__file__).with_name('db_services_v5_ui.cjs')),
        str(root/'app/admin_web/static/db_services.js'),str(fixture),scenario],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
