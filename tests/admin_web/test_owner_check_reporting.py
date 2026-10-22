"""#298 executed-owner proof, never a new verification/SQLite API path."""
from collections import Counter
import copy
from datetime import datetime,timedelta,timezone
import json
import os
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import uuid

import pytest

from app import operations_verification as v
from app.admin_web import operations_service as ops
from app.admin_web.operations_schema import validate_v2
from app.admin_web.operations_verification import OwnerChecks
from tests.admin_web.test_operations_inventory import resolved,manifest
from tests.admin_web.test_operations_service import regular,systemd_text,NOW


@pytest.fixture(autouse=True)
def isolated_check_context(monkeypatch):
    monkeypatch.setattr(v,'_rows',{});monkeypatch.setattr(v,'_paths',{})
    monkeypatch.setattr(v,'_instance',str(uuid.uuid4()));monkeypatch.setattr(v,'_pid',os.getpid())
    monkeypatch.setenv('WEB_ADMIN_DB_SERVICES_ENABLED','false')


def owner(db_id,directory):
    directory.mkdir(mode=0o750)
    path=directory/'store.sqlite3'
    args=()
    if db_id=='sensor_spool':
        from app.device_fingerprint_sensor.spool import SensorSpool
        repo=SensorSpool(str(path),total_budget_bytes=10000000,main_db_max_bytes=5000000,max_events=100)
    elif db_id=='network_attribution':
        from app.network_attribution.models import NetworkAttributionConfig
        from app.network_attribution.repository import NetworkAttributionRepository
        repo=NetworkAttributionRepository(NetworkAttributionConfig(True,str(path)))
    elif db_id=='network_metadata_projection':
        from app.network_metadata_projection.models import ProjectionConfig
        from app.network_metadata_projection.repository import ProjectionRepository
        repo=ProjectionRepository(ProjectionConfig(True,str(path)))
    elif db_id=='network_service_intelligence':
        from app.network_service_recognition.materialization_repository import ServiceMaterializationRepository
        repo=ServiceMaterializationRepository(str(path))
    elif db_id=='visits':
        from app.visit_lifecycle.config import visit_config_from_settings
        from app.visit_lifecycle.repository import VisitRepository
        repo=VisitRepository(visit_config_from_settings(dict(visit_lifecycle_enabled=True,
            visit_lifecycle_db_path=str(path),visit_lifecycle_webhook_source=str(directory/'source.log'))))
    elif db_id=='visitor_registry':
        from app.visitor_registry.registry_models import RegistryConfig
        from app.visitor_registry.registry_repository import VisitorRegistryRepository
        repo=VisitorRegistryRepository(RegistryConfig(True,str(path),str(directory/'source.log'),2,'UTC',5,20,1048576))
        args=('2026-10-22T00:00:00.000Z',)
    elif db_id=='observations':
        from app.observations.repository import ObservationRepository
        from tests.observations.conftest import make_config
        repo=ObservationRepository(make_config(directory));path=repo.db_path
    elif db_id=='current_state':
        from app.current_state.config import current_state_config_from_settings
        from app.current_state.repository import CurrentStateRepository
        repo=CurrentStateRepository(current_state_config_from_settings(dict(current_state_enabled=True,
            current_state_db_path=str(path),current_state_site_ids='a'*24,current_state_client_ssids_json='["Synthetic"]')))
    elif db_id=='traffic_projection':
        from app.traffic_projection.repository import TrafficProjectionRepository
        repo=TrafficProjectionRepository(str(path))
    elif db_id=='fingerprint_evidence':
        from app.device_fingerprint.repository import DeviceFingerprintRepository
        from tests.device_fingerprint.test_repository import provision
        provision(path);repo=DeviceFingerprintRepository(str(path),max_db_bytes=64*1024*1024)
    elif db_id=='fingerprint_integration':
        from app.device_fingerprint_integration.repository import IntegrationRepository
        repo=IntegrationRepository(path)
    elif db_id=='settings':
        from app.settings_control.repository import SettingsRepository
        repo=SettingsRepository.__new__(SettingsRepository)
        from app.settings_control.definitions import SettingsDefinitionRegistry
        repo.db_path=str(path);repo.registry=SettingsDefinitionRegistry()
    elif db_id=='network_metadata':
        from app.network_metadata.repository import NetworkMetadataRepository
        from tests.network_metadata import configuration
        repo=NetworkMetadataRepository(configuration(directory));path=Path(repo.config.db_path)
    else:raise AssertionError(db_id)
    return repo,path,args


