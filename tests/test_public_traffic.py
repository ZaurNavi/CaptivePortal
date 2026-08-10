import json
import logging
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
import run as run_module

from app.portal_counter import (
    PortalCounterRepository,
    PortalCounterService,
)
from app.public_traffic.cli import main as cli_main
from app.public_traffic.models import (
    INT64_MAX,
    BackfillIncompleteError,
    PublicTrafficConfig,
    PublicTrafficConfigError,
    TrafficEvent,
)
from app.public_traffic.reader import PublicTrafficReader
from app.public_traffic.repository import PublicTrafficRepository
from app.public_traffic.service import (
    PublicTrafficService,
    format_traffic_bytes,
)
from app.public_traffic.worker import PublicTrafficWorker
from app.web import web as web_module


UTC = timezone.utc
NOW = datetime(2026, 7, 29, 8, 0, tzinfo=UTC)


class MutableClock:
    def __init__(self, value=NOW):
        self.value = value

    def __call__(self):
        return self.value


def config(tmp_path, **overrides):
    values = {
        "public_traffic_counter_enabled": True,
        "public_traffic_ssid": "Zefer_Parki",
        "public_traffic_db_path": str(tmp_path / "traffic.db"),
        "omada_webhook_normalized_log_file": str(
            tmp_path / "normalized.log"
        ),
        "portal_counter_timezone": "Asia/Baku",
        "public_traffic_scan_interval_seconds": 10,
        "public_traffic_frontend_refresh_seconds": 60,
    }
    values.update(overrides)
    return PublicTrafficConfig.from_settings(values)


def stack(tmp_path, **overrides):
    selected_config = config(tmp_path, **overrides)
    repository = PublicTrafficRepository(selected_config.db_path)
    clock = MutableClock()
    logger = logging.getLogger(f"public-traffic-{id(tmp_path)}")
    service = PublicTrafficService(
        config=selected_config,
        repository=repository,
        logger=logger,
        clock=clock,
    )
    assert service.initialize()
    reader = PublicTrafficReader(
        source_path=selected_config.source_log_path,
        repository=repository,
        service=service,
        logger=logger,
    )
    worker = PublicTrafficWorker(
        reader=reader,
        repository=repository,
        service=service,
        logger=logger,
        scan_interval_seconds=10,
    )
    return selected_config, repository, service, reader, worker, clock


def offline(
    event_id,
    *,
    ssid="Zefer_Parki",
    traffic=1024**3,
    parse_status="parsed",
    controller_timestamp="2026-07-29T07:30:00.000Z",
    received_at="2026-07-29T07:30:01.000Z",
):
    return {
        "event": "omada.client_offline",
        "normalized_event_id": event_id,
        "ssid": ssid,
        "reported_traffic_bytes_estimate": traffic,
        "parse_status": parse_status,
        "controller_timestamp": controller_timestamp,
        "received_at": received_at,
    }


def append_lines(path, records, *, newline=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as stream:
        for index, record in enumerate(records):
            if isinstance(record, bytes):
                encoded = record
            else:
                encoded = json.dumps(
                    record,
                    separators=(",", ":"),
                ).encode("utf-8")
            stream.write(encoded)
            if newline or index < len(records) - 1:
                stream.write(b"\n")


def table_rows(db_path, table):
    with closing(sqlite3.connect(db_path)) as connection:
        return connection.execute(
            f"SELECT * FROM {table}"
        ).fetchall()


def complete_backfill(worker):
    worker.run_once()
    assert worker.repository.initial_backfill_completed()


@pytest.mark.parametrize("parse_status", ["parsed", "partial"])
def test_valid_offline_is_counted_regardless_of_parse_status(
    tmp_path,
    parse_status,
):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [offline("event-1", parse_status=parse_status)],
    )

    complete_backfill(worker)
    snapshot = service.get_snapshot()

    assert snapshot.available
    assert snapshot.today_bytes == 1024**3
    assert snapshot.total_bytes == 1024**3
    assert snapshot.completed_sessions_today == 1
    assert snapshot.completed_sessions_total == 1
    assert len(table_rows(repository.db_path, "processed_events")) == 1


def test_multiple_ssids_are_aggregated_separately(tmp_path):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [
            offline("z-1", traffic=100),
            offline("w-1", ssid="Welcome", traffic=250),
            offline("z-2", traffic=50),
        ],
    )

    complete_backfill(worker)

    assert service.get_snapshot().total_bytes == 150
    welcome = repository.get_snapshot(
        ssid="Welcome",
        local_date=service.local_date(),
    )
    assert welcome.total_bytes == 250
    assert welcome.completed_sessions_total == 1


def test_zero_traffic_counts_completed_session_and_updates_time(
    tmp_path,
):
    selected, _, service, _, worker, _ = stack(tmp_path)
    append_lines(selected.source_log_path, [offline("zero", traffic=0)])

    complete_backfill(worker)
    snapshot = service.get_snapshot()

    assert snapshot.total_bytes == 0
    assert snapshot.completed_sessions_total == 1
    assert snapshot.updated_at == "2026-07-29T08:00:00.000Z"


@pytest.mark.parametrize(
    "traffic",
    [True, 1.0, "1", None, -1, INT64_MAX + 1],
)
def test_invalid_traffic_is_finally_skipped(tmp_path, traffic):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [offline("invalid", traffic=traffic)],
    )

    complete_backfill(worker)
    snapshot = service.get_snapshot()
    rows = table_rows(repository.db_path, "processed_events")

    assert snapshot.total_bytes == 0
    assert snapshot.completed_sessions_total == 0
    assert len(rows) == 1
    assert rows[0][5] == 0
    assert rows[0][6] == "invalid_traffic_value"


def test_int64_max_is_allowed(tmp_path):
    selected, _, service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [offline("max", traffic=INT64_MAX)],
    )

    complete_backfill(worker)

    assert service.get_snapshot().total_bytes == INT64_MAX


