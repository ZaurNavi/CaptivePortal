"""Bounded protected NI-04 delivery/identity interfaces; upstream read-only."""
from dataclasses import dataclass
from app.device_fingerprint.validation import validate_site_id
from app.network_attribution.validation import canonical_mac
from app.network_metadata.validation import canonical_uuid, digest, integer, ip, ni_timestamp, text
from app.network_metadata.canonical import observation_uuid, source_event_identity
from .models import ProjectionUnavailable, ProjectionValidationError, ALGORITHM
from .read_service import DeviceNetworkMetadataReadService
from .recognition_read_service import RecognitionProjectionEdgeFactV1
from .validation import edge_id, semantic_digest, read_window
from .effective_runtime_state import effective_runtime_state


@dataclass(frozen=True, slots=True, repr=False)
class RecognitionIdentityV1:
    site_id: str
    client_mac: str
    device_id: str | None
    binding_state: str
    registry_binding_change_seq: int | None


@dataclass(frozen=True, slots=True, repr=False)
class RecognitionFeedEntryV1:
    feed_seq: int
    committed_at_utc: str
    fact: RecognitionProjectionEdgeFactV1
    identity: RecognitionIdentityV1


@dataclass(frozen=True, slots=True)
class RecognitionFeedBoundsV1:
    min_retained_feed_seq: int | None
    max_feed_seq: int | None


@dataclass(frozen=True, slots=True, repr=False)
class AuthoritativeBindingChangeV1:
    change_seq: int
    site_id: str
    client_mac: str
    device_id: str
    evaluated_at_utc: str


@dataclass(frozen=True, slots=True, repr=False)
class RecognitionDeviceCoverageV1:
    projection_runtime_state: str
    projection_safe_reason: str | None
    identity_binding_state: str
    bound_device_id: str | None
    device_linked_pending_count: int


@dataclass(frozen=True, slots=True, repr=False)
class RecognitionCandidateV1:
    fact: RecognitionProjectionEdgeFactV1
    identity: RecognitionIdentityV1


_IDENTITY_JOIN = (
    " LEFT JOIN projection_site_mac_bindings b ON b.site_id=e.site_id AND b.client_mac=e.client_mac"
    " LEFT JOIN projection_registry_identities r ON r.device_id=b.device_id"
    " LEFT JOIN projection_registry_binding_change_index c ON c.site_id=b.site_id AND c.client_mac=b.client_mac")
_IDENTITY_COLUMNS = (
    "b.binding_state AS joined_binding_state,b.device_id AS joined_device_id,"
    "c.change_seq AS joined_change_seq,c.device_id AS change_device_id,r.client_mac AS registry_mac")


