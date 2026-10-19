# TASK-TRAFFIC-03 — Period Statistics — FINAL

**Проект:** CaptivPortal  
**Area:** Admin Console → Traffic  
**Parent:** `CaptivPortal — Генеральная дорожная карта раздела Admin Console → Traffic — FINAL v1`  
**Dependencies:** `TRAFFIC-00`, `TRAFFIC-01`, `TRAFFIC-02-READ`, `TRAFFIC-02`, `TASK-TRAFFIC-02-PERF-01`  
**Тип:** architecture / Historical read extension + Admin API consumer + functional panel specification  
**Статус:** `FINAL — TECH LEAD REVIEW INCORPORATED`  
**Implementation authorization:** `NOT GRANTED BY THIS FINAL; REQUIRES SEPARATE OWNER AUTHORIZATION`  
**Branch / code / commit / push / PR / merge:** `NOT AUTHORIZED BY THIS FINAL`  
**Deployment / production activation:** `NOT AUTHORIZED BY THIS FINAL; SEPARATE OWNER-CONTROLLED ACTION`  
**Finalized:** 2026-08-30
**Tech Lead review:** `ARCHITECTURE DIRECTION PASS / 5 MANDATORY CORRECTIONS INCORPORATED`

---

# 0. Executive decision

`TRAFFIC-03` добавляет следующую Network Traffic плашку:

```text
Period Statistics
```

Она отвечает только на вопрос:

```text
«Сколько?»
```

Обязательные v1 metrics:

```text
Average Download
Average Upload
Average Total

Peak Download
Peak Upload
Peak Total
```

Unit:

```text
Mbps
```

В этом TASK:

```text
Average Total
Peak Total
```

являются **обязательными**, а не optional.

Canonical source/owner:

```text
Observation persisted AP history
        ↓
AnalyticsSourceGateway
        ↓
HistoricalTrafficReadService
        ↓
shared historical application request
        ↓
Admin safe serialization
        ↓
Traffic browser
        ↓
Period Statistics
```

Permanent:

```text
TRAFFIC-03 DOES NOT create a second Historical Traffic semantic owner.
```

Key FINAL decisions:

```text
Period Average
→ interval/time-aware
→ uses accepted persisted Site rate values
→ weighted by accepted canonical Site sample intervals
→ no re-calculation of Mbps from raw counters
→ no average(History bucket means)
→ no average(all persisted sample rates)

Peak
→ maximum accepted complete Site sample value
→ no missing/invalid evidence treated as zero
→ no peak timestamp in TRAFFIC-03

HTTP/API
→ NO separate /traffic/statistics request in v1
→ reuse the existing History request
→ optional include=statistics
→ one range/evaluation/source read execution
→ avoid a second expensive historical scan

Feature flag
→ WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=false
→ subordinate product-exposure flag
→ requires Admin + Traffic + History enabled

Frontend
→ no second scheduler/coordinator
→ Statistics is a passive range-sensitive consumer
   of the accepted History coordinator execution

Performance
→ existing shared Admin deadline remains authoritative
→ no timeout/deadline increase
→ no cache/rollup/new DB
```

This FINAL does not grant implementation, merge, deployment or production activation authorization.

---

# 1. Exact repository baseline recheck

Current repository state was rechecked immediately before issuing this FINAL.

```text
origin/main =
473df4646970292f7bcea74d5d69fce03dba642a

tree =
ba145de1bba0aa30d2f87fc769c0d8e5f9fc8f54
```

Current main:

```text
Merge PR #88
fix: bound historical traffic queries to requested range
```

FINAL re-fetch result:

```text
reviewed DRAFT baseline = FINAL baseline
SHA drift = NONE
tree drift = NONE
impact review = NO CONFLICT
```

PR #88 publication candidate:

```text
4e43e07b9401346e51a938df08346b4c89448373
```

PR #88 parent:

```text
bf918a567aa53458810332c99cedd39e9b7b2f18
```

which is the merge of:

```text
PR #87
TASK-TRAFFIC-02 — Network Traffic History
```

If `origin/main` changes after this FINAL and before implementation authorization:

```text
re-fetch
re-pin exact SHA/tree
perform impact review
```

Mandatory impact review if newer main touches:

```text
app/analytics/historical_traffic.py
app/analytics/models.py
app/analytics/source_gateway.py
app/analytics/runtime.py

app/admin_web/config.py
app/admin_web/pages.py
app/admin_web/query_service.py
app/admin_web/routes.py
app/admin_web/historical_traffic_serialization.py
app/admin_web/traffic_network_ranges.py
app/admin_web/static/admin.js
app/admin_web/static/admin.css
app/admin_web/templates/admin/traffic.html

app/config.py
app/settings.py
.env.example
```

---

# 2. Current predecessor state

For this FINAL, accepted predecessor state is:

```text
TRAFFIC-00 — Traffic Section Foundation
DONE / MERGED / PRODUCTION

TRAFFIC-01 — Current Network Throughput
DONE / MERGED / PRODUCTION

TRAFFIC-02-READ — Historical Network Traffic Read Foundation
DONE / ACCEPTED / MERGED

TRAFFIC-02 — Network Traffic History
DONE / ACCEPTED / MERGED / PRODUCTION

TASK-TRAFFIC-02-PERF-01
Historical range query remediation
DONE / ACCEPTED / MERGED / PRODUCTION
```

Owner reports current production has:

```text
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
```

and History has passed production acceptance.

Repository truth and Owner-reported production state remain separate concepts.

---

# 3. PR #87 — accepted TRAFFIC-02 contracts to reuse

Current TRAFFIC-02 already provides:

```text
GET /admin/api/v1/sites/<site_id>/traffic/history?range=24h|7d
```

Server-owned range resolver:

```text
app/admin_web/traffic_network_ranges.py
```

Canonical Network range IDs:

```text
24h
7d
```

Default selected Network range:

```text
24h
```

Canonical server resolution:

```text
evaluated_at_utc = server UTC now
to_utc = evaluated_at_utc

24h:
from_utc = evaluated_at_utc - 86400 s

7d:
from_utc = evaluated_at_utc - 604800 s
```

Interval:

```text
[from_utc,to_utc)
```

Browser never calculates canonical UTC boundaries.

---

# 4. Current shared Network range owner

Current browser contract already exposes:

```text
window.CaptivPortalTrafficNetworkRange
```

with:

```text
selected()
select(...)
subscribe(...)
```

Current DOM controls:

```text
traffic-network-range-24h
traffic-network-range-7d
```

Permanent ownership:

```text
Traffic page / Network Traffic analytical context
→ owns selected Network range
```

Not:

```text
History panel owns range
Statistics panel owns range
Peak panel owns range
AP panel owns range
```

Current consumers:

```text
TRAFFIC-02 History
```

This TASK adds:

```text
TRAFFIC-03 Period Statistics
```

Future:

```text
TRAFFIC-04
TRAFFIC-05
TRAFFIC-06
```

MUST reuse the same selected Network range.

---

# 5. Current History frontend orchestration

Current History panel key:

```text
network-traffic-history
```

Current registration:

```text
autoRefresh=false
```

Existing `CaptivPortalTrafficCoordinator` owns:

```text
one initial execution
generation
AbortController
same-origin request
request timeout
Retry-After/backoff
manual refresh
refreshPanel
refreshAll
visibility lifecycle
pagehide
global auth failures
panel-local failures
```

Current History loader captures:

```text
rangeContext.selected()
```

locally for each execution.

Rapid supersession already uses coordinator generation/abort protection.

`TRAFFIC-03` MUST preserve this.

---

# 6. Current History DTO — accepted basis

History response currently exposes:

```text
result.status
result.range
result.buckets
result.coverage
result.quality
```

Exact v1 range contracts:

```text
24h
duration = 86400 seconds
bucket_seconds = 300
bucket_count = 288

7d
duration = 604800 seconds
bucket_seconds = 900
bucket_count = 672
```

History bucket aggregation:

```text
mean_of_complete_site_rate_samples
```

Hard boundary:

```text
History bucket mean
!=
Period Average
```

---

# 7. Current Historical semantic owner

Current accepted service:

```python
HistoricalTrafficReadService.get_site_history(
    site_id,
    *,
    from_utc,
    to_utc,
    evaluated_at_utc=None,
    bucket_seconds=None,
    deadline=None,
)
```

Canonical facts:

```text
sample_at =
ap_dynamic cycle.finished_at

MAX_SITE_HISTORY_BUCKETS =
720

MAX_SITE_SAMPLE_SOURCE_SKEW_SECONDS =
60

primary source =
wired

fallback =
lan

source decision =
one Site bucket / one source family

source mixing inside bucket =
false
```

The service already owns:

```text
Site validation
range validation
source integrity
source-family selection
complete Site sample acceptance
gap semantics
coverage
quality
watermark
deadline propagation
```

---

# 8. PERF-01 accepted remediation — mandatory preservation

PR #88 fixed a production deadline defect.

Root cause:

```text
historical candidate validation previously touched
all persisted history before requested 24h/7d filtering
```

On production-size Observation storage this could exceed:

```text
shared Admin query deadline
```

and return intermittent:

```text
503 query_deadline
```

PR #88 changed historical candidate work to:

```text
requested-range bounded aggregation
+
separate bounded source-boundary/watermark lookup
```

`TRAFFIC-03` MUST NOT regress this.

Forbidden:

```text
reintroduce whole-history candidate validation
for Period Statistics

run a second full candidate validation pass
for the same range

load all history into Python
```

---

# 9. Current accepted production-size performance evidence

After PERF remediation, accepted production-size read-only evidence on
approximately 253 MB `observations.sqlite3`:

```text
24h:
5/5 PASS
p50 ≈ 1.005s
max ≈ 1.077s

7d:
5/5 PASS
p50 ≈ 5.332s
max ≈ 6.457s

failures:
0
```

Shared query deadline remained unchanged.

No cache, rollup, DB or timeout increase was used as the fix.

---

# 10. Product domain

`TRAFFIC-03` belongs only to:

```text
NETWORK TRAFFIC
```

Meaning:

```text
Site AP/network throughput evidence
```

Unit:

```text
Mbps
```

Forbidden product meanings:

```text
Internet Traffic
WAN Traffic
Internet Usage
WAN Usage
billing traffic
Guest Traffic
Guest Session Traffic
SSID Traffic
Zefer_Parki Traffic
```

Radio is not a Site Network Traffic v1 source.

---

# 11. Required visible metrics — FINAL scope decision

All six are required:

```text
Average Download
Average Upload
Average Total

Peak Download
Peak Upload
Peak Total
```

No metric is optional in this TASK.

Reason for making Total mandatory:

```text
1. Historical Site samples already have canonical
   Download + Upload + Total semantics.

2. Total is the exact aggregate Network Throughput direction-combination
   later needed by TRAFFIC-04 busiest-period selection.

3. Average Total can be validated against the same accepted interval basis
   used by Download and Upload.

4. Peak Total is NOT derivable as Peak Download + Peak Upload because the
   directional peaks may occur at different samples.

5. Making Total explicit now avoids later introducing an ambiguous
   browser-side derived KPI.
```

---

# 12. Semantic split: TRAFFIC-03 vs TRAFFIC-04

Permanent:

```text
TRAFFIC-03
= How much?

Average Download
Average Upload
Average Total
Peak Download
Peak Upload
Peak Total
```

Future:

```text
TRAFFIC-04
= When?

busiest bucket
busiest hour
timestamp/range
average throughput during busiest period
```

`TRAFFIC-03` MUST NOT expose:

```text
peak timestamp
peak bucket
peak hour
busiest timestamp
busiest range
peak composition time
```

Those belong to TRAFFIC-04.

---

# 13. Critical forbidden Period Average algorithms

Forbidden:

```text
average(History bucket.download_mbps)

average(History bucket.upload_mbps)

average(History bucket.total_mbps)
```

Also forbidden:

```text
average(all persisted Site sample rates)
```

when samples are weighted equally regardless of elapsed time.

Also forbidden:

```text
browser calculates Average from History buckets
```

Also forbidden:

```text
Admin layer reads raw Observation rows
and calculates Period Average
```

---

# 14. Why History bucket mean cannot be Period Average

History bucket v1 is:

```text
arithmetic mean of complete Site samples
inside one display bucket
```

Sampling intervals can differ.

Buckets can have different:

```text
sample count
gap structure
partial coverage
source-family evidence
```

Therefore:

```text
mean(bucket means)
```

would give equal weight to buckets rather than accepted time evidence.

Likewise:

```text
mean(all samples)
```

would give equal weight to samples even when their temporal intervals differ.

Neither is canonical Period Average.

---

# 15. Existing persisted Mbps ownership

Observation already calculates AP rate fields from counter deltas.

Existing rate logic:

```text
rate =
delta_bytes * 8
/
elapsed_seconds
/
1_000_000
```

Persisted reasons:

```text
ok
no_baseline
counter_reset
gap_too_large
invalid_elapsed
source_unavailable
```

`TRAFFIC-03` MUST reuse persisted accepted Mbps.

It MUST NOT recalculate Mbps from:

```text
wired_down_bytes
wired_up_bytes
lan_rx_bytes
lan_tx_bytes
```

---

# 16. Canonical Site sample for Period Statistics

For each canonical historical Site sample:

```text
sample_at =
cycle.finished_at
```

The sample belongs to one History bucket.

That bucket has one canonical selected source:

```text
wired
or
lan
```

For a complete Site sample, values are:

```text
D_i = Site Download Mbps
U_i = Site Upload Mbps
T_i = D_i + U_i
```

under the bucket-selected source family.

Only:

```text
complete Site samples
```

are accepted numeric Period Statistics samples.

---

# 17. Empty AP population remains valid zero evidence

Accepted complete-success AP dynamic cycle with:

```text
items_seen = 0
items_stored = 0
items_skipped = 0
```

remains:

```text
valid empty population
```

Canonical:

```text
Download = 0.0
Upload = 0.0
Total = 0.0
selected source = wired
```

This sample participates in Average/Peak as real zero evidence.

---

# 18. Period Average temporal interpretation — FINAL

Canonical v1 method identifier:

```text
right_endpoint_sample_hold_time_weighted.v1
```

This is a **time-aware interpretation model for sampled canonical Site throughput estimates**.

It MUST NOT be described as a proven source fact about the original AP counter interval.

Persisted AP Mbps is produced earlier by Observation from source-specific timestamps:

```text
wired_observed_at
lan_observed_at
```

and the corresponding previous source sample used by Observation rate calculation.

By contrast, `TRAFFIC-02-READ` places the canonical Historical **Site sample** at:

```text
sample_at = ap_dynamic cycle.finished_at
```

These are different temporal concepts.

For `TRAFFIC-03 v1`, ordered accepted canonical Site samples are interpreted as:

```text
S_1, S_2, ... S_n
```

where:

```text
t_i = canonical Site sample placement = cycle.finished_at
D_i = accepted Site Download Mbps estimate
U_i = accepted Site Upload Mbps estimate
T_i = D_i + U_i
F_i = canonical source family selected for that Site sample/bucket
```

For adjacent canonical Site samples:

```text
S_(i-1), S_i
```

define the **sample-hold weighting interval**:

```text
Δ_i = t_i - t_(i-1)
```

The right-hand sample value `S_i` is used as the throughput estimate for this weighting interval.

Canonical meaning:

```text
sample placement
= cycle.finished_at

weighting interval
= elapsed time between adjacent canonical Site sample placements

rate estimate assigned to interval
= right-hand accepted sampled Site rate
```

This is intentionally:

```text
time-aware average of sampled Site throughput estimates
```

It is NOT:

```text
reconstruction of the exact AP counter integration intervals
exact integration of wired_observed_at / lan_observed_at source ΔT
recalculation of Mbps from raw counters
proof that cycle.finished_at was the source rate endpoint
```

If exact source-counter interval integration is later required, it is a materially more complex read-layer contract and requires a separate architecture decision. It MUST NOT be silently substituted into this TASK.

---

# 19. Accepted sample-hold weighting interval

Weighting interval `i` is accepted only when:

```text
1. both adjacent Site samples are accepted complete Site samples;

2. t_i > t_(i-1);

3. Δ_i <= accepted Historical quality gap threshold;

4. F_i == F_(i-1);

5. both Download and Upload are finite non-negative accepted values;

6. Total is canonical and internally consistent.
```

If any condition fails:

```text
weighting interval is excluded
```

Its elapsed time is NOT:

```text
filled with zero
interpolated
forward-filled
back-filled
reconstructed from raw counters
```

The same exclusions remain deterministic inputs to Period Average quality/provenance.

---

# 20. Source-family transition behavior

If:

```text
F_(i-1) != F_i
```

the cross-transition interval is excluded from Period Average.

Reason:

```text
one weighted interval must not bridge two different canonical source families.
```

Both samples may still be individually valid for Peak.

Record:

```text
excluded_source_transition_interval_count
```

A LAN fallback sample is not invalid by itself.

Permanent:

```text
fallback != failure
```

But a source transition breaks interval continuity for Average v1.

---

# 21. Gap behavior

If:

```text
Δ_i > Historical quality gap threshold
```

the interval is excluded.

No:

```text
long gap → 0 Mbps
```

No:

```text
long gap → assume last rate continued
```

Record:

```text
excluded_gap_interval_count
```

---

# 22. Invalid elapsed behavior

If:

```text
Δ_i <= 0
```

the interval is not accepted.

Record:

```text
invalid_period_interval_count
```

This statistic-specific interval reason is separate from persisted AP
rate reason:

```text
invalid_elapsed
```

Both remain visible as separate evidence where applicable.

---

# 23. Boundary behavior

V1 does NOT extrapolate sampled Site rates beyond accepted canonical sample placements.

Therefore:

```text
[from_utc, first accepted sample)
```

is not automatically filled.

And:

```text
[last accepted sample, to_utc)
```

is not automatically filled.

Return factual:

```text
leading_unweighted_seconds
trailing_unweighted_seconds
```

These are provenance of:

```text
right_endpoint_sample_hold_time_weighted.v1
```

They do not claim exact missing AP source-counter interval duration.

They do not automatically make the result partial if the inherited Historical range contract is complete and no internal accepted weighting interval was lost.

---

# 24. Exact Average formula

Let:

```text
A =
set of accepted Period Average intervals
```

and:

```text
W =
Σ Δ_i  for i ∈ A
```

If:

```text
W > 0
```

then:

```text
Average Download =
Σ(D_i × Δ_i) / W

Average Upload =
Σ(U_i × Δ_i) / W

Average Total =
Σ(T_i × Δ_i) / W
```

Unit:

```text
Mbps
```

If:

```text
W = 0
```

then:

```text
Average Download = null
Average Upload = null
Average Total = null
```

Never zero merely because no interval exists.

---

# 25. Average Total invariant

Because all three averages use the exact same accepted interval set and weights:

```text
Average Total
≈
Average Download + Average Upload
```

within safe floating-point tolerance.

Serializer MUST validate this.

Browser MUST NOT compute `Average Total`.

---

# 26. What this Period Average means

Product-safe meaning:

```text
time-weighted mean of accepted sampled Site Network Throughput estimates
using right-endpoint sample-hold weighting
inside the selected Network range
```

It does NOT claim:

```text
WAN utilization
Internet utilization
billing utilization
SSID utilization
guest-only utilization
exact counter-interval integration
```

The source rate values remain persisted Observation-derived Mbps.

`TRAFFIC-03` changes only how accepted canonical Site samples are weighted over time for the Period Average product statistic.

---

# 27. Period Average model boundary — FINAL

Canonical v1 method:

```text
right_endpoint_sample_hold_time_weighted.v1
```

Canonical Historical Site sample placement remains:

```text
cycle.finished_at
```

Permanent distinction:

```text
Observation source-specific rate ΔT
!=
Historical canonical Site sample placement ΔT
```

The first is owned by Observation rate calculation using source-specific timestamps.

The second is the `TRAFFIC-03` sampled-rate weighting model used only to form a time-aware Period Average from already accepted Site Mbps estimates.

No raw counter re-derivation is permitted.

Any future requirement for exact AP source-counter interval integration is outside this TASK and requires a new reviewed read-layer contract.

---

# 28. Peak sample population

Peak uses:

```text
accepted complete Site samples
inside [from_utc,to_utc)
```

with the exact same bucket-selected source-family policy used by the Historical
semantic owner.

Missing/invalid samples are excluded.

No gap fill.

No interpolation.

---

# 29. Exact Peak formulas

If at least one accepted complete Site sample exists:

```text
Peak Download =
max(D_i)

Peak Upload =
max(U_i)

Peak Total =
max(T_i)
```

If none exists:

```text
Peak Download = null
Peak Upload = null
Peak Total = null
```

---

# 30. Peak Total is NOT directional-peak sum

Permanent:

```text
Peak Total
!=
Peak Download + Peak Upload
```

unless those maxima happen to occur in the same sample.

Canonical:

```text
Peak Total =
max(D_i + U_i)
```

at one accepted Site sample.

Browser never derives it.

---

# 31. Peak consistency invariants

For non-negative accepted evidence:

```text
Peak Total >= Peak Download

Peak Total >= Peak Upload

Peak Total <= Peak Download + Peak Upload
```

within safe numeric tolerance.

Serializer validates these invariants.

---

# 32. No Peak timestamp in TRAFFIC-03

