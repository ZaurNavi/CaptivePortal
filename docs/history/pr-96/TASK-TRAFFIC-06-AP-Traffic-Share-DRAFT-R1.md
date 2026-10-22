# TASK-TRAFFIC-06 — AP Traffic Share — DRAFT R1

**Project:** CaptivPortal  
**Area:** Admin Console → Traffic  
**Roadmap item:** `TRAFFIC-06 — AP Traffic Share`  
**Document state:** `DRAFT R1`  
**Prepared:** 2026-09-01  
**Owner / Tech Lead review source:** R1 corrections received 2026-09-01  
**Implementation authorization:** `NOT GRANTED`  
**Code / patch / PR / merge / deploy / activation:** `NOT AUTHORIZED`

---

# 1. Status

```text
TASK:
TRAFFIC-06 — AP Traffic Share

STATUS:
DRAFT R1

ROADMAP POSITION:
NEXT / DRAFT REQUESTED / NOT IMPLEMENTED

ARCHITECTURAL DIRECTION:
ACCEPTED WITH R1 HARDENING

IMPLEMENTATION:
NOT AUTHORIZED

FINAL:
NOT DECLARED
```

This document is a fully rebuilt architecture DRAFT R1 after Owner / Tech Lead review.

It does not authorize:

```text
production code
Coder implementation
Git publication
PR creation
merge
deployment
feature activation
production changes
```

Current product intent remains:

```text
share of accepted Network Traffic evidence within selected range

sample count != traffic share
```

---

# 2. Baseline model: TASK development parent vs runtime/PERF reference

Two baselines are intentionally distinct.

## 2.1 TASK development parent baseline

Current Git / Knowledge Base main re-verified before R1:

```text
main:
022c8666ef58f0a6d4bef9dd72696199ebd5719f

tree:
a231cb06f15469ed99f0f8f4256b3ebc439467f2
```

Commit:

```text
Merge PR #95
Docs: reconcile TRAFFIC-05 and independent ranges production state
```

PR #95 is documentation-only relative to the runtime application implementation.

At the time of this R1 review:

```text
no newer repository commit was found after 022c8666...
```

Therefore this exact `main` is the current TASK development parent baseline for R1.

Before FINAL:

```text
fetch origin/main
re-pin exact TASK development parent SHA/tree
classify every intervening commit as docs-only or implementation-changing
```

If an implementation-changing commit touches relevant Traffic / Analytics / Admin
contracts:

```text
mandatory impact review before FINAL
```

Before implementation authorization the same re-pin/review must occur again.

## 2.2 Runtime / PERF compatibility reference baseline

Current runtime implementation / production compatibility reference:

```text
commit:
daf68e91fc759188980cf8741913e6b60a58eb62

tree:
b0e2f028eecf6aec9d86e35542c33e7105209335
```

This is the accepted `TRAFFIC-RANGE-01` runtime implementation.

Use this runtime implementation baseline for:

```text
production-behavior compatibility
existing-product PERF baseline
exact pre-TRAFFIC-06 payload semantics
```

Do not substitute docs-only `022c8666...` as though it were a different runtime
implementation.

## 2.3 Reviewed current sources

Current KB reviewed:

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

Relevant current implementation reviewed:

```text
app/analytics/historical_traffic.py
app/analytics/source_gateway.py
app/admin_web/query_service.py
app/admin_web/routes.py
app/admin_web/historical_traffic_serialization.py
app/admin_web/static/admin.js
```

Relevant current Traffic tests reviewed include:

```text
tests/analytics/test_historical_traffic_ap.py
tests/admin_web/test_traffic_independent_ranges.py
tests/admin_web/test_traffic_independent_ranges_frontend.py
```

---

# 3. Current production/runtime context

Current production Traffic surface:

```text
Current Network Throughput
Network Traffic History
Period Statistics
Peak Load
Traffic by AP
```

Current accepted historical architecture:

```text
independent 24h | 7d historical panel ranges

canonical products= projection

TrafficHistoricalRequestBroker

CaptivPortalTrafficCoordinator

max historical HTTP requests in flight from one Traffic page = 1

HISTORICAL_TRAFFIC_REQUEST_ADMISSION_GUARD_SECONDS = 10
```

Preserved capacity limits:

```text
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS = 10

Traffic browser request timeout = 20 seconds

Admin concurrency = unchanged
```

Current platform response limit:

```text
WEB_ADMIN_MAX_RESPONSE_BYTES = 1048576
```

Historical RANGE-01 timings are dated evidence only.

They do not automatically become TRAFFIC-06 thresholds.

---

# 4. Goal / product question

Product name:

```text
AP Traffic Share
```

Primary operator question:

```text
What share of accepted Site Network Traffic evidence
within this panel's applied historical range
was contributed by each AP?
```

Supported panel ranges:

```text
24h
7d
```

The panel has its own independent selected/applied range.

Per AP, v1 answers:

```text
Total Share
Download Share
Upload Share
```

It does not answer:

```text
current AP rate
AP Peak
AP historical chart
traffic volume in MB/GB
sample count share
client count share
```

---

# 5. Domain boundary / non-goals

Network Traffic remains:

```text
persisted AP/network throughput evidence
source rates in Mbps
```

It is not:

```text
WAN
Internet-only
Guest Traffic
Guest Session Traffic
SSID Traffic
billing traffic
```

TRAFFIC-06 does NOT introduce:

```text
new Traffic collector
new query-time Omada path
new Traffic DB
new table/schema
new index by default
cache
rollup
new retention
new acquisition cadence
second historical semantic owner
second browser scheduler
larger QueryDeadline
larger browser timeout
larger Admin concurrency
```

TRAFFIC-06 does not change accepted public meanings of:

```text
network_traffic_history.v1
network_traffic_period_statistics.v1
network_traffic_peak_load.v1
network_traffic_by_ap.v1
```

---

# 6. Dependencies

TRAFFIC-06 depends on accepted:

```text
TRAFFIC-00
Traffic Foundation

TRAFFIC-02-READ
Historical Traffic semantic foundation

TRAFFIC-02
Network Traffic History

TRAFFIC-02-PERF-01
requested-range-bounded source validation

TRAFFIC-03
canonical Period interval/time-weighted model

TRAFFIC-04
shared Historical semantic-owner pattern

TRAFFIC-05
AP population / AP accepted historical evidence

TRAFFIC-RANGE-01
products=
independent selected/applied panel ranges
broker/coordinator
single in-flight request
10-second admission guard
```

Source remains:

```text
persisted AP Observation facts
```

No query-time Omada dependency.

---

# 7. Permanent inherited Traffic invariants

Historical owner:

```text
HistoricalTrafficReadService
```

Current owner:

```text
CurrentTrafficReadService
```

Canonical historical source family is selected by existing Site semantics.

Share does not invent per-AP source fallback.

Permanent source rules remain:

```text
wired primary
lan fallback only through canonical existing Site selection
radio excluded from Site Network Traffic total
no AP-specific source-family mixing inside one accepted Site sample
```

Execution remains:

```text
requested-range bounded
read-only/query-only
same Admin QueryDeadline
fail-closed integrity
```

Browser does not become canonical analytics owner.

---

# 8. Semantic owner and one shared AP contribution primitive

## 8.1 Single semantic owner

AP Traffic Share is a new derived product owned by:

```text
HistoricalTrafficReadService
```

Do NOT create an independent:

```text
ApTrafficShareReadService
```

that owns a second historical interpretation.

`AnalyticsSourceGateway` may expose additional bounded internal facts, but remains
a source gateway.

## 8.2 One shared internal AP contribution / weighting primitive

R1 hard requirement:

```text
one shared internal AP contribution/weighting primitive
```

owned inside the existing Historical Traffic read/source implementation.

Conceptually:

```text
canonical accepted Site interval classification
        ↓
selected-source per-AP contribution materialization
        ↓
shared AP contribution values
        ├── TRAFFIC-05 Average / Coverage
        └── TRAFFIC-06 Share
```

Current TRAFFIC-05 already has internal evidence equivalent to:

```text
ap_site_accepted_interval_seconds
ap_accepted_interval_seconds
ap_weighted_download
ap_weighted_upload
```

and its Average uses the accepted weighted values rather than a separate public
formula.

TRAFFIC-06 MUST consume the exact same underlying weighted AP facts.

Forbidden:

```text
TRAFFIC-05 implements rate × elapsed one way

TRAFFIC-06 independently reimplements rate × elapsed
```

If extracting/refactoring a private shared primitive is required:

```text
allowed inside TASK scope
ONLY with exact TRAFFIC-05 backward-compatibility proof
```

The private class/function name is not frozen by this DRAFT.

Its semantic identity is frozen.

---

# 9. AP population / identity and range_presence_proven

## 9.1 Population method

Reuse exactly:

```text
current_union_historical_validated.v1
```

for one authorized canonical Site and selected Share range.

AP machine identity:

```text
canonical AP MAC
```

Display identity remains aligned with TRAFFIC-05:

```text
accepted current name
→ accepted historical name
→ MAC fallback
```

## 9.2 New canonical historical-presence distinction

R1 introduces an explicit semantic property:

```text
range_presence_proven
```

This is a canonical Share evidence property.

It answers:

```text
Does this population AP have at least one proven historical presence
inside the selected range on the canonical eligible Site sample basis?
```

### `range_presence_proven = true`

At least one eligible historical Site endpoint/sample in the selected range
contains this AP as accepted selected-source AP evidence.

Then:

```text
historical presence is proven
```

and structural absence of this AP from other otherwise trusted complete Site
samples may contribute zero for those other intervals.

### `range_presence_proven = false`

The AP enters the population only through current context and has no proven
historical presence in the selected range.

Then:

```text
evidence_status = insufficient_data

Download Share = null
Upload Share   = null
Total Share    = null
```

It MUST NOT be represented as historical `0%`.

## 9.3 Integrity invariant for no-presence AP

Permanent:

```text
range_presence_proven = false
→ AP historical integrated contribution D/U/T MUST be absent/null
```

If any nonzero or otherwise materialized historical contribution is attached to:

```text
range_presence_proven = false
```

that is a source/cross-product integrity contradiction.

Required:

```text
FAIL CLOSED
HistoricalTrafficSourceUnavailable / equivalent
```

No repair, clamping or inferred presence.

## 9.4 Historical-only / disappeared AP

A historical AP absent from current context remains population-visible.

If:

```text
range_presence_proven = true
```

it may have numeric Share.

Current disappearance does not erase historical contribution.

## 9.5 Replacement AP

Different MAC:

```text
different AP identity
```

even if display name matches.

## 9.6 Supported population cap

R1 retains:

```text
supported_max_ap_count = 12
```

per authorized canonical Site.

```text
population_count <= 12
→ return all population APs

population_count > 12
→ product status unsupported_population
→ returned_ap_count = 0
→ items = []
```

No:

```text
top-N
first 12
pagination
silent truncation
```

## 9.7 Population count zero

Explicit R1 rule:

```text
population_count = 0
→ product status = insufficient_data
→ items = []
```

No unsupported status and no invented zero-share population.

---

# 10. Exact Share metric identities

Recommended/frozen-for-R1 metric identity:

```text
metric_version =
network_traffic_ap_share.v1

share_method =
accepted_site_interval_integrated_ap_contribution_ratio.v1

temporal_method =
right_endpoint_sample_hold_time_weighted.v1

population_method =
current_union_historical_validated.v1

presence_method =
accepted_selected_source_historical_presence_in_range.v1

absence_method =
proven_population_member_absent_from_trusted_complete_site_sample_zero_contribution.v1

order_method =
total_share_desc_nulls_last_ap_mac_ascending.v1
```

Canonical API unit:

```text
fraction
```

where numeric:

```text
0.0 <= share_fraction <= 1.0
```

Presentation unit:

```text
percent
```

No MB/GB amount is exposed.

---

# 11. Reuse exact Period Statistics interval evidence

Share does not own a similar-but-separate Site interval classifier.

The canonical interval basis remains the existing
`HistoricalTrafficPeriodIntervalEvidence`.

For fixed:

```text
Site
range
evaluated_at
source snapshot
```

required semantic identity:

```text
Share Site interval classification
==
Period Statistics Site interval classification
```

R1 canonical source fields are the existing Period interval evidence:

```text
range_seconds
candidate_interval_count
accepted_interval_count
accepted_interval_seconds
interval_coverage_ratio
excluded_gap_interval_count
excluded_source_transition_interval_count
invalid_period_interval_count
accepted_peak_sample_count
leading_unweighted_seconds
trailing_unweighted_seconds
```

Share may expose only the subset required by its public DTO.

But internally it MUST consume/project the exact same evidence object/semantic
result.

Forbidden:

```text
Statistics accepted intervals = X

Share independently computes accepted intervals = Y
```

for the same fixed context.

The only allowed divergence is a separately detected AP decomposition integrity
contradiction, and that divergence does not produce a second partial interval set:

```text
it FAILS CLOSED
```

---

# 12. Formula and canonical interval population

## 12.1 Accepted Site intervals

Let canonical accepted Site samples be ordered by:

```text
t_i = cycle.finished_at
```

Candidate interval:

```text
I_i = (t_(i-1), t_i]
Δ_i = t_i - t_(i-1)
```

The exact accepted/excluded classification is inherited from Period Statistics.

Share does not reclassify it.

## 12.2 Site right-endpoint rates

For each already-accepted interval `i`:

```text
S_i^D = canonical Site Download Mbps
S_i^U = canonical Site Upload Mbps
S_i^T = S_i^D + S_i^U
```

## 12.3 AP right-endpoint contributions

For population AP `a` with:

```text
range_presence_proven = true
```

at accepted endpoint `i`:

### Case 1 — AP accepted selected-source evidence is present

Use exact shared AP contribution evidence:

```text
A_(a,i)^D
A_(a,i)^U
A_(a,i)^T = D + U
```

