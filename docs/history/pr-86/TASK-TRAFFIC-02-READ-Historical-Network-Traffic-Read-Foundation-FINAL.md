# TASK-TRAFFIC-02-READ — Historical Network Traffic Read Foundation — FINAL

**Project:** CaptivPortal  
**Area:** Admin Console → Traffic  
**Parent:** `CaptivPortal — Генеральная дорожная карта раздела Admin Console → Traffic — FINAL v1`  
**Predecessors:** `TASK-TRAFFIC-00`, `TASK-TRAFFIC-01`  
**Type:** architecture / backend read-foundation specification  
**Status:** `FINAL — TECH LEAD REVIEW INCORPORATED / READY FOR EXPLICIT OWNER IMPLEMENTATION AUTHORIZATION`  
**Implementation authorization:** `NOT GRANTED`  
**Branch / code / commit / push / PR / merge:** `NOT AUTHORIZED`  
**Production activation:** `NOT GRANTED; SEPARATE OWNER-CONTROLLED ACTION`  
**Prepared / finalized:** 2026-08-29  
**Tech Lead review:** `ARCHITECTURE DIRECTION PASS / TARGETED CORRECTIONS INCORPORATED`  

---

# 0. Executive decision

`TRAFFIC-02-READ` creates the canonical read-layer owner for:

```text
Historical Network Traffic
```

Canonical v1 source:

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

FINAL decisions:

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

Canonical Site historical sample timestamp:

```text
sample_at = ap_dynamic cycle.finished_at
```

Canonical output bound:

```text
MAX_SITE_HISTORY_BUCKETS = 720
```

Canonical complete Site sample skew policy:

```text
MAX_SITE_SAMPLE_SOURCE_SKEW_SECONDS = 60
```

Bucket v1 numeric aggregation:

```text
mean_of_complete_site_rate_samples
```

This aggregation is ONLY the `TRAFFIC-02` History bucket contract. It is NOT the
future canonical `TRAFFIC-03 Period Average`, which remains interval/time-aware
and must still be implemented through the same Historical Traffic semantic
owner.

This FINAL does not grant implementation, merge, deployment or production
activation authorization.

---

# 1. Exact FINAL repository rebind and production drift

Repository state was rechecked after Tech Lead review.

Current repository:

```text
main =
0d00a9127c0b393bf2c7b57aa5bde103c13119db

tree =
9bc737a7d2978f4345fd6b6bb7a0edfea08d019f
```

Current main is:

```text
Merge PR #85
Docs: reconcile Traffic production state and Central Lab V6
```

DRAFT baseline was:

```text
8f3ad59771f72c49834b1012963de6d94b9e0d18
tree 2ef8bf264a008259242cde0778d0ebd20fa94b9e
```

Comparison from DRAFT baseline to FINAL baseline changes only documentation /
governance files. Runtime implementation files are unchanged.

Therefore:

```text
architecture impact = NONE
runtime rebind conflict = NONE
```

Repository and production are intentionally distinguished:

```text
repository current main =
0d00a9127c0b393bf2c7b57aa5bde103c13119db

production runtime HEAD =
8f3ad59771f72c49834b1012963de6d94b9e0d18

production runtime tree =
2ef8bf264a008259242cde0778d0ebd20fa94b9e
```

This is accepted docs-only repository/production drift.

Implementation, if later authorized, MUST start from the exact current
`origin/main`, not from production HEAD and not from the historical DRAFT
baseline.

If `origin/main` changes after this FINAL and before implementation
authorization:

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

# 13. No artificial calendar-day ceiling — FINAL

`HistoricalTrafficReadService` v1 MUST NOT reject a range because it exceeds:

```text
7 days
31 days
30 days
```

solely because older Analytics contracts contain such bounds.

Allowed technical bounds are:

```text
actual persisted coverage
query deadline
MAX_SITE_HISTORY_BUCKETS
SQLite/performance budget
```

Canonical:

```text
range capability
!=
UI range exposure
```

