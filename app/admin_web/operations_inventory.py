"""Code-owned Operations inventory and privileged startup bindings (V1)."""

from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Mapping

MANIFEST_PATH = "/etc/captiveportal/admin-db-services-v1.json"
MANIFEST_MAX_BYTES = 32768
APPROVED_ROOTS = ("/opt/CaptivePortal/data", "/var/lib/captive-portal/fingerprint-sensor")
SERVICE_INTENTS = frozenset({"run", "disabled", "maintenance", "unknown"})
STORE_INTENTS = frozenset({"expected", "optional_disabled", "unknown"})


@dataclass(frozen=True)
class Service:
    id: str
    unit: str
    label: str
    role: str


@dataclass(frozen=True)
class Store:
    id: str
    filename: str
    label: str
    purpose: str
    writers: tuple[str, ...]
    services: tuple[str, ...]
    kind: str
    readers: tuple[str, ...] = ()


SERVICES = (
    Service("portal_core", "captive-portal.service", "CaptivPortal Core", "Guest Auth, CAPPORT, Admin and in-process workers"),
    Service("fingerprint_evidence", "fingerprint-evidence.service", "Fingerprint Evidence", "Direct-TLS fingerprint evidence ingress and writer"),
    Service("fingerprint_sensor", "fingerprint-sensor.service", "Fingerprint Sensor", "Passive fingerprint sensor, durable spool and network attribution"),
    Service("fingerprint_suricata", "fingerprint-suricata.service", "Fingerprint Suricata", "TLS/QUIC capture for fingerprint evidence"),
    Service("fingerprint_classification", "fingerprint-classification.service", "Fingerprint Classification", "Post-auth fingerprint integration and classification worker"),
    Service("network_metadata", "network-metadata.service", "Network Metadata", "NI-01 durable network metadata ingestion"),
    Service("network_metadata_projection", "network-metadata-projection.service", "Network Metadata Projection", "NI-02B device-relative projection and late binding"),
    Service("network_service_recognition", "network-service-recognition.service", "Network Service Recognition", "NI-04 background materialized service intelligence"),
    Service("traffic_projection", "traffic-projection.service", "Traffic Projection", "Derived historical traffic projection worker"),
)
STORES = (
    Store("portal_counter", "portal_counter.db", "Portal Counter", "Durable authorization counter", ("portal_counter",), ("portal_core",), "operational_counter"),
    Store("public_traffic", "public_traffic.sqlite3", "Public Traffic", "Completed-session traffic counter", ("public_traffic",), ("portal_core",), "operational_counter"),
    Store("visitor_registry", "visitor_registry.sqlite3", "Visitor Registry", "Device and identity registry", ("visitor_registry",), ("portal_core",), "authoritative", ("network_metadata_projection", "fingerprint_classification")),
    Store("visits", "visits.sqlite3", "Visits", "Visits, offline facts and durable reader checkpoint", ("visit_lifecycle",), ("portal_core",), "authoritative", ("fingerprint_classification",)),
    Store("observations", "observations.sqlite3", "Observations", "Historical client and AP observations", ("observation_foundation",), ("portal_core",), "authoritative", ("traffic_projection",)),
    Store("current_state", "current_state.sqlite3", "Current State", "Current and recent materialized snapshots", ("current_state",), ("portal_core",), "materialized_snapshot"),
    Store("traffic_projection", "traffic_projection.sqlite3", "Traffic Projection", "Derived historical traffic", ("traffic_projection",), ("traffic_projection",), "derived"),
    Store("fingerprint_evidence", "device_fingerprint_evidence.sqlite3", "Fingerprint Evidence", "Normalized evidence and source health", ("fingerprint_evidence",), ("fingerprint_evidence",), "authoritative", ("fingerprint_classification",)),
    Store("fingerprint_classification", "device_fingerprint_classification.sqlite3", "Fingerprint Classification", "Persisted classification output", ("fingerprint_classification",), ("fingerprint_classification",), "materialized_snapshot"),
    Store("fingerprint_control_plane", "device_fingerprint_control_plane.sqlite3", "Fingerprint Control Plane", "Protected admission and activation configuration", ("fingerprint_control_plane",), (), "configuration", ("fingerprint_classification",)),
    Store("fingerprint_integration", "device_fingerprint_integration.sqlite3", "Fingerprint Integration", "Durable post-auth integration jobs and links", ("fingerprint_integration_submitter", "fingerprint_integration_worker"), ("portal_core", "fingerprint_classification"), "durable_queue", ("fingerprint_classification",)),
    Store("network_metadata", "network_metadata.sqlite3", "Network Metadata", "Durable network metadata and checkpoints", ("network_metadata",), ("network_metadata",), "authoritative", ("network_metadata_projection", "network_service_recognition")),
    Store("network_attribution", "network_attribution.sqlite3", "Network Attribution", "Trusted temporal DHCP attribution", ("network_attribution",), ("fingerprint_sensor",), "authoritative", ("network_metadata_projection",)),
    Store("network_metadata_projection", "network_metadata_projection.sqlite3", "Network Metadata Projection", "Device-relative edges and pending attribution", ("network_metadata_projection",), ("network_metadata_projection",), "derived", ("network_service_recognition",)),
    Store("network_service_intelligence", "network_service_intelligence.sqlite3", "Network Service Intelligence", "Materialized recognized services", ("network_service_recognition",), ("network_service_recognition",), "materialized_snapshot"),
    Store("settings", "settings.sqlite3", "Settings", "Protected global configuration generations", ("settings_control",), ("portal_core",), "configuration"),
    Store("sensor_spool", "spool.sqlite3", "Sensor Spool", "Durable Sensor delivery queue", ("fingerprint_sensor_spool",), ("fingerprint_sensor",), "durable_queue"),
)


