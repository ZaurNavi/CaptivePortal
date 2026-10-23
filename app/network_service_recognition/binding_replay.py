"""B1 consumer contract: deterministic jobs + cursor in one owned transaction."""
from datetime import timedelta
from hashlib import sha256
from app.network_metadata.validation import canonical_uuid, integer, ni_timestamp, ni_format_utc
from app.network_attribution.validation import canonical_mac
from app.device_fingerprint.validation import validate_site_id
from .canonical import canonical_json


class BindingReplayConflict(RuntimeError):
    def __init__(self):
        super().__init__("binding_replay_lineage_conflict")


def replay_identity(generation_id, change):
    canonical_uuid(generation_id)
    integer(change.change_seq, 1)
    validate_site_id(change.site_id)
    canonical_uuid(change.device_id)
    if canonical_mac(change.client_mac) != change.client_mac:
        raise BindingReplayConflict()
    frozen = dict(generation_id=generation_id, binding_change_seq=change.change_seq,
                  site_id=change.site_id, client_mac=change.client_mac, device_id=change.device_id)
    return sha256(canonical_json(frozen)).hexdigest(), frozen


def enqueue_binding_changes(repository, generation_id, after_change_seq, changes, evaluated_at_utc):
    """The repository supplies its capacity-checked single-writer transaction."""
    canonical_uuid(generation_id)
    integer(after_change_seq)
    at = ni_timestamp(evaluated_at_utc, canonical=True)
    if type(changes) is not tuple or len(changes) > 128:
        raise BindingReplayConflict()
    if not changes:
        return False
    from_utc, to_utc = ni_format_utc(at - timedelta(days=1)), ni_format_utc(at)
    jobs = [replay_identity(generation_id, change) for change in changes]
    sequences = [frozen["binding_change_seq"] for _, frozen in jobs]
    if sequences != sorted(set(sequences)) or sequences[0] <= after_change_seq:
        raise BindingReplayConflict()
    with repository.transaction():
        connection = repository.connection
        checkpoint = connection.execute(
            "SELECT last_binding_change_seq FROM service_materialization_checkpoints WHERE generation_id=?",
            (generation_id,)).fetchone()
        if checkpoint is None or checkpoint[0] != after_change_seq:
            raise BindingReplayConflict()
        for job_id, frozen in jobs:
            row = connection.execute(
                "SELECT job_id,generation_id,binding_change_seq,site_id,client_mac,device_id "
                "FROM service_binding_replay_jobs WHERE job_id=? OR (generation_id=? AND binding_change_seq=?)",
                (job_id, generation_id, frozen["binding_change_seq"])).fetchone()
            if row is not None:
                if tuple(row) != (job_id, *frozen.values()):
                    raise BindingReplayConflict()
            else:
                connection.execute(
                    "INSERT INTO service_binding_replay_jobs"
                    "(job_id,generation_id,binding_change_seq,site_id,client_mac,device_id,"
                    "from_utc,to_utc,cursor_event_at,cursor_edge_id,state) "
                    "VALUES(?,?,?,?,?,?,?,?,NULL,NULL,'pending')",
                    (job_id, *frozen.values(), from_utc, to_utc))
                repository.append_visit_delivery('binding',evaluated_at_utc,site_id=frozen['site_id'],
                    device_id=frozen['device_id'],client_mac=frozen['client_mac'],binding_seq=frozen['binding_change_seq'])
            repository.crash_point("binding_job_enqueued")
        connection.execute(
            "UPDATE service_materialization_checkpoints SET last_binding_change_seq=?,updated_at_utc=? "
            "WHERE generation_id=? AND last_binding_change_seq=?",
            (sequences[-1], evaluated_at_utc, generation_id, after_change_seq))
    return True


def read_targeted_replay_page(reader, job, *, deadline):
    """Replay can read only the exact Site+MAC persisted in its durable job."""
    validate_site_id(job["site_id"])
    canonical_uuid(job["device_id"])
    if canonical_mac(job["client_mac"]) != job["client_mac"]:
        raise BindingReplayConflict()
    cursor = None
    if job["cursor_event_at"] is not None or job["cursor_edge_id"] is not None:
        if job["cursor_event_at"] is None or job["cursor_edge_id"] is None:
            raise BindingReplayConflict()
        cursor = (job["cursor_event_at"], job["cursor_edge_id"])
    return reader.read_candidate_page(job["site_id"], job["from_utc"], job["to_utc"],
        client_mac=job["client_mac"], cursor=cursor, limit=128, deadline=deadline)
