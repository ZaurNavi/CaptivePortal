# TASK-DTI-NI-03
## PROTOCOL INTELLIGENCE + DEVICE CARD P1
### ARCHITECTURE CONTRACT v1
### IMPLEMENTATION-READY / FOR TECH LEAD REVIEW

**Проект:** CaptivPortal  
**Роль:** Architect  
**Текущий re-pinned baseline:** `main@3467da8abd4ad4bb5b381a13e374e2e8faf4685e`  
**TREE:** `2e3cb2b345af370275cb9b8fe35729f6f5218d35`  
**Baseline movement:** `NO`  
**Parent stage:** `TASK-DTI-NI-02B = PRODUCTION ACCEPTED / CLOSED`  
**Статус:** `ARCHITECTURE ACCEPTED BY ARCHITECT / PENDING TECH LEAD REVIEW`  
**Implementation authorization:** `NO`  
**Coder authorization:** `NO`  
**Production change:** `NO`

---

# 0. BASELINE RE-PIN / CURRENT-STATE IMPACT

Перед подготовкой этого контракта текущий `origin/main` re-pinned.

Получено:

```text
origin/main HEAD =
3467da8abd4ad4bb5b381a13e374e2e8faf4685e

TREE =
2e3cb2b345af370275cb9b8fe35729f6f5218d35
```

Это тот же baseline, который указан во входном запросе:

```text
Merge PR #195
DTI-NI-02B:
Device-relative network metadata projection
```

Следовательно:

```text
BASELINE_MOVED = NO
MATERIAL_DIFFERENCES = NONE
```

Ни один закрытый контракт NI-01 / NI-02A / NI-02B не требует reopening.

Current source подтверждает наличие:

```text
DeviceNetworkMetadataReadService

DeviceNetworkMetadataEdgeV1

projection_runtime_state

projection_site_mac_bindings

projection_registry_identities

AdminQueryService

existing Device Detail page

existing:
GET /admin/api/v1/sites/<site_id>/devices/<device_id>/current

existing Site capability:
admin.read.device
```

Current NI-02B read path уже использует:

```text
read-only SQLite
query_only=ON
foreign_keys=ON
busy_timeout=500ms
```

и materialized Device-relative projection остаётся единственной
Network Intelligence identity/projection authority для NI-03.

---

# 1. ARCHITECTURE RESULT

NI-03 V1 выбирает:

```text
BOUNDED READ-TIME AGGREGATION
OVER THE EXISTING NI-02B MATERIALIZED PROJECTION
```

NI-03 V1 НЕ создаёт:

```text
новую SQLite DB
новый writer
новый background service
новый checkpoint
новый durable summary history
```

Canonical chain:

```text
Device Detail / Admin API
        ↓
AdminQueryService
        ↓
DeviceProtocolIntelligenceReadService
        ↓
bounded protocol-evidence read boundary
        ↓
existing NI-02B projection DB
        ↓
DeviceProtocolSummaryV1
        ↓
Device Card
```

Forbidden chain remains:

```text
Browser
→ NI-01
→ NI-02A
→ Registry
```

and:

```text
NI-03
→ query-time IP→MAC attribution
```

---

# 2. WHY NO NEW MATERIALIZED SUMMARY STORE

A separate `DeviceProtocolSummary` DB is explicitly rejected in NI-03 V1.

Reasons:

```text
NI-02B already materializes the expensive temporal identity projection;

only three protocol families are admitted;

summary window is fixed and bounded;

projection retention is already bounded to 14 days;

current production edge cardinality is compatible with
bounded per-Device read-time aggregation;

a second store would create:
writer lifecycle,
checkpoint,
rebuild,
retention,
capacity,
failure
and consistency ownership
without adding new authority.
```

Permanent NI-03 V1 rule:

```text
DeviceProtocolSummaryV1 is EPHEMERAL READ MODEL
```

It is never persisted server-side.

---

# 3. INHERITED FROZEN CONTRACTS

NI-03 inherits unchanged:

```text
NI-01:
DNS / TLS / QUIC admitted network metadata

NI-02A:
Site + IPv4 + event_at
→ Site + MAC
via trusted_dhcp_v4 authority

NI-02B:
DeviceNetworkMetadataEdgeV1
materialized Site+MAC identity
late existing Registry device_id binding
0/1/2 edge semantics
Site scope
14-day sensitive edge retention
failure isolation
```

NI-03 MUST NOT redefine:

```text
temporal attribution
DHCP authority
MAC identity
device_id generation
Registry binding
peer_scope
direction
edge identity
edge retention
```

---

# 4. GOAL

NI-03 P1 answers only:

```text
Which admitted protocol families
have recently been observed
for this exact Site + Device?
```

and:

```text
What is the most recent admitted protocol observation?
```

with explicit:

```text
fresh / recent / stale / unavailable

source coverage

attribution coverage

projection availability
```

This is the first visible Network Intelligence milestone.

---

# 5. NON-GOALS

NI-03 P1 MUST NOT implement:

```text
Dominant Protocol

protocol percentages

protocol traffic totals

protocol byte totals

protocol packet totals

protocol popularity

service recognition

commercial product recognition

provider recognition

organization recognition

ASN recognition

behavioral profiling

transport health

remote endpoint history UI

DNS-name UI

SNI UI

Device protocol history browser

cross-Site aggregation
```

No NI-04 / NI-05 / NI-06 scope is admitted.

---

# 6. EXACT PRODUCT PROTOCOL VOCABULARY

NI-03 V1 Product Protocol is exactly:

```text
dns
tls
quic
```

Authority:

```text
DeviceNetworkMetadataEdgeV1.source_event_family
```

Exact display labels:

```text
dns  → DNS
tls  → TLS
quic → QUIC
```

Canonical protocol-order rank:

```text
dns  = 0
tls  = 1
quic = 2
```

This rank is only a deterministic tie-break.

It is NOT a dominance ranking.

---

# 7. TRANSPORT PROTOCOL IS NOT PRODUCT PROTOCOL

NI-02B:

```text
transport_protocol =
TCP | UDP | null
```

is explicitly NOT part of NI-03 Product Protocol vocabulary.

Therefore NI-03 Device Card MUST NOT display:

```text
TCP
UDP
```

as Recent Protocols.

Transport is not silently promoted into application/protocol family.

---

# 8. FUTURE FLOW / NEW PROTOCOL FAMILIES

Any future admitted:

```text
flow application protocol
HTTP family
other application protocol family
```

does NOT automatically enter NI-03 V1.

Unknown `source_event_family` under V1 is:

```text
integrity incompatibility
```

not:

```text
Other
Unknown protocol
```

Adding another Product Protocol requires:

```text
new admitted protocol vocabulary version
+
API/DTO compatibility decision
```

NI-03 V1 remains closed to:

```text
dns
tls
quic
```

---

# 9. SERVICE / COMPANY NAMES ARE FORBIDDEN

NI-03 MUST NOT infer:

```text
YouTube
Google
WhatsApp
Microsoft
TikTok
Telegram
Netflix
Meta
Cloudflare
or any other commercial/service/provider identity
```

from:

```text
DNS
SNI
IP
port
ALPN
peer endpoint
```

Exact prohibition:

```text
DNS name → service identity = NO

SNI → service identity = NO

IP → service/company identity = NO

ASN/org lookup = NO

service category inference = NO
```

Those belong to NI-04/NI-05.

---

# 10. SUMMARY TIME MODEL

NI-03 V1 uses exactly two code-owned windows.

## Summary evidence window

```text
86400 seconds
24 hours
```

## Recent Protocols window

```text
3600 seconds
60 minutes
```

These are NOT operator-configurable in NI-03 V1.

---

# 11. WINDOW BOUNDARIES

For one evaluation time:

```text
evaluated_at
```

define:

```text
summary_from =
evaluated_at - 24h

recent_from =
evaluated_at - 60m
```

Exact interval semantics:

```text
Summary evidence:
[summary_from, evaluated_at)

Recent Protocols:
[recent_from, evaluated_at)
```

Thus:

```text
event exactly summary_from
→ included

event exactly recent_from
→ Recent

event exactly evaluated_at
→ invalid/non-past evidence for this evaluation
```

No browser-provided `from` or `to`.

Server owns evaluation time.

---

# 12. WHY 24 HOURS

24h is frozen because it is:

```text
bounded enough for frequent Device Card reads;

well inside NI-02B 14-day sensitive retention;

large enough to preserve useful Last Protocol Observation;

small enough to avoid turning NI-03 into behavioral history.
```

