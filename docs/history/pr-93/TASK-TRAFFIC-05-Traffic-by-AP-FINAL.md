# TASK-TRAFFIC-05 — Traffic by AP — FINAL

**Проект:** CaptivPortal  
**Area:** Admin Console → Traffic  
**Canonical Roadmap item:** `TRAFFIC-05 — Traffic by AP`  
**Dependencies:** `TRAFFIC-00`, `TRAFFIC-01`, `TRAFFIC-02-READ`, `TRAFFIC-02`, `TASK-TRAFFIC-02-PERF-01`, `TRAFFIC-03`, `TRAFFIC-04`  
**Тип:** architecture / bounded all-AP Historical Network Traffic projection + existing Current AP Traffic composition + Traffic UI functional contract  
**Статус:** `FINAL — OWNER + TECH LEAD REVIEW INCORPORATED / ARCHITECTURE APPROVED`  
**Implementation authorization:** `NOT GRANTED BY THIS FINAL; REQUIRES SEPARATE OWNER AUTHORIZATION`  
**Code / patch / commit / push / PR / merge:** `NOT AUTHORIZED`  
**Production deployment / activation:** `NOT AUTHORIZED`  
**Prepared:** 2026-08-31

---

# 0. Executive decision

`TRAFFIC-05` реализует следующий canonical Traffic product:

```text
Admin Console → Traffic → Traffic by AP
```

Ключевой Owner product invariant:

```text
ALL APs in the supported product population
MUST be visible simultaneously.
```

Для каждой AP одновременно показываются:

```text
AP identity

Download history
Upload history

Now:
Download
Upload
Total

Average:
Download
Upload
Total

Peak:
Download
Upload
Total

Coverage
```

Unit:

```text
Mbps
```

Permanent product domain:

```text
NETWORK TRAFFIC
```

Meaning:

```text
persisted Site AP/network throughput evidence
```

Forbidden meanings:

```text
Internet Traffic
WAN Traffic
billing traffic
Guest Traffic
Guest Session Traffic
SSID Traffic
Zefer_Parki Traffic
traffic volume MB/GB
```

Canonical historical owner remains:

```text
HistoricalTrafficReadService
```

Canonical current AP `Now` owner remains:

```text
CurrentTrafficReadService
```

No third Traffic semantic owner is introduced.

This FINAL explicitly removes:

```text
selected AP UX
AP selector replacing another AP
one-AP-at-a-time chart model
product pagination
AP cursor
Next / Previous
ap_limit
ap_cursor
```

---

# 1. Exact repository baseline

Repository was re-fetched immediately before issuing this FINAL.

```text
origin/main =
f58679351fa6cd8558f67234937a7706fb4f3dae

tree =
d22c54100d80540e4cc9506b3f51323d7ee8201c
```

Current main:

```text
Merge PR #92
Docs: reconcile TRAFFIC-04 production state
```

PR #92 is documentation/current-state reconciliation only.

Accepted runtime / production checkpoint remains:

```text
a9cd8a9b9b9efc46bc82d315385ebbd1a3bf63b0

tree =
f53f204cf3ebf7cecf4e872ce450b4f3f4265cc9
```

Therefore:

```text
repository main
!=
production runtime HEAD

runtime code drift from PR #92 =
NONE
```

Before any implementation authorization:

```text
re-fetch origin/main
re-pin SHA/tree
perform impact review
```

Mandatory impact review if newer main touches:

```text
app/analytics/**
app/admin_web/**
app/observations/**
app/config.py
app/settings.py
run.py
```

---

# 2. Current accepted Traffic chain

Treat as accepted predecessors:

```text
TRAFFIC-00 — Traffic Section Foundation
DONE / PRODUCTION ACTIVE

TRAFFIC-01 — Current Network Throughput
DONE / PRODUCTION ACTIVE

TRAFFIC-02-READ — Historical Network Traffic Read Foundation
DONE / ACCEPTED

TRAFFIC-02 — Network Traffic History
DONE / PRODUCTION ACTIVE

TRAFFIC-02-PERF-01
DONE / PRODUCTION REMEDIATION ACTIVE

TRAFFIC-03 — Period Statistics
DONE / PRODUCTION ACTIVE

TRAFFIC-04 — Peak Load
CLOSED / PRODUCTION PASS / ACTIVE
```

TRAFFIC-05 MUST NOT redesign or duplicate those capabilities.

---

# 3. Existing architecture to preserve

Current Traffic architecture already has:

```text
one Traffic page coordinator

one shared Network range:
24h | 7d

one combined historical request path
for:
History
Statistics
Peak

bounded Admin concurrency
bounded Admin QueryDeadline
bounded Admin response bytes

fail-closed configuration
feature flags default false
deploy and activation separated
```

TRAFFIC-05 remains inside these boundaries.

---

# 4. Product correction from DRAFT R1

DRAFT R1 proposed:

```text
one selected AP at a time
AP selection
one selected AP chart
product pagination
```

This is rejected.

FINAL canonical product model:

```text
AP-1
  D/U history chart
  Now
  Average
  Peak
  Coverage

AP-2
  D/U history chart
  Now
  Average
  Peak
  Coverage

...

AP-N
  D/U history chart
  Now
  Average
  Peak
  Coverage
```

All supported APs render on the same Traffic page simultaneously.

---

# 5. No selected-AP state

TRAFFIC-05 v1 has NO product state:

```text
selected_ap
selected_ap_mac
active AP
AP selector
```

No AP replaces another AP in the functional product.

Every returned AP has its own chart and metrics.

---

# 6. Chart-series contract

For each AP:

```text
visible chart count per AP = 1

series per AP chart = 2

series:
Download
Upload
```

If supported AP count is `N`:

```text
visible AP charts = N

visible history series = 2N
```

There is no single shared chart containing all AP lines.

---

# 7. Roadmap binding

Roadmap-required TRAFFIC-05 outcomes remain:

```text
AP identity

Download history
Upload history

Now

Average
Peak

Coverage
```

Shared:

```text
24h / 7d Network range
```

TRAFFIC-06 remains separate:

```text
AP Traffic Share
```

---

# 8. Architecture options after Owner correction

All-AP requirement changes the Option C proof.

Three options were re-evaluated.

## Option A — separate automatic AP historical request

```text
History request
+
Traffic-by-AP request
```

Rejected as default because it introduces:

```text
third automatic Traffic product request

possible concurrent expensive historical scans

extra Admin concurrency pressure

higher 429/query_deadline risk
```

## Option B — full AP data embedded naively as repeated bucket objects

Rejected because repeating for every AP:

```text
bucket_start
bucket_end
selected_source
field names
```

for all 672 7d points causes unnecessary payload expansion.

## Option C-R2 — RECOMMENDED

```text
existing combined History request
        ↓
same HistoricalTrafficReadService execution
        ↓
Site History / Statistics / Peak
        +
complete supported all-AP projection
```

with:

```text
compact bucket-aligned AP series representation
```

This preserves:

```text
one historical HTTP request

one HistoricalTrafficReadService owner

one shared Network range

one Traffic coordinator

one shared QueryDeadline

no automatic third historical request
```

FINAL selects:

```text
OPTION C-R2
```

as architectural recommendation.

---

# 9. Canonical historical owner

Historical per-AP semantics are a bounded projection inside:

```text
HistoricalTrafficReadService
```

Allowed extension:

```text
HistoricalTrafficReadService
→ all-AP projection
```

Forbidden:

```text
ApTrafficHistoryService as second semantic owner

TrafficByApRepository

direct Admin SQL calculation

browser historical calculation
```

---

# 10. Canonical current `Now` owner

Current repository already has:

```text
CurrentTrafficReadService.list_current_ap_traffic(...)
```

with accepted per-AP semantics:

```text
AP MAC
name

Download
Upload
Total

rate reasons
rate status

observed timestamp
age

selected Site source
```

TRAFFIC-05 MUST reuse these semantics.

Permanent:

```text
Now
!=
last Historical bucket
```

---

# 11. Bounded current all-AP composition

Because TRAFFIC-05 needs all supported APs simultaneously, implementation may add
a narrow bounded read method inside `CurrentTrafficReadService`, conceptually:

```python
get_current_ap_traffic_for_population(
    site_id,
    ap_macs,
    ...existing current policy...,
    deadline,
)
```

Requirements:

```text
input AP count <= 12

same source-selection owner

same freshness policy

same rate values

same rate reasons/status

same current snapshot integrity rules
```

This is reuse of the current owner, not a second calculation owner.

---

# 12. Product AP population — FINAL R2 proposal

For selected Site and selected Network range:

```text
TRAFFIC_BY_AP_POPULATION
=
CURRENT_ACCEPTED_AP_POPULATION
UNION
HISTORICAL_VALIDATED_AP_POPULATION
```

Machine identity:

```text
ap_mac
```

Union is de-duplicated by canonical AP MAC.

---

# 13. Current accepted AP population

Canonical current population is:

```text
all AP identities present in the accepted complete Current Traffic AP snapshot
```

An AP remains in current population even if its current selected-source rate is:

```text
partial
unavailable
```

because AP identity and current evidence are still product-relevant.

If there is no accepted current snapshot:

```text
current population = empty set
```

This does not invalidate historical AP population.

---

# 14. Historical validated AP population

Canonical historical population is:

```text
distinct canonical AP MACs present in validated canonical AP dynamic cycles
inside requested [from_utc,to_utc)
```

Population identity does NOT require that the AP has a valid Traffic pair.

Therefore an AP with:

```text
identity present
selected-source Traffic unavailable
```

remains in product population and may show:

```text
History partial / insufficient_data
```

rather than disappearing.

---

# 15. Why union population is required

Example:

```text
AP-X is installed now

Current Now = valid

but AP-X was added recently
and has little/no 7d History
```

Required:

```text
AP-X visible

Now = valid

History = partial / insufficient_data
```

Forbidden:

```text
hide AP-X because it lacks old historical evidence
```

Likewise a historical AP removed from current deployment may remain visible for a
range containing its historical evidence:

```text
History = usable
Now = unavailable
```

---

# 16. Population range dependence

Because historical population is range-scoped:

```text
24h population
may differ from
7d population
```

Current population is unioned into both.

Therefore:

```text
24h can be supported
while 7d can exceed supported bound
```

or vice versa.

This is valid.

---

# 17. Supported AP hard cardinality bound

FINAL freezes v1:

```text
MAX_TRAFFIC_BY_AP_SUPPORTED_APS = 12
```

This is an architecture constant.

It is NOT an operator-tunable environment setting.

Changing it later requires:

```text
architecture review
payload proof
PERF proof
frontend proof
```

---

# 18. Why the bound is 12 and not arbitrary

Current platform hard response limit:

```text
WEB_ADMIN_MAX_RESPONSE_BYTES = 1,048,576 bytes
```

7d Site History already returns:

```text
672 canonical Site buckets
```

Naively repeating full Site-style bucket objects per AP is rejected.

FINAL uses a compact aligned representation described below.

A conservative structural model with:

```text
672 points/AP

status[]
download_mbps[]
upload_mbps[]

long finite numeric representations
long AP display name
full Now/Average/Peak/Coverage metadata
```

is approximately:

```text
~34 KiB per AP
```

before ordinary envelope variation.

Twelve APs:

```text
12 × 672 = 8,064 AP bucket positions

12 × 672 × 2
= 16,128 Download/Upload metric points
```

The combined all-AP payload remains inside a conservative sub-1MiB product
budget with meaningful headroom, while higher counts approach the response and
rendering budget too closely.

Therefore v1 freezes:

```text
12 AP
```

rather than selecting the mathematically largest count that might barely fit.

Candidate implementation MUST still prove exact serialized size and PERF.

---

# 19. Hard bound is a product support contract

For population count:

```text
0..12
```

TRAFFIC-05 must return:

```text
ALL population APs
```

simultaneously.

For population count:

```text
>12
```

TRAFFIC-05 MUST NOT:

```text
return first 12

silently truncate

paginate product population

hide APs

pretend population is complete
```

---

# 20. Population exceeded semantics

When:

```text
population_count > 12
```

combined historical request remains product-safe:

```text
HTTP 200
```

for already-valid:

```text
History
Statistics
Peak
```

and returns:

```text
ap_traffic.status =
unsupported_population
```

with:

```text
supported_max_ap_count = 12

population_count = exact detected union count

returned_ap_count = 0

population_complete = false

items = []
```

No AP subset is returned.

---

# 21. Why unsupported population is AP-local

Population >12 is not:

```text
source failure
authentication failure
invalid request
History failure
```

Therefore it must not unnecessarily break:

```text
History
Statistics
Peak
```

The AP panel clearly says the AP population exceeds the supported v1 bound.

---

# 22. AP population status values

Top-level `ap_traffic.status` allowed:

```text
ok
partial
insufficient_data
unsupported_population
```

`unsupported_population` is structurally distinct from data quality.

---

# 23. Population metadata

`ap_traffic.population` minimum:

```text
population_method =
current_union_historical_validated.v1

population_count

current_population_count

historical_population_count

supported_max_ap_count = 12

returned_ap_count

population_complete
```

When population <=12:

```text
returned_ap_count = population_count
population_complete = true
```

When population >12:

```text
returned_ap_count = 0
population_complete = false
```

---

# 24. AP identity order

When supported:

```text
all AP items ordered by canonical AP MAC ascending
```

Frozen:

```text
ap_order_method =
ap_mac_ascending.v1
```

No traffic-based ordering in v1.

---

# 25. AP display name

Accepted review decision:

```text
1. current accepted AP name, if non-empty
2. latest non-empty historical AP name inside selected range
3. AP MAC
```

Return:

```text
display_name
display_name_source =
current
|
historical
|
mac_fallback
```

Name never affects identity, calculation, ordering or source selection.

---

# 26. Historical Site source-family invariant

Current historical contract remains authoritative.

Each Site History bucket chooses:

```text
selected_source =
wired
|
lan
|
null
```

One usable Site bucket uses one source family.

Source may change between buckets.

---

# 27. Critical per-AP source rule

All AP historical values in a Site bucket inherit the Site bucket's source family.

Example:

```text
Site bucket selected_source = wired
```

then:

```text
AP-1 → wired
AP-2 → wired
AP-3 → wired
...
```

If AP-2 lacks accepted wired evidence:

```text
AP-2 point = partial / none
```

Forbidden:

```text
AP-2 silently falls back to LAN
inside a wired Site bucket
```

---

# 28. No per-AP independent fallback

TRAFFIC-05 does not choose:

```text
best source per AP
```

It consumes:

```text
canonical Site bucket source
```

This preserves comparability and future TRAFFIC-06 semantics.

---

# 29. AP historical bucket opportunity population

For AP `A` and Site bucket `B`:

```text
opportunity_sample_count =
outer Site bucket complete_site_sample_count
```

An AP sample is accepted only when:

```text
same Site
same AP MAC
same canonical accepted Site sample/cycle
valid pair for Site-bucket selected_source
```

---

# 30. AP point status

Allowed per aligned bucket position:

```text
complete
partial
none
```

`none`:

```text
no accepted AP sample
D/U = null
```

`complete`:

```text
all canonical Site sample opportunities
have accepted AP selected-source evidence
```

`partial`:

```text
some but not all canonical Site sample opportunities
have accepted AP selected-source evidence
```

or AP-specific temporal evidence prevents complete comparability.

Missing is never zero.

---

