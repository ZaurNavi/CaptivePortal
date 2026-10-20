#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO = Path(r"C:\CaptivPortal-UI-Preview")
EXPECTED_HEAD = "7df71a8e807efd74b123117e78cb8d992c190fa1"
EXPECTED_TREE = "8f1342f0a0f1e8242642161e02b2f3276e6ddf51"
EXPECTED_DIRTY = {
    "app/admin_web/static/admin.css",
    "app/admin_web/static/admin.js",
}
SITE = "0123456789abcdef01234567"
DEVICE_IDS = [f"10000000-0000-4000-8000-{i:012d}" for i in range(1, 13)]
MACS = [f"02:00:00:00:00:{i:02X}" for i in range(1, 13)]
ADMIN_JS = REPO / "app" / "admin_web" / "static" / "admin.js"
ADMIN_CSS = REPO / "app" / "admin_web" / "static" / "admin.css"


def git(*args: str) -> str:
    cp = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True)
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr.strip() or cp.stdout.strip())
    return cp.stdout.strip()


def verify_candidate() -> None:
    head = git("rev-parse", "HEAD")
    tree = git("show", "-s", "--format=%T", "HEAD")
    if head != EXPECTED_HEAD:
        raise RuntimeError(f"Unexpected HEAD: {head}")
    if tree != EXPECTED_TREE:
        raise RuntimeError(f"Unexpected baseline TREE: {tree}")
    status = git("status", "--porcelain")
    dirty = set()
    for line in status.splitlines():
        if len(line) >= 4:
            dirty.add(line[3:].replace("\\", "/"))
    if dirty != EXPECTED_DIRTY:
        raise RuntimeError(f"Expected only patched CSS/JS dirty; got: {sorted(dirty)}")
    cp = subprocess.run(["git", "-C", str(REPO), "diff", "--check"], capture_output=True, text=True)
    if cp.returncode != 0:
        raise RuntimeError("git diff --check failed:\n" + (cp.stdout + cp.stderr))
    if not ADMIN_JS.is_file() or not ADMIN_CSS.is_file():
        raise RuntimeError("Patched Admin assets are missing")


def device_item(index: int) -> dict:
    i = index + 1
    return {
        "device_id": DEVICE_IDS[index],
        "canonical_mac": MACS[index],
        "device_type": ["phone", "laptop", "tablet", "unknown"][index % 4],
        "site_first_seen_at": f"2026-08-{10 + (index % 15):02d}T08:15:00.000Z",
        "site_last_seen_at": f"2026-09-09T{11 - (index % 6):02d}:{55 - index:02d}:00.000Z",
        "site_snapshot_count": 12 + i * 3,
        "site_visit_count": 2 + (i % 8),
        "last_site_ip": f"192.168.10.{40 + i}",
        "last_site_ssid": "Zefer_Parki" if index % 3 else "Guest_WiFi",
        "last_site_ap_mac": f"AA:BB:CC:DD:EE:{(20 + i):02X}",
    }


