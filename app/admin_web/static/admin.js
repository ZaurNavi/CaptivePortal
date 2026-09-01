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
    homeTimer: null,
    stopped: false,
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

  function legacyHealthCoordinatorEnabled() {
    return context.page === "home" && root.dataset.homeLiveEnabled !== "true"
      && root.dataset.homeHealthEnabled === "true";
  }

  function healthCoordinator() {
    return window.CaptivPortalHomeHealthCoordinator || null;
  }

  async function loadLegacyHomeWithHealth(manual) {
    await Promise.resolve();
    const health = healthCoordinator();
    const outcomes = await Promise.allSettled([
      loadHome(),
      health ? health.run(manual) : Promise.resolve(),
    ]);
    if (outcomes[0].status === "rejected") throw outcomes[0].reason;
  }

  function scheduleLegacyHome() {
    if (!legacyHealthCoordinatorEnabled() || context.stopped || document.hidden) return;
    if (context.homeTimer !== null) window.clearTimeout(context.homeTimer);
    const health = healthCoordinator();
    const due = health ? health.nextEligibleAt() : performance.now() + 60000;
    if (!Number.isFinite(due)) return;
    context.homeTimer = window.setTimeout(() => {
      context.homeTimer = null;
      run(() => loadLegacyHomeWithHealth(false)).finally(scheduleLegacyHome);
    }, Math.max(1000, due - performance.now()));
  }

  function runLegacyHome(manual) {
    if (context.homeTimer !== null) window.clearTimeout(context.homeTimer);
    context.homeTimer = null;
    return run(() => loadLegacyHomeWithHealth(manual)).finally(scheduleLegacyHome);
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
    if (context.page === "traffic") return;
    if (context.page === "home" && root.dataset.homeLiveEnabled === "true") return;
    if (context.page === "home") {
      context.operation = () => loadHome();
      if (legacyHealthCoordinatorEnabled()) {
        document.addEventListener("visibilitychange", () => {
          const health = healthCoordinator();
          if (document.hidden) {
            if (context.homeTimer !== null) window.clearTimeout(context.homeTimer);
            context.homeTimer = null;
            if (health) health.abort("hidden");
          } else runLegacyHome(false);
        });
        window.addEventListener("pagehide", () => {
          context.stopped = true;
          if (context.homeTimer !== null) window.clearTimeout(context.homeTimer);
          context.homeTimer = null;
          const health = healthCoordinator();
          if (health) health.abort("pagehide");
        });
      }
    }
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
      if (legacyHealthCoordinatorEnabled()) {
        runLegacyHome(true);
        return;
      }
      if (context.operation) run(context.operation);
      else if (context.page === "observations") run(() => loadObservations(false));
    });
    loadMoreButton.addEventListener("click", () => {
      if (context.page === "devices") run(() => loadDevices(true));
      if (context.page === "visits") run(() => loadVisits(true));
      if (context.page === "observations") run(() => loadObservations(true));
    });
    if (legacyHealthCoordinatorEnabled()) runLegacyHome(false);
    else if (context.operation) run(context.operation);
  }

  configure();
}());

(function () {
  "use strict";
  if (typeof window === "undefined" || typeof document === "undefined") return;
  const root = document.getElementById("admin-page");
  if (!root || root.dataset.page !== "traffic" || root.dataset.trafficEnabled !== "true") return;

  const refreshButton = document.getElementById("refresh-button");
  const globalState = document.getElementById("traffic-global-state");
  const globalTitle = document.getElementById("traffic-global-state-title");
  const globalMessage = document.getElementById("traffic-global-state-message");
  const emptyState = document.getElementById("traffic-empty-state");
  const panelsElement = document.getElementById("traffic-panels");
  const siteId = root.dataset.siteId;
  const apiBase = root.dataset.apiBase;
  const refreshSeconds = Number(root.dataset.trafficRefreshSeconds);
  const requestTimeoutSeconds = Number(root.dataset.trafficRequestTimeoutSeconds);
  const panels = new Map();
  const failureKinds = new Set(["session", "forbidden", "disabled", "invalid", "busy", "timeout", "unavailable", "unexpected"]);
  let scheduler = null;
  let stopped = false;
  let globalPaused = false;

  function now() {
    return typeof performance !== "undefined" && typeof performance.now === "function"
      ? performance.now() : Date.now();
  }

  function retryAfterSeconds(value) {
    if (Number.isSafeInteger(value) && value >= 0) return value;
    if (typeof value !== "string" || !/^[0-9]+$/.test(value)) return 0;
    const parsed = Number(value);
    return Number.isSafeInteger(parsed) ? parsed : 0;
  }

  function safeFailure(kind, status, code, retryAfter) {
    const safeKind = failureKinds.has(kind) ? kind : "unexpected";
    return Object.freeze({
      kind: safeKind,
      status: Number.isInteger(status) ? status : 0,
      code: typeof code === "string" && /^[a-z][a-z0-9_]{0,63}$/.test(code) ? code : null,
      retryAfter: retryAfterSeconds(retryAfter),
    });
  }

  function classifyTrafficHttp(status, payload, retryAfter) {
    const code = payload && payload.error && typeof payload.error.code === "string"
      ? payload.error.code : null;
    if (status === 401) return safeFailure("session", status, code, retryAfter);
    if (status === 403) return safeFailure("forbidden", status, code, retryAfter);
    if (status === 404) return safeFailure("disabled", status, code, retryAfter);
    if (status === 400) return safeFailure("invalid", status, code, retryAfter);
    if (status === 429) return safeFailure("busy", status, code, retryAfter);
    if (status === 503 && code === "query_deadline") return safeFailure("timeout", status, code, retryAfter);
    if (status === 503) return safeFailure("unavailable", status, code, retryAfter);
    return safeFailure("unexpected", status, code, retryAfter);
  }

  function neutralAbort(reason) {
    return reason === "superseded" || reason === "hidden" || reason === "pagehide"
      || reason === "session" || reason === "forbidden";
  }

  function validateSpec(spec) {
    if (!spec || typeof spec !== "object" || Array.isArray(spec)) return false;
    if (typeof spec.key !== "string" || !/^[a-z][a-z0-9_-]{0,63}$/.test(spec.key)) return false;
    if (typeof spec.autoRefresh !== "boolean" || typeof spec.load !== "function" || typeof spec.render !== "function") return false;
    return (spec.renderLoading === undefined || typeof spec.renderLoading === "function")
      && (spec.renderFailure === undefined || typeof spec.renderFailure === "function")
      && (spec.prepareRefresh === undefined || typeof spec.prepareRefresh === "function");
  }

  function updateFoundationState() {
    const empty = panels.size === 0;
    emptyState.hidden = !empty;
    refreshButton.disabled = empty || globalPaused || stopped;
  }

  function clearScheduler() {
    if (scheduler !== null) window.clearTimeout(scheduler);
    scheduler = null;
  }

  function abortPanel(state, reason) {
    if (state.controller) state.controller.abort(reason);
  }

  function showGlobal(failure) {
    globalPaused = true;
    globalState.hidden = false;
    globalState.dataset.state = "error";
    globalTitle.textContent = failure.kind === "session" ? "Session expired" : "Access denied";
    globalMessage.textContent = failure.kind === "session"
      ? "Sign in again to continue."
      : "This account cannot access Traffic for the current Site.";
    clearScheduler();
    panels.forEach((state) => abortPanel(state, failure.kind));
    updateFoundationState();
  }

  function validateTrafficUrl(value) {
    if (typeof value !== "string" || !value.startsWith("/")) {
      throw {trafficFailure: safeFailure("invalid", 0, null, null)};
    }
    const resolved = new URL(value, window.location.origin);
    const expectedPrefix = `${apiBase}/traffic/`;
    if (resolved.origin !== window.location.origin || !resolved.pathname.startsWith(expectedPrefix)) {
      throw {trafficFailure: safeFailure("invalid", 0, null, null)};
    }
    return resolved.pathname + resolved.search;
  }

  async function requestJson(value, state, generation, controller) {
    const url = validateTrafficUrl(value);
    const timeout = window.setTimeout(() => {
      if (state.controller === controller && state.generation === generation) controller.abort("timeout");
    }, requestTimeoutSeconds * 1000);
    try {
      let response;
      try {
        response = await fetch(url, {
          method: "GET",
          credentials: "same-origin",
          cache: "no-store",
          headers: {Accept: "application/json"},
          signal: controller.signal,
        });
      } catch (_error) {
        if (controller.signal.aborted) {
          if (neutralAbort(controller.signal.reason)) throw {trafficNeutral: true};
          if (controller.signal.reason === "timeout") throw {trafficFailure: safeFailure("timeout", 0, null, null)};
        }
        throw {trafficFailure: safeFailure("unavailable", 0, null, null)};
      }
      let payload;
      try {
        payload = await response.json();
      } catch (_error) {
        throw {trafficFailure: classifyTrafficHttp(response.status, null, response.headers.get("Retry-After"))};
      }
      if (!response.ok) {
        const errorPayload = payload && typeof payload === "object" && !Array.isArray(payload)
          ? payload : null;
        throw {trafficFailure: classifyTrafficHttp(response.status, errorPayload, response.headers.get("Retry-After"))};
      }
      if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
        throw {trafficFailure: safeFailure("unexpected", response.status, null, null)};
      }
      if (!("result" in payload)) throw {trafficFailure: safeFailure("unexpected", response.status, null, null)};
      return payload;
    } finally {
      window.clearTimeout(timeout);
    }
  }

  function backoffMilliseconds(state, failure) {
    const local = Math.min(300, refreshSeconds * (2 ** Math.max(0, state.failureCount - 1)));
    return Math.max(failure.retryAfter, local) * 1000;
  }

  function schedule() {
    clearScheduler();
    if (stopped || globalPaused || document.hidden || panels.size === 0) return;
    const eligible = Array.from(panels.values()).filter((state) => (
      (state.spec.autoRefresh || state.pending) && !state.inFlight && !state.suspended
    ));
    if (!eligible.length) return;
    const nextAt = Math.min(...eligible.map((state) => state.nextEligibleAt));
    scheduler = window.setTimeout(() => {
      scheduler = null;
      if (stopped || globalPaused || document.hidden) return;
      const instant = now();
      const runs = eligible.filter((state) => state.nextEligibleAt <= instant).map((state) => runPanel(state, {manual: false, initial: false}));
      Promise.allSettled(runs).then(schedule);
    }, Math.max(0, nextAt - now()));
  }

  function runPanel(state, options) {
    const manual = options && options.manual === true;
    const initial = options && options.initial === true;
    if (stopped || globalPaused || document.hidden) return Promise.resolve(false);
    const instant = now();
    if (state.suspended) {
      if (!manual) return Promise.resolve(false);
      state.suspended = false;
    }
    if (instant < state.nextEligibleAt) {
      schedule();
      return Promise.resolve(false);
    }
    if (state.inFlight) {
      if (!manual) return state.inFlight;
      abortPanel(state, "superseded");
    }
    state.generation += 1;
    state.pending = false;
    const generation = state.generation;
    const controller = new AbortController();
    state.controller = controller;
    if (state.spec.renderLoading) state.spec.renderLoading();
    const execution = Promise.resolve().then(() => state.spec.load(Object.freeze({
      siteId,
      apiBase,
      manual,
      generation,
      requestJson: (url) => requestJson(url, state, generation, controller),
    }))).then((value) => {
      if (state.generation !== generation || controller.signal.aborted) return false;
      state.spec.render(value);
      state.initialComplete = true;
      state.failureCount = 0;
      state.nextEligibleAt = Math.max(
        state.nextEligibleAt,
        state.spec.autoRefresh ? now() + refreshSeconds * 1000 : 0,
      );
      return true;
    }).catch((error) => {
      if (error && error.trafficNeutral) return false;
      if (state.generation !== generation || neutralAbort(controller.signal.reason)) return false;
      const candidate = error && error.trafficFailure ? error.trafficFailure : null;
      const failure = candidate
        ? safeFailure(candidate.kind, candidate.status, candidate.code, candidate.retryAfter)
        : safeFailure("unexpected", 0, null, null);
      state.initialComplete = true;
      if (failure.kind === "session" || failure.kind === "forbidden") {
        showGlobal(failure);
        return false;
      }
      if (state.spec.renderFailure) state.spec.renderFailure(failure);
      if (failure.kind === "busy" || failure.kind === "timeout" || failure.kind === "unavailable") {
        state.failureCount += 1;
        state.nextEligibleAt = Math.max(
          state.nextEligibleAt,
          now() + backoffMilliseconds(state, failure),
        );
      } else {
        state.suspended = true;
      }
      return false;
    }).finally(() => {
      if (state.controller === controller) state.controller = null;
      if (state.inFlight === execution) state.inFlight = null;
      schedule();
    });
    state.inFlight = execution;
    return execution;
  }

  function registerPanel(spec) {
    if (!validateSpec(spec)) throw new TypeError("Invalid Traffic panel registration");
    if (panels.has(spec.key)) throw new Error("Duplicate Traffic panel key");
    const state = {
      spec: Object.freeze({...spec}),
      generation: 0,
      controller: null,
      inFlight: null,
      failureCount: 0,
      nextEligibleAt: 0,
      suspended: false,
      initialComplete: false,
      pending: false,
    };
    panels.set(spec.key, state);
    updateFoundationState();
    Promise.resolve().then(() => runPanel(state, {manual: false, initial: true}));
    return true;
  }

  function refreshPanel(key, options) {
    const state = typeof key === "string" ? panels.get(key) : null;
    if (!state) return Promise.resolve(false);
    return runPanel(state, {manual: Boolean(options && options.manual), initial: false});
  }

  function queuePanel(key, options) {
    const state = typeof key === "string" ? panels.get(key) : null;
    if (!state || stopped || globalPaused) return false;
    const notBefore = options && Number.isFinite(options.notBefore)
      ? Math.max(0, options.notBefore) : 0;
    state.suspended = false;
    state.pending = true;
    state.nextEligibleAt = Math.max(state.nextEligibleAt, notBefore);
    schedule();
    return true;
  }

  function refreshAll(options) {
    if (panels.size === 0) return Promise.resolve([]);
    return Promise.all(Array.from(panels.values()).map((state) => {
      const manual = Boolean(options && options.manual);
      if (state.spec.prepareRefresh) {
        const notBefore = state.spec.prepareRefresh({manual});
        queuePanel(state.spec.key, {notBefore});
        return Promise.resolve(true);
      }
      return runPanel(state, {manual, initial: false});
    }));
  }

  refreshButton.addEventListener("click", () => refreshAll({manual: true}));
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      clearScheduler();
      panels.forEach((state) => abortPanel(state, "hidden"));
    } else {
      const instant = now();
      panels.forEach((state) => {
        if (state.inFlight) {
          state.inFlight.finally(() => {
            if (!stopped && !globalPaused && !document.hidden && !state.inFlight
                && (!state.initialComplete || (state.spec.autoRefresh && state.nextEligibleAt <= now()))) {
              runPanel(state, {manual: false, initial: !state.initialComplete});
            }
          });
          return;
        }
        if (!state.inFlight && (!state.initialComplete || (state.spec.autoRefresh && state.nextEligibleAt <= instant))) {
          runPanel(state, {manual: false, initial: !state.initialComplete});
        }
      });
      schedule();
    }
  });
  window.addEventListener("pagehide", () => {
    stopped = true;
    clearScheduler();
    panels.forEach((state) => abortPanel(state, "pagehide"));
    updateFoundationState();
  });
  window.CaptivPortalTrafficCoordinator = Object.freeze({
    registerPanel, refreshPanel, refreshAll, queuePanel,
  });
  updateFoundationState();
}());

