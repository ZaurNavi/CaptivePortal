from __future__ import annotations

import hashlib
import os
import sqlite3
import stat
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from app.observations.models import (
    ObservationSchemaError,
    ObservationStorageError,
    ObservationValidationError,
    StorageFailureCategory,
)
from app.observations.repository import (
    REQUIRED_INDEXES,
    REQUIRED_TABLES,
    ObservationRepository,
    classify_sqlite_error,
)

from .conftest import ap_row, client_row, make_config, radio_row


def scalar(repository: ObservationRepository, sql: str, params=()):
    with repository.read_connection() as connection:
        return connection.execute(sql, params).fetchone()[0]


def test_schema_v1_tables_indexes_foreign_keys_and_wal(
    observation_config,
):
    repository = ObservationRepository(observation_config)
    initialized = repository.initialize("2026-01-01T00:00:00.000Z")
    assert initialized.created is True
    assert initialized.abandoned_cycles == 0
    with repository.read_connection() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        indexes = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
        }
    assert REQUIRED_TABLES.issubset(tables)
    assert set(REQUIRED_INDEXES).issubset(indexes)
    with sqlite3.connect(observation_config.db_path) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


@pytest.mark.skipif(os.name != "posix", reason="POSIX file mode only")
def test_database_uses_0640_on_posix(observation_config):
    ObservationRepository(observation_config).initialize(
        "2026-01-01T00:00:00.000Z"
    )
    assert stat.S_IMODE(os.stat(observation_config.db_path).st_mode) == 0o640


def test_running_cycle_finalizes_atomically_and_is_immutable(repository):
    running = repository.create_cycle(
        kind="client",
        site_id="site-a",
        started_at="2026-01-01T00:00:00.000Z",
        cycle_id="cycle-1",
    )
    assert running.state == "running"
    assert running.finished_at is None
    with pytest.raises(FrozenInstanceError):
        running.state = "completed"

    completed = repository.finalize_cycle(
        "cycle-1",
        finished_at="2026-01-01T00:01:00.000Z",
        complete=False,
        result="partial",
        source_rows_reported=10,
        items_seen=10,
        items_stored=8,
        items_skipped=2,
        error_count=1,
        data_quality_warning_count=1,
    )
    assert completed.state == "completed"
    assert completed.complete is False
    assert completed.result == "partial"
    with pytest.raises(ObservationValidationError):
        repository.finalize_cycle(
            "cycle-1",
            finished_at="2026-01-01T00:02:00.000Z",
            complete=True,
            result="success",
        )


def test_startup_recovery_abandons_running_without_finished_at(
    observation_config,
):
    first = ObservationRepository(observation_config)
    first.initialize("2026-01-01T00:00:00.000Z")
    first.create_cycle(
        kind="ap_dynamic",
        site_id="site-a",
        started_at="2026-01-01T00:01:00.000Z",
        cycle_id="stale-cycle",
    )

    second = ObservationRepository(observation_config)
    result = second.initialize("2026-01-02T00:00:00.000Z")
    recovered = second.get_cycle("stale-cycle")
    assert result.created is False
    assert result.abandoned_cycles == 1
    assert recovered.state == "abandoned"
    assert recovered.abandoned_at == "2026-01-02T00:00:00.000Z"
    assert recovered.finished_at is None
    assert recovered.complete is False
    assert recovered.result is None


def test_client_idempotency_site_identity_and_atomic_batch(repository):
    repository.create_cycle(
        kind="client",
        site_id="site-a",
        started_at="2026-01-01T00:00:00.000Z",
        cycle_id="clients",
    )
    row = client_row("clients", "2026-01-01T00:00:01.000Z")
    assert repository.insert_client_batch([row]) == 1
    assert repository.insert_client_batch([row]) == 0
    assert scalar(repository, "SELECT COUNT(*) FROM client_observations") == 1

    with pytest.raises(ObservationStorageError) as raised:
        repository.insert_client_batch([
            client_row(
                "clients",
                "2026-01-01T00:00:02.000Z",
                client_mac="AA:BB:CC:DD:EE:02",
            ),
            client_row(
                "clients",
                "2026-01-01T00:00:03.000Z",
                site_id="site-b",
                client_mac="AA:BB:CC:DD:EE:03",
            ),
        ])
    assert raised.value.category == StorageFailureCategory.CONSTRAINT
    assert scalar(repository, "SELECT COUNT(*) FROM client_observations") == 1


