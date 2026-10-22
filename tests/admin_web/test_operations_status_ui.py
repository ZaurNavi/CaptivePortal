"""Issue 298: endpoint conditions are not live flow/integrity measurements."""
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
from datetime import timedelta
from types import SimpleNamespace
import threading
import uuid

import pytest

from app import operations_verification as v
from app.admin_web import operations_service as ops
from app.admin_web.operations_schema import validate_v2
from tests.admin_web.test_operations_inventory import resolved
from tests.admin_web.test_operations_service import NOW, regular, systemd_text, SyntheticSensorMetadata
from tests.admin_web.test_operations_v2 import reader_service
from tests.admin_web.test_owner_check_reporting import proof


@pytest.mark.parametrize('mismatch', ['none','pid','boot','start_ticks'])
def test_stale_report_reader_validates_process_incarnation_before_retaining_result(monkeypatch,mismatch):
    """Exercise the unchanged Reader and collector on both platforms, no I/O."""
    from app import operations_verification_report as transport
    from app.admin_web.operations_verification import OwnerChecks
    unit=v.OWNERS['network_metadata'];producer=dict(pid=123,boot_id=str(uuid.uuid4()),start_ticks=100)
    instance=str(uuid.uuid4());at=NOW-timedelta(seconds=300)
    body=dict(schema_version=transport.SCHEMA,producer_unit=unit,producer=producer,epoch=instance,sequence=1,
        sample_time_utc=v.stamp(at),sample_boottime_ns=5_000_000_000,
        store_checks=dict(instance=instance,checks={'network_metadata':proof('network_metadata',at=at)}))
    raw=json.dumps(body).encode()
    info=SimpleNamespace(st_dev=1,st_ino=2,st_size=len(raw),st_mtime_ns=1,st_ctime_ns=1)
    closed=[]
    fake_os=SimpleNamespace(O_RDONLY=0,O_NOFOLLOW=0,O_NONBLOCK=0,O_CLOEXEC=0,
        open=lambda *a,**kw:102,fstat=lambda fd:info,stat=lambda *a,**kw:info,
        read=lambda *a:raw,close=closed.append,sysconf=lambda key:100)
    monkeypatch.setattr(transport,'os',fake_os)
    class Channel:
        uid=1000
        def open(self):return 101
        def validate_file(self,info):pass
    actual=dict(producer)
    if mismatch=='pid':actual['pid']+=1
    if mismatch=='boot':actual['boot_id']=str(uuid.uuid4())
    if mismatch=='start_ticks':actual['start_ticks']+=1
    reader=transport.Reader(unit,channel=lambda unit:Channel(),identity=lambda pid,uid:actual,
        boottime=lambda:305_000_000_000)
    services=[ops.service_row(s,'run',ops.parse_systemd(systemd_text())[s.unit],NOW) for s in ops.SERVICES]
    records=OwnerChecks(readers={unit:reader}).collect(services,{}, {},NOW,deadline=1,
        monotonic=lambda:0,cancel=threading.Event())
    record=records.get('network_metadata')
    value=v.project('network_metadata',record,'a'*64,intent='expected',source_current=False,stale=True)
    if mismatch=='none':
        assert record['source_current'] is False
        assert value['status']=='stale' and value['last_result']=='passed' and value['binding']=='matched'
    else:
        assert record is None and value['last_result'] is None and value['binding']=='unknown'
    assert closed==[102,101]
    v.validate_public(value,'network_metadata')


@pytest.mark.parametrize('result', ['passed', 'failed', 'unknown', 'not_run'])
@pytest.mark.parametrize('binding', ['matched', 'changed', 'unknown'])
@pytest.mark.parametrize('ttl', [False, True])
def test_original_result_and_binding_are_independent_of_report_ttl(result, binding, ttl):
    row=proof(status=result, scope=[] if result!='passed' else None)
    if result=='not_run':row['checked_at_utc']=None
    current={'matched':'a'*64,'changed':'b'*64,'unknown':None}[binding]
    record=dict(row=row)
    value=v.project('visits',record,current,intent='expected',source_current=not ttl,stale=ttl)
    assert value['last_result']==result and value['binding']==binding
    assert value['scope']==(None if result=='not_run' else row['scope'] or None)
    v.validate_public(value,'visits')
    # The original six-field projection is byte-equivalent to its legacy form.
    original={key:item for key,item in value.items() if key not in {'last_result','binding'}}
    assert v.validate_public(original,'visits')==original


@pytest.mark.parametrize('db_id', ['visits','sensor_spool'])
def test_entire_sampler_staleness_drops_binding_not_historical_result(db_id):
    value=v.project(db_id,dict(row=proof(db_id)), 'a'*64,intent='expected',
        source_current=True,stale=True,binding_current=False)
    assert value['status']=='stale' and value['last_result']=='passed' and value['binding']=='unknown'
    v.validate_public(value,db_id)