### Case 2 — structural absence in trusted complete Site sample

Use:

```text
A_(a,i)^D = 0
A_(a,i)^U = 0
A_(a,i)^T = 0
```

only under the strict structural-absence definition in Section 13.

### Case 3 — present AP row with selected-source evidence contradiction

Do NOT:

```text
zero-fill
skip AP
exclude only for Share
create Share-specific partial interval
```

Required:

```text
FAIL CLOSED
```

because the canonical Site interval was already accepted by the existing owner.

## 12.4 Current-only / no-presence AP

For:

```text
range_presence_proven = false
```

do not build a zero-filled AP_WEIGHT across the whole historical range.

Its historical Share state is:

```text
unproven
```

and public fractions are null.

This resolves the DRAFT contradiction:

```text
structural absence zero
≠
no proven historical presence
```

---

# 13. Strict structural absence definition

The phrase:

```text
AP row missing → zero
```

is forbidden as a generic rule.

Structural zero is allowed only when upstream accepted evidence proves ALL of:

```text
1. Site cycle/sample is canonical for the requested Site/range.

2. Cycle integrity is accepted.

3. Site selected-source sample is complete and already accepted
   by canonical Historical semantics.

4. The AP is a known Share/TRAFFIC-05 population member.

5. range_presence_proven = true for this AP.

6. The AP row is absent because this AP is not a member of that particular
   otherwise complete accepted Site sample.

7. There is no evidence that the row is missing due to corruption,
   incomplete acquisition, duplicate identity, incompatible selected source
   or integrity failure.
```

Only then:

```text
structural absence
→ zero contribution for this accepted interval
```

This rule models an AP that genuinely appears/disappears during a range.

It does NOT convert acquisition uncertainty into zero traffic.

---

# 14. Present-invalid evidence is an integrity contradiction

R1 explicitly removes any second AP interval classifier.

Canonical Site interval population is already owned upstream.

If:

```text
the Site endpoint/interval is canonical accepted
```

but an AP row that must participate in the selected Site source has:

```text
invalid selected-source rate
incompatible selected source
impossible weighted evidence
duplicate identity
corrupt AP contribution
```

then:

```text
cross-product integrity contradiction
```

Required behavior:

```text
FAIL CLOSED
HistoricalTrafficSourceUnavailable / equivalent safe unavailable path
```

Forbidden:

```text
Share-only interval exclusion
Share-only partial interval
zero-fill
silent AP skip
renormalization
```

Thus:

```text
Share Site interval basis remains exactly Period Statistics basis
```

or the whole Share projection is unavailable.

---

# 15. Integrated weights and conservation law

## 15.1 Directional Site weights

For `k ∈ {D,U}`:

```text
SITE_WEIGHT_k =
Σ accepted Site intervals ( S_i^k × Δ_i )
```

## 15.2 AP weights

For each AP with `range_presence_proven = true`:

```text
AP_WEIGHT_(a,k) =
Σ accepted Site intervals ( A_(a,i)^k × Δ_i )
```

Structural-zero intervals add `0 × Δ_i`.

AP with `range_presence_proven = false` has no numeric AP_WEIGHT.

## 15.3 Fundamental conservation law

Before Share division, for each direction `k`:

```text
SITE_WEIGHT_k
=
Σ AP_WEIGHT_(a,k)
```

over APs with proven historical presence, with structural zero contributions
already included.

Required numeric policy:

```text
math.isclose(
    math.fsum(ap_weights),
    site_weight,
    rel_tol=1e-9,
    abs_tol=1e-9
)
```

or an exactly equivalent frozen implementation.

Use numerically stable summation where applicable.

If conservation fails:

```text
FAIL CLOSED
```

Do NOT repair by normalizing APs to their own sum.

Forbidden:

```text
share_a = ap_weight_a / sum(ap_weights)
```

when canonical denominator is Site Network Traffic weight.

Canonical denominator remains:

```text
SITE_WEIGHT_k
```

The conservation law proves AP decomposition matches the Site denominator.

## 15.4 Derived sum-to-one invariant

Only after conservation passes and Site denominator is positive:

```text
SHARE_(a,k) =
AP_WEIGHT_(a,k) / SITE_WEIGHT_k
```

Then:

```text
Σ numeric AP Share_(a,k) = 1
```

within the same numerical tolerance.

Sum-to-one is a derived invariant.

It is not a normalization method.

---

# 16. Total Share is independently defined from total contribution

Explicit R1 contract:

```text
SITE_WEIGHT_T =
SITE_WEIGHT_D + SITE_WEIGHT_U
```

For AP `a`:

```text
AP_WEIGHT_(a,T) =
AP_WEIGHT_(a,D) + AP_WEIGHT_(a,U)
```

If:

```text
SITE_WEIGHT_T > 0
```

then:

```text
TOTAL_SHARE_a =
AP_WEIGHT_(a,T) / SITE_WEIGHT_T
```

Forbidden:

```text
download_share + upload_share

(download_share + upload_share) / 2

weighted combination of already computed percentages

any browser recomputation from percentages
```

Required counterexamples:

```text
Download denominator = 0
Upload denominator > 0
→ Total Share == Upload Share

Upload denominator = 0
Download denominator > 0
→ Total Share == Download Share

Download denominator = 0
Upload denominator = 0
→ Total denominator = 0
→ Total Share = null
```

Conservation applies independently to D, U and T.

---

# 17. AP presence seconds and TRAFFIC-05 identity

For fixed Site/range/evaluated_at/current context/source snapshot:

```text
APShare accepted_presence_seconds
==
TRAFFIC-05 ap_accepted_interval_seconds
```

for every AP with proven historical presence.

The current internal Site opportunity time remains:

```text
ap_site_accepted_interval_seconds
```

The Share pipeline MUST use the same underlying:

```text
ap_weighted_download
ap_weighted_upload
```

as TRAFFIC-05 Average weighting.

If TRAFFIC-05 Average is represented conceptually as:

```text
avg_D =
ap_weighted_download / ap_accepted_interval_seconds

avg_U =
ap_weighted_upload / ap_accepted_interval_seconds
```

then Share MUST use those exact existing weighted numerators:

```text
AP_WEIGHT_D = same ap_weighted_download
AP_WEIGHT_U = same ap_weighted_upload
```

not an independently equivalent recomputation.

This requirement is semantic even if implementation refactors the private field
transport.

---

# 18. Coverage and denominator evidence

## 18.1 Share interval evidence source

Share coverage derives from exact Period interval evidence.

Public Share DTO may project:

```text
range_seconds
candidate_interval_count
accepted_interval_count
accepted_interval_seconds
interval_coverage_ratio
excluded_gap_interval_count
excluded_source_transition_interval_count
invalid_period_interval_count
accepted_endpoint_sample_count
leading_unweighted_seconds
trailing_unweighted_seconds
```

Recommended mapping:

```text
accepted_endpoint_sample_count
=
existing accepted_peak_sample_count
```

if the public naming is made Share-neutral.

The internal source remains the existing Period field; no new count is calculated.