NI-03 V1 does not expose the full 14-day edge history.

---

# 13. DEVICE FIRST APPEARS INSIDE WINDOW

If a Device first gains retained edge evidence at time:

```text
T > summary_from
```

NI-03:

```text
shows only the evidence that exists
```

and MUST NOT infer anything about:

```text
summary_from → T
```

No:

```text
"Device was inactive before T"
```

claim is allowed.

---

# 14. HISTORICAL COMPLETENESS CLAIM

NI-03 V1 explicitly does NOT claim:

```text
complete observation coverage for every second of the 24h window
```

The public summary contains:

```text
historical_window_completeness_claimed = false
```

This is permanent for V1.

Therefore missing protocol evidence is never interpreted as total network inactivity.

---

# 15. INTERNAL PROJECTION READ EXTENSION

NI-03 uses the existing NI-02B read owner:

```text
DeviceNetworkMetadataReadService
```

NI-03 MUST NOT open projection SQLite from:

```text
Flask route
template
JavaScript
Admin serializer
```

A bounded NI-02B-owned method is added:

```text
read_protocol_evidence_v1(
    site_id,
    device_id,
    client_mac,
    from_utc,
    to_utc,
    *,
    max_rows
)
```

No NI-02B schema change.

No NI-02B writer change.

---

# 16. PURPOSE OF `read_protocol_evidence_v1`

This method returns only facts required by NI-03:

```text
projection binding state

projection runtime state

last projection commit timestamp

protocol edge facts:
    event_at
    source_event_family
    edge_id
```

It MUST NOT return to NI-03:

```text
device_ip
peer_ip
ports
DNS names
SNI
capture raw values
Registry raw values
```

---

# 17. ProtocolEdgeFactV1

Exact internal immutable DTO:

```text
ProtocolEdgeFactV1

event_at: canonical UTC timestamp

protocol_id:
    dns
    tls
    quic

edge_id:
    canonical NI-02B edge_id
```

`edge_id` is internal-only tie-break provenance.

It is never emitted to the browser.

---

# 18. ProjectionProtocolEvidenceV1

Exact internal immutable DTO:

```text
ProjectionProtocolEvidenceV1

site_id

device_id

identity_binding_state:
    authoritative
    not_yet_registry_resolved
    registry_unavailable
    absent

projection_runtime_state:
    initializing
    usable
    degraded
    source_unavailable
    attribution_unavailable
    registry_degraded
    capacity_waiting_reader
    capacity_halted
    blocked_conflict
    stopping

last_projection_commit_at: timestamp | null

facts:
    tuple[ProtocolEdgeFactV1, ...]

row_limit_exceeded:
    false
```

If row limit would be exceeded:

```text
no partial DTO is returned
→ bounded read error
```

---

# 19. EXACT DEVICE IDENTITY CHECK

AdminQueryService first resolves the existing Device through the current:

```text
AdminDeviceReadGateway
```

for exact:

```text
site_id + device_id
```

This produces the canonical Registry MAC already owned by the existing Device Card identity path.

NI-03 then passes:

```text
site_id
device_id
canonical_mac
```

to the NI-02B projection read boundary.

---

# 20. PROJECTION BINDING CHECK

Inside the same projection SQLite read snapshot:

```text
lookup projection_site_mac_bindings
by:
site_id + client_mac
```

Exact result:

```text
no row
→ absent

binding_state=not_yet_registry_resolved
→ not_yet_registry_resolved

binding_state=registry_unavailable
→ registry_unavailable

binding_state=authoritative
AND device_id == requested device_id
→ authoritative

binding_state=authoritative
AND device_id != requested device_id
→ integrity unavailable
```

No MAC/device_id reassignment is invented by NI-03.

---

# 21. PRE-REGISTRY EDGE VISIBILITY

NI-03 Device Card does NOT bypass NI-02B late binding.

Therefore while projection binding is:

```text
not_yet_registry_resolved
registry_unavailable
absent
```

Device Card does NOT query edges by MAC as a substitute for authoritative binding.

Public state becomes:

```text
identity_pending
```

No Registry write.

No query-time Registry binding.

---

# 22. LATE BINDING

When NI-02B later changes the exact Site+MAC binding to:

```text
authoritative
+
existing device_id
```

the next NI-03 read automatically sees all still-retained edges for:

```text
site_id + client_mac
```

inside the 24h summary window.

No summary row rewrite exists because summaries are not persisted.

No edge rewrite occurs.

---

# 23. EDGE READ FILTER

After authoritative binding is verified, read facts only for:

```text
site_id = exact requested Site

client_mac = exact authoritative MAC

event_at >= summary_from

event_at < evaluated_at
```

using the existing NI-02B index:

```text
(site_id, client_mac, event_at, edge_id)
```

No cross-Site query.

---

# 24. MAX ROW SCAN

NI-03 hard maximum:

```text
PROTOCOL_SUMMARY_MAX_EDGE_ROWS = 20000
```

The projection read boundary may materialize at most:

```text
20001
```

small protocol fact rows only to detect overflow.

If row 20001 exists:

```text
protocol evidence limit exceeded
→ no truncated/partial summary
→ Admin source_unavailable / HTTP 503
```

The service MUST NOT silently summarize only the newest 20,000 rows.

---

# 25. FUTURE TIMESTAMP INTEGRITY

For the exact authoritative Site+MAC, NI-03 must reject a source snapshot
that contains retained Device edge evidence with:

```text
event_at >= evaluated_at
```

for the current evaluation.

This is:

```text
projection evidence integrity unavailable
```

No future event is displayed.

No client clock is used to decide this.

---

# 26. DeviceProtocolIntelligenceReadService

New NI-03 semantic owner:

```text
DeviceProtocolIntelligenceReadService
```

Recommended module ownership:

```text
app/network_protocol_intelligence/
```

This service owns:

```text
protocol vocabulary

24h summary window

60m Recent window

aggregation

freshness

coverage mapping

DeviceProtocolSummaryV1
```

It does NOT own projection SQLite schema or Device attribution.

---

# 27. EXACT READ SERVICE METHOD

Canonical NI-03 semantic method:

```text
get_device_protocol_summary(
    site_id,
    device_id,
    client_mac,
    *,
    evaluated_at_utc,
    deadline
) -> DeviceProtocolSummaryV1
```

All arguments are server-side/internal.

No user-defined window.

---

# 28. DeviceProtocolSummaryV1 — EXACT PUBLIC DTO

```text
DeviceProtocolSummaryV1

schema_version:
    1

site_id:
    exact Site ID

device_id:
    exact canonical existing Device UUID

evaluated_at_utc:
    canonical UTC timestamp

window:
    from_utc
    to_utc
    duration_seconds = 86400
    recent_from_utc
    recent_duration_seconds = 3600

availability_state:
    usable
    degraded

evidence_state:
    present
    empty
    identity_pending

identity_binding_state:
    authoritative
    pending
    unavailable
    absent

recent_protocols:
    tuple[RecentProtocolV1, ...]

last_protocol_observation:
    LastProtocolObservationV1 | null

freshness_state:
    fresh
    recent
    stale
    unavailable

coverage:
    scope = current_pipeline

    source_state:
        usable
        degraded
        unavailable
        unknown

    attribution_state:
        usable
        degraded
        unavailable
        unknown

    projection_state:
        usable
        degraded

    historical_window_completeness_claimed:
        false
```

No other public fields are admitted in V1.

---

# 29. RecentProtocolV1

Exact DTO:

```text
RecentProtocolV1

protocol_id:
    dns | tls | quic

display_label:
    DNS | TLS | QUIC

last_observed_at:
    canonical UTC timestamp
```

No count.

No percentage.

No direction.

No peer scope.

---

# 30. LastProtocolObservationV1

Exact DTO:

```text
LastProtocolObservationV1

protocol_id:
    dns | tls | quic

display_label:
    DNS | TLS | QUIC

observed_at:
    canonical UTC timestamp
```

No endpoint.

No direction.

No transport.

No peer scope.

---

# 31. EVENT COUNT — EXCLUDED

`event_count` is intentionally NOT included in:

```text
DeviceProtocolSummaryV1
RecentProtocolV1
Device Card
Admin API
```

Reason:

```text
metadata event count is not traffic volume;

event count is affected by protocol emission behavior,
attribution gaps and observation semantics;

P1 must not imply popularity/dominance.
```

Internal row-count enforcement is not a product metric.

---

# 32. DIRECTION — EXCLUDED FROM P1

NI-02B direction:

```text
inbound
outbound
local
unknown
```

