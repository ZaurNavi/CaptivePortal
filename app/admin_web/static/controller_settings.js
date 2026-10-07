"use strict";

(() => {
  const page = document.getElementById("controller-settings-page");
  if (!page || page.dataset.controllerState !== "active") return;
  const state = document.getElementById("controller-settings-state");
  const fields = document.getElementById("controller-settings-fields");
  const save = document.getElementById("controller-settings-save");
  const writable = ["controller_url", "controller_id", "client_id"];
  const keys = [...writable, "client_secret", "tls_certificate_verification"];
  const sources = {environment: "Environment", repository_default: "Repository default", persisted_override: "Persisted override"};
  const edits = new Map();
  let model = null;
  let etag = null;

  function note(parent, label, value) {
    const line = document.createElement("small");
    line.className = "controller-settings-source";
    line.textContent = `${label}: ${value === null || value === undefined ? "Unavailable" : value}`;
    parent.append(line);
  }

  async function load(message = null) {
    model = null;
    etag = null;
    edits.clear();
    if (save) save.disabled = true;
    fields.replaceChildren();
    try {
      const response = await fetch("/admin/api/v1/settings/controller", {
        method: "GET", credentials: "same-origin", cache: "no-store", headers: {Accept: "application/json"}
      });
      if (!response.ok) throw new Error("unavailable");
      const current = await response.json();
      if (current.api_version !== "admin.settings.controller.v2") throw new Error("unavailable");
      model = current;
      etag = response.headers.get("ETag");
      const canEdit = page.dataset.writeAllowed === "true" && current.mutation_available === true && etag !== null;
      const rows = [];
      for (const key of keys) {
        const item = current.fields[key];
        const label = document.createElement("dt");
        label.textContent = item.display_label;
        const value = document.createElement("dd");
        if (writable.includes(key)) {
          note(value, "Configured value", item.configured_value);
          note(value, "Configured source", sources[item.configured_source]);
          note(value, "Effective value", item.effective_value);
          note(value, "Effective source", sources[item.effective_source]);
          note(value, "Persisted override", item.persisted_override_value);
          if (item.pending_value !== null) {
            note(value, "Pending value", item.pending_value);
            note(value, "Pending source", sources[item.pending_source]);
          }
          if (canEdit) {
            const input = document.createElement("input");
            input.type = "text";
            input.value = item.configured_value;
            input.setAttribute("aria-label", item.display_label);
            const clearLabel = document.createElement("label");
            const clear = document.createElement("input");
            clear.type = "checkbox";
            clear.disabled = item.persisted_override_value === null;
            clear.addEventListener("change", () => { input.disabled = clear.checked; });
            clearLabel.append(clear, document.createTextNode(" Clear override / use deployment value"));
            value.append(input, clearLabel);
            edits.set(key, {input, clear, original: item.configured_value});
          }
        } else {
          note(value, "Effective", key === "client_secret" ? (item.effective_presence === "configured" ? "Configured" : "Not configured") : (item.effective_value ? "Enabled" : "Disabled"));
          note(value, "Source", sources[item.effective_source]);
          note(value, "Management", "Read-only / deployment-controlled");
        }
        rows.push(label, value);
      }
      fields.replaceChildren(...rows);
      fields.hidden = false;
      if (save) save.disabled = !canEdit;
      state.textContent = message || (current.store_state !== "available" ? "SettingsStore unavailable. Effective configuration only; mutation is disabled." :
        current.restart_required ? `Global Settings restart pending; ${current.pending_controller_setting_count} Controller fields pending.` : "Current configured and effective Controller configuration.");
      return true;
    } catch (_) {
      model = null;
      etag = null;
      fields.replaceChildren();
      fields.hidden = true;
      state.textContent = "Controller configuration is unavailable.";
      return false;
    }
  }

  async function submit() {
    if (!model || !etag || !save || save.disabled) return;
    const changes = [];
    for (const [key, edit] of edits) {
      const setting = model.fields[key].setting_key;
      if (edit.clear.checked) changes.push({key: setting, operation: "clear_override"});
      else if (edit.input.value !== edit.original) changes.push({key: setting, operation: "set", value: edit.input.value});
    }
    if (!changes.length) { state.textContent = "No changes selected."; return; }
    if (!window.confirm(`Persist ${changes.map(item => item.key).join(", ")}? No connection test will be performed. Current runtime configuration remains unchanged until external captive-portal.service restart/adoption.`)) return;
    save.disabled = true;
    try {
      const response = await fetch("/admin/api/v1/settings/controller/generations", {
        method: "POST", credentials: "same-origin", cache: "no-store",
        headers: {"Content-Type": "application/json", "X-CSRF-Token": page.dataset.csrfToken, "If-Match": etag, "Idempotency-Key": crypto.randomUUID()},
        body: JSON.stringify({changes})
      });
      if (response.status === 412) {
        await load("Configuration changed elsewhere. Review the reloaded values before saving again.");
        return;
      }
      if (response.status === 200 || response.status === 201) {
        // The receipt acknowledges the original durable operation, never field truth.
        await load("Configuration persisted. If restart is pending, current runtime still uses the effective configuration shown.");
        return;
      }
      await load("Save was not accepted. Review current configuration before retrying.");
    } catch (_) {
      await load("Save outcome unavailable. Review current configuration before retrying.");
    }
  }
  if (save) save.addEventListener("click", submit);
  load();
})();
