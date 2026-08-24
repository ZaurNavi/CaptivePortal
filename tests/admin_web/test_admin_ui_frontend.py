from __future__ import annotations

import json
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


def test_admin_javascript_syntax_and_state_contract(tmp_path):
    if not NODE:
        pytest.skip("Node.js is required for Admin UI behavior tests")
    source_path = (
        Path(__file__).parents[2]
        / "app" / "admin_web" / "static" / "admin.js"
    )
    source = source_path.read_text(encoding="utf-8")
    script = tmp_path / "admin-ui-contract.js"
    script.write_text(
        "global.window = {};\n"
        + source
        + "\nconst api = window.CaptivPortalAdminTest;\n"
        + r"""
function assert(value, message) {
  if (!value) throw new Error(message);
}
assert(api.canonicalMac("aa-bb-cc-dd-ee-ff") === "AA:BB:CC:DD:EE:FF", "MAC canonicalization");
assert(api.canonicalMac("not-a-mac") === null, "invalid MAC rejected");
assert(api.classifyHttp(401, {}, null).kind === "session", "401 state");
assert(api.classifyHttp(403, {}, null).kind === "forbidden", "403 state");
assert(api.classifyHttp(429, {}, "1").message.includes("1 second"), "Retry-After state");
assert(api.classifyHttp(503, {error: {code: "query_deadline"}}, null).title === "Query timed out", "deadline state");
assert(api.classifyHttp(503, {error: {code: "source_unavailable"}}, null).kind === "unavailable", "unavailable state");
assert(api.classifyHttp(500, null, null).kind === "unexpected", "malformed state");
assert(api.display(null) === "—", "null is not numeric zero");
assert(api.display(0) === "0", "real zero is preserved");
const instant = new Date("2026-08-23T12:34:00.000Z");
assert(api.localDatetimeValue(instant) === "2026-08-23T16:34", "Baku local field value");
assert(api.utcFromLocal("2026-08-23T16:34") === "2026-08-23T12:34:00.000Z", "local round trip to UTC");

const all = api.parseVisitFilters("", "", "all");
assert(all.status === null && all.fromUtc === null && all.toUtc === null, "all omits optional filters");
const open = api.parseVisitFilters("2026-08-23T15:00", "2026-08-23T16:00", "open");
const closed = api.parseVisitFilters("2026-08-23T14:00", "2026-08-23T16:00", "closed");
assert(open.status === "open" && closed.status === "closed", "canonical visit statuses");
assert(open.fromUtc === "2026-08-23T11:00:00.000Z", "initialized local value becomes correct UTC");
let sourceCalls = 0;
try {
  api.parseVisitFilters("2026-08-23T15:00", "", "all");
  sourceCalls += 1;
} catch (error) {
  assert(error.uiFailure.title === "Incomplete time range", "paired time validation");
}
assert(sourceCalls === 0, "one boundary stops before fetch");

const visits = api.createVisitQueryState(open);
visits.setCursor("open-cursor");
const unchanged = visits.parameters();
assert(unchanged.get("status") === "open" && unchanged.get("cursor") === "open-cursor", "draft edits cannot change applied cursor state");
visits.apply(closed);
assert(visits.snapshot().cursor === null, "Apply resets cursor");
visits.setCursor("closed-cursor");
const more = visits.parameters();
assert(more.get("status") === "closed" && more.get("cursor") === "closed-cursor", "Load more preserves filters");
assert(more.get("from_utc") === closed.fromUtc && more.get("to_utc") === closed.toUtc, "Load more preserves time range");
visits.resetCursor();
const refreshed = visits.parameters();
assert(refreshed.get("status") === "closed" && !refreshed.has("cursor"), "Refresh repeats filters without old cursor");
const login = api.safeReturnPath({pathname: "/admin/sites/a/devices", search: "?mac=x"});
assert(login.startsWith("/admin/login?next="), "safe login return");
assert(!login.includes("http"), "no external login target");
console.log("admin ui contract passed");
""",
        encoding="utf-8",
    )
    checked = subprocess.run(
        [NODE, "--check", str(source_path)],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
        env={**os.environ, "NODE_NO_WARNINGS": "1", "TZ": "Asia/Baku"},
    )
    completed = subprocess.run(
        [NODE, str(script)],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
        env={**os.environ, "NODE_NO_WARNINGS": "1", "TZ": "Asia/Baku"},
    )
    assert checked.returncode == 0, checked.stderr
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "admin ui contract passed" in completed.stdout


