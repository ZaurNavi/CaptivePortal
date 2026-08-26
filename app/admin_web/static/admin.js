(function () {
  "use strict";

  const MAC_PATTERN = /^[0-9A-F]{2}(?::[0-9A-F]{2}){5}$/;
  const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

  function canonicalMac(value) {
    if (typeof value !== "string") return null;
    const candidate = value.trim().replaceAll("-", ":").toUpperCase();
    return MAC_PATTERN.test(candidate) ? candidate : null;
  }

  function classifyHttp(status, payload, retryAfter) {
    const code = payload && payload.error && typeof payload.error.code === "string"
      ? payload.error.code : null;
    if (status === 401) return {kind: "session", title: "Session expired", message: "Sign in again to continue."};
    if (status === 403) return {kind: "forbidden", title: "Access denied", message: "This Site is not available to your account."};
    if (status === 429) {
      const suffix = retryAfter ? ` You may retry after ${retryAfter} second(s).` : " Retry manually in a moment.";
      return {kind: "busy", title: "Service is busy", message: `The read limit is currently occupied.${suffix}`};
    }
    if (status === 503) {
      if (code === "query_deadline") return {kind: "unavailable", title: "Query timed out", message: "Reduce the range or retry manually."};
      if (code === "response_too_large") return {kind: "unavailable", title: "Result is too large", message: "Use a narrower filter and retry."};
      return {kind: "unavailable", title: "Data temporarily unavailable", message: "The portal remains operational. Retry manually later."};
    }
    return {kind: "unexpected", title: "Unexpected response", message: "The response could not be safely interpreted."};
  }

  function display(value) {
    if (value === null || value === undefined || value === "") return "—";
    if (typeof value === "boolean") return value ? "Yes" : "No";
    if (typeof value === "number" && !Number.isFinite(value)) return "—";
    return String(value);
  }

  function localDatetimeValue(value) {
    const pad = (part) => String(part).padStart(2, "0");
    return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`
      + `T${pad(value.getHours())}:${pad(value.getMinutes())}`;
  }

  function parseVisitFilters(fromValue, toValue, statusValue) {
    const hasFrom = typeof fromValue === "string" && fromValue !== "";
    const hasTo = typeof toValue === "string" && toValue !== "";
    if (hasFrom !== hasTo) {
      throw {uiFailure: {kind: "unexpected", title: "Incomplete time range", message: "From and To must be provided together."}};
    }
    let fromUtc = null;
    let toUtc = null;
    if (hasFrom) {
      fromUtc = utcFromLocal(fromValue);
      toUtc = utcFromLocal(toValue);
      if (!fromUtc || !toUtc || fromUtc >= toUtc) {
        throw {uiFailure: {kind: "unexpected", title: "Invalid time range", message: "Provide a valid From and To range."}};
      }
    }
    const status = statusValue === "all" || statusValue === "" ? null : statusValue;
    if (status !== null && status !== "open" && status !== "closed") {
      throw {uiFailure: {kind: "unexpected", title: "Invalid status", message: "Choose All, Open or Closed."}};
    }
    return Object.freeze({fromUtc, toUtc, status});
  }

  function createVisitQueryState(initialFilters) {
    let applied = initialFilters;
    let cursor = null;
    return Object.freeze({
      apply(filters) { applied = filters; cursor = null; },
      resetCursor() { cursor = null; },
      setCursor(value) { cursor = value; },
      parameters() {
        const parameters = new URLSearchParams({limit: "100"});
        if (applied.fromUtc !== null) {
          parameters.set("from_utc", applied.fromUtc);
          parameters.set("to_utc", applied.toUtc);
        }
        if (applied.status !== null) parameters.set("status", applied.status);
        if (cursor) parameters.set("cursor", cursor);
        return parameters;
      },
      snapshot() { return {applied, cursor}; },
    });
  }

  function safeReturnPath(locationValue) {
    const path = locationValue && typeof locationValue.pathname === "string"
      ? locationValue.pathname : "/admin/";
    const search = locationValue && typeof locationValue.search === "string"
      ? locationValue.search : "";
    return `/admin/login?next=${encodeURIComponent(path + search)}`;
  }

  if (typeof window !== "undefined") {
    window.CaptivPortalAdminTest = Object.freeze({
      canonicalMac,
      classifyHttp,
      createVisitQueryState,
      display,
      localDatetimeValue,
      parseVisitFilters,
      safeReturnPath,
      utcFromLocal,
    });
  }
  if (typeof document === "undefined") return;

  const root = document.getElementById("admin-page");
  if (!root) return;
  const content = document.getElementById("page-content");
  const statePanel = document.getElementById("page-state");
  const stateTitle = document.getElementById("state-title");
  const stateMessage = document.getElementById("state-message");
  const refreshButton = document.getElementById("refresh-button");
  const pagination = document.getElementById("pagination");
  const loadMoreButton = document.getElementById("load-more-button");
  const context = {
    page: root.dataset.page,
    siteId: root.dataset.siteId,
    apiBase: root.dataset.apiBase,
    deviceId: root.dataset.deviceId || null,
    cursor: null,
    loading: false,
    operation: null,
    visitQuery: null,
  };

  function node(tag, className, text) {
    const value = document.createElement(tag);
    if (className) value.className = className;
    if (text !== undefined) value.textContent = display(text);
    return value;
  }

  function setState(kind, title, message, visible) {
    statePanel.dataset.state = (kind === "loading" || kind === "ready")
      ? "normal"
      : (kind === "unexpected" || kind === "session" || kind === "forbidden" ? "error" : "warning");
    stateTitle.textContent = title;
    stateMessage.textContent = message;
    statePanel.hidden = visible === false;
  }

  function definitionList(entries) {
    const list = node("dl", "detail-list");
    entries.forEach(([label, value]) => {
      list.append(node("dt", null, label), node("dd", null, value));
    });
    return list;
  }

  function card(title, entries, wide) {
    const value = node("article", `card${wide ? " card-wide" : ""}`);
    value.append(node("h2", null, title), definitionList(entries));
    return value;
  }

  function showFailure(failure) {
    content.replaceChildren();
    pagination.hidden = true;
    setState(failure.kind, failure.title, failure.message, true);
    if (failure.kind === "session") {
      const link = node("a", "button", "Sign in");
      link.href = safeReturnPath(window.location);
      content.append(link);
    }
  }

  async function requestJson(url) {
    let response;
    try {
      response = await fetch(url, {
        method: "GET",
        credentials: "same-origin",
        cache: "no-store",
        headers: {Accept: "application/json"},
      });
    } catch (_error) {
      throw {uiFailure: {kind: "unavailable", title: "Network unavailable", message: "Check connectivity and retry manually."}};
    }
    let payload;
    try {
      payload = await response.json();
    } catch (_error) {
      throw {uiFailure: classifyHttp(response.status, null, response.headers.get("Retry-After"))};
    }
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      throw {uiFailure: classifyHttp(response.status, null, response.headers.get("Retry-After"))};
    }
    if (!response.ok) {
      throw {uiFailure: classifyHttp(response.status, payload, response.headers.get("Retry-After"))};
    }
    if (!("result" in payload)) {
      throw {uiFailure: classifyHttp(500, null, null)};
    }
    return payload;
  }

  async function run(operation) {
    if (context.loading) return;
    context.loading = true;
    refreshButton.disabled = true;
    loadMoreButton.disabled = true;
    setState("loading", "Loading", "Requesting current Site data…", true);
    try {
      await operation();
    } catch (error) {
      showFailure(error && error.uiFailure ? error.uiFailure : classifyHttp(500, null, null));
    } finally {
      context.loading = false;
      refreshButton.disabled = false;
      loadMoreButton.disabled = false;
    }
  }

  function analyticsValue(result) {
    if (!result || typeof result !== "object") return null;
    if (result.status === "insufficient_data" || result.status === "unavailable") return null;
    return result.value && typeof result.value === "object" ? result.value : null;
  }

  async function loadHome() {
    content.replaceChildren();
    const health = await requestJson("/admin/api/v1/health");
    const to = new Date();
    const from = new Date(to.getTime() - 24 * 60 * 60 * 1000);
    const range = `from_utc=${encodeURIComponent(from.toISOString())}&to_utc=${encodeURIComponent(to.toISOString())}`;
    const visits = await requestJson(`${context.apiBase}/summary/visits?${range}`);
    const devices = await requestJson(`${context.apiBase}/summary/devices?${range}`);
    const visitValue = analyticsValue(visits.result);
    const deviceValue = analyticsValue(devices.result);
    content.append(
      card("Runtime", [["Status", health.result && health.result.status]]),
      card("Visits · 24 hours", [["Total", visitValue && (visitValue.total_visit_count ?? visitValue.visit_count)], ["Quality", visits.result && visits.result.status]]),
      card("Devices · 24 hours", [["Unique devices", deviceValue && (deviceValue.unique_linked_devices ?? deviceValue.unique_device_count ?? deviceValue.device_count)], ["Quality", devices.result && devices.result.status]])
    );
    const insufficient = !visitValue || !deviceValue;
    setState(insufficient ? "warning" : "ready", insufficient ? "Insufficient data" : "Up to date", insufficient ? "One or more summaries cannot produce a numeric value for this window." : "Showing the latest 24-hour Site summary.", true);
  }

  function deviceCard(item) {
    const value = card("Device", [
      ["MAC", item.canonical_mac], ["Type", item.device_type],
      ["First seen", item.site_first_seen_at], ["Last seen", item.site_last_seen_at],
      ["Snapshots", item.site_snapshot_count], ["Visits", item.site_visit_count],
      ["Last SSID", item.last_site_ssid], ["Last AP", item.last_site_ap_mac],
    ], false);
    if (typeof item.device_id === "string" && UUID_PATTERN.test(item.device_id)) {
      const link = node("a", "card-link", "Open device card");
      link.href = `/admin/sites/${context.siteId}/devices/${encodeURIComponent(item.device_id)}`;
      value.prepend(link);
    }
    return value;
  }

  async function loadDevices(append) {
    if (!append) {
      context.cursor = null;
      content.replaceChildren();
    }
    const macInput = document.getElementById("device-mac");
    let mac = null;
    if (macInput && macInput.value.trim()) {
      mac = canonicalMac(macInput.value);
      if (!mac) throw {uiFailure: {kind: "unexpected", title: "Invalid MAC", message: "Enter an exact MAC address such as AA:BB:CC:DD:EE:FF."}};
      macInput.value = mac;
    }
    const parameters = new URLSearchParams({limit: "100"});
    if (mac) parameters.set("mac", mac);
    if (context.cursor) parameters.set("cursor", context.cursor);
    const payload = await requestJson(`${context.apiBase}/devices?${parameters.toString()}`);
    const items = payload.result && Array.isArray(payload.result.items) ? payload.result.items : null;
    if (!items) throw {uiFailure: classifyHttp(500, null, null)};
    items.forEach((item) => content.append(deviceCard(item)));
    context.cursor = payload.page && typeof payload.page.next_cursor === "string" ? payload.page.next_cursor : null;
    pagination.hidden = !context.cursor;
    setState(items.length || append ? "ready" : "empty", items.length || append ? "Up to date" : "No devices", items.length || append ? "Site-scoped device evidence loaded." : "No device matches the current Site and filter.", true);
  }

  function visitRow(item) {
    const value = node("article", "data-row");
    const header = node("div", "data-row-header");
    header.append(node("strong", null, item.status || "Visit"), node("span", "mono", item.started_at));
    value.append(header, definitionList([
      ["MAC", item.client_mac], ["Started", item.started_at], ["Closed", item.closed_at],
      ["Duration (s)", item.duration_seconds], ["SSID", item.final_ssid || item.start_ssid],
      ["AP", item.final_ap_mac || item.start_ap_mac], ["Traffic (bytes)", item.reported_traffic_total_bytes],
    ]));
    return value;
  }

  async function loadVisits(append) {
    if (!append) {
      context.visitQuery.resetCursor();
      content.replaceChildren();
    }
    const parameters = context.visitQuery.parameters();
    const payload = await requestJson(`${context.apiBase}/visits?${parameters.toString()}`);
    const items = payload.result && Array.isArray(payload.result.items) ? payload.result.items : null;
    if (!items) throw {uiFailure: classifyHttp(500, null, null)};
    let list = content.querySelector(".row-list");
    if (!list) { list = node("div", "row-list"); content.append(list); }
    items.forEach((item) => list.append(visitRow(item)));
    const nextCursor = payload.page && typeof payload.page.next_cursor === "string" ? payload.page.next_cursor : null;
    context.visitQuery.setCursor(nextCursor);
    pagination.hidden = !nextCursor;
    setState(items.length || append ? "ready" : "empty", items.length || append ? "Up to date" : "No visits", items.length || append ? "Newest Site visits are shown first." : "No visits are available for this Site.", true);
  }

  async function loadDevice() {
    content.replaceChildren();
    if (!context.deviceId || !UUID_PATTERN.test(context.deviceId)) throw {uiFailure: classifyHttp(500, null, null)};
    const payload = await requestJson(`${context.apiBase}/devices/${encodeURIComponent(context.deviceId)}`);
    const result = payload.result;
    if (!result || typeof result !== "object" || !result.identity) throw {uiFailure: classifyHttp(500, null, null)};
    const identity = result.identity;
    content.append(card("Identity", [
      ["MAC", identity.canonical_mac], ["Type", identity.device_type],
      ["First seen", identity.site_first_seen_at], ["Last seen", identity.site_last_seen_at],
      ["Snapshot count", identity.site_snapshot_count], ["Visit count", identity.site_visit_count],
    ]));
    content.append(card("Latest Site snapshot", Object.entries(result.latest_snapshot || {}).map(([key, value]) => [key.replaceAll("_", " "), value])));
    content.append(card("Latest client observation", Object.entries(result.latest_client_observation || {}).map(([key, value]) => [key.replaceAll("_", " "), value])));
    const visits = Array.isArray(result.recent_visits) ? result.recent_visits : [];
    const list = node("div", "row-list");
    visits.forEach((item) => list.append(visitRow(item)));
    if (visits.length) content.append(list);
    setState(visits.length ? "ready" : "warning", visits.length ? "Up to date" : "Partial context", visits.length ? "Device context and recent visits loaded." : "Device context is available, but there are no recent Site visits.", true);
  }

  function observationRow(item) {
    const value = node("article", "data-row");
    const header = node("div", "data-row-header");
    header.append(node("strong", null, item.client_mac || item.ap_mac || "Observation"), node("span", "mono", item.observed_at));
    const safeEntries = Object.entries(item).filter(([key]) => key !== "radios");
    value.append(header, definitionList(safeEntries.map(([key, field]) => [key.replaceAll("_", " "), field])));
    if (Array.isArray(item.radios) && item.radios.length) {
      value.append(node("h3", null, "Radios"));
      item.radios.forEach((radio) => value.append(definitionList(Object.entries(radio).map(([key, field]) => [key.replaceAll("_", " "), field]))));
    }
    if (item.partial === true) value.prepend(node("span", "badge warning", "Partial"));
    return value;
  }

  function utcFromLocal(value) {
    if (!value) return null;
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString();
  }

  async function loadObservations(append) {
    const form = document.getElementById("observation-form");
    const kind = form.elements.kind.value;
    const mac = canonicalMac(form.elements.mac.value);
    const from = utcFromLocal(form.elements.from.value);
    const to = utcFromLocal(form.elements.to.value);
    if (!mac || !from || !to || from >= to) throw {uiFailure: {kind: "unexpected", title: "Invalid filter", message: "Provide an exact MAC and a valid bounded time range."}};
    form.elements.mac.value = mac;
    if (!append) { context.cursor = null; content.replaceChildren(); }
    const parameters = new URLSearchParams({from_utc: from, to_utc: to, limit: "100"});
    parameters.set(kind === "clients" ? "client_mac" : "ap_mac", mac);
    if (context.cursor) parameters.set("cursor", context.cursor);
    const payload = await requestJson(`${context.apiBase}/observations/${kind}?${parameters.toString()}`);
    const items = payload.result && Array.isArray(payload.result.items) ? payload.result.items : null;
    if (!items) throw {uiFailure: classifyHttp(500, null, null)};
    let list = content.querySelector(".row-list");
    if (!list) { list = node("div", "row-list"); content.append(list); }
    items.forEach((item) => list.append(observationRow(item)));
    context.cursor = payload.page && typeof payload.page.next_cursor === "string" ? payload.page.next_cursor : null;
    pagination.hidden = !context.cursor;
    setState(items.length || append ? "ready" : "empty", items.length || append ? "Up to date" : "No observations", items.length || append ? "Normalized Site observations loaded." : "No rows match this Site, device and time range.", true);
  }

  function configure() {
    if (context.page === "home" && root.dataset.homeLiveEnabled === "true") return;
    if (context.page === "home") context.operation = () => loadHome();
    if (context.page === "devices") {
      context.operation = () => loadDevices(false);
      const form = document.getElementById("device-search-form");
      form.addEventListener("submit", (event) => { event.preventDefault(); run(() => loadDevices(false)); });
      document.getElementById("clear-device-search").addEventListener("click", () => { form.elements.mac.value = ""; run(() => loadDevices(false)); });
    }
    if (context.page === "device") context.operation = () => loadDevice();
    if (context.page === "visits") {
      const form = document.getElementById("visit-filter-form");
      const now = new Date();
      const from = new Date(now.getTime() - 24 * 60 * 60 * 1000);
      form.elements.to.value = localDatetimeValue(now);
      form.elements.from.value = localDatetimeValue(from);
      context.visitQuery = createVisitQueryState(
        parseVisitFilters(
          form.elements.from.value,
          form.elements.to.value,
          form.elements.status.value
        )
      );
      context.operation = () => loadVisits(false);
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        run(async () => {
          const filters = parseVisitFilters(
            form.elements.from.value,
            form.elements.to.value,
            form.elements.status.value
          );
          context.visitQuery.apply(filters);
          await loadVisits(false);
        });
      });
      document.getElementById("clear-visit-filters").addEventListener("click", () => {
        form.elements.from.value = "";
        form.elements.to.value = "";
        form.elements.status.value = "all";
        run(async () => {
          context.visitQuery.apply(parseVisitFilters("", "", "all"));
          await loadVisits(false);
        });
      });
    }
    if (context.page === "observations") {
      const form = document.getElementById("observation-form");
      const now = new Date();
      const from = new Date(now.getTime() - 60 * 60 * 1000);
      form.elements.to.value = localDatetimeValue(now);
      form.elements.from.value = localDatetimeValue(from);
      context.operation = null;
      setState("empty", "Choose a filter", "Enter a client or AP MAC and a bounded time range.", true);
      form.addEventListener("submit", (event) => { event.preventDefault(); run(() => loadObservations(false)); });
    }
    refreshButton.addEventListener("click", () => {
      if (context.operation) run(context.operation);
      else if (context.page === "observations") run(() => loadObservations(false));
    });
    loadMoreButton.addEventListener("click", () => {
      if (context.page === "devices") run(() => loadDevices(true));
      if (context.page === "visits") run(() => loadVisits(true));
      if (context.page === "observations") run(() => loadObservations(true));
    });
    if (context.operation) run(context.operation);
  }

  configure();
}());

(function () {
  "use strict";

  const API_VERSION = "admin.read.v1";
  const UTC = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/;
  const STATUSES = new Set(["complete", "partial"]);
  const FRESHNESS = new Set(["fresh", "stale", "unavailable"]);
  const PERIODS = new Set(["last_24h", "yesterday", "last_48h", "last_7d", "current_month", "last_30d", "custom"]);
  const ROLLING = new Set(["last_24h", "last_48h", "last_7d", "current_month", "last_30d"]);
  const QUALITY = new Set([
    "coverage_start_unknown", "requested_before_coverage_start",
    "requested_after_coverage_through", "source_unavailable", "query_deadline",
    "opening_authorization_evidence_missing", "authorization_chronology_anomaly",
    "pending_offline_events", "invalid_offline_events", "missing_reported_traffic",
    "missing_controller_time", "semantic_replay_suppressed",
    "unsupported_processing_result", "reader_stale", "reader_unavailable",
  ]);
  const BACKOFF = [60, 120, 300];

  function object(value) { return value && typeof value === "object" && !Array.isArray(value); }
  function integer(value) { return typeof value === "number" && Number.isInteger(value) && value >= 0; }
  function utc(value) {
    if (typeof value !== "string" || !UTC.test(value)) return false;
    const parsed = new Date(value);
    return !Number.isNaN(parsed.getTime()) && parsed.toISOString() === value;
  }
  function optionalUtc(value) { return value === null || utc(value); }
  function coverage(value) {
    if (!object(value) || !STATUSES.has(value.status)
      || value.fully_covered !== (value.status === "complete")
      || !optionalUtc(value.coverage_from_utc) || !optionalUtc(value.coverage_through_utc)
      || !optionalUtc(value.covered_from_utc) || !optionalUtc(value.covered_through_utc)
      || !Array.isArray(value.quality_reasons)
      || new Set(value.quality_reasons).size !== value.quality_reasons.length
      || value.quality_reasons.some((reason) => !QUALITY.has(reason))) return false;
    if (value.status === "complete" && value.quality_reasons.length) return false;
    if ((value.covered_from_utc === null) !== (value.covered_through_utc === null)) return false;
    if (value.covered_from_utc !== null
      && new Date(value.covered_from_utc) >= new Date(value.covered_through_utc)) return false;
    return true;
  }
  function range(value, evaluatedAt) {
    if (!object(value) || !object(value.requested) || !object(value.resolved)) return false;
    const resolved = value.resolved;
    return utc(resolved.from_utc) && utc(resolved.to_utc)
      && typeof resolved.from_local === "string" && typeof resolved.to_local_exclusive === "string"
      && typeof resolved.timezone === "string" && resolved.timezone.length > 0
      && new Date(resolved.from_utc) < new Date(resolved.to_utc)
      && new Date(resolved.to_utc) <= new Date(evaluatedAt);
  }
  function visits(value) {
    return object(value) && integer(value.value) && STATUSES.has(value.status)
      && value.value === value.verified_visit_count && integer(value.verified_visit_count)
      && integer(value.integrity_anomaly_count) && value.cohort === "visit_opening_authorization"
      && value.source_kind === "visit_lifecycle" && coverage(value.coverage)
      && value.status === value.coverage.status
      && optionalUtc(value.earliest_persisted_evidence_at)
      && optionalUtc(value.latest_persisted_evidence_at);
  }
  function traffic(value) {
    const names = ["eligible_terminal_event_count", "included_fingerprint_count",
      "unmatched_included_event_count", "pending_event_count", "invalid_event_count",
      "missing_traffic_count", "missing_controller_time_count", "semantic_duplicate_count",
      "other_excluded_event_count"];
    return object(value) && integer(value.bytes) && STATUSES.has(value.status)
      && value.estimated === true && value.attribution === "completed_session_end"
      && value.source_kind === ["om", "ada_offline_reported_traffic"].join("")
      && names.every((name) => integer(value[name]))
      && value.included_fingerprint_count <= value.eligible_terminal_event_count
      && value.semantic_duplicate_count === value.eligible_terminal_event_count - value.included_fingerprint_count
      && FRESHNESS.has(value.ingestion_freshness) && optionalUtc(value.reader_watermark_at)
      && coverage(value.coverage) && value.status === value.coverage.status
      && optionalUtc(value.earliest_persisted_evidence_at)
      && optionalUtc(value.latest_persisted_evidence_at);
  }
  function validateActivity(payload, siteId, expectedKind) {
    if (!object(payload) || payload.api_version !== API_VERSION || payload.site_id !== siteId
      || !object(payload.result)) return null;
    const result = payload.result;
    if (!utc(result.evaluated_at_utc) || typeof result.timezone !== "string"
      || !Array.isArray(result.guest_ssids) || !result.guest_ssids.length
      || result.guest_ssids.some((ssid) => typeof ssid !== "string" || !ssid)
      || !range(result.range, result.evaluated_at_utc)
      || result.range.requested.kind !== expectedKind
      || !visits(result.authorized_visits) || !traffic(result.traffic)
      || !(result.next_site_midnight_utc === null || utc(result.next_site_midnight_utc))) return null;
    if (expectedKind === "today" && result.next_site_midnight_utc === null) return null;
    return result;
  }
  function validatePreview(payload, siteId) {
    if (!object(payload) || payload.api_version !== API_VERSION || payload.site_id !== siteId
      || !object(payload.result) || typeof payload.result.timezone !== "string"
      || !object(payload.result.requested) || !object(payload.result.resolved)
      || !utc(payload.result.resolved.from_utc) || !utc(payload.result.resolved.to_utc)
      || typeof payload.result.resolved.from_local !== "string"
      || typeof payload.result.resolved.to_local_exclusive !== "string"
      || typeof payload.result.can_apply !== "boolean"
      || !(payload.result.validation_reason === null || payload.result.validation_reason === "end_in_future")) return null;
    return payload.result;
  }
  function bytes(value) {
    if (!integer(value)) return "—";
    if (value === 0) return "0 B";
    const units = ["B", "KB", "MB", "GB", "TB"];
    let amount = value; let index = 0;
    while (amount >= 1024 && index < units.length - 1) { amount /= 1024; index += 1; }
    return `${index === 0 ? amount : amount.toFixed(amount >= 10 ? 1 : 2)} ${units[index]}`;
  }
  function selectionDynamic(period) { return ROLLING.has(period); }
  function eligible(source, manual, now) {
    if (source.disabled) return false;
    if (!manual && !source.autoRefresh) return false;
    if (source.failureCount > 0) {
      const threshold = manual && Number.isFinite(source.manualEligibleAt)
        ? source.manualEligibleAt
        : source.nextEligibleAt;
      return now >= threshold;
    }
    return manual || now >= source.nextEligibleAt;
  }
  function nextEligible(today, selected) {
    const values = [today.nextEligibleAt];
    if (selected.autoRefresh) values.push(selected.nextEligibleAt);
    return Math.min(...values.filter(Number.isFinite));
  }
  function claim(source, controller, generation) {
    if (source.generation !== generation || source.controller !== null) return false;
    source.controller = controller; return true;
  }
  function release(source, controller) { if (source.controller === controller) source.controller = null; }
  function abort(source, reason) {
    const controller = source.controller; if (!controller) return false;
    controller.abort(reason); release(source, controller); return true;
  }
  function failureTransition(source, item, interval, now, randomValue) {
    if (item.kind === "disabled" || item.kind === "invalid") {
      if (item.kind === "disabled") source.disabled = true;
      source.autoRefresh = false; source.nextEligibleAt = Infinity;
      return Infinity;
    }
    source.failureCount += 1;
    const jitter = item.status === 429
      ? Math.max(0, Math.min(1, randomValue || 0)) * 10
      : 0;
    const delay = Math.max(
      interval,
      BACKOFF[Math.min(source.failureCount - 1, 2)],
      item.retryAfter || 0,
    ) + jitter;
    source.nextEligibleAt = now + delay * 1000;
    source.manualEligibleAt = source.nextEligibleAt;
    return delay;
  }

  if (typeof window !== "undefined") {
    window.CaptivPortalHomeActivityTest = Object.freeze({
      bytes, coverage, coverageText, eligible, nextEligible, range,
      selectionDynamic, failureTransition,
      validateActivity, validatePreview, visits, traffic, claim, release, abort,
    });
  }
  if (typeof document === "undefined") return;
  const root = document.getElementById("admin-page");
  if (!root || root.dataset.page !== "home" || root.dataset.homeActivityEnabled !== "true") return;

  const siteId = root.dataset.siteId;
  const base = root.dataset.apiBase + "/home-activity";
  const interval = Number(root.dataset.homeActivityRefreshSeconds);
  const timeoutMs = Number(root.dataset.homeActivityRequestTimeoutSeconds) * 1000;
  const picker = document.getElementById("activity-picker");
  const pickerOpener = document.getElementById("activity-picker-open");
  const fields = document.getElementById("activity-custom-fields");
  const previewButton = document.getElementById("activity-preview");
  const applyButton = document.getElementById("activity-apply");
  const cancelButton = document.getElementById("activity-cancel");
  const previewState = document.getElementById("activity-preview-state");
  const today = {generation: 0, controller: null, failureCount: 0, nextEligibleAt: 0, manualEligibleAt: 0, autoRefresh: true, disabled: false, accepted: null};
  const selected = {generation: 0, controller: null, failureCount: 0, nextEligibleAt: 0, manualEligibleAt: 0, autoRefresh: true, disabled: false, accepted: null, revision: 0};
  const preview = {generation: 0, controller: null};
  let applied = {period: "last_24h"};
  let previewSignature = null;
  let stopped = false;

  function currentSignature() {
    return JSON.stringify({
      from_date: picker.elements.from_date.value,
      from_time: picker.elements.from_time.value,
      to_date: picker.elements.to_date.value,
      to_time: picker.elements.to_time.value,
    });
  }
  function selectedParameters() {
    const values = {period: picker.elements.period.value};
    if (values.period === "custom") {
      ["from_date", "from_time", "to_date", "to_time"].forEach((name) => {
        if (picker.elements[name].value) values[name] = picker.elements[name].value;
      });
    }
    return values;
  }
  function query(values) {
    const result = new URLSearchParams();
    Object.entries(values).forEach(([key, value]) => result.set(key, value));
    return result.toString();
  }
  function classify(status, code) {
    if (status === 401) return {global: true, kind: "session", retryAfter: 0, status};
    if (status === 403) return {global: true, kind: "forbidden", retryAfter: 0, status};
    if (status === 404) return {global: false, kind: "disabled", retryAfter: 0, status};
    if (status === 400) return {global: false, kind: "invalid", retryAfter: 0, status};
    return {global: false, kind: code === "query_deadline" ? "timeout" : "unavailable", retryAfter: 0, status};
  }
  async function requestJson(url, source, generation) {
    const controller = new AbortController();
    if (!claim(source, controller, generation)) throw {neutral: true};
    const timer = window.setTimeout(() => controller.abort("timeout"), timeoutMs);
    try {
      const response = await fetch(url, {method: "GET", credentials: "same-origin", cache: "no-store", headers: {Accept: "application/json"}, signal: controller.signal});
      let payload = null; try { payload = await response.json(); } catch (_error) { payload = null; }
      if (!response.ok) {
        const failure = classify(response.status, payload && payload.error && payload.error.code);
        const retryAfter = Number(response.headers.get("Retry-After"));
        failure.retryAfter = Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : 0;
        throw {failure};
      }
      if (source.generation !== generation || stopped) throw {neutral: true};
      return payload;
    } catch (error) {
      if (controller.signal.aborted) {
        if (["hidden", "pagehide", "superseded"].includes(controller.signal.reason)) throw {neutral: true};
        throw {failure: {global: false, kind: "timeout", retryAfter: 0}};
      }
      if (error && (error.failure || error.neutral)) throw error;
      throw {failure: {global: false, kind: "unavailable", retryAfter: 0}};
    } finally {
      window.clearTimeout(timer); release(source, controller);
    }
  }
  function rangeText(value) {
    const resolved = value.range.resolved;
    return `${resolved.from_local} → ${resolved.to_local_exclusive} · ${resolved.timezone}`;
  }
  function coverageText(label, value) {
    if (value.status === "complete") return `${label} complete`;
    const coverageValue = value.coverage;
    if (coverageValue.covered_from_utc && coverageValue.covered_through_utc) {
      return `${label} partial · proven ${coverageValue.covered_from_utc} → ${coverageValue.covered_through_utc}`;
    }
    return `${label} partial · proven coverage unavailable`;
  }
  function qualityText(value) {
    const visit = value.authorized_visits; const trafficValue = value.traffic;
    const labels = [coverageText("Visits", visit), coverageText("Traffic", trafficValue), `Reader ${trafficValue.ingestion_freshness}`];
    return labels.join(" · ");
  }
  function render(kind, value) {
    document.getElementById(`activity-${kind}-range`).textContent = rangeText(value);
    document.getElementById(`activity-${kind}-visits`).textContent = String(value.authorized_visits.value);
    const suffix = value.traffic.status === "partial" ? " · Partial · Estimated" : " · Estimated";
    document.getElementById(`activity-${kind}-traffic`).textContent = bytes(value.traffic.bytes) + suffix;
    document.getElementById(`activity-${kind}-quality`).textContent = qualityText(value);
  }
  function loading(kind) {
    document.getElementById(`activity-${kind}-quality`).textContent = "Loading…";
  }
  function failed(kind, message) {
    document.getElementById(`activity-${kind}-quality`).textContent = message;
  }
  function success(source, dynamic, value) {
    source.accepted = value; source.failureCount = 0; source.manualEligibleAt = 0; source.autoRefresh = dynamic;
    if (source === selected && applied.period === "yesterday"
      && today.accepted && today.accepted.next_site_midnight_utc) {
      source.autoRefresh = true;
      source.nextEligibleAt = new Date(today.accepted.next_site_midnight_utc).getTime() - Date.now() + performance.now();
    } else if (dynamic) source.nextEligibleAt = performance.now() + interval * 1000;
    else if (value.next_site_midnight_utc) source.nextEligibleAt = new Date(value.next_site_midnight_utc).getTime() - Date.now() + performance.now();
    else source.nextEligibleAt = Infinity;
  }
  function failure(source, kind, item) {
    if (item.global) {
      const coordinator = window.CaptivPortalHomeCoordinator;
      if (coordinator) coordinator.stop(item.kind);
      return;
    }
    if (item.kind === "disabled") {
      failureTransition(source, item, interval, performance.now(), Math.random());
      failed(kind, "Activity is disabled; current panels remain available.");
      return;
    }
    failureTransition(source, item, interval, performance.now(), Math.random());
    if (source === selected && !selectionDynamic(applied.period)) {
      if (applied.period === "yesterday"
        && today.accepted && today.accepted.next_site_midnight_utc) {
        source.autoRefresh = true;
        source.nextEligibleAt = new Date(today.accepted.next_site_midnight_utc).getTime() - Date.now() + performance.now();
      } else {
        source.autoRefresh = false;
        source.nextEligibleAt = Infinity;
      }
    }
    failed(kind, item.kind === "invalid" ? "Invalid Activity request or response." : "Activity source unavailable; retry remains bounded.");
  }
  async function refreshToday(manual) {
    if (!eligible(today, manual, performance.now())) return;
    today.generation += 1; const generation = today.generation; loading("today");
    try {
      const payload = await requestJson(`${base}/today`, today, generation);
      const value = validateActivity(payload, siteId, "today");
      if (!value) throw {failure: {global: false, kind: "invalid", retryAfter: 0}};
      render("today", value); success(today, true, value);
    } catch (error) { if (!(error && error.neutral)) failure(today, "today", error.failure || {global: false, kind: "unavailable", retryAfter: 0}); }
  }
  async function refreshSelected(manual) {
    if (!eligible(selected, manual, performance.now())) return;
    selected.generation += 1; const generation = selected.generation; const revision = selected.revision; loading("selected");
    try {
      const payload = await requestJson(`${base}/selected?${query(applied)}`, selected, generation);
      const expected = applied.period === "custom" ? "custom" : "preset";
      const value = validateActivity(payload, siteId, expected);
      if (!value || selected.revision !== revision) throw {failure: {global: false, kind: "invalid", retryAfter: 0}};
      render("selected", value); success(selected, selectionDynamic(applied.period), value);
    } catch (error) { if (!(error && error.neutral)) failure(selected, "selected", error.failure || {global: false, kind: "unavailable", retryAfter: 0}); }
  }
  async function run(manual) { await refreshToday(manual); await refreshSelected(manual); }
  async function runToday(manual) { await refreshToday(manual); }
  async function runSelected(manual) { await refreshSelected(manual); }
  function abortAll(reason) { abort(today, reason); abort(selected, reason); abort(preview, reason); }
  function abortSelected(reason) { selected.generation += 1; abort(selected, reason); }
  function due() { return nextEligible(today, selected); }

  window.CaptivPortalHomeActivityCoordinator = Object.freeze({
    abort: abortAll, abortSelected, nextEligibleAt: due,
    run, runToday, runSelected,
  });

  async function doPreview() {
    preview.generation += 1; const generation = preview.generation; abort(preview, "superseded");
    previewState.textContent = "Resolving range in the Site timezone…";
    const values = selectedParameters(); delete values.period;
    try {
      const payload = await requestJson(`${base}/range-preview?${query(values)}`, preview, generation);
      const value = validatePreview(payload, siteId);
      if (!value) throw {failure: {global: false, kind: "invalid", retryAfter: 0}};
      previewSignature = value.can_apply ? currentSignature() : null;
      applyButton.disabled = !value.can_apply;
      previewState.textContent = value.can_apply
        ? `${value.resolved.from_local} → ${value.resolved.to_local_exclusive} · ${value.timezone} · UTC ${value.resolved.from_utc} → ${value.resolved.to_utc}`
        : "End is in the future.";
    } catch (error) {
      if (!(error && error.neutral)) {
        previewSignature = null; applyButton.disabled = true;
        previewState.textContent = "This local range is invalid, nonexistent, or ambiguous in the Site timezone.";
      }
    }
  }
  function showCustom() {
    const custom = picker.elements.period.value === "custom";
    fields.hidden = !custom; previewButton.hidden = !custom;
    previewSignature = null; applyButton.disabled = custom;
    previewState.textContent = "";
  }
  function openPicker() {
    picker.hidden = false;
    pickerOpener.setAttribute("aria-expanded", "true");
    picker.elements.period.focus();
  }
  function closePicker() {
    picker.hidden = true;
    pickerOpener.setAttribute("aria-expanded", "false");
    pickerOpener.focus();
  }
  function restoreAppliedDraft() {
    picker.elements.period.value = applied.period;
    ["from_date", "from_time", "to_date", "to_time"].forEach((name) => {
      picker.elements[name].value = applied[name] || "";
    });
    showCustom();
  }
  pickerOpener.addEventListener("click", openPicker);
  picker.elements.period.addEventListener("change", showCustom);
  ["from_date", "from_time", "to_date", "to_time"].forEach((name) => picker.elements[name].addEventListener("input", () => {
    previewSignature = null; if (picker.elements.period.value === "custom") applyButton.disabled = true;
  }));
  previewButton.addEventListener("click", doPreview);
  picker.addEventListener("submit", (event) => {
    event.preventDefault();
    const values = selectedParameters();
    if (values.period === "custom" && previewSignature !== currentSignature()) return;
    applied = values; selected.revision += 1; abortSelected("superseded");
    selected.failureCount = 0; selected.nextEligibleAt = 0; selected.manualEligibleAt = 0; selected.autoRefresh = selectionDynamic(values.period);
    closePicker();
    const coordinator = window.CaptivPortalHomeCoordinator;
    if (coordinator) coordinator.requestActivitySelected();
  });
  cancelButton.addEventListener("click", () => {
    restoreAppliedDraft(); closePicker();
  });
  picker.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault(); restoreAppliedDraft(); closePicker();
    }
  });
  document.addEventListener("visibilitychange", () => { if (document.hidden) abortAll("hidden"); });
  window.addEventListener("pagehide", () => { stopped = true; abortAll("pagehide"); });
  showCustom();
}());

(function () {
  "use strict";

  const API_VERSION = "admin.read.v1";
  const FRESHNESS = new Set(["fresh", "stale", "unavailable"]);
  const AUTH = new Set(["authorized", "pending", "other", "unknown"]);
  const AP_PRODUCT = new Set(["Online", "Other", "Unknown"]);
  const BACKOFF_SECONDS = [60, 120, 300];

  function integer(value) { return Number.isInteger(value) && value >= 0 && typeof value !== "boolean"; }
  function signedIntegerOrNull(value) { return value === null || Number.isInteger(value); }
  function nonnegativeIntegerOrNull(value) { return value === null || integer(value); }
  function optionalString(value) { return value === null || typeof value === "string"; }
  function display(value) { return value === null || value === undefined ? "—" : String(value); }
  function currentAge(snapshot, acceptedAt, now) {
    if (!snapshot || snapshot.age_seconds === null) return null;
    return snapshot.age_seconds + Math.max(0, now - acceptedAt) / 1000;
  }
  function localFreshness(snapshot, policy, acceptedAt, now) {
    const age = currentAge(snapshot, acceptedAt, now);
    if (!snapshot || snapshot.freshness_status === "unavailable" || age === null || age > policy.unavailable_after_seconds) return "unavailable";
    return age <= policy.fresh_max_age_seconds ? "fresh" : "stale";
  }
  function retryDelay(failureCount, refreshSeconds, retryAfter) {
    const backoff = BACKOFF_SECONDS[Math.min(Math.max(failureCount - 1, 0), 2)];
    return Math.max(refreshSeconds, backoff, retryAfter || 0);
  }
  function enrichmentState(rows, cursor, summary, mac, effectiveFreshness) {
    if (!summary || effectiveFreshness === "unavailable") return "AP source unavailable";
    const item = rows.find((value) => value.ap_mac === mac);
    if (item) return `Matched · ${item.product_status_classification}`;
    return cursor ? "Not yet loaded" : "Absent after inventory load";
  }
  function sourceScopeValid(scope, kind, siteId) {
    if (!scope || typeof scope !== "object" || Array.isArray(scope) || scope.site_id !== siteId) return false;
    if (kind === "ap") return scope.scope_type === "site_ap_inventory";
    return scope.scope_type === "client_ssid_allowlist" && Array.isArray(scope.ssids)
      && scope.ssids.length > 0 && scope.ssids.every((item) => typeof item === "string" && item.length > 0);
  }
  function classify(status, code) {
    if (status === 401) return {global: true, retryable: false, kind: "session"};
    if (status === 403) return {global: true, retryable: false, kind: "forbidden"};
    if (status === 404) return {global: true, retryable: false, kind: "disabled"};
    if (status === 400) return {global: false, retryable: false, kind: "invalid"};
    if (status === 429 || status === 503 || status === 500) return {global: false, retryable: true, kind: code === "query_deadline" ? "timeout" : "unavailable"};
    return {global: false, retryable: true, kind: "unexpected"};
  }
  function validSnapshot(value, kind, siteId) {
    const basic = value && typeof value === "object" && !Array.isArray(value)
      && value.kind === kind && value.site_id === undefined
      && FRESHNESS.has(value.freshness_status)
      && (value.age_seconds === null || (typeof value.age_seconds === "number" && Number.isFinite(value.age_seconds) && value.age_seconds >= 0))
      && optionalString(value.cycle_id) && (value.cycle_id === null || value.cycle_id.length > 0)
      && optionalString(value.source_scope_hash) && (value.source_scope_hash === null || /^[0-9a-f]{64}$/.test(value.source_scope_hash))
      && typeof siteId === "string";
    if (!basic) return false;
    if (value.freshness_status === "fresh" || value.freshness_status === "stale") {
      return value.complete === true && value.cycle_id !== null
        && value.source_scope_hash !== null && sourceScopeValid(value.source_scope, kind, siteId);
    }
    if (typeof value.complete !== "boolean") return false;
    if (value.cycle_id === null) return value.source_scope_hash === null && value.source_scope === null;
    return value.source_scope_hash !== null && sourceScopeValid(value.source_scope, kind, siteId);
  }
  function validEnvelope(payload, siteId) {
    return payload && typeof payload === "object" && !Array.isArray(payload)
      && payload.api_version === API_VERSION && payload.site_id === siteId
      && payload.result && typeof payload.result === "object" && !Array.isArray(payload.result);
  }
  function validateClientSummary(payload, siteId) {
    if (!validEnvelope(payload, siteId)) return null;
    const result = payload.result;
    const scope = result.snapshot && result.snapshot.source_scope;
    if (!validSnapshot(result.snapshot, "client", siteId) || !result.freshness_policy
      || !integer(result.freshness_policy.fresh_max_age_seconds)
      || !integer(result.freshness_policy.unavailable_after_seconds)
      || !Array.isArray(result.devices_by_ap)
      || (scope !== null && !sourceScopeValid(scope, "client", siteId))) return null;
    const counts = result.counts;
    if (!counts || typeof counts !== "object") return null;
    if (result.snapshot.freshness_status === "unavailable") {
      if (Object.values(counts).some((value) => value !== null) || result.devices_by_ap.length) return null;
    } else {
      if (!Object.values(counts).every(integer)) return null;
      if (counts.online !== counts.authorized + counts.pending + counts.other + counts.unknown) return null;
      if (counts.other_unknown !== counts.other + counts.unknown) return null;
      let bucketTotal = 0;
      for (const bucket of result.devices_by_ap) {
        if (!bucket || typeof bucket.ap_mac !== "string" || !integer(bucket.client_count)) return null;
        bucketTotal += bucket.client_count;
      }
      if (counts.online !== bucketTotal + counts.ap_unknown) return null;
    }
    return result;
  }
  function validateApSummary(payload, siteId) {
    if (!validEnvelope(payload, siteId)) return null;
    const result = payload.result;
    const scope = result.snapshot && result.snapshot.source_scope;
    if (!validSnapshot(result.snapshot, "ap", siteId) || !result.freshness_policy
      || !integer(result.freshness_policy.fresh_max_age_seconds)
      || !integer(result.freshness_policy.unavailable_after_seconds)
      || (scope !== null && !sourceScopeValid(scope, "ap", siteId))
      || !result.counts) return null;
    const values = Object.values(result.counts);
    if (result.snapshot.freshness_status === "unavailable") {
      if (values.some((value) => value !== null)) return null;
    } else if (!values.every(integer) || result.counts.total !== result.counts.online + result.counts.other + result.counts.unknown) return null;
    return result;
  }
  function validatePage(payload, siteId, kind, pinned) {
    if (!validEnvelope(payload, siteId) || !payload.page || !Array.isArray(payload.result.items)) return null;
    const result = payload.result;
    if (!validSnapshot(result.snapshot, kind, siteId)
      || result.snapshot.freshness_status === "unavailable" || result.snapshot.complete !== true
      || !Number.isInteger(payload.page.limit) || payload.page.limit < 1 || payload.page.limit > 250) return null;
    if (payload.page.cycle_id !== pinned.cycle_id || payload.page.source_scope_hash !== pinned.source_scope_hash) return null;
    if (result.snapshot.cycle_id !== pinned.cycle_id || result.snapshot.source_scope_hash !== pinned.source_scope_hash) return null;
    if (JSON.stringify(result.snapshot.source_scope) !== JSON.stringify(pinned.source_scope)) return null;
    if (!(payload.page.next_cursor === null || (typeof payload.page.next_cursor === "string" && payload.page.next_cursor.length > 0 && payload.page.next_cursor.length <= 4096))) return null;
    for (const item of result.items) {
      if (!item || typeof item !== "object" || Array.isArray(item)) return null;
      if (kind === "client") {
        if (typeof item.client_mac !== "string" || typeof item.ssid !== "string" || !AUTH.has(item.auth_classification)
          || !optionalString(item.name) || !optionalString(item.hostname) || !optionalString(item.ip)
          || !optionalString(item.ap_name) || !optionalString(item.ap_mac) || !optionalString(item.band)
          || !signedIntegerOrNull(item.rssi) || !signedIntegerOrNull(item.snr)
          || !nonnegativeIntegerOrNull(item.controller_uptime)
          || !nonnegativeIntegerOrNull(item.controller_traffic_down)
          || !nonnegativeIntegerOrNull(item.controller_traffic_up)
          || !nonnegativeIntegerOrNull(item.controller_traffic_total)) return null;
        const ssids = pinned.source_scope && pinned.source_scope.ssids;
        if (!Array.isArray(ssids) || !ssids.includes(item.ssid)) return null;
      } else if (typeof item.ap_mac !== "string" || !optionalString(item.name) || !AP_PRODUCT.has(item.product_status_classification)) return null;
    }
    return payload;
  }
  function claimController(source, controller, generation) {
    if (source.generation !== generation || source.controller !== null) return false;
    source.controller = controller;
    return true;
  }
  function releaseController(source, controller) {
    if (source.controller === controller) source.controller = null;
  }
  function abortOwnedController(source, reason) {
    const controller = source.controller;
    if (!controller) return false;
    controller.abort(reason);
    releaseController(source, controller);
    return true;
  }
  function retainedSelection(options, selected) {
    return Array.isArray(options) && options.includes(selected) ? selected : "";
  }
  function clientParameters(cycleId, limit, cursor, values) {
    const result = new URLSearchParams({cycle_id: cycleId, limit: String(limit), sort: values.sort});
    if (values.auth) result.set("auth_classification", values.auth);
    if (values.ap) result.set("ap_mac", values.ap);
    if (values.ssid) result.set("ssid", values.ssid);
    if (cursor) result.set("cursor", cursor);
    return result;
  }
  function resetClientState(source, view) {
    source.cursor = null;
    source.rows = [];
    view.clearRows();
    view.hideMore();
    view.loading();
  }
  function failureTransition(source, failure) {
    if (failure.kind === "invalid" && !source.cleanRetry) {
      source.cleanRetry = true;
      return {cleanRefresh: true, failureCount: source.failureCount};
    }
    source.failureCount += 1;
    return {cleanRefresh: false, failureCount: source.failureCount};
  }
  function neutralAbort(reason, hidden) {
    return hidden || reason === "hidden" || reason === "superseded" || reason === "pagehide";
  }
  function canStartCleanRefresh(source, generation, isStopped, hidden) {
    return source.generation === generation && source.controller === null && !isStopped && !hidden;
  }
  function unavailableValues(kind) {
    return kind === "client"
      ? {primary: "—", detail: "Other — · Unknown —", state: "Unavailable"}
      : {primary: "— / —", detail: "Other — · Unknown —", count: "Unavailable", state: "Unavailable"};
  }

  if (typeof window !== "undefined") {
    window.CaptivPortalHomeLiveTest = Object.freeze({
      classify, currentAge, localFreshness, retryDelay,
      abortOwnedController, canStartCleanRefresh, claimController, clientParameters, enrichmentState,
      failureTransition, neutralAbort, releaseController, resetClientState,
      retainedSelection, unavailableValues,
      validateApSummary, validateClientSummary, validatePage,
    });
  }
  if (typeof document === "undefined") return;
  const root = document.getElementById("admin-page");
  if (!root || root.dataset.page !== "home" || root.dataset.homeLiveEnabled !== "true"
    || root.dataset.homeTrafficEnabled === "true"
    || root.dataset.homeActivityEnabled === "true") return;

  const siteId = root.dataset.siteId;
  const apiBase = root.dataset.apiBase + "/current-state";
  const refreshSeconds = Number(root.dataset.homeLiveRefreshSeconds);
  const timeoutMs = Number(root.dataset.homeLiveRequestTimeoutSeconds) * 1000;
  const pageSize = Number(root.dataset.currentStatePageSize);
  const refreshButton = document.getElementById("refresh-button");
  const clientRows = document.getElementById("live-client-rows");
  const apRows = document.getElementById("live-ap-rows");
  const clientMore = document.getElementById("live-client-more");
  const apMore = document.getElementById("live-ap-more");
  const filters = document.getElementById("live-client-filters");
  const globalPanel = document.getElementById("home-live-global");
  const globalTitle = document.getElementById("home-live-global-title");
  const globalMessage = document.getElementById("home-live-global-message");
  const sources = {
    client: {generation: 0, controller: null, timer: null, failureCount: 0, cleanRetry: false, summary: null, acceptedAt: 0, lastCompletedAt: 0, rows: [], cursor: null, loadingMore: false},
    ap: {generation: 0, controller: null, timer: null, failureCount: 0, cleanRetry: false, summary: null, acceptedAt: 0, lastCompletedAt: 0, rows: [], cursor: null, loadingMore: false},
  };
  let stopped = false;
  let ageTimer = null;

  function node(tag, className, text) {
    const value = document.createElement(tag);
    if (className) value.className = className;
    if (text !== undefined) value.textContent = display(text);
    return value;
  }
  function setGlobal(title, message, state) {
    globalTitle.textContent = title;
    globalMessage.textContent = message;
    globalPanel.dataset.state = state || "warning";
    globalPanel.hidden = false;
  }
  function clearGlobal() { globalPanel.hidden = true; }
  function abortSource(source) {
    abortOwnedController(source, "superseded");
    if (source.timer !== null) window.clearTimeout(source.timer);
    source.timer = null;
  }
  function abortAll(reason) {
    Object.values(sources).forEach((source) => {
      abortOwnedController(source, reason);
      if (source.timer !== null) window.clearTimeout(source.timer);
      source.timer = null;
    });
    if (reason === "pagehide" && ageTimer !== null) window.clearTimeout(ageTimer);
  }
  function stop(kind) {
    stopped = true;
    abortAll(kind);
    if (kind === "session") {
      setGlobal("Session expired", "Sign in again to continue.", "error");
      const link = node("a", "button", "Sign in");
      link.href = `/admin/login?next=${encodeURIComponent(window.location.pathname)}`;
      globalPanel.append(link);
    } else if (kind === "forbidden") setGlobal("Access denied", "This Site is not available to your account.", "error");
    else setGlobal("Live Home is disabled", "Reload the page to continue.", "warning");
  }
  async function requestJson(url, source, generation) {
    const controller = new AbortController();
    if (!claimController(source, controller, generation)) throw {neutral: true};
    const timeout = window.setTimeout(() => controller.abort("timeout"), timeoutMs);
    try {
      const response = await fetch(url, {method: "GET", credentials: "same-origin", cache: "no-store", headers: {Accept: "application/json"}, signal: controller.signal});
      let payload = null;
      try { payload = await response.json(); } catch (_error) { payload = null; }
      if (!response.ok) {
        const code = payload && payload.error && typeof payload.error.code === "string" ? payload.error.code : null;
        const failure = classify(response.status, code);
        const retry = Number(response.headers.get("Retry-After"));
        failure.retryAfter = Number.isFinite(retry) && retry > 0 ? retry : 0;
        throw {liveFailure: failure};
      }
      if (source.generation !== generation || stopped) throw {neutral: true};
      return payload;
    } catch (error) {
      if (controller.signal.aborted) {
        if (neutralAbort(controller.signal.reason, document.hidden)) throw {neutral: true};
        throw {liveFailure: {global: false, retryable: true, kind: "timeout", retryAfter: 0}};
      }
      if (error && (error.liveFailure || error.neutral)) throw error;
      throw {liveFailure: {global: false, retryable: true, kind: "unavailable", retryAfter: 0}};
    } finally {
      window.clearTimeout(timeout);
      releaseController(source, controller);
    }
  }
  function paramsForClients(summary, cursor) {
    return clientParameters(summary.snapshot.cycle_id, pageSize, cursor, {
      sort: filters.elements.sort.value,
      auth: filters.elements.auth.value,
      ap: filters.elements.ap.value,
      ssid: filters.elements.ssid.value,
    });
  }
  function paramsForAps(summary, cursor) {
    const value = new URLSearchParams({cycle_id: summary.snapshot.cycle_id, limit: String(pageSize)});
    if (cursor) value.set("cursor", cursor);
    return value;
  }
  function renderFreshness(kind) {
    const source = sources[kind];
    if (!source.summary) return;
    const snapshot = source.summary.snapshot;
    const status = localFreshness(snapshot, source.summary.freshness_policy, source.acceptedAt, performance.now());
    const age = currentAge(snapshot, source.acceptedAt, performance.now());
    const label = status === "unavailable" ? "Unavailable" : `${status === "stale" ? "STALE" : "Fresh"} · age ${Math.floor(age)}s · observed ${display(snapshot.observed_at)}`;
    document.getElementById(kind === "client" ? "live-client-freshness" : "live-ap-freshness").textContent = label;
    if (kind === "client") {
      clientRows.closest(".table-scroll").hidden = status === "unavailable";
      document.getElementById("live-devices-by-ap").hidden = status === "unavailable";
      if (status === "unavailable") clientMore.hidden = true;
    } else {
      apRows.hidden = status === "unavailable";
      if (status === "unavailable") apMore.hidden = true;
    }
    if (status === "unavailable") {
      const values = unavailableValues(kind);
      if (kind === "client") {
        ["live-online", "live-authorized", "live-pending", "live-other-unknown"].forEach((id) => { document.getElementById(id).textContent = values.primary; });
        document.getElementById("live-other-detail").textContent = values.detail;
        document.getElementById("live-client-state").textContent = values.state;
        clientRows.replaceChildren();
        const byAp = document.getElementById("live-devices-by-ap");
        byAp.replaceChildren();
      } else {
        document.getElementById("live-ap-total").textContent = values.primary;
        document.getElementById("live-ap-detail").textContent = values.detail;
        document.getElementById("live-ap-count").textContent = values.count;
        document.getElementById("live-ap-state").textContent = values.state;
        apRows.replaceChildren();
        if (sources.client.summary) renderByAp();
      }
    }
  }
  function renderClientSummary() {
    const result = sources.client.summary;
    const counts = result.counts;
    document.getElementById("live-online").textContent = display(counts.online);
    document.getElementById("live-authorized").textContent = display(counts.authorized);
    document.getElementById("live-pending").textContent = display(counts.pending);
    document.getElementById("live-other-unknown").textContent = display(counts.other_unknown);
    document.getElementById("live-other-detail").textContent = `Other ${display(counts.other)} · Unknown ${display(counts.unknown)}`;
    document.getElementById("live-client-warning").hidden = !result.snapshot.latest_attempt_result || result.snapshot.latest_attempt_result === "success";
    const ssids = result.snapshot.source_scope && result.snapshot.source_scope.ssids;
    const ssidSelect = filters.elements.ssid;
    const selectedSsid = ssidSelect.value;
    ssidSelect.replaceChildren(node("option", null, "All"));
    ssidSelect.firstChild.value = "";
    if (Array.isArray(ssids)) ssids.forEach((ssid) => { const option = node("option", null, ssid); option.value = ssid; ssidSelect.append(option); });
    ssidSelect.value = retainedSelection(ssids, selectedSsid);
    document.getElementById("live-ssid-label").hidden = !Array.isArray(ssids) || ssids.length <= 1;
    if (sources.ap.rows.length) renderAps(); else renderByAp();
    renderFreshness("client");
  }
  function renderApSummary() {
    const result = sources.ap.summary;
    const counts = result.counts;
    document.getElementById("live-ap-total").textContent = `${display(counts.online)} / ${display(counts.total)}`;
    document.getElementById("live-ap-detail").textContent = `Other ${display(counts.other)} · Unknown ${display(counts.unknown)}`;
    document.getElementById("live-ap-warning").hidden = !result.snapshot.latest_attempt_result || result.snapshot.latest_attempt_result === "success";
    renderFreshness("ap");
  }
  function apLabel(mac) {
    const item = sources.ap.rows.find((value) => value.ap_mac === mac);
    return item && item.name ? `${item.name} · ${mac}` : mac;
  }
  function apEnrichment(mac) {
    const summary = sources.ap.summary;
    const effectiveFreshness = summary
      ? localFreshness(summary.snapshot, summary.freshness_policy, sources.ap.acceptedAt, performance.now())
      : "unavailable";
    return enrichmentState(sources.ap.rows, sources.ap.cursor, summary, mac, effectiveFreshness);
  }
  function renderByAp() {
    const target = document.getElementById("live-devices-by-ap");
    target.replaceChildren();
    const result = sources.client.summary;
    const effectiveFreshness = result
      ? localFreshness(result.snapshot, result.freshness_policy, sources.client.acceptedAt, performance.now())
      : "unavailable";
    if (!result || effectiveFreshness === "unavailable") { target.append(node("p", "live-detail", "Unavailable")); return; }
    const max = Math.max(1, ...result.devices_by_ap.map((item) => item.client_count));
    result.devices_by_ap.forEach((item) => {
      const row = node("div", "live-bar");
      const track = node("span", "live-bar-track");
      const fill = node("span", "live-bar-fill");
      fill.style.width = `${Math.min(100, item.client_count / max * 100)}%`;
      track.append(fill);
      const label = node("span");
      label.append(node("strong", null, apLabel(item.ap_mac)), node("br"), node("small", "live-detail", apEnrichment(item.ap_mac)));
      row.append(label, track, node("strong", null, item.client_count));
      target.append(row);
    });
    if (result.counts.ap_unknown > 0) target.append(node("p", "live-detail", `AP Unknown · ${result.counts.ap_unknown}`));
    rebuildApFilter();
  }
  function rebuildApFilter() {
    const selected = filters.elements.ap.value;
    const macs = new Set();
    if (sources.client.summary) sources.client.summary.devices_by_ap.forEach((item) => macs.add(item.ap_mac));
    sources.ap.rows.forEach((item) => macs.add(item.ap_mac));
    filters.elements.ap.replaceChildren(node("option", null, "All"));
    filters.elements.ap.firstChild.value = "";
    Array.from(macs).sort().forEach((mac) => { const option = node("option", null, apLabel(mac)); option.value = mac; filters.elements.ap.append(option); });
    filters.elements.ap.value = macs.has(selected) ? selected : "";
  }
  function clientRow(item) {
    const row = node("tr");
    const identity = node("td");
    identity.append(node("strong", null, item.name || item.hostname || item.client_mac), node("br"), node("span", "mono", item.client_mac));
    const facts = node("details", "controller-facts");
    facts.append(node("summary", null, "Controller facts"));
    const list = node("dl", "detail-list");
    [["Controller uptime", item.controller_uptime], ["Controller trafficDown", item.controller_traffic_down], ["Controller trafficUp", item.controller_traffic_up], ["Controller trafficTotal", item.controller_traffic_total]].forEach(([label, value]) => { list.append(node("dt", null, label), node("dd", null, value)); });
    facts.append(list);
    [identity, node("td", null, {authorized: "Authorized", pending: "Waiting", other: "Other", unknown: "Unknown"}[item.auth_classification]), node("td", null, item.ip), node("td", null, item.ap_name || item.ap_mac || "AP Unknown"), node("td", null, item.band), node("td", null, item.rssi), node("td", null, item.snr)].forEach((cell) => row.append(cell));
    const factCell = node("td"); factCell.append(facts); row.append(factCell);
    return row;
  }
  function renderClients(append) {
    if (!append) clientRows.replaceChildren();
    sources.client.rows.forEach((item, index) => { if (!append || index >= clientRows.children.length) clientRows.append(clientRow(item)); });
    clientMore.hidden = !sources.client.cursor;
    document.getElementById("live-client-state").textContent = sources.client.rows.length ? `Showing ${sources.client.rows.length} current device(s).` : "No devices in this current snapshot.";
  }
  function renderAps() {
    apRows.replaceChildren();
    const buckets = new Map();
    if (sources.client.summary) sources.client.summary.devices_by_ap.forEach((item) => buckets.set(item.ap_mac, item.client_count));
    sources.ap.rows.forEach((item) => {
      const row = node("article", "data-row");
      const header = node("div", "data-row-header");
      header.append(node("strong", null, item.name || item.ap_mac), node("span", "badge", item.product_status_classification));
      row.append(header, node("p", "mono", item.ap_mac), node("p", "live-detail", `Current scoped clients: ${buckets.get(item.ap_mac) || 0}`));
      apRows.append(row);
    });
    const total = sources.ap.summary && sources.ap.summary.counts.total;
    document.getElementById("live-ap-count").textContent = total === null || total === undefined
      ? ""
      : (sources.ap.cursor ? `Showing ${sources.ap.rows.length} of ${total}` : `${sources.ap.rows.length} access point(s) loaded`);
    document.getElementById("live-ap-state").textContent = sources.ap.rows.length ? "Current access points loaded." : "No access points in this current snapshot.";
    apMore.hidden = !sources.ap.cursor;
    rebuildApFilter(); renderByAp();
  }
  function schedule(kind, delaySeconds) {
    const source = sources[kind];
    if (source.timer !== null) window.clearTimeout(source.timer);
    if (stopped || document.hidden) return;
    source.timer = window.setTimeout(() => { source.timer = null; refreshGroup(kind, false); }, delaySeconds * 1000);
  }
  function handleFailure(kind, failure) {
    if (failure.global) { stop(failure.kind); return false; }
    const source = sources[kind];
    const transition = failureTransition(source, failure);
    if (transition.cleanRefresh) {
      source.cursor = null; source.rows = [];
      if (kind === "client") renderClients(false); else renderAps();
      return true;
    }
    const state = document.getElementById(kind === "client" ? "live-client-state" : "live-ap-state");
    state.textContent = failure.kind === "invalid" ? "Unexpected current-state request response. Automatic retry stopped." : "Live source unavailable; retry remains bounded.";
    if (failure.kind !== "invalid") schedule(kind, retryDelay(source.failureCount, refreshSeconds, failure.retryAfter));
    return false;
  }
  async function refreshGroup(kind, manual) {
    if (stopped || document.hidden) return;
    if (sources[kind].controller) {
      if (!manual) schedule(kind, refreshSeconds);
      return;
    }
    const source = sources[kind];
    source.generation += 1;
    const generation = source.generation;
    abortSource(source);
    let cleanRefresh = false;
    try {
      const summaryPayload = await requestJson(`${apiBase}/${kind === "client" ? "clients" : "aps"}/summary`, source, generation);
      const summary = kind === "client" ? validateClientSummary(summaryPayload, siteId) : validateApSummary(summaryPayload, siteId);
      if (!summary) throw {liveFailure: {global: false, retryable: true, kind: "unexpected", retryAfter: 0}};
      if (source.generation !== generation) return;
      source.summary = summary; source.acceptedAt = performance.now(); source.rows = []; source.cursor = null;
      if (kind === "client") { renderClientSummary(); renderClients(false); } else { renderApSummary(); renderAps(); }
      if (summary.snapshot.cycle_id !== null && summary.snapshot.freshness_status !== "unavailable") {
        const parameters = kind === "client" ? paramsForClients(summary, null) : paramsForAps(summary, null);
        const pagePayload = await requestJson(`${apiBase}/${kind === "client" ? "clients" : "aps"}?${parameters.toString()}`, source, generation);
        const valid = validatePage(pagePayload, siteId, kind, summary.snapshot);
        if (!valid) throw {liveFailure: {global: false, retryable: true, kind: "unexpected", retryAfter: 0}};
        source.rows = valid.result.items.slice(); source.cursor = valid.page.next_cursor;
        if (kind === "client") renderClients(false); else renderAps();
      }
      source.failureCount = 0; source.cleanRetry = false; clearGlobal();
      source.lastCompletedAt = performance.now();
      document.getElementById("home-live-announcement").textContent = `Home updated. ${sources.client.summary && sources.client.summary.counts.online !== null ? sources.client.summary.counts.online : "unknown"} devices online.`;
      schedule(kind, refreshSeconds);
    } catch (error) {
      if (!(error && error.neutral)) cleanRefresh = handleFailure(kind, error && error.liveFailure ? error.liveFailure : {global: false, retryable: true, kind: "unexpected", retryAfter: 0});
    } finally {
      refreshButton.disabled = false;
    }
    if (cleanRefresh && canStartCleanRefresh(source, generation, stopped, document.hidden)) {
      await Promise.resolve();
      if (canStartCleanRefresh(source, generation, stopped, document.hidden)) await refreshGroup(kind, true);
    }
  }
  async function loadMore(kind) {
    const source = sources[kind];
    if (source.loadingMore || !source.cursor || !source.summary || stopped) return;
    source.loadingMore = true;
    const generation = source.generation;
    const cursor = source.cursor;
    const identity = `${siteId}|${source.summary.snapshot.cycle_id}|${source.summary.snapshot.source_scope_hash}|${cursor}`;
    let cleanRefresh = false;
    try {
      const parameters = kind === "client" ? paramsForClients(source.summary, cursor) : paramsForAps(source.summary, cursor);
      const payload = await requestJson(`${apiBase}/${kind === "client" ? "clients" : "aps"}?${parameters.toString()}`, source, generation);
      const valid = validatePage(payload, siteId, kind, source.summary.snapshot);
      const currentIdentity = `${siteId}|${source.summary.snapshot.cycle_id}|${source.summary.snapshot.source_scope_hash}|${cursor}`;
      if (!valid || identity !== currentIdentity || source.generation !== generation) throw {liveFailure: {global: false, retryable: true, kind: "unexpected", retryAfter: 0}};
      source.rows.push(...valid.result.items); source.cursor = valid.page.next_cursor;
      if (kind === "client") renderClients(true); else renderAps();
    } catch (error) {
      if (!(error && error.neutral)) cleanRefresh = handleFailure(kind, error && error.liveFailure ? error.liveFailure : {global: false, retryable: true, kind: "unexpected", retryAfter: 0});
    } finally { source.loadingMore = false; }
    if (cleanRefresh && canStartCleanRefresh(source, generation, stopped, document.hidden)) {
      await Promise.resolve();
      if (canStartCleanRefresh(source, generation, stopped, document.hidden)) await refreshGroup(kind, true);
    }
  }
  function refreshAll() {
    if (stopped || document.hidden) return;
    refreshButton.disabled = true;
    abortAll("superseded");
    Promise.allSettled([refreshGroup("client", true), refreshGroup("ap", true)]).finally(() => { refreshButton.disabled = false; });
  }
  refreshButton.addEventListener("click", refreshAll);
  clientMore.addEventListener("click", () => loadMore("client"));
  apMore.addEventListener("click", () => loadMore("ap"));
  filters.addEventListener("change", () => {
    const source = sources.client;
    abortSource(source);
    source.generation += 1;
    resetClientState(source, {
      clearRows: () => clientRows.replaceChildren(),
      hideMore: () => { clientMore.hidden = true; },
      loading: () => {
        clientRows.closest(".table-scroll").hidden = false;
        document.getElementById("live-client-state").textContent = "Loading filtered current clients…";
      },
    });
    refreshGroup("client", true);
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) abortAll("hidden");
    else if (!stopped) {
      Object.entries(sources).forEach(([kind, source]) => {
        const elapsed = source.lastCompletedAt ? (performance.now() - source.lastCompletedAt) / 1000 : refreshSeconds;
        if (!source.summary || elapsed >= refreshSeconds) refreshGroup(kind, false);
        else schedule(kind, refreshSeconds - elapsed);
      });
    }
  });
  window.addEventListener("pagehide", () => { stopped = true; abortAll("pagehide"); });
  function scheduleAgeTick() {
    if (stopped) return;
    ageTimer = window.setTimeout(() => {
      ageTimer = null;
      if (!document.hidden) { renderFreshness("client"); renderFreshness("ap"); }
      scheduleAgeTick();
    }, 1000);
  }
  scheduleAgeTick();
  refreshAll();
}());

(function () {
  "use strict";

  const API_VERSION = "admin.read.v1";
  const SOURCES = new Set(["wired", "lan"]);
  const FRESHNESS = new Set(["fresh", "stale", "unavailable"]);
  const FRESHNESS_REASONS = new Set(["within_freshness_window", "within_stale_window", "age_exceeded", "clock_anomaly", "no_complete_snapshot", "source_unavailable"]);
  const COVERAGE = new Set(["complete", "partial", "none"]);
  const COVERAGE_REASONS = new Set(["missing_direction", "missing_pair", "temporal_skew", "no_valid_rate", "empty_population"]);
  const SELECTION_REASONS = new Set(["no_complete_snapshot", "empty_population", "primary_full_coverage", "fallback_full_coverage", "fallback_higher_coverage", "primary_preferred_tie_or_higher"]);
  const RATE_REASONS = new Set(["ok", "no_baseline", "counter_reset", "gap_too_large", "invalid_elapsed", "source_unavailable"]);
  const RATE_STATUS = new Set(["valid", "partial", "unavailable"]);
  const LATEST_STATES = new Set(["none", "running", "completed", "abandoned"]);
  const LATEST_RESULTS = new Set(["success", "partial", "failed", "shutdown"]);
  const UTC_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/;
  const BACKOFF = [60, 120, 300];

  function object(value) { return value && typeof value === "object" && !Array.isArray(value); }
  function integer(value) { return typeof value === "number" && Number.isInteger(value) && value >= 0; }
  function numberOrNull(value) { return value === null || (typeof value === "number" && Number.isFinite(value) && value >= 0); }
  function stringOrNull(value) { return value === null || typeof value === "string"; }
  function canonicalUtc(value) {
    if (typeof value !== "string" || !UTC_PATTERN.test(value)) return false;
    const parsed = new Date(value);
    return !Number.isNaN(parsed.getTime()) && parsed.toISOString() === value;
  }
  function optionalUtc(value) { return value === null || canonicalUtc(value); }
  function envelope(payload, siteId) {
    return object(payload) && payload.api_version === API_VERSION && payload.site_id === siteId && object(payload.result);
  }
  function latestAttempt(snapshot) {
    if (!LATEST_STATES.has(snapshot.latest_attempt_state)
      || !(snapshot.latest_attempt_result === null || LATEST_RESULTS.has(snapshot.latest_attempt_result))
      || !optionalUtc(snapshot.latest_attempt_at)) return false;
    if (snapshot.latest_attempt_state === "none") return snapshot.latest_attempt_result === null && snapshot.latest_attempt_at === null;
    if (snapshot.latest_attempt_state === "running" || snapshot.latest_attempt_state === "abandoned") return snapshot.latest_attempt_result === null && snapshot.latest_attempt_at !== null;
    return LATEST_RESULTS.has(snapshot.latest_attempt_result) && snapshot.latest_attempt_at !== null;
  }
  function validTrafficSnapshot(snapshot) {
    if (!object(snapshot) || snapshot.source_kind !== "observation_ap_dynamic"
      || typeof snapshot.complete !== "boolean" || !stringOrNull(snapshot.cycle_id)
      || (snapshot.cycle_id !== null && snapshot.cycle_id.length === 0)
      || !canonicalUtc(snapshot.evaluated_at) || !optionalUtc(snapshot.observed_at)
      || !optionalUtc(snapshot.newest_observed_at) || !numberOrNull(snapshot.age_seconds)
      || !numberOrNull(snapshot.source_skew_seconds) || !FRESHNESS.has(snapshot.freshness_status)
      || !FRESHNESS_REASONS.has(snapshot.freshness_reason)
      || !SELECTION_REASONS.has(snapshot.selection_reason)
      || !(snapshot.selected_source === null || SOURCES.has(snapshot.selected_source))
      || typeof snapshot.using_previous_complete_snapshot !== "boolean"
      || typeof snapshot.empty_population !== "boolean" || !latestAttempt(snapshot)) return false;
    if ((snapshot.observed_at === null) !== (snapshot.newest_observed_at === null)) return false;
    if (snapshot.observed_at !== null) {
      if (new Date(snapshot.observed_at) > new Date(snapshot.newest_observed_at)
        || new Date(snapshot.newest_observed_at) > new Date(snapshot.evaluated_at)) return false;
    }
    if (snapshot.cycle_id === null) {
      return snapshot.complete === false && snapshot.selected_source === null
        && snapshot.selection_reason === "no_complete_snapshot" && snapshot.empty_population === false
        && snapshot.freshness_status === "unavailable" && snapshot.freshness_reason === "no_complete_snapshot"
        && snapshot.observed_at === null && snapshot.age_seconds === null && snapshot.source_skew_seconds === null;
    }
    if (snapshot.complete !== true || !SOURCES.has(snapshot.selected_source)) return false;
    if (snapshot.empty_population) {
      return snapshot.selected_source === "wired"
        && snapshot.selection_reason === "empty_population";
    }
    return snapshot.selection_reason !== "empty_population";
  }
  function validPolicy(policy, includeSkew) {
    return object(policy) && numberOrNull(policy.fresh_max_age_seconds) && policy.fresh_max_age_seconds !== null
      && numberOrNull(policy.unavailable_after_seconds) && policy.unavailable_after_seconds !== null
      && policy.unavailable_after_seconds >= policy.fresh_max_age_seconds
      && (!includeSkew || (numberOrNull(policy.max_ap_skew_seconds) && policy.max_ap_skew_seconds !== null));
  }
  function validSourceSelection(value, snapshot, full) {
    if (!object(value) || value.selected_source !== snapshot.selected_source
      || value.selection_reason !== snapshot.selection_reason || value.source_mixing_allowed !== false) return false;
    if (!full) return true;
    return value.primary_source === "wired" && integer(value.wired_pair_valid_ap_count) && integer(value.lan_pair_valid_ap_count);
  }
  function validCoverage(value, snapshot) {
    if (!object(value) || !COVERAGE.has(value.coverage_status)
      || value.empty_population !== snapshot.empty_population || !Array.isArray(value.coverage_reasons)
      || new Set(value.coverage_reasons).size !== value.coverage_reasons.length
      || value.coverage_reasons.some((reason) => !COVERAGE_REASONS.has(reason))) return false;
    const names = ["total_ap_count", "valid_rate_ap_count", "valid_download_ap_count", "valid_upload_ap_count", "missing_rate_ap_count", "stale_ap_count", "unavailable_ap_count", "reset_ap_count", "gap_rejected_ap_count", "no_baseline_ap_count", "source_unavailable_ap_count", "invalid_elapsed_ap_count"];
    if (!names.every((name) => integer(value[name]))) return false;
    const total = value.total_ap_count;
    if (names.slice(1).some((name) => value[name] > total)
      || value.missing_rate_ap_count !== total - value.valid_rate_ap_count) return false;
    if (snapshot.cycle_id === null) return value.coverage_status === "none" && total === 0;
    if (snapshot.empty_population) return value.coverage_status === "complete" && total === 0;
    return true;
  }
  function validTraffic(value, snapshot, coverage) {
    if (!object(value) || value.unit !== "Mbps" || !numberOrNull(value.download_mbps)
      || !numberOrNull(value.upload_mbps) || !numberOrNull(value.total_mbps)) return false;
    if (value.download_mbps !== null && value.upload_mbps !== null) {
      if (value.total_mbps === null || Math.abs(value.total_mbps - value.download_mbps - value.upload_mbps) > 1e-6) return false;
    } else if (value.total_mbps !== null) return false;
    if (coverage.coverage_status === "none" || snapshot.freshness_status === "unavailable") {
      if (value.download_mbps !== null || value.upload_mbps !== null || value.total_mbps !== null) return false;
    }
    if (snapshot.empty_population) return value.download_mbps === 0 && value.upload_mbps === 0 && value.total_mbps === 0;
    return true;
  }
  function validateTrafficSummary(payload, siteId) {
    if (!envelope(payload, siteId)) return null;
    const result = payload.result;
    if (!validTrafficSnapshot(result.snapshot) || !validPolicy(result.freshness_policy, true)
      || !validSourceSelection(result.source_selection, result.snapshot, true)
      || !validCoverage(result.coverage, result.snapshot)
      || !validTraffic(result.traffic, result.snapshot, result.coverage)) return null;
    return result;
  }
  function validateTrafficPage(payload, siteId, summary) {
    if (!envelope(payload, siteId) || !object(payload.page) || !Array.isArray(payload.result.items)) return null;
    const result = payload.result;
    const snapshot = result.snapshot;
    if (!object(snapshot) || snapshot.source_kind !== "observation_ap_dynamic"
      || snapshot.cycle_id !== summary.snapshot.cycle_id || snapshot.freshness_status === "unavailable"
      || !canonicalUtc(snapshot.evaluated_at) || !optionalUtc(snapshot.observed_at)
      || !optionalUtc(snapshot.newest_observed_at) || !numberOrNull(snapshot.age_seconds)
      || !FRESHNESS.has(snapshot.freshness_status) || !FRESHNESS_REASONS.has(snapshot.freshness_reason)
      || !validPolicy(result.freshness_policy, false)
      || !validSourceSelection(result.source_selection, summary.snapshot, false)
      || !integer(payload.page.limit) || payload.page.limit < 1 || payload.page.limit > 250
      || payload.page.cycle_id !== summary.snapshot.cycle_id
      || payload.page.selected_source !== summary.snapshot.selected_source
      || !(payload.page.next_cursor === null || (typeof payload.page.next_cursor === "string" && payload.page.next_cursor.length > 0 && payload.page.next_cursor.length <= 4096))) return null;
    if ((snapshot.observed_at === null) !== (snapshot.newest_observed_at === null)) return null;
    if (snapshot.observed_at !== null && (
      new Date(snapshot.observed_at) > new Date(snapshot.newest_observed_at)
      || new Date(snapshot.newest_observed_at) > new Date(snapshot.evaluated_at)
    )) return null;
    for (const item of result.items) {
      if (!object(item) || typeof item.ap_mac !== "string" || !stringOrNull(item.name)
        || !numberOrNull(item.download_mbps) || !numberOrNull(item.upload_mbps) || !numberOrNull(item.total_mbps)
        || !RATE_REASONS.has(item.download_reason) || !RATE_REASONS.has(item.upload_reason)
        || !RATE_STATUS.has(item.rate_status) || !optionalUtc(item.observed_at)
        || !numberOrNull(item.age_seconds) || item.selected_source !== summary.snapshot.selected_source) return null;
      if (item.observed_at !== null && new Date(item.observed_at) > new Date(snapshot.evaluated_at)) return null;
      if (item.download_mbps !== null && item.upload_mbps !== null) {
        if (item.total_mbps === null || Math.abs(item.total_mbps - item.download_mbps - item.upload_mbps) > 1e-6) return null;
      } else if (item.total_mbps !== null) return null;
    }
    return payload;
  }
  function trafficAge(snapshot, acceptedAt, now) {
    if (!snapshot || snapshot.age_seconds === null) return null;
    return snapshot.age_seconds + Math.max(0, now - acceptedAt) / 1000;
  }
  function trafficFreshness(snapshot, policy, acceptedAt, now) {
    const age = trafficAge(snapshot, acceptedAt, now);
    if (!snapshot || snapshot.freshness_status === "unavailable" || age === null || age > policy.unavailable_after_seconds) return "unavailable";
    return age <= policy.fresh_max_age_seconds ? "fresh" : "stale";
  }
  function formatMbps(value) { return value === null ? "—" : `${value.toFixed(2)} Mbps`; }
  function trafficDisplay(result, effectiveFreshness) {
    if (!result || effectiveFreshness === "unavailable") return {download: "—", upload: "—", total: "—", label: "", downloadLabel: "", uploadLabel: "", totalLabel: "", state: "Unavailable"};
    const partial = result.coverage.coverage_status === "partial";
    return {
      download: formatMbps(result.traffic.download_mbps),
      upload: formatMbps(result.traffic.upload_mbps),
      total: formatMbps(result.traffic.total_mbps),
      label: partial ? "Observed subtotal" : "",
      downloadLabel: partial && result.traffic.download_mbps !== null ? "Observed subtotal" : "",
      uploadLabel: partial && result.traffic.upload_mbps !== null ? "Observed subtotal" : "",
      totalLabel: partial && result.traffic.total_mbps !== null ? "Observed subtotal" : "",
      state: effectiveFreshness === "stale" ? "Stale" : "Current",
    };
  }
  function retryDelay(failureCount, refreshSeconds, retryAfter, jitter) {
    return Math.max(refreshSeconds, BACKOFF[Math.min(Math.max(failureCount - 1, 0), 2)], retryAfter || 0) + (jitter || 0);
  }
  function retryJitter(status, randomValue) {
    return status === 429 ? Math.max(0, Math.min(1, randomValue)) * 10 : 0;
  }
  function trafficFailureTransition(state, failure, refreshSeconds, now, randomValue) {
    if (failure.kind === "invalid" && !state.cleanRetry) {
      state.cleanRetry = true;
      state.nextEligibleAt = now;
      return {cleanRefresh: true, delaySeconds: 0};
    }
    state.failureCount += 1;
    const terminal = failure.kind === "invalid" || failure.kind === "disabled";
    const delay = terminal ? Infinity : retryDelay(
      state.failureCount,
      refreshSeconds,
      failure.retryAfter,
      retryJitter(failure.status, randomValue),
    );
    state.nextEligibleAt = terminal ? Infinity : now + delay * 1000;
    return {cleanRefresh: false, delaySeconds: delay};
  }
  function classify(status, code) {
    if (status === 401) return {global: true, retryable: false, kind: "session", status};
    if (status === 403) return {global: true, retryable: false, kind: "forbidden", status};
    if (status === 404) return {global: false, retryable: false, kind: "disabled", status};
    if (status === 400) return {global: false, retryable: false, kind: "invalid", status};
    if (status === 429 || status === 503 || status === 500) return {global: false, retryable: true, kind: code === "query_deadline" ? "timeout" : "unavailable", status};
    return {global: false, retryable: true, kind: "unexpected", status};
  }
  async function runPhasedCycle(clientOperation, apOperation, trafficOperation) {
    const phaseA = await Promise.allSettled([clientOperation(), apOperation()]);
    const traffic = await trafficOperation();
    return {phaseA, traffic};
  }
  function sourceEligible(source, manual, now) {
    if (now >= source.nextEligibleAt) return true;
    return Boolean(manual && source.failureCount === 0
      && source.nextEligibleAt !== Infinity && !source.disabled);
  }
  function runEligiblePhasedCycle(sourceStates, manual, now, operations) {
    const clock = typeof now === "function" ? now : () => now;
    const invoke = (name) => sourceEligible(sourceStates[name], manual, clock())
      ? operations[name]() : Promise.resolve({cleanRefresh: false, skipped: true});
    return runPhasedCycle(
      () => invoke("client"),
      () => invoke("ap"),
      () => invoke("traffic"),
    );
  }
  function runActivityPhase(activity, pendingSelected, manual) {
    if (!activity) return Promise.resolve();
    return pendingSelected
      ? activity.runToday(manual)
      : activity.run(manual);
  }
  function beginCoordinator(state, view) {
    if (state.active) return null;
    state.active = true;
    state.generation += 1;
    if (view) view.setBusy(true);
    return state.generation;
  }
  function endCoordinator(state, generation, view) {
    if (state.generation !== generation) return false;
    state.active = false;
    if (view) view.setBusy(false);
    return true;
  }
  function ownsGeneration(source, generation, stopped) {
    return !stopped && source.generation === generation;
  }
  function acceptTrafficSummary(source, summary, acceptedAt) {
    source.summary = summary;
    source.acceptedAt = acceptedAt;
    source.rows = [];
    source.cursor = null;
  }
  function trafficPageEligible(summary, effectiveFreshness, pageForbidden) {
    return Boolean(summary && summary.snapshot.cycle_id !== null
      && effectiveFreshness !== "unavailable" && !pageForbidden);
  }
  function clearTrafficPageState(source) {
    source.rows = [];
    source.cursor = null;
  }
  function pageFailureEffect(failure) {
    return failure && failure.status === 403 ? "preserve_summary_forbidden" : "retry_group";
  }

  if (typeof window !== "undefined") {
    window.CaptivPortalHomeTrafficTest = Object.freeze({
      acceptTrafficSummary, beginCoordinator, canonicalUtc, classify,
      clearTrafficPageState, endCoordinator, formatMbps, ownsGeneration,
      pageFailureEffect, retryDelay, retryJitter, runPhasedCycle,
      runActivityPhase, runEligiblePhasedCycle, sourceEligible,
      trafficFailureTransition,
      trafficAge, trafficDisplay, trafficFreshness, trafficPageEligible,
      validateTrafficPage, validateTrafficSummary,
    });
  }
  if (typeof document === "undefined") return;
  const root = document.getElementById("admin-page");
  if (!root || root.dataset.page !== "home" || root.dataset.homeLiveEnabled !== "true"
    || (root.dataset.homeTrafficEnabled !== "true"
      && root.dataset.homeActivityEnabled !== "true")) return;

  const live = window.CaptivPortalHomeLiveTest;
  const siteId = root.dataset.siteId;
  const currentBase = root.dataset.apiBase + "/current-state";
  const trafficBase = root.dataset.apiBase + "/current-traffic";
  const trafficEnabled = root.dataset.homeTrafficEnabled === "true";
  const liveRefresh = Number(root.dataset.homeLiveRefreshSeconds);
  const trafficRefresh = Number(root.dataset.homeTrafficRefreshSeconds);
  const liveTimeout = Number(root.dataset.homeLiveRequestTimeoutSeconds) * 1000;
  const trafficTimeout = Number(root.dataset.homeTrafficRequestTimeoutSeconds) * 1000;
  const currentPageSize = Number(root.dataset.currentStatePageSize);
  const trafficPageSize = Number(root.dataset.homeTrafficPageSize);
  const refreshButton = document.getElementById("refresh-button");
  const clientRows = document.getElementById("live-client-rows");
  const apRows = document.getElementById("live-ap-rows");
  const trafficRows = document.getElementById("traffic-ap-rows");
  const clientMore = document.getElementById("live-client-more");
  const apMore = document.getElementById("live-ap-more");
  const trafficMore = document.getElementById("traffic-ap-more");
  const filters = document.getElementById("live-client-filters");
  const globalPanel = document.getElementById("home-live-global");
  const sources = {
    client: {generation: 0, controller: null, failureCount: 0, cleanRetry: false, summary: null, acceptedAt: 0, rows: [], cursor: null, nextEligibleAt: 0},
    ap: {generation: 0, controller: null, failureCount: 0, cleanRetry: false, summary: null, acceptedAt: 0, rows: [], cursor: null, nextEligibleAt: 0},
    traffic: {generation: 0, controller: null, failureCount: 0, cleanRetry: false, summary: null, acceptedAt: 0, rows: [], cursor: null, nextEligibleAt: trafficEnabled ? 0 : Infinity, pageForbidden: false, disabled: !trafficEnabled},
  };
  const coordinator = {generation: 0, active: false, pending: false, pendingActivity: false, timer: null, activePromise: null};
  let stopped = false;
  let ageTimer = null;

  function node(tag, className, text) {
    const value = document.createElement(tag);
    if (className) value.className = className;
    if (text !== undefined) value.textContent = text === null || text === undefined ? "—" : String(text);
    return value;
  }
  function setGlobal(title, message, state) {
    document.getElementById("home-live-global-title").textContent = title;
    document.getElementById("home-live-global-message").textContent = message;
    globalPanel.dataset.state = state || "warning";
    globalPanel.hidden = false;
  }
  function clearGlobal() { globalPanel.hidden = true; }
  function activityController() { return window.CaptivPortalHomeActivityCoordinator || null; }
  function abortAll(reason) {
    Object.values(sources).forEach((source) => live.abortOwnedController(source, reason));
    const activity = activityController();
    if (activity) activity.abort(reason);
  }
  function stopAll(kind) {
    stopped = true;
    abortAll(kind);
    if (coordinator.timer !== null) window.clearTimeout(coordinator.timer);
    if (ageTimer !== null) window.clearTimeout(ageTimer);
    if (kind === "session") {
      setGlobal("Session expired", "Sign in again to continue.", "error");
      const link = node("a", "button", "Sign in");
      link.href = `/admin/login?next=${encodeURIComponent(window.location.pathname)}`;
      globalPanel.append(link);
    } else setGlobal("Access denied", "This Site is not available to your account.", "error");
  }
  async function requestJson(url, source, generation, timeoutMs) {
    const controller = new AbortController();
    if (!live.claimController(source, controller, generation)) throw {neutral: true};
    const timeout = window.setTimeout(() => controller.abort("timeout"), timeoutMs);
    try {
      const response = await fetch(url, {method: "GET", credentials: "same-origin", cache: "no-store", headers: {Accept: "application/json"}, signal: controller.signal});
      let payload = null;
      try { payload = await response.json(); } catch (_error) { payload = null; }
      if (!response.ok) {
        const code = payload && payload.error && typeof payload.error.code === "string" ? payload.error.code : null;
        const failure = classify(response.status, code);
        const header = Number(response.headers.get("Retry-After"));
        failure.retryAfter = Number.isFinite(header) && header > 0 ? header : 0;
        throw {liveFailure: failure};
      }
      if (!ownsGeneration(source, generation, stopped)) throw {neutral: true};
      return payload;
    } catch (error) {
      if (controller.signal.aborted) {
        if (live.neutralAbort(controller.signal.reason, document.hidden)) throw {neutral: true};
        throw {liveFailure: {global: false, retryable: true, kind: "timeout", retryAfter: 0, status: 0}};
      }
      if (error && (error.liveFailure || error.neutral)) throw error;
      throw {liveFailure: {global: false, retryable: true, kind: "unavailable", retryAfter: 0, status: 0}};
    } finally {
      window.clearTimeout(timeout);
      live.releaseController(source, controller);
    }
  }
  function markSuccess(source, interval) {
    source.failureCount = 0;
    source.cleanRetry = false;
    source.nextEligibleAt = performance.now() + interval * 1000;
  }
  function markFailure(source, failure, interval) {
    return trafficFailureTransition(
      source, failure, interval, performance.now(), Math.random()
    ).cleanRefresh;
  }
  function currentParams(kind, summary, cursor) {
    if (kind === "client") return live.clientParameters(summary.snapshot.cycle_id, currentPageSize, cursor, {
      sort: filters.elements.sort.value, auth: filters.elements.auth.value,
      ap: filters.elements.ap.value, ssid: filters.elements.ssid.value,
    });
    const value = new URLSearchParams({cycle_id: summary.snapshot.cycle_id, limit: String(currentPageSize)});
    if (cursor) value.set("cursor", cursor);
    return value;
  }
  function trafficParams(summary, cursor) {
    const value = new URLSearchParams({cycle_id: summary.snapshot.cycle_id, limit: String(trafficPageSize)});
    if (cursor) value.set("cursor", cursor);
    return value;
  }
  function renderCurrentFreshness(kind) {
    const source = sources[kind];
    if (!source.summary) return;
    const status = live.localFreshness(source.summary.snapshot, source.summary.freshness_policy, source.acceptedAt, performance.now());
    const age = live.currentAge(source.summary.snapshot, source.acceptedAt, performance.now());
    document.getElementById(kind === "client" ? "live-client-freshness" : "live-ap-freshness").textContent = status === "unavailable" ? "Unavailable" : `${status === "stale" ? "STALE" : "Fresh"} · age ${Math.floor(age)}s · observed ${source.summary.snapshot.observed_at || "—"}`;
    if (status !== "unavailable") return;
    const values = live.unavailableValues(kind);
    if (kind === "client") {
      ["live-online", "live-authorized", "live-pending", "live-other-unknown"].forEach((id) => { document.getElementById(id).textContent = values.primary; });
      document.getElementById("live-other-detail").textContent = values.detail;
      document.getElementById("live-client-state").textContent = values.state;
      clientRows.replaceChildren(); clientMore.hidden = true;
      document.getElementById("live-devices-by-ap").replaceChildren(node("p", "live-detail", "Unavailable"));
    } else {
      document.getElementById("live-ap-total").textContent = values.primary;
      document.getElementById("live-ap-detail").textContent = values.detail;
      document.getElementById("live-ap-count").textContent = values.count;
      document.getElementById("live-ap-state").textContent = values.state;
      apRows.replaceChildren(); apMore.hidden = true;
      renderByAp();
    }
  }
  function renderClientSummary() {
    const result = sources.client.summary;
    const counts = result.counts;
    document.getElementById("live-online").textContent = counts.online === null ? "—" : String(counts.online);
    document.getElementById("live-authorized").textContent = counts.authorized === null ? "—" : String(counts.authorized);
    document.getElementById("live-pending").textContent = counts.pending === null ? "—" : String(counts.pending);
    document.getElementById("live-other-unknown").textContent = counts.other_unknown === null ? "—" : String(counts.other_unknown);
    document.getElementById("live-other-detail").textContent = `Other ${counts.other === null ? "—" : counts.other} · Unknown ${counts.unknown === null ? "—" : counts.unknown}`;
    document.getElementById("live-client-warning").hidden = !result.snapshot.latest_attempt_result || result.snapshot.latest_attempt_result === "success";
    const ssids = result.snapshot.source_scope && result.snapshot.source_scope.ssids;
    const select = filters.elements.ssid;
    const selected = select.value;
    select.replaceChildren(node("option", null, "All")); select.firstChild.value = "";
    if (Array.isArray(ssids)) ssids.forEach((ssid) => { const option = node("option", null, ssid); option.value = ssid; select.append(option); });
    select.value = live.retainedSelection(ssids, selected);
    document.getElementById("live-ssid-label").hidden = !Array.isArray(ssids) || ssids.length <= 1;
    renderCurrentFreshness("client");
  }
  function renderApSummary() {
    const result = sources.ap.summary; const counts = result.counts;
    document.getElementById("live-ap-total").textContent = `${counts.online === null ? "—" : counts.online} / ${counts.total === null ? "—" : counts.total}`;
    document.getElementById("live-ap-detail").textContent = `Other ${counts.other === null ? "—" : counts.other} · Unknown ${counts.unknown === null ? "—" : counts.unknown}`;
    document.getElementById("live-ap-warning").hidden = !result.snapshot.latest_attempt_result || result.snapshot.latest_attempt_result === "success";
    renderCurrentFreshness("ap");
  }
  function apLabel(mac) {
    const item = sources.ap.rows.find((value) => value.ap_mac === mac);
    return item && item.name ? `${item.name} · ${mac}` : mac;
  }
  function renderByAp() {
    const target = document.getElementById("live-devices-by-ap"); target.replaceChildren();
    const result = sources.client.summary;
    const freshness = result ? live.localFreshness(result.snapshot, result.freshness_policy, sources.client.acceptedAt, performance.now()) : "unavailable";
    if (!result || freshness === "unavailable") { target.append(node("p", "live-detail", "Unavailable")); return; }
    const apFreshness = sources.ap.summary ? live.localFreshness(sources.ap.summary.snapshot, sources.ap.summary.freshness_policy, sources.ap.acceptedAt, performance.now()) : "unavailable";
    const max = Math.max(1, ...result.devices_by_ap.map((item) => item.client_count));
    result.devices_by_ap.forEach((item) => {
      const row = node("div", "live-bar"); const track = node("span", "live-bar-track"); const fill = node("span", "live-bar-fill");
      fill.style.width = `${Math.min(100, item.client_count / max * 100)}%`; track.append(fill);
      const label = node("span"); label.append(node("strong", null, apLabel(item.ap_mac)), node("br"), node("small", "live-detail", live.enrichmentState(sources.ap.rows, sources.ap.cursor, sources.ap.summary, item.ap_mac, apFreshness)));
      row.append(label, track, node("strong", null, item.client_count)); target.append(row);
    });
    if (result.counts.ap_unknown > 0) target.append(node("p", "live-detail", `AP Unknown · ${result.counts.ap_unknown}`));
    rebuildApFilter();
  }
  function rebuildApFilter() {
    const select = filters.elements.ap; const selected = select.value; const macs = new Set();
    if (sources.client.summary) sources.client.summary.devices_by_ap.forEach((item) => macs.add(item.ap_mac));
    sources.ap.rows.forEach((item) => macs.add(item.ap_mac));
    select.replaceChildren(node("option", null, "All")); select.firstChild.value = "";
    Array.from(macs).sort().forEach((mac) => { const option = node("option", null, apLabel(mac)); option.value = mac; select.append(option); });
    select.value = macs.has(selected) ? selected : "";
  }
  function renderClients() {
    clientRows.replaceChildren();
    sources.client.rows.forEach((item) => {
      const row = node("tr"); const identity = node("td");
      identity.append(node("strong", null, item.name || item.hostname || item.client_mac), node("br"), node("span", "mono", item.client_mac));
      const facts = node("details", "controller-facts"); facts.append(node("summary", null, "Controller facts"));
      const list = node("dl", "detail-list");
      [["Controller uptime", item.controller_uptime], ["Controller trafficDown", item.controller_traffic_down], ["Controller trafficUp", item.controller_traffic_up], ["Controller trafficTotal", item.controller_traffic_total]].forEach(([label, value]) => list.append(node("dt", null, label), node("dd", null, value)));
      facts.append(list);
      [identity, node("td", null, {authorized: "Authorized", pending: "Waiting", other: "Other", unknown: "Unknown"}[item.auth_classification]), node("td", null, item.ip), node("td", null, item.ap_name || item.ap_mac || "AP Unknown"), node("td", null, item.band), node("td", null, item.rssi), node("td", null, item.snr)].forEach((cell) => row.append(cell));
      const factCell = node("td"); factCell.append(facts); row.append(factCell); clientRows.append(row);
    });
    clientMore.hidden = !sources.client.cursor;
    document.getElementById("live-client-state").textContent = sources.client.rows.length ? `Showing ${sources.client.rows.length} current device(s).` : "No devices in this current snapshot.";
  }
  function renderAps() {
    apRows.replaceChildren(); const buckets = new Map();
    if (sources.client.summary) sources.client.summary.devices_by_ap.forEach((item) => buckets.set(item.ap_mac, item.client_count));
    sources.ap.rows.forEach((item) => {
      const row = node("article", "data-row"); const header = node("div", "data-row-header");
      header.append(node("strong", null, item.name || item.ap_mac), node("span", "badge", item.product_status_classification));
      row.append(header, node("p", "mono", item.ap_mac), node("p", "live-detail", `Current scoped clients: ${buckets.get(item.ap_mac) || 0}`)); apRows.append(row);
    });
    const total = sources.ap.summary && sources.ap.summary.counts.total;
    document.getElementById("live-ap-count").textContent = total === null || total === undefined ? "" : (sources.ap.cursor ? `Showing ${sources.ap.rows.length} of ${total}` : `${sources.ap.rows.length} access point(s) loaded`);
    document.getElementById("live-ap-state").textContent = sources.ap.rows.length ? "Current access points loaded." : "No access points in this current snapshot.";
    apMore.hidden = !sources.ap.cursor; rebuildApFilter(); renderByAp();
  }
  function setTrafficState(title, message, state) {
    document.getElementById("traffic-state-title").textContent = title;
    document.getElementById("traffic-state-message").textContent = message;
    document.getElementById("traffic-state").dataset.state = state || "warning";
  }
  function clearTrafficCurrent(message) {
    ["traffic-download", "traffic-upload", "traffic-total"].forEach((id) => { document.getElementById(id).textContent = "—"; });
    ["traffic-download-label", "traffic-upload-label", "traffic-total-label"].forEach((id) => { document.getElementById(id).textContent = ""; });
    document.getElementById("traffic-freshness").textContent = "Unavailable";
    document.getElementById("traffic-coverage").textContent = "Coverage unavailable";
    document.getElementById("traffic-download-coverage").textContent = "Download —/— APs";
    document.getElementById("traffic-upload-coverage").textContent = "Upload —/— APs";
    document.getElementById("traffic-both-coverage").textContent = "Both —/— APs";
    trafficRows.replaceChildren(); trafficMore.hidden = true;
    document.getElementById("traffic-ap-state").textContent = message || "Traffic AP details unavailable.";
  }
  function renderTrafficSummary() {
    const result = sources.traffic.summary;
    const effective = result ? trafficFreshness(result.snapshot, result.freshness_policy, sources.traffic.acceptedAt, performance.now()) : "unavailable";
    const shown = trafficDisplay(result, effective);
    document.getElementById("traffic-download").textContent = shown.download;
    document.getElementById("traffic-upload").textContent = shown.upload;
    document.getElementById("traffic-total").textContent = shown.total;
    document.getElementById("traffic-download-label").textContent = shown.downloadLabel;
    document.getElementById("traffic-upload-label").textContent = shown.uploadLabel;
    document.getElementById("traffic-total-label").textContent = shown.totalLabel;
    if (!result || effective === "unavailable") { clearTrafficCurrent("Traffic snapshot is unavailable."); setTrafficState("Traffic unavailable", "Persisted AP traffic cannot currently describe the Site.", "warning"); return; }
    const age = trafficAge(result.snapshot, sources.traffic.acceptedAt, performance.now());
    document.getElementById("traffic-freshness").textContent = `${effective === "stale" ? "STALE" : "Fresh"} · age ${Math.floor(age)}s · observed ${result.snapshot.observed_at || "—"}`;
    const c = result.coverage;
    document.getElementById("traffic-coverage").textContent = `${c.coverage_status === "partial" ? "Partial" : "Complete"} coverage · source ${result.source_selection.selected_source === "lan" ? "LAN" : "Wired"}`;
    document.getElementById("traffic-download-coverage").textContent = `Download ${c.valid_download_ap_count}/${c.total_ap_count} APs`;
    document.getElementById("traffic-upload-coverage").textContent = `Upload ${c.valid_upload_ap_count}/${c.total_ap_count} APs`;
    document.getElementById("traffic-both-coverage").textContent = `Both ${c.valid_rate_ap_count}/${c.total_ap_count} APs`;
    setTrafficState(effective === "stale" ? "Traffic is stale" : "Traffic updated", c.coverage_status === "partial" ? "Showing persisted observed subtotals for available AP evidence." : "Persisted AP traffic evidence is available.", effective === "stale" || c.coverage_status === "partial" ? "warning" : "ready");
  }
  function renderTrafficRows() {
    trafficRows.replaceChildren();
    sources.traffic.rows.forEach((item) => {
      const row = node("article", "data-row"); const header = node("div", "data-row-header");
      header.append(node("strong", null, item.name || item.ap_mac), node("span", "badge", item.rate_status));
      row.append(header, node("p", "mono", item.ap_mac), node("p", "live-detail", `Download ${formatMbps(item.download_mbps)} · Upload ${formatMbps(item.upload_mbps)} · Total ${formatMbps(item.total_mbps)}`), node("p", "live-detail", `Source ${item.selected_source === "lan" ? "LAN" : "Wired"} · observed ${item.observed_at || "—"}`));
      trafficRows.append(row);
    });
    trafficMore.hidden = !sources.traffic.cursor || sources.traffic.pageForbidden;
    document.getElementById("traffic-ap-state").textContent = sources.traffic.pageForbidden ? "AP traffic detail access denied." : (sources.traffic.rows.length ? `Showing ${sources.traffic.rows.length} AP traffic row(s).` : "No AP traffic rows in this snapshot.");
  }
  function renderTrafficFreshness() {
    if (!trafficEnabled) return;
    if (!sources.traffic.summary) return;
    const effective = trafficFreshness(sources.traffic.summary.snapshot, sources.traffic.summary.freshness_policy, sources.traffic.acceptedAt, performance.now());
    renderTrafficSummary();
    if (effective === "unavailable") { clearTrafficPageState(sources.traffic); renderTrafficRows(); }
  }
  function currentFailure(kind, failure) {
    if (failure.global) { stopAll(failure.kind); return false; }
    const source = sources[kind]; const clean = markFailure(source, failure, liveRefresh);
    document.getElementById(kind === "client" ? "live-client-state" : "live-ap-state").textContent = failure.kind === "invalid" ? "Unexpected current-state response; bounded clean refresh applied." : "Live source unavailable; retry remains bounded.";
    return clean;
  }
  async function refreshCurrent(kind, generation) {
    const source = sources[kind]; source.generation = generation;
    if (stopped || document.hidden || coordinator.pending) return {cleanRefresh: false};
    try {
      const stem = kind === "client" ? "clients" : "aps";
      const summaryPayload = await requestJson(`${currentBase}/${stem}/summary`, source, generation, liveTimeout);
      const summary = kind === "client" ? live.validateClientSummary(summaryPayload, siteId) : live.validateApSummary(summaryPayload, siteId);
      if (!summary) throw {liveFailure: {global: false, retryable: true, kind: "unexpected", retryAfter: 0, status: 200}};
      if (source.generation !== generation) return {cleanRefresh: false};
      source.summary = summary; source.acceptedAt = performance.now(); source.rows = []; source.cursor = null;
      if (kind === "client") { renderClientSummary(); renderClients(); } else { renderApSummary(); renderAps(); }
      if (summary.snapshot.cycle_id !== null && summary.snapshot.freshness_status !== "unavailable") {
        const params = currentParams(kind, summary, null);
        const pagePayload = await requestJson(`${currentBase}/${stem}?${params.toString()}`, source, generation, liveTimeout);
        const valid = live.validatePage(pagePayload, siteId, kind, summary.snapshot);
        if (!valid) throw {liveFailure: {global: false, retryable: true, kind: "unexpected", retryAfter: 0, status: 200}};
        source.rows = valid.result.items.slice(); source.cursor = valid.page.next_cursor;
        if (kind === "client") renderClients(); else renderAps();
      }
      markSuccess(source, liveRefresh); clearGlobal();
      return {cleanRefresh: false};
    } catch (error) {
      if (error && error.neutral) return {cleanRefresh: false};
      return {cleanRefresh: currentFailure(kind, error && error.liveFailure ? error.liveFailure : {global: false, kind: "unexpected", retryAfter: 0, status: 0})};
    }
  }
  function trafficFailure(failure) {
    if (failure.kind === "session" || (failure.kind === "forbidden" && failure.status === 403)) { stopAll(failure.kind); return false; }
    if (failure.kind === "disabled") {
      sources.traffic.disabled = true; sources.traffic.nextEligibleAt = Infinity;
      clearTrafficCurrent("Traffic is disabled; Home Live remains available.");
      setTrafficState("Traffic disabled", "Reload after the feature is enabled.", "warning");
      return false;
    }
    const clean = markFailure(sources.traffic, failure, trafficRefresh);
    setTrafficState("Traffic unavailable", failure.kind === "invalid" ? "Unexpected Traffic response; bounded clean refresh applied." : "Traffic retry remains bounded; Current State is unchanged.", "warning");
    return clean;
  }
  async function refreshTraffic(generation) {
    const source = sources.traffic; source.generation = generation;
    if (!trafficEnabled || stopped || document.hidden || coordinator.pending || source.disabled) return {cleanRefresh: false};
    try {
      const payload = await requestJson(`${trafficBase}/summary`, source, generation, trafficTimeout);
      const summary = validateTrafficSummary(payload, siteId);
      if (!summary) throw {liveFailure: {global: false, retryable: true, kind: "unexpected", retryAfter: 0, status: 200}};
      if (source.generation !== generation) return {cleanRefresh: false};
      acceptTrafficSummary(source, summary, performance.now());
      renderTrafficSummary(); renderTrafficRows();
      if (trafficPageEligible(summary, summary.snapshot.freshness_status, source.pageForbidden)) {
        try {
          const params = trafficParams(summary, null);
          const pagePayload = await requestJson(`${trafficBase}/aps?${params.toString()}`, source, generation, trafficTimeout);
          const valid = validateTrafficPage(pagePayload, siteId, summary);
          if (!valid) throw {liveFailure: {global: false, retryable: true, kind: "unexpected", retryAfter: 0, status: 200}};
          source.rows = valid.result.items.slice(); source.cursor = valid.page.next_cursor; renderTrafficRows();
        } catch (error) {
          const failure = error && error.liveFailure;
          if (failure && pageFailureEffect(failure) === "preserve_summary_forbidden") {
            source.pageForbidden = true; clearTrafficPageState(source); renderTrafficRows();
            markSuccess(source, trafficRefresh); return {cleanRefresh: false};
          }
          throw error;
        }
      }
      markSuccess(source, trafficRefresh);
      return {cleanRefresh: false};
    } catch (error) {
      if (error && error.neutral) return {cleanRefresh: false};
      return {cleanRefresh: trafficFailure(error && error.liveFailure ? error.liveFailure : {global: false, kind: "unexpected", retryAfter: 0, status: 0})};
    }
  }
  function nextDelay() {
    const finite = Object.values(sources).map((source) => source.nextEligibleAt).filter(Number.isFinite);
    const activity = activityController();
    if (activity) {
      const due = activity.nextEligibleAt();
      if (Number.isFinite(due)) finite.push(due);
    }
    if (!finite.length) return Math.min(liveRefresh, trafficRefresh) * 1000;
    return Math.max(1000, Math.min(...finite) - performance.now());
  }
  function scheduleCoordinator(delayMs) {
    if (coordinator.timer !== null) window.clearTimeout(coordinator.timer);
    if (stopped || document.hidden) return;
    coordinator.timer = window.setTimeout(() => { coordinator.timer = null; requestRefresh(false); }, delayMs);
  }
  async function performRefresh(manual) {
    const busyView = {setBusy: (value) => { refreshButton.disabled = value; }};
    const generation = beginCoordinator(coordinator, busyView);
    if (generation === null) return;
    abortAll("superseded");
    let cleanRefresh = false;
    try {
      const outcome = await runEligiblePhasedCycle(
        sources,
        manual,
        () => performance.now(),
        {
          client: () => refreshCurrent("client", generation),
          ap: () => refreshCurrent("ap", generation),
          traffic: () => coordinator.pending || stopped || document.hidden
            ? Promise.resolve({cleanRefresh: false})
            : refreshTraffic(generation),
        },
      );
      cleanRefresh = outcome.phaseA.some((item) => item.status === "fulfilled" && item.value.cleanRefresh)
        || (outcome.traffic && outcome.traffic.cleanRefresh);
      await Promise.resolve();
      const activity = activityController();
      if (activity && !coordinator.pending && !stopped && !document.hidden) {
        await runActivityPhase(activity, coordinator.pendingActivity, manual);
      }
      document.getElementById("home-live-announcement").textContent = "Home current sources updated.";
    } finally {
      endCoordinator(coordinator, generation, busyView);
    }
    if (cleanRefresh || coordinator.pending) {
      coordinator.pending = false;
      await Promise.resolve();
      if (!stopped && !document.hidden) requestRefresh(true);
    } else if (coordinator.pendingActivity) {
      coordinator.pendingActivity = false;
      requestActivitySelected();
    } else scheduleCoordinator(nextDelay());
  }
  function requestRefresh(manual) {
    if (stopped || document.hidden) return;
    if (coordinator.active) {
      if (manual) {
        coordinator.pending = true;
        Object.values(sources).forEach((source) => { source.generation += 1; });
        abortAll("superseded");
      }
      return;
    }
    coordinator.activePromise = performRefresh(manual);
  }
  async function performActivitySelected() {
    const busyView = {setBusy: (value) => { refreshButton.disabled = value; }};
    const generation = beginCoordinator(coordinator, busyView);
    if (generation === null) return;
    try {
      const activity = activityController();
      if (activity && !stopped && !document.hidden) await activity.runSelected(true);
    } finally {
      endCoordinator(coordinator, generation, busyView);
    }
    if (coordinator.pendingActivity) {
      coordinator.pendingActivity = false;
      requestActivitySelected();
    } else scheduleCoordinator(nextDelay());
  }
  function requestActivitySelected() {
    if (stopped || document.hidden) return;
    const activity = activityController();
    if (!activity) return;
    if (coordinator.active) {
      coordinator.pendingActivity = true;
      activity.abortSelected("superseded");
      return;
    }
    coordinator.activePromise = performActivitySelected();
  }
  window.CaptivPortalHomeCoordinator = Object.freeze({
    requestActivitySelected,
    stop: stopAll,
  });
  async function loadMore(kind) {
    const source = sources[kind];
    if (stopped || coordinator.active || !source.summary || !source.cursor || source.pageForbidden) return;
    const busyView = {setBusy: (value) => { refreshButton.disabled = value; }};
    const generation = beginCoordinator(coordinator, busyView);
    if (generation === null) return;
    source.generation = generation;
    try {
      const params = kind === "traffic" ? trafficParams(source.summary, source.cursor) : currentParams(kind, source.summary, source.cursor);
      const stem = kind === "traffic" ? `${trafficBase}/aps` : `${currentBase}/${kind === "client" ? "clients" : "aps"}`;
      const payload = await requestJson(`${stem}?${params.toString()}`, source, generation, kind === "traffic" ? trafficTimeout : liveTimeout);
      const valid = kind === "traffic" ? validateTrafficPage(payload, siteId, source.summary) : live.validatePage(payload, siteId, kind, source.summary.snapshot);
      if (!valid || source.generation !== generation) throw {liveFailure: {global: false, kind: "unexpected", retryAfter: 0, status: 200}};
      source.rows.push(...valid.result.items); source.cursor = valid.page.next_cursor;
      if (kind === "client") renderClients(); else if (kind === "ap") renderAps(); else renderTrafficRows();
    } catch (error) {
      if (!(error && error.neutral)) {
        const failure = error && error.liveFailure ? error.liveFailure : {global: false, kind: "unexpected", retryAfter: 0, status: 0};
        if (kind === "traffic" && pageFailureEffect(failure) === "preserve_summary_forbidden") { source.pageForbidden = true; clearTrafficPageState(source); renderTrafficRows(); }
        else if (kind === "traffic") trafficFailure(failure); else currentFailure(kind, failure);
      }
    } finally {
      endCoordinator(coordinator, generation, busyView);
      if (coordinator.pending) { coordinator.pending = false; requestRefresh(true); }
      else scheduleCoordinator(nextDelay());
    }
  }
  refreshButton.addEventListener("click", () => requestRefresh(true));
  clientMore.addEventListener("click", () => loadMore("client"));
  apMore.addEventListener("click", () => loadMore("ap"));
  if (trafficMore) trafficMore.addEventListener("click", () => loadMore("traffic"));
  filters.addEventListener("change", () => {
    live.resetClientState(sources.client, {clearRows: () => clientRows.replaceChildren(), hideMore: () => { clientMore.hidden = true; }, loading: () => { document.getElementById("live-client-state").textContent = "Loading filtered current clients…"; }});
    requestRefresh(true);
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) { coordinator.pending = false; abortAll("hidden"); if (coordinator.timer !== null) window.clearTimeout(coordinator.timer); coordinator.timer = null; }
    else if (!stopped) requestRefresh(false);
  });
  window.addEventListener("pagehide", () => { stopped = true; coordinator.pending = false; abortAll("pagehide"); if (coordinator.timer !== null) window.clearTimeout(coordinator.timer); });
  function ageTick() {
    if (stopped) return;
    ageTimer = window.setTimeout(() => {
      ageTimer = null;
      if (!document.hidden) { renderCurrentFreshness("client"); renderCurrentFreshness("ap"); renderTrafficFreshness(); }
      ageTick();
    }, 1000);
  }
  ageTick(); requestRefresh(true);
}());
