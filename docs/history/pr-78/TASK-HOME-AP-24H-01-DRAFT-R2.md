# TASK-HOME-AP-24H-01 — 24-hour AP status/history block for Admin Home — DRAFT R2

**Project:** CaptivPortal  
**Area:** Admin Console → Home → Access Point 24h History  
**Type:** Product read model / Analytics + Admin composition  
**Status:** DRAFT R2 — Owner / Tech Lead architectural review required  
**Implementation authorization:** NOT GRANTED  
**Production activation:** NOT GRANTED  
**Prepared:** 2026-08-28  
**Exact repository baseline:** `origin/main@bc929dbe7c1687415bd4eeda971dcbc9376d8bbc`  
**Baseline commit:** `TASK-OMADA-WEBHOOK-TRAFFIC-BYTES-01 — accept Omada Bytes traffic alias`  

---

# 0. Executive decision

`HOME-AP-24H-01` remains a separate Site-aware Home read model whose product goal is a truthful rolling 24-hour AP availability/history picture.

The R1 architecture remains accepted:

```text
Admin Home → same-origin Admin API
           → bounded Admin query gate
           → AP-24H backend/read model
           → read-only Current State + Observation
```

No AP-history calculation moves into JavaScript/template.

Repository investigation still confirms that the required persistence foundations already exist:

```text
Current State
- historical AP inventory/status cycles
- raw status_code persisted
- default AP poll delay 60 s
- default history retention 48 h

Observation Foundation
- historical AP dynamic observations
- four dynamic sections per attempted AP:
  overview / wired_uplink / lan_traffic / radios
- default worker delay 30 s after a dynamic run
- default dynamic retention 180 days
```

Therefore AP-24H itself still requires:

```text
NO new DB
NO schema migration
NO retention increase
NO collection-cadence increase
NO Omada request-time fallback
```

However R2 makes one dependency **mandatory**:

```text
TASK-CURRENT-STATE-AP-STATUS-SEMANTICS-01
```

The product goal explicitly requires:

- real AP unavailable/offline periods;
- when they occurred;
- how long they lasted.

The present Current State mapper proves only:

```text
status_code == 1 → online
other numeric code → other
missing/unusable → unknown
```

Therefore `HOME-AP-24H-01` MUST NOT proceed to implementation or FINAL until the controlled semantics research closes this gap.

The dependency is semantic/research, not a storage dependency. Raw `status_code` is already persisted, so the research itself needs no DB/schema change.

After the research, one canonical shared status mapper MUST be used by:

```text
Current State normalization
HOME-AP-24H historical interpretation
```

No private AP-status mapping is permitted inside HOME-AP-24H.

A second important R2 correction concerns Observation cadence. `OBSERVATION_AP_INTERVAL_SECONDS=30` is a worker schedule delay, **not a guarantee that each AP gets a complete four-section observation every 30 seconds**. The AP dynamic worker is sequential, budgeted, and cursor-rotated. Under default `OBSERVATION_AP_DYNAMIC_MAX_REQUESTS_PER_CYCLE=200`, four dynamic section requests per AP plus inventory overhead bound the number of fully observed APs per run. Sites above that effective capacity naturally produce partial cycles and rotated evidence.

Therefore AP-24H coverage semantics are based on persisted cycle quality and actual per-AP evidence timestamps, not on an invented `30 s per AP` guarantee.

**R2 architecture state:**

```text
Direction: PASS
Implementation: BLOCKED
Mandatory prerequisite: TASK-CURRENT-STATE-AP-STATUS-SEMANTICS-01
```

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

# 8. Observation schedule, capacity and retention

Repository defaults:

```text
OBSERVATION_AP_INTERVAL_SECONDS = 30
OBSERVATION_DYNAMIC_RETENTION_DAYS = 180
OBSERVATION_AP_DYNAMIC_MAX_REQUESTS_PER_CYCLE = 200
OBSERVATION_AP_CYCLE_MAX_DURATION_SECONDS = 120
OBSERVATION_AP_INVENTORY_INTERVAL_SECONDS = 300
OBSERVATION_AP_PAGE_SIZE = 100
```

The `30 s` value is the fixed delay scheduled **after** a dynamic run completes. It is not a per-AP sampling SLA.

Each fully observed AP needs four dynamic requests:

```text
overview
wired_uplink
lan_traffic
radios
```

The same cycle request budget also pays for AP inventory refresh requests when the inventory cache is not reused.

Define:

```text
B = OBSERVATION_AP_DYNAMIC_MAX_REQUESTS_PER_CYCLE
S = number of required dynamic sections = 4
I(c) = inventory requests consumed in cycle c
```

The maximum number of APs that can receive all four dynamic section requests in cycle `c` is bounded by:

```text
full_ap_capacity(c) <= floor((B - I(c)) / S)
```

With cached inventory, the absolute upper bound is:

```text
floor(B / 4)
```

At repository defaults:

```text
floor(200 / 4) = 50 APs
```

Inventory refresh overhead can make the fully observed count lower than 50 for that run. A remainder may permit a partially attempted next AP; such a row is `partial` and does not turn the parent cycle into a complete success.

When the budget/deadline stops a run before all ordered APs are attempted, the worker advances a rotation cursor. Later cycles start from a different AP. Therefore the **effective per-AP evidence cadence** depends on:

- Site AP count;
- request budget;
- inventory cache/refresh cost;
- request latency;
- cycle deadline;
- endpoint failures;
- cursor rotation.

AP-24H MUST treat actual persisted timestamps/cycle quality as truth. It MUST NOT assume one Observation row per AP every 30 seconds.

