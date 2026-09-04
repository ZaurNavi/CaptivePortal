from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.analytics.historical_traffic import HistoricalTrafficReadService
from app.observations.repository import _schema_sql as observation_schema_sql
from app.traffic_projection.config import traffic_projection_config_from_settings
from app.traffic_projection.health import classify_projection_health
from app.traffic_projection.models import (
    PROJECTION_VERSION,
    ProjectionRunResult,
    TrafficProjectionDiverged,
    TrafficProjectionConfigError,
    TrafficProjectionStorageCorrupt,
)
from app.traffic_projection.repository import (
    REQUIRED_TABLES,
    TrafficProjectionRepository,
)
from app.traffic_projection.read_service import TrafficProjectionReadService
from app.traffic_projection.service import SEMANTIC_CONTRACT_SHA256
from app.traffic_projection.models import TrafficProjectionConfig
from app.traffic_projection.runtime import create_traffic_projection_runtime
from app.traffic_projection.service import TrafficProjectionService
from app.traffic_projection.source import (
    TrafficProjectionSource,
    source_revision_marker,
    source_semantic_fingerprint,
)


NOW = "2026-09-03T12:00:00.000Z"
SITE = "site-a"


def _observation_db(path):
    connection = sqlite3.connect(path)
    connection.executescript(observation_schema_sql())
    return connection


