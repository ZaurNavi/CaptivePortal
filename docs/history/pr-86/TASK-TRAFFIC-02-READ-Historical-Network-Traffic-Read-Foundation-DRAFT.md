# TASK-TRAFFIC-02-READ — Historical Network Traffic Read Foundation — DRAFT

**Project:** CaptivPortal  
**Area:** Admin Console → Traffic  
**Parent:** `CaptivPortal — Генеральная дорожная карта раздела Admin Console → Traffic — FINAL v1`  
**Predecessors:** `TASK-TRAFFIC-00`, `TASK-TRAFFIC-01`  
**Type:** architecture / backend read-foundation specification  
**Status:** `DRAFT — FOR OWNER + TECH LEAD ARCHITECTURAL REVIEW`  
**Implementation authorization:** `NOT GRANTED`  
**Branch / code / commit / push / PR / merge:** `NOT AUTHORIZED`  
**Production activation:** `NOT AUTHORIZED / NOT PART OF THIS DRAFT`  
**Prepared:** 2026-08-29

---

# 0. Executive decision

`TRAFFIC-02-READ` creates the canonical read-layer owner for:

```text
Historical Network Traffic
```

The proposed v1 source remains:

```text
Observation persisted AP history
```

Canonical architecture:

```text
Omada AP traffic primitives
        ↓
existing Observation acquisition
        ↓
observations.sqlite3
        ↓
AnalyticsSourceGateway
        ↓
HistoricalTrafficReadService
        ↓
future TRAFFIC-02 / 03 / 04 / 05 / 06
```

This DRAFT proposes:

```text
NO new collector
NO new Omada polling
NO new Traffic DB
NO schema migration
NO derived rollup storage
NO Admin/browser → Omada
NO Traffic UI/API in TRAFFIC-02-READ
```

Native Omada historical endpoints remain:

```text
validation / reference sources
```

not product authorities.

---

# 1. Verified current repository baseline

Current GitHub `main` was rechecked before preparation.

```text
main =
8f3ad59771f72c49834b1012963de6d94b9e0d18

tree =
2ef8bf264a008259242cde0778d0ebd20fa94b9e
```

Current main is:

```text
Merge PR #84
TASK-TRAFFIC-01 — Current Network Throughput
```

Owner report states production is deployed on the same SHA/tree and
`TRAFFIC-00 + TRAFFIC-01` are production-active.

Repository truth used by this DRAFT is the GitHub main above.

If `origin/main` changes before FINAL or implementation authorization:

```text
re-fetch
re-pin SHA/tree
perform impact review
```

Mandatory impact review if newer main touches:

```text
app/analytics/**
app/observations/**
app/admin_web/**
run.py
app/config.py
app/settings.py
```

---

# 2. Current accepted Traffic state

Current project state:

```text
TRAFFIC-00
DONE / MERGED

TRAFFIC-01
DONE / MERGED
```

`TRAFFIC-01` now exposes:

```text
Current Network Throughput
Download Now
Upload Now
Total Now
Source
Freshness
Coverage
```

using the existing:

```text
CurrentTrafficReadService
```

`TRAFFIC-02-READ` MUST NOT change current Traffic semantics.

---

# 3. Goal

Create a Site-aware, bounded, read-only historical Network Traffic contract
over already persisted AP Observation evidence.

The foundation must allow later tasks to build:

```text
TRAFFIC-02 — Network Traffic History
TRAFFIC-03 — Period Statistics
TRAFFIC-04 — Peak Load Period
TRAFFIC-05 — Traffic by AP
TRAFFIC-06 — AP Traffic Share
TRAFFIC-10 — 30-day Enablement
TRAFFIC-11 — Heatmap
TRAFFIC-12 — Period Comparison
```

without each task inventing its own historical traffic algorithm.

Permanent:

```text
one historical Network Traffic semantic owner
```

---

# 4. Domain boundary

This TASK belongs only to:

```text
NETWORK TRAFFIC
```

Meaning:

```text
AP / network throughput evidence
unit = Mbps
```

It does NOT mean:

```text
WAN Traffic
Internet Traffic
billing traffic
guest-session traffic
completed-session volume
SSID Traffic
Zefer_Parki Traffic
```

`Guest Session Traffic` remains a separate later domain based on Visit Lifecycle.

Never combine the two as one universal Traffic metric.

---

# 5. Canonical persisted source already exists

Current repository persists historical AP dynamic facts in:

```text
observations.sqlite3
```

Relevant tables:

```text
observation_cycles
ap_observations
ap_radio_observations
```

For Network Traffic v1, canonical rows are:

```text
observation_cycles
+
ap_observations
```

Radio rows are NOT part of Site Network Traffic total v1.

---

# 6. Relevant persisted AP facts

Current `ap_observations` already persists:

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

wired_observed_at
lan_observed_at

wired_up_bytes
wired_down_bytes
wired_activity_raw

wired_download_mbps
wired_upload_mbps
wired_download_rate_reason
wired_upload_rate_reason

lan_rx_bytes
lan_tx_bytes
lan_rx_mbps
lan_tx_mbps
lan_rx_rate_reason
lan_tx_rate_reason
```

Therefore persisted history already contains both:

```text
raw cumulative counters
+
derived directional rate facts
```

---

# 7. Existing derived-rate ownership

Observation acquisition already calculates persisted AP rate fields.

Current rate formula is:

```text
delta_bytes * 8
/
elapsed_seconds
/
1_000_000
=
Mbps
```

Allowed reasons:

```text
ok
no_baseline
counter_reset
gap_too_large
invalid_elapsed
source_unavailable
```

Rate is numeric only when:

```text
reason = ok
```

Historical read MUST reuse these persisted derived rate facts.

It MUST NOT silently create a second rate formula.

---

# 8. Direction semantics

Canonical mappings remain:

```text
wired Download
=
wired_download_mbps

wired Upload
=
wired_upload_mbps

