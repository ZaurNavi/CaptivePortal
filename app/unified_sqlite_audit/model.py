"""One catalog and two independent assurance axes; public DTOs contain no paths."""
from dataclasses import dataclass
from datetime import datetime, timezone
import copy
import json
import re
import uuid

from app.admin_web.operations_inventory import STORES

LIMIT = 131072
PHYSICAL = frozenset({'NOT_EVALUATED','NOT_ADMITTED','RUNNING','PASS','INTEGRITY_FAIL','FK_FAIL',
    'UNAVAILABLE','INCOMPLETE','RESOURCE_BLOCKED','STALE'})
DOMAIN = frozenset({'NOT_EVALUATED','NOT_ADMITTED','RUNNING','PASS','FAIL','INCOMPLETE','STALE'})
TERMINAL_PHYSICAL = frozenset({'PASS','INTEGRITY_FAIL','FK_FAIL'})


class AuditError(ValueError):
    def __init__(self, reason='audit_unavailable'):
        super().__init__(reason)
        self.reason = reason


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')


def identifier(value):
    try:
        return type(value) is str and str(uuid.UUID(value)) == value
    except (ValueError, AttributeError):
        return False


def bounded(value, minimum=0):
    return type(value) is int and minimum <= value <= 2**53-1


@dataclass(frozen=True)
class AdmittedStore:
    """Private, owner-qualified job. Never a public DTO or filename discovery."""
    store_id: str
    path: str
    source_id: str
    uid: int
    gid: int
    max_snapshot_bytes: int
    host_memory_budget_bytes: int
    no_competing_audit: bool
    domain_validator_id: str | None = None
    # An external owner/SysAdmin qualification, not inferred from the manifest.
    cgroup: str | None = None


FAST = frozenset({'NOT_EVALUATED','FAST_PASS','FAST_FAIL','UNAVAILABLE','DISABLED',
    'UNKNOWN','STALE','NEW_EMPTY','CONFLICT'})
DEEP = frozenset({'NOT_EVALUATED','NOT_ADMITTED','DISABLED','QUEUED','RUNNING','PASSED',
    'DOMAIN_FAIL','INTEGRITY_FAIL','FK_FAIL','INCOMPLETE','RESOURCE_DEFERRED','UNAVAILABLE',
    'STALE','ORPHAN_HOLD'})
CYCLES = frozenset({'NOT_STARTED','RUNNING','COMPLETE','PARTIAL','BLOCKED','INTERRUPTED',
    'BLOCKED_NO_TRUSTED_BINDINGS','DISABLED','ORPHAN_HOLD'})
REASONS = frozenset({'not_started','manifest_unavailable_or_invalid','feature_off',
    'invalid_flag','not_evaluated','no_trusted_bindings','owner_qualification_absent',
    'owner_disabled','duplicate_or_gate_unresolved','binding_mismatch','owner_uid_not_admitted',
    'source_identity_mismatch','source_metadata_unavailable','owner_qualified',
    'domain_validator_absent','domain_failed','physical_failed','verified','running','complete',
    'incomplete','cancelled','resource_unqualified','source_unavailable','source_changed',
    'release_unproven','journal_invalid','prior_incomplete','ready_unproven','worker_failed'})


def enabled(settings):
    """Do not re-read environment or turn an invalid flag into a startup failure."""
    raw = settings.get('sqlite_unified_audit_enabled', 'false')
    return type(raw) is str and raw == 'true'


def digest(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def timestamp(value):
    if type(value) is not str or len(value) != 24:
        return False
    try:
        return datetime.strptime(value, '%Y-%m-%dT%H:%M:%S.%fZ').strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]+'Z' == value
    except ValueError:
        return False


