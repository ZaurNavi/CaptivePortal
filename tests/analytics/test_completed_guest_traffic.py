from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import pytest

from app.analytics.completed_guest_traffic import (
    CompletedGuestSessionTrafficIntegrityUnavailable,
    CompletedGuestSessionTrafficReadService,
    CompletedGuestSessionTrafficValidationError,
)
from app.analytics.source_gateway import AnalyticsSourceUnavailable


SITE = "a" * 24
OTHER_SITE = "b" * 24
VISIT = "11111111-1111-4111-8111-111111111111"
START = "2026-09-05T09:55:00.000Z"
CLOSED = "2026-09-05T10:00:00.000Z"
NOW = "2026-09-05T10:05:00.000Z"


def _visit(**overrides):
    row = dict(
        visit_id=VISIT,
        site_id=SITE,
        client_mac="AA:BB:CC:DD:EE:01",
        started_at=START,
        closed_at=CLOSED,
        duration_seconds=300,
        status="closed",
        start_ssid="Zefer_Parki",
        final_ssid="Zefer_Parki",
        start_ap_mac="AA:BB:CC:DD:EE:10",
        final_ap_mac="AA:BB:CC:DD:EE:11",
    )
    row.update(overrides)
    return row


def _sample(row_id, observed_at, *, uptime, down, up, ssid="Zefer_Parki", ap=None):
    return dict(
        visit_id=VISIT,
        row_id=row_id,
        cycle_id=f"cycle-{row_id}",
        observed_at=observed_at,
        site_id=SITE,
        client_mac="AA:BB:CC:DD:EE:01",
        ssid=ssid,
        ap_mac=ap or "AA:BB:CC:DD:EE:10",
        uptime=uptime,
        traffic_down=down,
        traffic_up=up,
        source_inventory_complete=1,
        cycle_kind="client",
        cycle_state="completed",
        cycle_result="success",
        cycle_complete=1,
    )


def _complete_samples():
    return [
        _sample(1, "2026-09-05T09:55:30.000Z", uptime=100, down=1000, up=2000),
        _sample(2, "2026-09-05T09:56:30.000Z", uptime=160, down=1500, up=2200,
                ap="AA:BB:CC:DD:EE:11"),
        _sample(3, "2026-09-05T09:59:30.000Z", uptime=340, down=1500, up=2200),
    ]


class Gateway:
    def __init__(self, visits=None, samples=None, boundaries=(), *, fail=None):
        self.visits = [_visit()] if visits is None else list(visits)
        self.samples = _complete_samples() if samples is None else list(samples)
        self.boundaries = list(boundaries)
        self.fail = fail
        self.calls = []

    def completed_visit_page(self, **kwargs):
        self.calls.append(("visits", kwargs))
        if self.fail == "visits":
            raise AnalyticsSourceUnavailable("private")
        return self.visits[: kwargs["limit"]]

    def completed_visit_authorization_boundaries_batch(self, **kwargs):
        self.calls.append(("authorizations", kwargs))
        if self.fail == "authorizations":
            raise AnalyticsSourceUnavailable("private")
        return self.boundaries

    def completed_visit_traffic_evidence_batch(self, **kwargs):
        self.calls.append(("observations", kwargs))
        if self.fail == "observations":
            raise AnalyticsSourceUnavailable("private")
        return self.samples


def _read(gateway, **kwargs):
    return CompletedGuestSessionTrafficReadService(gateway).get_completed_guest_session_traffic(
        SITE, range_id="24h", evaluated_at_utc=NOW, **kwargs
    )


def test_positive_zero_and_ap_roam_are_complete_sampled_evidence():
    gateway = Gateway()
    result = _read(gateway)
    item = result.items[0]
    assert result.status == "ok"
    assert item.observed_download_bytes == 500
    assert item.observed_upload_bytes == 200
    assert item.observed_total_bytes == 700
    assert item.accepted_download_interval_count == 2
    assert item.accepted_upload_interval_count == 2
    assert item.traffic_evidence_status == "complete"
    assert item.evidence_reason_codes == ()
    with pytest.raises(FrozenInstanceError):
        item.observed_total_bytes = 0