# 31. AP History bucket numeric method

When accepted AP samples exist:

```text
Download =
mean of accepted AP Download rates
for canonical Site bucket sample opportunities

Upload =
mean of accepted AP Upload rates
for the same accepted AP sample subset
```

Frozen method:

```text
mean_of_accepted_ap_rates_for_canonical_site_bucket_samples.v1
```

No History `Total` array is needed by v1 chart.

Backend still owns any Total needed for aggregate identities/tests.

---

# 32. Complete-bucket additive identity

Mandatory semantic identity for deterministic complete fixture:

When every AP is complete over the exact same Site sample population:

```text
Σ AP Download bucket means
=
Site Download bucket mean

Σ AP Upload bucket means
=
Site Upload bucket mean

Σ AP Total bucket means
=
Site Total bucket mean
```

within accepted float tolerance.

If AP evidence is partial:

```text
no additive completeness claim
```

---

# 33. AP History compact all-AP representation

To support all APs without duplicating outer timestamps/source metadata,
TRAFFIC-05 uses:

```text
outer Site History buckets
as canonical timeline and source context
```

Each AP supplies only aligned columns.

Proposed:

```text
history.series.encoding =
outer_history_bucket_aligned_du.v1

history.series.bucket_count =
outer result.range.bucket_count

history.series.status[]
history.series.download_mbps[]
history.series.upload_mbps[]
```

All three arrays have exact length:

```text
288 for 24h
672 for 7d
```

---

# 34. Alignment invariant

For every index `i`:

```text
AP history.series.*[i]
corresponds exactly to
result.buckets[i]
```

Therefore AP series does NOT repeat:

```text
bucket_start_utc
bucket_end_utc
selected_source
```

These remain canonical in the outer Site bucket.

---

# 35. Browser calculation boundary

Using aligned Site bucket timestamps for X-axis placement is presentation logic.

Browser MUST NOT calculate:

```text
AP Average

AP Peak

AP Traffic Total metric

source selection

coverage status

population status
```

Those are backend-owned.

---

# 36. Valid zero vs missing

Accepted AP rate:

```text
0.0 Mbps
```

is serialized as numeric zero.

Missing/invalid evidence:

```text
null
```

Status array distinguishes:

```text
complete / partial / none
```

Browser MUST NOT convert null into zero.

---

# 37. AP Period Average

Accepted review decision:

```text
average_method =
right_endpoint_ap_sample_hold_time_weighted.v1
```

It is NOT:

```text
average(AP History bucket means)
```

---

# 38. AP Average interval eligibility

An AP interval contributes only when:

```text
corresponding canonical Site interval is accepted

Site source family remains comparable

AP has accepted selected-source evidence required
for that interval
```

No:

```text
gap fill
source-transition fill
absence fill
zero fill
```

---

# 39. AP Average formula

For accepted intervals:

```text
Δ_i =
canonical Site sample interval

D_i =
right-endpoint AP Download

U_i =
right-endpoint AP Upload

T_i =
D_i + U_i
```

Then:

```text
Average Download =
Σ(D_i × Δ_i) / ΣΔ_i

Average Upload =
Σ(U_i × Δ_i) / ΣΔ_i

Average Total =
Σ(T_i × Δ_i) / ΣΔ_i
```

If:

```text
ap_accepted_interval_seconds = 0
```

then:

```text
Average D/U/Total = null
```

---

# 40. AP Average Total invariant

Backend serializer validates:

```text
Average Total
≈
Average Download + Average Upload
```

for the exact same accepted interval set.

Browser does not compute Total.

---

# 41. AP Average coverage

Return:

```text
site_accepted_interval_seconds
ap_accepted_interval_seconds
ap_interval_coverage_ratio
```

When Site denominator >0:

```text
ap_interval_coverage_ratio =
ap_accepted_interval_seconds
/
site_accepted_interval_seconds
```

This is evidence coverage, not:

```text
Health
SLA
Traffic Share
```

---

# 42. AP Peak

Accepted review decision:

```text
peak_method =
max_accepted_complete_ap_sample.v1
```

Population:

```text
accepted canonical Site samples
where this AP has valid selected-source pair evidence
```

---

# 43. AP Peak metrics

```text
Peak Download =
max(AP Download sample)

Peak Upload =
max(AP Upload sample)

Peak Total =
max(AP Download + AP Upload at the same sample)
```

Permanent:

```text
Peak Total
!=
Peak Download + Peak Upload
```

unless maxima naturally occur at the same sample.

---

# 44. AP Peak timestamps excluded

Accepted review decision:

```text
NO AP Peak timestamp in TRAFFIC-05 v1
```

TRAFFIC-04 already owns Site-wide temporal Peak product.

---

# 45. AP historical coverage summary

Per AP minimum:

```text
status

bucket_count
complete_bucket_count
partial_bucket_count
missing_bucket_count

sample_opportunity_count
accepted_sample_count

site_accepted_interval_seconds
ap_accepted_interval_seconds
ap_interval_coverage_ratio

no_baseline_count
counter_reset_count
gap_too_large_count
invalid_elapsed_count
source_unavailable_count

missing_selected_source_sample_count
source_transition_excluded_interval_count
```

---

# 46. AP historical item status

Allowed:

```text
complete
partial
insufficient_data
```

`complete`:

```text
outer History ok
and all required AP bucket/sample/interval evidence complete
```

`partial`:

```text
some trustworthy AP historical metric exists
but full-range comparability is incomplete
```

`insufficient_data`:

```text
AP identity exists in product population
but no usable historical numeric Traffic evidence exists
```

---

# 47. Current AP Now contract

Each AP item includes:

```text
now.status =
valid
|
partial
|
unavailable

download_mbps
upload_mbps
total_mbps

download_reason
upload_reason

observed_at
age_seconds

selected_source
```

These remain existing CurrentTrafficReadService semantics.

---

# 48. Current AP absent

Historical AP may not exist in the current accepted snapshot.

Then:

```text
Now status = unavailable
D/U/Total = null
```

No History fallback.

---

# 49. Current-only AP

Current AP may have no historical Traffic in selected range.

Then:

```text
AP remains visible

Now may be valid

History series = all none/null as appropriate

Average = null
Peak = null

History status = insufficient_data
```

This is a primary reason for union population.

---

# 50. Current vs historical evaluation identity

Historical:

```text
range.evaluated_at_utc
```

Current:

```text
current_snapshot.evaluated_at
```

These MAY differ.

Likewise:

```text
current selected_source
may differ from
last historical bucket selected_source
```

UI must represent provenance truthfully.

---

# 51. AP Traffic top-level successful states

When population <=12:

```text
ok
partial
insufficient_data
```

`ok` requires:

```text
all population APs returned
population_complete=true
outer History ok
all AP historical statuses complete
current snapshot fresh
all AP Now statuses valid
```

`partial` means trustworthy data exists but one or more required dimensions are
partial/stale/unavailable.

`insufficient_data` means product population is supported but no usable numeric
AP Traffic evidence exists.

---

# 52. All-AP response shape

Existing History response remains canonical.

Optional:

```text
result.ap_traffic
```

contains:

```text
status

metric_version
unit

population

history_series_encoding

history_bucket_method
average_method
peak_method
ap_order_method

current_snapshot

items[]
```

When supported:

```text
items.length = population.population_count
```

No page object.

---

# 53. DTO method identifiers

Proposed/frozen for R2:

```text
metric_version =
network_traffic_by_ap.v1

unit =
Mbps

population_method =
current_union_historical_validated.v1

history_series_encoding =
outer_history_bucket_aligned_du.v1

history_bucket_method =
mean_of_accepted_ap_rates_for_canonical_site_bucket_samples.v1

average_method =
right_endpoint_ap_sample_hold_time_weighted.v1

peak_method =
max_accepted_complete_ap_sample.v1

ap_order_method =
ap_mac_ascending.v1
```

