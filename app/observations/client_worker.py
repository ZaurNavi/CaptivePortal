"""Bounded fixed-delay collector for Omada client observations."""

from __future__ import annotations

import logging
import threading
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from app.models import Result

from .models import ObservationConfig, utc_now
from .normalizer import (
    canonical_client_mac,
    classify_client,
    normalize_client_observation,
)
from .repository import ObservationRepository


@dataclass(frozen=True, slots=True)
class ClientCycleOutcome:
    site_id: str
    cycle_id: str | None
    result: str
    complete: bool
    items_seen: int
    items_stored: int
    items_skipped: int
    duplicate_mac_count: int
    unknown_auth_status_count: int
    failure_category: str | None = None


@dataclass(slots=True)
class _Inventory:
    rows: list[Any]
    total_rows: int | None
    complete: bool
    result: str
    error_count: int
    quality_warnings: int
    failure_category: str | None = None
    http_status: int | None = None
    error_code: int | None = None


class ClientObservationWorker:
    """One stoppable worker using an already-created shared provider."""

    def __init__(
        self,
        *,
        provider: Any,
        repository: ObservationRepository,
        config: ObservationConfig,
        logger: logging.Logger,
        now_factory: Callable[[], str] = utc_now,
        monotonic: Callable[[], float] = time.monotonic,
    ):
        self.provider = provider
        self.repository = repository
        self.config = config
        self.logger = logger
        self._now_factory = now_factory
        self._monotonic = monotonic
        self._stop_event = threading.Event()
        self._lifecycle_lock = threading.Lock()
        self._cycle_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.last_error: Exception | None = None
        self.degraded = False

    @property
    def running(self) -> bool:
        with self._lifecycle_lock:
            return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        if not self.config.enabled or not self.config.client_enabled:
            return False
        with self._lifecycle_lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self._stop_event.clear()
            self.last_error = None
            self._thread = threading.Thread(
                target=self._run,
                name="client-observation-worker",
                daemon=True,
            )
            self._thread.start()
            return True

    def stop(self, timeout: float | None = None) -> bool:
        self._stop_event.set()
        with self._lifecycle_lock:
            thread = self._thread
        if thread is None:
            return True
        thread.join(
            self.config.shutdown_timeout_seconds
            if timeout is None
            else max(0.0, float(timeout))
        )
        stopped = not thread.is_alive()
        if stopped:
            with self._lifecycle_lock:
                if self._thread is thread:
                    self._thread = None
        return stopped

    def run_once(self) -> tuple[ClientCycleOutcome, ...]:
        if (
            not self.config.enabled
            or not self.config.client_enabled
            or self._stop_event.is_set()
        ):
            return ()
        if not self._cycle_lock.acquire(blocking=False):
            return ()
        outcomes: list[ClientCycleOutcome] = []
        try:
            for site_id in self.config.site_ids:
                if self._stop_event.is_set():
                    break
                outcomes.append(self._run_site(site_id))
            self.degraded = any(
                outcome.result not in {"success"}
                for outcome in outcomes
            )
            if not self.degraded:
                self.last_error = None
            return tuple(outcomes)
        finally:
            self._cycle_lock.release()

    def _run(self) -> None:
        if self._stop_event.wait(
            self.config.client_initial_delay_seconds
        ):
            return
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception as exc:  # Last-resort fail-open boundary.
                self.last_error = exc
                self.degraded = True
                self.logger.error(
                    "observation.client_cycle_failed "
                    "failure_category=worker_error"
                )
            if self._stop_event.wait(
                self.config.client_interval_seconds
            ):
                return

    def _run_site(self, site_id: str) -> ClientCycleOutcome:
        started_at = self._now_factory()
        started_monotonic = self._monotonic()
        try:
            cycle = self.repository.create_cycle(
                kind="client",
                site_id=site_id,
                started_at=started_at,
            )
        except Exception as exc:
            self.last_error = exc
            self.degraded = True
            self._log_storage_error(site_id=site_id, cycle_id=None)
            return ClientCycleOutcome(
                site_id=site_id,
                cycle_id=None,
                result="failed",
                complete=False,
                items_seen=0,
                items_stored=0,
                items_skipped=0,
                duplicate_mac_count=0,
                unknown_auth_status_count=0,
                failure_category="storage_error",
            )

        inventory = self._poll_inventory(site_id)
        counts = Counter(
            mac
            for raw in inventory.rows
            if (mac := canonical_client_mac(raw)) is not None
        )
        duplicate_macs = {
            mac for mac, count in counts.items() if count > 1
        }
        duplicate_count = len(duplicate_macs)
        unknown_auth_status_count = 0
        rows: list[dict[str, Any]] = []
        for raw in inventory.rows:
            eligibility = classify_client(raw, self.config.client_ssids)
            if eligibility.unknown_auth_status:
                unknown_auth_status_count += 1
            if (
                not eligibility.eligible
                or eligibility.client_mac in duplicate_macs
            ):
                continue
            normalized = normalize_client_observation(
                raw,
                cycle_id=cycle.cycle_id,
                site_id=site_id,
                observed_at=started_at,
                source_inventory_complete=inventory.complete,
            )
            if normalized is not None:
                rows.append(normalized)

        items_seen = len(inventory.rows)
        items_stored = 0
        error_count = inventory.error_count
        quality_warnings = (
            inventory.quality_warnings
            + duplicate_count
            + unknown_auth_status_count
        )
        result_name = inventory.result
        complete = inventory.complete
        failure_category = inventory.failure_category
        try:
            items_stored = self.repository.insert_client_batch(rows)
        except Exception as exc:
            self.last_error = exc
            result_name = "failed"
            complete = False
            error_count += 1
            failure_category = "storage_error"
            self._log_storage_error(
                site_id=site_id,
                cycle_id=cycle.cycle_id,
            )

        items_skipped = max(0, items_seen - items_stored)
        try:
            self.repository.finalize_cycle(
                cycle.cycle_id,
                finished_at=self._now_factory(),
                complete=complete,
                result=result_name,
                source_rows_reported=inventory.total_rows,
                items_seen=items_seen,
                items_stored=items_stored,
                items_skipped=items_skipped,
                error_count=error_count,
                data_quality_warning_count=quality_warnings,
            )
        except Exception as exc:
            self.last_error = exc
            result_name = "failed"
            complete = False
            failure_category = "storage_error"
            self._log_storage_error(
                site_id=site_id,
                cycle_id=cycle.cycle_id,
            )

        duration_ms = max(
            0,
            int((self._monotonic() - started_monotonic) * 1000),
        )
        if duplicate_count:
            self.logger.warning(
                "observation.client_duplicate_mac site_id=%s cycle_id=%s "
                "duplicate_mac_count=%s",
                site_id,
                cycle.cycle_id,
                duplicate_count,
            )
        event = (
            "observation.client_cycle_completed"
            if result_name == "success"
            else "observation.client_cycle_failed"
        )
        self.logger.info(
            "%s site_id=%s cycle_id=%s duration_ms=%s complete=%s "
            "items_seen=%s items_stored=%s items_skipped=%s "
            "error_count=%s duplicate_mac_count=%s "
            "unknown_auth_status_count=%s failure_category=%s "
            "http_status=%s error_code=%s",
            event,
            site_id,
            cycle.cycle_id,
            duration_ms,
            complete,
            items_seen,
            items_stored,
            items_skipped,
            error_count,
            duplicate_count,
            unknown_auth_status_count,
            failure_category,
            inventory.http_status,
            inventory.error_code,
        )
        return ClientCycleOutcome(
            site_id=site_id,
            cycle_id=cycle.cycle_id,
            result=result_name,
            complete=complete,
            items_seen=items_seen,
            items_stored=items_stored,
            items_skipped=items_skipped,
            duplicate_mac_count=duplicate_count,
            unknown_auth_status_count=unknown_auth_status_count,
            failure_category=failure_category,
        )

    def _poll_inventory(self, site_id: str) -> _Inventory:
        rows: list[Any] = []
        expected_total: int | None = None
        last_status: int | None = None
        last_error_code: int | None = None
        for page in range(1, self.config.client_max_pages + 1):
            if self._stop_event.is_set():
                return _Inventory(
                    rows, expected_total, False, "shutdown", 0, 1,
                    "shutdown", last_status, last_error_code,
                )
            try:
                result = self.provider.list_observation_clients(
                    site_id,
                    page,
                    self.config.client_page_size,
                    self.config.request_timeout_seconds,
                )
            except Exception:
                return _Inventory(
                    rows=rows,
                    total_rows=expected_total,
                    complete=False,
                    result="partial" if rows else "failed",
                    error_count=1,
                    quality_warnings=0,
                    failure_category="provider_error",
                    http_status=None,
                    error_code=None,
                )
            if not isinstance(result, Result) or not result.success:
                data = (
                    result.data
                    if isinstance(result, Result)
                    and isinstance(result.data, Mapping)
                    else {}
                )
                category = _safe_category(data.get("failure_category"))
                return _Inventory(
                    rows=rows,
                    total_rows=expected_total,
                    complete=False,
                    result="partial" if rows else "failed",
                    error_count=1,
                    quality_warnings=0,
                    failure_category=category,
                    http_status=_safe_int(data.get("http_status")),
                    error_code=_safe_int(data.get("error_code")),
                )
            data = result.data if isinstance(result.data, Mapping) else {}
            page_rows = data.get("clients")
            total_rows = data.get("total_rows")
            returned_page = data.get("page")
            if (
                not isinstance(page_rows, list)
                or type(total_rows) is not int
                or total_rows < 0
                or type(returned_page) is not int
                or returned_page != page
                or (
                    expected_total is not None
                    and total_rows != expected_total
                )
            ):
                return _Inventory(
                    rows, expected_total, False,
                    "partial" if rows else "failed", 1, 1,
                    "malformed_response",
                    _safe_int(data.get("http_status")),
                    _safe_int(data.get("error_code")),
                )
            expected_total = total_rows
            last_status = _safe_int(data.get("http_status"))
            last_error_code = _safe_int(data.get("error_code"))
            remaining = self.config.client_max_rows - len(rows)
            if remaining <= 0:
                return _Inventory(
                    rows, expected_total, False, "partial", 1, 1,
                    "row_limit", last_status, last_error_code,
                )
            rows.extend(page_rows[:remaining])
            if len(page_rows) > remaining:
                return _Inventory(
                    rows, expected_total, False, "partial", 1, 1,
                    "row_limit", last_status, last_error_code,
                )
            if len(rows) > expected_total:
                return _Inventory(
                    rows, expected_total, False, "partial", 1, 1,
                    "inconsistent_total", last_status, last_error_code,
                )
            if len(rows) == expected_total:
                return _Inventory(
                    rows, expected_total, True, "success", 0, 0,
                    None, last_status, last_error_code,
                )
            if expected_total > self.config.client_max_rows:
                return _Inventory(
                    rows, expected_total, False, "partial", 1, 1,
                    "row_limit", last_status, last_error_code,
                )
            if not page_rows or len(page_rows) < self.config.client_page_size:
                return _Inventory(
                    rows, expected_total, False, "partial", 1, 1,
                    "inconsistent_total", last_status, last_error_code,
                )
        return _Inventory(
            rows, expected_total, False, "partial", 1, 1,
            "page_limit", last_status, last_error_code,
        )

    def _log_storage_error(
        self,
        *,
        site_id: str,
        cycle_id: str | None,
    ) -> None:
        self.logger.error(
            "observation.storage_error site_id=%s cycle_id=%s "
            "failure_category=storage_error",
            site_id,
            cycle_id,
        )


def _safe_int(value: Any) -> int | None:
    return value if type(value) is int else None


def _safe_category(value: Any) -> str:
    allowed = {
        "timeout", "network_error", "http_error", "token_error",
        "token_expired", "malformed_response", "controller_error",
        "invalid_argument", "provider_error",
    }
    return (
        value
        if isinstance(value, str) and value in allowed
        else "unknown_error"
    )
