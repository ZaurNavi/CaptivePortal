"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const [sourcePath,fixturePath,expected,scenario]=process.argv.slice(2);
const source=fs.readFileSync(sourcePath,"utf8"),model=JSON.parse(fs.readFileSync(fixturePath,"utf8"));
class Node {
  constructor(tag){this.tagName=tag;this.children=[];this.dataset={};this.handlers={};this.textContent="";this.className="";}
  append(...items){this.children.push(...items);} replaceChildren(...items){this.children=items;}
  setAttribute(key,value){this[key]=String(value);if(key==="class")this.className=String(value);}
  addEventListener(key,fn){this.handlers[key]=fn;}
  get classList(){return {toggle:(cls,on)=>{const s=new Set(this.className.split(" "));on?s.add(cls):s.delete(cls);this.className=[...s].join(" ");},contains:cls=>this.className.split(" ").includes(cls)};}
  getBoundingClientRect(){return this.box || {left:0,right:1200,top:0,bottom:5000,width:1200,height:5000};}
  scrollIntoView(){this.scrolled=true;} focus(){document.activeElement=this;}
  set innerHTML(_){throw Error("unsafe HTML");}
}
const walk=node=>[node,...node.children.flatMap(walk)],text=node=>[node.textContent,...node.children.map(text)].join(" ");
const ids=new Map(["db-services-page","ops-status-title","ops-updated","ops-warning","refresh-button","ops-summary","ops-services","ops-databases","ops-topology-board","ops-flow-relations","ops-flow-context"].map(id=>[id,new Node("div")]));
ids.get("db-services-page").dataset={apiBase:"/admin/api/v1/operations/db-services",apiV2:"/admin/api/v2/operations/db-services"};
const document={hidden:false,handlers:{},getElementById:id=>ids.get(id)||[...ids.values()].flatMap(walk).find(n=>n.id===id),
  createElement:tag=>new Node(tag),createElementNS:(_,tag)=>new Node(tag),addEventListener(key,fn){this.handlers[key]=fn;}};
let frame,requests=0,timers=0;
const window={innerWidth:1440,handlers:{},requestAnimationFrame:fn=>{frame=fn;return 1;},cancelAnimationFrame:()=>{},addEventListener(key,fn){this.handlers[key]=fn;}};
const context={document,window,AbortController,console,Date,Map,Set,Number,String,Array,Math,Promise,
  setTimeout:(_,ms)=>{assert.equal(ms,15000);timers++;return 1;},clearTimeout:()=>{},
  fetch:async(url,options)=>{requests++;assert.equal(url,"/admin/api/v2/operations/db-services");assert.equal(options.credentials,"same-origin");return {ok:true,status:200,json:async()=>structuredClone(model)};}};
