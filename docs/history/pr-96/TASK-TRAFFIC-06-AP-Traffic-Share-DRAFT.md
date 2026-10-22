# TASK-TRAFFIC-06 — AP Traffic Share — DRAFT

**Project:** CaptivPortal  
**Area:** Admin Console → Traffic  
**Roadmap item:** `TRAFFIC-06 — AP Traffic Share`  
**Type:** architecture / derived historical Network Traffic share product  
**Prepared:** 2026-09-01  
**Implementation authorization:** `NOT GRANTED`  
**Publication / merge / deploy / activation:** `NOT AUTHORIZED`

---

# 1. Status

```text
TRAFFIC-06 — AP Traffic Share

NEXT / DRAFT REQUESTED / NOT IMPLEMENTED

ARCHITECTURE DRAFT ONLY
IMPLEMENTATION NOT AUTHORIZED
FINAL NOT DECLARED
```

Current KB intent:

```text
share of accepted Network Traffic evidence within selected range
sample count != traffic share
```

This DRAFT is for Owner + Tech Lead architecture review only.

---

# 2. Current repository / KB baseline

Verified current repository / KB baseline:

```text
main:
022c8666ef58f0a6d4bef9dd72696199ebd5719f

tree:
a231cb06f15469ed99f0f8f4256b3ebc439467f2
```

This is merge PR #95:

```text
Docs: reconcile TRAFFIC-05 and independent ranges production state
```

PR #95 changes current documentation only; application code/tests/runtime/production
are unchanged.

Reviewed current sources include:

```text
README.md
README_RU.md
docs/README.md
docs/architecture.md
docs/configuration.md
docs/deployment.md
docs/module-index.md
docs/modules/admin-web.md
docs/modules/analytics.md
docs/modules/traffic.md
docs/project-inventory.md
docs/testing.md
```

Relevant current implementation/tests were also reviewed:

```text
app/analytics/historical_traffic.py
app/analytics/source_gateway.py
app/admin_web/query_service.py
app/admin_web/routes.py
app/admin_web/historical_traffic_serialization.py
app/admin_web/static/admin.js
tests/analytics/test_historical_traffic_ap.py
tests/admin_web/test_traffic_independent_ranges.py
tests/admin_web/test_traffic_independent_ranges_frontend.py
```

Before FINAL and again before implementation authorization:

```text
re-fetch origin/main
re-pin SHA/tree
impact-review drift
```

---

# 3. Current production/runtime baseline

Current implementation / production baseline:

```text
HEAD:
daf68e91fc759188980cf8741913e6b60a58eb62

tree:
b0e2f028eecf6aec9d86e35542c33e7105209335
```

Current Traffic surface:

```text
Current Network Throughput
Network Traffic History
Period Statistics
Peak Load
Traffic by AP
```

`TRAFFIC-RANGE-01` is production-active and accepted.

Production/current architecture includes:

```text
independent 24h|7d historical selectors
products= projection
TrafficHistoricalRequestBroker
CaptivPortalTrafficCoordinator
max historical in-flight = 1
10-second historical dispatch admission guard
```

Preserved limits:

```text
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS = 10
Traffic browser request timeout = 20s
Admin query concurrency = unchanged
```

Historical PERF measurements are evidence only, not TRAFFIC-06 SLOs.

---

# 4. Goal / user question

Panel name:

```text
AP Traffic Share
```

Primary question:

```text
What share of accepted Site Network Traffic evidence
within this panel's applied range was contributed by each AP?
```

Range:

```text
24h | 7d
```

independent from History, Statistics, Peak and Traffic by AP.

Visible conceptual result per AP:

```text
Total Share
Download Share
Upload Share
```

The result is a dimensionless proportion, not MB/GB volume.

---

# 5. Non-goals

TRAFFIC-06 does NOT implement or redefine:

```text
WAN / Internet Traffic
Guest Traffic
Guest Session Traffic
SSID Traffic
billing traffic
traffic volume MB/GB
sample-count share
client-count share
airtime/utilization share
```

It does NOT change accepted formulas/contracts of:

```text
History
Period Statistics
Peak Load
Traffic by AP
Current Network Throughput
```

It does NOT add by default:

```text
collector
Omada query path
DB/schema/table/index
cache/rollup
retention/cadence changes
second historical owner
second scheduler
QueryDeadline increase
browser timeout increase
Admin concurrency increase
```

---

# 6. Current dependencies

TRAFFIC-06 depends on accepted:

```text
TRAFFIC-02-READ / HistoricalTrafficReadService
TRAFFIC-02 / History
TRAFFIC-02-PERF-01 / requested-range bounding
TRAFFIC-03 / accepted interval weighting
TRAFFIC-05 / AP population and selected-source AP facts
TRAFFIC-RANGE-01 / products=, independent ranges, broker/coordinator/guard
```

Canonical source remains:

```text
persisted AP Observation history
```

No query-time Omada read.

---

# 7. Existing Traffic invariants inherited unchanged

Network Traffic means:

```text
AP/network throughput evidence
source rate unit = Mbps
```

Not Internet/WAN/guest/SSID/billing.

Owners:

```text
HistoricalTrafficReadService = single historical semantic owner
CurrentTrafficReadService    = current Network semantic owner
```

Source family:

```text
canonical Site source selection
wired/lan according to current rules
radio excluded
no per-AP fallback inside one accepted Site sample
```

Historical execution remains:

```text
requested-range bounded
read-only
shared Admin QueryDeadline
fail-closed integrity
```

Browser remains passive for canonical analytics.

---

# 8. Semantic owner

Recommendation:

```text
HistoricalTrafficReadService
```

owns AP Traffic Share.

Conceptually:

```text
accepted Site samples/intervals
+
accepted selected-source AP facts
→ AP Traffic Share
```

Do NOT create a parallel historical `ApTrafficShareReadService`.

`AnalyticsSourceGateway` may provide additional bounded range facts, but does not
own Share semantics.

`CurrentTrafficReadService` may contribute current AP population/name context needed
to preserve `current_union_historical_validated.v1`; current rates MUST NOT enter
Share numerator or denominator.

---

# 9. AP population / identity model

Recommendation: reuse exact TRAFFIC-05 population:

```text
current_union_historical_validated.v1
```

for one authorized canonical Site and Share applied range.

Identity:

```text
canonical AP MAC
```

Display name:

```text
current accepted name
→ latest accepted historical name
→ MAC
```

Policies:

- current-only AP remains visible; without weighted historical presence its Share
  values are null, not invented `0%`;
- historical-only/disappeared AP remains visible and may have numeric Share;
- replacement AP with another MAC is a separate identity;
- same display name does not merge MAC identities;
- no cross-Site population mixing.

DRAFT recommendation: reuse current hard cap:

```text
12 APs per authorized canonical Site
```

Rationale: Share is a complete decomposition of the same AP population and should
not claim completeness when TRAFFIC-05 declares that population unsupported.

```text
<=12 → return all
>12  → unsupported_population
        returned_ap_count=0
        items=[]
```

No top-N, pagination or silent truncation.

---

# 10. Exact Share metric proposal

Recommended identifiers:

```text
metric_version =
network_traffic_ap_share.v1

share_method =
accepted_site_interval_integrated_ap_contribution_ratio.v1

temporal_method =
right_endpoint_sample_hold_time_weighted.v1

absence_method =
complete_site_sample_absence_zero_contribution.v1

population_method =
current_union_historical_validated.v1

order_method =
total_share_desc_nulls_last_ap_mac_ascending.v1
```

Canonical API unit:

```text
fraction
```

Numeric range:

```text
0.0 .. 1.0
```

UI displays percent.

---

# 11. Formula / numerator / denominator

Use the same canonical accepted Site interval population as the accepted
time-aware Statistics model.

Ordered accepted Site sample placement:

```text
t_i = cycle.finished_at
```

Candidate interval:

```text
I_i = (t_(i-1), t_i]
Δ_i = t_i - t_(i-1)
```

Reuse existing interval exclusion semantics for invalid elapsed, source transition
and excessive gap. Do not create a second interval classifier.

For each accepted interval, right endpoint Site rates are:

```text
S_i^D
S_i^U
S_i^T = D + U
```

For AP `a`, use exact selected-source AP rates from the same accepted right-endpoint
Site sample:

```text
A_(a,i)^D
A_(a,i)^U
A_(a,i)^T
```

## Structural absence

If AP `a` is absent from an otherwise complete accepted Site sample, Share-only
decomposition treats that AP contribution at that sample as:

```text
0
```

This does NOT redefine generic missing evidence as zero.

If an AP row is present but selected-source evidence is invalid, do NOT zero-fill.
The affected Site sample/interval must remain excluded according to existing
historical integrity/quality semantics.

## Integrated internal weights

For direction `k`:

```text
SITE_WEIGHT_k = Σ(S_i^k × Δ_i)

AP_WEIGHT_(a,k) = Σ(A_(a,i)^k × Δ_i)
```

These internal weights are not exposed/labeled as traffic volume or MB/GB.

Canonical Share:

```text
if SITE_WEIGHT_k > 0:

SHARE_(a,k) =
AP_WEIGHT_(a,k) / SITE_WEIGHT_k
```

If:

```text
SITE_WEIGHT_k = 0
```

directional Share is undefined:

```text
null
```

not zero.

Sample count is never numerator or denominator.

Bucket means, AP Average and AP Peak are not canonical Share inputs.

---

# 12. Coverage and quality semantics

Share exposes exact interval evidence, at minimum:

```text
range_seconds
candidate_interval_count
accepted_interval_count
accepted_interval_seconds
excluded_gap_interval_count
excluded_source_transition_interval_count
invalid_period_interval_count
accepted_endpoint_sample_count
```

Interval classification must be identical to the existing historical
time-weighted classifier.

Recommended Share coverage:

```text
complete
partial
none
```

`none`:

```text
accepted_interval_count = 0
```

`complete`:

```text
outer Historical status=ok
AND accepted intervals exist
AND no Share interval exclusion
```

`partial`:

```text
trusted accepted intervals exist
but outer/interval coverage is incomplete
```

Directional denominator status:

```text
positive
zero_traffic
insufficient_data
```

Rules:

```text
no accepted intervals → insufficient_data
accepted intervals + weight=0 → zero_traffic
weight>0 → positive
```

Per AP expose evidence such as:

```text
accepted_presence_interval_count
accepted_presence_seconds
```

so valid observed zero is distinguishable from no weighted historical presence.

---

# 13. Status model

Recommended top-level Share statuses:

```text
ok
partial
insufficient_data
unsupported_population
```

No separate top-level `no_traffic` is recommended.

Valid zero traffic is represented through denominator status `zero_traffic`.

`ok`:
```text
supported population
accepted intervals exist
coverage complete
```

`partial`:
```text
supported population
accepted intervals exist
trusted Share exists
coverage incomplete
```

Numeric partial Share means:

```text
Share within accepted comparable evidence
```

not an estimate over missing intervals.

`insufficient_data`:
```text
no accepted intervals
all Share fractions null
```

`unsupported_population`:
```text
population >12
items=[]
```

Recommended AP item evidence status:

```text
ok
insufficient_data
```

Current-only/no weighted-presence AP:

```text
insufficient_data
shares=null
```

AP with accepted presence and true zero contribution may have numeric `0.0`
when the Site denominator is positive.

---

# 14. Traffic-by-AP identity invariants

For the same fixed:

```text
Site
range
evaluated_at
current AP context
source snapshot
```

require:

```text
TrafficByAP population_count = APShare population_count
TrafficByAP MAC set = APShare MAC set
supported_max_ap_count = 12 in both
unsupported decision identical
display names/name sources identical
```

Both products use the same selected-source AP sample facts.

Semantic divergence point:

```text
common AP/Site samples
     ↓
TRAFFIC-05:
series / Average / Peak / Coverage

TRAFFIC-06:
time-integrated contribution ratio
```

Share MUST NOT be calculated from serialized TRAFFIC-05 payload in browser.

For same fixed context:

```text
Share-only result
=
Share sub-result of products=aps,apshare
```

If both are requested, internal AP/sample materialization SHOULD be reused where
practical inside one HistoricalTrafficReadService execution.

---

# 15. API projection design

Options:

### A. Share implicit in `aps`
Rejected recommendation: Share has its own panel/range and `products=apshare`
should not require AP history arrays/Average/Peak/Now projection.

