#!/usr/bin/env python3
"""
TASK-DEVICE-CARD-01 controlled browser fixture.

This file is intentionally OUTSIDE the CaptivPortal repository.
It serves the exact candidate admin.js/admin.css from C:\CaptivPortal-UI-Preview
and synthetic read-only Admin API responses for browser acceptance.

It refuses to start unless the immutable LAB candidate identity is exact and
the repository worktree is clean.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(r"C:\CaptivPortal-UI-Preview")
EXPECTED_HEAD = "e940a4df2b3fc66db9c81a383e353205304e149b"
EXPECTED_TREE = "8f1342f0a0f1e8242642161e02b2f3276e6ddf51"
EXPECTED_PARENT = "3eac6f13d5f3966574f6d1b0a10f531d988f91ec"

SITE = "0123456789abcdef01234567"
DEVICE = "10000000-0000-4000-8000-000000000001"
MAC = "02:00:00:00:00:01"
NOW = "2026-09-09T06:00:00.000Z"

ADMIN_JS = REPO / "app" / "admin_web" / "static" / "admin.js"
ADMIN_CSS = REPO / "app" / "admin_web" / "static" / "admin.css"

SCENARIOS = {
    "online": "Online + Authorized + valid Current Guest Traffic",
    "pending": "Online + Pending; Traffic not applicable; no fabricated zero",
    "offline": "Fresh complete scope; Device absent => Offline",
    "stale": "Stale Current State => Unknown, never false Offline",
    "invalid-timestamp": "Unavailable invalid timestamp => sanitized semantic Unknown",
    "current-503": "Current endpoint 503; historical Device Card must remain",
    "traffic-failure": "Current State remains; Traffic technical failure is panel-local",
    "zero": "Authorized valid 0.0 Mbps evidence remains numeric zero",
    "slow": "Slow Current response for refresh/no-overlap observation",
}

COUNTS = {"history": 0, "current": 0}


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(REPO), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    return completed.stdout.strip()


def verify_candidate() -> None:
    head = _git("rev-parse", "HEAD")
    tree = _git("show", "-s", "--format=%T", "HEAD")
    parent = _git("rev-parse", "HEAD~1")
    dirty = _git("status", "--porcelain")
    if head != EXPECTED_HEAD:
        raise RuntimeError(f"Unexpected candidate HEAD: {head}")
    if tree != EXPECTED_TREE:
        raise RuntimeError(f"Unexpected candidate tree: {tree}")
    if parent != EXPECTED_PARENT:
        raise RuntimeError(f"Unexpected candidate parent: {parent}")
    if dirty:
        raise RuntimeError("Candidate worktree is dirty; browser fixture refused.")
    if not ADMIN_JS.is_file() or not ADMIN_CSS.is_file():
        raise RuntimeError("Candidate Admin static files are missing.")


def historical_result() -> dict:
    return {
        "result": {
            "identity": {
                "canonical_mac": MAC,
                "device_type": "phone",
                "site_first_seen_at": "2026-09-01T08:00:00.000Z",
                "site_last_seen_at": "2026-09-09T05:59:00.000Z",
                "site_snapshot_count": 12,
                "site_visit_count": 4,
            },
            "latest_snapshot": {
                "active": True,
                "auth_status": "historical-only",
                "observed_at": "2026-09-08T17:00:00.000Z",
            },
            "latest_client_observation": {
                "observed_at": "2026-09-08T17:05:00.000Z",
                "ssid": "Zefer_Parki",
                "ap_mac": "AA:BB:CC:DD:EE:FF",
                "rssi": -61,
            },
            "recent_visits": [
                {
                    "status": "closed",
                    "client_mac": MAC,
                    "started_at": "2026-09-08T16:00:00.000Z",
                    "closed_at": "2026-09-08T17:00:00.000Z",
                    "duration_seconds": 3600,
                    "start_ssid": "Zefer_Parki",
                    "final_ssid": "Zefer_Parki",
                    "start_ap_mac": "AA:BB:CC:DD:EE:FF",
                    "final_ap_mac": "AA:BB:CC:DD:EE:FF",
                    "reported_traffic_total_bytes": 123456,
                }
            ],
        }
    }


def snapshot(*, status="fresh", reason="within_freshness_window",
             observed=NOW, finished=NOW, age=0, complete=True, cycle="cycle-a") -> dict:
    return {
        "cycle_id": cycle,
        "observed_at": observed,
        "capture_finished_at": finished,
        "age_seconds": age,
        "freshness_status": status,
        "freshness_reason": reason,
        "complete": complete,
    }


def client(auth="authorized") -> dict:
    return {
        "client_mac": MAC,
        "name": "Fixture Phone",
        "hostname": "fixture-phone",
        "device_type": "phone",
        "ip": "192.168.10.50",
        "ssid": "Zefer_Parki",
        "ap_name": "EAP613-1",
        "ap_mac": "AA:BB:CC:DD:EE:FF",
        "radio_id": 1,
        "band": "5GHz",
        "channel": 44,
        "rssi": -52,
        "snr": 31,
        "controller_uptime": 1800,
        "controller_traffic_down_bytes": 123456,
        "controller_traffic_up_bytes": 4567,
        "controller_traffic_total_bytes": 128023,
        "active": True,
        "wireless": True,
    }


def traffic_applicable(*, down=1.25, up=0.10, total=1.35) -> dict:
    return {
        "applicability": "applicable",
        "applicability_reason": "authorized_current_guest",
        "source_health_status": "healthy",
        "source_health_reason": "within_freshness_window",
        "rate_evidence_status": "complete",
        "current_cycle_id": "cycle-a",
        "baseline_cycle_id": "cycle-b",
        "elapsed_seconds": 60,
        "item": {
            "download_mbps": down,
            "upload_mbps": up,
            "total_mbps": total,
            "rate_status": "valid",
            "source_progress_status": "advanced",
            "connection_continuity_status": "proven",
            "continuity_basis": "uptime_progress",
            "download_reason": "valid",
            "upload_reason": "valid",
            "total_reason": "valid",
        },
        "failure_reason": None,
    }


def traffic_non_applicable(reason: str) -> dict:
    return {
        "applicability": "not_applicable",
        "applicability_reason": reason,
        "source_health_status": None,
        "source_health_reason": None,
        "rate_evidence_status": "not_applicable",
        "current_cycle_id": "cycle-a",
        "baseline_cycle_id": None,
        "elapsed_seconds": None,
        "item": None,
        "failure_reason": None,
    }


def traffic_unknown() -> dict:
    return {
        "applicability": "unknown",
        "applicability_reason": "current_state_unknown",
        "source_health_status": None,
        "source_health_reason": None,
        "rate_evidence_status": "not_applicable",
        "current_cycle_id": "cycle-a",
        "baseline_cycle_id": None,
        "elapsed_seconds": None,
        "item": None,
        "failure_reason": None,
    }


def current_result(scenario: str) -> tuple[int, dict]:
    base = {
        "contract_version": "admin.device.current.v1",
        "site_id": SITE,
        "device_id": DEVICE,
        "evaluated_at_utc": NOW,
        "scope": {
            "scope_type": "client_ssid_allowlist",
            "site_id": SITE,
            "ssids": ["Zefer_Parki"],
        },
    }

    if scenario == "current-503":
        return 503, {"error": {"code": "source_unavailable"}}

    if scenario in {"online", "slow"}:
        base["current_state"] = {
            "presence_status": "online",
            "presence_reason": "present_in_fresh_complete_scope",
            "snapshot": snapshot(),
            "authorization": {"classification": "authorized", "reason": "current_row"},
            "client": client("authorized"),
        }
        base["current_guest_traffic"] = traffic_applicable()
        return 200, {"result": base}

    if scenario == "zero":
        base["current_state"] = {
            "presence_status": "online",
            "presence_reason": "present_in_fresh_complete_scope",
            "snapshot": snapshot(),
            "authorization": {"classification": "authorized", "reason": "current_row"},
            "client": client("authorized"),
        }
        base["current_guest_traffic"] = traffic_applicable(down=0.0, up=0.0, total=0.0)
        return 200, {"result": base}

    if scenario == "pending":
        base["current_state"] = {
            "presence_status": "online",
            "presence_reason": "present_in_fresh_complete_scope",
            "snapshot": snapshot(),
            "authorization": {"classification": "pending", "reason": "current_row"},
            "client": client("pending"),
        }
        base["current_guest_traffic"] = traffic_non_applicable("not_authorized_current_guest")
        return 200, {"result": base}

    if scenario == "offline":
        base["current_state"] = {
            "presence_status": "offline",
            "presence_reason": "absent_from_fresh_complete_scope",
            "snapshot": snapshot(),
            "authorization": {"classification": "unknown", "reason": "offline"},
            "client": None,
        }
        base["current_guest_traffic"] = traffic_non_applicable("offline")
        return 200, {"result": base}

    if scenario == "stale":
        base["current_state"] = {
            "presence_status": "unknown",
            "presence_reason": "current_state_unknown",
            "snapshot": snapshot(
                status="stale",
                reason="older_than_freshness_window",
                observed="2026-09-09T05:57:00.000Z",
                finished="2026-09-09T05:57:00.000Z",
                age=180,
            ),
            "authorization": {"classification": "unknown", "reason": "current_state_unknown"},
            "client": None,
        }
        base["current_guest_traffic"] = traffic_unknown()
        return 200, {"result": base}

    if scenario == "invalid-timestamp":
        base["current_state"] = {
            "presence_status": "unknown",
            "presence_reason": "current_state_unknown",
            "snapshot": snapshot(
                status="unavailable",
                reason="invalid_timestamp",
                observed=None,
                finished=None,
                age=None,
            ),
            "authorization": {"classification": "unknown", "reason": "current_state_unknown"},
            "client": None,
        }
        base["current_guest_traffic"] = traffic_unknown()
        return 200, {"result": base}

    if scenario == "traffic-failure":
        base["current_state"] = {
            "presence_status": "online",
            "presence_reason": "present_in_fresh_complete_scope",
            "snapshot": snapshot(),
            "authorization": {"classification": "authorized", "reason": "current_row"},
            "client": client("authorized"),
        }
        base["current_guest_traffic"] = {
            "applicability": "applicable",
            "applicability_reason": "authorized_current_guest",
            "source_health_status": None,
            "source_health_reason": None,
            "rate_evidence_status": None,
            "current_cycle_id": "cycle-a",
            "baseline_cycle_id": None,
            "elapsed_seconds": None,
            "item": None,
            "failure_reason": "source_unavailable",
        }
        return 200, {"result": base}

    return current_result("online")


def scenario_from_cookie(header: str | None) -> str:
    if not header:
        return "online"
    cookie = SimpleCookie()
    try:
        cookie.load(header)
    except Exception:
        return "online"
    morsel = cookie.get("dc_scenario")
    value = morsel.value if morsel else "online"
    return value if value in SCENARIOS else "online"


def page_html(scenario: str) -> bytes:
    links = " ".join(
        f'<a class="scenario{" active" if name == scenario else ""}" href="/fixture/{name}">{name}</a>'
        for name in SCENARIOS
    )
    description = SCENARIOS[scenario]
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>DEVICE-CARD-01 Browser Fixture — {scenario}</title>
<link rel="stylesheet" href="/candidate-admin.css">
<style>
body {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
.fixture {{ border: 2px solid #777; border-radius: 10px; padding: 14px; margin-bottom: 18px; }}
.fixture code {{ user-select: all; }}
.scenario {{ display:inline-block; margin:4px; padding:6px 9px; border:1px solid #999; border-radius:6px; text-decoration:none; }}
.scenario.active {{ font-weight:700; outline:2px solid currentColor; }}
.fixture-note {{ margin-top:8px; }}
</style>
</head>
<body>
<section class="fixture">
  <strong>Controlled fixture — exact candidate admin.js</strong>
  <div>Candidate HEAD: <code>{EXPECTED_HEAD}</code></div>
  <div>Candidate TREE: <code>{EXPECTED_TREE}</code></div>
  <div>Scenario: <strong>{scenario}</strong> — {description}</div>
  <div>{links}</div>
  <div class="fixture-note">Watch the fixture CMD window: it prints HISTORY/CURRENT request counters.</div>
  <h3>Fixture diagnostics</h3>
  <pre id="fixture-debug">instrumentation starting…</pre>
</section>

<div id="admin-page"
     data-page="device"
     data-site-id="{SITE}"
     data-api-base="/admin/api/v1/sites/{SITE}"
     data-device-id="{DEVICE}">
  <div class="section-heading">
    <h1>Device Card — Controlled Acceptance</h1>
    <button id="refresh-button" type="button">Refresh</button>
  </div>

  <div id="page-state" class="state-panel">
    <strong id="state-title">Loading</strong>
    <p id="state-message">Loading historical Device context…</p>
  </div>

  <main id="page-content" class="content-grid"></main>

  <section id="device-current-context" class="section-card">
    <div class="section-heading">
      <div>
        <h2>Current Device Context</h2>
        <p>Current managed Site/SSID evidence, independent from historical device context.</p>
      </div>
    </div>
    <div id="device-current-state" class="state-panel" role="status" aria-live="polite">
      <span class="state-dot" aria-hidden="true"></span>
      <div>
        <strong id="device-current-state-title">Loading</strong>
        <p id="device-current-state-message">Requesting current device evidence…</p>
      </div>
    </div>
    <div id="device-current-content" class="content-grid" aria-live="polite"></div>
  </section>

  <div id="pagination" hidden>
    <button id="load-more-button" type="button">Load more</button>
  </div>
</div>

<script>
(function () {
  "use strict";
  const events = [];
  const originalFetch = window.fetch.bind(window);

  function text(id) {
    const el = document.getElementById(id);
    return el ? el.textContent : "<missing>";
  }

  function headings(selector) {
    return Array.from(document.querySelectorAll(selector))
      .map((el) => el.textContent)
      .join(" | ") || "<none>";
  }

  function render(label) {
    const target = document.getElementById("fixture-debug");
    if (!target) return;
    target.textContent = [
      "PROBE=" + label,
      "document.readyState=" + document.readyState,
      "CaptivPortalAdminTest=" + typeof window.CaptivPortalAdminTest,
      "",
      "HISTORICAL title=" + text("state-title"),
      "HISTORICAL message=" + text("state-message"),
      "HISTORICAL cards=" + headings("#page-content h2"),
      "HISTORICAL children=" + (document.getElementById("page-content")?.children.length ?? -1),
      "",
      "CURRENT title=" + text("device-current-state-title"),
      "CURRENT message=" + text("device-current-state-message"),
      "CURRENT cards=" + headings("#device-current-content h2"),
      "CURRENT children=" + (document.getElementById("device-current-content")?.children.length ?? -1),
      "",
      "FETCH EVENTS:",
      ...(events.length ? events : ["<none>"]),
    ].join("\n");
  }

  window.fetch = async function (...args) {
    const url = String(args[0]);
    events.push("START " + url);
    render("fetch-start");
    try {
      const response = await originalFetch(...args);
      events.push("RESOLVED HTTP " + response.status + " " + url);
      render("fetch-resolved");
      return response;
    } catch (error) {
      events.push("REJECTED " + (error && error.name ? error.name : String(error)) + " " + url);
      render("fetch-rejected");
      throw error;
    }
  };

  window.__deviceCardFixtureRenderDebug = render;
  window.addEventListener("error", (event) => {
    events.push("WINDOW ERROR " + (event.message || "<no message>"));
    render("window-error");
  });
  window.addEventListener("unhandledrejection", (event) => {
    const reason = event.reason;
    events.push("UNHANDLED REJECTION " + (
      reason && reason.message ? reason.message : JSON.stringify(reason)
    ));
    render("unhandled-rejection");
  });

  render("before-candidate");
}());
</script>
<script src="/candidate-admin.js"></script>
<script>
(function () {
  const render = window.__deviceCardFixtureRenderDebug;
  if (!render) return;
  [100, 500, 1500, 4000].forEach((ms) => {
    window.setTimeout(() => render("after-" + ms + "ms"), ms);
  });
}());
</script>
</body>
</html>""".encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "DeviceCard01Fixture/1.0"

    def log_message(self, fmt: str, *args) -> None:
        # Keep output focused on evidence counters.
        return

    def _send(self, status: int, body: bytes, content_type: str, *, cookie: str | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, value: dict) -> None:
        body = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            self.send_response(302)
            self.send_header("Location", "/fixture/online")
            self.end_headers()
            return

        if path.startswith("/fixture/"):
            scenario = path.rsplit("/", 1)[-1]
            if scenario not in SCENARIOS:
                scenario = "online"
            self._send(
                200,
                page_html(scenario),
                "text/html; charset=utf-8",
                cookie=f"dc_scenario={scenario}; Path=/; SameSite=Lax",
            )
            return

        if path == "/candidate-admin.js":
            self._send(200, ADMIN_JS.read_bytes(), "text/javascript; charset=utf-8")
            return

        if path == "/candidate-admin.css":
            self._send(200, ADMIN_CSS.read_bytes(), "text/css; charset=utf-8")
            return

        base = f"/admin/api/v1/sites/{SITE}/devices/{DEVICE}"

        if path == base:
            COUNTS["history"] += 1
            print(f"HISTORY #{COUNTS['history']}  path={path}", flush=True)
            self._json(200, historical_result())
            return

        if path == base + "/current":
            scenario = scenario_from_cookie(self.headers.get("Cookie"))
            COUNTS["current"] += 1
            print(f"CURRENT #{COUNTS['current']}  scenario={scenario}  path={path}", flush=True)
            if scenario == "slow":
                time.sleep(3.0)
            status, payload = current_result(scenario)
            self._json(status, payload)
            return

        if path == "/fixture-stats":
            self._json(200, {"result": dict(COUNTS)})
            return

        self._json(404, {"error": {"code": "not_found"}})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    verify_candidate()

    print("DEVICE-CARD-01 CONTROLLED BROWSER FIXTURE", flush=True)
    print(f"HEAD   = {EXPECTED_HEAD}", flush=True)
    print(f"TREE   = {EXPECTED_TREE}", flush=True)
    print(f"PARENT = {EXPECTED_PARENT}", flush=True)
    print("WORKTREE = CLEAN", flush=True)
    print("", flush=True)
    print(f"OPEN: http://{args.host}:{args.port}/fixture/online", flush=True)
    print("Stop with Ctrl+C.", flush=True)
    print("", flush=True)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    print("Fixture stopped.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
