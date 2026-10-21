"""#295 informational NI02B reporting; only existing precomputed state."""
import copy
import json
from collections import Counter
from datetime import timedelta
from types import SimpleNamespace
import threading

import pytest

from app.network_metadata_projection import operations_health as h
from app.operations_health import NI02_UNIT, DEPENDENCIES, ni02_health
from app.device_fingerprint_sensor.operations_metadata import stamp
from tests.device_fingerprint_sensor.test_operations_metadata import report as sensor_report, NOW
from .support import stack


def report():
    original=sensor_report()
    return {k:copy.deepcopy(original[k]) for k in ('producer','epoch','sequence','sample_time_utc','sample_boottime_ns')} | dict(
        schema_version=h.SCHEMA,producer_unit=NI02_UNIT,provenance=h.PROVENANCE,
        application_health=ni02_health('usable',dict.fromkeys(DEPENDENCIES[NI02_UNIT],True),0),
        source_confirmed_at=stamp(NOW),writer_committed_at=stamp(NOW),pending_observed_at=stamp(NOW))


def raw(value):return json.dumps(value,separators=(',',':')).encode()


def test_closed_self_reported_contract_never_claims_independent_authentication():
    value=report()
    assert h.decode(raw(value))==value and len(raw(value))<=4096
    assert value['provenance']=='source_self_reported_shared_uid'
    assert not any(x in raw(value) for x in (b'/var/',b'device_id',b'client_mac',b'Authorization',b'independently_authenticated'))


@pytest.mark.parametrize('fault',['schema','unit','provenance','extra','duplicate','bad-json','oversize',
    'green_no_source','pending_unknown','pending_old','pending_bool','time_future','epoch','sequence','pid','reason'])
def test_malformed_unfresh_and_overclaim_reports_are_rejected(fault):
    value=report()
    if fault in {'schema','unit','provenance'}:value[{'schema':'schema_version','unit':'producer_unit','provenance':'provenance'}[fault]]='independently_authenticated'
    elif fault=='extra':value['raw_path']='/PRIVATE_CANARY'
    elif fault=='green_no_source':value['source_confirmed_at']=None
    elif fault=='pending_unknown':value['application_health']['pending_count']=None
    elif fault=='pending_old':value['pending_observed_at']=stamp(NOW-timedelta(seconds=181))
    elif fault=='pending_bool':value['application_health']['pending_count']=True
    elif fault=='time_future':value['source_confirmed_at']=stamp(NOW+timedelta(seconds=1))
    elif fault=='epoch':value['epoch']='CANARY'
    elif fault=='sequence':value['sequence']=True
    elif fault=='pid':value['producer']['pid']=False
    elif fault=='reason':value['application_health']['reason']='RAW_ERROR'
    data=raw(value)
    if fault=='duplicate':data=data[:-1]+b',"sequence":1}'
    elif fault=='bad-json':data=b'{'
    elif fault=='oversize':data=b' '*4097
    with pytest.raises((ValueError,TypeError)):h.decode(data)


@pytest.mark.parametrize('flag',[False,True])
def test_source_poll_retry_and_report_do_not_add_health_SQL_or_transactions(tmp_path,flag):
    value=stack(tmp_path);service=value.service;captured=[]
    service._operations_publisher=SimpleNamespace(enabled=flag,publish=lambda *args:captured.append(args))
    service.monotonic=lambda:100
    try:
        service.poll();service.retry()
        sql=[];value.repo.connection.set_trace_callback(sql.append)
        service._publish_operations_health()
        assert sql==[], 'health must consume memory, never issue a SQL probe'
        assert len(captured)==int(flag)
        if flag:
            health,times,stop=captured[0]
            assert health['state']=='healthy' and health['pending_count']==0
            assert health['dependencies']==dict.fromkeys(DEPENDENCIES[NI02_UNIT],True)
            assert times['source_confirmed_at'] is not None and times['writer_committed_at'] is not None
    finally:value.repo.close()


def test_enable_observer_does_not_change_poll_or_retry_SQL_trace_counts(tmp_path):
    traces=[]
    for enabled in (False,True):
        directory=tmp_path/str(enabled);directory.mkdir();value=stack(directory)
        value.service._operations_publisher=SimpleNamespace(enabled=enabled)
        trace=[];value.repo.connection.set_trace_callback(trace.append)
        try:
            value.service.poll();value.service.retry()
            traces.append(Counter(statement.split()[0] for statement in trace))
        finally:value.repo.close()
    assert traces[0]==traces[1]


@pytest.mark.parametrize('case',['backlog','source_error','no_source','stale_source','no_pending','write_error'])
def test_native_degraded_missing_and_failure_never_become_healthy(tmp_path,case):
    value=stack(tmp_path);service=value.service;captured=[];tick=[100]
    service.monotonic=lambda:tick[0]
    service._operations_publisher=SimpleNamespace(enabled=True,publish=lambda *args:captured.append(args))
    try:
        if case=='backlog':value.attribution.states={'10.73.0.7':'unavailable'}
        if case!='no_source':service.poll()
        if case!='no_pending':service.retry()
        if case=='source_error':
            value.source.fail=True;service.poll()
        if case=='stale_source':tick[0]+=31
        if case=='write_error':service.emit('projection_unavailable',reason_code='projection_store_unavailable')
        sql=[];value.repo.connection.set_trace_callback(sql.append)
        service._publish_operations_health();assert sql==[]
        health=captured[-1][0]
        assert health['state']!='healthy'
        if case=='backlog':assert health['state']=='degraded' and health['reason']=='pending_attribution' and health['pending_count']==1
        if case=='source_error':assert health['state']=='unavailable'
        if case=='stale_source':assert health['state']=='unknown' and health['reason']=='source_poll_stale'
    finally:value.repo.close()


def test_publisher_OFF_or_stopped_does_no_channel_work_and_freezes_startup_flag(monkeypatch):
    calls=[]
    def forbidden():calls.append(1);raise AssertionError('no channel')
    monkeypatch.setenv('WEB_ADMIN_DB_SERVICES_ENABLED','false')
    publisher=h.HealthPublisher(channel=forbidden)
    monkeypatch.setenv('WEB_ADMIN_DB_SERVICES_ENABLED','true')
    assert not publisher.publish({}, {}, threading.Event()) and calls==[]
    publisher=h.HealthPublisher(channel=forbidden,enabled=True);stop=threading.Event();stop.set()
    assert not publisher.publish({}, {}, stop) and calls==[]


def test_missing_channel_is_rate_limited_without_retry_or_worker_error():
    tick=[0];calls=[]
    def missing():calls.append(1);raise FileNotFoundError()
    publisher=h.HealthPublisher(channel=missing,enabled=True,monotonic=lambda:tick[0])
    for moment in (0,1,59.9,60):
        tick[0]=moment;assert not publisher.publish({}, {}, threading.Event())
    assert calls==[1,1]
