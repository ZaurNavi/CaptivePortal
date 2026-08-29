from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).parents[2]
SOURCE = ROOT / "app" / "admin_web" / "static" / "admin.js"


def _node() -> str:
    value = shutil.which("node")
    if value:
        return value
    bundled = Path(os.environ.get("LOCALAPPDATA", "")) / "Codex" / "dependencies" / "node" / "bin" / "node.exe"
    assert bundled.exists(), "Node is mandatory for the Traffic foundation frontend gate"
    return str(bundled)


def test_traffic_foundation_javascript_syntax():
    completed = subprocess.run(
        [_node(), "--check", str(SOURCE)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_traffic_coordinator_real_node_dom_fetch_and_lifecycle(tmp_path):
    probe = tmp_path / "traffic-foundation-probe.js"
    probe.write_text(
        r'''
const assert = (value, message) => { if (!value) throw new Error(message); };
const settle = () => new Promise((resolve) => setImmediate(resolve));
class Element {
  constructor(id) { this.id=id; this.dataset={}; this.hidden=false; this.disabled=false; this.textContent=""; this.listeners={}; }
  addEventListener(kind, callback) { (this.listeners[kind] ||= []).push(callback); }
  dispatch(kind) { (this.listeners[kind] || []).forEach((callback) => callback({preventDefault(){}})); }
  replaceChildren() { this.children=[]; }
}
const ids=["admin-page","refresh-button","traffic-global-state","traffic-global-state-title","traffic-global-state-message","traffic-empty-state","traffic-panels"];
const elements=Object.fromEntries(ids.map((id)=>[id,new Element(id)]));
const panelSentinel={id:"future-traffic-panel"};
elements["traffic-panels"].children=[panelSentinel];
elements["admin-page"].dataset={page:"traffic",siteId:"0123456789abcdef01234567",apiBase:"/admin/api/v1/sites/0123456789abcdef01234567",trafficEnabled:"true",trafficRefreshSeconds:"60",trafficRequestTimeoutSeconds:"20"};
const documentListeners={}; const windowListeners={}; let hidden=false;
global.document={get hidden(){return hidden;},set hidden(value){hidden=value;},getElementById:(id)=>elements[id]||null,addEventListener:(kind,callback)=>{(documentListeners[kind] ||= []).push(callback);}};
let timerId=0; const timers=new Map();
global.window={location:{origin:"https://localhost",pathname:"/admin/sites/0123456789abcdef01234567/traffic",search:""},
  setTimeout:(callback,delay)=>{const id=++timerId;timers.set(id,{callback,delay});return id;},clearTimeout:(id)=>timers.delete(id),
  addEventListener:(kind,callback)=>{(windowListeners[kind] ||= []).push(callback);}};
global.performance={now:()=>1000};
let fetchPlan=[]; let fetchCalls=[];
global.fetch=async(url,options)=>{fetchCalls.push({url,options}); const item=fetchPlan.shift() || {status:200,payload:{result:{ok:true}}};
  if(item.hang)return new Promise((_resolve,reject)=>options.signal.addEventListener("abort",()=>reject(new Error("aborted")),{once:true}));
  return {ok:item.status>=200&&item.status<300,status:item.status,headers:{get:(name)=>name==="Retry-After"?(item.retryAfter||null):null},json:async()=>item.payload};};
require(process.argv[2]);
const coordinator=window.CaptivPortalTrafficCoordinator;
assert(coordinator && Object.isFrozen(coordinator),"frozen coordinator exposed");
assert(Object.keys(coordinator).sort().join(",")==="refreshAll,refreshPanel,registerPanel","public API is narrow");
assert(elements["traffic-empty-state"].hidden===false,"zero-panel empty state visible");
assert(elements["refresh-button"].disabled===true,"zero-panel refresh disabled");
assert(fetchCalls.length===0 && timers.size===0,"zero panels produce no fetch or timer");
assert(elements["traffic-panels"].children.length===1&&elements["traffic-panels"].children[0]===panelSentinel,"coordinator preserves pre-rendered panel markup");
assert((elements["refresh-button"].listeners.click||[]).length===1,"Traffic page has exactly one Refresh owner");
assert(window.CaptivPortalAdminTest.classifyHttp(401,{},null).kind==="session","generic classifier unchanged");

let invalidRejected=false;try{coordinator.registerPanel({key:"bad",autoRefresh:false,load:null,render(){}});}catch(_error){invalidRejected=true;}
assert(invalidRejected,"invalid registration rejected");
let firstLoads=0;let firstRenders=0;
coordinator.registerPanel({key:"manual",autoRefresh:false,load:async()=>{firstLoads+=1;return "one";},render:(value)=>{assert(value==="one","render value");firstRenders+=1;}});
Promise.resolve().then(async()=>{
  await settle();
  assert(firstLoads===1&&firstRenders===1,"manual-only panel receives initial load");
  assert(elements["traffic-empty-state"].hidden===true&&elements["refresh-button"].disabled===false,"first registration activates shell");
  assert(timers.size===0,"manual-only panel schedules no periodic timer");
  let duplicate=false;try{coordinator.registerPanel({key:"manual",autoRefresh:false,load:async()=>1,render(){}});}catch(_error){duplicate=true;}
  assert(duplicate,"duplicate key rejected");

  let otherLoads=0;
  coordinator.registerPanel({key:"other",autoRefresh:false,load:async()=>{otherLoads+=1;return 2;},render(){}});
  await settle();
  const beforeOther=otherLoads;
  await coordinator.refreshPanel("manual",{manual:true});
  assert(firstLoads===2&&otherLoads===beforeOther,"refreshPanel isolates selected panel");
  assert(await coordinator.refreshPanel("missing",{manual:true})===false,"unknown panel is safe no-op");
  await coordinator.refreshAll({manual:true});
  assert(firstLoads===3&&otherLoads===beforeOther+1,"refreshAll runs all eligible panels");

  let periodicLoads=0;
  coordinator.registerPanel({key:"periodic",autoRefresh:true,load:async()=>{periodicLoads+=1;return "periodic";},render(){}});
  await settle();
  assert(periodicLoads===1&&Array.from(timers.values()).some((timer)=>timer.delay===60000),"auto panel receives initial load then periodic timer");

  let networkRenders=0;fetchPlan.push({status:200,payload:{result:{value:7}}});
  coordinator.registerPanel({key:"network",autoRefresh:false,load:({requestJson,apiBase})=>requestJson(`${apiBase}/traffic/example`),render:()=>{networkRenders+=1;}});
  await settle();
  assert(networkRenders===1,"same-origin Site API request accepted");
  assert(fetchCalls.at(-1).url==="/admin/api/v1/sites/0123456789abcdef01234567/traffic/example","bounded Traffic namespace");
  assert(fetchCalls.at(-1).options.credentials==="same-origin"&&fetchCalls.at(-1).options.cache==="no-store","safe fetch contract");

  let rejectedKind=null;
  coordinator.registerPanel({key:"external",autoRefresh:false,load:({requestJson})=>requestJson("https://evil.example/data"),render(){},renderFailure:(failure)=>{rejectedKind=failure.kind;}});
  await settle();
  assert(rejectedKind==="invalid"&&fetchCalls.every((call)=>!call.url.includes("evil")),"external URL rejected before fetch");

  let busyCalls=0;fetchPlan.push({status:429,retryAfter:"120",payload:{error:{code:"query_busy"}}});
  coordinator.registerPanel({key:"busy",autoRefresh:true,load:({requestJson,apiBase})=>{busyCalls+=1;return requestJson(`${apiBase}/traffic/busy`);},render(){},renderFailure(){}});
  await settle();
  assert(busyCalls===1,"busy panel attempted once");
  await coordinator.refreshPanel("busy",{manual:true});
  assert(busyCalls===1,"manual cannot bypass Retry-After");

  let timeoutKind=null;fetchPlan.push({status:503,payload:{error:{code:"query_deadline"}}});
  coordinator.registerPanel({key:"timeout",autoRefresh:false,load:({requestJson,apiBase})=>requestJson(`${apiBase}/traffic/timeout`),render(){},renderFailure:(failure)=>{timeoutKind=failure.kind;}});
  let malformedKind=null;fetchPlan.push({status:200,payload:{wrong:true}});
  coordinator.registerPanel({key:"malformed",autoRefresh:false,load:({requestJson,apiBase})=>requestJson(`${apiBase}/traffic/malformed`),render(){},renderFailure:(failure)=>{malformedKind=failure.kind;}});
  await settle();
  assert(timeoutKind==="timeout"&&malformedKind==="unexpected","deadline and malformed envelopes are isolated classifications");

  let healthy=0;let failed=0;
  coordinator.registerPanel({key:"failed",autoRefresh:false,load:async()=>{throw {trafficFailure:{kind:"unavailable",status:503,code:"source_unavailable",retryAfter:0}};},render(){},renderFailure:()=>{failed+=1;}});
  coordinator.registerPanel({key:"healthy",autoRefresh:false,load:async()=>"ok",render:()=>{healthy+=1;}});
  await settle();
  assert(failed===1&&healthy===1,"panel-local failure isolation");

  let oldResolve;let raceRenders=[];let raceLoads=0;
  coordinator.registerPanel({key:"race",autoRefresh:false,load:()=>{raceLoads+=1;if(raceLoads===1)return new Promise((resolve)=>{oldResolve=resolve;});return Promise.resolve("new");},render:(value)=>raceRenders.push(value)});
  await settle();
  const replacement=coordinator.refreshPanel("race",{manual:true});
  await replacement;oldResolve("old");await settle();
  assert(raceRenders.join(",")==="new","superseded generation cannot overwrite newer render");

  let abortSignal;let lifecycleRenders=0;coordinator.registerPanel({key:"lifecycle",autoRefresh:false,load:({requestJson,apiBase})=>{if(!abortSignal)fetchPlan.push({hang:true});const pending=requestJson(`${apiBase}/traffic/lifecycle`);abortSignal=fetchCalls.at(-1).options.signal;return pending;},render(){lifecycleRenders+=1;}});
  await settle();
  document.hidden=true;(documentListeners.visibilitychange||[]).forEach((callback)=>callback());
  assert(abortSignal.aborted&&abortSignal.reason==="hidden","hidden aborts active request neutrally");
  document.hidden=false;(documentListeners.visibilitychange||[]).forEach((callback)=>callback());
  await settle();
  assert(lifecycleRenders===1,"visible resumes a neutrally aborted initial load even for manual-only panel");
  let forbiddenFailures=0;fetchPlan.push({status:403,payload:{error:{code:"site_forbidden"}}});
  coordinator.registerPanel({key:"forbidden",autoRefresh:false,load:({requestJson,apiBase})=>requestJson(`${apiBase}/traffic/forbidden`),render(){},renderFailure:()=>{forbiddenFailures+=1;}});
  await settle();
  const callsAfterForbidden=fetchCalls.length;
  await coordinator.refreshAll({manual:true});
  assert(elements["traffic-global-state"].hidden===false&&elements["refresh-button"].disabled===true,"403 promotes global pause");
  assert(fetchCalls.length===callsAfterForbidden&&forbiddenFailures===0,"global pause stops later work without panel failure");
  (windowListeners.pagehide||[]).forEach((callback)=>callback());
  assert(elements["refresh-button"].disabled===true,"pagehide terminally stops coordinator");
  console.log("TRAFFIC_COORDINATOR_OK");
}).catch((error)=>{console.error(error);process.exitCode=1;});
''',
        encoding="utf-8",
    )
    completed = subprocess.run(
        [_node(), str(probe), str(SOURCE)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={**os.environ, "NODE_NO_WARNINGS": "1"},
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "TRAFFIC_COORDINATOR_OK" in completed.stdout


def test_traffic_frontend_keeps_product_semantics_out_of_foundation():
    source = SOURCE.read_text(encoding="utf-8")
    traffic = source.split("window.CaptivPortalTrafficCoordinator", 1)[0].rsplit("(function ()", 1)[-1]
    assert "current-traffic" not in traffic
    assert "Omada" not in traffic
    assert "Mbps" not in traffic
    assert "localStorage" not in traffic
    assert "sessionStorage" not in traffic
    assert 'if (context.page === "traffic") return;' in source