is NOT shown in NI-03 Device Card P1.

It is not included in `DeviceProtocolSummaryV1`.

Reason:

```text
P1 is protocol-family visibility only;

adding direction creates a second aggregation dimension
not required by the accepted milestone.
```

No traffic-volume meaning is inferred.

---

# 33. PEER SCOPE — EXCLUDED FROM P1

NI-02B:

```text
local
external
unknown
```

is NOT shown in NI-03 P1.

No:

```text
Internet
WAN
external service
```

presentation is introduced.

---

# 34. RECENT PROTOCOL AGGREGATION

For facts in:

```text
[recent_from, evaluated_at)
```

group by:

```text
protocol_id
```

and retain:

```text
max(event_at)
```

per protocol.

Exactly one RecentProtocolV1 item per protocol family.

Multiple DNS edges therefore produce:

```text
one DNS item
```

not multiple rows.

---

# 35. RECENT PROTOCOL ORDER

Sort:

```text
last_observed_at DESC
```

Tie:

```text
protocol canonical rank ASC

DNS
TLS
QUIC
```

No event count used in ordering.

---

# 36. LAST PROTOCOL OBSERVATION

From all facts in:

```text
[summary_from, evaluated_at)
```

choose the maximum by:

```text
event_at DESC

then protocol canonical rank ASC

then edge_id ASC
```

`edge_id` is a deterministic internal tie-break only.

It is not public.

---

# 37. EVIDENCE STATE

Exact rules:

```text
projection binding not authoritative
→ evidence_state=identity_pending

authoritative binding
AND at least one fact in 24h
→ evidence_state=present

authoritative binding
AND zero facts in 24h
→ evidence_state=empty
```

No fourth V1 evidence state.

---

# 38. PUBLIC IDENTITY BINDING MAPPING

Internal NI-02B mapping:

```text
authoritative
→ authoritative

not_yet_registry_resolved
→ pending

registry_unavailable
→ unavailable

no Site+MAC binding row
→ absent
```

These values describe only projection-to-Device binding.

They are NOT temporal IP attribution states.

---

# 39. COVERAGE MODEL — IMPORTANT BOUNDARY

NI-03 V1 coverage is:

```text
CURRENT PIPELINE COVERAGE STATE
```

It is NOT:

```text
percentage of network events attributed

percentage of 24h window observed

statistical confidence

per-Device attribution accuracy percentage
```

Therefore public:

```text
coverage.scope =
current_pipeline
```

and:

```text
historical_window_completeness_claimed=false
```

always.

---

# 40. SOURCE COVERAGE AUTHORITY

NI-03 does NOT query NI-01 directly.

Source coverage is derived only from the currently materialized NI-02B:

```text
projection_runtime_state.runtime_state
```

inside the same projection DB read snapshot.

Thus:

```text
no query-time NI-01 reconstruction

no source-health cross-DB join

no raw EVE read
```

---

# 41. ATTRIBUTION COVERAGE AUTHORITY

NI-03 does NOT query NI-02A directly.

Attribution coverage is derived only from NI-02B current runtime state.

Thus Device Card never executes:

```text
resolve_ipv4(...)
```

No query-time attribution.

---

# 42. ENDPOINT ATTRIBUTION OUTCOMES — P1 HANDLING

NI-02B internal outcomes:

```text
resolved
ambiguous
unattributed
unavailable
outside_historical_horizon
unsupported_address_family
pending retry
```

are handled as follows in NI-03 P1:

```text
resolved
→ may produce materialized Device edge
→ contributes protocol evidence

ambiguous
unattributed
outside_historical_horizon
unsupported_address_family
→ may produce no Device edge
→ NOT individually counted or exposed by NI-03 V1

unavailable / pending retry
→ reflected only through current pipeline attribution degradation
  when NI-02B runtime exposes attribution_unavailable
```

No percentage or denominator is fabricated.

---

# 43. WHY AMBIGUOUS / UNATTRIBUTED COUNTS ARE NOT SHOWN

NI-02B V1 does not retain complete per-Device durable no-edge disposition
history suitable for a rigorous denominator.

Therefore NI-03 MUST NOT invent:

```text
90% attributed
5 ambiguous events
7 unattributed events
```

from incomplete materialization.

This is a permanent NI-03 V1 safety rule.

---

# 44. RUNTIME-STATE → PRODUCT COVERAGE MAPPING

Exact mapping:

```text
NI-02B runtime = usable

projection_state  = usable
source_state      = usable
attribution_state = usable
```

```text
NI-02B runtime = registry_degraded

projection_state  = degraded
source_state      = usable
attribution_state = usable
```

```text
NI-02B runtime = attribution_unavailable

projection_state  = degraded
source_state      = usable
attribution_state = degraded
```

```text
NI-02B runtime = source_unavailable

projection_state  = degraded
source_state      = unavailable
attribution_state = unknown
```

```text
NI-02B runtime = capacity_waiting_reader

projection_state  = degraded
source_state      = degraded
attribution_state = degraded
```

```text
NI-02B runtime = capacity_halted

projection_state  = degraded
source_state      = degraded
attribution_state = degraded
```

```text
NI-02B runtime = blocked_conflict

projection_state  = degraded
source_state      = degraded
attribution_state = degraded
```

```text
NI-02B runtime = degraded

projection_state  = degraded
source_state      = degraded
attribution_state = degraded
```

```text
NI-02B runtime = initializing

projection_state  = degraded
source_state      = unknown
attribution_state = unknown
```

```text
NI-02B runtime = stopping

projection_state  = degraded
source_state      = unknown
attribution_state = unknown
```

Unknown runtime enum:

```text
integrity unavailable
→ HTTP 503
```

---

# 45. NI-02B DISABLED

If NI-02B projection is deployment-disabled:

```text
Device Protocol API = HTTP 503 source_unavailable
```

NI-03 does NOT open an old projection DB merely to present stale history
when the authoritative projection product is explicitly disabled.

---

# 46. PROJECTION DB UNAVAILABLE

If exact projection DB cannot be opened / trusted:

```text
HTTP 503 source_unavailable
```

No partial DTO.

No fallback to:

```text
NI-01
NI-02A
Registry query-time reconstruction
```

---

# 47. FRESHNESS MODEL

Exact public enum:

```text
fresh
recent
stale
unavailable
```

Freshness is derived from:

```text
last protocol observation age
+
current source coverage
+
current attribution coverage
```

not timestamp alone.

---

# 48. BASE TEMPORAL FRESHNESS

If no `last_protocol_observation`:

```text
base freshness =
unavailable
```

Otherwise:

```text
0 <= age <= 300 seconds
→ fresh

300 < age <= 3600 seconds
→ recent

3600 < age <= 86400 seconds
→ stale
```

No retained evidence older than the 24h summary window participates.

---

# 49. COVERAGE CAP ON FRESHNESS

After base freshness:

## Source unavailable or unknown

If:

```text
source_state in {unavailable, unknown}
```

and evidence exists:

```text
freshness_state = stale
```

This prevents a recent old edge from claiming current freshness while
source continuity is not trustworthy.

## Source degraded

If:

```text
source_state=degraded
```

then:

```text
fresh → recent
recent → recent
stale → stale
```

## Attribution degraded / unavailable / unknown

If:

```text
attribution_state in {degraded, unavailable, unknown}
```

then:

```text
fresh → recent
recent → recent
stale → stale
```

## Both usable

If:

```text
source_state=usable
AND
attribution_state=usable
```

use base temporal freshness unchanged.

---

# 50. `registry_degraded` DOES NOT FALSIFY TEMPORAL FRESHNESS

If current Device binding is already authoritative and NI-02B runtime is:

```text
registry_degraded
```

then:

```text
source_state=usable
attribution_state=usable
```

so temporal freshness is not downgraded solely because Registry
reconciliation is degraded.

Overall:

```text
availability_state=degraded
```

still exposes that projection runtime is not fully healthy.

---

# 51. `attribution_unavailable` WITH COMMITTED EDGES

This production-relevant state MUST remain useful.

If:

```text
runtime_state=attribution_unavailable
```

and committed Device edges exist:

```text
HTTP 200

historical committed protocol evidence remains visible

projection_state=degraded

source_state=usable

attribution_state=degraded
```

A base `fresh` timestamp is capped to:

```text
recent
```

The whole Device Card is NOT reduced to unavailable.

---

# 52. HEALTHY COVERAGE + ZERO EDGES

If:

```text
authoritative Device binding

runtime=usable

zero Device protocol facts in 24h
```

