"""Partial-foundation tests only; not worker/security or overall TASK acceptance."""
import json
import os
from dataclasses import replace
import uuid
from types import MappingProxyType
import pytest
from app.admin_web.operations_inventory import Inventory, SERVICES, STORES
from app.unified_sqlite_audit.model import AdmittedStore, catalog, project, stamp
from app.unified_sqlite_audit.preflight import prepare


def forbidden(*args,**kwargs):
    pytest.fail('Unqualified preflight must not access a source or owner evidence')


def bindings():
    return Inventory(MappingProxyType({s.id:'run' for s in SERVICES}),
        MappingProxyType({s.id:'expected' for s in STORES}),
        MappingProxyType({s.id:'/opt/CaptivePortal/data/'+s.filename for s in STORES}))


def test_off_has_no_inventory_owner_metadata_or_SQL_side_effect(monkeypatch):
    import sqlite3
    monkeypatch.setattr(sqlite3,'connect',forbidden)
    value,admitted,inventory=prepare(False,None,inventory_loader=forbidden,lstat=forbidden,owner_snapshot=forbidden)
    status=project(value)
    assert status['cycle_state']=='DISABLED' and len(status['stores'])==17
    assert admitted=={} and inventory is None
    assert status['summary']['evaluated']==0


@pytest.mark.parametrize('error',[FileNotFoundError,ValueError,PermissionError])
def test_on_unavailable_manifest_has_all_17_unknown_entries_and_zero_source_access(monkeypatch,error):
    import sqlite3
    monkeypatch.setattr(sqlite3,'connect',forbidden)
    def unavailable():raise error()
    value,admitted,inventory=prepare(True,None,inventory_loader=unavailable,lstat=forbidden,owner_snapshot=forbidden)
    status=project(value)
    assert status['cycle_state']=='BLOCKED_NO_TRUSTED_BINDINGS'
    assert status['phase1']=='UNAVAILABLE' and admitted=={} and inventory is None
    assert [r['store_id'] for r in status['stores']]==[s.id for s in STORES]
    assert status['summary']['bound']==status['summary']['evaluated']==0
    assert status['summary']['eligible_physical_count'] is None
    assert status['summary']['physical_coverage_complete'] is None
    assert all(row['effective_path_identity'] is None and row['effective_enabled'] is None for row in status['stores'])
    assert '/opt/' not in json.dumps(status)


def test_valid_manifest_alone_never_authorizes_source_access(monkeypatch):
    import sqlite3
    monkeypatch.setattr(sqlite3,'connect',forbidden)
    observed=[]
    def evidence(unit,**kwargs):observed.append((unit,kwargs));return {'checks':{}}
    value,admitted,inventory=prepare(True,None,inventory_loader=bindings,lstat=forbidden,owner_snapshot=evidence)
    status=project(value)
    assert len(observed)==1 and observed[0][1]=={'refresh':False}
    assert admitted=={} and inventory is not None
    assert status['summary']['bound']==17 and status['summary']['eligible_physical_count']==0
    assert all(r['admission']=='NOT_ADMITTED' and r['effective_path_identity'] is None and r['effective_enabled'] is None for r in status['stores'])


def test_projection_has_independent_physical_and_domain_denominators_without_forged_success():
    value=catalog(True,bound=True,portal_run_id=str(uuid.uuid4()))
    row=value['stores'][0]
    row.update(eligible_physical=True,eligible_domain=False,effective_path_identity='0'*64)
    receipt=dict(snapshot_id=str(uuid.uuid4()),source_id='0'*64,portal_run_id=value['portal_run_id'],
        verified_at=stamp(),method='sqlite_online_backup_ram_v1')
    row['last_verified_physical_success']=receipt
    row['deep'].update(physical_verdict='PASS',domain_verdict='NOT_ADMITTED',reason='domain_validator_absent',
        integrity='PASS',fk='PASS',snapshot_id=receipt['snapshot_id'],verified_at=receipt['verified_at'],
        assurance_scope='SNAPSHOT_ONLY',snapshot_receipt=receipt,
        source_observation_before='1'*64,source_observation_snapshot='1'*64,source_observation_after='1'*64)
    status=project(value)
    assert status['summary']['eligible_physical_count']==1 and status['summary']['eligible_domain_count']==0
    assert status['summary']['physical_coverage_complete'] is True
    assert status['summary']['domain_coverage_complete'] is False
    assert status['stores'][0]['last_verified_success'] is None


@pytest.mark.parametrize('kind',['competing','uid','binding','duplicate'])
def test_rejected_owner_qualification_does_not_even_stat_source(monkeypatch,kind):
    monkeypatch.setattr(os,'geteuid',lambda:1000,raising=False)
    monkeypatch.setattr(os,'getegid',lambda:1000,raising=False)
    inventory=bindings();identity=STORES[0].id
    job=AdmittedStore(identity,inventory.paths[identity],'0'*64,1000,1000,1,1,True)
    jobs=[job]
    if kind=='competing':jobs=[replace(job,no_competing_audit=False)]
    if kind=='uid':jobs=[replace(job,uid=1001)]
    if kind=='binding':jobs=[replace(job,path='/not-the-binding')]
    if kind=='duplicate':jobs=[job,job]
    value,admitted,_=prepare(True,str(uuid.uuid4()),inventory_loader=lambda:inventory,
        qualifications=tuple(jobs),lstat=forbidden,owner_snapshot=lambda *a,**k:{'checks':{}})
    assert admitted=={} and project(value)['summary']['eligible_physical_count']==0


def test_owner_disabled_never_inspects_or_opens_source():
    inventory=bindings()
    from types import MappingProxyType
    inventory=replace(inventory,store_intents=MappingProxyType({s.id:'optional_disabled' for s in STORES}))
    value,admitted,_=prepare(True,None,inventory_loader=lambda:inventory,lstat=forbidden,
        owner_snapshot=lambda *a,**k:{'checks':{}})
    assert admitted=={}
    assert all(r['fast']['state']=='DISABLED' and r['deep']['state']=='DISABLED' for r in value['stores'])
