"""B1 post-lock/reap OFFLINE bridge. Never an Admission or CompletionFence.

No runnable real adapter, SQL, source I/O, service wiring or queue mutation lives
here. Positive simulations are kept separate from mandatory operational denial.
There is deliberately no live-enable option (including environment/config).
"""
from __future__ import annotations

from dataclasses import dataclass
import os

from . import contracts as c
from .locks import PermanentLock
from .operational_contracts import (OperatorProfile, Outcome, identifier, integer,
    path, require)
from .operator_profile_binding import ProfileBinding, validate_binding
from .receipt_ports import (ReceiptChannel, ReleaseReceipts, ResourceReceipts,
    RootLayout, UnavailableReceiptPorts)
from .release_fence import check_release
from .resource_admission import evaluate


@dataclass(frozen=True, repr=False)
class PostLockContext:
    job_id: str
    attempt_id: str
    epoch: str
    run_id: str
    worker_pid: int
    owner_uid: int
    lock_path: str
    lock_device: int
    lock_inode: int

    def __post_init__(self):
        for name in ('job_id', 'attempt_id', 'epoch', 'run_id'):
            identifier(getattr(self, name))
        integer(self.worker_pid, 1, (1 << 31) - 1)
        integer(self.owner_uid, 0, (1 << 32) - 1)
        integer(self.lock_device); integer(self.lock_inode, 1)
        path(self.lock_path)

    def check(self, binding):
        task = binding.task
        for name in ('job_id', 'attempt_id', 'epoch', 'run_id'):
            identifier(getattr(self, name))
            require(getattr(self, name) == getattr(task, name), 'config_trust')
        integer(self.worker_pid, 1, (1 << 31) - 1)
        require(self.worker_pid == task.worker_pid and self.owner_uid == binding.owner_uid,
            'worker_reap')
        lock = binding.global_lock
        require((self.lock_path, self.lock_device, self.lock_inode) ==
            (lock.path, lock.identity.device, lock.identity.inode), 'filesystem_trust')


@dataclass(frozen=True)
class OfflineDecision:
    status: str
    simulation: Outcome | None = None

    def __post_init__(self):
        require(self.status in {'not_admitted', 'orphan_hold'}
            and (self.simulation is None or type(self.simulation) is Outcome), 'evidence_unknown')

    @property
    def admits_live(self):
        return False

    def __bool__(self):
        raise TypeError('offline_evidence_is_not_authority')


@dataclass(frozen=True, repr=False)
class OfflineOperationalHooks:
    profile: OperatorProfile
    configured: ProfileBinding
    ports: object

    def _binding(self, observed, now_ns):
        require(type(self.profile) is OperatorProfile and type(self.configured) is ProfileBinding,
            'config_trust')
        validate_binding(self.configured, observed, self.profile, now_ns=now_ns)

    def preflight(self, context, *, now_ns):
        try:
            require(type(context) is PostLockContext, 'config_trust')
            # Reject unknown/public/live provenance BEFORE invoking any reader.
            require(getattr(self.ports, 'channel', None) is ReceiptChannel.OFFLINE_FIXTURE, 'config_trust')
            require(type(self.configured) is ProfileBinding, 'config_trust')
            context.check(self.configured)
            self.configured.check(self.profile, now_ns, kind='configured')
            receipts = self.ports.resources()
            require(type(receipts) is ResourceReceipts, 'evidence_unknown')
            self._binding(receipts.binding, now_ns)
            require(receipts.root_layout is RootLayout.SYNTHETIC_EXPORTED, 'cgroup_topology')
            simulation = evaluate(self.profile, receipts.before, receipts.after, receipts.geometry, now_ns=now_ns)
            return OfflineDecision('not_admitted', simulation)
        except Exception:
            # Collector exceptions and UNKNOWN are closed denial, without values.
            return OfflineDecision('not_admitted')

    def release(self, *, now_ns):
        try:
            require(getattr(self.ports, 'channel', None) is ReceiptChannel.OFFLINE_FIXTURE, 'config_trust')
            receipts = self.ports.release()
            require(type(receipts) is ReleaseReceipts, 'orphan_hold')
            self._binding(receipts.binding, now_ns)
            require(receipts.root_layout is RootLayout.SYNTHETIC_EXPORTED, 'cgroup_topology')
            simulation = check_release(self.profile, receipts.reap, receipts.before,
                receipts.after, receipts.ownership, now_ns=now_ns)
            return OfflineDecision('orphan_hold', simulation)
        except Exception:
            return OfflineDecision('orphan_hold')


def probe_after_lock(job, gate, hooks=None, *, now_ns):
    """Called only after worker authorization and independently acquired gate.

    gate.check validates THIS process owns the open description; OP-A evidence
    cannot serve as that check. Nothing in the return value permits execution.
    """
    if type(gate) is not PermanentLock:
        raise c.CoordinatorError('not_admitted')
    gate.check()
    if job['store_id'] != 'fingerprint_evidence' or type(hooks) is not OfflineOperationalHooks:
        return OfflineDecision('not_admitted')
    context = PostLockContext(job['job_id'], job['attempt_id'], job['claim_epoch'], job['run_id'],
        os.getpid(), gate.spec.uid, gate.spec.path, gate.spec.device, gate.spec.inode)
    result = hooks.preflight(context, now_ns=now_ns)
    gate.check()  # A receipt collection cannot excuse lock-path replacement.
    return result


def unavailable_decisions():
    """Missing implementation is explicitly unavailable, never a fallback."""
    ports = UnavailableReceiptPorts()
    return ports.resources(), ports.release(), OfflineDecision('not_admitted'), OfflineDecision('orphan_hold')
