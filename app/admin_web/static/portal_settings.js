/* GLOBAL guest presentation. Server-owned metadata; no preview or restart authority. */
(function () {
  "use strict";
  const root = document.getElementById("portal-settings-page");
  if (!root) return;
  const status = document.getElementById("portal-settings-state");
  const groups = document.getElementById("portal-settings-groups");
  const save = document.getElementById("portal-settings-save");
  const writable = root.dataset.writeAllowed === "true";
  let model = null, etag = null, busy = false, controls = [];
  const text = value => value === null ? "—" : String(value);
  function node(tag, value, className) {
    const element = document.createElement(tag);
    if (value !== undefined) element.textContent = value;
    if (className) element.className = className;
    return element;
  }
  async function request(url, options) {
    const abort = new AbortController();
    const timer = window.setTimeout(() => abort.abort(), 30000);
    try {
      const response = await fetch(url, {...options, credentials: "same-origin", cache: "no-store", signal: abort.signal});
      const body = await response.json();
      if (!response.ok) {const error = new Error("Portal settings rejected"); error.status = response.status; throw error;}
      return {response, body};
    } finally {window.clearTimeout(timer);}
  }
  function render() {
    groups.replaceChildren(); controls = [];
    const containers = new Map();
    model.settings.forEach(item => {
      if (!containers.has(item.group)) {
        const section = node("section", undefined, "card card-wide settings-group");
        section.append(node("h2", item.group === "branding" ? "Branding & welcome" : "Support contacts"));
        if (item.group === "support") section.append(node("p", "This value is publicly visible to guests. No private credential or personal secret may be entered."));
        groups.append(section); containers.set(item.group, section);
      }
      const row = node("article", undefined, "settings-item");
      row.append(node("h3", item.display_label), node("p", item.description), node("p", item.key, "mono muted"));
      const facts = node("dl", undefined, "settings-facts");
      [["Configured", item.configured_value], ["Effective", item.effective_value],
       ["Source", item.persisted_override_value !== null ? "persisted_override" : item.base_source],
       ["Pending", item.pending_value], ["Apply requirement", item.apply_requirement]].forEach(([label, value]) => facts.append(node("dt", label), node("dd", text(value))));
      row.append(facts, node("p", JSON.stringify(item.validation), "muted"));
      const operation = node("select");
      [["unchanged", "Keep unchanged"], ["set", "Set override"],
       ...(item.persisted_override_value !== null ? [["clear_override", "Reset to deployment/default"]] : [])]
        .forEach(([value, label]) => {const option = node("option", label); option.value = value; operation.append(option);});
      operation.disabled = !writable;
      const actionLabel = node("label", "Override action "); actionLabel.append(operation); row.append(actionLabel);
      const input = node(item.presentation_type === "multiline_plain_text" ? "textarea" : "input");
      if (input.tagName !== "TEXTAREA") input.type = item.presentation_type === "telephone" ? "tel" : item.presentation_type === "email" ? "email" : item.presentation_type === "restricted_url" ? "url" : "text";
      input.value = item.configured_value; input.disabled = true;
      // Browser lengths are advisory. Unicode code-point and all semantic checks remain server-owned.
      input.required = item.validation.required;
      input.maxLength = item.validation.max_length * 2; // UTF-16 must not reject valid code-point lengths.
      operation.addEventListener("change", () => {input.disabled = !writable || operation.value !== "set";});
      const valueLabel = node("label", "Value "); valueLabel.append(input); row.append(valueLabel);
      containers.get(item.group).append(row); controls.push({item, input, operation});
    });
  }
  async function load() {
    save.disabled = true; model = null; etag = null;
    const result = await request(root.dataset.apiBase, {headers: {Accept: "application/json"}});
    if (result.body.api_version !== "admin.settings.portal.v1" || !Array.isArray(result.body.settings) || result.body.settings.length !== 14) throw new Error("Invalid Portal model");
    model = result.body; etag = result.response.headers.get("ETag"); render(); save.disabled = !writable;
    status.textContent = `Configured generation ${model.configured_generation}; effective ${text(model.effective_generation)}. ` + (model.restart_required ? "Pending captive-portal.service restart." : "Current configured generation is adopted.");
  }
  function unavailable() {save.disabled = true; status.textContent = "Portal settings unavailable. No changes have been confirmed.";}
  document.getElementById("portal-settings-refresh").addEventListener("click", async () => {
    if (busy) return; busy = true;
    try {await load();} catch (_error) {unavailable();} finally {busy = false;}
  });
  document.getElementById("portal-settings-form").addEventListener("submit", async event => {
    event.preventDefault(); if (busy || !writable || !model || !etag) return;
    const changes = controls.filter(row => row.operation.value !== "unchanged").map(row => ({key: row.item.key,
      operation: row.operation.value, ...(row.operation.value === "set" ? {value: row.input.value} : {})}));
    if (!changes.length) {status.textContent = "No override changes selected."; return;}
    busy = true; save.disabled = true;
    try {
      const result = await request(root.dataset.apiBase + "/generations", {method: "POST", headers: {
        "Content-Type": "application/json", "X-CSRF-Token": root.dataset.csrfToken, "If-Match": etag,
        "Idempotency-Key": crypto.randomUUID()}, body: JSON.stringify({changes})});
      await load();
      status.textContent = result.body.changed ? "Saved successfully." + (result.body.restart_required ? " Pending captive-portal.service restart." : "") : "Accepted: no persisted override change.";
    } catch (error) {
      if (error.status === 412) {try {await load(); status.textContent = "Configuration changed concurrently. Review current values before another Save.";} catch (_error) {unavailable();}}
      else if (error.status === 422 || error.status === 400) {status.textContent = "Save rejected. Nothing was persisted. Review values and validation hints."; save.disabled = !writable;}
      else {unavailable();}
    } finally {busy = false;}
  });
  if (root.dataset.storeState === "available") load().catch(unavailable);
})();