The read layer may internally know which sample produced a peak.

The TRAFFIC-03 public DTO MUST NOT expose:

```text
peak_at
peak_bucket
peak_hour
peak_range
```

Reason:

```text
TRAFFIC-04 owns “When?”
```

This prevents accidental duplication of future Peak Load semantics.

---

# 33. Statistics status model

Canonical server Statistics result states in v1 are exactly:

```text
ok
partial
insufficient_data
```

There is no generic server `unavailable` Statistics DTO in v1.

Source/read/deadline/integrity failure is represented by the existing combined request error contract, normally sanitized `503`, rather than by fabricating a successful Statistics object.

Browser presentation may still have a local visual `unavailable/error` state when a request fails or the browser rejects a malformed Statistics sub-DTO.

---

# 34. Statistics `ok`

`ok` requires:

```text
History result status = ok

Average trio is numeric

Peak trio is numeric

no Statistics-specific accepted interval was excluded
because of:
- excessive gap
- source-family transition
- non-positive elapsed
```

LAN fallback is allowed.

A fallback bucket does not force partial by itself.

---

# 35. Statistics `partial`

`partial` applies when at least some trustworthy numeric Statistics evidence
exists, but the requested period is not fully comparable under the v1
Statistics contract.

Examples:

```text
History result is partial

Average numeric but one or more intervals excluded

Peak numeric but Average is null because no accepted weighting interval

source-family transition breaks one or more Average intervals

gap breaks one or more Average intervals
```

Numeric values MAY be shown.

They MUST have a visible:

```text
Partial
```

qualifier.

---

# 36. Statistics `insufficient_data`

Use:

```text
insufficient_data
```

when there is no accepted numeric Period Statistics evidence.

Canonical:

```text
accepted_peak_sample_count = 0
accepted_interval_count = 0
```

All six metrics:

```text
null
```

Not:

```text
0 Mbps
```

---

# 37. Peak-only partial case

If:

```text
accepted_peak_sample_count > 0

but

accepted_interval_count = 0
```

then:

```text
Peak Download/Upload/Total
may be numeric

Average Download/Upload/Total
= null

Statistics status
= partial
```

This is not `insufficient_data` because accepted Peak evidence exists.

---

# 38. Unavailable behavior belongs to request/application failure

V1 does not use `period_statistics.status="unavailable"` as a canonical successful server DTO state.

If Statistics cannot be safely calculated because of source/read/deadline/integrity failure:

```text
combined request follows existing Admin error mapping
```

Examples:

```text
429 concurrency_limit
503 query_deadline
503 source_unavailable
503 response_too_large
500 internal_error where applicable
```

A server serializer validation error is not converted to HTTP 200.

The browser may preserve previous accepted History/Statistics values with an explicit local failure state while Current and other Traffic panels remain operational.

---

# 39. Partial coverage — when values remain visible

No arbitrary percentage threshold such as:

```text
50%
80%
90%
```

is introduced.

Average values remain numeric when:

```text
accepted_interval_seconds > 0
```

Peak values remain numeric when:

```text
accepted_peak_sample_count > 0
```

If overall evidence is incomplete:

```text
status = partial
```

and coverage evidence remains visible.

This avoids turning partial-but-real evidence into fabricated unavailability.

---

# 40. Quality rule: missing != zero

Permanent:

```text
missing != 0

unknown != 0

insufficient != 0

unavailable != 0

gap != 0
```

Valid accepted:

```text
0.0 Mbps
```

remains a genuine numeric zero.

---

# 41. Existing source-quality reasons remain authoritative

Reuse existing historical quality evidence:

```text
no_baseline_count
counter_reset_count
gap_too_large_count
invalid_elapsed_count
source_unavailable_count
source_skew_excluded_sample_count
```

Also reuse:

```text
partial_cycle_count
failed_cycle_count
shutdown_cycle_count
abandoned_cycle_count
running_cycle_count
```

TRAFFIC-03 does not rename these into a new global enum.

---

# 42. Source-quality reason does not automatically equal Statistics failure

A non-zero reason count is evidence.

It forces Statistics degradation only when it materially reduces the accepted
Statistics evidence according to the canonical interval/sample rules.

For example:

```text
one no_baseline sample
```

does not automatically make the entire 7-day result unavailable.

If accepted interval continuity and History coverage remain safe, the value can
remain usable.

All reason counts remain visible in safe provenance.

---

# 43. Source-family fallback and transitions

Canonical:

```text
wired
= primary

lan
= fallback
```

Statistics may combine accepted evidence from different buckets over the
selected period.

But:

```text
one Average interval
must not cross wired ↔ lan transition
```

Peak may compare accepted numeric Site samples from either canonical family.

Expose:

```text
source_transition_count
excluded_source_transition_interval_count
```

No single false “Source = Wired” label for a range containing transitions.

---

# 44. Historical freshness wording

Historical Statistics MUST NOT invent:

```text
Fresh / Stale
```

threshold semantics absent from the historical contract.

Reuse factual:

```text
source_watermark_utc
source_age_seconds
available_from_utc
available_through_utc
```

An old requested range is not stale simply because it is old.

If current source lag creates coverage problems, existing History coverage/gap
semantics reflect them.

---

# 45. Statistics interval evidence DTO

Preferred immutable read-layer fields:

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

Exact interval-count semantics are frozen for v1.

First define:

```text
accepted_peak_sample_count =
number of time-ordered accepted complete canonical Site samples
that are eligible for Peak evaluation inside [from_utc,to_utc)
```

Then:

```text
candidate_interval_count =
max(accepted_peak_sample_count - 1, 0)
```

Thus a candidate interval is every adjacent pair in that ordered accepted-sample
sequence **before** interval-level exclusions are applied.

Every candidate interval is classified into exactly one mutually exclusive v1
accounting category using deterministic precedence:

```text
1. invalid_period_interval
2. source_transition
3. excessive_gap
4. accepted
```

Exact classification:

```text
if elapsed is non-finite or elapsed <= 0:
    invalid_period_interval_count += 1

elif source_family_left != source_family_right:
    excluded_source_transition_interval_count += 1

elif elapsed > accepted Historical quality gap threshold:
    excluded_gap_interval_count += 1

else:
    accepted_interval_count += 1
    accepted_interval_seconds += elapsed
```

Therefore the permanent accounting invariant is:

```text
candidate_interval_count
=
accepted_interval_count
+ invalid_period_interval_count
+ excluded_source_transition_interval_count
+ excluded_gap_interval_count
```

Reason counters do **not overlap** in v1. For example, an interval that both
crosses a source transition and exceeds the gap threshold is counted only as:

```text
source_transition
```

because source-transition precedence is above excessive-gap precedence.

This deterministic accounting contract MUST be implemented in the canonical
Historical read layer and MUST NOT be reclassified by Admin/browser code.

No raw AP rows.

No raw counters.

No SQL rows.

---

# 46. Interval coverage ratio

Canonical:

```text
interval_coverage_ratio =
accepted_interval_seconds / range_seconds
```

when:

```text
range_seconds > 0
```

Bound:

```text
0.0 <= ratio <= 1.0
```

This is evidence coverage.

It is NOT:

```text
Traffic Health %
Network quality score
availability SLA
```

---

# 47. New read-layer behavior required by TRAFFIC-03

This TASK DOES require a narrow extension of the accepted Historical read layer.

New behavior:

```text
1. preserve individual accepted complete Site samples
   inside the requested range before History bucket averaging;

2. order those samples by canonical sample_at;

3. calculate Period Average accepted interval evidence;

4. calculate six Period Statistics metrics;

5. return immutable Statistics DTO alongside History when explicitly requested;

6. perform this without creating a second historical semantic owner.
```

---

# 48. Where the new behavior belongs

Allowed ownership:

```text
HistoricalTrafficReadService
+
AnalyticsSourceGateway
```

Forbidden ownership:

```text
AdminQueryService formula
routes.py formula
serializer formula
browser formula
new TrafficStatisticsRepository
new TrafficStatisticsService outside Historical read owner
```

A dedicated immutable Statistics DTO/model inside `app/analytics` is allowed.

---

# 49. Preferred HistoricalTrafficReadService extension

FINAL preferred extension:

```python
get_site_history(
    ...,
    include_period_statistics=False,
)
```

When:

```text
include_period_statistics = false
```

return behavior and performance contract remain equivalent to current
TRAFFIC-02 History.

When:

```text
include_period_statistics = true
```

the same canonical range read additionally returns:

```text
period_statistics
```

No second call to `get_site_history()`.

No second read owner.

---

# 50. Preferred DTO extension

Preferred:

```text
HistoricalSiteTraffic
    ...
    period_statistics:
        HistoricalTrafficPeriodStatistics | None
```

Default:

```text
None
```

so current History callers remain compatible.

New immutable models may include:

```text
HistoricalTrafficPeriodStatistics
HistoricalTrafficPeriodAverage
HistoricalTrafficPeriodPeak
HistoricalTrafficPeriodIntervalEvidence
```

Exact class naming may be minimally consolidated.

---

# 51. One shared historical execution — mandatory performance architecture

When Statistics is requested, the mandatory invariant is **one shared historical product execution**, not an artificial requirement for exactly one SQL statement.

Required:

```text
one browser HTTP historical request

one HistoricalTrafficReadService call

one read-only SQLite snapshot / transaction boundary

one shared QueryDeadline

one Historical Traffic semantic owner

no second independent Statistics service call

no second independent Admin historical query path
```

Current PERF-01 implementation already performs multiple bounded projections inside one historical read, including conceptually:

```text
requested-range metadata/integrity work
History bucket aggregation
source-boundary / watermark lookup
attempt/quality projections
```

Therefore FINAL does NOT require one literal physical SQL/CTE execution.

Forbidden:

```text
History service call
+
independent Statistics service call

or

History historical semantic owner
+
second Statistics historical semantic owner
```

Any Statistics-specific SQL projection MUST:

```text
remain requested-range bounded
share the same read-only snapshot
share the same QueryDeadline
reuse exactly the accepted Historical validation semantics
reuse exactly the accepted source-family selection semantics
preserve PERF-01 range bounding
```

Preferred:

```text
avoid an additional complete full-range validation pass when practical
```

but physical SQL pass count is an implementation/performance detail proven by query-plan evidence and benchmark, not a semantic contract.

---

# 52. SourceGateway implementation direction

Preferred implementation:

```text
extend the existing requested-range bounded Historical SourceGateway path
with a Statistics projection inside the same read-only snapshot and QueryDeadline
```

The implementation may use more than one bounded SQL statement when that is clearer or faster.

Permanent requirements:

```text
no all-history validation to answer 24h/7d
no second independent historical service call
no second independent source-selection implementation
no divergent Site-sample acceptance rules
```

