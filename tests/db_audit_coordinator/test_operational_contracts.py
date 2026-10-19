"""Synthetic receipts only. Helpers here are shared by the four OP-A test files."""
from dataclasses import FrozenInstanceError, asdict, replace
import builtins
import json
import os
from pathlib import Path
import sqlite3
from uuid import UUID

import pytest

from app.db_audit_coordinator import cgroup_v2 as cg
from app.db_audit_coordinator import operational_contracts as oc
from app.db_audit_coordinator.resource_admission import Geometry, evaluate

NOW = 10_000_000_000


def uid(value):
    return str(UUID(int=value))


def stamp(value=1, *, kind="observed", offset=0, channel="offline_fixture"):
    return oc.Stamp(kind, channel, uid(value), NOW - 10_000_000 + offset)


def fixture_case(*, populated=1):
    task = oc.TaskIdentity(uid(11), uid(12), uid(13), uid(14), uid(15), 1001, 300, 2001, 400)
    job = "/audit/jobs/job-" + task.job_id
    paths = ("/", "/audit", "/audit/jobs", job)
    nodes = []
    for index, name in enumerate(paths):
        directory = oc.FileIdentity(7, index + 10, 0, 0o755, "directory", 2)
        values = {
            "cgroup.controllers": "cpu memory pids\n", "cgroup.subtree_control": "memory pids\n" if index < 3 else "\n",
            "cgroup.type": "domain\n", "cgroup.events": f"populated {populated if index == 3 else 1}\nfrozen 0\n",
            "cgroup.procs": ("2001\n" if populated else "") if index == 3 else f"{900+index}\n",
            "memory.max": ("max", "100000000", "80000000", "64000000")[index] + "\n",
            "memory.current": ("12000000", "10000000", "8000000", "1000000")[index] + "\n",
            "memory.swap.max": "max\n" if index < 3 else "0\n", "memory.swap.current": "0\n",
            "memory.events": "low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\n",
            "memory.peak": ("12001024", "10001024", "8001024", "1001024")[index] + "\n",
            "memory.pressure": "some avg10=0.00 avg60=0.00 avg300=0.00 total=0\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=0\n",
        }
        files = []
        for sequence, key in enumerate(sorted(cg.METRICS)):
            identity = oc.FileIdentity(7, 1000 + index * 100 + sequence, 0, 0o644, "file", 1)
            files.append((key, cg.MetricRead(values[key], identity, identity)))
        nodes.append(cg.NodeRead(name, directory, directory, tuple(files)))
    before = cg.CgroupSample("coordinator.cgroup-fixture.v1", uid(20), task,
        stamp(21, offset=7_000_000),
        "20 1 0:7 / /fixture-cgroup rw,nosuid,nodev,noexec - cgroup2 cgroup rw\n",
        "0::" + job + "\n", tuple(nodes), "MemTotal: 1048576 kB\nMemAvailable: 262144 kB\n",
        "pswpin 0\npswpout 0\npgscan_direct 0\npgsteal_direct 0\n",
        cg.ProcessRead("unlimited", "16777216", 65536, 16384, 8192))
    after = replace(before, stamp=stamp(22, offset=8_000_000))
    source = oc.SourceIdentity(8, 99, uid(30), "a"*64, "b"*64, "c"*64, "d"*64, stamp(31))
    fs = oc.FilesystemProof("ext4", True, True, True, True,
        oc.FileIdentity(9, 40, 0, 0o700, "directory", 2), stamp(41))
    policy = oc.ResourcePolicy(1_000_000_000, 100, 128_000_000, 4096, 8192, "e"*64)
    profile = oc.OperatorProfile("coordinator.operator-profile.offline.v1", oc.DOMAIN, oc.STORE,
        uid(20), task, "/audit", job, "/fixture-cgroup", nodes[-1].before,
        cg.ancestry_digest(tuple(nodes)), 0, 64_000_000, 0, stamp(42, kind="configured"), source, fs, policy)
    geometry = Geometry("coordinator.source-geometry.offline.v1", profile.profile_id, task, source,
        "offline_after_global_gate", 4096, 568, 512, 8, 4096, 4096, 4096, 4096, 8192,
        stamp(43, offset=5_000_000), stamp(44))
    return profile, before, after, geometry


def metric(sample, name, value, *, node=-1, before=None, after=None):
    nodes = list(sample.nodes)
    selected = nodes[node]
    files = []
    for key, receipt in selected.files:
        if key == name:
            receipt = replace(receipt, value=value,
                before=receipt.before if before is None else before,
                after=receipt.after if after is None else after)
        files.append((key, receipt))
    nodes[node] = replace(selected, files=tuple(files))
    return replace(sample, nodes=tuple(nodes))


def test_closed_roundtrip_profile_is_immutable_and_not_an_enable_switch():
    profile, *_ = fixture_case()
    assert oc.OperatorProfile.parse(asdict(profile)) == profile
    with pytest.raises(FrozenInstanceError):
        profile.child_memory_max = 1
    outcome = evaluate(*fixture_case(), now_ns=NOW)
    assert outcome.status == "CANDIDATE_SAFE_SIMULATED" and outcome.admits_live is False
    assert outcome.sanitized()["admits_live"] is False
    with pytest.raises(TypeError, match="offline_evidence_is_not_authority"):
        bool(outcome)


