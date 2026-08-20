"""Protected, aggregate-only internal HTTP API for Analytics v1."""

from __future__ import annotations

import hmac
import ipaddress
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from flask import Blueprint, Response, g, request

from .models import AnalyticsResult
from .serialization import AnalyticsSerializationError, serialize_analytics_value
from .validation import AnalyticsQueryValidationError, format_utc, parse_utc


API_VERSION = "analytics.internal.v1"
API_PREFIX = "/api/internal/analytics/v1"
QUALITY_MODE_DEFAULT = "strict_complete"


@dataclass(frozen=True, slots=True)
class _Endpoint:
    path: str
    service: str
    method: str
    allowed: frozenset[str]
    build: Callable[[Mapping[str, str]], tuple[tuple[Any, ...], dict[str, Any]]]


def create_analytics_blueprint(runtime: Any, *, logger: logging.Logger) -> Blueprint:
    config = runtime.api_config
    if config is None:
        raise ValueError("Analytics API configuration is unavailable")
    blueprint = Blueprint("analytics_internal_v1", __name__, url_prefix=API_PREFIX)
    slots = threading.BoundedSemaphore(config.max_concurrent_requests)

    @blueprint.before_app_request
    def protect_api():
        if not _is_analytics_path(request.path):
            return None
        g.analytics_request_id = str(uuid.uuid4())
        g.analytics_started = time.monotonic()
        g.analytics_telemetry_emitted = False
        if any(key.lower() in {"token", "access_token", "bearer_token"}
               for key in request.args.keys()):
            return _reject(
                logger, config, "query_token_forbidden", 400,
                "Authentication credentials are not accepted in the query string.",
            )
        authorization = request.headers.get("Authorization", "")
        if not _valid_bearer(authorization, config.bearer_token):
            response = _reject(
                logger, config, "invalid_credential", 401,
                "Authentication is required.",
            )
            response.headers["WWW-Authenticate"] = "Bearer"
            return response
        if not _source_allowed(request.remote_addr, config.allowed_networks):
            return _reject(
                logger, config, "source_network_forbidden", 403,
                "The source network is not allowed.",
            )
        return None

    @blueprint.after_app_request
    def security_headers(response: Response) -> Response:
        if not _is_analytics_path(request.path):
            return response
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        if not getattr(g, "analytics_telemetry_emitted", False):
            _emit_framework_response_telemetry(logger, response)
        return response

    @blueprint.get("/health")
    def health() -> Response:
        if request.args:
            return _reject(
                logger, config, "invalid_request", 400,
                "The request parameters are invalid.", "health",
            )
        if hasattr(runtime, "live_health_payload"):
            healthy, health_value = runtime.live_health_payload()
        else:
            healthy = runtime.state == "active"
            health_value = runtime.health_payload()
        status = "ok" if healthy else "unavailable"
        payload = {
            "api_version": API_VERSION,
            "request_id": g.analytics_request_id,
            "result": {
                "status": status,
                "value": health_value,
                "quality": {},
                "provenance": {},
            },
        }
        response = _json_response(
            payload,
            200 if status == "ok" else 503,
            config.max_response_bytes,
            logger,
        )
        if getattr(response, "analytics_response_too_large", False):
            _failed(logger, "health", 503, "response_too_large")
        elif not healthy:
            _failed(logger, "health", 503, "source_unavailable")
        else:
            _completed(
                logger, "health", response.status_code, status, None,
                response.calculate_content_length(),
            )
        return response

    for endpoint in _ENDPOINTS:
        blueprint.add_url_rule(
            endpoint.path,
            endpoint=f"analytics_{endpoint.method}",
            view_func=_metric_view(runtime, endpoint, slots, logger),
            methods=["GET"],
        )
    return blueprint


