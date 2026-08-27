"""Opt-in 60-second mixed Visit writer contention acceptance workload."""

from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import statistics
import sys
import tempfile
import threading
import time
import uuid
from collections import Counter, defaultdict
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.visit_lifecycle import (
    VisitLifecycleConfig,
    VisitLifecycleService,
    VisitStartRequest,
)
from app.visit_lifecycle.reconciliation import VisitLinkReconciler
from app.visit_lifecycle.repository import (
    PriorityWriteCoordinator,
    VisitRepository,
    _expected_v2_signature,
    _schema_signature,
)
from app.visit_lifecycle.start_sink import LocalVisitStartSubmitter
from app.visit_lifecycle.webhook_reader import VisitLifecycleWebhookReader


SITE_ID = "load-site"
START_MACS = tuple(
    f"02:11:22:33:{index // 256:02X}:{index % 256:02X}"
    for index in range(64)
)
PRESEEDED_START_MAC_COUNT = 32


class Telemetry:
    def __init__(self):
        self.events = []
        self.lock = threading.Lock()

    def emit(self, event, level="info", **fields):
        with self.lock:
            self.events.append((event, level, fields))
        return True


class InstrumentedCoordinator(PriorityWriteCoordinator):
    def __init__(self):
        super().__init__()
        self.lock = threading.Lock()
        self.grants = Counter()
        self.maximum_hold_ms = defaultdict(int)
        self.maximum_chunk_items = 0
        self.pending_nonempty_chunks = 0
        self._local = threading.local()

    @contextmanager
    def acquire(self, operation, **kwargs):
        with super().acquire(operation, **kwargs) as lease:
            acquired = time.monotonic()
            with self.lock:
                self.grants[operation] += 1
            self._local.operation = operation
            self._local.items = 0
            try:
                yield lease
            finally:
                held_ms = int(round((time.monotonic() - acquired) * 1000))
                with self.lock:
                    self.maximum_hold_ms[operation] = max(
                        self.maximum_hold_ms[operation],
                        held_ms,
                    )
                    if operation == "pending_retry":
                        if int(self._local.items) > 0:
                            self.pending_nonempty_chunks += 1
                        self.maximum_chunk_items = max(
                            self.maximum_chunk_items,
                            int(self._local.items),
                        )
                self._local.operation = None
                self._local.items = 0

    def note_pending_item(self):
        if getattr(self._local, "operation", None) == "pending_retry":
            self._local.items = int(getattr(self._local, "items", 0)) + 1


class EmptyRegistry:
    def get_device_by_mac(self, _mac):
        return None

    def get_snapshot_by_auth_session(
        self,
        _session_id,
        *,
        site_id,
        client_mac,
    ):
        return None


def _config(root: Path) -> VisitLifecycleConfig:
    return VisitLifecycleConfig(
        enabled=True,
        db_path=str(root / "visits.sqlite3"),
        webhook_source=str(root / "omada_webhook_normalized.log"),
        scan_interval_seconds=5.0,
        reconcile_interval_seconds=30.0,
        max_line_bytes=1_048_576,
        reader_max_lines_per_scan=5_000,
        reader_max_bytes_per_scan=16_777_216,
        reader_max_duration_seconds=20.0,
        reconcile_batch_size=500,
        pending_offline_batch_size=500,
        offline_match_grace_seconds=30.0,
        start_writer_slot_wait_ms=750,
        reader_writer_slot_wait_ms=250,
        reconciliation_writer_slot_wait_ms=250,
        sqlite_busy_timeout_ms=500,
        start_max_attempts=3,
        start_total_budget_ms=2_000,
        shutdown_timeout_seconds=20.0,
        max_offline_clock_skew_seconds=120.0,
        max_reported_duration_drift_seconds=300.0,
    )


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _offline(index: int) -> str:
    timestamp = _utc_now()
    record = {
        "event": "omada.client_offline",
        "normalized_event_id": f"load-offline:{index:08d}",
        "site_id": SITE_ID,
        "site_resolution_status": "resolved",
        "client_mac": (
            f"02:00:{(index >> 24) & 255:02X}:{(index >> 16) & 255:02X}:"
            f"{(index >> 8) & 255:02X}:{index & 255:02X}"
        ),
        "controller_timestamp": timestamp,
        "received_at": timestamp,
        "ssid": "Zefer_Parki",
    }
    return json.dumps(record, separators=(",", ":")) + "\n"


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1)
    return ordered[index]


