"""Closed report versions / source-process binding and bounded native delivery."""
import copy
from datetime import datetime,timedelta,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import uuid

import pytest

from app import operations_verification as v
from app import operations_verification_report as transport
from app.device_fingerprint_sensor import operations_metadata as m
from app.network_metadata_projection import operations_health as h
from app.operations_health import sensor_health,ni02_health,DEPENDENCIES
from tests.device_fingerprint_sensor.test_operations_metadata import report as sensor_report,NOW
from tests.network_metadata_projection.test_operations_health import report as ni02_report
from tests.admin_web.test_owner_check_reporting import proof,owner,close,isolated_check_context


def encoded(value):return json.dumps(value,separators=(',',':')).encode()


@pytest.mark.parametrize('unit',[v.SENSOR,v.NI02,'network-service-recognition.service'])
@pytest.mark.parametrize('fault',['none','old-schema','future','extra','owner','scope','oversize','duplicate'])
def test_new_closed_versions_are_explicit_and_legacy_versions_cannot_smuggle_checks(unit,fault):
    if unit==v.SENSOR:
        value=sensor_report();value.update(schema_version=m.SCHEMA_V3,
            application_health=sensor_health('initializing',dict.fromkeys(DEPENDENCIES[v.SENSOR],False)))
        checks={key:proof(key) for key in ('network_attribution','sensor_spool')};decoder=m.decode;old=m.SCHEMA_V2
    elif unit==v.NI02:
        value=ni02_report();value['schema_version']=h.SCHEMA_V2
        checks={'network_metadata_projection':proof('network_metadata_projection')};decoder=h.decode;old=h.SCHEMA
    else:
        value={k:val for k,val in ni02_report().items() if k in {'producer','epoch','sequence','sample_time_utc','sample_boottime_ns'}}
        value.update(schema_version=transport.SCHEMA,producer_unit=unit)
        checks={'network_service_intelligence':proof('network_service_intelligence')}
        decoder=lambda raw:transport.decode(raw,unit);old='captivprod.ops.owner-startup-check.v0'
    value['store_checks']=dict(instance=value['epoch'],checks=checks)
    first=next(iter(checks.values()))
    if fault=='old-schema':value['schema_version']=old
    elif fault=='future':first['checked_at_utc']=m.stamp(NOW+timedelta(seconds=1))
    elif fault=='extra':first['path']='/PRIVATE_CANARY'
    elif fault=='owner':value['store_checks']['checks']['settings']=proof('settings')
    elif fault=='scope':first['scope']=['integrity_check']
    raw=encoded(value)
    if fault=='oversize':raw+=b' '*4096
    elif fault=='duplicate':raw=raw[:-1]+b',"store_checks":{}}'
    if fault=='none':
        assert decoder(raw)==value and len(raw)<=4096
        assert b'checked_store_id' in raw and b'/PRIVATE' not in raw
    else:
        with pytest.raises((ValueError,TypeError)):decoder(raw)


native=pytest.mark.skipif(sys.platform!='linux' or not hasattr(os,'geteuid') or os.geteuid()!=0,
    reason='Linux root disposable tmpfs owner-check transport, no production paths')


