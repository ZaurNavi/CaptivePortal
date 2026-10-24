"""Closed v2 projection contract. No raw producer report crosses this boundary."""
from app.operations_health import STATES, REASONS, OWNER_SERVICES, LOCAL_SERVICES, APP_SOURCES, PHASE_REASONS, validate_owner, validate_local
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
        require(evidence["source"] in {'none', *APP_SOURCES.values()} and evidence["reason"] in REASONS)
        require(evidence["source"] == "none" or evidence["source"] == APP_SOURCES.get(row["id"]))
        require(type(evidence["ttl"]) is int and 0 < evidence["ttl"] <= 180)
        require(evidence["age"] is None or type(evidence["age"]) in {float, int} and math.isfinite(evidence["age"]) and 0 <= evidence["age"] <= 2**53-1)
        for key in ("observed_at", "received_at"):
            if evidence[key] is not None:
                try:parse_stamp(evidence[key])
                except Exception:require(False)
        if row["id"] in OWNER_SERVICES or row['id'] in LOCAL_SERVICES:
            if evidence["source"] == "none":
                require((evidence['state'], evidence['reason']) in {
                    ('unknown', 'report_unavailable'), ('stale', 'report_stale')})
            elif evidence["state"] == "stale":
                require(evidence["reason"] == "report_stale")
            else:
                try:
                    validator = validate_owner if row['id'] in OWNER_SERVICES else validate_local
                    validator({key: evidence[key] for key in ('state','reason')},
                        (OWNER_SERVICES | LOCAL_SERVICES)[row['id']])
                except ValueError:require(False)
        if evidence['reason'] in PHASE_REASONS:
            require(row['id'] in OWNER_SERVICES or row['id'] in LOCAL_SERVICES)
            require(evidence['source'] != 'none')
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


def validate_v3(model):
    """V2's entire closed privacy contract plus exactly one bounded workload."""
    from .operations_service import OperationsError
    if type(model) is not dict or model.get("api_version") != "admin.operations.db-services.v3":
        raise OperationsError()
    workload = model.get("workload")
    if type(workload) is not dict or set(workload) != {"network_metadata_projection"}:
        raise OperationsError()
    pending = workload["network_metadata_projection"]
    if type(pending) is not dict or set(pending) != {"pending_attribution_count"}:
        raise OperationsError()
    count = pending["pending_attribution_count"]
    if count is not None and (type(count) is not int or not 0 <= count <= 2**53-1):
        raise OperationsError()
    v2 = {key: value for key, value in model.items() if key != "workload"}
    v2["api_version"] = "admin.operations.db-services.v2"
    validate_v2(v2)
    return model


def validate_v4(model):
    """V3 remains the full base contract, with two closed workload additions."""
    from .operations_service import OperationsError
    from app.device_fingerprint_sensor.operations_metadata import sensor_workload
    from app.operations_app_health import ni04_workload
    if type(model) is not dict or model.get('api_version') != 'admin.operations.db-services.v4':
        raise OperationsError()
    workload = model.get('workload')
    if type(workload) is not dict or set(workload) != {
            'network_metadata_projection', 'fingerprint_sensor', 'network_service_recognition'}:
        raise OperationsError()
    try:
        if type(workload['fingerprint_sensor']) is not dict or type(workload['network_service_recognition']) is not dict:
            raise ValueError()
        sensor_workload(workload['fingerprint_sensor'])
        ni04_workload(workload['network_service_recognition'])
    except (ValueError, TypeError, KeyError):
        raise OperationsError() from None
    v3 = dict(model, api_version='admin.operations.db-services.v3',
        workload={'network_metadata_projection': workload['network_metadata_projection']})
    validate_v3(v3)
    return model


def core_workload(value=None):
    fields = {'portal_evidence_queue_depth', 'visit_writer_foreground_waiters',
        'visit_writer_background_waiters'}
    if value is None:return dict.fromkeys(fields)
    if type(value) is not dict or set(value) != fields:raise ValueError()
    if any(item is not None and (type(item) is not int or not 0 <= item <= 2**53-1)
            for item in value.values()):raise ValueError()
    if (value['visit_writer_foreground_waiters'] is None) != (value['visit_writer_background_waiters'] is None):
        raise ValueError()
    return dict(value)


def validate_v5(model):
    """Closed additions projected through the complete, unchanged V4 contract."""
    from .operations_service import OperationsError
    from app.operations_app_health import phase2_workload
    from app.operations_health import NI04_UNIT, CLASSIFICATION_UNIT, TRAFFIC_UNIT
    if type(model) is not dict or model.get('api_version') != 'admin.operations.db-services.v5':
        raise OperationsError()
    workload = model.get('workload')
    if type(workload) is not dict or set(workload) != {'network_metadata_projection',
            'fingerprint_sensor', 'network_service_recognition', 'fingerprint_classification',
            'portal_core', 'traffic_projection'}:raise OperationsError()
    try:
        for key, unit in (('network_service_recognition',NI04_UNIT),
                ('fingerprint_classification',CLASSIFICATION_UNIT),('traffic_projection',TRAFFIC_UNIT)):
            if type(workload[key]) is not dict:raise ValueError()
            phase2_workload(unit,workload[key])
        if type(workload['portal_core']) is not dict:raise ValueError()
        core_workload(workload['portal_core'])
    except (ValueError, TypeError, KeyError):raise OperationsError() from None
    validate_v4(dict(model,api_version='admin.operations.db-services.v4',workload={
        'network_metadata_projection':workload['network_metadata_projection'],
        'fingerprint_sensor':workload['fingerprint_sensor'],
        'network_service_recognition':{'feed_backlog_entries':None}}))
    return model
