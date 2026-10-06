"use strict";

(() => {
  const page = document.getElementById("controller-settings-page");
  if (!page || page.dataset.controllerState !== "active") return;
  const state = document.getElementById("controller-settings-state");
  const fields = document.getElementById("controller-settings-fields");
  const keys = ["controller_url", "controller_id", "client_id", "client_secret", "tls_certificate_verification"];

  async function load() {
    try {
      const response = await fetch("/admin/api/v1/settings/controller", {
        method: "GET", credentials: "same-origin", cache: "no-store",
        headers: {Accept: "application/json"}
      });
      if (!response.ok) throw new Error("unavailable");
      const model = await response.json();
      if (model.api_version !== "admin.settings.controller.v1") throw new Error("unavailable");
      const rows = [];
      for (const key of keys) {
        const item = model.fields[key];
        const label = document.createElement("dt");
        label.textContent = item.display_label;
        const value = document.createElement("dd");
        const text = document.createElement("span");
        if (key === "client_secret") {
          text.textContent = item.effective_presence === "configured" ? "Configured" : "Not configured";
        } else if (key === "tls_certificate_verification") {
          text.textContent = item.effective_value ? "Enabled" : "Disabled";
        } else {
          text.textContent = item.effective_value;
        }
        const source = document.createElement("small");
        source.className = "controller-settings-source";
        source.textContent = item.effective_source === "environment" ? "Environment" : "Repository default";
        value.append(text, source);
        rows.push(label, value);
      }
      fields.replaceChildren(...rows);
      fields.hidden = false;
      state.textContent = "Read-only effective startup configuration.";
    } catch (_) {
      fields.replaceChildren();
      fields.hidden = true;
      state.textContent = "Controller configuration is unavailable.";
    }
  }
  load();
})();