Statistics projection MUST reuse exactly the accepted semantics for:

```text
candidate cycles
integrity validation
complete Site sample acceptance
wired/LAN source selection
source skew exclusion
rate reason validity
range boundaries
```

Whether the optimal implementation shares CTE text, stages a bounded in-memory intermediate inside the read service, or executes an additional bounded SQL projection is decided by measured EXPLAIN/query-plan and benchmark evidence.

No schema/index change is authorized by this FINAL.

---

# 53. PERF-01 anti-regression invariant

Statistics extension MUST preserve:

```text
requested-range bounded candidate selection
```

introduced by PR #88.

Global source boundary/watermark lookup may remain the existing bounded mechanism.

Statistics MUST NOT require:

```text
validate all 180 days
to answer 24h
```

or:

```text
validate all 180 days
to answer 7d
```

---

# 54. No new acquisition

No:

```text
new collector
new Omada endpoint polling
new Observation worker
new polling cadence
```

Native Omada:

```text
dashboard/traffic-activities
dashboard/traffic-distribution
```

remain:

```text
VALIDATION / REFERENCE
```

not product sources.

---

# 55. No new persistence

No:

```text
Traffic Statistics DB
rollup table
cache table
materialized view
Redis
JSON cache
background aggregate worker
schema migration
```

If query-on-read fails the accepted performance gate:

```text
STOP
→ return measurements
→ separate architecture review
```

Do not silently add persistence.

---

# 56. API architecture decision — NO separate Statistics request

FINAL decision:

```text
DO NOT add
GET /traffic/statistics
in v1.
```

Reason:

Current Traffic page already loads:

```text
Current Network Throughput
+
History
```

A separate Statistics request would create:

```text
Current
+
History expensive historical scan
+
Statistics expensive historical scan
```

on initial load/range change.

Current shared Admin concurrency default is limited.

Production already observed a legitimate:

```text
429 concurrency_limit
```

during rapid History switching.

Therefore adding a third independent range request is unnecessary risk.

---

# 57. Preferred combined endpoint contract

Keep existing endpoint:

```text
GET /admin/api/v1/sites/<site_id>/traffic/history
```

Current request:

```text
?range=24h
or
?range=7d
```

When Statistics product is enabled, frontend requests:

```text
?range=24h&include=statistics

?range=7d&include=statistics
```

This explicitly asks the existing historical application contract to include
the Period Statistics projection.

---

# 58. Backward-compatible History-only API

Request without:

```text
include=statistics
```

continues to return current History contract.

Even if Statistics feature is enabled, an authorized History-only consumer MAY
request:

```text
range=24h
```

and receive:

```text
History only
```

This preserves a stable current History API.

---

# 59. `include` validation

Allowed only:

```text
include=statistics
```

Single value only.

Forbidden:

```text
include=statistics&include=statistics
include=foo
include=statistics,other
```

Unknown parameters remain:

```text
400 invalid_request
```

---

# 60. Statistics feature-disabled include behavior

If:

```text
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=false
```

then authorized request:

```text
?range=24h&include=statistics
```

returns:

```text
404 not_found
```

after normal authentication/Site authorization/master History boundary.

Normal:

```text
?range=24h
```

continues to return current History.

---

# 61. Combined success response

When Statistics is requested and safely calculated:

```json
{
  "result": {
    "status": "ok",
    "range": { "...": "existing History range contract" },
    "buckets": [],
    "coverage": {},
    "quality": {},
    "period_statistics": {
      "status": "ok",
      "metric_version": "network_traffic_period_statistics.v1",
      "average_method": "right_endpoint_sample_hold_time_weighted.v1",
      "peak_method": "max_accepted_complete_site_sample.v1",
      "unit": "Mbps",
      "average": {},
      "peak": {},
      "interval_evidence": {}
    }
  }
}
```

No independent Statistics range object is allowed.

Outer History range remains the canonical shared Network range.

---

# 62. Period Statistics DTO — FINAL

Canonical DTO:

```json
{
  "status": "ok",
  "metric_version": "network_traffic_period_statistics.v1",
  "average_method": "right_endpoint_sample_hold_time_weighted.v1",
  "peak_method": "max_accepted_complete_site_sample.v1",
  "unit": "Mbps",

  "average": {
    "download_mbps": 1.23,
    "upload_mbps": 0.11,
    "total_mbps": 1.34
  },

  "peak": {
    "download_mbps": 8.42,
    "upload_mbps": 1.21,
    "total_mbps": 9.10
  },

  "interval_evidence": {
    "range_seconds": 86400,
    "candidate_interval_count": 2860,
    "accepted_interval_count": 2858,
    "accepted_interval_seconds": 85680.0,
    "interval_coverage_ratio": 0.9916666667,
    "excluded_gap_interval_count": 1,
    "excluded_source_transition_interval_count": 1,
    "invalid_period_interval_count": 0,
    "accepted_peak_sample_count": 2861,
    "leading_unweighted_seconds": 30.0,
    "trailing_unweighted_seconds": 30.0
  }
}
```

Values above are illustrative.

Frozen method identities are mandatory because outer History already exposes a different aggregation identity:

```text
History:
mean_of_complete_site_rate_samples

Period Average:
right_endpoint_sample_hold_time_weighted.v1

Period Peak:
max_accepted_complete_site_sample.v1
```

`metric_version` does not replace these exact method identifiers.

---

# 63. No duplicate range in Statistics DTO

Statistics MUST NOT return an independently calculated:

```text
from_utc
to_utc
evaluated_at
range_id
```

that could drift from outer History.

It inherits:

```text
result.range
```

Serializer validates Statistics against that same range context.

---

# 64. Statistics safe serializer ownership

Extend existing:

```text
app/admin_web/historical_traffic_serialization.py
```

rather than creating a second independent Historical semantics serializer.

History projection remains canonical.

When Statistics is requested:

```text
serializer validates and projects period_statistics
```

When not requested:

```text
current History response remains unchanged.
```

---

# 65. Statistics serializer — primitive and method validation

Require exact canonical server DTO fields:

```text
status:
ok | partial | insufficient_data

metric_version:
network_traffic_period_statistics.v1

average_method:
right_endpoint_sample_hold_time_weighted.v1

peak_method:
max_accepted_complete_site_sample.v1

unit:
Mbps
```

The server canonical DTO does NOT use a generic serializer-created `unavailable` recovery state in v1.

All numeric Mbps values:

```text
finite
non-negative
or null where status contract allows
```

Counts:

```text
integer >= 0
```

Durations:

```text
finite >= 0
```

Ratio:

```text
finite
0..1
```

Any unknown/mismatched method identifier is a semantic contract violation and MUST fail closed.

---

# 66. Statistics serializer — Average invariants

Average trio must be:

```text
all numeric
or
all null
```

If numeric:

```text
accepted_interval_count > 0
accepted_interval_seconds > 0
```

Validate:

```text
Average Total
≈
Average Download + Average Upload
```

within safe tolerance.

---

# 67. Statistics serializer — Peak invariants

Peak trio must be:

```text
all numeric
or
all null
```

If numeric:

```text
accepted_peak_sample_count > 0
```

Validate:

```text
Peak Total >= Peak Download
Peak Total >= Peak Upload
Peak Total <= Peak Download + Peak Upload
```

within safe tolerance.

---

# 68. Statistics serializer — status consistency

Canonical server Statistics states are exactly:

```text
ok
partial
insufficient_data
```

## ok

```text
average numeric
peak numeric
outer History status = ok
excluded_gap_interval_count = 0
excluded_source_transition_interval_count = 0
invalid_period_interval_count = 0
```

## partial

At least one trustworthy numeric metric family exists and one or more completeness conditions fail.

Examples:

```text
History partial
Average interval exclusions
Peak numeric but Average is null because no accepted weighting interval because no accepted interval
```

## insufficient_data

```text
average all null
peak all null
accepted_interval_count = 0
accepted_peak_sample_count = 0
```

There is no serializer self-healing transition to a server DTO `unavailable` state.

---

# 69. Statistics serializer — interval arithmetic

Validate the exact v1 interval accounting contract:

```text
candidate_interval_count
=
max(accepted_peak_sample_count - 1, 0)
```

and:

```text
candidate_interval_count
=
accepted_interval_count
+ invalid_period_interval_count
+ excluded_source_transition_interval_count
+ excluded_gap_interval_count
```

Reason counters are mutually exclusive under the frozen precedence:

```text
invalid_period_interval
→ source_transition
→ excessive_gap
→ accepted
```

Also validate:

```text
accepted_interval_seconds
<=
range_seconds

interval_coverage_ratio
≈
accepted_interval_seconds / range_seconds
```

within safe tolerance.

And:

```text
leading_unweighted_seconds <= range_seconds
trailing_unweighted_seconds <= range_seconds
```

No negative values.

---

# 70. Outer History cross-field consistency

Statistics uses the same outer:

```text
result.range
result.coverage
result.quality
```

At minimum validate consistency with:

```text
source_transition_count
source_watermark_utc
source-age evidence
no-baseline/reset/gap/source-unavailable reasons
```

where the same evidence is reused.

Do not create two contradictory quality totals.

---

# 71. Server fail-closed Statistics integrity

Server-side canonical Statistics calculation and serialization are **fail closed**.

If Analytics/read layer produces a malformed or cross-field-invalid Statistics DTO:

```text
serializer MUST NOT catch it
and synthesize:
period_statistics.status = unavailable
HTTP 200
```

That behavior could hide a semantic implementation defect.

Required server behavior:

```text
Statistics calculation/serialization integrity violation
→ existing AdminQueryUnavailable mapping
→ combined historical request = 503 source_unavailable
   or the existing sanitized unavailable mapping used by the route
```

No malformed canonical Statistics payload is admitted as HTTP 200.

A future explicit canonical Analytics/Application `unavailable` state is allowed only if separately defined with a safe reason contract; it MUST NOT be manufactured from serializer validation failure.

Browser behavior is separate:

```text
HTTP 200 payload
History sub-contract validates
period_statistics sub-contract fails browser validation
```

may produce:

```text
History presentation remains valid/rendered
Statistics presentation fails local
previous accepted Statistics may remain visible with error state
```

This browser defensive isolation does not weaken the server fail-closed contract.

---

# 72. Shared query/deadline failure

If the single combined Historical read exceeds the shared QueryDeadline:

```text
503 query_deadline
```

applies to the whole request.

Reason:

```text
History and Statistics share one source execution.
```

Do not return fake cached Statistics.

Do not retry in the panel independently.

---

# 73. Existing HTTP security chain

Required:

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
if include=statistics:
    WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED
        ↓
AdminQueryService
        ↓
admin.read.overview
        ↓
