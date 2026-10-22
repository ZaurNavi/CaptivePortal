"""WP3 versioned projection, auth, truth and independent evidence age."""
import copy
import json
from types import SimpleNamespace
from unittest.mock import Mock
from pathlib import Path
import shutil
import subprocess

import pytest

from app.admin_web import operations_service as ops
from app.admin_web.operations_health import SensorHealthEvidence, project
from app.admin_web.operations_schema import validate_v2
from app.operations_health import sensor_health, DEPENDENCIES, SENSOR_UNIT
from app.operations_health import ni02_health, NI02_UNIT
from tests.admin_web.test_operations_inventory import resolved
from tests.admin_web.test_operations_service import NOW, regular, systemd_text
from tests.admin_web.test_db_services_routes import operations_app, logged_in
from tests.device_fingerprint_sensor.test_operations_metadata import report as metadata_report

API = '/admin/api/v2/operations/db-services'
V1 = '/admin/api/v1/operations/db-services'
ORIGIN = 100_000_000_000


class Reader:
    def __init__(self,state='ready'):
        self.calls=0;self.state=state
        self.producer=metadata_report()['producer']
        self.channel=lambda:SimpleNamespace(sensor_uid=1003)
        self.identity=lambda pid,uid:dict(self.producer,pid=pid)

    def read(self,service,now,**kwargs):
        self.calls+=1
        if self.state=='missing':return dict(status='unknown',reason='metadata_unavailable',stores=None)
        return dict(status='fresh',reason=None,stores=metadata_report()['stores'],
            health=sensor_health(self.state,dict.fromkeys(DEPENDENCIES[SENSOR_UNIT],True)),
            observed_at=ops.timestamp(NOW),age=0,producer=self.producer,expires_boottime_ns=ORIGIN+180_000_000_000)


def reader_service(monkeypatch,state='ready',clock=None):
    clock=clock or [ORIGIN]
    monkeypatch.setattr(ops,'boot_ns',lambda:clock[0])
    reader=Reader(state);sources=[]
    def acquire(cancel):sources.append(1);return systemd_text()
    service=ops.AdminOperationsReadService(resolved(),acquire=acquire,lstat=regular,now=lambda:NOW,
        sensor_metadata=reader,monotonic=lambda:0)
    return service,reader,sources


@pytest.mark.parametrize('native,state',[('ready','healthy'),('degraded','degraded'),('unavailable','unavailable'),
    ('initializing','unknown'),('stopping','unknown'),('missing','unknown')])
def test_v2_truthful_native_health_and_v1_identical_projection(monkeypatch,native,state):
    service,reader,sources=reader_service(monkeypatch,native)
    try:
        old=service.read('v1');model=validate_v2(service.read('v2',version=2))
        assert sources==[1] and reader.calls==1
        assert old['api_version']=='admin.operations.db-services.v1' and model['api_version']=='admin.operations.db-services.v2'
        assert all(r['application_health']=='unknown' for r in old['services'])
        sensor=next(r for r in model['services'] if r['id']=='fingerprint_sensor')
        assert sensor['operational_state']=='running' and sensor['application_health']==state
        assert all(r['application_health']=='unknown' for r in model['services'] if r['id']!='fingerprint_sensor')
        for row in model['databases']:
            assert row['store_verification']==dict(status='not_attested',scope=None,as_of=None,source='none',last_result=None,binding='unknown')
            assert row['health_evidence']=='none' and row['schema_observed_version'] is None
        assert len(model['services'])==9 and len(model['databases'])==17
        assert len(model['topology']['nodes'])==31 and len(model['topology']['edges'])==45
        assert all(e['flow_evidence']=='not_instrumented' for e in model['topology']['edges'])
        assert len(json.dumps(model).encode())<48000
        assert len(model['partial_failures'])<=32
        assert not any(key.startswith('_') for key in model)
        assert not any(x in json.dumps(model) for x in ('producer_epoch','boot_id','start_ticks','/source/','/var/lib/','/run/'))
        assert sum(model['summary']['application_health'].values())==9
        for new,previous in zip(model['databases'],old['databases']):
            assert {k:({field:value for field,value in new[k].items() if field not in {'last_result','binding'}} if k=='store_verification' else new[k]) for k in previous}==previous
        for new,previous in zip(model['services'],old['services']):
            assert {k:new[k] for k in previous if k!='application_health'}=={k:v for k,v in previous.items() if k!='application_health'}
        journal=next(r for r in model['databases'] if r['id']=='sensor_spool')
        assert journal['journal_bytes']==(None if native=='missing' else 64)
        assert journal['total_footprint_bytes']==next(r for r in old['databases'] if r['id']=='sensor_spool')['total_footprint_bytes']
    finally:service.close()


