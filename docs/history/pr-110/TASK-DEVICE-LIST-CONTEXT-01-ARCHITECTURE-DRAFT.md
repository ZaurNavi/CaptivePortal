# TASK-DEVICE-LIST-CONTEXT-01 — Devices List Context — ARCHITECTURE DRAFT

**Project:** CaptivPortal  
**Area:** Admin Console → Devices list  
**Dependency:** `TASK-WEB-DEVICE-UI-01`  
**Related accepted production task:** `TASK-DEVICE-CARD-01 — Current Device Context`  
**Type:** read-only Admin projection/composition architecture  
**Status:** `DRAFT — FOR TECH LEAD REVIEW`  
**Implementation authorization:** `NOT GRANTED`  
**Coder:** `HOLD`  
**GitHub / branch / commit / push / PR:** `HOLD`  
**Production:** `UNTOUCHED`  
**Prepared:** 2026-09-09

---

# 0. Executive architecture decision

`TASK-DEVICE-LIST-CONTEXT-01` extends the **existing historical Devices list** with two missing list-level facts:

```text
hostname
current_presence
```

and changes the context-enabled list ordering to:

```text
CURRENT ONLINE DEVICES
        ↓
remaining historical Devices
```

without changing Device membership semantics.

Canonical product model:

```text
historical Site Device inventory
        +
trusted persisted Current State overlay
        ↓
bounded Site-safe server-side composition
        ↓
canonical MAC match
        ↓
current_presence
        ↓
Online-first ordering BEFORE pagination
        ↓
existing bounded cursor / Load More model
        ↓
Admin Devices list DTO
```

Permanent:

```text
Devices
=
historical known Device inventory

Current State
=
current overlay

Current State
DOES NOT create Device membership in this TASK
```

A client visible in Current State but absent from the historical Device inventory does **not** become a new Devices-list row in `TASK-DEVICE-LIST-CONTEXT-01`.

---

# 1. Repository / KB / application baseline

## 1.1 Current repository baseline

Architecture draft is rebound to:

```text
CURRENT REPOSITORY MAIN =
fd12f16c1f64900ce4096b3509a3b52d6bfe1b46

TREE =
edb5bab5479a4417d545429eeacf2b29a640e441
```

Current main is:

```text
PR #109
Docs: reconcile DEVICE-CARD-01 production closure
```

## 1.2 Docs-only reconciliation

PR #109 is documentation-only.

It did not change:

```text
application code
runtime config
DB/schema
Current State
Device Current Context
Traffic
production application behavior
```

Therefore:

```text
current repository main
!=
current deployed application commit
```

is expected and not an architecture contradiction.

## 1.3 Current deployed application baseline

Production application state:

```text
SHA =
7df71a8e807efd74b123117e78cb8d992c190fa1

CODE TREE =
8f1342f0a0f1e8242642161e02b2f3276e6ddf51
```

## 1.4 Canonical KB authority

Post-PR-109 Knowledge Base is the documentation authority for this draft.

Especially authoritative:

```text
docs/tasks/TASK-DEVICE-CARD-01-FINAL.md
```

Canonical KB now states:

```text
TASK-DEVICE-CARD-01=COMPLETE
DEVICE_CURRENT_CONTEXT=PRODUCTION ACTIVE
WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED=true
```

Repository safe default remains:

```text
WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED=false
```

---

# 2. Problem statement

`TASK-WEB-DEVICE-UI-01` is frozen because the current Devices list payload cannot support two required UI behaviors correctly:

```text
1. hostname in compact Device row
2. reliable Current Presence + global Online-first ordering
```

Current Web Designer patch remains preserved.

Status:

```text
TASK-WEB-DEVICE-UI-01
=
FROZEN / HOLD

MERGED=NO
DEPLOYED=NO
```

This architecture task exists to provide a stable backend/list contract so presentation work can resume later.

---

# 3. Exact scope of TASK-DEVICE-LIST-CONTEXT-01

In scope:

```text
historical Devices list enrichment

hostname
current_presence

Current State evidence metadata sufficient to interpret presence

global Online-first ordering

stable cursor semantics under changing Current State

Current State fail-open behavior relative to historical Devices list

bounded Site-scoped read composition

feature rollout for the enriched list contract
```

