"""G2-OP-A OFFLINE evidence vocabulary, not a credential or live admission API.

No runtime imports this module. Values describe supplied observations, not facts
this process has independently measured. Only synthetic, fresh, closed evidence
can yield CANDIDATE_SAFE_SIMULATED; operator/live data cannot enable execution.
Actual receipt collection/authentication and child wiring belong to OP-B.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
import re
from uuid import UUID

MAX_INT = (1 << 63) - 1
DOMAIN = "lab-ubunt-local-sqlite-v1"
STORE = "fingerprint_evidence"
CODES = frozenset({"config_trust", "cgroup_topology", "limit_headroom", "source_identity",
    "ram_budget", "worker_reap", "filesystem_trust", "evidence_unknown", "deadline",
    "orphan_hold", "queue_lifecycle", "live_admission_forbidden"})


class EvidenceError(ValueError):
    def __init__(self, code):
        self.code = code if code in CODES else "evidence_unknown"
        super().__init__(self.code)  # No untrusted values, paths or exceptions.


def require(value, code):
    if not value:
        raise EvidenceError(code)


def integer(value, minimum=0, maximum=MAX_INT, code="evidence_unknown"):
    require(type(value) is int and minimum <= value <= maximum, code)
    return value


def boolean(value, code="evidence_unknown"):
    require(type(value) is bool, code)
    return value


def identifier(value, code="config_trust"):
    require(type(value) is str and len(value) == 36, code)
    try:
        require(str(UUID(value)) == value, code)
    except (ValueError, AttributeError):
        raise EvidenceError(code) from None
    return value


def digest(value, code="config_trust"):
    require(type(value) is str and re.fullmatch(r"[a-f0-9]{64}", value) is not None, code)
    return value


def path(value):
    require(type(value) is str and len(value) <= 512 and value.startswith("/"), "filesystem_trust")
    if value == "/":
        return value
    parts = value[1:].split("/")
    require(1 <= len(parts) <= 16 and all(part not in {"", ".", ".."}
        and re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", part) for part in parts), "filesystem_trust")
    return value


def closed(value, cls, code="config_trust"):
    require(type(value) is dict and set(value) == {item.name for item in fields(cls)}, code)
    return value


@dataclass(frozen=True, repr=False)
class Stamp:
    kind: str
    channel: str
    receipt_id: str
    captured_ns: int

    def __post_init__(self):
        require(type(self.kind) is str and self.kind in {"observed", "configured", "UNKNOWN"}, "config_trust")
        require(type(self.channel) is str and self.channel in {"offline_fixture", "operator_review", "public_socket",
            "environment", "status_file", "UNKNOWN"}, "config_trust")
        identifier(self.receipt_id)
        integer(self.captured_ns)

    @classmethod
    def parse(cls, value):
        return cls(**closed(value, cls))


def stamp_check(stamp, now_ns, max_age_ns, kind="observed"):
    require(type(stamp) is Stamp, "config_trust")
    integer(now_ns); integer(max_age_ns, 1)
    require(stamp.kind != "UNKNOWN", "evidence_unknown")
    require(stamp.kind == kind and stamp.channel == "offline_fixture", "config_trust")
    require(0 <= now_ns - stamp.captured_ns <= max_age_ns, "evidence_unknown")


@dataclass(frozen=True, repr=False)
class TaskIdentity:
    queue_id: str
    job_id: str
    attempt_id: str
    epoch: str
    run_id: str
    supervisor_pid: int
    supervisor_start_ticks: int
    worker_pid: int
    worker_start_ticks: int

    def __post_init__(self):
        for name in ("queue_id", "job_id", "attempt_id", "epoch", "run_id"):
            identifier(getattr(self, name))
        for name in ("supervisor_pid", "worker_pid"):
            integer(getattr(self, name), 1, (1 << 31) - 1, "worker_reap")
        for name in ("supervisor_start_ticks", "worker_start_ticks"):
            integer(getattr(self, name), 1, code="worker_reap")
        require(self.supervisor_pid != self.worker_pid, "worker_reap")

    @classmethod
    def parse(cls, value):
        return cls(**closed(value, cls))


@dataclass(frozen=True, repr=False)
class FileIdentity:
    device: int
    inode: int
    uid: int
    mode: int
    kind: str
    links: int

    def __post_init__(self):
        integer(self.device); integer(self.inode, 1); integer(self.uid, 0, (1 << 32) - 1)
        integer(self.mode, 0, 0o7777); integer(self.links, 1)
        require(type(self.kind) is str and self.kind in {"file", "directory", "symlink", "UNKNOWN"}, "filesystem_trust")

    def check(self, kind, uid):
        require(self.kind == kind and self.uid == uid and not self.mode & 0o7022,
            "filesystem_trust")
        if kind == "file":
            require(self.links == 1, "filesystem_trust")

    @classmethod
    def parse(cls, value):
        return cls(**closed(value, cls, "filesystem_trust"))


@dataclass(frozen=True, repr=False)
class SourceIdentity:
    device: int
    inode: int
    generation: str
    locator_sha256: str
    writer_artifact_sha256: str
    auditor_artifact_sha256: str
    service_identity_sha256: str
    stamp: Stamp

    def __post_init__(self):
        integer(self.device, code="source_identity"); integer(self.inode, 1, code="source_identity")
        identifier(self.generation, "source_identity")
        for name in ("locator_sha256", "writer_artifact_sha256", "auditor_artifact_sha256", "service_identity_sha256"):
            digest(getattr(self, name), "source_identity")
        require(type(self.stamp) is Stamp, "source_identity")

    @classmethod
    def parse(cls, value):
        data = dict(closed(value, cls, "source_identity"))
        data["stamp"] = Stamp.parse(data["stamp"])
        return cls(**data)


@dataclass(frozen=True, repr=False)
class FilesystemProof:
    filesystem: str
    local_posix: bool
    atomic_replace: bool
    file_fsync: bool
    directory_fsync: bool
    root_identity: FileIdentity
    stamp: Stamp

    def __post_init__(self):
        require(type(self.filesystem) is str and self.filesystem in {"ext4", "xfs", "btrfs", "tmpfs", "UNKNOWN"}, "filesystem_trust")
        for name in ("local_posix", "atomic_replace", "file_fsync", "directory_fsync"):
            boolean(getattr(self, name), "filesystem_trust")
        require(type(self.root_identity) is FileIdentity and type(self.stamp) is Stamp, "filesystem_trust")

    @classmethod
    def parse(cls, value):
        data = dict(closed(value, cls, "filesystem_trust"))
        data["root_identity"] = FileIdentity.parse(data["root_identity"])
        data["stamp"] = Stamp.parse(data["stamp"])
        return cls(**data)


@dataclass(frozen=True, repr=False)
class ResourcePolicy:
    max_age_ns: int
    timeout_ms: int
    supported_cap_bytes: int
    minimum_margin_bytes: int
    host_reserve_bytes: int
    justification_sha256: str

    def __post_init__(self):
        integer(self.max_age_ns, 1, 60_000_000_000, "config_trust")
        integer(self.timeout_ms, 1, 300_000, "config_trust")
        integer(self.supported_cap_bytes, 1, code="ram_budget")
        integer(self.minimum_margin_bytes, 1, code="ram_budget")
        integer(self.host_reserve_bytes, code="ram_budget")
        digest(self.justification_sha256)

    @classmethod
    def parse(cls, value):
        return cls(**closed(value, cls))


@dataclass(frozen=True, repr=False)
class OperatorProfile:
    schema: str
    domain: str
    store_id: str
    profile_id: str
    task: TaskIdentity
    coordinator_cgroup: str
    job_cgroup: str
    mountpoint: str
    job_cgroup_identity: FileIdentity
    cgroup_ancestry_sha256: str
    owner_uid: int
    child_memory_max: int | None
    child_swap_max: int | None
    config_stamp: Stamp
    source: SourceIdentity
    filesystem: FilesystemProof
    policy: ResourcePolicy

    def __post_init__(self):
        require(self.schema == "coordinator.operator-profile.offline.v1" and self.domain == DOMAIN
            and self.store_id == STORE, "config_trust")
        identifier(self.profile_id)
        require(type(self.task) is TaskIdentity and type(self.policy) is ResourcePolicy, "config_trust")
        path(self.coordinator_cgroup); path(self.job_cgroup); path(self.mountpoint)
        require(self.coordinator_cgroup != "/" and self.job_cgroup.startswith(self.coordinator_cgroup + "/"), "cgroup_topology")
        integer(self.owner_uid, 0, (1 << 32) - 1, "filesystem_trust")
        require(type(self.job_cgroup_identity) is FileIdentity, "filesystem_trust")
        digest(self.cgroup_ancestry_sha256, "filesystem_trust")
        for value in (self.child_memory_max, self.child_swap_max):
            if value is not None:
                integer(value, code="limit_headroom")
        require(type(self.config_stamp) is Stamp and type(self.source) is SourceIdentity
            and type(self.filesystem) is FilesystemProof, "config_trust")

    @classmethod
    def parse(cls, value):
        data = dict(closed(value, cls))
        for name, factory in (("task", TaskIdentity), ("config_stamp", Stamp), ("source", SourceIdentity),
                              ("filesystem", FilesystemProof), ("policy", ResourcePolicy),
                              ("job_cgroup_identity", FileIdentity)):
            data[name] = factory.parse(data[name])
        return cls(**data)

    def check(self, now_ns):
        age = self.policy.max_age_ns
        stamp_check(self.config_stamp, now_ns, age, "configured")
        stamp_check(self.source.stamp, now_ns, age)
        stamp_check(self.filesystem.stamp, now_ns, age)
        fs = self.filesystem
        require(fs.filesystem != "UNKNOWN" and fs.local_posix and fs.atomic_replace
            and fs.file_fsync and fs.directory_fsync, "filesystem_trust")
        fs.root_identity.check("directory", self.owner_uid)
        self.job_cgroup_identity.check("directory", self.owner_uid)
        require(self.child_memory_max is not None and self.child_swap_max is not None, "evidence_unknown")
        require(0 < self.child_memory_max <= self.policy.supported_cap_bytes
            and self.child_swap_max == 0, "limit_headroom")


@dataclass(frozen=True)
class Outcome:
    status: str
    codes: tuple[str, ...]
    budget_bytes: int | None = None
    remaining_ms: int | None = None
    unavailable: tuple[str, ...] = ()

    def __post_init__(self):
        require(type(self.status) is str and self.status in {"NOT_ADMITTED", "CANDIDATE_SAFE_SIMULATED", "HOLD",
            "RELEASE_CONFIRMED_SIMULATED"}, "evidence_unknown")
        require(type(self.codes) is tuple and len(self.codes) <= len(CODES)
            and all(type(code) is str and code in CODES for code in self.codes), "evidence_unknown")
        for value in (self.budget_bytes, self.remaining_ms):
            if value is not None:
                integer(value)
        require(type(self.unavailable) is tuple and all(value == "memory.peak" for value in self.unavailable), "evidence_unknown")

    @property
    def admits_live(self):
        return False

    def __bool__(self):
        raise TypeError("offline_evidence_is_not_authority")

    def sanitized(self):
        return dict(schema="coordinator.preflight.offline.v1", status=self.status, codes=list(self.codes),
            budget_bytes=self.budget_bytes, remaining_ms=self.remaining_ms, unavailable=list(self.unavailable),
            admits_live=False)


def queue_rollover_candidate(*, retained_jobs, unresolved_jobs, evict_acknowledged=False,
                             replay_pruned_keys=False):
    """NO pruning: bounded storage + eternal dedup for unbounded keys needs an ADR.

    Candidate policy is STOP at 128. Never evict an ACKed identity or invent an
    epoch-reset/replay window. Archive/tombstone/window decisions remain OPEN
    ARCHITECTURE DECISION; this function neither reads nor mutates queue state.
    """
    integer(retained_jobs, 0, 128, "queue_lifecycle")
    integer(unresolved_jobs, 0, retained_jobs, "queue_lifecycle")
    boolean(evict_acknowledged, "queue_lifecycle"); boolean(replay_pruned_keys, "queue_lifecycle")
    require(not evict_acknowledged and not replay_pruned_keys, "queue_lifecycle")
    return "HOLD_ARCHITECTURE_DECISION" if retained_jobs == 128 else "NO_ROLLOVER_NEEDED"
