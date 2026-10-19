"""Pure bounded parser of SUPPLIED synthetic cgroup/proc read receipts.

No filesystem, /proc, cgroup, source DB or environment access. A receipt is
offline evidence, NOT authenticated live kernel attestation. OP-B must supply
trusted collection after the independently child-held global gate.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
import hashlib
import json
import re

from .operational_contracts import (EvidenceError, FileIdentity, MAX_INT, OperatorProfile,
    Stamp, TaskIdentity, integer, path, require, stamp_check)

METRICS = frozenset({"cgroup.controllers", "cgroup.subtree_control", "cgroup.type", "cgroup.events",
    "cgroup.procs", "memory.max", "memory.current", "memory.swap.max", "memory.swap.current",
    "memory.events", "memory.peak", "memory.pressure"})
EVENTS = frozenset({"low", "high", "max", "oom", "oom_kill"})
VMSTAT = ("pswpin", "pswpout", "pgscan_direct", "pgsteal_direct")
CONTROLLERS = frozenset({"memory", "pids", "cpu", "cpuset", "io", "rdma", "misc", "hugetlb"})


def text(value, maximum=16384):
    require(type(value) is str and len(value) <= maximum and "\x00" not in value, "evidence_unknown")
    return value


def number(value):
    value = text(value, 32).strip()
    require(re.fullmatch(r"0|[1-9][0-9]{0,18}", value) is not None, "evidence_unknown")
    return integer(int(value))


def limit(value):
    value = text(value, 32).strip()
    return None if value == "max" else number(value)


def counters(value, required, optional=()):
    result = {}
    for line in text(value).splitlines():
        pair = line.split()
        require(len(pair) == 2 and pair[0] in set(required) | set(optional)
            and pair[0] not in result, "evidence_unknown")
        result[pair[0]] = number(pair[1])
    require(set(required) <= result.keys(), "evidence_unknown")
    return result


def pressure(value):
    result = {}
    for line in text(value, 1024).splitlines():
        pair = line.split()
        require(len(pair) == 5 and pair[0] in {"some", "full"} and pair[0] not in result,
            "evidence_unknown")
        fields = {}
        for item in pair[1:]:
            pieces = item.split("=")
            require(len(pieces) == 2 and pieces[0] in {"avg10", "avg60", "avg300", "total"}
                and pieces[0] not in fields, "evidence_unknown")
            fields[pieces[0]] = pieces[1]
        require(len(fields) == 4, "evidence_unknown")
        avgs = []
        for key in ("avg10", "avg60", "avg300"):
            require(re.fullmatch(r"[0-9]{1,3}\.[0-9]{2}", fields[key]) is not None, "evidence_unknown")
            value = Decimal(fields[key])
            require(0 <= value <= 100, "evidence_unknown")
            avgs.append(value)
        result[pair[0]] = (any(value > 0 for value in avgs), number(fields["total"]))
    require(set(result) == {"some", "full"}, "evidence_unknown")
    return result


def meminfo(value):
    result = {}
    for line in text(value).splitlines():
        pieces = line.split()
        require(len(pieces) in {2, 3} and pieces[0].endswith(":")
            and re.fullmatch(r"[A-Za-z_()]+:", pieces[0]) is not None, "evidence_unknown")
        key = pieces[0][:-1]
        require(key not in result and (len(pieces) == 2 or pieces[2] == "kB"), "evidence_unknown")
        amount = number(pieces[1]) * (1024 if len(pieces) == 3 else 1)
        integer(amount)
        result[key] = (amount, len(pieces) == 3)
    require({"MemTotal", "MemAvailable"} <= result.keys(), "evidence_unknown")
    require(result["MemTotal"][1] and result["MemAvailable"][1]
        and 0 <= result["MemAvailable"][0] <= result["MemTotal"][0], "evidence_unknown")
    return result["MemAvailable"][0]


def vmstat(value):
    result = {}
    for line in text(value).splitlines():
        pair = line.split()
        require(len(pair) == 2 and re.fullmatch(r"[a-z0-9_]+", pair[0]) is not None
            and pair[0] not in result, "evidence_unknown")
        result[pair[0]] = number(pair[1])
    require(set(VMSTAT) <= result.keys(), "evidence_unknown")
    return tuple(result[key] for key in VMSTAT)


def mount(value, expected):
    found = []
    for line in text(value).splitlines():
        pieces = line.split()
        require(pieces.count("-") == 1, "cgroup_topology")
        separator = pieces.index("-")
        require(separator >= 6 and len(pieces) == separator + 4, "cgroup_topology")
        kind = pieces[separator + 1]
        require(kind != "cgroup", "cgroup_topology")
        if kind == "cgroup2":
            integer(number(pieces[0]), 1, code="cgroup_topology")
            integer(number(pieces[1]), code="cgroup_topology")
            device = pieces[2].split(":")
            require(len(device) == 2, "cgroup_topology")
            major = integer(number(device[0]), 0, (1 << 32) - 1, "cgroup_topology")
            minor = integer(number(device[1]), 0, (1 << 32) - 1, "cgroup_topology")
            # Linux dev_t encoding, evaluated portably without os.stat/makedev.
            encoded = ((major & 0xfff) << 8) | ((major & ~0xfff) << 32) | (minor & 0xff) | ((minor & ~0xff) << 12)
            integer(encoded, code="cgroup_topology")
            require(pieces[3] == "/" and pieces[4] == expected and "\\" not in pieces[4]
                and "rw" in pieces[5].split(","), "cgroup_topology")
            found.append(encoded)
    require(len(found) == 1, "cgroup_topology")
    return found[0]


@dataclass(frozen=True, repr=False)
class MetricRead:
    value: str | None
    before: FileIdentity | None
    after: FileIdentity | None

    def read(self, uid, device, *, optional=False):
        if self.value is None:
            require(optional and self.before is None and self.after is None, "evidence_unknown")
            return None
        text(self.value)
        require(type(self.before) is FileIdentity and type(self.after) is FileIdentity,
            "filesystem_trust")
        self.before.check("file", uid)
        require(self.before == self.after and self.before.device == device, "filesystem_trust")
        return self.value


@dataclass(frozen=True, repr=False)
class NodeRead:
    path: str
    before: FileIdentity
    after: FileIdentity
    files: tuple[tuple[str, MetricRead], ...]


@dataclass(frozen=True, repr=False)
class ProcessRead:
    address_limit: str
    data_limit: str
    vms_bytes: int
    data_bytes: int
    rss_bytes: int

    def headroom(self):
        available = []
        for raw, used in ((self.address_limit, self.vms_bytes), (self.data_limit, self.data_bytes)):
            integer(used)
            text(raw, 32)
            if raw != "unlimited":
                cap = number(raw)
                require(cap >= used, "limit_headroom")
                available.append(cap - used)
        integer(self.rss_bytes)
        require(self.rss_bytes <= self.vms_bytes and self.data_bytes <= self.vms_bytes, "limit_headroom")
        return min(available) if available else None


@dataclass(frozen=True, repr=False)
class CgroupSample:
    schema: str
    profile_id: str
    task: TaskIdentity
    stamp: Stamp
    mountinfo: str
    membership: str
    nodes: tuple[NodeRead, ...]
    proc_meminfo: str
    proc_vmstat: str
    process: ProcessRead


@dataclass(frozen=True, repr=False)
class NodeFacts:
    path: str
    identity: FileIdentity
    file_identities: tuple[FileIdentity | None, ...]
    cap: int | None
    current: int
    swap_cap: int | None
    swap_current: int
    events: tuple[int, ...]
    pressure_active: bool
    pressure_totals: tuple[int, int]
    populated: int
    procs: tuple[int, ...]
    peak: int | None


@dataclass(frozen=True, repr=False)
class CgroupFacts:
    task: TaskIdentity
    profile_id: str
    stamp: Stamp
    nodes: tuple[NodeFacts, ...]
    effective_cap: int
    headroom: int
    mem_available: int
    rlimit_headroom: int | None
    vm_counters: tuple[int, ...]
    unavailable: tuple[str, ...]


def ancestry_digest(nodes):
    require(type(nodes) is tuple and 1 <= len(nodes) <= 17, "cgroup_topology")
    require(all(type(node) is NodeRead and type(node.before) is FileIdentity for node in nodes), "filesystem_trust")
    for node in nodes:
        path(node.path)
    return hashlib.sha256(json.dumps([(node.path, asdict(node.before)) for node in nodes],
        sort_keys=True, separators=(",", ":")).encode("ascii")).hexdigest()


def attest(sample, profile, now_ns):
    require(type(profile) is OperatorProfile, "config_trust")
    profile.check(now_ns)
    require(type(sample) is CgroupSample and sample.schema == "coordinator.cgroup-fixture.v1",
        "cgroup_topology")
    require(sample.profile_id == profile.profile_id and type(sample.task) is TaskIdentity
        and sample.task == profile.task, "worker_reap")
    stamp_check(sample.stamp, now_ns, profile.policy.max_age_ns)
    mount_device = mount(sample.mountinfo, profile.mountpoint)
    require(mount_device == profile.job_cgroup_identity.device, "filesystem_trust")
    require(text(sample.membership, 1024).splitlines() == ["0::" + profile.job_cgroup], "cgroup_topology")
    components = profile.job_cgroup[1:].split("/")
    expected = ["/"] + ["/" + "/".join(components[:index]) for index in range(1, len(components) + 1)]
    require(type(sample.nodes) is tuple and len(sample.nodes) == len(expected) <= 17, "cgroup_topology")
    facts, unavailable = [], []
    for index, node in enumerate(sample.nodes):
        require(type(node) is NodeRead and path(node.path) == expected[index], "cgroup_topology")
        require(type(node.before) is FileIdentity and type(node.after) is FileIdentity
            and node.before == node.after, "filesystem_trust")
        node.before.check("directory", profile.owner_uid)
        require(not facts or facts[0].identity.device == node.before.device, "filesystem_trust")
        require(type(node.files) is tuple and len(node.files) == len(METRICS), "cgroup_topology")
        require(all(type(pair) is tuple and len(pair) == 2 and type(pair[0]) is str
            and type(pair[1]) is MetricRead for pair in node.files), "cgroup_topology")
        entries = dict(node.files)
        require(len(entries) == len(node.files) and set(entries) == METRICS, "cgroup_topology")
        values = {name: item.read(profile.owner_uid, node.before.device, optional=name == "memory.peak")
                  for name, item in entries.items()}
        controllers = values["cgroup.controllers"].split()
        subtree = values["cgroup.subtree_control"].split()
        require(len(controllers) == len(set(controllers)) and set(controllers) <= CONTROLLERS and "memory" in controllers
            and len(subtree) == len(set(subtree)) and set(subtree) <= CONTROLLERS, "cgroup_topology")
        require(index == len(sample.nodes) - 1 or "memory" in subtree, "cgroup_topology")
        require(values["cgroup.type"].strip() == "domain", "cgroup_topology")
        cap = limit(values["memory.max"])
        current = number(values["memory.current"])
        swap_cap = limit(values["memory.swap.max"])
        swap_current = number(values["memory.swap.current"])
        require((cap is None or current <= cap) and (swap_cap is None or swap_current <= swap_cap), "limit_headroom")
        events = counters(values["memory.events"], EVENTS, {"oom_group_kill"})
        # Missing optional oom_group_kill is explicitly represented by absence;
        # standard mandatory event counters may never be invented as zero.
        event_values = tuple(events[key] for key in sorted(events))
        psi = pressure(values["memory.pressure"])
        populated = counters(values["cgroup.events"], {"populated", "frozen"})
        require(populated["populated"] in {0, 1} and populated["frozen"] == 0, "cgroup_topology")
        raw_procs = values["cgroup.procs"].splitlines()
        require(len(raw_procs) <= 32, "cgroup_topology")
        procs = tuple(integer(number(raw), 1, (1 << 31) - 1) for raw in raw_procs)
        require(len(set(procs)) == len(procs) and (populated["populated"] or not procs), "cgroup_topology")
        peak = None if values["memory.peak"] is None else number(values["memory.peak"])
        require(peak is None or peak >= current, "evidence_unknown")
        if peak is None:
            unavailable.append("memory.peak")
        facts.append(NodeFacts(node.path, node.before, tuple(entries[key].before for key in sorted(entries)),
            cap, current, swap_cap, swap_current, event_values,
            any(value[0] for value in psi.values()), (psi["some"][1], psi["full"][1]),
            populated["populated"], procs, peak))
    leaf = facts[-1]
    require(leaf.identity == profile.job_cgroup_identity
        and ancestry_digest(sample.nodes) == profile.cgroup_ancestry_sha256, "filesystem_trust")
    require(leaf.cap == profile.child_memory_max and leaf.cap is not None
        and leaf.swap_cap == profile.child_swap_max == 0, "limit_headroom")
    require(all(node.swap_current == 0 for node in facts), "limit_headroom")
    require(all(parent.current >= child.current for parent, child in zip(facts, facts[1:])), "evidence_unknown")
    limits = [node.cap for node in facts if node.cap is not None]
    require(bool(limits), "limit_headroom")
    headroom = min(node.cap - node.current for node in facts if node.cap is not None)
    require(type(sample.process) is ProcessRead, "evidence_unknown")
    return CgroupFacts(sample.task, sample.profile_id, sample.stamp, tuple(facts), min(limits), headroom,
        meminfo(sample.proc_meminfo), sample.process.headroom(), vmstat(sample.proc_vmstat), tuple(unavailable))


def stable(before, after):
    require(before.task == after.task and before.profile_id == after.profile_id
        and before.stamp.receipt_id != after.stamp.receipt_id
        and before.stamp.captured_ns < after.stamp.captured_ns, "evidence_unknown")
    require(len(before.nodes) == len(after.nodes), "cgroup_topology")
    for old, new in zip(before.nodes, after.nodes):
        require((old.path, old.identity, old.file_identities, old.cap, old.swap_cap)
            == (new.path, new.identity, new.file_identities, new.cap, new.swap_cap), "filesystem_trust")
        require(old.events == new.events and old.pressure_totals == new.pressure_totals
            and not old.pressure_active and not new.pressure_active, "limit_headroom")
    require(before.vm_counters == after.vm_counters, "limit_headroom")
