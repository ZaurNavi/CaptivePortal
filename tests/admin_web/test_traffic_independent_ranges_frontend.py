from __future__ import annotations

from .test_traffic_history_frontend import (
    ROOT,
    _foundation_source,
    _panel_source,
    _run_node,
)


def test_independent_range_broker_guard_priority_and_coalescing(tmp_path):
    harness = r'''
const assert=(value,message)=>{if(!value)throw new Error(message);};
class Element {
  constructor(id){this.id=id;this.dataset={};this.textContent="";this.attributes={};this.children=[];this.listeners={};this.namespaceURI=id==="traffic-history-chart-svg"?"http://www.w3.org/2000/svg":null;}
  setAttribute(key,value){this.attributes[key]=String(value);}
  addEventListener(kind,callback){(this.listeners[kind]??=[]).push(callback);}
  replaceChildren(...children){this.children=children;}
  click(){for(const callback of this.listeners.click||[])callback({preventDefault(){}});}
}
const elements={};
function element(id){
  if(!elements[id]) elements[id]=new Element(id);
  return elements[id];
}
const root=element("admin-page");
root.dataset={page:"traffic",trafficEnabled:"true",trafficIndependentRangesEnabled:"true"};
element("traffic-history-panel").dataset.historyEnabled="true";
element("traffic-statistics-panel").dataset.statisticsEnabled="true";
element("traffic-peak-panel").dataset.peakEnabled="true";
element("traffic-ap-panel").dataset.apEnabled="true";
global.document={getElementById:element,createElementNS:(_namespace,name)=>new Element(name)};
let now=1000;global.performance={now:()=>now};
let registered=null;const queued=[];
global.window={CaptivPortalTrafficCoordinator:{
  registerPanel:(spec)=>{registered=spec;return true;},
  refreshPanel:()=>Promise.resolve(false),
  queuePanel:(key,options)=>{queued.push({key,options});return true;},
}};
'''
    assertions = r'''
(async()=>{
  assert(registered&&registered.key==="network-traffic-history","one broker lane registered");
  assert(registered.autoRefresh===false,"broker does not own a scheduler");
  let urls=[];
  const neutral={trafficNeutral:true};
  const context={siteId:"0123456789abcdef01234567",apiBase:"/admin/api/v1/sites/0123456789abcdef01234567",requestJson:async(url)=>{urls.push(url);throw neutral;}};
  try{await registered.load(context);}catch(error){assert(error===neutral,"initial neutral abort preserved");}
  assert(urls[0].endsWith("range=24h&products=history%2Cstatistics%2Cpeak%2Caps"),"initial all-24h is one combined request");
  assert(queued.at(-1).options.notBefore===11000,"guard starts at actual dispatch");

  element("traffic-history-range-7d").click();
  assert(element("traffic-history-state-title").textContent.includes("waiting"),"waiting is distinct from loading");
  assert(queued.at(-1).options.notBefore===11000,"explicit selection cannot bypass guard");
  registered.prepareRefresh();
  now=11000;
  try{await registered.load(context);}catch(error){assert(error===neutral,"explicit neutral abort preserved");}
  assert(urls[1].endsWith("range=7d&products=history"),"explicit intent outranks global refresh");

  element("traffic-statistics-range-7d").click();
  now=21000;
  try{await registered.load(context);}catch(error){assert(error===neutral,"coalesced neutral abort preserved");}
  assert(urls[2].endsWith("range=7d&products=history%2Cstatistics"),"same-range pending products coalesce canonically");

  element("traffic-history-range-24h").click();
  element("traffic-history-range-7d").click();
  now=31000;
  try{await registered.load(context);}catch(error){assert(error===neutral,"latest neutral abort preserved");}
  assert(urls[3].endsWith("range=7d&products=history%2Cstatistics"),"latest pending range wins without stale intent");
  assert(urls.length===4,"broker dispatches one HTTP request per admitted batch");
  console.log("TRAFFIC_INDEPENDENT_RANGE_BROKER_OK");
})().catch((error)=>{console.error(error);process.exitCode=1;});
'''
    output = _run_node(tmp_path, harness + _panel_source() + assertions)
    assert "TRAFFIC_INDEPENDENT_RANGE_BROKER_OK" in output


