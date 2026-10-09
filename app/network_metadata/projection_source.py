"""NI-01-owned sensitive, read-only boundary for the isolated NI-02B worker.

No payload/family tables or raw EVE are read. All joined lineage and endpoint
data comes from one SQLite snapshot; an untrusted dependency fails the read.
"""
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .canonical import ni01_canonical_json, observation_uuid, source_event_identity
from .config import make_capture_scope_binding
from .models import SourceGenerationV1, NetworkMetadataError, NetworkMetadataStorageUnavailable, LOGICAL_SOURCE_ID
from .schema import validate_schema
from .validation import canonical_uuid, digest, integer, ip, ni_timestamp


@dataclass(frozen=True, slots=True, repr=False)
class NetworkMetadataProjectionSourceRecordV1:
    observation_id: str
    source_event_identity: str
    source_event_family: str
    source_generation_id: str
    record_start_byte_offset: int
    site_id: str
    capture_source_id: str
    network_scope_id: str
    network_scope_state: str
    capture_scope_binding_digest: str
    capture_scope_ipv4_cidrs: tuple[str, ...]
    event_at: str
    ingested_at: str
    sensitive_endpoint_presence_state: str
    src_ip: str | None
    dst_ip: str | None
    src_port: int | None
    dst_port: int | None
    transport_protocol: str | None


