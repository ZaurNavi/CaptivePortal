"""Read-only Projection product-health observation and bounded telemetry."""

from __future__ import annotations

import threading
import time
from typing import Any, Mapping

from .telemetry import TrafficProjectionTelemetry


OBSERVE_INTERVAL_SECONDS = 5.0
HEARTBEAT_INTERVAL_SECONDS = 55.0
RECONCILE_STUCK_SECONDS = 60.0


class TrafficProjectionHealthObserver:
    def __init__(
        self,
        root_service,
        *,
        telemetry: TrafficProjectionTelemetry,
        monotonic=time.monotonic,
    ):
        self.root_service = root_service
        self.telemetry = telemetry
        self._monotonic = monotonic
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.known_owned_keys: set[tuple[str, str]] = set()
        self._previous_status: dict[tuple[str, str], str] = {}
        self._previous_source_available: dict[tuple[str, str], bool] = {}
        self._previous_storage_available: dict[tuple[str, str], bool] = {}
        self._last_heartbeat: dict[tuple[str, str], float] = {}
        self._reconcile_progress: dict[
            tuple[str, str], tuple[tuple[Any, Any], float, bool]
        ] = {}

    def start(self, initial_services) -> None:
        services = tuple(initial_services)
        keys = {
            (service.projection_version, site_id)
            for service in services
            for site_id in service.config.site_ids
        }
        with self._lock:
            self.known_owned_keys = keys
        for service in services:
            for site_id in service.config.site_ids:
                self.observe_service_site(
                    service,
                    site_id,
                    startup=True,
                    force_heartbeat=True,
                )
        thread = threading.Thread(
            target=self._run,
            name="traffic-projection-health",
            daemon=True,
        )
        self._thread = thread
        thread.start()

    def request_stop(self) -> None:
        self._stop.set()

    def stop(self, timeout_seconds: float) -> bool:
        self.request_stop()
        thread = self._thread
        if thread is None:
            return True
        thread.join(timeout=max(float(timeout_seconds), 0.0))
        return not thread.is_alive()

    def observe_service_site(
        self,
        service,
        site_id: str,
        *,
        startup: bool = False,
        force_heartbeat: bool = False,
        source_unavailable_event_already_emitted: bool = False,
    ) -> None:
        del startup
        with self._lock:
            self._observe_service_site_locked(
                service,
                site_id,
                force_heartbeat=force_heartbeat,
                source_unavailable_event_already_emitted=(
                    source_unavailable_event_already_emitted
                ),
            )

    def _run(self) -> None:
        while not self._stop.wait(OBSERVE_INTERVAL_SECONDS):
            self._observe_once()

    def _observe_once(self) -> None:
        try:
            services = tuple(self.root_service._health_worker_services())
            keys = {
                (service.projection_version, site_id)
                for service in services
                for site_id in service.config.site_ids
            }
            with self._lock:
                self.known_owned_keys = keys
        except Exception:
            with self._lock:
                keys = set(self.known_owned_keys)
                if not keys:
                    keys = {
                        (self.root_service.projection_version, site_id)
                        for site_id in self.root_service.config.site_ids
                    }
                for key in sorted(keys):
                    self._observe_failure_locked(key)
            return
        for service in services:
            for site_id in service.config.site_ids:
                try:
                    self.observe_service_site(service, site_id)
                except Exception:
                    with self._lock:
                        self._observe_failure_locked(
                            (service.projection_version, site_id)
                        )

    def _observe_service_site_locked(
        self,
        service,
        site_id: str,
        *,
        force_heartbeat: bool,
        source_unavailable_event_already_emitted: bool,
    ) -> None:
        key = (service.projection_version, site_id)
        try:
            observation = service.health_observation(site_id)
            health = observation["health"]
            site_state = observation["site_state"]
            source_available = observation["source_available"]
            if (
                not isinstance(health, Mapping)
                or site_state is not None and not isinstance(site_state, Mapping)
                or type(source_available) is not bool
                or not isinstance(health.get("status"), str)
            ):
                raise ValueError
        except Exception:
            self._observe_failure_locked(key)
            return

        now = self._monotonic()
        status = str(health["status"])
        first_observation = key not in self._previous_status
        previous_status = self._previous_status.get(key)
        previous_source = self._previous_source_available.get(key)
        storage_recovered = self._previous_storage_available.get(key) is False
        status_changed = not first_observation and status != previous_status
        source_availability_changed = (
            previous_source is not None and previous_source != source_available
        )
        heartbeat_due = (
            key not in self._last_heartbeat
            or now - self._last_heartbeat[key] >= HEARTBEAT_INTERVAL_SECONDS
        )
        should_emit_source_unavailable = (
            source_available is False
            and previous_source is not False
            and source_unavailable_event_already_emitted is False
        )
        if should_emit_source_unavailable:
            self.telemetry.emit(
                "traffic_projection_worker_source_unavailable",
                projection_version=key[0],
                site_id=key[1],
                error_category="source_unavailable",
            )

        emit_product_health = (
            first_observation
            or force_heartbeat
            or status_changed
            or storage_recovered
            or source_availability_changed
            or heartbeat_due
        )
        fields = _product_health_fields(key, health, site_state)
        if emit_product_health:
            self.telemetry.emit("traffic_projection_product_health", **fields)
            self._last_heartbeat[key] = now
        if status_changed and status == "diverged":
            self.telemetry.emit(
                "traffic_projection_site_diverged",
                projection_version=key[0],
                site_id=key[1],
                status="diverged",
                error_category=fields["error_category"],
                projection_revision=fields["projection_revision"],
            )
        if status_changed and status == "stale":
            self.telemetry.emit(
                "traffic_projection_stale",
                projection_version=key[0],
                site_id=key[1],
                status="stale",
                build_state=fields["build_state"],
                projection_revision=fields["projection_revision"],
                source_head_utc=fields["source_head_utc"],
                projection_head_utc=fields["projection_head_utc"],
                head_lag_seconds=fields["head_lag_seconds"],
                last_incremental_progress_at=fields[
                    "last_incremental_progress_at"
                ],
                last_full_reconcile_completed_at=fields[
                    "last_full_reconcile_completed_at"
                ],
                error_category=fields["error_category"],
            )

        self._previous_status[key] = status
        self._previous_source_available[key] = source_available
        self._previous_storage_available[key] = True
        self._observe_reconcile_progress_locked(key, fields, now)

    def _observe_failure_locked(self, key: tuple[str, str]) -> None:
        now = self._monotonic()
        previous_storage = self._previous_storage_available.get(key)
        heartbeat_due = (
            key not in self._last_heartbeat
            or now - self._last_heartbeat[key] >= HEARTBEAT_INTERVAL_SECONDS
        )
        if previous_storage is not False:
            self.telemetry.emit(
                "traffic_projection_worker_storage_unavailable",
                projection_version=key[0],
                site_id=key[1],
                error_category="health_state_unavailable",
            )
        if previous_storage is not False or heartbeat_due:
            self.telemetry.emit(
                "traffic_projection_product_health",
                **_unavailable_product_health_fields(key),
            )
            self._last_heartbeat[key] = now
        self._previous_storage_available[key] = False
        self._previous_status[key] = "unavailable"

    def _observe_reconcile_progress_locked(
        self,
        key: tuple[str, str],
        fields: Mapping[str, Any],
        now: float,
    ) -> None:
        if fields["reconcile_sweep_started_at"] is None:
            self._reconcile_progress.pop(key, None)
            return
        identity = (
            fields["reconcile_cursor_started_at"],
            fields["reconcile_cursor_cycle_id"],
        )
        prior = self._reconcile_progress.get(key)
        if prior is None or identity != prior[0]:
            self._reconcile_progress[key] = (identity, now, False)
            return
        _prior_identity, changed_at, stuck_emitted = prior
        if now - changed_at >= RECONCILE_STUCK_SECONDS and not stuck_emitted:
            self.telemetry.emit(
                "traffic_projection_reconcile_stuck",
                projection_version=key[0],
                site_id=key[1],
                status=fields["status"],
                reconcile_sweep_started_at=fields[
                    "reconcile_sweep_started_at"
                ],
                reconcile_sweep_from_utc=fields["reconcile_sweep_from_utc"],
                reconcile_cursor_started_at=fields[
                    "reconcile_cursor_started_at"
                ],
                reconcile_cursor_cycle_id=fields[
                    "reconcile_cursor_cycle_id"
                ],
                error_category="reconcile_stuck",
            )
            self._reconcile_progress[key] = (identity, changed_at, True)


