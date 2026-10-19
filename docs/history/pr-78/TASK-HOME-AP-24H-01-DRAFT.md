# TASK-HOME-AP-24H-01 — 24-hour AP status/history block for Admin Home — DRAFT

**Project:** CaptivPortal  
**Area:** Admin Console → Home → Access Point 24h History  
**Type:** Product read model / Analytics + Admin composition  
**Status:** DRAFT — Owner / Tech Lead architectural review required  
**Implementation authorization:** NOT GRANTED  
**Production activation:** NOT GRANTED  
**Prepared:** 2026-08-28  
**Exact repository baseline:** `origin/main@bc929dbe7c1687415bd4eeda971dcbc9376d8bbc`  
**Baseline commit:** `TASK-OMADA-WEBHOOK-TRAFFIC-BYTES-01 — accept Omada Bytes traffic alias`  

---

# 0. Executive decision

`HOME-AP-24H-01` adds a separate Site-aware Home read model that answers:

> “Что происходило с каждой точкой доступа за последние 24 часа, насколько надёжны эти данные и что известно о её состоянии сейчас?”

The block is NOT a second copy of Home Live.

Home Live remains the canonical current snapshot presentation.

`HOME-AP-24H-01` adds historical context over a fixed rolling 24-hour window.

Repository investigation confirms that the required historical persistence already exists:

```text
Current State
- AP inventory/status snapshots
- default cadence: 60 s
- default history retention: 48 h

Observation Foundation
- AP dynamic observations
- default cadence: 30 s
- default dynamic retention: 180 days
- AP overview / wired / LAN / radio quality flags
- AP resource, traffic-counter and radio facts
```

Therefore:

```text
NO new collector
NO new DB
NO schema migration
NO retention increase
NO cadence increase
```

is required for a useful AP-24H block.

However one major semantic limitation is confirmed:

```text
Current State currently proves only:
status_code == 1 → online

all other numeric codes → other

missing/unusable code → unknown
```

The repository test contract explicitly prohibits treating current `0`, `2`, or other codes as `offline`.

Therefore current data can prove:

```text
positive online evidence
unknown / unmapped status evidence
history gaps
Current State source quality
Observation complete/partial history
which Observation sections were unavailable
```

but it CANNOT yet truthfully prove:

```text
physical AP outage
offline start/end
offline duration
24h uptime percentage
```

without a separate verified Omada AP-status semantics decision.

**Architectural conclusion for this DRAFT:**

> **B. Реализуемо частично на текущих данных.**
>
> A useful 24h block can be implemented now without new storage or collection.
> It can show positive online evidence, current-state certainty, 24h evidence coverage,
> Observation degradation/partial intervals, gaps, and current-vs-history context.
>
> Real AP outage/downtime semantics are NOT currently proven and MUST NOT be invented.
> Full outage duration requires a separate narrow AP status-semantics foundation/research decision,
> but not a schema/storage/cadence change.

---

# 1. Goal

Add a dedicated Admin Home block that gives an operator an understandable rolling 24-hour AP picture while preserving source semantics.

For every AP seen in the selected Site during the last 24 hours, the operator should be able to determine:

- whether positive online evidence was consistently present;
- whether status evidence contains unknown/unmapped periods;
- whether collection history contains gaps;
- whether Observation was complete or partial;
- which Observation sections were missing/failed;
- when those evidence-quality problems occurred;
- the current known AP state;
- whether the current state is consistent with the preceding 24h evidence;
- whether the AP is new/recent and therefore lacks a full 24h history.

The block MUST NOT claim a physical outage where the sources only prove uncertainty.

---

# 2. Current roadmap context

Already implemented/accepted Home blocks:

```text
Home Live
Home Traffic
Home Activity
Home Health
```

`HOME-AP-24H-01` is the next independent Home block.

It MUST NOT redefine or silently change any accepted Home contract.

---

# 3. Baseline truth

At DRAFT preparation:

```text
origin/main =
bc929dbe7c1687415bd4eeda971dcbc9376d8bbc
```

Before FINAL:

1. fetch `origin/main`;
2. record exact SHA;
3. compare changes touching:
   - `app/observations/**`;
   - `app/current_state/**`;
   - `app/analytics/**`;
   - `app/admin_web/**`;
   - `app/config.py`;
   - `app/settings.py`;
4. if AP persistence/status semantics/Home composition changed, return for impact review.

Do not authorize implementation from this DRAFT if baseline has materially drifted.

---

# 4. Architectural placement

Canonical direction:

```text
Admin Home browser
        ↓
same-origin Admin API
        ↓
Admin route / authentication / Site policy
        ↓
shared Admin query controls
        ↓
Home AP-24H read model
        ↓
Analytics/query layer
        ↓
read-only Current State history
+
read-only Observation history
```

The browser is presentation only.

No AP history calculation belongs in:

```text
admin.js
Jinja template
CSS
browser-side arrays/reducers
```

except rendering already prepared statuses, timestamps, counters and timeline segments/buckets.

---

# 5. Source ownership

## 5.1 Current State owns

Current State is the source of truth for:

- current AP inventory;
- current AP identity fields;
- controller AP status code/classification;
- current snapshot freshness;
- retained AP inventory/status snapshots;
- AP cycle result/complete/failure metadata.

## 5.2 Observation owns

Observation Foundation is the source of truth for:

- AP dynamic observation history;
- AP-level `partial`;
- endpoint/section availability:
  - overview;
  - wired uplink;
  - LAN traffic;
  - radios;
- section observation timestamps;
- AP CPU/memory facts;
- wired/LAN traffic-counter facts and derived rates;
- radio configuration/runtime facts;
- radio utilization/counters;
- Observation cycle quality.

## 5.3 Analytics/query layer owns

The AP-24H backend owns:

- fixed rolling-24h window resolution;
- evidence coverage calculations;
- gap detection;
- bucket/segment construction;
- per-AP summaries;
- Site summary;
- source-quality interpretation;
- current-vs-24h categorical context;
- response bounding/pagination.

## 5.4 Admin owns

Admin owns:

- authentication;
- Site authorization;
- query concurrency/deadline boundary;
- safe serialization;
- same-origin API route;
- independent Home component failure handling.

---

# 6. Confirmed Observation Foundation state

Observation Storage Foundation is schema v1.

Persisted cycle kinds:

```text
client
ap_dynamic
ap_config
```

AP dynamic history is stored in:

```text
ap_observations
ap_radio_observations
```

AP configuration history is stored separately in:

```text
ap_config_snapshots
```

Historical Site/AP indexes already exist, including:

```text
(site_id, ap_mac, observed_at, row_id)
(site_id, observed_at, row_id)
(site_id, ap_mac, band, radio_observed_at, row_id)
```

No new index is obviously required for a 24h Site/AP query.

Coder MUST provide query-plan evidence before adding any index.

---

# 7. Observation AP dynamic facts already persisted

Per AP observation row, existing historical fields include:

```text
observed_at
site_id
ap_mac

partial
overview_ok
wired_uplink_ok
lan_traffic_ok
radios_ok

overview_observed_at
wired_observed_at
lan_observed_at

name
ip
model
firmware_version

cpu_util
mem_util
uptime_seconds

wired_* counters
wired_download_mbps
wired_upload_mbps
wired_*_rate_reason

lan_* counters
lan_rx_mbps
lan_tx_mbps
lan_*_rate_reason
```

