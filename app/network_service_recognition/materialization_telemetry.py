"""Privacy-closed worker aggregates; never evidence/identity-bearing logging."""
import logging

FIELDS=frozenset('feed_highwater_seq feed_cursor_seq feed_backlog_rows live_batches_total feed_rows_examined_total candidate_edges_total source_evidence_rows_read_total service_positive_observations_total recognition_unknown_total recognition_limited_total idempotent_replays_total binding_replay_jobs_total binding_replay_edges_total coverage_reconciliations_total backfill_pages_total backfill_edges_total materialization_lag_seconds last_successful_commit_age_seconds source_failures_total store_failures_total capacity_halt_total'.split())


class MaterializationTelemetry:
    def __init__(self,logger=None):
        self.logger=logger or logging.getLogger('network_service_materialization')

    def emit(self,**values):
        if not values or set(values)-FIELDS or any(type(v) is not int or not 0<=v<=2**63-1 for v in values.values()):
            raise ValueError('invalid_materialization_telemetry')
        self.logger.info('network_service_materialization',extra={'materialization_counts':values})
