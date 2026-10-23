const assert = require("node:assert/strict"), fs = require("node:fs"), vm = require("node:vm");
const source = fs.readFileSync(process.argv[2], "utf8");
const site = "0123456789abcdef01234567", device = "10000000-0000-4000-8000-000000000001";
const visit = "20000000-0000-4000-8000-000000000001";
class Element {
  constructor(tag) {this.tagName = tag; this.dataset = {}; this.children = []; this.listeners = {}; this.isConnected = true; this.top = 1; this.textContent = "";}
  append(...values) {this.children.push(...values);}
  replaceChildren(...values) {this.children = values;}
  setAttribute(name, value) {this[name] = value;}
  addEventListener(name, fn) {this.listeners[name] = fn;}
  getBoundingClientRect() {return {top: this.top, bottom: this.top + 30};}
  text() {return this.textContent + this.children.map(c => c.text()).join(" ");}
}
function dto(id = visit) {
  const fact = {protocol_id: "tls", last_observed_at: "2026-10-21T10:01:00.000001Z"};
  return {api_version: "admin.visit.protocol-intelligence.v1",request_id: "30000000-0000-4000-8000-000000000001",site_id: site,page: null,
    result: {type: "VisitProtocolSummaryV1",schema_version: 1,site_id: site,device_id: device,visit_id: id,visit_status: "open",
      started_at: "2026-10-21T10:00:00.000Z",closed_at: null,summary_state: "active",protocols: [fact],last_protocol_observation: fact,
      evaluated_at: "2026-10-21T10:02:00.000Z",source_coverage: "bounded_partial",attribution_coverage: "current_available",
      finalized_at: null,partial_reason: "bounded_source",historical_completeness_claimed: false}};
}
function serviceDto(id = visit) {
  const envelope = dto(id), v = envelope.result;
  envelope.api_version = "admin.visit.recognized-services.v1";
  envelope.result = {type:"VisitServiceHistoryV1",schema_version:1,site_id:site,device_id:device,visit_id:id,visit_status:"open",
    started_at:v.started_at,closed_at:null,history_state:"processing",partial_reason:"backfill_limited",evaluated_at:v.evaluated_at,
    truncated:false,historical_completeness_claimed:false,services:[{service_id:"service.youtube",display_name:"YouTube",organization_id:"org.google",
      organization_display_name:"Google",first_observed_at:v.protocols[0].last_observed_at,last_observed_at:v.protocols[0].last_observed_at,
      distinct_observation_count:2,status:"processing",finalized_at:null,taxonomy:{id:"taxonomy",version:1,digest_sha256:"a".repeat(64)},
      ruleset:{id:"ruleset",version:1,digest_sha256:"b".repeat(64)},provenance:"materialized_ni04_strong_observation"}]};
  return envelope;
}
function setup(ids = [visit]) {
  let now = 0, timerId = 0, observer;
  const roots = ids.map(id => {const e = new Element("section"); e.dataset = {visitId: id,deviceId: device,visitStatus: "open"}; return e;});
  const timers = new Map(), events = {}, requests = [], queue = [];
  const page = {dataset: {page: "device",siteId: site},querySelectorAll: selector => {assert.equal(selector,".visit-network-results"); return roots.filter(r => r.isConnected);}};
  const document = {hidden: false,getElementById: id => id === "admin-page" ? page : null,createElement: tag => new Element(tag)};
  const window = {innerHeight: 800,addEventListener: (name,fn) => events[name] = fn,
    setTimeout: (fn,delay) => {timers.set(++timerId,{fn,at: now + delay});return timerId;},clearTimeout: id => timers.delete(id)};
  const context = {document,window,AbortController,Date: class extends Date {static now() {return now;}},
    MutationObserver: class {constructor(fn) {observer = this;this.fn = fn;} observe() {} disconnect() {this.disconnected = true;}},
    fetch: (url,options) => {
      requests.push({url,options});
      return queue.length ? queue.shift()(url,options) : Promise.resolve({ok: true,status: 200,json: async () => (url.endsWith("/recognized-services") ? serviceDto : dto)(url.split("/visits/")[1].split("/")[0])});
    }};
  vm.runInNewContext(source,context);
  async function settle() {for (let i = 0;i < 15;i++) await Promise.resolve();}
  async function advance(milliseconds) {
    now += milliseconds;
    const due = [...timers].filter(([,t]) => t.at <= now);
    for (const [id,t] of due) {if (timers.delete(id)) t.fn();}
    await settle();
  }
  return {roots,get requests() {return requests.filter(r=>r.url.endsWith("/protocol-intelligence"));},allRequests:requests,
    queue,document,events,timers,settle,advance,get observer() {return observer;}};
}
(async () => {
  vm.runInNewContext(source,{}); // DOM-less Node stays inert.
  let s = setup(); await s.settle();
  assert.equal(s.requests.length,1);
  assert.equal(s.requests[0].url,`/admin/api/v2/sites/${site}/devices/${device}/visits/${visit}/protocol-intelligence`);
  assert.equal(s.requests[0].options.credentials,"same-origin");assert.equal(s.requests[0].options.cache,"no-store");
  assert.match(s.roots[0].text(),/TLS/); assert.doesNotMatch(s.roots[0].text(),/24h|60m/);
  assert.match(s.roots[0].text(),/YouTube/);assert.match(s.roots[0].text(),/2 distinct confirmed observations/);
  assert.equal(s.allRequests.length,2);assert.ok(s.allRequests[1].url.endsWith(`/visits/${visit}/recognized-services`));
  await s.advance(29999); assert.equal(s.requests.length,1);
  await s.advance(1001); assert.equal(s.requests.length,2);
  s.document.hidden = true; await s.advance(120000); assert.equal(s.requests.length,2);
  s.document.hidden = false; await s.advance(1000); assert.equal(s.requests.length,3);
  // Closing is learned through the bound Visit response, not a Device-wide query.
  s.queue.push(async () => {const v = dto();v.result.visit_status = "closed";v.result.closed_at = "2026-10-21T10:01:30.000Z";return {ok:true,status:200,json:async()=>v};});
  await s.advance(30000); assert.equal(s.roots[0].dataset.visitStatus,"closed");
  const closedCount = s.requests.length;await s.advance(120000);assert.equal(s.requests.length,closedCount);
  s.events.pagehide();assert.equal(s.timers.size,0);assert.equal(s.observer.disconnected,true);
  // Unknown identity never substitutes today's MAC or the containing Device ID.
  s = setup([""]);await s.settle();assert.equal(s.requests.length,0);assert.match(s.roots[0].text(),/binding pending/);
  // Bounded global concurrency and fairness across cards.
  const ids = Array.from({length:6},(_,i)=>`20000000-0000-4000-8000-00000000000${i}`);
  s = setup(ids);await s.settle();assert.equal(s.requests.length,2);
  await s.advance(1000);assert.equal(s.requests.length,4);
  await s.advance(1000);assert.equal(s.requests.length,6);
  assert.equal(new Set(s.requests.map(r=>r.url)).size,6);
  // Every invalid identity/shape/boundary must fail closed and clear cached facts.
  for (const mutate of [v=>v.result.visit_id = ids[0],v=>v.result.site_id = "foreign",v=>v.result.device_id = ids[0],
    v=>v.result.client_mac = "private",v=>v.result.protocols[0].last_observed_at = "2026-10-21T09:59:59.000000Z",
    v=>v.result.protocols.push(v.result.protocols[0]),v=>v.result.historical_completeness_claimed = true,
    v=>v.result.protocols[0].last_observed_at = "2026-10-21T10:02:00.000001Z"]) {
    s = setup();await s.settle();s.queue.push(async()=>{const v=dto();mutate(v);return {ok:true,status:200,json:async()=>v};});
    await s.advance(30000);assert.match(s.roots[0].text(),/temporarily unavailable/);assert.doesNotMatch(s.roots[0].text(),/TLS/);
  }
  s = setup();await s.settle();s.roots[0].top = 1000;await s.advance(60000);assert.equal(s.requests.length,1);
  s.roots[0].top = 1;s.roots[0].isConnected = false;s.observer.fn();await s.advance(60000);assert.equal(s.requests.length,1);
  for (const mutate of [v=>v.result.visit_id=ids[0],v=>v.result.services[0].distinct_observation_count=true,
    v=>v.result.services[0].first_observed_at="2026-10-21T09:00:00.000000Z",v=>v.result.services[0].sni="private",
    v=>v.result.services.push(v.result.services[0]),v=>v.result.historical_completeness_claimed=true]) {
    s=setup();await s.settle();
    s.queue.push(async()=>({ok:true,status:200,json:async()=>dto()}));
    s.queue.push(async()=>{const v=serviceDto();mutate(v);return {ok:true,status:200,json:async()=>v};});
    await s.advance(30000);assert.match(s.roots[0].text(),/TLS/);assert.doesNotMatch(s.roots[0].text(),/YouTube/);
    assert.match(s.roots[0].text(),/service results temporarily unavailable/);
  }
  // NI03 outage cannot suppress a valid NI04 section; closure stops BOTH lanes.
  s=setup();await s.settle();
  s.queue.push(async()=>({ok:false,status:503}));
  s.queue.push(async()=>{const v=serviceDto();v.result.visit_status="closed";v.result.closed_at="2026-10-21T10:01:30.000Z";return {ok:true,status:200,json:async()=>v};});
  await s.advance(30000);assert.match(s.roots[0].text(),/YouTube/);assert.doesNotMatch(s.roots[0].text(),/TLS/);
  const count=s.allRequests.length;await s.advance(120000);assert.equal(s.allRequests.length,count);
  assert.doesNotMatch(source,/\/admin\/api\/v1|recent_protocols|duration_seconds/);
  console.log("NI03_FRONTEND_PASS");
})().catch(error=>{console.error(error);process.exitCode=1;});
