from __future__ import annotations

import hashlib
from dataclasses import FrozenInstanceError

import pytest

from app.observations.models import ObservationValidationError
from app.observations.read_service import ObservationReadService

from .conftest import ap_row, client_row, radio_row


START = "2026-01-01T00:00:00.000Z"
END = "2026-01-01T23:59:59.999Z"


def create_cycle(repository, identifier, kind, site="site-a", *, complete=True):
    repository.create_cycle(
        kind=kind,
        site_id=site,
        started_at=START,
        cycle_id=identifier,
    )
    if complete:
        repository.finalize_cycle(
            identifier,
            finished_at="2026-01-01T00:10:00.000Z",
            complete=True,
            result="success",
        )


def test_client_history_filters_site_and_cursor_without_gap(repository):
    for site, cycle in (("site-a", "a"), ("site-b", "b")):
        create_cycle(repository, cycle, "client", site)
        repository.insert_client_batch([
            client_row(
                cycle,
                "2026-01-01T00:00:01.000Z",
                site_id=site,
                client_mac="AA:BB:CC:DD:EE:01",
            ),
            client_row(
                cycle,
                "2026-01-01T00:00:01.000Z",
                site_id=site,
                client_mac="AA:BB:CC:DD:EE:02",
                ssid="Other",
                radio_id=0,
            ),
            client_row(
                cycle,
                "2026-01-01T00:00:02.000Z",
                site_id=site,
                client_mac="AA:BB:CC:DD:EE:03",
            ),
        ])

    service = ObservationReadService(repository)
    first = service.get_site_client_observations(
        "site-a", START, END, limit=2
    )
    second = service.get_site_client_observations(
        "site-a", START, END, limit=2, cursor=first.next_cursor
    )
    combined = first.items + second.items
    assert [item.client_mac for item in combined] == [
        "AA:BB:CC:DD:EE:01",
        "AA:BB:CC:DD:EE:02",
        "AA:BB:CC:DD:EE:03",
    ]
    assert first.next_cursor is not None
    assert second.next_cursor is None
    assert {item.site_id for item in combined} == {"site-a"}

    filtered = service.get_site_client_observations(
        "site-a",
        START,
        END,
        ssid="Other",
        radio_id=0,
    )
    assert [item.client_mac for item in filtered.items] == [
        "AA:BB:CC:DD:EE:02"
    ]


def test_client_history_and_latest_are_immutable(repository):
    create_cycle(repository, "client", "client")
    repository.insert_client_batch([
        client_row("client", "2026-01-01T00:00:01.000Z", hostname="phone")
    ])
    service = ObservationReadService(repository)
    item = service.get_latest_client_observation(
        "site-a", "aa-bb-cc-dd-ee-01"
    )
    assert item.client_mac == "AA:BB:CC:DD:EE:01"
    assert item.data["hostname"] == "phone"
    with pytest.raises(FrozenInstanceError):
        item.ssid = "changed"
    with pytest.raises(TypeError):
        item.data["hostname"] = "changed"


def test_running_and_abandoned_cycles_are_excluded_but_filterable(repository):
    create_cycle(repository, "running", "client", complete=False)
    repository.insert_client_batch([
        client_row("running", "2026-01-01T00:00:01.000Z")
    ])
    service = ObservationReadService(repository)
    assert service.get_latest_client_observation(
        "site-a", "AA:BB:CC:DD:EE:01"
    ) is None
    running = service.get_latest_client_observation(
        "site-a",
        "AA:BB:CC:DD:EE:01",
        cycle_states=("running",),
    )
    assert running is not None

    repository.initialize("2026-01-02T00:00:00.000Z")
    assert service.get_latest_client_observation(
        "site-a",
        "AA:BB:CC:DD:EE:01",
        cycle_states=("abandoned",),
    ) is not None


def test_ap_radio_and_latest_complete_config_queries(repository):
    create_cycle(repository, "ap-dynamic", "ap_dynamic")
    repository.insert_ap_batch([(
        ap_row(
            "ap-dynamic",
            "2026-01-01T00:00:05.000Z",
            cpu_util=12.5,
        ),
        [
            radio_row("2026-01-01T00:00:04.000Z", band="2.4GHz"),
            radio_row("2026-01-01T00:00:04.500Z", band="5GHz"),
        ],
    )])
    create_cycle(repository, "config-1", "ap_config")
    payload = '{"name":"AP-1"}'
    repository.insert_ap_config_batch([{
        "cycle_id": "config-1",
        "captured_at": "2026-01-01T00:05:00.000Z",
        "site_id": "site-a",
        "ap_mac": "10:20:30:40:50:60",
        "config_sha256": hashlib.sha256(payload.encode()).hexdigest(),
        "schema_version": 1,
        "config_json": payload,
    }])
    # A later complete cycle without a row represents a partial AP attempt;
    # it must not replace the latest complete config.
    create_cycle(repository, "config-partial", "ap_config")

    service = ObservationReadService(repository)
    ap = service.get_latest_ap_observation(
        "site-a", "10-20-30-40-50-60"
    )
    assert ap.data["cpu_util"] == 12.5
    radios = service.get_latest_ap_radio_observations(
        "site-a", "10:20:30:40:50:60"
    )
    assert [row.band for row in radios] == ["2.4GHz", "5GHz"]
    history = service.get_ap_radio_observations(
        "site-a",
        "10:20:30:40:50:60",
        START,
        END,
        band="5GHz",
    )
    assert [row.band for row in history.items] == ["5GHz"]
    config = service.get_latest_ap_config(
        "site-a", "10:20:30:40:50:60"
    )
    assert config.cycle_id == "config-1"
    assert config.config_json == payload


