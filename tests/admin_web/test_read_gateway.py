from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.admin_web.read_gateway import AdminReadSourceError, AdminSqlReadGateway
from app.analytics.source_gateway import QueryDeadline


SITE = "a" * 24
OTHER_SITE = "b" * 24
MAC = "02:00:00:00:00:01"
AP = "02:00:00:00:00:02"


def _databases(tmp_path: Path) -> tuple[Path, Path]:
    visits = tmp_path / "visits.sqlite3"
    observations = tmp_path / "observations.sqlite3"
    with sqlite3.connect(visits) as connection:
        connection.executescript(
            """
            PRAGMA user_version=2;
            CREATE TABLE visits (
                visit_id TEXT PRIMARY KEY, site_id TEXT, client_mac TEXT,
                device_id TEXT, started_at TEXT, closed_at TEXT, status TEXT,
                duration_seconds INTEGER, start_ssid TEXT, final_ssid TEXT,
                start_ap_mac TEXT, final_ap_mac TEXT,
                reported_traffic_total_bytes INTEGER, close_reason TEXT,
                close_time_source TEXT, start_ip TEXT, final_ip TEXT,
                reported_connected_seconds INTEGER,
                reported_traffic_up_bytes INTEGER,
                reported_traffic_down_bytes INTEGER
            );
            CREATE TABLE visit_authorizations (
                visit_id TEXT, portal_ssid TEXT, portal_ap_mac TEXT
            );
            CREATE INDEX idx_visits_site_started
            ON visits(site_id, started_at DESC, visit_id DESC);
            """
        )
    with sqlite3.connect(observations) as connection:
        connection.executescript(
            """
            PRAGMA user_version=1;
            CREATE TABLE observation_cycles (
                cycle_id TEXT PRIMARY KEY, state TEXT
            );
            CREATE TABLE client_observations (
                row_id INTEGER PRIMARY KEY, cycle_id TEXT, observed_at TEXT,
                site_id TEXT, client_mac TEXT, ip TEXT, ssid TEXT,
                ap_name TEXT, ap_mac TEXT, radio_id INTEGER, band TEXT,
                channel INTEGER, rssi INTEGER, snr INTEGER, rx_rate INTEGER,
                tx_rate INTEGER, traffic_down INTEGER, traffic_up INTEGER,
                uptime INTEGER, auth_status INTEGER, active INTEGER,
                raw_secret TEXT
            );
            CREATE TABLE ap_observations (
                row_id INTEGER PRIMARY KEY, cycle_id TEXT, observed_at TEXT,
                site_id TEXT, ap_mac TEXT, name TEXT, ip TEXT, model TEXT,
                firmware_version TEXT, cpu_util REAL, mem_util REAL,
                uptime_seconds INTEGER, wired_download_mbps REAL,
                wired_upload_mbps REAL, lan_rx_mbps REAL, lan_tx_mbps REAL,
                partial INTEGER, raw_secret TEXT
            );
            CREATE TABLE ap_radio_observations (
                row_id INTEGER PRIMARY KEY, cycle_id TEXT,
                ap_observation_row_id INTEGER, radio_observed_at TEXT,
                site_id TEXT, ap_mac TEXT, band TEXT, radio_id INTEGER,
                actual_channel INTEGER, frequency_mhz INTEGER,
                channel_width TEXT, tx_power REAL, tx_util REAL, rx_util REAL,
                interference_util REAL, busy_util REAL, radio_rx_mbps REAL,
                radio_tx_mbps REAL, raw_secret TEXT
            );
            CREATE INDEX idx_client_site_mac_time
            ON client_observations(site_id, client_mac, observed_at, row_id);
            CREATE INDEX idx_ap_site_mac_time
            ON ap_observations(site_id, ap_mac, observed_at, row_id);
            CREATE INDEX idx_radio_site_ap_band_time
            ON ap_radio_observations(
                site_id, ap_mac, band, radio_observed_at, row_id
            );
            """
        )
    return visits, observations


def _gateway(paths):
    return AdminSqlReadGateway(*paths)


def _deadline():
    return QueryDeadline.after(10)


