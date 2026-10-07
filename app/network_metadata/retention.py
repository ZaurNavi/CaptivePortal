"""Bounded NI retention, never an active-generation or capacity override."""
from datetime import timedelta
from .models import RETENTION_MAX_BATCHES_PER_PASS
from .validation import ni_format_utc, ni_timestamp


class RetentionPolicy:
    def __init__(self, repository):
        self.repository = repository

    def expire_touched_identity(self, generation_id, offset, transaction_now):
        """Due retention for one proven existing identity, inside its ingest transaction."""
        row = self.repository.connection.execute(
            "SELECT o.observation_id,o.event_at,o.ingested_at FROM network_metadata_observations o "
            "JOIN network_metadata_source_records r ON r.observation_id=o.observation_id "
            "WHERE r.source_generation_id=? AND r.record_start_byte_offset=?", (generation_id, offset)).fetchone()
        if row is None:
            return
        now = ni_timestamp(transaction_now, canonical=True)
        oldest = min(ni_timestamp(row[1], canonical=True), ni_timestamp(row[2], canonical=True))
        if oldest < now - timedelta(days=30):
            self._delete("core", [row[0]])
        elif oldest < now - timedelta(days=14):
            self._delete("sensitive", [row[0]])

    def run(self):
        repo = self.repository
        now = repo.clock()
        cutoffs = {days: ni_format_utc(now - timedelta(days=days)) for days in (14, 30, 45, 90)}
        totals = dict(sensitive=0, core=0, health=0, faults=0, generations=0, bindings=0, runs=0)
        classes = tuple(totals)
        remaining_batches = RETENTION_MAX_BATCHES_PER_PASS
        for category in classes:
            while remaining_batches > 0:
                if repo.footprint()["combined"] + max(16777216, 8 * repo.config.batch_max_bytes) > repo.config.max_db_bytes:
                    return totals
                ids = self._select(category, cutoffs)
                if not ids:
                    break
                with repo.transaction():
                    self._delete(category, ids)
                totals[category] += len(ids)
                remaining_batches -= 1
            if remaining_batches == 0:
                break
        repo.emit("retention_completed", count=sum(totals.values()))
        return totals

    def _select(self, kind, cutoff):
        conn = self.repository.connection
        if kind in {"sensitive", "core"}:
            age = cutoff[14 if kind == "sensitive" else 30]
            extra = " AND sensitive_endpoint_presence_state!='expired'" if kind == "sensitive" else ""
            return [row[0] for row in conn.execute(
                "SELECT observation_id FROM network_metadata_observations WHERE (event_at<? OR ingested_at<?)" + extra +
                " ORDER BY observation_id LIMIT 5000", (age, age))]
        if kind == "health":
            return [row[0] for row in conn.execute("""SELECT health_id FROM network_metadata_source_health
                WHERE evaluated_at<? AND NOT EXISTS(SELECT 1 FROM network_metadata_observations o WHERE o.source_health_ref=health_id)
                ORDER BY health_id LIMIT 5000""", (cutoff[45],))]
        if kind == "faults":
            return [row[0] for row in conn.execute("SELECT rowid FROM network_metadata_ingest_fault_aggregates WHERE last_seen_utc<? ORDER BY rowid LIMIT 5000", (cutoff[45],))]
        if kind == "generations":
            return [row[0] for row in conn.execute("""SELECT source_generation_id FROM network_metadata_source_generations g
                WHERE closed_at_utc<? AND processing_state='runnable'
                AND NOT EXISTS(SELECT 1 FROM network_metadata_checkpoint c WHERE c.source_generation_id=g.source_generation_id)
                AND NOT EXISTS(SELECT 1 FROM network_metadata_observations o WHERE o.source_generation_id=g.source_generation_id)
                AND NOT EXISTS(SELECT 1 FROM network_metadata_source_records r WHERE r.source_generation_id=g.source_generation_id)
                AND NOT EXISTS(SELECT 1 FROM network_metadata_source_health h WHERE h.source_generation_id=g.source_generation_id)
                AND NOT EXISTS(SELECT 1 FROM network_metadata_ingest_fault_aggregates f WHERE f.source_generation_id=g.source_generation_id)
                ORDER BY g.source_generation_id LIMIT 5000""", (cutoff[90],))]
        if kind == "bindings":
            current = self.repository.config.capture_scope_binding.binding_digest
            return [row[0] for row in conn.execute("""SELECT binding_digest FROM network_metadata_capture_scope_bindings b
                WHERE valid_from_utc<? AND binding_digest!=?
                AND NOT EXISTS(SELECT 1 FROM network_metadata_source_generations g WHERE g.capture_scope_binding_digest=b.binding_digest)
                AND NOT EXISTS(SELECT 1 FROM network_metadata_observations o WHERE o.capture_scope_binding_digest=b.binding_digest)
                ORDER BY b.binding_digest LIMIT 5000""", (cutoff[90], current))]
        return [row[0] for row in conn.execute("""SELECT ingest_run_id FROM network_metadata_ingest_runs r
            WHERE started_at_utc<? AND NOT EXISTS(SELECT 1 FROM network_metadata_observations o WHERE o.ingest_run_id=r.ingest_run_id)
            ORDER BY r.ingest_run_id LIMIT 5000""", (cutoff[90],))]

    def _delete(self, kind, ids):
        conn = self.repository.connection
        placeholders = ",".join("?" for _ in ids)
        if kind == "sensitive":
            for table in ("sensitive_endpoints", "dns_queries", "dns_answers"):
                conn.execute(f"DELETE FROM network_metadata_{table} WHERE observation_id IN ({placeholders})", ids)
            for table, fields in (("dns", ("query_names_presence_state", "answer_values_presence_state")),
                                  ("tls", ("sni_presence_state",)), ("quic", ("sni_presence_state",))):
                assignments = [f"{field}=CASE WHEN {field}='observed_retained' THEN 'expired' ELSE {field} END" for field in fields]
                if table != "dns":
                    assignments.append("sni=NULL")
                conn.execute(f"UPDATE network_metadata_{table} SET {','.join(assignments)} WHERE observation_id IN ({placeholders})", ids)
            conn.execute(f"UPDATE network_metadata_observations SET sensitive_endpoint_presence_state='expired' WHERE observation_id IN ({placeholders})", ids)
            conn.execute(f"UPDATE network_metadata_source_records SET digest_state='expired',source_record_sha256=NULL,semantic_payload_sha256=NULL WHERE observation_id IN ({placeholders})", ids)
        else:
            table, field = {"core": ("observations", "observation_id"), "health": ("source_health", "health_id"),
                "faults": ("ingest_fault_aggregates", "rowid"), "generations": ("source_generations", "source_generation_id"),
                "bindings": ("capture_scope_bindings", "binding_digest"), "runs": ("ingest_runs", "ingest_run_id")}[kind]
            conn.execute(f"DELETE FROM network_metadata_{table} WHERE {field} IN ({placeholders})", ids)
