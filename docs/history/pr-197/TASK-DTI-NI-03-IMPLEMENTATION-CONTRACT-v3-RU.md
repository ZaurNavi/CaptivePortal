# TASK-DTI-NI-03
## PROTOCOL INTELLIGENCE + DEVICE CARD P1
### TECH LEAD IMPLEMENTATION CONTRACT v3
### CODER TASK — IMPLEMENTATION AUTHORIZED

**Проект:** CaptivPortal  
**Роль документа:** Technical Lead → Coder  
**Дата:** 2026-10-09  
**Implementation stage:** NI-03  
**Production change:** NO  
**Repository publication:** NO, до отдельного Tech Lead authorization  

---

# 0. TECH LEAD ARCHITECTURE / BASELINE DISPOSITION

Reviewed architecture:

```text
TASK-DTI-NI-03
ARCHITECTURE CONTRACT v1

+

TASK-DTI-NI-03
ARCHITECTURE CONTRACT v1-R1
TECH LEAD R1 — BOUNDED REPAIR ADDENDUM
```

Architecture was originally accepted against:

```text
ORIGINAL_ARCHITECTURE_BASE_HEAD=
3467da8abd4ad4bb5b381a13e374e2e8faf4685e

ORIGINAL_ARCHITECTURE_BASE_TREE=
2e3cb2b345af370275cb9b8fe35729f6f5218d35
```

Before Coder implementation began, `main` advanced through:

```text
ADMIN-SETTINGS-06
PR #196
Merge commit:
51deead342bd821b5c46fb75a7ceef37bef63e7c
```

Authoritative current implementation baseline:

```text
BASE_HEAD=
51deead342bd821b5c46fb75a7ceef37bef63e7c

BASE_TREE=
7b6cfa20c23c097e87059ca12a593f697f0a36a2

PARENT_1=
3467da8abd4ad4bb5b381a13e374e2e8faf4685e

PARENT_2=
fe075ba8307fd961d658362922f774d10a5e108e
```

Baseline movement impact was reviewed by Tech Lead before any NI-03 source
change.

Material ADMIN-SETTINGS-06 changes intersect NI-03 implementation files:

```text
app/admin_web/config.py
app/admin_web/runtime.py
app/admin_web/routes.py
app/admin_web/templates/admin/base.html
app/admin_web/static/admin.css
```

and introduce:

```text
AdminFeaturePlanV1
Settings → Features registry/UI
startup feature-plan composition
```

Disposition:

```text
NI-03 semantic architecture remains valid.

NI-03 remains:
deployment-owned
default-OFF
read-only
NOT a writable Admin Settings feature in this stage.

NI-03 MUST NOT be added to:
SettingsDefinitionRegistry feature domain
AdminFeaturePlanV1 registry
Settings → Features UI
Settings mutation API

WEB_ADMIN_ENABLED remains an outer Admin composition gate.
A true NI-03 deployment preference while WEB_ADMIN_ENABLED=false
is inert and MUST NOT by itself make Admin configuration invalid.
```

R1 disposition remains:

```text
P1-01 — NI-02B configuration handoff to Admin runtime
CLOSED

P1-02 — application device_id logging vs Nginx access log
CLOSED
```

Final Tech Lead verdict after baseline movement:

```text
ARCHITECTURE_REOPEN=NO
ARCHITECT_RETURN=NO

BASELINE_RECONCILIATION=PASS

OPEN_P0=0
OPEN_P1=0
OPEN_P2=0

READY_FOR_IMPLEMENTATION=YES
```

Coder must implement ONLY from the authoritative current baseline above.
The old baseline is not an implementation base anymore.

---

# 1. CODER AUTHORIZATION STATE

This TASK is the complete implementation instruction.

Coder does NOT:

```text
prepare an architecture
prepare a PLAN
research alternatives
choose semantics
invent interfaces
propose scope
change contracts
make product decisions
```

Coder executes the exact implementation contract below.

Authorization:

```text
CODER_IMPLEMENTATION=GO

CODER_ARCHITECTURE_DECISIONS=NO
CODER_PLAN_REQUIRED=NO
CODER_RESEARCH_REQUIRED=NO
CODER_SCOPE_CHOICE=NO

COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOYMENT=NO
PRODUCTION_ACTION=NO
```

Coder starts implementation immediately from the pinned baseline.

Exact implementation branch:

```text
feature/dti-ni-03-protocol-intelligence
```

Before changing source, Coder must ensure the implementation worktree is clean
and based exactly on:

```text
HEAD=51deead342bd821b5c46fb75a7ceef37bef63e7c
TREE=7b6cfa20c23c097e87059ca12a593f697f0a36a2
```

Because the previous STOP occurred before implementation:

```text
IMPLEMENTATION_STARTED=NO
SOURCE_CHANGED=NO
```

there is no NI-03 candidate to merge/rebase from the old baseline.

If a concrete contradiction makes the exact contract impossible inside the
authorized boundaries, Coder MUST STOP and report the contradiction only.
Coder MUST NOT solve it by selecting a new architecture.

---

# 2. GOAL

Implement NI-03 P1:

```text
existing Device
+
existing NI-02B materialized Device-relative network metadata
        ↓
bounded read-time protocol aggregation
        ↓
DeviceProtocolSummaryV1
        ↓
read-only Admin API
        ↓
Device Card:
Network / Protocol Intelligence
```

The user-visible result must answer only:

```text
Which admitted protocol families were recently observed
for this exact Site + Device?

What was the latest admitted protocol observation?

How fresh/useful is the evidence right now?
```

Product Protocol V1 is exactly:

```text
dns
tls
quic
```

Display labels are exactly:

```text
DNS
TLS
QUIC
```

---

# 3. EXPLICIT NON-GOALS

Do NOT implement:

```text
Service Recognition
Google / YouTube / WhatsApp / Microsoft / Telegram / TikTok etc.
organization/provider inference
ASN inference
service categories

Dominant Protocol
protocol percentages
event-count product metrics
traffic totals / bytes
direction presentation
peer-scope presentation
remote endpoint presentation

raw DNS names
raw SNI
raw remote IP/port history

query-time NI-01 read
query-time NI-02A resolve_ipv4()
query-time Registry binding

new database
new writer
new background service
new timer
new checkpoint
new durable protocol-summary history
server-side summary cache

new Admin capability
Admin Settings mutation
Admin systemd control

NI-02B schema/writer/checkpoint/retry/retention changes
NI-02A authority changes
NI-01 schema/normalizer/writer changes
Visitor Registry writer/schema changes
CAPPORT/Auth/Omada semantics changes
Nginx route/log-format changes
```

