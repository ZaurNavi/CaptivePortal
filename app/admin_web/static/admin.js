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
  if (!root || root.dataset.page !== "home" || root.dataset.homeLiveEnabled !== "true") return;

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