The Historical service MAY read valid ranges longer than 31 days when:

```text
output remains bounded
query meets deadline
source evidence is available
```

`AnalyticsConfig.max_query_window_days` and
`AnalyticsConfig.wireless_max_window_days` MUST NOT be used for Historical
Traffic range rejection.

The service MAY reuse:

```text
AnalyticsConfig.quality_gap_threshold_seconds
```

for gap semantics.

Focused proof of a valid synthetic range greater than 31 days is mandatory.

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

FINAL decision:

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

# 18. Canonical service method — FINAL

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

No `max_query_window_days` parameter.

The service itself derives:

```text
sample_at
bucket membership
source-family selection
Site sample validity
coverage
quality
```

from persisted Observation facts.

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

# 20. Canonical time range and sample timestamp

All requested ranges are:

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

Canonical historical Site sample timestamp:

```text
sample_at
=
canonical ap_dynamic cycle.finished_at
```

`sample_at` is source-independent and determines:

```text
requested-range membership
bucket membership
first_complete_sample_at
last_complete_sample_at
inter-sample gap calculation
```

Section timestamps:

```text
wired_observed_at
lan_observed_at
```

remain evidence integrity / provenance timestamps. They MUST NOT determine
bucket membership.

Boundary semantics:

```text
cycle.finished_at == from_utc
→ included

cycle.finished_at == to_utc
→ excluded

cycle.finished_at == bucket_end
→ belongs to next bucket
```

No hidden `-1ms` adjustment.

The reason for using `cycle.finished_at` is to avoid a circular dependency:

```text
source timestamp
→ bucket
→ source-family selection
→ source timestamp
```

Bucket membership is fixed before source-family selection.

---

# 21. Evaluation time and as-of semantics

If omitted:

```text
evaluated_at_utc = current UTC
```

Required:

```text
to_utc <= evaluated_at_utc
```

Future requested ranges are invalid.

Every source/coverage calculation is:

```text
as-of evaluated_at_utc
```

Rows/cycles with:

```text
finished_at > evaluated_at_utc
```

MUST NOT influence:

```text
requested history result
available_from_utc
available_through_utc
source_watermark_utc
source age
quality counters used by the returned result
```

This rule is mandatory even when the database already contains later persisted
evidence, allowing deterministic backdated evaluations.

Therefore:

```text
source_age_seconds >= 0
```

Future persisted evidence relative to `evaluated_at_utc` is invisible to the
result.

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

# 24. Bounded Site history bucket count — FINAL

Canonical Site-history v1 output constant:

```text
MAX_SITE_HISTORY_BUCKETS = 720
```

This is:

```text
Site historical time-series output cardinality bound
```

not:

```text
calendar-day ceiling
generic future AP-series limit
AP count limit
TRAFFIC-05 payload limit
TRAFFIC-06 payload limit
```

Future AP-oriented tasks MUST define their own series/response bounds.

Purpose:

```text
prevent raw 30-second history → browser-scale payload
keep application DTO bounded
preserve deterministic query/payload budgets
```

---

# 25. Automatic granularity — FINAL

When `bucket_seconds` is omitted, choose the smallest supported fixed-duration
bucket that keeps:

```text
bucket_count <= MAX_SITE_HISTORY_BUCKETS
```

Canonical ladder:

```text
5 min   = 300 s
15 min  = 900 s
1 hour  = 3600 s
6 hour  = 21600 s
1 day   = 86400 s
7 day   = 604800 s
30 day  = 2592000 s
```

For ranges that do not fit within `MAX_SITE_HISTORY_BUCKETS` even at the final
ladder step, use deterministic whole-day fallback:

```text
range_seconds =
to_utc - from_utc

required_seconds =
ceil(range_seconds / MAX_SITE_HISTORY_BUCKETS)

bucket_seconds =
ceil(required_seconds / 86400) * 86400
```

The resulting:

```text
bucket_count
=
ceil(range_seconds / bucket_seconds)
```

