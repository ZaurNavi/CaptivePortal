# TASK-TRAFFIC-06 — AP Traffic Share — FINAL CANDIDATE

**Project:** CaptivPortal  
**Area:** Admin Console → Traffic  
**Roadmap item:** `TRAFFIC-06 — AP Traffic Share`  
**Document state:** `FINAL CANDIDATE — AWAITING OWNER / TECH LEAD APPROVAL`  
**Prepared:** 2026-09-01  
**Owner / Tech Lead review source:** DRAFT R1 final-hardening corrections incorporated 2026-09-01  
**Implementation authorization:** `NOT GRANTED`  
**Code / patch / PR / merge / deploy / activation:** `NOT AUTHORIZED`

---

# 1. Status

```text
TASK:
TRAFFIC-06 — AP Traffic Share

STATUS:
FINAL CANDIDATE

ROADMAP POSITION:
NEXT / NOT IMPLEMENTED

ARCHITECTURE:
OWNER / TECH LEAD R1 DIRECTION ACCEPTED
FINAL HARDENING INCORPORATED

IMPLEMENTATION:
NOT AUTHORIZED

FINAL APPROVAL:
PENDING OWNER / TECH LEAD
```

This is the complete architecture FINAL CANDIDATE.

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

Canonical product intent:

```text
share of accepted Network Traffic evidence within selected range

sample count != traffic share
```

# 2. Baseline model: TASK development parent vs runtime/PERF reference

Two baselines are intentionally distinct.

## 2.1 TASK development parent baseline

`origin/main` was re-fetched immediately before this FINAL CANDIDATE.

Exact current Git / Knowledge Base main:

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

PR #95 is documentation-only relative to the accepted runtime implementation.

Re-fetch result:

```text
newer repository commits after 022c8666...:
NONE

implementation drift:
NONE

TASK rebind required:
NO
```

Therefore:

```text
TASK development parent baseline =
022c8666ef58f0a6d4bef9dd72696199ebd5719f
tree a231cb06f15469ed99f0f8f4256b3ebc439467f2
```

Before any separate implementation authorization:

```text
re-fetch origin/main again
re-pin exact SHA/tree
impact-review any implementation-changing drift
```

Docs-only drift may be documented without changing runtime semantics.

Implementation-changing drift touching relevant Traffic / Analytics / Admin
contracts requires architecture impact review before coding authorization.

## 2.2 Runtime / PERF compatibility reference baseline

Accepted runtime implementation / production compatibility reference:

```text
commit:
daf68e91fc759188980cf8741913e6b60a58eb62

tree:
b0e2f028eecf6aec9d86e35542c33e7105209335
```

This is accepted `TRAFFIC-RANGE-01`.

Use it for:

```text
pre-TRAFFIC-06 runtime compatibility
existing-product semantic comparison
existing-product PERF baseline
```

Do NOT use docs-only `022c8666...` as though it were a different runtime
application implementation.

## 2.3 Current TRAFFIC-05 current-context behavior verified

Current `AdminQueryService.historical_traffic_history(...)` behavior was checked.

When AP Traffic is requested, it attempts `CurrentTrafficReadService`.

If current traffic source/validation fails, current TRAFFIC-05 orchestration
currently falls back internally to:

```text
current_snapshot = None
current_population_count = 0
current_items = ()
current_cycle_id = None
```

and continues the historical AP path.

For TRAFFIC-05 this is an existing technical fallback.

FINAL CANDIDATE rule:

```text
DO NOT reinterpret that fallback zero
as proof that current AP population is empty
for the new TRAFFIC-06 Share semantic.
```

TRAFFIC-06 introduces explicit current-context provenance while leaving
TRAFFIC-05 public semantics unchanged unless a separate task authorizes otherwise.

## 2.4 Reviewed current sources

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

Relevant current tests reviewed include:

```text
tests/analytics/test_historical_traffic_ap.py
tests/admin_web/test_traffic_independent_ranges.py
tests/admin_web/test_traffic_independent_ranges_frontend.py
```

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

# 9. AP population / identity, range_presence_proven and current context

## 9.1 Intended population method

The canonical intended full population method remains:

```text
current_union_historical_validated.v1
```

for one authorized canonical Site and the selected Share range.

AP machine identity:

```text
canonical AP MAC
```

Display identity:

```text
accepted current name
→ accepted historical name
→ MAC fallback
```

## 9.2 Historical contribution vs current population enrichment

TRAFFIC-06 separates two concepts:

```text
historical contribution semantics
```

and:

```text
current population enrichment
```

Historical Share numerator/denominator comes only from persisted historical
Network Traffic evidence.

Current AP context is used only to complete:

```text
current ∪ historical population identity
```

and to expose current-only APs with unproven historical presence.

Current AP rates MUST NEVER enter Share numerator or denominator.

## 9.3 Canonical current population status

Freeze:

```text
current_population_status =
available | unavailable
```

`available` means current population evidence was safely resolved and validated.

`unavailable` means no safe current population snapshot can be established
without asserting corruption.

It does NOT mean:

```text
current AP population = 0
```

## 9.4 Canonical current population count

When:

```text
current_population_status = available
```

required:

```text
current_population_count = integer >= 0
```

A numeric zero is a proved empty current population.

When:

```text
current_population_status = unavailable
```

required:

```text
current_population_count = null
```

Never serialize/log a fabricated `0`.

Permanent:

```text
current context unavailable
!=
current population empty
```

## 9.5 `population_count` under available vs unavailable current context

When current context is available:

```text
population_count =
count(current accepted population ∪ validated historical population)
```

and the full union is known.

When current context is unavailable:

```text
population_count =
historical_population_count
```

meaning:

```text
count of the known validated historical population returned by this partial
historical Share projection
```

This MUST be interpreted together with:

```text
population_complete = false
current_population_status = unavailable
current_population_count = null
```

It MUST NOT be interpreted as the proven full current∪historical Site population.

