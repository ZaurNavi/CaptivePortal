from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from types import SimpleNamespace

from app.analytics.source_gateway import (
    AnalyticsSourceGateway,
    QueryDeadline,
    _completed_visit_authorization_sql,
    _completed_visit_evidence_sql,
    _completed_visit_page_sql,
)


SITE = "a" * 24


class ReadBoundary:
    def __init__(self, path):
        self.path = path
        self.repository = SimpleNamespace(db_path=path, config=SimpleNamespace(db_path=path))
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


def _databases(tmp_path):
    visits = tmp_path / "visits.sqlite3"
    observations = tmp_path / "observations.sqlite3"
    with sqlite3.connect(visits) as connection:
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
    with sqlite3.connect(observations) as connection:
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
    boundary = ReadBoundary(visits)
    gateway = AnalyticsSourceGateway(ReadBoundary(observations), boundary, boundary)
    return gateway, visits, observations


def _insert_visit(path, identity, *, status="closed", started="2026-09-04T09:00:00.000Z",
                  closed="2026-09-05T09:00:00.000Z"):
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO visits VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (identity, SITE, "AA:BB:CC:DD:EE:01", started,
             None if status == "open" else closed, status,
             None if status == "open" else 86400, "Zefer_Parki", "Zefer_Parki",
             None, None),
        )


def test_closed_completion_cohort_uses_closed_at_and_keyset_not_visit_start(tmp_path):
    gateway, visits, _observations = _databases(tmp_path)
    ids = [
        "11111111-1111-4111-8111-111111111111",
        "22222222-2222-4222-8222-222222222222",
    ]
    _insert_visit(visits, ids[0], started="2026-09-01T00:00:00.000Z",
                  closed="2026-09-05T09:00:00.000Z")
    _insert_visit(visits, ids[1], closed="2026-09-05T08:00:00.000Z")
    _insert_visit(visits, "33333333-3333-4333-8333-333333333333", status="open")
    deadline = QueryDeadline.after(10)
    first = gateway.completed_visit_page(
        site_id=SITE, from_utc="2026-09-04T10:00:00.000Z",
        to_utc="2026-09-05T10:00:00.000Z", after=None, limit=1,
        deadline=deadline,
    )
    second = gateway.completed_visit_page(
        site_id=SITE, from_utc="2026-09-04T10:00:00.000Z",
        to_utc="2026-09-05T10:00:00.000Z",
        after=(first[0]["closed_at"], first[0]["visit_id"]), limit=1,
        deadline=deadline,
    )
    assert [first[0]["visit_id"], second[0]["visit_id"]] == ids


def test_authorization_and_observation_batches_are_strict_and_set_based(tmp_path):
    gateway, visits, observations = _databases(tmp_path)
    identity = "11111111-1111-4111-8111-111111111111"
    _insert_visit(
        visits, identity, started="2026-09-05T09:55:00.000Z",
        closed="2026-09-05T10:00:00.000Z",
    )
    with sqlite3.connect(visits) as connection:
        connection.executemany(
            "INSERT INTO visit_authorizations VALUES(?,?,?)",
            [(1, identity, "2026-09-05T09:55:00.000Z"),
             (2, identity, "2026-09-05T09:57:00.000Z")],
        )
    with sqlite3.connect(observations) as connection:
        connection.executemany(
            "INSERT INTO observation_cycles VALUES(?,?,?,?,?)",
            [("good", "client", "completed", "success", 1),
             ("partial", "client", "completed", "partial", 0)],
        )
        connection.executemany(
            "INSERT INTO client_observations VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            [(1, "good", "2026-09-05T09:56:00.000Z", SITE,
              "AA:BB:CC:DD:EE:01", 1, "Zefer_Parki", None, 10, 100, 200),
             (2, "partial", "2026-09-05T09:57:00.000Z", SITE,
              "AA:BB:CC:DD:EE:01", 1, "Zefer_Parki", None, 70, 200, 300),
             (3, "good", "2026-09-05T10:00:00.000Z", SITE,
              "AA:BB:CC:DD:EE:01", 1, "Zefer_Parki", None, 250, 300, 400)],
        )
    windows = ({
        "visit_id": identity, "client_mac": "AA:BB:CC:DD:EE:01",
        "started_at": "2026-09-05T09:55:00.000Z",
        "closed_at": "2026-09-05T10:00:00.000Z",
    },)
    boundaries = gateway.completed_visit_authorization_boundaries_batch(
        site_id=SITE, windows=windows, deadline=QueryDeadline.after(10)
    )
    evidence = gateway.completed_visit_traffic_evidence_batch(
        site_id=SITE, windows=windows, deadline=QueryDeadline.after(10)
    )
    assert [row["row_id"] for row in boundaries] == [2]
    assert [row["row_id"] for row in evidence] == [1]


def test_query_plans_use_existing_frozen_indexes(tmp_path):
    _gateway, visits, observations = _databases(tmp_path)
    window = (
        "11111111-1111-4111-8111-111111111111", SITE,
        "AA:BB:CC:DD:EE:01", "2026-09-05T09:00:00.000Z",
        "2026-09-05T10:00:00.000Z",
    )
    with sqlite3.connect(visits) as connection:
        visit_plan = " ".join(row[3] for row in connection.execute(
            "EXPLAIN QUERY PLAN " + _completed_visit_page_sql(with_after=False),
            (SITE, "2026-09-04T10:00:00.000Z", "2026-09-05T10:00:00.000Z", 50),
        ))
        auth_plan = " ".join(row[3] for row in connection.execute(
            "EXPLAIN QUERY PLAN " + _completed_visit_authorization_sql(1),
            window,
        ))
    with sqlite3.connect(observations) as connection:
        observation_plan = " ".join(row[3] for row in connection.execute(
            "EXPLAIN QUERY PLAN " + _completed_visit_evidence_sql(1),
            window,
        ))
    assert "idx_visits_site_closed" in visit_plan
    assert "idx_visit_auth_visit_time" in auth_plan
    assert "idx_client_site_mac_time" in observation_plan
    assert "SCAN visits" not in visit_plan
    assert "SCAN visit_authorizations" not in auth_plan
    assert "SCAN client_observations" not in observation_plan