### B. New endpoint
Rejected recommendation: duplicates current historical route/security/projection
boundary and weakens coalescing.

### C. New `products=` token
Recommended.

Exact token:

```text
apshare
```

Existing endpoint remains:

```text
GET /admin/api/v1/sites/<site_id>/traffic/history
```

Proposed canonical product order:

```text
history,statistics,peak,aps,apshare
```

Examples:

```text
?range=24h&products=apshare
?range=7d&products=apshare
?range=7d&products=aps,apshare
```

Out-of-order/duplicate/unknown/whitespace/empty projections remain `400`.

Recommendation:

```text
legacy include= is NOT extended with Share
```

`include + products` remains `400`.

`products=apshare` must not execute/serialize unrelated product-specific:

```text
History chart
Statistics
Peak Load
full Traffic-by-AP series/Average/Peak/Now
```

Shared range/source/integrity/AP-population foundation is allowed.

---

# 16. Serialization contract

When requested, response adds:

```text
ap_traffic_share
```

Common current fields remain:

```text
status
range
coverage
quality
requested_products
```

Conceptual Share DTO:

```text
status
metric_version
unit=fraction
display_unit=percent
share_method
temporal_method
absence_method
population_method
order_method

population:
  population_count
  current_population_count
  historical_population_count
  supported_max_ap_count
  returned_ap_count
  population_complete

coverage:
  status
  range_seconds
  candidate_interval_count
  accepted_interval_count
  accepted_interval_seconds
  excluded_gap_interval_count
  excluded_source_transition_interval_count
  invalid_period_interval_count
  accepted_endpoint_sample_count

denominators:
  download_status
  upload_status
  total_status

items[]
```

Item:

```text
ap_mac
display_name
display_name_source
evidence_status
accepted_presence_interval_count
accepted_presence_seconds
download_share_fraction
upload_share_fraction
total_share_fraction
```

No raw integrated weights.

Numeric fractions:

```text
finite
0 <= value <= 1
```

Malformed values fail closed; do not clamp.

For every direction with positive denominator:

```text
abs(fsum(numeric_shares) - 1.0) <= 1e-9
```

Zero/insufficient denominator requires all fractions for that direction to be null.

Server keeps unrounded fractions.

UI formatting recommendation:

```text
exact zero → 0.00%
0 < percent < 0.01 → <0.01%
otherwise → 2 decimals
```

Displayed rounded percentages need not visually total exactly 100%; canonical server
fractions do.

---

# 17. Independent-range integration

Share becomes another independent historical panel with:

```text
24h | 7d
```

It owns page-local:

```text
selected_range
applied_range
phase
last successful payload
error
intent generation
```

Fresh page:

```text
selected=24h
applied=null until success
```

Failed range switch:

```text
selected=new range
applied=previous successful range
previous payload preserved
```

Reload resets Share to 24h.

No localStorage/sessionStorage/cookie/URL/server persistence.

---

# 18. Broker/coordinator integration

Broker product id:

```text
apshare
```

`TrafficHistoricalRequestBroker` owns Share intent/coalescing/generation mapping.

`CaptivPortalTrafficCoordinator` remains sole scheduler/lifecycle owner.

Permanent:

```text
max historical HTTP requests in flight = 1
```

Initial all-24h MAY coalesce:

```text
products=history,statistics,peak,aps,apshare
```

Share-only click:

```text
range=7d&products=apshare
```

must not automatically request other panels.

If AP and Share have same pending range:

```text
products=aps,apshare
```

may coalesce.

Global Refresh groups Share by its own selected range.

Latest Share intent wins; stale response cannot overwrite newer selected range.

No Share-specific fetch/timer/AbortController/scheduler.

---

# 19. Admission guard interaction

Inherit unchanged:

```text
HISTORICAL_TRAFFIC_REQUEST_ADMISSION_GUARD_SECONDS = 10
```

Eligibility:

```text
next_dispatch >= max(
  previous_request_completion,
  previous_dispatch + 10s,
  coordinator Retry-After/backoff/lifecycle eligibility
)
```

Share cannot bypass via:

```text
range click
retry
Global Refresh
503 recovery
coalescing
```

`waiting` means queued/admission blocked.