## 9.6 Population completeness

For a supported population:

```text
current_population_status = available
→ population_complete = true
```

provided normal population integrity checks pass.

```text
current_population_status = unavailable
→ population_complete = false
```

because unseen current-only APs cannot be ruled out.

For unsupported population:

```text
population_complete = false
```

## 9.7 `range_presence_proven`

Canonical Share evidence property:

```text
range_presence_proven
```

It answers:

```text
Does this population AP have at least one proven historical presence
inside the selected range on the canonical eligible Site sample basis?
```

### Proven historical presence

If at least one eligible historical Site endpoint/sample contains the AP as
accepted selected-source AP evidence:

```text
range_presence_proven = true
```

Structural absence from other trusted complete Site samples may then contribute
zero under Section 13.

### Unproven historical presence

If the AP is known only from current context and has no proven historical
presence in the selected range:

```text
range_presence_proven = false
evidence_status = insufficient_data

Download Share = null
Upload Share = null
Total Share = null
```

Do NOT display historical `0%`.

## 9.8 No-presence integrity invariant

Permanent:

```text
range_presence_proven = false
→ no numeric historical integrated AP contribution may exist
```

Any materialized/nonzero historical contribution under false presence is a
cross-product integrity contradiction:

```text
FAIL CLOSED
HistoricalTrafficSourceUnavailable / equivalent safe unavailable path
```

## 9.9 Current-context matrix

### A. Current context available, non-empty

```text
current_population_status = available
current_population_count > 0

population =
historical validated ∪ current accepted

population_complete = true
```

Current-only AP:

```text
range_presence_proven = false
Share D/U/T = null
```

### B. Current context available, empty

```text
current_population_status = available
current_population_count = 0
```

This is a validated/proven zero.

Historical-only APs remain valid population members.

If historical population exists:

```text
population = historical population
population_complete = true
```

### C. Current context unavailable, historical evidence exists

```text
current_population_status = unavailable
current_population_count = null

population =
validated historical population only

population_complete = false
```

Historical AP shares may remain numeric.

Required product status:

```text
partial
```

when accepted historical Share evidence otherwise exists.

No current-only AP conclusion is made.

Absence of a current-only AP from the response is NOT proof of its absence from
the Site.

Historical Site denominator and AP historical contributions remain unchanged.

### D. Current context unavailable, no historical population

```text
current_population_status = unavailable
current_population_count = null
historical_population_count = 0
population_count = 0
population_complete = false

product status = insufficient_data
items = []
```

This means:

```text
no known historical Share population
AND current population could not be established
```

It does NOT mean:

```text
the Site is proven to have zero APs
```

### E. Current context malformed / integrity contradiction

If a current source returns evidence that is present but cannot be safely
interpreted, for example:

```text
duplicate/inconsistent AP identity
impossible population/page completeness
contradictory current population facts
malformed safely-returned evidence
```

required:

```text
FAIL CLOSED
```

Do NOT downgrade corrupt evidence to `unavailable`.

Transient/safe source unavailability and corrupt returned evidence are separate
semantic classes.

## 9.10 Supported population cap with unavailable current context

Hard support cap remains:

```text
12 AP per authorized canonical Site
```

When current context is available:

```text
full union population > 12
→ unsupported_population
```

When current context is unavailable:

```text
known historical population > 12
→ unsupported_population
```

If known historical population is <=12 while current context is unavailable:

```text
historical Share may be returned as partial
population_complete=false
```

The system MUST NOT assert that the unknown full union is <=12.

## 9.11 Historical-only / disappeared AP

Historical AP absent from current context remains visible.

If:

```text
range_presence_proven = true
```

it may have numeric historical Share.

## 9.12 Replacement AP

Different MAC:

```text
different AP identity
```

even if display name matches.

## 9.13 Population zero

If current context is available and both current/historical populations are
proved empty:

```text
population_count = 0
current_population_count = 0
population_complete = true
product status = insufficient_data
items = []
```

If current context is unavailable and historical population is empty, use Matrix D
instead; do not claim known-empty Site.

# 10. Exact Share metric identities

Canonical metric identity:

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

# 17. AP contribution identity and TRAFFIC-05 compatibility

For fixed:

```text
Site
range
evaluated_at
source snapshot
```

historical AP evidence identity is mandatory.

## 17.1 Always-required historical identity

Regardless of current context availability:

```text
APShare historical_population_count
==
TRAFFIC-05 validated historical population count
```

and historical AP MAC identity must come from the same validated historical
population semantics.

Share D/U integrated contribution MUST use the exact same underlying:

```text
ap_weighted_download
ap_weighted_upload
```

facts used by TRAFFIC-05 Average weighting.

Current implementation already represents AP Average conceptually as:

```text
avg_D =
ap_weighted_download / ap_accepted_interval_seconds

avg_U =
ap_weighted_upload / ap_accepted_interval_seconds
```

TRAFFIC-06 therefore requires:

```text
AP_WEIGHT_D = same ap_weighted_download
AP_WEIGHT_U = same ap_weighted_upload
```

not a separately recomputed equivalent.

For every AP with proven historical presence:

```text
APShare accepted_presence_seconds
==
TRAFFIC-05 ap_accepted_interval_seconds
```

Current internal Site opportunity evidence remains aligned with:

```text
ap_site_accepted_interval_seconds
```

## 17.2 Full population identity when current context is available

Only when:

```text
current_population_status = available
```

require full fixed-context identity:

```text
APShare population_count
==
TrafficByAP population_count

APShare current_population_count
==
TrafficByAP current accepted population count

APShare MAC set
==
TrafficByAP MAC set

display_name
==
TrafficByAP display_name

display_name_source
==
TrafficByAP display_name_source

supported_max_ap_count
==
12 in both

unsupported decision
==
same in both
```

## 17.3 Current context unavailable

When:

```text
current_population_status = unavailable
```

do NOT require identity with TRAFFIC-05's technical:

```text
current_population_count = 0
```

