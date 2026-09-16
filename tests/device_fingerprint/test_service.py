import threading
import os
from types import SimpleNamespace

import pytest

import app.device_fingerprint.service as module
from app.device_fingerprint.repository import DeviceFingerprintRepository
from app.device_fingerprint.schema_registry import EvidenceSchemaRegistry
from app.device_fingerprint.service import DeviceFingerprintRuntime, DeviceFingerprintService
from app.device_fingerprint.telemetry import DeviceFingerprintTelemetry
from tests.device_fingerprint import Identity, NOW, config, evidence_event, logger, producer


def runtime(tmp_path, **kwargs):
    cfg = config(tmp_path)
    repo = DeviceFingerprintRepository(cfg.db_path, max_db_bytes=cfg.max_db_bytes)
    registry = EvidenceSchemaRegistry(); registry.register("dhcp", 1, lambda value: dict(value)); registry.freeze()
    value = DeviceFingerprintRuntime(cfg, repo, registry, artifact_identity=Identity(), telemetry=DeviceFingerprintTelemetry(logger()), now=lambda: NOW, **kwargs)
    value.initialize(); value.mark_ready()
    return value


def test_initializing_transitions_to_ready_only_when_explicitly_marked(tmp_path):
    cfg = config(tmp_path)
    repo = DeviceFingerprintRepository(cfg.db_path, max_db_bytes=cfg.max_db_bytes)
    registry = EvidenceSchemaRegistry(); registry.register("dhcp", 1, lambda value: dict(value)); registry.freeze()
    value = DeviceFingerprintRuntime(
        cfg, repo, registry, artifact_identity=Identity(),
        telemetry=DeviceFingerprintTelemetry(logger()), now=lambda: NOW,
    )
    assert (value.state, value.accepting_writes, value.maintenance_thread) == (
        "initializing", False, None
    )
    value.initialize()
    assert value.state == "initializing"
    value.mark_ready()
    assert (value.state, value.reason, value.accepting_writes) == ("ready", None, True)


def test_health_payload_consumes_authoritative_schema_and_retention_constants(tmp_path):
    from app.device_fingerprint.config import SOURCE_HEALTH_RETENTION_DAYS
    from app.device_fingerprint.schema import SCHEMA_VERSION
    value = runtime(tmp_path)
    payload = value.health_payload()
    assert payload["schema_version"] == SCHEMA_VERSION == 2
    assert payload["source_health_retention_days"] == SOURCE_HEALTH_RETENTION_DAYS == 30


def test_runtime_registration_and_stopping_share_condition(tmp_path):
    value = runtime(tmp_path)
    assert value.begin_ingest() is True and value.active_ingest_count == 1
    value.transition_stopping()
    assert value.begin_ingest() is False
    value.finish_ingest()
    assert value.active_ingest_count == 0


def test_signal_is_nonblocking_and_raises_system_exit(tmp_path):
    value = runtime(tmp_path)
    with pytest.raises(SystemExit) as caught:
        value.signal_stop()
    assert caught.value.code == 0
    assert value.state == "stopping" and value.stop_event.is_set()


def test_constructor_starts_no_thread_and_maintenance_waits_full_delay(tmp_path, monkeypatch):
    value = runtime(tmp_path)
    assert value.maintenance_thread is None
    calls = []
    monkeypatch.setattr(module, "RETENTION_SCAN_INTERVAL_SECONDS", 0.01)
    value.run_maintenance_once = lambda: (calls.append(True), value.stop_event.set())
    value.start_maintenance(); value.maintenance_thread.join(1)
    assert calls == [True]


def test_maintenance_runs_one_nonoverlapping_pass_after_every_completed_fixed_delay(tmp_path):
    value = runtime(tmp_path)
    waits = []
    passes = []

    class Stop:
        def wait(self, delay):
            waits.append(delay)
            return len(waits) == 3

    value.stop_event = Stop()
    value.run_maintenance_once = lambda: passes.append(len(waits))
    value._maintenance_loop()
    assert waits == [module.RETENTION_SCAN_INTERVAL_SECONDS] * 3
    assert passes == [1, 2]


def test_start_maintenance_rejects_a_second_overlapping_thread(tmp_path, monkeypatch):
    value = runtime(tmp_path)
    entered = threading.Event()

    class Stop:
        def wait(self, _delay):
            entered.set()
            return True

    value.stop_event = Stop()
    value.start_maintenance()
    assert entered.wait(1)
    value.maintenance_thread.join(1)
    with pytest.raises(RuntimeError):
        value.start_maintenance()