def close(repo):
    if hasattr(repo,'close'):repo.close()
    elif isinstance(getattr(repo,'connection',None),sqlite3.Connection):repo.connection.close()


@pytest.mark.parametrize('db_id',list(v.ALLOWED))
def test_real_initialize_exact_scope_and_no_added_SQL_or_fsync(tmp_path,monkeypatch,db_id):
    connect=sqlite3.connect;traces=[]
    def traced(*args,**kwargs):
        c=connect(*args,**kwargs)
        # Existing validators build memoized in-memory schema references once;
        # compare the actual store I/O, not cold-vs-warm reference construction.
        if str(args[0])!=':memory:':c.set_trace_callback(traces.append)
        return c
    monkeypatch.setattr(sqlite3,'connect',traced)
    fsync=[]
    monkeypatch.setattr(os,'fsync',lambda *a:fsync.append(a))
    if hasattr(os,'fdatasync'):monkeypatch.setattr(os,'fdatasync',lambda *a:fsync.append(a))
    counts=[]
    for wrapped in (False,True):
        repo,path,args=owner(db_id,tmp_path/str(wrapped));traces.clear()
        try:
            method=repo.initialize
            result=method(*args) if wrapped else method.__wrapped__(repo,*args)
            counts.append(Counter(sql.split()[0] for sql in traces))
            if wrapped:
                value=v.snapshot(v.OWNERS[db_id])['checks'][db_id]
                if db_id=='current_state':
                    assert result is True and value['status']=='not_run' and value['scope']==[]
                    repo.initialize();value=v.snapshot(v.PORTAL)['checks'][db_id]
                assert value['status']=='passed' and value['scope']==list(v.ALLOWED[db_id])
                assert 'integrity_check' not in value['scope']
                assert v.parse_stamp(value['checked_at_utc'])<=datetime.now(timezone.utc)
                assert value['checked_store_id']==v.file_identity(path)
        finally:close(repo)
    assert counts[0]==counts[1],(db_id,counts)
    assert not fsync


@pytest.mark.parametrize('kind',['schema','io','before-report'])
def test_failure_replaces_prior_pass_and_does_not_leak_error_or_claim_completed_scope(tmp_path,kind):
    path=tmp_path/'db';path.write_bytes(b'disposable')
    class InvalidSchema(ValueError):pass
    class Repo:
        fail=None
        @v.startup_check('visits',lambda s:path,v.ALLOWED['visits'],failures=(InvalidSchema,))
        def initialize(self):
            if self.fail=='schema':raise InvalidSchema('/PRIVATE_TOKEN_CANARY')
            if self.fail:raise OSError('/PRIVATE_TOKEN_CANARY')
    repo=Repo();repo.initialize();assert v.snapshot(v.PORTAL)['checks']['visits']['status']=='passed'
    repo.fail=kind
    with pytest.raises((InvalidSchema,OSError)):repo.initialize()
    row=v.snapshot(v.PORTAL)['checks']['visits']
    assert row['status']==('failed' if kind=='schema' else 'unknown') and row['scope']==[]
    assert 'PRIVATE' not in json.dumps(row)