Dynamic retention remains sufficient for a 24h query and is not changed by this TASK.

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

# 16. Mandatory prerequisite — AP status semantics

The following task is a mandatory prerequisite:

```text
TASK-CURRENT-STATE-AP-STATUS-SEMANTICS-01
```

HOME-AP-24H cannot close its primary product contract until this research establishes how Omada represents a known physical AP-unavailable condition.

The research must determine, with controlled live evidence:

1. whether an unavailable AP remains present in a **complete** Site AP inventory;
2. which raw `status_code` value(s) occur while it is physically unavailable;
3. which transient status values occur during disconnect/reboot/recovery;
4. whether those values are stable/repeatable;
5. whether `last_seen_ms`, controller uptime or other persisted fields are supporting evidence only or necessary to disambiguate;
6. whether the controller instead removes the AP from complete inventory while unavailable.

The accepted research result must define one canonical shared mapper, conceptually:

```text
map_ap_controller_status(status_code)
    -> online | offline | other | unknown
```

If the research proves an additional stable controller state that deserves a distinct canonical device-state classification, it must be explicitly documented rather than inferred by HOME-AP-24H.

The shared mapper must be the only code authority for raw status-code semantics.

HOME-AP-24H must apply that same mapper to historical raw `status_code` rows so that pre-mapper historical rows can be interpreted consistently without rewriting the database. Current State must use the same mapper for newly persisted `status_classification` values.

Historical stored `status_classification` created before the mapper change must not overrule the canonical mapper when raw `status_code` is available.

### Research outcome branch

If controlled testing proves:

```text
AP remains present in complete inventory
+ stable repeatable offline status code exists
```

then HOME-AP-24H can obtain outage history without a schema change.

If controlled testing proves:

```text
AP disappears from otherwise complete inventories while physically unavailable
```

then absence alone cannot be retroactively persisted as a per-AP state row by the current schema. In that case the research MUST return to Owner/Tech Lead with evidence and a separate foundation/storage design may be required before product-complete outage history can be finalized.

The semantics task itself still requires no new DB/schema.

# 17. No hidden status reinterpretation

Forbidden inside HOME-AP-24H:

```text
if status_code == 0: offline
if status_code == 2: offline
if AP missing: offline
```

unless the mandatory semantics task has explicitly proven and approved that meaning.

After the prerequisite closes, HOME-AP-24H imports/uses the same canonical mapper as Current State; it does not copy the mapping table or create a local equivalent.

If raw `status_code` is missing/unusable:

```text
canonical device state = unknown
```

If an AP is absent from a complete successful inventory after the AP has previously been known:

```text
canonical device state = unknown
reason = not_in_complete_inventory
```

unless a later explicitly approved foundation changes that contract.

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

# 29. Historical raw evidence cadence

Current State and Observation have different collection models.

Current State AP inventory:

```text
repository default fixed delay = 60 s after a run
one complete successful inventory cycle is the authoritative device-state sample set
```

Observation AP dynamic:

```text
repository default fixed delay = 30 s after a run
four dynamic endpoint requests per fully observed AP
bounded request budget
bounded cycle deadline
rotation cursor when not all APs fit
```

Therefore AP-24H does not expose or promise a fixed raw per-AP Observation cadence.

For each AP, the backend derives actual evidence timing from persisted rows and parent cycle state.

The browser receives only prepared 15-minute buckets/segments.

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

# 31. Deterministic source gap and effective-cadence semantics

No AP-24H product decision may use an undefined phrase such as `sufficient source evidence`.

## 31.1 Current State authoritative cycle set

For AP device-state history, only cycles matching all of the following are authoritative:

```text
current_state_cycles.kind = 'ap'
current_state_cycles.result = 'success'
current_state_cycles.complete = 1
```

For each such cycle, its `capture_started_at` is the AP-state sample time for the complete Site inventory represented by that cycle.

Partial/failed/shutdown Current State cycles are source-quality evidence only.

## 31.2 Current State gap threshold

Define:

```text
CS_INTERVAL = active CURRENT_STATE_AP_INTERVAL_SECONDS
CS_GAP = max(
    3 * CS_INTERVAL,
    ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS
)
```

This threshold is used only for evidence continuity. It is not an outage threshold.

A canonical sample at `t_i` may carry state forward no later than:

```text
min(t_next, t_i + CS_GAP)
```

If the next authoritative complete inventory occurs later than `t_i + CS_GAP`, the intervening remainder is `unknown/source_gap`.

## 31.3 Observation effective cadence

Observation does **not** derive a per-AP gap threshold from `3 × OBSERVATION_AP_INTERVAL_SECONDS`.

The authoritative complete Observation set is:

```text
observation_cycles.kind = 'ap_dynamic'
state = 'completed'
result = 'success'
complete = 1
```

For a complete-success cycle, every stored AP row used as complete evidence must have:

```text
partial = 0
overview_ok = 1
wired_uplink_ok = 1
lan_traffic_ok = 1
radios_ok = 1
```

The exact per-AP evidence cadence is defined as the actual timestamp sequence persisted for that AP:

```text
effective_ap_evidence_times =
    sorted(observed_at for persisted AP observation rows of that AP)

effective_ap_inter_sample_gap_i =
    effective_ap_evidence_times[i] - effective_ap_evidence_times[i-1]
```

There is intentionally no single configured scalar named `effective_per_ap_cadence`. Under rotation it is a measured sequence, not a promise. Authoritative completeness is determined by parent-cycle quality; diagnostic timing may be summarized by actual inter-sample gaps.

Observation continuity uses the existing Analytics data-quality threshold:

```text
OBS_GAP = ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS
```

Repository default:

```text
180 s
```

This avoids pretending that each AP must be sampled every 30 seconds when request-budget rotation makes that impossible.

## 31.4 Capacity-exceeded condition

Define the absolute cached-inventory upper bound:

```text
OBS_FULL_AP_CAPACITY_UPPER_BOUND =
    floor(
        OBSERVATION_AP_DYNAMIC_MAX_REQUESTS_PER_CYCLE
        / dynamic_section_count
    )
```

where:

```text
dynamic_section_count = 4
```

If the Site roster exceeds this upper bound, a complete four-section dynamic cycle is impossible under the current request budget even with zero inventory-request cost.

AP-24H MUST expose this as source-quality degradation:

```text
reason = observation_cycle_capacity_exceeded
```

It MUST NOT classify any AP as faulty merely because rotation/partial cycles reduce its Observation frequency.

## 31.5 Partial-cycle rows

Rows belonging to completed `partial` cycles may contribute diagnostic facts:

- section problem counts;
- last diagnostic evidence timestamp;
- source-quality timeline.

They do not count as authoritative complete Observation coverage and cannot fill an authoritative source gap.

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

# 35. AP device-state vocabulary after prerequisite

Canonical product values remain:

```text
operational
degraded
unavailable
unknown
```

The mandatory AP-status semantics task must close the raw controller mapping before implementation.

## `operational`

Canonical shared mapper says:

```text
online
```

and the sample comes from a complete successful Current State AP inventory.

## `unavailable`

Canonical shared mapper says:

```text
offline
```

based on controlled, approved Omada semantics research.

No other evidence path may create `unavailable`.

## `degraded`

For v1, this value is permitted only when:

1. the canonical shared device-status contract explicitly defines a controller state as degraded; or
2. a 15-minute AP-state bucket contains both proven operational and proven unavailable intervals while no unknown interval exists, in which case reason is `mixed_state_within_bucket`.

Observation `partial` alone never creates AP device-state `degraded`.

## `unknown`

Use when:

- mapper returns `other` or `unknown`;
- no trustworthy complete Current State cycle exists;
- AP is absent from a complete inventory after previously becoming known;
- source continuity exceeds `CS_GAP`;
- current snapshot freshness is unavailable;
- evidence conflicts or cannot be safely placed.

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

# 37. Authoritative Current State history contract

AP device-state history is constructed only from complete successful Current State AP inventories:

```text
kind='ap'
result='success'
complete=1
```

Each authoritative cycle produces exactly one logical state sample for every AP that is already in the AP-24H historical identity cohort.

Three cases are distinct and MUST stay distinct.

## A. No trustworthy complete cycle exists

For a time span with no authoritative complete Current State cycle and no valid carried-forward sample within `CS_GAP`:

```text
state = unknown
reason = current_state_source_gap
```

This is evidence unavailability.

## B. Complete successful inventory exists but a previously-known AP is absent

For an authoritative complete inventory cycle after the AP has already had `first_evidence_at`, if that AP has no row in the cycle:

```text
state = unknown
reason = not_in_complete_inventory
```

This is NOT:

```text
source gap
offline
```

because the Site inventory itself was successfully completed.

## C. AP was not yet known

Before the AP's first trustworthy presence:

```text
state = unknown
reason = before_first_evidence
coverage_class = short_history
```

That pre-first-evidence portion is not counted as:

- outage;
- problem duration;
- unknown-device-state duration;
- negative availability evidence.

The history-eligible interval begins at:

```text
history_eligible_from = max(window.from_utc, first_evidence_at)
```

## Reappearance case

Sequence:

```text
AP present in complete inventory
→ absent in one or more complete inventories
→ AP present again
```

must produce:

```text
operational/offline/other according to mapper while present
unknown/not_in_complete_inventory while absent
mapped state again after reappearance
```

Absence is never automatically converted into outage.

# 38. 24h AP state summary

Per AP, after the mandatory mapper is available:

```json
{
  "history": {
    "status": "operational|degraded|unavailable|unknown",
    "reason_code": "...",
    "coverage_status": "complete|partial|insufficient_data",
    "history_eligible_from": "...",
    "first_evidence_at": "...",
    "last_evidence_at": "...",
    "authoritative_sample_count": 0,
    "operational_seconds": 0,
    "unavailable_seconds": 0,
    "unknown_evidence_seconds": 0,
    "max_gap_seconds": null
  }
}
```

There is deliberately no generic `coverage_ratio` field in v1.

`operational_seconds` and `unavailable_seconds` are computed from the deterministic bounded step-function in this TASK.

`unknown_evidence_seconds` excludes the pre-`first_evidence_at` short-history interval.

An optional future uptime percentage requires a separate explicit product contract; it is not implied by these fields.

# 39. 24h history status rule

Let the AP history-eligible interval be:

```text
[history_eligible_from, window.to_utc)
```

and let the deterministic Current State state intervals from section 50 cover parts of that interval.

Per-AP `history.status`:

```text
operational
```
when:

- coverage status is `complete`;
- every eligible second is proven operational;
- unavailable seconds = 0;
- unknown evidence seconds = 0.

```text
unavailable
```
when the latest authoritative/current interval is canonically unavailable and current evidence is within its validity window.

```text
degraded
```
when the eligible window contains at least one proven unavailable interval and at least one proven operational interval, with no condition requiring `unknown` precedence.

```text
unknown
```
when:

- coverage is insufficient/partial in a way that prevents a safe overall state conclusion;
- unknown evidence exists materially in the eligible interval;
- the mapper returns other/unknown for required samples;
- source gaps prevent placement.