MUST be `<= MAX_SITE_HISTORY_BUCKETS`.

No speculative/unbounded "choose a larger bucket" behavior is permitted.

---

# 26. Bucket count, boundaries and common ranges

Canonical:

```text
range_seconds =
to_utc - from_utc

bucket_count =
ceil(range_seconds / bucket_seconds)
```

For zero-based bucket `N`:

```text
bucket_start =
from_utc + N * bucket_seconds

bucket_end =
min(bucket_start + bucket_seconds, to_utc)
```

The final bucket MAY be shorter than `bucket_seconds`.

No sample with:

```text
sample_at < from_utc
sample_at >= to_utc
```

is included.

Common automatic resolutions:

```text
24h
→ 300-second buckets
→ 288 buckets

7d
→ 900-second buckets
→ 672 buckets

30d
→ 3600-second buckets
→ 720 buckets

180d
→ 21600-second buckets
→ 720 buckets
```

Exact-boundary test is mandatory:

```text
720 buckets
→ accepted

explicit bucket request producing 721 buckets
→ validation error
```

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
bucket_count <= MAX_SITE_HISTORY_BUCKETS
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

# 30. Cycle integrity and as-of eligibility

For a claimed complete-success cycle require:

```text
kind = ap_dynamic
state = completed
complete = true
result = success

finished_at != null
finished_at >= started_at
finished_at <= evaluated_at_utc

items_seen = items_stored
items_skipped = 0
error_count = 0
data_quality_warning_count = 0

source_rows_reported = items_seen
stored AP row count = items_stored
```

Any contradiction inside a cycle claiming complete-success is a source
integrity failure.

Do not silently downgrade corrupted truth to normal partial history.

Special valid case:

```text
items_seen = 0
items_stored = 0
items_skipped = 0
```

with all other complete-success invariants satisfied means:

```text
valid empty AP population
```

not missing data.

---

# 31. AP row and section temporal integrity

For every AP row of a non-empty canonical cycle:

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

Required source section timestamps must satisfy:

```text
cycle.started_at
<= source section timestamp
<= cycle.finished_at
<= evaluated_at_utc
```

Section timestamp integrity is required for rate evidence.

Section timestamps do NOT determine bucket membership; `sample_at` remains:

```text
cycle.finished_at
```

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

FINAL selects:

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

# 35. Bucket source-family coverage inputs and Site sample skew

For each bucket compute:

```text
canonical_cycle_count

wired_complete_site_cycle_count
lan_complete_site_cycle_count

wired_pair_valid_ap_opportunities
lan_pair_valid_ap_opportunities

total_ap_opportunities
```

A non-empty family has a complete Site sample only when:

```text
every AP in that canonical cycle
has valid Download + Upload pair
for that family
```

AND its AP source timestamps are temporally comparable.

Canonical v1 policy:

```text
MAX_SITE_SAMPLE_SOURCE_SKEW_SECONDS = 60
```

This is a versioned Historical Traffic semantic policy.

It MUST NOT depend on:

```text
WEB_ADMIN_HOME_TRAFFIC_MAX_AP_SKEW_SECONDS
```

and requires no new env setting.

For the candidate source family within one cycle compute:

```text
source_oldest_observed_at
source_newest_observed_at

source_skew_seconds =
source_newest_observed_at - source_oldest_observed_at
```

A complete Site numeric sample requires:

```text
source_skew_seconds <= 60
```

Boundary:

```text
< 60  → accepted
= 60  → accepted
> 60  → excluded as complete Site numeric sample
```

Skew exclusions remain visible in quality metadata.

---

# 36. Historical source-family selection — FINAL algorithm

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

    if lan_pair_valid_ap_opportunities > wired_pair_valid_ap_opportunities:
        selected_source = lan
        selection_reason = fallback_higher_coverage

    else:
        selected_source = wired
        selection_reason = primary_preferred_tie_or_higher
