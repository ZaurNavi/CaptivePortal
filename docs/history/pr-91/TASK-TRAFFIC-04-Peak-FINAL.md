# TASK-TRAFFIC-04 — Peak — FINAL

**Проект:** CaptivPortal  
**Area:** Admin Console → Traffic  
**Canonical Roadmap item:** `TRAFFIC-04 — Peak Load Period`  
**Dependencies:** `TRAFFIC-00`, `TRAFFIC-01`, `TRAFFIC-02-READ`, `TRAFFIC-02`, `TASK-TRAFFIC-02-PERF-01`, `TRAFFIC-03`  
**Тип:** architecture / Historical read extension + Admin API projection + passive Traffic panel  
**Статус:** `FINAL — TECH LEAD REVIEW INCORPORATED / FOR SHORT OWNER + TECH LEAD FINAL CHECK`  
**Implementation authorization:** `NOT GRANTED BY THIS FINAL; REQUIRES SEPARATE OWNER AUTHORIZATION`  
**Code / patch / commit / push / PR / merge:** `NOT AUTHORIZED BY THIS FINAL`  
**Production deployment / activation:** `NOT AUTHORIZED BY THIS FINAL`  
**Подготовлен:** 2026-08-30

---

# 0. Executive decision

`TRAFFIC-04` является temporal companion к уже принятому:

```text
TRAFFIC-03 — Period Statistics
```

Permanent semantic split:

```text
TRAFFIC-03
→ «Сколько?»

Average Download / Upload / Total
Peak Download / Upload / Total
```

```text
TRAFFIC-04
→ «Когда?»

When were the accepted Peak samples observed?
When was the busiest canonical History bucket?
What was the busiest fully comparable 60-minute period?
```

V1 product title:

```text
Peak Load
```

Primary visible outcomes:

```text
Peak Download
value + observed timestamp

Peak Upload
value + observed timestamp

Peak Total
value + observed timestamp

Busiest History Bucket
bucket range + Average Total Mbps

Busiest 60 Minutes
60-minute range + Average Total Mbps
```

Unit for throughput values:

```text
Mbps
```

Canonical owner remains:

```text
Observation persisted AP history
        ↓
AnalyticsSourceGateway
        ↓
HistoricalTrafficReadService
        ↓
existing combined Historical Admin application/API
        ↓
existing Traffic History coordinator execution
        ↓
Peak Load panel
```

This FINAL fixes:

```text
NO new historical semantic owner
NO separate Peak HTTP request
NO separate Peak frontend loader
NO second range selector
NO new collector
NO Omada polling
NO direct Admin/Browser → Omada
NO new DB/schema/index
NO cache/rollup
NO deadline/timeout/concurrency increase
NO traffic-volume MB/GB calculation
```

Feature rollout proposal:

```text
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=false
```

with v1 dependency:

```text
Peak=true
requires:
Admin=true
Traffic=true
History=true
Statistics=true
```

Implementation remains forbidden until a separate explicit Owner implementation authorization.

---

# 1. Current repository recheck

Repository state was re-fetched before issuing this FINAL.

Current repository:

```text
origin/main =
e1a278c3e2c131b0762d7134485dcf3208eac11e

tree =
a529faae4ded9e3f6c5cb72c5a9c6d9cfcc9df3e
```

Current main is:

```text
Merge PR #90
Docs: reconcile TRAFFIC-03 production state and publication governance
```

PR #90 is documentation/governance only.

Its first parent is the accepted runtime merge:

```text
b92efbfabb38f912550526bc5a3d1f2f1a8ae4d6
```

with accepted/runtime tree:

```text
1d8b94590848f9505e45e653384dd8a7c18d4339
```

Therefore current repository/runtime relationship is:

```text
repository main
=
e1a278c3... docs/governance

current runtime implementation represented by main
=
b92efbfa... / tree 1d8b9459...
```

Impact review:

```text
PR #90 runtime drift:
NONE

TRAFFIC-04 architecture rebind conflict:
NONE
```

Before any eventual implementation:

```text
re-fetch origin/main
pin exact SHA/tree again
```

If newer main touches Traffic/Analytics runtime contracts, STOP for impact review.

---

# 2. Current production truth from accepted project state

Owner + Assistant Tech Lead report:

```text
TRAFFIC-03
PRODUCTION ACCEPTANCE PASS / CLOSED

PR #89
MERGED

production commit
b92efbfabb38f912550526bc5a3d1f2f1a8ae4d6

production tree
1d8b94590848f9505e45e653384dd8a7c18d4339

WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=true
```

History and Statistics:

```text
24h PASS
7d PASS
shared applied range PASS
browser/product acceptance PASS
```

This FINAL does not alter that accepted production state.

---

# 3. Canonical process invariant and exact pre-publication candidate path

Permanent project promotion order:

```text
Coder patch
    ↓
Windows Central Lab
targeted / regression / exact candidate tree verification
    ↓
production-compatible Linux Central Lab
SAME exact candidate tree
production-size immutable snapshot
official PERF
    ↓
Controlled Browser Acceptance
SAME exact candidate tree
    ↓
ALL mandatory gates PASS
    ↓
Accepted candidate
    ↓
publication commit / GitHub PR
    ↓
merge
    ↓
Git artifact
    ↓
Production deployment FROM GIT
    ↓
separate feature activation
    ↓
Production Product / Browser Acceptance
```

This exact path is a TASK-specific mandatory acceptance contract.

Canonical pre-publication transport may be:

```text
patch
controlled Lab artifact
local bundle
controlled worktree materialization
```

A publication commit or GitHub feature branch is NOT required to transport the
candidate into either Central Lab.

Explicit:

```text
Linux PERF Lab MUST NOT require
publication commit / GitHub feature branch
```

A local `LAB ONLY` commit/tree may be created only to materialize and fingerprint
the exact candidate for immutable Lab testing. It is:

```text
local
not pushed
not publication identity
not deployable identity
```

Before mandatory Linux PERF, record:

```text
exact candidate tree identity
production-size snapshot SHA256
production-size snapshot byte size
```

After mandatory Linux PERF, record again:

```text
exact candidate tree identity
production-size snapshot SHA256
```

Required:

```text
candidate tree before PERF
=
candidate tree after PERF

snapshot SHA before PERF
=
snapshot SHA after PERF
```

The same exact candidate tree then proceeds to Controlled Browser Acceptance.
Any candidate mutation after a mandatory gate invalidates prior acceptance for
that candidate and requires rerunning affected mandatory gates.

Forbidden normal path:

```text
push candidate to Git
→ fetch on production host
→ perform missing acceptance
```

Also permanent for this TASK:

```text
production /opt/CaptivePortal
!=
Linux Central Lab
```

Production is not a substitute for missing targeted/regression/PERF/browser
acceptance.

Therefore:

```text
targeted PASS
regression PASS
PERF FAIL
→ candidate NOT ACCEPTED
→ normal publication NOT AUTHORIZED

controlled browser FAIL
→ candidate NOT ACCEPTED
→ normal publication NOT AUTHORIZED
```

All mandatory `TRAFFIC-04` gates are pre-publication unless explicitly labelled
as later Production Product Acceptance.

Implementation / publication / merge / deployment remain separately
unauthorized by this FINAL.

---

# 4. Roadmap binding

Canonical Traffic Roadmap defines:

```text
TRAFFIC-03
= «Сколько?»

TRAFFIC-04
= «Когда?»
```

Roadmap TRAFFIC-04 direction:

```text
busiest canonical bucket
busiest hour
timestamp/range
average Total throughput during busiest hour
```

Preferred selection metric:

```text
Total accepted Network Throughput
=
Download + Upload
```

when compatible accepted evidence exists for both directions.

This TASK preserves that Roadmap intent while also exposing the timestamps
deliberately withheld from the accepted TRAFFIC-03 Peak DTO.

---

# 5. Product domain

This TASK belongs exclusively to:

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

Forbidden labels/meanings:

```text
Internet Traffic
WAN Traffic
Internet Usage
WAN Usage
Billing Traffic
Guest Traffic
Guest Session Traffic
SSID Traffic
Zefer_Parki Traffic
Traffic Volume
MB transferred
GB transferred
```

No MB/GB volume metric is introduced.

---

# 6. Canonical source remains unchanged

Permanent path:

```text
Observation persisted AP history
→ AnalyticsSourceGateway
→ HistoricalTrafficReadService
→ Admin
→ Browser
```

Native Omada historical endpoints remain:

```text
VALIDATION / REFERENCE
```

not product source.

Forbidden:

```text
Browser → Omada
Admin route → Omada
Peak panel → Omada
Peak panel → Observation DB
new Peak repository
new Peak collector
```

---

# 7. Current Historical semantic owner

Current accepted service:

```python
HistoricalTrafficReadService.get_site_history(...)
```

already owns:

```text
Site validation
[from,to)
evaluated_at
bucket selection
bounded output
source-family selection
complete Site sample acceptance
gap semantics
source skew
coverage
quality
watermark
shared deadline propagation
Period Statistics
```

Current canonical Site sample placement:

```text
sample_at =
ap_dynamic cycle.finished_at
```

This remains unchanged.

---

# 8. Current History contract

Current ranges:

```text
24h
7d
```

Canonical History buckets:

```text
24h → 5-minute → 288
7d  → 15-minute → 672
```

Bucket aggregation:

```text
mean_of_complete_site_rate_samples
```

Each bucket already exposes:

```text
bucket_start_utc
bucket_end_utc

download_mbps
upload_mbps
total_mbps

status
selected_source
source provenance
sample/gap evidence
```

