from pathlib import Path
import sys

from flask import Blueprint, Flask, jsonify, render_template, request, send_from_directory


REPO = Path(r"C:\CaptivPortal-UI-Preview")
SITE_ID = "000000000000000000000001"

CLIENT_CYCLE = "10000000-0000-4000-8000-000000000001"
AP_CYCLE = "20000000-0000-4000-8000-000000000001"
TRAFFIC_CYCLE = "30000000-0000-4000-8000-000000000001"

CLIENT_SCOPE_HASH = "a" * 64
AP_SCOPE_HASH = "b" * 64

OBSERVED_AT = "2026-08-26T06:00:00.000Z"


sys.path.insert(0, str(REPO))

from app.admin_web.pages import HOME  # noqa: E402


app = Flask(
    __name__,
    template_folder=str(REPO / "app" / "admin_web" / "templates"),
)


admin_static = Blueprint("admin_web_v1", __name__)


@admin_static.get("/admin/static/<path:filename>", endpoint="static")
def static_file(filename):
    return send_from_directory(
        REPO / "app" / "admin_web" / "static",
        filename,
    )


app.register_blueprint(admin_static)


def client_scope():
    return {
        "scope_type": "client_ssid_allowlist",
        "site_id": SITE_ID,
        "ssids": ["Zefer_Parki"],
    }


def ap_scope():
    return {
        "scope_type": "site_ap_inventory",
        "site_id": SITE_ID,
    }


def client_snapshot():
    return {
        "kind": "client",
        "cycle_id": CLIENT_CYCLE,
        "observed_at": OBSERVED_AT,
        "age_seconds": 5,
        "freshness_status": "fresh",
        "complete": True,
        "source_scope_hash": CLIENT_SCOPE_HASH,
        "source_scope": client_scope(),
        "latest_attempt_result": "success",
    }


def ap_snapshot():
    return {
        "kind": "ap",
        "cycle_id": AP_CYCLE,
        "observed_at": OBSERVED_AT,
        "age_seconds": 7,
        "freshness_status": "fresh",
        "complete": True,
        "source_scope_hash": AP_SCOPE_HASH,
        "source_scope": ap_scope(),
        "latest_attempt_result": "success",
    }


def traffic_snapshot():
    return {
        "source_kind": "observation_ap_dynamic",
        "cycle_id": TRAFFIC_CYCLE,
        "complete": True,
        "evaluated_at": "2026-08-26T06:00:20.000Z",
        "observed_at": "2026-08-26T06:00:02.000Z",
        "newest_observed_at": "2026-08-26T06:00:15.000Z",
        "age_seconds": 18,
        "source_skew_seconds": 13,
        "freshness_status": "fresh",
        "freshness_reason": "within_freshness_window",
        "latest_attempt_state": "completed",
        "latest_attempt_result": "success",
        "latest_attempt_at": "2026-08-26T06:00:17.000Z",
        "using_previous_complete_snapshot": False,
        "selected_source": "wired",
        "selection_reason": "primary_full_coverage",
        "empty_population": False,
    }


