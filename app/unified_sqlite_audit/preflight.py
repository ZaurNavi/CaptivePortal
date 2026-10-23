"""Bounded metadata only. Inventory is a binding, not owner/RO admission."""
import os
import stat
from app.admin_web.operations_inventory import STORES, load_inventory
from app.operations_verification import PORTAL, snapshot, project as owner_project, opaque_identity
from .model import AdmittedStore, catalog, stamp


def prepare(enabled, portal_run_id, *, inventory_loader=load_inventory, qualifications=(),
            lstat=os.lstat, owner_snapshot=snapshot):
    result = catalog(enabled,portal_run_id=portal_run_id)
    if not enabled:
        return result, {}, None
    try:
        inventory = inventory_loader()
    except Exception:
        return result, {}, None
    result = catalog(True,portal_run_id=portal_run_id,bound=True)
    evidence = owner_snapshot(PORTAL,refresh=False)['checks']
    admitted = {}
    # Only explicit qualified jobs can cause a source stat; never inspect other owners opportunistically.
    supplied = {q.store_id:q for q in qualifications if isinstance(q,AdmittedStore)}
    if len(supplied)!=len(qualifications):
        supplied={}  # Duplicate/unknown qualifications never silently select a winner.
    for item,row in zip(STORES,result['stores']):
        intent = inventory.store_intents[item.id]
        row.update(binding='BOUND',effective_enabled=False if intent=='optional_disabled' else None,
            eligible_physical=False,eligible_domain=False,admission_reason='owner_qualification_absent')
        if intent=='optional_disabled':
            row['fast']['state']='DISABLED';row['deep'].update(state='DISABLED',reason='owner_disabled')
            continue
        q = supplied.get(item.id)
        if intent!='expected' or q is None:
            continue
        if q.path != inventory.paths[item.id] or not q.no_competing_audit:
            row['admission_reason']='duplicate_or_gate_unresolved' if not q.no_competing_audit else 'binding_mismatch'
            continue
        try:
            if q.uid != os.geteuid() or q.gid != os.getegid():
                row['admission_reason']='owner_uid_not_admitted';continue
            info = lstat(q.path)
            current = opaque_identity(info)
            if not stat.S_ISREG(info.st_mode) or current != q.source_id:
                row['fast']['state']='CONFLICT';row['admission_reason']='source_identity_mismatch';continue
            row.update(effective_path_identity=current,effective_enabled=True,eligible_physical=True,admission='ADMITTED',admission_reason='owner_qualified')
            row['fast'].update(state='FAST_PASS',scopes=['file_metadata'],source='qualified_metadata',checked_at=stamp())
            record = evidence.get(item.id)
            observed = owner_project(item.id,None if record is None else dict(row=record),current,
                intent=intent,source_current=True)
            # Do not relabel a previously executed Q/F/history scan as fast metadata.
            if observed['status']=='failed':
                row['fast']['state']='FAST_FAIL'
                row.update(eligible_physical=False,admission='NOT_ADMITTED',admission_reason='duplicate_or_gate_unresolved')
            else:admitted[item.id] = q
        except (OSError,ValueError,AttributeError):
            row['fast']['state']='UNAVAILABLE';row['admission_reason']='source_metadata_unavailable'
    states=[r['fast']['state'] for r in result['stores']]
    result['phase1']='FAST_FAIL' if 'FAST_FAIL' in states else 'UNAVAILABLE' if any(s in {'UNAVAILABLE','CONFLICT'} for s in states) else 'FAST_PASS' if admitted else 'NOT_EVALUATED'
    return result, admitted, inventory