class ServiceRecognitionDeliveryReadService(DeviceNetworkMetadataReadService):
    @staticmethod
    def _cursor(after, limit, maximum):
        try:
            integer(after)
            integer(limit, 1, maximum)
        except Exception:
            raise ProjectionValidationError() from None

    @staticmethod
    def _require_extension(connection):
        if connection.execute("SELECT 1 FROM projection_service_recognition_extension_meta WHERE singleton_id=1").fetchone() is None:
            raise ProjectionUnavailable()

    @staticmethod
    def _identity(site, mac, row):
        validate_site_id(site)
        if canonical_mac(mac) != mac:
            raise ValueError
        state, device, change = row["joined_binding_state"], row["joined_device_id"], row["joined_change_seq"]
        if state not in {"authoritative", "not_yet_registry_resolved", "registry_unavailable"}:
            raise ValueError
        if state == "authoritative":
            canonical_uuid(device)
            integer(change, 1)
            if row["registry_mac"] != mac or row["change_device_id"] != device:
                raise ValueError
        elif device is not None or change is not None:
            raise ValueError
        return RecognitionIdentityV1(site, mac, device, state, change)

    @classmethod
    def _candidate(cls, row):
        metadata = {"delivery_seq", "delivery_time", "joined_binding_state", "joined_device_id",
                    "joined_change_seq", "change_device_id", "registry_mac"}
        edge = {key: value for key, value in dict(row).items() if key not in metadata}
        if (edge["device_endpoint_role"] != "src" or edge["direction"] != "outbound"
                or edge["peer_scope"] != "external" or edge["source_event_family"] not in {"dns", "tls", "quic"}
                or edge["attribution_state"] != "resolved" or edge["attribution_source"] != "trusted_dhcp_v4"
                or edge["network_scope_state"] != "within_intended_scope"
                or edge["projection_contract_version"] != 2
                or edge["projection_algorithm_version"] != ALGORITHM
                or edge["peer_attribution_state"] != "not_applicable_outside_guest_scope"
                or edge["peer_attribution_binding_id"] is not None):
            raise ValueError
        canonical_uuid(edge["source_generation_id"], 4)
        canonical_uuid(edge["source_observation_ref"], 5)
        integer(edge["record_start_byte_offset"])
        event_identity = source_event_identity(edge["source_generation_id"], edge["record_start_byte_offset"])
        if (edge["source_event_identity"] != event_identity
                or edge["source_observation_ref"] != observation_uuid(edge["source_event_family"], event_identity)
                or edge["edge_id"] != edge_id(edge["source_observation_ref"], "src")
                or edge["edge_semantic_digest"] != semantic_digest(edge)):
            raise ValueError
        for key in ("event_at", "source_ingested_at", "projected_at"):
            ni_timestamp(edge[key], canonical=True)
        canonical_uuid(edge["attribution_binding_id"], 4)
        instant = ni_timestamp(edge["event_at"], canonical=True)
        if not ni_timestamp(edge["attribution_valid_from"]) <= instant < ni_timestamp(edge["attribution_valid_until"]):
            raise ValueError
        digest(edge["capture_scope_binding_digest"])
        for key in ("capture_source_id", "network_scope_id"):
            text(edge[key], 128, controls=True)
        for prefix in ("device", "peer"):
            address, port = edge[prefix + "_ip"], edge[prefix + "_port"]
            if address is not None and ip(address) != address:
                raise ValueError
            if port is not None:
                integer(port, 0, 65535)
        if edge["device_ip"] is None or edge["transport_protocol"] not in {None, "TCP", "UDP"}:
            raise ValueError
        identity = cls._identity(edge["site_id"], edge["client_mac"], row)
        fact = RecognitionProjectionEdgeFactV1(**{key: edge[key] for key in RecognitionProjectionEdgeFactV1.__dataclass_fields__})
        return fact, identity

    def recognition_feed_bounds(self, *, deadline):
        with self._snapshot(deadline=deadline) as connection:
            self._require_extension(connection)
            first = connection.execute("SELECT feed_seq FROM projection_service_recognition_feed ORDER BY feed_seq LIMIT 1").fetchone()
            sequence = connection.execute("SELECT seq FROM sqlite_sequence WHERE name='projection_service_recognition_feed'").fetchone()
            floor, high = first[0] if first else None, sequence[0] if sequence else None
            try:
                for value in (floor, high):
                    if value is not None:
                        integer(value, 1)
                if floor is not None and (high is None or floor > high):
                    raise ValueError
            except Exception:
                raise ProjectionUnavailable() from None
            # Lifetime committed highwater remains observable even after all
            # retained feed rows cascade away. Never reset a consumer to zero.
            return RecognitionFeedBoundsV1(floor, high)

    def read_service_recognition_feed(self, after_feed_seq, *, limit=256, deadline):
        self._cursor(after_feed_seq, limit, 256)
        with self._snapshot(deadline=deadline) as connection:
            self._require_extension(connection)
            rows = connection.execute(
                "SELECT e.*,f.feed_seq AS delivery_seq,f.committed_at_utc AS delivery_time," + _IDENTITY_COLUMNS +
                " FROM projection_service_recognition_feed f LEFT JOIN device_network_metadata_edges e ON e.edge_id=f.edge_id" +
                _IDENTITY_JOIN + " WHERE f.feed_seq>? ORDER BY f.feed_seq LIMIT ?", (after_feed_seq, limit)).fetchall()
            try:
                values = []
                for row in rows:
                    deadline.require_remaining()
                    integer(row["delivery_seq"], after_feed_seq + 1)
                    ni_timestamp(row["delivery_time"], canonical=True)
                    fact, identity = self._candidate(row)
                    values.append(RecognitionFeedEntryV1(row["delivery_seq"], row["delivery_time"], fact, identity))
                return tuple(values)
            except Exception:
                raise ProjectionUnavailable() from None

    def read_authoritative_binding_changes(self, after_change_seq, *, limit=128, deadline):
        self._cursor(after_change_seq, limit, 128)
        with self._snapshot(deadline=deadline) as connection:
            self._require_extension(connection)
            rows = connection.execute(
                "SELECT c.*,b.binding_state AS current_state,b.device_id AS current_device_id,"
                "r.client_mac AS registry_mac FROM projection_registry_binding_change_index c "
                "LEFT JOIN projection_site_mac_bindings b ON b.site_id=c.site_id AND b.client_mac=c.client_mac "
                "LEFT JOIN projection_registry_identities r ON r.device_id=b.device_id "
                "WHERE c.change_seq>? ORDER BY c.change_seq LIMIT ?", (after_change_seq, limit)).fetchall()
            try:
                values = []
                for row in rows:
                    deadline.require_remaining()
                    integer(row["change_seq"], after_change_seq + 1)
                    validate_site_id(row["site_id"])
                    canonical_uuid(row["device_id"])
                    if (canonical_mac(row["client_mac"]) != row["client_mac"]
                            or row["binding_state"] != "authoritative" or row["current_state"] != "authoritative"
                            or row["current_device_id"] != row["device_id"] or row["registry_mac"] != row["client_mac"]):
                        raise ValueError
                    ni_timestamp(row["evaluated_at_utc"], canonical=True)
                    values.append(AuthoritativeBindingChangeV1(row["change_seq"], row["site_id"], row["client_mac"],
                                                              row["device_id"], row["evaluated_at_utc"]))
                return tuple(values)
            except Exception:
                raise ProjectionUnavailable() from None

    @staticmethod
    def _requested_identity(site_id, client_mac, device_id=None):
        try:
            validate_site_id(site_id)
            if canonical_mac(client_mac) != client_mac:
                raise ValueError
            if device_id is not None:
                canonical_uuid(device_id)
        except Exception:
            raise ProjectionValidationError() from None

    @classmethod
    def _current_identity(cls, connection, site, mac):
        row = connection.execute(
            "SELECT b.binding_state AS joined_binding_state,b.device_id AS joined_device_id,"
            "c.change_seq AS joined_change_seq,c.device_id AS change_device_id,r.client_mac AS registry_mac "
            "FROM projection_site_mac_bindings b "
            "LEFT JOIN projection_registry_binding_change_index c ON c.site_id=b.site_id AND c.client_mac=b.client_mac "
            "LEFT JOIN projection_registry_identities r ON r.device_id=b.device_id "
            "WHERE b.site_id=? AND b.client_mac=?", (site, mac)).fetchone()
        if row is None:
            return RecognitionIdentityV1(site, mac, None, "absent", None)
        try:
            return cls._identity(site, mac, row)
        except Exception:
            raise ProjectionUnavailable() from None

    def read_current_identity(self, site_id, client_mac, *, deadline):
        self._requested_identity(site_id, client_mac)
        with self._snapshot(deadline=deadline) as connection:
            self._require_extension(connection)
            return self._current_identity(connection, site_id, client_mac)

    def read_recognition_device_coverage(self, site_id, device_id, client_mac, from_utc, to_utc, *, deadline):
        self._requested_identity(site_id, client_mac, device_id)
        read_window(site_id, from_utc, to_utc, 1, None)
        if (ni_timestamp(to_utc, canonical=True) - ni_timestamp(from_utc, canonical=True)).total_seconds() != 86400:
            raise ProjectionValidationError()
        with self._snapshot(deadline=deadline) as connection:
            self._require_extension(connection)
            identity = self._current_identity(connection, site_id, client_mac)
            if identity.binding_state == "authoritative" and identity.device_id != device_id:
                raise ProjectionUnavailable()
            runtime = connection.execute(
                "SELECT runtime_state,safe_reason,last_source_poll_at FROM projection_runtime_state WHERE singleton_id=1").fetchone()
            if runtime is None:
                raise ProjectionUnavailable()
            state, reason = effective_runtime_state(runtime, enabled=self.idle_write_reduction_enabled,
                                                    evaluated_at_utc=self.clock())
            pending = 0
            if identity.binding_state == "authoritative":
                pending = connection.execute(
                    "SELECT count(DISTINCT p.observation_id) "
                    "FROM device_network_metadata_edges e INDEXED BY idx_projection_mac_event "
                    "JOIN projection_pending_attribution p ON p.observation_id=e.source_observation_ref AND p.site_id=e.site_id "
                    "WHERE e.site_id=? AND e.client_mac=? AND e.event_at>=? AND e.event_at<? "
                    "AND p.event_at>=? AND p.event_at<?",
                    (site_id, client_mac, from_utc, to_utc, from_utc, to_utc)).fetchone()[0]
            return RecognitionDeviceCoverageV1(state, reason, identity.binding_state, identity.device_id, pending)

    def read_candidate_sites(self, after_site_id=None, *, limit=128, deadline):
        self._cursor(0, limit, 128)
        if after_site_id is not None:
            try:
                validate_site_id(after_site_id)
            except Exception:
                raise ProjectionValidationError() from None
        with self._snapshot(deadline=deadline) as connection:
            self._require_extension(connection)
            rows = connection.execute(
                "SELECT DISTINCT site_id FROM projection_site_mac_bindings WHERE site_id>? ORDER BY site_id LIMIT ?",
                (after_site_id or "", limit)).fetchall()
            try:
                for row in rows:
                    validate_site_id(row[0])
            except Exception:
                raise ProjectionUnavailable() from None
            return tuple(row[0] for row in rows)

    def read_candidate_page(self, site_id, from_utc, to_utc, *, client_mac=None, cursor=None, limit=128, deadline):
        read_window(site_id, from_utc, to_utc, limit, cursor)
        self._cursor(0, limit, 128)
        if (ni_timestamp(to_utc, canonical=True) - ni_timestamp(from_utc, canonical=True)).total_seconds() > 86400:
            raise ProjectionValidationError()
        if client_mac is not None:
            self._requested_identity(site_id, client_mac)
        index = "idx_projection_mac_event" if client_mac is not None else "idx_projection_site_event"
        predicates, params = ["e.site_id=?"], [site_id]
        if client_mac is not None:
            predicates.append("e.client_mac=?")
            params.append(client_mac)
        predicates.extend(["e.event_at>=?", "e.event_at<?", "e.device_endpoint_role='src'",
                           "e.direction='outbound'", "e.peer_scope='external'"])
        params.extend((from_utc, to_utc))
        if cursor is not None:
            predicates.append("(e.event_at,e.edge_id)>(?,?)")
            params.extend(cursor)
        with self._snapshot(deadline=deadline) as connection:
            self._require_extension(connection)
            rows = connection.execute(
                "SELECT e.*," + _IDENTITY_COLUMNS + " FROM device_network_metadata_edges e INDEXED BY " + index +
                _IDENTITY_JOIN + " WHERE " + " AND ".join(predicates) +
                " ORDER BY e.event_at,e.edge_id LIMIT ?", (*params, limit)).fetchall()
            try:
                result = []
                for row in rows:
                    deadline.require_remaining()
                    fact, identity = self._candidate(row)
                    result.append(RecognitionCandidateV1(fact, identity))
                return tuple(result)
            except Exception:
                raise ProjectionUnavailable() from None
