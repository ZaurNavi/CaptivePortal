"""Task-06 keeps controller facts separate from the advisory fingerprint UI."""

import subprocess
import json
from pathlib import Path

import pytest

from .test_admin_ui_frontend import NODE


@pytest.mark.skipif(NODE is None, reason="Node is required for frontend checks")
def test_fingerprint_summary_details_and_separate_controller_surface():
    script = Path(__file__).parents[2] / "app/admin_web/static/admin.js"
    program = r'''
const fs = require("fs");
const vm = require("vm");
const assert = require("assert");
global.window = {};
vm.runInThisContext(fs.readFileSync(process.argv[1], "utf8"));
const ui = window.CaptivPortalAdminTest;
const missing = ui.fingerprintSummaryEntries({state: "no_result"});
assert.strictEqual(missing.length, 6);
assert.strictEqual(ui.display(missing[0][1]), "—");
assert(missing.slice(2).every(row => row[1] === "—"));
assert.strictEqual(ui.fingerprintSummaryEntries({state: "unavailable"})[0][1], "Unavailable");
const dimension = {value: "Smartphone", canonical_value_id: "smartphone", status: "resolved",
  support_level: "medium", supporting_origin_groups: ["dhcp"], contradicting_origin_groups: ["portal"],
  not_evaluable_origin_groups: ["tcp"], out_of_scope_taxon_references: ["outside"],
  explanation_codes: ["exact_code"], knowledge_references: [{canonical_knowledge_record_id: "record-1",
    rule_or_source_record_identity: "source-1", knowledge_provenance_id: "provenance-1",
    knowledge_provenance_digest: "digest-1", knowledge_bundle_id: "bundle-1", knowledge_bundle_digest: "bundle-digest-1"}]};
const fingerprint = {state: "classified", global_classification_status: "partial",
  classified_at_utc: "2026-10-04T00:00:00.000Z", device_class_result: dimension,
  platform_result: {...dimension, value: "ChromeOS", canonical_value_id: "chromeos"},
  manufacturer_result: {...dimension, value: "Unknown", status: "insufficient_evidence", canonical_value_id: null},
  model_result: {...dimension, value: "Unknown", status: "recognized_out_of_scope", canonical_value_id: null}};
const summary = ui.fingerprintSummaryEntries(fingerprint);
assert.deepStrictEqual(summary.map(row => row[0]),
  ["Status", "Classified at", "Type", "Fingerprint Platform", "Manufacturer", "Model Family"]);
assert.strictEqual(summary[2][1], "Smartphone");
assert.strictEqual(summary[2][3], "medium");
assert.strictEqual(summary[3][1], "ChromeOS");
assert.strictEqual(summary[4][1], "Unknown");
assert.strictEqual(summary[4][3], null);
assert.strictEqual(summary[5][3], null);
const diagnostics = Object.fromEntries(ui.fingerprintDetailEntries(dimension));
assert.strictEqual(Object.keys(diagnostics).length, 9);
assert.strictEqual(diagnostics["Canonical value"], "smartphone");
assert.strictEqual(diagnostics["Status"], "resolved");
assert.strictEqual(diagnostics["Support level"], "medium");
assert.strictEqual(diagnostics["Supporting sources"], "dhcp");
assert.strictEqual(diagnostics["Contradicting sources"], "portal");
assert.strictEqual(diagnostics["Not-evaluable sources"], "tcp");
assert.strictEqual(diagnostics["Out-of-scope references"], "outside");
assert.strictEqual(diagnostics["Explanation codes"], "exact_code");
assert(diagnostics["Knowledge references"].includes("record-1"));
assert(diagnostics["Knowledge references"].includes("bundle-digest-1"));
const controller = ui.deviceIdentityEntries({device_type: "Android", device_type_key: "android"});
assert.strictEqual(controller.find(row => row[0] === "Controller Platform")[1], "Android");
const completedUnknown = ui.fingerprintSummaryEntries({...fingerprint,
  global_classification_status: "unknown",
  device_class_result: {...dimension, value: "Unknown", status: "unknown", canonical_value_id: null, support_level: "none"}});
assert.strictEqual(completedUnknown[0][1], "unknown");
assert.notStrictEqual(completedUnknown[0][1], "Unavailable");
assert.strictEqual(completedUnknown[2][1], "Unknown");
assert.strictEqual(completedUnknown[2][3], null);
assert.notStrictEqual(completedUnknown[2][1], controller.find(row => row[0] === "Controller Platform")[1]);
'''
    completed = subprocess.run([NODE, "-e", program, str(script)], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    source = script.read_text(encoding="utf-8")
    assert 'card("Fingerprint Information", fingerprintSummaryEntries(fingerprint))' in source
    assert 'node("summary", null, "Fingerprint details")' in source
    assert "fingerprintCard(result.fingerprint)" in source
    assert source.count("[identity, presentation.fingerprintType, presentation.deviceType") == 2
    css = script.with_name("admin.css").read_text(encoding="utf-8")
    assert "overflow-x: auto" in css
    assert ".fingerprint-details dd { overflow-wrap: anywhere; }" in css


@pytest.mark.skipif(NODE is None, reason="Node is required for frontend checks")
@pytest.mark.parametrize("state", ["no_result", "unavailable", "classified"])
def test_device_card_safe_dom_renders_summary_and_optional_diagnostics(state, tmp_path):
    from .test_device_current_context_frontend import _legacy_admin_source

    dimension = {"value": "Smartphone", "canonical_value_id": "smartphone", "status": "resolved",
                 "support_level": "medium", "supporting_origin_groups": ["dhcp"],
                 "contradicting_origin_groups": [], "not_evaluable_origin_groups": [],
                 "out_of_scope_taxon_references": [], "explanation_codes": ["exact_code"],
                 "knowledge_references": []}
    fingerprint = {"state": state}
    if state == "classified":
        fingerprint.update(global_classification_status="partial", classified_at_utc="2026-10-04T00:00:00.000Z",
                           device_class_result=dimension,
                           platform_result={**dimension, "value": "ChromeOS", "canonical_value_id": "chromeos"},
                           manufacturer_result={**dimension, "value": "Unknown", "status": "unknown", "canonical_value_id": None},
                           model_result={**dimension, "value": "Unknown", "status": "insufficient_evidence", "canonical_value_id": None})
    harness = r'''
const assert = require("assert");
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.dataset = {}; this.listeners = {}; this.className = ""; this.textContent = ""; }
  addEventListener(kind, callback) { this.listeners[kind] = callback; }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = items; }
  setAttribute() {}
  querySelector() { return null; }
}
const ids = ["admin-page", "page-content", "page-state", "state-title", "state-message", "refresh-button", "pagination", "load-more-button"];
const elements = Object.fromEntries(ids.map(id => [id, new Element(id)]));
elements["admin-page"].dataset = {page: "device", siteId: "0123456789abcdef01234567",
  apiBase: "/admin/api/v1/sites/0123456789abcdef01234567", deviceId: "10000000-0000-4000-8000-000000000001"};
global.document = {getElementById: id => elements[id] || null, createElement: tag => new Element(tag)};
global.window = {location: {pathname: "/admin/device", search: ""}, addEventListener() {}};
const fingerprint = JSON.parse(process.argv[2]);
global.fetch = async () => ({ok: true, status: 200, headers: {get: () => null}, json: async () => ({result: {
  identity: {canonical_mac: "02:00:00:00:00:01", device_type: "Android", device_type_key: "android"},
  latest_snapshot: {}, latest_client_observation: {}, recent_visits: [], fingerprint}})});
'''
    assertions = r'''
setImmediate(() => {
  const cards = elements["page-content"].children;
  assert(cards.some(card => card.children[0].textContent === "Identity"));
  const card = cards.find(card => card.children[0].textContent === "Fingerprint Information");
  assert(card);
  assert(card.className.includes("fingerprint-card"));
  const list = card.children[1].children;
  assert.strictEqual(list.length, 12);
  const status = list[1].textContent;
  if (fingerprint.state === "unavailable") assert.strictEqual(status, "Unavailable");
  if (fingerprint.state === "no_result") assert.strictEqual(status, "—");
  if (fingerprint.state === "classified") {
    assert.strictEqual(status, "partial");
    assert.strictEqual(list[5].children[0].textContent, "Smartphone");
    assert.strictEqual(list[5].children[1].textContent, "medium");
    assert.strictEqual(list[7].children[0].textContent, "ChromeOS");
    assert.strictEqual(list[9].children[0].textContent, "Unknown");
    assert.strictEqual(list[9].children.length, 1);
    const details = card.children.find(child => child.tag === "details");
    assert.strictEqual(details.children[0].textContent, "Fingerprint details");
    assert.strictEqual(details.children.filter(child => child.tag === "h3").length, 4);
  } else assert(!card.children.some(child => child.tag === "details"));
});
'''
    probe = tmp_path / "task06-device-card.js"
    probe.write_text(harness + _legacy_admin_source() + assertions, encoding="utf-8")
    completed = subprocess.run([NODE, str(probe),
                                json.dumps(fingerprint)], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