/* TRAFFIC_CURRENT_PANEL_START */
(function () {
  "use strict";
  if (typeof window === "undefined" || typeof document === "undefined") return;
  const root = document.getElementById("admin-page");
  const coordinator = window.CaptivPortalTrafficCoordinator;
  if (!root || root.dataset.page !== "traffic" || root.dataset.trafficEnabled !== "true"
      || !coordinator || typeof coordinator.registerPanel !== "function") return;

  const elements = {
    panel: document.getElementById("traffic-current-panel"),
    state: document.getElementById("traffic-current-state"),
    title: document.getElementById("traffic-current-state-title"),
    message: document.getElementById("traffic-current-state-message"),
    download: document.getElementById("traffic-current-download"),
    upload: document.getElementById("traffic-current-upload"),
    total: document.getElementById("traffic-current-total"),
    source: document.getElementById("traffic-current-source"),
    freshness: document.getElementById("traffic-current-freshness"),
    coverage: document.getElementById("traffic-current-coverage"),
    updated: document.getElementById("traffic-current-updated"),
  };
  if (Object.values(elements).some((value) => !value)) return;

  const FRESHNESS = new Set(["fresh", "stale", "unavailable"]);
  const COVERAGE = new Set(["complete", "partial", "none"]);
  const SOURCES = new Set(["wired", "lan"]);
  const TRAFFIC_CURRENT_UTC = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/;

  function object(value) {
    return value && typeof value === "object" && !Array.isArray(value);
  }

  function metric(value) {
    return value === null || (typeof value === "number" && Number.isFinite(value) && value >= 0);
  }

  function utc(value) {
    return typeof value === "string"
      && TRAFFIC_CURRENT_UTC.test(value)
      && Number.isFinite(Date.parse(value));
  }

  function validate(payload, siteId) {
    if (!object(payload) || payload.api_version !== "admin.read.v1" || payload.site_id !== siteId
        || !object(payload.result)) throw new Error("Invalid current Traffic response");
    const result = payload.result;
    const traffic = result.traffic;
    const snapshot = result.snapshot;
    const selection = result.source_selection;
    const coverage = result.coverage;
    if (!object(traffic) || !object(snapshot) || !object(selection) || !object(coverage)
        || traffic.unit !== "Mbps"
        || !metric(traffic.download_mbps) || !metric(traffic.upload_mbps) || !metric(traffic.total_mbps)
        || !FRESHNESS.has(snapshot.freshness_status)
        || (snapshot.selected_source !== null && !SOURCES.has(snapshot.selected_source))
        || selection.selected_source !== snapshot.selected_source
        || selection.selection_reason !== snapshot.selection_reason
        || !COVERAGE.has(coverage.coverage_status)
        || !utc(snapshot.evaluated_at)
        || (snapshot.observed_at !== null && !utc(snapshot.observed_at))) {
      throw new Error("Invalid current Traffic response");
    }
    const unavailable = snapshot.freshness_status === "unavailable" || coverage.coverage_status === "none";
    if (unavailable && [traffic.download_mbps, traffic.upload_mbps, traffic.total_mbps].some((value) => value !== null)) {
      throw new Error("Invalid current Traffic response");
    }
    return Object.freeze({traffic, snapshot, coverage});
  }

  function formatMetric(value) {
    return value === null ? "—" : `${value.toFixed(2)} Mbps`;
  }

  function formatTime(value) {
    if (!utc(value)) return "—";
    return new Date(value).toLocaleString([], {dateStyle: "medium", timeStyle: "medium"});
  }

  function setMetrics(traffic) {
    elements.download.textContent = formatMetric(traffic ? traffic.download_mbps : null);
    elements.upload.textContent = formatMetric(traffic ? traffic.upload_mbps : null);
    elements.total.textContent = formatMetric(traffic ? traffic.total_mbps : null);
  }

  function renderLoading() {
    elements.state.dataset.state = "warning";
    elements.title.textContent = "Loading current network throughput…";
    elements.message.textContent = "Reading the latest persisted AP traffic evidence.";
    setMetrics(null);
    elements.source.textContent = "—";
    elements.freshness.textContent = "—";
    elements.coverage.textContent = "—";
    elements.updated.textContent = "—";
  }

  function render(value) {
    const unavailable = value.snapshot.freshness_status === "unavailable"
      || value.coverage.coverage_status === "none";
    const degraded = !unavailable && (value.snapshot.freshness_status === "stale"
      || value.coverage.coverage_status === "partial");
    elements.state.dataset.state = unavailable ? "error" : (degraded ? "warning" : "ready");
    elements.title.textContent = unavailable ? "Current throughput unavailable"
      : (degraded ? "Current throughput has limited evidence" : "Current throughput ready");
    elements.message.textContent = unavailable
      ? "No usable persisted AP traffic estimate is available."
      : (degraded ? "The estimate is based on stale or partial persisted evidence."
        : "The latest persisted AP traffic estimate is complete and fresh.");
    setMetrics(unavailable ? null : value.traffic);
    elements.source.textContent = value.snapshot.selected_source === "wired" ? "Wired"
      : (value.snapshot.selected_source === "lan" ? "LAN fallback" : "Source unavailable");
    elements.freshness.textContent = value.snapshot.freshness_status === "fresh" ? "Fresh"
      : (value.snapshot.freshness_status === "stale" ? "Stale" : "Unavailable");
    elements.coverage.textContent = value.coverage.coverage_status === "complete" ? "Complete"
      : (value.coverage.coverage_status === "partial" ? "Partial" : "Unavailable");
    elements.updated.textContent = value.snapshot.observed_at === null
      ? `Evaluated ${formatTime(value.snapshot.evaluated_at)} · observed —`
      : `Evaluated ${formatTime(value.snapshot.evaluated_at)} · observed ${formatTime(value.snapshot.observed_at)}`;
  }

  function renderFailure(failure) {
    renderLoading();
    elements.state.dataset.state = "error";
    elements.title.textContent = failure && failure.kind === "busy"
      ? "Current throughput is busy" : "Current throughput unavailable";
    elements.message.textContent = failure && failure.kind === "busy"
      ? "Try Refresh again after the current query completes."
      : "The current persisted estimate could not be loaded.";
  }

  coordinator.registerPanel({
    key: "current-network-throughput",
    autoRefresh: true,
    load: async (context) => validate(
      await context.requestJson(`${context.apiBase}/traffic/current`),
      context.siteId,
    ),
    render,
    renderLoading,
    renderFailure,
  });
}());
/* TRAFFIC_CURRENT_PANEL_END */

/* TRAFFIC_NETWORK_RANGE_CONTEXT_START */
(function () {
  "use strict";
  if (typeof window === "undefined" || typeof document === "undefined") return;
  const root = document.getElementById("admin-page");
  if (root && root.dataset.trafficIndependentRangesEnabled === "true") return;
  const range24h = document.getElementById("traffic-network-range-24h");
  const range7d = document.getElementById("traffic-network-range-7d");
  if (!root || root.dataset.page !== "traffic" || root.dataset.trafficEnabled !== "true"
      || !range24h || !range7d) return;
  const allowed = new Set(["24h", "7d"]);
  const listeners = new Set();
  let selected = "24h";

  function updateControls() {
    range24h.setAttribute("aria-pressed", selected === "24h" ? "true" : "false");
    range7d.setAttribute("aria-pressed", selected === "7d" ? "true" : "false");
  }
  function select(value) {
    if (!allowed.has(value) || value === selected) return false;
    selected = value;
    updateControls();
    listeners.forEach((listener) => listener(selected));
    return true;
  }
  function subscribe(listener) {
    if (typeof listener !== "function") throw new TypeError("Invalid Network range listener");
    listeners.add(listener);
    return () => listeners.delete(listener);
  }

  range24h.addEventListener("click", () => select("24h"));
  range7d.addEventListener("click", () => select("7d"));
  updateControls();
  window.CaptivPortalTrafficNetworkRange = Object.freeze({
    selected: () => selected,
    select,
    subscribe,
  });
}());
/* TRAFFIC_NETWORK_RANGE_CONTEXT_END */

