# TASK-ANALYTICS-FOUNDATION-01 — Analytics Foundation — REV1

**Project:** CaptivPortal  
**Type:** master architecture / implementation specification  
**Status:** DRAFT FOR TECH LEAD / OWNER REVIEW  
**Implementation authorization:** NOT GRANTED  
**Architecture baseline:** `origin/main@fe797593fb12b9cb9f81bdb22e1c14f2d08b037e`  
**Production baseline at preparation:** `main@fe797593fb12b9cb9f81bdb22e1c14f2d08b037e`  
**Date:** 2026-08-14  
**Execution tasks:** `TASK-ANALYTICS-01A`, `TASK-ANALYTICS-01B`, `TASK-ANALYTICS-01C`

---

## 1. Purpose

Implement the next functional stage:

```text
Analytics Foundation
```

Permanent invariant:

```text
Analytics does not collect.
Analytics reads persisted facts.
```

Target:

```text
Visitor Registry / Snapshot ─┐
Visit Lifecycle ─────────────┼──> Analytics Read / Quality Foundation
Observation Foundation ──────┘              │
                                            ├──> Wireless Analytics
                                            └──> Visit Analytics
                                                     │
                                              future Web Foundation
```

Analytics must remain independent of Omada availability after facts are persisted.

---

## 2. Current authoritative baseline

Verified at `main@fe797593fb12b9cb9f81bdb22e1c14f2d08b037e`:

```text
Observation Foundation schema = 1
Visit Lifecycle schema        = 2
Visitor Registry schema       = 1
```

Production evidence confirms Observation and Visit Lifecycle are active and accumulating/closing real data.

Current code exposes:

```text
ObservationReadService
VisitLifecycleReadService
VisitorRegistryReadService
```

Current code/tests/schema override historical roadmap assumptions.

---

## 3. Required implementation order

```text
01A — Read and Data Quality Foundation
        ↓ merge + acceptance
01B — Wireless Analytics
        ↓ merge + acceptance
01C — Visit Analytics
```

- 01B cannot begin before 01A acceptance.
- 01C cannot begin before 01B acceptance.
- Each gets separate branch/PR/review/Linux gate.
- Production activation is separate.

Recommended branches:

```text
feature/analytics-read-quality-v1
feature/wireless-analytics-v1
feature/visit-analytics-v1
```

---

## 4. Authoritative sources

```text
Visitor Registry DB:
  /opt/CaptivePortal/data/visitor_registry.sqlite3

Observation DB:
  /opt/CaptivePortal/data/observations.sqlite3

Visit DB:
  /opt/CaptivePortal/data/visits.sqlite3
```

Analytics must:

- never mutate source DBs;
- never migrate source DBs;
- never change collector cadence;
- never change Visit matching/finalization;
- never call Omada for missing history.

Preferred path:

```text
Analytics services
→ source read services
→ source repositories read-only
```

Narrow read-only extensions are allowed only if current public read services cannot satisfy required bounded queries.

---

## 5. Derived analytics persistence decision

REV1 decision:

```text
NO derived analytics DB by default.
Use bounded query-on-read.
```

Reason:

- facts already have authoritative storage;
- product semantics are still being validated;
- premature rollups duplicate truth.

Known raw scale:

```text
300 active clients
× 1 observation/min
× 180 days
= 77,760,000 client rows
```

Therefore 01A MUST benchmark query-on-read.

If query-on-read cannot be bounded/performant:

```text
STOP before 01B.
Prepare separate Analytics Rollup Storage architecture.
```

No silent cache/materialized DB.

Any future derived storage requires:

```text
schema
rebuild
idempotency
retention
versioning
backfill
source-of-truth contract
failure recovery
```

---

## 6. Verified source fields

### 6.1 Registry / Snapshot

Registry identity/current profile includes:

```text
device_id
mac
first_seen_at
last_seen_at
last_site_id
last-known profile/context
snapshot_count
```

Snapshot includes:

```text
snapshot_id
device_id
auth_session_id
site_id
requested_mac
authorized_at
captured_at
auth_final_reason
portal context
client context
radio_id
channel
rssi
snr
traffic_down
traffic_up
uptime
active
auth_status
```

Important:

```text
Registry device identity is currently global-by-MAC.
Visits are Site-scoped.
```

Therefore `visitor_devices.last_*` is NOT automatically Site-specific truth.

### 6.2 Visit v2

```text
visit_id
site_id
client_mac
device_id
initial_snapshot_id
start_auth_session_id
start_auth_run_number
start_final_reason
started_at
closed_at
status
close_reason
close_time_source
start_ip
start_ssid
start_ap_mac
final_ip
final_ssid
final_ap_mac
reported_connected_seconds
reported_traffic_total_bytes
reported_traffic_up_bytes
reported_traffic_down_bytes
duration_seconds
offline_event_id
```

Authorization evidence:

```text
visit_id
auth_session_id
auth_run_number
authorization_attempt
authorized_at
final_reason
client_ip
portal_ssid
portal_ap_mac
portal_radio_id
```

Source event v2:

```text
event_id
event_type
site_id
client_mac
controller_event_at
received_at
client_ip
ssid
ap_mac
reported_connected_seconds
reported_traffic_total_bytes
processing_result
visit_id
reason
first_processed_at
processed_at
pending_until
```

Visit interval:

```text
closed = [started_at, closed_at)
open   = [started_at, +∞)
```

### 6.3 Client Observation v1

```text
cycle_id
observed_at
site_id
client_mac
source_inventory_complete
controller_client_id
name
hostname
system_name
device_type
connect_device_type
ip
ssid
ap_name
ap_mac
connect_type
signal_level
signal_rank
wifi_mode
radio_id
band
channel
rx_rate
tx_rate
rssi
snr
vid
uptime
last_seen_ms
auth_status
activity
wireless
power_save
blocked
guest
active
manager
traffic_down
traffic_up
down_packet
up_packet
```

### 6.4 AP Observation v1

```text
cycle_id
observed_at
site_id
ap_mac
partial
overview_ok
wired_uplink_ok
lan_traffic_ok
radios_ok
overview_observed_at
wired_observed_at
lan_observed_at
name
ip
model
firmware_version
wlan_id
cpu_util
mem_util
uptime_seconds
wired_rate_raw
wired_duplex_code
wired_up_bytes
wired_down_bytes
wired_up_packets
wired_down_packets
wired_activity_raw
wired_download_mbps
wired_upload_mbps
wired_download_rate_reason
wired_upload_rate_reason
lan_rx_bytes
lan_tx_bytes
lan_rx_packets
lan_tx_packets
lan_rx_drop_packets
lan_tx_drop_packets
lan_rx_error_packets
lan_tx_error_packets
lan_rx_mbps
lan_tx_mbps
lan_rx_rate_reason
lan_tx_rate_reason
```

### 6.5 AP Radio Observation v1

```text
radio_observed_at
site_id
ap_mac
band
radio_id
actual_channel_raw
actual_channel
frequency_mhz
channel_width
max_tx_rate
tx_power
wireless_mode
tx_util
rx_util
interference_util
busy_util
rx_bytes
tx_bytes
rx_packets
tx_packets
rx_drop_packets
tx_drop_packets
rx_error_packets
tx_error_packets
rx_retry_packets
tx_retry_packets
radio_rx_mbps
radio_tx_mbps
radio_rx_rate_reason
radio_tx_rate_reason
```

### 6.6 Observation cycle quality

```text
kind
site_id
state
complete
result
source_rows_reported
items_seen
items_stored
items_skipped
error_count
data_quality_warning_count
started_at
finished_at
abandoned_at
```

---

## 7. Time contract

Internal Analytics time:

```text
UTC
YYYY-MM-DDTHH:MM:SS.mmmZ
```

All Analytics ranges:

```text
[from_utc, to_utc)
```

Current Observation row read service uses inclusive `<= to_utc`. Analytics must normalize this without source migration and exclude an observation exactly at `to_utc`.

No double-counting adjacent buckets.

Display timezone is explicit metadata/parameter, never persistence.

---

## 8. Site / Multi-Site boundary

Near-term:

```text
Site-aware, single-tenant
```

Mandatory:

- `site_id` on every query;
- no cross-site aggregate v1;
- no hardcoded Site/SSID;
- no tenant_id;
- Tenant != Site;
- no cross-site MAC matching;
- global Registry last-context must not leak across Sites.

