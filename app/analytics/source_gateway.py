"""Bounded, read-only SQL composition behind existing source read services."""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterable, Iterator, Mapping, Sequence

from app.observations.read_service import ObservationReadService
from app.visit_lifecycle.read_service import VisitLifecycleReadService
from app.visitor_registry.registry_read_service import (
    VisitorRegistryReadService,
)


SOURCE_SCHEMA_VERSIONS = {
    "observations": 1,
    "visits": 2,
    "registry": 1,
}
MAX_CROSS_SOURCE_IDENTIFIERS = 250_000
_SQLITE_PROGRESS_OPCODES = 100
_SNAPSHOT_BATCH_SIZE = 800
_VISIT_WINDOW_BATCH_SIZE = 100

CLIENT_FIELDS = frozenset({
    "ap_mac", "radio_id", "band", "channel", "rssi", "snr",
    "traffic_down", "traffic_up",
})
AP_FIELDS = frozenset({"cpu_util", "mem_util"})
RADIO_FIELDS = frozenset({
    "busy_util", "tx_util", "rx_util", "interference_util",
    "rx_retry_packets", "tx_retry_packets",
    "rx_error_packets", "tx_error_packets",
    "rx_drop_packets", "tx_drop_packets",
    "radio_rx_mbps", "radio_tx_mbps",
})
WIRELESS_SCALAR_FIELDS = {
    "client": frozenset({"rssi", "snr"}),
    "ap": frozenset({"cpu_util", "mem_util"}),
    "radio": frozenset({
        "tx_util", "rx_util", "interference_util", "busy_util",
    }),
}
CLIENT_CONTEXT_FIELDS = frozenset({"ap_mac", "ssid", "band", "channel"})
STORED_RATE_FIELDS = {
    "wired_download_mbps": ("ap", "wired_download_rate_reason"),
    "wired_upload_mbps": ("ap", "wired_upload_rate_reason"),
    "lan_rx_mbps": ("ap", "lan_rx_rate_reason"),
    "lan_tx_mbps": ("ap", "lan_tx_rate_reason"),
    "radio_rx_mbps": ("radio", "radio_rx_rate_reason"),
    "radio_tx_mbps": ("radio", "radio_tx_rate_reason"),
}
CLIENT_COUNTER_FIELDS = {
    "client_download_mbps": "traffic_down",
    "client_upload_mbps": "traffic_up",
}
RADIO_COUNTER_FIELDS = {
    "rx_retry_delta": ("rx_retry_packets", "rx_packets"),
    "tx_retry_delta": ("tx_retry_packets", "tx_packets"),
    "rx_error_delta": ("rx_error_packets", "rx_packets"),
    "tx_error_delta": ("tx_error_packets", "tx_packets"),
    "rx_drop_delta": ("rx_drop_packets", "rx_packets"),
    "tx_drop_delta": ("tx_drop_packets", "tx_packets"),
    "rx_packet_delta": ("rx_packets", "rx_packets"),
    "tx_packet_delta": ("tx_packets", "tx_packets"),
}
FIELD_ALLOWLIST = {
    "client": CLIENT_FIELDS,
    "ap": AP_FIELDS,
    "radio": RADIO_FIELDS,
}

_NON_OK_RATE_REASONS_SQL = (
    "'no_baseline','counter_reset','gap_too_large','invalid_elapsed',"
    "'source_unavailable'"
)
_CANONICAL_MAC_SQL = (
    "ap_mac GLOB "
    "'[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:"
    "[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]'"
)


def _rate_shape_ok_sql(value: str, reason: str, timestamp: str) -> str:
    return (
        f"({reason}='ok' AND {timestamp} IS NOT NULL "
        f"AND typeof({value}) IN ('integer','real') AND {value}>=0 "
        f"AND abs({value})<=1.7976931348623157e308)"
    )


def _rate_ok_sql(value: str, reason: str, timestamp: str) -> str:
    return (
        f"({_rate_shape_ok_sql(value, reason, timestamp)} "
        f"AND {timestamp}>=target.started_at "
        f"AND {timestamp}<=target.finished_at "
        "AND target.finished_at<=target.evaluated_at)"
    )


def _rate_valid_sql(value: str, reason: str, timestamp: str) -> str:
    return (
        f"COALESCE(({_rate_shape_ok_sql(value, reason, timestamp)} OR "
        f"({reason} IN ({_NON_OK_RATE_REASONS_SQL}) AND {value} IS NULL)),0)"
    )


_WIRED_DOWN_OK = _rate_ok_sql(
    "wired_download_mbps", "wired_download_rate_reason", "wired_observed_at"
)
_WIRED_UP_OK = _rate_ok_sql(
    "wired_upload_mbps", "wired_upload_rate_reason", "wired_observed_at"
)
_LAN_DOWN_OK = _rate_ok_sql(
    "lan_rx_mbps", "lan_rx_rate_reason", "lan_observed_at"
)
_LAN_UP_OK = _rate_ok_sql(
    "lan_tx_mbps", "lan_tx_rate_reason", "lan_observed_at"
)
_CURRENT_TRAFFIC_STATS_SQL = f"""
    WITH target AS (
      SELECT started_at, finished_at, ? AS evaluated_at
      FROM observation_cycles
      WHERE cycle_id=?
    )
    SELECT
      COUNT(*) AS stored_row_count,
      COALESCE(SUM(COALESCE(site_id!=?,1)),0) AS bad_site_count,
      COALESCE(SUM(COALESCE(NOT ({_CANONICAL_MAC_SQL}),1)),0)
        AS bad_mac_count,
      COUNT(*)-COUNT(DISTINCT ap_mac) AS duplicate_mac_count,
      COALESCE(SUM(COALESCE(partial!=0,1)
                   OR COALESCE(overview_ok!=1,1)
                   OR COALESCE(wired_uplink_ok!=1,1)
                   OR COALESCE(lan_traffic_ok!=1,1)
                   OR COALESCE(radios_ok!=1,1)),0) AS bad_flag_count,
      COALESCE(SUM(NOT ({_rate_valid_sql('wired_download_mbps', 'wired_download_rate_reason', 'wired_observed_at')})),0)
        + COALESCE(SUM(NOT ({_rate_valid_sql('wired_upload_mbps', 'wired_upload_rate_reason', 'wired_observed_at')})),0)
        + COALESCE(SUM(NOT ({_rate_valid_sql('lan_rx_mbps', 'lan_rx_rate_reason', 'lan_observed_at')})),0)
        + COALESCE(SUM(NOT ({_rate_valid_sql('lan_tx_mbps', 'lan_tx_rate_reason', 'lan_observed_at')})),0)
        AS bad_rate_count,
      COALESCE(SUM(wired_observed_at IS NULL),0) AS missing_wired_time_count,
      COALESCE(SUM(lan_observed_at IS NULL),0) AS missing_lan_time_count,
      MIN(wired_observed_at) AS wired_oldest,
      MAX(wired_observed_at) AS wired_newest,
      MIN(lan_observed_at) AS lan_oldest,
      MAX(lan_observed_at) AS lan_newest,
      COALESCE(SUM(({_WIRED_DOWN_OK}) AND ({_WIRED_UP_OK})),0)
        AS wired_pair_valid_count,
      COALESCE(SUM(({_LAN_DOWN_OK}) AND ({_LAN_UP_OK})),0)
        AS lan_pair_valid_count
    FROM ap_observations CROSS JOIN target
    WHERE cycle_id=?
"""

_HISTORICAL_WIRED_DOWN_OK = (
    "(a.wired_download_rate_reason='ok' AND a.wired_observed_at IS NOT NULL "
    "AND typeof(a.wired_download_mbps) IN ('integer','real') "
    "AND a.wired_download_mbps>=0 "
    "AND abs(a.wired_download_mbps)<=1.7976931348623157e308 "
    "AND a.wired_observed_at>=c.started_at "
    "AND a.wired_observed_at<=c.finished_at)"
)
_HISTORICAL_WIRED_UP_OK = _HISTORICAL_WIRED_DOWN_OK.replace(
    "download", "upload"
)
_HISTORICAL_LAN_DOWN_OK = (
    "(a.lan_rx_rate_reason='ok' AND a.lan_observed_at IS NOT NULL "
    "AND typeof(a.lan_rx_mbps) IN ('integer','real') "
    "AND a.lan_rx_mbps>=0 AND abs(a.lan_rx_mbps)<=1.7976931348623157e308 "
    "AND a.lan_observed_at>=c.started_at "
    "AND a.lan_observed_at<=c.finished_at)"
)
_HISTORICAL_LAN_UP_OK = _HISTORICAL_LAN_DOWN_OK.replace("lan_rx", "lan_tx")


def _historical_rate_shape(value: str, reason: str, timestamp: str) -> str:
    ok = (
        f"({reason}='ok' AND {timestamp} IS NOT NULL "
        f"AND typeof({value}) IN ('integer','real') AND {value}>=0 "
        f"AND abs({value})<=1.7976931348623157e308)"
    )
    return (
        f"COALESCE(({ok} OR ({reason} IN ({_NON_OK_RATE_REASONS_SQL}) "
        f"AND {value} IS NULL)),0)"
    )


def _utc_epoch_ms_sql(column: str) -> str:
    return (
        f"(CAST(strftime('%s',{column}) AS INTEGER)*1000 "
        f"+ CAST(substr({column},21,3) AS INTEGER))"
    )


_HISTORICAL_RANGE_CANDIDATES_CTE = """
    candidate_cycles AS (
      SELECT c.*
      FROM observation_cycles c INDEXED BY idx_cycles_site_kind_started
      WHERE c.site_id=? AND c.kind='ap_dynamic'
        AND c.state='completed' AND c.complete=1 AND c.result='success'
        AND c.started_at>=? AND c.started_at<?
        AND (c.finished_at IS NULL
             OR (c.finished_at>=? AND c.finished_at<?))
      UNION ALL
      SELECT c.*
      FROM observation_cycles c INDEXED BY idx_cycles_site_kind_started
      WHERE c.site_id=? AND c.kind='ap_dynamic'
        AND c.state='completed' AND c.complete=1 AND c.result='success'
        AND c.started_at<?
        AND c.finished_at>=? AND c.finished_at<?
    )
"""


_HISTORICAL_VALIDATION_CTES = f"""
    cycle_aggregates AS (
      SELECT c.cycle_id, c.started_at, c.finished_at,
        c.source_rows_reported, c.items_seen, c.items_stored,
        c.items_skipped, c.error_count, c.data_quality_warning_count,
        COUNT(a.row_id) AS stored_row_count,
        COALESCE(SUM(CASE WHEN a.row_id IS NULL THEN 0
          ELSE COALESCE(a.site_id<>?,1) END),0) AS bad_site_count,
        COALESCE(SUM(CASE WHEN a.row_id IS NULL THEN 0
          ELSE COALESCE(NOT ({_CANONICAL_MAC_SQL}),1) END),0)
          AS bad_mac_count,
        COUNT(a.row_id)-COUNT(DISTINCT a.ap_mac) AS duplicate_mac_count,
        COALESCE(SUM(CASE WHEN a.row_id IS NULL THEN 0 ELSE
          COALESCE(a.partial<>0,1) OR COALESCE(a.overview_ok<>1,1)
          OR COALESCE(a.wired_uplink_ok<>1,1)
          OR COALESCE(a.lan_traffic_ok<>1,1)
          OR COALESCE(a.radios_ok<>1,1) END),0) AS bad_flag_count,
        COALESCE(SUM(CASE WHEN a.row_id IS NULL THEN 0 ELSE
          NOT ({_historical_rate_shape('a.wired_download_mbps', 'a.wired_download_rate_reason', 'a.wired_observed_at')})
          OR NOT ({_historical_rate_shape('a.wired_upload_mbps', 'a.wired_upload_rate_reason', 'a.wired_observed_at')})
          OR NOT ({_historical_rate_shape('a.lan_rx_mbps', 'a.lan_rx_rate_reason', 'a.lan_observed_at')})
          OR NOT ({_historical_rate_shape('a.lan_tx_mbps', 'a.lan_tx_rate_reason', 'a.lan_observed_at')})
          END),0) AS bad_rate_count,
        COALESCE(SUM(CASE WHEN a.row_id IS NULL THEN 0 ELSE
          a.wired_observed_at IS NULL OR a.lan_observed_at IS NULL
          OR a.wired_observed_at<c.started_at
          OR a.wired_observed_at>c.finished_at
          OR a.lan_observed_at<c.started_at
          OR a.lan_observed_at>c.finished_at END),0) AS bad_time_count,
        COALESCE(SUM(({_HISTORICAL_WIRED_DOWN_OK})
                     AND ({_HISTORICAL_WIRED_UP_OK})),0) AS wired_pair_count,
        COALESCE(SUM(({_HISTORICAL_LAN_DOWN_OK})
                     AND ({_HISTORICAL_LAN_UP_OK})),0) AS lan_pair_count,
        MIN(a.wired_observed_at) AS wired_oldest,
        MAX(a.wired_observed_at) AS wired_newest,
        MIN(a.lan_observed_at) AS lan_oldest,
        MAX(a.lan_observed_at) AS lan_newest,
        COALESCE(SUM(a.wired_download_mbps),0.0) AS wired_download,
        COALESCE(SUM(a.wired_upload_mbps),0.0) AS wired_upload,
        COALESCE(SUM(a.lan_rx_mbps),0.0) AS lan_download,
        COALESCE(SUM(a.lan_tx_mbps),0.0) AS lan_upload,
        COALESCE(SUM(a.wired_download_rate_reason='no_baseline')
          +SUM(a.wired_upload_rate_reason='no_baseline'),0) AS wired_no_baseline,
        COALESCE(SUM(a.lan_rx_rate_reason='no_baseline')
          +SUM(a.lan_tx_rate_reason='no_baseline'),0) AS lan_no_baseline,
        COALESCE(SUM(a.wired_download_rate_reason='counter_reset')
          +SUM(a.wired_upload_rate_reason='counter_reset'),0) AS wired_counter_reset,
        COALESCE(SUM(a.lan_rx_rate_reason='counter_reset')
          +SUM(a.lan_tx_rate_reason='counter_reset'),0) AS lan_counter_reset,
        COALESCE(SUM(a.wired_download_rate_reason='gap_too_large')
          +SUM(a.wired_upload_rate_reason='gap_too_large'),0) AS wired_gap_too_large,
        COALESCE(SUM(a.lan_rx_rate_reason='gap_too_large')
          +SUM(a.lan_tx_rate_reason='gap_too_large'),0) AS lan_gap_too_large,
        COALESCE(SUM(a.wired_download_rate_reason='invalid_elapsed')
          +SUM(a.wired_upload_rate_reason='invalid_elapsed'),0) AS wired_invalid_elapsed,
        COALESCE(SUM(a.lan_rx_rate_reason='invalid_elapsed')
          +SUM(a.lan_tx_rate_reason='invalid_elapsed'),0) AS lan_invalid_elapsed,
        COALESCE(SUM(a.wired_download_rate_reason='source_unavailable')
          +SUM(a.wired_upload_rate_reason='source_unavailable'),0) AS wired_source_unavailable,
        COALESCE(SUM(a.lan_rx_rate_reason='source_unavailable')
          +SUM(a.lan_tx_rate_reason='source_unavailable'),0) AS lan_source_unavailable
        ,COALESCE(SUM(a.wired_download_rate_reason='ok')
          +SUM(a.wired_upload_rate_reason='ok'),0) AS wired_ok
        ,COALESCE(SUM(a.lan_rx_rate_reason='ok')
          +SUM(a.lan_tx_rate_reason='ok'),0) AS lan_ok
      FROM candidate_cycles c
      LEFT JOIN ap_observations a INDEXED BY sqlite_autoindex_ap_observations_1
        ON a.cycle_id=c.cycle_id
      GROUP BY c.cycle_id
    ),
    validated_cycles AS (
      SELECT *,
        (COALESCE(source_rows_reported=items_seen,0)
         AND finished_at IS NOT NULL AND finished_at>=started_at
         AND COALESCE(items_seen=items_stored,0)
         AND COALESCE(items_skipped=0,0)
         AND COALESCE(error_count=0,0)
         AND COALESCE(data_quality_warning_count=0,0)
         AND COALESCE(stored_row_count=items_stored,0)
         AND bad_site_count=0 AND bad_mac_count=0
         AND duplicate_mac_count=0 AND bad_flag_count=0
         AND bad_rate_count=0 AND bad_time_count=0) AS integrity_ok,
        (stored_row_count=0 OR
          (wired_pair_count=stored_row_count
           AND {_utc_epoch_ms_sql('wired_newest')}
               -{_utc_epoch_ms_sql('wired_oldest')}<=?))
          AS wired_complete,
        (stored_row_count=0 OR
          (lan_pair_count=stored_row_count
           AND {_utc_epoch_ms_sql('lan_newest')}
               -{_utc_epoch_ms_sql('lan_oldest')}<=?))
          AS lan_complete
      FROM cycle_aggregates
    )
"""


_HISTORICAL_CYCLE_CTES = (
    _HISTORICAL_RANGE_CANDIDATES_CTE
    + ","
    + _HISTORICAL_VALIDATION_CTES
)


_HISTORICAL_RANGED_SELECTION_CTES = f"""
  ranged AS (
    SELECT *, CAST((({_utc_epoch_ms_sql('finished_at')}
      -{_utc_epoch_ms_sql('?')})/(?*1000)) AS INTEGER)
      AS bucket_index
    FROM validated_cycles
    WHERE integrity_ok=1 AND finished_at>=? AND finished_at<?
  ),
  bucket_selection AS (
    SELECT bucket_index, COUNT(*) canonical_cycle_count,
      SUM(wired_complete) wired_complete_count,
      SUM(lan_complete) lan_complete_count,
      SUM(wired_pair_count) wired_pairs, SUM(lan_pair_count) lan_pairs,
      SUM(stored_row_count) total_ap_opportunities,
      SUM(stored_row_count=0) empty_cycle_count,
      CASE
        WHEN SUM(stored_row_count=0)=COUNT(*) THEN 'wired'
        WHEN SUM(wired_complete)=COUNT(*) THEN 'wired'
        WHEN SUM(lan_complete)=COUNT(*) THEN 'lan'
        WHEN SUM(lan_complete)>SUM(wired_complete) THEN 'lan'
        WHEN SUM(wired_complete)>SUM(lan_complete) THEN 'wired'
        WHEN SUM(lan_pair_count)>SUM(wired_pair_count) THEN 'lan'
        ELSE 'wired' END selected_source,
      CASE
        WHEN SUM(stored_row_count=0)=COUNT(*) THEN 'empty_population'
        WHEN SUM(wired_complete)=COUNT(*) THEN 'primary_full_coverage'
        WHEN SUM(lan_complete)=COUNT(*) THEN 'fallback_full_coverage'
        WHEN SUM(lan_complete)>SUM(wired_complete) THEN 'fallback_higher_coverage'
        WHEN SUM(wired_complete)>SUM(lan_complete) THEN 'primary_preferred_tie_or_higher'
        WHEN SUM(lan_pair_count)>SUM(wired_pair_count) THEN 'fallback_higher_coverage'
        ELSE 'primary_preferred_tie_or_higher' END selection_reason
    FROM ranged GROUP BY bucket_index
  )
"""


_HISTORICAL_BUCKET_SQL = f"""
  WITH {_HISTORICAL_CYCLE_CTES},
  {_HISTORICAL_RANGED_SELECTION_CTES},
  selected AS (
    SELECT r.*, s.selected_source,
      CASE WHEN s.selected_source='wired' THEN r.wired_download ELSE r.lan_download END download,
      CASE WHEN s.selected_source='wired' THEN r.wired_upload ELSE r.lan_upload END upload
    FROM ranged r JOIN bucket_selection s USING(bucket_index)
    WHERE CASE WHEN s.selected_source='wired' THEN r.wired_complete ELSE r.lan_complete END
  ),
  ordered AS (
    SELECT *, LAG(finished_at) OVER (
      PARTITION BY bucket_index ORDER BY finished_at,cycle_id) previous_at
    FROM selected
  ),
  sample_stats AS (
    SELECT bucket_index, COUNT(*) complete_sample_count,
      AVG(download) download_mbps, AVG(upload) upload_mbps,
      MIN(finished_at) first_sample, MAX(finished_at) last_sample,
      COALESCE(MAX(({_utc_epoch_ms_sql('finished_at')}
        -{_utc_epoch_ms_sql('previous_at')})/1000.0),0.0)
        max_inter_gap,
      COALESCE(SUM((({_utc_epoch_ms_sql('finished_at')}
        -{_utc_epoch_ms_sql('previous_at')})/1000.0)>?),0)
        inter_gap_count
    FROM ordered GROUP BY bucket_index
  )
  SELECT s.*,
    COALESCE(x.complete_sample_count,0) complete_sample_count,
    x.download_mbps, x.upload_mbps, x.first_sample, x.last_sample,
    COALESCE(x.max_inter_gap,0.0) max_inter_gap,
    COALESCE(x.inter_gap_count,0) inter_gap_count,
    COALESCE(SUM(CASE WHEN s.selected_source='wired' THEN r.wired_no_baseline ELSE r.lan_no_baseline END),0) no_baseline_count,
    COALESCE(SUM(CASE WHEN s.selected_source='wired' THEN r.wired_counter_reset ELSE r.lan_counter_reset END),0) counter_reset_count,
    COALESCE(SUM(CASE WHEN s.selected_source='wired' THEN r.wired_gap_too_large ELSE r.lan_gap_too_large END),0) gap_too_large_count,
    COALESCE(SUM(CASE WHEN s.selected_source='wired' THEN r.wired_invalid_elapsed ELSE r.lan_invalid_elapsed END),0) invalid_elapsed_count,
    COALESCE(SUM(CASE WHEN s.selected_source='wired' THEN r.wired_source_unavailable ELSE r.lan_source_unavailable END),0) source_unavailable_count,
    COALESCE(SUM(CASE WHEN s.selected_source='wired' THEN r.wired_ok ELSE r.lan_ok END),0) ok_count,
    COALESCE(SUM(CASE WHEN s.selected_source='wired'
      THEN r.wired_pair_count=r.stored_row_count AND NOT r.wired_complete
      ELSE r.lan_pair_count=r.stored_row_count AND NOT r.lan_complete END),0)
      skew_excluded_count
  FROM bucket_selection s JOIN ranged r USING(bucket_index)
  LEFT JOIN sample_stats x USING(bucket_index)
  GROUP BY s.bucket_index
  ORDER BY s.bucket_index
"""


