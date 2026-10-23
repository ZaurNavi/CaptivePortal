/* Visit-owned NI03 results. No raw projection reads or rolling-window fallback. */
(function () {
  "use strict";
  if (typeof document === "undefined") return;
  const page = document.getElementById("admin-page");
  if (!page || !["device", "visits"].includes(page.dataset.page)) return;
  const site = page.dataset.siteId;
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
  const labels = {dns: "DNS", tls: "TLS", quic: "QUIC"};
  const states = new Set(["not_materialized", "pending", "partial", "active", "unavailable", "finalized"]);
  const reasons = new Set(["not_materialized", "visit_revision_changed", "identity_unconfirmed", "source_unavailable",
    "no_confirmed_observation", "late_unresolved", "bounded_source", "grace_elapsed_partial"]);
  const cards = new Map();
  let stopped = false, inflight = 0, timer = null;
  function element(tag, text, cls) {
    const value = document.createElement(tag);
    if (text !== undefined) value.textContent = text;
    if (cls) value.className = cls;
    return value;
  }
  function exact(value, fields) {
    return value !== null && typeof value === "object" && !Array.isArray(value) &&
      Object.keys(value).length === fields.length && fields.every((key) => Object.hasOwn(value, key));
  }
  function stamp(value) {
    if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3}(?:\d{3})?)?Z$/.test(value)) throw new Error("shape");
    const time = Date.parse(value);
    if (!Number.isFinite(time) || new Date(time).toISOString().slice(0, 19) !== value.slice(0, 19)) throw new Error("shape");
    return value.slice(0, 19) + "." + (value.slice(20, -1) || "").padEnd(6, "0") + "Z";
  }
  function validate(payload, card) {
    if (!exact(payload, ["api_version", "request_id", "site_id", "result", "page"]) ||
        payload.api_version !== "admin.visit.protocol-intelligence.v1" || payload.site_id !== site ||
        !uuid.test(payload.request_id) || payload.page !== null) throw new Error("shape");
    const value = payload.result;
    if (!exact(value, ["type", "schema_version", "site_id", "device_id", "visit_id", "visit_status", "started_at", "closed_at",
      "summary_state", "protocols", "last_protocol_observation", "evaluated_at", "source_coverage", "attribution_coverage",
      "finalized_at", "partial_reason", "historical_completeness_claimed"]) ||
        value.type !== "VisitProtocolSummaryV1" || value.schema_version !== 1 || value.site_id !== site ||
        value.device_id !== card.device || value.visit_id !== card.visit || !["open", "closed"].includes(value.visit_status) ||
        !states.has(value.summary_state) || !reasons.has(value.partial_reason) || value.historical_completeness_claimed !== false ||
        !["unknown", "bounded_partial", "unavailable"].includes(value.source_coverage) ||
        !["unknown", "current_available", "limited"].includes(value.attribution_coverage)) throw new Error("shape");
    const lower = stamp(value.started_at);
    const closed = value.closed_at === null ? null : stamp(value.closed_at);
    const evaluated = value.evaluated_at === null ? null : stamp(value.evaluated_at);
    if ((value.visit_status === "closed") !== (closed !== null) || (closed && closed < lower) ||
        (value.summary_state === "finalized") !== (value.finalized_at !== null)) throw new Error("shape");
    if (value.finalized_at !== null && (!closed || stamp(value.finalized_at) < closed)) throw new Error("shape");
    if (!Array.isArray(value.protocols) || value.protocols.length > 3) throw new Error("shape");
    const seen = new Set();
    for (const item of value.protocols) {
      if (!exact(item, ["protocol_id", "last_observed_at"]) || !Object.hasOwn(labels, item.protocol_id) || seen.has(item.protocol_id)) throw new Error("shape");
      const at = stamp(item.last_observed_at), upper = closed || evaluated;
      if (!upper || at < lower || at >= upper || !evaluated || at >= evaluated) throw new Error("shape");
      seen.add(item.protocol_id);
    }
    const ordered = [...value.protocols].sort((a, b) => b.last_observed_at.localeCompare(a.last_observed_at) || a.protocol_id.localeCompare(b.protocol_id));
    if (JSON.stringify(value.last_protocol_observation) !== JSON.stringify(ordered[0] || null)) throw new Error("shape");
    return value;
  }
  function visible(card) {
    if (document.hidden || !card.root.isConnected) return false;
    const bounds = card.root.getBoundingClientRect();
    return bounds.bottom >= 0 && bounds.top <= window.innerHeight;
  }
  function render(card, value) {
    updateVisitCard(card, value);
    card.status.textContent = value.summary_state.replaceAll("_", " ") + " — " + value.partial_reason.replaceAll("_", " ");
    card.evaluated.textContent = value.evaluated_at ? "Last protocol evaluation: " + value.evaluated_at : "Not yet materialized";
    card.list.replaceChildren();
    for (const fact of value.protocols) {
      const item = element("li"), time = element("time", fact.last_observed_at);
      time.dateTime = fact.last_observed_at;
      item.append(element("strong", labels[fact.protocol_id] + " "), time);
      card.list.append(item);
    }
    if (!value.protocols.length) card.list.append(element("li", "No confirmed protocol observation saved for this visit."));
    card.root.dataset.visitStatus = value.visit_status;
    card.closed = value.visit_status === "closed";
  }
  function updateVisitCard(card, value) {
    const article = card.root.parentElement;
    if (!article || !article.classList.contains("data-row")) return;
    const heading = article.querySelector(".data-row-header strong");
    if (heading) heading.textContent = value.visit_status;
    for (const label of article.querySelectorAll(".detail-list dt")) {
      const field = label.nextElementSibling;
      if (!field || field.tagName !== "DD") continue;
      if (label.textContent === "Closed") field.textContent = value.closed_at || "—";
      if (label.textContent === "Duration (s)" && value.closed_at !== null) {
        field.textContent = String(Math.floor((Date.parse(value.closed_at) - Date.parse(value.started_at)) / 1000));
      }
    }
  }
  function validateServices(payload, card) {
    if (!exact(payload, ["api_version", "request_id", "site_id", "result", "page"]) ||
        payload.api_version !== "admin.visit.recognized-services.v1" || payload.site_id !== site || !uuid.test(payload.request_id) || payload.page !== null) throw new Error("shape");
    const v = payload.result;
    if (!exact(v, ["type", "schema_version", "site_id", "device_id", "visit_id", "visit_status", "started_at", "closed_at", "history_state",
      "partial_reason", "evaluated_at", "services", "truncated", "historical_completeness_claimed"]) ||
        v.type !== "VisitServiceHistoryV1" || v.schema_version !== 1 || v.site_id !== site || v.device_id !== card.device || v.visit_id !== card.visit ||
        !["open", "closed"].includes(v.visit_status) || !["processing", "confirmed", "incomplete", "unavailable", "no_confirmed_observation"].includes(v.history_state) ||
        !["not_materialized", "history_expired", "source_unavailable", "backfill_limited", "visit_revision_changed", "lineage_pending"].includes(v.partial_reason) ||
        typeof v.truncated !== "boolean" || v.historical_completeness_claimed !== false || !Array.isArray(v.services) || v.services.length > 50) throw new Error("shape");
    const lower = stamp(v.started_at), upper = v.closed_at === null ? null : stamp(v.closed_at);
    if ((v.visit_status === "closed") !== (upper !== null) || upper && upper < lower) throw new Error("shape");
    if (v.evaluated_at !== null) stamp(v.evaluated_at);
    const seen = new Set();
    for (const service of v.services) {
      if (!exact(service, ["service_id", "display_name", "organization_id", "organization_display_name", "first_observed_at", "last_observed_at",
        "distinct_observation_count", "status", "finalized_at", "taxonomy", "ruleset", "provenance"]) ||
          !["processing", "confirmed", "incomplete"].includes(service.status) || service.provenance !== "materialized_ni04_strong_observation" ||
          !Number.isSafeInteger(service.distinct_observation_count) || service.distinct_observation_count <= 0 || seen.has(service.service_id)) throw new Error("shape");
      for (const key of ["service_id", "display_name", "organization_id", "organization_display_name"]) {
        if (typeof service[key] !== "string" || !service[key].length || service[key].length > 128 || /[\u0000-\u001f]/.test(service[key])) throw new Error("shape");
      }
      for (const lineage of [service.taxonomy, service.ruleset]) {
        if (!exact(lineage, ["id", "version", "digest_sha256"]) || typeof lineage.id !== "string" || lineage.id.length > 128 ||
            !Number.isSafeInteger(lineage.version) || lineage.version <= 0 || !/^[0-9a-f]{64}$/.test(lineage.digest_sha256)) throw new Error("shape");
      }
      const first = stamp(service.first_observed_at), last = stamp(service.last_observed_at);
      if (first < lower || last < first || upper && last >= upper) throw new Error("shape");
      if (service.finalized_at !== null) stamp(service.finalized_at);
      seen.add(service.service_id);
    }
    return v;
  }
  async function refreshServices(card, controller) {
    try {
      const response = await fetch(`/admin/api/v2/sites/${encodeURIComponent(site)}/devices/${card.device}/visits/${card.visit}/recognized-services`, {
        method: "GET", credentials: "same-origin", cache: "no-store", signal: controller.signal, headers: {Accept: "application/json"}
      });
      if (!response.ok) throw new Error("unavailable");
      const value = validateServices(await response.json(), card);
      if (stopped || !card.root.isConnected || controller.signal.aborted) return;
      updateVisitCard(card, value);
      card.servicesStatus.textContent = value.history_state.replaceAll("_", " ") + " — " + value.partial_reason.replaceAll("_", " ") +
        (value.truncated ? " (first 50 services)" : "");
      card.servicesList.replaceChildren();
      for (const service of value.services) {
        const item = element("li");
        item.append(element("strong", service.display_name + " · " + service.organization_display_name),
          element("p", `${service.first_observed_at} → ${service.last_observed_at}; ${service.distinct_observation_count} distinct confirmed observations; ${service.status}`),
          element("small", `NI04 strong evidence · taxonomy ${service.taxonomy.version} · ruleset ${service.ruleset.version}`));
        card.servicesList.append(item);
      }
      if (!value.services.length) card.servicesList.append(element("li", "No confirmed service observation saved. This does not mean the service was not used."));
      card.servicesEvaluated.textContent = value.evaluated_at ? "Last service materialization: " + value.evaluated_at : "Not yet materialized";
      if (value.visit_status === "closed") { card.closed = true; card.root.dataset.visitStatus = "closed"; }
    } catch (_) {
      if (!stopped && card.root.isConnected) {
        card.servicesList.replaceChildren();card.servicesStatus.textContent = "Saved service results temporarily unavailable.";
      }
    }
  }
  async function refresh(card) {
    card.busy = true; card.attempted = true; inflight += 1; card.lastStart = Date.now();
    const controller = new AbortController(); card.controller = controller;
    const timeout = window.setTimeout(() => controller.abort(), 5000);
    try {
      try {
      const response = await fetch(`/admin/api/v2/sites/${encodeURIComponent(site)}/devices/${card.device}/visits/${card.visit}/protocol-intelligence`, {
        method: "GET", credentials: "same-origin", cache: "no-store", signal: controller.signal, headers: {Accept: "application/json"}
      });
      if ([401, 403, 404].includes(response.status)) card.terminal = true;
      if (!response.ok) throw new Error("unavailable");
      const value = validate(await response.json(), card);
      if (!stopped && card.root.isConnected && !controller.signal.aborted) {
        render(card, value); card.loaded = true; card.failures = 0;
      }
      } catch (_) {
      if (!stopped && card.root.isConnected) {
        card.failures += 1; card.list.replaceChildren();
        card.status.textContent = "Saved visit protocol results temporarily unavailable.";
      }
      }
      // Independent failure isolation; never a Device-wide NI04 fallback.
      if (!stopped && !card.terminal && !controller.signal.aborted) await refreshServices(card, controller);
    } finally {
      window.clearTimeout(timeout); card.controller = null; card.busy = false; inflight -= 1;
    }
  }
  function discover() {
    for (const root of page.querySelectorAll(".visit-network-results")) {
      if (cards.has(root)) continue;
      const heading = element("h3", "Network protocols"), status = element("p", "Waiting for visibility…", "state-panel");
      status.setAttribute("role", "status");
      const list = element("ul", undefined, "protocol-chip-list");
      const evaluated = element("small", "Not yet materialized");
      const servicesHeading = element("h3", "Recognized services");
      const servicesStatus = element("p", "Waiting for visibility…", "state-panel");
      servicesStatus.setAttribute("role", "status");
      const servicesList = element("ul"), servicesEvaluated = element("small", "Not yet materialized");
      const button = element("button", "Refresh visit results", "button button-secondary");
      button.type = "button";
      const protocolSection = element("section", undefined, "card visit-network-section");
      const serviceSection = element("section", undefined, "card visit-network-section");
      protocolSection.append(heading, status, list, evaluated);
      serviceSection.append(servicesHeading, servicesStatus, servicesList, servicesEvaluated);
      root.append(protocolSection, serviceSection, button);
      const card = {root, status, list, evaluated, servicesStatus, servicesList, servicesEvaluated, visit: root.dataset.visitId, device: root.dataset.deviceId,
        closed: root.dataset.visitStatus === "closed", busy: false, loaded: false, attempted: false, failures: 0, lastStart: null, terminal: false};
      cards.set(root, card);
      if (!uuid.test(card.visit) || !uuid.test(card.device)) {
        status.textContent = "Visit identity binding pending."; card.terminal = true; button.disabled = true;
        servicesStatus.textContent = "Visit identity binding pending.";
      }
      button.addEventListener("click", () => { if (visible(card) && !card.busy && !card.terminal && inflight < 2) refresh(card); });
    }
    for (const [root, card] of cards) if (!root.isConnected) {
      if (card.controller) card.controller.abort();
      cards.delete(root);
    }
  }
  function tick() {
    if (stopped) return;
    discover();
    const now = Date.now();
    const ordered = [...cards.values()].sort((a, b) => (a.lastStart || 0) - (b.lastStart || 0));
    for (const card of ordered) {
      const delay = Math.min(300000, 30000 * 2 ** Math.min(card.failures, 4));
      if (inflight >= 2) break;
      if (!card.busy && !card.terminal && (!card.closed || !card.attempted) && visible(card) &&
          (card.lastStart === null || now - card.lastStart >= delay)) refresh(card);
    }
    timer = window.setTimeout(tick, 1000);
  }
  window.addEventListener("pagehide", () => {
    stopped = true; window.clearTimeout(timer); observer.disconnect();
    for (const card of cards.values()) if (card.controller) card.controller.abort();
    cards.clear();
  });
  const observer = new MutationObserver(discover);
  observer.observe(page, {childList: true, subtree: true});
  tick();
}());