(async()=>{
  vm.runInNewContext(source,context,{timeout:1000});await new Promise(resolve=>setImmediate(resolve));
  assert.equal(requests,1);assert.equal(timers,1);
  const board=ids.get("ops-topology-board");
  if(expected==="reject") {
    assert.equal(ids.get("ops-status-title").textContent,"Unavailable");assert.equal(board.children.length,0);return;
  }
  const nodes=()=>walk(board).filter(n=>n.dataset.nodeId),edges=()=>walk(board).filter(n=>n.dataset.edgeId);
  assert.equal(nodes().length,31);assert.equal(edges().length,45);
  const dbId=scenario==="app-degraded-running"?"sensor_spool":scenario==="disabled-settings-proof"?"settings":"visits";
  const target=nodes().find(n=>n.dataset.nodeId===`db:${dbId}`);
  assert.equal(target.dataset.condition,expected,scenario);
  if(scenario==="app-degraded-running") {
    const sensor=nodes().find(n=>n.dataset.nodeId==="svc:fingerprint_sensor");
    assert.equal(sensor.dataset.condition,"degraded");
    const badges=sensor.children.filter(n=>n.className==="ops-badge");
    assert.equal(badges[0].dataset.state,"running");assert.equal(badges[0].dataset.family,"service");
    assert.equal(badges[1].dataset.state,"degraded");assert.equal(badges[1].dataset.family,"application");
  }
  assert.equal(ids.get("ops-summary").children.length,4);
  assert(text(ids.get("ops-summary")).includes("files present"));
  assert(!text(ids.get("ops-summary")).includes("/ 17 verified"));
  if(scenario==="ttl-pass") assert(text(ids.get("ops-databases")).includes("Last startup check passed · stale report"));
  if(scenario.startsWith("failed-")) assert(text(ids.get("ops-databases")).includes("Last startup check failed · stale report"));
  const nodeMap=new Map(nodes().map(n=>[n.dataset.nodeId,n]));
  for(const edge of model.topology.edges) {
    const path=edges().find(n=>n.dataset.edgeId===edge.id);
    const endpoints=[nodeMap.get(edge.from_node_id).dataset.condition,nodeMap.get(edge.to_node_id).dataset.condition];
    const color=endpoints.includes("failed")?"failed":endpoints.includes("degraded")?"degraded":endpoints.every(c=>c==="operating")?"operating":"unknown";
    assert.equal(path.dataset.condition,color);
    assert.equal(path["marker-end"],`url(#ops-arrow-${color})`);
    if(path.dataset.feedback!=="true") assert(Number(nodeMap.get(edge.from_node_id).dataset.stage)<Number(nodeMap.get(edge.to_node_id).dataset.stage));
  }
  assert.equal(edges().filter(n=>n.dataset.feedback==="true").length,2);
  assert(text(board).includes("not measured live data flow"));
  const toggle=walk(board).find(n=>n.className==="ops-problems-toggle");
  assert.equal(toggle.type,"button");assert.equal(toggle["aria-pressed"],"false");
  const order=nodes().map(n=>n.dataset.nodeId),edgeOrder=edges().map(n=>n.dataset.edgeId);
  toggle.handlers.click();assert.equal(toggle["aria-pressed"],"true");assert.equal(toggle.textContent,"Show all");
  assert.deepEqual(nodes().map(n=>n.dataset.nodeId),order);assert.deepEqual(edges().map(n=>n.dataset.edgeId),edgeOrder);
  for(const node of nodes())assert.equal(node.classList.contains("ops-normal-dim"),node.dataset.condition==="operating");
  target.handlers.focus();assert(!target.classList.contains("ops-normal-dim"));
  target.handlers.click();assert.equal(document.activeElement.id,`ops-db-row-${dbId}`);assert.equal(target["aria-pressed"],"true");
  assert.equal(requests,1);assert.equal(timers,1,"toggle/focus add no network or timer");
  // Deterministic desktop/mobile geometry canary. Real browser geometry is a
  // separate acceptance artifact; these boxes detect routing through cards.
  for(const width of [1200,390]) {
    window.innerWidth=width;
    board.box={left:0,top:0,right:width,bottom:8000,width,height:8000};
    let y=22;
    const rows=board.children.filter(n=>n.className==="ops-flow-level");
    for(const row of rows) {
      const mobile=width<=760,columns=mobile?1:3,cardWidth=(width-96-36)/columns;
      row.children.forEach((node,i)=>{
        const left=mobile?32:48+(cardWidth+18)*i,top=y+(mobile?i*148:0);
        const w=mobile?width-64:cardWidth;
        node.box={left,top,right:left+w,bottom:top+120,width:w,height:120};
      });
      const bottom=Math.max(...row.children.map(n=>n.box.bottom));
      row.box={left:48,top:y,right:width-48,bottom,width:width-96,height:bottom-y};y=bottom+40;
    }
    window.handlers.resize();frame();
    for(const path of edges()) {
      const points=[...path.d.matchAll(/[ML]([\d.-]+) ([\d.-]+)/g)].map(m=>[Number(m[1]),Number(m[2])]);
      assert(points.length>=4 && points.flat().every(Number.isFinite));
      const edge=model.topology.edges.find(e=>e.id===path.dataset.edgeId);
      for(let i=1;i<points.length;i++) {
        const [a,b]=[points[i-1],points[i]];
        for(const node of nodes()) {
          const r=node.box;
          const vertical=a[0]===b[0] && a[0]>r.left+.1 && a[0]<r.right-.1 && Math.max(a[1],b[1])>r.top+.1 && Math.min(a[1],b[1])<r.bottom-.1;
          const horizontal=a[1]===b[1] && a[1]>r.top+.1 && a[1]<r.bottom-.1 && Math.max(a[0],b[0])>r.left+.1 && Math.min(a[0],b[0])<r.right-.1;
          assert(!vertical&&!horizontal,`${width}: ${edge.id} intersects ${node.dataset.nodeId}`);
        }
      }
    }
  }
  toggle.handlers.click();assert.equal(toggle["aria-pressed"],"false");
  assert.equal(requests,1);
  console.log(`PASS ${scenario}: condition/summary/45 directed edges/SCC/toggle/focus/geometry`);
})().catch(error=>{console.error(error);process.exitCode=1;});