---

# 54. AP item DTO

Conceptually:

```text
ap_mac
display_name
display_name_source

status

history:
  status

  series:
    encoding
    bucket_count
    status[]
    download_mbps[]
    upload_mbps[]

  average:
    download_mbps
    upload_mbps
    total_mbps

  peak:
    download_mbps
    upload_mbps
    total_mbps

  coverage:
    ...

now:
  status
  download_mbps
  upload_mbps
  total_mbps
  download_reason
  upload_reason
  observed_at
  age_seconds
  selected_source
```

---

# 55. Unsupported population DTO

When population >12:

```text
ap_traffic = {
  status: "unsupported_population",
  metric_version: "network_traffic_by_ap.v1",
  unit: "Mbps",
  population: {
    population_method: "current_union_historical_validated.v1",
    population_count: N,
    current_population_count: ...,
    historical_population_count: ...,
    supported_max_ap_count: 12,
    returned_ap_count: 0,
    population_complete: false
  },
  items: []
}
```

No partial first 12 items.

---

# 56. API design

Keep existing:

```text
GET /admin/api/v1/sites/<site_id>/traffic/history
```

Existing include forms:

```text
<absent>
statistics
statistics,peak
```

New exact forms:

```text
aps
statistics,aps
statistics,peak,aps
```

Canonical token ordering remains exact.

---

# 57. Removed API contracts from R1

FINAL explicitly removes:

```text
ap_limit
ap_cursor
page.next_cursor
AP cursor
cursor stack
Previous / Next
cursor-pinned AP pagination
```

No user-visible or hidden AP pagination is required.

---

# 58. No hidden backend pagination product behavior

Implementation MAY internally stream/batch SQL rows to bound memory.

But internal batching MUST NOT affect API semantics.

Required:

```text
one supported response
contains entire supported population
```

Internal implementation batching cannot create:

```text
partial population API pages
```

---

# 59. Initial request with all active Traffic products

When By-AP is enabled:

```text
GET .../traffic/history
?range=24h
&include=statistics,peak,aps
```

or 7d.

Normal page load:

```text
1 Current Network Throughput request
+
1 combined historical request
```

No automatic third AP request.

---

# 60. Shared Network range

TRAFFIC-05 consumes:

```text
window.CaptivPortalTrafficNetworkRange
```

existing:

```text
24h
7d
```

No second AP range selector.

Range change:

```text
one admitted combined historical refresh
```

All AP cards update together.

---

# 61. Frontend ownership

TRAFFIC-05 remains inside existing:

```text
network-traffic-history
```

coordinator execution.

No new:

```text
registerPanel network loader

fetch()

timer

AbortController

visibility owner

pagehide owner

retry/backoff owner
```

---

# 62. All-AP simultaneous rendering invariant

When:

```text
population_count <= 12
```

DOM must contain a functional AP representation for:

```text
every returned AP
```

simultaneously.

No AP is hidden behind:

```text
selector
tab replacement
Next
Previous
Load more
```

Visual collapsing for design purposes is not authorized in this functional TASK
if it prevents simultaneous information availability.

---

# 63. Functional AP card

Each AP gets its own functional block:

```text
AP identity

D/U History chart

Now D/U/Total

Average D/U/Total

Peak D/U/Total

Coverage
```

All cards exist on same page.

Final styling is separate Web Designer work.

---

# 64. Frontend render budget

At hard supported maximum:

```text
AP cards = 12

charts = 12

series = 24

7d bucket positions = 8,064

D/U metric values = 16,128
```

Frontend MUST NOT create a DOM node per sample.

---

# 65. Chart implementation performance contract

Recommended functional implementation:

```text
one SVG per AP

one path for Download

one path for Upload
```

Gaps are represented inside path data using multiple move segments.

Do NOT render:

```text
circle per sample
span per sample
SVG element per sample
```

Maximum primary line path elements:

```text
24
```

at 12 AP.

Axes/labels may add bounded ordinary elements.

---

# 66. Chart missing/partial semantics

`none` aligned point:

```text
line gap
```

not zero.

Partial numeric point may be plotted but must have an accessible/textual evidence
qualifier in AP Coverage/state.

Critical completeness meaning must not rely only on color.

---

# 67. Browser calculations forbidden

Browser does NOT calculate:

```text
Now Total

Average

Average Total

Peak

Peak Total

Coverage

population

source family

AP historical source fallback

Traffic Share
```

It only:

```text
validates safe DTO
formats backend values
maps aligned history values onto chart coordinates
```

---

# 68. TRAFFIC-06 boundary

No:

```text
share_percent
traffic_share
contribution %
AP ranking by share
```

in TRAFFIC-05.

Future:

```text
TRAFFIC-06 — AP Traffic Share
```

owns this.

---


# 69. TENANT-READINESS / SITE DATA ISOLATION

TRAFFIC-05 is strictly:

```text
Site-scoped
```

The already-authorized canonical:

```text
site_id
```

is the data-isolation boundary for the entire TRAFFIC-05 request.

Permanent invariant:

```text
authorized canonical Site
        ↓
TRAFFIC-05 population / metrics / response
        ↓
evidence from that Site only
```

TRAFFIC-05 AP population, Current AP evidence, Historical AP evidence, History,
Average, Peak and Coverage MUST contain evidence only from that canonical Site.

TRAFFIC-05 MUST NOT:

```text
enumerate AP identities from another Site

count APs from another Site

aggregate Traffic from another Site

use another Site's AP to influence population status

serialize another Site's AP identity

serialize another Site's Now

serialize another Site's History

serialize another Site's Average

serialize another Site's Peak

serialize another Site's Coverage

leak another Site's cardinality through response metadata or telemetry
```

Frontend visibility/filtering is NOT an authorization boundary.

A browser-side Site filter cannot repair or enforce Site isolation.

Site isolation must already be true before the DTO reaches presentation.

---

# 70. Supported 12-AP bound is per authorized canonical Site

Permanent:

```text
MAX_TRAFFIC_BY_AP_SUPPORTED_APS = 12
```

means:

```text
12 AP
PER authorized canonical Site request
```

It does NOT mean:

```text
12 per Tenant

12 per Controller

12 globally across CaptivPortal

12 across every Site visible to the Principal
```

Example future topology:

```text
Tenant A

Site A1 = 7 AP
Site A2 = 9 AP
```

does NOT create:

```text
16-AP TRAFFIC-05 population
```

Instead independent Site requests remain:

```text
Site A1 request
→ population_count = 7

Site A2 request
→ population_count = 9
```

unless a future separately authorized cross-Site product is explicitly designed.

TRAFFIC-05 is not a cross-Site product.

---

# 71. Future Principal / Tenant / RBAC compatibility

Current Admin authorization may continue using the accepted present-day model:

```text
platform_operator
+
allowed Site IDs
```

TRAFFIC-05 MUST NOT encode a permanent product invariant such as:

```text
only platform_operator can ever use Traffic
```

Traffic product semantics must remain compatible with a future centralized flow
such as:

```text
Principal
        ↓
Tenant / Site membership
        ↓
Role / Capabilities
        ↓
centralized AccessPolicy
        ↓
authorized canonical Site
        ↓
unchanged Traffic read semantics
```

Future policy replacement or extension MUST NOT require changing:

```text
network_traffic_by_ap.v1

AP population semantics inside one authorized Site

AP source-family rules

AP Average semantics

AP Peak semantics

aligned History representation

12-AP per-Site support semantics
```

---

# 72. Authorization ownership

TRAFFIC-05 relies on centralized Admin authorization.

Forbidden inside TRAFFIC-05 analytics/product logic:

```text
username-specific access rules

customer-name conditions

Tenant-name conditions

special customer branches

browser-only Site filtering

hard-coded platform_operator checks inside metric calculation
```

