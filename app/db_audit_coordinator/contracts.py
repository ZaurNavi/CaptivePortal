"""Closed G1 contracts; fixture success never attests a real store's health.

Retention is deliberately saturating: 128 total accepted jobs, no eviction.
Unresolved ACKs and scoped idempotency therefore never disappear. At saturation
admission returns queue_full; operator-reviewed rollover is NOT implemented G1.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone

SCHEMA = "db_audit_coordinator.queue.v1"
DOMAIN = "lab-ubunt-local-sqlite-v1"
MAX_BYTES = 256 * 1024
MAX_FRAME = 8192
MAX_OUTSTANDING = 32
MAX_HISTORY = 128
MAX_INTEGER = 2**63-1
FINGERPRINT_METHOD = "sqlite_backup_memory_t3_v1"
FINGERPRINT_VALIDATOR = "fingerprint.evidence.t3.schema2.v1"
STORES = frozenset({"portal_counter", "public_traffic", "visitor_registry", "visits", "observations",
    "current_state", "traffic_projection", "fingerprint_evidence", "fingerprint_classification",
    "fingerprint_control_plane", "fingerprint_integration", "network_metadata", "network_attribution",
    "network_metadata_projection", "network_service_intelligence", "settings", "sensor_spool"})
OUTSTANDING = frozenset({"registered", "queued", "claimed", "running"})
TERMINAL = frozenset({"completed", "failed", "deferred", "canceled"})
REASONS = frozenset({"accepted", "claimed", "running", "fixture_passed", "fixture_failed", "worker_crashed",
    "resource_deferred", "gate_busy", "unsafe_path", "unauthorized", "orphan_hold", "canceled", "timeout",
    "restarted_after_claim", "status_untrusted", "fingerprint_snapshot_passed", "fingerprint_integrity_suspect"})
ERRORS = frozenset({"invalid_request", "store_busy", "queue_full", "queue_unavailable", "queue_unknown",
    "coordinator_unavailable", "not_admitted", "gate_busy", "unsafe_path", "unauthorized", "orphan_hold"})


class CoordinatorError(Exception):
    def __init__(self, code):
        self.code = code if code in ERRORS else "coordinator_unavailable"
        super().__init__(self.code)


def integer(value, maximum=MAX_INTEGER):
    if type(value) is not int or not 0 <= value <= maximum:
        raise CoordinatorError("invalid_request")
    return value


def identifier(value):
    if type(value) is not str:
        raise CoordinatorError("invalid_request")
    try:
        if str(uuid.UUID(value)) != value: raise ValueError()
    except ValueError:
        raise CoordinatorError("invalid_request") from None
    return value


def digest(value):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise CoordinatorError("invalid_request")
    return value


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def timestamp(value):
    if type(value) is not str or re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z", value) is None:
        raise CoordinatorError("invalid_request")
    try: datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError: raise CoordinatorError("invalid_request") from None


def closed(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise CoordinatorError("invalid_request")


def decode(raw, limit=MAX_BYTES):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError()
            result[key] = value
        return result
    def invalid(_value): raise ValueError()
    try:
        if type(raw) is not bytes or len(raw) > limit: raise ValueError()
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid)
    except (ValueError, UnicodeError, RecursionError):
        raise CoordinatorError("invalid_request") from None


def encode(value, limit=MAX_BYTES):
    try: raw = json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode("ascii")
    except (ValueError, TypeError, RecursionError): raise CoordinatorError("invalid_request") from None
    if len(raw) > limit: raise CoordinatorError("invalid_request")
    return raw


def request(value):
    if type(value) is not dict: raise CoordinatorError("invalid_request")
    if value.get("op") == "submit":
        closed(value, {"op", "store_id", "idempotency_key", "origin"})
        if (type(value["store_id"]) is not str or value["store_id"] not in STORES
                or type(value["origin"]) is not str or value["origin"] not in {"manual", "scheduled"}):
            raise CoordinatorError("invalid_request")
        identifier(value["idempotency_key"])
    elif value.get("op") == "status":
        closed(value, {"op", "job_id"}); identifier(value["job_id"])
    else: raise CoordinatorError("invalid_request")
    return value


def scope(uid):
    integer(uid, 2**32-1)
    return hashlib.sha256(f"uid:{uid}".encode("ascii")).hexdigest()


def idempotency(scope_hash, key):
    digest(scope_hash); identifier(key)
    return hashlib.sha256((scope_hash+":"+key).encode("ascii")).hexdigest()


def empty_state():
    """Pure provisioning payload, never automatically installed by the core."""
    return dict(schema_version=SCHEMA, controller_epoch=str(uuid.uuid4()), next_sequence=1,
        jobs=[], last_attempt_by_store={}, last_verified_success_by_store={})


JOB_KEYS = frozenset({"job_id", "seq", "store_id", "scope_hash", "idempotency_hash", "origin", "state",
    "claim_epoch", "attempt_id", "run_id", "created_at", "updated_at", "reason_code", "method_version",
    "validator_version", "source_generation", "resource_envelope", "auth_hash", "auth_device", "auth_inode",
    "worker_pid", "audit_result"})
RESULT_KEYS = frozenset({"fixture_only", "job_id", "store_id", "run_id", "attempt_id", "claim_epoch",
    "method_version", "validator_version", "source_generation", "snapshot_id", "completed_at", "result", "reason_code"})


def _result(value):
    closed(value, RESULT_KEYS)
    if value["fixture_only"] is not True or value["store_id"] not in STORES:
        raise CoordinatorError("invalid_request")
    for key in ("job_id", "run_id", "attempt_id", "claim_epoch", "source_generation"): identifier(value[key])
    fingerprint = value["method_version"] == FINGERPRINT_METHOD and value["validator_version"] == FINGERPRINT_VALIDATOR and value["store_id"] == "fingerprint_evidence"
    if not fingerprint and (value["method_version"] != "fixture.sentinel.v1" or value["validator_version"] != "fixture.v1"):
        raise CoordinatorError("invalid_request")
    if value["result"] not in {"passed", "failed", "incomplete"} or value["reason_code"] not in REASONS:
        raise CoordinatorError("invalid_request")
    if value["snapshot_id"] is not None: digest(value["snapshot_id"])
    if value["result"] == "passed" and (value["snapshot_id"] is None or value["reason_code"] != ("fingerprint_snapshot_passed" if fingerprint else "fixture_passed")):
        raise CoordinatorError("invalid_request")
    if value["result"] == "failed" and ((not fingerprint and value["snapshot_id"] is None) or value["reason_code"] != ("fingerprint_integrity_suspect" if fingerprint else "fixture_failed")):
        raise CoordinatorError("invalid_request")
    if value["result"] == "incomplete" and (value["snapshot_id"] is not None or value["reason_code"] not in {
            "resource_deferred","gate_busy","unsafe_path","unauthorized","orphan_hold","canceled",
            "timeout","worker_crashed","restarted_after_claim","status_untrusted"}):
        raise CoordinatorError("invalid_request")
    timestamp(value["completed_at"])
    return value


def _state(value):
    closed(value, {"schema_version", "controller_epoch", "next_sequence", "jobs", "last_attempt_by_store", "last_verified_success_by_store"})
    if value["schema_version"] != SCHEMA: raise CoordinatorError("invalid_request")
    identifier(value["controller_epoch"]); integer(value["next_sequence"])
    if value["next_sequence"]<1:raise CoordinatorError("invalid_request")
    if type(value["jobs"]) is not list or len(value["jobs"]) > MAX_HISTORY: raise CoordinatorError("invalid_request")
    ids, sequences, outstanding, keys = set(), [], set(), set()
    for job in value["jobs"]:
        closed(job, JOB_KEYS)
        identifier(job["job_id"]); identifier(job["source_generation"])
        if job["store_id"] not in STORES or job["origin"] not in {"manual", "scheduled"} or job["state"] not in OUTSTANDING | TERMINAL:
            raise CoordinatorError("invalid_request")
        integer(job["seq"]); digest(job["scope_hash"]); digest(job["idempotency_hash"])
        if job["seq"]<1:raise CoordinatorError("invalid_request")
        for key in ("created_at", "updated_at"): timestamp(job[key])
        if job["job_id"] in ids or job["idempotency_hash"] in keys or job["reason_code"] not in REASONS:
            raise CoordinatorError("invalid_request")
        ids.add(job["job_id"]); keys.add(job["idempotency_hash"]); sequences.append(job["seq"])
        if ((job["method_version"], job["validator_version"]) != ("fixture.sentinel.v1", "fixture.v1")
                and not (job["store_id"] == "fingerprint_evidence" and
                    (job["method_version"], job["validator_version"]) == (FINGERPRINT_METHOD, FINGERPRINT_VALIDATOR))):
            raise CoordinatorError("invalid_request")
        if job["state"] in OUTSTANDING:
            if job["store_id"] in outstanding: raise CoordinatorError("invalid_request")
            outstanding.add(job["store_id"])
        claimed = job["claim_epoch"] is not None
        if claimed:
            for key in ("claim_epoch", "attempt_id", "run_id"): identifier(job[key])
            digest(job["auth_hash"])
            integer(job["auth_device"]); integer(job["auth_inode"])
        elif any(job[key] is not None for key in ("attempt_id", "run_id", "auth_hash", "auth_device", "auth_inode", "worker_pid", "resource_envelope", "audit_result")):
            raise CoordinatorError("invalid_request")
        if job["state"] in {"claimed", "running", "completed", "failed", "deferred"} and not claimed:
            raise CoordinatorError("invalid_request")
        if job["worker_pid"] is not None:
            integer(job["worker_pid"], 2**31-1)
            if job["worker_pid"]==0:raise CoordinatorError("invalid_request")
        if job["resource_envelope"] is not None:
            closed(job["resource_envelope"], {"fixture_only", "memory_limit_bytes", "timeout_seconds"})
            if job["resource_envelope"]["fixture_only"] is not True: raise CoordinatorError("invalid_request")
            integer(job["resource_envelope"]["memory_limit_bytes"], 64*1024**2)
            integer(job["resource_envelope"]["timeout_seconds"], 10)
        if job["audit_result"] is not None:
            result(job["audit_result"])
            if any(job["audit_result"][key]!=job[key] for key in ("job_id","store_id","run_id","attempt_id","claim_epoch","method_version","validator_version","source_generation")):
                raise CoordinatorError("invalid_request")
            expected="completed" if job["audit_result"]["result"]=="passed" else "failed" if job["audit_result"]["result"]=="failed" else "canceled" if job["audit_result"]["reason_code"]=="canceled" else "deferred"
            if job["state"]!=expected:raise CoordinatorError("invalid_request")
        elif job["state"] in {"completed","failed","deferred"}:
            raise CoordinatorError("invalid_request")
    if sequences != sorted(set(sequences)) or (sequences and value["next_sequence"] <= sequences[-1]) or len(outstanding) > MAX_OUTSTANDING:
        raise CoordinatorError("invalid_request")
    for key in ("last_attempt_by_store", "last_verified_success_by_store"):
        records = value[key]
        if type(records) is not dict or not set(records) <= STORES: raise CoordinatorError("invalid_request")
        for store_id, record in records.items():
            result(record)
            if record["store_id"] != store_id or (key == "last_verified_success_by_store" and record["result"] != "passed"):
                raise CoordinatorError("invalid_request")
            if not any(job["audit_result"]==record for job in value["jobs"]):raise CoordinatorError("invalid_request")
    encode(value)
    return value


def result(value):
    try:return _result(value)
    except CoordinatorError:raise
    except (KeyError,TypeError,ValueError,RecursionError):raise CoordinatorError("invalid_request") from None


def state(value):
    try:return _state(value)
    except CoordinatorError:raise
    except (KeyError,TypeError,ValueError,RecursionError):raise CoordinatorError("invalid_request") from None


def public_job(job):
    """No UID, descriptor identity, paths, keys or private authority in status."""
    return dict(resource_domain=DOMAIN,**{key:job[key] for key in (
        "job_id","store_id","seq","origin","state","run_id","attempt_id","claim_epoch",
        "method_version","validator_version","source_generation","resource_envelope","created_at",
        "updated_at","reason_code","audit_result")})
