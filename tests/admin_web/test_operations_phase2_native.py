"""Closed native Phase2 versions and existing owner cadence, no DB reads."""
import copy
import os
import pytest
from app import operations_app_health as h
from app.operations_health import NI04_UNIT,CLASSIFICATION_UNIT,TRAFFIC_UNIT,owner_health
from tests.test_operations_app_health import report,raw,TestChannel,NOW,reader_for,write_report

UNITS=(NI04_UNIT,CLASSIFICATION_UNIT,TRAFFIC_UNIT)


@pytest.mark.parametrize('unit',UNITS)
@pytest.mark.parametrize('count',[None,0,1])
def test_phase2_native_versions_closed_and_legacy_accepted(unit,count):
    workload=h.phase2_workload(unit)
    if unit==NI04_UNIT:workload['visit_outbox_unacked']=count
    elif unit==CLASSIFICATION_UNIT:workload.update(integration_jobs_pending=count,integration_jobs_leased=count)
    else:workload['incremental_backlog_present']=count
    value=dict(report(unit),schema_version=h.SCHEMA_V3 if unit==NI04_UNIT else h.SCHEMA_V2,workload=workload)
    if unit==CLASSIFICATION_UNIT:
        with pytest.raises(ValueError):h.decode(raw(value),unit)
    else:assert h.decode(raw(value),unit)==value
    assert h.decode(raw(report(unit)),unit)==report(unit)


@pytest.mark.parametrize('unit',UNITS)
@pytest.mark.parametrize('fault',['bool','negative','float','overflow','text','extra','missing','wrong-version','wrong-unit','null-object'])
def test_phase2_native_rejects_unbounded_or_foreign_payload(unit,fault):
    workload=h.phase2_workload(unit)
    field=next(k for k in workload if k!='feed_backlog_entries')
    bad=dict(bool=True,negative=-1,float=1.0,overflow=2**53,text='1')
    if fault in bad:workload[field]=bad[fault]
    elif fault=='extra':workload['PRIVATE']=1
    elif fault=='missing':workload.pop(field)
    value=dict(report(unit),schema_version=h.SCHEMA_V3 if unit==NI04_UNIT else h.SCHEMA_V2,workload=workload)
    if fault=='wrong-version':value['schema_version']=h.SCHEMA if unit!=NI04_UNIT else h.SCHEMA_V2
    elif fault=='wrong-unit':value['producer_unit']='PRIVATE'
    elif fault=='null-object':value['workload']=None
    with pytest.raises(ValueError):h.decode(raw(value),unit)


@pytest.mark.skipif(os.name!='posix',reason='Linux/POSIX owner report openat contract')
@pytest.mark.parametrize('unit',UNITS)
def test_workload_changes_do_not_amplify_reports_or_read_sql(tmp_path,monkeypatch,unit):
    import sqlite3
    monkeypatch.setattr(sqlite3,'connect',lambda *a,**k:pytest.fail('report SQL forbidden'))
    tick=[0];writes=[];providers=[];original=h.os.replace
    def replace(*args,**kwargs):writes.append(tick[0]);return original(*args,**kwargs)
    monkeypatch.setattr(h.os,'replace',replace)
    def workload():
        providers.append(tick[0]);v=h.phase2_workload(unit)
        if unit==NI04_UNIT:v['visit_outbox_unacked']=tick[0]
        elif unit==TRAFFIC_UNIT:v['incremental_backlog_present']=tick[0]%2
        return v
    p=h.HealthPublisher(unit,enabled=True,channel=lambda u:TestChannel(tmp_path),monotonic=lambda:tick[0],
        now=lambda:NOW,boottime=lambda:100_000_000_000,identity=lambda pid,uid:dict(report(unit)['producer'],pid=pid),
        interval=55 if unit==TRAFFIC_UNIT else 60,workload_provider=workload)
    health=owner_health(unit,'ready' if unit==CLASSIFICATION_UNIT else 'usable')
    for second in range(121):
        tick[0]=second;p.publish(health)
        assert p.last_health==health and 'workload' not in p.last_health
    expected=[0,55,110] if unit==TRAFFIC_UNIT else [0,60,120]
    assert writes==expected
    value=h.decode((tmp_path/h.REPORT).read_bytes(),unit)
    if unit==CLASSIFICATION_UNIT:
        assert providers==[] and p.workload_provider is None
        assert value['schema_version']==h.SCHEMA and 'workload' not in value
    else:
        assert providers==expected
        assert value['workload']==workload()