_HISTORICAL_STATISTICS_SQL = f"""
  WITH {_HISTORICAL_CYCLE_CTES},
  {_HISTORICAL_RANGED_SELECTION_CTES},
  selected AS (
    SELECT r.cycle_id, r.finished_at, s.selected_source,
      CASE WHEN s.selected_source='wired'
        THEN r.wired_download ELSE r.lan_download END download,
      CASE WHEN s.selected_source='wired'
        THEN r.wired_upload ELSE r.lan_upload END upload
    FROM ranged r JOIN bucket_selection s USING(bucket_index)
    WHERE CASE WHEN s.selected_source='wired'
      THEN r.wired_complete ELSE r.lan_complete END
  ),
  ordered AS (
    SELECT *,
      LAG(finished_at) OVER (ORDER BY finished_at,cycle_id) previous_at,
      LAG(selected_source) OVER (ORDER BY finished_at,cycle_id) previous_source
    FROM selected
  ),
  classified AS (
    SELECT *,
      ({_utc_epoch_ms_sql('finished_at')}
       -{_utc_epoch_ms_sql('previous_at')})/1000.0 AS elapsed_seconds,
      CASE
        WHEN previous_at IS NULL THEN 'first'
        WHEN {_utc_epoch_ms_sql('previous_at')} IS NULL
          OR {_utc_epoch_ms_sql('finished_at')} IS NULL
          OR {_utc_epoch_ms_sql('finished_at')}
             -{_utc_epoch_ms_sql('previous_at')}<=0 THEN 'invalid'
        WHEN selected_source<>previous_source THEN 'source_transition'
        WHEN ({_utc_epoch_ms_sql('finished_at')}
              -{_utc_epoch_ms_sql('previous_at')})/1000.0>? THEN 'gap'
        ELSE 'accepted'
      END interval_result
    FROM ordered
  )
  SELECT
    COUNT(*) accepted_peak_sample_count,
    CASE WHEN COUNT(*)=0 THEN 0 ELSE COUNT(*)-1 END candidate_interval_count,
    COALESCE(SUM(interval_result='accepted'),0) accepted_interval_count,
    COALESCE(SUM(CASE WHEN interval_result='accepted'
      THEN elapsed_seconds ELSE 0.0 END),0.0) accepted_interval_seconds,
    COALESCE(SUM(interval_result='gap'),0) excluded_gap_interval_count,
    COALESCE(SUM(interval_result='source_transition'),0)
      excluded_source_transition_interval_count,
    COALESCE(SUM(interval_result='invalid'),0) invalid_period_interval_count,
    SUM(CASE WHEN interval_result='accepted'
      THEN download*elapsed_seconds END) weighted_download,
    SUM(CASE WHEN interval_result='accepted'
      THEN upload*elapsed_seconds END) weighted_upload,
    MAX(download) peak_download,
    MAX(upload) peak_upload,
    MAX(download+upload) peak_total,
    MIN(finished_at) first_sample_at,
    MAX(finished_at) last_sample_at
  FROM classified
"""


_HISTORICAL_COMBINED_CYCLE_CTES = (
    _HISTORICAL_CYCLE_CTES
    .replace(
        "candidate_cycles AS (",
        "candidate_cycles AS MATERIALIZED (",
        1,
    )
    .replace(
        "cycle_aggregates AS (",
        "cycle_aggregates AS MATERIALIZED (",
        1,
    )
    .replace(
        "validated_cycles AS (",
        "validated_cycles AS MATERIALIZED (",
        1,
    )
)
_HISTORICAL_COMBINED_RANGED_SELECTION_CTES = (
    _HISTORICAL_RANGED_SELECTION_CTES
    .replace("ranged AS (", "ranged AS MATERIALIZED (", 1)
    .replace(
        "bucket_selection AS (",
        "bucket_selection AS MATERIALIZED (",
        1,
    )
)

_HISTORICAL_STATISTICS_RESULT_FIELDS = (
    "accepted_peak_sample_count",
    "candidate_interval_count",
    "accepted_interval_count",
    "accepted_interval_seconds",
    "excluded_gap_interval_count",
    "excluded_source_transition_interval_count",
    "invalid_period_interval_count",
    "weighted_download",
    "weighted_upload",
    "peak_download",
    "peak_upload",
    "peak_total",
    "first_sample_at",
    "last_sample_at",
)

_HISTORICAL_BUCKET_RESULT_FIELDS = (
    "bucket_index",
    "canonical_cycle_count",
    "wired_complete_count",
    "lan_complete_count",
    "wired_pairs",
    "lan_pairs",
    "total_ap_opportunities",
    "empty_cycle_count",
    "selected_source",
    "selection_reason",
    "complete_sample_count",
    "download_mbps",
    "upload_mbps",
    "first_sample",
    "last_sample",
    "max_inter_gap",
    "inter_gap_count",
    "no_baseline_count",
    "counter_reset_count",
    "gap_too_large_count",
    "invalid_elapsed_count",
    "source_unavailable_count",
    "ok_count",
    "skew_excluded_count",
)

_HISTORICAL_PEAK_SAMPLE_FIELDS = (
    "peak_sample_finished_at",
    "peak_sample_selected_source",
    "peak_sample_download",
    "peak_sample_upload",
    "peak_sample_previous_at",
    "peak_sample_interval_result",
)

_HISTORICAL_AP_RESULT_FIELDS = (
    "ap_mac",
    "ap_current_name",
    "ap_historical_name",
    "ap_bucket_index",
    "ap_bucket_opportunity_count",
    "ap_bucket_accepted_count",
    "ap_bucket_download",
    "ap_bucket_upload",
    "ap_sample_opportunity_count",
    "ap_accepted_sample_count",
    "ap_site_accepted_interval_seconds",
    "ap_accepted_interval_seconds",
    "ap_weighted_download",
    "ap_weighted_upload",
    "ap_peak_download",
    "ap_peak_upload",
    "ap_peak_total",
    "ap_no_baseline_count",
    "ap_counter_reset_count",
    "ap_gap_too_large_count",
    "ap_invalid_elapsed_count",
    "ap_source_unavailable_count",
    "ap_missing_selected_source_sample_count",
    "ap_source_transition_excluded_interval_count",
)

_HISTORICAL_STATISTICS_AGGREGATES_SQL = """
      COUNT(*) accepted_peak_sample_count,
      CASE WHEN COUNT(*)=0 THEN 0 ELSE COUNT(*)-1 END
        candidate_interval_count,
      COALESCE(SUM(interval_result='accepted'),0) accepted_interval_count,
      COALESCE(SUM(CASE WHEN interval_result='accepted'
        THEN elapsed_seconds ELSE 0.0 END),0.0) accepted_interval_seconds,
      COALESCE(SUM(interval_result='gap'),0) excluded_gap_interval_count,
      COALESCE(SUM(interval_result='source_transition'),0)
        excluded_source_transition_interval_count,
      COALESCE(SUM(interval_result='invalid'),0)
        invalid_period_interval_count,
      SUM(CASE WHEN interval_result='accepted'
        THEN download*elapsed_seconds END) weighted_download,
      SUM(CASE WHEN interval_result='accepted'
        THEN upload*elapsed_seconds END) weighted_upload,
      MAX(download) peak_download,
      MAX(upload) peak_upload,
      MAX(download+upload) peak_total,
      MIN(finished_at) first_sample_at,
      MAX(finished_at) last_sample_at
"""


_HISTORICAL_COMBINED_CTES_SQL = f"""
  WITH {_HISTORICAL_COMBINED_CYCLE_CTES},
  integrity_meta AS MATERIALIZED (
    SELECT
      COALESCE(SUM(NOT integrity_ok AND (
        (finished_at>=? AND finished_at<?)
        OR (finished_at IS NULL AND started_at>=? AND started_at<?))),0)
        integrity_failure_count
    FROM validated_cycles
  ),
  {_HISTORICAL_COMBINED_RANGED_SELECTION_CTES},
  bucket_selected AS (
    SELECT r.*, s.selected_source,
      CASE WHEN s.selected_source='wired'
        THEN r.wired_download ELSE r.lan_download END download,
      CASE WHEN s.selected_source='wired'
        THEN r.wired_upload ELSE r.lan_upload END upload
    FROM ranged r JOIN bucket_selection s USING(bucket_index)
    WHERE CASE WHEN s.selected_source='wired'
      THEN r.wired_complete ELSE r.lan_complete END
  ),
  bucket_ordered AS (
    SELECT *, LAG(finished_at) OVER (
      PARTITION BY bucket_index ORDER BY finished_at,cycle_id) previous_at
    FROM bucket_selected
  ),
  bucket_sample_stats AS (
    SELECT bucket_index, COUNT(*) complete_sample_count,
      AVG(download) download_mbps, AVG(upload) upload_mbps,
      MIN(finished_at) first_sample, MAX(finished_at) last_sample,
      COALESCE(MAX(({_utc_epoch_ms_sql('finished_at')}
        -{_utc_epoch_ms_sql('previous_at')})/1000.0),0.0)
        max_inter_gap,
      COALESCE(SUM((({_utc_epoch_ms_sql('finished_at')}
        -{_utc_epoch_ms_sql('previous_at')})/1000.0)>?),0)
        inter_gap_count
    FROM bucket_ordered GROUP BY bucket_index
  ),
  bucket_rows AS (
    SELECT s.*,
      COALESCE(x.complete_sample_count,0) complete_sample_count,
      x.download_mbps, x.upload_mbps, x.first_sample, x.last_sample,
      COALESCE(x.max_inter_gap,0.0) max_inter_gap,
      COALESCE(x.inter_gap_count,0) inter_gap_count,
      COALESCE(SUM(CASE WHEN s.selected_source='wired'
        THEN r.wired_no_baseline ELSE r.lan_no_baseline END),0)
        no_baseline_count,
      COALESCE(SUM(CASE WHEN s.selected_source='wired'
        THEN r.wired_counter_reset ELSE r.lan_counter_reset END),0)
        counter_reset_count,
      COALESCE(SUM(CASE WHEN s.selected_source='wired'
        THEN r.wired_gap_too_large ELSE r.lan_gap_too_large END),0)
        gap_too_large_count,
      COALESCE(SUM(CASE WHEN s.selected_source='wired'
        THEN r.wired_invalid_elapsed ELSE r.lan_invalid_elapsed END),0)
        invalid_elapsed_count,
      COALESCE(SUM(CASE WHEN s.selected_source='wired'
        THEN r.wired_source_unavailable ELSE r.lan_source_unavailable END),0)
        source_unavailable_count,
      COALESCE(SUM(CASE WHEN s.selected_source='wired'
        THEN r.wired_ok ELSE r.lan_ok END),0) ok_count,
      COALESCE(SUM(CASE WHEN s.selected_source='wired'
        THEN r.wired_pair_count=r.stored_row_count AND NOT r.wired_complete
        ELSE r.lan_pair_count=r.stored_row_count AND NOT r.lan_complete END),0)
        skew_excluded_count
    FROM bucket_selection s JOIN ranged r USING(bucket_index)
    LEFT JOIN bucket_sample_stats x USING(bucket_index)
    GROUP BY s.bucket_index
  ),
  statistics_selected AS (
    SELECT r.cycle_id, r.finished_at, s.selected_source,
      CASE WHEN s.selected_source='wired'
        THEN r.wired_download ELSE r.lan_download END download,
      CASE WHEN s.selected_source='wired'
        THEN r.wired_upload ELSE r.lan_upload END upload
    FROM ranged r JOIN bucket_selection s USING(bucket_index)
    WHERE CASE WHEN s.selected_source='wired'
      THEN r.wired_complete ELSE r.lan_complete END
  ),
  statistics_ordered AS (
    SELECT *,
      ROW_NUMBER() OVER (ORDER BY finished_at,cycle_id) sequence_no,
      LAG(finished_at) OVER (ORDER BY finished_at,cycle_id) previous_at,
      LAG(selected_source) OVER (
        ORDER BY finished_at,cycle_id) previous_source
    FROM statistics_selected
  ),
  statistics_classified AS (
    SELECT *,
      ({_utc_epoch_ms_sql('finished_at')}
       -{_utc_epoch_ms_sql('previous_at')})/1000.0 AS elapsed_seconds,
      CASE
        WHEN previous_at IS NULL THEN 'first'
        WHEN {_utc_epoch_ms_sql('previous_at')} IS NULL
          OR {_utc_epoch_ms_sql('finished_at')} IS NULL
          OR {_utc_epoch_ms_sql('finished_at')}
             -{_utc_epoch_ms_sql('previous_at')}<=0 THEN 'invalid'
        WHEN selected_source<>previous_source THEN 'source_transition'
        WHEN ({_utc_epoch_ms_sql('finished_at')}
              -{_utc_epoch_ms_sql('previous_at')})/1000.0>? THEN 'gap'
        ELSE 'accepted'
      END interval_result
    FROM statistics_ordered
  ),
  statistics_row AS (
    SELECT
      {_HISTORICAL_STATISTICS_AGGREGATES_SQL}
    FROM statistics_classified
  )
"""

_HISTORICAL_COMBINED_SQL = _HISTORICAL_COMBINED_CTES_SQL + """
  SELECT b.*, m.integrity_failure_count, p.*
  FROM integrity_meta m
  CROSS JOIN statistics_row p
  LEFT JOIN bucket_rows b ON 1=1
  ORDER BY b.bucket_index
"""

_HISTORICAL_PEAK_STATISTICS_SELECT_SQL = ",\n    ".join(
    f"p.{field}" for field in _HISTORICAL_STATISTICS_RESULT_FIELDS
)

_HISTORICAL_PEAK_BUCKET_SELECT_SQL = ",\n    ".join(
    f"b.{field}" for field in _HISTORICAL_BUCKET_RESULT_FIELDS
)
_HISTORICAL_PEAK_NULL_BUCKET_SELECT_SQL = ",\n    ".join(
    f"NULL AS {field}" for field in _HISTORICAL_BUCKET_RESULT_FIELDS
)
_HISTORICAL_PEAK_NULL_STATISTICS_SELECT_SQL = ",\n    ".join(
    f"NULL AS {field}" for field in _HISTORICAL_STATISTICS_RESULT_FIELDS
)
_HISTORICAL_PEAK_NULL_SAMPLE_SELECT_SQL = ",\n    ".join(
    f"NULL AS {field}" for field in _HISTORICAL_PEAK_SAMPLE_FIELDS
)

_HISTORICAL_PEAK_COMBINED_SQL = _HISTORICAL_COMBINED_CTES_SQL + f"""
  SELECT 0 AS projection_kind, b.bucket_index AS projection_order,
    {_HISTORICAL_PEAK_BUCKET_SELECT_SQL},
    m.integrity_failure_count,
    {_HISTORICAL_PEAK_STATISTICS_SELECT_SQL},
    {_HISTORICAL_PEAK_NULL_SAMPLE_SELECT_SQL}
  FROM integrity_meta m
  CROSS JOIN statistics_row p
  LEFT JOIN bucket_rows b ON 1=1
  UNION ALL
  SELECT 1 AS projection_kind, s.sequence_no AS projection_order,
    {_HISTORICAL_PEAK_NULL_BUCKET_SELECT_SQL},
    NULL AS integrity_failure_count,
    {_HISTORICAL_PEAK_NULL_STATISTICS_SELECT_SQL},
    s.finished_at AS peak_sample_finished_at,
    s.selected_source AS peak_sample_selected_source,
    s.download AS peak_sample_download,
    s.upload AS peak_sample_upload,
    s.previous_at AS peak_sample_previous_at,
    s.interval_result AS peak_sample_interval_result
  FROM statistics_classified s
  ORDER BY projection_kind, projection_order
"""

_HISTORICAL_AP_NULL_RESULT_SELECT_SQL = ",\n    ".join(
    f"NULL AS {field}" for field in _HISTORICAL_AP_RESULT_FIELDS
)
_HISTORICAL_AP_RESULT_SELECT_SQL = ",\n    ".join(
    f"x.{field}" for field in _HISTORICAL_AP_RESULT_FIELDS
)

_HISTORICAL_AP_CTES_SQL = _HISTORICAL_COMBINED_CTES_SQL + f""",
  ap_request AS MATERIALIZED (
    SELECT ? AS current_cycle_id, ? AS site_id
  ),
  ap_population_evidence AS MATERIALIZED (
    SELECT a.ap_mac,
      MAX(a.cycle_id=q.current_cycle_id) AS current_member,
      MAX(r.cycle_id IS NOT NULL) AS historical_member,
      MAX(CASE WHEN a.cycle_id=q.current_cycle_id
        AND a.name IS NOT NULL AND trim(a.name)<>'' THEN a.name END)
        AS current_name
    FROM ap_observations a
    CROSS JOIN ap_request q
    LEFT JOIN ranged r ON r.cycle_id=a.cycle_id
    WHERE a.site_id=q.site_id
      AND (a.cycle_id=q.current_cycle_id OR r.cycle_id IS NOT NULL)
    GROUP BY a.ap_mac
  ),
  ap_historical_names_ranked AS MATERIALIZED (
    SELECT a.ap_mac, a.name,
      ROW_NUMBER() OVER (
        PARTITION BY a.ap_mac ORDER BY r.finished_at DESC, r.cycle_id DESC
      ) AS name_rank
    FROM ranged r
    JOIN ap_observations a ON a.cycle_id=r.cycle_id
    CROSS JOIN ap_request q
    WHERE a.site_id=q.site_id AND a.name IS NOT NULL AND trim(a.name)<>''
  ),
  ap_population AS MATERIALIZED (
    SELECT e.ap_mac, e.current_member, e.historical_member,
      e.current_name, n.name AS historical_name
    FROM ap_population_evidence e
    LEFT JOIN ap_historical_names_ranked n
      ON n.ap_mac=e.ap_mac AND n.name_rank=1
  ),
  ap_population_meta AS MATERIALIZED (
    SELECT COUNT(*) AS population_count,
      COALESCE(SUM(current_member),0) AS current_population_count,
      COALESCE(SUM(historical_member),0) AS historical_population_count
    FROM ap_population
  ),
  ap_supported_population AS MATERIALIZED (
    SELECT p.* FROM ap_population p CROSS JOIN ap_population_meta m
    WHERE m.population_count<=12
  ),
  ap_bucket_rows AS MATERIALIZED (
    SELECT p.ap_mac, s.bucket_index,
      COUNT(b.cycle_id) AS opportunity_count,
      COUNT(a.row_id) AS accepted_count,
      AVG(CASE WHEN b.selected_source='wired'
        THEN a.wired_download_mbps ELSE a.lan_rx_mbps END) AS download,
      AVG(CASE WHEN b.selected_source='wired'
        THEN a.wired_upload_mbps ELSE a.lan_tx_mbps END) AS upload
    FROM ap_supported_population p
    CROSS JOIN bucket_selection s
    LEFT JOIN bucket_selected b ON b.bucket_index=s.bucket_index
    LEFT JOIN ap_observations a
      ON a.cycle_id=b.cycle_id AND a.ap_mac=p.ap_mac
    GROUP BY p.ap_mac, s.bucket_index
  ),
  ap_sample_rows AS MATERIALIZED (
    SELECT p.ap_mac, s.cycle_id, s.selected_source, s.interval_result,
      s.elapsed_seconds,
      a.row_id,
      CASE WHEN s.selected_source='wired'
        THEN a.wired_download_mbps ELSE a.lan_rx_mbps END AS download,
      CASE WHEN s.selected_source='wired'
        THEN a.wired_upload_mbps ELSE a.lan_tx_mbps END AS upload
    FROM ap_supported_population p
    CROSS JOIN statistics_classified s
    LEFT JOIN ap_observations a
      ON a.cycle_id=s.cycle_id AND a.ap_mac=p.ap_mac
  ),
  ap_quality_rows AS MATERIALIZED (
    SELECT p.ap_mac, r.cycle_id, s.selected_source, a.row_id,
      CASE WHEN s.selected_source='wired'
        THEN a.wired_download_rate_reason ELSE a.lan_rx_rate_reason END
        AS download_reason,
      CASE WHEN s.selected_source='wired'
        THEN a.wired_upload_rate_reason ELSE a.lan_tx_rate_reason END
        AS upload_reason
    FROM ap_supported_population p
    CROSS JOIN ranged r
    JOIN bucket_selection s USING(bucket_index)
    LEFT JOIN ap_observations a
      ON a.cycle_id=r.cycle_id AND a.ap_mac=p.ap_mac
  ),
  ap_quality_aggregates AS MATERIALIZED (
    SELECT ap_mac,
      COALESCE(SUM(download_reason='no_baseline')
        +SUM(upload_reason='no_baseline'),0) AS no_baseline_count,
      COALESCE(SUM(download_reason='counter_reset')
        +SUM(upload_reason='counter_reset'),0) AS counter_reset_count,
      COALESCE(SUM(download_reason='gap_too_large')
        +SUM(upload_reason='gap_too_large'),0) AS gap_too_large_count,
      COALESCE(SUM(download_reason='invalid_elapsed')
        +SUM(upload_reason='invalid_elapsed'),0) AS invalid_elapsed_count,
      COALESCE(SUM(download_reason='source_unavailable')
        +SUM(upload_reason='source_unavailable'),0) AS source_unavailable_count
    FROM ap_quality_rows GROUP BY ap_mac
  ),
  ap_aggregates AS MATERIALIZED (
    SELECT p.ap_mac,
      COUNT(s.cycle_id) AS sample_opportunity_count,
      COUNT(s.row_id) AS accepted_sample_count,
      COALESCE(SUM(CASE WHEN s.interval_result='accepted'
        THEN s.elapsed_seconds ELSE 0 END),0.0)
        AS site_accepted_interval_seconds,
      COALESCE(SUM(CASE WHEN s.interval_result='accepted' AND s.row_id IS NOT NULL
        THEN s.elapsed_seconds ELSE 0 END),0.0)
        AS accepted_interval_seconds,
      SUM(CASE WHEN s.interval_result='accepted' AND s.row_id IS NOT NULL
        THEN s.download*s.elapsed_seconds END) AS weighted_download,
      SUM(CASE WHEN s.interval_result='accepted' AND s.row_id IS NOT NULL
        THEN s.upload*s.elapsed_seconds END) AS weighted_upload,
      MAX(CASE WHEN s.row_id IS NOT NULL THEN s.download END) AS peak_download,
      MAX(CASE WHEN s.row_id IS NOT NULL THEN s.upload END) AS peak_upload,
      MAX(CASE WHEN s.row_id IS NOT NULL THEN s.download+s.upload END)
        AS peak_total,
      COUNT(s.cycle_id)-COUNT(s.row_id) AS missing_selected_source_sample_count,
      COALESCE(SUM(s.interval_result='source_transition'
        AND s.row_id IS NOT NULL),0) AS source_transition_excluded_interval_count
    FROM ap_supported_population p
    LEFT JOIN ap_sample_rows s ON s.ap_mac=p.ap_mac
    GROUP BY p.ap_mac
  ),
  ap_result_rows AS MATERIALIZED (
    SELECT p.ap_mac, p.current_name AS ap_current_name,
      p.historical_name AS ap_historical_name,
      b.bucket_index AS ap_bucket_index,
      b.opportunity_count AS ap_bucket_opportunity_count,
      b.accepted_count AS ap_bucket_accepted_count,
      b.download AS ap_bucket_download,
      b.upload AS ap_bucket_upload,
      g.sample_opportunity_count AS ap_sample_opportunity_count,
      g.accepted_sample_count AS ap_accepted_sample_count,
      g.site_accepted_interval_seconds AS ap_site_accepted_interval_seconds,
      g.accepted_interval_seconds AS ap_accepted_interval_seconds,
      g.weighted_download AS ap_weighted_download,
      g.weighted_upload AS ap_weighted_upload,
      g.peak_download AS ap_peak_download,
      g.peak_upload AS ap_peak_upload,
      g.peak_total AS ap_peak_total,
      COALESCE(q.no_baseline_count,0) AS ap_no_baseline_count,
      COALESCE(q.counter_reset_count,0) AS ap_counter_reset_count,
      COALESCE(q.gap_too_large_count,0) AS ap_gap_too_large_count,
      COALESCE(q.invalid_elapsed_count,0) AS ap_invalid_elapsed_count,
      COALESCE(q.source_unavailable_count,0) AS ap_source_unavailable_count,
      g.missing_selected_source_sample_count
        AS ap_missing_selected_source_sample_count,
      g.source_transition_excluded_interval_count
        AS ap_source_transition_excluded_interval_count
    FROM ap_supported_population p
    JOIN ap_aggregates g USING(ap_mac)
    LEFT JOIN ap_quality_aggregates q USING(ap_mac)
    LEFT JOIN ap_bucket_rows b USING(ap_mac)
  )
"""