def run(*, duration_seconds: float, start_rate: float) -> dict:
    if duration_seconds <= 0 or start_rate < 10:
        raise ValueError("duration must be positive and Start rate must be >=10/s")
    with tempfile.TemporaryDirectory(prefix="visit-writer-load-") as folder:
        root = Path(folder)
        config = _config(root)
        coordinator = InstrumentedCoordinator()
        repository = VisitRepository(config, write_coordinator=coordinator)
        repository.initialize()
        retry_pending_row = repository._retry_pending_row  # noqa: SLF001

        def instrumented_retry_pending_row(*args, **kwargs):
            coordinator.note_pending_item()
            return retry_pending_row(*args, **kwargs)

        repository._retry_pending_row = instrumented_retry_pending_row  # type: ignore[method-assign]  # noqa: SLF001
        telemetry = Telemetry()
        service = VisitLifecycleService(repository, telemetry)
        submitter = LocalVisitStartSubmitter(
            service,
            telemetry,
            max_attempts=config.start_max_attempts,
            total_budget_ms=config.start_total_budget_ms,
        )
        reader = VisitLifecycleWebhookReader(
            config=config,
            repository=repository,
            service=service,
            telemetry=telemetry,
        )
        reconciler = VisitLinkReconciler(
            config=config,
            repository=repository,
            registry_read_service=EmptyRegistry(),
            telemetry=telemetry,
        )

        preseed_outcomes = []
        for index, client_mac in enumerate(
            START_MACS[:PRESEEDED_START_MAC_COUNT]
        ):
            preseed_outcomes.append(submitter.submit_authorized(
                VisitStartRequest(
                    auth_session_id=str(uuid.uuid4()),
                    site_id=SITE_ID,
                    client_mac=client_mac,
                    authorized_at=datetime.now(timezone.utc),
                    auth_run_number=1,
                    authorization_attempt=1,
                    final_reason="AUTHORIZED_AFTER_ATTEMPT",
                    client_ip="192.0.2.10",
                    portal_ssid="Zefer_Parki",
                    portal_ap_mac="02:AA:BB:CC:DD:EE",
                    portal_radio_id=0,
                )
            ))
        if any(item.status != "opened" for item in preseed_outcomes):
            raise RuntimeError("reconciliation preseed did not open")

        backlog_count = config.pending_offline_batch_size
        with open(config.webhook_source, "w", encoding="utf-8", newline="") as output:
            for index in range(backlog_count):
                output.write(_offline(index))
        while not reader.scan_once():
            pass
        initial_states = repository.get_reader_states()
        initial_reader_offset = next(iter(initial_states.values())).source_offset

        stop = threading.Event()
        latencies_ms = []
        outcomes = []
        dynamic_source_count = 0
        maximum_reader_lag_bytes = 0
        maximum_reader_offset_during_load = initial_reader_offset
        reconciliation_progress_samples = []
        metric_lock = threading.Lock()

        def starts():
            interval = 1.0 / start_rate
            next_at = time.monotonic()
            end_at = next_at + duration_seconds
            index = 0
            while next_at < end_at:
                remaining = next_at - time.monotonic()
                if remaining > 0:
                    stop.wait(remaining)
                request = VisitStartRequest(
                    auth_session_id=str(uuid.uuid4()),
                    site_id=SITE_ID,
                    client_mac=START_MACS[index % len(START_MACS)],
                    authorized_at=datetime.now(timezone.utc),
                    auth_run_number=1,
                    authorization_attempt=1,
                    final_reason="AUTHORIZED_AFTER_ATTEMPT",
                    client_ip="192.0.2.10",
                    portal_ssid="Zefer_Parki",
                    portal_ap_mac="02:AA:BB:CC:DD:EE",
                    portal_radio_id=0,
                )
                started = time.monotonic()
                result = submitter.submit_authorized(request)
                with metric_lock:
                    latencies_ms.append((time.monotonic() - started) * 1000)
                    outcomes.append(result)
                index += 1
                next_at += interval

        def append_events():
            nonlocal dynamic_source_count
            index = backlog_count
            while not stop.wait(0.5):
                with open(
                    config.webhook_source,
                    "a",
                    encoding="utf-8",
                    newline="",
                ) as output:
                    output.write(_offline(index))
                index += 1
                dynamic_source_count += 1

        def scan():
            nonlocal maximum_reader_lag_bytes
            nonlocal maximum_reader_offset_during_load
            while not stop.is_set():
                reader.scan_once()
                states = repository.get_reader_states()
                if states:
                    state = next(iter(states.values()))
                    lag = max(
                        0,
                        os.path.getsize(config.webhook_source)
                        - state.source_offset,
                    )
                    maximum_reader_lag_bytes = max(
                        maximum_reader_lag_bytes,
                        lag,
                    )
                    maximum_reader_offset_during_load = max(
                        maximum_reader_offset_during_load,
                        state.source_offset,
                    )
                stop.wait(config.scan_interval_seconds)

        def reconcile():
            while not stop.is_set():
                reconciler.run_once()
                with closing(
                    repository._connect(readonly=True)  # noqa: SLF001
                ) as connection:
                    attempt_count = connection.execute(
                        "SELECT COALESCE(SUM(link_reconcile_attempt_count), 0) "
                        "FROM visits"
                    ).fetchone()[0]
                with metric_lock:
                    if (
                        not reconciliation_progress_samples
                        or attempt_count > reconciliation_progress_samples[-1]
                    ):
                        reconciliation_progress_samples.append(attempt_count)
                stop.wait(config.reconcile_interval_seconds)

        workers = [
            threading.Thread(target=starts, name="load-starts"),
            threading.Thread(target=append_events, name="load-journal"),
            threading.Thread(target=scan, name="load-reader"),
            threading.Thread(target=reconcile, name="load-reconcile"),
        ]
        for worker in workers:
            worker.start()
        workers[0].join(duration_seconds + 10)
        stop.set()
        service.wake_write_waiters()
        for worker in workers[1:]:
            worker.join(5)

        states = repository.get_reader_states()
        state = next(iter(states.values()))
        source_size = os.path.getsize(config.webhook_source)
        residual_bytes = max(0, source_size - state.source_offset)
        with open(config.webhook_source, "rb") as source:
            source.seek(state.source_offset)
            residual_lines = sum(1 for _line in source)
        maximum_reader_lag_bytes = max(
            maximum_reader_lag_bytes,
            residual_bytes,
        )
        calculated_scans = max(
            math.ceil(residual_lines / config.reader_max_lines_per_scan),
            math.ceil(residual_bytes / config.reader_max_bytes_per_scan),
        )
        scheduler_tolerance_seconds = max(
            config.scan_interval_seconds,
            2.0,
        )
        allowed_catchup_seconds = (
            calculated_scans * config.scan_interval_seconds
            + scheduler_tolerance_seconds
        )

        catchup_started = time.monotonic()
        for _ in range(100):
            reader.scan_once()
            states = repository.get_reader_states()
            state = next(iter(states.values()))
            if state.source_offset >= os.path.getsize(config.webhook_source):
                break
        catchup_seconds = time.monotonic() - catchup_started
        states = repository.get_reader_states()
        state = next(iter(states.values()))
        source_size = os.path.getsize(config.webhook_source)
        final_residual_bytes = max(0, source_size - state.source_offset)
        with open(config.webhook_source, "rb") as source:
            source.seek(state.source_offset)
            final_residual_lines = sum(1 for _line in source)

        successful = [item for item in outcomes if item.status in {"opened", "reused"}]
        successful_preseed = [
            item for item in preseed_outcomes if item.status == "opened"
        ]
        with closing(repository._connect(readonly=True)) as connection:  # noqa: SLF001
            authorization_count = connection.execute(
                "SELECT COUNT(*) FROM visit_authorizations"
            ).fetchone()[0]
            duplicate_authorizations = connection.execute(
                """
                SELECT COUNT(*) FROM (
                    SELECT auth_session_id, auth_run_number
                    FROM visit_authorizations
                    GROUP BY auth_session_id, auth_run_number
                    HAVING COUNT(*) > 1
                )
                """
            ).fetchone()[0]
            source_event_count = connection.execute(
                "SELECT COUNT(*) FROM visit_source_events"
            ).fetchone()[0]
            duplicate_source_event_count = connection.execute(
                """
                SELECT COUNT(*) FROM (
                    SELECT event_id FROM visit_source_events
                    GROUP BY event_id HAVING COUNT(*) > 1
                )
                """
            ).fetchone()[0]
            reconciliation_attempt_count = connection.execute(
                "SELECT COALESCE(SUM(link_reconcile_attempt_count), 0) "
                "FROM visits"
            ).fetchone()[0]
            quick_check = connection.execute("PRAGMA quick_check").fetchone()[0]
            foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
            user_version = connection.execute("PRAGMA user_version").fetchone()[0]
            signature_ok = _schema_signature(connection) == _expected_v2_signature()
            journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        with closing(repository._connect()) as connection:  # noqa: SLF001
            synchronous = connection.execute("PRAGMA synchronous").fetchone()[0]

        events = list(telemetry.events)
        storage_errors = [event for event in events if event[0] == "visit.storage_error"]
        background_exhaustions = sum(
            1
            for _event, _level, fields in storage_errors
            if fields.get("retry_exhausted")
            and int(fields.get("background_blocked_attempt_count") or 0) > 0
        )
        final_busy = [fields for _e, _l, fields in storage_errors]
        totals = {
            name: sum(int(fields.get(name) or 0) for fields in final_busy)
            for name in (
                "coordinator_busy_attempt_count",
                "sqlite_busy_attempt_count",
                "background_blocked_attempt_count",
                "background_blocked_wait_ms",
                "foreground_blocked_attempt_count",
                "foreground_blocked_wait_ms",
            )
        }
        totals["max_background_holder_age_ms"] = max(
            [int(fields.get("max_background_holder_age_ms") or 0) for fields in final_busy]
            or [0]
        )
        return {
            "python_version": os.sys.version.split()[0],
            "sqlite_version": sqlite3.sqlite_version,
            "journal_mode": journal_mode,
            "synchronous": synchronous,
            "production_peak_evidence_source": "not available to coder; FINAL floor applied",
            "production_peak_rate": None,
            "test_start_rate": start_rate,
            "duration_seconds": duration_seconds,
            "reader_input_rate_per_second": 2.0,
            "pending_backlog_count": backlog_count,
            "reconciliation_candidate_count": len(START_MACS),
            "start_count": len(outcomes),
            "start_opened_count": sum(
                1 for item in outcomes if item.status == "opened"
            ),
            "start_reused_count": sum(
                1 for item in outcomes if item.status == "reused"
            ),
            "start_p50_ms": round(statistics.median(latencies_ms), 3),
            "start_p95_ms": round(_percentile(latencies_ms, 0.95), 3),
            "start_p99_ms": round(_percentile(latencies_ms, 0.99), 3),
            "start_p99_target_ms": 750,
            "start_p99_target_met": (
                _percentile(latencies_ms, 0.99) < 750
            ),
            "start_max_ms": round(max(latencies_ms, default=0.0), 3),
            "start_retry_exhausted_count": sum(
                1 for item in outcomes if item.status == "unavailable"
            ),
            "background_caused_start_exhaustion_count": background_exhaustions,
            **totals,
            "reader_deferral_count": sum(
                1 for event in events if event[0] == "visit.reader_scan_deferred"
            ),
            "reader_real_failure_count": sum(
                1 for event in events if event[0] == "visit.reader_scan_failed"
            ),
            "reconciliation_degraded_count": sum(
                1
                for event in events
                if event[0] == "visit.reconciliation_degraded"
            ),
            "reader_initial_source_offset": initial_reader_offset,
            "reader_maximum_source_offset_during_load": (
                maximum_reader_offset_during_load
            ),
            "reader_durable_progress_during_load_bytes": max(
                0,
                maximum_reader_offset_during_load - initial_reader_offset,
            ),
            "reader_maximum_lag_bytes": maximum_reader_lag_bytes,
            "reader_residual_lag_lines": residual_lines,
            "reader_residual_lag_bytes": residual_bytes,
            "reader_final_residual_lag_lines": final_residual_lines,
            "reader_final_residual_lag_bytes": final_residual_bytes,
            "reader_calculated_catchup_scan_count": calculated_scans,
            "reader_calculated_catchup_window_seconds": (
                calculated_scans * config.scan_interval_seconds
            ),
            "reader_scheduler_tolerance_seconds": (
                scheduler_tolerance_seconds
            ),
            "reader_allowed_catchup_seconds": allowed_catchup_seconds,
            "reader_actual_final_catchup_seconds": round(catchup_seconds, 3),
            "reader_catchup_within_allowed_window": (
                catchup_seconds <= allowed_catchup_seconds
            ),
            "pending_chunk_grants": coordinator.grants["pending_retry"],
            "pending_chunks_committed": coordinator.pending_nonempty_chunks,
            "maximum_pending_chunk_item_count": coordinator.maximum_chunk_items,
            "maximum_background_holder_age_ms_by_operation": dict(
                coordinator.maximum_hold_ms
            ),
            "reconciliation_processed_count": reconciliation_attempt_count,
            "reconciliation_progress_samples": (
                reconciliation_progress_samples
            ),
            "authorization_expected": len(successful_preseed) + len(successful),
            "authorization_actual": authorization_count,
            "duplicate_retry_recovery_count": sum(
                1
                for event in events
                if event[0] == "visit.start_retry_recovered"
            ),
            "duplicate_authorization_count": duplicate_authorizations,
            "source_events_expected": backlog_count + dynamic_source_count,
            "source_events_actual": source_event_count,
            "duplicate_source_event_count": duplicate_source_event_count,
            "quick_check": quick_check,
            "foreign_key_check": len(foreign_keys),
            "user_version": user_version,
            "schema_signature": signature_ok,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--start-rate", type=float, default=10.0)
    args = parser.parse_args()
    result = run(duration_seconds=args.duration, start_rate=args.start_rate)
    print(json.dumps(result, indent=2, sort_keys=True))
    required = (
        result["start_retry_exhausted_count"] == 0
        and result["background_caused_start_exhaustion_count"] == 0
        and result["start_p99_target_met"] is True
        and result["start_opened_count"] > 0
        and result["start_reused_count"] > 0
        and result["authorization_expected"] == result["authorization_actual"]
        and result["duplicate_authorization_count"] == 0
        and result["source_events_expected"] == result["source_events_actual"]
        and result["duplicate_source_event_count"] == 0
        and result["reader_final_residual_lag_lines"] == 0
        and result["reader_final_residual_lag_bytes"] == 0
        and result["reader_real_failure_count"] == 0
        and result["reconciliation_degraded_count"] == 0
        and result["reader_durable_progress_during_load_bytes"] > 0
        and result["pending_chunks_committed"] >= 2
        and result["maximum_pending_chunk_item_count"] <= 25
        and len(result["reconciliation_progress_samples"]) >= 2
        and result["reconciliation_processed_count"]
        >= result["reconciliation_candidate_count"]
        and result["reader_catchup_within_allowed_window"] is True
        and result["quick_check"] == "ok"
        and result["foreign_key_check"] == 0
        and result["user_version"] == 2
        and result["schema_signature"] is True
    )
    return 0 if required else 1


if __name__ == "__main__":
    raise SystemExit(main())
