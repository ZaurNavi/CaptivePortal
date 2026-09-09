"""Site-enforcing, bounded Admin query orchestration."""

from __future__ import annotations

import threading
import uuid
import sqlite3
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping

from app.analytics.serialization import serialize_analytics_value
from app.analytics.source_gateway import (
    AnalyticsQueryDeadlineExceeded,
    QueryDeadline,
)
from app.analytics.validation import AnalyticsQueryValidationError, parse_utc
from app.analytics.completed_guest_traffic import (
    DEFAULT_LIMIT as COMPLETED_GUEST_DEFAULT_LIMIT,
    MAX_LIMIT as COMPLETED_GUEST_MAX_LIMIT,
)
from app.analytics import (
    CompletedGuestSessionTrafficIntegrityUnavailable,
    CompletedGuestSessionTrafficSourceUnavailable,
    CompletedGuestSessionTrafficValidationError,
    CurrentGuestTrafficIntegrityUnavailable,
    CurrentGuestTrafficSourceUnavailable,
    CurrentGuestTrafficValidationError,
    CurrentTrafficIntegrityUnavailable,
    CurrentTrafficSourceUnavailable,
    CurrentTrafficValidationError,
    HistoricalTrafficIntegrityUnavailable,
    HistoricalTrafficSourceUnavailable,
    HistoricalTrafficValidationError,
    HomeActivitySourceUnavailable,
    HomeActivityValidationError,
)
from app.analytics.validation import format_utc
from app.common.mac import format_mac_colon
from app.current_state import (
    CurrentStateSchemaError,
    CurrentStateStorageError,
    CurrentStateValidationError,
)
from app.current_state.read_service import CurrentClientInventoryContextExpired
from app.current_state.normalizer import canonical_scope

from .config import AdminWebConfig
from .cursors import (
    AdminCursorError,
    decode_cursor,
    encode_cursor,
    filter_fingerprint,
)
from .device_gateway import (
    AdminDeviceContextExpired,
    AdminDeviceIntegrityError,
    AdminDeviceReadGateway,
    AdminDeviceSourceError,
)
from .device_list_context_cursor import (
    DeviceListContextCursor,
    DeviceListContextCursorError,
)
from .device_list_context_serialization import (
    DeviceListContextSerializationError,
    serialize_device_list_context,
    serialize_device_list_context_overlay,
)
from .models import AdminPrincipal
from .policy import AdminAccessPolicy
from .read_gateway import AdminReadSourceError, AdminSqlReadGateway
from .current_state_serialization import (
    serialize_ap_page,
    serialize_ap_summary,
    serialize_client_page,
    serialize_client_summary,
)
from .current_traffic_serialization import (
    CurrentTrafficSerializationError,
    serialize_current_ap_traffic_page,
    serialize_current_traffic_summary,
)
from .current_guest_traffic_serialization import (
    CurrentGuestTrafficSerializationError,
    serialize_current_guest_traffic,
)
from .device_current_context_serialization import (
    DeviceCurrentContextSerializationError,
    serialize_device_current_context,
)
from .completed_guest_traffic_serialization import (
    CompletedGuestSessionTrafficSerializationError,
    serialize_completed_guest_session_traffic,
)
from .home_activity_serialization import (
    HomeActivitySerializationError,
    serialize_home_activity,
)
from .home_health import HomeHealthValidationError
from .home_health_serialization import (
    HomeHealthSerializationError,
    serialize_home_health,
)
from .historical_traffic_serialization import (
    HistoricalTrafficSerializationError,
    serialize_historical_traffic,
)
from .traffic_network_ranges import (
    TrafficNetworkRangeError,
    resolve_traffic_network_range,
)
from .home_ap_24h_serialization import (
    HomeAp24SerializationError,
    serialize_home_ap_24h,
)
from app.analytics.home_ap_24h import (
    CONTRACT_VERSION as HOME_AP_24H_CONTRACT_VERSION,
    DEFAULT_PAGE_SIZE as HOME_AP_24H_DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE as HOME_AP_24H_MAX_PAGE_SIZE,
    HomeAp24SourceUnavailable,
    HomeAp24ValidationError,
)


class AdminQueryError(RuntimeError):
    code = "internal_error"


class AdminQueryValidationError(AdminQueryError):
    code = "invalid_request"


class AdminQueryCursorExpired(AdminQueryValidationError):
    code = "cursor_expired"


class AdminQueryForbidden(AdminQueryError):
    code = "site_forbidden"


class AdminQueryNotFound(AdminQueryError):
    code = "not_found"


class AdminQueryBusy(AdminQueryError):
    code = "concurrency_limit"


class AdminQueryUnavailable(AdminQueryError):
    code = "source_unavailable"


class AdminQueryIntegrityUnavailable(AdminQueryUnavailable):
    """A returned source/product projection contradicted its safe contract."""


class AdminQueryDeadline(AdminQueryError):
    code = "query_deadline"


_CURRENT_CLIENT_SORTS = frozenset({
    "client_mac", "controller_uptime", "controller_traffic_total_desc",
    "controller_traffic_down", "controller_traffic_up", "auth_status",
    "ap", "rssi", "snr",
})
_CURRENT_AUTH = frozenset({"authorized", "pending", "other", "unknown"})
_CURRENT_PAGE_CALLER_REASONS = frozenset({
    "cursor is malformed", "cursor Site changed", "cursor cycle changed",
    "cursor source scope changed", "cursor source scope is no longer current",
    "cursor context changed", "sort is not allowed", "limit is outside bounds",
    "auth_classification is invalid", "ap_mac is invalid", "ssid is invalid",
    "cycle_id is invalid",
})
_PREFETCH_NOT_PROVIDED = object()


@dataclass(frozen=True, slots=True)
class AdminQueryResponse:
    result: Any
    page: dict[str, Any] | None = None


class AdminQueryExecutionControls:
    """One process-owned Admin concurrency budget and request deadline."""

    def __init__(
        self,
        *,
        max_concurrent_queries: int,
        max_query_duration_seconds: int,
    ):
        self._slots = threading.BoundedSemaphore(max_concurrent_queries)
        self._max_query_duration_seconds = max_query_duration_seconds

    @property
    def max_query_duration_seconds(self) -> int:
        """Expose the authoritative bound for dependent shutdown joins."""
        return self._max_query_duration_seconds

    def run(self, operation: Callable[[QueryDeadline], Any]):
        if not self._slots.acquire(blocking=False):
            raise AdminQueryBusy()
        try:
            deadline = QueryDeadline.after(self._max_query_duration_seconds)
            return operation(deadline)
        except AnalyticsQueryDeadlineExceeded as exc:
            raise AdminQueryDeadline() from exc
        finally:
            self._slots.release()


class AdminHomeHealthQueryService:
    """Authorize and serialize Health using the shared Admin query gate."""

    def __init__(self, *, policy, read_service, execution_controls):
        self._policy = policy
        self._home_health = read_service
        self._execution_controls = execution_controls

    def home_health(self, principal, site_id):
        if not self._policy.authorize(
            principal, "admin.read.overview", site_id
        ):
            raise AdminQueryForbidden()
        source = self._home_health
        if source is None:
            raise AdminQueryUnavailable()

        def query(deadline):
            try:
                value = source.evaluate(site_id, deadline=deadline)
                return AdminQueryResponse(serialize_home_health(value))
            except HomeHealthValidationError as exc:
                raise AdminQueryValidationError() from exc
            except HomeHealthSerializationError as exc:
                raise AdminQueryUnavailable() from exc

        return self._execution_controls.run(query)