```

For a valid empty-population canonical cycle/bucket:

```text
selected_source = wired
selection_reason = empty_population
```

If there are no canonical cycles/samples at all:

```text
selected_source = null
selection_reason = no_canonical_samples
```

Source-family completeness counts MUST incorporate the 60-second Site-sample
source skew policy.

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

exists only when:

```text
all APs have valid Download + Upload pair
AND source_skew_seconds <= MAX_SITE_SAMPLE_SOURCE_SKEW_SECONDS
```

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

Canonical timestamp:

```text
sample_at = cycle.finished_at
```

If any AP pair is invalid or source skew exceeds 60 seconds:

```text
that cycle is excluded from bucket numeric mean
```

but its reasons/skew remain visible in quality metadata.

Valid empty population:

```text
items_seen = 0
items_stored = 0
items_skipped = 0
```

returns:

```text
download_mbps = 0.0
upload_mbps = 0.0
total_mbps = 0.0
selected_source = wired
```

This is valid zero evidence.

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

# 40. Bucket numeric aggregation — FINAL v1

For `TRAFFIC-02 History`, one bucket numeric value is:

```text
mean_of_complete_site_rate_samples
```

Specifically:

```text
download_mbps =
arithmetic mean of complete Site download samples

upload_mbps =
arithmetic mean of complete Site upload samples

total_mbps =
download_mbps + upload_mbps
```

Only complete Site samples for the bucket-selected source family participate.

Browser never recomputes this.

This is intentionally NOT described as:

```text
time-weighted average
canonical Period Average
```

`TRAFFIC-03 Period Average` remains a separate interval/time-aware semantic,
implemented later through an extension/aggregate method of the SAME
`HistoricalTrafficReadService`.

Forbidden future shortcut:

```text
average(bucket.download_mbps)
average(all sample rates)
→ call it canonical Period Average
```

without separate interval-aware proof.

---

# 41. TRAFFIC-03 Period Average boundary

`TRAFFIC-02-READ v1` does NOT reconstruct interval-weighted period averages only
to support future Period Statistics.

Permanent ownership:

```text
TRAFFIC-02 History bucket
→ mean_of_complete_site_rate_samples

TRAFFIC-03 Period Average
→ interval/time-aware calculation
→ implemented inside/through HistoricalTrafficReadService
→ not a new independent SQL/semantic owner
```

The future aggregate method may reuse persisted rates plus proven timing
evidence, but its exact formula belongs to the `TRAFFIC-03` architecture review.

This FINAL does not authorize a second rate formula or another Traffic
repository.

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

FINAL reuses the existing Analytics quality threshold:

```text
ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS
```

Current repository default:

```text
180 seconds
```

No new independent Traffic gap threshold is introduced in READ v1.

---

# 46. Bucket temporal gap fields

Each bucket exposes:

```text
first_complete_sample_at
last_complete_sample_at

leading_gap_seconds
trailing_gap_seconds
max_inter_sample_gap_seconds
gap_count_over_threshold
```

All sample timestamps above use:

```text
sample_at = cycle.finished_at
```

Gap calculations MUST NOT switch to wired/LAN section timestamps.

No interpolation occurs across an unacceptable gap.

The accepted gap threshold comes from:

```text
AnalyticsConfig.quality_gap_threshold_seconds
```

and is independent from the 60-second intra-cycle AP source skew policy.

---

# 47. Bucket completeness status and attempt semantics

Canonical bucket statuses:

```text
complete
partial
none
```

Collection attempt counters remain quality metadata.

A:

```text
failed
partial
shutdown
abandoned
running
```

attempt MUST NOT automatically make a bucket partial.

Instead, completeness is determined from actual accepted Site samples and the
gap contract.

## complete

```text
complete_site_sample_count > 0
AND requested bucket interval is covered without unacceptable
    leading/trailing/inter-sample gap