/* TRAFFIC_HISTORY_PANEL_START */
(function () {
  "use strict";
  if (typeof window === "undefined" || typeof document === "undefined") return;
  const root = document.getElementById("admin-page");
  const coordinator = window.CaptivPortalTrafficCoordinator;
  const independentRanges = Boolean(
    root && root.dataset.trafficIndependentRangesEnabled === "true"
  );
  const rangeContext = independentRanges
    ? null : window.CaptivPortalTrafficNetworkRange;
  const panel = document.getElementById("traffic-history-panel");
  if (!root || root.dataset.page !== "traffic" || root.dataset.trafficEnabled !== "true"
      || !panel || panel.dataset.historyEnabled !== "true" || !coordinator
      || typeof coordinator.registerPanel !== "function"
      || typeof coordinator.refreshPanel !== "function"
      || (independentRanges && typeof coordinator.queuePanel !== "function")
      || (!independentRanges && (!rangeContext
        || typeof rangeContext.selected !== "function"
        || typeof rangeContext.subscribe !== "function"))) return;

  const elements = {
    state: document.getElementById("traffic-history-state"),
    title: document.getElementById("traffic-history-state-title"),
    message: document.getElementById("traffic-history-state-message"),
    applied: document.getElementById("traffic-history-applied-range"),
    coverage: document.getElementById("traffic-history-coverage"),
    watermark: document.getElementById("traffic-history-watermark"),
    gaps: document.getElementById("traffic-history-gaps"),
    transitions: document.getElementById("traffic-history-source-transitions"),
    timezone: document.getElementById("traffic-history-timezone"),
    chart: document.getElementById("traffic-history-chart-svg"),
  };
  if (Object.values(elements).some((value) => !value)) return;

  const statisticsPanel = document.getElementById("traffic-statistics-panel");
  const statisticsEnabled = Boolean(
    statisticsPanel && statisticsPanel.dataset.statisticsEnabled === "true"
  );
  const statisticsElements = statisticsEnabled ? {
    state: document.getElementById("traffic-statistics-state"),
    title: document.getElementById("traffic-statistics-state-title"),
    message: document.getElementById("traffic-statistics-state-message"),
    averageDownload: document.getElementById("traffic-statistics-average-download"),
    averageUpload: document.getElementById("traffic-statistics-average-upload"),
    averageTotal: document.getElementById("traffic-statistics-average-total"),
    peakDownload: document.getElementById("traffic-statistics-peak-download"),
    peakUpload: document.getElementById("traffic-statistics-peak-upload"),
    peakTotal: document.getElementById("traffic-statistics-peak-total"),
    applied: document.getElementById("traffic-statistics-applied-range"),
    coverage: document.getElementById("traffic-statistics-coverage"),
    intervals: document.getElementById("traffic-statistics-interval-coverage"),
    watermark: document.getElementById("traffic-statistics-watermark"),
  } : null;
  if (statisticsEnabled && Object.values(statisticsElements).some((value) => !value)) return;
  const peakPanel = document.getElementById("traffic-peak-panel");
  const peakEnabled = Boolean(peakPanel && peakPanel.dataset.peakEnabled === "true");
  const peakElements = peakEnabled ? {
    state: document.getElementById("traffic-peak-state"),
    title: document.getElementById("traffic-peak-state-title"),
    message: document.getElementById("traffic-peak-state-message"),
    download: document.getElementById("traffic-peak-download"),
    downloadAt: document.getElementById("traffic-peak-download-at"),
    upload: document.getElementById("traffic-peak-upload"),
    uploadAt: document.getElementById("traffic-peak-upload-at"),
    total: document.getElementById("traffic-peak-total"),
    totalAt: document.getElementById("traffic-peak-total-at"),
    bucket: document.getElementById("traffic-peak-bucket"),
    bucketRange: document.getElementById("traffic-peak-bucket-range"),
    hour: document.getElementById("traffic-peak-hour"),
    hourRange: document.getElementById("traffic-peak-hour-range"),
    applied: document.getElementById("traffic-peak-applied-range"),
    coverage: document.getElementById("traffic-peak-coverage"),
    watermark: document.getElementById("traffic-peak-watermark"),
    transitions: document.getElementById("traffic-peak-source-transitions"),
  } : null;
  if (peakEnabled && (!statisticsEnabled || Object.values(peakElements).some((value) => !value))) return;
  const apPanel = document.getElementById("traffic-ap-panel");
  const apEnabled = Boolean(apPanel && apPanel.dataset.apEnabled === "true");
  const apElements = apEnabled ? {
    state: document.getElementById("traffic-ap-state"),
    title: document.getElementById("traffic-ap-state-title"),
    message: document.getElementById("traffic-ap-state-message"),
    applied: document.getElementById("traffic-ap-applied-range"),
    population: document.getElementById("traffic-ap-population"),
    coverage: document.getElementById("traffic-ap-coverage"),
    current: document.getElementById("traffic-ap-current"),
    items: document.getElementById("traffic-ap-items"),
  } : null;
  if (apEnabled && Object.values(apElements).some((value) => !value)) return;
  const apSharePanel = document.getElementById("traffic-apshare-panel");
  const apShareEnabled = Boolean(
    apSharePanel && apSharePanel.dataset.apshareEnabled === "true"
  );
  const apShareElements = apShareEnabled ? {
    state: document.getElementById("traffic-apshare-state"),
    title: document.getElementById("traffic-apshare-state-title"),
    message: document.getElementById("traffic-apshare-state-message"),
    applied: document.getElementById("traffic-apshare-applied-range"),
    population: document.getElementById("traffic-apshare-population"),
    coverage: document.getElementById("traffic-apshare-coverage"),
    current: document.getElementById("traffic-apshare-current"),
    items: document.getElementById("traffic-apshare-items"),
  } : null;
  if (apShareEnabled && (!independentRanges
      || Object.values(apShareElements).some((value) => !value))) return;

  const PANEL_KEY = "network-traffic-history";
  const RANGE = Object.freeze({"24h": Object.freeze({seconds: 86400, bucket: 300, count: 288}), "7d": Object.freeze({seconds: 604800, bucket: 900, count: 672})});
  const STATUSES = new Set(["ok", "partial", "insufficient_data"]);
  const COVERAGE = new Set(["complete", "partial", "none"]);
  const BUCKET = new Set(["complete", "partial", "none"]);
  const SOURCE = new Set(["wired", "lan"]);
  const HISTORY_UTC = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/;
  let appliedRange = null;
  let accepted = null;

  function object(value) { return value && typeof value === "object" && !Array.isArray(value); }
  function count(value) { return Number.isInteger(value) && value >= 0; }
  function metric(value) { return value === null || (typeof value === "number" && Number.isFinite(value) && value >= 0); }
  function utc(value) { return typeof value === "string" && HISTORY_UTC.test(value) && Number.isFinite(Date.parse(value)); }

  function metricFamily(value) {
    if (!object(value) || ![value.download_mbps, value.upload_mbps, value.total_mbps].every(metric)) return false;
    const values = [value.download_mbps, value.upload_mbps, value.total_mbps];
    return values.every((item) => item === null) || values.every((item) => item !== null);
  }

  function validateStatistics(value, history) {
    if (!object(value) || !STATUSES.has(value.status)
        || value.metric_version !== "network_traffic_period_statistics.v1"
        || value.average_method !== "right_endpoint_sample_hold_time_weighted.v1"
        || value.peak_method !== "max_accepted_complete_site_sample.v1"
        || value.unit !== "Mbps" || !metricFamily(value.average) || !metricFamily(value.peak)
        || !object(value.interval_evidence)) throw new Error("Invalid period Statistics response");
    const evidence = value.interval_evidence;
    const countFields = ["candidate_interval_count", "accepted_interval_count",
      "excluded_gap_interval_count", "excluded_source_transition_interval_count",
      "invalid_period_interval_count", "accepted_peak_sample_count"];
    const durationFields = ["range_seconds", "accepted_interval_seconds",
      "leading_unweighted_seconds", "trailing_unweighted_seconds"];
    if (!countFields.every((key) => count(evidence[key]))
        || !durationFields.every((key) => typeof evidence[key] === "number" && Number.isFinite(evidence[key]) && evidence[key] >= 0)
        || typeof evidence.interval_coverage_ratio !== "number" || !Number.isFinite(evidence.interval_coverage_ratio)
        || evidence.interval_coverage_ratio < 0 || evidence.interval_coverage_ratio > 1
        || evidence.range_seconds !== RANGE[history.range.id].seconds
        || evidence.accepted_interval_seconds > evidence.range_seconds
        || evidence.leading_unweighted_seconds > evidence.range_seconds
        || evidence.trailing_unweighted_seconds > evidence.range_seconds
        || evidence.candidate_interval_count !== Math.max(evidence.accepted_peak_sample_count - 1, 0)
        || evidence.candidate_interval_count !== evidence.accepted_interval_count
          + evidence.invalid_period_interval_count
          + evidence.excluded_source_transition_interval_count
          + evidence.excluded_gap_interval_count
        || evidence.accepted_peak_sample_count !== history.coverage.complete_site_sample_count
        || Math.abs(evidence.interval_coverage_ratio
          - evidence.accepted_interval_seconds / evidence.range_seconds) > 1e-9) {
      throw new Error("Invalid period Statistics response");
    }
    const averageNumeric = value.average.download_mbps !== null;
    const peakNumeric = value.peak.download_mbps !== null;
    if (averageNumeric && (evidence.accepted_interval_count === 0 || evidence.accepted_interval_seconds <= 0
        || Math.abs(value.average.total_mbps - value.average.download_mbps - value.average.upload_mbps) > 1e-9)) {
      throw new Error("Invalid period Statistics response");
    }
    if (!averageNumeric && (evidence.accepted_interval_count !== 0 || evidence.accepted_interval_seconds !== 0)) {
      throw new Error("Invalid period Statistics response");
    }
    if (peakNumeric && (evidence.accepted_peak_sample_count === 0
        || value.peak.total_mbps + 1e-9 < value.peak.download_mbps
        || value.peak.total_mbps + 1e-9 < value.peak.upload_mbps
        || value.peak.total_mbps > value.peak.download_mbps + value.peak.upload_mbps + 1e-9)) {
      throw new Error("Invalid period Statistics response");
    }
    if (!peakNumeric && evidence.accepted_peak_sample_count !== 0) throw new Error("Invalid period Statistics response");
    const complete = history.status === "ok" && averageNumeric && peakNumeric
      && evidence.excluded_gap_interval_count === 0
      && evidence.excluded_source_transition_interval_count === 0
      && evidence.invalid_period_interval_count === 0;
    if ((value.status === "ok" && !complete)
        || (value.status === "partial" && (complete || (!averageNumeric && !peakNumeric)))
        || (value.status === "insufficient_data" && (averageNumeric || peakNumeric
          || evidence.accepted_interval_count !== 0 || evidence.accepted_peak_sample_count !== 0))) {
      throw new Error("Invalid period Statistics response");
    }
    return Object.freeze(value);
  }

  function validateCommonProjection(payload, siteId, requestedProducts) {
    if (!object(payload) || payload.api_version !== "admin.read.v1"
        || payload.site_id !== siteId || !object(payload.result)) {
      throw new Error("Invalid historical Traffic projection");
    }
    const value = payload.result;
    const range = value.range;
    const coverage = value.coverage;
    if (!Array.isArray(value.requested_products)
        || value.requested_products.join(",") !== requestedProducts.join(",")
        || !STATUSES.has(value.status) || !object(range) || !RANGE[range.id]
        || range.unit !== "Mbps" || range.metric_version !== "network_traffic_history.v1"
        || range.aggregation !== "mean_of_complete_site_rate_samples"
        || range.source_kind !== "observation_ap_dynamic"
        || range.sample_timestamp_semantics !== "cycle_finished_at"
        || range.bucket_alignment !== "range_start_utc"
        || range.max_site_history_buckets !== 720
        || !utc(range.from_utc) || !utc(range.to_utc)
        || !utc(range.evaluated_at_utc) || range.evaluated_at_utc !== range.to_utc
        || range.bucket_seconds !== RANGE[range.id].bucket
        || range.bucket_count !== RANGE[range.id].count
        || Date.parse(range.to_utc) - Date.parse(range.from_utc)
          !== RANGE[range.id].seconds * 1000
        || !object(coverage) || !COVERAGE.has(coverage.status)
        || coverage.bucket_count !== range.bucket_count
        || !count(coverage.complete_bucket_count)
        || !count(coverage.partial_bucket_count)
        || !count(coverage.missing_bucket_count)
        || coverage.complete_bucket_count + coverage.partial_bucket_count
          + coverage.missing_bucket_count !== range.bucket_count
        || !count(coverage.canonical_cycle_count)
        || !count(coverage.complete_site_sample_count)
        || !count(coverage.excluded_site_sample_count)
        || !count(coverage.gap_bucket_count)
        || !count(coverage.source_transition_count)
        || !object(value.quality)
        || !Object.values(value.quality).every(count)) {
      throw new Error("Invalid historical Traffic projection");
    }
    const expectedCoverage = value.status === "ok" ? "complete"
      : (value.status === "partial" ? "partial" : "none");
    if (coverage.status !== expectedCoverage) {
      throw new Error("Invalid historical Traffic projection");
    }
    const fields = {
      history: "buckets",
      statistics: "period_statistics",
      peak: "peak_load",
      aps: "ap_traffic",
      apshare: "ap_traffic_share",
    };
    for (const [product, field] of Object.entries(fields)) {
      if (Object.prototype.hasOwnProperty.call(value, field)
          !== requestedProducts.includes(product)) {
        throw new Error("Invalid historical Traffic product projection");
      }
    }
    if (Object.prototype.hasOwnProperty.call(value, "ap_bucket_axis")
        !== requestedProducts.includes("aps")) {
      throw new Error("Invalid historical Traffic AP axis projection");
    }
    return value;
  }

  function validateApAxis(axis, history) {
    if (!object(axis) || axis.bucket_count !== history.range.bucket_count
        || axis.bucket_seconds !== history.range.bucket_seconds
        || !Array.isArray(axis.bucket_start_utc)
        || axis.bucket_start_utc.length !== axis.bucket_count) {
      throw new Error("Invalid AP bucket axis");
    }
    let expected = Date.parse(history.range.from_utc);
    for (const value of axis.bucket_start_utc) {
      if (!utc(value) || Date.parse(value) !== expected) {
        throw new Error("Invalid AP bucket axis");
      }
      expected += axis.bucket_seconds * 1000;
    }
    if (expected !== Date.parse(history.range.to_utc)) {
      throw new Error("Invalid AP bucket axis");
    }
    return Object.freeze(axis);
  }

  function validateProjection(payload, siteId, requestedProducts) {
    const common = validateCommonProjection(payload, siteId, requestedProducts);
    const history = requestedProducts.includes("history")
      ? validate(payload, siteId) : Object.freeze(common);
    const statistics = requestedProducts.includes("statistics")
      ? validateStatistics(common.period_statistics, common) : null;
    const peak = requestedProducts.includes("peak")
      ? validatePeak(common.peak_load, common, statistics) : null;
    let ap = null;
    let axis = null;
    if (requestedProducts.includes("aps")) {
      axis = validateApAxis(common.ap_bucket_axis, common);
      ap = validateApTraffic(common.ap_traffic, common);
    }
    const apShare = requestedProducts.includes("apshare")
      ? validateApShare(common.ap_traffic_share, common) : null;
    return Object.freeze({common, history, statistics, peak, ap, axis, apshare: apShare});
  }

  function validatePeak(value, history, statistics) {
    if (!object(value) || !STATUSES.has(value.status)
        || value.metric_version !== "network_traffic_peak_load.v1" || value.unit !== "Mbps"
        || value.peak_value_method !== "max_accepted_complete_site_sample.v1"
        || value.peak_tie_break_method !== "earliest_peak_sample_at.v1"
        || value.sample_timestamp_semantics !== "cycle_finished_at" || !object(value.events)
        || Object.keys(value.events).sort().join(",") !== "download,total,upload") throw new Error("Invalid Peak response");
    for (const name of ["download", "upload", "total"]) {
      const event = value.events[name];
      const expected = statistics === null
        ? event.value_mbps : statistics.peak[`${name}_mbps`];
      if (!object(event) || !metric(event.value_mbps) || !count(event.occurrence_count)) throw new Error("Invalid Peak response");
      if (event.value_mbps === null) {
        if (event.sample_at_utc !== null || event.selected_source !== null || event.occurrence_count !== 0 || expected !== null) throw new Error("Invalid Peak response");
      } else if (!utc(event.sample_at_utc) || Date.parse(event.sample_at_utc) < Date.parse(history.range.from_utc)
          || Date.parse(event.sample_at_utc) >= Date.parse(history.range.to_utc) || !SOURCE.has(event.selected_source)
          || event.occurrence_count < 1
          || (statistics !== null && Math.abs(event.value_mbps - expected) > 1e-9)) throw new Error("Invalid Peak response");
    }
    const bucket = value.busiest_bucket;
    if (!object(bucket) || bucket.method !== "max_complete_history_bucket_total_mean.v1" || bucket.tie_break_method !== "earliest_bucket_start.v1" || !count(bucket.occurrence_count)) throw new Error("Invalid Peak response");
    if (bucket.status === "ok") {
      if (!utc(bucket.bucket_start_utc) || !utc(bucket.bucket_end_utc) || !metric(bucket.average_total_mbps)
          || !SOURCE.has(bucket.selected_source) || bucket.occurrence_count < 1
          || (Array.isArray(history.buckets)
            ? !history.buckets.some((item) => item.status === "complete" && item.bucket_start_utc === bucket.bucket_start_utc
              && item.bucket_end_utc === bucket.bucket_end_utc && item.selected_source === bucket.selected_source
              && Math.abs(item.total_mbps - bucket.average_total_mbps) <= 1e-9)
            : (Date.parse(bucket.bucket_end_utc) - Date.parse(bucket.bucket_start_utc)
                !== history.range.bucket_seconds * 1000
              || Date.parse(bucket.bucket_start_utc) < Date.parse(history.range.from_utc)
              || Date.parse(bucket.bucket_end_utc) > Date.parse(history.range.to_utc)))) throw new Error("Invalid Peak response");
    } else if (bucket.status !== "insufficient_data" || bucket.bucket_start_utc !== null || bucket.bucket_end_utc !== null
        || bucket.average_total_mbps !== null || bucket.selected_source !== null || bucket.occurrence_count !== 0) throw new Error("Invalid Peak response");
    const hour = value.busiest_hour;
    if (!object(hour) || Object.prototype.hasOwnProperty.call(hour, "occurrence_count") || hour.duration_seconds !== 3600
        || hour.method !== "max_complete_rolling_3600s_average_total_sample_hold.v1"
        || hour.average_method !== "right_endpoint_sample_hold_time_weighted.v1"
        || hour.tie_break_method !== "earliest_window_start.v1") throw new Error("Invalid Peak response");
    if (hour.status === "ok") {
      if (!utc(hour.window_start_utc) || !utc(hour.window_end_utc)
          || Date.parse(hour.window_end_utc) - Date.parse(hour.window_start_utc) !== 3600000
          || Date.parse(hour.window_start_utc) < Date.parse(history.range.from_utc)
          || Date.parse(hour.window_end_utc) > Date.parse(history.range.to_utc)
          || !metric(hour.average_total_mbps) || hour.accepted_interval_seconds !== 3600 || !SOURCE.has(hour.selected_source)) throw new Error("Invalid Peak response");
    } else if (hour.status !== "insufficient_data" || hour.window_start_utc !== null || hour.window_end_utc !== null
        || hour.average_total_mbps !== null || hour.accepted_interval_seconds !== null || hour.selected_source !== null) throw new Error("Invalid Peak response");
    const numeric = value.events.download.value_mbps !== null;
    const complete = history.status === "ok"
      && (statistics === null || statistics.status === "ok")
      && numeric && bucket.status === "ok" && hour.status === "ok";
    if ((value.status === "ok" && !complete) || (value.status === "partial" && (complete || !numeric))
        || (value.status === "insufficient_data" && (numeric || bucket.status !== "insufficient_data" || hour.status !== "insufficient_data"))) throw new Error("Invalid Peak response");
    return Object.freeze(value);
  }

  function validateApTraffic(value, history) {
    const statuses = new Set(["ok", "partial", "insufficient_data", "unsupported_population"]);
    const itemStatuses = new Set(["complete", "partial", "insufficient_data"]);
    const pointStatuses = new Set(["complete", "partial", "none"]);
    const nowStatuses = new Set(["valid", "partial", "unavailable"]);
    const rateReasons = new Set(["ok", "no_baseline", "counter_reset", "gap_too_large", "invalid_elapsed", "source_unavailable"]);
    const freshness = new Set(["fresh", "stale", "unavailable"]);
    const freshnessReasons = new Set(["within_freshness_window", "within_stale_window", "age_exceeded", "clock_anomaly", "no_complete_snapshot", "source_unavailable"]);
    if (!object(value) || !statuses.has(value.status)
        || value.metric_version !== "network_traffic_by_ap.v1" || value.unit !== "Mbps"
        || value.history_series_encoding !== "outer_history_bucket_aligned_du.v1"
        || value.history_bucket_method !== "mean_of_accepted_ap_rates_for_canonical_site_bucket_samples.v1"
        || value.average_method !== "right_endpoint_ap_sample_hold_time_weighted.v1"
        || value.peak_method !== "max_accepted_complete_ap_sample.v1"
        || value.ap_order_method !== "ap_mac_ascending.v1"
        || !object(value.population) || !Array.isArray(value.items)) {
      throw new Error("Invalid AP Traffic response");
    }
    const population = value.population;
    if (population.population_method !== "current_union_historical_validated.v1"
        || !count(population.population_count) || !count(population.current_population_count)
        || !count(population.historical_population_count) || population.supported_max_ap_count !== 12
        || !count(population.returned_ap_count) || typeof population.population_complete !== "boolean"
        || population.current_population_count > population.population_count
        || population.historical_population_count > population.population_count) {
      throw new Error("Invalid AP Traffic response");
    }
    if (value.status === "unsupported_population") {
      if (population.population_count <= 12 || population.returned_ap_count !== 0
          || population.population_complete !== false || value.items.length !== 0
          || value.current_snapshot !== null) throw new Error("Invalid AP Traffic response");
      return Object.freeze(value);
    }
    if (population.population_count > 12 || population.returned_ap_count !== population.population_count
        || population.population_complete !== true || value.items.length !== population.population_count) {
      throw new Error("Invalid AP Traffic response");
    }
    const snapshot = value.current_snapshot;
    if (snapshot !== null && (!object(snapshot)
        || snapshot.source_kind !== "observation_ap_dynamic"
        || typeof snapshot.cycle_id !== "string" || !snapshot.cycle_id
        || !utc(snapshot.evaluated_at)
        || ((snapshot.observed_at === null) !== (snapshot.newest_observed_at === null))
        || (snapshot.observed_at !== null && (!utc(snapshot.observed_at)
          || !utc(snapshot.newest_observed_at)
          || Date.parse(snapshot.observed_at) > Date.parse(snapshot.newest_observed_at)
          || Date.parse(snapshot.newest_observed_at) > Date.parse(snapshot.evaluated_at)))
        || !freshness.has(snapshot.freshness_status)
        || !freshnessReasons.has(snapshot.freshness_reason)
        || !SOURCE.has(snapshot.selected_source))) {
      throw new Error("Invalid AP Traffic response");
    }
    let previousMac = null;
    let anyNumeric = false;
    let allComplete = true;
    for (const item of value.items) {
      if (!object(item) || !/^(?:[0-9A-F]{2}:){5}[0-9A-F]{2}$/.test(item.ap_mac)
          || (previousMac !== null && item.ap_mac <= previousMac)
          || typeof item.display_name !== "string" || !item.display_name || item.display_name.length > 256
          || !new Set(["current", "historical", "mac_fallback"]).has(item.display_name_source)
          || (item.display_name_source === "mac_fallback" && item.display_name !== item.ap_mac)
          || !itemStatuses.has(item.status) || !object(item.history) || !object(item.now)) {
        throw new Error("Invalid AP Traffic response");
      }
      previousMac = item.ap_mac;
      const series = item.history.series;
      const coverage = item.history.coverage;
      if (!object(series) || series.encoding !== "outer_history_bucket_aligned_du.v1"
          || series.bucket_count !== history.range.bucket_count
          || !Array.isArray(series.status) || !Array.isArray(series.download_mbps)
          || !Array.isArray(series.upload_mbps)
          || series.status.length !== series.bucket_count
          || series.download_mbps.length !== series.bucket_count
          || series.upload_mbps.length !== series.bucket_count || !object(coverage)) {
        throw new Error("Invalid AP Traffic response");
      }
      for (let index = 0; index < series.bucket_count; index += 1) {
        const point = series.status[index];
        const download = series.download_mbps[index];
        const upload = series.upload_mbps[index];
        if (!pointStatuses.has(point) || !metric(download) || !metric(upload)
            || (point === "none" && (download !== null || upload !== null))
            || (point !== "none" && (download === null || upload === null))) {
          throw new Error("Invalid AP Traffic response");
        }
      }
      if (!["complete", "partial", "insufficient_data"].includes(item.history.status)
          || item.history.status !== coverage.status || !metricFamily(item.history.average)
          || !metricFamily(item.history.peak) || coverage.bucket_count !== series.bucket_count
          || !count(coverage.complete_bucket_count) || !count(coverage.partial_bucket_count)
          || !count(coverage.missing_bucket_count)
          || coverage.complete_bucket_count + coverage.partial_bucket_count + coverage.missing_bucket_count !== series.bucket_count
          || !count(coverage.sample_opportunity_count) || !count(coverage.accepted_sample_count)
          || coverage.accepted_sample_count > coverage.sample_opportunity_count
          || typeof coverage.site_accepted_interval_seconds !== "number"
          || typeof coverage.ap_accepted_interval_seconds !== "number"
          || coverage.ap_accepted_interval_seconds < 0
          || coverage.ap_accepted_interval_seconds > coverage.site_accepted_interval_seconds
          || (coverage.ap_interval_coverage_ratio !== null
              && (typeof coverage.ap_interval_coverage_ratio !== "number"
                  || coverage.ap_interval_coverage_ratio < 0 || coverage.ap_interval_coverage_ratio > 1))) {
        throw new Error("Invalid AP Traffic response");
      }
      const completePoints = series.status.filter((entry) => entry === "complete").length;
      const partialPoints = series.status.filter((entry) => entry === "partial").length;
      const missingPoints = series.status.filter((entry) => entry === "none").length;
      const expectedRatio = coverage.site_accepted_interval_seconds === 0 ? null
        : coverage.ap_accepted_interval_seconds / coverage.site_accepted_interval_seconds;
      const qualityCounts = ["no_baseline_count", "counter_reset_count", "gap_too_large_count",
        "invalid_elapsed_count", "source_unavailable_count", "missing_selected_source_sample_count",
        "source_transition_excluded_interval_count"];
      if (coverage.complete_bucket_count !== completePoints
          || coverage.partial_bucket_count !== partialPoints
          || coverage.missing_bucket_count !== missingPoints
          || !qualityCounts.every((key) => count(coverage[key]))
          || (expectedRatio === null ? coverage.ap_interval_coverage_ratio !== null
            : Math.abs(coverage.ap_interval_coverage_ratio - expectedRatio) > 1e-9)) {
        throw new Error("Invalid AP Traffic response");
      }
      const averageNumeric = item.history.average.download_mbps !== null;
      const peakNumeric = item.history.peak.download_mbps !== null;
      if ((averageNumeric !== (coverage.ap_accepted_interval_seconds > 0))
          || (peakNumeric !== (coverage.accepted_sample_count > 0))
          || (averageNumeric && Math.abs(item.history.average.total_mbps
            - item.history.average.download_mbps - item.history.average.upload_mbps) > 1e-9)
          || (peakNumeric && (item.history.peak.total_mbps + 1e-9 < item.history.peak.download_mbps
            || item.history.peak.total_mbps + 1e-9 < item.history.peak.upload_mbps
            || item.history.peak.total_mbps
              > item.history.peak.download_mbps + item.history.peak.upload_mbps + 1e-9))) {
        throw new Error("Invalid AP Traffic response");
      }
      const now = item.now;
      if (!nowStatuses.has(now.status) || !metric(now.download_mbps) || !metric(now.upload_mbps)
          || !metric(now.total_mbps) || (now.selected_source !== null && !SOURCE.has(now.selected_source))
          || !rateReasons.has(now.download_reason) || !rateReasons.has(now.upload_reason)
          || (now.observed_at !== null && !utc(now.observed_at))
          || (now.age_seconds !== null && !metric(now.age_seconds))
          || (now.total_mbps !== null && (now.download_mbps === null
            || now.upload_mbps === null || Math.abs(now.total_mbps
              - now.download_mbps - now.upload_mbps) > 1e-9))
          || (now.status === "valid" && (now.download_mbps === null || now.upload_mbps === null
              || now.total_mbps === null || !SOURCE.has(now.selected_source)
              || now.observed_at === null || now.age_seconds === null))
          || (now.status === "partial" && ((now.download_mbps === null && now.upload_mbps === null)
              || !SOURCE.has(now.selected_source) || now.observed_at === null || now.age_seconds === null))
          || (now.status === "unavailable" && (now.download_mbps !== null
              || now.upload_mbps !== null || now.total_mbps !== null))) {
        throw new Error("Invalid AP Traffic response");
      }
      const historicalNumeric = coverage.accepted_sample_count > 0;
      const currentNumeric = now.download_mbps !== null || now.upload_mbps !== null;
      if (currentNumeric && (snapshot === null || snapshot.observed_at === null
          || Date.parse(now.observed_at) < Date.parse(snapshot.observed_at)
          || Date.parse(now.observed_at) > Date.parse(snapshot.newest_observed_at))) {
        throw new Error("Invalid AP Traffic response");
      }
      const itemComplete = coverage.status === "complete" && now.status === "valid"
        && snapshot !== null && snapshot.freshness_status === "fresh";
      if ((item.status === "complete" && !itemComplete)
          || (item.status === "partial" && (itemComplete || (!historicalNumeric && !currentNumeric)))
          || (item.status === "insufficient_data" && (historicalNumeric || currentNumeric))) {
        throw new Error("Invalid AP Traffic response");
      }
      anyNumeric = anyNumeric || historicalNumeric || currentNumeric;
      allComplete = allComplete && item.status === "complete";
    }
    const complete = population.population_count > 0 && history.status === "ok" && snapshot !== null
      && snapshot.freshness_status === "fresh" && allComplete;
    if ((value.status === "ok" && !complete)
        || (value.status === "partial" && (complete || !anyNumeric))
        || (value.status === "insufficient_data" && anyNumeric)) {
      throw new Error("Invalid AP Traffic response");
    }
    return Object.freeze(value);
  }

  function validateApShare(value, history) {
    const statuses = new Set(["ok", "partial", "insufficient_data", "unsupported_population"]);
    const denominatorStatuses = new Set(["positive", "zero_traffic", "insufficient_data"]);
    if (!object(value) || !statuses.has(value.status)
        || value.metric_version !== "network_traffic_ap_share.v1"
        || value.unit !== "fraction" || value.display_unit !== "percent"
        || value.share_method !== "accepted_site_interval_integrated_ap_contribution_ratio.v1"
        || value.temporal_method !== "right_endpoint_sample_hold_time_weighted.v1"
        || value.presence_method !== "accepted_selected_source_historical_presence_in_range.v1"
        || value.absence_method !== "proven_population_member_absent_from_trusted_complete_site_sample_zero_contribution.v1"
        || value.population_method !== "current_union_historical_validated.v1"
        || value.order_method !== "total_share_desc_nulls_last_ap_mac_ascending.v1"
        || !object(value.population) || !object(value.coverage)
        || !object(value.denominators) || !Array.isArray(value.items)) {
      throw new Error("Invalid AP Traffic Share response");
    }
    const population = value.population;
    const currentAvailable = population.current_population_status === "available";
    if (population.population_method !== value.population_method
        || !count(population.population_count)
        || !count(population.historical_population_count)
        || !["available", "unavailable"].includes(population.current_population_status)
        || (currentAvailable ? !count(population.current_population_count)
          : population.current_population_count !== null)
        || population.supported_max_ap_count !== 12
        || !count(population.returned_ap_count)
        || typeof population.population_complete !== "boolean"
        || population.historical_population_count > population.population_count
        || (currentAvailable && population.current_population_count > population.population_count)
        || (!currentAvailable && (population.population_complete
          || population.population_count !== population.historical_population_count))) {
      throw new Error("Invalid AP Traffic Share response");
    }
    const coverage = value.coverage;
    const coverageCounts = ["candidate_interval_count", "accepted_interval_count",
      "excluded_gap_interval_count", "excluded_source_transition_interval_count",
      "invalid_period_interval_count", "accepted_endpoint_sample_count"];
    const coverageDurations = ["range_seconds", "accepted_interval_seconds",
      "leading_unweighted_seconds", "trailing_unweighted_seconds"];
    if (!coverageCounts.every((key) => count(coverage[key]))
        || !coverageDurations.every((key) => typeof coverage[key] === "number"
          && Number.isFinite(coverage[key]) && coverage[key] >= 0)
        || typeof coverage.interval_coverage_ratio !== "number"
        || !Number.isFinite(coverage.interval_coverage_ratio)
        || coverage.interval_coverage_ratio < 0 || coverage.interval_coverage_ratio > 1
        || coverage.range_seconds !== RANGE[history.range.id].seconds
        || coverage.accepted_interval_seconds > coverage.range_seconds
        || coverage.candidate_interval_count !== Math.max(coverage.accepted_endpoint_sample_count - 1, 0)
        || coverage.candidate_interval_count !== coverage.accepted_interval_count
          + coverage.excluded_gap_interval_count
          + coverage.excluded_source_transition_interval_count
          + coverage.invalid_period_interval_count
        || coverage.accepted_endpoint_sample_count !== history.coverage.complete_site_sample_count
        || Math.abs(coverage.interval_coverage_ratio
          - coverage.accepted_interval_seconds / coverage.range_seconds) > 1e-9) {
      throw new Error("Invalid AP Traffic Share response");
    }
    const denominators = value.denominators;
    if (!["download_status", "upload_status", "total_status"].every(
      (key) => denominatorStatuses.has(denominators[key])
    )) throw new Error("Invalid AP Traffic Share response");
    if (value.status === "unsupported_population") {
      if (population.population_count <= 12 || population.returned_ap_count !== 0
          || population.population_complete || value.items.length !== 0
          || !Object.values(denominators).every((status) => status === "insufficient_data")) {
        throw new Error("Invalid AP Traffic Share response");
      }
      return Object.freeze(value);
    }
    if (population.population_count > 12
        || population.returned_ap_count !== population.population_count
        || value.items.length !== population.population_count
        || (currentAvailable && !population.population_complete)) {
      throw new Error("Invalid AP Traffic Share response");
    }
    let previous = null;
    const fractionSums = {download: 0, upload: 0, total: 0};
    const fractionCounts = {download: 0, upload: 0, total: 0};
    for (const item of value.items) {
      if (!object(item) || !/^(?:[0-9A-F]{2}:){5}[0-9A-F]{2}$/.test(item.ap_mac)
          || typeof item.display_name !== "string" || !item.display_name
          || !["current", "historical", "mac_fallback"].includes(item.display_name_source)
          || typeof item.range_presence_proven !== "boolean"
          || !["accepted", "insufficient_data"].includes(item.evidence_status)
          || !count(item.accepted_presence_interval_count)
          || typeof item.accepted_presence_seconds !== "number"
          || !Number.isFinite(item.accepted_presence_seconds)
          || item.accepted_presence_seconds < 0
          || item.accepted_presence_interval_count > coverage.accepted_interval_count
          || item.accepted_presence_seconds > coverage.accepted_interval_seconds + 1e-9
          || ((item.accepted_presence_interval_count === 0)
            !== (Math.abs(item.accepted_presence_seconds) <= 1e-9))) {
        throw new Error("Invalid AP Traffic Share response");
      }
      const fractions = {
        download: item.download_share_fraction,
        upload: item.upload_share_fraction,
        total: item.total_share_fraction,
      };
      for (const [direction, fraction] of Object.entries(fractions)) {
        const status = denominators[`${direction}_status`];
        if (fraction !== null && (typeof fraction !== "number"
            || !Number.isFinite(fraction) || fraction < 0 || fraction > 1)) {
          throw new Error("Invalid AP Traffic Share response");
        }
        if (!item.range_presence_proven || status !== "positive") {
          if (fraction !== null) throw new Error("Invalid AP Traffic Share response");
        } else {
          if (fraction === null) throw new Error("Invalid AP Traffic Share response");
          fractionSums[direction] += fraction;
          fractionCounts[direction] += 1;
        }
      }
      if (!item.range_presence_proven && (item.evidence_status !== "insufficient_data"
          || item.accepted_presence_interval_count !== 0
          || item.accepted_presence_seconds !== 0)) {
        throw new Error("Invalid AP Traffic Share response");
      }
      if (item.range_presence_proven && item.evidence_status !== "accepted") {
        throw new Error("Invalid AP Traffic Share response");
      }
      const order = [item.total_share_fraction === null ? 1 : 0,
        -(item.total_share_fraction || 0), item.ap_mac];
      if (previous !== null && (order[0] < previous[0]
          || (order[0] === previous[0] && (order[1] < previous[1]
            || (order[1] === previous[1] && order[2] <= previous[2]))))) {
        throw new Error("Invalid AP Traffic Share response");
      }
      previous = order;
    }
    for (const direction of ["download", "upload", "total"]) {
      if (denominators[`${direction}_status`] === "positive"
          && (fractionCounts[direction] === 0
            || Math.abs(fractionSums[direction] - 1) > 1e-9)) {
        throw new Error("Invalid AP Traffic Share response");
      }
    }
    if (coverage.accepted_interval_count === 0
        && !Object.values(denominators).every((status) => status === "insufficient_data")) {
      throw new Error("Invalid AP Traffic Share response");
    }
    const complete = history.status === "ok" && currentAvailable
      && population.population_count > 0 && coverage.accepted_interval_count > 0
      && coverage.excluded_gap_interval_count === 0
      && coverage.excluded_source_transition_interval_count === 0
      && coverage.invalid_period_interval_count === 0;
    const anyPresence = value.items.some((item) => item.range_presence_proven);
    if ((value.status === "ok" && !complete)
        || (value.status === "partial" && (complete || !anyPresence))
        || (value.status === "insufficient_data" && (
          (population.population_count > 0 && coverage.accepted_interval_count > 0 && anyPresence)
          || !Object.values(denominators).every((status) => status === "insufficient_data")
          || value.items.some((item) => item.download_share_fraction !== null
            || item.upload_share_fraction !== null || item.total_share_fraction !== null)))) {
      throw new Error("Invalid AP Traffic Share response");
    }
    return Object.freeze(value);
  }

  function validate(payload, siteId) {
    if (!object(payload) || payload.api_version !== "admin.read.v1" || payload.site_id !== siteId || !object(payload.result)) {
      throw new Error("Invalid historical Traffic response");
    }
    const value = payload.result;
    const range = value.range;
    const coverage = value.coverage;
    if (!STATUSES.has(value.status) || !object(range) || !RANGE[range.id]
        || range.unit !== "Mbps" || range.metric_version !== "network_traffic_history.v1"
        || range.aggregation !== "mean_of_complete_site_rate_samples"
        || range.source_kind !== "observation_ap_dynamic"
        || range.sample_timestamp_semantics !== "cycle_finished_at"
        || range.bucket_alignment !== "range_start_utc" || range.max_site_history_buckets !== 720
        || !utc(range.from_utc) || !utc(range.to_utc) || !utc(range.evaluated_at_utc)
        || range.evaluated_at_utc !== range.to_utc
        || range.bucket_seconds !== RANGE[range.id].bucket || range.bucket_count !== RANGE[range.id].count
        || Date.parse(range.to_utc) - Date.parse(range.from_utc) !== RANGE[range.id].seconds * 1000
        || !Array.isArray(value.buckets) || value.buckets.length !== range.bucket_count
        || !object(coverage) || !COVERAGE.has(coverage.status) || coverage.bucket_count !== range.bucket_count
        || !count(coverage.complete_bucket_count) || !count(coverage.partial_bucket_count)
        || !count(coverage.missing_bucket_count)
        || coverage.complete_bucket_count + coverage.partial_bucket_count + coverage.missing_bucket_count !== range.bucket_count
        || !count(coverage.gap_bucket_count) || !count(coverage.source_transition_count)) {
      throw new Error("Invalid historical Traffic response");
    }
    const expectedCoverage = value.status === "ok" ? "complete" : (value.status === "partial" ? "partial" : "none");
    if (coverage.status !== expectedCoverage) throw new Error("Invalid historical Traffic response");
    let cursor = range.from_utc;
    const aggregate = {complete: 0, partial: 0, none: 0, samples: 0, excluded: 0, gaps: 0, transitions: 0};
    for (const bucket of value.buckets) {
      if (!object(bucket) || !BUCKET.has(bucket.status) || bucket.bucket_start_utc !== cursor
          || !utc(bucket.bucket_end_utc) || Date.parse(bucket.bucket_end_utc) <= Date.parse(bucket.bucket_start_utc)
          || Date.parse(bucket.bucket_end_utc) - Date.parse(bucket.bucket_start_utc) !== range.bucket_seconds * 1000
          || !metric(bucket.download_mbps) || !metric(bucket.upload_mbps) || !metric(bucket.total_mbps)
          || typeof bucket.selection_reason !== "string" || !bucket.selection_reason
          || typeof bucket.source_changed_from_previous !== "boolean"
          || !count(bucket.complete_site_sample_count) || !count(bucket.excluded_site_sample_count)
          || !count(bucket.gap_count_over_threshold) || !count(bucket.selected_source_skew_excluded_sample_count)) {
        throw new Error("Invalid historical Traffic response");
      }
      if (bucket.status === "none") {
        if ((bucket.selected_source !== null && !SOURCE.has(bucket.selected_source))
            || bucket.complete_site_sample_count !== 0
            || (bucket.selected_source === null && bucket.selection_reason !== "no_canonical_samples")
            || bucket.download_mbps !== null || bucket.upload_mbps !== null || bucket.total_mbps !== null) {
          throw new Error("Invalid historical Traffic response");
        }
      } else if (!SOURCE.has(bucket.selected_source) || bucket.complete_site_sample_count === 0
          || bucket.download_mbps === null || bucket.upload_mbps === null || bucket.total_mbps === null) {
        throw new Error("Invalid historical Traffic response");
      }
      aggregate[bucket.status] += 1;
      aggregate.samples += bucket.complete_site_sample_count;
      aggregate.excluded += bucket.excluded_site_sample_count;
      aggregate.gaps += bucket.gap_count_over_threshold > 0 ? 1 : 0;
      aggregate.transitions += bucket.source_changed_from_previous === true ? 1 : 0;
      cursor = bucket.bucket_end_utc;
    }
    if (cursor !== range.to_utc
        || coverage.complete_bucket_count !== aggregate.complete
        || coverage.partial_bucket_count !== aggregate.partial
        || coverage.missing_bucket_count !== aggregate.none
        || coverage.complete_site_sample_count !== aggregate.samples
        || coverage.excluded_site_sample_count !== aggregate.excluded
        || coverage.gap_bucket_count !== aggregate.gaps
        || coverage.source_transition_count !== aggregate.transitions) {
      throw new Error("Invalid historical Traffic response");
    }
    return Object.freeze(value);
  }

  function displayRange(value) { return value === "24h" ? "Last 24 hours" : "Last 7 days"; }
  function displayZone() {
    const candidate = Intl.DateTimeFormat().resolvedOptions().timeZone;
    return typeof candidate === "string" && candidate ? candidate : "UTC";
  }
  function displayTime(value) {
    return utc(value) ? new Date(value).toLocaleString([], {
      dateStyle: "medium", timeStyle: "medium", timeZone: displayZone(),
    }) : "—";
  }
  function svgElement(name, attributes) {
    const element = document.createElementNS(elements.chart.namespaceURI, name);
    Object.entries(attributes || {}).forEach(([key, value]) => element.setAttribute(key, String(value)));
    return element;
  }
  function paths(buckets, field, maximum, cssClass) {
    const output = [];
    let points = [];
    function commit() {
      if (!points.length) return;
      output.push(svgElement("polyline", {
        points: points.join(" "),
        class: cssClass,
      }));
      points = [];
    }
    buckets.forEach((bucket, index) => {
      const value = bucket[field];
      if (value === null) { commit(); return; }
      const x = 48 + (index / Math.max(1, buckets.length - 1)) * 888;
      const y = 284 - (value / maximum) * 248;
      points.push(`${x.toFixed(2)},${y.toFixed(2)}`);
    });
    commit();
    return output;
  }
  function partialMarkers(buckets, field, maximum, cssClass) {
    const output = [];
    buckets.forEach((bucket, index) => {
      const value = bucket[field];
      if (bucket.status !== "partial" || value === null) return;
      const x = 48 + (index / Math.max(1, buckets.length - 1)) * 888;
      const y = 284 - (value / maximum) * 248;
      output.push(svgElement("circle", {
        cx: x.toFixed(2), cy: y.toFixed(2), r: 4,
        class: `traffic-history-partial-marker ${cssClass}`,
      }));
    });
    return output;
  }
  function renderChart(value) {
    const numeric = value.buckets.flatMap((bucket) => [bucket.download_mbps, bucket.upload_mbps]).filter((item) => item !== null);
    const maximum = Math.max(1, ...numeric);
    const title = svgElement("title", {id: "traffic-history-chart-title"});
    title.textContent = `Download and Upload network traffic history for ${displayRange(value.range.id)}`;
    const description = svgElement("desc", {id: "traffic-history-chart-description"});
    description.textContent = `${value.coverage.complete_bucket_count} complete, ${value.coverage.partial_bucket_count} partial and ${value.coverage.missing_bucket_count} missing buckets. Missing values are rendered as gaps.`;
    const xAxis = svgElement("line", {x1: 48, y1: 284, x2: 936, y2: 284, class: "traffic-history-axis"});
    const yAxis = svgElement("line", {x1: 48, y1: 36, x2: 48, y2: 284, class: "traffic-history-axis"});
    const zeroLabel = svgElement("text", {x: 40, y: 288, class: "traffic-history-axis-label", "text-anchor": "end"});
    zeroLabel.textContent = "0";
    const maximumLabel = svgElement("text", {x: 40, y: 42, class: "traffic-history-axis-label", "text-anchor": "end"});
    maximumLabel.textContent = maximum.toFixed(2);
    const unitLabel = svgElement("text", {x: 12, y: 22, class: "traffic-history-axis-label"});
    unitLabel.textContent = "Mbps";
    const startLabel = svgElement("text", {x: 48, y: 308, class: "traffic-history-axis-label", "text-anchor": "start"});
    startLabel.textContent = displayTime(value.range.from_utc);
    const endLabel = svgElement("text", {x: 936, y: 308, class: "traffic-history-axis-label", "text-anchor": "end"});
    endLabel.textContent = displayTime(value.range.to_utc);
    elements.chart.replaceChildren(title, description, xAxis, yAxis,
      zeroLabel, maximumLabel, unitLabel, startLabel, endLabel,
      ...paths(value.buckets, "download_mbps", maximum, "traffic-history-line-download"),
      ...paths(value.buckets, "upload_mbps", maximum, "traffic-history-line-upload"),
      ...partialMarkers(value.buckets, "download_mbps", maximum, "traffic-history-partial-marker-download"),
      ...partialMarkers(value.buckets, "upload_mbps", maximum, "traffic-history-partial-marker-upload"));
  }
  function renderLoading() {
    elements.state.dataset.state = "warning";
    elements.title.textContent = accepted ? "Refreshing network traffic history…" : "Loading network traffic history…";
    elements.message.textContent = accepted
      ? `Previously loaded ${displayRange(appliedRange)} remains visible until replacement succeeds.`
      : "Reading persisted AP traffic evidence.";
    if (statisticsEnabled) {
      statisticsElements.state.dataset.state = "warning";
      statisticsElements.title.textContent = "Loading period statistics…";
      statisticsElements.message.textContent = "Reading the combined persisted History result.";
    }
    if (peakEnabled) {
      peakElements.state.dataset.state = "warning";
      peakElements.title.textContent = "Loading peak evidence…";
      peakElements.message.textContent = "Reading the combined persisted History result.";
    }
    if (apEnabled) {
      apElements.state.dataset.state = "warning";
      apElements.title.textContent = "Loading AP traffic…";
      apElements.message.textContent = "Reading the combined persisted History result and current AP evidence.";
    }
    if (apShareEnabled) {
      apShareElements.state.dataset.state = "warning";
      apShareElements.title.textContent = "Loading AP Traffic Share…";
      apShareElements.message.textContent = "Reading accepted persisted AP contribution evidence.";
    }
  }
  function formatStatistic(value) { return value === null ? "—" : `${value.toFixed(2)} Mbps`; }
  function renderStatistics(value, history) {
    if (value === null) {
      statisticsElements.state.dataset.state = "error";
      statisticsElements.title.textContent = "Period statistics unavailable";
      statisticsElements.message.textContent = "History loaded, but its Statistics evidence was invalid.";
      return;
    }
    const insufficient = value.status === "insufficient_data";
    const partial = value.status === "partial";
    statisticsElements.state.dataset.state = insufficient || partial ? "warning" : "ready";
    statisticsElements.title.textContent = insufficient ? "Period statistics insufficient"
      : (partial ? "Period statistics partial" : "Period statistics ready");
    statisticsElements.message.textContent = insufficient
      ? "No accepted numeric samples are available for this period."
      : (partial ? "Trustworthy values are shown with incomplete interval evidence."
        : "Accepted samples cover all comparable intervals in the History result.");
    const values = [value.average.download_mbps, value.average.upload_mbps, value.average.total_mbps,
      value.peak.download_mbps, value.peak.upload_mbps, value.peak.total_mbps];
    [statisticsElements.averageDownload, statisticsElements.averageUpload, statisticsElements.averageTotal,
      statisticsElements.peakDownload, statisticsElements.peakUpload, statisticsElements.peakTotal]
      .forEach((element, index) => { element.textContent = formatStatistic(values[index]); });
    statisticsElements.applied.textContent = displayRange(history.range.id);
    statisticsElements.coverage.textContent = value.status === "ok" ? "Complete"
      : (partial ? "Partial" : "Insufficient");
    const evidence = value.interval_evidence;
    statisticsElements.intervals.textContent = `${(evidence.interval_coverage_ratio * 100).toFixed(1)}% · ${evidence.accepted_interval_count}/${evidence.candidate_interval_count} intervals`;
    statisticsElements.watermark.textContent = history.coverage.source_watermark_utc === null
      ? "—" : displayTime(history.coverage.source_watermark_utc);
  }
  function renderPeak(value, history) {
    if (value === null) {
      peakElements.state.dataset.state = "error";
      peakElements.title.textContent = "Peak Load unavailable";
      peakElements.message.textContent = "History and Period Statistics remain available, but Peak evidence was invalid.";
      [peakElements.download, peakElements.upload, peakElements.total, peakElements.bucket, peakElements.hour].forEach((element) => { element.textContent = "—"; });
      [peakElements.downloadAt, peakElements.uploadAt, peakElements.totalAt, peakElements.bucketRange, peakElements.hourRange].forEach((element) => { element.textContent = "—"; });
      peakElements.transitions.textContent = "—";
      return;
    }
    const partial = value.status === "partial";
    const insufficient = value.status === "insufficient_data";
    peakElements.state.dataset.state = partial || insufficient ? "warning" : "ready";
    peakElements.title.textContent = insufficient ? "Peak evidence insufficient" : (partial ? "Peak Load partial" : "Peak Load ready");
    peakElements.message.textContent = insufficient ? "No accepted Peak samples are available for this period."
      : (partial ? "Trustworthy Peak evidence is shown; one or more temporal products are incomplete."
        : "Peak samples and complete period winners are ready.");
    for (const [name, valueElement, timeElement] of [
      ["download", peakElements.download, peakElements.downloadAt],
      ["upload", peakElements.upload, peakElements.uploadAt],
      ["total", peakElements.total, peakElements.totalAt],
    ]) {
      const event = value.events[name];
      valueElement.textContent = formatStatistic(event.value_mbps);
      timeElement.textContent = event.sample_at_utc === null ? "No accepted peak sample"
        : `Observed at ${displayTime(event.sample_at_utc)}${event.occurrence_count > 1 ? ` · First of ${event.occurrence_count} equal peaks` : ""}`;
    }
    const bucket = value.busiest_bucket;
    peakElements.bucket.textContent = formatStatistic(bucket.average_total_mbps);
    peakElements.bucketRange.textContent = bucket.status === "ok"
      ? `${displayTime(bucket.bucket_start_utc)} – ${displayTime(bucket.bucket_end_utc)}${bucket.occurrence_count > 1 ? ` · First of ${bucket.occurrence_count} equal buckets` : ""}`
      : "No complete comparable bucket";
    const hour = value.busiest_hour;
    peakElements.hour.textContent = formatStatistic(hour.average_total_mbps);
    peakElements.hourRange.textContent = hour.status === "ok"
      ? `${displayTime(hour.window_start_utc)} – ${displayTime(hour.window_end_utc)}`
      : "No complete comparable 60-minute period";
    peakElements.applied.textContent = displayRange(history.range.id);
    peakElements.coverage.textContent = history.coverage.status === "complete" ? "Complete"
      : (history.coverage.status === "partial" ? "Partial" : "No data");
    peakElements.watermark.textContent = history.coverage.source_watermark_utc === null ? "—"
      : `${displayTime(history.coverage.source_watermark_utc)} · ${history.coverage.source_age_seconds === null ? "age —" : `${Math.round(history.coverage.source_age_seconds)}s old`}`;
    peakElements.transitions.textContent = String(history.coverage.source_transition_count);
  }
  function apPath(values, statuses, maximum) {
    let path = "";
    let open = false;
    values.forEach((value, index) => {
      if (value === null || statuses[index] === "none") { open = false; return; }
      const x = 12 + (index / Math.max(1, values.length - 1)) * 456;
      const y = 108 - (value / maximum) * 92;
      path += `${open ? " L" : "M"}${x.toFixed(2)} ${y.toFixed(2)}`;
      open = true;
    });
    return path;
  }
  function apMetric(value) { return value === null ? "—" : `${value.toFixed(2)} Mbps`; }
  function renderApTraffic(value, history) {
    apElements.items.replaceChildren();
    apElements.applied.textContent = displayRange(history.range.id);
    apElements.population.textContent = `${value.population.population_count} AP`;
    if (value.status === "unsupported_population") {
      apElements.state.dataset.state = "warning";
      apElements.title.textContent = "AP population is not supported";
      apElements.message.textContent = `${value.population.population_count} APs are in this Site/range; v1 supports up to 12 without truncation.`;
      apElements.coverage.textContent = "Unsupported population";
      apElements.current.textContent = "—";
      return;
    }
    apElements.state.dataset.state = value.status === "ok" ? "ready" : "warning";
    apElements.title.textContent = value.status === "ok" ? "AP traffic ready"
      : (value.status === "partial" ? "AP traffic partial" : "AP traffic insufficient");
    apElements.message.textContent = value.status === "ok"
      ? "All supported Site AP evidence is complete."
      : "All supported Site APs are shown; missing evidence remains unavailable.";
    apElements.coverage.textContent = value.status === "ok" ? "Complete"
      : (value.status === "partial" ? "Partial" : "Insufficient");
    apElements.current.textContent = value.current_snapshot === null ? "Unavailable"
      : `${displayTime(value.current_snapshot.evaluated_at)} · ${value.current_snapshot.freshness_status} · ${value.current_snapshot.selected_source}`;
    for (const item of value.items) {
      const card = document.createElement("article");
      card.className = "card traffic-ap-card";
      card.dataset.apMac = item.ap_mac;
      const heading = document.createElement("h3");
      heading.textContent = item.display_name;
      const identity = document.createElement("p");
      identity.className = "traffic-ap-identity";
      identity.textContent = item.ap_mac;
      const svg = document.createElementNS(elements.chart.namespaceURI, "svg");
      svg.setAttribute("viewBox", "0 0 480 120");
      svg.setAttribute("role", "img");
      svg.setAttribute("aria-label", `${item.display_name} Download and Upload history`);
      const numeric = [...item.history.series.download_mbps, ...item.history.series.upload_mbps]
        .filter((entry) => entry !== null);
      const maximum = Math.max(1, ...numeric);
      const downloadPath = document.createElementNS(elements.chart.namespaceURI, "path");
      downloadPath.setAttribute("class", "traffic-history-line-download");
      downloadPath.setAttribute("d", apPath(item.history.series.download_mbps, item.history.series.status, maximum));
      const uploadPath = document.createElementNS(elements.chart.namespaceURI, "path");
      uploadPath.setAttribute("class", "traffic-history-line-upload");
      uploadPath.setAttribute("d", apPath(item.history.series.upload_mbps, item.history.series.status, maximum));
      svg.replaceChildren(downloadPath, uploadPath);
      const metrics = document.createElement("div");
      metrics.className = "traffic-ap-metrics";
      for (const [label, family] of [
        ["Now", item.now], ["Average", item.history.average], ["Peak", item.history.peak],
      ]) {
        const group = document.createElement("p");
        group.textContent = `${label}: D ${apMetric(family.download_mbps)} · U ${apMetric(family.upload_mbps)} · Total ${apMetric(family.total_mbps)}`;
        metrics.appendChild(group);
      }
      const evidence = document.createElement("p");
      evidence.className = "traffic-ap-evidence";
      const ratio = item.history.coverage.ap_interval_coverage_ratio;
      const nowAt = item.now.observed_at === null ? "observed —" : `observed ${displayTime(item.now.observed_at)}`;
      const nowAge = item.now.age_seconds === null ? "age —" : `age ${Math.round(item.now.age_seconds)}s`;
      evidence.textContent = `Coverage ${ratio === null ? "—" : `${(ratio * 100).toFixed(1)}%`} · ${item.history.status} · Now ${item.now.status} · D ${item.now.download_reason} / U ${item.now.upload_reason} · ${item.now.selected_source || "source —"} · ${nowAt} · ${nowAge}`;
      card.replaceChildren(heading, identity, svg, metrics, evidence);
      apElements.items.appendChild(card);
    }
  }
  function shareMetric(value) {
    if (value === null) return "—";
    const percent = value * 100;
    if (percent > 0 && percent < 0.01) return "<0.01%";
    return `${percent.toFixed(2)}%`;
  }
  function renderApShare(value, history) {
    apShareElements.items.replaceChildren();
    apShareElements.applied.textContent = displayRange(history.range.id);
    apShareElements.population.textContent = `${value.population.population_count} AP`;
    apShareElements.current.textContent = value.population.current_population_status === "available"
      ? `${value.population.current_population_count} current AP`
      : "Unavailable · historical population only";
    if (value.status === "unsupported_population") {
      apShareElements.state.dataset.state = "warning";
      apShareElements.title.textContent = "AP Traffic Share is not supported";
      apShareElements.message.textContent = "This Site/range population exceeds the supported 12 AP limit; no subset is shown.";
      apShareElements.coverage.textContent = "Unsupported population";
      return;
    }
    const partial = value.status === "partial";
    const insufficient = value.status === "insufficient_data";
    apShareElements.state.dataset.state = partial || insufficient ? "warning" : "ready";
    apShareElements.title.textContent = insufficient ? "AP Traffic Share is insufficient"
      : (partial ? "AP Traffic Share is partial" : "AP Traffic Share ready");
    const zeroTraffic = value.denominators.total_status === "zero_traffic";
    apShareElements.message.textContent = zeroTraffic
      ? "No accepted Network Traffic was observed in this range."
      : (insufficient
        ? "No sufficient comparable Network Traffic evidence is available for this range."
        : (partial
          ? "Shares cover accepted comparable historical evidence; current population or range evidence is incomplete."
          : "Shares cover accepted Site Network Traffic evidence for the applied range."));
    apShareElements.coverage.textContent = `${(value.coverage.interval_coverage_ratio * 100).toFixed(1)}% · ${value.coverage.accepted_interval_count}/${value.coverage.candidate_interval_count} intervals`;
    for (const item of value.items) {
      const card = document.createElement("article");
      card.className = "card traffic-ap-card";
      card.dataset.apMac = item.ap_mac;
      const heading = document.createElement("h3");
      heading.textContent = item.display_name;
      const identity = document.createElement("p");
      identity.className = "traffic-ap-identity";
      identity.textContent = item.ap_mac;
      const metrics = document.createElement("div");
      metrics.className = "traffic-ap-metrics";
      for (const [label, metric] of [
        ["Total Share", item.total_share_fraction],
        ["Download Share", item.download_share_fraction],
        ["Upload Share", item.upload_share_fraction],
      ]) {
        const row = document.createElement("p");
        row.textContent = `${label}: ${shareMetric(metric)}`;
        metrics.appendChild(row);
      }
      const evidence = document.createElement("p");
      evidence.className = "traffic-ap-evidence";
      evidence.textContent = item.range_presence_proven
        ? `${item.evidence_status} · ${item.accepted_presence_interval_count} accepted intervals · ${Math.round(item.accepted_presence_seconds)}s`
        : "Insufficient accepted historical contribution evidence";
      card.replaceChildren(heading, identity, metrics, evidence);
      apShareElements.items.appendChild(card);
    }
  }
  function renderHistory(value) {
    accepted = value;
    appliedRange = value.range.id;
    const empty = value.status === "insufficient_data";
    const partial = value.status === "partial";
    elements.state.dataset.state = empty ? "warning" : (partial ? "warning" : "ready");
    elements.title.textContent = empty ? "No historical data for this range"
      : (partial ? "History partial" : "History ready");
    elements.message.textContent = empty
      ? "No canonical persisted traffic samples are available for the selected range."
      : (partial ? "Accepted samples are shown; gaps and partial buckets remain visible."
        : "Persisted traffic history has complete bucket coverage.");
    elements.applied.textContent = displayRange(appliedRange);
    elements.coverage.textContent = value.coverage.status === "complete" ? "Complete"
      : (value.coverage.status === "partial" ? "Partial" : "No data");
    elements.watermark.textContent = value.coverage.source_watermark_utc === null ? "—"
      : `${displayTime(value.coverage.source_watermark_utc)} · ${value.coverage.source_age_seconds === null ? "age —" : `${Math.round(value.coverage.source_age_seconds)}s old`}`;
    elements.gaps.textContent = String(value.coverage.gap_bucket_count);
    elements.transitions.textContent = String(value.coverage.source_transition_count);
    elements.timezone.textContent = displayZone();
    renderChart(value);
  }
  function render(result) {
    const value = statisticsEnabled || apEnabled || apShareEnabled ? result.history : result;
    renderHistory(value);
    if (statisticsEnabled) renderStatistics(result.statistics, value);
    if (peakEnabled) renderPeak(result.peak, value);
    if (apEnabled) renderApTraffic(result.ap, value);
    if (apShareEnabled) renderApShare(result.apshare, value);
  }
  function renderFailure(failure) {
    elements.state.dataset.state = "error";
    elements.title.textContent = failure && failure.kind === "busy" ? "History query is busy" : "History unavailable";
    elements.message.textContent = accepted
      ? `Previously loaded ${displayRange(appliedRange)} remains visible. Refresh when the source is available.`
      : "Persisted network traffic history could not be loaded.";
    if (statisticsEnabled) {
      statisticsElements.state.dataset.state = "error";
      statisticsElements.title.textContent = "Period statistics unavailable";
      statisticsElements.message.textContent = "The combined persisted History request failed.";
    }
    if (peakEnabled) {
      peakElements.state.dataset.state = "error";
      peakElements.title.textContent = "Peak Load unavailable";
      peakElements.message.textContent = "The combined persisted History request failed.";
    }
    if (apEnabled) {
      apElements.state.dataset.state = "error";
      apElements.title.textContent = "AP traffic unavailable";
      apElements.message.textContent = "The combined persisted History request failed.";
    }
    if (apShareEnabled) {
      apShareElements.state.dataset.state = "error";
      apShareElements.title.textContent = "AP Traffic Share unavailable";
      apShareElements.message.textContent = "The accepted historical Share request failed.";
    }
  }
  function requestSelectedRange() {
    coordinator.refreshPanel(PANEL_KEY, {manual: true});
  }

  if (!independentRanges) {
    rangeContext.subscribe(requestSelectedRange);
    coordinator.registerPanel({
      key: PANEL_KEY,
      autoRefresh: false,
      load: async (context) => {
        const requestRange = rangeContext.selected();
        const include = peakEnabled ? (apEnabled ? "statistics,peak,aps" : "statistics,peak")
          : (statisticsEnabled ? (apEnabled ? "statistics,aps" : "statistics")
            : (apEnabled ? "aps" : null));
        const suffix = include === null ? "" : `&include=${encodeURIComponent(include)}`;
        const value = validate(
          await context.requestJson(`${context.apiBase}/traffic/history?range=${encodeURIComponent(requestRange)}${suffix}`),
          context.siteId,
        );
        let ap = null;
        if (apEnabled) ap = validateApTraffic(value.ap_traffic, value);
        if (!statisticsEnabled && !apEnabled) return value;
        let statistics = null;
        try { statistics = validateStatistics(value.period_statistics, value); } catch (_error) { statistics = null; }
        let peak = null;
        if (peakEnabled && statistics !== null) {
          try { peak = validatePeak(value.peak_load, value, statistics); } catch (_error) { peak = null; }
        }
        return Object.freeze({history: value, statistics, peak, ap});
      },
      render,
      renderLoading,
      renderFailure,
    });
    return;
  }

  const PRODUCT_ORDER = Object.freeze(["history", "statistics", "peak", "aps", "apshare"]);
  const ADMISSION_GUARD_MILLISECONDS = 10000;
  const productUi = {
    history: {state: elements.state, title: elements.title, message: elements.message},
    statistics: statisticsEnabled ? {
      state: statisticsElements.state, title: statisticsElements.title,
      message: statisticsElements.message,
    } : null,
    peak: peakEnabled ? {
      state: peakElements.state, title: peakElements.title,
      message: peakElements.message,
    } : null,
    aps: apEnabled ? {
      state: apElements.state, title: apElements.title,
      message: apElements.message,
    } : null,
    apshare: apShareEnabled ? {
      state: apShareElements.state, title: apShareElements.title,
      message: apShareElements.message,
    } : null,
  };
  const enabledProducts = PRODUCT_ORDER.filter((product) => productUi[product]);
  const states = new Map(enabledProducts.map((product) => [product, {
    product,
    selectedRange: "24h",
    appliedRange: null,
    phase: "initial",
    lastSuccessfulPayload: null,
    lastError: null,
    intentGeneration: 1,
  }]));
  const pending = new Map();
  let sequence = 0;
  let lastDispatchMonotonic = null;
  let activeBatch = null;

  function monotonicNow() {
    return typeof performance !== "undefined" && typeof performance.now === "function"
      ? performance.now() : Date.now();
  }

  function controls(product) {
    return {
      range24h: document.getElementById(`traffic-${product === "aps" ? "ap" : product}-range-24h`),
      range7d: document.getElementById(`traffic-${product === "aps" ? "ap" : product}-range-7d`),
    };
  }

  function updateControls(state) {
    const pair = controls(state.product);
    if (!pair.range24h || !pair.range7d) throw new Error("Missing Traffic range controls");
    pair.range24h.setAttribute("aria-pressed", state.selectedRange === "24h" ? "true" : "false");
    pair.range7d.setAttribute("aria-pressed", state.selectedRange === "7d" ? "true" : "false");
    pair.range24h.dataset.applied = state.appliedRange === "24h" ? "true" : "false";
    pair.range7d.dataset.applied = state.appliedRange === "7d" ? "true" : "false";
  }

  function phaseText(product, phase, state, failure) {
    const label = product === "history" ? "History" : product === "statistics"
      ? "Period statistics" : product === "peak" ? "Peak Load"
        : product === "aps" ? "AP traffic" : "AP Traffic Share";
    if (phase === "waiting") return [
      `${label} waiting for request admission`,
      state.appliedRange === null
        ? `${displayRange(state.selectedRange)} is queued.`
        : `${displayRange(state.selectedRange)} is queued; ${displayRange(state.appliedRange)} remains visible.`,
    ];
    if (phase === "loading") return [
      `Loading ${label.toLowerCase()}…`,
      state.appliedRange === null
        ? `Reading ${displayRange(state.selectedRange)} persisted evidence.`
        : `${displayRange(state.appliedRange)} remains visible until ${displayRange(state.selectedRange)} succeeds.`,
    ];
    const busy = failure && failure.kind === "busy";
    return [
      busy ? `${label} query is busy` : `${label} unavailable`,
      state.appliedRange === null
        ? `${displayRange(state.selectedRange)} could not be loaded.`
        : `${displayRange(state.selectedRange)} could not be loaded; showing ${displayRange(state.appliedRange)}.`,
    ];
  }

  function renderPhase(state, phase, failure) {
    state.phase = phase;
    const ui = productUi[state.product];
    const [title, message] = phaseText(state.product, phase, state, failure);
    ui.state.dataset.state = phase.startsWith("error") ? "error" : "warning";
    ui.title.textContent = title;
    ui.message.textContent = message;
    updateControls(state);
  }

  function enqueue(product, range, priority, force) {
    const state = states.get(product);
    if (!state || !RANGE[range] || (!force && state.selectedRange === range)) return false;
    state.selectedRange = range;
    state.intentGeneration += 1;
    state.lastError = null;
    pending.set(product, {
      product,
      range,
      generation: state.intentGeneration,
      priority,
      sequence: sequence += 1,
    });
    renderPhase(state, "waiting", null);
    return true;
  }

  function enqueueRefresh() {
    enabledProducts.forEach((product) => {
      const state = states.get(product);
      const existing = pending.get(product);
      if (existing && existing.priority > 1) return;
      enqueue(product, state.selectedRange, 1, true);
    });
  }

  function nextAdmissionAt() {
    return lastDispatchMonotonic === null
      ? 0 : lastDispatchMonotonic + ADMISSION_GUARD_MILLISECONDS;
  }

  function nextBatch() {
    if (!pending.size) return null;
    const intents = Array.from(pending.values()).sort((left, right) => (
      right.priority - left.priority || left.sequence - right.sequence
    ));
    const first = intents[0];
    const selected = PRODUCT_ORDER.map((product) => pending.get(product))
      .filter((intent) => intent && intent.range === first.range);
    selected.forEach((intent) => pending.delete(intent.product));
    selected.forEach((intent) => renderPhase(states.get(intent.product), "loading", null));
    return Object.freeze({
      range: first.range,
      products: Object.freeze(selected.map((intent) => intent.product)),
      intents: Object.freeze(selected),
    });
  }

  function restoreBatch(batch) {
    for (const intent of batch.intents) {
      const state = states.get(intent.product);
      if (state.intentGeneration !== intent.generation
          || state.selectedRange !== intent.range || pending.has(intent.product)) continue;
      pending.set(intent.product, intent);
      renderPhase(state, "waiting", null);
    }
  }

  function schedulePending() {
    if (pending.size) coordinator.queuePanel(PANEL_KEY, {notBefore: nextAdmissionAt()});
  }

  function applyBatch(batch, projected) {
    for (const intent of batch.intents) {
      const state = states.get(intent.product);
      if (state.intentGeneration !== intent.generation
          || state.selectedRange !== intent.range) continue;
      if (intent.product === "history") renderHistory(projected.history);
      if (intent.product === "statistics") {
        renderStatistics(projected.statistics, projected.common);
      }
      if (intent.product === "peak") renderPeak(projected.peak, projected.common);
      if (intent.product === "aps") renderApTraffic(projected.ap, projected.common);
      if (intent.product === "apshare") renderApShare(projected.apshare, projected.common);
      state.appliedRange = projected.common.range.id;
      state.phase = "ready";
      state.lastSuccessfulPayload = projected[intent.product === "aps" ? "ap" : intent.product];
      state.lastError = null;
      updateControls(state);
    }
  }

  function failBatch(batch, failure) {
    for (const intent of batch.intents) {
      const state = states.get(intent.product);
      if (state.intentGeneration !== intent.generation
          || state.selectedRange !== intent.range) continue;
      state.lastError = failure;
      renderPhase(
        state,
        state.lastSuccessfulPayload === null ? "error_empty" : "error_with_previous",
        failure,
      );
    }
  }

  function selectProductRange(product, range) {
    if (!enqueue(product, range, 2, false)) return;
    coordinator.queuePanel(PANEL_KEY, {notBefore: nextAdmissionAt()});
  }

  enabledProducts.forEach((product) => {
    const pair = controls(product);
    if (!pair.range24h || !pair.range7d) throw new Error("Missing Traffic range controls");
    pair.range24h.addEventListener("click", () => selectProductRange(product, "24h"));
    pair.range7d.addEventListener("click", () => selectProductRange(product, "7d"));
    updateControls(states.get(product));
    pending.set(product, {
      product,
      range: "24h",
      generation: states.get(product).intentGeneration,
      priority: 0,
      sequence: sequence += 1,
    });
  });

  coordinator.registerPanel({
    key: PANEL_KEY,
    autoRefresh: false,
    prepareRefresh: () => {
      enqueueRefresh();
      return nextAdmissionAt();
    },
    load: async (context) => {
      const batch = nextBatch();
      if (batch === null) return null;
      activeBatch = batch;
      lastDispatchMonotonic = monotonicNow();
      const products = batch.products.join(",");
      try {
        const payload = await context.requestJson(
          `${context.apiBase}/traffic/history?range=${encodeURIComponent(batch.range)}&products=${encodeURIComponent(products)}`,
        );
        return Object.freeze({
          batch,
          projected: validateProjection(payload, context.siteId, batch.products),
        });
      } catch (error) {
        if (error && error.trafficNeutral) {
          restoreBatch(batch);
          activeBatch = null;
          schedulePending();
        }
        throw error;
      }
    },
    render: (value) => {
      if (value === null) return;
      applyBatch(value.batch, value.projected);
      activeBatch = null;
      schedulePending();
    },
    renderLoading: () => {},
    renderFailure: (failure) => {
      if (activeBatch !== null) failBatch(activeBatch, failure);
      activeBatch = null;
      schedulePending();
    },
  });
}());
/* TRAFFIC_HISTORY_PANEL_END */