class AdminQueryService:
    """Repeat policy checks and coordinate one deadline/slot per request."""

    def __init__(
        self,
        *,
        config: AdminWebConfig,
        policy: AdminAccessPolicy,
        device_gateway: AdminDeviceReadGateway,
        read_gateway: AdminSqlReadGateway,
        visit_analytics_service: Any,
        current_state_read_service: Any | None = None,
        current_traffic_read_service: Any | None = None,
        current_guest_traffic_read_service: Any | None = None,
        completed_guest_session_traffic_read_service: Any | None = None,
        historical_traffic_read_service: Any | None = None,
        home_activity_read_service: Any | None = None,
        home_activity_config: Any | None = None,
        home_ap_24h_read_service: Any | None = None,
        execution_controls: AdminQueryExecutionControls | None = None,
        device_list_context_state: str = "disabled",
        device_list_context_cursor_codec: Any | None = None,
    ):
        self._config = config
        self._policy = policy
        self._devices = device_gateway
        self._reads = read_gateway
        self._analytics = visit_analytics_service
        self._current_state = current_state_read_service
        self._current_traffic = current_traffic_read_service
        self._current_guest_traffic = current_guest_traffic_read_service
        self._completed_guest_session_traffic = (
            completed_guest_session_traffic_read_service
        )
        self._historical_traffic = historical_traffic_read_service
        self._home_activity = home_activity_read_service
        self._home_activity_config = home_activity_config
        self._home_ap_24h = home_ap_24h_read_service
        self._device_list_context_state = device_list_context_state
        self._device_list_context_cursor_codec = device_list_context_cursor_codec
        self._execution_controls = execution_controls or (
            AdminQueryExecutionControls(
                max_concurrent_queries=config.max_concurrent_queries,
                max_query_duration_seconds=(
                    config.max_query_duration_seconds
                ),
            )
        )
        self._traffic_evidence = None

    def configure_traffic_evidence(self) -> None:
        """Compose optional Evidence without making core Admin composition fatal."""
        from .traffic_evidence import TrafficEvidenceAggregator

        self._traffic_evidence = TrafficEvidenceAggregator(
            config=self._config,
            read_current=self._traffic_evidence_current,
            read_historical=self._historical_traffic_projection,
            online_service=self._current_guest_traffic,
            completed_service=self._completed_guest_session_traffic,
            current_available=self._current_traffic is not None,
            historical_available=self._historical_traffic is not None,
        )

    @property
    def traffic_evidence_aggregator(self):
        return self._traffic_evidence

    def traffic_evidence(self, principal, site_id, *, range_id):
        self._authorize(principal, "admin.read.overview", site_id)
        self._authorize(principal, "admin.read.devices", site_id)
        try:
            resolved_range = resolve_traffic_network_range(
                range_id, datetime.now(timezone.utc)
            )
        except TrafficNetworkRangeError as exc:
            raise AdminQueryValidationError() from exc
        if self._traffic_evidence is None:
            raise AdminQueryUnavailable()

        def query(deadline):
            from .traffic_evidence_serialization import (
                TrafficEvidenceSerializationError,
            )
            try:
                return AdminQueryResponse(
                    self._traffic_evidence.get_evidence(
                        site_id, resolved_range=resolved_range, deadline=deadline
                    )
                )
            except TrafficEvidenceSerializationError as exc:
                raise AdminQueryIntegrityUnavailable() from exc

        return self._run(query)

    def current_guest_traffic(
        self, principal, site_id, *, limit=None, cursor=None
    ):
        self._authorize(principal, "admin.read.devices", site_id)
        selected_limit = self._current_guest_limit(limit)
        selected_cursor = self._current_guest_cursor(cursor)
        source = self._current_guest_traffic
        if source is None:
            raise AdminQueryUnavailable()

        def query(deadline):
            try:
                deadline.require_remaining()
                value = source.get_current_guest_traffic(
                    site_id,
                    limit=selected_limit,
                    cursor=selected_cursor,
                )
                deadline.require_remaining()
                result, page = serialize_current_guest_traffic(value, site_id)
                if page["limit"] != selected_limit:
                    raise AdminQueryIntegrityUnavailable()
                return AdminQueryResponse(result, page)
            except CurrentGuestTrafficValidationError as exc:
                if str(exc) == "cursor_expired":
                    raise AdminQueryCursorExpired() from exc
                raise AdminQueryValidationError() from exc
            except CurrentGuestTrafficIntegrityUnavailable as exc:
                raise AdminQueryIntegrityUnavailable() from exc
            except CurrentGuestTrafficSerializationError as exc:
                raise AdminQueryIntegrityUnavailable() from exc
            except CurrentGuestTrafficSourceUnavailable as exc:
                raise AdminQueryUnavailable() from exc

        return self._run(query)

    def completed_guest_session_traffic(
        self, principal, site_id, *, range_id, limit=None, cursor=None
    ):
        self._authorize(principal, "admin.read.devices", site_id)
        if range_id not in {"24h", "7d"}:
            raise AdminQueryValidationError()
        selected_limit = self._completed_guest_limit(limit)
        selected_cursor = self._completed_guest_cursor(cursor)
        source = self._completed_guest_session_traffic
        if source is None:
            raise AdminQueryUnavailable()

        def query(deadline):
            try:
                deadline.require_remaining()
                value = source.get_completed_guest_session_traffic(
                    site_id,
                    range_id=range_id,
                    limit=selected_limit,
                    cursor=selected_cursor,
                    deadline=deadline,
                )
                deadline.require_remaining()
                result, page = serialize_completed_guest_session_traffic(
                    value, site_id
                )
                if page["limit"] != selected_limit:
                    raise AdminQueryIntegrityUnavailable()
                return AdminQueryResponse(result)
            except CompletedGuestSessionTrafficValidationError as exc:
                raise AdminQueryValidationError() from exc
            except CompletedGuestSessionTrafficIntegrityUnavailable as exc:
                raise AdminQueryIntegrityUnavailable() from exc
            except CompletedGuestSessionTrafficSerializationError as exc:
                raise AdminQueryIntegrityUnavailable() from exc
            except CompletedGuestSessionTrafficSourceUnavailable as exc:
                raise AdminQueryUnavailable() from exc

        return self._run(query)

    def home_ap_24h(self, principal, site_id, *, limit=None, cursor=None):
        self._authorize(principal, "admin.read.overview", site_id)
        source = self._home_ap_24h
        if source is None:
            raise AdminQueryUnavailable()
        selected_limit = self._home_ap_24h_limit(limit)
        filters = {
            "limit": selected_limit,
            "contract_version": HOME_AP_24H_CONTRACT_VERSION,
            "window": "rolling_24h:900:96",
        }
        try:
            decoded = decode_cursor(
                cursor,
                kind="home_ap_24h",
                site_id=site_id,
                filters=filters,
                identity_kind="mac",
                maximum_length=self._config.max_cursor_chars,
            )
        except AdminCursorError as exc:
            raise AdminQueryValidationError() from exc
        anchor = None if decoded is None else parse_utc(decoded[0], "cursor timestamp")
        after = None if decoded is None else decoded[1]

        def query(deadline):
            try:
                value = source.get_home_ap_24h(
                    site_id,
                    evaluated_at_utc=anchor,
                    after_ap_mac=after,
                    limit=selected_limit,
                    deadline=deadline,
                )
                has_more = bool(value.get("page", {}).get("has_more"))
                result = serialize_home_ap_24h(value)
                next_cursor = None
                if has_more and result["items"]:
                    next_cursor = encode_cursor(
                        kind="home_ap_24h",
                        site_id=site_id,
                        timestamp=result["window"]["evaluated_at_utc"],
                        identity=result["items"][-1]["ap_mac"],
                        filters=filters,
                    )
                result["page"]["next_cursor"] = next_cursor
                return AdminQueryResponse(result)
            except HomeAp24ValidationError as exc:
                raise AdminQueryValidationError() from exc
            except (HomeAp24SourceUnavailable, HomeAp24SerializationError) as exc:
                raise AdminQueryUnavailable() from exc

        return self._run(query)

    def home_activity(
        self,
        principal,
        site_id,
        *,
        resolved_range,
        evaluated_at,
        next_site_midnight_utc=None,
    ):
        self._authorize(principal, "admin.read.overview", site_id)
        activity = self._home_activity_config
        source = self._home_activity
        context = None if activity is None else activity.site(site_id)
        if source is None or context is None or not activity.enabled:
            raise AdminQueryUnavailable()

        def query(deadline):
            try:
                value = source.get_activity(
                    site_id=site_id,
                    guest_ssids=activity.guest_ssids,
                    range_payload=resolved_range.public_range(),
                    from_utc=format_utc(resolved_range.from_utc),
                    to_utc=format_utc(resolved_range.to_utc),
                    evaluated_at_utc=format_utc(evaluated_at),
                    timezone_name=context.timezone,
                    visits_coverage_from_utc=context.visits_coverage_from_utc,
                    traffic_coverage_from_utc=context.traffic_coverage_from_utc,
                    traffic_fresh_max_age_seconds=(
                        activity.traffic_fresh_max_age_seconds
                    ),
                    traffic_stale_max_age_seconds=(
                        activity.traffic_stale_max_age_seconds
                    ),
                    deadline=deadline,
                    next_site_midnight_utc=next_site_midnight_utc,
                )
                return AdminQueryResponse(serialize_home_activity(value))
            except HomeActivityValidationError as exc:
                raise AdminQueryValidationError() from exc
            except (
                HomeActivitySourceUnavailable,
                HomeActivitySerializationError,
                sqlite3.Error,
                OSError,
            ) as exc:
                raise AdminQueryUnavailable() from exc

        return self._run(query)

    def current_client_summary(self, principal, site_id):
        self._authorize(principal, "admin.read.overview", site_id)

        def query(deadline):
            value = self._current_call(
                deadline, "summary", "get_current_client_summary", site_id
            )
            try:
                result = serialize_client_summary(value, site_id)
            except CurrentStateValidationError as exc:
                raise AdminQueryUnavailable() from exc
            return AdminQueryResponse(result)

        return self._run(query)

    def list_current_clients(
        self, principal, site_id, *, cycle_id=None, limit=None, cursor=None,
        sort=None, auth_classification=None, ap_mac=None, ssid=None,
    ):
        self._authorize(principal, "admin.read.devices", site_id)
        selected_limit = self._current_limit(limit)
        selected_cycle = self._current_cycle(cycle_id)
        selected_cursor = self._current_cursor(cursor)
        selected_sort = "controller_traffic_total_desc" if sort is None else sort
        if selected_sort not in _CURRENT_CLIENT_SORTS:
            raise AdminQueryValidationError()
        if auth_classification is not None and auth_classification not in _CURRENT_AUTH:
            raise AdminQueryValidationError()
        selected_ap = self._optional_mac(ap_mac)
        selected_ssid = self._exact_ssid(ssid)

        def query(deadline):
            value = self._current_call(
                deadline,
                "page",
                "list_current_clients",
                site_id,
                cycle_id=selected_cycle,
                limit=selected_limit,
                cursor=selected_cursor,
                sort=selected_sort,
                auth_classification=auth_classification,
                ap_mac=selected_ap,
                ssid=selected_ssid,
            )
            try:
                result, page = serialize_client_page(
                    value, site_id, limit=selected_limit,
                    explicit_cycle_id=selected_cycle,
                    explicit_cursor=selected_cursor,
                )
            except CurrentStateValidationError as exc:
                raise AdminQueryUnavailable() from exc
            except ValueError as exc:
                raise AdminQueryValidationError() from exc
            return AdminQueryResponse(result, page)

        return self._run(query)

    def current_ap_summary(self, principal, site_id):
        self._authorize(principal, "admin.read.overview", site_id)

        def query(deadline):
            value = self._current_call(
                deadline, "summary", "get_current_ap_summary", site_id
            )
            try:
                result = serialize_ap_summary(value, site_id)
            except CurrentStateValidationError as exc:
                raise AdminQueryUnavailable() from exc
            return AdminQueryResponse(result)

        return self._run(query)

    def list_current_aps(
        self, principal, site_id, *, cycle_id=None, limit=None, cursor=None,
    ):
        self._authorize(principal, "admin.read.overview", site_id)
        selected_limit = self._current_limit(limit)
        selected_cycle = self._current_cycle(cycle_id)
        selected_cursor = self._current_cursor(cursor)

        def query(deadline):
            value = self._current_call(
                deadline,
                "page",
                "list_current_aps",
                site_id,
                cycle_id=selected_cycle,
                limit=selected_limit,
                cursor=selected_cursor,
            )
            try:
                result, page = serialize_ap_page(
                    value, site_id, limit=selected_limit,
                    explicit_cycle_id=selected_cycle,
                    explicit_cursor=selected_cursor,
                )
            except CurrentStateValidationError as exc:
                raise AdminQueryUnavailable() from exc
            except ValueError as exc:
                raise AdminQueryValidationError() from exc
            return AdminQueryResponse(result, page)

        return self._run(query)

    def current_traffic_summary(self, principal, site_id):
        self._authorize(principal, "admin.read.overview", site_id)

        def query(deadline):
            value = self._traffic_call(
                deadline,
                "summary",
                "get_current_site_traffic",
                site_id,
                fresh_max_age_seconds=self._config.home_traffic_fresh_max_age_seconds,
                stale_max_age_seconds=self._config.home_traffic_stale_max_age_seconds,
                max_ap_skew_seconds=self._config.home_traffic_max_ap_skew_seconds,
            )
            try:
                result = serialize_current_traffic_summary(value, site_id)
            except CurrentTrafficSerializationError as exc:
                raise AdminQueryUnavailable() from exc
            return AdminQueryResponse(result)

        return self._run(query)

    def _read_current_site_raw(self, site_id, *, evaluated_at_utc, deadline):
        options = {
            "fresh_max_age_seconds": self._config.home_traffic_fresh_max_age_seconds,
            "stale_max_age_seconds": self._config.home_traffic_stale_max_age_seconds,
            "max_ap_skew_seconds": self._config.home_traffic_max_ap_skew_seconds,
        }
        if evaluated_at_utc is not None:
            options["evaluated_at_utc"] = evaluated_at_utc
        source = self._current_traffic
        if source is None:
            raise AdminQueryUnavailable()
        return source.get_current_site_traffic(
            site_id, deadline=deadline, **options
        )

    def _traffic_evidence_current(self, site_id, *, evaluated_at_utc, deadline):
        try:
            value = self._read_current_site_raw(
                site_id,
                evaluated_at_utc=evaluated_at_utc,
                deadline=deadline,
            )
            return value, serialize_current_traffic_summary(value, site_id)
        except AnalyticsQueryDeadlineExceeded as exc:
            raise AdminQueryDeadline() from exc
        except CurrentTrafficValidationError as exc:
            raise AdminQueryIntegrityUnavailable() from exc
        except CurrentTrafficIntegrityUnavailable as exc:
            raise AdminQueryIntegrityUnavailable() from exc
        except (CurrentTrafficSourceUnavailable, sqlite3.Error, OSError) as exc:
            raise AdminQueryUnavailable() from exc
        except CurrentTrafficSerializationError as exc:
            raise AdminQueryIntegrityUnavailable() from exc

    def historical_traffic_history(
        self, principal, site_id, *, range_id, include_statistics=False,
        include_peak=False, include_aps=False, include_ap_share=False,
        include_history=True,
        requested_products=None,
    ):
        self._authorize(principal, "admin.read.overview", site_id)
        try:
            resolved_range = resolve_traffic_network_range(
                range_id, datetime.now(timezone.utc)
            )
        except TrafficNetworkRangeError as exc:
            raise AdminQueryValidationError() from exc
        source = self._historical_traffic
        if source is None:
            raise AdminQueryUnavailable()

        def query(deadline):
            return self._historical_traffic_projection(
                site_id,
                resolved_range=resolved_range,
                deadline=deadline,
                include_statistics=include_statistics,
                include_peak=include_peak,
                include_aps=include_aps,
                include_ap_share=include_ap_share,
                include_history=include_history,
                requested_products=requested_products,
            )

        return self._run(query)

    def _historical_traffic_projection(
        self, site_id, *, resolved_range, deadline, include_statistics=False,
        include_peak=False, include_aps=False, include_ap_share=False,
        include_history=True, requested_products=None,
        prefetched_current=_PREFETCH_NOT_PROVIDED,
    ):
        source = self._historical_traffic
        if source is None:
            raise AdminQueryUnavailable()
        try:
            current_snapshot = None
            current_population_count = 0
            current_items = ()
            current_cycle_id = None
            current_population_status = (
                "unavailable" if include_ap_share else "available"
            )
            if include_aps or include_ap_share:
                current = prefetched_current
                if current is _PREFETCH_NOT_PROVIDED and self._current_traffic is not None:
                    try:
                        current = self._read_current_site_raw(
                            site_id,
                            evaluated_at_utc=resolved_range.evaluated_at_utc,
                            deadline=deadline,
                        )
                    except (
                        CurrentTrafficIntegrityUnavailable,
                        CurrentTrafficValidationError,
                    ) as exc:
                        if include_ap_share:
                            raise AdminQueryIntegrityUnavailable() from exc
                        current = None
                    except CurrentTrafficSourceUnavailable:
                        current = None
                        current_population_status = (
                            "unavailable" if include_ap_share else "available"
                        )
                if current is not _PREFETCH_NOT_PROVIDED and current is not None:
                    try:
                        current_snapshot = current.snapshot
                        current_population_count = current.coverage.total_ap_count
                        current_cycle_id = current.snapshot.cycle_id
                        current_population_status = (
                            "available"
                            if (
                                current_cycle_id is not None
                                and current.snapshot.complete is True
                                and current.snapshot.freshness_status in {"fresh", "stale"}
                            )
                            else ("unavailable" if include_ap_share else "available")
                        )
                        if include_ap_share and current_population_status == "unavailable":
                            current_snapshot = None
                            current_population_count = 0
                            current_cycle_id = None
                        if current_cycle_id is not None and current_population_count <= 12:
                            try:
                                page = self._current_traffic.list_current_ap_traffic(
                                    site_id,
                                    cycle_id=current_cycle_id,
                                    evaluated_at_utc=resolved_range.evaluated_at_utc,
                                    fresh_max_age_seconds=self._config.home_traffic_fresh_max_age_seconds,
                                    stale_max_age_seconds=self._config.home_traffic_stale_max_age_seconds,
                                    max_ap_skew_seconds=self._config.home_traffic_max_ap_skew_seconds,
                                    limit=12,
                                    deadline=deadline,
                                )
                                if page.page.next_cursor is not None:
                                    raise AdminQueryIntegrityUnavailable(
                                        "Current AP population projection is incomplete"
                                    )
                                current_items = page.items
                            except (
                                CurrentTrafficIntegrityUnavailable,
                                CurrentTrafficValidationError,
                            ) as exc:
                                if include_ap_share:
                                    raise AdminQueryIntegrityUnavailable() from exc
                                raise
                            except CurrentTrafficSourceUnavailable:
                                if include_ap_share:
                                    current_snapshot = None
                                    current_population_count = 0
                                    current_items = ()
                                    current_cycle_id = None
                                    current_population_status = "unavailable"
                                else:
                                    raise
                    except (
                        CurrentTrafficIntegrityUnavailable,
                        CurrentTrafficValidationError,
                    ) as exc:
                        if include_ap_share:
                            raise AdminQueryIntegrityUnavailable() from exc
                        current_snapshot = None
                        current_population_count = 0
                        current_items = ()
                        current_cycle_id = None
                        current_population_status = "available"
                    except CurrentTrafficSourceUnavailable:
                        current_snapshot = None
                        current_population_count = 0
                        current_items = ()
                        current_cycle_id = None
                        current_population_status = (
                            "unavailable" if include_ap_share else "available"
                        )
            value = source.get_site_history(
                site_id,
                from_utc=resolved_range.from_utc,
                to_utc=resolved_range.to_utc,
                evaluated_at_utc=resolved_range.evaluated_at_utc,
                deadline=deadline,
                include_period_statistics=include_statistics,
                include_peak_load=include_peak,
                include_ap_traffic=include_aps,
                include_ap_share=include_ap_share,
                current_population_status=current_population_status,
                current_cycle_id=current_cycle_id,
            )
            if include_aps:
                value = source.compose_current_ap_traffic(
                    value,
                    current_snapshot=current_snapshot,
                    current_population_count=current_population_count,
                    current_items=tuple(current_items),
                )
            result = serialize_historical_traffic(
                value,
                site_id,
                resolved_range=resolved_range,
                include_history=include_history,
                include_period_statistics=include_statistics,
                include_peak_load=include_peak,
                include_ap_traffic=include_aps,
                include_ap_share=include_ap_share,
                requested_products=requested_products,
            )
            return AdminQueryResponse(result)
        except HistoricalTrafficValidationError as exc:
            raise AdminQueryValidationError() from exc
        except (
            HistoricalTrafficIntegrityUnavailable,
            HistoricalTrafficSerializationError,
        ) as exc:
            if include_ap_share:
                raise AdminQueryIntegrityUnavailable() from exc
            raise AdminQueryUnavailable() from exc
        except (HistoricalTrafficSourceUnavailable, sqlite3.Error, OSError) as exc:
            raise AdminQueryUnavailable() from exc

    def list_current_ap_traffic(
        self, principal, site_id, *, cycle_id, limit=None, cursor=None,
    ):
        self._authorize(principal, "admin.read.observations", site_id)
        selected_cycle = self._current_cycle(cycle_id)
        if selected_cycle is None:
            raise AdminQueryValidationError()
        selected_limit = self._traffic_limit(limit)
        selected_cursor = self._current_cursor(cursor)

        def query(deadline):
            value = self._traffic_call(
                deadline,
                "page",
                "list_current_ap_traffic",
                site_id,
                cycle_id=selected_cycle,
                fresh_max_age_seconds=self._config.home_traffic_fresh_max_age_seconds,
                stale_max_age_seconds=self._config.home_traffic_stale_max_age_seconds,
                max_ap_skew_seconds=self._config.home_traffic_max_ap_skew_seconds,
                limit=selected_limit,
                cursor=selected_cursor,
            )
            try:
                result, page = serialize_current_ap_traffic_page(
                    value,
                    site_id,
                    cycle_id=selected_cycle,
                    limit=selected_limit,
                )
            except CurrentTrafficSerializationError as exc:
                raise AdminQueryUnavailable() from exc
            return AdminQueryResponse(result, page)

        return self._run(query)

    def visit_summary(self, principal, site_id, from_utc, to_utc):
        self._authorize(principal, "admin.read.overview", site_id)
        start, end = self._time_range(from_utc, to_utc)
        return self._run(
            lambda deadline: self._analytics_response(
                self._analytics.get_visit_counts(
                    site_id, start, end, deadline=deadline
                )
            )
        )

    def device_summary(self, principal, site_id, from_utc, to_utc):
        self._authorize(principal, "admin.read.overview", site_id)
        start, end = self._time_range(from_utc, to_utc)
        return self._run(
            lambda deadline: self._analytics_response(
                self._analytics.get_device_counts(
                    site_id, start, end, deadline=deadline
                )
            )
        )

    def list_devices(
        self, principal, site_id, *, limit=None, cursor=None, mac=None,
    ):
        self._authorize(principal, "admin.read.devices", site_id)
        selected_limit = self._limit(limit, self._config.device_page_size)
        selected_mac = self._optional_mac(mac)
        filters = {} if selected_mac is None else {"mac": selected_mac}
        if not self._config.device_list_context_enabled:
            try:
                decoded = decode_cursor(
                    cursor,
                    kind="devices",
                    site_id=site_id,
                    filters=filters,
                    identity_kind="uuid",
                    maximum_length=self._config.max_cursor_chars,
                )
            except AdminCursorError as exc:
                raise AdminQueryValidationError() from exc

            def query(deadline):
                page = self._devices.list_devices(
                    site_id=site_id,
                    limit=selected_limit,
                    cursor=decoded,  # type: ignore[arg-type]
                    canonical_mac=selected_mac,
                    deadline=deadline,
                )
                items = [self._device_list_dto(item) for item in page.items]
                next_cursor = None
                if page.has_more and page.items:
                    last = page.items[-1]
                    next_cursor = encode_cursor(
                        kind="devices",
                        site_id=site_id,
                        timestamp=last.site_last_seen_at,
                        identity=last.device_id,
                        filters=filters,
                    )
                return AdminQueryResponse(
                    result={"items": items},
                    page={"limit": selected_limit, "next_cursor": next_cursor},
                )

            return self._run(query)

        codec = self._device_list_context_cursor_codec
        if self._device_list_context_state != "active" or codec is None:
            raise AdminQueryUnavailable()
        try:
            decoded = codec.decode(cursor, site_id=site_id, filters=filters)
        except DeviceListContextCursorError as exc:
            raise AdminQueryValidationError() from exc

        return self._run(
            lambda deadline: self._device_list_context_response(
                deadline=deadline,
                site_id=site_id,
                selected_limit=selected_limit,
                selected_mac=selected_mac,
                filters=filters,
                decoded=decoded,
                codec=codec,
            )
        )

    def _device_list_context_response(
        self,
        *,
        deadline,
        site_id,
        selected_limit,
        selected_mac,
        filters,
        decoded,
        codec,
    ):
        if decoded is not None:
            return self._device_list_context_continuation(
                deadline=deadline,
                site_id=site_id,
                selected_limit=selected_limit,
                selected_mac=selected_mac,
                filters=filters,
                decoded=decoded,
                codec=codec,
            )

        evaluated = format_utc(datetime.now(timezone.utc))
        safe_scope = self._device_list_context_safe_scope(site_id)
        source = self._current_state
        method = getattr(source, "get_current_client_inventory_context", None)
        context = None
        execution_unavailable = (
            source is None or not callable(method) or safe_scope is None
        )
        if not execution_unavailable:
            try:
                deadline.require_remaining()
                context = method(site_id, evaluated_at_utc=evaluated)
                deadline.require_remaining()
            except CurrentClientInventoryContextExpired as exc:
                raise AdminQueryIntegrityUnavailable() from exc
            except AnalyticsQueryDeadlineExceeded:
                raise
            except (
                CurrentStateStorageError,
                CurrentStateSchemaError,
                CurrentStateValidationError,
                sqlite3.Error,
                OSError,
            ):
                execution_unavailable = True

        if execution_unavailable:
            overlay = self._device_list_context_overlay(
                site_id=site_id,
                overlay_mode="unknown",
                source_execution_status="unavailable",
                evaluated_at_utc=evaluated,
                scope=safe_scope,
                snapshot=None,
            )
            page = self._devices.list_devices_context(
                site_id=site_id,
                limit=selected_limit,
                deadline=deadline,
                overlay_mode="unknown",
                current_cycle_id=None,
                source_scope_hash=None,
                cursor=None,
                canonical_mac=selected_mac,
            )
            return self._device_list_context_page(
                site_id=site_id,
                selected_limit=selected_limit,
                filters=filters,
                page=page,
                overlay=overlay,
                current_cycle_id=None,
                source_scope_hash=None,
                codec=codec,
            )

        expected_scope_hash = None
        if safe_scope is not None:
            expected_scope_hash = canonical_scope(
                "client", site_id, tuple(safe_scope["ssids"])
            )[1]
        if (
            getattr(context, "site_id", None) != site_id
            or getattr(context, "evaluated_at_utc", None) != evaluated
            or getattr(context, "overlay_mode", None) not in {"trusted", "unknown"}
        ):
            raise AdminQueryIntegrityUnavailable()
        if context.overlay_mode == "trusted":
            if (
                safe_scope is None
                or not isinstance(getattr(context, "current_cycle_id", None), str)
                or not context.current_cycle_id
                or getattr(context, "source_scope_hash", None)
                != expected_scope_hash
            ):
                raise AdminQueryIntegrityUnavailable()
            overlay = self._device_list_context_trusted_overlay(
                site_id=site_id,
                evaluated_at_utc=evaluated,
                scope=safe_scope,
                snapshot=context.snapshot,
                current_cycle_id=context.current_cycle_id,
                source_scope_hash=context.source_scope_hash,
            )
        elif (
            getattr(context, "current_cycle_id", None) is not None
            or getattr(context, "source_scope_hash", None) is not None
        ):
            raise AdminQueryIntegrityUnavailable()
        else:
            overlay = self._device_list_context_overlay(
                site_id=site_id,
                overlay_mode=context.overlay_mode,
                source_execution_status="available",
                evaluated_at_utc=context.evaluated_at_utc,
                scope=safe_scope,
                snapshot=context.snapshot,
            )
        if context.overlay_mode == "unknown":
            page = self._devices.list_devices_context(
                site_id=site_id,
                limit=selected_limit,
                deadline=deadline,
                overlay_mode="unknown",
                current_cycle_id=None,
                source_scope_hash=None,
                cursor=None,
                canonical_mac=selected_mac,
            )
            return self._device_list_context_page(
                site_id=site_id,
                selected_limit=selected_limit,
                filters=filters,
                page=page,
                overlay=overlay,
                current_cycle_id=None,
                source_scope_hash=None,
                codec=codec,
            )
        try:
            page = self._devices.list_devices_context(
                site_id=site_id,
                limit=selected_limit,
                deadline=deadline,
                overlay_mode="trusted",
                current_cycle_id=context.current_cycle_id,
                source_scope_hash=context.source_scope_hash,
                cursor=None,
                canonical_mac=selected_mac,
            )
        except AdminDeviceIntegrityError:
            raise
        except (AdminDeviceContextExpired, AdminDeviceSourceError):
            deadline.require_remaining()
            overlay = self._device_list_context_overlay(
                site_id=site_id,
                overlay_mode="unknown",
                source_execution_status="unavailable",
                evaluated_at_utc=evaluated,
                scope=safe_scope,
                snapshot=None,
            )
            page = self._devices.list_devices_context(
                site_id=site_id,
                limit=selected_limit,
                deadline=deadline,
                overlay_mode="unknown",
                current_cycle_id=None,
                source_scope_hash=None,
                cursor=None,
                canonical_mac=selected_mac,
            )
            return self._device_list_context_page(
                site_id=site_id,
                selected_limit=selected_limit,
                filters=filters,
                page=page,
                overlay=overlay,
                current_cycle_id=None,
                source_scope_hash=None,
                codec=codec,
            )
        return self._device_list_context_page(
            site_id=site_id,
            selected_limit=selected_limit,
            filters=filters,
            page=page,
            overlay=overlay,
            current_cycle_id=context.current_cycle_id,
            source_scope_hash=context.source_scope_hash,
            codec=codec,
        )

    def _device_list_context_continuation(
        self,
        *,
        deadline,
        site_id,
        selected_limit,
        selected_mac,
        filters,
        decoded,
        codec,
    ):
        overlay = {
            "overlay_mode": decoded.overlay_mode,
            "ordering_applied": decoded.overlay_mode == "trusted",
            "source_execution_status": decoded.source_execution_status,
            "evaluated_at_utc": decoded.evaluated_at_utc,
            "scope": decoded.scope,
            "snapshot": decoded.snapshot,
        }
        cursor_key = (
            decoded.last_online_rank,
            decoded.last_site_last_seen_at,
            decoded.last_device_id,
        )
        if decoded.overlay_mode == "unknown":
            page = self._devices.list_devices_context(
                site_id=site_id,
                limit=selected_limit,
                deadline=deadline,
                overlay_mode="unknown",
                current_cycle_id=None,
                source_scope_hash=None,
                cursor=cursor_key,
                canonical_mac=selected_mac,
            )
        else:
            source = self._current_state
            method = getattr(source, "get_current_client_inventory_context", None)
            if source is None or not callable(method):
                raise AdminQueryUnavailable()
            try:
                deadline.require_remaining()
                context = method(
                    site_id,
                    evaluated_at_utc=decoded.evaluated_at_utc,
                    current_cycle_id=decoded.current_cycle_id,
                    expected_source_scope_hash=decoded.source_scope_hash,
                )
                deadline.require_remaining()
            except CurrentClientInventoryContextExpired as exc:
                raise AdminQueryCursorExpired() from exc
            except AnalyticsQueryDeadlineExceeded:
                raise
            except (
                CurrentStateStorageError,
                CurrentStateSchemaError,
                sqlite3.Error,
                OSError,
            ) as exc:
                raise AdminQueryUnavailable() from exc
            except CurrentStateValidationError as exc:
                raise AdminQueryIntegrityUnavailable() from exc
            if (
                getattr(context, "overlay_mode", None) != "trusted"
                or getattr(context, "site_id", None) != site_id
                or getattr(context, "evaluated_at_utc", None)
                != decoded.evaluated_at_utc
                or getattr(context, "current_cycle_id", None)
                != decoded.current_cycle_id
                or getattr(context, "source_scope_hash", None)
                != decoded.source_scope_hash
            ):
                raise AdminQueryIntegrityUnavailable()
            self._device_list_context_trusted_overlay(
                site_id=site_id,
                evaluated_at_utc=decoded.evaluated_at_utc,
                scope=decoded.scope,
                snapshot=context.snapshot,
                current_cycle_id=decoded.current_cycle_id,
                source_scope_hash=decoded.source_scope_hash,
            )
            try:
                page = self._devices.list_devices_context(
                    site_id=site_id,
                    limit=selected_limit,
                    deadline=deadline,
                    overlay_mode="trusted",
                    current_cycle_id=decoded.current_cycle_id,
                    source_scope_hash=decoded.source_scope_hash,
                    cursor=cursor_key,
                    canonical_mac=selected_mac,
                )
            except AdminDeviceContextExpired as exc:
                raise AdminQueryCursorExpired() from exc
        return self._device_list_context_page(
            site_id=site_id,
            selected_limit=selected_limit,
            filters=filters,
            page=page,
            overlay=overlay,
            current_cycle_id=decoded.current_cycle_id,
            source_scope_hash=decoded.source_scope_hash,
            codec=codec,
        )

    def _device_list_context_trusted_overlay(
        self,
        *,
        site_id,
        evaluated_at_utc,
        scope,
        snapshot,
        current_cycle_id,
        source_scope_hash,
    ):
        snapshot_scope = getattr(snapshot, "source_scope", None)
        if (
            getattr(snapshot, "site_id", None) != site_id
            or getattr(snapshot, "kind", None) != "client"
            or getattr(snapshot, "evaluated_at", None) != evaluated_at_utc
            or getattr(snapshot, "cycle_id", None) != current_cycle_id
            or getattr(snapshot, "source_scope_hash", None) != source_scope_hash
            or getattr(snapshot, "source_scope_version", None) != 1
            or getattr(snapshot, "complete", None) is not True
            or getattr(snapshot, "freshness_status", None) != "fresh"
            or getattr(snapshot, "freshness_reason", None)
            != "within_freshness_window"
            or not isinstance(snapshot_scope, Mapping)
            or not isinstance(scope, Mapping)
            or dict(snapshot_scope) != dict(scope)
        ):
            raise AdminQueryIntegrityUnavailable()
        return self._device_list_context_overlay(
            site_id=site_id,
            overlay_mode="trusted",
            source_execution_status="available",
            evaluated_at_utc=evaluated_at_utc,
            scope=scope,
            snapshot=snapshot,
        )

    @staticmethod
    def _device_list_context_overlay(**kwargs):
        try:
            return serialize_device_list_context_overlay(**kwargs)
        except DeviceListContextSerializationError as exc:
            raise AdminQueryIntegrityUnavailable() from exc

    def _device_list_context_page(
        self,
        *,
        site_id,
        selected_limit,
        filters,
        page,
        overlay,
        current_cycle_id,
        source_scope_hash,
        codec,
    ):
        try:
            result = serialize_device_list_context(
                site_id=site_id, items=page.items, overlay=overlay
            )
        except DeviceListContextSerializationError as exc:
            raise AdminQueryIntegrityUnavailable() from exc
        next_cursor = None
        if page.has_more:
            if not page.items:
                raise AdminQueryIntegrityUnavailable()
            last = page.items[-1]
            value = DeviceListContextCursor(
                version=1,
                kind="devices_context",
                site_id=site_id,
                filter_fingerprint=filter_fingerprint(filters),
                ordering_contract_version=1,
                overlay_mode=overlay["overlay_mode"],
                evaluated_at_utc=overlay["evaluated_at_utc"],
                source_execution_status=overlay["source_execution_status"],
                scope=overlay["scope"],
                snapshot=overlay["snapshot"],
                current_cycle_id=current_cycle_id,
                source_scope_hash=source_scope_hash,
                last_online_rank=last.online_rank,
                last_site_last_seen_at=last.site_last_seen_at,
                last_device_id=last.device_id,
            )
            try:
                next_cursor = codec.encode(value)
            except DeviceListContextCursorError as exc:
                raise AdminQueryUnavailable() from exc
        return AdminQueryResponse(
            result=result,
            page={"limit": selected_limit, "next_cursor": next_cursor},
        )

    def _device_list_context_safe_scope(self, site_id):
        try:
            config = getattr(self._current_state, "config", None)
            ssids = getattr(config, "client_ssids", None)
            if (
                not isinstance(ssids, (tuple, list))
                or not ssids
                or any(not isinstance(value, str) or not value for value in ssids)
            ):
                return None
            scope_json, _scope_hash = canonical_scope(
                "client", site_id, tuple(ssids)
            )
            scope = json.loads(scope_json)
            return scope if isinstance(scope, dict) else None
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

    def device_detail(self, principal, site_id, device_id):
        self._authorize(principal, "admin.read.device", site_id)
        selected_id = self._uuid(device_id, "device_id")

        def query(deadline):
            device = self._devices.get_device(
                site_id=site_id,
                device_id=selected_id,
                deadline=deadline,
            )
            if device is None:
                raise AdminQueryNotFound()
            visits, _ = self._reads.list_visits(
                site_id=site_id,
                device_id=selected_id,
                limit=min(20, self._config.visit_page_size),
                deadline=deadline,
            )
            observation = self._reads.latest_client_observation(
                site_id=site_id,
                client_mac=device.canonical_mac,
                deadline=deadline,
            )
            return AdminQueryResponse(
                result={
                    "identity": self._device_list_dto(device),
                    "latest_snapshot": device.latest_snapshot,
                    "recent_visits": list(visits),
                    "latest_client_observation": observation,
                }
            )

        return self._run(query)

    def device_current_context(
        self,
        principal,
        site_id,
        device_id,
        *,
        query_parameters_present: bool = False,
    ):
        """Compose one exact Device Current result under one Admin budget."""

        self._authorize(principal, "admin.read.device", site_id)
        if query_parameters_present:
            raise AdminQueryValidationError()
        selected_id = self._uuid(device_id, "device_id")
        if self._current_state is None:
            raise AdminQueryUnavailable()

        def query(deadline):
            device = self._devices.get_device(
                site_id=site_id,
                device_id=selected_id,
                deadline=deadline,
            )
            if device is None:
                raise AdminQueryNotFound()
            evaluated = format_utc(datetime.now(timezone.utc))
            current = self._current_call(
                deadline,
                "entity",
                "get_current_client",
                site_id,
                client_mac=device.canonical_mac,
                evaluated_at_utc=evaluated,
            )
            client = current.client
            if client is not None and client.auth_classification == "authorized":
                applicability = "applicable"
                applicability_reason = "authorized_current_guest"
            elif client is not None:
                applicability = "not_applicable"
                applicability_reason = "not_authorized_current_guest"
            elif (
                current.snapshot.freshness_status == "fresh"
                and current.snapshot.complete
            ):
                applicability = "not_applicable"
                applicability_reason = "offline"
            else:
                applicability = "unknown"
                applicability_reason = "current_state_unknown"

            traffic = None
            traffic_failure = None
            if applicability == "applicable":
                source = self._current_guest_traffic
                cycle_id = current.snapshot.cycle_id
                if source is None or cycle_id is None:
                    traffic_failure = "source_unavailable"
                else:
                    try:
                        deadline.require_remaining()
                        traffic = source.get_current_guest_traffic_for_client(
                            site_id,
                            device.canonical_mac,
                            evaluated_at_utc=evaluated,
                            current_cycle_id=cycle_id,
                        )
                        deadline.require_remaining()
                    except AnalyticsQueryDeadlineExceeded:
                        traffic = None
                        traffic_failure = "query_deadline"
                    except CurrentGuestTrafficIntegrityUnavailable:
                        traffic = None
                        traffic_failure = "integrity_unavailable"
                    except CurrentGuestTrafficSourceUnavailable:
                        traffic = None
                        traffic_failure = "source_unavailable"
                    except CurrentGuestTrafficValidationError:
                        traffic = None
                        traffic_failure = "integrity_unavailable"
            try:
                scope_json, _scope_hash = canonical_scope(
                    "client", site_id, self._current_state.config.client_ssids
                )
                scope = json.loads(scope_json)
                result = serialize_device_current_context(
                    site_id=site_id,
                    device_id=selected_id,
                    evaluated_at_utc=evaluated,
                    scope=scope,
                    current=current,
                    traffic=traffic,
                    applicability=applicability,
                    applicability_reason=applicability_reason,
                    traffic_failure_reason=traffic_failure,
                )
            except DeviceCurrentContextSerializationError as exc:
                raise AdminQueryIntegrityUnavailable() from exc
            return AdminQueryResponse(result=result)

        return self._run(query)

    def list_visits(
        self,
        principal,
        site_id,
        *,
        from_utc=None,
        to_utc=None,
        status=None,
        client_mac=None,
        device_id=None,
        ssid=None,
        ap_mac=None,
        limit=None,
        cursor=None,
    ):
        self._authorize(principal, "admin.read.visits", site_id)
        if (from_utc is None) != (to_utc is None):
            raise AdminQueryValidationError()
        start = end = None
        if from_utc is not None:
            start, end = self._time_range(from_utc, to_utc)
        if status is not None and status not in {"open", "closed"}:
            raise AdminQueryValidationError()
        mac = self._optional_mac(client_mac)
        selected_device = (
            None if device_id is None else self._uuid(device_id, "device_id")
        )
        selected_ssid = self._text_filter(ssid)
        selected_ap = self._optional_mac(ap_mac)
        selected_limit = self._limit(limit, self._config.visit_page_size)
        filters = {
            "from_utc": start,
            "to_utc": end,
            "status": status,
            "client_mac": mac,
            "device_id": selected_device,
            "ssid": selected_ssid,
            "ap_mac": selected_ap,
        }
        decoded = self._cursor(
            cursor, "visits", site_id, filters, "uuid"
        )

        def query(deadline):
            items, has_more = self._reads.list_visits(
                site_id=site_id,
                from_utc=start,
                to_utc=end,
                status=status,
                client_mac=mac,
                device_id=selected_device,
                ssid=selected_ssid,
                ap_mac=selected_ap,
                limit=selected_limit,
                cursor=decoded,  # type: ignore[arg-type]
                deadline=deadline,
            )
            next_cursor = None
            if has_more and items:
                next_cursor = encode_cursor(
                    kind="visits",
                    site_id=site_id,
                    timestamp=items[-1]["started_at"],
                    identity=items[-1]["visit_id"],
                    filters=filters,
                )
            return AdminQueryResponse(
                {"items": list(items)},
                {"limit": selected_limit, "next_cursor": next_cursor},
            )

        return self._run(query)

    def visit_detail(self, principal, site_id, visit_id):
        self._authorize(principal, "admin.read.visits", site_id)
        selected_id = self._uuid(visit_id, "visit_id")

        def query(deadline):
            visit = self._reads.get_visit(
                site_id=site_id,
                visit_id=selected_id,
                deadline=deadline,
            )
            if visit is None:
                raise AdminQueryNotFound()
            return AdminQueryResponse(visit)

        return self._run(query)

    def client_observations(
        self,
        principal,
        site_id,
        *,
        client_mac,
        from_utc,
        to_utc,
        limit=None,
        cursor=None,
    ):
        self._authorize(principal, "admin.read.observations", site_id)
        mac = self._mac(client_mac)
        start, end = self._observation_range(from_utc, to_utc)
        selected_limit = self._limit(
            limit, self._config.observation_page_size
        )
        filters = {"client_mac": mac, "from_utc": start, "to_utc": end}
        decoded = self._cursor(
            cursor, "client_observations", site_id, filters, "row_id"
        )

        def query(deadline):
            items, has_more = self._reads.list_client_observations(
                site_id=site_id,
                client_mac=mac,
                from_utc=start,
                to_utc=end,
                limit=selected_limit,
                cursor=decoded,  # type: ignore[arg-type]
                deadline=deadline,
            )
            return self._observation_response(
                items,
                has_more,
                selected_limit,
                site_id,
                "client_observations",
                filters,
                "observed_at",
            )

        return self._run(query)

    def ap_observations(
        self,
        principal,
        site_id,
        *,
        ap_mac,
        from_utc,
        to_utc,
        limit=None,
        cursor=None,
    ):
        self._authorize(principal, "admin.read.observations", site_id)
        mac = self._mac(ap_mac)
        start, end = self._observation_range(from_utc, to_utc)
        selected_limit = self._limit(
            limit, self._config.observation_page_size
        )
        filters = {"ap_mac": mac, "from_utc": start, "to_utc": end}
        decoded = self._cursor(
            cursor, "ap_observations", site_id, filters, "row_id"
        )

        def query(deadline):
            items, has_more = self._reads.list_ap_observations(
                site_id=site_id,
                ap_mac=mac,
                from_utc=start,
                to_utc=end,
                limit=selected_limit,
                cursor=decoded,  # type: ignore[arg-type]
                deadline=deadline,
            )
            return self._observation_response(
                items,
                has_more,
                selected_limit,
                site_id,
                "ap_observations",
                filters,
                "observed_at",
            )

        return self._run(query)

    def _run(self, operation: Callable[[QueryDeadline], AdminQueryResponse]):
        try:
            return self._execution_controls.run(operation)
        except AnalyticsQueryValidationError as exc:
            raise AdminQueryValidationError() from exc
        except AdminDeviceIntegrityError as exc:
            raise AdminQueryUnavailable() from exc
        except (AdminDeviceSourceError, AdminReadSourceError) as exc:
            raise AdminQueryUnavailable() from exc

    @property
    def _slots(self):
        """Compatibility access to the single shared execution gate."""
        return self._execution_controls._slots

    @_slots.setter
    def _slots(self, value):
        self._execution_controls._slots = value

    def _authorize(self, principal, capability: str, site_id: str) -> None:
        if not self._policy.authorize(principal, capability, site_id):
            raise AdminQueryForbidden()

    def _current_call(self, deadline, operation_kind, method_name, site_id, **kwargs):
        source = self._current_state
        if source is None:
            raise AdminQueryUnavailable()
        method = getattr(source, method_name, None)
        if not callable(method):
            raise AdminQueryUnavailable()
        try:
            deadline.require_remaining()
            value = method(site_id, **kwargs)
            deadline.require_remaining()
            return value
        except AnalyticsQueryDeadlineExceeded as exc:
            raise AdminQueryDeadline() from exc
        except CurrentStateValidationError as exc:
            if operation_kind == "page" and str(exc) in _CURRENT_PAGE_CALLER_REASONS:
                raise AdminQueryValidationError() from exc
            raise AdminQueryUnavailable() from exc
        except (CurrentStateSchemaError, CurrentStateStorageError, sqlite3.Error, OSError) as exc:
            raise AdminQueryUnavailable() from exc

    def _traffic_call(self, deadline, operation_kind, method_name, site_id, **kwargs):
        source = self._current_traffic
        if source is None:
            raise AdminQueryUnavailable()
        method = getattr(source, method_name, None)
        if not callable(method):
            raise AdminQueryUnavailable()
        try:
            return method(site_id, deadline=deadline, **kwargs)
        except AnalyticsQueryDeadlineExceeded as exc:
            raise AdminQueryDeadline() from exc
        except CurrentTrafficValidationError as exc:
            if operation_kind == "page":
                raise AdminQueryValidationError() from exc
            raise AdminQueryUnavailable() from exc
        except (CurrentTrafficSourceUnavailable, sqlite3.Error, OSError) as exc:
            raise AdminQueryUnavailable() from exc

    def _current_limit(self, value) -> int:
        if value is None:
            return self._config.current_state_page_size
        if not isinstance(value, str) or not value or not value.isascii() or not value.isdigit() or value.startswith("0"):
            raise AdminQueryValidationError()
        parsed = int(value)
        if not 1 <= parsed <= 250:
            raise AdminQueryValidationError()
        return parsed

    def _traffic_limit(self, value) -> int:
        if value is None:
            return self._config.home_traffic_page_size
        if not isinstance(value, str) or not value or not value.isascii() or not value.isdigit() or value.startswith("0"):
            raise AdminQueryValidationError()
        parsed = int(value)
        if not 1 <= parsed <= 250:
            raise AdminQueryValidationError()
        return parsed

    @staticmethod
    def _current_guest_limit(value) -> int:
        if value is None:
            return 50
        if (
            not isinstance(value, str) or not value or not value.isascii()
            or not value.isdigit() or value.startswith("0")
        ):
            raise AdminQueryValidationError()
        parsed = int(value)
        if not 1 <= parsed <= 200:
            raise AdminQueryValidationError()
        return parsed

    def _current_guest_cursor(self, value):
        if value is None:
            return None
        if (
            not isinstance(value, str) or not value
            or len(value) > min(2048, self._config.max_cursor_chars)
        ):
            raise AdminQueryValidationError()
        return value

    @staticmethod
    def _completed_guest_limit(value) -> int:
        if value is None:
            return COMPLETED_GUEST_DEFAULT_LIMIT
        if (
            not isinstance(value, str) or not value or not value.isascii()
            or not value.isdigit() or value.startswith("0")
        ):
            raise AdminQueryValidationError()
        parsed = int(value)
        if not 1 <= parsed <= COMPLETED_GUEST_MAX_LIMIT:
            raise AdminQueryValidationError()
        return parsed

    def _completed_guest_cursor(self, value):
        if value is None:
            return None
        if (
            not isinstance(value, str) or not value
            or len(value) > self._config.max_cursor_chars
        ):
            raise AdminQueryValidationError()
        return value

    @staticmethod
    def _home_ap_24h_limit(value) -> int:
        if value is None:
            return HOME_AP_24H_DEFAULT_PAGE_SIZE
        if not isinstance(value, str) or not value.isascii() or not value.isdigit() or value.startswith("0"):
            raise AdminQueryValidationError()
        parsed = int(value)
        if not 1 <= parsed <= HOME_AP_24H_MAX_PAGE_SIZE:
            raise AdminQueryValidationError()
        return parsed

    def _current_cursor(self, value):
        if value is None:
            return None
        if not isinstance(value, str) or not value or len(value) > self._config.max_cursor_chars:
            raise AdminQueryValidationError()
        return value

    @staticmethod
    def _current_cycle(value):
        if value is None:
            return None
        if not isinstance(value, str):
            raise AdminQueryValidationError()
        try:
            canonical = str(uuid.UUID(value))
        except (ValueError, AttributeError) as exc:
            raise AdminQueryValidationError() from exc
        if canonical != value:
            raise AdminQueryValidationError()
        return value

    def _exact_ssid(self, value):
        if value is None:
            return None
        if not isinstance(value, str) or value == "" or len(value) > self._config.max_filter_chars:
            raise AdminQueryValidationError()
        return value

    @staticmethod
    def _analytics_response(result: Any) -> AdminQueryResponse:
        if result.status == "unavailable":
            if result.quality.reason == "query_deadline":
                raise AdminQueryDeadline()
            raise AdminQueryUnavailable()
        return AdminQueryResponse(serialize_analytics_value(result))

    @staticmethod
    def _device_list_dto(item) -> dict[str, Any]:
        value = asdict(item)
        value.pop("latest_snapshot", None)
        return value

    def _observation_response(
        self,
        items,
        has_more,
        limit,
        site_id,
        kind,
        filters,
        timestamp_field,
    ):
        visible = []
        next_cursor = None
        for item in items:
            value = dict(item)
            value.pop("_row_id", None)
            visible.append(value)
        if has_more and items:
            next_cursor = encode_cursor(
                kind=kind,
                site_id=site_id,
                timestamp=items[-1][timestamp_field],
                identity=items[-1]["_row_id"],
                filters=filters,
            )
        return AdminQueryResponse(
            {"items": visible},
            {"limit": limit, "next_cursor": next_cursor},
        )

    def _cursor(self, value, kind, site_id, filters, identity_kind):
        try:
            return decode_cursor(
                value,
                kind=kind,
                site_id=site_id,
                filters=filters,
                identity_kind=identity_kind,
                maximum_length=self._config.max_cursor_chars,
            )
        except AdminCursorError as exc:
            raise AdminQueryValidationError() from exc

    @staticmethod
    def _time_range(from_utc, to_utc) -> tuple[str, str]:
        try:
            start = parse_utc(from_utc, "from_utc")
            end = parse_utc(to_utc, "to_utc")
        except Exception as exc:
            raise AdminQueryValidationError() from exc
        if start >= end:
            raise AdminQueryValidationError()
        return str(from_utc), str(to_utc)

    def _observation_range(self, from_utc, to_utc) -> tuple[str, str]:
        start_text, end_text = self._time_range(from_utc, to_utc)
        start = parse_utc(start_text, "from_utc")
        end = parse_utc(end_text, "to_utc")
        if end - start > timedelta(
            hours=self._config.observation_max_window_hours
        ):
            raise AdminQueryValidationError()
        return start_text, end_text

    def _limit(self, value, default: int) -> int:
        if value is None:
            return default
        if isinstance(value, str) and value.isdigit():
            value = int(value)
        if type(value) is not int or not 1 <= value <= min(default, 500):
            raise AdminQueryValidationError()
        return value

    def _text_filter(self, value):
        if value is None:
            return None
        if (
            not isinstance(value, str)
            or not value.strip()
            or len(value) > self._config.max_filter_chars
        ):
            raise AdminQueryValidationError()
        return value.strip()

    @classmethod
    def _optional_mac(cls, value):
        return None if value is None else cls._mac(value)

    @staticmethod
    def _mac(value):
        try:
            return format_mac_colon(value)
        except (TypeError, ValueError) as exc:
            raise AdminQueryValidationError() from exc

    @staticmethod
    def _uuid(value, name):
        if not isinstance(value, str):
            raise AdminQueryValidationError()
        try:
            canonical = str(uuid.UUID(value))
        except (ValueError, AttributeError) as exc:
            raise AdminQueryValidationError() from exc
        if canonical != value:
            raise AdminQueryValidationError()
        return value