def test_accepted_zero_is_numeric_not_missing():
    result = _read(Gateway(samples=[
        _sample(1, "2026-09-05T09:55:30.000Z", uptime=1, down=0, up=0),
        _sample(2, "2026-09-05T09:57:30.000Z", uptime=121, down=0, up=0),
        _sample(3, "2026-09-05T09:59:30.000Z", uptime=241, down=0, up=0),
    ]))
    assert result.items[0].observed_download_bytes == 0
    assert result.items[0].observed_upload_bytes == 0
    assert result.items[0].observed_total_bytes == 0


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"uptime": 100}, "continuity_frozen"),
        ({"uptime": 99}, "connection_reset"),
        ({"uptime": None}, "continuity_unproven"),
        ({"ssid": "Other"}, "ssid_transition"),
        ({"ssid": None}, "ssid_unproven"),
        ({"traffic_down": None}, "counter_missing"),
        ({"traffic_down": 999}, "counter_reset"),
    ],
)
def test_interval_rejections_are_explicit_and_directions_are_independent(changes, reason):
    first = _sample(1, "2026-09-05T09:55:30.000Z", uptime=100, down=1000, up=2000)
    second = _sample(2, "2026-09-05T09:56:30.000Z", uptime=160, down=1500, up=2200)
    second.update(changes)
    item = _read(Gateway(samples=[first, second])).items[0]
    assert reason in item.evidence_reason_codes
    if reason in {"counter_missing", "counter_reset"}:
        assert item.observed_download_bytes is None
        assert item.observed_upload_bytes == 200
        assert item.traffic_evidence_status == "partial"
    else:
        assert item.observed_download_bytes is None
        assert item.observed_upload_bytes is None
        assert item.traffic_evidence_status == "insufficient_data"


def test_authorization_boundary_rejects_crossing_interval_but_later_resumes():
    gateway = Gateway(
        samples=_complete_samples(),
        boundaries=[{
            "visit_id": VISIT,
            "row_id": 10,
            "authorized_at": "2026-09-05T09:56:00.000Z",
        }],
    )
    item = _read(gateway).items[0]
    assert item.observed_download_bytes == 0
    assert item.observed_upload_bytes == 0
    assert item.accepted_download_interval_count == 1
    assert "authorization_boundary" in item.evidence_reason_codes
    assert item.traffic_evidence_status == "partial"


def test_gap_edges_and_no_samples_have_frozen_quality():
    item = _read(Gateway(samples=[
        _sample(1, "2026-09-05T09:58:10.000Z", uptime=1, down=1, up=1),
        _sample(2, "2026-09-05T09:59:20.000Z", uptime=71, down=2, up=2),
    ])).items[0]
    assert "start_edge_uncovered" in item.evidence_reason_codes
    assert item.traffic_evidence_status == "partial"

    gap = _read(Gateway(samples=[
        _sample(1, "2026-09-05T09:55:30.000Z", uptime=1, down=1, up=1),
        _sample(2, "2026-09-05T09:58:31.000Z", uptime=182, down=2, up=2),
    ])).items[0]
    assert "gap_too_large" in gap.evidence_reason_codes
    assert gap.traffic_evidence_status == "insufficient_data"

    empty = _read(Gateway(samples=[])).items[0]
    assert empty.evidence_reason_codes == ("no_usable_interval",)
    assert empty.traffic_evidence_status == "insufficient_data"


def test_long_visit_is_visible_but_skips_all_observation_reads():
    gateway = Gateway(visits=[_visit(
        started_at="2026-09-04T09:59:59.000Z", duration_seconds=86401
    )])
    result = _read(gateway)
    assert result.status == "partial"
    assert result.source_health.observations == "not_required"
    assert result.items[0].traffic_evidence_status == "unavailable"
    assert result.items[0].evidence_reason_codes == (
        "attribution_window_exceeds_supported_max",
    )
    assert [name for name, _ in gateway.calls] == ["visits"]


