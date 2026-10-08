/* GLOBAL guest presentation. Server-owned metadata; no preview or restart authority. */
(function () {
  "use strict";
  const root = document.getElementById("portal-settings-page");
  if (!root) return;
  const status = document.getElementById("portal-settings-state");
  const statusTitle = document.getElementById("portal-settings-state-title");
  const statusMessage = document.getElementById("portal-settings-state-message");
  const generation = document.getElementById("portal-settings-generation");
  const adoptionNote = document.getElementById("portal-settings-adoption-note");
  const groups = document.getElementById("portal-settings-groups");
  const save = document.getElementById("portal-settings-save");
  const refresh = document.getElementById("portal-settings-refresh");
  const writable = root.dataset.writeAllowed === "true";
  let model = null, etag = null, busy = false, controls = [];
  const text = value => value === null ? "—" : String(value);
  function node(tag, value, className) {
    const element = document.createElement(tag);
    if (value !== undefined) element.textContent = value;
    if (className) element.className = className;
    return element;
  }
  function setStatus(title, message, state) {
    statusTitle.textContent = title; statusMessage.textContent = message;
    status.dataset.state = state;
  }
  function updateActions() {
    const editable = writable && model !== null && etag !== null && !busy;
    save.disabled = !editable || !controls.some(row => row.operation.value !== "unchanged");
    refresh.disabled = busy;
    root.setAttribute("aria-busy", String(busy));
    controls.forEach(row => {
      row.operation.disabled = !editable;
      row.input.disabled = !editable || row.operation.value !== "set";
    });
  }
  function sourceLabel(value) {
    return {repository_default: "Repository default", persisted_override: "Saved override",
      environment: "Deployment environment"}[value] || "Unavailable";
  }
  function validationHint(validation) {
    const parts = [validation.required ? "Required" : "Optional"];
    if (validation.content === "plain_text") parts.push("Plain text");
    if (validation.format === "support_phone_e164_display_v1") parts.push("International phone number");
    if (validation.format === "support_email_ascii_v1") parts.push("ASCII email address");
    if (validation.scheme === "https") parts.push("HTTPS");
    if (Array.isArray(validation.allowed_hosts)) parts.push(validation.allowed_hosts.join(" / ") + " only");
    if (Number.isInteger(validation.max_length)) parts.push(`Maximum ${validation.max_length} characters`);
    if (validation.line_policy === "single_line") parts.push("Single line");
    if (Number.isInteger(validation.max_lines)) parts.push(`Up to ${validation.max_lines} lines`);
    if (validation.fragment === "forbidden") parts.push("No fragment");
    if (validation.explicit_port === "forbidden") parts.push("No explicit port");
    if (validation.query_policy === "forbidden") parts.push("No query parameters");
    if (validation.query_policy === "none_or_locale_only") parts.push("Locale query only");
    return parts.join(" · ");
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
        if (item.group === "support") section.append(node("p", "This value is publicly visible to guests. No private credential or personal secret may be entered.", "portal-support-warning"));
        const grid = node("div", undefined, "portal-settings-grid " + (item.group === "branding" ? "portal-settings-grid--branding" : "portal-settings-grid--support"));
        section.append(grid); groups.append(section); containers.set(item.group, grid);
      }
      const row = node("article", undefined, "settings-item portal-setting-card");
      row.append(node("h3", item.display_label), node("p", item.description, "portal-setting-description"), node("p", item.key, "mono muted portal-setting-key"));
      const facts = node("dl", undefined, "settings-facts");
      [["Configured", item.configured_value], ["Effective", item.effective_value],
       ["Source", sourceLabel(item.persisted_override_value !== null ? "persisted_override" : item.base_source)],
       ["Pending", item.configured_value !== item.effective_value ? item.pending_value : null]].forEach(([label, value]) => {
         const pending = label === "Pending" && value !== null;
         const fact = node("dd", label === "Pending" && value === null ? "None" : text(value), "portal-setting-value" + (pending ? " portal-setting-pending" : ""));
         fact.dataset.fact = label;
         facts.append(node("dt", label), fact);
       });
      row.append(facts);
      const operation = node("select");
      [["unchanged", "No change"], ["set", "Use custom value"],
       ...(item.persisted_override_value !== null ? [["clear_override", "Reset to deployment/default"]] : [])]
        .forEach(([value, label]) => {const option = node("option", label); option.value = value; operation.append(option);});
      operation.disabled = !writable;
      const edit = node("div", undefined, "portal-setting-edit");
      const actionLabel = node("label", "Change "); actionLabel.append(operation); edit.append(actionLabel);
      const input = node(item.presentation_type === "multiline_plain_text" ? "textarea" : "input");
      input.className = "portal-setting-input";
      if (input.tagName === "TEXTAREA") input.rows = 4;
      if (input.tagName !== "TEXTAREA") input.type = item.presentation_type === "telephone" ? "tel" : item.presentation_type === "email" ? "email" : item.presentation_type === "restricted_url" ? "url" : "text";
      input.value = item.configured_value; input.disabled = true;
      // Browser lengths are advisory. Unicode code-point and all semantic checks remain server-owned.
      input.required = item.validation.required;
      input.maxLength = item.validation.max_length * 2; // UTF-16 must not reject valid code-point lengths.
      operation.addEventListener("change", updateActions);
      const hint = node("p", validationHint(item.validation), "muted portal-validation-hint");
      hint.id = "portal-validation-" + item.key;
      input.setAttribute("aria-describedby", hint.id);
      const valueLabel = node("label", "New value "); valueLabel.append(input); edit.append(valueLabel, hint);
      row.append(edit);
      containers.get(item.group).append(row); controls.push({item, input, operation});
    });
  }
  async function load() {
    save.disabled = true; model = null; etag = null;
    setStatus("Loading", "Requesting current guest portal settings…", "operational");
    const result = await request(root.dataset.apiBase, {headers: {Accept: "application/json"}});
    if (result.body.api_version !== "admin.settings.portal.v1" || !Array.isArray(result.body.settings) || result.body.settings.length !== 14) throw new Error("Invalid Portal model");
    model = result.body; etag = result.response.headers.get("ETag"); render();
    generation.textContent = `Configured generation ${model.configured_generation} · Effective generation ${text(model.effective_generation)}`;
    adoptionNote.hidden = !model.settings.some(item => item.apply_requirement === "main_service_restart");
    if (model.restart_required) setStatus("Pending restart", "Pending captive-portal.service restart.", "warning");
    else setStatus("Active", "All guest portal settings are active.", "operational");
  }
  function unavailable() {
    model = null; etag = null; generation.textContent = "";
    setStatus("Unavailable", "Portal settings unavailable. No changes have been confirmed.", "unavailable");
  }
  async function refreshSettings() {
    if (busy) return; busy = true; updateActions();
    try {await load();} catch (_error) {unavailable();} finally {busy = false; updateActions();}
  }
  refresh.addEventListener("click", refreshSettings);
  document.getElementById("portal-settings-form").addEventListener("submit", async event => {
    event.preventDefault(); if (busy || !writable || !model || !etag) return;
    const changes = controls.filter(row => row.operation.value !== "unchanged").map(row => ({key: row.item.key,
      operation: row.operation.value, ...(row.operation.value === "set" ? {value: row.input.value} : {})}));
    if (!changes.length) {updateActions(); return;}
    busy = true; updateActions();
    setStatus("Saving", "Saving selected changes…", "operational");
    try {
      const result = await request(root.dataset.apiBase + "/generations", {method: "POST", headers: {
        "Content-Type": "application/json", "X-CSRF-Token": root.dataset.csrfToken, "If-Match": etag,
        "Idempotency-Key": crypto.randomUUID()}, body: JSON.stringify({changes})});
      await load();
      setStatus("Save successful", (result.body.changed ? "Saved successfully." : "Accepted: no persisted override change.") +
        (model.restart_required ? " Pending captive-portal.service restart." : " All guest portal settings are active."), model.restart_required ? "warning" : "operational");
    } catch (error) {
      if (error.status === 412) {try {await load(); setStatus("Concurrent change", "Configuration changed concurrently. Review current values before another Save.", "warning");} catch (_error) {unavailable();}}
      else if (error.status === 422 || error.status === 400) {setStatus("Save rejected", "Save rejected. Nothing was persisted. Review values and validation hints.", "error");}
      else {unavailable();}
    } finally {busy = false; updateActions();}
  });
  if (root.dataset.storeState === "available") refreshSettings();
  else {unavailable(); updateActions();}
})();