Per radio:

```text
band
radio_id
actual_channel
frequency_mhz
channel_width
max_tx_rate
tx_power
wireless_mode

tx_util
rx_util
interference_util
busy_util

rx/tx bytes
rx/tx packets
drop/error/retry counters

radio_rx_mbps
radio_tx_mbps
rate reasons
```

This is significantly richer than what the first AP-24H block strictly needs.

---

# 8. Observation cadence and retention

Repository defaults:

```text
OBSERVATION_AP_INTERVAL_SECONDS = 30
OBSERVATION_DYNAMIC_RETENTION_DAYS = 180
```

Therefore a rolling 24h window is comfortably inside the repository retention design.

This DRAFT does NOT change:

```text
collection cadence
retention
request budgets
AP endpoint set
Observation schema
```

---

# 9. Observation `partial` semantics

`ApObservation.partial` does NOT mean:

```text
AP physically degraded
AP offline
radio failed
wired link failed
```

It means the AP dynamic observation was incomplete.

The AP worker queries four independent sections:

```text
overview
wired_uplink
lan_traffic
radios
```

and sets:

```text
partial = true
```

when one or more sections were unavailable/malformed, or rate-quality processing could not safely produce a valid rate.

Therefore UI wording MUST preserve:

```text
Observation degraded / incomplete
```

not:

```text
AP degraded
```

unless separate device-state evidence proves degradation.

---

# 10. Observation cycle semantics

Observation cycle state/result is separate from AP state.

Cycle-level facts include:

```text
state
complete
result
error_count
data_quality_warning_count
```

A partial/failed AP dynamic cycle may mean:

- Controller/API request issue;
- inventory incompleteness;
- request budget/deadline;
- malformed response;
- individual endpoint failure;
- storage/worker issue.

It MUST NOT be translated into:

```text
all APs were offline
```

---

# 11. Confirmed Current State state

Current Network State is schema v1.

It stores:

```text
current_state_cycles
current_ap_state
```

despite the name "Current State", retained cycles are historical for a bounded period.

Current AP rows include:

```text
cycle_id
site_id
observed_at
ap_mac
name
ip
model
firmware_version
status_code
status_classification
last_seen_ms
controller_uptime
uptime_raw
```

Thus the repository already retains an AP status evidence stream.

---

# 12. Current State cadence and retention

Repository defaults:

```text
CURRENT_STATE_AP_INTERVAL_SECONDS = 60
CURRENT_STATE_HISTORY_RETENTION_HOURS = 48
```

Current AP freshness defaults:

```text
fresh <= 90 s
stale <= 300 s
unavailable after 300 s
```

Cleanup removes whole cycles older than the configured history-retention cutoff.

A 24h read model therefore requires no Current State retention increase under the repository default.

---

# 13. Current State production-setting caveat

Repository defaults are NOT proof of production settings.

Production acceptance MUST read and record the actual active values:

```text
CURRENT_STATE_AP_INTERVAL_SECONDS
CURRENT_STATE_HISTORY_RETENTION_HOURS

OBSERVATION_AP_INTERVAL_SECONDS
OBSERVATION_DYNAMIC_RETENTION_DAYS
```

Activation MUST NOT silently modify them.

If actual retention is shorter than 24h:

```text
AP-24H reports partial/insufficient coverage
```

or production activation is withheld by Owner.

This TASK does not change retention.

---

# 14. Critical AP offline limitation

Current AP normalization is intentionally conservative.

Existing rule:

```text
status_code == 1
→ status_classification = online

status_code is another integer
→ status_classification = other

status_code missing/unusable
→ status_classification = unknown
```

Existing tests explicitly verify:

```text
0  → other
2  → other
99 → other

and:
status_classification != offline
```

Therefore the current repository does NOT contain a proven controller-code mapping for physical AP offline state.

---

# 15. Consequence of the offline limitation

The current code can safely say:

```text
"online evidence existed"
```

or:

```text
"the controller status is unmapped / uncertain"
```

but cannot safely say:

```text
"the AP was offline for 17 minutes"
```

from status code 0/2/other alone.

Likewise:

```text
AP absent from an inventory
```

does NOT automatically mean offline.

It may mean:

- AP removed/adopted elsewhere;
- Site inventory changed;
- incomplete inventory;
- controller/API failure;
- AP no longer managed;
- other unsupported controller state.

No outage inference is allowed from absence alone.

---

# 16. Separate dependency for full outage semantics

If Owner requires real outage duration in the first production version, create/approve a separate narrow dependency, proposed ID:

```text
TASK-CURRENT-STATE-AP-STATUS-SEMANTICS-01
```

Its purpose:

1. perform controlled live Omada evidence collection;
2. power down/disconnect only an approved test AP;
3. observe:
   - whether AP remains in Site inventory;
   - exact raw `status_code`;
   - `lastSeen`;
   - behavior during restart/disconnect/re-adoption;
4. prove controller-version-specific mapping;
5. define a canonical shared AP status mapper.

Expected result if evidence permits:

```text
online
offline
other
unknown
```

No schema change should be necessary because raw `status_code` is already persisted.

This dependency is semantic, not storage-related.

---

# 17. No hidden status reinterpretation

`HOME-AP-24H-01` MUST NOT contain its own private mapping such as:

```text
0 = offline
2 = offline
```

if Current State does not already define it.

When a future verified mapping exists:

```text
Current State and AP-24H use the same shared canonical mapping
```

Do not fork status semantics between modules.

---

# 18. Existing Current State read contract

Current State already exposes:

```text
get_current_ap_summary(site_id)
list_current_aps(site_id, ...)
```

and Admin exposes:

```text
GET /admin/api/v1/sites/<site_id>/current-state/aps/summary
GET /admin/api/v1/sites/<site_id>/current-state/aps
```

These are current-snapshot contracts.

They MUST NOT be repurposed into a 24h historical response.

---

# 19. Existing Home Live AP semantics

Home Live currently displays:

```text
AP Online / Total
Other
Unknown
Access Points Now
```

The Admin serializer deliberately collapses:

```text
offline + other
```

into product `Other`.

`HOME-AP-24H-01` MUST NOT alter that accepted Home Live contract.

---

# 20. Existing Observation Admin API

Admin already supports a raw per-AP historical route:

```text
GET /admin/api/v1/sites/<site_id>/observations/aps
```

requiring:

```text
ap_mac
from_utc
to_utc
```

This route is not suitable as the Home AP-24H data source.

Reasons:

- it is per AP;
- using it from Home would create N requests;
- the underlying Observation page max is bounded;
- one AP at 30 s cadence can produce ~2880 rows over 24h;
- raw rows should not be sent to the browser for Home aggregation.

Do not reuse this endpoint by looping over APs in JavaScript.

---

# 21. Existing Analytics capabilities

Analytics already provides Site-scoped, read-only calculations over persisted Observation facts.

Existing AP-related functions include:

```text
AP CPU distribution
AP memory distribution

radio:
tx_util
rx_util
interference_util
busy_util

stored throughput distributions:
wired
LAN
radio

counter quality:
retry
error
drop
packet deltas
```

Existing Analytics statuses:

```text
ok
partial
insufficient_data
unavailable
```

Existing quality model already tracks:

```text
partial cycles
failed cycles
abandoned cycles
missing/rejected rows
source watermarks
```

No existing Analytics DTO currently represents:

```text
AP 24h availability/status history
```

---

# 22. Analytics limitation relevant to this TASK

Current generic `AnalyticsSourceGateway` knows:

```text
Observation
Visits
Registry
```

It does not currently include Current State as an Analytics source.

Therefore AP-24H needs a new read-only composition path for:

```text
Observation + Current State
```

This is an Analytics/query-layer extension.

It is NOT a new storage foundation.

---

# 23. Preferred backend architecture

Preferred implementation shape:

```text
app/analytics/home_ap_24h.py
```

or equivalent dedicated Analytics product-read service.

Conceptually:

```text
HomeAp24hReadService
    ↓
HomeAp24hSourceGateway
    ├── ObservationReadService
    └── CurrentStateReadService
```

It MUST:

- use existing read-only SQLite boundaries;
- never initialize/migrate a source;
- never call Omada;
- never write;
- honor one shared monotonic query deadline;
- aggregate Site-wide, not AP-by-AP SQL calls.

---

# 24. Current State Analytics read boundary

ObservationReadService already exposes a query-only Analytics connection.

CurrentStateReadService currently does not.

Preferred narrow extension:

```text
CurrentStateReadService.analytics_read_connection()
```

with the same principles:

```text
existing repository connection
URI mode=ro
PRAGMA query_only=ON
no schema ownership by Analytics
```

Expected schema check:

```text
Current State user_version == 1
```

This is a read-boundary extension only.

No Current State API/current semantics change.

---

# 25. AP-24H source readiness isolation

Do NOT make unrelated Visit/Registry Analytics source failures automatically destroy AP-24H if its required sources remain healthy.

AP-24H requires exactly:

```text
Current State
Observation
Analytics/query code itself
```

A Visit Lifecycle or Visitor Registry outage is irrelevant to this block.

Therefore preferred composition is a dedicated AP-24H Analytics service with its own source readiness.

---

# 26. No Omada request-time fallback

If Current State/Observation history is unavailable:

```text
do NOT call Omada from Home request
```

The block must show degraded/unavailable evidence state.

Reason:

- Home stays a persisted read model;
- request latency stays bounded;
- Admin browsing does not change controller load;
- history cannot be reconstructed by a single live poll anyway.

---

# 27. Time window contract

Primary window:

```text
rolling 24 hours
```

Canonical calculation:

```text
to_utc   = server evaluated_at_utc
from_utc = to_utc - 24 hours
```

Interval semantics:

```text
[from_utc, to_utc)
```

This is NOT:

```text
today
calendar day
Site-local midnight
previous day
```

---

# 28. Timezone contract

Rolling 24h mathematics is timezone-independent.

Canonical persistence/query timestamps remain UTC.

API returns:

```text
evaluated_at_utc
from_utc
to_utc
```

All bucket boundaries are UTC.

No dependency on Home Activity timezone configuration is introduced.

The final Web Designer may choose localized timestamp formatting as presentation-only behavior, but MUST NOT change the rolling window.

---

# 29. Historical raw sample cadence

Expected repository-default raw evidence cadence:

```text
Current State AP inventory/status: ~60 s
Observation AP dynamic:          ~30 s
```

The Home API MUST NOT return raw source-cadence samples.

Raw samples exist for backend evidence only.

---

# 30. Home timeline granularity

Proposed DRAFT output granularity:

```text
15-minute buckets
```

Rolling 24h:

```text
96 buckets per AP
```

Bucket boundaries are anchored to:

```text
from_utc
```

not to calendar quarter-hours.

Rationale:

- enough temporal resolution for a Home overview;
- predictable payload size;
- no raw 30s/60s stream sent to browser;
- still shows when evidence-quality problems clustered.

Tech Lead may adjust bucket size in FINAL, but must keep a bounded fixed contract.

---

# 31. Underlying gap thresholds

Use source cadence plus existing Analytics quality threshold.

Proposed formulas:

```text
current_state_gap_threshold_seconds =
max(
    3 × active Current State AP interval,
    ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS
)

observation_gap_threshold_seconds =
max(
    3 × active Observation AP interval,
    ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS
)
```

Repository defaults yield:

```text
Current State: max(180, 180) = 180 s
Observation:   max(90, 180)  = 180 s
```

A gap is evidence unavailability.

It is NOT AP downtime.

---

# 32. AP identity roster for the 24h window

The AP set is the Site-scoped union of AP MAC identities seen in:

```text
Current State AP history within the window
+
Observation AP history within the window
+
latest complete Current State AP inventory
```

This handles:

- one AP;
- two APs;
- many APs;
- AP newly added during the window;
- AP present earlier but absent from latest inventory;
- one source temporarily missing an AP that exists in the other source.

Identity key:

```text
canonical AP MAC
```

No AP name is used as identity.

---

# 33. AP identity display metadata

Preferred name/model source:

1. latest trustworthy Current State AP row;
2. if absent, latest trustworthy Observation overview row;
3. else null.

Response MUST expose where identity metadata came from:

```text
identity_source = current_state | observation | none
```

Do not merge contradictory values silently.

MAC remains canonical stable identity.

---

# 34. Status vocabulary — separate axes

The UI MUST NOT collapse device state and evidence quality into one ambiguous word.

AP-24H exposes at least two independent status axes:

```text
A. AP state evidence
B. Observation / source quality
```

Both may use the product vocabulary where appropriate, but their scope is explicit.

---

# 35. AP state evidence vocabulary

Canonical values:

```text
operational
degraded
unavailable
unknown
```

Current baseline can safely emit only:

```text
operational
unknown
```

for device state.

## `operational`

Positive trusted status evidence says:

```text
Current State status_classification == online
```

## `degraded`

Reserved for a future proven device-state condition.

Current baseline has no canonical device-degraded mapping.

MUST NOT be synthesized from Observation partial.

## `unavailable`

Reserved for a verified canonical AP offline/unavailable state.

Current baseline has no verified offline mapping.

MUST NOT be synthesized from `other`, missing rows, API errors or gaps.

## `unknown`

Use when:

- status code is `other`;
- status code is unknown;
- AP missing from current trustworthy inventory;
- current snapshot too old;
- Current State source unavailable;
- historical status coverage is insufficient.

---

# 36. Observation quality vocabulary

Observation quality uses:

```text
operational
degraded
unavailable
unknown
```

with a different explicit scope.

## `operational`

Usable AP observation evidence exists and required sections are complete.

## `degraded`

At least one AP observation or Site cycle is partial/incomplete, while useful evidence remains.

Examples:

```text
overview unavailable
wired endpoint unavailable
LAN endpoint unavailable
radios endpoint unavailable
rate source unavailable
partial Site cycle
```

This means:

```text
observation evidence degraded
```

not physical AP degradation.

## `unavailable`

