# TASK-DEVICE-FINGERPRINT-01-FINAL

## Passive Mobile / Personal Device Fingerprint Evidence Foundation

**Project:** CaptivPortal  
**Program:** Passive Mobile / Personal Device Fingerprinting  
**Research predecessor:** `DEVICE-FINGERPRINT-00 FINAL R2`  
**Parent task:** `TASK-DEVICE-FINGERPRINT-01`  
**Revision:** `FINAL`  
**Status:** `FINAL — FOR TECHLEAD10 CONSISTENCY RECHECK / OWNER IMPLEMENTATION AUTHORIZATION`  
**Implementation-ready:** `YES — CONTRACT COMPLETE; EXECUTION NOT YET AUTHORIZED`  
**Implementation authorization:** `NOT GRANTED`  
**Coder:** `HOLD`  
**Branch / commit / push / PR / deploy:** `NOT AUTHORIZED`  
**Prepared:** 2026-09-14

---

# 0. FINAL Control Gate


```text
DEVICE-FINGERPRINT-00 =
CLOSED / DO NOT REOPEN

R7 =
TECHLEAD10 PASS

FIX-1…FIX-25 =
CLOSED / ACCEPTED / PRESERVED

OWNER VALUES =
FROZEN

INFRA VALUES =
FROZEN

TASK-DEVICE-FINGERPRINT-01-FINAL =
ASSEMBLED

ARCHITECTURE =
PASS

NEW RESEARCH =
NOT REQUIRED

NEW DRAFT REVISION =
NOT REQUIRED

IMPLEMENTATION CONTRACT =
COMPLETE

TECHLEAD10 FINAL CONSISTENCY PASS =
PENDING

OWNER EXPLICIT IMPLEMENTATION AUTHORIZATION =
NOT GRANTED

CODER =
HOLD
```

This FINAL is the complete implementation contract for Task-01.

It does NOT itself authorize:

```text
implementation
branch
commit
push
PR
merge
deploy
activation
```

Coder implementation may begin only after:

```text
1. TechLead10 FINAL consistency PASS

AND

2. Owner explicit implementation authorization
```

---

# 1. Final Repository / Research Baseline


Repository:

```text
ZaurNavi/CaptivePortal
```

Fresh `main` recheck immediately before FINAL assembly:

```text
HEAD =
14ab4034dd9fe170b33795322c29c543bf6c2544

TREE =
f328a665ef08a76c7f14a36a1a2e45d47c230468
```

Research runtime/code parent:

```text
3dc85735ddf5d05dd20733d15dfe1c22c9c4fde5
```

Status:

```text
material runtime drift =
NO

research/runtime rebind =
VALID

DEVICE-FINGERPRINT-00 =
CLOSED / DO NOT REOPEN
```

Before actual Coder implementation starts, TechLead10 must still perform the normal fresh implementation-baseline rebind and record the exact baseline commit/tree in the implementation handoff.

If `main` materially drifts before implementation authorization:

```text
STOP
→ Tech Lead source rebind
```

Do not silently implement against an unreviewed baseline.

---

# 2. Frozen Program Boundary

Task-01 is only:

```text
PASSIVE EVIDENCE FOUNDATION
```

Task-01 owns:

```text
strict configuration

dedicated auxiliary HTTP process

schema-registry mechanism

authenticated evidence ingest

authenticated source-health ingest

canonical validation

idempotent atomic persistence

separate SQLite storage

bounded read service

retention

runtime health

safe telemetry

service lifecycle
```

Task-01 does NOT implement:

```text
packet capture

Suricata installation

SPAN configuration

DHCP parser

TCP SYN parser

TLS/QUIC producer

Portal producer

classification

identity integration

Device Card

Analytics fingerprint products
```

---

# 3. Frozen Domain Ownership

```text
Visitor Registry
→ device_id / Registry device identity

Visit Lifecycle
→ visit_id / Site Visit chronology

Authorization/session owner
→ auth_session_id

Observation
→ Omada/controller historical observations

Current State
→ current wireless state

Device Fingerprint Evidence
→ NEW normalized passive evidence

Future Task-04
→ derived classification

Future Task-05
→ exact Site-safe identity/classification integration

Future Task-06
→ Device Card / Admin presentation
```

Task-01 does NOT become identity owner.

---

# 4. Frozen Acquisition Identity — FIX-1

Task-01 durable acquisition identity is:

```text
site_id
+
observed_mac
+
observed_at
```

Task-01 evidence rows contain NO:

```text
device_id
visit_id
auth_session_id
```

Task-01 introduces NO:

```text
bare-MAC Registry resolver

Visit resolver

auth-session resolver

evidence_identity_links table
```

Permanent rules:

```text
bare Registry MAC match != Site proof

last_site_id != permanent Site membership proof

unresolved = valid

no fuzzy nearest-device resolution

no cross-Site MAC inference

no cross-MAC fingerprint similarity resolution
```

Exact identity integration is deferred to:

```text
TASK-DEVICE-FINGERPRINT-05
```

---

# 5. V1 Packet Sensor Topology

Frozen architecture:

```text
D — SEPARATE PHYSICAL SENSOR
```

Conceptual:

```text
Catalyst trusted passive mirror/feed
        ↓
separate physical packet sensor
        ↓
Task-02 normalized evidence producer
        ↓
HTTPS management transport
        ↓
fingerprint-evidence.service
```

Task-01 does NOT implement the sensor.

A VM/existing-host packet sensor is not an equal unproven V1 option.

---

# 6. Entrypoint Governance — FIX-23


Task-01 authorizes exactly one auxiliary process composition root:

```text
python3 -m app.device_fingerprint.cli run
```

for:

```text
fingerprint-evidence.service
```

`run.py` remains NO-TOUCH and remains the main CaptivPortal composition root.

## `.github/instructions/python.instructions.md`

Replace the current absolute entrypoint invariant with exactly:

```text
run.py remains the process entrypoint
for captive-portal.service / main CaptivPortal runtime.

Auxiliary service process entrypoints are forbidden
unless explicitly authorized by an approved TASK/architecture contract.

An authorized auxiliary CLI is a separate composition root
and MUST NOT be registered into the main run.py runtime.
```

## `AGENTS.md`

Replace the current absolute architectural invariant with exactly:

```text
run.py is the process entrypoint and
top-level lifecycle/composition root
for captive-portal.service / main CaptivPortal runtime.

Auxiliary service process entrypoints are forbidden
unless explicitly authorized by an approved TASK /
architecture contract.

An authorized auxiliary service entrypoint is an
independent composition root and MUST NOT be registered
into run.py or the main CaptivPortal Flask runtime.
```

For Task-01 the authorized exception remains exactly:

```text
python3 -m app.device_fingerprint.cli run
```

No other auxiliary entrypoint is authorized by this TASK.

The dedicated fingerprint Flask app remains separate from:

```text
run.py
app/web/web.py:create_app()
captive-portal.service
```

---

# 7. HTTP Runtime Pattern — FIX-7

Use the existing project Flask/Werkzeug runtime family.

Exact service runtime:

```python
app.run(
    host=config.bind_address,
    port=config.port,
    debug=False,
    use_reloader=False,
    threaded=True,
    ssl_context=(config.tls_cert_path, config.tls_key_path),
    request_handler=DeviceFingerprintSafeRequestHandler,
)
```

The API itself additionally enforces a:

```text
BoundedSemaphore(
    max_concurrent_ingest_requests
)
```

for ingest endpoints.

Do NOT introduce:

```text
FastAPI
aiohttp
gunicorn
uWSGI
another HTTP framework/server
```

inside Task-01.

Any future HTTP-server replacement requires separate review.

---

# 8. Direct TLS Ownership — FIX-7 FROZEN

V1 freezes:

```text
TLS TERMINATION =
DIRECTLY IN fingerprint-evidence.service
```

No reverse proxy in V1.

Therefore authoritative source peer input is:

```text
request.remote_addr
```

from the direct TLS TCP connection.

The service MUST ignore for authorization:

```text
X-Forwarded-For
Forwarded
X-Real-IP
arbitrary proxy headers
```

They are not trusted.

Management-network authorization requires BOTH:

```text
network/firewall restriction
+
application CIDR allowlist
```

If infrastructure cannot support direct TLS, return to Architect/Tech Lead.

Coder must not substitute a proxy.

---

# 9. API Namespace / Exact Methods — FIX-25


Frozen:

```text
API_VERSION =
device-fingerprint.internal.v1

API_PREFIX =
/api/internal/device-fingerprint/v1
```

Exactly three V1 endpoints/methods exist:

```text
POST /api/internal/device-fingerprint/v1/evidence/batch

POST /api/internal/device-fingerprint/v1/source-health/batch

GET  /api/internal/device-fingerprint/v1/health
```

No other HTTP method is part of V1.

In particular there is NO implicit API contract for:

```text
GET /evidence/batch
GET /source-health/batch
POST /health
PUT
PATCH
DELETE
OPTIONS
HEAD
```

Routes must disable/override automatic behavior as necessary so unsupported methods under this namespace are returned through the exact fingerprint JSON error contract rather than Flask/Werkzeug default HTML.

Unknown path under:

```text
/api/internal/device-fingerprint/v1/*
```

uses the same protected namespace error contract.

No public captive-portal route.
No Admin browser route.

---

# 10. Request Logging Safety

`DeviceFingerprintSafeRequestHandler` must strip query strings for the entire fingerprint namespace.

Logged request line for:

```text
/api/internal/device-fingerprint/v1/*
```

contains:

```text
METHOD + path + protocol
```

and never:

```text
query string
Bearer
request JSON
payload content
```

Request bodies are not access-logged.

---

# 11. Security Headers

All Task-01 API responses include:

```text
Cache-Control: no-store
Pragma: no-cache
X-Content-Type-Options: nosniff
```

Authentication credentials are never reflected.

---

# 12. V1 Protection Order — FIX-3/FIX-7/FIX-25


For ANY request under:

```text
/api/internal/device-fingerprint/v1/*
```

the protection order is exactly:

```text
1. create central request_id

2. reject forbidden query credential names
   case-insensitively:
   token
   access_token
   bearer_token

3. parse + authenticate:
   Authorization: Bearer <credential>

4. authorize direct peer:
   request.remote_addr
   against management CIDR allowlist

5. route / method enforcement:
   unknown path → 404 not_found
   known path + unsupported method → 405 method_not_allowed

6. endpoint-specific validation/authorization
```

For POST ingest after routing/method pass:

```text
validate body producer_id
validate capture_source_id
validate site_id
validate source_kind
```

No proxy header participates in authorization:

```text
X-Forwarded-For
Forwarded
X-Real-IP
```

Missing/invalid credential:

```text
401 invalid_credential
WWW-Authenticate: Bearer
```

Authenticated direct peer outside allowed management networks:

```text
403 source_network_forbidden
```

The namespace MUST NOT expose unauthenticated Flask/Werkzeug 404/405 HTML pages.
Unknown-path/method information is disclosed only after credential + direct-peer network authorization.

---

# 13. Bearer Credential Contract — FIX-15 COMPLETE


Each configured producer Bearer secret must satisfy exactly:

```text
[A-Za-z0-9_-]{32,256}
```

Therefore:

```text
32..256 ASCII characters
base64url-safe alphabet only

NO Unicode
NO spaces
NO tabs
NO control characters
NO silent trimming
```

Authentication syntax:

```text
Authorization: Bearer <credential>
```

Scheme is exactly:

```text
Bearer
```

Malformed header, wrong scheme, non-ASCII credential, or credential failing the regex:

```text
401
```

For syntactically valid credentials, authentication checks every configured producer secret using:

```python
hmac.compare_digest
```

and resolves exactly one matching producer.

Do NOT use a plaintext-token dictionary lookup as the authorization decision.

Duplicate configured secrets:

```text
CONFIG ERROR
```

Secrets are:

```text
generated outside Git
never accepted in query string
never logged
redacted from repr/config telemetry
```

---

# 14. Producer Identifier Formats — FIX-11

Machine identifier regex:

```text
producer_id =
[a-z0-9][a-z0-9._-]{0,63}

capture_source_id =
[a-z0-9][a-z0-9._-]{0,63}
```

Rules:

```text
1..64 ASCII characters

lowercase only

no silent case conversion

no whitespace

no path separators
```

Duplicate producer IDs:

```text
CONFIG ERROR
```

Duplicate capture source IDs across V1 producer entries:

```text
CONFIG ERROR
```

V1 binds one configured producer to one capture source.

---

# 15. Source Kind / Subtype Formats

```text
source_kind =
[a-z][a-z0-9_]{0,63}
```

```text
source_subtype =
NULL
or
[a-z0-9][a-z0-9._-]{0,63}
```

No silent case conversion.

Unknown evidence schema:

```text
FAIL CLOSED
```

---

# 16. Extractor / Version Formats

```text
extractor_name =
[a-z0-9][a-z0-9._-]{0,63}
```

```text
extractor_version =
[0-9A-Za-z][0-9A-Za-z._+-]{0,63}
```

```text
feature_schema_version =
INTEGER
1..2147483647
```