def _metric_view(
    runtime: Any,
    endpoint: _Endpoint,
    slots: threading.BoundedSemaphore,
    logger: logging.Logger,
) -> Callable[[], Response]:
    def view() -> Response:
        config = runtime.api_config
        assert config is not None
        try:
            parameters = _validated_parameters(endpoint.allowed)
            site = parameters["site_id"]
            if site not in config.allowed_site_ids:
                return _reject(
                    logger, config, "site_forbidden", 403,
                    "The requested Site is not allowed.", endpoint.method,
                )
            if runtime.state != "active":
                response = _error_response(
                    "analytics_unavailable",
                    "Analytics is temporarily unavailable.",
                    503,
                    config.max_response_bytes,
                    logger,
                )
                category = (
                    "runtime_disabled"
                    if runtime.state == "disabled"
                    else "runtime_unavailable"
                )
                _failed(logger, endpoint.method, 503, category)
                return response
            if not slots.acquire(blocking=False):
                response = _error_response(
                    "concurrency_limit",
                    "Too many Analytics requests are in progress.",
                    429,
                    config.max_response_bytes,
                    logger,
                )
                response.headers["Retry-After"] = "1"
                _rejected(logger, endpoint.method, 429, "concurrency_limit")
                return response
            try:
                args, kwargs = endpoint.build(parameters)
                service = getattr(runtime, endpoint.service)
                method = getattr(service, endpoint.method)
                result = method(*args, **kwargs)
                return _result_response(result, endpoint.method, config, logger)
            finally:
                slots.release()
        except AnalyticsSerializationError:
            response = _error_response(
                "serialization_error",
                "The Analytics response could not be serialized.",
                500,
                config.max_response_bytes,
                logger,
            )
            _failed(logger, endpoint.method, 500, "serialization_error")
            return response
        except AnalyticsQueryValidationError:
            response = _error_response(
                "invalid_request",
                "The request parameters are invalid.",
                400,
                config.max_response_bytes,
                logger,
            )
            _rejected(logger, endpoint.method, 400, "invalid_request")
            return response
        except Exception:
            response = _error_response(
                "internal_error",
                "The Analytics request failed.",
                500,
                config.max_response_bytes,
                logger,
            )
            _failed(logger, endpoint.method, 500, "internal_error")
            return response

    view.__name__ = f"analytics_{endpoint.method}"
    return view


def _result_response(
    result: AnalyticsResult[Any],
    metric: str,
    config: Any,
    logger: logging.Logger,
) -> Response:
    if not isinstance(result, AnalyticsResult):
        raise AnalyticsSerializationError("service returned an invalid result")
    serialized = serialize_analytics_value(result)
    reason = serialized["quality"].get("reason")
    status_code = (
        503
        if result.status == "unavailable" or reason == "query_deadline"
        else 200
    )
    payload = {
        "api_version": API_VERSION,
        "request_id": g.analytics_request_id,
        "result": serialized,
    }
    response = _json_response(
        payload,
        status_code,
        config.max_response_bytes,
        logger,
    )
    if getattr(response, "analytics_response_too_large", False):
        _failed(logger, metric, 503, "response_too_large")
    else:
        _completed(
            logger,
            metric,
            response.status_code,
            result.status,
            serialized.get("provenance"),
            response.calculate_content_length(),
        )
    return response


def _validated_parameters(allowed: frozenset[str]) -> dict[str, str]:
    unknown = set(request.args) - set(allowed)
    if unknown:
        raise AnalyticsQueryValidationError("unknown query parameter")
    parameters: dict[str, str] = {}
    for key in request.args:
        values = request.args.getlist(key)
        if len(values) != 1:
            raise AnalyticsQueryValidationError("duplicate scalar parameter")
        parameters[key] = values[0]
    for name in ("site_id", "from_utc", "to_utc"):
        if name not in parameters or not parameters[name]:
            raise AnalyticsQueryValidationError(f"{name} is required")
    start = parse_utc(parameters["from_utc"], "from_utc")
    end = parse_utc(parameters["to_utc"], "to_utc")
    if start >= end:
        raise AnalyticsQueryValidationError("from_utc must be before to_utc")
    return parameters


