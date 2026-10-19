# TASK-DEVICE-CARD-01 — Current Device Context — FINAL

**Project:** CaptivPortal  
**Roadmap:** `CaptivPortal — Device Card Upgrade Roadmap v1`  
**Roadmap item:** `DEVICE-CARD-01 — Current Device Context`  
**Covers:** `Current Status` + `Current Guest Traffic`  
**Type:** read-only architecture / bounded exact entity reads / Site-safe Admin projection / Device Card extension  

**Status:** `FINAL — ARCHITECT + TECH LEAD REVIEW INCORPORATED`  
**Owner status:** `READY FOR OWNER FINAL REVIEW`  
**Implementation authorization:** `NOT GRANTED`  
**Coder authorization:** `NOT GRANTED`  
**Branch / commit / push / PR / merge:** `NOT AUTHORIZED`  
**Production deployment / activation:** `NOT AUTHORIZED`  

**Prepared:** 2026-09-08

---

# 0. Final architectural statement

`DEVICE-CARD-01` extends the **existing** Device Card with one new read-only product block:

```text
CURRENT DEVICE CONTEXT
```

It answers only:

> What can CaptivPortal truthfully assert about this exact Device now, inside the requested Site and the accepted managed Current State client scope?

Canonical architecture:

```text
existing Site-safe Admin Device boundary
        ↓
site_id + device_id
        ↓
prove Device membership in requested Site
        ↓
resolve canonical MAC server-side
        ↓
CurrentStateReadService
exact bounded entity read
        ↓
Current Device Context
        │
        └── only when current client is authorized
                ↓
        CurrentGuestTrafficReadService
        exact bounded per-client projection
        ↓
same evaluated_at_utc
same pinned current_cycle_id
        ↓
strict safe Admin serializer
        ↓
GET /admin/api/v1/sites/<site_id>/devices/<device_id>/current
        ↓
Device Card
```

Permanent:

```text
NO new semantic owner
NO new Device identity
NO new Visitor Profile
NO new Traffic formula
NO query-time Omada
NO new collector
NO new DB
NO schema migration
NO write/control actions
```

---

# 1. Architecture review baseline and implementation baseline

## 1.1 Architecture review baseline

Final architecture reconciliation is bound to:

```text
Architecture review baseline =
main@3eac6f13d5f3966574f6d1b0a10f531d988f91ec

tree =
e4b5c32946e50a84b21652cee43feabb6b519450
```

This `main` includes:

```text
PR #107
Docs: reconcile TRAFFIC-09 production closure
```

## 1.2 Runtime checkpoint reference

Canonical KB separately records:

```text
runtime implementation / production checkpoint =
e32ade378bdbfc9f8458db9c18221958f4552718

runtime tree =
2766139c83965dcf2f80e0c8084b3fb363dbd781
```

Permanent:

```text
repository review baseline
!=
runtime implementation checkpoint
```

## 1.3 Implementation baseline

The implementation baseline is NOT frozen by this FINAL.

At separate Owner implementation authorization:

```text
Implementation baseline =
exact current origin/main SHA/tree at that moment
```

Required before any code:

```text
git fetch origin
re-pin origin/main SHA
re-pin origin/main tree
impact review
```

Mandatory STOP / re-review if drift touches:

```text
app/current_state/**
app/analytics/current_guest_traffic.py
app/analytics/models.py

app/admin_web/query_service.py
app/admin_web/routes.py
app/admin_web/current_state_serialization.py
app/admin_web/current_guest_traffic_serialization.py
app/admin_web/device_gateway.py
app/admin_web/runtime.py
app/admin_web/static/admin.js
app/admin_web/templates/admin/device.html

Admin security / Site policy

app/config.py
app/settings.py
```

Material drift means this FINAL must be rebound before Coder starts.

---

# 2. Exact TASK scope

`DEVICE-CARD-01` answers only:

```text
What is happening with this Device now?
```

In scope:

```text
Current Presence
Current Authorization
Current Network Context
Current Radio Context
Current Controller Context
Current Guest Traffic
Current freshness/evidence/source state
```

Out of scope:

```text
Visit Detail
Visit Traffic
Device historical timeline
Snapshot History
Observation History
Device Summary / Intelligence

Reconnect
Block
Unblock
Hotspot Auth
Hotspot Unauth
Rate Limit
Lock-to-AP
Rename
authentication-period change

any write/control action
```

Roadmap remains:

```text
DEVICE-CARD-01 — Current Device Context
        ↓
DEVICE-CARD-02 — Visit Detail & Visit Traffic
        ↓
DEVICE-CARD-03 — Device History
        ↓
DEVICE-CARD-04 — Device Summary / Intelligence
```

No work from `02/03/04` may be pulled into `01`.

---

# 3. Existing Device Detail contract is preserved

Accepted existing endpoint:

```text
GET /admin/api/v1/sites/<site_id>/devices/<device_id>
```

Current result remains:

```text
identity
latest_snapshot
recent_visits
latest_client_observation
```

This contract stays backward-compatible.

`DEVICE-CARD-01` MUST NOT make this endpoint depend on Current State.

Permanent:

```text
latest_client_observation
=
historical persisted Observation

NOT
=
Current Device State
```

Likewise:

```text
latest_snapshot
=
historical safe authorization snapshot

NOT
=
Current Device State
```

---

# 4. New Device Current subresource

Frozen API:

```text
GET /admin/api/v1/sites/<site_id>/devices/<device_id>/current
```

Method:

```text
GET only
```

Query parameters v1:

```text
NONE
```

Unknown or duplicate query parameters:

```text
400 invalid_request
```

Forbidden:

```text
?mac=
?client_mac=
browser-selected identity override
```

This endpoint is:

```text
read-only
Site-scoped
Device-specific
bounded
composition-only
```

It is not a new semantic owner.

---

# 5. Security / Site ordering

Frozen ordering:

```text
authenticated Admin session
        ↓
canonical Site resolution
        ↓
Site allowlist / policy
        ↓
feature gate
        ↓
admin.read.device
        ↓
validate device_id
        ↓
existing Site Device membership proof
        ↓
resolve canonical MAC server-side
        ↓
Current State / Current Guest Traffic reads
```

