"use strict";
const assert = require("node:assert/strict"), fs = require("node:fs"), vm = require("node:vm");
const full = fs.readFileSync(process.argv[2], "utf8");
const source = full.slice(full.indexOf("/* NI-04: independent bounded Service Intelligence coordinator. */"));
assert.ok(source.startsWith("/* NI-04:"));
const site = "0123456789abcdef01234567", device = "10000000-0000-4000-8000-000000000001";
const at = "2026-10-12T00:00:00.123456Z", event = "2026-10-11T23:59:59.123456Z";
const service = {service_id: "service.youtube", display_name: "YouTube", organization_id: "org.google",
  organization_display_name: "Google", service_category_id: "category.video_streaming",
  service_category_display_name: "Video Streaming", last_observed_at: event, support_state: "directly_supported"};
const {last_observed_at, ...last} = service;
const base = {api_version: "admin.device.service-intelligence.v1", request_id: device, site_id: site, page: null,
  result: {schema_version: 1, site_id: site, device_id: device, evaluated_at_utc: at,
    window: {from_utc: "2026-10-11T00:00:00.123456Z", to_utc: at, duration_seconds: 86400,
      recent_from_utc: "2026-10-11T23:00:00.123456Z", recent_duration_seconds: 3600},
    availability_state: "usable", evidence_state: "supported_results_present", identity_binding_state: "authoritative",
    recent_services: [service], service_categories: [{service_category_id: service.service_category_id, display_name: service.service_category_display_name, last_observed_at: event}],
    last_service_observation: {...last, observed_at: event}, freshness_state: "fresh",
    coverage: {scope: "current_pipeline", source_state: "usable", attribution_state: "usable", projection_state: "usable", recognition_state: "usable", historical_window_completeness_claimed: false},
    recognition_ruleset_id: "captivportal.network-intelligence.service-recognition", recognition_ruleset_version: 1, recognition_ruleset_digest_sha256: "a".repeat(64),
    taxonomy_id: "captivportal.network-intelligence.recognition-taxonomy", taxonomy_version: 1, taxonomy_digest_sha256: "b".repeat(64)}};
