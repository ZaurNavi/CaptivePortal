# TASK-TRAFFIC-05 — Traffic by AP — DRAFT

**Project:** CaptivPortal  
**Area:** Admin Console → Traffic  
**Roadmap item:** `TRAFFIC-05 — Traffic by AP`  
**Dependencies:** `TRAFFIC-00`, `TRAFFIC-01`, `TRAFFIC-02-READ`, `TRAFFIC-02`, `TASK-TRAFFIC-02-PERF-01`, `TRAFFIC-03`, `TRAFFIC-04`  
**Status:** `DRAFT — FOR OWNER + TECH LEAD ARCHITECTURAL REVIEW`  
**Implementation authorization:** `NOT GRANTED`  
**Publication / merge / deploy / activation:** `NOT GRANTED`  
**Prepared:** 2026-08-31

---

## 0. Executive decision

`TRAFFIC-05` implements the next canonical Traffic product:

```text
Traffic by AP
```

For each AP, v1 must expose:

```text
AP identity
Download history
Upload history
Now
Average
Peak
Coverage
```

Unit:

```text
Mbps
```

Domain:

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

Historical owner remains:

```text
HistoricalTrafficReadService
```

Current per-AP `Now` owner remains:

```text
CurrentTrafficReadService
```

No third semantic owner is introduced.

---

# 1. Exact current baseline

Repository was re-fetched before this DRAFT.

```text
origin/main =
f58679351fa6cd8558f67234937a7706fb4f3dae

tree =
d22c54100d80540e4cc9506b3f51323d7ee8201c
```

Current main is PR #92:

```text
Docs: reconcile TRAFFIC-04 production state
```

PR #92 is docs/current-state reconciliation only.

Accepted runtime / production checkpoint remains:

```text
a9cd8a9b9b9efc46bc82d315385ebbd1a3bf63b0

tree:
f53f204cf3ebf7cecf4e872ce450b4f3f4265cc9
```

Therefore:

```text
repository baseline
!=
production HEAD

but

runtime impact of PR #92 = NONE
```

Before FINAL and again before implementation authorization:

```text
re-fetch origin/main
re-pin SHA/tree
impact review if app/analytics/**, app/admin_web/**,
app/observations/**, app/config.py, app/settings.py or run.py changed.
```

---

# 2. Current accepted Traffic chain

Treat as completed:

```text
TRAFFIC-00 — Foundation
TRAFFIC-01 — Current Network Throughput
TRAFFIC-02-READ — Historical Traffic owner
TRAFFIC-02 — History
TRAFFIC-02-PERF-01 — production range-query remediation
TRAFFIC-03 — Period Statistics
TRAFFIC-04 — Peak Load
```

TRAFFIC-04 is production active and closed.

Current Traffic architecture already uses:

```text
one shared 24h|7d Network range
one Traffic coordinator
one combined History request for History + Statistics + Peak
bounded Admin query controls
```

TRAFFIC-05 must preserve these boundaries.

---

# 3. Roadmap binding

Canonical Roadmap defines TRAFFIC-05 as a graphical historical AP product:

```text
Per AP:
AP identity
Download history
Upload history
Now
Average
Peak
Coverage
```

and explicitly requires dedicated decisions for:

```text
AP bounds
pagination
max series
max graph points
response budget
cursor / continuation
```

`TRAFFIC-06 — AP Traffic Share` is a separate next TASK.

---

# 4. Architecture options

Three options are reasonable.

## A. Separate AP historical endpoint + separate panel loader

Pros:

```text
clean AP-only API
simple pagination
strong panel isolation
```

Cons:

```text
automatic extra historical request
extra Admin concurrency slot
range change can run History + AP scans concurrently
higher 429/query_deadline risk
```

**Recommendation:** reject for v1 default.

## B. Put all AP histories into existing History response

Pros:

```text
one HTTP request
```

Cons:

```text
unbounded AP cardinality
large 7d payload
poor pagination
response_too_large risk
```

**Recommendation:** reject unbounded form.

## C. Bounded AP projection inside the existing History execution

```text
existing History request
→ HistoricalTrafficReadService
→ current Site History/Statistics/Peak
→ optional bounded AP page
```

First/range load remains one historical request.

Explicit AP pagination uses the same History coordinator execution and another
combined request only when the user requests another AP page.

**DRAFT recommendation: OPTION C.**

---

# 5. Canonical source path

Historical:

```text
Observation persisted AP history
→ AnalyticsSourceGateway
→ HistoricalTrafficReadService
→ bounded per-AP projection
```

Current:

```text
latest accepted Observation AP snapshot
→ CurrentTrafficReadService
→ bounded AP Now projection
```

Forbidden:

```text
Admin → Omada
Browser → Omada
new collector
new Traffic DB
direct Admin SQL owner
browser-side source selection
browser-side Average/Peak calculation
```

Native Omada `dashboard/traffic-distribution` remains validation/reference only.

---

# 6. Current per-AP `Now` — exact ownership

Current repository already has:

```text
CurrentTrafficReadService.list_current_ap_traffic(...)
```

and a safe Admin serializer for AP items.

Existing AP current facts include:

```text
ap_mac
name
download_mbps
upload_mbps
total_mbps
download_reason
upload_reason
rate_status
observed_at
age_seconds
selected_source
```

TRAFFIC-05 MUST reuse this semantic contract.

Permanent:

```text
Now != last History bucket
```

If an efficient bounded lookup is required, a narrow method such as:

```python
get_current_ap_traffic_for_macs(...)
```

is allowed only inside `CurrentTrafficReadService` and must preserve the exact
existing current source/freshness/rate semantics.

---

# 7. Current vs historical timestamps

Historical AP metrics use the shared History:

```text
range.from_utc
range.to_utc
range.evaluated_at_utc
```

Current AP `Now` has its own:

```text
current_snapshot.evaluated_at
current_snapshot.observed_at
freshness
```

These MAY differ.

Do not claim one exact historical/current snapshot.

Current selected source may also differ from the final historical bucket source.

That is valid provenance, not automatically a defect.

---

# 8. Critical historical source-family invariant

For every canonical Site History bucket:

```text
one selected_source =
wired | lan
```

TRAFFIC-05 per-AP buckets MUST inherit that Site-bucket source.

Example:

```text
Site bucket source = wired

AP-1 → wired
AP-2 → wired
AP-3 → wired
```

If AP-2 lacks accepted wired evidence:

```text
AP-2 = partial / none
```

Forbidden:

```text
AP-1 wired
AP-2 LAN fallback
AP-3 wired
inside the same canonical Site bucket
```

This invariant is required for comparability and future TRAFFIC-06.

---

# 9. AP identity and population

Canonical machine identity:

```text
ap_mac
```

Historical AP population:

```text
distinct canonical AP MACs appearing in validated canonical AP dynamic cycles
inside requested [from,to)
```

An AP is not removed merely because selected-source Traffic evidence is missing.

Stable backend order:

```text
AP MAC ascending
```

Frozen candidate identifier:

```text
ap_order_method = ap_mac_ascending.v1
```

---

# 10. AP display name — DRAFT

Recommended display-name resolution:

```text
1. current accepted AP name if non-empty
2. latest non-empty persisted AP name inside requested range
3. AP MAC
```

Return:

```text
display_name
display_name_source =
current | historical | mac_fallback
```

Name never affects metric identity or pagination.

---

# 11. Canonical AP page bound

DRAFT proposal:

```text
ap_limit default = 4
ap_limit max = 4
ap_limit min = 1
```

Reason:

```text
24h = 288 points/AP
7d  = 672 points/AP
```

At max page size:

```text
7d:
4 × 672 = 2688 AP bucket objects
```

before summary/current metadata.

No new repository config is proposed for page size.

---

# 12. Chart/series budget

Per returned AP:

```text
24h → max 288 canonical buckets
7d  → max 672 canonical buckets
```

The browser displays one selected AP at a time.

Chart series:

```text
Download
Upload
```

Maximum visible series:

```text
2
```

`Total` remains available for Now/Average/Peak but is not required as a third
history line.

No raw 30-second rows are sent to browser.

---

# 13. AP bucket sample population

For AP `A` and canonical Site bucket `B`:

```text
opportunity_sample_count =
outer Site bucket complete_site_sample_count
```

An AP sample is accepted only when:

```text
same Site
same AP MAC
same canonical accepted Site sample/cycle
valid Download+Upload pair
for outer Site bucket selected_source
```

Then:

```text
0 <= accepted_ap_sample_count <= opportunity_sample_count
```

---

# 14. AP bucket status

Allowed:

```text
complete
partial
none
```

`none`:

```text
accepted_ap_sample_count = 0
D/U/Total = null
```

`complete`:

```text
opportunity_sample_count > 0
accepted_ap_sample_count = opportunity_sample_count
required temporal evidence comparable
```

`partial`:

```text
0 < accepted_ap_sample_count < opportunity_sample_count
or AP temporal evidence is incomplete
```

Missing AP evidence never becomes zero.

---

# 15. AP bucket numeric method

If at least one accepted AP sample exists:

```text
Download =
arithmetic mean of accepted AP Download rates
inside the canonical Site bucket

Upload =
arithmetic mean of accepted AP Upload rates
inside the same accepted AP sample subset

Total =
Download + Upload
```

Frozen candidate method:

```text
mean_of_accepted_ap_rates_for_canonical_site_bucket_samples.v1
```

This is only AP History bucket aggregation.

It is NOT AP Period Average.

---

# 16. Complete-bucket additive identity

Mandatory cross-contract invariant:

When all AP buckets in one Site bucket are complete over the exact same accepted
Site sample set:

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

within safe float tolerance.

If one AP is partial/none, this identity MUST NOT be claimed.

TRAFFIC-05 does not create `Unattributed Traffic`.

---

# 17. AP Period Average

Forbidden:

```text
average(AP History bucket averages)
```

Canonical candidate method:

```text
right_endpoint_ap_sample_hold_time_weighted.v1
```

It reuses the accepted sampled-time interpretation from TRAFFIC-03.

An AP interval contributes only when:

```text
corresponding canonical Site interval is accepted
AND
Site source family is comparable
AND
AP has accepted selected-source evidence for the required interval endpoints
```

No gap/source-transition/AP-absence zero fill.

Formula:

```text
Average Download = Σ(D_i × Δ_i) / ΣΔ_i
Average Upload   = Σ(U_i × Δ_i) / ΣΔ_i
Average Total    = Σ(T_i × Δ_i) / ΣΔ_i
```

where:

```text
T_i = D_i + U_i
```

No accepted AP interval seconds:

```text
Average D/U/Total = null
```

---

# 18. AP Average evidence

Return at least:

```text
site_accepted_interval_seconds
ap_accepted_interval_seconds
```

When Site denominator >0:

```text
ap_interval_coverage_ratio =
ap_accepted_interval_seconds / site_accepted_interval_seconds
```

This is evidence coverage.

It is NOT Traffic Share and NOT Health.

---

# 19. AP Peak

Candidate method:

```text
max_accepted_complete_ap_sample.v1
```

Population:

```text
accepted canonical Site samples where this AP has a valid pair for the
Site-selected source family
```

Canonical:

```text
Peak Download = max(AP D)
Peak Upload   = max(AP U)
Peak Total    = max(AP D + AP U at the same sample)
```

Permanent:

```text
Peak Total != Peak Download + Peak Upload
```

unless directional maxima naturally occur together.

AP Peak timestamps are deliberately OUT of TRAFFIC-05 v1.

---

# 20. AP historical coverage

Minimum per AP:

```text
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

No synthetic Traffic-quality score.

---

# 21. AP historical status

Per AP:

```text
complete
partial
insufficient_data
```

`complete` requires:

```text
outer History = ok
and AP covers all required canonical bucket/sample/interval evidence
```

`partial` means some trustworthy AP history exists but full comparability is not
satisfied.

`insufficient_data` means AP identity exists in range but no usable numeric
historical Traffic evidence exists.

---

# 22. Current AP Now shape

For each AP:

```text
status =
valid | partial | unavailable

download_mbps
upload_mbps
total_mbps

download_reason
upload_reason

observed_at
age_seconds

