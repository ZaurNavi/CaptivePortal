# TASK-HOME-AP-24H-01 — 24-hour AP status/history block for Admin Home — FINAL

**Project:** CaptivPortal  
**Area:** Admin Console → Home → Access Point 24h History  
**Type:** Product read model / Analytics + Admin composition  
**Status:** FINAL — superseding revision after accepted Phase R Outcome A; implementation remains BLOCKED only by accepted Phase M shared mapper artifact  
**Implementation authorization:** BLOCKED until Owner + Tech Lead accept the exact Phase M shared mapper artifact/handoff  
**Production activation:** NOT GRANTED  
**Prepared:** 2026-08-28  
**Exact repository baseline:** `origin/main@bc929dbe7c1687415bd4eeda971dcbc9376d8bbc`  
**Baseline commit:** `TASK-OMADA-WEBHOOK-TRAFFIC-BYTES-01 — accept Omada Bytes traffic alias`  
**Supersedes:** previous `TASK-HOME-AP-24H-01-FINAL.md` issued before accepted AP-status research outcome  

---

# 0. Executive decision

`HOME-AP-24H-01` remains a separate Site-aware Home read model whose product goal is a truthful rolling 24-hour AP availability/history picture.

The approved architecture remains:

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

The mandatory AP-status research dependency is now **RESOLVED**.

Owner + Tech Lead accepted:

```text
TASK-CURRENT-STATE-AP-STATUS-SEMANTICS-01
Phase R — Outcome A VERIFIED
```

Accepted canonical semantics for the current production compatibility tuple:

```text
raw 1        → online
raw 0        → offline
other int    → other
missing/bad  → unknown

raw 3        → other
```

The physically powered-off AP remained present in complete successful Site AP inventories, so no absence-based foundation or new storage is required.

The remaining delivery gate is implementation/acceptance of one shared mapper artifact:

```text
TASK-CURRENT-STATE-AP-STATUS-SEMANTICS-01-PHASE-M-FINAL
```

HOME-AP-24H MUST use that exact shared mapper for historical raw `status_code`.

No private AP-status mapping is permitted inside HOME-AP-24H.

Observation cadence is governed by the collector-capacity contract. `OBSERVATION_AP_INTERVAL_SECONDS=30` is a worker schedule delay, **not a guarantee that each AP gets a complete four-section observation every 30 seconds**. The AP dynamic worker is sequential, budgeted, and cursor-rotated. Under default `OBSERVATION_AP_DYNAMIC_MAX_REQUESTS_PER_CYCLE=200`, four dynamic section requests per AP plus inventory overhead bound the number of fully observed APs per run. Sites above that effective capacity naturally produce partial cycles and rotated evidence.

Therefore AP-24H coverage semantics are based on persisted cycle quality and actual per-AP evidence timestamps, not on an invented `30 s per AP` guarantee.

**FINAL architecture state:**

```text
Direction: PASS

Phase R:
ACCEPTED — Outcome A VERIFIED

Storage/schema dependency:
NONE

Implementation:
BLOCKED ONLY BY accepted Phase M shared mapper artifact
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

Observation cycle state/result is separate from AP state **and separate from AP-local row quality**.

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
- storage/worker issue;
- later APs were not reached because the bounded request budget/deadline was exhausted.

It MUST NOT be translated into:

```text
all APs were offline
all AP rows in the cycle are incomplete
```

Normative separation:

```text
AP-local Observation quality
!=
Site/source cycle quality
```

A persisted AP row from a parent `ap_dynamic` cycle whose overall result is `partial` MAY still be complete AP-local evidence for that AP when the row itself proves all four dynamic sections succeeded.

Conversely, the parent cycle remains Site/source-quality degradation and explains why some other AP rows may be absent.

A parent-cycle `partial` therefore:

- contributes to Site/source metadata;
- may explain rotation/budget omissions;
- never turns a missing AP row into AP fault;
- does NOT automatically downgrade a fully successful AP-local row.

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

# 14. Accepted canonical AP status semantics

Phase R Outcome A is accepted.

For the tested current-production compatibility tuple:

```text
Omada Controller:
5.14.32.3

AP:
EAP613(EU) v1.0

Firmware:
1.8.3 Build 20260617 Rel. 36045

