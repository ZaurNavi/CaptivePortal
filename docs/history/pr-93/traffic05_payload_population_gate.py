from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

REPO = Path(r"C:\CaptivPortal-UI-Preview")
EXPECTED_HEAD = "c997e53876bc70cc57e16d6082cc79a1161b5217"
EXPECTED_TREE = "a80e90f7a00e934e853a90516781a5882620d072"
PAYLOAD_LIMIT = 786_432
MAX_RESPONSE_BYTES = 1_048_576

os.chdir(REPO)
sys.path.insert(0, str(REPO))

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from app.admin_web import create_admin_web_runtime
from app.analytics import HistoricalTrafficApPopulation
from tests.admin_web.conftest import SITE_ID, enabled_settings, login
from tests.admin_web.test_traffic_ap import OneApCurrentSource, _product
from tests.admin_web.test_traffic_history import _result
from tests.admin_web.test_traffic_peak import _peak_result


def fail(message: str) -> None:
    raise SystemExit("FAIL: " + message)


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(REPO), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        fail("git failed: " + " ".join(args) + "\n" + completed.stdout + completed.stderr)
    return completed.stdout.strip()


def supported_product(base):
    template_product = _product(base=base)
    template_item = template_product.items[0]
    items = []
    for index in range(12):
        mac = f"02:00:00:00:00:{index:02X}"
        prefix = f"AP-{index + 1:02d}-"
        name = prefix + ("X" * (256 - len(prefix)))
        items.append(
            replace(
                template_item,
                ap_mac=mac,
                display_name=name,
                display_name_source="current",
            )
        )
    return replace(
        template_product,
        population=HistoricalTrafficApPopulation(12, 12, 12, 12, 12, True),
        items=tuple(items),
    )