The AP-24H query cannot read the Observation source, or the Observation source is positively unavailable.

## `unknown`

No usable Observation history exists for this AP/window and the source is not positively unavailable.

---

# 37. Current AP state contract

Per AP:

```json
{
  "current": {
    "status": "operational|degraded|unavailable|unknown",
    "reason_code": "...",
    "observed_at": "...",
    "freshness_status": "fresh|stale|unavailable",
    "freshness_reason": "..."
  }
}
```

Current rules on this baseline:

```text
fresh + online
→ operational

stale + last-known online
→ unknown / stale_current_evidence

unavailable snapshot
→ unknown / current_state_stale_or_unavailable

other status
→ unknown / controller_status_unmapped

unknown status
→ unknown / controller_status_unknown

not in latest complete inventory
→ unknown / not_in_latest_inventory
```

Do not call stale last-known online "currently operational".

---

# 38. 24h AP state summary

Per AP:

```json
{
  "history": {
    "status": "...",
    "reason_code": "...",
    "coverage_status": "...",
    "first_evidence_at": "...",
    "last_evidence_at": "...",
    "status_sample_count": 0,
    "online_sample_count": 0,
    "unknown_or_other_sample_count": 0,
    "max_gap_seconds": null,
    "coverage_ratio": null
  }
}
```

No field named:

```text
uptime_percent
offline_seconds
downtime_seconds
```

is allowed until offline semantics are proven.

---

# 39. 24h history status rule — current baseline

`history.status = operational` only if all are true:

1. at least one trustworthy AP status sample exists;
2. historical coverage is `complete`;
3. every trustworthy status sample used for AP state is canonical `online`;
4. no trusted sample is `other/unknown`;
5. no future verified unavailable segment exists.

Otherwise:

```text
history.status = unknown
```

on the current baseline.

When a future canonical unavailable/degraded mapping exists, FINAL may extend:

```text
degraded = one or more resolved historical impairment/outage segments
           while current state has recovered

unavailable = current canonical state unavailable
```

but this DRAFT does not invent those states.

---

# 40. Coverage status

Per source/AP:

```text
complete
partial
insufficient_data
```

## Complete

For AP status history:

- trustworthy samples reach both window edges within the gap threshold;
- no inter-sample gap exceeds threshold;
- AP identity is known for the intended coverage period.

## Partial

Some trustworthy history exists, but:

- first sample starts after the window edge;
- last sample ends before the window edge;
- max gap exceeds threshold;
- source had partial/failed cycles;
- AP was first seen during the 24h window.

## Insufficient data

No usable historical samples exist.

Coverage is not AP availability.

---

# 41. Newly added AP

If an AP first appears at:

```text
Tfirst > from_utc
```

do NOT interpret:

```text
from_utc → Tfirst
```

as downtime.

Response:

```text
coverage_status = partial
reason_code = recent_ap_or_short_history
history_started_at = Tfirst
```

No penalty score.

No invented zero uptime.

---

# 42. AP no longer in latest inventory

If an AP has trustworthy 24h history but is absent from latest complete Current State inventory:

```text
current.status = unknown
reason_code = not_in_latest_inventory
```

Historical evidence remains visible.

Do NOT delete it from the Home 24h roster solely because it is absent now.

Do NOT call it offline.

---

# 43. Current State partial/failed cycle handling

A `partial`, `failed`, or `shutdown` Current State cycle contributes:

```text
source/evidence quality
```

but not negative AP device-state evidence.

A complete successful AP inventory cycle is the authoritative basis for coverage.

A valid AP row from a partial cycle MAY be retained as diagnostic supporting evidence, but it MUST NOT upgrade a bucket/history classification from unknown to operational if strict complete inventory evidence is absent.

---

# 44. Observation AP partial handling

For each AP Observation row:

```text
partial == false
AND overview_ok
AND wired_uplink_ok
AND lan_traffic_ok
AND radios_ok
```

is complete AP dynamic evidence.

If one or more are false:

```text
observation_quality = degraded
```

with reason codes identifying exactly which sections were unavailable.

Example reasons:

```text
overview_unobserved
wired_uplink_unobserved
lan_traffic_unobserved
radios_unobserved
rate_quality_degraded
site_cycle_partial
```

These are evidence reasons, not hardware fault diagnoses.

---

# 45. Controller/API failure semantics

Controller/API problems are represented as source-quality degradation/unavailability.

They MUST NOT turn all APs into:

```text
unavailable
offline
```

Example:

```text
AP observation cycle failed because Controller API timed out
```

means:

```text
Observation quality unavailable/degraded for that interval
AP physical state unknown
```

---

# 46. Radio/uplink semantics

Current stored facts can show:

- radio utilization;
- retry/error/drop counters;
- wired/LAN counters;
- section observation success.

But no currently approved product thresholds define:

```text
radio degraded
uplink degraded
```

Therefore v1 AP-24H MUST NOT derive a red/yellow AP health state from arbitrary thresholds.

Section fetch failure is:

```text
evidence degraded
```

not:

```text
radio/uplink failed
```

---

# 47. Secondary diagnostics available without new collection

Existing data could support future/secondary diagnostics:

```text
24h CPU distribution
24h memory distribution
per-band busy utilization
per-band interference utilization
radio retry/error/drop quality
wired/LAN throughput distributions
```

Existing Analytics already contains much of this formula machinery.

DRAFT decision for the mandatory Home AP-24H contract:

```text
DO NOT make these required v1 primary metrics
```

Reason:

- the task is status/history first;
- no approved device-degradation thresholds exist;
- Home Traffic already owns traffic presentation;
- adding metrics only to fill cards would blur semantics.

They may be added later without new collection/storage.

---

# 48. Current vs 24h context

Do not invent a numeric "normality score".

Provide a categorical evidence comparison.

Proposed values:

```text
consistent_with_24h_online_evidence
current_less_certain_than_24h
history_insufficient
historical_state_mixed_or_unknown
```

Future verified offline semantics may add:

```text
recovered_after_historical_unavailability
current_unavailable_after_operational_history
```

Current baseline examples:

```text
current operational
+ history operational
→ consistent_with_24h_online_evidence

current unknown
+ history operational
→ current_less_certain_than_24h

history partial/insufficient
→ history_insufficient
```

This is evidence comparison, not anomaly detection.

---

# 49. Timeline/bucket contract

Per returned AP page, provide a fixed rolling 24h timeline.

Proposed:

```text
96 × 15-minute buckets
```

Each bucket contains prepared backend classifications only.

Conceptual DTO:

```json
{
  "from_utc": "...",
  "to_utc": "...",
  "ap_state": "operational|degraded|unavailable|unknown",
  "observation_quality": "operational|degraded|unavailable|unknown",
  "reason_codes": [],
  "status_sample_count": 0,
  "observation_sample_count": 0
}
```

Browser may render colors/segments.

Browser MUST NOT recompute state from counts.

---

# 50. Bucket AP-state rules

For trustworthy Current State evidence inside a bucket:

```text
only online samples
+ sufficient source evidence
→ operational

verified canonical unavailable sample
→ unavailable
    [future only, after semantics foundation]

verified canonical degraded sample
→ degraded
    [future only]

other/unknown/conflicting samples
→ unknown

no usable samples
→ unknown
```