@pytest.mark.parametrize('sensor', [False, True])
def test_ttl_only_keeps_lstat_binding_but_never_self_attests_stale_sensor(monkeypatch,sensor):
    bound=resolved();tick=[100_000_000_000];monkeypatch.setattr(ops,'boot_ns',lambda:tick[0])
    identity='sensor_spool' if sensor else 'visits'
    row=proof(identity,identity=v.opaque_identity(regular(bound.paths[identity])))
    class Checks:
        calls=0
        def collect(self,*args,**kwargs):
            self.calls+=1
            return {identity:dict(row=row,source_current=True,expires=tick[0]+1_000_000_000)}
    checks=Checks();calls=[]
    def lstat(path):
        assert not path.startswith(tuple(bound.paths[k] for k in ('sensor_spool','network_attribution')))
        calls.append(path);return regular(path)
    def forbidden(*args,**kwargs):raise AssertionError('No SQLite for UI projection')
    monkeypatch.setattr(sqlite3,'connect',forbidden)
    service=ops.AdminOperationsReadService(bound,acquire=lambda c:systemd_text(),lstat=lstat,
        now=lambda:NOW,monotonic=lambda:0,sensor_metadata=SyntheticSensorMetadata(bound,regular),owner_checks=checks)
    try:
        before=validate_v2(service.read('before',version=2));count=len(calls)
        tick[0]+=1_000_000_001
        after=validate_v2(service.read('after',version=2))
        check=lambda model:next(r for r in model['databases'] if r['id']==identity)['store_verification']
        assert check(before)['status']=='passed' and check(before)['binding']=='matched'
        assert check(after)['status']=='stale' and check(after)['reason']=='source_stale'
        assert check(after)['last_result']=='passed'
        assert check(after)['binding']==('unknown' if sensor else 'matched')
        assert checks.calls==1 and len(calls)==count
    finally:service.close()


@pytest.mark.parametrize('fault', ['partial-result','partial-binding','bad-result','bad-binding','extra',
    'passed-failed','passed-unbound','failed-passed','changed-matched','unknown-passed','missing-pass','disabled-null-matched'])
def test_public_extension_rejects_partial_inconsistent_or_overclaimed_forms(fault):
    value=v.project('visits',dict(row=proof()),'a'*64,intent='expected',source_current=True)
    identity='visits'
    if fault=='partial-result':value.pop('last_result')
    elif fault=='partial-binding':value.pop('binding')
    elif fault=='bad-result':value['last_result']=True
    elif fault=='bad-binding':value['binding']=None
    elif fault=='extra':value['store_id']='PRIVATE'
    elif fault=='passed-failed':value['last_result']='failed'
    elif fault=='passed-unbound':value['binding']='unknown'
    elif fault=='failed-passed':value.update(status='failed',reason='startup_check_failed')
    elif fault=='changed-matched':value.update(status='stale',freshness='stale',reason='store_changed')
    elif fault=='unknown-passed':value.update(status='unknown',reason='startup_unavailable')
    elif fault=='missing-pass':value=dict(v.not_attested(),last_result='passed',binding='matched')
    else:
        identity='settings'
        value=v.project(identity,None,None,intent='optional_disabled',source_current=False)
        value['binding']='matched'
    with pytest.raises(ValueError):v.validate_public(value,identity)


def test_disabled_settings_does_not_erase_an_actual_validated_prior_result():
    value=v.project('settings',dict(row=proof('settings')),'a'*64,intent='optional_disabled',source_current=True)
    assert value==dict(status='not_applicable',scope=None,as_of=None,source='none',freshness='not_applicable',
        reason='configured_disabled',last_result='passed',binding='matched')
    v.validate_public(value,'settings')


