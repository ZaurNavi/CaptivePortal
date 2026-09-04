"""Single-writer materialization, reconciliation and repair service."""

from __future__ import annotations

import hashlib
import logging
import os
import random
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Collection, Iterator, Mapping

from .health import classify_projection_health
from .models import (
    PROJECTION_VERSION,
    SEMANTIC_CONTRACT_SHA256,
    SUPPORTED_SEMANTIC_CONTRACTS,
    MAX_BULK_CYCLES_PER_TRANSACTION,
    MAX_BULK_TRANSACTION_SECONDS,
    MAX_CLEANUP_CHUNKS_PER_INVOCATION,
    ProjectionRunResult,
    TrafficProjectionConfig,
    TrafficProjectionDiverged,
    TrafficProjectionStorageCorrupt,
    TrafficProjectionWriterUnavailable,
)
from .repository import TrafficProjectionRepository
from .source import TrafficProjectionSource, source_revision_marker
from .telemetry import TrafficProjectionTelemetry


UTC = timezone.utc


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class TrafficProjectionService:
    """Projection worker; it has no provider and no request-time acquisition path."""

    def __init__(
        self,
        config: TrafficProjectionConfig,
        *,
        repository: TrafficProjectionRepository | None = None,
        source: TrafficProjectionSource | None = None,
        logger: logging.Logger | None = None,
        clock=utc_now,
        monotonic=time.monotonic,
        projection_version: str = PROJECTION_VERSION,
        semantic_contract_sha256: str = SEMANTIC_CONTRACT_SHA256,
        supported_semantic_contracts: Collection[str] = (
            SUPPORTED_SEMANTIC_CONTRACTS
        ),
    ):
        self.config = config
        self.projection_version = projection_version
        self.semantic_contract_sha256 = semantic_contract_sha256
        self.supported_semantic_contracts = frozenset(
            supported_semantic_contracts
        )
        if semantic_contract_sha256 not in self.supported_semantic_contracts:
            raise ValueError("semantic contract is unsupported")
        self.repository = repository or TrafficProjectionRepository(
            config.db_path, projection_version=projection_version
        )
        if self.repository.projection_version != projection_version:
            raise ValueError("repository projection_version does not match service")
        self.source = source or TrafficProjectionSource(config.source_db_path)
        self.logger = logger or logging.getLogger(__name__)
        self.telemetry = TrafficProjectionTelemetry(self.logger)
        self._clock = clock
        self._monotonic = monotonic
        self._stop = threading.Event()
        self._last_checkpoint = 0.0
        self._last_cleanup = 0.0
        self._target_site_index = 0

    def initialize(self) -> None:
        self.repository.initialize()
        now = self._clock()
        self.repository.ensure_version(self.semantic_contract_sha256, now)
        for site_id in self.config.site_ids:
            self.repository.ensure_site(site_id)

    def run_once(self) -> tuple[ProjectionRunResult, ...]:
        self.initialize()
        results = []
        for site_id in self.config.site_ids:
            incremental = self.incremental_site(site_id)
            results.append(
                self.reconcile_site(site_id)
                if self._reconciliation_due(site_id)
                else incremental
            )
        self._checkpoint_if_due()
        return tuple(results)

    def mark_ready(self) -> None:
        now = self._clock()
        heads: dict[str, tuple[str, str]] = {}
        for site_id in self.config.site_ids:
            head = self.source.head(site_id)
            if head is None:
                raise TrafficProjectionWriterUnavailable(
                    "Projection source head is unavailable"
                )
            heads[site_id] = head
            from_utc = _minus_days(head[0], self.config.retention_days)
            if self.source.cycle_count(
                site_id, from_utc=from_utc, through=head
            ) != self.repository.cycle_count(
                site_id, from_utc=from_utc, through=head
            ):
                self.repository.update_site(
                    site_id,
                    status="diverged",
                    last_error_category="ready_source_identity",
                )
                raise TrafficProjectionDiverged(
                    "Projection build identity diverged"
                )
            self._deep_audit(site_id, tuple_head=head)
            self.repository.update_site(site_id, last_deep_audit_at=now)
        self.repository.mark_ready(now, self.config.site_ids, heads)

    def activate(self) -> None:
        now = self._clock()
        heads: dict[str, tuple[str, str]] = {}
        for site_id in self.config.site_ids:
            head = self.source.head(site_id)
            if head is None:
                raise TrafficProjectionWriterUnavailable(
                    "Projection source head is unavailable"
                )
            heads[site_id] = head
        self.repository.activate(now, self.config.site_ids, heads)

    def fail_version(self) -> None:
        self.repository.fail_version(self._clock())

    def incremental_site(
        self,
        site_id: str,
        *,
        limit: int = 100,
        work_deadline_monotonic: float | None = None,
    ) -> ProjectionRunResult:
        """Discover append-only head progress using the non-authoritative checkpoint."""
        now = self._clock()
        state = self.repository.site_state(site_id) or {}
        if state.get("status") == "diverged":
            raise TrafficProjectionDiverged("Projection Site remains diverged")
        head = self.source.head(site_id)
        if head is None:
            self.repository.update_site(
                site_id, status=(
                    "rebuilding" if state.get("status") == "rebuilding" else "stale"
                ), source_head_utc=None, source_head_cycle_id=None,
                last_incremental_scan_at=now, backlog_cycle_count=0,
            )
            return ProjectionRunResult(site_id, 0, 0, 0, 0, 0, 0, False)
        cursor = None
        if state.get("fast_checkpoint_started_at"):
            cursor = (str(state["fast_checkpoint_started_at"]),
                      str(state["fast_checkpoint_cycle_id"]))
        rows = self.source.metadata(
            site_id, from_utc=_minus_days(head[0], self.config.retention_days),
            through=head, after=cursor, limit=max(1, min(int(limit), 100)),
        )
        markers = self.repository.source_markers(
            site_id, tuple(str(row["cycle_id"]) for row in rows)
        )
        (
            examined,
            projected,
            replayed,
            corrected,
            _invalidated,
            cursor,
            budget_exhausted,
        ) = self._materialize_metadata(
            site_id,
            rows,
            markers,
            now_utc=now,
            work_deadline_monotonic=work_deadline_monotonic,
        )
        checkpoint_fields: dict[str, Any] = {}
        if cursor is not None:
            checkpoint_fields = {
                "fast_checkpoint_started_at": cursor[0],
                "fast_checkpoint_cycle_id": cursor[1],
            }
        self.repository.update_site(
            site_id, source_head_utc=head[0], source_head_cycle_id=head[1],
            last_incremental_scan_at=now,
            backlog_cycle_count=int(
                budget_exhausted
                or len(rows) == max(1, min(int(limit), 100))
            ),
            **checkpoint_fields,
        )
        return ProjectionRunResult(
            site_id, examined, projected, replayed, corrected, 0, 0, False
        )

    def _materialize_metadata(
        self,
        site_id: str,
        rows: tuple[Mapping[str, Any], ...],
        markers: Mapping[str, str],
        *,
        now_utc: str,
        work_deadline_monotonic: float | None,
    ) -> tuple[int, int, int, int, int, tuple[str, str] | None, bool]:
        """Load/write a bounded metadata chunk without per-cycle connections."""
        all_changed_ids = tuple(
            str(row["cycle_id"])
            for row in rows
            if markers.get(str(row["cycle_id"]))
            != source_revision_marker(row)
        )
        changed_ids = all_changed_ids[:MAX_BULK_CYCLES_PER_TRANSACTION]
        loaded = dict(self.source.cycles(
            site_id,
            changed_ids,
            work_deadline_monotonic=work_deadline_monotonic,
            monotonic=self._monotonic,
        ))
        candidates = tuple(
            loaded[cycle_id]
            for cycle_id in changed_ids
            if cycle_id in loaded and loaded[cycle_id] is not None
        )
        written = dict(self.repository.upsert_cycles(
            candidates,
            now_utc,
            work_deadline_monotonic=work_deadline_monotonic,
            monotonic=self._monotonic,
        ))
        examined = projected = replayed = corrected = invalidated = 0
        cursor: tuple[str, str] | None = None
        budget_exhausted = False
        for row in rows:
            cycle_id = str(row["cycle_id"])
            old_marker = markers.get(cycle_id)
            if old_marker == source_revision_marker(row):
                replayed += 1
            elif cycle_id not in loaded:
                budget_exhausted = True
                break
            elif loaded[cycle_id] is None:
                invalidated += 1
            elif cycle_id not in written:
                budget_exhausted = True
                break
            else:
                projected += 1
                corrected += int(old_marker is not None and written[cycle_id])
            examined += 1
            cursor = (str(row["started_at"]), cycle_id)
        return (
            examined,
            projected,
            replayed,
            corrected,
            invalidated,
            cursor,
            budget_exhausted,
        )

    def reconcile_site(
        self,
        site_id: str,
        *,
        limit: int = 5000,
        allow_diverged: bool = False,
        work_deadline_monotonic: float | None = None,
        completion_deadline_monotonic: float | None = None,
    ) -> ProjectionRunResult:
        now = self._clock()
        state = self.repository.site_state(site_id) or {}
        repairing = state.get("status") == "rebuilding"
        if state.get("status") == "diverged" and not allow_diverged:
            raise TrafficProjectionDiverged("Projection Site remains diverged")
        head = self.source.head(site_id)
        if head is None:
            self.repository.update_site(
                site_id, status=(
                    "rebuilding" if state.get("status") == "rebuilding" else "stale"
                ), source_head_utc=None,
                source_head_cycle_id=None, last_incremental_scan_at=now,
                backlog_cycle_count=0,
            )
            return ProjectionRunResult(site_id, 0, 0, 0, 0, 0, 0, False)
        sweep_head = (
            (state.get("reconcile_sweep_source_head_utc"),
             state.get("reconcile_sweep_source_head_cycle_id"))
            if state.get("reconcile_sweep_source_head_utc") else head
        )
        from_utc = state.get("reconcile_sweep_from_utc")
        if not from_utc:
            from_utc = _minus_days(
                str(sweep_head[0]), self.config.retention_days
            )
            self.repository.update_site(
                site_id, reconcile_sweep_started_at=now,
                reconcile_sweep_source_head_utc=sweep_head[0],
                reconcile_sweep_source_head_cycle_id=sweep_head[1],
                reconcile_sweep_from_utc=from_utc,
            )
        cursor = None
        if state.get("reconcile_cursor_started_at"):
            cursor = (str(state["reconcile_cursor_started_at"]),
                      str(state["reconcile_cursor_cycle_id"]))
        metadata = self.source.metadata(
            site_id, from_utc=str(from_utc), through=(str(sweep_head[0]), str(sweep_head[1])),
            after=cursor, limit=max(1, min(int(limit), 5000)),
        )
        markers = self.repository.source_markers(
            site_id, tuple(str(row["cycle_id"]) for row in metadata)
        )
        (
            examined,
            projected,
            replayed,
            corrected,
            invalidated,
            cursor,
            budget_exhausted,
        ) = self._materialize_metadata(
            site_id,
            metadata,
            markers,
            now_utc=now,
            work_deadline_monotonic=work_deadline_monotonic,
        )
        if cursor is not None:
            self.repository.update_site(
                site_id, reconcile_cursor_started_at=cursor[0],
                reconcile_cursor_cycle_id=cursor[1], last_incremental_scan_at=now,
                last_incremental_progress_at=now,
                source_head_utc=head[0], source_head_cycle_id=head[1],
            )
        completed = (
            not budget_exhausted
            and len(metadata) < max(1, min(int(limit), 5000))
        )
        if (
            completed
            and completion_deadline_monotonic is not None
            and completion_deadline_monotonic - self._monotonic()
            < MAX_BULK_TRANSACTION_SECONDS
        ):
            completed = False
        deep_checked = 0
        if completed:
            source_count = self.source.cycle_count(
                site_id, from_utc=str(from_utc),
                through=(str(sweep_head[0]), str(sweep_head[1])),
            )
            projection_count = self.repository.cycle_count(
                site_id, from_utc=str(from_utc),
                through=(str(sweep_head[0]), str(sweep_head[1])),
            )
            if source_count != projection_count:
                self.repository.update_site(
                    site_id, status="diverged",
                    last_error_category="source_identity",
                )
                raise TrafficProjectionDiverged(
                    "Projection retained-horizon identity diverged"
                )
            deep_checked = self._deep_audit(site_id, tuple_head=(str(sweep_head[0]), str(sweep_head[1])))
            boundaries = self.source.boundaries(site_id, evaluated_at_utc=now)
            self.repository.update_site(
                site_id, status="healthy", reconcile_cursor_started_at=None,
                reconcile_cursor_cycle_id=None, reconcile_sweep_started_at=None,
                reconcile_sweep_source_head_utc=None,
                reconcile_sweep_source_head_cycle_id=None,
                reconcile_sweep_from_utc=None,
                last_full_reconcile_completed_at=now,
                last_full_reconcile_source_head_utc=sweep_head[0],
                last_full_reconcile_source_head_cycle_id=sweep_head[1],
                last_deep_audit_at=now, backlog_cycle_count=0,
                source_head_utc=head[0], source_head_cycle_id=head[1],
                last_error_category=None,
                **boundaries,
                source_boundary_proof_at=now,
                source_boundary_proof_head_utc=head[0],
                source_boundary_proof_head_cycle_id=head[1],
            )
        else:
            self.repository.update_site(
                site_id,
                status="rebuilding" if repairing else "catching_up",
                backlog_cycle_count=len(metadata),
                source_head_utc=head[0], source_head_cycle_id=head[1],
            )
        result = ProjectionRunResult(
            site_id, examined, projected, replayed, corrected, invalidated,
            deep_checked, completed,
        )
        self.telemetry.emit(
            "traffic_projection_reconcile_completed",
            projection_version=self.projection_version,
            site_id=site_id,
            cycles_examined=examined,
            cycles_projected=projected,
            cycles_replayed=replayed,
            cycles_corrected=corrected,
            cycles_invalidated=invalidated,
            deep_audit_checked=deep_checked,
        )
        return result

    def _reconciliation_due(self, site_id: str) -> bool:
        state = self.repository.site_state(site_id) or {}
        if state.get("reconcile_sweep_started_at"):
            return True
        completed = state.get("last_full_reconcile_completed_at")
        if not isinstance(completed, str):
            return True
        try:
            now = datetime.fromisoformat(self._clock().replace("Z", "+00:00"))
            prior = datetime.fromisoformat(completed.replace("Z", "+00:00"))
        except ValueError:
            return True
        return (
            now - prior
        ).total_seconds() >= self.config.full_reconcile_target_interval_seconds

    def repair_site(self, site_id: str) -> ProjectionRunResult:
        """Advance one durable bounded repair quantum for one Site."""
        if site_id not in self.config.site_ids:
            raise ValueError("Site is not configured")
        state = self.repository.site_state(site_id) or {}
        resuming = bool(
            state.get("status") == "rebuilding"
            and (
                state.get("last_error_category") == "repair_delete"
                or state.get("reconcile_sweep_started_at")
            )
        )
        if not resuming:
            self.repository.begin_site_repair(site_id)
        state = self.repository.site_state(site_id) or {}
        if state.get("last_error_category") == "repair_delete":
            deleted = self.repository.delete_site_cycles(
                site_id, limit=MAX_BULK_CYCLES_PER_TRANSACTION
            )
            if deleted == MAX_BULK_CYCLES_PER_TRANSACTION:
                return ProjectionRunResult(site_id, 0, 0, 0, 0, 0, 0, False)
        result = self.reconcile_site(
            site_id,
            limit=MAX_BULK_CYCLES_PER_TRANSACTION,
            allow_diverged=True,
        )
        if (
            result.sweep_completed
            and (self.repository.site_state(site_id) or {}).get("status") != "healthy"
        ):
            raise TrafficProjectionWriterUnavailable(
                "Projection Site repair did not establish healthy proof"
            )
        return result

    def rebuild_range(
        self, site_id: str, *, from_utc: str, to_utc: str
    ) -> int:
        """Explicitly reproject a bounded source-start range, never final buckets."""
        if site_id not in self.config.site_ids:
            raise ValueError("Site is not configured")
        start = datetime.fromisoformat(from_utc.replace("Z", "+00:00"))
        end = datetime.fromisoformat(to_utc.replace("Z", "+00:00"))
        if start.tzinfo is None or end.tzinfo is None or start >= end:
            raise ValueError("Range is invalid")
        state = self.repository.site_state(site_id) or {}
        if state.get("status") == "diverged":
            raise TrafficProjectionDiverged("Projection Site remains diverged")
        self.repository.update_site(site_id, status="rebuilding")
        cursor = None
        count = 0
        while True:
            rows = self.source.metadata(
                site_id, from_utc=from_utc, through=(to_utc, ""),
                after=cursor, limit=100,
            )
            if not rows:
                break
            for cycle in rows:
                value = self.source.cycle(site_id, str(cycle["cycle_id"]))
                if value is not None:
                    self.repository.upsert_cycle(value, self._clock())
                    count += 1
                cursor = (str(cycle["started_at"]), str(cycle["cycle_id"]))
            if len(rows) < 100:
                break
        self.repository.checkpoint_passive()
        self.reconcile_site(site_id)
        return count

    def cleanup(
        self, *, max_chunks: int = MAX_CLEANUP_CHUNKS_PER_INVOCATION
    ) -> int:
        if self.repository.version_status() not in {"active", "building", "ready"}:
            return 0
        cutoff = _minus_days(self._clock(), self.config.retention_days)
        remaining_chunks = max(1, min(int(max_chunks), MAX_CLEANUP_CHUNKS_PER_INVOCATION))
        deleted = 0
        for site_id in self.config.site_ids:
            while remaining_chunks > 0:
                chunk = self.repository.delete_before(site_id, cutoff)
                deleted += chunk
                remaining_chunks -= 1
                if chunk < MAX_BULK_CYCLES_PER_TRANSACTION:
                    break
            if remaining_chunks == 0:
                break
        self.repository.checkpoint_passive()
        return deleted

    def _version_service(self, projection_version: str) -> "TrafficProjectionService":
        record = self.repository.version_record(projection_version)
        if record is None:
            raise TrafficProjectionStorageCorrupt(
                "Traffic projection version is unavailable"
            )
        semantic = str(record["semantic_contract_sha256"])
        if semantic not in self.supported_semantic_contracts:
            raise TrafficProjectionStorageCorrupt(
                "Traffic projection semantic contract is unsupported"
            )
        return TrafficProjectionService(
            self.config,
            repository=TrafficProjectionRepository(
                str(self.repository.db_path), projection_version=projection_version
            ),
            source=self.source,
            logger=self.logger,
            clock=self._clock,
            monotonic=self._monotonic,
            projection_version=projection_version,
            semantic_contract_sha256=semantic,
            supported_semantic_contracts=self.supported_semantic_contracts,
        )

    def _owned_worker_services(self) -> tuple["TrafficProjectionService", ...]:
        """Return active-first contexts owned by this one locked writer process."""
        self.initialize()
        services: list[TrafficProjectionService] = []
        for record in self.repository.worker_version_records():
            version = str(record["projection_version"])
            semantic = str(record["semantic_contract_sha256"])
            if semantic not in self.supported_semantic_contracts:
                continue
            services.append(
                self if version == self.projection_version
                else self._version_service(version)
            )
        return tuple(services)

    def _record_worker_failure(self, site_id: str) -> None:
        try:
            state = self.repository.site_state(site_id) or {}
            self.repository.update_site(
                site_id,
                status=(
                    "rebuilding" if state.get("status") == "rebuilding" else "stale"
                ),
                last_error_category=(
                    "repair_delete"
                    if state.get("last_error_category") == "repair_delete"
                    else "source_or_storage"
                ),
            )
        except Exception:
            pass

    def _maintain_version(
        self,
        service: "TrafficProjectionService",
        *,
        is_target: bool,
        active_deadline_monotonic: float | None = None,
    ) -> tuple[ProjectionRunResult, ...]:
        """Run active maintenance or one bounded target Site quantum."""
        version_results: list[ProjectionRunResult] = []
        service.initialize()
        site_ids = service.config.site_ids
        if is_target and site_ids:
            site_ids = (site_ids[self._target_site_index % len(site_ids)],)
            self._target_site_index = (
                self._target_site_index + 1
            ) % len(service.config.site_ids)
        target_deadline = None
        if is_target:
            target_deadline = self._monotonic() + MAX_BULK_TRANSACTION_SECONDS
            if active_deadline_monotonic is not None:
                target_deadline = min(
                    target_deadline, active_deadline_monotonic
                )
        for site_id in site_ids:
            if self._stop.is_set():
                break
            try:
                state = service.repository.site_state(site_id) or {}
                repairing = bool(
                    service.repository.version_status() == "active"
                    and state.get("status") == "rebuilding"
                    and (
                        state.get("last_error_category") == "repair_delete"
                        or state.get("reconcile_sweep_started_at")
                    )
                )
                if repairing:
                    version_results.append(service.repair_site(site_id))
                    continue
                target_quantum = MAX_BULK_CYCLES_PER_TRANSACTION
                incremental = service.incremental_site(
                    site_id,
                    limit=target_quantum if is_target else 100,
                    work_deadline_monotonic=target_deadline,
                )
                reconciliation_due = service._reconciliation_due(site_id)
                if (
                    reconciliation_due
                    and (
                        target_deadline is None
                        or self._monotonic() < target_deadline
                    )
                ):
                    version_results.append(service.reconcile_site(
                        site_id,
                        limit=target_quantum if is_target else 5000,
                        work_deadline_monotonic=target_deadline,
                        completion_deadline_monotonic=(
                            active_deadline_monotonic if is_target else None
                        ),
                    ))
                else:
                    version_results.append(incremental)
            except TrafficProjectionDiverged:
                service.telemetry.emit(
                    "traffic_projection_scan_failed",
                    projection_version=service.projection_version,
                    site_id=site_id,
                    error_category="diverged",
                )
            except Exception:
                service._record_worker_failure(site_id)
                service.telemetry.emit(
                    "traffic_projection_scan_failed",
                    projection_version=service.projection_version,
                    site_id=site_id,
                    error_category="source_or_storage",
                )
        return tuple(version_results)

    def _worker_services_by_role(
        self,
    ) -> tuple[
        tuple["TrafficProjectionService", ...],
        tuple["TrafficProjectionService", ...],
    ]:
        services = self._owned_worker_services()
        active_version = self.repository.active_version()
        active = tuple(
            service for service in services
            if service.projection_version == active_version
        )
        targets = tuple(
            service for service in services
            if service.projection_version != active_version
        )
        return active, targets

    def _target_window(
        self,
        targets: tuple["TrafficProjectionService", ...],
        *,
        active_deadline_monotonic: float,
    ) -> Mapping[str, tuple[ProjectionRunResult, ...]]:
        """Use idle active-cadence budget for separately committed target quanta."""
        results: dict[str, tuple[ProjectionRunResult, ...]] = {}
        if not targets:
            return results
        idle_quanta = 0
        idle_limit = max(
            sum(len(service.config.site_ids) for service in targets), 1
        )
        target_index = 0
        while not self._stop.is_set():
            remaining = active_deadline_monotonic - self._monotonic()
            if remaining < MAX_BULK_TRANSACTION_SECONDS:
                break
            service = targets[target_index % len(targets)]
            target_index += 1
            quantum = self._maintain_version(
                service,
                is_target=True,
                active_deadline_monotonic=active_deadline_monotonic,
            )
            results[service.projection_version] = quantum
            progressed = any(
                result.cycles_examined > 0 or result.sweep_completed
                for result in quantum
            )
            idle_quanta = 0 if progressed else idle_quanta + 1
            if idle_quanta >= idle_limit:
                break
        return results

    def worker_iteration(self) -> Mapping[str, tuple[ProjectionRunResult, ...]]:
        """Maintain active first, then advance one bounded target quantum."""
        results: dict[str, tuple[ProjectionRunResult, ...]] = {}
        active, targets = self._worker_services_by_role()
        for service in active:
            results[service.projection_version] = self._maintain_version(
                service, is_target=False
            )
        if targets:
            service = targets[0]
            results[service.projection_version] = self._maintain_version(
                service, is_target=True
            )
        self._checkpoint_if_due()
        return results

    def serve_forever(self) -> None:
        with writer_lock(self.config.writer_lock_path):
            while not self._stop.is_set():
                started = self._monotonic()
                active, targets = self._worker_services_by_role()
                for service in active:
                    self._maintain_version(service, is_target=False)
                self._cleanup_if_due()
                active_deadline = (
                    started + self.config.source_head_scan_interval_seconds
                )
                self._target_window(
                    targets,
                    active_deadline_monotonic=active_deadline,
                )
                self._checkpoint_if_due()
                remaining = max(
                    active_deadline - self._monotonic(), 0.0,
                )
                self._stop.wait(remaining)

    def stop(self) -> None:
        self._stop.set()

    def health(self, site_id: str) -> Mapping[str, Any]:
        state = self.repository.site_state(site_id)
        version = self.repository.version_record()
        version_status = None if version is None else str(version.get("status"))
        version_available = bool(
            version_status == "active"
            and version is not None
            and version.get("semantic_contract_sha256")
            in self.supported_semantic_contracts
        )
        source_available = True
        try:
            current_head = self.source.head(site_id)
        except Exception:
            current_head = None
            source_available = False
        if state is not None and current_head is not None:
            state = dict(state)
            state["source_head_utc"], state["source_head_cycle_id"] = current_head
        return classify_projection_health(
            state,
            now_utc=self._clock(),
            version_available=version_available,
            source_available=source_available and current_head is not None,
            build_state=version_status,
        ).safe_dict()

    def _deep_audit(self, site_id: str, *, tuple_head: tuple[str, str]) -> int:
        with self.repository.read_connection() as connection:
            rows = connection.execute(
                """SELECT cycle_id,source_semantic_fingerprint FROM traffic_projection_cycles
                   WHERE projection_version=? AND site_id=? AND source_started_at>=?
                     AND (source_started_at<? OR
                          (source_started_at=? AND cycle_id<=?))
                   ORDER BY cycle_id""",
                (
                    self.projection_version,
                    site_id,
                    _minus_days(tuple_head[0], self.config.retention_days),
                    tuple_head[0],
                    tuple_head[0],
                    tuple_head[1],
                ),
            ).fetchall()
        if not rows:
            return 0
        count = min(100, max(10, (len(rows) + 99) // 100), len(rows))
        seed = (
            f"{site_id}|{self.projection_version}|{tuple_head[0]}|{tuple_head[1]}"
        )
        rng = random.Random(hashlib.sha256(seed.encode("utf-8")).digest())
        for row in rng.sample(list(rows), count):
            source = self.source.cycle(site_id, str(row["cycle_id"]))
            if source is None or source.source_semantic_fingerprint != row["source_semantic_fingerprint"]:
                self.repository.update_site(site_id, status="diverged", last_error_category="deep_fingerprint")
                raise TrafficProjectionDiverged("Projection deep audit diverged")
        return count

    def _checkpoint_if_due(self) -> None:
        now = self._monotonic()
        if now - self._last_checkpoint >= 60:
            self.repository.checkpoint_passive()
            self._last_checkpoint = now

    def _cleanup_if_due(self) -> None:
        now = self._monotonic()
        if now - self._last_cleanup >= 86400:
            for service in self._owned_worker_services():
                service.cleanup()
            self._last_cleanup = now


@contextmanager
def writer_lock(path: str) -> Iterator[None]:
    lock_path = Path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_path, "a+b")  # noqa: SIM115 - handle spans context
    try:
        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        try:
            os.chmod(lock_path, 0o600)
        except OSError:
            pass
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise TrafficProjectionWriterUnavailable("Projection writer is already active") from exc
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise TrafficProjectionWriterUnavailable("Projection writer is already active") from exc
        yield
    finally:
        try:
            if os.name == "nt":
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        handle.close()


def _minus_days(value: str, days: int) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (parsed - timedelta(days=days)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