---

## 9. Accepted source-row policy

Default:

```text
quality_mode = strict_complete
```

Client fact:

```text
cycle.state = completed
cycle.complete = true
cycle.result = success
source_inventory_complete = true
```

AP fact:

```text
cycle.state = completed
cycle.complete = true
cycle.result = success
ap.partial = false
required section available
```

Radio fact requires accepted parent AP fact.

Diagnostic inclusion of partial data must return:

```text
quality_mode = diagnostic_including_partial
status = partial
```

---

## 10. Common immutable result envelope

```text
AnalyticsResult[T]
    status
    value
    quality
    provenance
```

Statuses:

```text
ok
partial
insufficient_data
unavailable
```

Rules:

```text
missing != 0
unavailable != 0
insufficient sample != 0
```

---

## 11. Provenance

Minimum:

```text
site_id
from_utc
to_utc
computed_at_utc
quality_mode
source_names
source_schema_versions
source_rows_examined
source_rows_accepted
source_rows_rejected
sample_size
missing_count
partial_cycle_count
failed_cycle_count
abandoned_cycle_count
filters
metric_version
```

Metric-specific:

```text
thresholds
gap_threshold_seconds
counter_max_gap_seconds
join_max_lag_seconds
display_timezone
```

---

## 12. 01A quality formulas

### Device link coverage

```text
linked_visits / eligible_visits
```

### Initial snapshot coverage

```text
visits_with_initial_snapshot / eligible_visits
```

### Authorization attachment coverage

```text
visits_with_authorization_count>=1 / eligible_visits
```

### Closed visit ratio

```text
closed / total
```

Return `open_count` separately. Open is not automatically invalid.

### Observation coverage in Visit

Window:

```text
closed: [started_at, closed_at)
open:   [started_at, evaluation_to)
```

Return:

```text
sample_count
first_observed_at
last_observed_at
edge_gap_start_seconds
edge_gap_end_seconds
max_inter_sample_gap_seconds
gap_count_over_threshold
```

For closed duration >0 and >=2 samples:

```text
observed_span_seconds = last - first
observed_span_ratio =
min(1, observed_span_seconds / visit.duration_seconds)
```

This is temporal span coverage, not RF probability.

### Complete cycle ratio

```text
complete_cycle_ratio =
count(completed AND complete=true)
/
count(completed)
```

Return success/partial/failed/shutdown/running/abandoned separately.

### Freshness

```text
evaluation_at - latest accepted source timestamp
```

No good/bad label in 01A.

Approved missing-field counts:

```text
client:
  ap_mac radio_id band channel rssi snr traffic_down traffic_up

AP/radio:
  cpu_util mem_util busy_util tx_util rx_util interference_util
  rx_retry_packets tx_retry_packets
  rx_error_packets tx_error_packets
  rx_drop_packets tx_drop_packets
  radio_rx_mbps radio_tx_mbps
```

---

## 13. 01B wireless formulas

### Percentiles

Use deterministic R-7:

```text
h=(n-1)p
j=floor(h)
g=h-j
Q=x[j]+g(x[j+1]-x[j])
```

Required:

```text
p10 p50 p90 p95
```

### Signal distribution

For RSSI/SNR:

```text
sample_count missing_count min max mean p10 p50 p90 p95
```

Threshold ratio only if explicitly configured:

```text
count(value < threshold) / non_null_count
```

Neutral label:

```text
below_configured_threshold_ratio
```

### Context distributions

Return both:

```text
observation_count
distinct_client_count
```

by:

```text
AP SSID band channel
```

### Concurrent observed clients

Per accepted complete client cycle:

```text
count(client rows)
```

Return min/mean/p50/p95/max across cycles.

### AP resource/radio

Distributions:

```text
cpu_util
mem_util
tx_util
rx_util
interference_util
busy_util
```

Bands separate by default.

### Persisted rates

Use only where matching `*_rate_reason == "ok"`:

```text
wired_download_mbps
wired_upload_mbps
lan_rx_mbps
lan_tx_mbps
radio_rx_mbps
radio_tx_mbps
```

Return exclusion counts by reason.

### Client counter rates

For same Site+MAC consecutive accepted samples:

```text
delta = current - previous
elapsed = t_current - t_previous

rate_mbps = delta * 8 / elapsed / 1_000_000
```

Valid only:

```text
delta >= 0
0 < elapsed <= max_gap
```

Reset/gap => NULL rate + reason.

### Retry/error/drop deltas

Cumulative counters are never summed directly.

For same Site+AP+band:

```text
delta = current - previous
```

Optional:

```text
events_per_1000_packets =
1000 * sum(valid event deltas) / sum(valid packet deltas)
```

only denominator >0.

### Client ↔ AP temporal join

```text
same Site
same AP
same band where available
AP/radio timestamp <= client timestamp
choose latest
lag <= configured max lag
```

Never future-match.

### Correlation

Pearson:

```text
r =
Σ((x-x̄)(y-ȳ))
/
sqrt(Σ(x-x̄)^2 * Σ(y-ȳ)^2)
```

Candidates:

```text
RSSI ↔ busy_util
SNR  ↔ busy_util
RSSI ↔ cpu_util
SNR  ↔ cpu_util
```

Requires min samples and nonzero variance. No causal conclusion.

---

## 14. 01C Visit formulas

Canonical entity:

```text
visit_id
```

### Visit counts

```text
total open closed
```

Trend population:

```text
from <= started_at < to
```

### Unique devices

```text
COUNT(DISTINCT device_id)
WHERE device_id IS NOT NULL
```

Return unlinked visits separately.

### Repeat devices

Within selected Site/window:

```text
device has >=2 Visits
repeat_ratio = repeat_device_count / unique_linked_devices
```

### New-to-Site device

```text
earliest Visit.started_at for same site_id + device_id
falls in query window
```

Do not use global Registry first_seen for Site newness.

### Duration

Closed Visits only:

```text
mean p50 p95 min max
```

Open Visits excluded.

### Authorization count

```text
COUNT(visit_authorizations rows per visit)
```

Return distribution.

### Closure

Closed only:

```text
close_reason distribution
close_time_source distribution
```

### Source-event quality

Site-scoped only:

```text
closed unmatched invalid pending_match
```

Null-site historical invalid events are not attributed to any Site.

### Context

Separate:

```text
start_ssid
final_ssid
start_ap_mac
final_ap_mac
```

Touched-context metrics are non-exclusive.

### Traffic

Keep separate:

```text
Visit reported traffic
Observation-derived counter delta
```

No hidden merge.

### Return interval

Same Site+device:

```text
next.started_at - previous.started_at
```

Requires minimum cohort sample.

---

## 15. Configuration

Safe defaults:

```text
ANALYTICS_FOUNDATION_ENABLED=false

ANALYTICS_DEFAULT_LIMIT=500
ANALYTICS_MAX_LIMIT=2000
ANALYTICS_MAX_QUERY_WINDOW_DAYS=31
ANALYTICS_MAX_QUERY_DURATION_SECONDS=10

ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS=180

ANALYTICS_WIRELESS_ENABLED=true
ANALYTICS_WIRELESS_MIN_SAMPLES=20
ANALYTICS_WIRELESS_MAX_WINDOW_DAYS=7
ANALYTICS_COUNTER_MAX_GAP_SECONDS=180
ANALYTICS_AP_JOIN_MAX_LAG_SECONDS=120
ANALYTICS_RSSI_THRESHOLD_DBM=
ANALYTICS_SNR_THRESHOLD_DB=

ANALYTICS_VISIT_ENABLED=true
ANALYTICS_VISIT_MIN_COHORT_SIZE=20
ANALYTICS_VISIT_MAX_WINDOW_DAYS=90
```

Empty signal thresholds mean “not configured”.

No production identifiers.

---

## 16. Performance/capacity gate

Benchmark:

```text
A: 30 clients, 2 AP, 1 day
B: 100 clients, 10 AP, 7 days
C: 300 clients, 30 AP, 7 days
```

Approx client rows:

```text
A:    43,200
B: 1,008,000
C: 3,024,000
```

Measure:

```text
elapsed
rows examined
rows transferred to Python
peak materialized sample count
query plan/index usage
```

Required query classes:

1. cycle quality;
2. single Visit + observation coverage;
3. RSSI/SNR candidate scan;
4. AP/radio utilization;
5. Visit/device counts;
6. repeat-device candidate.

Hard stop before 01B if a normal 24h/100-client quality query requires:

```text
unbounded full-table scan
OR >250,000 Python row objects materialized at once
```

Prefer aggregate SQL/streaming.

---

## 17. Security/privacy

Allowed internal entity identifiers only for explicit entity query:

```text
visit_id device_id client MAC AP MAC
```

Aggregate outputs/telemetry must not contain:

```text
client MAC lists
device_id lists
IP/hostname lists
raw snapshot JSON
auth_context_json
client_json
raw_controller_snapshot_json
secrets/tokens/cookies/passwords
```

Language:

```text
unique devices != unique people
```

---

## 18. Product / Observability boundary

Authoritative product path:

```text
source SQLite
→ source read services
→ Analytics services
→ future Web/API
```

Forbidden:

```text
Analytics → Grafana/Loki as source of product truth
Admin Console → Grafana API → metrics
```

Grafana is internal validation/engineering only.

---

## 19. Internal-only vs potential Web contracts

Internal-only now:

```text
source health
cycle quality
field-missing diagnostics
reset/gap diagnostics
unmatched/invalid diagnostics
join coverage
correlations
performance measurements
```

Potential future Web contracts after Web/security review:

```text
Visit counts
unique/repeat device metrics
duration
AP/SSID/band distributions
RSSI/SNR aggregate distributions
radio utilization
traffic-rate distributions
```

No Web routes in Analytics Foundation.

---

## 20. Telemetry

Summary only:

```text
analytics.query_completed
analytics.query_insufficient_data
analytics.query_unavailable
analytics.source_quality_warning
analytics.performance_budget_exceeded
```

Safe:

```text
metric site_id duration_ms sample_size accepted_rows rejected_rows
status reason quality_mode
```

No raw sample arrays.

---

## 21. Fail-open / runtime

Analytics is downstream.

Failure must never affect:

```text
Auth CAPPORT Cleaner Snapshot Registry Observation Visit
```

No periodic analytics worker in REV1.

No thread at import.

No production startup integration until separate task.

---

## 22. Common tests

Every execution stage includes:

- formula determinism;
- complete/partial/missing fixtures;
- Site isolation;
- half-open boundaries;
- UTC/timezone;
- limit/cursor;
- reset/gap;
- open/closed Visit;
- no Omada calls;
- source read-only;
- privacy/security markers;
- performance fixtures;
- source regressions;
- full pytest;
- compileall;
- diff-check.

No new schema migration without separate review.

---

## 23. Regression invariants

Every PR must explicitly report:

```text
OmadaProvider changed: NO
Observation schema changed: NO
Observation collector behavior changed: NO
Visit schema changed: NO
Visit finalization changed: NO
Registry schema changed: NO
Snapshot changed: NO
Auth/CAPPORT semantics changed: NO
Production activation: NO
```

---

## 24. Stop conditions

Stop if:

- implementation baseline materially differs;
- Site isolation cannot be guaranteed;
- Omada is needed to fill historical gaps;
- source write/migration is required;
- query needs unbounded materialization;
- derived storage becomes necessary;
- new external dependency is required;
- Registry last-context would leak cross-Site state;
- metric semantics are ambiguous;
- source fields cannot distinguish requested metric;
- full regression failure cannot be classified.

---

## 25. Repository actions

Before approval:

```text
NO implementation branch
NO code changes
NO commit
NO push
NO PR
NO deploy
```

First possible implementation command:

```text
TASK Analytics 01A утверждено, начинать PR A
```

---

## 26. Handoff format

Each stage returns:

```text
BASELINE
IMPLEMENTED / NOT IMPLEMENTED
FILES
SOURCE CONTRACTS
QUERY CONTRACTS
METRIC FORMULAS
QUALITY / PROVENANCE
PERFORMANCE
SECURITY / PRIVACY
TARGETED TESTS
REGRESSIONS
FULL GATE
RISKS
REPOSITORY ACTIONS
NEXT OWNER ACTION
```

---

## 27. Review gate

REV1 is ready for Tech Lead/owner review only.

Implementation authorization is not granted.