def _insert_visit(path, identity, site, started):
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            INSERT INTO visits(
                visit_id,site_id,client_mac,device_id,started_at,status,
                start_ssid,start_ap_mac
            ) VALUES (?,?,?,?,?,'open','OwnerWiFi',?)
            """,
            (identity, site, MAC, identity, started, AP),
        )


def test_visit_reads_are_site_scoped_descending_and_safe(tmp_path):
    paths = _databases(tmp_path)
    _insert_visit(paths[0], "v1", SITE, "2026-01-01T01:00:00.000Z")
    _insert_visit(paths[0], "v2", SITE, "2026-01-01T02:00:00.000Z")
    _insert_visit(paths[0], "foreign", OTHER_SITE, "2027-01-01T00:00:00.000Z")
    gateway = _gateway(paths)
    items, has_more = gateway.list_visits(
        site_id=SITE, limit=1, deadline=_deadline()
    )
    assert items[0]["visit_id"] == "v2"
    assert "site_id" not in items[0]
    assert has_more is True
    second, _ = gateway.list_visits(
        site_id=SITE,
        limit=1,
        cursor=(items[0]["started_at"], items[0]["visit_id"]),
        deadline=_deadline(),
    )
    assert second[0]["visit_id"] == "v1"
    assert gateway.get_visit(
        site_id=SITE, visit_id="foreign", deadline=_deadline()
    ) is None


def test_client_observation_uses_allowlist_and_descending_keyset(tmp_path):
    paths = _databases(tmp_path)
    with sqlite3.connect(paths[1]) as connection:
        connection.execute("INSERT INTO observation_cycles VALUES ('c','completed')")
        for row_id in (1, 2):
            connection.execute(
                """
                INSERT INTO client_observations(
                    row_id,cycle_id,observed_at,site_id,client_mac,ip,active,
                    raw_secret
                ) VALUES (?,'c',?,?,?,'192.0.2.1',1,'forbidden')
                """,
                (row_id, f"2026-01-01T0{row_id}:00:00.000Z", SITE, MAC),
            )
        connection.execute(
            """
            INSERT INTO client_observations(
                row_id,cycle_id,observed_at,site_id,client_mac,raw_secret
            ) VALUES (3,'c','2026-01-01T03:00:00.000Z',?,?,'foreign')
            """,
            (OTHER_SITE, MAC),
        )
    items, more = _gateway(paths).list_client_observations(
        site_id=SITE,
        client_mac=MAC,
        from_utc="2026-01-01T00:00:00.000Z",
        to_utc="2026-01-02T00:00:00.000Z",
        limit=1,
        deadline=_deadline(),
    )
    assert items[0]["observed_at"] == "2026-01-01T02:00:00.000Z"
    assert items[0]["active"] is True
    assert "raw_secret" not in items[0]
    assert more is True


def test_ap_page_batches_radios_in_exactly_two_selects(tmp_path, monkeypatch):
    paths = _databases(tmp_path)
    with sqlite3.connect(paths[1]) as connection:
        connection.execute("INSERT INTO observation_cycles VALUES ('c','completed')")
        connection.execute(
            """
            INSERT INTO ap_observations(
                row_id,cycle_id,observed_at,site_id,ap_mac,name,partial,raw_secret
            ) VALUES (1,'c','2026-01-01T01:00:00.000Z',?,?,?,0,'forbidden')
            """,
            (SITE, AP, "AP-1"),
        )
        connection.executemany(
            """
            INSERT INTO ap_radio_observations(
                row_id,cycle_id,ap_observation_row_id,radio_observed_at,
                site_id,ap_mac,band,radio_id,raw_secret
            ) VALUES (?,'c',1,'2026-01-01T01:00:00.000Z',?,?,?,?, 'forbidden')
            """,
            [(1, SITE, AP, "2.4GHz", 0), (2, SITE, AP, "5GHz", 1)],
        )
    statements = []
    original_connect = sqlite3.connect

    class TrackingConnection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if sql.lstrip().upper().startswith("SELECT"):
                statements.append(sql)
            return super().execute(sql, parameters)

    def connect(*args, **kwargs):
        kwargs["factory"] = TrackingConnection
        return original_connect(*args, **kwargs)

    monkeypatch.setattr("app.admin_web.read_gateway.sqlite3.connect", connect)
    items, more = _gateway(paths).list_ap_observations(
        site_id=SITE,
        ap_mac=AP,
        from_utc="2026-01-01T00:00:00.000Z",
        to_utc="2026-01-02T00:00:00.000Z",
        limit=100,
        deadline=_deadline(),
    )
    assert more is False
    assert [radio["band"] for radio in items[0]["radios"]] == ["2.4GHz", "5GHz"]
    assert "raw_secret" not in items[0]
    assert all("raw_secret" not in radio for radio in items[0]["radios"])
    assert len(statements) == 2


def test_source_schema_version_mismatch_is_sanitized(tmp_path):
    paths = _databases(tmp_path)
    with sqlite3.connect(paths[0]) as connection:
        connection.execute("PRAGMA user_version=1")
    with pytest.raises(AdminReadSourceError, match="source unavailable"):
        _gateway(paths).list_visits(site_id=SITE, limit=1, deadline=_deadline())
