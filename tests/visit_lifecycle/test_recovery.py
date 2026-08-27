from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone

import pytest

from app.visit_lifecycle.recovery import (
    RecoveryError,
    backup_database,
    main,
    recover,
)

from .conftest import make_request


NOW = "2026-08-13T11:00:00.000Z"


def _event(
    repository,
    *,
    event_id="offline:1",
    mac="02:11:22:33:44:55",
    controller_at="2026-08-13T10:05:00.000Z",
    ssid="Zefer_Parki",
    client_ip="192.0.2.20",
    ap_mac="02:FF:EE:DD:CC:BB",
    reported_seconds=1800,
    reported_bytes=123456,
    site_id="site-a",
    processing_result="unmatched",
    reason="stale_or_ambiguous",
):
    with repository._connect() as connection:  # noqa: SLF001
        connection.execute(
            """
            INSERT INTO visit_source_events (
                event_id, event_type, site_id, client_mac,
                controller_event_at, received_at, source_identity,
                source_offset_start, source_offset_end,
                processing_result, visit_id, reason,
                first_processed_at, processed_at, pending_until,
                last_match_attempt_at, client_ip, ssid, ap_mac,
                reported_connected_seconds, reported_traffic_total_bytes
            ) VALUES (?, 'omada.client_offline', ?, ?, ?, ?,
                      'fixture', 0, 1, ?, NULL, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                site_id,
                mac,
                controller_at,
                controller_at,
                processing_result,
                reason,
                NOW,
                NOW,
                client_ip,
                ssid,
                ap_mac,
                reported_seconds,
                reported_bytes,
            ),
        )
        connection.commit()


def _fingerprint(repository):
    with repository._connect(readonly=True) as connection:  # noqa: SLF001
        return tuple(
            connection.execute(f"SELECT * FROM {table}").fetchall()
            for table in (
                "visits",
                "visit_authorizations",
                "visit_source_events",
                "visit_reader_state",
            )
        )


def test_dry_run_is_read_only_and_reports_earliest_safe_event(
    visit_repository,
    visit_service,
):
    opened = visit_service.submit_authorized(make_request())
    _event(
        visit_repository,
        event_id="offline:2",
        controller_at="2026-08-13T10:06:00.000Z",
    )
    _event(visit_repository, event_id="offline:1")
    before = _fingerprint(visit_repository)

    result = recover(
        db_path=str(visit_repository.db_path.resolve()),
        site_id="site-a",
        now_utc=NOW,
    )

    assert result["mode"] == "dry-run"
    assert result["examined_count"] == 1
    assert result["recoverable_count"] == 1
    assert result["candidates"][0]["visit_id"] == opened.visit_id
    assert result["candidates"][0]["event_id"] == "offline:1"
    assert _fingerprint(visit_repository) == before


def test_apply_revalidates_and_closes_from_persisted_controller_evidence(
    visit_repository,
    visit_service,
):
    opened = visit_service.submit_authorized(make_request())
    _event(visit_repository)
    with visit_repository._connect(readonly=True) as connection:  # noqa: SLF001
        authorization_before = tuple(
            tuple(row) for row in connection.execute(
                "SELECT * FROM visit_authorizations WHERE visit_id=?",
                (opened.visit_id,),
            ).fetchall()
        )
        opening_before = tuple(connection.execute(
            """
            SELECT start_auth_session_id, start_auth_run_number,
                   start_final_reason, started_at
            FROM visits WHERE visit_id=?
            """,
            (opened.visit_id,),
        ).fetchone())
        visit_count_before = connection.execute(
            "SELECT COUNT(*) FROM visits"
        ).fetchone()[0]

    result = recover(
        db_path=str(visit_repository.db_path.resolve()),
        site_id="site-a",
        apply=True,
        now_utc=NOW,
    )

    assert result["applied_count"] == 1
    visit = visit_repository.get_visit("site-a", opened.visit_id)
    assert visit.status == "closed"
    assert visit.closed_at == "2026-08-13T10:05:00.000Z"
    assert visit.close_reason == "omada_client_offline_recovered"
    assert visit.close_time_source == "controller"
    assert visit.duration_seconds == 300
    assert visit.offline_event_id == "offline:1"
    assert visit.reported_connected_seconds == 1800
    with visit_repository._connect(readonly=True) as connection:  # noqa: SLF001
        event = connection.execute(
            "SELECT * FROM visit_source_events WHERE event_id='offline:1'"
        ).fetchone()
        authorization_after = tuple(
            tuple(row) for row in connection.execute(
                "SELECT * FROM visit_authorizations WHERE visit_id=?",
                (opened.visit_id,),
            ).fetchall()
        )
        opening_after = tuple(connection.execute(
            """
            SELECT start_auth_session_id, start_auth_run_number,
                   start_final_reason, started_at
            FROM visits WHERE visit_id=?
            """,
            (opened.visit_id,),
        ).fetchone())
        assert connection.execute("SELECT COUNT(*) FROM visits").fetchone()[0] == (
            visit_count_before
        )
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
    assert event["processing_result"] == "closed"
    assert event["reason"] is None
    assert event["visit_id"] == opened.visit_id
    assert event["first_processed_at"] == NOW
    assert authorization_after == authorization_before
    assert opening_after == opening_before

    repeated = recover(
        db_path=str(visit_repository.db_path.resolve()),
        site_id="site-a",
        apply=True,
        now_utc=NOW,
    )
    assert repeated["examined_count"] == 0
    assert repeated["applied_count"] == 0

    next_visit = visit_service.submit_authorized(make_request(
        auth_session_id="33333333-3333-4333-8333-333333333333",
        authorized_at=datetime(2026, 8, 13, 10, 10, tzinfo=timezone.utc),
        auth_run_number=2,
    ))
    assert next_visit.status == "opened"
    assert next_visit.visit_id != opened.visit_id


def test_zero_authorization_visit_is_never_recovered(
    visit_repository,
    visit_service,
):
    opened = visit_service.submit_authorized(make_request())
    with visit_repository._connect() as connection:  # noqa: SLF001
        connection.execute(
            "DELETE FROM visit_authorizations WHERE visit_id=?",
            (opened.visit_id,),
        )
        connection.commit()
    _event(visit_repository)

    result = recover(
        db_path=str(visit_repository.db_path.resolve()),
        site_id="site-a",
        apply=True,
        now_utc=NOW,
    )

    assert result["applied_count"] == 0
    assert result["skip_reason_counts"] == {
        "authorization_evidence_missing": 1
    }
    assert visit_repository.get_visit("site-a", opened.visit_id).status == "open"


def test_same_time_semantic_duplicates_choose_lowest_event_id(
    visit_repository,
    visit_service,
):
    visit_service.submit_authorized(make_request())
    _event(visit_repository, event_id="offline:b")
    _event(visit_repository, event_id="offline:a")

    result = recover(
        db_path=str(visit_repository.db_path.resolve()),
        site_id="site-a",
        now_utc=NOW,
    )

    assert result["semantic_duplicate_count"] == 1
    assert result["candidates"][0]["event_id"] == "offline:a"


def test_same_time_conflicting_events_are_ambiguous(
    visit_repository,
    visit_service,
):
    visit_service.submit_authorized(make_request())
    _event(visit_repository, event_id="offline:a")
    _event(visit_repository, event_id="offline:b", client_ip="192.0.2.99")

    result = recover(
        db_path=str(visit_repository.db_path.resolve()),
        site_id="site-a",
        now_utc=NOW,
    )

    assert result["recoverable_count"] == 0
    assert result["skip_reason_counts"] == {
        "ambiguous_same_timestamp_events": 1
    }


@pytest.mark.parametrize(
    ("changes", "expected_reason"),
    [
        ({"site_id": "site-b"}, "no_safe_offline_after_latest_authorization"),
        ({"mac": "02:11:22:33:44:99"}, "no_safe_offline_after_latest_authorization"),
        (
            {"controller_at": "2026-08-13T09:59:59.000Z"},
            "no_safe_offline_after_latest_authorization",
        ),
        ({"reason": "no_open_visit"}, "no_safe_offline_after_latest_authorization"),
        ({"reason": "ssid_changed"}, "no_safe_offline_after_latest_authorization"),
        (
            {"processing_result": "invalid", "reason": "invalid_event"},
            "no_safe_offline_after_latest_authorization",
        ),
        ({"ssid": "other-ssid"}, "ssid_conflict"),
    ],
)
def test_recovery_requires_exact_safe_persisted_evidence(
    visit_repository,
    visit_service,
    changes,
    expected_reason,
):
    opened = visit_service.submit_authorized(make_request())
    _event(visit_repository, **changes)

    result = recover(
        db_path=str(visit_repository.db_path.resolve()),
        site_id="site-a",
        apply=True,
        now_utc=NOW,
    )

    assert result["recoverable_count"] == 0
    assert result["skip_reason_counts"] == {expected_reason: 1}
    assert visit_repository.get_visit("site-a", opened.visit_id).status == "open"


def test_limit_and_keyset_continuation_neither_repeat_nor_skip(
    visit_repository,
    visit_service,
):
    visits = []
    for index in range(3):
        mac = f"02:11:22:33:44:{index + 10:02X}"
        visits.append(visit_service.submit_authorized(make_request(
            auth_session_id=str(uuid.uuid4()),
            client_mac=mac,
            authorized_at=datetime(
                2026, 8, 13, 10, index, tzinfo=timezone.utc
            ),
        )))

    first = recover(
        db_path=str(visit_repository.db_path.resolve()),
        site_id="site-a",
        limit=2,
        now_utc=NOW,
    )
    second = recover(
        db_path=str(visit_repository.db_path.resolve()),
        site_id="site-a",
        limit=2,
        after_started_at=first["next_after_started_at"],
        after_visit_id=first["next_after_visit_id"],
        now_utc=NOW,
    )

    assert first["examined_count"] == 2
    assert first["truncated"] is True
    assert first["remaining_open_visit_count"] == 1
    assert second["examined_count"] == 1
    assert second["truncated"] is False
    assert second["remaining_open_visit_count"] == 0


def test_sqlite_backup_is_consistent_verified_and_source_unchanged(
    visit_repository,
    visit_service,
    tmp_path,
):
    visit_service.submit_authorized(make_request())
    before = _fingerprint(visit_repository)
    destination = tmp_path / "backup.sqlite3"

    result = backup_database(
        db_path=str(visit_repository.db_path.resolve()),
        backup_to=str(destination.resolve()),
    )

    assert result["quick_check"] == "ok"
    assert result["source_schema_version"] == 2
    assert result["backup_schema_version"] == 2
    assert destination.is_file()
    assert _fingerprint(visit_repository) == before
    with sqlite3.connect(destination) as connection:
        assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
    with pytest.raises(RecoveryError, match="already exists"):
        backup_database(
            db_path=str(visit_repository.db_path.resolve()),
            backup_to=str(destination.resolve()),
        )


@pytest.mark.parametrize("limit", [0, 5001])
def test_limit_bounds_are_strict(visit_repository, limit):
    with pytest.raises(RecoveryError, match="between 1 and 5000"):
        recover(
            db_path=str(visit_repository.db_path.resolve()),
            site_id="site-a",
            limit=limit,
        )


def test_missing_relative_and_wrong_schema_database_are_rejected(
    visit_repository,
    tmp_path,
):
    with pytest.raises(RecoveryError, match="absolute"):
        recover(db_path="visits.sqlite3", site_id="site-a")
    with pytest.raises(RecoveryError, match="does not exist"):
        recover(db_path=str((tmp_path / "missing.sqlite3").resolve()), site_id="site-a")
    wrong = tmp_path / "wrong.sqlite3"
    with sqlite3.connect(wrong) as connection:
        connection.execute("CREATE TABLE unrelated(value TEXT)")
    with pytest.raises(RecoveryError, match="version"):
        recover(db_path=str(wrong.resolve()), site_id="site-a")


def test_cli_action_conflicts_and_backup_selection_are_rejected(
    visit_repository,
    tmp_path,
):
    db_path = str(visit_repository.db_path.resolve())
    with pytest.raises(SystemExit):
        main(["--db-path", db_path, "--site-id", "site-a", "--dry-run", "--apply"])
    with pytest.raises(SystemExit):
        main([
            "--db-path", db_path,
            "--site-id", "site-a",
            "--backup-to", str((tmp_path / "backup.sqlite3").resolve()),
        ])


@pytest.mark.parametrize(
    "extra",
    [
        ["--limit", "1"],
        ["--after-started-at", "2026-08-13T10:00:00.000Z"],
        ["--after-visit-id", "11111111-1111-4111-8111-111111111111"],
    ],
)
def test_backup_mode_rejects_every_recovery_selector(
    visit_repository,
    tmp_path,
    extra,
):
    with pytest.raises(SystemExit):
        main([
            "--db-path", str(visit_repository.db_path.resolve()),
            "--backup-to", str((tmp_path / "backup.sqlite3").resolve()),
            *extra,
        ])


def test_no_explicit_action_is_dry_run_with_exact_default_limit(
    visit_repository,
    capsys,
):
    assert main([
        "--db-path", str(visit_repository.db_path.resolve()),
        "--site-id", "site-a",
    ]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["mode"] == "dry-run"
    assert result["limit"] == 500
    assert result["resolved_db_path"] == str(visit_repository.db_path.resolve())
    assert result["schema_version"] == 2


def test_continuation_requires_canonical_complete_pair(visit_repository):
    path = str(visit_repository.db_path.resolve())
    with pytest.raises(RecoveryError, match="complete pair"):
        recover(
            db_path=path,
            site_id="site-a",
            after_started_at="2026-08-13T10:00:00.000Z",
        )
    with pytest.raises(RecoveryError, match="invalid|canonical"):
        recover(
            db_path=path,
            site_id="site-a",
            after_started_at="2026-08-13T10:00:00Z",
            after_visit_id="11111111-1111-4111-8111-111111111111",
        )


def test_recovery_query_plan_uses_existing_v2_indexes(visit_repository):
    with visit_repository._connect(readonly=True) as connection:  # noqa: SLF001
        authorization = " ".join(
            str(row[3]) for row in connection.execute(
                "EXPLAIN QUERY PLAN SELECT COUNT(*), MAX(authorized_at) "
                "FROM visit_authorizations WHERE visit_id=?",
                ("11111111-1111-4111-8111-111111111111",),
            )
        )
        visits = " ".join(
            str(row[3]) for row in connection.execute(
                "EXPLAIN QUERY PLAN SELECT * FROM visits "
                "WHERE site_id=? AND status='open' "
                "ORDER BY started_at ASC, visit_id ASC LIMIT 501",
                ("site-a",),
            )
        )
        events = " ".join(
            str(row[3]) for row in connection.execute(
                "EXPLAIN QUERY PLAN SELECT * FROM visit_source_events "
                "WHERE site_id=? AND client_mac=? "
                "AND controller_event_at>=? "
                "ORDER BY controller_event_at ASC, event_id ASC",
                (
                    "site-a",
                    "02:11:22:33:44:55",
                    "2026-08-13T10:00:00.000Z",
                ),
            )
        )

    assert "idx_visit_auth_visit_time" in authorization
    assert "idx_visits_site_status_started" in visits
    assert "idx_visit_events_site_controller" in events