lan Download
=
lan_rx_mbps

lan Upload
=
lan_tx_mbps
```

`wired_activity_raw` remains diagnostic/cross-check only.

Radio throughput remains excluded from Site Network Traffic total.

---

# 9. Existing historical read primitives

Current repository already provides:

```text
ObservationReadService.analytics_read_connection()
```

which opens the existing Observation repository through the read-only boundary.

Current `AnalyticsSourceGateway` already performs:

```text
read-only SQLite composition
query deadline enforcement
progress-handler cancellation
schema boundary validation
Site-scoped queries
stored rate distributions
cycle quality queries
```

Therefore preferred implementation is a narrow extension of:

```text
AnalyticsSourceGateway
```

not a new SQLite owner.

---

# 10. Why existing Wireless Analytics is not the new owner

Current `WirelessAnalyticsService.get_throughput_distribution(...)`
can query persisted:

```text
wired_download_mbps
wired_upload_mbps
lan_rx_mbps
lan_tx_mbps
radio_rx_mbps
radio_tx_mbps
```

but it returns:

```text
distribution statistics
```

not:

```text
canonical Site historical time series
```

It also currently belongs to the generic Wireless Analytics contract.

Therefore:

```text
WirelessAnalyticsService
!=
Historical Network Traffic semantic owner
```

Do not stretch `get_throughput_distribution()` into a chart timeline contract.

---

# 11. Existing 7-day / 31-day ceilings are NOT source retention

Current Analytics configuration contains:

```text
ANALYTICS_WIRELESS_MAX_WINDOW_DAYS = 7
ANALYTICS_MAX_QUERY_WINDOW_DAYS = 31
```

These are existing Analytics query-contract limits.

They do NOT prove:

```text
Observation retention = 7 days
or
Observation retention = 31 days
```

`TRAFFIC-02-READ` MUST NOT inherit those ceilings merely because it lives in
`app/analytics`.

---

# 12. Observation retention facts

Current Observation configuration default:

```text
OBSERVATION_DYNAMIC_RETENTION_DAYS = 180
```

The dynamic retention covers:

```text
client
ap_dynamic
```

Cleanup deletes non-running dynamic cycles older than the configured cutoff.

Important:

```text
repository default 180 days
!=
proof that production currently has 180 days of data
```

Actual available history can be shorter because:

```text
collection started later
cleanup already ran
production config may override default
historical gaps may exist
```

Therefore read results MUST expose actual persisted coverage boundaries.

---

# 13. No artificial calendar-day ceiling — DRAFT decision

`HistoricalTrafficReadService` v1 MUST NOT define:

```text
MAX_WINDOW_DAYS = 7
MAX_WINDOW_DAYS = 31
MAX_WINDOW_DAYS = 30
```

solely for UI convenience.

Allowed bounds are:

```text
actual persisted coverage
query deadline
bounded output point count
SQLite/performance budget
```

Canonical principle:

```text
range capability
!=
UI range exposure
```

Thus the backend may technically read a 30-day or longer range while:

```text
TRAFFIC-02 UI v1
```

still exposes only:

```text
24h
7d
```

until later product tasks approve additional selectors.

---

# 14. TRAFFIC-10 relationship

`TRAFFIC-10 — 30-day Enablement` remains meaningful.

It controls:

```text
product/UI exposure
benchmark acceptance
browser/chart payload acceptance
```

It does NOT need the historical read service to be structurally incapable of
reading 30 days.

Canonical:

```text
read capability
!=
product option enabled
```

---

# 15. New semantic owner

Preferred new service:

```text
app/analytics/historical_traffic.py

HistoricalTrafficReadService
```

Preferred runtime exposure:

```text
AnalyticsRuntime.historical_traffic_service
```

The service is:

```text
read-only
Site-scoped
demand-only
no background thread
no startup query
no write path
no Omada dependency
```

---

# 16. Runtime isolation

`HistoricalTrafficReadService` is optional/additive.

Construction failure MUST NOT make unavailable:

```text
Analytics quality service
Wireless Analytics
Visit Analytics
CurrentTrafficReadService
HomeActivityReadService
Admin Web
Home
Traffic Current
Captive Portal
```

Expected:

```text
historical_traffic_service = None
```

with existing Analytics runtime health unchanged.

This mirrors the accepted optional Current Traffic service pattern.

---

# 17. No new feature flag in READ foundation

DRAFT recommendation:

```text
NO new ANALYTICS_HISTORICAL_TRAFFIC_ENABLED
NO new WEB_ADMIN_TRAFFIC_HISTORY_ENABLED
```

Reason:

`TRAFFIC-02-READ` performs no request unless called.

It has:

```text
no worker
no timer
no polling
no startup read
```

Future product exposure remains controlled by:

```text
WEB_ADMIN_TRAFFIC_ENABLED
```

at the Admin boundary.

A subordinate feature flag may be introduced later only if operational need is
proven.

---

# 18. Canonical service method — DRAFT

Preferred first public read contract:

```python
get_site_history(
    site_id,
    *,
    from_utc,
    to_utc,
    evaluated_at_utc=None,
    bucket_seconds=None,
    deadline=None,
)
```

No source-family parameter.

No Omada parameter.

No SSID parameter.

No guest-session parameter.

---

# 19. Site semantics

Every query requires exact:

```text
site_id
```

No:

```text
cross-Site aggregate
tenant_id
hidden default Site
cross-Site AP merge
```

Current model remains:

```text
Site-aware
single-tenant
```

---

# 20. Canonical time range

All ranges:

```text
[from_utc, to_utc)
```

Required:

```text
from_utc < to_utc
```

Internal format:

```text
UTC
YYYY-MM-DDTHH:MM:SS.mmmZ
```

An observation exactly at:

```text
to_utc
```

belongs to the next range and is excluded.

No hidden `-1ms` adjustment.

---

# 21. Evaluation time

If omitted:

```text
evaluated_at_utc = current UTC
```

Required:

```text
to_utc <= evaluated_at_utc
```

Future ranges are invalid.

A historical read must not silently fill future time with zero.

---

# 22. Timezone semantics

Persistence and bucket membership are UTC.

V1 fixed-duration buckets are:

```text
anchored at from_utc
```

Timezone is presentation metadata only.

Example:

```text
from_utc = 2026-08-28T13:00:00.000Z
bucket = 300 seconds