Site:
Home
```

the canonical mapper contract is:

```text
raw status == 1  → online
raw status == 0  → offline
other integer    → other
missing/unusable → unknown
```

Explicit transition evidence:

```text
raw status == 3
→ other
```

`3` is NOT offline.

The AP remained present in complete successful inventory during both accepted outage runs.

Therefore:

```text
raw 0 is sufficient canonical controller-observed unavailable evidence
```

and no absence-based persistence foundation is required.

The exact repository baseline still contains the pre-mapper local normalizer behavior until Phase M is implemented; this is now an implementation gap, not a semantic uncertainty.

# 15. Controller-observed availability semantics and latency

HOME-AP-24H describes:

```text
controller-observed availability
```

not instantaneous physical/electrical AP state.

Canonical `unavailable` begins only when an authoritative Current State sample from a complete-success AP cycle contains a raw code that the accepted shared mapper classifies as:

```text
offline
```

For the accepted mapping:

```text
raw 0 → offline
```

The physical power-off timestamp is NOT the start of `unavailable_seconds`.

`lastSeen` is NOT the start.

The first missed-heartbeat/transition status is NOT the start.

`raw 3` is NOT the start.

Run #3 canonical latency evidence demonstrates why.

Physical OFF:

```text
2026-08-27T22:06:58.426Z
```

Transition `1 → 3`:

```text
40.005 s < latency <= 50.128 s
```

First stable `0`:

```text
590.064 s < latency <= 599.960 s
```

approximately:

```text
9m50s–10m00s
```

after physical power loss.

Physical ON:

```text
2026-08-27T22:21:58.511Z
```

First recovered `1`:

```text
2026-08-27T22:24:38.435Z
```

approximately:

```text
2m30s–2m40s
```

later.

Therefore all AP-24H labels, API semantics and documentation MUST avoid implying electrical-time precision.

Preferred wording:

```text
Controller-observed unavailable
Controller-observed availability
```

Run #2 proves repeatability of `0=offline`, but its retained excerpt MUST NOT be used as the canonical numeric detection-latency SLA.

# 16. Resolved research dependency and remaining Phase M gate

The research dependency is closed:

```text
Phase R:
ACCEPTED

Outcome:
A — VERIFIED
```

Accepted findings:

```text
AP remains present in complete successful inventory during power loss

1 → online
0 → offline
3 → other
other int → other
missing/unusable → unknown
```

Rejected as active delivery dependencies:

```text
Pattern B absence-based foundation
Pattern C unresolved semantics
new AP status storage
new schema
```

The only remaining AP-status gate is:

```text
accepted Phase M shared mapper artifact
```

Phase M must provide one authority, expected by its own FINAL contract at:

```text
app/current_state/ap_status.py
classify_ap_status_code(raw_status)
```

HOME-AP-24H implementation MUST remain blocked until Owner + Tech Lead accept that exact mapper artifact/handoff.

After mapper acceptance, no additional AP-status research/architecture round is required unless implementation evidence materially contradicts the accepted contract.

# 17. Shared mapper authority — no private reinterpretation

HOME-AP-24H MUST import/use the accepted Phase M shared mapper.

Canonical behavior:

```text
1        → online
0        → offline
3        → other
other int→ other
None/bad → unknown
```

Forbidden inside HOME-AP-24H:

```text
if status_code == 0: ...   # duplicated private mapper
not 1 → offline
AP missing → offline
lastSeen heuristic → offline
uptime heuristic → offline
3 → offline
```

Historical Current State rows are interpreted from:

```text
raw status_code
→ shared mapper
```

even if an old source-era row still contains:

```text
status_classification='other'
```

for raw `0`.

No backfill is required.

If an AP is absent from a complete successful inventory after it has previously been known:

```text
device state = unknown
reason = not_in_complete_inventory
```

Accepted Outcome A does NOT change absence semantics.

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

## 31.3 Observation effective cadence and AP-local authority

Observation does **not** derive a per-AP evidence cadence from `3 × OBSERVATION_AP_INTERVAL_SECONDS`.

AP-local complete Observation evidence is row-local.

A persisted AP row is complete AP-local evidence when all are true:

```text
parent cycle:
  kind = 'ap_dynamic'
  state = 'completed'
  row was durably stored

row:
  partial = 0
  overview_ok = 1
  wired_uplink_ok = 1
  lan_traffic_ok = 1
  radios_ok = 1