@dataclass(frozen=True)
class TopologyNode:
    id: str
    node_type: str
    label: str
    catalog_ref: str | None
    group: str


@dataclass(frozen=True)
class TopologyEdge:
    from_node_id: str
    relation: str
    to_node_id: str

    def dto(self):
        return dict(id=f"e:{self.from_node_id}:{self.relation}:{self.to_node_id}",
            from_node_id=self.from_node_id, to_node_id=self.to_node_id,
            relation=self.relation, flow_evidence="not_instrumented")


TOPOLOGY_SOURCES = (
    TopologyNode("src:guest_http", "source", "Guest Portal / Auth", None, "portal_guest"),
    TopologyNode("src:omada_controller", "source", "Omada Controller", None, "portal_guest"),
    TopologyNode("src:visit_webhook_journal", "source", "Visit Webhook Journal", None, "portal_guest"),
    TopologyNode("src:passive_capture", "source", "Passive Capture", None, "fingerprint"),
)
SERVICE_GROUPS = ("portal_guest", "fingerprint", "fingerprint", "fingerprint", "fingerprint",
    "network_intelligence", "network_intelligence", "network_intelligence", "traffic_analytics")
STORE_GROUPS = ("portal_guest",)*6 + ("traffic_analytics",) + ("fingerprint",)*4 + (
    "network_intelligence", "fingerprint", "network_intelligence", "network_intelligence", "portal_guest", "fingerprint")
TOPOLOGY_CONSUMER = TopologyNode("consumer:admin_read_models", "consumer", "Admin Read Models", None, "portal_guest")