bucket 0:
[13:00, 13:05)

bucket 1:
[13:05, 13:10)
```

Changing display timezone does NOT move a sample between buckets.

This avoids DST ambiguity.

---

# 23. Calendar-local buckets are out of scope

`TRAFFIC-02-READ v1` does NOT implement:

```text
Site-local midnight buckets
weekday/hour heatmap buckets
DST-aware calendar days
calendar months
```

Those belong to later tasks such as:

```text
TRAFFIC-11
```

and must still consume the same historical source owner.

---

# 24. Bounded bucket count — DRAFT proposal

Proposed constant:

```text
MAX_BUCKETS = 720
```

This is:

```text
an output cardinality bound
```

not:

```text
a calendar-day ceiling
```

The purpose is to prevent:

```text
raw 30-second history → browser-scale payload
```

and to keep future Admin serialization bounded.

---

# 25. Automatic granularity — DRAFT proposal

If caller does not specify a bucket size, choose the smallest supported bucket
that keeps:

```text
bucket_count <= 720
```

Proposed fixed-duration ladder:

```text
5 min   = 300 s
15 min  = 900 s
1 hour  = 3600 s
6 hour  = 21600 s
1 day   = 86400 s
7 day   = 604800 s
30 day  = 2592000 s
```

If an even longer range exceeds 720 buckets at the final fixed step:

```text
compute a larger whole-day bucket size
```

rather than reject merely because a day ceiling was reached.

---

# 26. Resulting common ranges

With the DRAFT policy:

```text
24h
→ 5-minute buckets
→ 288 points

7d
→ 15-minute buckets
→ 672 points

30d
→ 1-hour buckets
→ 720 points

180d
→ 6-hour buckets
→ 720 points
```

This is a proposed backend resolution contract.

It is NOT tied to Omada native adaptive granularity.

---

# 27. Explicit bucket request

If an internal trusted caller supplies:

```text
bucket_seconds
```

it must satisfy:

```text
positive integer
fixed-duration bucket
bucket_count <= MAX_BUCKETS
```

Future Admin browser MUST NOT be allowed to request arbitrary unbounded raw
resolution directly.

`TRAFFIC-02` may expose only named product ranges and let the server resolve
bucket size.

---

# 28. Historical semantic unit

Every numeric point is:

```text
Mbps
```

It is historical:

```text
Network Throughput
```

not:

```text
traffic volume
```

Do NOT label the value as:

```text
MB
GB
data transferred
Internet usage
```

---

# 29. Canonical source-cycle acceptance

A canonical Site historical source cycle is:

```text
kind = ap_dynamic
state = completed
complete = true
result = success
```

The cycle must also pass integrity checks.

---

# 30. Cycle integrity

For a claimed complete-success cycle require:

```text
finished_at != null
finished_at >= started_at

items_seen = items_stored
items_skipped = 0
error_count = 0
data_quality_warning_count = 0

source_rows_reported = items_seen
stored AP row count = items_stored
```

Any contradiction inside a cycle claiming complete-success is a source
integrity failure.

Do not silently downgrade corrupted truth to a normal partial sample.

---

# 31. AP row integrity

For every AP row of a canonical cycle:

```text
site_id = requested Site
cycle_id = selected cycle
canonical AP MAC
unique AP MAC inside cycle

partial = 0
overview_ok = 1
wired_uplink_ok = 1
lan_traffic_ok = 1
radios_ok = 1
```

Section timestamps must satisfy cycle temporal integrity.

---

# 32. Rate shape integrity

For each wired/LAN direction:

```text
reason = ok
→ finite numeric rate
→ rate >= 0
→ required section timestamp exists
```

and:

```text
reason != ok
→ rate = null
```

Contradictory rate/reason shape inside a complete-success source cycle is
integrity failure.

Allowed rate reasons remain exactly:

```text
ok
no_baseline
counter_reset
gap_too_large
invalid_elapsed
source_unavailable
```

---

# 33. Historical source families

Machine values remain:

```text
wired
lan
```

Primary:

```text
wired
```

Fallback:

```text
lan
```

No:

```text
radio
client
SSID
WAN
```

in Site Network Traffic v1.

---

# 34. Source-selection unit

DRAFT selects:

```text
one bucket
=
one source-family decision
```

Therefore within one historical bucket:

```text
all comparable Site/AP samples use wired
OR
all comparable Site/AP samples use lan
```

Forbidden:

```text
AP-1 wired
+
AP-2 lan
inside one bucket
→ Site total
```

---

# 35. Bucket source-family coverage inputs

For each bucket compute:

```text
canonical_cycle_count

wired_complete_site_cycle_count
lan_complete_site_cycle_count

wired_pair_valid_ap_opportunities
lan_pair_valid_ap_opportunities

total_ap_opportunities
```

A family has a complete Site cycle when:

```text
every AP in that canonical cycle
has valid Download + Upload pair
for that family
```

---

# 36. Historical source-family selection — DRAFT algorithm

For a non-empty bucket:

```text
if wired_complete_site_cycle_count == canonical_cycle_count:
    selected_source = wired
    selection_reason = primary_full_coverage

elif lan_complete_site_cycle_count == canonical_cycle_count:
    selected_source = lan
    selection_reason = fallback_full_coverage

elif lan_complete_site_cycle_count > wired_complete_site_cycle_count:
    selected_source = lan
    selection_reason = fallback_higher_coverage

elif wired_complete_site_cycle_count > lan_complete_site_cycle_count:
    selected_source = wired
    selection_reason = primary_preferred_tie_or_higher