The product/read layer receives or operates under an already-authorized
canonical Site context and performs Site-scoped calculation only.

---

# 73. Full multi-tenancy implementation is OUT OF SCOPE

This TASK MUST NOT introduce merely for future readiness:

```text
Tenant DB

Tenant table

user DB

membership table

RBAC persistence schema

tenant_id in Traffic metric DTO

Tenant selector

customer account UI

new authentication system

Portal branding model

Tenant billing/account logic
```

Future:

```text
Platform Multi-Tenancy / Identity & Access
```

requires a separate architecture task.

TRAFFIC-05 tenant-readiness is achieved by:

```text
strict Site isolation

centralized policy ownership

neutral Site-scoped product services
```

not by premature Tenant infrastructure.

---

# 74. CaptivPortal Site vs Omada Site

TRAFFIC-05 MUST NOT introduce a new permanent coupling that assumes:

```text
Tenant identity == Omada Site identity
```

or:

```text
future user authorization == Omada Site authorization
```

Current accepted Site integration may continue unchanged.

Future:

```text
Tenant
Controller
CaptivPortal Site
Omada Site
Principal membership
```

binding architecture is outside this TASK.

TRAFFIC-05 only requires an authorized canonical Site identifier and Site-scoped
evidence.

---

# 75. Site-isolation invariant for population discovery

The union population:

```text
CURRENT_ACCEPTED_AP_POPULATION
UNION
HISTORICAL_VALIDATED_AP_POPULATION
```

is always evaluated under:

```text
one authorized canonical site_id
```

Therefore:

```text
current population count
historical population count
union population count
supported/unsupported decision
```

are all Site-local.

An AP belonging to Site B MUST NOT change Site A:

```text
population_count

current_population_count

historical_population_count

unsupported_population decision

returned_ap_count
```

---

# 76. Site-isolation invariant for Current AP evidence

CurrentTrafficReadService composition for TRAFFIC-05 MUST be bound to the same
authorized canonical Site.

For Site A request:

```text
requested AP identity set
MUST contain Site A population only
```

and returned current AP evidence MUST be Site A evidence only.

A Site B AP with the same or similar display name is irrelevant.

Machine identity remains:

```text
Site scope + canonical ap_mac
```

Product DTO may continue to expose only `ap_mac` because the outer request Site
is authoritative context; this does not weaken backend Site isolation.

---

# 77. Site-isolation invariant for Historical AP evidence

Historical AP projection MUST preserve Site restriction through:

```text
population discovery

canonical cycle/sample selection

bucket aggregation

Average interval selection

Peak population

Coverage

quality counts
```

For Site A request, no Site B row may participate even if:

```text
timestamp overlaps

AP MAC resembles another AP

source family matches

cycle is otherwise valid
```

---

# 78. Site-isolation invariant for telemetry

Safe telemetry fields such as:

```text
ap_population_count

ap_returned_count

ap_history_points_total

ap_supported_max
```

describe only the current authorized canonical Site request.

No cross-Site aggregate/cardinality is emitted by TRAFFIC-05 telemetry.

If operational logging includes `site_id` according to existing safe policy,
that Site identifies the scoped request; it does not authorize aggregation
across Sites.


# 79. Security chain

Required conceptual chain:

```text
Admin authentication
        ↓
canonical Site resolution
        ↓
admin.read.context
        ↓
WEB_ADMIN_TRAFFIC_ENABLED
        ↓
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED
        ↓
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED for aps include
        ↓
AdminQueryService
        ↓
accepted read authorization
        ↓
HistoricalTrafficReadService
        ↓
CurrentTrafficReadService composition
```

No new security model.

---

# 80. Feature flag

Proposed:

```text
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED=false
```

Settings key:

```text
web_admin_traffic_by_ap_enabled
```

Admin config:

```text
traffic_by_ap_enabled: bool
```

---

# 81. Feature dependencies

```text
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED=true
```

requires:

```text
WEB_ADMIN_ENABLED=true
WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
```

It does NOT require:

```text
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED
WEB_ADMIN_TRAFFIC_PEAK_ENABLED
```

Those are sibling product surfaces.

---

# 82. Disabled behavior

With By-AP false:

```text
By-AP markup absent

no `aps` include

no AP population calculation for this product

no AP history series calculation

no AP Now composition for this product
```

Existing:

```text
Current
History
Statistics
Peak
```

remain unchanged.

Direct `aps` include:

```text
404 not_found
```

after normal security/parent gates.

---

# 83. Fail-closed serializer

Malformed backend AP semantic DTO:

```text
MUST NOT
be converted into a successful generic unavailable state
```

Expected application mapping:

```text
AdminQueryUnavailable
→ combined request 503 source_unavailable
```

except explicitly valid:

```text
unsupported_population
```

which is a defined product state, not malformed data.

---

# 84. HTTP mappings

Reuse current Traffic API mappings:

```text
200 safe result
400 invalid_request
401 authentication_required
403 site_forbidden
404 not_found
429 concurrency_limit
503 query_deadline
503 source_unavailable
503 response_too_large
500 sanitized internal_error
```

`unsupported_population` is an AP sub-product result in HTTP 200.

---

# 85. Response-size platform bound

Existing hard platform value:

```text
WEB_ADMIN_MAX_RESPONSE_BYTES
```

Current/default:

```text
1,048,576 bytes
```

No new response-size config.

---

# 86. TRAFFIC-05 all-AP payload acceptance gate

FINAL replaces R1's provisional 80% rule with a more conservative v1 product gate:

```text
worst-case supported 12-AP 7d serialized combined response
<= 75% of WEB_ADMIN_MAX_RESPONSE_BYTES
```

Current/default target:

```text
<= 786,432 bytes
```

Hard platform limit remains:

```text
< 1,048,576 bytes
```

---

# 87. Why 75%

FINAL all-AP payload uses a compact aligned representation and intentionally keeps
substantial headroom for:

```text
existing Site History payload

Statistics/Peak metadata

Current AP metadata

names/quality fields

safe JSON envelope

small compatible future additions
```

The candidate must prove exact bytes.

If 12 AP cannot satisfy 75% after correct implementation:

```text
STOP
→ do not silently lower/raise bound
→ return to Owner + Tech Lead
```

because both:

```text
supported cardinality
and
representation
```

are architecture contracts.

---

# 88. Population discovery must happen before heavy all-AP projection

Historical owner should first establish:

```text
current population identities

historical validated range identities

union population count
```

If count >12:

```text
do NOT build 12 AP histories
do NOT truncate
return unsupported_population
```

This avoids wasting the expensive per-AP projection for an unsupported product
population.

---

# 89. Population count must be exact

FINAL requires:

```text
population_count = exact union count
```

not:

```text
at least 13
```

because the product state should report the actual reason safely and
deterministically.

Population counting must remain requested-range bounded and pass PERF.

---

# 90. Historical query ownership

AP historical projection remains:

```text
inside one HistoricalTrafficReadService call
```

and:

```text
inside the same read-only Observation SQLite snapshot
```

as Site History/Statistics/Peak for that HTTP request.

No second HistoricalTrafficReadService call.

---

# 91. SQL statement count is not an invariant

Implementation may use multiple bounded SQL projections if necessary.

Allowed:

```text
range-bounded population query

range-bounded AP aggregate/series query

existing Site History/Statistics/Peak projections
```

Requirements:

```text
same semantic owner

same read transaction/snapshot

same QueryDeadline

requested-range bounded

no source writes
```

---

# 92. Existing performance remediations must remain

Preserve:

```text
TRAFFIC-02-PERF-01 requested-range bounding

TRAFFIC-03 expensive range validation reuse

TRAFFIC-04 typed Peak sample rows

TRAFFIC-04 deterministic linear/two-pointer busiest 60m
```