def catalog(enabled=False, *, portal_run_id=None, bound=False):
    return dict(api_version='audit.unified.v1',catalog_version='operations.stores.v1',
        portal_run_id=portal_run_id,audit_cycle_id=None,generated_at=stamp(),
        cycle_state='NOT_STARTED' if enabled and bound else 'BLOCKED_NO_TRUSTED_BINDINGS' if enabled else 'DISABLED',
        reason='not_started' if enabled and bound else 'manifest_unavailable_or_invalid' if enabled else 'feature_off',
        phase1='NOT_EVALUATED' if bound else 'UNAVAILABLE' if enabled else 'DISABLED',
        stores=[dict(store_id=item.id,owner_service_ids=list(item.services),kind=item.kind,
            binding='UNKNOWN',effective_path_identity=None,effective_enabled=None,
            admission='NOT_ADMITTED',admission_reason='no_trusted_bindings',
            eligible_physical=None if not bound else False,eligible_domain=None if not bound else False,
            fast=dict(state='NOT_EVALUATED',scopes=[],source='none',checked_at=None),
            deep=dict(state='NOT_EVALUATED',method=None,snapshot_id=None,snapshot_at=None,verified_at=None,
                physical_verdict='NOT_EVALUATED',domain_verdict='NOT_EVALUATED',integrity=None,fk=None,
                domain_t3=None,reason='not_evaluated',duration_ms=None,source_generation=None,
                assurance_scope=None,source_observation_before=None,source_observation_snapshot=None,
                source_observation_after=None,live_freshness='UNKNOWN',snapshot_receipt=None),
            last_verified_physical_success=None,last_verified_domain_success=None,last_verified_success=None,
            freshness='UNKNOWN') for item in STORES])


def validate(value):
    """Closed public outcome shape, bounded JSON, no arbitrary reason/error text."""
    expected = set(catalog()) | {'summary'}
    if type(value) is not dict or set(value) != expected or value.get('api_version') != 'audit.unified.v1':
        raise AuditError('invalid_status')
    if (value['catalog_version'] != 'operations.stores.v1' or value['cycle_state'] not in CYCLES
            or value['reason'] not in REASONS or not timestamp(value['generated_at'])
            or value['phase1'] not in FAST or
            any(value[k] is not None and not identifier(value[k]) for k in ('portal_run_id','audit_cycle_id'))):
        raise AuditError('invalid_status')
    if type(value['stores']) is not list or any(type(r) is not dict for r in value['stores']) or [r.get('store_id') for r in value['stores']] != [s.id for s in STORES]:
        raise AuditError('invalid_status')
    template = catalog()['stores'][0]
    for item,row in zip(STORES,value['stores']):
        if type(row) is not dict or set(row) != set(template) or set(row['fast']) != set(template['fast']) or set(row['deep']) != set(template['deep']):
            raise AuditError('invalid_status')
        deep = row['deep']
        if (row['owner_service_ids'] != list(item.services) or row['kind'] != item.kind
                or row['binding'] not in {'UNKNOWN','BOUND'} or row['admission'] not in {'NOT_ADMITTED','ADMITTED'}
                or row['admission_reason'] not in REASONS or row['freshness'] not in {'UNKNOWN','CURRENT','HISTORICAL','STALE'}
                or row['effective_path_identity'] is not None and not digest(row['effective_path_identity'])
                or row['fast']['state'] not in FAST or row['fast']['source'] not in {'none','qualified_metadata'}
                or row['fast']['scopes'] not in ([],['file_metadata'])
                or row['fast']['checked_at'] is not None and not timestamp(row['fast']['checked_at'])
                or deep['state'] not in DEEP or deep['reason'] not in REASONS
                or deep['method'] not in {None,'sqlite_online_backup_ram_v1'}
                or deep['duration_ms'] is not None and not bounded(deep['duration_ms'])
                or deep['source_generation'] is not None and not digest(deep['source_generation'])):
            raise AuditError('invalid_status')
        if (deep['assurance_scope'] not in {None,'SNAPSHOT_ONLY'} or
                deep['live_freshness'] not in {'UNKNOWN','UNCHANGED_OBSERVATION','ADVANCED'} or
                any(deep[k] is not None and not digest(deep[k]) for k in
                    ('source_observation_before','source_observation_snapshot','source_observation_after'))):
            raise AuditError('invalid_status')
        for key in ('snapshot_id',):
            if deep[key] is not None and not identifier(deep[key]):raise AuditError('invalid_status')
        for key in ('snapshot_at','verified_at'):
            if deep[key] is not None and not timestamp(deep[key]):raise AuditError('invalid_status')
        for key in ('integrity','fk','domain_t3'):
            if deep[key] not in {None,'PASS','FAIL','NOT_ADMITTED'}:raise AuditError('invalid_status')
        if deep['physical_verdict'] not in PHYSICAL or deep['domain_verdict'] not in DOMAIN:
            raise AuditError('invalid_status')
        if any(type(row[key]) is not bool and row[key] is not None for key in ('eligible_physical','eligible_domain','effective_enabled')):
            raise AuditError('invalid_status')
        # Receipts exposed here are closed, sanitized identities, never private paths/results.
        for receipt in (row['last_verified_physical_success'],row['last_verified_domain_success'],
                        row['last_verified_success'],deep['snapshot_receipt']):
            if receipt is not None and (type(receipt) is not dict or set(receipt) != {'snapshot_id','source_id','portal_run_id','verified_at','method'}):
                raise AuditError('invalid_status')
            if receipt is not None and (not identifier(receipt['snapshot_id']) or not identifier(receipt['portal_run_id'])
                    or not digest(receipt['source_id']) or not timestamp(receipt['verified_at'])
                    or receipt['method'] != 'sqlite_online_backup_ram_v1'):
                raise AuditError('invalid_status')
        if row['last_verified_success'] != row['last_verified_domain_success']:
            raise AuditError('invalid_status')
        if deep['physical_verdict']=='PASS':
            receipt=deep['snapshot_receipt']
            if (deep['integrity']!='PASS' or deep['fk']!='PASS' or receipt is None
                    or receipt['snapshot_id']!=deep['snapshot_id'] or receipt['verified_at']!=deep['verified_at']
                    or receipt['portal_run_id']!=value['portal_run_id']
                    or receipt['source_id']!=row['effective_path_identity']
                    or deep['assurance_scope']!='SNAPSHOT_ONLY'
                    or any(deep[k] is None for k in ('source_observation_before','source_observation_snapshot','source_observation_after'))
                    or row['eligible_physical'] is not True):
                raise AuditError('invalid_status')
        if deep['domain_verdict']=='PASS' and (deep['physical_verdict']!='PASS' or deep['domain_t3']!='PASS'
                or row['eligible_domain'] is not True):
            raise AuditError('invalid_status')
        if deep['live_freshness']=='ADVANCED' and row['freshness']=='CURRENT':raise AuditError('invalid_status')
    raw = json.dumps(value,allow_nan=False,separators=(',',':')).encode()
    if len(raw) > LIMIT:
        raise AuditError('status_limit')
    if json.dumps(value['summary'],sort_keys=True)!=json.dumps(_summary(value['stores']),sort_keys=True):
        raise AuditError('invalid_status')
    return value


