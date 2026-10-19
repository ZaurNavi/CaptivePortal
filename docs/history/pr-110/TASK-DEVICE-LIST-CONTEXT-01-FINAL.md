# TASK-DEVICE-LIST-CONTEXT-01 — Devices List Context — FINAL

**Project:** CaptivPortal  
**Area:** Admin Console → Devices list  
**Dependency:** `TASK-WEB-DEVICE-UI-01`  
**Related accepted production task:** `TASK-DEVICE-CARD-01 — Current Device Context`  
**Type:** read-only Admin projection/composition architecture  

**Status:** `FINAL — ARCHITECT + TECH LEAD REVIEW INCORPORATED`  
**Implementation authorization:** `NOT GRANTED`  
**Coder authorization:** `NOT GRANTED`  
**GitHub write / branch / commit / push / PR / merge:** `HOLD`  
**Production:** `UNTOUCHED`  
**TASK-WEB-DEVICE-UI-01:** `FROZEN / HOLD`  
**Prepared:** 2026-09-09

---

# 0. Final architecture decision

`TASK-DEVICE-LIST-CONTEXT-01` extends the **existing historical Devices inventory** with list-level context required by the paused Web Designer task:

```text
hostname
current_presence
```

and enables true server-side:

```text
Online-first ordering
```

before pagination.

Canonical model:

```text
existing historical Site Device inventory
        +
one trusted persisted Current State overlay
        ↓
server-side canonical MAC match
        ↓
current_presence
        ↓
Online-first ordering BEFORE LIMIT/cursor
        ↓
bounded context-aware keyset pagination
        ↓
enriched Admin Devices list DTO
```

Permanent:

```text
Devices membership
=
existing Registry / Visit Device boundary

Current State
=
current overlay only

Current State
DOES NOT create Device membership
```

A Current State client that has no accepted historical Device membership does not become a new Devices-list row in this TASK.

---

# 1. Repository / KB / application baseline

Architecture FINAL is bound to:

```text
CURRENT REPOSITORY MAIN =
fd12f16c1f64900ce4096b3509a3b52d6bfe1b46

TREE =
edb5bab5479a4417d545429eeacf2b29a640e441
```

This is:

```text
PR #109
Docs: reconcile DEVICE-CARD-01 production closure
```

PR #109 is docs-only.

Current deployed application baseline remains:

```text
SHA =
7df71a8e807efd74b123117e78cb8d992c190fa1

CODE TREE =
8f1342f0a0f1e8242642161e02b2f3276e6ddf51
```

Permanent distinction:

```text
repository main
!=
deployed application commit

docs-only merge
!=
runtime architecture change
```

Post-PR-109 Knowledge Base is canonical documentation authority.

Especially:

```text
docs/tasks/TASK-DEVICE-CARD-01-FINAL.md
```

---

# 2. Implementation baseline rule

This FINAL does not itself freeze a future Coder baseline.

At separate Owner implementation authorization:

```text
implementation baseline =
exact current origin/main SHA/tree at that moment
```

Required:

```text
git fetch origin
re-pin origin/main SHA/tree
impact review
```

Mandatory architecture re-review if drift affects:

```text
app/admin_web/device_gateway.py
app/admin_web/query_service.py
app/admin_web/runtime.py
app/admin_web/routes.py
app/admin_web/cursors.py

app/current_state/**

app/admin_web/config.py
app/config.py
app/settings.py

Admin security / Site policy
Device list DTO/cursor semantics
Device Current semantics
```

---

# 3. Exact TASK scope

In scope:

```text
raw hostname in Devices list
current_presence
Current State overlay metadata
server-side Online-first ordering
context-aware cursor consistency
initial Current overlay fail-open behavior
trusted continuation integrity
bounded Site-safe composition
feature rollout
```

Out of scope:

```text
Device Detail redesign
Device Current contract changes

Current Guest Traffic in Devices list
Traffic rates in Devices list

Visit Detail / Visit Traffic
Snapshot History
Observation History
Device Summary / Intelligence

Reconnect
Block / Unblock
Hotspot Auth / Unauth
Rate Limit
Lock-to-AP
Rename

new Device identity
new Device membership
new Registry persistence
new Current State collection

frontend polling
Web Designer visual implementation
```

---

# 4. Existing Devices endpoint remains the product

Existing endpoint remains:

```text
GET /admin/api/v1/sites/<site_id>/devices
```

Existing capability remains:

```text
admin.read.devices
```

Existing query parameters remain:

```text
limit
cursor
mac
```

No second public Devices-list endpoint is introduced.

Feature ON enriches the same product.

Feature OFF preserves the old production path exactly.

---

# 5. Existing historical membership semantics remain canonical

Site Device membership remains:

```text
Site Snapshot evidence
OR
Site Visit evidence
```

Forbidden as membership authority:

```text
Current State row alone
Registry global last_site_id
Registry global last_*
Latest Observation alone
```

Current State may decorate a known Device row only.

No cross-Site fallback.

---

# 6. Semantic owners

## Historical inventory / identity / Site membership

Owner:

```text
existing Admin Device read boundary
AdminDeviceReadGateway
Registry / Visit persisted evidence
```