HistoricalTrafficReadService
```

No new security model.

---

# 74. API mappings

Reuse existing History mappings.

```text
200
History safe result
History safe result + Statistics status ok / partial / insufficient_data

400 invalid_request
bad range/include/query shape

401 authentication_required

403 site_forbidden

404 not_found
Traffic/History/Statistics product gate disabled as applicable

429 concurrency_limit
Retry-After

503 query_deadline

503 source_unavailable

503 response_too_large

500 internal_error
sanitized
```

---

# 75. No new Statistics endpoint — permanent v1 statement

Browser MUST NOT call:

```text
/admin/api/v1/sites/<site_id>/traffic/statistics
```

in this v1 architecture.

If future architectural needs require independent Statistics fetching, that
must be separately reviewed because it changes:

```text
request count
range evaluation identity
query concurrency
performance ownership
```

---

# 76. One exact range/evaluation identity

Because History and Statistics share one response:

```text
History.range.id
=
Statistics selected/applied Network range

History.from/to/evaluated_at
=
Statistics calculation boundaries
```

No cross-request timing drift.

This is a major reason for the combined API decision.

---

# 77. Feature flag decision

FINAL decision:

```text
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=false
```

Repository default:

```text
false
```

Settings key:

```text
web_admin_traffic_statistics_enabled
```

Admin config field:

```text
traffic_statistics_enabled: bool
```

---

# 78. Feature dependency

For v1:

```text
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=true
```

requires:

```text
WEB_ADMIN_ENABLED=true
WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
```

Reason:

```text
Statistics v1 intentionally shares:
- existing History historical request
- existing History product range execution
```

This is a v1 rollout/execution dependency.

It does NOT make History the permanent semantic owner of the Network range.

---

# 79. Statistics flag controls product exposure only

Statistics flag MUST NOT:

```text
start HistoricalTrafficReadService
stop HistoricalTrafficReadService
start Observation
stop Observation
change collection cadence
change retention
change Analytics runtime state
```

Canonical:

```text
product flag
!=
service lifecycle switch
```

---

# 80. Statistics disabled behavior

With:

```text
Traffic=true
History=true
Statistics=false
```

required:

```text
Traffic page available
Current panel available
History panel available
shared Network range available

Statistics markup absent
Statistics JS consumer inactive

History request stays current:
?range=24h|7d

NO include=statistics
NO Statistics calculation

zero additional Statistics HTTP requests

direct include=statistics
→ 404
```

History behavior/performance remains current baseline.

---

# 81. Statistics enabled behavior

With:

```text
Traffic=true
History=true
Statistics=true
```

required:

```text
Period Statistics markup visible

existing History execution requests:
?range=<selected>&include=statistics

one historical HTTP request

response contains:
History
+
Period Statistics

Current panel unaffected
```

---

# 82. Dormant production deploy

Subordinate flag enables:

```text
deploy new code
with
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=false
```

Then:

```text
dormant post-check
```

Then only after separate Owner action:

```text
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=true
```

Then:

```text
production product acceptance
```

No production activation is granted by this FINAL.

---

# 83. UI panel

Add one separate visual panel/card:

```text
Period Statistics
```

Recommended semantic structure:

```text
Period Statistics
How much Network Throughput was observed?

Applied range · Last 24 hours
Coverage · Complete / Partial / Insufficient / Unavailable

AVERAGE
Download
Upload
Total

PEAK
Download
Upload
Total
```

Unit:

```text
Mbps
```

---

# 84. UI — all six metrics mandatory

Visible:

```text
Average Download
Average Upload
Average Total

Peak Download
Peak Upload
Peak Total
```

No optional hiding of Total when Statistics is enabled.

If the Statistics request/presentation is unavailable or a metric is null under the canonical status contract:

```text
—
```

not omitted.

---

# 85. UI — no second range selector

Statistics panel MUST NOT add:

```text
24h / 7d controls
```

It consumes:

```text
CaptivPortalTrafficNetworkRange
```

The only visible Network range selector remains the shared one.

Future range-sensitive panels reuse it.

---

# 86. UI — applied range

Statistics displays its last successful:

```text
applied range
```

from:

```text
validated response.range.id
```

Not from mutable selected state.

Example:

```text
Selected = 7d
Applied = 24h
```

is a valid transitional/failure state.

Old 24h numbers MUST remain labelled:

```text
Last 24 hours
```

until 7d succeeds.

---

# 87. Selected vs applied range state machine

Example:

```text
applied = 24h
user selects 7d
```

Immediately:

```text
shared selected Network range = 7d
```

If History coordinator execution is admitted:

```text
History + Statistics loading selected 7d
old applied 24h evidence may remain visible
```

Success:

```text
validated response.range.id = 7d
History applied = 7d
Statistics applied = 7d
```

Failure:

```text
selected remains 7d
applied remains 24h
old values remain explicitly 24h
failure visible
```

---

# 88. Coordinator backoff false-return behavior

Current:

```text
refreshPanel(...,{manual:true})
```

may decline a new execution during:

```text
nextEligibleAt
```

backoff.

If refresh is not admitted:

```text
selected range may change
applied Statistics remains unchanged
no fake Loading state
no claim that a Statistics request started
```

A neutral message MAY say:

```text
Selected 7d · displaying Last 24 hours until refresh
```

but MUST NOT say:

```text
Loading 7d
```

without an actual coordinator execution.

---

# 89. Rapid supersession

Example:

```text
applied 24h
→ select 7d
→ 7d request starts
→ before completion select 24h
```

Existing coordinator generation/AbortController owns supersession.

Statistics data is inside the same History response.

Therefore:

```text
stale/superseded 7d response
MUST NOT update Statistics
```

Final applied result comes only from:

```text
latest successful non-superseded response
```

---

# 90. Loader range capture

Current History loader captures selected range at execution start.

Keep:

```text
requestRange = rangeContext.selected()
```

local to that execution.

Statistics rendering trusts only:

```text
validated response.range.id
```

Never:

```text
mutable outer selected variable
```

for applied statistics identity.

---

# 91. Frontend orchestration decision

Statistics is a **visual panel**, but v1 does NOT register an independent
network-loading panel with the coordinator.

Reason:

```text
independent registerPanel(load)
→ independent request
→ duplicate expensive historical query
```

Instead:

```text
existing network-traffic-history coordinator execution
→ receives one combined historical response
→ History render path consumes History sub-contract
→ Statistics render path consumes period_statistics sub-contract
```

This is intentional query coalescing.

---

# 92. Coordinator ownership remains singular

No new:

```text
setInterval
setTimeout polling loop
AbortController
Retry-After logic
visibilitychange
pagehide
global Refresh listener
request generation owner
```

Statistics inherits request lifecycle from the existing History coordinator
execution.

---

# 93. Initial load

If Statistics enabled:

```text
Traffic page opens
→ current History panel registration performs its one initial execution
→ request includes include=statistics
→ History + Statistics receive same 24h response
```

No third product request.

Current panel still performs its own normal current request.

Thus expected normal initial Traffic request count remains conceptually:

```text
Current request
+
one historical range request
```

not:

```text
Current
+
History
+
Statistics
```

---

# 94. Shared range change

Current shared range change currently refreshes only History because no other
independent range request exists.

After TRAFFIC-03:

```text
range change
→ still one History coordinator refresh
→ response includes History + Statistics
```

Thus both visual panels update from one canonical range execution.

---

# 95. Global Refresh

Existing:

```text
refreshAll({manual:true})
```

continues to own global Refresh.

Current:

```text
Current Network Throughput
```

reloads.

History execution reloads:

```text
History + Statistics
```

No Statistics-specific Refresh listener.

---

# 96. Panel-local Statistics presentation failure

There is no canonical successful server DTO:

```text
period_statistics.status = unavailable
```

in v1.

Two failure classes remain distinct.

## A. Combined server request fails

Examples:

```text
429 concurrency_limit
503 query_deadline
503 source_unavailable
503 serializer/integrity failure
```

Then no new History/Statistics response is accepted.

Browser may preserve previously accepted History/Statistics presentation with an explicit local error state. Current remains unaffected.

## B. HTTP 200 History validates but browser rejects `period_statistics` sub-DTO

Then:

```text
History presentation may remain valid/rendered
Statistics presentation fails local
previous accepted Statistics may remain visible with error qualifier
Current remains unaffected
```

Permanent:

```text
Statistics presentation failure
!=
Traffic page failure
```

---

# 97. Shared historical request failure

If the one combined request returns:

```text
429
503 query_deadline
503 source_unavailable
```

then both History and Statistics lack a new accepted response.

Existing accepted data may remain visible with explicit failure state.

Current panel remains isolated.

Home remains isolated.

---

# 98. No browser canonical calculation

Browser MUST NOT:

```text
average History buckets
average History samples
calculate interval weights
calculate Peak
calculate Average Total
calculate Peak Total
fill gaps
select source family
calculate UTC range boundaries
```

Browser may only:

```text
validate
format
display
```

---

# 99. UI numeric formatting

Visible Mbps:

```text
two decimal places
```

Examples:

```text
0.0 → 0.00 Mbps
1.237 → 1.24 Mbps
null → —
```

Formatting does not alter canonical value.

---

# 100. UI quality indication

Minimum visible:

```text
Applied range
Statistics status
History coverage
interval coverage
source watermark / age
```

If Partial, visible:

```text
Partial
```

not tooltip-only.

Critical missing/gap evidence must not exist only in a tooltip.

---

# 101. UI source transitions

If:

```text
source_transition_count > 0
```

surface compact evidence such as:

```text
Source transitions · 1
```

If an interval was excluded:

```text
Average excludes 1 cross-source interval
```

or equivalent concise wording.

Do not imply LAN fallback means error.

---

# 102. UI no peak time

Do not add:

```text
Peak at 18:42
Peak hour
Peak period
```

even if internally easy.

Those belong to TRAFFIC-04.

---

# 103. UI no chart

TRAFFIC-03 v1 is KPI/statistics presentation.

No new:

```text
Statistics chart
sparkline
histogram
heatmap
```

History chart already exists.

This keeps TASK scope narrow.

---

# 104. Stable DOM hooks — proposed

```text
traffic-statistics-panel
traffic-statistics-heading

traffic-statistics-state
traffic-statistics-state-title
traffic-statistics-state-message

traffic-statistics-applied-range
traffic-statistics-coverage
traffic-statistics-interval-coverage
traffic-statistics-watermark

traffic-statistics-average-download
traffic-statistics-average-upload
traffic-statistics-average-total

traffic-statistics-peak-download
traffic-statistics-peak-upload
traffic-statistics-peak-total
```

No private range control hooks.

---

# 105. Frontend Statistics DTO validation

Before Statistics presentation rendering, browser validates:

```text
period_statistics object

status:
ok | partial | insufficient_data

