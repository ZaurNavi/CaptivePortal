"""DOM/Node acceptance for retained diagnostic attribution, not new claims."""
import json
from pathlib import Path
import subprocess

import pytest

from .test_admin_ui_frontend import NODE
from .test_fingerprint_origin_diagnostics import assets, retained_case, SITE, MAC

SCRIPT = Path(__file__).parents[2] / 'app/admin_web/static/admin.js'


@pytest.mark.skipif(NODE is None, reason='Node is required for frontend checks')
def test_A_B_C_source_attribution_and_provenance_grouping(retained_case):
    _, _, _, _, _, adapter = retained_case()
    fresh = adapter.get_detail(SITE, MAC).as_dict()
    _, _, _, _, _, adapter = retained_case('expired')
    expired = adapter.get_detail(SITE, MAC).as_dict()
    program = r'''
const fs = require('fs'), vm = require('vm'), assert = require('assert');
global.window = {};
vm.runInThisContext(fs.readFileSync(process.argv[1], 'utf8'));
const ui = window.CaptivPortalAdminTest;
const [fresh, expired] = JSON.parse(process.argv[2]);
const dimension = fresh.device_class_result;
const rows = Object.fromEntries(ui.fingerprintDetailEntries(dimension, fresh.origin_diagnostics, 'device_class'));
assert.strictEqual(dimension.status, 'resolved');
assert.strictEqual(dimension.canonical_value_id, 'smartphone');
assert(rows['Retained selected-value support'].includes('DHCP / K1 — resolved (smartphone)'));
assert(!rows['Retained selected-value support'].includes('knowledge_source_expired'));
assert(rows['Other-origin diagnostics (not selected-value support)'].includes('MAC registry / K4 — no_claim'));
assert(rows['Other-origin diagnostics (not selected-value support)'].includes('knowledge_source_expired'));
assert(rows['Aggregate explanation codes (all origins, not selected-value provenance)'].includes('knowledge_source_expired'));
const stale = Object.fromEntries(ui.fingerprintDetailEntries(expired.device_class_result, expired.origin_diagnostics, 'device_class'));
assert.notStrictEqual(expired.device_class_result.status, 'resolved');
assert(stale['Other-origin diagnostics (not selected-value support)'].includes('DHCP / K1 — no_claim'));
assert(stale['Other-origin diagnostics (not selected-value support)'].includes('knowledge_source_expired'));
const reference = dimension.knowledge_references[0];
assert(reference);
const seven = {...dimension, knowledge_references: Array.from({length:7}, (_, i) =>
  ({...reference, canonical_knowledge_record_id: `record-${i}`, rule_or_source_record_identity: `rule-${i}`}))};
const engineering = Object.fromEntries(ui.fingerprintDetailEntries(seven));
assert.strictEqual(engineering['Knowledge provenance grouping'], '7 record references · 1 provenance groups; not a count of independent sources');
for(let i = 0; i < 7; i++) assert(engineering['Knowledge references'].includes(`record-${i} · rule-${i}`));
assert(engineering['Knowledge references'].includes(reference.knowledge_provenance_id));
assert(engineering['Knowledge references'].includes(reference.knowledge_provenance_digest));
const unsupported = Object.fromEntries(ui.fingerprintDetailEntries(dimension, {state:'unavailable'}));
assert(unsupported['Origin diagnostics'].startsWith('Unavailable.'));
assert(!unsupported['Origin diagnostics'].includes('K4'));
'''
    completed = subprocess.run([NODE, '-e', program, str(SCRIPT), json.dumps([fresh, expired])], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr


@pytest.mark.skipif(NODE is None, reason='Node is required for frontend checks')
@pytest.mark.parametrize('diagnostics_available', [True, False])
def test_device_card_dom_keeps_resolved_value_and_discloses_retained_time(retained_case, tmp_path, diagnostics_available):
    from .test_device_current_context_frontend import _legacy_admin_source
    _, _, _, _, _, adapter = retained_case()
    fingerprint = adapter.get_detail(SITE, MAC).as_dict()
    if not diagnostics_available:
        fingerprint['origin_diagnostics'] = {'state': 'unavailable'}
    harness = r'''
const assert = require('assert');
class Element {
 constructor(tag) { this.tag=tag; this.children=[]; this.dataset={}; this.listeners={}; this.className=''; this.textContent=''; }
 addEventListener(kind, callback) { this.listeners[kind]=callback; }
 append(...items) { this.children.push(...items); }
 replaceChildren(...items) { this.children=items; }
 setAttribute() {} querySelector() { return null; }
}
const ids=['admin-page','page-content','page-state','state-title','state-message','refresh-button','pagination','load-more-button'];
const elements=Object.fromEntries(ids.map(id=>[id,new Element(id)]));
elements['admin-page'].dataset={page:'device',siteId:'0123456789abcdef01234567',apiBase:'/admin/api/v1/sites/0123456789abcdef01234567',deviceId:'10000000-0000-4000-8000-000000000001'};
global.document={getElementById:id=>elements[id]||null,createElement:tag=>new Element(tag)};
global.window={location:{pathname:'/admin/device',search:''},addEventListener(){}};
const fingerprint=JSON.parse(process.argv[2]);
let requests=0;
global.fetch=async()=>{ requests++; return {ok:true,status:200,headers:{get:()=>null},json:async()=>({result:{identity:{},latest_snapshot:{},latest_client_observation:{},recent_visits:[],fingerprint}})}; };
'''
    assertions = r'''
setImmediate(()=>{
 const card=elements['page-content'].children.find(card=>card.children[0].textContent==='Fingerprint Information');
 assert(card);
 const flatten=element=>[element.textContent,...element.children.flatMap(flatten)];
 const texts=flatten(card);
 assert(texts.includes('Smartphone'));
 assert(texts.includes('Android'));
 assert(texts.some(text=>text.includes('last retained production classification, not a live assessment')));
 assert(texts.some(text=>text.includes('aggregate expiry code is not proof')));
 assert(texts.includes('Aggregate explanation codes (all origins, not selected-value provenance)'));
 if(fingerprint.origin_diagnostics.state==='available') {
  assert(texts.includes('Retained selected-value support'));
  assert(texts.some(text=>text.includes('DHCP / K1 — resolved (smartphone)')));
  assert(texts.includes('Other-origin diagnostics (not selected-value support)'));
  assert(texts.some(text=>text.includes('MAC registry / K4 — no_claim')));
 } else assert(texts.some(text=>text.startsWith('Unavailable. Aggregate codes')));
 assert.strictEqual(requests,1);
 assert(!texts.includes('Unavailable')); // core card is still classified
 assert(!texts.includes('7 independent sources'));
});
'''
    probe = tmp_path / 'origin-card-dom.cjs'
    probe.write_text(harness + _legacy_admin_source() + assertions, encoding='utf-8')
    completed = subprocess.run([NODE, str(probe), json.dumps(fingerprint)], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
