from __future__ import annotations

from typing import Optional
import time
import copy

from app.models.result import Result
from .models import PaginationResult
from .protocols import PendingClientSessionProvider


def paginate_site_inventory(
    provider: PendingClientSessionProvider,
    *,
    site_id: str,
    page_size: int,
    max_pages: int,
    max_clients: int,
    request_timeout_seconds: float,
    shutdown_event=None,
    budget_deadline: Optional[float] = None,
) -> PaginationResult:
    clients = []
    pages_fetched = 0
    controller_total = None
    page = 1
    any_successful = False

    while True:
        # pre-request checks
        if shutdown_event is not None and getattr(shutdown_event, "is_set", None) and shutdown_event.is_set():
            return PaginationResult(
                clients=tuple(clients),
                inventory_complete=False,
                scan_result="partial" if any_successful else "failed",
                pages_fetched=pages_fetched,
                controller_total_rows=controller_total,
                failure_reason="shutdown_requested",
            )

        if budget_deadline is not None and time.monotonic() > budget_deadline:
            return PaginationResult(
                clients=tuple(clients),
                inventory_complete=False,
                scan_result="partial" if any_successful else "failed",
                pages_fetched=pages_fetched,
                controller_total_rows=controller_total,
                failure_reason="scan_budget_exceeded",
            )

        if len(clients) >= max_clients and controller_total is not None and len(clients) < controller_total:
            # do not perform another request; return partial
            return PaginationResult(
                clients=tuple(clients),
                inventory_complete=False,
                scan_result="partial",
                pages_fetched=pages_fetched,
                controller_total_rows=controller_total,
                failure_reason="max_clients_reached_before_total",
            )

        if pages_fetched >= max_pages and (controller_total is None or len(clients) < controller_total):
            return PaginationResult(
                clients=tuple(clients),
                inventory_complete=False,
                scan_result="partial" if any_successful else "failed",
                pages_fetched=pages_fetched,
                controller_total_rows=controller_total,
                failure_reason="max_pages_exceeded",
            )

        result: Result = provider.list_active_clients(site_id=site_id, page=page, page_size=page_size, timeout_seconds=request_timeout_seconds)

        if not result.success:
            return PaginationResult(
                clients=tuple(clients),
                inventory_complete=False,
                scan_result="partial" if any_successful else "failed",
                pages_fetched=pages_fetched,
                controller_total_rows=controller_total,
                failure_reason=str(result.error or result.message or "page_request_failed"),
            )

        data = result.data
        if not isinstance(data, dict):
            return PaginationResult(
                clients=tuple(clients),
                inventory_complete=False,
                scan_result="partial" if any_successful else "failed",
                pages_fetched=pages_fetched,
                controller_total_rows=controller_total,
                failure_reason="result_data_not_object",
            )

        page_clients = data.get("clients")
        total_rows = data.get("total_rows")

        if type(total_rows) is not int or total_rows < 0:
            return PaginationResult(
                clients=tuple(clients),
                inventory_complete=False,
                scan_result="partial" if any_successful else "failed",
                pages_fetched=pages_fetched,
                controller_total_rows=controller_total,
                failure_reason="invalid_total_rows",
            )

        if not isinstance(page_clients, list):
            return PaginationResult(
                clients=tuple(clients),
                inventory_complete=False,
                scan_result="partial" if any_successful else "failed",
                pages_fetched=pages_fetched,
                controller_total_rows=total_rows,
                failure_reason="result.data.clients_not_list",
            )

        # total_rows first page becomes canonical
        if controller_total is None:
            controller_total = total_rows
        else:
            if total_rows != controller_total:
                return PaginationResult(
                    clients=tuple(clients),
                    inventory_complete=False,
                    scan_result="partial" if any_successful else "failed",
                    pages_fetched=pages_fetched,
                    controller_total_rows=controller_total,
                    failure_reason="total_rows_changed",
                )

        # append deep copies
        for item in page_clients:
            clients.append(copy.deepcopy(item))

        pages_fetched += 1
        any_successful = True

        if len(clients) > controller_total:
            return PaginationResult(
                clients=tuple(clients),
                inventory_complete=False,
                scan_result="partial",
                pages_fetched=pages_fetched,
                controller_total_rows=controller_total,
                failure_reason="row_count_exceeds_total",
            )

        if len(clients) == controller_total:
            return PaginationResult(
                clients=tuple(clients),
                inventory_complete=True,
                scan_result="success",
                pages_fetched=pages_fetched,
                controller_total_rows=controller_total,
                failure_reason=None,
            )

        if not page_clients:
            return PaginationResult(
                clients=tuple(clients),
                inventory_complete=False,
                scan_result="partial",
                pages_fetched=pages_fetched,
                controller_total_rows=controller_total,
                failure_reason="empty_page_before_total",
            )

        if len(page_clients) < page_size and len(clients) < controller_total:
            return PaginationResult(
                clients=tuple(clients),
                inventory_complete=False,
                scan_result="partial",
                pages_fetched=pages_fetched,
                controller_total_rows=controller_total,
                failure_reason="short_page_before_total",
            )

        page += 1