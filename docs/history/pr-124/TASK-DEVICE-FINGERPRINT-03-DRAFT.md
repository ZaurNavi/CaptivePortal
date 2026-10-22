# TASK-DEVICE-FINGERPRINT-03-DRAFT

## Portal UA / Client Hints Evidence

**Project:** CaptivPortal  
**Program:** Device Fingerprint  
**Parent foundation:** `TASK-DEVICE-FINGERPRINT-01`  
**Network evidence predecessor:** `TASK-DEVICE-FINGERPRINT-02`  
**Prepared:** 2026-09-15  
**Status:** `ARCHITECT DRAFT — FOR TECHLEAD10 SOURCE / ARCHITECTURE REVIEW`  
**Implementation-ready:** `NO`  
**Coder:** `HOLD`  
**Implementation authorization:** `NOT GRANTED`  
**Production deploy / activation:** `NOT AUTHORIZED`

---

# 0. Architect Control Gate

```text
DEVICE-FINGERPRINT-00 = CLOSED / PASS
DEVICE-FINGERPRINT-01 = IMPLEMENTED / MERGED
DEVICE-FINGERPRINT-02 = IMPLEMENTED / MERGED
DEVICE-FINGERPRINT-03 = THIS DRAFT

CLASSIFICATION = NOT IN SCOPE
DEVICE CARD / UI = NOT IN SCOPE
PACKET CAPTURE = NOT IN SCOPE
HIGH-ENTROPY CLIENT HINTS = DEFERRED
JAVASCRIPT FINGERPRINTING = FORBIDDEN

CODER = HOLD
IMPLEMENTATION = NOT AUTHORIZED
BRANCH = NOT AUTHORIZED
COMMIT = NOT AUTHORIZED
PUSH = NOT AUTHORIZED
PR = NOT AUTHORIZED
DEPLOY = NOT AUTHORIZED
ACTIVATION = NOT AUTHORIZED
```

---

# 1. Fresh Repository Baseline

```text
repository = ZaurNavi/CaptivePortal

HEAD =
479ed77e713c449850cfc5d4dd972b7c6429e64a

TREE =
ca2f404d0fc38e1fe82e40085f29684f9c142447
```

This HEAD contains merged `TASK-DEVICE-FINGERPRINT-02`.
Task-01 and Task-02 are consumed as existing foundations.
TechLead10 must perform a fresh source rebind before implementation-ready FINAL.

---

# 2. Goal

```text
existing portal HTTP request
→ bounded transient UA/low-entropy-CH parser
→ normalized P1 portal evidence
→ non-blocking in-memory handoff
→ asynchronous HTTPS/Bearer Task-01 ingest
→ existing canonical evidence DB
```

Task-03 is evidence acquisition only. It is not classification.

---

# 3. Canonical Research Facts Consumed

Portal ingress:

```text
nginx :80/:443
→ CaptivPortal backend 127.0.0.1:8088
```

Application visibility proven for:

```text
User-Agent
sec-ch-ua
sec-ch-ua-platform
sec-ch-ua-mobile
```

Controlled Android evidence proved that normalized portal evidence can expose:

```text
platform = Android
mobile = true
runtime/browser family = Chromium / Android WebView
WebView/captive context = observable
OS major = observable when explicitly present
model family = observable when explicitly present
```

Permanent rule:

```text
raw User-Agent = transient evidence
raw User-Agent != permanent authoritative device field
```

---

# 4. Exact HTTP Source Boundary

Task-03 collects only from real portal-entry paths:

```text
A. Omada External Portal
GET /

B. CAPPORT portal login
create_capport_blueprint(...).capport_login()
```

Both converge into:

```text
PortalEntryHandler.prepare_portal()
```

which owns AuthSession create/reuse and AuthWorker scheduling.

---

# 5. Explicitly Excluded HTTP Paths

No Task-03 collection from:

```text
/capport/api
/auth/session/<session_id>
/auth/session/<session_id>/retry
Admin Web
Omada webhook receiver
portal counter API
public traffic API
static assets
arbitrary Flask routes
```

No global Flask `before_request` fingerprint collector.

---

# 6. Source Kind / Subtypes

```text
source_kind = portal_headers
feature_schema_version = 1
```

Exact subtypes:

```text
omada_external_portal
capport_login
```

No subtype for CAPPORT API, session polling, retry, Admin or webhook traffic.

---

# 7. Extractor Identity

```text
extractor_name = portal-http-parser
extractor_version = 1.0.0
feature_schema_version = 1
rule_version = null
```

---

# 8. Task-01 Boundary Reused

Task-03 reuses Task-01:

```text
normalized evidence envelope
EvidenceSchemaRegistry
HTTPS/Bearer ingest API
producer/site/capture/source authorization
P1 privacy class
retention
idempotency
source-health events
canonical evidence SQLite DB
read-service boundary
```

Task-03 creates no second DB/API/identity model/classification table/UI storage.

---

