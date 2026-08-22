from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.admin_web.device_gateway import (
    AdminDeviceIntegrityError,
    AdminDeviceReadGateway,
    AdminDeviceSourceError,
)
from app.analytics.source_gateway import (
    AnalyticsQueryDeadlineExceeded,
    QueryDeadline,
)


SITE = "a" * 24
OTHER_SITE = "b" * 24


def _databases(tmp_path: Path) -> tuple[Path, Path]:
    registry = tmp_path / "registry.sqlite3"
    visits = tmp_path / "visits.sqlite3"
    with sqlite3.connect(registry) as connection:
        connection.executescript(
            """
            PRAGMA user_version=1;
            CREATE TABLE visitor_devices (
                device_id TEXT PRIMARY KEY,
                mac TEXT NOT NULL UNIQUE
            );
            CREATE TABLE device_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                site_id TEXT NOT NULL,
                requested_mac TEXT NOT NULL,
                authorized_at TEXT NOT NULL,
                captured_at TEXT NOT NULL,
                name TEXT,
                hostname TEXT,
                system_name TEXT,
                ip TEXT,
                ssid TEXT,
                ap_name TEXT,
                ap_mac TEXT,
                device_type TEXT,
                radio_id INTEGER,
                channel INTEGER,
                rssi INTEGER,
                snr INTEGER,
                traffic_down INTEGER,
                traffic_up INTEGER,
                uptime INTEGER,
                active INTEGER,
                auth_status INTEGER
            );
            CREATE INDEX idx_device_snapshots_site_order
            ON device_snapshots(site_id, authorized_at DESC, captured_at DESC);
            """
        )
    with sqlite3.connect(visits) as connection:
        connection.executescript(
            """
            PRAGMA user_version=2;
            CREATE TABLE visits (
                visit_id TEXT PRIMARY KEY,
                site_id TEXT NOT NULL,
                client_mac TEXT NOT NULL,
                device_id TEXT,
                started_at TEXT NOT NULL,
                closed_at TEXT,
                status TEXT NOT NULL
            );
            CREATE INDEX idx_visits_site_device_started
            ON visits(site_id, device_id, started_at DESC, visit_id DESC);
            """
        )
    return registry, visits


def _snapshot(
    registry: Path,
    *,
    device_id: str,
    mac: str,
    captured_at: str,
    site_id: str = SITE,
    suffix: str = "1",
    ip: str | None = None,
) -> None:
    with sqlite3.connect(registry) as connection:
        connection.execute(
            "INSERT OR IGNORE INTO visitor_devices(device_id, mac) VALUES (?, ?)",
            (device_id, mac),
        )
        connection.execute(
            """
            INSERT INTO device_snapshots(
                snapshot_id, device_id, site_id, requested_mac,
                authorized_at, captured_at, ip, ssid, ap_mac, device_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"snapshot-{device_id}-{suffix}",
                device_id,
                site_id,
                mac,
                captured_at,
                captured_at,
                ip,
                "OwnerWiFi",
                "AA:BB:CC:DD:EE:FF",
                "phone",
            ),
        )


def _visit(
    visits: Path,
    *,
    device_id: str,
    mac: str,
    started_at: str,
    closed_at: str | None = None,
    site_id: str = SITE,
    suffix: str = "1",
) -> None:
    with sqlite3.connect(visits) as connection:
        connection.execute(
            """
            INSERT INTO visits(
                visit_id, site_id, client_mac, device_id,
                started_at, closed_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"visit-{device_id}-{suffix}",
                site_id,
                mac,
                device_id,
                started_at,
                closed_at,
                "closed" if closed_at else "open",
            ),
        )


def _gateway(paths: tuple[Path, Path]) -> AdminDeviceReadGateway:
    return AdminDeviceReadGateway(*paths)


def _deadline() -> QueryDeadline:
    return QueryDeadline.after(10.0)


def test_exact_site_membership_union_counts_and_latest_context(tmp_path):
    paths = _databases(tmp_path)
    registry, visits = paths
    _snapshot(
        registry,
        device_id="snapshot-only",
        mac="00:00:00:00:00:01",
        captured_at="2026-01-01T01:00:00.000Z",
        ip="192.0.2.1",
    )
    _visit(
        visits,
        device_id="visit-only",
        mac="00:00:00:00:00:02",
        started_at="2026-01-01T02:00:00.000Z",
    )
    _snapshot(
        registry,
        device_id="both",
        mac="00:00:00:00:00:03",
        captured_at="2026-01-01T00:00:00.000Z",
        suffix="1",
        ip="192.0.2.3",
    )
    _snapshot(
        registry,
        device_id="both",
        mac="00:00:00:00:00:03",
        captured_at="2026-01-01T03:00:00.000Z",
        suffix="2",
        ip="192.0.2.33",
    )
    _visit(
        visits,
        device_id="both",
        mac="00:00:00:00:00:03",
        started_at="2025-12-31T23:00:00.000Z",
        closed_at="2026-01-01T04:00:00.000Z",
    )
    _snapshot(
        registry,
        device_id="other-site",
        mac="00:00:00:00:00:04",
        captured_at="2027-01-01T00:00:00.000Z",
        site_id=OTHER_SITE,
    )

    page = _gateway(paths).list_devices(
        site_id=SITE,
        limit=10,
        deadline=_deadline(),
    )

    assert [item.device_id for item in page.items] == [
        "both",
        "visit-only",
        "snapshot-only",
    ]
    both = page.items[0]
    assert both.site_first_seen_at == "2025-12-31T23:00:00.000Z"
    assert both.site_last_seen_at == "2026-01-01T04:00:00.000Z"
    assert both.site_snapshot_count == 2
    assert both.site_visit_count == 1
    assert both.last_site_ip == "192.0.2.33"
    assert page.items[1].last_site_ip is None


