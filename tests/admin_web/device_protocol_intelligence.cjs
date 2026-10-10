"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(process.argv[2], "utf8");
const site = "0123456789abcdef01234567", device = "10000000-0000-4000-8000-000000000001";
const at = "2026-10-09T12:00:00.000000Z";
const base = {
  api_version: "admin.device.protocol-intelligence.v1", request_id: device, site_id: site, page: null,
  result: {schema_version: 1, site_id: site, device_id: device, evaluated_at_utc: at,
    window: {from_utc: "2026-10-08T12:00:00.000000Z", to_utc: at, duration_seconds: 86400,
      recent_from_utc: "2026-10-09T11:00:00.000000Z", recent_duration_seconds: 3600},
    availability_state: "usable", evidence_state: "present", identity_binding_state: "authoritative",
    recent_protocols: [{protocol_id: "dns", display_label: "DNS", last_observed_at: "2026-10-09T11:59:59.000000Z"}],
    last_protocol_observation: {protocol_id: "dns", display_label: "DNS", observed_at: "2026-10-09T11:59:59.000000Z"},
    freshness_state: "fresh", coverage: {scope: "current_pipeline", source_state: "usable", attribution_state: "usable",
      projection_state: "usable", historical_window_completeness_claimed: false}}
};
const settle = () => new Promise((resolve) => setImmediate(resolve));
class Element {
  constructor() {this.dataset = {}; this.listeners = {}; this.children = []; this.textContent = "";}
  addEventListener(type, fn) {(this.listeners[type] ??= []).push(fn);}
  append(...items) {this.children.push(...items);}
  replaceChildren(...items) {this.children = items;}
  click() {for (const fn of this.listeners.click || []) fn();}
}
function fixture(enabled = true, hidden = false) {
  let now = Date.parse(at), next = 0, calls = [], payload = structuredClone(base), status = 200, hold = false, resolve = null;
  const timers = new Map(), events = {};
  const ids = Object.fromEntries(["admin-page", "device-protocol-intelligence", "device-protocol-content", "device-protocol-state-title", "device-protocol-state-message", "device-protocol-refresh", "refresh-button"].map((key) => [key, new Element()]));
  ids["admin-page"].dataset = {page: "device", siteId: site, deviceId: device};
  if (!enabled) delete ids["device-protocol-intelligence"];
  const document = {hidden, getElementById: (id) => ids[id] || null, createElement: () => new Element(),
    addEventListener: (type, fn) => {events[type] = fn;}};
  class TestDate extends Date {static now() {return now;}}
  const context = {document, Date: TestDate, AbortController, Set, Object, Array, Number, Error,
    window: {setTimeout: (fn, ms) => {const id = ++next; timers.set(id, {fn, ms}); return id;},
      clearTimeout: (id) => timers.delete(id), addEventListener: (type, fn) => {events[type] = fn;}},
    fetch: async (url, options) => {
      calls.push({url, options});
      if (hold) await new Promise((done, reject) => {resolve = done; options.signal.addEventListener("abort", () => reject(new Error("abort")));});
      return {ok: status === 200, status, json: async () => payload};
    }};
  vm.runInNewContext(source, context);
  return {ids, calls, timers, events, document, context,
    setPayload: (value) => {payload = value;}, setStatus: (value) => {status = value;},
    setHold: (value) => {hold = value;}, release: () => {hold = false; resolve();},
    advance: (ms) => {now += ms;},
    fire: (ms) => {const entry = [...timers].find(([, timer]) => timer.ms === ms); assert.ok(entry, `timer ${ms}`); timers.delete(entry[0]); entry[1].fn();}};
}
(async () => {
  const off = fixture(false); await settle(); assert.equal(off.calls.length, 0);
  const hidden = fixture(true, true); await settle(); assert.equal(hidden.calls.length, 0);
  hidden.document.hidden = false; hidden.events.visibilitychange(); await settle(); assert.equal(hidden.calls.length, 1);
  const f = fixture(); await settle(); await settle();
  assert.equal(f.calls.length, 1); assert.equal(f.ids["device-protocol-content"].children.length, 6);
  assert.equal(f.ids["device-protocol-content"].children[2].children[1].textContent, "Fresh");
  assert.ok(f.calls[0].url.endsWith("/protocol-intelligence")); assert.equal(f.calls[0].options.cache, "no-store");
  f.setHold(true); f.ids["device-protocol-refresh"].click(); await settle();
  for (let i = 0; i < 5; i++) f.ids["refresh-button"].click();
  assert.equal(f.calls.length, 2); f.release(); await settle(); await settle(); assert.equal(f.calls.length, 3);
  f.document.hidden = true; f.events.visibilitychange(); assert.ok(![...f.timers.values()].some((t) => t.ms === 60000));
  f.advance(30000); f.document.hidden = false; f.events.visibilitychange();
  assert.equal(f.calls.length, 3); assert.ok([...f.timers.values()].some((t) => t.ms === 30000));
  f.advance(30000); f.fire(30000); await settle(); assert.equal(f.calls.length, 4);
  f.setStatus(503); f.ids["device-protocol-refresh"].click(); await settle();
  assert.equal(f.ids["device-protocol-content"].children.length, 6); assert.match(f.ids["device-protocol-state-message"].textContent, /last successful/);
  f.fire(60000); await settle(); assert.ok([...f.timers.values()].some((t) => t.ms === 120000));
  f.fire(120000); await settle(); assert.ok([...f.timers.values()].some((t) => t.ms === 300000));
  f.setStatus(200); f.ids["device-protocol-refresh"].click(); await settle(); assert.ok([...f.timers.values()].some((t) => t.ms === 60000));
  f.setStatus(503); f.advance(840000); f.ids["device-protocol-refresh"].click(); await settle();
  assert.equal(f.ids["device-protocol-content"].children.length, 0);
  f.events.pagehide(); const stopped = f.calls.length; f.ids["device-protocol-refresh"].click(); await settle(); assert.equal(f.calls.length, stopped);
  for (const status of [401, 403, 404]) {
    const t = fixture(); await settle(); t.setStatus(status); t.ids["device-protocol-refresh"].click(); await settle();
    const before = t.calls.length; t.ids["refresh-button"].click(); await settle(); assert.equal(t.calls.length, before);
  }
  const timeout = fixture(); await settle(); timeout.setHold(true); timeout.ids["refresh-button"].click(); await settle();
  timeout.fire(10000); await settle(); assert.ok(timeout.calls.at(-1).options.signal.aborted);
  for (const mutate of [
    (v) => {v.result.peer_ip = "private";}, (v) => {v.result.schema_version = 2;},
    (v) => {v.result.recent_protocols[0].protocol_id = "tcp";},
    (v) => {v.result.recent_protocols[0].display_label = "private";},
    (v) => {v.result.recent_protocols.push(v.result.recent_protocols[0]);},
    (v) => {v.result.coverage.historical_window_completeness_claimed = true;},
    (v) => {v.result.evaluated_at_utc = "2026-02-30T12:00:00.000000Z";},
    (v) => {v.result.device_id = "other";}, (v) => {v.result.window.duration_seconds = NaN;}
  ]) {
    const t = fixture(true, true), value = structuredClone(base); mutate(value); t.setPayload(value);
    t.document.hidden = false; t.events.visibilitychange(); await settle();
    assert.equal(t.ids["device-protocol-content"].children.length, 0); assert.match(t.ids["device-protocol-state-title"].textContent, /unavailable/);
  }
  for (const state of ["empty", "identity_pending"]) {
    const t = fixture(true, true), value = structuredClone(base);
    Object.assign(value.result, {evidence_state: state, freshness_state: "unavailable", recent_protocols: [], last_protocol_observation: null,
      identity_binding_state: state === "empty" ? "authoritative" : "pending",
      availability_state: state === "empty" ? "usable" : "degraded"});
    t.setPayload(value); t.document.hidden = false; t.events.visibilitychange(); await settle();
    assert.equal(t.ids["device-protocol-content"].children.length, 6);
    assert.match(t.ids["device-protocol-state-title"].textContent, state === "empty" ? /No recent/ : /binding pending/);
  }
  for (const projection of ["usable", "degraded"]) {
    for (const identity of ["authoritative", "pending", "unavailable", "absent"]) {
      const value = structuredClone(base);
      Object.assign(value.result, {evidence_state: identity === "authoritative" ? "empty" : "identity_pending",
        identity_binding_state: identity, freshness_state: "unavailable", recent_protocols: [], last_protocol_observation: null,
        availability_state: projection === "usable" && identity === "authoritative" ? "usable" : "degraded"});
      value.result.coverage.projection_state = projection;
      const valid = fixture(true, true);
      valid.setPayload(value); valid.document.hidden = false; valid.events.visibilitychange(); await settle();
      assert.equal(valid.ids["device-protocol-content"].children.length, 6);
      const invalid = fixture(true, true), contradiction = structuredClone(value);
      contradiction.result.availability_state = value.result.availability_state === "usable" ? "degraded" : "usable";
      invalid.setPayload(contradiction); invalid.document.hidden = false; invalid.events.visibilitychange(); await settle();
      assert.equal(invalid.ids["device-protocol-content"].children.length, 0);
      assert.match(invalid.ids["device-protocol-state-title"].textContent, /unavailable/);
    }
  }
  for (const freshness of ["recent", "stale"]) {
    const t = fixture(true, true), value = structuredClone(base);
    value.result.freshness_state = freshness;
    value.result.availability_state = "degraded";
    Object.assign(value.result.coverage, {projection_state: "degraded", attribution_state: freshness === "stale" ? "unknown" : "degraded", source_state: freshness === "stale" ? "unavailable" : "usable"});
    t.setPayload(value); t.document.hidden = false; t.events.visibilitychange(); await settle();
    assert.equal(t.ids["device-protocol-content"].children[2].children[1].textContent, freshness === "stale" ? "Stale" : "Recent");
  }
  const empty = fixture(true, true), emptyValue = structuredClone(base);
  Object.assign(emptyValue.result, {evidence_state: "empty", freshness_state: "unavailable", recent_protocols: [], last_protocol_observation: null, availability_state: "degraded"});
  Object.assign(emptyValue.result.coverage, {projection_state: "degraded", attribution_state: "degraded"});
  empty.setPayload(emptyValue); empty.document.hidden = false; empty.events.visibilitychange(); await settle();
  assert.equal(empty.ids["device-protocol-state-title"].textContent, "Insufficient coverage");
  console.log("NI03_FRONTEND_PASS");
})().catch((error) => {console.error(error); process.exitCode = 1;});