Any discovered need for one of these is:

```text
STOP → TECH LEAD
```

Do not implement around it.

---

# 4. FROZEN SEMANTIC CONTRACT

## 4.1. Time windows

Exact:

```text
summary window = 86400 seconds / 24h
recent window  = 3600 seconds / 60m

summary interval:
[ evaluated_at - 24h, evaluated_at )

recent interval:
[ evaluated_at - 60m, evaluated_at )
```

Boundary rules:

```text
event exactly evaluated_at-3600s
→ Recent

event 1 microsecond before evaluated_at-3600s
→ not Recent

event exactly evaluated_at-86400s
→ included in 24h summary

event < evaluated_at-86400s
→ excluded

event >= evaluated_at
→ integrity unavailable
→ no public result
```

`evaluated_at` is server UTC, never browser time.

## 4.2. Recent Protocol aggregation

For all eligible facts inside the recent interval:

```text
group by protocol_id
retain max(event_at)
```

Exactly one item per protocol.

Ordering:

```text
last_observed_at DESC
tie → canonical rank ASC
```

Canonical rank:

```text
DNS
TLS
QUIC
```

## 4.3. Last Protocol Observation

Choose across the entire 24h summary window:

```text
event_at DESC
then protocol canonical rank ASC
then edge_id ASC
```

`edge_id` is internal tie-break only and MUST NOT be public.

## 4.4. Product counts

No public:

```text
event_count
percentage
ratio
dominant protocol
```

The internal 20,000-row safety bound is NOT a product metric.

---

# 5. EXACT PUBLIC DTO

Implement exact public semantic DTO:

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
    usable | degraded

evidence_state:
    present | empty | identity_pending

identity_binding_state:
    authoritative | pending | unavailable | absent

recent_protocols:
    tuple[RecentProtocolV1, ...]

last_protocol_observation:
    LastProtocolObservationV1 | null

freshness_state:
    fresh | recent | stale | unavailable

coverage:
    scope = current_pipeline

    source_state:
        usable | degraded | unavailable | unknown

    attribution_state:
        usable | degraded | unavailable | unknown

    projection_state:
        usable | degraded

    historical_window_completeness_claimed:
        false
```

No extra public fields.

`RecentProtocolV1` exactly:

```text
protocol_id:
    dns | tls | quic

display_label:
    DNS | TLS | QUIC

last_observed_at:
    canonical UTC timestamp
```

`LastProtocolObservationV1` exactly:

```text
protocol_id:
    dns | tls | quic

display_label:
    DNS | TLS | QUIC

observed_at:
    canonical UTC timestamp
```

Public DTO MUST NOT contain:

```text
client_mac
device_ip
peer_ip
port
transport protocol
direction
peer_scope
edge_id
source observation identity/ref
DNS name
DNS answer
TLS/QUIC SNI
ALPN
Registry row
NI-02A binding ID
capture source ID
projection checkpoint
pending queue size
DB size
runtime safe_reason
```

---

# 6. EVIDENCE / IDENTITY SEMANTICS

Projection binding mapping:

```text
authoritative
→ identity_binding_state=authoritative

not_yet_registry_resolved
→ pending

registry_unavailable
→ unavailable

no Site+MAC binding
→ absent
```

Evidence state:

```text
binding not authoritative
→ evidence_state=identity_pending
→ DO NOT scan edges

authoritative binding + >=1 eligible fact
→ evidence_state=present

authoritative binding + 0 eligible facts
→ evidence_state=empty
```

Authoritative projection binding must match the requested `device_id`.

If:

```text
binding_state=authoritative
AND bound device_id != requested device_id
```

then:

```text
integrity unavailable
→ HTTP 503 source_unavailable
```

No fallback MAC/device reassignment.

Late binding behavior:

```text
before authoritative NI-02B binding
→ edge scan forbidden

after NI-02B authoritative binding
→ next NI-03 request may see all still-retained matching edges
→ no edge rewrite
→ no summary rewrite/persistence
```

---

# 7. COVERAGE MAPPING

Coverage is current pipeline state only.

Always:

```text
coverage.scope=current_pipeline
historical_window_completeness_claimed=false
```

Do NOT fabricate percentages or historical completeness.

Exact NI-02B runtime mapping:

```text
usable
→ projection=usable
→ source=usable
→ attribution=usable

registry_degraded
→ projection=degraded
→ source=usable
→ attribution=usable

attribution_unavailable
→ projection=degraded
→ source=usable
→ attribution=degraded

source_unavailable
→ projection=degraded
→ source=unavailable
→ attribution=unknown

capacity_waiting_reader
capacity_halted
blocked_conflict
degraded
→ projection=degraded
→ source=degraded
→ attribution=degraded

initializing
stopping
→ projection=degraded
→ source=unknown
→ attribution=unknown
```

Unknown NI-02B runtime enum:

```text
integrity unavailable
→ HTTP 503 source_unavailable
```

Readable degraded projection states MUST NOT automatically become 503.

Committed evidence stays usable according to this mapping.

---

# 8. FRESHNESS

Base freshness from last protocol observation age:

```text
no last observation
→ unavailable

0 <= age <= 300s
→ fresh

300s < age <= 3600s
→ recent

