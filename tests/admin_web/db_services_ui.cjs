"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const [sourcePath, fixturePath] = process.argv.slice(2);
const source = fs.readFileSync(sourcePath, "utf8");
const fixture = JSON.parse(fs.readFileSync(fixturePath, "utf8"));
class Node {
  constructor(tag) { this.tagName=tag; this.children=[]; this.dataset={}; this.handlers={}; this.textContent=""; this.hidden=false; this.className=""; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children=[...nodes]; }
  addEventListener(name, callback) { this.handlers[name]=callback; }
  setAttribute(name,value) { this[name]=String(value);if(name==="class")this.className=String(value); }
  getAttribute(name) { return this[name]; }
  get classList() { return {toggle:(value,on)=>{const set=new Set(this.className.split(" "));on?set.add(value):set.delete(value);this.className=[...set].join(" ");},contains:value=>this.className.split(" ").includes(value)}; }
  get style() { return {setProperty:()=>{}}; }
  getBoundingClientRect() { return {left:10,top:100,right:200,bottom:300,width:190,height:200}; }
  scrollIntoView() { this.scrolled=true; }
  focus() { document.activeElement=this; }
  set innerHTML(_value) { throw Error("unsafe HTML assignment"); }
}
const ids = new Map(["db-services-page","ops-status-title","ops-updated","ops-warning","refresh-button","ops-summary","ops-services","ops-databases","ops-topology-board","ops-flow-relations","ops-flow-context"].map(id=>[id,new Node("div")]));
ids.get("db-services-page").dataset.apiBase="/admin/api/v1/operations/db-services";
const document = {hidden:false, handlers:{}, getElementById:id=>ids.get(id)||[...ids.values()].flatMap(descendants).find(node=>node.id===id), createElement:tag=>new Node(tag), createElementNS:(_ns,tag)=>new Node(tag),
  addEventListener(name, callback) { this.handlers[name]=callback; }};
