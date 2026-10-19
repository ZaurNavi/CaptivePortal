"""Closed operational pilot policy. No hypervisor input, approval token or ENV.

The three-store LAB pilot's host gate is external and attended. All numeric
memory policy here refers exclusively to the guest VM. No defaults grant an
installation, store, memory budget, legacy cutover, or real execution permission.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import PurePosixPath
import time
import uuid

from . import contracts as c

SCHEMA = 'db_audit_coordinator.queue.operational.v1'
METHOD = 'sqlite_backup_memory_t3.operational.v1'
VALIDATORS = {
    'fingerprint_evidence': 'fingerprint.evidence.t3.schema2.v1',
    'network_service_intelligence': 'ni04.materialization.t3.schema1.v1',
    'public_traffic': 'public_traffic.t3.schema2.v1',
    'traffic_projection': 'traffic_projection.t3.schema1.v1',
}
INCOMPLETE_REASONS = {'preflight_denied','gate_busy','unsafe_path','unauthorized','resource_deferred',
    'timeout','worker_crashed','restarted_after_claim','status_untrusted','orphan_hold','canceled'}
REASONS = INCOMPLETE_REASONS | {'accepted','claimed','running','audit_passed','audit_failed','controlled_failure'}
PREFLIGHT_MAX_SECONDS = 300
ATTEMPT_MAX_SECONDS = 5400
SOCKET = '/run/captive-portal/db-audit/coordinator.sock'
ROOT = '/var/lib/captive-portal/db-audit'
PROFILE = '/etc/captive-portal/db-audit/pilot.json'


def require(value, code='not_admitted'):
    if not value:
        raise c.CoordinatorError(code)


def integer(value, low=0, high=c.MAX_INTEGER):
    require(type(value) is int and low <= value <= high)
    return value


def path(value):
    require(type(value) is str and len(value) <= 512 and value.startswith('/')
        and str(PurePosixPath(value)) == value and '..' not in PurePosixPath(value).parts
        and all(32 <= ord(char) < 127 for char in value))
    return value


def physical_generation(store, device, inode):
    """Explicit physical file-instance identity, NOT an invented DB UUID.

    Stores without a native DB-generation singleton use the pinned dev/inode.
    No in-place rollback detection is claimed. Native snapshot lineage is also
    returned separately by its store validator, never substituted by this value.
    """
    require(store in VALIDATORS); integer(device); integer(inode, 1)
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'coordinator-file-instance-v1:{store}:{device}:{inode}'))


@dataclass(frozen=True)
class Deadlines:
    started_ns: int
    attempt_seconds: int
    receipt_seconds: int = PREFLIGHT_MAX_SECONDS

    def __post_init__(self):
        integer(self.started_ns); integer(self.attempt_seconds, 1, ATTEMPT_MAX_SECONDS)
        integer(self.receipt_seconds, 1, PREFLIGHT_MAX_SECONDS)

    def check(self, now_ns=None):
        now = time.monotonic_ns() if now_ns is None else integer(now_ns)
        require(self.started_ns <= now < self.started_ns + self.attempt_seconds*1_000_000_000, 'not_admitted')

    def receipt(self, captured_ns, now_ns=None):
        now = time.monotonic_ns() if now_ns is None else integer(now_ns)
        self.check(now)
        require(type(captured_ns) is int and self.started_ns <= captured_ns
            and 0 <= now-captured_ns < self.receipt_seconds*1_000_000_000)


@dataclass(frozen=True)
class StorePolicy:
    store_id: str
    source: str
    device: int
    inode: int
    uid: int
    gid: int
    schema_version: int
    source_max_bytes: int
    wal_max_bytes: int
    image_max_bytes: int
    backup_overhead_bytes: int
    validator_overhead_bytes: int
    margin_bytes: int
    guest_reserve_bytes: int
    memory_max_bytes: int
    attempt_seconds: int

    def __post_init__(self):
        require(self.store_id in VALIDATORS); path(self.source)
        integer(self.device); integer(self.inode, 1); integer(self.uid, 0, 2**32-1); integer(self.gid, 0, 2**32-1)
        integer(self.schema_version, 1, 2)
        require(self.schema_version==(2 if self.store_id in {'public_traffic','fingerprint_evidence'} else 1))
        for name in ('source_max_bytes', 'image_max_bytes', 'backup_overhead_bytes',
                'validator_overhead_bytes', 'margin_bytes', 'guest_reserve_bytes', 'memory_max_bytes'):
            integer(getattr(self, name), 1)
        integer(self.wal_max_bytes); integer(self.attempt_seconds, 1, ATTEMPT_MAX_SECONDS)
        require(self.source_max_bytes <= self.image_max_bytes < self.memory_max_bytes)

    @classmethod
    def parse(cls, value):
        c.closed(value, cls.__dataclass_fields__)
        return cls(**value)

    def metadata(self):
        return METHOD, VALIDATORS[self.store_id], physical_generation(self.store_id, self.device, self.inode)


SNAPSHOT_KEYS = {'schema_version', 'generation_kind', 'lineage_sha256', 'watermark_sha256', 'page_size', 'page_count'}
RESULT_KEYS = c.RESULT_KEYS | {'snapshot_metadata', 'duration_ms'}


def result(value):
    c.closed(value, RESULT_KEYS)
    require(value['fixture_only'] is False and value['method_version'] == METHOD
        and value['store_id'] in VALIDATORS and value['validator_version'] == VALIDATORS[value['store_id']], 'invalid_request')
    for name in ('job_id','run_id','attempt_id','claim_epoch','source_generation'):
        c.identifier(value[name])
    c.timestamp(value['completed_at']); integer(value['duration_ms'])
    require(value['reason_code'] in REASONS and value['result'] in {'passed','failed','incomplete'}, 'invalid_request')
    snapshot = value['snapshot_metadata']
    if value['result'] == 'passed':
        require(value['reason_code'] == 'audit_passed' and type(snapshot) is dict, 'invalid_request')
        c.closed(snapshot, SNAPSHOT_KEYS)
        integer(snapshot['schema_version'],1,2); integer(snapshot['page_size'],512,65536); integer(snapshot['page_count'],1)
        require(snapshot['schema_version']==(2 if value['store_id'] in {'public_traffic','fingerprint_evidence'} else 1))
        require(snapshot['page_size'] & (snapshot['page_size']-1) == 0, 'invalid_request')
        require(snapshot['generation_kind'] in {'native_lineage', 'pinned_file_instance'}, 'invalid_request')
        require(snapshot['generation_kind']==('pinned_file_instance' if value['store_id']=='public_traffic' else 'native_lineage'))
        for key in ('lineage_sha256','watermark_sha256'): c.digest(snapshot[key])
        c.digest(value['snapshot_id'])
        require(value['snapshot_id'] == hashlib.sha256(c.encode(snapshot)).hexdigest(), 'invalid_request')
    else:
        require(snapshot is None and value['snapshot_id'] is None, 'invalid_request')
        require(value['reason_code'] != 'audit_passed', 'invalid_request')
        require(value['reason_code'] in ({'audit_failed','controlled_failure'} if value['result']=='failed' else INCOMPLETE_REASONS))
    return value


def empty_state():
    value = c.empty_state(); value['schema_version'] = SCHEMA
    return value


def state(value):
    """Operational records never pass the unchanged fixture-only c.state API."""
    c.closed(value, {'schema_version','controller_epoch','next_sequence','jobs','last_attempt_by_store','last_verified_success_by_store'})
    require(value['schema_version'] == SCHEMA, 'invalid_request'); c.identifier(value['controller_epoch'])
    integer(value['next_sequence'],1)
    require(type(value['jobs']) is list and len(value['jobs']) <= c.MAX_HISTORY, 'invalid_request')
    ids, keys, sequences, outstanding = set(), set(), [], set()
    for job in value['jobs']:
        c.closed(job,c.JOB_KEYS)
        for key in ('job_id','source_generation'): c.identifier(job[key])
        for key in ('scope_hash','idempotency_hash'): c.digest(job[key])
        require(job['store_id'] in VALIDATORS and job['method_version'] == METHOD
            and job['validator_version'] == VALIDATORS[job['store_id']] and job['origin'] == 'manual', 'invalid_request')
        require(job['job_id'] not in ids and job['idempotency_hash'] not in keys, 'invalid_request')
        ids.add(job['job_id']); keys.add(job['idempotency_hash']); integer(job['seq'],1); sequences.append(job['seq'])
        require(job['state'] in c.OUTSTANDING | c.TERMINAL and job['reason_code'] in REASONS, 'invalid_request')
        for key in ('created_at','updated_at'): c.timestamp(job[key])
        if job['state'] in c.OUTSTANDING:
            require(job['store_id'] not in outstanding, 'invalid_request'); outstanding.add(job['store_id'])
        if job['claim_epoch'] is not None:
            for key in ('claim_epoch','attempt_id','run_id'): c.identifier(job[key])
            c.digest(job['auth_hash']); integer(job['auth_device']); integer(job['auth_inode'],1)
        else:
            require(all(job[key] is None for key in ('attempt_id','run_id','auth_hash','auth_device','auth_inode','worker_pid','resource_envelope','audit_result')), 'invalid_request')
        if job['state'] in {'claimed','running','completed','failed','deferred'}:
            require(job['claim_epoch'] is not None, 'invalid_request')
        if job['state']=='queued':require(job['claim_epoch'] is None,'invalid_request')
        if job['state']=='claimed':require(job['worker_pid'] is None and job['resource_envelope'] is not None,'invalid_request')
        if job['state']=='running':require(job['worker_pid'] is not None and job['resource_envelope'] is not None,'invalid_request')
        if job['worker_pid'] is not None: integer(job['worker_pid'],1,2**31-1)
        if job['resource_envelope'] is not None:
            c.closed(job['resource_envelope'], {'fixture_only','memory_limit_bytes','timeout_seconds'})
            require(job['resource_envelope']['fixture_only'] is False, 'invalid_request')
            integer(job['resource_envelope']['memory_limit_bytes'],1)
            integer(job['resource_envelope']['timeout_seconds'],1,ATTEMPT_MAX_SECONDS)
        if job['audit_result'] is not None:
            item = result(job['audit_result'])
            require(all(item[key] == job[key] for key in ('job_id','store_id','run_id','attempt_id','claim_epoch','method_version','validator_version','source_generation')), 'invalid_request')
            expected = 'completed' if item['result']=='passed' else 'failed' if item['result']=='failed' else 'canceled' if item['reason_code']=='canceled' else 'deferred'
            require(job['state']==expected, 'invalid_request')
        else:
            require(job['state'] not in {'completed','failed','deferred'}, 'invalid_request')
    require(sequences == sorted(set(sequences)) and (not sequences or value['next_sequence'] > sequences[-1])
        and len(outstanding) <= c.MAX_OUTSTANDING, 'invalid_request')
    for key in ('last_attempt_by_store','last_verified_success_by_store'):
        records=value[key]; require(type(records) is dict and set(records) <= VALIDATORS.keys(), 'invalid_request')
        for store, record in records.items():
            result(record)
            require(record['store_id']==store and (key!='last_verified_success_by_store' or record['result']=='passed')
                and any(job['audit_result']==record for job in value['jobs']), 'invalid_request')
    c.encode(value)
    return value


def make_result(job, kind, reason, *, snapshot=None, duration_ms=0):
    value = dict(fixture_only=False, **{name: job[name] for name in ('job_id','store_id','run_id',
        'attempt_id','claim_epoch','method_version','validator_version','source_generation')},
        completed_at=c.utc(), result=kind, reason_code=reason, snapshot_metadata=snapshot,
        snapshot_id=hashlib.sha256(c.encode(snapshot)).hexdigest() if snapshot is not None else None,
        duration_ms=duration_ms)
    return result(value)