Canonical capability:

```text
admin.read.device
```

Do NOT substitute:

```text
admin.read.devices
```

because this is an exact entity read.

Device not belonging to requested Site:

```text
404 / existing leak-safe not-found behavior
```

Mandatory:

```text
no Current State query
no Traffic query
```

before Device Site membership is proven.

---

# 6. Site Device membership stays unchanged

Existing accepted contract:

```text
Site membership =
Site Snapshot evidence
OR
Site Visit evidence
```

Forbidden as membership authority:

```text
Registry global last_site_id
Registry global last_*
```

The same global Device identity may have evidence in multiple Sites.

All current reads receive:

```text
requested exact site_id
+
server-resolved canonical MAC
```

No cross-Site fallback.

---

# 7. Current State is the sole owner of current context

Primary semantic owner:

```text
CurrentStateReadService
```

Current State owns current:

```text
presence
authorization
network context
radio context
controller context
current cumulative counters
```

Forbidden fallback sources:

```text
Latest Snapshot
Latest Client Observation
Visit
Registry global last_*
Omada live query
browser inference
```

Permanent:

```text
Current State
!=
Latest Historical Observation
```

If Current State is stale/unavailable/missing:

```text
do not replace it with historical evidence
```

Existing historical Device Card blocks remain visible separately.

---

# 8. Exact Current State entity read

Current page-oriented API:

```text
CurrentStateReadService.list_current_clients(...)
```

MUST NOT be used to find one Device.

Forbidden:

```text
page 1 → page 2 → ... → search MAC
limit=500 → Python scan
load all → filter
browser join
```

Frozen narrow read contract:

```python
CurrentStateReadService.get_current_client(
    site_id,
    client_mac,
    *,
    evaluated_at_utc=None,
    cycle_id=None,
)
```

Return type is frozen conceptually as:

```text
CurrentClientLookup
```

with:

```text
snapshot: CurrentSnapshotMeta
client: CurrentClientState | None
```

The method MUST reuse:

```text
existing Site validation
existing complete-success cycle selection
existing exact client source scope
existing scope hash semantics
existing freshness semantics
existing CurrentSnapshotMeta meaning
```

No new Current State meaning.

---

# 9. Frozen CurrentClientLookup stale behavior

`CurrentClientLookup.client` is allowed to be non-null **only if all of the following are true**:

```text
snapshot exists
AND snapshot.complete=true
AND snapshot.freshness_status=fresh
AND compatible trusted current client scope
AND canonical MAC exists in that exact cycle
```

Therefore:

```text
fresh complete + MAC present
→ client object
→ presence=online

fresh complete + MAC absent
→ client=null
→ presence=offline

stale
→ client=null
→ presence=unknown

unavailable freshness
→ client=null
→ presence=unknown

no complete snapshot
→ client=null
→ presence=unknown
```

Permanent:

```text
stale persisted client row
MUST NOT leave CurrentStateReadService.get_current_client(...)
as Current Device Context
```

Historical fallback remains forbidden.

---

# 10. Exact Current State query shape

For one Device:

```text
select accepted current client cycle
+
exact MAC row in that exact cycle
```

Exact target row shape:

```text
WHERE cycle_id=? AND client_mac=?
```

Current schema already provides:

```text
PRIMARY KEY(cycle_id, client_mac)
```

Frozen default:

```text
NEW INDEX = NO
SCHEMA CHANGE = NO
```

Before code, Coder PLAN MUST show:

```text
exact SQL/read path
index/key used
EXPLAIN QUERY PLAN
source call count
deadline behavior
```

If current schema/index cannot provide bounded exact lookup:

```text
STOP
→ return EXPLAIN + measured evidence
→ separate architecture/index decision
```

No opportunistic index.

---

# 11. Canonical Current State scope contract

Device Current MUST reuse the existing Current State machine contract.

Canonical scope:

```json
{
  "scope_type": "client_ssid_allowlist",
  "site_id": "<site_id>",
  "ssids": ["<exact ssid>"]
}
```

Machine value is frozen:

```text
scope_type = client_ssid_allowlist
```

Presentation/UI wording MAY say:

```text
Managed Site/SSID scope
```

but this is presentation only.

`source_scope_hash` remains:

```text
internal integrity/coherence detail
```

and is not required in the normal Device Current DTO/UI.

---

# 12. Frozen Presence machine contract

Exact API machine values:

```text
online
offline
unknown
```

## online

Exactly:

```text
accepted complete Current State client snapshot
+
fresh
+
trustworthy compatible client_ssid_allowlist scope
+
canonical MAC present in that exact snapshot
+
persisted row satisfies active/wireless invariants
```

## offline

Exactly:

```text
accepted complete Current State client snapshot
+
fresh
+
trustworthy compatible client_ssid_allowlist scope
+
canonical MAC absent from that exact snapshot
```

Meaning:

```text
not present in the current managed client scope
at this accepted Current State snapshot
```

It does NOT universally mean:

```text
physical device powered off
absent from every SSID/network
absent from another unmanaged network
```

## unknown

Required for:

```text
no complete snapshot
stale source
unavailable source
clock anomaly
invalid timestamp
untrustworthy/incompatible scope
integrity cannot be safely proven
```

Permanent:

```text
stale != offline
unavailable != offline
missing source != offline
```

---

# 13. Presence reason contract

Exact safe `presence_reason` values:

```text
present_in_fresh_complete_scope
absent_from_fresh_complete_scope
current_state_unknown
```

Detailed source reason remains in:

```text
snapshot.freshness_reason
```

No second freshness-reason vocabulary.

---

# 14. Semantic freshness vs execution failure

This distinction is permanent.

## Successful Current State read with stale/unavailable evidence

If the authoritative read executes successfully and returns semantic evidence such as:

```text
freshness_status=stale
```

or:

```text
freshness_status=unavailable
```

then:

```text
HTTP 200
current_state.presence_status=unknown
current_state.client=null
```

This is a valid semantic product state.

It is NOT an endpoint/source execution failure.

Examples:

```text
old complete snapshot
older_than_freshness_window
older_than_unavailable_threshold
no complete snapshot represented safely by CurrentSnapshotMeta
clock anomaly represented safely
```

