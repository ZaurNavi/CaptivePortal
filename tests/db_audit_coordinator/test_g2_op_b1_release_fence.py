from dataclasses import replace

import pytest

from app.db_audit_coordinator.admission import CompletionFence
from app.db_audit_coordinator.receipt_ports import RootLayout, UnavailableReceiptPorts
from .test_g2_op_b1_operator_profile_binding import b1_case
from .test_operational_contracts import NOW, metric, stamp, uid


def test_positive_simulated_reap_does_not_release_operational_fence_or_mutate_queue():
    hooks, _ = b1_case(released=True)
    result = hooks.release(now_ns=NOW)
    assert result.status == 'orphan_hold' and result.admits_live is False
    assert result.simulation.status == 'RELEASE_CONFIRMED_SIMULATED'
    assert not isinstance(hooks, CompletionFence) and not CompletionFence().released({}, None)
    with pytest.raises(TypeError): bool(result)


@pytest.mark.parametrize('case', ['worker_alive', 'pid_reuse', 'supervisor_replaced', 'epoch', 'inode',
    'device', 'group_gone', 'snapshot_open', 'descendant', 'untrusted', 'stale', 'reordered',
    'root_missing', 'still_populated', 'missing_receipt', 'missing_collector'])
def test_positive_release_requires_all_reap_empty_group_and_ownership_proofs(case):
    hooks, _ = b1_case(released=True); receipt = hooks.ports.release_value
    if case == 'worker_alive': receipt = replace(receipt, reap=replace(receipt.reap, reaped=False))
    elif case == 'pid_reuse': receipt = replace(receipt, reap=replace(receipt.reap, observed_start_ticks=999))
    elif case == 'supervisor_replaced': receipt = replace(receipt, reap=replace(receipt.reap, waiter_start_ticks=999))
    elif case == 'epoch':
        receipt = replace(receipt, reap=replace(receipt.reap, task=replace(receipt.reap.task, epoch=uid(999))))
    elif case in {'inode', 'device'}:
        node = receipt.after.nodes[-1]; identity = replace(node.before, **{case: 999})
        receipt = replace(receipt, after=replace(receipt.after, nodes=receipt.after.nodes[:-1] +
            (replace(node, before=identity, after=identity),)))
    elif case == 'group_gone': receipt = replace(receipt, after=replace(receipt.after, nodes=receipt.after.nodes[:-1]))
    elif case == 'snapshot_open': receipt = replace(receipt, ownership=replace(receipt.ownership, snapshot_closed=False))
    elif case == 'descendant': receipt = replace(receipt, ownership=replace(receipt.ownership, surviving_descendants=1))
    elif case == 'untrusted': receipt = replace(receipt, reap=replace(receipt.reap, stamp=replace(receipt.reap.stamp, channel='status_file')))
    elif case == 'stale': receipt = replace(receipt, reap=replace(receipt.reap, stamp=stamp(800, offset=-2_000_000_000)))
    elif case == 'reordered': receipt = replace(receipt, before=receipt.after, after=receipt.before)
    elif case == 'root_missing': receipt = replace(receipt, root_layout=RootLayout.ROOT_CONTROLS_ABSENT)
    elif case == 'still_populated': receipt = replace(receipt, after=metric(receipt.after, 'cgroup.events', 'populated 1\nfrozen 0'))
    elif case == 'missing_receipt': receipt = None
    else: hooks = replace(hooks, ports=UnavailableReceiptPorts())
    if case != 'missing_collector': hooks.ports.release_value = receipt
    result = hooks.release(now_ns=NOW)
    assert result.status == 'orphan_hold' and result.admits_live is False
    assert result.simulation is None or result.simulation.status == 'HOLD'
