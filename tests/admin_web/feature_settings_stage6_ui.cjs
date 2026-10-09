// Executes the actual dedicated script with disposable DOM/fetch; no network.
const fs = require("fs"), vm = require("vm"), assert = require("assert");
const [script, scenario, encoded] = process.argv.slice(2);
let model = JSON.parse(encoded);
class Element {
  constructor(tag = "div") { this.tagName = tag.toUpperCase(); this.children = []; this.listeners = {}; this.dataset = {}; this.attributes = {}; this.disabled = false; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  addEventListener(name, fn) { this.listeners[name] = fn; }
  setAttribute(name, value) { this.attributes[name] = value; }
}
const ids = ["settings-page", "status", "groups", "save", "refresh", "dirty"];
const nodes = Object.fromEntries(ids.map(id => ["features-" + id, new Element()]));
nodes["features-settings-page"].dataset = {apiBase: "/admin/api/v1/settings/features",
  csrfToken: "csrf", writeAllowed: scenario === "readonly" ? "false" : "true"};
const calls = [];
const context = {
  document: {getElementById: id => nodes[id], createElement: tag => new Element(tag)},
  crypto: {randomUUID: () => "11111111-1111-4111-8111-111111111111"},
  fetch: async (url, options) => {
    calls.push({url, options});
    const status = options.method === "POST" ? ({conflict: 412, invalid: 422, outage: 503}[scenario] || 201)
      : scenario === "loadoutage" ? 503 : 200;
    if (options.method === "POST" && status === 201) {
      model = JSON.parse(JSON.stringify(model));
      for (const change of JSON.parse(options.body).changes) {
        const row = model.features.find(row => row.key === change.key);
        row.configured_value = change.operation === "set" ? change.value : row.base_value;
        row.pending_value = row.configured_value === row.effective_value ? null : row.configured_value;
      }
      model.etag = '"settings-g1"';
    }
    return {ok: status < 400, status, json: async () => model};
  }
};
const descend = node => [node, ...node.children.flatMap(descend)];
const settle = () => new Promise(resolve => setImmediate(resolve));
const controls = () => descend(nodes["features-groups"]).filter(node => node.tagName === "INPUT");
const resets = () => descend(nodes["features-groups"]).filter(node => node.tagName === "BUTTON");
const text = () => descend(nodes["features-groups"]).map(node => node.textContent || "").join("\n");
(async () => {
  vm.runInNewContext(fs.readFileSync(script, "utf8"), context);
  assert.equal(nodes["features-save"].disabled, true);
  await settle();
  if (scenario === "loadoutage") {
    assert.equal(calls.length, 1);
    assert.equal(nodes["features-save"].disabled, true);
    assert(nodes["features-status"].textContent.includes("unavailable"));
    return;
  }
  assert.equal(controls().length, 17);
  assert.deepEqual(controls().map(node => node.checked), model.features.map(row => row.configured_value));
  assert.equal(resets().length, 1);
  assert(text().includes("<script>literal label</script>"));
  assert(text().includes("Dormant — parent disabled"));
  assert(text().includes("WEB_ADMIN_TRAFFIC_ENABLED"));
  assert(text().includes("Runtime unavailable"));
  assert(text().includes("Pending restart"));
  assert(!text().includes('{"type"'));
  assert(!text().includes("Healthy") && !text().includes("Connected"));
  await nodes["features-save"].listeners.click();
  assert.equal(calls.length, 1);
  if (scenario === "readonly") {
    assert(controls().every(node => node.disabled) && resets().every(node => node.disabled));
    controls()[0].checked = true; controls()[0].listeners.change();
    await nodes["features-save"].listeners.click();
    assert.equal(calls.length, 1);
    return;
  }
  const original = controls()[0].checked;
  controls()[0].checked = !original; controls()[0].listeners.change();
  assert.equal(calls.length, 1); // Browser candidate only.
  assert.equal(nodes["features-save"].disabled, false);
  controls()[0].checked = original; controls()[0].listeners.change();
  assert.equal(nodes["features-save"].disabled, true);
  if (scenario === "reset" || scenario === "reset_then_toggle") {
    resets()[0].listeners.click();
    if (scenario === "reset_then_toggle") {
      controls()[16].checked = !controls()[16].checked;
      controls()[16].listeners.change();
    }
  } else {
    controls()[0].checked = !original; controls()[0].listeners.change();
  }
  if (scenario === "refresh") {
    await nodes["features-refresh"].listeners.click();
    assert.equal(calls.length, 2);
    assert.equal(nodes["features-save"].disabled, true);
    return;
  }
  if (scenario === "parent_no_cascade") {
    // Editing a parent cannot mutate child switches or server-derived states.
    const child = controls()[5].checked;
    controls()[4].checked = !controls()[4].checked; controls()[4].listeners.change();
    assert.equal(controls()[5].checked, child);
    assert(text().includes("Dormant — parent disabled"));
  }
  const saving = nodes["features-save"].listeners.click();
  assert.equal(nodes["features-save"].disabled, true);
  assert.equal(nodes["features-refresh"].disabled, true);
  assert(controls().every(node => node.disabled));
  await nodes["features-save"].listeners.click(); // No duplicate in-flight POST.
  await saving;
  const submitted = calls[1];
  assert.equal(submitted.options.method, "POST");
  assert.equal(submitted.options.credentials, "same-origin");
  assert.equal(submitted.options.headers["X-CSRF-Token"], "csrf");
  assert.equal(submitted.options.headers["If-Match"], '"settings-g0"');
  assert.equal(submitted.options.headers["Idempotency-Key"], "11111111-1111-4111-8111-111111111111");
  const changes = JSON.parse(submitted.options.body).changes;
  if (scenario === "reset") assert.deepEqual(changes, [{key: model.features[16].key, operation: "clear_override"}]);
  else {
    assert(changes.every(change => change.operation === "set" && typeof change.value === "boolean"));
    assert.equal(changes.length, scenario === "parent_no_cascade" ? 2 : 1);
  }
  if (scenario === "invalid" || scenario === "outage") {
    assert.equal(calls.length, 2);
    assert.equal(nodes["features-save"].disabled, false); // Candidate retained.
    assert(nodes["features-status"].textContent.includes("preserved"));
    await nodes["features-save"].listeners.click();
    assert.equal(calls[2].options.body, submitted.options.body);
    assert.equal(calls[2].options.headers["Idempotency-Key"], submitted.options.headers["Idempotency-Key"]);
  } else {
    assert.equal(calls.length, 3); // Refresh authoritative GET, not mutation receipt values.
    assert.equal(nodes["features-save"].disabled, true);
    assert(nodes["features-status"].textContent.includes(scenario === "conflict" ? "changed elsewhere" : "Pending captive-portal.service restart"));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