def test_daily_overflow_is_finally_skipped_and_offset_advances(
    tmp_path,
):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [
            offline("max", traffic=INT64_MAX),
            offline("overflow", traffic=1),
        ],
    )

    complete_backfill(worker)
    rows = table_rows(repository.db_path, "processed_events")
    states = repository.get_reader_states()

    assert service.get_snapshot().total_bytes == INT64_MAX
    assert rows[1][5] == 0
    assert rows[1][6] == "aggregate_overflow"
    assert next(iter(states.values())).source_offset == Path(
        selected.source_log_path
    ).stat().st_size


def test_total_across_days_cannot_overflow(tmp_path):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [
            offline(
                "day-1",
                traffic=INT64_MAX,
                controller_timestamp="2026-07-28T07:00:00Z",
            ),
            offline(
                "day-2",
                traffic=1,
                controller_timestamp="2026-07-29T07:00:00Z",
            ),
        ],
    )

    complete_backfill(worker)
    rows = table_rows(repository.db_path, "processed_events")

    assert service.get_snapshot().total_bytes == INT64_MAX
    assert rows[1][6] == "aggregate_overflow"


def test_duplicate_does_not_change_totals_but_advances_new_inode(
    tmp_path,
):
    selected, repository, service, reader, worker, _ = stack(tmp_path)
    active = Path(selected.source_log_path)
    append_lines(active, [offline("same", traffic=100)])
    complete_backfill(worker)

    active.rename(Path(f"{active}.1"))
    append_lines(active, [offline("same", traffic=100)])
    reader.scan()

    assert service.get_snapshot().total_bytes == 100
    states = repository.get_reader_states()
    active_identity = f"{active.stat().st_dev}:{active.stat().st_ino}"
    assert states[active_identity].source_offset == active.stat().st_size
    assert len(table_rows(repository.db_path, "processed_events")) == 1


@pytest.mark.parametrize(
    "event_name",
    [
        "omada.client_online",
        "omada.client_authentication_expired",
    ],
)
def test_non_target_events_advance_without_processed_event(
    tmp_path,
    event_name,
):
    selected, repository, _, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [{
            "event": event_name,
            "normalized_event_id": "ignored-1",
        }],
    )

    complete_backfill(worker)

    assert table_rows(repository.db_path, "processed_events") == []
    state = next(iter(repository.get_reader_states().values()))
    assert state.source_offset == Path(
        selected.source_log_path
    ).stat().st_size


@pytest.mark.parametrize("invalid_ssid", [None, "", "   "])
def test_invalid_offline_ssid_is_stored_as_skipped(
    tmp_path,
    invalid_ssid,
):
    selected, repository, _, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [offline("missing-ssid", ssid=invalid_ssid)],
    )

    complete_backfill(worker)
    row = table_rows(repository.db_path, "processed_events")[0]

    assert row[1] is None
    assert row[5] == 0
    assert row[6] == "missing_ssid"


def test_missing_event_id_warns_and_only_advances_offset(
    tmp_path,
    caplog,
):
    selected, repository, _, _, worker, _ = stack(tmp_path)
    record = offline("")
    append_lines(selected.source_log_path, [record])

    with caplog.at_level(logging.WARNING):
        complete_backfill(worker)

    assert table_rows(repository.db_path, "processed_events") == []
    assert "missing_normalized_event_id" in caplog.text
    state = next(iter(repository.get_reader_states().values()))
    assert state.source_offset == Path(
        selected.source_log_path
    ).stat().st_size


def test_controller_timestamp_precedes_received_at(tmp_path):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [offline(
            "time",
            controller_timestamp="2026-07-28T19:59:59Z",
            received_at="2026-07-28T20:00:01Z",
        )],
    )

    complete_backfill(worker)

    previous_day = repository.get_snapshot(
        ssid="Zefer_Parki",
        local_date="2026-07-28",
    )
    assert previous_day.today_bytes == 1024**3
    assert service.get_snapshot().today_bytes == 0


def test_invalid_controller_uses_received_at(tmp_path):
    selected, repository, _, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [offline(
            "received",
            controller_timestamp="invalid",
            received_at="2026-07-28T20:00:00Z",
        )],
    )

    complete_backfill(worker)

    snapshot = repository.get_snapshot(
        ssid="Zefer_Parki",
        local_date="2026-07-29",
    )
    assert snapshot.today_bytes == 1024**3


@pytest.mark.parametrize(
    "extreme_controller_timestamp",
    [
        "0001-01-01T00:00:00+14:00",
        "9999-12-31T23:59:59-14:00",
    ],
)
def test_extreme_controller_timestamp_uses_received_at_and_advances(
    tmp_path,
    extreme_controller_timestamp,
):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [offline(
            "extreme-controller",
            traffic=7,
            controller_timestamp=extreme_controller_timestamp,
            received_at="2026-07-29T07:30:01Z",
        )],
    )

    complete_backfill(worker)

    assert service.get_snapshot().total_bytes == 7
    assert len(table_rows(repository.db_path, "processed_events")) == 1
    state = next(iter(repository.get_reader_states().values()))
    assert state.source_offset == Path(
        selected.source_log_path
    ).stat().st_size


def test_extreme_controller_and_received_timestamps_use_clock(
    tmp_path,
    caplog,
):
    selected, _, service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [offline(
            "extreme-clock-fallback",
            traffic=9,
            controller_timestamp="0001-01-01T00:00:00+14:00",
            received_at="9999-12-31T23:59:59-14:00",
        )],
    )

    with caplog.at_level(logging.WARNING):
        complete_backfill(worker)

    assert service.get_snapshot().total_bytes == 9
    assert "public_traffic_timestamp_fallback" in caplog.text


def test_last_timestamp_fallback_warns_and_counts(tmp_path, caplog):
    selected, _, service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [offline(
            "fallback",
            controller_timestamp=None,
            received_at="invalid",
        )],
    )

    with caplog.at_level(logging.WARNING):
        complete_backfill(worker)

    assert service.get_snapshot().today_bytes == 1024**3
    assert "public_traffic_timestamp_fallback" in caplog.text


def test_incomplete_line_waits_for_newline_and_backfill_stays_false(
    tmp_path,
):
    selected, repository, service, reader, worker, _ = stack(tmp_path)
    active = Path(selected.source_log_path)
    append_lines(
        active,
        [offline("partial")],
        newline=False,
    )

    worker.run_once()

    assert not repository.initial_backfill_completed()
    assert table_rows(repository.db_path, "processed_events") == []
    with active.open("ab") as stream:
        stream.write(b"\n")
    worker.run_once()

    assert repository.initial_backfill_completed()
    assert service.get_snapshot().total_bytes == 1024**3
    assert reader.scan()


