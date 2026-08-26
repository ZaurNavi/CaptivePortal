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
assert(api.bytes(5153960755) === "4.8 GB", "larger byte units use at most one decimal");
assert(api.coverageText("Traffic", payload().result.traffic) === "Traffic complete", "complete coverage is explicit");
const partialCoverage = payload().result.traffic;
partialCoverage.status = "partial"; partialCoverage.coverage.status = "partial";
partialCoverage.coverage.fully_covered = false;
partialCoverage.coverage.quality_reasons = ["requested_before_coverage_start"];
assert(api.coverageText("Traffic", partialCoverage).includes("proven 2026-08-24T20:00:00.000Z"), "partial coverage shows proven intersection");
const unavailableTraffic = payload().result.traffic;
unavailableTraffic.bytes = null; unavailableTraffic.status = "unavailable";
unavailableTraffic.coverage.status = "unavailable";
unavailableTraffic.coverage.fully_covered = false;
unavailableTraffic.coverage.quality_reasons = ["unsupported_processing_result"];
assert(api.traffic(unavailableTraffic), "per-metric unavailable Traffic is accepted");
assert(api.coverageText("Traffic", unavailableTraffic) === "Traffic unavailable", "unavailable provenance is explicit");
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
  await coordinator.runActivityPhase(null, false, false);
  await coordinator.runActivityPhase(activity, false, true);
  await coordinator.runActivityPhase(activity, true, true);
  assert(JSON.stringify(calls) === '["today+selected","today","today+selected","today"]', "all Activity coordinator phase combinations stay bounded");
  assert(coordinator.pageFailureEffect({status: 403}) === "preserve_summary_forbidden", "Traffic AP 403 remains isolated from summary");
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


