from __future__ import annotations

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


def test_home_health_real_node_contract(tmp_path):
    if not NODE:
        pytest.fail("Node.js is mandatory for the Home Health frontend gate")
    source = (
        Path(__file__).parents[2] / "app" / "admin_web" / "static" / "admin.js"
    ).read_text(encoding="utf-8")
    script = tmp_path / "home-health-contract.js"
    script.write_text(
        "global.window = {};\n" + source + r'''
const api = window.CaptivPortalHomeHealthTest;
function assert(value, message) { if (!value) throw new Error(message); }
function copy(value) { return JSON.parse(JSON.stringify(value)); }
const site = "0123456789abcdef01234567";
const ids = ["guest_access", "live_network_state", "network_history", "visit_tracking", "analytics_home_data"];
const labels = ["Guest Access", "Live Network State", "Network History Collection", "Visit Tracking", "Analytics & Home Data"];
const states = [
  ["operational", "latest_authorization_verified", "Guest authorization is operating normally."],
  ["degraded", "current_state_stale", "Current network state is delayed; last complete data remains available."],
  ["unavailable", "observation_unavailable", "Network history collection is unavailable."],
  ["unknown", "initializing", "There is not enough current evidence to confirm status."],
  ["operational", "analytics_operational", "Analytics and Home data sources are available."],
];
function payload() {
  return {api_version: "admin.read.v1", site_id: site, result: {
    health_version: 1, site_id: site, evaluated_at: "2026-08-27T12:00:00.000Z",
    status: "degraded", message: "Some CaptivPortal functions are degraded.",
    components: ids.map((id, index) => ({id, label: labels[index],
      status: states[index][0], reason_code: states[index][1], message: states[index][2],
      criticality: index === 0 ? "critical" : "feature",
      scope: index < 3 ? {type: "site", site_id: site} : {type: "global"},
      evidence_at: index === 1 ? null : "2026-08-27T11:59:00.000Z",
      last_success_at: index === 2 ? null : "2026-08-27T11:58:00.000Z"}))}};
}
assert(api.validateHealth(payload(), site) !== null, "all four states accepted atomically");
for (const mutate of [
  (v) => { v.result.components.reverse(); },
  (v) => { v.result.components[0].status = "healthy"; },
  (v) => { v.result.components[0].reason_code = "private_failure"; },
  (v) => { v.result.components[0].message = "raw exception"; },
  (v) => { v.result.message = "All good"; },
  (v) => { v.result.components[0].scope.site_id = "ffffffffffffffffffffffff"; },
  (v) => { v.result.components[3].scope.site_id = site; },
  (v) => { v.result.components[2].evidence_at = "not-a-time"; },
  (v) => { v.result.health_version = 2; },
]) {
  const invalid = copy(payload()); mutate(invalid);
  assert(api.validateHealth(invalid, site) === null, "malformed Health is rejected before rendering");
}
assert(api.classify(401, null, 0).global, "session expiry is global");
assert(api.classify(403, null, 0).global, "forbidden is global");
assert(api.classify(404, null, 0).kind === "disabled", "feature 404 disables only Health");
assert(api.classify(503, "query_deadline", 0).kind === "timeout", "deadline remains distinct");
assert(api.classify(429, "concurrency_limit", 12).retryAfter === 12, "Retry-After is retained");
assert(api.legacyCoordinatorEnabled("false", "true"), "legacy Home coordinator owns Health without Home Live");
assert(!api.legacyCoordinatorEnabled("true", "true"), "Home Live coordinator owns enabled Health");
const owner = {generation: 1, controller: null};
const first = new AbortController(); const second = new AbortController();
assert(api.claim(owner, first, 1), "generation owns request");
api.release(owner, second);
assert(owner.controller === first, "old completion cannot release new controller");
assert(api.abort(owner, "hidden") && first.signal.aborted, "hidden abort cancels current Health request");
const live = window.CaptivPortalHomeLiveTest;
const combined = window.CaptivPortalHomeTrafficTest;
for (const values of [
  ["true", "false", "false", "false"],
  ["true", "false", "false", "true"],
  ["true", "true", "false", "true"],
  ["true", "false", "true", "true"],
  ["true", "true", "true", "true"],
]) {
  const owners = Number(live.standaloneCoordinatorEnabled(...values))
    + Number(combined.combinedCoordinatorEnabled(...values));
  assert(owners === 1, "exactly one Home coordinator owns each Health feature combination");
}
''',
        encoding="utf-8",
    )
    completed = subprocess.run(
        [NODE, str(script)], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, completed.stderr


def test_home_health_static_security_contract():
    source = (
        Path(__file__).parents[2] / "app" / "admin_web" / "static" / "admin.js"
    ).read_text(encoding="utf-8")
    health = source[source.index("const IDS = [\"guest_access\"") : source.index("}());", source.index("const IDS = [\"guest_access\""))]
    assert ".innerHTML" not in health
    assert "localStorage" not in health and "sessionStorage" not in health
    assert 'credentials: "same-origin"' in health
    assert 'cache: "no-store"' in health


def test_home_health_real_node_dom_fetch_and_recovery(tmp_path):
    if not NODE:
        pytest.fail("Node.js is mandatory for the Home Health frontend gate")
    source = (
        Path(__file__).parents[2] / "app" / "admin_web" / "static" / "admin.js"
    ).read_text(encoding="utf-8")
    marker_at = source.index('  const IDS = ["guest_access"')
    start = source.rfind("(function () {", 0, marker_at)
    end = source.index("\n(function () {", marker_at)
    health_source = source[start:end]
    script = tmp_path / "home-health-dom-contract.js"
    script.write_text(
        r'''
function assert(value, message) { if (!value) throw new Error(message); }
class Element {
  constructor(id) { this.id = id; this.dataset = {}; this.textContent = "";
    this.children = []; this.listeners = {}; this.hidden = false; this.disabled = false; }
  append(...values) { this.children.push(...values); }
  replaceChildren(...values) { this.children = [...values]; }
  addEventListener(name, callback) { (this.listeners[name] ||= []).push(callback); }
}
const ids = ["admin-page", "refresh-button", "home-health-state", "home-health-status",
  "home-health-message", "home-health-updated", "home-health-components"];
const elements = Object.fromEntries(ids.map((id) => [id, new Element(id)]));
const site = "0123456789abcdef01234567";
elements["admin-page"].dataset = {page: "home", siteId: site,
  apiBase: `/admin/api/v1/sites/${site}`, homeLiveEnabled: "true",
  homeHealthEnabled: "true", homeHealthRefreshSeconds: "60",
  homeHealthRequestTimeoutSeconds: "20"};
const documentListeners = {}; const windowListeners = {};
global.document = {hidden: false, getElementById: (id) => elements[id] || null,
  createElement: (tag) => new Element(tag),
  addEventListener(name, callback) { (documentListeners[name] ||= []).push(callback); }};
let clock = 1000;
global.performance = {now: () => clock};
global.window = {setTimeout, clearTimeout,
  addEventListener(name, callback) { (windowListeners[name] ||= []).push(callback); },
  CaptivPortalHomeCoordinator: {stops: [], stop(kind) { this.stops.push(kind); }}};
const calls = []; const queue = []; const signals = [];
function response(status, payload, retryAfter = null) { return {
  ok: status >= 200 && status < 300, status, json: async () => payload,
  headers: {get: (name) => name === "Retry-After" ? retryAfter : null}}; }
global.fetch = (url, options) => { calls.push(url); signals.push(options.signal);
  const next = queue.shift(); if (!next) throw new Error("unexpected fetch"); return next; };
const componentIds = ["guest_access", "live_network_state", "network_history", "visit_tracking", "analytics_home_data"];
const componentLabels = ["Guest Access", "Live Network State", "Network History Collection", "Visit Tracking", "Analytics & Home Data"];
const operationalReasons = [
  ["latest_authorization_verified", "Guest authorization is operating normally."],
  ["current_state_operational", "Current client and access-point state is available."],
  ["observation_operational", "Network history collection is operating normally."],
  ["visit_operational", "Visit tracking is operating normally."],
  ["analytics_operational", "Analytics and Home data sources are available."],
];
function payload(status = "operational", suffix = "A") { return {api_version: "admin.read.v1",
  site_id: site, result: {health_version: 1, site_id: site,
  evaluated_at: `2026-08-27T12:00:00.00${suffix === "A" ? "0" : "1"}Z`, status,
  message: status === "operational" ? "All CaptivPortal functions are operating normally." : "Some CaptivPortal functions are degraded.",
  components: componentIds.map((id, index) => ({id, label: componentLabels[index],
    status: index === 1 && status === "degraded" ? "degraded" : "operational",
    reason_code: index === 1 && status === "degraded" ? "current_state_stale" : operationalReasons[index][0],
    message: index === 1 && status === "degraded"
      ? "Current network state is delayed; last complete data remains available."
      : operationalReasons[index][1], criticality: index === 0 ? "critical" : "feature",
    scope: index < 3 ? {type: "site", site_id: site} : {type: "global"},
    evidence_at: "2026-08-27T11:59:00.000Z", last_success_at: null}))}}; }
''' + health_source + r'''
const health = window.CaptivPortalHomeHealthCoordinator;
(async () => {
  queue.push(Promise.resolve(response(200, payload("operational", "A"))));
  await health.run(true);
  assert(elements["home-health-components"].children.length === 5, "all components render");
  assert(elements["home-health-status"].textContent === "Operational", "aggregate renders");
  const previousTime = elements["home-health-updated"].textContent;
  clock += 70000; queue.push(Promise.resolve(response(503, {error: {code: "query_deadline"}})));
  await health.run(true);
  assert(elements["home-health-status"].textContent === "Update unavailable", "failure is not false operational");
  assert(elements["home-health-components"].children.length === 5
    && elements["home-health-updated"].textContent === previousTime, "old values retain old timestamp");
  clock += 400000; queue.push(Promise.resolve(response(200, payload("degraded", "B"))));
  await health.run(true);
  assert(elements["home-health-status"].textContent === "Degraded"
    && elements["home-health-updated"].textContent !== previousTime,
    "next successful refresh recovers without reload");

  let resolveHidden; clock += 400000;
  queue.push(new Promise((resolve) => { resolveHidden = resolve; }));
  const pending = health.run(true); await new Promise((resolve) => setImmediate(resolve));
  health.abort("hidden");
  assert(signals.at(-1).aborted, "hidden lifecycle aborts active Health request");
  resolveHidden(response(200, payload("operational", "A"))); await pending;

  clock += 400000; queue.push(Promise.resolve(response(404, {error: {code: "not_found"}})));
  const before404 = calls.length; await health.run(true); await health.run(true);
  assert(calls.length === before404 + 1, "feature 404 stops Health until reload");
  assert(window.CaptivPortalHomeCoordinator.stops.length === 0, "Health 404 leaves other Home modules running");
  console.log("home health DOM contract passed");
})().catch((error) => { console.error(error); process.exitCode = 1; });
''',
        encoding="utf-8",
    )
    completed = subprocess.run(
        [NODE, str(script)], capture_output=True, text=True, timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "home health DOM contract passed" in completed.stdout