## Authoritative read execution failure

Only real execution/source/integrity failures that prevent construction of a safe Current State result produce:

```text
controlled HTTP 503
```

Examples conceptually include:

```text
CurrentStateStorageError
CurrentStateSchemaError
query/deadline/source execution failure
integrity failure where safe Current State result cannot be constructed
```

Permanent:

```text
old/stale/unavailable evidence
!=
source read execution failure
```

---

# 15. Historical evidence regression invariants

Mandatory:

```text
latest_client_observation exists
+
Current State stale/unavailable
→ current presence MUST NOT become online
```

Also:

```text
old Snapshot active=true
+
fresh complete Current State proves MAC absent
→ current presence = offline
```

Current State wins current semantics.

Historical evidence remains historical.

---

# 16. Current Authorization contract

Use only:

```text
CurrentClientState.auth_classification
```

Accepted machine values remain:

```text
authorized
pending
other
unknown
```

No remapping.

Safe Device Current projection:

```text
authorization_classification:
authorized | pending | other | unknown

authorization_reason:
current_row | offline | current_state_unknown
```

Rules:

### online

```text
authorization_classification =
exact CurrentClientState.auth_classification

authorization_reason =
current_row
```

### offline

```text
authorization_classification =
unknown

authorization_reason =
offline
```

### presence unknown

```text
authorization_classification =
unknown

authorization_reason =
current_state_unknown
```

Forbidden:

```text
historical authStatus fallback
offline → other
offline → unauthorized
```

---

# 17. Current context fields

For `presence=online`, safe current client fields:

```text
client_mac
name
hostname
device_type

ip
ssid

ap_name
ap_mac

radio_id
band
channel

rssi
snr

controller_uptime

auth_classification

controller_traffic_down
controller_traffic_up
controller_traffic_total

active
wireless
```

Snapshot metadata:

```text
cycle_id
observed_at
capture_finished_at
age_seconds
freshness_status
freshness_reason
complete
```

No extra AP lookup is allowed merely to obtain:

```text
ap_name
```

when CurrentClientState already contains it.

If presence is `offline` or `unknown`:

```text
client = null
```

Stale rows are not exposed as "Current".

---

# 18. NULL rules for current facts

Permanent:

```text
NULL stays NULL
missing stays missing
unknown stays unknown
```

Never:

```text
missing RSSI → 0
missing SNR → 0
missing counter → 0
missing IP/AP → fabricated API value
```

UI may display:

```text
—
```

for null.

API preserves null.

---

# 19. Controller counters are cumulative bytes, not rate

Current State fields:

```text
controller_traffic_down
controller_traffic_up
controller_traffic_total
```

mean:

```text
current Omada/controller connection cumulative bytes
```

Safe Device DTO names make units explicit:

```text
controller_traffic_down_bytes
controller_traffic_up_bytes
controller_traffic_total_bytes
```

They MUST NOT be labeled:

```text
Download Now
Upload Now
Current Speed
Mbps
```

Also forbidden as actual traffic throughput:

```text
rxRate
txRate
```

PHY/link rate is not user traffic throughput.

---

# 20. Current Guest Traffic has one semantic owner

Canonical owner:

```text
CurrentGuestTrafficReadService
```

Device Card MUST NOT:

```text
read two Current State rows and calculate delta/time itself
copy Traffic formula
calculate in AdminQueryService
calculate in serializer
calculate in JavaScript
calculate in template
use rxRate/txRate as throughput
```

Existing Traffic-07 semantic meaning remains authoritative.

---

# 21. Frozen exact single-client Current Guest Traffic method

Existing paged method remains unchanged:

```python
CurrentGuestTrafficReadService.get_current_guest_traffic(
    site_id,
    *,
    evaluated_at_utc=None,
    limit=...,
    cursor=None,
    sort=...
)
```

New exact entity projection:

```python
CurrentGuestTrafficReadService.get_current_guest_traffic_for_client(
    site_id,
    client_mac,
    *,
    evaluated_at_utc,
    current_cycle_id,
)
```

`source_scope_hash` may be checked internally but is not required as public method input if the pinned Current State cycle already proves the same configured scope.

Frozen return type:

```text
CurrentGuestTrafficClientResult
```

It MUST reuse the same existing:

```text
population semantics
baseline selection
counter delta rules
elapsed rules
max gap
uptime progress
connection continuity
SSID continuity
counter reset
counter missing
source frozen
no baseline semantics
source health semantics
reason codes
NULL/zero semantics
```

No second rate algorithm.

---

# 22. Exact target Traffic evidence read

For one Device, the Traffic entity path MUST read only:

```text
pinned accepted current cycle
+
exact current row for canonical MAC
+
nearest previous accepted baseline cycle
+
exact baseline row for same canonical MAC
+
newer degraded-attempt evidence where existing source-health semantics require it
```

Required exact row query shape:

```text
WHERE cycle_id=? AND client_mac=?
```

Forbidden:

```text
materialize all current rows
materialize all baseline rows
Top 50/200 scan
Online Guests pagination
```

Implementation should reuse the existing rate projection helper/formula rather than copy it.

---

# 23. Existing Traffic-07 item semantics are preserved

Reuse exact existing item fields:

```text
download_mbps
upload_mbps
total_mbps

rate_status

source_progress_status
connection_continuity_status
continuity_basis

download_reason
upload_reason
total_reason
```

Reuse existing source/root fields where applicable:

```text
source_health_status
source_health_reason
rate_evidence_status
current_cycle_id
baseline_cycle_id
elapsed_seconds
```

Existing item reason vocabulary remains:

```text
valid
no_baseline
no_authorized_baseline
ssid_transition
invalid_elapsed
baseline_gap_too_large
connection_continuity_unproven
source_frozen
connection_reset
counter_missing
counter_reset
```

Existing successful semantic root/evidence values remain unchanged, including:

```text
rate_evidence_status:
complete
partial
insufficient_data
not_applicable
```

No parallel GOOD/BAD vocabulary.

---

# 24. Current Guest Traffic applicability

Frozen composition-level applicability enum:

```text
applicable
not_applicable
unknown
```

Frozen applicability reasons:

```text
authorized_current_guest
not_authorized_current_guest
offline
current_state_unknown
```

