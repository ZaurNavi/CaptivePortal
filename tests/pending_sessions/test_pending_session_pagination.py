from app.models import Result
from app.pending_sessions import paginate_site_inventory


class FakeProvider:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def list_active_clients(
        self,
        *,
        site_id,
        page,
        page_size,
        timeout_seconds,
    ):
        self.calls.append(
            {
                "site_id": site_id,
                "page": page,
                "page_size": page_size,
                "timeout_seconds": timeout_seconds,
            }
        )
        return self.results.pop(0)


class SetEvent:
    def is_set(self):
        return True


def ok(clients, total):
    return Result.ok(data={"clients": clients, "total_rows": total})


def paginate(provider, **overrides):
    values = {
        "site_id": "site-1",
        "page_size": 2,
        "max_pages": 10,
        "max_clients": 100,
        "request_timeout_seconds": 5.0,
    }
    values.update(overrides)
    return paginate_site_inventory(provider, **values)


def test_two_page_inventory_success():
    provider = FakeProvider(
        [
            ok([{"mac": "1"}, {"mac": "2"}], 3),
            ok([{"mac": "3"}], 3),
        ]
    )

    result = paginate(provider)

    assert result.inventory_complete is True
    assert result.scan_result == "success"
    assert result.pages_fetched == 2
    assert result.controller_total_rows == 3
    assert result.clients == ({"mac": "1"}, {"mac": "2"}, {"mac": "3"})
    assert [call["page"] for call in provider.calls] == [1, 2]


def test_max_clients_is_a_hard_cap_even_inside_page():
    provider = FakeProvider(
        [ok([{"mac": "1"}, {"mac": "2"}, {"mac": "3"}], 10)]
    )

    result = paginate(provider, page_size=3, max_clients=2)

    assert len(result.clients) == 2
    assert result.clients == ({"mac": "1"}, {"mac": "2"})
    assert result.inventory_complete is False
    assert result.scan_result == "partial"
    assert result.failure_reason == "max_clients_reached_before_total"


def test_pagination_returns_defensive_copy():
    source = [{"nested": {"value": 1}}]
    provider = FakeProvider([ok(source, 1)])

    result = paginate(provider)

    source[0]["nested"]["value"] = 999
    assert result.clients[0]["nested"]["value"] == 1


def test_total_rows_change_is_rejected():
    provider = FakeProvider(
        [
            ok([{"mac": "1"}, {"mac": "2"}], 3),
            ok([{"mac": "3"}], 4),
        ]
    )

    result = paginate(provider)

    assert result.inventory_complete is False
    assert result.scan_result == "partial"
    assert result.failure_reason == "total_rows_changed"


def test_empty_page_before_total_is_partial():
    provider = FakeProvider([ok([], 2)])

    result = paginate(provider)

    assert result.inventory_complete is False
    assert result.scan_result == "partial"
    assert result.failure_reason == "empty_page_before_total"


def test_provider_failure_before_first_page_is_failed():
    provider = FakeProvider([Result.fail(error="HTTP_ERROR", message="request failed")])

    result = paginate(provider)

    assert result.inventory_complete is False
    assert result.scan_result == "failed"
    assert result.pages_fetched == 0
    assert result.failure_reason == "HTTP_ERROR"


def test_shutdown_before_first_request_is_failed_without_provider_call():
    provider = FakeProvider([])

    result = paginate(provider, shutdown_event=SetEvent())

    assert result.scan_result == "failed"
    assert result.failure_reason == "shutdown_requested"
    assert provider.calls == []


def test_max_pages_stops_incomplete_inventory():
    provider = FakeProvider([ok([{"mac": "1"}, {"mac": "2"}], 4)])

    result = paginate(provider, max_pages=1)

    assert result.scan_result == "partial"
    assert result.pages_fetched == 1
    assert result.failure_reason == "max_pages_exceeded"