```

The parent cycle MAY be either:

```text
result='success', complete=1
```

or:

```text
result='partial', complete=0
```

A parent `partial` result does not invalidate an otherwise complete AP-local row.

The exact per-AP evidence cadence is the actual timestamp sequence of complete AP-local rows:

```text
effective_ap_evidence_times =
    sorted(
        observed_at
        for persisted rows of that AP
        where AP-local complete predicate is true
    )

effective_ap_inter_sample_gap_i =
    effective_ap_evidence_times[i] - effective_ap_evidence_times[i-1]
```

There is intentionally no configured scalar named `effective_per_ap_cadence`.

Under request-budget rotation, it is a measured sequence, not a promise.

Site/source-cycle quality is evaluated separately from AP-local row quality:

```text
parent partial
→ Site/source degradation evidence

AP-local complete row inside that parent
→ complete evidence for that AP at that timestamp

AP absent because it was not reached
→ no AP-local sample; NOT AP fault
```

Observation continuity uses the existing Analytics data-quality threshold:

```text
OBS_GAP = ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS
```

Repository default:

```text
180 s
```

A gap larger than `OBS_GAP` means AP-local Observation evidence continuity is incomplete. It does not mean the AP failed.

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

## 31.5 Rows from partial parent cycles

Rows from a completed parent cycle with:

```text
result='partial'
complete=0
```

are classified by their own row-local evidence.

### AP-local complete row inside partial parent

If:

```text
row.partial = 0
overview_ok = 1
wired_uplink_ok = 1
lan_traffic_ok = 1
radios_ok = 1
```

then the row:

- IS complete AP-local Observation evidence;
- MAY fill AP-local evidence continuity at its `observed_at`;
- MAY contribute to an AP-local operational Observation-quality bucket;
- does NOT make the Site/source cycle healthy.

The parent-cycle partial result remains visible in Site/source-quality metadata.

### AP-local partial row

If the row itself is partial or any required section flag is false, it is diagnostic/degraded AP-local evidence.

### Missing row

If the AP has no row because request-budget rotation did not reach it:

```text
no AP-local evidence exists for that AP at that cycle
```

The missing row is not fault evidence and is never synthesized as a partial AP row.

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

# 35. Canonical AP device-state vocabulary

Canonical product values:

```text
operational
degraded
unavailable
unknown
```

## `operational`

Authoritative complete-success Current State sample contains the AP and:

```text
shared mapper(status_code) == online
```

For accepted production semantics:

```text
raw 1 → operational
```

## `unavailable`

Authoritative complete-success Current State sample contains the AP and:

```text
shared mapper(status_code) == offline
```

For accepted production semantics:

```text
raw 0 → unavailable
```

This means:

```text
Controller-observed unavailable
```

not the precise physical power-loss instant.

No other evidence path may create `unavailable`.

## `degraded`

For v1, device-state `degraded` is used only for a mixed resolved bucket:

```text
some eligible seconds operational
+
some eligible seconds unavailable
+
zero eligible unknown seconds
```

with:

```text
reason = mixed_state_within_bucket
```

The accepted shared mapper itself has no canonical `degraded` output.

Observation partial/degraded never creates AP device-state degraded.

## `unknown`

Use when:

- mapper returns `other`;
- mapper returns `unknown`;
- raw `3` is present;
- no trustworthy complete Current State cycle exists;
- AP is absent from a complete inventory after becoming known;
- source continuity exceeds `CS_GAP`;
- current snapshot evidence is too stale/unavailable;
- evidence cannot be safely placed.

`other` remains an internal canonical mapper output and becomes product device-state `unknown` in AP-24H.

# 36. Observation quality vocabulary

AP-24H exposes two separate Observation-quality scopes:

```text
A. AP-local observation_quality
B. Site/source Observation status
```

They MUST NOT be collapsed.

## 36.1 AP-local `observation_quality`

Allowed values:

```text
operational
degraded
unavailable
unknown
```

### `operational`

A persisted AP-local row is complete evidence for that AP when:

```text
row.partial = 0
overview_ok = 1
wired_uplink_ok = 1
lan_traffic_ok = 1
radios_ok = 1
```

A complete AP-local row remains `operational` / local-complete even when its parent Site `ap_dynamic` cycle is `partial`.

### `degraded`

The AP-local row itself is incomplete or degraded:

```text
row.partial = 1
OR
one or more AP-local required section flags != 1
OR
row-local rate-quality processing is degraded
```

AP-local degradation reason codes MUST describe the AP row itself.

A parent Site cycle being `partial` is NOT, by itself, an AP-local degradation reason.

### `unavailable`

The Observation source/read boundary is unreadable/unavailable such that AP-local evidence cannot be queried safely.

### `unknown`

No usable AP-local Observation evidence exists for the AP/window while the source itself remains readable.

Typical causes include:

```text
AP not reached because of request-budget rotation
no AP-local row in the interval
history not yet accumulated
```

`unknown` is not AP fault evidence.

## 36.2 Site/source Observation status

Site/source quality is evaluated separately from AP-local rows.

A parent `ap_dynamic` cycle:

```text
result='partial'
or complete=0
```

contributes Site/source Observation degradation and may carry reasons such as:

```text
site_cycle_partial
observation_cycle_capacity_exceeded
request_budget_exhausted
deadline_exhausted
inventory_incomplete
```

A failed/shutdown cycle or source read failure contributes the corresponding Site/source degradation/unavailability state.

Therefore this combination is valid and expected:

```text
Site/source Observation status = degraded
AP A observation_quality        = operational
AP B observation_quality        = unknown
```

Site/source degradation never automatically downgrades a complete AP-local row and never turns a missing/rotated AP row into an AP fault.

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

and let section 50 construct deterministic intervals from authoritative Current State samples using the accepted shared mapper.

Per-AP `history.status`:

```text
operational
```

when:

- coverage is complete;
- every eligible second is canonically operational;
- `unavailable_seconds = 0`;
- `unknown_evidence_seconds = 0`.

```text
unavailable
```

when the latest valid authoritative interval is canonically unavailable:

```text
raw 0 → shared mapper offline → product unavailable
```

and current evidence remains within `CS_GAP`.

```text
degraded
```

when the eligible window contains:

```text
operational_seconds > 0
AND
unavailable_seconds > 0
AND
unknown_evidence_seconds = 0
```

```text
unknown
```

when:

- mapper returns `other/unknown` for a required interval;
- raw `3` participates;
- complete-inventory AP absence produces `not_in_complete_inventory`;
- source gaps exist;
- coverage is insufficient in a way that prevents a safe overall conclusion.

`unavailable_seconds` is always controller-observed unavailable duration.

It is never reconstructed from physical test timestamps, `lastSeen`, uptime, or transition code `3`.

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

For each persisted AP Observation row:

```text
partial == false
AND overview_ok
AND wired_uplink_ok
AND lan_traffic_ok
AND radios_ok
```

is complete AP-local dynamic evidence.

This remains true even when the parent `ap_dynamic` Site cycle is `partial`.

If the AP row itself is partial or one or more required AP-local section flags are false:

```text
observation_quality = degraded
```

with AP-local reason codes describing only that row's evidence.

Allowed AP-local examples:

```text
overview_unobserved
wired_uplink_unobserved
lan_traffic_unobserved
radios_unobserved
rate_quality_degraded
```

`site_cycle_partial` is explicitly NOT an AP-local degradation reason.

It belongs only to Site/source Observation status/source metadata.

A parent partial cycle without an AP-local row failure:

```text
does not downgrade the AP-local row
does not add an AP-local degraded reason
does not imply AP hardware fault
```

All AP-local reason codes are evidence-quality diagnostics, not hardware fault diagnoses.

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

## 50.1 Authoritative inputs

Query Current State AP cycles covering:

```text
[window.from_utc - CS_GAP, window.to_utc)
```

Device-state authority requires:

```text
kind='ap'
result='success'
complete=1
```

Partial/failed/shutdown cycles affect source-quality metadata only.

For every AP already in the historical identity cohort, each authoritative complete cycle at `t_i` yields exactly one logical state sample:

```text
AP row present
→ classify raw status_code through the accepted shared mapper