else:
    compare valid AP-pair opportunities

    if lan > wired:
        selected_source = lan
        selection_reason = fallback_higher_coverage

    else:
        selected_source = wired
        selection_reason = primary_preferred_tie_or_higher
```

If there are no canonical cycles:

```text
selected_source = null
selection_reason = no_canonical_samples
```

This is the DRAFT historical generalization of the accepted Current Traffic
source-selection policy.

---

# 37. Source family may change between buckets

Allowed:

```text
bucket N     = wired
bucket N + 1 = lan
bucket N + 2 = wired
```

This is evidence-driven fallback.

The contract must expose source transitions.

A transition is:

```text
provenance / quality context
```

not automatically a defect.

---

# 38. Canonical Site rate sample

For one canonical cycle and the bucket-selected family:

```text
complete Site rate sample
```

exists only when all APs in the cycle have valid:

```text
Download
+
Upload
```

for that family.

Then:

```text
site_download_mbps
=
SUM(AP Download)

site_upload_mbps
=
SUM(AP Upload)

site_total_mbps
=
download + upload
```

If any AP pair is invalid:

```text
that cycle is excluded from the bucket numeric mean
```

but its reason counts remain visible in quality metadata.

---

# 39. No partial undercount presented as full Site rate

A cycle with:

```text
AP-1 valid
AP-2 missing/reset/gap
```

MUST NOT be presented as a canonical Site total based only on AP-1.

This avoids a false low Site graph value.

Known partial evidence is recorded as quality/exclusion.

---

# 40. Bucket numeric aggregation — DRAFT proposal

For v1, one bucket numeric value is:

```text
arithmetic mean
of complete Site rate samples
for the selected source family
inside that bucket
```

Fields:

```text
download_mbps
upload_mbps
total_mbps
```

Total:

```text
total_mbps = download_mbps + upload_mbps
```

when both directions exist.

Browser never recomputes this.

---

# 41. Why DRAFT does not claim time-weighted average

Persisted rate fields are already interval averages calculated by Observation,
but their exact acquisition baseline elapsed interval is not persisted as a
dedicated field.

Therefore this DRAFT does NOT silently call the bucket metric:

```text
time-weighted average
```

unless implementation reconstructs the original interval timing exactly and
that reconstruction passes dedicated tests.

Current proposal is explicitly:

```text
mean_of_complete_site_rate_samples
```

This is a TECH LEAD REVIEW POINT before FINAL.

---

# 42. Future time-weighted option

If Owner / Tech Lead requires exact time weighting before FINAL:

preferred approach is still:

```text
reuse persisted rate values
+
reconstruct exact prior completed sample timestamp
+
weight only validated intervals
```

Not:

```text
recalculate a second Mbps formula from raw counters
```

This would remain a read-layer change and would not require new Omada polling,
but it materially increases query complexity and must be benchmarked.

---

# 43. Valid zero

If canonical complete Site samples exist and all rates are zero:

```text
download_mbps = 0.0
upload_mbps = 0.0
total_mbps = 0.0
```

This is valid zero evidence.

Never convert it to no-data.

---

# 44. Missing is not zero

If a bucket has no complete Site rate sample:

```text
download_mbps = null
upload_mbps = null
total_mbps = null
```

Do not fabricate:

```text
0 Mbps
```

---

# 45. Historical gap threshold

DRAFT reuses the existing Analytics quality threshold:

```text
ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS
```

Current repository default:

```text
180 seconds
```

No new independent Traffic gap threshold is proposed in READ v1.

---

# 46. Bucket temporal gap fields

Each bucket should expose:

```text
first_complete_sample_at
last_complete_sample_at

leading_gap_seconds
trailing_gap_seconds
max_inter_sample_gap_seconds
gap_count_over_threshold
```

No interpolation is performed across a gap exceeding the accepted threshold.

---

# 47. Bucket completeness status

Canonical bucket statuses:

```text
complete
partial
none
```

## complete

Proposed:

```text
at least one complete Site sample
AND all canonical cycles in bucket produced complete Site samples
    for selected source