## Hostname

Owner:

```text
latest requested-Site Device Snapshot
through existing Admin Device projection
```

## Current Presence

Owner:

```text
CurrentStateReadService
```

using the already accepted `TASK-DEVICE-CARD-01` semantics.

## List ordering / pagination composition

Owner:

```text
Admin Devices list composition boundary
```

This is composition only.

It does not become a new domain semantic owner.

---

# 7. Existing AdminDeviceReadGateway execution paths

Tech Lead review decision is frozen:

```text
USE EXISTING AdminDeviceReadGateway
WITH A NEW SEPARATE CONTEXT METHOD/PATH
```

Canonical:

```text
AdminDeviceReadGateway.list_devices(...)
=
existing historical path
=
UNCHANGED
```

New context-enabled path:

```text
AdminDeviceReadGateway.list_devices_context(...)
```

or repository-consistent equivalent name.

No sibling gateway is required by architecture.

Reason:

```text
avoid duplicating Registry/Visit historical membership SQL
avoid identity/membership semantic drift
preserve one historical projection owner
```

---

# 8. Feature OFF must use the old path directly

Permanent invariant:

```text
WEB_ADMIN_DEVICE_LIST_CONTEXT_ENABLED=false
        ↓
AdminDeviceReadGateway.list_devices(...)
        ↓
existing SQL
existing historical order
existing cursor
existing serializer/DTO
NO Current DB attach/read
NO Current overlay work
```

Feature OFF must not merely produce equivalent results through the new context code.

It must preserve the direct old execution path.

---

# 9. Existing Device list DTO and Device Detail Identity must not drift

Current repository reuses:

```text
_device_list_dto(item)
```

for:

```text
Devices list
Device Detail → identity
```

Therefore this TASK MUST NOT add context fields to the shared historical row/serializer in a way that automatically changes Device Detail Identity.

Permanent:

```text
FEATURE OFF Device list DTO
=
exact current production DTO

Device Detail identity
=
unchanged
```

Feature ON Devices list receives a separate enriched projection.

Architecture permits a dedicated type/serializer, conceptually:

```text
AdminDeviceListContextRow
serialize_device_list_context(...)
```

Exact naming is Tech Lead implementation territory.

---

# 10. Hostname contract

Canonical v1 list field:

```text
hostname: string | null
```

Source:

```text
latest requested-Site Snapshot
→ hostname
```

The gateway already reads:

```text
name
hostname
system_name
```

No new source is required.

## No fallback

Forbidden backend fallback:

```text
hostname
→ name
→ system_name
→ MAC
```

If hostname is missing:

```text
hostname=null
```

Presentation may later show:

```text
—
```

`device_type` remains a separate field.

---

# 11. Current Presence must reuse DEVICE-CARD-01 semantics

List Presence machine values:

```text
online
offline
unknown
```

Canonical accepted semantics:

```text
fresh + complete + trusted + MAC present
→ online

fresh + complete + trusted + MAC absent
→ offline

stale
→ unknown

unavailable
→ unknown

invalid timestamp
→ unknown

untrusted/incompatible scope
→ unknown
```

Permanent:

```text
stale != offline
unavailable != offline
invalid timestamp != offline
```

List `offline` means only:

```text
not present in the fresh complete managed Current State client scope
```

It is not a universal physical-device-offline claim.

---

# 12. Historical facts are never Current Presence authority

Forbidden Presence heuristics:

```text
site_last_seen_at
Latest Snapshot active
Latest Client Observation
Visit status
historical auth_status
IP
SSID
AP
Registry last_*
browser inference
```

Cross-surface invariant:

```text
same Site
same canonical MAC
same evaluated_at
same accepted Current cycle
→ Devices list presence == Device Current presence
```

---

# 13. Exact single-Device Current contract remains unchanged

Existing production endpoint remains:

```text
GET /admin/api/v1/sites/<site_id>/devices/<device_id>/current
```

Capability:

```text
admin.read.device
```

DTO:

```text
admin.device.current.v1
```

This TASK MUST NOT:

```text
modify its semantics
wrap it as list source
call it once per row
weaken its trust/freshness rules
```

---

# 14. list_current_clients() is NOT the Presence semantic boundary

Existing:

```text
CurrentStateReadService.list_current_clients(...)
```

is a general Current client population product.

It MUST NOT be reused as the architectural Presence selector for this task.

Forbidden:

```text
list_current_clients(...)
→ infer trusted list Presence semantics
```

A dedicated narrow Current State inventory-context descriptor is required.

---

# 15. New narrow Current State inventory-context descriptor

Required conceptual method:

```text
CurrentStateReadService.get_current_client_inventory_context(...)
```

or repository-consistent equivalent.

Conceptual return:

```text
CurrentClientInventoryContext
```

with:

```text
site_id
evaluated_at_utc
snapshot
overlay_mode = trusted | unknown
```

When trusted:

```text
current_cycle_id
source_scope_hash
```

The descriptor does NOT return:

```text
Device list rows
per-Device projections
full Current population
```

---

# 16. Inventory-context semantic responsibility