selected_source
```

Use existing Current Traffic machine semantics.

If AP is absent from the accepted current snapshot:

```text
status = unavailable
D/U/Total = null
```

Do not substitute a History value.

Accepted `0.0 Mbps` remains valid zero.

---

# 23. Traffic-by-AP overall status

Proposed:

```text
ok
partial
insufficient_data
```

`ok` for the returned page requires:

```text
outer History = ok
items non-empty
all returned AP historical status = complete
current snapshot fresh
all returned AP Now status = valid
```

`partial` if usable evidence exists but any required historical/current dimension
is incomplete/stale/unavailable.

`insufficient_data` if the returned page contains no usable historical or current
numeric Traffic evidence.

Server source/integrity/deadline failures remain HTTP errors rather than a
successful generic `unavailable`.

---

# 24. Recommended API design

Do NOT add an automatically loaded independent:

```text
GET /traffic/aps
```

for v1.

Extend:

```text
GET /admin/api/v1/sites/<site_id>/traffic/history
```

with a bounded AP projection.

Existing include forms remain valid:

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

Canonical token order is fixed.

`peak` still requires `statistics`.

`aps` does not require Statistics or Peak.

---

# 25. AP request parameters

Only when `include` contains `aps`:

```text
ap_limit
ap_cursor
```

`ap_limit`:

```text
1..4
default 4
```

`ap_cursor`:

```text
opaque server-issued continuation
```

If AP parameters appear without `aps`:

```text
400 invalid_request
```

Unknown/duplicate include forms:

```text
400 invalid_request
```

---

# 26. Initial request with current production panels

With History + Statistics + Peak + By-AP enabled:

```text
GET /admin/api/v1/sites/<site_id>/traffic/history
?range=24h
&include=statistics,peak,aps
&ap_limit=4
```

or:

```text
range=7d
```

Normal initial Traffic page browser request count remains:

```text
1 Current Network Throughput request
+
1 combined historical request
```

No third automatic AP historical request.

---

# 27. Canonical response extension

```text
result
├── existing History
├── period_statistics         # if requested
├── peak_load                 # if requested
└── ap_traffic                # if requested
```

`ap_traffic` candidate identifiers:

```text
metric_version =
network_traffic_by_ap.v1

unit =
Mbps

history_bucket_method =
mean_of_accepted_ap_rates_for_canonical_site_bucket_samples.v1

average_method =
right_endpoint_ap_sample_hold_time_weighted.v1

peak_method =
max_accepted_complete_ap_sample.v1

ap_order_method =
ap_mac_ascending.v1
```

No duplicate AP historical range object; outer `result.range` is authoritative.

---

# 28. AP item response

Preferred conceptual shape:

```text
ap_mac
display_name
display_name_source
status

history:
  buckets
  average
  peak
  coverage

now:
  status
  D/U/Total
  rate reasons
  observed_at
  age
  selected_source
```

`ap_traffic` also exposes:

```text
current_snapshot
page:
  limit
  next_cursor
```

No `share_percent`.

---

# 29. AP cursor contract

Cursor is opaque to browser.

Internal v1 context must pin at least:

```text
version
kind
site_id
range_id
from_utc
to_utc
evaluated_at_utc
bucket_seconds
last_ap_mac
```

Reject as `400 invalid_request`:

```text
bad/tampered cursor
wrong Site
wrong range
wrong bucket contract
wrong kind/version
invalid MAC
oversized cursor
```

Cursor must not contain secrets.

---

# 30. Why cursor pins historical evaluation

Page 2 must not silently shift “Last 7 days” relative to page 1.

Therefore:

```text
AP cursor
→ same historical [from,to)/evaluated_at
```

Current AP `Now` is still evaluated as current evidence on the new request and
may be newer than page 1.

This distinction is intentional.

---

# 31. AP pagination / range behavior

Initial:

```text
no cursor
```

Next:

```text
use returned next_cursor
```

Browser may keep previous opaque cursors locally for a Previous action.

On shared Network range change:

```text
clear AP cursor stack
load first AP page
```

On global Traffic Refresh:

```text
new historical evaluation
reset AP pagination to first page
```

---

# 32. Frontend ownership

TRAFFIC-05 does NOT register a second automatic AP historical loader.

It remains a passive consumer of the existing:

```text
network-traffic-history
```

coordinator execution.

AP page navigation:

```text
set local pending AP cursor
→ refreshPanel("network-traffic-history",{manual:true})
```

No:

```text
direct fetch
private timer
private AbortController
visibility/pagehide owner
retry/backoff owner
```

---

# 33. AP pagination loading semantics

AP pagination may use local presentation intent so that:

```text
AP panel shows page-loading
while accepted History/Statistics/Peak stay visually stable
```

This does not create a second lifecycle owner.

If coordinator refuses execution due backoff:

```text
no fake Loading
no applied AP-page change
previous accepted AP evidence remains visible
```

Exact frontend pending-state behavior must be frozen before FINAL.

---

# 34. Shared range and supersession

Shared range remains:

```text
24h | 7d
default 24h
```

No second selector.

Rapid:

```text
24h
→ 7d in flight
→ 24h
```

must not allow stale 7d response to update:

```text
History
Statistics
Peak
Traffic by AP
```

Latest successful non-superseded generation owns all.

---

# 35. AP selection UX

Within the currently loaded AP page:

```text
selected AP
```

is presentation-only state.

Selecting another loaded AP:

```text
zero HTTP requests
```

The selected AP drives:

```text
Download/Upload history chart
Now/Average/Peak/Coverage detail
```

---

# 36. Chart contract

Recommended:

```text
two-series line chart
Download
Upload
```

Unit:

```text
Mbps
```

X-axis:

```text
canonical Site History bucket timeline
```

Y-axis:

```text
starts at zero
```

`none` bucket:

```text
gap, not zero
```

Partial numeric evidence may be displayed but MUST be visibly distinguishable
from complete evidence.

Do not rely on color alone for critical partial/gap meaning.

---

# 37. Functional UI minimum

Panel title:

```text
Traffic by AP
```

Per loaded AP show:

```text
AP identity

