"""Application orchestration for compact consolidated Traffic evidence."""

from __future__ import annotations

import sqlite3
from typing import Any, Callable

from app.analytics import (
    CompletedGuestSessionTrafficIntegrityUnavailable,
    CompletedGuestSessionTrafficSourceUnavailable,
    CompletedGuestSessionTrafficValidationError,
    CurrentGuestTrafficIntegrityUnavailable,
    CurrentGuestTrafficSourceUnavailable,
    CurrentGuestTrafficValidationError,
)
from app.analytics.source_gateway import AnalyticsQueryDeadlineExceeded

from .completed_guest_traffic_serialization import (
    CompletedGuestSessionTrafficSerializationError,
    serialize_completed_guest_session_traffic,
)
from .current_guest_traffic_serialization import (
    CurrentGuestTrafficSerializationError,
    serialize_current_guest_traffic,
)
from .traffic_evidence_serialization import (
    CONTRACT_VERSION,
    PRODUCT_IDS,
    TrafficEvidenceSerializationError,
    project_aps,
    project_apshare,
    project_completed,
    project_current,
    project_history,
    project_online,
    project_peak,
    project_statistics,
    scope_completed,
    scope_current,
    scope_historical,
    scope_online,
    serialize_traffic_evidence,
)


class TrafficEvidenceAggregator:
    """Run at most four owner groups under one supplied Admin deadline."""

    def __init__(
        self,
        *,
        config: Any,
        read_current: Callable[..., Any],
        read_historical: Callable[..., Any],
        online_service: Any | None,
        completed_service: Any | None,
        current_available: bool,
        historical_available: bool,
    ):
        if not callable(read_current) or not callable(read_historical):
            raise TypeError("Traffic Evidence readers are unavailable")
        self._config = config
        self._read_current = read_current
        self._read_historical = read_historical
        self._online = online_service
        self._completed = completed_service
        self._current_available = current_available
        self._historical_available = historical_available

    def get_evidence(self, site_id: str, *, resolved_range, deadline) -> dict[str, Any]:
        exposures = self._exposures()
        scopes = self._scopes(resolved_range)
        products = {
            product_id: self._not_attempted(product_id, exposures[product_id], scopes[product_id])
            for product_id in PRODUCT_IDS
        }

        current_raw = None
        current_read_ok = False
        if not self._current_available:
            products["current"] = self._failed(
                "current", scopes["current"], "runtime_unavailable"
            )
        else:
            try:
                deadline.require_remaining()
                current_raw, current_value = self._read_current(
                    site_id,
                    evaluated_at_utc=resolved_range.evaluated_at_utc,
                    deadline=deadline,
                )
                current_read_ok = True
                products["current"] = self._available(
                    "current", scopes["current"], project_current(current_value)
                )
            except Exception as exc:  # one product failure must not stop later groups
                products["current"] = self._failed(
                    "current", scopes["current"], self._failure_category(exc)
                )

        historical_ids = tuple(
            product_id for product_id in (
                "history", "statistics", "peak", "aps", "apshare"
            ) if exposures[product_id]
        )
        if historical_ids and not self._historical_available:
            for product_id in historical_ids:
                products[product_id] = self._failed(
                    product_id, scopes[product_id], "runtime_unavailable"
                )
        elif historical_ids:
            try:
                deadline.require_remaining()
                response = self._read_historical(
                    site_id,
                    resolved_range=resolved_range,
                    deadline=deadline,
                    include_history=exposures["history"],
                    include_statistics=exposures["statistics"],
                    include_peak=exposures["peak"],
                    include_aps=exposures["aps"],
                    include_ap_share=exposures["apshare"],
                    requested_products=historical_ids,
                    prefetched_current=current_raw if current_read_ok else None,
                )
                value = response.result
                projectors = {
                    "history": project_history,
                    "statistics": project_statistics,
                    "peak": project_peak,
                    "aps": project_aps,
                    "apshare": project_apshare,
                }
                for product_id in historical_ids:
                    products[product_id] = self._available(
                        product_id,
                        scopes[product_id],
                        projectors[product_id](value),
                    )
            except Exception as exc:
                category = self._failure_category(exc)
                for product_id in historical_ids:
                    products[product_id] = self._failed(
                        product_id, scopes[product_id], category
                    )

        if exposures["online_guests"]:
            if self._online is None:
                products["online_guests"] = self._failed(
                    "online_guests", scopes["online_guests"], "runtime_unavailable"
                )
            else:
                try:
                    deadline.require_remaining()
                    value = self._online.get_current_guest_traffic(
                        site_id,
                        evaluated_at_utc=resolved_range.evaluated_at_utc,
                        limit=1,
                        cursor=None,
                    )
                    deadline.require_remaining()
                    serialized, page = serialize_current_guest_traffic(value, site_id)
                    if page["limit"] != 1:
                        raise TrafficEvidenceSerializationError(
                            "Online bounded page is invalid"
                        )
                    products["online_guests"] = self._available(
                        "online_guests", scopes["online_guests"], project_online(serialized)
                    )
                except Exception as exc:
                    products["online_guests"] = self._failed(
                        "online_guests", scopes["online_guests"],
                        self._failure_category(exc),
                    )

        if exposures["completed_sessions"]:
            if self._completed is None:
                products["completed_sessions"] = self._failed(
                    "completed_sessions", scopes["completed_sessions"],
                    "runtime_unavailable",
                )
            else:
                try:
                    deadline.require_remaining()
                    value = self._completed.get_completed_guest_session_traffic(
                        site_id,
                        range_id=resolved_range.id,
                        evaluated_at_utc=resolved_range.evaluated_at_utc,
                        limit=100,
                        cursor=None,
                        deadline=deadline,
                    )
                    deadline.require_remaining()
                    serialized, page = serialize_completed_guest_session_traffic(
                        value, site_id
                    )
                    if page["limit"] != 100 or serialized["range"] != {
                        "id": resolved_range.id,
                        "from_utc": resolved_range.from_utc,
                        "to_utc": resolved_range.to_utc,
                        "evaluated_at_utc": resolved_range.evaluated_at_utc,
                    }:
                        raise TrafficEvidenceSerializationError(
                            "Completed range is invalid"
                        )
                    products["completed_sessions"] = self._available(
                        "completed_sessions",
                        scope_completed(
                            resolved_range,
                            limit=100,
                            returned_count=page["returned_count"],
                            has_more=page["next_cursor"] is not None,
                        ),
                        project_completed(serialized),
                    )
                except Exception as exc:
                    products["completed_sessions"] = self._failed(
                        "completed_sessions", scopes["completed_sessions"],
                        self._failure_category(exc),
                    )

        result = {
            "contract_version": CONTRACT_VERSION,
            "evaluated_at_utc": resolved_range.evaluated_at_utc,
            "evidence_range": {
                "id": resolved_range.id,
                "from_utc": resolved_range.from_utc,
                "to_utc": resolved_range.to_utc,
            },
            "products": products,
        }
        return serialize_traffic_evidence(result, resolved_range=resolved_range)

    def _exposures(self) -> dict[str, bool]:
        return {
            "current": True,
            "history": self._config.traffic_history_enabled,
            "statistics": self._config.traffic_statistics_enabled,
            "peak": self._config.traffic_peak_enabled,
            "aps": self._config.traffic_by_ap_enabled,
            "apshare": self._config.traffic_ap_share_enabled,
            "online_guests": self._config.traffic_online_guests_enabled,
            "completed_sessions": self._config.traffic_completed_sessions_enabled,
        }

    @staticmethod
    def _scopes(value) -> dict[str, dict[str, Any]]:
        historical = scope_historical(value)
        return {
            "current": scope_current(value.evaluated_at_utc),
            "history": dict(historical),
            "statistics": dict(historical),
            "peak": dict(historical),
            "aps": dict(historical),
            "apshare": dict(historical),
            "online_guests": scope_online(value.evaluated_at_utc),
            "completed_sessions": None,
        }

    @staticmethod
    def _not_attempted(product_id, enabled, scope):
        return {
            "product_id": product_id,
            "exposure_status": "enabled" if enabled else "disabled",
            "delivery_status": "not_attempted",
            "scope": scope,
            "evidence": None,
            "failure_category": None,
        }

    @staticmethod
    def _available(product_id, scope, evidence):
        return {
            "product_id": product_id,
            "exposure_status": "enabled",
            "delivery_status": "available",
            "scope": scope,
            "evidence": evidence,
            "failure_category": None,
        }

    @staticmethod
    def _failed(product_id, scope, category):
        return {
            "product_id": product_id,
            "exposure_status": "enabled",
            "delivery_status": "failed",
            "scope": scope,
            "evidence": None,
            "failure_category": category,
        }

    @staticmethod
    def _failure_category(exc: Exception) -> str:
        name = type(exc).__name__
        code = getattr(exc, "code", None)
        if isinstance(exc, AnalyticsQueryDeadlineExceeded) or code == "query_deadline":
            return "query_deadline"
        if isinstance(exc, (
            TrafficEvidenceSerializationError,
            CurrentGuestTrafficSerializationError,
            CompletedGuestSessionTrafficSerializationError,
            CurrentGuestTrafficIntegrityUnavailable,
            CompletedGuestSessionTrafficIntegrityUnavailable,
        )) or "Integrity" in name or "Serialization" in name:
            return "integrity_unavailable"
        if isinstance(exc, (
            CurrentGuestTrafficSourceUnavailable,
            CompletedGuestSessionTrafficSourceUnavailable,
            sqlite3.Error,
            OSError,
        )) or code == "source_unavailable":
            return "source_unavailable"
        if isinstance(exc, (
            CurrentGuestTrafficValidationError,
            CompletedGuestSessionTrafficValidationError,
        )) or code == "invalid_request":
            return "integrity_unavailable"
        return "unexpected"