`loading` means actual request containing `apshare` is in flight.

Selectors remain interactive while waiting.

Pending Share intents collapse to latest.

---

# 20. UI product contract

Panel:

```text
AP Traffic Share
```

Explanation:

```text
Share of accepted Site Network Traffic evidence
within this panel's applied range.
```

Show all supported APs simultaneously, not top-N.

Per AP:

```text
label
Total Share
Download Share
Upload Share
coverage/evidence qualifier
```

Recommended order:

```text
Total Share descending
null Total last
tie → AP MAC ascending
```

If all Total shares null:

```text
AP MAC ascending
```

One AP + positive Total denominator:

```text
Total Share = 100%
```

Directional 100% only when that directional denominator is positive.

Valid all-zero traffic:

```text
No accepted Network Traffic was observed in this range.
```

Do not invent a 0% distribution.

Partial:

```text
numeric values may display
with explicit Partial qualifier
```

Insufficient:

```text
no percentages
```

>12:

```text
unsupported_population
no first-12 subset
```

Waiting/loading/error preserves prior successful payload/applied range exactly per
RANGE-01.

This TASK does not freeze final visual card layout.

---

# 21. Security / Site isolation

TRAFFIC-06 is strictly Site-scoped.

Authorized canonical Site is the data-isolation boundary.

Site B MUST NOT affect Site A:

```text
population
numerator
denominator
Share values
unsupported decision
coverage
response metadata
telemetry
```

Frontend filtering is not an authorization boundary.

No browser/source direct access and no Omada request path.

Current centralized Admin authorization remains owner of access policy.

Future Principal/Tenant/RBAC policy may change authorization without changing Share
metric semantics.

---

# 22. Observability

Extend existing Admin Traffic telemetry only.

Recommended fields:

```text
range
requested_products
product_count
share_status
share_population_count
share_returned_ap_count
share_supported_max_ap_count
share_coverage_status
share_accepted_interval_count
share_accepted_interval_seconds
duration_ms
response_bytes
failure_reason
query_deadline
share_unsupported_population
share_integrity_failure
```

Do not log:

```text
raw AP contribution arrays
all Share fractions
SQL
DB path
cross-Site cardinality
```

No new observability subsystem.

---

# 23. Performance contract

TRAFFIC-06 gets new pre-publication PERF gates.

Prior measured timings are NOT thresholds.

Canonical compatibility baseline code:

```text
commit:
daf68e91fc759188980cf8741913e6b60a58eb62

tree:
b0e2f028eecf6aec9d86e35542c33e7105209335
```

Run baseline/candidate on:

```text
same production-compatible Linux environment
same immutable production-size Observation snapshot
same snapshot SHA/bytes
same fixed evaluated_at
same resolved range
same QueryDeadline=10s
same API timing boundary
```

Minimum:

```text
10 measured runs per variant
documented unmeasured warmups
```

Percentiles use deterministic linear/type-7 style:

```text
rank=(N-1)*p
linear interpolation between floor/ceil rank
max=literal maximum
```

## Mandatory Share-only

```text
SH24 = range=24h&products=apshare
SH7  = range=7d&products=apshare
```

Record:

```text
p50/p95/max
successes
query_deadline
source-integrity failures
unexpected 5xx
response bytes
status
population
coverage
```

New TRAFFIC-06 hard gates, justified from unchanged 10s deadline:

```text
p95 <= 8.0s
# reserves 20% deadline headroom at p95

max <= 9.0s
# reserves 1s / 10% before hard deadline

query_deadline = 0
source-integrity failures = 0
unexpected 5xx = 0
```

Share-only response proposal:

```text
<=25% WEB_ADMIN_MAX_RESPONSE_BYTES
```

because at most 12 aggregate items and no history arrays.

## AP backward-compatibility

Measure baseline/current AP-only and candidate AP-only:

```text
BA24/BA7 = baseline products=aps
CA24/CA7 = candidate products=aps
```

Proposed relative gates:

```text
Δp50 <= max(0.50s, 20% baseline p50)
Δp95 <= max(0.75s, 25% baseline p95)
Δmax <= max(1.00s, 25% baseline max)
```

Candidate AP-only hard:

```text
p95<=8s
max<=9s
0 deadline/integrity/unexpected5xx
```