def test_invalid_json_advances_and_next_line_is_counted(
    tmp_path,
    caplog,
):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [b'{"broken":', offline("valid")],
    )

    with caplog.at_level(logging.WARNING):
        complete_backfill(worker)

    assert "reason=invalid_json" in caplog.text
    assert service.get_snapshot().completed_sessions_total == 1
    state = next(iter(repository.get_reader_states().values()))
    assert state.source_offset == Path(
        selected.source_log_path
    ).stat().st_size


def test_invalid_utf8_advances_and_next_line_is_counted(
    tmp_path,
    caplog,
):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [b"\xff\xfe", offline("valid")],
    )

    with caplog.at_level(logging.WARNING):
        complete_backfill(worker)

    assert "public_traffic_invalid_utf8" in caplog.text
    assert service.get_snapshot().completed_sessions_total == 1
    state = next(iter(repository.get_reader_states().values()))
    assert state.source_offset == Path(
        selected.source_log_path
    ).stat().st_size


def test_transaction_failure_rolls_back_aggregate_event_and_offset(
    tmp_path,
    monkeypatch,
):
    selected, repository, _, reader, _, _ = stack(tmp_path)
    append_lines(selected.source_log_path, [offline("rollback")])

    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("forced failure")

    monkeypatch.setattr(repository, "_add_to_daily", fail)

    with pytest.raises(sqlite3.OperationalError):
        reader.scan()

    assert table_rows(repository.db_path, "traffic_daily") == []
    assert table_rows(repository.db_path, "processed_events") == []
    assert repository.get_reader_states() == {}


def test_empty_installation_becomes_ready_with_zero_stats(tmp_path):
    _, repository, service, _, worker, _ = stack(tmp_path)

    complete_backfill(worker)
    snapshot = service.get_snapshot()

    assert snapshot.available
    assert snapshot.total_bytes == 0
    assert snapshot.updated_at is None


def test_backfill_reads_oldest_rotation_first(tmp_path):
    selected, repository, _, _, worker, _ = stack(tmp_path)
    active = Path(selected.source_log_path)
    append_lines(f"{active}.2", [offline("oldest", traffic=1)])
    append_lines(f"{active}.1", [offline("middle", traffic=2)])
    append_lines(active, [offline("newest", traffic=3)])

    complete_backfill(worker)
    with closing(sqlite3.connect(repository.db_path)) as connection:
        ids = [
            row[0]
            for row in connection.execute(
                """
                SELECT normalized_event_id
                FROM processed_events
                ORDER BY rowid
                """
            )
        ]

    assert ids == ["oldest", "middle", "newest"]


def test_live_rotation_finishes_old_inode_then_new_active(tmp_path):
    selected, repository, service, reader, worker, _ = stack(tmp_path)
    active = Path(selected.source_log_path)
    append_lines(active, [offline("first", traffic=1)])
    complete_backfill(worker)
    old_identity = f"{active.stat().st_dev}:{active.stat().st_ino}"

    active.rename(Path(f"{active}.1"))
    append_lines(
        f"{active}.1",
        [offline("old-tail", traffic=2)],
    )
    append_lines(active, [offline("new-active", traffic=4)])
    reader.scan()

    assert service.get_snapshot().total_bytes == 7
    assert repository.get_reader_states()[
        old_identity
    ].retired_completed


def test_truncate_restarts_at_zero_without_double_count(tmp_path):
    selected, repository, service, reader, worker, _ = stack(tmp_path)
    active = Path(selected.source_log_path)
    append_lines(active, [offline("same", traffic=5)])
    complete_backfill(worker)
    active.write_bytes(b"")
    append_lines(
        active,
        [
            offline("same", traffic=5),
            offline("new", traffic=7),
        ],
    )

    reader.scan()

    assert service.get_snapshot().total_bytes == 12
    assert len(table_rows(repository.db_path, "processed_events")) == 2


def test_missing_active_inode_warns_only_once_across_restart(
    tmp_path,
    caplog,
):
    selected, repository, _, reader, worker, _ = stack(tmp_path)
    active = Path(selected.source_log_path)
    append_lines(active, [offline("event")])
    complete_backfill(worker)
    active.unlink()

    with caplog.at_level(logging.WARNING):
        reader.scan()
        reader.scan()
        restarted = PublicTrafficReader(
            source_path=selected.source_log_path,
            repository=repository,
            service=reader.service,
            logger=reader.logger,
        )
        restarted.scan()

    assert caplog.text.count(
        "public_traffic_old_inode_not_found"
    ) == 1


def test_missing_completed_retired_inode_does_not_warn(
    tmp_path,
    caplog,
):
    selected, _, _, reader, worker, _ = stack(tmp_path)
    active = Path(selected.source_log_path)
    rotated = Path(f"{active}.1")
    append_lines(rotated, [offline("retired")])
    complete_backfill(worker)
    rotated.unlink()

    with caplog.at_level(logging.WARNING):
        reader.scan()

    assert "public_traffic_old_inode_not_found" not in caplog.text


@pytest.mark.parametrize(
    ("value", "display"),
    [
        (0, "0 MB"),
        (1024**2, "1 MB"),
        (812 * 1024**2, "812 MB"),
        (3 * 1024**3 + 182 * 1024**2, "3.18 GB"),
        (int(Decimal("4.5") * (1024**3)), "4.5 GB"),
        (int(Decimal("1.24") * (1024**4)), "1.24 TB"),
    ],
)
def test_binary_formatting_uses_half_up(value, display):
    assert format_traffic_bytes(value) == display


def test_reset_is_forbidden_before_backfill(tmp_path):
    _, repository, service, _, _, _ = stack(tmp_path)

    with pytest.raises(BackfillIncompleteError):
        service.reset(ssid="Zefer_Parki")

    assert table_rows(repository.db_path, "counter_resets") == []