def test_observation_rows_require_matching_cycle_kind(repository):
    for cycle_id, kind in (
        ("client-kind", "client"),
        ("dynamic-kind", "ap_dynamic"),
        ("config-kind", "ap_config"),
    ):
        repository.create_cycle(
            kind=kind,
            site_id="site-a",
            started_at="2026-01-01T00:00:00.000Z",
            cycle_id=cycle_id,
        )

    with pytest.raises(ObservationStorageError) as client_error:
        repository.insert_client_batch([
            client_row(
                "dynamic-kind",
                "2026-01-01T00:00:01.000Z",
            )
        ])
    assert client_error.value.category == StorageFailureCategory.CONSTRAINT

    with pytest.raises(ObservationStorageError) as ap_error:
        repository.insert_ap_batch([(
            ap_row(
                "client-kind",
                "2026-01-01T00:00:01.000Z",
            ),
            [],
        )])
    assert ap_error.value.category == StorageFailureCategory.CONSTRAINT

    config_json = '{"name":"AP-1"}'
    with pytest.raises(ObservationStorageError) as config_error:
        repository.insert_ap_config_batch([{
            "cycle_id": "dynamic-kind",
            "captured_at": "2026-01-01T00:00:01.000Z",
            "site_id": "site-a",
            "ap_mac": "10:20:30:40:50:60",
            "config_sha256": hashlib.sha256(
                config_json.encode()
            ).hexdigest(),
            "schema_version": 1,
            "config_json": config_json,
        }])
    assert config_error.value.category == StorageFailureCategory.CONSTRAINT

    assert scalar(repository, "SELECT COUNT(*) FROM client_observations") == 0
    assert scalar(repository, "SELECT COUNT(*) FROM ap_observations") == 0
    assert scalar(repository, "SELECT COUNT(*) FROM ap_config_snapshots") == 0


def test_ap_radio_uniqueness_and_cycle_cascade(repository):
    repository.create_cycle(
        kind="ap_dynamic",
        site_id="site-a",
        started_at="2026-01-01T00:00:00.000Z",
        cycle_id="aps",
    )
    entry = (
        ap_row("aps", "2026-01-01T00:00:01.000Z"),
        [
            radio_row("2026-01-01T00:00:01.100Z", band="2.4GHz"),
            radio_row("2026-01-01T00:00:01.100Z", band="5GHz"),
        ],
    )
    assert repository.insert_ap_batch([entry]) == (1, 2)
    assert repository.insert_ap_batch([entry]) == (0, 0)
    repository.finalize_cycle(
        "aps",
        finished_at="2026-01-01T00:01:00.000Z",
        complete=True,
        result="success",
    )
    assert repository.delete_expired_cycles(
        kinds=("ap_dynamic",),
        cutoff_utc="2026-01-02T00:00:00.000Z",
        limit=10,
    ) == 1
    assert scalar(repository, "SELECT COUNT(*) FROM ap_observations") == 0
    assert scalar(repository, "SELECT COUNT(*) FROM ap_radio_observations") == 0


def test_complete_config_is_change_only_across_cycles(repository):
    config_json = '{"name":"AP-1"}'
    digest = hashlib.sha256(config_json.encode("utf-8")).hexdigest()
    for identifier, timestamp in (
        ("config-1", "2026-01-01T00:00:00.000Z"),
        ("config-2", "2026-01-02T00:00:00.000Z"),
    ):
        repository.create_cycle(
            kind="ap_config",
            site_id="site-a",
            started_at=timestamp,
            cycle_id=identifier,
        )
        inserted = repository.insert_ap_config_batch([{
            "cycle_id": identifier,
            "captured_at": timestamp,
            "site_id": "site-a",
            "ap_mac": "10:20:30:40:50:60",
            "config_sha256": digest,
            "schema_version": 1,
            "config_json": config_json,
        }])
        assert inserted == (1 if identifier == "config-1" else 0)
    assert scalar(repository, "SELECT COUNT(*) FROM ap_config_snapshots") == 1


@pytest.mark.parametrize(
    ("payload", "digest"),
    [
        ('{"b":2,"a":1}', None),
        ('{"name":"first","name":"second"}', None),
        ('{"value":NaN}', None),
        ('[]', None),
        ('{"name":"AP-1"}', "0" * 64),
    ],
)
def test_config_requires_canonical_strict_json_and_matching_hash(
    repository,
    payload,
    digest,
):
    repository.create_cycle(
        kind="ap_config",
        site_id="site-a",
        started_at="2026-01-01T00:00:00.000Z",
        cycle_id=f"invalid-config-{hash(payload)}",
    )
    actual_digest = digest or hashlib.sha256(payload.encode()).hexdigest()
    with pytest.raises(ObservationValidationError):
        repository.insert_ap_config_batch([{
            "cycle_id": f"invalid-config-{hash(payload)}",
            "captured_at": "2026-01-01T00:00:00.000Z",
            "site_id": "site-a",
            "ap_mac": "10:20:30:40:50:60",
            "config_sha256": actual_digest,
            "schema_version": 1,
            "config_json": payload,
        }])