result:

```text
HTTP 200

availability_state=usable

evidence_state=empty

recent_protocols=[]

last_protocol_observation=null

freshness_state=unavailable

source_state=usable

attribution_state=usable
```

Safe meaning:

```text
No recent protocol evidence is retained for this Device.
```

Forbidden meaning:

```text
No network activity.
```

---

# 53. INCOMPLETE COVERAGE + ZERO EDGES

If zero facts and:

```text
source or attribution coverage != usable
```

result remains:

```text
HTTP 200
```

if projection DB itself is readable.

UI meaning:

```text
Insufficient coverage to determine recent protocol evidence.
```

Never:

```text
No network activity.
```

---

# 54. AVAILABILITY STATE

Inside a successful HTTP 200 DTO:

```text
availability_state=usable
```

only when:

```text
projection_state=usable
AND
identity_binding_state=authoritative
```

Otherwise:

```text
availability_state=degraded
```

Store-disabled/unreadable conditions do not return DTO; they return 503.

---

# 55. QUERY-TIME AGGREGATION RETENTION

Because summaries are not persisted:

```text
summary retention =
none
```

Every summary is rebuilt from currently retained NI-02B edges.

Therefore NI-03 cannot create behavioral history longer than NI-02B.

---

# 56. EDGE RETENTION RELATION

NI-02B edge retention remains:

```text
<=14 days
```

NI-03 reads only 24h.

No NI-03 datum extends source retention.

No summary cache survives server-side.

---

# 57. BROWSER RETENTION

Browser application-controlled persistence MUST NOT store NI-03 response in:

```text
localStorage
sessionStorage
cookies
IndexedDB
URL/query
history state
data-* raw JSON
client telemetry
```

Allowed:

```text
ephemeral in-memory object
+
rendered DOM
while Device page is active
```

Transient last-good rendering is bounded by the UI stale-render policy below.

---

# 58. PRIVACY — PUBLIC API

DeviceProtocolSummaryV1 MUST NOT expose:

```text
client_mac

device_ip
peer_ip

ports

transport protocol

direction

peer_scope

edge_id

source_observation_ref

source_event_identity

DNS name

DNS answer

TLS SNI

QUIC SNI

ALPN

Registry row

NI-02A binding ID

capture source ID

projection checkpoint

pending queue size

DB size

runtime reason code
```

Only protocol family + timestamps + product-safe coverage states are public.

---

# 59. ADMIN PERMISSION

NI-03 introduces NO new permission.

Required Site capability:

```text
admin.read.device
```

Rationale:

```text
NI-03 is an additional read-only section of the existing Device Card.
```

No mutation permission.

No global capability.

No Settings capability.

---

# 60. SITE AUTHORIZATION ORDER

Exact route policy:

```text
1. authenticate Admin session;

2. resolve exact Site through existing AdminSiteContextResolver;

3. require existing admin.read.device for that Site;

4. validate canonical device_id;

5. resolve exact Device in that Site;

6. only then query NI-03 read service.
```

No projection read before Site/device authorization.

---

# 61. ADMIN QUERY SERVICE OWNERSHIP

Add exact method:

```text
AdminQueryService.device_protocol_intelligence(
    principal,
    site_id,
    device_id,
    *,
    query_parameters_present=False
)
```

It owns:

```text
authorization

device existence / Site membership

shared Admin concurrency/deadline

server evaluated_at

NI-03 semantic service call

strict serialization/error translation
```

---

# 62. NO SQLITE IN ROUTE

Flask route MUST NOT:

```text
open SQLite

construct SQL

read projection tables

call NI-02A

call NI-01

call Registry directly for NI-03 binding
```

The existing Device gateway remains the Device-card identity lookup,
not a new NI-03 Registry path.

---

# 63. ADMIN API ENDPOINT

Exact endpoint:

```text
GET /admin/api/v1/sites/<site_id>/devices/<device_id>/protocol-intelligence
```

No:

```text
POST
PUT
PATCH
DELETE
```

No query parameters.

No request body.

---

# 64. API VERSION

Exact endpoint API version:

```text
admin.device.protocol-intelligence.v1
```

Success and error envelopes for this endpoint use that identifier.

---

# 65. SUCCESS ENVELOPE

Exact top-level shape:

```json
{
  "api_version": "admin.device.protocol-intelligence.v1",
  "request_id": "<uuid>",
  "site_id": "<site_id>",
  "result": {
    "...": "DeviceProtocolSummaryV1"
  },
  "page": null
}
```

No pagination because output cardinality is:

```text
Recent Protocols <= 3
Last Protocol Observation <= 1
```

---

# 66. API RESPONSE CAP

Exact endpoint maximum serialized response:

```text
16384 bytes
```

If exceeded:

```text
503 response_too_large
```

This is a contract-integrity failure, not a truncation signal.

---

# 67. API CACHE CONTRACT

Response headers:

```text
Cache-Control: no-store
Pragma: no-cache
```

No ETag.

No browser cache reuse.

No CORS expansion.

Same-origin Admin policy remains.

---

# 68. API ERROR MAPPING

Exact:

```text
400 invalid_request
→ invalid Site/device syntax
→ any query parameter present
```

```text
401 authentication_required
→ missing/expired Admin session
```

```text
403 site_forbidden
→ Site not allowed
→ admin.read.device denied
```

```text
404 not_found
→ Device absent from exact Site
→ NI-03 Admin feature disabled
```

```text
429 concurrency_limit
Retry-After: 1
→ Admin/NI-03 reader concurrency gate unavailable
```

```text
503 query_deadline
→ bounded query deadline reached
```

```text
503 source_unavailable
→ NI-02B disabled
→ projection DB unavailable
→ projection evidence integrity unavailable
→ row-scan hard limit exceeded
```

```text
503 response_too_large
→ 16 KiB API cap exceeded
```

```text
500 internal_error
→ unexpected application failure
```

No private exception text.

---

# 69. RUNTIME DEGRADED STATES ARE NOT 503 WHEN STORE IS READABLE

These current NI-02B runtime states:

```text
registry_degraded
attribution_unavailable
source_unavailable
capacity_waiting_reader
capacity_halted
blocked_conflict
degraded
initializing
stopping
```

return:

```text
HTTP 200
```

when:

```text
projection DB can be safely read
AND
exact schema is trustworthy
AND
Device identity query is valid
```

They are represented through coverage/availability fields.

This preserves useful committed evidence.

---

# 70. FEATURE GATE

Introduce deployment-owned:

```text
WEB_ADMIN_DEVICE_PROTOCOL_INTELLIGENCE_ENABLED
```

Repository default:

```text
false
```

Exact values:

```text
true
false
```

This is NOT a writable Admin Settings key in NI-03.

---

# 71. FEATURE-GATE ACTIVATION

Activation target:

```text
captive-portal.service restart
```

No hot enable.

No Admin systemd authority.

No restart button.

Enabling NI-03 does NOT restart or reconfigure:

```text
network-metadata-projection.service
```

---

# 72. ADMIN DISABLED

If:

```text
WEB_ADMIN_ENABLED=false
```

the NI-03 feature flag is inert.

A true NI-03 preference MUST NOT independently activate Admin Web.

No self-lockout/security semantics are changed.

---

# 73. DEVICE CARD SECTION VISIBILITY

Render NI-03 Device section only when:

```text
WEB_ADMIN_DEVICE_PROTOCOL_INTELLIGENCE_ENABLED=true

AND

principal has admin.read.device for current Site
```

No hidden browser request when section is absent.

---

# 74. DEVICE CARD SECTION — EXACT TITLE

Title:

```text
Network / Protocol Intelligence
```

Subtitle:

```text
Recent protocol evidence derived from device-relative network metadata.
```

No service names.

---

# 75. DEVICE CARD P1 FIELDS

The section displays exactly:

```text
Recent Protocols

Last Protocol Observation

Freshness

Source coverage

Attribution coverage

Last evaluated
```

and:

```text
manual Refresh button
```

No raw edge table.

---

# 76. RECENT PROTOCOL PRESENTATION

For each item:

```text
DNS
TLS
QUIC
```

plus:

```text
Last observed timestamp
```

No:

```text
count
percentage
bytes
direction
peer address
service name
```

---

# 77. LAST PROTOCOL OBSERVATION PRESENTATION

Format conceptually:

```text
<TLS|DNS|QUIC>
<observed timestamp>
```

No endpoint details.

---

# 78. FRESHNESS DISPLAY LABELS

Exact public labels:

```text
fresh       → Fresh
recent      → Recent
stale       → Stale
unavailable → Unavailable
```

No score.

No percentage.

---

# 79. COVERAGE DISPLAY LABELS

Exact:

```text
usable      → Available
degraded    → Degraded
unavailable → Unavailable
unknown     → Unknown
```

UI heading remains:

```text
Source coverage
Attribution coverage
```

These are current pipeline states, not percentages.

---

# 80. EMPTY — GOOD COVERAGE UX

When:

```text
evidence_state=empty
source_state=usable
attribution_state=usable
```

show:

```text
No recent protocol evidence
```

message:

```text
No DNS, TLS or QUIC evidence is retained for this Device
in the last 24 hours. This does not prove there was no network activity.
```

---

# 81. EMPTY — INSUFFICIENT COVERAGE UX

When:

```text
evidence_state=empty
AND
(source_state != usable OR attribution_state != usable)
```

show:

```text
Insufficient coverage
```

message:

```text
Recent protocol evidence cannot be determined reliably from the
currently available Network Intelligence coverage.
```

No inactivity claim.

---

# 82. IDENTITY PENDING UX

When public identity binding is:

```text
pending
unavailable
absent
```

show:

```text
Device network identity binding pending
```

message:

```text
Device-relative protocol evidence is not yet authoritatively linked
to this Device for the current Site.
```

No MAC fallback.

Automatic polling continues.

---

# 83. STALE EVIDENCE UX

If:

```text
freshness_state=stale
```

committed data remains visible.

Show:

```text
Stale evidence
```

No automatic clearing solely because it is stale.

---

# 84. TEMPORARY API UNAVAILABLE UX

For 503/network timeout:

```text
Protocol intelligence temporarily unavailable
```

If a previous successful response exists and is younger than the
client stale-render maximum:

```text
keep previous rendered data
+
show temporary-unavailable warning
```

After stale-render maximum expires:

```text
clear protocol data
+
show unavailable state
```

---

# 85. NO SERVICE RECOGNITION UI

Device Card MUST NOT contain labels such as:

```text
YouTube
WhatsApp
Google
TikTok
Streaming
Messaging
Cloud
Social
```

in NI-03.

---

# 86. FRONTEND OWNERSHIP

Use a dedicated static module:

```text
app/admin_web/static/device_protocol_intelligence.js
```

loaded only for the Device page when NI-03 section is enabled.

It does not own protocol semantics.

It consumes only the versioned API DTO.

---

# 87. DOM CONTRACT

Exact section/control IDs:

```text
device-protocol-intelligence

device-protocol-state
device-protocol-state-title
device-protocol-state-message

device-protocol-content

device-protocol-refresh
```

No raw DTO serialized into HTML attributes.

---

# 88. AUTOMATIC POLLING INTERVAL

Code-owned constant:

```text
60 seconds
```

Not configurable in NI-03 V1.

No 1-second polling.

---

# 89. AUTO-POLL START

Start automatic polling only when:

```text
Device Detail page active

NI-03 section rendered

document visible

page not stopped

authenticated session has not entered terminal failure state
```

Initial load:

```text
immediate request
```

then normal schedule.

---

# 90. AUTO-POLL STOP

Stop scheduling when:

```text
document.hidden=true

pagehide

section removed/not admitted

401 session failure

403 authorization failure

404 Device/feature no longer available
```

On visibility return:

```text
immediate refresh if 60s interval has elapsed;
otherwise schedule remaining interval.
```

---

# 91. REQUEST CONCURRENCY — BROWSER

Per Device Card:

```text
maximum in-flight NI-03 request = 1
```

No overlapping automatic requests.

No overlapping manual/automatic requests.

---

# 92. MANUAL REFRESH COALESCING

If manual Refresh is pressed while request is in flight:

```text
do not start second concurrent request
```

Instead:

```text
set exactly one pending manual refresh
```

When active request completes:

```text
run one immediate follow-up request
```

Multiple clicks coalesce into one follow-up.

---

# 93. PAGE-LEVEL REFRESH

The existing Device page Refresh action may invoke the same NI-03 manual
refresh coordinator.

It MUST NOT create a second parallel request when the section-specific
Refresh has already started one.

One coordinator owns NI-03 requests.

---

# 94. BROWSER REQUEST TIMEOUT

Exact request timeout:

```text
10 seconds
```

Use `AbortController`.

Timeout reason is product-safe:

```text
temporarily unavailable
```

No stack/error detail displayed.

---

# 95. SERVER QUERY DEADLINE

NI-03 projection read hard ceiling:

```text
5 seconds
```

Effective server deadline is:

```text
min(
    remaining shared Admin query deadline,
    5 seconds
)
```

The projection SQLite read snapshot MUST NOT intentionally remain open
past that deadline.

---

# 96. SQLITE BUSY TIMEOUT

Exact:

```text
500 ms
```

This preserves current NI-02B read behavior.

Busy timeout does not extend the 5-second NI-03 deadline.

---

# 97. CLIENT RETRY / BACKOFF

After HTTP/network failure:

```text
1st automatic retry delay = 60s

2nd consecutive failure = 120s

3rd and later = 300s
```

Successful request resets backoff to:

```text
60s
```

Manual Refresh bypasses waiting time but not concurrency or request timeout.

---

# 98. MAXIMUM CLIENT STALE RENDER

Maximum age of last successful API response kept visible after request
failures:

```text
900 seconds
15 minutes
```

After 15 minutes from the response's:

```text
evaluated_at_utc
```

the UI must not continue presenting that response as current panel data.

It switches to unavailable presentation.

This client rendering bound is separate from protocol evidence freshness.

---

# 99. NO CLIENT POLLING WHILE HIDDEN

A background/hidden browser tab must not continue NI-03 60-second polling.

This is mandatory.

---

# 100. SERVER CONCURRENCY BOUND

NI-03 uses:

```text
existing shared AdminQueryExecutionControls
```

AND an NI-03-specific process-local read semaphore:

```text
maximum concurrent NI-03 projection reads = 2
```

If unavailable:

```text
429 concurrency_limit
Retry-After: 1
```

This bound is code-owned in V1.

---

# 101. PER-QUERY BOUNDS

Exact:

```text
lookback = 24h

Recent window = 1h

maximum edge facts = 20,000

maximum protocol result items = 3

maximum last-observation items = 1

SQLite busy timeout = 500ms

NI-03 DB snapshot/query deadline = 5s

Admin API body <= 16 KiB
```

No user override.

---

# 102. NI-02B WRITER PROTECTION

NI-03 readers MUST:

```text
use mode=ro

PRAGMA query_only=ON

use short read transaction

respect 5s deadline

never checkpoint WAL

never issue VACUUM

never obtain projection writer lock
```

A read timeout is not NI-02B corruption.

---

# 103. SAME-SNAPSHOT CONSISTENCY

For one summary request, projection runtime state, binding state and edge
facts MUST be read inside one projection SQLite read snapshot.

Do not:

```text
read status
close DB
read edges in another later snapshot
```

for the same summary.

This prevents one DTO mixing unrelated projection moments.

---

# 104. MULTI-SITE CONTRACT

Every NI-03 query is:

```text
site_id + device_id
```

and internally verified against:

```text
site_id + canonical MAC projection binding
```

No:

```text
default Site

global Device query

cross-Site edge query

cross-Site MAC merge
```

---

# 105. SAME DEVICE_ID ACROSS SITES

If NI-02B legitimately binds the same existing Registry device_id to the
same MAC on multiple separately proven Sites:

```text
NI-03 treats each Site independently.
```

Summary cache/request identity is conceptually:

```text
site_id + device_id
```

never `device_id` alone.

---

# 106. NO SERVER SUMMARY CACHE

NI-03 V1 has no application cache.

No:

```text
Redis
in-memory cross-request summary cache
SQLite summary cache
```

Every request executes one bounded current projection read.

This avoids stale cross-Site or late-binding cache semantics in P1.

---

# 107. AVAILABILITY MATRIX — USABLE + EDGES

NI-02B:

```text
runtime=usable
authoritative binding
edges present
```

API:

```text
200
availability=usable
evidence=present
source=usable
attribution=usable
```

Device Card:

```text
show Recent Protocols
show Last Protocol Observation
show timestamp-derived freshness
```

Auto poll:

```text
YES / 60s
```

---

# 108. AVAILABILITY MATRIX — USABLE + ZERO EDGES

NI-02B:

```text
runtime=usable
authoritative binding
zero facts
```

API:

```text
200
availability=usable
evidence=empty
freshness=unavailable
```