def test_reset_one_ssid_preserves_state_and_other_ssids(tmp_path):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [
            offline("z", traffic=10),
            offline("w", ssid="Welcome", traffic=20),
        ],
    )
    complete_backfill(worker)
    states_before = repository.get_reader_states()

    summary = service.reset(ssid="Zefer_Parki")

    assert summary.previous_total_bytes == 10
    assert service.get_snapshot().total_bytes == 0
    welcome = repository.get_snapshot(
        ssid="Welcome",
        local_date=service.local_date(),
    )
    assert welcome.total_bytes == 20
    assert len(table_rows(repository.db_path, "processed_events")) == 2
    assert repository.get_reader_states() == states_before
    assert repository.initial_backfill_completed()
    assert len(table_rows(repository.db_path, "counter_resets")) == 1


def test_reset_all_preserves_processed_events_and_state(tmp_path):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [
            offline("z", traffic=10),
            offline("w", ssid="Welcome", traffic=20),
        ],
    )
    complete_backfill(worker)

    summary = service.reset(ssid=None)

    assert summary.affected_ssids == 2
    assert table_rows(repository.db_path, "traffic_daily") == []
    assert len(table_rows(repository.db_path, "processed_events")) == 2
    assert repository.initial_backfill_completed()


def test_reset_transaction_failure_rolls_back_delete_and_audit(
    tmp_path,
):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    append_lines(selected.source_log_path, [offline("z", traffic=10)])
    complete_backfill(worker)

    with pytest.raises(RuntimeError):
        service.reset(
            ssid="Zefer_Parki",
            before_commit=lambda: (_ for _ in ()).throw(
                RuntimeError("forced")
            ),
        )

    assert service.get_snapshot().total_bytes == 10
    assert table_rows(repository.db_path, "counter_resets") == []


def test_old_events_do_not_restore_after_reset_and_truncate(
    tmp_path,
):
    selected, _, service, reader, worker, _ = stack(tmp_path)
    active = Path(selected.source_log_path)
    original = offline("old", traffic=10)
    append_lines(active, [original])
    complete_backfill(worker)
    service.reset(ssid="Zefer_Parki")
    active.write_bytes(b"")
    append_lines(active, [original, offline("new", traffic=4)])

    reader.scan()

    assert service.get_snapshot().total_bytes == 4


def test_cli_without_yes_does_not_reset(tmp_path, capsys):
    selected, _, service, _, worker, _ = stack(tmp_path)
    append_lines(selected.source_log_path, [offline("z", traffic=10)])
    complete_backfill(worker)
    settings = {
        "public_traffic_counter_enabled": True,
        "public_traffic_ssid": selected.ssid,
        "public_traffic_db_path": selected.db_path,
        "omada_webhook_normalized_log_file": (
            selected.source_log_path
        ),
        "portal_counter_timezone": selected.timezone_name,
        "public_traffic_scan_interval_seconds": 10,
        "public_traffic_frontend_refresh_seconds": 60,
    }

    with patch(
        "app.public_traffic.cli.get_settings",
        return_value=settings,
    ):
        exit_code = cli_main(["reset", "--ssid", selected.ssid])

    assert exit_code == 2
    assert service.get_snapshot().total_bytes == 10
    assert "--yes" in capsys.readouterr().err


def test_cli_rejects_reset_during_backfill(tmp_path, capsys):
    selected, _, _, _, _, _ = stack(tmp_path)
    settings = {
        "public_traffic_counter_enabled": True,
        "public_traffic_ssid": selected.ssid,
        "public_traffic_db_path": selected.db_path,
        "omada_webhook_normalized_log_file": (
            selected.source_log_path
        ),
        "portal_counter_timezone": selected.timezone_name,
        "public_traffic_scan_interval_seconds": 10,
        "public_traffic_frontend_refresh_seconds": 60,
    }

    with patch(
        "app.public_traffic.cli.get_settings",
        return_value=settings,
    ):
        exit_code = cli_main([
            "reset",
            "--ssid",
            selected.ssid,
            "--yes",
        ])

    assert exit_code == 1
    assert "backfill is not complete" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("public_traffic_ssid", ""),
        ("public_traffic_db_path", ""),
        ("portal_counter_timezone", ""),
        ("public_traffic_scan_interval_seconds", 0),
        ("public_traffic_frontend_refresh_seconds", -1),
    ],
)
def test_invalid_enabled_configuration_is_rejected(
    tmp_path,
    key,
    value,
):
    values = {
        "public_traffic_counter_enabled": True,
        "public_traffic_ssid": "Zefer_Parki",
        "public_traffic_db_path": str(tmp_path / "db.sqlite"),
        "omada_webhook_normalized_log_file": str(tmp_path / "log"),
        "portal_counter_timezone": "Asia/Baku",
        "public_traffic_scan_interval_seconds": 10,
        "public_traffic_frontend_refresh_seconds": 60,
    }
    values[key] = value

    with pytest.raises(PublicTrafficConfigError):
        PublicTrafficConfig.from_settings(values)


def test_invalid_timezone_is_a_fail_safe_configuration_error(
    tmp_path,
    caplog,
):
    selected = config(
        tmp_path,
        portal_counter_timezone="Not/A-Timezone",
    )
    service = PublicTrafficService(
        config=selected,
        repository=PublicTrafficRepository(selected.db_path),
        logger=logging.getLogger("invalid-traffic-timezone"),
    )

    with caplog.at_level(logging.ERROR):
        assert not service.initialize()

    assert not service.available
    assert "public_traffic_configuration_error" in caplog.text
    assert not Path(selected.db_path).exists()


def test_unusable_database_path_is_a_fail_safe_database_error(
    tmp_path,
    caplog,
):
    db_directory = tmp_path / "database-is-a-directory"
    db_directory.mkdir()
    selected = config(
        tmp_path,
        public_traffic_db_path=str(db_directory),
    )
    service = PublicTrafficService(
        config=selected,
        repository=PublicTrafficRepository(selected.db_path),
        logger=logging.getLogger("invalid-traffic-database"),
    )

    with caplog.at_level(logging.ERROR):
        assert not service.initialize()

    assert not service.available
    assert "public_traffic_database_error" in caplog.text


