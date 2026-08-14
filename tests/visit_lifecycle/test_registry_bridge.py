from __future__ import annotations

import sqlite3
import uuid

from app.visitor_registry.registry_read_service import (
    VisitorRegistryReadService,
)


class RegistryRepositoryStub:
    def __init__(self, path):
        self.path = path

    def _connect(self, *, readonly=False):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection


def test_exact_snapshot_lookup_is_auth_session_site_and_mac_scoped(tmp_path):
    path = tmp_path / "registry.sqlite3"
    session_id = str(uuid.uuid4())
    selected_id = str(uuid.uuid4())
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE device_snapshots (
                snapshot_id TEXT, device_id TEXT, auth_session_id TEXT,
                site_id TEXT, requested_mac TEXT, authorized_at TEXT,
                captured_at TEXT
            )
            """
        )
        rows = [
            (str(uuid.uuid4()), str(uuid.uuid4()), session_id, "site-b",
             "02:11:22:33:44:55", "2026-08-13T10:00:00.000Z",
             "2026-08-13T10:00:01.000Z"),
            (str(uuid.uuid4()), str(uuid.uuid4()), session_id, "site-a",
             "02:00:00:00:00:01", "2026-08-13T10:00:00.000Z",
             "2026-08-13T10:00:01.000Z"),
            (selected_id, str(uuid.uuid4()), session_id, "site-a",
             "02:11:22:33:44:55", "2026-08-13T10:00:00.000Z",
             "2026-08-13T10:00:01.000Z"),
        ]
        connection.executemany(
            "INSERT INTO device_snapshots VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    service = VisitorRegistryReadService(
        RegistryRepositoryStub(path),
        object(),
        configured_enabled=True,
    )
    actual = service.get_snapshot_by_auth_session(
        session_id,
        site_id="site-a",
        client_mac="02-11-22-33-44-55",
    )
    assert actual["snapshot_id"] == selected_id
    assert "raw_snapshot_json" not in actual
    assert service.get_snapshot_by_auth_session(
        session_id,
        site_id="site-c",
        client_mac="02:11:22:33:44:55",
    ) is None