Forbidden regressions:

```text
all-history candidate validation

duplicated independent historical semantic scans

GROUP_CONCAT Peak sample transport

unbounded AP materialization
```

---

# 93. Current AP composition deadline

Current AP Now may use its own current read-only snapshot because it is a separate
time domain.

But entire combined Admin application request remains under:

```text
same shared Admin QueryDeadline
```

No:

```text
second deadline
timeout extension
concurrency extension
```

---

# 94. No new acquisition/storage

TRAFFIC-05 introduces:

```text
0 new Omada product reads
0 new collectors
0 schema migrations
0 new indexes
0 Traffic DB
0 cache
0 rollup
```

Native Omada per-AP range aggregates remain validation/reference only.

---

# 95. PERF governance correction

TRAFFIC-05 does NOT pre-authorize the TRAFFIC-04 controlled p50 amendment.

Initial standard envelope:

```text
A vs C p50
<= max(0.50s, 20% of C.p50)
```

If correct optimized implementation objectively cannot satisfy it:

```text
STOP
→ evidence
→ Owner + Tech Lead controlled amendment review
```

No amendment is granted by this DRAFT.

---

# 96. Official PERF variants

Use immutable production-size Observation evidence.

For each range:

```text
B24 / B7
accepted baseline:
History + Statistics + Peak

C24 / C7
candidate:
same request, By-AP code present but aps NOT requested

A24 / A7
candidate:
History + Statistics + Peak + aps
with exactly the maximum supported all-AP population = 12
```

A variants must exercise:

```text
all 12 AP identities

all 12 History series

all 12 Now

all 12 Average

all 12 Peak

all 12 Coverage
```

No first-page shortcut exists.

---

# 97. Maximum-cardinality PERF fixture

If the real production-size snapshot contains fewer than 12 APs, official Lab
must additionally use a deterministic immutable test fixture with:

```text
production schema

production-like requested-range cycle density

12 AP product population

7d canonical range density

valid/partial/missing evidence cases
```

This fixture is:

```text
test-only
immutable during run
hashed
not product storage
not a new production DB
```

It exists solely to prove the supported hard product contract.

---

# 98. Two required PERF evidence classes

Required:

## Real production-size snapshot

Proves:

```text
actual production data size/path behavior
```

## 12-AP maximum-cardinality fixture

Proves:

```text
hard supported product cardinality
payload
CPU/query viability
all-AP projection
```

Both must pass relevant gates before candidate acceptance.

---

# 99. PERF run count

For main B/C/A matrix:

```text
>=10 measured runs per variant

6 variants

>=60 measured runs
```

Warm-ups:

```text
unmeasured
equal/documented
```

Use deterministic interleaving.

---

# 100. Percentile algorithm

For p50/p95:

```text
sort ascending

rank=(N-1)*p

lower=floor(rank)
upper=ceil(rank)

if lower == upper:
  percentile=value[lower]
else:
  percentile=
    value[lower]
    +(rank-lower)*(value[upper]-value[lower])
```

`max` is literal maximum.

---

# 101. Candidate compatibility C vs B

With AP projection not requested:

```text
Δp50 <= max(0.50s, 20% of B.p50)

Δp95 <= max(0.75s, 25% of B.p95)

Δmax <= max(1.00s, 25% of B.max)
```

Hard:

```text
C.p95 <= 8.0s
C.max <= 9.0s
```

---

# 102. All-AP overhead A vs C

Initial standard:

```text
Δp50 <= max(0.50s, 20% of C.p50)

Δp95 <= max(0.75s, 25% of C.p95)

Δmax <= max(1.00s, 25% of C.max)
```

Hard:

```text
A.p95 <= 8.0s
A.max <= 9.0s
```

No 30% p50 allowance is pre-authorized.

---

# 103. PERF hard functional gates

Every run:

```text
0 query_deadline

0 source-integrity failures

0 unexpected 5xx

24h Site bucket count = 288

7d Site bucket count = 672
```

A variants additionally:

```text
population_count = 12

returned_ap_count = 12

population_complete = true

items.length = 12

each AP history array length:
24h = 288
7d = 672

all method/version identifiers exact
```

---

# 104. Payload gate in PERF

For maximum 12-AP fixture:

```text
A7 serialized response
<= 75% WEB_ADMIN_MAX_RESPONSE_BYTES
```

Also record:

```text
A24 bytes
A7 bytes

B bytes
C bytes
```

No response may hit:

```text
response_too_large
```

for supported population.

---

# 105. Unsupported population PERF/functional proof

Mandatory fixture:

```text
13 AP union population
```

Expected:

```text
HTTP 200

History/Statistics/Peak valid

ap_traffic.status=unsupported_population

population_count=13

supported_max_ap_count=12

returned_ap_count=0

items=[]
```

And importantly:

```text
no 12-AP series materialization
```

after over-bound population is established.

---

# 106. Query-plan evidence

Official Linux Lab captures safe query-plan evidence for materially new AP SQL.

Must show:

```text
requested-range bounded work

relevant existing indexes used appropriately

no all-history validation

no AP × all-history explosion

population count before expensive AP projection
```

No new index is authorized by this TASK.

---

# 107. PERF failure response

On failure:

```text
STOP
→ profile
→ query plans
→ evidence
→ Owner + Tech Lead review
```

Forbidden silent fixes:

```text
increase QueryDeadline

increase browser timeout

increase Admin concurrency

add index

add schema/table

cache

rollup

reduce semantic validation

change supported bound
```

Any bound/architecture change returns to review.

---

# 108. Read-only immutability

Official Lab records:

```text
candidate tree

source fixture SHA256
source fixture bytes

schema/user_version
```

Before/after:

```text
candidate tree unchanged

source SHA unchanged

schema unchanged

no writes
```

---

# 109. Browser governance correction

DRAFT R1 incorrectly made manual Controlled Browser Acceptance a mandatory
pre-publication gate.

FINAL removes that requirement.

Normal workflow:

```text
Coder patch
→ Owner + Tech Lead Lab
→ mandatory functional/central gates
→ mandatory production-size PERF
→ accepted candidate
→ publication
→ Owner merge
→ production deploy FROM GIT
→ dormant acceptance
→ separate activation
→ Production Product / Browser Acceptance
```

---

# 110. Pre-publication frontend acceptance

Frontend automated tests remain mandatory in Owner + Tech Lead Lab.

They must validate:

```text
all-AP rendering contract

12 supported APs

13 unsupported APs

shared range

no AP pagination

no AP selector

no second coordinator

no direct fetch/timer

DTO validation

rapid generation supersession
```

This is automated functional acceptance, not a separate manual browser gate.

---

# 111. Production Product / Browser Acceptance

Manual/real product browser acceptance occurs after:

```text
accepted candidate
publication
merge
deploy FROM GIT
dormant acceptance
separate activation
```

Then verify production UI.

---

# 112. Production browser — all-AP invariant

For supported production population:

```text
every product AP visible simultaneously
```

For each:

```text
identity
D/U history
Now D/U/Total
Average D/U/Total
Peak D/U/Total
Coverage
```

No AP selection to reveal another AP.

---

# 113. Production browser — range

Verify:

```text
24h
7d

same range applied to:
History
Statistics
Peak
all AP histories
```

All AP cards refresh as one accepted historical generation.

---

# 114. Production browser — unsupported population

If a controlled test environment can produce >12 APs, verify:

```text
clear unsupported message

no first-12 truncation

no AP cards pretending complete population

History/Statistics/Peak remain functional
```

Production itself does not need to be mutated merely to create 13 APs.

Lab fixture provides mandatory functional proof.

---

# 115. Frontend automated render bound

At 12 AP / 7d fixture automated tests should verify:

```text
12 AP blocks

12 chart SVGs

2 primary line paths per chart

no sample-per-DOM-node rendering
```