## online + authorized

```text
applicability = applicable
applicability_reason = authorized_current_guest
```

Then exact Traffic semantic service is called.

## online + pending / other / unknown auth

```text
applicability = not_applicable
applicability_reason = not_authorized_current_guest
item = null
```

## offline

```text
applicability = not_applicable
applicability_reason = offline
item = null
```

## current presence unknown

```text
applicability = unknown
applicability_reason = current_state_unknown
item = null
```

No synthetic 0 Mbps.

---

# 25. Numeric zero vs null

Permanent:

```text
numeric 0.0 Mbps
=
accepted valid zero-rate evidence
```

while:

```text
null
=
unknown / unavailable / not applicable / missing evidence
```

Do NOT synthesize zero for:

```text
pending
other
offline
unknown presence
stale source
unavailable source
no baseline
counter reset
source frozen
counter missing
```

Mandatory regression:

```text
NULL != 0
```

---

# 26. One evaluation anchor

Each Device Current request captures one server-owned:

```text
evaluated_at_utc
```

Browser cannot supply it.

This one anchor is used for:

```text
Current State freshness
Current State exact read
Current Guest Traffic source health
Traffic interval/evidence evaluation
Admin response
```

---

# 27. Current State / Traffic cycle coherence

Frozen architecture:

```text
explicit cycle pinning
```

Flow:

```text
1. AdminQueryService captures evaluated_at_utc.

2. Resolve Site Device and canonical MAC.

3. CurrentStateReadService.get_current_client(
       site_id,
       canonical_mac,
       evaluated_at_utc=evaluated_at_utc,
   )

4. Receive current snapshot cycle_id.

5. If current client is online + authorized:

   CurrentGuestTrafficReadService.get_current_guest_traffic_for_client(
       site_id,
       canonical_mac,
       evaluated_at_utc=evaluated_at_utc,
       current_cycle_id=current_state_cycle_id,
   )

6. Traffic service MUST NOT independently select a newer current cycle.

7. Previous baseline cycle is allowed only for rate calculation.
```

Mandatory successful coherence:

```text
Current Context current_cycle_id
=
Current Guest Traffic current_cycle_id
```

If pinned coherence cannot be guaranteed without changing accepted Traffic meaning:

```text
STOP
→ Architect + Tech Lead review
```

Never hide mismatch.

---

# 28. Race behavior

Required race rule:

```text
Current State entity read selects cycle A

collector publishes cycle B

Traffic entity read MUST remain pinned to A
```

Allowed response:

```text
cycle A Current Context
+
cycle A Traffic
```

or, if pinned Traffic evidence can no longer be safely read:

```text
cycle A Current Context
+
Traffic unavailable
```

Forbidden:

```text
cycle A Current Context
+
cycle B Traffic
```

---

# 29. One Admin request budget

New query service method:

```python
AdminQueryService.device_current_context(
    principal,
    site_id,
    device_id,
)
```

runs inside:

```text
one existing AdminQueryExecutionControls concurrency slot
+
one existing QueryDeadline
```

All composition is in-process.

Forbidden:

```text
AdminQueryService → HTTP localhost → another Admin endpoint
```

Do NOT increase:

```text
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS
Admin max concurrency
browser timeout
```

for this feature.

---

# 30. Exact Admin response contract

Outer envelope remains the existing Admin API envelope.

Inner result contract:

```text
contract_version = admin.device.current.v1
```

Exact inner shape:

```json
{
  "contract_version": "admin.device.current.v1",
  "site_id": "0123456789abcdef01234567",
  "device_id": "uuid",
  "evaluated_at_utc": "2026-09-08T16:00:00.000Z",

  "scope": {
    "scope_type": "client_ssid_allowlist",
    "site_id": "0123456789abcdef01234567",
    "ssids": ["Zefer_Parki"]
  },

  "current_state": {
    "presence_status": "online",
    "presence_reason": "present_in_fresh_complete_scope",

    "snapshot": {
      "cycle_id": "cycle-id-or-null",
      "observed_at": "timestamp-or-null",
      "capture_finished_at": "timestamp-or-null",
      "age_seconds": 12.0,
      "freshness_status": "fresh",
      "freshness_reason": "within_freshness_window",
      "complete": true
    },

    "authorization": {
      "classification": "authorized",
      "reason": "current_row"
    },

    "client": {
      "client_mac": "AA:BB:CC:DD:EE:FF",
      "name": "Guest phone",
      "hostname": "phone",
      "device_type": "phone",
      "ip": "192.168.10.50",
      "ssid": "Zefer_Parki",
      "ap_name": "EAP613-1",
      "ap_mac": "AA:BB:CC:DD:EE:01",
      "radio_id": 1,
      "band": "5GHz",
      "channel": 44,
      "rssi": -52,
      "snr": 31,
      "controller_uptime": 1800,
      "controller_traffic_down_bytes": 123456,
      "controller_traffic_up_bytes": 4567,
      "controller_traffic_total_bytes": 128023,
      "active": true,
      "wireless": true
    }
  },

  "current_guest_traffic": {
    "applicability": "applicable",
    "applicability_reason": "authorized_current_guest",

    "source_health_status": "healthy",
    "source_health_reason": "within_freshness_window",
    "rate_evidence_status": "complete",

    "current_cycle_id": "cycle-id-or-null",
    "baseline_cycle_id": "baseline-id-or-null",
    "elapsed_seconds": 30.0,

    "item": {
      "download_mbps": 1.25,
      "upload_mbps": 0.10,
      "total_mbps": 1.35,
      "rate_status": "valid",
      "source_progress_status": "advanced",
      "connection_continuity_status": "proven",
      "continuity_basis": "uptime_progress",
      "download_reason": "valid",
      "upload_reason": "valid",
      "total_reason": "valid"
    },

    "failure_reason": null
  }
}
```

---

# 31. DTO enum and null rules

## scope.scope_type

Exact machine value:

```text
client_ssid_allowlist
```

No alternative machine scope enum is introduced.

## presence_status

```text
online
offline
unknown
```

## presence_reason

```text
present_in_fresh_complete_scope
absent_from_fresh_complete_scope
current_state_unknown
```