Out of scope:

```text
Device Detail redesign
Device Detail Current semantic changes

Current Guest Traffic in Devices list
Traffic rates in Devices list

Visit Detail
Visit Traffic
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
new Registry persistence
new Current State collection

frontend auto-refresh / polling

Web Designer visual implementation
```

---

# 4. Existing Devices list remains the inventory owner

Current production endpoint:

```text
GET /admin/api/v1/sites/<site_id>/devices
```

Current capability:

```text
admin.read.devices
```

Current query surface:

```text
limit
cursor
mac
```

Current list is a Site-scoped historical Device inventory based on the accepted Registry / Visit boundary.

Permanent:

```text
Device list membership
!=
Current State membership
```

Current State may decorate an existing Device row.

It may not create a Device row in this TASK.

---

# 5. Existing Device membership contract remains unchanged

Canonical Site membership remains:

```text
Site Snapshot evidence
OR
Site Visit evidence
```

Current State is NOT added as a third Device membership source.

Forbidden membership authority:

```text
Registry global last_site_id
Registry global last_*

Current State row alone

Latest Observation alone
```

A Device may have evidence in multiple Sites.

Every list read remains bound to:

```text
requested exact site_id
```

No cross-Site fallback.

---

# 6. Semantic ownership

## Historical Device identity / Site membership / historical ordering facts

Owner:

```text
existing Admin Device read boundary
AdminDeviceReadGateway
+
Registry / Visit persisted evidence
```

## List hostname

Owner:

```text
latest Site Snapshot projection
through the existing Admin Device read boundary
```

No new source.

## Current Presence

Owner:

```text
CurrentStateReadService
```

and exactly the accepted semantics established by `TASK-DEVICE-CARD-01`.

## Ordering / pagination composition

Owner:

```text
Admin Devices list projection boundary
```

This boundary composes semantic owners.

It does NOT become a new domain semantic owner.

---

# 7. Hostname contract — architectural decision

For v1 the canonical list field is:

```text
hostname: string | null
```

Source:

```text
latest Site-local Device Snapshot
→ snapshot.hostname
```

The existing Device gateway already reads:

```text
name
hostname
system_name
```

from the latest Site Snapshot.

`TASK-DEVICE-LIST-CONTEXT-01` only promotes:

```text
hostname
```

into the list DTO.

## No fallback chain in v1

Do NOT silently define:

```text
hostname
→ else name
→ else system_name
```

as one field.

Reason:

```text
hostname
name
system_name
```

are distinct persisted controller facts.

If UI labels a value as `Hostname`, the backend must not substitute a different semantic field.

Therefore:

```text
hostname missing
→ hostname=null
→ UI may show —
```

`name` and `system_name` remain available in their existing historical Snapshot context but are not list fallbacks in this TASK.

A future explicit `display_name` product may define a fallback strategy separately if required.

---

# 8. Device Type remains separate

Existing:

```text
device_type
```

remains a separate list field.

Do not derive Type from hostname/name/system_name.

The intended presentation contract becomes conceptually:

```text
MAC
Hostname
Type
...
```

with:

```text
Hostname=null
```

allowed.

---

# 9. Current Presence must reuse DEVICE-CARD-01 semantics

The list MUST NOT invent a second Current Presence definition.

Accepted production semantics remain:

```text
fresh + complete + present
→ online

fresh + complete + absent
→ offline

stale
→ unknown

unavailable
→ unknown

invalid timestamp
→ unknown

untrusted scope
→ unknown
```

Permanent:

```text
stale != offline
unavailable != offline
invalid timestamp != offline
```

The meaning of list `offline` is the same scope-aware meaning as Device Current:

```text
not present in the fresh complete managed Current State client scope
```

It does not prove the physical Device is powered off or absent from every other network.

---

# 10. Forbidden Current Presence heuristics

Never derive list Current Presence from:

```text
site_last_seen_at
Latest Site Snapshot
Latest Client Observation
Visit status
historical active
historical authStatus
IP
SSID
AP
Registry last_*
browser inference
```

Historical evidence remains historical.

---

# 11. Cross-surface Current Presence invariant

For the same:

```text
site_id
canonical MAC
evaluated_at_utc
accepted Current State cycle
```

the following MUST agree:

```text
Devices list current_presence
=
Device Detail Current presence
```

No list-specific interpretation is allowed.

`TASK-DEVICE-LIST-CONTEXT-01` must not weaken or redefine:

```text
GET /admin/api/v1/sites/<site_id>/devices/<device_id>/current
```

or:

```text
admin.device.current.v1
```

---

# 12. Current State list-overlay boundary

The exact single-Device method:

```text
CurrentStateReadService.get_current_client(...)
```

is correct for Device Detail but MUST NOT be called once per list row.

Forbidden:

```text
for each Device row:
    get_current_client(...)
```

and forbidden HTTP equivalent:

```text
100 Device rows
→ 100 /devices/<id>/current requests
```

A list-specific population/context read boundary is required.

---

# 13. Required Current State overlay descriptor

Architectural requirement:

`CurrentStateReadService` must remain responsible for selecting and validating the Current State evidence used by the list.

A narrow list-overlay context contract is allowed and expected, conceptually:

```text
CurrentClientInventoryContext
```

It must determine:

```text
one evaluated_at_utc
one accepted client snapshot
Site
canonical client_ssid_allowlist scope
freshness
complete/trusted state
current cycle identity when usable
```

It MUST reuse existing:

```text
complete-success cycle selection
scope canonicalization
scope trust
freshness policy
Site validation
timestamp validation
```

No new presence semantics.

Exact implementation name is for Tech Lead reconciliation.

---

# 14. Trusted overlay states

## Trusted current overlay

Usable for online/offline only if:

```text
snapshot exists
complete=true
freshness_status=fresh
scope_type=client_ssid_allowlist
scope Site matches requested Site
scope is trusted/compatible
```

Then:

```text
matching current MAC
→ online

missing current MAC
→ offline
```

## Semantic Current State unknown

If successful Current State read yields:

```text
stale
unavailable
no complete trusted snapshot
invalid timestamp
untrusted scope
```

then:

```text
all historical Device rows
→ current_presence=unknown
```

No Current overlay is used for ordering.

## Current State execution failure

If the Current State source cannot be safely executed/read:

```text
historical Devices list should fail open where overall Admin budget still permits
```

Result:

```text
HTTP 200
historical Devices available
current_presence=unknown
Current overlay source marked unavailable
```

Do not fabricate offline.

---

# 15. Important fail-open boundary

Permanent product invariant:

```text
Current overlay unavailable
!=
Historical Devices inventory unavailable
```

Initial list request should prefer:

```text
Current State source unavailable
        ↓
historical list still 200
        ↓
all rows current_presence=unknown
```

The global Admin QueryDeadline remains authoritative.

If the overall Admin request deadline is exhausted and the historical query cannot safely complete, normal Admin deadline failure may still apply.

This TASK does not increase the global deadline.

---

# 16. No Current-only Device insertion

A Current State client with no accepted historical Device membership:

```text
Current MAC exists
+
no Site Snapshot/Visit Device identity
```

does NOT become a Devices-list item in v1.

Reason:

```text
Devices
=
historical Device inventory + Current overlay

not
=
Current State inventory union historical inventory
```

This keeps:

```text
Device identity
Site membership
Device Card routing
```

unchanged.

---

# 17. Pre-pagination composition is mandatory

True Online-first must occur before:

```text
LIMIT
cursor
page construction
```

Forbidden:

```text
fetch historical page
→ decorate page
→ browser sort current page
```

because Online Devices may exist outside the loaded historical page.

Permanent:

```text
Online-first
=
server-side global ordering over the logical result set
```

not page-local presentation sorting.

---

# 18. Recommended physical composition boundary

Preferred architecture:

```text
CurrentStateReadService
→ validates/selects one overlay context / pinned cycle

existing Admin Device read/composition gateway
→ performs one set-based historical + pinned-current membership composition

AdminQueryService
→ serializes/list-paginates one result
```

The Admin composition gateway MAY consume persisted Current State rows for the **already selected pinned cycle** in a read-only set-based join.

It MUST NOT independently decide:

```text
which Current State cycle is latest
whether a snapshot is fresh
whether scope is trusted
whether stale means offline
```

Those semantics remain owned by:

```text
CurrentStateReadService
```

Exact SQL/attachment/helper structure is Tech Lead implementation work.