CLIENTS = [
    {
        "client_mac": "AA:BB:CC:DD:EE:01",
        "name": "Moto G85",
        "hostname": "moto-g85",
        "ip": "192.168.10.101",
        "ssid": "Zefer_Parki",
        "ap_name": "Park AP 1",
        "ap_mac": "11:22:33:44:55:01",
        "band": "5 GHz",
        "rssi": -55,
        "snr": 35,
        "controller_uptime": 4200,
        "controller_traffic_down": 157286400,
        "controller_traffic_up": 31457280,
        "controller_traffic_total": 188743680,
        "auth_classification": "authorized",
    },
    {
        "client_mac": "AA:BB:CC:DD:EE:02",
        "name": "iPhone",
        "hostname": "iphone",
        "ip": "192.168.10.102",
        "ssid": "Zefer_Parki",
        "ap_name": "Park AP 1",
        "ap_mac": "11:22:33:44:55:01",
        "band": "5 GHz",
        "rssi": -61,
        "snr": 29,
        "controller_uptime": 3300,
        "controller_traffic_down": 94371840,
        "controller_traffic_up": 18874368,
        "controller_traffic_total": 113246208,
        "auth_classification": "authorized",
    },
    {
        "client_mac": "AA:BB:CC:DD:EE:03",
        "name": "Samsung A55",
        "hostname": "galaxy-a55",
        "ip": "192.168.10.103",
        "ssid": "Zefer_Parki",
        "ap_name": "Park AP 1",
        "ap_mac": "11:22:33:44:55:01",
        "band": "2.4 GHz",
        "rssi": -69,
        "snr": 22,
        "controller_uptime": 1600,
        "controller_traffic_down": 52428800,
        "controller_traffic_up": 10485760,
        "controller_traffic_total": 62914560,
        "auth_classification": "pending",
    },
    {
        "client_mac": "AA:BB:CC:DD:EE:04",
        "name": "Redmi Note",
        "hostname": "redmi-note",
        "ip": "192.168.10.104",
        "ssid": "Zefer_Parki",
        "ap_name": "Park AP 1",
        "ap_mac": "11:22:33:44:55:01",
        "band": "5 GHz",
        "rssi": -64,
        "snr": 27,
        "controller_uptime": 2800,
        "controller_traffic_down": 73400320,
        "controller_traffic_up": 12582912,
        "controller_traffic_total": 85983232,
        "auth_classification": "authorized",
    },
    {
        "client_mac": "AA:BB:CC:DD:EE:05",
        "name": "Pixel 9",
        "hostname": "pixel-9",
        "ip": "192.168.10.105",
        "ssid": "Zefer_Parki",
        "ap_name": "Park AP 2",
        "ap_mac": "11:22:33:44:55:02",
        "band": "5 GHz",
        "rssi": -49,
        "snr": 41,
        "controller_uptime": 5100,
        "controller_traffic_down": 209715200,
        "controller_traffic_up": 41943040,
        "controller_traffic_total": 251658240,
        "auth_classification": "authorized",
    },
    {
        "client_mac": "AA:BB:CC:DD:EE:06",
        "name": "Galaxy S24",
        "hostname": "galaxy-s24",
        "ip": "192.168.10.106",
        "ssid": "Zefer_Parki",
        "ap_name": "Park AP 2",
        "ap_mac": "11:22:33:44:55:02",
        "band": "5 GHz",
        "rssi": -58,
        "snr": 33,
        "controller_uptime": 2500,
        "controller_traffic_down": 125829120,
        "controller_traffic_up": 25165824,
        "controller_traffic_total": 150994944,
        "auth_classification": "authorized",
    },
    {
        "client_mac": "AA:BB:CC:DD:EE:07",
        "name": "Honor",
        "hostname": "honor",
        "ip": "192.168.10.107",
        "ssid": "Zefer_Parki",
        "ap_name": "Park AP 2",
        "ap_mac": "11:22:33:44:55:02",
        "band": "2.4 GHz",
        "rssi": -72,
        "snr": 18,
        "controller_uptime": 900,
        "controller_traffic_down": 20971520,
        "controller_traffic_up": 5242880,
        "controller_traffic_total": 26214400,
        "auth_classification": "pending",
    },
    {
        "client_mac": "AA:BB:CC:DD:EE:08",
        "name": None,
        "hostname": None,
        "ip": "192.168.10.108",
        "ssid": "Zefer_Parki",
        "ap_name": None,
        "ap_mac": None,
        "band": None,
        "rssi": None,
        "snr": None,
        "controller_uptime": 120,
        "controller_traffic_down": 0,
        "controller_traffic_up": 0,
        "controller_traffic_total": 0,
        "auth_classification": "other",
    },
]


APS = [
    {
        "ap_mac": "11:22:33:44:55:01",
        "name": "Park AP 1",
        "product_status_classification": "Online",
    },
    {
        "ap_mac": "11:22:33:44:55:02",
        "name": "Park AP 2",
        "product_status_classification": "Online",
    },
]


def envelope(result):
    return {
        "api_version": "admin.read.v1",
        "site_id": SITE_ID,
        "result": result,
    }


@app.get("/")
@app.get("/admin/sites/<site_id>/")
def home(site_id=SITE_ID):
    return render_template(
        "admin/home.html",
        page=HOME,
        site_id=SITE_ID,
        username="UI Preview",
        csrf_token="preview",
        runtime_state="active",
        home_live_enabled=True,
        home_live_refresh_seconds=60,
        home_live_request_timeout_seconds=20,
        current_state_page_size=100,
        home_traffic_enabled=True,
        home_traffic_refresh_seconds=60,
        home_traffic_request_timeout_seconds=20,
        home_traffic_page_size=100,
    )


@app.get(
    "/admin/api/v1/sites/<site_id>/current-state/clients/summary"
)
def current_clients_summary(site_id):
    return jsonify(
        envelope(
            {
                "snapshot": client_snapshot(),
                "freshness_policy": {
                    "fresh_max_age_seconds": 60,
                    "unavailable_after_seconds": 180,
                },
                "counts": {
                    "online": 8,
                    "authorized": 5,
                    "pending": 2,
                    "other": 1,
                    "unknown": 0,
                    "other_unknown": 1,
                    "ap_unknown": 1,
                },
                "devices_by_ap": [
                    {
                        "ap_mac": "11:22:33:44:55:01",
                        "client_count": 4,
                    },
                    {
                        "ap_mac": "11:22:33:44:55:02",
                        "client_count": 3,
                    },
                ],
            }
        )
    )


@app.get(
    "/admin/api/v1/sites/<site_id>/current-state/clients"
)
def current_clients(site_id):
    limit = int(request.args.get("limit", "100"))

    return jsonify(
        {
            **envelope(
                {
                    "snapshot": client_snapshot(),
                    "items": CLIENTS,
                }
            ),
            "page": {
                "limit": limit,
                "cycle_id": CLIENT_CYCLE,
                "source_scope_hash": CLIENT_SCOPE_HASH,
                "next_cursor": None,
            },
        }
    )


