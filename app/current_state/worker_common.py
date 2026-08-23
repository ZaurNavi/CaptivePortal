"""Shared bounded inventory polling without provider ownership."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.models import Result


@dataclass(slots=True)
class InventoryResult:
    rows: list[Any]
    total_rows: int | None
    complete: bool
    result: str
    error_count: int
    warning_count: int
    page_count: int
    failure_category: str | None
    http_status: int | None = None
    error_code: int | None = None


def poll_inventory(
    *,
    provider: Any,
    method_name: str,
    result_key: str,
    site_id: str,
    page_size: int,
    max_pages: int,
    max_rows: int,
    timeout_seconds: float,
    stop_event: Any,
) -> InventoryResult:
    rows: list[Any] = []
    expected_total: int | None = None
    page_count = 0
    last_http: int | None = None
    last_error: int | None = None
    method = getattr(provider, method_name)
    for page in range(1, max_pages + 1):
        if stop_event.is_set():
            return InventoryResult(rows, expected_total, False, "shutdown", 0, 0, page_count, "shutdown", last_http, last_error)
        try:
            response = method(site_id, page, page_size, timeout_seconds)
            page_count += 1
        except Exception:
            return InventoryResult(rows, expected_total, False, "partial" if rows else "failed", 1, 0, page_count + 1, "network_error")
        if not isinstance(response, Result) or not response.success:
            data = response.data if isinstance(response, Result) and isinstance(response.data, Mapping) else {}
            return InventoryResult(
                rows, expected_total, False, "partial" if rows else "failed", 1, 0, page_count,
                _category(data.get("failure_category")), _int(data.get("http_status")), _int(data.get("error_code")),
            )
        data = response.data if isinstance(response.data, Mapping) else {}
        page_rows = data.get(result_key)
        total = data.get("total_rows")
        returned_page = data.get("page")
        last_http = _int(data.get("http_status"))
        last_error = _int(data.get("error_code"))
        if (
            not isinstance(page_rows, list)
            or type(total) is not int
            or total < 0
            or type(returned_page) is not int
            or returned_page != page
            or (expected_total is not None and expected_total != total)
        ):
            return InventoryResult(rows, expected_total, False, "partial" if rows else "failed", 1, 1, page_count, "malformed_response", last_http, last_error)
        expected_total = total
        if total > max_rows:
            return InventoryResult(rows, expected_total, False, "partial" if rows else "failed", 1, 1, page_count, "row_limit", last_http, last_error)
        if len(rows) + len(page_rows) > max_rows:
            return InventoryResult(rows, expected_total, False, "partial" if rows else "failed", 1, 1, page_count, "row_limit", last_http, last_error)
        rows.extend(page_rows)
        if len(rows) > total:
            return InventoryResult(rows, expected_total, False, "partial", 1, 1, page_count, "inconsistent_total", last_http, last_error)
        if len(rows) == total:
            return InventoryResult(rows, total, True, "success", 0, 0, page_count, None, last_http, last_error)
        if not page_rows or len(page_rows) < page_size:
            return InventoryResult(rows, total, False, "partial" if rows else "failed", 1, 1, page_count, "inconsistent_total", last_http, last_error)
    return InventoryResult(rows, expected_total, False, "partial" if rows else "failed", 1, 1, page_count, "page_limit", last_http, last_error)


def _category(value: Any) -> str:
    allowed = {
        "timeout", "network_error", "http_error", "controller_error", "token_error",
        "malformed_response", "inconsistent_total", "row_limit", "page_limit", "shutdown",
    }
    return value if isinstance(value, str) and value in allowed else "controller_error"


def _int(value: Any) -> int | None:
    return value if type(value) is int else None
