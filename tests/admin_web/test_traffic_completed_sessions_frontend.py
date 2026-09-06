from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ADMIN_JS = ROOT / "app" / "admin_web" / "static" / "admin.js"
TRAFFIC_TEMPLATE = ROOT / "app" / "admin_web" / "templates" / "admin" / "traffic.html"
BASE_TEMPLATE = ROOT / "app" / "admin_web" / "templates" / "admin" / "base.html"


def _block(source: str, name: str) -> str:
    start = f"/* {name}_START */"
    end = f"/* {name}_END */"
    assert source.count(start) == source.count(end) == 1
    return source.split(start, 1)[1].split(end, 1)[0]


def test_template_contract_places_completed_sessions_between_online_and_history():
    template = TRAFFIC_TEMPLATE.read_text(encoding="utf-8")
    base = BASE_TEMPLATE.read_text(encoding="utf-8")
    assert "data-traffic-completed-sessions-enabled" in base
    assert template.index('id="traffic-online-guests-panel"') < template.index(
        'id="traffic-completed-sessions-panel"'
    ) < template.index('id="traffic-history-panel"')
    for heading in (
        "Guest", "Session Start", "Session End", "Duration", "SSID",
        "Download", "Upload", "Total", "Evidence",
    ):
        assert f">{heading}<" in template