## 18.2 Directional denominator status

For D/U/T separately:

```text
positive
zero_traffic
insufficient_data
```

Exact rules:

```text
accepted_interval_count = 0
→ insufficient_data

accepted intervals exist AND SITE_WEIGHT_k = 0
→ zero_traffic

SITE_WEIGHT_k > 0
→ positive
```

No negative/non-finite Site weight is allowed.

Such evidence is an integrity failure.

---

# 19. Outer Historical status vs AP Traffic Share product status

These are separate concepts.

## 19.1 Outer Historical response status

Existing response-level fields remain:

```text
status
range
coverage
quality
```

The outer `status` continues to describe common Historical result semantics.

TRAFFIC-06 does not redefine it.

## 19.2 AP Traffic Share product status

Inside:

```text
ap_traffic_share.status
```

allowed:

```text
ok
partial
insufficient_data
unsupported_population
```

## 19.3 Exact product/directional cross-field matrix

### Product `insufficient_data`

Required:

```text
population_count may be 0 or supported nonzero

accepted_interval_count = 0

download denominator = insufficient_data
upload denominator   = insufficient_data
total denominator    = insufficient_data

all Share fractions = null
```

Population zero specifically requires:

```text
status = insufficient_data
items = []
```

### Product `unsupported_population`

Required:

```text
population_count > 12
returned_ap_count = 0
population_complete = false
items = []
```

No directional numeric Share.

### Product `ok` or `partial` + direction `zero_traffic`

Required:

```text
accepted intervals exist

SITE_WEIGHT_direction = 0

all Share fractions for that direction = null
```

### Product `ok` or `partial` + direction `positive`

For every AP:

```text
range_presence_proven = true
→ directional Share numeric, including valid 0.0

range_presence_proven = false
→ directional Share null
```

And:

```text
conservation PASS
numeric Share sum-to-one PASS
```

## 19.4 Product `ok`

Recommended exact criteria:

```text
supported population
population_count > 0
accepted intervals > 0
outer Historical status = ok
no Period interval exclusion
no AP decomposition integrity contradiction
```

Zero traffic in one/all directions does not by itself make product insufficient.

## 19.5 Product `partial`

Recommended:

```text
supported population
population_count > 0
accepted intervals > 0
trusted comparable evidence exists
outer Historical/Period evidence is incomplete
no integrity contradiction
```

Numeric Share on positive directions means:

```text
Share within accepted comparable evidence
```

No estimate is made for excluded intervals.

---

# 20. API projection design

## 20.1 Endpoint

No new endpoint.

Continue:

```text
GET /admin/api/v1/sites/<site_id>/traffic/history
```

## 20.2 New canonical product token

Add:

```text
apshare
```

Proposed canonical product order:

```text
history,statistics,peak,aps,apshare
```

Valid examples:

```text
?range=24h&products=apshare

?range=7d&products=apshare

?range=24h&products=aps,apshare

?range=24h&products=history,statistics,peak,aps,apshare
```

Reject:

```text
apshare,aps
duplicate apshare
unknown token
empty token
whitespace variant
duplicate products parameter
include + products
```

with:

```text
400 invalid_request
```

## 20.3 Legacy include

Do NOT add Share to:

```text
include=
```

Legacy include remains compatibility-only.

## 20.4 Product-scoped isolation

`products=apshare` MUST NOT execute/serialize unrelated product-specific:

```text
full History chart payload
Period Statistics public product
Peak public product
Traffic-by-AP series/Average/Peak/Now public product
```

Shared internal range, integrity, Period interval evidence, AP population and AP
contribution primitive may be reused.

## 20.5 Atomic requested projection vs feature exposure

Requested projection is atomic with respect to feature exposure.

Example:

```text
products=aps,apshare
```

and:

```text
WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED=false
```

Required:

```text
whole request → 404
```

after canonical security/Site/parent feature gates.

Forbidden:

```text
return aps
silently omit apshare
```

The same principle applies to any mixed projection containing a disabled product.

---

# 21. Serialization contract

When `apshare` is requested, result contains:

```text
ap_traffic_share
```

No Share-only AP history axis or AP history arrays.

Recommended product constants:

```text
metric_version =
network_traffic_ap_share.v1

unit =
fraction

display_unit =
percent

share_method =
accepted_site_interval_integrated_ap_contribution_ratio.v1

temporal_method =
right_endpoint_sample_hold_time_weighted.v1

presence_method =
accepted_selected_source_historical_presence_in_range.v1

absence_method =
proven_population_member_absent_from_trusted_complete_site_sample_zero_contribution.v1

population_method =
current_union_historical_validated.v1

order_method =
total_share_desc_nulls_last_ap_mac_ascending.v1
```

## 21.1 Population projection

```text
population_count
current_population_count
historical_population_count
supported_max_ap_count
returned_ap_count
population_complete
```

## 21.2 Coverage projection

Projection from existing Period interval evidence, including enough fields to
prove range/accepted-time meaning.

## 21.3 Denominator projection

```text
download_status
upload_status
total_status
```

No Site/AP internal weights are exposed as traffic amounts.

## 21.4 AP item

```text
ap_mac
display_name
display_name_source

range_presence_proven
evidence_status

accepted_presence_interval_count
accepted_presence_seconds

download_share_fraction
upload_share_fraction
total_share_fraction
```

## 21.5 Numeric validation

Every numeric fraction:

```text
finite
0 <= value <= 1
```

No NaN/Infinity.

Do not clamp malformed values.

Serializer must fail closed on contract contradiction.

## 21.6 Conservation validation

Before public Share serialization succeeds:

```text
D conservation PASS
U conservation PASS
T conservation PASS
```

for directions with comparable accepted evidence.

Do not use serializer normalization to force equality.

## 21.7 No-presence validation

Required:

```text
range_presence_proven = false
→ accepted_presence_interval_count = 0
→ accepted_presence_seconds = 0
→ D/U/T Share null
→ no numeric historical AP weight materialized
```

Conflict:

```text
FAIL CLOSED
```

## 21.8 Positive denominator validation

Direction status `positive`:

```text
proven-presence APs have numeric Share
no-presence APs have null Share
numeric fractions fsum to 1 within 1e-9
```

## 21.9 Zero/insufficient denominator validation

Direction status:

```text
zero_traffic
or
insufficient_data
```

requires all fractions for that direction:

```text
null
```

## 21.10 UI conversion

Server fractions are canonical and unrounded.

UI may multiply by `100` for display.

Recommended display:

```text
0 → 0.00%
0 < percent < 0.01 → <0.01%
otherwise → two decimal places
```

Visual rounding is not a semantic sum-to-100 contract.

---

# 22. Independent-range integration

AP Traffic Share is a new independent historical panel.

Own selector:

```text
24h | 7d
```

Own page-lifetime state:

```text
selected_range
applied_range
phase
last successful payload
error
intent generation
```

Initial:

```text
selected_range = 24h
applied_range = null until first valid success
```

Successful request:

```text
applied_range = exact validated server range
```

Failed new selection:

```text
selected_range = new intent
applied_range = previous successful range
previous payload remains visible
Share-local error shown
```

Reload:

```text
Share resets to 24h
```

No:

```text
localStorage
sessionStorage
cookie
URL range state
server range state
```

No return to one global historical range.

---

# 23. Broker / coordinator integration

Broker product key:

```text
apshare
```

`TrafficHistoricalRequestBroker` remains owner of:

```text
Share intent
selected/applied coordination
same-range coalescing
generation/supersession
response mapping
```

It remains NOT scheduler owner.

`CaptivPortalTrafficCoordinator` remains sole:

```text
scheduler
lifecycle owner
network request lifecycle owner
```

Permanent:

```text
max historical HTTP requests in flight per Traffic page = 1
```

## 23.1 Share range click

Example:

```text
Share 24h → 7d
```

queues:

```text
range=7d
products=apshare
```

unless broker safely coalesces other pending same-range products.

Share click does not force unrelated product recalculation.

## 23.2 AP + Share same-range coalescing

May coalesce:

```text
products=aps,apshare
```

because both reuse common AP population/contribution facts.

Coalescing is an optimization.

It is not a semantic requirement.

## 23.3 Initial all-24h grouping

After Share activation, a fresh page may attempt:

```text
products=history,statistics,peak,aps,apshare
```

ONLY if mandatory `ALL24` PERF proves this grouping safe.

If `ALL24` fails accepted gate:

```text
do NOT increase deadline

architectural fallback =
broker dispatch grouping / product separation
within existing one-in-flight scheduler
```

Possible safe execution remains sequential under the same coordinator/admission
architecture.

The product contract does not require all five products to share one HTTP request.

## 23.4 Global Refresh

Global Refresh groups products by their own selected range and allowed/safe
dispatch grouping.

Historical requests remain sequential.

## 23.5 Supersession

Latest Share intent wins.

Stale generation/range response cannot replace a newer Share selection.

No Share-owned timer/fetch/AbortController.

---

# 24. Admission guard

Inherit unchanged:

```text
HISTORICAL_TRAFFIC_REQUEST_ADMISSION_GUARD_SECONDS = 10
```

Canonical eligibility:

```text
next_dispatch >= max(
    previous_request_completion,
    previous_dispatch + 10s,
    coordinator Retry-After / backoff / lifecycle eligibility
)
```

Share cannot bypass guard by:

```text
range click
manual retry
Global Refresh
HTTP 503
same-range coalescing
grouping fallback
```

State:

```text
waiting
= queued / admission blocked

loading
= actual historical request containing Share is in flight
```

Selectors remain interactive while waiting.

Pending Share intent collapses to latest before dispatch.

---

# 25. UI product contract

Panel:

```text
AP Traffic Share
```

Explain substantially:

```text
Share of accepted Site Network Traffic evidence
within this panel's applied range.
```

Do not label:

```text
Internet Share
WAN Share
Guest Share
Volume Share
```

Show every supported population AP.

No top-N.

Per AP:

```text
AP label
Total Share
Download Share
Upload Share
evidence qualifier
```

Primary display metric:

```text
Total Share
```

Recommended order:

```text
numeric Total Share descending
null Total Share last
tie → AP MAC ascending
```

If every Total Share is null:

```text
AP MAC ascending
```

## 25.1 One AP

With:

```text
range_presence_proven=true
positive Total denominator
```

Total Share:

```text
100%
```

Directional 100% only if that direction denominator is positive.

## 25.2 Current-only AP

Show AP because population is shared with TRAFFIC-05.

But:

```text
range_presence_proven=false
evidence_status=insufficient_data
shares=—
```

Do not display `0%`.

## 25.3 Proven AP with true zero contribution

If historical presence is proven and AP contribution is valid zero while the Site
denominator is positive:

```text
Share = 0.00%
```

This is a real zero.

## 25.4 Zero Site Traffic

Accepted evidence exists but denominator status `zero_traffic`:

```text
No accepted Network Traffic was observed in this range.
```

No invented percentage distribution.

## 25.5 Partial

Numeric Share may remain visible on positive denominators with:

```text
Partial
```

meaning normalization is over accepted comparable evidence only.

## 25.6 Insufficient

No accepted intervals:

```text
No sufficient comparable Network Traffic evidence for this range.
```

No percentages.

## 25.7 Unsupported

Population >12:

```text
AP Traffic Share is not available for this Site/range population.
```

No first-12 subset.

Waiting/loading/error preserves prior successful payload/applied range according
to RANGE-01.

Final visual layout remains outside this semantic DRAFT.

---

# 26. Security / Site isolation

TRAFFIC-06 is Site-scoped.

Canonical authorized Site is the data-isolation boundary.

Site B may not influence Site A:

```text
population
range_presence_proven
AP weights
Site denominator
Share
unsupported decision
coverage
response metadata
telemetry
```

Site B APs must not push Site A over the 12-AP cap.

Frontend filtering is not security.

Forbidden:

```text
browser → SQLite
browser → Omada
Admin request → Omada
```

Future RBAC/Tenant policy may alter authorization without changing Share metric
semantics.

---

# 27. Observability

Reuse existing Admin Traffic telemetry.

Recommended fields when Share requested:

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

share_download_denominator_status
share_upload_denominator_status
share_total_denominator_status

share_no_presence_ap_count

duration_ms
response_bytes
failure_reason
query_deadline
share_unsupported_population
share_integrity_failure
```

Do not log:

```text
raw AP weights
per-interval AP contribution arrays
all Share fractions
SQL text
DB path
cross-Site population details
```

Conservation failure should be classifiable as product/source integrity failure
without leaking bad raw data.

---

# 28. Feature flag and atomic feature behavior

Recommended:

```text
WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED=false
```

Repository default:

```text
false
```

Dependencies:

```text
WEB_ADMIN_ENABLED=true
WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED=true
```

Do NOT require:

```text
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED
WEB_ADMIN_TRAFFIC_PEAK_ENABLED
```

Share is its own public projection over shared internal semantics.

The flag controls product exposure only.

It does not start/stop:

```text
Observation
HistoricalTrafficReadService
CurrentTrafficReadService
```

## 28.1 Feature OFF

Required:

```text
Share panel absent

broker queues no apshare intent

products=apshare → 404

products=aps,apshare → whole request 404

