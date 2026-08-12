"""Narrow read-only Omada extension for observation collectors."""

from __future__ import annotations

import copy
import math
from typing import Any

import requests

from app.common.mac import format_mac_hyphen
from app.models import Result


TOKEN_EXPIRED_ERROR = -44112
MAX_PAGE_SIZE = 500
MAX_AP_PAGE_SIZE = 100

_SAFE_OVERRIDE_FIELDS = frozenset({
    "ssidId", "ssidEntryId", "ssidName", "band", "security",
    "vlanEnable", "vlanId", "ssidEnable",
})
_SENSITIVE_KEY_PARTS = (
    "token", "secret", "password", "cookie", "authorization",
)


def _failure(
    *,
    error: str,
    message: str,
    category: str,
    retryable: bool,
    http_status: int | None = None,
    error_code: int | None = None,
) -> Result:
    return Result.fail(
        error=error,
        message=message,
        data={
            "failure_category": category,
            "retryable": bool(retryable),
            "http_status": http_status,
            "error_code": error_code,
        },
    )


def _validated_timeout(value: Any) -> float | None:
    if type(value) not in {int, float}:
        return None
    parsed = float(value)
    if not math.isfinite(parsed) or not 0 < parsed <= 60:
        return None
    return parsed


def _safe_token_failure(result: Result) -> Result:
    data = result.data if isinstance(result.data, dict) else {}
    status = data.get("http_status")
    error_code = data.get("error_code")
    category = data.get("failure_category")
    return _failure(
        error="TOKEN_ERROR",
        message="Observation token request failed",
        category=(
            category
            if isinstance(category, str) and category in {
                "timeout", "network_error", "http_error",
                "token_error", "malformed_response",
            }
            else "token_error"
        ),
        retryable=bool(data.get("retryable", True)),
        http_status=status if type(status) is int and status >= 0 else None,
        error_code=(
            error_code if type(error_code) is int else None
        ),
    )


def _get_shared_token(provider, *, force_refresh: bool = False):
    try:
        result = (
            provider._get_token(force_refresh=True)
            if force_refresh
            else provider._get_token()
        )
    except Exception:
        return None, _failure(
            error="TOKEN_ERROR",
            message="Observation token request failed",
            category="token_error",
            retryable=True,
        )
    if not isinstance(result, Result) or not result.success:
        if isinstance(result, Result):
            return None, _safe_token_failure(result)
        return None, _failure(
            error="TOKEN_ERROR",
            message="Observation token result is invalid",
            category="malformed_response",
            retryable=True,
        )
    data = result.data if isinstance(result.data, dict) else {}
    token = data.get("token")
    if not isinstance(token, str) or not token.strip():
        return None, _failure(
            error="TOKEN_ERROR",
            message="Observation token result is invalid",
            category="malformed_response",
            retryable=True,
        )
    return token, None


