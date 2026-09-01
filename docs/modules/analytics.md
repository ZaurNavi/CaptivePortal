# Analytics

Status: current module contract
Updated: 2026-09-01
Baseline: `main@daf68e91fc759188980cf8741913e6b60a58eb62`

## Purpose

Read-only query/interpretation layer over persisted facts.

Analytics does not collect, own source persistence, call Omada or migrate/write
source DBs.

## Sources

`ObservationReadService`, `VisitLifecycleReadService`, `VisitorRegistryReadService`
→ `AnalyticsSourceGateway`.

Source health checks validate expected schema and SQLite `PRAGMA query_only`.

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

`CurrentTrafficReadService` owns current Site Network Throughput semantics for
Home Traffic and Traffic Current Network Throughput.

Rules:
- persisted AP Observation facts only;
- complete-success source cycles;
- strict source integrity;
- `wired` primary, `lan` fallback;
- one source family per Site result;
- explicit freshness/AP skew.

## Historical Network Traffic

`HistoricalTrafficReadService` is the single historical Network Traffic semantic
owner used by:

- Network Traffic History;
- Period Statistics;
- Peak Load;
- Traffic by AP.

Canonical source:

```text
persisted AP Observation history
```

It owns:
- Site/range validation;
- canonical 24h/7d range semantics;
- accepted complete Site samples;
- source-family selection;
- coverage/quality/watermark;
- bounded query/deadline behavior;
- History buckets;
- Period Statistics;
- Peak Load;
- Traffic by AP.

`TRAFFIC-02-PERF-01` requested-range bounding remains mandatory.

## Product-scoped historical projection

`TASK-TRAFFIC-RANGE-01` adds product-scoped execution without adding another
historical semantic owner.

Canonical product order:

```text
history,statistics,peak,aps
```

A request executes only the requested product-specific projections. Shared range,
coverage, integrity and source-boundary facts may still be reused where required.

AP-only projection remains self-contained through `ap_bucket_axis`.

Independent browser ranges do not create independent Analytics services. Every
historical panel continues to read the same persisted Network Traffic foundation.

## Period Statistics

Metrics in Mbps:

```text
Average Download / Upload / Total
Peak Download / Upload / Total
```

Average:

```text
right_endpoint_sample_hold_time_weighted.v1
```

Peak:

```text
max_accepted_complete_site_sample.v1
```

## Peak Load

Canonical methods:

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

Busiest 60 Minutes has no `occurrence_count` contract.

## Traffic by AP

Current metric:

```text
network_traffic_by_ap.v1
unit = Mbps
```

Canonical AP semantics include:

```text
population = current_union_historical_validated.v1
series = outer_history_bucket_aligned_du.v1
bucket method = mean_of_accepted_ap_rates_for_canonical_site_bucket_samples.v1
Average = right_endpoint_ap_sample_hold_time_weighted.v1
Peak = max_accepted_complete_ap_sample.v1
order = ap_mac_ascending.v1
supported population cap = 12 APs
```

Traffic by AP is per-AP Network Traffic evidence. It is not `TRAFFIC-06 AP Traffic
Share`; no share formula is current.

Historical product status models remain product-specific. Where applicable,
`ok | partial | insufficient_data` semantics remain explicit and safe.

## Performance boundary

The accepted independent-range remediation preserves:

```text
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS = 10
```

No query deadline, browser timeout or Admin concurrency increase is part of this
architecture.

## Internal API

Prefix: `/api/internal/analytics/v1`.

This is not Admin browser authentication and is not a product/browser Traffic path.

## Fail-open

Analytics may be disabled/unavailable without breaking Portal/Auth.