---

# 19. No full uncontrolled materialization

The preferred list architecture does NOT require:

```text
load all historical Devices into Python
load Current State page-by-page into Python
build N Device current requests
```

Composition must be:

```text
set-based
bounded
pre-pagination
```

The current client table may only be used under:

```text
one pinned accepted cycle
requested Site
```

---

# 20. Online-first ordering — frozen product semantics

When trusted fresh complete Current State is available:

```text
bucket 1:
current_presence=online

bucket 2:
all remaining historical Devices
```

Within each bucket preserve existing historical ordering:

```text
site_last_seen_at DESC
device_id DESC
```

Canonical ordering key:

```text
online_rank ASC
site_last_seen_at DESC
device_id DESC
```

where conceptually:

```text
online → online_rank=0
offline/unknown → online_rank=1
```

The UI does not perform a second sort.

---

# 21. Unknown-overlay ordering

If Current State cannot prove current presence:

```text
all current_presence=unknown
```

and ordering becomes exactly the existing historical order:

```text
site_last_seen_at DESC
device_id DESC
```

Do NOT guess online positions.

---

# 22. Existing MAC filter

Current list query supports:

```text
mac
```

This remains an optional search/filter input.

It is NOT semantic Device identity authority.

Canonical Device identity still comes from the historical Device projection.

With an exact MAC filter:

```text
matching historical Device row
→ receive hostname + current_presence
```

under the same rules.

---

# 23. Cursor must bind the Current overlay

Current State may change while the operator presses `Load More`.

Therefore a context-enabled list cursor MUST pin the overlay used by the first page.

For one pagination chain, the cursor must bind at least:

```text
Site
filters
ordering contract/version

evaluated_at_utc

Current overlay mode:
trusted pinned cycle
OR
unknown overlay

when trusted:
current_cycle_id
internal source-scope identity

last ordering key:
online rank
site_last_seen_at
device_id
```

The cursor remains opaque to the browser.

`source_scope_hash` may be carried internally in the cursor but is not a normal UI/DTO field.

---

# 24. Pagination consistency model

## First page with trusted Current State

```text
evaluated_at = T
current cycle = A
```

All subsequent pages in that cursor chain use:

```text
T
+
cycle A
```

even if collector publishes cycle B.

Forbidden:

```text
page 1 uses cycle A
page 2 silently uses cycle B
```

## First page with unknown Current overlay

If the first page establishes:

```text
Current overlay = unknown
```

the entire cursor chain remains:

```text
unknown overlay
+
historical ordering
```

even if Current State recovers before `Load More`.

A new top-level Refresh/new page-1 request may establish a new overlay.

---

# 25. Pinned cycle expiry / incompatibility

If a cursor is bound to a trusted Current cycle and that pinned evidence can no longer be safely used because of:

```text
retention expiry
scope incompatibility/change
pinned-cycle integrity failure
```

do NOT silently switch to a newer Current cycle.

Required behavior:

```text
cursor_expired / restart pagination
```

using the existing safe Admin cursor failure pattern.

---

# 26. Temporary source failure during trusted continuation

A continuation page that was already pinned to trusted online-first ordering MUST NOT silently degrade to unknown/historical ordering, because that would invalidate the cursor order and can create skips/duplicates.

Therefore:

```text
trusted cursor chain
+
temporary inability to read pinned Current membership
→ controlled continuation failure
```

not:

```text
silently continue with historical-only order
```

A new page-1/Refresh request may fail open to unknown overlay.

This preserves both:

```text
fail-open product behavior
and
pagination correctness
```

without mixing two orderings in one cursor chain.

---

# 27. Historical consistency scope

This TASK adds consistency for the **Current overlay**.

It does NOT redesign the existing historical Registry/Visit list into a transactional historical snapshot.

The existing historical keyset behavior remains the baseline.

Permanent new guarantee:

```text
Current State changes between Load More
MUST NOT reorder one existing cursor chain
```

No broader historical snapshot-isolation project is introduced here.

---

# 28. Device list DTO — proposed v1 extension

When list-context feature is enabled, keep all existing item fields and add only:

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

No current IP/AP/RSSI/Traffic fields are added to the list in this TASK.

---

# 29. Current overlay metadata — proposed root contract

