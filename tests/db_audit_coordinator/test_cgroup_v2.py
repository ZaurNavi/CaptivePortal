from dataclasses import replace

import pytest

from app.db_audit_coordinator import cgroup_v2 as cg
from app.db_audit_coordinator.operational_contracts import EvidenceError
from .test_operational_contracts import NOW, fixture_case, metric


def test_unbounded_root_is_not_a_cap_and_all_finite_ancestors_apply():
    profile, before, *_ = fixture_case()
    sample = metric(before, "memory.max", "9000000", node=1)
    sample = metric(sample, "memory.current", "8500000", node=1)
    facts = cg.attest(sample, profile, NOW)
    assert facts.nodes[0].cap is None
    assert facts.effective_cap == 9_000_000 and facts.headroom == 500_000
    assert facts.mem_available == 262144 * 1024
    assert facts.rlimit_headroom == 16777216 - 16384


@pytest.mark.parametrize("value", [None, "", "-1", "+1", "01", "1.0", "true", "9223372036854775808", "\x001"])
@pytest.mark.parametrize("name", ["memory.max", "memory.current", "memory.swap.max", "memory.swap.current"])
def test_invalid_required_kernel_counters_are_not_zero(name, value):
    profile, sample, *_ = fixture_case()
    with pytest.raises(EvidenceError):
        cg.attest(metric(sample, name, value), profile, NOW)


@pytest.mark.parametrize("name,value", [("memory.max", "max"), ("memory.swap.max", "max"),
    ("memory.swap.max", "1"), ("memory.swap.current", "1"), ("memory.current", "64000001"),
    ("memory.peak", "0"), ("cgroup.events", "populated 2\nfrozen 0"),
    ("cgroup.events", "populated 0\nfrozen 0"), ("cgroup.events", "populated 1\nfrozen 1"),
    ("cgroup.procs", "2001\n2001"), ("cgroup.procs", "0"), ("cgroup.procs", "\n".join(str(i+1) for i in range(33))),
    ("cgroup.type", "domain threaded"), ("cgroup.controllers", "cpu pids"),
    ("cgroup.controllers", "memory memory"), ("cgroup.controllers", "memory unapproved"),
    ("memory.events", "low 0\nhigh 0\nmax 0\noom 0"),
    ("memory.events", "low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\nsecret 0"),
    ("memory.events", "low 0\nlow 0\nhigh 0\nmax 0\noom 0\noom_kill 0")])
def test_inconsistent_incomplete_and_ambiguous_metrics_refuse(name, value):
    profile, sample, *_ = fixture_case()
    with pytest.raises(EvidenceError):
        cg.attest(metric(sample, name, value), profile, NOW)


def test_optional_peak_absence_is_explicit_not_zero():
    profile, sample, *_ = fixture_case()
    node = sample.nodes[-1]
    files = tuple((name, cg.MetricRead(None, None, None) if name == "memory.peak" else value)
        for name, value in node.files)
    sample = replace(sample, nodes=sample.nodes[:-1] + (replace(node, files=files),))
    facts = cg.attest(sample, profile, NOW)
    assert facts.nodes[-1].peak is None and facts.unavailable == ("memory.peak",)


@pytest.mark.parametrize("where,change", [("directory", {"kind": "symlink"}),
    ("directory", {"mode": 0o777}), ("directory", {"uid": 1}),
    ("file", {"kind": "symlink"}), ("file", {"mode": 0o666}),
    ("file", {"uid": 1}), ("file", {"links": 2})])
def test_symlinks_wrong_owner_writable_or_linked_evidence_rejected(where, change):
    profile, sample, *_ = fixture_case()
    node = sample.nodes[-1]
    if where == "directory":
        identity = replace(node.before, **change)
        sample = replace(sample, nodes=sample.nodes[:-1] + (replace(node, before=identity, after=identity),))
    else:
        receipt = dict(node.files)["memory.max"]
        identity = replace(receipt.before, **change)
        sample = metric(sample, "memory.max", receipt.value, before=identity, after=identity)
    with pytest.raises(EvidenceError):
        cg.attest(sample, profile, NOW)


@pytest.mark.parametrize("where", ["directory", "file"])
def test_replacement_mid_read_fails_closed(where):
    profile, sample, *_ = fixture_case()
    node = sample.nodes[-1]
    if where == "directory":
        node = replace(node, after=replace(node.after, inode=node.after.inode + 1))
        sample = replace(sample, nodes=sample.nodes[:-1] + (node,))
    else:
        receipt = dict(node.files)["memory.max"]
        sample = metric(sample, "memory.max", receipt.value, after=replace(receipt.after, inode=9999))
    with pytest.raises(EvidenceError, match="filesystem_trust"):
        cg.attest(sample, profile, NOW)