def proof(db_id='visits',*,status='passed',scope=None,at=NOW,identity='a'*64):
    return dict(status=status,scope=list(v.ALLOWED[db_id]) if scope is None else scope,
        checked_at_utc=v.stamp(at),checked_store_id=identity,observed_store_id=identity,
        reason={'passed':'startup_check','failed':'startup_check_failed','not_run':'check_not_run','unknown':'startup_unavailable'}[status])


@pytest.mark.parametrize('fault',['unknown_id','owner','scope','integrity','duplicate','bool','path','time','future','status','reason','identity'])
def test_closed_source_contract_rejects_unknown_and_overclaimed_evidence(fault):
    value=dict(instance=str(uuid.uuid4()),checks={'sensor_spool':proof('sensor_spool')})
    row=value['checks']['sensor_spool'];unit=v.SENSOR
    if fault=='unknown_id':value['checks']['secret_db']=value['checks'].pop('sensor_spool')
    elif fault=='owner':unit=v.NI02
    elif fault=='scope':row['scope']=['schema_signature']
    elif fault=='integrity':row['scope']=['integrity_check']
    elif fault=='duplicate':row['scope']=['quick_check','quick_check']
    elif fault=='bool':row['scope']=[True]
    elif fault=='path':row['path']='/PRIVATE_CANARY'
    elif fault=='time':row['checked_at_utc']='bad'
    elif fault=='future':row['checked_at_utc']=v.stamp(NOW+timedelta(seconds=1))
    elif fault=='status':row['status']='verified_forever'
    elif fault=='reason':row['reason']='PRIVATE_CANARY'
    else:row['observed_store_id']='inode-42'
    with pytest.raises((ValueError,TypeError)):v.validate_checks(value,unit,NOW)


@pytest.mark.parametrize('fault',['none','replace','restart','stop','stale','unknown','missing','failed'])
def test_projection_revokes_current_pass_for_source_or_store_change(fault):
    row=proof(status='failed' if fault=='failed' else 'passed',scope=[] if fault=='failed' else None)
    record=None if fault=='missing' else dict(row=row)
    result=v.project('visits',record,'b'*64 if fault=='replace' else 'a'*64,intent='expected',
        source_current=fault not in {'restart','stop','unknown'},stale=fault=='stale')
    v.validate_public(result,'visits')
    assert result['status']==('passed' if fault=='none' else 'failed' if fault=='failed' else 'not_attested' if fault=='missing' else 'stale')


def test_missing_checks_and_disabled_settings_do_not_create_false_FAILURE():
    assert v.project('visits',None,None,intent='expected',source_current=False)==dict(v.not_attested(),last_result=None,binding='unknown')
    value=v.project('settings',None,None,intent='optional_disabled',source_current=False)
    assert value['status']=='not_applicable';v.validate_public(value,'settings')


def test_sampler_additive_v2_retains_v1_auth_catalog_budget_and_zero_SQL(tmp_path,monkeypatch):
    from tests.admin_web.test_operations_service import SyntheticSensorMetadata
    bound=resolved();info=regular(bound.paths['visits']);identity=v.opaque_identity(info)
    row=proof(identity=identity)
    class Checks:
        calls=0
        def collect(self,*args,**kwargs):
            self.calls+=1
            return {'visits':dict(row=row,source_current=True,expires=None)}
    checks=Checks()
    def blocked(*a,**kw):raise AssertionError('SQLite/owner RPC/fsync forbidden during GET')
    monkeypatch.setattr(sqlite3,'connect',blocked);monkeypatch.setattr(os,'fsync',blocked)
    reader=ops.AdminOperationsReadService(bound,acquire=lambda c:systemd_text(),lstat=regular,
        now=lambda:NOW,monotonic=lambda:0,sensor_metadata=SyntheticSensorMetadata(bound,regular),owner_checks=checks)
    try:
        old=reader.read('old',version=1);model=validate_v2(reader.read('new',version=2))
        assert checks.calls==1 and all('store_verification' not in r for r in old['databases'])
        value=next(r for r in model['databases'] if r['id']=='visits')
        assert value['store_verification']['status']=='passed' and value['operational_state']=='present_unverified'
        assert value['health_evidence']=='none' and value['schema_observed_version'] is None
        assert [len(model[k]) for k in ('services','databases')]==[9,17]
        assert len(model['topology']['nodes'])==31 and len(model['topology']['edges'])==45
        assert len(json.dumps(model,separators=(',',':')).encode())<=48000
        raw=json.dumps(model)
        assert identity not in raw and 'checked_store_id' not in raw and '/opt/' not in raw
    finally:reader.close()