3600s < age <= 86400s
→ stale
```

Then apply coverage cap.

If:

```text
source_state in {unavailable, unknown}
```

and evidence exists:

```text
freshness=stale
```

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

If source and attribution are both usable, retain base freshness.

Important current-production case:

```text
runtime=attribution_unavailable
+
committed fresh edges
→ HTTP 200
→ availability=degraded
→ source=usable
→ attribution=degraded
→ base fresh capped to recent
```

Do not collapse whole card to unavailable.

---

# 9. NEW SEMANTIC MODULE

Create:

```text
app/network_protocol_intelligence/
```

Expected public implementation files:

```text
app/network_protocol_intelligence/__init__.py
app/network_protocol_intelligence/models.py
app/network_protocol_intelligence/read_service.py
```

Private helper decomposition inside this package is Coder-owned only if it does not change this TASK.

Canonical semantic owner:

```text
DeviceProtocolIntelligenceReadService
```

Canonical method:

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

The service owns:

```text
protocol vocabulary
24h/60m window calculation
aggregation
ordering
freshness
coverage mapping
DTO construction
NI-03-specific process-local read concurrency gate
```

It MUST NOT own:

```text
projection schema
Device attribution
Registry binding logic
NI-02B writer state changes
```

---

# 10. NI-03-SPECIFIC SERVER CONCURRENCY / DEADLINE

Implement one process-local NI-03 read semaphore:

```text
maximum concurrent NI-03 projection reads = 2
```

Acquire:

```text
non-blocking
```

No slot:

```text
Protocol Intelligence busy
→ Admin 429 concurrency_limit
→ Retry-After: 1
```

This is in addition to existing shared:

```text
AdminQueryExecutionControls
```

Per-request NI-03 projection-read deadline:

```text
5 seconds
```

Effective deadline:

```text
min(
    remaining shared Admin deadline,
    5 seconds from NI-03 read start
)
```

Do not extend the shared deadline.

The 5-second limit must be an actual cancellable SQLite-read bound, not merely an after-the-fact elapsed-time check.

Use bounded SQLite progress interruption or an equivalent existing safe pattern.

Deadline expiry:

```text
→ Admin 503 query_deadline
```

Ordinary SQLite busy/store failure:

```text
→ Admin 503 source_unavailable
```

---

# 11. BOUNDED NI-02B READ EXTENSION

Only NI-02B source file authorized for semantic read extension:

```text
app/network_metadata_projection/read_service.py
```

Do NOT modify NI-02B schema/models/writer/service/checkpoint/retention.

Add one narrow product-safe same-snapshot read method.

Implementation-contract method name:

```text
read_protocol_evidence_snapshot(
    site_id,
    device_id,
    client_mac,
    from_utc,
    to_utc,
    *,
    max_rows,
    deadline
)
```

This method is internal and MUST return only the data needed by NI-03:

```text
runtime_state

projection binding:
    binding_state
    bound_device_id

narrow fact rows:
    edge_id
    event_at
    source_event_family
```

No endpoint payload, IP, port, SNI, DNS name, peer details or raw Registry row.

One call MUST use one SQLite read transaction/snapshot for:

```text
projection_runtime_state
+
projection_site_mac_bindings
+
eligible edge facts
```

Forbidden:

```text
get_status() in one snapshot
then list_edges_*() in another snapshot
```

Validation:

```text
exact Site
canonical UUID device_id
canonical MAC
exact bounded time window
max_rows=20000
```

Edge filter after authoritative binding:

```text
site_id = requested Site
client_mac = requested canonical MAC
event_at >= from_utc
event_at < to_utc
```

Use the existing index-compatible order/path.

Read at most:

```text
20001 narrow rows
```

to detect overflow.

If 20,001st row exists:

```text
NO partial summary
→ source_unavailable
```

Exact 20,000 is allowed.

Read requirements remain:

```text
mode=ro
query_only=ON
foreign_keys=ON
busy_timeout=500ms
short transaction
```

Never:

```text
VACUUM
checkpoint WAL
TRUNCATE WAL
obtain writer lock
write projection_runtime_state
```

Deadline cancellation must close the snapshot.

---

# 12. UNKNOWN PROTOCOL FAMILY

NI-03 admits exactly:

```text
dns
tls
quic
```

Any retained eligible row with another `source_event_family` inside the selected authoritative Device window is:

```text
projection evidence integrity unavailable
```

Result:

```text
HTTP 503 source_unavailable
```

Do not ignore it silently and do not map it to `unknown`.

TCP/UDP are never Product Protocols.

---

# 13. ADMIN CONFIGURATION — POST ADMIN-SETTINGS-06 BASELINE

Add deployment-owned feature flag:

```text
WEB_ADMIN_DEVICE_PROTOCOL_INTELLIGENCE_ENABLED
```

Repository default:

```text
false
```

Exact accepted textual values:

```text
true
false
```

Integrate through the existing main-process configuration pipeline:

```text
process environment
→ app/config.py
→ app/settings.py:get_settings()
→ settings bootstrap snapshot
→ existing AdminFeaturePlanV1 composition for REGISTERED features
→ app/admin_web/config.py
→ Admin runtime composition
```

Required source changes remain:

```text
app/config.py
app/settings.py
app/admin_web/config.py
.env.example
```

Add exact internal settings name:

```text
web_admin_device_protocol_intelligence_enabled
```

`AdminWebConfig` gains:

```text
device_protocol_intelligence_enabled: bool
```

Important ADMIN-SETTINGS-06 compatibility rule:

```text
WEB_ADMIN_DEVICE_PROTOCOL_INTELLIGENCE_ENABLED
is NOT a Settings → Features managed key in NI-03.
```

Therefore Coder MUST NOT modify:

```text
app/settings_control/definitions.py
app/settings_control/features.py
SettingsDefinitionRegistry
AdminFeaturePlanV1 registry
Settings Features API/UI
Settings mutation domains/schema
```

The new flag is preserved as an ordinary deployment-owned setting outside the
17 ADMIN-SETTINGS-06 managed feature definitions.

`AdminFeaturePlanV1.composition_settings()` already preserves unrelated settings.
NI-03 must consume the resulting value without rebuilding or extending the
feature plan.

Exact outer-gate semantics:

```text
WEB_ADMIN_ENABLED=false
+
WEB_ADMIN_DEVICE_PROTOCOL_INTELLIGENCE_ENABLED=true
→ Admin remains disabled
→ NI-03 remains inert
→ no projection read
→ no NI-03 composition
→ NOT a configuration error merely because the preference is true
```

When Admin is enabled:

```text
NI-03 flag=false
→ feature absent / API 404

