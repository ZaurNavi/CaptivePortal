"""Disposable exact source/authority/Registry data; no real network inputs."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from dataclasses import replace
import uuid

from app.network_metadata.config import make_capture_scope_binding
from app.network_metadata.canonical import source_event_identity, observation_uuid
from app.network_metadata.projection_source import NetworkMetadataProjectionSourceRecordV1
from app.network_metadata.validation import ni_format_utc
from app.network_attribution.models import NetworkMetadataAttributionResultV1, NetworkAttributionHorizonV1
from app.device_fingerprint.validation import format_utc
from app.network_metadata_projection.models import ProjectionConfig, RegistryEvaluation
from app.network_metadata_projection.repository import ProjectionRepository
from app.network_metadata_projection.service import NetworkMetadataProjectionService

SITE = "6a64f17630da7c70d232187a"
T0 = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
GENERATION = "9412aebe-6e13-463b-9a93-d2e5c8475766"
MAC = "00:11:22:33:44:55"
OTHER_MAC = "00:11:22:33:44:66"
IDENTITY = SimpleNamespace(artifact_sha="a" * 40, artifact_tree="b" * 40)


class Clock:
    def __init__(self):
        self.value = T0 + timedelta(seconds=30)
    def __call__(self):
        return self.value
    def advance(self, **kwargs):
        self.value += timedelta(**kwargs)


def source_record(offset=0, **changes):
    binding = make_capture_scope_binding(dict(schema_version=1, capture_source_id="synthetic-sensor",
        site_id=SITE, network_scope_id="synthetic-scope", ipv4_cidrs=["10.73.0.0/16"],
        valid_from_utc="2026-01-01T00:00:00.000000Z"))
    identity = source_event_identity(GENERATION, offset)
    value = NetworkMetadataProjectionSourceRecordV1(observation_uuid("dns", identity), identity, "dns", GENERATION,
        offset, SITE, binding.capture_source_id, binding.network_scope_id, "within_intended_scope", binding.binding_digest,
        binding.ipv4_cidrs, "2026-10-09T12:00:00.123456Z", ni_format_utc(T0), "observed_retained",
        "10.73.0.7", "10.73.0.8", 65535, 65535, "UDP")
    return replace(value, **changes)


class Source:
    def __init__(self, records=()):
        self.records = list(records)
        self.fail = False
    def list_source_generations(self):
        if self.fail:
            raise OSError("source-private-sentinel")
        ids = sorted({record.source_generation_id for record in self.records})
        return tuple(self.get_source_progress(item) for item in ids)
    def get_source_progress(self, generation):
        records = [value for value in self.records if value.source_generation_id == generation]
        return SimpleNamespace(source_generation_id=generation, generation_start_offset=0,
            committed_byte_offset=max((value.record_start_byte_offset for value in records), default=0) + 1)
    def read_projection_batch(self, generation, after, limit):
        return tuple(sorted((record for record in self.records if record.source_generation_id == generation
            and (after is None or record.record_start_byte_offset > after)), key=lambda value: value.record_start_byte_offset)[:limit])
    def get_projection_source_record(self, observation):
        return next((item for item in self.records if item.observation_id == observation), None)


class Attribution:
    def __init__(self):
        self.calls = []
        self.states = {}
        self.macs = {"10.73.0.7": MAC, "10.73.0.8": OTHER_MAC}
        self.ids = {}
    def get_authority_horizon(self, site):
        return NetworkAttributionHorizonV1("available", site, format_utc(T0), format_utc(T0))
    def resolve_ipv4(self, site, address, event):
        self.calls.append((site, address, event))
        state = self.states.get(address, "resolved")
        if state != "resolved":
            return NetworkMetadataAttributionResultV1(state)
        return NetworkMetadataAttributionResultV1("resolved", site_id=site, client_mac=self.macs.get(address, MAC),
            ipv4=address, event_at=event, binding_id=self.ids.setdefault(address, str(uuid.uuid4())),
            valid_from=format_utc(T0), valid_until=format_utc(T0 + timedelta(hours=1)), attribution_source="trusted_dhcp_v4")


class Registry:
    def __init__(self):
        self.calls, self.values = [], {}
        self.batches = []
    def evaluate_many(self, macs, *, stop_event=None):
        requested = tuple(dict.fromkeys(macs))
        self.batches.append(requested)
        evaluations = {}
        for mac in requested:
            if stop_event is not None and stop_event.is_set():
                break
            evaluations[mac] = self.evaluate(mac)
        return evaluations
    def evaluate(self, mac):
        self.calls.append(mac)
        return self.values.get(mac, RegistryEvaluation("not_yet_registry_resolved"))


def stack(tmp_path, records=None):
    clock = Clock()
    config = ProjectionConfig(True, str(tmp_path / "projection.sqlite3"), max_db_bytes=67108864)
    repository = ProjectionRepository(config, clock=clock).initialize()
    source, attribution, registry = Source(records or [source_record()]), Attribution(), Registry()
    service = NetworkMetadataProjectionService(config, repository, source, attribution, registry, IDENTITY)
    service.run_id = repository.create_run(IDENTITY)
    return SimpleNamespace(clock=clock, config=config, repo=repository, source=source, attribution=attribution,
                           registry=registry, service=service)
