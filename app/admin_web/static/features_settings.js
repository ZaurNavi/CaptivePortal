"use strict";
(() => {
  const page = document.getElementById("features-settings-page");
  if (!page) return;
  const writable = page.dataset.writeAllowed === "true";
  const base = page.dataset.apiBase;
  const status = document.getElementById("features-status");
  const groups = document.getElementById("features-groups");
  const save = document.getElementById("features-save");
  const refresh = document.getElementById("features-refresh");
  const dirty = document.getElementById("features-dirty");
  const pending = new Map();
  let model = null;
  let busy = false;
  let receipt = null;
  const stateLabels = {enabled: "Enabled", disabled: "Disabled",
    dormant_parent_disabled: "Dormant — parent disabled", runtime_unavailable: "Runtime unavailable"};
  const boolText = value => value === null ? "Unavailable" : value ? "On" : "Off";
  function node(tag, text, className) {
    const item = document.createElement(tag);
    if (text !== undefined) item.textContent = text;
    if (className) item.className = className;
    return item;
  }
  function controls() {
    save.disabled = busy || !writable || !model || pending.size === 0;
    refresh.disabled = busy;
    dirty.textContent = pending.size ? pending.size + " unsaved change(s)" : "No unsaved changes";
  }
  function render() {
    groups.replaceChildren();
    for (const [group, title] of [["home", "Home"], ["traffic", "Traffic"], ["devices", "Devices"]]) {
      const section = node("section", undefined, "feature-settings-group");
      section.append(node("h2", title));
      for (const row of model.features.filter(item => item.group === group)) {
        const article = node("article", undefined, "feature-settings-row");
        const label = node("label", undefined, "feature-settings-label");
        const toggle = node("input");
        toggle.type = "checkbox";
        toggle.setAttribute("role", "switch");
        toggle.setAttribute("aria-label", row.display_label);
        const change = pending.get(row.key);
        toggle.checked = change ? change.operation === "set" ? change.value : row.base_value : row.configured_value;
        toggle.disabled = !writable || busy;
        toggle.addEventListener("change", () => {
          const wasReset = pending.get(row.key)?.operation === "clear_override";
          if (!wasReset && toggle.checked === row.configured_value) pending.delete(row.key);
          else pending.set(row.key, {key: row.key, operation: "set", value: toggle.checked});
          receipt = null;
          controls();
        });
        label.append(toggle, node("strong", row.display_label));
        article.append(label, node("code", row.key, "muted"), node("p", row.description, "muted"));
        const details = node("dl", undefined, "feature-settings-details");
        for (const [name, text] of [
          ["Configured", boolText(row.configured_value)], ["Effective", boolText(row.effective_value)],
          ["Source", row.configured_source], ["Pending", row.pending_value === null ? "—" : boolText(row.pending_value) + " · Pending restart"],
          ["Configured state", stateLabels[row.configured_feature_state]],
          ["Effective state", stateLabels[row.effective_feature_state]],
          ["Configured blocked by", row.configured_blocked_by_feature_keys.join(", ") || "—"],
          ["Effective blocked by", row.effective_blocked_by_feature_keys.join(", ") || "—"]
        ]) details.append(node("dt", name), node("dd", text));
        article.append(details, node("p", "Boolean preference. Disabled parents preserve child preferences.", "muted"));
        if (row.persisted_override_value !== null) {
          const reset = node("button", "Reset to deployment/default", "button button-secondary");
          reset.type = "button"; reset.disabled = !writable || busy;
          reset.addEventListener("click", () => {
            pending.set(row.key, {key: row.key, operation: "clear_override"});
            receipt = null; render(); controls();
          });
          article.append(reset);
        }
        section.append(article);
      }
      groups.append(section);
    }
    controls();
  }
  async function read(discard) {
    const response = await fetch(base, {credentials: "same-origin", cache: "no-store"});
    if (!response.ok) throw new Error("Settings unavailable. Local changes are preserved.");
    const next = await response.json();
    if (next.api_version !== "admin.settings.features.v1" || next.features.length !== 17) throw new Error("Invalid feature response.");
    model = next;
    if (discard) { pending.clear(); receipt = null; }
    render();
  }
  refresh.addEventListener("click", async () => {
    busy = true; controls();
    try { await read(true); status.textContent = "Feature preferences refreshed."; }
    catch (error) { status.textContent = error.message; }
    finally { busy = false; renderIfReady(); }
  });
  function renderIfReady() { if (model) render(); else controls(); }
  save.addEventListener("click", async () => {
    if (!writable || busy || !model || pending.size === 0) return;
    busy = true; render();
    try {
      const body = JSON.stringify({changes: Array.from(pending.values()).sort((a, b) => a.key.localeCompare(b.key))});
      if (!receipt || receipt.body !== body) receipt = {body, key: crypto.randomUUID(), etag: model.etag};
      const response = await fetch(base + "/generations", {method: "POST", credentials: "same-origin",
        headers: {"Content-Type": "application/json", "X-CSRF-Token": page.dataset.csrfToken,
          "If-Match": receipt.etag, "Idempotency-Key": receipt.key}, body: receipt.body});
      if (response.status === 412) {
        await read(true);
        status.textContent = "Settings changed elsewhere. Refreshed current preferences; review before saving.";
      } else if (response.ok) {
        await read(true);
        status.textContent = "Persisted successfully. Pending captive-portal.service restart.";
      } else {
        status.textContent = response.status === 422 ? "Configuration prerequisites are invalid. Local changes are preserved for correction."
          : "Settings unavailable or request rejected. Local changes are preserved.";
      }
    } catch (error) { status.textContent = error.message; }
    finally { busy = false; renderIfReady(); }
  });
  controls();
  read(false).catch(error => { status.textContent = error.message; controls(); });
})();
