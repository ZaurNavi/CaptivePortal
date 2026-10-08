// Disposable DOM and fetch only: executes the actual Settings controller, no network.
const fs = require("fs"), vm = require("vm"), assert = require("assert");
const [script, scenario, encoded] = process.argv.slice(2);
const model = JSON.parse(encoded);
class Element {
  constructor(tag = "div") { this.tagName = tag.toUpperCase(); this.children = []; this.listeners = {}; this.dataset = {}; this.attributes = {}; this.disabled = false; }
  append(...nodes) { if (this.tagName === "SELECT" && !this.children.length) this.value = nodes[0].value; this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  setAttribute(name, value) { this.attributes[name] = value; }
}
const ids = ["page", "state", "state-title", "state-message", "generation", "adoption-note", "groups", "save", "refresh", "form"];
const nodes = Object.fromEntries(ids.map(id => ["portal-settings-" + id, new Element()]));
nodes["portal-settings-page"].dataset = {apiBase: "/admin/api/v1/settings/portal", storeState: "available", csrfToken: "csrf", writeAllowed: scenario === "readonly" ? "false" : "true"};
const calls = [];
const context = {
  document: {getElementById: id => nodes[id], createElement: tag => new Element(tag)},
  window: {setTimeout, clearTimeout}, AbortController,
  crypto: {randomUUID: () => "11111111-1111-4111-8111-111111111111"},
  fetch: async (url, options) => {
    calls.push({url, options});
    const status = options.method === "POST" ? ({conflict: 412, invalid: 422, badrequest: 400, outage: 503, noop: 200}[scenario] || 201) : scenario === "loadoutage" ? 503 : 200;
    if (options.method === "POST" && status === 201) {
      model.configured_generation = 1; model.restart_required = true;
      for (const change of JSON.parse(options.body).changes) {
        const item = model.settings.find(item => item.key === change.key);
        item.configured_value = change.operation === "set" ? change.value : item.default_value;
        item.pending_value = item.configured_value !== item.effective_value ? item.configured_value : null;
      }
    }
    return {ok: status < 400, status, headers: {get: () => '"settings-g0"'}, json: async () => options.method === "POST" ? {changed: scenario !== "noop", restart_required: true} : model};
  }
};
const descend = node => [node, ...node.children.flatMap(descend)];
const settle = () => new Promise(resolve => setImmediate(resolve));
(async () => {
  vm.runInNewContext(fs.readFileSync(script, "utf8"), context);
  assert.equal(nodes["portal-settings-state-title"].textContent, "Loading");
  assert.equal(nodes["portal-settings-save"].disabled, true);
  assert.equal(nodes["portal-settings-refresh"].disabled, true);
  await settle();
  if (scenario === "loadoutage") {
    assert.equal(nodes["portal-settings-state-title"].textContent, "Unavailable");
    assert.equal(nodes["portal-settings-state"].dataset.state, "unavailable");
    assert.equal(nodes["portal-settings-save"].disabled, true);
    assert.equal(calls.length, 1);
    return;
  }
  const all = descend(nodes["portal-settings-groups"]);
  const actions = all.filter(node => node.tagName === "SELECT");
  const inputs = all.filter(node => ["INPUT", "TEXTAREA"].includes(node.tagName));
  assert.equal(inputs.length, 14);
  assert.equal(inputs.filter(node => node.tagName === "TEXTAREA").length, 3);
  assert(all.some(node => node.textContent === "This value is publicly visible to guests. No private credential or personal secret may be entered."));
  assert.equal(all.filter(node => node.className === "portal-support-warning").length, 1);
  assert.equal(all.filter(node => node.className && node.className.includes("portal-settings-grid--branding")).length, 1);
  assert.equal(all.filter(node => node.className && node.className.includes("portal-settings-grid--support")).length, 1);
  const hints = all.filter(node => node.className === "muted portal-validation-hint");
  assert.equal(hints.length, 14);
  assert(hints[0].textContent.includes(`Maximum ${model.settings[0].validation.max_length} characters`));
  assert(hints[0].textContent.includes("Required · Plain text"));
  assert(hints[0].textContent.includes("Single line"));
  assert(hints[6].textContent.includes(`Up to ${model.settings[6].validation.max_lines} lines`));
  assert(hints[9].textContent.includes("Optional · International phone number"));
  assert(hints[10].textContent.includes("Optional · ASCII email address"));
  assert(hints[12].textContent.includes(model.settings[12].validation.allowed_hosts.join(" / ") + " only"));
  assert(hints[13].textContent.includes("Locale query only"));
  const renderedText = all.map(node => node.textContent || "").join("\n");
  for (const forbidden of ["bidi_controls", "max_length", "main_service_restart", "Apply requirement", "Override action", "Keep unchanged", "Set override"])
    assert(!renderedText.includes(forbidden));
  for (const source of ["repository_default", "persisted_override", "environment"])
    assert(!all.some(node => node.textContent === source));
  assert(all.some(node => node.textContent === "Repository default"));
  assert(all.some(node => node.textContent === "Saved override"));
  if (scenario === "environment") assert(all.some(node => node.textContent === "Deployment environment"));
  inputs.forEach((input, index) => {
    assert.equal(input.attributes["aria-describedby"], hints[index].id);
    assert.equal(input.className, "portal-setting-input");
    if (input.tagName === "TEXTAREA") assert.equal(input.rows, 4);
  });
  const rows = all.filter(node => node.tagName === "ARTICLE");
  rows.forEach((row, index) => {
    const facts = descend(row).filter(node => node.tagName === "DD");
    assert.deepEqual(facts.map(node => node.dataset.fact), ["Configured", "Effective", "Source", "Pending"]);
    assert.equal(facts[0].textContent, model.settings[index].configured_value);
    assert.equal(facts[1].textContent, model.settings[index].effective_value === null ? "—" : model.settings[index].effective_value);
    assert(facts[0].className.includes("portal-setting-value"));
    assert(facts[1].className.includes("portal-setting-value"));
    if (model.settings[index].pending_value !== null) {
      assert.equal(facts[3].textContent, model.settings[index].pending_value);
      assert(facts[3].className.includes("portal-setting-pending"));
    } else assert.equal(facts[3].textContent, "None");
  });
  if (scenario === "pending") {
    assert.equal(nodes["portal-settings-state-title"].textContent, "Pending restart");
    assert.equal(nodes["portal-settings-state"].dataset.state, "warning");
    assert.equal(nodes["portal-settings-state-message"].textContent, "Pending captive-portal.service restart.");
  } else {
    assert.equal(nodes["portal-settings-state-title"].textContent, "Active");
    assert.equal(nodes["portal-settings-state-message"].textContent, "All guest portal settings are active.");
  }
  assert.equal(nodes["portal-settings-save"].disabled, true);
  assert.equal(nodes["portal-settings-refresh"].disabled, false);
  await nodes["portal-settings-form"].listeners.submit({preventDefault() {}});
  assert.equal(calls.length, 1); // Zero selected changes never POST.
  assert.equal(actions[0].children.length, 2); // No reset without a persisted override.
  assert.equal(actions[13].children.length, 3);
  assert.equal(inputs[0].value, "<script>literal</script>");
  assert.equal(inputs[0].maxLength, model.settings[0].validation.max_length * 2);
  if (scenario === "readonly") {
    assert.equal(nodes["portal-settings-save"].disabled, true);
    assert(actions.every(node => node.disabled));
    assert(inputs.every(node => node.disabled));
    actions[0].value = "set"; actions[0].listeners.change();
    assert.equal(nodes["portal-settings-save"].disabled, true);
    await nodes["portal-settings-form"].listeners.submit({preventDefault() {}});
    assert.equal(calls.length, 1);
    return;
  }
  actions[0].value = "set"; actions[0].listeners.change();
  assert.equal(nodes["portal-settings-save"].disabled, false);
  assert.equal(inputs[0].disabled, false);
  actions[0].value = "unchanged"; actions[0].listeners.change();
  assert.equal(nodes["portal-settings-save"].disabled, true);
  assert.equal(inputs[0].disabled, true);
  actions[13].value = "clear_override"; actions[13].listeners.change();
  assert.equal(nodes["portal-settings-save"].disabled, false);
  assert.equal(inputs[13].disabled, true);
  actions[13].value = "unchanged"; actions[13].listeners.change();
  assert.equal(nodes["portal-settings-save"].disabled, true);
  if (scenario === "dirty") {
    actions[6].value = "set"; actions[6].listeners.change();
    inputs[6].value = "First line\nSecond line";
    assert.equal(nodes["portal-settings-save"].disabled, false);
    assert.equal(inputs[6].tagName, "TEXTAREA");
    assert.equal(inputs[6].value, "First line\nSecond line");
    await nodes["portal-settings-refresh"].listeners.click();
    assert.equal(calls.length, 2);
    assert.equal(nodes["portal-settings-save"].disabled, true);
    assert(descend(nodes["portal-settings-groups"]).filter(node => node.tagName === "SELECT").every(node => node.value === "unchanged"));
    return;
  }
  const index = scenario === "clear" ? 13 : 0;
  actions[index].value = scenario === "clear" ? "clear_override" : "set";
  actions[index].listeners.change();
  inputs[index].value = " exact unchanged input ";
  const saving = nodes["portal-settings-form"].listeners.submit({preventDefault() {}});
  assert.equal(nodes["portal-settings-save"].disabled, true);
  assert.equal(nodes["portal-settings-refresh"].disabled, true);
  assert(actions.every(node => node.disabled));
  assert(inputs.every(node => node.disabled));
  await nodes["portal-settings-form"].listeners.submit({preventDefault() {}}); // No duplicate in-flight POST.
  await saving;
  await settle();
  assert.equal(calls[1].options.method, "POST");
  const mutation = JSON.parse(calls[1].options.body);
  assert.deepEqual(mutation, {changes: [{key: model.settings[index].key, operation: scenario === "clear" ? "clear_override" : "set", ...(scenario === "clear" ? {} : {value: " exact unchanged input "})}]});
  assert.equal(calls[1].options.headers["X-CSRF-Token"], "csrf");
  assert.equal(calls[1].options.headers["If-Match"], '"settings-g0"');
  assert.equal(calls[1].options.headers["Idempotency-Key"], "11111111-1111-4111-8111-111111111111");
  assert.equal(calls[1].options.credentials, "same-origin");
  assert.equal(calls[1].options.cache, "no-store");
  const message = nodes["portal-settings-state-message"].textContent;
  if (scenario === "conflict") { assert.equal(calls.length, 3); assert(message.includes("Review current values")); assert.equal(nodes["portal-settings-save"].disabled, true); }
  else if (scenario === "invalid" || scenario === "badrequest") { assert.equal(calls.length, 2); assert(message.includes("Nothing was persisted")); assert.equal(nodes["portal-settings-state"].dataset.state, "error"); assert.equal(nodes["portal-settings-save"].disabled, false); }
  else if (scenario === "outage") { assert.equal(calls.length, 2); assert.equal(nodes["portal-settings-save"].disabled, true); }
  else if (scenario === "noop") { assert.equal(calls.length, 3); assert(message.includes("no persisted override change")); assert.equal(nodes["portal-settings-save"].disabled, true); }
  else { assert.equal(calls.length, 3); assert(message.includes("Pending captive-portal.service restart")); assert.equal(nodes["portal-settings-save"].disabled, true); }
  assert(calls.every(call => call.options.credentials === "same-origin" && call.options.cache === "no-store"));
})().catch(error => { console.error(error); process.exitCode = 1; });