def test_source_ttl_inside_fresh_common_cache_never_extends_green(monkeypatch):
    clock=[ORIGIN];service,reader,sources=reader_service(monkeypatch,clock=clock)
    try:
        assert service.read('before',version=2)['summary']['application_health']['healthy']==1
        clock[0]+=180_000_000_001
        model=validate_v2(service.read('expired',version=2))
        assert model['sample_status']=='fresh' and model['summary']['application_health']['healthy']==0
        assert model['summary']['application_health']['stale']==1
        assert sources==[1] and reader.calls==1
        assert next(r for r in model['databases'] if r['id']=='sensor_spool')['journal_bytes'] is None
    finally:service.close()


@pytest.mark.parametrize('native',['degraded','unavailable','ready'])
@pytest.mark.parametrize('fault',['malformed','restarted','dead','ttl'])
def test_invalid_newer_data_retains_only_confirmed_failure_in_same_generation(native,fault):
    reader=Reader(native);cache=SensorHealthEvidence(reader)
    service=dict(operational_state='running',main_pid=123,started_at_utc=ops.timestamp(NOW))
    first=cache.collect(reader.read(service,NOW),service,NOW)
    unknown=dict(status='unknown',reason='metadata_unavailable',stores=None)
    if fault=='restarted':service['main_pid']=124
    if fault=='dead':reader.identity=Mock(side_effect=OSError('PRIVATE'))
    second=cache.collect(unknown,service,NOW)
    expiry=ORIGIN+181_000_000_000 if fault=='ttl' else ORIGIN
    output=project(second,boottime=lambda:expiry)
    expected='unknown' if native=='ready' or fault in {'dead','restarted'} else 'stale' if fault=='ttl' else native
    assert output['state']==expected and output['state']!='healthy'
    if expected in {'degraded','unavailable'}:assert output['observed_at']==first['evidence']['observed_at']
    assert 'PRIVATE' not in json.dumps(output)


@pytest.mark.parametrize('path',[API,V1])
@pytest.mark.parametrize('flag,grants,status',[('false','admin.read.operations',404),('true','admin.read.settings.global',403)])
def test_v2_and_v1_auth_gate_has_no_sampler(monkeypatch,path,flag,grants,status):
    app,runtime,_=operations_app(monkeypatch,flag=flag,grants=grants)
    runtime.operations_service=Mock()
    try:
        response=logged_in(app).get(path,base_url='https://localhost')
        assert response.status_code==status and runtime.operations_service.mock_calls==[]
        assert response.json['api_version']=='admin.operations.db-services.'+('v2' if path==API else 'v1')
    finally:runtime.clear()


def test_v2_unauthenticated_has_no_sampler(monkeypatch):
    app,runtime,_=operations_app(monkeypatch);runtime.operations_service=Mock()
    try:
        response=app.test_client().get(API,base_url='https://localhost')
        assert response.status_code==401 and response.json['api_version']=='admin.operations.db-services.v2'
        assert runtime.operations_service.mock_calls==[]
    finally:runtime.clear()


@pytest.mark.parametrize('method',['post','put','patch','delete','options'])
def test_v2_has_no_control_methods_or_sampling(monkeypatch,method):
    app,runtime,_=operations_app(monkeypatch);runtime.operations_service=Mock()
    try:
        response=getattr(logged_in(app),method)(API,base_url='https://localhost')
        assert response.status_code==(200 if method=='options' else 405)
        assert runtime.operations_service.mock_calls==[]
    finally:runtime.clear()


@pytest.mark.parametrize('suffix,body',[('?path=/private',None),('?site_id=x',None),('',b'body')])
def test_v2_rejects_query_and_body_before_sampling(monkeypatch,suffix,body):
    app,runtime,_=operations_app(monkeypatch);runtime.operations_service=Mock()
    try:
        response=logged_in(app).get(API+suffix,data=body,base_url='https://localhost')
        assert response.status_code==400 and runtime.operations_service.mock_calls==[]
    finally:runtime.clear()


def test_v2_GET_HEAD_and_v1_share_actual_cache(monkeypatch):
    app,runtime,_=operations_app(monkeypatch)
    runtime.operations_service.close();service,reader,sources=reader_service(monkeypatch)
    runtime.operations_service=service;client=logged_in(app)
    try:
        for path in (API,V1,API,V1):
            response=client.get(path,base_url='https://localhost')
            assert response.status_code==200
            assert response.headers['Cache-Control']=='no-store'
        assert client.head(API,base_url='https://localhost').data==b''
        assert sources==[1] and reader.calls==1
    finally:runtime.clear()


