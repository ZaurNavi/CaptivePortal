# Analytics

Status: current module contract
Updated: 2026-08-31
Baseline: `main@a9cd8a9b9b9efc46bc82d315385ebbd1a3bf63b0`

## Purpose

Read-only query/interpretation layer over persisted facts.

Analytics does not collect, own source persistence, call Omada or migrate/write
source DBs.

## Sources

`ObservationReadService`, `VisitLifecycleReadService`, `VisitorRegistryReadService`
→ `AnalyticsSourceGateway`.

Source health checks expected schema and SQLite `PRAGMA query_only`.

## Services

Current services include:

- `AnalyticsReadService`;
- `WirelessAnalyticsService`;
- `VisitAnalyticsService`;
- `CurrentTrafficReadService`;
- `HistoricalTrafficReadService`;
- `HomeActivityReadService`.

## Home Activity

Read-only aggregate over persisted Visit Lifecycle facts. Guest Session Traffic
remains a separate completed-session domain and is not Network Traffic.

## Current Traffic

`CurrentTrafficReadService` reads persisted AP Observation facts and remains the
semantic owner for Home Traffic and Traffic Current Network Throughput.

Rules:
- complete-success source cycles only;
- strict source integrity;
- `wired` primary, `lan` fallback;
- one source family per Site result;
- freshness/AP skew explicit.

## Historical Network Traffic

`HistoricalTrafficReadService` is the single historical Network Traffic semantic
owner used by:

```text
Traffic History
Period Statistics
Peak Load
```

Canonical source:

```text
persisted AP Observation history
```

It owns Site/range validation, accepted complete Site samples, source-family
selection, coverage/quality/watermark, bounded query/deadline behavior, History
buckets, Period Statistics and Peak Load temporal projections.

`TRAFFIC-02-PERF-01` requested-range bounding remains mandatory.

No second Traffic historical collector/DB/algorithm owner exists.

## Period Statistics

Production-current at `main@a9cd8a9b9b9efc46bc82d315385ebbd1a3bf63b0`.

Metrics in Mbps:

```text
Average Download / Upload / Total
Peak Download / Upload / Total
```

Average:
`right_endpoint_sample_hold_time_weighted.v1`.

Peak:
`max_accepted_complete_site_sample.v1`.

Peak Total is a direct maximum of accepted Total samples, not
`Peak Download + Peak Upload`.

## Peak Load

Production-current at `main@a9cd8a9b9b9efc46bc82d315385ebbd1a3bf63b0`.

Canonical method identities:

```text
metric: network_traffic_peak_load.v1
peak: max_accepted_complete_site_sample.v1
peak tie: earliest_peak_sample_at.v1
sample timestamp: cycle_finished_at
busiest bucket: max_complete_history_bucket_total_mean.v1
bucket tie: earliest_bucket_start.v1
busiest 60m: max_complete_rolling_3600s_average_total_sample_hold.v1
60m average: right_endpoint_sample_hold_time_weighted.v1
hour tie: earliest_window_start.v1
```

Peak values are cross-validated against Period Statistics in the same response.
Busiest 60 Minutes has no `occurrence_count` contract.

History / Statistics / Peak share one 24h/7d range and one Historical read
execution. No independent Peak request/scheduler exists.

Statuses remain product-safe `ok | partial | insufficient_data` where applicable.

## Internal API

Prefix: `/api/internal/analytics/v1`.

This is not Admin browser authentication and is not a product/browser Traffic path.

## Fail-open

Analytics may be disabled/unavailable without breaking Portal/Auth.