`CurrentStateReadService` alone must:

```text
select complete-success client cycle
validate exact Site
validate canonical client_ssid_allowlist scope
validate source_scope_hash
validate source_scope_json
validate source_scope_version
evaluate timestamp
evaluate freshness
decide trusted vs unknown
validate pinned cycle on continuation
```

It MUST reuse/factor the accepted logic already used by:

```text
CurrentStateReadService.get_current_client(...)
```

No second Presence policy.

---

# 17. Overlay modes

Frozen machine modes:

```text
trusted
unknown
```

## trusted

Only when:

```text
complete-success client snapshot exists
freshness_status=fresh
Site matches
canonical client_ssid_allowlist scope matches
scope hash/json/version trusted
timestamp trusted
```

Then MAC membership in the pinned cycle may determine:

```text
online
offline
```

## unknown

When:

```text
stale
unavailable
no complete trusted snapshot
invalid timestamp
untrusted/incompatible scope
other safely represented non-trusted Current evidence
```

Then:

```text
all historical rows
→ current_presence=unknown
```

No Current ordering is applied.

---

# 18. Current DB rows may be consumed only after semantic selection

After `CurrentStateReadService` returns a trusted descriptor:

```text
site=S
cycle=A
scope_hash=H
overlay_mode=trusted
```

the Admin Device context gateway may perform a read-only set-based composition against:

```text
current_client_state
```

for:

```text
cycle_id=A
site_id=S
canonical MAC
```

The gateway MUST NOT independently choose:

```text
latest cycle
freshness
scope trust
overlay mode
stale/offline meaning
```

Permanent:

```text
CurrentStateReadService
=
semantic selector / validator

AdminDeviceReadGateway.list_devices_context
=
set-based consumer of already selected evidence
```

---

# 19. Runtime injection of Current State DB path

No root lifecycle redesign is required.

Existing runtime already receives:

```text
current_state_read_service
```

and that service has its repository/config boundary.

Architecture permits:

```text
Admin runtime
→ CurrentStateReadService
→ Current State read-only repository/db path
→ AdminDeviceReadGateway context composition
```

No new lifecycle root.

No query-time Omada.

Feature OFF causes no additional list Current workload.

---

# 20. Existing Current State key/index boundary

Candidate design is compatible with existing:

```text
PRIMARY KEY(cycle_id, client_mac)
```

for:

```text
current_client_state
```

Preferred set-based membership join uses:

```text
pinned cycle_id
+
canonical MAC
```

Architecture decision:

```text
NEW CURRENT STATE INDEX = NOT JUSTIFIED
NEW SCHEMA = NOT JUSTIFIED
```

Actual performance remains acceptance-gated.

If measured query plan requires schema/index change:

```text
STOP
→ return evidence
→ architecture re-review
```

---

# 21. No Current-only Device insertion

A Current client with no historical Device membership:

```text
Current State MAC exists
+
no Site Snapshot/Visit Device identity
```

does NOT become a Devices row.

Permanent:

```text
Devices
=
historical inventory + Current overlay

NOT
=
historical inventory UNION Current population
```

---

# 22. Pre-pagination Online-first is mandatory

True Online-first must be computed before:

```text
LIMIT
cursor position
page construction
```

Forbidden:

```text
fetch historical page
→ decorate
→ browser sort
```

or:

```text
fetch page
→ sort only that page server-side
```

because online Devices may be outside the historical first page.

---

# 23. Canonical Online-first ordering

For:

```text
overlay_mode=trusted
```

canonical key:

```text
online_rank ASC
site_last_seen_at DESC
device_id DESC
```

with:

```text
online → online_rank=0
all other historical rows → online_rank=1
```

Therefore:

```text
all Current Online known Devices first
then remaining historical Devices
```

Within each bucket, preserve the accepted historical ordering.

The gateway receives `overlay_mode`.

It does not decide trusted vs unknown itself.

---

# 24. Unknown-overlay ordering

For:

```text
overlay_mode=unknown
```

all rows have:

```text
current_presence=unknown
```

Ordering is exactly:

```text
site_last_seen_at DESC
device_id DESC
```

No Current membership governs ordering.

---

# 25. Existing MAC filter remains a filter only

Existing:

```text
mac
```

query parameter remains supported.

It is:

```text
filter only
```

It is NOT:

```text
semantic identity authority
cross-Site identity selector
```

The resulting historical Device identity still comes from the accepted Site Device boundary.

---

# 26. Dedicated Device List Context cursor contract

The existing generic Admin cursor v1 MUST remain untouched.

Do NOT:

```text
add new fields to generic v1 payload
bump global cursor version
change existing kind=devices cursor behavior
```

Feature OFF continues to use:

```text
existing generic cursor
kind=devices
```

Feature ON uses a dedicated context cursor codec/version.

Conceptual:

```text
DeviceListContextCursor v1
kind=devices_context
```

Exact module/helper naming is Tech Lead technical territory.

---

# 27. Dedicated context cursor payload

Conceptual exact semantic payload must contain:

```text
version
kind=devices_context

site_id
filter fingerprint
ordering_contract_version

overlay_mode

evaluated_at_utc

if overlay_mode=trusted:
    current_cycle_id
    source_scope_hash

last key:
    online_rank
    site_last_seen_at
    device_id
```

The browser treats cursor as opaque transport.

Internal semantic fields are not normal public DTO fields.

---

# 28. Cursor opacity is NOT semantic authority

Permanent invariant:

```text
CURSOR CONTENT IS NOT CURRENT STATE SEMANTIC AUTHORITY
```

A returned caller-controlled cursor cannot itself prove:

```text
trusted Current scope
freshness
cycle validity
Current Presence
```

On continuation the server MUST revalidate through trusted server-side boundaries.

Required revalidation includes:

```text
requested Site

filter fingerprint
ordering contract version

current configured canonical client scope

if trusted:
    pinned cycle exists
    pinned cycle Site matches
    kind=client
    result=success
    complete=true
    source scope hash matches
    scope json/version remains compatible
    evaluated-at/cycle relationship remains safe
```

`online_rank` is only a keyset position value.

It never determines row Presence.

---

# 29. Cursor integrity architecture decision

Architecture chooses:

```text
SERVER-SIDE REVALIDATION IS MANDATORY
```

A dedicated context cursor codec may add transport-integrity protection if existing project conventions later justify it, but FINAL does not rely on caller-returned cursor fields alone.

Semantic trust always comes from server-side Current State revalidation.

Therefore:

```text
opaque != trusted
canonical encoding != semantic authority
```

Coder may not weaken this rule.

---

# 30. One evaluated-at / one overlay per pagination chain

First page establishes:

```text
evaluated_at_utc=T
overlay_mode
```

If trusted:

```text
current_cycle_id=A
source_scope_hash=H
```

All continuation pages in that chain use the same:

```text
T
overlay mode
A/H when trusted
```

Collector publication of cycle B does not alter that chain.

---

# 31. Trusted continuation behavior

Example:

```text
page 1
→ overlay_mode=trusted
→ cycle=A

collector publishes B

page 2
→ revalidate and use A
```

Forbidden:

```text
page 2 silently uses B
```

If pinned A can no longer be safely resolved:

```text
cursor_expired
```

or another existing controlled continuation failure where appropriate.

Do not silently switch ordering mode.

---

# 32. Unknown-chain continuation behavior

If page 1 establishes:

```text
overlay_mode=unknown
```

the entire cursor chain remains:

```text
overlay_mode=unknown
historical ordering
all current_presence=unknown
```

Even if Current State becomes fresh before page 2.

A new:

```text
Refresh
or new page-1 request
```

may establish trusted mode.

Permanent:

```text
cursor-chain ordering mode
takes precedence over newly observed Current State
for continuation consistency
```

---

# 33. Root overlay metadata

Context-enabled list result includes a root metadata object:

```text
current_state_overlay
```

Required machine fields:

```text
overlay_mode:
trusted | unknown

ordering_applied:
true | false
```

Meaning:

```text
trusted
→ ordering_applied=true

unknown
→ ordering_applied=false
```

This tells UI and diagnostics whether Current membership actually governed ordering.

---

# 34. Root Current overlay semantic metadata

Conceptual public metadata:

```json
{
  "current_state_overlay": {
    "overlay_mode": "trusted",
    "ordering_applied": true,
    "source_execution_status": "available",
    "evaluated_at_utc": "...",
    "scope": {
      "scope_type": "client_ssid_allowlist",
      "site_id": "<site_id>",
      "ssids": ["Zefer_Parki"]
    },
    "snapshot": {
      "observed_at": "...",
      "capture_finished_at": "...",
      "age_seconds": 12.0,
      "freshness_status": "fresh",
      "freshness_reason": "within_freshness_window",
      "complete": true
    }
  }
}
```

Normal UI DTO does NOT require:

```text
source_scope_hash
current_cycle_id
raw storage scope
```

Those remain internal cursor/integrity details.

---

# 35. Initial unknown semantic evidence

If the Current State read executes safely but evidence is:

```text
stale
unavailable
invalid timestamp
untrusted scope
no complete trusted snapshot
```

initial list response:

```text
HTTP 200
overlay_mode=unknown
ordering_applied=false
source_execution_status=available

all current_presence=unknown
historical ordering
```

This is semantic Current evidence state, not execution failure.

---

# 36. Initial Current State execution failure

If Current State selection cannot execute safely:

```text
source/storage/query execution failure
```

preferred initial result, where historical query can still complete within the Admin budget:

```text
HTTP 200
overlay_mode=unknown
ordering_applied=false
source_execution_status=unavailable
snapshot=null

all current_presence=unknown
historical ordering
```

Permanent:

```text
Current overlay unavailable
!=
historical Devices unavailable
```

If overall Admin deadline is exhausted and historical query cannot complete safely, normal Admin deadline behavior still applies.

---

# 37. Trusted continuation failure

A trusted continuation cannot fail-open by silently switching to unknown historical ordering.

If pinned Current evidence cannot be safely read/revalidated:

```text
do not reorder the chain
do not switch overlay mode
```

Use controlled continuation failure.

