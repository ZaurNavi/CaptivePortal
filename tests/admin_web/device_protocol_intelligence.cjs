"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(process.argv[2], "utf8");
const css = fs.readFileSync(require("node:path").join(require("node:path").dirname(process.argv[2]), "admin.css"), "utf8");
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
  constructor(tag = "div") {this.tagName = tag.toUpperCase(); this.dataset = {}; this.listeners = {}; this.children = []; this._text = "";}
  get textContent() {return this._text + this.children.map((child) => child.textContent).join("");}
  set textContent(value) {this._text = String(value); this.children = [];}
  addEventListener(type, fn) {(this.listeners[type] ??= []).push(fn);}
  append(...items) {this.children.push(...items);}
  replaceChildren(...items) {this._text = ""; this.children = items;}
  click() {for (const fn of this.listeners.click || []) fn();}
}
function fixture(enabled = true, hidden = false) {
  let now = Date.parse(at), next = 0, calls = [], payload = structuredClone(base), status = 200, hold = false, resolve = null;
  const timers = new Map(), events = {};
  const ids = Object.fromEntries(["admin-page", "device-protocol-intelligence", "device-protocol-content", "device-protocol-state-title", "device-protocol-state-message", "device-protocol-refresh", "refresh-button"].map((key) => [key, new Element()]));
  ids["admin-page"].dataset = {page: "device", siteId: site, deviceId: device};
  if (!enabled) delete ids["device-protocol-intelligence"];
  const document = {hidden, getElementById: (id) => ids[id] || null, createElement: (tag) => new Element(tag),
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
const fieldLabels = ["Recent Protocols", "Last Protocol Observation", "Freshness", "Source coverage", "Attribution coverage", "Last evaluated"];
function assertCards(f) {
  const cards = f.ids["device-protocol-content"].children;
  assert.equal(cards.length, 6);
  assert.deepEqual(cards.map((card) => card.children[0].textContent), fieldLabels);
  for (const card of cards) {
    assert.ok(card.className.split(" ").includes("card"));
    assert.ok(card.className.split(" ").includes("protocol-info-card"));
    assert.equal(card.children[0].className, "protocol-info-label");
    assert.equal(card.children[1].className, "protocol-info-value");
  }
  for (const [index, variant] of [[0, "recent"], [1, "last"], [2, "freshness"]]) {
    assert.ok(cards[index].className.split(" ").includes("protocol-info-card--" + variant));
  }
  return cards;
}
function assertTime(time, raw, display) {
  assert.equal(time.tagName, "TIME"); assert.equal(time.dateTime, raw);
  assert.equal(time.title, raw); assert.equal(time.textContent, display);
}
function assertStatus(card, state, label) {
  const badge = card.children[1].children[0];
  assert.equal(badge.className, "protocol-status"); assert.equal(badge.dataset.state, state);
  assert.equal(badge.textContent, label);
}
(async () => {
  const off = fixture(false); await settle(); assert.equal(off.calls.length, 0);
  const hidden = fixture(true, true); await settle(); assert.equal(hidden.calls.length, 0);
  hidden.document.hidden = false; hidden.events.visibilitychange(); await settle(); assert.equal(hidden.calls.length, 1);
  const f = fixture(); await settle(); await settle();
  assert.equal(f.calls.length, 1); assert.equal(f.ids["device-protocol-content"].children.length, 6);
  const cards = assertCards(f);
  assert.equal(f.ids["device-protocol-content"].children[2].children[1].textContent, "Fresh");
  assertStatus(cards[2], "fresh", "Fresh"); assertStatus(cards[3], "usable", "Available");
  assertStatus(cards[4], "usable", "Available");
  assertTime(cards[5].children[1].children[0], at, "09.10.2026, 12:00:00 UTC");
  assert.equal(f.ids["device-protocol-state-title"].textContent, "Protocol evidence");
  assert.equal(f.ids["device-protocol-state-message"].textContent, "Recent device-relative protocol evidence; historical completeness is not claimed.");
  const three = fixture(true, true), threeValue = structuredClone(base);
  threeValue.result.recent_protocols = ["dns", "tls", "quic"].map((protocol) => ({protocol_id: protocol,
    display_label: protocol.toUpperCase(), last_observed_at: "2026-10-09T11:59:59.327200Z"}));
  threeValue.result.last_protocol_observation.observed_at = "2026-10-09T11:59:59.327200Z";
  three.setPayload(threeValue); three.document.hidden = false; three.events.visibilitychange(); await settle();
  const threeCards = assertCards(three), chips = threeCards[0].children[1].children[0];
  assert.equal(chips.className, "protocol-chip-list"); assert.equal(chips.children.length, 3);
  assert.deepEqual(chips.children.map((chip) => chip.children[0].textContent), ["DNS", "TLS", "QUIC"]);
  for (const chip of chips.children) {
    assert.equal(chip.className, "protocol-chip"); assert.equal(chip.children[0].tagName, "STRONG");
    assertTime(chip.children[1], "2026-10-09T11:59:59.327200Z", "09.10.2026, 11:59:59 UTC");
  }
  assertTime(threeCards[1].children[1].children[0].children[1], "2026-10-09T11:59:59.327200Z", "09.10.2026, 11:59:59 UTC");
  assert.ok(!chips.textContent.includes(";")); assert.ok(!chips.textContent.includes("327200"));
  assert.deepEqual(threeValue.result.recent_protocols.map((item) => item.last_observed_at), Array(3).fill("2026-10-09T11:59:59.327200Z"));
  const ordered = fixture(true, true), orderedValue = structuredClone(threeValue);
  orderedValue.result.recent_protocols = ["quic", "dns", "tls"].map((protocol, index) => ({protocol_id: protocol,
    display_label: protocol.toUpperCase(), last_observed_at: `2026-10-09T11:59:5${9 - index}.327200Z`}));
  orderedValue.result.last_protocol_observation = {protocol_id: "quic", display_label: "QUIC", observed_at: orderedValue.result.recent_protocols[0].last_observed_at};
  ordered.setPayload(orderedValue); ordered.document.hidden = false; ordered.events.visibilitychange(); await settle();
  assert.deepEqual(assertCards(ordered)[0].children[1].children[0].children.map((chip) => chip.children[0].textContent), ["QUIC", "DNS", "TLS"]);
  const dated = fixture(true, true), datedValue = structuredClone(base), rawDate = "2026-10-10T08:07:45.327200Z";
  datedValue.result.evaluated_at_utc = rawDate;
  Object.assign(datedValue.result.window, {to_utc: rawDate, from_utc: "2026-10-09T08:07:45.327200Z", recent_from_utc: "2026-10-10T07:07:45.327200Z"});
  datedValue.result.recent_protocols[0].last_observed_at = "2026-10-10T08:07:44.327200Z";
  datedValue.result.last_protocol_observation.observed_at = "2026-10-10T08:07:44.327200Z";
  dated.advance(Date.parse(rawDate) - Date.parse(at));
  dated.setPayload(datedValue); dated.document.hidden = false; dated.events.visibilitychange(); await settle();
  assertTime(assertCards(dated)[5].children[1].children[0], rawDate, "10.10.2026, 08:07:45 UTC");
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
    const emptyCards = assertCards(t);
    assert.equal(emptyCards[0].children[1].textContent, "—"); assert.equal(emptyCards[1].children[1].textContent, "—");
    assertStatus(emptyCards[2], "unavailable", "Unavailable");
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
    const statusCards = assertCards(t);
    assertStatus(statusCards[2], freshness, freshness === "stale" ? "Stale" : "Recent");
    assertStatus(statusCards[3], freshness === "stale" ? "unavailable" : "usable", freshness === "stale" ? "Unavailable" : "Available");
    assertStatus(statusCards[4], freshness === "stale" ? "unknown" : "degraded", freshness === "stale" ? "Unknown" : "Degraded");
    if (freshness === "stale") {
      assert.equal(t.ids["device-protocol-state-title"].textContent, "Stale evidence");
      assert.equal(t.ids["device-protocol-state-message"].textContent, "Last evaluated 09.10.2026, 12:00:00 UTC");
      assertTime(t.ids["device-protocol-state-message"].children[0], at, "09.10.2026, 12:00:00 UTC");
    }
  }
  const empty = fixture(true, true), emptyValue = structuredClone(base);
  Object.assign(emptyValue.result, {evidence_state: "empty", freshness_state: "unavailable", recent_protocols: [], last_protocol_observation: null, availability_state: "degraded"});
  Object.assign(emptyValue.result.coverage, {projection_state: "degraded", attribution_state: "degraded"});
  empty.setPayload(emptyValue); empty.document.hidden = false; empty.events.visibilitychange(); await settle();
  assert.equal(empty.ids["device-protocol-state-title"].textContent, "Insufficient coverage");
  assertStatus(assertCards(empty)[4], "degraded", "Degraded");
  const protocolCss = css.slice(css.indexOf("/* NI-03 presentation only;"));
  assert.ok(protocolCss.startsWith("/* NI-03 presentation only;"));
  for (const line of protocolCss.split("\n")) {
    if (!line.trim() || line.trim().startsWith("/*") || line.trim() === "}" || line.trim().startsWith("@media")) continue;
    assert.ok(line.trim().startsWith("#device-protocol-intelligence"), "scoped protocol CSS only");
  }
  for (const [state, background, color] of [["usable", "#d9f3ef", "#24514f"], ["fresh", "#d9f3ef", "#24514f"],
    ["recent", "#e7f1ff", "#175cd3"], ["degraded", "#fef0c7", "#734c00"], ["stale", "#fef0c7", "#734c00"],
    ["unavailable", "#fee4e2", "#7a271a"], ["unknown", "#eef2f4", "#667482"]]) {
    const rule = protocolCss.match(new RegExp('\\[data-state="' + state + '"\\][\\s\\S]*?\\{([^}]+)\\}'));
    assert.ok(rule, state + " style"); assert.ok(rule[1].includes("background: " + background));
    assert.ok(rule[1].includes("color: " + color));
  }
  assert.match(protocolCss, /protocol-info-card--recent \{ grid-column: 1 \/ -1;/);
  assert.match(protocolCss, /protocol-info-card--freshness \{ grid-column: span 6;/);
  assert.match(protocolCss, /@media \(max-width: 820px\)/);
  assert.match(protocolCss, /@media \(max-width: 560px\)/);
  assert.match(protocolCss, /overflow-wrap: anywhere/);
  console.log("NI03_FRONTEND_PASS");
})().catch((error) => {console.error(error); process.exitCode = 1;});