def test_exact_mac_filter_preserves_site_membership_and_deduplication(tmp_path):
    paths = _databases(tmp_path)
    registry, visits = paths
    _snapshot(
        registry,
        device_id="snapshot-only",
        mac="00:00:00:00:00:11",
        captured_at="2026-01-01T01:00:00.000Z",
    )
    _visit(
        visits,
        device_id="visit-only",
        mac="00:00:00:00:00:12",
        started_at="2026-01-01T02:00:00.000Z",
    )
    _snapshot(
        registry,
        device_id="both",
        mac="00:00:00:00:00:13",
        captured_at="2026-01-01T03:00:00.000Z",
    )
    _visit(
        visits,
        device_id="both",
        mac="00:00:00:00:00:13",
        started_at="2026-01-01T04:00:00.000Z",
    )
    _snapshot(
        registry,
        device_id="other-site",
        mac="00:00:00:00:00:14",
        captured_at="2026-01-01T05:00:00.000Z",
        site_id=OTHER_SITE,
    )
    _snapshot(
        registry,
        device_id="other-mac",
        mac="00:00:00:00:00:15",
        captured_at="2026-01-01T06:00:00.000Z",
    )

    gateway = _gateway(paths)
    snapshot_only = gateway.list_devices(
        site_id=SITE, canonical_mac="00:00:00:00:00:11",
        limit=10, deadline=_deadline(),
    )
    visit_only = gateway.list_devices(
        site_id=SITE, canonical_mac="00:00:00:00:00:12",
        limit=10, deadline=_deadline(),
    )
    both_page = gateway.list_devices(
        site_id=SITE, canonical_mac="00:00:00:00:00:13",
        limit=10, deadline=_deadline(),
    )
    other_site = gateway.list_devices(
        site_id=SITE, canonical_mac="00:00:00:00:00:14",
        limit=10, deadline=_deadline(),
    )

    assert [item.device_id for item in snapshot_only.items] == ["snapshot-only"]
    assert [item.device_id for item in visit_only.items] == ["visit-only"]
    assert [item.device_id for item in both_page.items] == ["both"]
    assert other_site.items == ()
    both = both_page.items[0]
    assert both.site_snapshot_count == 1
    assert both.site_visit_count == 1


def test_descending_keyset_is_stable_across_sources(tmp_path):
    paths = _databases(tmp_path)
    registry, visits = paths
    for number in range(1, 6):
        device_id = f"device-{number}"
        timestamp = f"2026-01-01T0{number}:00:00.000Z"
        mac = f"00:00:00:00:00:{number:02X}"
        if number % 2:
            _snapshot(
                registry,
                device_id=device_id,
                mac=mac,
                captured_at=timestamp,
            )
        else:
            _visit(
                visits,
                device_id=device_id,
                mac=mac,
                started_at=timestamp,
            )
    gateway = _gateway(paths)
    first = gateway.list_devices(site_id=SITE, limit=2, deadline=_deadline())
    cursor = (
        first.items[-1].site_last_seen_at,
        first.items[-1].device_id,
    )
    second = gateway.list_devices(
        site_id=SITE,
        limit=2,
        cursor=cursor,
        deadline=_deadline(),
    )
    third = gateway.list_devices(
        site_id=SITE,
        limit=2,
        cursor=(
            second.items[-1].site_last_seen_at,
            second.items[-1].device_id,
        ),
        deadline=_deadline(),
    )
    assert [item.device_id for item in first.items] == ["device-5", "device-4"]
    assert [item.device_id for item in second.items] == ["device-3", "device-2"]
    assert [item.device_id for item in third.items] == ["device-1"]
    assert first.has_more is True
    assert third.has_more is False


def test_canonical_mac_conflict_is_generic_integrity_failure(tmp_path):
    paths = _databases(tmp_path)
    registry, visits = paths
    _snapshot(
        registry,
        device_id="conflict",
        mac="00:00:00:00:00:01",
        captured_at="2026-01-01T01:00:00.000Z",
    )
    _visit(
        visits,
        device_id="conflict",
        mac="00:00:00:00:00:02",
        started_at="2026-01-01T02:00:00.000Z",
    )
    with pytest.raises(AdminDeviceIntegrityError, match="identity conflict"):
        _gateway(paths).list_devices(
            site_id=SITE,
            limit=100,
            deadline=_deadline(),
        )


