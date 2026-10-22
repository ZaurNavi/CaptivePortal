# TASK-DEVICE-FINGERPRINT-03-FINAL

## Portal UA / Client Hints Evidence

**Project:** CaptivPortal  
**Program:** Device Fingerprint  
**Parent foundation:** `TASK-DEVICE-FINGERPRINT-01`  
**Network evidence predecessor:** `TASK-DEVICE-FINGERPRINT-02`  
**Prepared:** 2026-09-15  
**Status:** `FINAL — FOR TECHLEAD10 FINAL CONSISTENCY REVIEW`  
**Implementation-ready:** `PENDING TECHLEAD10 FINAL PASS`  
**Coder:** `HOLD`  
**Implementation authorization:** `NOT GRANTED`  
**Production deploy / activation:** `NOT AUTHORIZED`

---

# 0. Final Control Gate


```text
DEVICE-FINGERPRINT-00 = CLOSED / PASS
DEVICE-FINGERPRINT-01 = IMPLEMENTED / MERGED
DEVICE-FINGERPRINT-02 = IMPLEMENTED / MERGED
DEVICE-FINGERPRINT-03 = FINAL ASSEMBLED

ARCHITECTURE = PASS
TECHNICAL CONTRACT = COMPLETE
NEW RESEARCH = NOT REQUIRED

CURRENT GATE = TECHLEAD10 FINAL CONSISTENCY REVIEW
TECHLEAD10 FINAL PASS = PENDING
OWNER IMPLEMENTATION AUTHORIZATION = NOT GRANTED

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

Coder implementation begins only after:

```text
Architect FINAL
+
TechLead10 FINAL consistency PASS
+
Owner explicit implementation authorization
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

External `GET /` Task-03 extraction is eligible ONLY AFTER the route's existing
minimum Omada-parameter guard has passed:

```text
site is present
AND
(clientMac is present OR clientIp is present)
```

A request already rejected by that guard:

```text
MUST NOT parse UA/Client Hints
MUST NOT create a Task-03 candidate
```

CAPPORT remains eligible only after:

```text
state.allowed == true
state.client_found == true
state.client is not None
```

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

# 12. Failure-Isolation Invariant — Hard Containment


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

Two independent local exception-containment boundaries are mandatory.

Route-level extraction:

```python
candidate = None
try:
    candidate = extract_portal_evidence_candidate(...)
except Exception:
    safe_task03_extractor_failure_telemetry()
    candidate = None
```

The telemetry call itself is best-effort/sanitized and MUST NOT propagate.

Shared PortalEntry submission:

```python
try:
    portal_evidence_sink.try_submit(...)
except Exception:
    safe_task03_submit_failure_telemetry()
    # continue existing portal/auth result unchanged
```

This local `try/except` MUST be inside the existing
`PortalEntryHandler.prepare_portal()` outer `try` boundary so a Task-03 sink
exception cannot reach the handler's existing broad exception path.

No Task-03 exception may alter:

```text
HTTP status
AuthSession state
AuthWorker scheduling
portal rendering
CAPPORT response
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
eligible HTTP route
→ local exception containment
→ bounded transient header normalization
→ PortalEvidenceCandidate | None

PortalEntryHandler.prepare_portal()
→ canonical AuthSession
→ AuthWorker scheduling
→ local exception containment
→ non-blocking evidence try_submit
```

For a newly-created session, evidence submission occurs only after successful
AuthWorker scheduling.

For a reused eligible session, submission occurs only after the existing
create/reuse decision has resolved the canonical AuthSession.

---

# 14. External Portal Interception


In `app/web/web.py`, current `GET /` keeps its existing minimum-parameter guard
first.

Exact order:

```text
read/validate existing Omada minimum parameters
→ if guard fails: existing controlled response; NO Task-03 parsing
→ capture request observation timestamp
→ try bounded Task-03 extraction locally
→ extractor exception: sanitized Task-03 telemetry + candidate=None
→ create PortalClientContext
→ call existing PortalEntryHandler with optional candidate
```

Source subtype:

```text
omada_external_portal
```

The route makes no fingerprint network call.

Task-03 extraction failure does not alter the existing guard/status/rendering
semantics.

---

# 15. CAPPORT Login Interception


In `app/capport/routes.py`, only `capport_login()` is eligible and only after:

```text
state.allowed == true
state.client_found == true
state.client is not None
```