Therefore `busiest canonical bucket` can be selected from canonical History
buckets inside the same Historical semantic owner.

Browser MUST NOT perform that selection.

---

# 9. Current TRAFFIC-03 Peak contract

Accepted Period Statistics method:

```text
peak_method =
max_accepted_complete_site_sample.v1
```

Peak sample population:

```text
accepted complete canonical Site samples
inside [from_utc,to_utc)
```

Current formulas:

```text
Peak Download = max(D_i)
Peak Upload   = max(U_i)
Peak Total    = max(T_i)
```

where:

```text
T_i = D_i + U_i
```

Missing/invalid evidence is excluded.

No interpolation.

No zero fill.

Current TRAFFIC-03 deliberately does NOT expose peak timestamps.

That temporal identity belongs to this TASK.

---

# 10. Key reuse conclusion

The current read path already knows the accepted sample population required for
Peak values.

Therefore:

```text
TRAFFIC-04 DOES NOT need
a second Peak calculation population.
```

Required extension is primarily:

```text
retain/select temporal identity
for the already accepted maxima

+
derive Roadmap busiest-period facts
from the same accepted requested-range evidence.
```

---

# 11. Product structure — FINAL

One new Traffic card:

```text
Peak Load
```

Recommended functional sections:

```text
PEAK MOMENTS

Download
39.01 Mbps
Observed at 30 Aug 14:32:10

Upload
15.45 Mbps
Observed at 30 Aug 17:05:41

Total
40.41 Mbps
Observed at 30 Aug 14:32:10


BUSIEST PERIOD

Busiest History Bucket
14:30 → 14:35
Average Total 18.24 Mbps

Busiest 60 Minutes
14:07 → 15:07
Average Total 7.82 Mbps
```

Numbers/timestamps above are illustrative only.

---

# 12. Peak moment is an observed canonical Site sample

Canonical Peak event means:

```text
an accepted complete canonical Site sample
whose selected metric equals the maximum accepted value
for that metric inside the selected Network range
```

For each family:

```text
Download Peak event
Upload Peak event
Total Peak event
```

A Peak event is NOT:

```text
the exact physical instant when a packet-rate spike happened
the original AP counter interval end
a raw Omada timestamp
a History bucket midpoint
a browser chart point invented from pixels
```

---

# 13. Peak timestamp semantics

Canonical timestamp:

```text
peak sample_at =
cycle.finished_at
```

UI language should prefer:

```text
Observed at
```

rather than:

```text
Traffic occurred exactly at
```

because:

```text
cycle.finished_at
=
canonical Historical Site sample placement

NOT
source-specific AP rate ΔT endpoint
```

No raw source-specific counter interval is reconstructed.

---

# 14. Separate timestamps for Download / Upload / Total

FINAL decision:

```text
three independent Peak event timestamps
```

Required:

```text
Peak Download:
value + sample_at

Peak Upload:
value + sample_at

Peak Total:
value + sample_at
```

Reason:

```text
directional maxima can occur at different accepted Site samples
```

Permanent:

```text
Peak Total timestamp
is NOT assumed equal to
Peak Download timestamp
or Peak Upload timestamp
```

---

# 15. Peak Total identity

Canonical remains:

```text
Peak Total =
max(D_i + U_i)
```

at one accepted complete Site sample.

Forbidden:

```text
Peak Total value =
Peak Download + Peak Upload

Peak Total timestamp =
timestamp of larger directional Peak
```

---

# 16. Cross-surface identity with TRAFFIC-03

For one exact:

```text
Site
selected range
[from,to)
evaluated_at
Historical read execution
```

required:

```text
TRAFFIC-04 Peak Download value
=
TRAFFIC-03 Peak Download value

TRAFFIC-04 Peak Upload value
=
TRAFFIC-03 Peak Upload value

TRAFFIC-04 Peak Total value
=
TRAFFIC-03 Peak Total value
```

This is a mandatory serializer/read-layer invariant.

TRAFFIC-04 adds temporal identity.

It does NOT create alternative Peak values.

---

# 17. Peak tie-breaking

Equal maximum may occur more than once.

Canonical v1 comparison:

```text
exact accepted canonical numeric value equality
```

No tolerance-based tie grouping is introduced.

For each metric:

```text
occurrence_count =
number of accepted complete Site samples
whose metric equals the exact canonical Peak value
```

Canonical chosen event:

```text
earliest sample_at
inside [from,to)
```

Method identifier:

```text
earliest_peak_sample_at.v1
```

---

# 18. Why earliest tie wins

Earliest is selected because it is:

```text
deterministic
stable
easy to test
independent of browser sorting
not dependent on ingestion row order
```

UI MAY indicate:

```text
First of 3 equal peaks
```

when:

```text
occurrence_count > 1
```

No list of every tied timestamp in v1.

---

# 19. Peak event source provenance

Each Peak event should carry:

```text
selected_source =
wired | lan
```

corresponding to the canonical source family of the bucket/sample context.

A Peak event is valid under either accepted family.

LAN fallback does not make the event invalid.

No AP-level source mixing is introduced.

---

# 20. Peak event method identity

Frozen:

```text
peak_value_method =
max_accepted_complete_site_sample.v1

peak_tie_break_method =
earliest_peak_sample_at.v1

sample_timestamp_semantics =
cycle_finished_at
```

These identifiers MUST appear in the canonical Peak Load DTO.

---

# 21. Busiest canonical History bucket

Roadmap-required semantic owner:

```text
HistoricalTrafficReadService
```

Candidate bucket is eligible only when:

```text
bucket.status = complete

download_mbps is numeric
upload_mbps is numeric
total_mbps is numeric
```

Selection metric:

```text
bucket.total_mbps
```

Canonical:

```text
Busiest History Bucket =
eligible complete canonical History bucket
with maximum total_mbps
```

---

# 22. Why partial History buckets are not eligible for canonical busiest bucket

A partial History bucket may contain a valid numeric sample mean.

However selecting a maximum across partial and complete buckets can create
non-comparable competition because the partial bucket represents less accepted
period evidence.

Therefore v1 canonical busiest bucket uses:

```text
complete buckets only
```

If no complete numeric bucket exists:

```text
busiest_bucket.status = insufficient_data
```

The panel may still show valid Peak moments.

---

# 23. Busiest bucket tie-breaking

If multiple eligible buckets have exactly equal maximum:

```text
earliest bucket_start_utc wins
```

Expose:

```text
occurrence_count
```

Method identity:

```text
max_complete_history_bucket_total_mean.v1
```

Tie method:

```text
earliest_bucket_start.v1
```

---

# 24. Busiest bucket output

Canonical fields:

```text
status

bucket_start_utc
bucket_end_utc

average_total_mbps

selected_source

occurrence_count

method
tie_break_method
```

`average_total_mbps` is the existing canonical History bucket:

```text
total_mbps
```

It is NOT:

```text
TRAFFIC-03 Period Average
```

and must be labelled as:

```text
bucket average
```

where explanation is needed.

---

# 25. Busiest 60 Minutes — Roadmap “busiest hour”

V1 user-facing wording:

```text
Busiest 60 Minutes
```

This is intentionally more exact than ambiguous:

```text
Busiest Hour
```

Canonical period width:

```text
3600 seconds
```

It is a fixed-duration rolling period.

It is NOT:

```text
a calendar clock hour
18:00–19:00 by local timezone
a browser-created hour bucket
```

---

# 26. Why rolling 60 minutes

Traffic ranges are canonical UTC rolling windows:

```text
24h
7d
```

There is no current Site product timezone contract for calendar-hour
aggregation.

A rolling 3600-second period:

```text
preserves UTC/source semantics
does not depend on browser timezone
does not introduce DST behavior
answers “which 60 minutes were busiest?”
```

Display timezone remains presentation-only.

---

# 27. Busiest 60-minute value model

Use the already accepted TRAFFIC-03 sample-hold temporal model:

```text
right_endpoint_sample_hold_time_weighted.v1
```

over:

```text
Total accepted Network Throughput
```

For any candidate 3600-second window:

```text
window_average_total_mbps
=
time-weighted accepted Total
over that exact 3600-second interval
```

No:

```text
average(History bucket means)
raw sample arithmetic mean
counter recalculation
zero fill
```

---

# 28. Canonical sample-hold interpretation remains unchanged

For Period Average / Busiest 60 Minutes:

```text
Site sample placement =
cycle.finished_at

adjacent accepted Site samples
define sampled hold intervals

right sample value
is the throughput estimate for the weighting interval
```

This remains:

```text
a time-aware sampled Site throughput model
```

not exact reconstruction of source-specific AP counter intervals.

---

# 29. Busiest 60-minute candidate domain

Candidate window must satisfy:

```text
window_end - window_start = 3600 seconds

window_start >= selected_range.from_utc

window_end <= selected_range.to_utc
```

The canonical mathematical selection is over all 3600-second windows fully
inside the selected range.

Implementation MAY exploit the fact that the sampled-hold function changes only
at canonical sample boundaries.

Physical candidate enumeration strategy is an implementation detail if focused
tests prove the same exact result.

---

# 30. Busiest 60-minute completeness requirement

A candidate 60-minute window is eligible only if:

```text
accepted comparable sample-hold evidence
covers the full 3600 seconds

accepted_interval_seconds_in_window = 3600

no invalid elapsed interval contributes

no excessive gap contributes

no cross-source transition interval contributes
```

No arbitrary:

```text
80%
90%
95%
```

coverage threshold.

Canonical winner must be fully comparable.

---

# 31. Busiest 60 Minutes when coverage is partial