fallback.

That existing TRAFFIC-05 value is not promoted into new canonical Share
provenance.

Required:

```text
historical population identity still applies

historical AP weighted identity still applies

current population identity = unavailable / not asserted

full union population identity = not asserted

population_complete = false
```

This FINAL CANDIDATE therefore improves explicit current-context provenance for
TRAFFIC-06 without silently redefining TRAFFIC-05 public behavior.

Any future change to TRAFFIC-05 current-context public semantics requires a
separate explicit task/review.

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

Canonical mapping:

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

Outer Historical response status and Share product status are separate.

## 19.1 Outer Historical response

Existing common response fields remain:

```text
status
range
coverage
quality
```

TRAFFIC-06 does not redefine them.

## 19.2 Share product status

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

## 19.3 Status precedence

Use deterministic precedence:

```text
1. integrity contradiction
   → fail closed / no successful Share product DTO

2. known unsupported population
   → unsupported_population

3. no accepted Share intervals OR no known population
   → insufficient_data

4. trusted accepted Share exists but either:
      outer/Period coverage incomplete
      OR current_population_status=unavailable
   → partial

5. otherwise
   → ok
```

## 19.4 `ok`

Requires:

```text
current_population_status = available

supported full union population

population_count > 0

accepted intervals > 0

outer Historical status = ok

no Period interval exclusion

no AP decomposition integrity contradiction
```

Directional zero traffic does not by itself prevent `ok`.

## 19.5 `partial`

Requires trusted accepted Share evidence and at least one partiality reason such
as:

```text
outer Historical / Period coverage incomplete
OR
current_population_status = unavailable
```

Numeric Share on positive denominators means:

```text
Share within accepted comparable historical evidence
```

When current context is unavailable, the response also means:

```text
historical Share is valid for known historical APs
but current-only population enrichment is incomplete
```

## 19.6 `insufficient_data`

Required when no accepted Share intervals or no known historical/current
population can support the product.

Cross-field requirements:

```text
download denominator = insufficient_data
upload denominator = insufficient_data
total denominator = insufficient_data

all Share fractions = null
```

### Proven known-empty Site

If current context is available and full population is proved empty:

```text
current_population_status = available
current_population_count = 0
population_count = 0
population_complete = true
items = []
```

### Unknown current population + no historical population

```text
current_population_status = unavailable
current_population_count = null
historical_population_count = 0
population_count = 0
population_complete = false
items = []
```

Both are `insufficient_data`, but their provenance is different.

## 19.7 `unsupported_population`

When known population evidence proves the cap exceeded:

```text
returned_ap_count = 0
population_complete = false
items = []
```

With current context available, the full union count drives the decision.

With current context unavailable, historical count alone may prove unsupported if
it already exceeds 12.

## 19.8 Directional denominator matrix

Allowed:

```text
positive
zero_traffic
insufficient_data
```

### Product `insufficient_data`

All directional statuses:

```text
insufficient_data
```

and all Share fractions null.

### Product `ok` or `partial` + direction `zero_traffic`

```text
accepted intervals exist
SITE_WEIGHT_direction = 0
all fractions for that direction = null
```

### Product `ok` or `partial` + direction `positive`

For each AP:

```text
range_presence_proven = true
→ numeric Share, including valid 0.0

range_presence_proven = false
→ Share null
```

Then conservation and derived sum-to-one invariants MUST pass.

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

Canonical product order:

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

When `apshare` is requested, response contains:

```text
ap_traffic_share
```

No Share-only AP history axis, History buckets or AP historical arrays.

Canonical product constants:

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

Freeze exact fields:

```text
population_count
historical_population_count
current_population_status
current_population_count
supported_max_ap_count
returned_ap_count
population_complete
```

Rules:

```text
current_population_status=available
→ current_population_count is integer >=0

current_population_status=unavailable
→ current_population_count = null
→ population_complete = false
```

Never encode unavailable as fabricated current count `0`.

When unavailable:

```text
population_count = historical_population_count
```

and explicitly means known historical population count only.

## 21.2 Coverage projection

Share projects exact accepted Period interval evidence semantics, including enough
fields to prove range/accepted-time meaning.

No separate Share interval classifier.

## 21.3 Denominator projection

```text
download_status
upload_status
total_status
```

No Site/AP integrated weights are exposed as Traffic amounts.

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

## 21.5 Fraction validation

Every numeric fraction:

```text
finite
0 <= value <= 1
```

No NaN/Infinity.

Do not clamp malformed values.

## 21.6 Conservation validation

Before successful Share serialization:

```text
D conservation PASS
U conservation PASS
T conservation PASS
```

where applicable.

Do not normalize AP weights in the serializer.

## 21.7 No-presence validation

Required:

```text
range_presence_proven = false
→ accepted_presence_interval_count = 0
→ accepted_presence_seconds = 0
→ D/U/T Share = null
→ no numeric historical AP contribution
```

Conflict:

```text
FAIL CLOSED
```

## 21.8 Positive denominator validation

Direction `positive`:

```text
proven-presence APs → numeric Share
no-presence APs → null Share
numeric fractions fsum to 1 within 1e-9
```

## 21.9 Zero / insufficient denominator validation

Direction:

```text
zero_traffic
or
insufficient_data
```

requires every Share fraction for that direction:

```text
null
```

## 21.10 Current-context cross-field validation

### Available

```text
current_population_status=available
→ current_population_count integer >=0
```

Supported full union:

```text
population_complete=true
```

### Unavailable

```text
current_population_status=unavailable
→ current_population_count=null
→ population_complete=false
```

If historical population exists and accepted Share exists:

```text
product status must be partial
```

If no historical population:

```text
product status must be insufficient_data
items=[]
```

Malformed combinations fail closed.

## 21.11 Presentation conversion

Server fractions are canonical and unrounded.

UI may multiply by `100` for display.

Canonical display:

```text
0 → 0.00%
0 < percent < 0.01 → <0.01%
otherwise → two decimal places
```