(function () {
  "use strict";
  const STATUS = new Set(["operational", "degraded", "unavailable", "unknown"]);
  const COVERAGE = new Set(["complete", "partial", "insufficient_data"]);
  const FRESHNESS = new Set(["fresh", "stale", "unavailable"]);
  function count(value) { return Number.isInteger(value) && value >= 0; }
  function utc(value) { return typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(value) && Number.isFinite(Date.parse(value)); }
  function counts(value, population) {
    return value && Object.keys(value).length === 4 && ["operational", "degraded", "unavailable", "unknown"].every((key) => count(value[key]))
      && Object.values(value).reduce((total, item) => total + item, 0) === population;
  }
  function validResult(payload, siteId) {
    if (!payload || payload.api_version !== "admin.read.v1" || payload.site_id !== siteId || !payload.result) return null;
    const value = payload.result;
    if (value.contract_version !== "admin.home_ap_24h.v1" || !STATUS.has(value.block_status)) return null;
    if (!value.window || value.window.kind !== "rolling_24h" || value.window.bucket_seconds !== 900 || value.window.bucket_count !== 96
      || !utc(value.window.evaluated_at_utc) || !utc(value.window.from_utc) || !utc(value.window.to_utc)
      || value.window.evaluated_at_utc !== value.window.to_utc
      || Date.parse(value.window.to_utc) - Date.parse(value.window.from_utc) !== 86400000) return null;
    if (!value.summary || !value.sources || !value.page || !Array.isArray(value.items)) return null;
    const population = value.summary.ap_count_in_window;
    if (!count(population) || !counts(value.summary.current, population) || !counts(value.summary.history, population)
      || !counts(value.summary.observation_quality, population)
      || !["short_history_ap_count", "status_gap_ap_count", "observation_problem_ap_count"].every((key) => count(value.summary[key]) && value.summary[key] <= population)) return null;
    if (Object.keys(value.sources).length !== 2 || !["current_state", "observations"].every((key) => value.sources[key] && STATUS.has(value.sources[key].status))) return null;
    if (!Number.isInteger(value.page.limit) || value.page.limit < 1 || value.page.limit > 20 || value.items.length > value.page.limit) return null;
    if (!value.items.every((item) => item && typeof item.ap_mac === "string" && item.current && STATUS.has(item.current.status)
      && FRESHNESS.has(item.current.freshness_status)
      && item.history && STATUS.has(item.history.status) && COVERAGE.has(item.history.coverage_status)
      && item.observation_quality && STATUS.has(item.observation_quality.status)
      && Array.isArray(item.timeline) && item.timeline.length === 96
      && item.timeline.every((bucket, index) => bucket && STATUS.has(bucket.ap_state) && STATUS.has(bucket.observation_quality)
        && utc(bucket.from_utc) && utc(bucket.to_utc)
        && Date.parse(bucket.from_utc) === Date.parse(value.window.from_utc) + index * 900000
        && Date.parse(bucket.to_utc) === Date.parse(bucket.from_utc) + 900000
        && ["operational_seconds", "unavailable_seconds", "unknown_evidence_seconds", "short_history_seconds"].every((key) => count(bucket[key]))
        && bucket.operational_seconds + bucket.unavailable_seconds + bucket.unknown_evidence_seconds + bucket.short_history_seconds === 900
        && ["authoritative_state_sample_count", "complete_observation_sample_count", "diagnostic_partial_observation_sample_count"].every((key) => count(bucket[key]))))) return null;
    if (value.page.next_cursor !== null && typeof value.page.next_cursor !== "string") return null;
    return value;
  }
  function retryDelay(failures, retryAfter) {
    if (Number.isFinite(retryAfter) && retryAfter > 0) return retryAfter * 1000;
    return Math.min(300000, 5000 * (2 ** Math.min(Math.max(0, failures - 1), 6)));
  }
  function controllerEnabled(root) { return root && root.dataset.homeAp24hEnabled === "true"; }
  if (typeof window !== "undefined") window.CaptivPortalHomeAp24Test = Object.freeze({validResult, retryDelay, controllerEnabled});
  if (typeof document === "undefined") return;
  const root = document.getElementById("admin-page");
  if (!root || root.dataset.page !== "home" || !controllerEnabled(root)) return;
  const siteId = root.dataset.siteId;
  const base = root.dataset.apiBase + "/home/ap-24h";
  const refreshMs = Number(root.dataset.homeAp24hRefreshSeconds) * 1000;
  const timeoutMs = Number(root.dataset.homeAp24hRequestTimeoutSeconds) * 1000;
  const state = {generation: 0, controller: null, active: false, stopped: false, failures: 0, next: 0, cursor: null, timer: null};
  const panel = document.getElementById("home-ap-24h-state");
  const target = document.getElementById("home-ap-24h-items");
  const more = document.getElementById("home-ap-24h-more");
  function node(tag, className, text) {
    const value = document.createElement(tag);
    if (className) value.className = className;
    if (text !== undefined) value.textContent = text === null || text === undefined ? "—" : String(text);
    return value;
  }
  function setPanel(status, title, message) {
    panel.dataset.state = status;
    document.getElementById("home-ap-24h-status").textContent = title;
    document.getElementById("home-ap-24h-message").textContent = message;
  }
  function renderSummary(value) {
    const summary = document.getElementById("home-ap-24h-summary"); summary.replaceChildren();
    const axes = [["Current", value.summary.current], ["24-hour state", value.summary.history], ["Observation evidence", value.summary.observation_quality]];
    axes.forEach(([label, counts]) => {
      const card = node("article", "health-component");
      card.append(node("strong", null, label), node("p", "live-detail", `Operational ${counts.operational} · Degraded ${counts.degraded} · Unavailable ${counts.unavailable} · Unknown ${counts.unknown}`));
      summary.append(card);
    });
    document.getElementById("home-ap-24h-window").textContent = `${value.window.from_utc} through ${value.window.to_utc} · ${value.summary.ap_count_in_window} AP(s)`;
  }
  function renderItems(items, append) {
    if (!append) target.replaceChildren();
    items.forEach((item) => {
      const row = node("article", "data-row"); const heading = node("div", "data-row-header");
      heading.append(node("strong", null, item.name || item.ap_mac), node("span", "badge", item.current.status));
      const detail = node("p", "live-detail", `${item.ap_mac} · 24h ${item.history.status} · unavailable ${item.history.unavailable_seconds}s · Observation ${item.observation_quality.status}`);
      const timeline = node("div", "ap24-timeline");
      item.timeline.forEach((bucket) => { const segment = node("span", "ap24-segment"); segment.dataset.state = bucket.ap_state; segment.title = `${bucket.from_utc} · ${bucket.ap_state} · Observation ${bucket.observation_quality}`; timeline.append(segment); });
      row.append(heading, detail, timeline); target.append(row);
    });
  }
  async function request(cursor, generation) {
    const controller = new AbortController(); state.controller = controller;
    const timeout = window.setTimeout(() => controller.abort("timeout"), timeoutMs);
    try {
      const params = new URLSearchParams({limit: "20"}); if (cursor) params.set("cursor", cursor);
      const response = await fetch(`${base}?${params}`, {method: "GET", credentials: "same-origin", cache: "no-store", headers: {Accept: "application/json"}, signal: controller.signal});
      let payload = null; try { payload = await response.json(); } catch (_error) { payload = null; }
      if (!response.ok) {
        const failure = new Error("request failed"); failure.status = response.status;
        failure.retryAfter = Number(response.headers.get("Retry-After")) || 0; throw failure;
      }
      if (state.stopped || generation !== state.generation) return null;
      const value = validResult(payload, siteId); if (!value) throw new Error("malformed response");
      return value;
    } finally {
      window.clearTimeout(timeout); if (state.controller === controller) state.controller = null;
    }
  }
  function failure(error) {
    if (error && error.status === 404) { state.stopped = true; target.replaceChildren(); more.hidden = true; setPanel("unavailable", "Feature unavailable", "AP 24-hour history is disabled."); return; }
    state.failures += 1; state.next = performance.now() + retryDelay(state.failures, error && error.retryAfter);
    setPanel("unavailable", "Update unavailable", "AP 24-hour evidence could not be refreshed. Other Home panels remain independent.");
  }
  async function run(manual) {
    if (state.stopped || state.active || document.hidden) return;
    if (performance.now() < state.next && (!manual || state.failures > 0)) return;
    state.active = true; state.generation += 1; const generation = state.generation;
    if (state.controller) state.controller.abort("superseded");
    try {
      const value = await request(null, generation); if (!value) return;
      state.failures = 0; state.next = performance.now() + refreshMs; state.cursor = value.page.next_cursor;
      renderSummary(value); renderItems(value.items, false); more.hidden = !state.cursor;
      setPanel(value.block_status, value.block_status[0].toUpperCase() + value.block_status.slice(1), value.block_reason || "Persisted Current State and Observation evidence loaded.");
    } catch (error) {
      if (!(error && error.name === "AbortError")) failure(error);
    } finally { state.active = false; }
  }
  async function loadMore() {
    if (!state.cursor || state.active || state.stopped) return;
    state.active = true; state.generation += 1; const generation = state.generation;
    try {
      const value = await request(state.cursor, generation); if (!value) return;
      state.cursor = value.page.next_cursor; renderItems(value.items, true); more.hidden = !state.cursor;
    } catch (error) { if (!(error && error.name === "AbortError")) failure(error); }
    finally { state.active = false; }
  }
  function abort(reason) {
    if (state.controller) {
      state.generation += 1;
      state.controller.abort(reason);
    }
  }
  function nextEligibleAt() { return state.stopped ? Infinity : state.next; }
  const api = Object.freeze({run, abort, nextEligibleAt}); window.CaptivPortalHomeAp24Coordinator = api;
  more.addEventListener("click", loadMore);
  const combined = root.dataset.homeLiveEnabled === "true" && [root.dataset.homeTrafficEnabled, root.dataset.homeActivityEnabled, root.dataset.homeHealthEnabled, root.dataset.homeAp24hEnabled].some((value) => value === "true");
  if (!combined) {
    const refresh = document.getElementById("refresh-button"); refresh.addEventListener("click", () => run(true));
    function schedule() { if (state.timer !== null) window.clearTimeout(state.timer); if (!state.stopped && !document.hidden) state.timer = window.setTimeout(async () => { state.timer = null; await run(false); schedule(); }, Math.max(1000, state.next - performance.now())); }
    document.addEventListener("visibilitychange", () => { if (document.hidden) { abort("hidden"); if (state.timer !== null) window.clearTimeout(state.timer); } else { run(false).then(schedule); } });
    window.addEventListener("pagehide", () => { state.stopped = true; abort("pagehide"); });
    run(true).then(schedule);
  }
}());