def _summary(rows):
    physical = [r for r in rows if r['eligible_physical'] is True]
    domain = [r for r in rows if r['eligible_domain'] is True]
    unknown = any(r['eligible_physical'] is None for r in rows)
    return dict(assurance_scope='SNAPSHOT_ONLY',live_integrity_verified=False,
        registered_logical=len(STORES),bound=sum(r['binding']=='BOUND' for r in rows),
        eligible_physical_count=None if unknown else len(physical),eligible_domain_count=None if unknown else len(domain),
        evaluated=sum(r['deep']['physical_verdict'] in TERMINAL_PHYSICAL for r in rows),
        physical_coverage_complete=None if unknown else bool(physical) and all(r['deep']['physical_verdict'] in TERMINAL_PHYSICAL for r in physical),
        domain_coverage_complete=None if unknown else bool(domain) and all(r['deep']['domain_verdict'] in {'PASS','FAIL'} for r in domain),
        physical={s:sum(r['deep']['physical_verdict']==s for r in rows) for s in sorted(PHYSICAL)},
        domain={s:sum(r['deep']['domain_verdict']==s for r in rows) for s in sorted(DOMAIN)})


def project(value):
    result = copy.deepcopy(value)
    result['generated_at'] = stamp()
    result['summary'] = _summary(result['stores'])
    return validate(result)
