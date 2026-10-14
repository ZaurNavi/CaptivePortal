"use strict";
const assert = require("node:assert/strict"), fs = require("node:fs"), vm = require("node:vm");
const full = fs.readFileSync(process.argv[2], "utf8");
const source = full.slice(full.indexOf("/* NI-04: independent bounded Service Intelligence coordinator. */"));
const site = "0123456789abcdef01234567", device = "10000000-0000-4000-8000-000000000001";
const at = "2026-10-14T12:00:00.000000Z", event = "2026-10-14T11:59:00.000000Z";
const row = (id, org, name, organization, time = event) => ({
  service_id: id, organization_id: org, display_name: name, organization_display_name: organization,
  last_observed_at: time, service_category_id: "category.other_supported",
  service_category_display_name: "Other Supported", support_state: "directly_supported",
});
const google = [
  row("service.youtube", "org.google", "YouTube", "Google"),
  row("service.gmail", "org.google", "Gmail", "Google", "2026-10-14T11:58:00.000000Z"),
  row("service.google_drive", "org.google", "Google Drive", "Google", "2026-10-14T11:57:00.000000Z"),
];
const meta = [
  row("service.instagram", "org.meta", "Instagram", "Meta", "2026-10-14T11:56:00.000000Z"),
  row("service.whatsapp", "org.meta", "WhatsApp", "Meta", "2026-10-14T11:55:00.000000Z"),
];
function payload(rows = [...google, ...meta], version = 3) {
  rows = structuredClone(rows);
  const first = rows[0], {last_observed_at, ...last} = first || {};
  return {api_version: `admin.device.service-intelligence.v${version}`, request_id: device, site_id: site, page: null, result: {
    schema_version: version, site_id: site, device_id: device, evaluated_at_utc: at,
    window: {from_utc: "2026-10-13T12:00:00.000000Z", to_utc: at, duration_seconds: 86400,
      recent_from_utc: "2026-10-14T11:00:00.000000Z", recent_duration_seconds: 3600},
    identity_binding_state: "authoritative", availability_state: "usable",
    evidence_state: first ? "supported_results_present" : "no_supported_result_observed_with_sufficient_coverage",
    freshness_state: first ? "fresh" : "unavailable",
    recent_services: rows, service_categories: first ? [{service_category_id: first.service_category_id,
      display_name: first.service_category_display_name, last_observed_at: first.last_observed_at}] : [],
    last_service_observation: first ? {...last, observed_at: last_observed_at} : null,
    coverage: {scope: "confirmed_device_evidence", source_state: "usable", pipeline_attribution_state: "usable",
      device_evidence_binding_state: "authoritative", device_linked_pending: false, recognition_state: "usable",
      historical_window_completeness_claimed: false},
    recognition_ruleset_id: "captivportal.network-intelligence.service-recognition", recognition_ruleset_version: 1,
    recognition_ruleset_digest_sha256: "a".repeat(64), taxonomy_id: "captivportal.network-intelligence.recognition-taxonomy",
    taxonomy_version: 2, taxonomy_digest_sha256: "b".repeat(64),
    ...(version === 3 ? {materialization: {state: "current", window_coverage_state: "complete",
      last_successful_update_at_utc: at, lag_seconds: 0}} : {}),
  }};
}
class Element {
  constructor(tag = "div") {this.tagName = tag; this.children = []; this.attributes = {}; this.dataset = {}; this.listeners = {}; this.text = ""; this.hidden = false;}
  get textContent() {return this.text + this.children.map(e => e.textContent).join(" ");}
  set textContent(v) {this.text = String(v); this.children = [];}
  set innerHTML(_) {throw new Error("HTML injection forbidden");}
  appendChild(e) {this.children.push(e);}
  replaceChildren(...e) {this.children = e; this.text = "";}
  setAttribute(k, v) {this.attributes[k] = v;}
  addEventListener(k, f) {this.listeners[k] = f;}
}
function fixture(p = payload(), {mode = "serve", enabled = true, http = 200} = {}) {
  const ids = Object.fromEntries(["admin-page", "device-service-intelligence", "device-service-content",
    "device-service-state", "device-service-refresh"].map(id => [id, new Element()]));
  ids["admin-page"].dataset = {page: "device", siteId: site, deviceId: device};
  ids["device-service-intelligence"].dataset = {materializationMode: mode};
  let observe, now = Date.parse(at), n = 0, calls = 0;
  const timers = new Map(), events = {};
  const document = {hidden: false, getElementById: id => !enabled && id === "device-service-intelligence" ? null : ids[id] || null,
    createElement: tag => new Element(tag), addEventListener: (e, f) => {events[e] = f;}};
  class Observer {constructor(f) {observe = f;} observe() {}}
  class Clock extends Date {static now() {return now;}}
  const window = {addEventListener: (e, f) => {events[e] = f;},
    setTimeout(f, ms) {timers.set(++n, {f, ms}); return n;}, clearTimeout(id) {timers.delete(id);},
    fetch: async () => {calls++; return {ok: http === 200, status: http,
      headers: {get: () => "application/json"}, text: async () => JSON.stringify(p)};}};
  vm.runInNewContext(source, {document, window, Date: Clock, AbortController, TextEncoder, IntersectionObserver: Observer});
  return {ids, timers, events, document, get calls() {return calls;}, visible() {if (observe) observe([{isIntersecting: true}]);},
    advance(ms) {now += ms;}, setPayload(v) {p = v;}, setStatus(v) {http = v;}};
}
const settle = () => new Promise(r => setImmediate(r));
const nodes = e => [e, ...e.children.flatMap(nodes)];
const orgCard = f => f.ids["device-service-content"].children[1];
const groups = f => orgCard(f).children.find(e => e.tagName === "ul").children;
const images = e => nodes(e).filter(n => n.tagName === "img");
let passed = 0;
async function test(name, fn) {await fn(); passed++; console.log("PASS " + name);}
async function load(p, options) {const f = fixture(p, options); f.visible(); await settle(); return f;}
(async () => {
  for (const version of [2, 3]) await test(`V${version} grouping and original cards`, async () => {
    const f = await load(payload(undefined, version), {mode: version === 3 ? "serve" : "off"});
    assert.equal(f.calls, 1);
    assert.deepEqual(f.ids["device-service-content"].children.map(e => e.children[0].textContent), [
      "Recent Services · last 60 minutes", "Organizations · last 60 minutes", "Service Categories",
      "Last Service Observation · last 24 hours", "Freshness / coverage"]);
    assert.equal(groups(f).length, 2);
    assert.match(groups(f)[0].textContent, /Google.*3 recognized services shown.*YouTube.*Gmail.*Google Drive/);
    assert.match(groups(f)[1].textContent, /Meta.*2 recognized services shown.*Instagram.*WhatsApp/);
    assert.doesNotMatch(groups(f)[0].textContent, /Instagram|WhatsApp/);
    assert.doesNotMatch(groups(f)[1].textContent, /YouTube|Gmail|Google Drive/);
    assert.match(orgCard(f).textContent, /based only on recognized services shown in this 60-minute result/);
    assert.doesNotMatch(orgCard(f).textContent, /visits|bytes|connections|usage duration|100%/);
  });
  await test("latest group wins, not count or name", async () => {
    const rows = [row("service.instagram", "org.meta", "Instagram", "Meta"), ...google.map(r => ({...r, last_observed_at: "2026-10-14T11:58:00.000000Z"})).sort((a, b) => a.service_id < b.service_id ? -1 : 1)];
    const f = await load(payload(rows)); assert.equal(nodes(groups(f)[0]).find(e => e.tagName === "h4").textContent, "Meta");
  });
  await test("equal group times use canonical org ID; members retain DTO order", async () => {
    const rows = [row("service.alpha", "org.zeta", "Alpha", "Zeta"),
      row("service.beta", "org.alpha", "Beta", "Alpha"), row("service.gamma", "org.alpha", "Gamma", "Alpha")];
    const f = await load(payload(rows)); assert.equal(nodes(groups(f)[0]).find(e => e.tagName === "h4").textContent, "Alpha");
    assert.match(groups(f)[0].textContent, /Beta.*Gamma/);
  });
  await test("same display name does not merge distinct org IDs", async () => {
    const f = await load(payload([row("service.alpha", "org.alpha", "Alpha", "Same"),
      row("service.beta", "org.beta", "Beta", "Same")]));
    assert.equal(groups(f).length, 2); groups(f).forEach(g => assert.match(g.textContent, /1 recognized service shown/));
  });
  await test("local asset allowlist and approved logo exceptions", async () => {
    const f = await load(); const srcs = images(orgCard(f)).map(e => e.src);
    assert.deepEqual(srcs, [
      "/admin/static/icons/organizations/generic.svg",
      "/admin/static/icons/services/generic.svg", "/admin/static/icons/services/generic.svg", "/admin/static/icons/services/generic.svg",
      "/admin/static/icons/organizations/generic.svg", "/admin/static/icons/services/instagram.svg", "/admin/static/icons/services/whatsapp.svg"]);
    for (const img of images(orgCard(f))) {
      assert.equal(img.attributes.alt, ""); assert.equal(img.attributes["aria-hidden"], "true");
      assert.ok(!("tabindex" in img.attributes)); assert.ok(img.src.startsWith("/admin/static/icons/"));
    }
    assert.equal(f.calls, 1);
  });
  await test("unknown canonical IDs use generic assets, never dynamic filenames", async () => {
    const f = await load(payload([row("service.unmapped", "org.unmapped", "Unmapped", "Unknown Operator")]));
    assert.deepEqual(images(orgCard(f)).map(e => e.src), [
      "/admin/static/icons/organizations/generic.svg", "/admin/static/icons/services/generic.svg"]);
  });
  await test("image failures stop at local fallback, without broken images or loops", async () => {
    const f = await load(); const image = images(orgCard(f)).find(e => e.src.endsWith("instagram.svg"));
    image.listeners.error(); assert.equal(image.src, "/admin/static/icons/services/generic.svg");
    image.listeners.error(); assert.equal(image.hidden, true);
    const tile = nodes(orgCard(f)).find(e => e.children.includes(image));
    assert.equal(tile.children[1].hidden, false); image.listeners.error(); assert.equal(image.hidden, true);
    const generic = images(orgCard(f))[0]; generic.listeners.error(); assert.equal(generic.hidden, true);
    assert.equal(f.calls, 1);
  });
  await test("hostile labels remain literal text; accessible exact timestamps", async () => {
    const hostile = '<img src=x onerror=alert(1)>';
    const f = await load(payload([row("service.whatsapp", "org.meta", hostile, "<script>alert(1)</script>")]));
    assert.ok(orgCard(f).textContent.includes(hostile));
    assert.ok(!images(orgCard(f)).some(e => e.src.includes("alert")));
    assert.equal(nodes(orgCard(f)).filter(e => e.tagName === "script").length, 0);
    const time = nodes(orgCard(f)).find(e => e.tagName === "time");
    assert.equal(time.attributes.datetime, event); assert.equal(time.attributes.title, event);
    assert.equal(time.textContent, "2026-10-14 11:59:00 UTC");
  });
  for (const [name, mutate] of [
    ["conflicting names for one organization", p => {p.result.recent_services[1].organization_display_name = "Not Google";}],
    ["duplicate service identity", p => {p.result.recent_services[1].service_id = "service.youtube";}],
    ["outside recent window", p => {p.result.recent_services[4].last_observed_at = "2026-10-14T10:59:59.999999Z";}],
    ["not directly supported", p => {p.result.recent_services[4].support_state = "inferred";}],
    ["cross-site", p => {p.result.site_id = "111111111111111111111111";}],
    ["cross-device", p => {p.result.device_id = "20000000-0000-4000-8000-000000000001";}],
    ["asset path injected as ID", p => {p.result.recent_services[0].organization_id = "//evil.example/icon.svg";}],
  ]) await test(name + " rejected without phantom groups", async () => {
    const p = payload(); mutate(p); const f = await load(p);
    assert.equal(f.ids["device-service-content"].children.length, 0);
  });
  await test("12 services / groups accepted, 13 rejected", async () => {
    const rows = Array.from({length: 12}, (_, i) => row(`service.item${String(i).padStart(2, "0")}`,
      `org.item${String(i).padStart(2, "0")}`, "Service", "Organization"));
    const f = await load(payload(rows)); assert.equal(groups(f).length, 12);
    rows.push(row("service.item12", "org.item12", "Service", "Organization"));
    assert.equal((await load(payload(rows))).ids["device-service-content"].children.length, 0);
  });
  await test("empty has no branded or zero-count tiles", async () => {
    const f = await load(payload([])); assert.match(orgCard(f).textContent, /No confirmed organizations.*does not mean the device had no network activity/);
    assert.equal(images(orgCard(f)).length, 0); assert.doesNotMatch(orgCard(f).textContent, /0 recognized/);
  });
  await test("24h-only observation is never included in organizations", async () => {
    const p = payload([]), {last_observed_at, ...last} = google[0];
    p.result.last_service_observation = {...last, observed_at: "2026-10-14T10:00:00.000000Z"};
    p.result.freshness_state = "stale"; p.result.evidence_state = "supported_results_present";
    const f = await load(p); assert.equal(images(orgCard(f)).length, 0);
    assert.doesNotMatch(orgCard(f).textContent, /Google|YouTube/);
    assert.match(f.ids["device-service-content"].children[3].textContent, /YouTube/);
  });
  for (const state of ["lagging", "backfilling", "unavailable", "capacity_halted", "conflict"])
    await test(state + " stored facts qualified; no independent requests", async () => {
      const p = payload(); p.result.materialization.state = state;
      p.result.materialization.window_coverage_state = "partial"; p.result.availability_state = "degraded";
      const f = await load(p); assert.equal(groups(f).length, 2); assert.equal(f.calls, 1);
      assert.match(f.ids["device-service-state"].textContent, /behind.*may be missing/);
    });
  await test("limited recognition and partial attribution stay visibly qualified", async () => {
    const p = payload(); p.result.coverage.recognition_state = "limited";
    p.result.coverage.pipeline_attribution_state = "degraded"; p.result.availability_state = "degraded";
    const f = await load(p); assert.match(f.ids["device-service-state"].textContent, /coverage is partial/);
    assert.match(f.ids["device-service-content"].textContent, /Recognition: limited/);
  });
  for (const state of ["pending", "absent", "unavailable"]) await test(state + " identity has no positive group", async () => {
    const p = payload([]); p.result.identity_binding_state = state;
    p.result.coverage.device_evidence_binding_state = "none"; p.result.availability_state = "degraded";
    p.result.evidence_state = "identity_pending"; const f = await load(p); assert.equal(images(orgCard(f)).length, 0);
    const bad = payload(); bad.result.identity_binding_state = state;
    bad.result.coverage.device_evidence_binding_state = "none";
    assert.equal((await load(bad)).ids["device-service-content"].children.length, 0);
  });
  for (const http of [401, 403, 404]) await test(http + " access failure clears facts and stops", async () => {
    const f = await load(undefined, {http}); assert.equal(f.ids["device-service-content"].children.length, 0);
    f.ids["device-service-refresh"].listeners.click(); await settle(); assert.equal(f.calls, 1);
  });
  await test("last-good grouping expires at 15 minutes", async () => {
    const f = await load(); f.setStatus(503); f.ids["device-service-refresh"].listeners.click(); await settle();
    assert.equal(groups(f).length, 2); assert.match(f.ids["device-service-state"].textContent, /stale last-good/);
    f.advance(900000); const age = [...f.timers.values()].find(t => t.ms === 900000); assert.ok(age); age.f();
    assert.equal(f.ids["device-service-content"].children.length, 0);
    assert.match(f.ids["device-service-state"].textContent, /expired.*unknown/);
  });
  await test("invalid refreshed org names cannot replace last-good facts", async () => {
    const f = await load(), bad = payload();
    bad.result.recent_services[1].organization_display_name = "Conflicting Operator";
    f.setPayload(bad); f.ids["device-service-refresh"].listeners.click(); await settle();
    assert.match(f.ids["device-service-state"].textContent, /stale last-good/);
    assert.equal(groups(f).length, 2);
    assert.doesNotMatch(orgCard(f).textContent, /Conflicting Operator/);
  });
  await test("exact 60-minute lower boundary included; older value rejected", async () => {
    const p = payload([row("service.alpha", "org.alpha", "Alpha", "Alpha", "2026-10-14T11:00:00.000000Z")]);
    p.result.freshness_state = "recent";
    assert.equal(groups(await load(p)).length, 1);
    p.result.recent_services[0].last_observed_at = "2026-10-14T10:59:59.999999Z";
    assert.equal((await load(p)).ids["device-service-content"].children.length, 0);
  });
  await test("long NFC localized labels are preserved, never truncated", async () => {
    const name = "Длинное подтверждённое название сервиса без сокращений";
    const organization = "Uzun təşkilat adı — təsdiqlənmiş xidmətlərin təşkilatı";
    const f = await load(payload([row("service.alpha", "org.alpha", name, organization)]));
    assert.ok(orgCard(f).textContent.includes(name)); assert.ok(orgCard(f).textContent.includes(organization));
  });
  await test("disabled section does no work", async () => {
    const f = await load(undefined, {enabled: false}); assert.equal(f.calls, 0); assert.equal(f.timers.size, 0);
  });
  await test("semantic headings/lists, no added keyboard stops or external hrefs", async () => {
    const f = await load();
    assert.equal(orgCard(f).children[0].tagName, "h3");
    assert.equal(groups(f)[0].tagName, "li");
    assert.equal(nodes(orgCard(f)).filter(e => e.tagName === "h4").length, 2);
    assert.ok(nodes(orgCard(f)).every(e => !("href" in e.attributes) && !("tabindex" in e.attributes)));
    for (const forbidden of ["innerHTML", "localStorage", "sessionStorage", "indexedDB", "document.cookie", "console.log"])
      assert.ok(!source.includes(forbidden));
  });
  console.log(`NI05_ORGANIZATION_CONTEXT_PASS ${passed} scenarios`);
})().catch(error => {console.error(error); process.exitCode = 1;});
