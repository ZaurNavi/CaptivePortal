from dataclasses import asdict, replace

import pytest

from app.db_audit_coordinator import cgroup_v2 as cg
from app.db_audit_coordinator.operational_contracts import EvidenceError
from app.db_audit_coordinator.resource_admission import Geometry, cancel_condition, evaluate
from .test_operational_contracts import NOW, fixture_case, metric, stamp, uid


def test_budget_is_explicit_measured_sum_not_historical_multiplier():
    args = fixture_case()
    result = evaluate(*args, now_ns=NOW)
    assert result.status == "CANDIDATE_SAFE_SIMULATED"
    assert result.budget_bytes == 4096 + 568 + 4096 + 4096 + 4096 + 8192
    assert result.remaining_ms == 95 and result.admits_live is False
    assert not cancel_condition(*args, now_ns=NOW)
    assert evaluate(now_ns=NOW).status == "NOT_ADMITTED"
    assert cancel_condition(now_ns=NOW)


@pytest.mark.parametrize("field,value", [("child_memory_max", None), ("child_swap_max", None),
    ("child_memory_max", 0), ("child_memory_max", 200_000_000), ("child_swap_max", 1)])
def test_child_systemd_cap_and_zero_swap_must_be_independently_known(field, value):
    profile, before, after, geometry = fixture_case()
    result = evaluate(replace(profile, **{field: value}), before, after, geometry, now_ns=NOW)
    assert result.status == "NOT_ADMITTED"
    assert result.codes[0] in {"evidence_unknown", "limit_headroom"}


@pytest.mark.parametrize("field", ["main_bytes", "wal_bytes", "page_size", "page_count",
    "image_estimate_bytes", "backup_overhead_bytes", "validator_overhead_bytes", "margin_bytes",
    "other_live_rss_reserved_bytes"])
@pytest.mark.parametrize("value", [True, -1, 2**63, None, 0.5])
def test_geometry_rejects_wrong_type_unknown_negative_overflow(field, value):
    geometry = fixture_case()[3]
    with pytest.raises(EvidenceError):
        replace(geometry, **{field: value})


@pytest.mark.parametrize("change", [{"page_size": 513}, {"page_size": 256}, {"page_size": 131072},
    {"main_bytes": 4097}, {"page_count": 7}, {"image_estimate_bytes": 4095},
    {"wal_bytes": 1}, {"wal_bytes": 569}, {"margin_bytes": 1},
    {"image_estimate_bytes": 200_000_000}, {"other_live_rss_reserved_bytes": (1 << 63) - 1}])
def test_unavailable_invalid_or_unjustified_image_budget_refuses(change):
    profile, before, after, geometry = fixture_case()
    result = evaluate(profile, before, after, replace(geometry, **change), now_ns=NOW)
    assert result.status == "NOT_ADMITTED" and result.codes == ("ram_budget",)


@pytest.mark.parametrize("field", ["device", "inode", "generation", "locator_sha256",
    "writer_artifact_sha256", "auditor_artifact_sha256", "service_identity_sha256"])
def test_current_source_and_installed_identity_must_match_exactly(field):
    profile, before, after, geometry = fixture_case()
    value = 123 if field in {"device", "inode"} else uid(999) if field == "generation" else "f"*64
    geometry = replace(geometry, source=replace(geometry.source, **{field: value}))
    assert evaluate(profile, before, after, geometry, now_ns=NOW).codes == ("source_identity",)


@pytest.mark.parametrize("where", ["profile", "source", "geometry", "reservations", "before", "after"])
def test_historical_or_future_evidence_is_not_current_admission(where):
    profile, before, after, geometry = fixture_case()
    stale = stamp(500, offset=-2_000_000_000)
    if where == "profile":
        profile = replace(profile, config_stamp=replace(stale, kind="configured"))
    elif where == "source":
        profile = replace(profile, source=replace(profile.source, stamp=stale))
    elif where == "geometry":
        geometry = replace(geometry, stamp=stale)
    elif where == "reservations":
        geometry = replace(geometry, reservations_stamp=stale)
    elif where == "before":
        before = replace(before, stamp=stale)
    else:
        after = replace(after, stamp=replace(after.stamp, captured_ns=NOW + 1))
    assert evaluate(profile, before, after, geometry, now_ns=NOW).status == "NOT_ADMITTED"


