from __future__ import annotations

import copy
import math
from typing import Any

import requests

from app.common.mac import format_mac_hyphen
from app.models import Result

TOKEN_EXPIRED_ERROR = -44112


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
            "retryable": retryable,
            "http_status": http_status,
            "error_code": error_code,
        },
    )


def _validated_timeout(value: Any) -> float | None:
    if type(value) not in (int, float) or isinstance(value, bool):
        return None
    parsed = float(value)
    return parsed if parsed > 0 and math.isfinite(parsed) else None


def _token_or_failure(provider) -> tuple[str | None, Result | None]:
    result = provider._get_token()
    if not result.success:
        data = result.data if isinstance(result.data, dict) else {}
        return None, _failure(
            error="TOKEN_ERROR",
            message=result.message or "Token request failed",
            category=str(data.get("failure_category", "token_error")),
            retryable=bool(data.get("retryable", True)),
            http_status=data.get("http_status"),
            error_code=data.get("error_code"),
        )
    if not isinstance(result.data, dict):
        return None, _failure(
            error="TOKEN_ERROR",
            message="Token result data must be an object",
            category="malformed_response",
            retryable=True,
        )
    token = result.data.get("token")
    if not isinstance(token, str) or not token.strip():
        return None, _failure(
            error="TOKEN_ERROR",
            message="Token result contains no access token",
            category="malformed_response",
            retryable=True,
        )
    return token, None


def _parse_response(response) -> tuple[dict[str, Any] | None, Result | None]:
    status = response.status_code
    if not 200 <= status <= 299:
        retryable = status in {408, 429} or 500 <= status <= 599
        return None, _failure(
            error="HTTP_ERROR",
            message=f"HTTP {status}",
            category="http_error",
            retryable=retryable,
            http_status=status,
        )
    try:
        payload = response.json()
    except (TypeError, ValueError):
        return None, _failure(
            error="MALFORMED_RESPONSE",
            message="Controller returned invalid JSON",
            category="malformed_response",
            retryable=True,
            http_status=status,
        )
    if not isinstance(payload, dict):
        return None, _failure(
            error="MALFORMED_RESPONSE",
            message="Controller response root must be an object",
            category="malformed_response",
            retryable=True,
            http_status=status,
        )
    error_code = payload.get("errorCode")
    if type(error_code) is not int:
        return None, _failure(
            error="MALFORMED_RESPONSE",
            message="Controller errorCode must be an integer",
            category="malformed_response",
            retryable=True,
            http_status=status,
        )
    if error_code == TOKEN_EXPIRED_ERROR:
        return None, _failure(
            error="TOKEN_EXPIRED",
            message=str(payload.get("msg") or "Token expired"),
            category="token_expired",
            retryable=True,
            http_status=status,
            error_code=error_code,
        )
    if error_code != 0:
        return None, _failure(
            error="API_ERROR",
            message=str(payload.get("msg") or "Controller error"),
            category="controller_error",
            retryable=False,
            http_status=status,
            error_code=error_code,
        )
    return payload, None


def list_active_clients(
    self,
    *,
    site_id: str,
    page: int,
    page_size: int,
    timeout_seconds: float,
) -> Result:
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
    if type(page_size) is not int or page_size <= 0:
        return _failure(
            error="INVALID_PAGE_SIZE",
            message="page_size must be a positive integer",
            category="invalid_argument",
            retryable=False,
        )
    timeout = _validated_timeout(timeout_seconds)
    if timeout is None:
        return _failure(
            error="INVALID_TIMEOUT",
            message="timeout_seconds must be finite and positive",
            category="invalid_argument",
            retryable=False,
        )

    token, token_failure = _token_or_failure(self)
    if token_failure is not None:
        return token_failure
    url = (
        f"{self._omada_url}/openapi/v1/{self._omada_id}"
        f"/sites/{site_id.strip()}/clients"
    )
    try:
        response = requests.get(
            url,
            headers={"Authorization": f"AccessToken={token}"},
            params={"page": page, "pageSize": page_size},
            verify=self._verify_ssl,
            timeout=(timeout, timeout),
        )
    except requests.exceptions.Timeout as exc:
        return _failure(
            error="HTTP_ERROR",
            message=str(exc),
            category="timeout",
            retryable=True,
        )
    except requests.exceptions.RequestException as exc:
        return _failure(
            error="HTTP_ERROR",
            message=str(exc),
            category="network_error",
            retryable=True,
        )

    payload, failure = _parse_response(response)
    if failure is not None:
        return failure
    result = payload.get("result")
    if not isinstance(result, dict):
        return _failure(
            error="MALFORMED_RESPONSE",
            message="Controller result must be an object",
            category="malformed_response",
            retryable=True,
            http_status=response.status_code,
            error_code=0,
        )
    clients = result.get("data")
    total_rows = result.get("totalRows")
    if not isinstance(clients, list):
        return _failure(
            error="MALFORMED_RESPONSE",
            message="Controller result.data must be an array",
            category="malformed_response",
            retryable=True,
            http_status=response.status_code,
            error_code=0,
        )
    if type(total_rows) is not int or total_rows < 0:
        return _failure(
            error="MALFORMED_RESPONSE",
            message="Controller result.totalRows must be a non-negative integer",
            category="malformed_response",
            retryable=True,
            http_status=response.status_code,
            error_code=0,
        )
    return Result.ok(
        message=str(payload.get("msg") or "Success."),
        data={
            "http_status": response.status_code,
            "error_code": 0,
            "message": str(payload.get("msg") or "Success."),
            "page": page,
            "page_size": page_size,
            "total_rows": total_rows,
            "clients": copy.deepcopy(clients),
        },
    )