Missing source evidence never becomes unavailable AP state.

---

# 51. Bucket Observation-quality rules

Within a bucket:

```text
usable AP observations
+ all complete
+ no applicable Site-cycle degradation
→ operational

one or more AP rows partial
or section flags false
or Site AP cycle partial
→ degraded

Observation source read unavailable
→ unavailable

no applicable usable history
→ unknown
```

If a bucket contains both complete and partial samples:

```text
degraded
```

because degradation evidence must not be hidden by successful samples.

---

# 52. Problem-duration semantics

Any displayed duration derived from the 15-minute timeline is explicitly:

```text
bucketed evidence duration
```

not exact physical outage duration.

Examples:

```text
Observation degraded: 45 min
Status evidence unknown: 30 min
```

mean:

```text
3 degraded 15-min buckets
2 unknown 15-min buckets
```

The response SHOULD expose both:

```text
bucket_count
bucket_seconds
```

so presentation semantics remain clear.

Do not call unknown evidence duration "downtime".

---

# 53. Site summary contract

The Site-level response must summarize the full Site roster, not just the current AP page.

Minimum:

```json
{
  "ap_count_in_window": 0,
  "current": {
    "operational": 0,
    "degraded": 0,
    "unavailable": 0,
    "unknown": 0
  },
  "history": {
    "operational": 0,
    "degraded": 0,
    "unavailable": 0,
    "unknown": 0
  },
  "observation_quality": {
    "operational": 0,
    "degraded": 0,
    "unavailable": 0,
    "unknown": 0
  },
  "short_history_ap_count": 0,
  "status_gap_ap_count": 0,
  "observation_problem_ap_count": 0
}
```

The summary MUST preserve axis names.

Do not publish one ambiguous:

```text
bad_ap_count
```

without breakdown.

---

# 54. Proposed Admin API

New same-origin endpoint:

```text
GET /admin/api/v1/sites/<site_id>/home/ap-24h
```

Allowed parameters:

```text
limit
cursor
```

No user-supplied time range.

The time range is always rolling 24h.

Authorization:

```text
authenticated Admin session
resolved Site
admin.read.overview
```

Unknown parameters:

```text
400 invalid_request
```

Forbidden Site:

```text
403 site_forbidden
```

---

# 55. Pagination contract

The Site summary covers all AP identities in the Site window.

Per-AP items are paginated.

DRAFT proposal:

```text
default limit = 25 APs
maximum limit = 50 APs
sort = canonical ap_mac ascending
```

Rationale:

- deterministic;
- scales beyond current two APs;
- 96 timeline buckets per AP remain bounded;
- no hard-coded current AP count;
- response remains under Admin byte limit.

Cursor MUST bind:

```text
site_id
window_to_utc / evaluation anchor
last_ap_mac
limit/query contract version
```

Subsequent pages use the same 24h window anchor.

A new refresh without cursor creates a new rolling window.

---

# 56. Existing AP source capacity

Current collectors are already configured with bounded AP inventory sizes.

Repository defaults include:

```text
Observation AP max rows = 500
Current State AP max rows = 500
```

AP-24H MUST NOT hard-code:

```text
2 APs
```

If a Site exceeds the configured collection cap:

- source cycles should already become partial/bounded;
- AP-24H reports degraded/partial evidence;
- it MUST NOT silently pretend the Site is complete.

Scaling beyond configured source capacity is a separate collection-capacity decision.

---

# 57. Response top-level contract

Conceptual v1 response:

```json
{
  "contract_version": "admin.home_ap_24h.v1",
  "window": {
    "kind": "rolling_24h",
    "evaluated_at_utc": "...",
    "from_utc": "...",
    "to_utc": "...",
    "bucket_seconds": 900,
    "bucket_count": 96
  },
  "block_status": "operational|degraded|unavailable|unknown",
  "block_reason": null,
  "sources": {},
  "summary": {},
  "items": [],
  "page": {
    "limit": 25,
    "next_cursor": null
  }
}
```

`block_status` describes the AP-24H read model itself.

It is NOT an AP hardware state.

---

# 58. Source metadata contract

Return product-safe source evidence.

Example:

```json
{
  "sources": {
    "current_state": {
      "status": "operational|degraded|unavailable|unknown",
      "schema_version": 1,
      "first_evidence_at": null,
      "last_evidence_at": null,
      "complete_cycle_count": 0,
      "partial_cycle_count": 0,
      "failed_cycle_count": 0,
      "max_gap_seconds": null
    },
    "observations": {
      "status": "operational|degraded|unavailable|unknown",
      "schema_version": 1,
      "first_evidence_at": null,
      "last_evidence_at": null,
      "complete_cycle_count": 0,
      "partial_cycle_count": 0,
      "failed_cycle_count": 0,
      "max_gap_seconds": null
    }
  }
}
```

No DB path is exposed.

No raw SQL/internal exception is exposed.

---

# 59. Per-AP response contract

Conceptual:

```json
{
  "ap_mac": "AA:BB:CC:DD:EE:FF",
  "name": "AP name",
  "model": "EAP613",
  "identity_source": "current_state",

  "current": {
    "status": "operational",
    "reason_code": "fresh_online_evidence",
    "observed_at": "...",
    "freshness_status": "fresh"
  },

  "history": {
    "status": "operational",
    "reason_code": "continuous_online_evidence",
    "coverage_status": "complete",
    "first_evidence_at": "...",
    "last_evidence_at": "...",
    "status_sample_count": 0,
    "online_sample_count": 0,
    "unknown_or_other_sample_count": 0,
    "max_gap_seconds": null,
    "coverage_ratio": null,
    "current_vs_24h": "consistent_with_24h_online_evidence"
  },

  "observation_quality": {
    "status": "operational",
    "reason_code": null,
    "complete_sample_count": 0,
    "partial_sample_count": 0,
    "section_problem_counts": {
      "overview": 0,
      "wired_uplink": 0,
      "lan_traffic": 0,
      "radios": 0
    }
  },

  "timeline": []
}
```

No physical downtime field on the current baseline.

---

# 60. Block-level status

## `operational`

The AP-24H service answered successfully and both required source boundaries are usable.

Individual APs may still have unknown/degraded evidence; that is represented in summaries/items.

## `degraded`

The read model remains useful but one required source is degraded/partially usable.

Examples:

- Observation available but partial history;
- Current State available but significant source gaps;
- one source temporarily unavailable while the other provides useful evidence.

## `unavailable`

The AP-24H backend cannot provide a meaningful response at all.

Examples:

- query layer cannot open both required sources;
- schema mismatch;
- hard query/deadline failure before a safe payload is produced.

## `unknown`

The sources are readable, but there is no historical AP evidence yet.

---

# 61. Fail-open Home behavior

AP-24H is an independent Home component.

Failure MUST NOT:

- fail `/admin/sites/<site_id>/`;
- hide Home Live;
- hide Home Traffic;
- hide Home Activity;
- hide Home Health;
- change Admin runtime state.

The AP-24H fetch may independently return:

```text
429 concurrency_limit
503 query_deadline
503 source_unavailable
```

The page renders an AP-24H-specific unavailable state.

Other Home components continue normally.

---

# 62. Partial source behavior

## Current State unavailable, Observation available

Return HTTP 200 if Observation history can still produce a meaningful partial block.

Per AP:

```text
current.status = unknown
history.status = unknown
observation_quality = derived normally
```

Block:

```text
degraded
```

## Observation unavailable, Current State available

Return HTTP 200 if Current State status history is usable.

Per AP:

```text
current/history = derived
observation_quality = unavailable
```

Block:

```text
degraded
```

## Both unavailable

AP-24H endpoint:

```text
503 source_unavailable
```

No impact on other Home components.

---

# 63. Analytics/query failure behavior

If the AP-24H Analytics/query service is unavailable:

```text
503 source_unavailable
```

Do not call source modules directly from the browser as fallback.

Do not fall back to Home Live and call it "24h".

---

# 64. No-history behavior

Readable empty history is not an infrastructure failure.

If no AP history exists:

```text
HTTP 200
block_status = unknown
block_reason = no_historical_evidence
ap_count_in_window = 0
```

If current inventory contains APs but no 24h history has accumulated yet:

- APs remain in roster;
- current state may be shown;
- history is `unknown/insufficient_data`.

---

# 65. Multi-AP behavior

The same contract applies to:

```text
1 AP
2 APs
25 APs
100 APs
up to the configured source inventory capacity
```

No naming logic:

```text
AP1
AP2
primary AP
secondary AP
```

may be hard-coded.

All identity and grouping is Site + canonical AP MAC.

---

# 66. Site isolation

Every source query MUST contain the authorized:

```text
site_id
```

No cross-Site aggregation.

A cursor for Site A cannot be reused on Site B.

If an AP MAC appears in multiple Sites at different times:

```text
each Site history is isolated by Site context
```

---

# 67. Query architecture — no N queries

Forbidden shape:

```text
list APs
for each AP:
    query 24h Current State
    query 24h Observation
    query radios
```

Required shape:

```text
bounded Site-aware set queries
```

The number of SQL statements per AP-24H request must be bounded independently of AP count.

Python grouping over already bounded query results is allowed.

DB round trips must not scale linearly with AP count.

---

# 68. Query-side aggregation

Prefer SQL aggregation for:

- Site cycle quality;
- AP roster;
- per-AP status sample counts;
- per-AP first/last evidence;
- gap/window quality where practical;
- section failure counts;
- bucket grouping.

Do not materialize all 30-second Observation rows into Admin serialization merely to reduce them later.

Where Python merging is used, input must already be bounded by:

```text
24h window
Site
AP page
required fields only
```

---

# 69. Read transaction consistency

Current State and Observation are separate SQLite databases.

AP-24H uses:

```text
one immutable evaluated_at/window anchor
```

for both.

Each source query should use a read-only transaction/snapshot.

Cross-database byte-for-byte simultaneity is not required.

Response exposes source watermarks/evidence timestamps so small collection skew is visible.

No `ATTACH` with write permissions.

---

# 70. Query deadline

AP-24H participates in the existing Admin query concurrency/deadline gate.

Current repository default:

```text
WEB_ADMIN_MAX_CONCURRENT_QUERIES = 2
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS = 10
```

AP-24H MUST NOT bypass those controls.

Source SQL should install/use query-deadline interruption where the existing Analytics pattern requires it.

---

# 71. Browser refresh contract

DRAFT proposal:

```text
refresh every 120 seconds
```

Rationale:

- Current State AP cadence is ~60 s;
- Home Live already provides faster current context;
- 24h history does not need second-level refresh;
- reduces repeated historical scans.

No request overlaps.

If a prior AP-24H request is still in flight:

```text
do not start another
```

Final refresh value is subject to Tech Lead review.

---

# 72. Server cache

No cache is required by architecture if the capacity benchmark passes.

Preferred initial rule:

```text
no new persistent cache
no new DB
```

A small process-local cache MAY be considered only if Central Lab proves repeated AP-24H query cost materially threatens Admin budgets.

If added later:

- cache key must include Site + anchored window/version;
- TTL must be bounded;
- stale cache must be explicit;
- it must not become source of truth.

Do not preemptively add cache complexity.

---

# 73. Browser payload bound

The API must pass the existing Admin response byte cap.

Current repository default:

```text
WEB_ADMIN_MAX_RESPONSE_BYTES = 1 MiB
```

Browser receives:

- Site summary;
- source quality;
- at most one AP page;
- prepared 15-minute timeline buckets;
- no raw Observation rows;
- no raw Current State cycle rows.

Central Lab must test worst-case page payload.

If 50 AP × 96 buckets cannot safely stay under the existing byte cap, FINAL lowers AP page max rather than increasing `WEB_ADMIN_MAX_RESPONSE_BYTES` as a workaround.

---

# 74. Current/Home frontend boundary

The frontend is allowed to:

- request AP-24H JSON;
- render Site summary;
- render AP summaries;
- render 24h buckets/segments;
- format timestamps;
- paginate;
- show status colors/labels;
- show independent loading/error states.

The frontend is forbidden to:

- decide whether an AP is operational;
- infer offline from missing data;
- compute coverage ratios;
- calculate gap duration;
- merge Current State with Observation;
- classify Observation partial;
- calculate per-AP 24h state;
- calculate current-vs-history semantics.

---

# 75. Home HTML/JS integration

Final visual design is not part of architecture.

Implementation may require:

```text
app/admin_web/templates/admin/home.html
app/admin_web/static/admin.js
app/admin_web/static/admin.css
```

but functional implementation must preserve existing hooks/contracts.

Web Designer refinement follows backend functional acceptance.

No existing Home block is removed/reordered semantically by backend implementation.

---

# 76. No new production feature flag

This DRAFT does not introduce a new production feature flag.

Do NOT modify existing feature-flag semantics for:

```text
Home Live
Home Traffic
Home Activity
Home Health
Observation
Current State
Analytics
```

If Owner/Tech Lead later wants a temporary rollout gate, it requires explicit FINAL approval.

---

# 77. No schema/storage changes

Required:

```text
Observation PRAGMA user_version = 1
Current State PRAGMA user_version = 1
Visit PRAGMA user_version = 2
```

No:

- new table;
- new column;
- new index without query-plan evidence;
- migration;
- materialized AP-24H DB;
- retained rollup table.

The block is computed from existing persisted facts.

---

# 78. No collection changes

This TASK must not change:

```text
OBSERVATION_AP_INTERVAL_SECONDS
CURRENT_STATE_AP_INTERVAL_SECONDS
Omada endpoints
poll order
AP inventory behavior
retention
request timeout
```

If production source coverage is insufficient, report evidence.

Do not silently increase collection load to make the Home card prettier.

---

# 79. No other subsystem changes

Forbidden without a separate approved task:

```text
Omada authorization
AuthWorker
CAPPORT
Visit Lifecycle semantics
Public Traffic semantics
webhook schema
Visitor Registry semantics
Pending Session Cleaner
Home Activity formulas
Home Traffic formulas
Home Live current contract
Home Health contract
Grafana
Loki
Alloy
```