Now:
Download / Upload / Total

Average:
Download / Upload / Total

Peak:
Download / Upload / Total

Coverage
```

Selected AP also shows Download/Upload history chart.

Final visual rearrangement remains a later Web Designer phase.

---

# 38. TRAFFIC-06 boundary

TRAFFIC-05 MUST NOT calculate:

```text
AP Share %
Traffic contribution %
ranking by share
```

Future `TRAFFIC-06` owns AP Traffic Share.

Permanent:

```text
sample count != traffic share
```

TRAFFIC-05 may expose reusable accepted evidence, but no share field/UI.

---

# 39. Security / feature gate

Security chain:

```text
Admin authentication
→ canonical Site resolution
→ admin.read.context
→ WEB_ADMIN_TRAFFIC_ENABLED
→ WEB_ADMIN_TRAFFIC_HISTORY_ENABLED
→ include-specific feature gate
→ AdminQueryService
→ HistoricalTrafficReadService
→ bounded CurrentTrafficReadService composition
```

No new security model.

Exact inner read capability should be checked against current policy before
FINAL; do not depend on the Home feature gate merely because the existing Home
current-AP endpoint exists.

---

# 40. Feature flag

Proposed:

```text
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED=false
```

Settings:

```text
web_admin_traffic_by_ap_enabled
```

Admin config:

```text
traffic_by_ap_enabled: bool
```

Dependency:

```text
ByAP=true
requires:
WEB_ADMIN_ENABLED=true
WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
```

It does NOT require:

```text
Statistics=true
Peak=true
```

Feature flag controls product exposure only, not service lifecycle.

---

# 41. Disabled behavior

With By-AP disabled:

```text
By-AP markup absent
no `aps` include
no AP historical projection
no AP Now composition for TRAFFIC-05

Current unchanged
History unchanged
Statistics unchanged
Peak unchanged
```

Direct authorized request containing `aps`:

```text
404 not_found
```

after normal parent security/feature boundaries.

---

# 42. Server fail-closed behavior

Canonical server AP DTO validation is fail-closed.

Malformed/cross-field-invalid AP server result:

```text
AdminQueryUnavailable
→ combined request 503
```

Do not self-heal semantic defects into HTTP 200 `unavailable`.

Browser may defensively fail the AP presentation locally if an HTTP 200 payload
somehow contains malformed AP sub-data while existing History subcontracts were
already safely parsed.

---

# 43. HTTP mappings

Reuse current Traffic History mappings:

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

No new AP-specific status family.

---

# 44. Response-size budget

Keep existing:

```text
WEB_ADMIN_MAX_RESPONSE_BYTES
```

No new TRAFFIC-05 response-size config.

DRAFT proposes mandatory AP-enabled headroom:

```text
serialized A24/A7 response
<= 80% of WEB_ADMIN_MAX_RESPONSE_BYTES
```

With current/default 1,048,576 bytes:

```text
target <= 838,860 bytes
```

This 80% threshold is explicitly for Tech Lead review before FINAL.

---

# 45. Historical SourceGateway constraints

AP projection must remain:

```text
requested-range bounded
inside same HistoricalTrafficReadService execution
inside same read-only Observation SQLite snapshot
under same shared QueryDeadline
```

Physical SQL statement count is NOT an invariant.

Additional bounded SQL projections are allowed if they reuse accepted
validation/source-selection semantics and pass query-plan/PERF gates.

Forbidden:

```text
all-history validation
second HistoricalTrafficReadService call
new SQL owner
```

---

# 46. Current AP lookup and deadline

Current AP `Now` is a separate semantic read and may use a separate bounded
read-only current snapshot.

But the whole Admin application request must use:

```text
the same shared Admin QueryDeadline
```

No separate AP deadline.

No new browser query slot.

---

# 47. Performance invariants from previous tasks

TRAFFIC-05 MUST preserve:

```text
TRAFFIC-02-PERF-01 requested-range bounding