def _request_page(
    provider,
    *,
    token: str,
    site_id: str,
    page: int,
    page_size: int,
    timeout: float,
) -> Result:
    url = (
        f"{provider._omada_url}/openapi/v1/{provider._omada_id}"
        f"/sites/{site_id}/clients"
    )
    try:
        response = requests.get(
            url,
            headers={
                "Authorization": f"AccessToken={token}",
                "Accept": "application/json",
            },
            params={"page": page, "pageSize": page_size},
            verify=provider._verify_ssl,
            timeout=(timeout, timeout),
        )
    except requests.exceptions.Timeout:
        return _failure(
            error="HTTP_ERROR",
            message="Observation client request timed out",
            category="timeout",
            retryable=True,
        )
    except requests.exceptions.RequestException:
        return _failure(
            error="HTTP_ERROR",
            message="Observation client request failed",
            category="network_error",
            retryable=True,
        )
    except Exception:
        return _failure(
            error="HTTP_ERROR",
            message="Observation client request failed",
            category="network_error",
            retryable=True,
        )

    status = response.status_code
    if type(status) is not int or not 200 <= status <= 299:
        valid_status = status if type(status) is int else None
        retryable = (
            valid_status in {408, 429}
            or (valid_status is not None and 500 <= valid_status <= 599)
        )
        return _failure(
            error="HTTP_ERROR",
            message="Observation client endpoint returned an HTTP error",
            category="http_error",
            retryable=retryable,
            http_status=valid_status,
        )
    try:
        payload = response.json()
    except Exception:
        return _failure(
            error="MALFORMED_RESPONSE",
            message="Observation client endpoint returned malformed JSON",
            category="malformed_response",
            retryable=True,
            http_status=status,
        )
    if not isinstance(payload, dict):
        return _failure(
            error="MALFORMED_RESPONSE",
            message="Observation client response root must be an object",
            category="malformed_response",
            retryable=True,
            http_status=status,
        )
    error_code = payload.get("errorCode")
    if type(error_code) is not int:
        return _failure(
            error="MALFORMED_RESPONSE",
            message="Observation client errorCode must be an integer",
            category="malformed_response",
            retryable=True,
            http_status=status,
        )
    if error_code == TOKEN_EXPIRED_ERROR:
        return _failure(
            error="TOKEN_EXPIRED",
            message="Observation access token expired",
            category="token_expired",
            retryable=True,
            http_status=status,
            error_code=error_code,
        )
    if error_code != 0:
        return _failure(
            error="API_ERROR",
            message="Controller rejected observation client request",
            category="controller_error",
            retryable=False,
            http_status=status,
            error_code=error_code,
        )
    result = payload.get("result")
    if not isinstance(result, dict):
        return _failure(
            error="MALFORMED_RESPONSE",
            message="Observation client result must be an object",
            category="malformed_response",
            retryable=True,
            http_status=status,
            error_code=0,
        )
    clients = result.get("data")
    total_rows = result.get("totalRows")
    if not isinstance(clients, list):
        return _failure(
            error="MALFORMED_RESPONSE",
            message="Observation client data must be an array",
            category="malformed_response",
            retryable=True,
            http_status=status,
            error_code=0,
        )
    if type(total_rows) is not int or total_rows < 0:
        return _failure(
            error="MALFORMED_RESPONSE",
            message="Observation totalRows must be a non-negative integer",
            category="malformed_response",
            retryable=True,
            http_status=status,
            error_code=0,
        )
    current_page = result.get("currentPage")
    if current_page is not None and (
        type(current_page) is not int or current_page != page
    ):
        return _failure(
            error="MALFORMED_RESPONSE",
            message="Observation currentPage is inconsistent",
            category="malformed_response",
            retryable=True,
            http_status=status,
            error_code=0,
        )
    if len(clients) > page_size:
        return _failure(
            error="MALFORMED_RESPONSE",
            message="Observation page exceeds the requested bound",
            category="malformed_response",
            retryable=True,
            http_status=status,
            error_code=0,
        )
    try:
        copied_clients = copy.deepcopy(clients)
    except Exception:
        return _failure(
            error="MALFORMED_RESPONSE",
            message="Observation client data could not be copied",
            category="malformed_response",
            retryable=True,
            http_status=status,
            error_code=0,
        )
    return Result.ok(
        message="Success",
        data={
            "clients": copied_clients,
            "total_rows": total_rows,
            "page": page,
            "page_size": page_size,
            "http_status": status,
            "error_code": 0,
        },
    )