AND no partial/failed/abandoned collection evidence causes a missing sample
AND leading/trailing/inter-sample gaps do not exceed threshold
```

## partial

```text
some complete Site samples exist
BUT one or more required completeness conditions fail
```

## none

```text
no complete Site sample exists
```

---

# 48. Partial does not become zero

For `partial` bucket v1 DRAFT recommends:

```text
numeric bucket value MAY remain available
only if it is explicitly defined as sample mean over complete samples
and status remains partial
```

However future Period Statistics MUST NOT silently treat a partial bucket as a
fully covered Site period.

This exact consumer policy is finalized in `TRAFFIC-03`.

---

# 49. Range-level coverage

Top-level coverage:

```text
complete
partial
none
```

## complete

All requested buckets are complete.

## partial

At least one usable bucket exists but:

```text
one or more buckets are partial/none
or requested range extends outside proven available history
```

## none

No usable bucket exists.

---

# 50. Actual source coverage boundaries

Read contract must expose:

```text
available_from_utc
available_through_utc
source_watermark_utc
```

These are derived from actual persisted accepted evidence.

Do NOT infer:

```text
available_from = now - configured retention
```

because the DB may contain less data.

---

# 51. Historical source freshness

Historical range age is NOT itself a freshness failure.

Example:

```text
querying a complete range from 10 days ago
```

must not become stale merely because the range is old.

Instead expose:

```text
source_watermark_utc
source_age_seconds
```

where:

```text
source_age_seconds
=
evaluated_at_utc - latest accepted current source watermark
```

`TRAFFIC-02-READ` v1 does not create another `fresh/stale` threshold taxonomy.

---

# 52. Collection freshness vs historical completeness

Permanent:

```text
current collection freshness
!=
historical range completeness
```

A source may be currently fresh but a requested old range can be partial due
retention/gaps.

A source may currently be temporarily delayed while a closed historical range
remains complete.

Do not collapse these into one "Traffic Health %" value.

---

# 53. Collection attempt quality

For requested bucket/range also count Observation attempts:

```text
completed_success_count
completed_partial_count
completed_failed_count
completed_shutdown_count
abandoned_count
running_count
```

A running tail cycle is informational and must not by itself corrupt a closed
historical bucket.

---

# 54. Rate reason quality

For the selected source family aggregate:

```text
ok
no_baseline
counter_reset
gap_too_large
invalid_elapsed
source_unavailable
```

Counts must remain available in bucket/range quality metadata.

No reason is silently relabeled as zero.

---

# 55. Source transition metadata

Return:

```text
source_transition_count
```

and optionally per bucket:

```text
source_changed_from_previous
```

Do not call fallback itself an error.

A LAN fallback bucket with complete evidence may still be:

```text
coverage = complete
```

with explicit source provenance.

---

# 56. No-data behavior

Valid query + source available + no accepted historical evidence:

```text
service result status = insufficient_data
coverage = none
bucket numeric values = null
HTTP future mapping = 200 product no-data state
```

Do not raise source unavailable merely because the Site has no data.

---

# 57. Partial-data behavior

Valid query + some accepted historical evidence + incomplete range:

```text
status = partial
coverage = partial
```

Examples:

```text
range starts before earliest retained evidence
missing buckets
collection gaps
rate resets
no-baseline samples
source section unavailable in some attempts
```

No fallback to Omada.

---

# 58. Source-unavailable behavior

Source unavailable means the persisted read boundary itself cannot safely
satisfy the contract.

Examples:

```text
Observation DB unavailable
schema mismatch
SQLite read error
complete-success integrity contradiction
query-only boundary missing
```

Expected typed failure:

```text
HistoricalTrafficSourceUnavailable
```

Future Admin mapping:

```text
503 source_unavailable
```

---

# 59. Query-deadline behavior

SQLite statement interruption/deadline:

```text
AnalyticsQueryDeadlineExceeded
```

or a dedicated narrow wrapper preserving that distinction.

Future Admin mapping:

```text
503 query_deadline
```

Do not convert timeout to no-data.

---

# 60. Invalid range behavior

Invalid caller input includes:

```text
invalid Site syntax
invalid UTC timestamp
from >= to
to > evaluated_at
invalid bucket size
bucket count above allowed output bound
```

Expected:

```text
HistoricalTrafficValidationError
```

Future Admin mapping:

```text
400 invalid_request
```

---

# 61. No raw-row payload

The read foundation MUST perform:

```text
server-side aggregation
```

Forbidden future API pattern:

```text
return all 30-second ap_observations
→ browser downsample
```

The browser is presentation only.

---

# 62. Canonical immutable DTO — DRAFT

Preferred models:

```text
HistoricalTrafficRange
HistoricalTrafficBucket
HistoricalTrafficCoverage
HistoricalTrafficSourceSelection
HistoricalTrafficQuality
HistoricalSiteTraffic
```

All DTOs:

```text
frozen
Site-scoped
no sqlite3.Row
no mutable source dictionaries
```

---

# 63. HistoricalTrafficRange — proposed fields

```text
site_id
from_utc
to_utc
evaluated_at_utc

bucket_seconds
bucket_count
bucket_alignment = range_start_utc

unit = Mbps
aggregation = mean_of_complete_site_rate_samples
metric_version = network_traffic_history.v1
source_kind = observation_ap_dynamic
```

---

# 64. HistoricalTrafficBucket — proposed fields

```text
bucket_start_utc
bucket_end_utc

download_mbps
upload_mbps
total_mbps

status

selected_source
selection_reason
source_changed_from_previous

canonical_cycle_count
complete_site_sample_count
excluded_site_sample_count

total_ap_opportunities
selected_pair_valid_ap_opportunities

first_complete_sample_at
last_complete_sample_at

leading_gap_seconds
trailing_gap_seconds
max_inter_sample_gap_seconds
gap_count_over_threshold

rate_reason_counts
```

No raw controller JSON.

---

# 65. HistoricalTrafficCoverage — proposed fields

```text
status

available_from_utc
available_through_utc
source_watermark_utc
source_age_seconds

bucket_count
complete_bucket_count
partial_bucket_count
missing_bucket_count

canonical_cycle_count
complete_site_sample_count
excluded_site_sample_count

gap_bucket_count
source_transition_count
```

---

# 66. HistoricalTrafficSourceSelection — proposed fields

Per bucket:

```text
primary_source = wired
selected_source = wired | lan | null
selection_reason

wired_complete_site_cycle_count
lan_complete_site_cycle_count

wired_pair_valid_ap_opportunities
lan_pair_valid_ap_opportunities

source_mixing_allowed = false
```

---

# 67. HistoricalTrafficQuality — proposed range fields

```text
partial_cycle_count
failed_cycle_count
shutdown_cycle_count
abandoned_cycle_count

no_baseline_count
counter_reset_count
gap_too_large_count
invalid_elapsed_count
source_unavailable_count

integrity_failure_count
```

`integrity_failure_count > 0` for a claimed canonical cycle is expected to be
terminal source-unavailable rather than a returned partial result.

---

# 68. DTO serializer boundary

`TRAFFIC-02-READ` is a backend read foundation.

DRAFT recommendation:

```text
DO NOT add Admin HTTP serializer yet
```

The canonical application DTO is locked here.

Future:

```text
TRAFFIC-02
```

adds a safe Admin serializer that:

```text
whitelists DTO fields
validates enum/value shape
validates finite non-negative Mbps
validates bucket ordering
validates bucket_count bound
does not recalculate values
does not change source selection
does not change quality status
```

Thus:

```text
read semantics owner = TRAFFIC-02-READ
HTTP projection owner = TRAFFIC-02
```

---

# 69. Future Admin endpoint boundary

No endpoint is added in this TASK.

Future preferred namespace:

```text
GET /admin/api/v1/sites/<site_id>/traffic/history
```

is reserved conceptually for `TRAFFIC-02`.

Exact HTTP contract is finalized only after this READ foundation is merged and
rebound.

---

# 70. Future security ordering

Future `TRAFFIC-02` route should preserve:

```text
authenticated Admin session
        ↓