# 9. Transport Choice

V1 freezes:

```text
ASYNC HTTPS/Bearer
→ existing Task-01 API
```

Base URL:

```text
https://192.168.0.202:9443/api/internal/device-fingerprint/v1
```

Endpoints:

```text
POST /evidence/batch
POST /source-health/batch
```

A direct same-process Task-01 repository adapter is rejected because it would create a second write path around Task-01 validation/security/idempotency.

---

# 10. Portal Producer Identity

```text
producer_id = portal-zefer-01
capture_source_id = zefer-portal-http-01
site_id = 6a64f17630da7c70d232187a
allowed_guest_cidrs = ["192.168.8.0/22"]
allowed_source_kinds = ["portal_headers"]
```

This producer is separate from `sensor-zefer-01` and uses a different Bearer credential.

Task-01 external mapping concept:

```json
{
  "producer_id": "portal-zefer-01",
  "bearer_token": "<external-secret>",
  "capture_source_id": "zefer-portal-http-01",
  "site_id": "6a64f17630da7c70d232187a",
  "allowed_guest_cidrs": ["192.168.8.0/22"],
  "allowed_source_kinds": ["portal_headers"]
}
```

No secret in Git.

---

# 11. Credential / TLS Files

Portal producer credential:

```text
/etc/captive-portal/device-fingerprint/portal.bearer
root:admin
0640
```

Portal TLS trust:

```text
/etc/captive-portal/device-fingerprint/portal-ca.crt
root:root
0644
```

TLS verification is mandatory. `verify=False` is forbidden.

No credential in command line, telemetry, queue, payload or repository.

---

# 12. Failure-Isolation Invariant

```text
PORTAL FINGERPRINT FAILURE
MUST NEVER
BECOME AUTHORIZATION FAILURE
```

Task-03 MUST NOT:

```text
block Authorization
delay AuthWorker scheduling waiting for evidence
call Task-01 HTTP from request thread
retry evidence delivery from request thread
wait for queue capacity
wait for coalescer lock
write fingerprint SQLite from request thread
```

If evidence handoff cannot accept an event:

```text
drop evidence
increment bounded sanitized telemetry
continue normal portal/auth flow
```

---

# 13. Exact Interception Architecture

Two layers:

```text
HTTP route
→ bounded transient header normalization

PortalEntryHandler.prepare_portal()
→ canonical AuthSession
→ AuthWorker scheduling
→ non-blocking evidence try_submit
```

For a newly created session, evidence submission occurs only after successful AuthWorker scheduling.

---

# 14. External Portal Interception

In `app/web/web.py`, current `GET /`:

```text
capture allowed header values + request timestamp
normalize into transient PortalEvidenceCandidate
source_subtype = omada_external_portal
pass candidate into PortalEntryHandler
```

The route makes no fingerprint network call.

---

# 15. CAPPORT Login Interception

In `app/capport/routes.py`, only `capport_login()` and only after:

```text
state.allowed == true
state.client_found == true
state.client is not None
```

Then:

```text
source_subtype = capport_login
```

CAPPORT discovery requests without a resolved client create no evidence.

---

# 16. Shared PortalEntry Hook

`PortalEntryHandler` receives optional:

```text
portal_evidence_sink
```

Default:

```text
DISABLED / NULL SINK
```

`open_portal()` / `prepare_portal()` accept an optional already-normalized `portal_evidence_candidate`.

No Flask `request` import is added to `portal_entry.py`.

---

# 17. Authorization Ordering

New session:

```text
create/reuse AuthSession
→ existing portal counter/telemetry
→ submit AuthWorker
→ if worker scheduling succeeded:
   portal_evidence_sink.try_submit(...)
→ snapshot / response
```

If AuthWorker scheduling fails:

```text
fingerprint try_submit = NOT CALLED
```

For reused sessions, evidence may be submitted after reuse is resolved.

---

# 18. Canonical Identity Binding

Envelope identity uses canonical AuthSession facts only:

```text
site_id = session.site_id
observed_mac = session.client_mac
observed_ip = session.client_ip when scope-valid
observed_at = original portal HTTP observation time
```

No fuzzy identity matching.
No UA-similarity identity.
No cross-MAC merge.

---

# 19. MAC / IP / Site / SSID Scope

MAC is mandatory:

```text
session.client_mac is null
→ NO evidence
```

IP:

```text
null IP → observed_ip = null
non-null IP must be inside 192.168.8.0/22
out-of-scope IP → drop event
```

Site must equal exactly:

```text
6a64f17630da7c70d232187a
```

SSID is scope corroboration only:

```text
if present and != Zefer_Parki
→ drop event
```

If SSID is absent, valid Site+MAC(+guest IP where present) is sufficient.
AP MAC is not persisted and not used as fingerprint identity.

---

# 20. Request Timestamp Authority

At the eligible HTTP route capture:

```text
datetime.now(timezone.utc)
```

before PortalEntryHandler processing.