TRAFFIC-03 materialized range path

TRAFFIC-04 typed Peak rows

TRAFFIC-04 deterministic linear/two-pointer rolling 60m
```

Do not reintroduce:

```text
unbounded scans
duplicated expensive validation paths
GROUP_CONCAT Peak sample packing
```

---

# 48. Mandatory pre-publication PERF

Official production-size Linux PERF is mandatory.

One immutable read-only snapshot.

Variants:

```text
B24/B7
accepted baseline:
History + Statistics + Peak

C24/C7
candidate:
same request without AP include

A24/A7
candidate:
History + Statistics + Peak + aps
ap_limit=4
```

Minimum:

```text
10 runs each
60 measured runs total
```

Use one fixed evaluated_at per comparison class and exact same source snapshot.

---

# 49. PERF run order / percentiles

Use deterministic interleaving such as:

```text
B → C → A
A → C → B
```

Warm-up unmeasured and equal.

For p50 and p95 use deterministic type-7-style linear interpolation:

```text
rank=(N-1)*p
lower=floor(rank)
upper=ceil(rank)

same index:
value[lower]

otherwise:
value[lower] + (rank-lower)*(value[upper]-value[lower])
```

`max` = literal maximum run.

---

# 50. PERF hard functional gates

Every variant:

```text
>=10 runs
0 query_deadline
0 source-integrity failures
0 unexpected 5xx

24h Site buckets = 288
7d Site buckets = 672
snapshot SHA unchanged
candidate tree unchanged
```

AP variants additionally:

```text
items <= 4
each AP history points:
24h = 288
7d = 672

method IDs exact
response below hard max
response meets accepted headroom gate
```

---

# 51. Candidate compatibility C vs B

Keep existing accepted envelope:

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

# 52. AP overhead A vs C

DRAFT proposes reusing the final TRAFFIC-04 amended p50 envelope:

```text
Δp50 <= max(0.50s, 30% of C.p50)
```

Keep:

```text
Δp95 <= max(0.75s, 25% of C.p95)

Δmax <= max(1.00s, 25% of C.max)

A.p95 <= 8.0s
A.max <= 9.0s
```

Any failure:

```text
PERF FAIL
```

---

# 53. PERF failure policy

Do NOT fix PERF failure by silently:

```text
increasing QueryDeadline
increasing browser timeout
increasing Admin concurrency
adding index
adding DB/schema
adding cache/rollup
weakening semantic validation
```

Required:

```text
STOP
→ profile
→ EXPLAIN/query-plan evidence
→ architecture review
```

---

# 54. Query-plan / read-only gate

Central Lab captures safe query-plan evidence for materially new AP SQL.

Prove:

```text
range bounded
existing indexes used appropriately
no all-history validation
no AP-cardinality × full-history explosion
```

Before/after official PERF:

```text
candidate tree same
snapshot SHA same
no DB writes/schema changes
```

---

# 55. Controlled Browser Acceptance

Because frontend changes:

```text
Controlled Browser Acceptance
=
MANDATORY PRE-PUBLICATION GATE
```

Same exact candidate tree after mandatory Lab/PERF.

Must prove:

```text
24h / 7d
one shared range
no second automatic AP request
AP selection = no request
pagination = same History coordinator
range/global refresh resets AP page
backoff no fake Loading
rapid supersession safe
partial/none/zero displayed truthfully
```

Browser FAIL:

```text
candidate NOT ACCEPTED
publication NOT AUTHORIZED
```

---

# 56. Focused Analytics tests

Preferred:

```text
tests/analytics/test_historical_traffic_ap.py
```

Minimum:

```text
AP population
MAC ordering
limit/cursor
Site source inheritance
NO per-AP fallback
bucket complete/partial/none
missing != zero
valid zero
complete-bucket additive identity
AP Average time weighting
Average != mean(bucket means)
Average Total invariant
AP Peak accepted evidence only
Peak Total per-sample
no AP Peak timestamp
quality counts
24h/7d range identity
```

If bounded current MAC lookup is added, focused tests prove exact equality with
the existing current AP contract.

---

# 57. Focused Admin/API tests

Preferred:

```text
tests/admin_web/test_traffic_ap.py
```

Minimum:

```text
flag default false
flag dependency
does not require Statistics/Peak
include grammar
ap_limit 1..4/default
AP params without aps → 400
cursor invalid/Site mismatch/range mismatch → 400
disabled aps → 404
enabled aps → 200
safe serializer
response-size gate
```

---

# 58. Focused frontend tests

Preferred:

```text
tests/admin_web/test_traffic_ap_frontend.py
```

Minimum:

```text
no second range selector
no second coordinator
no independent automatic AP loader
no direct fetch
no private timer
no AP AbortController
no visibility/pagehide owner

