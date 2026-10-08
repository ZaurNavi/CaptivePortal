// Disposable UI execution: real dedicated script, no browser/network/storage.
const fs = require("fs");
const vm = require("vm");
const assert = require("assert");
const [script, template, scenario] = process.argv.slice(2);
const sentinel = "DISPOSABLE_STAGE4_UI_SECRET_47";
class Element {
  constructor(tag = "div") {
    this.tag = tag; this.children = []; this.listeners = {}; this.dataset = {};
    this.disabled = false; this.hidden = false; this.value = ""; this.textContent = "";
  }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = items; }
  setAttribute(key, value) { this[key] = value; }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  focus() { this.focused = true; }
}
const page = new Element();
page.dataset = {controllerState: "active", writeAllowed: scenario === "ordinary-writer" ? "true" : "false", csrfToken: "csrf"};
const state = new Element();
const fields = new Element();
const ordinarySave = scenario === "ordinary-writer" ? new Element("button") : null;
const nodes = {"controller-settings-page": page, "controller-settings-state": state,
  "controller-settings-fields": fields, "controller-settings-save": ordinarySave};
for (const name of ["controls", "editor", "new", "repeat", "replace", "clear", "save", "cancel"]) {
  nodes[`controller-secret-${name}`] = new Element();
}
const node = name => nodes[`controller-secret-${name}`];
node("controls").dataset.secretWriteAllowed = ["readonly", "ordinary-writer"].includes(scenario) ? "false" : "true";
node("editor").hidden = true;
const html = fs.readFileSync(template, "utf8");
const inputTags = [...html.matchAll(/<input\b[^>]*>/g)].map(match => match[0]);
assert.equal(inputTags.length, 2);
for (const name of ["new", "repeat"]) {
  const tag = inputTags.find(tag => tag.includes(`id="controller-secret-${name}"`));
  assert(tag);
  for (const key of ["type", "autocomplete", "spellcheck", "autocapitalize", "autocorrect"]) {
    node(name)[key] = tag.match(new RegExp(`${key}="([^"]+)"`))[1];
  }
  assert.equal(node(name).type, "password");
  assert.equal(node(name).autocomplete, "new-password");
}
const current = {api_version: "admin.settings.controller.v3", store_state: "available", mutation_available: true,
  secret_mutation_available: true, restart_required: false, pending_controller_setting_count: 0, fields: {}};
for (const [name, key] of [["controller_url", "OMADA_URL"], ["controller_id", "OMADA_ID"], ["client_id", "OMADA_CLIENT_ID"]]) {
  current.fields[name] = {setting_key: key, display_label: name, configured_value: "old", configured_source: "environment",
    effective_value: "effective", effective_source: "environment", persisted_override_value: "old", pending_value: null};
}
current.fields.client_secret = {display_label: "Client Secret", configured_presence: "configured", configured_source: "managed_secret_override",
  effective_presence: "configured", effective_source: "environment", persisted_secret_override_present: true,
  pending_replacement: true, secret_store_state: "available"};
