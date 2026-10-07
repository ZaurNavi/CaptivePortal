"""Single-writer NI store. No source payload and no repair/migration path."""
import os
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone

from .canonical import ni01_canonical_json
from .models import (LOGICAL_SOURCE_ID, NORMALIZER_VERSION, CONFLICT_CATEGORIES,
    FAULT_CATEGORIES, SourceGenerationV1, SourceCheckpointV1,
    NetworkMetadataStorageUnavailable, NetworkMetadataStorageCorrupt,
    NetworkMetadataStorageLimit, NetworkMetadataWriterUnavailable,
    NetworkMetadataValidationError)
from .schema import TABLE_DDL, create_schema, validate_schema
from .validation import integer, digest, canonical_uuid, ni_format_utc, ni_timestamp


class WriterLock:
    def __init__(self, path):
        self.path, self.fd = path, None

    def __enter__(self):
        import fcntl
        try:
            self.fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o640)
            os.fchmod(self.fd, 0o640)
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.__exit__(None, None, None)
            raise NetworkMetadataWriterUnavailable() from None
        return self

    def __exit__(self, *_):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


class NetworkMetadataRepository:
    def __init__(self, config, *, clock=lambda: datetime.now(timezone.utc), telemetry=None):
        self.config, self.clock, self.telemetry = config, clock, telemetry
        self.connection = None
        self.capacity_halted = False

    def emit(self, event, **fields):
        if self.telemetry is not None:
            self.telemetry.emit(event, **fields)

    def initialize(self):
        try:
            self.connection = sqlite3.connect(self.config.db_path, timeout=.5, isolation_level=None)
            self.connection.row_factory = sqlite3.Row
            for pragma in ("foreign_keys=ON", "busy_timeout=500", "journal_mode=WAL",
                           "synchronous=FULL", "wal_autocheckpoint=1000", "journal_size_limit=67108864"):
                self.connection.execute("PRAGMA " + pragma)
            existing = self.connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            if not existing:
                if (self.connection.execute("PRAGMA user_version").fetchone()[0] != 0
                        or self.connection.execute("SELECT count(*) FROM sqlite_master").fetchone()[0] != 0):
                    raise NetworkMetadataStorageCorrupt()
                with self.transaction():
                    create_schema(self.connection, ni_format_utc(self.clock()))
            validate_schema(self.connection)
            page_size = self.connection.execute("PRAGMA page_size").fetchone()[0]
            cap = self.config.max_db_bytes // page_size
            if self.connection.execute("PRAGMA page_count").fetchone()[0] > cap:
                raise NetworkMetadataStorageLimit()
            accepted = self.connection.execute(f"PRAGMA max_page_count={cap}").fetchone()[0]
            if accepted > cap:
                raise NetworkMetadataStorageLimit()
            if self.footprint()["combined"] > self.config.max_db_bytes:
                raise NetworkMetadataStorageLimit()
            self.load_active()
        except (sqlite3.Error, OSError):
            self.close()
            raise NetworkMetadataStorageUnavailable() from None
        return self

    def close(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def recover(self):
        self.close()
        self.initialize()
        return self.load_active()

    @contextmanager
    def transaction(self):
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            now = ni_format_utc(self.clock())
            yield now
            self.connection.execute("COMMIT")
        except BaseException as error:
            if self.connection is not None and self.connection.in_transaction:
                self.connection.execute("ROLLBACK")
            if isinstance(error, (sqlite3.Error, OSError)):
                raise NetworkMetadataStorageUnavailable() from None
            raise

    def _insert(self, table, values):
        if table not in TABLE_DDL:
            raise NetworkMetadataValidationError()
        columns = {row[1] for row in self.connection.execute(f"PRAGMA table_info({table})")}
        if not set(values) <= columns:
            raise NetworkMetadataValidationError()
        names = ",".join(values)
        self.connection.execute(f"INSERT INTO {table} ({names}) VALUES ({','.join('?' for _ in values)})",
                                tuple(values.values()))

    def persist_binding(self, binding):
        values = asdict(binding)
        values["ipv4_cidrs_json"] = ni01_canonical_json(list(values.pop("ipv4_cidrs"))).decode("utf-8")
        columns = ("binding_digest", "schema_version", "capture_source_id", "site_id",
                   "network_scope_id", "ipv4_cidrs_json", "valid_from_utc")
        with self.transaction():
            row = self.connection.execute("SELECT " + ",".join(columns) + " FROM network_metadata_capture_scope_bindings WHERE binding_digest=?",
                                          (binding.binding_digest,)).fetchone()
            if row is None:
                self._insert("network_metadata_capture_scope_bindings", values)
            elif tuple(row) != tuple(values[column] for column in columns):
                raise NetworkMetadataStorageCorrupt()

    def create_ingest_run(self, identity):
        digest(identity.artifact_sha, 40)
        digest(identity.artifact_tree, 40)
        run_id = str(uuid.uuid4())
        with self.transaction() as now:
            self._insert("network_metadata_ingest_runs", dict(ingest_run_id=run_id,
                started_at_utc=now, repository_head=identity.artifact_sha,
                repository_tree=identity.artifact_tree, normalizer_version=NORMALIZER_VERSION,
                configuration_digest=self.config.configuration_digest))
        return run_id

    def load_active(self):
        try:
            rows = self.connection.execute("SELECT * FROM network_metadata_source_generations WHERE closed_at_utc IS NULL").fetchall()
            checkpoints = self.connection.execute("SELECT * FROM network_metadata_checkpoint").fetchall()
            if len(rows) > 1 or len(checkpoints) > 1:
                raise NetworkMetadataStorageCorrupt()
            generation = SourceGenerationV1(**dict(rows[0])) if rows else None
            checkpoint = SourceCheckpointV1(**dict(checkpoints[0])) if checkpoints else None
            if generation is None:
                if checkpoint is not None:
                    raise NetworkMetadataStorageCorrupt()
                return None, None
            canonical_uuid(generation.source_generation_id, 4)
            canonical_uuid(generation.host_boot_id)
            ni_timestamp(generation.opened_at_utc, canonical=True)
            if (generation.logical_source_id != LOGICAL_SOURCE_ID or checkpoint is None
                    or checkpoint.logical_source_id != LOGICAL_SOURCE_ID
                    or checkpoint.source_generation_id != generation.source_generation_id
                    or checkpoint.committed_byte_offset != generation.committed_byte_offset
                    or checkpoint.continuity_anchor_start_offset + checkpoint.continuity_anchor_length != checkpoint.committed_byte_offset
                    or checkpoint.continuity_anchor_length != min(4096, checkpoint.committed_byte_offset)):
                raise NetworkMetadataStorageCorrupt()
            if checkpoint.continuity_anchor_length:
                digest(checkpoint.continuity_anchor_sha256)
            elif checkpoint.continuity_anchor_sha256 is not None:
                raise NetworkMetadataStorageCorrupt()
            return generation, checkpoint
        except (sqlite3.Error, TypeError, NetworkMetadataValidationError):
            raise NetworkMetadataStorageCorrupt() from None

    def transition_generation(self, *, binding, boot_id, physical, start=0, anchor=(0, 0, None),
                              close_reason=None, gap=False, end=None, tail_start=None):
        old, checkpoint = self.load_active()
        if old is not None and old.processing_state != "runnable":
            raise NetworkMetadataStorageCorrupt()
        integer(start)
        canonical_uuid(boot_id)
        generation_id = str(uuid.uuid4()) if physical is not None else None
        with self.transaction() as now:
            if old is not None:
                if close_reason is None:
                    raise NetworkMetadataValidationError()
                final_offset = checkpoint.committed_byte_offset if end is None else integer(end, checkpoint.committed_byte_offset)
                if tail_start is not None:
                    self._fault(old.source_generation_id, "partial_final_record", now, tail_start)
                self.connection.execute("DELETE FROM network_metadata_checkpoint WHERE logical_source_id=?", (LOGICAL_SOURCE_ID,))
                self.connection.execute("UPDATE network_metadata_source_generations SET closed_at_utc=?,close_reason=?,end_offset=?,committed_byte_offset=?,coverage_gap_possible=? WHERE source_generation_id=?",
                    (now, close_reason, final_offset, final_offset, int(gap), old.source_generation_id))
            if physical is not None:
                dev, ino = physical
                self._insert("network_metadata_source_generations", dict(source_generation_id=generation_id,
                    logical_source_id=LOGICAL_SOURCE_ID, host_boot_id=boot_id, st_dev=integer(dev), st_ino=integer(ino),
                    generation_start_offset=start, committed_byte_offset=start, end_offset=None,
                    capture_scope_binding_schema_version=1, capture_scope_binding_digest=binding.binding_digest,
                    binding_valid_from_utc=binding.valid_from_utc, opened_at_utc=now, closed_at_utc=None,
                    close_reason=None, coverage_gap_possible=0, processing_state="runnable",
                    blocked_reason_code=None, blocked_at_utc=None, blocked_record_start_byte_offset=None))
                self._insert("network_metadata_checkpoint", dict(logical_source_id=LOGICAL_SOURCE_ID,
                    source_generation_id=generation_id, committed_byte_offset=start,
                    continuity_anchor_start_offset=anchor[0], continuity_anchor_length=anchor[1],
                    continuity_anchor_sha256=anchor[2], updated_at_utc=now))
        if old is not None:
            self.emit("source_generation_closed", source_generation_id=old.source_generation_id, reason_code=close_reason)
        if generation_id:
            self.emit("source_generation_opened", source_generation_id=generation_id)
        return self.load_active()

    def latest_health(self, capture_source_id=None):
        source = self.config.capture_scope_binding.capture_source_id if capture_source_id is None else capture_source_id
        return self.connection.execute("SELECT * FROM network_metadata_source_health WHERE capture_source_id=? ORDER BY evaluated_at DESC,rowid DESC LIMIT 1", (source,)).fetchone()

    def latest_closed_generation_gap_possible(self):
        row = self.connection.execute("SELECT coverage_gap_possible FROM network_metadata_source_generations "
            "WHERE logical_source_id=? AND closed_at_utc IS NOT NULL ORDER BY rowid DESC LIMIT 1", (LOGICAL_SOURCE_ID,)).fetchone()
        return bool(row[0]) if row is not None else False

    def insert_health(self, snapshot):
        values = asdict(snapshot)
        values["reason_codes_json"] = ni01_canonical_json(list(values.pop("reason_codes"))).decode("utf-8")
        self._insert("network_metadata_source_health", values)

    def persist_health(self, controller, generation, *, force=False):
        candidate = controller.copy()
        previous = controller.last_snapshot
        with self.transaction() as now:
            result = candidate.ensure(self, generation, now, force=force)
        controller.adopt(candidate)
        if previous is None or result != previous.health_id:
            self.emit("health_heartbeat" if force else "health_transition", metadata_ingest_health=controller.ingest,
                      metadata_output_health=controller.output, capture_health=controller.capture)
        return result

    def _fault(self, generation_id, category, now, offset):
        if category not in FAULT_CATEGORIES:
            raise NetworkMetadataValidationError()
        clock = ni_timestamp(now, canonical=True)
        epoch = ni_format_utc(clock.replace(minute=clock.minute - clock.minute % 5, second=0, microsecond=0))
        self.connection.execute("""INSERT INTO network_metadata_ingest_fault_aggregates
            VALUES(?,?,?,?,?,1,?,?,?,?) ON CONFLICT(logical_source_id,source_generation_key,fault_category,aggregation_epoch_start_utc)
            DO UPDATE SET count=count+1,last_seen_utc=excluded.last_seen_utc,last_relevant_offset=excluded.last_relevant_offset""",
            (LOGICAL_SOURCE_ID, generation_id or "none", generation_id, category, epoch, now, now, offset, offset))

    def identity_outcome(self, generation_id, outcome):
        row = self.connection.execute("SELECT digest_state,source_record_sha256,semantic_payload_sha256 FROM network_metadata_source_records WHERE source_generation_id=? AND record_start_byte_offset=?",
                                      (generation_id, outcome.start)).fetchone()
        if row is None:
            return "new"
        if row[0] == "expired":
            return "replay_identity_evidence_expired"
        if row[1] != outcome.source_record_sha256:
            return "source_record_identity_conflict"
        if outcome.normalized is None:
            return "normalizer_determinism_conflict"
        if row[2] != outcome.normalized.semantic_payload_sha256:
            return "normalizer_determinism_conflict"
        return "duplicate_noop"

    def _crash_point(self, label):
        """Private no-op injection boundary. Never configured in production."""

    def ingest_batch(self, outcomes, run_id, controller, anchor_provider):
        generation, checkpoint = self.load_active()
        if generation is None or generation.processing_state != "runnable":
            raise NetworkMetadataStorageCorrupt()
        if not outcomes:
            return dict(committed=0, duplicates=0, blocked=None)
        if len(outcomes) > self.config.batch_max_records:
            raise NetworkMetadataValidationError()
        expected = checkpoint.committed_byte_offset
        retained = 0
        for outcome in outcomes:
            digest(outcome.source_record_sha256)
            if outcome.normalized is not None and outcome.normalized.source_record_sha256 != outcome.source_record_sha256:
                raise NetworkMetadataValidationError()
            if outcome.start != expected or outcome.end != outcome.start + outcome.byte_length + 1:
                raise NetworkMetadataValidationError()
            expected = outcome.end
            if outcome.category != "record_too_large":
                retained += outcome.byte_length
            elif len(outcomes) != 1:
                raise NetworkMetadataValidationError()
        if retained > self.config.batch_max_bytes:
            raise NetworkMetadataValidationError()
        self.ensure_headroom()
        cursor, committed, duplicates, blocked = checkpoint.committed_byte_offset, 0, 0, None
        faults = 0
        previous_health = controller.last_snapshot
        with self.transaction() as now:
            candidate = controller.copy()
            plan = []
            sensitive_cutoff = ni_timestamp(now, canonical=True) - timedelta(days=14)
            core_cutoff = ni_timestamp(now, canonical=True) - timedelta(days=30)
            # Phase A is read-only in SQLite: freeze identity dispositions and
            # final prefix health before retention or first-ingest writes.
            for outcome in outcomes:
                disposition = self.identity_outcome(generation.source_generation_id, outcome)
                if disposition in CONFLICT_CATEGORIES:
                    # Observe trustworthy source time, not its ordinary fault/filter category.
                    candidate.observe_output_time(outcome.output_event_at)
                    blocked = disposition
                    candidate.block(blocked)
                    cursor = outcome.start
                    plan.append((outcome, disposition))
                    break
                if disposition == "new" and outcome.normalized is not None:
                    if ni_timestamp(outcome.normalized.event_at, canonical=True) < core_cutoff:
                        outcome = replace(outcome, category="retention_expired_event", normalized=None)
                    else:
                        candidate.observation_committed(outcome.normalized.event_at)
                candidate.observe_source(outcome)
                cursor = outcome.end
                plan.append((outcome, disposition))
            candidate.committed_offset = cursor
            batch_health_id = candidate.ensure(self, generation, now)
            # Phase B uses only the frozen prefix. Existing provenance is never
            # rewritten; every first-ingest observation owns the same final ref.
            for outcome, disposition in plan:
                if disposition != "new":
                    from .retention import RetentionPolicy
                    RetentionPolicy(self).expire_touched_identity(generation.source_generation_id, outcome.start, now)
                if disposition in CONFLICT_CATEGORIES:
                    self._fault(generation.source_generation_id, disposition, now, outcome.start)
                    faults += 1
                    break
                if disposition == "duplicate_noop":
                    duplicates += 1
                elif outcome.normalized is not None:
                    self._crash_point("before_observation_insert")
                    self._observation(outcome, generation, run_id, batch_health_id, now,
                        sensitive_expired=ni_timestamp(outcome.normalized.event_at, canonical=True) < sensitive_cutoff)
                    self._crash_point("after_observation_insert_before_commit")
                    committed += 1
                else:
                    self._fault(generation.source_generation_id, outcome.category, now, outcome.start)
                    faults += 1
            self._crash_point("before_checkpoint_update")
            anchor = anchor_provider(cursor)
            self.connection.execute("UPDATE network_metadata_checkpoint SET committed_byte_offset=?,continuity_anchor_start_offset=?,continuity_anchor_length=?,continuity_anchor_sha256=?,updated_at_utc=? WHERE logical_source_id=?",
                (cursor, *anchor, now, LOGICAL_SOURCE_ID))
            if blocked:
                self.connection.execute("UPDATE network_metadata_source_generations SET committed_byte_offset=?,processing_state='blocked',blocked_reason_code=?,blocked_at_utc=?,blocked_record_start_byte_offset=? WHERE source_generation_id=?",
                    (cursor, blocked, now, cursor, generation.source_generation_id))
            else:
                self.connection.execute("UPDATE network_metadata_source_generations SET committed_byte_offset=? WHERE source_generation_id=?", (cursor, generation.source_generation_id))
            self._crash_point("after_checkpoint_update_before_commit")
        controller.adopt(candidate)
        self._crash_point("after_commit")
        self.emit("batch_committed", source_generation_id=generation.source_generation_id, count=committed)
        if duplicates:
            self.emit("duplicate_noop", source_generation_id=generation.source_generation_id, count=duplicates)
        if faults:
            self.emit("ingest_fault_aggregate_updated", source_generation_id=generation.source_generation_id, count=faults)
        if controller.last_snapshot != previous_health:
            self.emit("health_transition", source_generation_id=generation.source_generation_id,
                      metadata_ingest_health=controller.ingest, metadata_output_health=controller.output)
        self.capacity_halted = self.footprint()["combined"] > self.config.max_db_bytes
        return dict(committed=committed, duplicates=duplicates, blocked=blocked)

    def _observation(self, outcome, generation, run_id, health_id, now, *, sensitive_expired=False):
        event, payload = outcome.normalized, outcome.normalized.payload
        binding = event.binding
        self._insert("network_metadata_observations", dict(observation_id=event.observation_id, schema_version=1,
            source_type="suricata", source_contract_version="suricata-eve-v1", source_event_family=event.family,
            source_event_identity=event.source_event_identity, source_generation_id=generation.source_generation_id,
            record_start_byte_offset=outcome.start, capture_source_id=binding.capture_source_id,
            capture_scope_binding_schema_version=1, capture_scope_binding_digest=binding.binding_digest,
            network_scope_id=binding.network_scope_id, network_scope_state="within_intended_scope", site_id=binding.site_id,
            event_at=event.event_at, ingested_at=now, flow_id_decimal=str(event.flow_id) if event.flow_id is not None else None,
            transaction_id_decimal=str(event.transaction_id) if event.transaction_id is not None else None,
            source_health_ref=health_id, ingest_run_id=run_id, normalizer_version=NORMALIZER_VERSION,
            sensitive_endpoint_presence_state="expired" if sensitive_expired else "observed_retained"))
        self._insert("network_metadata_source_records", dict(source_generation_id=generation.source_generation_id,
            record_start_byte_offset=outcome.start, record_end_byte_offset=outcome.end, record_byte_length=outcome.byte_length,
            source_event_family=event.family, outcome_code="normalized", observation_id=event.observation_id,
            ingested_at=now, source_record_sha256=None if sensitive_expired else event.source_record_sha256,
            semantic_payload_sha256=None if sensitive_expired else event.semantic_payload_sha256,
            digest_state="expired" if sensitive_expired else "retained"))
        if not sensitive_expired:
            self._insert("network_metadata_sensitive_endpoints", asdict(event.endpoint))
        values = asdict(payload)
        if event.family == "dns":
            queries, answers = values.pop("queries"), values.pop("answers")
            if sensitive_expired:
                for field in ("query_names_presence_state", "answer_values_presence_state"):
                    if values[field] == "observed_retained":
                        values[field] = "expired"
                queries, answers = (), ()
            values["dns_tx_id_decimal"] = str(values.pop("dns_tx_id"))
            self._insert("network_metadata_dns", dict(observation_id=event.observation_id, **values))
            for item in queries:
                self._insert("network_metadata_dns_queries", dict(observation_id=event.observation_id, **item))
            for item in answers:
                self._insert("network_metadata_dns_answers", dict(observation_id=event.observation_id, **item))
        elif event.family == "tls":
            client, server = values.pop("client_alpns"), values.pop("server_alpns")
            if sensitive_expired:
                values["sni"] = None
                if values["sni_presence_state"] == "observed_retained":
                    values["sni_presence_state"] = "expired"
            self._insert("network_metadata_tls", dict(observation_id=event.observation_id, **values))
            for side, items in (("client", client), ("server", server)):
                for ordinal, alpn in enumerate(items):
                    self._insert("network_metadata_tls_alpn", dict(observation_id=event.observation_id, side=side, ordinal=ordinal, alpn=alpn))
        else:
            if sensitive_expired:
                values["sni"] = None
                if values["sni_presence_state"] == "observed_retained":
                    values["sni_presence_state"] = "expired"
            self._insert("network_metadata_quic", dict(observation_id=event.observation_id, **values))

    def footprint(self):
        try:
            values = {}
            for kind, suffix in (("main", ""), ("wal", "-wal"), ("shm", "-shm"), ("journal", "-journal")):
                try:
                    values[kind] = os.stat(self.config.db_path + suffix).st_size
                except FileNotFoundError:
                    values[kind] = 0
            values["combined"] = sum(values.values())
            return values
        except OSError:
            raise NetworkMetadataStorageUnavailable() from None

    def ensure_headroom(self):
        headroom = max(16777216, 8 * self.config.batch_max_bytes)
        if self.footprint()["combined"] + headroom <= self.config.max_db_bytes:
            self.capacity_halted = False
            return
        # One bounded maintenance attempt, only when its reserved budget fits.
        if self.footprint()["combined"] + self.config.batch_max_bytes <= self.config.max_db_bytes:
            from .retention import RetentionPolicy
            RetentionPolicy(self).run()
        self.wal_maintenance(retention_ran=True)
        if self.footprint()["combined"] + headroom > self.config.max_db_bytes:
            self.capacity_halted = True
            self.emit("capacity_stop", reason_code="storage_capacity_headroom_exhausted",
                      sqlite_footprint_bytes=self.footprint()["combined"], max_db_bytes=self.config.max_db_bytes)
            raise NetworkMetadataStorageLimit()
        self.capacity_halted = False

    def wal_maintenance(self, *, retention_ran=False):
        footprint = self.footprint()
        if self.connection.in_transaction:
            raise NetworkMetadataValidationError()
        if not (retention_ran or footprint["wal"] > 67108864 or footprint["combined"] > self.config.max_db_bytes * .75):
            return
        try:
            page_size = self.connection.execute("PRAGMA page_size").fetchone()[0]
            growth = max(0, page_size * self.connection.execute("PRAGMA page_count").fetchone()[0] - footprint["main"])
            if footprint["combined"] + growth > self.config.max_db_bytes:
                return
            busy, _, _ = self.connection.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
            after = self.footprint()
            if busy == 0 and (after["wal"] > 67108864 or after["combined"] > self.config.max_db_bytes * .75):
                self.connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        except sqlite3.Error:
            raise NetworkMetadataStorageUnavailable() from None