---

# 80. Proposed code ownership

Likely backend surfaces:

```text
app/analytics/home_ap_24h.py
app/analytics/home_ap_24h_models.py        # if useful
app/analytics/home_ap_24h_source.py        # if gateway split is warranted

app/current_state/read_service.py          # read-only analytics connection only

app/admin_web/query_service.py
app/admin_web/routes.py
app/admin_web/home_ap_24h_serialization.py
```

Home integration:

```text
app/admin_web/templates/admin/home.html
app/admin_web/static/admin.js
app/admin_web/static/admin.css
```

Composition:

```text
run.py / runtime composition
```

only as necessary to inject the new read service.

No persistence-owner file should need schema mutation.

---

# 81. Primary source-of-truth table

| Displayed meaning | Source | Current availability |
|---|---|---|
| AP identity / current inventory | Current State | YES |
| Current positive online state | Current State `status==1` | YES |
| Current real offline state | Current State | **NO — mapping not proven** |
| 24h positive online evidence | Current State retained cycles | YES |
| 24h real outage duration | Current State | **NO — mapping not proven** |
| Current snapshot freshness | Current State meta | YES |
| Current State collection gaps | Current State cycles | YES |
| AP Observation complete/partial | Observation AP rows | YES |
| Observation endpoint completeness | `overview_ok`, `wired_uplink_ok`, `lan_traffic_ok`, `radios_ok` | YES |
| Observation cycle partial/failed | Observation cycles | YES |
| AP CPU / memory history | Observation | YES |
| Radio utilization history | Observation radio rows | YES |
| Radio error/retry/drop counters | Observation radio rows | YES |
| Wired/LAN counters/rates | Observation AP rows | YES |
| Physical wired/radio fault state | Current stored facts | **NO canonical threshold/state contract** |
| Home current AP list | Existing Home Live | YES, separate accepted contract |

---

# 82. What can be implemented now without new collection/storage

Fully implementable now:

1. rolling 24h source window;
2. Site/AP roster;
3. current AP positive-online/unknown status;
4. Current State freshness;
5. status sample counts;
6. 24h status-evidence coverage;
7. status-evidence gaps;
8. recent/new AP short-history handling;
9. AP absent-from-current-inventory handling;
10. Observation 24h complete/partial history;
11. per-section Observation degradation counts;
12. Observation problem timeline;
13. Current State source-quality timeline;
14. 15-minute prepared AP timeline;
15. Site summary;
16. per-AP summary;
17. current-vs-24h evidence context;
18. Site-aware pagination;
19. fail-open independent Home behavior;
20. source provenance/quality.

No new collection/storage is needed for those.

---

# 83. What cannot be honestly implemented now

Not currently justified:

```text
AP uptime percentage
AP downtime percentage
offline start/end
offline duration
"AP was offline"
device-level degraded state
radio failed state
wired uplink failed state
```

unless separate verified semantics are approved.

Do not fill these with:

```text
0
100%
No outages
```

because `unknown` is not zero.

---

# 84. Test plan — source semantics

At minimum:

1. status 1 → AP current operational.
2. status 0 → AP current unknown, not unavailable.
3. status 2 → AP current unknown, not unavailable.
4. missing status → unknown.
5. stale last-known online → current unknown.
6. source unavailable → AP current unknown, source unavailable.
7. AP absent latest complete inventory → unknown.
8. no mapping path creates offline from `other`.
9. Observation `partial=true` → Observation degraded, AP state unchanged.
10. radios endpoint missing → observation reason `radios_unobserved`, AP not called degraded/offline.

---

# 85. Test plan — 24h window

11. exact rolling 24h window.
12. UTC half-open boundary.
13. event/sample at `from_utc` included.
14. sample at `to_utc` excluded.
15. exactly 96 15-minute buckets.
16. bucket boundaries cover exactly 24h with no overlap/gap.
17. no calendar-midnight dependency.
18. DST/local timezone cannot change window duration.

---

# 86. Test plan — coverage/gaps

19. continuous healthy samples → coverage complete.
20. edge start gap above threshold → partial.
21. edge end gap above threshold → partial.
22. inter-sample gap above threshold → partial.
23. recent AP first seen 3h ago → partial/recent, not 21h downtime.
24. no samples → insufficient data.
25. one source history absent → correct partial source behavior.
26. failed Current State cycle → source gap, not AP outage.
27. failed Observation cycle → observation degraded/unavailable evidence, not AP outage.

---

# 87. Test plan — Observation quality

28. all four sections complete → operational Observation bucket.
29. one wired section false → degraded Observation bucket.
30. one radio section false → degraded Observation bucket.
31. mixed complete+partial samples in bucket → degraded.
32. cycle partial with AP row → degraded source/evidence.
33. cycle failed/no AP row → unknown AP observation evidence.
34. observation query unavailable → observation quality unavailable.
35. section failure counts aggregate correctly.

---

# 88. Test plan — current vs history

36. current online + complete online 24h → consistent.
37. current unknown + prior complete online history → current_less_certain.
38. partial history → history_insufficient.
39. no history → history_insufficient.
40. recent AP → history_insufficient/recent.
41. no arbitrary "abnormal" score emitted.

---

# 89. Test plan — Site/multi-AP

42. one AP.
43. two APs.
44. 25 APs.
45. > one response page.
46. AP present only in Current State is included.
47. AP present only in Observation is included.
48. historical AP absent current inventory remains included.
49. same AP MAC in different Site cannot leak.
50. cursor Site mismatch rejected.
51. deterministic AP-MAC ordering.
52. Site summary covers all Site APs, not only returned page.

---

# 90. Test plan — performance

53. DB query count does not grow linearly with AP count.
54. no per-AP SQL loop.
55. 24h Observation query uses Site/time indexes.
56. Current State query uses kind/Site/time cycle index.
57. query deadline interruption works.
58. response remains within Admin max bytes.
59. browser receives no raw 30s/60s sample stream.
60. page max bound enforced.
61. no overlapping frontend refresh.

---

# 91. Capacity benchmark

Central Lab must generate a production-compatible 24h fixture.

Profiles:

```text
1 AP
2 AP
25 AP
100 AP
500 AP
```

At repository-default cadences:

```text
Current State AP: 60 s
Observation AP:   30 s
```

The 500-AP fixture represents approximately:

```text
Current State AP rows:
500 × 1440 ≈ 720,000

Observation AP rows:
500 × 2880 ≈ 1,440,000

plus cycles/radios as appropriate
```

The implementation must aggregate, not serialize raw rows.

---

# 92. Performance acceptance

Hard acceptance:

```text
one AP-24H request completes inside the existing
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS
```

for the approved capacity fixture and requested AP page.

Repository default hard deadline:

```text
10 seconds
```

Targets for review:

```text
<= 2 s typical small Site
<= 5 s 500-AP capacity fixture page
```

Target miss with hard correctness PASS returns evidence to Tech Lead.

Do NOT fix performance by:

```text
increasing Admin deadline
increasing response byte cap
reducing collection retention
```

without separate review.

---

# 93. Fail-open tests