Device Card:

```text
No recent protocol evidence
```

Historical committed data visible:

```text
none exists in 24h
```

Auto poll:

```text
YES
```

Safe meaning:

```text
no retained protocol evidence
NOT no network activity
```

---

# 109. AVAILABILITY MATRIX — ATTRIBUTION UNAVAILABLE

NI-02B:

```text
runtime=attribution_unavailable
```

API:

```text
200 if projection DB readable
availability=degraded
source=usable
attribution=degraded
```

Historical committed data:

```text
YES
```

Freshness:

```text
fresh is capped to recent
```

Auto poll:

```text
YES
```

Safe meaning:

```text
committed history is usable;
newest attribution tail may be incomplete/pending.
```

---

# 110. AVAILABILITY MATRIX — REGISTRY DEGRADED

If Device projection binding already authoritative:

```text
HTTP 200

historical data visible

projection=degraded
source=usable
attribution=usable

freshness not downgraded solely by Registry degradation
```

If Device binding not authoritative:

```text
HTTP 200
evidence_state=identity_pending
```

Auto poll:

```text
YES
```

---

# 111. AVAILABILITY MATRIX — SOURCE UNAVAILABLE

API:

```text
200 if projection DB remains readable
```

Committed Device evidence:

```text
visible
```

Coverage:

```text
source=unavailable
attribution=unknown
projection=degraded
```

Freshness with evidence:

```text
stale
```

Auto poll:

```text
YES
```

Safe meaning:

```text
historical committed evidence exists,
but current source continuity cannot be trusted.
```

---

# 112. AVAILABILITY MATRIX — CAPACITY WAITING READER

API:

```text
200
```

Historical committed evidence:

```text
visible
```

Coverage:

```text
source=degraded
attribution=degraded
projection=degraded
```

Base fresh:

```text
capped to recent
```

Auto poll:

```text
YES
```

No claim of corruption.

---

# 113. AVAILABILITY MATRIX — CAPACITY HALTED

API:

```text
200 if store readable
```

Historical committed data:

```text
visible
```

Coverage:

```text
degraded
```

Auto poll:

```text
YES
```

No new-edge expectation.

No fallback reconstruction.

---

# 114. AVAILABILITY MATRIX — BLOCKED CONFLICT

API:

```text
200 if store readable
```

Historical committed data:

```text
visible
```

Coverage:

```text
degraded
```

Auto poll:

```text
YES
```

Safe meaning:

```text
committed evidence remains readable;
projection advancement is blocked.
```

No conflict detail goes to browser.

---

# 115. AVAILABILITY MATRIX — DISABLED

If NI-02B is disabled:

```text
HTTP 503 source_unavailable
```

Device Card:

```text
temporarily unavailable
```

Historical DB is not opened as a fallback.

Auto polling:

```text
YES with 60/120/300 backoff
```

unless NI-03 feature itself is disabled, in which case section/API are absent/404.

---

# 116. AVAILABILITY MATRIX — PROJECTION DB UNAVAILABLE

```text
HTTP 503 source_unavailable
```

No summary DTO.

Last client-good result may remain rendered for max 15m.

Auto poll:

```text
YES with failure backoff
```

---

# 117. AVAILABILITY MATRIX — DEVICE ABSENT FROM SITE

Existing Device gateway returns no Device.

API:

```text
404 not_found
```

Device Card protocol section:

```text
terminal for current page
```

Auto polling:

```text
STOP
```

No projection lookup after confirmed Device absence.

---

# 118. AVAILABILITY MATRIX — IDENTITY PENDING

Existing Device exists, but NI-02B Site+MAC binding is:

```text
pending
unavailable
absent
```

API:

```text
200
availability=degraded
evidence_state=identity_pending
freshness=unavailable
```

Edge scan:

```text
NO
```

Auto poll:

```text
YES / 60s
```

When NI-02B later binds authoritatively, old retained edges become visible
on the next read.

---

# 119. SOURCE GAP INSIDE 24H

NI-03 V1 does not have authoritative historical gap materialization.

Therefore if a source gap occurred earlier inside 24h:

```text
NI-03 MUST NOT claim full-window completeness
```

even if current runtime later returns to usable.

This is why:

```text
historical_window_completeness_claimed=false
```

is permanent V1 behavior.

No gap is reconstructed from absence of edges.

---

# 120. ATTRIBUTION GAP INSIDE 24H

Same rule:

```text
no historical completeness percentage

no inferred missing-event count

no "all activity attributed" claim
```

Current attribution state describes only current pipeline usability.

---

# 121. RETENTION TRUNCATION

Because query lookback is 24h and NI-02B edge retention is 14d:

```text
normal retention does not truncate the NI-03 query window.
```

However a recently created/rebuilt projection store may have less than
24h of materialized evidence.

NI-03 does not invent the missing period.

Completeness remains false.

---

# 122. ADMIN RUNTIME COMPOSITION

When:

```text
WEB_ADMIN_ENABLED=true
AND
WEB_ADMIN_DEVICE_PROTOCOL_INTELLIGENCE_ENABLED=true
```

Admin runtime composes:

```text
DeviceNetworkMetadataReadService

DeviceProtocolIntelligenceReadService
```

as optional read-only dependencies.

Failure to open projection DB at startup MUST NOT break Admin Web startup.

The API returns runtime unavailability later.

---

# 123. FAILURE ISOLATION

NI-03 failure MUST NOT break:

```text
Guest Portal

CAPPORT

Authorization

Omada authorization

Visitor Registry

Device Fingerprint

NI-01

NI-02A

NI-02B writer

existing Admin pages

existing Device Current Context
```

NI-03 is optional read-only product functionality.

---

# 124. NO NEW SYSTEMD UNIT

NI-03 V1 introduces:

```text
NO new service
NO new timer
NO new daemon
```

No:

```text
network-protocol-intelligence.service
```

is admitted.

All server-side NI-03 product reads execute inside:

```text
captive-portal.service
```

under existing Admin request lifecycle.

---

# 125. DEPLOYMENT DEFAULT OFF

Repository/default config:

```text
WEB_ADMIN_DEVICE_PROTOCOL_INTELLIGENCE_ENABLED=false
```

Code deployment alone MUST NOT expose the Device Card section.

Production activation is separate.

---

# 126. PRODUCTION ACTIVATION

Separate activation requires:

```text
exact accepted repository HEAD/TREE

NI-02B production accepted and readable

set:
WEB_ADMIN_DEVICE_PROTOCOL_INTELLIGENCE_ENABLED=true

restart captive-portal.service

verify Admin Device Card/API

verify no NI-02B writer regression

verify polling bounds
```

No change to NI-02B service priority/mechanics is required.

---

# 127. ROLLBACK

Rollback:

```text
WEB_ADMIN_DEVICE_PROTOCOL_INTELLIGENCE_ENABLED=false

restart captive-portal.service
```

or code rollback after disabling the feature.

No DB restore.

No NI-02B restart required.

No projection data migration rollback.

---

# 128. MIGRATION

```text
DATABASE MIGRATION = NONE
```

No schema change to:

```text
network_metadata_projection.sqlite3
network_metadata.sqlite3
network_attribution.sqlite3
visitor_registry.sqlite3
```

---

# 129. REBUILD

```text
NI-03 SUMMARY REBUILD = NOT APPLICABLE
```

Every request recomputes from retained NI-02B projection.

If NI-02B derived store itself is rebuilt under its accepted contract,
NI-03 automatically reflects the rebuilt retained projection.

---

# 130. FUTURE NI-04 RELATIONSHIP

NI-03 summary is intentionally lossy.

Therefore NI-04 MUST NOT use:

```text
DeviceProtocolSummaryV1
```

as its mandatory evidence source.

Intended future relationship:

```text
DeviceNetworkMetadataEdgeV1
        ├─→ NI-03 Protocol Intelligence summary
        │
        └─→ NI-04 Service Recognition
             using separately admitted retained metadata/source refs
```

NI-04 does not need to rebuild Device attribution.

---

# 131. PROTOCOL SUMMARY IS NOT SERVICE-RECOGNITION INPUT AUTHORITY

NI-03 loses:

```text
DNS names
SNI
peer IP
ALPN
other recognition evidence
```

by design.

Therefore it cannot become the only source for NI-04.

---

# 132. OBSERVABILITY — SERVER

Allowed aggregate telemetry:

```text
protocol_intelligence_requests_total

protocol_intelligence_result_state:
    present
    empty
    identity_pending
    unavailable

protocol_intelligence_query_duration_ms

protocol_intelligence_rows_scanned

protocol_intelligence_row_limit_exceeded_total

protocol_intelligence_deadline_total

protocol_intelligence_busy_total

protocol_intelligence_http_status_class
```

No per-Device behavior metric.

---

# 133. OBSERVABILITY PRIVACY

Logs/telemetry MUST NOT contain:

```text
MAC

device_id

raw IP

port

DNS name

SNI

edge payload

protocol history list for one Device
```

Allowed bounded context:

```text
request_id
Site ID
safe failure category
row-count bucket
duration bucket
```

No browser engineering telemetry.

---

# 134. CLIENT OBSERVABILITY

Browser may render product state only.

It MUST NOT send:

```text
poll timing diagnostics
raw runtime state
edge count
Device protocol history
errors with stack traces
```

to telemetry from NI-03 P1.

---

# 135. PERFORMANCE — QUERY COMPLEXITY

One NI-03 request may inspect at most:

```text
20,001 narrow rows
```

from one exact:

```text
Site + MAC + 24h
```

range.

No full Site scan.

No cross-Site scan.

No 14-day scan.

---

# 136. PERFORMANCE — ACCEPTANCE CEILING

The hard correctness ceiling is:

```text
5 seconds server-side
```

A query that cannot finish within it returns bounded unavailable/deadline
semantics.

No read request is allowed to keep a projection SQLite snapshot open
indefinitely.

---

# 137. PERFORMANCE — WRITER COEXISTENCE

Lab acceptance MUST prove with active NI-02B writes that:

```text
2 simultaneous NI-03 readers
+
normal NI-02B writer
```

does NOT cause:

```text
projection writer permanent fault

blocked_conflict

false capacity_halted

checkpoint corruption
```

Temporary ordinary WAL reader contention remains a valid SQLite condition.

---

# 138. PRODUCTION RESPONSE CARDINALITY

Public DTO maximum:

```text
Recent Protocols = 3

Last Protocol Observation = 1

Coverage dimensions = 3
```

There is no pagination.

---

# 139. DETERMINISTIC ACCEPTANCE — PROTOCOL SEMANTICS

Required:

```text
DNS edge
→ Recent DNS when inside 60m

TLS edge
→ Recent TLS when inside 60m

QUIC edge
→ Recent QUIC when inside 60m

multiple DNS edges
→ one DNS item
→ last_observed_at=max(DNS event_at)

TCP/UDP
→ never Product Protocol

unknown source_event_family
→ fail closed / unavailable
```

---

# 140. ACCEPTANCE — RECENT WINDOW

```text
event at evaluated_at-3600s
→ Recent

event 1 microsecond before evaluated_at-3600s
→ not Recent

event inside 24h but outside 60m
→ may be Last Protocol Observation
→ not Recent Protocol

event exactly summary_from
→ included in 24h summary

event before summary_from
→ excluded
```

---

# 141. ACCEPTANCE — FRESHNESS BOUNDARIES

```text
age=0
→ fresh

age=300s
→ fresh

age>300s and <=3600s
→ recent

age>3600s and <=86400s
→ stale

no Last Protocol Observation
→ unavailable
```

Coverage caps must then be applied exactly.

---

# 142. ACCEPTANCE — COVERAGE CAP

Required:

```text
last edge age=2m
runtime=usable
→ fresh

last edge age=2m
runtime=attribution_unavailable
→ recent

last edge age=2m
runtime=capacity_halted
→ recent

last edge age=2m
runtime=source_unavailable
→ stale

last edge age=30m
runtime=attribution_unavailable
→ recent

last edge age=2h
any readable degraded runtime
→ stale
```

---

# 143. ACCEPTANCE — ZERO EDGE

```text
usable runtime + authoritative binding + zero facts
→ evidence=empty
→ no protocol evidence wording
→ NEVER "no network activity"

source unavailable + zero facts
→ insufficient coverage wording
→ NEVER "no activity"

attribution degraded + zero facts
→ insufficient coverage wording
```

---

# 144. ACCEPTANCE — DEVICE IDENTITY

```text
exact Site + authoritative Device binding
→ edges eligible

same device_id on another Site
→ not included

other MAC
→ not included

projection binding absent
→ identity_pending
→ no edge scan

not_yet_registry_resolved
→ identity_pending
→ no edge scan

registry_unavailable binding
→ identity_pending
→ no edge scan

late authoritative binding
→ retained pre-binding edges automatically visible
→ no summary rewrite
```

---

# 145. ACCEPTANCE — LOCAL TWO-EDGE OBSERVATION

If same Device can legitimately have two retained role edges for one
observation:

```text
protocol set remains one protocol family
```

No double display.

No count is exposed.

---

# 146. ACCEPTANCE — SITE ISOLATION

Mandatory:

```text
Site A request
never reads Site B edges

wrong Site for existing device_id
→ 404 after existing Device lookup

Site not allowed
→ 403

no default-Site fallback
```

---

# 147. ACCEPTANCE — PRE-REGISTRY

An NI-02B edge existing only under pre-Registry Site+MAC identity:

```text
is NOT shown on existing Device Card
until NI-02B authoritative binding exists.
```

After binding:

```text
same retained edge appears in summary automatically.
```

No Registry write.

---

# 148. ACCEPTANCE — API

Required:

```text
GET exact endpoint
→ 200 versioned DTO

query parameter present
→ 400

invalid canonical device ID
→ 400

unauthenticated
→ 401

wrong Site/capability
→ 403

Device missing
→ 404

feature disabled
→ 404

reader concurrency exceeded
→ 429 + Retry-After:1

deadline
→ 503 query_deadline

projection disabled/store unavailable
→ 503 source_unavailable

response >16KiB
→ 503 response_too_large

Cache-Control=no-store
Pragma=no-cache
```

---

# 149. ACCEPTANCE — CURRENT DEGRADED PRODUCTION CASE

Simulate:

```text
NI-02B runtime=attribution_unavailable
committed fresh edges exist
```

Must return:

```text
200

committed protocol evidence visible

availability=degraded

source=usable

attribution=degraded

fresh base evidence capped to recent

auto-poll continues
```

No whole-card unavailable collapse.

---

# 150. ACCEPTANCE — UI

Required:

```text
section absent when feature OFF

section present when feature ON + authorized

Recent Protocols rendered

Last Protocol Observation rendered

fresh/recent/stale/unavailable rendered

source coverage rendered

attribution coverage rendered

evaluated time rendered

manual Refresh works

automatic poll works

no duplicate concurrent requests

hidden tab stops polling

pagehide stops polling

visibility return resumes bounded polling
```

---

# 151. ACCEPTANCE — MANUAL/AUTO COALESCING

Required:

```text
auto request active
+
manual click x5
→ no parallel requests
→ exactly one immediate follow-up after current request
```

Likewise page-level and section-level Refresh must share one coordinator.

---

# 152. ACCEPTANCE — BACKOFF

Required:

```text
1st failure → next auto attempt 60s

2nd consecutive failure → 120s

3rd+ → 300s

success → reset 60s

manual → immediate if no request active
or one coalesced follow-up
```

---

# 153. ACCEPTANCE — STALE CLIENT RENDER

Required:

```text
last successful summary age <15m
+
temporary request failure
→ old data may remain visibly marked unavailable/stale-request

age >=15m
→ protocol data cleared from active current panel
→ unavailable presentation
```

No localStorage/sessionStorage persistence.

---

# 154. ACCEPTANCE — PRIVACY

Prove API/HTML/JS do NOT expose:

```text
DNS names
SNI
remote IP
remote port
MAC
edge_id
raw Registry row
NI-02A binding
raw projection runtime reason
```

Prove logs do not contain those values from NI-03 path.

---

# 155. ACCEPTANCE — ROW LIMIT

```text
20,000 matching facts
→ summary allowed

20,001 matching facts
→ 503 source_unavailable

no partial protocol set

no silent newest-only truncation
```

---

# 156. ACCEPTANCE — SQLITE CONCURRENCY

Required:

```text
mode=ro
query_only=ON
foreign_keys=ON
busy_timeout=500ms

same-snapshot status/binding/facts

2 NI-03 reads max concurrently

5s server read deadline

active NI-02B writer unaffected beyond ordinary bounded reader contention
```

---

# 157. ACCEPTANCE — FAILURE ISOLATION

Inject:

```text
projection disabled
projection DB missing
projection DB busy
projection DB schema invalid
runtime source_unavailable
runtime attribution_unavailable
runtime capacity_waiting_reader
runtime capacity_halted
runtime blocked_conflict
NI-03 row limit exceeded
browser timeout
```