@app.get(
    "/admin/api/v1/sites/<site_id>/current-state/aps/summary"
)
def current_aps_summary(site_id):
    return jsonify(
        envelope(
            {
                "snapshot": ap_snapshot(),
                "freshness_policy": {
                    "fresh_max_age_seconds": 90,
                    "unavailable_after_seconds": 300,
                },
                "counts": {
                    "total": 2,
                    "online": 2,
                    "other": 0,
                    "unknown": 0,
                },
            }
        )
    )


@app.get(
    "/admin/api/v1/sites/<site_id>/current-state/aps"
)
def current_aps(site_id):
    limit = int(request.args.get("limit", "100"))

    return jsonify(
        {
            **envelope(
                {
                    "snapshot": ap_snapshot(),
                    "items": APS,
                }
            ),
            "page": {
                "limit": limit,
                "cycle_id": AP_CYCLE,
                "source_scope_hash": AP_SCOPE_HASH,
                "next_cursor": None,
            },
        }
    )


@app.get(
    "/admin/api/v1/sites/<site_id>/current-traffic/summary"
)
def current_traffic_summary(site_id):
    return jsonify(
        envelope(
            {
                "snapshot": traffic_snapshot(),
                "freshness_policy": {
                    "fresh_max_age_seconds": 90,
                    "unavailable_after_seconds": 180,
                    "max_ap_skew_seconds": 60,
                },
                "traffic": {
                    "download_mbps": 42.125,
                    "upload_mbps": 6.25,
                    "total_mbps": 48.375,
                    "unit": "Mbps",
                },
                "source_selection": {
                    "primary_source": "wired",
                    "selected_source": "wired",
                    "selection_reason": "primary_full_coverage",
                    "wired_pair_valid_ap_count": 2,
                    "lan_pair_valid_ap_count": 2,
                    "source_mixing_allowed": False,
                },
                "coverage": {
                    "coverage_status": "complete",
                    "empty_population": False,
                    "total_ap_count": 2,
                    "valid_rate_ap_count": 2,
                    "valid_download_ap_count": 2,
                    "valid_upload_ap_count": 2,
                    "missing_rate_ap_count": 0,
                    "stale_ap_count": 0,
                    "unavailable_ap_count": 0,
                    "reset_ap_count": 0,
                    "gap_rejected_ap_count": 0,
                    "no_baseline_ap_count": 0,
                    "source_unavailable_ap_count": 0,
                    "invalid_elapsed_ap_count": 0,
                    "coverage_reasons": [],
                },
            }
        )
    )


@app.get(
    "/admin/api/v1/sites/<site_id>/current-traffic/aps"
)
def current_traffic_aps(site_id):
    limit = int(request.args.get("limit", "100"))

    result = {
        "snapshot": {
            "source_kind": "observation_ap_dynamic",
            "cycle_id": TRAFFIC_CYCLE,
            "evaluated_at": "2026-08-26T06:00:20.000Z",
            "observed_at": "2026-08-26T06:00:02.000Z",
            "newest_observed_at": "2026-08-26T06:00:15.000Z",
            "age_seconds": 18,
            "freshness_status": "fresh",
            "freshness_reason": "within_freshness_window",
        },
        "freshness_policy": {
            "fresh_max_age_seconds": 90,
            "unavailable_after_seconds": 180,
        },
        "source_selection": {
            "selected_source": "wired",
            "selection_reason": "primary_full_coverage",
            "source_mixing_allowed": False,
        },
        "items": [
            {
                "ap_mac": "11:22:33:44:55:01",
                "name": "Park AP 1",
                "download_mbps": 25.50,
                "upload_mbps": 3.75,
                "total_mbps": 29.25,
                "download_reason": "ok",
                "upload_reason": "ok",
                "rate_status": "valid",
                "observed_at": "2026-08-26T06:00:02.000Z",
                "age_seconds": 18,
                "selected_source": "wired",
            },
            {
                "ap_mac": "11:22:33:44:55:02",
                "name": "Park AP 2",
                "download_mbps": 16.625,
                "upload_mbps": 2.50,
                "total_mbps": 19.125,
                "download_reason": "ok",
                "upload_reason": "ok",
                "rate_status": "valid",
                "observed_at": "2026-08-26T06:00:15.000Z",
                "age_seconds": 5,
                "selected_source": "wired",
            },
        ],
    }

    return jsonify(
        {
            **envelope(result),
            "page": {
                "limit": limit,
                "next_cursor": None,
                "cycle_id": TRAFFIC_CYCLE,
                "selected_source": "wired",
            },
        }
    )


if __name__ == "__main__":
    print()
    print("CaptivPortal Admin UI Preview")
    print("Repository:", REPO)
    print("Open: http://127.0.0.1:5055/")
    print()

    app.run(
        host="127.0.0.1",
        port=5055,
        debug=False,
        use_reloader=False,
    )
