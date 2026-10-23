/* DB-SERVICES-01: one global, read-only snapshot; no Site controller. */
(() => {
  "use strict";
  if (typeof document === "undefined") return;
  const root = document.getElementById("db-services-page");
  if (!root) return;
  const byId = (id) => document.getElementById(id);
  const title = byId("ops-status-title");
  const updated = byId("ops-updated");
  const warning = byId("ops-warning");
  const refresh = byId("refresh-button");
  const labels = {present_unverified: "Present · unverified", not_provisioned: "Not provisioned", optional_disabled: "Optional · disabled"};
  const display = (value) => value == null ? "—" : labels[value] || String(value).replace(/^./, (c) => c.toUpperCase());
  const reasons = {
    probe_unavailable: "Process evidence unavailable", intent_unknown: "Deployment intent not confirmed",
    unexpected_running: "Process running despite disabled/maintenance intent", configured_disabled: "Configured disabled",
    unit_unavailable: "Expected unit unavailable", unit_failed: "Unit reported failure", expected_stopped: "Expected process stopped",
    sample_timeout: "Metadata collection budget exceeded", sample_stale: "Operational snapshot is stale",
    symlink_file: "Symbolic link rejected", nonregular_file: "Nonregular file rejected",
    stat_unavailable: "File metadata unavailable", metadata_permission_boundary: "Metadata permission boundary; size unknown",
    orphan_sidecar_possible: "Main file absent; sidecar present", file_missing: "Expected file missing; owner bootstrap needs investigation",
    not_attested: "File presence only; see separate owner startup check", storage_collision: "File identity collision; sizes excluded"
  };
  const healthReasons = {source_ready:"Source-native ready; dependencies confirmed", source_degraded:"Source reports limited operation",
    source_unavailable:"Source reports unavailable", source_initializing:"Source initializing", source_stopping:"Source stopping",
    dependencies_unconfirmed:"Required dependencies not confirmed", pending_attribution:"Limited: confirmed pending attribution backlog",
    registry_degraded:"Registry dependency degraded", source_poll_stale:"Source confirmation is stale", capacity_limited:"Source capacity limited",
    blocked_conflict:"Source blocked by a conflict", report_unavailable:"Trusted health evidence unavailable", report_stale:"Health evidence expired",
    backfilling_incomplete_coverage:"Backfilling / coverage incomplete", source_lagging:"Source processing is lagging", source_stale:"Native source is stale",
    projection_rebuilding:"Projection rebuilding / coverage incomplete", projection_catching_up:"Projection catching up", projection_stale:"Projection data is stale",
    core_composed:"Local Core composition ready; not Omada end-to-end verification", core_unavailable:"Required Web/Auth composition unavailable",
    core_component_degraded:"Required enabled component has limited availability", authorization_degraded:"Recent cached authorization failure"};
  const phaseBNotice=(row)=>row.application_health_evidence?.source==="observed_via_sensor" ? "Observed via Sensor; not a Suricata self-report" :
    row.application_health_evidence?.source==="portal_in_process" ? "In-process composition; not Omada end-to-end verification" :
    ["projection_rebuilding","projection_catching_up","projection_stale"].includes(row.application_health_evidence?.reason) ? healthReasons[row.application_health_evidence.reason] : null;
  const reason = (value) => value == null ? "No collection failure reported" : Object.hasOwn(reasons, value) ? reasons[value] : "Evidence unavailable";
  function element(tag, text, cls) {
    const node = document.createElement(tag);
    if (text != null) node.textContent = String(text);
    if (cls) node.className = cls;
    return node;
  }
  function bytes(value) {
    if (!Number.isSafeInteger(value) || value < 0) return "—";
    const units = ["B", "KB", "MB", "GB", "TB"];
    let index = 0, number = value;
    while (number >= 1024 && index < units.length - 1) { number /= 1024; index += 1; }
    return `${index ? number.toFixed(number < 10 ? 1 : 0) : number} ${units[index]}`;
  }
  function badge(state, family) {
    const node = element("span", display(state), "ops-badge");
    node.dataset.state = state;
    node.dataset.family = family;
    return node;
  }
  function lastResult(row) {
    const v = row.store_verification;
    return v && Object.hasOwn(v,"last_result") ? v.last_result : v && ["passed","failed","unknown"].includes(v.status) ? v.status : null;
  }
  function serviceCondition(row, model) {
    if (model.sample_status !== "fresh") return "unknown";
    if (row.operational_state === "failed" || row.application_health === "unavailable" ||
        row.operational_state === "stopped" && row.expected_mode === "run") return "failed";
    if (row.operational_state === "degraded" || row.application_health === "degraded") return "degraded";
    return row.operational_state === "running" ? "operating" : "unknown";
  }
  function databaseCondition(row, model) {
    if (model.sample_status !== "fresh") return "unknown";
    const v=row.store_verification, owners=model.services.filter(s=>row.writer_service_ids.includes(s.id));
    const owner=model.services.find(s=>s.unit===v?.source);
    if (["failed","incompatible"].includes(row.operational_state) ||
        ["symlink_file","nonregular_file","storage_collision"].includes(row.reason_code) ||
        owners.some(s=>s.operational_state === "failed") ||
        row.file_presence === "absent" && row.expected_mode === "expected" && row.operational_state === "unavailable" ||
        v && lastResult(row) === "failed" && v.binding === "matched") return "failed";
    const ni02 = row.id === "network_metadata_projection";
    if (row.operational_state === "degraded" || owners.some(s=>s.operational_state === "degraded" ||
        !ni02 && ["degraded","unavailable"].includes(s.application_health))) return "degraded";
    return row.expected_mode === "expected" && row.file_presence === "present" && row.operational_state === "present_unverified" &&
      row.metadata_evidence?.state === "fresh" &&
      owner?.operational_state === "running" && v && lastResult(row) === "passed" && v.binding === "matched" &&
      (!ni02 || v.status === "passed" && v.freshness === "current_report") ? "operating" : "unknown";
  }
  function databaseBadge(row, model) {
    const state=databaseCondition(row,model), node=badge(state,"condition");
    node.textContent=state === "operating" ? "Operating · startup check OK" : state === "failed" ? "Failure confirmed" :
      state === "degraded" ? "Degraded" : row.expected_mode === "optional_disabled" ? "Disabled" :
      row.file_presence === "present" ? "Present · check not bound" : display(row.operational_state);
    return node;
  }
  function field(label, value, mono = false) {
    const node = element("div", null, "ops-field");
    node.append(element("span", label, "ops-field-label"), element("span", value == null ? "—" : value, mono ? "mono" : ""));
    return node;
  }
  function pendingLabel(model) {
    const count = model.workload?.network_metadata_projection?.pending_attribution_count;
    return `Pending attribution: ${model.sample_status === "fresh" && Number.isSafeInteger(count) && count >= 0 ? count : "Unknown"}`;
  }
  function workloadLabels(id, model) {
    const fresh=model.sample_status === "fresh", metrics=model.workload?.[id];
    const count=(value)=>fresh && Number.isSafeInteger(value) && value>=0 ? value : null;
    const show=(value)=>value===null ? "Unknown" : value;
    if(id==="fingerprint_sensor") {
      const rows=count(metrics?.spool_pending_rows), size=count(metrics?.spool_bytes), age=count(metrics?.oldest_spool_age_seconds);
      return [`Spool pending: ${show(rows)}`, `Spool size: ${size===null ? "Unknown" : bytes(size)}`,
        `Oldest pending: ${age===null ? "Unknown" : age+"s"}`];
    }
    // Phase 1-B numeric acceptance is HOLD until NI02 source epoch is bound.
    return id==="network_service_recognition" ? ["Feed backlog: Unknown"] : [];
  }
  function details(entries) {
    const node = element("details", null, "ops-details");
    node.append(element("summary", "Details"));
    const body = element("div", null, "ops-detail-grid");
    entries.forEach(([label, value]) => body.append(field(label, Array.isArray(value) ? value.join(", ") || "—" : value, true)));
    node.append(body);
    return node;
  }
  function tile(label, main, secondary) {
    const node = element("article", null, "ops-tile");
    node.append(element("h3", label), element("strong", main), element("p", secondary));
    return node;
  }
  function uptime(value) {
    if (!Number.isSafeInteger(value) || value < 0) return "—";
    const days = Math.floor(value / 86400), hours = Math.floor(value / 3600) % 24;
    return days ? `${days}d ${hours}h` : hours ? `${hours}h ${Math.floor(value / 60) % 60}m` : `${Math.floor(value / 60)}m`;
  }
  // Presentation stages only. Relationships always come from the backend catalog.
  const lanes = [
    ["portal_guest", "Portal & Guest Lifecycle", [
      ["Inputs", "src:guest_http", "src:omada_controller", "src:visit_webhook_journal"],
      ["Core", "svc:portal_core"], ["Core stores A", "db:portal_counter", "db:public_traffic", "db:visitor_registry", "db:visits"],
      ["Core stores B", "db:observations", "db:current_state", "db:settings"], ["Consumer", "consumer:admin_read_models"]]],
    ["fingerprint", "Fingerprint Pipeline", [
      ["Ingress", "src:passive_capture"], ["Capture", "svc:fingerprint_suricata", "svc:fingerprint_sensor"],
      ["Sensor outputs", "db:sensor_spool", "db:network_attribution", "svc:fingerprint_evidence"],
      ["Evidence / control", "db:fingerprint_evidence", "db:fingerprint_control_plane", "db:fingerprint_integration"],
      ["Classification", "svc:fingerprint_classification"], ["Output", "db:fingerprint_classification"]]],
    ["network_intelligence", "Network Intelligence", [
      ["Ingest", "svc:network_metadata"], ["Metadata", "db:network_metadata"], ["Projection", "svc:network_metadata_projection"],
      ["Device edges", "db:network_metadata_projection"], ["Recognition", "svc:network_service_recognition"],
      ["Intelligence", "db:network_service_intelligence"]]],
    ["traffic_analytics", "Traffic & Analytics", [["Projection", "svc:traffic_projection"], ["History", "db:traffic_projection"]]]
  ];
  const relationLabels = {feeds:"Feed", writes_to:"Write", read_by:"Read"};
  const board = byId("ops-topology-board");
  let topology = null, svg = null, selected = null, geometryFrame = null, problemsOnly = false;
  const nodeElements = new Map(), laneElements = new Map(), edgeElements = new Map();
  const controls=element("div",null,"ops-flow-controls"), problems=element("button","Show problems","ops-problems-toggle");
  problems.type="button"; problems.setAttribute("aria-pressed","false");
  problems.addEventListener("click",()=>{
    problemsOnly=!problemsOnly; problems.setAttribute("aria-pressed",String(problemsOnly));
    problems.textContent=problemsOnly ? "Show all" : "Show problems";
    if(topology) emphasize(selected);
  });
  controls.append(problems,element("p","Structural relationships only; link colors reflect endpoint states, not measured live data flow.","ops-flow-disclaimer"));
  const conditionLegend=element("div",null,"ops-condition-legend");
  ["operating","degraded","failed","unknown"].forEach(state=>conditionLegend.append(badge(state,"condition")));
  controls.append(conditionLegend);
  function svgElement(tag, attributes) {
    const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
    return node;
  }
  function emphasize(id) {
    const related = new Set(id ? [id] : []);
    topology.edges.forEach((edge) => {
      const incident = edge.from_node_id === id || edge.to_node_id === id;
      if (incident) { related.add(edge.from_node_id); related.add(edge.to_node_id); }
      const path = edgeElements.get(edge.id);
      path.classList.toggle("ops-emphasized", !!id && incident);
      path.classList.toggle("ops-subdued", !!id && !incident);
      path.classList.toggle("ops-normal-dim", problemsOnly && path.dataset.condition === "operating" && !incident);
    });
    nodeElements.forEach((node, identity) => {
      node.classList.toggle("ops-emphasized", related.has(identity));
      node.classList.toggle("ops-subdued", !!id && !related.has(identity));
      node.classList.toggle("ops-normal-dim", problemsOnly && node.dataset.condition === "operating" && !related.has(identity));
      node.setAttribute("aria-pressed", String(identity === selected));
    });
    const node = topology.nodes.find((item) => item.id === id);
    byId("ops-flow-context").textContent=node ? `${node.label} · Structural relationships only · ${topology.edges.filter((edge) => edge.from_node_id === id || edge.to_node_id === id).map((edge) => `${relationLabels[edge.relation]}: ${topology.nodes.find((item) => item.id === (edge.from_node_id === id ? edge.to_node_id : edge.from_node_id)).label}`).join("; ")}` : "Select a node to inspect its structural relationships. Classification ↔ Integration is a feedback loop.";
  }
  function activateNode(node) {
    selected = node.id;
    emphasize(selected);
    if (node.node_type === "service" || node.node_type === "database") {
      const row = byId(`${node.node_type === "service" ? "ops-service" : "ops-db"}-row-${node.catalog_ref}`);
      row?.scrollIntoView({block:"center", behavior:"auto"});
      row?.focus({preventScroll:true});
    }
  }
  function geometry() {
    geometryFrame = null;
    if (!svg || !topology) return;
    const bounds = board.getBoundingClientRect();
    svg.setAttribute("viewBox", `0 0 ${bounds.width} ${bounds.height}`);
    const mobile = window.innerWidth <= 760;
    const rect = (node) => {
      const box = node.getBoundingClientRect();
      return {left:box.left-bounds.left, right:box.right-bounds.left, top:box.top-bounds.top, bottom:box.bottom-bounds.top, cy:(box.top+box.bottom)/2-bounds.top};
    };
    topology.edges.forEach((edge, index) => {
      const a = rect(nodeElements.get(edge.from_node_id)), b = rect(nodeElements.get(edge.to_node_id));
      const sourceLane = rect(laneElements.get(edge.from_node_id)), targetLane = rect(laneElements.get(edge.to_node_id));
      const feedback=edgeElements.get(edge.id).dataset.feedback === "true";
      // Rails stay outside every card; row gaps are the only horizontal runs.
      const rail = feedback ? 6+index*.45 : bounds.width-6-index*(mobile ? .45 : .7);
      let points;
      if (mobile) {
        const side=feedback ? "left" : "right";
        points=[[a[side],a.cy],[rail,a.cy],[rail,b.cy],[b[side],b.cy]];
      } else {
        const ax=(a.left+a.right)/2, bx=(b.left+b.right)/2;
        const exit=sourceLane.bottom+8+index%3*3, enter=feedback ? targetLane.bottom+8+index%3*3 : targetLane.top-8-index%3*3;
        points=[[ax,a.bottom],[ax,exit],[rail,exit],[rail,enter],[bx,enter],[bx,feedback ? b.bottom : b.top]];
      }
      edgeElements.get(edge.id).setAttribute("d", points.map(([x,y],i) => `${i ? "L" : "M"}${x.toFixed(2)} ${y.toFixed(2)}`).join(" "));
    });
  }
  function scheduleGeometry() {
    if (geometryFrame === null) geometryFrame = window.requestAnimationFrame(geometry);
  }
  function renderTopology(model) {
    topology = model.topology;
    nodeElements.clear(); laneElements.clear(); edgeElements.clear();
    const nodes = new Map(topology.nodes.map((node) => [node.id, node]));
    const serviceRows = new Map(model.services.map((row) => [row.id,row]));
    const dbRows = new Map(model.databases.map((row) => [row.id,row]));
    svg = svgElement("svg", {class:"ops-flow-svg", "aria-hidden":"true", focusable:"false"});
    const defs = svgElement("defs", {});
    ["operating","degraded","failed","unknown"].forEach(condition=>{
      const marker=svgElement("marker",{id:`ops-arrow-${condition}`,viewBox:"0 0 8 8",refX:"7",refY:"4",markerWidth:"5",markerHeight:"5",orient:"auto"});
      marker.dataset.condition=condition;
      marker.append(svgElement("path",{d:"M 0 0 L 8 4 L 0 8 z",class:"ops-arrowhead"})); defs.append(marker);
    });
    svg.append(defs);
    board.replaceChildren(controls,svg);
    // Longest-path levels of the structural DAG. Only the known SCC write
    // return is excluded from ranking, never from rendering or navigation.
    const feedbackReturn=e=>e.from_node_id==="svc:fingerprint_classification" && e.to_node_id==="db:fingerprint_integration";
    const remaining=new Set(nodes.keys()), ranks=new Map();
    while(remaining.size) {
      const ready=[...remaining].filter(id=>topology.edges.filter(e=>e.to_node_id===id && !feedbackReturn(e)).every(e=>ranks.has(e.from_node_id)));
      if(!ready.length) throw new Error("unexpected_topology_cycle");
      ready.forEach(id=>{
        ranks.set(id,Math.max(0,...topology.edges.filter(e=>e.to_node_id===id && !feedbackReturn(e)).map(e=>ranks.get(e.from_node_id)+1)));
        remaining.delete(id);
      });
    }
    for(let level=0;level<=Math.max(...ranks.values());level+=1) {
      const identities=[...nodes.keys()].filter(id=>ranks.get(id)===level);
      for(let offset=0;offset<identities.length;offset+=3) {
        const stage=element("div",null,"ops-flow-level"); stage.dataset.level=String(level);
        identities.slice(offset,offset+3).forEach(identity=>{
          const item = nodes.get(identity), node = element("button", null, "ops-flow-node");
          node.type = "button"; node.dataset.nodeId = item.id; node.dataset.nodeType = item.node_type;
          node.dataset.stage = String(level); node.dataset.group=item.group;
          node.dataset.condition=item.node_type==="service" ? serviceCondition(serviceRows.get(item.catalog_ref),model) :
            item.node_type==="database" ? databaseCondition(dbRows.get(item.catalog_ref),model) : "unknown";
          node.setAttribute("aria-pressed", "false");
          node.append(element("span",`${display(item.node_type)} · ${lanes.find(l=>l[0]===item.group)[1]}`,"ops-node-type"), element("strong", item.label));
          if (item.node_type === "service") {
            const row = serviceRows.get(item.catalog_ref);
            const appBadge=badge(row.application_health,"application");appBadge.textContent=`App: ${display(row.application_health)}`;
            node.append(badge(row.operational_state,"service"),appBadge);
            if(row.id==="network_metadata_projection") node.append(element("small",pendingLabel(model)));
            workloadLabels(row.id, model).forEach(label=>node.append(element("small",label)));
            if(row.application_health_evidence?.reason==="backfilling_incomplete_coverage")
              node.append(element("small",healthReasons.backfilling_incomplete_coverage));
            if(phaseBNotice(row))node.append(element("small",phaseBNotice(row)));
          } else if (item.node_type === "database") {
            const row = dbRows.get(item.catalog_ref);
            node.append(element("small", row.filename, "mono"), databaseBadge(row,model), element("small", bytes(row.total_footprint_bytes)));
          }
          node.addEventListener("mouseenter", () => emphasize(item.id));
          node.addEventListener("mouseleave", () => emphasize(document.activeElement?.dataset?.nodeId || selected));
          node.addEventListener("focus", () => emphasize(item.id));
          node.addEventListener("blur", () => emphasize(selected));
          node.addEventListener("click", () => activateNode(item));
          stage.append(node); nodeElements.set(identity,node); laneElements.set(identity,stage);
      });
      board.append(stage);
      }
    }
    topology.edges.forEach((edge) => {
      const endpoints=[nodeElements.get(edge.from_node_id).dataset.condition,nodeElements.get(edge.to_node_id).dataset.condition];
      const condition=endpoints.includes("failed") ? "failed" : endpoints.includes("degraded") ? "degraded" : endpoints.every(s=>s==="operating") ? "operating" : "unknown";
      const path = svgElement("path", {class:`ops-flow-edge ops-relation-${edge.relation}`, "marker-end":`url(#ops-arrow-${condition})`});
      path.dataset.condition=condition;
      path.dataset.feedback=String(feedbackReturn(edge) || edge.from_node_id==="db:fingerprint_integration" && edge.to_node_id==="svc:fingerprint_classification");
      path.dataset.edgeId=edge.id; path.dataset.relation=edge.relation;
      path.dataset.crossLane = String(nodes.get(edge.from_node_id).group !== nodes.get(edge.to_node_id).group);
      svg.append(path); edgeElements.set(edge.id,path);
    });
    byId("ops-flow-relations").replaceChildren(...topology.edges.map((edge) => element("li", `${nodes.get(edge.from_node_id).label} → ${relationLabels[edge.relation]} → ${nodes.get(edge.to_node_id).label}`)));
    if (!nodes.has(selected)) selected = null;
    emphasize(selected); scheduleGeometry();
  }
  function validTopology(model) {
    const graph = model.topology;
    if (!graph || graph.contract_version !== "admin.operations.topology.v1" || graph.scope !== "global" || graph.mode !== "structural_only" ||
        !Array.isArray(graph.nodes) || graph.nodes.length !== 31 || !Array.isArray(graph.edges) || graph.edges.length !== 45) return false;
    const expected = new Map(lanes.flatMap(([group,,stages]) => stages.flatMap(([, ...ids]) => ids.map((id) => [id,group]))));
    const ids = new Set(), edges = new Set();
    for (const node of graph.nodes) {
      if (!expected.has(node.id) || ids.has(node.id) || expected.get(node.id) !== node.group || typeof node.label !== "string") return false;
      const type = node.id.startsWith("svc:") ? "service" : node.id.startsWith("db:") ? "database" : node.id.startsWith("src:") ? "source" : "consumer";
      if (node.node_type !== type || node.catalog_ref !== (["service","database"].includes(type) ? node.id.split(":")[1] : null)) return false;
      if (type === "service" && !model.services.some((row) => row.id === node.catalog_ref)) return false;
      if (type === "database" && !model.databases.some((row) => row.id === node.catalog_ref)) return false;
      ids.add(node.id);
    }
    for (const edge of graph.edges) {
      if (Object.keys(edge).sort().join(",") !== "flow_evidence,from_node_id,id,relation,to_node_id" ||
          !ids.has(edge.from_node_id) || !ids.has(edge.to_node_id) || !Object.hasOwn(relationLabels,edge.relation) ||
          edge.flow_evidence !== "not_instrumented" || edges.has(edge.id) || edge.id !== `e:${edge.from_node_id}:${edge.relation}:${edge.to_node_id}`) return false;
      edges.add(edge.id);
    }
    return true;
  }
  function render(model) {
    root.dataset.outdated = model.sample_status === "stale" ? "true" : "false";
    const summary = model.summary, v2 = ["admin.operations.db-services.v2","admin.operations.db-services.v3","admin.operations.db-services.v4"].includes(model.api_version);
    // V1 already provides each app-health state. Keep these axes separate from
    // backend process/store status counts; never add overlapping unknowns.
    const health = {healthy:0, degraded:0, unavailable:0, unknown:0, stale:0};
    model.services.forEach((row) => { health[Object.hasOwn(health, row.application_health) ? row.application_health : "unknown"] += 1; });
    const unknownHealth = health.unknown + health.stale;
    const checks={passed:0,failed:0,missing:0,stale:0};
    model.databases.forEach(row=>{
      const result=lastResult(row); checks[result === "passed" || result === "failed" ? result : "missing"]+=1;
      if(row.store_verification?.status === "stale") checks.stale+=1;
    });
    byId("ops-summary").replaceChildren(
      tile("Services", summary.services.expected_running ? `${summary.services.running} / ${summary.services.expected_running} processes running` : "0 processes expected to run",
        `${summary.services.registered} registered · App health: ${health.healthy} confirmed healthy · ${health.degraded} degraded · ${health.unavailable} unavailable · ${unknownHealth} unknown/stale`),
      tile("Databases", `${model.databases.filter(row=>row.file_presence === "present").length} / ${summary.databases.registered} files present`,
        `${checks.passed} last check passed · ${checks.failed} last check failed · ${checks.missing} no result. ${checks.stale} historical reports stale (overlapping axis). ${summary.databases.disabled} disabled · ${summary.databases.not_provisioned} not provisioned. Historical owner startup checks, not continuous SQLite integrity monitoring.`),
      tile(summary.storage.total_complete ? "Logical DB file lengths" : "Known subtotal", bytes(summary.storage.known_footprint_bytes),
        `Main + WAL + SHM · logical lengths, not allocated disk space · ${summary.storage.total_complete ? "Complete" : "Partial coverage; unknown sizes are not zero"}`),
      tile("Problems & coverage", `${summary.problems.established} confirmed · ${summary.problems.unknown_or_stale} unknown/stale`,
        `Status unknowns: ${summary.services.unknown_or_stale} process · ${summary.databases.unknown_or_stale} DB. Separate axes: ${unknownHealth} app health unknown/stale · ${summary.databases.present_unverified} DBs present/unverified. Counts overlap; do not add.`)
    );
    const services = new Map(model.services.map((row) => [row.id, row.label]));
    byId("ops-services").replaceChildren(...model.services.map((row) => {
      const article = element("article", null, "ops-row ops-service");
      article.id = `ops-service-row-${row.id}`; article.tabIndex = -1;
      const identity = element("div", null, "ops-identity");
      identity.append(element("h3", row.label), element("p", row.role), element("span", row.unit, "mono"));
      const states = element("div", null, "ops-state-group");
      states.append(element("span", "Process"), badge(row.operational_state, "service"), element("span", "Application health"), badge(row.application_health, "application"));
      if(row.id==="network_metadata_projection") states.append(element("span",pendingLabel(model)));
      if(row.application_health_evidence?.reason==="backfilling_incomplete_coverage")
        states.append(element("span",healthReasons.backfilling_incomplete_coverage));
      if(phaseBNotice(row))states.append(element("span",phaseBNotice(row)));
      const process = element("div", null, "ops-process");
      process.append(field("PID", row.main_pid), field("Uptime", uptime(row.uptime_seconds)), field("Restarts", row.n_restarts));
      workloadLabels(row.id, model).forEach(label=>process.append(element("span",label)));
      article.append(identity, states, process, field("Expected", display(row.expected_mode)), details([
        ["Stable ID", row.id], ["ActiveState", row.active_state], ["SubState", row.sub_state],
        ["Started at", row.started_at_utc], ["Sampled at", row.sampled_at_utc], ["Reason", reason(row.reason_code)]
      ]));
      if (v2) {
        const evidence = row.application_health_evidence;
        article.append(details([["Health source", evidence.source], ["Health observed", evidence.observed_at],
          ["Health received", evidence.received_at], ["Evidence age / TTL", evidence.age == null ? "Unknown" : `${evidence.age}s / ${evidence.ttl}s`],
          ["Health reason", healthReasons[evidence.reason]]]));
      }
      return article;
    }));
    byId("ops-databases").replaceChildren(...model.databases.map((row) => {
      const article = element("article", null, "ops-row ops-database");
      article.id = `ops-db-row-${row.id}`; article.tabIndex = -1;
      const identity = element("div", null, "ops-identity");
      identity.append(element("h3", row.label), element("p", row.purpose), element("span", row.filename, "mono"));
      const state = element("div", null, "ops-state-group");
      state.append(databaseBadge(row,model), element("span", display(row.store_kind)), element("span", reason(row.reason_code)));
      const size = element("div", null, "ops-size");
      size.append(element("strong", bytes(row.total_footprint_bytes)), element("span", `DB ${bytes(row.main_file_bytes)} · WAL ${bytes(row.wal_bytes)} · SHM ${bytes(row.shm_bytes)}`));
      const owners = element("div", null, "ops-owners");
      owners.append(element("span", "Writer ownership", "ops-field-label"));
      row.writer_service_ids.forEach((id) => owners.append(element("span", services.get(id) || id, services.has(id) ? "" : "mono")));
      owners.append(element("span", row.writer_owner_component_ids.join(", "), "mono"));
      article.append(identity, state, size, owners, details([
        ["Stable DB ID", row.id], ["Expected mode", row.expected_mode], ["File presence", row.file_presence],
        ["Writer components", row.writer_owner_component_ids], ["Writer services", row.writer_service_ids],
        ["Reader services", row.reader_service_ids], ["Store kind", row.store_kind],
        ["Schema expected", row.schema_expected_version], ["Schema observed", row.schema_observed_version],
        ["Health evidence", row.health_evidence], ["Health checked", row.health_checked_at_utc],
        ["Sampled at", row.sampled_at_utc], ["Reason", reason(row.reason_code)]
      ]));
      if (v2) article.append(verificationView(row), details([["Verification source", row.store_verification.source],
        ["Check freshness", row.store_verification.freshness || "Unknown"], ["Last startup result", lastResult(row) || "No result"], ["Metadata source", row.metadata_evidence.source],
        ["Metadata age / TTL", row.metadata_evidence.age == null ? "Unknown" : `${row.metadata_evidence.age}s / ${row.metadata_evidence.ttl}s`],
        ["DELETE journal (not included in main + WAL + SHM)", bytes(row.journal_bytes)]]));
      return article;
    }));
    renderTopology(model);
    warning.hidden = model.partial_failures.length === 0;
    title.textContent = model.sample_status === "stale" ? "Stale data" : model.snapshot_state === "partial" ? "Partial data" : "Snapshot collected";
    const age = Math.max(0, Math.floor((Date.now() - Date.parse(model.sampling_completed_at_utc)) / 1000));
    updated.textContent = Number.isFinite(age) ? `Updated ${age} sec ago` : "Sample time unavailable";
  }
  let timer = null, inFlight = false, controller = null, disposed = false, last = null;
  let apiVersion = root.dataset.apiV4 === "/admin/api/v4/operations/db-services" ? 4 :
    root.dataset.apiV3 === "/admin/api/v3/operations/db-services" ? 3 :
    root.dataset.apiV2 === "/admin/api/v2/operations/db-services" ? 2 : 1;
  const checkScopes = {schema_version:"schema version",schema_signature:"schema structure",quick_check:"SQLite quick_check",
    foreign_key_check:"foreign key check",integrity_check:"full SQLite integrity_check"};
  const checkOwners = {portal_counter:"captive-portal.service",public_traffic:"captive-portal.service",visitor_registry:"captive-portal.service",
    visits:"captive-portal.service",observations:"captive-portal.service",current_state:"captive-portal.service",settings:"captive-portal.service",
    fingerprint_integration:"captive-portal.service",sensor_spool:"fingerprint-sensor.service",network_attribution:"fingerprint-sensor.service",
    network_metadata_projection:"network-metadata-projection.service",network_metadata:"network-metadata.service",
    network_service_intelligence:"network-service-recognition.service",traffic_projection:"traffic-projection.service",
    fingerprint_evidence:"fingerprint-evidence.service",fingerprint_classification:"fingerprint-classification.service",fingerprint_control_plane:"fingerprint-classification.service"};
  const permittedScopes = {visitor_registry:["schema_version","schema_signature","quick_check"],visits:["schema_version","schema_signature","quick_check","foreign_key_check"],
    observations:["schema_version","schema_signature"],current_state:["schema_version","schema_signature","quick_check"],traffic_projection:["schema_version","schema_signature","quick_check","foreign_key_check"],
    fingerprint_evidence:["schema_version","schema_signature"],fingerprint_integration:["schema_version","schema_signature"],network_metadata:["schema_version","schema_signature"],
    network_attribution:["schema_version","schema_signature","quick_check","foreign_key_check"],network_metadata_projection:["schema_version","schema_signature","quick_check","foreign_key_check"],
    network_service_intelligence:["schema_version","schema_signature","quick_check","foreign_key_check"],settings:["schema_version","schema_signature","quick_check","foreign_key_check"],sensor_spool:["schema_version","quick_check"]};
  function validVerification(row) {
    const v=row.store_verification;
    if (!v || typeof v!=="object" || Array.isArray(v)) return false;
    const extension=["last_result","binding"].filter(key=>Object.hasOwn(v,key));
    if(extension.length) {
      if(extension.length!==2 || ![null,"passed","failed","unknown","not_run"].includes(v.last_result) || !["matched","changed","unknown"].includes(v.binding)) return false;
      if(["passed","failed"].includes(v.status) && (v.last_result!==v.status || v.binding!=="matched")) return false;
      if(v.status==="stale" && (!["passed","failed","unknown"].includes(v.last_result) || v.reason==="store_changed" && v.binding==="matched")) return false;
      if(v.status==="unknown" && v.last_result!=="unknown") return false;
      if(v.last_result===null && v.binding!=="unknown") return false;
      if(v.status==="not_attested" && (Object.hasOwn(v,"reason") ? v.last_result!=="not_run" : v.last_result!==null || v.binding!=="unknown")) return false;
    }
    const fields=Object.keys(v).filter(key=>!extension.includes(key)).sort().join(",");
    if (fields==="as_of,scope,source,status") return v.status==="not_attested" && v.scope===null && v.as_of===null && v.source==="none";
    if (fields!=="as_of,freshness,reason,scope,source,status" || !["passed","failed","unknown","stale","not_attested","not_applicable"].includes(v.status) ||
        !["none",checkOwners[row.id]].includes(v.source) || !["current_report","stale","unknown","not_applicable"].includes(v.freshness) ||
        !["startup_check","startup_check_failed","startup_unavailable","check_not_run","store_changed","source_stale","configured_disabled"].includes(v.reason)) return false;
    if (v.as_of!==null && (typeof v.as_of!=="string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(v.as_of) ||
        !Number.isFinite(Date.parse(v.as_of)) || new Date(v.as_of).toISOString()!==v.as_of)) return false;
    if (v.scope!==null && (!Array.isArray(v.scope) || new Set(v.scope).size!==v.scope.length ||
        v.scope.some(s=>typeof s!=="string" || !(permittedScopes[row.id] || []).includes(s)) ||
        JSON.stringify(v.scope)!==JSON.stringify(Object.keys(checkScopes).filter(s=>v.scope.includes(s))))) return false;
    if (["passed","failed","stale"].includes(v.status) && (v.source==="none" || v.as_of===null)) return false;
    if (v.status==="passed") return !!v.scope?.length && v.freshness==="current_report" && v.reason==="startup_check";
    if (v.status==="failed") return v.freshness==="current_report" && v.reason==="startup_check_failed";
    if (v.status==="stale") return v.freshness==="stale" && ["source_stale","store_changed"].includes(v.reason);
    if (v.status==="not_applicable") return row.id==="settings" && row.expected_mode==="optional_disabled" && v.source==="none" &&
      v.scope===null && v.as_of===null && v.freshness==="not_applicable" && v.reason==="configured_disabled";
    if (v.status==="not_attested") return v.source==="none" && v.scope===null && v.as_of===null && v.freshness==="unknown" && v.reason==="check_not_run";
    return v.status==="unknown" && v.reason==="startup_unavailable";
  }
  function verificationView(row) {
    const v=row.store_verification, block=element("section",null,"ops-verification");
    const label={passed:"Startup check passed",failed:"Startup check failed",stale:"Previously checked · stale evidence",
      unknown:"Owner check evidence unavailable",not_attested:"No verification evidence",not_applicable:"Not applicable · Settings disabled"};
    const result=lastResult(row);
    block.append(element("strong",v.status==="stale" && ["passed","failed"].includes(result) ? `Last startup check ${result} · stale report` : label[v.status]));
    if (v.as_of) block.append(element("span",`Checked at ${v.as_of} · ${(v.scope || []).map(s=>checkScopes[s]).join(" + ") || "no completed successful scope reported"}`));
    block.append(element("small",v.status==="passed" ? "Historical owner startup result, not continuous integrity monitoring." :
      v.status==="stale" ? "Historical result retained; report freshness and current file/process binding are separate." : "File presence and application health are separate from this result."));
    if(Object.hasOwn(v,"binding")) block.append(element("small",`Current process/store binding: ${v.binding}.`));
    if (row.id==="network_metadata_projection" && v.source!=="none") block.append(element("small","Informational shared-admin self-report; not independently authenticated."));
    return block;
  }
  function validV2(model) {
    const states = new Set(["healthy","degraded","unavailable","unknown","stale"]);
    const sources={fingerprint_sensor:"sensor_native.v2",network_metadata_projection:"source_self_reported_shared_uid",
      fingerprint_evidence:"source_self_reported_shared_uid",network_metadata:"source_self_reported_shared_uid",network_service_recognition:"source_self_reported_shared_uid",
      fingerprint_classification:"source_self_reported_shared_uid",traffic_projection:"source_self_reported_shared_uid",fingerprint_suricata:"observed_via_sensor",portal_core:"portal_in_process"};
    const owners=["fingerprint_evidence","network_metadata","network_service_recognition","fingerprint_classification","traffic_projection"];
    const ownerReasons={source_ready:"healthy",backfilling_incomplete_coverage:"healthy",source_degraded:"degraded",source_lagging:"degraded",source_stale:"degraded",
      source_unavailable:"unavailable",capacity_limited:"unavailable",blocked_conflict:"unavailable",source_initializing:"unknown",source_stopping:"unknown",dependencies_unconfirmed:"unknown",
      projection_rebuilding:"degraded",projection_catching_up:"degraded",projection_stale:"degraded"};
    const coreReasons={core_composed:"healthy",core_unavailable:"unavailable",core_component_degraded:"degraded",authorization_degraded:"degraded",dependencies_unconfirmed:"unknown"};
    const proxyReasons={source_ready:"healthy",source_unavailable:"unavailable",dependencies_unconfirmed:"unknown"};
    const noSource=(e)=>e.state==="unknown" && e.reason==="report_unavailable" || e.state==="stale" && e.reason==="report_stale";
    const localValid=(row,e)=>!["portal_core","fingerprint_suricata"].includes(row.id) || (e.source==="none" ? noSource(e) :
      e.state==="stale" ? e.reason==="report_stale" : (row.id==="portal_core" ? coreReasons : proxyReasons)[e.reason]===e.state);
    const ownerValid=(row,e)=>!owners.includes(row.id) || (e.source==="none" ?
      (e.state==="unknown" && e.reason==="report_unavailable" || e.state==="stale" && e.reason==="report_stale") : (e.state==="stale" ? e.reason==="report_stale" :
      ownerReasons[e.reason]===e.state && (!["backfilling_incomplete_coverage","source_lagging","capacity_limited","blocked_conflict"].includes(e.reason) || row.id==="network_service_recognition") &&
      (e.reason!=="source_stale" || row.id==="network_metadata") &&
      (!["projection_rebuilding","projection_catching_up","projection_stale"].includes(e.reason) || row.id==="traffic_projection")));
    const keys = (value, expected) => value && typeof value === "object" && !Array.isArray(value) && Object.keys(value).sort().join(",") === expected;
    return model.services.every((row) => {
      const e = row.application_health_evidence;
      return keys(e, "age,observed_at,reason,received_at,source,state,ttl") && states.has(e.state) && e.state === row.application_health &&
        Object.hasOwn(healthReasons, e.reason) && ["none","sensor_native.v2","source_self_reported_shared_uid","observed_via_sensor","portal_in_process"].includes(e.source) &&
        Number.isInteger(e.ttl) && e.ttl > 0 && e.ttl <= 180 && (e.age === null || Number.isFinite(e.age) && e.age >= 0) &&
        (e.source==="none" || sources[row.id]===e.source) && ownerValid(row,e) && localValid(row,e) &&
        (Object.hasOwn(sources,row.id) || e.state === "unknown" && e.source === "none") &&
        (!["backfilling_incomplete_coverage","source_lagging","source_stale","projection_rebuilding","projection_catching_up","projection_stale",...Object.keys(coreReasons).filter(k=>k!=="dependencies_unconfirmed")].includes(e.reason) ||
          (owners.includes(row.id) || row.id==="portal_core" || row.id==="fingerprint_suricata") && e.source!=="none") &&
        (!["healthy","degraded","unavailable"].includes(e.state) || e.source !== "none" && Number.isFinite(e.age) && e.age <= e.ttl && typeof e.observed_at === "string" && typeof e.received_at === "string");
    }) && model.databases.every((row) => validVerification(row) &&
      keys(row.metadata_evidence,"age,source,state,ttl") && ["sensor_metadata","sampler_lstat","none"].includes(row.metadata_evidence.source) &&
      ["fresh","stale","unknown"].includes(row.metadata_evidence.state) &&
      (row.journal_bytes === null || row.id === "sensor_spool" && Number.isSafeInteger(row.journal_bytes) && row.journal_bytes >= 0));
  }
  function validV3(model) {
    const keys=(value,expected)=>value && typeof value==="object" && !Array.isArray(value) && Object.keys(value).sort().join(",")===expected;
    if(!keys(model,"api_version,databases,freshness_seconds,generated_at_utc,partial_failures,request_id,sample_status,sampling_completed_at_utc,sampling_started_at_utc,scope,services,snapshot_state,summary,topology,workload") ||
        !keys(model.workload,"network_metadata_projection") || !keys(model.workload.network_metadata_projection,"pending_attribution_count")) return false;
    const count=model.workload.network_metadata_projection.pending_attribution_count;
    return (count===null || Number.isSafeInteger(count) && count>=0) && validV2(model);
  }
  function validV4(model) {
    const keys=(value,expected)=>value && typeof value==="object" && !Array.isArray(value) && Object.keys(value).sort().join(",")===expected;
    const bounded=value=>value===null || Number.isSafeInteger(value) && value>=0;
    if(!keys(model.workload,"fingerprint_sensor,network_metadata_projection,network_service_recognition") ||
        !keys(model.workload.fingerprint_sensor,"oldest_spool_age_seconds,spool_bytes,spool_pending_rows") ||
        !keys(model.workload.network_service_recognition,"feed_backlog_entries")) return false;
    const s=model.workload.fingerprint_sensor, values=[s.spool_pending_rows,s.spool_bytes,s.oldest_spool_age_seconds];
    if(!values.every(bounded) || !bounded(model.workload.network_service_recognition.feed_backlog_entries)) return false;
    if(!values.every(value=>value===null) && (s.spool_pending_rows===null || s.spool_bytes===null ||
        (s.spool_pending_rows===0 ? s.oldest_spool_age_seconds!==null : s.oldest_spool_age_seconds===null))) return false;
    return validV3({...model,api_version:"admin.operations.db-services.v3",
      workload:{network_metadata_projection:model.workload.network_metadata_projection}});
  }
  function schedule() {
    if (timer !== null) clearTimeout(timer);
    timer = null;
    if (!disposed && !document.hidden) timer = setTimeout(load, 15000);
  }
  async function fetchSnapshot(url) {
    return await fetch(url, {credentials: "same-origin", cache: "no-store", signal: controller.signal});
  }
  async function load() {
    if (disposed || inFlight || document.hidden) return;
    inFlight = true;
    refresh.disabled = true;
    controller = new AbortController();
    try {
      const url=()=>apiVersion===4 ? root.dataset.apiV4 : apiVersion===3 ? root.dataset.apiV3 : apiVersion===2 ? root.dataset.apiV2 : root.dataset.apiBase;
      let response = await fetchSnapshot(url());
      while (apiVersion>1 && response.status === 404) {
        // Sticky negotiation ONLY on unsupported version. Never hide faults.
        apiVersion-=1;
        response = await fetchSnapshot(url());
      }
      const model = await response.json();
      if (disposed) return;
      if (!response.ok) {
        if (response.status === 503 && model.error?.code === "snapshot_pending") {
          title.textContent = "Collecting operational snapshot…";
        } else { title.textContent = "Unavailable"; }
        return;
      }
      if (model.api_version !== `admin.operations.db-services.v${apiVersion}` || model.scope !== "global" || !model.summary ||
          !Array.isArray(model.services) || model.services.length !== 9 || !Array.isArray(model.databases) || model.databases.length !== 17 ||
          !Array.isArray(model.partial_failures) || model.partial_failures.length > 32 || !validTopology(model) ||
          (apiVersion===4 ? !validV4(model) : apiVersion===3 ? !validV3(model) : apiVersion===2 && !validV2(model))) throw new Error("invalid_snapshot");
      render(model);
      last = model;
    } catch (_error) {
      if (!disposed) title.textContent = "Unavailable";
    } finally {
      inFlight = false;
      refresh.disabled = false;
      controller = null;
      if (last && (title.textContent === "Unavailable" || title.textContent === "Collecting operational snapshot…")) {
        const age = Math.max(0, Math.floor((Date.now() - Date.parse(last.sampling_completed_at_utc)) / 1000));
        const failedTitle=title.textContent;
        if(last.api_version==="admin.operations.db-services.v4") render({...last,workload:{
          network_metadata_projection:last.workload.network_metadata_projection,
          fingerprint_sensor:{spool_pending_rows:null,spool_bytes:null,oldest_spool_age_seconds:null},
          network_service_recognition:{feed_backlog_entries:null}}});
        if(age>90) render({...last,sample_status:"stale"});
        root.dataset.outdated = age > 90 ? "true" : "false";
        title.textContent=age>90 ? "Stale data" : failedTitle;
        updated.textContent = `Refresh failed · previous snapshot (${Number.isFinite(age) ? age + " sec old" : "time unavailable"})`;
      }
      schedule();
    }
  }
  refresh.addEventListener("click", load);
  window.addEventListener("resize", scheduleGeometry);
  board.addEventListener("keydown", (event) => { if (event.key === "Escape") { selected = null; emphasize(null); } });
  document.addEventListener("visibilitychange", () => {
    if (timer !== null) clearTimeout(timer);
    timer = null;
    if (!document.hidden) load();
  });
  window.addEventListener("pagehide", () => { disposed = true; if (timer !== null) clearTimeout(timer); if (geometryFrame !== null) window.cancelAnimationFrame(geometryFrame); controller?.abort(); });
  load();
})();