def test_sensor_only_uses_exported_identity_no_raw_Sensor_stat(tmp_path,monkeypatch):
    from tests.admin_web.test_operations_service import SyntheticSensorMetadata
    bound=resolved();sensor=bound.paths['sensor_spool'];proof_row=proof('sensor_spool')
    class Checks:
        def collect(self,*a,**kw):return {'sensor_spool':dict(row=proof_row,source_current=True,expires=None)}
    calls=[]
    def guarded(path):
        calls.append(path)
        assert not path.startswith(tuple(bound.paths[k] for k in ('sensor_spool','network_attribution')))
        return regular(path)
    reader=ops.AdminOperationsReadService(bound,acquire=lambda c:systemd_text(),lstat=guarded,
        now=lambda:NOW,sensor_metadata=SyntheticSensorMetadata(bound,regular),owner_checks=Checks())
    try:
        model=validate_v2(reader.read('request',version=2))
        value=next(r for r in model['databases'] if r['id']=='sensor_spool')
        assert value['store_verification']['status']=='passed'
    finally:reader.close()


def test_inprocess_capture_does_not_survive_fork_or_change_ownership(monkeypatch):
    v._rows['visits']=proof();v._paths['visits']='not-exported'
    old=v._instance;monkeypatch.setattr(v,'_pid',os.getpid()+1)
    assert v.snapshot(v.PORTAL)['checks']=={} and v._instance!=old
    assert v.snapshot(v.SENSOR)['checks']=={}


@pytest.mark.parametrize('db_id',['network_attribution','network_metadata_projection','network_service_intelligence'])
def test_real_failed_schema_check_is_failed_even_when_initializer_sanitizes_error(tmp_path,db_id):
    repo,path,args=owner(db_id,tmp_path/'owner');repo.initialize(*args);close(repo)
    with sqlite3.connect(path) as connection:connection.execute('PRAGMA user_version=99')
    with pytest.raises(Exception):repo.initialize(*args)
    row=v.snapshot(v.OWNERS[db_id])['checks'][db_id]
    assert row['status']=='failed' and row['scope']==[] and row['reason']=='startup_check_failed'
    close(repo)


def test_owner_collector_binds_exact_process_time_and_same_instance(monkeypatch):
    import threading
    services=[ops.service_row(s,'run',ops.parse_systemd(systemd_text())[s.unit],NOW) for s in ops.SERVICES]
    source=dict(status='fresh',producer={'pid':123},checks=dict(instance=str(uuid.uuid4()),
        checks={'sensor_spool':proof('sensor_spool')}),expires_boottime_ns=1)
    checks=OwnerChecks(readers={})
    got=checks.collect(services,source,{},NOW,deadline=2,monotonic=lambda:0,cancel=threading.Event())
    assert set(got)=={'sensor_spool'}
    for change in ({'producer':{'pid':124}},{'checks':dict(instance=str(uuid.uuid4()),checks={'visits':proof()})}):
        assert checks.collect(services,dict(source,**change),{},NOW,deadline=2,monotonic=lambda:0,cancel=threading.Event())=={}
    older=copy.deepcopy(source);older['checks']['checks']['sensor_spool']['checked_at_utc']=v.stamp(NOW-timedelta(days=1))
    assert checks.collect(services,older,{},NOW,deadline=2,monotonic=lambda:0,cancel=threading.Event())=={}


