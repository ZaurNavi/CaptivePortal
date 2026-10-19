"""Exact native root layout and sanitized diagnostics; no live cgroup writes."""
from dataclasses import replace
import sys

import pytest

from app.db_audit_coordinator import contracts as c
from app.db_audit_coordinator import daemon_cli
from app.db_audit_coordinator.live_receipts import parse_node
from tests.db_audit_coordinator.test_b2_live_policy import node, sample

PSI='some avg10=0.00 avg60=0.00 avg300=0.00 total=12\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=3\n'
CONTROLS=('memory.max','memory.current','memory.swap.max','memory.swap.current','memory.events')


@pytest.mark.parametrize('psi',[None,PSI])
def test_native_root_five_controls_absent_optional_psi(psi):
    root=parse_node('/',(1,1),{'memory.pressure':psi},root=True)
    assert root.root_controls=='ROOT_CONTROL_NOT_EXPOSED'
    assert root.maximum is root.current is root.swap_max is root.swap_current is root.events is None
    assert (root.psi is None)==(psi is None)
    sample(nodes=(root,node())).check()
    assert root.populated is None and root.procs==()


@pytest.mark.parametrize('psi',['','some avg10=0.00',PSI+PSI,PSI.replace('0.00','NaN'),
    PSI.replace('total=12','total=-1'),True,123])
def test_malformed_standalone_root_psi_fails_closed(psi):
    with pytest.raises(Exception):parse_node('/',(1,1),{'memory.pressure':psi},root=True)


@pytest.mark.parametrize('control',CONTROLS)
def test_partial_authoritative_root_control_bundle_is_still_rejected(control):
    with pytest.raises(c.CoordinatorError):
        parse_node('/',(1,1),{control:'0','memory.pressure':PSI},root=True)


@pytest.mark.parametrize('location,root',[('/leaf',False),('/system.slice',False),('/leaf',True),('/',False)])
def test_standalone_pressure_exception_is_only_for_explicit_root(location,root):
    with pytest.raises(c.CoordinatorError):parse_node(location,(1,1),{'memory.pressure':PSI},root=root)


def test_root_pressure_and_identity_drift_remain_blocking():
    root=parse_node('/',(1,1),{'memory.pressure':PSI},root=True)
    baseline=sample(nodes=(root,node()))
    for changed in (replace(root,identity=(1,2)),
            parse_node('/',(1,1),{'memory.pressure':PSI.replace('total=12','total=13')},root=True),
            parse_node('/',(1,1),{'memory.pressure':PSI.replace('avg10=0.00','avg10=1.00')},root=True)):
        with pytest.raises(c.CoordinatorError):sample(nodes=(changed,node())).check(baseline)
    with pytest.raises(c.CoordinatorError):sample(nodes=(root,)).check()
    with pytest.raises(c.CoordinatorError):sample(nodes=(root,replace(node(),maximum=None))).check()
    with pytest.raises(c.CoordinatorError):sample(nodes=(root,replace(node(),swap_max=1))).check()


@pytest.mark.parametrize('stage',sorted(daemon_cli.STAGES))
def test_daemon_only_one_short_stage_reason(monkeypatch,capsys,stage):
    from app.db_audit_coordinator import live_profile,live_coordinator
    monkeypatch.setattr(live_profile,'load_profile',lambda:None)
    class Subject:
        diagnostic_stage=stage
        def __init__(self,profile):pass
        def serve(self):raise c.CoordinatorError('not_admitted')
        def close(self):pass
    monkeypatch.setattr(live_coordinator,'LiveCoordinator',Subject)
    assert daemon_cli.main(['run'])==3
    assert capsys.readouterr().err==f'db_audit_coordinator stage={stage} reason_code=not_admitted\n'


