from __future__ import annotations

import sqlite3
import uuid

import pytest

from app.visit_lifecycle import SCHEMA_VERSION, VisitRepository, VisitSchemaError
from app.visit_lifecycle import repository as repository_module
from app.visit_lifecycle.repository import (
    _schema_signature,
    _schema_sql_v1,
)

from .conftest import config_with


V2_COLUMNS = {
    "client_ip",
    "ssid",
    "ap_mac",
    "reported_connected_seconds",
    "reported_traffic_total_bytes",
}


def _create_v1(path):
    with sqlite3.connect(path) as connection:
        connection.executescript(_schema_sql_v1())


def _columns(path):
    with sqlite3.connect(path) as connection:
        return {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(visit_source_events)"
            )
        }


def _table_info(path):
    with sqlite3.connect(path) as connection:
        return tuple(
            tuple(row)
            for row in connection.execute(
                "PRAGMA table_info(visit_source_events)"
            )
        )


def _signature(path):
    with sqlite3.connect(path) as connection:
        return _schema_signature(connection)


def _rewrite_source_table_sql(path, transform):
    with sqlite3.connect(path) as connection:
        original = connection.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type='table' AND name='visit_source_events'"
        ).fetchone()[0]
        normalized = " ".join(original.split())
        modified = transform(normalized)
        assert modified != normalized
        schema_version = int(connection.execute(
            "PRAGMA schema_version"
        ).fetchone()[0])
        connection.execute("PRAGMA writable_schema=ON")
        connection.execute(
            "UPDATE sqlite_master SET sql=? "
            "WHERE type='table' AND name='visit_source_events'",
            (modified,),
        )
        connection.execute(f"PRAGMA schema_version={schema_version + 1}")
        connection.execute("PRAGMA writable_schema=OFF")
    return modified


def _seed_v1(path, *, pending=False):
    visit_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            """
            INSERT INTO visits (
                visit_id, site_id, client_mac,
                start_auth_session_id, start_auth_run_number,
                start_final_reason, started_at, status,
                created_at, updated_at
            ) VALUES (?, 'site-a', '02:11:22:33:44:55', ?, 1,
                      'AUTHORIZED_AFTER_ATTEMPT', ?, 'open', ?, ?)
            """,
            (
                visit_id,
                session_id,
                "2026-08-13T10:00:00.000Z",
                "2026-08-13T10:00:00.000Z",
                "2026-08-13T10:00:00.000Z",
            ),
        )
        connection.execute(
            """
            INSERT INTO visit_authorizations (
                visit_id, auth_session_id, auth_run_number,
                authorized_at, final_reason, created_at
            ) VALUES (?, ?, 1, ?, 'AUTHORIZED_AFTER_ATTEMPT', ?)
            """,
            (
                visit_id,
                session_id,
                "2026-08-13T10:00:00.000Z",
                "2026-08-13T10:00:00.000Z",
            ),
        )
        connection.execute(
            """
            INSERT INTO visit_source_events (
                event_id, event_type, site_id, client_mac,
                controller_event_at, received_at,
                source_identity, source_offset_start, source_offset_end,
                processing_result, reason, first_processed_at,
                processed_at, pending_until
            ) VALUES ('event:0', 'omada.client_offline', 'site-a',
                      '02:11:22:33:44:55', ?, ?, '1:1', 0, 100,
                      ?, ?, ?, ?, ?)
            """,
            (
                "2026-08-13T10:05:00.000Z",
                "2026-08-13T10:05:01.000Z",
                "pending_match" if pending else "unmatched",
                "no_open_visit",
                "2026-08-13T10:05:02.000Z",
                "2026-08-13T10:05:02.000Z",
                "2026-08-13T10:05:32.000Z" if pending else None,
            ),
        )
    return visit_id, session_id