resolve Site
        ↓
authorize admin.read.context
        ↓
WEB_ADMIN_TRAFFIC_ENABLED
        ↓
AdminQueryService
        ↓
admin.read.overview
        ↓
HistoricalTrafficReadService
```

No new auth mechanism.

No browser bearer token.

No Traffic-specific Site resolver.

---

# 71. Feature flag boundary

Current master product flag remains:

```text
WEB_ADMIN_TRAFFIC_ENABLED
```

It controls product exposure.

It MUST NOT start/stop:

```text
Observation
Analytics
HistoricalTrafficReadService
CurrentTrafficReadService
Home
Visit Lifecycle
```

Canonical:

```text
Traffic product flag
!=
source/read-service lifecycle
```

---

# 72. Traffic Foundation reuse

`TRAFFIC-02-READ` contains:

```text
NO frontend code
```

Future `TRAFFIC-02` History panel MUST register through existing:

```text
window.CaptivPortalTrafficCoordinator
```

It MUST NOT create:

```text
second page coordinator
second global Refresh owner
new visibility lifecycle
new page-level AbortController owner
independent polling timer
```

This requirement is locked now even though the frontend is out of scope.

---

# 73. No Admin/browser direct Omada access

Permanent forbidden paths:

```text
Browser → Omada
Admin route → Omada
HistoricalTrafficReadService → Omada
Traffic page → traffic-activities
Traffic page → traffic-distribution
```

No request-time acquisition.

---

# 74. Native Omada historical endpoints

Research verified:

```text
dashboard/traffic-activities
dashboard/traffic-distribution
```

`traffic-activities` provides Site historical volume buckets.

Observed Controller 5.14.32.3 granularity:

```text
≤26h      → 5-minute
27–170h   → hourly
171h–120d → daily
≥121d     → weekly
```

These are Controller-specific observed behaviors, not universal contracts.

---

# 75. Native Omada role in v1

Canonical:

```text
validation source
!=
product source
```

V1:

```text
traffic-activities
→ validation/reference for Site history

traffic-distribution
→ later validation/reference for AP share
```

Do NOT persist or call them as part of `TRAFFIC-02-READ`.

---

# 76. No new acquisition decision

Current persisted Observation facts are sufficient to build the first
historical Network Throughput contract.

Therefore DRAFT verdict:

```text
NEW ACQUISITION PATH:
NOT REQUIRED
```

If future evidence proves Observation history insufficient for a required
product semantic:

```text
STOP
→ separate acquisition architecture review/TASK
```

Do not add native history polling opportunistically.

---

# 77. No derived Traffic DB decision

DRAFT:

```text
NO derived historical Traffic DB
NO materialized rollup table
NO cache persistence
```

Use:

```text
bounded query-on-read
```

first.

If benchmark fails:

```text
STOP
→ report measured failure
→ separate rollup/storage architecture
```

No silent cache.

---

# 78. Query-plan / performance gate

Before FINAL implementation acceptance, targeted tests must verify:

```text
EXPLAIN QUERY PLAN
```

uses existing useful source indexes and avoids an obviously unbounded accidental
Cartesian scan.

No index/schema change is authorized by this DRAFT.

If acceptable performance requires a new index:

```text
STOP
→ architecture review
```

Do not silently alter Observation schema.

---

# 79. Existing relevant indexes

Current Observation schema already has indexes including:

```text
idx_ap_site_time
(site_id, observed_at, row_id)

idx_ap_site_mac_time
(site_id, ap_mac, observed_at, row_id)

idx_cycles_site_kind_started
(site_id, kind, started_at)
```

and unique cycle/AP keys.

These are the first implementation target.

---

# 80. Source read transaction

Preferred:

```text
one read-only SQLite snapshot transaction
```

for one `get_site_history()` call covering:

```text
actual coverage boundaries
cycle quality
bucket source-family selection
bucket traffic aggregates
gap metadata
quality counts
```

Avoid multiple unrelated snapshots producing self-inconsistent history metadata.

---

# 81. Read-only requirements

Reuse existing Observation/Analytics boundary:

```text
URI mode=ro
PRAGMA query_only=ON
schema version check
QueryDeadline
SQLite progress handler
```

No:

```text
INSERT
UPDATE
DELETE
CREATE
ALTER
VACUUM
migration
```

from historical read service.

---

# 82. Exact implementation scope — proposed

Preferred new production file:

```text
app/analytics/historical_traffic.py
```

Preferred modified production files:

```text
app/analytics/__init__.py
app/analytics/models.py
app/analytics/source_gateway.py
app/analytics/runtime.py
```

Preferred new tests:

```text
tests/analytics/test_historical_traffic.py
tests/analytics/test_historical_traffic_runtime.py
```

No Admin Web file is required in `TRAFFIC-02-READ`.

---

# 83. Expected unchanged production files

Do NOT change:

```text
app/observations/config.py
app/observations/repository.py
app/observations/read_service.py
app/observations/ap_worker.py
app/observations/ap_normalizer.py

app/analytics/config.py
app/analytics/wireless.py
app/analytics/current_traffic.py
app/analytics/home_activity.py

app/admin_web/routes.py
app/admin_web/query_service.py
app/admin_web/static/admin.js
app/admin_web/templates/admin/traffic.html
app/admin_web/templates/admin/home.html
app/admin_web/config.py