def test_hidden_initial_abort_cannot_bypass_historical_admission_guard(tmp_path):
    harness = r'''
const assert=(value,message)=>{if(!value)throw new Error(message);};
const settle=()=>new Promise((resolve)=>setImmediate(resolve));
class Element {
  constructor(id){this.id=id;this.dataset={};this.textContent="";this.hidden=false;this.disabled=false;this.attributes={};this.children=[];this.listeners={};this.namespaceURI=id==="traffic-history-chart-svg"?"http://www.w3.org/2000/svg":null;}
  setAttribute(key,value){this.attributes[key]=String(value);}
  addEventListener(kind,callback){(this.listeners[kind]??=[]).push(callback);}
  replaceChildren(...children){this.children=children;}
}
const elements={};
function element(id){if(!elements[id])elements[id]=new Element(id);return elements[id];}
const site="0123456789abcdef01234567";
element("admin-page").dataset={page:"traffic",siteId:site,apiBase:`/admin/api/v1/sites/${site}`,trafficEnabled:"true",trafficIndependentRangesEnabled:"true",trafficRefreshSeconds:"60",trafficRequestTimeoutSeconds:"20"};
element("traffic-history-panel").dataset.historyEnabled="true";
element("traffic-statistics-panel").dataset.statisticsEnabled="true";
element("traffic-peak-panel").dataset.peakEnabled="true";
element("traffic-ap-panel").dataset.apEnabled="true";
const documentListeners={},windowListeners={};let hidden=false;
global.document={get hidden(){return hidden;},set hidden(value){hidden=value;},getElementById:element,createElementNS:(_namespace,name)=>new Element(name),addEventListener:(kind,callback)=>{(documentListeners[kind]??=[]).push(callback);}};
let now=0;global.performance={now:()=>now};
let timerId=0;const timers=new Map();
global.window={location:{origin:"https://localhost",pathname:`/admin/sites/${site}/traffic`,search:""},setTimeout:(callback,delay)=>{const id=++timerId;timers.set(id,{callback,delay});return id;},clearTimeout:(id)=>timers.delete(id),addEventListener:(kind,callback)=>{(windowListeners[kind]??=[]).push(callback);}};
let dispatches=0;let active=0;let maxActive=0;
global.fetch=(_url,options)=>{dispatches+=1;active+=1;maxActive=Math.max(maxActive,active);return new Promise((_resolve,reject)=>options.signal.addEventListener("abort",()=>{active-=1;reject(new Error("aborted"));},{once:true}));};
function fireNextTimer(){const entry=Array.from(timers.entries()).sort((left,right)=>left[1].delay-right[1].delay)[0];assert(entry,"scheduler timer exists");timers.delete(entry[0]);entry[1].callback();}
'''
    assertions = r'''
(async()=>{
  await settle();await settle();
  assert(dispatches===1&&active===1,"initial historical request dispatched once at T+0");
  now=3000;document.hidden=true;(documentListeners.visibilitychange||[]).forEach((callback)=>callback());
  await settle();await settle();
  assert(active===0,"hidden neutrally aborts the initial request");
  assert(element("traffic-history-state-title").textContent.includes("waiting"),"restored batch remains waiting");

  now=5000;document.hidden=false;(documentListeners.visibilitychange||[]).forEach((callback)=>callback());
  await settle();await settle();
  assert(dispatches===1,"visibility resume cannot bypass T+10 admission");
  assert(element("traffic-history-state-title").textContent.includes("waiting"),"resume does not fake loading");

  now=9999;fireNextTimer();await settle();await settle();
  assert(dispatches===1,"restored request is not admitted before T+10");
  now=10000;fireNextTimer();await settle();await settle();
  assert(dispatches===2&&active===1,"exactly one restored request is admitted at T+10");
  assert(maxActive===1,"historical requests never overlap");
  (windowListeners.pagehide||[]).forEach((callback)=>callback());
  await settle();
  console.log("TRAFFIC_HIDDEN_ADMISSION_GUARD_OK");
})().catch((error)=>{console.error(error);process.exitCode=1;});
'''
    output = _run_node(
        tmp_path,
        harness + _foundation_source() + _panel_source() + assertions,
    )
    assert "TRAFFIC_HIDDEN_ADMISSION_GUARD_OK" in output


def test_independent_ranges_keep_network_and_lifecycle_out_of_panel_broker():
    source = _panel_source()
    independent = source.split("const PRODUCT_ORDER", 1)[1]
    assert "fetch(" not in independent
    assert "AbortController" not in independent
    assert "setTimeout(" not in independent and "setInterval(" not in independent
    assert "visibilitychange" not in independent and "pagehide" not in independent
    assert "localStorage" not in independent and "sessionStorage" not in independent
    assert "innerHTML" not in independent
    assert "ADMISSION_GUARD_MILLISECONDS = 10000" in independent
    assert "queuePanel(PANEL_KEY" in independent


def test_template_has_per_product_ranges_only_when_feature_enabled():
    template = (
        ROOT / "app" / "admin_web" / "templates" / "admin" / "traffic.html"
    ).read_text(encoding="utf-8")
    for product in ("history", "statistics", "peak", "ap"):
        assert f"traffic-{product}-range-24h" in template
        assert f"traffic-{product}-range-7d" in template
    assert "traffic-network-range-24h" in template
    assert "traffic-network-range-7d" in template
    assert "traffic-current-range" not in template