```text
rule_version =
NULL
or
[0-9A-Za-z][0-9A-Za-z._+-]{0,63}
```

No arbitrary unbounded strings.

---

# 17. UUID Contracts — FIX-11

Use the repository canonical UUID contract:

```text
lowercase canonical UUID string
xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

length =
36
```

Accepted UUID version:

```text
any UUID version accepted
if canonical lowercase representation is exact
```

Producer guidance:

```text
uuid4 recommended
```

Fields:

```text
source_event_id =
producer-owned
created ONCE before spool/delivery

source_health_event_id =
producer-owned
created ONCE before spool/delivery

evidence_id =
central service-owned uuid4

source_health_id =
central service-owned uuid4
```

Retry never regenerates producer event IDs.

---

# 18. Site ID Contract

Exact:

```text
site_id =
24 lowercase hexadecimal characters
```

Regex:

```text
[0-9a-f]{24}
```

No:

```text
silent lowercasing
Site-name substitution
Site inference from packet content
```

Invalid Site ID:

```text
400
```

Authorized producer sending another valid Site:

```text
403
```

---

# 19. MAC Contract

`observed_mac` is REQUIRED for Task-01 device evidence.

Canonical durable format:

```text
AA:BB:CC:DD:EE:FF
```

Use existing:

```text
app.common.mac.parse_mac
app.common.mac.format_mac_colon
```

Input accepted through the shared parser may use a supported separator form.

Storage is always uppercase colon-separated.

Privacy class:

```text
P1 / MODERATE
```

---

# 20. IP Contract

`observed_ip`:

```text
NULL
or canonical Python ipaddress representation
```

Canonicalization:

```text
ipaddress.ip_address(value)
→ str(...)
```

Privacy:

```text
P1 / MODERATE
```

Task-01 accepts no IP-only evidence identity.

`observed_mac` remains required.

No common durable:

```text
destination_ip
```

field exists.

---

# 21. Timestamp Contract — FIX-2

All timestamps:

```text
YYYY-MM-DDTHH:MM:SS.mmmZ
```

Fixed UTC milliseconds.

```text
observed_at =
producer observation time

ingested_at =
central service time
```

Producer must be time-synchronized.

No timezone assumption.

No variable microsecond precision.

---

# 22. Clock Bounds — OWNER FROZEN


Owner explicitly freezes:

```text
DEFAULT_MAX_FUTURE_SKEW_SECONDS =
120

DEFAULT_MAX_DELAYED_EVENT_AGE_SECONDS =
86400
```

Runtime config fields:

```text
config.max_future_skew_seconds
config.max_delayed_event_age_seconds
```

Repository defaults are therefore:

```text
120 seconds
86400 seconds / 24 hours
```

Validation against central UTC now:

```text
observed_at > now + config.max_future_skew_seconds
→ 400 invalid_request

observed_at < now - config.max_delayed_event_age_seconds
→ 400 invalid_request
```

No degraded acceptance.

Privacy retention age always starts from:

```text
observed_at
```

not `ingested_at`.

---

# 23. Configuration Pipeline — FIX-3/FIX-11

Only:

```text
app/config.py
        ↓
app/settings.py
        ↓
app/device_fingerprint/config.py
        ↓
DeviceFingerprintConfig
```

No hidden reuse of:

```text
OBSERVATION_SITE_IDS
CURRENT_STATE_SITE_IDS
```

No packet-derived Site authority.

---

# 24. Exact Environment Variable Names — FIX-11/FIX-14


Task-01 environment names are frozen:

```text
DEVICE_FINGERPRINT_EVIDENCE_ENABLED

DEVICE_FINGERPRINT_DB_PATH
DEVICE_FINGERPRINT_WRITER_LOCK_PATH

DEVICE_FINGERPRINT_BIND_ADDRESS
DEVICE_FINGERPRINT_PORT

DEVICE_FINGERPRINT_TLS_CERT_PATH
DEVICE_FINGERPRINT_TLS_KEY_PATH

DEVICE_FINGERPRINT_API_ALLOWED_NETWORKS
DEVICE_FINGERPRINT_PRODUCERS_JSON

DEVICE_FINGERPRINT_RETENTION_DAYS

DEVICE_FINGERPRINT_MAX_FUTURE_SKEW_SECONDS
DEVICE_FINGERPRINT_MAX_DELAYED_EVENT_AGE_SECONDS

DEVICE_FINGERPRINT_MAX_DB_BYTES
DEVICE_FINGERPRINT_MAX_HTTP_REQUEST_BYTES
DEVICE_FINGERPRINT_MAX_EVENTS_PER_BATCH
DEVICE_FINGERPRINT_MAX_PAYLOAD_BYTES
DEVICE_FINGERPRINT_MAX_CONCURRENT_INGEST_REQUESTS
```

There is intentionally NO:

```text
DEVICE_FINGERPRINT_SOURCE_HEALTH_RETENTION_DAYS
```

in V1.

Source-health retention is the fixed repository constant:

```text
SOURCE_HEALTH_RETENTION_DAYS = 30
```

No Coder-defined alternative environment names.

---

# 25. Default Paths

Frozen:

```text
DEVICE_FINGERPRINT_DB_PATH =
/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3
```

```text
DEVICE_FINGERPRINT_WRITER_LOCK_PATH =
/opt/CaptivePortal/data/device_fingerprint_evidence.writer.lock
```

DB and lock paths must be:

```text
absolute
distinct
safe targets
```

No remote/network filesystem SQLite.

---

# 26. Fixed Repository Constants — FIX-21

These values are fixed repository constants in Task-01 V1:

```text
SCHEMA_VERSION = 1
BUSY_TIMEOUT_MS = 500
WAL_AUTOCHECKPOINT_PAGES = 1000
JOURNAL_SIZE_LIMIT_BYTES = 67_108_864
MAX_HTTP_RESPONSE_BYTES = 65_536
RETENTION_SCAN_INTERVAL_SECONDS = 300
RETENTION_DELETE_CHUNK_ROWS = 500
MAX_RETENTION_CHUNKS_PER_PASS = 20
SOURCE_HEALTH_RETENTION_DAYS = 30
SHUTDOWN_TIMEOUT_SECONDS = 20.0
```

They are NOT environment-overridable in V1.

Coder does not add aliases or alternate knobs.

---

# 27. Configurable Defaults + Runtime Config — OWNER FROZEN


Repository defaults for environment-configurable settings:

```text
DEFAULT_RETENTION_DAYS = 30

DEFAULT_MAX_FUTURE_SKEW_SECONDS = 120

DEFAULT_MAX_DELAYED_EVENT_AGE_SECONDS = 86400

DEFAULT_MAX_DB_BYTES = 1_073_741_824

DEFAULT_MAX_HTTP_REQUEST_BYTES = 1_048_576

DEFAULT_MAX_EVENTS_PER_BATCH = 100

DEFAULT_MAX_PAYLOAD_BYTES = 8_192

DEFAULT_MAX_CONCURRENT_INGEST_REQUESTS = 2
```

The first three values are now explicitly Owner-approved.

Each valid environment variable overrides ONLY its corresponding default.

Exact mapping remains:

```text
DEVICE_FINGERPRINT_RETENTION_DAYS
→ config.retention_days
→ DEFAULT_RETENTION_DAYS

DEVICE_FINGERPRINT_MAX_FUTURE_SKEW_SECONDS
→ config.max_future_skew_seconds
→ DEFAULT_MAX_FUTURE_SKEW_SECONDS

DEVICE_FINGERPRINT_MAX_DELAYED_EVENT_AGE_SECONDS
→ config.max_delayed_event_age_seconds
→ DEFAULT_MAX_DELAYED_EVENT_AGE_SECONDS

DEVICE_FINGERPRINT_MAX_DB_BYTES
→ config.max_db_bytes
→ DEFAULT_MAX_DB_BYTES

DEVICE_FINGERPRINT_MAX_HTTP_REQUEST_BYTES
→ config.max_http_request_bytes
→ DEFAULT_MAX_HTTP_REQUEST_BYTES

DEVICE_FINGERPRINT_MAX_EVENTS_PER_BATCH
→ config.max_events_per_batch
→ DEFAULT_MAX_EVENTS_PER_BATCH

DEVICE_FINGERPRINT_MAX_PAYLOAD_BYTES
→ config.max_payload_bytes
→ DEFAULT_MAX_PAYLOAD_BYTES

DEVICE_FINGERPRINT_MAX_CONCURRENT_INGEST_REQUESTS
→ config.max_concurrent_ingest_requests
→ DEFAULT_MAX_CONCURRENT_INGEST_REQUESTS
```

The only three layers for each configurable concept are:

```text
environment variable
→ config.<field>
→ DEFAULT_<FIELD>
```

No competing pseudo-constant alias.

---

# 28. Config Bounds — FIX-21

Strict runtime config bounds:

```text
config.retention_days:
1..90

config.max_future_skew_seconds:
0..600

config.max_delayed_event_age_seconds:
60..604800

config.max_db_bytes:
67_108_864 .. 8_589_934_592

config.max_http_request_bytes:
65_536 .. 4_194_304

config.max_events_per_batch:
1..500

config.max_payload_bytes:
256 .. 65_536

config.max_concurrent_ingest_requests:
1..8

config.port:
1..65535
```

Environment value outside its bound:

```text
CONFIG ERROR
```

No silent clamp.

---

# 29. Enabled / Disabled CLI Contract — FIX-13


Default:

```text
DEVICE_FINGERPRINT_EVIDENCE_ENABLED=false
```

Exact CLI `run` sequence begins:

```text
1. parse command
2. load get_settings()
3. build DeviceFingerprintConfig

4. if enabled == false:
       return exit status 0 immediately
```

Disabled exit performs:

```text
NO dedicated logger/runtime startup
NO artifact identity capture
NO writer lock
NO DB create/migrate
NO Flask app construction
NO TLS listener
NO long-running process
```

Intentional disable is NOT implemented through:

```text
argparse error
exception
exit 1
exit 2
```

because systemd uses:

```text
Restart=on-failure
```

and intentional disable is not a failure.

Only when enabled is true does enabled startup continue.

---

# 30. Producers JSON — INITIAL PRODUCER FROZEN


Exact environment:

```text
DEVICE_FINGERPRINT_PRODUCERS_JSON
```

Value is a JSON array containing:

```text
1..32 producer objects
when feature is enabled
```

Initial production foundation mapping is frozen as:

```json
{
  "producer_id": "sensor-zefer-01",
  "bearer_token": "<external-secret>",
  "capture_source_id": "zefer-span-01",
  "site_id": "6a64f17630da7c70d232187a",
  "allowed_guest_cidrs": ["192.168.8.0/22"],
  "allowed_source_kinds": ["dhcp", "tcp_syn", "tls_client", "quic_client"]
}
```

The actual `bearer_token` literal MUST NOT appear in:

```text
Git
TASK
PLAN
ADR
PR
handoff
tests
fixtures
chat documentation
logs
```

No extra object keys.

Validation remains:

```text
producer_id exact machine-id contract

bearer_token exact Bearer contract

capture_source_id exact machine-id contract

site_id exact 24 lowercase hex

allowed_guest_cidrs:
1..32 unique strict networks

allowed_source_kinds:
1..32 unique valid source-kind identifiers
```

Important:

```text
allowed_source_kinds
=
producer security authorization

NOT
EvidenceSchemaRegistry registration
```

Task-01 production EvidenceSchemaRegistry remains EMPTY.

Task-02 owns production schema registration.

Sensor `capture_interface` remains outside Task-01 central configuration.

---

# 31. Direct TLS Configuration — INFRA FROZEN


Direct TLS is mandatory.

Frozen paths:

```text
DEVICE_FINGERPRINT_TLS_CERT_PATH =
/etc/captive-portal/device-fingerprint/server.crt

DEVICE_FINGERPRINT_TLS_KEY_PATH =
/etc/captive-portal/device-fingerprint/server.key
```

Certificate requirement:

```text
SAN IP =
192.168.0.202
```

Paths must be:

```text
absolute
distinct
readable by service identity
```

The service starts NO plain-HTTP fallback.

If TLS material is missing, unreadable or invalid:

```text
startup FAIL
no listener
```

TLS material is provisioned outside Git.

No private key is copied into:

```text
/opt/CaptivePortal
Git
TASK
tests
fixtures
logs
```

Task-02 may later finalize producer trust/pinning details, but Task-01 server remains direct-TLS only.

---

# 32. Management Network Configuration — INFRA FROZEN


Frozen application allowlist:

```text
DEVICE_FINGERPRINT_API_ALLOWED_NETWORKS =
192.168.0.0/24
```

Parsing remains strict CIDR configuration.

`request.remote_addr` must fall inside the configured management allowlist.

Application CIDR authorization is mandatory even though the host firewall enforces the same initial `/24`.

Permanent:

```text
request.remote_addr =
authoritative application peer address

X-Forwarded-For =
NOT TRUSTED

Forwarded =
NOT TRUSTED

X-Real-IP =
NOT TRUSTED
```

Future Task-02 SHOULD evaluate narrowing both firewall and application access to the physical sensor `/32` once its management IP is frozen.

