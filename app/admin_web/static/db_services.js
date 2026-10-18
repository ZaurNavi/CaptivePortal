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
  function field(label, value, mono = false) {
    const node = element("div", null, "ops-field");
    node.append(element("span", label, "ops-field-label"), element("span", value == null ? "—" : value, mono ? "mono" : ""));
    return node;
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
  let topology = null, svg = null, selected = null, geometryFrame = null;
  const nodeElements = new Map(), laneElements = new Map(), edgeElements = new Map();
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
    });
    nodeElements.forEach((node, identity) => {
      node.classList.toggle("ops-emphasized", related.has(identity));
      node.classList.toggle("ops-subdued", !!id && !related.has(identity));
      node.setAttribute("aria-pressed", String(identity === selected));
    });
    const node = topology.nodes.find((item) => item.id === id);
    byId("ops-flow-context").textContent = node ? `${node.label} · Structural relationships only · ${topology.edges.filter((edge) => edge.from_node_id === id || edge.to_node_id === id).map((edge) => `${relationLabels[edge.relation]}: ${topology.nodes.find((item) => item.id === (edge.from_node_id === id ? edge.to_node_id : edge.from_node_id)).label}`).join("; ")}` : "Select a node to inspect its structural relationships.";
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
    const cross = topology.edges.filter((edge) => {
      const from = topology.nodes.find((node) => node.id === edge.from_node_id);
      return from.group !== topology.nodes.find((node) => node.id === edge.to_node_id).group;
    });
    const rect = (node) => {
      const box = node.getBoundingClientRect();
      return {left:box.left-bounds.left, right:box.right-bounds.left, top:box.top-bounds.top, bottom:box.bottom-bounds.top, cy:(box.top+box.bottom)/2-bounds.top};
    };
    topology.edges.forEach((edge, index) => {
      const from = topology.nodes.find((node) => node.id === edge.from_node_id);
      const to = topology.nodes.find((node) => node.id === edge.to_node_id);
      const a = rect(nodeElements.get(from.id)), b = rect(nodeElements.get(to.id));
      const sourceLane = rect(laneElements.get(from.group)), targetLane = rect(laneElements.get(to.group));
      let points;
      if (from.group !== to.group) {
        const rail = bounds.width - (mobile ? 7 : 12) - cross.indexOf(edge)*(mobile ? 1.6 : 3);
        const sourceY = sourceLane.bottom - 10 - index%4*2;
        const targetY = targetLane.top + 53 + index%4*2;
        const exitX = a.right+5, enterX = b.left-5;
        points = [[a.right,a.cy],[exitX,a.cy],[exitX,sourceY],[rail,sourceY],[rail,targetY],[enterX,targetY],[enterX,b.cy],[b.left,b.cy]];
      } else if (mobile) {
        const rail = sourceLane.right-8-index%4*2;
        points = [[a.right,a.cy],[rail,a.cy],[rail,b.cy],[b.right,b.cy]];
      } else if (Number(nodeElements.get(to.id).dataset.stage) === Number(nodeElements.get(from.id).dataset.stage)+1) {
        const middle = (a.right+b.left)/2;
        points = [[a.right,a.cy],[middle,a.cy],[middle,b.cy],[b.left,b.cy]];
      } else {
        const railY = sourceLane.bottom-10-index%4*2;
        points = [[a.right,a.cy],[a.right+5,a.cy],[a.right+5,railY],[b.left-5,railY],[b.left-5,b.cy],[b.left,b.cy]];
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
    const defs = svgElement("defs", {}), marker = svgElement("marker", {id:"ops-arrow", viewBox:"0 0 8 8", refX:"7", refY:"4", markerWidth:"5", markerHeight:"5", orient:"auto-start-reverse"});
    marker.append(svgElement("path", {d:"M 0 0 L 8 4 L 0 8 z", class:"ops-arrowhead"}));
    defs.append(marker); svg.append(defs);
    board.replaceChildren(svg);
    lanes.forEach(([group,label,stages]) => {
      const lane = element("section", null, "ops-flow-lane");
      lane.dataset.group = group;
      const heading = element("h3", label, "ops-lane-title");
      heading.id = `ops-lane-${group}`; lane.setAttribute("aria-labelledby", heading.id);
      const columns = element("div", null, "ops-flow-stages");
      columns.style.setProperty("--ops-stages", stages.length);
      stages.forEach(([stageLabel,...identities], stageIndex) => {
        const stage = element("div", null, "ops-flow-stage");
        stage.append(element("h4", stageLabel, "ops-stage-title"));
        identities.forEach((identity) => {
          const item = nodes.get(identity), node = element("button", null, "ops-flow-node");
          node.type = "button"; node.dataset.nodeId = item.id; node.dataset.nodeType = item.node_type;
          node.dataset.stage = String(stageIndex);
          node.setAttribute("aria-pressed", "false");
          node.append(element("span", display(item.node_type), "ops-node-type"), element("strong", item.label));
          if (item.node_type === "service") {
            const row = serviceRows.get(item.catalog_ref);
            node.append(badge(row.operational_state,"service"), element("small", `App: ${display(row.application_health)}`));
          } else if (item.node_type === "database") {
            const row = dbRows.get(item.catalog_ref);
            node.append(element("small", row.filename, "mono"), badge(row.operational_state,"database"), element("small", bytes(row.total_footprint_bytes)));
          }
          node.addEventListener("mouseenter", () => emphasize(item.id));
          node.addEventListener("mouseleave", () => emphasize(selected));
          node.addEventListener("focus", () => emphasize(item.id));
          node.addEventListener("blur", () => emphasize(selected));
          node.addEventListener("click", () => activateNode(item));
          stage.append(node); nodeElements.set(identity,node);
        });
        columns.append(stage);
      });
      lane.append(heading, columns); board.append(lane); laneElements.set(group,lane);
    });
    topology.edges.forEach((edge) => {
      const path = svgElement("path", {class:`ops-flow-edge ops-relation-${edge.relation}`, "marker-end":"url(#ops-arrow)"});
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
    const summary = model.summary;
    byId("ops-summary").replaceChildren(
      tile("Services", summary.services.expected_running ? `${summary.services.running} / ${summary.services.expected_running} running` : "0 expected to run",
        `${summary.services.registered} registered · ${summary.services.unknown_or_stale} unknown/stale`),
      tile("Databases", `${summary.databases.available} / ${summary.databases.registered} verified`,
        `${summary.databases.present_unverified} present · unverified; ${summary.databases.disabled} disabled; ${summary.databases.not_provisioned} not provisioned; ${summary.databases.unknown_or_stale} unknown/stale`),
      tile(summary.storage.total_complete ? "DB storage footprint" : "Known subtotal", bytes(summary.storage.known_footprint_bytes),
        summary.storage.total_complete ? "File lengths · Complete" : "File lengths · Partial coverage"),
      tile("Problems", summary.problems.established, `${summary.problems.unknown_or_stale} unknown/stale`)
    );
    const services = new Map(model.services.map((row) => [row.id, row.label]));
    byId("ops-services").replaceChildren(...model.services.map((row) => {
      const article = element("article", null, "ops-row ops-service");
      article.id = `ops-service-row-${row.id}`; article.tabIndex = -1;
      const identity = element("div", null, "ops-identity");
      identity.append(element("h3", row.label), element("p", row.role), element("span", row.unit, "mono"));
      const states = element("div", null, "ops-state-group");
      states.append(badge(row.operational_state, "service"), element("span", "Application health"), badge(row.application_health, "application"));
      const process = element("div", null, "ops-process");
      process.append(field("PID", row.main_pid), field("Uptime", uptime(row.uptime_seconds)), field("Restarts", row.n_restarts));
      article.append(identity, states, process, field("Expected", display(row.expected_mode)), details([
        ["Stable ID", row.id], ["ActiveState", row.active_state], ["SubState", row.sub_state],
        ["Started at", row.started_at_utc], ["Sampled at", row.sampled_at_utc], ["Reason", row.reason_code]
      ]));
      return article;
    }));
    byId("ops-databases").replaceChildren(...model.databases.map((row) => {
      const article = element("article", null, "ops-row ops-database");
      article.id = `ops-db-row-${row.id}`; article.tabIndex = -1;
      const identity = element("div", null, "ops-identity");
      identity.append(element("h3", row.label), element("p", row.purpose), element("span", row.filename, "mono"));
      const state = element("div", null, "ops-state-group");
      state.append(badge(row.operational_state, "database"), element("span", display(row.store_kind)));
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
        ["Sampled at", row.sampled_at_utc], ["Reason", row.reason_code]
      ]));
      return article;
    }));
    renderTopology(model);
    warning.hidden = model.partial_failures.length === 0;
    title.textContent = model.sample_status === "stale" ? "Stale data" : model.snapshot_state === "partial" ? "Partial data" : "Available";
    const age = Math.max(0, Math.floor((Date.now() - Date.parse(model.sampling_completed_at_utc)) / 1000));
    updated.textContent = Number.isFinite(age) ? `Updated ${age} sec ago` : "Sample time unavailable";
  }
  let timer = null, inFlight = false, controller = null, disposed = false, last = null;
  function schedule() {
    if (timer !== null) clearTimeout(timer);
    timer = null;
    if (!disposed && !document.hidden) timer = setTimeout(load, 15000);
  }
  async function load() {
    if (disposed || inFlight || document.hidden) return;
    inFlight = true;
    refresh.disabled = true;
    controller = new AbortController();
    try {
      const response = await fetch(root.dataset.apiBase, {credentials: "same-origin", cache: "no-store", signal: controller.signal});
      const model = await response.json();
      if (disposed) return;
      if (!response.ok) {
        if (response.status === 503 && model.error?.code === "snapshot_pending") {
          title.textContent = "Collecting operational snapshot…";
        } else { title.textContent = "Unavailable"; }
        return;
      }
      if (model.api_version !== "admin.operations.db-services.v1" || model.scope !== "global" || !model.summary ||
          !Array.isArray(model.services) || model.services.length !== 9 || !Array.isArray(model.databases) || model.databases.length !== 17 ||
          !Array.isArray(model.partial_failures) || !validTopology(model)) throw new Error("invalid_snapshot");
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
        root.dataset.outdated = age > 90 ? "true" : "false";
        if (age > 90 && title.textContent === "Unavailable") title.textContent = "Stale data";
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