@pytest.mark.parametrize('failure',['profile','constructor','serve','close'])
def test_sensitive_exception_payload_and_untrusted_enums_never_print(monkeypatch,capsys,failure):
    from app.db_audit_coordinator import live_profile,live_coordinator
    secret='/private/source.db pid=42 token=SECRET 192.0.2.1 aa:bb:cc:dd:ee:ff'
    class PayloadError(Exception):code=secret
    def fail():raise PayloadError(secret)
    monkeypatch.setattr(live_profile,'load_profile',fail if failure=='profile' else lambda:None)
    class Subject:
        diagnostic_stage=secret
        def __init__(self,profile):
            if failure=='constructor':fail()
        def serve(self):
            if failure=='serve':fail()
        def close(self):
            if failure=='close':fail()
    monkeypatch.setattr(live_coordinator,'LiveCoordinator',Subject)
    assert daemon_cli.main(['run'])==3
    output=capsys.readouterr()
    expected='profile_load' if failure=='profile' else 'coordinator_initialization' if failure=='constructor' else 'serve'
    assert output.err==f'db_audit_coordinator stage={expected} reason_code=coordinator_unavailable\n'
    assert output.out=='' and secret not in output.err and 'Traceback' not in output.err


@pytest.mark.skipif(sys.platform!='linux',reason='Linux/POSIX native nofollow cgroup receipt reader')
def test_native_layout_read_through_disposable_directory(tmp_path):
    import os
    from app.db_audit_coordinator.live_receipts import read_at
    (tmp_path/'memory.pressure').write_text(PSI,encoding='ascii')
    fd=os.open(tmp_path,os.O_RDONLY|os.O_DIRECTORY)
    try:
        values={name:read_at(fd,name,optional=True,trusted_uid=os.geteuid()) for name in (*CONTROLS,'memory.pressure')}
        root=parse_node('/',(1,1),values,root=True)
        assert root.psi is not None and root.root_controls=='ROOT_CONTROL_NOT_EXPOSED'
    finally:os.close(fd)


@pytest.mark.parametrize('missing',(*CONTROLS,'memory.pressure'))
def test_one_missing_nonroot_control_never_uses_root_exception(missing):
    values={'memory.max':'1024','memory.current':'0','memory.swap.max':'0','memory.swap.current':'0',
        'memory.events':'low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\n','memory.pressure':PSI,
        'cgroup.events':'populated 0\nfrozen 0\n','cgroup.procs':''}
    values.pop(missing)
    with pytest.raises(c.CoordinatorError):parse_node('/job',(1,2),values)


@pytest.mark.skipif(sys.platform!='linux',reason='Linux/POSIX blocked-child pipe and post-claim diagnostic contract')
def test_actual_dispatch_failure_retains_post_claim_stage_and_claim(monkeypatch,capsys):
    import threading
    from app.db_audit_coordinator import live_coordinator as runtime,live_profile
    from tests.db_audit_coordinator.test_b2_live_policy import profile
    from tests.db_audit_coordinator.test_recover_once import old_queue
    value=runtime.LiveCoordinator.__new__(runtime.LiveCoordinator)
    current=old_queue();first=current['jobs'][0]
    first.update(state='queued',claim_epoch=None,attempt_id=None,run_id=None,auth_hash=None,
        auth_device=None,auth_inode=None,resource_envelope=None,reason_code='accepted')
    value._mutex=threading.RLock();value.process=None;value.orphan_hold=False;value._stopped=False
    value._batch=(first['job_id'],);value._state=lambda:current;value.profile=profile()
    commits=[];value._commit=lambda state:commits.append(__import__('copy').deepcopy(state))
    monkeypatch.setattr(type(value.profile),'artifact',lambda self:None)
    def denied(*args,**kwargs):raise c.CoordinatorError('not_admitted')
    monkeypatch.setattr(runtime,'create_leaf',denied)
    value.serve=value.dispatch_one;value.close=lambda:None
    monkeypatch.setattr(live_profile,'load_profile',lambda:None)
    monkeypatch.setattr(runtime,'LiveCoordinator',lambda profile:value)
    assert daemon_cli.main(['run'])==3
    assert len(commits)==1 and commits[0]['jobs'][0]['state']=='claimed'
    assert value.orphan_hold and current['jobs'][0]['worker_pid'] is None
    assert capsys.readouterr().err=='db_audit_coordinator stage=post_claim_leaf_attestation reason_code=not_admitted\n'