no partial mixed projection
```

after normal canonical security/Site/parent gates.

## 28.2 Feature-OFF backward compatibility

When:

```text
WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED=false
```

existing Traffic behavior must be semantically identical to pre-TASK runtime for:

```text
products=history
products=statistics
products=peak
products=aps
existing canonical combinations
legacy include=
```

No Share calculation may execute.

No response contract changes may leak into existing products.

Explicit feature-off regression evidence is mandatory.

---

# 29. Performance contract

TRAFFIC-06 has mandatory pre-publication PERF.

No publication while any mandatory PERF gate is FAIL/PENDING.

## 29.1 Baseline terminology

### TASK development parent

At R1:

```text
022c8666ef58f0a6d4bef9dd72696199ebd5719f
tree a231cb06f15469ed99f0f8f4256b3ebc439467f2
```

### PERF/runtime compatibility reference

```text
daf68e91fc759188980cf8741913e6b60a58eb62
tree b0e2f028eecf6aec9d86e35542c33e7105209335
```

Before FINAL and before PERF:

```text
re-fetch main/runtime state
classify drift
pin exact baseline and exact candidate
```

## 29.2 Controlled environment

Baseline/candidate comparisons use:

```text
same production-compatible Linux machine/environment
same immutable production-size Observation snapshot
same snapshot SHA/bytes
same fixed evaluated_at_utc
same [from_utc,to_utc)
same QueryDeadline=10s
same API timing boundary
same warm-up policy
```

Snapshot must be immutable/read-only for acceptance.

## 29.3 Runs and percentile algorithm

At least:

```text
10 measured runs per mandatory variant where timing gate applies
```

Warmups:

```text
unmeasured
documented
equal for comparable variants
```

Percentiles:

```text
sort values ascending

rank = (N - 1) * p

lower = floor(rank)
upper = ceil(rank)

if lower == upper:
    percentile = values[lower]
else:
    percentile =
        values[lower]
        + (rank-lower)
          * (values[upper]-values[lower])
```

`max` is literal measured maximum.

## 29.4 Mandatory performance matrix

```text
SH24
products=apshare
range=24h

SH7
products=apshare
range=7d

BA24
baseline products=aps
range=24h

BA7
baseline products=aps
range=7d

CA24
candidate products=aps
range=24h

CA7
candidate products=aps
range=7d

AS24
candidate products=aps,apshare
range=24h

AS7
candidate products=aps,apshare
range=7d

E24-B
baseline products=history,statistics,peak,aps
range=24h

E24-C
candidate products=history,statistics,peak,aps
range=24h

ALL24
candidate products=history,statistics,peak,aps,apshare
range=24h
```

No mandatory legacy all-products 7d combined gate.

RANGE-01 intentionally removed the need for that shared 7d pattern.

## 29.5 Share-only hard time gates

For SH24 and SH7:

```text
p95 <= 8.0s

max <= 9.0s

query_deadline = 0

source_integrity = 0

unexpected_5xx = 0
```

8s/9s are derived from current fixed 10s deadline headroom, not copied from old
A7 measurements.

## 29.6 Share-only hard byte gate

Share-only contains at most 12 aggregate AP rows and no historical arrays.

Hard:

```text
SH24 response_bytes <= 65536

SH7 response_bytes  <= 65536
```

That is:

```text
64 KiB
```

Accidental serialization of:

```text
History buckets
AP series
raw per-interval contribution arrays
full-range support material
```

must fail this gate.

No platform response limit increase is an accepted fix.

## 29.7 AP-only backward compatibility

Compare:

```text
BA24 ↔ CA24
BA7  ↔ CA7
```

Semantic identity is required excluding only documented request/transport metadata.

Relative timing:

```text
Δp50 <= max(0.50s, 20% baseline p50)

Δp95 <= max(0.75s, 25% baseline p95)

Δmax <= max(1.00s, 25% baseline max)
```

Candidate AP-only also requires:

```text
p95 <= 8.0s
max <= 9.0s
query_deadline = 0
source_integrity = 0
unexpected_5xx = 0
```

## 29.8 AP + Share coalesced

AS24/AS7 compare against candidate AP-only CA24/CA7.

Relative incremental Share overhead:

```text
Δp50 <= max(0.50s, 20% CA.p50)

Δp95 <= max(0.75s, 25% CA.p95)

Δmax <= max(1.00s, 25% CA.max)
```

Hard:

```text
p95 <= 8.0s
max <= 9.0s
query_deadline = 0
source_integrity = 0
unexpected_5xx = 0
```

Byte gate:

```text
AS24 response_bytes <= CA24 response_bytes + 65536

AS7 response_bytes  <= CA7 response_bytes + 65536

AND
response_bytes < WEB_ADMIN_MAX_RESPONSE_BYTES
```

## 29.9 Existing four-product 24h backward compatibility

This is mandatory R1 hardening.

Baseline:

```text
E24-B =
range=24h
products=history,statistics,peak,aps
```

Candidate:

```text
E24-C =
range=24h
products=history,statistics,peak,aps
```

Require semantic identity excluding documented request/transport metadata.

Relative timing:

```text
Δp50 <= max(0.50s, 20% E24-B.p50)

Δp95 <= max(0.75s, 25% E24-B.p95)

Δmax <= max(1.00s, 25% E24-B.max)
```

Candidate hard:

```text
p95 <= 8.0s
max <= 9.0s
query_deadline = 0
source_integrity = 0
unexpected_5xx = 0
```

This proves shared Historical/AP refactoring did not regress the existing initial
production 24h product path.

## 29.10 ALL24 activated grouping proof

Candidate:

```text
ALL24 =
range=24h
products=history,statistics,peak,aps,apshare
```

Mandatory hard:

```text
p95 <= 8.0s
max <= 9.0s
query_deadline = 0
source_integrity = 0
unexpected_5xx = 0
```

Byte gate:

```text
ALL24 response_bytes
<= E24-C response_bytes + 65536

AND
ALL24 response_bytes < WEB_ADMIN_MAX_RESPONSE_BYTES
```

If ALL24 fails while individual products pass:

```text
do NOT increase deadline
```

Required architecture fallback:

```text
broker dispatch grouping/product separation
under existing one-in-flight scheduler and admission guard
```

Coalescing is optimization, not product semantics.

## 29.11 Query plan / work-shape proof

For materially changed/new Share queries capture safe plan/profile evidence.

Prove:

```text
requested-range bounded

same read-only source snapshot

same QueryDeadline

no all-history validation

no second historical semantic scan owner

no N × full-history AP explosion

population cap discovered before unnecessary over-bound heavy materialization

shared AP contribution primitive reused
```

No new index is authorized by R1.

## 29.12 PERF failure policy

If any mandatory variant fails:

```text
candidate NOT ACCEPTED
publication NOT AUTHORIZED
```

Do not "fix" by:

```text
raising QueryDeadline
raising browser timeout
raising Admin concurrency
adding index without architecture review
adding cache/rollup without architecture review
weakening integrity
silent payload truncation
```

Return profile/query-plan evidence to architecture.

---

# 30. Testing / acceptance contract

Testing governance remains:

```text
Coder:
focused/minimal TASK/module development tests only

Owner + Tech Lead / Central Lab:
targeted cross-surface regression
full official gate
PERF
official PASS/FAIL
```

Exact test set must be re-reviewed after implementation.

## 30.1 Core semantic tests

Mandatory:

```text
exact metric/method identifiers

same Period interval evidence source

same accepted interval counts/seconds as Period Statistics

one shared AP weighting primitive

range_presence_proven true/false semantics

structural absence strict qualification

present-invalid contradiction fail-closed

D conservation

U conservation

T conservation

sum-to-one derived from conservation

