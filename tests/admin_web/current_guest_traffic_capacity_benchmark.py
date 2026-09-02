"""Owner-run authenticated HTTP capacity gate for TRAFFIC-07.

This is deliberately not a pytest test.  It uses a temporary 10k+10k Current
State fixture, the real Admin route/query/serialization stack, and no provider.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import statistics
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from app.admin_web import create_admin_web_runtime
from app.current_state.read_service import CurrentStateReadService
from app.current_state.repository import CurrentStateRepository
from tests.admin_web.conftest import enabled_settings, login
from tests.analytics.current_guest_traffic_capacity_benchmark import (
    SITE,
    _fingerprint,
    _config,
    _cycle,
    _mixed_rows,
)


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(fraction * len(ordered) + 0.999) - 1))
    return ordered[index]


def _measure(client, *, limit: int, runs: int) -> dict[str, object]:
    durations: list[float] = []
    semantic = None
    max_bytes = 0
    for _ in range(runs):
        started = time.perf_counter()
        response = client.get(
            f"/admin/api/v1/sites/{SITE}/traffic/online-guests/current?limit={limit}",
            base_url="https://localhost",
        )
        durations.append(time.perf_counter() - started)
        if response.status_code != 200:
            raise RuntimeError(f"unexpected HTTP status {response.status_code}")
        max_bytes = max(max_bytes, len(response.data))
        payload = response.get_json()
        current = {
            "status": payload["result"]["status"],
            "population": payload["result"]["population_count"],
            "rate_counts": (
                payload["result"]["rate_valid_count"],
                payload["result"]["rate_partial_count"],
                payload["result"]["rate_unavailable_count"],
            ),
            "returned": payload["page"]["returned_count"],
            "has_cursor": payload["page"]["next_cursor"] is not None,
        }
        if semantic is not None and semantic != current:
            raise RuntimeError("HTTP product result is nondeterministic")
        semantic = current
    return {
        "runs": runs,
        "p50_seconds": statistics.median(durations),
        "p95_seconds": _percentile(durations, 0.95),
        "max_seconds": max(durations),
        "max_response_bytes": max_bytes,
        "payload_budget_256k": max_bytes <= 256 * 1024,
        "semantic": semantic,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=10)
    args = parser.parse_args()
    if args.runs < 10:
        raise SystemExit("--runs must be at least 10")
    with tempfile.TemporaryDirectory(prefix="traffic07-product-") as temporary:
        root = Path(temporary)
        baseline, current = _mixed_rows()
        now = datetime.now(timezone.utc)
        current_at = (now - timedelta(seconds=10)).strftime(
            "%Y-%m-%dT%H:%M:%S.%f"
        )[:23] + "Z"
        baseline_at = (now - timedelta(seconds=70)).strftime(
            "%Y-%m-%dT%H:%M:%S.%f"
        )[:23] + "Z"
        for row in baseline:
            row["observed_at"] = baseline_at
        for row in current:
            row["observed_at"] = current_at
        repository = CurrentStateRepository(_config(root, "product"))
        repository.initialize()
        repository.publish_cycle(
            _cycle("baseline", baseline_at, len(baseline)),
            client_rows=baseline,
        )
        repository.publish_cycle(
            _cycle("current", current_at, len(current)),
            client_rows=current,
        )
        db_path = Path(repository.config.db_path)
        before = _fingerprint(db_path)
        runtime = create_admin_web_runtime(
            enabled_settings(
                web_admin_allowed_site_ids=SITE,
                web_admin_default_site_id=SITE,
                web_admin_traffic_enabled="true",
                web_admin_traffic_online_guests_enabled="true",
            ),
            SimpleNamespace(state="active", visit_service=object()),
            SimpleNamespace(repository=SimpleNamespace(
                config=SimpleNamespace(db_path=root / "registry.sqlite3")
            )),
            SimpleNamespace(repository=SimpleNamespace(db_path=root / "visits.sqlite3")),
            SimpleNamespace(_repository=SimpleNamespace(db_path=root / "observations.sqlite3")),
            logging.getLogger("traffic07-product-benchmark"),
            current_state_read_service=CurrentStateReadService(repository),
        )
        if runtime.traffic_online_guests_state != "active":
            raise RuntimeError("Online Guests product did not compose")
        app = Flask(__name__)
        app.config.update(TESTING=True)
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
        app.register_blueprint(runtime.blueprint)
        client = app.test_client()
        if login(client).status_code != 302:
            raise RuntimeError("Admin authentication failed")
        measurements = {
            "API50": _measure(client, limit=50, runs=args.runs),
            "API200": _measure(client, limit=200, runs=args.runs),
        }
        after = _fingerprint(db_path)
        if before != after:
            raise RuntimeError("authenticated product reads changed durable storage")
        if not all(item["payload_budget_256k"] for item in measurements.values()):
            raise RuntimeError("256 KiB product payload budget exceeded")
        print(json.dumps({
            "fixture": {"current_rows": 10_000, "baseline_rows": 10_000},
            "measurements": measurements,
            "read_only_unchanged": True,
            "provider_calls": 0,
            "db_sha256": hashlib.sha256(db_path.read_bytes()).hexdigest(),
        }, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