@pytest.mark.skipif(os.name!='posix',reason='Linux/POSIX owner native openat report contract')
@pytest.mark.parametrize('fault',['valid','stale','pid','start','boot','sequence','before-start'])
@pytest.mark.parametrize('unit',UNITS)
def test_native_v3_same_reader_enforces_incarnation_without_extra_read(tmp_path,monkeypatch,fault,unit):
    from datetime import timedelta
    value=report(unit)
    if unit==CLASSIFICATION_UNIT:value['application_health']=owner_health(unit,'ready')
    elif unit==NI04_UNIT:value.update(schema_version=h.SCHEMA_V3,workload=dict(feed_backlog_entries=None,visit_outbox_unacked=7))
    else:value.update(schema_version=h.SCHEMA_V2,workload=dict(incremental_backlog_present=1))
    path,reader,service=reader_for(tmp_path,value,identity=lambda pid,uid:report(unit)['producer'])
    reader.unit=unit  # Reuse disposable fixture, not the NI04-only admission seam.
    calls=[];original=h.os.read
    def read(*args):calls.append(1);return original(*args)
    monkeypatch.setattr(h.os,'read',read)
    first=reader.read(service,NOW,deadline=1,monotonic=lambda:0)
    assert first['status']=='fresh' and first['health']==value['application_health'] and calls==[1]
    assert ('workload' in first)==(unit!=CLASSIFICATION_UNIT)
    if unit!=CLASSIFICATION_UNIT:assert first['workload']==value['workload']
    value=copy.deepcopy(value);now=NOW
    if fault=='stale':
        value['sequence']+=1;value['sample_boottime_ns']+=1_000_000_000
        value['sample_time_utc']=h.m.stamp(NOW+timedelta(seconds=1));reader.boottime=lambda:282_000_000_000
        now=NOW+timedelta(seconds=182)
    elif fault=='pid':value['producer']['pid']+=1
    elif fault=='start':value['producer']['start_ticks']+=1
    elif fault=='boot':value['producer']['boot_id']='00000000-0000-0000-0000-000000000001'
    elif fault=='sequence':value['sequence']-=1
    elif fault=='before-start':value['sample_time_utc']='2000-01-01T00:00:00.000Z'
    else:value['sequence']+=1
    write_report(path,value)
    second=reader.read(service,now,deadline=1,monotonic=lambda:0)
    assert (second['status']=='fresh')==(fault=='valid')
    if fault!='valid':assert 'workload' not in second


@pytest.mark.parametrize('schema',[h.SCHEMA,h.SCHEMA_V2,h.SCHEMA_V3])
@pytest.mark.parametrize('workload',[None,{},dict(integration_jobs_pending=None,integration_jobs_leased=None),
    dict(integration_jobs_pending=0,integration_jobs_leased=0),
    dict(integration_jobs_pending=7,integration_jobs_leased=1)])
def test_classification_native_is_v1_only_and_never_accepts_workload(schema,workload):
    value=dict(report(CLASSIFICATION_UNIT),schema_version=schema,
        application_health=owner_health(CLASSIFICATION_UNIT,'ready'))
    if workload is not None:value['workload']=workload
    if schema==h.SCHEMA and workload is None:
        assert h.decode(raw(value),CLASSIFICATION_UNIT)==value
    else:
        with pytest.raises(ValueError):h.decode(raw(value),CLASSIFICATION_UNIT)


@pytest.mark.skipif(os.name!='posix',reason='Linux/POSIX owner native openat report contract')
@pytest.mark.parametrize('schema',[h.SCHEMA_V2,h.SCHEMA_V3])
def test_invalid_extended_classification_cannot_replace_valid_v1_health(tmp_path,schema):
    value=report(CLASSIFICATION_UNIT)
    value['application_health']=owner_health(CLASSIFICATION_UNIT,'ready')
    path,reader,service=reader_for(tmp_path,value,identity=lambda pid,uid:value['producer'])
    reader.unit=CLASSIFICATION_UNIT
    first=reader.read(service,NOW,deadline=1,monotonic=lambda:0)
    assert first['status']=='fresh' and first['health']['state']=='healthy' and 'workload' not in first
    forged=dict(value,schema_version=schema,sequence=2,
        workload=dict(integration_jobs_pending=7,integration_jobs_leased=1))
    write_report(path,forged)
    assert reader.read(service,NOW,deadline=1,monotonic=lambda:0)==dict(status='unknown',reason='report_unavailable')


@pytest.mark.skipif(os.name!='posix',reason='Linux/POSIX owner native openat report contract')
def test_classification_v1_sigterm_restart_keeps_health_and_never_adds_workload(tmp_path):
    import subprocess
    import sys
    import time
    from datetime import datetime,timezone,timedelta
    program='''
import sys,time
from pathlib import Path
from app import operations_app_health as h
from app.operations_health import CLASSIFICATION_UNIT,owner_health
from tests.test_operations_app_health import TestChannel
p=h.HealthPublisher(CLASSIFICATION_UNIT,enabled=True,channel=lambda unit:TestChannel(Path(sys.argv[1])),
    workload_provider=lambda:(_ for _ in ()).throw(AssertionError('Classification provider forbidden')))
assert p.publish(owner_health(CLASSIFICATION_UNIT,'ready'))
time.sleep(60)
'''
    reader=h.HealthReader(CLASSIFICATION_UNIT,channel=lambda unit:TestChannel(tmp_path))
    children=[]
    try:
        previous=None
        for _ in range(2):
            child=subprocess.Popen([sys.executable,'-c',program,str(tmp_path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            children.append(child)
            service=dict(operational_state='running',main_pid=child.pid,
                started_at_utc=h.m.stamp(datetime.now(timezone.utc)-timedelta(seconds=1)))
            end=time.monotonic()+5
            while True:
                result=reader.read(service,datetime.now(timezone.utc),deadline=time.monotonic()+1)
                if result['status']=='fresh':break
                assert child.poll() is None,child.communicate()[1]
                assert time.monotonic()<end,result
                time.sleep(0.01)
            value=h.decode((tmp_path/h.REPORT).read_bytes(),CLASSIFICATION_UNIT)
            assert value['schema_version']==h.SCHEMA and 'workload' not in value and 'workload' not in result
            assert result['health']==owner_health(CLASSIFICATION_UNIT,'ready')
            if previous is not None:
                assert value['producer']['pid']!=previous['producer']['pid'] and value['epoch']!=previous['epoch']
                assert value['sequence']==1
            previous=value
            child.terminate();child.wait(timeout=5)
            service['operational_state']='stopped'
            assert reader.read(service,datetime.now(timezone.utc),deadline=time.monotonic()+1)==dict(status='unknown',reason='report_unavailable')
    finally:
        for child in children:
            if child.poll() is None:
                child.kill();child.wait(timeout=5)
            child.communicate(timeout=5)
