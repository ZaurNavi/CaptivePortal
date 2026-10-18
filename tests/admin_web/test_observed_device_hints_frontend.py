import json
import subprocess
from pathlib import Path

import pytest

from app.admin_web.device_fingerprint_presentation import ObservedDeviceHintsPresentationService
from app.device_fingerprint.read_service import DeviceFingerprintReadService
from app.analytics.source_gateway import QueryDeadline
from tests.device_fingerprint.test_observed_hints import SITE, MAC, FIRST, AS_OF, portal, retained
from tests.device_fingerprint.test_network_schemas import tcp_v2, tls, quic
from .test_device_current_context_frontend import _legacy_admin_source, _node


@pytest.mark.parametrize("version", [1, 2])
def test_A01_A02_A05_A13_A16_safe_dom_full_groups_false_zero_40_options(retained, tmp_path, version):
    path, _, add = retained
    add(portal(version, **({"os_major": 0} if version == 2 else {})), version=version)
    add(dict(message_type="discover", parameter_request_list=[1, 3], option_order=[53, 55],
             vendor_class="<img src=x onerror=alert(1)>", client_identifier_kind="opaque",
             maximum_message_size=None, rapid_commit_requested=False, capport_requested=True,
             ipv6_only_preferred_requested=False, hostname_present=False), kind="dhcp")
    add(tcp_v2(tcp_header_length_bytes=60, tcp_window=0, tcp_option_records=[dict(
        record_type="nop", kind=1, declared_length=None, available_value_length=0,
        structure_state="well_formed") for _ in range(40)]), kind="tcp_syn", version=2)
    add(tls(), kind="tls_client")
    add(quic(), kind="quic_client")
    hints = ObservedDeviceHintsPresentationService(DeviceFingerprintReadService(str(path), retention_days=30)).get(
        SITE, MAC, site_first_seen_at=FIRST, as_of_utc=AS_OF, deadline=QueryDeadline.after(5))
    program = r'''
const assert = require("assert");
class Element {
  constructor(tag) {this.tag=tag;this.children=[];this.dataset={};this.listeners={};this.className="";this.textContent="";}
  append(...children) {this.children.push(...children);}
  replaceChildren(...children) {this.children=children;}
  addEventListener(name, fn) {this.listeners[name]=fn;}
  querySelector() {return null;}
  setAttribute() {}
  set innerHTML(_) {throw Error("unsafe HTML");}
}
const ids=["admin-page","page-content","page-state","state-title","state-message","refresh-button","pagination","load-more-button"];
const elements=Object.fromEntries(ids.map(id=>[id,new Element(id)]));
elements["admin-page"].dataset={page:"device",siteId:"0123456789abcdef01234567",apiBase:"/admin/api/v1/sites/0123456789abcdef01234567",deviceId:"10000000-0000-4000-8000-000000000001"};
global.document={getElementById:id=>elements[id]||null,createElement:tag=>new Element(tag)};
global.window={location:{pathname:"/admin/device",search:""},addEventListener(){}};
const hints=JSON.parse(process.argv[2]); let calls=0;
global.fetch=async()=>{calls++;return {ok:true,status:200,headers:{get:()=>null},json:async()=>({result:{
 identity:{device_type:"Android",device_type_key:"android"},fingerprint:{state:"no_result"},observed_device_hints:hints,recent_visits:[]}})};};
'''
    assertions = r'''
setImmediate(()=>{
 const cards=elements["page-content"].children;
 assert.strictEqual(calls,1);
 assert.strictEqual(cards[1].children[0].textContent,"Fingerprint Information");
 const card=cards[2]; assert(card.children[0].textContent.startsWith("Observed Device Hints"));
 assert(card.className.includes("fingerprint-card"));
 const walk=(element)=>[element,...element.children.flatMap(walk)];
 const nodes=walk(card); const text=nodes.map(n=>n.textContent).join("\n");
 assert(text.includes("Nokia G21"));
 assert(text.includes("2026-10-17T10:00:00.000Z"));
 assert(text.includes("earlier history not searched"));
 assert(text.includes("not a live service status"));
 assert(text.includes("<img src=x onerror=alert(1)>"));
 assert(!nodes.some(n=>n.tag==="img"||n.tag==="script"));
 assert(nodes.some(n=>n.tag==="dd" && n.textContent==="No"));
 assert(nodes.some(n=>n.tag==="dd" && n.textContent==="0"));
 assert(nodes.some(n=>n.tag==="dd" && n.textContent==="—"));
 assert.strictEqual(nodes.filter(n=>n.tag==="h4").length,40);
 assert.deepStrictEqual(nodes.filter(n=>n.tag==="h3").map(n=>n.textContent),["Portal / Browser","DHCP","TCP SYN","TLS Client","QUIC Client"]);
 const details=card.children.find(n=>n.tag==="details");
 assert.strictEqual(details.children[0].tag,"summary");
 assert.strictEqual(details.children[0].textContent,"All observed details");
 assert(!details.open);
 if(hints.reported_os.schema==="portal_headers/2") {
  assert(text.includes("OS major: 0 (reported, platform not provided)")); assert(!text.includes("Android 0"));
 } else assert(text.includes("Android 13"));
});
'''
    script = tmp_path / "observed-hints-dom.cjs"
    script.write_text(program + _legacy_admin_source() + assertions, encoding="utf-8")
    completed = subprocess.run([_node(), str(script), json.dumps(hints)], capture_output=True, text=True, timeout=20)
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_existing_wrapping_and_native_details_need_no_css_changes():
    root = Path(__file__).parents[2]
    css = (root / "app/admin_web/static/admin.css").read_text(encoding="utf-8")
    assert ".fingerprint-details dd { overflow-wrap: anywhere; }" in css
    source = (root / "app/admin_web/static/admin.js").read_text(encoding="utf-8")
    block = source.split("  // DF-RICH-HINTS-01:BEGIN\n")[1].split("  // DF-RICH-HINTS-01:END\n")[0]
    assert "innerHTML" not in block and "fetch(" not in block and "setInterval" not in block
    assert 'node("details", "fingerprint-details")' in block