If selected 24h/7d range is partial but contains one or more fully comparable
60-minute windows:

```text
a canonical busiest 60-minute result MAY be returned
```

Top-level Peak Load status remains:

```text
partial
```

because the whole requested range is partial.

The local hour result can still have:

```text
status = ok
```

for its own complete 60-minute evidence.

---

# 32. No complete 60-minute window

If no eligible fully comparable 3600-second window exists:

```text
busiest_hour.status =
insufficient_data

window_start_utc = null
window_end_utc = null
average_total_mbps = null
```

Never:

```text
choose the best 17-minute fragment
call a partial 60m window complete
fill missing seconds with 0
```

---

# 33. Busiest 60-minute tie / plateau contract — FINAL

Canonical domain remains:

```text
all eligible rolling 3600-second windows
fully inside [from_utc,to_utc)
```

For the piecewise-constant sample-hold throughput function, rolling 3600-second
Average Total is a continuous piecewise-linear function.

Therefore the maximum may form a flat plateau:

```text
the same maximum value
for every eligible window_start
inside a continuous interval
```

There may be infinitely many maximizing start timestamps.

Consequently `busiest_hour` MUST NOT expose:

```text
occurrence_count
```

because the number of maximizing windows is not a well-defined finite canonical
product value over the all-windows domain.

Canonical winner:

```text
maximum Average Total
over all eligible rolling 3600-second windows
```

Tie / plateau rule:

```text
earliest eligible window_start_utc
among all maximizing windows
```

Method identifiers:

```text
busiest_hour_method =
max_complete_rolling_3600s_average_total_sample_hold.v1

tie_break_method =
earliest_window_start.v1
```

Peak-event `occurrence_count` remains valid because Peak samples form a finite
discrete population.

Busiest-bucket `occurrence_count` remains valid because canonical History
buckets form a finite discrete population.

---

# 34. Relationship: Peak Total sample vs busiest bucket vs busiest 60 minutes

These are intentionally different temporal products.

Example:

```text
one 30-second burst
may create:
highest Peak Total sample

but not:
highest 5-minute/15-minute bucket average

and not:
highest 60-minute average
```

Permanent labels must distinguish:

```text
Peak Total
→ maximum accepted Site sample

Busiest History Bucket
→ maximum complete History bucket mean

Busiest 60 Minutes
→ maximum complete rolling 3600s time-weighted Total average
```

Do not present them as synonyms.

---

# 35. Top-level Peak Load status

Canonical server states:

```text
ok
partial
insufficient_data
```

No generic successful server:

```text
unavailable
```

Source/deadline/integrity failure remains HTTP/application failure.

---

# 36. Peak Load `ok`

Requires:

```text
outer History status = ok
Period Statistics status = ok

all three Peak events valid

busiest_bucket.status = ok

busiest_hour.status = ok
```

Fallback to LAN is allowed.

Source fallback by itself does not force partial.

---

# 37. Peak Load `partial`

Use when trustworthy Peak temporal evidence exists but the selected range or
one temporal subproduct is incomplete.

Examples:

```text
outer History partial

Statistics partial

Peak events valid
but no complete busiest hour

Peak events valid
but no complete busiest bucket
```

Numeric/time evidence may remain visible with explicit Partial qualifier.

---

# 38. Peak Load `insufficient_data`

Canonical invariant:

```text
Peak Load.status = insufficient_data
→ no accepted Peak samples
→ all three Peak events are null
→ busiest_bucket.status = insufficient_data
→ busiest_hour.status = insufficient_data
```

Exact Peak-event shape:

```text
value_mbps = null
sample_at_utc = null
selected_source = null
occurrence_count = 0
```

No fabricated zero.

A real accepted all-zero population is NOT insufficient.

Rationale:

```text
Peak events
History buckets
rolling-hour candidates
```

all derive from the same canonical accepted Site-sample population.

If no accepted Peak sample exists, no complete canonical History bucket and no
fully comparable rolling 3600-second winner can exist for the same requested
range.

---

# 39. Valid zero Peak

If accepted complete Site samples exist and:

```text
D_i = 0
U_i = 0
T_i = 0
```

then:

```text
Peak Download = 0.0
Peak Upload = 0.0
Peak Total = 0.0
```

with valid timestamps.

Tie rule may select the earliest accepted zero sample.

This is valid zero evidence.

---

# 40. Missing remains non-zero

Permanent:

```text
missing != 0
unknown != 0
gap != 0
partial != 0
insufficient != 0
unavailable != 0
```

No Peak/busiest selection may insert zero for missing evidence.

---

# 41. Source transitions and winning-period provenance

Peak events:

```text
may occur in wired or LAN canonical buckets
```

Busiest bucket:

```text
complete bucket already has one canonical source family
```

Busiest 60 Minutes:

```text
any cross-family weighting interval is excluded
```

A canonical `busiest_hour.status=ok` therefore requires all accepted weighting
intervals contributing to the winning 3600-second window to belong to one common
canonical source family.

The winning hour MUST expose:

```text
selected_source =
wired | lan
```

Serializer invariant:

```text
busiest_hour.status=ok
→ selected_source is wired|lan
→ every accepted weighting interval in the winning window
  belongs to selected_source
→ no source transition exists inside the contributing 3600 seconds
```

For:

```text
busiest_hour.status=insufficient_data
```

required:

```text
selected_source = null
```

Expose range-level:

```text
source_transition_count
```

through existing History evidence.

No AP-level source mixing is introduced.

---

# 42. No-baseline / reset / invalid / unavailable evidence

Reuse existing Historical quality:

```text
no_baseline_count
counter_reset_count
gap_too_large_count
invalid_elapsed_count
source_unavailable_count
source_skew_excluded_sample_count
```

TRAFFIC-04 does not create competing reason enums for source rows.

These reasons affect Peak Load only through the accepted sample/interval/bucket
contracts already owned by HistoricalTrafficReadService.

---

# 43. Coverage boundaries / watermark

Peak Load response reuses outer Historical:

```text
available_from_utc
available_through_utc
source_watermark_utc
source_age_seconds
coverage.status
```

Do not calculate another independent watermark.

Do not invent historical Fresh/Stale classification.

---

# 44. Shared Network range

Peak Load MUST use the current shared:

```text
CaptivPortalTrafficNetworkRange
```

Allowed:

```text
24h
7d
```

Default:

```text
24h
```

No Peak range selector.

No Peak custom dates.

No 30d exposure.

---

# 45. Canonical range resolution

Browser sends only:

```text
range=24h
or
range=7d
```

Server/application owns:

```text
evaluated_at_utc
from_utc
to_utc
[from,to)
```

Peak Load uses the exact same outer range returned for History/Statistics.

No independent Peak evaluation clock.

---

# 46. Selected vs applied range

Peak Load applied range is:

```text
validated combined response.range.id
```

not mutable browser selected state.

During:

```text
applied 24h
→ selected 7d
→ request in flight
```

old Peak Load evidence remains labelled:

```text
Last 24 hours
```

until a 7d response is accepted.

Failure:

```text
selected = 7d
applied remains 24h
```

No false relabelling.

---

# 47. Rapid range switching

Example:

```text
24h applied
→ select 7d
→ request starts
→ select 24h
```

Existing Traffic coordinator generation/abort rules remain authoritative.

A stale/superseded 7d response MUST NOT update:

```text
History
Statistics
Peak Load
```

Latest successful non-superseded combined response owns all three applied
products.

---

# 48. Frontend orchestration decision

Peak Load is:

```text
a passive visual consumer
of the existing network-traffic-history coordinator execution
```

It MUST NOT register an independent expensive network loader.

Reason:

```text
separate Peak loader
→ additional historical HTTP request
→ additional Admin query slot
→ unnecessary concurrency/deadline pressure
```

---

# 49. Existing coordinator remains sole lifecycle owner

No new:

```text
setInterval
polling setTimeout
AbortController
Retry-After owner
backoff owner
visibilitychange
pagehide
generation counter
global Refresh listener
```

Peak Load reuses the current History execution.

---

# 50. Initial load

Peak disabled:

```text
current behavior unchanged
History+Statistics request
```

Peak enabled:

```text
existing one History coordinator initial execution
→ one combined historical request
→ History + Statistics + Peak Load
```

No third historical request.

---

# 51. Shared range change

Range change:

```text
shared selector
→ existing History refreshPanel execution
→ one combined response
→ History + Statistics + Peak Load update together
```

Current Network Throughput is not reloaded only because range changed.

---

# 52. Global Refresh

Existing:

```text
refreshAll({manual:true})
```

remains authoritative.

Current panel reloads normally.

The one historical execution reloads:

```text
History
Statistics
Peak Load
```

No Peak-specific Refresh handler.

---

# 53. Coordinator backoff

If coordinator declines a refresh because of current backoff:

```text
Peak Load does not enter fake Loading
```

Selected range may differ from applied range.

Old applied Peak evidence remains honestly labelled.

---

# 54. API architecture — no separate Peak endpoint

FINAL decision:

```text
DO NOT add
GET /traffic/peak
```

in v1.

Reason:

```text
Peak Load uses the same Site/range/evaluation/sample population
as History + Statistics

separate endpoint creates unnecessary repeated historical work
```

---

# 55. Existing canonical endpoint remains

Use:

```text
GET /admin/api/v1/sites/<site_id>/traffic/history
```

Current accepted forms:

```text
?range=24h
?range=7d

?range=24h&include=statistics
?range=7d&include=statistics
```

---

# 56. Peak include contract — FINAL

When Peak product is enabled, browser uses exact:

```text
?range=24h&include=statistics,peak

?range=7d&include=statistics,peak
```

Accepted v1 include forms become exactly:

```text
absent
statistics
statistics,peak
```

Forbidden:

```text
peak
peak,statistics
statistics,peak,foo
duplicate include
whitespace variants
unknown token
```

Invalid shape:

```text
400 invalid_request
```

---

# 57. Why `peak` requires `statistics` in v1

Peak temporal identity must be cross-validated against accepted TRAFFIC-03 Peak
values.

V1 combined response therefore always carries:

```text
period_statistics
+
peak_load
```

when Peak is requested.

This gives one response-level invariant:

```text
Peak Load values == Period Statistics Peak values
```

No duplicate browser query is required.

---

# 58. Backward compatibility

With Peak code merged but flag disabled:

```text
?range=24h&include=statistics
```

remains current accepted Statistics response.

No `peak_load` key appears.

History-only request remains unchanged.

---

# 59. Peak feature flag

Final:

```text
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=false
```

Settings key:

```text
web_admin_traffic_peak_enabled
```

Admin config:

```text
traffic_peak_enabled: bool
```

Repository default:

```text
false
```

---

# 60. Feature dependency

FINAL v1:

```text
Peak=true
```

requires:

```text
WEB_ADMIN_ENABLED=true
WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=true
```

Reason:

```text
Peak v1 intentionally reuses:
shared History request
Period Statistics Peak identity
shared Network range
```

This is rollout/execution dependency.

It does not change Historical semantic ownership.

---

# 61. Feature flag controls exposure only

Peak flag MUST NOT:

```text
start/stop HistoricalTrafficReadService
start/stop Observation
change retention
change acquisition cadence
change source selection
change Analytics runtime state
```

Product flag != service lifecycle.

---

# 62. Peak disabled behavior

With:

```text
Traffic=true
History=true
Statistics=true
Peak=false
```

required:

```text
Current visible
History visible
Statistics visible

Peak markup absent
Peak frontend consumer inactive

historical request remains:
include=statistics

no Peak calculation requested

direct include=statistics,peak
→ 404 after normal auth/Site/product boundaries
```

---

# 63. Peak enabled behavior

With:

```text
Traffic=true
History=true
Statistics=true
Peak=true
```

required:

```text
Peak Load panel visible

one historical request:
include=statistics,peak

response:
History
+ Period Statistics
+ Peak Load
```

No independent query slot.

---

# 64. API security chain

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
include statistics:
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED
        ↓
include peak:
WEB_ADMIN_TRAFFIC_PEAK_ENABLED
        ↓
AdminQueryService
        ↓
admin.read.overview
        ↓
HistoricalTrafficReadService
```

No new auth/capability model.

---

# 65. HTTP mappings

Reuse current History endpoint contract:

```text
200
safe History/Statistics/Peak result

400 invalid_request
invalid range/include/query

401 authentication_required

403 site_forbidden

404 not_found
required product gate disabled

429 concurrency_limit

503 query_deadline

503 source_unavailable

503 response_too_large

500 internal_error
sanitized
```

---

# 66. Combined response extension

Preferred:

```json
{
  "result": {
    "status": "partial",
    "range": {},
    "buckets": [],
    "coverage": {},
    "quality": {},

    "period_statistics": {},

    "peak_load": {
      "status": "partial",
      "metric_version": "network_traffic_peak_load.v1",
      "unit": "Mbps",
      "peak_value_method": "max_accepted_complete_site_sample.v1",
      "peak_tie_break_method": "earliest_peak_sample_at.v1",
      "sample_timestamp_semantics": "cycle_finished_at",
      "events": {},
      "busiest_bucket": {},
      "busiest_hour": {}
    }
  }
}
```

No independent range object inside Peak Load.

---

# 67. Peak event DTO — final

For each:

```text
download
upload
total
```

preferred:

```json
{
  "value_mbps": 39.01,
  "sample_at_utc": "2026-08-30T10:32:10.000Z",
  "selected_source": "wired",
  "occurrence_count": 1
}
```

If insufficient:

```text
value_mbps = null
sample_at_utc = null
selected_source = null
occurrence_count = 0
```

---

# 68. Peak Load method identities

Exact FINAL identifiers:

```text
metric_version =
network_traffic_peak_load.v1

peak_value_method =
max_accepted_complete_site_sample.v1

peak_tie_break_method =
earliest_peak_sample_at.v1

sample_timestamp_semantics =
cycle_finished_at

busiest_bucket_method =
max_complete_history_bucket_total_mean.v1

busiest_bucket_tie_break_method =
earliest_bucket_start.v1

busiest_hour_method =
max_complete_rolling_3600s_average_total_sample_hold.v1

busiest_hour_tie_break_method =
earliest_window_start.v1


busiest_hour_average_method =
right_endpoint_sample_hold_time_weighted.v1
```

Canonical schema invariant:

```text
busiest_hour has no occurrence_count field
```

Serializer/focused tests MUST validate exact identities.

---

# 69. Busiest bucket DTO — FINAL

## `status = ok`

Canonical shape:

```json
{
  "status": "ok",
  "bucket_start_utc": "...",
  "bucket_end_utc": "...",
  "average_total_mbps": 18.24,
  "selected_source": "wired",
  "occurrence_count": 1,
  "method": "max_complete_history_bucket_total_mean.v1",
  "tie_break_method": "earliest_bucket_start.v1"
}
```

No new bucket calculation.

It references canonical History bucket meaning.

## `status = insufficient_data`

Exact canonical null-shape:

```text
status = insufficient_data

bucket_start_utc = null
bucket_end_utc = null

average_total_mbps = null

selected_source = null

occurrence_count = 0

method =
max_complete_history_bucket_total_mean.v1

tie_break_method =
earliest_bucket_start.v1
```

No other partial/mixed shape is valid.

---

# 70. Busiest hour DTO — FINAL

## `status = ok`

Canonical shape:

```json
{
  "status": "ok",
  "window_start_utc": "...",
  "window_end_utc": "...",
  "duration_seconds": 3600,
  "average_total_mbps": 7.82,
  "accepted_interval_seconds": 3600,
  "selected_source": "wired",
  "method": "max_complete_rolling_3600s_average_total_sample_hold.v1",
  "average_method": "right_endpoint_sample_hold_time_weighted.v1",
  "tie_break_method": "earliest_window_start.v1"
}
```

## `status = insufficient_data`

Exact canonical null-shape:

```text
status = insufficient_data

window_start_utc = null
window_end_utc = null

duration_seconds = 3600

average_total_mbps = null
accepted_interval_seconds = null

selected_source = null

method =
max_complete_rolling_3600s_average_total_sample_hold.v1

average_method =
right_endpoint_sample_hold_time_weighted.v1

tie_break_method =
earliest_window_start.v1
```

Permanent schema invariant:

```text
busiest_hour has NO occurrence_count
```

No browser averaging.

---

# 71. Serializer fail-closed rule

Server canonical Peak Load DTO is fail-closed.

Malformed/cross-field-invalid server DTO:

```text
MUST NOT
be self-healed into HTTP 200 unavailable
```

Expected:

```text
serialization/application integrity failure
→ AdminQueryUnavailable
→ combined request 503
```

Browser may preserve previously accepted visual evidence.

---

# 72. Peak event serializer invariants

For each event with numeric value:

```text
sample_at_utc valid UTC
sample_at ∈ [from,to)
selected_source = wired | lan
occurrence_count >= 1
value finite >= 0
```

For null event:

```text
value = null
sample_at = null
selected_source = null
occurrence_count = 0
```

No mixed shape.

---

# 73. Cross-check against Period Statistics

Mandatory:

```text
peak_load.events.download.value_mbps
=
period_statistics.peak.download_mbps

peak_load.events.upload.value_mbps
=
period_statistics.peak.upload_mbps

peak_load.events.total.value_mbps
=
period_statistics.peak.total_mbps
```

with existing safe float tolerance.

If Period Statistics Peak family is null:

```text
all three Peak events must be null
```

---

# 74. Peak event timestamp independence

Serializer MUST NOT require:

```text
download.sample_at
=
upload.sample_at
=
total.sample_at
```

They may be equal naturally.

They are independently selected.

---

# 75. Busiest bucket serializer invariants

If status `ok`:

```text
start/end valid UTC

from <= start < end <= to

average_total_mbps finite >= 0

selected_source wired|lan

occurrence_count >= 1
```

The selected bucket must exist exactly in:

```text
result.buckets
```

and its:

```text
status = complete
total_mbps = average_total_mbps
```

No serializer-created bucket.

---

# 76. Busiest hour serializer invariants

If status `ok`:

```text
duration_seconds = 3600

window_start/end valid UTC

from <= start < end <= to

end-start = 3600 seconds

accepted_interval_seconds = 3600

average_total_mbps finite >= 0

selected_source = wired | lan

every accepted weighting interval contributing to the winning window
belongs to selected_source

no source transition exists inside the contributing 3600 seconds
```

If status `insufficient_data`, exact shape is mandatory:

```text
window_start_utc = null
window_end_utc = null

duration_seconds = 3600

average_total_mbps = null
accepted_interval_seconds = null

selected_source = null

method =
max_complete_rolling_3600s_average_total_sample_hold.v1

average_method =
right_endpoint_sample_hold_time_weighted.v1

