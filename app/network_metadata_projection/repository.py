"""Single writer, atomic dispositions, monotonic Registry joins and hard cap."""
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.network_metadata.validation import digest, ni_timestamp
from .config import configuration_digest, ScopeAdmission
from .models import (ALGORITHM, PROJECTION_TRANSACTION_HEADROOM_BYTES, ProjectionUnavailable,
                     ProjectionCapacity, ProjectionConflict, RUNTIME_STATES)
from .schema import TABLES, INDEXES, create_schema, validate_schema
from .validation import timestamp, semantic_digest
from .service_extension import append_candidate, maintain_authoritative_change


class ProjectionRepository:
    def __init__(self, config, *, clock=lambda: datetime.now(timezone.utc), crash_point=lambda _: None,
                 monotonic=time.monotonic, install_service_recognition_extension=False, reset_bootstrap=None):
        if type(install_service_recognition_extension) is not bool:
            raise ProjectionUnavailable()
        self._install_service_recognition_extension = install_service_recognition_extension
        if reset_bootstrap is not None and (type(reset_bootstrap) is not dict or set(reset_bootstrap) != {
                "floors", "reset_epoch_id", "reset_at_utc"}):
            raise ProjectionUnavailable("invalid_reset_bootstrap")
        self._reset_bootstrap = reset_bootstrap
        self.config, self.clock, self.crash_point = config, clock, crash_point
        self.connection = self._writer_fd = None
        self._retention_authorized = False
        self.live_state, self.live_reason = "initializing", None
        self.active_run_id = None
        self.monotonic = monotonic
        self.source_verified_in_run = False
        self.last_durable_source_poll_at = self.last_durable_source_poll_tick = None
        self._transaction_source_poll_at = None
        self._last_soft_checkpoint_tick = None
        self.telemetry = None
        # Process-local observed authority read state, never inferred from a
        # successful NI-01 poll or restored optimistically after restart.
        self.attribution_read_state = None
        self.service_recognition_extension_present = False

    def _count_success(self, **counts):
        if self.config.telemetry_aggregation_enabled and self.telemetry is not None:
            self.telemetry.observe_success(**counts)

    def footprint(self):
        try:
            total = 0
            for suffix in ("", "-wal", "-shm", "-journal"):
                try:
                    total += Path(self.config.db_path + suffix).stat().st_size
                except FileNotFoundError:
                    pass
            return total
        except OSError:
            raise ProjectionUnavailable() from None

    def _lock(self):
        self._writer_fd = os.open(self.config.db_path + ".writer.lock", os.O_CREAT | os.O_RDWR, 0o640)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(self._writer_fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(self._writer_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def initialize(self):
        if not self.config.enabled:
            raise ProjectionUnavailable("projection_disabled")
        try:
            self._lock()
            path = Path(self.config.db_path)
            if path.exists() and path.stat().st_size:
                probe = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=.5)
                try:
                    probe.execute("PRAGMA foreign_keys=ON")
                    validate_schema(probe, integrity=True)
                finally:
                    probe.close()
            self.connection = sqlite3.connect(self.config.db_path, isolation_level=None, timeout=.5)
            self.connection.row_factory = sqlite3.Row
            self.connection.create_function("projection_retention_delete_authorized", 0, lambda: int(self._retention_authorized))
            for pragma in ("foreign_keys=ON", "journal_mode=WAL", "synchronous=FULL", "busy_timeout=500", "wal_autocheckpoint=1000"):
                self.connection.execute("PRAGMA " + pragma)
            objects = self.connection.execute("SELECT count(*) FROM sqlite_master").fetchone()[0]
            if objects == 0 and self.connection.execute("PRAGMA user_version").fetchone()[0] == 0:
                with self.transaction():
                    create_schema(self.connection, timestamp(self.clock()))
                    if self.config.scope_admission_json is not None:
                        self._pin_scope_admission()
                    if self._reset_bootstrap is not None:
                        self.crash_point("reset_core_created")
                        self._insert_reset_floors(**self._reset_bootstrap)
                        self.crash_point("reset_floors_installed")
            elif self._reset_bootstrap is not None:
                raise ProjectionUnavailable("reset_requires_fresh_store")
            # #296: additive compatibility with the already deployed #293
            # index. Only this sole writer installs it; readers never migrate.
            name = "idx_projection_mac_family_event_latest"
            if self.connection.execute("SELECT 1 FROM sqlite_schema WHERE name=?", (name,)).fetchone() is None:
                with self.transaction():
                    validate_schema(self.connection)
                    self.connection.execute(f"CREATE INDEX {name} ON {INDEXES[name]}")
                    self.crash_point("visit_protocol_index_installed")
            if self.config.scope_admission_json is not None:
                with self.transaction():
                    self._pin_scope_admission()
            self.service_recognition_extension_present = (
                validate_schema(self.connection, integrity=True) == "CORE_PLUS_EXTENSION_V1")
            row = self.connection.execute("SELECT runtime_state,safe_reason FROM projection_runtime_state").fetchone()
            self.live_state, self.live_reason = row
            if self._install_service_recognition_extension:
                from .service_extension import install_service_recognition_extension
                install_service_recognition_extension(self)
            return self
        except (sqlite3.Error, OSError, ProjectionUnavailable, ProjectionConflict):
            self.close()
            raise ProjectionUnavailable() from None
        except BaseException:
            self.close()
            raise

    def _pin_scope_admission(self):
        admission = ScopeAdmission(self.config.scope_admission_json)
        old = self.connection.execute("SELECT admission_digest,admission_json FROM projection_scope_admission").fetchone()
        if old is None:
            self.insert("projection_scope_admission", dict(singleton_id=1,
                admission_digest=admission.digest, admission_json=admission.canonical))
        elif tuple(old) != (admission.digest, admission.canonical):
            raise ProjectionConflict("scope_admission_untrusted")

    def maintain_capacity(self, *, post_commit=False, retention_ran=False):
        """Legacy PASSIVE cadence or opt-in conditional soft maintenance.

        Pinned readers defer writes, never rewind a durable disposition. Live
        diagnostics deliberately need not be persisted when the cap forbids it.
        """
        try:
            reserved_footprint = self.footprint() + PROJECTION_TRANSACTION_HEADROOM_BYTES
            pressure = reserved_footprint > self.config.max_db_bytes
            if self.config.checkpoint_opt_enabled:
                recovery = self.live_state in {"capacity_waiting_reader", "capacity_halted"}
                try:
                    wal_bytes = Path(self.config.db_path + "-wal").stat().st_size
                except FileNotFoundError:
                    wal_bytes = 0
                soft = wal_bytes >= 16777216 or (retention_ran and wal_bytes > 0)
                tick = self.monotonic()
                if reserved_footprint < self.config.max_db_bytes and not recovery:
                    if not soft or (self._last_soft_checkpoint_tick is not None
                                    and tick - self._last_soft_checkpoint_tick < 60):
                        return True
                    self._last_soft_checkpoint_tick = tick
            busy, frames, completed = self.connection.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
            reader_blocked = bool(busy or frames > completed)
            self._count_success(checkpoint_attempt_count=1, checkpoint_busy_count=int(reader_blocked))
            if pressure:
                self.connection.execute("PRAGMA busy_timeout=0")
                try:
                    result = self.connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
                    reader_blocked = bool(result[0])
                except sqlite3.OperationalError as error:
                    if str(error).lower() not in {"database is locked", "database table is locked"} and (getattr(error, "sqlite_errorcode", 0) & 255) not in (5, 6):
                        raise
                    reader_blocked = True
                finally:
                    self.connection.execute("PRAGMA busy_timeout=500")
            current = self.footprint()
            if current + PROJECTION_TRANSACTION_HEADROOM_BYTES > self.config.max_db_bytes:
                self.live_state = "capacity_waiting_reader" if current <= self.config.max_db_bytes and reader_blocked else "capacity_halted"
                self.live_reason = self.live_state
                return False
            if self.live_state in {"capacity_waiting_reader", "capacity_halted"}:
                validate_schema(self.connection, integrity=True)
                self.live_state, self.live_reason = "usable", None
            return True
        except (sqlite3.Error, OSError):
            raise ProjectionUnavailable() from None

    @contextmanager
    def transaction(self, *, retention=False):
        if self.connection is None:
            raise ProjectionUnavailable()
        if self.footprint() + PROJECTION_TRANSACTION_HEADROOM_BYTES > self.config.max_db_bytes:
            if not self.maintain_capacity():
                raise ProjectionCapacity(self.live_state)
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            self._retention_authorized = retention
            self._transaction_source_poll_at = None
            yield
            self.crash_point("before_commit")
            self.connection.execute("COMMIT")
            if self.config.idle_write_reduction_enabled and self._transaction_source_poll_at is not None:
                self.last_durable_source_poll_at = self._transaction_source_poll_at
                self.last_durable_source_poll_tick = self.monotonic()
                self.source_verified_in_run = True
            self._count_success(commit_count=1)
            self.crash_point("after_commit")
        except BaseException as error:
            if self.connection.in_transaction:
                self.connection.execute("ROLLBACK")
            if isinstance(error, (sqlite3.Error, OSError)):
                raise ProjectionUnavailable() from None
            raise
        finally:
            self._retention_authorized = False
            self._transaction_source_poll_at = None
        # Do not turn a committed batch into a pretend rollback on pressure.
        if self.config.checkpoint_opt_enabled:
            self.maintain_capacity(post_commit=True, retention_ran=retention)
        else:
            self.maintain_capacity(post_commit=True)

    def insert(self, table, values):
        if table not in TABLES:
            raise ProjectionUnavailable()
        self.connection.execute(f"INSERT INTO {table} ({','.join(values)}) VALUES ({','.join('?' for _ in values)})", tuple(values.values()))

    def create_run(self, identity):
        digest(identity.artifact_sha, 40)
        digest(identity.artifact_tree, 40)
        run_id = str(uuid.uuid4())
        admission = ScopeAdmission(self.config.scope_admission_json)
        stored = self.connection.execute("SELECT admission_digest FROM projection_scope_admission").fetchone()
        if stored is None or stored[0] != admission.digest:
            raise ProjectionConflict("scope_admission_untrusted")
        with self.transaction():
            if self.config.idle_write_reduction_enabled and self.live_state != "blocked_conflict":
                self.runtime("initializing")
            self.insert("projection_runs", dict(projection_run_id=run_id, started_at_utc=timestamp(self.clock()),
                repository_head=identity.artifact_sha, repository_tree=identity.artifact_tree,
                projection_contract_version=2, projection_algorithm_version=ALGORITHM,
                configuration_digest=configuration_digest(self.config), scope_admission_digest=admission.digest))
        self.active_run_id = run_id
        return run_id

    def checkpoint(self, generation):
        return self.connection.execute("SELECT * FROM projection_source_checkpoints WHERE source_generation_id=?", (generation,)).fetchone()

    def reset_floor(self, generation):
        return self.connection.execute("SELECT * FROM projection_source_reset_floors WHERE source_generation_id=?", (generation,)).fetchone()

    def install_reset_floors(self, floors, *, reset_epoch_id, reset_at_utc):
        with self.transaction():
            self._insert_reset_floors(floors, reset_epoch_id=reset_epoch_id, reset_at_utc=reset_at_utc)

    def _insert_reset_floors(self, floors, *, reset_epoch_id, reset_at_utc):
        import hashlib
        from app.network_metadata.canonical import ni01_canonical_json
        from app.network_metadata.validation import canonical_uuid
        from .validation import validate_reset_floors
        canonical_uuid(reset_epoch_id, 4)
        ni_timestamp(reset_at_utc, canonical=True)
        admission = ScopeAdmission(self.config.scope_admission_json)
        ordered = sorted(floors, key=lambda item: item["source_generation_id"])
        if not self.connection.in_transaction or any(self.connection.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone() for table in (
                "projection_runs", "device_network_metadata_edges", "projection_source_checkpoints",
                "projection_pending_attribution", "projection_source_reset_epoch")):
            raise ProjectionUnavailable("reset_requires_fresh_store")
        self.insert("projection_source_reset_epoch", dict(singleton_id=1, reset_epoch_id=reset_epoch_id,
            reset_at_utc=reset_at_utc, admission_digest=admission.digest,
            source_snapshot_digest=hashlib.sha256(ni01_canonical_json(ordered)).hexdigest(), floor_count=len(ordered)))
        for floor in ordered:
            self.insert("projection_source_reset_floors", dict(floor, reset_epoch_id=reset_epoch_id, reset_at_utc=reset_at_utc))
        validate_reset_floors(self.connection, admission)

    def existing_edges(self, observation):
        return {row["device_endpoint_role"]: dict(row) for row in self.connection.execute(
            "SELECT * FROM device_network_metadata_edges WHERE source_observation_ref=?", (observation,))}

    def binding(self, site, mac):
        return self.connection.execute("SELECT * FROM projection_site_mac_bindings WHERE site_id=? AND client_mac=?", (site, mac)).fetchone()

    def _registry_binding(self, site, mac, evaluation, run_id, now, *, edge_at=None):
        old = self.binding(site, mac)
        state, device_id, bound = evaluation.state, evaluation.device_id, None
        if evaluation.state == "authoritative":
            known = self.connection.execute("SELECT * FROM projection_registry_identities WHERE client_mac=? OR device_id=?", (mac, device_id)).fetchall()
            if any(row["client_mac"] != mac or row["device_id"] != device_id for row in known):
                raise ProjectionConflict("registry_identity_conflict")
            if old and old["binding_state"] == "authoritative" and old["device_id"] != device_id:
                raise ProjectionConflict("registry_identity_conflict")
            if not known:
                self.insert("projection_registry_identities", dict(device_id=device_id, client_mac=mac,
                    registry_schema_version=1, first_bound_at=now, last_verified_at=now, registry_record_updated_at=evaluation.record_updated_at))
            else:
                self.connection.execute("UPDATE projection_registry_identities SET last_verified_at=?,registry_record_updated_at=? WHERE device_id=?",
                                        (now, evaluation.record_updated_at, device_id))
            bound = old["authoritative_bound_at"] if old and old["binding_state"] == "authoritative" else now
        elif old and old["binding_state"] == "authoritative":
            state, device_id, bound = "authoritative", old["device_id"], old["authoritative_bound_at"]
        if old is None:
            if edge_at is None:
                raise ProjectionUnavailable()
            self.insert("projection_site_mac_bindings", dict(site_id=site, client_mac=mac, binding_state=state,
                device_id=device_id, first_edge_at=edge_at, last_edge_at=edge_at, last_evaluated_at=now,
                authoritative_bound_at=bound, last_safe_reason=evaluation.reason))
        else:
            self.connection.execute("UPDATE projection_site_mac_bindings SET binding_state=?,device_id=?,last_evaluated_at=?,authoritative_bound_at=?,last_safe_reason=? WHERE site_id=? AND client_mac=?",
                (state, device_id, now, bound, evaluation.reason, site, mac))
        if old is None or old["binding_state"] != state or old["last_safe_reason"] != evaluation.reason:
            self.insert("projection_registry_binding_events", dict(site_id=site, client_mac=mac,
                previous_state=None if old is None else old["binding_state"], new_state=state, device_id=device_id,
                evaluated_at=now, registry_schema_version=1 if evaluation.state != "registry_unavailable" else None,
                registry_record_updated_at=evaluation.record_updated_at, safe_reason=evaluation.reason, projection_run_id=run_id))
        if self.service_recognition_extension_present:
            maintain_authoritative_change(self.connection, old, site=site, mac=mac, state=state,
                                          device=device_id, evaluated_at=now)

    def runtime(self, state, reason=None, *, observation=None, **times):
        if state not in RUNTIME_STATES or not set(times) <= {"last_source_poll_at", "last_projection_commit_at", "last_registry_reconcile_at", "last_retention_at"}:
            raise ProjectionUnavailable()
        self.live_state, self.live_reason = state, reason
        values = dict(runtime_state=state, safe_reason=reason, blocked_observation_id=observation,
                      updated_at_utc=timestamp(self.clock()), **times)
        self.connection.execute("UPDATE projection_runtime_state SET " + ",".join(key + "=?" for key in values) +
            ",pending_attribution_count=(SELECT count(*) FROM projection_pending_attribution) WHERE singleton_id=1", tuple(values.values()))
        if self.config.idle_write_reduction_enabled and "last_source_poll_at" in times:
            self._transaction_source_poll_at = times["last_source_poll_at"]

    def set_failure(self, state, reason=None, *, observation=None):
        self.live_state, self.live_reason = state, reason
        try:
            with self.transaction():
                self.runtime(state, reason, observation=observation)
        except ProjectionUnavailable:
            # No status-only capacity exemption. Remain live fail-closed.
            pass

    def successful_source_state(self):
        """Read-only candidate state; no idle UPDATE needed to evaluate it."""
        if (self.attribution_read_state == "unavailable"
                or self.connection.execute("SELECT 1 FROM projection_pending_attribution LIMIT 1").fetchone()):
            return "attribution_unavailable"
        if self.connection.execute("SELECT 1 FROM projection_site_mac_bindings WHERE binding_state='registry_unavailable' LIMIT 1").fetchone():
            return "registry_degraded"
        return "usable"

    def successful_source_reason(self, state):
        if state != "attribution_unavailable":
            return None
        return ("pending_attribution" if self.attribution_read_state == "available"
                else "attribution_authority_unavailable")

    def pending_metrics(self):
        row = self.connection.execute(
            "SELECT count(*),min(first_pending_at) FROM projection_pending_attribution").fetchone()
        age = 0 if row[1] is None else max(0, int((self.clock() - ni_timestamp(row[1], canonical=True)).total_seconds()))
        return int(row[0]), age

    def success_state(self, *, source_verified=False, **times):
        if self.live_state in {"blocked_conflict", "capacity_halted", "capacity_waiting_reader"}:
            self.runtime(self.live_state, self.live_reason, **times)
        elif (self.config.idle_write_reduction_enabled and not source_verified
                and not self.source_verified_in_run):
            self.runtime(self.live_state, self.live_reason, **times)
        elif not source_verified and self.live_state in {"source_unavailable", "blocked_conflict"}:
            self.runtime(self.live_state, self.live_reason, **times)
        else:
            state = self.successful_source_state()
            self.runtime(state, self.successful_source_reason(state), **times)

    def commit_dispositions(self, dispositions, evaluations, run_id, *, checkpoint=None):
        if not 1 <= len(dispositions) <= 256:
            raise ProjectionUnavailable()
        now = timestamp(self.clock())
        with self.transaction():
            for source, edges, pending in dispositions:
                for edge in edges:
                    row = self.connection.execute("SELECT * FROM device_network_metadata_edges WHERE edge_id=?", (edge["edge_id"],)).fetchone()
                    if row is not None:
                        if row["edge_semantic_digest"] != edge["edge_semantic_digest"] or semantic_digest(dict(row)) != edge["edge_semantic_digest"]:
                            raise ProjectionConflict("edge_semantic_conflict")
                        continue
                    self.insert("device_network_metadata_edges", edge)
                    if self.service_recognition_extension_present:
                        append_candidate(self.connection, edge, now)
                    site, mac = edge["site_id"], edge["client_mac"]
                    if self.binding(site, mac) is None:
                        self._registry_binding(site, mac, evaluations[(site, mac)], run_id, now, edge_at=edge["event_at"])
                    else:
                        self.connection.execute("UPDATE projection_site_mac_bindings SET last_edge_at=max(last_edge_at,?) WHERE site_id=? AND client_mac=?",
                                                (edge["event_at"], site, mac))
                if pending is None:
                    self.connection.execute("DELETE FROM projection_pending_attribution WHERE observation_id=?", (source.observation_id,))
                else:
                    prior = self.connection.execute("SELECT first_pending_at FROM projection_pending_attribution WHERE observation_id=?", (source.observation_id,)).fetchone()
                    if prior:
                        pending["first_pending_at"] = prior[0]
                    columns = tuple(pending)
                    self.connection.execute("INSERT INTO projection_pending_attribution (" + ",".join(columns) + ") VALUES(" +
                        ",".join("?" for _ in columns) + ") ON CONFLICT(observation_id) DO UPDATE SET " +
                        ",".join(name + "=excluded." + name for name in columns if name != "observation_id"), tuple(pending.values()))
            if checkpoint is not None:
                last = next(iter(dispositions[-1]))
                old = self.checkpoint(last.source_generation_id)
                floor = self.reset_floor(last.source_generation_id)
                boundaries = [value for value in (
                    None if old is None else old["last_record_start_byte_offset"],
                    None if floor is None else floor["last_retained_record_start_byte_offset"]) if value is not None]
                expected_after = max(boundaries) if boundaries else None
                if (checkpoint["after"] != expected_after or any(
                        source.source_generation_id != last.source_generation_id
                        or (expected_after is not None and source.record_start_byte_offset <= expected_after)
                        for source, _, _ in dispositions)):
                    raise ProjectionConflict("checkpoint_source_conflict")
                self.connection.execute("INSERT INTO projection_source_checkpoints VALUES(?,?,?,?,?) ON CONFLICT(source_generation_id) DO UPDATE SET "
                    "last_record_start_byte_offset=excluded.last_record_start_byte_offset,last_observation_id=excluded.last_observation_id,"
                    "last_source_ingested_at=excluded.last_source_ingested_at,updated_at_utc=excluded.updated_at_utc",
                    (last.source_generation_id, last.record_start_byte_offset, last.observation_id, last.ingested_at, now))
            times = {"last_projection_commit_at": now}
            if checkpoint is not None:
                times["last_source_poll_at"] = now
            self.success_state(source_verified=checkpoint is not None, **times)

    def reconcile_selection(self):
        # Preselect once: transitions cannot re-enter this pass. Frozen V1 lanes.
        limit, uq, aq = 500, 400, 100
        unresolved = self.connection.execute("SELECT * FROM projection_site_mac_bindings WHERE binding_state!='authoritative' "
            "ORDER BY CASE binding_state WHEN 'not_yet_registry_resolved' THEN 0 ELSE 1 END,last_evaluated_at,site_id,client_mac LIMIT ?", (limit,)).fetchall()
        authoritative = self.connection.execute("SELECT * FROM projection_site_mac_bindings WHERE binding_state='authoritative' "
            "ORDER BY last_evaluated_at,site_id,client_mac LIMIT ?", (limit,)).fetchall()
        u, a = min(uq, len(unresolved)), min(aq, len(authoritative))
        if u < uq:
            a = min(len(authoritative), limit - u)
        if a < aq:
            u = min(len(unresolved), limit - a)
        return tuple(unresolved[:u] + authoritative[:a])

    def reconcile(self, selected, evaluations, run_id):
        now = timestamp(self.clock())
        with self.transaction():
            for row in selected:
                self._registry_binding(row["site_id"], row["client_mac"], evaluations[(row["site_id"], row["client_mac"])], run_id, now)
            self.success_state(last_registry_reconcile_at=now)

    def pending(self):
        return self.connection.execute("SELECT * FROM projection_pending_attribution WHERE next_retry_at<=? ORDER BY next_retry_at,observation_id LIMIT ?",
            (timestamp(self.clock()), self.config.attribution_retry_batch_size)).fetchall()

    def close(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None
        if self._writer_fd is not None:
            os.close(self._writer_fd)
            self._writer_fd = None