That timestamp becomes `observed_at`.
It is not worker/queue/delivery/ingest time.

---

# 21. Raw Header Lifetime

Only these raw headers are read:

```text
User-Agent
sec-ch-ua
sec-ch-ua-platform
sec-ch-ua-mobile
```

Raw values exist only during bounded parser execution in the Flask request thread.

After normalization:

```text
raw strings discarded
not queued
not logged
not hashed for durable correlation
not persisted
```

Raw-UA durable retention:

```text
ZERO
```

---

# 22. Input Bounds

```text
User-Agent max chars = 1024
sec-ch-ua max chars = 1024
sec-ch-ua-platform max chars = 128
sec-ch-ua-mobile max chars = 16
```

Oversized individual header:

```text
treat that header as malformed/unavailable
DO NOT truncate and parse
continue request
```

---

# 23. Accept / Accept-Language Decision

V1 evidence explicitly excludes:

```text
Accept
Accept-Language
```

Reason:

```text
research value optional/unproven
Accept already serves HTTP negotiation
Accept-Language expands locale/privacy surface
neither is needed for Phase-1 portal evidence
```

No durable locale/language/MIME-preference features.

---

# 24. High-Entropy CH / JS Boundary

Forbidden:

```text
Accept-CH expansion
Sec-CH-UA-Model solicitation
Sec-CH-UA-Full-Version
Sec-CH-UA-Full-Version-List
Sec-CH-UA-Platform-Version
Sec-CH-UA-Arch
Sec-CH-UA-Bitness
Sec-CH-UA-WoW64
```

Also forbidden:

```text
canvas
audio
WebGL
fonts
screen fingerprinting
timezone fingerprinting
hardware concurrency
device memory
plugin/media enumeration
```

No active client probing.

---

# 25. Exact portal_headers/1 Schema

Payload has EXACTLY 16 keys:

```text
platform_family
mobile_boolean
browser_runtime_family
webview_or_captive_context
model_family
os_major
platform_source
mobile_source
runtime_source
context_source
model_source
os_major_source
ua_present
sec_ch_ua_present
sec_ch_ua_platform_present
sec_ch_ua_mobile_present
```

All nullable fields are present explicitly as JSON `null`.
No extra key.

---

# 26. platform_family

Type:

```text
string | null
```

Allowed:

```text
android
ios
windows
macos
chromeos
linux
```

No `other` bucket.
Unrecognized = `null`.

Precedence:

```text
1. valid sec-ch-ua-platform
2. bounded transient UA fallback
```

CH mappings are case-insensitive semantic mappings for Android, iOS, Windows, macOS, Chrome OS and Linux.

UA fallback precedence:

```text
Android → android
iPhone/iPad/iPod → ios
CrOS → chromeos
Windows NT → windows
Macintosh/Mac OS X → macos
X11/Linux → linux
```

Android checked before generic Linux.

---

# 27. mobile_boolean

Type:

```text
boolean | null
```

Primary authority:

```text
sec-ch-ua-mobile
?1 → true
?0 → false
```

Malformed → unavailable.

UA fallback may set only positive `true` for explicit:

```text
iPhone
iPod
Android ... Mobile
```

Absence of a mobile token does not infer `false`.

---

# 28. browser_runtime_family

Type:

```text
string | null
```

Allowed:

```text
android_webview
chromium
firefox
safari_webkit
```

No browser version and no `other` bucket.

WebView precedence over generic Chromium.

Low-entropy `sec-ch-ua` brand mapping:

```text
Android WebView → android_webview
Chromium / Google Chrome / Microsoft Edge / Opera → chromium
Firefox → firefox
```

Unknown/GREASE brands produce no durable runtime value.

UA fallback:

```text
Firefox/ → firefox
CriOS/ Chrome/ Chromium/ Edg/ OPR/ → chromium
Version/... Safari/ without Chromium-family token → safari_webkit
```

---

# 29. WebView / Captive Context

`webview_or_captive_context`:

```text
string | null
```

Allowed positive values only:

```text
android_webview
captive_helper
```

Android WebView positive evidence includes explicit `; wv)` or accepted Android `Version/4.0 + Chrome + Mobile Safari` WebView pattern.

`captive_helper` requires explicit UA token:

```text
CaptiveNetworkSupport
CaptivePortalLogin
CaptivePortal
```

Portal URL alone does not prove captive-helper runtime.
Absence does not produce a negative `browser` value.

---

# 30. model_family Policy

`model_family` is approved as P1 only when explicitly present in bounded Android UA syntax.

```text
string | null
max 64 chars
```

Conceptual accepted form:

```text
Android <version>;
[optional locale;]
<model family> Build/
```

Persist only `<model family>`.
Never persist:

```text
Build ID
firmware ID
serial
locale
raw UA fragment
```

Sanitization:

```text
trim
collapse internal repeated whitespace
printable ASCII only
1..64 chars
```