const frames=new Map();let frameId=0;
const window = {innerWidth:1440,handlers:{},addEventListener(name,callback) { this.handlers[name]=callback; },requestAnimationFrame:fn=>{frames.set(++frameId,fn);return frameId;},cancelAnimationFrame:id=>frames.delete(id)};
let timerId=0, calls=0, response={ok:true,status:200,json:async()=>structuredClone(fixture)}, deferred=null;
const timers=new Map(), aborts=[];
let currentTime=Date.parse(fixture.sampling_completed_at_utc)+1000;
class Clock extends Date { static now() { return currentTime; } }
const context={document,window,Date:Clock,Map,Number,String,Array,Math,Promise,
  setTimeout:(callback,ms)=>{timers.set(++timerId,{callback,ms});return timerId;},
  clearTimeout:id=>timers.delete(id),
  AbortController:class { constructor(){this.signal={};} abort(){aborts.push(true);} },
  fetch:(url,options)=>{calls++;assert.equal(url,"/admin/api/v1/operations/db-services");assert.equal(options.credentials,"same-origin");assert.equal(options.cache,"no-store");
    return deferred ? new Promise((resolve,reject)=>{deferred.resolve=resolve;deferred.reject=reject;}) : Promise.resolve(response);}
};
const tick=async()=>{await new Promise(resolve=>setImmediate(resolve));};
const text=node=>[node.textContent,...node.children.map(text)].join(" ");
const descendants=node=>[node,...node.children.flatMap(descendants)];
(async()=>{
  vm.runInNewContext(source, {window:{}}, {timeout:1000}); // DOM-less import is inert.
  vm.runInNewContext(source,context,{timeout:1000});
  await tick();
  assert.equal(calls,1);
  assert.equal(ids.get("ops-summary").children.length,4);
  assert.equal(ids.get("ops-services").children.length,9);
  assert.equal(ids.get("ops-databases").children.length,17);
  assert.equal(ids.get("ops-status-title").textContent,"Available");
  assert.equal(timers.size,1); assert.equal([...timers.values()][0].ms,15000);
  assert(text(ids.get("ops-summary")).includes("0 / 17 verified"));
  assert(text(ids.get("ops-summary")).includes("111 / 9 running"),"summary must use backend count, not recompute");
  assert(text(ids.get("ops-databases")).includes("Present · unverified"));
  assert(text(ids.get("ops-databases")).includes("0 B"));
  assert(text(ids.get("ops-databases")).includes("—"));
  assert(text(ids.get("ops-databases")).includes("1.0 KB"));
  assert(text(ids.get("ops-databases")).includes("1.0 MB"));
  assert(text(ids.get("ops-databases")).includes("1.0 GB"));
  assert(text(ids.get("ops-databases")).includes("1.0 TB"));
  assert(text(ids.get("ops-databases")).includes("<script>SYNTHETIC</script>"));
  assert(!text(ids.get("ops-databases")).includes("/private/PATH_CANARY"));
  assert(!text(ids.get("ops-services")).includes("Healthy"));
  assert(descendants(ids.get("ops-databases")).some(n=>n.tagName==="details"));
  const board=ids.get("ops-topology-board");
  const graphNodes=()=>descendants(board).filter(node=>node.dataset.nodeId);
  const graphEdges=()=>descendants(board).filter(node=>node.dataset.edgeId);
  assert.equal(graphNodes().length,31);assert.equal(new Set(graphNodes().map(n=>n.dataset.nodeId)).size,31);
  assert.equal(graphEdges().length,45);assert.equal(ids.get("ops-flow-relations").children.length,45);
  fixture.topology.edges.forEach((edge,index)=>{
    const label=id=>fixture.topology.nodes.find(n=>n.id===id).label;
    assert.equal(ids.get("ops-flow-relations").children[index].textContent,`${label(edge.from_node_id)} → ${{feeds:"Feed",writes_to:"Write",read_by:"Read"}[edge.relation]} → ${label(edge.to_node_id)}`);
  });
  for(const node of graphNodes()) {
    const item=fixture.topology.nodes.find(n=>n.id===node.dataset.nodeId);
    assert.equal(node.dataset.nodeType,item.node_type);
    const row=(item.node_type==="service"?fixture.services:fixture.databases).find(r=>r.id===item.catalog_ref);
    const badges=node.children.filter(n=>n.className==="ops-badge");
    if(["source","consumer"].includes(item.node_type))assert.equal(badges.length,0);
    else assert.equal(badges[0].dataset.state,row.operational_state);
  }
  for(const edge of graphEdges())assert.equal(edge["marker-end"],"url(#ops-arrow)");
  assert(graphEdges().some(edge=>edge.dataset.crossLane==="true"));
  assert.equal(frames.size,1);window.handlers.resize();window.handlers.resize();assert.equal(frames.size,1);
  [...frames.values()].forEach(fn=>fn());frames.clear();
  assert(graphEdges().every(edge=>edge.d.startsWith("M")&&!edge.d.includes("NaN")));
  const node=graphNodes().find(n=>n.dataset.nodeId==="svc:portal_core");
  const before=graphEdges().map(n=>n.dataset.relation);
  node.handlers.mouseenter();assert(graphEdges().some(n=>n.classList.contains("ops-subdued")));
  node.handlers.click();assert.equal(document.activeElement.id,"ops-service-row-portal_core");assert(document.activeElement.scrolled);
  assert.equal(node["aria-pressed"],"true");board.handlers.keydown({key:"Escape"});assert.equal(node["aria-pressed"],"false");
  assert.deepEqual(graphEdges().map(n=>n.dataset.relation),before);
  const dbNode=graphNodes().find(n=>n.dataset.nodeId==="db:visits");dbNode.handlers.focus();dbNode.handlers.click();
  assert.equal(document.activeElement.id,"ops-db-row-visits");assert.equal(document.activeElement.tabIndex,-1);
  document.hidden=true; document.handlers.visibilitychange();
  assert.equal(timers.size,0);
  await ids.get("refresh-button").handlers.click(); assert.equal(calls,1);
  deferred={}; document.hidden=false; document.handlers.visibilitychange(); await tick();
  assert.equal(calls,2); assert.equal(ids.get("refresh-button").disabled,true);
  ids.get("refresh-button").handlers.click(); document.handlers.visibilitychange();
  assert.equal(calls,2,"at most one fetch in flight");
  deferred.resolve(response); await tick(); deferred=null;
  assert.equal(timers.size,1); assert.equal(ids.get("refresh-button").disabled,false);
  response={ok:false,status:503,json:async()=>({error:{code:"snapshot_pending"}})};
  await ids.get("refresh-button").handlers.click();
  assert.equal(ids.get("ops-status-title").textContent,"Collecting operational snapshot…");
  assert.equal(ids.get("ops-services").children.length,9,"retain prior snapshot");
  response={ok:false,status:503,json:async()=>({error:{code:"operations_unavailable"}})};
  currentTime+=100000;
  await ids.get("refresh-button").handlers.click();
  assert.equal(ids.get("ops-status-title").textContent,"Stale data");
  assert.equal(ids.get("db-services-page").dataset.outdated,"true");
  assert.equal(ids.get("ops-databases").children.length,17);
  assert.equal(graphNodes().length,31);assert.equal(graphEdges().length,45);
  const malformed=structuredClone(fixture);malformed.topology.edges[0].state="active";
  response={ok:true,status:200,json:async()=>malformed};
  const previousNode=graphNodes()[0];await ids.get("refresh-button").handlers.click();
  assert.equal(graphNodes()[0],previousNode,"reject malformed graph before replacing trustworthy data");
  const partial=structuredClone(fixture); partial.snapshot_state="partial"; partial.summary.storage.total_complete=false;
  partial.partial_failures=[{source:"db_stat",id:"settings",code:"stat_unavailable"}];
  response={ok:true,status:200,json:async()=>partial};
  await ids.get("refresh-button").handlers.click();
  assert.equal(ids.get("ops-status-title").textContent,"Partial data");
  assert.equal(ids.get("ops-warning").hidden,false);
  assert.equal(graphEdges().length,45);assert.equal(graphNodes().length,31);
  assert(text(ids.get("ops-summary")).includes("Known subtotal"));
  partial.sample_status="stale";
  await ids.get("refresh-button").handlers.click();
  assert.equal(ids.get("ops-status-title").textContent,"Stale data");
  partial.summary.services.expected_running=0;
  await ids.get("refresh-button").handlers.click();
  assert(text(ids.get("ops-summary")).includes("0 expected to run"));
  deferred={}; ids.get("refresh-button").handlers.click(); await tick();
  window.handlers.pagehide();
  assert.equal(timers.size,0); assert.equal(aborts.length,1);
  deferred.resolve(response); await tick(); assert.equal(timers.size,0);
  console.log("DB-SERVICES-01 frontend: render/format/security/refresh/visibility/one-in-flight/stale/partial/dispose PASS");
})().catch(error=>{console.error(error);process.exitCode=1;});