def test_latest_ap_radios_are_ranked_per_band_in_sql(repository):
    for index in range(4):
        cycle_id = f"ap-{index}"
        create_cycle(repository, cycle_id, "ap_dynamic")
        repository.insert_ap_batch([(
            ap_row(
                cycle_id,
                f"2026-01-01T00:00:0{index}.000Z",
            ),
            [
                radio_row(
                    f"2026-01-01T00:00:0{index}.100Z",
                    band="2.4GHz",
                    actual_channel=index + 1,
                ),
                radio_row(
                    f"2026-01-01T00:00:0{index}.200Z",
                    band="5GHz",
                    actual_channel=36 + index,
                ),
            ],
        )])

    statements = []
    original_read_connection = repository.read_connection

    class ConnectionProxy:
        def __init__(self, connection):
            self._connection = connection

        def execute(self, statement, parameters=()):
            statements.append(statement)
            return self._connection.execute(statement, parameters)

    class ReadConnectionProxy:
        def __enter__(self):
            self._context = original_read_connection()
            return ConnectionProxy(self._context.__enter__())

        def __exit__(self, exc_type, exc_value, traceback):
            return self._context.__exit__(exc_type, exc_value, traceback)

    repository.read_connection = ReadConnectionProxy
    radios = ObservationReadService(
        repository
    ).get_latest_ap_radio_observations(
        "site-a", "10:20:30:40:50:60"
    )

    assert [(row.band, row.data["actual_channel"]) for row in radios] == [
        ("2.4GHz", 4),
        ("5GHz", 39),
    ]
    assert all("latest_rank" not in row.data for row in radios)
    normalized_sql = " ".join(statements[0].lower().split())
    assert "row_number() over" in normalized_sql
    assert "partition by o.band" in normalized_sql
    assert "latest_rank = 1" in normalized_sql


def test_latest_ap_config_requires_complete_completed_cycle(repository):
    complete_payload = '{"name":"complete"}'
    incomplete_payload = '{"name":"incomplete"}'

    create_cycle(repository, "config-complete", "ap_config")
    repository.insert_ap_config_batch([{
        "cycle_id": "config-complete",
        "captured_at": "2026-01-01T00:01:00.000Z",
        "site_id": "site-a",
        "ap_mac": "10:20:30:40:50:60",
        "config_sha256": hashlib.sha256(
            complete_payload.encode()
        ).hexdigest(),
        "schema_version": 1,
        "config_json": complete_payload,
    }])

    create_cycle(
        repository,
        "config-incomplete",
        "ap_config",
        complete=False,
    )
    repository.insert_ap_config_batch([{
        "cycle_id": "config-incomplete",
        "captured_at": "2026-01-01T00:02:00.000Z",
        "site_id": "site-a",
        "ap_mac": "10:20:30:40:50:60",
        "config_sha256": hashlib.sha256(
            incomplete_payload.encode()
        ).hexdigest(),
        "schema_version": 1,
        "config_json": incomplete_payload,
    }])
    repository.finalize_cycle(
        "config-incomplete",
        finished_at="2026-01-01T00:10:00.000Z",
        complete=False,
        result="partial",
    )

    config = ObservationReadService(repository).get_latest_ap_config(
        "site-a", "10:20:30:40:50:60"
    )
    assert config is not None
    assert config.cycle_id == "config-complete"
    assert config.config_json == complete_payload


@pytest.mark.parametrize(
    "call",
    [
        lambda service: service.get_client_observations(
            "", "AA:BB:CC:DD:EE:01", START, END
        ),
        lambda service: service.get_client_observations(
            "site-a", "not-a-mac", START, END
        ),
        lambda service: service.get_client_observations(
            "site-a", "AA:BB:CC:DD:EE:01", "bad", END
        ),
        lambda service: service.get_client_observations(
            "site-a", "AA:BB:CC:DD:EE:01", END, START
        ),
        lambda service: service.get_client_observations(
            "site-a", "AA:BB:CC:DD:EE:01", START, END, limit=2001
        ),
        lambda service: service.get_client_observations(
            "site-a",
            "AA:BB:CC:DD:EE:01",
            START,
            END,
            cursor="not-a-cursor",
        ),
        lambda service: service.get_latest_client_observation(
            "site-a",
            "AA:BB:CC:DD:EE:01",
            cycle_states=("invalid",),
        ),
    ],
)
def test_query_validation_is_explicit(repository, call):
    with pytest.raises(ObservationValidationError):
        call(ObservationReadService(repository))