def list_observation_clients(
    self,
    site_id: str,
    page: int,
    page_size: int,
    timeout_seconds: float,
) -> Result:
    """Return one strictly validated page using the shared token cache."""
    if not isinstance(site_id, str) or not site_id.strip():
        return _failure(
            error="INVALID_SITE_ID",
            message="site_id is required",
            category="invalid_argument",
            retryable=False,
        )
    if type(page) is not int or page <= 0:
        return _failure(
            error="INVALID_PAGE",
            message="page must be a positive integer",
            category="invalid_argument",
            retryable=False,
        )
    if (
        type(page_size) is not int
        or not 1 <= page_size <= MAX_PAGE_SIZE
    ):
        return _failure(
            error="INVALID_PAGE_SIZE",
            message="page_size is outside the observation bound",
            category="invalid_argument",
            retryable=False,
        )
    timeout = _validated_timeout(timeout_seconds)
    if timeout is None:
        return _failure(
            error="INVALID_TIMEOUT",
            message="timeout_seconds is outside the observation bound",
            category="invalid_argument",
            retryable=False,
        )
    site = site_id.strip()
    token, failure = _get_shared_token(self)
    if failure is not None:
        return failure
    response = _request_page(
        self,
        token=token,
        site_id=site,
        page=page,
        page_size=page_size,
        timeout=timeout,
    )
    if response.error != "TOKEN_EXPIRED":
        return response
    invalidate = getattr(self, "_invalidate_cached_token", None)
    if callable(invalidate):
        try:
            invalidate(token)
        except Exception:
            return _failure(
                error="TOKEN_ERROR",
                message="Observation token invalidation failed",
                category="token_error",
                retryable=True,
            )
    fresh_token, failure = _get_shared_token(self, force_refresh=True)
    if failure is not None:
        return failure
    retried = _request_page(
        self,
        token=fresh_token,
        site_id=site,
        page=page,
        page_size=page_size,
        timeout=timeout,
    )
    if retried.error == "TOKEN_EXPIRED" and callable(invalidate):
        try:
            invalidate(fresh_token)
        except Exception:
            return _failure(
                error="TOKEN_ERROR",
                message="Observation token invalidation failed",
                category="token_error",
                retryable=True,
            )
    return retried


def _validated_identity(value: Any, *, error: str, message: str) -> tuple[str | None, Result | None]:
    if not isinstance(value, str) or not value.strip():
        return None, _failure(
            error=error,
            message=message,
            category="invalid_argument",
            retryable=False,
        )
    return value.strip(), None


def _validated_ap_mac(value: Any) -> tuple[str | None, Result | None]:
    try:
        return format_mac_hyphen(value), None
    except (TypeError, ValueError):
        return None, _failure(
            error="INVALID_AP_MAC",
            message="ap_mac must be a valid MAC address",
            category="invalid_argument",
            retryable=False,
        )