## snapshot freshness_status

Reuse existing:

```text
fresh
stale
unavailable
```

## snapshot freshness_reason

Reuse existing Current State values, including:

```text
within_freshness_window
older_than_freshness_window
older_than_unavailable_threshold
no_complete_snapshot
clock_anomaly
invalid_timestamp
invalid_source_scope
```

## authorization.classification

```text
authorized
pending
other
unknown
```

## authorization.reason

```text
current_row
offline
current_state_unknown
```

## current_state.client

```text
online
→ object

offline|unknown
→ null
```

## current_guest_traffic.applicability

```text
applicable
not_applicable
unknown
```

## current_guest_traffic.rate_evidence_status

If an exact Traffic semantic read completed successfully, reuse existing:

```text
complete
partial
insufficient_data
not_applicable
```

If exact Traffic semantic service failed by exception and no semantic result exists:

```text
rate_evidence_status = null
```

## current_guest_traffic.item

```text
successful applicable semantic result
→ item object where contract permits

not_applicable|unknown
→ null

Traffic sub-read execution failure
→ null
```

---

# 32. Traffic sub-read execution failure

This is distinct from a normal semantic `insufficient_data` result.

If Current State is valid but exact Current Guest Traffic service fails by exception:

```text
source_unavailable
integrity_unavailable
query_deadline
```

preferred endpoint response remains:

```text
HTTP 200
```

Current State context is retained.

Exact projection:

```text
current_guest_traffic:
    applicability = applicable
    applicability_reason = authorized_current_guest

    source_health_status = null
    source_health_reason = null
    rate_evidence_status = null

    current_cycle_id = pinned Current State cycle_id
    baseline_cycle_id = null
    elapsed_seconds = null

    item = null

    failure_reason =
        source_unavailable
        | integrity_unavailable
        | query_deadline
```

Permanent:

```text
insufficient_data
=
normal semantic outcome from a successfully completed Traffic read
```

while:

```text
failure_reason != null
=
technical failure to obtain a semantic Traffic result
```

These meanings MUST NOT be mixed.

---

# 33. Traffic sub-read failure reason enum

Exact `failure_reason` enum:

```text
null
source_unavailable
integrity_unavailable
query_deadline
```

When:

```text
failure_reason != null
```

the following are mandatory:

```text
source_health_status = null
source_health_reason = null
rate_evidence_status = null
baseline_cycle_id = null
elapsed_seconds = null
item = null
```

`current_cycle_id` remains the pinned Current State cycle identity.

Normal semantic outcomes such as:

```text
no_baseline
counter_reset
source_frozen
```

must NOT populate `failure_reason`.

---

# 34. Authoritative Current State execution failure

If the authoritative Current State read cannot be safely executed because of source/storage/schema/query/integrity failure:

```text
GET /devices/<device_id>/current
→ controlled 503
```

Examples include:

```text
storage execution failure
schema/read incompatibility
query deadline
source execution failure
integrity failure where no safe Current State semantic result can be constructed
```

Existing historical Device endpoint remains independent.

Browser must show:

```text
Current Device Context = unavailable
```

while keeping:

```text
Identity
Latest Site Snapshot
Latest Client Observation
Recent Visits
```

visible if their existing endpoint succeeded.

---

# 35. Strict serializer

Preferred new file:

```text
app/admin_web/device_current_context_serialization.py
```

It owns only:

```text
strict validation
field allowlist
enum validation
nullability validation
unit meaning
cycle coherence validation
safe Admin DTO
```

It MUST fail closed on contradictory shapes.

Examples of contradictory shapes:

```text
presence=online + client=null

presence=offline + client object

freshness=stale + presence=online

Traffic failure_reason!=null + rate_evidence_status!=null

Traffic failure_reason!=null + item object

Traffic successful semantic result + unknown reason outside accepted Traffic vocabulary

Current State cycle != Traffic current cycle for successful Traffic evidence
```

It MUST NOT:

```text
query sources
calculate Traffic
repair source data
fallback to history
invent quality scores
```

Do not expose arbitrary source dictionaries.

---

# 36. Privacy / internal data

Do NOT expose without separate product need:

```text
raw_controller_snapshot_json
client_json
auth_context_json

filesystem paths
SQLite paths
SQL internals

OAuth/token data
provider config

raw exception text
source file offsets
retry IDs
internal worker objects
```

Internal:

```text
source_scope_hash
```

is used for integrity/coherence only and is not part of the normal Device Card DTO/UI.

---

# 37. No Omada path

Permanent:

```text
Browser
→ Admin API
→ persisted Current State / accepted Traffic read services
```

Forbidden:

```text
Browser → Omada
Device Current request → Omada
Device Current request → force Current State collection
Device Current request → custom token refresh for new Omada call
live Omada Client Detail fallback
```

---

# 38. No write/control functionality

`DEVICE-CARD-01` is READ ONLY.

Explicitly not included:

```text
Reconnect
Block
Unblock
Hotspot Auth
Hotspot Unauth
Rate Limit
Rename
Lock-to-AP
authentication-period change
```

Client Control is a separate future write/security domain.

---

# 39. Feature flag

Frozen rollout flag:

```text
WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED=false
```

Settings key:

```text
web_admin_device_current_context_enabled
```

Admin config field:

```text
device_current_context_enabled
```

Safe repository default:

```text
false
```

Dependency:

```text
true requires WEB_ADMIN_ENABLED=true
```

Does NOT require:

```text
WEB_ADMIN_TRAFFIC_ENABLED
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED
```

Flag controls product exposure only.

It does NOT start/stop:

```text
Current State
Traffic
Observation
Visit
Registry
OmadaProvider
```

When OFF:

```text
Current section absent
no current frontend request
zero new Device Current read workload
authenticated current endpoint → 404
existing Device Card unchanged
```

---

# 40. Current Guest Traffic service composition is decoupled from Traffic UI

Current Guest Traffic semantic service is reusable by two independent consumers:

```text
Traffic Online Guests
Device Current Context
```

Composition need:

```text
need CurrentGuestTrafficReadService if:

traffic_online_guests_enabled
OR
device_current_context_enabled
```

If both are enabled:

```text
reuse one shared semantic service instance
```