@pytest.mark.parametrize("change", ["host", "ancestor", "rlimit", "live_reservation"])
def test_each_independent_headroom_is_enforced(change):
    profile, before, after, geometry = fixture_case()
    if change == "host":
        after = replace(after, proc_meminfo="MemTotal: 1048576 kB\nMemAvailable: 16 kB\n")
    elif change == "ancestor":
        before = metric(before, "memory.max", "10000001", node=1)
        after = metric(after, "memory.max", "10000001", node=1)
    elif change == "rlimit":
        after = replace(after, process=replace(after.process, address_limit="65537"))
    else:
        geometry = replace(geometry, other_live_rss_reserved_bytes=63_000_000)
    result = evaluate(profile, before, after, geometry, now_ns=NOW)
    assert result.status == "NOT_ADMITTED"
    assert result.codes[0] in {"ram_budget", "limit_headroom"}


@pytest.mark.parametrize("event", ["low", "high", "max", "oom", "oom_kill"])
def test_event_changes_including_reset_are_not_ignored(event):
    profile, before, after, geometry = fixture_case()
    original = dict(after.nodes[-1].files)["memory.events"].value
    for first, last in ((before, metric(after, "memory.events", original.replace(event + " 0\n", event + " 1\n"))),
                        (metric(before, "memory.events", original.replace(event + " 0\n", event + " 1\n")), after)):
        assert evaluate(profile, first, last, geometry, now_ns=NOW).codes == ("limit_headroom",)


@pytest.mark.parametrize("kind", ["psi", "psi_total", "swap", "reclaim", "missing_reclaim", "identity", "cap_change", "same_receipt", "time_reversed"])
def test_conservative_cancel_on_pressure_uncertainty_or_race(kind):
    profile, before, after, geometry = fixture_case()
    if kind in {"psi", "psi_total"}:
        raw = dict(after.nodes[-1].files)["memory.pressure"].value
        raw = raw.replace("avg10=0.00", "avg10=0.01", 1) if kind == "psi" else raw.replace("total=0", "total=1", 1)
        after = metric(after, "memory.pressure", raw)
    elif kind == "swap":
        after = replace(after, proc_vmstat=after.proc_vmstat.replace("pswpin 0", "pswpin 1"))
    elif kind == "reclaim":
        after = replace(after, proc_vmstat=after.proc_vmstat.replace("pgscan_direct 0", "pgscan_direct 1"))
    elif kind == "missing_reclaim":
        after = replace(after, proc_vmstat="pswpin 0\npswpout 0\n")
    elif kind == "identity":
        node = after.nodes[-1]; identity = replace(node.before, inode=9999)
        after = replace(after, nodes=after.nodes[:-1] + (replace(node, before=identity, after=identity),))
    elif kind == "cap_change":
        after = metric(after, "memory.max", "99999999", node=1)
    elif kind == "same_receipt":
        after = replace(after, stamp=before.stamp)
    else:
        after = replace(after, stamp=replace(after.stamp, captured_ns=before.stamp.captured_ns - 1))
    assert cancel_condition(profile, before, after, geometry, now_ns=NOW)
    assert evaluate(profile, before, after, geometry, now_ns=NOW).status == "NOT_ADMITTED"


@pytest.mark.parametrize("elapsed", [100_000_000, 100_000_001, 99_999_999])
def test_timeout_and_sub_millisecond_rounding_never_extend_budget(elapsed):
    profile, before, after, geometry = fixture_case()
    now = geometry.stamp.captured_ns + elapsed
    assert evaluate(profile, before, after, geometry, now_ns=now).codes == ("deadline",)
    assert cancel_condition(profile, before, after, geometry, now_ns=now)


def test_geometry_closed_schema_and_gate_phase_no_fallback():
    geometry = fixture_case()[3]
    assert Geometry.parse(asdict(geometry)) == geometry
    data = asdict(geometry); data["db_path"] = "synthetic-unapproved-target"
    with pytest.raises(EvidenceError):
        Geometry.parse(data)
    with pytest.raises(EvidenceError, match="source_identity"):
        replace(geometry, phase="before_global_gate")


def test_optional_counter_unavailability_remains_visible_in_result():
    profile, before, after, geometry = fixture_case()
    def no_peak(sample):
        node = sample.nodes[-1]
        files = tuple((key, cg.MetricRead(None, None, None) if key == "memory.peak" else value)
            for key, value in node.files)
        return replace(sample, nodes=sample.nodes[:-1] + (replace(node, files=files),))
    result = evaluate(profile, no_peak(before), no_peak(after), geometry, now_ns=NOW)
    assert result.status == "CANDIDATE_SAFE_SIMULATED" and result.unavailable == ("memory.peak",)