```

A failed/partial/abandoned attempt inside the bucket may coexist with
`status=complete` when the next accepted sample arrives without creating an
unacceptable evidence gap.

## partial

```text
complete_site_sample_count > 0
AND at least one unacceptable uncovered interval exists
```

Examples:

```text
leading gap > threshold
trailing gap > threshold
inter-sample gap > threshold
source/rate/skew exclusions produce an unacceptable evidence gap
```

## none

```text
complete_site_sample_count = 0
```

A running tail cycle is informational only and does not degrade a closed
historical bucket by itself.

---

# 48. Partial bucket numeric contract — FINAL

If:

```text
complete_site_sample_count > 0
```

then a partial bucket retains numeric values:

```text
download_mbps
upload_mbps
total_mbps
```

calculated only from complete Site samples, while:

```text
status = partial
```

If:

```text
complete_site_sample_count = 0
```

then:

```text
download_mbps = null
upload_mbps = null
total_mbps = null
status = none
```

A partial numeric bucket MUST NOT be treated downstream as a fully covered
interval.

`TRAFFIC-03`, `TRAFFIC-04` and `TRAFFIC-06` must apply their own
accepted-coverage policy through the same Historical Traffic semantic owner.

UI MUST NOT independently decide that a partial bucket is equivalent to complete
evidence.

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

# 50. Actual source coverage boundaries — FINAL as-of semantics

The read contract exposes:

```text
available_from_utc
available_through_utc
source_watermark_utc
```

Canonical meanings, all as-of `evaluated_at_utc`:

```text
available_from_utc
=
earliest integrity-valid complete Site sample available in persisted source
with sample_at <= evaluated_at_utc

available_through_utc
=
latest integrity-valid complete Site sample available in persisted source
with sample_at <= evaluated_at_utc

source_watermark_utc
=
latest integrity-valid canonical ap_dynamic cycle.finished_at
where finished_at <= evaluated_at_utc
```

`available_from_utc` / `available_through_utc` describe complete Site numeric
sample availability.

`source_watermark_utc` describes the newest integrity-valid canonical
`ap_dynamic` collection watermark even if that cycle is later excluded for the
bucket-selected source family's numeric sample because of source-specific
rate/skew evidence.

No boundary is inferred from configured retention alone:

```text
available_from != evaluated_at - retention_days
```

Future DB rows relative to evaluation time MUST NOT influence these values.

---

# 51. Historical source freshness / age semantics

Historical range age is NOT itself a freshness failure.

Example:

```text
querying a complete range from 10 days ago
```

does not become stale merely because the range is old.

Expose:

```text
source_watermark_utc
source_age_seconds
```

where:

```text
source_age_seconds =
evaluated_at_utc - source_watermark_utc
```

when a watermark exists.

As-of filtering guarantees:

```text
source_age_seconds >= 0
```

`TRAFFIC-02-READ v1` does not create another `fresh/stale/unavailable` threshold
taxonomy for historical range age.

Historical range completeness remains separate from current collection recency.

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

For requested bucket/range count Observation attempts:

```text
completed_success_count
completed_partial_count
completed_failed_count
completed_shutdown_count
abandoned_count
running_count
```

Counts are filtered:

```text
as-of evaluated_at_utc
```

Attempt counts are quality/provenance metadata.

Permanent rule:

```text
failed/partial/abandoned attempt
!= automatically partial bucket
```

Only an actual unacceptable evidence gap created by missing usable Site samples
changes bucket completeness.

Running tail cycle:

```text
informational only
```

and does not degrade a closed historical bucket by itself.

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

# 62. Canonical immutable DTO — FINAL

Canonical models:

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
no provider objects
no raw settings
```

The read DTO is the canonical application contract for future Traffic
consumers.

---

# 63. HistoricalTrafficRange — canonical fields

```text
site_id
from_utc
to_utc
evaluated_at_utc

bucket_seconds
bucket_count
bucket_alignment = range_start_utc

max_site_history_buckets = 720
max_site_sample_source_skew_seconds = 60

unit = Mbps
aggregation = mean_of_complete_site_rate_samples
metric_version = network_traffic_history.v1
source_kind = observation_ap_dynamic
sample_timestamp_semantics = cycle_finished_at
```

