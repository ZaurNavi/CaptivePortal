"""Offline preflight math only; never allocates RAM, opens SQLite or admits live work.

The candidate budget is image + WAL + measured backup/validator overhead +
positive justified margin + separately observed outstanding RSS reservations.
It must fit host reserve, EVERY finite ancestor/child headroom and finite process
rlimit headroom. No 18 GiB cap or universal multiplier is inferred from history.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import cgroup_v2 as cg
from .operational_contracts import (EvidenceError, MAX_INT, OperatorProfile, Outcome,
    SourceIdentity, Stamp, TaskIdentity, closed, identifier, integer, require, stamp_check)


@dataclass(frozen=True, repr=False)
class Geometry:
    schema: str
    profile_id: str
    task: TaskIdentity
    source: SourceIdentity
    phase: str
    main_bytes: int
    wal_bytes: int
    page_size: int
    page_count: int
    image_estimate_bytes: int
    backup_overhead_bytes: int
    validator_overhead_bytes: int
    margin_bytes: int
    other_live_rss_reserved_bytes: int
    stamp: Stamp
    reservations_stamp: Stamp

    def __post_init__(self):
        require(self.schema == "coordinator.source-geometry.offline.v1", "source_identity")
        identifier(self.profile_id)
        require(type(self.task) is TaskIdentity and type(self.source) is SourceIdentity,
            "source_identity")
        require(self.phase == "offline_after_global_gate", "source_identity")
        for name in ("main_bytes", "page_size", "page_count", "image_estimate_bytes",
                     "backup_overhead_bytes", "validator_overhead_bytes", "margin_bytes"):
            integer(getattr(self, name), 1, code="ram_budget")
        integer(self.wal_bytes, code="ram_budget")
        integer(self.other_live_rss_reserved_bytes, code="ram_budget")
        require(type(self.stamp) is Stamp and type(self.reservations_stamp) is Stamp, "evidence_unknown")

    @classmethod
    def parse(cls, value):
        data = dict(closed(value, cls, "source_identity"))
        for name, factory in (("task", TaskIdentity), ("source", SourceIdentity),
                              ("stamp", Stamp), ("reservations_stamp", Stamp)):
            data[name] = factory.parse(data[name])
        return cls(**data)


def evaluate(profile=None, before=None, after=None, geometry=None, *, now_ns):
    """Only CANDIDATE_SAFE_SIMULATED or NOT_ADMITTED; no live-enable flag exists."""
    try:
        require(type(profile) is OperatorProfile and type(geometry) is Geometry, "config_trust")
        profile.check(now_ns)
        require(geometry.profile_id == profile.profile_id and geometry.task == profile.task, "source_identity")
        for name in ("device", "inode", "generation", "locator_sha256", "writer_artifact_sha256",
                     "auditor_artifact_sha256", "service_identity_sha256"):
            require(getattr(geometry.source, name) == getattr(profile.source, name), "source_identity")
        for receipt in (geometry.stamp, geometry.reservations_stamp, geometry.source.stamp):
            stamp_check(receipt, now_ns, profile.policy.max_age_ns)
        elapsed = now_ns - geometry.stamp.captured_ns
        require(0 <= elapsed < profile.policy.timeout_ms * 1_000_000, "deadline")
        first = cg.attest(before, profile, now_ns)
        last = cg.attest(after, profile, now_ns)
        cg.stable(first, last)
        require(geometry.stamp.captured_ns <= first.stamp.captured_ns
            and last.stamp.captured_ns <= now_ns, "evidence_unknown")
        leaf = last.nodes[-1]
        require(leaf.populated == 1 and leaf.procs == (profile.task.worker_pid,), "worker_reap")
        page_size = geometry.page_size
        require(512 <= page_size <= 65536 and page_size & (page_size - 1) == 0, "ram_budget")
        require(geometry.main_bytes % page_size == 0 and geometry.main_bytes <= geometry.page_count * page_size
            <= geometry.image_estimate_bytes <= profile.policy.supported_cap_bytes, "ram_budget")
        require(geometry.wal_bytes == 0 or geometry.wal_bytes >= 32
            and (geometry.wal_bytes - 32) % (page_size + 24) == 0, "ram_budget")
        require(geometry.margin_bytes >= profile.policy.minimum_margin_bytes, "ram_budget")
        budget = sum((geometry.image_estimate_bytes, geometry.wal_bytes, geometry.backup_overhead_bytes,
            geometry.validator_overhead_bytes, geometry.margin_bytes, geometry.other_live_rss_reserved_bytes))
        integer(budget, 1, MAX_INT, "ram_budget")
        for facts in (first, last):
            require(budget < facts.headroom and budget < facts.effective_cap, "limit_headroom")
            require(budget + profile.policy.host_reserve_bytes < facts.mem_available, "ram_budget")
            require(facts.rlimit_headroom is None or budget < facts.rlimit_headroom, "limit_headroom")
        remaining_ms = (profile.policy.timeout_ms * 1_000_000 - elapsed) // 1_000_000
        # Sub-millisecond remainder is not rounded up into an extra live budget.
        require(remaining_ms > 0, "deadline")
        return Outcome("CANDIDATE_SAFE_SIMULATED", (), budget, remaining_ms, last.unavailable)
    except EvidenceError as error:
        return Outcome("NOT_ADMITTED", (error.code,))


def cancel_condition(profile=None, initial=None, current=None, geometry=None, *, now_ns):
    """Conservative offline cancellation advice, NOT an executor or watchdog."""
    return evaluate(profile, initial, current, geometry, now_ns=now_ns).status != "CANDIDATE_SAFE_SIMULATED"