UI labels may explain the reason but must not downgrade `unknown` into an outage claim.

# 40. Coverage status — deterministic

Coverage describes evidence continuity, not uptime.

There is no `coverage_ratio` in AP-24H v1.

## `complete`

For AP device-state history, after `history_eligible_from`:

1. a valid authoritative state interval starts no later than `history_eligible_from`;
2. every eligible second until `to_utc` is covered by a canonical authoritative state interval;
3. no `current_state_source_gap` interval exists;
4. `not_in_complete_inventory` is a **known evidence result** and therefore does not itself make source coverage incomplete, but it makes AP device state `unknown` for that interval.

Thus source coverage may be complete while device-state conclusion is unknown.

## `partial`

Use when usable authoritative history exists but one or more eligible spans are uncovered because:

- no carry-in/edge sample exists within `CS_GAP`;
- an inter-cycle gap exceeds `CS_GAP`;
- the source starts too late after `history_eligible_from`;
- the source ends too early before `to_utc`;
- Current State source history is shorter than required.

## `insufficient_data`

No usable authoritative Current State AP history exists for the AP/window.

`before_first_evidence` short-history time is outside the eligible interval and is not a coverage failure by itself.

# 41. Newly added / first-known AP

`first_evidence_at` is the first trustworthy complete Current State inventory in retained evidence where the AP is present.

Before that timestamp, complete inventories in the 24h window that do not contain the AP are not interpreted as `not_in_complete_inventory` for this AP, because the AP had not yet entered the known cohort.

Return:

```text
history_eligible_from = first_evidence_at
coverage_class = short_history
reason_code = before_first_evidence
```

The preceding part of the rolling window contributes neither downtime nor unknown-device-state duration.

If retained evidence is too short to prove that the AP was genuinely newly added rather than merely older than retention, wording must remain `short history / first evidence`, not `AP added at`.

# 42. AP absent from latest complete inventory

Once an AP has a trustworthy `first_evidence_at`, absence from any later **complete successful** Current State AP inventory is explicit negative presence evidence but not an offline classification.

Current state:

```text
status = unknown
reason = not_in_complete_inventory
```

Historical status follows the same rule for that sample/interval.

A sequence of several complete inventories without the AP remains:

```text
unknown/not_in_complete_inventory
```

until the AP reappears or a separately approved semantics/foundation contract proves that absence itself is canonical offline evidence.

# 43. Current State partial/failed/shutdown cycles

Cycles with:

```text
result != 'success'
or complete != 1
```

are never authoritative AP device-state samples.

They affect source/evidence quality only.

They may explain why an authoritative continuity gap exists, but they do not produce:

```text
offline
unavailable
not_in_complete_inventory
```

for any AP.

`not_in_complete_inventory` is valid only when the **Site AP inventory cycle itself is complete and successful**.

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

The API returns a fixed 96-bucket rolling timeline per AP page.

```text
window = 24 h
bucket = 15 min = 900 s
bucket_count = 96
```

Bucket boundaries are anchored to `window.from_utc`.

Each bucket is backend-prepared and contains:

```json
{
  "from_utc": "...",
  "to_utc": "...",
  "ap_state": "operational|degraded|unavailable|unknown",
  "ap_state_reason": "...",
  "observation_quality": "operational|degraded|unavailable|unknown",
  "observation_reason_codes": [],
  "operational_seconds": 0,
  "unavailable_seconds": 0,
  "unknown_evidence_seconds": 0,
  "short_history_seconds": 0,
  "authoritative_state_sample_count": 0,
  "complete_observation_sample_count": 0,
  "diagnostic_partial_observation_sample_count": 0
}
```

The browser renders; it does not classify.

# 50. Deterministic AP-state interval and bucket algorithm

This section is normative.

## 50.1 Input rows

Query authoritative complete successful Current State AP cycles for:

```text
[window.from_utc - CS_GAP, window.to_utc)
```

The lookback exists only to obtain a possible carry-in state at the left edge.

For each complete cycle at time `t_i` and each AP that has already entered the known cohort:

```text
AP row present
→ map raw status_code through canonical shared mapper

AP row absent
→ unknown / not_in_complete_inventory
```

Before `first_evidence_at`, state is `unknown/before_first_evidence` and is marked short-history, not eligible history.

## 50.2 Step-function validity

For a state sample at `t_i`, let `t_next` be the next authoritative complete inventory time.

Its evidence is valid on:

```text
[t_i, min(t_next, t_i + CS_GAP, window.to_utc))
```

If `t_next > t_i + CS_GAP`, then:

```text
[t_i + CS_GAP, t_next)
→ unknown / current_state_source_gap
```

The same rule applies at the right edge: the final sample cannot be carried later than `t_i + CS_GAP`.

A pre-window carry-in sample may cover from `window.from_utc` only when:

```text
window.from_utc - t_i <= CS_GAP
```

## 50.3 Bucket reduction

Intersect these deterministic intervals with each 15-minute bucket.

Accumulate seconds by class:

```text
operational_seconds
unavailable_seconds
unknown_evidence_seconds
short_history_seconds
```

`degraded` is not stored as duration unless the canonical mapper itself defines a degraded state; if it does, add an equivalent explicit `degraded_seconds` field in FINAL.

Bucket AP state is:

1. `unknown` if any eligible bucket seconds are unknown;
2. else `degraded` if both operational and unavailable seconds are > 0;
3. else `unavailable` if unavailable seconds > 0 and operational seconds = 0;
4. else `operational` if operational seconds cover all eligible bucket seconds;
5. else `unknown`.

A bucket containing only pre-first-evidence time is:

```text
ap_state = unknown
ap_state_reason = before_first_evidence
short_history_seconds = 900
```

but is excluded from AP problem-duration totals.

# 51. Deterministic Observation-quality bucket algorithm

Observation quality uses a separate axis.

## 51.1 Complete authoritative Observation row

A row is complete authoritative Observation evidence only when:

```text
parent cycle:
  kind='ap_dynamic'
  state='completed'
  result='success'
  complete=1

row:
  partial=0
  overview_ok=1
  wired_uplink_ok=1
  lan_traffic_ok=1
  radios_ok=1
```

## 51.2 Diagnostic partial evidence

Rows from completed partial cycles or rows with `partial=1` may contribute diagnostic reason counts but cannot make a bucket source-complete.

## 51.3 Bucket reduction

For each 15-minute bucket after AP first evidence:

- if the Observation source itself cannot be read → `unavailable`;
- else if any applicable partial/section-failure evidence exists → `degraded`;
- else if complete authoritative rows exist and their continuity does not contain a gap > `OBS_GAP` → `operational`;
- else → `unknown`.

If the Site roster exceeds `OBS_FULL_AP_CAPACITY_UPPER_BOUND`, source-level reason includes:

```text
observation_cycle_capacity_exceeded
```

and missing/rotated AP rows in partial cycles are never interpreted as AP faults.

No AP device-state field is modified by Observation-quality classification.

# 52. Duration semantics

AP-24H distinguishes exact backend interval accounting from physical certainty.

After the canonical offline mapper is proven, the deterministic Current State step-function may expose:

```text
operational_seconds
unavailable_seconds
unknown_evidence_seconds
```

within the history-eligible interval.

`unavailable_seconds` is the product outage-duration evidence required by HOME-AP-24H, subject to the canonical mapper and the `CS_GAP` validity rule.

Observation quality duration is bucketed/presentation evidence and may expose:

```text
observation_degraded_bucket_count
observation_degraded_bucket_seconds
```

Unknown/source-gap time MUST be labelled as evidence unknown, never downtime.

Pre-first-evidence short history is reported separately and excluded from both outage and unknown-problem totals.

No uptime percentage is introduced in v1.

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

# 55. Pagination and canonical cursor contract

The Site summary covers the full Site AP roster for the anchored 24h window.

Per-AP items are paginated.

DRAFT R2 proposal:

```text
default limit = 25 APs
maximum limit = 50 APs
sort = canonical ap_mac ascending
```

The implementation MUST reuse/extend:

```text
app/admin_web/cursors.py
```

No second cursor codec is allowed.

The existing versioned Site/filter-bound codec may be extended with a canonical MAC identity kind if needed.

For AP-24H, cursor context must bind at minimum:

```text
kind = home_ap_24h
site_id
evaluation/window anchor
limit
query/contract version
last AP MAC
```

Recommended binding:

```text
timestamp field = evaluated_at_utc/window.to_utc
identity = last canonical AP MAC
filters fingerprint includes:
  limit
  contract_version
  fixed window kind / bucket contract
```

The first page resolves one immutable:

```text
evaluated_at_utc
from_utc
to_utc
```

Subsequent pages decode that same anchor from the cursor and MUST NOT recalculate `now`.

Malformed, non-canonical, wrong-Site, wrong-kind, wrong-contract or context-mismatched cursor:

```text
400 invalid_request
```

There is no fallback to page 1.

# 56. Existing AP source capacity

Current source capacity is bounded and must be represented honestly.

Current State repository defaults permit up to 500 AP rows per inventory run, subject to page/time limits.

Observation dynamic capacity is different because each full AP observation costs four section requests.

At default dynamic request budget:

```text
B = 200
S = 4
cached-inventory absolute full-AP upper bound = 50
```

An inventory refresh consumes part of that same budget and can reduce full-AP capacity for that run.

When AP count exceeds the effective full-cycle capacity:

- Observation cycles become partial;
- the rotation cursor advances;
- different APs receive evidence on different runs;
- per-AP evidence cadence stretches;
- AP-24H reports source degradation/partial Observation coverage;
- missing AP Observation rows are not AP-fault evidence.

The task does not increase the collector budget or cadence.

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

Conceptual R2 response:

```json
{
  "ap_mac": "AA:BB:CC:DD:EE:FF",
  "name": "AP name",
  "model": "EAP613",
  "identity_source": "current_state",

  "current": {
    "status": "operational|degraded|unavailable|unknown",
    "reason_code": "fresh_online_evidence",
    "observed_at": "...",
    "freshness_status": "fresh"
  },

  "history": {
    "status": "operational|degraded|unavailable|unknown",
    "reason_code": "...",
    "coverage_status": "complete|partial|insufficient_data",
    "history_eligible_from": "...",
    "first_evidence_at": "...",
    "last_evidence_at": "...",
    "authoritative_sample_count": 0,
    "operational_seconds": 0,
    "unavailable_seconds": 0,
    "unknown_evidence_seconds": 0,
    "short_history_seconds": 0,
    "max_gap_seconds": null,
    "current_vs_24h": "consistent_with_24h"
  },

  "observation_quality": {
    "status": "operational|degraded|unavailable|unknown",
    "reason_code": null,
    "complete_sample_count": 0,
    "diagnostic_partial_sample_count": 0,
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

There is no field named:

```text
coverage_ratio
uptime_percent
```

in v1.

Outage duration is expressed only through proven `unavailable_seconds` after the mandatory semantics prerequisite closes.

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

# 71. Independent feature flag, refresh and request timeout

AP-24H is an independently rollable Home component.

Add safe-disabled default:

```text
WEB_ADMIN_HOME_AP_24H_ENABLED=false
```

It MUST NOT inherit enablement from:

```text
Home Live
Home Traffic
Home Activity
Home Health
```

Proposed independent refresh contract:

```text
WEB_ADMIN_HOME_AP_24H_REFRESH_SECONDS=120
```

Recommended validation bounds:

```text
60..600 seconds
```

Proposed independent browser request timeout:

```text
WEB_ADMIN_HOME_AP_24H_REQUEST_TIMEOUT_SECONDS=20
```

Recommended validation bounds:

```text
5..60 seconds
```

The request timeout MUST be strictly greater than:

```text
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS
```

matching the existing Home component safety pattern.

Frontend behavior:

- no overlapping AP-24H requests;
- refresh only when the component is enabled;
- one failed refresh preserves independent component error state and does not stop other Home refresh loops.

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

# 76. AP-24H rollout feature boundary

Required repository-default rollout gate:

```text
WEB_ADMIN_HOME_AP_24H_ENABLED=false
```

Rules:

- `false` → no AP-24H Home block fetch/render activation;
- `true` → AP-24H runtime/query path may activate if its own required sources are available;
- source unavailability does not disable Admin or other Home modules;
- enabling AP-24H does not mutate any existing Home flag;
- disabling AP-24H does not disable Current State/Observation collectors.

The feature flag requires Admin Web itself to be enabled, but it does not require Home Live/Traffic/Activity/Health flags to be true.

Production rollout of this flag remains Owner-controlled after FINAL + prerequisite + Central Lab acceptance.

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

| Displayed meaning | Source | R2 status |
|---|---|---|
| AP identity / current inventory | Current State complete successful AP cycles | YES |
| Raw AP controller status | Current State `status_code` | YES |
| Canonical online/offline mapping | Mandatory `TASK-CURRENT-STATE-AP-STATUS-SEMANTICS-01` | **PREREQUISITE** |
| Current positive online state | shared mapper over Current State raw status | after prerequisite |
| Current real offline state | shared mapper over Current State raw status | after prerequisite if controller exposes it |
| 24h state intervals | authoritative Current State complete cycles + shared mapper | after prerequisite |
| 24h outage duration | deterministic state intervals | after prerequisite if offline mapping proven |
| AP absence in complete inventory | Current State complete cycle membership | YES → `unknown/not_in_complete_inventory` |
| Current State source gaps | Current State cycle history | YES |
| AP Observation complete/partial | Observation AP rows + parent cycles | YES |
| Observation endpoint completeness | `overview_ok`, `wired_uplink_ok`, `lan_traffic_ok`, `radios_ok` | YES |
| Observation cycle partial/failed | Observation cycles | YES |
| Observation capacity pressure | config + cycle quality/roster | YES |
| AP CPU / memory history | Observation | YES |
| Radio utilization history | Observation radio rows | YES |
| Radio error/retry/drop counters | Observation radio rows | YES |
| Wired/LAN counters/rates | Observation AP rows | YES |
| Physical wired/radio fault state | current stored facts | **NO canonical fault threshold contract** |
| Home current AP list | existing Home Live | YES, separate accepted contract |

# 82. What existing storage already supports

Without new collection/storage, the existing data model already supports:

1. rolling 24h Site/AP roster;
2. raw Current State AP status history;
3. Current State complete/partial/failed cycle quality;
4. explicit AP presence/absence in complete inventories;
5. source gaps and edge coverage;
6. short/first-evidence history;
7. Observation complete/partial history;
8. per-section Observation degradation counts;
9. Observation capacity-pressure handling;
10. Site summary and per-AP summaries;
11. prepared 15-minute timeline;
12. Site-aware pagination;
13. independent fail-open Home behavior;
14. source provenance/quality;
15. retrospective reclassification of historical raw `status_code` through a shared mapper.

The missing requirement is semantic proof, not raw persistence.

# 83. Mandatory implementation gate

Product-complete HOME-AP-24H MUST NOT be implemented before:

```text
TASK-CURRENT-STATE-AP-STATUS-SEMANTICS-01
```

has an accepted result.

Before that research, the repository does not justify:

```text
AP unavailable/offline
outage start/end
outage duration
```

The R1 notion of shipping a partial HOME-AP-24H without outage semantics is removed from the delivery path.

If the research proves a stable offline status mapping, HOME-AP-24H may proceed without schema migration.

If the research proves that physical unavailability is represented only by AP disappearance from complete inventory, Owner/Tech Lead must decide the additional foundation/storage contract before HOME-AP-24H FINAL.

# 84. Test plan — canonical source semantics

After prerequisite closure, at minimum:

1. shared mapper baseline-online code → `online`.
2. proven offline code → `offline`.
3. unproven numeric code → `other`.
4. missing/unusable code → `unknown`.
5. HOME-AP-24H and Current State use the same mapper implementation.
6. historical raw status rows are interpreted through the same mapper.
7. old persisted `status_classification='other'` cannot suppress a newly proven raw offline code.
8. partial Current State cycle creates no AP-state sample.
9. failed Current State cycle creates no AP-state sample.
10. complete inventory with previously-known AP absent → unknown/not-in-complete-inventory.
11. several complete absences then reappearance remain unknown in the absence interval, not outage.
12. Observation `partial=true` changes Observation quality only.
13. radios/wired/LAN/overview section failure never creates AP offline state.

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

# 86. Test plan — authoritative coverage/gaps

19. continuous complete Current State cycles inside `CS_GAP` → complete evidence continuity.
20. missing left-edge carry-in → partial coverage.
21. missing right-edge continuation beyond `CS_GAP` → partial coverage.
22. inter-cycle gap > `CS_GAP` → explicit source-gap interval.
23. partial cycle between two complete cycles cannot fill the gap.
24. failed cycle cannot fill the gap.
25. AP first seen 3h into window → `history_eligible_from=first_evidence_at`; prior 21h is short history, not outage/unknown problem duration.
26. complete inventory after first evidence but AP absent → state unknown, source coverage may still be complete.
27. AP absent for multiple complete inventories then reappears → unknown interval then mapped state.
28. no authoritative samples → insufficient data.
29. no `coverage_ratio` appears in payload.
30. source gap is never converted to unavailable AP state.

# 87. Test plan — Observation quality and capacity rotation

31. all four sections complete in complete-success cycle → complete Observation evidence.
32. one wired section false → degraded Observation evidence only.
33. one radio section false → degraded Observation evidence only.
34. mixed complete+partial diagnostics in bucket → Observation quality degraded.
35. cycle partial due request budget → source degraded/partial.
36. Site AP count greater than `floor(B/4)` → `observation_cycle_capacity_exceeded` source reason.
37. rotation cursor causes AP A to be observed this run and AP B next run → neither missing row is called AP fault.
38. AP row from partial cycle is diagnostic and does not fill authoritative complete coverage.
39. Observation source unavailable → Observation quality unavailable, AP device state unchanged.
40. section failure counts aggregate correctly.

# 88. Test plan — current vs history

36. current online + complete online 24h → consistent.
37. current unknown + prior complete online history → current_less_certain.
38. partial history → history_insufficient.
39. no history → history_insufficient.
40. recent AP → history_insufficient/recent.
41. no arbitrary "abnormal" score emitted.

---

# 89. Test plan — Site/multi-AP and cursor

45. one AP.
46. two APs.
47. 25 APs.
48. > one AP response page.
49. AP present only in Current State is included.
50. AP present only in Observation can appear in roster but has Current State device state unknown until trustworthy Current State evidence exists.
51. historical AP absent from latest inventory remains included.
52. same AP MAC in different Site cannot leak.
53. existing Admin cursor codec is used/extended, not duplicated.
54. cursor kind mismatch → 400.
55. cursor Site mismatch → 400.
56. cursor window/evaluation anchor mismatch → 400.
57. cursor limit/query-contract mismatch → 400.
58. malformed/non-canonical cursor → 400.
59. no cursor error falls back to first page.
60. second page preserves the exact first-page 24h window anchor.
61. deterministic AP-MAC ordering.
62. Site summary covers all Site APs, not only returned page.

# 90. Test plan — performance

63. DB query count does not grow linearly with AP count.
64. no per-AP SQL loop.
65. Current State complete-cycle query uses Site/kind/time indexes.
66. Observation Site/time query uses existing indexes.
67. backend does not materialize full raw 30s histories into Admin response.
68. query deadline interruption works.
69. response remains within Admin max bytes.
70. page max bound enforced.
71. frontend refresh does not overlap.
72. disabled AP-24H flag causes no AP-24H polling.
73. AP-24H request timeout is greater than server query deadline.

# 91. Capacity benchmark model

Central Lab uses two different fixture classes and MUST NOT conflate them.

## 91.1 Production-contract collector fixtures

Use collector behavior that respects:

```text
OBSERVATION_AP_DYNAMIC_MAX_REQUESTS_PER_CYCLE
four dynamic section requests/AP
inventory request overhead
cycle deadline
rotation cursor
partial cycles
```

Profiles should include at least:

```text
1 AP
2 APs
25 APs
50 APs
51 APs
100 APs
```

The `51+` profiles explicitly verify capacity pressure/rotation semantics.

## 91.2 Query-capacity stress fixture

A synthetic dense 500-AP × 24h history MAY be generated to stress SQL aggregation/storage/read bounds.

It must be labelled exactly as a:

```text
query-capacity stress fixture
```

It is NOT a claim that the current Observation collector produces a complete four-section sample for each of 500 APs every 30 seconds.

Dense synthetic row counts may still be used to prove that the AP-24H query path remains bounded under worst-case persisted volume.

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
<= 5 s 500-AP query-capacity stress fixture page
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

# 93. Fail-open and feature-gate tests

74. `WEB_ADMIN_HOME_AP_24H_ENABLED=false` → AP-24H component not activated/fetched.
75. enabling AP-24H does not alter Home Live flag.
76. enabling AP-24H does not alter Home Traffic flag.
77. enabling AP-24H does not alter Home Activity flag.
78. enabling AP-24H does not alter Home Health flag.
79. AP-24H 503 does not fail Home HTML.
80. AP-24H 503 does not stop other Home refresh loops.
81. Current State unavailable + Observation available → 200 degraded partial block when safe useful payload exists.
82. Observation unavailable + Current State available → 200 degraded partial block when safe useful payload exists.
83. both required sources unavailable → AP-24H endpoint 503 only.
84. query deadline → AP-24H endpoint 503 only.
85. concurrency limit → 429 only for AP-24H request.
86. invalid AP-24H timeout/refresh config follows Admin safe configuration validation.

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

Owner + Tech Lead Central Lab performs the official exact-artifact acceptance:

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

Before AP-24H activation, Owner/Tech Lead records:

```text
deployed commit SHA