`bucket_count` follows the exact `ceil(range / bucket)` contract.

---

# 64. HistoricalTrafficBucket — canonical fields

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

selected_source_skew_excluded_sample_count
rate_reason_counts
```

`first_complete_sample_at` / `last_complete_sample_at` use:

```text
cycle.finished_at
```

No raw controller JSON.

---

# 65. HistoricalTrafficCoverage — canonical fields

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

Coverage boundaries and watermark are computed as-of:

```text
evaluated_at_utc
```

---

# 66. HistoricalTrafficSourceSelection — canonical fields

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

For selected complete Site samples also expose enough quality metadata to prove
the 60-second source skew policy, without exposing raw AP rows.

---

# 67. HistoricalTrafficQuality — canonical range fields

```text
partial_cycle_count
failed_cycle_count
shutdown_cycle_count
abandoned_cycle_count
running_cycle_count

no_baseline_count
counter_reset_count
gap_too_large_count
invalid_elapsed_count
source_unavailable_count

source_skew_excluded_sample_count
integrity_failure_count
```

A claimed complete-success cycle with an integrity contradiction is terminal
source-unavailable, not a normal returned partial result.

Collection attempt counters do not by themselves define bucket completeness.

---

# 68. DTO serializer boundary

`TRAFFIC-02-READ` is a backend read foundation.

FINAL decision:

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

Therefore FINAL verdict:

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

FINAL:

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

Before implementation acceptance, targeted tests must verify:

```text
EXPLAIN QUERY PLAN
```

uses existing useful source indexes and avoids an obviously unbounded accidental
Cartesian scan.

No index/schema change is authorized by this FINAL.

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

# 82. Exact implementation scope — FINAL

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

No Observation acquisition/storage/schema file should be changed.

No Analytics range-limit configuration change is required.

The 60-second source skew policy and
`MAX_SITE_HISTORY_BUCKETS = 720` may be versioned constants/policy inside the
Historical Traffic read domain; no new environment setting is required.

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

This FINAL intentionally needs no new environment setting.

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

`tests/analytics/test_historical_traffic.py` MUST prove at minimum:

```text
Site scope enforced

half-open [from,to)
cycle.finished_at used as sample_at
finished_at == from_utc included
finished_at == to_utc excluded
finished_at == bucket boundary → next bucket

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

selected-source AP skew:
below 60s → accepted
exactly 60s → accepted
above 60s → sample excluded

valid zero preserved
empty AP population → valid 0.0 / selected wired

missing data not zero

no-baseline counted
counter reset counted
gap-too-large counted
invalid elapsed counted
source unavailable reason counted
source-skew exclusion counted

no canonical samples
→ insufficient_data / coverage none

some usable buckets + unacceptable gaps
→ partial

all covered buckets
→ complete

failed/partial attempt without unacceptable gap
→ does not automatically destroy completeness

attempt causing unacceptable gap
→ partial

actual coverage boundaries returned as-of evaluated_at

future persisted cycle after evaluated_at
→ excluded from result and watermark
```

---

# 87. Required focused range / bucket tests

At minimum:

```text
24h → 300-second buckets → 288
7d  → 900-second buckets → 672
30d → 3600-second buckets → 720
180d → 21600-second buckets → 720
```

Also prove:

```text
final short bucket uses min(start + bucket, to_utc)

MAX_SITE_HISTORY_BUCKETS exact boundary:
720 → accepted

explicit bucket request producing:
721 → validation error

no generic 7-day rejection
no generic 31-day rejection

valid synthetic range >31d
→ accepted
when bounded bucket count and deadline are satisfied

dynamic whole-day fallback
→ deterministic ceil formula
→ bucket_count <= 720
```

---

# 88. Required focused gap / as-of tests

Prove:

```text
leading gap
trailing gap
inter-sample gap
gap threshold exact boundary
gap > threshold
```

No interpolation over unacceptable gaps.

Gap timestamps use:

```text
cycle.finished_at
```

not source section timestamps.

Also prove:

```text
old closed historical range
→ not stale merely because it is old

