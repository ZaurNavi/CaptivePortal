"""Additive NI-02B-owned recognition snapshot; NI-03 reader is untouched."""
from dataclasses import dataclass
from app.device_fingerprint.validation import validate_site_id
from app.network_attribution.validation import canonical_mac
from app.network_metadata.validation import canonical_uuid, ni_timestamp, digest, ip, integer, text
from .read_service import DeviceNetworkMetadataReadService
from .models import ProjectionUnavailable, ProjectionValidationError, RUNTIME_STATES
from .effective_runtime_state import effective_runtime_state


@dataclass(frozen=True, slots=True, repr=False)
class RecognitionProjectionEdgeFactV1:
    edge_id: str
    event_at: str
    source_observation_ref: str
    source_event_family: str
    source_generation_id: str
    capture_source_id: str
    network_scope_id: str
    capture_scope_binding_digest: str
    device_endpoint_role: str
    device_ip: str
    device_port: int | None
    peer_ip: str | None
    peer_port: int | None
    transport_protocol: str | None
    peer_scope: str
    direction: str


@dataclass(frozen=True, slots=True, repr=False)
class RecognitionProjectionSnapshotV2:
    schema_version: int
    site_id: str
    device_id: str
    identity_binding_state: str
    projection_runtime_state: str
    projection_safe_reason: str | None
    bound_device_id: str | None
    facts: tuple[RecognitionProjectionEdgeFactV1, ...]
    device_linked_pending_count: int
    historical_window_completeness_claimed: bool = False


class DeviceNetworkMetadataRecognitionReadService(DeviceNetworkMetadataReadService):
    def read_service_recognition_snapshot(self, site_id, device_id, client_mac, from_utc, to_utc,
                                         *, max_rows, deadline):
        try:
            validate_site_id(site_id)
            canonical_uuid(device_id)
            if canonical_mac(client_mac) != client_mac or type(max_rows) is not int or max_rows != 5000:
                raise ValueError
            first, last = ni_timestamp(from_utc, canonical=True), ni_timestamp(to_utc, canonical=True)
            if (last - first).total_seconds() != 86400:
                raise ValueError
        except Exception:
            raise ProjectionValidationError() from None
        with self._snapshot(deadline=deadline) as connection:
            runtime = connection.execute(
                "SELECT runtime_state,safe_reason,last_source_poll_at FROM projection_runtime_state WHERE singleton_id=1").fetchone()
            if runtime is None:
                raise ProjectionUnavailable()
            state, reason = effective_runtime_state(runtime, enabled=self.idle_write_reduction_enabled,
                                                    evaluated_at_utc=self.clock())
            if state not in RUNTIME_STATES:
                raise ProjectionUnavailable()
            binding = connection.execute(
                "SELECT binding_state,device_id FROM projection_site_mac_bindings WHERE site_id=? AND client_mac=?",
                (site_id, client_mac)).fetchone()
            identity = binding[0] if binding else "absent"
            bound = binding[1] if binding else None
            if identity not in {"authoritative", "not_yet_registry_resolved", "registry_unavailable", "absent"}:
                raise ProjectionUnavailable()
            if identity != "authoritative":
                if bound is not None:
                    raise ProjectionUnavailable()
                return RecognitionProjectionSnapshotV2(2, site_id, device_id, identity, state, reason, None, (), 0)
            if bound != device_id:
                raise ProjectionUnavailable()
            registry_identity = connection.execute(
                "SELECT client_mac FROM projection_registry_identities WHERE device_id=?", (bound,)).fetchone()
            if registry_identity is None or registry_identity[0] != client_mac:
                raise ProjectionUnavailable()
            columns = tuple(RecognitionProjectionEdgeFactV1.__dataclass_fields__)
            rows = connection.execute("SELECT " + ",".join(columns) +
                " FROM device_network_metadata_edges INDEXED BY idx_projection_mac_event "
                "WHERE site_id=? AND client_mac=? AND event_at>=? AND event_at<? "
                "AND direction='outbound' AND peer_scope='external' ORDER BY event_at,edge_id LIMIT ?",
                (site_id, client_mac, from_utc, to_utc, max_rows + 1)).fetchall()
            if len(rows) > max_rows:
                raise ProjectionUnavailable()
            facts = []
            try:
                for row in rows:
                    deadline.require_remaining()
                    digest(row["edge_id"])
                    canonical_uuid(row["source_observation_ref"], 5)
                    canonical_uuid(row["source_generation_id"], 4)
                    digest(row["capture_scope_binding_digest"])
                    if row["source_event_family"] not in {"dns", "tls", "quic"} or row["device_endpoint_role"] != "src":
                        raise ValueError
                    if not first <= ni_timestamp(row["event_at"], canonical=True) < last:
                        raise ValueError
                    if ip(row["device_ip"]) != row["device_ip"]:
                        raise ValueError
                    if row["device_port"] is not None:
                        integer(row["device_port"], 0, 65535)
                    if row["peer_ip"] is not None and ip(row["peer_ip"]) != row["peer_ip"]:
                        raise ValueError
                    if row["peer_port"] is not None:
                        integer(row["peer_port"], 0, 65535)
                    if row["transport_protocol"] is not None:
                        if row["transport_protocol"] not in {"TCP", "UDP"}:
                            raise ValueError
                    text(row["capture_source_id"], 128, controls=True)
                    text(row["network_scope_id"], 128, controls=True)
                    facts.append(RecognitionProjectionEdgeFactV1(**dict(row)))
            except (ValueError, TypeError):
                raise ProjectionUnavailable() from None
            # Any committed role edge can link pending to this exact Device.
            # Both-pending/no-edge observations cannot enter this join.
            linked = connection.execute(
                "SELECT DISTINCT p.observation_id FROM device_network_metadata_edges AS e INDEXED BY idx_projection_mac_event "
                "JOIN projection_pending_attribution AS p ON p.observation_id=e.source_observation_ref AND p.site_id=e.site_id "
                "WHERE e.site_id=? AND e.client_mac=? AND e.event_at>=? AND e.event_at<? "
                "AND p.event_at>=? AND p.event_at<? LIMIT ?",
                (site_id, client_mac, from_utc, to_utc, from_utc, to_utc, max_rows + 1)).fetchall()
            if len(linked) > max_rows:
                raise ProjectionUnavailable()
            return RecognitionProjectionSnapshotV2(2, site_id, device_id, identity, state, reason, bound,
                                                   tuple(facts), len(linked))