@pytest.mark.parametrize("registry_version,visit_version", [(0, 2), (1, 1)])
def test_schema_versions_are_verified(tmp_path, registry_version, visit_version):
    paths = _databases(tmp_path)
    with sqlite3.connect(paths[0]) as connection:
        connection.execute(f"PRAGMA user_version={registry_version}")
    with sqlite3.connect(paths[1]) as connection:
        connection.execute(f"PRAGMA user_version={visit_version}")
    with pytest.raises(AdminDeviceSourceError, match="source unavailable"):
        _gateway(paths).list_devices(
            site_id=SITE,
            limit=100,
            deadline=_deadline(),
        )


def test_query_only_blocks_writes_on_attached_sources(tmp_path):
    paths = _databases(tmp_path)
    gateway = _gateway(paths)
    connection = gateway._open(_deadline())  # noqa: SLF001
    try:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute(
                "INSERT INTO registry_db.visitor_devices VALUES ('x', 'y')"
            )
    finally:
        connection.set_progress_handler(None, 0)
        connection.rollback()
        connection.close()


def test_deadline_interrupts_statement_and_handler_is_cleared(tmp_path, monkeypatch):
    paths = _databases(tmp_path)
    registry, _visits = paths
    with sqlite3.connect(registry) as connection:
        connection.executemany(
            "INSERT INTO visitor_devices(device_id, mac) VALUES (?, ?)",
            [
                (f"device-{number}", f"00:00:00:{number // 65536:02X}:{number // 256 % 256:02X}:{number % 256:02X}")
                for number in range(20_000)
            ],
        )
        connection.executemany(
            """
            INSERT INTO device_snapshots(
                snapshot_id, device_id, site_id, requested_mac,
                authorized_at, captured_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    f"snapshot-{number}",
                    f"device-{number}",
                    SITE,
                    f"00:00:00:{number // 65536:02X}:{number // 256 % 256:02X}:{number % 256:02X}",
                    "2026-01-01T00:00:00.000Z",
                    "2026-01-01T00:00:00.000Z",
                )
                for number in range(20_000)
            ],
        )

    calls = 0

    class ExpiringDeadline:
        def require_remaining(self):
            return None

        def expired(self):
            nonlocal calls
            calls += 1
            return calls > 1

    progress_calls: list[tuple[object, int]] = []
    original_connect = sqlite3.connect

    class TrackingConnection(sqlite3.Connection):
        def set_progress_handler(self, callback, instructions):
            progress_calls.append((callback, instructions))
            return super().set_progress_handler(callback, instructions)

    def tracking_connect(*args, **kwargs):
        kwargs["factory"] = TrackingConnection
        return original_connect(*args, **kwargs)

    monkeypatch.setattr("app.admin_web.device_gateway.sqlite3.connect", tracking_connect)
    with pytest.raises(AnalyticsQueryDeadlineExceeded):
        _gateway(paths).list_devices(
            site_id=SITE,
            limit=100,
            deadline=ExpiringDeadline(),  # type: ignore[arg-type]
        )
    assert progress_calls[-1] == (None, 0)


def test_explain_uses_site_indexes_and_reports_temp_btrees(tmp_path):
    paths = _databases(tmp_path)
    details = _gateway(paths).explain(site_id=SITE, deadline=_deadline())
    plan = "\n".join(details)
    assert "idx_device_snapshots_site_order" in plan
    assert "idx_visits_site_device_started" in plan
    assert "TEMP B-TREE" in plan


def test_device_page_executes_one_cross_database_data_statement(
    tmp_path, monkeypatch
):
    paths = _databases(tmp_path)
    _snapshot(
        paths[0],
        device_id="one",
        mac="00:00:00:00:00:01",
        captured_at="2026-01-01T01:00:00.000Z",
    )
    statements = []
    progress_calls = []
    original_connect = sqlite3.connect

    class TrackingConnection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if sql.lstrip().upper().startswith("WITH"):
                statements.append(sql)
            return super().execute(sql, parameters)

        def set_progress_handler(self, callback, instructions):
            progress_calls.append((callback, instructions))
            return super().set_progress_handler(callback, instructions)

    def connect(*args, **kwargs):
        kwargs["factory"] = TrackingConnection
        return original_connect(*args, **kwargs)

    monkeypatch.setattr("app.admin_web.device_gateway.sqlite3.connect", connect)
    _gateway(paths).list_devices(
        site_id=SITE,
        canonical_mac="00:00:00:00:00:01",
        limit=100,
        deadline=_deadline(),
    )
    assert len(statements) == 1
    assert progress_calls[-1] == (None, 0)
    assert "last_site_id" not in statements[0]
    assert "last_known_" not in statements[0]
