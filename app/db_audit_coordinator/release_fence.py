"""Offline positive release receipt checker; never releases locks or starts jobs.

Only independently observed wait/reap + same dedicated cgroup empty receipt +
closed snapshot/descendant ownership can confirm a SIMULATED release. PID absence,
TTL, lock mtime, low memory.current or dropped cache are not receipt alternatives.
No single-child-equivalent fallback is implemented; it needs separate admission.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import cgroup_v2 as cg
from .operational_contracts import (EvidenceError, OperatorProfile, Outcome, Stamp,
    TaskIdentity, boolean, integer, require, stamp_check)


@dataclass(frozen=True, repr=False)
class ReapReceipt:
    schema: str
    task: TaskIdentity
    profile_id: str
    mechanism: str
    waiter_pid: int
    waiter_start_ticks: int
    observed_pid: int
    observed_start_ticks: int
    reaped: bool
    exit_kind: str
    exit_value: int
    stamp: Stamp

    def check(self, profile, now_ns):
        require(self.schema == "coordinator.wait-receipt.offline.v1" and type(self.mechanism) is str
            and self.mechanism in {"waitpid", "waitid"}, "worker_reap")
        require(type(self.task) is TaskIdentity and self.task == profile.task
            and self.profile_id == profile.profile_id, "worker_reap")
        boolean(self.reaped, "worker_reap")
        require(self.reaped, "orphan_hold")
        for value in (self.waiter_pid, self.observed_pid):
            integer(value, 1, (1 << 31) - 1, "worker_reap")
        for value in (self.waiter_start_ticks, self.observed_start_ticks):
            integer(value, 1, code="worker_reap")
        require((self.waiter_pid, self.waiter_start_ticks) ==
            (profile.task.supervisor_pid, profile.task.supervisor_start_ticks), "worker_reap")
        require((self.observed_pid, self.observed_start_ticks) ==
            (profile.task.worker_pid, profile.task.worker_start_ticks), "worker_reap")
        require(type(self.exit_kind) is str and self.exit_kind in {"exited", "signaled"}, "worker_reap")
        integer(self.exit_value, 0 if self.exit_kind == "exited" else 1,
            255 if self.exit_kind == "exited" else 64, "worker_reap")
        stamp_check(self.stamp, now_ns, profile.policy.max_age_ns)


@dataclass(frozen=True, repr=False)
class OwnershipReceipt:
    schema: str
    task: TaskIdentity
    profile_id: str
    snapshot_closed: bool
    snapshot_owners: int
    surviving_descendants: int
    ownership_verified: bool
    stamp: Stamp

    def check(self, profile, now_ns):
        require(self.schema == "coordinator.closed-ownership.offline.v1"
            and type(self.task) is TaskIdentity and self.task == profile.task
            and self.profile_id == profile.profile_id, "worker_reap")
        boolean(self.snapshot_closed, "worker_reap"); boolean(self.ownership_verified, "worker_reap")
        integer(self.snapshot_owners, code="worker_reap")
        integer(self.surviving_descendants, code="worker_reap")
        stamp_check(self.stamp, now_ns, profile.policy.max_age_ns)
        require(self.snapshot_closed and self.ownership_verified and self.snapshot_owners == 0
            and self.surviving_descendants == 0, "orphan_hold")


def check_release(profile=None, reap=None, before=None, after=None, ownership=None, *, now_ns):
    try:
        require(type(profile) is OperatorProfile and type(reap) is ReapReceipt
            and type(ownership) is OwnershipReceipt, "orphan_hold")
        profile.check(now_ns)
        reap.check(profile, now_ns)
        ownership.check(profile, now_ns)
        first = cg.attest(before, profile, now_ns)
        last = cg.attest(after, profile, now_ns)
        cg.stable(first, last)
        # Reap precedes both positive empty observations and ownership evidence.
        require(reap.stamp.captured_ns <= first.stamp.captured_ns
            and first.stamp.captured_ns < last.stamp.captured_ns <= ownership.stamp.captured_ns <= now_ns,
            "orphan_hold")
        require(ownership.stamp.receipt_id not in {reap.stamp.receipt_id, first.stamp.receipt_id,
            last.stamp.receipt_id}, "worker_reap")
        require(all(facts.nodes[-1].populated == 0 and not facts.nodes[-1].procs
            for facts in (first, last)), "orphan_hold")
        return Outcome("RELEASE_CONFIRMED_SIMULATED", (), unavailable=last.unavailable)
    except EvidenceError as error:
        return Outcome("HOLD", (error.code,))