Pinned context no longer safely resolvable:

```text
AdminQueryCursorExpired
code=cursor_expired
```

is the canonical existing public restart-pagination convention.

---

# 38. Cursor expiry cases

Use existing:

```text
AdminQueryCursorExpired
cursor_expired
```

for:

```text
pinned cycle retention expiry
pinned cycle missing
required pinned scope/context incompatibility
pinned context no longer safely resolvable
```

Do not introduce a second public cursor-expiry error code without separate need.

---

# 39. Historical consistency boundary

This TASK freezes Current overlay consistency across `Load More`.

It does NOT redesign historical Registry/Visit list reads into a full transactional historical snapshot.

Existing historical keyset semantics remain baseline.

New guarantee:

```text
Current State changes between pages
MUST NOT reorder one context cursor chain
```

---

# 40. Context-enabled list item DTO

Feature ON preserves all existing list fields and adds:

```text
hostname: string | null

current_presence:
online | offline | unknown
```

Existing fields remain:

```text
device_id
canonical_mac
device_type

site_first_seen_at
site_last_seen_at
site_snapshot_count
site_visit_count

last_site_ip
last_site_ssid
last_site_ap_mac
```

No Current:

```text
IP
AP
RSSI
SNR
authorization
Traffic Mbps
```

is added to the list by this TASK.

---

# 41. Separate context serializer/projection

Feature ON MUST use a separate enriched projection/serializer.

It must not rely on modifying the historical `_device_list_dto()` contract in a way that alters:

```text
Feature OFF list
Device Detail identity
```

Conceptual architecture:

```text
historical AdminDeviceRow
        +
context enrichment
        ↓
AdminDeviceListContextRow
        ↓
serialize_device_list_context(...)
```

Exact naming is Tech Lead territory.

---

# 42. Context-enabled root DTO

Conceptual:

```json
{
  "items": [
    {
      "device_id": "...",
      "canonical_mac": "AA:BB:CC:DD:EE:FF",
      "hostname": "phone-or-null",
      "device_type": "android",
      "site_first_seen_at": "...",
      "site_last_seen_at": "...",
      "site_snapshot_count": 4,
      "site_visit_count": 7,
      "last_site_ip": "...",
      "last_site_ssid": "...",
      "last_site_ap_mac": "...",
      "current_presence": "online"
    }
  ],
  "current_state_overlay": {
    "overlay_mode": "trusted",
    "ordering_applied": true,
    "source_execution_status": "available",
    "evaluated_at_utc": "...",
    "scope": {
      "scope_type": "client_ssid_allowlist",
      "site_id": "<site_id>",
      "ssids": ["Zefer_Parki"]
    },
    "snapshot": {
      "observed_at": "...",
      "capture_finished_at": "...",
      "age_seconds": 12.0,
      "freshness_status": "fresh",
      "freshness_reason": "within_freshness_window",
      "complete": true
    }
  }
}
```

Existing page envelope remains:

```text
limit
next_cursor
```

with the new dedicated context cursor only when feature ON.

---

# 43. Public scope machine contract

Reuse canonical:

```text
scope_type=client_ssid_allowlist
```

No new scope enum.

Public safe scope:

```json
{
  "scope_type": "client_ssid_allowlist",
  "site_id": "<site_id>",
  "ssids": ["<configured exact SSID>"]
}
```

---

# 44. One Admin slot / one QueryDeadline

One context-enabled Devices request remains:

```text
one AdminQueryExecutionControls slot
one QueryDeadline
```

Expected constant logical work:

```text
1 narrow Current inventory-context selection/validation
+
1 set-based Device context page query
```

No:

```text
per-row Current read
second Admin concurrency slot
global deadline increase
global concurrency increase
```

---

# 45. QueryDeadline nuance

The narrow Current State context selector is not required by architecture to accept the Admin `QueryDeadline` directly if current repository patterns safely use:

```text
deadline.require_remaining()
→ Current State call
→ deadline.require_remaining()
```

The set-based Device composition gateway must continue to use existing SQLite deadline/progress enforcement.

If measurements show the narrow Current selection itself can exceed the existing Admin budget:

```text
return evidence
```

Do not increase global timeout by default.

---

# 46. Current population bound

Do NOT freeze:

```text
10000
```

as a new architecture hard limit.

Correct contract:

```text
list overlay is bounded by accepted configured
CurrentStateConfig.client_max_rows
```

Repository default currently:

```text
10000
```

Capacity acceptance must record:

```text
actual configured Current population bound
actual tested population
```

If implementation supports only a smaller bound, that must become an explicit reviewed configuration/contract.

No hidden lower limit.

---

# 47. Existing Device page-size bounds remain

Existing repository defaults/bounds remain authoritative.

No page-size increase is introduced by this TASK.

Architecture expects existing:

```text
WEB_ADMIN_DEVICE_PAGE_SIZE
```

behavior to remain bounded.

Feature ON changes ordering/DTO, not page-size policy.

---

# 48. Performance status

Architecture form is accepted:

```text
set-based pinned-current membership composition
before LIMIT
```

But:

```text
PERFORMANCE=UNPROVEN
```

until measured.