Product exposure states remain independent.

Permanent:

```text
Traffic page disabled
!=
Device Card Current Guest Traffic disabled
```

No UI coupling.

---

# 41. Frontend v1 refresh policy — frozen

Final v1 decision:

```text
NO automatic polling
```

Device Current lifecycle:

```text
one load on Device Card open
+
existing/manual Refresh
```

There is:

```text
NO hidden timer
NO 60s auto-refresh
NO new refresh-seconds setting
NO Traffic coordinator reuse
```

Freshness fields already communicate evidence age.

Future automatic refresh, if product need is proven, requires a separate controlled change.

---

# 42. Frontend functional ownership

Existing Device historical loader remains.

Add a dedicated local function, conceptually:

```text
loadDeviceCurrent()
```

No new framework.

Do NOT use:

```text
CaptivPortalTrafficCoordinator
```

Device Card is not the Traffic page.

Initial Device page load:

```text
historical Device request
+
independent Current request when flag ON
```

Current request failure is local to the Current panel.

Manual Refresh:

```text
refresh historical Device content
+
refresh Current panel
```

No second Current request if one is already in flight.

No automatic retry loop.

---

# 43. Frontend rendering rules

Existing sections remain:

```text
Identity
Latest Site Snapshot
Latest Client Observation
Recent Visits
```

New isolated section:

```text
Current Device Context
```

Recommended visible groups:

```text
Presence
Authorization
Network
Radio
Controller
Current Guest Traffic
Evidence / Freshness
```

Current and historical provenance must remain visually distinguishable.

Presentation MAY label scope as:

```text
Managed Site/SSID scope
```

but API machine scope remains:

```text
client_ssid_allowlist
```

Source data must be rendered with:

```text
textContent / safe DOM construction
```

Forbidden:

```text
innerHTML with source data
raw JSON dump
raw exception text
```

---

# 44. Existing page failure isolation

Mandatory browser acceptance:

```text
base Device Detail = 200
current endpoint = 503
```

must render:

```text
Identity = visible
Latest Snapshot = visible
Latest Observation = visible
Recent Visits = visible
Current Device Context = unavailable
```

Never blank the whole Device page because Current State failed.

---

# 45. One current-context request failure must not erase history

Permanent:

```text
Current Context failure
!=
Device Card failure
```

Also:

```text
Current State available
+
Current Guest Traffic unavailable
→ Presence/Auth/IP/SSID/AP/RSSI/SNR remain available
```

Traffic is a subordinate optional evidence block.

---

# 46. Expected implementation file scope

Subject to mandatory baseline recheck at Owner implementation authorization.

Preferred MODIFY:

```text
app/current_state/read_service.py
app/analytics/current_guest_traffic.py

app/admin_web/query_service.py
app/admin_web/routes.py
app/admin_web/runtime.py
app/admin_web/static/admin.js
app/admin_web/templates/admin/device.html
```

Preferred ADD:

```text
app/admin_web/device_current_context_serialization.py
```

Feature flag is accepted in this FINAL, therefore expected MODIFY:

```text
app/admin_web/config.py
app/config.py
app/settings.py
.env.example
```

Tests:

```text
tests/current_state/**
tests/analytics/test_current_guest_traffic.py
tests/admin_web/**
```

No change expected by default:

```text
app/current_state repository/schema
Current State collectors/workers
Observation schema/worker
Visit Lifecycle
Registry writer
OmadaProvider
Auth/CAPPORT
Traffic formulas
requirements
Grafana/Loki/Alloy
systemd/Nginx
```

`run.py` modification is NOT expected.

If Coder claims `run.py` is required:

```text
STOP
→ show exact composition gap
→ Tech Lead review
```

---

# 47. Coder pre-code PLAN — mandatory after separate authorization

No broad coding before PLAN review.

Even after Owner grants separate implementation authorization, Coder must first provide:

1. exact implementation baseline SHA/tree;
2. exact files to change;
3. existing contracts reused;
4. exact endpoint;
5. exact capability;
6. Site/device membership sequence;
7. Current State entity-read design;
8. exact SQL/read path;
9. index used;
10. `EXPLAIN QUERY PLAN`;
11. Current Guest Traffic entity-projection design;
12. proof no rate formula duplication;
13. one-evaluation/current-cycle coherence design;
14. exact DTO/serializer implementation mapping;
15. semantic-vs-execution failure mapping;
16. feature flag behavior;
17. frontend initial/manual-refresh behavior;
18. expected source/query call count;
19. Admin deadline behavior;
20. targeted tests;
21. performance/boundedness gate;
22. stop conditions.

Coder does not decide architecture outside this frozen contract.

---

# 48. Mandatory security / Site tests

At minimum:

```text
unauthenticated
→ 401

invalid Site
→ 400

forbidden Site
→ 403

feature OFF
→ 404

unknown query param
→ 400

duplicate query param
→ 400

invalid device_id
→ 400

Device not member of Site
→ 404
→ no Current State/Traffic read

same Device evidence in another Site
→ no leakage

admin.read.device
→ required

admin.read.devices
→ not substituted
```

---

# 49. Mandatory Current State tests

```text
fresh complete + MAC present
→ client object
→ online

fresh complete + MAC absent
→ client=null
→ offline

stale + MAC present
→ client=null
→ unknown
→ HTTP 200

stale + MAC absent
→ client=null
→ unknown
→ HTTP 200

semantic freshness_status=unavailable
→ client=null
→ unknown
→ HTTP 200

no complete snapshot safely represented
→ client=null
→ unknown
→ HTTP 200

clock anomaly safely represented
→ client=null
→ unknown
→ HTTP 200

invalid/untrustworthy scope safely represented
→ unknown
→ never false current assertion

authoritative storage/schema/query execution failure
→ controlled HTTP 503

exact entity lookup
→ bounded exact row

no OFFSET
no page scan
```

---

# 50. Mandatory historical/current separation tests

```text
historical Latest Client Observation exists
+
Current State unavailable/stale
→ NOT online

historical Snapshot active=true
+
fresh complete Current State MAC absent
→ offline

historical authStatus says authorized
+
current row absent
→ authorization_classification=unknown
```

No historical fallback.

---

