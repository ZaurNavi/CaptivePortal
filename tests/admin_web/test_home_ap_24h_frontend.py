from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "app" / "admin_web" / "static" / "admin.js"


def test_home_ap_24h_real_node_contract(tmp_path):
    node = shutil.which("node")
    assert node is not None, "Node is mandatory for the AP-24H frontend gate"
    probe = tmp_path / "ap24-contract.js"
    probe.write_text(
        f"""
global.window = {{}};
require({SCRIPT.as_posix()!r});
const api = window.CaptivPortalHomeAp24Test;
if (!api) throw new Error("missing AP24 test API");
const start = Date.parse("2026-08-27T12:00:00.000Z");
const timeline = Array.from({{length:96}}, (_, index) => ({{
  from_utc:new Date(start + index*900000).toISOString(),to_utc:new Date(start + (index+1)*900000).toISOString(),
  ap_state:"operational",observation_quality:"operational",operational_seconds:900,
  unavailable_seconds:0,unknown_evidence_seconds:0,short_history_seconds:0,
  authoritative_state_sample_count:1,complete_observation_sample_count:1,diagnostic_partial_observation_sample_count:0
}}));
const item = {{ap_mac:"AA:BB:CC:DD:EE:01",current:{{status:"operational",freshness_status:"fresh"}},history:{{status:"degraded",coverage_status:"complete"}},observation_quality:{{status:"unknown"}},timeline}};
const counts = {{operational:1,degraded:0,unavailable:0,unknown:0}};
const summary = {{ap_count_in_window:1,current:counts,history:counts,observation_quality:counts,short_history_ap_count:0,status_gap_ap_count:0,observation_problem_ap_count:0}};
const sources = {{current_state:{{status:"operational"}},observations:{{status:"degraded"}}}};
const value = {{contract_version:"admin.home_ap_24h.v1",block_status:"degraded",window:{{kind:"rolling_24h",evaluated_at_utc:"2026-08-28T12:00:00.000Z",from_utc:"2026-08-27T12:00:00.000Z",to_utc:"2026-08-28T12:00:00.000Z",bucket_seconds:900,bucket_count:96}},summary,sources,items:[item],page:{{limit:20,next_cursor:null}}}};
const payload = {{api_version:"admin.read.v1",site_id:"{('0123456789abcdef01234567')}",result:value}};
if (!api.validResult(payload, "0123456789abcdef01234567")) throw new Error("valid payload rejected");
const malformed = JSON.parse(JSON.stringify(payload)); malformed.result.items[0].timeline.pop();
if (api.validResult(malformed, "0123456789abcdef01234567")) throw new Error("malformed timeline accepted");
const badDuration = JSON.parse(JSON.stringify(payload)); badDuration.result.items[0].timeline[0].operational_seconds = 899;
if (api.validResult(badDuration, "0123456789abcdef01234567")) throw new Error("malformed duration accepted");
const badSummary = JSON.parse(JSON.stringify(payload)); badSummary.result.summary.current.operational = 0;
if (api.validResult(badSummary, "0123456789abcdef01234567")) throw new Error("malformed summary accepted");
const badWindow = JSON.parse(JSON.stringify(payload)); badWindow.result.window.to_utc = "2026-08-28T11:00:00.000Z";
if (api.validResult(badWindow, "0123456789abcdef01234567")) throw new Error("malformed window accepted");
if (api.validResult(payload, "ffffffffffffffffffffffff")) throw new Error("cross-Site payload accepted");
if (api.retryDelay(1, 1) !== 1000) throw new Error("Retry-After ignored");
""",
        encoding="utf-8",
    )
    subprocess.run([node, str(probe)], cwd=ROOT, check=True, timeout=30)


def test_home_ap_24h_static_security_and_no_browser_semantics():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "CaptivPortalHomeAp24Coordinator" in source
    assert "innerHTML" not in source
    assert "localStorage" not in source
    assert "sessionStorage" not in source
    assert "classify_ap_status_code" not in source
    assert "/home/ap-24h" in source