Architecture FINAL does not pre-declare performance PASS.

---

# 49. Mandatory future query-plan/capacity gate

Before acceptance measure:

```text
EXPLAIN QUERY PLAN

representative populated Registry DB
representative Visit DB
representative Current State DB

page 1
continuation
exact MAC filter
large historical inventory
Current population at accepted configured bound
```

Record:

```text
baseline/candidate SHA/tree

historical Device count
snapshot count
visit count
Current client count
configured client_max_rows

page size

source call count
SQL/query count
rows transferred

query plan

p50
p95
max

response bytes

provider_calls
writes
```

Mandatory PASS qualities:

```text
Current membership composition before LIMIT

bounded pinned-cycle Current lookup

no Current page-scan loop

no full historical Python materialization

no N+1

stable Online-first keyset

fits existing QueryDeadline

provider_calls=0
writes=0
```

---

# 50. Feature flag

Frozen flag:

```text
WEB_ADMIN_DEVICE_LIST_CONTEXT_ENABLED=false
```

Repository-safe default:

```text
false
```

Dependency:

```text
true requires WEB_ADMIN_ENABLED=true
```

Independent from:

```text
WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED
WEB_ADMIN_TRAFFIC_ENABLED
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED
```

Flag controls list product exposure/composition only.

---

# 51. Feature OFF exact isolation

Permanent:

```text
FLAG OFF
→ existing AdminDeviceReadGateway.list_devices()
→ existing generic devices cursor
→ existing _device_list_dto()
→ exact old Device list DTO/order
→ Device Detail identity unchanged
→ zero Current overlay reads
→ zero Current DB list workload
```

This is stricter than mere behavioral equivalence.

---

# 52. Feature ON execution path

Feature ON:

```text
same GET /devices endpoint
same capability=admin.read.devices
same limit/mac surface

+
new Current inventory descriptor
+
AdminDeviceReadGateway.list_devices_context(...)
+
separate context serializer
+
dedicated devices_context cursor
+
hostname
+
current_presence
+
root Current overlay metadata
+
Online-first
```

No user-selectable sort is added in v1.

---

# 53. No Current Guest Traffic in list

`CurrentGuestTrafficReadService` is OUT OF SCOPE.

Do not add:

```text
download_mbps
upload_mbps
total_mbps
Traffic evidence
```

to Devices list.

Existing Traffic semantic rule remains untouched:

```text
0 Mbps = valid evidence
0 != null
```

but is not consumed here.

---

# 54. Security / Site isolation

Required boundary:

```text
authenticated Admin session
        ↓
canonical Site resolution
        ↓
Site allowlist / policy
        ↓
admin.read.devices
        ↓
historical Site Device inventory
        +
Current State same Site
        ↓
server-side canonical MAC match
        ↓
safe list projection
```

Forbidden:

```text
Current State from another Site
cross-Site Registry current context
client-provided MAC as identity authority
cross-Site fallback
```

Existing `mac` query parameter remains filter-only.

---

# 55. Runtime lifecycle

Architecture answer:

```text
existing app/admin_web/runtime.py
+
existing _query_service(...) construction boundary
is sufficient
```

No root application lifecycle change is expected.

`run.py` is not expected to change.

If later claimed necessary:

```text
STOP
→ show exact composition gap
→ Tech Lead review
```

---

# 56. Expected repository areas to change

Expected MODIFY:

```text
app/admin_web/device_gateway.py
app/admin_web/query_service.py
app/admin_web/runtime.py

app/current_state/read_service.py

app/admin_web/config.py
app/config.py
app/settings.py
.env.example
```

Expected dedicated context cursor code:

```text
new Device List Context cursor codec/helpers
```

This may be:

```text
new dedicated module
```

or narrowly isolated helpers, but generic `app/admin_web/cursors.py` v1 semantics must remain unchanged.

Likely dedicated serializer:

```text
app/admin_web/device_list_context_serialization.py
```

`app/admin_web/routes.py` should require only minimal feature/cursor handling reconciliation if needed.

---

# 57. Generic cursor v1 is NO-TOUCH semantically

Current generic cursor v1 is shared Admin infrastructure.

This TASK MUST NOT:

```text
change its payload shape
change its version
weaken exact validation
change existing kind=devices behavior
affect Visits/Observations/other consumers
```

Feature OFF uses it unchanged.

Feature ON uses dedicated context cursor code.

---

# 58. Areas not expected to change

Do NOT change by default:

```text
Device Current endpoint / DTO semantics

Current State schema
Current State collectors/workers
Current State cadence

Visitor Registry writer/schema
Visit Lifecycle
Observation acquisition/schema

CurrentGuestTrafficReadService
Traffic formulas/products

OmadaProvider
Auth/CAPPORT
Pending Session Cleaner

requirements
Grafana/Loki/Alloy
systemd/Nginx
```

---

# 59. Explicit forbidden approaches

Forbidden:

```text
N /devices/<id>/current requests

N get_current_client() calls

list_current_clients() as Presence semantic authority

page-local Online sorting

browser sorting for global Online-first

historical heuristic Online/Offline

stale Current State → Offline
unavailable Current State → Offline

Current-only client insertion

gateway independently selecting Current latest cycle

gateway deciding freshness/trust

generic Admin cursor v1 modification

caller cursor treated as semantic authority

silent trusted→unknown ordering switch mid-chain

silent cycle A→B switch mid-chain

full historical Python materialization

Current page scan loop

per-row DB connection

new DB/cache/table

new collector/poller

query-time Omada

new Traffic calculation

frontend polling

write/control action
```

---

# 60. Acceptance — hostname

Must prove:

```text
latest requested-Site Snapshot hostname exists
→ exact list hostname

hostname missing
→ null

name exists + hostname null
→ hostname remains null

system_name exists + hostname null
→ hostname remains null

newer hostname in another Site
→ no leak
```

---

# 61. Acceptance — Presence

Must prove:

```text
trusted fresh complete + historical MAC present
→ online

trusted fresh complete + historical MAC absent
→ offline

stale
→ unknown

unavailable
→ unknown

invalid timestamp
→ unknown

untrusted scope
→ unknown

historical Observation says active
+
Current overlay unknown
→ unknown

historical Snapshot active=true
+
trusted fresh Current absence
→ offline
```

---

# 62. Acceptance — inventory boundary

Must prove:

```text
Current State MAC
+
no historical Site Device membership
→ no Devices row
```

Also:

```text
historical Device
+
trusted fresh Current absence
→ Device remains in list
→ current_presence=offline
```

---

# 63. Acceptance — Online-first

Use historical inventory significantly larger than one page.

Example:

```text
online Device historical rank=430
online Device historical rank=1700
```

Required:

```text
both participate in global Online-first ordering
before any non-online row that sorts after them by canonical key
```

No browser `Load More` may be required merely for an online Device to become eligible for the Online bucket.

---

# 64. Acceptance — cursor race

Test:

```text
page 1:
T
overlay=trusted
cycle=A

collector publishes B

Load More
```

Required:

```text
continuation revalidates A
ordering remains against A
```

No:

```text
duplicate from A→B movement
skip from A→B movement
silent B switch
```

Refresh/new page 1 may select B.

---

# 65. Acceptance — unknown chain

Page 1:

```text
overlay_mode=unknown
ordering_applied=false
```

Current State recovers before page 2.

Required page 2:

```text
overlay_mode=unknown
ordering_applied=false
historical ordering
all current_presence=unknown
```

Only new page 1/Refresh may switch to trusted.

---

# 66. Acceptance — cursor semantic integrity

Tampered/caller-provided cursor content must NOT be able to:

```text
make stale cycle trusted
select foreign Site Current evidence
change configured scope
force online_rank semantics
make missing cycle authoritative
```

Server-side revalidation must reject unsafe context.

Pinned context no longer resolvable:

```text
cursor_expired
```

---

# 67. Acceptance — initial fail-open

Initial Current source execution failure:

```text
historical query still fits deadline
→ HTTP 200
→ overlay_mode=unknown
→ ordering_applied=false
→ source_execution_status=unavailable
→ current_presence=unknown
```

Never false Offline.

---

# 68. Acceptance — trusted continuation failure

Trusted continuation loses safe pinned evidence:

```text
DO NOT silently use historical-only ordering
DO NOT silently use newer Current cycle
```

Use controlled cursor/source failure.

---

# 69. Acceptance — feature OFF regression

Feature OFF must prove exact current production path:

```text
old list_devices()
old cursor
old serializer
old DTO
old ordering
no Current DB access
```

Device Detail Identity:

```text
unchanged
```

---

# 70. Acceptance — feature ON compatibility

Feature ON:

```text
existing historical fields preserved
hostname added
current_presence added
root overlay metadata added
Online-first intentional
mac filter preserved
Load More preserved
```

Existing Device Detail:

```text
unchanged
```

Existing Device Current:

```text
unchanged
```

---

# 71. Tests / benchmarks to extend

Prefer extending:

```text
tests/admin_web/test_device_gateway.py
tests/admin_web/test_query_service.py
tests/admin_web/test_routes.py
tests/admin_web/test_runtime.py
tests/admin_web/test_config.py
tests/admin_web/benchmark_device_gateway.py

tests/current_state/test_read_service.py
```

Mandatory cross-surface regression:

```text
tests/admin_web/test_device_current_context.py
tests/admin_web/test_device_current_context_frontend.py
```

to prove Device Current semantics remain unchanged.

Do not create an unnecessary parallel testing universe.

---

# 72. Testing ownership

Project model remains:

```text
CODER WRITES
OWNER + TECH LEAD TEST
```

After future authorization, Coder owns only:

```text
focused tests for touched/new code
compile/syntax checks
git diff --check
handoff
```

Owner + Tech Lead / Central Lab own:

```text
repository rebind
query-plan verification
capacity gate
cross-surface regression
controlled browser acceptance
official PASS/FAIL
```

---

# 73. Web Designer dependency

Until this backend contract is implemented and accepted:

```text
TASK-WEB-DEVICE-UI-01 = FROZEN / HOLD
CURRENT PATCH = PRESERVED
```