62. AP-24H 503 does not fail Home HTML.
63. AP-24H 503 does not stop Home Live refresh.
64. AP-24H 503 does not stop Home Traffic.
65. AP-24H 503 does not stop Home Activity.
66. AP-24H 503 does not change Home Health.
67. Current State unavailable + Observation available → 200 degraded partial block.
68. Observation unavailable + Current State available → 200 degraded partial block.
69. both unavailable → AP-24H endpoint 503 only.
70. query deadline → AP-24H endpoint 503 only.
71. concurrency limit → 429 only for AP-24H request.

---

# 94. Schema/integrity regression

Verify after implementation:

```text
Observation PRAGMA user_version = 1
Current State PRAGMA user_version = 1
Visit PRAGMA user_version = 2
```

No schema signature drift.

No new persistent DB.

No source writes caused by AP-24H read.

---

# 95. Existing Home regression

Must prove unchanged:

```text
Home Live endpoints/payload
Home Traffic endpoints/payload
Home Activity endpoints/payload
Home Health endpoint/payload
current-state APIs
raw Observation APIs
```

No accepted Home calculation is moved into AP-24H.

---

# 96. Central Lab acceptance

Coder runs focused/module tests only.

Central Lab performs the official exact-artifact acceptance:

1. exact candidate commit;
2. full repository regression;
3. AP-24H deterministic tests;
4. multi-AP/site isolation;
5. 24h capacity benchmark;
6. query-plan inspection;
7. response-size bound;
8. no-write verification;
9. schema-version/signature verification;
10. existing Home regressions.

Only exact Central-Lab-approved artifact may proceed to Owner rollout review.

---

# 97. Production precheck

Before activation, Owner/Tech Lead records:

```text
deployed commit SHA

Current State:
state
schema version
AP enabled
AP interval
history retention
latest AP complete cycle

Observation:
state
schema version
AP enabled
AP interval
dynamic retention
latest ap_dynamic complete cycle

Analytics/query:
state
query deadline

Admin:
max response bytes
max concurrent queries
```

No setting is changed merely to satisfy this precheck.

---

# 98. Production forward acceptance

Read-only verification for the real Site:

1. endpoint authenticates;
2. correct Site only;
3. rolling window is exactly 24h;
4. expected AP identities appear;
5. current online APs agree with existing Current State/Home Live positive evidence;
6. `other/unknown` is never displayed as offline;
7. Observation partial evidence matches persisted Observation facts;
8. source gaps are shown as gaps/unknown, not outage;
9. recently-added AP gets short-history semantics;
10. AP absent from current inventory is not falsely called offline;
11. query latency is within budget;
12. response size is within bound;
13. other Home panels continue if AP-24H request is forced to fail.

---

# 99. Production acceptance — outage limitation

For this DRAFT/current baseline:

```text
do NOT perform a production "outage duration" acceptance
```

because outage semantics are not approved.

Do not power off a production AP simply to make the Home block show red.

If the separate AP status-semantics task is later approved, its controlled physical test becomes the authority for real offline behavior.

---

# 100. Rollout boundary

This DRAFT does not authorize rollout.

Expected later rollout after FINAL/Central Lab:

1. backup exact code/config artifact as normal;
2. deploy read-model/frontend changes;
3. no DB migration;
4. restart application if required by normal deploy;
5. verify sources remain healthy;
6. perform AP-24H forward read checks;
7. verify existing Home components;
8. observe Admin query telemetry.

No Observation/Current State DB mutation is part of activation.

---

# 101. Rollback

Because no schema changes are allowed:

```text
rollback = code/frontend rollback only
```

No DB downgrade.

No historical data reverse migration.

No source cleanup.

Existing persisted cycles remain valid.

---

# 102. Telemetry

Add bounded operational telemetry for the new backend request, e.g.:

```text
admin.home_ap_24h_query_completed
```

Safe fields:

```text
site_id
status_code
outcome
reason
duration_ms
block_status
current_state_source_status
observation_source_status
ap_count_in_window
returned_ap_count
next_page_present
response_size_category
```

Do not log:

```text
raw DB rows
full timeline payload
credentials
tokens
session cookie
```

Per-AP high-cardinality telemetry is not required.

---

# 103. Non-goals

This TASK does NOT:

- prove Omada offline status codes;
- change AP status mapping secretly;
- build AP SLA/uptime billing;
- create a new monitoring stack;
- replace Grafana;
- replace Home Live;
- redesign Home layout;
- create hardware health scores;
- create radio quality thresholds;
- create uplink failure thresholds;
- change collector cadence;
- change retention;
- change DB schema;
- backfill history;
- modify Auth;
- modify Visit Lifecycle;
- modify Public Traffic;
- modify webhook normalization;
- modify CAPPORT;
- modify Home Activity;
- modify Home Traffic;
- modify Home Health;
- add a new persistent cache.

---

# 104. Architecture stop conditions

Return to Owner/Tech Lead if implementation appears to require:

```text
Observation schema v2
Current State schema v2
new persistent AP history table
new collector endpoint
different collection cadence
retention increase
Omada request from Admin route
private AP status-code guess
new external dependency
cross-Site query
Home Live contract change
Home Traffic formula change
```

Do not expand scope silently.

---

# 105. DRAFT open items for Tech Lead

The structural architecture is defined.

Items for FINAL review:

1. approve 15-minute output bucket granularity;
2. approve AP page default/max:
   ```text
   25 / 50
   ```
3. approve 120-second Home refresh hint;
4. decide whether partial AP-24H implementation should ship before the separate AP status-semantics research;
5. if real outage/downtime is mandatory for first release, approve:
   ```text
   TASK-CURRENT-STATE-AP-STATUS-SEMANTICS-01
   ```
   as a prerequisite.

No schema/storage/collection decision is currently open.

---

# 106. Final architectural conclusion

## B. Реализуемо частично — ограничения

**What is fully possible now:**

```text
rolling 24h AP evidence
current positive online state
unknown/unmapped current state
coverage/gaps
new AP short history
Observation complete/partial history
Observation problem intervals
which Observation sections were unavailable
Site summary
per-AP summary
prepared timeline
current-vs-history evidence context
multi-AP
Site-aware
bounded Home API
```

**What is not yet technically justified:**

```text
real AP offline periods
downtime duration
uptime percentage
physical AP unavailable status
device-level degraded status
```

The missing piece is NOT data storage.

The raw historical `status_code` already exists in Current State.

The missing piece is a **verified semantic mapping of Omada AP controller status to canonical offline/unavailable state**.

Therefore:

```text
NO foundation/storage migration is required for AP-24H itself.

A narrow AP-status semantics research/foundation task is required
only if full physical outage/downtime behavior is mandatory.
```

---

# 107. Required next step

Return this DRAFT to:

```text
Owner
Tech Lead
```

for architectural review.

Do NOT:

```text
create implementation branch
modify code
commit
push
create PR
deploy
change production configuration
```

from this DRAFT.

After review, Architect prepares:

```text
TASK-HOME-AP-24H-01-FINAL.md
```

or, if Owner requires verified outage semantics first:

```text
TASK-CURRENT-STATE-AP-STATUS-SEMANTICS-01
```

followed by the AP-24H FINAL.