def test_root_rollup_distinguishes_uniform_and_mixed_item_evidence():
    insufficient = _read(Gateway(samples=[]))
    assert insufficient.status == "insufficient_data"
    assert insufficient.items[0].traffic_evidence_status == "insufficient_data"

    long_visit = _visit(
        visit_id="00000000-0000-4000-8000-000000000002",
        started_at="2026-09-04T08:59:00.000Z",
        closed_at="2026-09-05T09:59:00.000Z",
        duration_seconds=90_000,
    )
    mixed_without_numeric = _read(Gateway(
        visits=[_visit(), long_visit],
        samples=[],
    ))
    assert [item.traffic_evidence_status for item in mixed_without_numeric.items] == [
        "insufficient_data", "unavailable",
    ]
    assert mixed_without_numeric.status == "partial"
    assert mixed_without_numeric.source_health.observations == "healthy"

    mixed_with_complete = _read(Gateway(
        visits=[_visit(), long_visit],
        samples=_complete_samples(),
    ))
    assert [item.traffic_evidence_status for item in mixed_with_complete.items] == [
        "complete", "unavailable",
    ]
    assert mixed_with_complete.status == "partial"


def test_source_unavailable_root_contracts_are_independent():
    visits = _read(Gateway(fail="visits"))
    assert visits.status == "unavailable"
    assert visits.items == ()
    assert visits.source_health.visits == "unavailable"
    assert visits.source_health.observations == "not_required"

    observations = _read(Gateway(fail="observations"))
    assert observations.status == "partial"
    assert observations.source_health.visits == "healthy"
    assert observations.source_health.observations == "unavailable"
    assert observations.items[0].observed_total_bytes is None


def test_empty_cohort_does_not_touch_authorization_or_observation_sources():
    gateway = Gateway(visits=[])
    result = _read(gateway)
    assert result.status == "ok"
    assert result.items == ()
    assert result.source_health.observations == "not_required"
    assert [name for name, _ in gateway.calls] == ["visits"]


def test_completion_cohort_cursor_is_range_pinned_and_server_recomputed():
    second = _visit(
        visit_id="00000000-0000-4000-8000-000000000002",
        closed_at="2026-09-05T09:59:00.000Z",
    )
    gateway = Gateway(visits=[_visit(), second], samples=[])
    first = _read(gateway, limit=1)
    assert first.page.next_cursor is not None
    next_page = _read(gateway, limit=1, cursor=first.page.next_cursor)
    visit_call = next(item for item in gateway.calls if item[0] == "visits" and item[1]["after"])
    assert visit_call[1]["after"] == (first.items[0].closed_at, first.items[0].visit_id)

    raw = first.page.next_cursor + "=" * (-len(first.page.next_cursor) % 4)
    import base64
    payload = json.loads(base64.urlsafe_b64decode(raw))
    payload["absolute_from_utc"] = "2026-09-04T10:05:01.000Z"
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=").decode()
    with pytest.raises(CompletedGuestSessionTrafficValidationError):
        _read(gateway, limit=1, cursor=encoded)
    with pytest.raises(CompletedGuestSessionTrafficValidationError):
        CompletedGuestSessionTrafficReadService(gateway).get_completed_guest_session_traffic(
            OTHER_SITE, range_id="24h", cursor=first.page.next_cursor
        )


def test_cross_site_or_persisted_counter_integrity_fails_closed():
    with pytest.raises(CompletedGuestSessionTrafficIntegrityUnavailable):
        _read(Gateway(visits=[_visit(site_id=OTHER_SITE)]))
    malformed = _complete_samples()
    malformed[0]["traffic_down"] = "1000"
    with pytest.raises(CompletedGuestSessionTrafficIntegrityUnavailable):
        _read(Gateway(samples=malformed))