@pytest.mark.parametrize("key,value", [("enabled", True), ("path", "/arbitrary"), ("secret", "canary"), ("store", "settings")])
def test_unknown_profile_keys_never_form_authority(key, value):
    profile, *_ = fixture_case()
    data = asdict(profile); data[key] = value
    with pytest.raises(oc.EvidenceError, match="config_trust"):
        oc.OperatorProfile.parse(data)


@pytest.mark.parametrize("key", list(asdict(fixture_case()[0])))
def test_missing_profile_field_is_not_a_default(key):
    data = asdict(fixture_case()[0]); del data[key]
    with pytest.raises(oc.EvidenceError):
        oc.OperatorProfile.parse(data)


@pytest.mark.parametrize("channel", ["operator_review", "public_socket", "environment", "status_file", "UNKNOWN"])
def test_untrusted_or_live_provenance_never_grants_admission(channel):
    profile, before, after, geometry = fixture_case()
    profile = replace(profile, config_stamp=replace(profile.config_stamp, channel=channel))
    result = evaluate(profile, before, after, geometry, now_ns=NOW)
    assert result.status == "NOT_ADMITTED" and result.admits_live is False
    assert result.codes == ("config_trust",)


@pytest.mark.parametrize("kind", ["UNKNOWN", "observed"])
def test_configured_and_observed_are_not_interchangeable(kind):
    profile, before, after, geometry = fixture_case()
    profile = replace(profile, config_stamp=replace(profile.config_stamp, kind=kind))
    assert evaluate(profile, before, after, geometry, now_ns=NOW).status == "NOT_ADMITTED"


@pytest.mark.parametrize("bad", [True, False, -1, 2**63, 1.5, "1", None])
def test_numeric_contract_rejects_bool_wrong_type_and_overflow(bad):
    with pytest.raises(oc.EvidenceError):
        oc.integer(bad)


@pytest.mark.parametrize("field,value", [("domain", "other"), ("store_id", "settings"),
    ("schema", "v2"), ("profile_id", "not-a-uuid"), ("job_cgroup", "/escape/job"),
    ("job_cgroup", "/audit/../escape"), ("job_cgroup", "/audit//job"),
    ("mountpoint", "C:/escape"), ("mountpoint", "/" + "/".join(["a"]*18))])
def test_fixed_domain_store_and_path_contract(field, value):
    profile, *_ = fixture_case()
    with pytest.raises(oc.EvidenceError):
        replace(profile, **{field: value})


@pytest.mark.parametrize("change", [{"local_posix": False}, {"atomic_replace": False},
    {"file_fsync": False}, {"directory_fsync": False}, {"filesystem": "UNKNOWN"}])
def test_filesystem_receipts_do_not_assume_durability(change):
    profile, before, after, geometry = fixture_case()
    profile = replace(profile, filesystem=replace(profile.filesystem, **change))
    assert evaluate(profile, before, after, geometry, now_ns=NOW).codes == ("filesystem_trust",)


@pytest.mark.parametrize("ack,pruned", [(True, False), (False, True), (True, True)])
def test_queue_candidate_never_authorizes_eviction_or_pruned_replay(ack, pruned):
    with pytest.raises(oc.EvidenceError, match="queue_lifecycle"):
        oc.queue_rollover_candidate(retained_jobs=128, unresolved_jobs=1,
            evict_acknowledged=ack, replay_pruned_keys=pruned)


@pytest.mark.parametrize("unresolved", [0, 1, 32, 128])
def test_bounded_queue_rollover_is_open_architecture_decision_not_implemented(unresolved):
    assert oc.queue_rollover_candidate(retained_jobs=128, unresolved_jobs=unresolved) == "HOLD_ARCHITECTURE_DECISION"
    assert oc.queue_rollover_candidate(retained_jobs=127, unresolved_jobs=0) == "NO_ROLLOVER_NEEDED"


def test_sanitized_outcome_does_not_echo_identity_paths_or_payload():
    profile, before, after, geometry = fixture_case()
    result = evaluate(profile, before, after, geometry, now_ns=NOW)
    raw = json.dumps(result.sanitized())
    for private in (profile.job_cgroup, profile.task.job_id, profile.source.locator_sha256, "payload", "secret"):
        assert private not in raw
    assert set(result.sanitized()) == {"schema", "status", "codes", "budget_bytes", "remaining_ms", "unavailable", "admits_live"}


def test_evaluation_performs_no_io_and_existing_runtime_is_unwired(monkeypatch):
    import app.db_audit_coordinator.coordinator as coordinator
    import app.db_audit_coordinator.worker as worker
    from app.db_audit_coordinator import release_fence
    for module in (coordinator, worker):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "resource_admission" not in source and "release_fence" not in source
    args = fixture_case()
    def forbidden(*_args, **_kwargs):
        pytest.fail("offline evaluation must not read filesystem, source SQLite or process state")
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(os, "open", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    assert evaluate(*args, now_ns=NOW).status == "CANDIDATE_SAFE_SIMULATED"
    assert release_fence.check_release(now_ns=NOW).status == "HOLD"