def _request_observation_result(
    provider,
    *,
    token: str,
    url: str,
    timeout: float,
    params: dict[str, int] | None = None,
    result_kind: str,
    allow_missing_result: bool = False,
) -> Result:
    try:
        response = requests.get(
            url,
            headers={
                "Authorization": f"AccessToken={token}",
                "Accept": "application/json",
            },
            params=params,
            verify=provider._verify_ssl,
            timeout=(timeout, timeout),
        )
    except requests.exceptions.Timeout:
        return _failure(
            error="HTTP_ERROR",
            message="Observation request timed out",
            category="timeout",
            retryable=True,
        )
    except requests.exceptions.RequestException:
        return _failure(
            error="HTTP_ERROR",
            message="Observation request failed",
            category="network_error",
            retryable=True,
        )
    except Exception:
        return _failure(
            error="HTTP_ERROR",
            message="Observation request failed",
            category="network_error",
            retryable=True,
        )

    status = response.status_code
    if type(status) is not int or not 200 <= status <= 299:
        valid_status = status if type(status) is int else None
        error_code = None
        try:
            failure_payload = response.json()
            if isinstance(failure_payload, dict):
                candidate = failure_payload.get("errorCode")
                error_code = candidate if type(candidate) is int else None
        except Exception:
            pass
        retryable = (
            valid_status in {408, 429}
            or (valid_status is not None and 500 <= valid_status <= 599)
        )
        return _failure(
            error="HTTP_ERROR",
            message="Observation endpoint returned an HTTP error",
            category="http_error",
            retryable=retryable,
            http_status=valid_status,
            error_code=error_code,
        )
    try:
        payload = response.json()
    except Exception:
        return _failure(
            error="MALFORMED_RESPONSE",
            message="Observation endpoint returned malformed JSON",
            category="malformed_response",
            retryable=True,
            http_status=status,
        )
    if not isinstance(payload, dict):
        return _failure(
            error="MALFORMED_RESPONSE",
            message="Observation response root must be an object",
            category="malformed_response",
            retryable=True,
            http_status=status,
        )
    error_code = payload.get("errorCode")
    if type(error_code) is not int:
        return _failure(
            error="MALFORMED_RESPONSE",
            message="Observation errorCode must be an integer",
            category="malformed_response",
            retryable=True,
            http_status=status,
        )
    if error_code == TOKEN_EXPIRED_ERROR:
        return _failure(
            error="TOKEN_EXPIRED",
            message="Observation access token expired",
            category="token_expired",
            retryable=True,
            http_status=status,
            error_code=error_code,
        )
    if error_code != 0:
        return _failure(
            error="API_ERROR",
            message="Controller rejected observation request",
            category="controller_error",
            retryable=False,
            http_status=status,
            error_code=error_code,
        )
    result_present = "result" in payload
    result = payload.get("result")
    valid_result = (
        (result_kind == "object" and isinstance(result, dict))
        or (result_kind == "list" and isinstance(result, list))
        or (
            allow_missing_result
            and (not result_present or result is None)
        )
    )
    if not valid_result:
        return _failure(
            error="MALFORMED_RESPONSE",
            message="Observation result has an invalid container",
            category="malformed_response",
            retryable=True,
            http_status=status,
            error_code=0,
        )
    try:
        copied = copy.deepcopy(result)
        _strip_sensitive_fields(copied)
    except Exception:
        return _failure(
            error="MALFORMED_RESPONSE",
            message="Observation result could not be copied",
            category="malformed_response",
            retryable=True,
            http_status=status,
            error_code=0,
        )
    return Result.ok(
        message="Success",
        data={
            "result": copied,
            "http_status": status,
            "error_code": 0,
        },
    )


def _strip_sensitive_fields(value: Any) -> None:
    if isinstance(value, dict):
        for key in tuple(value):
            normalized = "".join(
                character.lower()
                for character in str(key)
                if character.isalnum()
            )
            if any(part in normalized for part in _SENSITIVE_KEY_PARTS):
                value.pop(key, None)
                continue
            _strip_sensitive_fields(value[key])
    elif isinstance(value, list):
        for item in value:
            _strip_sensitive_fields(item)


def _observation_get(
    provider,
    *,
    url: str,
    timeout: float,
    params: dict[str, int] | None = None,
    result_kind: str = "object",
    allow_missing_result: bool = False,
) -> Result:
    token, failure = _get_shared_token(provider)
    if failure is not None:
        return failure
    response = _request_observation_result(
        provider,
        token=token,
        url=url,
        timeout=timeout,
        params=params,
        result_kind=result_kind,
        allow_missing_result=allow_missing_result,
    )
    if response.error != "TOKEN_EXPIRED":
        return response
    invalidate = getattr(provider, "_invalidate_cached_token", None)
    if callable(invalidate):
        try:
            invalidate(token)
        except Exception:
            return _failure(
                error="TOKEN_ERROR",
                message="Observation token invalidation failed",
                category="token_error",
                retryable=True,
            )
    fresh_token, failure = _get_shared_token(provider, force_refresh=True)
    if failure is not None:
        return failure
    retried = _request_observation_result(
        provider,
        token=fresh_token,
        url=url,
        timeout=timeout,
        params=params,
        result_kind=result_kind,
        allow_missing_result=allow_missing_result,
    )
    if retried.error == "TOKEN_EXPIRED" and callable(invalidate):
        try:
            invalidate(fresh_token)
        except Exception:
            return _failure(
                error="TOKEN_ERROR",
                message="Observation token invalidation failed",
                category="token_error",
                retryable=True,
            )
    return retried