def _common(parameters: Mapping[str, str]) -> tuple[str, str, str]:
    return parameters["site_id"], parameters["from_utc"], parameters["to_utc"]


def _quality(parameters: Mapping[str, str]):
    site, start, end = _common(parameters)
    evaluation = format_utc(datetime.now(timezone.utc))
    return (site, start, end, evaluation), {}


def _signal(parameters: Mapping[str, str]):
    site, start, end = _common(parameters)
    return (
        site, start, end, _required(parameters, "metric"),
    ), {
        "ap_mac": parameters.get("ap_mac"),
        "ssid": parameters.get("ssid"),
        "band": parameters.get("band"),
        "channel": _optional_int(parameters, "channel"),
        "threshold": _optional_float(parameters, "threshold"),
        "quality_mode": parameters.get("quality_mode", QUALITY_MODE_DEFAULT),
    }


def _client_context(parameters: Mapping[str, str]):
    return (*_common(parameters), _required(parameters, "dimension")), {
        "quality_mode": parameters.get("quality_mode", QUALITY_MODE_DEFAULT)
    }


def _concurrency(parameters: Mapping[str, str]):
    return _common(parameters), {
        "group_by": parameters.get("group_by"),
        "quality_mode": parameters.get("quality_mode", QUALITY_MODE_DEFAULT),
    }


def _ap_resource(parameters: Mapping[str, str]):
    return (*_common(parameters), _required(parameters, "metric")), {
        "ap_mac": parameters.get("ap_mac"),
        "quality_mode": parameters.get("quality_mode", QUALITY_MODE_DEFAULT),
    }


def _radio(parameters: Mapping[str, str]):
    return (*_common(parameters), _required(parameters, "metric")), {
        "ap_mac": parameters.get("ap_mac"),
        "band": parameters.get("band"),
        "quality_mode": parameters.get("quality_mode", QUALITY_MODE_DEFAULT),
    }


def _throughput(parameters: Mapping[str, str]):
    return _radio(parameters)


def _counter_quality(parameters: Mapping[str, str]):
    return _common(parameters), {
        "ap_mac": parameters.get("ap_mac"),
        "band": parameters.get("band"),
        "quality_mode": parameters.get("quality_mode", QUALITY_MODE_DEFAULT),
    }


def _correlation(parameters: Mapping[str, str]):
    return (
        *_common(parameters),
        _required(parameters, "signal_metric"),
        _required(parameters, "ap_metric"),
    ), {"quality_mode": parameters.get("quality_mode", QUALITY_MODE_DEFAULT)}


def _visit(parameters: Mapping[str, str]):
    return _common(parameters), {}


def _time_series(parameters: Mapping[str, str]):
    return (*_common(parameters), _required(parameters, "granularity")), {
        "display_timezone": parameters.get("display_timezone", "UTC")
    }


def _required(parameters: Mapping[str, str], name: str) -> str:
    value = parameters.get(name)
    if not isinstance(value, str) or not value:
        raise AnalyticsQueryValidationError(f"{name} is required")
    return value


def _optional_int(parameters: Mapping[str, str], name: str) -> int | None:
    value = parameters.get(name)
    if value is None:
        return None
    if not value.isdigit():
        raise AnalyticsQueryValidationError(f"{name} must be an integer")
    return int(value)


def _optional_float(parameters: Mapping[str, str], name: str) -> float | None:
    value = parameters.get(name)
    if value is None:
        return None
    try:
        parsed = float(value)
    except ValueError as exc:
        raise AnalyticsQueryValidationError(f"{name} must be a number") from exc
    return parsed


