from dataclasses import asdict, replace
import hashlib
import os
from pathlib import Path
import sys
import uuid

import pytest

from app.db_audit_coordinator import contracts as c, operational_hooks as hooks_module, worker
from app.db_audit_coordinator.locks import PermanentLock
from app.db_audit_coordinator.operational_hooks import OfflineDecision, OfflineOperationalHooks, probe_after_lock
from app.db_audit_coordinator.receipt_ports import ReceiptChannel, RootLayout, UnavailableReceiptPorts
from app.db_audit_coordinator.operational_contracts import EvidenceError
from tests.db_audit_coordinator import cleanup, lab, submit
from .test_g2_op_b1_operator_profile_binding import b1_case
from .test_operational_contracts import NOW, metric


@pytest.mark.parametrize('channel', [None, 'offline_fixture', 'trusted', True, 'public_socket', 'environment', 'status_file'])
def test_unqualified_collector_identity_is_denied_before_invocation(channel):
    hooks, context = b1_case(); hooks.ports.channel = channel
    assert hooks.preflight(context, now_ns=NOW).status == 'not_admitted'
    assert hooks.ports.calls == []


def test_defaults_missing_ports_and_forged_outputs_never_enable_real_execution():
    hooks, context = b1_case()
    for port in (UnavailableReceiptPorts(), None, object()):
        result = replace(hooks, ports=port).preflight(context, now_ns=NOW)
        assert result.status == 'not_admitted' and result.admits_live is False
    hooks.ports.resource_value = {'trusted': True, 'status': 'LAB_ADMITTED'}
    assert hooks.preflight(context, now_ns=NOW).simulation is None
    hooks.ports.resources = lambda: (_ for _ in ()).throw(OSError('PRIVATE_CANARY'))
    assert 'PRIVATE_CANARY' not in repr(hooks.preflight(context, now_ns=NOW))


@pytest.mark.parametrize('field,value', [('worker_pid', True), ('owner_uid', False),
    ('lock_inode', 0), ('lock_device', -1), ('epoch', 'invalid'), ('lock_path', '/queue/../escape')])
def test_post_lock_context_is_closed_typed_not_a_boolean_authority(field, value):
    _, context = b1_case()
    with pytest.raises(EvidenceError):
        replace(context, **{field: value})


def test_expired_config_and_wrong_claim_never_invoke_receipt_port():
    hooks, context = b1_case()
    expired = replace(hooks.configured, stamp=replace(hooks.configured.stamp, captured_ns=0))
    assert replace(hooks, configured=expired).preflight(context, now_ns=NOW).status == 'not_admitted'
    assert hooks.preflight(replace(context, worker_pid=context.worker_pid+1), now_ns=NOW).status == 'not_admitted'
    assert hooks.ports.calls == []


@pytest.mark.parametrize('root', [RootLayout.ROOT_CONTROLS_ABSENT, RootLayout.UNKNOWN])
def test_absent_root_controls_are_an_explicit_unqualified_layout_not_zero(root):
    hooks, context = b1_case()
    hooks.ports.resource_value = replace(hooks.ports.resource_value, root_layout=root)
    result = hooks.preflight(context, now_ns=NOW)
    assert result.status == 'not_admitted' and result.simulation is None


@pytest.mark.parametrize('change', ['missing_subgroup', 'unbounded', 'swap', 'pressure', 'unknown_reclaim',
    'stale_geometry', 'missing_root_current', 'different_mount', 'membership', 'timeout'])
def test_resource_bridge_keeps_negative_admission_math_and_root_unknown(change):
    hooks, context = b1_case(); receipts = hooks.ports.resource_value
    before, after, geometry = receipts.before, receipts.after, receipts.geometry
    if change == 'missing_subgroup': after = replace(after, nodes=after.nodes[:-1])
    elif change == 'unbounded': after = metric(after, 'memory.max', 'max')
    elif change == 'swap': after = metric(after, 'memory.swap.max', '1')
    elif change == 'pressure':
        raw = dict(after.nodes[-1].files)['memory.pressure'].value.replace('avg10=0.00', 'avg10=1.00')
        after = metric(after, 'memory.pressure', raw)
    elif change == 'unknown_reclaim': after = replace(after, proc_vmstat='pswpin 0\npswpout 0\n')
    elif change == 'stale_geometry': geometry = replace(geometry, stamp=replace(geometry.stamp, captured_ns=0))
    elif change == 'missing_root_current':
        node = after.nodes[0]
        from app.db_audit_coordinator.cgroup_v2 import MetricRead
        node = replace(node, files=tuple((key, MetricRead(None, None, None) if key == 'memory.current' else value)
            for key, value in node.files))
        after = replace(after, nodes=(node,) + after.nodes[1:])
    elif change == 'different_mount': after = replace(after, mountinfo=after.mountinfo.replace('/fixture-cgroup', '/alternate'))
    elif change == 'membership': after = replace(after, membership='0::/system.slice\n')
    else: geometry = replace(geometry, stamp=replace(geometry.stamp, captured_ns=NOW-101_000_000))
    hooks.ports.resource_value = replace(receipts, before=before, after=after, geometry=geometry)
    result = hooks.preflight(context, now_ns=NOW)
    assert result.status == 'not_admitted' and result.simulation.status == 'NOT_ADMITTED'


