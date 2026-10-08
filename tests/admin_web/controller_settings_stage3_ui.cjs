// Disposable DOM/fetch boundary: execute the real dedicated script, no network.
const fs = require("fs");
const vm = require("vm");
const assert = require("assert");
const [script, scenario] = process.argv.slice(2);
class Element {
  constructor(tag = "div") { this.tag = tag; this.children = []; this.listeners = {}; this.disabled = false; this.checked = false; this.dataset = {}; }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = items; }
  setAttribute(key, value) { this[key] = value; }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  focus() {}
}
const page = new Element();
page.dataset = {controllerState: "active", writeAllowed: scenario === "readonly" ? "false" : "true", csrfToken: "csrf"};
const state = new Element();
const fields = new Element();
const save = scenario === "readonly" ? null : new Element("button");
const nodes = {"controller-settings-page": page, "controller-settings-state": state, "controller-settings-fields": fields, "controller-settings-save": save};
for (const name of ["controls", "editor", "new", "repeat", "replace", "clear", "save", "cancel"]) nodes[`controller-secret-${name}`] = new Element();
nodes["controller-secret-controls"].dataset.secretWriteAllowed = "false";
const current = {api_version: "admin.settings.controller.v3", store_state: scenario === "outage" ? "unavailable" : "available", mutation_available: !["outage", "mutation-unavailable"].includes(scenario), secret_mutation_available: true, restart_required: false, pending_controller_setting_count: 0, fields: {}};
for (const [name, key] of [["controller_url", "OMADA_URL"], ["controller_id", "OMADA_ID"], ["client_id", "OMADA_CLIENT_ID"]]) {
  current.fields[name] = {setting_key: key, display_label: name, configured_value: "old", configured_source: "environment", effective_value: "effective", effective_source: "environment", persisted_override_value: "old", pending_value: null};
}
current.fields.client_secret = {display_label: "Client Secret", configured_presence: "configured", configured_source: "environment", effective_presence: "configured", effective_source: "environment", persisted_secret_override_present: false, pending_replacement: false, secret_store_state: "available"};
current.fields.tls_certificate_verification = {display_label: "TLS", effective_value: false, effective_source: "repository_default"};
const calls = [];
let uuid = 0;
const confirmations = [];
const context = {
  document: {getElementById: id => nodes[id], createElement: tag => new Element(tag), createTextNode: text => ({textContent: text})},
  window: {confirm: text => { confirmations.push(text); return scenario !== "cancel"; }},
  crypto: {randomUUID: () => `unique-${++uuid}`},
  fetch: async (url, options) => {
    calls.push({url, options});
    if (options.method === "GET") return {ok: true, headers: {get: () => scenario === "outage" ? null : '"settings-g0"'}, json: async () => current};
    return {status: scenario === "conflict" ? 412 : scenario === "noop" ? 200 : 201};
  }
};
function descend(node) { return [node, ...(node.children || []).flatMap(descend)]; }
const settle = () => new Promise(resolve => setImmediate(resolve));
(async () => {
  vm.runInNewContext(fs.readFileSync(script, "utf8"), context);
  await settle();
  assert.equal(nodes["controller-secret-controls"].hidden, true);
  assert.equal(nodes["controller-secret-replace"].disabled, true);
  const inputs = descend(fields).filter(item => item.tag === "input" && item.type === "text");
  if (["outage", "readonly", "mutation-unavailable"].includes(scenario)) {
    assert.equal(current.mutation_available, scenario === "readonly");
    assert.equal(inputs.length, 0);
    if (save) assert.equal(save.disabled, true);
    assert.equal(calls.length, 1);
    return;
  }
  assert.equal(inputs.length, 3); // Never a secret/TLS input.
  if (scenario === "clear") {
    const clears = descend(fields).filter(item => item.tag === "input" && item.type === "checkbox");
    clears[0].checked = true;
    clears[0].listeners.change();
    assert.equal(inputs[0].disabled, true);
  } else inputs[0].value = "new";
  await save.listeners.click();
  await settle();
  assert(confirmations[0].includes("OMADA_URL"));
  assert(confirmations[0].includes("No connection test"));
  assert(confirmations[0].includes("restart/adoption"));
  assert(!confirmations[0].includes("new"));
  if (scenario === "cancel") { assert.equal(calls.length, 1); return; }
  assert.deepEqual(calls.map(item => item.options.method), ["GET", "POST", "GET"]);
  const changes = JSON.parse(calls[1].options.body).changes;
  assert.equal(changes.length, 1);
  assert.equal(changes[0].key, "OMADA_URL");
  assert.equal(changes[0].operation, scenario === "clear" ? "clear_override" : "set");
  assert.equal(calls[1].options.headers["X-CSRF-Token"], "csrf");
  assert.equal(calls[1].options.headers["If-Match"], '"settings-g0"');
  if (scenario === "conflict") {
    assert(state.textContent.includes("Review"));
    const next = descend(fields).find(item => item.tag === "input" && item.type === "text");
    next.value = "retry";
    await save.listeners.click();
    await settle();
    assert.notEqual(calls[1].options.headers["Idempotency-Key"], calls[3].options.headers["Idempotency-Key"]);
  }
})().catch(error => { process.stderr.write(error.stack); process.exitCode = 1; });