def historical_result(device_index: int) -> dict:
    item = device_item(device_index)
    return {
        "result": {
            "identity": {
                "canonical_mac": item["canonical_mac"],
                "device_type": item["device_type"],
                "site_first_seen_at": item["site_first_seen_at"],
                "site_last_seen_at": item["site_last_seen_at"],
                "site_snapshot_count": item["site_snapshot_count"],
                "site_visit_count": item["site_visit_count"],
            },
            "latest_snapshot": {
                "authorized_at": "2026-09-09T10:20:00.000Z",
                "captured_at": "2026-09-09T11:54:00.000Z",
                "name": None,
                "hostname": None,
                "system_name": None,
                "device_type": item["device_type"],
                "ip": item["last_site_ip"],
                "ssid": item["last_site_ssid"],
                "ap_name": "EAP613-1",
                "ap_mac": item["last_site_ap_mac"],
                "radio_id": 1,
                "channel": 44,
                "rssi": -52,
                "snr": 31,
                "traffic_down": 45678912,
                "traffic_up": 5368709120,
                "uptime": 93600,
                "active": True,
                "auth_status": 2,
            },
            "latest_client_observation": {
                "observed_at": "2026-09-09T11:53:30.000Z",
                "client_mac": item["canonical_mac"],
                "ip": item["last_site_ip"],
                "ssid": item["last_site_ssid"],
                "ap_mac": item["last_site_ap_mac"],
                "rssi": -61,
                "snr": 25,
                "traffic_down": 123456789,
                "traffic_up": 9876543,
                "uptime": 7200,
            },
            "recent_visits": [
                {
                    "status": "closed",
                    "client_mac": item["canonical_mac"],
                    "started_at": "2026-09-09T09:15:00.000Z",
                    "closed_at": "2026-09-09T11:45:00.000Z",
                    "duration_seconds": 9000,
                    "start_ssid": item["last_site_ssid"],
                    "final_ssid": item["last_site_ssid"],
                    "start_ap_mac": item["last_site_ap_mac"],
                    "final_ap_mac": item["last_site_ap_mac"],
                    "reported_traffic_total_bytes": 987654321,
                }
            ],
        }
    }


def current_result(device_index: int) -> dict:
    item = device_item(device_index)
    cycle = "11111111-1111-4111-8111-111111111111"
    baseline = "22222222-2222-4222-8222-222222222222"
    return {
        "result": {
            "contract_version": "admin.device.current.v1",
            "site_id": SITE,
            "device_id": item["device_id"],
            "evaluated_at_utc": "2026-09-09T12:00:00.000Z",
            "scope": {
                "scope_type": "client_ssid_allowlist",
                "site_id": SITE,
                "ssids": ["Zefer_Parki"],
            },
            "current_state": {
                "presence_status": "online",
                "presence_reason": "present_in_fresh_complete_scope",
                "snapshot": {
                    "cycle_id": cycle,
                    "observed_at": "2026-09-09T11:57:00.000Z",
                    "capture_finished_at": "2026-09-09T11:57:00.000Z",
                    "age_seconds": 180,
                    "freshness_status": "fresh",
                    "freshness_reason": "within_freshness_window",
                    "complete": True,
                },
                "authorization": {"classification": "authorized", "reason": "current_row"},
                "client": {
                    "client_mac": item["canonical_mac"],
                    "name": "Fixture Phone",
                    "hostname": "fixture-phone",
                    "device_type": item["device_type"],
                    "ip": item["last_site_ip"],
                    "ssid": item["last_site_ssid"],
                    "ap_name": "EAP613-1",
                    "ap_mac": item["last_site_ap_mac"],
                    "radio_id": 1,
                    "band": "5GHz",
                    "channel": 44,
                    "rssi": -52,
                    "snr": 31,
                    "controller_uptime": 93600,
                    "controller_traffic_down_bytes": 45678912,
                    "controller_traffic_up_bytes": 5368709120,
                    "controller_traffic_total_bytes": 5414388032,
                    "active": True,
                    "wireless": True,
                },
            },
            "current_guest_traffic": {
                "applicability": "applicable",
                "applicability_reason": "authorized_current_guest",
                "source_health_status": "healthy",
                "source_health_reason": "within_freshness_window",
                "rate_evidence_status": "complete",
                "current_cycle_id": cycle,
                "baseline_cycle_id": baseline,
                "elapsed_seconds": 60,
                "item": {
                    "download_mbps": 0.126738492,
                    "upload_mbps": 1.253847293,
                    "total_mbps": 1.380585785,
                    "rate_status": "valid",
                    "source_progress_status": "advanced",
                    "connection_continuity_status": "proven",
                    "continuity_basis": "uptime_progress",
                    "download_reason": "valid",
                    "upload_reason": "valid",
                    "total_reason": "valid",
                },
                "failure_reason": None,
            },
        }
    }