(function () {
  "use strict";

  const API_VERSION = "admin.read.v1";
  const IDS = ["guest_access", "live_network_state", "network_history", "visit_tracking", "analytics_home_data"];
  const LABELS = ["Guest Access", "Live Network State", "Network History Collection", "Visit Tracking", "Analytics & Home Data"];
  const STATUSES = new Set(["operational", "degraded", "unavailable", "unknown"]);
  const AGGREGATE_MESSAGES = Object.freeze({
    operational: "All CaptivPortal functions are operating normally.",
    degraded: "Some CaptivPortal functions are degraded.",
    unavailable: "Guest access is currently unavailable.",
    unknown: "There is not enough current evidence to confirm system status.",
  });
  const REASON_MESSAGES = Object.freeze({
    latest_authorization_verified: "Guest authorization is operating normally.",
    no_authorization_evidence: "There is not enough current authorization evidence to confirm status.",
    authorization_evidence_old: "Authorization evidence is too old to confirm current status.",
    invalid_authorization_evidence_time: "Authorization evidence time cannot be trusted.",
    authorization_transient_failure: "Guest authorization recently encountered a temporary system failure.",
    authorization_unavailable: "Guest authorization is currently unavailable.",
    current_state_operational: "Current client and access-point state is available.",
    current_state_stale: "Current network state is delayed; last complete data remains available.",
    current_state_unavailable: "Current network state is unavailable.",
    latest_collection_incomplete: "The latest collection did not complete; last complete data remains available.",
    observation_operational: "Network history collection is operating normally.",
    stale_evidence: "Data collection is delayed; last known data remains available.",
    observation_unavailable: "Network history collection is unavailable.",
    initializing: "There is not enough current evidence to confirm status.",
    visit_operational: "Visit tracking is operating normally.",
    visit_runtime_degraded: "Visit tracking is operating with reduced availability.",
    visit_runtime_unavailable: "Visit tracking is currently unavailable.",
    analytics_operational: "Analytics and Home data sources are available.",
    analytics_source_unavailable: "Analytics source data is currently unavailable.",
    current_traffic_service_unavailable: "Current Traffic data is currently unavailable.",
    home_activity_service_unavailable: "Home Activity data is currently unavailable.",
    component_disabled: "This required function is disabled.",
    health_read_failed: "There is not enough current evidence to confirm status.",
  });
  const HEALTH_TIMESTAMP = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/;
  const BACKOFF = [60, 120, 300];

  function object(value) { return value && typeof value === "object" && !Array.isArray(value); }
  function utc(value) {
    if (typeof value !== "string" || !HEALTH_TIMESTAMP.test(value)) return false;
    const parsed = new Date(value);
    return !Number.isNaN(parsed.getTime()) && parsed.toISOString() === value;
  }
  function optionalUtc(value) { return value === null || utc(value); }
  function aggregateStatus(components) {
    if (components[0].status === "unavailable") return "unavailable";
    if (components.some((item) => item.status === "degraded" || item.status === "unavailable")) return "degraded";
    if (components.some((item) => item.status === "unknown")) return "unknown";
    return "operational";
  }
  function validateHealth(payload, siteId) {
    if (!object(payload) || payload.api_version !== API_VERSION || payload.site_id !== siteId
      || !object(payload.result)) return null;
    const result = payload.result;
    if (result.health_version !== 1 || result.site_id !== siteId || !utc(result.evaluated_at)
      || !STATUSES.has(result.status) || result.message !== AGGREGATE_MESSAGES[result.status]
      || !Array.isArray(result.components) || result.components.length !== IDS.length) return null;
    for (let index = 0; index < IDS.length; index += 1) {
      const item = result.components[index];
      const criticality = index === 0 ? "critical" : "feature";
      const scopeType = index < 3 ? "site" : "global";
      if (!object(item) || item.id !== IDS[index] || item.label !== LABELS[index]
        || !STATUSES.has(item.status) || !(item.reason_code in REASON_MESSAGES)
        || item.message !== REASON_MESSAGES[item.reason_code]
        || item.criticality !== criticality
        || !object(item.scope) || item.scope.type !== scopeType
        || (item.scope.type === "site" && (item.scope.site_id !== siteId
          || Object.keys(item.scope).length !== 2))
        || (item.scope.type === "global" && ("site_id" in item.scope
          || Object.keys(item.scope).length !== 1))
        || !optionalUtc(item.evidence_at) || !optionalUtc(item.last_success_at)) return null;
    }
    if (result.status !== aggregateStatus(result.components)) return null;
    return result;
  }
  function claim(source, controller, generation) {
    if (source.generation !== generation || source.controller !== null) return false;
    source.controller = controller; return true;
  }
  function release(source, controller) {
    if (source.controller === controller) source.controller = null;
  }
  function abort(source, reason) {
    if (!source.controller) return false;
    const controller = source.controller;
    controller.abort(reason); release(source, controller); return true;
  }
  function classify(status, code, retryAfter) {
    if (status === 401) return {global: true, kind: "session", retryAfter: 0};
    if (status === 403) return {global: true, kind: "forbidden", retryAfter: 0};
    if (status === 404) return {global: false, kind: "disabled", retryAfter: 0};
    return {global: false, kind: code === "query_deadline" ? "timeout" : "unavailable", retryAfter: retryAfter || 0};
  }
  function legacyCoordinatorEnabled(homeLive, homeHealth) {
    return homeLive !== "true" && homeHealth === "true";
  }

  if (typeof window !== "undefined") {
    window.CaptivPortalHomeHealthTest = Object.freeze({
      abort, claim, classify, legacyCoordinatorEnabled, release,
      validateHealth,
    });
  }
  if (typeof document === "undefined") return;
  const root = document.getElementById("admin-page");
  if (!root || root.dataset.page !== "home" || root.dataset.homeHealthEnabled !== "true") return;

  const siteId = root.dataset.siteId;
  const url = root.dataset.apiBase + "/home/health";
  const interval = Number(root.dataset.homeHealthRefreshSeconds);
  const timeoutMs = Number(root.dataset.homeHealthRequestTimeoutSeconds) * 1000;
  const source = {generation: 0, controller: null, failureCount: 0, nextEligibleAt: 0, disabled: false};
  let stopped = false;

  function node(tag, className, text) {
    const value = document.createElement(tag);
    if (className) value.className = className;
    if (text !== undefined) value.textContent = text;
    return value;
  }
  function render(value) {
    const panel = document.getElementById("home-health-state");
    panel.dataset.state = value.status;
    document.getElementById("home-health-status").textContent = value.status[0].toUpperCase() + value.status.slice(1);
    document.getElementById("home-health-message").textContent = value.message;
    document.getElementById("home-health-updated").textContent = `Last updated ${value.evaluated_at}`;
    const target = document.getElementById("home-health-components");
    target.replaceChildren();
    value.components.forEach((item) => {
      const row = node("article", "health-component");
      row.dataset.state = item.status;
      const heading = node("div", "data-row-header");
      heading.append(node("strong", null, item.label), node("span", "badge", item.status));
      const evidence = item.evidence_at ? `Evidence ${item.evidence_at}` : "Evidence unavailable";
      const success = item.last_success_at ? `Last success ${item.last_success_at}` : "Last success unavailable";
      row.append(heading, node("p", "live-detail", item.message), node("p", "live-detail", `${evidence} · ${success}`));
      target.append(row);
    });
  }
  function updateUnavailable() {
    const panel = document.getElementById("home-health-state");
    panel.dataset.state = "unknown";
    document.getElementById("home-health-status").textContent = "Update unavailable";
    document.getElementById("home-health-message").textContent = "The latest Health update could not be completed; previously rendered evidence remains timestamped.";
  }
  async function request(generation) {
    const controller = new AbortController();
    if (!claim(source, controller, generation)) throw {neutral: true};
    const timer = window.setTimeout(() => controller.abort("timeout"), timeoutMs);
    try {
      const response = await fetch(url, {method: "GET", credentials: "same-origin", cache: "no-store", headers: {Accept: "application/json"}, signal: controller.signal});
      let payload = null; try { payload = await response.json(); } catch (_error) { payload = null; }
      if (!response.ok) {
        const code = payload && payload.error && payload.error.code;
        const retry = Number(response.headers.get("Retry-After"));
        throw {failure: classify(response.status, code, Number.isFinite(retry) && retry > 0 ? retry : 0)};
      }
      if (source.generation !== generation || stopped) throw {neutral: true};
      return payload;
    } catch (error) {
      if (controller.signal.aborted && ["hidden", "pagehide", "superseded"].includes(controller.signal.reason)) throw {neutral: true};
      if (error && (error.failure || error.neutral)) throw error;
      throw {failure: {global: false, kind: "unavailable", retryAfter: 0}};
    } finally {
      window.clearTimeout(timer); release(source, controller);
    }
  }
  async function run(manual) {
    if (stopped || document.hidden || source.disabled) return;
    const now = performance.now();
    if (!manual && now < source.nextEligibleAt) return;
    if (manual && source.failureCount > 0 && now < source.nextEligibleAt) return;
    source.generation += 1; const generation = source.generation;
    abort(source, "superseded");
    try {
      const payload = await request(generation);
      const result = validateHealth(payload, siteId);
      if (!result) throw {failure: {global: false, kind: "unavailable", retryAfter: 0}};
      render(result); source.failureCount = 0; source.nextEligibleAt = performance.now() + interval * 1000;
    } catch (error) {
      if (error && error.neutral) return;
      const failure = error && error.failure ? error.failure : {global: false, kind: "unavailable", retryAfter: 0};
      if (failure.global) {
        const coordinator = window.CaptivPortalHomeCoordinator;
        if (coordinator) coordinator.stop(failure.kind);
        else {
          stopped = true;
          source.disabled = true;
          source.nextEligibleAt = Infinity;
        }
      } else if (failure.kind === "disabled") {
        source.disabled = true; source.nextEligibleAt = Infinity;
      } else {
        source.failureCount += 1;
        source.nextEligibleAt = performance.now() + Math.max(interval, BACKOFF[Math.min(source.failureCount - 1, 2)], failure.retryAfter || 0) * 1000;
        updateUnavailable();
      }
    }
  }
  window.CaptivPortalHomeHealthCoordinator = Object.freeze({
    abort: (reason) => abort(source, reason),
    nextEligibleAt: () => source.nextEligibleAt,
    run,
  });
}());