Exact order after the resolved-client gate:

```text
capture request observation timestamp
→ try bounded Task-03 extraction locally
→ extractor exception: sanitized Task-03 telemetry + candidate=None
→ build existing PortalClientContext
→ call PortalEntryHandler with optional candidate
```

Source subtype:

```text
capport_login
```

CAPPORT discovery requests without a resolved client create no evidence.
Task-03 extraction failure does not alter CAPPORT status/response semantics.

---

# 16. Shared PortalEntry Hook — Local Sink Containment


`PortalEntryHandler` receives optional:

```text
portal_evidence_sink
```

Default:

```text
DISABLED / NULL SINK
```

`open_portal()` / `prepare_portal()` accept an optional already-normalized:

```text
portal_evidence_candidate
```

No Flask `request` import is added to `portal_entry.py`.

The Task-03 sink call has its OWN local exception containment inside
`prepare_portal()`:

```python
try:
    portal_evidence_sink.try_submit(...)
except Exception:
    safe_task03_submit_failure_telemetry()
```

That exception MUST NOT escape into the handler's existing broad outer
`except Exception` path.

Therefore a sink bug/failure cannot convert an otherwise valid portal flow into
HTTP 500.

---

# 17. Authorization Ordering


New session:

```text
create/reuse AuthSession
→ existing portal counter/telemetry
→ submit AuthWorker
→ if worker scheduling succeeded:
   locally-contained portal_evidence_sink.try_submit(...)
→ snapshot / response
```

If AuthWorker scheduling fails:

```text
fingerprint try_submit = NOT CALLED
```

If `try_submit()` raises:

```text
exception contained locally
existing AuthSession/result remains authoritative
existing response continues unchanged
```

For reused sessions, evidence may be submitted only after reuse is resolved.

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

# 22. Input Bounds / General Parser Grammar


Raw length bound is applied BEFORE any parsing/unquoting/substring inspection:

```text
User-Agent max chars = 1024
sec-ch-ua max chars = 1024
sec-ch-ua-platform max chars = 128
sec-ch-ua-mobile max chars = 16
```

Length means the Python header string length delivered by Flask/Werkzeug.

Oversized individual header:

```text
treat that header as unavailable
DO NOT truncate
DO NOT parse any prefix
continue request
```

For Client Hints, HTTP optional whitespace (`OWS`) means ONLY:

```text
SP   = 0x20
HTAB = 0x09
```

General CH rules:

```text
whole-header grammar must match
malformed CH = unavailable
no best-effort substring salvage
no backslash escape interpretation in V1
unknown/GREASE brand = ignored only after whole header is syntactically valid
```

General User-Agent rules:

```text
UA may be parsed only when non-empty and <=1024 chars
CR / LF / NUL anywhere → UA unavailable
all matching is deterministic ASCII case-insensitive literal/token matching
no parser side effects
```

The parser does not log raw header values.

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

# 26. platform_family — Exact Grammar


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

## sec-ch-ua-platform grammar

After the section-22 raw length check, accepted syntax is EXACTLY:

```text
OWS DQUOTE platform-value DQUOTE OWS
```

where:

```text
platform-value length = 1..64
platform-value chars = ASCII letters / digits / SP / . / _ / -
```

Not accepted:

```text
backslash escapes
comma/list syntax
semicolon parameters
embedded DQUOTE
control characters
extra non-OWS text
```

A syntactically valid but unrecognized quoted value is `unknown`, not malformed.

Case-insensitive exact semantic mappings:

```text
"Android"  → android
"iOS"      → ios
"Windows"  → windows
"macOS"    → macos
"Chrome OS"→ chromeos
"Linux"    → linux
```

Precedence:

```text
1. recognized valid sec-ch-ua-platform
2. UA fallback only if CH platform is absent/malformed/unrecognized
```

## UA platform fallback

Define an ASCII literal token match as case-insensitive literal matching whose
immediate preceding/following characters, when present, are NOT ASCII
alphanumeric.

Apply precedence:

```text
Android              → android
iPhone | iPad | iPod → ios
CrOS                 → chromeos
Windows NT           → windows
Macintosh | Mac OS X → macos
X11 | Linux          → linux
```

Android is checked before generic Linux.

---

# 27. mobile_boolean — Exact Grammar


Type:

```text
boolean | null
```

After raw length validation, `sec-ch-ua-mobile` grammar is EXACTLY:

```text
OWS ( "?1" / "?0" ) OWS
```

Only SP/HTAB surrounding OWS is permitted.

Semantics:

```text
?1 → true
?0 → false
```

Any other value, internal whitespace, parameter, list, quote or token is:

```text
malformed / unavailable
```

UA fallback is used only when valid `sec-ch-ua-mobile` is unavailable.
It may infer positive `true` only for explicit UA evidence:

```text
iPhone token
iPod token
Android token + Mobile token
```

Absence of positive mobile evidence never infers `false`.

---

# 28. browser_runtime_family — Exact sec-ch-ua Grammar


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

## sec-ch-ua grammar

After raw length validation, accepted V1 syntax is:

```text
brand-list = OWS brand-item *( OWS "," OWS brand-item ) OWS

brand-item =
  DQUOTE brand DQUOTE
  OWS ";" OWS "v" OWS "=" OWS
  DQUOTE version DQUOTE
```

Bounds:

```text
brand length = 1..64
version length = 1..32
brand-list items = 1..16
```

Allowed `brand` characters:

```text
printable ASCII 0x20..0x7e
EXCEPT:
DQUOTE
backslash
comma
semicolon
```

Allowed `version` characters:

```text
ASCII letters
digits
.
_
-
```

The parameter name is exact lowercase ASCII:

```text
v
```

No extra parameters are accepted.
No trailing comma is accepted.
If ANY item is malformed, the ENTIRE `sec-ch-ua` header is unavailable.

Recognized brands are case-insensitive after syntactic validation:

```text
Android WebView → android_webview
Chromium        → chromium
Google Chrome   → chromium
Microsoft Edge  → chromium
Opera           → chromium
Firefox         → firefox
```

All versions are parsed only to validate grammar and then discarded.
Unknown/GREASE brands are ignored.

Derive CH runtime:

```text
if Android WebView brand is present:
    android_webview
else collapse all recognized families
if exactly one family remains:
    that family
if >1 distinct recognized families remain:
    CH runtime = null
if none remain:
    CH runtime = null
```

## UA runtime fallback / reconciliation

Compute bounded UA runtime independently:

```text
explicit Android WebView rule → android_webview
Firefox/ token               → firefox
CriOS/ | Chrome/ | Chromium/ | Edg/ | OPR/ → chromium
Version/ + Safari/ and no Chromium-family token → safari_webkit
```

Final runtime reconciliation:

```text
if CH runtime == android_webview:
    result = android_webview
    source = sec_ch_ua unless UA also independently says android_webview,
             then combined

else if UA runtime == android_webview:
    result = android_webview
    source = user_agent unless CH also says android_webview,
             then combined

else if CH and UA are both non-null and equal:
    result = that family
    source = combined

else if CH and UA are both non-null and different:
    result = null
    source = null

else:
    use the one non-null result and its source
```

---

# 29. WebView / Captive Context — Exact Rules


`webview_or_captive_context`:

```text
string | null
```

Allowed positive values only:

```text
android_webview
captive_helper
```

## Android WebView UA rule

`android_webview` is positive when either exact bounded rule is true:

```text
A.
UA contains, case-insensitively:
";" OWS "wv" OWS ")"

OR

B.
UA contains an Android token and, in this order after that token:
Version/4.0
then Chrome/ or Chromium/
then Mobile Safari/
```

Rule B requires all literals in order; partial presence is insufficient.

## Captive-helper UA rule

`captive_helper` is positive when the UA contains, using the section-26 ASCII
literal token boundary rule, one of:

```text
CaptiveNetworkSupport
CaptivePortalLogin
CaptivePortal
```

Matching is case-insensitive.

Context precedence:

```text
android_webview
before
captive_helper
```

Portal URL alone does not prove captive-helper runtime.
Absence does not produce a negative `browser` value.

`context_source` is:

```text
user_agent
or
null
```

---

# 30. model_family — Exact Android Extraction


`model_family` is approved as P1 only when explicitly present in bounded Android
UA syntax.

```text
string | null
max 64 chars
```

Model extraction runs only when final `platform_family == android` and the UA is
available under section 22.

Exact bounded algorithm:

```text
1. inspect at most the first 4 non-nested parenthesized UA comments

2. each inspected comment must be <=256 chars for extraction purposes

3. split a comment on ';' into at most 8 fields
   trim ASCII SP/HTAB around each field

4. find a field matching exactly:
   Android <major>[.<minor>...]

   version grammar:
   major = 1..99 without leading sign
   each optional minor component = 1..3 decimal digits
   maximum 3 minor components

5. after the Android field, allow EITHER:
   a. the model/build field immediately
   OR
   b. exactly one locale field, then the model/build field

6. allowed locale field grammar:
   [A-Za-z]{2,3}([-_][A-Za-z0-9]{2,8}){1,2}

7. model/build field must match the entire field:
   <model> SP Build/<build-id>

8. <model> grammar before whitespace normalization:
   first char = ASCII alphanumeric
   remaining chars = ASCII alphanumeric / SP / . / _ / ( / ) / + / -
   raw model length = 1..64

9. <build-id> grammar:
   [A-Za-z0-9._-]{1,64}

10. persist ONLY <model> after:
    trim SP/HTAB
    collapse one-or-more internal SP/HTAB to one SP
```

The Build ID is used only as the explicit delimiter proving model syntax and is
immediately discarded.

If multiple distinct valid model candidates are found:

```text
model_family = null
```

Reject to `null` if the normalized model:

```text
is empty
exceeds 64 chars
contains non-printable/non-allowed chars
matches a MAC-like token
matches a UUID-like token
```

Never persist:

```text
Build ID
firmware ID
serial
locale
raw UA fragment
```

Do not truncate a rejected value into durable evidence.

---

# 31. os_major — Exact Extraction


```text
integer | null
range 1..99
```

OS major is persisted only from an explicit UA version token and only when it
agrees with final `platform_family`.

## Android

For `platform_family == android`, use the same bounded parenthesized-comment
scan as section 30.

Exact Android version field:

```text
Android <major>[.<minor>...]
```

with the section-30 version grammar.

Collect valid major values from inspected comments.

```text
exactly one distinct major → persist it
zero or >1 distinct majors → null
```

## iOS / iPadOS

For `platform_family == ios`, scan the bounded UA for exact case-insensitive
patterns with ASCII token boundaries:

```text
CPU iPhone OS <major>[_<minor>...]
CPU OS <major>[_<minor>...]
```

where:

```text
major = 1..99
optional minor component = 1..3 decimal digits
maximum 3 minor components
```

Collect valid major values:

```text
exactly one distinct major → persist it
zero or >1 distinct majors → null
```

V1 does NOT infer OS major from:

```text
Windows NT mapping
macOS compatibility token
ChromeOS browser/build token
Linux
browser version
JA4
model family
```

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
source_event_id = UUID4 created once after duplicate rejection and before queue admission
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

If queue admission fails, the generated UUID is discarded and is never durable.

Task-01 persists existing:

```text
privacy_class=P1
```

---

# 36. Coalescing Semantics / Atomic Admission


Purpose: prevent refresh/reopen/reuse request floods without suppressing evidence
that was never actually admitted to the queue.

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

Normal successful-admission window:

```text
21600 seconds = 6 hours
```

Atomic request-path admission is EXACTLY:

```text
1. acquire coalescer lock NON-BLOCKING

2. bounded expiry cleanup <=32 entries

3. check duplicate key

4. if duplicate:
   portal_evidence_coalesced += 1
   return without queue admission

5. create source_event_id if needed and construct normalized queue item

6. call queue.put_nowait(...) while admission remains serialized

7. ONLY if put_nowait succeeds:
   commit/update coalescer key with normal 6-hour expiry

8. if queue.Full:
   DO NOT create or retain the coalescer entry
   portal_evidence_drop_queue_full += 1
   discard the UUID/event
   return

9. release coalescer lock
```

Permanent invariant:

```text
QUEUE REJECTION MUST NEVER POISON THE 6-HOUR COALESCE WINDOW
```

---

# 37. Coalescer Bounds / Non-Blocking Rule


```text
max entries = 8192
clock = time.monotonic()
max expired entries removed per request-path submit = 32
```

At capacity before a successful new admission:

```text
evict oldest key
```

Coalescer lock acquisition from the request path is NON-BLOCKING.
If contended:

```text
drop evidence
portal_evidence_drop_coalescer_busy += 1
continue request
```

No raw UA/CH in coalescer.

Coalescer entries store only:

```text
site_id
canonical MAC
source_subtype
normalized payload SHA256
monotonic expiry
```

Background delivery code may use the same lock to shorten expiries; request
threads never wait for it.

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