def get_pending_client_state(
    self,
    *,
    site_id: str,
    client_mac: str,
    timeout_seconds: float,
) -> Result:
    if not isinstance(site_id, str) or not site_id.strip():
        return _failure(
            error="INVALID_SITE_ID",
            message="site_id is required",
            category="invalid_argument",
            retryable=False,
        )
    try:
        endpoint_mac = format_mac_hyphen(client_mac)
    except (TypeError, ValueError):
        return _failure(
            error="INVALID_CLIENT_MAC",
            message="client_mac is invalid",
            category="invalid_argument",
            retryable=False,
        )
    timeout = _validated_timeout(timeout_seconds)
    if timeout is None:
        return _failure(
            error="INVALID_TIMEOUT",
            message="timeout_seconds must be finite and positive",
            category="invalid_argument",
            retryable=False,
        )

    token, token_failure = _token_or_failure(self)
    if token_failure is not None:
        return token_failure
    url = (
        f"{self._omada_url}/openapi/v1/{self._omada_id}"
        f"/sites/{site_id.strip()}/clients/{endpoint_mac}"
    )
    try:
        response = requests.get(
            url,
            headers={"Authorization": f"AccessToken={token}"},
            verify=self._verify_ssl,
            timeout=(timeout, timeout),
        )
    except requests.exceptions.Timeout as exc:
        return _failure(
            error="HTTP_ERROR",
            message=str(exc),
            category="timeout",
            retryable=True,
        )
    except requests.exceptions.RequestException as exc:
        return _failure(
            error="HTTP_ERROR",
            message=str(exc),
            category="network_error",
            retryable=True,
        )

    payload, failure = _parse_response(response)
    if failure is not None:
        return failure
    client = payload.get("result")
    if not isinstance(client, dict):
        return _failure(
            error="MALFORMED_RESPONSE",
            message="Controller result must be an object",
            category="malformed_response",
            retryable=True,
            http_status=response.status_code,
            error_code=0,
        )
    return Result.ok(
        message=str(payload.get("msg") or "Success."),
        data={
            "http_status": response.status_code,
            "error_code": 0,
            "message": str(payload.get("msg") or "Success."),
            "client": copy.deepcopy(client),
        },
    )


def reconnect_client(
    self,
    *,
    site_id: str,
    client_mac: str,
    timeout_seconds: float,
) -> Result:
    if not isinstance(site_id, str) or not site_id.strip():
        return _failure(
            error="INVALID_SITE_ID",
            message="site_id is required",
            category="invalid_argument",
            retryable=False,
        )
    try:
        endpoint_mac = format_mac_hyphen(client_mac)
    except (TypeError, ValueError):
        return _failure(
            error="INVALID_CLIENT_MAC",
            message="client_mac is invalid",
            category="invalid_argument",
            retryable=False,
        )
    timeout = _validated_timeout(timeout_seconds)
    if timeout is None:
        return _failure(
            error="INVALID_TIMEOUT",
            message="timeout_seconds must be finite and positive",
            category="invalid_argument",
            retryable=False,
        )

    token, token_failure = _token_or_failure(self)
    if token_failure is not None:
        return token_failure
    url = (
        f"{self._omada_url}/openapi/v1/{self._omada_id}"
        f"/sites/{site_id.strip()}/clients/{endpoint_mac}/reconnect"
    )
    try:
        response = requests.post(
            url,
            headers={"Authorization": f"AccessToken={token}"},
            verify=self._verify_ssl,
            timeout=(timeout, timeout),
        )
    except requests.exceptions.Timeout as exc:
        return _failure(
            error="HTTP_ERROR",
            message=str(exc),
            category="timeout",
            retryable=True,
        )
    except requests.exceptions.RequestException as exc:
        return _failure(
            error="HTTP_ERROR",
            message=str(exc),
            category="network_error",
            retryable=True,
        )

    payload, failure = _parse_response(response)
    if failure is not None:
        if failure.error == "TOKEN_EXPIRED":
            invalidate = getattr(
                self,
                "_invalidate_cached_token",
                None,
            )
            if callable(invalidate):
                invalidate(token)
        return failure
    return Result.ok(
        message=str(payload.get("msg") or "Success."),
        data={
            "http_status": response.status_code,
            "error_code": 0,
            "message": str(payload.get("msg") or "Success."),
            "command_accepted": True,
        },
    )


def install_pending_session_methods(provider_class) -> None:
    provider_class.list_active_clients = list_active_clients
    provider_class.get_pending_client_state = get_pending_client_state
    provider_class.reconnect_client = reconnect_client