metric_version:
network_traffic_period_statistics.v1

average_method:
right_endpoint_sample_hold_time_weighted.v1

peak_method:
max_accepted_complete_site_sample.v1

unit:
Mbps

average trio valid
peak trio valid
interval evidence valid

outer range id:
24h | 7d
```

Malformed `period_statistics` sub-DTO in an otherwise valid HTTP 200 payload:

```text
Statistics presentation fail-local
History presentation remains usable if its own contract validates
```

Browser MUST NOT rewrite the malformed Statistics object into a synthetic valid server state.

---

# 106. Product copy

Recommended helper meaning:

```text
Average and peak Site Network Throughput from accepted persisted AP evidence.
Missing intervals are not treated as zero.
May include local/service traffic and is not Internet/WAN-only traffic.
```

Do not use:

```text
Internet speed
Internet average
WAN peak
guest traffic
```

---

# 107. Performance — architecture objective

Primary v1 objective:

```text
TRAFFIC-03 must not create another expensive independent historical path.
```

Permanent execution contract:

```text
one selected range
one server evaluation
one HistoricalTrafficReadService execution
one read-only SQLite snapshot / shared QueryDeadline
one HTTP historical response
History + Statistics
no second independent Historical/Statistics path
```

Additional requested-range-bounded SQL projections inside that one read snapshot
are explicitly allowed under §§51–52/117. Physical SQL statement/pass count is a
performance implementation detail, not an architecture invariant.

---

# 108. Shared deadline contract

`TRAFFIC-03` creates:

```text
NO History/Statistics-specific QueryDeadline
```

Use existing:

```text
AdminQueryExecutionControls
```

Current/default:

```text
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS = 10
```

If approved shared Admin configuration changes later:

```text
Statistics inherits it
```

No local override.

---

# 109. Browser timeout contract

Use existing shared Traffic request timeout:

```text
WEB_ADMIN_TRAFFIC_REQUEST_TIMEOUT_SECONDS
```

Current/default:

```text
20 seconds
```

No:

```text
WEB_ADMIN_TRAFFIC_STATISTICS_TIMEOUT_SECONDS
```

is introduced.

---

# 110. No deadline increase as performance fix

Forbidden response to slow Statistics:

```text
10s → 20s backend deadline
```

without separate architecture approval.

Also forbidden:

```text
increase browser timeout
increase query concurrency
```

as a silent fix.

First response to measured failure:

```text
STOP
→ profile/query-plan evidence
→ architecture review
```

---

# 111. Response-size budget

Statistics is O(1):

```text
six numeric metrics
+
small interval evidence
```

It does not increase bucket count.

Existing authoritative response bound:

```text
WEB_ADMIN_MAX_RESPONSE_BYTES
```

remains unchanged.

If combined 7d response exceeds configured bound:

```text
STOP
→ evidence
→ architecture review
```

Do not increase the limit silently.

---

# 112. No new concurrency slot

Because there is no separate Statistics HTTP request:

```text
TRAFFIC-03 does not add an independent AdminQueryExecutionControls slot
```

to normal page load.

This is a required acceptance invariant.

---

# 113. Existing 429 behavior

Production has already demonstrated that rapid historical switching can
legitimately encounter:

```text
429 concurrency_limit
```

followed by later successful request.

TRAFFIC-03 must not promise that 429 can never occur.

Required instead:

```text
Statistics adds zero independent request
Statistics adds zero independent retry
existing coordinator/backoff remains authoritative
selected/applied state remains truthful
```

---

# 114. Performance benchmark — controlled matrix

Central Lab MUST benchmark four variants on the **same immutable production-size read-only snapshot**:

```text
H24 = History-only 24h
S24 = History+Statistics 24h

H7  = History-only 7d
S7  = History+Statistics 7d
```

For comparison, each range uses the same evaluation class and preferably one fixed `evaluated_at_utc` anchor so History-only and History+Statistics operate on identical `[from_utc,to_utc)` boundaries.

Minimum measured runs:

```text
10 runs per variant
40 measured runs total minimum
```

Run ordering MUST reduce warm-cache/order bias.

The exact p95 algorithm is the frozen type-7 linear interpolation contract in
§115 and MUST be used identically for all four variants and all p95 comparisons.

Required controlled order per range:

```text
paired interleaving with alternating first variant

pair 1: H → S
pair 2: S → H
pair 3: H → S
...
```

until each variant has at least 10 measured executions.

24h and 7d may be benchmarked in separate controlled blocks.

Before measured runs, an unmeasured warm-up is allowed only if applied equally to both compared variants and documented.

---

# 115. Performance measurements and hard PASS/FAIL gates

For each of `H24`, `S24`, `H7`, `S7`, record:

```text
run count
success count
p50 duration
p95 duration
max duration
serialized response bytes
bucket count
HTTP/application status
query_deadline count
source-integrity failure count
Statistics status for S variants
snapshot fingerprint
fixed evaluation anchor / range boundaries
```

Hard functional gates for every variant:

```text
runs >= 10
0 query_deadline
0 source-integrity failures
0 unexpected 5xx
bucket_count = 288 for 24h
bucket_count = 672 for 7d
response bytes < configured WEB_ADMIN_MAX_RESPONSE_BYTES
source snapshot remains read-only/unchanged
```

Statistics variants additionally require every successful result to contain:

```text
metric_version = network_traffic_period_statistics.v1
average_method = right_endpoint_sample_hold_time_weighted.v1
peak_method = max_accepted_complete_site_sample.v1
Statistics status in:
ok | partial | insufficient_data
```

## Deterministic p95 calculation

For every measured duration set (`H24`, `S24`, `H7`, `S7`), Central Lab MUST
calculate p95 using the same frozen linear-interpolation / type-7 style contract.

Given `N` measured durations:

```text
1. sort durations ascending

2. rank = (N - 1) * 0.95

3. lower = floor(rank)
   upper = ceil(rank)

4. if lower == upper:
       p95 = values[lower]

   otherwise:
       p95 = values[lower]
             + (rank - lower)
               * (values[upper] - values[lower])
```

Zero-based indexes are used after sorting.

This exact algorithm applies to:

```text
H24
S24
H7
S7
```

and to every p95 value used in History-only vs History+Statistics
baseline/candidate regression comparisons.

Do not substitute nearest-rank, inclusive/exclusive library defaults, or another
percentile method.

`max` remains the literal maximum observed measured run:

```text
max = values[N - 1]
```

after ascending sort.

## Absolute safety headroom relative to shared 10s QueryDeadline

For BOTH `S24` and `S7`:

```text
p95 <= 8.0 seconds
max  <= 9.0 seconds
```

Therefore the measured combined path preserves at least:

```text
2.0s p95 headroom
1.0s observed-max headroom
```

against the 10s shared deadline.

Equality at 8.0/9.0 is accepted; any higher value is FAIL.

---

# 116. Allowed Statistics regression relative to History-only

Absolute headroom alone is not sufficient. Combined Statistics must also remain bounded relative to History-only on the same snapshot/evaluation class.

For each range independently:

```text
Δp50 = S.p50 - H.p50
Δp95 = S.p95 - H.p95
Δmax = S.max - H.max
```

PASS requires ALL:

```text
Δp50 <= max(0.50s, 20% of H.p50)

Δp95 <= max(0.75s, 25% of H.p95)

Δmax <= max(1.00s, 25% of H.max)
```

AND the absolute gates from the previous section:

```text
S.p95 <= 8.0s
S.max <= 9.0s
```

Negative deltas are allowed and simply mean the combined measured run was faster.

The gate is evaluated separately for:

```text
24h
7d
```

Any single failed relative or absolute condition is:

```text
PERF FAIL
```

No deadline/timeout/concurrency increase is allowed as remediation inside this TASK.

---

# 117. Query-plan and physical-pass evidence

Central Lab MUST capture safe query-plan evidence for every new Statistics SQL projection and the existing bounded Historical projections materially affected by the implementation.

Confirm:

```text
requested-range candidate work remains bounded
existing relevant indexes are used
no accidental all-history candidate validation is introduced
```

Physical SQL statement/pass count is **not** a hard architecture number.

It is accepted when:

```text
all projections share one HistoricalTrafficReadService execution
share one read-only SQLite snapshot / QueryDeadline
reuse accepted validation/source-selection semantics
meet the measurable benchmark gates
```

A new index/schema change is NOT authorized.

If query-plan/performance evidence shows it is necessary:

```text
STOP
→ architecture review
```

Do not modify schema/indexes silently.

---

# 118. Read-only immutability

Performance/acceptance must prove:

```text
Observation DB row counts unchanged
schema/user_version unchanged
source fingerprint unchanged where practical
```

Statistics remains read-only.

---

# 119. Feature configuration plumbing

FINAL feature-flag contract adds repository config:

```text
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=false
```

Pipeline:

```text
app/config.py
→ app/settings.py
→ app/admin_web/config.py
→ AdminWebConfig
→ render_admin_page()
→ traffic.html / frontend
```

---

# 120. Config validation

Exact:

```text
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=true
```

requires:

```text
WEB_ADMIN_ENABLED=true
WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
```

Invalid hierarchy:

```text
AdminWebConfigError
→ fail closed for Admin feature
```

Do not silently turn Statistics off.

---

# 121. Expected implementation scope — Analytics

Expected MODIFY:

```text
app/analytics/models.py
app/analytics/historical_traffic.py
app/analytics/source_gateway.py
```

Possible narrow MODIFY if new DTO exports are needed:

```text
app/analytics/__init__.py
```

Expected unchanged:

```text
app/analytics/runtime.py
app/analytics/config.py
app/analytics/wireless.py
```

Same Historical service object is already composed.

---

# 122. Expected implementation scope — Admin/config

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

app/admin_web/static/admin.js
app/admin_web/static/admin.css
app/admin_web/templates/admin/traffic.html
```

Expected unchanged:

```text
app/admin_web/runtime.py
app/admin_web/traffic_network_ranges.py
app/admin_web/current_traffic_serialization.py
app/admin_web/templates/admin/base.html
```

If a listed expected-unchanged production file becomes necessary:

```text
STOP
→ factual reason
→ architecture review
```

---

# 123. Observation expected unchanged

Do NOT change:

```text
app/observations/ap_worker.py
app/observations/repository.py
app/observations/schema
Observation config
collector cadence
rate formula
```

The existing persisted Mbps calculation is authoritative input.

---

# 124. Other subsystems expected unchanged

No changes to:

```text
Current State
Visit Lifecycle
Visitor Registry
Auth
CAPPORT
Pending Session Cleaner
OmadaProvider/controllers
Loki/Grafana/Alloy
systemd
Nginx
requirements/dependencies
```

---

# 125. Proposed focused Analytics tests

Preferred new test file:

```text
tests/analytics/test_historical_traffic_statistics.py
```

