"""Fail-open operational telemetry for the canonical Home AP-24H read model."""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass
from typing import Any, Mapping

from app.analytics.home_ap_24h import (
    MAX_PAGE_SIZE,
    HomeAp24SourceUnavailable,
    HomeAp24ValidationError,
)
from app.analytics.source_gateway import AnalyticsQueryDeadlineExceeded

from .home_ap_24h_serialization import (
    HomeAp24SerializationError,
    serialize_home_ap_24h,
)
from .query_service import AdminQueryBusy, AdminQueryDeadline


COMPONENT = "home_ap_24h_telemetry"
DEFAULT_INITIAL_DELAY_SECONDS = 15
DEFAULT_INTERVAL_SECONDS = 120
MIN_INITIAL_DELAY_SECONDS = 0
MAX_INITIAL_DELAY_SECONDS = 3600
MIN_INTERVAL_SECONDS = 60
MAX_INTERVAL_SECONDS = 3600


class HomeAp24TelemetryConfigError(ValueError):
    """Enabled AP-24H telemetry configuration is invalid."""


@dataclass(frozen=True, slots=True)
class HomeAp24TelemetryConfig:
    enabled: bool
    initial_delay_seconds: int
    interval_seconds: int


def home_ap_24h_telemetry_config_from_settings(
    settings: Mapping[str, Any],
) -> HomeAp24TelemetryConfig:
    """Parse bounded settings while preserving disabled rollback safety."""
    enabled = _bool(
        settings.get("web_admin_home_ap_24h_telemetry_enabled", "false")
    )
    if not enabled:
        return HomeAp24TelemetryConfig(
            enabled=False,
            initial_delay_seconds=DEFAULT_INITIAL_DELAY_SECONDS,
            interval_seconds=DEFAULT_INTERVAL_SECONDS,
        )
    return HomeAp24TelemetryConfig(
        enabled=True,
        initial_delay_seconds=_integer(
            settings.get(
                "web_admin_home_ap_24h_telemetry_initial_delay_seconds",
                str(DEFAULT_INITIAL_DELAY_SECONDS),
            ),
            MIN_INITIAL_DELAY_SECONDS,
            MAX_INITIAL_DELAY_SECONDS,
        ),
        interval_seconds=_integer(
            settings.get(
                "web_admin_home_ap_24h_telemetry_interval_seconds",
                str(DEFAULT_INTERVAL_SECONDS),
            ),
            MIN_INTERVAL_SECONDS,
            MAX_INTERVAL_SECONDS,
        ),
    )


def create_home_ap_24h_telemetry_worker(
    settings: Mapping[str, Any],
    *,
    admin_runtime: Any,
    telemetry: Any,
    logger: logging.Logger,
) -> "HomeAp24TelemetryWorker | None":
    """Fail closed for telemetry without affecting the composed Admin runtime."""
    try:
        config = home_ap_24h_telemetry_config_from_settings(settings)
    except HomeAp24TelemetryConfigError:
        logger.error(
            "admin.home_ap_24h_telemetry_configuration_failed",
            extra={
                "event": "admin.home_ap_24h_telemetry_configuration_failed",
                "failure_category": "configuration_error",
            },
        )
        return None
    if not config.enabled:
        return None
    if (
        admin_runtime is None
        or getattr(admin_runtime, "state", None) != "active"
        or getattr(admin_runtime, "home_ap_24h_state", None) != "active"
        or getattr(admin_runtime, "home_ap_24h_service", None) is None
        or getattr(admin_runtime, "query_execution_controls", None) is None
        or not _telemetry_available(telemetry)
    ):
        logger.error(
            "admin.home_ap_24h_telemetry_composition_failed",
            extra={
                "event": "admin.home_ap_24h_telemetry_composition_failed",
                "failure_category": "prerequisite_unavailable",
            },
        )
        return None
    admin_config = getattr(admin_runtime, "config", None)
    site_ids = tuple(sorted(getattr(admin_config, "allowed_site_ids", ())))
    if not site_ids:
        logger.error(
            "admin.home_ap_24h_telemetry_composition_failed",
            extra={
                "event": "admin.home_ap_24h_telemetry_composition_failed",
                "failure_category": "prerequisite_unavailable",
            },
        )
        return None
    return HomeAp24TelemetryWorker(
        config=config,
        site_ids=site_ids,
        read_service=admin_runtime.home_ap_24h_service,
        execution_controls=admin_runtime.query_execution_controls,
        telemetry=telemetry,
        logger=logger,
    )