_HISTORICAL_AP_BASE_SELECT_SQL = f"""
  SELECT 0 AS projection_kind, b.bucket_index AS projection_order,
    {_HISTORICAL_PEAK_BUCKET_SELECT_SQL},
    m.integrity_failure_count,
    {_HISTORICAL_PEAK_STATISTICS_SELECT_SQL},
    {_HISTORICAL_PEAK_NULL_SAMPLE_SELECT_SQL},
    pm.population_count AS ap_population_count,
    pm.current_population_count AS ap_current_population_count,
    pm.historical_population_count AS ap_historical_population_count,
    {_HISTORICAL_AP_NULL_RESULT_SELECT_SQL}
  FROM integrity_meta m
  CROSS JOIN statistics_row p
  CROSS JOIN ap_population_meta pm
  LEFT JOIN bucket_rows b ON 1=1
"""

_HISTORICAL_AP_ROWS_SELECT_SQL = f"""
  SELECT 2 AS projection_kind,
    ROW_NUMBER() OVER (ORDER BY x.ap_mac, x.ap_bucket_index) AS projection_order,
    {_HISTORICAL_PEAK_NULL_BUCKET_SELECT_SQL},
    NULL AS integrity_failure_count,
    {_HISTORICAL_PEAK_NULL_STATISTICS_SELECT_SQL},
    {_HISTORICAL_PEAK_NULL_SAMPLE_SELECT_SQL},
    pm.population_count AS ap_population_count,
    pm.current_population_count AS ap_current_population_count,
    pm.historical_population_count AS ap_historical_population_count,
    {_HISTORICAL_AP_RESULT_SELECT_SQL}
  FROM ap_population_meta pm
  JOIN ap_result_rows x ON 1=1
"""

_HISTORICAL_AP_COMBINED_SQL = _HISTORICAL_AP_CTES_SQL + f"""
  {_HISTORICAL_AP_BASE_SELECT_SQL}
  UNION ALL
  {_HISTORICAL_AP_ROWS_SELECT_SQL}
  ORDER BY projection_kind, projection_order
"""

_HISTORICAL_AP_PEAK_COMBINED_SQL = _HISTORICAL_AP_CTES_SQL + f"""
  {_HISTORICAL_AP_BASE_SELECT_SQL}
  UNION ALL
  SELECT 1 AS projection_kind, s.sequence_no AS projection_order,
    {_HISTORICAL_PEAK_NULL_BUCKET_SELECT_SQL},
    NULL AS integrity_failure_count,
    {_HISTORICAL_PEAK_NULL_STATISTICS_SELECT_SQL},
    s.finished_at AS peak_sample_finished_at,
    s.selected_source AS peak_sample_selected_source,
    s.download AS peak_sample_download,
    s.upload AS peak_sample_upload,
    s.previous_at AS peak_sample_previous_at,
    s.interval_result AS peak_sample_interval_result,
    pm.population_count AS ap_population_count,
    pm.current_population_count AS ap_current_population_count,
    pm.historical_population_count AS ap_historical_population_count,
    {_HISTORICAL_AP_NULL_RESULT_SELECT_SQL}
  FROM statistics_classified s CROSS JOIN ap_population_meta pm
  UNION ALL
  {_HISTORICAL_AP_ROWS_SELECT_SQL}
  ORDER BY projection_kind, projection_order
"""



# TASK-TRAFFIC-05 R6: lean AP support reuses the existing Site
# History/Statistics projection. Only cycle identity/bucket support is added;
# AP identity is discovered before the heavier bounded raw-rate projection.
_HISTORICAL_AP_LEAN_CTES_SQL = _HISTORICAL_COMBINED_CTES_SQL.replace(
    "SELECT r.cycle_id, r.finished_at, s.selected_source,",
    "SELECT r.cycle_id, r.finished_at, r.bucket_index, s.selected_source,",
    1,
)

_HISTORICAL_AP_LEAN_COMBINED_SQL = _HISTORICAL_AP_LEAN_CTES_SQL + f"""
  SELECT 0 AS projection_kind, b.bucket_index AS projection_order,
    {_HISTORICAL_PEAK_BUCKET_SELECT_SQL},
    m.integrity_failure_count,
    {_HISTORICAL_PEAK_STATISTICS_SELECT_SQL},
    {_HISTORICAL_PEAK_NULL_SAMPLE_SELECT_SQL},
    NULL AS ap_support_cycle_id,
    NULL AS ap_support_bucket_index
  FROM integrity_meta m
  CROSS JOIN statistics_row p
  LEFT JOIN bucket_rows b ON 1=1

  UNION ALL

  SELECT 1 AS projection_kind, s.sequence_no AS projection_order,
    {_HISTORICAL_PEAK_NULL_BUCKET_SELECT_SQL},
    NULL AS integrity_failure_count,
    {_HISTORICAL_PEAK_NULL_STATISTICS_SELECT_SQL},
    s.finished_at AS peak_sample_finished_at,
    s.selected_source AS peak_sample_selected_source,
    s.download AS peak_sample_download,
    s.upload AS peak_sample_upload,
    s.previous_at AS peak_sample_previous_at,
    s.interval_result AS peak_sample_interval_result,
    s.cycle_id AS ap_support_cycle_id,
    s.bucket_index AS ap_support_bucket_index
  FROM statistics_classified s

  UNION ALL

  SELECT 2 AS projection_kind,
    ROW_NUMBER() OVER (ORDER BY r.finished_at,r.cycle_id)
      AS projection_order,
    {_HISTORICAL_PEAK_NULL_BUCKET_SELECT_SQL},
    NULL AS integrity_failure_count,
    {_HISTORICAL_PEAK_NULL_STATISTICS_SELECT_SQL},
    r.finished_at AS peak_sample_finished_at,
    s.selected_source AS peak_sample_selected_source,
    NULL AS peak_sample_download,
    NULL AS peak_sample_upload,
    NULL AS peak_sample_previous_at,
    NULL AS peak_sample_interval_result,
    r.cycle_id AS ap_support_cycle_id,
    r.bucket_index AS ap_support_bucket_index
  FROM ranged r
  JOIN bucket_selection s USING(bucket_index)
  WHERE NOT CASE WHEN s.selected_source='wired'
    THEN r.wired_complete ELSE r.lan_complete END

  ORDER BY projection_kind, projection_order
"""

_HISTORICAL_AP_CANDIDATES_MATERIALIZED_CTE = (
    _HISTORICAL_RANGE_CANDIDATES_CTE.replace(
        "candidate_cycles AS (",
        "candidate_cycles AS MATERIALIZED (",
        1,
    )
)

_HISTORICAL_AP_IDENTITY_SQL = f"""
  WITH {_HISTORICAL_AP_CANDIDATES_MATERIALIZED_CTE}
  SELECT c.cycle_id, a.ap_mac
  FROM candidate_cycles c
  CROSS JOIN ap_observations a
    INDEXED BY sqlite_autoindex_ap_observations_1
  WHERE a.cycle_id=c.cycle_id AND a.site_id=?
"""

_HISTORICAL_AP_RAW_SQL = f"""
  WITH {_HISTORICAL_AP_CANDIDATES_MATERIALIZED_CTE}
  SELECT c.cycle_id, c.finished_at,
    a.ap_mac, a.row_id, a.name,
    a.wired_download_mbps, a.wired_upload_mbps,
    a.wired_download_rate_reason, a.wired_upload_rate_reason,
    a.lan_rx_mbps, a.lan_tx_mbps,
    a.lan_rx_rate_reason, a.lan_tx_rate_reason
  FROM candidate_cycles c
  CROSS JOIN ap_observations a
    INDEXED BY sqlite_autoindex_ap_observations_1
  WHERE a.cycle_id=c.cycle_id AND a.site_id=?
"""

_HISTORICAL_AP_CURRENT_IDENTITY_SQL = """
  SELECT a.ap_mac, a.name
  FROM ap_observations a
    INDEXED BY sqlite_autoindex_ap_observations_1
  WHERE a.cycle_id=? AND a.site_id=?
  ORDER BY a.ap_mac
"""


def _historical_ap_epoch_ms(value: str) -> int:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return int(parsed.timestamp()) * 1000 + parsed.microsecond // 1000


_HISTORICAL_AP_QUALITY_REASONS = frozenset((
    "no_baseline",
    "counter_reset",
    "gap_too_large",
    "invalid_elapsed",
    "source_unavailable",
))


def _historical_ap_population_and_rows(
    *,
    support_rows: Sequence[Mapping[str, Any]],
    identity_rows: Sequence[Mapping[str, Any]],
    raw_rows: Sequence[Mapping[str, Any]],
    current_identity_rows: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, int], tuple[Mapping[str, Any], ...]]:
    """Compose the exact R3 AP aggregate-row contract in one raw-row pass."""
    support: dict[str, dict[str, Any]] = {}
    complete_support: list[dict[str, Any]] = []
    bucket_opportunity_count: dict[int, int] = {}
    site_accepted_interval_seconds = 0.0

    for source_row in support_rows:
        row = source_row
        kind = int(row["projection_kind"])
        if kind not in (1, 2):
            continue

        cycle_id = row["ap_support_cycle_id"]
        bucket_index = row["ap_support_bucket_index"]
        finished_at = row["peak_sample_finished_at"]
        selected_source = row["peak_sample_selected_source"]
        if (
            not isinstance(cycle_id, str)
            or not cycle_id
            or type(bucket_index) is not int
            or bucket_index < 0
            or not isinstance(finished_at, str)
            or not finished_at
            or selected_source not in {"wired", "lan"}
            or cycle_id in support
        ):
            raise AnalyticsSourceUnavailable(
                "Historical AP lean support is unavailable"
            )

        previous_at = row["peak_sample_previous_at"]
        interval_result = row["peak_sample_interval_result"]
        elapsed: float | None = None

        if kind == 1:
            if interval_result not in {
                "first", "accepted", "gap", "source_transition", "invalid"
            }:
                raise AnalyticsSourceUnavailable(
                    "Historical AP interval support is unavailable"
                )
            if isinstance(previous_at, str) and previous_at:
                elapsed = (
                    _historical_ap_epoch_ms(finished_at)
                    - _historical_ap_epoch_ms(previous_at)
                ) / 1000.0
            if interval_result == "accepted":
                if elapsed is None or elapsed <= 0:
                    raise AnalyticsSourceUnavailable(
                        "Historical AP accepted interval is unavailable"
                    )
                site_accepted_interval_seconds += elapsed
            bucket_opportunity_count[bucket_index] = (
                bucket_opportunity_count.get(bucket_index, 0) + 1
            )

        item = {
            "cycle_id": cycle_id,
            "bucket_index": bucket_index,
            "finished_at": finished_at,
            "selected_source": selected_source,
            "selected_complete": kind == 1,
            "interval_result": interval_result,
            "elapsed": elapsed,
        }
        support[cycle_id] = item
        if kind == 1:
            complete_support.append(item)

    support_ids = set(support)
    sample_opportunity_count = len(complete_support)
    bucket_indexes = sorted({
        int(item["bucket_index"]) for item in support.values()
    })

    historical_macs: set[str] = set()
    seen_identity_keys: set[tuple[str, str]] = set()
    for source_row in identity_rows:
        row = source_row
        cycle_id = row["cycle_id"]
        mac = row["ap_mac"]
        if not isinstance(cycle_id, str) or not isinstance(mac, str):
            raise AnalyticsSourceUnavailable(
                "Historical AP identity projection is unavailable"
            )
        if cycle_id not in support_ids:
            continue
        key = (cycle_id, mac)
        if key in seen_identity_keys:
            raise AnalyticsSourceUnavailable(
                "Historical AP identity projection contains duplicates"
            )
        seen_identity_keys.add(key)
        historical_macs.add(mac)

    current_names: dict[str, str | None] = {}
    for source_row in current_identity_rows:
        row = source_row
        mac = row["ap_mac"]
        if not isinstance(mac, str) or not mac or mac in current_names:
            raise AnalyticsSourceUnavailable(
                "Current AP identity projection is unavailable"
            )
        name = row["name"]
        current_names[mac] = (
            name if isinstance(name, str) and name.strip() else None
        )

    population_macs = set(current_names) | historical_macs
    population = {
        "population_count": len(population_macs),
        "current_population_count": len(current_names),
        "historical_population_count": len(historical_macs),
    }

    if len(population_macs) > 12:
        if raw_rows:
            raise AnalyticsSourceUnavailable(
                "Unsupported AP population was materialized"
            )
        return population, ()

    if not population_macs:
        if raw_rows:
            raise AnalyticsSourceUnavailable(
                "Historical AP raw projection is unexpected"
            )
        return population, ()

    def new_state() -> dict[str, Any]:
        return {
            "accepted_sample_count": 0,
            "accepted_interval_seconds": 0.0,
            "weighted_download": 0.0,
            "weighted_upload": 0.0,
            "peak_download": None,
            "peak_upload": None,
            "peak_total": None,
            "no_baseline": 0,
            "counter_reset": 0,
            "gap_too_large": 0,
            "invalid_elapsed": 0,
            "source_unavailable": 0,
            "source_transition_excluded_interval_count": 0,
            "historical_name": None,
            "historical_name_key": None,
            "buckets": {},
        }

    states: dict[str, dict[str, Any]] = {
        mac: new_state() for mac in population_macs
    }
    raw_historical_macs: set[str] = set()
    seen_raw_keys: set[tuple[str, str]] = set()

    for source_row in raw_rows:
        row = source_row
        cycle_id = row["cycle_id"]
        mac = row["ap_mac"]
        if not isinstance(cycle_id, str) or not isinstance(mac, str):
            raise AnalyticsSourceUnavailable(
                "Historical AP raw projection is unavailable"
            )

        item = support.get(cycle_id)
        if item is None:
            continue

        key = (cycle_id, mac)
        if key in seen_raw_keys:
            raise AnalyticsSourceUnavailable(
                "Historical AP raw projection contains duplicates"
            )
        seen_raw_keys.add(key)
        raw_historical_macs.add(mac)

        state = states.get(mac)
        if state is None:
            raise AnalyticsSourceUnavailable(
                "Historical AP raw population projection is inconsistent"
            )

        selected_source = str(item["selected_source"])
        if selected_source == "wired":
            download = row["wired_download_mbps"]
            upload = row["wired_upload_mbps"]
            down_reason = row["wired_download_rate_reason"]
            up_reason = row["wired_upload_rate_reason"]
        else:
            download = row["lan_rx_mbps"]
            upload = row["lan_tx_mbps"]
            down_reason = row["lan_rx_rate_reason"]
            up_reason = row["lan_tx_rate_reason"]

        if down_reason in _HISTORICAL_AP_QUALITY_REASONS:
            state[down_reason] += 1
        if up_reason in _HISTORICAL_AP_QUALITY_REASONS:
            state[up_reason] += 1

        name = row["name"]
        if isinstance(name, str) and name.strip():
            name_key = (str(item["finished_at"]), cycle_id)
            if (
                state["historical_name_key"] is None
                or name_key > state["historical_name_key"]
            ):
                state["historical_name_key"] = name_key
                state["historical_name"] = name

        # Incomplete support cycles are valid quality/name evidence, but
        # their bucket-selected rate may legitimately be unavailable.
        # R3 validates D/U only for selected-complete samples.
        if not item["selected_complete"]:
            continue

        if (
            type(download) not in (int, float)
            or isinstance(download, bool)
            or type(upload) not in (int, float)
            or isinstance(upload, bool)
            or float(download) < 0
            or float(upload) < 0
        ):
            raise AnalyticsSourceUnavailable(
                "Historical AP selected rate is unavailable"
            )

        download = float(download)
        upload = float(upload)

        state["accepted_sample_count"] += 1
        state["peak_download"] = (
            download
            if state["peak_download"] is None
            else max(state["peak_download"], download)
        )
        state["peak_upload"] = (
            upload
            if state["peak_upload"] is None
            else max(state["peak_upload"], upload)
        )
        total = download + upload
        state["peak_total"] = (
            total
            if state["peak_total"] is None
            else max(state["peak_total"], total)
        )

        interval_result = item["interval_result"]
        if interval_result == "accepted":
            elapsed = item["elapsed"]
            if elapsed is None:
                raise AnalyticsSourceUnavailable(
                    "Historical AP accepted interval is unavailable"
                )
            state["accepted_interval_seconds"] += elapsed
            state["weighted_download"] += download * elapsed
            state["weighted_upload"] += upload * elapsed
        elif interval_result == "source_transition":
            state["source_transition_excluded_interval_count"] += 1

        bucket_index = int(item["bucket_index"])
        bucket = state["buckets"].get(bucket_index)
        if bucket is None:
            state["buckets"][bucket_index] = [1, download, upload]
        else:
            bucket[0] += 1
            bucket[1] += download
            bucket[2] += upload

    if raw_historical_macs != historical_macs:
        raise AnalyticsSourceUnavailable(
            "Historical AP raw population projection is incomplete"
        )

    result_rows: list[Mapping[str, Any]] = []

    for mac in sorted(population_macs):
        state = states[mac]
        accepted_interval_seconds = float(
            state["accepted_interval_seconds"]
        )

        aggregate = {
            "ap_current_name": current_names.get(mac),
            "ap_historical_name": state["historical_name"],
            "ap_sample_opportunity_count": sample_opportunity_count,
            "ap_accepted_sample_count": state["accepted_sample_count"],
            "ap_site_accepted_interval_seconds": (
                site_accepted_interval_seconds
            ),
            "ap_accepted_interval_seconds": accepted_interval_seconds,
            "ap_weighted_download": (
                state["weighted_download"]
                if accepted_interval_seconds > 0
                else None
            ),
            "ap_weighted_upload": (
                state["weighted_upload"]
                if accepted_interval_seconds > 0
                else None
            ),
            "ap_peak_download": state["peak_download"],
            "ap_peak_upload": state["peak_upload"],
            "ap_peak_total": state["peak_total"],
            "ap_no_baseline_count": state["no_baseline"],
            "ap_counter_reset_count": state["counter_reset"],
            "ap_gap_too_large_count": state["gap_too_large"],
            "ap_invalid_elapsed_count": state["invalid_elapsed"],
            "ap_source_unavailable_count": state["source_unavailable"],
            "ap_missing_selected_source_sample_count": (
                sample_opportunity_count
                - state["accepted_sample_count"]
            ),
            "ap_source_transition_excluded_interval_count": state[
                "source_transition_excluded_interval_count"
            ],
        }

        if not bucket_indexes:
            result_rows.append({
                "ap_mac": mac,
                **aggregate,
                "ap_bucket_index": None,
                "ap_bucket_opportunity_count": 0,
                "ap_bucket_accepted_count": 0,
                "ap_bucket_download": None,
                "ap_bucket_upload": None,
            })
            continue

        bucket_state = state["buckets"]
        for bucket_index in bucket_indexes:
            values = bucket_state.get(bucket_index)
            if values is None:
                accepted_count = 0
                bucket_download = None
                bucket_upload = None
            else:
                accepted_count = int(values[0])
                bucket_download = float(values[1]) / accepted_count
                bucket_upload = float(values[2]) / accepted_count

            result_rows.append({
                "ap_mac": mac,
                **aggregate,
                "ap_bucket_index": bucket_index,
                "ap_bucket_opportunity_count": (
                    bucket_opportunity_count.get(bucket_index, 0)
                ),
                "ap_bucket_accepted_count": accepted_count,
                "ap_bucket_download": bucket_download,
                "ap_bucket_upload": bucket_upload,
            })

    return population, tuple(result_rows)