def status_fixture(monkeypatch,scenario):
    service,_,_=reader_service(monkeypatch)
    try:model=service.read('synthetic-ui',version=2)
    finally:service.close()
    row=next(r for r in model['databases'] if r['id']=='visits')
    owner=next(s for s in model['services'] if s['id']=='portal_core')
    row['store_verification']=v.project('visits',dict(row=proof()),'a'*64,intent='expected',source_current=True)
    expected='operating'
    if scenario=='ttl-pass':row['store_verification'].update(status='stale',freshness='stale',reason='source_stale')
    elif scenario.startswith('failed-'):
        binding=scenario.split('-')[1]
        row['store_verification']=v.project('visits',dict(row=proof(status='failed',scope=[])),
            'a'*64 if binding=='matched' else 'b'*64 if binding=='changed' else None,intent='expected',source_current=False,stale=True)
        expected='failed' if binding=='matched' else 'unknown'
    elif scenario=='changed':
        row['store_verification'].update(status='stale',freshness='stale',reason='store_changed',binding='changed');expected='unknown'
    elif scenario=='legacy':
        row['store_verification']={k:i for k,i in row['store_verification'].items() if k not in {'last_result','binding'}};expected='unknown'
    elif scenario=='missing-proof':row['store_verification']=v.not_attested();expected='unknown'
    elif scenario=='sampler-stale':model['sample_status']='stale';expected='unknown'
    elif scenario=='sample-unknown':model['sample_status']='unknown';expected='unknown'
    elif scenario=='metadata-unknown':row['metadata_evidence']['state']='unknown';expected='unknown'
    elif scenario=='degraded':owner['application_health']=owner['application_health_evidence']['state']='degraded';expected='degraded'
    elif scenario=='app-degraded-running':
        row=next(r for r in model['databases'] if r['id']=='sensor_spool')
        row['store_verification']=v.project('sensor_spool',dict(row=proof('sensor_spool')),'a'*64,intent='expected',source_current=True)
        owner=next(s for s in model['services'] if s['id']=='fingerprint_sensor')
        owner['application_health']=owner['application_health_evidence']['state']='degraded'
        owner['application_health_evidence']['reason']='source_degraded';expected='degraded'
    elif scenario=='owner-failed':owner['operational_state']='failed';expected='failed'
    elif scenario=='owner-stopped':owner['operational_state']='stopped';expected='unknown'
    elif scenario=='unsafe':row.update(operational_state='unknown',file_presence='unknown',reason_code='symlink_file');expected='failed'
    elif scenario=='absent':row.update(operational_state='unavailable',file_presence='absent',reason_code='file_missing');expected='failed'
    elif scenario=='permission':row.update(operational_state='unknown',file_presence='unknown',reason_code='metadata_permission_boundary');expected='unknown'
    elif scenario=='disabled':row.update(operational_state='disabled',expected_mode='optional_disabled');expected='unknown'
    elif scenario=='disabled-settings-proof':
        row=next(r for r in model['databases'] if r['id']=='settings')
        row.update(operational_state='disabled',expected_mode='optional_disabled')
        row['store_verification']=v.project('settings',dict(row=proof('settings')),'a'*64,
            intent='optional_disabled',source_current=True);expected='unknown'
    elif scenario=='invalid-partial':row['store_verification'].pop('binding');expected='reject'
    elif scenario=='invalid-overclaim':row['store_verification']['last_result']='failed';expected='reject'
    elif scenario=='invalid-extra':row['store_verification']['path']='/PRIVATE';expected='reject'
    elif scenario=='invalid-legacy':row['store_verification'].pop('last_result');expected='reject'
    elif scenario=='invalid-result-type':row['store_verification']['last_result']=True;expected='reject'
    elif scenario=='invalid-binding':row['store_verification']['binding']=None;expected='reject'
    elif scenario=='invalid-changed':row['store_verification'].update(status='stale',freshness='stale',reason='store_changed');expected='reject'
    elif scenario=='invalid-unknown':row['store_verification'].update(status='unknown',reason='startup_unavailable');expected='reject'
    return model,expected


@pytest.mark.parametrize('scenario', ['passed','ttl-pass','failed-matched','failed-changed','failed-unknown',
    'changed','legacy','missing-proof','sampler-stale','sample-unknown','metadata-unknown','degraded','app-degraded-running','owner-failed','owner-stopped','unsafe',
    'absent','permission','disabled','disabled-settings-proof','invalid-partial','invalid-overclaim','invalid-extra','invalid-legacy',
    'invalid-result-type','invalid-binding','invalid-changed','invalid-unknown'])
def test_ui_operational_truth_table_and_problem_toggle(monkeypatch,tmp_path,scenario):
    model,expected=status_fixture(monkeypatch,scenario)
    # Scenario-specific app-state display checks deliberately use a synthetic
    # evidence producer in Node; no real source is authenticated by this fixture.
    if scenario=='degraded':
        owner=next(s for s in model['services'] if s['id']=='portal_core')
        owner['operational_state']='degraded'
        owner['application_health']=owner['application_health_evidence']['state']='unknown'
    fixture=tmp_path/'snapshot.json';fixture.write_text(json.dumps(model),encoding='utf-8')
    root=Path(__file__).parents[2]
    result=subprocess.run([shutil.which('node'),str(Path(__file__).with_name('operations_status_ui.cjs')),
        str(root/'app/admin_web/static/db_services.js'),str(fixture),expected,scenario],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