def test_newer_partial_and_corrupt_databases_are_preserved(tmp_path: Path):
    config = make_config(tmp_path)
    with sqlite3.connect(config.db_path) as connection:
        connection.execute("PRAGMA user_version=2")
    with pytest.raises(ObservationSchemaError):
        ObservationRepository(config).initialize(
            "2026-01-01T00:00:00.000Z"
        )
    assert Path(config.db_path).exists()

    partial = make_config(tmp_path, db_path=str(tmp_path / "data" / "partial.db"))
    with sqlite3.connect(partial.db_path) as connection:
        connection.execute("CREATE TABLE observation_cycles (cycle_id TEXT)")
    with pytest.raises(ObservationSchemaError):
        ObservationRepository(partial).initialize(
            "2026-01-01T00:00:00.000Z"
        )
    assert Path(partial.db_path).exists()

    corrupt = make_config(tmp_path, db_path=str(tmp_path / "data" / "corrupt.db"))
    Path(corrupt.db_path).write_bytes(b"not a sqlite database")
    with pytest.raises(ObservationStorageError) as raised:
        ObservationRepository(corrupt).initialize(
            "2026-01-01T00:00:00.000Z"
        )
    assert raised.value.category == StorageFailureCategory.CORRUPT
    assert Path(corrupt.db_path).read_bytes() == b"not a sqlite database"


def test_startup_detects_missing_required_index(observation_config):
    repository = ObservationRepository(observation_config)
    repository.initialize("2026-01-01T00:00:00.000Z")
    with sqlite3.connect(observation_config.db_path) as connection:
        connection.execute("DROP INDEX idx_client_site_time")
    with pytest.raises(ObservationSchemaError):
        repository.initialize("2026-01-02T00:00:00.000Z")


def test_initialize_does_not_run_full_integrity_scan(
    observation_config,
    monkeypatch,
):
    repository = ObservationRepository(observation_config)

    def fail_if_called(connection):
        raise AssertionError("full integrity scan entered startup path")

    monkeypatch.setattr(repository, "_integrity_check", fail_if_called)
    initialized = repository.initialize("2026-01-01T00:00:00.000Z")

    assert initialized.created is True
    with pytest.raises(AssertionError, match="full integrity scan"):
        repository.validate_runtime_health()


def test_runtime_health_scan_honors_interrupt_callback(
    repository,
    monkeypatch,
):
    def expensive_scan(connection):
        connection.execute(
            """
            WITH RECURSIVE sequence(value) AS (
                SELECT 1
                UNION ALL
                SELECT value + 1 FROM sequence WHERE value < 1000000
            )
            SELECT sum(value) FROM sequence
            """
        ).fetchone()

    monkeypatch.setattr(repository, "_integrity_check", expensive_scan)

    assert repository.validate_runtime_health(
        should_interrupt=lambda: True
    ) is False


def test_strict_fixed_width_utc_and_nonfinite_values_are_rejected(repository):
    with pytest.raises(ObservationValidationError):
        repository.create_cycle(
            kind="client",
            site_id="site-a",
            started_at="2026-01-01T00:00:00Z",
        )
    repository.create_cycle(
        kind="ap_dynamic",
        site_id="site-a",
        started_at="2026-01-01T00:00:00.000Z",
        cycle_id="finite",
    )
    with pytest.raises(ObservationValidationError):
        repository.insert_ap_batch([(
            ap_row(
                "finite",
                "2026-01-01T00:00:01.000Z",
                cpu_util=float("nan"),
            ),
            [],
        )])


