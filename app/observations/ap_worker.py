"""Bounded sequential AP dynamic/config observation worker."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from app.models import Result

from .ap_normalizer import (
    build_ap_config,
    canonical_ap_mac,
    normalize_ap_lan,
    normalize_ap_overview,
    normalize_ap_radios,
    normalize_ap_wired,
)
from .models import ObservationConfig, parse_utc, utc_now
from .repository import ObservationRepository
from .telemetry import ObservationTelemetry


_CALL_FAILED = object()


@dataclass(frozen=True, slots=True)
class APCycleOutcome:
    site_id: str
    kind: str
    cycle_id: str | None
    result: str
    complete: bool
    items_seen: int
    items_stored: int
    items_skipped: int
    error_count: int
    request_count: int
    failure_category: str | None = None


@dataclass(frozen=True, slots=True)
class _CachedInventory:
    ap_macs: tuple[str, ...]
    source_rows: int
    captured_monotonic: float
    quality_warnings: int
    duplicate_ap_mac_count: int


@dataclass(slots=True)
class _InventoryResult:
    ap_macs: tuple[str, ...]
    source_rows: int | None
    complete: bool
    quality_warnings: int
    error_count: int
    failure_category: str | None
    stale_cache_used: bool = False
    cache_age_seconds: float | None = None
    duplicate_ap_mac_count: int = 0


class _Budget:
    def __init__(self, *, deadline: float, maximum: int, monotonic, stop_event):
        self.deadline = deadline
        self.maximum = maximum
        self.monotonic = monotonic
        self.stop_event = stop_event
        self.used = 0
        self.exhausted_reason: str | None = None

    def take(self, requested_timeout: float) -> float | None:
        if self.stop_event.is_set():
            self.exhausted_reason = "shutdown"
            return None
        remaining = self.deadline - self.monotonic()
        if remaining <= 0:
            self.exhausted_reason = "deadline"
            return None
        if self.used >= self.maximum:
            self.exhausted_reason = "request_budget"
            return None
        self.used += 1
        return min(requested_timeout, remaining)


class APObservationWorker:
    """One thread owns both dynamic and slow AP schedules."""

    _DYNAMIC = (
        ("overview", "get_observation_ap_overview", normalize_ap_overview),
        ("wired_uplink", "get_observation_ap_wired_uplink", normalize_ap_wired),
        ("lan_traffic", "get_observation_ap_lan_traffic", normalize_ap_lan),
        ("radios", "get_observation_ap_radios", normalize_ap_radios),
    )
    _CONFIG = (
        ("general_config", "get_observation_ap_general_config"),
        ("ip_setting", "get_observation_ap_ip_setting"),
        ("radio_config", "get_observation_ap_radio_config"),
        ("ofdma", "get_observation_ap_ofdma"),
        ("available_channels", "get_observation_ap_available_channels"),
        ("safe_overrides", "get_observation_ap_safe_overrides"),
        ("rf_scan_state", "get_observation_ap_rf_scan_state"),
    )

    def __init__(
        self,
        *,
        provider: Any,
        repository: ObservationRepository,
        config: ObservationConfig,
        telemetry: ObservationTelemetry,
        now_factory: Callable[[], str] = utc_now,
        monotonic: Callable[[], float] = time.monotonic,
    ):
        self.provider = provider
        self.repository = repository
        self.config = config
        self.telemetry = telemetry
        self._now_factory = now_factory
        self._monotonic = monotonic
        self._stop_event = threading.Event()
        self._lifecycle_lock = threading.Lock()
        self._cycle_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._inventory_cache: dict[str, _CachedInventory] = {}
        self._cursor: dict[tuple[str, str], int] = {}
        self.last_error: Exception | None = None
        self.degraded = False

    @property
    def running(self) -> bool:
        with self._lifecycle_lock:
            return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        if not self.config.enabled or not self.config.ap_enabled:
            return False
        with self._lifecycle_lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self._stop_event.clear()
            self.last_error = None
            self._thread = threading.Thread(
                target=self._run,
                name="ap-observation-worker",
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
        thread.join(self.config.shutdown_timeout_seconds if timeout is None else max(0.0, float(timeout)))
        stopped = not thread.is_alive()
        if stopped:
            with self._lifecycle_lock:
                if self._thread is thread:
                    self._thread = None
        return stopped

    def run_dynamic_once(self) -> tuple[APCycleOutcome, ...]:
        return self._run_kind("ap_dynamic")

    def run_config_once(self) -> tuple[APCycleOutcome, ...]:
        return self._run_kind("ap_config")

    def _run_kind(self, kind: str) -> tuple[APCycleOutcome, ...]:
        if not self.config.enabled or not self.config.ap_enabled or self._stop_event.is_set():
            return ()
        if not self._cycle_lock.acquire(blocking=False):
            return ()
        outcomes: list[APCycleOutcome] = []
        try:
            for site_id in self.config.site_ids:
                if self._stop_event.is_set():
                    break
                outcomes.append(
                    self._run_dynamic_site(site_id)
                    if kind == "ap_dynamic"
                    else self._run_config_site(site_id)
                )
            self.degraded = any(outcome.result != "success" for outcome in outcomes)
            if not self.degraded:
                self.last_error = None
            return tuple(outcomes)
        finally:
            self._cycle_lock.release()

    def _run(self) -> None:
        if self._stop_event.wait(self.config.ap_initial_delay_seconds):
            return
        dynamic_due = self._monotonic()
        config_due = dynamic_due
        while not self._stop_event.is_set():
            now = self._monotonic()
            try:
                if now >= dynamic_due:
                    self.run_dynamic_once()
                    dynamic_due = self._monotonic() + self.config.ap_interval_seconds
                    now = self._monotonic()
                if now >= config_due and not self._stop_event.is_set():
                    self.run_config_once()
                    config_due = self._monotonic() + self.config.ap_config_interval_seconds
            except Exception as exc:
                self.last_error = exc
                self.degraded = True
                self.telemetry.emit("observation.ap_cycle_failed", "error", failure_category="worker_error")
                dynamic_due = self._monotonic() + self.config.ap_interval_seconds
                config_due = self._monotonic() + self.config.ap_config_interval_seconds
            wait_for = max(0.001, min(dynamic_due, config_due) - self._monotonic())
            self._stop_event.wait(wait_for)

    def _new_cycle(self, site_id: str, kind: str):
        try:
            return self.repository.create_cycle(kind=kind, site_id=site_id, started_at=self._now_factory())
        except Exception as exc:
            self.last_error = exc
            self.degraded = True
            self.telemetry.emit("observation.storage_error", "error", site_id=site_id, kind=kind, failure_category="storage_error")
            return None

    def _run_dynamic_site(self, site_id: str) -> APCycleOutcome:
        started = self._monotonic()
        cycle = self._new_cycle(site_id, "ap_dynamic")
        if cycle is None:
            return self._failed_without_cycle(site_id, "ap_dynamic")
        budget = _Budget(
            deadline=started + self.config.ap_cycle_max_duration_seconds,
            maximum=self.config.ap_dynamic_max_requests_per_cycle,
            monotonic=self._monotonic,
            stop_event=self._stop_event,
        )
        inventory = self._inventory(site_id, budget)
        entries: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
        errors = inventory.error_count
        warnings = inventory.quality_warnings
        attempted = 0
        ordered = self._ordered(site_id, "ap_dynamic", inventory.ap_macs)
        for ap_mac in ordered:
            if budget.exhausted_reason or self._stop_event.is_set():
                break
            attempted += 1
            values: dict[str, Any] = {}
            timestamps: dict[str, str] = {}
            radio_rows: tuple[dict[str, Any], ...] | None = None
            ok: dict[str, bool] = {}
            for section, method_name, normalizer in self._DYNAMIC:
                result = self._call(site_id, ap_mac, method_name, budget, section)
                if result is _CALL_FAILED:
                    ok[section] = False
                    errors += 1
                    if budget.exhausted_reason is not None:
                        break
                    continue
                normalized = normalizer(result)
                if normalized is None:
                    ok[section] = False
                    errors += 1
                    self._endpoint_failed(site_id, ap_mac, section, "malformed_response")
                    continue
                ok[section] = True
                timestamps[section] = self._now_factory()
                if section == "radios":
                    radio_rows = normalized
                else:
                    values.update(normalized)
            if not any(ok.values()):
                continue
            observed_at = self._now_factory()
            ap_row: dict[str, Any] = {
                "cycle_id": cycle.cycle_id,
                "observed_at": observed_at,
                "site_id": site_id,
                "ap_mac": ap_mac,
                "partial": not all(ok.get(name, False) for name, _, _ in self._DYNAMIC),
                "overview_ok": ok.get("overview", False),
                "wired_uplink_ok": ok.get("wired_uplink", False),
                "lan_traffic_ok": ok.get("lan_traffic", False),
                "radios_ok": ok.get("radios", False),
                "overview_observed_at": timestamps.get("overview"),
                "wired_observed_at": timestamps.get("wired_uplink"),
                "lan_observed_at": timestamps.get("lan_traffic"),
                **values,
            }
            rate_errors = self._apply_ap_rates(ap_row, site_id, ap_mac)
            errors += rate_errors
            if rate_errors:
                ap_row["partial"] = True
            prepared_radios: list[dict[str, Any]] = []
            if radio_rows is not None:
                radio_time = timestamps["radios"]
                bands = [row.get("band") for row in radio_rows]
                duplicate_bands = {band for band in bands if bands.count(band) > 1}
                if duplicate_bands:
                    warnings += len(duplicate_bands)
                    ap_row["partial"] = True
                for row in radio_rows:
                    if row.get("band") in duplicate_bands:
                        continue
                    complete = {**row, "radio_observed_at": radio_time}
                    rate_errors = self._apply_radio_rates(complete, site_id, ap_mac)
                    errors += rate_errors
                    if rate_errors:
                        ap_row["partial"] = True
                    prepared_radios.append(complete)
            entries.append((ap_row, prepared_radios))
        if ordered and attempted < len(ordered):
            warnings += 1
            self._advance_cursor(site_id, "ap_dynamic", len(ordered), attempted)
        ap_inserted = radio_inserted = 0
        if entries:
            try:
                ap_inserted, radio_inserted = self.repository.insert_ap_batch(entries)
            except Exception as exc:
                self.last_error = exc
                errors += 1
                self.telemetry.emit("observation.storage_error", "error", site_id=site_id, cycle_id=cycle.cycle_id, failure_category="storage_error")
        result, complete, failure = self._dynamic_result(inventory, ordered, entries, ap_inserted, budget)
        return self._finalize(
            cycle, kind="ap_dynamic", result=result, complete=complete,
            source_rows=inventory.source_rows, items_seen=len(ordered),
            items_stored=ap_inserted, errors=errors, warnings=warnings,
            request_count=budget.used, failure=failure or inventory.failure_category,
            extra={
                "radio_rows_stored": radio_inserted,
                "duplicate_ap_mac_count": inventory.duplicate_ap_mac_count,
                "inventory_stale_cache_used": inventory.stale_cache_used,
                "inventory_cache_age_seconds": inventory.cache_age_seconds,
            },
            started=started,
        )

    def _run_config_site(self, site_id: str) -> APCycleOutcome:
        started = self._monotonic()
        cycle = self._new_cycle(site_id, "ap_config")
        if cycle is None:
            return self._failed_without_cycle(site_id, "ap_config")
        budget = _Budget(
            deadline=started + self.config.ap_config_cycle_max_duration_seconds,
            maximum=self.config.ap_config_max_requests_per_cycle,
            monotonic=self._monotonic,
            stop_event=self._stop_event,
        )
        inventory = self._inventory(site_id, budget)
        rows: list[dict[str, Any]] = []
        errors = inventory.error_count
        warnings = inventory.quality_warnings
        complete_aps = 0
        unchanged = 0
        attempted = 0
        ordered = self._ordered(site_id, "ap_config", inventory.ap_macs)
        for ap_mac in ordered:
            if budget.exhausted_reason or self._stop_event.is_set():
                break
            attempted += 1
            sections: dict[str, Any] = {}
            failed = False
            for section, method_name in self._CONFIG:
                result = self._call(site_id, ap_mac, method_name, budget, section)
                if result is _CALL_FAILED:
                    errors += 1
                    failed = True
                    break
                sections[section] = result
            canonical = None if failed else build_ap_config(sections)
            if canonical is None:
                if not failed:
                    errors += 1
                    self._endpoint_failed(site_id, ap_mac, "config_normalization", "unsafe_or_malformed")
                self.telemetry.emit("observation.ap_config_failed", "warning", site_id=site_id, cycle_id=cycle.cycle_id, ap_mac=ap_mac, failure_category="section_incomplete")
                continue
            complete_aps += 1
            try:
                previous = self.repository.get_latest_complete_config_hash(site_id=site_id, ap_mac=ap_mac)
            except Exception as exc:
                self.last_error = exc
                errors += 1
                self.telemetry.emit("observation.storage_error", "error", site_id=site_id, cycle_id=cycle.cycle_id, failure_category="storage_error")
                continue
            if previous == canonical.sha256:
                unchanged += 1
                self.telemetry.emit("observation.ap_config_unchanged", site_id=site_id, cycle_id=cycle.cycle_id, ap_mac=ap_mac)
                continue
            rows.append({
                "cycle_id": cycle.cycle_id,
                "captured_at": self._now_factory(),
                "site_id": site_id,
                "ap_mac": ap_mac,
                "config_sha256": canonical.sha256,
                "schema_version": 1,
                "config_json": canonical.config_json,
            })
        if ordered and attempted < len(ordered):
            warnings += 1
            self._advance_cursor(site_id, "ap_config", len(ordered), attempted)
        inserted = 0
        if rows:
            try:
                inserted = self.repository.insert_ap_config_batch(rows)
            except Exception as exc:
                self.last_error = exc
                errors += 1
                self.telemetry.emit("observation.storage_error", "error", site_id=site_id, cycle_id=cycle.cycle_id, failure_category="storage_error")
        for row in rows[:inserted]:
            self.telemetry.emit("observation.ap_config_captured", site_id=site_id, cycle_id=cycle.cycle_id, ap_mac=row["ap_mac"])
        result, complete, failure = self._config_result(inventory, ordered, complete_aps, budget, errors)
        return self._finalize(
            cycle, kind="ap_config", result=result, complete=complete,
            source_rows=inventory.source_rows, items_seen=len(ordered),
            items_stored=inserted, errors=errors, warnings=warnings,
            request_count=budget.used, failure=failure or inventory.failure_category,
            extra={
                "unchanged_count": unchanged,
                "complete_ap_count": complete_aps,
                "duplicate_ap_mac_count": inventory.duplicate_ap_mac_count,
                "inventory_stale_cache_used": inventory.stale_cache_used,
                "inventory_cache_age_seconds": inventory.cache_age_seconds,
            },
            started=started,
        )

    def _inventory(self, site_id: str, budget: _Budget) -> _InventoryResult:
        now = self._monotonic()
        cached = self._inventory_cache.get(site_id)
        if cached is not None and now - cached.captured_monotonic < self.config.ap_inventory_interval_seconds:
            return _InventoryResult(
                cached.ap_macs,
                cached.source_rows,
                True,
                cached.quality_warnings,
                0,
                None,
                cache_age_seconds=max(0.0, now - cached.captured_monotonic),
                duplicate_ap_mac_count=cached.duplicate_ap_mac_count,
            )
        rows: list[Any] = []
        expected: int | None = None
        failure: str | None = None
        for page in range(1, self.config.ap_max_pages + 1):
            timeout = budget.take(self.config.request_timeout_seconds)
            if timeout is None:
                failure = budget.exhausted_reason
                break
            try:
                result = self.provider.list_observation_access_points(site_id, page, self.config.ap_page_size, timeout)
            except Exception:
                failure = "provider_error"
                break
            if not isinstance(result, Result) or not result.success:
                failure = _failure_category(result)
                break
            data = result.data if isinstance(result.data, Mapping) else {}
            page_rows = data.get("access_points")
            total = data.get("total_rows")
            returned_page = data.get("page")
            if not isinstance(page_rows, list) or type(total) is not int or total < 0 or type(returned_page) is not int or returned_page != page or (expected is not None and total != expected):
                failure = "malformed_response"
                break
            expected = total
            remaining = self.config.ap_max_rows - len(rows)
            if remaining <= 0 or len(page_rows) > remaining:
                rows.extend(page_rows[:max(0, remaining)])
                failure = "row_limit"
                break
            rows.extend(page_rows)
            if len(rows) == total:
                break
            if len(rows) > total or not page_rows or len(page_rows) < self.config.ap_page_size:
                failure = "inconsistent_total"
                break
            if total > self.config.ap_max_rows:
                failure = "row_limit"
                break
        else:
            failure = "page_limit"
        complete = failure is None and expected is not None and len(rows) == expected
        if complete:
            macs = [mac for row in rows if (mac := canonical_ap_mac(row)) is not None]
            counts = {mac: macs.count(mac) for mac in set(macs)}
            duplicates = {mac for mac, count in counts.items() if count > 1}
            invalid_ap_rows = sum(
                1
                for row in rows
                if not isinstance(row, Mapping)
                or (row.get("type") == "ap" and canonical_ap_mac(row) is None)
            )
            canonical = tuple(sorted(mac for mac in macs if mac not in duplicates))
            warnings = len(duplicates) + invalid_ap_rows
            cache = _CachedInventory(canonical, expected, now, warnings, len(duplicates))
            self._inventory_cache[site_id] = cache
            return _InventoryResult(
                canonical,
                expected,
                True,
                warnings,
                0,
                None,
                cache_age_seconds=0.0,
                duplicate_ap_mac_count=len(duplicates),
            )
        if cached is not None:
            age = now - cached.captured_monotonic
            if age <= self.config.ap_inventory_max_stale_seconds:
                return _InventoryResult(
                    cached.ap_macs,
                    cached.source_rows,
                    False,
                    cached.quality_warnings + 1,
                    1,
                    failure,
                    True,
                    max(0.0, age),
                    cached.duplicate_ap_mac_count,
                )
            failure = "inventory_stale_expired"
        return _InventoryResult((), expected, False, 1, 1, failure or "inventory_failed")

    def _call(self, site_id: str, ap_mac: str, method_name: str, budget: _Budget, section: str) -> Any:
        timeout = budget.take(self.config.request_timeout_seconds)
        if timeout is None:
            return _CALL_FAILED
        try:
            result = getattr(self.provider, method_name)(site_id, ap_mac, timeout)
        except Exception:
            self._endpoint_failed(site_id, ap_mac, section, "provider_error")
            return _CALL_FAILED
        if not isinstance(result, Result) or not result.success or not isinstance(result.data, Mapping) or "result" not in result.data:
            self._endpoint_failed(site_id, ap_mac, section, _failure_category(result))
            return _CALL_FAILED
        return result.data.get("result")

    def _apply_ap_rates(self, row: dict[str, Any], site_id: str, ap_mac: str) -> int:
        errors = 0
        for timestamp, counter, rate, reason, direction, source in (
            ("wired_observed_at", "wired_down_bytes", "wired_download_mbps", "wired_download_rate_reason", "download", "wired"),
            ("wired_observed_at", "wired_up_bytes", "wired_upload_mbps", "wired_upload_rate_reason", "upload", "wired"),
            ("lan_observed_at", "lan_rx_bytes", "lan_rx_mbps", "lan_rx_rate_reason", "rx", "lan"),
            ("lan_observed_at", "lan_tx_bytes", "lan_tx_mbps", "lan_tx_rate_reason", "tx", "lan"),
        ):
            current_time = row.get(timestamp)
            current_value = row.get(counter)
            baseline = None
            if current_time is not None and type(current_value) is int:
                try:
                    baseline = self.repository.get_latest_ap_rate_sample(site_id=site_id, ap_mac=ap_mac, timestamp_column=timestamp, counter_column=counter)
                except Exception as exc:
                    self.last_error = exc
                    errors += 1
                    self.telemetry.emit("observation.storage_error", "error", site_id=site_id, ap_mac=ap_mac, failure_category="storage_error")
            value, why = _rate(current_time, current_value, baseline, self.config.rate_max_gap_seconds)
            row[rate] = value
            row[reason] = why
            if why == "counter_reset":
                self.telemetry.emit("observation.ap_rate_reset", "warning", site_id=site_id, ap_mac=ap_mac, source=source, direction=direction)
        return errors

    def _apply_radio_rates(self, row: dict[str, Any], site_id: str, ap_mac: str) -> int:
        errors = 0
        for counter, rate, reason, direction in (
            ("rx_bytes", "radio_rx_mbps", "radio_rx_rate_reason", "rx"),
            ("tx_bytes", "radio_tx_mbps", "radio_tx_rate_reason", "tx"),
        ):
            current_value = row.get(counter)
            baseline = None
            if type(current_value) is int:
                try:
                    baseline = self.repository.get_latest_radio_rate_sample(site_id=site_id, ap_mac=ap_mac, band=row["band"], counter_column=counter)
                except Exception as exc:
                    self.last_error = exc
                    errors += 1
                    self.telemetry.emit("observation.storage_error", "error", site_id=site_id, ap_mac=ap_mac, band=row["band"], failure_category="storage_error")
            value, why = _rate(row.get("radio_observed_at"), current_value, baseline, self.config.rate_max_gap_seconds)
            row[rate] = value
            row[reason] = why
            if why == "counter_reset":
                self.telemetry.emit("observation.ap_rate_reset", "warning", site_id=site_id, ap_mac=ap_mac, source="radio", direction=direction, band=row["band"])
        return errors

    def _ordered(self, site_id: str, kind: str, macs: tuple[str, ...]) -> tuple[str, ...]:
        if not macs:
            return ()
        start = self._cursor.get((site_id, kind), 0) % len(macs)
        return macs[start:] + macs[:start]

    def _advance_cursor(self, site_id: str, kind: str, total: int, attempted: int) -> None:
        if total:
            key = (site_id, kind)
            self._cursor[key] = (self._cursor.get(key, 0) + max(1, attempted)) % total

    def _endpoint_failed(self, site_id: str, ap_mac: str, section: str, category: str) -> None:
        self.telemetry.emit("observation.ap_endpoint_failed", "warning", site_id=site_id, ap_mac=ap_mac, section=section, failure_category=category)

    def _dynamic_result(self, inventory, ordered, entries, inserted, budget):
        if self._stop_event.is_set():
            return "shutdown", False, "shutdown"
        if not ordered and inventory.complete and not inventory.stale_cache_used and inventory.quality_warnings == 0:
            return "success", True, None
        if not ordered:
            return "failed", False, inventory.failure_category or "no_valid_access_points"
        if ordered and (not entries or inserted == 0):
            return "failed", False, budget.exhausted_reason or inventory.failure_category or "no_ap_observations"
        if inventory.error_count or inventory.quality_warnings or budget.exhausted_reason or inserted < len(ordered) or any(row[0]["partial"] for row in entries):
            return "partial", False, budget.exhausted_reason or inventory.failure_category
        return "success", True, None

    def _config_result(self, inventory, ordered, complete_aps, budget, errors):
        if self._stop_event.is_set():
            return "shutdown", False, "shutdown"
        if not ordered and inventory.complete and not inventory.stale_cache_used and inventory.quality_warnings == 0:
            return "success", True, None
        if not ordered:
            return "failed", False, inventory.failure_category or "no_valid_access_points"
        if ordered and complete_aps == 0:
            return "failed", False, budget.exhausted_reason or inventory.failure_category or "no_complete_config"
        if errors or inventory.error_count or inventory.quality_warnings or budget.exhausted_reason or complete_aps < len(ordered):
            return "partial", False, budget.exhausted_reason or inventory.failure_category
        return "success", True, None

    def _finalize(self, cycle, *, kind, result, complete, source_rows, items_seen, items_stored, errors, warnings, request_count, failure, extra, started):
        items_skipped = max(0, items_seen - items_stored)
        try:
            self.repository.finalize_cycle(
                cycle.cycle_id,
                finished_at=self._now_factory(),
                complete=complete,
                result=result,
                source_rows_reported=source_rows,
                items_seen=items_seen,
                items_stored=items_stored,
                items_skipped=items_skipped,
                error_count=errors,
                data_quality_warning_count=warnings,
            )
        except Exception as exc:
            self.last_error = exc
            result, complete, failure = "failed", False, "storage_error"
            self.telemetry.emit("observation.storage_error", "error", site_id=cycle.site_id, cycle_id=cycle.cycle_id, failure_category="storage_error")
        duration_ms = max(0, int((self._monotonic() - started) * 1000))
        event = "observation.ap_cycle_completed" if result == "success" else "observation.ap_cycle_failed"
        self.telemetry.emit(event, "info" if result == "success" else "warning", site_id=cycle.site_id, cycle_id=cycle.cycle_id, kind=kind, result=result, complete=complete, duration_ms=duration_ms, items_seen=items_seen, items_stored=items_stored, items_skipped=items_skipped, error_count=errors, request_count=request_count, failure_category=failure, **extra)
        return APCycleOutcome(cycle.site_id, kind, cycle.cycle_id, result, complete, items_seen, items_stored, items_skipped, errors, request_count, failure)

    @staticmethod
    def _failed_without_cycle(site_id: str, kind: str) -> APCycleOutcome:
        return APCycleOutcome(site_id, kind, None, "failed", False, 0, 0, 0, 1, 0, "storage_error")


def _failure_category(result: Any) -> str:
    if isinstance(result, Result) and isinstance(result.data, Mapping):
        value = result.data.get("failure_category")
        if isinstance(value, str) and value:
            return value
    return "malformed_response" if isinstance(result, Result) else "provider_error"


def _rate(current_time: Any, current_value: Any, baseline: tuple[str, int] | None, max_gap: float) -> tuple[float | None, str]:
    if current_time is None or type(current_value) is not int:
        return None, "source_unavailable"
    if baseline is None:
        return None, "no_baseline"
    previous_time, previous_value = baseline
    try:
        elapsed = (parse_utc(current_time) - parse_utc(previous_time)).total_seconds()
    except Exception:
        return None, "invalid_elapsed"
    if elapsed <= 0:
        return None, "invalid_elapsed"
    if elapsed > max_gap:
        return None, "gap_too_large"
    if current_value < previous_value:
        return None, "counter_reset"
    return (current_value - previous_value) * 8.0 / elapsed / 1_000_000.0, "ok"