Task-01 does not invent that future `/32`.

---

# 33. Producer / Capture Authorization

Authenticated producer is bound to exactly:

```text
producer_id
capture_source_id
site_id
allowed_guest_cidrs
allowed_source_kinds
```

For evidence ingest:

```text
body producer_id
must equal authenticated producer

event capture_source_id
must equal configured producer capture_source_id

event site_id
must equal configured producer site_id

event source_kind
must be configured for producer

observed_ip, when present,
must belong to one configured guest CIDR
```

For source-health ingest:

```text
same producer/capture/Site/source authorization
```

No observed IP exists in source-health rows.

---

# 34. Task-01 Source Schema Ownership — FIX-9

Task-01 owns only:

```text
EvidenceSchemaRegistry mechanism

(source_kind, feature_schema_version)
dispatch

strict unknown-schema rejection

schema validator/canonicalizer interface
```

Task-01 production registry starts with:

```text
ZERO enabled device-evidence schemas
```

Therefore a Task-01-only deployment can legitimately run:

```text
health
source-health contract
repository/service smoke
```

while `/evidence/batch` fails closed for every unregistered schema.

---

# 35. Future Production Schema Ownership — FIX-9

Task-02 owns registration of:

```text
dhcp
tcp_syn
tls_client
quic_client
```

Task-03 owns registration of:

```text
portal_client
```

Optional tasks later own:

```text
dns_ecosystem
mdns_service
ipv6_stack
```

Task-01 Coder MUST NOT invent production payload schemas for these.

---

# 36. Test Schema Rule — FIX-9

Task-01 tests may inject explicit in-memory test schema definitions through `EvidenceSchemaRegistry`.

Rules:

```text
test registry injected by constructor/factory

test schema never registered by production builder

no fake production source_kind added only for tests

production registry remains empty in Task-01
```

This allows full ingest/idempotency testing without stealing Task-02/03 ownership.

---

# 37. Future Payload Sections Are Guidance Only

The previously researched DHCP/TCP/TLS/QUIC field candidates remain:

```text
FUTURE TASK-02 ARCHITECTURE GUIDANCE
```

They are NOT Task-01 production schemas.

Portal field candidates remain:

```text
FUTURE TASK-03 ARCHITECTURE GUIDANCE
```

No Task-01 implementation may register them.

---

# 38. Evidence Wire Contract — FIX-15 EXACT KEYS


`POST /evidence/batch` root JSON has EXACT keys:

```text
producer_id
events
```

No extra root keys.

Every evidence event has EXACTLY all 14 keys:

```text
source_event_id
source_kind
source_subtype
extractor_name
extractor_version
feature_schema_version
rule_version
site_id
capture_source_id
observed_at
observed_mac
observed_ip
quality_state
payload
```

All 14 keys MUST be present.

Nullable values are represented explicitly as JSON `null`:

```text
source_subtype
rule_version
observed_ip
```

Missing nullable keys are NOT equivalent to explicit null.

Extra event keys:

```text
400 invalid_request
```

`payload` must be a JSON object.

---

# 39. Evidence Wire Nullability / Required Values


Non-null required values:

```text
source_event_id
source_kind
extractor_name
extractor_version
feature_schema_version
site_id
capture_source_id
observed_at
observed_mac
quality_state
payload
```

Explicitly nullable but key-required:

```text
source_subtype
rule_version
observed_ip
```

Rules:

```text
null in a non-null field
→ 400

omitted one of the 14 event keys
→ 400

extra event key
→ 400
```

No Coder choice between missing nullable field and explicit null.

---

# 40. Evidence Quality State — FIX-6

Exact:

```text
valid
partial
degraded
```

No:

```text
available
unavailable
unsupported
```

on device evidence.

An accepted device row always means:

```text
a normalized observation actually occurred
```

---

# 41. Canonical Payload JSON — FIX-4/FIX-21

After source-schema validation, central service constructs canonical payload JSON exactly:

```python
json.dumps(
    approved_payload,
    ensure_ascii=True,
    allow_nan=False,
    sort_keys=True,
    separators=(",", ":"),
)
```

Then UTF-8 encode.

Forbidden:

```text
NaN
Infinity
-Infinity
unknown fields
producer-owned serialized JSON bytes
insignificant-whitespace authority
```

Maximum canonical UTF-8 payload size:

```text
config.max_payload_bytes
```

whose repository default is:

```text
DEFAULT_MAX_PAYLOAD_BYTES = 8_192
```

---

# 42. Server-Owned Payload Hash — FIX-4

Central service computes:

```text
payload_sha256 =
SHA-256(
    canonical payload UTF-8 bytes
)
```

Durable form:

```text
64 lowercase hexadecimal characters
```

Producer-supplied payload hash:

```text
NOT ACCEPTED
```

---

# 43. Evidence Retry Identity — FIX-4

Producer creates:

```text
source_event_id
```

exactly once before spool/delivery.

Retry reuses the exact same:

```text
producer_id
source_event_id
canonical immutable event content
```

Central uniqueness:

```text
UNIQUE (
    producer_id,
    source_event_id
)
```

This is transport retry idempotency only.

It is NOT SPAN/mirror packet dedup.

---

# 44. Retry Equality Contract

Immutable canonical evidence content consists of:

```text
producer_id
source_event_id
source_kind
source_subtype
extractor_name
extractor_version
feature_schema_version
rule_version
site_id
capture_source_id
observed_at
observed_mac
observed_ip
quality_state
payload_json
payload_sha256
```

Not part of producer retry equality:

```text
evidence_id
ingested_at
```

Same retry key + all immutable content equal:

```text
IDEMPOTENT SUCCESS / NO-OP
```

Same retry key + any immutable field different:

```text
409 CONFLICT
NEVER overwrite
```

---

# 45. Duplicate Keys Inside One Request

Within one submitted batch, duplicate:

```text
source_event_id
```

for the same authenticated producer is:

```text
400 invalid_request
```

even if the bodies are equal.

Producer must spool one logical event once.

This removes ambiguous within-batch counting.

---

# 46. Evidence Batch Atomicity — FIX-8

Atomicity rule:

```text
ONE STORAGE-ELIGIBLE REQUEST
=
ONE SQLite WRITE TRANSACTION
```

Request-level:

```text
HTTP framing
authentication
network ACL
JSON parse
root shape
batch/event count
canonical static validation
```

may reject before opening the database transaction.

If pre-validation passes:

```text
BEGIN IMMEDIATE
```

exactly once for the batch.

Within that transaction:

```text
check existing retry identities

classify:
new
or duplicate-noop
or conflict

INSERT all new rows
```

If any retry conflict appears:

```text
ROLLBACK ENTIRE TRANSACTION

NO new row from this batch persists

existing rows remain untouched
```

No per-item transaction.

No partial successful batch.

---

# 47. Evidence Batch Validation Failure

If ANY event has:

```text
invalid canonical field

producer/Site/capture/source mismatch

unsupported schema

forbidden field

invalid timestamp

invalid MAC/IP

oversized payload
```

then:

```text
whole request fails

NO new event from request persists
```

Static validation may fail before DB transaction.

Atomic outcome is still all-or-nothing.

---

# 48. Evidence Batch Success Counts

200 response may expose exactly:

```text
received
inserted
duplicate_noop
```

Counts are non-sensitive integers.

For success:

```text
received =
inserted + duplicate_noop
```

No event body/payload is echoed.

---

# 49. Exact HTTP Status + Error Code Contract — FIX-20/FIX-25


Exact fingerprint namespace error contract:

| HTTP | `error.code` | Exact public message |
|---:|---|---|
| 400 | `query_token_forbidden` | `Authentication credentials are not accepted in the query string.` |
| 400 | `invalid_request` | `The request is invalid.` |
| 400 | `unsupported_schema` | `The evidence schema is not supported.` |
| 401 | `invalid_credential` | `Authentication is required.` |
| 403 | `source_network_forbidden` | `The source network is not allowed.` |
| 403 | `producer_forbidden` | `The producer is not allowed.` |
| 403 | `site_forbidden` | `The Site is not allowed.` |
| 403 | `capture_source_forbidden` | `The capture source is not allowed.` |
| 403 | `source_kind_forbidden` | `The source kind is not allowed.` |
| 404 | `not_found` | `The requested fingerprint endpoint does not exist.` |
| 405 | `method_not_allowed` | `The method is not allowed for this endpoint.` |
| 409 | `idempotency_conflict` | `The request conflicts with an existing immutable event.` |
| 413 | `request_too_large` | `The request exceeds the allowed size.` |
| 429 | `concurrency_limit` | `Too many fingerprint requests are in progress.` |
| 500 | `internal_error` | `The fingerprint request failed.` |
| 503 | `runtime_unavailable` | `The fingerprint service is temporarily unavailable.` |
| 503 | `repository_unavailable` | `The fingerprint repository is temporarily unavailable.` |
| 503 | `storage_limit` | `The fingerprint repository storage limit was reached.` |
| 503 | `storage_corrupt` | `The fingerprint repository is unavailable.` |

Unexpected programming/serialization failure:

```text
500 internal_error
```

with sanitized telemetry and no exception detail in response.

Do NOT convert an unexpected application bug to 400 or repository_unavailable unless it objectively belongs there.

For 401 include:

```text
WWW-Authenticate: Bearer
```

For 429 include:

```text
Retry-After: 1
```

No Flask/Werkzeug default HTML error page may escape from the fingerprint API namespace.
No other V1 error code is emitted by these endpoints.

---

# 50. Exact POST / Health / Error Shapes — FIX-20/FIX-25


Every fingerprint API response is:

```text
JSON
bounded
non-sensitive
deterministic
```

and includes the Task-01 security headers.

## POST batch success — EXACT

Both POST batch endpoints return exactly:

```json
{
  "api_version": "device-fingerprint.internal.v1",
  "request_id": "<uuid>",
  "result": {
    "status": "ok",
    "received": 10,
    "inserted": 8,
    "duplicate_noop": 2
  }
}
```

No optional success fields.

## Error — EXACT

All 4xx/5xx fingerprint namespace errors, including 404/405, return exactly:

```json
{
  "api_version": "device-fingerprint.internal.v1",
  "request_id": "<uuid>",
  "error": {
    "code": "<exact code from section 49>",
    "message": "<exact message from section 49>"
  }
}
```

409 specifically is exactly:

```json
{
  "api_version": "device-fingerprint.internal.v1",
  "request_id": "<uuid>",
  "error": {
    "code": "idempotency_conflict",
    "message": "The request conflicts with an existing immutable event."
  }
}
```

No conflict_count, optional conflict metadata, payload echo, secret echo, raw exception, SQL text or filesystem secret path.

## GET /health — EXACT

```json
{
  "api_version": "device-fingerprint.internal.v1",
  "request_id": "<uuid>",
  "result": {
    "status": "ready",
    "reason": null,
    "artifact_identity": {
      "artifact_sha": "<40hex>",
      "artifact_tree": "<40hex>",
      "service_name": "fingerprint-evidence.service",
      "process_started_at": "<utc-ms>"
    },
    "schema_version": 1,
    "evidence_retention_days": 30,
    "source_health_retention_days": 30,
    "last_successful_retention_at": null
  }
}
```

`evidence_retention_days` is actual `config.retention_days`.
`source_health_retention_days` is exactly `SOURCE_HEALTH_RETENTION_DAYS`.
`last_successful_retention_at` is null or canonical UTC-ms.

`result.status` exactly one of:

```text
initializing
ready
degraded
unavailable
stopping
```

`reason` is null or an exact runtime reason_code.

---

# 51. Source Health Is Point-in-Time Events — FIX-10

Task-01 source-health model is exactly:

```text
immutable point-in-time source-health observation
at observed_at
```

It is NOT an interval model.

Scope:

```text
site_id
capture_source_id
source_kind
```

State:

```text
available
unavailable
unsupported
```

Silence:

```text
!= unavailable
```

Stale last health event:

```text
!= continuous unavailable

!= device evidence
```

---

# 52. Source Health Wire Contract — FIX-15


`POST /source-health/batch` exact root keys:

```text
producer_id
events
```

Every source-health event has EXACTLY:

```text
source_health_event_id
site_id
capture_source_id
source_kind
status
reason_code
observed_at
```

All seven keys MUST be present.

Nullable:

```text
reason_code
```

must be explicit JSON `null` when absent.

No extra event keys.

Within one submitted source-health batch, duplicate:

```text
source_health_event_id
```

for the authenticated producer is:

```text
400 invalid_request

whole request rejected

NO DB write
```

even when duplicate bodies are identical.

---

# 53. Source Health Reason Code

`reason_code`:

```text
NULL
or
[a-z0-9][a-z0-9._-]{0,63}
```

Examples may later include:

```text
capture_unavailable
parser_unavailable
unsupported_platform
```

Task-01 does not require a closed production reason taxonomy beyond format.

Do not put raw exception text in reason_code.

---

# 54. Source Health Canonical Hash + Idempotency — FIX-15


Producer creates `source_health_event_id` once before spool/delivery.

Central uniqueness:

```text
UNIQUE (
    producer_id,
    source_health_event_id
)
```

Canonical immutable health content is exactly:

```text
producer_id
source_health_event_id
site_id
capture_source_id
source_kind
status
reason_code
observed_at
```

Canonicalization is exactly:

```python
json.dumps(
    immutable_health_content,
    ensure_ascii=True,
    allow_nan=False,
    sort_keys=True,
    separators=(",", ":"),
)
```

then UTF-8 and SHA-256.

`content_sha256` is 64 lowercase hex.

Same retry key + same canonical content:

```text
200 duplicate NO-OP
```

Same retry key + different canonical content:

```text
409
NO overwrite
```

Producer does not supply the durable content hash.

---

# 55. Source Health Batch Atomicity

Same philosophy as device evidence.

After request/auth/static validation:

```text
one BEGIN IMMEDIATE transaction
```

All new health events insert together.

Idempotent duplicates are no-op success.

Any retry conflict:

```text
ROLLBACK whole batch
409
```

Any invalid/unauthorized item:

```text
whole request fails
NO partial persistence
```

---

# 56. Source Health Read Semantics — FIX-10

Read service may return:

```text
latest known source-health event
+
its observed_at
```

for exact:

```text
site_id
capture_source_id
source_kind
```

It MUST NOT claim:

```text
source continuously available
for interval A..B
```

Task-01 has no health interval semantics.

Future classifier/source-correlation task owns:

```text
health freshness horizon
temporal association
```

---

# 57. Source Health Does Not Become Device Evidence

No source-health row contains:

```text
observed_mac
observed_ip
device_id
visit_id
auth_session_id
```

No synthetic row like:

```text
device X:
quic unavailable
```

is created.

Permanent:

```text
missing / unavailable / unsupported
!=
negative device evidence
```

---

# 58. Database Identity

Database:

```text
/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3
```

Task-01 schema version:

```text
PRAGMA user_version = 1
```

Exactly two V1 data tables:

```text
device_fingerprint_evidence

device_fingerprint_source_health_events
```

No Task-01 identity-link table.

No classifier table.

No Registry mirror table.

---

# 59. Evidence Table — FIX-11 EXACT COLUMNS

Table:

```text
device_fingerprint_evidence
```

Columns:

```text
evidence_id
TEXT
PRIMARY KEY
NOT NULL

producer_id
TEXT
NOT NULL

source_event_id
TEXT
NOT NULL

source_kind
TEXT
NOT NULL

source_subtype
TEXT
NULL

extractor_name
TEXT
NOT NULL

extractor_version
TEXT
NOT NULL

feature_schema_version
INTEGER
NOT NULL

rule_version
TEXT
NULL

site_id
TEXT
NOT NULL

capture_source_id
TEXT
NOT NULL

observed_at
TEXT
NOT NULL

observed_mac
TEXT
NOT NULL

observed_ip
TEXT
NULL

privacy_class
TEXT
NOT NULL

quality_state
TEXT
NOT NULL

payload_json
TEXT
NOT NULL

payload_sha256
TEXT
NOT NULL

ingested_at
TEXT
NOT NULL
```

No other columns in schema v1.

---

# 60. Evidence Table — SQL Constraints

Required SQL-level checks at minimum:

```text
length(evidence_id) = 36

length(producer_id) BETWEEN 1 AND 64

length(source_event_id) = 36

length(source_kind) BETWEEN 1 AND 64

source_subtype IS NULL
OR length(source_subtype) BETWEEN 1 AND 64

length(extractor_name) BETWEEN 1 AND 64

length(extractor_version) BETWEEN 1 AND 64

feature_schema_version >= 1
AND feature_schema_version <= 2147483647

rule_version IS NULL
OR length(rule_version) BETWEEN 1 AND 64

length(site_id) = 24
AND
site_id NOT GLOB '*[^0-9a-f]*'

length(capture_source_id) BETWEEN 1 AND 64

length(observed_mac) = 17

length(observed_at) = 24
AND
substr(observed_at, -1, 1) = 'Z'

observed_ip IS NULL
OR length(observed_ip) BETWEEN 2 AND 45

privacy_class = 'P1'

quality_state IN (
    'valid',
    'partial',
    'degraded'
)

length(payload_json) >= 2

length(payload_sha256) = 64
AND
payload_sha256 NOT GLOB '*[^0-9a-f]*'

length(ingested_at) = 24
AND
substr(ingested_at, -1, 1) = 'Z'
```

Application canonical validation remains authoritative for full format parsing.

SQLite CHECKs are defense-in-depth.

---

# 61. Evidence Table — Exact Index Names

Required indexes:

```text
uq_df_evidence_producer_event
UNIQUE (
    producer_id,
    source_event_id
)
```

```text
idx_df_evidence_site_mac_time
(
    site_id,
    observed_mac,
    observed_at,
    evidence_id
)
```

```text
idx_df_evidence_site_kind_time
(
    site_id,
    source_kind,
    observed_at,
    evidence_id
)
```

```text
idx_df_evidence_retention
(
    observed_at,
    evidence_id
)
```

Schema validation checks exact names, uniqueness and column order.

---

# 62. Source Health Table — FIX-11 EXACT COLUMNS

Table:

```text
device_fingerprint_source_health_events
```

Columns:

```text
source_health_id
TEXT
PRIMARY KEY
NOT NULL

producer_id
TEXT
NOT NULL

source_health_event_id
TEXT
NOT NULL

site_id
TEXT
NOT NULL

capture_source_id
TEXT
NOT NULL

source_kind
TEXT
NOT NULL

status
TEXT
NOT NULL

reason_code
TEXT
NULL

observed_at
TEXT
NOT NULL

content_sha256
TEXT
NOT NULL

ingested_at
TEXT
NOT NULL
```

No interval end column.

No MAC/IP/device identity column.

---

# 63. Source Health SQL Constraints

Required defense-in-depth checks:

```text
length(source_health_id) = 36

length(producer_id) BETWEEN 1 AND 64

length(source_health_event_id) = 36

length(site_id) = 24
AND
site_id NOT GLOB '*[^0-9a-f]*'

length(capture_source_id) BETWEEN 1 AND 64

length(source_kind) BETWEEN 1 AND 64

status IN (
    'available',
    'unavailable',
    'unsupported'
)

reason_code IS NULL
OR length(reason_code) BETWEEN 1 AND 64

length(observed_at) = 24
AND
substr(observed_at, -1, 1) = 'Z'

length(content_sha256) = 64
AND
content_sha256 NOT GLOB '*[^0-9a-f]*'

length(ingested_at) = 24
AND
substr(ingested_at, -1, 1) = 'Z'
```

Full machine-id/reason/timestamp format is validated in application code.

---

# 64. Source Health Exact Index Names

```text
uq_df_source_health_producer_event
UNIQUE (
    producer_id,
    source_health_event_id
)
```

```text
idx_df_source_health_scope_time
(
    site_id,
    capture_source_id,
    source_kind,
    observed_at,
    source_health_id
)
```

```text
idx_df_source_health_retention
(
    observed_at,
    source_health_id
)
```

Exact names and column order are schema signature.

---

# 65. SQLite Connection Contract — FIX-11

Writer connections:

```text
sqlite3.Row

PRAGMA busy_timeout=500

PRAGMA foreign_keys=ON

PRAGMA journal_mode=WAL

PRAGMA synchronous=NORMAL

PRAGMA wal_autocheckpoint=1000

PRAGMA journal_size_limit=67108864
```

Read-only connections:

```text
open read-only

PRAGMA busy_timeout=500

PRAGMA foreign_keys=ON

PRAGMA query_only=ON
```

No read consumer opens a writable connection.

---

# 66. SQLite Startup Contract

On initialize:

```text
validate DB target/path safety

ensure parent safely

acquire writer lock

open DB

read PRAGMA user_version
```

If:

```text
user_version > 1
→ fail closed

version 0 + fingerprint tables already exist
→ partial/corrupt schema
→ fail closed

version 0 + no fingerprint tables
→ create schema v1 in transaction
→ set user_version=1

version 1
→ exact schema validation
```

Then:

```text
PRAGMA quick_check
must return "ok"
```

Then exact schema validation again.

No silent recreate after ambiguous failure.

---

# 67. Strict Schema Signature

Schema validation must check at least:

```text
exact required tables

no missing required columns

column SQLite types

primary keys

NOT NULL expectations

required CHECK fragments

required index names

required unique indexes

exact index column order

PRAGMA user_version
```

Unexpected additional application-owned fingerprint table/column under schema v1:

```text
SCHEMA ERROR
```

No loose best-effort acceptance.

---

# 68. Writer Lock

Writer authority:

```text
fingerprint-evidence.service
```

Lock path:

```text
/opt/CaptivePortal/data/device_fingerprint_evidence.writer.lock
```

Only one writer process may initialize/serve writes.

Failure to own writer lock:

```text
startup FAIL
```

One-shot future maintenance commands, if ever added, must also own the same lock.

Task-01 does not add repair/rebuild commands by default.

---

# 69. Main DB Ceiling / WAL Semantics — FIX-16/FIX-21

Logical main DB growth ceiling is runtime:

```text
config.max_db_bytes
```

default:

```text
DEFAULT_MAX_DB_BYTES = 1_073_741_824
```

Writer configures `PRAGMA max_page_count` from `config.max_db_bytes` and actual SQLite page size.

`PRAGMA journal_size_limit=67108864` means a post-transaction/checkpoint/reset residual journal/WAL size target/limit.

It is NOT a guaranteed hard maximum transient WAL filesize and is NOT the whole filesystem-capacity protection mechanism.

Do NOT permanently reject writes merely because the physical main DB file size equals/exceeds the configured logical ceiling; deleted pages may be reusable.

Storage-limit is entered when SQLite cannot allocate required growth and reports FULL/max-page condition.

No Task-01 VACUUM.

---

# 70. Retention Contract — OWNER FROZEN


P2 raw/high-risk durable retention:

```text
0
```

P1 normalized device evidence retention:

```text
DEFAULT_RETENTION_DAYS =
30
```

Owner status:

```text
ACCEPTED / FROZEN
```

Runtime:

```text
DEVICE_FINGERPRINT_RETENTION_DAYS
→ config.retention_days
```

Source-health P0 retention:

```text
SOURCE_HEALTH_RETENTION_DAYS =
30
```

fixed repository constant.

Cutoffs:

```text
evidence cutoff =
central_now - config.retention_days
```

```text
source-health cutoff =
central_now - SOURCE_HEALTH_RETENTION_DAYS
```

Both durable retention clocks use:

```text
observed_at
```

not `ingested_at`.

---

# 71. Mandatory Retention Maintenance Loop — FIX-14/FIX-19/FIX-24


The maintenance loop runs one bounded pass after every completed fixed delay of:

```text
RETENTION_SCAN_INTERVAL_SECONDS = 300
```

unless `stop_event` terminates the wait.

Conceptually:

```text
while true:

    if stop_event.wait(RETENTION_SCAN_INTERVAL_SECONDS):
        exit

    run exactly one bounded retention pass
```

This maintenance pass is mandatory while the service remains running.
The first pass is delayed by one full interval after maintenance-thread start.
Exactly one maintenance thread exists, therefore maintenance passes do not overlap.
No ingest request thread may run retention synchronously.

Evidence cutoff:

```text
central_now - config.retention_days
```

Source-health cutoff:

```text
central_now - SOURCE_HEALTH_RETENTION_DAYS
```

For each table delete ordered by observed_at + primary row id in chunks of at most:

```text
RETENTION_DELETE_CHUNK_ROWS = 500
```

Maximum:

```text
MAX_RETENTION_CHUNKS_PER_PASS = 20
```

per table/pass.

Each delete chunk is one bounded transaction.
Do not hold one giant cleanup transaction.

---

# 72. Retention Eligibility — FIX-14


Evidence row expires when:

```text
observed_at
<
central_now - config.retention_days
```

Source-health row expires when:

```text
observed_at
<
central_now - SOURCE_HEALTH_RETENTION_DAYS
```

Strict less-than.

No retention eligibility uses ingested_at.

No undefined source-health retention setting exists in V1.

---

# 73. Runtime State + Maintenance Ownership — FIX-19

Configuration-disabled is not a served runtime state.

Running state set:

```text
initializing
ready
degraded
unavailable
stopping
```

Maintenance ownership:

```text
exactly one maintenance thread
per fingerprint-evidence.service process
```

Constructor/factory creates state only and has NO thread side effect.

No maintenance thread starts during module import or object construction.

CLI composition root owns thread start.

No ingest request thread runs retention synchronously.

---

# 74. Enabled Startup + Maintenance Lifecycle — FIX-19/FIX-24


Exact enabled sequence after repository/app composition:

```text
install SIGTERM/SIGINT handlers
start exactly one maintenance thread
runtime → ready
enter app.run(...)
```

Maintenance constructor/factory has NO thread side effect.
Only CLI composition root starts the thread.

Normal first pass occurs after one `RETENTION_SCAN_INTERVAL_SECONDS`, not at startup.

The loop is fixed-delay, mandatory while running, non-overlapping and interruptible by `stop_event`.