def list_observation_access_points(
    self,
    site_id: str,
    page: int,
    page_size: int,
    timeout_seconds: float,
) -> Result:
    site, failure = _validated_identity(
        site_id,
        error="INVALID_SITE_ID",
        message="site_id is required",
    )
    if failure is not None:
        return failure
    if type(page) is not int or page <= 0:
        return _failure(error="INVALID_PAGE", message="page must be positive", category="invalid_argument", retryable=False)
    if type(page_size) is not int or not 1 <= page_size <= MAX_AP_PAGE_SIZE:
        return _failure(error="INVALID_PAGE_SIZE", message="page_size is outside the AP bound", category="invalid_argument", retryable=False)
    timeout = _validated_timeout(timeout_seconds)
    if timeout is None:
        return _failure(error="INVALID_TIMEOUT", message="timeout_seconds is outside the observation bound", category="invalid_argument", retryable=False)
    url = f"{self._omada_url}/openapi/v1/{self._omada_id}/sites/{site}/devices"
    response = _observation_get(
        self,
        url=url,
        timeout=timeout,
        params={"page": page, "pageSize": page_size},
    )
    if not response.success:
        return response
    result = response.data.get("result")
    rows = result.get("data") if isinstance(result, dict) else None
    total_rows = result.get("totalRows") if isinstance(result, dict) else None
    current_page = result.get("currentPage") if isinstance(result, dict) else None
    if (
        not isinstance(rows, list)
        or type(total_rows) is not int
        or total_rows < 0
        or (current_page is not None and (type(current_page) is not int or current_page != page))
        or len(rows) > page_size
    ):
        return _failure(
            error="MALFORMED_RESPONSE",
            message="Observation AP inventory page is malformed",
            category="malformed_response",
            retryable=True,
            http_status=response.data.get("http_status"),
            error_code=0,
        )
    return Result.ok(message="Success", data={
        "access_points": rows,
        "total_rows": total_rows,
        "page": page,
        "page_size": page_size,
        "http_status": response.data.get("http_status"),
        "error_code": 0,
    })


def _get_ap_endpoint(
    self,
    site_id: str,
    ap_mac: str,
    timeout_seconds: float,
    *,
    suffix: str,
    version: int = 1,
    result_kind: str = "object",
    allow_missing_result: bool = False,
) -> Result:
    site, failure = _validated_identity(site_id, error="INVALID_SITE_ID", message="site_id is required")
    if failure is not None:
        return failure
    endpoint_mac, failure = _validated_ap_mac(ap_mac)
    if failure is not None:
        return failure
    timeout = _validated_timeout(timeout_seconds)
    if timeout is None:
        return _failure(error="INVALID_TIMEOUT", message="timeout_seconds is outside the observation bound", category="invalid_argument", retryable=False)
    url = (
        f"{self._omada_url}/openapi/v{version}/{self._omada_id}"
        f"/sites/{site}/aps/{endpoint_mac}{suffix}"
    )
    return _observation_get(
        self,
        url=url,
        timeout=timeout,
        result_kind=result_kind,
        allow_missing_result=allow_missing_result,
    )


def get_observation_ap_overview(self, site_id, ap_mac, timeout_seconds):
    return _get_ap_endpoint(self, site_id, ap_mac, timeout_seconds, suffix="")


def get_observation_ap_wired_uplink(self, site_id, ap_mac, timeout_seconds):
    return _get_ap_endpoint(self, site_id, ap_mac, timeout_seconds, suffix="/wired-uplink")


def get_observation_ap_lan_traffic(self, site_id, ap_mac, timeout_seconds):
    return _get_ap_endpoint(self, site_id, ap_mac, timeout_seconds, suffix="/lan-traffic-info")


