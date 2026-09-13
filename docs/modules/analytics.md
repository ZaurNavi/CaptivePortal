# Analytics

Status: current module contract
Updated: 2026-09-13
Baseline: `main@3dc85735ddf5d05dd20733d15dfe1c22c9c4fde5`

## Purpose

Read-only query/interpretation layer over persisted facts.

Analytics does not collect, own source persistence, call Omada or migrate/write
source DBs.

## Sources

`ObservationReadService`, `VisitLifecycleReadService`, `VisitorRegistryReadService`
→ `AnalyticsSourceGateway`.

`CurrentStateReadService` is the persisted Current State read boundary used by
`CurrentGuestTrafficReadService`.

Source health checks validate expected schema and SQLite `PRAGMA query_only`.

## SQLite finite/nonnegative portability

`TASK-TEST-BASELINE-CLEANUP-01` removed the platform-sensitive max-double SQL
check from `AnalyticsSourceGateway`.

Current and historical rate validation use the same fail-closed portable shape:

```text
typeof(value) IN ('integer','real')
AND value >= 0
AND COALESCE((value - value) = 0, 0)
```

Finite values pass. Infinity/non-finite evidence fails closed.

This is a read-validation portability rule only; Analytics remains read-only and
does not add source writes, migrations or query-time Omada access.

## Device Type read contract

Analytics remains read-only and preserves raw source semantics.

`SafeSnapshotSummary` exposes both:

```text
device_type
device_type_key
```

The canonical key is derived from the raw source value only through
`app/common/device_type.py`.

Analytics does not classify Device Type from hostname, system name, MAC, vendor,
SSID, AP, IP or unrelated evidence.

## Services

Current services include:

- `AnalyticsReadService`;
- `WirelessAnalyticsService`;
- `VisitAnalyticsService`;
- `CurrentTrafficReadService`;
- `HistoricalTrafficReadService`;
- `CurrentGuestTrafficReadService`;
- `CompletedGuestSessionTrafficReadService`;
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

## Online Guests Traffic current rate

`CurrentGuestTrafficReadService` is the semantic owner for `TASK-TRAFFIC-07`.

Canonical source:

```text
persisted Current State
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
accepted Current State guest scope. This is not independent proof of
instantaneous RF presence.

## Exact-client Current Guest Traffic reuse

`TASK-DEVICE-CARD-01` reuses the existing `CurrentGuestTrafficReadService`
semantic owner for one current authorized device.

New exact-client projection:

```text
CurrentStateReadService.read_current_guest_rate_client_evidence(...)
→ CurrentGuestTrafficReadService.get_current_guest_traffic_for_client(...)
```

The projection is pinned to the accepted Current State `current_cycle_id` and
canonical Site/scope identity. It reads one current row plus the nearest accepted
baseline row instead of materializing the Site population.

This is not a new Traffic semantic owner.

Permanent:

```text
same current cycle as Device Current Context
authorized current guest only
numeric zero remains valid
no query-time Omada
no source write
no new persistence/schema
```

Traffic source/integrity/deadline failures can be reported locally by Device
Current Context without invalidating otherwise trustworthy Current State facts.

## Completed Guest Session Traffic

`CompletedGuestSessionTrafficReadService` is the semantic owner for
`TASK-TRAFFIC-08`.

Canonical source:

```text
closed Visit Lifecycle rows
+
persisted Client Observation evidence
→ CompletedGuestSessionTrafficReadService
```

Core contracts:

```text
session identity = visit_id
population = status=closed
cohort boundary = closed_at
attribution window = [started_at, closed_at)
ranges = 24h | 7d
default range = 24h
max attribution window = 86400s
max accepted Observation gap = 180s
sort = closed_at DESC, visit_id DESC
pagination = keyset / no OFFSET
limit default=max=100
```

The selected UI cohort does not clip a Visit's internal attribution window.
Visits over 24 hours remain visible but return `null` traffic values with
`unavailable / attribution_window_exceeds_supported_max`.

Download/upload are evaluated independently. Numeric zero is valid evidence.
Missing/regressed counters, unproven/frozen/reset continuity, large gaps,
authorization boundaries and SSID evidence failures remain explicit reason codes.

Uptime continuity:

```text
current uptime > previous uptime → proven
equal → continuity_frozen
lower → connection_reset
missing → continuity_unproven
```

SSID must be present and equal at both interval endpoints. AP equality is not
required; roaming is allowed.

This read path performs no Omada/provider call, source DB write or projection
read. `historical_traffic_projection.v1` is not a source.

## Traffic Evidence semantic-owner reuse

Traffic Evidence does not create an Analytics semantic owner.

`TrafficEvidenceAggregator` lives in the Admin composition layer and reuses:

```text
Current:
  CurrentTrafficReadService

History / Statistics / Peak / AP Traffic / AP Share:
  HistoricalTrafficReadService

Online Guests:
  CurrentGuestTrafficReadService

Completed Sessions:
  CompletedGuestSessionTrafficReadService
```

Canonical architecture:

```text
accepted semantic owners
→ bounded application aggregation
→ safe Admin serialization
→ admin.read.v1
→ UI
```

Historical evidence products are grouped into one bounded Historical read.
Traffic Evidence performs no Omada/provider call and owns no source persistence,
schema, collection or scheduler.

## Historical Network Traffic

`HistoricalTrafficReadService` is the single historical Network Traffic semantic
owner used by:

- Network Traffic History;
- Period Statistics;
- Peak Load;
- Traffic by AP;
- AP Traffic Share.

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
- Traffic by AP;
- AP Traffic Share.

`TRAFFIC-02-PERF-01` requested-range bounding remains mandatory.

## Product-scoped historical projection

`TASK-TRAFFIC-RANGE-01` adds product-scoped execution without adding another
historical semantic owner.

Canonical product order:

```text
history,statistics,peak,aps,apshare
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

Traffic by AP remains per-AP Network Traffic evidence in Mbps.

## AP Traffic Share

`TRAFFIC-06` is current production functionality.

```text
metric = network_traffic_ap_share.v1
unit = fraction
display unit = percent
share = accepted_site_interval_integrated_ap_contribution_ratio.v1
temporal = right_endpoint_sample_hold_time_weighted.v1
presence = accepted_selected_source_historical_presence_in_range.v1
absence = proven_population_member_absent_from_trusted_complete_site_sample_zero_contribution.v1
```

AP Share reuses accepted HistoricalTrafficReadService interval/AP contribution facts. `sample count != traffic share`; browser code does not derive Share from sample counts. Current status family includes `ok | partial | insufficient_data | unsupported_population`. Safe current-source unavailability may yield truthful partial historical Share; malformed/contradictory current evidence fails closed.

Historical product status models remain product-specific. Where applicable,
`ok | partial | insufficient_data` semantics remain explicit and safe.

## Performance boundary

The accepted independent-range remediation preserves:

```text
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS = 10
```

No query deadline, browser timeout or Admin concurrency increase is part of this
architecture.

Current production baseline after `TASK-ADMIN-PROD-BASELINE-01` (2026-09-05):

```text
Admin concurrency=4
Admin query deadline=25s
dependent request timeouts=30s
historical admission guard=3s
```

## Internal API

Prefix: `/api/internal/analytics/v1`.

This is not Admin browser authentication and is not a product/browser Traffic path.

## Fail-open

Analytics may be disabled/unavailable without breaking Portal/Auth.