app/config.py
app/settings.py
.env.example
run.py
```

Current DRAFT intentionally needs no new environment setting.

If implementation requires changing one of these:

```text
STOP
→ return exact reason
→ architecture impact review
```

---

# 84. Explicit non-goals

Not in `TRAFFIC-02-READ`:

```text
Traffic History UI
History chart
Admin history endpoint
browser range selector
Traffic coordinator changes
Period Average
Period Peak
Peak Load Period
Traffic by AP UI
AP Traffic Share UI
Online Guests
Guest Session Traffic
Traffic Evidence panel
30-day UI option
Heatmap
Period Comparison
Home changes
Web Designer work
```

---

# 85. Coder focused tests — ownership

Coder may run only focused/minimal tests for this TASK.

Coder MUST NOT independently run:

```text
full tests/analytics
full tests/admin_web
full repository pytest
Central Lab V6
baseline/candidate differential
official release gate
```

These remain Owner + Tech Lead / Central Lab responsibilities.

---

# 86. Required focused source tests

`tests/analytics/test_historical_traffic.py` should prove at minimum:

```text
Site scope enforced
half-open [from,to)
to == exact boundary excluded

complete-success cycles accepted
partial/failed/abandoned excluded as canonical samples

complete-success integrity contradiction
→ source unavailable

wired primary full coverage
lan fallback full coverage
lan higher coverage
wired tie preference

no source mixing inside bucket

source family may change between buckets
transition metadata correct

valid zero preserved

missing data not zero

no-baseline counted
counter reset counted
gap-too-large counted
invalid elapsed counted
source unavailable reason counted

no canonical samples
→ insufficient_data / coverage none

some usable buckets + missing/gaps
→ partial

all complete buckets
→ complete

actual coverage boundaries returned
```

---

# 87. Required focused range/granularity tests

At minimum:

```text
24h → 300-second buckets
7d  → 900-second buckets
30d → 3600-second buckets
180d → 21600-second buckets
```

Also prove:

```text
no generic 7-day rejection
no generic 31-day rejection
```

A valid >31d synthetic range must be accepted if:

```text
bucket output stays bounded
source query meets deadline
```

---

# 88. Required focused gap tests

Prove:

```text
leading gap
trailing gap
inter-sample gap
gap threshold boundary
gap > threshold
```

No interpolation over unacceptable gaps.

Prove old closed historical range is not marked stale simply because it is old.

---

# 89. Required read-only / immutability tests

Before/after query verify:

```text
Observation row counts unchanged
PRAGMA user_version unchanged
query_only remains true
no write dependency exists
```

No test may need an Omada client.

---

# 90. Required runtime-isolation tests

`tests/analytics/test_historical_traffic_runtime.py`:

```text
normal Analytics runtime
→ historical_traffic_service available

historical service construction failure
→ historical_traffic_service = None
→ existing Analytics state unchanged
→ CurrentTrafficReadService unchanged
→ Wireless unchanged
→ Visit Analytics unchanged
→ HomeActivity unchanged
```

No startup query.

No background thread.

---

# 91. Coder focused command — proposed

```bash
python -m pytest -q \
  tests/analytics/test_historical_traffic.py \
  tests/analytics/test_historical_traffic_runtime.py
```

Static:

```bash
PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc \
python -m compileall -q app/analytics