# 51. Mandatory Authorization tests

Current row:

```text
authorized → authorized
pending → pending
other → other
unknown → unknown
```

No current row because fresh absence:

```text
presence=offline
authorization_classification=unknown
authorization_reason=offline
```

Current State unknown:

```text
authorization_classification=unknown
authorization_reason=current_state_unknown
```

Never:

```text
offline → other
offline → unauthorized
```

---

# 52. Mandatory Traffic semantic tests

## Authorized + valid

```text
numeric download/upload/total
existing rate_status/reasons preserved
```

## Authorized + valid zero

```text
0.0 remains numeric 0.0
```

## Pending / other / unknown auth

```text
not_applicable
item=null
NOT 0 Mbps
```

## Offline

```text
not_applicable
item=null
NOT 0 Mbps
```

## Presence unknown

```text
applicability=unknown
item=null
```

## no baseline

```text
successful Traffic semantic result
rate_evidence_status=insufficient_data where existing contract requires
null rate(s)
reason=no_baseline
NOT zero
failure_reason=null
```

## no authorized baseline

```text
reason=no_authorized_baseline
failure_reason=null
```

## SSID transition

```text
reason=ssid_transition
failure_reason=null
```

## invalid elapsed

```text
reason=invalid_elapsed
failure_reason=null
```

## gap too large

```text
reason=baseline_gap_too_large
failure_reason=null
```

## source frozen

```text
reason=source_frozen
failure_reason=null
```

## continuity unproven

```text
reason=connection_continuity_unproven
failure_reason=null
```

## connection reset

```text
reason=connection_reset
failure_reason=null
```

## counter missing

```text
reason=counter_missing
failure_reason=null
```

## counter reset

```text
reason=counter_reset
failure_reason=null
```

Existing paged Online Guests behavior must remain unchanged.

---

# 53. Mandatory Traffic execution-failure tests

## source unavailable exception

```text
HTTP 200
Current State retained

current_guest_traffic:
applicability=applicable
applicability_reason=authorized_current_guest
source_health_status=null
source_health_reason=null
rate_evidence_status=null
current_cycle_id=pinned Current State cycle
baseline_cycle_id=null
elapsed_seconds=null
item=null
failure_reason=source_unavailable
```

## integrity unavailable exception

Same shape, with:

```text
failure_reason=integrity_unavailable
```

## query deadline exception

Same shape, with:

```text
failure_reason=query_deadline
```

Mandatory:

```text
technical Traffic sub-read exception
MUST NOT be labeled insufficient_data
```

---

# 54. Mandatory coherence/race test

Required:

```text
request captures evaluated_at=T

Current State selects cycle A

collector publishes cycle B

Traffic exact projection remains pinned to A
```

Allowed:

```text
A context + A Traffic
```

or:

```text
A context + Traffic unavailable
```

Forbidden:

```text
A context + B Traffic
```

---

# 55. Mandatory source/no-side-effect tests

Prove:

```text
provider_calls = 0
Omada calls = 0

writes = 0
schema mutations = 0
new collection cycles = 0

no forced Current State acquisition
no token refresh caused by custom Omada read
```

---

# 56. Query-plan / boundedness acceptance

Record:

```text
candidate SHA/tree
current-client population size
source DB/snapshot size

source call count
SQL/query count
rows transferred
EXPLAIN QUERY PLAN

duration
response bytes

provider_calls
writes
```

Mandatory qualitative PASS:

```text
exact Device read does not grow by page count
no paged-list search
no all-client materialization for one Device
exact current/baseline target rows
all reads inside existing Admin QueryDeadline
```

If implementation cost grows because it searches pages:

```text
FAIL
```

---

# 57. Testing ownership

Preserve project model:

```text
CODER WRITES
OWNER + TECH LEAD TEST
```

Coder owns:

```text
focused/minimal tests for changed/new code
compileall touched Python scope
static/Node syntax checks where needed
git diff --check
handoff
```

Coder does NOT own or claim:

```text
full regression
Central Lab official PASS
official PERF
production acceptance
```

Owner + Tech Lead / Central Lab own:

```text
targeted cross-surface regression
baseline/candidate differential
full approved gate
query-plan verification
capacity verification
controlled browser acceptance
official PASS/FAIL
```

---

# 58. Mandatory Central Lab regression

Because shared Current State / Current Guest Traffic read contracts are extended:

```text
Current State
Home Live
Devices
existing Device Detail
Traffic-07 Online Guests
Traffic-09 Evidence
Admin Site/security
```

must be included.

No regression in:

```text
Portal
CAPPORT
Auth
Observation
Visit Lifecycle
Visitor Registry
Traffic
```

---

# 59. Controlled Browser Acceptance

Before publication:

1. Existing Device Card loads.
2. Identity block unchanged.
3. Latest Snapshot block unchanged.
4. Latest Observation block unchanged.
5. Recent Visits unchanged.
6. Current Device Context loads independently.
7. Online authorized test phone:
   - Online;
   - Authorized;
   - current IP/SSID/AP;
   - RSSI/SNR when present;
   - current Mbps from accepted Traffic evidence.
8. Pending test phone:
   - Pending;
   - Traffic not applicable;
   - no fabricated zero.
9. Fresh complete scope with Device absent:
   - Offline;
   - UI wording/provenance makes managed-scope meaning clear.
10. Stale/unavailable Current State semantic evidence:
    - HTTP 200;
    - Unknown;
    - never false Offline.
11. Current State execution failure:
    - Current endpoint 503;
    - historical Device Card remains.
12. Traffic sub-read exception:
    - Current State context remains;
    - Traffic failure_reason shown safely;
    - not labeled insufficient_data.
13. Manual Refresh updates both base/history and current panel without duplicate current request.
14. No automatic polling.
15. Traffic page unchanged.
16. No browser request to:
    - Omada;
    - Loki;
    - Grafana;
    - internal Analytics bearer API.

---

# 60. Staged rollout

Frozen feature default:

```text
WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED=false
```

Recommended lifecycle:

```text
merge
        ↓
dormant production deploy
        ↓
feature=false
        ↓
production base smoke
        ↓
separate Owner activation
        ↓
feature=true
        ↓
Device Current production smoke
```

