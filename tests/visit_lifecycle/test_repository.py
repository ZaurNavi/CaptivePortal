from __future__ import annotations

import os
import sqlite3
import threading
import uuid
from dataclasses import FrozenInstanceError, replace

import pytest

from app.visit_lifecycle import (
    SCHEMA_VERSION,
    VisitLifecycleService,
    VisitRepository,
    VisitSchemaError,
    VisitStorageCategory,
    VisitStorageError,
    VisitTelemetry,
    VisitValidationError,
)
from app.visit_lifecycle.models import normalize_start_request
from app.visit_lifecycle.repository import (
    REQUIRED_INDEXES,
    REQUIRED_TABLES,
    classify_sqlite_error,
)

from .conftest import config_with, make_request


def _connection(repository):
    return repository._connect()  # noqa: SLF001


def _close_visit(repository, visit_id, *, event_id="offline:0"):
    with _connection(repository) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO visit_source_events (
                event_id, event_type, site_id, client_mac,
                controller_event_at, received_at, source_identity,
                source_offset_start, source_offset_end, processing_result,
                visit_id, reason, first_processed_at, processed_at
            ) VALUES (?, 'omada.client_offline', 'site-a',
                      '02:11:22:33:44:55', ?, ?, 'dev:inode',
                      0, 100, 'closed', ?, NULL, ?, ?)
            """,
            (
                event_id,
                "2026-08-13T10:05:00.000Z",
                "2026-08-13T10:05:01.000Z",
                visit_id,
                "2026-08-13T10:05:02.000Z",
                "2026-08-13T10:05:02.000Z",
            ),
        )
        connection.execute(
            """
            UPDATE visits SET status='closed', closed_at=?,
                close_reason='omada_client_offline',
                close_time_source='controller_timestamp',
                duration_seconds=300, offline_event_id=?, updated_at=?
            WHERE visit_id=?
            """,
            (
                "2026-08-13T10:05:00.000Z",
                event_id,
                "2026-08-13T10:05:02.000Z",
                visit_id,
            ),
        )
        connection.commit()


def test_schema_version_tables_indexes_foreign_keys_and_query_plan(
    visit_repository,
):
    with _connection(visit_repository) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == (
            SCHEMA_VERSION
        )
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert REQUIRED_TABLES <= tables
        indexes = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
        }
        assert set(REQUIRED_INDEXES) <= indexes
        auth_fks = connection.execute(
            "PRAGMA foreign_key_list(visit_authorizations)"
        ).fetchall()
        event_fks = connection.execute(
            "PRAGMA foreign_key_list(visit_source_events)"
        ).fetchall()
        visit_fks = connection.execute(
            "PRAGMA foreign_key_list(visits)"
        ).fetchall()
        assert any(row[2:7] == (
            "visits", "visit_id", "visit_id", "NO ACTION", "CASCADE"
        ) for row in auth_fks)
        assert any(row[2:7] == (
            "visits", "visit_id", "visit_id", "NO ACTION", "SET NULL"
        ) for row in event_fks)
        assert any(row[2:7] == (
            "visit_source_events", "offline_event_id", "event_id",
            "NO ACTION", "SET NULL",
        ) for row in visit_fks)
        ssid_plan = " ".join(
            str(row[3])
            for row in connection.execute(
                "EXPLAIN QUERY PLAN SELECT 1 FROM visit_authorizations "
                "WHERE visit_id=? AND portal_ssid=?",
                ("x", "s"),
            )
        )
        ap_plan = " ".join(
            str(row[3])
            for row in connection.execute(
                "EXPLAIN QUERY PLAN SELECT 1 FROM visit_authorizations "
                "WHERE visit_id=? AND portal_ap_mac=?",
                ("x", "02:AA:BB:CC:DD:EE"),
            )
        )
        assert "idx_visit_auth_visit_ssid" in ssid_plan
        assert "idx_visit_auth_visit_ap" in ap_plan


@pytest.mark.skipif(os.name != "posix", reason="POSIX file mode contract")
def test_visit_database_uses_0640_on_posix(visit_repository):
    assert os.stat(visit_repository.db_path).st_mode & 0o777 == 0o640


def test_new_repeat_and_duplicate_start_contract(visit_service, visit_repository):
    first_request = make_request()
    first = visit_service.submit_authorized(first_request)
    assert first.status == "opened"
    assert first.created is True
    assert str(uuid.UUID(first.visit_id)) == first.visit_id
    visit = visit_repository.get_visit("site-a", first.visit_id)
    assert visit.started_at == "2026-08-13T10:00:00.000Z"
    assert visit.start_auth_session_id == first_request.auth_session_id
    assert visit.start_auth_run_number == 1

    repeated = visit_service.submit_authorized(make_request(auth_run_number=2))
    assert repeated.status == "reused"
    assert repeated.visit_id == first.visit_id
    assert visit_repository.authorization_count(first.visit_id) == 2
    with _connection(visit_repository) as connection:
        radio_id = connection.execute(
            "SELECT portal_radio_id FROM visit_authorizations "
            "WHERE auth_session_id=?",
            (first_request.auth_session_id,),
        ).fetchone()[0]
    assert radio_id == 0
    unchanged = visit_repository.get_visit("site-a", first.visit_id)
    assert unchanged.started_at == visit.started_at
    assert unchanged.start_auth_session_id == visit.start_auth_session_id

    duplicate = visit_service.submit_authorized(first_request)
    assert duplicate.status == "duplicate"
    assert duplicate.visit_id == first.visit_id
    assert visit_repository.authorization_count(first.visit_id) == 2


def test_start_requires_canonical_auth_session_uuid(visit_service):
    with pytest.raises(VisitValidationError, match="auth_session_id"):
        visit_service.submit_authorized(
            make_request(auth_session_id="not-a-session-uuid")
        )


def test_replayed_authorization_linked_to_closed_visit_creates_no_open(
    visit_service,
    visit_repository,
):
    request = make_request()
    opened = visit_service.submit_authorized(request)
    _close_visit(visit_repository, opened.visit_id)
    replay = visit_service.submit_authorized(request)
    assert replay.status == "duplicate"
    assert replay.visit_id == opened.visit_id
    assert visit_repository.get_open_visit(
        "site-a", "02:11:22:33:44:55"
    ) is None


def test_same_mac_in_different_sites_creates_distinct_visits(visit_service):
    a = visit_service.submit_authorized(make_request(site_id="site-a"))
    b = visit_service.submit_authorized(make_request(site_id="site-b"))
    assert a.visit_id != b.visit_id


def test_concurrent_start_has_one_open_visit(visit_config):
    first_repo = VisitRepository(visit_config)
    second_repo = VisitRepository(visit_config)
    first_repo.initialize()
    first = VisitLifecycleService(
        first_repo, VisitTelemetry(__import__("logging").getLogger("first"))
    )
    second = VisitLifecycleService(
        second_repo, VisitTelemetry(__import__("logging").getLogger("second"))
    )
    barrier = threading.Barrier(2)
    results = []

    def submit(service):
        barrier.wait()
        results.append(service.submit_authorized(make_request()))

    threads = [
        threading.Thread(target=submit, args=(first,)),
        threading.Thread(target=submit, args=(second,)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(results) == 2
    assert len({item.visit_id for item in results}) == 1
    assert sorted(item.status for item in results) == ["opened", "reused"]


def test_local_write_slot_wait_is_bounded(visit_config):
    visit_config = replace(visit_config, start_writer_slot_wait_ms=25)
    repository = VisitRepository(visit_config)
    repository.initialize()
    acquired = threading.Event()
    release = threading.Event()

    def hold_write_slot():
        with repository._bounded_write("reader"):  # noqa: SLF001
            acquired.set()
            release.wait(2)

    holder = threading.Thread(target=hold_write_slot)
    holder.start()
    assert acquired.wait(1)
    try:
        with pytest.raises(VisitStorageError) as error:
            repository.create_or_reuse_start(
                normalize_start_request(make_request()),
                now_utc="2026-08-13T10:00:00.000Z",
            )
        assert error.value.category is VisitStorageCategory.BUSY
    finally:
        release.set()
        holder.join(1)


def test_database_enforces_open_unique_and_immutable_start_evidence(
    visit_service,
    visit_repository,
):
    opened = visit_service.submit_authorized(make_request())
    with _connection(visit_repository) as connection:
        row = connection.execute(
            "SELECT * FROM visits WHERE visit_id=?", (opened.visit_id,)
        ).fetchone()
        values = dict(row)
        values["visit_id"] = str(uuid.uuid4())
        values["start_auth_session_id"] = str(uuid.uuid4())
        columns = ",".join(values)
        placeholders = ",".join("?" for _ in values)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                f"INSERT INTO visits ({columns}) VALUES ({placeholders})",
                tuple(values.values()),
            )
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE visits SET start_final_reason='CHANGED' WHERE visit_id=?",
                (opened.visit_id,),
            )


def test_offline_event_fk_unique_and_authorization_cascade(
    visit_service,
    visit_repository,
):
    opened = visit_service.submit_authorized(make_request())
    with _connection(visit_repository) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE visits SET offline_event_id='missing' WHERE visit_id=?",
                (opened.visit_id,),
            )
        connection.execute("DELETE FROM visits WHERE visit_id=?", (opened.visit_id,))
        assert connection.execute(
            "SELECT COUNT(*) FROM visit_authorizations WHERE visit_id=?",
            (opened.visit_id,),
        ).fetchone()[0] == 0


def test_offline_event_delete_uses_required_set_null_action(
    visit_service,
    visit_repository,
):
    opened = visit_service.submit_authorized(make_request())
    _close_visit(visit_repository, opened.visit_id)
    with _connection(visit_repository) as connection:
        connection.execute(
            "DELETE FROM visit_source_events WHERE event_id='offline:0'"
        )
        row = connection.execute(
            "SELECT status, offline_event_id FROM visits WHERE visit_id=?",
            (opened.visit_id,),
        ).fetchone()
    assert tuple(row) == ("closed", None)


def test_visit_dto_is_immutable(visit_service, visit_repository):
    opened = visit_service.submit_authorized(make_request())
    visit = visit_repository.get_visit("site-a", opened.visit_id)
    with pytest.raises(FrozenInstanceError):
        visit.status = "closed"


def test_newer_and_corrupt_database_are_preserved(visit_config):
    path = visit_config.db_path
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version=99")
    with pytest.raises(VisitSchemaError, match="newer"):
        VisitRepository(visit_config).initialize()
    assert os.path.exists(path)

    corrupt_config = config_with(
        visit_config,
        db_path=str(visit_config.db_path) + ".corrupt",
    )
    path = corrupt_config.db_path
    original = b"not-a-sqlite-database"
    with open(path, "wb") as output:
        output.write(original)
    with pytest.raises(VisitStorageError) as error:
        VisitRepository(corrupt_config).initialize()
    assert error.value.category is VisitStorageCategory.CORRUPT
    with open(path, "rb") as source:
        assert source.read() == original


def test_partial_or_modified_schema_is_rejected_without_recreation(
    visit_config,
):
    partial_config = config_with(
        visit_config,
        db_path=str(visit_config.db_path) + ".partial",
    )
    with sqlite3.connect(partial_config.db_path) as connection:
        connection.execute("CREATE TABLE visits (visit_id TEXT)")
    with pytest.raises(VisitSchemaError, match="non-empty"):
        VisitRepository(partial_config).initialize()
    with sqlite3.connect(partial_config.db_path) as connection:
        assert connection.execute(
            "SELECT sql FROM sqlite_master WHERE name='visits'"
        ).fetchone()[0] == "CREATE TABLE visits (visit_id TEXT)"

    unrelated_config = config_with(
        visit_config,
        db_path=str(visit_config.db_path) + ".unrelated",
    )
    with sqlite3.connect(unrelated_config.db_path) as connection:
        connection.execute("CREATE TABLE unrelated_application_data (id INTEGER)")
    with pytest.raises(VisitSchemaError, match="non-empty"):
        VisitRepository(unrelated_config).initialize()
    with sqlite3.connect(unrelated_config.db_path) as connection:
        user_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
    assert user_tables == {"unrelated_application_data"}

    repository = VisitRepository(visit_config)
    repository.initialize()
    with sqlite3.connect(visit_config.db_path) as connection:
        connection.execute("DROP INDEX idx_visits_site_started")
    with pytest.raises(VisitSchemaError, match="index"):
        repository.initialize()


def test_existing_nonregular_database_target_is_rejected(visit_config):
    directory_config = config_with(
        visit_config,
        db_path=str(visit_config.db_path) + ".directory",
    )
    os.mkdir(directory_config.db_path)
    with pytest.raises(VisitStorageError) as error:
        VisitRepository(directory_config).initialize()
    assert error.value.category is VisitStorageCategory.UNAVAILABLE


@pytest.mark.skipif(os.name != "posix", reason="POSIX symlink contract")
def test_existing_database_symlink_is_rejected(visit_config):
    target = str(visit_config.db_path) + ".target"
    with sqlite3.connect(target):
        pass
    os.symlink(target, visit_config.db_path)
    with pytest.raises(VisitStorageError) as error:
        VisitRepository(visit_config).initialize()
    assert error.value.category is VisitStorageCategory.UNAVAILABLE


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("database is locked", VisitStorageCategory.BUSY),
        ("database or disk is full", VisitStorageCategory.FULL),
        ("database disk image is malformed", VisitStorageCategory.CORRUPT),
    ],
)
def test_storage_error_classification(message, expected):
    assert classify_sqlite_error(sqlite3.OperationalError(message)) is expected