At minimum prove:

```text
24h and 7d exact range behavior

Average uses elapsed-time weighting

Average != simple sample mean
on unequal intervals

Average != average History bucket averages

gap interval excluded

source transition interval excluded

interval-reason accounting is mutually exclusive with precedence:
invalid_period_interval → source_transition → excessive_gap → accepted

overlapping-failure interval fixture proves deterministic precedence; for example
a cross-source interval that also exceeds the gap threshold increments only
excluded_source_transition_interval_count, not excluded_gap_interval_count

candidate_interval_count = max(accepted_peak_sample_count - 1, 0)

candidate_interval_count equals accepted + all three exclusive rejection counts

valid zero participates as zero

missing evidence is not zero

Average Total == Average Download + Average Upload

Peak accepted samples only

Peak Total != directional peak sum
when peaks occur at different samples

Peak zero is valid
when all accepted samples are zero

Peak-only partial case

insufficient case

partial History → partial Statistics

source fallback alone is allowed

source transition provenance counted

no-baseline/reset/gap/invalid/source-unavailable
quality remains visible
```

---

# 126. Focused interval-weight example

Required deterministic proof:

Samples:

```text
t0:
D=1 Mbps

t1 = t0 + 30s:
D=1 Mbps

t2 = t1 + 90s:
D=3 Mbps
```

With all accepted and same source:

```text
time-weighted Average Download
=
(1×30 + 3×90) / 120
=
2.5 Mbps
```

Simple sample mean:

```text
(1 + 3)/2
=
2.0 Mbps
```

Test MUST prove canonical result is:

```text
2.5
```

not 2.0.

Equivalent Upload/Total proof required.

---

# 127. Focused gap test

Example:

```text
Δ > quality gap threshold
```

must prove:

```text
interval excluded
accepted_interval_seconds does not include it
Average denominator does not include it
no zero inserted
status partial when usable evidence remains
```

---

# 128. Focused source transition test

Example:

```text
wired sample
→ next accepted sample in LAN-selected bucket
```

must prove:

```text
cross-transition interval excluded from Average

both samples remain eligible for Peak

source transition count remains visible

no wired/LAN AP mixing occurs
```

---

# 129. Focused Peak separation from TRAFFIC-04

Test data where:

```text
Peak Download occurs at sample A
Peak Upload occurs at sample B
Peak Total occurs at sample C
```

must prove:

```text
all three values correct

no peak timestamp exposed in Statistics DTO
```

---

# 130. Admin/API focused tests

Preferred new:

```text
tests/admin_web/test_traffic_statistics.py
```

At minimum:

```text
Statistics flag default false

Statistics=true + Admin=false
→ config invalid

Statistics=true + Traffic=false
→ config invalid

Statistics=true + History=false
→ config invalid

Stats disabled:
normal History still 200
include=statistics → 404

Stats enabled:
History-only request still valid
include=statistics → 200 with period_statistics

duplicate include → 400
unknown include → 400
unknown query parameter → 400

Site isolation/security unchanged

shared deadline passed

no separate Statistics service/query request
```

---

# 131. Safe serializer focused tests

At minimum:

```text
six metrics exact projection

valid zero

all-null insufficient

partial numeric

malformed canonical Statistics DTO rejected fail-closed

serializer validation error maps through AdminQueryUnavailable / 503

invalid Average Total rejected

invalid Peak Total invariants rejected

NaN / inf / negative rejected

interval coverage ratio mismatch rejected

accepted seconds > range seconds rejected

candidate_interval_count != max(accepted_peak_sample_count - 1, 0) rejected

interval accounting identity mismatch rejected

accepted intervals > candidates rejected

status/metric presence mismatch rejected

outer range identity reused
```

---

# 132. Frontend focused tests

Preferred:

```text
tests/admin_web/test_traffic_statistics_frontend.py
```

At minimum prove:

```text
no second range selector

no second coordinator

no second registerPanel network loader

no direct fetch

no private timer

no AbortController

no visibility/pagehide handler

Stats enabled causes existing History request:
&include=statistics

Stats disabled preserves current History request shape

initial response renders six metrics

0.0 → 0.00 Mbps
null → —

partial visibly labelled

insufficient visibly labelled

browser Statistics presentation failure does not corrupt already validated History
```

---

# 133. Shared range frontend tests

Prove:

```text
default selected Network range = 24h

History and Statistics applied range come from same response

select 7d
→ one historical refresh

Current panel does not reload solely due range change

no private Statistics selected range state

failed request:
selected 7d
applied Statistics remains 24h

backoff false-return:
no fake Loading
no fake applied change
```

---

# 134. Rapid supersession frontend test

Required:

```text
24h applied
→ select 7d
→ 7d combined request in flight
→ select 24h
```

Prove:

```text
old 7d generation superseded/aborted by existing coordinator

stale 7d response cannot update:
History
or
Statistics

last successful 24h response owns both applied states
```

---

# 135. No duplicate request test

Critical performance regression test:

```text
Traffic page with:
Current
History
Statistics
```

must perform:

```text
Current request
+
ONE historical request
```

not:

```text
Current
+
History
+
Statistics
```

This is a mandatory v1 architectural acceptance.

---

# 136. Coder testing ownership

Coder may run only:

```text
new/modified focused TRAFFIC-03 tests
minimal relevant module tests
compile checks
git diff --check
```

Coder MUST NOT independently run:

```text
full Analytics suite
full Admin suite
full repository pytest
Central Lab V6
official baseline/candidate differential
```

Those remain Central Lab-owned.

---

# 137. Proposed Coder focused command

Final exact command should be rebound to actual test files after implementation.

Expected shape:

```bash
python -m pytest -q \
  tests/analytics/test_historical_traffic_statistics.py \
  tests/admin_web/test_traffic_statistics.py \
  tests/admin_web/test_traffic_statistics_frontend.py
```

Static:

```bash
PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc \
python -m compileall -q app/analytics app/admin_web

git diff --check
```

No full suite by Coder.

---

# 138. Central Lab targeted regression boundary

Owner + Tech Lead / Central Lab must run exact-candidate regression covering:

```text
TRAFFIC-03 focused tests

TRAFFIC-02-PERF-01 range-bounding regressions

TRAFFIC-02-READ HistoricalTrafficReadService regressions

TRAFFIC-02 History API/serializer/frontend

TRAFFIC-00 coordinator/Foundation

TRAFFIC-01 Current Network Throughput

shared Admin config/pages/query/routes

Home Current Traffic relevant shared-boundary regression
if shared config/routes are touched
```

---

# 139. Central Lab TRAFFIC-02-PERF invariant

Must specifically prove PR #88 protection remains:

```text
requested-range candidate bound

cycle started before range but finished inside preserved

future/out-of-range cycles do not alter requested buckets

global coverage boundaries/watermark remain correct

no full-history candidate validation regression
```

---

# 140. Central Lab Statistics performance gate

Central Lab official PERF gate is exactly the controlled matrix and thresholds in §§114–117.

Required variants:

```text
H24 History-only 24h
S24 History+Statistics 24h
H7  History-only 7d
S7  History+Statistics 7d
```

Minimum:

```text
10 measured runs per variant
```

Required recorded evidence:

```text
p50
p95
max
response bytes
bucket count
Statistics status
query_deadline count
source-integrity failure count
snapshot fingerprint
evaluation/range identity
```

Hard combined headroom:

```text
S24/S7 p95 <= 8.0s
S24/S7 max <= 9.0s
```

Relative regression gates:

```text
Δp50 <= max(0.50s, 20% of H.p50)
Δp95 <= max(0.75s, 25% of H.p95)
Δmax <= max(1.00s, 25% of H.max)
```

Also mandatory:

```text
0 query_deadline
0 source-integrity failures
0 timeout/deadline tuning
```

Central Lab can therefore issue an objective PASS/FAIL without subjective wording such as “approaches the deadline”.

---

# 141. Central Lab concurrency/browser acceptance

Controlled Traffic page:

```text
Current visible
History visible
Statistics visible
```

Confirm:

```text
normal initial historical requests = 1

range change historical requests = 1 per admitted generation

no independent Statistics retry

429 remains safe/local if legitimately returned

next eligible refresh can succeed

Statistics does not cause extra concurrency pressure
```

---

# 142. Central Lab full gate

Official PASS/FAIL remains:

```text
Owner + Tech Lead / Central Lab
```

Use current verified runner at candidate execution time.

Evidence:

```text
exact baseline
exact candidate
targeted regression
full approved regression
strict regressions
compatibility baseline
compileall
git diff --check
exact-artifact immutability
```

---

# 143. Central Lab runner decision

FINAL decision:

```text
DO NOT change the canonical Central Lab runner
merely because ordinary new tests are added.
```

New tests should be included through normal current test discovery/selection
practice.

Runner change is justified only if:

```text
current runner structurally cannot execute a newly required acceptance class
```

and then it requires:

```text
separate explicit testing-governance update/review
```

not silent modification inside TRAFFIC-03.

---

# 144. Production rollout

If later implemented/accepted/merged:

Stage 1:

```text
deploy code
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=false
```

Verify dormant:

```text
service active
Current works
History works
no Statistics markup
no Statistics include request
History performance unchanged
```

Stage 2 — separate Owner authorization:

```text
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=true
```

Then restart/reload according to current deployment contract.

---

# 145. Production acceptance

After separate activation:

```text
Statistics panel visible

six metrics visible

range = current shared Network range

24h works
7d works

one combined historical request

Average/Peak values safe

Partial/Insufficient states truthful

Current remains operational
History remains operational

no new 503 query_deadline pattern

no excess 429 attributable to an extra Stats request
```

---

# 146. Rollback

Statistics-specific rollback:

```text
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=false
```

Expected:

```text
Statistics markup disappears
History returns to History-only request
Current unchanged
History unchanged
HistoricalTrafficReadService remains available
Observation unchanged
```

No need to disable:

```text
WEB_ADMIN_TRAFFIC_ENABLED
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED
```

for Statistics-only rollback.

---

# 147. Operational telemetry — FINAL contract

Existing:

```text
admin.traffic_history_query_completed
```

remains the historical request event.

When Statistics is requested, safely add:

```text
statistics_requested = true
statistics_status
```

Optional additional event:

```text
admin.traffic_statistics_evaluated
```

may contain only:

```text
request_id
site_id
range_id
statistics_status
duration_ms or statistics_phase_duration_ms if measured safely
accepted_interval_count
accepted_interval_seconds
accepted_peak_sample_count
```

No:

```text
SQL
DB path
secrets
raw AP rows
```

A separate telemetry event is not required if existing History telemetry safely
carries sufficient evidence.

---

# 148. Architecture Decisions — FINAL summary

