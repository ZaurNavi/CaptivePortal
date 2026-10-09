"""Bounded real Registry trust/authority tracing; disposable inputs only."""
import sqlite3

import pytest

from app.network_metadata_projection.models import ProjectionConflict, RegistryEvaluation
from app.network_metadata_projection.registry_adapter import RegistryAdapter
from tests.visitor_registry.test_device_registry import make_stack, append_event, event_for
from .support import stack, source_record, SITE, MAC, OTHER_MAC


def test_real_500_row_reconciliation_one_trust_probe(tmp_path, monkeypatch, record_property):
    (tmp_path / "registry").mkdir()
    config, _, registry_repository, reader, _ = make_stack(tmp_path / "registry")
    macs = tuple("02:10:00:" + ":".join(f"{part:02X}" for part in number.to_bytes(3, "big")) for number in range(500))
    for number, mac in enumerate(macs):
        append_event(config.source_log_path, event_for(session_id=f"synthetic-{number}", mac=mac))
    assert reader.scan().complete
    (tmp_path / "projection").mkdir()
    value = stack(tmp_path / "projection")
    try:
        now = "2026-10-09T12:00:00.000000Z"
        with value.repo.transaction():
            for mac in macs:
                value.repo._registry_binding(SITE, mac, RegistryEvaluation("not_yet_registry_resolved"),
                    value.service.run_id, now, edge_at=now)
        adapter = RegistryAdapter(config.db_path)
        value.service.registry = adapter
        statements, probes, authority_calls = [], [], []
        connect, probe, point = sqlite3.connect, adapter._trust_probe, adapter.reader.get_device_by_mac
        def traced_connect(*args, **kwargs):
            connection = connect(*args, **kwargs)
            connection.set_trace_callback(statements.append)
            return connection
        def counted_probe():
            probes.append(True)
            return probe()
        def counted_point(mac):
            authority_calls.append(mac)
            return point(mac)
        monkeypatch.setattr(sqlite3, "connect", traced_connect)
        monkeypatch.setattr(adapter, "_trust_probe", counted_probe)
        monkeypatch.setattr(adapter.reader, "get_device_by_mac", counted_point)
        value.service.reconcile()
        assert len(probes) == 1
        assert len(authority_calls) == 500 and set(authority_calls) == set(macs)
        assert all(value.repo.binding(SITE, mac)["binding_state"] == "authoritative" for mac in macs)
        for pragma in ("quick_check", "foreign_key_check", "integrity_check"):
            count = sum(sql.lower().startswith("pragma " + pragma) for sql in statements)
            record_property("registry_500_row_" + pragma + "_count", count)
            assert count == 0
        record_property("registry_trust_probes_per_500_row_pass", len(probes))
        record_property("registry_exact_authority_point_reads", len(authority_calls))
        assert sum(sql.lower() == "pragma user_version" for sql in statements) == 1
        assert not any("group by" in sql.lower() or "from reader_state" in sql.lower() for sql in statements)
        assert all(registry_repository.get_device_by_mac(mac) is not None for mac in macs)
    finally:
        value.repo.close()


def test_initial_new_site_mac_evaluations_use_one_batch(tmp_path):
    value = stack(tmp_path, [source_record(), source_record(1, site_id="f" * 24)])
    try:
        value.service.poll()
        assert value.registry.batches == [(MAC, OTHER_MAC)]
        assert value.registry.calls == [MAC, OTHER_MAC]
        assert value.repo.binding(SITE, MAC) is not None
        assert value.repo.binding("f" * 24, MAC) is not None
    finally:
        value.repo.close()


@pytest.mark.parametrize("damage", ["PRAGMA user_version=2", "DROP INDEX idx_visitor_devices_last_seen",
    "UPDATE registry_state SET state='unavailable'", "DELETE FROM registry_state"])
def test_batch_untrusted_registry_returns_unavailable_without_authority_reads(tmp_path, monkeypatch, damage):
    config, _, _, _, _ = make_stack(tmp_path)
    with sqlite3.connect(config.db_path) as connection:
        connection.execute(damage)
    adapter = RegistryAdapter(config.db_path)
    def forbidden(*args):
        pytest.fail("untrusted Registry reached authority lookup")
    monkeypatch.setattr(adapter.reader, "get_device_by_mac", forbidden)
    assert {item.state for item in adapter.evaluate_many((MAC, OTHER_MAC)).values()} == {"registry_unavailable"}


def test_unreadable_registry_batch_is_safe(tmp_path):
    path = tmp_path / "invalid.sqlite3"
    path.write_bytes(b"not a SQLite database")
    before = path.read_bytes()
    assert {item.state for item in RegistryAdapter(str(path)).evaluate_many((MAC, OTHER_MAC)).values()} == {"registry_unavailable"}
    assert path.read_bytes() == before


def test_individual_point_failure_and_returned_identity_validation(tmp_path, monkeypatch):
    config, _, _, _, _ = make_stack(tmp_path)
    adapter = RegistryAdapter(config.db_path)
    def point(mac):
        if mac == MAC:
            raise sqlite3.OperationalError("private Registry exception")
        return {"mac": mac, "device_id": "00000000-0000-4000-8000-000000000123", "updated_at": None,
            "last_ip": "ignored", "last_site_id": "ignored"}
    monkeypatch.setattr(adapter.reader, "get_device_by_mac", point)
    results = adapter.evaluate_many((MAC, OTHER_MAC))
    assert results[MAC] == RegistryEvaluation("registry_unavailable", reason="registry_unavailable")
    assert results[OTHER_MAC].state == "authoritative"
    monkeypatch.setattr(adapter.reader, "get_device_by_mac", lambda mac: {"mac": OTHER_MAC, "device_id": "invalid"})
    with pytest.raises(ProjectionConflict, match="registry_identity_conflict"):
        adapter.evaluate(MAC)
    monkeypatch.setattr(adapter.reader, "get_device_by_mac", lambda mac: {"mac": mac, "device_id": "invalid"})
    assert adapter.evaluate(MAC).state == "registry_unavailable"


def test_stop_between_registry_points_does_not_commit_reconciliation(tmp_path, monkeypatch):
    config, _, _, _, _ = make_stack(tmp_path)
    value = stack(tmp_path)
    try:
        with value.repo.transaction():
            for mac in (MAC, OTHER_MAC):
                value.repo._registry_binding(SITE, mac, RegistryEvaluation("not_yet_registry_resolved"),
                    value.service.run_id, "2026-10-09T12:00:00.000000Z", edge_at="2026-10-09T12:00:00.000000Z")
        before = value.repo.connection.total_changes
        adapter = RegistryAdapter(config.db_path)
        value.service.registry = adapter
        calls = []
        def point(mac):
            calls.append(mac)
            value.service.stop_event.set()
            return None
        monkeypatch.setattr(adapter.reader, "get_device_by_mac", point)
        value.service.reconcile()
        assert len(calls) == 1
        assert value.repo.connection.total_changes == before
    finally:
        value.repo.close()