State transitions remain:

```text
retention failure + repository healthy
→ degraded / retention_failed

later successful retention
→ ready

storage corruption/unavailability
→ unavailable

SQLite FULL/max-page
→ unavailable / storage_limit

signal
→ stopping
```

---

# 75. Storage-Limit Recovery — FIX-16


After `storage_limit`, retention may delete eligible rows.

Recovery is allowed only after:

```text
retention cleanup succeeds

PRAGMA quick_check = ok

strict schema validation PASS

allocatable page capacity exists
```

For V1, allocatable page capacity exists when:

```text
PRAGMA page_count < PRAGMA max_page_count

OR

PRAGMA freelist_count > 0
```

Then:

```text
state → ready
reason → None
```

There is NO requirement that:

```text
os.path.getsize(DB) < config.max_db_bytes
```

after DELETE.

A later write that still receives SQLITE_FULL immediately returns to:

```text
unavailable / storage_limit
```

No VACUUM. No automatic repair.

Other unavailable semantics remain unchanged.

---

# 76. Runtime Health HTTP Semantics — FIX-20

`GET /health` is protected by Bearer + direct-peer CIDR ACL.

Query handling order:

```text
case-insensitive presence of:
token
access_token
bearer_token
→ 400 query_token_forbidden
before Bearer authentication
```

After credential-query rejection, ANY other query parameter on `/health`:

```text
400 invalid_request
```

`/health` accepts no ordinary query parameters.

HTTP status by runtime state:

```text
ready
degraded
→ 200

initializing
unavailable
stopping
→ 503
```

The exact JSON shape is frozen in section 50.

No generic `retention_days` field exists; retention fields are separate.

---

# 77. Ingest Eligibility by Runtime State

Evidence/source-health POST:

```text
ready
→ accept

degraded(retention_failed)
→ accept

initializing
→ 503

unavailable
→ 503

stopping
→ 503
```

No write while unavailable/stopping.

---

# 78. Source Health Service State Is Separate

Runtime service state:

```text
ready/degraded/unavailable
```

is operational health of the central evidence service.

`device_fingerprint_source_health_events` represents producer-observed source component health.

These are separate models.

Do not synthesize source-health events from central service runtime state.

---

# 79. Dedicated Flask App Factory

Task-01 exact ownership:

```text
app/device_fingerprint/api.py
```

exports a dedicated application factory concept:

```python
create_device_fingerprint_app(
    runtime,
    *,
    logger,
) -> Flask
```

It creates a Flask app containing only Task-01 internal routes.

It does not accept/register the main CaptivePortal app.

---

# 80. Atomic Ingest Registration + Concurrency Guard — FIX-19/FIX-24


Evidence and source-health POST share one:

```text
BoundedSemaphore(config.max_concurrent_ingest_requests)
```

Health GET does not consume an ingest slot.

If no semaphore slot is immediately available:

```text
429 concurrency_limit
Retry-After: 1
```

Runtime owns one synchronization boundary:

```text
Condition
```

protecting at least:

```text
runtime state
accepting_writes
active_ingest_count
```

## Exact ingest registration

```text
acquire ingest semaphore nonblocking

lock runtime Condition

if accepting_writes == false
or runtime state is not ingest-eligible:
    unlock
    release semaphore
    → 503 runtime_unavailable

active_ingest_count += 1

unlock
```

Only after the increment is the request active and allowed to execute repository-mutating ingest work.

Signal transition uses the SAME Condition:

```text
lock runtime Condition
runtime state = stopping
accepting_writes = false
notify_all()
unlock
```

Therefore after stopping becomes visible NO new request can increment `active_ingest_count`.

Request completion remains in `finally`:

```text
lock Condition
active_ingest_count -= 1
notify_all()
unlock
release semaphore
```

No request may leak active registration on error/exception paths.

---

# 81. HTTP Request Size — FIX-21

Flask app config:

```text
MAX_CONTENT_LENGTH =
config.max_http_request_bytes
```

repository default:

```text
DEFAULT_MAX_HTTP_REQUEST_BYTES = 1_048_576
```

Oversized request:

```text
413 request_too_large
```

No body echo.

---

# 82. Batch Count — FIX-21

For both POST endpoints:

```text
1..config.max_events_per_batch
```

repository default:

```text
DEFAULT_MAX_EVENTS_PER_BATCH = 100
```

Empty batch:

```text
400 invalid_request
```

Too many:

```text
413 request_too_large
```

---

# 83. Request Content Type

POST endpoints require:

```text
Content-Type: application/json
```

Missing/wrong content type:

```text
400
```

No form/query fallback.

---

# 84. Repository Write Transaction

One repository method per batch owns:

```text
BEGIN IMMEDIATE
```

and:

```text
COMMIT
or
ROLLBACK
```

Service/API layers do not open nested writer transactions.

No `executescript()` for ordinary ingest.

---

# 85. Conflict Detection

Inside write transaction:

```text
SELECT existing immutable fields
WHERE producer_id=? AND source_event_id=?
```

or source-health equivalent.

If existing:

```text
compare exact canonical stored immutable content
```

Hash-only comparison is insufficient for correctness contract.

Hash may accelerate/assist but exact canonical fields define equality.

---

# 86. Canonical Ingested Timestamp

For a successful batch, central service captures one:

```text
batch_ingested_at
```

in fixed UTC milliseconds.

Every NEW row inserted from that batch receives the same:

```text
ingested_at=batch_ingested_at
```

Duplicate NO-OP rows keep original stored `ingested_at`.

---

# 87. Evidence ID Generation

For each NEW evidence row:

```text
evidence_id =
str(uuid.uuid4())
```

generated by central service inside the accepted batch operation.

Never producer supplied.

Never reused on retry.

Duplicate NO-OP returns no new ID.

IDs are not returned in success response in V1.

---

# 88. Source Health ID Generation

For each NEW source-health row:

```text
source_health_id =
str(uuid.uuid4())
```

central-owned.

Not producer supplied.

Not echoed in V1 success response.

---

# 89. Task-01 Read Service — FIX-17


Task-01 internal Python read service has only foundation-owned read semantics.

Required evidence method:

```text
list_evidence(
    site_id,
    observed_mac,
    from_utc,
    to_utc,
    *,
    source_kind=None,
    limit,
    cursor,
)
```

Required source-health method:

```text
latest_source_health(
    site_id,
    capture_source_id,
    source_kind,
    *,
    through_utc,
)
```

Task-01 intentionally has NO classifier-oriented “latest evidence by source” grouping method.

Future Task-04 may define:

```text
latest evidence windows
per-source grouping
schema/subtype aggregation
classifier freshness
```

without changing immutable Task-01 evidence meaning.

No HTTP evidence-query endpoint exists in Task-01.

---

# 90. Read Bounds — FIX-17


`list_evidence()` requires:

```text
site_id
observed_mac
from_utc
to_utc
limit
```

Rules:

```text
from_utc < to_utc

requested time range
<= configured retention_days

default page limit = 100

maximum page limit = 500
```

Optional `source_kind` must satisfy exact source-kind syntax.

No unbounded evidence query.

`latest_source_health()` returns at most one point event:

```text
latest observed_at <= through_utc
```

for exact site_id + capture_source_id + source_kind.

It does not claim an availability interval.

---

# 91. Evidence Read Cursor — FIX-22

Task-01 cursor exists ONLY for `list_evidence()`.

Exact internal cursor tuple:

```text
observed_at
evidence_id
```

Ordering:

```text
observed_at ASC
evidence_id ASC
```

No offset pagination.

There is NO Task-01 source-health cursor.

`latest_source_health()` returns at most one point-in-time row and is not paginated.

---

# 92. Read-Only DB Connections

Read service opens:

```text
read-only SQLite connection
+
PRAGMA query_only=ON
```

It has no cleanup/insert/update/delete methods.

Admin/Analytics never receive repository writer object.

---

# 93. Schema Registry API — Task-01

Task-01 owns an immutable-after-composition registry concept.

Required behavior:

```text
register schema before serving

duplicate registration for same key
→ error

unknown key
→ unsupported schema

registry frozen before HTTP server starts

no runtime dynamic remote registration
```

Schema key:

```text
(source_kind, feature_schema_version)
```

---

# 94. Schema Validator Result Contract

A registered schema validator receives:

```text
payload JSON object
```

and returns:

```text
validated normalized Mapping
```

Central ingest then canonical-JSON serializes that result.

Validator must not return:

```text
bytes
NaN/Infinity
unbounded objects
unknown fields
```

Task-01 tests provide test validators.

---

# 95. Production Registry in Task-01

Production composition:

```text
registry = EvidenceSchemaRegistry()
registry.freeze()
```

with no device-evidence schemas registered.

Therefore Task-01 production `/evidence/batch` returns:

```text
400 unsupported_schema
```

for any event until Task-02/03 later modify production composition.

This is expected.

---

# 96. Source Health Does Not Need Device Schema Registry

Source-health has its own fixed Task-01 V1 schema.

It validates:

```text
configured allowed source_kind
```

but does not require a device payload schema to exist.

This allows foundation/source-health smoke before Task-02 evidence schemas.

---

# 97. Privacy Classes — Final Candidate

```text
P0 =
bounded operational/source-health facts

P1 =
normalized fingerprint/correlation facts

P2 =
high/privacy-sensitive raw transient material
```

P1 includes:

```text
observed_mac
observed_ip
future DHCP vector
future TCP vector
future JA4
future normalized Portal features
```

P2 includes:

```text
raw packet bytes
raw DNS names
raw SNI
raw full UA
arbitrary raw mDNS/local names
```

---

# 98. P2 Denylist

Central device evidence ingest rejects schema/payload attempting to persist ordinary:

```text
raw_packet
packet_payload
sni
server_name
dns_rrname
fqdn_destination
full_user_agent
cookie
authorization
credential
raw_headers
```

This is defense-in-depth.

Exact future schemas must also allowlist only safe fields.

No arbitrary destination field in common envelope.

---

# 99. Logging / Telemetry Safety

Dedicated logger:

```text
captivportal.device_fingerprint
```

No raw request body.

No Bearer.

No raw evidence payload.

No MAC/IP in ordinary operational telemetry unless a future explicit bounded diagnostic contract authorizes it.

Safe telemetry identifiers:

```text
event name
producer_id
capture_source_id
site_id
source_kind
HTTP status
error category
counts
runtime state
artifact identity
schema version
```

---

# 100. Core Telemetry Events

Minimum Task-01 events:

```text
device_fingerprint_service_started

device_fingerprint_service_stopped

device_fingerprint_ingest_completed

device_fingerprint_ingest_rejected

device_fingerprint_ingest_conflict

device_fingerprint_ingest_duplicate

device_fingerprint_source_health_completed

device_fingerprint_source_health_rejected

device_fingerprint_retention_completed

device_fingerprint_retention_failed

device_fingerprint_storage_limit

device_fingerprint_storage_unavailable

device_fingerprint_product_health
```

No exact-once telemetry claim.

---

# 101. Artifact Identity

CLI `run` requires:

```text
capture_loaded_artifact_identity(
    "fingerprint-evidence.service"
)
```

Failure:

```text
sanitized startup failure
exit status 1
no HTTP listener
```

Identity captured once and immutable for process lifetime.

Safe identity fields included in startup/health telemetry.

No dynamic later Git query masquerades as loaded identity.

---

# 102. CLI Lifecycle — FIX-13/FIX-19 EXACT

Exact `run` lifecycle:

```text
1. parse command
2. load get_settings()
3. build DeviceFingerprintConfig

4. if enabled == false:
       return exit status 0 immediately

       no logger/runtime startup
       no artifact identity capture
       no writer lock
       no DB initialize
       no Flask app
       no maintenance thread
       no listener

5. configure dedicated logger
6. capture immutable artifact identity
7. create runtime/service state
   (NO maintenance thread side effect)
8. acquire writer lock
9. initialize repository
10. build/freeze production schema registry
11. create dedicated Flask app
12. install SIGTERM/SIGINT handlers
13. start exactly one maintenance thread
14. runtime → ready
15. run direct-TLS Flask/Werkzeug app
16. finally: idempotent bounded finalization
17. return exit status
```

Disabled is normal success.

Enabled startup configuration/storage failure is fail-closed and exits non-zero before serving writes.

---

# 103. Signal / Shutdown / Hard Containment — FIX-13/FIX-19/FIX-24


Exact SIGTERM/SIGINT handler performs ONLY:

```text
1. lock runtime Condition

2. runtime state → stopping
   accepting_writes = false
   notify_all()

3. unlock runtime Condition

4. set maintenance stop_event

5. raise SystemExit(0)
```

Signal handler MUST NOT wait for active ingest, join threads, run retention, audit DB health, close DB or release writer lock.

`SystemExit(0)` unwinds the main blocking Flask/Werkzeug `app.run(...)`.

## One total graceful shutdown budget

Outer idempotent finalizer creates one deadline:

```text
deadline = monotonic_now + SHUTDOWN_TIMEOUT_SECONDS
SHUTDOWN_TIMEOUT_SECONDS = 20.0
```

Normal clean finalization order:

```text
1. accepting_writes is already false

2. wait under runtime Condition
   for active_ingest_count == 0
   using only time remaining before deadline

3. join maintenance thread
   using only the SAME remaining deadline

4. ONLY IF:
   active_ingest_count == 0
   AND maintenance thread terminated

   then close repository/resources

5. release writer lock LAST

6. best-effort stopped telemetry

7. normal process exit
```

Writer lock MUST remain owned for the entire lifetime of any possible DB-mutating execution inside that process.

## Graceful deadline expiry

If the shared 20-second deadline expires while either:

```text
active_ingest_count > 0
OR
maintenance thread is still alive
```

then:

```text
emit sanitized shutdown_timeout telemetry

DO NOT close repository resources
from underneath live work

DO NOT release writer lock

DO NOT resume accepting requests
```

Runtime remains `stopping` and enters:

```text
hard shutdown containment
```

Writer lock remains process-owned until process termination.
External `TimeoutStopSec=30` is the hard process containment boundary.
No second fingerprint writer may acquire the lock while the original process still contains live DB-mutating execution.

The 20 seconds are one total graceful application budget, never 20s ingest + 20s maintenance.
Finalizer remains idempotent.
No Authorization/main-runtime interaction.

---

# 104. Systemd / Activation / Mutable Artifact Lifecycle — INFRA FROZEN


External unit:

```text
fingerprint-evidence.service
```

Frozen process identity:

```text
User=admin
Group=admin
```

Core unit shape:

```text
Type=simple

User=admin
Group=admin

WorkingDirectory=/opt/CaptivePortal

EnvironmentFile=/etc/default/captive-portal

ExecStart=/usr/bin/python3 -m app.device_fingerprint.cli run

Restart=on-failure

RestartSec=5

TimeoutStopSec=30

KillSignal=SIGTERM
```

No socket activation.

Before Owner activation:

```text
service installed
disabled
inactive

DEVICE_FINGERPRINT_EVIDENCE_ENABLED=false
```

Activation:

```text
DEVICE_FINGERPRINT_EVIDENCE_ENABLED=true

systemd operational intent:
enable + start

result:
enabled + active
```

Rollback/deactivation:

```text
disable + stop

DEVICE_FINGERPRINT_EVIDENCE_ENABLED=false
```

Exact `systemctl` command syntax belongs to deploy/infra procedure.

Mutable artifact invariant:

```text
NO Git checkout/artifact mutation under /opt/CaptivePortal
while fingerprint-evidence.service from that checkout is alive
```

Service must be stopped before checkout mutation.

After controlled update, restart only if activation state requires and verify loaded artifact identity.

---

# 105. Main CaptivePortal NO-TOUCH Runtime

Task-01 does NOT modify:

```text
run.py

main Flask application composition

Authorization routes

Analytics blueprint registration

Admin Web composition
```

No fingerprint blueprint in `captive-portal.service`.

This is a mandatory FIX-7 acceptance check.

---

# 106. Repository Availability Errors

Task-01 internal sanitized categories:

```text
DeviceFingerprintStorageUnavailable

DeviceFingerprintStorageCorrupt

DeviceFingerprintWriterUnavailable

DeviceFingerprintValidationError

DeviceFingerprintConflict

DeviceFingerprintConfigError
```

No raw sqlite exception text crosses HTTP boundary.

---

# 107. Runtime State Reason Codes

Exact V1 operational state reasons:

```text
None

retention_failed

storage_limit

storage_unavailable

storage_corrupt

stopping
```

No arbitrary raw exception string.

---

# 108. Retention Failure Behavior

If retention transaction fails but:

```text
repository quick_check
+
schema validation
```

still pass:

```text
state =
degraded

reason =
retention_failed

ingest remains allowed
```

Next successful cleanup:

```text
ready
reason=None
```

If repository health validation fails:

```text
unavailable
```

---

# 109. Repository Busy / Contention

Writer uses bounded:

```text
busy_timeout=500 ms
```

If a batch cannot acquire DB write within bounded constraints:

```text
503 repository_unavailable
```

This individual bounded busy failure does NOT automatically mark storage corrupt.

Runtime may remain ready/degraded if repository health still validates.

---

# 110. DB / Lock / TLS Filesystem Contract — INFRA FROZEN


Database directory:

```text
/opt/CaptivePortal/data

ownership =
admin:admin

mode =
0750
```

Fingerprint DB:

```text
/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3

ownership =
admin:admin

mode =
0640
```

Writer lock:

```text
/opt/CaptivePortal/data/device_fingerprint_evidence.writer.lock

ownership =
admin:admin

mode =
0640
```

TLS directory:

```text
/etc/captive-portal/device-fingerprint

ownership =
root:admin

mode =
0750
```

Certificate:

```text
/etc/captive-portal/device-fingerprint/server.crt

ownership =
root:admin

mode =
0640
```

Private key:

```text
/etc/captive-portal/device-fingerprint/server.key

ownership =
root:admin

mode =
0640
```

Required result:

```text
admin service process =
can read certificate/key
can write DB/lock

unauthorized ordinary users =
cannot read private key
```

Safety precheck:

If deployment discovers that changing ownership of the existing shared:

```text
/opt/CaptivePortal/data
```

would affect another production component:

```text
STOP

do not recursively chown

preserve existing safe ownership

return exact filesystem evidence
to Owner / Tech Lead
```

Task-01 must not broaden permissions beyond required access.

---

# 111. No Remote SQLite

Database path validation must reject designs that intentionally point at network/shared filesystems.

Application validation can prove:

```text
absolute path
distinct DB/lock path
```

Deployment acceptance proves storage is local to the central service host.

No:

```text
NFS
SMB
CIFS
sensor-mounted SQLite
```

---

# 112. Evidence Read Privacy

Internal Python read service returns normalized evidence only.

It never returns:

```text
raw packet
raw SNI
raw DNS
full UA
credentials
```

because those values are not durable in schema v1.

No browser API exists in Task-01.

---

# 113. Source Schema Unknown Behavior — FIX-9

For device evidence:

```text
configured producer
+
authorized source_kind
+
unregistered (
    source_kind,
    feature_schema_version
)
```

returns:

```text
400
code=unsupported_schema
```

No DB write.

No fallback arbitrary payload storage.

---

# 114. Source Kind Authorization vs Schema Registration

These are independent checks:

```text
producer allowed_source_kinds
=
security authorization

EvidenceSchemaRegistry
=
payload semantic authorization
```

Both must pass.

A configured allowed source kind with no registered schema:

```text
still rejected
```

This allows Task-01 foundation configuration to anticipate Task-02 without silently enabling payloads.

---

# 115. Source Health Source Kinds

Source-health events do not require device payload schema registration.

They require:

```text
source_kind is authorized
for authenticated producer
```

This permits health of a planned/installed source to be reported independently of per-device payload schema availability.

---

# 116. HTTP Health Authentication + Query Contract — FIX-20

`GET /health` requires valid configured producer Bearer plus allowed `request.remote_addr`.

No body producer_id.

Any valid configured producer credential may query health in V1.

Query contract:

```text
token
access_token
bearer_token
(case-insensitive)
→ 400 query_token_forbidden
BEFORE Bearer authentication
```

Any other query parameter:

```text
400 invalid_request
```

No query parameter is accepted by `/health`.

---

# 117. Request ID

Every accepted HTTP framework request under API prefix gets central:

```text
request_id =
uuid4 canonical lowercase
```

Returned in response.

Safe telemetry may include request_id.

No producer controls request_id.

---

# 118. Batch Response Count Semantics

Evidence/source-health success counts:

```text
received
inserted
duplicate_noop
```

For a fully idempotent retry:

```text
received=N
inserted=0
duplicate_noop=N
```

No partial failure count because failed batch persists nothing new.

---

# 119. 409 Semantics — FIX-20

Any existing retry identity with different canonical immutable content:

```text
409 idempotency_conflict
```

Entire write transaction rolls back.

Exact response is the standard error shape with:

```text
code =
idempotency_conflict

message =
The request conflicts with an existing immutable event.
```

No:

```text
conflict_count
conflicting index
MAC
payload
optional metadata
```

No overwrite/update.

---

# 120. 503 Error Routing — FIX-20

503 routing is exact:

```text
runtime initializing/unavailable/stopping
→ runtime_unavailable

bounded DB busy / temporary DB I/O unavailable
→ repository_unavailable

SQLite FULL/max-page
→ storage_limit

quick_check/schema integrity corruption
→ storage_corrupt
```

Do not collapse storage corruption into generic repository-unavailable.

Producer retry policy remains Task-02 responsibility.

---

# 121. 429 Backpressure

If ingest semaphore unavailable:

```text
429

Retry-After: 1
```

No queue inside Flask API beyond server/socket behavior.

Producer spool remains Task-02 responsibility.

---

# 122. Privacy Retention Clock — FIX-14


For device evidence:

```text
expiry =
observed_at + configured DEVICE_FINGERPRINT_RETENTION_DAYS
```

For source health:

```text
expiry =
observed_at + SOURCE_HEALTH_RETENTION_DAYS
=
observed_at + 30 days
```

A late accepted event has less remaining durable lifetime.

ingested_at never resets either retention clock.

No source-health retention environment setting exists in V1.

---

# 123. Source Health Freshness

Task-01 returns:

```text
latest point event
observed_at
```

It does not compute:

```text
fresh
stale
continuous availability interval
```

Those semantics are future consumer policy.

---

# 124. Task-02 Dedup Responsibility

SPAN/mirror dedup remains:

```text
Task-02
MANDATORY
```

Task-01 trusts that each `source_event_id` represents one normalized logical source event.

Task-01 does not deduplicate packet identity.

Transport retry idempotency must not be mistaken for packet dedup.

---

# 125. Phase-1 Evidence Ranking — PRESERVED

Core:

```text
existing CaptivPortal/Omada facts
DHCP exact vector
Portal proven low-entropy evidence
TLS JA4
QUIC JA4 where present
```

Weak supporting:

```text
TCP SYN normalized vector
hostname
private/local-admin MAC qualifier
valid OUI
existing Visit/connection context
```

Optional:

```text
DNS normalized ecosystem
mDNS service family
exact QUIC transport parameters
```

Deferred:

```text
LLMNR
routed/global IPv6
high-entropy Client Hints
```

JA3 remains not-primary.

No Task-01 implementation of any producer.

---

# 126. Future Classification Boundary — PRESERVED

Task-01 stores no:

```text
device_class
form_factor
os_family
vendor
model_hint
classification_state
confidence
```

Future Task-04 owns classifier.

Honest unknown remains preferred over false certainty.

---

# 127. Future Identity Boundary — PRESERVED

Task-01 query/storage has no:

```text
device_id
visit_id
auth_session_id
```

Task-05 may later use independently Site-proven relationships.

No Task-01 schema migration is pre-created for Task-05.

---

# 128. Exact Application + Governance / Documentation Boundary — FIX-18/FIX-23


## NEW application files

```text
app/device_fingerprint/__init__.py
app/device_fingerprint/config.py
app/device_fingerprint/models.py
app/device_fingerprint/validation.py
app/device_fingerprint/schema_registry.py
app/device_fingerprint/schema.py
app/device_fingerprint/repository.py
app/device_fingerprint/read_service.py
app/device_fingerprint/service.py
app/device_fingerprint/api.py
app/device_fingerprint/telemetry.py
app/device_fingerprint/cli.py
```

## MODIFY configuration

```text
app/config.py
app/settings.py
.env.example
```

## MODIFY repository instruction/governance

```text
.github/instructions/python.instructions.md
AGENTS.md
```

Both entrypoint-governance replacements are exact and frozen in section 6.

## MODIFY canonical documentation

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
```

## NEW canonical module contract

```text
docs/modules/device-fingerprint.md
```

After implementation it is the current module contract with repository status `current; default disabled` and links to the accepted FINAL rather than duplicating the complete TASK.

Required doc semantics remain:

```text
docs/README.md
→ knowledge map/current module entry

docs/module-index.md
→ Device Fingerprint Evidence
   current; default disabled

docs/configuration.md
→ DEVICE_FINGERPRINT_* defaults
   enabled requirements
   external secrets

docs/security.md
→ dedicated direct-TLS service
   per-producer Bearer
   direct-peer CIDR allowlist
   request.remote_addr authority
   no proxy-header trust

docs/logging.md
→ captivportal.device_fingerprint
   safe telemetry
   fingerprint query-string stripping
   no payload/Bearer/MAC/IP operational logging

docs/project-inventory.md
→ auxiliary process / persistence / default-disabled state

docs/deployment.md
→ stop service BEFORE checkout/update
   + artifact-owned restart invariant

docs/architecture.md / README*
→ controlled auxiliary composition exception
```

`AGENTS.md` must contain the exact controlled auxiliary-entrypoint invariant from section 6.
No unrelated documentation rewrite.

---

# 129. Explicit NO-TOUCH Boundary — FINAL

Application/runtime NO-TOUCH:

```text
run.py

app/artifact_identity.py
app/common/mac.py
app/common/device_type.py