DB contains canonical cycle after evaluated_at
→ future cycle does not affect:
   requested history
   available_from_utc
   available_through_utc
   source_watermark_utc
   source_age_seconds

source_age_seconds
→ never negative
```

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

# 91. Coder focused command — FINAL

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

Owner + Tech Lead / Central Lab MUST re-evaluate the relevant targeted set
against the current repository test inventory at execution time.

Required semantic regression areas include at least:

```text
existing Analytics source gateway/read boundaries
CurrentTrafficReadService
TRAFFIC-00 Foundation
TRAFFIC-01 Current Network Throughput
Home Current Traffic compatibility
Traffic feature-flag independence
```

Reason:

```text
source_gateway.py
models.py
runtime.py
```

are shared boundaries.

Do not mechanically reuse an older targeted command as canonical after a new
read service/test set is added.

Coder does not run this broader Central Lab block.

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

Repository documentation currently records a V6-fixed Windows runner, but:

```text
documented gate version
!=
automatically current gate version
```

Before official execution Owner / Tech Lead verifies:

```text
exact candidate
exact baseline
known compatibility baseline
current test set
TASK-specific cross-surface invariants
approved runner
```

Acceptance includes:

```text
targeted regression
full approved regression
baseline/candidate differential
strict regressions classification
compileall
git diff --check
exact artifact immutability
official PASS/FAIL
```

Infrastructure failure before test logic is repaired/retried before being
classified as an implementation regression.

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

No implementation is authorized by this FINAL.

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

Do not prepare a coder FINAL for History against this FINAL assumption.

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

# 104. Review Point A — RESOLVED: History bucket aggregation

FINAL decision:

```text
TRAFFIC-02 History bucket
=
mean_of_complete_site_rate_samples
```

Accepted because it:

```text
uses persisted derived rate truth
is deterministic
does not treat missing time as zero
does not reimplement the Observation rate formula
```

Hard boundary:

```text
this is NOT canonical TRAFFIC-03 Period Average
```

Future:

```text
TRAFFIC-03 Period Average
→ interval/time-aware
→ implemented inside/through HistoricalTrafficReadService
→ may use a separate aggregate method
→ no independent SQL/semantic owner
```

`TRAFFIC-03` is forbidden to simply average History buckets or raw sample rates
and label that result canonical Period Average without interval-aware proof.

---

# 105. Review Point B — RESOLVED: Site history bound

FINAL constant:

```text
MAX_SITE_HISTORY_BUCKETS = 720
```

Scope is explicitly:

```text
Site historical time-series v1
```

It is NOT a generic future limit for:

```text
per-AP series
AP cardinality
TRAFFIC-05 payload
TRAFFIC-06 payload
```

Accepted common resolutions:

```text
24h  → 300s   → 288
7d   → 900s   → 672
30d  → 3600s  → 720
180d → 21600s → 720
```

Longer-range fallback is deterministic:

```text
required_seconds =
ceil(range_seconds / MAX_SITE_HISTORY_BUCKETS)

bucket_seconds =
ceil(required_seconds / 86400) * 86400
```

and must still satisfy:

```text
bucket_count <= 720
```

---

# 106. Review Point C — RESOLVED: partial numeric bucket

FINAL rule:

```text
if complete_site_sample_count > 0:
    download/upload/total =
        mean only over complete Site samples
    status = partial

if complete_site_sample_count == 0:
    download_mbps = null
    upload_mbps = null
    total_mbps = null
    status = none