_HISTORICAL_META_SQL = f"""
  WITH {_HISTORICAL_CYCLE_CTES}
  SELECT
    COALESCE(SUM(NOT integrity_ok AND (
      (finished_at>=? AND finished_at<?)
      OR (finished_at IS NULL AND started_at>=? AND started_at<?))),0)
      integrity_failure_count
  FROM validated_cycles
"""


_HISTORICAL_BOUNDARY_BATCH_SIZE = 64

_CLIENT_MAC_SQL = (
    "client_mac GLOB "
    "'[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:"
    "[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]'"
)
_OFFLINE_EVENT_TYPE = "om" + "ada.client_offline"


def _home_activity_visit_sql(ssid_placeholders: str) -> str:
    return f"""
        WITH cohort AS (
          SELECT v.visit_id, v.started_at, v.start_auth_session_id,
                 v.start_auth_run_number, v.start_ssid
          FROM visits AS v INDEXED BY idx_visits_site_started
          WHERE v.site_id=? AND v.started_at>=? AND v.started_at<?
        ), evidence AS (
          SELECT c.visit_id, c.started_at, c.start_ssid,
                 COALESCE(SUM(
                   a.auth_session_id=c.start_auth_session_id
                   AND a.auth_run_number=c.start_auth_run_number
                   AND a.authorized_at=c.started_at
                 ),0) AS opening_match_count,
                 MAX(CASE WHEN
                   a.auth_session_id=c.start_auth_session_id
                   AND a.auth_run_number=c.start_auth_run_number
                   AND a.authorized_at=c.started_at
                 THEN a.portal_ssid END) AS opening_portal_ssid,
                 COUNT(DISTINCT CASE WHEN
                   a.auth_session_id=c.start_auth_session_id
                   AND a.auth_run_number=c.start_auth_run_number
                   AND a.authorized_at=c.started_at
                   AND a.portal_ssid IS NOT NULL
                 THEN a.portal_ssid END) AS opening_ssid_count
          FROM cohort AS c
          LEFT JOIN visit_authorizations AS a
            INDEXED BY idx_visit_auth_visit_time
            ON a.visit_id=c.visit_id
          GROUP BY c.visit_id, c.started_at, c.start_ssid
        ), resolved AS (
          SELECT *, COALESCE(start_ssid, opening_portal_ssid) AS scoped_ssid,
                 CASE
                   WHEN opening_ssid_count>1 THEN 1
                   WHEN start_ssid IS NOT NULL
                    AND opening_portal_ssid IS NOT NULL
                    AND start_ssid<>opening_portal_ssid THEN 1
                   ELSE 0
                 END AS scope_conflict
          FROM evidence
        )
        SELECT
          COALESCE(SUM(scoped_ssid IN ({ssid_placeholders})
                       AND opening_match_count=1 AND scope_conflict=0),0)
            AS verified_visit_count,
          COALESCE(SUM(scoped_ssid IN ({ssid_placeholders})
                       AND opening_match_count!=1 AND scope_conflict=0),0)
            AS integrity_anomaly_count,
          COALESCE(SUM(scoped_ssid IS NULL OR scope_conflict!=0),0)
            AS unproven_scope_count,
          MIN(CASE WHEN scoped_ssid IN ({ssid_placeholders})
                   THEN started_at END) AS earliest_persisted_evidence_at,
          MAX(CASE WHEN scoped_ssid IN ({ssid_placeholders})
                   THEN started_at END) AS latest_persisted_evidence_at
        FROM resolved
    """


def _home_activity_traffic_sql(ssid_placeholders: str) -> str:
    return f"""
        WITH scoped AS (
          SELECT event_id, processing_result, client_mac,
                 controller_event_at, received_at, ssid,
                 reported_connected_seconds, reported_traffic_total_bytes,
                 1 AS controller_in_range
          FROM visit_source_events INDEXED BY idx_visit_events_site_controller
          WHERE site_id=? AND controller_event_at>=? AND controller_event_at<?
            AND ssid IN ({ssid_placeholders})
            AND event_type=?
          UNION ALL
          SELECT event_id, processing_result, client_mac,
                 controller_event_at, received_at, ssid,
                 reported_connected_seconds, reported_traffic_total_bytes,
                 0 AS controller_in_range
          FROM visit_source_events INDEXED BY idx_visit_events_site_controller
          WHERE site_id=? AND controller_event_at IS NULL
            AND received_at>=? AND received_at<?
            AND ssid IN ({ssid_placeholders})
            AND event_type=?
        ), attributable AS (
          SELECT * FROM scoped
        ), eligible AS (
          SELECT * FROM attributable
          WHERE controller_in_range=1
            AND processing_result IN ('closed','unmatched')
            AND {_CLIENT_MAC_SQL}
            AND typeof(reported_connected_seconds)='integer'
            AND reported_connected_seconds>=0
            AND typeof(reported_traffic_total_bytes)='integer'
            AND reported_traffic_total_bytes>=0
        ), fingerprints AS (
          SELECT client_mac, ssid, controller_event_at,
                 reported_connected_seconds, reported_traffic_total_bytes,
                 COUNT(*) AS event_count,
                 MAX(processing_result='unmatched') AS contains_unmatched
          FROM eligible
          GROUP BY client_mac, ssid, controller_event_at,
                   reported_connected_seconds, reported_traffic_total_bytes
        )
        SELECT
          COALESCE((SELECT SUM(reported_traffic_total_bytes)
                    FROM fingerprints),0) AS traffic_bytes,
          (SELECT COUNT(*) FROM eligible) AS eligible_terminal_event_count,
          (SELECT COUNT(*) FROM fingerprints) AS included_fingerprint_count,
          COALESCE((SELECT SUM(processing_result='unmatched')
                    FROM eligible),0) AS unmatched_included_event_count,
          COALESCE((SELECT SUM(processing_result='pending_match')
                    FROM attributable),0) AS pending_event_count,
          COALESCE((SELECT SUM(processing_result='invalid')
                    FROM attributable),0) AS invalid_event_count,
          COALESCE((SELECT SUM(
                    processing_result IN ('closed','unmatched')
                    AND controller_in_range=1
                    AND (reported_traffic_total_bytes IS NULL
                         OR typeof(reported_traffic_total_bytes)!='integer'
                         OR reported_traffic_total_bytes<0))
                    FROM attributable),0) AS missing_traffic_count,
          COALESCE((SELECT SUM(controller_event_at IS NULL)
                    FROM attributable),0) AS missing_controller_time_count,
          COALESCE((SELECT SUM(event_count-1) FROM fingerprints),0)
                    AS semantic_duplicate_count,
          COALESCE((SELECT SUM(
                    processing_result IN ('closed','unmatched')
                    AND controller_in_range=1
                    AND NOT (
                      {_CLIENT_MAC_SQL}
                      AND typeof(reported_connected_seconds)='integer'
                      AND reported_connected_seconds>=0
                      AND typeof(reported_traffic_total_bytes)='integer'
                      AND reported_traffic_total_bytes>=0
                    )) FROM attributable),0)
          - COALESCE((SELECT SUM(
                    processing_result IN ('closed','unmatched')
                    AND controller_in_range=1
                    AND (reported_traffic_total_bytes IS NULL
                         OR typeof(reported_traffic_total_bytes)!='integer'
                         OR reported_traffic_total_bytes<0))
                    FROM attributable),0) AS other_excluded_event_count,
          COALESCE((SELECT SUM(processing_result NOT IN
                    ('pending_match','closed','unmatched','invalid'))
                    FROM attributable),0) AS unsupported_result_count,
          (SELECT MIN(COALESCE(controller_event_at,received_at))
             FROM attributable) AS earliest_persisted_evidence_at,
          (SELECT MAX(COALESCE(controller_event_at,received_at))
             FROM attributable) AS latest_persisted_evidence_at
    """


class AnalyticsSourceError(RuntimeError):
    """A source cannot satisfy the read-only Analytics contract."""


class AnalyticsSourceUnavailable(AnalyticsSourceError):
    """A source database or its schema is unavailable."""


class AnalyticsQueryDeadlineExceeded(AnalyticsSourceError):
    """The hard monotonic query deadline interrupted SQLite."""


class AnalyticsPerformanceBudgetExceeded(AnalyticsSourceError):
    """A cross-source query would exceed the bounded materialization cap."""


@dataclass(frozen=True, slots=True)
class QueryDeadline:
    expires_at: float
    monotonic: Any = time.monotonic

    @classmethod
    def after(
        cls,
        seconds: float,
        *,
        monotonic=time.monotonic,
    ) -> "QueryDeadline":
        return cls(monotonic() + seconds, monotonic)

    def expired(self) -> bool:
        return self.monotonic() >= self.expires_at

    def require_remaining(self) -> None:
        if self.expired():
            raise AnalyticsQueryDeadlineExceeded(
                "Analytics query deadline exceeded"
            )


@dataclass(frozen=True, slots=True)
class ResolvedSnapshotLinks:
    resolved_links: frozenset[tuple[str, str]]
    matched_link_count: int
    watermark: str | None