Exact design classes are implementation detail.

Functional bound is mandatory.

---

# 116. Rapid supersession

Existing Traffic coordinator generation rule remains.

Sequence:

```text
24h
→ 7d in flight
→ 24h
```

Stale 7d result MUST NOT update:

```text
History
Statistics
Peak
any AP card
```

Latest accepted generation owns all.

---

# 117. Failure isolation

If combined historical HTTP request fails:

```text
History/Statistics/Peak/By-AP
share that request failure
```

Current Network Throughput remains panel-independent.

If AP product returns valid:

```text
unsupported_population
```

History/Statistics/Peak are NOT failed.

Only AP panel shows unsupported state.

---

# 118. Coder responsibility correction

Coder responsibilities:

```text
implement approved TASK

prepare patch

static sanity as applicable:

python compileall

node --check if JS changed

git diff --check
```

Coder does NOT own official pytest acceptance.

---

# 119. Owner + Tech Lead Lab responsibility

Owner + Tech Lead run:

```text
focused TRAFFIC-05 pytest suites

targeted regression

Central Lab gate

production-size PERF

max-cardinality fixture PERF

official PASS/FAIL
```

---

# 120. Focused Analytics tests — executed by Lab

Preferred new:

```text
tests/analytics/test_historical_traffic_ap.py
```

Required:

```text
union population

current-only AP

historical-only AP

de-duplication

MAC ordering

12 supported

13 unsupported / no truncation

Site source inheritance

NO per-AP fallback

complete/partial/none series

valid zero

missing != zero

complete-bucket additive identity

AP Average time weighting

Average != bucket-mean average

AP Average Total invariant

AP Peak accepted sample

AP Peak Total same-sample

no AP Peak timestamp

quality counts

24h/7d array lengths
```

---

# 121. Current owner tests — executed by Lab

If bounded current population lookup is added, prove:

```text
<=12 input bound

same current source selection

same D/U/Total

same rate reasons

same rate status

same timestamps/freshness

existing current API semantics unchanged
```

---

# 122. Admin/API tests — executed by Lab

Preferred:

```text
tests/admin_web/test_traffic_ap.py
```

Required:

```text
flag default false

flag dependencies

does not require Statistics/Peak

include grammar exact

no ap_limit

no ap_cursor

disabled aps → 404

supported all-AP → 200

12 → all 12 returned

13 → unsupported_population + zero items

no silent truncation

safe serializer fail-closed

75% payload gate fixture

hard response limit preserved
```

---


# 123. Site-isolation security tests — executed by Lab

Mandatory focused acceptance fixture contains at least:

```text
Site A
Site B
same Observation/current source database
```

For an authorized Site A request prove:

```text
AP population contains only Site A identities
```

while Site B AP evidence exists in the same underlying DB.

Site B evidence MUST NOT appear in Site A:

```text
population_count

current_population_count

historical_population_count

returned AP items

Current Now

History series

Average

Peak

Coverage

quality counts
```

Mandatory unsupported-bound isolation case:

```text
Site A = 12 AP
Site B = 5 AP
```

Expected Site A:

```text
population_count = 12
status != unsupported_population
```

Site B APs MUST NOT push Site A over the 12-AP bound.

Also prove:

```text
Site A = 13 AP
Site B arbitrary
```

Expected Site A:

```text
unsupported_population

population_count = 13

returned_ap_count = 0

items = []
```

Site B cardinality remains irrelevant.

Security acceptance MUST exercise both:

```text
CurrentTrafficReadService composition

HistoricalTrafficReadService AP projection
```

under the same authorized canonical Site context.

Frontend filtering is not considered evidence of security isolation.


# 123. Frontend tests — executed by Lab

Preferred:

```text
tests/admin_web/test_traffic_ap_frontend.py
```

Required:

```text
no selected AP state

no AP selector

no pagination

no Next/Previous

all returned APs rendered simultaneously

12 AP cards

12 charts

2 history series per chart

no sample DOM nodes

no second Network range

no second coordinator

no direct fetch

no private timer

no AP AbortController

no visibility/pagehide owner

browser does not calculate Average/Peak/source/population

unsupported_population renders explicit message and zero AP subset

rapid supersession safe
```

---

# 124. Existing Traffic regression — Lab

Must preserve:

```text
TRAFFIC-00 Foundation/coordinator

TRAFFIC-01 Current Network Throughput

TRAFFIC-02-READ

TRAFFIC-02-PERF-01

TRAFFIC-02 History

TRAFFIC-03 Statistics

TRAFFIC-04 Peak
```

When `aps` is absent:

```text
existing response semantics unchanged
```

---

# 125. Fixed-context Current AP equality

Under same fixed:

```text
Site
current cycle
evaluation
source policy
```

TRAFFIC-05 AP Now must equal existing CurrentTrafficReadService AP semantics.

Compare:

```text
ap_mac
source
D/U/Total
rate reasons
rate status
observed_at
```

Sequential live requests need not be exactly equal.

---

# 126. Site/AP additive regression

For complete deterministic fixture:

```text
Σ AP D bucket
= Site D bucket

Σ AP U bucket
= Site U bucket

Σ AP Total bucket
= Site Total bucket
```

For partial fixture:

```text
no additive completeness claim
```

---

# 127. Expected implementation file scope — Analytics

Expected MODIFY:

```text
app/analytics/models.py

app/analytics/historical_traffic.py

app/analytics/source_gateway.py

app/analytics/current_traffic.py
# only if bounded current population lookup is needed

app/analytics/__init__.py
```

No new semantic service module is expected.

---

# 128. Expected implementation file scope — Admin/config

Expected MODIFY:

```text
app/config.py
app/settings.py
.env.example

app/admin_web/config.py
app/admin_web/pages.py
app/admin_web/query_service.py
app/admin_web/routes.py

app/admin_web/historical_traffic_serialization.py

app/admin_web/current_traffic_serialization.py
# only for narrow safe projection reuse

app/admin_web/static/admin.js
app/admin_web/static/admin.css
app/admin_web/templates/admin/traffic.html
```

---

# 129. Expected unchanged production scope

Expected unchanged:

```text
app/analytics/runtime.py
app/analytics/config.py

app/admin_web/runtime.py
app/admin_web/traffic_network_ranges.py
app/admin_web/templates/admin/base.html

app/observations/**
app/current_state/**
app/visit_lifecycle/**
app/visitor_registry/**
app/auth/**
app/capport/**
app/controllers/**

run.py
requirements*
```

If required change appears:

```text
STOP
→ exact reason
→ architecture review
```

---

# 130. No new performance config

Do NOT add:

```text
WEB_ADMIN_TRAFFIC_BY_AP_MAX_APS
```

as operator config in v1.

The supported bound:

```text
12
```

is a product contract, not a knob.

Also no new:

```text
query timeout
response timeout
concurrency config
```

---

# 131. Feature telemetry

Safe historical telemetry additions may include:

```text
ap_traffic_requested

ap_traffic_status

ap_population_count

ap_returned_count

ap_supported_max = 12

ap_history_points_total

response_bytes

All counts are for the authorized canonical Site only.
```

Do not log:

```text
full AP MAC population

raw series

SQL

DB path
```

unless an existing logging policy explicitly requires identities.

---

# 132. Unsupported population telemetry

When over bound:

```text
ap_traffic_status=unsupported_population

ap_population_count=N

ap_supported_max=12

ap_returned_count=0
```

This makes future need to raise the supported bound observable.

---

# 133. Dormant deployment

Normal rollout:

```text
deploy accepted Git artifact

WEB_ADMIN_TRAFFIC_BY_AP_ENABLED=false
```

Dormant acceptance:

```text
service active

Current PASS

History PASS

Statistics PASS

Peak PASS

By-AP markup absent

no aps include

no AP product calculation

no new query deadline/concurrency pattern
```

