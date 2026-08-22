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
