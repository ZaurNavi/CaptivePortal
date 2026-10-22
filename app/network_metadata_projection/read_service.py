"""Projection-only set-based reads. No upstream calls or query-time attribution."""
import sqlite3
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path
from app.device_fingerprint.validation import validate_site_id
from app.network_metadata.validation import canonical_uuid
from app.network_attribution.validation import canonical_mac
from .models import ALGORITHM, ProjectionUnavailable, ProjectionValidationError, DeviceNetworkMetadataEdgeV1
from dataclasses import asdict
from .schema import validate_schema
from .validation import read_window
from app.analytics.source_gateway import AnalyticsQueryDeadlineExceeded
from app.network_metadata.validation import ni_timestamp
from .config import idle_read_guard_from_env
from .effective_runtime_state import effective_runtime_state

JOIN = " FROM device_network_metadata_edges e LEFT JOIN projection_site_mac_bindings b ON b.site_id=e.site_id AND b.client_mac=e.client_mac"
COLUMNS = "SELECT e.*,b.site_id AS joined_site,b.device_id,b.binding_state,b.last_evaluated_at,b.authoritative_bound_at"


class DeviceNetworkMetadataReadService:
    def __init__(self, db_path, *, enabled=True, max_db_bytes=17179869184,
                 idle_write_reduction_enabled=None, clock=lambda: datetime.now(timezone.utc)):
        self.db_path, self.enabled, self.max_db_bytes = db_path, enabled, max_db_bytes
        if enabled and idle_write_reduction_enabled is None:
            idle_write_reduction_enabled = idle_read_guard_from_env()
        if idle_write_reduction_enabled is not None and type(idle_write_reduction_enabled) is not bool:
            raise ProjectionValidationError()
        self.idle_write_reduction_enabled = bool(enabled and idle_write_reduction_enabled)
        self.clock = clock

    def _runtime_state(self, connection):
        if not self.idle_write_reduction_enabled:
            row = connection.execute("SELECT runtime_state FROM projection_runtime_state WHERE singleton_id=1").fetchone()
            if row is None:
                raise ProjectionUnavailable()
            return row[0]
        row = connection.execute("SELECT runtime_state,safe_reason,last_source_poll_at FROM projection_runtime_state WHERE singleton_id=1").fetchone()
        if row is None:
            raise ProjectionUnavailable()
        return effective_runtime_state(row, enabled=True, evaluated_at_utc=self.clock())[0]

    @contextmanager
    def _snapshot(self, *, deadline=None):
        connection = None
        try:
            if not self.enabled:
                raise ProjectionUnavailable("projection_disabled")
            connection = sqlite3.connect(Path(self.db_path).resolve().as_uri() + "?mode=ro", uri=True, timeout=.5, isolation_level=None)
            connection.row_factory = sqlite3.Row
            if deadline is not None:
                deadline.require_remaining()
                connection.set_progress_handler(lambda: int(deadline.expired()), 100)
            for pragma in ("query_only=ON", "foreign_keys=ON", "busy_timeout=500"):
                connection.execute("PRAGMA " + pragma)
            connection.execute("BEGIN")
            validate_schema(connection)
            yield connection
            if deadline is not None:
                deadline.require_remaining()
        except (sqlite3.Error, OSError, ValueError, ProjectionUnavailable):
            if deadline is not None and deadline.expired():
                raise AnalyticsQueryDeadlineExceeded("Projection read deadline exceeded") from None
            raise ProjectionUnavailable() from None
        finally:
            if connection is not None:
                connection.close()

    def read_protocol_evidence_snapshot(self, site_id, device_id, client_mac, from_utc, to_utc, *, max_rows, deadline):
        """NI-03 narrow read: runtime, identity and facts in the same snapshot."""
        try:
            validate_site_id(site_id)
            canonical_uuid(device_id)
            if canonical_mac(client_mac) != client_mac or type(max_rows) is not int or max_rows != 20000:
                raise ValueError
            first, last = ni_timestamp(from_utc, canonical=True), ni_timestamp(to_utc, canonical=True)
            if (last - first).total_seconds() != 86400:
                raise ValueError
        except Exception:
            raise ProjectionValidationError() from None
        with self._snapshot(deadline=deadline) as connection:
            state = self._runtime_state(connection)
            binding = connection.execute(
                "SELECT binding_state,device_id FROM projection_site_mac_bindings WHERE site_id=? AND client_mac=?",
                (site_id, client_mac)).fetchone()
            result = dict(runtime_state=state, binding_state=binding[0] if binding else None,
                          bound_device_id=binding[1] if binding else None, facts=())
            if binding is None or binding[0] in {"not_yet_registry_resolved", "registry_unavailable"}:
                return result
            if binding[0] != "authoritative" or binding[1] != device_id:
                raise ProjectionUnavailable()
            # The upper half-open bound excludes future data from aggregation,
            # but its presence in this exact identity scope is an integrity failure.
            if connection.execute(
                "SELECT 1 FROM device_network_metadata_edges INDEXED BY idx_projection_mac_event "
                "WHERE site_id=? AND client_mac=? AND event_at>=? LIMIT 1",
                (site_id, client_mac, to_utc)).fetchone() is not None:
                raise ProjectionUnavailable()
            rows = connection.execute(
                "SELECT edge_id,event_at,source_event_family FROM device_network_metadata_edges "
                "INDEXED BY idx_projection_mac_event WHERE site_id=? AND client_mac=? "
                "AND event_at>=? AND event_at<? ORDER BY event_at,edge_id LIMIT ?",
                (site_id, client_mac, from_utc, to_utc, max_rows + 1)).fetchall()
            if len(rows) > max_rows:
                raise ProjectionUnavailable()
            result["facts"] = tuple(dict(row) for row in rows)
            return result

    @staticmethod
    def _logical(row):
        if row["joined_site"] is None:
            raise ProjectionUnavailable()
        item = dict(row)
        for key in ("joined_site", "record_start_byte_offset", "source_ingested_at", "edge_semantic_digest"):
            item.pop(key)
        item["identity_binding_state"] = item.pop("binding_state")
        item["identity_binding_evaluated_at"] = item.pop("last_evaluated_at")
        item["device_id_bound_at"] = item.pop("authoritative_bound_at")
        for role, prefix in (("device", "device"), ("peer", "peer")):
            item[role + "_endpoint"] = dict(ip=item.pop(prefix + "_ip"), port=item.pop(prefix + "_port"), transport_protocol=item["transport_protocol"])
        item.pop("transport_protocol")
        return asdict(DeviceNetworkMetadataEdgeV1(**item))

    def read_visit_protocol_snapshot(self, site_id, device_id, client_mac, started_at, ended_at,
                                     *, evaluated_at, deadline):
        """Three bounded index seeks over one REAL Visit interval, never 24h.

        For the existing Visit background loop ONLY. This is not a complete
        history attestation: NI02 retention/gaps cannot prove a negative. A
        future record is excluded by end <= actual evaluation time, not by
        interpreting later legitimate visits as corruption. No raw endpoint,
        domain or event payload is read. The caller must validate the Visit's
        own immutable Device link and recheck its guard before the Visit write.
        """
        try:
            validate_site_id(site_id)
            canonical_uuid(device_id)
            if canonical_mac(client_mac) != client_mac:
                raise ValueError
            start = ni_timestamp(started_at, canonical=True)
            end = ni_timestamp(ended_at, canonical=True)
            now = ni_timestamp(evaluated_at, canonical=True)
            if not start < end <= now:
                raise ValueError
        except Exception:
            raise ProjectionValidationError() from None
        with self._snapshot(deadline=deadline) as connection:
            # The metadata validator accepts old V2 for other consumers; this
            # specialized read must not fall back to a non-indexed edge scan.
            if connection.execute("SELECT 1 FROM sqlite_schema WHERE type='index' AND name=?",
                    ("idx_projection_mac_family_event_latest",)).fetchone() is None:
                raise ProjectionUnavailable()
            state = self._runtime_state(connection)
            binding = connection.execute(
                "SELECT binding_state,device_id,authoritative_bound_at FROM projection_site_mac_bindings "
                "WHERE site_id=? AND client_mac=?", (site_id, client_mac)).fetchone()
            result = dict(runtime_state=state, binding_state=binding[0] if binding else None,
                bound_device_id=binding[1] if binding else None, binding_confirmed_at=binding[2] if binding else None,
                facts=(), historical_completeness_claimed=False)
            if binding is None or binding[0] in {"not_yet_registry_resolved", "registry_unavailable"}:
                return result
            if binding[0] != "authoritative" or binding[1] != device_id:
                raise ProjectionUnavailable()
            if ni_timestamp(binding[2], canonical=True) > now:
                raise ProjectionUnavailable()
            facts = []
            for family in ("dns", "tls", "quic"):
                deadline.require_remaining()
                row = connection.execute(
                    "SELECT edge_id,event_at,source_event_family FROM device_network_metadata_edges "
                    "INDEXED BY idx_projection_mac_family_event_latest "
                    "WHERE site_id=? AND client_mac=? AND source_event_family=? AND event_at>=? AND event_at<? "
                    "ORDER BY event_at DESC,edge_id LIMIT 1",
                    (site_id, client_mac, family, started_at, ended_at)).fetchone()
                if row is not None:
                    # Stored text remains untrusted even behind a valid index.
                    from app.network_metadata.validation import digest
                    digest(row['edge_id'])
                    event_at = ni_timestamp(row['event_at'], canonical=True)
                    if row['source_event_family'] != family or not start <= event_at < end or event_at > now:
                        raise ProjectionUnavailable()
                    facts.append(dict(row))
            result['facts'] = tuple(facts)
            return result

    def _list(self, site_id, from_utc, to_utc, limit, cursor, predicate, identity):
        read_window(site_id, from_utc, to_utc, limit, cursor)
        parameters = [site_id, identity, from_utc, to_utc]
        condition = "e.site_id=? AND " + predicate + " AND e.event_at>=? AND e.event_at<?"
        if cursor is not None:
            condition += " AND (e.event_at>? OR (e.event_at=? AND e.edge_id>?))"
            parameters.extend((cursor[0], cursor[0], cursor[1]))
        with self._snapshot() as connection:
            # Probe for corrupt missing internal binding before filtering by a
            # device join (which otherwise could silently hide the bad edge).
            if connection.execute("SELECT 1" + JOIN + " WHERE e.site_id=? AND e.event_at>=? AND e.event_at<? AND b.site_id IS NULL LIMIT 1",
                                  (site_id, from_utc, to_utc)).fetchone():
                raise ProjectionUnavailable()
            rows = connection.execute(COLUMNS + JOIN + " WHERE " + condition + " ORDER BY e.event_at,e.edge_id LIMIT ?", parameters + [limit + 1]).fetchall()
            items = [self._logical(row) for row in rows[:limit]]
            return dict(items=items, next_cursor=(items[-1]["event_at"], items[-1]["edge_id"]) if len(rows) > limit else None)

    def list_edges_by_device(self, site_id, device_id, from_utc, to_utc, *, limit=100, cursor=None):
        try:
            canonical_uuid(device_id)
        except Exception:
            raise ProjectionValidationError() from None
        return self._list(site_id, from_utc, to_utc, limit, cursor, "b.device_id=? AND b.binding_state='authoritative'", device_id)

    def list_edges_by_mac(self, site_id, client_mac, from_utc, to_utc, *, limit=100, cursor=None):
        try:
            if canonical_mac(client_mac) != client_mac:
                raise ValueError
        except Exception:
            raise ProjectionValidationError() from None
        return self._list(site_id, from_utc, to_utc, limit, cursor, "e.client_mac=?", client_mac)

    def list_edges_by_observation(self, site_id, observation_id):
        try:
            validate_site_id(site_id)
            canonical_uuid(observation_id, 5)
        except Exception:
            raise ProjectionValidationError() from None
        with self._snapshot() as connection:
            rows = connection.execute(COLUMNS + JOIN + " WHERE e.site_id=? AND e.source_observation_ref=? "
                "ORDER BY CASE e.device_endpoint_role WHEN 'src' THEN 0 ELSE 1 END LIMIT 2", (site_id, observation_id)).fetchall()
            return tuple(self._logical(row) for row in rows)

    def get_status(self):
        defaults = dict(enabled=self.enabled, store_state="unavailable" if self.enabled else "disabled",
            runtime_state=None, safe_reason=None, schema_version=None, projection_contract_version=2,
            projection_algorithm_version=ALGORITHM, last_projection_commit_at=None, last_registry_reconcile_at=None,
            pending_attribution_count=0, checkpoint_count=0, db_bytes=0, capacity_limit_bytes=self.max_db_bytes)
        if not self.enabled:
            return defaults
        try:
            with self._snapshot() as connection:
                row = connection.execute("SELECT * FROM projection_runtime_state WHERE singleton_id=1").fetchone()
                for key in ("runtime_state", "safe_reason", "last_projection_commit_at", "last_registry_reconcile_at", "pending_attribution_count"):
                    defaults[key] = row[key]
                if self.idle_write_reduction_enabled:
                    defaults["runtime_state"], defaults["safe_reason"] = effective_runtime_state(
                        row, enabled=True, evaluated_at_utc=self.clock())
                defaults["checkpoint_count"] = connection.execute("SELECT count(*) FROM projection_source_checkpoints").fetchone()[0]
                total = 0
                for suffix in ("", "-wal", "-shm", "-journal"):
                    try:
                        total += Path(self.db_path + suffix).stat().st_size
                    except FileNotFoundError:
                        pass
                defaults.update(store_state="available", schema_version=2, db_bytes=total)
        except (ProjectionUnavailable, OSError):
            defaults["safe_reason"] = "projection_store_unavailable"
        return defaults