def shell(page: str, body: str, device_id: str | None = None, demo: bool = False) -> bytes:
    device_attr = f' data-device-id="{device_id}"' if device_id else ""
    demo_banner = """
<div class="preview-note"><strong>Status demo mode:</strong> first rows are recolored by fixture-only JavaScript. This does NOT exist in the production PATCH.</div>
""" if demo else ""
    demo_js = """
<script>
setTimeout(() => {
  const rows = document.querySelectorAll('.device-row');
  const states = [['online','Online'],['online','Online'],['offline','Offline'],['unknown','Unknown']];
  rows.forEach((row, i) => {
    const s = row.querySelector('.device-status');
    if (!s) return;
    const [state,label] = states[i % states.length];
    s.dataset.status = state; s.lastChild.textContent = label; s.setAttribute('aria-label', 'Current status ' + label.toLowerCase());
  });
}, 250);
</script>
""" if demo else ""
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CaptivPortal UI Lab Preview</title><link rel="stylesheet" href="/candidate-admin.css">
<style>.preview-note{{margin:0 0 1rem;padding:.8rem 1rem;border:1px dashed #d08b00;border-radius:10px;background:#fff9e8}} .preview-links a{{margin-right:.8rem}}</style>
<script defer src="/candidate-admin.js"></script></head><body>
<header class="topbar"><a class="brand" href="/admin/sites/{SITE}/devices"><span class="brand-mark">CP</span><span>CaptivPortal</span></a>
<div class="topbar-context"><span class="eyebrow">Current Site</span><strong class="mono">{SITE}</strong></div><div class="topbar-account"><span>Lab Owner</span></div></header>
<div class="app-frame"><nav class="sidebar" aria-label="Admin navigation"><a class="nav-link" href="#">Home</a><a class="nav-link is-active" href="/admin/sites/{SITE}/devices">Devices</a><a class="nav-link" href="#">Visits</a><a class="nav-link" href="#">Observations</a><a class="nav-link" href="#">Traffic</a></nav>
<main id="main-content" class="content"><div class="page-heading"><div><p class="eyebrow">Read-only operations</p><h1>{'Devices' if page=='devices' else 'Device Detail'}</h1><p>{'Compact list design preview' if page=='devices' else 'Human-readable Device Detail preview'}</p></div><button id="refresh-button" class="button" type="button">Refresh</button></div>
<div class="preview-links"><a href="/admin/sites/{SITE}/devices">Actual list behavior</a><a href="/demo/status">Status lamp visual demo</a></div>{demo_banner}
<section id="admin-page" data-page="{page}" data-site-id="{SITE}" data-api-base="/admin/api/v1/sites/{SITE}"{device_attr}>
{body}
</section></main></div>{demo_js}</body></html>"""
    return html.encode("utf-8")


def devices_page(demo: bool = False) -> bytes:
    body = """
<form id="device-search-form" class="filter-bar" novalidate>
<label for="device-mac">Exact MAC address</label><input id="device-mac" name="mac" autocomplete="off" placeholder="AA:BB:CC:DD:EE:FF" maxlength="17">
<button class="button button-secondary" type="submit">Search</button><button id="clear-device-search" class="button button-quiet" type="button">Clear</button></form>
<div id="page-state" class="state-panel" role="status" aria-live="polite"><span class="state-dot"></span><div><strong id="state-title">Loading</strong><p id="state-message">Requesting current Site data…</p></div></div>
<div id="page-content" class="content-grid" aria-live="polite"></div>
<div id="pagination" class="pagination" hidden><button id="load-more-button" class="button button-secondary" type="button">Load more</button></div>
"""
    return shell("devices", body, demo=demo)


def device_page(device_id: str) -> bytes:
    body = """
<div id="page-state" class="state-panel" role="status" aria-live="polite"><span class="state-dot"></span><div><strong id="state-title">Loading</strong><p id="state-message">Requesting historical Device context…</p></div></div>
<div id="page-content" class="content-grid" aria-live="polite"></div>
<div id="pagination" class="pagination" hidden><button id="load-more-button" class="button button-secondary" type="button">Load more</button></div>
<section id="device-current-context" class="section-card" aria-labelledby="device-current-context-title"><div class="section-heading"><div><h2 id="device-current-context-title">Current Device Context</h2><p>Current managed Site/SSID evidence, independent from historical device context.</p></div></div>
<div id="device-current-state" class="state-panel" role="status" aria-live="polite"><span class="state-dot"></span><div><strong id="device-current-state-title">Loading</strong><p id="device-current-state-message">Requesting current device evidence…</p></div></div>
<div id="device-current-content" class="content-grid" aria-live="polite"></div></section>
"""
    return shell("device", body, device_id=device_id)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        return

    def send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status); self.send_header("Content-Type", content_type); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def send_json(self, value: dict, status: int = 200) -> None:
        self.send_bytes(status, json.dumps(value, separators=(",", ":")).encode(), "application/json; charset=utf-8")

    def do_GET(self) -> None:
        parsed = urlparse(self.path); path = parsed.path; qs = parse_qs(parsed.query)
        if path == "/":
            self.send_response(302); self.send_header("Location", f"/admin/sites/{SITE}/devices"); self.end_headers(); return
        if path == "/candidate-admin.js": self.send_bytes(200, ADMIN_JS.read_bytes(), "text/javascript; charset=utf-8"); return
        if path == "/candidate-admin.css": self.send_bytes(200, ADMIN_CSS.read_bytes(), "text/css; charset=utf-8"); return
        if path == f"/admin/sites/{SITE}/devices": self.send_bytes(200, devices_page(False), "text/html; charset=utf-8"); return
        if path == "/demo/status": self.send_bytes(200, devices_page(True), "text/html; charset=utf-8"); return
        prefix = f"/admin/sites/{SITE}/devices/"
        if path.startswith(prefix):
            did = path[len(prefix):]
            if did in DEVICE_IDS: self.send_bytes(200, device_page(did), "text/html; charset=utf-8"); return
        api_list = f"/admin/api/v1/sites/{SITE}/devices"
        if path == api_list:
            mac = qs.get("mac", [None])[0]
            cursor = qs.get("cursor", [None])[0]
            all_items = [device_item(i) for i in range(len(DEVICE_IDS))]
            if mac:
                all_items = [x for x in all_items if x["canonical_mac"] == mac]
                page_items = all_items; next_cursor = None
            elif cursor:
                page_items = all_items[6:]; next_cursor = None
            else:
                page_items = all_items[:6]; next_cursor = "fixture-page-2"
            self.send_json({"result": {"items": page_items}, "page": {"next_cursor": next_cursor}}); return
        api_prefix = api_list + "/"
        if path.startswith(api_prefix):
            suffix = path[len(api_prefix):]
            is_current = suffix.endswith("/current")
            did = suffix[:-8] if is_current else suffix
            if did in DEVICE_IDS:
                idx = DEVICE_IDS.index(did)
                self.send_json(current_result(idx) if is_current else historical_result(idx)); return
        self.send_json({"error": {"code": "not_found"}}, 404)


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--host", default="127.0.0.1"); ap.add_argument("--port", type=int, default=8766); args = ap.parse_args()
    verify_candidate()
    print("TASK-WEB-DEVICE-UI-01 LAB VISUAL PREVIEW")
    print("BASELINE HEAD =", EXPECTED_HEAD)
    print("BASELINE TREE =", EXPECTED_TREE)
    print("PATCHED FILES = admin.css, admin.js")
    print("DIFF CHECK = PASS")
    print()
    print(f"OPEN ACTUAL PATCH: http://{args.host}:{args.port}/admin/sites/{SITE}/devices")
    print(f"OPTIONAL STATUS-LAMP DEMO: http://{args.host}:{args.port}/demo/status")
    print("Stop with Ctrl+C")
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
    return 0

if __name__ == "__main__": raise SystemExit(main())