After acceptance, presentation may rely on:

```text
hostname
current_presence
server Online-first order
stable Load More cursor
```

UI rule:

```text
green dot
=
current_presence=online
```

Absence of a green dot must not itself be presented as proof of Offline.

---

# 74. Feature rollout

Repository safe default:

```text
WEB_ADMIN_DEVICE_LIST_CONTEXT_ENABLED=false
```

Recommended lifecycle:

```text
implementation
→ accepted gates
→ merge
→ dormant deploy flag=false
→ baseline production smoke
→ separate Owner activation
→ flag=true
→ Devices context smoke
```

Feature flag does not start/stop:

```text
Current State collector
Registry
Visit
Observation
OmadaProvider
Traffic
```

It is an Admin list exposure/composition flag only.

---

# 75. Stop conditions

Tech Lead / later Coder MUST STOP and return evidence if implementation requires:

```text
new Device membership semantics

Current-only Device insertion

historical→Current heuristic

stale/unavailable→Offline

per-row Current reads

list_current_clients() as Presence authority

page-local/browser Online sorting

full historical Python materialization

unbounded Current scan

gateway-owned Current semantic selection

generic cursor v1 modification

caller cursor as Current semantic authority

silent cursor ordering-mode switch

new DB/cache/schema

new Current State index without measured proof

new collector/poller

query-time Omada

Device Current semantic change

Traffic calculation

global Admin deadline/concurrency increase

frontend polling

write/control functionality

root lifecycle/run.py change without proven composition gap
```

Any requires architecture re-review.

---

# 76. Canonical FINAL summary

```text
TASK:
TASK-DEVICE-LIST-CONTEXT-01

STATUS:
FINAL — ARCHITECT + TECH LEAD REVIEW INCORPORATED

REPOSITORY BASELINE:
fd12f16c1f64900ce4096b3509a3b52d6bfe1b46

TREE:
edb5bab5479a4417d545429eeacf2b29a640e441

PRODUCT:
existing historical Devices inventory
+
trusted Current State overlay

HISTORICAL MEMBERSHIP OWNER:
existing Registry / Visit Device boundary

CURRENT-ONLY DEVICE INSERTION:
NO

HOSTNAME:
latest requested-Site Snapshot hostname
raw-only
nullable
no fallback

CURRENT PRESENCE OWNER:
CurrentStateReadService

PRESENCE:
online | offline | unknown

PRESENCE POLICY:
same as DEVICE-CARD-01

CURRENT STATE LIST DESCRIPTOR:
new narrow inventory-context method

list_current_clients AS PRESENCE AUTHORITY:
FORBIDDEN

GATEWAY:
existing AdminDeviceReadGateway
+
new separate list_devices_context path

OLD list_devices PATH:
UNCHANGED

FEATURE OFF:
direct old execution path
exact old DTO/cursor/order
zero Current reads

FEATURE ON:
enriched list context path

ONLINE-FIRST:
server-side
before pagination

ORDER:
online_rank ASC
site_last_seen_at DESC
device_id DESC

UNKNOWN OVERLAY ORDER:
historical order only

CURSOR:
dedicated Device List Context cursor/version

GENERIC CURSOR V1:
UNCHANGED

CURSOR SEMANTIC AUTHORITY:
NO

SERVER-SIDE CURSOR REVALIDATION:
REQUIRED

PINNING:
one evaluated_at
one overlay mode
one Current cycle when trusted
per Load More chain

CURSOR EXPIRY:
AdminQueryCursorExpired
code=cursor_expired

INITIAL CURRENT FAILURE:
historical fail-open
presence unknown

TRUSTED CONTINUATION FAILURE:
no silent ordering change

ONE ADMIN SLOT:
YES

ONE QUERY DEADLINE:
YES

CURRENT POPULATION BOUND:
configured CurrentStateConfig.client_max_rows

DEFAULT CURRENT MAX ROWS:
10000
not a new architecture hard limit

PERFORMANCE:
UNPROVEN UNTIL CAPACITY GATE

CURRENT GUEST TRAFFIC:
OUT OF SCOPE

DEVICE DETAIL CURRENT:
UNCHANGED

FEATURE FLAG:
WEB_ADMIN_DEVICE_LIST_CONTEXT_ENABLED=false

AUTO REFRESH:
NO

NEW OMADA:
NO

NEW COLLECTOR:
NO

NEW DB:
NO

NEW SCHEMA:
NO

NEW CURRENT INDEX:
NO by default

WRITES:
NO

CODER:
HOLD

IMPLEMENTATION AUTHORIZATION:
NOT GRANTED

GITHUB WRITE:
HOLD

PRODUCTION:
UNTOUCHED

TASK-WEB-DEVICE-UI-01:
FROZEN
```

---

# 77. Workflow after this FINAL

This FINAL does not authorize implementation.

Next allowed workflow:

```text
Tech Lead final architecture acceptance
        ↓
fresh repository rebind
        ↓
Tech Lead exact Coder technical TASK
        ↓
separate Owner implementation authorization
        ↓
Coder pre-code PLAN
        ↓
PLAN review
        ↓
only then implementation
```