Visual rounding is not a semantic sum-to-100 contract.

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

`TrafficHistoricalRequestBroker` owns:

```text
Share intent
selected/applied coordination
same-range coalescing
generation/supersession
response mapping
```

It is NOT scheduler owner.

`CaptivPortalTrafficCoordinator` remains sole:

```text
scheduler
network lifecycle owner
request timeout/backoff owner
page lifecycle owner
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

unless safely coalesced with other current same-range intents.

Share selection does not force unrelated historical products to recalculate.

## 23.2 AP + Share same-range coalescing

Allowed:

```text
products=aps,apshare
```

because both consume the same AP population / shared AP contribution foundation.

Coalescing is an optimization, not semantic identity.

## 23.3 Initial 24h grouping contract

There are exactly two allowed initial-load strategies.

### Preferred strategy — ALL24

Allowed only when exact candidate `ALL24` capability gate PASSes:

```text
Group ALL24:
history,statistics,peak,aps,apshare
```

One historical request.

### Canonical fallback strategy

If ALL24 capability FAILs while all mandatory scoped gates PASS, the accepted
candidate MUST use this deterministic initial grouping:

```text
G1:
history,statistics,peak

G2:
aps,apshare
```

Dispatch order:

```text
G1 first
then G2
```

subject to the existing coordinator/admission guard.

Rationale:

```text
G1 keeps Site-level History/Statistics/Peak together on shared Site evidence.

G2 keeps AP-heavy Traffic-by-AP and AP Share together on the one shared AP
contribution/weighting primitive.

Only two historical groups are created.

No duplicate AP history/contribution materialization is required between AP and
Share.

Existing Site-level products become available before the AP-heavy second group.
```

This exact fallback is architecture, not a Coder choice.

Forbidden fallback behavior:

```text
Coder invents arbitrary grouping after PERF

runtime sends ALL24, waits for it to fail/503, then retries split groups

adaptive undocumented group splitting

parallel G1/G2
```

If ALL24 is unsafe, the exact accepted candidate must be built/configured to use
G1→G2 from first dispatch.

## 23.4 Strategy selection before publication

Acceptance determines the allowed production initial strategy:

```text
ALL24 PASS
→ ALL24 strategy allowed

ALL24 FAIL
AND all core mandatory gates PASS
AND G1 PASS
AND G2/AS24 PASS
→ canonical G1→G2 fallback strategy required
```

If ALL24 fails and fallback gates fail:

```text
candidate FAIL
→ architecture/PERF review
```

No third grouping strategy is authorized by this FINAL CANDIDATE.

Any candidate change from ALL24 strategy to G1→G2 strategy changes the exact
candidate artifact and must be re-run through required acceptance gates.

## 23.5 Global Refresh

Global Refresh groups products by each panel's own selected range.

Within one same-range set, only accepted safe grouping is used.

Historical requests remain sequential.

## 23.6 Supersession

Latest Share intent wins.

A stale range/generation result cannot replace newer Share state.

No Share-owned timer/fetch/AbortController.

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

Canonical order:

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

Canonical safe fields when Share is requested:

```text
range
requested_products
product_count

share_status
share_population_count
share_historical_population_count

share_current_population_status
share_current_population_count

share_returned_ap_count
share_supported_max_ap_count
share_population_complete

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

Rules:

```text
share_current_population_status=available
→ share_current_population_count is numeric >=0

share_current_population_status=unavailable
→ do not log fabricated 0
→ count is omitted/null according to safe telemetry format
```

This must let operators distinguish:

```text
historical Share partial because historical coverage is partial
```

from:

```text
historical Share is valid but current population enrichment is unavailable
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

Conservation/current-context corruption failure is classified as safe
product/source integrity failure without exposing bad raw evidence.

# 28. Feature flag and atomic feature behavior

Canonical:

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

No QueryDeadline/browser timeout/Admin concurrency increase is allowed.

## 29.1 Baseline terminology

### TASK development parent

```text
022c8666ef58f0a6d4bef9dd72696199ebd5719f
tree a231cb06f15469ed99f0f8f4256b3ebc439467f2
```

### PERF/runtime compatibility reference

```text
daf68e91fc759188980cf8741913e6b60a58eb62
tree b0e2f028eecf6aec9d86e35542c33e7105209335
```

Before implementation authorization and before official PERF:

```text
re-fetch
pin exact candidate tree
pin exact compatibility baseline
classify drift
```

## 29.2 Controlled environment

Baseline/candidate comparisons use:

```text
same production-compatible Linux environment

same immutable production-size Observation snapshot

same snapshot SHA256 and byte size

same fixed evaluated_at_utc

same exact [from_utc,to_utc)

same QueryDeadline = 10s

same application/API timing boundary

same documented warm-up policy
```

Browser rendering and the 10-second client admission interval are not included in
a single database request duration.

## 29.3 Runs and percentile method

At least:

```text
10 measured runs
```

for every timing variant required below.

Warmups:

```text
unmeasured
documented
equal for comparable variants
```

Percentiles:

```text
sort ascending

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

Use:

```text
p=0.50 for p50
p=0.95 for p95
```

`max` is literal measured maximum.

## 29.4 Performance matrix

### Always mandatory candidate-acceptance variants

```text
SH24
range=24h
products=apshare

SH7
range=7d
products=apshare

BA24
baseline range=24h
products=aps

BA7
baseline range=7d
products=aps

CA24
candidate range=24h
products=aps

CA7
candidate range=7d
products=aps

AS24
candidate range=24h
products=aps,apshare

AS7
candidate range=7d
products=aps,apshare

E24-B
baseline range=24h
products=history,statistics,peak,aps

E24-C
candidate range=24h
products=history,statistics,peak,aps
```

These are mandatory release gates.

### Mandatory capability measurement

```text
ALL24
candidate range=24h
products=history,statistics,peak,aps,apshare
```

ALL24 MUST be measured.