aps include only when enabled

AP selection → zero request

pagination → refreshPanel(network-traffic-history)

range/global refresh resets cursor

backoff no fake Loading

rapid supersession

browser does not calculate:
source
Average
Peak
Total
```

---

# 59. Central Lab regression

Central Lab official targeted boundary includes:

```text
TRAFFIC-00
TRAFFIC-01
TRAFFIC-02-READ
TRAFFIC-02-PERF-01
TRAFFIC-02
TRAFFIC-03
TRAFFIC-04
TRAFFIC-05
```

Also verify fixed-context equality:

```text
TRAFFIC-05 AP Now
=
CurrentTrafficReadService AP item
```

and complete-bucket identity:

```text
Σ complete AP bucket values
=
Site History bucket value
```

No exact equality is required for partial AP populations.

---

# 60. Coder vs Central Lab ownership

Coder runs only:

```text
focused/minimal TRAFFIC-05 tests
directly affected module tests
compileall
git diff --check
```

Coder does NOT own:

```text
official full regression
official production-size PERF
official Controlled Browser gate
official PASS/FAIL
```

Expected focused command shape:

```bash
python -m pytest -q \
  tests/analytics/test_historical_traffic_ap.py \
  tests/admin_web/test_traffic_ap.py \
  tests/admin_web/test_traffic_ap_frontend.py
```

Exact command is frozen after implementation file names exist.

---

# 61. Expected implementation files

Expected MODIFY:

```text
app/analytics/models.py
app/analytics/historical_traffic.py
app/analytics/source_gateway.py
app/analytics/current_traffic.py          # only if bounded MAC lookup needed
app/analytics/__init__.py

app/config.py
app/settings.py
.env.example

app/admin_web/config.py
app/admin_web/pages.py
app/admin_web/query_service.py
app/admin_web/routes.py
app/admin_web/historical_traffic_serialization.py
app/admin_web/current_traffic_serialization.py   # only narrow reuse/extraction

app/admin_web/static/admin.js
app/admin_web/static/admin.css
app/admin_web/templates/admin/traffic.html
```

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

If an expected-unchanged production file becomes necessary:

```text
STOP
→ exact reason
→ architecture impact review
```

---

# 62. No new persistence/acquisition

Not authorized:

```text
new collector
new Omada polling
new Traffic DB
Observation migration
new index
cache
rollup
new dependency
```

If v1 cannot pass PERF/payload limits:

```text
STOP
```

Do not silently expand architecture.

---

# 63. Rollout / rollback

Repository default:

```text
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED=false
```

Stage 1:

```text
deploy accepted Git artifact
flag=false
```

Dormant acceptance:

```text
Current PASS
History PASS
Statistics PASS
Peak PASS
By-AP absent
no aps include
no new deadline/error pattern
```

Stage 2 — separate Owner action:

```text
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED=true
```

Production acceptance:

```text
24h/7d
AP identity
Now
Average
Peak
Coverage
chart
AP selection
pagination if present
existing panels unchanged
```

Rollback:

```text
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED=false
```

No DB/schema rollback.

---

# 64. Explicit non-goals

Out of TRAFFIC-05:

```text
TRAFFIC-06 AP Traffic Share
share %
ranking by share

TRAFFIC-07 Online Guests
TRAFFIC-08 Completed Guest Sessions
TRAFFIC-09 Evidence consolidation

AP Peak timestamps
AP busiest bucket/hour

30d UI
Heatmap
Period Comparison