def test_new_database_is_created_directly_as_schema_v2(visit_config):
    repository = VisitRepository(visit_config)
    assert repository.initialize() is True
    with sqlite3.connect(visit_config.db_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
    assert V2_COLUMNS <= _columns(visit_config.db_path)


def test_exact_v1_migrates_and_preserves_rows_with_null_context(visit_config):
    _create_v1(visit_config.db_path)
    visit_id, session_id = _seed_v1(visit_config.db_path)

    assert VisitRepository(visit_config).initialize() is False

    with sqlite3.connect(visit_config.db_path) as connection:
        connection.row_factory = sqlite3.Row
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert connection.execute(
            "SELECT visit_id FROM visits"
        ).fetchone()[0] == visit_id
        assert connection.execute(
            "SELECT auth_session_id FROM visit_authorizations"
        ).fetchone()[0] == session_id
        event = connection.execute(
            "SELECT * FROM visit_source_events WHERE event_id='event:0'"
        ).fetchone()
        assert event is not None
        assert all(event[column] is None for column in V2_COLUMNS)


def test_fresh_and_migrated_v2_have_identical_layout_and_signature(
    visit_config,
):
    migrated_config = config_with(
        visit_config,
        db_path=str(visit_config.db_path) + ".migrated",
    )
    assert VisitRepository(visit_config).initialize() is True
    _create_v1(migrated_config.db_path)
    assert VisitRepository(migrated_config).initialize() is False

    assert _table_info(visit_config.db_path) == _table_info(
        migrated_config.db_path
    )
    assert _signature(visit_config.db_path) == _signature(
        migrated_config.db_path
    )


def test_v1_pending_event_blocks_migration_without_changes(visit_config):
    _create_v1(visit_config.db_path)
    _seed_v1(visit_config.db_path, pending=True)
    before = _columns(visit_config.db_path)

    with pytest.raises(VisitSchemaError, match="pending offline evidence"):
        VisitRepository(visit_config).initialize()

    with sqlite3.connect(visit_config.db_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert connection.execute(
            "SELECT processing_result FROM visit_source_events"
        ).fetchone()[0] == "pending_match"
    assert _columns(visit_config.db_path) == before


def test_modified_v1_is_rejected_without_changes(visit_config):
    _create_v1(visit_config.db_path)
    with sqlite3.connect(visit_config.db_path) as connection:
        connection.execute("DROP INDEX idx_visit_events_site_processed")
    before = _columns(visit_config.db_path)

    with pytest.raises(VisitSchemaError, match="exact contract"):
        VisitRepository(visit_config).initialize()

    with sqlite3.connect(visit_config.db_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
    assert _columns(visit_config.db_path) == before


def test_migration_failure_rolls_back_all_alter_statements(
    visit_config,
    monkeypatch,
):
    _create_v1(visit_config.db_path)
    statements = repository_module.MIGRATION_V1_TO_V2_STATEMENTS
    monkeypatch.setattr(
        repository_module,
        "MIGRATION_V1_TO_V2_STATEMENTS",
        (statements[0], "ALTER TABLE missing_table ADD COLUMN broken TEXT"),
    )

    with pytest.raises(Exception):
        VisitRepository(visit_config).initialize()

    with sqlite3.connect(visit_config.db_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
    assert V2_COLUMNS.isdisjoint(_columns(visit_config.db_path))


def test_repeated_initialize_on_v2_is_noop(visit_config):
    repository = VisitRepository(visit_config)
    assert repository.initialize() is True
    with sqlite3.connect(visit_config.db_path) as connection:
        before = connection.execute(
            "SELECT type, name, sql FROM sqlite_master ORDER BY type, name"
        ).fetchall()
    assert repository.initialize() is False
    with sqlite3.connect(visit_config.db_path) as connection:
        after = connection.execute(
            "SELECT type, name, sql FROM sqlite_master ORDER BY type, name"
        ).fetchall()
        assert connection.execute("PRAGMA user_version").fetchone()[0] == (
            SCHEMA_VERSION
        )
    assert after == before


def test_foreign_version_zero_schema_is_rejected_unchanged(visit_config):
    with sqlite3.connect(visit_config.db_path) as connection:
        connection.execute("CREATE TABLE foreign_data (value TEXT)")
    with pytest.raises(VisitSchemaError, match="non-empty"):
        VisitRepository(visit_config).initialize()
    with sqlite3.connect(visit_config.db_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
        assert connection.execute(
            "SELECT sql FROM sqlite_master WHERE name='foreign_data'"
        ).fetchone()[0] == "CREATE TABLE foreign_data (value TEXT)"


def test_newer_schema_version_is_rejected_unchanged(visit_config):
    with sqlite3.connect(visit_config.db_path) as connection:
        connection.execute("CREATE TABLE future_data (value TEXT)")
        connection.execute("PRAGMA user_version=3")
    with pytest.raises(VisitSchemaError, match="newer"):
        VisitRepository(visit_config).initialize()
    with sqlite3.connect(visit_config.db_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 3
        assert connection.execute(
            "SELECT COUNT(*) FROM future_data"
        ).fetchone()[0] == 0


def test_v2_without_ap_mac_check_is_rejected_unchanged(visit_config):
    VisitRepository(visit_config).initialize()
    mac_check = (
        " CHECK (ap_mac IS NULL OR ap_mac GLOB "
        "'[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:"
        "[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:"
        "[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]')"
    )
    modified = _rewrite_source_table_sql(
        visit_config.db_path,
        lambda sql: sql.replace(mac_check, ""),
    )

    with pytest.raises(VisitSchemaError, match="exact contract"):
        VisitRepository(visit_config).initialize()

    with sqlite3.connect(visit_config.db_path) as connection:
        assert connection.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE name='visit_source_events'"
        ).fetchone()[0] == modified


def test_v2_with_changed_numeric_check_is_rejected_unchanged(visit_config):
    VisitRepository(visit_config).initialize()
    modified = _rewrite_source_table_sql(
        visit_config.db_path,
        lambda sql: sql.replace(
            "reported_connected_seconds >= 0",
            "reported_connected_seconds >= -1",
        ),
    )

    with pytest.raises(VisitSchemaError, match="exact contract"):
        VisitRepository(visit_config).initialize()

    with sqlite3.connect(visit_config.db_path) as connection:
        assert connection.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE name='visit_source_events'"
        ).fetchone()[0] == modified


@pytest.mark.parametrize(
    ("name", "statement"),
    [
        ("extra_table", "CREATE TABLE extra_table (id INTEGER)"),
        ("extra_index", "CREATE INDEX extra_index ON visits(site_id)"),
        (
            "extra_view",
            "CREATE VIEW extra_view AS SELECT visit_id FROM visits",
        ),
        (
            "extra_trigger",
            "CREATE TRIGGER extra_trigger AFTER INSERT ON visits "
            "BEGIN SELECT 1; END",
        ),
    ],
)
def test_v2_with_extra_schema_object_is_rejected_unchanged(
    visit_config,
    name,
    statement,
):
    VisitRepository(visit_config).initialize()
    with sqlite3.connect(visit_config.db_path) as connection:
        connection.execute(statement)
        original_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name=?",
            (name,),
        ).fetchone()[0]

    with pytest.raises(VisitSchemaError, match="exact contract"):
        VisitRepository(visit_config).initialize()

    with sqlite3.connect(visit_config.db_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert connection.execute(
            "SELECT sql FROM sqlite_master WHERE name=?",
            (name,),
        ).fetchone()[0] == original_sql


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("ap_mac", "not-a-mac"),
        ("ap_mac", "GG:GG:GG:GG:GG:GG"),
        ("reported_connected_seconds", -1),
        ("reported_connected_seconds", 1.5),
        ("reported_traffic_total_bytes", -1),
        ("reported_traffic_total_bytes", 1.5),
    ],
)
def test_v2_source_context_constraints(visit_repository, column, value):
    with visit_repository._connect() as connection:  # noqa: SLF001
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                f"""
                INSERT INTO visit_source_events (
                    event_id, event_type, source_identity,
                    source_offset_start, source_offset_end,
                    processing_result, first_processed_at, processed_at,
                    {column}
                ) VALUES ('bad:0', 'omada.client_offline', '1:1', 0, 1,
                          'invalid', ?, ?, ?)
                """,
                (
                    "2026-08-13T10:00:00.000Z",
                    "2026-08-13T10:00:00.000Z",
                    value,
                ),
            )