_COMMON = frozenset({"site_id", "from_utc", "to_utc"})
_QUALITY = _COMMON
_WIRELESS_MODE = frozenset({"quality_mode"})
_ENDPOINTS = (
    _Endpoint(
        "/quality/source", "quality_service", "get_source_quality",
        _QUALITY, _quality,
    ),
    _Endpoint(
        "/wireless/signal", "wireless_service", "get_signal_distribution",
        _COMMON | _WIRELESS_MODE
        | {"metric", "ap_mac", "ssid", "band", "channel", "threshold"},
        _signal,
    ),
    _Endpoint(
        "/wireless/client-context", "wireless_service",
        "get_client_distribution",
        _COMMON | _WIRELESS_MODE | {"dimension"}, _client_context,
    ),
    _Endpoint(
        "/wireless/concurrency", "wireless_service",
        "get_concurrent_client_distribution",
        _COMMON | _WIRELESS_MODE | {"group_by"}, _concurrency,
    ),
    _Endpoint(
        "/wireless/ap-resource", "wireless_service",
        "get_ap_resource_distribution",
        _COMMON | _WIRELESS_MODE | {"metric", "ap_mac"}, _ap_resource,
    ),
    _Endpoint(
        "/wireless/radio-utilization", "wireless_service",
        "get_radio_utilization",
        _COMMON | _WIRELESS_MODE | {"metric", "ap_mac", "band"}, _radio,
    ),
    _Endpoint(
        "/wireless/throughput", "wireless_service",
        "get_throughput_distribution",
        _COMMON | _WIRELESS_MODE | {"metric", "ap_mac", "band"},
        _throughput,
    ),
    _Endpoint(
        "/wireless/counter-quality", "wireless_service",
        "get_counter_quality",
        _COMMON | _WIRELESS_MODE | {"ap_mac", "band"}, _counter_quality,
    ),
    _Endpoint(
        "/wireless/correlation", "wireless_service",
        "get_signal_ap_correlation",
        _COMMON | _WIRELESS_MODE | {"signal_metric", "ap_metric"},
        _correlation,
    ),
    _Endpoint("/visits/counts", "visit_service", "get_visit_counts", _COMMON, _visit),
    _Endpoint(
        "/visits/time-series", "visit_service", "get_visit_time_series",
        _COMMON | {"granularity", "display_timezone"}, _time_series,
    ),
    _Endpoint("/visits/devices", "visit_service", "get_device_counts", _COMMON, _visit),
    _Endpoint("/visits/repeat-devices", "visit_service", "get_repeat_devices", _COMMON, _visit),
    _Endpoint(
        "/visits/new-to-site", "visit_service", "get_new_to_site_devices",
        _COMMON, _visit,
    ),
    _Endpoint(
        "/visits/duration", "visit_service", "get_duration_distribution",
        _COMMON, _visit,
    ),
    _Endpoint(
        "/visits/authorizations", "visit_service",
        "get_authorization_distribution", _COMMON, _visit,
    ),
    _Endpoint(
        "/visits/closure", "visit_service", "get_closure_distribution",
        _COMMON, _visit,
    ),
    _Endpoint(
        "/visits/source-events", "visit_service", "get_source_event_quality",
        _COMMON, _visit,
    ),
    _Endpoint(
        "/visits/contexts", "visit_service", "get_context_distributions",
        _COMMON, _visit,
    ),
    _Endpoint(
        "/visits/transitions", "visit_service", "get_context_transition",
        _COMMON, _visit,
    ),
    _Endpoint(
        "/visits/observation-coverage", "visit_service",
        "get_observation_coverage_summary", _COMMON, _visit,
    ),
    _Endpoint(
        "/visits/traffic", "visit_service", "get_visit_traffic_summary",
        _COMMON, _visit,
    ),
    _Endpoint(
        "/visits/return-intervals", "visit_service", "get_return_intervals",
        _COMMON, _visit,
    ),
)


def _valid_bearer(header: str, expected: str) -> bool:
    if not isinstance(header, str) or header.count(" ") != 1:
        return False
    scheme, credential = header.split(" ", 1)
    if scheme != "Bearer" or not credential or credential.strip() != credential:
        return False
    return hmac.compare_digest(credential, expected)


def _source_allowed(remote_addr: str | None, networks: tuple[Any, ...]) -> bool:
    try:
        address = ipaddress.ip_address(remote_addr or "")
    except ValueError:
        return False
    return any(address.version == network.version and address in network for network in networks)