Full queue follows the atomic section-36 rule and creates NO coalescer entry.

No persistent portal spool.

Internal queue item is a bounded record:

```text
QueuedPortalEvidence:
  event = fully normalized Task-01 evidence event
  coalescer_key = bounded key from section 36
```

The key is internal delivery metadata only and is not sent to Task-01.

Never queue:

```text
raw User-Agent
raw Client Hints
Flask request
cookies
full URL
Authorization header
Accept-Language
```

---

# 39. create_app Composition + Dedicated Worker


`app/web/web.py` freezes an explicit injectable seam:

```python
_AUTO_PORTAL_EVIDENCE = object()

def create_app(
    ...,
    portal_evidence_sink=_AUTO_PORTAL_EVIDENCE,
) -> Flask:
    ...
```

Composition semantics:

```text
INJECTED SINK:
use exactly the supplied sink
do not auto-read Task-03 config
do not auto-create Task-03 runtime/worker

_AUTO + disabled config:
NULL sink
no worker thread
no Task-03 IO

_AUTO + enabled + valid config:
create bounded in-memory runtime
start exactly one daemon worker

_AUTO + enabled + invalid config:
sanitized Task-03 telemetry
NULL sink
core Flask startup continues

_AUTO + worker start failure:
sanitized Task-03 telemetry
NULL sink
core Flask startup continues
```

Task-03 config is read directly from environment through the isolated Task-03
config module.

Composition/startup MUST NOT perform:

```text
credential file read
CA file read
HTTP request
Task-01 health check
SQLite access
fingerprint DB scan
network wait
```

Dedicated worker:

```text
name = device-fingerprint-portal
thread = daemon
count = exactly one when enabled/valid
```

It is separate from AuthWorker executor and all existing worker pools.
The worker blocks waiting for the in-memory queue.

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

Each drained item retains its internal `coalescer_key` until delivery outcome is
known so section-41 expiry correction can be applied.

Availability principle:

```text
Authorization availability > fingerprint completeness
```

---

# 41. Delivery Cooldowns / Coalescer Expiry Interaction


Normal successful evidence delivery:

```text
coalescer entries represented by the delivered batch
retain their normal 6-hour expiry
```

Transient failure:

```text
connection error
TLS transient error
timeout
500
503
```

sets:

```text
cooldown = 30 seconds
```

For EVERY coalescer key represented by that failed batch:

```text
entry expiry = min(current expiry, transient cooldown deadline)
```

429:

```text
valid Retry-After 1..60 seconds
→ cooldown = Retry-After

otherwise
→ cooldown = 30 seconds
```

Affected key expiry is shortened to the resolved cooldown deadline.

Permanent-class rejection:

```text
400 401 403 404 405 409 413
→ drop batch
→ local producer_rejected
→ cooldown = 300 seconds
```

Affected key expiry is shortened to the 300-second rejection-cooldown deadline.

Background shortening uses the same coalescer lock. Request-path callers remain
non-blocking and drop on lock contention.

During an active delivery cooldown:

```text
NO Task-01 HTTP attempt is made
```

Queued events discarded because the worker is already inside that cooldown also
have any committed coalescer entry shortened to the same cooldown deadline.

Therefore:

```text
identical requests during cooldown
remain coalesced/dropped
and create no HTTP attempt
```

After the shortened expiry/cooldown deadline passes:

```text
the next otherwise-eligible identical portal request
may generate and enqueue a new event
```

No persistent retry backlog is introduced.
No infinite latch is introduced.

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

Config semantics are consumed only by the `_AUTO_PORTAL_EVIDENCE` composition
path from section 39.

Disabled:

```text
NULL sink
no worker
no Task-03 IO
```

Enabled + invalid config:

```text
sanitized telemetry
NULL sink
core CaptivPortal startup continues
```

Injected sink bypasses automatic Task-03 config/runtime composition entirely.

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

# 45. Source Health — Exact Epoch / Stale-Recovery Semantics


Scope:

```text
source_kind = portal_headers
site_id = 6a64f17630da7c70d232187a
capture_source_id = zefer-portal-http-01
```

Malformed/missing UA/CH is evidence completeness, not source-unavailable state.

No periodic heartbeat in V1.
Silence is allowed and does not mean unavailable.

Local health state begins:

```text
unknown
```

## Initial available epoch

First successful EVIDENCE delivery in a runtime health epoch:

```text
→ evidence delivery result remains SUCCESS
→ perform one bounded best-effort source-health attempt:
   available
   reason_code = null
   observed_at = successful-delivery time
```

This available attempt occurs once per local health epoch, not on every batch.

## First transient failure

On the first transient evidence-delivery failure while not already unavailable:

```text
remember in memory:
unavailable_started_at = first-failure UTC time

reason = ingest_delivery_unavailable

local health state = unavailable
```

Subsequent failures while already unavailable do not move the remembered first
failure time.

## Recovery while remembered timestamp is still valid

Task-01 frozen maximum delayed-event age:

```text
86400 seconds
```

After a later successful EVIDENCE delivery, if:

```text
recovery_time - unavailable_started_at <= 86400 seconds
```

perform one bounded best-effort source-health batch:

```text
unavailable
observed_at = first-failure time
reason_code = ingest_delivery_unavailable

available
observed_at = recovery time
reason_code = null
```

Then local health state becomes available.

## Recovery after stale remembered timestamp

If:

```text
recovery_time - unavailable_started_at > 86400 seconds
```

then:

```text
DO NOT send the stale unavailable event
DO NOT create a source-health batch that Task-01 must reject

discard stale unavailable history
attempt available(recovery_time) only
local health state = available
```

## Source-health failure isolation

Any source-health submission failure:

```text
MUST NOT change an already-successful evidence-delivery result
MUST NOT change portal/auth result
MUST NOT create request-thread work
MUST NOT create a retry backlog
```

Source-health submission is best-effort background work only.

Permanent-class producer rejection remains local `producer_rejected`; central
health may be absent if the same Task-01 boundary rejects it.

Worker-start failure:

```text
local sanitized telemetry only
no request-thread fallback delivery
```

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

Exact parser grammar tests MUST include:

```text
sec-ch-ua-platform:
valid quoted known platform
valid quoted unknown platform
malformed unquoted
malformed escape
malformed list/parameter
OWS only SP/HTAB

sec-ch-ua-mobile:
OWS ?1 OWS
OWS ?0 OWS
all other forms unavailable

sec-ch-ua:
valid one/multi brand list
Chromium aliases collapse
Android WebView precedence
unknown/GREASE ignored
malformed item poisons whole header
extra parameter rejected
trailing comma rejected
conflicting recognized families resolve exactly per section 28

UA:
explicit Android WebView `; wv)`
ordered Version/4.0 + Chrome + Mobile Safari WebView rule
captive-helper exact tokens
Android model exact field grammar
locale + model exact grammar
Build ID never persisted
multiple model candidates → null
Android/iOS OS-major exact grammar
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


Prove:

```text
same Site+MAC+subtype+payload within 6h → one event
same payload + different MAC → separate
same MAC + changed normalized payload → separate
same MAC/payload + different subtype → separate
after 6h → new event
cache <= 8192
expiry work <=32 per request-path submit
```

Atomic queue/coalescer proof:

```text
queue has capacity
→ put_nowait succeeds
→ coalescer key committed

queue full
→ put_nowait raises queue.Full
→ NO coalescer entry retained
→ next eligible identical request is not poisoned for 6h
```

Delivery-outcome expiry proof:

```text
success → normal 6h expiry retained
transient failure → affected expiry shortened to 30s deadline
429 → affected expiry shortened to resolved Retry-After/cooldown deadline
permanent reject → affected expiry shortened to 300s deadline
post-cooldown identical request → may emit again
```

---

# 59. Authorization Ordering / Hard-Containment / Composition Tests


Using injected fake executor and sink:

```text
AuthWorker submission happens before evidence try_submit
worker-start failure → evidence try_submit not called
sink exception → existing portal/auth result unchanged
queue full → request continues
coalescer lock busy → request continues
```

Route-level extractor containment:

```text
GET / parser raises
→ existing valid portal flow unchanged

CAPPORT parser raises
→ existing valid CAPPORT login flow unchanged
```

External guard proof:

```text
missing site / missing client identity
→ existing guard response
→ extractor NOT called
```

Composition seam:

```text
injected sink → no auto Task-03 composition
_AUTO + disabled → NULL sink / no worker / no IO
_AUTO + invalid → NULL sink / Flask app still created
_AUTO + worker-start failure → NULL sink / Flask app still created
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

Verify:

```text
failed batch is dropped
no synchronous retry
exact cooldown classification
coalescer expiry shortened for failed-batch keys
no HTTP attempt during active cooldown
post-cooldown identical event may be admitted again
```

Source-health tests:

```text
malformed UA/CH != unavailable

first successful evidence delivery
→ one available attempt for initial health epoch

first transient failure
→ remember first unavailable timestamp only once

recovery <=86400s
→ unavailable(first-failure) + available(recovery) attempt

recovery >86400s
→ stale unavailable discarded
→ available(recovery) only

source-health submission failure
→ evidence delivery result remains unchanged
→ portal/auth unchanged

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
External GET / guard precedes Task-03 extraction
CAPPORT resolved-client gate precedes Task-03 extraction
route extractor exception containment local
PortalEntry sink exception containment local
AuthWorker-before-evidence ordering
no request-path HTTP
no request-path credential IO
atomic queue/coalescer admission
queue rejection cannot poison 6h window
failed-delivery expiry shortening exact
bounded/non-blocking request-path queue/coalescer
raw UA/CH never queued/persisted/logged
Accept/Accept-Language excluded
high-entropy CH absent
exact parser grammar
portal_headers/1 exact schema
producer identity exact
Task-01 registry extension exact
create_app injectable seam exact
no startup credential/CA/HTTP IO
source-health stale-recovery semantics exact
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
External GET / rejected guard does NOT parse evidence
Task-01 HTTPS/Bearer acceptance
portal_headers/1 validation
canonical MAC/Site/IP envelope
source subtype
exact parser grammar
atomic coalescer/queue behavior
Task-01 P1 DB row
zero raw UA/CH persistence
```

No production deployment required.

---

# 65. Gate E — Failure Isolation


Prove separately:

```text
Task-03 disabled
invalid Task-03 config
worker absent/start failure
route extractor raises
sink try_submit raises
queue full
coalescer lock busy
credential unreadable
Task-01 evidence service stopped
TLS failure
Task-01 503
Task-01 401/403
source-health submission failure
background producer blocked
```

For every case:

```text
existing Portal HTTP result unchanged
AuthSession semantics unchanged
AuthWorker scheduling functional when it otherwise would be
CAPPORT response semantics unchanged
fingerprint failure does not alter authorization result
```

---

# 66. Gate F — Request-Path Non-Blocking Proof


Structural proof:

```text
no requests.post in app/web/** request path
no requests.post in app/capport/** request path
no credential/CA file read in request path
no blocking coalescer lock acquisition
no blocking queue put
only bounded parser + non-blocking admission
```

Call-site containment proof:

```text
extractor exceptions contained at route
sink exceptions contained inside PortalEntryHandler before outer broad handler
```

Synchronization proof:

```text
background producer intentionally blocked
AuthWorker scheduled
portal response completes before producer release
```

No numeric latency SLO is invented in this FINAL.

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

# 68. Gate H — Flood / Coalescing / Cooldown


Send >=100 identical eligible portal-entry requests for same Site/MAC/subtype/payload inside the normal 6h window.

Expected after successful first admission/delivery:

```text
1 normalized event accepted
remaining eligible duplicates coalesced
```

Change one normalized evidence field:

```text
new event emitted immediately
```

Queue-rejection case:

```text
force queue full on first candidate
→ no coalescer poison
→ release capacity
→ next identical request may enqueue immediately
```

Delivery-failure case:

```text
admit event
force transient/permanent-class failure
→ affected coalescer expiry shortened to exact cooldown deadline
→ no Task-01 attempt during cooldown
→ next identical request after cooldown may generate a new event
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

# 70. FINAL Control Status

```text
TASK = TASK-DEVICE-FINGERPRINT-03-FINAL
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

ARCHITECTURE = PASS
TECHNICAL CONTRACT = COMPLETE

CURRENT GATE = TECHLEAD10 FINAL CONSISTENCY REVIEW
TECHLEAD10 FINAL PASS = PENDING
OWNER IMPLEMENTATION AUTHORIZATION = NOT GRANTED

IMPLEMENTATION-READY = PENDING TECHLEAD10 FINAL PASS
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

# 71. Next Workflow

```text
TASK-DEVICE-FINGERPRINT-03-FINAL
        ↓
TechLead10 FINAL consistency review
        ↓
FINAL PASS
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

**End of TASK-DEVICE-FINGERPRINT-03-FINAL.**

