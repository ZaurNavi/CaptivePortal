from flask import Flask, Response, jsonify, send_from_directory
from pathlib import Path

CANDIDATE = Path(r"C:\CaptivPortal-Lab\TASK-WEB-ASSET-LIBRARY-01-FIX-ANDROID")
STATIC_DIR = CANDIDATE / "app" / "admin_web" / "static"
SITE_ID = "0123456789abcdef01234567"
ANDROID_DEVICE_ID = "11111111-1111-4111-8111-111111111111"

app = Flask(__name__)

def shell(page, device_id=None):
    controls = ""
    subtitle = ""
    if page == "devices":
        title = "Devices"
        subtitle = "<p>Site membership from authorized snapshots and visits.</p>"
        controls = """
<form id="device-search-form" class="filter-bar" novalidate>
  <label for="device-mac">Exact MAC address</label>
  <input id="device-mac" name="mac" inputmode="text" autocomplete="off"
         placeholder="AA:BB:CC:DD:EE:FF" maxlength="17">
  <button class="button button-secondary" type="submit">Search</button>
  <button id="clear-device-search" class="button button-quiet" type="button">Clear</button>
</form>
"""
    else:
        title = "Device"
        subtitle = "<p>Site-local identity, recent visits and latest safe observation.</p>"

    device_attr = f' data-device-id="{device_id}"' if device_id else ""
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} · CaptivPortal LAB</title>
  <link rel="stylesheet" href="/admin/static/admin.css">
  <script defer src="/admin/static/admin.js"></script>
</head>
<body>
  <header class="topbar">
    <a class="brand" href="/admin/sites/{SITE_ID}/devices">
      <span class="brand-mark" aria-hidden="true">CP</span>
      <span>CaptivPortal LAB</span>
    </a>
    <div class="topbar-context">
      <span class="eyebrow">Current Site</span>
      <strong class="mono">{SITE_ID}</strong>
    </div>
  </header>
  <div class="app-frame">
    <nav class="sidebar" aria-label="Admin navigation">
      <a class="nav-link is-active" href="/admin/sites/{SITE_ID}/devices">Devices</a>
    </nav>
    <main id="main-content" class="content">
      <div class="page-heading">
        <div>
          <p class="eyebrow">Read-only LAB preview</p>
          <h1>{title}</h1>
          {subtitle}
        </div>
        <button id="refresh-button" class="button" type="button">Refresh</button>
      </div>
      <section id="admin-page"
        data-page="{page}"
        data-site-id="{SITE_ID}"
        data-api-base="/admin/api/v1/sites/{SITE_ID}"{device_attr}
        data-runtime-state="active">
        {controls}
        <div id="page-state" class="state-panel" role="status" aria-live="polite">
          <span class="state-dot" aria-hidden="true"></span>
          <div>
            <strong id="state-title">Loading</strong>
            <p id="state-message">Requesting current Site data…</p>
          </div>
        </div>
        <div id="page-content" class="content-grid" aria-live="polite"></div>
        <div id="pagination" class="pagination" hidden>
          <button id="load-more-button" class="button button-secondary" type="button">Load more</button>
        </div>
      </section>
    </main>
  </div>
</body>
</html>"""
    return Response(html, mimetype="text/html")

@app.get("/admin/static/<path:filename>")
def static_file(filename):
    return send_from_directory(STATIC_DIR, filename)

@app.get("/admin/sites/<site_id>/devices")
def devices_page(site_id):
    return shell("devices")

@app.get("/admin/sites/<site_id>/devices/<device_id>")
def device_page(site_id, device_id):
    return shell("device", device_id=device_id)

@app.get("/admin/api/v1/sites/<site_id>/devices")
def devices_api(site_id):
    return jsonify({
        "result": {
            "items": [
                {
                    "device_id": ANDROID_DEVICE_ID,
                    "canonical_mac": "7E:F5:3E:79:38:5E",
                    "hostname": "android-12d4ade551720f0f",
                    "device_type": "android",
                    "site_last_seen_at": "2026-09-12T07:09:59.704Z",
                    "last_site_ssid": "Zefer_Parki",
                    "site_visit_count": 1,
                    "site_snapshot_count": 13,
                    "current_presence": "offline"
                },
                {
                    "device_id": "22222222-2222-4222-8222-222222222222",
                    "canonical_mac": "AA:BB:CC:DD:EE:FF",
                    "hostname": "non-android-fixture",
                    "device_type": "unknown",
                    "site_last_seen_at": "2026-09-12T07:10:00.000Z",
                    "last_site_ssid": "Zefer_Parki",
                    "site_visit_count": 2,
                    "site_snapshot_count": 2,
                    "current_presence": "online"
                }
            ]
        },
        "page": {"next_cursor": None}
    })

@app.get("/admin/api/v1/sites/<site_id>/devices/<device_id>")
def device_api(site_id, device_id):
    return jsonify({
        "result": {
            "identity": {
                "canonical_mac": "7E:F5:3E:79:38:5E",
                "device_type": "android",
                "site_first_seen_at": "2026-09-01T10:00:00.000Z",
                "site_last_seen_at": "2026-09-12T07:09:59.704Z",
                "site_snapshot_count": 13,
                "site_visit_count": 1
            },
            "latest_snapshot": {
                "captured_at": "2026-09-12T07:09:59.704Z",
                "hostname": "android-12d4ade551720f0f",
                "device_type": "Android",
                "ssid": "Zefer_Parki",
                "active": False
            },
            "latest_client_observation": {
                "observed_at": "2026-09-12T07:09:59.704Z",
                "device_type": "ANDROID",
                "ssid": "Zefer_Parki"
            },
            "recent_visits": []
        }
    })

if __name__ == "__main__":
    print("Candidate static dir:", STATIC_DIR)
    print("Devices:", f"http://127.0.0.1:8099/admin/sites/{SITE_ID}/devices")
    print("Detail :", f"http://127.0.0.1:8099/admin/sites/{SITE_ID}/devices/{ANDROID_DEVICE_ID}")
    app.run(host="127.0.0.1", port=8099, debug=False, use_reloader=False)
