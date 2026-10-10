/* NI-03: independent, privacy-safe Device Card read coordinator. */
(function () {
  "use strict";
  const section = document.getElementById("device-protocol-intelligence");
  const page = document.getElementById("admin-page");
  if (!section || !page || page.dataset.page !== "device") return;
  const site = page.dataset.siteId, device = page.dataset.deviceId;
  const content = document.getElementById("device-protocol-content");
  const title = document.getElementById("device-protocol-state-title");
  const message = document.getElementById("device-protocol-state-message");
  const protocolLabels = {dns: "DNS", tls: "TLS", quic: "QUIC"};
  const rank = {dns: 0, tls: 1, quic: 2};
  const coverageLabels = {usable: "Available", degraded: "Degraded", unavailable: "Unavailable", unknown: "Unknown"};
  const freshnessLabels = {fresh: "Fresh", recent: "Recent", stale: "Stale", unavailable: "Unavailable"};
  let stopped = false, terminal = false, active = null, pending = false;
  let timer = null, expiryTimer = null, lastStart = null, failures = 0, lastGood = null;

  function exact(value, fields) {
    return value !== null && typeof value === "object" && !Array.isArray(value) &&
      Object.keys(value).length === fields.length && fields.every((key) => Object.hasOwn(value, key));
  }
  function utc(value) {
    if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$/.test(value)) throw new Error("shape");
    const short = value.slice(0, 23) + "Z", time = Date.parse(short);
    if (!Number.isFinite(time) || new Date(time).toISOString() !== short) throw new Error("shape");
    return time;
  }
  function validate(payload) {
    if (!exact(payload, ["api_version", "request_id", "site_id", "result", "page"]) ||
        payload.api_version !== "admin.device.protocol-intelligence.v1" || payload.site_id !== site || payload.page !== null ||
        typeof payload.request_id !== "string" || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(payload.request_id)) throw new Error("shape");
    const v = payload.result;
    if (!exact(v, ["schema_version", "site_id", "device_id", "evaluated_at_utc", "window", "availability_state", "evidence_state", "identity_binding_state", "recent_protocols", "last_protocol_observation", "freshness_state", "coverage"]) ||
        v.schema_version !== 1 || v.site_id !== site || v.device_id !== device ||
        !["usable", "degraded"].includes(v.availability_state) ||
        !["present", "empty", "identity_pending"].includes(v.evidence_state) ||
        !["authoritative", "pending", "unavailable", "absent"].includes(v.identity_binding_state) ||
        !Object.hasOwn(freshnessLabels, v.freshness_state)) throw new Error("shape");
    const at = utc(v.evaluated_at_utc), w = v.window, c = v.coverage;
    if (!exact(w, ["from_utc", "to_utc", "duration_seconds", "recent_from_utc", "recent_duration_seconds"]) ||
        w.to_utc !== v.evaluated_at_utc || w.duration_seconds !== 86400 || w.recent_duration_seconds !== 3600 ||
        utc(w.from_utc) !== at - 86400000 || utc(w.recent_from_utc) !== at - 3600000 ||
        w.from_utc.slice(23) !== v.evaluated_at_utc.slice(23) || w.recent_from_utc.slice(23) !== v.evaluated_at_utc.slice(23) ||
        !exact(c, ["scope", "source_state", "attribution_state", "projection_state", "historical_window_completeness_claimed"]) ||
        c.scope !== "current_pipeline" || c.historical_window_completeness_claimed !== false ||
        !Object.hasOwn(coverageLabels, c.source_state) || !Object.hasOwn(coverageLabels, c.attribution_state) ||
        v.availability_state !== (c.projection_state === "usable" && v.identity_binding_state === "authoritative" ? "usable" : "degraded")) throw new Error("shape");
    if (!["usable/usable/usable", "degraded/usable/usable", "degraded/usable/degraded", "degraded/unavailable/unknown",
      "degraded/degraded/degraded", "degraded/unknown/unknown"].includes(
        `${c.projection_state}/${c.source_state}/${c.attribution_state}`)) throw new Error("shape");
    const seen = new Set();
    let previous = null;
    if (!Array.isArray(v.recent_protocols) || v.recent_protocols.length > 3) throw new Error("shape");
    function protocol(item, field) {
      if (!exact(item, ["protocol_id", "display_label", field]) || !Object.hasOwn(protocolLabels, item.protocol_id) ||
          item.display_label !== protocolLabels[item.protocol_id]) throw new Error("shape");
      utc(item[field]);
    }
    for (const item of v.recent_protocols) {
      protocol(item, "last_observed_at");
      if (seen.has(item.protocol_id) || item.last_observed_at < w.recent_from_utc || item.last_observed_at >= w.to_utc ||
          (previous && (previous.last_observed_at < item.last_observed_at ||
            (previous.last_observed_at === item.last_observed_at && rank[previous.protocol_id] >= rank[item.protocol_id])))) throw new Error("shape");
      seen.add(item.protocol_id); previous = item;
    }
    const last = v.last_protocol_observation;
    if (last !== null) {
      protocol(last, "observed_at");
      if (last.observed_at < w.from_utc || last.observed_at >= w.to_utc || v.evidence_state !== "present" || v.freshness_state === "unavailable") throw new Error("shape");
      if (last.observed_at >= w.recent_from_utc) {
        const first = v.recent_protocols[0];
        if (!first || first.protocol_id !== last.protocol_id || first.last_observed_at !== last.observed_at) throw new Error("shape");
      } else if (v.recent_protocols.length) throw new Error("shape");
    } else if (v.recent_protocols.length || v.evidence_state === "present" || v.freshness_state !== "unavailable") throw new Error("shape");
    if ((v.identity_binding_state === "authoritative") !== (v.evidence_state !== "identity_pending")) throw new Error("shape");
    return v;
  }
  function state(heading, detail) { title.textContent = heading; message.textContent = detail; }
  function field(label, value) {
    const card = document.createElement("div"), name = document.createElement("strong"), text = document.createElement("p");
    card.className = "section-card"; name.textContent = label; text.textContent = value;
    card.append(name, text); return card;
  }
  function render(v) {
    const recent = v.recent_protocols.map((p) => p.display_label + " · " + p.last_observed_at).join("; ") || "—";
    const last = v.last_protocol_observation;
    content.replaceChildren(
      field("Recent Protocols", recent),
      field("Last Protocol Observation", last ? last.display_label + " · " + last.observed_at : "—"),
      field("Freshness", freshnessLabels[v.freshness_state]),
      field("Source coverage", coverageLabels[v.coverage.source_state]),
      field("Attribution coverage", coverageLabels[v.coverage.attribution_state]),
      field("Last evaluated", v.evaluated_at_utc));
    if (v.evidence_state === "identity_pending") {
      state("Device network identity binding pending", "Device-relative protocol evidence is not yet authoritatively linked to this Device for the current Site.");
    } else if (v.evidence_state === "empty") {
      if (v.coverage.source_state === "usable" && v.coverage.attribution_state === "usable") {
        state("No recent protocol evidence", "No DNS, TLS or QUIC evidence is retained for this Device in the last 24 hours. This does not prove there was no network activity.");
      } else state("Insufficient coverage", "Recent protocol evidence cannot be determined reliably from the currently available Network Intelligence coverage.");
    } else if (v.freshness_state === "stale") state("Stale evidence", "Last evaluated " + v.evaluated_at_utc);
    else state("Protocol evidence", "Recent device-relative protocol evidence; historical completeness is not claimed.");
  }
  function clearTimer() { if (timer !== null) window.clearTimeout(timer); timer = null; }
  function eligible() { return !stopped && !terminal && !document.hidden; }
  function schedule(delay) {
    clearTimer();
    if (eligible()) timer = window.setTimeout(() => { timer = null; refresh(false); }, delay);
  }
  function discardExpired() {
    if (lastGood && Date.now() - utc(lastGood.evaluated_at_utc) >= 900000) {
      lastGood = null; content.replaceChildren();
      state("Protocol intelligence temporarily unavailable", "Refresh to request current protocol evidence.");
    }
  }
  function retainUntilBound() {
    if (expiryTimer !== null) window.clearTimeout(expiryTimer);
    expiryTimer = null;
    discardExpired();
    if (lastGood) expiryTimer = window.setTimeout(discardExpired,
      Math.max(0, 900000 - (Date.now() - utc(lastGood.evaluated_at_utc))));
  }
  async function refresh(manual) {
    if (!eligible()) return;
    if (active) { if (manual) pending = true; return; }
    clearTimer();
    const controller = new AbortController(); active = controller; lastStart = Date.now();
    const timeout = window.setTimeout(() => controller.abort(), 10000);
    let success = false;
    try {
      const response = await fetch(`/admin/api/v1/sites/${site}/devices/${device}/protocol-intelligence`, {
        method: "GET", credentials: "same-origin", cache: "no-store", signal: controller.signal,
        headers: {Accept: "application/json"}
      });
      if ([401, 403, 404].includes(response.status)) { terminal = true; throw new Error("terminal"); }
      if (!response.ok) throw new Error("unavailable");
      const value = validate(await response.json());
      if (stopped || terminal || controller.signal.aborted) return;
      lastGood = value; render(value); retainUntilBound(); failures = 0; success = true;
    } catch (_) {
      if (!stopped) {
        failures += 1; discardExpired();
        if (terminal) { lastGood = null; content.replaceChildren(); }
        state("Protocol intelligence temporarily unavailable", lastGood ?
          "Showing the last successful response; the current request is unavailable." : "Protocol evidence is currently unavailable.");
      }
    } finally {
      window.clearTimeout(timeout); active = null;
      if (pending && eligible()) { pending = false; refresh(true); }
      else { pending = false; schedule(success ? 60000 : failures <= 1 ? 60000 : failures === 2 ? 120000 : 300000); }
    }
  }
  for (const id of ["device-protocol-refresh", "refresh-button"]) {
    const button = document.getElementById(id);
    if (button) button.addEventListener("click", () => refresh(true));
  }
  document.addEventListener("visibilitychange", () => {
    clearTimer(); discardExpired();
    if (eligible()) {
      const elapsed = lastStart === null ? 60000 : Date.now() - lastStart;
      if (elapsed >= 60000) refresh(false); else schedule(60000 - elapsed);
    }
  });
  window.addEventListener("pagehide", () => {
    stopped = true; pending = false; clearTimer();
    if (expiryTimer !== null) window.clearTimeout(expiryTimer);
    if (active) active.abort();
    lastGood = null;
  });
  refresh(false);
}());