tie_break_method =
earliest_window_start.v1
```

Permanent:

```text
busiest_hour has NO occurrence_count
```

No partial 60-minute winner can be serialized as `ok`.

No mixed insufficient shape is accepted.

---

# 77. Busiest sub-status

For:

```text
busiest_bucket
busiest_hour
```

allowed:

```text
ok
insufficient_data
```

No local server `partial`.

Partial is a top-level range/result qualifier.

Reason:

```text
canonical winner either satisfies its exact local comparability contract
or it does not.
```

---

# 78. Top-level Peak Load status consistency

`ok` requires:

```text
Period Statistics status = ok
History status = ok

all three Peak events numeric and valid

busiest_bucket.status = ok

busiest_hour.status = ok
```

`partial` requires trustworthy Peak temporal evidence but incomplete range-level
or temporal subproduct evidence, for example:

```text
History/Statistics partial

Peak events valid
but
busiest bucket insufficient

or

Peak events valid
but
busiest hour insufficient
```

`insufficient_data` has one exact canonical invariant:

```text
Peak Load.status = insufficient_data
→ no accepted Peak samples
→ all three Peak events are null
→ busiest_bucket.status = insufficient_data
→ busiest_hour.status = insufficient_data
```

And both subproducts MUST use their exact insufficient DTO shapes defined in:

```text
§69
§70
```

A mixed shape such as:

```text
Peak Load.status = insufficient_data
but
busiest_bucket.status = ok
```

or:

```text
Peak Load.status = insufficient_data
but
busiest_hour.status = ok
```

is invalid canonical server output and MUST fail closed during serialization.

---

# 79. Timezone API contract

All canonical timestamps/ranges:

```text
UTC
```

API:

```text
sample_at_utc
bucket_start_utc
bucket_end_utc
window_start_utc
window_end_utc
```

No server calculation based on browser timezone.

---

# 80. Timezone display contract

Reuse current History display policy:

```text
browser formats returned UTC timestamps
in its resolved local timezone
using Intl.DateTimeFormat
```

Display timezone remains visible.

If a trustworthy browser timezone cannot be resolved:

```text
display UTC
```

Browser does not alter canonical event/window selection.

---

# 81. UI wording — Peak moments

Recommended:

```text
Peak Download
39.01 Mbps
Observed at 14:32:10

Peak Upload
15.45 Mbps
Observed at 17:05:41

Peak Total
40.41 Mbps
Observed at 14:32:10
```

Do not say:

```text
Internet peak
WAN peak
Guest peak
```

---

# 82. UI wording — busiest periods

Recommended:

```text
Busiest History Bucket
14:30–14:35
18.24 Mbps average Total

Busiest 60 Minutes
14:07–15:07
7.82 Mbps average Total
```

Labels must make clear:

```text
sample peak
!=
bucket average
!=
60-minute average
```

---

# 83. UI quality evidence

Minimum visible:

```text
Applied range

Peak Load status

History coverage

source watermark / age

source transitions when non-zero
```

When outer result is partial:

```text
Partial
```

must be visible, not tooltip-only.

---

# 84. Insufficient UI

Peak event insufficient:

```text
—
No accepted peak sample
```

Busiest bucket insufficient:

```text
No complete comparable bucket
```

Busiest hour insufficient:

```text
No complete comparable 60-minute period
```

Do not render `0 Mbps` unless accepted zero exists.

---

# 85. Previous accepted result during loading/failure

When a new shared range request is in flight:

```text
old accepted Peak Load may remain visible
```

but remains labelled with its old:

```text
applied range
```

On shared request failure:

```text
old accepted evidence may remain
with explicit refresh failure
```

Current panel and rest of Traffic stay operational.

---

# 86. Browser malformed Peak sub-DTO

If HTTP 200 History/Statistics parsing is valid but browser detects malformed
`peak_load` sub-DTO:

```text
Peak presentation fails local

History remains rendered

Statistics remains rendered
```

This browser defensive behavior does not weaken server fail-closed serializer
contract.

---

# 87. Backend ownership — narrow extension

Allowed new read-layer behavior:

```text
1. retain/select temporal identity for the already calculated
   Download/Upload/Total Peak samples;

2. count exact tied peak occurrences;

3. select canonical busiest complete History bucket;

4. calculate canonical busiest complete rolling 3600-second
   Average Total period;

5. return immutable Peak Load DTO
   through HistoricalTrafficReadService.
```

No independent Peak service owner.

---

# 88. HistoricalTrafficReadService extension — FINAL

Preferred conceptual signature:

```python
get_site_history(
    ...,
    include_period_statistics=False,
    include_peak_load=False,
)
```

Validation:

```text
include_peak_load=true
requires
include_period_statistics=true
```

Reason:

```text
Peak Load cross-validates against Period Statistics Peak values
and shares the same requested-range execution.
```

---

# 89. Immutable Analytics models — final

Preferred new models:

```text
HistoricalTrafficPeakEvent
HistoricalTrafficBusiestBucket
HistoricalTrafficBusiestHour
HistoricalTrafficPeakLoad
```

And:

```text
HistoricalSiteTraffic.peak_load
    | None
```

Default:

```text
None
```

to preserve History-only/Statistics-only callers.

Names may be minimally consolidated.

---

# 90. SourceGateway behavior

When Peak requested:

```text
one HistoricalTrafficReadService execution

one read-only SQLite snapshot

one shared QueryDeadline

requested-range bounded candidate semantics
```

Physical SQL statement count is NOT fixed.

Allowed:

```text
additional requested-range bounded SQL projections
inside the same snapshot
```

Forbidden:

```text
second independent historical query owner

second HistoricalTrafficReadService call

unbounded/all-history candidate validation

new DB connection snapshot for Peak
```

---

# 91. Preferred reuse of PR #89 materialized path

PR #89 final remediation uses an explicitly materialized requested-range
validation pipeline for combined History + Statistics.

Preferred:

```text
extend/reuse that accepted pipeline
```

for Peak temporal projections.

Do NOT casually revert to pre-remediation duplicated CTE work.

Physical plan remains performance-reviewed rather than architecturally fixed to
one SQL statement.

---

# 92. Busiest bucket implementation ownership

Preferred:

```text
HistoricalTrafficReadService
selects from the canonical History buckets it has already constructed
```

This requires no second source query.

The browser is forbidden to scan `result.buckets` and choose the winner.

---

# 93. Busiest 60 Minutes implementation ownership

Must live inside:

```text
HistoricalTrafficReadService / AnalyticsSourceGateway historical path
```

and reuse the same accepted Site sample semantics.

Acceptable:

```text
range-bounded SQL aggregate

or
bounded deterministic calculation over the already materialized
requested-range accepted Site sample sequence
```

Not acceptable:

```text
browser calculation
Admin serializer calculation
new repository/service owner
```

---

# 94. No new retention/range

Peak uses:

```text
24h
7d
```

No:

```text
30d
custom range
calendar hour selector
```

`TRAFFIC-10` remains future 30d product owner.

---

# 95. Feature config plumbing

Expected:

```text
app/config.py
→ app/settings.py
→ app/admin_web/config.py
→ AdminWebConfig
→ pages/routes
→ traffic.html
→ admin.js
```

Add repository-safe:

```text
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=false
```

to:

```text
.env.example
```

No production env modification in implementation TASK.

---

# 96. Expected production files to modify

Based on current `main@e1a278c3...` preferred scope:

```text
MODIFY:
app/analytics/models.py
app/analytics/historical_traffic.py
app/analytics/source_gateway.py
app/analytics/__init__.py

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

No new production module is currently required.

---

# 97. Expected unchanged files

Expected unchanged:

```text
app/analytics/runtime.py
app/analytics/config.py
app/analytics/current_traffic.py

app/observations/**
app/current_state/**
app/visit_lifecycle/**
app/visitor_registry/**
app/auth/**
app/capport/**
app/controllers/**

app/admin_web/runtime.py
app/admin_web/traffic_network_ranges.py
app/admin_web/current_traffic_serialization.py
app/admin_web/templates/admin/base.html

run.py
requirements*
```

If implementation proves one must change:

```text
STOP
→ return exact reason
→ architecture impact review
```

---

# 98. No Web Designer redesign in functional TASK

This TASK may add only the functional Peak Load markup/styles necessary for
acceptance.

Current Traffic visual composition is not frozen final design.

Final layout/card rearrangement remains a later dedicated Web Designer phase.

Do not combine aesthetic redesign with Peak semantics implementation.

---

# 99. Focused Analytics tests — Peak events

Preferred new:

```text
tests/analytics/test_historical_traffic_peak.py
```

At minimum:

```text
Peak Download value/timestamp

Peak Upload value/timestamp

Peak Total value/timestamp

three timestamps may differ

Peak values exactly equal Period Statistics Peak values

Peak Total max is per-sample Total
not directional Peak sum

accepted zero gives timestamped 0.0 Peak

missing/no samples → null events
```

---

# 100. Focused tie tests

Required:

```text
two equal Download maxima
→ earliest sample_at selected
→ occurrence_count = 2

same for Upload

same for Total
```

Also prove:

```text
later DB row order cannot change winner
```

---

# 101. Source-family Peak tests

At minimum:

```text
wired Peak event

LAN fallback Peak event

Peak values can compare samples from different canonical buckets/families

no AP-level source mixing introduced
```

---

# 102. Busiest canonical bucket tests

At minimum:

```text
complete bucket A total 5
complete bucket B total 7
→ B selected

partial bucket total 20
complete bucket total 7
→ complete bucket selected

all buckets partial/none
→ insufficient

equal complete bucket maxima
→ earliest bucket_start wins
→ occurrence_count exact
```

---

# 103. Busiest 60 Minutes algorithm tests

Deterministic synthetic evidence must prove:

```text
exact fixed 3600-second width

canonical domain = all eligible rolling 3600-second windows

time-aware weighting

not average(History bucket averages)

not raw sample arithmetic mean

window clipping across sample-hold intervals

full accepted 3600s required

gap inside window
→ candidate ineligible

source transition inside window
→ candidate ineligible

status=ok
→ all contributing accepted intervals share one selected_source

invalid elapsed evidence
→ candidate ineligible

accepted zero window is valid

no full 60m window
→ insufficient
```

Also prove that the implementation strategy, even if it evaluates only
mathematically sufficient breakpoints, returns the same canonical winner as the
all-eligible-windows definition.

---

# 104. Rolling-window winner tests

Construct at least:

```text
short high spike
vs
sustained moderate load
```

Prove:

```text
Peak Total sample can belong to spike

Busiest 60 Minutes can belong to sustained period
```

This prevents semantic collapse of sample Peak and busiest hour.

---

# 105. Rolling-hour tie / plateau regression

Mandatory focused regression:

```text
maximum rolling Average Total forms a flat plateau
over a continuous interval of eligible window_start values
```

Required:

```text
earliest valid maximizing window_start_utc selected deterministically

no occurrence_count emitted

selected_source remains the common source family
for the full winning 3600-second period
```

Also include a discrete equal-maxima case separated by a lower region and prove
the same earliest-window rule.

---

# 106. Range tests

For both:

```text
24h
7d
```

prove:

```text
Peak events inside [from,to)

no event at exact to_utc

busiest bucket inside range

busiest hour fully inside range

same outer evaluated_at/range identity as History/Statistics
```

---

# 107. Partial / quality focused tests

Cases:

```text
History partial + valid Peaks
→ Peak Load partial

valid Peaks + no complete hour
→ Peak Load partial

no accepted Peak sample
→ insufficient_data

no-baseline evidence not zero

counter reset not zero

source unavailable reason not zero

gap not zero

source transition provenance retained
```

---

# 108. Server serializer focused tests

Required:

```text
method identifiers exact

Peak values = Statistics Peak values

timestamp shapes valid

timestamp inside [from,to)

Peak-event occurrence_count contract

busiest-bucket occurrence_count contract

busiest bucket exists in History bucket list

busiest bucket complete

busiest bucket value equality

busiest hour exact 3600s

busiest hour accepted seconds = 3600

busiest hour selected_source = wired|lan when ok

all accepted weighting intervals in winning hour use selected_source

busiest hour has NO occurrence_count

busiest hour plateau selects earliest valid maximizing start

Peak Load insufficient_data
→ no accepted Peak samples
→ all three Peak events null
→ busiest_bucket insufficient_data
→ busiest_hour insufficient_data

exact busiest_bucket insufficient shape:
bucket_start_utc=null
bucket_end_utc=null
average_total_mbps=null
selected_source=null
occurrence_count=0
method exact
tie_break_method exact

exact busiest_hour insufficient shape:
window_start_utc=null
window_end_utc=null
duration_seconds=3600
average_total_mbps=null
accepted_interval_seconds=null
selected_source=null
method exact
average_method exact
tie_break_method exact
NO occurrence_count

mixed insufficient shapes rejected

status cross-field consistency

NaN/inf/negative rejected

malformed server DTO
→ fail closed
→ no synthetic HTTP 200 unavailable
```

---

# 109. Admin/API focused tests

Preferred:

```text
tests/admin_web/test_traffic_peak.py
```

At minimum:

```text
Peak flag default false

Peak=true requires:
Admin/Traffic/History/Statistics true

Peak disabled:
include=statistics works
include=statistics,peak → 404

Peak enabled:
include=statistics works
include=statistics,peak → 200

include=peak → 400

include=peak,statistics → 400

unknown include → 400

duplicate include → 400

security/Site isolation unchanged

shared deadline unchanged
```

---

# 110. Frontend focused tests

Preferred:

```text
tests/admin_web/test_traffic_peak_frontend.py
```

At minimum:

```text
Peak markup absent when disabled

Peak markup visible when enabled

no second range selector

no new registerPanel loader

no direct fetch

no private timer

no AbortController

no visibility/pagehide owner

Peak enabled changes existing historical request only to:
include=statistics,peak

one historical request per admitted generation
```

---

# 111. Frontend data tests

Required:

```text
three Peak moments render

timestamps may differ

0.0 → 0.00 Mbps

null → —

Peak/bucket tie occurrence note safe

busiest bucket renders range + average Total

busiest 60 Minutes renders range + average Total

partial visible

insufficient visible

browser formats UTC only for display

browser does not select max
browser does not calculate hour
browser does not calculate Total
```

---

# 112. Shared selected/applied range tests

Prove:

```text
selected 24h / applied 24h initial

select 7d
→ one historical refresh

during request:
old Peak remains applied 24h

success:
History/Statistics/Peak all applied 7d

failure:
selected 7d
all three remain applied 24h

backoff false-return:
no fake Loading
```

---

# 113. Rapid supersession test

Required:

```text
24h
→ 7d in flight
→ 24h
```

Stale 7d response MUST NOT update:

```text
History
Statistics
Peak Load
```

Latest successful generation owns all.

---

# 114. Request-count performance invariant

With:

```text
Current
History
Statistics
Peak Load
```

normal page load MUST remain:

```text
1 Current request

+
1 historical request
```

not:

```text
Current
+ History
+ Statistics
+ Peak
```

Range change:

```text
1 admitted historical request
```

No Peak-specific concurrency slot.

---

# 115. Shared deadline / timeout

Authoritative Admin query deadline remains current shared:

```text
10s default
```

Authoritative Traffic browser timeout remains current shared:

```text
20s default
```

Peak introduces:

```text
NO Peak deadline
NO Peak browser timeout
```

Forbidden remediation:

```text
increase 10s
increase 20s
increase Admin concurrency
```

without separate architecture review.

---

# 116. PERF baseline facts to preserve

Accepted PR #89 final remediation production-size evidence:

```text
snapshot:
bf90a989f156c39cbf8fd6fd1a3f5b9f14c36f039e5a14d121b193edaa2fe5a8

size:
256995328 bytes

fixed evaluated_at:
2026-08-30T09:51:55.587Z

S24:
p50 1.278168
p95 1.537511
max 1.670745

S7:
p50 5.570484
p95 6.542208
max 7.083732

40/40 measured requests:
200

query deadlines:
0

source integrity failures:
0
```

These are historical accepted evidence, not guaranteed future measurements.

---

# 117. TRAFFIC-04 mandatory PERF gate — PRE-PUBLICATION / Linux Central Lab

Because Peak extends the same performance-sensitive historical path:

```text
PERF is mandatory acceptance
BEFORE publication to a normal GitHub PR
```

Official PERF executes in:

```text
production-compatible Linux Central Lab
```

and NOT in:

```text
production /opt/CaptivePortal
```

The Linux Lab receives the SAME exact candidate tree that already passed the
required Windows Central Lab targeted/regression/tree checks.

Candidate transport into Linux Lab does NOT require:

```text
publication commit
GitHub feature branch
normal Git push
```

Allowed pre-publication transport:

```text
patch
controlled Lab artifact
local bundle
controlled worktree materialization
```

Before and after official PERF verify:

```text
same exact candidate tree identity

same immutable production-size snapshot SHA256
```

Any mismatch:

```text
PERF acceptance INVALID
```

Candidate cannot be accepted/published if this gate fails.

---

# 118. PERF controlled variants

On one immutable production-size read-only snapshot:

```text
B24
=
accepted baseline/current-main
History + Statistics 24h

C24
=
candidate
History + Statistics 24h
Peak not requested

P24
=
candidate
History + Statistics + Peak 24h


B7
=
accepted baseline/current-main
History + Statistics 7d

C7
=
candidate
History + Statistics 7d
Peak not requested

P7
=
candidate
History + Statistics + Peak 7d
```

Minimum:

```text
10 measured runs per variant

60 measured runs minimum
```

---

# 119. PERF evaluation identity and immutability

For each range comparison:

```text
same exact candidate tree for C/P variants

same immutable source snapshot

same fixed evaluated_at_utc

same [from,to)

same production-compatible Linux Lab environment class

same feature/query contract except measured variant
```

Record before measured PERF:

```text
candidate tree identity
snapshot SHA256
snapshot byte size
```

Record after measured PERF:

```text
candidate tree identity
snapshot SHA256
```

Required:

```text
candidate tree before = candidate tree after

snapshot SHA before = snapshot SHA after
```

The accepted baseline `B` is separately pinned to its exact accepted Git
SHA/tree.

A normal publication commit is not part of this identity requirement and is not
required before official PERF.

---

# 120. PERF run ordering

Reduce cache/order bias.

Required per-range paired/interleaved pattern:

```text
B → C → P
P → C → B
B → C → P
...
```

until every variant has at least 10 measured runs.

Equivalent deterministic alternating order is acceptable only if documented
before the measured run.

Any warm-up must be:

```text
unmeasured
equal for all variants
documented
```

---

# 121. Deterministic percentile method

Reuse the accepted TRAFFIC-03 type-7-style p95 contract.

For sorted durations:

```text
rank = (N - 1) * 0.95

lower = floor(rank)
upper = ceil(rank)

if lower == upper:
    p95 = values[lower]
else:
    p95 =
        values[lower]
        + (rank-lower)
          * (values[upper]-values[lower])
```

Use identically for:

```text
B24/C24/P24
B7/C7/P7
```

`max` is literal observed maximum.

---

# 122. PERF hard functional gates

Every variant:

```text
runs >= 10

0 query_deadline

0 source-integrity failures

0 unexpected 5xx

24h bucket_count = 288

7d bucket_count = 672

response bytes < WEB_ADMIN_MAX_RESPONSE_BYTES

source snapshot unchanged
```

C/P successful responses preserve:

```text
Statistics method IDs
```

P additionally requires:

```text
Peak Load method IDs exact
Peak Load status valid
```

---

# 123. Candidate compatibility gate: C vs B

Candidate with Peak not requested MUST preserve existing History+Statistics
performance.

For each range:

```text
Δp50 = C.p50 - B.p50
Δp95 = C.p95 - B.p95
Δmax = C.max - B.max
```

PASS requires:

```text
Δp50 <= max(0.50s, 20% of B.p50)

Δp95 <= max(0.75s, 25% of B.p95)

Δmax <= max(1.00s, 25% of B.max)
```

Also:

```text
C.p95 <= 8.0s
C.max <= 9.0s
```

This preserves the already accepted TRAFFIC-03 performance envelope.

---

# 124. Peak overhead gate: P vs C

For each range:

```text
Δp50 = P.p50 - C.p50
Δp95 = P.p95 - C.p95
Δmax = P.max - C.max
```

FINAL accepts the same existing TRAFFIC-03 relative envelope:

```text
Δp50 <= max(0.50s, 20% of C.p50)

Δp95 <= max(0.75s, 25% of C.p95)

Δmax <= max(1.00s, 25% of C.max)
```

AND hard headroom:

```text
P.p95 <= 8.0s
P.max <= 9.0s
```

Any one failure:

```text
PERF FAIL
```

---

# 125. PERF remediation prohibition

On FAIL do NOT silently:

```text
increase QueryDeadline
increase browser timeout
increase concurrent queries
add cache
add rollup
add DB/index/schema
remove required semantic checks
```

Required:

```text
STOP
→ profile
→ EXPLAIN/query-plan evidence
→ Owner + Tech Lead architecture review
```

---

# 126. Query-plan gate

Central Lab must capture safe:

```text
EXPLAIN QUERY PLAN
```

or equivalent for every materially new Peak SQL projection.

Confirm:

```text
requested-range work bounded

PR #88/PR #89 performance remediation preserved

relevant existing indexes used

no accidental all-history candidate validation

no independent second historical semantic path
```

Physical SQL statement count is not a fixed architectural number.

---

# 127. Read-only immutability gate

Before/after mandatory PERF:

```text
source snapshot fingerprint unchanged

row counts/schema unchanged where checked

no production/source writes
```

Peak remains read-only.

---

# 128. Central Lab targeted regression

Exact candidate targeted set should include at least:

```text
new TRAFFIC-04 focused tests

TRAFFIC-03 Period Statistics tests

TRAFFIC-02-PERF-01 range-bounding tests

TRAFFIC-02-READ historical tests

TRAFFIC-02 History API/serializer/frontend

TRAFFIC-00 coordinator/Foundation

TRAFFIC-01 Current Network Throughput

shared Admin config/pages/query/routes
```

Exact test list is rebuilt against candidate at review time.

---

# 129. Home regression

No Home file is expected to change.

Because shared Admin/config/runtime boundaries are touched, Central Lab should
retain relevant Home Current Traffic/security smoke/regression if current gate
already includes them.

No Home semantic change is permitted.

---

# 130. Controlled Browser Acceptance — functional — MANDATORY PRE-PUBLICATION

`TRAFFIC-04` changes frontend behavior.

Therefore Controlled Browser Acceptance is a mandatory pre-publication gate,
separate from later Production Product Acceptance.

It runs against the SAME exact accepted-candidate tree that passed required
Lab/PERF gates.

Controlled candidate must prove:

```text
Traffic page opens

Current works

History works

Statistics works

Peak Load visible when enabled

24h:
three Peak moments visible
busiest bucket
busiest 60m

7d:
same

range switching:
all three historical panels synchronized

no stuck Loading

no browser exception

no independent Peak request
```

Failure rule:

```text
controlled candidate browser FAIL
→ candidate NOT ACCEPTED
→ normal publication NOT AUTHORIZED
```

---

# 131. Controlled Browser Acceptance — temporal correctness — MANDATORY PRE-PUBLICATION

Use controlled fixture or known evidence proving:

```text
Peak Download timestamp differs from Upload timestamp

Peak Total follows its own sample

Peak-event tie selects earliest

busiest-hour plateau selects earliest valid maximizing window_start

busiest-hour selected_source matches its contributing intervals

display timezone correct

API UTC remains unchanged

selected/applied range truthful
```

This is part of candidate acceptance before publication, not a substitute for
later production browser/product acceptance.

---

# 132. Controlled Browser Acceptance — quality — MANDATORY PRE-PUBLICATION

Controlled candidate states:

```text
partial
insufficient
valid zero
gap
source transition
```

must remain visually distinguishable.

No zero fabrication.

The controlled browser gate must also prove:

```text
no busiest-hour occurrence_count presentation

selected_source provenance is presented or retained safely
according to the accepted functional UI contract
```

Failure:

```text
candidate NOT ACCEPTED
normal publication NOT AUTHORIZED
```

After publication/merge/deploy/activation, Production Product / Browser
Acceptance is a second independent acceptance level.

---

# 133. Central Lab full gate

Official PASS/FAIL belongs to:

```text
Owner + Tech Lead / Central Lab
```

Use the CURRENT verified runner at execution time.

Evidence:

```text
exact baseline
exact candidate
targeted regression
mandatory PERF
full approved regression
strict regressions
compatibility baseline
compileall
git diff --check
exact-artifact immutability
```

---

# 134. Central Lab runner

Ordinary new Peak pytest files do NOT automatically require changing the
canonical full runner.

Change runner only if:

```text
gate/compatibility/environment contract structurally changes
```

and only through explicit testing-governance review.

TASK-specific PERF procedure can remain a separate mandatory pre-publication
acceptance script/artifact.

---

# 135. Coder testing ownership

Coder runs only focused/minimal tests inside TASK scope.

Coder does NOT run:

```text
official Central Lab full gate
cross-module full regression
official PERF acceptance
official PASS/FAIL
```

Coder can prepare:

```text
candidate
focused tests
PERF helper/script if TASK requires
exact handoff commands
```

Central Lab executes official gates.

---

# 136. Proposed focused Coder command

Exact filenames may be minimally adjusted by implementation.

Expected:

```bash
python -m pytest -q \
  tests/analytics/test_historical_traffic_peak.py \
  tests/admin_web/test_traffic_peak.py \
  tests/admin_web/test_traffic_peak_frontend.py
```

Static:

```bash
PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc \
python -m compileall -q app/analytics app/admin_web

git diff --check
```

No full suite by Coder.

---

# 137. Coder handoff requirements

Handoff records:

```text
exact baseline SHA/tree

changed production files

new/modified tests

exact focused commands

passed/skipped/failed

compileall

git diff --check

scope deviation

new performance projection/query-plan note

explicit:
broader/Central Lab/PERF official acceptance NOT RUN BY CODER
```

---

# 138. Production rollout — if later accepted and authorized

Stage 1:

```text
accepted Git artifact deployed

WEB_ADMIN_TRAFFIC_PEAK_ENABLED=false
```

Dormant verification:

```text
service active
Current works
History works
Statistics works

Peak markup absent

historical request stays:
include=statistics

no Peak calculation
```

---

# 139. Separate activation

Only after Owner authorization:

```text
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=true
```

Then restart/reload per current production procedure.

Verify running environment actually contains:

```text
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=true
```

---

# 140. Production Product / Browser Acceptance — SECOND LEVEL

This gate occurs only AFTER:

```text
all pre-publication gates PASS
→ accepted candidate
→ publication
→ merge
→ Git-based production deployment
→ separate Peak activation
```

It does NOT replace Controlled Browser Acceptance.

After activation verify:

```text
Peak Load panel visible

24h works
7d works

three Peak timestamps work

busiest bucket works

busiest 60m works or truthfully says insufficient

busiest 60m source provenance is valid

History works
Statistics works

one historical request per execution

no new deadline failure pattern

no new independent concurrency pressure
```

Production browser/product FAIL is handled as production acceptance/rollback
evidence; it does not retroactively authorize skipping the mandatory controlled
pre-publication browser gate.

---

# 141. Peak-only rollback

Preferred:

```text
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=false
```

Expected:

```text
Peak panel disappears

request returns to:
include=statistics

History remains active

Statistics remains active

Current remains active

HistoricalTrafficReadService remains active
```

No need to disable entire Traffic/History/Statistics for Peak-only rollback.

---

# 142. Operational telemetry

Reuse:

```text
admin.traffic_history_query_completed
```

Add safe fields when Peak requested:

```text
peak_requested = true
peak_status
busiest_bucket_status
busiest_hour_status
```

Optional safe separate event:

```text
admin.traffic_peak_evaluated
```

only if existing telemetry cannot represent required operational evidence.

Never log:

```text
SQL
DB path
secrets
raw AP rows
```

---

# 143. Exact scope summary

In scope:

```text
Peak event timestamps for:
Download / Upload / Total

exact tie-breaking

Peak value identity with TRAFFIC-03

busiest complete History bucket

busiest complete rolling 60-minute Total period

canonical immutable DTO

combined History API include extension

subordinate feature flag

passive Traffic panel

24h / 7d shared range

quality/partial/insufficient states

focused tests

mandatory pre-publication PERF

Central Lab regression
```

---

# 144. Explicit non-goals

Not in `TRAFFIC-04`:

```text
new Peak value algorithm independent from TRAFFIC-03

traffic volume MB/GB

TRAFFIC-05 Traffic by AP

TRAFFIC-06 AP Share

TRAFFIC-07 Online Guests

TRAFFIC-08 Completed Guest Session Traffic

TRAFFIC-09 Evidence consolidation

30d UI exposure

Heatmap

Period Comparison

custom date range

calendar-clock-hour analytics

AP-specific Peak

SSID/guest throughput

new acquisition

Omada historical product source

new DB/schema/index

cache/rollup

Home redesign

Traffic final visual redesign
```

---

# 145. Architecture decisions — FINAL

1. `TRAFFIC-04 = When?`, not another `How much?`.
2. Peak values reuse `max_accepted_complete_site_sample.v1`.
3. Three separate Peak timestamps are required.
4. Peak timestamp semantics = canonical `cycle.finished_at`.
5. UI says `Observed at`.
6. Peak-event tie-breaking = earliest canonical sample.
7. Peak-event `occurrence_count` is returned.
8. Peak Total event is independent of directional peaks.
9. Busiest canonical bucket uses complete History buckets only.
10. Busiest bucket selects max canonical bucket `total_mbps`.
11. Busiest-bucket tie = earliest bucket start; finite `occurrence_count` retained.
12. Busiest hour = rolling fixed 3600 seconds.
13. Canonical busiest-hour domain = all eligible rolling 3600-second windows.
14. Busiest hour uses accepted sample-hold Average Total.
15. Busiest hour requires full 3600s comparable evidence.
16. No partial 60m candidate can become canonical winner.
17. Busiest-hour tie/plateau = earliest eligible maximizing window start.
18. `busiest_hour.occurrence_count` is forbidden.
19. `busiest_hour.selected_source` is required when status=ok.
20. All accepted weighting intervals in winning hour use that one source family.
21. One shared Network range 24h/7d.
22. No second range selector.
23. No separate Peak HTTP request.
24. Combined include form = `statistics,peak`.
25. Peak flag default false.
26. Peak v1 requires Statistics enabled.
27. Peak is passive consumer of History coordinator execution.
28. Shared 10s deadline/20s browser timeout unchanged.
29. Mandatory PERF happens before Git publication in production-compatible Linux Central Lab.
30. Linux PERF does not require publication commit/GitHub feature branch.
31. Production `/opt/CaptivePortal` is not Linux Central Lab.
32. Controlled Browser Acceptance is mandatory pre-publication.
33. Production Product/Browser Acceptance is a separate second level.
34. Exact candidate tree and immutable snapshot identities are verified before/after PERF.
35. No collector/DB/schema/index/cache/rollup.

---

# 146. Owner + Tech Lead review decisions — INCORPORATED

The DRAFT review explicitly accepted:

```text
Q1 rolling fixed 3600s:
ACCEPTED

Q2 complete-only busiest bucket:
ACCEPTED

Q3 full 3600s comparable evidence:
ACCEPTED

Q4 include=statistics,peak only:
ACCEPTED

Q5 PERF relative envelope:
ACCEPTED
```

Therefore these are no longer open questions in FINAL.

Final PERF envelope remains:

```text
C vs B:
existing TRAFFIC-03 relative envelope

P vs C:
same relative envelope
```

with unchanged absolute gates:

```text
p95 <= 8.0s
max <= 9.0s
```

and unchanged:

```text
query deadline
browser timeout
Admin concurrency
```

Additional mandatory review corrections incorporated into FINAL:

```text
busiest_hour occurrence_count removed

continuous plateau semantics documented

earliest maximizing rolling-window start is canonical tie-break

busiest_hour selected_source added

literal Windows Lab → Linux Lab → controlled browser
pre-publication path fixed

Linux PERF publication independence fixed

candidate tree/snapshot before/after verification fixed

controlled browser acceptance classified as mandatory pre-publication
```

No architecture issue remains open in this FINAL based on the reviewed DRAFT.

---

# 147. Risks

## R1 — Timestamp overclaim

Risk:

```text
user reads sample_at as exact packet spike instant
```

Mitigation:

```text
Observed at wording
cycle_finished_at method identity
explicit source-timestamp distinction
```

## R2 — Peak value drift from TRAFFIC-03

Mitigation:

```text
same read execution
same sample population
serializer equality invariant
```

## R3 — Partial bucket falsely selected

Mitigation:

```text
complete-only canonical busiest bucket
```

## R4 — Partial hour bias

Mitigation:

```text
full 3600s accepted evidence required
```

## R5 — PERF regression

Mitigation:

```text
no second HTTP request
same read-only snapshot/deadline
range-bounded projections
pre-publication B/C/P benchmark
```

## R6 — Query complexity

Mitigation:

```text
query-plan gate
no deadline increase
STOP before cache/schema workaround
```

---

# 148. Stop conditions

Implementation MUST STOP and return evidence if it requires:

```text
changing TRAFFIC-03 Peak values

changing peak_method

changing Observation Mbps formula

recalculating Mbps from counters

using source timestamps as a replacement Peak value model

creating second Historical service

creating /traffic/peak heavy endpoint

second frontend historical loader

second Network range selector

browser max/rolling-hour calculation

AP-level wired/LAN mixing

including partial bucket as canonical busiest bucket
without architecture amendment

using incomplete 60-minute candidate as canonical winner
without architecture amendment

reverting PR #88/#89 range/performance remediation

increasing QueryDeadline

increasing browser timeout

increasing Admin concurrency

adding DB/schema/index/cache/rollup

adding Omada calls

adding 30d selector

adding AP/SSID/guest Peak
```

Also STOP on material `origin/main` drift before implementation.

---

# 149. FINAL short-check checklist

Owner + Tech Lead short final check should confirm only that the reviewed
corrections are represented correctly:

1. Repository binding remains `main@e1a278c3... / tree a529faae...`.
2. `busiest_hour` has no `occurrence_count`.
3. All eligible rolling 3600-second windows remain the canonical domain.
4. Plateau/tie winner is earliest maximizing eligible `window_start_utc`.
5. Mandatory plateau regression exists.
6. `busiest_hour.selected_source` is required for `status=ok`.
7. Winning 60m accepted intervals all belong to that source.
8. Exact pre-publication path is Windows Central Lab → Linux Central Lab → Controlled Browser.
9. Linux PERF requires same exact candidate tree, not a publication commit/branch.
10. Production `/opt/CaptivePortal` is explicitly not Linux Central Lab.
11. Candidate tree and snapshot SHA are verified before/after PERF.
12. Controlled Browser Acceptance is mandatory pre-publication.
13. Production Product/Browser Acceptance remains a second post-activation gate.
14. Q1–Q5 are closed as ACCEPTED.
15. PERF relative/absolute envelopes are unchanged.
16. Peak Load insufficient_data exact cross-subproduct invariant is fixed.
17. Exact busiest_bucket insufficient DTO shape is fixed.
18. Exact busiest_hour insufficient DTO shape is fixed.
19. `busiest_hour` still has no occurrence_count.
20. Implementation authorization remains NOT GRANTED.

---

# 150. FINAL status

```text
TASK:
TASK-TRAFFIC-04 — Peak

CANONICAL ROADMAP ID:
TRAFFIC-04 — Peak Load Period

STATUS:
FINAL — TECH LEAD FINAL CONSISTENCY FIXES INCORPORATED
TECH LEAD FINAL REVIEW = PASS

BOUND TO REPOSITORY:
main@e1a278c3e2c131b0762d7134485dcf3208eac11e

TREE:
a529faae4ded9e3f6c5cb72c5a9c6d9cfcc9df3e

RUNTIME CODE CHECKPOINT:
b92efbfabb38f912550526bc5a3d1f2f1a8ae4d6

RUNTIME TREE:
1d8b94590848f9505e45e653384dd8a7c18d4339

CANONICAL OWNER:
HistoricalTrafficReadService

PEAK VALUE METHOD:
max_accepted_complete_site_sample.v1

PEAK TIMESTAMP:
cycle.finished_at

BUSIEST HOUR DOMAIN:
all eligible rolling 3600-second windows

BUSIEST HOUR TIE / PLATEAU:
earliest_window_start.v1

BUSIEST HOUR occurrence_count:
NOT PART OF CONTRACT

BUSIEST HOUR selected_source:
REQUIRED WHEN status=ok

RANGES:
24h / 7d shared Network range

SEPARATE PEAK HTTP REQUEST:
NO

CANONICAL INCLUDE:
statistics,peak

FEATURE DEFAULT:
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=false

NEW ACQUISITION:
NO

NEW DB / SCHEMA / INDEX / CACHE / ROLLUP:
NO

SHARED QUERY DEADLINE:
UNCHANGED

CONTROLLED BROWSER ACCEPTANCE:
MANDATORY PRE-PUBLICATION

MANDATORY PERF:
PRE-PUBLICATION
PRODUCTION-COMPATIBLE LINUX CENTRAL LAB

PUBLICATION COMMIT REQUIRED BEFORE PERF:
NO

PRODUCTION /opt/CaptivePortal AS LAB:
FORBIDDEN

IMPLEMENTATION AUTHORIZATION:
NOT GRANTED

MERGE AUTHORIZATION:
NOT GRANTED

PRODUCTION DEPLOYMENT:
NOT GRANTED

PRODUCTION ACTIVATION:
NOT GRANTED
```

Next allowed step:

```text
Owner + Tech Lead short FINAL verification
```

Only after that, if Owner separately authorizes implementation:

```text
Coder implementation may begin
from a newly rechecked exact origin/main baseline.
```

This FINAL itself does NOT authorize implementation.

---

