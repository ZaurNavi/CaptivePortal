"""Product-safe, read-only Home System Health evaluation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from app.analytics.source_gateway import (
    AnalyticsQueryDeadlineExceeded,
    QueryDeadline,
)
from app.auth.health import (
    OUTCOME_BLOCKING_FAILURE,
    OUTCOME_RETRYABLE_FAILURE,
    OUTCOME_VERIFIED_SUCCESS,
)


STATUSES = frozenset({"operational", "degraded", "unavailable", "unknown"})
_COMPONENTS = (
    ("guest_access", "Guest Access", "critical", "site"),
    ("live_network_state", "Live Network State", "feature", "site"),
    ("network_history", "Network History Collection", "feature", "site"),
    ("visit_tracking", "Visit Tracking", "feature", "global"),
    ("analytics_home_data", "Analytics & Home Data", "feature", "global"),
)
_MESSAGES = {
    "latest_authorization_verified": "Guest authorization is operating normally.",
    "no_authorization_evidence": "There is not enough current authorization evidence to confirm status.",
    "authorization_evidence_old": "Authorization evidence is too old to confirm current status.",
    "invalid_authorization_evidence_time": "Authorization evidence time cannot be trusted.",
    "authorization_transient_failure": "Guest authorization recently encountered a temporary system failure.",
    "authorization_unavailable": "Guest authorization is currently unavailable.",
    "current_state_operational": "Current client and access-point state is available.",
    "current_state_stale": "Current network state is delayed; last complete data remains available.",
    "current_state_unavailable": "Current network state is unavailable.",
    "latest_collection_incomplete": "The latest collection did not complete; last complete data remains available.",
    "observation_operational": "Network history collection is operating normally.",
    "stale_evidence": "Data collection is delayed; last known data remains available.",
    "observation_unavailable": "Network history collection is unavailable.",
    "initializing": "There is not enough current evidence to confirm status.",
    "visit_operational": "Visit tracking is operating normally.",
    "visit_runtime_degraded": "Visit tracking is operating with reduced availability.",
    "visit_runtime_unavailable": "Visit tracking is currently unavailable.",
    "analytics_operational": "Analytics and Home data sources are available.",
    "analytics_source_unavailable": "Analytics source data is currently unavailable.",
    "current_traffic_service_unavailable": "Current Traffic data is currently unavailable.",
    "home_activity_service_unavailable": "Home Activity data is currently unavailable.",
    "component_disabled": "This required function is disabled.",
    "health_read_failed": "There is not enough current evidence to confirm status.",
}
_AGGREGATE_MESSAGES = {
    "operational": "All CaptivPortal functions are operating normally.",
    "degraded": "Some CaptivPortal functions are degraded.",
    "unavailable": "Guest access is currently unavailable.",
    "unknown": "There is not enough current evidence to confirm system status.",
}


class HomeHealthError(RuntimeError):
    pass


class HomeHealthValidationError(HomeHealthError):
    pass


@dataclass(frozen=True, slots=True)
class HomeHealthComponent:
    id: str
    label: str
    status: str
    reason_code: str
    message: str
    criticality: str
    scope_type: str
    site_id: str | None
    evidence_at: datetime | None
    last_success_at: datetime | None


@dataclass(frozen=True, slots=True)
class HomeHealthResult:
    health_version: int
    site_id: str
    evaluated_at: datetime
    status: str
    message: str
    components: tuple[HomeHealthComponent, ...]


class HomeHealthReadService:
    """Evaluate five fixed components without active network acquisition."""

    def __init__(
        self,
        *,
        allowed_site_ids: frozenset[str],
        auth_tracker: Any,
        current_state_runtime: Any,
        observation_runtime: Any,
        visit_runtime: Any,
        analytics_runtime: Any,
        auth_evidence_max_age_seconds: int,
        home_traffic_enabled: bool,
        home_activity_enabled: bool,
        logger: logging.Logger | None = None,
        now_factory: Callable[[], datetime] | None = None,
    ):
        self._sites = allowed_site_ids
        self._auth_tracker = auth_tracker
        self._current_state = current_state_runtime
        self._observations = observation_runtime
        self._visits = visit_runtime
        self._analytics = analytics_runtime
        self._auth_max_age = auth_evidence_max_age_seconds
        self._traffic_expected = home_traffic_enabled
        self._activity_expected = home_activity_enabled
        self._logger = logger or logging.getLogger("admin.home_health")
        self._now_factory = now_factory or (lambda: datetime.now(timezone.utc))

    def evaluate(
        self,
        site_id: str,
        *,
        deadline: QueryDeadline,
        evaluated_at: datetime | None = None,
    ) -> HomeHealthResult:
        if site_id not in self._sites:
            raise HomeHealthValidationError("Site is not allowed")
        now = _utc(evaluated_at or self._now_factory())
        evaluators = (
            self._guest_access,
            self._live_network_state,
            self._network_history,
            self._visit_tracking,
            self._analytics_home_data,
        )
        components = []
        for index, evaluator in enumerate(evaluators):
            deadline.require_remaining()
            try:
                value = evaluator(site_id, now, deadline)
            except AnalyticsQueryDeadlineExceeded:
                raise
            except Exception:
                identity = _COMPONENTS[index]
                self._logger.warning(
                    "admin.home_health_component_read_failed",
                    extra={
                        "event": "admin.home_health_component_read_failed",
                        "component_id": identity[0],
                        "failure_category": "source_read_error",
                    },
                )
                value = _component(
                    identity, site_id, "unknown", "health_read_failed"
                )
            components.append(value)
            deadline.require_remaining()
        result = tuple(components)
        status = _aggregate(result)
        return HomeHealthResult(
            1,
            site_id,
            now,
            status,
            _AGGREGATE_MESSAGES[status],
            result,
        )

    def _guest_access(
        self, site_id: str, now: datetime, deadline: QueryDeadline
    ) -> HomeHealthComponent:
        identity = _COMPONENTS[0]
        snapshot = self._auth_tracker.snapshot(site_id)
        if snapshot is None or snapshot.outcome is None:
            return _component(identity, site_id, "unknown", "no_authorization_evidence")
        observed = _utc_or_none(snapshot.observed_at)
        last_success = _utc_or_none(snapshot.last_success_at)
        if observed is None or observed > now:
            return _component(
                identity,
                site_id,
                "unknown",
                "invalid_authorization_evidence_time",
                evidence_at=observed,
                last_success_at=last_success,
            )
        if (now - observed).total_seconds() > self._auth_max_age:
            return _component(
                identity,
                site_id,
                "unknown",
                "authorization_evidence_old",
                evidence_at=observed,
                last_success_at=last_success,
            )
        if snapshot.outcome == OUTCOME_VERIFIED_SUCCESS:
            status, reason = "operational", "latest_authorization_verified"
        elif snapshot.outcome == OUTCOME_RETRYABLE_FAILURE:
            status, reason = "degraded", "authorization_transient_failure"
        elif snapshot.outcome == OUTCOME_BLOCKING_FAILURE:
            status, reason = "unavailable", "authorization_unavailable"
        else:
            status, reason = "unknown", "health_read_failed"
        return _component(
            identity,
            site_id,
            status,
            reason,
            evidence_at=observed,
            last_success_at=last_success,
        )

    def _live_network_state(
        self, site_id: str, now: datetime, deadline: QueryDeadline
    ) -> HomeHealthComponent:
        identity = _COMPONENTS[1]
        runtime = self._current_state
        state = getattr(runtime, "state", None)
        if state == "disabled":
            return _component(identity, site_id, "unavailable", "component_disabled")
        if state == "unavailable" or runtime is None:
            return _component(identity, site_id, "unavailable", "current_state_unavailable")
        if state in {"starting", "stopping", None}:
            return _component(identity, site_id, "unknown", "initializing")
        source = getattr(runtime, "read_service", None)
        if source is None:
            return _component(identity, site_id, "unavailable", "current_state_unavailable")
        deadline.require_remaining()
        client = source.get_current_client_summary(site_id, evaluated_at_utc=now)
        deadline.require_remaining()
        ap = source.get_current_ap_summary(site_id, evaluated_at_utc=now)
        deadline.require_remaining()
        metas = (client.snapshot, ap.snapshot)
        evidence = _minimum_timestamp(tuple(meta.observed_at for meta in metas))
        success = _minimum_timestamp(tuple(meta.capture_finished_at for meta in metas))
        freshness = tuple(meta.freshness_status for meta in metas)
        if "unavailable" in freshness:
            return _component(
                identity, site_id, "unavailable", "current_state_unavailable",
                evidence_at=evidence, last_success_at=success,
            )
        incomplete = any(
            meta.latest_attempt_result not in {None, "success"} for meta in metas
        )
        if incomplete:
            status, reason = "degraded", "latest_collection_incomplete"
        elif state == "degraded" or "stale" in freshness:
            status, reason = "degraded", "current_state_stale"
        elif state == "active" and freshness == ("fresh", "fresh"):
            status, reason = "operational", "current_state_operational"
        else:
            status, reason = "unknown", "initializing"
        return _component(
            identity, site_id, status, reason,
            evidence_at=evidence, last_success_at=success,
        )

    def _network_history(
        self, site_id: str, now: datetime, deadline: QueryDeadline
    ) -> HomeHealthComponent:
        identity = _COMPONENTS[2]
        runtime = self._observations
        state = getattr(runtime, "state", None)
        if state == "disabled":
            return _component(identity, site_id, "unavailable", "component_disabled")
        if state == "unavailable" or runtime is None:
            return _component(identity, site_id, "unavailable", "observation_unavailable")
        if state in {"starting", "stopping", None}:
            return _component(identity, site_id, "unknown", "initializing")
        config = getattr(runtime, "config", None)
        repository = getattr(runtime, "repository", None)
        if config is None or repository is None:
            return _component(identity, site_id, "unavailable", "observation_unavailable")
        required: list[tuple[str, Any, float]] = []
        site_count = len(config.site_ids)
        if config.client_enabled:
            deadline_seconds = (
                config.client_interval_seconds
                + site_count * config.client_max_pages * config.request_timeout_seconds
            )
            required.append(("client", runtime.client_worker, deadline_seconds))
        if config.ap_enabled:
            dynamic = site_count * config.ap_cycle_max_duration_seconds
            config_round = site_count * config.ap_config_cycle_max_duration_seconds
            deadline_seconds = max(config.ap_interval_seconds, config_round) + dynamic
            required.append(("ap_dynamic", runtime.ap_worker, deadline_seconds))
        if not required:
            return _component(identity, site_id, "unavailable", "component_disabled")
        latest_times: list[str] = []
        success_times: list[str] = []
        degraded = state == "degraded"
        stale = False
        for kind, worker, allowance in required:
            if not bool(getattr(worker, "running", False)):
                return _component(identity, site_id, "unavailable", "observation_unavailable")
            latest, success = repository.get_home_health_cycles(
                site_id, kind, deadline=deadline
            )
            if latest is not None and latest.finished_at is not None:
                latest_times.append(latest.finished_at)
                if latest.result != "success" or latest.complete is not True:
                    degraded = True
            if success is None or success.finished_at is None:
                return _component(
                    identity, site_id, "unknown", "initializing",
                    evidence_at=_minimum_timestamp(tuple(latest_times)),
                )
            success_times.append(success.finished_at)
            finished = _parse_timestamp(success.finished_at)
            if now > finished + timedelta(seconds=allowance):
                stale = True
        evidence = _minimum_timestamp(tuple(latest_times))
        last_success = _minimum_timestamp(tuple(success_times))
        if stale:
            status, reason = "degraded", "stale_evidence"
        elif degraded:
            status, reason = "degraded", "latest_collection_incomplete"
        else:
            status, reason = "operational", "observation_operational"
        return _component(
            identity, site_id, status, reason,
            evidence_at=evidence, last_success_at=last_success,
        )

    def _visit_tracking(
        self, site_id: str, now: datetime, deadline: QueryDeadline
    ) -> HomeHealthComponent:
        identity = _COMPONENTS[3]
        runtime = self._visits
        state = getattr(runtime, "state", None)
        available = bool(getattr(runtime, "available", False))
        if state == "disabled":
            return _component(identity, site_id, "unavailable", "component_disabled")
        if state == "unavailable" or not available or runtime is None:
            return _component(identity, site_id, "unavailable", "visit_runtime_unavailable")
        if state == "degraded":
            return _component(identity, site_id, "degraded", "visit_runtime_degraded")
        if state == "active" and available:
            return _component(identity, site_id, "operational", "visit_operational")
        return _component(identity, site_id, "unknown", "initializing")

    def _analytics_home_data(
        self, site_id: str, now: datetime, deadline: QueryDeadline
    ) -> HomeHealthComponent:
        identity = _COMPONENTS[4]
        runtime = self._analytics
        state = getattr(runtime, "state", None)
        if state == "disabled":
            return _component(identity, site_id, "unavailable", "component_disabled")
        if state == "unavailable" or runtime is None:
            return _component(identity, site_id, "unavailable", "analytics_source_unavailable")
        if state not in {"active", "degraded"}:
            return _component(identity, site_id, "unknown", "initializing")
        deadline.require_remaining()
        healthy, _ = runtime.live_health_payload()
        evidence_at = _utc(self._now_factory())
        deadline.require_remaining()
        if not healthy:
            status, reason = "unavailable", "analytics_source_unavailable"
        elif self._traffic_expected and getattr(runtime, "current_traffic_service", None) is None:
            status, reason = "degraded", "current_traffic_service_unavailable"
        elif self._activity_expected and getattr(runtime, "home_activity_service", None) is None:
            status, reason = "degraded", "home_activity_service_unavailable"
        elif state == "degraded":
            status, reason = "degraded", "analytics_source_unavailable"
        else:
            status, reason = "operational", "analytics_operational"
        return _component(
            identity, site_id, status, reason, evidence_at=evidence_at
        )


def _component(
    identity: tuple[str, str, str, str],
    site_id: str,
    status: str,
    reason: str,
    *,
    evidence_at: datetime | None = None,
    last_success_at: datetime | None = None,
) -> HomeHealthComponent:
    if status not in STATUSES or reason not in _MESSAGES:
        raise HomeHealthValidationError("Invalid health classification")
    component_id, label, criticality, scope_type = identity
    return HomeHealthComponent(
        component_id,
        label,
        status,
        reason,
        _MESSAGES[reason],
        criticality,
        scope_type,
        site_id if scope_type == "site" else None,
        evidence_at,
        last_success_at,
    )


def _aggregate(components: tuple[HomeHealthComponent, ...]) -> str:
    critical = next(item for item in components if item.criticality == "critical")
    if critical.status == "unavailable":
        return "unavailable"
    if any(item.status in {"degraded", "unavailable"} for item in components):
        return "degraded"
    if any(item.status == "unknown" for item in components):
        return "unknown"
    return "operational"


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise HomeHealthValidationError("Evaluation time must be timezone-aware")
    return value.astimezone(timezone.utc)


def _utc_or_none(value: object) -> datetime | None:
    try:
        return _utc(value)  # type: ignore[arg-type]
    except (HomeHealthValidationError, OverflowError, ValueError):
        return None


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise HomeHealthValidationError("Source timestamp is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HomeHealthValidationError("Source timestamp is invalid") from exc
    return _utc(parsed)


def _minimum_timestamp(values: tuple[object, ...]) -> datetime | None:
    if not values or any(value is None for value in values):
        return None
    return min(_parse_timestamp(value) for value in values)