Reject to null on control chars, URL, MAC-like token, UUID-like token or unbounded content.
Do not truncate a rejected value into durable evidence.

---

# 31. os_major

```text
integer | null
range 1..99
```

Only explicit UA version token.

Android:

```text
Android <major>[.<minor>...]
→ major
```

iOS/iPadOS:

```text
CPU iPhone OS <major>_
CPU OS <major>_
→ major
```

V1 does not map Windows NT to marketing Windows version and does not persist macOS/ChromeOS/Linux OS major without later research.

---

# 32. Provenance Fields

```text
platform_source = sec_ch_ua_platform | user_agent | null
mobile_source = sec_ch_ua_mobile | user_agent | null
runtime_source = sec_ch_ua | user_agent | combined | null
context_source = user_agent | null
model_source = user_agent | null
os_major_source = user_agent | null
```

No raw source value retained.

---

# 33. Presence Booleans

```text
ua_present
sec_ch_ua_present
sec_ch_ua_platform_present
sec_ch_ua_mobile_present
```

Boolean means header had a non-empty value within its input-length bound.
A bounded malformed header may have `present=true` while its normalized feature stays null.

---

# 34. Evidence Emission Minimum / Quality

Do not persist an event if all six normalized evidence values are null:

```text
platform_family
mobile_boolean
browser_runtime_family
webview_or_captive_context
model_family
os_major
```

Presence booleans alone are insufficient.

`quality_state=valid` when:

```text
platform_family != null
AND browser_runtime_family != null
AND (mobile_boolean != null OR webview_or_captive_context != null)
```

`quality_state=partial` when at least one durable evidence field is non-null but `valid` criteria are not met.

Missing/malformed headers do not use `degraded`; runtime failure belongs to source health.

---

# 35. Complete Task-01 Envelope

```text
source_event_id = UUID4 created once after coalescing accepts
source_kind = portal_headers
source_subtype = omada_external_portal | capport_login
extractor_name = portal-http-parser
extractor_version = 1.0.0
feature_schema_version = 1
rule_version = null
site_id = canonical AuthSession site
capture_source_id = zefer-portal-http-01
observed_at = original HTTP request time
observed_mac = canonical AuthSession MAC
observed_ip = canonical guest IP or null
quality_state = valid | partial
payload = exact portal_headers/1
```

Task-01 persists existing `privacy_class=P1`.

---

# 36. Coalescing Semantics

Purpose: prevent refresh/reopen/reuse request floods.

Canonical normalized payload hash:

```text
payload_sha256 = SHA256(Task-01 canonical JSON(payload))
```

Key:

```text
(site_id, canonical_mac, source_subtype, payload_sha256)
```

Observed IP is not part of fingerprint-content dedup.

Different MAC = independent.
Different payload = immediate new event.
Different subtype = independent.

Window:

```text
21600 seconds = 6 hours
```

Same key inside 6h:

```text
NO new evidence
portal_evidence_coalesced += 1
```

---

# 37. Coalescer Bounds / Non-Blocking Rule

```text
max entries = 8192
clock = time.monotonic()
max expired entries removed per submit = 32
```

At capacity: evict oldest key.

Coalescer lock acquisition is NON-BLOCKING.
If contended:

```text
drop evidence
portal_evidence_drop_coalescer_busy += 1
continue request
```

No raw UA/CH in coalescer.

---

# 38. Bounded In-Memory Handoff

Task-03 uses one bounded FIFO queue:

```text
max normalized items = 256
```

Request-path enqueue:

```text
put_nowait()
```

Full queue:

```text
drop evidence
portal_evidence_drop_queue_full += 1
```

No persistent portal spool.

Queue contains fully normalized Task-01 event objects only.
Never raw headers, Flask request, cookies, URL or Authorization.

---

# 39. Dedicated Worker

One background thread:

```text
name = device-fingerprint-portal
```

It is separate from AuthWorker executor and all existing worker pools.

Disabled config:

```text
no thread
no queue activity
no HTTP
```

Enabled startup may only create in-memory structures and start one daemon thread.
It performs no startup HTTP, credential read, CA read, SQLite open, DB scan or Task-01 health wait.

Worker-start/config failure must be caught; main Flask startup continues.

---

# 40. Background Batch / Delivery

Worker drains up to:

```text
50 evidence events
```

per Task-01 batch, below Task-01 max 100.

HTTP timeout:

```text
connect = 0.5 seconds
read = 2.0 seconds
```

No HTTP call in request thread.
No request-path credential/CA access.

Failed evidence batch is DROPPED.
Task-03 V1 has no persistent retry spool.

Availability principle:

```text
Authorization availability > fingerprint completeness
```

---

# 41. Delivery Cooldowns

Transient:

```text
connection error
TLS transient error
timeout
500
503
→ 30 second cooldown
```

429:

```text
valid Retry-After 1..60 seconds
otherwise 30 seconds
```

Permanent-class rejection:

```text
400 401 403 404 405 409 413
→ drop batch
→ local producer_rejected
→ 300 second cooldown
```

Events during cooldown are dropped without HTTP attempt.
No infinite latch, so externally corrected credentials/config can recover.
No retry backlog.

---

# 42. Queue Age Bound

Before send:

```text
local UTC now - observed_at <= 300 seconds
```

Older item:

```text
drop
portal_evidence_drop_queue_stale += 1
```

No timestamp rewrite.
Task-01 independently retains authoritative delayed-event validation.

---

# 43. Task-03 Config Isolation

New package owns:

```text
app/device_fingerprint_portal/config.py
```

It reads `DEVICE_FINGERPRINT_PORTAL_*` directly from environment.

Do NOT integrate into:

```text
app/config.py
app/settings.py
```

Default:

```text
DEVICE_FINGERPRINT_PORTAL_ENABLED=false
```

Invalid enabled config:

```text
sanitized telemetry
NULL/unavailable sink
core CaptivPortal startup continues
```

---

# 44. Proposed Exact Config

```text
DEVICE_FINGERPRINT_PORTAL_ENABLED=false
DEVICE_FINGERPRINT_PORTAL_PRODUCER_ID=portal-zefer-01
DEVICE_FINGERPRINT_PORTAL_CAPTURE_SOURCE_ID=zefer-portal-http-01
DEVICE_FINGERPRINT_PORTAL_SITE_ID=6a64f17630da7c70d232187a
DEVICE_FINGERPRINT_PORTAL_GUEST_CIDRS=192.168.8.0/22
DEVICE_FINGERPRINT_PORTAL_ALLOWED_SSIDS=Zefer_Parki
DEVICE_FINGERPRINT_PORTAL_EVIDENCE_BASE_URL=https://192.168.0.202:9443/api/internal/device-fingerprint/v1
DEVICE_FINGERPRINT_PORTAL_CA_CERT_PATH=/etc/captive-portal/device-fingerprint/portal-ca.crt
DEVICE_FINGERPRINT_PORTAL_CREDENTIAL_PATH=/etc/captive-portal/device-fingerprint/portal.bearer
DEVICE_FINGERPRINT_PORTAL_QUEUE_MAX_EVENTS=256
DEVICE_FINGERPRINT_PORTAL_BATCH_SIZE=50
DEVICE_FINGERPRINT_PORTAL_QUEUE_MAX_AGE_SECONDS=300
DEVICE_FINGERPRINT_PORTAL_COALESCE_SECONDS=21600
DEVICE_FINGERPRINT_PORTAL_COALESCE_MAX_ENTRIES=8192
DEVICE_FINGERPRINT_PORTAL_CONNECT_TIMEOUT_SECONDS=0.5
DEVICE_FINGERPRINT_PORTAL_READ_TIMEOUT_SECONDS=2.0
DEVICE_FINGERPRINT_PORTAL_TRANSIENT_COOLDOWN_SECONDS=30
DEVICE_FINGERPRINT_PORTAL_REJECT_COOLDOWN_SECONDS=300
```

`.env.example` contains no Bearer value.

---

# 45. Source Health

Scope:

```text
source_kind = portal_headers
site_id = 6a64f17630da7c70d232187a
capture_source_id = zefer-portal-http-01
```

Malformed/missing UA/CH is evidence completeness, not source-unavailable state.

No periodic heartbeat in V1.
Silence is allowed and does not mean unavailable.

First successful evidence delivery may establish:

```text
available / reason=null
```

On first transient delivery failure, remember in memory:

```text
unavailable_started_at
reason = ingest_delivery_unavailable
```

On later evidence-delivery recovery, asynchronously attempt a bounded source-health batch containing:

```text
unavailable at first failure time
available at recovery time
```

provided Task-01 age rules still permit it.

Permanent-class producer rejection is locally `producer_rejected`; central health may be absent if the same API boundary rejects it.

Worker-start failure: local telemetry only; never request-thread fallback delivery.

---

# 46. Operational Telemetry Privacy

Allowed counters/state only:

```text
runtime state
events extracted/partial/queued/coalesced
drop_missing_mac
drop_site_scope
drop_ip_scope
drop_ssid_scope
drop_malformed
drop_coalescer_busy
drop_queue_full
drop_queue_stale
delivery batch/success/failure class/cooldown
source-health transition type
```

Forbidden ordinary logs:

```text
raw UA
raw Client Hints
normalized model string
MAC
client IP
Bearer token
full normalized payload
```

---

# 47. Privacy Boundary

Durable normalized portal evidence:

```text
P1
```

P2/raw durable lifetime:

```text
ZERO
```

Forbidden durable/queued content:

```text
raw User-Agent
raw Client Hints
raw-header hash
all headers
Accept-Language
cookies
Authorization
SNI
DNS names
URLs
browser history
high-entropy CH
JS fingerprint vectors
```

Raw UA/CH hashes are explicitly forbidden because they would create a durable correlator outside normalized privacy policy.