## Coalesced AP + Share

Mandatory:

```text
AS24 = products=aps,apshare
AS7  = products=aps,apshare
```

Against candidate AP-only:

```text
Δp50 <= max(0.50s, 20% CA.p50)
Δp95 <= max(0.75s, 25% CA.p95)
Δmax <= max(1.00s, 25% CA.max)
```

Hard:

```text
p95<=8s
max<=9s
0 deadline/integrity/unexpected5xx
```

Proposed AS7 payload:

```text
<=75% WEB_ADMIN_MAX_RESPONSE_BYTES
```

Initial all-products 24h smoke/PERF also requires:

```text
0 failures
p95<=8s
max<=9s
response below hard platform max
```

Capture query-plan evidence for materially new Share SQL and prove:

```text
requested-range bounded
no all-history validation
no second historical owner
no N×full-history explosion
population cap checked before over-bound materialization
```

If SH7/AS7 fails accepted PERF:

```text
STOP
→ profile/query-plan evidence
→ architecture/PERF review
```

Do NOT increase QueryDeadline/browser timeout/Admin concurrency or silently add
index/cache/rollup.

---

# 24. Backward compatibility

When Share is not requested, fixed-context results must remain unchanged:

```text
products=history
products=statistics
products=peak
products=aps
legacy include=
```

Current metric versions remain unchanged.

`products=` grammar is extended only by `apshare` as final canonical token.

No Share panel action changes another panel's selected/applied range.

Current Network Throughput remains range-insensitive.

Traffic-by-AP population/12-cap/Average/Peak/Coverage/source semantics do not change.

---

# 25. Feature flag

Recommended:

```text
WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED=false
```

Repository default false.

Recommended dependencies:

```text
WEB_ADMIN_ENABLED=true
WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED=true
```

Do NOT require product exposure flags for:

```text
Traffic by AP
Statistics
Peak
```

Share is an independent product projection over shared evidence.

Flag controls product exposure only; it does not start/stop Analytics or acquisition.

Flag false:

```text
panel absent
broker does not queue apshare
direct products=apshare → 404 after normal security/parent gates
```

---

# 26. Testing / acceptance gates

Testing governance remains current.

Coder: focused/minimal TASK development verification.

Owner + Tech Lead/Central Lab: official targeted/full/PERF/PASS-FAIL.

Mandatory semantic cases:

```text
exact formula/method IDs
sample-count counterexample
bucket-average counterexample
D/U/Total Share
one AP 100%
multiple AP sum-to-one
valid zero
all-zero Site
direction zero
partial coverage
gap/source transition/invalid elapsed
structural absence zero
present-invalid evidence not zero-filled
no intervals
current-only
historical-only
disappeared/replacement AP
```

Population:

```text
1/2/12 supported
13 unsupported
no truncation
deterministic order
Site-local cap
```

Traffic-by-AP identity:

```text
same population/MACs/names/unsupported decision
same common selected-source sample facts
Share-only = Share sub-result in aps,apshare
AP-only unchanged
```

API:

```text
flag/default/dependencies
auth/Site isolation
products grammar with apshare
projection isolation
include compatibility unchanged
requested_products
fail-closed serialization
response-size handling
```

Serializer:

```text
fractions finite/in range
positive denominator sums=1 within 1e-9
zero/insufficient denominator → null
current-only insufficient → null
unsupported → zero items
cross-field corruption rejected
```

Frontend:

```text
independent selected/applied
waiting/loading
previous payload retained
latest intent wins
stale response rejected
same-range coalescing
Global Refresh
reload→24h
guard/retry/backoff rules
max in-flight=1
no second scheduler/timer/AbortController
all APs displayed
zero/partial/insufficient/unsupported states
```

Security:

```text
Site A request never uses/leaks Site B AP evidence/count
```

PERF: all Section 23 mandatory variants/gates.

---

# 27. Rollout / dormant activation

Canonical flow:

```text
implementation/patch
→ focused TASK evidence
→ Owner+Tech Lead targeted regression
→ Central Lab full gate
→ mandatory Linux PERF
→ all mandatory gates PASS
→ accepted candidate
→ Git publication
→ Owner merge
→ deploy FROM GIT with Share OFF
→ dormant acceptance
→ separate Owner activation
→ production browser/product acceptance
```