def _product_health_fields(
    key: tuple[str, str],
    health: Mapping[str, Any],
    site_state: Mapping[str, Any] | None,
) -> dict[str, Any]:
    state = site_state or {}
    return {
        "projection_version": key[0],
        "site_id": key[1],
        "status": health.get("status"),
        "build_state": health.get("build_state"),
        "projection_revision": health.get("projection_revision"),
        "source_head_utc": health.get("source_head_utc"),
        "projection_head_utc": health.get("projection_head_utc"),
        "head_lag_seconds": health.get("head_lag_seconds"),
        "last_incremental_progress_at": health.get(
            "last_incremental_progress_at"
        ),
        "reconcile_sweep_started_at": health.get(
            "reconcile_sweep_started_at"
        ),
        "reconcile_sweep_from_utc": state.get("reconcile_sweep_from_utc"),
        "reconcile_sweep_source_head_utc": state.get(
            "reconcile_sweep_source_head_utc"
        ),
        "reconcile_cursor_started_at": state.get(
            "reconcile_cursor_started_at"
        ),
        "reconcile_cursor_cycle_id": state.get("reconcile_cursor_cycle_id"),
        "last_full_reconcile_completed_at": health.get(
            "last_full_reconcile_completed_at"
        ),
        "backlog_cycle_count": health.get("backlog_cycle_count"),
        "error_category": state.get("last_error_category"),
    }


def _unavailable_product_health_fields(
    key: tuple[str, str],
) -> dict[str, Any]:
    fields = {
        name: None
        for name in (
            "build_state",
            "projection_revision",
            "source_head_utc",
            "projection_head_utc",
            "head_lag_seconds",
            "last_incremental_progress_at",
            "reconcile_sweep_started_at",
            "reconcile_sweep_from_utc",
            "reconcile_sweep_source_head_utc",
            "reconcile_cursor_started_at",
            "reconcile_cursor_cycle_id",
            "last_full_reconcile_completed_at",
            "backlog_cycle_count",
        )
    }
    return {
        "projection_version": key[0],
        "site_id": key[1],
        "status": "unavailable",
        **fields,
        "error_category": "health_state_unavailable",
    }