```

Partial numeric value:

```text
!= fully covered interval
```

Downstream `TRAFFIC-03 / 04 / 06` must apply their own accepted-coverage policy
through the same Historical Traffic semantic owner.

The UI does not decide this semantic.

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

# 108. FINAL acceptance contract

This FINAL is considered architecture-complete with the following locked
decisions:

1. Observation AP history is canonical product source.
2. No new acquisition path.
3. No derived Traffic DB.
4. `HistoricalTrafficReadService` is the single historical semantic owner.
5. Existing 7d/31d Analytics ceilings are not Historical Traffic ceilings.
6. Range is bounded by actual coverage/performance/output cardinality.
7. UTC half-open `[from,to)` is canonical.
8. `sample_at = ap_dynamic cycle.finished_at`.
9. `sample_at` controls range membership, bucket membership and gaps.
10. Range-start fixed-duration buckets are canonical v1.
11. Final bucket may be short.
12. `MAX_SITE_HISTORY_BUCKETS = 720`.
13. Dynamic long-range bucket fallback uses the exact whole-day ceil formula.
14. One source-family decision per Site bucket.
15. Wired/LAN mixing inside a bucket is forbidden.
16. Source transitions between buckets are allowed with provenance.
17. Complete Site sample requires all AP pairs valid.
18. Complete Site sample requires source skew `<= 60s`.
19. Empty AP population is valid zero with source `wired`.
20. Missing evidence is not zero.
21. History bucket aggregation is `mean_of_complete_site_rate_samples`.
22. History sample-mean is not TRAFFIC-03 canonical Period Average.
23. Attempt failures affect completeness only through actual gap/coverage impact.
24. Running tail attempts are informational.
25. Partial bucket may retain numeric mean when at least one complete Site sample exists.
26. Zero complete Site samples means null metrics / status `none`.
27. Coverage/watermark calculations are as-of `evaluated_at_utc`.
28. Future persisted cycles relative to evaluation are ignored.
29. Historical source age is separate from historical range completeness.
30. Native Omada history remains validation/reference only.
31. No Admin/UI code is included in READ foundation.
32. Traffic Foundation coordinator remains untouched.
33. Future security/feature boundary is preserved.
34. No new feature flag is required.
35. Coder testing is focused/minimal only.
36. Central Lab owns cross-module/broader/full acceptance.
37. Repository FINAL baseline is `0d00a912...`.
38. Production remains `8f3ad597...` and docs-only drift is explicit.
39. Merge/deploy/activation remain separately authorized.
40. This FINAL itself does not grant implementation authorization.

---

# 109. Final status

```text
TASK:
TRAFFIC-02-READ — Historical Network Traffic Read Foundation

STATUS:
FINAL — TECH LEAD REVIEW INCORPORATED
READY FOR EXPLICIT OWNER IMPLEMENTATION AUTHORIZATION

REPOSITORY BASELINE:
main@0d00a9127c0b393bf2c7b57aa5bde103c13119db

REPOSITORY TREE:
9bc737a7d2978f4345fd6b6bb7a0edfea08d019f

PRODUCTION RUNTIME HEAD:
8f3ad59771f72c49834b1012963de6d94b9e0d18

PRODUCTION RUNTIME TREE:
2ef8bf264a008259242cde0778d0ebd20fa94b9e

REPOSITORY / PRODUCTION DRIFT:
DOCS-ONLY / ACCEPTED

CANONICAL SOURCE:
Observation persisted AP dynamic history

CANONICAL SAMPLE TIMESTAMP:
ap_dynamic cycle.finished_at

MAX SITE HISTORY BUCKETS:
720

MAX SITE SAMPLE SOURCE SKEW:
60 seconds

HISTORY BUCKET AGGREGATION:
mean_of_complete_site_rate_samples

NEW ACQUISITION:
NO

NEW DB / SCHEMA:
NO

ADMIN / UI:
OUT OF SCOPE

IMPLEMENTATION AUTHORIZATION:
NOT GRANTED BY THIS FINAL

BRANCH / CODE / COMMIT / PUSH / PR / MERGE:
NOT AUTHORIZED BY THIS FINAL

PRODUCTION ACTIVATION:
NOT GRANTED
```

Next governance action:

```text
explicit Owner implementation authorization
```

Only after that may Coder implement this FINAL against the exact revalidated
`origin/main` baseline.

---

