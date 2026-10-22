"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const [sourcePath,fixturePath,scenario]=process.argv.slice(2);
const source=fs.readFileSync(sourcePath,"utf8"),fixture=JSON.parse(fs.readFileSync(fixturePath,"utf8"));
class Node {
  constructor(tag){this.tagName=tag;this.children=[];this.dataset={};this.handlers={};this.textContent="";this.hidden=false;this.className="";}
  append(...values){this.children.push(...values);} replaceChildren(...values){this.children=[...values];}
  addEventListener(name,fn){this.handlers[name]=fn;} setAttribute(name,value){this[name]=String(value);if(name==="class")this.className=String(value);}
  get classList(){return {toggle:()=>{}};} get style(){return {setProperty:()=>{}};}
  getBoundingClientRect(){return {left:10,top:100,right:200,bottom:300,width:190,height:200};}
  scrollIntoView(){} focus(){} set innerHTML(value){throw Error("innerHTML forbidden");}
}
const names=["db-services-page","ops-status-title","ops-updated","ops-warning","refresh-button","ops-summary","ops-services","ops-databases","ops-topology-board","ops-flow-relations","ops-flow-context"];
const ids=new Map(names.map(name=>[name,new Node("div")]));
ids.get("db-services-page").dataset={apiBase:"/admin/api/v1/operations/db-services",apiV2:"/admin/api/v2/operations/db-services"};
const document={hidden:false,handlers:{},getElementById:id=>ids.get(id),createElement:tag=>new Node(tag),createElementNS:(_,tag)=>new Node(tag),addEventListener(name,fn){this.handlers[name]=fn;}};
const window={innerWidth:1440,handlers:{},addEventListener(name,fn){this.handlers[name]=fn;},requestAnimationFrame:()=>1,cancelAnimationFrame:()=>{}};
let sequence=0,calls=[],timers=new Map();
const text=node=>[node.textContent,...node.children.map(text)].join(" ");
const snapshot=()=>structuredClone(fixture);
const context={document,window,Map,Set,Number,String,Array,Math,Promise,Date,
  setTimeout:(fn,ms)=>{timers.set(++sequence,{fn,ms});return sequence;},clearTimeout:id=>timers.delete(id),
  AbortController:class {constructor(){this.signal={};}abort(){}},
  fetch:async(url,options)=>{
    calls.push(url);assert.equal(options.credentials,"same-origin");assert.equal(options.cache,"no-store");
    if (scenario==="fallback" && url.includes("/v2/")) return {status:404,ok:false,json:async()=>({})};
    if (["401","403","503"].includes(scenario)) return {status:Number(scenario),ok:false,json:async()=>({error:{code:"operations_unavailable"}})};
    const model=snapshot();
    if (scenario==="fallback") model.api_version="admin.operations.db-services.v1";
    if (scenario==="bad-reason") model.services[0].application_health_evidence.reason="/PRIVATE_XSS_CANARY";
    if (scenario==="false-green") {model.services[0].application_health=model.services[0].application_health_evidence.state="healthy";}
    if (scenario==="false-verified") model.databases[0].store_verification.status="verified";
    if (scenario==="check-bad-scope") model.databases.find(r=>r.id==="visits").store_verification.scope=["integrity_check"];
    if (scenario==="check-bad-owner") model.databases.find(r=>r.id==="visits").store_verification.source="fingerprint-sensor.service";
    if (scenario==="check-raw-path") model.databases.find(r=>r.id==="visits").store_verification.path="/PRIVATE_XSS_CANARY";
    return {status:200,ok:true,json:async()=>model};
  }};
const tick=async()=>{await new Promise(resolve=>setImmediate(resolve));};
(async()=>{
  vm.runInNewContext(source,context,{timeout:1000});await tick();
  const rejected=["401","403","503","bad-reason","false-green","false-verified","check-bad-scope","check-bad-owner","check-raw-path"].includes(scenario);
  assert.equal(calls.length,scenario==="fallback"?2:1);
  assert.equal(calls[0],"/admin/api/v2/operations/db-services");
  assert.equal(timers.size,1);assert.equal([...timers.values()][0].ms,15000);
  if (rejected){assert.equal(ids.get("ops-services").children.length,0);assert.equal(ids.get("ops-status-title").textContent,"Unavailable");}
  else {
    assert.equal(ids.get("ops-summary").children.length,4);assert.equal(ids.get("ops-services").children.length,9);
    assert.equal(ids.get("ops-databases").children.length,17);
    if(scenario!=="fallback"){
      assert(text(ids.get("ops-services")).includes("Health observed"));
      assert(text(ids.get("ops-services")).includes("Source-native ready; dependencies confirmed"));
      assert(text(ids.get("ops-summary")).includes(scenario.startsWith("check-") ? "Historical owner startup checks shown separately" : "No SQLite attestation collected"));
      assert(text(ids.get("ops-databases")).includes("DELETE journal (not included in main + WAL + SHM)"));
      if(scenario.startsWith("check-")){
        const expected={"check-passed":"Startup check passed","check-failed":"Startup check failed","check-stale":"Previously checked · stale evidence","check-settings":"Not applicable · Settings disabled"}[scenario];
        assert(text(ids.get("ops-databases")).includes(expected));
        assert(text(ids.get("ops-databases")).includes("SQLite quick_check"));
        assert(!text(ids.get("ops-databases")).includes("full SQLite integrity_check"));
      }
    }
  }
  assert(!text(ids.get("ops-services")).includes("PRIVATE_XSS_CANARY"));
  const before=calls.length;document.hidden=true;document.handlers.visibilitychange();
  assert.equal(timers.size,0);await ids.get("refresh-button").handlers.click();assert.equal(calls.length,before);
  document.hidden=false;document.handlers.visibilitychange();await tick();
  assert.equal(calls.length,before+1);
  assert.equal(calls.at(-1),scenario==="fallback"?"/admin/api/v1/operations/db-services":"/admin/api/v2/operations/db-services");
  console.log("PASS v2 truth / privacy / one visible-only poll / explicit v1 fallback");
})().catch(error=>{console.error(error);process.exitCode=1;});
