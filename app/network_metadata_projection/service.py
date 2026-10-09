"""Bounded offline projection/retry/reconciliation loop, upstream read-only."""
import ipaddress
import threading
import time
from datetime import timedelta
from types import SimpleNamespace
from app.device_fingerprint.validation import parse_utc
from app.network_metadata.validation import ni_timestamp, canonical_uuid
from app.network_metadata.canonical import observation_uuid, source_event_identity
from app.network_attribution.models import NetworkMetadataAttributionResultV1
from app.network_attribution.validation import canonical_mac
from .models import (ALGORITHM, ATTRIBUTION_STATES, ProjectionConflict, ProjectionError,
                     ProjectionUnavailable, RegistryEvaluation)
from .models import NetworkMetadataProjectionResultV1, PreparedDisposition
from .validation import edge_id, semantic_digest, timestamp


class NetworkMetadataProjectionService:
    def __init__(self, config, repository, source, attribution, registry, identity, *, telemetry=None,
                 stop_event=None, monotonic=time.monotonic):
        self.config, self.repository, self.source = config, repository, source
        self.attribution, self.registry, self.identity = attribution, registry, identity
        self.telemetry, self.stop_event, self.monotonic = telemetry, stop_event or threading.Event(), monotonic
        self.run_id = None
        self.last_retry = self.last_reconcile = self.last_retention = None

    def emit(self, event, **fields):
        if self.telemetry is not None:
            self.telemetry.emit(event, **fields)

    def stop(self):
        self.stop_event.set()

    def startup(self):
        if not self.config.enabled:
            return False
        self.repository.initialize()
        self.run_id = self.repository.create_run(self.identity)
        return True

    @staticmethod
    def _source_identity(source):
        try:
            expected = source_event_identity(source.source_generation_id, source.record_start_byte_offset)
            if (source.source_event_identity != expected or source.observation_id != observation_uuid(source.source_event_family, expected)):
                raise ValueError
        except Exception:
            raise ProjectionConflict("source_observation_identity_conflict") from None

    def _eligible(self, source):
        cutoff = self.repository.clock() - timedelta(days=14)
        return (source.sensitive_endpoint_presence_state == "observed_retained"
                and ni_timestamp(source.event_at, canonical=True) >= cutoff
                and ni_timestamp(source.ingested_at, canonical=True) >= cutoff)

    def _resolve(self, source, role, horizon):
        result = NetworkMetadataAttributionResultV1
        address = getattr(source, role + "_ip")
        if address is None:
            return result("endpoint_absent")
        if ipaddress.ip_address(address).version != 4:
            return result("unsupported_address_family")
        if horizon.state != "available":
            return result("unavailable", "authority_horizon_unavailable")
        instant = ni_timestamp(source.event_at, canonical=True)
        if instant < max(parse_utc(horizon.first_usable_at), parse_utc(horizon.retained_from)):
            return result("outside_historical_horizon")
        try:
            value = self.attribution.resolve_ipv4(source.site_id, address, source.event_at)
        except Exception:
            return result("unavailable", "attribution_store_unavailable")
        if value.state not in ATTRIBUTION_STATES or value.state == "invalid":
            raise ProjectionConflict("attribution_query_contract_invalid")
        if value.state == "resolved":
            try:
                if (value.site_id != source.site_id or value.ipv4 != address or value.event_at != source.event_at
                        or value.attribution_source != "trusted_dhcp_v4" or canonical_mac(value.client_mac) != value.client_mac):
                    raise ValueError
                canonical_uuid(value.binding_id, 4)
                if not parse_utc(value.valid_from) <= instant < parse_utc(value.valid_until):
                    raise ValueError
            except Exception:
                raise ProjectionConflict("attribution_query_contract_invalid") from None
            if not any(ipaddress.IPv4Address(address) in ipaddress.IPv4Network(cidr) for cidr in source.capture_scope_ipv4_cidrs):
                raise ProjectionConflict("resolved_endpoint_outside_capture_scope")
        return value

    def _edge(self, source, role, own, peer):
        other = "dst" if role == "src" else "src"
        address = getattr(source, other + "_ip")
        scope = "unknown"
        if address is not None and ipaddress.ip_address(address).version == 4:
            scope = "local" if any(ipaddress.IPv4Address(address) in ipaddress.IPv4Network(cidr)
                                     for cidr in source.capture_scope_ipv4_cidrs) else "external"
        edge = dict(edge_id=edge_id(source.observation_id, role), schema_version=1, site_id=source.site_id,
            client_mac=own.client_mac, event_at=source.event_at, source_ingested_at=source.ingested_at,
            projected_at=timestamp(self.repository.clock()), device_endpoint_role=role,
            device_ip=getattr(source, role + "_ip"), device_port=getattr(source, role + "_port"), peer_ip=address,
            peer_port=None if address is None else getattr(source, other + "_port"), transport_protocol=source.transport_protocol,
            peer_scope=scope, direction="local" if scope == "local" else ("outbound" if role == "src" else "inbound") if scope == "external" else "unknown",
            source_observation_ref=source.observation_id, source_event_identity=source.source_event_identity,
            source_event_family=source.source_event_family, source_generation_id=source.source_generation_id,
            record_start_byte_offset=source.record_start_byte_offset, capture_source_id=source.capture_source_id,
            network_scope_id=source.network_scope_id, network_scope_state=source.network_scope_state,
            capture_scope_binding_digest=source.capture_scope_binding_digest, attribution_state="resolved",
            attribution_source="trusted_dhcp_v4", attribution_binding_id=own.binding_id,
            attribution_valid_from=own.valid_from, attribution_valid_until=own.valid_until,
            peer_attribution_state=peer.state, peer_attribution_binding_id=peer.binding_id if peer.state == "resolved" else None,
            projection_contract_version=1, projection_algorithm_version=ALGORITHM, projection_run_id=self.run_id)
        edge["edge_semantic_digest"] = semantic_digest(edge)
        return edge

    def prepare(self, source, *, prior_pending=None):
        self._source_identity(source)
        if not self._eligible(source):
            result = NetworkMetadataProjectionResultV1(source.observation_id,
                prior_pending["src_snapshot_state"] if prior_pending is not None else "endpoint_absent",
                prior_pending["dst_snapshot_state"] if prior_pending is not None else "endpoint_absent",
                len(self.repository.existing_edges(source.observation_id)),
                "expired_unresolved" if prior_pending is not None else "terminal_no_edge")
            return PreparedDisposition(source, [], None, result)
        if prior_pending is not None and any(prior_pending[key] != getattr(source, attribute) for key, attribute in (
                ("site_id", "site_id"), ("source_generation_id", "source_generation_id"),
                ("record_start_byte_offset", "record_start_byte_offset"), ("event_at", "event_at"), ("source_ingested_at", "ingested_at"))):
            raise ProjectionConflict("source_observation_identity_conflict")
        try:
            horizon = self.attribution.get_authority_horizon(source.site_id)
        except Exception:
            horizon = SimpleNamespace(state="unavailable")
        states = {}
        for role in ("src", "dst"):
            if prior_pending is not None and not prior_pending["pending_" + role]:
                states[role] = NetworkMetadataAttributionResultV1(prior_pending[role + "_snapshot_state"],
                    binding_id=prior_pending[role + "_snapshot_binding_id"])
            else:
                states[role] = self._resolve(source, role, horizon)
        existing = self.repository.existing_edges(source.observation_id) if prior_pending is not None else {}
        edges = []
        for role in ("src", "dst"):
            # R1: old edges are neither rebuilt nor re-digested on retry. Frozen
            # counterpart state/binding is read from pending snapshots only.
            if role not in existing and states[role].state == "resolved" and (prior_pending is None or prior_pending["pending_" + role]):
                edges.append(self._edge(source, role, states[role], states["dst" if role == "src" else "src"]))
        pending = None
        if any(value.state == "unavailable" for value in states.values()):
            now = self.repository.clock()
            pending = dict(observation_id=source.observation_id, site_id=source.site_id,
                source_generation_id=source.source_generation_id, record_start_byte_offset=source.record_start_byte_offset,
                event_at=source.event_at, source_ingested_at=source.ingested_at,
                first_pending_at=timestamp(now), last_attempt_at=timestamp(now),
                next_retry_at=timestamp(now + timedelta(seconds=self.config.attribution_retry_interval_seconds)))
            for role, value in states.items():
                pending["pending_" + role] = int(value.state == "unavailable")
                pending[role + "_snapshot_state"] = value.state
                pending[role + "_snapshot_binding_id"] = value.binding_id if value.state == "resolved" else None
        count = len(existing) + len(edges)
        status = ("partial_pending" if count else "pending") if pending is not None else ("complete" if count else "terminal_no_edge")
        result = NetworkMetadataProjectionResultV1(source.observation_id, states["src"].state, states["dst"].state, count, status)
        return PreparedDisposition(source, edges, pending, result)

    def _evaluations(self, dispositions):
        keys = {}
        for _, edges, _ in dispositions:
            for edge in edges:
                if self.stop_event.is_set():
                    return {}
                key = edge["site_id"], edge["client_mac"]
                if key not in keys and self.repository.binding(*key) is None:
                    keys[key] = None
        by_mac = self.registry.evaluate_many((key[1] for key in keys), stop_event=self.stop_event)
        if self.stop_event.is_set():
            return {}
        return {key: by_mac[key[1]] for key in keys}

    def _checkpoint_verified(self, generation):
        checkpoint = self.repository.checkpoint(generation.source_generation_id)
        if checkpoint is None:
            return None
        offset = checkpoint["last_record_start_byte_offset"]
        if not generation.generation_start_offset <= offset < generation.committed_byte_offset:
            raise ProjectionConflict("checkpoint_source_conflict")
        record = self.source.get_projection_source_record(checkpoint["last_observation_id"])
        if record is None:
            # Core retention may have removed this observation by event age even
            # when delivery was recent. Verify the durable canonical lineage
            # against the exact generation/offset, never a nearest source row.
            identity = source_event_identity(generation.source_generation_id, offset)
            if checkpoint["last_observation_id"] not in {observation_uuid(family, identity) for family in ("dns", "tls", "quic")}:
                raise ProjectionConflict("checkpoint_source_conflict")
            ni_timestamp(checkpoint["last_source_ingested_at"], canonical=True)
        elif (record.source_generation_id != generation.source_generation_id or record.record_start_byte_offset != offset
              or record.ingested_at != checkpoint["last_source_ingested_at"]):
            raise ProjectionConflict("checkpoint_source_conflict")
        return offset

    def poll(self):
        if self.stop_event.is_set() or self.repository.live_state == "blocked_conflict":
            return
        observation = None
        try:
            generations = self.source.list_source_generations()
            for generation in generations:
                after = self._checkpoint_verified(generation)
                batch = self.source.read_projection_batch(generation.source_generation_id, after, self.config.batch_max_observations)
                if batch:
                    offsets = [source.record_start_byte_offset for source in batch]
                    if offsets != sorted(set(offsets)) or (after is not None and offsets[0] <= after):
                        raise ProjectionConflict("checkpoint_source_conflict")
                    prepared = []
                    for source in batch:
                        if self.stop_event.is_set():
                            return ()
                        observation = source.observation_id
                        prepared.append(self.prepare(source))
                    evaluations = self._evaluations(prepared)
                    if self.stop_event.is_set():
                        return ()
                    self.repository.commit_dispositions(prepared, evaluations, self.run_id, checkpoint={"after": after})
                    self.emit("batch_committed", count=len(prepared))
                    if self.repository.live_state.startswith("capacity_"):
                        self.emit("projection_unavailable", reason_code=self.repository.live_reason)
                    return tuple(item.result for item in prepared)  # One bounded batch, not unbounded catch-up.
            with self.repository.transaction():
                self.repository.success_state(source_verified=True, last_source_poll_at=timestamp(self.repository.clock()))
        except ProjectionConflict as error:
            self.repository.set_failure("blocked_conflict", error.reason, observation=observation)
            self.emit("projection_conflict", reason_code=error.reason)
            return (NetworkMetadataProjectionResultV1(observation, "invalid", "invalid", 0, "conflict", error.reason),) if observation else ()
        except ProjectionError:
            raise
        except Exception:
            self.repository.set_failure("source_unavailable", "source_unavailable")
            self.emit("source_unavailable")

    def retry(self):
        selected = self.repository.pending()
        results = []
        for start in range(0, len(selected), 256):
            prepared = []
            for row in selected[start:start + 256]:
                if self.stop_event.is_set():
                    return tuple(results)
                source = self.source.get_projection_source_record(row["observation_id"])
                if source is None:
                    result = NetworkMetadataProjectionResultV1(row["observation_id"], row["src_snapshot_state"], row["dst_snapshot_state"],
                        len(self.repository.existing_edges(row["observation_id"])), "expired_unresolved")
                    prepared.append(PreparedDisposition(SimpleNamespace(observation_id=row["observation_id"]), [], None, result))
                    self.emit("expired_unresolved", observation_id=row["observation_id"])
                else:
                    prepared.append(self.prepare(source, prior_pending=row))
            evaluations = self._evaluations(prepared)
            if self.stop_event.is_set():
                return tuple(results)
            self.repository.commit_dispositions(prepared, evaluations, self.run_id)
            results.extend(item.result for item in prepared)
        return tuple(results)

    def reconcile(self):
        if self.stop_event.is_set():
            return
        selected = self.repository.reconcile_selection()
        if self.stop_event.is_set():
            return
        by_mac = self.registry.evaluate_many((row["client_mac"] for row in selected), stop_event=self.stop_event)
        if self.stop_event.is_set():
            return
        evaluations = {(row["site_id"], row["client_mac"]): by_mac[row["client_mac"]] for row in selected}
        self.repository.reconcile(selected, evaluations, self.run_id)
        self.emit("registry_reconciled", count=len(selected))

    def tick(self):
        if self.stop_event.is_set() or not self.config.enabled or self.repository.live_state == "blocked_conflict":
            return
        try:
            if self.repository.live_state.startswith("capacity_") and not self.repository.maintain_capacity():
                self.emit("projection_unavailable", reason_code=self.repository.live_reason)
                return
            self.poll()
            if self.repository.live_state == "blocked_conflict":
                return
            now = self.monotonic()
            for field, interval, action in (("last_retry", self.config.attribution_retry_interval_seconds, self.retry),
                    ("last_reconcile", self.config.registry_reconcile_interval_seconds, self.reconcile),
                    ("last_retention", self.config.retention_interval_seconds, self.retain)):
                previous = getattr(self, field)
                if self.stop_event.is_set() or self.repository.live_state.startswith("capacity_"):
                    return
                if previous is None or now - previous >= interval:
                    action()
                    setattr(self, field, now)
        except ProjectionConflict as error:
            self.repository.set_failure("blocked_conflict", error.reason)
            self.emit("projection_conflict", reason_code=error.reason)
        except ProjectionError as error:
            self.emit("projection_unavailable", reason_code=error.reason)
        except Exception:
            self.repository.set_failure("source_unavailable", "source_unavailable")
            self.emit("source_unavailable")

    def retain(self):
        if self.stop_event.is_set():
            return
        from .retention import ProjectionRetention
        totals = ProjectionRetention(self.repository, self.source).run()
        self.emit("retention_completed", count=sum(totals.values()))
        return totals

    def run(self):
        if not self.startup():
            return
        try:
            while not self.stop_event.is_set():
                self.tick()
                self.stop_event.wait(self.config.poll_interval_seconds)
        finally:
            self.repository.close()