1 → online
0 → offline
3 → other
other int → other
missing/unusable → unknown

AP row absent
→ unknown / not_in_complete_inventory
```

Before `first_evidence_at`:

```text
state = unknown / before_first_evidence
coverage_class = short_history
```

but that period is excluded from AP problem/outage duration.

## 50.2 Product state conversion

Canonical mapper output converts to AP-24H product state:

```text
online  → operational
offline → unavailable
other   → unknown
unknown → unknown
```

There is no direct mapper output `degraded`.

## 50.3 Step-function validity

For logical sample `(t_i, state_i)`, let `t_next` be the next authoritative complete inventory time.

The sample is valid on:

```text
[t_i, min(t_next, t_i + CS_GAP, window.to_utc))
```

If:

```text
t_next > t_i + CS_GAP
```

then:

```text
[t_i + CS_GAP, t_next)
→ unknown / current_state_source_gap
```

The final sample cannot be carried beyond:

```text
t_i + CS_GAP
```

A pre-window carry-in sample may cover from `window.from_utc` only if:

```text
window.from_utc - t_i <= CS_GAP
```

## 50.4 Controller-observed outage start/end

A canonical unavailable interval starts at:

```text
timestamp of the authoritative complete-success sample
whose raw status maps to offline
```

For the accepted mapper:

```text
first authoritative raw 0 sample
```

It does NOT start at:

```text
physical power OFF
first raw 3
first missed heartbeat
lastSeen freeze
```

The unavailable interval ends when the next authoritative sample maps away from offline, subject to the normal step-function/`CS_GAP` rules.

For recovery:

```text
authoritative raw 1 sample
→ operational begins at that sample timestamp
```

not at the physical power-ON timestamp.

## 50.5 15-minute bucket reduction

Intersect deterministic intervals with each 15-minute bucket.

Accumulate:

```text
operational_seconds
unavailable_seconds
unknown_evidence_seconds
short_history_seconds
```

Bucket AP state:

1. `unknown` if any eligible seconds are unknown;
2. else `degraded` if both operational and unavailable seconds are > 0;
3. else `unavailable` if unavailable seconds > 0 and operational seconds = 0;
4. else `operational` if operational seconds cover all eligible seconds;
5. else `unknown`.

A bucket containing only pre-first-evidence time is:

```text
ap_state = unknown
ap_state_reason = before_first_evidence
short_history_seconds = 900
```

and is excluded from problem/outage duration totals.

## 50.6 Duration semantics

`unavailable_seconds` equals the sum of seconds covered by canonical:

```text
offline → product unavailable
```

intervals after intersection with the history-eligible window.

It is a controller-observed duration.

It is NOT physical downtime SLA.

# 51. Deterministic Observation-quality bucket algorithm

Observation quality uses a separate axis from AP device state and a separate axis from Site/source-cycle quality.

## 51.1 Complete AP-local Observation row

A persisted row is complete AP-local Observation evidence when:

```text
parent cycle:
  kind='ap_dynamic'
  state='completed'