class AnalyticsSourceGateway:
    """Read persisted facts without owning, migrating, or mutating sources."""

    def __init__(
        self,
        observation_read_service: ObservationReadService,
        visit_read_service: VisitLifecycleReadService,
        registry_read_service: VisitorRegistryReadService,
    ):
        self._observations = observation_read_service
        self._visits = visit_read_service
        self._registry = registry_read_service

    def current_traffic_data(
        self,
        *,
        site_id: str,
        cycle_id: str | None,
        evaluated_at_utc: str,
        after_ap_mac: str | None,
        page_limit: int | None,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        """Read one AP traffic snapshot in a single SQLite transaction."""
        with self._connection("observations", deadline) as connection:
            connection.execute("BEGIN")
            try:
                if cycle_id is None:
                    cycle = self._one(
                        connection,
                        """
                        SELECT * FROM observation_cycles
                        WHERE site_id=? AND kind='ap_dynamic'
                          AND state='completed' AND complete=1
                          AND result='success'
                        ORDER BY started_at DESC, cycle_id DESC
                        LIMIT 1
                        """,
                        (site_id,),
                        deadline,
                    )
                else:
                    cycle = self._one(
                        connection,
                        """
                        SELECT * FROM observation_cycles
                        WHERE site_id=? AND cycle_id=? AND kind='ap_dynamic'
                          AND state='completed' AND complete=1
                          AND result='success'
                        LIMIT 1
                        """,
                        (site_id, cycle_id),
                        deadline,
                    )
                latest = self._one(
                    connection,
                    """
                    SELECT cycle_id, state, result, started_at, finished_at
                    FROM observation_cycles
                    WHERE site_id=? AND kind='ap_dynamic'
                    ORDER BY started_at DESC, cycle_id DESC
                    LIMIT 1
                    """,
                    (site_id,),
                    deadline,
                )
                if cycle is None:
                    return {"cycle": None, "latest": latest, "stats": None,
                            "rows": ()}

                selected_cycle_id = str(cycle["cycle_id"])
                stats = self._one(
                    connection,
                    _CURRENT_TRAFFIC_STATS_SQL,
                    (
                        evaluated_at_utc, selected_cycle_id,
                        site_id, selected_cycle_id,
                    ),
                    deadline,
                )
                parameters: list[Any] = [selected_cycle_id]
                where = "cycle_id=?"
                if after_ap_mac is not None:
                    where += " AND ap_mac>?"
                    parameters.append(after_ap_mac)
                suffix = ""
                if page_limit is not None:
                    suffix = " LIMIT ?"
                    parameters.append(page_limit + 1)
                rows = self._all(
                    connection,
                    f"""
                    SELECT cycle_id, site_id, ap_mac, name,
                           partial, overview_ok, wired_uplink_ok,
                           lan_traffic_ok, radios_ok,
                           wired_observed_at, wired_download_mbps,
                           wired_upload_mbps,
                           wired_download_rate_reason,
                           wired_upload_rate_reason,
                           lan_observed_at, lan_rx_mbps, lan_tx_mbps,
                           lan_rx_rate_reason, lan_tx_rate_reason
                    FROM ap_observations
                    WHERE {where}
                    ORDER BY ap_mac ASC{suffix}
                    """,
                    parameters,
                    deadline,
                )
                deadline.require_remaining()
                return {
                    "cycle": cycle,
                    "latest": latest,
                    "stats": stats,
                    "rows": tuple(rows),
                }
            finally:
                connection.rollback()

    def _historical_boundary_candidates(
        self,
        connection: sqlite3.Connection,
        *,
        site_id: str,
        evaluated_at_utc: str,
        descending: bool,
        cursor: tuple[str, str] | None,
        deadline: QueryDeadline,
    ) -> tuple[sqlite3.Row, ...]:
        direction = "DESC" if descending else "ASC"
        comparison = "<" if descending else ">"
        cursor_clause = ""
        parameters: list[Any] = [
            site_id,
            evaluated_at_utc,
            evaluated_at_utc,
        ]
        if cursor is not None:
            cursor_clause = (
                f"AND (c.finished_at{comparison}? OR "
                f"(c.finished_at=? AND c.cycle_id{comparison}?))"
            )
            parameters.extend((cursor[0], cursor[0], cursor[1]))
        parameters.append(_HISTORICAL_BOUNDARY_BATCH_SIZE)
        return self._all(
            connection,
            f"""
            SELECT c.cycle_id, c.finished_at
            FROM observation_cycles c INDEXED BY idx_cycles_site_kind_started
            WHERE c.site_id=? AND c.kind='ap_dynamic'
              AND c.state='completed' AND c.complete=1 AND c.result='success'
              AND c.started_at<=? AND c.finished_at IS NOT NULL
              AND c.finished_at<=?
              {cursor_clause}
            ORDER BY c.finished_at {direction}, c.cycle_id {direction}
            LIMIT ?
            """,
            tuple(parameters),
            deadline,
        )

    def _historical_validated_boundary_batch(
        self,
        connection: sqlite3.Connection,
        *,
        site_id: str,
        cycle_ids: Sequence[str],
        max_skew_milliseconds: int,
        deadline: QueryDeadline,
    ) -> Mapping[str, Mapping[str, Any]]:
        placeholders = ",".join("?" for _ in cycle_ids)
        rows = self._all(
            connection,
            f"""
            WITH candidate_cycles AS (
              SELECT c.*
              FROM observation_cycles c
              WHERE c.site_id=? AND c.kind='ap_dynamic'
                AND c.cycle_id IN ({placeholders})
            ),
            {_HISTORICAL_VALIDATION_CTES}
            SELECT cycle_id, finished_at, integrity_ok,
                   wired_complete, lan_complete
            FROM validated_cycles
            """,
            (
                site_id,
                *cycle_ids,
                site_id,
                max_skew_milliseconds,
                max_skew_milliseconds,
            ),
            deadline,
        )
        return {str(row["cycle_id"]): dict(row) for row in rows}

    def _historical_source_bounds(
        self,
        connection: sqlite3.Connection,
        *,
        site_id: str,
        evaluated_at_utc: str,
        max_skew_milliseconds: int,
        deadline: QueryDeadline,
    ) -> Mapping[str, str | None]:
        source_watermark: str | None = None
        available_through: str | None = None
        cursor: tuple[str, str] | None = None
        while source_watermark is None or available_through is None:
            candidates = self._historical_boundary_candidates(
                connection,
                site_id=site_id,
                evaluated_at_utc=evaluated_at_utc,
                descending=True,
                cursor=cursor,
                deadline=deadline,
            )
            if not candidates:
                break
            validated = self._historical_validated_boundary_batch(
                connection,
                site_id=site_id,
                cycle_ids=tuple(str(row["cycle_id"]) for row in candidates),
                max_skew_milliseconds=max_skew_milliseconds,
                deadline=deadline,
            )
            for candidate in candidates:
                row = validated[str(candidate["cycle_id"])]
                if not bool(row["integrity_ok"]):
                    continue
                finished_at = str(row["finished_at"])
                if source_watermark is None:
                    source_watermark = finished_at
                if available_through is None and (
                    bool(row["wired_complete"]) or bool(row["lan_complete"])
                ):
                    available_through = finished_at
                if source_watermark is not None and available_through is not None:
                    break
            last = candidates[-1]
            cursor = (str(last["finished_at"]), str(last["cycle_id"]))

        available_from: str | None = None
        cursor = None
        while available_from is None:
            candidates = self._historical_boundary_candidates(
                connection,
                site_id=site_id,
                evaluated_at_utc=evaluated_at_utc,
                descending=False,
                cursor=cursor,
                deadline=deadline,
            )
            if not candidates:
                break
            validated = self._historical_validated_boundary_batch(
                connection,
                site_id=site_id,
                cycle_ids=tuple(str(row["cycle_id"]) for row in candidates),
                max_skew_milliseconds=max_skew_milliseconds,
                deadline=deadline,
            )
            for candidate in candidates:
                row = validated[str(candidate["cycle_id"])]
                if bool(row["integrity_ok"]) and (
                    bool(row["wired_complete"]) or bool(row["lan_complete"])
                ):
                    available_from = str(row["finished_at"])
                    break
            last = candidates[-1]
            cursor = (str(last["finished_at"]), str(last["cycle_id"]))

        return {
            "available_from_utc": available_from,
            "available_through_utc": available_through,
            "source_watermark_utc": source_watermark,
        }

    def historical_traffic_data(
        self,
        *,
        site_id: str,
        from_utc: str,
        to_utc: str,
        evaluated_at_utc: str,
        bucket_seconds: int,
        gap_threshold_seconds: float,
        max_site_sample_source_skew_seconds: int,
        deadline: QueryDeadline,
        include_period_statistics: bool = False,
        include_peak_load: bool = False,
        include_ap_traffic: bool = False,
        current_cycle_id: str | None = None,
    ) -> Mapping[str, Any]:
        """Return bounded historical AP-rate aggregates from one read snapshot."""
        max_skew_milliseconds = max_site_sample_source_skew_seconds * 1000
        cycle_parameters = (
            site_id, from_utc, to_utc, from_utc, to_utc,
            site_id, from_utc, from_utc, to_utc, site_id,
            max_skew_milliseconds, max_skew_milliseconds,
        )
        with self._connection("observations", deadline) as connection:
            connection.execute("BEGIN")
            try:
                if include_period_statistics or include_ap_traffic:
                    if include_ap_traffic:
                        combined_sql = _HISTORICAL_AP_LEAN_COMBINED_SQL
                        combined_parameters = (
                            *cycle_parameters,
                            from_utc, to_utc, from_utc, to_utc,
                            from_utc, from_utc,
                            bucket_seconds,
                            from_utc,
                            to_utc,
                            gap_threshold_seconds,
                            gap_threshold_seconds,
                        )
                    else:
                        combined_sql = (
                            _HISTORICAL_PEAK_COMBINED_SQL
                            if include_peak_load
                            else _HISTORICAL_COMBINED_SQL
                        )
                        combined_parameters = (
                            *cycle_parameters,
                            from_utc, to_utc, from_utc, to_utc,
                            from_utc, from_utc,
                            bucket_seconds,
                            from_utc,
                            to_utc,
                            gap_threshold_seconds,
                            gap_threshold_seconds,
                        )

                    combined_rows = self._all(
                        connection,
                        combined_sql,
                        combined_parameters,
                        deadline,
                    )
                    if not combined_rows:
                        raise AnalyticsSourceUnavailable(
                            "Historical traffic combined projection is unavailable"
                        )
                    first = combined_rows[0]
                    if (
                        (include_peak_load or include_ap_traffic)
                        and int(first["projection_kind"]) != 0
                    ):
                        raise AnalyticsSourceUnavailable(
                            "Historical traffic combined projection is unavailable"
                        )
                    meta_values = {
                        "integrity_failure_count": first[
                            "integrity_failure_count"
                        ]
                    }
                    combined_statistics = {
                        field: first[field]
                        for field in _HISTORICAL_STATISTICS_RESULT_FIELDS
                    }
                    auxiliary_fields = {
                        "integrity_failure_count",
                        *_HISTORICAL_STATISTICS_RESULT_FIELDS,
                    }

                    projected = include_peak_load or include_ap_traffic
                    if projected:
                        auxiliary_fields.update((
                            "projection_kind",
                            "projection_order",
                            *_HISTORICAL_PEAK_SAMPLE_FIELDS,
                        ))
                    if include_ap_traffic:
                        auxiliary_fields.update((
                            "ap_support_cycle_id",
                            "ap_support_bucket_index",
                        ))

                    if include_peak_load:
                        peak_samples = tuple(
                            {
                                "finished_at": row[
                                    "peak_sample_finished_at"
                                ],
                                "selected_source": row[
                                    "peak_sample_selected_source"
                                ],
                                "download": row["peak_sample_download"],
                                "upload": row["peak_sample_upload"],
                                "previous_at": row[
                                    "peak_sample_previous_at"
                                ],
                                "interval_result": row[
                                    "peak_sample_interval_result"
                                ],
                            }
                            for row in combined_rows
                            if int(row["projection_kind"]) == 1
                        )
                    else:
                        peak_samples = None

                    bucket_source_rows = (
                        (
                            row for row in combined_rows
                            if int(row["projection_kind"]) == 0
                        )
                        if projected
                        else iter(combined_rows)
                    )
                    rows = tuple(
                        {
                            key: value
                            for key, value in row.items()
                            if key not in auxiliary_fields
                        }
                        for source_row in bucket_source_rows
                        for row in (dict(source_row),)
                        if row["bucket_index"] is not None
                    )
                    statistics = (
                        combined_statistics
                        if include_period_statistics else None
                    )

                    if include_ap_traffic:
                        support_rows = tuple(
                            row for row in combined_rows
                            if int(row["projection_kind"]) in (1, 2)
                        )
                        support_cycle_ids = {
                            str(row["ap_support_cycle_id"])
                            for row in support_rows
                        }
                        identity_parameters = (
                            site_id, from_utc, to_utc, from_utc, to_utc,
                            site_id, from_utc, from_utc, to_utc, site_id,
                        )
                        identity_rows = (
                            self._all(
                                connection,
                                _HISTORICAL_AP_IDENTITY_SQL,
                                identity_parameters,
                                deadline,
                            )
                            if support_cycle_ids else ()
                        )
                        current_identity_rows = (
                            ()
                            if current_cycle_id is None
                            else self._all(
                                connection,
                                _HISTORICAL_AP_CURRENT_IDENTITY_SQL,
                                (current_cycle_id, site_id),
                                deadline,
                            )
                        )
                        historical_macs = {
                            str(row["ap_mac"])
                            for row in identity_rows
                            if str(row["cycle_id"]) in support_cycle_ids
                        }
                        current_macs = {
                            str(row["ap_mac"])
                            for row in current_identity_rows
                        }
                        population_count = len(
                            historical_macs | current_macs
                        )
                        raw_rows = (
                            self._all(
                                connection,
                                _HISTORICAL_AP_RAW_SQL,
                                identity_parameters,
                                deadline,
                            )
                            if (
                                population_count <= 12
                                and bool(historical_macs)
                            )
                            else ()
                        )
                        population, ap_rows = (
                            _historical_ap_population_and_rows(
                                support_rows=support_rows,
                                identity_rows=identity_rows,
                                raw_rows=raw_rows,
                                current_identity_rows=current_identity_rows,
                            )
                        )
                    else:
                        population = None
                        ap_rows = None

                    meta_values.update(self._historical_source_bounds(
                        connection,
                        site_id=site_id,
                        evaluated_at_utc=evaluated_at_utc,
                        max_skew_milliseconds=max_skew_milliseconds,
                        deadline=deadline,
                    ))
                else:
                    meta = self._one(
                        connection,
                        _HISTORICAL_META_SQL,
                        (
                            *cycle_parameters,
                            from_utc, to_utc, from_utc, to_utc,
                        ),
                        deadline,
                    )
                    meta_values = dict(meta or {})
                    meta_values.update(self._historical_source_bounds(
                        connection,
                        site_id=site_id,
                        evaluated_at_utc=evaluated_at_utc,
                        max_skew_milliseconds=max_skew_milliseconds,
                        deadline=deadline,
                    ))
                    rows = self._all(
                        connection,
                        _HISTORICAL_BUCKET_SQL,
                        (
                            *cycle_parameters,
                            from_utc, from_utc,
                            bucket_seconds,
                            from_utc,
                            to_utc,
                            gap_threshold_seconds,
                        ),
                        deadline,
                    )
                    statistics = None
                    peak_samples = None
                    population = None
                    ap_rows = None

                attempts = self._one(
                    connection,
                    """
                    SELECT
                      COALESCE(SUM(state='completed' AND result='partial'
                        AND finished_at<=?),0)
                        partial_cycle_count,
                      COALESCE(SUM(state='completed' AND result='failed'
                        AND finished_at<=?),0)
                        failed_cycle_count,
                      COALESCE(SUM(state='completed' AND result='shutdown'
                        AND finished_at<=?),0)
                        shutdown_cycle_count,
                      COALESCE(SUM(state='abandoned' AND abandoned_at<=?),0)
                        abandoned_cycle_count,
                      COALESCE(SUM(
                        state='running'
                        OR (state='completed' AND finished_at>?)
                        OR (state='abandoned' AND abandoned_at>?)
                      ),0) running_cycle_count
                    FROM observation_cycles INDEXED BY idx_cycles_site_kind_started
                    WHERE site_id=? AND kind='ap_dynamic'
                      AND started_at>=? AND started_at<? AND started_at<=?
                    """,
                    (
                        evaluated_at_utc, evaluated_at_utc,
                        evaluated_at_utc, evaluated_at_utc,
                        evaluated_at_utc, evaluated_at_utc,
                        site_id, from_utc, to_utc, evaluated_at_utc,
                    ),
                    deadline,
                )
                deadline.require_remaining()
                return {
                    "meta": meta_values,
                    "buckets": tuple(dict(row) for row in rows),
                    "attempts": dict(attempts or {}),
                    "period_statistics": (
                        dict(statistics) if statistics is not None else None
                    ),
                    "peak_samples": peak_samples,
                    "ap_population": population,
                    "ap_rows": ap_rows,
                }
            finally:
                connection.rollback()

    def explain_historical_traffic(
        self,
        *,
        site_id: str,
        from_utc: str,
        to_utc: str,
        evaluated_at_utc: str,
        bucket_seconds: int,
        gap_threshold_seconds: float,
        max_site_sample_source_skew_seconds: int,
        deadline: QueryDeadline,
    ) -> tuple[str, ...]:
        """Expose safe plan text for deterministic capacity/index evidence."""
        max_skew_milliseconds = max_site_sample_source_skew_seconds * 1000
        parameters = (
            site_id, from_utc, to_utc, from_utc, to_utc,
            site_id, from_utc, from_utc, to_utc, site_id,
            max_skew_milliseconds, max_skew_milliseconds,
            from_utc, from_utc, bucket_seconds, from_utc, to_utc,
            gap_threshold_seconds,
        )
        with self._connection("observations", deadline) as connection:
            rows = self._all(
                connection,
                "EXPLAIN QUERY PLAN " + _HISTORICAL_BUCKET_SQL,
                parameters,
                deadline,
            )
        return tuple(str(row[3]) for row in rows)

    def explain_historical_traffic_statistics(
        self,
        *,
        site_id: str,
        from_utc: str,
        to_utc: str,
        evaluated_at_utc: str,
        bucket_seconds: int,
        gap_threshold_seconds: float,
        max_site_sample_source_skew_seconds: int,
        deadline: QueryDeadline,
    ) -> tuple[str, ...]:
        """Expose the bounded Statistics projection plan."""
        max_skew_milliseconds = max_site_sample_source_skew_seconds * 1000
        parameters = (
            site_id, from_utc, to_utc, from_utc, to_utc,
            site_id, from_utc, from_utc, to_utc, site_id,
            max_skew_milliseconds, max_skew_milliseconds,
            from_utc, from_utc, bucket_seconds, from_utc, to_utc,
            gap_threshold_seconds,
        )
        with self._connection("observations", deadline) as connection:
            rows = self._all(
                connection,
                "EXPLAIN QUERY PLAN " + _HISTORICAL_STATISTICS_SQL,
                parameters,
                deadline,
            )
        return tuple(str(row[3]) for row in rows)

    def explain_historical_traffic_combined(
        self,
        *,
        site_id: str,
        from_utc: str,
        to_utc: str,
        evaluated_at_utc: str,
        bucket_seconds: int,
        gap_threshold_seconds: float,
        max_site_sample_source_skew_seconds: int,
        deadline: QueryDeadline,
        include_peak_load: bool = False,
    ) -> tuple[str, ...]:
        """Expose the single-pass combined History and Statistics plan."""
        max_skew_milliseconds = max_site_sample_source_skew_seconds * 1000
        parameters = (
            site_id, from_utc, to_utc, from_utc, to_utc,
            site_id, from_utc, from_utc, to_utc, site_id,
            max_skew_milliseconds, max_skew_milliseconds,
            from_utc, to_utc, from_utc, to_utc,
            from_utc, from_utc, bucket_seconds, from_utc, to_utc,
            gap_threshold_seconds, gap_threshold_seconds,
        )
        with self._connection("observations", deadline) as connection:
            rows = self._all(
                connection,
                "EXPLAIN QUERY PLAN " + (
                    _HISTORICAL_PEAK_COMBINED_SQL
                    if include_peak_load
                    else _HISTORICAL_COMBINED_SQL
                ),
                parameters,
                deadline,
            )
        return tuple(str(row[3]) for row in rows)

    def home_activity_data(
        self,
        *,
        site_id: str,
        guest_ssids: Sequence[str],
        from_utc: str,
        to_utc: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        """Return bounded Activity aggregates in one read-only snapshot."""
        if not guest_ssids:
            raise AnalyticsSourceUnavailable("Activity guest scope is empty")
        placeholders = ",".join("?" for _ in guest_ssids)
        visit_sql = _home_activity_visit_sql(placeholders)
        traffic_sql = _home_activity_traffic_sql(placeholders)
        visit_parameters = (
            site_id, from_utc, to_utc,
            *tuple(guest_ssids), *tuple(guest_ssids),
            *tuple(guest_ssids), *tuple(guest_ssids),
        )
        traffic_parameters = (
            site_id, from_utc, to_utc, *tuple(guest_ssids),
            _OFFLINE_EVENT_TYPE,
            site_id, from_utc, to_utc, *tuple(guest_ssids),
            _OFFLINE_EVENT_TYPE,
        )
        with self._connection("visits", deadline) as connection:
            connection.execute("BEGIN")
            try:
                visits = self._one(
                    connection, visit_sql, visit_parameters, deadline
                )
                traffic = self._one(
                    connection, traffic_sql, traffic_parameters, deadline
                )
                reader = self._one(
                    connection,
                    "SELECT MAX(updated_at) AS watermark "
                    "FROM visit_reader_state",
                    (),
                    deadline,
                )
                deadline.require_remaining()
            finally:
                connection.rollback()
        return {
            "visits": dict(visits) if visits is not None else {},
            "traffic": dict(traffic) if traffic is not None else {},
            "reader_watermark_at": (
                None if reader is None else reader["watermark"]
            ),
        }

    def explain_home_activity(
        self,
        *,
        site_id: str,
        guest_ssids: Sequence[str],
        from_utc: str,
        to_utc: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, tuple[str, ...]]:
        """Return plans used by the deterministic Activity capacity gate."""
        if not guest_ssids:
            raise AnalyticsSourceUnavailable("Activity guest scope is empty")
        placeholders = ",".join("?" for _ in guest_ssids)
        visit_parameters = (
            site_id, from_utc, to_utc,
            *tuple(guest_ssids), *tuple(guest_ssids),
            *tuple(guest_ssids), *tuple(guest_ssids),
        )
        traffic_parameters = (
            site_id, from_utc, to_utc, *tuple(guest_ssids),
            _OFFLINE_EVENT_TYPE,
            site_id, from_utc, to_utc, *tuple(guest_ssids),
            _OFFLINE_EVENT_TYPE,
        )
        with self._connection("visits", deadline) as connection:
            visits = self._all(
                connection,
                "EXPLAIN QUERY PLAN " + _home_activity_visit_sql(placeholders),
                visit_parameters,
                deadline,
            )
            traffic = self._all(
                connection,
                "EXPLAIN QUERY PLAN " + _home_activity_traffic_sql(placeholders),
                traffic_parameters,
                deadline,
            )
        return {
            "authorized_visits": tuple(str(row[3]) for row in visits),
            "traffic": tuple(str(row[3]) for row in traffic),
        }

    def cycle_quality(
        self,
        *,
        site_id: str,
        kind: str,
        from_utc: str,
        to_utc: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        if kind not in {"client", "ap_dynamic", "ap_config"}:
            raise ValueError("unsupported observation cycle kind")
        with self._connection("observations", deadline) as connection:
            row = self._one(
                connection,
                """
                SELECT
                    COUNT(*) AS row_count,
                    COALESCE(SUM(state='running'), 0) AS running,
                    COALESCE(SUM(state='completed'), 0) AS completed,
                    COALESCE(SUM(state='abandoned'), 0) AS abandoned,
                    COALESCE(SUM(
                        state='completed' AND complete=1
                    ), 0) AS completed_complete,
                    COALESCE(SUM(
                        state='completed' AND complete=0
                    ), 0) AS completed_incomplete,
                    COALESCE(SUM(
                        state='completed' AND result='success'
                    ), 0) AS success,
                    COALESCE(SUM(
                        state='completed' AND result='partial'
                    ), 0) AS partial,
                    COALESCE(SUM(
                        state='completed' AND result='failed'
                    ), 0) AS failed,
                    COALESCE(SUM(
                        state='completed' AND result='shutdown'
                    ), 0) AS shutdown,
                    MAX(CASE
                        WHEN state='completed'
                         AND complete=1
                         AND result='success'
                        THEN finished_at
                    END) AS latest_accepted_at
                FROM observation_cycles
                WHERE site_id=? AND kind=?
                  AND started_at>=? AND started_at<?
                """,
                (site_id, kind, from_utc, to_utc),
                deadline,
            )
        return dict(row)

    def field_completeness(
        self,
        *,
        site_id: str,
        source: str,
        from_utc: str,
        to_utc: str,
        fields: Sequence[str],
        quality_mode: str,
        deadline: QueryDeadline,
    ) -> tuple[Mapping[str, Any], ...]:
        allowed = FIELD_ALLOWLIST.get(source)
        selected = tuple(dict.fromkeys(fields))
        if allowed is None or not selected or any(
            field not in allowed for field in selected
        ):
            raise ValueError("fields are outside the approved allowlist")
        spec = _field_source_spec(source)
        strict = spec["strict"]
        accepted = strict if quality_mode == "strict_complete" else "1"
        projections = ",\n".join(
            f"COALESCE(SUM(CASE WHEN ({accepted}) "
            f"AND o.{field} IS NOT NULL THEN 1 ELSE 0 END), 0) "
            f"AS non_null_{field}"
            for field in selected
        )
        with self._connection("observations", deadline) as connection:
            row = self._one(
                connection,
                f"""
                SELECT
                    COUNT(*) AS rows_examined,
                    COALESCE(SUM(CASE WHEN ({accepted}) THEN 1 ELSE 0 END), 0)
                        AS rows_accepted,
                    COUNT(*) - COALESCE(SUM(
                        CASE WHEN ({accepted}) THEN 1 ELSE 0 END
                    ), 0) AS rows_rejected,
                    COUNT(DISTINCT CASE
                        WHEN c.state='completed'
                         AND (c.complete<>1 OR c.result<>'success')
                        THEN c.cycle_id END
                    ) AS partial_cycle_count,
                    {projections},
                    MAX(CASE WHEN ({accepted}) THEN {spec["time"]} END)
                        AS latest_accepted_at
                FROM {spec["from"]}
                WHERE o.site_id=? AND {spec["time"]}>=? AND {spec["time"]}<?
                """,
                (site_id, from_utc, to_utc),
                deadline,
            )
        common = dict(row)
        return tuple({
            "field": field,
            "row_count": int(common["rows_accepted"]),
            "non_null_count": int(common[f"non_null_{field}"]),
            "rows_examined": int(common["rows_examined"]),
            "rows_rejected": int(common["rows_rejected"]),
            "partial_cycle_count": int(common["partial_cycle_count"]),
            "latest_accepted_at": common["latest_accepted_at"],
        } for field in selected)

    def visit_population(
        self,
        *,
        site_id: str,
        from_utc: str,
        to_utc: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        where = _visit_overlap_where()
        with self._connection("visits", deadline) as connection:
            row = self._one(
                connection,
                f"""
                SELECT
                    COUNT(*) AS total,
                    COALESCE(SUM(v.device_id IS NOT NULL), 0) AS linked,
                    COALESCE(SUM(v.initial_snapshot_id IS NOT NULL), 0)
                        AS snapshot_linked,
                    COALESCE(SUM(v.status='open'), 0) AS open_count,
                    COALESCE(SUM(v.status='closed'), 0) AS closed_count,
                    COALESCE(SUM(EXISTS(
                        SELECT 1 FROM visit_authorizations a
                        WHERE a.visit_id=v.visit_id
                    )), 0) AS authorization_attached,
                    MAX(COALESCE(v.closed_at, v.started_at)) AS watermark
                FROM visits v
                WHERE {where}
                """,
                (site_id, from_utc, to_utc),
                deadline,
            )
        return dict(row)

    def initial_snapshot_links(
        self,
        *,
        site_id: str,
        from_utc: str,
        to_utc: str,
        deadline: QueryDeadline,
    ) -> tuple[tuple[str, str], ...]:
        with self._connection("visits", deadline) as connection:
            rows = self._all(
                connection,
                f"""
                SELECT initial_snapshot_id, client_mac
                FROM visits v
                WHERE {_visit_overlap_where()}
                  AND initial_snapshot_id IS NOT NULL
                ORDER BY started_at, visit_id
                LIMIT ?
                """,
                (
                    site_id,
                    from_utc,
                    to_utc,
                    MAX_CROSS_SOURCE_IDENTIFIERS + 1,
                ),
                deadline,
            )
        if len(rows) > MAX_CROSS_SOURCE_IDENTIFIERS:
            raise AnalyticsPerformanceBudgetExceeded(
                "snapshot link population exceeds materialization budget"
            )
        return tuple(
            (str(row["initial_snapshot_id"]), str(row["client_mac"]))
            for row in rows
        )

    def resolved_snapshot_links(
        self,
        *,
        site_id: str,
        links: Sequence[tuple[str, str]],
        deadline: QueryDeadline,
    ) -> ResolvedSnapshotLinks:
        if not links:
            return ResolvedSnapshotLinks(frozenset(), 0, None)
        resolved: set[tuple[str, str]] = set()
        expected = frozenset(links)
        identifiers = tuple(dict.fromkeys(link[0] for link in links))
        watermark: str | None = None
        with self._connection("registry", deadline) as connection:
            for offset in range(0, len(identifiers), _SNAPSHOT_BATCH_SIZE):
                deadline.require_remaining()
                batch = identifiers[offset:offset + _SNAPSHOT_BATCH_SIZE]
                placeholders = ",".join("?" for _ in batch)
                rows = self._all(
                    connection,
                    f"""
                    SELECT snapshot_id, requested_mac, captured_at
                    FROM device_snapshots
                    WHERE site_id=? AND snapshot_id IN ({placeholders})
                    """,
                    (site_id, *batch),
                    deadline,
                )
                for row in rows:
                    captured_at = str(row["captured_at"])
                    watermark = max(watermark or captured_at, captured_at)
                    link = (
                        str(row["snapshot_id"]),
                        str(row["requested_mac"]),
                    )
                    if link in expected:
                        resolved.add(link)
        return ResolvedSnapshotLinks(
            resolved_links=frozenset(resolved),
            matched_link_count=sum(1 for link in links if link in resolved),
            watermark=watermark,
        )

    def visit_quality_page(
        self,
        *,
        site_id: str,
        from_utc: str,
        to_utc: str,
        status: str | None,
        cursor: tuple[str, str] | None,
        limit: int,
        deadline: QueryDeadline,
    ) -> tuple[Mapping[str, Any], ...]:
        clauses = [_visit_overlap_where()]
        parameters: list[Any] = [site_id, from_utc, to_utc]
        if status is not None:
            clauses.append("v.status=?")
            parameters.append(status)
        if cursor is not None:
            clauses.append(
                "(v.started_at<? OR "
                "(v.started_at=? AND v.visit_id<?))"
            )
            parameters.extend((cursor[0], cursor[0], cursor[1]))
        parameters.append(limit)
        with self._connection("visits", deadline) as connection:
            rows = self._all(
                connection,
                f"""
                SELECT
                    v.visit_id, v.site_id, v.client_mac, v.device_id,
                    v.initial_snapshot_id, v.started_at, v.closed_at,
                    v.status, v.duration_seconds,
                    COUNT(a.row_id) AS authorization_count
                FROM visits v
                LEFT JOIN visit_authorizations a ON a.visit_id=v.visit_id
                WHERE {' AND '.join(clauses)}
                GROUP BY v.visit_id
                ORDER BY v.started_at DESC, v.visit_id DESC
                LIMIT ?
                """,
                tuple(parameters),
                deadline,
            )
        return tuple(dict(row) for row in rows)

    def visit_by_id(
        self,
        *,
        site_id: str,
        visit_id: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any] | None:
        with self._connection("visits", deadline) as connection:
            row = self._one(
                connection,
                """
                SELECT v.*, COUNT(a.row_id) AS authorization_count
                FROM visits v
                LEFT JOIN visit_authorizations a ON a.visit_id=v.visit_id
                WHERE v.site_id=? AND v.visit_id=?
                GROUP BY v.visit_id
                """,
                (site_id, visit_id),
                deadline,
            )
        return None if row is None else dict(row)

    def snapshot_by_id(
        self,
        *,
        site_id: str,
        snapshot_id: str,
        requested_mac: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any] | None:
        with self._connection("registry", deadline) as connection:
            row = self._one(
                connection,
                """
                SELECT snapshot_id, device_id, auth_session_id, site_id,
                       requested_mac, authorized_at, captured_at,
                       device_type, ssid, ap_mac, radio_id, channel,
                       rssi, snr, traffic_down, traffic_up
                FROM device_snapshots
                WHERE site_id=? AND snapshot_id=? AND requested_mac=?
                LIMIT 1
                """,
                (site_id, snapshot_id, requested_mac),
                deadline,
            )
        return None if row is None else dict(row)

    def registry_device(
        self,
        *,
        device_id: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any] | None:
        with self._connection("registry", deadline) as connection:
            row = self._one(
                connection,
                """
                SELECT device_id, mac, first_seen_at, last_seen_at,
                       last_site_id, last_ip, last_ssid, last_ap_name,
                       last_ap_mac, last_rssi, last_snr, snapshot_count
                FROM visitor_devices WHERE device_id=? LIMIT 1
                """,
                (device_id,),
                deadline,
            )
        return None if row is None else dict(row)

    def observation_coverage(
        self,
        *,
        site_id: str,
        client_mac: str,
        from_utc: str,
        to_utc: str,
        gap_threshold_seconds: float,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        with self._connection("observations", deadline) as connection:
            row = self._one(
                connection,
                """
                WITH accepted AS (
                    SELECT o.observed_at, o.row_id
                    FROM client_observations o
                    JOIN observation_cycles c ON c.cycle_id=o.cycle_id
                    WHERE o.site_id=? AND o.client_mac=?
                      AND o.observed_at>=? AND o.observed_at<?
                      AND c.state='completed' AND c.complete=1
                      AND c.result='success'
                      AND o.source_inventory_complete=1
                ),
                ordered AS (
                    SELECT observed_at, row_id,
                           LAG(observed_at) OVER (
                               ORDER BY observed_at, row_id
                           ) AS previous_at
                    FROM accepted
                ),
                gaps AS (
                    SELECT observed_at,
                           CASE WHEN previous_at IS NULL THEN NULL ELSE
                             (julianday(observed_at)-julianday(previous_at))
                             * 86400.0
                           END AS gap_seconds
                    FROM ordered
                )
                SELECT COUNT(*) AS sample_count,
                       MIN(observed_at) AS first_observed_at,
                       MAX(observed_at) AS last_observed_at,
                       MAX(gap_seconds) AS max_gap_seconds,
                       COALESCE(SUM(gap_seconds>?), 0)
                           AS gap_count_over_threshold
                FROM gaps
                """,
                (
                    site_id,
                    client_mac,
                    from_utc,
                    to_utc,
                    gap_threshold_seconds,
                ),
                deadline,
            )
        return dict(row)

    def source_event_quality(
        self,
        *,
        site_id: str,
        from_utc: str,
        to_utc: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Mapping[str, int]]:
        with self._connection("visits", deadline) as connection:
            rows = self._all(
                connection,
                """
                SELECT processing_result, reason, COUNT(*) AS count
                FROM visit_source_events
                WHERE site_id=? AND processed_at>=? AND processed_at<?
                GROUP BY processing_result, reason
                """,
                (site_id, from_utc, to_utc),
                deadline,
            )
        by_result: dict[str, int] = {}
        by_reason: dict[str, int] = {}
        for row in rows:
            result = str(row["processing_result"])
            count = int(row["count"])
            by_result[result] = by_result.get(result, 0) + count
            if row["reason"] is not None:
                reason = str(row["reason"])
                by_reason[reason] = by_reason.get(reason, 0) + count
        return {
            "by_processing_result": by_result,
            "by_reason": by_reason,
        }

    def source_event_watermark(
        self, *, site_id: str, from_utc: str, to_utc: str,
        deadline: QueryDeadline,
    ) -> str | None:
        with self._connection("visits", deadline) as connection:
            row = self._one(connection, """
              SELECT MAX(processed_at) watermark FROM visit_source_events
              WHERE site_id=? AND processed_at>=? AND processed_at<?
            """, (site_id, from_utc, to_utc), deadline)
        return None if row is None else row["watermark"]

    def observation_watermarks(
        self,
        *,
        site_id: str,
        from_utc: str,
        to_utc: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, str | None]:
        with self._connection("observations", deadline) as connection:
            row = self._one(
                connection,
                """
                SELECT
                  (SELECT MAX(o.observed_at)
                   FROM client_observations o
                   JOIN observation_cycles c ON c.cycle_id=o.cycle_id
                   WHERE o.site_id=? AND o.observed_at>=? AND o.observed_at<?
                     AND c.state='completed' AND c.complete=1
                     AND c.result='success'
                     AND o.source_inventory_complete=1) AS client,
                  (SELECT MAX(o.observed_at)
                   FROM ap_observations o
                   JOIN observation_cycles c ON c.cycle_id=o.cycle_id
                   WHERE o.site_id=? AND o.observed_at>=? AND o.observed_at<?
                     AND c.state='completed' AND c.complete=1
                     AND c.result='success' AND o.partial=0) AS ap,
                  (SELECT MAX(r.radio_observed_at)
                   FROM ap_radio_observations r
                   JOIN ap_observations o
                     ON o.row_id=r.ap_observation_row_id
                   JOIN observation_cycles c ON c.cycle_id=r.cycle_id
                   WHERE r.site_id=? AND r.radio_observed_at>=?
                     AND r.radio_observed_at<?
                     AND c.state='completed' AND c.complete=1
                     AND c.result='success' AND o.partial=0
                     AND o.radios_ok=1) AS radio
                """,
                (
                    site_id, from_utc, to_utc,
                    site_id, from_utc, to_utc,
                    site_id, from_utc, to_utc,
                ),
                deadline,
            )
        return dict(row)

    def registry_watermark(
        self,
        *,
        site_id: str,
        from_utc: str,
        to_utc: str,
        deadline: QueryDeadline,
    ) -> str | None:
        with self._connection("registry", deadline) as connection:
            row = self._one(
                connection,
                """
                SELECT MAX(captured_at) AS watermark
                FROM device_snapshots
                WHERE site_id=? AND captured_at>=? AND captured_at<?
                """,
                (site_id, from_utc, to_utc),
                deadline,
            )
        return None if row is None else row["watermark"]

    def visit_cohort_summary(
        self, *, site_id: str, from_utc: str, to_utc: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        with self._connection("visits", deadline) as connection:
            row = self._one(connection, """
                SELECT COUNT(*) total_visit_count,
                       COALESCE(SUM(status='open'),0) open_visit_count,
                       COALESCE(SUM(status='closed'),0) closed_visit_count,
                       MAX(started_at) watermark
                FROM visits
                WHERE site_id=? AND started_at>=? AND started_at<?
            """, (site_id, from_utc, to_utc), deadline)
        return dict(row)

    def visit_start_timestamps(
        self, *, site_id: str, from_utc: str, to_utc: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        with self._connection("visits", deadline) as connection:
            rows = self._all(connection, """
                SELECT started_at
                FROM visits
                WHERE site_id=? AND started_at>=? AND started_at<?
                ORDER BY started_at, visit_id LIMIT ?
            """, (site_id, from_utc, to_utc,
                    MAX_CROSS_SOURCE_IDENTIFIERS + 1), deadline)
        if len(rows) > MAX_CROSS_SOURCE_IDENTIFIERS:
            raise AnalyticsPerformanceBudgetExceeded(
                "Visit time-series cohort exceeds materialization budget")
        return {"rows": tuple(dict(row) for row in rows),
                "watermark": (None if not rows
                              else str(rows[-1]["started_at"]))}

    def visit_device_summary(
        self, *, site_id: str, from_utc: str, to_utc: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        with self._connection("visits", deadline) as connection:
            row = self._one(connection, """
                WITH cohort AS (
                  SELECT device_id, started_at FROM visits
                  WHERE site_id=? AND started_at>=? AND started_at<?
                ), grouped AS (
                  SELECT device_id, COUNT(*) visit_count FROM cohort
                  WHERE device_id IS NOT NULL GROUP BY device_id
                )
                SELECT (SELECT COUNT(DISTINCT device_id) FROM cohort
                        WHERE device_id IS NOT NULL) unique_linked_devices,
                       (SELECT COUNT(*) FROM cohort
                        WHERE device_id IS NOT NULL) linked_visit_count,
                       (SELECT COUNT(*) FROM cohort
                        WHERE device_id IS NULL) unlinked_visit_count,
                       (SELECT COUNT(*) FROM grouped
                        WHERE visit_count>=2) repeat_device_count,
                       (SELECT COUNT(*) FROM cohort) rows_examined,
                       (SELECT MAX(started_at) FROM cohort) watermark
            """, (site_id, from_utc, to_utc), deadline)
        return dict(row)

    def visit_new_to_site_summary(
        self, *, site_id: str, from_utc: str, to_utc: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        with self._connection("visits", deadline) as connection:
            row = self._one(connection, """
                WITH firsts AS (
                  SELECT device_id, MIN(started_at) first_started_at
                  FROM visits WHERE site_id=? AND device_id IS NOT NULL
                  GROUP BY device_id
                ), cohort_devices AS (
                  SELECT DISTINCT device_id FROM visits
                  WHERE site_id=? AND started_at>=? AND started_at<?
                    AND device_id IS NOT NULL
                ), cohort AS (
                  SELECT device_id, started_at FROM visits
                  WHERE site_id=? AND started_at>=? AND started_at<?
                )
                SELECT COUNT(cd.device_id) unique_linked_devices_in_window,
                       COALESCE(SUM(f.first_started_at>=?
                                AND f.first_started_at<?),0)
                           new_to_site_device_count,
                       COALESCE(SUM(f.first_started_at<?),0)
                           known_before_window_device_count,
                       (SELECT COUNT(*) FROM cohort WHERE device_id IS NULL)
                           unlinked_visit_count,
                       (SELECT COUNT(*) FROM cohort) rows_examined,
                       (SELECT MAX(started_at) FROM cohort) watermark
                FROM cohort_devices cd JOIN firsts f USING(device_id)
            """, (site_id, site_id, from_utc, to_utc,
                    site_id, from_utc, to_utc,
                    from_utc, to_utc, from_utc), deadline)
        return dict(row)

    def visit_duration_distribution(
        self, *, site_id: str, from_utc: str, to_utc: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        base = """
          SELECT rowid row_id, NULL cycle_id, NULL ap_mac,
                 started_at observed_at, duration_seconds value,
                 CASE WHEN status='closed' THEN 1 ELSE 0 END accepted,
                 NULL reason
          FROM visits WHERE site_id=? AND started_at>=? AND started_at<?
        """
        with self._connection("visits", deadline) as connection:
            result = dict(self._distribution_from_base(
                connection, base_sql=base,
                parameters=(site_id, from_utc, to_utc), threshold=None,
                deadline=deadline))
            excluded = self._one(connection, """
              SELECT COALESCE(SUM(status='open'),0) excluded_open_count,
                     COALESCE(SUM(status='closed' AND duration_seconds IS NULL),0)
                       excluded_missing_duration_count
              FROM visits WHERE site_id=? AND started_at>=? AND started_at<?
            """, (site_id, from_utc, to_utc), deadline)
        result.update(dict(excluded))
        return result

    def visit_authorization_distribution(
        self, *, site_id: str, from_utc: str, to_utc: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        base = """
          SELECT v.rowid row_id, NULL cycle_id, NULL ap_mac,
                 v.started_at observed_at, COUNT(a.row_id) value,
                 1 accepted, NULL reason
          FROM visits v LEFT JOIN visit_authorizations a
            ON a.visit_id=v.visit_id
          WHERE v.site_id=? AND v.started_at>=? AND v.started_at<?
          GROUP BY v.visit_id
        """
        with self._connection("visits", deadline) as connection:
            result = dict(self._distribution_from_base(
                connection, base_sql=base,
                parameters=(site_id, from_utc, to_utc), threshold=None,
                deadline=deadline))
            counts = self._one(connection, """
              WITH cohort AS (
                SELECT v.visit_id, COUNT(a.row_id) n FROM visits v
                LEFT JOIN visit_authorizations a ON a.visit_id=v.visit_id
                WHERE v.site_id=? AND v.started_at>=? AND v.started_at<?
                GROUP BY v.visit_id)
              SELECT COALESCE(SUM(n=1),0) exactly_one,
                     COALESCE(SUM(n>1),0) multiple,
                     COALESCE(SUM(n=0),0) zero FROM cohort
            """, (site_id, from_utc, to_utc), deadline)
        result.update(dict(counts))
        return result

    def visit_closure_summary(
        self, *, site_id: str, from_utc: str, to_utc: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        base = """
          SELECT rowid row_id, NULL cycle_id, NULL ap_mac,
                 started_at observed_at,
                 CASE WHEN reported_connected_seconds IS NOT NULL
                       AND duration_seconds IS NOT NULL
                      THEN reported_connected_seconds-duration_seconds END value,
                 CASE WHEN status='closed' THEN 1 ELSE 0 END accepted,
                 NULL reason
          FROM visits WHERE site_id=? AND started_at>=? AND started_at<?
        """
        with self._connection("visits", deadline) as connection:
            groups = self._all(connection, """
              SELECT close_reason, close_time_source, COUNT(*) count
              FROM visits WHERE site_id=? AND started_at>=? AND started_at<?
                AND status='closed'
              GROUP BY close_reason, close_time_source
            """, (site_id, from_utc, to_utc), deadline)
            dist = dict(self._distribution_from_base(
                connection, base_sql=base,
                parameters=(site_id, from_utc, to_utc), threshold=None,
                deadline=deadline))
        reasons: dict[str, int] = {}
        sources: dict[str, int] = {}
        for row in groups:
            n = int(row["count"])
            reasons[str(row["close_reason"])] = (
                reasons.get(str(row["close_reason"]), 0) + n)
            sources[str(row["close_time_source"])] = (
                sources.get(str(row["close_time_source"]), 0) + n)
        return {"close_reasons": reasons, "close_time_sources": sources,
                "closed_visit_count": sum(reasons.values()),
                "duration_difference": dist}

    def visit_context_distribution(
        self, *, site_id: str, from_utc: str, to_utc: str,
        dimension: str, deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        columns = {
            "start_ssid": ("v.start_ssid", False),
            "final_ssid": ("v.final_ssid", False),
            "start_ap_mac": ("v.start_ap_mac", False),
            "final_ap_mac": ("v.final_ap_mac", False),
            "touched_ssid": ("a.portal_ssid", True),
            "touched_ap_mac": ("a.portal_ap_mac", True),
        }
        if dimension not in columns:
            raise ValueError("unsupported Visit context dimension")
        column, touched = columns[dimension]
        join = "JOIN visit_authorizations a ON a.visit_id=v.visit_id" if touched else ""
        count = "COUNT(DISTINCT v.visit_id)" if touched else "COUNT(*)"
        with self._connection("visits", deadline) as connection:
            rows = self._all(connection, f"""
              SELECT {column} context, {count} visit_count
              FROM visits v {join}
              WHERE v.site_id=? AND v.started_at>=? AND v.started_at<?
              GROUP BY {column} ORDER BY visit_count DESC, context
            """, (site_id, from_utc, to_utc), deadline)
            meta = self._one(connection, """
              SELECT COUNT(*) rows_examined, MAX(started_at) watermark
              FROM visits WHERE site_id=? AND started_at>=? AND started_at<?
            """, (site_id, from_utc, to_utc), deadline)
        return {"rows": tuple(dict(row) for row in rows),
                "rows_examined": int(meta["rows_examined"]),
                "watermark": meta["watermark"]}

    def visit_context_transitions(
        self, *, site_id: str, from_utc: str, to_utc: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        with self._connection("visits", deadline) as connection:
            row = self._one(connection, """
              SELECT COUNT(*) rows_examined, MAX(started_at) watermark,
                COALESCE(SUM(start_ssid IS NOT NULL AND final_ssid IS NOT NULL),0) ssid_comparable,
                COALESCE(SUM(start_ssid IS NOT NULL AND final_ssid IS NOT NULL AND start_ssid<>final_ssid),0) ssid_changed,
                COALESCE(SUM(start_ssid IS NOT NULL AND final_ssid IS NOT NULL AND start_ssid=final_ssid),0) ssid_unchanged,
                COALESCE(SUM(start_ssid IS NULL OR final_ssid IS NULL),0) ssid_missing,
                COALESCE(SUM(start_ap_mac IS NOT NULL AND final_ap_mac IS NOT NULL),0) ap_comparable,
                COALESCE(SUM(start_ap_mac IS NOT NULL AND final_ap_mac IS NOT NULL AND start_ap_mac<>final_ap_mac),0) ap_changed,
                COALESCE(SUM(start_ap_mac IS NOT NULL AND final_ap_mac IS NOT NULL AND start_ap_mac=final_ap_mac),0) ap_unchanged,
                COALESCE(SUM(start_ap_mac IS NULL OR final_ap_mac IS NULL),0) ap_missing
              FROM visits WHERE site_id=? AND started_at>=? AND started_at<?
            """, (site_id, from_utc, to_utc), deadline)
        return dict(row)

    def visit_windows(
        self, *, site_id: str, from_utc: str, to_utc: str,
        evaluation_at_utc: str, deadline: QueryDeadline,
    ) -> tuple[Mapping[str, Any], ...]:
        with self._connection("visits", deadline) as connection:
            rows = self._all(connection, """
              SELECT visit_id, client_mac, device_id, started_at, closed_at,
                     CASE WHEN closed_at IS NULL THEN ? ELSE closed_at END
                       evaluation_end,
                     reported_traffic_total_bytes,
                     reported_traffic_up_bytes,
                     reported_traffic_down_bytes
              FROM visits
              WHERE site_id=? AND started_at>=? AND started_at<?
              ORDER BY started_at, visit_id LIMIT ?
            """, (evaluation_at_utc, site_id, from_utc, to_utc,
                    MAX_CROSS_SOURCE_IDENTIFIERS + 1), deadline)
        if len(rows) > MAX_CROSS_SOURCE_IDENTIFIERS:
            raise AnalyticsPerformanceBudgetExceeded(
                "Visit cohort exceeds materialization budget")
        return tuple(dict(row) for row in rows)

    def visit_observation_coverage_batch(
        self, *, site_id: str, windows: Sequence[Mapping[str, Any]],
        gap_threshold_seconds: float, deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        if not windows:
            return {"rows": (), "rows_examined": 0, "rows_accepted": 0,
                    "watermark": None}
        results: list[Mapping[str, Any]] = []
        examined = 0
        accepted = 0
        watermark: str | None = None
        with self._connection("observations", deadline) as connection:
            for offset in range(0, len(windows), _VISIT_WINDOW_BATCH_SIZE):
                deadline.require_remaining()
                batch = windows[offset:offset + _VISIT_WINDOW_BATCH_SIZE]
                values = ",".join("(?,?,?,?,?)" for _ in batch)
                parameters: list[Any] = []
                for row in batch:
                    parameters.extend((row["visit_id"], site_id,
                                       row["client_mac"], row["started_at"],
                                       row["evaluation_end"]))
                parameters.append(gap_threshold_seconds)
                rows = self._all(connection, f"""
                  WITH windows(visit_id,site_id,client_mac,start_at,end_at) AS (
                    VALUES {values}
                  ), accepted AS (
                    SELECT w.visit_id, w.start_at, w.end_at,
                           o.observed_at, o.row_id
                    FROM windows w
                    LEFT JOIN client_observations o
                      ON o.site_id=w.site_id AND o.client_mac=w.client_mac
                     AND o.observed_at>=w.start_at AND o.observed_at<w.end_at
                    LEFT JOIN observation_cycles c ON c.cycle_id=o.cycle_id
                    WHERE o.row_id IS NULL OR (
                      c.state='completed' AND c.complete=1
                      AND c.result='success'
                      AND o.source_inventory_complete=1)
                  ), ordered AS (
                    SELECT *, LAG(observed_at) OVER (
                      PARTITION BY visit_id ORDER BY observed_at,row_id
                    ) previous_at FROM accepted
                  ), gaps AS (
                    SELECT *, CASE WHEN previous_at IS NULL THEN NULL ELSE
                      (julianday(observed_at)-julianday(previous_at))*86400.0
                    END gap_seconds FROM ordered
                  )
                  SELECT visit_id, MIN(start_at) start_at, MIN(end_at) end_at,
                         COUNT(observed_at) sample_count,
                         MIN(observed_at) first_observed_at,
                         MAX(observed_at) last_observed_at,
                         MAX(gap_seconds) max_gap_seconds,
                         COALESCE(SUM(gap_seconds>?),0)
                           gap_count_over_threshold
                  FROM gaps GROUP BY visit_id ORDER BY visit_id
                """, (*parameters,), deadline)
                for row in rows:
                    item = dict(row)
                    results.append(item)
                    examined += int(item["sample_count"])
                    accepted += int(item["sample_count"])
                    observed = item["last_observed_at"]
                    if observed is not None:
                        watermark = max(watermark or str(observed), str(observed))
        return {"rows": tuple(results), "rows_examined": examined,
                "rows_accepted": accepted, "watermark": watermark}

    def visit_observed_traffic_batch(
        self, *, site_id: str, windows: Sequence[Mapping[str, Any]],
        max_gap_seconds: float, deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        if not windows:
            return {"rows": (), "rows_examined": 0, "rows_accepted": 0,
                    "watermark": None}
        output: list[Mapping[str, Any]] = []
        examined = accepted = 0
        watermark: str | None = None
        with self._connection("observations", deadline) as connection:
            for offset in range(0, len(windows), _VISIT_WINDOW_BATCH_SIZE):
                batch = windows[offset:offset + _VISIT_WINDOW_BATCH_SIZE]
                values = ",".join("(?,?,?,?,?)" for _ in batch)
                parameters: list[Any] = []
                for row in batch:
                    parameters.extend((row["visit_id"], site_id,
                                       row["client_mac"], row["started_at"],
                                       row["evaluation_end"]))
                rows = self._all(connection, f"""
                  WITH windows(visit_id,site_id,client_mac,start_at,end_at) AS (
                    VALUES {values}
                  ), samples AS (
                    SELECT w.visit_id,o.observed_at,o.row_id,
                           o.traffic_down,o.traffic_up
                    FROM windows w JOIN client_observations o
                      ON o.site_id=w.site_id AND o.client_mac=w.client_mac
                     AND o.observed_at>=w.start_at AND o.observed_at<w.end_at
                    JOIN observation_cycles c ON c.cycle_id=o.cycle_id
                    WHERE c.state='completed' AND c.complete=1
                      AND c.result='success' AND o.source_inventory_complete=1
                  ), pairs AS (
                    SELECT *, LAG(observed_at) OVER (
                      PARTITION BY visit_id ORDER BY observed_at,row_id) prev_at,
                      LAG(traffic_down) OVER (
                      PARTITION BY visit_id ORDER BY observed_at,row_id) prev_down,
                      LAG(traffic_up) OVER (
                      PARTITION BY visit_id ORDER BY observed_at,row_id) prev_up
                    FROM samples
                  ), deltas AS (
                    SELECT *,
                      (julianday(observed_at)-julianday(prev_at))*86400.0 elapsed,
                      CASE WHEN prev_down IS NOT NULL AND traffic_down>=prev_down
                             AND ROUND((julianday(observed_at)-julianday(prev_at))*86400.0,3)>0
                             AND ROUND((julianday(observed_at)-julianday(prev_at))*86400.0,3)<=?
                           THEN traffic_down-prev_down END down_delta,
                      CASE WHEN prev_up IS NOT NULL AND traffic_up>=prev_up
                             AND ROUND((julianday(observed_at)-julianday(prev_at))*86400.0,3)>0
                             AND ROUND((julianday(observed_at)-julianday(prev_at))*86400.0,3)<=?
                           THEN traffic_up-prev_up END up_delta
                    FROM pairs
                  )
                  SELECT visit_id, COUNT(*) sample_count,
                         COALESCE(SUM(down_delta IS NOT NULL OR up_delta IS NOT NULL),0)
                           valid_interval_count,
                         SUM(down_delta) down_delta,
                         SUM(up_delta) up_delta,
                         MAX(observed_at) watermark
                  FROM deltas GROUP BY visit_id
                """, (*parameters, max_gap_seconds, max_gap_seconds), deadline)
                for row in rows:
                    item = dict(row); output.append(item)
                    examined += max(int(item["sample_count"]) - 1, 0)
                    accepted += int(item["valid_interval_count"])
                    observed = item["watermark"]
                    if observed is not None:
                        watermark = max(watermark or str(observed), str(observed))
        return {"rows": tuple(output), "rows_examined": examined,
                "rows_accepted": accepted,
                "rows_rejected": max(examined-accepted, 0),
                "watermark": watermark}

    def visit_return_intervals(
        self, *, site_id: str, from_utc: str, to_utc: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        base = """
          SELECT row_id, NULL cycle_id, NULL ap_mac,
                 started_at observed_at, interval_seconds value,
                 CASE WHEN interval_seconds>=0 THEN 1 ELSE 0 END accepted,
                 NULL reason
          FROM (
            SELECT rowid row_id, started_at,
              (julianday(started_at)-julianday(LAG(started_at) OVER (
                PARTITION BY device_id ORDER BY started_at,visit_id)))*86400.0
                interval_seconds
            FROM visits
            WHERE site_id=? AND device_id IS NOT NULL AND started_at<?
          ) WHERE started_at>=? AND started_at<? AND interval_seconds IS NOT NULL
        """
        with self._connection("visits", deadline) as connection:
            return self._distribution_from_base(
                connection, base_sql=base,
                parameters=(site_id, to_utc, from_utc, to_utc),
                threshold=None, deadline=deadline)

    def wireless_scalar_distribution(
        self,
        *,
        site_id: str,
        source: str,
        metric: str,
        from_utc: str,
        to_utc: str,
        quality_mode: str,
        filters: Mapping[str, Any],
        threshold: float | None,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        if metric not in WIRELESS_SCALAR_FIELDS.get(source, frozenset()):
            raise ValueError("unsupported wireless scalar metric")
        spec = _wireless_source_spec(source)
        filter_sql, filter_parameters = _wireless_filters(
            source, filters, alias="o"
        )
        accepted = (
            spec["strict"]
            if quality_mode == "strict_complete"
            else spec["diagnostic"]
        )
        base_sql = f"""
            SELECT o.row_id, o.cycle_id, o.ap_mac,
                   {spec['time']} AS observed_at,
                   o.{metric} AS value,
                   CASE WHEN ({accepted}) THEN 1 ELSE 0 END AS accepted,
                   NULL AS reason
            FROM {spec['from']}
            WHERE o.site_id=? AND {spec['time']}>=? AND {spec['time']}<?
              {filter_sql}
        """
        with self._connection("observations", deadline) as connection:
            return self._distribution_from_base(
                connection,
                base_sql=base_sql,
                parameters=(
                    site_id, from_utc, to_utc, *filter_parameters,
                ),
                threshold=threshold,
                deadline=deadline,
            )

    def client_context_distribution(
        self,
        *,
        site_id: str,
        dimension: str,
        from_utc: str,
        to_utc: str,
        quality_mode: str,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        if dimension not in CLIENT_CONTEXT_FIELDS:
            raise ValueError("unsupported client context dimension")
        spec = _wireless_source_spec("client")
        accepted = (
            spec["strict"]
            if quality_mode == "strict_complete"
            else spec["diagnostic"]
        )
        with self._connection("observations", deadline) as connection:
            rows = self._all(
                connection,
                f"""
                WITH base AS (
                    SELECT o.{dimension} AS context, o.client_mac,
                           CASE WHEN ({accepted}) THEN 1 ELSE 0 END accepted,
                           o.observed_at
                    FROM {spec['from']}
                    WHERE o.site_id=? AND o.observed_at>=?
                      AND o.observed_at<?
                ), accepted AS (
                    SELECT * FROM base WHERE accepted=1
                ), grouped AS (
                    SELECT context, COUNT(*) observation_count,
                           COUNT(DISTINCT client_mac) distinct_client_count
                    FROM accepted GROUP BY context
                )
                SELECT context, observation_count, distinct_client_count,
                       (SELECT COUNT(*) FROM base) rows_examined,
                       (SELECT COUNT(*) FROM accepted) rows_accepted,
                       (SELECT COUNT(*) FROM base WHERE accepted=0)
                           rows_rejected,
                       (SELECT COUNT(*) FROM accepted WHERE context IS NULL)
                           missing_context_count,
                       (SELECT MAX(observed_at) FROM accepted) watermark
                FROM grouped
                ORDER BY context IS NOT NULL, context
                """,
                (site_id, from_utc, to_utc),
                deadline,
            )
            if rows:
                first = rows[0]
                return {
                    "items": tuple(dict(row) for row in rows),
                    "rows_examined": int(first["rows_examined"]),
                    "rows_accepted": int(first["rows_accepted"]),
                    "rows_rejected": int(first["rows_rejected"]),
                    "missing_context_count": int(
                        first["missing_context_count"]
                    ),
                    "watermark": first["watermark"],
                }
            summary = self._one(
                connection,
                f"""
                SELECT COUNT(*) rows_examined,
                       COALESCE(SUM(({accepted})), 0) rows_accepted,
                       COUNT(*)-COALESCE(SUM(({accepted})), 0) rows_rejected,
                       MAX(CASE WHEN ({accepted}) THEN o.observed_at END)
                           watermark
                FROM {spec['from']}
                WHERE o.site_id=? AND o.observed_at>=? AND o.observed_at<?
                """,
                (site_id, from_utc, to_utc),
                deadline,
            )
        return {
            "items": (),
            "rows_examined": int(summary["rows_examined"]),
            "rows_accepted": int(summary["rows_accepted"]),
            "rows_rejected": int(summary["rows_rejected"]),
            "missing_context_count": 0,
            "watermark": summary["watermark"],
        }

    def concurrent_client_distribution(
        self,
        *,
        site_id: str,
        from_utc: str,
        to_utc: str,
        quality_mode: str,
        group_by: str | None,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        if group_by is not None and group_by not in {
            "ap_mac", "ssid", "band"
        }:
            raise ValueError("unsupported concurrent-client grouping")
        cycle_acceptance = (
            "c.state='completed' AND c.complete=1 AND c.result='success'"
            if quality_mode == "strict_complete"
            else "c.state='completed'"
        )
        row_acceptance = (
            "o.source_inventory_complete=1"
            if quality_mode == "strict_complete" else "1"
        )
        with self._connection("observations", deadline) as connection:
            summary = self._one(
                connection,
                f"""
                SELECT COUNT(*) rows_examined,
                       COALESCE(SUM({cycle_acceptance}), 0) rows_accepted,
                       COUNT(*)-COALESCE(SUM({cycle_acceptance}), 0)
                         rows_rejected,
                       COALESCE(SUM(c.state='completed'
                         AND c.result='partial'), 0) partial_cycle_count,
                       COALESCE(SUM(c.state='completed'
                         AND c.result='failed'), 0) failed_cycle_count,
                       COALESCE(SUM(c.state='abandoned'), 0)
                         abandoned_cycle_count,
                       MAX(CASE WHEN {cycle_acceptance}
                         THEN c.started_at END) watermark
                FROM observation_cycles c
                WHERE c.site_id=? AND c.kind='client'
                  AND c.started_at>=? AND c.started_at<?
                """,
                (site_id, from_utc, to_utc),
                deadline,
            )
            if group_by is None:
                samples = f"""
                    SELECT c.cycle_id, NULL context,
                           COUNT(o.row_id) value,
                           c.started_at observed_at
                    FROM accepted_cycles c
                    LEFT JOIN client_observations o
                      ON o.cycle_id=c.cycle_id AND ({row_acceptance})
                    GROUP BY c.cycle_id
                """
            else:
                # Groups originate only in real accepted observations.  The
                # cross product then supplies an explicit zero for every
                # accepted cycle in which that real group was absent.  This
                # keeps an actual NULL context distinct from an empty cycle.
                samples = f"""
                    SELECT c.cycle_id, g.context,
                           COUNT(o.row_id) value,
                           c.started_at observed_at
                    FROM accepted_cycles c
                    CROSS JOIN (
                      SELECT DISTINCT o.{group_by} context
                      FROM accepted_cycles present_cycle
                      JOIN client_observations o
                        ON o.cycle_id=present_cycle.cycle_id
                       AND ({row_acceptance})
                    ) g
                    LEFT JOIN client_observations o
                      ON o.cycle_id=c.cycle_id AND ({row_acceptance})
                     AND o.{group_by} IS g.context
                    GROUP BY c.cycle_id, g.context
                """
            rows = self._all(
                connection,
                f"""
                WITH accepted_cycles AS MATERIALIZED (
                    SELECT cycle_id, started_at
                    FROM observation_cycles c
                    WHERE c.site_id=? AND c.kind='client'
                      AND c.started_at>=? AND c.started_at<?
                      AND ({cycle_acceptance})
                ), samples AS ({samples}), ranked AS (
                    SELECT context, value, observed_at,
                           ROW_NUMBER() OVER (
                             PARTITION BY context ORDER BY value, cycle_id
                           )-1 AS rank_index,
                           COUNT(*) OVER (PARTITION BY context) AS n
                    FROM samples
                )
                SELECT context, MAX(n) cycle_sample_count,
                       MIN(value) minimum, AVG(value) mean,
                       MAX(value) maximum,
                       {_percentile_columns('p50', 0.50)},
                       {_percentile_columns('p95', 0.95)},
                       MAX(observed_at) watermark
                FROM ranked GROUP BY context
                ORDER BY context IS NOT NULL, context
                """,
                (site_id, from_utc, to_utc),
                deadline,
            )
        return {
            "items": tuple(dict(row) for row in rows),
            "rows_examined": int(summary["rows_examined"]),
            "rows_accepted": int(summary["rows_accepted"]),
            "rows_rejected": int(summary["rows_rejected"]),
            "partial_cycle_count": int(summary["partial_cycle_count"]),
            "failed_cycle_count": int(summary["failed_cycle_count"]),
            "abandoned_cycle_count": int(summary["abandoned_cycle_count"]),
            "watermark": summary["watermark"],
        }

    def radio_utilization_distributions(
        self,
        *,
        site_id: str,
        metric: str,
        from_utc: str,
        to_utc: str,
        quality_mode: str,
        ap_mac: str | None,
        band: str | None,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        if metric not in WIRELESS_SCALAR_FIELDS["radio"]:
            raise ValueError("unsupported radio utilization metric")
        spec = _wireless_source_spec("radio")
        accepted = (
            spec["strict"]
            if quality_mode == "strict_complete"
            else spec["diagnostic"]
        )
        filter_sql, filter_parameters = _wireless_filters(
            "radio", {"ap_mac": ap_mac, "band": band}, alias="o"
        )
        parameters = (site_id, from_utc, to_utc, *filter_parameters)
        with self._connection("observations", deadline) as connection:
            summary = self._one(
                connection,
                f"""
                SELECT COUNT(*) rows_examined,
                       COALESCE(SUM({accepted}), 0) rows_accepted,
                       COUNT(*)-COALESCE(SUM({accepted}), 0) rows_rejected,
                       COUNT(DISTINCT CASE WHEN {accepted}
                         THEN o.ap_mac END) distinct_ap_count,
                       COUNT(DISTINCT CASE WHEN NOT ({accepted})
                         THEN o.cycle_id END) partial_cycle_count,
                       MAX(CASE WHEN {accepted}
                         THEN o.radio_observed_at END) watermark
                FROM {spec['from']}
                WHERE o.site_id=? AND o.radio_observed_at>=?
                  AND o.radio_observed_at<? {filter_sql}
                """,
                parameters,
                deadline,
            )
            rows = self._all(
                connection,
                f"""
                WITH base AS MATERIALIZED (
                  SELECT o.ap_mac, o.band, o.{metric} value,
                         o.radio_observed_at observed_at
                  FROM {spec['from']}
                  WHERE o.site_id=? AND o.radio_observed_at>=?
                    AND o.radio_observed_at<? {filter_sql}
                    AND ({accepted})
                ), group_stats AS (
                  SELECT ap_mac, band, COUNT(*) rows_accepted,
                         COALESCE(SUM(value IS NULL), 0) missing_count,
                         MAX(observed_at) watermark
                  FROM base GROUP BY ap_mac, band
                ), histogram AS (
                  SELECT ap_mac, band, value, COUNT(*) frequency
                  FROM base WHERE value IS NOT NULL
                  GROUP BY ap_mac, band, value
                ), ranked AS (
                  SELECT ap_mac, band, value, frequency,
                         SUM(frequency) OVER (
                           PARTITION BY ap_mac, band ORDER BY value
                           ROWS UNBOUNDED PRECEDING
                         ) cumulative_count,
                         SUM(frequency) OVER (
                           PARTITION BY ap_mac, band
                         ) n
                  FROM histogram
                ), value_stats AS (
                  SELECT ap_mac, band,
                         COALESCE(SUM(frequency), 0) sample_count,
                         MIN(value) minimum, MAX(value) maximum,
                         SUM(value*frequency)*1.0/SUM(frequency) mean,
                         {_histogram_percentile_columns('p10', 0.10)},
                         {_histogram_percentile_columns('p50', 0.50)},
                         {_histogram_percentile_columns('p90', 0.90)},
                         {_histogram_percentile_columns('p95', 0.95)}
                  FROM ranked GROUP BY ap_mac, band
                )
                SELECT g.ap_mac, g.band, g.rows_accepted,
                       g.missing_count, g.watermark,
                       COALESCE(v.sample_count, 0) sample_count,
                       v.minimum, v.maximum, v.mean,
                       v.p10_lower, v.p10_upper,
                       v.p50_lower, v.p50_upper,
                       v.p90_lower, v.p90_upper,
                       v.p95_lower, v.p95_upper
                FROM group_stats g
                LEFT JOIN value_stats v
                  ON v.ap_mac=g.ap_mac AND v.band IS g.band
                ORDER BY g.ap_mac, g.band
                """,
                parameters,
                deadline,
            )
        return {
            "items": tuple(dict(row) for row in rows),
            "rows_examined": int(summary["rows_examined"]),
            "rows_accepted": int(summary["rows_accepted"]),
            "rows_rejected": int(summary["rows_rejected"]),
            "distinct_ap_count": int(summary["distinct_ap_count"]),
            "partial_cycle_count": int(summary["partial_cycle_count"]),
            "watermark": summary["watermark"],
        }

    def stored_rate_distribution(
        self,
        *,
        site_id: str,
        metric: str,
        from_utc: str,
        to_utc: str,
        quality_mode: str,
        ap_mac: str | None,
        band: str | None,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        try:
            source, reason_field = STORED_RATE_FIELDS[metric]
        except KeyError as exc:
            raise ValueError("unsupported stored rate metric") from exc
        spec = _wireless_source_spec(source)
        filters = {"ap_mac": ap_mac, "band": band}
        filter_sql, filter_parameters = _wireless_filters(
            source, filters, alias="o"
        )
        accepted_source = (
            spec["strict"]
            if quality_mode == "strict_complete"
            else spec["diagnostic"]
        )
        base_sql = f"""
            SELECT o.row_id, o.cycle_id, o.ap_mac,
                   {spec['time']} observed_at,
                   CASE WHEN ({accepted_source})
                         AND o.{reason_field}='ok'
                        THEN o.{metric} END value,
                   CASE WHEN ({accepted_source}) THEN 1 ELSE 0 END accepted,
                   CASE WHEN ({accepted_source})
                        THEN COALESCE(o.{reason_field}, 'source_missing')
                        ELSE 'source_rejected' END reason
            FROM {spec['from']}
            WHERE o.site_id=? AND {spec['time']}>=? AND {spec['time']}<?
              {filter_sql}
        """
        parameters = (site_id, from_utc, to_utc, *filter_parameters)
        with self._connection("observations", deadline) as connection:
            summary = self._distribution_from_base(
                connection, base_sql=base_sql, parameters=parameters,
                threshold=None, deadline=deadline,
            )
        result = dict(summary)
        result["reason_counts"] = _reason_counts(result)
        result["valid_rate_sample_count"] = int(
            result["reason_counts"].get("ok", 0)
        )
        result["excluded_rate_sample_count"] = (
            int(result["rows_accepted"])
            - result["valid_rate_sample_count"]
        )
        return result

    def client_counter_rate_distribution(
        self,
        *,
        site_id: str,
        metric: str,
        from_utc: str,
        to_utc: str,
        quality_mode: str,
        max_gap_seconds: float,
        client_mac: str | None,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        try:
            counter = CLIENT_COUNTER_FIELDS[metric]
        except KeyError as exc:
            raise ValueError("unsupported client counter rate") from exc
        spec = _wireless_source_spec("client")
        accepted = (
            spec["strict"]
            if quality_mode == "strict_complete"
            else spec["diagnostic"]
        )
        client_filter = "" if client_mac is None else "AND o.client_mac=?"
        parameters: tuple[Any, ...] = (
            site_id, from_utc, to_utc,
            *((client_mac,) if client_mac is not None else ()),
            max_gap_seconds,
        )
        base_sql = f"""
            WITH all_rows AS MATERIALIZED (
                SELECT o.row_id, o.cycle_id, o.observed_at, o.client_mac,
                       o.{counter} counter_value,
                       CASE WHEN ({accepted}) THEN 1 ELSE 0 END
                         source_accepted
                FROM {spec['from']}
                WHERE o.site_id=? AND o.observed_at>=? AND o.observed_at<?
                  {client_filter}
            ), accepted_rows AS (
                SELECT * FROM all_rows WHERE source_accepted=1
            ), ordered AS (
                SELECT *,
                       LAG(counter_value) OVER (
                         PARTITION BY client_mac
                         ORDER BY observed_at, row_id
                       ) previous_value,
                       LAG(observed_at) OVER (
                         PARTITION BY client_mac
                         ORDER BY observed_at, row_id
                       ) previous_at
                FROM accepted_rows
            ), classified AS (
                SELECT row_id, cycle_id, NULL ap_mac, observed_at, 1 accepted,
                       CASE
                         WHEN previous_at IS NULL THEN 'no_baseline'
                         WHEN counter_value IS NULL OR previous_value IS NULL
                           THEN 'source_missing'
                         WHEN ROUND(
                           (julianday(observed_at)-julianday(previous_at))
                           *86400.0, 3)<=0 THEN 'invalid_elapsed'
                         WHEN ROUND(
                           (julianday(observed_at)-julianday(previous_at))
                           *86400.0, 3)>? THEN 'gap_too_large'
                         WHEN counter_value<previous_value THEN 'counter_reset'
                         ELSE 'ok' END reason,
                       CASE WHEN previous_at IS NOT NULL
                         AND counter_value IS NOT NULL
                         AND previous_value IS NOT NULL
                         AND counter_value>=previous_value
                         AND ROUND(
                           (julianday(observed_at)-julianday(previous_at))
                           *86400.0, 3)>0
                         AND ROUND(
                           (julianday(observed_at)-julianday(previous_at))
                           *86400.0, 3)<=?
                       THEN (counter_value-previous_value)*8.0/
                            ROUND(
                              (julianday(observed_at)-julianday(previous_at))
                              *86400.0, 3)/1000000.0 END value
                FROM ordered
            )
            SELECT * FROM classified
            UNION ALL
            SELECT row_id, cycle_id, NULL ap_mac, observed_at, 0 accepted,
                   'source_rejected' reason, NULL value
            FROM all_rows WHERE source_accepted=0
        """
        distribution_parameters = (*parameters, max_gap_seconds)
        with self._connection("observations", deadline) as connection:
            summary = self._distribution_from_base(
                connection, base_sql=base_sql,
                parameters=distribution_parameters,
                threshold=None, deadline=deadline,
            )
        result = dict(summary)
        result["reason_counts"] = _reason_counts(result)
        result["valid_rate_sample_count"] = int(
            result["reason_counts"].get("ok", 0)
        )
        result["excluded_rate_sample_count"] = (
            int(result["rows_accepted"])
            - result["valid_rate_sample_count"]
        )
        return result

    def radio_counter_quality(
        self,
        *,
        site_id: str,
        from_utc: str,
        to_utc: str,
        quality_mode: str,
        max_gap_seconds: float,
        ap_mac: str | None,
        band: str | None,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        spec = _wireless_source_spec("radio")
        accepted = (
            spec["strict"]
            if quality_mode == "strict_complete"
            else spec["diagnostic"]
        )
        filter_sql, filter_parameters = _wireless_filters(
            "radio", {"ap_mac": ap_mac, "band": band}, alias="o"
        )
        fields = tuple(sorted({
            field for pair in RADIO_COUNTER_FIELDS.values() for field in pair
        }))
        previous_fields = ",\n".join(
            f"previous.{field} previous_{field}"
            for field in fields
        )
        metric_projections: list[str] = []
        for output_name, (counter, packet) in RADIO_COUNTER_FIELDS.items():
            previous_counter = f"previous_{counter}"
            previous_packet = f"previous_{packet}"
            valid = (
                f"previous_at IS NOT NULL AND {counter} IS NOT NULL "
                f"AND {previous_counter} IS NOT NULL AND elapsed>0 "
                "AND elapsed<=max_gap "
                f"AND {counter}>={previous_counter}"
            )
            ratio_valid = (
                f"{valid} AND {packet} IS NOT NULL "
                f"AND {previous_packet} IS NOT NULL "
                f"AND {packet}>={previous_packet}"
            )
            metric_projections.extend((
                f"COALESCE(SUM({valid}),0) AS {output_name}_valid_count",
                "COALESCE(SUM(previous_at IS NOT NULL "
                f"AND {counter} IS NOT NULL "
                f"AND {previous_counter} IS NOT NULL "
                "AND elapsed>0 AND elapsed<=max_gap "
                f"AND {counter}<{previous_counter}),0) "
                f"AS {output_name}_reset_count",
                "COALESCE(SUM(previous_at IS NOT NULL "
                f"AND elapsed>max_gap),0) AS {output_name}_gap_count",
                "COALESCE(SUM(previous_at IS NULL "
                f"OR {counter} IS NULL OR {previous_counter} IS NULL "
                f"OR elapsed<=0),0) AS {output_name}_missing_count",
                f"COALESCE(SUM(CASE WHEN {valid} THEN "
                f"{counter}-{previous_counter} ELSE 0 END),0) "
                f"AS {output_name}_total_delta",
                f"COALESCE(SUM(CASE WHEN {ratio_valid} THEN "
                f"{counter}-{previous_counter} ELSE 0 END),0) "
                f"AS {output_name}_ratio_event_delta",
                f"COALESCE(SUM(CASE WHEN {ratio_valid} THEN "
                f"{packet}-{previous_packet} ELSE 0 END),0) "
                f"AS {output_name}_packet_delta",
            ))
        projections = ",\n".join(metric_projections)
        with self._connection("observations", deadline) as connection:
            row = self._one(
                connection,
                f"""
                WITH limits(max_gap) AS (SELECT ?), base_rows AS MATERIALIZED (
                  SELECT o.row_id, o.radio_observed_at, o.ap_mac, o.band,
                         o.cycle_id,
                         {', '.join(f'o.{field}' for field in fields)},
                         CASE WHEN ({accepted}) THEN 1 ELSE 0 END accepted
                  FROM {spec['from']}
                  WHERE o.site_id=? AND o.radio_observed_at>=?
                    AND o.radio_observed_at<? {filter_sql}
                ), accepted_rows AS (
                  SELECT * FROM base_rows WHERE accepted=1
                ), ordered AS (
                  SELECT *,
                    LAG(row_id) OVER (
                      PARTITION BY ap_mac, band
                      ORDER BY radio_observed_at, row_id
                    ) previous_row_id,
                    LAG(radio_observed_at) OVER (
                      PARTITION BY ap_mac, band
                      ORDER BY radio_observed_at, row_id
                    ) previous_at
                  FROM accepted_rows
                ), intervals AS (
                  SELECT current.*, {previous_fields}, ROUND(
                    (julianday(current.radio_observed_at)
                     -julianday(current.previous_at))
                    *86400.0, 3
                  ) elapsed, (SELECT max_gap FROM limits) max_gap
                  FROM ordered current
                  LEFT JOIN ap_radio_observations previous
                    ON previous.row_id=current.previous_row_id
                )
                SELECT (SELECT COUNT(*) FROM base_rows) rows_examined,
                       COUNT(*) rows_accepted,
                       (SELECT COUNT(*) FROM base_rows WHERE accepted=0)
                         rows_rejected,
                       (SELECT COUNT(DISTINCT cycle_id) FROM base_rows
                         WHERE accepted=0) partial_cycle_count,
                       {projections}, MAX(radio_observed_at) watermark
                FROM intervals
                """,
                (
                    max_gap_seconds, site_id, from_utc, to_utc,
                    *filter_parameters,
                ),
                deadline,
            )
        common = dict(row)
        metrics = {
            output_name: {
                "rows_accepted": int(common["rows_accepted"]),
                "valid_count": int(common[f"{output_name}_valid_count"]),
                "reset_count": int(common[f"{output_name}_reset_count"]),
                "gap_count": int(common[f"{output_name}_gap_count"]),
                "missing_count": int(common[f"{output_name}_missing_count"]),
                "total_delta": int(common[f"{output_name}_total_delta"]),
                "ratio_event_delta": int(
                    common[f"{output_name}_ratio_event_delta"]
                ),
                "packet_delta": int(common[f"{output_name}_packet_delta"]),
                "watermark": common["watermark"],
            }
            for output_name in RADIO_COUNTER_FIELDS
        }
        rows_accepted = int(common["rows_accepted"])
        return {
            "metrics": metrics,
            "rows_examined": int(common["rows_examined"]),
            "rows_accepted": rows_accepted,
            "rows_rejected": int(common["rows_rejected"]),
            "partial_cycle_count": int(common["partial_cycle_count"]),
            "watermark": common["watermark"],
        }

    def signal_ap_correlation(
        self,
        *,
        site_id: str,
        signal_metric: str,
        ap_metric: str,
        from_utc: str,
        to_utc: str,
        quality_mode: str,
        max_lag_seconds: float,
        deadline: QueryDeadline,
        client_mac: str | None = None,
    ) -> Mapping[str, Any]:
        if signal_metric not in {"rssi", "snr"}:
            raise ValueError("unsupported signal correlation metric")
        if ap_metric not in {"busy_util", "cpu_util"}:
            raise ValueError("unsupported AP correlation metric")
        client_spec = _wireless_source_spec("client")
        target_source = "radio" if ap_metric == "busy_util" else "ap"
        client_accepted = (
            client_spec["strict"] if quality_mode == "strict_complete"
            else client_spec["diagnostic"]
        )
        client_filter = "" if client_mac is None else "AND o.client_mac=?"
        client_parameters: tuple[Any, ...] = (
            () if client_mac is None else (client_mac,)
        )
        if target_source == "radio":
            lookup_identity = (
                "lt.ap_mac=k.ap_mac AND lt.band=k.band"
            )
            key_columns = "observed_at, ap_mac, band"
            key_join = (
                "ch.observed_at=cg.observed_at AND ch.ap_mac=cg.ap_mac "
                "AND ch.band IS cg.band"
            )
            target_time = "t.radio_observed_at"
            target_table = "ap_radio_observations"
            lookup_from = "ap_radio_observations lt"
            lookup_time = "lt.radio_observed_at"
            lookup_accepted = (
                "EXISTS (SELECT 1 FROM ap_observations lp "
                "JOIN observation_cycles lc ON lc.cycle_id=lt.cycle_id "
                "WHERE lp.row_id=lt.ap_observation_row_id "
                "AND lp.radios_ok=1 AND lp.site_id=lt.site_id "
                "AND lp.ap_mac=lt.ap_mac AND lp.cycle_id=lt.cycle_id"
            )
            if quality_mode == "strict_complete":
                lookup_accepted += (
                    " AND lc.complete=1 AND lc.result='success' "
                    "AND lp.partial=0"
                )
            lookup_accepted += ")"
        else:
            lookup_identity = "lt.ap_mac=k.ap_mac"
            key_columns = "observed_at, ap_mac"
            key_join = (
                "ch.observed_at=cg.observed_at AND ch.ap_mac=cg.ap_mac"
            )
            target_time = "t.observed_at"
            target_table = "ap_observations"
            lookup_from = "ap_observations lt"
            lookup_time = "lt.observed_at"
            lookup_accepted = (
                "lt.overview_ok=1 AND EXISTS (SELECT 1 "
                "FROM observation_cycles lc WHERE lc.cycle_id=lt.cycle_id "
                "AND lc.state='completed'"
            )
            if quality_mode == "strict_complete":
                lookup_accepted += (
                    " AND lc.complete=1 AND lc.result='success' "
                    "AND lt.partial=0"
                )
            lookup_accepted += ")"
        with self._connection("observations", deadline) as connection:
            row = self._one(
                connection,
                f"""
                WITH clients AS MATERIALIZED (
                  SELECT o.row_id client_row_id, o.observed_at,
                         o.ap_mac, o.band, o.{signal_metric} signal_value
                  FROM {client_spec['from']}
                  WHERE o.site_id=? AND o.observed_at>=? AND o.observed_at<?
                    AND ({client_accepted}) AND o.ap_mac IS NOT NULL
                    {client_filter}
                ), client_groups AS MATERIALIZED (
                  SELECT {key_columns}, signal_value, COUNT(*) weight
                  FROM clients GROUP BY {key_columns}, signal_value
                ), client_keys AS MATERIALIZED (
                  SELECT DISTINCT {key_columns} FROM client_groups
                ), chosen AS MATERIALIZED (
                  SELECT k.*,
                    (SELECT lt.row_id FROM {lookup_from}
                     WHERE lt.site_id=? AND ({lookup_identity})
                       AND {lookup_time}<=k.observed_at
                       AND ({lookup_accepted})
                     ORDER BY {lookup_time} DESC, lt.row_id DESC
                     LIMIT 1) target_row_id
                  FROM client_keys k
                ), paired AS (
                  SELECT cg.*, ch.target_row_id
                  FROM client_groups cg JOIN chosen ch ON {key_join}
                ), selected AS (
                  SELECT ch.*, {target_time} target_at,
                    t.{ap_metric} target_value,
                    CASE WHEN {target_time} IS NULL THEN NULL ELSE
                    ROUND(
                      (julianday(ch.observed_at)-julianday({target_time}))
                      *86400.0,
                      3
                    )
                    END lag_seconds
                  FROM paired ch
                  LEFT JOIN {target_table} t ON t.row_id=ch.target_row_id
                ), bounded AS (
                  SELECT *, CASE WHEN target_row_id IS NOT NULL
                    AND lag_seconds>=0 AND lag_seconds<=?
                    THEN 1 ELSE 0 END matched
                  FROM selected
                ), lag_histogram AS (
                  SELECT lag_seconds, SUM(weight) frequency
                  FROM bounded WHERE matched=1 GROUP BY lag_seconds
                ), lag_ranked AS (
                  SELECT lag_seconds, frequency,
                    SUM(frequency) OVER (
                      ORDER BY lag_seconds ROWS UNBOUNDED PRECEDING
                    ) cumulative_count,
                    SUM(frequency) OVER() n
                  FROM lag_histogram
                )
                SELECT (SELECT COALESCE(SUM(weight),0) FROM client_groups)
                    client_sample_count,
                  (SELECT COALESCE(SUM(weight*matched),0) FROM bounded)
                    matched_count,
                  (SELECT COALESCE(SUM(weight),0) FROM bounded
                    WHERE matched=1 AND signal_value IS NOT NULL
                      AND target_value IS NOT NULL) sample_count,
                  (SELECT COALESCE(SUM(signal_value*weight),0) FROM bounded
                    WHERE matched=1 AND signal_value IS NOT NULL
                      AND target_value IS NOT NULL) sum_x,
                  (SELECT COALESCE(SUM(target_value*weight),0) FROM bounded
                    WHERE matched=1 AND signal_value IS NOT NULL
                      AND target_value IS NOT NULL) sum_y,
                  (SELECT COALESCE(SUM(
                    signal_value*signal_value*weight),0)
                    FROM bounded WHERE matched=1
                      AND signal_value IS NOT NULL AND target_value IS NOT NULL)
                    sum_xx,
                  (SELECT COALESCE(SUM(
                    target_value*target_value*weight),0)
                    FROM bounded WHERE matched=1
                      AND signal_value IS NOT NULL AND target_value IS NOT NULL)
                    sum_yy,
                  (SELECT COALESCE(SUM(
                    signal_value*target_value*weight),0)
                    FROM bounded WHERE matched=1
                      AND signal_value IS NOT NULL AND target_value IS NOT NULL)
                    sum_xy,
                  (SELECT MAX(lag_seconds) FROM lag_ranked) lag_max,
                  (SELECT MIN(CASE WHEN cumulative_count>
                    CAST((n-1)*0.50 AS INTEGER) THEN lag_seconds END)
                    FROM lag_ranked) lag_p50_lower,
                  (SELECT MIN(CASE WHEN cumulative_count>
                    CAST((n-1)*0.50+0.999999999999 AS INTEGER)
                    THEN lag_seconds END) FROM lag_ranked) lag_p50_upper,
                  (SELECT MIN(CASE WHEN cumulative_count>
                    CAST((n-1)*0.95 AS INTEGER) THEN lag_seconds END)
                    FROM lag_ranked) lag_p95_lower,
                  (SELECT MIN(CASE WHEN cumulative_count>
                    CAST((n-1)*0.95+0.999999999999 AS INTEGER)
                    THEN lag_seconds END) FROM lag_ranked) lag_p95_upper,
                  (SELECT MAX(observed_at) FROM client_groups) watermark
                """,
                (site_id, from_utc, to_utc, *client_parameters,
                 site_id, max_lag_seconds),
                deadline,
            )
        return dict(row)

    def _distribution_from_base(
        self,
        connection: sqlite3.Connection,
        *,
        base_sql: str,
        parameters: Iterable[Any],
        threshold: float | None,
        deadline: QueryDeadline,
    ) -> Mapping[str, Any]:
        row = self._one(
            connection,
            f"""
            WITH base AS MATERIALIZED ({base_sql}),
            values_only AS (
              SELECT value FROM base
              WHERE accepted=1 AND value IS NOT NULL
            ), histogram AS (
              SELECT value, COUNT(*) frequency
              FROM values_only GROUP BY value
            ), ranked AS (
              SELECT value, frequency,
                SUM(frequency) OVER (
                  ORDER BY value ROWS UNBOUNDED PRECEDING
                ) cumulative_count,
                SUM(frequency) OVER () n
              FROM histogram
            ), base_stats AS (
              SELECT COUNT(*) rows_examined,
                COALESCE(SUM(accepted=1), 0) rows_accepted,
                COALESCE(SUM(accepted=0), 0) rows_rejected,
                COUNT(DISTINCT CASE WHEN accepted=1 THEN ap_mac END)
                  distinct_ap_count,
                MAX(CASE WHEN accepted=1 THEN observed_at END) watermark,
                COUNT(DISTINCT CASE WHEN accepted=0 THEN cycle_id END)
                  partial_cycle_count,
                COALESCE(SUM(reason='ok'),0) reason_ok,
                COALESCE(SUM(reason='no_baseline'),0) reason_no_baseline,
                COALESCE(SUM(reason='counter_reset'),0)
                  reason_counter_reset,
                COALESCE(SUM(reason='gap_too_large'),0)
                  reason_gap_too_large,
                COALESCE(SUM(reason='invalid_elapsed'),0)
                  reason_invalid_elapsed,
                COALESCE(SUM(reason='source_missing'),0)
                  reason_source_missing,
                COALESCE(SUM(reason='source_unavailable'),0)
                  reason_source_unavailable,
                COALESCE(SUM(reason='source_rejected'),0)
                  reason_source_rejected
              FROM base
            ), value_stats AS (
              SELECT COALESCE(SUM(frequency),0) sample_count,
                MIN(value) minimum, MAX(value) maximum,
                SUM(value*frequency)*1.0/SUM(frequency) mean,
                {_histogram_percentile_columns('p10', 0.10)},
                {_histogram_percentile_columns('p50', 0.50)},
                {_histogram_percentile_columns('p90', 0.90)},
                {_histogram_percentile_columns('p95', 0.95)},
                CASE WHEN ? IS NULL THEN NULL ELSE
                  COALESCE(SUM(
                    CASE WHEN value<? THEN frequency ELSE 0 END
                  ), 0) END below_threshold_count
              FROM ranked
            )
            SELECT b.*, v.*,
              b.rows_accepted-v.sample_count missing_count
            FROM base_stats b CROSS JOIN value_stats v
            """,
            (*tuple(parameters), threshold, threshold),
            deadline,
        )
        return dict(row)

    @contextmanager
    def _connection(
        self,
        source: str,
        deadline: QueryDeadline,
    ) -> Iterator[sqlite3.Connection]:
        deadline.require_remaining()
        service = {
            "observations": self._observations,
            "visits": self._visits,
            "registry": self._registry,
        }[source]
        try:
            with service.analytics_read_connection() as connection:
                connection.execute("PRAGMA query_only=ON")
                version = self._one(
                    connection, "PRAGMA user_version", (), deadline
                )
                if version is None or int(version[0]) != SOURCE_SCHEMA_VERSIONS[source]:
                    raise AnalyticsSourceUnavailable(
                        f"{source} schema version is unavailable"
                    )
                yield connection
        except AnalyticsSourceError:
            raise
        except (sqlite3.Error, OSError, ValueError) as exc:
            raise AnalyticsSourceUnavailable(
                f"{source} read is unavailable"
            ) from exc

    def _one(
        self,
        connection: sqlite3.Connection,
        sql: str,
        parameters: Iterable[Any],
        deadline: QueryDeadline,
    ) -> sqlite3.Row | None:
        with _statement_deadline(connection, deadline):
            try:
                return connection.execute(sql, tuple(parameters)).fetchone()
            except sqlite3.OperationalError as exc:
                _translate_sqlite_error(exc, deadline)
                raise

    def _all(
        self,
        connection: sqlite3.Connection,
        sql: str,
        parameters: Iterable[Any],
        deadline: QueryDeadline,
    ) -> list[sqlite3.Row]:
        with _statement_deadline(connection, deadline):
            try:
                return connection.execute(sql, tuple(parameters)).fetchall()
            except sqlite3.OperationalError as exc:
                _translate_sqlite_error(exc, deadline)
                raise


@contextmanager
def _statement_deadline(
    connection: sqlite3.Connection,
    deadline: QueryDeadline,
) -> Iterator[None]:
    deadline.require_remaining()

    def interrupted() -> int:
        return int(deadline.expired())

    connection.set_progress_handler(interrupted, _SQLITE_PROGRESS_OPCODES)
    try:
        yield
    finally:
        connection.set_progress_handler(None, 0)


def _translate_sqlite_error(
    exc: sqlite3.OperationalError,
    deadline: QueryDeadline,
) -> None:
    if deadline.expired() or "interrupted" in str(exc).lower():
        raise AnalyticsQueryDeadlineExceeded(
            "Analytics SQLite statement exceeded its deadline"
        ) from exc


def _visit_overlap_where() -> str:
    return (
        "v.site_id=? AND (v.closed_at IS NULL OR v.closed_at>?) "
        "AND v.started_at<?"
    )


def _field_source_spec(source: str) -> Mapping[str, str]:
    if source == "client":
        return {
            "from": (
                "client_observations o "
                "JOIN observation_cycles c ON c.cycle_id=o.cycle_id"
            ),
            "time": "o.observed_at",
            "strict": (
                "c.state='completed' AND c.complete=1 "
                "AND c.result='success' "
                "AND o.source_inventory_complete=1"
            ),
        }
    if source == "ap":
        return {
            "from": (
                "ap_observations o "
                "JOIN observation_cycles c ON c.cycle_id=o.cycle_id"
            ),
            "time": "o.observed_at",
            "strict": (
                "c.state='completed' AND c.complete=1 "
                "AND c.result='success' AND o.partial=0 "
                "AND o.overview_ok=1"
            ),
        }
    return {
        "from": (
            "ap_radio_observations o "
            "JOIN ap_observations p ON p.row_id=o.ap_observation_row_id "
            "JOIN observation_cycles c ON c.cycle_id=o.cycle_id"
        ),
        "time": "o.radio_observed_at",
        "strict": (
            "c.state='completed' AND c.complete=1 "
            "AND c.result='success' AND p.partial=0 "
            "AND p.radios_ok=1 AND p.site_id=o.site_id "
            "AND p.ap_mac=o.ap_mac AND p.cycle_id=o.cycle_id"
        ),
    }


def _wireless_source_spec(source: str) -> Mapping[str, str]:
    if source == "client":
        return {
            "from": (
                "client_observations o "
                "JOIN observation_cycles c ON c.cycle_id=o.cycle_id"
            ),
            "time": "o.observed_at",
            "strict": (
                "c.state='completed' AND c.complete=1 "
                "AND c.result='success' "
                "AND o.source_inventory_complete=1"
            ),
            "diagnostic": "c.state='completed'",
        }
    if source == "ap":
        return {
            "from": (
                "ap_observations o "
                "JOIN observation_cycles c ON c.cycle_id=o.cycle_id"
            ),
            "time": "o.observed_at",
            "strict": (
                "c.state='completed' AND c.complete=1 "
                "AND c.result='success' AND o.partial=0 "
                "AND o.overview_ok=1"
            ),
            "diagnostic": (
                "c.state='completed' AND o.overview_ok=1"
            ),
        }
    if source == "radio":
        return {
            "from": (
                "ap_radio_observations o "
                "JOIN ap_observations p ON p.row_id=o.ap_observation_row_id "
                "JOIN observation_cycles c ON c.cycle_id=o.cycle_id"
            ),
            "time": "o.radio_observed_at",
            "strict": (
                "c.state='completed' AND c.complete=1 "
                "AND c.result='success' AND p.partial=0 "
                "AND p.radios_ok=1 AND p.site_id=o.site_id "
                "AND p.ap_mac=o.ap_mac AND p.cycle_id=o.cycle_id"
            ),
            "diagnostic": (
                "c.state='completed' AND p.radios_ok=1 "
                "AND p.site_id=o.site_id AND p.ap_mac=o.ap_mac "
                "AND p.cycle_id=o.cycle_id"
            ),
        }
    raise ValueError("unsupported wireless source")


def _wireless_filters(
    source: str,
    filters: Mapping[str, Any],
    *,
    alias: str,
) -> tuple[str, tuple[Any, ...]]:
    allowed = {
        "client": frozenset({
            "client_mac", "ap_mac", "ssid", "band", "channel",
        }),
        "ap": frozenset({"ap_mac"}),
        "radio": frozenset({"ap_mac", "band"}),
    }[source]
    clauses: list[str] = []
    parameters: list[Any] = []
    for key, value in filters.items():
        if key not in allowed:
            if value is not None:
                raise ValueError("unsupported wireless filter")
            continue
        if value is not None:
            clauses.append(f"AND {alias}.{key}=?")
            parameters.append(value)
    return " ".join(clauses), tuple(parameters)


def _percentile_columns(prefix: str, probability: float) -> str:
    return (
        "MAX(CASE WHEN rank_index="
        f"CAST((n-1)*{probability:.2f} AS INTEGER) "
        f"THEN value END) {prefix}_lower, "
        "MAX(CASE WHEN rank_index="
        f"CAST((n-1)*{probability:.2f}+0.999999999999 AS INTEGER) "
        f"THEN value END) {prefix}_upper"
    )


def _histogram_percentile_columns(prefix: str, probability: float) -> str:
    return (
        "MIN(CASE WHEN cumulative_count>"
        f"CAST((n-1)*{probability:.2f} AS INTEGER) "
        f"THEN value END) {prefix}_lower, "
        "MIN(CASE WHEN cumulative_count>"
        f"CAST((n-1)*{probability:.2f}+0.999999999999 AS INTEGER) "
        f"THEN value END) {prefix}_upper"
    )


def _reason_counts(raw: Mapping[str, Any]) -> Mapping[str, int]:
    names = (
        "ok", "no_baseline", "counter_reset", "gap_too_large",
        "invalid_elapsed", "source_missing", "source_unavailable",
        "source_rejected",
    )
    return {
        name: int(raw.get(f"reason_{name}") or 0)
        for name in names
        if int(raw.get(f"reason_{name}") or 0) > 0
    }