def test_report_expiration_demotes_pass_in_cached_snapshot_without_resampling(monkeypatch):
    from tests.admin_web.test_operations_service import SyntheticSensorMetadata
    bound=resolved();tick=[100000000000];monkeypatch.setattr(ops,'boot_ns',lambda:tick[0])
    class Checks:
        calls=0
        def collect(self,*a,**kw):
            self.calls+=1
            return {'visits':dict(row=proof(identity=v.opaque_identity(regular(bound.paths['visits']))),
                source_current=True,expires=tick[0]+180000000000)}
    source=Checks();reader=ops.AdminOperationsReadService(bound,acquire=lambda c:systemd_text(),lstat=regular,
        now=lambda:NOW,monotonic=lambda:0,sensor_metadata=SyntheticSensorMetadata(bound,regular),owner_checks=source)
    try:
        first=reader.read('a',version=2);tick[0]+=180000000001
        last=reader.read('b',version=2)
        before=next(r for r in first['databases'] if r['id']=='visits')['store_verification']
        after=next(r for r in last['databases'] if r['id']=='visits')['store_verification']
        assert before['status']=='passed' and after['status']=='stale' and before['as_of']==after['as_of']
        assert source.calls==1
    finally:reader.close()


@pytest.mark.parametrize('scenario',['check-passed','check-failed','check-stale','check-settings','check-bad-scope','check-bad-owner','check-raw-path'])
def test_ui_human_historical_scope_and_negative_payload_contract(tmp_path,monkeypatch,scenario):
    import shutil
    import subprocess
    from tests.admin_web.test_operations_v2 import reader_service
    reader,_,_=reader_service(monkeypatch)
    try:model=reader.read(str(uuid.uuid4()),version=2)
    finally:reader.close()
    state='failed' if scenario=='check-failed' else 'stale' if scenario=='check-stale' else 'passed'
    check=dict(status=state,scope=list(v.ALLOWED['visits']),as_of=v.stamp(NOW),source=v.PORTAL,
        freshness='stale' if state=='stale' else 'current_report',reason='source_stale' if state=='stale' else 'startup_check_failed' if state=='failed' else 'startup_check')
    next(r for r in model['databases'] if r['id']=='visits')['store_verification']=check
    if scenario=='check-settings':
        row=next(r for r in model['databases'] if r['id']=='settings');row['expected_mode']='optional_disabled'
        row['store_verification']=v.project('settings',None,None,intent='optional_disabled',source_current=False)
    validate_v2(model)
    path=tmp_path/'fixture.json';path.write_text(json.dumps(model),encoding='utf-8')
    root=Path(__file__).parents[2]
    result=subprocess.run([shutil.which('node'),str(Path(__file__).with_name('db_services_v2_ui.cjs')),
        str(root/'app/admin_web/static/db_services.js'),str(path),scenario],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr


def test_all_eligible_scopes_fit_existing_response_budget_without_claiming_all_17_checked():
    from tests.admin_web.test_operations_service import SyntheticSensorMetadata
    bound=resolved()
    class Checks:
        def collect(self,*a,**kw):return {db_id:dict(row=proof(db_id,identity=v.opaque_identity(regular(bound.paths[db_id]))),
            source_current=True,expires=None) for db_id in v.ALLOWED}
    reader=ops.AdminOperationsReadService(bound,acquire=lambda c:systemd_text(),lstat=regular,now=lambda:NOW,
        sensor_metadata=SyntheticSensorMetadata(bound,regular),owner_checks=Checks())
    try:
        model=validate_v2(reader.read(str(uuid.uuid4()),version=2))
        assert len(json.dumps(model,ensure_ascii=False,separators=(',',':')).encode())<=48000
        assert sum(row['store_verification']['status']=='passed' for row in model['databases'])==13
        assert sum(row['store_verification']['status']=='not_attested' for row in model['databases'])==4
    finally:reader.close()