To keep `current_presence` semantically interpretable, the list result should expose one page/root Current overlay evidence object.

Conceptually:

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

Page envelope remains conceptually:

```text
limit
next_cursor
```

---

# 30. Overlay execution status

List-specific execution-level machine field:

```text
source_execution_status =
available | unavailable
```

Meaning:

## available

The Current State read executed safely.

Its semantic evidence may still be:

```text
fresh
stale
unavailable
```

## unavailable

The Current State source/read could not execute safely for the initial list projection.

Then:

```text
snapshot=null
all current_presence=unknown
historical list may still succeed
```

Permanent:

```text
source execution unavailable
!=
semantic freshness unavailable
```

---

# 31. Public Current scope contract

Reuse canonical Current State machine value:

```text
scope_type = client_ssid_allowlist
```

Safe public scope:

```json
{
  "scope_type": "client_ssid_allowlist",
  "site_id": "<site_id>",
  "ssids": ["<configured exact SSID>"]
}
```

Do not expose:

```text
source_scope_hash
raw scope JSON
storage internals
```

unless separately required for diagnostics.

---

# 32. Public cycle identity

Normal Devices-list UI does not require:

```text
current_cycle_id
source_scope_hash
```

for presentation.

These identities are required internally for cursor/pinning integrity.

They MAY remain cursor/internal details.

This draft does not require exposing them in the normal list DTO.

---

# 33. Current Guest Traffic is explicitly not part of this TASK

Although `TASK-DEVICE-CARD-01` includes Current Guest Traffic, the Devices-list dependency does not require rates.

Do NOT add:

```text
download_mbps
upload_mbps
total_mbps
CurrentGuestTrafficReadService calls
```

to `TASK-DEVICE-LIST-CONTEXT-01`.

Existing Traffic semantics remain untouched:

```text
0 Mbps = valid numeric evidence
0 != null
```

but they are not consumed by the list.

---

# 34. Device Current API compatibility

Existing accepted endpoint remains unchanged:

```text
GET /admin/api/v1/sites/<site_id>/devices/<device_id>/current
```

Capability remains:

```text
admin.read.device
```

DTO remains:

```text
admin.device.current.v1
```

The list task MUST NOT:

```text
call this endpoint once per row
wrap it
modify its semantics
weaken its trust rules
```

List Current Presence is a separate bulk projection of the same Current State semantics.

---

# 35. List capability remains bulk capability

Existing Devices list capability remains:

```text
admin.read.devices
```

Do not replace it with:

```text
admin.read.device
```

because this is a bulk list read.

Device Detail and Device Current continue to use their existing entity capability independently.

---

# 36. Security / Site isolation

Required ordering remains:

```text
authenticated Admin session
        ↓
canonical Site resolution
        ↓
Site allowlist / Admin policy
        ↓
admin.read.devices
        ↓
historical Site Device inventory
        +
Current State exact same Site
        ↓
server-side canonical MAC match
        ↓
safe list projection
```

Forbidden:

```text
Current State from another Site
Registry global cross-Site current context
client-provided MAC as identity authority
cross-Site fallback
```

The optional existing `mac` parameter is only a filter.

---

# 37. One Admin request budget

One Devices list request must remain inside one existing:

```text
AdminQueryExecutionControls
```

Therefore:

```text
one Admin concurrency slot
one QueryDeadline
```

Expected constant composition:

```text
one Current overlay context read
+
one set-based composed Device page read
```

Exact physical query count is Tech Lead territory, but it must remain constant with page size and must not become per-row.

Do not increase:

```text
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS
WEB_ADMIN_MAX_CONCURRENT_QUERIES
```

for this TASK.

---

# 38. Page-size / capacity boundary

Existing repository contract:

```text
WEB_ADMIN_DEVICE_PAGE_SIZE default = 100
```

Existing gateway hard bound:

```text
max page size = 500
```

`TASK-DEVICE-LIST-CONTEXT-01` does not increase either.

Current State existing client collection bound remains:

```text
CURRENT_STATE_CLIENT_MAX_ROWS
repository default = 10000
```

No new larger Current population limit is introduced.

Representative acceptance must include Current populations up to the accepted configured bound.

---

# 39. Boundedness requirements

Required:

```text
NO N+1
NO per-row Current State call
NO per-row DB connection
NO pagination through Current State to find matches
NO browser joins
NO full uncontrolled Registry materialization
NO unbounded Current State scan
NO query-time Omada
NO writes
```

Preferred:

```text
set-based historical/current composition
before LIMIT
```

If implementation requires materializing the complete historical inventory in Python to achieve Online-first:

```text
STOP
→ architecture correction
```

---

# 40. Query-plan / performance gate

No artificial latency target is fixed before measurement.

Tech Lead technical TASK must require representative capacity evidence.

Record at least:

```text
candidate SHA/tree

historical Device count
Snapshot count
Visit count
Current client count

page size

source call count
query count
rows transferred

query plan
duration p50/p95/max
response bytes

provider_calls
writes
```

Mandatory qualitative PASS:

```text
online-first is computed before pagination

source/query count is not N+1

runtime does not grow by Current/Device page scanning

no all-historical Python materialization

no Omada/provider call

no source writes

fits existing Admin QueryDeadline
```

---

# 41. Feature flag — recommended and accepted in DRAFT

Recommended rollout flag:

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

It does NOT require:

```text
WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED
WEB_ADMIN_TRAFFIC_ENABLED
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED
```

These are independent product consumers.

---

# 42. Feature OFF behavior

When:

```text
WEB_ADMIN_DEVICE_LIST_CONTEXT_ENABLED=false
```

preserve exact current production list behavior:

```text
existing historical ordering
existing cursor contract
existing list DTO
no Current overlay read
no new list read workload
```

This enables dormant deployment.

---

# 43. Feature ON behavior

When enabled:

```text
same /devices endpoint
same existing filters
same capability

+
hostname
+
current_presence
+
current_state_overlay metadata
+
Online-first server ordering
+
context-aware cursor
```

No separate public Devices-list endpoint is introduced.

Reason:

```text
this is enrichment of the same Devices product,
not a second inventory product
```

---

# 44. No user-selectable sort in v1

When list context is enabled, Online-first is the canonical product order.

Do not add in this TASK:

```text
sort=online_first
sort=historical
```

as new API choices.

Feature OFF preserves old order.

Feature ON uses Online-first.

A future user-selectable sorting product can be designed separately.

---

# 45. Failure semantics summary

## Trusted fresh complete Current State

```text
online / offline
Online-first active
```

## Current State semantic stale/unavailable/untrusted

```text
HTTP 200
all current_presence=unknown
historical ordering
snapshot evidence explains why
```

## Initial Current State execution failure

```text
prefer HTTP 200
all current_presence=unknown
historical ordering
source_execution_status=unavailable
```

subject to overall Admin deadline availability.

## Trusted pinned continuation cannot read pinned evidence

```text
do not change ordering mode silently
controlled cursor/source failure
```

Refresh/new page 1 starts a new logical list.

---

# 46. Frontend lifecycle

This backend task does NOT introduce frontend polling.

Required list data behavior:

```text
initial Devices page load
manual existing Refresh
Load More
```

No hidden Current timer.

No per-row Current request.

`TASK-WEB-DEVICE-UI-01` remains frozen until this data contract is implemented/accepted.

---

# 47. Web Designer contract after backend acceptance

After `TASK-DEVICE-LIST-CONTEXT-01` passes, Web Designer may rely on:

```text
hostname
current_presence
Online-first server order
stable Load More cursor
```

Presentation may then implement:

```text
MAC + Hostname
separate Type
green Online indicator
compact Online-first list
```

Important UI rule:

```text
green dot
=
current_presence=online
```

Absence of a green dot MUST NOT itself be presented as proof of Offline.

The DTO may contain `offline`, but presentation can remain neutral unless the design explicitly labels that state with its managed-scope meaning.

---

# 48. Expected repository areas to change

Architecture-level expected areas:

```text
app/admin_web/device_gateway.py
app/admin_web/query_service.py
app/admin_web/runtime.py

app/current_state/read_service.py

app/admin_web/config.py
app/config.py
app/settings.py
.env.example

tests/admin_web/**
tests/current_state/**
```

Likely safe projection/serialization addition:

```text
app/admin_web/device_list_context_serialization.py
```

Exact module naming is for Tech Lead review.