app/visitor_registry/**
app/visit_lifecycle/**
app/observations/**
app/current_state/**
app/traffic_projection/**
app/analytics/**
app/admin_web/**
app/web/**

templates/**
static/icon assets
```

Only the existing instruction/documentation files listed in section 128 may change.

No existing Python domain other than:

```text
app/config.py
app/settings.py
```

may be changed.

If implementation objectively requires another file:

```text
STOP
→ Tech Lead review
```

---

# 130. No New Dependency

Task-01 uses existing project/runtime dependencies:

```text
Python stdlib
Flask
Werkzeug
sqlite3
```

No requirements/dependency file change.

No unrelated HTTP/security package.

---

# 131. Exact Test File Boundary — FINAL

## NEW

```text
tests/device_fingerprint/__init__.py
tests/device_fingerprint/test_config.py
tests/device_fingerprint/test_validation.py
tests/device_fingerprint/test_schema_registry.py
tests/device_fingerprint/test_repository.py
tests/device_fingerprint/test_read_service.py
tests/device_fingerprint/test_api.py
tests/device_fingerprint/test_service.py
tests/device_fingerprint/test_telemetry.py
tests/device_fingerprint/test_cli.py
```

No broad existing test-file rewrite is required by Task-01.

---

# 132. Required Config Tests

Must prove:

```text
disabled default

disabled config does not require endpoint secrets

enabled requires all endpoint/TLS/network/producer fields

exact env names

strict producers JSON shape

secret length

secret repr redaction

duplicate token rejection

duplicate producer rejection

duplicate capture source rejection

Site format

CIDR validation

source-kind validation

DB/lock absolute and distinct

all resource limit bounds

clock values

retention value
```

---

# 133. Required Validation Tests

Must prove canonical:

```text
site_id

MAC

IP

UUID

UTC millisecond timestamp

machine identifiers

extractor version

reason code

quality state

source health status
```

Also:

```text
future-skew rejection

delayed-age rejection

no destination_ip common field
```

---

# 134. Required Schema Registry Tests

Production builder:

```text
EMPTY
```

Test registry injection:

```text
PASS
```

Must prove:

```text
registration before freeze

duplicate registration rejected

register after freeze rejected

unknown schema rejected

validator returns normalized mapping

unknown/forbidden payload field rejected
```

No fake production schema.

---

# 135. Required Repository Tests

Must prove:

```text
schema user_version=1

exact two tables

exact columns/types/not-null/PK/checks

exact index names/order

WAL

synchronous=NORMAL

busy_timeout=500

query_only readers

quick_check

strict schema validation

partial schema fail-closed

newer user_version fail-closed

writer lock

main DB max-page guard
```

---

# 136. Required Evidence Idempotency Tests

Cases:

```text
new batch
→ inserted

same retry
→ 200 / all duplicate_noop

mixed new + duplicate
→ 200

mixed new + conflict
→ 409
→ new rolled back

conflict existing row unchanged

duplicate source_event_id inside one request
→ 400

two events same payload but different source_event_id
→ two logical events
```

---

# 137. Required Source Health Tests

Must prove:

```text
point event only

available/unavailable/unsupported exact

silence creates nothing

latest read returns event + observed_at

no interval claim

no MAC/IP identity fields

idempotent retry

conflict rollback

batch atomicity
```

---

# 138. Required HTTP Security / Namespace Tests — FIX-15/FIX-20/FIX-25


Must prove:

```text
dedicated Flask app only
API prefix exact

allowed methods EXACTLY:
POST /evidence/batch
POST /source-health/batch
GET /health

query key rejection is case-insensitive for:
token
access_token
bearer_token

forbidden query credential
→ 400 query_token_forbidden
BEFORE Bearer auth

missing/wrong/malformed Bearer
→ 401 invalid_credential

valid syntax secret uses hmac.compare_digest
against every configured producer

disallowed request.remote_addr
→ 403 source_network_forbidden

X-Forwarded-For ignored
Forwarded ignored
X-Real-IP ignored

unknown fingerprint path
after auth/network pass
→ 404 not_found
→ exact JSON
→ no HTML

known path + unsupported method
after auth/network pass
→ 405 method_not_allowed
→ exact JSON
→ no HTML

explicitly test:
POST /health
GET /evidence/batch
GET /source-health/batch
GET /unknown
OPTIONS /evidence/batch

body producer mismatch → 403 producer_forbidden
Site mismatch → 403 site_forbidden
capture source mismatch → 403 capture_source_forbidden
source kind mismatch → 403 source_kind_forbidden
unknown schema → 400 unsupported_schema
413 request_too_large
429 concurrency_limit
503 exact runtime/repository/storage categories
500 unexpected programming failure → internal_error

no raw body/secret in response/logging
```

No Flask/Werkzeug default HTML response under the fingerprint API namespace.

---

# 139. Required Lifecycle / Shutdown Race Tests — FIX-19/FIX-24


Must prove:

```text
constructor/factory starts NO maintenance thread

enabled CLI starts exactly one maintenance thread

first pass waits one full fixed delay

maintenance pass is mandatory after each completed delay

maintenance non-overlapping

stop_event interrupts wait

initializing → ready
ready → degraded(retention_failed)
degraded → ready
ready/degraded → unavailable(storage_limit)
storage_limit → ready only after accepted recovery proof
storage_unavailable latched
storage_corrupt latched
```

Atomic registration race tests must prove:

```text
semaphore acquired
then runtime Condition is authoritative

request cannot increment active_ingest_count
after stopping/accepting_writes=false
becomes visible under same Condition

rejected-after-semaphore request
releases semaphore

registered request decrements count in finally
and notify_all()
```

Shutdown tests must prove:

```text
signal updates state=stopping
and accepting_writes=false
under runtime Condition

signal sets stop_event
signal raises SystemExit(0)
signal performs no blocking wait

ONE total 20s deadline
covers active drain + maintenance join

clean shutdown:
active count zero
maintenance terminated
then repository close
then writer lock release LAST

timeout with active ingest
→ shutdown_timeout telemetry
→ repository NOT closed underneath it
→ writer lock NOT released

timeout with maintenance alive
→ shutdown_timeout telemetry
→ repository NOT closed underneath it
→ writer lock NOT released

runtime remains stopping
no new ingest accepted
```

`TimeoutStopSec=30` remains external hard containment.
HTTP health tests verify exact section-50 shape/status mapping.

---

# 140. Required Retention / Storage-Limit Tests — FIX-14/FIX-16


Must prove:

```text
device evidence cutoff uses configured retention_days

source-health cutoff uses fixed SOURCE_HEALTH_RETENTION_DAYS=30

ingested_at does not extend either retention

strict < cutoff

500 rows/chunk

20 chunks max/table/pass

both tables cleaned independently

no other DB touched

retention failure → degraded
```

Storage-limit tests must prove:

```text
PRAGMA max_page_count configured from config.max_db_bytes

journal_size_limit is NOT treated
as hard transient WAL file ceiling

SQLite FULL/max-page
→ unavailable/storage_limit

recovery may run retention

recovery requires:
quick_check ok
schema valid
AND (
    page_count < max_page_count
    OR freelist_count > 0
)

DB file remaining physically large
does NOT block recovery by itself

no VACUUM

write receiving SQLITE_FULL again
→ storage_limit again
```

---

# 141. Required Failure Isolation

Central service failures must not mutate or require:

```text
Authorization

Visitor Registry

Visit Lifecycle

Observation

Current State

Traffic Projection
```

Official acceptance later must stop/fail evidence service while core authorization remains PASS.

Coder narrow tests do not claim production failure isolation acceptance.

---

# 142. Exact Coder Narrow Test Commands — FINAL FROZEN

After FINAL + explicit Owner implementation authorization only, Coder runs exactly:

```bash
python -m pytest -q \
  tests/device_fingerprint/test_config.py \
  tests/device_fingerprint/test_validation.py \
  tests/device_fingerprint/test_schema_registry.py
```

Then:

```bash
python -m pytest -q \
  tests/device_fingerprint/test_repository.py \
  tests/device_fingerprint/test_read_service.py
```

Then:

```bash
python -m pytest -q \
  tests/device_fingerprint/test_api.py \
  tests/device_fingerprint/test_service.py \
  tests/device_fingerprint/test_telemetry.py \
  tests/device_fingerprint/test_cli.py
```

Then:

```bash
python -m compileall -q app/device_fingerprint
```

Then:

```bash
git diff --check
```

These are task-owned narrow test modules.

Coder does NOT run the full repository suite.

Exact command grouping is frozen in this FINAL.

---

# 143. Coder Non-Claims — PRESERVED

Coder must not claim:

```text
CENTRAL FULL GATE

PRODUCTION SENSOR TEST

PRODUCTION INGEST TEST

PRODUCTION TLS/ACL ACCEPTANCE

PRODUCTION DEPLOY

CLASSIFIER ACCURACY

DEVICE CARD ACCEPTANCE

OFFICIAL TASK PASS
```

---

# 144. Operational Deploy / Activation Order — FIX-23


After implementation, official acceptance, publication and explicit Owner deploy authorization, deployment order is EXACTLY:

```text
1. if fingerprint-evidence.service exists/runs:
   disable/stop it before checkout mutation

2. verify target Git SHA/tree

3. perform controlled Git checkout/artifact update

4. verify exact worktree/artifact coherence

5. provision/update external systemd unit

6. provision endpoint/TLS/firewall/producer configuration

7. keep:
   DEVICE_FINGERPRINT_EVIDENCE_ENABLED=false
   service=disabled + inactive

8. complete dormant-deploy acceptance

9. separate Owner activation:
   DEVICE_FINGERPRINT_EVIDENCE_ENABLED=true

10. systemd operational intent:
    enable + start

11. verify:
    enabled + active
    loaded artifact identity
    TLS/API health
    schema user_version
    quick_check
    production registry empty
    no packet producer active

12. foundation activation acceptance
```

There is NO checkout/artifact mutation before stopping an already-running evidence service.

Permanent future invariant:

```text
before ANY Git checkout/artifact mutation
under /opt/CaptivePortal:

stop fingerprint-evidence.service
if it is alive from that checkout
```

Task-01 activation does not activate packet collection.

---

# 145. Rollback / Deactivation — FIX-22

Operational deactivation intent:

```text
systemd:
disable + stop

DEVICE_FINGERPRINT_EVIDENCE_ENABLED=false
```

Code rollback, if required, occurs only after `fingerprint-evidence.service` is stopped.

Then normal controlled Git artifact rollback may occur.

No source DB restore.

No Authorization rollback.

Fingerprint DB remains isolated and may be preserved until explicit data disposition.

Exact systemctl command syntax belongs to deployment/infra procedure.

---

---

# 146. Owner / Infrastructure Freeze — COMPLETE

Owner/Infra freeze is accepted as binding input to this FINAL.

Owner values:

```text
P1 normalized evidence retention =
30 days

maximum future clock skew =
120 seconds

maximum delayed event age =
86400 seconds

P2 durable retention =
0
```

Status:

```text
FROZEN
```

These are no longer FINAL blockers.

---

# 147. Central Evidence Service Endpoint — FROZEN

Central host:

```text
CaptivPortal production VM
192.168.0.202
```

Frozen endpoint:

```text
DEVICE_FINGERPRINT_BIND_ADDRESS =
192.168.0.202

DEVICE_FINGERPRINT_PORT =
9443

DEVICE_FINGERPRINT_TLS_CERT_PATH =
/etc/captive-portal/device-fingerprint/server.crt

DEVICE_FINGERPRINT_TLS_KEY_PATH =
/etc/captive-portal/device-fingerprint/server.key

DEVICE_FINGERPRINT_API_ALLOWED_NETWORKS =
192.168.0.0/24
```

Architecture remains:

```text
direct TLS

NO reverse proxy

request.remote_addr =
authoritative peer

proxy forwarding headers =
NOT TRUSTED
```

Activation precheck:

```text
TCP/9443 MUST be verified unused
on 192.168.0.202 before activation
```

If listener conflict exists:

```text
STOP
→ Owner / Tech Lead
```

No silent alternate port.

---

# 148. TLS Material / Filesystem / Service Identity — FROZEN

Systemd identity:

```text
User =
admin

Group =
admin
```

DB directory:

```text
/opt/CaptivePortal/data
admin:admin
0750
```

DB:

```text
/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3
admin:admin
0640
```

Writer lock:

```text
/opt/CaptivePortal/data/device_fingerprint_evidence.writer.lock
admin:admin
0640
```

TLS directory:

```text
/etc/captive-portal/device-fingerprint
root:admin
0750
```

Certificate:

```text
/etc/captive-portal/device-fingerprint/server.crt
root:admin
0640
```

Private key:

```text
/etc/captive-portal/device-fingerprint/server.key
root:admin
0640
```

Certificate must include:

```text
SAN IP = 192.168.0.202
```

No private key in Git/TASK/tests/logs.

Shared `/opt/CaptivePortal/data` ownership precheck remains fail-closed:

```text
if changing ownership would affect another component
→ STOP
→ no recursive chown
→ preserve safe current state
→ return evidence
```

---

# 149. Firewall Contract — FROZEN

Enforcement point:

```text
host-local firewall
on 192.168.0.202
```

Owner:

```text
Owner / Infrastructure administrator
```

Required ingress policy:

```text
ALLOW:
TCP 9443
SOURCE 192.168.0.0/24
DESTINATION 192.168.0.202

DENY:
TCP 9443
from all other source networks
```

Application additionally enforces:

```text
DEVICE_FINGERPRINT_API_ALLOWED_NETWORKS =
192.168.0.0/24
```

Both layers must pass:

```text
host firewall
+
application direct-peer CIDR authorization
```

Future Task-02 may narrow to sensor `/32` only through explicit approved change.

---

# 150. Initial Producer Mapping — FROZEN

Initial producer:

```text
producer_id =
sensor-zefer-01

capture_source_id =
zefer-span-01

site_id =
6a64f17630da7c70d232187a

Site semantic name =
Zefer_Parki

allowed_guest_cidrs =
["192.168.8.0/22"]

allowed_source_kinds =
[
  "dhcp",
  "tcp_syn",
  "tls_client",
  "quic_client"
]
```

Permanent distinction:

```text
allowed_source_kinds
=
producer security authorization

NOT
production EvidenceSchemaRegistry registration
```

Task-01 production EvidenceSchemaRegistry remains:

```text
EMPTY
```

Task-01 foundation activation therefore does NOT accept production device evidence for these kinds until Task-02 registers production schemas.

---

# 151. Bearer Credential Lifecycle — FROZEN

Real credential MUST NOT appear in:

```text
Git
TASK
PLAN
ADR
PR
handoff
tests
fixtures
chat documentation
logs
```

Generation:

```text
48 random bytes

Python stdlib:
secrets.token_urlsafe(48)

base64url without padding

expected length =
64

must satisfy:
[A-Za-z0-9_-]{32,256}
```

Never manually invent the token.

Central storage/injection:

```text
/etc/default/captive-portal

inside:
DEVICE_FINGERPRINT_PRODUCERS_JSON
```

Recommended host file protection:

```text
owner=root
group=admin
mode=0640
```

No application fallback/default secret.

`.env.example` contains placeholders only.

Producer-side storage belongs to Task-02 and must remain:

```text
outside Git

service-readable only

not command-line

not telemetry
```

Rotation procedure:

```text
1. pause producer delivery
   or retain through bounded producer spool

2. generate a completely new credential

3. update protected central
   DEVICE_FINGERPRINT_PRODUCERS_JSON

4. update protected producer-side secret

5. controlled restart/reload
   fingerprint-evidence.service

6. restart/reload producer
   when Task-02 exists

7. verify new credential accepted

8. verify old credential
   → 401 invalid_credential

9. securely remove old credential

10. resume producer delivery
```

V1 has one active credential per producer.

No dual-token grace mechanism.

---

# 152. Production Prechecks — FAIL CLOSED

Normal deployment prechecks remain mandatory:

```text
TCP/9443 unused on 192.168.0.202

TLS certificate exists

TLS key exists

certificate SAN contains 192.168.0.202

admin can read TLS material

DB directory current ownership/mode verified

no unsafe recursive ownership change required

firewall policy implemented and verified

DEVICE_FINGERPRINT_PRODUCERS_JSON
contains frozen mapping

actual secret remains external
```

A failed precheck authorizes NO silent substitution.

Result:

```text
STOP
→ Owner / Tech Lead
```

No alternate:

```text
port
bind
path
user/group
network
Site
producer identity
```

may be invented by Coder/deploy operator.

---

# 153. Implementation / Acceptance Governance — MANDATORY

Execution contract:

```text
execution mode =
implementation

executor =
Coder

TASK-scoped test responsibility =
agent / focused module tests only

production execution =
NO

merge =
Owner only

deploy / activation =
separate Owner-authorized workflow
```

Coder implementation begins ONLY after:

```text
TASK-DEVICE-FINGERPRINT-01-FINAL issued by Architect
+
TechLead10 FINAL consistency PASS
+
Owner explicit implementation authorization
```

This FINAL currently satisfies only the first condition.

---

# 154. Gate A — Coder Focused Verification

Required:

```text
YES
```

Use the exact focused commands frozen by R7.

Command group 1:

```bash
python -m pytest -q \
  tests/device_fingerprint/test_config.py \
  tests/device_fingerprint/test_validation.py \
  tests/device_fingerprint/test_schema_registry.py
```

Command group 2:

```bash
python -m pytest -q \
  tests/device_fingerprint/test_repository.py \
  tests/device_fingerprint/test_read_service.py
```

Command group 3:

```bash
python -m pytest -q \
  tests/device_fingerprint/test_api.py \
  tests/device_fingerprint/test_service.py \
  tests/device_fingerprint/test_telemetry.py \
  tests/device_fingerprint/test_cli.py
```

Static/module checks:

```bash
python -m compileall -q app/device_fingerprint
```

```bash
git diff --check
```

Coder records:

```text
exact implementation baseline

changed/new files

exact commands

passed

skipped

failed

environment

candidate/patch identity

anything not executed
```

Coder does NOT run broader/full regression.

---

# 155. Gate B — Tech Lead Static / Source Review

Required:

```text
YES
```

Mandatory after Coder handoff.

Tech Lead verifies:

```text
FINAL conformance

allowed-file boundary

no run.py change

no unrelated domain change

no new dependency

schema/index identity

API/wire identity

config/env identity

security boundary

shutdown/writer-lock lifecycle

privacy/logging boundary

documentation reconciliation
```

Result:

```text
PASS
```

or:

```text
RETURN TO CODER
```

No publication before Gate B PASS.

---

# 156. Gate C — Fresh Windows Central Lab Full Regression

Required:

```text
YES
```

The current approved official gate MUST be discovered and verified immediately before execution.

Known runner at FINAL assembly time:

```text
C:\CaptivPortal-Lab\lab-test-v7-strict.cmd
```

Permanent rule:

```text
discover + verify current approved runner
before execution
```

Physical operator:

```text
Owner
```

Technical gate direction / evidence analysis:

```text
Tech Lead
```

PASS/FAIL authority:

```text
Owner + Tech Lead
```

Candidate must be:

```text
clean
immutable
exactly identified
```

Any strict regression:

```text
FAIL
→ candidate not accepted
→ normal publication prohibited
```

---

# 157. Gate D — Linux Production-Compatible Task-01 Gate

Required:

```text
YES
```

Environment:

```text
dedicated Owner Linux/WSL acceptance environment

NOT production 192.168.0.202
```

Use the SAME exact candidate that passed preceding required gates.

Minimum Linux proof:

```text
module imports / compile

POSIX DB + writer-lock behavior

SQLite WAL / quick_check / schema signature

DB/lock permissions behavior

signal lifecycle

maintenance-thread lifecycle

atomic active-ingest shutdown drain

writer lock retained through hard-shutdown containment

direct TLS startup
using controlled Lab TLS material

authenticated /health over TLS

Bearer rejection

direct-peer network authorization

protected JSON 404/405 behavior

disabled CLI exit 0

enabled startup fail-closed
on invalid TLS/config

no dependency on main captive-portal.service
```

Production certificates/secrets are NOT required.

Use controlled Lab values only.

---

# 158. Gate E — Failure-Isolation Proof

Required:

```text
YES
```

Must prove:

```text
fingerprint foundation disabled
→ core CaptivPortal authorization unaffected

fingerprint service absent/stopped/failed
→ core CaptivPortal authorization unaffected

fingerprint DB unavailable
→ main CaptivPortal runtime unaffected
```

This is cross-module acceptance.

Coder does NOT execute this official proof.

Execution/PASS authority:

```text
Owner
+
Tech Lead
+
Central Lab as directed
```

Failure:

```text
candidate not accepted
```

---

# 159. Gates Explicitly NOT Required for Task-01 Pre-Publication

```text
packet-sensor production gate =
NO / Task-02

Suricata throughput gate =
NO / Task-02

SPAN dedup gate =
NO / Task-02

classifier accuracy gate =
NO / Task-04

Device Card/browser gate =
NO / Task-06

production-size fingerprint traffic PERF =
NO / deferred until producer/sensor workload exists

production ingest =
NO

production deployment =
NO

production activation =
NO
```

Task-01 still requires all bounded functional/storage/security gates defined above.

---

# 160. Exact Candidate Identity Rule

All mandatory gates apply to ONE immutable candidate.

Record:

```text
baseline commit/tree

candidate patch SHA256
or
immutable LAB candidate commit/tree

complete changed-file list
```

Normal acceptance invariant:

```text
ALL mandatory gates PASS
on exact candidate
→ candidate accepted
```

Any code/test/config/documentation change after acceptance:

```text
NEW candidate identity
```

Tech Lead then decides which gates must be rerun.

Where tree-preserving publication/merge strategy applies:

```text
accepted candidate tree
=
publication commit tree
=
PR head tree
=
accepted merge tree
```

No publication artifact may contain unaccepted modifications.

---

# 161. Publication Condition

Before ALL mandatory gates PASS:

```text
NO normal publication commit

NO push

NO PR
```

After all mandatory gates PASS and Owner + Tech Lead accept the exact candidate, Tech Lead may SEPARATELY authorize Coder to perform:

```text
publication commit

branch

push

Draft PR
```

That authorization does NOT authorize:

```text
merge

deploy

activation
```

Merge remains Owner-controlled.

Deploy remains separate.

Activation remains separate.

---

# 162. Final Coder Handoff Contract

Coder handoff MUST include:

```text
implementation baseline

exact candidate identity

complete changed-file list

new test-file list

exact focused commands

actual focused results

known skips/failures

static checks

Central Lab =
PENDING / external at Coder handoff

Linux gate =
PENDING / external at Coder handoff

repository actions actually performed

repository actions NOT performed

risks / stop conditions

confirmation:
NO merge
NO deploy
NO activation
```

Coder handoff is not official acceptance.

---

# 163. Final Authorized File Boundary

The application/config/governance/documentation file boundary is exactly the boundary frozen earlier in this FINAL.

No implementation may add another file outside it without:

```text
STOP
→ Tech Lead review
```

Permanent critical no-touch:

```text
run.py

Visitor Registry source domain

Visit Lifecycle source domain

Observation source domain

Current State source domain

Traffic Projection source domain

Analytics source domain

Admin Web source domain

main web/auth composition
```

Task-01 adds no dependency.

---

# 164. Deployment / Activation Boundary

Even after accepted publication/merge:

```text
DEPLOY != ACTIVATION
```

Production deployment requires a separate Owner-authorized workflow.

Production activation requires a separate Owner-authorized step.

Task-01 activation may provision:

```text
foundation service
producer authorization mapping
Bearer secret
Site/CIDR/source authorization
```

but:

```text
production EvidenceSchemaRegistry =
EMPTY
```

and:

```text
no physical packet producer active
```

Therefore:

```text
Task-01 foundation activation
!=
packet collection activation
```

Packet sensor / SPAN / Suricata / producer activation remains Task-02.

---

# 165. FINAL Status

```text
TASK =
TASK-DEVICE-FINGERPRINT-01-FINAL

ARCHITECTURE =
PASS

DEVICE-FINGERPRINT-00 =
CLOSED / DO NOT REOPEN

R7 =
TECHLEAD10 PASS

FIX-1…FIX-25 =
CLOSED / ACCEPTED / PRESERVED

OWNER VALUES =
FROZEN

INFRA VALUES =
FROZEN

IMPLEMENTATION CONTRACT =
COMPLETE

CURRENT GATE =
TECHLEAD10 FINAL CONSISTENCY RECHECK

IMPLEMENTATION AUTHORIZATION =
NOT GRANTED

CODER =
HOLD

BRANCH =
NOT AUTHORIZED

COMMIT =
NOT AUTHORIZED

PUSH =
NOT AUTHORIZED

PR =
NOT AUTHORIZED

MERGE =
NOT AUTHORIZED BY THIS FINAL

DEPLOY =
NOT AUTHORIZED

ACTIVATION =
NOT AUTHORIZED
```

---

# 166. Next Workflow

```text
TASK-DEVICE-FINGERPRINT-01-FINAL
        ↓
TechLead10 FINAL consistency recheck
        ↓
PASS
        ↓
Owner explicit implementation authorization
        ↓
Coder implementation
        ↓
Gate A focused verification
        ↓
Coder handoff
        ↓
Gate B Tech Lead static/source review
        ↓
Gate C fresh Windows Central Lab
        ↓
Gate D Linux production-compatible gate
        ↓
Gate E failure-isolation proof
        ↓
Owner + Tech Lead exact-candidate acceptance
        ↓
separate publication authorization
        ↓
branch / publication commit / push / Draft PR
        ↓
Owner-controlled merge
        ↓
separate deploy authorization
        ↓
separate activation authorization
```

Until Owner explicitly authorizes implementation:

```text
CODER = HOLD

NO IMPLEMENTATION

NO BRANCH

NO COMMIT

NO PUSH

NO PR

NO DEPLOY

NO ACTIVATION
```

**End of TASK-DEVICE-FINGERPRINT-01-FINAL.**
