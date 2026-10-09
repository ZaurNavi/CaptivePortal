"""Projection-only set-based reads. No upstream calls or query-time attribution."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from app.device_fingerprint.validation import validate_site_id
from app.network_metadata.validation import canonical_uuid
from app.network_attribution.validation import canonical_mac
from .models import ALGORITHM, ProjectionUnavailable, ProjectionValidationError, DeviceNetworkMetadataEdgeV1
from dataclasses import asdict
from .schema import validate_schema
from .validation import read_window

JOIN = " FROM device_network_metadata_edges e LEFT JOIN projection_site_mac_bindings b ON b.site_id=e.site_id AND b.client_mac=e.client_mac"
COLUMNS = "SELECT e.*,b.site_id AS joined_site,b.device_id,b.binding_state,b.last_evaluated_at,b.authoritative_bound_at"


class DeviceNetworkMetadataReadService:
    def __init__(self, db_path, *, enabled=True, max_db_bytes=17179869184):
        self.db_path, self.enabled, self.max_db_bytes = db_path, enabled, max_db_bytes

    @contextmanager
    def _snapshot(self):
        connection = None
        try:
            if not self.enabled:
                raise ProjectionUnavailable("projection_disabled")
            connection = sqlite3.connect(Path(self.db_path).resolve().as_uri() + "?mode=ro", uri=True, timeout=.5, isolation_level=None)
            connection.row_factory = sqlite3.Row
            for pragma in ("query_only=ON", "foreign_keys=ON", "busy_timeout=500"):
                connection.execute("PRAGMA " + pragma)
            connection.execute("BEGIN")
            validate_schema(connection)
            yield connection
        except (sqlite3.Error, OSError, ValueError):
            raise ProjectionUnavailable() from None
        finally:
            if connection is not None:
                connection.close()

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
            runtime_state=None, safe_reason=None, schema_version=None, projection_contract_version=1,
            projection_algorithm_version=ALGORITHM, last_projection_commit_at=None, last_registry_reconcile_at=None,
            pending_attribution_count=0, checkpoint_count=0, db_bytes=0, capacity_limit_bytes=self.max_db_bytes)
        if not self.enabled:
            return defaults
        try:
            with self._snapshot() as connection:
                row = connection.execute("SELECT * FROM projection_runtime_state WHERE singleton_id=1").fetchone()
                for key in ("runtime_state", "safe_reason", "last_projection_commit_at", "last_registry_reconcile_at", "pending_attribution_count"):
                    defaults[key] = row[key]
                defaults["checkpoint_count"] = connection.execute("SELECT count(*) FROM projection_source_checkpoints").fetchone()[0]
                total = 0
                for suffix in ("", "-wal", "-shm", "-journal"):
                    try:
                        total += Path(self.db_path + suffix).stat().st_size
                    except FileNotFoundError:
                        pass
                defaults.update(store_state="available", schema_version=1, db_bytes=total)
        except (ProjectionUnavailable, OSError):
            defaults["safe_reason"] = "projection_store_unavailable"
        return defaults
