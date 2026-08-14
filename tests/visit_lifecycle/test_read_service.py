from __future__ import annotations

import uuid
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from app.visit_lifecycle import (
    VisitLifecycleReadService,
    VisitQueryValidationError,
)

from .conftest import make_request
from .test_repository import _close_visit


def _at(minutes: int) -> datetime:
    return datetime(2026, 8, 13, 10, 0, tzinfo=timezone.utc) + timedelta(
        minutes=minutes
    )


def _stamp(minutes: int) -> str:
    return _at(minutes).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _set_links(repository, visit_id, *, device_id=None):
    with repository._connect() as connection:  # noqa: SLF001
        connection.execute(
            "UPDATE visits SET device_id=? WHERE visit_id=?",
            (device_id, visit_id),
        )


def test_single_lookup_and_site_isolation(visit_service, visit_repository):
    opened = visit_service.submit_authorized(make_request())
    reader = VisitLifecycleReadService(visit_repository)
    assert reader.get_visit("site-a", opened.visit_id).visit_id == opened.visit_id
    assert reader.get_visit("site-b", opened.visit_id) is None
    assert reader.get_open_visit(
        "site-a", "02-11-22-33-44-55"
    ).visit_id == opened.visit_id
    assert reader.get_open_visit("site-b", "02:11:22:33:44:55") is None


def test_half_open_overlap_excludes_visit_closed_at_from(
    visit_service,
    visit_repository,
):
    opened = visit_service.submit_authorized(make_request())
    _close_visit(visit_repository, opened.visit_id)
    reader = VisitLifecycleReadService(visit_repository)
    page = reader.list_visits(
        "site-a",
        "2026-08-13T10:05:00.000Z",
        "2026-08-13T10:10:00.000Z",
    )
    assert page.items == ()
    page = reader.list_visits(
        "site-a",
        "2026-08-13T10:04:59.999Z",
        "2026-08-13T10:10:00.000Z",
    )
    assert [item.visit_id for item in page.items] == [opened.visit_id]


def test_device_history_open_ended_ranges(visit_service, visit_repository):
    device_id = str(uuid.uuid4())
    first = visit_service.submit_authorized(
        make_request(authorized_at=_at(0), client_mac="02:00:00:00:00:01")
    )
    second = visit_service.submit_authorized(
        make_request(authorized_at=_at(20), client_mac="02:00:00:00:00:02")
    )
    _close_visit(visit_repository, first.visit_id)
    _set_links(visit_repository, first.visit_id, device_id=device_id)
    _set_links(visit_repository, second.visit_id, device_id=device_id)
    reader = VisitLifecycleReadService(visit_repository)
    assert [item.visit_id for item in reader.list_device_visits(
        "site-a", device_id, from_utc=_stamp(10)
    ).items] == [second.visit_id]
    assert [item.visit_id for item in reader.list_device_visits(
        "site-a", device_id, to_utc=_stamp(10)
    ).items] == [first.visit_id]


def test_context_filters_include_authorization_evidence(
    visit_service,
    visit_repository,
):
    first = visit_service.submit_authorized(make_request())
    visit_service.submit_authorized(make_request(
        portal_ssid="Later_SSID",
        portal_ap_mac="02:00:00:00:10:10",
        auth_run_number=2,
    ))
    reader = VisitLifecycleReadService(visit_repository)
    kwargs = {
        "site_id": "site-a",
        "from_utc": _stamp(-1),
        "to_utc": _stamp(10),
    }
    assert reader.list_visits(**kwargs, ssid="Later_SSID").items[0].visit_id == (
        first.visit_id
    )
    assert reader.list_visits(
        **kwargs, ap_mac="02-00-00-00-10-10"
    ).items[0].visit_id == first.visit_id
    assert reader.list_visits(**kwargs, status="closed").items == ()


def test_stable_cursor_and_validation(visit_service, visit_repository):
    ids = []
    for index in range(3):
        ids.append(visit_service.submit_authorized(make_request(
            authorized_at=_at(index),
            client_mac=f"02:00:00:00:00:{index + 1:02X}",
        )).visit_id)
    reader = VisitLifecycleReadService(visit_repository)
    first = reader.list_open_visits("site-a", limit=2)
    assert [item.visit_id for item in first.items] == ids[::-1][:2]
    assert first.next_cursor
    second = reader.list_open_visits(
        "site-a", limit=2, cursor=first.next_cursor
    )
    assert [item.visit_id for item in second.items] == [ids[0]]
    with pytest.raises(VisitQueryValidationError, match="cursor"):
        reader.list_open_visits("site-a", cursor="not-a-cursor")
    with pytest.raises(VisitQueryValidationError, match="limit"):
        reader.list_open_visits("site-a", limit=2001)
    with pytest.raises(VisitQueryValidationError):
        reader.list_visits("site-a", _stamp(10), _stamp(0))


def test_unmatched_query_uses_processed_at_and_excludes_other_results(
    visit_repository,
):
    with visit_repository._connect() as connection:  # noqa: SLF001
        for index, result in enumerate(("unmatched", "pending_match", "invalid")):
            connection.execute(
                """
                INSERT INTO visit_source_events (
                    event_id, event_type, site_id, client_mac,
                    source_identity, source_offset_start, source_offset_end,
                    processing_result, reason, first_processed_at,
                    processed_at, pending_until
                ) VALUES (?, 'omada.client_offline', 'site-a',
                          '02:11:22:33:44:55', 'dev:inode', ?, ?, ?,
                          'no_open_visit', ?, ?, ?)
                """,
                (
                    f"event:{index}", index, index + 1, result,
                    _stamp(1), _stamp(index + 1),
                    _stamp(30) if result == "pending_match" else None,
                ),
            )
    reader = VisitLifecycleReadService(visit_repository)
    page = reader.list_unmatched_events(
        "site-a", _stamp(0), _stamp(10), reason="no_open_visit"
    )
    assert [item.event_id for item in page.items] == ["event:0"]
    with pytest.raises(FrozenInstanceError):
        page.items[0].reason = "changed"


def test_observation_window_is_pure_immutable_dto(
    visit_service,
    visit_repository,
):
    opened = visit_service.submit_authorized(make_request())
    reader = VisitLifecycleReadService(visit_repository)
    window = reader.observation_window("site-a", opened.visit_id)
    assert window.site_id == "site-a"
    assert window.client_mac == "02:11:22:33:44:55"
    assert window.to_utc is None
    with pytest.raises(FrozenInstanceError):
        window.to_utc = _stamp(10)