row:
  partial=0
  overview_ok=1
  wired_uplink_ok=1
  lan_traffic_ok=1
  radios_ok=1
```

The parent cycle does NOT need:

```text
result='success'
complete=1
```

for this AP-local predicate.

A complete AP-local row inside a parent `partial` cycle remains complete evidence for that AP at that timestamp.

## 51.2 AP-local diagnostic/degraded evidence

A persisted row is AP-local degraded evidence when:

```text
row.partial=1
OR
any required section flag != 1
```

Its reason codes come from the row/section evidence.

A parent-cycle `partial` without an AP-local partial row is NOT by itself an AP-local degraded sample.

## 51.3 Site/source quality

Parent cycle results are aggregated separately:

```text
success/complete
partial
failed
shutdown
```

A parent `partial`:

- keeps the Site/source quality degraded;
- may explain missing AP rows;
- does not downgrade a fully complete AP-local row;
- does not create AP fault evidence for APs not reached by rotation.

## 51.4 Bucket reduction

For each 15-minute bucket after AP first evidence:

1. if the Observation source itself cannot be read → AP-local `observation_quality=unavailable`;
2. else if any AP-local degraded row exists in the bucket → `degraded`;
3. else if AP-local complete rows provide continuity for the bucket without an AP-local gap > `OBS_GAP` → `operational`;
4. else → `unknown`.

The Site/source status for the same bucket/window is computed separately from parent cycles and may be `degraded` even when one or more AP-local buckets are operational.

Therefore this combination is valid:

```text
Site/source Observation quality = degraded
AP A local Observation quality  = operational
AP B local Observation quality  = unknown
```

If the Site roster exceeds `OBS_FULL_AP_CAPACITY_UPPER_BOUND`, source-level reason includes:

```text
observation_cycle_capacity_exceeded
```

and missing/rotated AP rows are never interpreted as AP faults.

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

FINAL proposal:

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

Conceptual FINAL response:

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

`unavailable_seconds` is now fully defined as controller-observed unavailable duration from authoritative complete-success Current State intervals classified by the accepted shared mapper.

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

Production rollout of this flag remains Owner-controlled after FINAL + accepted mapper artifact + Central Lab acceptance.

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

| Displayed meaning | Source | FINAL status |
|---|---|---|
| AP identity / current inventory | Current State complete successful AP cycles | YES |
| Raw AP controller status | Current State `status_code` | YES |
| Canonical status mapping | accepted Phase R Outcome A + accepted Phase M shared mapper artifact | RESEARCH RESOLVED; mapper artifact pending |
| Raw `1` | shared mapper | `online` |
| Raw `0` | shared mapper | `offline` |
| Raw `3` | shared mapper | `other` |
| Other integer | shared mapper | `other` |
| Missing/unusable status | shared mapper | `unknown` |
| Current product operational | complete-success AP row + mapper `online` | YES after mapper artifact |
| Current product unavailable | complete-success AP row + mapper `offline` | YES after mapper artifact |
| 24h state intervals | authoritative Current State complete cycles + shared mapper + `CS_GAP` | YES after mapper artifact |
| `unavailable_seconds` | deterministic canonical offline intervals | YES after mapper artifact |
| Physical power-loss/recovery timestamp | NOT a HOME source | NOT USED |
| `lastSeen` as outage start | NOT a HOME source | NOT USED |
| AP absence in complete inventory | Current State membership | YES → `unknown/not_in_complete_inventory` |
| Current State source gaps | Current State cycle history | YES |
| AP-local Observation complete/partial | Observation AP row flags | YES |
| Observation Site/source cycle quality | Observation cycles | YES |
| Observation endpoint completeness | AP row `*_ok` fields | YES |
| Observation capacity pressure | config + cycle/source quality | YES |
| AP CPU / memory history | Observation | YES |
| Radio utilization history | Observation radio rows | YES |
| Radio error/retry/drop counters | Observation radio rows | YES |
| Wired/LAN counters/rates | Observation AP rows | YES |
| Physical wired/radio hardware fault state | current stored facts | NO canonical threshold/fault contract |
| Home current AP list | existing Home Live | YES, separate accepted contract |

Compatibility evidence is specific to:

```text
Controller 5.14.32.3
EAP613(EU) v1.0
FW 1.8.3 Build 20260617 Rel. 36045
```

No ad-hoc version/model branch is introduced into HOME-AP-24H.

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

The semantic research gate is closed:

```text
Phase R — ACCEPTED
Outcome A — VERIFIED
```

No additional status research is required for the current production compatibility tuple.

The only remaining AP-status gate is acceptance of the exact Phase M shared mapper artifact.

HOME-AP-24H implementation MUST NOT start until Owner + Tech Lead accept:

```text
mapper module/API
candidate SHA
1→online
0→offline
3→other
other int→other
missing/unusable→unknown
schema unchanged
no backfill
```

After mapper acceptance:

```text
HOME-AP-24H ordinary coder implementation flow is unblocked
```

No Pattern B/C foundation task remains active.

No schema/storage dependency remains.

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

31. AP row with all four sections complete inside a parent success/complete cycle → complete AP-local evidence.
32. AP row with all four sections complete inside a parent partial cycle → still complete AP-local evidence.
33. parent partial cycle keeps Site/source quality degraded even when AP A local row is complete.
34. one wired section false → degraded AP-local Observation evidence only.
35. one radio section false → degraded AP-local Observation evidence only.
36. mixed AP-local complete+partial rows in bucket → AP-local Observation quality degraded.
37. cycle partial due request budget → Site/source degraded/partial.
38. Site AP count greater than `floor(B/4)` → `observation_cycle_capacity_exceeded` source reason.
39. rotation cursor causes AP A complete local row this run while AP B is not reached → AP A may be operational locally; AP B has no sample/unknown, not fault.
40. a missing AP row in a partial cycle is not synthesized as AP-local degraded evidence.
41. AP-local partial row remains diagnostic/degraded regardless of parent-cycle result.
42. Observation source unavailable → Observation quality unavailable, AP device state unchanged.
43. section failure counts aggregate correctly.

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

# 99. Production acceptance — controller-observed unavailable semantics

HOME-AP-24H production acceptance does NOT rediscover AP status codes.

Phase R already established the accepted mapping.

Production acceptance verifies that the accepted Phase M mapper artifact is correctly reflected in:

```text
current AP product state
24h timeline
unavailable_seconds
current-vs-history context
```

Required semantic checks:

```text
raw 1 authoritative sample
→ operational