class HomeAp24TelemetryWorker:
    """One process-local fixed-delay publisher over the shared read boundary."""

    def __init__(
        self,
        *,
        config: HomeAp24TelemetryConfig,
        site_ids: tuple[str, ...],
        read_service: Any,
        execution_controls: Any,
        telemetry: Any,
        logger: logging.Logger,
    ):
        self.config = config
        self._site_ids = tuple(site_ids)
        self._read_service = read_service
        self._execution_controls = execution_controls
        self._telemetry = telemetry
        self._logger = logger
        self._shutdown_timeout_seconds = (
            float(execution_controls.max_query_duration_seconds) + 1.0
        )
        self._stop_event = threading.Event()
        self._state_lock = threading.Lock()
        self._cycle_lock = threading.Lock()
        self._emit_error_reported = False
        self._thread: threading.Thread | None = None

    def start(self) -> bool:
        """Start once; repeated starts while running are no-ops."""
        if not self.config.enabled:
            return False
        with self._state_lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self._stop_event.clear()
            thread = threading.Thread(
                target=self._run,
                name="home-ap-24h-telemetry",
                daemon=True,
            )
            self._thread = thread
            self._emit(
                "home_ap_24h.telemetry_started",
                interval_seconds=self.config.interval_seconds,
                initial_delay_seconds=self.config.initial_delay_seconds,
                site_count=len(self._site_ids),
            )
            thread.start()
        return True

    def stop(self, timeout_seconds: float | None = None) -> bool:
        """Wake delay waits and join without blocking shutdown indefinitely."""
        self._stop_event.set()
        with self._state_lock:
            thread = self._thread
        if thread is None:
            return True
        timeout = (
            self._shutdown_timeout_seconds
            if timeout_seconds is None
            else max(0.0, float(timeout_seconds))
        )
        thread.join(timeout)
        stopped = not thread.is_alive()
        if stopped:
            with self._state_lock:
                if self._thread is thread:
                    self._thread = None
        return stopped

    def run_once(self) -> bool:
        """Evaluate all configured Sites without allowing overlapping cycles."""
        if not self._cycle_lock.acquire(blocking=False):
            return False
        try:
            for site_id in self._site_ids:
                if self._stop_event.is_set():
                    break
                self._evaluate_site(site_id)
            return True
        finally:
            self._cycle_lock.release()

    def _run(self) -> None:
        if self._stop_event.wait(self.config.initial_delay_seconds):
            return
        while not self._stop_event.is_set():
            self.run_once()
            if self._stop_event.wait(self.config.interval_seconds):
                return

    def _evaluate_site(self, site_id: str) -> None:
        try:
            result, has_more = self._execution_controls.run(
                lambda deadline: self._read_and_serialize(site_id, deadline)
            )
            self._emit_snapshot(site_id, result, has_more=has_more)
        except AdminQueryBusy:
            self._emit_failure(site_id, "concurrency_limit")
        except (AdminQueryDeadline, AnalyticsQueryDeadlineExceeded):
            self._emit_failure(site_id, "query_deadline")
        except HomeAp24SourceUnavailable:
            self._emit_failure(site_id, "source_unavailable")
        except HomeAp24SerializationError:
            self._emit_failure(site_id, "serialization_error")
        except HomeAp24ValidationError:
            self._emit_failure(site_id, "internal_error")
        except Exception:
            self._emit_failure(site_id, "internal_error")

    def _read_and_serialize(self, site_id: str, deadline: Any):
        raw = self._read_service.get_home_ap_24h(
            site_id,
            evaluated_at_utc=None,
            after_ap_mac=None,
            limit=MAX_PAGE_SIZE,
            deadline=deadline,
        )
        page = raw.get("page") if isinstance(raw, dict) else None
        has_more = bool(page.get("has_more")) if isinstance(page, dict) else False
        return serialize_home_ap_24h(raw), has_more

    def _emit_snapshot(
        self,
        site_id: str,
        result: dict[str, Any],
        *,
        has_more: bool,
    ) -> None:
        snapshot_id = str(uuid.uuid4())
        evaluated_at = result["window"]["evaluated_at_utc"]
        detail_emitted = 0
        for item in result["items"]:
            if self._emit(
                "home_ap_24h.ap_snapshot",
                **_ap_fields(snapshot_id, site_id, evaluated_at, item),
            ):
                detail_emitted += 1
        self._emit(
            "home_ap_24h.snapshot",
            **_snapshot_fields(
                snapshot_id,
                site_id,
                result,
                detail_emitted_count=detail_emitted,
                detail_truncated=(has_more or detail_emitted != len(result["items"])),
            ),
        )

    def _emit_failure(self, site_id: str, category: str) -> None:
        self._emit(
            "home_ap_24h.snapshot_failed",
            level="warning",
            site_id=site_id,
            failure_category=category,
        )

    def _emit(self, event: str, *, level: str = "info", **fields: Any) -> bool:
        try:
            return bool(
                self._telemetry.safe_emit_system(
                    event,
                    level=level,
                    component=COMPONENT,
                    **fields,
                )
            )
        except Exception:
            if not self._emit_error_reported:
                self._emit_error_reported = True
                self._logger.error(
                    "admin.home_ap_24h_telemetry_emit_failed",
                    extra={
                        "event": "admin.home_ap_24h_telemetry_emit_failed",
                        "failure_category": "telemetry_unavailable",
                    },
                )
            return False