no AP-weight renormalization

Total formula exact

valid numeric zero

zero Site denominator

no accepted intervals

partial evidence

unsupported population

Site isolation
```

## 30.2 Required semantic counterexample: sample count

Construct AP-A:

```text
many low-rate accepted samples
```

and AP-B:

```text
fewer samples but much larger time-integrated contribution
```

Expected:

```text
Share follows rate × elapsed contribution
not sample count
```

## 30.3 Required counterexample: bucket average

Construct unequal accepted interval lengths such that:

```text
bucket-average based Share
!=
integrated accepted contribution Share
```

Expected:

```text
canonical Share follows exact shared weighted evidence
```

## 30.4 Required Total-share counterexample

Use strongly different D/U distribution.

Prove Total Share is not:

```text
D Share + U Share
(D Share + U Share)/2
```

Required directional-zero fixtures:

```text
D denominator=0, U>0
→ Total Share == U Share

U denominator=0, D>0
→ Total Share == D Share

D=0 and U=0
→ Total Share null
```

## 30.5 Current-only counterexample

AP exists only in current population.

Expected:

```text
range_presence_proven=false
accepted_presence_seconds=0
shares=null
not 0
```

Injected numeric historical contribution with false presence:

```text
FAIL CLOSED
```

## 30.6 Proven AP + structural absence counterexample

AP has accepted historical presence in only part of range and is structurally
absent from other trusted complete Site samples.

Expected:

```text
range_presence_proven=true
absence intervals contribute zero
Share remains numeric when Site denominator positive
```

## 30.7 Present-invalid contradiction

Canonical Site endpoint is accepted, but injected AP selected-source evidence is
invalid.

Expected:

```text
FAIL CLOSED
```

Not:

```text
partial
zero-fill
Share-specific interval exclusion
```

## 30.8 Conservation violation

Inject AP weighted evidence where:

```text
Σ AP_WEIGHT != SITE_WEIGHT
```

Expected:

```text
FAIL CLOSED
```

Explicitly prove implementation does not renormalize AP weights.

## 30.9 TRAFFIC-05 / TRAFFIC-06 fixed-context identity tests

For fixed:

```text
Site
range
evaluated_at
current context
source snapshot
```

prove:

```text
population_count identical
MAC set identical
display_name identical
display_name_source identical
supported_max_ap_count identical
unsupported decision identical
```

For proven AP:

```text
APShare accepted_presence_seconds
==
TRAFFIC-05 ap_accepted_interval_seconds
```

And Share D/U integrated contribution uses the exact same underlying weighted AP
facts as TRAFFIC-05 Average.

## 30.10 Period interval identity tests

For the same fixed context:

```text
Share candidate_interval_count
==
Period Statistics candidate_interval_count

Share accepted_interval_count
==
Period Statistics accepted_interval_count

Share accepted_interval_seconds
==
Period Statistics accepted_interval_seconds

Share exclusion counts
==
Period Statistics exclusion counts

Share leading/trailing unweighted evidence
==
Period Statistics evidence
```

No separate Share interval classifier.

## 30.11 Population tests

Mandatory:

```text
population=0 → insufficient_data/items=[]

current-only AP

historical-only AP

disappeared AP

replacement AP / same display name different MAC

1 AP

2 AP

12 AP supported

13 AP unsupported

no truncation

deterministic ordering

Site-local cap
```

## 30.12 API tests

Mandatory:

```text
feature flag default false

feature dependencies

auth before product projection

Site authorization

products=apshare

products=aps,apshare

all-five canonical order

out-of-order apshare rejected

duplicate apshare rejected

malformed/unknown rejected

include + products rejected

legacy include unchanged

Share flag false:
  apshare →404
  aps,apshare → whole request 404

mixed requested projection atomic

Share-only projection isolation

requested_products exact

serializer fail-closed
```

## 30.13 Feature-OFF regressions

With Share flag false, prove exact semantics unchanged for:

```text
history
statistics
peak
aps
existing canonical product combinations
legacy include=
```

Also prove:

```text
Share panel absent
broker contains no apshare intent
no Share calculation path runs
```

## 30.14 Serializer integrity tests

Mandatory:

```text
fractions finite

0<=fraction<=1

false presence → no numeric Share

false presence + numeric AP contribution → fail closed

positive denominator:
  conservation PASS
  numeric fractions sum 1 within 1e-9

zero denominator:
  all direction fractions null

insufficient denominator:
  all direction fractions null

population zero matrix

unsupported matrix

Total formula exact

cross-field corruption fail closed
```

## 30.15 Frontend tests

Mandatory:

```text
Share independent 24h/7d selector

default 24h

selected/applied separate

waiting != loading

prior successful payload preserved on failure

latest Share intent wins

stale response rejected

same-range aps+apshare coalescing when safe

ALL24 coalescing only as optional safe grouping

fallback grouping possible without second scheduler

Global Refresh grouping

10-second guard

manual retry cannot bypass

503 cannot bypass

Retry-After preserved

max in-flight=1

no Share-owned scheduler

no Share-owned timer

no Share-owned AbortController

no direct independent fetch path

reload resets 24h

no storage persistence

all supported APs shown

no top-N

current-only displays null

true zero displays 0.00%

partial / insufficient / unsupported / zero-traffic UI
```

## 30.16 Security tests

Fixture:

```text
Site A
Site B
shared source DB
```

Authorized Site A Share must exclude Site B from:

```text
population
presence
weights
denominator
Share
unsupported decision
coverage
telemetry
```

Site B must not push Site A over 12.

## 30.17 PERF tests

All Section 29 mandatory variants/gates are release acceptance requirements.

---

# 31. Backward compatibility

TRAFFIC-06 code existing but Share not requested MUST preserve existing product
semantics.

For fixed context:

```text
products=history
unchanged

products=statistics
unchanged

products=peak
unchanged

products=aps
unchanged

products=history,statistics,peak,aps
unchanged

legacy include=
unchanged
```

TRAFFIC-05 remains:

```text
network_traffic_by_ap.v1
```

with unchanged:

```text
population
AP MAC identity
series
Average
Peak
Coverage
current evidence
12-AP cap
```

No Share feature may change Current Network Throughput.

---

# 32. Rollout / dormant activation

Canonical flow:

```text
implementation candidate
→ focused TASK evidence
→ Owner + Tech Lead targeted regression
→ official Central Lab full gate
→ mandatory Linux production-compatible PERF matrix
→ all mandatory gates PASS
→ accepted candidate
→ Git publication
→ Owner-authorized merge
→ production deploy FROM GIT with Share OFF
→ dormant acceptance
→ separate Owner activation
→ production browser/product acceptance
```

Dormant:

```text
WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED=false
```

Must prove:

```text
existing Traffic healthy
existing products semantically unchanged
no Share panel
no apshare request
no Share calculation
no deadline/capacity regression
```

Separate activation:

```text
WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED=true
```

Production acceptance should verify:

```text
Share panel visible
24h PASS
7d PASS
independent selected/applied range
current-only null semantics
true-zero semantics
D/U/T Share
conservation/sum behavior on observed data where applicable
all supported APs
partial/zero/insufficient/unsupported states
Traffic by AP unchanged
single-in-flight/guard behavior preserved
```

---

# 33. Rollback

Primary rollback:

```text
WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED=false
```

Expected:

```text
Share panel absent
no apshare intent
all existing Traffic products remain
independent ranges remain
```

No DB/schema/data rollback.

No Observation history deletion.

If code rollback is required:

```text
use verified Git artifact under current deployment governance
```

---

# 34. Explicit architectural decision boundary / STOP conditions

R1 finds no proven need for:

```text
new DB
new schema
new index
new cache
new rollup
new collector
new Omada request
new deadline
new browser timeout
new Admin concurrency
```

None is authorized.

STOP and return to Owner / Tech Lead if implementation requires:

```text
a second Share interval classifier

