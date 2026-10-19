"""Portable closed contracts; no real host/cgroup/install authority."""
from dataclasses import asdict,replace
import copy
import uuid

import pytest

from app.db_audit_coordinator import contracts as c
from app.db_audit_coordinator import live_policy as p
from app.db_audit_coordinator.live_profile import PilotProfile
from app.db_audit_coordinator.live_receipts import LocalSample,parse_node

STORES=('public_traffic','network_service_intelligence','traffic_projection')


def policy(store='public_traffic',source='/disposable/source.db',**changes):
    values=dict(store_id=store,source=source,device=1,inode=2,uid=1000,gid=1000,
        schema_version=2 if store in {'public_traffic','fingerprint_evidence'} else 1,source_max_bytes=2**20,wal_max_bytes=2**20,
        image_max_bytes=2**22,backup_overhead_bytes=2**20,validator_overhead_bytes=2**20,
        margin_bytes=2**20,guest_reserve_bytes=2**20,memory_max_bytes=2**26,attempt_seconds=5400)
    values.update(changes);return p.StorePolicy(**values)


def profile(**changes):
    values=dict(schema='db_audit_coordinator.pilot.v1',enabled=False,root=p.ROOT,socket=p.SOCKET,
        release_root='/opt/audit/pinned',commit='1'*40,tree='2'*40,python='/usr/bin/python3.10',python_sha256='3'*64,
        blobs=(('app/__init__.py','4'*64),),delegated='/system.slice/audit.service',delegated_device=1,delegated_inode=2,
        worker_uid=1001,worker_gid=1001,worker_groups=(1000,),operator_uids=(1002,),operator_gid=1002,
        stores=tuple(policy(store) for store in STORES))
    values.update(changes);return PilotProfile(**values)


def node(**changes):
    values={'memory.max':str(2**26),'memory.current':'1024','memory.swap.max':'0','memory.swap.current':'0',
        'memory.events':'low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\n',
        'memory.pressure':'some avg10=0.00 avg60=0.00 avg300=0.00 total=0\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=0\n',
        'cgroup.events':'populated 1\nfrozen 0\n','cgroup.procs':'123\n'}
    values.update(changes);return parse_node('/delegated/job',(1,2),values)


def sample(**changes):
    values=dict(captured_ns=1,nodes=(node(),),guest_available=2**30,guest_vm_counters=(0,0,0,0),
        guest_pressure=node().psi,rss=4096,address_headroom=None)
    values.update(changes);return LocalSample(**values)


@pytest.mark.parametrize('attempt',[1,300,301,5400])
def test_short_receipt_is_independent_of_whole_attempt(attempt):
    value=p.Deadlines(0,attempt)
    value.check(attempt*10**9-1)
    with pytest.raises(c.CoordinatorError):value.check(attempt*10**9)
    if attempt>300:
        value.check(300*10**9+1)
        with pytest.raises(c.CoordinatorError):value.receipt(0,300*10**9+1)
        value.receipt(300*10**9+1,300*10**9+1)


@pytest.mark.parametrize('changes',[{'attempt_seconds':5401},{'attempt_seconds':True},{'receipt_seconds':301},
    {'receipt_seconds':False},{'started_ns':-1}])
def test_deadline_invalid(changes):
    values=dict(started_ns=0,attempt_seconds=5400);values.update(changes)
    with pytest.raises(c.CoordinatorError):p.Deadlines(**values)


@pytest.mark.parametrize('captured,now',[(2,1),(-1,1),(True,1),(0,300*10**9)])
def test_receipt_future_missing_stale_is_not_admitted(captured,now):
    with pytest.raises(c.CoordinatorError):p.Deadlines(0,5400).receipt(captured,now)


@pytest.mark.parametrize('field,value',[('memory_max_bytes',True),('guest_reserve_bytes',0),('inode',0),
    ('source','/a/../source.db'),('source','relative.db'),('attempt_seconds',5401),('store_id','settings')])
def test_store_policy_has_no_implicit_budget_or_source_permission(field,value):
    with pytest.raises(c.CoordinatorError):policy(**{field:value})


def test_profile_default_disabled_and_no_host_authority_protocol():
    value=profile();assert value.enabled is False
    raw=c.decode(c.encode(asdict(value)))
    assert PilotProfile.parse(raw)==value
    for key in ('host_available','host_token','approval_file','ssh_key','operator_approved'):
        changed=copy.deepcopy(raw);changed[key]=True
        with pytest.raises(c.CoordinatorError):PilotProfile.parse(changed)
    with pytest.raises(c.CoordinatorError):profile(stores=(policy(),)*3)
    assert sample().scope=='guest_vm_only'
    assert not any('host' in key for key in asdict(sample()))


def test_native_root_absence_is_expected_not_a_fabricated_limit():
    root=parse_node('/',(1,1),{},root=True)
    assert root.root_controls=='ROOT_CONTROL_NOT_EXPOSED'
    assert root.maximum is root.current is root.swap_max is root.swap_current is None
    sample(nodes=(root,node())).check()
    with pytest.raises(c.CoordinatorError):parse_node('/leaf',(1,1),{})
    with pytest.raises(c.CoordinatorError):parse_node('/',(1,1),{'memory.max':'max'},root=True)


@pytest.mark.parametrize('changes',[{'memory.max':'max'},{'memory.swap.max':'1'},{'memory.swap.current':'1','memory.swap.max':'1'},
    {'memory.current':str(2**26+1)}, {'memory.events':'low 0\nhigh 0\nmax 1\noom 0\noom_kill 0'},
    {'memory.pressure':'some avg10=1.00 avg60=0.00 avg300=0.00 total=1\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=0'}])
def test_missing_or_unsafe_leaf_fails_closed(changes):
    with pytest.raises(Exception):sample(nodes=(node(**changes),)).check()


@pytest.mark.parametrize('changed',[{'captured_ns':0},{'nodes':(replace(node(),identity=(1,3)),)},
    {'guest_vm_counters':(1,0,0,0)},{'nodes':(replace(node(),maximum=2**25),)},
    {'guest_pressure':(('some',(False,1)),('full',(False,0)))}])
def test_changed_pressure_identity_caps_or_clock_is_rejected(changed):
    with pytest.raises(c.CoordinatorError):sample(**changed).check(sample())


def test_guest_and_each_ancestor_and_rlimit_headroom_are_checked():
    sample().admit(policy(),4096,0)
    for value in (sample(guest_available=2**20),sample(address_headroom=4096),
            sample(nodes=(replace(node(),location='/parent',maximum=2**26,current=2**26-1),node()))):
        with pytest.raises(c.CoordinatorError):value.admit(policy(),4096,0)


def test_fixture_queue_cannot_be_promoted_to_operational_success():
    with pytest.raises(c.CoordinatorError):p.state(c.empty_state())
    assert p.state(p.empty_state())['schema_version']==p.SCHEMA
    generation=p.physical_generation('public_traffic',1,2)
    assert generation==p.physical_generation('public_traffic',1,2)
    assert generation!=p.physical_generation('public_traffic',1,3)
    uuid.UUID(generation)