def test_home_activity_real_node_dom_fetch_and_coordinator(tmp_path):
    if not NODE:
        pytest.fail("Node.js is mandatory for the Home Activity frontend gate")
    source_path = (
        Path(__file__).parents[2]
        / "app" / "admin_web" / "static" / "admin.js"
    )
    source = source_path.read_text(encoding="utf-8")
    marker = '  const UTC = /^\\d{4}-\\d{2}-\\d{2}T'
    marker_at = source.index(marker)
    start = source.rfind("(function () {", 0, marker_at)
    end = source.index("\n(function () {", marker_at)
    activity_source = source[start:end]
    script = tmp_path / "home-activity-dom-contract.js"
    script.write_text(
        r'''
function assert(value, message) { if (!value) throw new Error(message); }
class Element {
  constructor(id) { this.id = id; this.hidden = false; this.disabled = false;
    this.textContent = ""; this.value = ""; this.listeners = {}; this.attributes = {}; }
  addEventListener(name, callback) { (this.listeners[name] ||= []).push(callback); }
  dispatch(name, extra = {}) { const event = {preventDefault() {}, key: null, ...extra};
    return Promise.all((this.listeners[name] || []).map((callback) => callback(event))); }
  focus() { global.focused = this.id; }
  setAttribute(name, value) { this.attributes[name] = value; }
}
const ids = ["admin-page", "activity-picker", "activity-picker-open",
  "activity-custom-fields", "activity-preview", "activity-apply", "activity-cancel",
  "activity-preview-state", "activity-today-range", "activity-today-visits",
  "activity-today-traffic", "activity-today-quality", "activity-selected-range",
  "activity-selected-visits", "activity-selected-traffic", "activity-selected-quality",
  "live-online", "traffic-total"];
const elements = Object.fromEntries(ids.map((id) => [id, new Element(id)]));
elements["admin-page"].dataset = {page: "home", homeActivityEnabled: "true",
  siteId: "0123456789abcdef01234567", apiBase: "/admin/api/v1/sites/0123456789abcdef01234567",
  homeActivityRefreshSeconds: "60", homeActivityRequestTimeoutSeconds: "20"};
elements["activity-picker"].hidden = true;
elements["activity-picker"].elements = {
  period: new Element("period"), from_date: new Element("from_date"),
  from_time: new Element("from_time"), to_date: new Element("to_date"),
  to_time: new Element("to_time")};
elements["activity-picker"].elements.period.value = "last_24h";
elements["live-online"].textContent = "17"; elements["traffic-total"].textContent = "9.00 Mbps";
const documentListeners = {};
global.document = {hidden: false, getElementById: (id) => elements[id] || null,
  addEventListener(name, callback) { (documentListeners[name] ||= []).push(callback); }};
const windowListeners = {};
let clock = 1000;
global.performance = {now: () => clock};
global.window = {setTimeout, clearTimeout,
  addEventListener(name, callback) { (windowListeners[name] ||= []).push(callback); }};
const fetchQueue = []; const fetchCalls = []; const fetchSignals = [];
function response(status, payload, retryAfter = null) { return {ok: status >= 200 && status < 300,
  status, json: async () => payload, headers: {get: (name) => name === "Retry-After" ? retryAfter : null}}; }
global.fetch = (url, options) => { fetchCalls.push(url); fetchSignals.push(options.signal);
  const next = fetchQueue.shift(); if (!next) throw new Error("unexpected fetch " + url);
  return typeof next === "function" ? next(url, options) : next; };
let selectedPromise = Promise.resolve(); let globalStops = 0;
window.CaptivPortalHomeCoordinator = {requestActivitySelected() {
  selectedPromise = window.CaptivPortalHomeActivityCoordinator.runSelected(true);
}, stop() { globalStops += 1; }};
function coverage(status = "complete", reasons = []) { return {
  coverage_from_utc: "2025-01-01T00:00:00.000Z",
  coverage_through_utc: "2026-08-25T08:00:00.000Z",
  covered_from_utc: "2026-08-24T20:00:00.000Z",
  covered_through_utc: "2026-08-25T08:00:00.000Z",
  fully_covered: status === "complete", status, quality_reasons: reasons}; }
function payload(kind = "today", visits = 4, trafficUnavailable = false) { const trafficStatus = trafficUnavailable ? "unavailable" : "complete";
  return {api_version: "admin.read.v1", site_id: elements["admin-page"].dataset.siteId, result: {
    evaluated_at_utc: "2026-08-25T08:00:00.000Z", timezone: "Asia/Baku", guest_ssids: ["Zefer_Parki"],
    range: {requested: {kind}, resolved: {from_utc: "2026-08-24T20:00:00.000Z",
      to_utc: "2026-08-25T08:00:00.000Z", from_local: "2026-08-25T00:00:00+04:00",
      to_local_exclusive: "2026-08-26T00:00:00+04:00", timezone: "Asia/Baku"}},
    authorized_visits: {value: visits, status: "complete", cohort: "visit_opening_authorization",
      source_kind: "visit_lifecycle", verified_visit_count: visits, integrity_anomaly_count: 0,
      coverage: coverage(), earliest_persisted_evidence_at: null, latest_persisted_evidence_at: null},
    traffic: {bytes: trafficUnavailable ? null : 5153960755, status: trafficStatus, estimated: true,
      attribution: "completed_session_end", source_kind: "omada_offline_reported_traffic",
      eligible_terminal_event_count: 1, included_fingerprint_count: 1,
      unmatched_included_event_count: 0, pending_event_count: 0, invalid_event_count: 0,
      missing_traffic_count: 0, missing_controller_time_count: 0, semantic_duplicate_count: 0,
      other_excluded_event_count: 0, reader_watermark_at: "2026-08-25T08:00:00.000Z",
      ingestion_freshness: "fresh", coverage: trafficUnavailable
        ? coverage("unavailable", ["unsupported_processing_result"]) : coverage(),
      earliest_persisted_evidence_at: null, latest_persisted_evidence_at: null},
    next_site_midnight_utc: kind === "today" ? "2026-08-25T20:00:00.000Z" : null}}; }
function previewPayload() { return {api_version: "admin.read.v1", site_id: elements["admin-page"].dataset.siteId,
  result: {timezone: "Asia/Baku", requested: {kind: "custom"}, resolved: {
    from_utc: "2026-07-31T20:00:00.000Z", to_utc: "2026-08-05T20:00:00.000Z",
    from_local: "2026-08-01T00:00:00+04:00", to_local_exclusive: "2026-08-06T00:00:00+04:00"},
    can_apply: true, validation_reason: null}}; }
async function flush() { await Promise.resolve(); await new Promise((resolve) => setImmediate(resolve)); await Promise.resolve(); }
''' + activity_source + r'''
const activity = window.CaptivPortalHomeActivityCoordinator;
(async () => {
  const picker = elements["activity-picker"];
  const opener = elements["activity-picker-open"];
  await opener.dispatch("click");
  assert(!picker.hidden && global.focused === "period", "picker opens and focuses range");
  picker.elements.period.value = "custom"; await picker.elements.period.dispatch("change");
  assert(!elements["activity-custom-fields"].hidden && !elements["activity-preview"].hidden
    && elements["activity-apply"].disabled, "custom requires preview");
  picker.elements.from_date.value = "2026-08-01"; picker.elements.to_date.value = "2026-08-05";
  await picker.elements.from_date.dispatch("input");
  fetchQueue.push(Promise.resolve(response(200, previewPayload())));
  await elements["activity-preview"].dispatch("click"); await flush();
  assert(fetchCalls.at(-1).includes("range-preview") && !elements["activity-apply"].disabled,
    "preview resolves custom range before Apply");
  fetchQueue.push(Promise.resolve(response(200, payload("custom"))));
  await picker.dispatch("submit"); await selectedPromise;
  assert(fetchCalls.at(-1).includes("period=custom") && elements["activity-selected-visits"].textContent === "4",
    "Apply loads the selected custom range");
  await opener.dispatch("click"); picker.elements.period.value = "last_7d";
  await elements["activity-cancel"].dispatch("click");
  assert(picker.hidden && picker.elements.period.value === "custom" && global.focused === "activity-picker-open",
    "Cancel restores applied draft and opener focus");
  await opener.dispatch("click"); picker.elements.period.value = "last_30d";
  await picker.dispatch("keydown", {key: "Escape"});
  assert(picker.hidden && picker.elements.period.value === "custom", "Escape restores applied selection");

  fetchQueue.push(Promise.resolve(response(200, payload("today"))));
  fetchQueue.push(Promise.resolve(response(200, payload("custom"))));
  await activity.run(true);
  assert(elements["activity-today-traffic"].textContent.startsWith("4.8 GB")
    && elements["activity-today-quality"].textContent.includes("Last updated")
    && elements["activity-today-quality"].textContent.includes("Visits data"),
    "DOM renders precision and provenance");

  fetchQueue.push(Promise.resolve(response(200, payload("today", 7, true))));
  await activity.runToday(true);
  assert(elements["activity-today-visits"].textContent === "7"
    && elements["activity-today-traffic"].textContent.startsWith("— · Unavailable · Estimated"),
    "Traffic unavailable preserves independent Visits");

  const todayBefore = elements["activity-today-visits"].textContent;
  clock += 400000; fetchQueue.push(Promise.resolve(response(503, {error: {code: "query_deadline"}})));
  await activity.runSelected(true);
  assert(elements["activity-today-visits"].textContent === todayBefore
    && elements["activity-selected-quality"].textContent.includes("unavailable"),
    "Selected 503 is isolated from Today");
  clock += 400000; fetchQueue.push(Promise.resolve(response(429, {error: {code: "concurrency_limit"}}, "120")));
  await activity.runSelected(true);
  clock += 400000; fetchQueue.push(Promise.reject(new Error("network")));
  await activity.runSelected(true);
  assert(elements["activity-today-visits"].textContent === todayBefore, "429/network remain source-isolated");

  let resolveLate; clock += 400000;
  fetchQueue.push(new Promise((resolve) => { resolveLate = resolve; }));
  const late = activity.runToday(true); await flush(); activity.abort("superseded");
  fetchQueue.push(Promise.resolve(response(200, payload("today", 9))));
  const current = activity.runToday(true); await current;
  resolveLate(response(200, payload("today", 99))); await late;
  assert(elements["activity-today-visits"].textContent === "9", "late generation cannot overwrite current DOM");

  let resolveHidden; clock += 400000;
  fetchQueue.push(new Promise((resolve) => { resolveHidden = resolve; }));
  const hiddenRequest = activity.runSelected(true); await flush();
  document.hidden = true; await Promise.all((documentListeners.visibilitychange || []).map((callback) => callback()));
  assert(fetchSignals.at(-1).aborted, "hidden lifecycle aborts active Activity fetch");
  resolveHidden(response(200, payload("custom", 88))); await hiddenRequest; document.hidden = false;

  clock += 400000; fetchQueue.push(Promise.resolve(response(404, {error: {code: "not_found"}})));
  const before404Calls = fetchCalls.length; await activity.runToday(true);
  assert(elements["activity-today-visits"].textContent === "—"
    && elements["activity-selected-traffic"].textContent === "— · Estimated"
    && elements["activity-picker-open"].disabled, "Activity 404 clears both Activity panels");
  await activity.run(true);
  assert(fetchCalls.length === before404Calls + 1 && globalStops === 0,
    "Activity 404 stops Activity only without polling or global Home stop");
  assert(elements["live-online"].textContent === "17" && elements["traffic-total"].textContent === "9.00 Mbps",
    "Activity 404 leaves Current State and Current Traffic untouched");
  await Promise.all((windowListeners.pagehide || []).map((callback) => callback()));
  console.log("home activity DOM contract passed");
})().catch((error) => { console.error(error); process.exitCode = 1; });
''',
        encoding="utf-8",
    )
    completed = subprocess.run(
        [NODE, str(script)], capture_output=True, text=True, timeout=30,
        check=False, env={**os.environ, "NODE_NO_WARNINGS": "1"},
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "home activity DOM contract passed" in completed.stdout


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