Prove no regression to:

```text
Portal
CAPPORT
Authorization
Fingerprint Sensor
NI-01
NI-02A
NI-02B writer
Visitor Registry
other Admin pages
```

---

# 158. ACCEPTANCE — NO NI-04

Search API/HTML/code path for product output.

Must prove no service/provider/company inference.

No DNS/SNI recognition rules.

No taxonomy.

No ServiceObservation/DeviceServiceSummary.

---

# 159. ACCEPTANCE — NO PERSISTED SUMMARY

Must prove:

```text
no new DB

no new table

no summary row

no checkpoint

no background writer

no summary retention job
```

Summary is read-time only.

---

# 160. Coder OWNERSHIP BOUNDARIES — ARCHITECTURAL

After Tech Lead implementation authorization, implementation ownership may
touch only the following conceptual boundaries.

## New NI-03 semantic module

```text
app/network_protocol_intelligence/
```

for:

```text
protocol constants
DTOs
coverage mapping
freshness
aggregation
read service
```

## Bounded NI-02B read extension

```text
app/network_metadata_projection/read_service.py
```

only for the exact product-safe protocol-evidence read boundary.

No schema/writer modifications.

## Admin integration

Bounded changes under:

```text
app/admin_web/
```

for:

```text
runtime composition
AdminQueryService
route
strict serializer
Device template
dedicated NI-03 JS
bounded CSS
feature flag parsing/presentation
```

Tests/docs/deployment example updates are permitted within the accepted
implementation contract.

---

# 161. FORBIDDEN IMPLEMENTATION OWNERSHIP

NI-03 MUST NOT modify semantics/schema of:

```text
NI-01 normalizer
NI-01 DB schema
NI-01 writer
NI-01 retention

NI-02A authority
NI-02A DB schema
NI-02A writer
DHCP admission

NI-02B writer
NI-02B edge schema
NI-02B checkpoint/retry
NI-02B retention
NI-02B late-binding semantics
NI-02B service resource priority

Visitor Registry writer/schema/device_id rules

Visit Lifecycle

Device Fingerprint identity

CAPPORT

Authorization semantics

Omada authorization
```

Any implementation need crossing these boundaries is:

```text
STOP → Architect return
```

---

# 162. NO NEW CAPABILITY

Do not add:

```text
admin.read.protocol
admin.read.network_intelligence
```

in NI-03 P1.

Existing:

```text
admin.read.device
```

is the exact permission.

---

# 163. NO SETTINGS MUTATION

NI-03 does not introduce:

```text
Settings page key
Settings API
Settings generation
Settings schema migration
```

The deployment feature gate is not writable through Admin Settings in
this stage.

---

# 164. NO SYSTEMD AUTHORITY

Admin UI does not:

```text
start
stop
restart
enable
disable
```

NI-02B.

No `systemctl`.

No systemd D-Bus.

---

# 165. OPEN ARCHITECTURE ISSUES

```text
OPEN_P0 = 0
OPEN_P1 = 0
OPEN_P2 = 0
```

No live-network research is required before Technical Lead implementation
contract preparation.

---

# 166. ARCHITECTURE INVARIANTS

```text
NI03-I01
Product Protocol vocabulary is exactly dns/tls/quic.

NI03-I02
TCP/UDP are not Product Protocols.

NI03-I03
NI-03 performs no service recognition.

NI03-I04
NI-03 performs no query-time Device attribution.

NI03-I05
NI-03 consumes only NI-02B materialized Device projection.

NI03-I06
Summary is read-time and non-persistent.

NI03-I07
Summary window is exactly 24h.

NI03-I08
Recent Protocols window is exactly 60m.

NI03-I09
Fresh threshold is exactly 5m.

NI03-I10
Protocol event counts are not public product fields.

NI03-I11
Direction/peer scope are not P1 Device Card fields.

NI03-I12
Zero edges never means no network activity.

NI03-I13
Historical 24h completeness is never claimed in V1.

NI03-I14
Current source/attribution coverage is derived from NI-02B runtime only.

NI03-I15
No NI-01 direct read from NI-03.

NI03-I16
No NI-02A direct read from NI-03.

NI03-I17
Pre-Registry edges are excluded until NI-02B authoritative device binding.

NI03-I18
Late binding makes retained edges visible without summary rewrite.

NI03-I19
All queries are Site-scoped.

NI03-I20
No raw DNS/SNI/IP/port is public.

NI03-I21
No new DB/service/writer exists.

NI03-I22
Auto polling is 60s and stops while hidden.

NI03-I23
One browser request in flight max.

NI03-I24
Server NI-03 read concurrency max is 2.

NI03-I25
Per-query edge-fact bound is 20,000.

NI03-I26
Per-query projection read deadline is 5s.

NI03-I27
Feature is deployment-default OFF.

NI03-I28
Existing admin.read.device is the only NI-03 Site capability.

NI03-I29
NI-04 must not use DeviceProtocolSummaryV1 as its mandatory evidence authority.

NI03-I30
NI-03 failure cannot break upstream Network Intelligence acquisition.
```

---

# 167. FINAL ARCHITECTURE VERDICT

```text
TASK =
TASK-DTI-NI-03

TITLE =
Protocol Intelligence + Device Card P1

BASELINE =
main@3467da8abd4ad4bb5b381a13e374e2e8faf4685e

TREE =
2e3cb2b345af370275cb9b8fe35729f6f5218d35

BASELINE_MOVED =
NO

MATERIAL_DIFFERENCES =
NONE

PRODUCT PROTOCOLS =
dns
tls
quic

TRANSPORT AS PRODUCT PROTOCOL =
NO

SERVICE RECOGNITION =
NO

STORAGE MODEL =
BOUNDED READ-TIME AGGREGATION
OVER NI-02B PROJECTION

NEW DATABASE =
NO

NEW WRITER =
NO

NEW SERVICE =
NO

SUMMARY PERSISTENCE =
NO

SUMMARY WINDOW =
24h

RECENT PROTOCOL WINDOW =
60m

FRESH THRESHOLD =
5m

RECENT THRESHOLD =
60m

MAX EDGE FACTS =
20000

MAX NI-03 SERVER READ TIME =
5s

MAX NI-03 CONCURRENT SERVER READS =
2

SQLITE BUSY TIMEOUT =
500ms

AUTO POLL =
60s

BROWSER REQUEST TIMEOUT =
10s

BROWSER FAILURE BACKOFF =
60 / 120 / 300s

MAX LAST-GOOD CLIENT RENDER =
15m

ADMIN API =
GET /admin/api/v1/sites/<site_id>/devices/<device_id>/protocol-intelligence

API VERSION =
admin.device.protocol-intelligence.v1

ADMIN CAPABILITY =
admin.read.device

FEATURE GATE =
WEB_ADMIN_DEVICE_PROTOCOL_INTELLIGENCE_ENABLED

FEATURE DEFAULT =
false

ACTIVATION TARGET =
captive-portal.service restart

QUERY-TIME NI-01 =
NO

QUERY-TIME NI-02A =
NO

QUERY-TIME REGISTRY BINDING =
NO

PRE-REGISTRY EDGE VISIBILITY =
EXCLUDED UNTIL NI-02B AUTHORITATIVE BINDING

ZERO EDGE =
NOT NO ACTIVITY

HISTORICAL WINDOW COMPLETENESS CLAIM =
NO

RAW DNS/SNI/IP/PORT UI =
NO

DIRECTION / PEER SCOPE P1 UI =
NO

PROTOCOL COUNTS / PERCENTAGES =
NO

DOMINANT PROTOCOL =
NO

MULTI-SITE =
SITE-SCOPED FROM DAY ONE

OPEN_P0 =
0

OPEN_P1 =
0

OPEN_P2 =
0
```

---

# 168. GOVERNANCE DISPOSITION

```text
ARCHITECTURE_STATUS=ACCEPTED

OPEN_P0=0
OPEN_P1=0
OPEN_P2=0

READY_FOR_TECH_LEAD_IMPLEMENTATION_CONTRACT=YES

TECH_LEAD_REVIEW=PENDING

IMPLEMENTATION_AUTHORIZATION=NO

CODER=HOLD

PRODUCTION_CHANGE=NO
```

Next exact governance step:

```text
Architect
→ this NI-03 Architecture Contract v1

Tech Lead
→ architecture review

if PASS:

Tech Lead
→ one exact implementation contract / Coder TASK

then and only then:

Coder implementation authorization
```
