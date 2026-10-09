"""Single writer, atomic dispositions, monotonic Registry joins and hard cap."""
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.network_metadata.validation import digest, ni_timestamp
from .config import configuration_digest
from .models import (ALGORITHM, PROJECTION_TRANSACTION_HEADROOM_BYTES, ProjectionUnavailable,
                     ProjectionCapacity, ProjectionConflict, RUNTIME_STATES)
from .schema import TABLES, create_schema, validate_schema
from .validation import timestamp, semantic_digest


class ProjectionRepository:
    def __init__(self, config, *, clock=lambda: datetime.now(timezone.utc), crash_point=lambda _: None):
        self.config, self.clock, self.crash_point = config, clock, crash_point
        self.connection = self._writer_fd = None
        self._retention_authorized = False
        self.live_state, self.live_reason = "initializing", None
        self.active_run_id = None

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
            validate_schema(self.connection, integrity=True)
            row = self.connection.execute("SELECT runtime_state,safe_reason FROM projection_runtime_state").fetchone()
            self.live_state, self.live_reason = row
            return self
        except (sqlite3.Error, OSError, ProjectionUnavailable):
            self.close()
            raise ProjectionUnavailable() from None

    def maintain_capacity(self, *, post_commit=False):
        """PASSIVE after every commit; TRUNCATE only under headroom pressure.

        Pinned readers defer writes, never rewind a durable disposition. Live
        diagnostics deliberately need not be persisted when the cap forbids it.
        """
        try:
            pressure = self.footprint() + PROJECTION_TRANSACTION_HEADROOM_BYTES > self.config.max_db_bytes
            busy, frames, completed = self.connection.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
            reader_blocked = bool(busy or frames > completed)
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
            yield
            self.crash_point("before_commit")
            self.connection.execute("COMMIT")
            self.crash_point("after_commit")
        except BaseException as error:
            if self.connection.in_transaction:
                self.connection.execute("ROLLBACK")
            if isinstance(error, (sqlite3.Error, OSError)):
                raise ProjectionUnavailable() from None
            raise
        finally:
            self._retention_authorized = False
        # Do not turn a committed batch into a pretend rollback on pressure.
        self.maintain_capacity(post_commit=True)

    def insert(self, table, values):
        if table not in TABLES:
            raise ProjectionUnavailable()
        self.connection.execute(f"INSERT INTO {table} ({','.join(values)}) VALUES ({','.join('?' for _ in values)})", tuple(values.values()))

    def create_run(self, identity):
        digest(identity.artifact_sha, 40)
        digest(identity.artifact_tree, 40)
        run_id = str(uuid.uuid4())
        with self.transaction():
            self.insert("projection_runs", dict(projection_run_id=run_id, started_at_utc=timestamp(self.clock()),
                repository_head=identity.artifact_sha, repository_tree=identity.artifact_tree,
                projection_contract_version=1, projection_algorithm_version=ALGORITHM,
                configuration_digest=configuration_digest(self.config)))
        self.active_run_id = run_id
        return run_id

    def checkpoint(self, generation):
        return self.connection.execute("SELECT * FROM projection_source_checkpoints WHERE source_generation_id=?", (generation,)).fetchone()

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

    def runtime(self, state, reason=None, *, observation=None, **times):
        if state not in RUNTIME_STATES or not set(times) <= {"last_source_poll_at", "last_projection_commit_at", "last_registry_reconcile_at", "last_retention_at"}:
            raise ProjectionUnavailable()
        self.live_state, self.live_reason = state, reason
        values = dict(runtime_state=state, safe_reason=reason, blocked_observation_id=observation,
                      updated_at_utc=timestamp(self.clock()), **times)
        self.connection.execute("UPDATE projection_runtime_state SET " + ",".join(key + "=?" for key in values) +
            ",pending_attribution_count=(SELECT count(*) FROM projection_pending_attribution) WHERE singleton_id=1", tuple(values.values()))

    def set_failure(self, state, reason=None, *, observation=None):
        self.live_state, self.live_reason = state, reason
        try:
            with self.transaction():
                self.runtime(state, reason, observation=observation)
        except ProjectionUnavailable:
            # No status-only capacity exemption. Remain live fail-closed.
            pass

    def success_state(self, *, source_verified=False, **times):
        if not source_verified and self.live_state in {"source_unavailable", "blocked_conflict"}:
            self.runtime(self.live_state, self.live_reason, **times)
        elif self.connection.execute("SELECT 1 FROM projection_pending_attribution LIMIT 1").fetchone():
            self.runtime("attribution_unavailable", **times)
        elif self.connection.execute("SELECT 1 FROM projection_site_mac_bindings WHERE binding_state='registry_unavailable' LIMIT 1").fetchone():
            self.runtime("registry_degraded", **times)
        else:
            self.runtime("usable", **times)

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
                if (old is not None and (checkpoint is None or old["last_record_start_byte_offset"] != checkpoint["after"])) or (old is None and checkpoint["after"] is not None):
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
