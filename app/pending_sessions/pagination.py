from __future__ import annotations

import copy
import time
from typing import Optional

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
    clients: list[dict] = []
    pages_fetched = 0
    controller_total: Optional[int] = None
    page = 1

    def finish(reason: str) -> PaginationResult:
        return PaginationResult(
            clients=tuple(clients),
            inventory_complete=False,
            scan_result="partial" if pages_fetched else "failed",
            pages_fetched=pages_fetched,
            controller_total_rows=controller_total,
            failure_reason=reason,
        )

    while True:
        if shutdown_event is not None and shutdown_event.is_set():
            return finish("shutdown_requested")
        if budget_deadline is not None and time.monotonic() >= budget_deadline:
            return finish("scan_budget_exceeded")
        if pages_fetched >= max_pages:
            return finish("max_pages_exceeded")
        if len(clients) >= max_clients:
            return finish("max_clients_reached_before_total")

        result = provider.list_active_clients(
            site_id=site_id,
            page=page,
            page_size=page_size,
            timeout_seconds=request_timeout_seconds,
        )
        if not result.success:
            return finish(str(result.error or result.message or "page_request_failed"))
        if not isinstance(result.data, dict):
            return finish("result_data_not_object")

        page_clients = result.data.get("clients")
        total_rows = result.data.get("total_rows")
        if type(total_rows) is not int or total_rows < 0:
            return finish("invalid_total_rows")
        if not isinstance(page_clients, list):
            return finish("result.data.clients_not_list")

        if controller_total is None:
            controller_total = total_rows
        elif total_rows != controller_total:
            return finish("total_rows_changed")

        remaining_capacity = max_clients - len(clients)
        if len(page_clients) > remaining_capacity:
            clients.extend(copy.deepcopy(page_clients[:remaining_capacity]))
            pages_fetched += 1
            return finish("max_clients_reached_before_total")

        clients.extend(copy.deepcopy(page_clients))
        pages_fetched += 1

        if len(clients) > controller_total:
            return finish("row_count_exceeds_total")
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
            return finish("empty_page_before_total")
        if len(page_clients) < page_size:
            return finish("short_page_before_total")

        page += 1