def test_home_ap_24h_real_node_dom_fetch_and_failure_isolation(tmp_path):
    node = shutil.which("node")
    assert node is not None, "Node is mandatory for the AP-24H frontend gate"
    source = SCRIPT.read_text(encoding="utf-8")
    marker = 'window.CaptivPortalHomeAp24Test = Object.freeze'
    marker_at = source.index(marker)
    start_at = source.rfind("(function () {", 0, marker_at)
    end_at = source.index("\n(function () {", marker_at)
    controller_source = source[start_at:end_at]
    probe = tmp_path / "ap24-dom.js"
    probe.write_text(
        r'''
function assert(value, message) { if (!value) throw new Error(message); }
class Element {
  constructor(id) { this.id = id; this.dataset = {}; this.textContent = "";
    this.children = []; this.listeners = {}; this.hidden = false; }
  append(...values) { this.children.push(...values); }
  replaceChildren(...values) { this.children = [...values]; }
  addEventListener(name, callback) { (this.listeners[name] ||= []).push(callback); }
  dispatch(name) { return Promise.all((this.listeners[name] || []).map((callback) => callback())); }
}
const ids = ["admin-page", "refresh-button", "home-ap-24h-state", "home-ap-24h-status",
  "home-ap-24h-message", "home-ap-24h-items", "home-ap-24h-more",
  "home-ap-24h-summary", "home-ap-24h-window"];
const elements = Object.fromEntries(ids.map((id) => [id, new Element(id)]));
const site = "0123456789abcdef01234567";
elements["admin-page"].dataset = {page:"home",siteId:site,
  apiBase:`/admin/api/v1/sites/${site}`,homeLiveEnabled:"true",
  homeTrafficEnabled:"false",homeActivityEnabled:"false",homeHealthEnabled:"false",
  homeAp24hEnabled:"true",homeAp24hRefreshSeconds:"120",
  homeAp24hRequestTimeoutSeconds:"20"};
global.document = {hidden:false,getElementById:(id)=>elements[id] || null,
  createElement:(tag)=>new Element(tag),addEventListener:()=>{}};
let now = 1000; global.performance = {now:()=>now};
const windowListeners = {};
global.window = {setTimeout,clearTimeout,
  addEventListener(name, callback) { (windowListeners[name] ||= []).push(callback); }};
const calls=[]; const signals=[]; const queue=[];
global.fetch = (url, options) => { calls.push(url); signals.push(options.signal);
  const next=queue.shift(); if (!next) throw new Error("unexpected fetch"); return next; };
function response(status,payload,retryAfter=null) { return {ok:status>=200&&status<300,status,
  json:async()=>payload,headers:{get:(name)=>name==="Retry-After"?retryAfter:null}}; }
function payload(nextCursor=null,name="AP-A") {
  const start=Date.parse("2026-08-27T12:00:00.000Z");
  const timeline=Array.from({length:96},(_,index)=>({
    from_utc:new Date(start+index*900000).toISOString(),to_utc:new Date(start+(index+1)*900000).toISOString(),
    ap_state:"operational",ap_state_reason:"operational_evidence",observation_quality:"operational",
    observation_reason_codes:[],operational_seconds:900,unavailable_seconds:0,
    unknown_evidence_seconds:0,short_history_seconds:0,authoritative_state_sample_count:1,
    complete_observation_sample_count:1,diagnostic_partial_observation_sample_count:0}));
  const counts={operational:1,degraded:0,unavailable:0,unknown:0};
  return {api_version:"admin.read.v1",site_id:site,result:{contract_version:"admin.home_ap_24h.v1",
    window:{kind:"rolling_24h",evaluated_at_utc:"2026-08-28T12:00:00.000Z",
      from_utc:"2026-08-27T12:00:00.000Z",to_utc:"2026-08-28T12:00:00.000Z",bucket_seconds:900,bucket_count:96},
    block_status:"operational",block_reason:null,sources:{current_state:{status:"operational"},observations:{status:"operational"}},
    summary:{ap_count_in_window:1,current:counts,history:counts,observation_quality:counts,
      short_history_ap_count:0,status_gap_ap_count:0,observation_problem_ap_count:0},
    items:[{ap_mac:"AA:BB:CC:DD:EE:01",name,model:"EAP",identity_source:"current_state",
      current:{status:"operational",freshness_status:"fresh"},history:{status:"operational",coverage_status:"complete",unavailable_seconds:0},
      observation_quality:{status:"operational"},timeline}],page:{limit:20,next_cursor:nextCursor}}};
}
''' + controller_source + r'''
const controller=window.CaptivPortalHomeAp24Coordinator;
(async()=>{
  queue.push(Promise.resolve(response(200,payload("next"))));
  await controller.run(true);
  assert(calls.length===1 && elements["home-ap-24h-items"].children.length===1,"initial page renders");
  assert(!elements["home-ap-24h-more"].hidden,"pagination is exposed");
  queue.push(Promise.resolve(response(200,payload(null,"AP-B"))));
  await elements["home-ap-24h-more"].dispatch("click");
  assert(calls.length===2 && elements["home-ap-24h-items"].children.length===2,"page appends without replacing");

  let resolvePending; now += 200000;
  queue.push(new Promise((resolve)=>{resolvePending=resolve;}));
  const pending=controller.run(true); await new Promise((resolve)=>setImmediate(resolve));
  await controller.run(true); assert(calls.length===3,"active request blocks overlap");
  controller.abort("hidden"); assert(signals.at(-1).aborted,"hidden/page lifecycle aborts owner");
  resolvePending(response(200,payload(null,"late"))); await pending;

  now += 400000; queue.push(Promise.resolve(response(503,{error:{code:"query_deadline"}})));
  await controller.run(true);
  assert(elements["home-ap-24h-items"].children.length===2,"independent failure preserves last safe rows");
  now += 400000; queue.push(Promise.resolve(response(404,{error:{code:"not_found"}})));
  const before404=calls.length; await controller.run(true); await controller.run(true);
  assert(calls.length===before404+1,"feature 404 stops only AP24 polling");
  assert(elements["home-ap-24h-items"].children.length===0,"feature 404 clears AP24 current values");
  console.log("ap24 DOM contract passed");
})().catch((error)=>{console.error(error);process.exitCode=1;});
''',
        encoding="utf-8",
    )
    completed = subprocess.run(
        [node, str(probe)], capture_output=True, text=True, timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "ap24 DOM contract passed" in completed.stdout