Its PASS/FAIL selects allowed initial broker grouping.

ALL24 is NOT by itself an unconditional candidate-failure gate.

### Canonical fallback measurement

```text
G1-24
candidate range=24h
products=history,statistics,peak

G2-24
candidate range=24h
products=aps,apshare
```

`G2-24` is identical to mandatory `AS24`.

`G1-24` MUST be measured as resilience/capability evidence.

If ALL24 FAILs, `G1-24` and `G2-24/AS24` become mandatory candidate-acceptance
gates for the fallback strategy.

No mandatory legacy all-products 7d combined variant exists.

RANGE-01 intentionally removed that requirement.

## 29.5 Share-only hard time gates

SH24 / SH7:

```text
p95 <= 8.0s
max <= 9.0s
query_deadline = 0
source_integrity = 0
unexpected_5xx = 0
```

## 29.6 Share-only hard byte gate

Share-only has at most 12 aggregate AP rows and no historical arrays.

Hard:

```text
SH24 response_bytes <= 65536
SH7  response_bytes <= 65536
```

64 KiB is an architecture guard against accidental History/AP-series/raw
contribution serialization.

## 29.7 AP-only backward compatibility

Compare:

```text
BA24 ↔ CA24
BA7  ↔ CA7
```

Semantic identity required except documented per-request transport metadata.

Relative gates:

```text
Δp50 <= max(0.50s, 20% baseline p50)

Δp95 <= max(0.75s, 25% baseline p95)

Δmax <= max(1.00s, 25% baseline max)
```

Candidate AP-only hard:

```text
p95 <= 8.0s
max <= 9.0s
query_deadline = 0
source_integrity = 0
unexpected_5xx = 0
```

## 29.8 AP + Share coalesced

AS24 / AS7 compare against candidate AP-only CA24 / CA7.

Incremental Share overhead:

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

Byte gates:

```text
AS24 response_bytes <= CA24 response_bytes + 65536

AS7 response_bytes <= CA7 response_bytes + 65536

AND
response_bytes < WEB_ADMIN_MAX_RESPONSE_BYTES
```

## 29.9 Existing four-product 24h compatibility

E24-B baseline:

```text
history,statistics,peak,aps
```

E24-C candidate:

```text
history,statistics,peak,aps
```

Require semantic identity excluding documented request/transport metadata.

Relative:

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

This is mandatory even if Share itself is feature-disabled in a compatibility
variant.

## 29.10 ALL24 capability gate

ALL24 is measured with at least 10 runs.

Capability PASS requires:

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

### ALL24 PASS

Then production initial 24h broker grouping MAY use:

```text
history,statistics,peak,aps,apshare
```

as one request.

### ALL24 FAIL

ALL24 capability is unavailable.

This alone does NOT reject the candidate if all mandatory scoped gates pass and
the canonical fallback grouping passes.

The accepted candidate MUST then use:

```text
G1 = history,statistics,peak
G2 = aps,apshare
```

from initial dispatch.

No initial "try ALL24 then fallback after failure" behavior is allowed.

## 29.11 Canonical fallback G1 gate

`G1-24`:

```text
products=history,statistics,peak
```

Hard capability:

```text
p95 <= 8.0s
max <= 9.0s
query_deadline = 0
source_integrity = 0
unexpected_5xx = 0

response_bytes < WEB_ADMIN_MAX_RESPONSE_BYTES
```

Semantic output must equal the corresponding History/Statistics/Peak
subproducts from the same fixed candidate evidence context.

### If ALL24 PASS

G1 result is resilience evidence and does not block candidate acceptance by
itself.

### If ALL24 FAIL

G1 becomes a mandatory acceptance gate.

G2 is already mandatory `AS24`, so fallback requires:

```text
G1 PASS
AND
AS24/G2 PASS
```

## 29.12 Exact candidate acceptance logic

Let:

```text
CORE =
all semantic/security/serializer tests PASS
AND SH24 PASS
AND SH7 PASS
AND BA24↔CA24 PASS
AND BA7↔CA7 PASS
AND AS24 PASS
AND AS7 PASS
AND E24-B↔E24-C PASS
AND all mandatory byte gates PASS
```

Then:

```text
candidate acceptance requires:

CORE PASS
AND
(
    ALL24 PASS
    OR
    (
        ALL24 FAIL
        AND G1-24 PASS
        AND G2-24/AS24 PASS
        AND exact candidate initial broker strategy = G1→G2
    )
)
```

Therefore:

```text
ALL24 PASS
OR
approved canonical fallback grouping PASS
```

is the initial-load capacity requirement.

Candidate FAILs if:

```text
CORE fails
```

or:

```text
ALL24 fails
AND canonical fallback cannot pass
```

No unreviewed third grouping is authorized.

## 29.13 Admission guard and fallback timing

G1 and G2 are separate HTTP/database requests.

They are not added together and compared to the 10s QueryDeadline.

Browser orchestration remains:

```text
G1 dispatch
→ completion
→ next dispatch eligibility obeys 10-second admission guard
→ G2 dispatch
```

The admission delay is expected orchestration safety behavior.

## 29.14 Query plan / work-shape proof

For materially new/refactored Share work, capture safe plan/profile evidence.

Prove:

```text
requested-range bounded

same read-only source snapshot

same QueryDeadline

no all-history validation

no second historical semantic owner

no N × full-history AP explosion

population cap discovered before unnecessary over-bound work

one shared AP contribution primitive reused
```

No new index is authorized by this FINAL CANDIDATE.

## 29.15 PERF failure policy

If a mandatory scoped/fallback gate fails:

```text
candidate NOT ACCEPTED
publication NOT AUTHORIZED
```

Forbidden remediation without new architecture review:

```text
increase QueryDeadline
increase browser timeout
increase Admin concurrency
add index/cache/rollup
weaken integrity
silent truncation
invent another grouping
```

# 30. Testing / acceptance contract

Testing governance remains:

```text
Coder:
focused/minimal TASK/module development tests only

Owner + Tech Lead / Central Lab:
targeted cross-surface regression
full official gate
official Linux PERF
official PASS/FAIL
```

## 30.1 Core semantic tests

Mandatory:

```text
exact metric/method identifiers
exact Period interval evidence identity
one shared AP weighting primitive
range_presence_proven semantics
strict structural absence qualification
present-invalid contradiction fail-closed
D/U/T conservation
no AP-weight renormalization
Total formula exact
valid numeric zero
zero Site denominator
partial/insufficient/unsupported matrices
Site isolation
```

## 30.2 Sample-count counterexample

AP-A:

```text
many low-rate accepted samples
```

AP-B:

```text
fewer samples with larger time-integrated contribution
```

Share follows:

```text
rate × elapsed contribution
```

not sample count.

## 30.3 Bucket-average counterexample

Use unequal accepted interval lengths.

Prove bucket-average Share is wrong and canonical Share follows exact shared
weighted evidence.

## 30.4 Total-share counterexample

Prove Total Share is not sum/average of D/U percentages.

Required:

```text
D denominator=0, U>0
→ Total Share == U Share

U denominator=0, D>0
→ Total Share == D Share

D=0, U=0
→ Total Share null
```

## 30.5 Current-context matrix tests

### Available + current-only AP

```text
current_population_status=available
range_presence_proven=false
Share=null
```

### Available + validated zero current AP

```text
current_population_status=available
current_population_count=0
```

This exact zero is preserved.

### Unavailable + historical APs

Expected:

```text
historical Shares retained
product status=partial
current_population_status=unavailable
current_population_count=null
population_complete=false
no fabricated count=0
```

Also prove:

```text
Site historical denominator unchanged
```

relative to same historical evidence without current enrichment.

### Unavailable + no historical AP

Expected:

```text
status=insufficient_data
items=[]
current_population_status=unavailable
current_population_count=null
population_complete=false
```

and no assertion of known-empty Site.

### Malformed current population evidence

Expected:

```text
FAIL CLOSED
```

not downgrade to unavailable.

## 30.6 Current-only contribution contradiction

Inject:

```text
range_presence_proven=false
+
numeric/nonzero historical AP contribution
```

Expected:

```text
FAIL CLOSED
```

## 30.7 Proven AP + structural absence

AP has accepted historical presence in one part of range and structural absence
in other trusted complete Site samples.

Expected:

```text
range_presence_proven=true
absence intervals contribute zero
Share remains numeric when denominator positive
```

## 30.8 Present-invalid contradiction

Canonical Site endpoint accepted, but AP selected-source evidence is corrupt.

Expected:

```text
FAIL CLOSED
```

not partial/zero-fill/Share-only interval exclusion.

## 30.9 Conservation violation

Inject:

```text
Σ AP_WEIGHT != SITE_WEIGHT
```

Expected:

```text
FAIL CLOSED
```

and prove no renormalization.

## 30.10 TRAFFIC-05 / TRAFFIC-06 identity

Always prove historical identity:

```text
historical population
historical AP MACs
shared weighted D/U facts
accepted_presence_seconds
```

For proven AP:

```text
APShare accepted_presence_seconds
==
TRAFFIC-05 ap_accepted_interval_seconds
```

When current context is available additionally prove:

```text
full population count
current population count
MAC set
display name/source
cap
unsupported decision
```

When current context is unavailable:

```text
do NOT assert current_population_count identity with TRAFFIC-05 technical fallback
```

Historical identity still applies.

## 30.11 Period interval identity

Same fixed context:

```text
candidate_interval_count
accepted_interval_count
accepted_interval_seconds
interval_coverage_ratio
gap/source-transition/invalid counts
leading_unweighted_seconds
trailing_unweighted_seconds
```

must equal Period Statistics evidence.

No Share interval classifier.

## 30.12 Population tests

Mandatory:

```text
proved empty current + empty historical
unavailable current + empty historical
current-only
historical-only
disappeared AP
replacement AP
1 AP
2 AP
12 AP
13 AP unsupported
no truncation
deterministic order
Site-local cap
```

## 30.13 API / atomic feature tests

Mandatory:

```text
feature flag default false
feature dependencies
auth before product projection
Site authorization
products=apshare
products=aps,apshare
all-five canonical order
out-of-order/duplicate/malformed rejected
include+products rejected
legacy include unchanged

Share flag false:
  apshare → whole request 404
  aps,apshare → whole request 404
  no partial product response
```

## 30.14 Feature-OFF regressions

With Share flag false prove pre-TASK semantics unchanged for:

```text
history
statistics
peak
aps
existing product combinations
legacy include=
```

Also:

```text
Share panel absent
broker no apshare intent
no Share calculation
```

## 30.15 Serializer tests

Mandatory:

```text
fractions finite/in range

current_population_status available/unavailable matrix

unavailable → current_population_count null

available zero → current_population_count=0

false presence → shares null

false presence + numeric contribution → fail closed

positive denominator:
  conservation PASS
  numeric fractions sum 1 within 1e-9

zero denominator:
  direction fractions null

insufficient denominator:
  direction fractions null

population zero matrices

unsupported matrix

Total formula exact

cross-field corruption fail closed
```

## 30.16 Frontend / broker tests

Mandatory:

```text
Share independent 24h/7d
default 24h
selected/applied separate
waiting != loading
prior successful payload retained
latest intent wins
stale response rejected
same-range AP+Share coalescing
Global Refresh grouping
10-second guard
manual retry cannot bypass
503 cannot bypass
Retry-After preserved
max in-flight=1
no Share-owned scheduler/timer/AbortController/fetch
reload resets 24h
no storage persistence
all supported APs shown
current-only null display
true zero display
partial/current-population-unavailable qualifier
insufficient/unsupported/zero-traffic states
```

## 30.17 Initial grouping tests

Implementation MUST support:

```text
ALL24 strategy
```

