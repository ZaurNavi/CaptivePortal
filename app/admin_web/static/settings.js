/* Global Settings V1. No Site controller, precedence, activation or restart authority. */
(function () {
  "use strict";
  const root = document.getElementById("settings-page");
  if (!root) return;
  const status = document.getElementById("settings-state");
  const groups = document.getElementById("settings-groups");
  const save = document.getElementById("settings-save");
  let model = null;
  let etag = null;
  let busy = false;
  let controls = [];
  const groupTitles = {pagination: "Pagination / Presentation", refresh: "Refresh Cadence"};
  function node(tag, text, className) {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (className) element.className = className;
    return element;
  }
  const text = (value) => value === null ? "—" : String(value);
  async function request(url, options) {
    const abort = new AbortController();
    const timer = window.setTimeout(() => abort.abort(), 30000);
    try {
      const response = await fetch(url, {...options, credentials: "same-origin", cache: "no-store", signal: abort.signal});
      const body = await response.json();
      if (!response.ok) {
        const error = new Error("Settings request failed");
        error.status = response.status;
        error.code = body.error && body.error.code;
        throw error;
      }
      return {response, body};
    } finally { window.clearTimeout(timer); }
  }
  function render() {
    groups.replaceChildren(); controls = [];
    const containers = new Map();
    model.settings.forEach((item) => {
      if (!containers.has(item.group)) {
        const section = node("section", undefined, "card card-wide settings-group");
        section.append(node("h2", groupTitles[item.group])); groups.append(section); containers.set(item.group, section);
      }
      const row = node("article", undefined, "settings-item");
      row.append(node("h3", item.display_label), node("p", item.description), node("p", item.key, "mono muted"));
      const facts = node("dl", undefined, "settings-facts");
      [["Configured", item.configured_value], ["Effective", item.effective_value],
        ["Persisted override", item.persisted_override_value], ["Base source", item.base_source],
        ["Base value", item.base_value], ["Pending", item.pending_value],
        ["Consumer", item.consumer_state], ["Activation", item.activation_state],
        ["Apply requirement", item.apply_requirement]].forEach(([label, value]) => {
          facts.append(node("dt", label), node("dd", text(value)));
        });
      row.append(facts);
      const label = node("label", "Override action ");
      const operation = node("select");
      [["unchanged", "Keep unchanged"], ["set", "Set override"], ["clear_override", "Clear override / use deployment value"]]
        .forEach(([value, title]) => {const option = node("option", title); option.value = value; operation.append(option);});
      label.append(operation); row.append(label);
      const valueLabel = node("label", `Value (${item.validation.min}–${item.validation.max}) `);
      const input = node("input"); input.type = "number"; input.step = "1";
      input.min = String(item.validation.min); input.max = String(item.validation.max);
      input.value = String(item.configured_value); input.disabled = true;
      operation.addEventListener("change", () => {input.disabled = operation.value !== "set";});
      valueLabel.append(input); row.append(valueLabel);
      containers.get(item.group).append(row); controls.push({item, operation, input});
    });
  }
  async function load() {
    save.disabled = true; model = null; etag = null;
    const result = await request(root.dataset.apiBase, {headers: {Accept: "application/json"}});
    if (result.body.api_version !== "admin.settings.v1" || !Array.isArray(result.body.settings) || result.body.settings.length !== 12) throw new Error("Invalid Settings model");
    model = result.body; etag = result.response.headers.get("ETag");
    render(); save.disabled = false;
    status.textContent = `Configured generation ${model.configured_generation}; effective ${text(model.effective_generation)}. ` +
      (model.restart_required ? "Pending captive-portal.service restart." : "Current configured generation is adopted.");
  }
  function unavailable() {save.disabled = true; status.textContent = "Settings unavailable. No changes have been confirmed.";}
  document.getElementById("settings-refresh").addEventListener("click", async () => {
    if (busy) return;
    busy = true; try {await load();} catch (_error) {unavailable();} finally {busy = false;}
  });
  document.getElementById("settings-form").addEventListener("submit", async (event) => {
    event.preventDefault(); if (busy || !model || !etag) return;
    const changes = controls.filter((row) => row.operation.value !== "unchanged").map((row) => ({
      key: row.item.key, operation: row.operation.value,
      ...(row.operation.value === "set" ? {value: Number(row.input.value)} : {}),
    }));
    if (!changes.length) {status.textContent = "No override changes selected."; return;}
    busy = true; save.disabled = true;
    try {
      const result = await request(root.dataset.apiBase + "/generations", {method: "POST",
        headers: {"Content-Type": "application/json", "X-CSRF-Token": root.dataset.csrfToken,
          "If-Match": etag, "Idempotency-Key": crypto.randomUUID()}, body: JSON.stringify({changes})});
      await load();
      status.textContent = result.body.changed ? "Persisted successfully. Pending captive-portal.service restart." : "Accepted: no persisted override change.";
    } catch (error) {
      if (error.status === 412) {
        try {await load(); status.textContent = "Settings changed concurrently. Review the current values before a new Save.";} catch (_error) {unavailable();}
      } else if (error.status === 422 || error.status === 400) {
        status.textContent = "Save rejected. Review values and validation bounds. Nothing was persisted.";
        save.disabled = false;
      } else {unavailable();}
    } finally {busy = false;}
  });
  if (root.dataset.storeState === "available") load().catch(unavailable);
})();