@pytest.mark.skipif(sys.platform != 'linux', reason='Linux child-owned flock and private authorization integration')
@pytest.mark.parametrize('case', ['ordered', 'invalid_auth', 'gate_busy', 'forged_success'])
def test_actual_private_authorization_and_own_gate_precede_every_hook(tmp_path, monkeypatch, case):
    fixture = lab(tmp_path); subject = fixture.coordinator(); read_fd, write_fd = os.pipe()
    cancel_read, cancel_write = os.pipe(); gates = []; held = None; trace = []
    try:
        submit(subject, 'fingerprint_evidence')
        state = subject.store.read(); job = state['jobs'][0]; info = os.fstat(read_fd); nonce = os.urandom(32).hex()
        job.update(state='claimed', claim_epoch=state['controller_epoch'], attempt_id=str(uuid.uuid4()),
            run_id=str(uuid.uuid4()), auth_hash=hashlib.sha256(nonce.encode()).hexdigest(),
            auth_device=info.st_dev, auth_inode=info.st_ino, worker_pid=os.getpid())
        subject.store.commit(state)
        payload = dict(job_id=job['job_id'], store_id=job['store_id'], claim_epoch=job['claim_epoch'],
            attempt_id=job['attempt_id'], nonce='0'*64 if case == 'invalid_auth' else nonce,
            root=str(fixture.root), uid=os.geteuid(), gate=asdict(fixture.gate), plan=None, cancel_fd=cancel_read)
        os.write(write_fd, c.encode(payload)); os.close(write_fd); write_fd = None
        original_auth, original_acquire = worker.authorization, PermanentLock.acquire
        def auth(fd):
            value = original_auth(fd); trace.append('private_authority_and_durable_claim'); return value
        def acquire(gate):
            gates.append(gate); value = original_acquire(gate); trace.append('independent_own_global_flock'); return value
        monkeypatch.setattr(worker, 'authorization', auth)
        monkeypatch.setattr(PermanentLock, 'acquire', acquire)
        if case == 'gate_busy':
            # A distinct open-file description, not an inherited/shared flock FD.
            held = PermanentLock(fixture.gate); original_acquire(held)
        if case == 'forged_success':
            monkeypatch.setattr(hooks_module, 'probe_after_lock', lambda *a, **k: True)
        else:
            def preflight(self, context, *, now_ns):
                gates[-1].check(); trace.append('post_lock_receipt_port_then_budget')
                return OfflineDecision('not_admitted')
            monkeypatch.setattr(OfflineOperationalHooks, 'preflight', preflight)
        hooks, _ = b1_case()
        if case == 'invalid_auth':
            with pytest.raises(c.CoordinatorError, match='unauthorized'):
                worker.execute(read_fd, offline_hooks=hooks)
        else:
            assert worker.execute(read_fd, offline_hooks=hooks) == 2
        read_fd = None
        expected = [] if case == 'invalid_auth' else ['private_authority_and_durable_claim']
        if case not in {'invalid_auth', 'gate_busy'}: expected.append('independent_own_global_flock')
        if case == 'ordered': expected.append('post_lock_receipt_port_then_budget')
        assert trace == expected
        assert not tuple(fixture.root.glob('*.preflight')) and not tuple(fixture.root.glob('*.source_read'))
        assert subject.store.read()['last_verified_success_by_store'] == {}
    finally:
        for gate in gates:
            gate.close()
        if held: held.close()
        for descriptor in (read_fd, write_fd, cancel_read, cancel_write):
            if descriptor is not None:
                try: os.close(descriptor)
                except OSError: pass
        cleanup(subject)


@pytest.mark.skipif(sys.platform != 'linux', reason='Linux process-owned flock requirement')
def test_offline_receipts_cannot_replace_own_gate(tmp_path):
    fixture = lab(tmp_path); hooks, _ = b1_case()
    job = {'store_id': 'fingerprint_evidence'}
    with pytest.raises(c.CoordinatorError):
        probe_after_lock(job, PermanentLock(fixture.gate), hooks, now_ns=NOW)
    assert hooks.ports.calls == []


def test_b1_imports_no_source_sqlite_collector_or_runtime_autostart():
    root = Path(__file__).resolve().parents[2]
    import ast
    for name in ('operator_profile_binding', 'receipt_ports', 'operational_hooks'):
        source = (root/'app/db_audit_coordinator'/f'{name}.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        imported = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        imported += [item.name for node in ast.walk(tree) if isinstance(node, ast.Import) for item in node.names]
        assert not any(value and ('sqlite' in value or 'audit_runner' in value or 'subprocess' in value) for value in imported)
    for name in ('run.py', 'app/device_fingerprint/service.py', 'app/settings.py'):
        source = (root/name).read_text(encoding='utf-8')
        assert not any(value in source for value in ('operational_hooks', 'receipt_ports', 'operator_profile_binding'))