def test_worker_start_is_immediate_idempotent_and_stops(tmp_path):
    _, _, _, _, worker, _ = stack(tmp_path)

    started_at = time.monotonic()
    assert worker.start()
    assert time.monotonic() - started_at < 0.5
    assert not worker.start()
    worker.stop()

    assert not worker.running


def test_backfill_lifecycle_logs_once_across_repeated_scans(
    tmp_path,
    caplog,
):
    selected, repository, _, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [offline("unfinished-backfill")],
        newline=False,
    )

    caplog.set_level(logging.INFO)
    worker.run_once()
    worker.run_once()

    assert caplog.text.count("public_traffic_backfill_started") == 1
    assert "public_traffic_backfill_completed" not in caplog.text
    with Path(selected.source_log_path).open("ab") as stream:
        stream.write(b"\n")
    worker.run_once()
    worker.run_once()

    assert repository.initial_backfill_completed()
    assert caplog.text.count("public_traffic_backfill_started") == 1
    assert caplog.text.count("public_traffic_backfill_completed") == 1
    assert "public_traffic_reconciliation_started" not in caplog.text


def test_startup_reconciliation_logs_once_then_scans_silently(
    tmp_path,
    caplog,
):
    selected, repository, service, _, first_worker, _ = stack(
        tmp_path
    )
    complete_backfill(first_worker)
    restarted_reader = PublicTrafficReader(
        source_path=selected.source_log_path,
        repository=repository,
        service=service,
        logger=logging.getLogger("reconciliation-reader"),
    )
    restarted_worker = PublicTrafficWorker(
        reader=restarted_reader,
        repository=repository,
        service=service,
        logger=logging.getLogger("reconciliation-worker"),
        scan_interval_seconds=10,
    )

    with caplog.at_level(logging.INFO):
        restarted_worker.run_once()
        restarted_worker.run_once()
        restarted_worker.run_once()

    assert (
        caplog.text.count("public_traffic_reconciliation_started")
        == 1
    )
    assert (
        caplog.text.count("public_traffic_reconciliation_completed")
        == 1
    )
    assert "public_traffic_backfill_started" not in caplog.text


def test_worker_start_failure_does_not_prevent_flask_start(
    caplog,
):
    class FailingWorker:
        def start(self):
            raise RuntimeError("cannot create thread")

    class TrafficService:
        available = True

    class FakeApp:
        def __init__(self):
            self.extensions = {
                "public_traffic_worker": FailingWorker(),
                "public_traffic_service": TrafficService(),
            }
            self.ran = False

        def run(self, **_kwargs):
            self.ran = True

    app = FakeApp()
    settings = {
        "host": "127.0.0.1",
        "port": 8088,
        "debug": False,
    }
    with (
        patch.object(run_module, "create_app", return_value=app),
        patch.object(
            run_module,
            "create_controller",
            return_value=object(),
        ),
        patch.object(run_module, "get_settings", return_value=settings),
        patch.object(run_module.atexit, "register"),
        patch.object(run_module.signal, "signal"),
        patch.object(run_module, "shutdown_handler"),
        caplog.at_level(logging.ERROR),
    ):
        run_module.main()

    assert app.ran
    assert not app.extensions["public_traffic_service"].available
    assert run_module._public_traffic_worker is None
    assert "public_traffic_counter_start_failed" in caplog.text


def test_api_keeps_open_counter_when_traffic_is_unavailable(
    tmp_path,
):
    open_service = PortalCounterService(
        PortalCounterRepository(str(tmp_path / "open.db"))
    )
    assert open_service.initialize()
    settings = {
        "portal_counter_enabled": True,
        "portal_counter_db_path": str(tmp_path / "open.db"),
        "portal_counter_timezone": "Asia/Baku",
        "portal_counter_api_enabled": True,
    }
    with (
        patch.object(
            web_module,
            "get_settings",
            return_value=settings,
        ),
        patch.object(
            web_module,
            "create_controller",
            return_value=object(),
        ),
    ):
        app = web_module.create_app(open_service)
    client = app.test_client()

    response = client.get("/api/public/portal-counter")

    assert response.status_code == 200
    assert response.get_json()["opened_total"] == 0
    assert response.get_json()["traffic"] == {
        "available": False,
        "ssid": "",
    }


def test_api_returns_traffic_and_preserves_old_fields(tmp_path):
    selected, _, traffic_service, _, worker, _ = stack(tmp_path)
    append_lines(
        selected.source_log_path,
        [offline("api", traffic=3_407_872_000)],
    )
    complete_backfill(worker)
    open_service = PortalCounterService(
        PortalCounterRepository(str(tmp_path / "open.db"))
    )
    assert open_service.initialize()
    settings = {
        "portal_counter_enabled": True,
        "portal_counter_db_path": str(tmp_path / "open.db"),
        "portal_counter_timezone": "Asia/Baku",
        "portal_counter_api_enabled": True,
    }
    with (
        patch.object(
            web_module,
            "get_settings",
            return_value=settings,
        ),
        patch.object(
            web_module,
            "create_controller",
            return_value=object(),
        ),
    ):
        app = web_module.create_app(
            open_service,
            public_traffic_service=traffic_service,
        )

    payload = app.test_client().get(
        "/api/public/portal-counter"
    ).get_json()

    assert set(payload) == {
        "opened_today",
        "opened_total",
        "day",
        "timezone",
        "traffic",
    }
    assert payload["traffic"] == {
        "available": True,
        "ssid": "Zefer_Parki",
        "today_bytes": 3_407_872_000,
        "today_display": "3.17 GB",
        "total_bytes": 3_407_872_000,
        "total_display": "3.17 GB",
        "completed_sessions_today": 1,
        "completed_sessions_total": 1,
        "updated_at": "2026-07-29T08:00:00.000Z",
    }