NI-03 flag=true
→ optional NI-03 composition is attempted
```

This flag is NOT:

```text
Admin Settings writable key
Settings Store definition
Settings generation key
Settings mutation API field
AdminFeaturePlanV1 feature node
```

No Settings schema/generation change.

---

# 14. NI-02B CONFIGURATION HANDOFF — R1 MANDATORY

When NI-03 feature is enabled, the main Admin process obtains NI-02B configuration only through:

```text
app.network_metadata_projection.config.projection_config_from_env()
```

No new aliases.

Forbidden:

```text
PROTOCOL_INTELLIGENCE_PROJECTION_DB_PATH
PROTOCOL_INTELLIGENCE_PROJECTION_ENABLED
PROTOCOL_INTELLIGENCE_PROJECTION_MAX_DB_BYTES
```

No route/request-time:

```text
os.getenv()
EnvironmentFile parsing
systemctl
systemd D-Bus
PID lookup
```

Exact authorities remain:

```text
NETWORK_METADATA_PROJECTION_ENABLED
NETWORK_METADATA_PROJECTION_DB_PATH
NETWORK_METADATA_PROJECTION_MAX_DB_BYTES
```

from:

```text
/etc/captive-portal/network-metadata-projection.env
```

via existing:

```text
projection_config_from_env()
```

Semantics:

```text
ProjectionConfig.enabled=false
→ NI-02B disabled for NI-03
→ DO NOT open old DB
→ NI-03 503 source_unavailable

projection_config_from_env validation failure
→ NI-03 dependency unavailable
→ Portal/Admin core still start

enabled=true + valid config
→ compose read-only projection reader
→ runtime store availability evaluated safely by the read path
```

Feature OFF:

```text
no NI-03 semantic reader composition
no hidden projection request
no Device Card section
API 404
```

---

# 15. RUNTIME COMPOSITION — CURRENT BASELINE

Modify bounded Admin runtime composition only:

```text
app/admin_web/runtime.py
```

Current baseline already requires:

```text
create_admin_web_runtime(..., feature_plan=...)
```

and applies:

```text
settings = feature_plan.composition_settings(settings)
```

Coder MUST preserve that ADMIN-SETTINGS-06 architecture.

Do NOT:

```text
create another feature plan
extend AdminFeaturePlanV1 for NI-03
bypass feature_plan.composition_settings()
re-run Settings resolution
read Settings Store at request time
```

NI-03 is optional.

When the composed Admin config is:

```text
WEB_ADMIN_ENABLED=true
AND
WEB_ADMIN_DEVICE_PROTOCOL_INTELLIGENCE_ENABLED=true
```

compose:

```text
ProjectionConfig
via projection_config_from_env()

DeviceNetworkMetadataReadService(
    db_path=projection_config.db_path,
    enabled=projection_config.enabled,
    max_db_bytes=projection_config.max_db_bytes
)

DeviceProtocolIntelligenceReadService(...)
```

Then pass the semantic service as an optional dependency into the existing:

```text
AdminQueryService
```

Do not create a second Admin query-service stack.

If Admin is disabled, NI-03 must not compose regardless of its raw deployment
preference.

Any NI-03 config/composition failure MUST NOT make existing Admin runtime
unavailable.

Protected baseline must still work:

```text
Guest Portal
CAPPORT
Authorization
existing Admin
Settings → Features
existing Device page
existing Device Current Context
```

No projection DB open when canonical projection config is disabled.

---

# 16. ADMIN QUERY SERVICE

Modify:

```text
app/admin_web/query_service.py
```

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
admin.read.device authorization
canonical device_id validation
existing Device gateway lookup
exact Site membership
server evaluated_at_utc
shared Admin query slot/deadline
call to DeviceProtocolIntelligenceReadService
strict serialization/error translation
```

Order inside accepted Admin flow:

```text
authorize Site/capability
→ validate canonical device_id
→ existing Device gateway lookup in exact Site
→ if Device absent: not_found
→ obtain canonical_mac from existing Device row
→ call NI-03 semantic service
```

No direct Registry call for NI-03 binding.

No SQLite in AdminQueryService.

No NI-01/NI-02A call.

If NI-03 semantic dependency is unavailable after Device exists:

```text
AdminQueryUnavailable
```

Map semantic exceptions narrowly:

```text
NI-03 validation
→ AdminQueryValidationError

NI-03 semaphore busy
→ AdminQueryBusy

NI-03 local/read deadline
→ AdminQueryDeadline

projection/integrity/store/row-limit unavailable
→ AdminQueryUnavailable
```

Unexpected exception:

```text
AdminQueryError / sanitized 500 path
```

No private reason to browser.

---

# 17. STRICT ADMIN SERIALIZER

Create:

```text
app/admin_web/device_protocol_intelligence_serialization.py
```

Purpose:

```text
DeviceProtocolSummaryV1
→ exact public dict
```

The serializer must enforce:

```text
exact V1 fields/enums
canonical timestamps
protocol vocabulary
no extra private fields
no NaN/non-finite values
historical_window_completeness_claimed=false
```

Serialization error:

```text
→ AdminQueryUnavailable
or exact existing sanitized integrity path
→ never partial DTO
```

Do not serialize dataclass `__dict__` blindly.

---

# 18. ADMIN API

Add exact endpoint:

```text
GET /admin/api/v1/sites/<site_id>/devices/<device_id>/protocol-intelligence
```

No POST/PUT/PATCH/DELETE.

No query parameters.

No request body.

Any query parameter:

```text
400 invalid_request
```

A non-empty GET request body:

```text
400 invalid_request
```

API version for BOTH success and error envelopes:

```text
admin.device.protocol-intelligence.v1
```

Success shape exactly:

```json
{
  "api_version": "admin.device.protocol-intelligence.v1",
  "request_id": "<uuid>",
  "site_id": "<site_id>",
  "result": { "...DeviceProtocolSummaryV1..." },
  "page": null
}
```

Endpoint serialized response maximum:

```text
16384 bytes
```

Exceed:

```text
503 response_too_large
```

Headers:

```text
Cache-Control: no-store
Pragma: no-cache
```

No ETag/CORS expansion.

Error mapping:

```text
400 invalid_request
→ bad Site/device syntax
→ query parameter present
→ request body present

401 authentication_required
→ missing/expired Admin session

403 site_forbidden
→ Site not allowed
→ admin.read.device denied

404 not_found
→ Device absent from exact Site
→ NI-03 feature disabled

429 concurrency_limit
Retry-After: 1
→ shared or NI-03 reader slot unavailable

503 query_deadline
→ shared/NI-03 read deadline

503 source_unavailable
→ canonical NI-02B disabled
→ projection DB unavailable/untrusted
→ integrity unavailable
→ unknown runtime enum
→ 20,001 row overflow

503 response_too_large
→ >16 KiB

500 internal_error
→ unexpected sanitized failure
```

