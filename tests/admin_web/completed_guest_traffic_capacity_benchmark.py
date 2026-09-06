"""Owner-run authenticated API50/API100 capacity gate for TRAFFIC-08.

This is intentionally not a pytest test.  It builds bounded Visit and client
Observation sources, uses the real Admin route/query/serializer stack, and
does not initialize a collector, writer, projection worker, or provider.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sqlite3
import statistics
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from app.admin_web import create_admin_web_runtime
from app.analytics.source_gateway import (
    _completed_visit_authorization_sql,
    _completed_visit_evidence_sql,
    _completed_visit_page_sql,
)
from tests.admin_web.conftest import enabled_settings, login


SITE = "a" * 24
OTHER_SITE = "b" * 24


class ReadBoundary:
    def __init__(self, path: Path):
        self.path = path
        self.repository = SimpleNamespace(
            db_path=path, config=SimpleNamespace(db_path=path)
        )
        self._repository = self.repository

    @contextmanager
    def analytics_read_connection(self):
        connection = sqlite3.connect(
            f"file:{self.path.as_posix()}?mode=ro", uri=True
        )
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()


def _utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _mac(index: int) -> str:
    return f"AA:BB:CC:{(index >> 16) & 255:02X}:{(index >> 8) & 255:02X}:{index & 255:02X}"


def _fingerprint(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    wal = path.with_name(path.name + "-wal")
    wal_data = wal.read_bytes() if wal.exists() else b""
    return {
        "main_size": len(data), "main_sha256": hashlib.sha256(data).hexdigest(),
        "wal_size": len(wal_data), "wal_sha256": hashlib.sha256(wal_data).hexdigest(),
    }


def _build(root: Path, count: int = 200):
    visits_path = root / "visits.sqlite3"
    observations_path = root / "observations.sqlite3"
    registry_path = root / "registry.sqlite3"
    projection_path = root / "traffic_projection.sqlite3"
    current_state_path = root / "current_state.sqlite3"
    public_traffic_path = root / "public_traffic.sqlite3"
    evaluated = datetime.now(timezone.utc)
    closed = evaluated - timedelta(minutes=5)
    started = closed - timedelta(hours=24)
    with sqlite3.connect(visits_path) as connection:
        connection.executescript("""
        PRAGMA user_version=2;
        CREATE TABLE visits(
          visit_id TEXT PRIMARY KEY,site_id TEXT,client_mac TEXT,started_at TEXT,
          closed_at TEXT,status TEXT,duration_seconds INTEGER,start_ssid TEXT,
          final_ssid TEXT,start_ap_mac TEXT,final_ap_mac TEXT
        );
        CREATE TABLE visit_authorizations(
          row_id INTEGER PRIMARY KEY,visit_id TEXT,authorized_at TEXT
        );
        CREATE INDEX idx_visits_site_closed ON visits(site_id,closed_at,visit_id);
        CREATE INDEX idx_visit_auth_visit_time ON visit_authorizations(visit_id,authorized_at,row_id);
        """)
        visits = []
        for index in range(count):
            visit_start = started - timedelta(seconds=1) if index == 15 else started
            duration = 86_401 if index == 15 else 86_400
            visits.append((
                str(uuid.UUID(int=index + 1)), SITE, _mac(index), _utc(visit_start),
                _utc(closed), "closed", duration, "Zefer_Parki", "Zefer_Parki",
                "AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02",
            ))
        connection.executemany(
            "INSERT INTO visits VALUES(?,?,?,?,?,?,?,?,?,?,?)", visits
        )
        connection.execute(
            "INSERT INTO visit_authorizations VALUES(?,?,?)",
            (1, str(uuid.UUID(int=9)), _utc(started + timedelta(minutes=10))),
        )
    with sqlite3.connect(observations_path) as connection:
        connection.executescript("""
        PRAGMA user_version=1;
        CREATE TABLE observation_cycles(
          cycle_id TEXT PRIMARY KEY,kind TEXT,state TEXT,result TEXT,complete INTEGER
        );
        CREATE TABLE client_observations(
          row_id INTEGER PRIMARY KEY,cycle_id TEXT,observed_at TEXT,site_id TEXT,
          client_mac TEXT,source_inventory_complete INTEGER,ssid TEXT,ap_mac TEXT,
          uptime INTEGER,traffic_down INTEGER,traffic_up INTEGER
        );
        CREATE INDEX idx_client_site_mac_time
          ON client_observations(site_id,client_mac,observed_at,row_id);
        """)
        row_id = 0
        for minute in range(1440):
            observed = started + timedelta(seconds=30 + minute * 60)
            cycle = f"cycle-{minute:04d}"
            connection.execute(
                "INSERT INTO observation_cycles VALUES(?,?,?,?,?)",
                (cycle, "client", "completed", "success", 1),
            )
            rows = []
            for index in range(count):
                if index in {14, 15}:
                    continue
                if index == 11 and 10 <= minute <= 13:
                    continue
                if index == 12 and minute < 4:
                    continue
                if index == 13 and minute >= 1436:
                    continue
                row_id += 1
                uptime = 10_000 + minute * 60
                down = index * 1000 + minute * 17
                up = index * 500 + minute * 11
                ssid = "Zefer_Parki"
                ap_mac = _mac(1000 + index % 2)
                if index == 1:
                    down = index * 1000
                    up = index * 500
                if index == 2 and minute == 10:
                    uptime -= 60
                if index == 3 and minute == 10:
                    uptime = 1
                if index == 4 and minute == 10:
                    uptime = None
                if index == 5 and minute == 10:
                    down = 0
                if index == 6 and minute == 10:
                    up = None
                if index == 7 and minute >= 720:
                    ap_mac = _mac(2000)
                if index == 9 and minute == 10:
                    ssid = "Other"
                if index == 10 and minute == 10:
                    ssid = None
                rows.append((row_id, cycle, _utc(observed), SITE, _mac(index), 1,
                             ssid, ap_mac, uptime, down, up))
            connection.executemany(
                "INSERT INTO client_observations VALUES(?,?,?,?,?,?,?,?,?,?,?)", rows
            )
        unrelated = []
        for index in range(30_000):
            row_id += 1
            unrelated.append((row_id, "cycle-0000", _utc(started + timedelta(seconds=30)),
                              OTHER_SITE, _mac(50_000 + index), 1, "Other", None,
                              1, index, index))
        connection.executemany(
            "INSERT INTO client_observations VALUES(?,?,?,?,?,?,?,?,?,?,?)", unrelated
        )
    for path in (
        registry_path, projection_path, current_state_path, public_traffic_path,
    ):
        with sqlite3.connect(path) as connection:
            connection.execute("PRAGMA user_version=1")
    immutable = {
        "visits": visits_path,
        "observations": observations_path,
        "projection": projection_path,
        "current_state": current_state_path,
        "public_traffic": public_traffic_path,
    }
    return visits_path, observations_path, registry_path, immutable, evaluated


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(fraction * len(ordered) + 0.999) - 1))
    return ordered[index]


def _measure(client, limit: int, runs: int) -> dict[str, object]:
    durations = []
    maximum_bytes = 0
    semantic = None
    for _ in range(runs):
        started = time.perf_counter()
        response = client.get(
            f"/admin/api/v1/sites/{SITE}/traffic/completed-sessions?range=24h&limit={limit}",
            base_url="https://localhost",
        )
        durations.append(time.perf_counter() - started)
        if response.status_code != 200:
            raise RuntimeError(f"unexpected HTTP status {response.status_code}")
        maximum_bytes = max(maximum_bytes, len(response.data))
        payload = response.get_json()["result"]
        current = (payload["status"], payload["page"]["returned_count"],
                   payload["page"]["next_cursor"] is not None)
        if semantic is not None and current != semantic:
            raise RuntimeError("completed-session API result changed across runs")
        semantic = current
    return {
        "runs": runs,
        "p50_seconds": statistics.median(durations),
        "p95_seconds": _percentile(durations, 0.95),
        "max_seconds": max(durations),
        "max_response_bytes": maximum_bytes,
        "payload_budget_256k": maximum_bytes <= 256 * 1024,
        "unexpected_http_statuses": 0,
        "deadline_failures": 0,
        "semantic": semantic,
    }


def _plans(visits: Path, observations: Path) -> dict[str, list[str]]:
    with sqlite3.connect(visits) as connection:
        rows = connection.execute(
            "SELECT visit_id,client_mac,started_at,closed_at FROM visits "
            "ORDER BY visit_id LIMIT 100"
        ).fetchall()
        window_parameters = tuple(
            value
            for row in rows
            for value in (row[0], SITE, row[1], row[2], row[3])
        )
        visit = [item[3] for item in connection.execute(
            "EXPLAIN QUERY PLAN " + _completed_visit_page_sql(with_after=False),
            (SITE, "a", "z", 100),
        )]
        authorization = [row[3] for row in connection.execute(
            "EXPLAIN QUERY PLAN " + _completed_visit_authorization_sql(len(rows)),
            window_parameters,
        )]
    with sqlite3.connect(observations) as connection:
        observation = [row[3] for row in connection.execute(
            "EXPLAIN QUERY PLAN " + _completed_visit_evidence_sql(len(rows)),
            window_parameters,
        )]
    return {"Visit": visit, "Authorization": authorization, "Observation": observation}


def _assert_no_persistent_full_scan(plans: dict[str, list[str]]) -> None:
    forbidden = {
        "Visit": ("SCAN visits", "SCAN v"),
        "Authorization": ("SCAN visit_authorizations", "SCAN a"),
        "Observation": ("SCAN client_observations", "SCAN o"),
    }
    for name, fragments in forbidden.items():
        details = "\n".join(plans[name])
        if any(fragment in details for fragment in fragments):
            raise RuntimeError(f"{name} actual query performs a persistent full scan")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=10)
    args = parser.parse_args()
    if args.runs < 10:
        raise SystemExit("--runs must be at least 10")
    with tempfile.TemporaryDirectory(prefix="traffic08-product-") as temporary:
        root = Path(temporary)
        visits, observations, registry, immutable, _evaluated = _build(root)
        boundaries = (ReadBoundary(observations), ReadBoundary(visits), ReadBoundary(registry))
        before = {name: _fingerprint(path) for name, path in immutable.items()}
        runtime = create_admin_web_runtime(
            enabled_settings(
                web_admin_allowed_site_ids=SITE,
                web_admin_default_site_id=SITE,
                web_admin_traffic_enabled="true",
                web_admin_traffic_completed_sessions_enabled="true",
            ),
            SimpleNamespace(state="active", visit_service=object()),
            boundaries[2], boundaries[1], boundaries[0],
            logging.getLogger("traffic08-product-benchmark"),
        )
        app = Flask(__name__)
        app.config.update(TESTING=True)
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
        app.register_blueprint(runtime.blueprint)
        client = app.test_client()
        if login(client).status_code != 302:
            raise RuntimeError("Admin authentication failed")
        measurements = {
            "API50": _measure(client, 50, args.runs),
            "API100": _measure(client, 100, args.runs),
        }
        after = {name: _fingerprint(path) for name, path in immutable.items()}
        if before != after:
            raise RuntimeError("authenticated product reads changed durable sources")
        if not all(item["payload_budget_256k"] for item in measurements.values()):
            raise RuntimeError("Completed-session payload exceeded 256 KiB")
        thresholds = {
            "API50": {"p95_seconds": 2.0, "max_seconds": 3.0},
            "API100": {"p95_seconds": 4.0, "max_seconds": 6.0},
        }
        for name, limits in thresholds.items():
            for metric, maximum in limits.items():
                if measurements[name][metric] > maximum:
                    raise RuntimeError(
                        f"{name} {metric} exceeded {maximum:.1f} seconds"
                    )
        plans = _plans(visits, observations)
        _assert_no_persistent_full_scan(plans)
        for name, expected in (("Visit", "idx_visits_site_closed"),
                               ("Authorization", "idx_visit_auth_visit_time"),
                               ("Observation", "idx_client_site_mac_time")):
            if expected not in " ".join(plans[name]):
                raise RuntimeError(f"{name} query plan missed {expected}")
        print(json.dumps({
            "fixture": {"visits": 200, "supported_window_seconds": 86_400,
                        "cadence_seconds": 60,
                        "unrelated_observation_rows": 30_000,
                        "semantic_edge_cases": [
                            "uptime_frozen", "uptime_reset", "uptime_missing",
                            "zero_delta", "counter_reset", "counter_missing",
                            "ap_roam", "authorization_boundary", "ssid_transition",
                            "ssid_missing", "gap_over_180s", "start_edge_uncovered",
                            "end_edge_uncovered", "no_samples", "visit_over_24h",
                        ]},
            "measurements": measurements,
            "performance_thresholds": thresholds,
            "query_plans": plans,
            "read_only_unchanged": sorted(immutable),
            "provider_calls": 0,
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