def get_observation_ap_radios(self, site_id, ap_mac, timeout_seconds):
    return _get_ap_endpoint(self, site_id, ap_mac, timeout_seconds, suffix="/radios")


def get_observation_ap_general_config(self, site_id, ap_mac, timeout_seconds):
    return _get_ap_endpoint(self, site_id, ap_mac, timeout_seconds, suffix="/general-config")


def get_observation_ap_ip_setting(self, site_id, ap_mac, timeout_seconds):
    return _get_ap_endpoint(self, site_id, ap_mac, timeout_seconds, suffix="/ip-setting")


def get_observation_ap_radio_config(self, site_id, ap_mac, timeout_seconds):
    return _get_ap_endpoint(self, site_id, ap_mac, timeout_seconds, suffix="/radio-config")


def get_observation_ap_ofdma(self, site_id, ap_mac, timeout_seconds):
    return _get_ap_endpoint(self, site_id, ap_mac, timeout_seconds, suffix="/ofdma")


def get_observation_ap_available_channels(self, site_id, ap_mac, timeout_seconds):
    return _get_ap_endpoint(self, site_id, ap_mac, timeout_seconds, suffix="/available-channel", result_kind="list")


def get_observation_ap_safe_overrides(self, site_id, ap_mac, timeout_seconds):
    response = _get_ap_endpoint(self, site_id, ap_mac, timeout_seconds, suffix="/override", version=2)
    if not response.success:
        return response
    result = response.data.get("result")
    entries = result.get("ssidOverrides") if isinstance(result, dict) else None
    if not isinstance(entries, list):
        return _failure(error="MALFORMED_RESPONSE", message="Observation override result is malformed", category="malformed_response", retryable=True, http_status=response.data.get("http_status"), error_code=0)
    safe_entries = []
    for entry in entries:
        if not isinstance(entry, dict):
            return _failure(error="MALFORMED_RESPONSE", message="Observation override item is malformed", category="malformed_response", retryable=True, http_status=response.data.get("http_status"), error_code=0)
        try:
            safe_entries.append(copy.deepcopy({key: entry[key] for key in _SAFE_OVERRIDE_FIELDS if key in entry}))
        except Exception:
            return _failure(error="MALFORMED_RESPONSE", message="Observation override item could not be copied", category="malformed_response", retryable=True, http_status=response.data.get("http_status"), error_code=0)
    return Result.ok(message="Success", data={
        "result": {"ssidOverrides": safe_entries},
        "http_status": response.data.get("http_status"),
        "error_code": 0,
    })


def get_observation_ap_rf_scan_state(self, site_id, ap_mac, timeout_seconds):
    return _get_ap_endpoint(self, site_id, ap_mac, timeout_seconds, suffix="/rf-scan-result", version=2, allow_missing_result=True)


def install_observation_methods(provider_class) -> None:
    provider_class.list_observation_clients = list_observation_clients
    provider_class.list_observation_access_points = list_observation_access_points
    provider_class.get_observation_ap_overview = get_observation_ap_overview
    provider_class.get_observation_ap_wired_uplink = get_observation_ap_wired_uplink
    provider_class.get_observation_ap_lan_traffic = get_observation_ap_lan_traffic
    provider_class.get_observation_ap_radios = get_observation_ap_radios
    provider_class.get_observation_ap_general_config = get_observation_ap_general_config
    provider_class.get_observation_ap_ip_setting = get_observation_ap_ip_setting
    provider_class.get_observation_ap_radio_config = get_observation_ap_radio_config
    provider_class.get_observation_ap_ofdma = get_observation_ap_ofdma
    provider_class.get_observation_ap_available_channels = get_observation_ap_available_channels
    provider_class.get_observation_ap_safe_overrides = get_observation_ap_safe_overrides
    provider_class.get_observation_ap_rf_scan_state = get_observation_ap_rf_scan_state