class GateHistorySource:
    def __init__(self, population: int):
        self.population = population
        self.calls = []

    def get_site_history(self, site_id, **kwargs):
        self.calls.append((site_id, kwargs))
        start = datetime.fromisoformat(kwargs["from_utc"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(kwargs["to_utc"].replace("Z", "+00:00"))
        evaluated = datetime.fromisoformat(
            kwargs["evaluated_at_utc"].replace("Z", "+00:00")
        )
        range_id = "7d" if end - start == timedelta(days=7) else "24h"
        base = _peak_result(_result(range_id, evaluated=evaluated))
        if not kwargs.get("include_peak_load"):
            base = replace(base, peak_load=None)
        if not kwargs.get("include_period_statistics"):
            base = replace(base, period_statistics=None)
        if kwargs.get("include_ap_traffic"):
            if self.population == 13:
                product = _product(unsupported=True, base=base)
            elif self.population == 12:
                product = supported_product(base)
            else:
                fail(f"unsupported gate fixture population: {self.population}")
            base = replace(base, ap_traffic=product)
        else:
            base = replace(base, ap_traffic=None)
        return base

    def compose_current_ap_traffic(self, value, **kwargs):
        self.calls.append(("compose", kwargs))
        return value


def build_app(tmp: Path, source: GateHistorySource) -> Flask:
    settings = enabled_settings(
        web_admin_traffic_enabled="true",
        web_admin_traffic_history_enabled="true",
        web_admin_traffic_statistics_enabled="true",
        web_admin_traffic_peak_enabled="true",
        web_admin_traffic_by_ap_enabled="true",
        web_admin_max_response_bytes=str(MAX_RESPONSE_BYTES),
        web_admin_home_live_enabled="false",
        web_admin_home_traffic_enabled="false",
    )
    runtime = create_admin_web_runtime(
        settings,
        SimpleNamespace(
            state="active",
            visit_service=object(),
            current_traffic_service=OneApCurrentSource(),
            historical_traffic_service=source,
        ),
        SimpleNamespace(
            repository=SimpleNamespace(
                config=SimpleNamespace(db_path=tmp / "registry.sqlite3")
            )
        ),
        SimpleNamespace(repository=SimpleNamespace(db_path=tmp / "visits.sqlite3")),
        SimpleNamespace(
            _repository=SimpleNamespace(db_path=tmp / "observations.sqlite3")
        ),
        logging.getLogger("traffic05-payload-gate"),
    )
    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.wsgi_app = ProxyFix(
        app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1
    )
    app.register_blueprint(runtime.blueprint)
    app.extensions["admin_web_runtime"] = runtime
    return app


def request_combined(population: int):
    with tempfile.TemporaryDirectory(prefix=f"traffic05-{population}-") as raw:
        source = GateHistorySource(population)
        client = build_app(Path(raw), source).test_client()
        if login(client).status_code != 302:
            fail("admin login failed")
        response = client.get(
            f"/admin/api/v1/sites/{SITE_ID}/traffic/history"
            "?range=7d&include=statistics,peak,aps",
            base_url="https://localhost",
        )
        return response, source


def main() -> None:
    head = git("rev-parse", "HEAD")
    tree = git("rev-parse", "HEAD^{tree}")
    if head != EXPECTED_HEAD:
        fail(f"unexpected HEAD: {head}")
    if tree != EXPECTED_TREE:
        fail(f"unexpected tree: {tree}")
    if git("status", "--porcelain=v1"):
        fail("Preview worktree is not clean")

    print("TASK-TRAFFIC-05 PAYLOAD / POPULATION ACCEPTANCE")
    print(f"HEAD={head}")
    print(f"TREE={tree}")
    print()

    supported, _ = request_combined(12)
    if supported.status_code != 200:
        fail(
            f"12-AP combined HTTP status {supported.status_code}: "
            + supported.get_data(as_text=True)[:500]
        )
    body = supported.data
    result = supported.get_json()["result"]
    product = result["ap_traffic"]

    checks = {
        "range_id": result["range"]["id"],
        "bucket_count": result["range"]["bucket_count"],
        "statistics_status": result["period_statistics"]["status"],
        "peak_status": result["peak_load"]["status"],
        "ap_status": product["status"],
        "population_count": product["population"]["population_count"],
        "returned_ap_count": product["population"]["returned_ap_count"],
        "items": len(product["items"]),
        "series_buckets_each": sorted(
            {item["history"]["series"]["bucket_count"] for item in product["items"]}
        ),
    }
    expected = {
        "range_id": "7d",
        "bucket_count": 672,
        "statistics_status": "ok",
        "peak_status": "ok",
        "ap_status": "ok",
        "population_count": 12,
        "returned_ap_count": 12,
        "items": 12,
        "series_buckets_each": [672],
    }
    if checks != expected:
        fail(f"12-AP combined contract mismatch: {checks!r}")

    payload_bytes = len(body)
    print("12_AP_7D_COMBINED:")
    print("  HTTP=200")
    print("  SITE_BUCKETS=672")
    print("  AP_COUNT=12")
    print("  AP_SERIES_BUCKETS_EACH=672")
    print(f"  PAYLOAD_BYTES={payload_bytes}")
    print(f"  REQUIRED_MAX_BYTES={PAYLOAD_LIMIT}")
    print(f"  WEB_ADMIN_MAX_RESPONSE_BYTES={MAX_RESPONSE_BYTES}")
    print(f"  HEADROOM_BYTES={PAYLOAD_LIMIT - payload_bytes}")
    if payload_bytes > PAYLOAD_LIMIT:
        fail(
            f"12-AP/7d combined payload {payload_bytes} exceeds "
            f"{PAYLOAD_LIMIT}"
        )
    print("  RESULT=PASS")
    print()

    unsupported, _ = request_combined(13)
    if unsupported.status_code != 200:
        fail(
            f"13-AP combined HTTP status {unsupported.status_code}: "
            + unsupported.get_data(as_text=True)[:500]
        )
    product13 = unsupported.get_json()["result"]["ap_traffic"]
    if not (
        product13["status"] == "unsupported_population"
        and product13["population"]["population_count"] == 13
        and product13["population"]["supported_max_ap_count"] == 12
        and product13["population"]["returned_ap_count"] == 0
        and product13["population"]["population_complete"] is False
        and product13["current_snapshot"] is None
        and product13["items"] == []
    ):
        fail(f"13-AP unsupported contract mismatch: {product13!r}")

    print("13_AP_UNSUPPORTED:")
    print("  HTTP=200")
    print("  STATUS=unsupported_population")
    print("  POPULATION_COUNT=13")
    print("  SUPPORTED_MAX_AP_COUNT=12")
    print("  RETURNED_AP_COUNT=0")
    print("  POPULATION_COMPLETE=false")
    print("  ITEMS=0")
    print("  RESULT=PASS")
    print()
    print("RESULT: PASS")


if __name__ == "__main__":
    main()