Dormant:

```text
WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED=false
```

Must preserve all current Traffic products/ranges/guard without `apshare` execution.

Separate activation:

```text
WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED=true
```

Production acceptance covers 24h/7d, independent range, D/U/Total Share, all
supported APs, quality states, and orchestration protections.

---

# 28. Rollback considerations

Primary rollback:

```text
WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED=false
```

Expected:

```text
Share panel removed
no apshare broker intent
all existing Traffic products remain active
independent ranges remain active
```

No DB/schema/data rollback.

If code rollback is required, use approved Git deployment procedure.

Do not delete Observation history.

---

# 29. Explicit architectural decisions required

Current analysis finds no proven requirement for:

```text
new DB/schema/index
cache/rollup
collector/Omada read
retention/cadence change
deadline/timeout/concurrency change
```

Therefore none is authorized in this DRAFT.

If implementation cannot meet approved semantics/PERF without one:

```text
STOP
```

Return:

```text
EXPLICIT ARCHITECTURAL DECISION REQUIRED
```

with root cause, profile/query-plan evidence, alternatives, risks, migration and
rollback impact.

---

# 30. Unresolved questions

These recommendations require Owner + Tech Lead review before FINAL.

### Q1 — formula
Accept `accepted_site_interval_integrated_ap_contribution_ratio.v1`?

Architect recommendation: `ACCEPT`.

### Q2 — structural absence
Accept zero contribution only when AP is absent from an otherwise complete accepted
Site sample, while present-invalid evidence is never zero-filled?

Architect recommendation: `ACCEPT`.

### Q3 — population
Reuse `current_union_historical_validated.v1` and 12-AP Site-local cap?

Architect recommendation: `ACCEPT`.

### Q4 — zero Traffic
Keep top-level `ok|partial|insufficient_data|unsupported_population` and express
valid no-traffic through directional `zero_traffic` denominator status instead of
a new top-level `no_traffic`?

Architect recommendation: `ACCEPT`.

### Q5 — API
Add exact token `apshare` and canonical order
`history,statistics,peak,aps,apshare`, without extending legacy include?

Architect recommendation: `ACCEPT`.

### Q6 — ordering
Use Total Share descending, null last, MAC ascending tie?

Architect recommendation: `ACCEPT`.

### Q7 — all APs
Show all supported APs, not top-N?

Architect recommendation: `ACCEPT`.

### Q8 — feature flag
Accept `WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED=false`, requiring
Admin+Traffic+History+IndependentRanges but not Traffic-by-AP exposure?

Architect recommendation: `ACCEPT`.

### Q9 — PERF
Accept new Section 23 Share-only/coalesced hard/relative/payload gates?

Architect recommendation: `ACCEPT`.

---

# 31. Acceptance criteria

Candidate acceptance requires all approved FINAL gates to PASS on the exact tree.

Minimum:

```text
Share = time-integrated accepted AP contribution ratio
not sample count

D/U/Total use identical accepted Site interval basis

positive-direction fractions sum to 1 within 1e-9

valid zero distinct from missing evidence

structural absence rule exact

current-only AP not falsely shown as historical 0%

historical-only/disappeared AP supported

population complete and Site-scoped through 12 AP

>12 explicit unsupported, no subset

browser does not own formula

HistoricalTrafficReadService remains sole historical owner

no new acquisition/storage/Omada path

products=apshare exact and projection-isolated

aps,apshare coalescing semantically identical to separate Share

independent selected/applied range

broker/coordinator/admission guard unchanged

existing Traffic regressions = 0

Site isolation PASS

SH24/SH7 PERF PASS

AP compatibility PERF PASS

AP+Share PERF PASS

payload gates PASS

QueryDeadline/browser timeout/Admin concurrency unchanged

feature deploys default OFF

activation remains separate Owner authorization
```

Any mandatory semantic/security/PERF failure:

```text
candidate NOT ACCEPTED
normal publication NOT AUTHORIZED
```

This DRAFT does not authorize implementation.

STATUS: DRAFT — AWAITING OWNER / TECH LEAD ARCHITECTURE REVIEW