def test_clean_finalize_closes_then_releases_lock(tmp_path):
    value = runtime(tmp_path)
    order = []
    value.repository.close = lambda: order.append("repository")
    assert value.finalize(release_lock=lambda: order.append("lock")) is True
    assert order == ["repository", "lock"]


def test_duplicate_ids_fail_before_repository_write(tmp_path):
    value = runtime(tmp_path)
    event = evidence_event()
    with pytest.raises(Exception):
        value.service.evidence_batch(producer(), {"producer_id": producer().producer_id, "events": [event, event]})
    assert value.repository.connection.execute("SELECT COUNT(*) FROM device_fingerprint_evidence").fetchone()[0] == 0


def test_retention_failure_degrades_but_keeps_ingest_then_recovers(tmp_path, monkeypatch):
    value = runtime(tmp_path)
    real_cleanup = value.repository.cleanup
    monkeypatch.setattr(value.repository, "cleanup", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("failure")))
    value.run_maintenance_once()
    assert (value.state, value.reason, value.accepting_writes) == ("degraded", "retention_failed", True)
    monkeypatch.setattr(value.repository, "cleanup", real_cleanup)
    value.run_maintenance_once()
    assert (value.state, value.reason, value.accepting_writes) == ("ready", None, True)


def test_storage_limit_recovery_requires_capacity_proof(tmp_path, monkeypatch):
    from app.device_fingerprint.models import DeviceFingerprintStorageLimit
    value = runtime(tmp_path)
    value.note_storage_error(DeviceFingerprintStorageLimit())
    assert (value.state, value.reason, value.accepting_writes) == ("unavailable", "storage_limit", False)
    monkeypatch.setattr(value.repository, "cleanup", lambda **_kwargs: {"device_fingerprint_evidence": 0, "device_fingerprint_source_health_events": 0})
    monkeypatch.setattr(value.repository, "validate_runtime_health", lambda: None)
    monkeypatch.setattr(value.repository, "capacity", lambda: {"page_count": 10, "max_page_count": 10, "freelist_count": 0})
    value.run_maintenance_once()
    assert value.state == "unavailable"
    monkeypatch.setattr(value.repository, "capacity", lambda: {"page_count": 10, "max_page_count": 10, "freelist_count": 1})
    value.run_maintenance_once()
    assert value.state == "ready"


def test_storage_limit_recovery_orders_retention_health_then_capacity(tmp_path, monkeypatch):
    from app.device_fingerprint.models import DeviceFingerprintStorageLimit
    value = runtime(tmp_path)
    value.note_storage_error(DeviceFingerprintStorageLimit())
    calls = []
    monkeypatch.setattr(value.repository, "cleanup", lambda **_kwargs: (
        calls.append("retention") or {
            "device_fingerprint_evidence": 0,
            "device_fingerprint_source_health_events": 0,
        }
    ))
    monkeypatch.setattr(value.repository, "validate_runtime_health", lambda: calls.append("quick-check-and-schema"))
    monkeypatch.setattr(value.repository, "capacity", lambda: (
        calls.append("capacity") or {
            "page_count": 9, "max_page_count": 10, "freelist_count": 0,
        }
    ))
    value.run_maintenance_once()
    assert calls == ["retention", "quick-check-and-schema", "capacity"]
    assert value.state == "ready"