def _insert_cycle(
    connection,
    cycle_id="cycle-a",
    *,
    rate=1.0,
    site_id=SITE,
    started="2026-09-03T11:58:59.000Z",
    finished="2026-09-03T11:59:00.000Z",
):
    connection.execute(
        "INSERT INTO observation_cycles VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (cycle_id, "ap_dynamic", site_id, "completed", started, finished, None,
         1, "success", 1, 1, 1, 0, 0, 0, started, finished),
    )
    connection.execute(
        """INSERT INTO ap_observations(
           cycle_id,observed_at,site_id,ap_mac,partial,overview_ok,
           wired_uplink_ok,lan_traffic_ok,radios_ok,wired_observed_at,
           lan_observed_at,name,wired_download_mbps,wired_upload_mbps,
           wired_download_rate_reason,wired_upload_rate_reason,
           lan_rx_mbps,lan_tx_mbps,lan_rx_rate_reason,lan_tx_rate_reason)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (cycle_id, finished, site_id, "AA:BB:CC:DD:EE:FF", 0, 1, 1, 1, 1,
         finished, finished, "AP one", rate, rate + 1, "ok", "ok",
         rate + 2, rate + 3, "ok", "ok"),
    )
    connection.commit()


def _repository(tmp_path):
    repository = TrafficProjectionRepository(str(tmp_path / "projection.sqlite3"))
    assert repository.initialize() is True
    repository.ensure_version(SEMANTIC_CONTRACT_SHA256, NOW)
    repository.ensure_site(SITE)
    return repository


def test_schema_v1_exact_tables_indexes_and_read_only_connection(tmp_path):
    repository = _repository(tmp_path)
    with repository.read_connection() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert REQUIRED_TABLES <= {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        indexes = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
        }
        assert {
            "idx_projection_cycles_started",
            "idx_projection_cycles_finished",
            "idx_projection_cycles_lifecycle",
            "idx_projection_ap_cycle",
            "idx_projection_ap_identity",
            "idx_projection_one_active",
            "idx_projection_one_target",
        } <= indexes
        assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("DELETE FROM traffic_projection_versions")


def test_existing_partial_or_newer_schema_fails_without_recreation(tmp_path):
    path = tmp_path / "projection.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE traffic_projection_versions(x)")
    connection.execute("PRAGMA user_version=2")
    connection.commit()
    connection.close()
    with pytest.raises(TrafficProjectionStorageCorrupt):
        TrafficProjectionRepository(str(path)).initialize()
    assert sqlite3.connect(path).execute("PRAGMA user_version").fetchone()[0] == 2


def test_marker_is_metadata_only_and_fingerprint_is_ap_semantic(tmp_path):
    path = tmp_path / "observations.sqlite3"
    connection = _observation_db(path)
    _insert_cycle(connection)
    source = TrafficProjectionSource(str(path))
    projected = source.cycle(SITE, "cycle-a")
    assert projected is not None
    cycle = projected.cycle
    assert source_revision_marker(cycle) == projected.source_revision_marker
    changed_ap = [dict(projected.ap_rows[0], wired_download_mbps=99.0)]
    raw_shape = [dict(
        changed_ap[0], name=changed_ap[0]["historical_name"],
        wired_download_rate_reason=changed_ap[0]["wired_download_reason"],
        wired_upload_rate_reason=changed_ap[0]["wired_upload_reason"],
        lan_rx_mbps=changed_ap[0]["lan_download_mbps"],
        lan_tx_mbps=changed_ap[0]["lan_upload_mbps"],
        lan_rx_rate_reason=changed_ap[0]["lan_download_reason"],
        lan_tx_rate_reason=changed_ap[0]["lan_upload_reason"],
    )]
    assert source_revision_marker(cycle) == projected.source_revision_marker
    assert source_semantic_fingerprint(cycle, raw_shape) != projected.source_semantic_fingerprint


def test_atomic_cycle_upsert_is_idempotent_and_replaces_children(tmp_path):
    observation_path = tmp_path / "observations.sqlite3"
    connection = _observation_db(observation_path)
    _insert_cycle(connection)
    repository = _repository(tmp_path)
    projected = TrafficProjectionSource(str(observation_path)).cycle(SITE, "cycle-a")
    assert projected is not None
    assert repository.upsert_cycle(projected, NOW) is True
    assert repository.upsert_cycle(projected, NOW) is False
    state = repository.site_state(SITE)
    assert state is not None and state["projection_revision"] == 1
    with repository.read_connection() as read:
        assert read.execute("SELECT COUNT(*) FROM traffic_projection_cycles").fetchone()[0] == 1
        assert read.execute("SELECT COUNT(*) FROM traffic_projection_ap_cycles").fetchone()[0] == 1


def test_version_ready_and_global_activation_are_separate(tmp_path):
    repository = _repository(tmp_path)
    with pytest.raises(TrafficProjectionStorageCorrupt):
        repository.activate(NOW, (SITE,), {SITE: (NOW, "cycle-a")})
    with pytest.raises(TrafficProjectionStorageCorrupt):
        repository.mark_ready(NOW, (SITE,), {SITE: (NOW, "cycle-a")})
    with repository.write_connection() as connection:
        connection.execute(
            """UPDATE traffic_projection_site_state
               SET status='healthy',source_head_utc=?,source_head_cycle_id='cycle-a',
                   projection_head_utc=?,projection_head_cycle_id='cycle-a',
                   last_full_reconcile_completed_at=?,
                   last_full_reconcile_source_head_utc=?,
                   last_full_reconcile_source_head_cycle_id='cycle-a',
                   last_deep_audit_at=?,backlog_cycle_count=0
               WHERE projection_version=? AND site_id=?""",
            (NOW, NOW, NOW, NOW, NOW, PROJECTION_VERSION, SITE),
        )
        connection.commit()
    with pytest.raises(TrafficProjectionStorageCorrupt):
        repository.mark_ready(NOW, (SITE,), {SITE: (NOW, "cycle-a")})
    repository.update_site(
        SITE,
        source_boundary_proof_at=NOW,
        source_boundary_proof_head_utc=NOW,
        source_boundary_proof_head_cycle_id="cycle-a",
    )
    assert repository.site_state(SITE)["source_watermark_utc"] is None
    repository.mark_ready(NOW, (SITE,), {SITE: (NOW, "cycle-a")})
    assert repository.active_version() is None
    repository.activate(NOW, (SITE,), {SITE: (NOW, "cycle-a")})
    assert repository.active_version() == PROJECTION_VERSION


@pytest.mark.parametrize(
    ("flag", "bad_value"),
    [
        ("partial", 1),
        ("overview_ok", 0),
        ("wired_uplink_ok", 0),
        ("lan_traffic_ok", 0),
        ("radios_ok", 0),
    ],
)
def test_projection_rejects_canonical_raw_ap_bad_flags(
    tmp_path, flag, bad_value
):
    observation_path = tmp_path / "observations.sqlite3"
    connection = _observation_db(observation_path)
    _insert_cycle(connection)
    connection.execute(
        f"UPDATE ap_observations SET {flag}=? WHERE cycle_id='cycle-a'",
        (bad_value,),
    )
    connection.commit()
    projected = TrafficProjectionSource(str(observation_path)).cycle(SITE, "cycle-a")
    assert projected is not None
    assert projected.integrity_counts["bad_flag_count"] == 1
    assert projected.integrity_ok is False
    assert projected.metric_facts_present is False


def test_retention_uses_explicit_terminal_lifecycle_predicate(tmp_path):
    observation_path = tmp_path / "observations.sqlite3"
    connection = _observation_db(observation_path)
    repository = _repository(tmp_path)
    source = TrafficProjectionSource(str(observation_path))
    for cycle_id in ("running", "recent-finish", "recent-abandon", "fully-old"):
        _insert_cycle(connection, cycle_id)
        projected = source.cycle(SITE, cycle_id)
        assert projected is not None
        repository.upsert_cycle(projected, NOW)
    with repository.write_connection() as writer:
        writer.execute(
            "UPDATE traffic_projection_cycles SET source_state='running',"
            "source_started_at='2026-08-01T00:00:00.000Z',source_finished_at=NULL "
            "WHERE cycle_id='running'"
        )
        writer.execute(
            "UPDATE traffic_projection_cycles SET source_state='completed',"
            "source_started_at='2026-08-01T00:00:00.000Z',"
            "source_finished_at='2026-09-02T00:00:00.000Z' "
            "WHERE cycle_id='recent-finish'"
        )
        writer.execute(
            "UPDATE traffic_projection_cycles SET source_state='abandoned',"
            "source_started_at='2026-08-01T00:00:00.000Z',source_finished_at=NULL,"
            "source_abandoned_at='2026-09-02T00:00:00.000Z' "
            "WHERE cycle_id='recent-abandon'"
        )
        writer.execute(
            "UPDATE traffic_projection_cycles SET source_state='completed',"
            "source_started_at='2026-08-01T00:00:00.000Z',"
            "source_finished_at='2026-08-01T00:01:00.000Z' "
            "WHERE cycle_id='fully-old'"
        )
        writer.commit()
    assert repository.delete_before(
        SITE, "2026-09-01T00:00:00.000Z"
    ) == 1
    with repository.read_connection() as read:
        retained = {
            row[0]
            for row in read.execute("SELECT cycle_id FROM traffic_projection_cycles")
        }
    assert retained == {"running", "recent-finish", "recent-abandon"}


def test_projection_head_uses_full_started_at_cycle_id_tuple(tmp_path):
    observation_path = tmp_path / "observations.sqlite3"
    connection = _observation_db(observation_path)
    _insert_cycle(connection, "cycle-b")
    _insert_cycle(connection, "cycle-a")
    source = TrafficProjectionSource(str(observation_path))
    repository = _repository(tmp_path)
    repository.upsert_cycle(source.cycle(SITE, "cycle-a"), NOW)
    repository.upsert_cycle(source.cycle(SITE, "cycle-b"), NOW)
    state = repository.site_state(SITE)
    assert state is not None
    assert state["projection_head_cycle_id"] == "cycle-b"


@pytest.mark.parametrize(
    ("stored", "storage", "source", "expected"),
    [
        ("diverged", True, True, "diverged"),
        ("healthy", False, True, "unavailable"),
        ("rebuilding", True, True, "rebuilding"),
        ("healthy", True, False, "stale"),
    ],
)
def test_health_precedence(stored, storage, source, expected):
    state = {
        "projection_version": PROJECTION_VERSION,
        "projection_revision": 1,
        "status": stored,
        "source_head_utc": "2026-09-03T11:59:00.000Z",
        "projection_head_utc": "2026-09-03T11:59:00.000Z",
        "last_incremental_progress_at": NOW,
        "last_full_reconcile_completed_at": NOW,
    }
    assert classify_projection_health(
        state, now_utc=NOW, storage_available=storage, source_available=source
    ).status == expected


def test_health_unavailable_requires_projection_storage_version_or_site_state():
    state = {
        "projection_version": PROJECTION_VERSION,
        "projection_revision": 1,
        "status": "healthy",
        "source_head_utc": NOW,
        "projection_head_utc": NOW,
        "last_full_reconcile_completed_at": NOW,
    }
    assert classify_projection_health(
        state, now_utc=NOW, storage_available=False
    ).status == "unavailable"
    assert classify_projection_health(
        state, now_utc=NOW, version_available=False
    ).status == "unavailable"
    assert classify_projection_health(None, now_utc=NOW).status == "unavailable"
    assert classify_projection_health(
        state, now_utc=NOW, source_available=False
    ).status == "stale"


def test_config_defaults_are_dormant_and_enabled_paths_are_strict(tmp_path):
    disabled = traffic_projection_config_from_settings({
        "traffic_projection_db_path": object(),
        "observation_site_ids": object(),
    })
    assert disabled.enabled is False
    with pytest.raises(TrafficProjectionConfigError):
        traffic_projection_config_from_settings({
            "traffic_projection_enabled": "true",
            "traffic_projection_db_path": "relative.sqlite3",
            "observation_db_path": str(tmp_path / "observations.sqlite3"),
            "traffic_projection_writer_lock_path": str(tmp_path / "writer.lock"),
            "observation_site_ids": SITE,
        })


def test_worker_projects_without_automatic_read_activation(tmp_path):
    observation_path = tmp_path / "observations.sqlite3"
    connection = _observation_db(observation_path)
    _insert_cycle(connection)
    repository = TrafficProjectionRepository(str(tmp_path / "projection.sqlite3"))
    service = TrafficProjectionService(
        TrafficProjectionConfig(
            enabled=True,
            db_path=str(tmp_path / "projection.sqlite3"),
            writer_lock_path=str(tmp_path / "projection.lock"),
            source_db_path=str(observation_path),
            site_ids=(SITE,),
        ),
        repository=repository,
        clock=lambda: NOW,
    )
    result = service.run_once()[0]
    assert result.sweep_completed is True
    assert repository.cycle_count(
        SITE, from_utc="2026-08-20T00:00:00.000Z",
        through=("2026-09-03T11:58:59.000Z", "cycle-a"),
    ) == 1
    assert repository.active_version() is None
    service.mark_ready()
    assert repository.active_version() is None
    service.activate()
    assert repository.active_version() == PROJECTION_VERSION


def test_reconciliation_persists_unchanged_metadata_cursor_once_per_chunk(tmp_path):
    observation_path = tmp_path / "observations.sqlite3"
    connection = _observation_db(observation_path)
    for cycle_id in ("cycle-a", "cycle-b", "cycle-c"):
        _insert_cycle(connection, cycle_id)
    repository = TrafficProjectionRepository(str(tmp_path / "projection.sqlite3"))
    service = TrafficProjectionService(
        TrafficProjectionConfig(
            enabled=True,
            db_path=str(tmp_path / "projection.sqlite3"),
            writer_lock_path=str(tmp_path / "projection.lock"),
            source_db_path=str(observation_path),
            site_ids=(SITE,),
        ),
        repository=repository,
        clock=lambda: NOW,
    )
    service.run_once()
    calls: list[dict[str, object]] = []
    original = repository.update_site

    def recording_update(site_id, **fields):
        calls.append(fields)
        return original(site_id, **fields)

    repository.update_site = recording_update  # type: ignore[method-assign]
    service.reconcile_site(SITE)
    cursor_writes = [
        fields for fields in calls if "reconcile_cursor_started_at" in fields
    ]
    assert len(cursor_writes) <= 2
    assert len(calls) <= 3


def test_incremental_chunk_reuses_bounded_source_and_writer_connections(
    tmp_path, monkeypatch
):
    observation_path = tmp_path / "observations.sqlite3"
    connection = _observation_db(observation_path)
    for number in range(100):
        _insert_cycle(connection, f"cycle-{number:03d}")
    connection.close()
    repository = TrafficProjectionRepository(str(tmp_path / "projection.sqlite3"))
    source = TrafficProjectionSource(str(observation_path))
    service = TrafficProjectionService(
        TrafficProjectionConfig(
            enabled=True,
            db_path=str(tmp_path / "projection.sqlite3"),
            writer_lock_path=str(tmp_path / "projection.lock"),
            source_db_path=str(observation_path),
            site_ids=(SITE,),
        ),
        repository=repository,
        source=source,
        clock=lambda: NOW,
    )
    service.initialize()
    counts = {"source_connections": 0, "write_connections": 0}
    source_connection = source.connection
    write_connection = repository.write_connection

    @contextmanager
    def counted_source_connection():
        counts["source_connections"] += 1
        with source_connection() as opened:
            yield opened

    @contextmanager
    def counted_write_connection():
        counts["write_connections"] += 1
        with write_connection() as opened:
            yield opened

    monkeypatch.setattr(source, "connection", counted_source_connection)
    monkeypatch.setattr(repository, "write_connection", counted_write_connection)
    result = service.incremental_site(SITE, limit=100)

    assert result.cycles_examined == 100
    assert result.cycles_projected == 100
    assert counts == {"source_connections": 3, "write_connections": 2}


def test_bulk_writer_preserves_cycle_count_and_elapsed_bounds(tmp_path):
    observation_path = tmp_path / "observations.sqlite3"
    connection = _observation_db(observation_path)
    _insert_cycle(connection)
    connection.close()
    repository = _repository(tmp_path)
    projected = TrafficProjectionSource(str(observation_path)).cycle(
        SITE, "cycle-a"
    )
    first = replace(
        projected, cycle=dict(projected.cycle, cycle_id="bounded-a")
    )
    second = replace(
        projected, cycle=dict(projected.cycle, cycle_id="bounded-b")
    )
    ticks = iter((0.0, 2.0))
    written = repository.upsert_cycles(
        (first, second), NOW, monotonic=lambda: next(ticks)
    )
    assert tuple(cycle_id for cycle_id, _changed in written) == ("bounded-a",)
    assert repository.source_marker(SITE, "bounded-a") is not None
    assert repository.source_marker(SITE, "bounded-b") is None
    with pytest.raises(ValueError):
        repository.upsert_cycles((projected,) * 101, NOW)


def test_reconciliation_without_readable_source_head_never_completes_sweep(
    tmp_path, monkeypatch
):
    observation_path = tmp_path / "observations.sqlite3"
    _observation_db(observation_path).close()
    repository = _repository(tmp_path)
    repository.update_site(
        SITE,
        status="healthy",
        last_full_reconcile_completed_at="2026-09-03T11:55:00.000Z",
        last_full_reconcile_source_head_utc="2026-09-03T11:54:59.000Z",
        last_full_reconcile_source_head_cycle_id="old-head",
        last_deep_audit_at="2026-09-03T11:55:00.000Z",
        source_boundary_proof_at="2026-09-03T11:55:00.000Z",
        source_boundary_proof_head_utc="2026-09-03T11:54:59.000Z",
        source_boundary_proof_head_cycle_id="old-head",
    )
    service = TrafficProjectionService(
        TrafficProjectionConfig(
            enabled=True,
            db_path=str(tmp_path / "projection.sqlite3"),
            writer_lock_path=str(tmp_path / "projection.lock"),
            source_db_path=str(observation_path),
            site_ids=(SITE,),
        ),
        repository=repository,
        clock=lambda: NOW,
    )
    monkeypatch.setattr(service.source, "head", lambda _site_id: None)
    result = service.reconcile_site(SITE)
    state = repository.site_state(SITE)
    assert result.sweep_completed is False
    assert state["last_full_reconcile_completed_at"] == "2026-09-03T11:55:00.000Z"
    assert state["last_full_reconcile_source_head_cycle_id"] == "old-head"
    assert state["last_deep_audit_at"] == "2026-09-03T11:55:00.000Z"
    assert state["source_boundary_proof_head_cycle_id"] == "old-head"


def test_serve_forever_always_scans_head_but_reconciles_only_when_due(tmp_path):
    class OneIterationStop:
        stopped = False

        def is_set(self):
            return self.stopped

        def wait(self, _seconds):
            self.stopped = True

    service = TrafficProjectionService(
        TrafficProjectionConfig(
            enabled=True,
            db_path=str(tmp_path / "projection.sqlite3"),
            writer_lock_path=str(tmp_path / "projection.lock"),
            source_db_path=str(tmp_path / "observations.sqlite3"),
            site_ids=(SITE,),
        )
    )
    calls: list[str] = []
    service._stop = OneIterationStop()  # type: ignore[assignment]
    service.initialize = lambda: None  # type: ignore[method-assign]
    service.incremental_site = lambda _site, **_kwargs: calls.append("incremental")  # type: ignore[method-assign]
    service.reconcile_site = lambda _site, **_kwargs: calls.append("reconcile")  # type: ignore[method-assign]
    service._reconciliation_due = lambda _site: False  # type: ignore[method-assign]
    service._checkpoint_if_due = lambda: None  # type: ignore[method-assign]
    service._cleanup_if_due = lambda: None  # type: ignore[method-assign]
    service._owned_worker_services = lambda: (service,)  # type: ignore[method-assign]
    service.repository.active_version = lambda: service.projection_version  # type: ignore[method-assign]
    service.repository.site_state = lambda _site: {"status": "healthy"}  # type: ignore[method-assign]
    service.repository.version_status = lambda: "active"  # type: ignore[method-assign]
    service.serve_forever()
    assert calls == ["incremental"]

    calls.clear()
    service._stop = OneIterationStop()  # type: ignore[assignment]
    service._reconciliation_due = lambda _site: True  # type: ignore[method-assign]
    service.serve_forever()
    assert calls == ["incremental", "reconcile"]


def test_divergence_is_latched_until_explicit_repair(tmp_path):
    observation_path = tmp_path / "observations.sqlite3"
    connection = _observation_db(observation_path)
    _insert_cycle(connection)
    repository = TrafficProjectionRepository(str(tmp_path / "projection.sqlite3"))
    service = TrafficProjectionService(
        TrafficProjectionConfig(
            enabled=True,
            db_path=str(tmp_path / "projection.sqlite3"),
            writer_lock_path=str(tmp_path / "projection.lock"),
            source_db_path=str(observation_path),
            site_ids=(SITE,),
        ),
        repository=repository,
        clock=lambda: NOW,
    )
    service.run_once()
    repository.update_site(SITE, status="diverged", last_error_category="audit")
    with pytest.raises(TrafficProjectionDiverged):
        service.incremental_site(SITE)
    with pytest.raises(TrafficProjectionDiverged):
        service.reconcile_site(SITE)
    assert repository.site_state(SITE)["status"] == "diverged"


def test_site_repair_invalidates_old_proof_and_completes_full_reconcile(tmp_path):
    observation_path = tmp_path / "observations.sqlite3"
    connection = _observation_db(observation_path)
    _insert_cycle(connection)
    repository = TrafficProjectionRepository(str(tmp_path / "projection.sqlite3"))
    service = TrafficProjectionService(
        TrafficProjectionConfig(
            enabled=True,
            db_path=str(tmp_path / "projection.sqlite3"),
            writer_lock_path=str(tmp_path / "projection.lock"),
            source_db_path=str(observation_path),
            site_ids=(SITE,),
        ),
        repository=repository,
        clock=lambda: NOW,
    )
    service.run_once()
    repository.update_site(
        SITE,
        status="diverged",
        last_full_reconcile_completed_at="2026-09-03T10:00:00.000Z",
        last_full_reconcile_source_head_utc="2026-09-03T10:00:00.000Z",
        last_full_reconcile_source_head_cycle_id="old-head",
        last_deep_audit_at="2026-09-03T10:00:00.000Z",
    )
    proof_at_reconcile: list[tuple[object, ...]] = []
    original = service.reconcile_site

    def inspecting_reconcile(site_id, **kwargs):
        state = repository.site_state(site_id)
        proof_at_reconcile.append((
            state["last_full_reconcile_completed_at"],
            state["last_full_reconcile_source_head_utc"],
            state["last_full_reconcile_source_head_cycle_id"],
            state["last_deep_audit_at"],
            state["projection_head_utc"],
            state["fast_checkpoint_started_at"],
            state["last_incremental_progress_at"],
            state["last_success_at"],
        ))
        return original(site_id, **kwargs)

    service.reconcile_site = inspecting_reconcile  # type: ignore[method-assign]
    result = service.repair_site(SITE)
    assert result.sweep_completed is True
    assert proof_at_reconcile[0] == (None,) * 8
    state = repository.site_state(SITE)
    assert state["status"] == "healthy"
    assert state["last_full_reconcile_completed_at"] == NOW
    assert state["last_deep_audit_at"] == NOW


def test_mark_ready_rejects_stale_health_text_without_current_proof(tmp_path):
    repository = _repository(tmp_path)
    with repository.write_connection() as connection:
        connection.execute(
            """UPDATE traffic_projection_site_state
               SET status='healthy',source_head_utc=?,source_head_cycle_id='cycle-b',
                   projection_head_utc=?,projection_head_cycle_id='cycle-a',
                   last_full_reconcile_completed_at=?,
                   last_full_reconcile_source_head_utc=?,
                   last_full_reconcile_source_head_cycle_id='cycle-a',
                   last_deep_audit_at=?,backlog_cycle_count=0
               WHERE projection_version=? AND site_id=?""",
            (NOW, NOW, NOW, NOW, NOW, PROJECTION_VERSION, SITE),
        )
        connection.commit()
    with pytest.raises(TrafficProjectionStorageCorrupt):
        repository.mark_ready(NOW, (SITE,), {SITE: (NOW, "cycle-b")})


def test_service_mark_ready_rechecks_current_retained_identity(tmp_path):
    observation_path = tmp_path / "observations.sqlite3"
    connection = _observation_db(observation_path)
    _insert_cycle(connection)
    repository = TrafficProjectionRepository(str(tmp_path / "projection.sqlite3"))
    service = TrafficProjectionService(
        TrafficProjectionConfig(
            enabled=True,
            db_path=str(tmp_path / "projection.sqlite3"),
            writer_lock_path=str(tmp_path / "projection.lock"),
            source_db_path=str(observation_path),
            site_ids=(SITE,),
        ),
        repository=repository,
        clock=lambda: NOW,
    )
    service.run_once()
    with repository.write_connection() as writer:
        writer.execute(
            "DELETE FROM traffic_projection_cycles WHERE projection_version=? "
            "AND site_id=?",
            (PROJECTION_VERSION, SITE),
        )
        writer.commit()
    with pytest.raises(TrafficProjectionDiverged):
        service.mark_ready()
    assert repository.site_state(SITE)["status"] == "diverged"


def test_disabled_runtime_does_not_create_projection_database(tmp_path):
    path = tmp_path / "projection.sqlite3"
    runtime = create_traffic_projection_runtime(
        {
            "traffic_projection_enabled": "false",
            "traffic_projection_db_path": str(path),
        },
        __import__("logging").getLogger("projection-test"),
    )
    assert runtime.state == "disabled"
    assert not path.exists()


def test_deep_audit_detects_ap_semantic_change_without_metadata_change(tmp_path):
    observation_path = tmp_path / "observations.sqlite3"
    connection = _observation_db(observation_path)
    _insert_cycle(connection)
    repository = TrafficProjectionRepository(str(tmp_path / "projection.sqlite3"))
    service = TrafficProjectionService(
        TrafficProjectionConfig(
            enabled=True,
            db_path=str(tmp_path / "projection.sqlite3"),
            writer_lock_path=str(tmp_path / "projection.lock"),
            source_db_path=str(observation_path),
            site_ids=(SITE,),
        ),
        repository=repository,
        clock=lambda: NOW,
    )
    service.run_once()
    connection.execute(
        "UPDATE ap_observations SET wired_download_mbps=99 WHERE cycle_id='cycle-a'"
    )
    connection.commit()
    connection.close()
    with pytest.raises(TrafficProjectionDiverged):
        service._deep_audit(  # noqa: SLF001 - direct focused audit contract
            SITE, tuple_head=("2026-09-03T11:58:59.000Z", "cycle-a")
        )
    assert repository.site_state(SITE)["status"] == "diverged"


def test_deep_audit_is_bounded_to_captured_sweep_head(tmp_path):
    observation_path = tmp_path / "observations.sqlite3"
    connection = _observation_db(observation_path)
    _insert_cycle(connection, "cycle-a", rate=1.0)
    connection.execute(
        "UPDATE observation_cycles SET started_at='2026-09-03T11:59:30.000Z',"
        "finished_at='2026-09-03T11:59:31.000Z',updated_at='2026-09-03T11:59:31.000Z' "
        "WHERE cycle_id='cycle-a'"
    )
    connection.execute(
        "UPDATE ap_observations SET observed_at='2026-09-03T11:59:31.000Z',"
        "wired_observed_at='2026-09-03T11:59:31.000Z',"
        "lan_observed_at='2026-09-03T11:59:31.000Z' WHERE cycle_id='cycle-a'"
    )
    _insert_cycle(connection, "cycle-z", rate=2.0)
    connection.execute(
        "UPDATE observation_cycles SET started_at='2026-09-03T11:59:45.000Z',"
        "finished_at='2026-09-03T11:59:46.000Z',updated_at='2026-09-03T11:59:46.000Z' "
        "WHERE cycle_id='cycle-z'"
    )
    connection.execute(
        "UPDATE ap_observations SET observed_at='2026-09-03T11:59:46.000Z',"
        "wired_observed_at='2026-09-03T11:59:46.000Z',"
        "lan_observed_at='2026-09-03T11:59:46.000Z' WHERE cycle_id='cycle-z'"
    )
    connection.commit()
    source = TrafficProjectionSource(str(observation_path))
    repository = _repository(tmp_path)
    repository.upsert_cycle(source.cycle(SITE, "cycle-a"), NOW)
    repository.upsert_cycle(source.cycle(SITE, "cycle-z"), NOW)
    connection.execute(
        "UPDATE ap_observations SET wired_download_mbps=999 WHERE cycle_id='cycle-z'"
    )
    connection.commit()
    service = TrafficProjectionService(
        TrafficProjectionConfig(
            enabled=True,
            db_path=str(tmp_path / "projection.sqlite3"),
            writer_lock_path=str(tmp_path / "projection.lock"),
            source_db_path=str(observation_path),
            site_ids=(SITE,),
        ),
        repository=repository,
        source=source,
        clock=lambda: NOW,
    )
    assert service._deep_audit(  # noqa: SLF001
        SITE, tuple_head=("2026-09-03T11:59:30.000Z", "cycle-a")
    ) == 1


def test_diverged_site_rejects_range_rebuild_without_changing_evidence(tmp_path):
    observation_path = tmp_path / "observations.sqlite3"
    connection = _observation_db(observation_path)
    _insert_cycle(connection)
    repository = TrafficProjectionRepository(str(tmp_path / "projection.sqlite3"))
    service = TrafficProjectionService(
        TrafficProjectionConfig(
            enabled=True,
            db_path=str(tmp_path / "projection.sqlite3"),
            writer_lock_path=str(tmp_path / "projection.lock"),
            source_db_path=str(observation_path),
            site_ids=(SITE,),
        ),
        repository=repository,
        clock=lambda: NOW,
    )
    service.run_once()
    repository.update_site(
        SITE, status="diverged", last_error_category="deep_fingerprint"
    )
    before = repository.site_state(SITE)
    with pytest.raises(TrafficProjectionDiverged):
        service.rebuild_range(
            SITE,
            from_utc="2026-09-03T11:00:00.000Z",
            to_utc="2026-09-03T12:00:00.000Z",
        )
    after = repository.site_state(SITE)
    assert after["status"] == "diverged"
    assert after["last_error_category"] == "deep_fingerprint"
    assert after["projection_revision"] == before["projection_revision"]


def test_interrupted_site_repair_stays_rebuilding_and_resumes(tmp_path):
    observation_path = tmp_path / "observations.sqlite3"
    connection = _observation_db(observation_path)
    for cycle_id in ("cycle-a", "cycle-b", "cycle-c"):
        _insert_cycle(connection, cycle_id)
    repository = TrafficProjectionRepository(str(tmp_path / "projection.sqlite3"))
    config = TrafficProjectionConfig(
        enabled=True,
        db_path=str(tmp_path / "projection.sqlite3"),
        writer_lock_path=str(tmp_path / "projection.lock"),
        source_db_path=str(observation_path),
        site_ids=(SITE,),
    )
    service = TrafficProjectionService(
        config, repository=repository, clock=lambda: NOW
    )
    service.run_once()
    repository.begin_site_repair(SITE)
    with repository.write_connection() as writer:
        writer.execute(
            "DELETE FROM traffic_projection_cycles WHERE projection_version=? "
            "AND site_id=?",
            (repository.projection_version, SITE),
        )
        writer.commit()
    first = service.reconcile_site(SITE, limit=1, allow_diverged=True)
    assert first.sweep_completed is False
    interrupted = repository.site_state(SITE)
    assert interrupted["status"] == "rebuilding"
    assert interrupted["reconcile_sweep_started_at"] is not None

    resumed = TrafficProjectionService(
        config, repository=repository, clock=lambda: NOW
    )
    result = resumed.repair_site(SITE)
    while not result.sweep_completed:
        result = resumed.repair_site(SITE)
    assert result.sweep_completed is True
    assert repository.site_state(SITE)["status"] == "healthy"


def test_bounded_site_repair_keeps_other_active_site_maintained(tmp_path):
    other_site = "site-b"
    observation_path = tmp_path / "observations.sqlite3"
    connection = _observation_db(observation_path)
    for number in range(102):
        _insert_cycle(connection, f"site-a-{number:03d}", site_id=SITE)
    _insert_cycle(connection, "site-b-initial", site_id=other_site)
    repository = TrafficProjectionRepository(str(tmp_path / "projection.sqlite3"))
    config = TrafficProjectionConfig(
        enabled=True,
        db_path=str(tmp_path / "projection.sqlite3"),
        writer_lock_path=str(tmp_path / "projection.lock"),
        source_db_path=str(observation_path),
        site_ids=(SITE, other_site),
    )
    service = TrafficProjectionService(
        config, repository=repository, clock=lambda: NOW
    )
    service.run_once()
    service.mark_ready()
    service.activate()

    started = service.repair_site(SITE)
    assert started.sweep_completed is False
    assert repository.site_state(SITE)["status"] == "rebuilding"
    _insert_cycle(
        connection,
        "site-b-new",
        site_id=other_site,
        started="2026-09-03T11:59:29.000Z",
        finished="2026-09-03T11:59:30.000Z",
    )
    repository.update_site(other_site, last_full_reconcile_completed_at=None)

    first_worker = TrafficProjectionService(
        config, repository=repository, clock=lambda: NOW
    )
    first_worker.worker_iteration()
    assert repository.source_marker(other_site, "site-b-new") is not None
    assert first_worker.health(other_site)["status"] == "healthy"
    assert repository.site_state(SITE)["status"] == "rebuilding"

    restarted_worker = TrafficProjectionService(
        config, repository=repository, clock=lambda: NOW
    )
    restarted_worker.worker_iteration()
    assert restarted_worker.health(other_site)["status"] == "healthy"
    assert repository.site_state(SITE)["status"] == "healthy"


def test_health_uses_current_source_head_progress_and_version_state(tmp_path):
    observation_path = tmp_path / "observations.sqlite3"
    connection = _observation_db(observation_path)
    _insert_cycle(connection)
    repository = TrafficProjectionRepository(str(tmp_path / "projection.sqlite3"))
    config = TrafficProjectionConfig(
        enabled=True,
        db_path=str(tmp_path / "projection.sqlite3"),
        writer_lock_path=str(tmp_path / "projection.lock"),
        source_db_path=str(observation_path),
        site_ids=(SITE,),
    )
    service = TrafficProjectionService(
        config, repository=repository, clock=lambda: NOW
    )
    service.run_once()
    assert service.health(SITE)["status"] == "rebuilding"
    service.mark_ready()
    assert service.health(SITE)["status"] == "rebuilding"
    service.activate()
    assert service.health(SITE)["status"] == "healthy"

    with repository.write_connection() as writer:
        writer.execute(
            "UPDATE traffic_projection_versions SET semantic_contract_sha256=? "
            "WHERE projection_version=?",
            ("0" * 64, repository.projection_version),
        )
        writer.commit()
    assert service.health(SITE)["status"] == "unavailable"
    with repository.write_connection() as writer:
        writer.execute(
            "UPDATE traffic_projection_versions SET semantic_contract_sha256=? "
            "WHERE projection_version=?",
            (SEMANTIC_CONTRACT_SHA256, repository.projection_version),
        )
        writer.commit()

    _insert_cycle(
        connection,
        "cycle-new",
        started="2026-09-03T12:02:59.000Z",
        finished="2026-09-03T12:03:00.000Z",
    )
    assert service.health(SITE)["status"] != "healthy"

    connection.execute("DELETE FROM observation_cycles")
    connection.execute("DELETE FROM ap_observations")
    connection.commit()
    assert service.health(SITE)["status"] == "stale"


def test_quiet_healthy_site_does_not_require_recent_incremental_progress(tmp_path):
    observation_path = tmp_path / "observations.sqlite3"
    connection = _observation_db(observation_path)
    _insert_cycle(connection)
    repository = TrafficProjectionRepository(str(tmp_path / "projection.sqlite3"))
    service = TrafficProjectionService(
        TrafficProjectionConfig(
            enabled=True,
            db_path=str(tmp_path / "projection.sqlite3"),
            writer_lock_path=str(tmp_path / "projection.lock"),
            source_db_path=str(observation_path),
            site_ids=(SITE,),
        ),
        repository=repository,
        clock=lambda: NOW,
    )
    service.run_once()
    service.mark_ready()
    service.activate()
    repository.update_site(
        SITE, last_incremental_progress_at="2026-09-03T11:00:00.000Z"
    )
    assert service.health(SITE)["status"] == "healthy"


def test_single_writer_maintains_active_while_building_target_and_activates(
    tmp_path,
):
    observation_path = tmp_path / "observations.sqlite3"
    connection = _observation_db(observation_path)
    _insert_cycle(connection)
    source = TrafficProjectionSource(str(observation_path))
    projected = source.cycle(SITE, "cycle-a")
    alternative_semantic = hashlib.sha256(b"supported-test-v2").hexdigest()
    supported = {SEMANTIC_CONTRACT_SHA256, alternative_semantic}
    db_path = str(tmp_path / "projection.sqlite3")
    version_a = TrafficProjectionRepository(db_path, projection_version="version-a")
    version_b = TrafficProjectionRepository(db_path, projection_version="version-b")
    version_a.initialize()

    def build(repository, semantic):
        repository.ensure_version(semantic, NOW)
        repository.ensure_site(SITE)
        repository.upsert_cycle(projected, NOW)
        repository.update_site(
            SITE,
            status="healthy",
            source_head_utc="2026-09-03T11:58:59.000Z",
            source_head_cycle_id="cycle-a",
            last_full_reconcile_completed_at=NOW,
            last_full_reconcile_source_head_utc="2026-09-03T11:58:59.000Z",
            last_full_reconcile_source_head_cycle_id="cycle-a",
            last_deep_audit_at=NOW,
            backlog_cycle_count=0,
            available_from_utc="2026-09-03T11:59:00.000Z",
            available_through_utc="2026-09-03T11:59:00.000Z",
            source_watermark_utc="2026-09-03T11:59:00.000Z",
            source_boundary_proof_at=NOW,
            source_boundary_proof_head_utc="2026-09-03T11:58:59.000Z",
            source_boundary_proof_head_cycle_id="cycle-a",
        )

    build(version_a, SEMANTIC_CONTRACT_SHA256)
    version_a.mark_ready(
        NOW, (SITE,), {SITE: ("2026-09-03T11:58:59.000Z", "cycle-a")}
    )
    version_a.activate(
        NOW,
        (SITE,),
        {SITE: ("2026-09-03T11:58:59.000Z", "cycle-a")},
    )
    build(version_b, alternative_semantic)
    assert version_a.active_version() == "version-a"
    active_result = HistoricalTrafficReadService(TrafficProjectionReadService(
        version_b,
        current_observation_db_path=str(observation_path),
        clock=lambda: NOW,
        supported_semantic_contracts=supported,
    )).get_site_history(
        SITE,
        from_utc="2026-09-03T11:00:00.000Z",
        to_utc=NOW,
        evaluated_at_utc=NOW,
    )
    assert active_result.status in {"ok", "partial"}
    assert version_b.cycle_count(
        SITE,
        from_utc="2026-09-03T00:00:00.000Z",
        through=("2026-09-03T11:58:59.000Z", "cycle-a"),
    ) == 1
    with pytest.raises(TrafficProjectionStorageCorrupt):
        version_b.activate(
            NOW,
            (SITE,),
            {SITE: ("2026-09-03T11:58:59.000Z", "cycle-a")},
        )
    assert version_a.active_version() == "version-a"

    _insert_cycle(
        connection,
        "cycle-b",
        started="2026-09-03T11:59:29.000Z",
        finished="2026-09-03T11:59:30.000Z",
    )
    version_a.update_site(SITE, last_full_reconcile_completed_at=None)
    version_b.update_site(SITE, last_full_reconcile_completed_at=None)
    worker = TrafficProjectionService(
        TrafficProjectionConfig(
            enabled=True,
            db_path=db_path,
            writer_lock_path=str(tmp_path / "projection.lock"),
            source_db_path=str(observation_path),
            site_ids=(SITE,),
        ),
        repository=version_b,
        source=source,
        clock=lambda: NOW,
        projection_version="version-b",
        semantic_contract_sha256=alternative_semantic,
        supported_semantic_contracts=supported,
    )
    iteration = worker.worker_iteration()
    assert tuple(iteration) == ("version-a", "version-b")
    assert version_a.source_marker(SITE, "cycle-b") is not None
    assert version_b.source_marker(SITE, "cycle-b") is not None
    assert version_a.active_version() == "version-a"

    version_b.mark_ready(
        NOW, (SITE,), {SITE: ("2026-09-03T11:59:29.000Z", "cycle-b")}
    )
    _insert_cycle(
        connection,
        "cycle-c",
        started="2026-09-03T11:59:44.000Z",
        finished="2026-09-03T11:59:45.000Z",
    )
    with pytest.raises(TrafficProjectionStorageCorrupt):
        worker.activate()
    assert version_b.version_status() == "ready"
    assert version_a.active_version() == "version-a"

    version_a.update_site(SITE, last_full_reconcile_completed_at=None)
    version_b.update_site(SITE, last_full_reconcile_completed_at=None)
    ready_iteration = worker.worker_iteration()
    assert tuple(ready_iteration) == ("version-a", "version-b")
    assert version_a.source_marker(SITE, "cycle-c") is not None
    assert version_b.source_marker(SITE, "cycle-c") is not None
    assert version_b.version_status() == "ready"
    assert version_a.active_version() == "version-a"

    worker.activate()
    assert version_b.active_version() == "version-b"
    assert version_a.version_status("version-a") == "retired"
    new_active = HistoricalTrafficReadService(TrafficProjectionReadService(
        version_b,
        current_observation_db_path=str(observation_path),
        clock=lambda: NOW,
        supported_semantic_contracts=supported,
    )).get_site_history(
        SITE,
        from_utc="2026-09-03T11:00:00.000Z",
        to_utc=NOW,
        evaluated_at_utc=NOW,
    )
    assert new_active.status in {"ok", "partial"}


def test_target_work_is_bounded_and_active_is_revisited_between_quanta(
    tmp_path, monkeypatch
):
    calls: list[tuple[str, int | None]] = []

    class FakeRepository:
        projection_version = "version-a"

        @staticmethod
        def active_version():
            return "version-a"

        @staticmethod
        def site_state(_site_id):
            return {"status": "healthy"}

        @staticmethod
        def version_status():
            return "active"

    class FakeService:
        def __init__(self, version, status):
            self.projection_version = version
            self.config = TrafficProjectionConfig(
                enabled=True,
                db_path=str(tmp_path / "projection.sqlite3"),
                writer_lock_path=str(tmp_path / "projection.lock"),
                source_db_path=str(tmp_path / "observations.sqlite3"),
                site_ids=(SITE,),
            )
            self.repository = FakeRepository()
            self.repository.version_status = lambda: status

        @staticmethod
        def initialize():
            return None

        def incremental_site(
            self, site_id, *, limit=100, work_deadline_monotonic=None
        ):
            calls.append((f"{self.projection_version}:incremental", limit))
            if self.projection_version == "version-b":
                assert work_deadline_monotonic is not None
            return ProjectionRunResult(site_id, 0, 0, 0, 0, 0, 0, False)

        def _reconciliation_due(self, _site_id):
            return self.projection_version == "version-b"

        def reconcile_site(
            self,
            site_id,
            *,
            limit=5000,
            work_deadline_monotonic=None,
            completion_deadline_monotonic=None,
        ):
            calls.append((f"{self.projection_version}:reconcile", limit))
            assert work_deadline_monotonic is not None
            return ProjectionRunResult(site_id, limit, 0, 0, 0, 0, 0, False)

    owner = TrafficProjectionService(
        TrafficProjectionConfig(
            enabled=True,
            db_path=str(tmp_path / "projection.sqlite3"),
            writer_lock_path=str(tmp_path / "projection.lock"),
            source_db_path=str(tmp_path / "observations.sqlite3"),
            site_ids=(SITE,),
        ),
        repository=FakeRepository(),  # type: ignore[arg-type]
        projection_version="version-a",
    )
    active = FakeService("version-a", "active")
    target = FakeService("version-b", "building")
    monkeypatch.setattr(owner, "_owned_worker_services", lambda: (active, target))
    monkeypatch.setattr(owner, "_checkpoint_if_due", lambda: None)

    owner.worker_iteration()
    owner.worker_iteration()

    assert calls == [
        ("version-a:incremental", 100),
        ("version-b:incremental", 100),
        ("version-b:reconcile", 100),
        ("version-a:incremental", 100),
        ("version-b:incremental", 100),
        ("version-b:reconcile", 100),
    ]


def test_scheduler_runs_multiple_target_quanta_between_active_deadlines(
    tmp_path, monkeypatch
):
    class FakeClock:
        now = 0.0

        def __call__(self):
            return self.now

    class StopAfterSecondActive:
        stopped = False

        def is_set(self):
            return self.stopped

        def wait(self, seconds):
            if not self.stopped:
                clock.now += seconds

    class FakeVersion:
        def __init__(self, version):
            self.projection_version = version
            self.config = TrafficProjectionConfig(
                enabled=True,
                db_path=str(tmp_path / "projection.sqlite3"),
                writer_lock_path=str(tmp_path / "projection.lock"),
                source_db_path=str(tmp_path / "observations.sqlite3"),
                site_ids=(SITE,),
            )

    clock = FakeClock()
    stop = StopAfterSecondActive()
    owner = TrafficProjectionService(
        TrafficProjectionConfig(
            enabled=True,
            db_path=str(tmp_path / "projection.sqlite3"),
            writer_lock_path=str(tmp_path / "projection.lock"),
            source_db_path=str(tmp_path / "observations.sqlite3"),
            site_ids=(SITE,),
        ),
        monotonic=clock,
    )
    owner._stop = stop  # type: ignore[assignment]
    active = FakeVersion("version-a")
    target = FakeVersion("version-b")
    events: list[tuple[str, float, float | None, int]] = []
    active_count = 0

    def maintain(service, *, is_target, active_deadline_monotonic=None):
        nonlocal active_count
        if not is_target:
            active_count += 1
            events.append(("active", clock.now, None, 0))
            if active_count == 2:
                stop.stopped = True
            return ()
        clock.now += 0.25
        result = ProjectionRunResult(SITE, 100, 100, 0, 0, 0, 0, False)
        events.append(("target", clock.now, active_deadline_monotonic, 100))
        return (result,)

    monkeypatch.setattr(
        owner, "_worker_services_by_role", lambda: ((active,), (target,))
    )
    monkeypatch.setattr(owner, "_maintain_version", maintain)
    monkeypatch.setattr(owner, "_cleanup_if_due", lambda: None)
    monkeypatch.setattr(owner, "_checkpoint_if_due", lambda: None)
    owner.serve_forever()

    active_events = [event for event in events if event[0] == "active"]
    target_events = [event for event in events if event[0] == "target"]
    assert [event[1] for event in active_events] == [0.0, 15.0]
    assert len(target_events) > 1
    assert all(event[1] < 15.0 for event in target_events)
    assert all(event[2] == 15.0 for event in target_events)
    assert all(event[3] <= 100 for event in target_events)


def test_target_quanta_rotate_across_configured_sites(tmp_path):
    calls: list[str] = []

    class FakeRepository:
        @staticmethod
        def site_state(_site_id):
            return {"status": "rebuilding"}

        @staticmethod
        def version_status():
            return "building"

    class FakeTarget:
        projection_version = "version-b"
        repository = FakeRepository()
        config = TrafficProjectionConfig(
            enabled=True,
            db_path=str(tmp_path / "projection.sqlite3"),
            writer_lock_path=str(tmp_path / "projection.lock"),
            source_db_path=str(tmp_path / "observations.sqlite3"),
            site_ids=(SITE, "site-b"),
        )

        @staticmethod
        def initialize():
            return None

        @staticmethod
        def incremental_site(site_id, **_kwargs):
            calls.append(site_id)
            return ProjectionRunResult(site_id, 100, 100, 0, 0, 0, 0, False)

        @staticmethod
        def _reconciliation_due(_site_id):
            return False

    owner = TrafficProjectionService(FakeTarget.config)
    target = FakeTarget()
    owner._maintain_version(target, is_target=True)  # type: ignore[arg-type]
    owner._maintain_version(target, is_target=True)  # type: ignore[arg-type]
    assert calls == [SITE, "site-b"]


def test_scheduler_structure_can_dispatch_frozen_rebuild_quanta_within_600s(
    tmp_path, monkeypatch
):
    class FakeClock:
        now = 0.0

        def __call__(self):
            return self.now

    class FakeTarget:
        projection_version = "version-b"
        config = TrafficProjectionConfig(
            enabled=True,
            db_path=str(tmp_path / "projection.sqlite3"),
            writer_lock_path=str(tmp_path / "projection.lock"),
            source_db_path=str(tmp_path / "observations.sqlite3"),
            site_ids=(SITE,),
        )

    clock = FakeClock()
    owner = TrafficProjectionService(FakeTarget.config, monotonic=clock)
    remaining_cycles = 40_320
    quantum_count = 0

    def maintain(_service, *, is_target, active_deadline_monotonic=None):
        nonlocal remaining_cycles, quantum_count
        assert is_target is True
        assert active_deadline_monotonic is not None
        examined = min(100, remaining_cycles)
        remaining_cycles -= examined
        quantum_count += int(examined > 0)
        clock.now += 1.0
        return (
            ProjectionRunResult(
                SITE, examined, examined, 0, 0, 0, 0,
                remaining_cycles == 0 and examined > 0,
            ),
        )

    monkeypatch.setattr(owner, "_maintain_version", maintain)
    active_passes: list[float] = []
    while remaining_cycles and clock.now < 600.0:
        active_passes.append(clock.now)
        active_deadline = clock.now + 15.0
        owner._target_window(
            (FakeTarget(),),
            active_deadline_monotonic=active_deadline,
        )
        clock.now = active_deadline

    assert remaining_cycles == 0
    assert quantum_count == 404
    assert clock.now <= 600.0
    assert all(
        later - earlier <= 15.0
        for earlier, later in zip(active_passes, active_passes[1:])
    )


def test_failed_target_preserves_active_version_and_cannot_activate(tmp_path):
    db_path = str(tmp_path / "projection.sqlite3")
    active = TrafficProjectionRepository(db_path, projection_version="version-a")
    target = TrafficProjectionRepository(db_path, projection_version="version-b")
    active.initialize()
    active.ensure_version(SEMANTIC_CONTRACT_SHA256, NOW)
    with active.write_connection() as connection:
        connection.execute(
            "UPDATE traffic_projection_versions SET status='ready' "
            "WHERE projection_version='version-a'"
        )
        connection.commit()
    active.ensure_site(SITE)
    with active.write_connection() as connection:
        connection.execute(
            """UPDATE traffic_projection_site_state
               SET status='healthy',source_head_utc=?,source_head_cycle_id='cycle-a',
                   projection_head_utc=?,projection_head_cycle_id='cycle-a',
                   last_full_reconcile_completed_at=?,
                   last_full_reconcile_source_head_utc=?,
                   last_full_reconcile_source_head_cycle_id='cycle-a',
                   last_deep_audit_at=?,backlog_cycle_count=0,
                   source_boundary_proof_at=?,source_boundary_proof_head_utc=?,
                   source_boundary_proof_head_cycle_id='cycle-a'
               WHERE projection_version='version-a' AND site_id=?""",
            (NOW, NOW, NOW, NOW, NOW, NOW, NOW, SITE),
        )
        connection.commit()
    active.activate(NOW, (SITE,), {SITE: (NOW, "cycle-a")})
    target.ensure_version(SEMANTIC_CONTRACT_SHA256, NOW)
    target_service = TrafficProjectionService(
        TrafficProjectionConfig(
            enabled=True,
            db_path=db_path,
            writer_lock_path=str(tmp_path / "projection.lock"),
            source_db_path=str(tmp_path / "observations.sqlite3"),
            site_ids=(SITE,),
        ),
        repository=target,
        clock=lambda: NOW,
        projection_version="version-b",
    )
    target_service.fail_version()
    assert target.version_status() == "failed"
    assert active.active_version() == "version-a"
    with pytest.raises(TrafficProjectionStorageCorrupt):
        target.mark_ready(NOW, (SITE,), {SITE: (NOW, "cycle-a")})
    with pytest.raises(TrafficProjectionStorageCorrupt):
        target.activate(NOW, (SITE,), {SITE: (NOW, "cycle-a")})
    assert active.active_version() == "version-a"


def test_cleanup_is_bounded_site_and_version_aware(tmp_path):
    observation_path = tmp_path / "observations.sqlite3"
    connection = _observation_db(observation_path)
    _insert_cycle(connection)
    source = TrafficProjectionSource(str(observation_path))
    projected = source.cycle(SITE, "cycle-a")
    repository = _repository(tmp_path)
    with repository.write_connection() as writer:
        writer.execute(
            "UPDATE traffic_projection_versions SET status='active' "
            "WHERE projection_version=?",
            (repository.projection_version,),
        )
        writer.commit()
    other_version = TrafficProjectionRepository(
        str(tmp_path / "projection.sqlite3"), projection_version="other-version"
    )
    other_version.ensure_version(SEMANTIC_CONTRACT_SHA256, NOW)
    other_version.ensure_site(SITE)
    other_version.upsert_cycle(
        replace(projected, cycle=dict(projected.cycle, cycle_id="other-version")),
        NOW,
    )
    repository.ensure_site("site-b")
    for cycle_id in ("old-a", "old-b"):
        repository.upsert_cycle(
            replace(projected, cycle=dict(projected.cycle, cycle_id=cycle_id)),
            NOW,
        )
    repository.upsert_cycle(
        replace(
            projected,
            cycle=dict(projected.cycle, site_id="site-b", cycle_id="other-site"),
        ),
        NOW,
    )
    with repository.write_connection() as writer:
        writer.execute(
            """UPDATE traffic_projection_cycles
               SET source_started_at='2026-08-01T00:00:00.000Z',
                   source_finished_at='2026-08-01T00:01:00.000Z'
               WHERE projection_version=?""",
            (repository.projection_version,),
        )
        writer.commit()
    with other_version.write_connection() as writer:
        writer.execute(
            """UPDATE traffic_projection_cycles
               SET source_started_at='2026-08-01T00:00:00.000Z',
                   source_finished_at='2026-08-01T00:01:00.000Z'
               WHERE projection_version=?""",
            (other_version.projection_version,),
        )
        writer.commit()
    assert repository.delete_before(
        SITE, "2026-09-01T00:00:00.000Z", limit=1
    ) == 1
    assert other_version.source_marker(SITE, "other-version") is not None
    with repository.read_connection() as read:
        assert read.execute(
            "SELECT COUNT(*) FROM traffic_projection_cycles "
            "WHERE projection_version=? AND site_id='site-b'",
            (repository.projection_version,),
        ).fetchone()[0] == 1
        assert read.execute(
            "SELECT COUNT(*) FROM traffic_projection_cycles "
            "WHERE projection_version=? AND site_id=?",
            (repository.projection_version, SITE),
        ).fetchone()[0] == 1
    assert repository.delete_before(
        SITE, "2026-09-01T00:00:00.000Z", limit=1
    ) == 1


def test_worker_error_preserves_repair_state_but_normal_site_becomes_stale(
    tmp_path, monkeypatch
):
    observation_path = tmp_path / "observations.sqlite3"
    _observation_db(observation_path).close()
    repository = _repository(tmp_path)
    repository.update_site(
        SITE,
        status="rebuilding",
        reconcile_sweep_started_at=NOW,
        reconcile_sweep_source_head_utc=NOW,
        reconcile_sweep_source_head_cycle_id="cycle-head",
        reconcile_sweep_from_utc="2026-08-20T00:00:00.000Z",
        reconcile_cursor_started_at="2026-09-01T00:00:00.000Z",
        reconcile_cursor_cycle_id="cycle-cursor",
    )
    service = TrafficProjectionService(
        TrafficProjectionConfig(
            enabled=True,
            db_path=str(tmp_path / "projection.sqlite3"),
            writer_lock_path=str(tmp_path / "projection.lock"),
            source_db_path=str(observation_path),
            site_ids=(SITE,),
        ),
        repository=repository,
        clock=lambda: NOW,
    )

    def unavailable(_site_id):
        raise RuntimeError("source unavailable")

    monkeypatch.setattr(service, "incremental_site", unavailable)
    service.worker_iteration()
    repairing = repository.site_state(SITE)
    assert repairing["status"] == "rebuilding"
    assert repairing["reconcile_sweep_started_at"] == NOW
    assert repairing["reconcile_cursor_cycle_id"] == "cycle-cursor"

    repository.update_site(SITE, status="healthy")
    service.worker_iteration()
    normal = repository.site_state(SITE)
    assert normal["status"] == "stale"


def test_incremental_path_skips_boundaries_and_completed_reconcile_proves_them(
    tmp_path, monkeypatch
):
    observation_path = tmp_path / "observations.sqlite3"
    connection = _observation_db(observation_path)
    _insert_cycle(connection)
    repository = TrafficProjectionRepository(str(tmp_path / "projection.sqlite3"))
    source = TrafficProjectionSource(str(observation_path))
    service = TrafficProjectionService(
        TrafficProjectionConfig(
            enabled=True,
            db_path=str(tmp_path / "projection.sqlite3"),
            writer_lock_path=str(tmp_path / "projection.lock"),
            source_db_path=str(observation_path),
            site_ids=(SITE,),
        ),
        repository=repository,
        source=source,
        clock=lambda: NOW,
    )
    service.initialize()
    calls = []
    original = source.boundaries

    def boundaries(site_id, *, evaluated_at_utc):
        calls.append((site_id, evaluated_at_utc))
        return original(site_id, evaluated_at_utc=evaluated_at_utc)

    monkeypatch.setattr(source, "boundaries", boundaries)
    service.incremental_site(SITE)
    assert calls == []
    with pytest.raises(TrafficProjectionStorageCorrupt):
        service.mark_ready()
    result = service.reconcile_site(SITE)
    assert result.sweep_completed is True
    assert calls == [(SITE, NOW)]
    state = repository.site_state(SITE)
    assert state["source_boundary_proof_at"] == NOW
    assert state["source_boundary_proof_head_cycle_id"] == "cycle-a"
    service.mark_ready()


def test_health_matrix_for_quiet_catching_and_stopped_progress():
    base = {
        "projection_version": PROJECTION_VERSION,
        "projection_revision": 1,
        "status": "healthy",
        "source_head_utc": NOW,
        "projection_head_utc": "2026-09-03T11:58:00.000Z",
        "last_incremental_progress_at": NOW,
        "last_full_reconcile_completed_at": NOW,
    }
    assert classify_projection_health(base, now_utc=NOW).status == "catching_up"
    active_sweep_within_ceiling = dict(
        base,
        last_full_reconcile_completed_at="2026-09-03T11:45:01.000Z",
        reconcile_sweep_started_at="2026-09-03T11:59:00.000Z",
    )
    assert classify_projection_health(
        active_sweep_within_ceiling, now_utc=NOW
    ).status == "catching_up"
    active_sweep_past_ceiling = dict(
        base,
        last_full_reconcile_completed_at="2026-09-03T11:44:59.000Z",
        reconcile_sweep_started_at="2026-09-03T11:59:00.000Z",
    )
    assert classify_projection_health(
        active_sweep_past_ceiling, now_utc=NOW
    ).status == "stale"
    stopped = dict(
        base,
        last_incremental_progress_at="2026-09-03T11:58:00.000Z",
    )
    assert classify_projection_health(stopped, now_utc=NOW).status == "stale"
    old_reconcile = dict(
        base,
        last_full_reconcile_completed_at="2026-09-03T11:44:59.000Z",
        last_incremental_progress_at=NOW,
    )
    assert classify_projection_health(old_reconcile, now_utc=NOW).status == "stale"


def test_cleanup_converges_in_bounded_restart_safe_chunks(tmp_path):
    observation_path = tmp_path / "observations.sqlite3"
    connection = _observation_db(observation_path)
    _insert_cycle(connection)
    projected = TrafficProjectionSource(str(observation_path)).cycle(SITE, "cycle-a")
    repository = _repository(tmp_path)
    for number in range(205):
        repository.upsert_cycle(
            replace(
                projected,
                cycle=dict(projected.cycle, cycle_id=f"expired-{number:03d}"),
            ),
            NOW,
        )
    with repository.write_connection() as writer:
        writer.execute(
            """UPDATE traffic_projection_cycles
               SET source_started_at='2026-08-01T00:00:00.000Z',
                   source_finished_at='2026-08-01T00:01:00.000Z'"""
        )
        writer.commit()
    config = TrafficProjectionConfig(
        enabled=True,
        db_path=str(tmp_path / "projection.sqlite3"),
        writer_lock_path=str(tmp_path / "projection.lock"),
        source_db_path=str(observation_path),
        site_ids=(SITE,),
    )
    first_process = TrafficProjectionService(
        config, repository=repository, clock=lambda: NOW
    )
    assert first_process.cleanup(max_chunks=1) == 100
    with repository.read_connection() as read:
        assert read.execute(
            "SELECT COUNT(*) FROM traffic_projection_cycles"
        ).fetchone()[0] == 105
    resumed = TrafficProjectionService(
        config, repository=repository, clock=lambda: NOW
    )
    assert resumed.cleanup() == 105
    with repository.read_connection() as read:
        assert read.execute(
            "SELECT COUNT(*) FROM traffic_projection_cycles"
        ).fetchone()[0] == 0


def test_cli_projection_version_is_explicit_and_never_auto_activates(
    tmp_path, monkeypatch
):
    from app.traffic_projection import cli

    created = []

    class FakeService:
        def __init__(self, _config, **kwargs):
            created.append(kwargs["projection_version"])

        def initialize(self):
            pass

        def worker_iteration(self):
            pass

    settings = {
        "traffic_projection_enabled": "true",
        "traffic_projection_db_path": str(tmp_path / "projection.sqlite3"),
        "traffic_projection_writer_lock_path": str(tmp_path / "projection.lock"),
        "observation_db_path": str(tmp_path / "observations.sqlite3"),
        "observation_site_ids": SITE,
    }
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli, "TrafficProjectionService", FakeService)
    assert cli.main(["build"]) == 0
    assert cli.main(["--projection-version", "target-v2", "build"]) == 0
    assert created == [PROJECTION_VERSION, "target-v2"]
    with pytest.raises(SystemExit):
        cli.main(["--projection-version", "", "build"])