traffic volume MB/GB
SSID/guest throughput
Home redesign
final Traffic visual redesign
```

---

# 65. Architecture decisions — DRAFT

1. `Traffic by AP` is Network Traffic/Mbps.
2. Historical owner stays `HistoricalTrafficReadService`.
3. Current `Now` owner stays `CurrentTrafficReadService`.
4. `Now` is not the final History bucket.
5. AP history inherits Site-bucket selected source.
6. Per-AP wired/LAN fallback is forbidden.
7. AP identity = canonical MAC.
8. Backend order = MAC ascending.
9. Proposed AP page max = 4.
10. 24h/7d points stay 288/672 per AP.
11. Browser displays one AP chart at a time, D/U only.
12. AP History bucket mean is not AP Period Average.
13. AP Average is interval/time-aware.
14. AP Peak uses accepted AP samples.
15. AP Peak timestamp excluded v1.
16. Existing History endpoint gains exact `aps` include forms.
17. No automatically loaded separate AP endpoint.
18. AP cursor pins historical evaluation.
19. Range/global refresh resets AP pagination.
20. Existing Traffic coordinator remains lifecycle owner.
21. Feature flag default false.
22. By-AP requires Admin+Traffic+History, not Statistics/Peak.
23. Mandatory PERF and Controlled Browser are pre-publication.
24. No timeout/deadline/concurrency increase.
25. No collector/DB/schema/index/cache/rollup.

---

# 66. Review questions

Owner + Tech Lead should explicitly accept/revise:

### Q1
Use recommended **Option C**?

```text
bounded AP projection inside existing History execution
```

Architect recommendation: `ACCEPT`.

### Q2
AP page max:

```text
4
```

Architect recommendation: `ACCEPT`, subject to PERF/payload evidence.

### Q3
Display name:

```text
current → historical → MAC
```

Architect recommendation: `ACCEPT`.

### Q4
AP Average:

```text
right_endpoint_ap_sample_hold_time_weighted.v1
```

Architect recommendation: `ACCEPT`.

### Q5
AP Peak:

```text
max_accepted_complete_ap_sample.v1
```

without AP timestamp?

Architect recommendation: `ACCEPT`.

### Q6
AP-enabled response headroom:

```text
<=80% of WEB_ADMIN_MAX_RESPONSE_BYTES
```

Architect recommendation: `ACCEPT`.

### Q7
A-vs-C p50 PERF envelope:

```text
max(0.50s, 30% of C.p50)
```

with all current p95/max limits unchanged?

Architect recommendation: `ACCEPT`.

---

# 67. Stop conditions

Implementation MUST STOP if it requires:

```text
new Traffic semantic owner
new collector / Omada read
new DB/schema/index/cache/rollup
per-AP independent source fallback
Mbps recalculation from raw counters
radio as Network Traffic source
browser Average/Peak/source calculation
raw 30s AP history
new Network range selector
independent AP scheduler/coordinator
automatic second AP historical request
timeout/deadline/concurrency increase
TRAFFIC-02/03/04 semantic change
CurrentTrafficReadService source-policy change
TRAFFIC-06 Share scope
```

Also STOP on material `origin/main` drift.

---

# 68. DRAFT status

```text
TASK:
TASK-TRAFFIC-05 — Traffic by AP

STATUS:
DRAFT — FOR OWNER + TECH LEAD ARCHITECTURAL REVIEW

REPOSITORY BASELINE:
main@f58679351fa6cd8558f67234937a7706fb4f3dae

TREE:
d22c54100d80540e4cc9506b3f51323d7ee8201c

PRODUCTION / RUNTIME CHECKPOINT:
a9cd8a9b9b9efc46bc82d315385ebbd1a3bf63b0

PRODUCTION / RUNTIME TREE:
f53f204cf3ebf7cecf4e872ce450b4f3f4265cc9

HISTORICAL OWNER:
HistoricalTrafficReadService

CURRENT AP OWNER:
CurrentTrafficReadService

RANGES:
24h / 7d shared Network range

AP PAGE LIMIT PROPOSAL:
4

SEPARATE AUTOMATIC AP HISTORICAL REQUEST:
NO

FEATURE DEFAULT:
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED=false

NEW ACQUISITION:
NO

NEW OMADA DEPENDENCY:
NO

NEW DB / SCHEMA / INDEX / CACHE / ROLLUP:
NO

MANDATORY PERF:
PRE-PUBLICATION

CONTROLLED BROWSER:
PRE-PUBLICATION

IMPLEMENTATION AUTHORIZATION:
NOT GRANTED

PUBLICATION / MERGE / DEPLOY / ACTIVATION:
NOT GRANTED
```

Next:

```text
Owner + Tech Lead review
→ targeted revision
→ FINAL
→ separate Owner implementation authorization
```

Implementation MUST NOT begin from this DRAFT.