def test_rate_baselines_use_latest_completed_partial_cycle_and_ignore_running(repository):
    repository.create_cycle(
        kind="ap_dynamic", site_id="site-a",
        started_at="2026-01-01T00:00:00.000Z", cycle_id="baseline",
    )
    repository.insert_ap_batch([(
        ap_row(
            "baseline", "2026-01-01T00:00:10.000Z",
            wired_observed_at="2026-01-01T00:00:10.000Z",
            wired_down_bytes=100,
        ),
        [radio_row("2026-01-01T00:00:11.000Z", band="5g", rx_bytes=200)],
    )])
    repository.finalize_cycle(
        "baseline", finished_at="2026-01-01T00:00:12.000Z",
        complete=False, result="partial",
    )
    repository.create_cycle(
        kind="ap_dynamic", site_id="site-a",
        started_at="2026-01-01T00:01:00.000Z", cycle_id="running",
    )
    repository.insert_ap_batch([(
        ap_row(
            "running", "2026-01-01T00:01:10.000Z",
            wired_observed_at="2026-01-01T00:01:10.000Z",
            wired_down_bytes=999,
        ),
        [radio_row("2026-01-01T00:01:11.000Z", band="5g", rx_bytes=999)],
    )])

    assert repository.get_latest_ap_rate_sample(
        site_id="site-a", ap_mac="10:20:30:40:50:60",
        timestamp_column="wired_observed_at", counter_column="wired_down_bytes",
    ) == ("2026-01-01T00:00:10.000Z", 100)
    assert repository.get_latest_radio_rate_sample(
        site_id="site-a", ap_mac="10:20:30:40:50:60",
        band="5g", counter_column="rx_bytes",
    ) == ("2026-01-01T00:00:11.000Z", 200)


def test_latest_config_hash_requires_completed_and_complete_cycle(repository):
    def insert_config(cycle_id, captured_at, payload):
        digest = hashlib.sha256(payload.encode()).hexdigest()
        repository.insert_ap_config_batch([{
            "cycle_id": cycle_id,
            "captured_at": captured_at,
            "site_id": "site-a",
            "ap_mac": "10:20:30:40:50:60",
            "config_sha256": digest,
            "schema_version": 1,
            "config_json": payload,
        }])
        return digest

    repository.create_cycle(
        kind="ap_config", site_id="site-a",
        started_at="2026-01-01T00:00:00.000Z", cycle_id="partial-config",
    )
    insert_config("partial-config", "2026-01-01T00:00:01.000Z", '{"value":1}')
    repository.finalize_cycle(
        "partial-config", finished_at="2026-01-01T00:00:02.000Z",
        complete=False, result="partial",
    )
    assert repository.get_latest_complete_config_hash(
        site_id="site-a", ap_mac="10:20:30:40:50:60"
    ) is None

    repository.create_cycle(
        kind="ap_config", site_id="site-a",
        started_at="2026-01-01T00:01:00.000Z", cycle_id="complete-config",
    )
    expected = insert_config(
        "complete-config", "2026-01-01T00:01:01.000Z", '{"value":2}'
    )
    repository.finalize_cycle(
        "complete-config", finished_at="2026-01-01T00:01:02.000Z",
        complete=True, result="success",
    )
    assert repository.get_latest_complete_config_hash(
        site_id="site-a", ap_mac="10:20:30:40:50:60"
    ) == expected


class ErrorWithCode(sqlite3.OperationalError):
    def __init__(self, code: int):
        super().__init__("sanitized")
        self.sqlite_errorcode = code


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (5, StorageFailureCategory.BUSY),
        (6, StorageFailureCategory.BUSY),
        (261, StorageFailureCategory.BUSY),
        (13, StorageFailureCategory.FULL),
        (10, StorageFailureCategory.IO_ERROR),
        (11, StorageFailureCategory.CORRUPT),
        (26, StorageFailureCategory.CORRUPT),
        (8, StorageFailureCategory.UNAVAILABLE),
        (14, StorageFailureCategory.UNAVAILABLE),
        (19, StorageFailureCategory.CONSTRAINT),
    ],
)
def test_sqlite_primary_code_classification(code, expected):
    assert classify_sqlite_error(ErrorWithCode(code)) == expected


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("database is locked", StorageFailureCategory.BUSY),
        ("database or disk is full", StorageFailureCategory.FULL),
        ("disk I/O error", StorageFailureCategory.IO_ERROR),
        (
            "database disk image is malformed",
            StorageFailureCategory.CORRUPT,
        ),
        (
            "attempt to write a readonly database",
            StorageFailureCategory.UNAVAILABLE,
        ),
        ("constraint failed", StorageFailureCategory.CONSTRAINT),
        ("client cycle identity mismatch", StorageFailureCategory.CONSTRAINT),
        ("ap cycle identity mismatch", StorageFailureCategory.CONSTRAINT),
        ("radio parent identity mismatch", StorageFailureCategory.CONSTRAINT),
        ("config cycle identity mismatch", StorageFailureCategory.CONSTRAINT),
    ],
)
def test_classification_without_python311_error_code(message, expected):
    error = sqlite3.OperationalError(message)
    assert getattr(error, "sqlite_errorcode", None) is None
    assert classify_sqlite_error(error) == expected