mandatory semantics task:
  accepted result ID/report
  canonical mapper version/contract

Current State:
  state
  schema version
  AP enabled
  AP interval
  history retention
  latest complete-success AP cycle

Observation:
  state
  schema version
  AP enabled
  AP interval
  dynamic request budget
  dynamic section count
  dynamic retention
  latest ap_dynamic cycle quality
  current Site AP roster count
  cached-inventory full-AP upper bound

Admin AP-24H:
  WEB_ADMIN_HOME_AP_24H_ENABLED
  refresh seconds
  request timeout seconds
  max query duration
  max response bytes
  max concurrent queries
```

No source collection setting is changed merely to satisfy this precheck.

# 98. Production forward acceptance

For the real Site after FINAL/Central Lab:

1. AP-24H flag activates only this component.
2. endpoint authenticates and enforces exact Site.
3. rolling window is exactly 24h UTC `[from,to)`.
4. expected AP identities appear.
5. current mapped status agrees with the accepted semantics report.
6. a controlled approved AP outage produces canonical unavailable evidence only through the shared mapper.
7. outage start/end placement follows complete Current State cycle timing and `CS_GAP` rules.
8. unavailable duration is generated by the deterministic backend interval algorithm.
9. source gaps remain unknown and are not added to outage duration.
10. complete-inventory AP absence remains unknown/not-in-complete-inventory unless the prerequisite result explicitly led to another approved foundation contract.
11. Observation partial/capacity pressure appears only on the Observation-quality axis.
12. recently/first-seen AP gets short-history semantics.
13. query latency is within budget.
14. response size is within bound.
15. other Home panels remain functional if AP-24H is forced to fail.

# 99. Production outage acceptance dependency

Unlike R1, product-complete production acceptance now **requires** the AP-status semantics prerequisite to have been closed before HOME-AP-24H implementation begins.

The physical outage experiment itself belongs to:

```text
TASK-CURRENT-STATE-AP-STATUS-SEMANTICS-01
```

HOME-AP-24H production acceptance does not rediscover status codes. It verifies that the already-approved canonical mapper is correctly reflected in:

```text
current state
24h timeline
outage duration
current-vs-history context
```

If the semantics research outcome required an additional foundation/storage task, HOME-AP-24H production acceptance remains blocked until that dependency is also closed.

# 100. Rollout boundary

This R2 DRAFT does not authorize rollout.

Required gate order:

```text
1. TASK-CURRENT-STATE-AP-STATUS-SEMANTICS-01 research accepted
2. any dependency discovered by that research closed
3. TASK-HOME-AP-24H-01 FINAL approved
4. coder focused/module implementation tests
5. exact candidate artifact to Owner + Tech Lead Central Lab gate
6. Central Lab PASS
7. Owner-controlled production deploy
8. WEB_ADMIN_HOME_AP_24H_ENABLED=true only after verification window begins
```

No schema migration is part of the expected happy path.

Rollback first disables the independent AP-24H feature flag; code rollback follows normal release procedure if required.

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

# 105. DRAFT R2 decisions fixed before FINAL

The following R2 requirements are no longer optional:

1. `TASK-CURRENT-STATE-AP-STATUS-SEMANTICS-01` is mandatory prerequisite.
2. no private HOME-AP-24H status mapping.
3. Current State device-state history uses complete-success AP cycles only.
4. AP absence in complete inventory is unknown, not offline.
5. pre-first-evidence time is short history, not problem duration.
6. Observation `30 s` is not a per-AP cadence guarantee.
7. request budget + four dynamic sections + rotation cursor are part of capacity semantics.
8. Site above dynamic capacity yields source degradation, not AP fault.
9. 15-minute / 96-bucket proposal remains.
10. `coverage_ratio` is removed from v1.
11. existing Admin cursor codec must be reused/extended.
12. independent safe-disabled AP-24H feature flag is required.
13. independent refresh=120 s proposal is retained.
14. independent request-timeout contract is required.

Remaining FINALization input comes primarily from the accepted status-semantics research result.

# 106. Final architectural conclusion — R2

Repository/storage finding:

> **B. Existing data/storage is sufficient for the read model, but product-complete HOME-AP-24H is blocked by mandatory AP status semantics research.**

This is not a request for a new AP-history database.

Already present:

```text
raw historical Current State status_code
complete/partial Current State inventories
Observation AP dynamic history
Observation section quality
24h-compatible retention
Site/time indexes
```

Mandatory missing contract:

```text
verified Omada physical unavailable → canonical status semantics
```

Therefore implementation authorization is:

```text
BLOCKED
```

until:

```text
TASK-CURRENT-STATE-AP-STATUS-SEMANTICS-01
```

is accepted.

If that research proves a stable offline status code while the AP remains represented in complete inventory:

```text
HOME-AP-24H can proceed without schema/storage change.
```

If it proves that physical unavailability is represented only by AP disappearance from otherwise complete inventories:

```text
research returns evidence to Owner/Tech Lead;
additional foundation/storage semantics may be required before FINAL.
```

Observation capacity does not block the read model, but it constrains evidence quality. AP-24H must report request-budget rotation/partial coverage honestly and never turn collector capacity pressure into an AP fault.

# 107. Required next step

Do NOT begin HOME-AP-24H implementation from this R2 DRAFT.

Next sequence:

```text
1. Review/approve TASK-HOME-AP-24H-01-DRAFT-R2.md
2. Execute/finalize TASK-CURRENT-STATE-AP-STATUS-SEMANTICS-01
   under explicit Owner-controlled live-test authorization
3. Record accepted canonical mapper / outcome
4. Reconcile any dependency discovered by the research
5. Prepare TASK-HOME-AP-24H-01-FINAL.md
6. Only then authorize implementation
```

This R2 itself does not authorize:

```text
branch creation
code changes
PR
deploy
production flag activation
physical AP disruption
```