def test_home_live_javascript_validation_freshness_and_retry_contract(tmp_path):
    if not NODE:
        pytest.skip("Node.js is required for Home Live behavior tests")
    source_path = (
        Path(__file__).parents[2]
        / "app" / "admin_web" / "static" / "admin.js"
    )
    source = source_path.read_text(encoding="utf-8")
    script = tmp_path / "home-live-contract.js"
    script.write_text(
        "global.window = {};\n" + source + r'''
const api = window.CaptivPortalHomeLiveTest;
function assert(value, message) { if (!value) throw new Error(message); }
const site = "0123456789abcdef01234567";
const cycle = "10000000-0000-4000-8000-000000000001";
const hash = "a".repeat(64);
function snapshot(kind) {
  return {kind, cycle_id: cycle, evaluated_at: "2026-08-23T10:00:00.000Z",
    observed_at: "2026-08-23T10:00:00.000Z", capture_finished_at: "2026-08-23T10:00:00.000Z",
    age_seconds: 10, freshness_status: "fresh", freshness_reason: "within_freshness_window",
    complete: true, source_scope_version: 1, source_scope_hash: hash,
    source_scope: kind === "client" ? {scope_type: "client_ssid_allowlist", site_id: site, ssids: ["WiFi"]} : {scope_type: "site_ap_inventory", site_id: site},
    latest_attempt_result: "success", latest_attempt_at: "2026-08-23T10:00:00.000Z", latest_partial_cycle_id: null};
}
const client = {api_version: "admin.read.v1", site_id: site, result: {
  snapshot: snapshot("client"), freshness_policy: {fresh_max_age_seconds: 60, unavailable_after_seconds: 180},
  counts: {online: 2, authorized: 1, pending: 1, other: 0, unknown: 0, other_unknown: 0, ap_unknown: 0},
  devices_by_ap: [{ap_mac: "AA:BB:CC:DD:EE:FF", client_count: 2}]}};
assert(api.validateClientSummary(client, site) !== null, "valid client summary");
client.result.counts.online = 3;
assert(api.validateClientSummary(client, site) === null, "client invariant rejected");
client.result.counts.online = 2;
const ap = {api_version: "admin.read.v1", site_id: site, result: {
  snapshot: snapshot("ap"), freshness_policy: {fresh_max_age_seconds: 90, unavailable_after_seconds: 300},
  counts: {total: 3, online: 1, other: 1, unknown: 1}}};
assert(api.validateApSummary(ap, site) !== null, "valid AP summary");
const acceptedAt = 1000;
assert(api.currentAge(snapshot("client"), acceptedAt, 61000) === 70, "monotonic age progression");
assert(api.localFreshness(snapshot("client"), {fresh_max_age_seconds: 60, unavailable_after_seconds: 180}, acceptedAt, 50000) === "fresh", "fresh locally");
assert(api.localFreshness(snapshot("client"), {fresh_max_age_seconds: 60, unavailable_after_seconds: 180}, acceptedAt, 61001) === "stale", "stale locally");
assert(api.localFreshness(snapshot("client"), {fresh_max_age_seconds: 60, unavailable_after_seconds: 180}, acceptedAt, 171001) === "unavailable", "unavailable locally");
assert(api.localFreshness(snapshot("client"), {fresh_max_age_seconds: 60, unavailable_after_seconds: 180}, acceptedAt, 171000) === "stale", "threshold itself is not unavailable");
const serverUnavailable = snapshot("client");
serverUnavailable.freshness_status = "unavailable";
assert(api.localFreshness(serverUnavailable, {fresh_max_age_seconds: 60, unavailable_after_seconds: 180}, acceptedAt, 1000) === "unavailable", "server unavailable remains unavailable");
assert(api.retryDelay(1, 60, 0) === 60 && api.retryDelay(2, 60, 0) === 120 && api.retryDelay(3, 60, 0) === 300, "bounded independent backoff");
assert(api.retryDelay(1, 60, 90) === 90, "Retry-After respected");
assert(api.enrichmentState([{ap_mac: "A", product_status_classification: "Online"}], null, ap.result, "A", "fresh") === "Matched · Online", "matched AP enrichment");
assert(api.enrichmentState([], "next", ap.result, "A", "fresh") === "Not yet loaded", "incomplete AP enrichment");
assert(api.enrichmentState([], null, ap.result, "A", "fresh") === "Absent after inventory load", "exhausted AP enrichment");
assert(api.enrichmentState([{ap_mac: "A", product_status_classification: "Online"}], null, ap.result, "A", "unavailable") === "AP source unavailable", "local AP expiry hides stale enrichment");
assert(api.classify(401, null).kind === "session" && api.classify(404, null).kind === "disabled", "global stop states");
assert(api.classify(429, null).retryable && api.classify(503, "query_deadline").kind === "timeout", "retryable source states");
const page = {api_version: "admin.read.v1", site_id: site, result: {snapshot: snapshot("client"), items: [{client_mac: "00:11:22:33:44:55", name: null, hostname: null, ip: null, ssid: "WiFi", ap_name: null, ap_mac: null, band: null, rssi: null, snr: null, controller_uptime: null, controller_traffic_down: null, controller_traffic_up: null, controller_traffic_total: null, auth_classification: "authorized"}]}, page: {limit: 100, cycle_id: cycle, source_scope_hash: hash, next_cursor: null}};
assert(api.validatePage(page, site, "client", snapshot("client")) !== null, "pinned page accepted");
page.page.cycle_id = "different";
assert(api.validatePage(page, site, "client", snapshot("client")) === null, "old generation page rejected");
page.page.cycle_id = cycle;
page.page.limit = 0;
assert(api.validatePage(page, site, "client", snapshot("client")) === null, "invalid page limit rejected");
page.page.limit = 100;
page.result.snapshot.complete = false;
assert(api.validatePage(page, site, "client", snapshot("client")) === null, "incomplete pinned page rejected");
page.result.snapshot = snapshot("client");
page.result.snapshot.source_scope = null;
assert(api.validatePage(page, site, "client", snapshot("client")) === null, "null scoped page rejected");

const malformedSummary = JSON.parse(JSON.stringify(client));
malformedSummary.result.snapshot.complete = false;
assert(api.validateClientSummary(malformedSummary, site) === null, "incomplete fresh summary rejected");
malformedSummary.result.snapshot = snapshot("client");
malformedSummary.result.snapshot.source_scope = null;
assert(api.validateClientSummary(malformedSummary, site) === null, "fresh null scope rejected");

const oldController = {reason: null, abort(reason) { this.reason = reason; }};
const newController = {reason: null, abort(reason) { this.reason = reason; }};
const ownership = {generation: 1, controller: null};
assert(api.claimController(ownership, oldController, 1), "old request owns controller");
assert(api.abortOwnedController(ownership, "superseded") && oldController.reason === "superseded", "manual refresh aborts old request");
ownership.generation = 2;
assert(api.claimController(ownership, newController, 2), "new generation claims controller");
api.releaseController(ownership, oldController);
assert(ownership.controller === newController, "old finally cannot clear new controller");
assert(api.abortOwnedController(ownership, "hidden") && newController.reason === "hidden", "hidden/page lifecycle aborts active owner");
assert(api.neutralAbort("hidden", false) && api.neutralAbort("pagehide", false), "hidden and pagehide aborts are neutral");
assert(api.neutralAbort("timeout", true) && !api.neutralAbort("timeout", false), "hidden abort cannot increment failure state");

const clean = {cleanRetry: false, failureCount: 0};
assert(api.failureTransition(clean, {kind: "invalid"}).cleanRefresh, "first 400 requests one clean refresh");
assert(!api.failureTransition(clean, {kind: "invalid"}).cleanRefresh, "second 400 cannot loop clean refresh");
const overlap = {generation: 1, controller: {abort() {}}};
assert(!api.claimController(overlap, {abort() {}}, 1), "clean refresh cannot overlap active request");
assert(!api.canStartCleanRefresh(overlap, 1, false, false), "clean refresh waits for owner release");
overlap.controller = null;
assert(api.canStartCleanRefresh(overlap, 1, false, false), "clean refresh starts only after prior lifecycle finishes");
assert(!api.canStartCleanRefresh(overlap, 0, false, false), "stale generation cannot start clean refresh");

const clientFailures = {cleanRetry: false, failureCount: 0};
const apFailures = {cleanRetry: false, failureCount: 0};
api.failureTransition(clientFailures, {kind: "unavailable"});
assert(clientFailures.failureCount === 1 && apFailures.failureCount === 0, "Client and AP backoff counters stay independent");

assert(api.retainedSelection(["WiFi", "Guest"], "Guest") === "Guest", "SSID remains selected inside new scope");
assert(api.retainedSelection(["WiFi"], "Guest") === "", "missing SSID safely falls back to All");
const filtered = api.clientParameters(cycle, 100, "cursor", {sort: "client_mac", auth: "authorized", ap: "AA", ssid: "Guest"});
assert(filtered.get("ssid") === "Guest" && filtered.get("cursor") === "cursor", "selected SSID is pinned into page query");
const state = {cursor: "old", rows: [{client_mac: "old"}]};
const view = {cleared: 0, hidden: 0, loadingCount: 0, clearRows() { this.cleared += 1; }, hideMore() { this.hidden += 1; }, loading() { this.loadingCount += 1; }};
api.resetClientState(state, view);
assert(state.cursor === null && state.rows.length === 0 && view.cleared === 1 && view.hidden === 1 && view.loadingCount === 1, "filter change immediately removes old rows and shows loading");
const unavailableClient = api.unavailableValues("client");
const unavailableAp = api.unavailableValues("ap");
assert(unavailableClient.primary === "—" && unavailableClient.detail === "Other — · Unknown —" && unavailableClient.state === "Unavailable", "local Client expiry replaces all current values");
assert(unavailableAp.primary === "— / —" && unavailableAp.detail === "Other — · Unknown —" && unavailableAp.count === "Unavailable" && unavailableAp.state === "Unavailable", "local AP expiry replaces counters and showing state");
console.log("home live contract passed");
''',
        encoding="utf-8",
    )
    checked = subprocess.run(
        [NODE, "--check", str(source_path)], capture_output=True, text=True,
        timeout=15, check=False, env={**os.environ, "NODE_NO_WARNINGS": "1"},
    )
    completed = subprocess.run(
        [NODE, str(script)], capture_output=True, text=True,
        timeout=15, check=False, env={**os.environ, "NODE_NO_WARNINGS": "1"},
    )
    assert checked.returncode == 0, checked.stderr
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "home live contract passed" in completed.stdout