class NetworkMetadataProjectionSourceReadService:
    def __init__(self, db_path):
        self.db_path = db_path

    @contextmanager
    def _snapshot(self):
        connection = None
        try:
            connection = sqlite3.connect(Path(self.db_path).resolve().as_uri() + "?mode=ro",
                                         uri=True, timeout=.5, isolation_level=None)
            connection.row_factory = sqlite3.Row
            for pragma in ("query_only=ON", "foreign_keys=ON", "busy_timeout=500"):
                connection.execute("PRAGMA " + pragma)
            connection.execute("BEGIN")
            validate_schema(connection, writer=False)
            yield connection
        except (sqlite3.Error, OSError, ValueError, TypeError, KeyError, NetworkMetadataError):
            raise NetworkMetadataStorageUnavailable() from None
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def _binding(connection, generation):
        if generation.logical_source_id != LOGICAL_SOURCE_ID:
            raise ValueError
        row = connection.execute("SELECT * FROM network_metadata_capture_scope_bindings WHERE binding_digest=?",
                                 (generation.capture_scope_binding_digest,)).fetchone()
        if row is None:
            raise ValueError
        values = dict(row)
        stored_digest = values.pop("binding_digest")
        encoded = values.pop("ipv4_cidrs_json")
        cidrs = json.loads(encoded)
        if ni01_canonical_json(cidrs).decode("utf-8") != encoded:
            raise ValueError
        binding = make_capture_scope_binding(dict(values, ipv4_cidrs=cidrs))
        if (binding.binding_digest != stored_digest or generation.capture_scope_binding_schema_version != 1
                or generation.binding_valid_from_utc != binding.valid_from_utc):
            raise ValueError
        return binding

    def _generation(self, connection, generation_id):
        row = connection.execute("SELECT * FROM network_metadata_source_generations WHERE source_generation_id=?",
                                 (canonical_uuid(generation_id, 4),)).fetchone()
        if row is None:
            raise ValueError
        generation = SourceGenerationV1(**dict(row))
        self._binding(connection, generation)
        return generation

    def list_source_generations(self):
        with self._snapshot() as connection:
            rows = connection.execute("SELECT * FROM network_metadata_source_generations ORDER BY opened_at_utc,source_generation_id")
            output = []
            for row in rows:
                generation = SourceGenerationV1(**dict(row))
                self._binding(connection, generation)
                output.append(generation)
            return tuple(output)

    def get_source_progress(self, source_generation_id):
        with self._snapshot() as connection:
            return self._generation(connection, source_generation_id)

    def _record(self, connection, row, generation):
        values = dict(row)
        binding = self._binding(connection, generation)
        offset = integer(values["record_start_byte_offset"])
        identity = source_event_identity(generation.source_generation_id, offset)
        if (values["source_generation_id"] != generation.source_generation_id
                or values["source_event_identity"] != identity
                or values["observation_id"] != observation_uuid(values["source_event_family"], identity)
                or values["source_event_family"] not in {"dns", "tls", "quic"}
                or values["schema_version"] != 1 or values["capture_scope_binding_schema_version"] != 1
                or values["network_scope_state"] != "within_intended_scope"
                or any(values[name] != getattr(binding, name) for name in ("site_id", "capture_source_id", "network_scope_id"))
                or values["capture_scope_binding_digest"] != binding.binding_digest
                or not generation.generation_start_offset <= offset < generation.committed_byte_offset):
            raise ValueError
        ni_timestamp(values["event_at"], canonical=True)
        ni_timestamp(values["ingested_at"], canonical=True)
        # Only dependencies of this selected observation: never audit the store.
        health = connection.execute("SELECT * FROM network_metadata_source_health WHERE health_id=?",
            (canonical_uuid(values["source_health_ref"], 4),)).fetchone()
        run = connection.execute("SELECT * FROM network_metadata_ingest_runs WHERE ingest_run_id=?",
            (canonical_uuid(values["ingest_run_id"], 4),)).fetchone()
        if (health is None or run is None
                or health["source_generation_id"] != generation.source_generation_id
                or health["capture_source_id"] != binding.capture_source_id
                or run["normalizer_version"] != values["normalizer_version"]):
            raise ValueError
        ni_timestamp(health["evaluated_at"], canonical=True)
        if ni_timestamp(run["started_at_utc"], canonical=True) > ni_timestamp(values["ingested_at"], canonical=True):
            raise ValueError
        for name in ("capture_health", "metadata_output_health", "metadata_ingest_health"):
            if health[name] not in {"usable", "partial", "stale", "unavailable", "unknown"}:
                raise ValueError
        digest(run["repository_head"], 40)
        digest(run["repository_tree"], 40)
        digest(run["configuration_digest"])
        state = values["sensitive_endpoint_presence_state"]
        if state not in {"observed_retained", "not_observed", "expired"}:
            raise ValueError
        endpoint = connection.execute("SELECT * FROM network_metadata_sensitive_endpoints WHERE observation_id=?",
                                      (values["observation_id"],)).fetchone()
        endpoints = dict(src_ip=None, dst_ip=None, src_port=None, dst_port=None, transport_protocol=None)
        if state == "observed_retained":
            if endpoint is None:
                raise ValueError
            for role in ("src", "dst"):
                address, port = endpoint[role + "_ip"], endpoint[role + "_port"]
                if address is not None and ip(address) != address:
                    raise ValueError
                if port is not None:
                    integer(port, 0, 65535)
                if address is None and port is not None:
                    raise ValueError
                endpoints.update({role + "_ip": address, role + "_port": port})
            if endpoint["transport_protocol"] not in {None, "TCP", "UDP"}:
                raise ValueError
            endpoints["transport_protocol"] = endpoint["transport_protocol"]
        # Never expose stale endpoints even if a damaged source leaves old rows.
        names = NetworkMetadataProjectionSourceRecordV1.__dataclass_fields__
        selected = {name: values[name] for name in names if name in values}
        return NetworkMetadataProjectionSourceRecordV1(**selected, capture_scope_ipv4_cidrs=binding.ipv4_cidrs, **endpoints)

    def read_projection_batch(self, source_generation_id, after_record_start_byte_offset, limit):
        integer(limit, 1, 256)
        if after_record_start_byte_offset is not None:
            integer(after_record_start_byte_offset)
        with self._snapshot() as connection:
            generation = self._generation(connection, source_generation_id)
            clause = "" if after_record_start_byte_offset is None else " AND record_start_byte_offset>?"
            parameters = [source_generation_id]
            if after_record_start_byte_offset is not None:
                parameters.append(after_record_start_byte_offset)
            parameters.append(limit)
            rows = connection.execute("SELECT * FROM network_metadata_observations WHERE source_generation_id=?" +
                                      clause + " ORDER BY record_start_byte_offset LIMIT ?", parameters).fetchall()
            return tuple(self._record(connection, row, generation) for row in rows)

    def get_projection_source_record(self, observation_id):
        canonical_uuid(observation_id, 5)
        with self._snapshot() as connection:
            row = connection.execute("SELECT * FROM network_metadata_observations WHERE observation_id=?", (observation_id,)).fetchone()
            if row is None:
                return None
            return self._record(connection, row, self._generation(connection, row["source_generation_id"]))