---

# 48. Production Schema Registration

Add pure validator:

```text
app/device_fingerprint/portal_schemas.py
validate_portal_headers_v1()
```

Modify production registry to include exactly:

```text
dhcp/1
tcp_syn/1
tls_client/1
quic_client/1
portal_headers/1
```

No Task-02 schema meaning changes.

`portal_schemas.py` imports no Flask, requests, thread, queue, credential or portal-route code.

---

# 49. New Portal Runtime Package

```text
app/device_fingerprint_portal/
```

Exact proposed files:

```text
__init__.py
config.py
models.py
extractor.py
coalescer.py
producer.py
runtime.py
telemetry.py
```

Ownership:

```text
extractor.py = bounded UA/CH normalization only
coalescer.py = bounded in-memory dedup only
runtime.py = non-blocking submit/queue/worker/cooldown/source-health state
producer.py = background credential + HTTPS/Bearer only
```

No SQLite repository and no classifier.

---

# 50. Runtime File Boundary

Modify narrowly:

```text
app/device_fingerprint/schema_registry.py
app/web/web.py
app/web/portal_entry.py
app/capport/routes.py
.env.example
```

Canonical docs as needed:

```text
README.md
README_RU.md
docs/README.md
docs/architecture.md
docs/project-inventory.md
docs/module-index.md
docs/configuration.md
docs/security.md
docs/logging.md
docs/deployment.md
docs/modules/device-fingerprint.md
docs/modules/portal-entry.md
```

New:

```text
docs/modules/device-fingerprint-portal.md
```

---

# 51. Explicit NO-TOUCH

```text
run.py
app/config.py
app/settings.py
app/auth/worker.py
app/auth/session.py
app/auth/health.py
app/observations/**
app/current_state/**
app/analytics/**
app/admin_web/**
app/traffic_projection/**
app/device_fingerprint_sensor/**
deploy/device-fingerprint/*
```

`app/auth/manager.py` should remain unchanged unless TechLead finds a strictly necessary typing-only source boundary.

No new systemd unit.

---

# 52. No New Dependency / Startup Dependency

No new Python package dependency.
Existing `requests` is used only in the Task-03 background producer.

Before core listener readiness Task-03 MUST NOT perform:

```text
Task-01 network health check
credential read
CA read
fingerprint DB open
repository scan
HTTP delivery
```

Optional config/thread composition failure is fail-open to core startup.

---

# 53. Classification / Identity Non-Goals

Task-03 MUST NOT produce:

```text
device_class
confidence score
vendor inference
model inference from network evidence
final browser product identity
person identity
cross-MAC linkage
```

Header values are spoofable client-supplied evidence, never authorization facts or ground truth.

Task-03A labeled matrix, Task-04 classifier, Task-05 identity integration and Task-06 Device Card remain separate.

---

# 54. Test Boundary — New

```text
tests/device_fingerprint/test_portal_schema.py

tests/device_fingerprint_portal/__init__.py
tests/device_fingerprint_portal/test_config.py
tests/device_fingerprint_portal/test_extractor.py
tests/device_fingerprint_portal/test_coalescer.py
tests/device_fingerprint_portal/test_producer.py
tests/device_fingerprint_portal/test_runtime.py
tests/device_fingerprint_portal/test_telemetry.py
tests/device_fingerprint_portal/test_privacy.py
```

Existing route/integration tests modified only for optional candidate plumbing.

---

# 55. Schema / Extractor Tests

Must prove:

```text
exact 16-key schema
allowed/null enums
os_major bounds
model bounds/printability
provenance enums
presence booleans
extra/missing key rejection
raw-UA-like key rejection
Accept-Language key rejection
```

Controlled fixtures:

```text
Android WebView
Android Chromium
desktop Chromium
Firefox
Safari/WebKit
CH-only partial
UA-only partial
missing headers
malformed CH
oversized header
explicit Android model
Android OS major
iOS OS major
unknown platform/runtime
```

No real browsing data.

---

# 56. Privacy Canary Tests

Inject unique canary strings into:

```text
User-Agent
sec-ch-ua
Accept-Language
```

Assert canaries are absent from:

```text
normalized payload
queue item
telemetry-safe structure
Task-01 persisted row
```

---

# 57. Identity / Scope Tests

```text
missing MAC → drop
wrong Site → drop
non-guest IP → drop
null IP + valid Site/MAC → allowed
SSID Zefer_Parki → allowed
different explicit SSID → drop
AP MAC never enters payload
```

---

# 58. Coalescing Tests

```text
same Site+MAC+subtype+payload within 6h → one event
same payload + different MAC → separate
same MAC + changed normalized payload → separate
same MAC/payload + different subtype → separate
after 6h → new event
cache <= 8192
expiry work <=32 per submit
```

---

# 59. Authorization Ordering / Non-Blocking Tests

Using injected fake executor and sink:

```text
AuthWorker submission happens before evidence try_submit
worker-start failure → evidence try_submit not called
sink exception → portal/auth result unchanged
queue full → request continues
coalescer lock busy → request continues
```

Async isolation synchronization proof:

```text
background producer blocks on test Event
AuthWorker is scheduled
portal response returns
BEFORE producer is released
```

This avoids a flaky timing benchmark.

---

# 60. Delivery / Source-Health Tests

Prove failures for:

```text
timeout
500
503
429
400
401
403
409
413
credential unreadable/invalid
```

never alter portal/auth result.

Verify exact cooldowns, failed-batch drop and no synchronous retry.

Source-health tests:

```text
malformed UA/CH != unavailable
first successful delivery → available
transient failure remembered
later recovery → bounded unavailable+available attempt
disabled runtime → no source-health network
worker-start failure → local telemetry only
```

---

# 61. Gate A — Coder Focused Verification

Only after FINAL + Owner explicit implementation authorization.

Proposed exact commands:

```bash
python -m pytest -q \
  tests/device_fingerprint/test_portal_schema.py \
  tests/device_fingerprint_portal
```

```bash
python -m pytest -q \
  tests/test_portal_entry.py \
  tests/test_capport_routes.py \
  tests/test_proxy_headers.py
```

```bash
python -m compileall -q \
  app/device_fingerprint \
  app/device_fingerprint_portal \
  app/web \
  app/capport
```

```bash
git diff --check
```

TechLead may narrow/fix exact test filenames after fresh source rebind.
Coder does not run official full regression.

---

# 62. Gate B — Tech Lead Static / Source Review

Verify:

```text
FINAL conformance
file boundary
no run.py change
no AuthWorker algorithm change
AuthWorker-before-evidence ordering
no request-path HTTP
no request-path credential IO
bounded/non-blocking queue and coalescer
raw UA/CH never queued/persisted/logged
Accept/Accept-Language excluded
high-entropy CH absent
portal_headers/1 exact schema
producer identity exact
Task-01 registry extension exact
no second DB/API/identity model
docs reconciled
```

Result: `PASS` or `RETURN TO CODER`.

---

# 63. Gate C — Fresh Central Full Regression

Required.
Use the current approved Central Lab runner discovered immediately before execution.

Must prove no regression to:

```text
External Portal
CAPPORT
Auth session/retry
Admin
Task-01
Task-02
Visit lifecycle
Observation/current-state
Traffic
```

Immutable candidate rules apply.

---

# 64. Gate D — Linux Portal Evidence Integration

Required against implemented immutable candidate.

Bring up production-compatible:

```text
main CaptivPortal
Task-01 evidence service
test Task-03 portal producer mapping
```

Controlled synthetic requests must prove:

```text
omada_external_portal event
capport_login event
Task-01 HTTPS/Bearer acceptance
portal_headers/1 validation
canonical MAC/Site/IP envelope
source subtype
coalescing
Task-01 P1 DB row
zero raw UA/CH persistence
```

No production deployment required.

---

# 65. Gate E — Failure Isolation

Prove separately:

```text
Task-03 disabled
worker absent/start failure
queue full
coalescer lock busy
credential unreadable
Task-01 evidence service stopped
TLS failure
Task-01 503
Task-01 401/403
background producer blocked
```

For every case:

```text
Portal functional
AuthWorker scheduling functional
fingerprint failure does not alter authorization result
```

---

# 66. Gate F — Request-Path Non-Blocking Proof

Structural proof:

```text
no requests.post in app/web/** request path
no requests.post in app/capport/** request path
no credential/CA file read in request path
only bounded parser + non-blocking coalescer + put_nowait
```

Synchronization proof:

```text
background producer intentionally blocked
AuthWorker scheduled
portal response completes before producer release
```

No numeric latency SLO invented in this DRAFT.

---

# 67. Gate G — Privacy / Durable Storage

Search Task-01 DB, Task-03 logs, auth telemetry, journald/application logs and any Task-03 durable locations.

Must prove controlled canaries absent for:

```text
full User-Agent
raw sec-ch-ua
raw sec-ch-ua-platform
raw sec-ch-ua-mobile
Accept-Language
model Build ID
cookie
Authorization header
```

Durable DB may contain only approved normalized `portal_headers/1` P1 fields.

---

# 68. Gate H — Flood / Coalescing

Send >=100 identical eligible portal-entry requests for same Site/MAC/subtype/payload inside the 6h window.

Expected:

```text
1 normalized event accepted for queue/delivery
remaining eligible duplicates coalesced
```

Change one normalized evidence field:

```text
new event emitted immediately
```

---

# 69. Publication / Activation Governance

Before all mandatory gates accept the immutable candidate:

```text
NO normal publication commit
NO push
NO PR
```

After exact-candidate Owner+TechLead acceptance, TechLead may separately authorize branch/publication commit/push/Draft PR.

That does not authorize merge/deploy/activation.

Repository default:

```text
DEVICE_FINGERPRINT_PORTAL_ENABLED=false
```

Production activation is a separate Owner workflow for producer mapping, secret, CA trust, env and enable flag.

---

# 70. TechLead10 Review — Core Source Contract

Please PASS/FIX:

```text
source_kind = portal_headers
subtypes = omada_external_portal / capport_login

GET / → external subtype
CAPPORT login after state.client resolution → capport subtype

shared submit point =
PortalEntryHandler.prepare_portal()
after AuthWorker scheduling
```

Confirm exclusion of CAPPORT API, auth polling/retry, Admin and webhook.

---

# 71. TechLead10 Review — Schema / Parser

Please PASS/FIX:

```text
exact 16-key schema
platform/mobile/runtime/context/model/os_major
provenance fields
presence booleans
valid/partial quality
low-entropy CH only
transient UA only
no Accept/Accept-Language
no raw hash
```

Confirm `model_family` explicit-only P1 policy and OS-major constraints.

---

# 72. TechLead10 Review — Failure Isolation / Handoff

Please PASS/FIX:

```text
AuthWorker scheduled first
queue = 256
put_nowait
coalescer lock non-blocking
coalescer window = 21600s
coalescer max = 8192
batch = 50
connect timeout = 0.5s
read timeout = 2.0s
failed batch = drop
transient cooldown = 30s
permanent-class cooldown = 300s
no persistent portal spool
```

No request-path network/file IO.

---

# 73. TechLead10 Review — Security / Source Health

Please PASS/FIX:

```text
producer = portal-zefer-01
capture source = zefer-portal-http-01
site = 6a64f17630da7c70d232187a
guest CIDR = 192.168.8.0/22
secret = separate from sensor
portal.bearer = root:admin 0640
```

Source health:

```text
transition-only
no heartbeat
available after successful delivery
transient failure remembered in-memory
recovery attempts unavailable+available history
malformed header != unavailable
disabled = silence
```

---

# 74. TechLead10 Review — File Boundary

Fresh-rebind before FINAL and confirm NO changes to:

```text
run.py
app/config.py
app/settings.py
AuthWorker logic
Task-02 sensor
deploy/device-fingerprint/*
```

Narrow runtime changes only:

```text
web.py
portal_entry.py
capport/routes.py
Task-01 schema registry
new portal package
```

---

# 75. Open Items Before FINAL

No broad research requested.

TechLead10 should return PASS/FIX on:

```text
1. source-kind/subtype naming
2. exact 16-key schema
3. parser enum/rule exactness
4. PortalEntryHandler hook ordering
5. 6-hour coalescing
6. memory-only queue/no-spool policy
7. zero-IO worker startup in create_app
8. timeout/cooldown values
9. transition-only source health
10. producer identity/config
11. file boundary
12. focused Gate A commands
```

---

# 76. Control Status

```text
TASK = TASK-DEVICE-FINGERPRINT-03-DRAFT
TITLE = Portal UA / Client Hints Evidence

REPOSITORY BASELINE =
479ed77e713c449850cfc5d4dd972b7c6429e64a

TREE =
ca2f404d0fc38e1fe82e40085f29684f9c142447

TASK-01 = CONSUMED
TASK-02 = CONSUMED
SOURCE KIND = portal_headers
HIGH-ENTROPY CH = DEFERRED
RAW UA DURABLE RETENTION = ZERO

IMPLEMENTATION-READY = NO
CURRENT GATE = TECHLEAD10 SOURCE / ARCHITECTURE REVIEW
CODER = HOLD

IMPLEMENTATION = NOT AUTHORIZED
BRANCH = NOT AUTHORIZED
COMMIT = NOT AUTHORIZED
PUSH = NOT AUTHORIZED
PR = NOT AUTHORIZED
DEPLOY = NOT AUTHORIZED
PRODUCTION ACTIVATION = NOT AUTHORIZED
CLASSIFIER = NOT AUTHORIZED
DEVICE CARD = NOT AUTHORIZED
```

---

# 77. Next Workflow

```text
TASK-DEVICE-FINGERPRINT-03-DRAFT
        ↓
TechLead10 source / architecture review
        ↓
PASS or narrow FIX
        ↓
Architect + TechLead10
TASK-DEVICE-FINGERPRINT-03-FINAL
        ↓
TechLead10 FINAL consistency PASS
        ↓
Owner explicit implementation authorization
        ↓
Coder implementation
        ↓
Gates A/B/C/D/E/F/G/H
        ↓
exact-candidate acceptance
        ↓
separate publication authorization
        ↓
Owner-controlled merge
        ↓
separate deploy/activation workflow
```

Until explicit Owner implementation authorization:

```text
CODER = HOLD
NO IMPLEMENTATION
NO BRANCH
NO COMMIT
NO PUSH
NO PR
NO DEPLOY
NO PRODUCTION ACTIVATION
```

**End of TASK-DEVICE-FINGERPRINT-03-DRAFT.**
