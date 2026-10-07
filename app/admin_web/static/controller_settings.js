"use strict";

(() => {
  const page = document.getElementById("controller-settings-page");
  if (!page || page.dataset.controllerState !== "active") return;
  const state = document.getElementById("controller-settings-state");
  const fields = document.getElementById("controller-settings-fields");
  const save = document.getElementById("controller-settings-save");
  const writable = ["controller_url", "controller_id", "client_id"];
  const keys = [...writable, "client_secret", "tls_certificate_verification"];
  const sources = {environment: "Environment", repository_default: "Repository default", persisted_override: "Persisted override", managed_secret_override: "Managed secret override"};
  const edits = new Map();
  let model = null;
  let etag = null;
  const secretControls = document.getElementById("controller-secret-controls");
  const secretEditor = document.getElementById("controller-secret-editor");
  const secretNew = document.getElementById("controller-secret-new");
  const secretRepeat = document.getElementById("controller-secret-repeat");
  const secretReplace = document.getElementById("controller-secret-replace");
  const secretClear = document.getElementById("controller-secret-clear");
  const secretSave = document.getElementById("controller-secret-save");
  let uncertainKey = null;
  let secretBusy = false;

  function wipeSecret() {
    secretNew.value = "";
    secretRepeat.value = "";
  }

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
      if (current.api_version !== "admin.settings.controller.v3") throw new Error("unavailable");
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
        } else if (key === "client_secret") {
          note(value, "Configured presence", item.configured_presence);
          note(value, "Configured source", sources[item.configured_source]);
          note(value, "Effective presence", item.effective_presence);
          note(value, "Effective source", sources[item.effective_source]);
          note(value, "Persisted managed override", item.persisted_secret_override_present);
          note(value, "Pending restart/replacement", item.pending_replacement);
          note(value, "Secret store", item.secret_store_state);
          note(value, "Management", "Write-only; no read-back");
        } else {
          note(value, "Effective", item.effective_value ? "Enabled" : "Disabled");
          note(value, "Source", sources[item.effective_source]);
          note(value, "Management", "Read-only / deployment-controlled");
        }
        rows.push(label, value);
      }
      fields.replaceChildren(...rows);
      fields.hidden = false;
      if (save) save.disabled = !canEdit;
      const canSecret = secretControls.dataset.secretWriteAllowed === "true" && current.secret_mutation_available === true && etag !== null;
      secretControls.hidden = !canSecret;
      secretReplace.disabled = !canSecret || secretBusy;
      secretClear.hidden = !canSecret || current.fields.client_secret.persisted_secret_override_present !== true;
      secretClear.disabled = !canSecret || secretBusy;
      state.textContent = message || (current.store_state !== "available" ? "SettingsStore unavailable. Effective configuration only; mutation is disabled." :
        current.restart_required ? `Global Settings restart pending; ${current.pending_controller_setting_count} Controller fields pending.` : "Current configured and effective Controller configuration.");
      return true;
    } catch (_) {
      model = null;
      etag = null;
      secretControls.hidden = true;
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
  secretReplace.addEventListener("click", () => { wipeSecret(); secretEditor.hidden = false; secretNew.focus(); });
  document.getElementById("controller-secret-cancel").addEventListener("click", () => { wipeSecret(); secretEditor.hidden = true; uncertainKey = null; });
  async function submitSecret(operation) {
    if (secretBusy || !model || !etag || model.secret_mutation_available !== true || secretControls.dataset.secretWriteAllowed !== "true") return;
    let value = null;
    if (operation === "replace_secret") {
      if (secretNew.value !== secretRepeat.value) { state.textContent = "Client Secret entries must match."; return; }
      value = secretNew.value;
    }
    const warning = operation === "replace_secret" ? "Replace Client Secret? The value cannot be read back later. Credentials will not be tested against Omada. The running Controller connection remains unchanged. An external captive-portal.service restart is required." : "Managed Client Secret will be removed. After the required external service restart, the deployment/environment secret will be used. No current secret will be displayed.";
    if (!window.confirm(warning)) { wipeSecret(); value = null; return; }
    const key = uncertainKey || crypto.randomUUID();
    secretBusy = true;
    secretSave.disabled = secretReplace.disabled = secretClear.disabled = true;
    let payload = {operation};
    if (value !== null) payload.secret = value;
    let body = null;
    try {
      body = JSON.stringify(payload);
      payload = null;
      value = null;
      const response = await fetch("/admin/api/v1/settings/controller/client-secret/generations", {
        method: "POST", credentials: "same-origin", cache: "no-store",
        headers: {"Content-Type": "application/json", "X-CSRF-Token": page.dataset.csrfToken, "If-Match": etag, "Idempotency-Key": key}, body
      });
      body = null;
      wipeSecret();
      uncertainKey = null;
      secretEditor.hidden = true;
      if (response.status === 412) {
        await load("Configuration changed elsewhere. Re-enter the secret after reviewing the reloaded configuration.");
      } else if (response.status === 200 || response.status === 201) {
        await load("Client Secret saved. The running process still uses the current effective secret. Credentials were not tested against Omada. An externally performed captive-portal.service restart is required.");
      } else {
        await load("Client Secret was not accepted. Re-enter after reviewing the configuration.");
      }
    } catch (_) {
      uncertainKey = key;
      await load("Save outcome unavailable. Re-enter the secret to retry with the same operation key.");
    } finally {
      payload = value = body = null;
      wipeSecret();
      secretBusy = false;
      secretSave.disabled = false;
      const canSecret = model && model.secret_mutation_available === true && etag !== null;
      secretReplace.disabled = secretClear.disabled = !canSecret;
    }
  }
  secretSave.addEventListener("click", () => submitSecret("replace_secret"));
  secretClear.addEventListener("click", () => submitSecret("clear_secret_override"));
  load();
})();