independent AP rate×elapsed weighting implementation

AP weight renormalization against sum(AP) instead of Site denominator

zero-fill for current-only/no-presence AP

zero-fill for corrupt/present-invalid AP evidence

different AP population from TRAFFIC-05

different Site isolation semantics

different >12 truncation behavior

new endpoint as independent historical path

new collector/DB/schema/index/cache/rollup

QueryDeadline increase

browser timeout increase

Admin concurrency increase

ALL24 safety achieved only by larger deadline rather than broker grouping

material implementation drift from pinned baseline without impact review
```

If any of these is needed:

```text
EXPLICIT ARCHITECTURAL DECISION REQUIRED
```

with root cause, evidence, alternatives, migration/rollback impact.

---

# 35. Acceptance criteria

TRAFFIC-06 can be accepted only if approved FINAL gates PASS on the exact candidate.

Minimum:

```text
1. Share is time-integrated accepted contribution ratio.

2. sample count does not enter numerator/denominator.

3. Share reuses exact Period Statistics Site interval classification.

4. Share uses one shared AP weighting primitive with TRAFFIC-05.

5. range_presence_proven resolves current-only null vs structural zero.

6. false historical presence cannot have historical numeric contribution.

7. structural absence is zero only inside trusted complete accepted Site sample
   for an AP whose range presence is already proven.

8. present-invalid AP evidence on an accepted Site endpoint is fail-closed,
   not Share-specific partial/exclusion.

9. canonical denominator is SITE_WEIGHT.

10. D/U/T conservation passes before division.

11. no AP-weight renormalization.

12. Total weight/share uses D+U weights, not D/U percentages.

13. positive denominator numeric shares derive sum-to-one.

14. zero denominator produces null shares.

15. product insufficient_data produces denominator insufficient_data and all null.

16. population zero → insufficient_data/items=[].

17. current-only AP → null Share, not 0%.

18. proven AP can have true numeric 0%.

19. TRAFFIC-05 and Share population/MAC/name/cap/unsupported identity PASS.

20. accepted_presence_seconds identity with TRAFFIC-05 AP accepted interval seconds PASS.

21. Site isolation PASS.

22. canonical products order includes apshare last.

23. legacy include unchanged.

24. mixed requested projection with disabled Share is atomically 404.

25. feature OFF is semantically backward compatible.

26. Share panel owns independent selected/applied range.

27. broker/coordinator ownership unchanged.

28. max historical in-flight remains 1.

29. 10-second admission guard unchanged.

30. SH24/SH7 PERF PASS.

31. BA↔CA AP-only compatibility PASS.

32. AS24/AS7 coalesced PERF PASS.

33. E24-B↔E24-C existing-four-product semantic/PERF compatibility PASS.

34. ALL24 PASS if used as initial coalescing.

35. If ALL24 fails, broker grouping fallback is used instead of deadline increase.

36. SH payload <=64KiB.

37. AS payload <= candidate AP-only +64KiB and below platform max.

38. ALL24 payload <= candidate existing-four +64KiB and below platform max.

39. QueryDeadline/browser timeout/Admin concurrency unchanged.

40. no new acquisition/storage infrastructure without separate architecture decision.

41. repository default feature flag is OFF.

42. dormant deploy and activation remain separate Owner-controlled steps.
```

Any mandatory failure:

```text
candidate NOT ACCEPTED

normal publication NOT AUTHORIZED
```

---

# 36. Owner / Tech Lead review decisions incorporated

| Review item | R1 outcome | R1 location |
|---|---|---|
| Q1 — time-integrated accepted contribution ratio | **ACCEPT WITH HARDENING** — formula retained; Site conservation frozen before Share division | §§10, 12, 15 |
| Q2 — structural absence | **ACCEPT WITH CORRECTION** — `range_presence_proven`; structural zero only after proven historical presence and trusted complete Site sample | §§9, 12–14 |
| Q3 — population | **ACCEPT** — `current_union_historical_validated.v1`, 12 AP per Site, no truncation | §9 |
| Q4 — zero Traffic | **ACCEPT** — no top-level `no_traffic`; denominator `zero_traffic`; fractions null | §§18–19 |
| Q5 — API | **ACCEPT** — `products=apshare`, canonical last token, no legacy include extension; mixed disabled projection atomic 404 | §20 |
| Q6 — ordering | **ACCEPT** — Total Share desc, null last, MAC tie | §§10, 25 |
| Q7 — all AP | **ACCEPT** — all supported APs, no top-N/pagination/truncation | §§9, 25 |
| Q8 — feature flag | **ACCEPT** — `WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED=false`; parent dependencies only; feature-OFF regressions explicit | §28 |
| Q9 — PERF | **REVISED / INCORPORATED** — SH, BA/CA, AS, E24-B/C, ALL24; 64KiB incremental byte gates; separate TASK/runtime baselines | §29 |

Additional R1 hardening incorporated from review:

```text
one shared internal AP contribution primitive

exact TRAFFIC-05 weighted evidence identity

exact Period interval evidence identity

present-invalid accepted-endpoint contradiction → fail closed

D/U/T conservation law

Total Share independent formula

population_count=0 matrix

outer Historical status vs product status separation

feature-off semantic regression gate

initial coalescing is optional optimization

broker grouping is fallback if ALL24 is unsafe
```

---

# 37. Final R1 state

```text
TASK-TRAFFIC-06:
AP Traffic Share

DOCUMENT:
DRAFT R1

OWNER / TECH LEAD R1 CORRECTIONS:
INCORPORATED

IMPLEMENTATION AUTHORIZATION:
NOT GRANTED

CODER AUTHORIZATION:
NOT GRANTED

GIT PUBLICATION:
NOT AUTHORIZED

MERGE:
NOT AUTHORIZED

DEPLOY:
NOT AUTHORIZED

ACTIVATION:
NOT AUTHORIZED
```

Before any move to FINAL:

```text
re-fetch origin/main

re-pin TASK development parent SHA/tree

verify runtime/PERF compatibility reference

impact-review implementation-changing drift

re-review this R1 for unresolved contradictions
```

STATUS: DRAFT R1 — AWAITING OWNER / TECH LEAD REVIEW
