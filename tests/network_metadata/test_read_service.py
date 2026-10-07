import pytest
from app.network_metadata.read_service import NetworkMetadataReadService
from app.network_metadata.models import NetworkMetadataValidationError
from app.network_metadata.retention import RetentionPolicy
from . import store, outcome, record, source_event, SITE

START, END = "2026-10-07T00:00:00.000000Z", "2026-10-08T00:00:00.000000Z"


def test_keyset_order_site_isolation_and_privacy(tmp_path):
    data = record()
    with store(tmp_path, source=(data + b"\n") * 3) as state:
        items = [outcome(state.config.capture_scope_binding, data, start=index * (len(data) + 1),
            generation=state.generation.source_generation_id) for index in range(3)]
        state.repo.ingest_batch(items, state.run, state.health, state.anchor)
        reader = NetworkMetadataReadService(state.config.db_path)
        first = reader.list_observations(SITE, START, END, limit=2)
        second = reader.list_observations(SITE, START, END, cursor=first["next_cursor"], limit=2)
        ids = [item["observation_id"] for item in first["items"] + second["items"]]
        assert ids == sorted(ids) and len(set(ids)) == 3 and second["next_cursor"] is None
        assert reader.list_observations("f" * 24, START, END)["items"] == []
        rendered = repr(first)
        for sentinel in ("ni-query-sentinel", "203.0.113.93", "10.73.0.7", "2001:db8::93", "query_type", "source_record_sha256"):
            assert sentinel not in rendered
        state.clock.advance(days=15)
        RetentionPolicy(state.repo).run()
        assert reader.list_observations(SITE, START, END)["items"][0]["sensitive_endpoint_presence_state"] == "expired"


@pytest.mark.parametrize("arguments", [{"limit": True}, {"limit": 0}, {"limit": 501}, {"family": "flow"},
    {"cursor": [START, "id"]}, {"cursor": ("2026-10-09T00:00:00.000000Z", "id")}])
def test_invalid_read_arguments(tmp_path, arguments):
    with store(tmp_path) as state:
        with pytest.raises(NetworkMetadataValidationError):
            NetworkMetadataReadService(state.config.db_path).list_observations(SITE, START, END, **arguments)


@pytest.mark.parametrize("start,end", [(END, START), (START, START), ("2026-10-07T00:00:00Z", END),
    (START, "2026-11-08T00:00:00.000000Z")])
def test_read_window(tmp_path, start, end):
    with pytest.raises(NetworkMetadataValidationError):
        NetworkMetadataReadService(str(tmp_path / "absent")).list_observations(SITE, start, end)


@pytest.mark.parametrize("family", ["tls", "quic"])
def test_family_projection_no_sni(tmp_path, family):
    data = record(source_event(family))
    with store(tmp_path, source=data + b"\n") as state:
        state.repo.ingest_batch([outcome(state.config.capture_scope_binding, data, generation=state.generation.source_generation_id)],
                               state.run, state.health, state.anchor)
        item = NetworkMetadataReadService(state.config.db_path).list_observations(SITE, START, END, family=family)["items"][0]
        assert "sni" not in item["family_data"]
        if family == "tls":
            assert item["family_data"]["client_alpns"] == ["h2", "h2"]
