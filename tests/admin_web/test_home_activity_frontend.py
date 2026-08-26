from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


NODE = shutil.which("node")
if not NODE:
    bundled = Path(
        r"C:\Users\Zaur Navi\.cache\codex-runtimes\codex-primary-runtime"
        r"\dependencies\node\bin\node.exe"
    )
    if bundled.exists():
        NODE = str(bundled)


def test_home_activity_real_node_contract(tmp_path):
    if not NODE:
        pytest.fail("Node.js is mandatory for the Home Activity frontend gate")
    source_path = (
        Path(__file__).parents[2]
        / "app" / "admin_web" / "static" / "admin.js"
    )
    script = tmp_path / "home-activity-contract.js"
    script.write_text(
        "global.window = {};\n" + source_path.read_text(encoding="utf-8") + r'''
const api = window.CaptivPortalHomeActivityTest;
function assert(value, message) { if (!value) throw new Error(message); }
function copy(value) { return JSON.parse(JSON.stringify(value)); }
const site = "0123456789abcdef01234567";
function coverage() {
  return {coverage_from_utc: "2025-01-01T00:00:00.000Z",
    coverage_through_utc: "2026-08-25T08:00:00.000Z",
    covered_from_utc: "2026-08-24T20:00:00.000Z",
    covered_through_utc: "2026-08-25T08:00:00.000Z",
    fully_covered: true, status: "complete", quality_reasons: []};
}
function payload(kind = "today") {
  return {api_version: "admin.read.v1", site_id: site, result: {
    evaluated_at_utc: "2026-08-25T08:00:00.000Z", timezone: "Asia/Baku",
    guest_ssids: ["Zefer_Parki"],
    range: {requested: {kind}, resolved: {
      from_utc: "2026-08-24T20:00:00.000Z", to_utc: "2026-08-25T08:00:00.000Z",
      from_local: "2026-08-25T00:00:00+04:00",
      to_local_exclusive: "2026-08-26T00:00:00+04:00", timezone: "Asia/Baku"}},
    authorized_visits: {value: 4, status: "complete",
      cohort: "visit_opening_authorization", source_kind: "visit_lifecycle",
      verified_visit_count: 4, integrity_anomaly_count: 0, coverage: coverage(),
      earliest_persisted_evidence_at: "2026-08-24T21:00:00.000Z",
      latest_persisted_evidence_at: "2026-08-25T07:00:00.000Z"},
    traffic: {bytes: 0, status: "complete", estimated: true,
      attribution: "completed_session_end", source_kind: "omada_offline_reported_traffic",
      eligible_terminal_event_count: 2, included_fingerprint_count: 2,
      unmatched_included_event_count: 1, pending_event_count: 0,
      invalid_event_count: 0, missing_traffic_count: 0,
      missing_controller_time_count: 0, semantic_duplicate_count: 0,
      other_excluded_event_count: 0,
      reader_watermark_at: "2026-08-25T08:00:00.000Z",
      ingestion_freshness: "fresh", coverage: coverage(),
      earliest_persisted_evidence_at: "2026-08-24T22:00:00.000Z",
      latest_persisted_evidence_at: "2026-08-25T06:00:00.000Z"},
    next_site_midnight_utc: kind === "today" ? "2026-08-25T20:00:00.000Z" : null}};
}

assert(api.validateActivity(payload(), site, "today") !== null, "valid Today accepted");
assert(api.bytes(0) === "0 B" && api.bytes(null) === "—", "zero and unavailable differ");
assert(api.coverageText("Traffic", payload().result.traffic) === "Traffic complete", "complete coverage is explicit");
const partialCoverage = payload().result.traffic;
partialCoverage.status = "partial"; partialCoverage.coverage.status = "partial";
partialCoverage.coverage.fully_covered = false;
partialCoverage.coverage.quality_reasons = ["requested_before_coverage_start"];
assert(api.coverageText("Traffic", partialCoverage).includes("proven 2026-08-24T20:00:00.000Z"), "partial coverage shows proven intersection");
const selected = payload("preset");
assert(api.validateActivity(selected, site, "preset") !== null, "valid selected accepted");
assert(api.selectionDynamic("last_24h") && api.selectionDynamic("current_month"), "rolling selections refresh");
assert(!api.selectionDynamic("yesterday") && !api.selectionDynamic("custom"), "finished selections stay static");

for (const mutate of [
  (value) => { value.result.guest_ssids = []; },
  (value) => { value.result.authorized_visits.value = 5; },
  (value) => { value.result.authorized_visits.coverage.status = "unknown"; },
  (value) => { value.result.traffic.estimated = false; },
  (value) => { value.result.traffic.semantic_duplicate_count = 1; },
  (value) => { value.result.traffic.pending_event_count = -1; },
  (value) => { value.result.range.resolved.to_utc = "2027-01-01T00:00:00.000Z"; },
  (value) => { value.result.next_site_midnight_utc = "not-a-time"; },
]) {
  const malformed = copy(payload()); mutate(malformed);
  assert(api.validateActivity(malformed, site, "today") === null, "malformed response rejected atomically");
}

const preview = {api_version: "admin.read.v1", site_id: site, result: {
  timezone: "America/New_York", requested: {period: "custom"},
  resolved: {from_utc: "2026-11-01T05:00:00.000Z", to_utc: "2026-11-01T07:00:00.000Z",
    from_local: "2026-11-01T01:00:00-04:00", to_local_exclusive: "2026-11-01T02:00:00-05:00"},
  can_apply: true, validation_reason: null}};
assert(api.validatePreview(preview, site) !== null, "strict preview accepted");
preview.result.validation_reason = "clipped";
assert(api.validatePreview(preview, site) === null, "hidden clipping cannot pass validation");

const todayState = {nextEligibleAt: 1000, failureCount: 0, autoRefresh: true};
const staticState = {nextEligibleAt: 0, failureCount: 1, autoRefresh: false};
assert(api.nextEligible(todayState, staticState) === 1000, "static failure cannot create polling loop");
assert(!api.eligible(staticState, false, 5000), "static range never retries automatically");
assert(api.eligible(staticState, true, 5000), "manual retry observes elapsed backoff");
staticState.nextEligibleAt = 6000;
assert(!api.eligible(staticState, true, 5000), "manual retry cannot bypass backoff");
const todayFailure = {nextEligibleAt: 0, failureCount: 0, autoRefresh: true, disabled: false};
const selectedFailure = {nextEligibleAt: 0, failureCount: 0, autoRefresh: true, disabled: false};
assert(api.failureTransition(selectedFailure, {kind: "unavailable", status: 429, retryAfter: 120}, 60, 1000, 0.5) === 125, "429 uses Retry-After and bounded jitter");
assert(todayFailure.failureCount === 0 && todayFailure.nextEligibleAt === 0, "Selected failure leaves Today state untouched");
api.failureTransition(selectedFailure, {kind: "disabled", status: 404, retryAfter: 0}, 60, 2000, 0);
assert(selectedFailure.disabled && !api.eligible(selectedFailure, true, 999999), "feature-disabled source remains stopped until reload");
const yesterdayFailure = {nextEligibleAt: 100000, manualEligibleAt: 5000, failureCount: 1, autoRefresh: true, disabled: false};
assert(!api.eligible(yesterdayFailure, false, 6000), "Yesterday failure does not poll before Site midnight");
assert(api.eligible(yesterdayFailure, true, 6000), "Yesterday remains manually retryable after backoff");

const owner = {generation: 1, controller: null};
const first = new AbortController(); const second = new AbortController();
assert(api.claim(owner, first, 1), "generation claims controller");
api.release(owner, second);
assert(owner.controller === first, "foreign completion cannot clear active controller");
assert(api.abort(owner, "hidden") && first.signal.aborted && owner.controller === null, "hidden abort cancels owner");

(async () => {
  const coordinator = window.CaptivPortalHomeTrafficTest;
  const calls = [];
  const activity = {
    run: async () => calls.push("today+selected"),
    runToday: async () => calls.push("today"),
  };
  await coordinator.runActivityPhase(activity, false, false);
  await coordinator.runActivityPhase(activity, true, false);
  assert(JSON.stringify(calls) === '["today+selected","today"]', "queued picker Apply suppresses duplicate Selected phase");
  console.log("home activity contract passed");
})().catch((error) => { console.error(error); process.exitCode = 1; });
''',
        encoding="utf-8",
    )
    env = {**os.environ, "NODE_NO_WARNINGS": "1"}
    checked = subprocess.run(
        [NODE, "--check", str(source_path)], capture_output=True, text=True,
        timeout=15, check=False, env=env,
    )
    completed = subprocess.run(
        [NODE, str(script)], capture_output=True, text=True,
        timeout=15, check=False, env=env,
    )
    assert checked.returncode == 0, checked.stderr
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "home activity contract passed" in completed.stdout


def test_home_activity_static_security_and_coordinator_contract():
    root = Path(__file__).parents[2]
    source = (root / "app" / "admin_web" / "static" / "admin.js").read_text(
        encoding="utf-8"
    )
    html = (root / "app" / "admin_web" / "templates" / "admin" / "home.html").read_text(
        encoding="utf-8"
    )
    assert "CaptivPortalHomeActivityCoordinator" in source
    assert "requestActivitySelected" in source
    assert "Promise.allSettled" in source
    assert "setInterval" not in source
    assert "localStorage" not in source
    assert "sessionStorage" not in source
    assert "indexedDB" not in source
    assert "innerHTML" not in source
    assert "Estimated" in html
    assert "Omada" not in source
    assert '<option value="last_24h">' in html
    for period in (
        "yesterday", "last_48h", "last_7d", "current_month", "last_30d",
        "custom",
    ):
        assert f'value="{period}"' in html
    assert 'id="activity-picker"' in html and "hidden" in html
    assert 'event.key === "Escape"' in source
    assert 'picker.elements.period.focus()' in source
    assert 'pickerOpener.focus()' in source
    assert "restoreAppliedDraft(); closePicker();" in source