def test_corrupt_aggregate_hides_only_traffic_from_api(tmp_path):
    selected, repository, traffic_service, _, worker, _ = stack(
        tmp_path
    )
    append_lines(selected.source_log_path, [offline("api")])
    complete_backfill(worker)
    with closing(sqlite3.connect(repository.db_path)) as connection:
        connection.execute(
            "UPDATE traffic_daily SET traffic_bytes = 1.5"
        )
        connection.commit()
    open_service = PortalCounterService(
        PortalCounterRepository(str(tmp_path / "open.db"))
    )
    assert open_service.initialize()
    settings = {
        "portal_counter_enabled": True,
        "portal_counter_db_path": str(tmp_path / "open.db"),
        "portal_counter_timezone": "Asia/Baku",
        "portal_counter_api_enabled": True,
    }
    with (
        patch.object(
            web_module,
            "get_settings",
            return_value=settings,
        ),
        patch.object(
            web_module,
            "create_controller",
            return_value=object(),
        ),
    ):
        app = web_module.create_app(
            open_service,
            public_traffic_service=traffic_service,
        )

    response = app.test_client().get(
        "/api/public/portal-counter"
    )

    assert response.status_code == 200
    assert response.get_json()["opened_total"] == 0
    assert response.get_json()["traffic"] == {
        "available": False,
        "ssid": "Zefer_Parki",
    }


def test_existing_database_is_available_before_reconciliation(
    tmp_path,
):
    selected, repository, _, _, worker, clock = stack(tmp_path)
    append_lines(selected.source_log_path, [offline("saved", traffic=9)])
    complete_backfill(worker)
    restarted = PublicTrafficService(
        config=selected,
        repository=PublicTrafficRepository(selected.db_path),
        logger=logging.getLogger("restarted-public-traffic"),
        clock=clock,
    )

    assert restarted.initialize()
    assert restarted.get_snapshot().available
    assert restarted.get_snapshot().total_bytes == 9
    assert repository.initial_backfill_completed()


def test_interrupted_backfill_resumes_without_duplicate(tmp_path):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    active = Path(selected.source_log_path)
    complete = json.dumps(offline("first", traffic=2)).encode()
    partial = json.dumps(offline("second", traffic=3)).encode()
    active.write_bytes(complete + b"\n" + partial)

    worker.run_once()

    assert not repository.initial_backfill_completed()
    assert len(table_rows(repository.db_path, "processed_events")) == 1
    with active.open("ab") as stream:
        stream.write(b"\n")
    worker.run_once()

    assert repository.initial_backfill_completed()
    assert service.get_snapshot().total_bytes == 5
    assert len(table_rows(repository.db_path, "processed_events")) == 2


def test_multiple_rotations_while_stopped_are_reconciled(tmp_path):
    selected, _, service, reader, worker, _ = stack(tmp_path)
    active = Path(selected.source_log_path)
    append_lines(active, [offline("before-stop", traffic=1)])
    complete_backfill(worker)

    active.rename(Path(f"{active}.2"))
    append_lines(f"{active}.1", [offline("during-stop", traffic=2)])
    append_lines(active, [offline("after-stop", traffic=4)])
    reader.scan()

    assert service.get_snapshot().total_bytes == 7


def test_never_existing_source_does_not_warn(tmp_path, caplog):
    _, _, _, reader, worker, _ = stack(tmp_path)
    complete_backfill(worker)

    with caplog.at_level(logging.WARNING):
        reader.scan()

    assert "public_traffic_old_inode_not_found" not in caplog.text


def test_reader_state_tracks_observed_size_and_retired_status(
    tmp_path,
):
    selected, repository, _, _, worker, _ = stack(tmp_path)
    active = Path(selected.source_log_path)
    rotated = Path(f"{active}.1")
    append_lines(rotated, [offline("retired")])
    append_lines(active, [offline("active")])

    complete_backfill(worker)
    states = repository.get_reader_states()
    active_identity = f"{active.stat().st_dev}:{active.stat().st_ino}"
    retired_identity = (
        f"{rotated.stat().st_dev}:{rotated.stat().st_ino}"
    )

    assert states[active_identity].last_observed_size == active.stat().st_size
    assert not states[active_identity].retired_completed
    assert states[retired_identity].retired_completed


def test_disappeared_completed_retired_inode_is_safe_when_reused(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.public_traffic.reader._source_identity",
        lambda _stat: "fixed:retired",
    )
    selected, repository, service, reader, worker, _ = stack(
        tmp_path
    )
    active = Path(selected.source_log_path)
    rotated = Path(f"{active}.1")
    append_lines(rotated, [offline("old-retired", traffic=2)])
    complete_backfill(worker)

    assert repository.get_reader_states()[
        "fixed:retired"
    ].retired_completed
    rotated.unlink()
    reader.scan()

    assert "fixed:retired" not in repository.get_reader_states()
    append_lines(active, [offline("reused-retired", traffic=3)])
    reader.scan()

    assert service.get_snapshot().total_bytes == 5


def test_retired_inode_reused_by_active_before_missing_scan(
    tmp_path,
    monkeypatch,
    caplog,
):
    monkeypatch.setattr(
        "app.public_traffic.reader._source_identity",
        lambda _stat: "fixed:instant-reuse",
    )
    selected, repository, service, reader, worker, _ = stack(
        tmp_path
    )
    active = Path(selected.source_log_path)
    rotated = Path(f"{active}.1")
    append_lines(rotated, [offline("old-instant", traffic=2)])
    complete_backfill(worker)
    old_offset = repository.get_reader_states()[
        "fixed:instant-reuse"
    ].source_offset

    rotated.unlink()
    append_lines(
        active,
        [
            offline("new-instant", traffic=3),
            {
                "event": "omada.client_online",
                "padding": "x" * (old_offset + 100),
            },
        ],
    )
    assert active.stat().st_size > old_offset
    with caplog.at_level(logging.WARNING):
        reader.scan()

    assert service.get_snapshot().total_bytes == 5
    assert "reason=retired_identity_reused" in caplog.text


def test_missing_inode_reappearance_restarts_from_zero(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.public_traffic.reader._source_identity",
        lambda _stat: "fixed:missing",
    )
    selected, repository, service, reader, worker, _ = stack(
        tmp_path
    )
    active = Path(selected.source_log_path)
    append_lines(active, [offline("old-active", traffic=2)])
    complete_backfill(worker)
    old_offset = repository.get_reader_states()[
        "fixed:missing"
    ].source_offset

    active.unlink()
    reader.scan()
    assert repository.get_reader_states()[
        "fixed:missing"
    ].missing_warning_emitted

    append_lines(
        active,
        [
            offline("reappeared", traffic=3),
            {
                "event": "omada.client_online",
                "padding": "x" * (old_offset + 100),
            },
        ],
    )
    assert active.stat().st_size > old_offset
    reader.scan()

    assert service.get_snapshot().total_bytes == 5
    state = repository.get_reader_states()["fixed:missing"]
    assert not state.missing_warning_emitted
    assert state.source_offset == active.stat().st_size