def test_storage_corrupt_is_latched(tmp_path, monkeypatch):
    from app.device_fingerprint.models import DeviceFingerprintStorageCorrupt
    value = runtime(tmp_path); value.note_storage_error(DeviceFingerprintStorageCorrupt())
    monkeypatch.setattr(value.repository, "cleanup", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not run")))
    value.run_maintenance_once()
    assert (value.state, value.reason) == ("unavailable", "storage_corrupt")


def test_storage_unavailable_is_latched(tmp_path, monkeypatch):
    value = runtime(tmp_path)
    value._unavailable("storage_unavailable", "device_fingerprint_storage_unavailable")
    monkeypatch.setattr(value.repository, "cleanup", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not run")))
    value.run_maintenance_once()
    assert (value.state, value.reason, value.accepting_writes) == (
        "unavailable", "storage_unavailable", False
    )


def test_shutdown_timeout_keeps_repository_and_lock(tmp_path):
    ticks = iter((0.0, 21.0))
    value = runtime(tmp_path, monotonic=lambda: next(ticks))
    value.active_ingest_count = 1
    closed = []; value.repository.close = lambda: closed.append("closed")
    assert value.finalize(release_lock=lambda: closed.append("lock")) is False
    assert closed == [] and value.state == "stopping"
    assert value.finalize(release_lock=lambda: closed.append("lock")) is False


def test_one_shutdown_budget_covers_ingest_drain_and_maintenance_join(tmp_path, monkeypatch):
    ticks = iter((0.0, 5.0, 7.0))
    value = runtime(tmp_path, monotonic=lambda: next(ticks))
    value.active_ingest_count = 1
    joined = []

    class Thread:
        alive = True
        def is_alive(self):
            return self.alive
        def join(self, timeout):
            joined.append(timeout)
            self.alive = False

    value.maintenance_thread = Thread()
    monkeypatch.setattr(
        value.condition, "wait",
        lambda timeout: (setattr(value, "active_ingest_count", 0), timeout)[1],
    )
    closed = []
    value.repository.close = lambda: closed.append("repository")
    assert value.finalize(release_lock=lambda: closed.append("lock")) is True
    assert joined == [13.0]
    assert closed == ["repository", "lock"]


def test_shutdown_timeout_with_live_maintenance_keeps_repository_and_lock(tmp_path):
    ticks = iter((0.0, 1.0))
    value = runtime(tmp_path, monotonic=lambda: next(ticks))
    joined = []

    class Thread:
        def is_alive(self):
            return True
        def join(self, timeout):
            joined.append(timeout)

    value.maintenance_thread = Thread()
    closed = []
    value.repository.close = lambda: closed.append("repository")
    assert value.finalize(release_lock=lambda: closed.append("lock")) is False
    assert joined == [19.0]
    assert closed == []
    assert (value.state, value.accepting_writes) == ("stopping", False)


def test_stopping_visibility_prevents_late_registration_under_same_condition(tmp_path):
    value = runtime(tmp_path)
    attempted = threading.Event()
    result = []

    def begin():
        attempted.set()
        result.append(value.begin_ingest())

    with value.condition:
        worker = threading.Thread(target=begin)
        worker.start()
        assert attempted.wait(1)
        value.state, value.reason, value.accepting_writes = "stopping", "stopping", False
        value.stop_event.set()
    worker.join(1)
    assert result == [False]
    assert value.active_ingest_count == 0


def test_storage_limit_recovery_ignores_physical_file_size_and_relatches_on_full(tmp_path, monkeypatch):
    from app.device_fingerprint.models import DeviceFingerprintStorageLimit
    value = runtime(tmp_path)
    value.note_storage_error(DeviceFingerprintStorageLimit())
    value.repository.close()
    with open(value.config.db_path, "wb") as handle:
        handle.truncate(value.config.max_db_bytes)
    assert os.path.getsize(value.config.db_path) == value.config.max_db_bytes
    monkeypatch.setattr(value.repository, "cleanup", lambda **_kwargs: {
        "device_fingerprint_evidence": 1,
        "device_fingerprint_source_health_events": 1,
    })
    monkeypatch.setattr(value.repository, "validate_runtime_health", lambda: None)
    monkeypatch.setattr(value.repository, "capacity", lambda: {
        "page_count": 10, "max_page_count": 10, "freelist_count": 1,
    })
    value.run_maintenance_once()
    assert (value.state, value.reason, value.accepting_writes) == ("ready", None, True)
    value.note_storage_error(DeviceFingerprintStorageLimit())
    assert (value.state, value.reason, value.accepting_writes) == (
        "unavailable", "storage_limit", False
    )


def test_registry_is_composed_only_once_and_must_be_frozen(tmp_path):
    cfg = config(tmp_path); repo = DeviceFingerprintRepository(cfg.db_path, max_db_bytes=cfg.max_db_bytes)
    value = DeviceFingerprintRuntime(cfg, repo, None, artifact_identity=Identity(), telemetry=DeviceFingerprintTelemetry(logger()), now=lambda: NOW)
    value.initialize(); registry = EvidenceSchemaRegistry()
    with pytest.raises(RuntimeError): value.configure_registry(registry)
    registry.freeze(); value.configure_registry(registry)
    with pytest.raises(RuntimeError): value.configure_registry(registry)