def _snapshot_fields(
    snapshot_id: str,
    site_id: str,
    result: dict[str, Any],
    *,
    detail_emitted_count: int,
    detail_truncated: bool,
) -> dict[str, Any]:
    summary = result["summary"]
    current = summary["current"]
    history = summary["history"]
    observation = summary["observation_quality"]
    current_source = result["sources"]["current_state"]
    observation_source = result["sources"]["observations"]
    window = result["window"]
    return {
        "snapshot_id": snapshot_id,
        "site_id": site_id,
        "contract_version": result["contract_version"],
        "evaluated_at_utc": window["evaluated_at_utc"],
        "window_from_utc": window["from_utc"],
        "window_to_utc": window["to_utc"],
        "block_status": result["block_status"],
        "block_reason": result["block_reason"],
        "ap_count_in_window": summary["ap_count_in_window"],
        "current_operational_count": current["operational"],
        "current_degraded_count": current["degraded"],
        "current_unavailable_count": current["unavailable"],
        "current_unknown_count": current["unknown"],
        "history_operational_count": history["operational"],
        "history_degraded_count": history["degraded"],
        "history_unavailable_count": history["unavailable"],
        "history_unknown_count": history["unknown"],
        "observation_operational_count": observation["operational"],
        "observation_degraded_count": observation["degraded"],
        "observation_unavailable_count": observation["unavailable"],
        "observation_unknown_count": observation["unknown"],
        "short_history_ap_count": summary["short_history_ap_count"],
        "status_gap_ap_count": summary["status_gap_ap_count"],
        "observation_problem_ap_count": summary["observation_problem_ap_count"],
        "current_state_status": current_source["status"],
        "current_state_complete_cycle_count": current_source["complete_cycle_count"],
        "current_state_partial_cycle_count": current_source["partial_cycle_count"],
        "current_state_failed_cycle_count": current_source["failed_cycle_count"],
        "current_state_max_gap_seconds": current_source["max_gap_seconds"],
        "observations_status": observation_source["status"],
        "observations_complete_cycle_count": observation_source["complete_cycle_count"],
        "observations_partial_cycle_count": observation_source["partial_cycle_count"],
        "observations_failed_cycle_count": observation_source["failed_cycle_count"],
        "observations_max_gap_seconds": observation_source["max_gap_seconds"],
        "detail_emitted_count": detail_emitted_count,
        "detail_truncated": detail_truncated,
    }


def _ap_fields(
    snapshot_id: str,
    site_id: str,
    evaluated_at: str,
    item: dict[str, Any],
) -> dict[str, Any]:
    current = item["current"]
    history = item["history"]
    observation = item["observation_quality"]
    sections = observation["section_problem_counts"]
    return {
        "snapshot_id": snapshot_id,
        "site_id": site_id,
        "evaluated_at_utc": evaluated_at,
        "ap_mac": item["ap_mac"],
        "ap_name": item.get("name"),
        "model": item.get("model"),
        "current_status": current["status"],
        "current_reason_code": current["reason_code"],
        "current_freshness_status": current["freshness_status"],
        "history_status": history["status"],
        "history_reason_code": history["reason_code"],
        "coverage_status": history["coverage_status"],
        "authoritative_sample_count": history["authoritative_sample_count"],
        "operational_seconds": history["operational_seconds"],
        "unavailable_seconds": history["unavailable_seconds"],
        "unknown_evidence_seconds": history["unknown_evidence_seconds"],
        "short_history_seconds": history["short_history_seconds"],
        "max_gap_seconds": history["max_gap_seconds"],
        "observation_status": observation["status"],
        "observation_reason_code": observation["reason_code"],
        "complete_sample_count": observation["complete_sample_count"],
        "diagnostic_partial_sample_count": observation[
            "diagnostic_partial_sample_count"
        ],
        "overview_problem_count": sections["overview"],
        "wired_uplink_problem_count": sections["wired_uplink"],
        "lan_traffic_problem_count": sections["lan_traffic"],
        "radios_problem_count": sections["radios"],
    }


def _telemetry_available(telemetry: Any) -> bool:
    return (
        telemetry is not None
        and getattr(telemetry, "enabled", False) is True
        and getattr(telemetry, "available", False) is True
        and callable(getattr(telemetry, "safe_emit_system", None))
    )


def _bool(value: object) -> bool:
    if value in (True, "true"):
        return True
    if value in (False, "false"):
        return False
    raise HomeAp24TelemetryConfigError(
        "AP-24H telemetry enabled must be exactly true or false"
    )


def _integer(value: object, minimum: int, maximum: int) -> int:
    try:
        selected = int(value)
    except (TypeError, ValueError) as exc:
        raise HomeAp24TelemetryConfigError(
            "AP-24H telemetry setting must be an integer"
        ) from exc
    if isinstance(value, bool) or not minimum <= selected <= maximum:
        raise HomeAp24TelemetryConfigError(
            "AP-24H telemetry setting is outside bounds"
        )
    return selected