---

# 134. Separate activation

Only after separate Owner authorization:

```text
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED=true
```

Then normal restart/reload procedure and production product acceptance.

---

# 135. Production supported population acceptance

If production union population <=12:

```text
all APs shown simultaneously

count in UI matches API population

no hidden subset

24h PASS

7d PASS where supported
```

Each AP:

```text
history D/U
Now
Average
Peak
Coverage
```

---

# 136. Production range-specific unsupported state

If:

```text
24h population <=12
7d population >12
```

then:

```text
24h By-AP works

7d By-AP explicitly unsupported_population

7d History/Statistics/Peak still work
```

This is correct.

---

# 137. Rollback

Primary rollback:

```text
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED=false
```

Expected:

```text
By-AP disappears

History request returns to previous include form

Current remains active

History remains active

Statistics remains active

Peak remains active
```

No DB/schema rollback.

---

# 138. Explicit non-goals

TRAFFIC-05 does NOT implement:

```text
AP pagination

selected AP UX

AP selector

TRAFFIC-06 AP Traffic Share

share %

traffic ranking by share

AP Peak timestamps

AP busiest bucket/hour

Guest Traffic

SSID Traffic

traffic volume MB/GB

30d

Heatmap

Period Comparison

new collector

new Omada read

new DB/schema/index/cache/rollup

Home redesign

final Traffic visual design
```

---

# 139. Stop conditions

Implementation MUST STOP if it requires:

```text
new Traffic semantic owner

new collector

new Omada product read

new DB/schema/index/cache/rollup

per-AP source fallback

recalculate Mbps from raw counters

radio as Network Traffic source

browser Average/Peak/source calculation

raw 30-second AP payload

selected AP/pagination product UX

silent AP truncation

returning only first 12 when population >12

new range selector

second automatic AP historical request

second historical coordinator

QueryDeadline increase

browser timeout increase

Admin concurrency increase

changing supported max from 12 without review

changing 75% payload gate without review

pre-authorizing 30% PERF p50

changing TRAFFIC-02/03/04 semantics
```

Also STOP on material main drift.

---

# 140. Owner + Tech Lead review answers incorporated

R1 Q1 — Option C:

```text
REVISED
→ C-R2 with all-AP aligned representation
→ recommended
```

R1 Q2 — AP page max 4:

```text
REJECTED / REMOVED
```

New:

```text
all-AP supported hard bound = 12
no pagination
```

R1 Q3 — display name:

```text
ACCEPTED
current → historical → MAC
```

R1 Q4 — Average:

```text
ACCEPTED
right_endpoint_ap_sample_hold_time_weighted.v1
```

R1 Q5 — Peak:

```text
ACCEPTED
max_accepted_complete_ap_sample.v1
no timestamp
```

R1 Q6 — 80%:

```text
REVISED
→ 75% worst-case 12-AP 7d combined response gate
```

R1 Q7 — 30% p50:

```text
REJECTED
→ standard 20% initial A-vs-C p50
→ amendment only after evidence/review
```

---

# 141. All review-mandated freezes

R2 explicitly freezes:

```text
all-AP simultaneous UI =
YES

supported population =
current accepted AP
UNION
validated historical AP in selected range

supported hard cardinality =
12

over-bound behavior =
unsupported_population
zero AP subset returned
no truncation

all-AP representation =
outer Site History aligned columnar D/U arrays

all-AP PERF =
mandatory max-cardinality 12-AP proof

payload gate =
12 AP / 7d combined response <=75% max bytes

selected AP UX =
NONE

product pagination =
NONE

Coder official pytest responsibility =
NONE

Owner + Tech Lead Lab =
focused/central/PERF official acceptance

manual production browser acceptance =
after deploy + activation
```

---

# 142. FINAL approval state

This is still FINAL, not FINAL.

Why:

```text
12-AP bound and 75% payload representation
must be reviewed by Owner + Tech Lead

implementation has not yet produced
exact serializer bytes / SQL plans / PERF evidence
```

However architecture is now concrete enough for review without reopening the
whole Traffic design.

---


# 143. Tenant-readiness / Site isolation — FINAL decisions

Owner + Tech Lead targeted addition is incorporated as permanent architecture:

```text
TRAFFIC-05 data-isolation boundary =
authorized canonical Site

12-AP hard bound =
per authorized canonical Site

cross-Site population/count/metric exposure =
FORBIDDEN

frontend filtering as authorization boundary =
FORBIDDEN

current platform_operator model =
implementation detail of current authorization layer,
not permanent Traffic product semantics

future centralized Principal/Tenant/RBAC/AccessPolicy =
compatible without changing Traffic metric semantics

Tenant DB / RBAC schema / tenant selector / tenant_id Traffic DTO =
OUT OF SCOPE
```

No multi-tenancy implementation is introduced by this TASK.


# 143. FINAL status

```text
TASK:
TASK-TRAFFIC-05 — Traffic by AP

STATUS:
FINAL — OWNER + TECH LEAD REVIEW INCORPORATED
ARCHITECTURE APPROVED

REPOSITORY BASELINE:
main@f58679351fa6cd8558f67234937a7706fb4f3dae

TREE:
d22c54100d80540e4cc9506b3f51323d7ee8201c

PRODUCTION / RUNTIME CHECKPOINT:
a9cd8a9b9b9efc46bc82d315385ebbd1a3bf63b0

PRODUCTION / RUNTIME TREE:
f53f204cf3ebf7cecf4e872ce450b4f3f4265cc9

PRODUCT:
Traffic by AP

DATA-ISOLATION BOUNDARY:
authorized canonical Site

12-AP BOUND:
PER authorized canonical Site

CROSS-SITE AP ENUMERATION / COUNT / DATA:
FORBIDDEN

TENANT IMPLEMENTATION:
OUT OF SCOPE

FUTURE CENTRALIZED PRINCIPAL/TENANT/RBAC POLICY:
COMPATIBLE WITHOUT CHANGING TRAFFIC METRIC SEMANTICS

ALL-AP SIMULTANEOUS:
YES

POPULATION:
current accepted AP
UNION
validated historical AP
WITHIN authorized canonical Site and selected range

SUPPORTED MAX:
12 AP per authorized canonical Site

OVER LIMIT:
unsupported_population
NO truncation
NO subset
NO pagination

HISTORICAL OWNER:
HistoricalTrafficReadService

CURRENT AP OWNER:
CurrentTrafficReadService

HISTORY REPRESENTATION:
outer_history_bucket_aligned_du.v1

RANGES:
24h / 7d

PER AP:
one chart
two series D/U

FEATURE DEFAULT:
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED=false

PAYLOAD GATE:
12 AP / 7d combined <=75% WEB_ADMIN_MAX_RESPONSE_BYTES

PERF DEFAULT:
A-vs-C p50 <= max(0.50s, 20% of C.p50)

NEW COLLECTOR:
NO

NEW OMADA DEPENDENCY:
NO

NEW DB / SCHEMA / INDEX / CACHE / ROLLUP:
NO

CODER OFFICIAL PYTEST:
NO

OWNER + TECH LEAD LAB:
YES

PRE-PUBLICATION MANUAL BROWSER GATE:
NO

POST-ACTIVATION PRODUCTION PRODUCT/BROWSER ACCEPTANCE:
YES

IMPLEMENTATION AUTHORIZATION:
NOT GRANTED

PUBLICATION:
NOT GRANTED

MERGE:
NOT GRANTED

DEPLOY:
NOT GRANTED

ACTIVATION:
NOT GRANTED
```

Next allowed step:

```text
Owner + Tech Lead short FINAL verification
```

Only after separate explicit Owner authorization may implementation begin.

This FINAL itself does NOT authorize implementation.
