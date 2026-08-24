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


def test_home_traffic_node_state_machine_and_validation(tmp_path):
    if not NODE:
        pytest.fail("Node.js is mandatory for the Home Traffic frontend gate")
    source_path = (
        Path(__file__).parents[2]
        / "app" / "admin_web" / "static" / "admin.js"
    )
    source = source_path.read_text(encoding="utf-8")
    script = tmp_path / "home-traffic-contract.js"
    script.write_text(
        "global.window = {};\n" + source + r'''
const api = window.CaptivPortalHomeTrafficTest;
const live = window.CaptivPortalHomeLiveTest;
function assert(value, message) { if (!value) throw new Error(message); }
function copy(value) { return JSON.parse(JSON.stringify(value)); }
const site = "0123456789abcdef01234567";
const cycle = "10000000-0000-4000-8000-000000000001";
function snapshot() {
  return {source_kind: "observation_ap_dynamic", cycle_id: cycle, complete: true,
    evaluated_at: "2026-08-24T13:00:00.000Z", observed_at: "2026-08-24T12:59:42.000Z",
    newest_observed_at: "2026-08-24T12:59:55.000Z", age_seconds: 18,
    source_skew_seconds: 13, freshness_status: "fresh", freshness_reason: "within_freshness_window",
    latest_attempt_state: "completed", latest_attempt_result: "success",
    latest_attempt_at: "2026-08-24T12:59:57.000Z", using_previous_complete_snapshot: false,
    selected_source: "wired", selection_reason: "primary_full_coverage", empty_population: false};
}
function summary() {
  return {api_version: "admin.read.v1", site_id: site, result: {
    snapshot: snapshot(),
    freshness_policy: {fresh_max_age_seconds: 90, unavailable_after_seconds: 180, max_ap_skew_seconds: 60},
    traffic: {download_mbps: 42.125, upload_mbps: 6.25, total_mbps: 48.375, unit: "Mbps"},
    source_selection: {primary_source: "wired", selected_source: "wired", selection_reason: "primary_full_coverage", wired_pair_valid_ap_count: 2, lan_pair_valid_ap_count: 2, source_mixing_allowed: false},
    coverage: {coverage_status: "complete", empty_population: false, total_ap_count: 2,
      valid_rate_ap_count: 2, valid_download_ap_count: 2, valid_upload_ap_count: 2,
      missing_rate_ap_count: 0, stale_ap_count: 0, unavailable_ap_count: 0,
      reset_ap_count: 0, gap_rejected_ap_count: 0, no_baseline_ap_count: 0,
      source_unavailable_ap_count: 0, invalid_elapsed_ap_count: 0, coverage_reasons: []}}};
}
function page(result) {
  return {api_version: "admin.read.v1", site_id: site, result: {
    snapshot: {source_kind: "observation_ap_dynamic", cycle_id: cycle,
      evaluated_at: "2026-08-24T13:00:00.000Z", observed_at: "2026-08-24T12:59:42.000Z",
      newest_observed_at: "2026-08-24T12:59:55.000Z", age_seconds: 18,
      freshness_status: "fresh", freshness_reason: "within_freshness_window"},
    freshness_policy: {fresh_max_age_seconds: 90, unavailable_after_seconds: 180},
    source_selection: {selected_source: "wired", selection_reason: "primary_full_coverage", source_mixing_allowed: false},
    items: [{ap_mac: "AA:BB:CC:DD:EE:FF", name: "AP-1", download_mbps: 0,
      upload_mbps: 0, total_mbps: 0, download_reason: "ok", upload_reason: "ok",
      rate_status: "valid", observed_at: "2026-08-24T12:59:42.000Z", age_seconds: 18,
      selected_source: "wired"}]}, page: {limit: 100, next_cursor: null, cycle_id: cycle, selected_source: "wired"}};
}

const valid = summary();
assert(api.validateTrafficSummary(valid, site) !== null, "valid summary accepted");
assert(api.formatMbps(0) === "0.00 Mbps" && api.formatMbps(null) === "—", "exact zero is preserved");
assert(api.trafficDisplay(valid.result, "fresh").download === "42.13 Mbps", "numeric current display");
assert(api.trafficDisplay(valid.result, "unavailable").download === "—", "local unavailable hides numeric values");
assert(api.trafficFreshness(valid.result.snapshot, valid.result.freshness_policy, 1000, 73001) === "stale", "fresh progresses to stale");
assert(api.trafficFreshness(valid.result.snapshot, valid.result.freshness_policy, 1000, 163001) === "unavailable", "stale progresses to unavailable");
assert(api.trafficFreshness(valid.result.snapshot, valid.result.freshness_policy, 1000, 163000) === "stale", "unavailable boundary is strict greater-than");

const partial = summary();
partial.result.coverage.coverage_status = "partial";
partial.result.coverage.coverage_reasons = ["missing_direction"];
partial.result.coverage.valid_rate_ap_count = 1;
partial.result.coverage.valid_upload_ap_count = 1;
partial.result.coverage.missing_rate_ap_count = 1;
partial.result.traffic.upload_mbps = null; partial.result.traffic.total_mbps = null;
assert(api.validateTrafficSummary(partial, site) !== null, "partial direction accepted");
assert(api.trafficDisplay(partial.result, "fresh").label === "Observed subtotal", "partial values are labeled");

const empty = summary();
empty.result.snapshot.empty_population = true;
empty.result.snapshot.selection_reason = "empty_population";
empty.result.source_selection.selection_reason = "empty_population";
empty.result.coverage.empty_population = true; empty.result.coverage.total_ap_count = 0;
["valid_rate_ap_count", "valid_download_ap_count", "valid_upload_ap_count"].forEach((key) => { empty.result.coverage[key] = 0; });
empty.result.source_selection.wired_pair_valid_ap_count = 0; empty.result.source_selection.lan_pair_valid_ap_count = 0;
empty.result.traffic = {download_mbps: 0, upload_mbps: 0, total_mbps: 0, unit: "Mbps"};
assert(api.validateTrafficSummary(empty, site) !== null, "empty-cycle exact zero accepted");

const invalidEmptyLan = copy(empty);
invalidEmptyLan.result.snapshot.selected_source = "lan";
invalidEmptyLan.result.source_selection.selected_source = "lan";
assert(api.validateTrafficSummary(invalidEmptyLan, site) === null, "empty cycle rejects LAN selection");
const invalidEmptyReason = copy(empty);
invalidEmptyReason.result.snapshot.selection_reason = "primary_full_coverage";
invalidEmptyReason.result.source_selection.selection_reason = "primary_full_coverage";
assert(api.validateTrafficSummary(invalidEmptyReason, site) === null, "empty cycle rejects non-empty selection reason");
const invalidNonemptyReason = summary();
invalidNonemptyReason.result.snapshot.selection_reason = "empty_population";
invalidNonemptyReason.result.source_selection.selection_reason = "empty_population";
assert(api.validateTrafficSummary(invalidNonemptyReason, site) === null, "non-empty cycle rejects empty selection reason");
const invalidEmptyCount = copy(empty);
invalidEmptyCount.result.coverage.total_ap_count = 1;
invalidEmptyCount.result.coverage.missing_rate_ap_count = 1;
assert(api.validateTrafficSummary(invalidEmptyCount, site) === null, "empty cycle rejects nonzero counts");
const invalidEmptyNull = copy(empty);
invalidEmptyNull.result.traffic.download_mbps = null;
invalidEmptyNull.result.traffic.total_mbps = null;
assert(api.validateTrafficSummary(invalidEmptyNull, site) === null, "empty cycle rejects null traffic");
const invalidEmptyValue = copy(empty);
invalidEmptyValue.result.traffic.download_mbps = 1;
invalidEmptyValue.result.traffic.total_mbps = 1;
assert(api.validateTrafficSummary(invalidEmptyValue, site) === null, "empty cycle rejects nonzero traffic");

const missing = summary();
Object.assign(missing.result.snapshot, {cycle_id: null, complete: false, observed_at: null,
  newest_observed_at: null, age_seconds: null, source_skew_seconds: null,
  freshness_status: "unavailable", freshness_reason: "no_complete_snapshot",
  selected_source: null, selection_reason: "no_complete_snapshot", empty_population: false,
  latest_attempt_state: "none", latest_attempt_result: null, latest_attempt_at: null});
missing.result.source_selection = {primary_source: "wired", selected_source: null,
  selection_reason: "no_complete_snapshot", wired_pair_valid_ap_count: 0,
  lan_pair_valid_ap_count: 0, source_mixing_allowed: false};
missing.result.coverage = {coverage_status: "none", empty_population: false, total_ap_count: 0,
  valid_rate_ap_count: 0, valid_download_ap_count: 0, valid_upload_ap_count: 0,
  missing_rate_ap_count: 0, stale_ap_count: 0, unavailable_ap_count: 0, reset_ap_count: 0,
  gap_rejected_ap_count: 0, no_baseline_ap_count: 0, source_unavailable_ap_count: 0,
  invalid_elapsed_ap_count: 0, coverage_reasons: []};
missing.result.traffic = {download_mbps: null, upload_mbps: null, total_mbps: null, unit: "Mbps"};
assert(api.validateTrafficSummary(missing, site) !== null, "no-cycle shape accepted");

for (const mutate of [
  (value) => { value.result.snapshot.selected_source = "LAN"; },
  (value) => { value.result.snapshot.freshness_status = "unknown"; },
  (value) => { value.result.snapshot.observed_at = "not-a-time"; },
  (value) => { value.result.snapshot.observed_at = "2026-08-24T13:00:01.000Z"; },
  (value) => { value.result.traffic.total_mbps = 999; },
  (value) => { value.result.coverage.valid_rate_ap_count = true; },
  (value) => { value.result.coverage.coverage_reasons = ["unknown"]; },
  (value) => { value.result.snapshot.latest_attempt_result = "unknown"; },
]) {
  const malformed = summary(); mutate(malformed);
  assert(api.validateTrafficSummary(malformed, site) === null, "malformed summary rejected atomically");
}

const validPage = page(valid.result);
assert(api.validateTrafficPage(validPage, site, valid.result) !== null, "pinned page accepted");
validPage.page.selected_source = "LAN";
assert(api.validateTrafficPage(validPage, site, valid.result) === null, "uppercase machine source rejected");
validPage.page.selected_source = "wired"; validPage.page.cycle_id = "different";
assert(api.validateTrafficPage(validPage, site, valid.result) === null, "stale cycle page rejected");
assert(api.pageFailureEffect({status: 403}) === "preserve_summary_forbidden", "AP 403 preserves summary");
assert(api.classify(403, null).global, "summary 403 is a global Site stop");

const busyView = {values: [], setBusy(value) { this.values.push(value); }};
const state = {generation: 0, active: false};
const generation = api.beginCoordinator(state, busyView);
assert(generation === 1 && api.beginCoordinator(state) === null, "coordinator rejects overlap");
assert(!api.endCoordinator(state, 0) && state.active, "late generation cannot release active coordinator");
assert(api.endCoordinator(state, 1, busyView) && !state.active, "owner releases coordinator");
assert(JSON.stringify(busyView.values) === "[true,false]", "shared Refresh ownership follows coordinator lifecycle");
const generationOwner = {generation: 2};
assert(!api.ownsGeneration(generationOwner, 1, false) && api.ownsGeneration(generationOwner, 2, false), "late generation response is ignored");
assert(!api.ownsGeneration(generationOwner, 2, true), "stopped lifecycle ignores response");

const trafficState = {summary: {old: true}, acceptedAt: 0, rows: [{old: true}], cursor: "old", pageForbidden: true};
api.acceptTrafficSummary(trafficState, valid.result, 123);
assert(trafficState.summary === valid.result && trafficState.rows.length === 0 && trafficState.cursor === null && trafficState.pageForbidden, "new summary preserves lifetime AP denial while clearing rows");
assert(api.trafficPageEligible(valid.result, "fresh", false)
  && !api.trafficPageEligible(valid.result, "fresh", true)
  && !api.trafficPageEligible(missing.result, "unavailable", false), "unavailable/no-cycle/forbidden summary skips AP request");
trafficState.rows = [{old: true}]; trafficState.cursor = "next"; api.clearTrafficPageState(trafficState);
assert(trafficState.rows.length === 0 && trafficState.cursor === null && trafficState.summary === valid.result, "local unavailable clears only Traffic page state");

const transition = {failureCount: 0, cleanRetry: false, nextEligibleAt: 0};
assert(api.trafficFailureTransition(transition, {kind: "invalid", status: 400, retryAfter: 0}, 60, 1000, 0).cleanRefresh, "pinned 400 produces one clean refresh");
assert(!api.trafficFailureTransition(transition, {kind: "invalid", status: 400, retryAfter: 0}, 60, 1000, 0).cleanRefresh && transition.nextEligibleAt === Infinity, "clean refresh cannot loop");
const busy = {failureCount: 0, cleanRetry: false, nextEligibleAt: 0};
const busyResult = api.trafficFailureTransition(busy, {kind: "unavailable", status: 429, retryAfter: 1}, 60, 1000, 0.5);
assert(busyResult.delaySeconds === 65 && busy.nextEligibleAt === 66000, "429 uses minimum backoff plus bounded jitter");
const currentFailures = {failureCount: 0};
assert(currentFailures.failureCount === 0 && busy.failureCount === 1, "Traffic failure state is isolated from Current State");
assert(live.neutralAbort("hidden", false) && live.neutralAbort("pagehide", false), "hidden/pagehide abort is neutral");

(async () => {
  const refreshSources = {
    client: {nextEligibleAt: 10000, failureCount: 0, disabled: false},
    ap: {nextEligibleAt: 10000, failureCount: 0, disabled: false},
    traffic: {nextEligibleAt: 10000, failureCount: 0, disabled: false},
  };
  const refreshCalls = {client: 0, ap: 0, traffic: 0};
  const refreshOperations = {
    client: async () => { refreshCalls.client += 1; return {cleanRefresh: false}; },
    ap: async () => { refreshCalls.ap += 1; return {cleanRefresh: false}; },
    traffic: async () => { refreshCalls.traffic += 1; return {cleanRefresh: false}; },
  };
  await api.runEligiblePhasedCycle(refreshSources, false, 1000, refreshOperations);
  assert(JSON.stringify(refreshCalls) === '{"client":0,"ap":0,"traffic":0}', "automatic refresh respects success interval");
  await api.runEligiblePhasedCycle(refreshSources, true, 1000, refreshOperations);
  assert(JSON.stringify(refreshCalls) === '{"client":1,"ap":1,"traffic":1}', "manual refresh immediately performs one new phased cycle");
  refreshSources.client.failureCount = 1;
  await api.runEligiblePhasedCycle(refreshSources, true, 1000, refreshOperations);
  assert(refreshCalls.client === 1 && refreshCalls.ap === 2 && refreshCalls.traffic === 2, "manual refresh does not bypass active source backoff");

  const forbiddenPageState = {summary: null, acceptedAt: 0, rows: [], cursor: null, pageForbidden: false};
  let summaryRequests = 0; let pageRequests = 0;
  async function trafficCycle() {
    summaryRequests += 1;
    api.acceptTrafficSummary(forbiddenPageState, valid.result, summaryRequests);
    if (api.trafficPageEligible(valid.result, "fresh", forbiddenPageState.pageForbidden)) {
      pageRequests += 1;
      forbiddenPageState.pageForbidden = true;
      api.clearTrafficPageState(forbiddenPageState);
    }
  }
  await trafficCycle(); await trafficCycle(); await trafficCycle();
  assert(summaryRequests === 3 && pageRequests === 1, "AP 403 blocks later AP pages while summaries continue");
  assert(forbiddenPageState.summary === valid.result && forbiddenPageState.pageForbidden, "summary data survives persistent AP detail denial");

  let active = 0; let maximum = 0; const events = [];
  function operation(name, delay) { return () => new Promise((resolve) => {
    active += 1; maximum = Math.max(maximum, active); events.push(`${name}:start`);
    setTimeout(() => { events.push(`${name}:end`); active -= 1; resolve(name); }, delay);
  }); }
  await api.runPhasedCycle(operation("client", 15), operation("ap", 5), operation("traffic", 1));
  assert(maximum === 2, "Phase A is capped at two in-tab reads");
  assert(events.indexOf("traffic:start") > events.indexOf("client:end") && events.indexOf("traffic:start") > events.indexOf("ap:end"), "Traffic waits for both Phase A requests to settle");
  console.log("home traffic contract passed");
})().catch((error) => { console.error(error); process.exitCode = 1; });
''',
        encoding="utf-8",
    )
    checked = subprocess.run(
        [NODE, "--check", str(source_path)],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
        env={**os.environ, "NODE_NO_WARNINGS": "1"},
    )
    completed = subprocess.run(
        [NODE, str(script)],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
        env={**os.environ, "NODE_NO_WARNINGS": "1"},
    )
    assert checked.returncode == 0, checked.stderr
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "home traffic contract passed" in completed.stdout


def test_home_traffic_static_privacy_and_request_contract():
    path = Path(__file__).parents[2] / "app" / "admin_web" / "static" / "admin.js"
    source = path.read_text(encoding="utf-8")
    assert "current-traffic" in source
    assert "selected_source=" not in source
    assert "localStorage" not in source
    assert "sessionStorage" not in source
    assert "indexedDB" not in source
    assert "setInterval" not in source
    assert "innerHTML" not in source
    assert "AbortController" in source
    assert "Promise.allSettled" in source