def test_same_inode_truncate_and_regrow_above_offset_restarts_zero(
    tmp_path,
    monkeypatch,
    caplog,
):
    monkeypatch.setattr(
        "app.public_traffic.reader._source_identity",
        lambda _stat: "fixed:truncate-regrow",
    )
    selected, _, service, reader, worker, _ = stack(tmp_path)
    active = Path(selected.source_log_path)
    append_lines(active, [offline("before-rewrite", traffic=2)])
    complete_backfill(worker)
    old_offset = active.stat().st_size

    active.write_bytes(b"")
    append_lines(
        active,
        [
            offline("after-rewrite-1", traffic=3),
            offline("after-rewrite-2", traffic=4),
            {
                "event": "omada.client_online",
                "padding": "x" * (old_offset + 100),
            },
        ],
    )
    assert active.stat().st_size > old_offset
    with caplog.at_level(logging.WARNING):
        reader.scan()

    assert service.get_snapshot().total_bytes == 9
    assert "reason=checkpoint_mismatch" in caplog.text


def test_schema_v1_migrates_reader_checkpoint_to_v2(tmp_path):
    db_path = tmp_path / "traffic-v1.db"
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute(
            """
            CREATE TABLE reader_state (
                source_identity TEXT PRIMARY KEY,
                source_path TEXT NOT NULL,
                source_offset INTEGER NOT NULL DEFAULT 0,
                last_observed_size INTEGER,
                retired_completed INTEGER NOT NULL DEFAULT 0,
                missing_warning_emitted INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute("PRAGMA user_version=1")
        connection.commit()
    repository = PublicTrafficRepository(str(db_path))

    repository.migrate("2026-07-29T08:00:00.000Z")

    with closing(sqlite3.connect(db_path)) as connection:
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(reader_state)"
            )
        }
        version = connection.execute(
            "PRAGMA user_version"
        ).fetchone()[0]
    assert "source_checkpoint" in columns
    assert version == 2


def test_sqlite_uses_wal_and_busy_timeout(tmp_path):
    selected, repository, _, _, _, _ = stack(tmp_path)
    with closing(repository._connect()) as connection:
        journal_mode = connection.execute(
            "PRAGMA journal_mode"
        ).fetchone()[0]
        busy_timeout = connection.execute(
            "PRAGMA busy_timeout"
        ).fetchone()[0]

    assert journal_mode.lower() == "wal"
    assert busy_timeout == 250
    assert Path(selected.db_path).exists()


def test_concurrent_reads_and_single_writer_do_not_lock(tmp_path):
    _, repository, service, _, _, _ = stack(tmp_path)
    repository.mark_initial_backfill_completed(service.now_iso())

    def write_events():
        for index in range(30):
            repository.process_offline_event(
                event=TrafficEvent(
                    normalized_event_id=f"parallel-{index}",
                    ssid="Zefer_Parki",
                    local_date=service.local_date(),
                    traffic_bytes=1,
                    skip_reason=None,
                ),
                source_identity="1:1",
                source_path="parallel.log",
                offset_start=index,
                offset_end=index + 1,
                observed_size=30,
                processed_at=service.now_iso(),
            )

    def read_snapshots():
        for _ in range(60):
            service.get_snapshot()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(write_events),
            executor.submit(read_snapshots),
        ]
        for future in futures:
            future.result()

    assert service.get_snapshot().total_bytes == 30


def test_updated_at_ignores_duplicate_invalid_and_overflow(
    tmp_path,
):
    selected, _, service, reader, worker, clock = stack(tmp_path)
    active = Path(selected.source_log_path)
    append_lines(active, [offline("max", traffic=INT64_MAX)])
    complete_backfill(worker)
    first_updated = service.get_snapshot().updated_at
    clock.value = datetime(2026, 7, 29, 9, 0, tzinfo=UTC)
    append_lines(
        active,
        [
            offline("max", traffic=INT64_MAX),
            offline("invalid-later", traffic=True),
            offline("overflow-later", traffic=1),
        ],
    )

    reader.scan()

    assert service.get_snapshot().updated_at == first_updated


def test_invalid_offline_warning_is_not_repeated_after_truncate(
    tmp_path,
    caplog,
):
    selected, _, _, reader, worker, _ = stack(tmp_path)
    active = Path(selected.source_log_path)
    invalid = offline("invalid-once", traffic=True)
    append_lines(active, [invalid])

    with caplog.at_level(logging.WARNING):
        complete_backfill(worker)
        active.write_bytes(b"")
        append_lines(active, [invalid])
        reader.scan()

    assert caplog.text.count("reason=invalid_traffic_value") == 1


def test_new_event_after_reset_starts_from_zero(tmp_path):
    selected, _, service, reader, worker, _ = stack(tmp_path)
    append_lines(selected.source_log_path, [offline("old", traffic=8)])
    complete_backfill(worker)
    service.reset(ssid="Zefer_Parki")
    append_lines(selected.source_log_path, [offline("new", traffic=3)])

    reader.scan()

    assert service.get_snapshot().total_bytes == 3
    assert service.get_snapshot().completed_sessions_total == 1


def test_cli_success_resets_and_writes_audit(tmp_path, capsys):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    append_lines(selected.source_log_path, [offline("cli", traffic=10)])
    complete_backfill(worker)
    settings = {
        "public_traffic_counter_enabled": True,
        "public_traffic_ssid": selected.ssid,
        "public_traffic_db_path": selected.db_path,
        "omada_webhook_normalized_log_file": (
            selected.source_log_path
        ),
        "portal_counter_timezone": selected.timezone_name,
        "public_traffic_scan_interval_seconds": 10,
        "public_traffic_frontend_refresh_seconds": 60,
    }

    with patch(
        "app.public_traffic.cli.get_settings",
        return_value=settings,
    ):
        exit_code = cli_main([
            "reset",
            "--ssid",
            selected.ssid,
            "--yes",
        ])

    assert exit_code == 0
    assert service.get_snapshot().total_bytes == 0
    assert len(table_rows(repository.db_path, "counter_resets")) == 1
    assert "Reset completed" in capsys.readouterr().out


def test_cli_reset_all_handles_cross_ssid_sum_above_int64(
    tmp_path,
    capsys,
):
    selected, repository, service, _, worker, _ = stack(tmp_path)
    complete_backfill(worker)
    per_ssid = INT64_MAX // 2 + 1
    with closing(repository._connect()) as connection:
        connection.executemany(
            """
            INSERT INTO traffic_daily (
                local_date,
                ssid,
                traffic_bytes,
                completed_sessions,
                updated_at
            )
            VALUES (?, ?, ?, 1, ?)
            """,
            [
                (
                    service.local_date(),
                    "SSID-A",
                    per_ssid,
                    service.now_iso(),
                ),
                (
                    service.local_date(),
                    "SSID-B",
                    per_ssid,
                    service.now_iso(),
                ),
            ],
        )
        connection.commit()
    settings = {
        "public_traffic_counter_enabled": True,
        "public_traffic_ssid": selected.ssid,
        "public_traffic_db_path": selected.db_path,
        "omada_webhook_normalized_log_file": (
            selected.source_log_path
        ),
        "portal_counter_timezone": selected.timezone_name,
        "public_traffic_scan_interval_seconds": 10,
        "public_traffic_frontend_refresh_seconds": 60,
    }

    with patch(
        "app.public_traffic.cli.get_settings",
        return_value=settings,
    ):
        exit_code = cli_main(["reset", "--all", "--yes"])

    assert exit_code == 0
    assert table_rows(repository.db_path, "traffic_daily") == []
    reset = table_rows(repository.db_path, "counter_resets")[0]
    assert reset[-1] == 2
    output = capsys.readouterr().out
    assert 'SSID "SSID-A"' in output
    assert 'SSID "SSID-B"' in output


def test_cli_rejects_ssid_and_all_together():
    with pytest.raises(SystemExit) as raised:
        cli_main([
            "reset",
            "--ssid",
            "Zefer_Parki",
            "--all",
            "--yes",
        ])

    assert raised.value.code == 2


def test_disabled_component_creates_no_database_or_worker(tmp_path):
    open_service = PortalCounterService(
        PortalCounterRepository(str(tmp_path / "open.db"))
    )
    assert open_service.initialize()
    traffic_path = tmp_path / "disabled-traffic.db"
    settings = {
        "portal_counter_enabled": True,
        "portal_counter_db_path": str(tmp_path / "open.db"),
        "portal_counter_timezone": "Asia/Baku",
        "portal_counter_api_enabled": True,
        "public_traffic_counter_enabled": False,
        "public_traffic_ssid": "Zefer_Parki",
        "public_traffic_db_path": str(traffic_path),
        "omada_webhook_normalized_log_file": str(tmp_path / "log"),
        "public_traffic_scan_interval_seconds": 10,
        "public_traffic_frontend_refresh_seconds": 60,
    }
    with (
        patch.object(
            web_module,
            "get_settings",
            return_value=settings,
        ),
        patch.object(
            web_module,
            "create_controller",
            return_value=object(),
        ),
    ):
        app = web_module.create_app(open_service)

    assert app.extensions["public_traffic_worker"] is None
    assert not traffic_path.exists()
    assert app.test_client().get(
        "/api/public/portal-counter"
    ).get_json()["traffic"]["available"] is False


def test_invalid_traffic_config_is_fail_safe_for_app(tmp_path):
    open_service = PortalCounterService(
        PortalCounterRepository(str(tmp_path / "open.db"))
    )
    assert open_service.initialize()
    settings = {
        "portal_counter_enabled": True,
        "portal_counter_db_path": str(tmp_path / "open.db"),
        "portal_counter_timezone": "Asia/Baku",
        "portal_counter_api_enabled": True,
        "public_traffic_counter_enabled": True,
        "public_traffic_ssid": "SafeSSID",
        "public_traffic_db_path": str(tmp_path / "traffic.db"),
        "omada_webhook_normalized_log_file": str(tmp_path / "log"),
        "public_traffic_scan_interval_seconds": 0,
        "public_traffic_frontend_refresh_seconds": 60,
    }
    with (
        patch.object(
            web_module,
            "get_settings",
            return_value=settings,
        ),
        patch.object(
            web_module,
            "create_controller",
            return_value=object(),
        ),
    ):
        app = web_module.create_app(open_service)

    payload = app.test_client().get(
        "/api/public/portal-counter"
    ).get_json()
    assert payload["opened_total"] == 0
    assert payload["traffic"] == {
        "available": False,
        "ssid": "SafeSSID",
    }
    assert app.extensions["public_traffic_worker"] is None


def test_create_app_constructs_but_does_not_start_worker(tmp_path):
    open_service = PortalCounterService(
        PortalCounterRepository(str(tmp_path / "open.db"))
    )
    assert open_service.initialize()
    settings = {
        "portal_counter_enabled": True,
        "portal_counter_db_path": str(tmp_path / "open.db"),
        "portal_counter_timezone": "Asia/Baku",
        "portal_counter_api_enabled": True,
        "public_traffic_counter_enabled": True,
        "public_traffic_ssid": "Zefer_Parki",
        "public_traffic_db_path": str(tmp_path / "traffic.db"),
        "omada_webhook_normalized_log_file": str(tmp_path / "log"),
        "public_traffic_scan_interval_seconds": 10,
        "public_traffic_frontend_refresh_seconds": 60,
    }
    with (
        patch.object(
            web_module,
            "get_settings",
            return_value=settings,
        ),
        patch.object(
            web_module,
            "create_controller",
            return_value=object(),
        ),
    ):
        first = web_module.create_app(open_service)
        second = web_module.create_app(open_service)

    assert not first.extensions["public_traffic_worker"].running
    assert not second.extensions["public_traffic_worker"].running