class Element {
  constructor() {this.dataset = {}; this.listeners = {}; this.children = []; this.text = ""; this.attributes = {};}
  get textContent() {return this.text + this.children.map((e) => e.textContent).join(" ");}
  set textContent(v) {this.text = String(v); this.children = [];}
  appendChild(e) {this.children.push(e);}
  replaceChildren(...e) {this.children = e; this.text = "";}
  setAttribute(k, v) {this.attributes[k] = v;}
  addEventListener(k, v) {this.listeners[k] = v;}
  click() {this.listeners.click();}
}
function fixture({enabled = true, hidden = false} = {}) {
  const ids = Object.fromEntries(["admin-page", "device-service-intelligence", "device-service-content", "device-service-state", "device-service-refresh"].map((k) => [k, new Element()]));
  ids["admin-page"].dataset = {page: "device", siteId: site, deviceId: device};
  if (!enabled) delete ids["device-service-intelligence"];
  let next = 0, now = Date.parse(at), payload = structuredClone(base), status = 200, hold = false, release, observe;
  const events = {}, timers = new Map(), calls = [];
  const document = {hidden, getElementById: (id) => ids[id] || null, createElement: () => new Element(), addEventListener: (e, fn) => {events[e] = fn;}};
  class TestDate extends Date {static now() {return now;}}
  class Observer {constructor(fn) {observe = fn;} observe() {}}
  const window = {setTimeout(fn, ms) {timers.set(++next, {fn, ms, at: now + ms}); return next;}, clearTimeout(id) {timers.delete(id);},
    addEventListener(e, fn) {events[e] = fn;}, fetch: async (url, options) => {
      calls.push({url, options});
      if (hold) await new Promise((done, reject) => {release = done; options.signal.addEventListener("abort", () => reject(new Error("abort")));});
      return {ok: status === 200, status, headers: {get: () => "application/json"}, text: async () => JSON.stringify(payload)};
    }};
  vm.runInNewContext(source, {document, window, Date: TestDate, AbortController, IntersectionObserver: Observer, TextEncoder, console});
  return {ids, calls, timers, events, document, visible: (v = true) => observe([{isIntersecting: v}]),
    setPayload: (v) => {payload = v;}, setStatus: (v) => {status = v;}, hold: () => {hold = true;}, release: () => {hold = false; release();},
    advance: (ms) => {now += ms;}, fire: (ms) => {const pair = [...timers].find(([, t]) => t.ms === ms); assert.ok(pair, `timer ${ms}`); timers.delete(pair[0]); now = Math.max(now, pair[1].at); pair[1].fn();}};
}
const settle = () => new Promise((resolve) => setImmediate(resolve));
(async () => {
  const off = fixture({enabled: false}); await settle(); assert.equal(off.calls.length, 0);
  const f = fixture(); await settle(); assert.equal(f.calls.length, 0);
  f.visible(); await settle(); assert.equal(f.calls.length, 1);
  assert.equal(f.ids["device-service-content"].children.length, 4);
  assert.match(f.ids["device-service-content"].textContent, /YouTube/);
  assert.ok(!f.ids["device-service-content"].textContent.includes("www.youtube.com"));
  assert.ok(f.calls[0].url.endsWith("/service-intelligence")); assert.equal(f.calls[0].options.cache, "no-store");
  assert.ok([...f.timers.values()].some((t) => t.ms === 120000));
  f.hold(); f.ids["device-service-refresh"].click(); await settle();
  for (let i = 0; i < 5; i++) f.ids["device-service-refresh"].click();
  assert.equal(f.calls.length, 2); f.release(); await settle(); await settle(); assert.equal(f.calls.length, 3);
  f.setStatus(503); f.ids["device-service-refresh"].click(); await settle();
  assert.match(f.ids["device-service-state"].textContent, /stale last-good/);
  f.fire(120000); await settle(); assert.ok([...f.timers.values()].some((t) => t.ms === 300000));
  f.fire(300000); await settle(); assert.ok([...f.timers.values()].some((t) => t.ms === 600000));
  f.advance(900000); f.ids["device-service-refresh"].click(); await settle(); assert.equal(f.ids["device-service-content"].children.length, 0);
  f.document.hidden = true; f.events.visibilitychange(); const before = f.calls.length;
  f.ids["device-service-refresh"].click(); await settle(); assert.equal(f.calls.length, before);
  f.document.hidden = false; f.events.visibilitychange(); await settle(); assert.equal(f.calls.length, before);
  f.advance(600000); f.events.visibilitychange(); await settle(); assert.equal(f.calls.length, before + 1);
  f.events.pagehide(); const stop = f.calls.length; f.ids["device-service-refresh"].click(); await settle(); assert.equal(f.calls.length, stop);
  const h = fixture({hidden: true}); h.visible(); await settle(); assert.equal(h.calls.length, 0);
  h.document.hidden = false; h.events.visibilitychange(); await settle(); assert.equal(h.calls.length, 1);
  h.visible(false); h.ids["device-service-refresh"].click(); await settle(); assert.equal(h.calls.length, 1);
  // Visibility and observer callbacks must obey the retained automatic deadline.
  const quick = fixture(); quick.visible(); await settle();
  quick.advance(5000); quick.document.hidden = true; quick.events.visibilitychange();
  quick.document.hidden = false; quick.events.visibilitychange(); await settle();
  assert.equal(quick.calls.length, 1);
  assert.ok([...quick.timers.values()].some((t) => t.ms === 115000));
  for (let i = 0; i < 20; i++) {quick.visible(); quick.events.visibilitychange();}
  await settle(); assert.equal(quick.calls.length, 1); assert.equal(quick.timers.size, 2);
  quick.fire(115000); await settle(); assert.equal(quick.calls.length, 2);
  quick.visible(); await settle(); assert.equal(quick.calls.length, 2);
  const delayed = fixture(); delayed.visible(); await settle(); delayed.visible(false);
  delayed.advance(120000); delayed.visible(); await settle(); assert.equal(delayed.calls.length, 2);
  const shown = fixture(); shown.visible(); await settle(); shown.document.hidden = true; shown.events.visibilitychange();
  shown.advance(125000); shown.document.hidden = false; shown.events.visibilitychange(); await settle();
  assert.equal(shown.calls.length, 2);
  const intersection = fixture(); intersection.visible(); await settle(); intersection.advance(5000);
  intersection.visible(false); intersection.visible(); await settle(); assert.equal(intersection.calls.length, 1);
  assert.ok([...intersection.timers.values()].some((t) => t.ms === 115000));
  // Failed reads retain 300/600-second retry deadlines across visibility changes.
  const retry = fixture(); retry.setStatus(503); retry.visible(); await settle();
  retry.fire(120000); await settle(); assert.equal(retry.calls.length, 2);
  retry.advance(5000); retry.document.hidden = true; retry.events.visibilitychange();
  retry.document.hidden = false; retry.events.visibilitychange();
  for (let i = 0; i < 20; i++) retry.visible();
  await settle(); assert.equal(retry.calls.length, 2); assert.equal(retry.timers.size, 1);
  retry.fire(295000); await settle(); assert.equal(retry.calls.length, 3);
  retry.advance(5000); retry.visible(false); retry.visible(); await settle();
  assert.equal(retry.calls.length, 3); assert.ok([...retry.timers.values()].some((t) => t.ms === 595000));
  // Cancellation is neutral, but cannot erase the dispatch cadence anchor.
  const cancelled = fixture(); cancelled.hold(); cancelled.visible(); await settle(); cancelled.advance(5000);
  cancelled.document.hidden = true; cancelled.events.visibilitychange(); await settle();
  cancelled.document.hidden = false; cancelled.events.visibilitychange(); await settle();
  assert.equal(cancelled.calls.length, 1); cancelled.fire(115000); await settle(); assert.equal(cancelled.calls.length, 2);
  cancelled.release(); await settle();
  // Manual Refresh still bypasses an automatic wait, with the existing one-slot gate.
  quick.ids["device-service-refresh"].click(); await settle(); assert.equal(quick.calls.length, 3);
  console.log("NI04_CADENCE_R1_PASS");
  for (const code of [401, 403, 404]) {
    const t = fixture(); t.setStatus(code); t.visible(); await settle();
    t.ids["device-service-refresh"].click(); await settle(); assert.equal(t.calls.length, 1); assert.equal(t.ids["device-service-content"].children.length, 0);
  }
  const timeout = fixture(); timeout.hold(); timeout.visible(); await settle(); timeout.fire(10000); await settle();
  assert.equal(timeout.calls[0].options.signal.aborted, true); assert.match(timeout.ids["device-service-state"].textContent, /unavailable/);
  for (const mutate of [
    (v) => {v.result.peer_ip = "raw-privacy-canary";}, (v) => {v.result.schema_version = 2;},
    (v) => {v.result.recent_services[0].sni = "raw-privacy-canary";},
    (v) => {v.result.recent_services.push(v.result.recent_services[0]);},
    (v) => {v.result.service_categories = [];}, (v) => {v.result.coverage.historical_window_completeness_claimed = true;},
    (v) => {v.result.identity_binding_state = "pending";}, (v) => {v.result.freshness_state = "stale";},
    (v) => {v.result.device_id = "other";}, (v) => {v.result.evaluated_at_utc = "2026-02-30T00:00:00.123456Z";},
    (v) => {v.result.last_service_observation.observed_at = "2026-10-11T23:55:00.123455Z";},
    (v) => {v.result.recent_services[0].last_observed_at = "2026-10-11T23:00:00.123455Z";},
  ]) {
    const t = fixture(), value = structuredClone(base); mutate(value); t.setPayload(value); t.visible(); await settle();
    assert.equal(t.ids["device-service-content"].children.length, 0); assert.ok(!t.ids["device-service-state"].textContent.includes("raw-privacy-canary"));
  }
  const empty = fixture(), value = structuredClone(base);
  Object.assign(value.result, {recent_services: [], service_categories: [], last_service_observation: null, freshness_state: "unavailable",
    evidence_state: "no_supported_result_observed_with_sufficient_coverage"});
  empty.setPayload(value); empty.visible(); await settle();
  assert.match(empty.ids["device-service-state"].textContent, /does not prove/);
  assert.equal(empty.ids["device-service-content"].children.length, 4);
  for (const forbidden of ["innerHTML", "localStorage", "sessionStorage", "indexedDB", "document.cookie", "console.log"])
    assert.ok(!source.includes(forbidden));
  console.log("NI04_FRONTEND_PASS");
})().catch((e) => {console.error(e); process.exitCode = 1;});
