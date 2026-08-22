"""Site-enforcing, bounded Admin query orchestration."""

from __future__ import annotations

import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Any, Callable, Mapping

from app.analytics.serialization import serialize_analytics_value
from app.analytics.source_gateway import (
    AnalyticsQueryDeadlineExceeded,
    QueryDeadline,
)
from app.analytics.validation import AnalyticsQueryValidationError, parse_utc
from app.common.mac import format_mac_colon

from .config import AdminWebConfig
from .cursors import AdminCursorError, decode_cursor, encode_cursor
from .device_gateway import (
    AdminDeviceIntegrityError,
    AdminDeviceReadGateway,
    AdminDeviceSourceError,
)
from .models import AdminPrincipal
from .policy import AdminAccessPolicy
from .read_gateway import AdminReadSourceError, AdminSqlReadGateway


class AdminQueryError(RuntimeError):
    code = "internal_error"


class AdminQueryValidationError(AdminQueryError):
    code = "invalid_request"


class AdminQueryForbidden(AdminQueryError):
    code = "site_forbidden"


class AdminQueryNotFound(AdminQueryError):
    code = "not_found"


class AdminQueryBusy(AdminQueryError):
    code = "concurrency_limit"


class AdminQueryUnavailable(AdminQueryError):
    code = "source_unavailable"


class AdminQueryDeadline(AdminQueryError):
    code = "query_deadline"


@dataclass(frozen=True, slots=True)
class AdminQueryResponse:
    result: Any
    page: dict[str, Any] | None = None


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
    ):
        self._config = config
        self._policy = policy
        self._devices = device_gateway
        self._reads = read_gateway
        self._analytics = visit_analytics_service
        self._slots = threading.BoundedSemaphore(config.max_concurrent_queries)

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

    def list_devices(self, principal, site_id, *, limit=None, cursor=None):
        self._authorize(principal, "admin.read.devices", site_id)
        selected_limit = self._limit(limit, self._config.device_page_size)
        try:
            decoded = decode_cursor(
                cursor,
                kind="devices",
                site_id=site_id,
                filters={},
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
                    filters={},
                )
            return AdminQueryResponse(
                result={"items": items},
                page={"limit": selected_limit, "next_cursor": next_cursor},
            )

        return self._run(query)

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
        if not self._slots.acquire(blocking=False):
            raise AdminQueryBusy()
        try:
            deadline = QueryDeadline.after(
                self._config.max_query_duration_seconds
            )
            return operation(deadline)
        except AnalyticsQueryDeadlineExceeded as exc:
            raise AdminQueryDeadline() from exc
        except AnalyticsQueryValidationError as exc:
            raise AdminQueryValidationError() from exc
        except AdminDeviceIntegrityError as exc:
            raise AdminQueryUnavailable() from exc
        except (AdminDeviceSourceError, AdminReadSourceError) as exc:
            raise AdminQueryUnavailable() from exc
        finally:
            self._slots.release()

    def _authorize(self, principal, capability: str, site_id: str) -> None:
        if not self._policy.authorize(principal, capability, site_id):
            raise AdminQueryForbidden()

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