def _is_analytics_path(path: str) -> bool:
    return path == API_PREFIX or path.startswith(API_PREFIX + "/")


def _emit_framework_response_telemetry(
    logger: logging.Logger,
    response: Response,
) -> None:
    """Cover routing/framework responses that bypass endpoint view code."""
    status = int(response.status_code)
    category = {
        400: "invalid_request",
        401: "invalid_credential",
        403: "access_forbidden",
        404: "not_found",
        405: "method_not_allowed",
        413: "request_too_large",
        429: "concurrency_limit",
        500: "internal_error",
        503: "runtime_unavailable",
    }.get(status, "http_error")
    if status >= 500:
        _failed(logger, "routing", status, category)
    elif status >= 400:
        _rejected(logger, "routing", status, category)
    else:
        _completed(
            logger,
            "routing",
            status,
            "ok",
            None,
            response.calculate_content_length(),
        )


def _json_response(
    payload: Mapping[str, Any],
    status: int,
    maximum: int,
    logger: logging.Logger,
) -> Response:
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    overflow = len(encoded) > maximum
    if overflow:
        fallback = {
            "api_version": API_VERSION,
            "request_id": getattr(g, "analytics_request_id", str(uuid.uuid4())),
            "error": {
                "code": "response_too_large",
                "message": "The Analytics response exceeds the configured limit.",
            },
        }
        encoded = json.dumps(
            fallback, ensure_ascii=True, allow_nan=False,
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
        status = 503
    response = Response(encoded, status=status, content_type="application/json")
    response.analytics_response_too_large = overflow
    return response


def _error_response(
    code: str,
    message: str,
    status: int,
    maximum: int,
    logger: logging.Logger,
) -> Response:
    return _json_response(
        {
            "api_version": API_VERSION,
            "request_id": getattr(g, "analytics_request_id", str(uuid.uuid4())),
            "error": {"code": code, "message": message},
        },
        status,
        maximum,
        logger,
    )


def _reject(
    logger: logging.Logger,
    config: Any,
    category: str,
    status: int,
    message: str,
    metric: str = "security",
) -> Response:
    response = _error_response(
        category, message, status, config.max_response_bytes, logger
    )
    _rejected(logger, metric, status, category)
    return response


def _completed(
    logger: logging.Logger,
    metric: str,
    status: int,
    analytics_status: str,
    provenance: Mapping[str, Any] | None,
    response_size: int | None,
) -> None:
    g.analytics_telemetry_emitted = True
    fields: dict[str, Any] = {
        "request_id": getattr(g, "analytics_request_id", None),
        "metric": metric,
        "http_status": status,
        "analytics_status": analytics_status,
        "duration_ms": round(
            (time.monotonic() - getattr(g, "analytics_started", time.monotonic())) * 1000,
            3,
        ),
        "source_ip": request.remote_addr,
        "response_size": response_size,
    }
    if provenance:
        for source, target in (
            ("source_rows_examined", "rows_examined"),
            ("source_rows_accepted", "rows_accepted"),
            ("source_rows_rejected", "rows_rejected"),
        ):
            fields[target] = provenance.get(source)
    logger.info("analytics.api_request_completed %s", fields)


def _rejected(logger: logging.Logger, metric: str, status: int, category: str) -> None:
    g.analytics_telemetry_emitted = True
    logger.warning(
        "analytics.api_request_rejected %s",
        {
            "request_id": getattr(g, "analytics_request_id", None),
            "metric": metric,
            "http_status": status,
            "source_ip": request.remote_addr,
            "rejection_category": category,
        },
    )


def _failed(logger: logging.Logger, metric: str, status: int, category: str) -> None:
    g.analytics_telemetry_emitted = True
    logger.error(
        "analytics.api_request_failed %s",
        {
            "request_id": getattr(g, "analytics_request_id", None),
            "metric": metric,
            "http_status": status,
            "source_ip": request.remote_addr,
            "failure_category": category,
        },
    )