current.fields.tls_certificate_verification = {display_label: "TLS", effective_value: false, effective_source: "repository_default"};
const calls = [], confirmations = [];
let sequence = 0, postCount = 0;
function forbidden() { throw new Error("forbidden UI persistence/logging"); }
const storage = {setItem: forbidden, getItem: forbidden, removeItem: forbidden};
const document = {getElementById: id => nodes[id], createElement: tag => new Element(tag), createTextNode: text => ({textContent: text})};
Object.defineProperty(document, "cookie", {set: forbidden, get: forbidden});
const context = {
  document, console: {log: forbidden, error: forbidden, warn: forbidden}, localStorage: storage, sessionStorage: storage,
  window: {confirm: text => { confirmations.push(text); return !["replace-cancel", "clear-cancel"].includes(scenario); },
    localStorage: storage, sessionStorage: storage, history: {pushState: forbidden, replaceState: forbidden}},
  crypto: {randomUUID: () => `disposable-key-${++sequence}`},
  fetch: async (url, options) => {
    assert(!url.includes(sentinel));
    calls.push({url, options});
    if (options.method === "GET") {
      return {ok: true, headers: {get: () => '"settings-g0"'}, json: async () => current};
    }
    postCount++;
    if (scenario.startsWith("network-") && postCount === 1 || scenario === "clear-network-retry" && postCount === 1) {
      throw new Error(sentinel); // Error text must not leak into UI/log/storage.
    }
    const status = scenario.startsWith("error-") ? Number(scenario.slice(6)) :
      scenario === "replay" ? 200 : scenario === "network-definitive" && postCount === 2 ? 409 : 201;
    return {status};
  }
};
function descend(element) { return [element, ...(element.children || []).flatMap(descend)]; }
const settle = () => new Promise(resolve => setImmediate(resolve));
async function click(name) { await node(name).listeners.click(); await settle(); }
function enter() { node("new").value = node("repeat").value = sentinel; }
function posts() { return calls.filter(item => item.options.method === "POST"); }
function clean() {
  assert.equal(node("new").value, ""); assert.equal(node("repeat").value, "");
  const rendered = [...Object.values(nodes).filter(Boolean), ...descend(fields)];
  assert(!rendered.some(item => String(item.textContent || "").includes(sentinel)));
  assert(confirmations.every(text => !text.includes(sentinel)));
}
function validSecretPost(call, operation = "replace_secret") {
  assert.equal(call.url, "/admin/api/v1/settings/controller/client-secret/generations");
  assert.equal(call.options.headers["X-CSRF-Token"], "csrf");
  assert.equal(call.options.headers["If-Match"], '"settings-g0"');
  assert.equal(call.options.credentials, "same-origin");
  assert.equal(call.options.cache, "no-store");
  assert.deepEqual(JSON.parse(call.options.body), operation === "replace_secret" ? {operation, secret: sentinel} : {operation});
}
(async () => {
  vm.runInNewContext(fs.readFileSync(script, "utf8"), context);
  await settle();
  clean();
  const inputs = descend(fields).filter(item => item.tag === "input" && item.type === "text");
  if (["readonly", "ordinary-writer"].includes(scenario)) {
    assert.equal(node("controls").hidden, true);
    assert.equal(node("replace").disabled, true); assert.equal(node("clear").disabled, true);
    enter(); await click("save"); assert.equal(posts().length, 0);
    if (scenario === "ordinary-writer") {
      assert.equal(inputs.length, 3);
      inputs[0].value = "new-ordinary-value";
      await ordinarySave.listeners.click(); await settle();
      assert.equal(posts().length, 1);
      assert.equal(posts()[0].url, "/admin/api/v1/settings/controller/generations");
      assert(!posts()[0].options.body.includes(sentinel));
    } else assert.equal(inputs.length, 0);
    return;
  }
  assert.equal(inputs.length, 0); // Secret authority does not imply ordinary write.
  assert.equal(node("controls").hidden, false); assert.equal(node("replace").disabled, false);
  assert.equal(node("clear").hidden, false);
  await click("replace"); enter();
  assert.equal(node("editor").hidden, false);
  if (scenario === "secret-writer") return;
  if (scenario === "mismatch") {
    node("repeat").value = "different";
    await click("save"); assert.equal(posts().length, 0); assert.equal(confirmations.length, 0); return;
  }
  if (scenario === "cancel") {
    await click("cancel"); clean(); assert.equal(node("editor").hidden, true); assert.equal(posts().length, 0); return;
  }
  const isClear = ["clear-success", "clear-cancel", "clear-network-retry", "network-switch-replace"].includes(scenario);
  await click(isClear ? "clear" : "save"); clean();
  if (["replace-cancel", "clear-cancel"].includes(scenario)) {
    assert.equal(posts().length, 0); return;
  }
  validSecretPost(posts()[0], isClear ? "clear_secret_override" : "replace_secret");
  assert(confirmations[0].includes(isClear ? "deployment/environment" : "cannot be read back"));
  assert(confirmations[0].includes("restart"));
  if (!isClear) {
    assert(confirmations[0].includes("will not be tested against Omada"));
    assert(confirmations[0].includes("running Controller connection remains unchanged"));
  }
  assert.deepEqual(calls.map(call => call.options.method), ["GET", "POST", "GET"]);
  if (scenario === "network-retry") {
    await click("save"); assert.equal(posts().length, 1); // Cleared raw value cannot be auto-retried.
    await click("replace"); enter(); await click("save"); clean();
    validSecretPost(posts()[1]);
    assert.equal(posts()[0].options.headers["Idempotency-Key"], posts()[1].options.headers["Idempotency-Key"]);
  } else if (scenario === "clear-network-retry") {
    await click("clear"); clean();
    validSecretPost(posts()[1], "clear_secret_override");
    assert.equal(posts()[0].options.headers["Idempotency-Key"], posts()[1].options.headers["Idempotency-Key"]);
  } else if (scenario === "network-switch-clear") {
    await click("clear"); clean(); validSecretPost(posts()[1], "clear_secret_override");
    assert.notEqual(posts()[0].options.headers["Idempotency-Key"], posts()[1].options.headers["Idempotency-Key"]);
  } else if (scenario === "network-switch-replace") {
    await click("replace"); enter(); await click("save"); clean(); validSecretPost(posts()[1]);
    assert.notEqual(posts()[0].options.headers["Idempotency-Key"], posts()[1].options.headers["Idempotency-Key"]);
  } else if (scenario === "network-cancel") {
    await click("cancel"); clean();
    await click("replace"); enter(); await click("save"); clean();
    assert.notEqual(posts()[0].options.headers["Idempotency-Key"], posts()[1].options.headers["Idempotency-Key"]);
  } else if (scenario === "network-definitive") {
    await click("replace"); enter(); await click("save"); clean(); // Same unresolved request gets a definitive 409.
    assert.equal(posts()[0].options.headers["Idempotency-Key"], posts()[1].options.headers["Idempotency-Key"]);
    await click("replace"); enter(); await click("save"); clean();
    assert.notEqual(posts()[1].options.headers["Idempotency-Key"], posts()[2].options.headers["Idempotency-Key"]);
  } else if (scenario === "error-412") {
    assert(state.textContent.includes("Configuration changed elsewhere"));
    await click("replace"); enter(); await click("save"); clean();
    assert.notEqual(posts()[0].options.headers["Idempotency-Key"], posts()[1].options.headers["Idempotency-Key"]);
  } else {
    assert.equal(node("editor").hidden, true);
  }
  clean();
})().catch(() => { process.stderr.write("Disposable Stage-4 UI behavior assertion failed\n"); process.exitCode = 1; });
