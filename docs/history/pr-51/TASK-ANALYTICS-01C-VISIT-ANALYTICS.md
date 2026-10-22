# TASK-ANALYTICS-01C — Visit Analytics

**Project:** CaptivPortal  
**Parent:** `TASK-ANALYTICS-FOUNDATION-01 — REV1`  
**Status:** BLOCKED BY 01A + 01B  
**Architecture baseline:** `main@fe797593fb12b9cb9f81bdb22e1c14f2d08b037e`  
**Implementation baseline:** MUST be pinned to exact accepted 01B merge SHA before owner approval  
**Recommended branch:** `feature/visit-analytics-v1`  
**Production activation:** separate future task

---

## 1. Goal

Implement Site-aware Visit/Visitor analytics using:

```text
Visit Lifecycle schema v2
Visitor Registry identity/linkage
01A quality/read contracts
01B wireless metrics
Observation history
```

Canonical entity:

```text
visit_id
```

A successful AuthSession is not automatically a physical Visit.

---

## 2. Prerequisites

Before owner approval:

```text
01A merged + accepted
01B merged + accepted
exact implementation baseline pinned
query-on-read performance still accepted
```

Run pre-change full Linux gate.

If Visit/source contracts changed, return architecture impact.

---

## 3. Allowed files

```text
app/analytics/visits.py
app/analytics/models.py
app/analytics/formulas.py
app/analytics/read_service.py
app/analytics/source_gateway.py
app/analytics/config.py
app/analytics/telemetry.py

tests/analytics/test_visit_analytics*.py
tests/analytics/** shared fixtures
```

Narrow read-only additions to Visit read boundary only if required for bounded set-based aggregate performance.

---

## 4. Forbidden

Do not change:

```text
Visit schema
Visit start
Visit finalization
Visit reader/runtime
Observation schema/collectors
Registry schema/worker
Snapshot
Omada
Auth/CAPPORT
Cleaner
customer routes/UI
Grafana/Alloy
production
```

No reconstructed Visit.

---

## 5. Configuration

```text
ANALYTICS_VISIT_ENABLED=true
ANALYTICS_VISIT_MIN_COHORT_SIZE=20
ANALYTICS_VISIT_MAX_WINDOW_DAYS=90
```

Master flag remains false until separate activation.

No hardcoded Site timezone.

Methods may accept:

```text
display_timezone="UTC"
```

Use stdlib:

```text
zoneinfo.ZoneInfo
```

If no authoritative Site timezone application source exists, default UTC and return that fact in provenance.

---

## 6. Time semantics

Storage/computation basis:

```text
UTC
```

Visit lifecycle interval:

```text
[started_at, closed_at)
```

Visit trend/start cohort:

```text
from_utc <= started_at < to_utc
```

This differs intentionally from lifecycle-overlap lookup.

Every output states its population semantics.

---

## 7. Bucketing

Visit-start time series can bucket by:

```text
hour
day
week
```

REV1 bounds:

```text
hour: query window <=7 days
day:  query window <=90 days
week: allowed within 90-day max
```

Bucket projection may use explicit `display_timezone`.

Adjacent bucket ranges are half-open.

DST uses `zoneinfo` behavior; tests required.

---

## 8. Core immutable outputs

Conceptual:

```text
VisitCountSummary
VisitTimeSeries
DeviceCountSummary
RepeatDeviceSummary
NewToSiteDeviceSummary
VisitDurationSummary
VisitAuthorizationSummary
VisitClosureSummary
VisitSourceEventQuality
VisitContextDistribution
VisitContextTransition
VisitObservationCoverageSummary
VisitWirelessSummary
VisitTrafficSummary
ReturnIntervalSummary
VisitAnalyticsBundle
```

Every metric uses 01A result/provenance envelope.

---

## 9. Visit count population

### Trend/count metrics

Use:

```text
Visit start cohort:
from <= started_at < to
```

Return:

```text
total_visit_count
open_visit_count
closed_visit_count
```

An open Visit started in the range belongs to count population but does not get final duration.

### Overlap metrics

Only explicitly named context/coverage methods may use:

```text
Visit interval overlaps [from,to)
```

Never mix these two populations under the same metric name.

---

## 10. Visit time series

Bucket by `started_at`.

Return:

```text
bucket_start
bucket_end
count
display_timezone
```

A successful source query with no Visit in a bucket returns `count=0`.

Unavailable source does not produce synthetic zero series.

---

## 11. Unique devices

Within Visit start cohort:

```text
unique_linked_devices =
COUNT(DISTINCT device_id)
WHERE device_id IS NOT NULL
```

Return also:

```text
linked_visit_count
unlinked_visit_count
```

Naming:

```text
unique devices
```

Never:

```text
unique people
```

---

## 12. Repeat devices

Within requested Site and start cohort:

```text
visits_per_device =
count Visits grouped by non-null device_id
```

Repeat:

```text
device has >=2 Visit starts in selected window
```

Return:

```text
unique_linked_devices
repeat_device_count
repeat_device_ratio
```

Formula:

```text
repeat_device_ratio =
repeat_device_count / unique_linked_devices
```

Zero denominator => NULL/insufficient.

This metric means repeat within selected window, not lifetime returning status.

---

## 13. New-to-Site devices

Definition:

```text
device is new_to_site
iff earliest Visit.started_at
for same site_id + device_id
falls inside selected window
```

This requires historical lookup before `from_utc`.

Do not use:

```text
Visitor Registry global first_seen_at
```

for Site newness.

Return:

```text
unique_linked_devices_in_window
new_to_site_device_count
known_before_window_device_count
unlinked_visit_count
```

---

## 14. Duration distribution

Only:

```text
status=closed
duration_seconds IS NOT NULL
started_at in cohort
```

Return:

```text
sample_count
excluded_open_count
minimum
maximum
mean
p50
p95
```

Use shared R-7 percentile.

Open Visit has no invented final duration.

No clamp/guess.

---

## 15. Authorization count per Visit

For each Visit:

```text
authorization_count =
COUNT(visit_authorizations rows)
```

Return distribution:

```text
sample_count
mean
p50
p95
max
```

Additional:

```text
visits_with_exactly_one_authorization
visits_with_multiple_authorizations
visits_with_zero_authorization
```

A zero count is a quality anomaly, not a reason to reconstruct evidence.

---

## 16. Closure distribution

Closed Visits only:

```text
close_reason
close_time_source
```

Return:

```text
reason -> count
time_source -> count
```

Controller-reported duration and lifecycle duration remain separate.

Optional internal diagnostic:

```text
duration_difference_seconds =
reported_connected_seconds - duration_seconds
```

only when both non-null.

No replacement of lifecycle duration.

---

## 17. Source-event quality

For:

```text
visit_source_events.site_id == requested site_id
```

return:

```text
closed
unmatched
invalid
pending_match
```

and reason distribution.

Important:

```text
historical site_unresolved event with site_id=NULL
```

cannot be attributed to requested Site.

Such events stay in operational/internal global evidence, not Site product metric.

No guessing by MAC/site name.

---

## 18. Visits by SSID

Separate distributions:

```text
start_ssid
final_ssid
```

Do not collapse them into one exclusive “Visit SSID”.

NULL context count returned separately.

Optional touched-context metric using authorization evidence:

```text
number of Visits that had at least one authorization evidence
with portal_ssid = group
```

A Visit may contribute to multiple touched SSIDs.

Output explicitly:

```text
grouping_is_non_exclusive=true
```

---

## 19. Visits by AP

Separate:

```text
start_ap_mac
final_ap_mac
```

Touched AP evidence uses:

```text
visit_authorizations.portal_ap_mac
```

and is non-exclusive.

AP transition is not automatically bad.

---

## 20. Start/final transitions

If both non-null:

```text
ssid_changed = start_ssid != final_ssid
ap_changed = start_ap_mac != final_ap_mac
```

For each context:

```text
comparable_count
changed_count
unchanged_count
missing_side_count
```

Interpretation:

- AP change may be roaming;
- SSID change is context transition, not automatic fault.

---

## 21. Observation coverage per Visit

Reuse exact 01A coverage.

Do not reimplement.

For start-cohort Visit set return:

```text
visit_count
visits_with_zero_client_observations
visits_with_one_or_more_client_observations
sample_count distribution
observed_span_ratio distribution where defined
max_gap distribution where defined
```

No per-Visit N+1 for large cohort.

---

## 22. No N+1 across Visits

Forbidden:

```text
for every Visit in 500-row page:
    Observation query
```

Required:

```text
bounded Visit cohort
→ group by Site/MAC/time windows
→ batch/set-based source retrieval
→ bounded composition
```

For a single explicit Visit detail query, a fixed small number of source calls is allowed.

Use query-spy tests.

---

## 23. Wireless inside Visit

Reuse 01B:

```text
Visit(site_id, client_mac, started_at, closed/evaluation_to)
→ 01B filter/window
```

Conceptual:

```text
get_visit_wireless_summary(site_id, visit_id)
```

Must return:

```text
Visit observation coverage
RSSI/SNR aggregate
AP/radio evidence where matched
quality/provenance
```

No duplicate percentile/correlation implementation.

---

## 24. Visit traffic — source separation

### Visit finalization source

Use:

```text
reported_traffic_total_bytes
reported_traffic_up_bytes
reported_traffic_down_bytes
```

Current schema may have total with up/down NULL.

NULL stays NULL.

### Observation source

Use 01B accepted client counter delta logic.

Return independently:

```text
reported_total_bytes
reported_up_bytes
reported_down_bytes

observed_counter_delta_down_bytes
observed_counter_delta_up_bytes
observed_delta_coverage
```

No hidden merge into `traffic_bytes`.

---

## 25. Traffic reconciliation diagnostic

Internal only.

If comparable:

```text
difference =
observed_total - reported_total
```

Optional ratio only if reported_total >0.

Return provenance and coverage.

Do not treat discrepancy automatically as defect.

---

## 26. Return intervals

For same:

```text
site_id + device_id
```

sort Visit starts.

Intervals:

```text
next.started_at - previous.started_at
```

Only non-negative chronological intervals.

Return:

```text
sample_count
minimum
maximum
mean
p50
p95
```

Require:

```text
sample_count >= ANALYTICS_VISIT_MIN_COHORT_SIZE
```

Else insufficient.

---

## 27. General cohort analytics boundary

General retention/cohort system is NOT implemented in 01C.

Any future cohort metric must define:

```text
entry event
Site
time basis
follow-up window
censoring
minimum sample
```

Potential future:

```text
return next day
return within 7 days
```

excluded from current scope unless added by reviewed amendment.

---

## 28. Query API

Conceptual:

```text
get_visit_counts(
    site_id, from_utc, to_utc
)

get_visit_time_series(
    site_id, from_utc, to_utc,
    granularity,
    display_timezone="UTC",
)

get_device_counts(...)
get_repeat_devices(...)
get_new_to_site_devices(...)
get_duration_distribution(...)
get_authorization_distribution(...)
get_closure_distribution(...)
get_source_event_quality(...)
get_context_distributions(...)
get_context_transition(...)
get_observation_coverage_summary(...)
get_visit_wireless_summary(...)
get_visit_traffic_summary(...)
get_return_intervals(...)
get_visit_analytics_bundle(...)
```

All require `site_id`.

---

## 29. Bundled Visit Analytics

Allowed bundle:

```text
Visit counts
device counts
repeat/new-to-site
duration
authorization distribution
closure
start/final context
observation coverage
wireless summary
traffic summary
quality/provenance
```

Do not silently include operational null-site invalid history.

---

## 30. Bounds

```text
ANALYTICS_VISIT_MAX_WINDOW_DAYS=90
```

No longer query in REV1.

Detail pages use:

```text
default 500
hard 2000
```

Master query deadline applies.

Long source-event scans must be SQL aggregated, not object-loaded.

---

## 31. Display timezone

If caller requests timezone:

- validate IANA name using `ZoneInfo`;
- store output bucket boundaries with explicit offset or UTC + label;
- computation source timestamps remain UTC.

No hardcode `Asia/Baku` in module.

Tests:

- normal day;
- DST forward;
- DST backward.

If timezone invalid => validation error, not UTC fallback silently.

---

## 32. Registry identity

Repeat/new metrics use `device_id`.

Never use long-term:

```text
IP
hostname
display name
```

Do not call a device a person.

Same device_id across Sites is isolated because every Visit query filters Site.

---

## 33. Data quality

Every result returns relevant:

```text
linked_visit_count
unlinked_visit_count
open/closed counts
sample count
missing fields
observation coverage
quality status
metric version
population semantics
timezone
```

Exclusions are explicit.

---

## 34. Internal vs future Web

Potential future product contract after Web/security review:

```text
Visits over time
unique devices
repeat devices
new-to-Site devices
duration
Visits by SSID/AP
traffic totals
```

Internal-only initially:

```text
source-event invalid/unmatched quality
linkage anomalies
observation coverage diagnostics
reported-vs-observed traffic reconciliation
wireless join diagnostics
```

No route/API here.

---

## 35. Security/privacy

Aggregate output:

- no MAC list;
- no device ID list;
- no IP/hostname list;
- no raw source events;
- no raw snapshot JSON;
- no secret.

Single Visit internal detail may include visit_id/device_id/client_mac where needed.

