// Disposable DOM and fetch only: executes the actual Settings controller, no network.
const fs = require("fs"), vm = require("vm"), assert = require("assert");
const [script, scenario, encoded] = process.argv.slice(2);
const model = JSON.parse(encoded);
class Element {
  constructor(tag = "div") { this.tagName = tag.toUpperCase(); this.children = []; this.listeners = {}; this.dataset = {}; this.disabled = false; }
  append(...nodes) { if (this.tagName === "SELECT" && !this.children.length) this.value = nodes[0].value; this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  addEventListener(name, callback) { this.listeners[name] = callback; }
}
const ids = ["page", "state", "groups", "save", "refresh", "form"];
const nodes = Object.fromEntries(ids.map(id => ["portal-settings-" + id, new Element()]));
nodes["portal-settings-page"].dataset = {apiBase: "/admin/api/v1/settings/portal", storeState: "available", csrfToken: "csrf", writeAllowed: scenario === "readonly" ? "false" : "true"};
const calls = [];
const context = {
  document: {getElementById: id => nodes[id], createElement: tag => new Element(tag)},
  window: {setTimeout, clearTimeout}, AbortController,
  crypto: {randomUUID: () => "11111111-1111-4111-8111-111111111111"},
  fetch: async (url, options) => {
    calls.push({url, options});
    const status = options.method === "POST" ? ({conflict: 412, invalid: 422, outage: 503, noop: 200}[scenario] || 201) : 200;
    return {ok: status < 400, status, headers: {get: () => '"settings-g0"'}, json: async () => options.method === "POST" ? {changed: scenario !== "noop", restart_required: true} : model};
  }
};
const descend = node => [node, ...node.children.flatMap(descend)];
const settle = () => new Promise(resolve => setImmediate(resolve));
(async () => {
  vm.runInNewContext(fs.readFileSync(script, "utf8"), context);
  await settle();
  const all = descend(nodes["portal-settings-groups"]);
  const actions = all.filter(node => node.tagName === "SELECT");
  const inputs = all.filter(node => ["INPUT", "TEXTAREA"].includes(node.tagName));
  assert.equal(inputs.length, 14);
  assert.equal(inputs.filter(node => node.tagName === "TEXTAREA").length, 3);
  assert(all.some(node => node.textContent === "This value is publicly visible to guests. No private credential or personal secret may be entered."));
  assert.equal(actions[0].children.length, 2); // No reset without a persisted override.
  assert.equal(actions[13].children.length, 3);
  assert.equal(inputs[0].value, "<script>literal</script>");
  assert.equal(inputs[0].maxLength, model.settings[0].validation.max_length * 2);
  if (scenario === "readonly") {
    assert.equal(nodes["portal-settings-save"].disabled, true);
    assert(actions.every(node => node.disabled));
    await nodes["portal-settings-form"].listeners.submit({preventDefault() {}});
    assert.equal(calls.length, 1);
    return;
  }
  const index = scenario === "clear" ? 13 : 0;
  actions[index].value = scenario === "clear" ? "clear_override" : "set";
  actions[index].listeners.change();
  inputs[index].value = " exact unchanged input ";
  await nodes["portal-settings-form"].listeners.submit({preventDefault() {}});
  await settle();
  assert.equal(calls[1].options.method, "POST");
  const mutation = JSON.parse(calls[1].options.body);
  assert.deepEqual(mutation, {changes: [{key: model.settings[index].key, operation: scenario === "clear" ? "clear_override" : "set", ...(scenario === "clear" ? {} : {value: " exact unchanged input "})}]});
  assert.equal(calls[1].options.headers["X-CSRF-Token"], "csrf");
  assert.equal(calls[1].options.headers["If-Match"], '"settings-g0"');
  assert.equal(calls[1].options.headers["Idempotency-Key"], "11111111-1111-4111-8111-111111111111");
  assert.equal(calls[1].options.credentials, "same-origin");
  assert.equal(calls[1].options.cache, "no-store");
  const message = nodes["portal-settings-state"].textContent;
  if (scenario === "conflict") { assert.equal(calls.length, 3); assert(message.includes("Review current values")); }
  else if (scenario === "invalid") { assert.equal(calls.length, 2); assert(message.includes("Nothing was persisted")); }
  else if (scenario === "outage") { assert.equal(calls.length, 2); assert.equal(nodes["portal-settings-save"].disabled, true); }
  else if (scenario === "noop") { assert.equal(calls.length, 3); assert(message.includes("no persisted override change")); }
  else { assert.equal(calls.length, 3); assert(message.includes("Pending captive-portal.service restart")); }
})().catch(error => { console.error(error); process.exitCode = 1; });
