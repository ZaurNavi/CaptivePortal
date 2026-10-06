from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
import subprocess
import shutil

from jinja2 import Environment, FileSystemLoader, select_autoescape
import pytest


ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "app/admin_web/static"
SOURCE = (STATIC / "admin.js").read_text(encoding="utf-8")
NODE = shutil.which("node")


class Dom(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.stack = []
        self.ids = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        item = dict(attrs)
        item["ancestors"] = self.stack[:]
        if "id" in item:
            self.ids[item["id"]] = item
        if tag not in {"meta", "link", "img", "input", "br", "hr"}:
            self.stack.append(item)

    def handle_endtag(self, tag):
        if self.stack:
            self.stack.pop()


def render(page, **flags):
    env = Environment(loader=FileSystemLoader(ROOT / "app/admin_web/templates"),
                      autoescape=select_autoescape())
    return env.get_template(f"admin/{page}.html").render(
        page={"key": page, "title": page.title()}, site_id="synthetic-site",
        url_for=lambda *args, **kwargs: "/admin/static/" + kwargs["filename"], **flags,
    )


def function(name):
    start = SOURCE.index(f"  function {name}(")
    following = re.search(r"\n  (?:async )?function ", SOURCE[start + 1:])
    assert following is not None
    return SOURCE[start:start + 1 + following.start()]


FAKE_NODE = r'''
const assert=require('assert'); global.window={};
function node(tag,className,text) {return {tag,className,textContent:text,
  children:[],dataset:{},style:{},attributes:{},append(...xs){this.children.push(...xs)},
  replaceChildren(...xs){this.children=xs},setAttribute(k,v){this.attributes[k]=v}};}
'''


def run_node(program):
    assert NODE is not None, "Node is required for WEB-UX-PACK-03"
    result = subprocess.run([NODE, "-e", program], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_home_one_ap_card_and_home_only_type_style():
    html = render("home", home_live_enabled=True, home_ap_24h_enabled=True)
    dom = Dom(html)
    parents = dom.ids["home-ap-24h"]["ancestors"]
    assert any(parent.get("aria-labelledby") == "aps-now-title" for parent in parents)
    assert "card" not in dom.ids["home-ap-24h"]["class"].split()
    assert "home-ap-24h-items" not in dom.ids and "home-ap-24h-more" not in dom.ids
    assert "live-ap-more" in dom.ids
    css = (STATIC / "admin.css").read_text(encoding="utf-8")
    assert ".live-fingerprint-type-cell .fingerprint-type-icon { display: flex; width: 44px; height: 44px; margin-inline: auto; }" in css
    assert ".live-fingerprint-type-cell .fingerprint-type-icon img { width: 44px; height: 44px; }" in css
    assert "width: 22px; height: 22px;" in css
    assert ".content { min-width: 0;" in css
    assert ".traffic-ap-subsection .traffic-ap-card { grid-column: auto; }" in css
    assert '.live-table thead th.live-fingerprint-type-header,' in css
    assert '.live-table tbody td.live-fingerprint-type-cell { text-align: center;' in css
    assert '.ap24-segment[data-state="unknown"] { background: #d92d20; }' in css
    for state, color in [("operational", "#12a594"), ("degraded", "#f4b740"), ("unavailable", "#d92d20")]:
        assert f'.ap24-segment[data-state="{state}"] {{ background: {color}; }}' in css


def test_roster_exact_join_timeline_before_devices_and_history_failure_is_local():
    run_node(FAKE_NODE + "require(" + repr((STATIC / "admin.js").as_posix()) + ");" + r'''
const api=window.CaptivPortalHomeLiveTest, target=node('div'), footer=node('p');
const mac='AA:BB:CC:DD:EE:01', second='AA:BB:CC:DD:EE:02';
const history={history:{status:'unknown',unavailable_seconds:0},observation_quality:{status:'unknown'},
  timeline:Array.from({length:96},(_,i)=>({ap_state:i?'operational':'unknown',from_utc:'TIME',observation_quality:'unknown'}))};
const cache=new Map([[second,history]]); let available=true;
window.CaptivPortalHomeAp24Coordinator={lookup:m=>available?cache.get(m)||null:null};
const rows=[{ap_mac:mac,name:'Same name',product_status_classification:'online'},
  {ap_mac:second,name:'Same name',product_status_classification:'online'}];
const clients={devices_by_ap:[{ap_mac:mac,client_count:2}],counts:{ap_unknown:0}};
const rates=[{ap_mac:second,rate_status:'valid',download_mbps:0,upload_mbps:null,total_mbps:0,selected_source:'wired',observed_at:'TIME'}];
const render=r=>api.renderAccessPointRoster(node,target,footer,r,clients,true,rates,true,true,x=>x==null?'—':x+' Mbps');
render(rows.slice(0,1)); assert.equal(target.children[0].children[2].children.length,1);
render(rows); const row=target.children[1];
assert.equal(target.children.length,2); assert.equal(row.children[0].children[0].textContent,'Same name');
assert.equal(row.children[1].textContent,second); assert.equal(row.children[2].className,'ap24-history');
assert.equal(row.children[3].className,'ap-device-count');
const segment=row.children[2].children[1].children[0];
assert.equal(segment.dataset.state,'unknown'); assert(segment.title.includes('unknown'));
assert.deepEqual(row.children[5].children.map(x=>x.children[1].textContent),['0 Mbps','—','0 Mbps']);
assert.equal(row.children[6].textContent,'Source Wired · observed TIME');
available=false; render(rows);
assert.equal(target.children.length,2); assert.equal(target.children[1].children[1].textContent,second);
assert.equal(target.children[1].children[2].children.length,1);
assert.equal(target.children[0].children[3].children[0].textContent,'Devices · 2');
assert.equal(target.children[1].children[5].children[0].children[1].textContent,'0 Mbps');
''')


def test_closed_visit_uses_existing_binary_formatter_only():
    run_node(FAKE_NODE + "\n".join(function(name) for name in
        ["display", "compactDecimal", "formatDeviceBytes", "definitionList", "visitRow"]) + r'''
for(const [value,shown] of [[0,'0 B'],[842,'842 B'],[1024,'1 KB'],[1048576,'1 MB'],
  [19608371,'18.7 MB'],[2300000000,'2.14 GB'],[1099511627776,'1 TB'],[null,'—']]) {
  const row=visitRow({status:'closed',started_at:'TIME',duration_seconds:71,reported_traffic_total_bytes:value});
  const fields=row.children[1].children;
  const traffic=fields.findIndex(x=>x.tag==='dt'&&x.textContent==='Traffic');
  assert(traffic>=0); assert.equal(fields[traffic+1].textContent,shown);
  assert(!fields.some(x=>x.textContent==='Traffic (bytes)'));
  const duration=fields.findIndex(x=>x.textContent==='Duration (s)');
  assert.equal(fields[duration+1].textContent,'71');
}
''')


@pytest.mark.parametrize("independent", [False, True])
@pytest.mark.parametrize("aps,evidence", [(True, True), (False, True), (True, False)])
def test_traffic_combined_card_and_completed_last(independent, aps, evidence):
    html = render("traffic", traffic_enabled=True, traffic_history_enabled=True,
        traffic_by_ap_enabled=aps, traffic_statistics_enabled=True, traffic_peak_enabled=True,
        traffic_ap_share_enabled=True, traffic_independent_ranges_enabled=independent,
        traffic_evidence_allowed=True, traffic_evidence_enabled=evidence,
        traffic_completed_sessions_allowed=True, traffic_completed_sessions_enabled=True)
    dom = Dom(html)
    panels = [key for key in dom.ids if key.endswith("-panel") and key.startswith("traffic-")]
    assert panels[-1] == "traffic-completed-sessions-panel"
    assert ("Network &amp; AP Traffic History" if aps else "Network Traffic History") in html
    if aps:
        assert "card" not in dom.ids["traffic-ap-panel"]["class"].split()
        assert dom.ids["traffic-history-panel"] in dom.ids["traffic-ap-panel"]["ancestors"]
        assert html.index('id="traffic-history-chart-svg"') < html.index('id="traffic-ap-items"')
        assert ("traffic-ap-range" in dom.ids) == independent
    for key in ["traffic-statistics-panel", "traffic-peak-panel", "traffic-apshare-panel"]:
        assert dom.ids["traffic-history-panel"] not in dom.ids[key]["ancestors"]


def test_natural_order_is_copy_only_with_exact_mac_tie_break():
    run_node(FAKE_NODE + function("apPresentationOrder") + r'''
const input=[{display_name:'AP10',ap_mac:'01'}, {display_name:'AP2',ap_mac:'02'},
  {display_name:'ap1',ap_mac:'03'},{display_name:'AP1',ap_mac:'04'}];
const before=JSON.stringify(input), sorted=apPresentationOrder(input);
assert.deepEqual(sorted.map(x=>x.display_name),['ap1','AP1','AP2','AP10']);
assert.deepEqual(sorted.slice(0,2).map(x=>x.ap_mac),['03','04']);
assert.equal(JSON.stringify(input),before); assert.notEqual(sorted,input);
''')