Telemetry does not include identifier lists.

---

## 36. Multi-Site

Every query requires Site.

No cross-Site repeat/new-device metric.

New-to-Site specifically derives earliest Visit in the requested Site.

Tenant not introduced.

---

## 37. Product/observability

Product truth path:

```text
Visit/Observation/Registry
→ Analytics
→ future Web Foundation
```

No Grafana/Loki source query.

Grafana may later visualize aggregate output internally.

---

## 38. Telemetry

Summary:

```text
analytics.visit_query_completed
analytics.visit_insufficient_data
analytics.visit_query_unavailable
```

Safe:

```text
site_id
metric
duration_ms
sample_size
status
reason
```

No device/MAC arrays.

---

## 39. Tests — Visit population

- start-cohort exact boundary;
- Visit started exactly from included;
- exactly to excluded;
- overlap semantics separate;
- open/closed count;
- no synthetic zero on unavailable.

---

## 40. Tests — devices

- unique linked devices;
- unlinked visits separate;
- repeat >=2;
- repeat ratio denominator;
- zero linked denominator;
- same device two Sites isolated;
- new-to-Site earliest Visit;
- Registry global first_seen ignored for Site-newness.

---

## 41. Tests — duration/auth

- closed only;
- open excluded;
- NULL excluded;
- R-7 p50/p95;
- one/multiple/zero authorization evidence;
- no AuthSession-as-Visit counting.

---

## 42. Tests — closure/events

- close reason;
- close_time_source;
- controller vs lifecycle duration separate;
- site-scoped source events;
- null-site invalid excluded;
- pending separate;
- unmatched separate;
- invalid not mixed into closed.

---

## 43. Tests — context

- start/final SSID separate;
- start/final AP separate;
- missing side;
- AP change not labeled fault;
- touched SSID non-exclusive;
- touched AP non-exclusive.

---

## 44. Tests — Observation/wireless/traffic

- 01A coverage reused;
- 01B formula reused;
- no N+1;
- Visit window half-open;
- open Visit evaluation window;
- reported traffic total only with null directions;
- observed delta separate;
- reconciliation diagnostic missing side.

---

## 45. Tests — return/timezone

- ordered intervals;
- min cohort;
- Site isolation;
- UTC;
- explicit display timezone;
- invalid timezone;
- DST forward;
- DST backward;
- hour/day/week bucket boundaries.

---

## 46. Tests — safety/performance

- 90d max;
- limit/deadline;
- read-only;
- no Omada;
- no schema writes;
- privacy markers;
- query spy prevents N+1;
- representative Visit performance dataset.

---

## 47. Regression/full gate

Run:

```text
tests/analytics/**
tests/visit_lifecycle/**
tests/observations/**
tests/visitor_registry/**
current Auth/CAPPORT regressions
```

Then:

```bash
python -m pytest -q -rs

PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc   python -m compileall -q app

git diff --check
```

Exact result counts required.

---

## 48. Acceptance

PASS only if:

- Site isolation;
- start cohort semantics explicit;
- overlap only where explicitly named;
- open Visit duration not invented;
- stable device_id used;
- no person inference;
- Site newness derived from same-Site Visit history;
- wireless formulas reused;
- traffic sources separate;
- invalid/unmatched not mixed with closed Visits;
- no N+1;
- bounded 90d;
- timezone explicit;
- read-only/no Omada;
- privacy clean;
- regressions/full gate accepted;
- production unchanged.

---

## 49. Stop conditions

Stop if:

- 01A/01B not accepted;
- exact baseline not pinned;
- Visit schema/read contracts materially changed;
- Site new-device semantics cannot be derived safely;
- null-site invalid would require attribution guess;
- query requires source migration;
- 90d query-on-read cannot be bounded;
- derived storage becomes required;
- new dependency required.

---

## 50. Repository actions

No implementation until owner approval.

After exact baseline pin:

```text
TASK Analytics 01C утверждено, начинать PR C
```

Branch:

```text
feature/visit-analytics-v1
```

Commit/push/PR/merge/deploy remain separately controlled.

---

## 51. Handoff

Return:

```text
BASELINE
IMPLEMENTED
NOT IMPLEMENTED
VISIT POPULATION SEMANTICS
FILES
METRICS/FORMULAS
SOURCE FIELDS
SITE IDENTITY
QUALITY/PROVENANCE
PERFORMANCE
PRIVACY
TARGETED TESTS
REGRESSIONS
FULL GATE
RISKS
REPOSITORY ACTIONS
WEB FOUNDATION READINESS
```