(function () {
  "use strict";

  const API_VERSION = "admin.read.v1";
  const UTC = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/;
  const STATUSES = new Set(["complete", "partial", "unavailable"]);
  const FRESHNESS = new Set(["fresh", "stale", "unavailable"]);
  const PERIODS = new Set(["last_24h", "yesterday", "last_48h", "last_7d", "current_month", "last_30d", "custom"]);
  const ROLLING = new Set(["last_24h", "last_48h", "last_7d", "current_month", "last_30d"]);
  const QUALITY = new Set([
    "coverage_start_unknown", "requested_before_coverage_start",
    "requested_after_coverage_through", "source_unavailable", "query_deadline",
    "opening_authorization_evidence_missing", "authorization_chronology_anomaly",
    "guest_scope_unproven",
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
    return object(value) && STATUSES.has(value.status)
      && ((value.status === "unavailable" && value.value === null
        && value.verified_visit_count === null)
        || (value.status !== "unavailable" && integer(value.value)
          && value.value === value.verified_visit_count && integer(value.verified_visit_count)))
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
    return object(value) && STATUSES.has(value.status)
      && ((value.status === "unavailable" && value.bytes === null)
        || (value.status !== "unavailable" && integer(value.bytes)))
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
    const rendered = index === 0 ? String(amount) : amount.toFixed(1).replace(/\.0$/, "");
    return `${rendered} ${units[index]}`;
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
        if (["hidden", "pagehide", "superseded", "disabled"].includes(controller.signal.reason)) throw {neutral: true};
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
    const requested = value.range.requested;
    if (requested.kind === "custom" && requested.to_date_inclusive === true) {
      return `${resolved.from_local} → Through ${requested.to_date} inclusive · technical end ${resolved.to_local_exclusive} · ${resolved.timezone}`;
    }
    return `${resolved.from_local} → ${resolved.to_local_exclusive} · ${resolved.timezone}`;
  }
  function coverageText(label, value) {
    if (value.status === "complete") return `${label} complete`;
    const coverageValue = value.coverage;
    if (value.status === "unavailable") return `${label} unavailable`;
    if (coverageValue.covered_from_utc && coverageValue.covered_through_utc) {
      return `${label} partial · proven ${coverageValue.covered_from_utc} → ${coverageValue.covered_through_utc}`;
    }
    return `${label} partial · proven coverage unavailable`;
  }
  function qualityText(value) {
    const visit = value.authorized_visits; const trafficValue = value.traffic;
    const visitStart = visit.coverage.coverage_from_utc || "unknown";
    const visitThrough = visit.coverage.coverage_through_utc || "unknown";
    const trafficStart = trafficValue.coverage.coverage_from_utc || "unknown";
    const trafficThrough = trafficValue.coverage.coverage_through_utc || "unknown";
    const labels = [coverageText("Visits", visit), `Visits data ${visitStart} → ${visitThrough}`,
      coverageText("Traffic", trafficValue), `Traffic data ${trafficStart} → ${trafficThrough}`,
      `Reader ${trafficValue.ingestion_freshness}`, `Last updated ${value.evaluated_at_utc}`];
    return labels.join(" · ");
  }
  function render(kind, value) {
    document.getElementById(`activity-${kind}-range`).textContent = rangeText(value);
    document.getElementById(`activity-${kind}-visits`).textContent = value.authorized_visits.status === "unavailable"
      ? "— · Unavailable" : String(value.authorized_visits.value);
    const suffix = value.traffic.status === "partial" ? " · Partial · Estimated"
      : value.traffic.status === "unavailable" ? " · Unavailable · Estimated" : " · Estimated";
    document.getElementById(`activity-${kind}-traffic`).textContent = bytes(value.traffic.bytes) + suffix;
    document.getElementById(`activity-${kind}-quality`).textContent = qualityText(value);
  }
  function loading(kind) {
    document.getElementById(`activity-${kind}-quality`).textContent = "Loading…";
  }
  function failed(kind, message) {
    document.getElementById(`activity-${kind}-quality`).textContent = message;
  }
  function disableActivity() {
    stopped = true;
    [today, selected].forEach((source) => {
      source.disabled = true; source.autoRefresh = false;
      source.nextEligibleAt = Infinity; source.manualEligibleAt = Infinity;
      source.generation += 1; abort(source, "disabled");
    });
    abort(preview, "disabled");
    ["today", "selected"].forEach((kind) => {
      document.getElementById(`activity-${kind}-range`).textContent = "Activity unavailable";
      document.getElementById(`activity-${kind}-visits`).textContent = "—";
      document.getElementById(`activity-${kind}-traffic`).textContent = "— · Estimated";
      failed(kind, "Activity is disabled; current panels remain available.");
    });
    picker.hidden = true; pickerOpener.disabled = true;
    previewButton.disabled = true; applyButton.disabled = true;
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
      disableActivity();
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
  function standaloneCoordinatorEnabled(homeLive, homeTraffic, homeActivity, homeHealth) {
    return homeLive === "true" && homeTraffic !== "true" && homeActivity !== "true" && homeHealth !== "true";
  }

  if (typeof window !== "undefined") {
    window.CaptivPortalHomeLiveTest = Object.freeze({
      classify, currentAge, localFreshness, retryDelay,
      abortOwnedController, canStartCleanRefresh, claimController, clientParameters, enrichmentState,
      failureTransition, neutralAbort, releaseController, resetClientState,
      retainedSelection, unavailableValues,
      standaloneCoordinatorEnabled,
      validateApSummary, validateClientSummary, validatePage,
    });
  }
  if (typeof document === "undefined") return;
  const root = document.getElementById("admin-page");
  if (!root || root.dataset.page !== "home" || !standaloneCoordinatorEnabled(
    root.dataset.homeLiveEnabled,
    root.dataset.homeTrafficEnabled,
    root.dataset.homeActivityEnabled,
    root.dataset.homeHealthEnabled,
  )) return;

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

  function healthController() { return window.CaptivPortalHomeHealthCoordinator || null; }

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
    const health = healthController();
    if (health) health.abort(reason);
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
    if (kind === "client") {
      const health = healthController();
      if (health && !stopped && !document.hidden) await health.run(manual);
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
  function combinedCoordinatorEnabled(homeLive, homeTraffic, homeActivity, homeHealth, homeAp24h) {
    return homeLive === "true" && (homeTraffic === "true" || homeActivity === "true" || homeHealth === "true" || homeAp24h === "true");
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
      combinedCoordinatorEnabled,
    });
  }
  if (typeof document === "undefined") return;
  const root = document.getElementById("admin-page");
  if (!root || root.dataset.page !== "home" || !combinedCoordinatorEnabled(
    root.dataset.homeLiveEnabled,
    root.dataset.homeTrafficEnabled,
    root.dataset.homeActivityEnabled,
    root.dataset.homeHealthEnabled,
    root.dataset.homeAp24hEnabled,
  )) return;

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
  function healthController() { return window.CaptivPortalHomeHealthCoordinator || null; }
  function ap24Controller() { return window.CaptivPortalHomeAp24Coordinator || null; }
  function abortAll(reason) {
    Object.values(sources).forEach((source) => live.abortOwnedController(source, reason));
    const activity = activityController();
    if (activity) activity.abort(reason);
    const health = healthController();
    if (health) health.abort(reason);
    const ap24 = ap24Controller();
    if (ap24) ap24.abort(reason);
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
    const health = healthController();
    if (health) {
      const due = health.nextEligibleAt();
      if (Number.isFinite(due)) finite.push(due);
    }
    const ap24 = ap24Controller();
    if (ap24) {
      const due = ap24.nextEligibleAt();
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
      const health = healthController();
      if (health && !coordinator.pending && !stopped && !document.hidden) {
        await health.run(manual);
      }
      const ap24 = ap24Controller();
      if (ap24 && !coordinator.pending && !stopped && !document.hidden) {
        await ap24.run(manual);
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