raw 0 authoritative sample
→ unavailable

raw 3 authoritative sample
→ unknown product state

AP absent in complete inventory
→ unknown/not_in_complete_inventory

partial/failed Current State cycle
→ source quality only
→ never offline
```

`unavailable_seconds` must begin/end from authoritative Current State sample timestamps under section 50.

It must NOT use:

```text
physical power marker
lastSeen
uptime
raw 3
```

No new physical outage is required merely for HOME production acceptance.

The accepted research report and exact mapper artifact are the semantic authorities.

# 100. Rollout boundary

This FINAL does not authorize rollout.

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

# 105. FINAL decisions

The following are fixed:

1. Phase R Outcome A is accepted.
2. tested mapping is:
   ```text
   1 → online
   0 → offline
   3 → other
   other int → other
   missing/unusable → unknown
   ```
3. HOME-AP-24H uses exactly the accepted shared mapper artifact.
4. no private HOME status mapping.
5. raw historical `status_code` overrides source-era `status_classification` for HOME semantic interpretation.
6. no backfill.
7. Current State device-state history uses complete-success AP cycles only.
8. AP absence in complete inventory remains unknown, not offline.
9. pre-first-evidence time is short history, not outage/problem duration.
10. `unavailable_seconds` is controller-observed offline interval duration.
11. physical power markers, `lastSeen`, uptime and raw `3` do not define unavailable interval boundaries.
12. Observation `30 s` is not a per-AP cadence guarantee.
13. request budget + four dynamic sections + rotation cursor remain capacity semantics.
14. Site above dynamic capacity yields source degradation, not AP fault.
15. AP-local Observation quality remains independent of Site/source cycle completeness.
16. 15-minute / 96-bucket contract remains.
17. `coverage_ratio` remains absent from v1.
18. existing Admin cursor codec is reused/extended.
19. independent safe-disabled AP-24H feature flag remains required.
20. refresh=120 s remains the product contract.
21. independent request timeout remains required.
22. no new DB/schema/retention/cadence.
23. no Pattern B/C delivery dependency.
24. implementation remains blocked only until the exact Phase M mapper artifact is accepted.

# 106. Final architectural conclusion — accepted Outcome A incorporated

Repository/storage conclusion:

> **A. Product-complete HOME-AP-24H is implementable on the existing persisted data once the accepted Phase M shared mapper artifact is available.**

Phase R closed the only missing device-status semantic.

Accepted production mapping:

```text
1 → online
0 → offline
3 → other
other int → other
missing/unusable → unknown
```

The AP remains present in complete successful inventory while physically powered off.

Therefore:

```text
NO new AP-history DB
NO Current State schema migration
NO negative-membership storage foundation
NO retention increase
NO cadence increase
```

is required.

HOME availability semantics are explicitly:

```text
controller-observed availability
```

not physical electrical-time availability.

Existing raw historical `status_code` is sufficient for retrospective semantic interpretation through the shared mapper.

Observation capacity remains a separate evidence-quality concern and never creates AP offline state.

Implementation authorization remains:

```text
BLOCKED ONLY UNTIL
Owner + Tech Lead accept the exact Phase M shared mapper artifact/handoff
```

After that gate, normal HOME-AP-24H coder implementation may proceed without another AP-status research/architecture round.

# 107. Required next step

Research is no longer a blocker.

Required critical path:

```text
1. Owner / Tech Lead authorize Phase M mapper implementation
2. Coder implements TASK-CURRENT-STATE-AP-STATUS-SEMANTICS-01-PHASE-M-FINAL
3. Coder returns exact mapper candidate + focused test evidence
4. Owner + Tech Lead run official Central Lab exact-artifact gate
5. Owner + Tech Lead accept mapper artifact/handoff
6. HOME-AP-24H implementation becomes unblocked
7. Coder implements HOME-AP-24H against this FINAL
8. Coder runs focused/module tests
9. Owner + Tech Lead run HOME exact-artifact Central Lab gate
10. Owner controls production rollout
```

This FINAL does NOT itself authorize:

```text
Phase M implementation start
HOME-AP-24H implementation start
branch creation
commit
push
PR
merge
deploy
production flag activation
physical AP disruption
```

No additional AP-status research round is required if Phase M implements the accepted mapping exactly.

