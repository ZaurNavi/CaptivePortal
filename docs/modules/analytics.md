# Analytics

Status: current module contract
Updated: 2026-09-03
Baseline: `main@6425988b5b4ec5ff38bf9c67c74846c3806f668f`

## Purpose

Read-only query/interpretation layer over persisted facts.

Analytics does not collect, own source persistence, call Omada or migrate/write
source DBs.

## Sources

`ObservationReadService`, `VisitLifecycleReadService`, `VisitorRegistryReadService`
continue through `AnalyticsSourceGateway`.

`CurrentStateReadService` is the persisted Current State boundary used by
`CurrentGuestTrafficReadService`.

Source reads remain read-only/query-only.

## Services

Current services include:

- `AnalyticsReadService`;
- `WirelessAnalyticsService`;
- `VisitAnalyticsService`;
- `CurrentTrafficReadService`;
- `HistoricalTrafficReadService`;
- `CurrentGuestTrafficReadService`;
- `HomeActivityReadService`.

## Home Activity

Read-only aggregate over persisted Visit Lifecycle facts.

## Current Traffic

`CurrentTrafficReadService` owns current Site Network Throughput semantics and
uses persisted Observation AP facts.

## Online Guests Traffic current rate

`CurrentGuestTrafficReadService` is the semantic owner for TASK-TRAFFIC-07.

```text
Current State
→ CurrentStateReadService
→ CurrentGuestTrafficReadService
```

Canonical contracts:

```text
metric = network_traffic_online_guest_current_rate.v1
population = fresh_complete_current_state_authorized_guest_scope.v1
rate = current_connection_counter_delta_interval_average.v1
baseline = nearest_previous_complete_same_site_scope_cycle.v1
continuity = omada_controller_connection_progress_v1
boundary observation = sampled_current_state_evidence.v1
unit = Mbps
```

It does not use Observation, Visit, Visitor Registry, AuthSession, query-time
Omada calls or browser-side rate calculations.

Online Guest means controller-reported active authorized wireless guest in the
accepted Current State guest scope, not independent proof of instantaneous
physical RF presence.

## Historical Network Traffic

`HistoricalTrafficReadService` remains the single historical Network Traffic
semantic owner for History, Statistics, Peak, Traffic by AP and AP Traffic Share.

Canonical historical projection remains:

```text
history,statistics,peak,aps,apshare
```

Online Guests Traffic is not a historical product and is not governed by
historical range/admission orchestration.

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