Dormant deploy verifies:

```text
existing Device Card PASS
Traffic PASS
Home PASS
Portal/CAPPORT/Auth PASS
no startup exception
no Device Current request when flag OFF
```

---

# 61. Separate production activation

Implementation/merge does NOT authorize activation.

Activation must confirm:

```text
effective feature flag=true
Device Current endpoint=200 for valid Device
panel visible
online semantics correct
pending semantics correct where safely available
provider_calls=0
no DB writes
Traffic Online Guests unchanged
```

Rollback:

```text
WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED=false
normal restart/readiness verification
```

No DB rollback.

---

# 62. Stop conditions

Coder MUST STOP and return evidence if implementation requires:

```text
new Omada call
new collector
new DB
new schema
new index without EXPLAIN + measured need

changing Current State collector semantics
changing Current State freshness semantics

changing CurrentGuestTraffic rate formula
changing continuity/gap/reset semantics

using Online Guests pagination to locate Device
using Current State pagination to locate Device
all-client materialization for exact entity read

browser-side MAC join
browser-provided authoritative MAC

Latest Observation as Current fallback
Latest Snapshot as Current fallback

coupling Device Current to WEB_ADMIN_TRAFFIC_* product exposure

destructive existing Device Detail change
Site membership semantic change
new Device identity

changing Home semantics
changing Traffic product semantics
changing Visit Lifecycle

global Admin deadline increase
global Admin concurrency increase
new dependency/framework

run.py required without proven composition gap

material implementation-baseline drift
```

Also STOP if:

```text
one evaluated_at/current-cycle coherence cannot be preserved
```

or:

```text
exact Traffic entity path requires a second rate algorithm
```

or:

```text
CurrentClientLookup must expose stale row as current
```

or:

```text
technical Traffic sub-read failure can only be represented
by corrupting existing semantic insufficient_data meaning
```

---

# 63. Canonical acceptance summary

```text
TASK:
DEVICE-CARD-01 — Current Device Context

STATUS:
FINAL — ARCHITECT + TECH LEAD REVIEW INCORPORATED

OWNER STATUS:
READY FOR OWNER FINAL REVIEW

ARCHITECTURE REVIEW BASELINE:
main@3eac6f13d5f3966574f6d1b0a10f531d988f91ec

ARCHITECTURE REVIEW TREE:
e4b5c32946e50a84b21652cee43feabb6b519450

IMPLEMENTATION BASELINE:
exact current origin/main at separate Owner authorization

EXISTING DEVICE CARD:
PRESERVED

BASE DEVICE ENDPOINT:
UNCHANGED

NEW ENDPOINT:
GET /admin/api/v1/sites/<site_id>/devices/<device_id>/current

QUERY PARAMS:
NONE

CAPABILITY:
admin.read.device

SITE MEMBERSHIP:
existing Site Snapshot OR Site Visit evidence

MAC AUTHORITY:
server-side only

CURRENT OWNER:
CurrentStateReadService

CURRENT STATE ENTITY READ:
bounded exact site_id + client_mac

CURRENTCLIENTLOOKUP CLIENT:
non-null only for fresh complete trusted scope + exact MAC present

SCOPE MACHINE TYPE:
client_ssid_allowlist

PRESENCE:
online | offline | unknown

OFFLINE MEANING:
absent from fresh complete managed Site/SSID scope

STALE / UNAVAILABLE / MISSING:
unknown

STALE / UNAVAILABLE SEMANTIC EVIDENCE:
HTTP 200

AUTHORITATIVE CURRENT READ EXECUTION FAILURE:
controlled HTTP 503

HISTORICAL FALLBACK:
FORBIDDEN

CURRENT AUTH:
CurrentClientState.auth_classification only

TRAFFIC OWNER:
CurrentGuestTrafficReadService

TRAFFIC ENTITY READ:
bounded exact client projection

TRAFFIC FORMULA DUPLICATION:
FORBIDDEN

TRAFFIC PAGE SCAN:
FORBIDDEN

TRAFFIC SEMANTIC INSUFFICIENT_DATA:
preserved only for successful semantic result

TRAFFIC TECHNICAL SUB-READ FAILURE:
HTTP 200
rate_evidence_status=null
failure_reason=source_unavailable|integrity_unavailable|query_deadline

NULL != 0:
PERMANENT

CONTROLLER COUNTERS:
cumulative bytes, not Mbps

ONE EVALUATED_AT:
REQUIRED

SAME CURRENT CYCLE:
REQUIRED

ADMIN REQUEST BUDGET:
one concurrency slot + one QueryDeadline

CURRENT STATE FAILURE ISOLATION:
base Device remains usable

TRAFFIC SUB-FAILURE:
Current State remains usable

FEATURE FLAG:
WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED=false

TRAFFIC UI DEPENDENCY:
NO

AUTO REFRESH:
NO

LOAD POLICY:
initial + manual Refresh

NEW OMADA CALL:
NO

NEW COLLECTOR:
NO

NEW DB:
NO

SCHEMA CHANGE:
NO

NEW INDEX:
NO by default

WRITE/CONTROL ACTIONS:
NO

SITE SAFE:
YES

IMPLEMENTATION AUTHORIZATION:
NOT GRANTED

CODER AUTHORIZATION:
NOT GRANTED

BRANCH:
NOT AUTHORIZED

COMMIT/PUSH/PR:
NOT AUTHORIZED

PRODUCTION:
NOT AUTHORIZED
```

---

# 64. FINAL status

```text
ARCHITECTURE_DIRECTION=PASS

REPOSITORY_RECONCILIATION=PASS

FINALIZATION=COMPLETE

STATUS=
FINAL — ARCHITECT + TECH LEAD REVIEW INCORPORATED

READY FOR OWNER FINAL REVIEW

IMPLEMENTATION AUTHORIZATION=NOT GRANTED

CODER AUTHORIZATION=NOT GRANTED
```

This FINAL does not itself authorize implementation.

Next allowed transition:

```text
Owner final review
        ↓
if Owner explicitly approves implementation
        ↓
separate Owner implementation authorization
        ↓
Coder submits mandatory pre-code PLAN
        ↓
PLAN review
        ↓
only then implementation may begin
```