Modify existing route response helpers only as narrowly as necessary to support a route-specific API version/size cap.

Existing endpoints MUST retain their existing API versions and behavior.

---

# 19. ADMIN PERMISSION / SITE BOUNDARY

No new capability.

Exact permission:

```text
admin.read.device
```

No:

```text
admin.read.protocol
admin.read.network_intelligence
```

All requests remain:

```text
site_id + device_id
```

No default-Site fallback.

No global device query.

No cross-Site MAC query.

No cross-Site merge.

A `device_id` existing on another Site does not make it visible on requested Site.

---

# 20. DEVICE CARD

Modify:

```text
app/admin_web/pages.py
app/admin_web/templates/admin/base.html
app/admin_web/templates/admin/device.html
app/admin_web/static/admin.css   # only bounded NI-03 presentation if needed
```

Render the section only when:

```text
feature=true
AND
principal has admin.read.device for the current Site
AND
page=device
```

No section:

```text
→ no NI-03 JS request
```

Exact title:

```text
Network / Protocol Intelligence
```

Exact subtitle:

```text
Recent protocol evidence derived from device-relative network metadata.
```

Display exactly:

```text
Recent Protocols
Last Protocol Observation
Freshness
Source coverage
Attribution coverage
Last evaluated
manual Refresh button
```

DOM IDs exactly:

```text
device-protocol-intelligence

device-protocol-state
device-protocol-state-title
device-protocol-state-message

device-protocol-content

device-protocol-refresh
```

No raw DTO in `data-*`.

No raw edge table.

---

# 21. DEVICE CARD WORDING

Freshness labels:

```text
fresh       → Fresh
recent      → Recent
stale       → Stale
unavailable → Unavailable
```

Coverage labels:

```text
usable      → Available
degraded    → Degraded
unavailable → Unavailable
unknown     → Unknown
```

Good coverage + empty evidence:

Title:

```text
No recent protocol evidence
```

Message:

```text
No DNS, TLS or QUIC evidence is retained for this Device
in the last 24 hours. This does not prove there was no network activity.
```

Empty + insufficient source/attribution coverage:

Title:

```text
Insufficient coverage
```

Message:

```text
Recent protocol evidence cannot be determined reliably from the
currently available Network Intelligence coverage.
```

Identity not authoritative:

Title:

```text
Device network identity binding pending
```

Message:

```text
Device-relative protocol evidence is not yet authoritatively linked
to this Device for the current Site.
```

Temporary request/store/API failure:

```text
Protocol intelligence temporarily unavailable
```

Stale evidence:

```text
Stale evidence
```

Do not use service names.

Do not say:

```text
No network activity
No services used
```

---

# 22. DEDICATED FRONTEND MODULE

Create:

```text
app/admin_web/static/device_protocol_intelligence.js
```

Load it ONLY for the Device page when the NI-03 section is enabled.

It consumes only:

```text
admin.device.protocol-intelligence.v1
```

It must use safe DOM APIs:

```text
textContent
createElement
replaceChildren
```

Do not render server strings through unsafe HTML.

No product semantics are recalculated in JS beyond strict DTO validation/presentation.

## 22.1. Initial / automatic polling

Initial request:

```text
immediate
```

Normal auto poll:

```text
60 seconds
```

Start/schedule only while:

```text
Device page active
section exists
document visible
page not stopped
session not terminal
```

Stop on:

```text
document.hidden
pagehide
401
403
404
```

Visibility return:

```text
if >=60s elapsed since eligible request
→ immediate refresh
else
→ schedule remaining interval
```

## 22.2. Browser request concurrency

Maximum:

```text
1 NI-03 request in flight
```

Manual click during request:

```text
no parallel request
set one pending manual refresh
after active request completes:
run one immediate follow-up
```

Five clicks still produce exactly one pending follow-up.

The page-level existing Refresh button and section Refresh button MUST use the same NI-03 coordinator.

They must not create two NI-03 requests.

## 22.3. Timeout / retry

Request timeout:

```text
10 seconds
```

Use:

```text
AbortController
```

Automatic failure backoff:

```text
1st consecutive failure → 60s
2nd                     → 120s
3rd+                    → 300s
success                  → reset to 60s
```

Manual Refresh bypasses waiting delay but never the one-in-flight rule.

## 22.4. Last-good render

After temporary request failure:

```text
last successful response age < 900s
→ may remain rendered
→ visibly mark temporary unavailable/stale-request state
```

At:

```text
age >= 900s from evaluated_at_utc
```

clear current protocol data and render unavailable state.

This 15m client display bound is NOT protocol freshness.

## 22.5. Browser persistence/privacy

MUST NOT persist NI-03 response in:

```text
localStorage
sessionStorage
IndexedDB
cookies
URL/query
history state
data-* raw JSON
```

Allowed:

```text
in-memory JS state
rendered DOM while page is active
```

No new NI-03 browser telemetry channel.

---

# 23. EXECUTION DIRECTIVE — NO PRE-CODE PLAN

Coder MUST NOT return a plan before implementation.

The required sequence is exactly:

```text
1. verify BASE_HEAD and BASE_TREE;

2. create/use the implementation branch/worktree if not already prepared;

3. inspect only the exact current source necessary to execute this TASK;

4. implement the exact contracts in §§4–22 and §§24–38;

5. add the exact focused tests required by this TASK;

6. run only the authorized focused test commands in §33;

7. build reproducible uncommitted candidate identity per §39;

8. return the Coder Handoff in §40;

9. HOLD for Tech Lead source review.
```

Implementation inspection is allowed only to map the already-decided contract
onto the current codebase.

It is NOT authorization to:

```text
research alternative designs
propose a different API
change DTOs
change thresholds
change file ownership
change persistence model
change concurrency model
change deployment ownership
expand scope
```

No preliminary Coder response is required.

---

# 24. EXPECTED FILE SCOPE

Expected/authorized production source scope:

```text
M .env.example
M app/config.py
M app/settings.py

M app/network_metadata_projection/read_service.py

A app/network_protocol_intelligence/__init__.py
A app/network_protocol_intelligence/models.py
A app/network_protocol_intelligence/read_service.py

M app/admin_web/config.py
M app/admin_web/runtime.py
M app/admin_web/query_service.py
A app/admin_web/device_protocol_intelligence_serialization.py
M app/admin_web/routes.py
M app/admin_web/pages.py
M app/admin_web/templates/admin/base.html
M app/admin_web/templates/admin/device.html
A app/admin_web/static/device_protocol_intelligence.js
M app/admin_web/static/admin.css
    only if minimal presentation rules are required

A deploy/network-metadata-projection/
  captive-portal-network-metadata-projection-read.conf

M deploy/network-metadata-projection/README.md
```

If a listed file does not actually need modification, do not touch it merely to match the list.

ADMIN-SETTINGS-06 files explicitly NOT owned by NI-03:

```text
app/settings_control/definitions.py
app/settings_control/features.py
app/settings_control/activation.py
app/settings_control/bootstrap.py
app/settings_control/repository.py
app/settings_control/resolver.py
app/settings_control/services.py
app/settings_control/validation.py
app/settings_control/value_validation.py

app/admin_web/static/features_settings.js
app/admin_web/templates/admin/settings_features.html
```

Any additional production file outside the authorized NI-03 conceptual
boundaries:

```text
STOP
→ report exact reason
→ no unauthorized edit
```

Tests may be added/modified only under:

```text
tests/network_protocol_intelligence/
tests/network_metadata_projection/
tests/admin_web/
```

for this TASK.

No modification to existing tests solely to weaken expected behavior.

---

# 25. DEPLOYMENT ARTIFACT — EXACT

Add repository artifact:

```text
deploy/network-metadata-projection/
captive-portal-network-metadata-projection-read.conf
```

Exact content:

```ini
[Service]
EnvironmentFile=-/etc/captive-portal/network-metadata-projection.env
```

Document production install destination:

```text
/etc/systemd/system/captive-portal.service.d/
20-network-metadata-projection-read.conf
```

The repository artifact MUST NOT install itself.

Application code MUST NOT write `/etc/systemd/system`.

No production `systemctl` by Coder.

README must document the activation collision gate:

```text
1. /etc/default/captive-portal MUST NOT independently define
   NETWORK_METADATA_PROJECTION_*.

2. For any other key existing in BOTH:
   /etc/default/captive-portal
   and
   /etc/captive-portal/network-metadata-projection.env

   the effective values MUST be semantically identical.

3. Any mismatch:
   ACTIVATION=HOLD.
```

Do not add a second projection env file.

---

# 26. APPLICATION / LOGGING PRIVACY — R1

NI-03 application-generated logs, metrics and telemetry MUST NOT contain:

```text
device_id
MAC
raw IP
port
DNS name
SNI
edge payload
protocol-history list for one Device
raw Registry row
NI-02A binding ID
```

Allowed bounded application diagnostic context:

```text
request_id
Site ID
safe failure category
HTTP status class
row-count bucket
duration bucket
```

On 4xx/5xx:

```text
do not interpolate full request path
do not log device_id
```

Do not add `device_id` metric labels.

No full DTO log.

No raw exception body to browser.

Existing reverse-proxy boundary is explicitly accepted:

```text
Nginx web_admin_safe
may contain site_id/device_id inside existing $uri
```

This TASK requires:

```text
NO Nginx route change
NO Nginx log-format change
NO endpoint rewrite
NO redaction layer
NO Nginx reload
```

Do not attempt to “fix” infrastructure logging in application code.

---

# 27. FAILURE ISOLATION

Inject/cover failures for:

```text
projection config disabled
projection env/config invalid
projection DB absent
projection DB schema invalid
SQLite busy
unknown projection runtime state
attribution_unavailable
source_unavailable
capacity_waiting_reader
capacity_halted
blocked_conflict
identity pending
20,001 row overflow
NI-03 semaphore full
5s deadline
browser timeout
```

Prove no regression to relevant code/runtime contracts:

```text
Guest Portal
CAPPORT
Authorization
existing Admin pages
existing Device Card
existing Device Current Context
NI-02B writer semantics
```

No fallback query to NI-01/NI-02A/Registry.

---

# 28. REQUIRED TEST CASES — SEMANTICS

At minimum implement deterministic cases:

## Protocols

```text
DNS edge inside 60m → Recent DNS
TLS edge inside 60m → Recent TLS
QUIC edge inside 60m → Recent QUIC

multiple same-protocol edges
→ one item
→ latest timestamp

TCP/UDP transport
→ never Product Protocol

unknown source_event_family
→ unavailable / no partial DTO
```

## Time

```text
evaluated_at-3600s exact → Recent
1 microsecond before     → not Recent

summary_from exact       → included
before summary_from      → excluded

future edge event_at >= evaluated_at
→ unavailable
```

## Freshness

```text
age 0      → fresh
age 300s   → fresh
>300..3600 → recent
>3600..86400 → stale
no last observation → unavailable
```

Then exact coverage caps.

## Identity

```text
authoritative exact Device binding → scan allowed

authoritative different device_id
→ unavailable

not_yet_registry_resolved
registry_unavailable
no binding
→ identity_pending
→ no edge scan

late authoritative binding
→ retained edges visible next request
```

## Coverage

```text
usable + fresh edge → fresh

attribution_unavailable + fresh edge
→ 200 / recent

source_unavailable + fresh edge
→ 200 / stale

capacity_halted + fresh edge
→ 200 / recent

usable + zero facts
→ empty
→ never "no network activity"

degraded coverage + zero facts
→ insufficient coverage
```

## Row bound

```text
20,000 → allowed
20,001 → source_unavailable
no truncation
```

## Site

```text
Site A cannot read Site B
wrong Site Device → 404
unauthorized Site/capability → 403
no default fallback
```

---

# 29. REQUIRED TEST CASES — API / UI

API:

```text
feature OFF → 404
feature ON + success → exact v1 envelope
query parameter → 400
GET body → 400
invalid device UUID → 400
unauthenticated → 401
forbidden Site/capability → 403
Device absent → 404
shared/NI03 concurrency → 429 + Retry-After:1
deadline → 503 query_deadline
projection disabled/store invalid → 503 source_unavailable
response >16KiB → 503 response_too_large
unexpected → sanitized 500
no-store/no-cache headers
```

UI:

```text
feature OFF → section absent + no request

feature ON + allowed
→ exact section/title/fields

Recent Protocols render
Last Protocol Observation render
fresh/recent/stale/unavailable render
source/attribution coverage render
Last evaluated render

manual Refresh works
auto poll 60s
one request in flight max
5 manual clicks during flight
→ one follow-up only

hidden tab → no polling
pagehide → stop
visibility return → bounded resume

failure backoff:
60 / 120 / 300
success resets to 60

last-good <15m retained with warning
>=15m cleared/unavailable

401/403/404 → terminal stop
```

Frontend validation must reject malformed/extra/noncanonical DTO shapes instead of rendering private/unknown fields.

Use real Node-based frontend test style consistent with existing Admin frontend tests.

No `innerHTML` for API-derived strings.

---

# 30. SAME-SNAPSHOT / WRITER COEXISTENCE TEST

Add a focused Linux-capable disposable-store integration test proving:

```text
one request reads:
runtime state + binding + fact rows
from one SQLite snapshot
```

and:

```text
2 simultaneous NI-03 readers
+
normal NI-02B writer activity
```

does not cause:

```text
writer permanent failure
blocked_conflict
false capacity_halted
checkpoint corruption
```

Ordinary short WAL reader contention is acceptable.

The test must use disposable test stores only.

No production DB.

---

# 31. CONFIG / FEATURE-PLAN HANDOFF TESTS

Required source/config tests:

```text
NI-03 feature defaults false

WEB_ADMIN_ENABLED=false
+
NI-03 deployment preference=true
→ Admin remains disabled
→ no NI-03 composition
→ no configuration failure solely from the NI-03 preference

NI-03 feature=false
→ no NI-03 composition

NI-03 feature=true
+
canonical projection enabled=false
→ Admin/core runtime remains active
→ NI-03 unavailable
→ old projection DB must not be opened

NI-03 feature=true
+
projection config validation failure
→ Admin/core remains active
→ NI-03 unavailable

NI-03 feature=true
+
valid canonical projection config
→ uses ProjectionConfig.db_path
→ no NI-03 DB-path alias
```

ADMIN-SETTINGS-06 compatibility tests must prove:

```text
existing AdminFeaturePlanV1 continues to manage only its registered features;

NI-03 does not appear in Settings → Features;

NI-03 does not add a SettingsDefinitionRegistry row;

existing Settings feature composition remains unchanged;

feature_plan object passed into Admin runtime remains the existing startup plan.
```

Deployment artifact test/document verification must prove exact EnvironmentFile
line.

Production env collision itself is NOT to be mutated by Coder.
It is a later Tech Lead/Deploy gate.

---

# 32. PRIVACY TESTS

Prove API/HTML/JS/application logs/metrics do not expose:

```text
DNS name
SNI
remote IP
remote port
MAC
edge_id
raw Registry row
NI-02A binding ID
raw projection reason
device_id in application-generated log/metric fields
```

Expected and accepted exception:

```text
API route URL contains device_id
Nginx existing $uri access log may record it
```

This expected infrastructure occurrence is NOT an NI-03 privacy failure.

Prove NI-03 introduces no:

```text
$request_uri logging
query-string logging
body logging
Authorization header logging
Cookie logging
```

No Nginx configuration change is part of the candidate.

---

# 33. CODER-AUTHORIZED TEST COMMANDS

Coder may run only focused task tests and direct shared-file regressions.

Expected Windows/canonical venv class of commands:

```text
python -m pytest -q \
  tests/network_protocol_intelligence \
  tests/network_metadata_projection/<NI03-read-extension-tests> \
  tests/admin_web/test_device_protocol_intelligence.py \
  tests/admin_web/test_device_protocol_intelligence_frontend.py \
  tests/admin_web/test_config.py \
  tests/admin_web/test_runtime.py \
  tests/admin_web/test_routes.py \
  tests/admin_web/test_query_service.py \
  tests/admin_web/test_device_current_context.py \
  tests/admin_web/test_device_current_context_frontend.py \
  tests/settings_control/test_features_stage6.py
```

If Windows cannot prove the native SQLite/POSIX concurrency/deadline path,
run the same relevant focused subset in the existing WSL/Linux Lab.

Also authorized:

```text
python -m compileall -q
exact changed Python packages/files

git diff --check
```

Do NOT run on your own initiative:

```text
full repository pytest
Central Lab official gate
production tests
live network capture
Omada mutation
production SQLite tests
production systemd tests
```

Tech Lead owns broader acceptance after candidate handoff.

If one existing focused regression outside the list is directly required because a shared function was changed, STOP before broad expansion and state the exact proposed test.

---

# 34. DATABASE / MIGRATION

Exact:

```text
DATABASE MIGRATION=NONE
NEW DATABASE=NO
SCHEMA CHANGE=NO
NI-03 SUMMARY PERSISTENCE=NO
```

No changes to:

```text
network_metadata_projection.sqlite3 schema
network_metadata.sqlite3 schema
network_attribution.sqlite3 schema
visitor_registry.sqlite3 schema
```

No migration helper.

No schema version bump.

---

# 35. DEPLOYMENT / ACTIVATION — NOT CODER WORK

Coder must NOT perform any of these.

Future Tech Lead/Owner production activation will separately follow R1:

```text
1. verify exact accepted HEAD/TREE
2. verify NI-02B existing env ownership
3. install systemd drop-in
4. collision gate
5. daemon-reload
6. keep NI-03 feature OFF
7. restart captive-portal
8. prove protected baseline
9. then separately set feature true
10. restart captive-portal
11. prove API/Device Card
12. prove NI-02B unaffected
13. production smoke/privacy/concurrency
```

Coder must only provide repository artifacts needed by this later procedure.

---

# 36. PRODUCTION ROLLBACK — CONTRACT ONLY

Do not execute.

Fast product rollback:

```text
WEB_ADMIN_DEVICE_PROTOCOL_INTELLIGENCE_ENABLED=false
restart captive-portal.service
verify protected baseline
```

Full NI-03 infrastructure rollback if later required:

```text
feature OFF
remove installed 20-network-metadata-projection-read.conf
daemon-reload
restart captive-portal.service
leave NI-02B env/service/DB unchanged
```

No DB rollback.

No NI-02B restart required.

---

# 37. FORBIDDEN SOURCE CHANGES

Do NOT modify:

```text
app/network_metadata/schema.py
app/network_metadata/repository.py
app/network_metadata/service.py

app/network_attribution/*
except no files at all for NI-03

app/network_metadata_projection/schema.py
app/network_metadata_projection/repository.py
app/network_metadata_projection/service.py
app/network_metadata_projection/retention.py
app/network_metadata_projection/cli.py
app/network_metadata_projection/models.py

app/visitor_registry/*
app/visit_lifecycle/*
app/device_fingerprint/*

app/settings_control/*
app/analytics/runtime.py
run.py

CAPPORT/Auth/Omada providers

Nginx production config
systemd production files
```

If tests appear to require changing one of these production modules:

```text
STOP
→ report contradiction
→ do not patch it
```

---

# 38. NO HIDDEN SCOPE EXPANSION

Explicitly prohibited “while here” changes:

```text
refactor Admin framework
rewrite admin.js
replace current Device Current Context coordinator
rename existing API versions
clean unrelated CSS
change analytics query framework
create generic network-intelligence framework
add service recognition stubs
add new permissions
add NI-03 to Settings → Features
modify AdminFeaturePlanV1 / SettingsDefinitionRegistry
add Settings control
upgrade SQLite architecture
change NI-02B resource priority
change retention
change poll intervals
```

Reuse existing patterns where compatible; do not generalize beyond NI-03 needs.

---

# 39. CANDIDATE IDENTITY BEFORE COMMIT

Implementation must remain uncommitted until Tech Lead source review.

Coder must produce a complete candidate identity.

Required:

```text
BASE_HEAD
BASE_TREE
HEAD_REMAINS=<BASE_HEAD>

BRANCH
WORKTREE

CANDIDATE_TREE

PATCH_PATH
PATCH_BYTES
PATCH_SHA256

PATCH_FORMAT=
git diff --binary --full-index BASE

PATCH_RECONSTRUCTION=PASS
PATCH_REVERSE_APPLY_CHECK=PASS

WORKTREE_STATUS
INDEX_STAGED_FILES
```

Use an external temporary Git index if needed to compute candidate tree without staging the actual worktree.

Do not fabricate a commit just to obtain a tree.

---

# 40. CODER HANDOFF FORMAT

After implementation and authorized focused tests, return:

```text
# TASK-DTI-NI-03 — CODER HANDOFF

STATUS=
REVIEW CANDIDATE / HOLD FOR TECH LEAD SOURCE REVIEW

BASELINE VERIFIED
...

IMPLEMENTED
...

NOT IMPLEMENTED
...

FILES INSPECTED
...

FILES CHANGED
...

ARCHITECTURE INVARIANTS
...

CONFIG HANDOFF RESULT
...

SAME-SNAPSHOT RESULT
...

PROTOCOL SEMANTICS RESULT
...

COVERAGE/FRESHNESS RESULT
...

API RESULT
...

FRONTEND RESULT
...

PRIVACY RESULT
...

SQLITE WRITER-COEXISTENCE RESULT
...

TESTS EXECUTED
...

TEST RESULTS
...

UNVERIFIED AREAS
...

KNOWN RISKS
...

CANDIDATE IDENTITY / PATCH
...

REPOSITORY ACTIONS
COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOYMENT=NO
PRODUCTION_ACTION=NO

NEXT ACTION=
TECH LEAD SOURCE REVIEW
```

Coder MUST NOT claim production acceptance.

---

# 41. STOP CONDITIONS FOR CODER

Immediately STOP and return to Tech Lead if:

```text
baseline HEAD/TREE differs from the authoritative v3 baseline before work starts

accepted main changes materially during implementation

same-snapshot requirement cannot be met without NI-02B schema/writer change

5s cancellable read cannot be implemented inside allowed boundary

current index cannot support bounded Site+MAC+time read without schema/index change

Admin runtime cannot consume ProjectionConfig without another config authority

existing query framework makes NI-03 require a new architecture-level dependency

required UI behavior would require rewriting shared Admin refresh semantics

privacy contract cannot be satisfied in application layer as scoped

20,000 row bound is impossible without changing accepted semantics

existing tests contradict Architecture v1/v1-R1

any need appears for NI-04 service recognition

any need appears for production access/mutation
```

Do not choose a workaround that changes architecture.

---

# 41A. CODER ROLE INVARIANT

Permanent execution rule for this TASK:

```text
Technical Lead decides.
Coder implements.
Coder does not design.
Coder does not plan architecture.
Coder does not research alternatives.
Coder does not publish repository changes without later authorization.
```

The Coder may make only ordinary local coding choices that do not alter any
specified contract, such as private helper naming or equivalent internal
decomposition inside an explicitly authorized file.

If even such a local choice would affect a public DTO, API behavior, database
semantics, concurrency, security, deployment, privacy, or ownership boundary:

```text
STOP → TECH LEAD
```

---

# 42. TECH LEAD ACCEPTANCE EXPECTATION

A candidate is eligible for Tech Lead source review only if:

```text
P0=0
P1=0

architecture semantics exact

feature default OFF

no migration/schema change

same-snapshot proof present

20,000/20,001 proof present

freshness/coverage boundaries proven

Site isolation proven

API exact

frontend coordinator proven

privacy proven

existing Device Current Context regression clean

NI-02B writer coexistence focused proof clean

candidate identity reproducible

no repository publication
no production action
```

Tech Lead will independently decide any broader integration/regression gate.

---

# 43. FINAL TASK STATUS

```text
TASK=
TASK-DTI-NI-03

TITLE=
Protocol Intelligence + Device Card P1

ARCHITECTURE=
PASS
v1 + v1-R1

BASELINE_RECONCILIATION=
PASS

BASELINE_MOVEMENT=
ADMIN-SETTINGS-06 / PR #196

BASE_HEAD=
51deead342bd821b5c46fb75a7ceef37bef63e7c

BASE_TREE=
7b6cfa20c23c097e87059ca12a593f697f0a36a2

OPEN_P0=
0

OPEN_P1=
0

OPEN_P2=
0

CODER_PRE_CODE_PLAN=
NOT REQUIRED

CODER_IMPLEMENTATION=
AUTHORIZED / GO

COMMIT=
NOT AUTHORIZED

PUSH=
NOT AUTHORIZED

PR=
NOT AUTHORIZED

MERGE=
NOT AUTHORIZED

DEPLOYMENT=
NOT AUTHORIZED

PRODUCTION_CHANGE=
NO
```
