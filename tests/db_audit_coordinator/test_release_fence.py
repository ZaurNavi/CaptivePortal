from dataclasses import replace

import pytest

from app.db_audit_coordinator.release_fence import OwnershipReceipt, ReapReceipt, check_release
from .test_operational_contracts import NOW, fixture_case, metric, stamp, uid


def release_case():
    profile, before, after, _ = fixture_case(populated=0)
    reap = ReapReceipt("coordinator.wait-receipt.offline.v1", profile.task, profile.profile_id,
        "waitpid", profile.task.supervisor_pid, profile.task.supervisor_start_ticks,
        profile.task.worker_pid, profile.task.worker_start_ticks, True, "exited", 0,
        stamp(80, offset=6_000_000))
    owners = OwnershipReceipt("coordinator.closed-ownership.offline.v1", profile.task, profile.profile_id,
        True, 0, 0, True, stamp(81, offset=9_000_000))
    return profile, reap, before, after, owners


def test_positive_reap_empty_dedicated_group_and_closed_ownership_only_simulated_release():
    result = check_release(*release_case(), now_ns=NOW)
    assert result.status == "RELEASE_CONFIRMED_SIMULATED" and result.codes == ()
    assert result.admits_live is False
    with pytest.raises(TypeError):
        bool(result)


@pytest.mark.parametrize("field,value", [("reaped", False), ("reaped", 1), ("mechanism", "pid_missing"),
    ("mechanism", "TTL"), ("mechanism", "mtime"), ("mechanism", "poll"),
    ("observed_pid", 9999), ("observed_start_ticks", 9999), ("waiter_pid", 9999),
    ("waiter_start_ticks", 9999), ("exit_value", True), ("exit_value", -1),
    ("exit_kind", "unknown"), ("profile_id", uid(999))])
def test_no_positive_actual_wait_receipt_means_orphan_hold(field, value):
    profile, reap, before, after, owners = release_case()
    result = check_release(profile, replace(reap, **{field: value}), before, after, owners, now_ns=NOW)
    assert result.status == "HOLD" and result.admits_live is False


@pytest.mark.parametrize("missing", ["profile", "reap", "before", "after", "ownership"])
def test_missing_receipt_never_falls_back_to_pid_or_memory(missing):
    args = list(release_case())
    args[["profile", "reap", "before", "after", "ownership"].index(missing)] = None
    assert check_release(*args, now_ns=NOW).status == "HOLD"


@pytest.mark.parametrize("field", ["queue_id", "job_id", "attempt_id", "epoch", "run_id", "worker_start_ticks"])
def test_pid_reuse_changed_epoch_or_competing_queue_cannot_borrow_reap(field):
    profile, reap, before, after, owners = release_case()
    other = replace(profile.task, **{field: 9999 if field == "worker_start_ticks" else uid(999)})
    result = check_release(profile, replace(reap, task=other), before, after, owners, now_ns=NOW)
    assert result.status == "HOLD" and result.codes == ("worker_reap",)


@pytest.mark.parametrize("field,value", [("snapshot_closed", False), ("snapshot_closed", 1),
    ("snapshot_owners", 1), ("snapshot_owners", True), ("snapshot_owners", -1),
    ("surviving_descendants", 1), ("ownership_verified", False), ("ownership_verified", None)])
def test_unknown_or_surviving_ram_owner_blocks_next_image(field, value):
    profile, reap, before, after, owners = release_case()
    result = check_release(profile, reap, before, after, replace(owners, **{field: value}), now_ns=NOW)
    assert result.status == "HOLD"


@pytest.mark.parametrize("scenario", ["supervisor_dead_worker_alive", "reaped_but_descendant_populated",
    "low_current_still_populated", "cache_drop_without_reap", "vanished_group", "replacement", "mid_read_change"])
def test_orphan_and_incomplete_cgroup_proof_do_not_release(scenario):
    profile, reap, before, after, owners = release_case()
    if scenario == "supervisor_dead_worker_alive":
        reap = replace(reap, reaped=False)
        after = metric(after, "cgroup.events", "populated 1\nfrozen 0")
        after = metric(after, "cgroup.procs", str(profile.task.worker_pid))
    elif scenario in {"reaped_but_descendant_populated", "low_current_still_populated"}:
        after = metric(after, "cgroup.events", "populated 1\nfrozen 0")
        if scenario == "low_current_still_populated":
            after = metric(after, "memory.current", "0")
    elif scenario == "cache_drop_without_reap":
        before = metric(before, "memory.current", "0")
        after = metric(after, "memory.current", "0")
        reap = None
    elif scenario == "vanished_group":
        after = replace(after, nodes=after.nodes[:-1])
    elif scenario == "replacement":
        for name in ("before", "after"):
            sample = before if name == "before" else after
            node = sample.nodes[-1]; changed = replace(node.before, inode=9999)
            sample = replace(sample, nodes=sample.nodes[:-1] + (replace(node, before=changed, after=changed),))
            if name == "before": before = sample
            else: after = sample
    else:
        node = after.nodes[-1]
        after = replace(after, nodes=after.nodes[:-1] + (replace(node, after=replace(node.after, device=99)),))
    assert check_release(profile, reap, before, after, owners, now_ns=NOW).status == "HOLD"


def test_retained_page_cache_is_not_a_live_snapshot_and_zero_cache_is_not_release():
    args = release_case()
    assert dict(args[3].nodes[-1].files)["memory.current"].value.strip() == "1000000"
    assert check_release(*args, now_ns=NOW).status == "RELEASE_CONFIRMED_SIMULATED"
    profile, reap, before, after, owners = args
    before = metric(before, "memory.current", "0")
    after = metric(after, "memory.current", "0")
    assert check_release(profile, None, before, after, owners, now_ns=NOW).status == "HOLD"


@pytest.mark.parametrize("where", ["reap", "owners", "profile", "sample", "wrong_order", "borrowed_receipt"])
def test_stale_untrusted_or_temporally_invalid_release_receipts_hold(where):
    profile, reap, before, after, owners = release_case()
    if where == "reap":
        reap = replace(reap, stamp=replace(reap.stamp, channel="status_file"))
    elif where == "owners":
        owners = replace(owners, stamp=stamp(99, offset=-2_000_000_000))
    elif where == "profile":
        profile = replace(profile, config_stamp=stamp(98, kind="configured", offset=-2_000_000_000))
    elif where == "sample":
        after = replace(after, stamp=replace(after.stamp, channel="UNKNOWN"))
    elif where == "wrong_order":
        reap = replace(reap, stamp=stamp(99, offset=9_500_000))
    else:
        owners = replace(owners, stamp=after.stamp)
    assert check_release(profile, reap, before, after, owners, now_ns=NOW).status == "HOLD"


def test_signal_exit_can_prove_release_but_never_a_passed_audit():
    profile, reap, before, after, owners = release_case()
    result = check_release(profile, replace(reap, exit_kind="signaled", exit_value=9), before, after, owners, now_ns=NOW)
    assert result.status == "RELEASE_CONFIRMED_SIMULATED"
    assert "passed" not in str(result.sanitized()).lower() and result.admits_live is False