@pytest.mark.parametrize("change", ["missing", "duplicate", "escape", "new_identity", "wrong_device", "disabled_memory"])
def test_exact_ancestry_and_profile_identity_required(change):
    profile, sample, *_ = fixture_case()
    nodes = list(sample.nodes)
    if change == "missing":
        nodes.pop(1)
    elif change == "duplicate":
        nodes[1] = nodes[0]
    elif change == "escape":
        nodes[-1] = replace(nodes[-1], path="/audit/../escape")
    elif change in {"new_identity", "wrong_device"}:
        original = nodes[-1].before
        identity = replace(original, **({"inode": 9999} if change == "new_identity" else {"device": 20}))
        nodes[-1] = replace(nodes[-1], before=identity, after=identity)
    else:
        sample = metric(sample, "cgroup.subtree_control", "pids", node=1)
        nodes = list(sample.nodes)
    with pytest.raises(EvidenceError):
        cg.attest(replace(sample, nodes=tuple(nodes)), profile, NOW)


@pytest.mark.parametrize("mountinfo,membership", [
    ("", None), ("20 1 0:30 / /fixture-cgroup rw - cgroup cgroup rw", None),
    ("20 1 0:30 /subtree /fixture-cgroup rw - cgroup2 cgroup rw", None),
    ("20 1 0:30 / /elsewhere rw - cgroup2 cgroup rw", None),
    ("20 1 0:30 / /fixture-cgroup ro - cgroup2 cgroup ro", None),
    (None, "0::/other\n"), (None, "1:memory:/audit\n"), (None, "0::/audit\n0::/audit\n")])
def test_unified_expected_mount_and_membership_only(mountinfo, membership):
    profile, sample, *_ = fixture_case()
    sample = replace(sample, mountinfo=sample.mountinfo if mountinfo is None else mountinfo,
                     membership=sample.membership if membership is None else membership)
    with pytest.raises(EvidenceError, match="cgroup_topology"):
        cg.attest(sample, profile, NOW)


def test_duplicate_cgroup_mount_and_mixed_hierarchy_rejected():
    profile, sample, *_ = fixture_case()
    for line in (sample.mountinfo, "21 1 0:31 / /v1 rw - cgroup cgroup rw\n"):
        with pytest.raises(EvidenceError, match="cgroup_topology"):
            cg.attest(replace(sample, mountinfo=sample.mountinfo + line), profile, NOW)


@pytest.mark.parametrize("device", ["0:8", "1:7", "0:-1", "0:4294967296", "unknown", "0:7:8"])
def test_mount_device_identity_is_not_just_a_trusted_path(device):
    profile, sample, *_ = fixture_case()
    with pytest.raises(EvidenceError):
        cg.attest(replace(sample, mountinfo=sample.mountinfo.replace("0:7", device)), profile, NOW)


def test_replaced_ancestor_cannot_borrow_profile_despite_two_consistent_samples():
    profile, sample, *_ = fixture_case()
    nodes = list(sample.nodes)
    identity = replace(nodes[1].before, inode=9999)
    nodes[1] = replace(nodes[1], before=identity, after=identity)
    with pytest.raises(EvidenceError, match="filesystem_trust"):
        cg.attest(replace(sample, nodes=tuple(nodes)), profile, NOW)


@pytest.mark.parametrize("value", ["MemTotal: 100 kB", "MemTotal: 1 kB\nMemAvailable: 2 kB",
    "MemTotal: 10 kB\nMemAvailable: 1 kB\nMemAvailable: 1 kB", "MemTotal: 10 kB\nMemAvailable: -1 kB",
    "MemTotal: 10 kB\nMemAvailable: 1", "MemTotal: 10 kB\nMemAvailable: 1 MB"])
def test_incomplete_proc_memory_is_unknown_not_zero(value):
    profile, sample, *_ = fixture_case()
    with pytest.raises(EvidenceError):
        cg.attest(replace(sample, proc_meminfo=value), profile, NOW)


@pytest.mark.parametrize("field,value", [("address_limit", None), ("address_limit", "unknown"),
    ("address_limit", "1"), ("data_limit", "-1"), ("vms_bytes", True),
    ("rss_bytes", 999999999), ("data_bytes", 999999999)])
def test_unknown_or_inconsistent_process_limits_fail_closed(field, value):
    profile, sample, *_ = fixture_case()
    with pytest.raises(EvidenceError):
        cg.attest(replace(sample, process=replace(sample.process, **{field: value})), profile, NOW)


@pytest.mark.parametrize("value", ["", "some avg10=NaN avg60=0.00 avg300=0.00 total=0\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=0",
    "some avg10=101.00 avg60=0.00 avg300=0.00 total=0", "some avg10=0.00 avg10=0.00 avg60=0.00 total=0"])
def test_malformed_or_unavailable_psi_not_assumed_quiet(value):
    profile, sample, *_ = fixture_case()
    with pytest.raises(EvidenceError):
        cg.attest(metric(sample, "memory.pressure", value), profile, NOW)


def test_missing_metric_duplicate_metric_and_unknown_metric_rejected():
    profile, sample, *_ = fixture_case()
    node = sample.nodes[-1]
    variants = [node.files[:-1], node.files[:-1] + (node.files[0],),
                node.files[:-1] + (("unapproved", node.files[-1][1]),)]
    for files in variants:
        with pytest.raises(EvidenceError):
            cg.attest(replace(sample, nodes=sample.nodes[:-1] + (replace(node, files=files),)), profile, NOW)
