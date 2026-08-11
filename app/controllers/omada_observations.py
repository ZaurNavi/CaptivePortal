"""Narrow read-only Omada extension for client observations."""

from __future__ import annotations

import copy
import math
from typing import Any

import requests

from app.models import Result


TOKEN_EXPIRED_ERROR = -44112
MAX_PAGE_SIZE = 500


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


def install_observation_methods(provider_class) -> None:
    provider_class.list_observation_clients = list_observation_clients