def test_completed_sessions_real_node_dom_fetch_cursor_and_security_contract():
    source = ADMIN_JS.read_text(encoding="utf-8")
    panel = _block(source, "TRAFFIC_COMPLETED_SESSIONS_PANEL")
    assert "const TRAFFIC_COMPLETED_SESSIONS_UTC" in panel
    assert "const UTC =" not in panel
    script = r'''
"use strict";
class Element {
  constructor(id="") { this.id=id; this.dataset={}; this.children=[]; this.hidden=false; this.disabled=false; this.textContent=""; this.listeners={}; this.attrs={}; }
  addEventListener(name, callback) { this.listeners[name]=callback; }
  click() { if(this.listeners.click)this.listeners.click(); }
  setAttribute(name, value) { this.attrs[name]=String(value); }
  appendChild(value) { this.children.push(value); return value; }
  replaceChildren(...values) { this.children=values; }
}
const ids=new Map();
function element(id){if(!ids.has(id))ids.set(id,new Element(id));return ids.get(id);}
const root=element("admin-page");
root.dataset={page:"traffic",trafficEnabled:"true",trafficCompletedSessionsEnabled:"true"};
const document={getElementById:element,createElement:()=>new Element()};
const refreshes=[];let spec=null;
const coordinator={
 registerPanel(value){spec=value;return true;},
 refreshPanel(key,options){refreshes.push([key,options]);return Promise.resolve(true);}
};
const window={CaptivPortalTrafficCoordinator:coordinator};
global.window=window;global.document=document;global.Intl=Intl;global.Date=Date;
eval(PANEL);
if(!spec||spec.historicalLane!==true||spec.historicalLaneGuard!==true||spec.autoRefresh!==false)throw new Error("historical lane registration");
const item={visit_id:"11111111-1111-4111-8111-111111111111",client_mac:"AA:BB:CC:DD:EE:01",started_at:"2026-09-05T09:55:00.000Z",closed_at:"2026-09-05T10:00:00.000Z",duration_seconds:300,start_ssid:"A",final_ssid:"B",start_ap_mac:null,final_ap_mac:null,observed_download_bytes:0,observed_upload_bytes:null,observed_total_bytes:null,download_evidence_status:"complete",upload_evidence_status:"insufficient_data",traffic_evidence_status:"partial",evidence_reason_codes:["counter_missing"],sample_count:2,accepted_download_interval_count:1,accepted_upload_interval_count:0,first_observed_at:"2026-09-05T09:55:30.000Z",last_observed_at:"2026-09-05T09:59:30.000Z"};
function payload(range="24h",cursor="opaque",items=[item]){const to="2026-09-05T10:05:00.000Z",from=range==="24h"?"2026-09-04T10:05:00.000Z":"2026-08-29T10:05:00.000Z";return {api_version:"admin.read.v1",site_id:"aaaaaaaaaaaaaaaaaaaaaaaa",page:null,result:{metric_version:"network_traffic_completed_guest_session_observed_bytes.v1",session_method:"closed_visit_completion_cohort.v1",attribution_method:"visit_window_observation_counter_interval_sum.v1",continuity_method:"observation_uptime_progress.v1",unit:"bytes",site_id:"aaaaaaaaaaaaaaaaaaaaaaaa",range:{id:range,from_utc:from,to_utc:to,evaluated_at_utc:to},status:"partial",source_health:{visits:"healthy",observations:"healthy"},page:{limit:100,returned_count:items.length,next_cursor:cursor,sort:"closed_at_desc_visit_id_desc.v1"},items}};}
let requested=[];
const context={siteId:"aaaaaaaaaaaaaaaaaaaaaaaa",apiBase:"/admin/api/v1/sites/aaaaaaaaaaaaaaaaaaaaaaaa",requestJson:async(url)=>{requested.push(url);return payload(url.includes("range=7d")?"7d":"24h");}};
(async()=>{
 const first=await spec.load(context);spec.render(first);
 if(!requested[0].includes("limit=100"))throw new Error("canonical page limit");
 const rows=element("traffic-completed-sessions-items").children;
 if(rows.length!==1)throw new Error("row render");
 if(rows[0].children[4].textContent!=="A → B")throw new Error("SSID transition");
 if(rows[0].children[5].textContent!=="0 B")throw new Error("zero bytes");
 if(rows[0].children[6].textContent!=="—")throw new Error("null bytes");
 if(rows[0].children[8].textContent!=="Partial evidence")throw new Error("evidence wording");
 element("traffic-completed-sessions-more").click();
 if(refreshes.length!==1)throw new Error("load more scheduling");
 element("traffic-completed-sessions-range-7d").click();
 if(refreshes.length!==2)throw new Error("independent range scheduling");
 const second=await spec.load(context);spec.render(second);
 if(!requested[1].includes("range=7d")||requested[1].includes("cursor="))throw new Error("new root chain");
 spec.renderGlobalFailure({kind:"forbidden"});
 if(element("traffic-completed-sessions-items").children.length!==0)throw new Error("security clear rows");
 if(!element("traffic-completed-sessions-more").hidden)throw new Error("security clear cursor");
 console.log("PASS");
})().catch((error)=>{console.error(error);process.exit(1);});
'''.replace("PANEL", json.dumps(panel))
    result = subprocess.run(
        ["node", "-e", script], cwd=ROOT, text=True,
        capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "PASS"


def test_completed_sessions_and_history_share_one_three_second_historical_lane():
    source = ADMIN_JS.read_text(encoding="utf-8")
    history = _block(source, "TRAFFIC_HISTORY_PANEL")
    completed = _block(source, "TRAFFIC_COMPLETED_SESSIONS_PANEL")
    assert "candidate.spec.historicalLane === true" in source
    assert "state.spec.historicalLaneGuard === true && dispatches.length" in source
    assert "state.historicalLaneOwnerGeneration === generation" in source
    assert history.count("historicalLane: true") == 2
    assert history.count("historicalLaneGuard: false") == 2
    assert completed.count("historicalLane: true") == 1
    assert completed.count("historicalLaneGuard: true") == 1
    assert "/traffic/completed-sessions?" in completed
    assert 'PRODUCT_ORDER = Object.freeze(["history", "statistics", "peak", "aps", "apshare"])' in history
    assert "completed" not in history.split("PRODUCT_ORDER", 1)[1].split(");", 1)[0]


def test_historical_lane_admits_only_one_noncoalescible_job_after_guard():
    script = r'''
"use strict";
const assert=(value,message)=>{if(!value)throw new Error(message);};
const settle=()=>new Promise((resolve)=>setImmediate(resolve));
class Element {
  constructor(){this.dataset={};this.hidden=false;this.disabled=false;this.listeners={};}
  addEventListener(name,callback){(this.listeners[name]||=[]).push(callback);}
}
const elements=new Map(["admin-page","refresh-button","traffic-global-state",
  "traffic-global-state-title","traffic-global-state-message","traffic-empty-state",
  "traffic-panels"].map((id)=>[id,new Element()]));
elements.get("admin-page").dataset={page:"traffic",trafficEnabled:"true",
  siteId:"aaaaaaaaaaaaaaaaaaaaaaaa",apiBase:"/admin/api/v1/sites/aaaaaaaaaaaaaaaaaaaaaaaa",
  trafficRefreshSeconds:"60",trafficRequestTimeoutSeconds:"30"};
const listeners={};let clock=0;let timerId=0;const timers=new Map();
global.performance={now:()=>clock};
global.document={hidden:false,getElementById:(id)=>elements.get(id)||null,
  addEventListener:(name,callback)=>{(listeners[name]||=[]).push(callback);}};
global.window={location:{origin:"https://localhost"},
  addEventListener(){},
  setTimeout:(callback,delay)=>{const id=++timerId;timers.set(id,{callback,at:clock+delay});return id;},
  clearTimeout:(id)=>timers.delete(id)};
global.fetch=()=>{throw new Error("unexpected fetch");};
require(SOURCE);
const coordinator=window.CaptivPortalTrafficCoordinator;
let releaseFirst;const firstHold=new Promise((resolve)=>{releaseFirst=resolve;});
let active=0;let maximum=0;let first=0;let second=0;
coordinator.registerPanel({key:"history-lane-proof",autoRefresh:false,historicalLane:true,historicalLaneGuard:false,
  load:async()=>{first+=1;active+=1;maximum=Math.max(maximum,active);await firstHold;active-=1;return 1;},
  render(){}});
coordinator.registerPanel({key:"completed-lane-proof",autoRefresh:false,historicalLane:true,historicalLaneGuard:true,
  load:async()=>{second+=1;active+=1;maximum=Math.max(maximum,active);active-=1;return 2;},
  render(){}});
async function runDue(){
  const due=[...timers.entries()].filter(([,timer])=>timer.at<=clock);
  due.forEach(([id,timer])=>{timers.delete(id);timer.callback();});
  await settle();await settle();
}
(async()=>{
  await settle();await settle();
  assert(first===1&&second===0&&active===1,"second historical job waits");
  releaseFirst();await settle();await settle();
  clock=2999;await runDue();
  assert(second===0,"three-second admission guard is not bypassed");
  clock=3000;await runDue();
  assert(second===1&&maximum===1,"one queued job dispatches with no overlap");
  console.log("PASS");
})().catch((error)=>{console.error(error);process.exit(1);});
'''.replace("SOURCE", json.dumps(str(ADMIN_JS)))
    result = subprocess.run(
        ["node", "-e", script], cwd=ROOT, text=True,
        capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "PASS"


def test_completed_historical_lane_same_panel_supersede_waits_for_settlement_and_guard():
    script = r'''
"use strict";
const assert=(value,message)=>{if(!value)throw new Error(message);};
const settle=()=>new Promise((resolve)=>setImmediate(resolve));
class Element {
  constructor(){this.dataset={};this.hidden=false;this.disabled=false;this.listeners={};}
  addEventListener(name,callback){(this.listeners[name]||=[]).push(callback);}
}
const elements=new Map(["admin-page","refresh-button","traffic-global-state",
  "traffic-global-state-title","traffic-global-state-message","traffic-empty-state",
  "traffic-panels"].map((id)=>[id,new Element()]));
elements.get("admin-page").dataset={page:"traffic",trafficEnabled:"true",
  siteId:"aaaaaaaaaaaaaaaaaaaaaaaa",apiBase:"/admin/api/v1/sites/aaaaaaaaaaaaaaaaaaaaaaaa",
  trafficRefreshSeconds:"60",trafficRequestTimeoutSeconds:"30"};
let clock=0;let timerId=0;const timers=new Map();
global.performance={now:()=>clock};
global.document={hidden:false,getElementById:(id)=>elements.get(id)||null,addEventListener(){}};
global.window={location:{origin:"https://localhost"},addEventListener(){},
  setTimeout:(callback,delay)=>{const id=++timerId;timers.set(id,{callback,at:clock+delay});return id;},
  clearTimeout:(id)=>timers.delete(id)};
let active=0;let maximum=0;const paths=[];
global.fetch=(url,options)=>new Promise((_resolve,reject)=>{
  paths.push(url);active+=1;maximum=Math.max(maximum,active);
  options.signal.addEventListener("abort",()=>{active-=1;reject(new Error("aborted"));},{once:true});
});
require(SOURCE);
const coordinator=window.CaptivPortalTrafficCoordinator;
let aLoads=0;let bLoads=0;
coordinator.registerPanel({key:"historical-a",autoRefresh:false,historicalLane:true,historicalLaneGuard:true,
  load:({requestJson,apiBase})=>{aLoads+=1;return requestJson(`${apiBase}/traffic/a`);},render(){}});
coordinator.registerPanel({key:"historical-b",autoRefresh:false,historicalLane:true,historicalLaneGuard:true,
  load:({requestJson,apiBase})=>{bLoads+=1;return requestJson(`${apiBase}/traffic/b`);},render(){}});
async function runDue(){
  const due=[...timers.entries()].filter(([,timer])=>timer.at<=clock);
  due.forEach(([id,timer])=>{timers.delete(id);timer.callback();});
  await settle();await settle();
}
(async()=>{
  await settle();await settle();
  assert(aLoads===1&&bLoads===0&&active===1,"A owns the initial historical lane");
  const superseded=coordinator.refreshPanel("historical-a",{manual:true});
  assert(aLoads===1&&paths.length===1,"same-panel replacement does not overlap old execution");
  await superseded;await settle();await settle();
  assert(active===0&&aLoads===1&&bLoads===0,"old execution settles before replacement admission");
  clock=2999;await runDue();
  assert(aLoads===1&&bLoads===0,"replacement cannot bypass the shared guard");
  clock=3000;await runDue();
  assert(aLoads===2&&bLoads===0&&active===1,"A replacement owns the lane after the guard");
  await settle();await settle();
  assert(bLoads===0&&active===1,"old generation release cannot admit B beside replacement A");
  assert(maximum===1,"historical HTTP in-flight remains one");
  assert(paths.join(",").endsWith("/traffic/a,/admin/api/v1/sites/aaaaaaaaaaaaaaaaaaaaaaaa/traffic/a"),
    "only A generations dispatched");
  console.log("PASS");
})().catch((error)=>{console.error(error);process.exit(1);});
'''.replace("SOURCE", json.dumps(str(ADMIN_JS)))
    result = subprocess.run(
        ["node", "-e", script], cwd=ROOT, text=True,
        capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "PASS"


def test_history_historical_lane_same_panel_supersede_preserves_legacy_admission():
    script = r'''
"use strict";
const assert=(value,message)=>{if(!value)throw new Error(message);};
const settle=()=>new Promise((resolve)=>setImmediate(resolve));
class Element {
  constructor(){this.dataset={};this.hidden=false;this.disabled=false;this.listeners={};}
  addEventListener(name,callback){(this.listeners[name]||=[]).push(callback);}
}
const elements=new Map(["admin-page","refresh-button","traffic-global-state",
  "traffic-global-state-title","traffic-global-state-message","traffic-empty-state",
  "traffic-panels"].map((id)=>[id,new Element()]));
elements.get("admin-page").dataset={page:"traffic",trafficEnabled:"true",
  siteId:"aaaaaaaaaaaaaaaaaaaaaaaa",apiBase:"/admin/api/v1/sites/aaaaaaaaaaaaaaaaaaaaaaaa",
  trafficRefreshSeconds:"60",trafficRequestTimeoutSeconds:"30"};
let clock=0;let timerId=0;const timers=new Map();
global.performance={now:()=>clock};
global.document={hidden:false,getElementById:(id)=>elements.get(id)||null,addEventListener(){}};
global.window={location:{origin:"https://localhost"},addEventListener(){},
  setTimeout:(callback,delay)=>{const id=++timerId;timers.set(id,{callback,at:clock+delay});return id;},
  clearTimeout:(id)=>timers.delete(id)};
const requests=[];
global.fetch=(url,options)=>new Promise((resolve)=>requests.push({url,options,resolve}));
require(SOURCE);
const coordinator=window.CaptivPortalTrafficCoordinator;
const rendered=[];let loads=0;
coordinator.registerPanel({key:"history-legacy",autoRefresh:false,historicalLane:true,historicalLaneGuard:false,
  load:({requestJson,apiBase})=>{loads+=1;return requestJson(`${apiBase}/traffic/history-proof`);},
  render:(value)=>rendered.push(value.result.label)});
const response=(label)=>({ok:true,status:200,headers:{get:()=>null},json:async()=>({result:{label}})});
(async()=>{
  await settle();await settle();
  assert(loads===1&&requests.length===1,"initial History request starts");
  const superseded=coordinator.refreshPanel("history-legacy",{manual:true});
  assert(requests[0].options.signal.aborted,"old History generation is aborted");
  assert(loads===1,"replacement waits for old execution settlement");
  requests[0].resolve(response("stale"));
  await superseded;await settle();await settle();
  assert(rendered.length===0,"stale History response cannot render");
  assert(clock===0&&loads===2&&requests.length===2,
    "replacement History dispatches without a coordinator scheduler hop");
  requests[1].resolve(response("current"));
  await settle();await settle();
  assert(rendered.length===1&&rendered[0]==="current","only replacement generation renders");
  console.log("PASS");
})().catch((error)=>{console.error(error);process.exit(1);});
'''.replace("SOURCE", json.dumps(str(ADMIN_JS)))
    result = subprocess.run(
        ["node", "-e", script], cwd=ROOT, text=True,
        capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "PASS"


def test_completed_owner_blocks_history_without_cross_panel_overlap():
    script = r'''
"use strict";
const assert=(value,message)=>{if(!value)throw new Error(message);};
const settle=()=>new Promise((resolve)=>setImmediate(resolve));
class Element {
  constructor(){this.dataset={};this.hidden=false;this.disabled=false;this.listeners={};}
  addEventListener(name,callback){(this.listeners[name]||=[]).push(callback);}
}
const elements=new Map(["admin-page","refresh-button","traffic-global-state",
  "traffic-global-state-title","traffic-global-state-message","traffic-empty-state",
  "traffic-panels"].map((id)=>[id,new Element()]));
elements.get("admin-page").dataset={page:"traffic",trafficEnabled:"true",
  siteId:"aaaaaaaaaaaaaaaaaaaaaaaa",apiBase:"/admin/api/v1/sites/aaaaaaaaaaaaaaaaaaaaaaaa",
  trafficRefreshSeconds:"60",trafficRequestTimeoutSeconds:"30"};
let clock=0;let timerId=0;const timers=new Map();
global.performance={now:()=>clock};
global.document={hidden:false,getElementById:(id)=>elements.get(id)||null,addEventListener(){}};
global.window={location:{origin:"https://localhost"},addEventListener(){},
  setTimeout:(callback,delay)=>{const id=++timerId;timers.set(id,{callback,at:clock+delay});return id;},
  clearTimeout:(id)=>timers.delete(id)};
global.fetch=()=>{throw new Error("unexpected fetch");};
require(SOURCE);
const coordinator=window.CaptivPortalTrafficCoordinator;
let releaseCompleted;const hold=new Promise((resolve)=>{releaseCompleted=resolve;});
let completed=0;let history=0;let active=0;let maximum=0;
coordinator.registerPanel({key:"completed-owner",autoRefresh:false,historicalLane:true,historicalLaneGuard:true,
  load:async()=>{completed+=1;active+=1;maximum=Math.max(maximum,active);await hold;active-=1;return 1;},render(){}});
coordinator.registerPanel({key:"history-waiter",autoRefresh:false,historicalLane:true,historicalLaneGuard:false,
  load:async()=>{history+=1;active+=1;maximum=Math.max(maximum,active);active-=1;return 2;},render(){}});
(async()=>{
  await settle();await settle();
  assert(completed===1&&history===0&&active===1,"Completed owner blocks History");
  releaseCompleted();await settle();await settle();
  assert(history===1&&maximum===1,
    "History resumes immediately after settlement without overlap or a scheduler hop");
  console.log("PASS");
})().catch((error)=>{console.error(error);process.exit(1);});
'''.replace("SOURCE", json.dumps(str(ADMIN_JS)))
    result = subprocess.run(
        ["node", "-e", script], cwd=ROOT, text=True,
        capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "PASS"