and canonical:

```text
G1 history,statistics,peak
G2 aps,apshare
```

fallback capability.

If accepted candidate uses ALL24:

```text
initial request = exact ALL24
```

If accepted candidate uses fallback:

```text
initial request 1 = exact G1
request 2 = exact G2
requests sequential
10-second admission guard respected
no initial ALL24 attempt
```

No arbitrary grouping.

## 30.18 Security tests

Site A + Site B fixture.

Site B never affects Site A:

```text
population
presence
current population provenance
weights
denominator
Share
cap
coverage
telemetry
```

## 30.19 PERF

All Section 29 required measured variants and conditional strategy gates apply.

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

FINAL CANDIDATE finds no proven need for:

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

treating current context unavailable as proved current population zero

failing the entire historical Share solely because safe current enrichment is unavailable

downgrading corrupt current evidence to transient unavailable
```

If any of these is needed:

```text
EXPLICIT ARCHITECTURAL DECISION REQUIRED
```

with root cause, evidence, alternatives, migration/rollback impact.

---

# 35. Acceptance criteria

TRAFFIC-06 implementation can be accepted only if approved FINAL gates PASS on
the exact candidate tree.

Minimum:

```text
1. Share is time-integrated accepted contribution ratio.

2. sample count is not numerator/denominator.

3. Share uses exact Period Statistics Site interval classification.

4. one shared AP contribution/weighting primitive is reused with TRAFFIC-05.

5. range_presence_proven resolves current-only null vs structural zero.

6. current context unavailable is distinct from current population empty.

7. current_population_status is explicit.

8. unavailable current context uses current_population_count=null,
   never fabricated 0.

9. unavailable current context does not destroy valid historical Share.

10. unavailable current context + valid historical Share → product partial,
    population_complete=false.

11. unavailable current context + no historical population →
    insufficient_data/items=[] without claiming known-empty Site.

12. malformed current population evidence fails closed.

13. current AP rates never enter Share numerator/denominator.

14. Site historical denominator is invariant to current-enrichment availability.

15. false historical presence cannot carry numeric historical contribution.

16. structural absence is zero only inside trusted complete Site samples
    after historical presence is proven.

17. present-invalid AP evidence on accepted Site endpoint fails closed.

18. canonical denominator is SITE_WEIGHT.

19. D/U/T conservation passes before division.

20. no AP-weight renormalization.

21. Total weight/share uses D+U weights, not D/U percentages.

22. positive denominator yields derived sum-to-one.

23. zero denominator produces null fractions.

24. product insufficient_data yields denominator insufficient_data and null shares.

25. proved current population zero remains numeric 0.

26. current-only AP with available current context → null Share, not 0%.

27. proven AP with true zero contribution may show numeric 0%.

28. historical identity with TRAFFIC-05 passes always.

29. full current/full-union identity with TRAFFIC-05 is asserted only when current
    context is available.

30. Site isolation passes.

31. products=apshare is canonical final token.

32. legacy include remains unchanged.

33. mixed projection containing disabled Share is atomically 404.

34. feature OFF is semantically backward compatible.

35. Share panel owns independent selected/applied range.

36. broker/coordinator ownership unchanged.

37. max historical in-flight remains 1.

38. 10-second admission guard unchanged.

39. SH24/SH7 mandatory PERF PASS.

40. BA↔CA AP-only compatibility PASS for 24h and 7d.

41. AS24/AS7 mandatory coalesced PERF PASS.

42. E24-B↔E24-C mandatory existing-four-product compatibility PASS.

43. ALL24 is measured as capability gate.

44. If ALL24 PASSes, ALL24 initial grouping is allowed.

45. If ALL24 FAILs, candidate may still pass only with canonical fallback:
    G1=history,statistics,peak
    then G2=aps,apshare.

46. If fallback is required, G1 PASS and G2/AS24 PASS are mandatory.

47. Accepted fallback candidate MUST NOT first attempt ALL24 in production.

48. No unreviewed third grouping strategy.

49. SH24/SH7 payload <=64KiB.

50. AS payload <= candidate AP-only +64KiB and below platform max.

51. ALL24 payload <= E24-C +64KiB and below platform max for ALL24 capability PASS.

52. QueryDeadline/browser timeout/Admin concurrency unchanged.

53. no new DB/schema/index/cache/rollup/collector/Omada path without separate
    architecture decision.

54. repository feature flag default is OFF.

55. dormant deploy and separate activation remain Owner-controlled.
```

Exact candidate acceptance principle:

```text
CORE mandatory scoped gates PASS

AND

