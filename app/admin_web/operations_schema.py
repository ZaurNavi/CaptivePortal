"""Closed v2 projection contract. No raw producer report crosses this boundary."""
from app.operations_health import STATES, REASONS, OWNER_SERVICES, validate_owner
from app.device_fingerprint_sensor.operations_metadata import parse_stamp
import math
from .operations_inventory import SERVICES, STORES
from app.operations_verification import validate_public

SERVICE_KEYS = frozenset({"id", "label", "unit", "role", "expected_mode", "operational_state", "application_health",
    "active_state", "sub_state", "main_pid", "n_restarts", "started_at_utc", "uptime_seconds", "sampled_at_utc",
    "reason_code", "application_health_evidence"})
STORE_KEYS = frozenset({"id", "label", "filename", "purpose", "writer_owner_component_ids", "writer_service_ids",
    "reader_service_ids", "store_kind", "expected_mode", "operational_state", "file_presence", "main_file_bytes",
    "wal_bytes", "shm_bytes", "total_footprint_bytes", "schema_expected_version", "schema_observed_version",
    "health_evidence", "health_checked_at_utc", "sampled_at_utc", "reason_code", "store_verification",
    "metadata_evidence", "journal_bytes"})


def validate_v2(model):
    from .operations_service import OperationsError
    def require(value):
        if not value:
            raise OperationsError()
    require(type(model) is dict and set(model) == {"api_version", "request_id", "scope", "generated_at_utc",
        "freshness_seconds", "sample_status", "snapshot_state", "sampling_started_at_utc", "sampling_completed_at_utc",
        "services", "databases", "partial_failures", "summary", "topology"})
    require(model["api_version"] == "admin.operations.db-services.v2" and model["scope"] == "global")
    require(type(model["services"]) is list and [r.get("id") for r in model["services"]] == [s.id for s in SERVICES])
    require(type(model["databases"]) is list and [r.get("id") for r in model["databases"]] == [s.id for s in STORES])
    for row in model["services"]:
        require(set(row) == SERVICE_KEYS)
        evidence = row["application_health_evidence"]
        require(type(evidence) is dict and set(evidence) == {"state", "source", "observed_at", "received_at", "age", "ttl", "reason"})
        require(evidence["state"] in STATES and row["application_health"] == evidence["state"])
        require(evidence["source"] in {"none", "sensor_native.v2", "source_self_reported_shared_uid"} and evidence["reason"] in REASONS)
        require(evidence["source"] == "none" or evidence["source"] == {
            "fingerprint_sensor": "sensor_native.v2", "network_metadata_projection": "source_self_reported_shared_uid",
            "fingerprint_evidence": "source_self_reported_shared_uid", "network_metadata": "source_self_reported_shared_uid",
            "network_service_recognition": "source_self_reported_shared_uid"}.get(row["id"]))
        require(type(evidence["ttl"]) is int and 0 < evidence["ttl"] <= 180)
        require(evidence["age"] is None or type(evidence["age"]) in {float, int} and math.isfinite(evidence["age"]) and 0 <= evidence["age"] <= 2**53-1)
        for key in ("observed_at", "received_at"):
            if evidence[key] is not None:
                try:parse_stamp(evidence[key])
                except Exception:require(False)
        if row["id"] in {"portal_core", "fingerprint_suricata", "fingerprint_classification", "traffic_projection"}:
            require(evidence["state"] == "unknown" and evidence["source"] == "none")
        if row["id"] in OWNER_SERVICES:
            if evidence["source"] == "none":
                require((evidence['state'], evidence['reason']) in {
                    ('unknown', 'report_unavailable'), ('stale', 'report_stale')})
            elif evidence["state"] == "stale":
                require(evidence["reason"] == "report_stale")
            else:
                try:validate_owner({key: evidence[key] for key in ('state','reason')}, OWNER_SERVICES[row['id']])
                except ValueError:require(False)
        if evidence['reason'] in {'backfilling_incomplete_coverage','source_lagging','source_stale'}:
            require(row['id'] in OWNER_SERVICES and evidence['source'] != 'none')
        if evidence["state"] in {"healthy", "degraded", "unavailable"}:
            require(evidence["source"] != "none" and evidence["age"] is not None and evidence["age"] <= evidence["ttl"])
            require(type(evidence["observed_at"]) is str and type(evidence["received_at"]) is str)
    for row in model["databases"]:
        require(set(row) == STORE_KEYS)
        try:validate_public(row['store_verification'],row['id'])
        except (ValueError,TypeError,KeyError):require(False)
        if row['store_verification']['status']=='not_applicable':require(row['expected_mode']=='optional_disabled')
        require(row["health_evidence"] == "none" and row["schema_observed_version"] is None)
        metadata = row["metadata_evidence"]
        require(type(metadata) is dict and set(metadata) == {"source", "state", "age", "ttl"})
        require(metadata["source"] in {"sensor_metadata", "sampler_lstat", "none"} and metadata["state"] in {"fresh", "stale", "unknown"})
        require(row["journal_bytes"] is None or row["id"] == "sensor_spool" and type(row["journal_bytes"]) is int and 0 <= row["journal_bytes"] <= 2**53-1)
    require(type(model["partial_failures"]) is list and len(model["partial_failures"]) <= 32)
    require(set(model["summary"]) == {"services", "databases", "storage", "problems", "application_health"})
    require(set(model["summary"]["application_health"]) == STATES)
    require(sum(model["summary"]["application_health"].values()) == 9)
    return model