git diff --check
```

Coder handoff records exact counts.

---

# 92. Central Lab targeted regression

Owner + Tech Lead / Central Lab must run relevant exact-candidate regression
covering at least:

```text
existing Analytics read/source gateway behavior
CurrentTrafficReadService
TRAFFIC-00 Foundation
TRAFFIC-01 Current Network Throughput
Home Current Traffic compatibility
```

Reason:

`source_gateway.py`, `models.py`, and `runtime.py` are shared boundaries.

---

# 93. TRAFFIC-00 / 01 regression requirements

Central Lab must confirm no regression in:

```text
Traffic page
Traffic coordinator
Current Network Throughput
Traffic current endpoint
Home current Traffic
feature flag independence
panel failure isolation
same-origin request boundary
```

`TRAFFIC-02-READ` itself adds no frontend, so any frontend delta is a regression.

---

# 94. Full Central Lab gate

Official acceptance belongs to:

```text
Owner + Tech Lead / Central Lab
```

Use the CURRENT VERIFIED Central Lab runner at execution time.

Do not hardcode an old runner version as timeless truth.

Acceptance includes:

```text
exact candidate
exact baseline
targeted regression
full approved regression
baseline/candidate differential
compileall
git diff --check
exact artifact immutability
official PASS/FAIL
```

---

# 95. Performance acceptance

Central Lab should benchmark synthetic or real read-only data at minimum:

```text
24h
7d
30d
```

and, if enough retained/synthetic data is available:

```text
180d
```

Record:

```text
row count
AP cardinality
bucket count
query duration
peak response DTO size
deadline result
```

No arbitrary day ceiling should be introduced solely because an old Analytics
module has one.

---

# 96. Native Omada validation oracle

Optional but strongly recommended Central Lab validation:

```text
Observation-derived historical Site evidence
vs
Omada dashboard/traffic-activities
```

on the same controlled Site/time window.

This is:

```text
independent validation
```

not application dependency.

Because accounting timestamps/granularity/unit labeling differ, do not require
byte-for-byte equality without a separately proven conversion/tolerance contract.

Material unexplained divergence must be investigated.

---

# 97. Native AP distribution oracle

`traffic-distribution` is not required to accept `TRAFFIC-02-READ` Site history.

It becomes more relevant later for:

```text
TRAFFIC-05
TRAFFIC-06
```

Keep:

```text
validation source != product source
```

---

# 98. Production behavior of READ foundation

`TRAFFIC-02-READ` itself:

```text
adds no Admin route
adds no panel
adds no scheduler
adds no collector
adds no env activation flag
```

If merged/deployed, the service object may be composed as an optional
demand-only dependency but performs zero source query until called.

Therefore no product exposure is activated by this TASK.

---

# 99. No production activation change

Implementation MUST NOT automatically modify:

```text
/etc/default/captive-portal
WEB_ADMIN_TRAFFIC_ENABLED
Observation settings
Analytics settings
systemd
Nginx
```

No restart/deploy/activation authorization is implied.

---

# 100. Merge / deploy separation

Permanent governance:

```text
DRAFT
→ review
→ FINAL
→ explicit implementation authorization
→ Coder implementation
→ Coder focused tests
→ Central Lab acceptance
→ Owner merge authorization
→ merge
→ separate deployment decision
→ later TRAFFIC-02 rebind
```

No implementation is authorized by this DRAFT.

---

# 101. Future TRAFFIC-02 rebind

After `TRAFFIC-02-READ` merge + acceptance:

```text
fetch exact new origin/main
pin merge SHA/tree
inspect actual service/DTO/runtime contract
```

Then create:

```text
TASK-TRAFFIC-02 — Network Traffic History — DRAFT/FINAL
```

on the real accepted READ implementation.

Do not prepare a coder FINAL for History against this DRAFT assumption.

---

# 102. Future TRAFFIC-02 responsibility

`TRAFFIC-02` will own:

```text
AdminQueryService bridge
safe Admin serializer
GET /traffic/history
History panel markup
Traffic coordinator registration
24h / 7d product selector
chart rendering
panel-local failures
browser DTO validation
```

It MUST NOT own:

```text
historical source selection
bucket calculations
gap semantics
historical coverage calculations
```

Those remain `TRAFFIC-02-READ`.

---

# 103. Future downstream ownership

`TRAFFIC-03 / 04 / 05 / 06` must consume or extend the same:

```text
HistoricalTrafficReadService
```

Forbidden:

```text
TRAFFIC-03 own history SQL
TRAFFIC-04 own history SQL
TRAFFIC-05 own source-family algorithm
TRAFFIC-06 own source-family algorithm
```

One semantic owner.

---

# 104. Review point A — bucket aggregation

DRAFT currently proposes:

```text
mean_of_complete_site_rate_samples
```

Reason:

```text
simple
deterministic
uses persisted derived rate truth
does not pretend missing time is zero
does not reimplement counter-rate formula
```

Before FINAL Tech Lead should explicitly decide:

```text
ACCEPT sample-mean v1
```

or require:

```text
exact interval-weighted reconstruction
```

If interval-weighted is required, the implementation scope/performance section
must be revised before FINAL.

---

# 105. Review point B — MAX_BUCKETS

DRAFT proposes:

```text
720
```

because it naturally supports:

```text
24h @ 5m
7d @ 15m
30d @ 1h
180d @ 6h
```

Tech Lead should confirm or revise the number based on benchmark/payload policy.

The key invariant is permanent:

```text
bounded points
not arbitrary max days
```

---

# 106. Review point C — partial bucket numeric value

DRAFT allows a partial bucket to retain a numeric mean calculated only from
complete Site samples, while clearly marking:

```text
status = partial
```

Alternative stricter policy:

```text
partial bucket
→ numeric values = null
```

Tech Lead should explicitly choose before FINAL because it affects future chart
semantics and Period Statistics.

No UI should make this choice independently.

---

# 107. Architecture verdict

Based on current repository and accepted research:

```text
Persisted historical AP Traffic source:
YES

Sufficient for first Historical Network Throughput:
YES

New collector required:
NO

New Omada history polling required:
NO

New DB/schema required:
NO

Existing Wireless distribution service sufficient as canonical owner:
NO

Dedicated HistoricalTrafficReadService justified:
YES

Artificial 7d/31d ceiling justified:
NO

Bounded bucket/query controls required:
YES
```

---

# 108. DRAFT acceptance criteria for architectural review

The DRAFT is ready to move toward FINAL only after Owner + Tech Lead confirm:

1. Observation AP history remains canonical product source.
2. No new acquisition path is introduced.
3. No derived Traffic DB is introduced.
4. `HistoricalTrafficReadService` is the semantic owner.
5. Existing 7d/31d Analytics ceilings are not reused as source ceilings.
6. Range is bounded by actual coverage/performance/output points, not arbitrary days.
7. UTC half-open range contract is accepted.
8. Range-start fixed-duration bucket alignment is accepted for v1.
9. Bucket source-family selection unit is accepted.
10. No wired/LAN mixing inside a bucket is accepted.
11. Source transitions between buckets are allowed/provenanced.
12. Complete Site sample requires all AP pairs valid.
13. Missing is not zero.
14. Valid zero remains zero.
15. Gap/coverage semantics are accepted.
16. Historical source age is separated from range completeness.
17. Native Omada history remains validation/reference only.
18. No Admin/UI code is included in READ foundation.
19. Traffic Foundation coordinator remains untouched.
20. Security/feature boundary for future TRAFFIC-02 is accepted.
21. Coder testing ownership remains focused/minimal.
22. Central Lab owns cross-module/full acceptance.
23. Review Point A is resolved.
24. Review Point B is resolved.
25. Review Point C is resolved.
26. Production activation remains separate.

---

# 109. Final DRAFT status

```text
TASK:
TRAFFIC-02-READ — Historical Network Traffic Read Foundation

STATUS:
DRAFT — FOR OWNER + TECH LEAD ARCHITECTURAL REVIEW

BOUND TO:
main@8f3ad59771f72c49834b1012963de6d94b9e0d18

TREE:
2ef8bf264a008259242cde0778d0ebd20fa94b9e

CANONICAL SOURCE PROPOSAL:
Observation persisted AP dynamic history

NEW ACQUISITION:
NO

NEW DB / SCHEMA:
NO

ADMIN / UI:
OUT OF SCOPE

IMPLEMENTATION AUTHORIZATION:
NOT GRANTED

PRODUCTION ACTIVATION:
NOT GRANTED
```

Next action:

```text
Owner + Tech Lead architectural review
→ corrections
→ FINAL
```

Implementation must not begin from this DRAFT.