(
  ALL24 capability PASS
  OR
  canonical G1→G2 fallback gates PASS
)
```

Any mandatory semantic/security/PERF/fallback failure:

```text
candidate NOT ACCEPTED
normal publication NOT AUTHORIZED
```

# 36. FINAL decisions

The following architecture decisions are frozen in this FINAL CANDIDATE.

| Decision | Frozen contract |
|---|---|
| Share semantic | `accepted_site_interval_integrated_ap_contribution_ratio.v1` |
| Historical owner | `HistoricalTrafficReadService` only |
| AP weighting | one shared internal primitive with TRAFFIC-05 |
| Site interval basis | exact Period Statistics interval evidence |
| Canonical denominator | Site D/U/T integrated weights |
| Conservation | Site weight must equal `fsum(AP weights)` within `rel_tol=1e-9`, `abs_tol=1e-9` |
| Renormalization | forbidden |
| Total Share | `(AP_WEIGHT_D+AP_WEIGHT_U)/(SITE_WEIGHT_D+SITE_WEIGHT_U)` |
| Historical presence | explicit `range_presence_proven` |
| Current-only AP | null Share when historical presence unproven |
| Structural absence | zero only after proven presence inside trusted complete Site sample |
| Present-invalid AP evidence | fail closed |
| Population target | `current_union_historical_validated.v1` |
| Current context provenance | `current_population_status=available|unavailable` |
| Current count unavailable | `null`, never fabricated `0` |
| Current unavailable + historical Share | historical Share retained, product `partial`, population incomplete |
| Current unavailable + no historical population | `insufficient_data`, `items=[]`, not known-empty Site |
| Current malformed | fail closed |
| TRAFFIC-05 full population identity | required only when current context available |
| Population cap | 12 per authorized canonical Site |
| Truncation/top-N | forbidden |
| API token | `apshare` |
| Canonical product order | `history,statistics,peak,aps,apshare` |
| Legacy include | no Share extension |
| Mixed disabled projection | whole request 404 |
| Range | independent 24h/7d |
| Broker/coordinator | unchanged ownership |
| Historical concurrency | max one in-flight |
| Admission guard | 10 seconds unchanged |
| Feature flag | `WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED=false` |
| ALL24 | measured capability, not unconditional candidate gate |
| Preferred initial grouping | ALL24 only if capability PASS |
| Canonical fallback | G1=`history,statistics,peak`; G2=`aps,apshare` |
| Fallback dispatch order | G1 then G2 under existing admission guard |
| Runtime try/fail fallback | forbidden |
| QueryDeadline | 10s unchanged |
| Browser timeout | unchanged |
| Admin concurrency | unchanged |
| New DB/schema/index/cache/rollup/collector | not authorized |

# 37. Coder implementation boundaries

This section defines boundaries only.

Implementation is NOT authorized by this FINAL CANDIDATE.

If Owner later grants separate implementation authorization, Coder may work
inside the following architectural scope.

## 37.1 Allowed implementation class

Allowed:

```text
extend HistoricalTrafficReadService projection for AP Share

extract/refactor a private shared AP contribution primitive

extend AnalyticsSourceGateway bounded requested-range facts as necessary

add Share models/internal DTOs

extend Admin query orchestration to preserve explicit current-context provenance

extend historical serializer

extend products= grammar with apshare

add Share panel/template/frontend state through existing broker/coordinator

add feature flag default false

add focused TASK tests
```

Likely files may include current Traffic/Analytics/Admin modules such as:

```text
app/analytics/historical_traffic.py
app/analytics/source_gateway.py
app/analytics/models.py

app/admin_web/query_service.py
app/admin_web/routes.py
app/admin_web/historical_traffic_serialization.py
app/admin_web/config.py
app/admin_web/pages.py
app/admin_web/templates/admin/traffic.html
app/admin_web/static/admin.js
app/admin_web/static/admin.css

app/config.py
app/settings.py
.env.example

focused tests
```

Exact file list is implementation-dependent.

## 37.2 Mandatory preservation

Coder MUST preserve:

```text
existing TRAFFIC-05 public semantics

existing products without apshare

legacy include behavior

Site isolation

Period interval classifier

shared QueryDeadline

broker/coordinator ownership

max one historical in-flight

10-second admission guard

12-AP cap/no truncation
```

## 37.3 Current-context boundary

Coder MUST NOT simply copy TRAFFIC-05 technical:

```text
current source unavailable
→ current_population_count=0
```

into Share public semantics.

Share requires explicit:

```text
available → numeric count
unavailable → null count
```

while retaining valid historical Share.

Coder MUST NOT silently modify TRAFFIC-05 public current-context behavior as part
of this task.

## 37.4 Weighting boundary

Coder MUST NOT implement a second independent:

```text
AP rate × elapsed
```

pipeline.

Share must consume the same underlying AP weighted D/U facts used by TRAFFIC-05.

No AP renormalization.

## 37.5 Grouping boundary

Coder MUST implement/support only:

```text
ALL24 strategy if exact candidate capability PASSes
```

or canonical fallback:

```text
G1 = history,statistics,peak
G2 = aps,apshare
```

according to accepted candidate PERF.

Coder MUST NOT invent runtime grouping after implementation.

If acceptance selects fallback, exact candidate must dispatch G1→G2 directly and
must not deliberately attempt unsafe ALL24 first.

## 37.6 Forbidden without new architecture review

STOP if implementation requires:

```text
new DB/schema/index
cache/rollup
collector/Omada read
new historical semantic owner
new Share interval classifier
independent weighting pipeline
metric semantic change
TRAFFIC-05 public semantic change
different population cap
silent truncation
new scheduler
QueryDeadline increase
browser timeout increase
Admin concurrency increase
third fallback grouping
```

Return evidence to Architect / Owner / Tech Lead.

## 37.7 Testing governance

Coder later owns only focused/minimal development verification inside TASK scope.

Official:

```text
targeted regression
Central Lab full gate
Linux production-size PERF
official PASS/FAIL
```

remain Owner + Tech Lead / Central Lab responsibility.

No implementation/publish/deploy action is authorized by this document.

---

# 38. FINAL CANDIDATE state

```text
TASK:
TASK-TRAFFIC-06 — AP Traffic Share

DOCUMENT:
FINAL CANDIDATE

TASK DEVELOPMENT PARENT:
022c8666ef58f0a6d4bef9dd72696199ebd5719f
tree a231cb06f15469ed99f0f8f4256b3ebc439467f2

RUNTIME / PERF COMPATIBILITY REFERENCE:
daf68e91fc759188980cf8741913e6b60a58eb62
tree b0e2f028eecf6aec9d86e35542c33e7105209335

REPOSITORY DRIFT:
NONE AT FINAL-CANDIDATE RECHECK

CURRENT-CONTEXT SEMANTICS:
FROZEN

ALL24 CAPABILITY VS ACCEPTANCE POLICY:
FROZEN

CANONICAL FALLBACK:
G1 history,statistics,peak
G2 aps,apshare

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

Before any separate implementation authorization:

```text
re-fetch origin/main
re-pin exact SHA/tree
impact-review implementation drift
```

STATUS: FINAL CANDIDATE — AWAITING OWNER / TECH LEAD APPROVAL; IMPLEMENTATION NOT AUTHORIZED