1. `TRAFFIC-03` contains six mandatory Mbps metrics.
2. Average Total and Peak Total are mandatory.
3. Network Traffic only.
4. `HistoricalTrafficReadService` remains sole Historical semantic owner.
5. Period Average method is `right_endpoint_sample_hold_time_weighted.v1`.
6. `cycle.finished_at` is Site sample placement, not the original AP rate ΔT.
7. Period Average is a time-aware average of sampled Site throughput estimates.
8. It is not exact source-counter interval integration.
9. Period Average never averages History bucket means.
10. Period Average never equally averages all samples.
11. Period Average never recalculates Mbps from counters.
12. Cross-source weighting intervals are excluded.
13. Excessive-gap weighting intervals are excluded.
14. Missing time is not zero.
15. Peak method is `max_accepted_complete_site_sample.v1`.
16. Peak uses accepted complete Site samples only.
17. Peak Total is max per-sample Total, not sum of directional peaks.
18. TRAFFIC-03 exposes no peak time.
19. Shared Network range 24h/7d is reused.
20. No second range selector.
21. No separate Statistics HTTP request in v1.
22. Existing History endpoint uses opt-in `include=statistics`.
23. One browser request + one HistoricalTrafficReadService call + one read-only snapshot/shared QueryDeadline serves History+Statistics.
24. Literal SQL pass count is a measured implementation detail, not an invariant.
25. No second independent Statistics historical service/path.
26. Server Statistics DTO statuses are `ok | partial | insufficient_data`.
27. Malformed server Statistics DTO fails closed to existing Admin unavailable mapping/503.
28. Browser malformed Stats sub-DTO may fail-local presentation only.
29. Statistics uses subordinate product flag, default false.
30. No timeout/deadline increase.
31. No new DB/cache/rollup.
32. No second coordinator/scheduler.
33. Combined performance must meet exact §§114–117 Central Lab gates.

---

# 149. Exact scope

In scope:

```text
narrow HistoricalTrafficReadService Statistics extension

range-bounded shared SourceGateway aggregation

immutable Period Statistics DTO

six metrics

Statistics status/evidence contract

History endpoint include=statistics extension

Statistics subordinate flag

safe Admin serializer extension

Period Statistics panel

shared selected/applied range behavior

shared History request lifecycle

focused tests

Central Lab performance/regression contract
```

---

# 150. Explicit non-goals

Not in TRAFFIC-03:

```text
TRAFFIC-04 Peak Load Period

peak timestamp
busiest bucket
busiest hour
busiest period

TRAFFIC-05 Traffic by AP

TRAFFIC-06 AP Traffic Share

TRAFFIC-07 Online Guests

TRAFFIC-08 Completed Guest Session Traffic

TRAFFIC-09 consolidated Evidence panel

30-day UI exposure

Traffic Heatmap

Period Comparison

Guest Session Traffic

new collector

new Omada polling

new Traffic DB

schema migration

cache/rollup without measured necessity

Home redesign

Web Designer redesign
```

---

# 151. API contract — summary

Current canonical endpoint remains:

```text
GET /admin/api/v1/sites/<site_id>/traffic/history
```

History only:

```text
?range=24h
?range=7d
```

History + Statistics:

```text
?range=24h&include=statistics
?range=7d&include=statistics
```

No separate:

```text
/traffic/statistics
```

in v1.

---

# 152. UI states — summary

Statistics visual/presentation states:

```text
loading
ready
partial
insufficient_data
request/presentation unavailable
refreshing previous applied evidence
selected/applied mismatch
shared request busy/timeout failure
```

Permanent:

```text
zero != missing
partial != complete
selected range != applied range
```

---

# 153. Tech Lead review decisions incorporated

Tech Lead review result:

```text
ARCHITECTURE DIRECTION: PASS
REWRITE REQUIRED: NO
MANDATORY TARGETED CORRECTIONS: 5
STATUS AFTER INCORPORATION: FINAL
```

The five corrections are now closed as follows.

## 1. Period Average temporal model

Accepted FINAL identifier:

```text
right_endpoint_sample_hold_time_weighted.v1
```

`cycle.finished_at` is canonical Site sample placement only; it is not claimed as the original Observation source-rate ΔT.

## 2. Historical execution/performance invariant

Accepted FINAL requirement:

```text
one browser HTTP historical request
one HistoricalTrafficReadService call
one read-only SQLite snapshot/shared QueryDeadline
no second independent Historical/Statistics path
```

Literal SQL pass count is not fixed.

## 3. Serializer fail-closed behavior

Malformed/cross-field-invalid canonical server Statistics DTO:

```text
NO HTTP 200 self-healing
→ fail closed
→ existing AdminQueryUnavailable / 503 mapping
```

Browser sub-DTO defensive failure remains presentation-local.

## 4. Algorithm identities

Frozen DTO identifiers:

```text
average_method = right_endpoint_sample_hold_time_weighted.v1
peak_method = max_accepted_complete_site_sample.v1
```

## 5. Measurable PERF gate

FINAL §§114–117 define:

```text
4 benchmark variants
>=10 runs each
paired controlled interleaving
absolute p95/max headroom
relative p50/p95/max regression limits
0 query_deadline
0 source-integrity failures
```

No unresolved Tech Lead architectural correction remains in this FINAL.

---

# 154. Risks

## R1 — Period Average semantic ambiguity

Risk:

```text
sample-hold weighting misrepresented as exact AP counter-interval integration
```

Mitigation:

```text
frozen average_method identifier
explicit source-timestamp vs Site-sample-placement distinction
deterministic unequal-interval tests
no raw counter re-derivation
```

## R2 — Source transition weighting

Risk:

```text
one interval bridges wired and LAN semantics
```

Mitigation:

```text
exclude cross-source weighting interval
record provenance
```

## R3 — PERF-01 regression

Risk:

```text
Statistics projection causes unbounded/all-history candidate work
```

Mitigation:

```text
requested-range bounded projections
shared read-only snapshot/QueryDeadline
query-plan evidence
objective production-size benchmark
```

## R4 — Query concurrency

Risk:

```text
extra Statistics request produces 429 pressure
```

Mitigation:

```text
no separate Statistics request
one combined History execution
```

## R5 — Combined request increases History latency

Mitigation:

```text
Statistics flag default false
History-only vs combined paired benchmark
p95/max absolute headroom
relative regression limits
no deadline increase
STOP on failure
```

## R6 — Statistics implementation defect hidden as partial availability

Mitigation:

```text
server serializer fails closed
malformed canonical DTO cannot become synthetic HTTP 200 unavailable
browser presentation isolation remains defensive only
```

---

# 155. Stop conditions

Implementation MUST STOP and return evidence if it requires:

```text
changing Observation rate formula

changing Observation schema

changing source-family selection semantics

mixing wired/LAN between APs in one bucket

calculating Average from History bucket averages

calculating Average/Peak in browser

recalculating Mbps from raw counters

adding a separate heavy Statistics HTTP query

reverting PR #88 range bounding

increasing Admin query deadline

increasing Traffic timeout as the fix

increasing concurrency limit as the fix

adding cache/rollup/new DB

adding Omada calls

adding 30d UI range

adding peak timestamps/busiest-period semantics

changing Traffic coordinator public contract
```

Also STOP if current main materially changes before implementation begins.

---

# 156. FINAL review closure

Owner + Tech Lead review has accepted the architecture after the five mandatory corrections incorporated above.

Closed decisions:

1. Six mandatory metrics accepted.
2. Total metrics mandatory.
3. Average method = `right_endpoint_sample_hold_time_weighted.v1`.
4. `cycle.finished_at` treated only as canonical Site sample placement.
5. No claim of exact AP counter-interval integration.
6. No counter re-derivation.
7. Source transition weighting interval exclusion accepted.
8. Gap weighting interval exclusion accepted.
9. Boundary non-extrapolation accepted.
10. Peak formulas accepted.
11. Peak method = `max_accepted_complete_site_sample.v1`.
12. Peak Total is independent max of Total samples.
13. No peak timestamps exposed.
14. Partial numeric policy accepted.
15. No arbitrary coverage percentage cutoff.
16. Existing History endpoint `include=statistics` accepted.
17. No separate Statistics endpoint.
18. One HTTP request / one HistoricalTrafficReadService call / one read-only snapshot/shared deadline.
19. Literal SQL pass count is not fixed.
20. Statistics flag default false.
21. Statistics→History flag dependency accepted for v1.
22. Shared Network range reuse accepted.
23. Passive Statistics frontend consumer model accepted.
24. No new coordinator.
25. Shared 10s deadline unchanged.
26. Server serializer fail-closed behavior accepted.
27. Exact algorithm IDs accepted.
28. Objective PERF gates accepted by this FINAL.
29. Coder/Central Lab ownership unchanged.
30. Central Lab runner remains unchanged by default.
31. Production activation remains separate Owner-controlled action.

This FINAL is coder-ready only after a separate explicit Owner implementation authorization.

---

# 157. FINAL status

```text
TASK:
TASK-TRAFFIC-03 — Period Statistics

STATUS:
FINAL — TECH LEAD REVIEW INCORPORATED

BOUND TO:
main@473df4646970292f7bcea74d5d69fce03dba642a

TREE:
ba145de1bba0aa30d2f87fc769c0d8e5f9fc8f54

BASELINE IMPACT REVIEW:
NO DRIFT SINCE DRAFT
NO RUNTIME REBIND CONFLICT

CANONICAL OWNER:
HistoricalTrafficReadService

AVERAGE METHOD:
right_endpoint_sample_hold_time_weighted.v1

PEAK METHOD:
max_accepted_complete_site_sample.v1

METRICS:
Average Download
Average Upload
Average Total
Peak Download
Peak Upload
Peak Total

RANGES:
24h / 7d shared Network range

NEW ACQUISITION:
NO

NEW DB / SCHEMA:
NO

SEPARATE STATISTICS HTTP REQUEST:
NO

FEATURE DEFAULT:
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=false

SHARED QUERY DEADLINE:
10s default / unchanged

PERF COMBINED HARD GATE:
p95 <= 8.0s
max <= 9.0s
plus relative regression limits in §§114–117

IMPLEMENTATION AUTHORIZATION:
NOT GRANTED BY THIS FINAL
REQUIRES SEPARATE OWNER AUTHORIZATION

MERGE AUTHORIZATION:
NOT GRANTED

PRODUCTION DEPLOYMENT:
NOT GRANTED

PRODUCTION ACTIVATION:
NOT GRANTED
```

Next permitted process step:

```text
Owner reviews FINAL
→ separate explicit implementation authorization if approved
→ Coder implementation on exact current main recheck
→ focused handoff
→ Central Lab official acceptance
→ Owner-controlled merge/deploy/activation
```

No implementation may begin solely because this FINAL exists.

---

