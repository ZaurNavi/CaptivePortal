"""Bounded retention; no capacity override and no live-evidence eviction."""
from datetime import timedelta
from .models import ProjectionCapacity
from .validation import timestamp
from app.network_metadata.validation import ni_timestamp


class ProjectionRetention:
    def __init__(self, repository, source):
        self.repository, self.source = repository, source

    def run(self):
        repo, totals = self.repository, {}
        now = repo.clock()
        cutoff = timestamp(now - timedelta(days=1))
        try:
            visible = {item.source_generation_id for item in self.source.list_source_generations()}
        except Exception:
            visible = None  # Unknown source visibility cannot authorize GC.
        categories = (
            ("device_network_metadata_edges", "edge_id", "event_at<? OR source_ingested_at<?", (cutoff, cutoff)),
            ("projection_pending_attribution", "observation_id", "event_at<? OR source_ingested_at<?", (cutoff, cutoff)),
            ("projection_site_mac_bindings", "rowid", "binding_state!='authoritative' AND last_evaluated_at<? AND NOT EXISTS(SELECT 1 FROM device_network_metadata_edges e WHERE e.site_id=projection_site_mac_bindings.site_id AND e.client_mac=projection_site_mac_bindings.client_mac)", (cutoff,)),
            ("projection_registry_identities", "device_id", "last_verified_at<? AND NOT EXISTS(SELECT 1 FROM projection_site_mac_bindings b WHERE b.device_id=projection_registry_identities.device_id)", (cutoff,)),
            ("projection_registry_binding_events", "binding_event_id", "evaluated_at<?", (cutoff,)),
            ("projection_runs", "projection_run_id", "started_at_utc<? AND projection_run_id!=? AND NOT EXISTS(SELECT 1 FROM device_network_metadata_edges e WHERE e.projection_run_id=projection_runs.projection_run_id) AND NOT EXISTS(SELECT 1 FROM projection_registry_binding_events b WHERE b.projection_run_id=projection_runs.projection_run_id)", (cutoff, repo.active_run_id or "")),
            ("projection_source_checkpoints", "source_generation_id", "updated_at_utc<? AND NOT EXISTS(SELECT 1 FROM projection_pending_attribution p WHERE p.source_generation_id=projection_source_checkpoints.source_generation_id) AND NOT EXISTS(SELECT 1 FROM device_network_metadata_edges e WHERE e.source_generation_id=projection_source_checkpoints.source_generation_id)", (cutoff,)),
        )
        remaining = repo.config.retention_max_batches_per_pass
        for table, key, condition, parameters in categories:
            totals[table] = 0
            while remaining:
                if table == "projection_source_checkpoints" and visible is None:
                    break
                if table == "device_network_metadata_edges":
                    candidates = {}
                    for column in ("event_at", "source_ingested_at"):
                        rows = repo.connection.execute(
                            f"SELECT {key},event_at,source_ingested_at FROM {table} WHERE {column}<? "
                            f"ORDER BY {column},{key} LIMIT ?", (cutoff, repo.config.retention_batch_size))
                        for identity, event_at, ingested_at in rows:
                            candidates[identity] = min(ni_timestamp(event_at, canonical=True),
                                                       ni_timestamp(ingested_at, canonical=True))
                    ids = sorted(candidates, key=lambda key: (candidates[key], key))[:repo.config.retention_batch_size]
                else:
                    rows = repo.connection.execute(f"SELECT {key} FROM {table} WHERE ({condition}) ORDER BY {key} LIMIT ?",
                        (*parameters, repo.config.retention_batch_size)).fetchall()
                    ids = [row[0] for row in rows if table != "projection_source_checkpoints" or row[0] not in visible]
                if not ids:
                    break
                try:
                    with repo.transaction(retention=True):
                        repo.connection.execute(f"DELETE FROM {table} WHERE {key} IN ({','.join('?' for _ in ids)})", ids)
                        # Count/state must match committed GC even on budget exit.
                        repo.success_state(last_retention_at=timestamp(now))
                except ProjectionCapacity:
                    return totals
                remaining -= 1
                totals[table] += len(ids)
            if remaining == 0:
                return totals
        with repo.transaction():
            repo.success_state(last_retention_at=timestamp(now))
        return totals