# Explicit, source-verified triples: never expand ownership/reader metadata.
TOPOLOGY_EDGES = (
    TopologyEdge("src:guest_http", "feeds", "svc:portal_core"),
    TopologyEdge("src:omada_controller", "feeds", "svc:portal_core"),
    TopologyEdge("src:visit_webhook_journal", "feeds", "svc:portal_core"),
    TopologyEdge("src:passive_capture", "feeds", "svc:fingerprint_sensor"),
    TopologyEdge("src:passive_capture", "feeds", "svc:fingerprint_suricata"),
    TopologyEdge("svc:fingerprint_suricata", "feeds", "svc:fingerprint_sensor"),
    TopologyEdge("svc:fingerprint_suricata", "feeds", "svc:network_metadata"),
    TopologyEdge("svc:fingerprint_sensor", "feeds", "svc:fingerprint_evidence"),
    TopologyEdge("svc:portal_core", "writes_to", "db:portal_counter"),
    TopologyEdge("svc:portal_core", "writes_to", "db:public_traffic"),
    TopologyEdge("svc:portal_core", "writes_to", "db:visitor_registry"),
    TopologyEdge("svc:portal_core", "writes_to", "db:visits"),
    TopologyEdge("svc:portal_core", "writes_to", "db:observations"),
    TopologyEdge("svc:portal_core", "writes_to", "db:current_state"),
    TopologyEdge("svc:portal_core", "writes_to", "db:settings"),
    TopologyEdge("svc:portal_core", "writes_to", "db:fingerprint_integration"),
    TopologyEdge("svc:traffic_projection", "writes_to", "db:traffic_projection"),
    TopologyEdge("svc:fingerprint_evidence", "writes_to", "db:fingerprint_evidence"),
    TopologyEdge("svc:fingerprint_classification", "writes_to", "db:fingerprint_classification"),
    TopologyEdge("svc:fingerprint_classification", "writes_to", "db:fingerprint_integration"),
    TopologyEdge("svc:fingerprint_sensor", "writes_to", "db:network_attribution"),
    TopologyEdge("svc:fingerprint_sensor", "writes_to", "db:sensor_spool"),
    TopologyEdge("svc:network_metadata", "writes_to", "db:network_metadata"),
    TopologyEdge("svc:network_metadata_projection", "writes_to", "db:network_metadata_projection"),
    TopologyEdge("svc:network_service_recognition", "writes_to", "db:network_service_intelligence"),
    TopologyEdge("db:observations", "read_by", "svc:traffic_projection"),
    TopologyEdge("db:network_metadata", "read_by", "svc:network_metadata_projection"),
    TopologyEdge("db:network_attribution", "read_by", "svc:network_metadata_projection"),
    TopologyEdge("db:visitor_registry", "read_by", "svc:network_metadata_projection"),
    TopologyEdge("db:network_metadata_projection", "read_by", "svc:network_service_recognition"),
    TopologyEdge("db:network_metadata", "read_by", "svc:network_service_recognition"),
    TopologyEdge("db:fingerprint_integration", "read_by", "svc:fingerprint_classification"),
    TopologyEdge("db:fingerprint_evidence", "read_by", "svc:fingerprint_classification"),
    TopologyEdge("db:fingerprint_control_plane", "read_by", "svc:fingerprint_classification"),
    TopologyEdge("db:visitor_registry", "read_by", "svc:fingerprint_classification"),
    TopologyEdge("db:visits", "read_by", "svc:fingerprint_classification"),
    TopologyEdge("db:visits", "read_by", "consumer:admin_read_models"),
    TopologyEdge("db:observations", "read_by", "consumer:admin_read_models"),
    TopologyEdge("db:visitor_registry", "read_by", "consumer:admin_read_models"),
    TopologyEdge("db:current_state", "read_by", "consumer:admin_read_models"),
    TopologyEdge("db:fingerprint_classification", "read_by", "consumer:admin_read_models"),
    TopologyEdge("db:fingerprint_evidence", "read_by", "consumer:admin_read_models"),
    TopologyEdge("db:network_metadata_projection", "read_by", "consumer:admin_read_models"),
    TopologyEdge("db:network_service_intelligence", "read_by", "consumer:admin_read_models"),
    TopologyEdge("db:traffic_projection", "read_by", "consumer:admin_read_models"),
)


def topology_snapshot():
    """Pure projection, called only by the enabled authorized read boundary."""
    from dataclasses import asdict
    nodes = (*TOPOLOGY_SOURCES,
        *(TopologyNode("svc:"+item.id, "service", item.label, item.id, group) for item, group in zip(SERVICES, SERVICE_GROUPS)),
        *(TopologyNode("db:"+item.id, "database", item.label, item.id, group) for item, group in zip(STORES, STORE_GROUPS)),
        TOPOLOGY_CONSUMER)
    if len(nodes) != 31 or len(nodes) > 40 or len(TOPOLOGY_EDGES) != 45 or len(TOPOLOGY_EDGES) > 64:
        raise InventoryUnavailable()
    return dict(contract_version="admin.operations.topology.v1", scope="global", mode="structural_only",
        nodes=[asdict(node) for node in nodes], edges=[edge.dto() for edge in TOPOLOGY_EDGES])