@native
@pytest.mark.parametrize('db_id',['sensor_spool','network_metadata_projection','network_service_intelligence'])
def test_real_owner_startup_to_tmpfs_report_to_validated_history_no_SQL_or_fsync(tmp_path,monkeypatch,db_id,record_property):
    folder=Path(tempfile.mkdtemp(prefix='issue298-owner-',dir='/run'))
    repo=None
    try:
        folder.chmod(0o755);child=folder/'owner';child.mkdir();child.chmod(0o700)
        repo,path,args=owner(db_id,tmp_path/'owner');repo.initialize(*args)
        paths=None
        if db_id=='sensor_spool':
            from app.network_attribution.models import NetworkAttributionConfig
            from app.network_attribution.repository import NetworkAttributionRepository
            attribution=NetworkAttributionRepository(NetworkAttributionConfig(True,str(tmp_path/'attribution.sqlite3'))).initialize()
            attribution.close();paths={'sensor_spool':str(path),'network_attribution':str(tmp_path/'attribution.sqlite3')}
        close(repo);repo=None
        initial={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in (paths.values() if paths else [path])}
        def blocked(*a,**kw):raise AssertionError('SQLite and fsync forbidden during report/read')
        monkeypatch.setattr(sqlite3,'connect',blocked);monkeypatch.setattr(os,'fsync',blocked);monkeypatch.setattr(os,'fdatasync',blocked)
        now=lambda:datetime.now(timezone.utc)
        service=dict(operational_state='running',main_pid=os.getpid(),started_at_utc=m.stamp(now()-timedelta(seconds=30)))
        # Tests use the current Lab principal only for transport mechanics;
        # separate existing three-principal tests prove Sensor UID isolation.
        if paths:
            child.chmod(0o2750)
            parent_channel=lambda:m.Channel(os.getuid(),os.getgid(),str(folder))
            # The Sensor protocol fixes the child name, not a caller path.
            child.rename(folder/m.CHILD);child=folder/m.CHILD
            publisher=m.SensorMetadataPublisher(paths,enabled=True,channel=parent_channel,
                health_provider=lambda:sensor_health('initializing',dict.fromkeys(DEPENDENCIES[v.SENSOR],False)))
            reader=m.SensorMetadataReader(channel=parent_channel)
            do_publish=lambda:publisher.publish(threading.Event())
            expected=m.SCHEMA_V3;report=m.REPORT;decode=m.decode
        else:
            channel=lambda:h.Channel(os.getuid(),str(child))
            if db_id=='network_metadata_projection':
                publisher=h.HealthPublisher(enabled=True,channel=channel,db_path=str(path))
                reader=h.HealthReader(channel=channel)
                at=m.stamp(now())
                do_publish=lambda:publisher.publish(ni02_health('initializing',dict.fromkeys(DEPENDENCIES[v.NI02],False),None),
                    dict(source_confirmed_at=None,writer_committed_at=None,pending_observed_at=None),threading.Event())
                expected=h.SCHEMA_V2;report=h.REPORT;decode=h.decode
            else:
                unit=v.OWNERS[db_id];reader=transport.Reader(unit,channel=lambda unit:channel())
                do_publish=lambda:transport.publish_startup(unit,channel=lambda unit:channel())
                expected=transport.SCHEMA;report=transport.REPORT;decode=lambda raw:transport.decode(raw,unit)
        def io():
            return {key:int(value) for key,value in (line.split(':',1) for line in Path('/proc/self/io').read_text().splitlines())}
        before=io();tick=time.monotonic();assert do_publish();elapsed=time.monotonic()-tick;after=io()
        assert after['write_bytes']==before['write_bytes']
        raw=(child/report).read_bytes();value=decode(raw)
        assert value['schema_version']==expected and len(raw)<=4096
        result=reader.read(service,now(),deadline=time.monotonic()+1)
        assert result['status']=='fresh' and result['checks']['checks'][db_id]['status']=='passed'
        row=result['checks']['checks'][db_id]
        public=v.project(db_id,dict(row=row),row['observed_store_id'],intent='expected',source_current=True)
        assert public['status']=='passed' and public['as_of']==row['checked_at_utc'];v.validate_public(public,db_id)
        assert {p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in initial}==initial
        service['main_pid']+=999999
        assert reader.read(service,now(),deadline=time.monotonic()+1)['status']=='unknown'
        record_property('owner_check_tmpfs',json.dumps(dict(db_id=db_id,bytes=len(raw),publish_seconds=elapsed,
            write_bytes_delta=after['write_bytes']-before['write_bytes'],extra_SQL=0,fsync=0)))
    finally:
        if repo is not None:close(repo)
        # Exact test-owned temp root, never a deployment directory.
        assert folder.parent==Path('/run') and folder.name.startswith('issue298-owner-')
        shutil.rmtree(folder)