@pytest.mark.parametrize('fault',['extra_root','extra_service','extra_evidence','wrong_source','green_unknown','old_api',
    'bool_age','huge_ttl','observed_XSS','scope','attestation','journal_as_WAL','extra_database'])
def test_v2_strict_schema_rejects_privacy_or_false_verified_or_green(fault,monkeypatch):
    service,_,_=reader_service(monkeypatch)
    try:model=service.read('fixture',version=2)
    finally:service.close()
    row=model['services'][0];e=row['application_health_evidence']
    if fault=='extra_root':model['raw_path']='/PRIVATE'
    elif fault=='extra_service':row['raw']='/PRIVATE'
    elif fault=='extra_evidence':e['pid']=123
    elif fault=='wrong_source':e['source']='ni02b_native.v1'
    elif fault=='green_unknown':row['application_health']=e['state']='healthy'
    elif fault=='old_api':model['api_version']='admin.operations.db-services.v1'
    elif fault=='bool_age':e['age']=True
    elif fault=='huge_ttl':e['ttl']=181
    elif fault=='observed_XSS':e['observed_at']='<script>CANARY</script>'
    elif fault=='scope':model['scope']='site'
    elif fault=='attestation':model['databases'][0]['store_verification']['status']='verified'
    elif fault=='journal_as_WAL':model['databases'][0]['journal_bytes']=123
    else:model['databases'].append(copy.deepcopy(model['databases'][0]))
    with pytest.raises(ops.OperationsError):validate_v2(model)


@pytest.mark.parametrize('scenario',['valid','fallback','401','403','503','bad-reason','false-green','false-verified'])
def test_v2_javascript_safe_projection_and_no_parallel_or_unauthorized_fallback(monkeypatch,tmp_path,scenario):
    service,_,_=reader_service(monkeypatch)
    try:model=service.read('js-fixture',version=2)
    finally:service.close()
    root=Path(__file__).resolve().parents[2];path=tmp_path/'v2.json';path.write_text(json.dumps(model),encoding='utf-8')
    node=shutil.which('node');assert node
    result=subprocess.run([node,str(Path(__file__).with_name('db_services_v2_ui.cjs')),
        str(root/'app/admin_web/static/db_services.js'),str(path),scenario],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'PASS v2 truth' in result.stdout


@pytest.mark.parametrize('case',['healthy','backlog','missing','stale'])
def test_ni02_running_source_self_reported_shared_uid_is_not_independent_attestation(monkeypatch,case):
    clock=[ORIGIN];monkeypatch.setattr(ops,'boot_ns',lambda:clock[0])
    class NI02Reader(Reader):
        def read(self,*args,**kwargs):
            self.calls+=1
            if case in {'missing','stale'}:return dict(status='unknown' if case=='missing' else 'stale')
            pending=2143 if case=='backlog' else 0
            deps=dict.fromkeys(DEPENDENCIES[NI02_UNIT],True)
            if case=='backlog':deps['attribution']=False
            return dict(status='fresh',health=ni02_health('attribution_unavailable' if pending else 'usable',deps,pending),
                producer=self.producer,observed_at=ops.timestamp(NOW),age=0,expires_boottime_ns=ORIGIN+180_000_000_000)
    ni02=NI02Reader()
    service=ops.AdminOperationsReadService(resolved(),acquire=lambda c:systemd_text(),lstat=regular,now=lambda:NOW,
        sensor_metadata=Reader('missing'),ni02_health=ni02,monotonic=lambda:0)
    try:
        model=validate_v2(service.read(case,version=2))
        row=next(r for r in model['services'] if r['id']=='network_metadata_projection')
        evidence=row['application_health_evidence']
        assert row['operational_state']=='running'
        assert evidence['state']=={'healthy':'healthy','backlog':'degraded','missing':'unknown','stale':'stale'}[case]
        if case in {'healthy','backlog'}:
            assert evidence['source']=='source_self_reported_shared_uid'
            assert evidence['observed_at']==ops.timestamp(NOW)
            if case=='backlog':assert evidence['reason']=='pending_attribution'
        assert 'independently_authenticated' not in json.dumps(model)
        assert all(r['application_health']=='unknown' for r in model['services'] if r['id']!='network_metadata_projection')
        assert all(r['application_health']=='unknown' for r in service.read('legacy')['services'])
        assert ni02.calls==1
    finally:service.close()