`app/admin_web/routes.py` may require only minimal feature/query contract reconciliation if current route structure cannot remain unchanged.

---

# 49. Areas not expected to change

Do NOT change by default:

```text
Device Current endpoint/DTO semantics

Current State schema
Current State collector
Current State worker cadence

Visitor Registry writer/schema
Visit Lifecycle
Observation acquisition/schema

CurrentGuestTrafficReadService formulas
Traffic products

OmadaProvider
Auth/CAPPORT
Pending Session Cleaner

requirements

Grafana
Loki
Alloy
systemd
Nginx
```

No Web Designer visual rewrite belongs to this backend architecture task.

---

# 50. Explicit forbidden approaches

Forbidden:

```text
N /devices/<id>/current requests for N list rows

N CurrentStateReadService.get_current_client() calls

page-local browser sorting

historical last_seen heuristic for Online

latest Snapshot active → Online

Latest Observation → Online/Offline

Visit open → Online

Current State stale → Offline

Current State unavailable → Offline

Current-only client → silently create historical Device row

Current State page scan until MAC

load all Devices into Python for sort

browser → Omada

Admin list → Omada

new DB/cache/table for Device list context

new collector/poller

write/control action

Traffic rate calculation in list
```

---

# 51. Acceptance invariants — hostname

Must prove:

```text
latest Site Snapshot hostname exists
→ list hostname exact same value

hostname missing
→ null

name exists but hostname null
→ hostname remains null

system_name exists but hostname null
→ hostname remains null

another Site has newer hostname
→ requested Site list does not leak it
```

---

# 52. Acceptance invariants — Current Presence

Must prove:

```text
fresh complete + known Device MAC present
→ online

fresh complete + known Device MAC absent
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
but Current State unknown
→ unknown

historical Snapshot says active
but fresh Current State proves absence
→ offline
```

---

# 53. Acceptance invariants — inventory boundary

Must prove:

```text
Current State MAC
+
no historical Device membership
→ NOT added to Devices list
```

and:

```text
historical Device
+
no Current row under fresh trusted snapshot
→ remains in list
→ current_presence=offline
```

---

# 54. Acceptance invariants — Online-first

With a historical inventory much larger than one page:

```text
online Device historically ranked at position 430
online Device historically ranked at position 1700
```

first context-enabled pages must still place all logically preceding online Devices before any non-online Device.

Permanent:

```text
no browser Load More is required
before an Online Device becomes eligible for Online-first position
```

---

# 55. Acceptance invariants — cursor race

Test:

```text
page 1:
evaluated_at=T
cycle=A

collector publishes cycle=B

Load More
```

Required:

```text
page 2 remains ordered against cycle A
```

No:

```text
duplicate due to A→B presence movement
skip due to A→B presence movement
silent switch to B
```

New Refresh may use B.

---

# 56. Acceptance invariants — Current overlay failure

Initial Current State failure:

```text
historical list available
→ HTTP 200 where deadline permits
→ current_presence=unknown
→ no false Offline
```

Current source later recovers:

```text
existing cursor chain remains in its pinned consistency mode
new Refresh may establish trusted overlay
```

---

# 57. Acceptance invariants — security

Must prove:

```text
unauthenticated → existing 401 behavior

invalid Site → existing safe behavior

forbidden Site → existing safe behavior

admin.read.devices required

Site A historical Device
+
same MAC Current in Site B
→ Site A does not inherit Site B Current presence

client `mac` query input
→ filter only
→ cannot select another Site identity
```

---

# 58. Acceptance invariants — backward compatibility

Feature OFF:

```text
existing list response/order/cursor regression PASS
```

Feature ON:

```text
existing fields preserved
hostname/current_presence added
Online-first intentional
existing mac filter preserved
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

# 59. Testing ownership

Preserve project model:

```text
CODER WRITES
OWNER + TECH LEAD TEST
```

Coder, after future authorization, owns:

```text
focused tests for changed/new code
syntax/compile checks
git diff --check
handoff
```

Owner + Tech Lead / Central Lab own:

```text
repository rebind
query-plan review
capacity test
cross-surface regression
controlled browser acceptance
official PASS/FAIL
```

No implementation is authorized by this DRAFT.

---

# 60. Mandatory Tech Lead review questions

Before this architecture becomes FINAL, Tech Lead must reconcile the current repository and answer:

1. Can the existing `AdminDeviceReadGateway` be safely extended into the set-based list composition boundary, or should a narrow sibling gateway be used?
2. What is the exact minimal Current State overlay-descriptor method name/model while preserving `CurrentStateReadService` semantic ownership?
3. What read-only path should the Admin list gateway use for the pinned `current_client_state` cycle without duplicating Current State freshness/scope logic?
4. What exact cursor version/shape best extends the existing cursor utilities while binding `evaluated_at`, overlay mode, pinned cycle and ordering key?
5. What exact safe error should represent an expired pinned list-context cursor using current Admin conventions?
6. Does the existing one-slot/one-deadline model need only composition reuse, with no global limit changes?
7. Does representative production-size query planning confirm set-based Online-first before LIMIT without full historical Python materialization?
8. Can runtime composition inject the Current State read/source path entirely inside `app/admin_web/runtime.py`, with no lifecycle-root change?
9. Which existing tests/benchmarks should be extended rather than duplicated?
10. Confirm that `hostname` raw-only, with no `name/system_name` fallback, matches the Owner-facing UI requirement.

Coder must not decide these architecture/repository reconciliation points independently.

---

# 61. Stop conditions for technical design

Tech Lead / later Coder must STOP and return evidence if the design requires:

```text
new Device membership semantics

Current-only Device insertion

historical → Current heuristic

Current State stale/unavailable → Offline

per-row current lookups

page-local Online sorting

full historical Python materialization

unbounded Current State population scan

new Current State schema/index by assumption

new DB/cache

new collector/poller

query-time Omada

new Traffic calculation

Device Current semantic change

Admin global deadline/concurrency increase

frontend polling

write/control functionality
```

Any of these requires architecture re-review.

---

# 62. Architecture verdict

```text
TASK-DEVICE-LIST-CONTEXT-01

ARCHITECTURE DIRECTION:
PROPOSED / READY FOR TECH LEAD REVIEW

PRODUCT:
existing Devices historical inventory
+
Current State overlay

HISTORICAL MEMBERSHIP OWNER:
existing Registry / Visit Device boundary

HOSTNAME OWNER:
latest Site Snapshot projection

HOSTNAME V1:
raw hostname only
no fallback

CURRENT PRESENCE OWNER:
CurrentStateReadService

PRESENCE:
online | offline | unknown

CURRENT-ONLY DEVICE INSERTION:
NO

ONLINE-FIRST:
server-side
before pagination

SECONDARY ORDER:
site_last_seen_at DESC
device_id DESC

CURRENT CONSISTENCY:
one evaluated_at
one pinned Current overlay per cursor chain

CURRENT CHANGES BETWEEN LOAD MORE:
do not change pinned chain

CURRENT SOURCE INITIAL FAILURE:
historical fail-open / presence unknown

N+1:
FORBIDDEN

BROWSER SORT:
FORBIDDEN

CURRENT STATE PAGE SCAN:
FORBIDDEN

HISTORICAL FULL MATERIALIZATION:
FORBIDDEN

COMPOSITION:
set-based, bounded, Site-scoped

LIST CAPABILITY:
admin.read.devices

DEVICE DETAIL CURRENT CONTRACT:
UNCHANGED

CURRENT GUEST TRAFFIC:
OUT OF SCOPE

FEATURE FLAG:
WEB_ADMIN_DEVICE_LIST_CONTEXT_ENABLED=false

AUTO REFRESH:
NO

NEW OMADA:
NO

NEW DB:
NO

NEW COLLECTOR:
NO

WRITES:
NO

TASK-WEB-DEVICE-UI-01:
FROZEN UNTIL DATA CONTRACT ACCEPTED

CODER:
HOLD

GITHUB:
HOLD

PRODUCTION:
UNTOUCHED
```

---

# 63. Next allowed workflow

```text
Architect DRAFT
        ↓
Tech Lead repository rebind / technical review
        ↓
architecture corrections if required
        ↓
FINAL architecture
        ↓
Tech Lead exact technical TASK
        ↓
separate Owner implementation authorization
        ↓
Coder PLAN
        ↓
only then implementation
```

This DRAFT does not authorize implementation.
