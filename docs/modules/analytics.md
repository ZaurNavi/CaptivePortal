# Analytics

Status: current module contract
Updated: 2026-08-30
Baseline: `main@b92efbfabb38f912550526bc5a3d1f2f1a8ae4d6`

## Purpose

Read-only query/interpretation layer over persisted facts.

Analytics:
- does not collect;
- does not own source persistence;
- does not call Omada;
- does not migrate/write source DB.

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

Read-only aggregate over persisted Visit Lifecycle facts. Authorized Visits use
one verified Visit-opening authorization per Visit, not AuthSession count.

Guest Session Traffic is an independent estimated completed-session metric and is
not Network Traffic.

## Current Traffic

Reads persisted AP Observation facts.

Rules:
- complete-success source cycles only;
- strict source integrity;
- `wired` primary, `lan` fallback;
- one source family per Site result;
- freshness/AP skew explicit.

Semantic owner for Home Traffic and Traffic Current Network Throughput:
`CurrentTrafficReadService`.

## Historical Network Traffic

`HistoricalTrafficReadService` is the single historical Network Traffic semantic
owner used by Traffic History and Period Statistics.

Canonical source:

```text
persisted AP Observation history
```

It owns:
- Site/range validation;
- accepted complete Site samples;
- source-family selection;
- coverage/quality/watermark;
- bounded query/deadline behavior;
- History buckets;
- Period Statistics computation.

`TRAFFIC-02-PERF-01` requested-range bounding remains mandatory.

No second Traffic historical collector/DB/algorithm owner exists.

## Period Statistics

Production-current as of `main@b92efbfabb38f912550526bc5a3d1f2f1a8ae4d6`.

Metrics in Mbps:

```text
Average Download / Upload / Total
Peak Download / Upload / Total
```

Average algorithm:
`right_endpoint_sample_hold_time_weighted.v1`.

Peak algorithm:
`max_accepted_complete_site_sample.v1`.

Peak Total is a direct maximum of accepted Total samples, not
`Peak Download + Peak Upload`.

Statistics shares the History range and read execution.

Statuses:

```text
ok
partial
insufficient_data
```

## Internal API

Prefix: `/api/internal/analytics/v1`.

This is not Admin browser authentication and is not a product/browser Traffic path.

## Fail-open

Analytics may be disabled/unavailable without breaking Portal/Auth.
