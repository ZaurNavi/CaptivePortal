"""Closed optional Service Recognition Extension V1 over exact fresh Core V2."""
from app.network_metadata.validation import ni_timestamp
from .models import ProjectionUnavailable

TABLES = {
    "projection_service_recognition_extension_meta":
        "singleton_id INTEGER PRIMARY KEY CHECK(singleton_id=1), "
        "extension_contract_version INTEGER NOT NULL CHECK(extension_contract_version=1), "
        "installed_at_utc TEXT NOT NULL",
    "projection_service_recognition_feed":
        "feed_seq INTEGER PRIMARY KEY AUTOINCREMENT, edge_id TEXT NOT NULL UNIQUE, "
        "committed_at_utc TEXT NOT NULL, FOREIGN KEY(edge_id) "
        "REFERENCES device_network_metadata_edges(edge_id) ON DELETE CASCADE",
    "projection_registry_binding_change_index":
        "change_seq INTEGER PRIMARY KEY AUTOINCREMENT, site_id TEXT NOT NULL, client_mac TEXT NOT NULL, "
        "binding_state TEXT NOT NULL CHECK(binding_state='authoritative'), device_id TEXT NOT NULL, "
        "evaluated_at_utc TEXT NOT NULL, UNIQUE(site_id,client_mac), "
        "FOREIGN KEY(site_id,client_mac) REFERENCES projection_site_mac_bindings(site_id,client_mac) ON DELETE CASCADE",
}


def create_extension_objects(connection):
    """Internal DDL primitive; installation owner must hold the writer lock."""
    for name, ddl in TABLES.items():
        connection.execute(f"CREATE TABLE {name} ({ddl})")


def validate_extension_metadata(connection):
    rows = connection.execute("SELECT * FROM projection_service_recognition_extension_meta").fetchall()
    if len(rows) != 1 or tuple(rows[0])[:2] != (1, 1):
        raise ProjectionUnavailable()
    ni_timestamp(rows[0][2], canonical=True)


def append_candidate(connection, edge, committed_at):
    if (edge["device_endpoint_role"] == "src" and edge["direction"] == "outbound"
            and edge["peer_scope"] == "external" and edge["source_event_family"] in {"dns", "tls", "quic"}
            and edge["projection_contract_version"] == 2
            and edge["attribution_state"] == "resolved"
            and edge["peer_attribution_state"] == "not_applicable_outside_guest_scope"):
        connection.execute(
            "INSERT INTO projection_service_recognition_feed(edge_id,committed_at_utc) VALUES(?,?)",
            (edge["edge_id"], committed_at))


def maintain_authoritative_change(connection, old, *, site, mac, state, device, evaluated_at):
    if state != "authoritative":
        connection.execute(
            "DELETE FROM projection_registry_binding_change_index WHERE site_id=? AND client_mac=?", (site, mac))
    elif old is None or old["binding_state"] != "authoritative" or old["device_id"] != device:
        connection.execute(
            "DELETE FROM projection_registry_binding_change_index WHERE site_id=? AND client_mac=?", (site, mac))
        connection.execute(
            "INSERT INTO projection_registry_binding_change_index"
            "(site_id,client_mac,binding_state,device_id,evaluated_at_utc) VALUES(?,?,'authoritative',?,?)",
            (site, mac, device, evaluated_at))


def install_service_recognition_extension(repository):
    """Explicit one-time install by the already locked NI-02B writer only."""
    from .schema import validate_schema
    from .validation import timestamp
    connection = repository.connection
    if connection is None or repository._writer_fd is None or connection.in_transaction:
        raise ProjectionUnavailable()
    if validate_schema(connection, integrity=True) == "CORE_PLUS_EXTENSION_V1":
        repository.service_recognition_extension_present = True
        return False
    with repository.transaction():
        for name, ddl in TABLES.items():
            connection.execute(f"CREATE TABLE {name} ({ddl})")
            repository.crash_point("extension_created_" + name)
        connection.execute(
            "INSERT INTO projection_registry_binding_change_index"
            "(site_id,client_mac,binding_state,device_id,evaluated_at_utc) "
            "SELECT site_id,client_mac,binding_state,device_id,last_evaluated_at "
            "FROM projection_site_mac_bindings WHERE binding_state='authoritative' "
            "ORDER BY site_id,client_mac")
        repository.crash_point("extension_seeded_bindings")
        connection.execute("INSERT INTO projection_service_recognition_extension_meta VALUES(1,1,?)",
                           (timestamp(repository.clock()),))
        repository.crash_point("extension_inserted_metadata")
        if validate_schema(connection, integrity=True) != "CORE_PLUS_EXTENSION_V1":
            raise ProjectionUnavailable()
        repository.crash_point("extension_validated")
    repository.service_recognition_extension_present = True
    return True