class InventoryUnavailable(ValueError):
    """Deliberately contains no path, source data or exception text."""

    def __init__(self):
        super().__init__("inventory_unavailable")


@dataclass(frozen=True)
class Inventory:
    service_intents: Mapping[str, str]
    store_intents: Mapping[str, str]
    paths: Mapping[str, str]


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InventoryUnavailable()
        result[key] = value
    return result


def _reject_constant(_value):
    raise InventoryUnavailable()


def parse_inventory(raw: bytes) -> Inventory:
    """Pure strict binding validation; no runtime path fallback."""
    try:
        if len(raw) > MANIFEST_MAX_BYTES:
            raise InventoryUnavailable()
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_reject_constant)
        if type(data) is not dict or set(data) != {"schema_version", "services", "databases"}:
            raise InventoryUnavailable()
        if data["schema_version"] != "admin.db-services.bindings.v1":
            raise InventoryUnavailable()
        intents, paths = {}, {}
        for key, catalog, allowed in (("services", SERVICES, SERVICE_INTENTS), ("databases", STORES, STORE_INTENTS)):
            items = data[key]
            if type(items) is not list or len(items) != len(catalog):
                raise InventoryUnavailable()
            known = {item.id for item in catalog}
            values = {}
            for item in items:
                expected_keys = {"id", "intent"} | ({"path"} if key == "databases" else set())
                if type(item) is not dict or set(item) != expected_keys:
                    raise InventoryUnavailable()
                identity, intent = item["id"], item["intent"]
                if type(identity) is not str or identity not in known or identity in values:
                    raise InventoryUnavailable()
                if type(intent) is not str or intent not in allowed:
                    raise InventoryUnavailable()
                values[identity] = intent
                if key == "databases":
                    value = item["path"]
                    if type(value) is not str or len(value) > 512 or any(ord(c) < 32 or ord(c) == 127 for c in value):
                        raise InventoryUnavailable()
                    path = PurePosixPath(value)
                    if (not path.is_absolute() or path.as_posix() != value or ".." in path.parts
                            or (str(path.parent) not in APPROVED_ROOTS and not (
                                identity == "fingerprint_evidence"
                                and str(path.parent) == "/opt/CaptivePortal/data/evidence"))
                            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", path.name) is None
                            or value in paths.values()):
                        raise InventoryUnavailable()
                    paths[identity] = value
            intents[key] = MappingProxyType(values)
        return Inventory(intents["services"], intents["databases"], MappingProxyType(paths))
    except (UnicodeError, ValueError, TypeError, RecursionError):
        raise InventoryUnavailable() from None


def _trusted_directory(path: Path) -> None:
    # Validate all fixed ancestors, not a directory listing or discovery.
    for parent in (path, *path.parents):
        metadata = parent.lstat()
        if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != 0 or metadata.st_mode & 0o022:
            raise InventoryUnavailable()


def load_inventory() -> Inventory:
    """Read exactly the fixed privileged manifest once at composition."""
    descriptor = None
    try:
        if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
            raise InventoryUnavailable()
        path = Path(MANIFEST_PATH)
        _trusted_directory(path.parent)
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        metadata = os.fstat(descriptor)
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != 0
                or metadata.st_mode & 0o022 or metadata.st_size > MANIFEST_MAX_BYTES):
            raise InventoryUnavailable()
        raw = bytearray()
        while len(raw) <= MANIFEST_MAX_BYTES:
            chunk = os.read(descriptor, min(4096, MANIFEST_MAX_BYTES + 1 - len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
        inventory = parse_inventory(bytes(raw))
        for root in APPROVED_ROOTS:
            for directory in (Path(root), *Path(root).parents):
                if not stat.S_ISDIR(directory.lstat().st_mode):
                    raise InventoryUnavailable()
        return inventory
    except (OSError, ValueError):
        raise InventoryUnavailable() from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
