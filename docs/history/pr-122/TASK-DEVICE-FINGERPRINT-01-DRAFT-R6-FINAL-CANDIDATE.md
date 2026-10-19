# TASK-DEVICE-FINGERPRINT-01-DRAFT-R6-FINAL-CANDIDATE

## Passive Mobile / Personal Device Fingerprint Evidence Foundation

**Project:** CaptivPortal  
**Program:** Passive Mobile / Personal Device Fingerprinting  
**Research predecessor:** `DEVICE-FINGERPRINT-00 FINAL R2`  
**Parent task:** `TASK-DEVICE-FINGERPRINT-01`  
**Revision:** `DRAFT-R6-FINAL-CANDIDATE`  
**Status:** `FOR TECHLEAD10 FINAL CONTRADICTION / SOURCE RECHECK`  
**Implementation-ready:** `NO`  
**Implementation authorization:** `NOT GRANTED`  
**Coder:** `HOLD`  
**Branch / commit / push / PR / deploy:** `NOT AUTHORIZED`  
**Prepared:** 2026-09-14

---

# 0. Control Gate — FIX-18…FIX-22 INCORPORATED

```text
DEVICE-FINGERPRINT-00 =
CLOSED / FINAL R2 PASS

FIX-1…FIX-17 =
PRESERVED / ACCEPTED

TECHLEAD10 R5 RECHECK =
FIX-18…FIX-22

DRAFT-R6-FINAL-CANDIDATE =
FIX-1…FIX-22 INCORPORATED

ARCHITECTURE DIRECTION =
PASS / ACCEPTED

NEW RESEARCH =
NOT REQUIRED

IMPLEMENTATION-READY =
NO

CODER =
HOLD

IMPLEMENTATION =
NOT AUTHORIZED
```

R6 changes ONLY the final repository-governance / lifecycle / wire-contract issues:

```text
FIX-18 =
repository Python entrypoint instruction
+ complete canonical documentation surface

FIX-19 =
maintenance thread lifecycle
+ active-ingest shutdown drain

FIX-20 =
complete HTTP error codes
+ exact POST/health response shapes

FIX-21 =
fixed constants
vs configurable defaults/runtime config

FIX-22 =
remove source-health cursor
+ exact systemd activation/deactivation
+ stale R5 labels
```

No architecture research is reopened.

---

# 1. Repository / Research Baseline

Current repository baseline:

```text
REPOSITORY =
ZaurNavi/CaptivePortal

main HEAD =
14ab4034dd9fe170b33795322c29c543bf6c2544

research runtime parent =
3dc85735ddf5d05dd20733d15dfe1c22c9c4fde5
```

Fresh Tech Lead recheck established:

```text
NO MATERIAL RUNTIME CODE DRIFT

research/runtime rebind =
VALID

DEVICE-FINGERPRINT-00 =
DO NOT REOPEN
```

Fresh baseline must be rechecked again immediately before implementation authorization.

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

# 6. Controlled Auxiliary Entrypoint Exception — FIX-12/FIX-18

Repository baseline currently contains an absolute Python instruction applying to:

```text
app/**/*.py
run.py
```

that says:

```text
run.py remains the only process entrypoint
```

Task-01 freezes the repository-governance correction:

```text
run.py remains the process entrypoint
for captive-portal.service / main CaptivPortal runtime.

Auxiliary service process entrypoints are forbidden
unless explicitly authorized by an approved TASK/architecture contract.

An authorized auxiliary CLI is a separate composition root
and MUST NOT be registered into the main run.py runtime.
```

For this TASK only:

```text
python3 -m app.device_fingerprint.cli run
```

is an explicitly authorized auxiliary service entrypoint.

Permanent:

```text
run.py remains NO-TOUCH

run.py remains the sole composition root
for captive-portal.service

fingerprint-evidence.service is separate

no fingerprint blueprint/runtime registration
inside main run.py/create_app composition
```

The implementation MUST update:

```text
.github/instructions/python.instructions.md
```

to the generic controlled-exception wording above.

This also reconciles the instruction with the already accepted auxiliary Traffic Projection service precedent.

No additional process entrypoint is authorized.

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

# 9. API Namespace / Version

Frozen:

```text
API_VERSION =
device-fingerprint.internal.v1

API_PREFIX =
/api/internal/device-fingerprint/v1
```

Endpoints:

```text
POST /api/internal/device-fingerprint/v1/evidence/batch

POST /api/internal/device-fingerprint/v1/source-health/batch

GET  /api/internal/device-fingerprint/v1/health
```

No other Task-01 HTTP routes.

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

# 12. V1 Authentication — FIX-3/FIX-7

Frozen:

```text
HTTPS
+
per-producer Bearer
+
management-network CIDR allowlist
+
strict producer authorization
```

Request order follows current internal API conventions:

```text
1. reject query-string credential names
2. parse Authorization: Bearer
3. constant-time credential match
4. enforce request.remote_addr CIDR allowlist
5. resolve authenticated producer
6. validate body producer_id matches authenticated producer
7. validate capture/Site/source authorization
```

Query-string credential names are rejected case-insensitively BEFORE Bearer authentication:

```text
token
access_token
bearer_token
```

Presence of any:

```text
400
```

Missing/invalid credential:

```text
401
WWW-Authenticate: Bearer
```

Authenticated but unauthorized scope:

```text
403
```

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

# 22. Clock Bounds — TECH LEAD ACCEPTED / OWNER PENDING

Current frozen recommendation:

```text
MAX_FUTURE_CLOCK_SKEW_SECONDS =
120

MAX_DELAYED_EVENT_AGE_SECONDS =
86400
```

Validation against central UTC now:

```text
observed_at > now + 120s
→ 400

observed_at < now - 86400s
→ 400
```

No degraded acceptance.

No exact future identity correlation outside accepted time contract.

Privacy retention age always starts from:

```text
observed_at
```

not `ingested_at`.

Owner approval is still required before FINAL.

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

# 27. Configurable Defaults + Runtime Config Concepts — FIX-21

The following are repository DEFAULTS for environment-configurable settings:

```text
DEFAULT_RETENTION_DAYS = 30
Owner pending

DEFAULT_MAX_FUTURE_SKEW_SECONDS = 120
Owner pending

DEFAULT_MAX_DELAYED_EVENT_AGE_SECONDS = 86400
Owner pending

DEFAULT_MAX_DB_BYTES = 1_073_741_824
DEFAULT_MAX_HTTP_REQUEST_BYTES = 1_048_576
DEFAULT_MAX_EVENTS_PER_BATCH = 100
DEFAULT_MAX_PAYLOAD_BYTES = 8_192
DEFAULT_MAX_CONCURRENT_INGEST_REQUESTS = 2
```

Each valid environment variable overrides ONLY its corresponding default.

Exact mapping:

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

Do not introduce an additional pseudo-constant alias such as:

```text
MAX_PAYLOAD_BYTES
MAX_NORMALIZED_PAYLOAD_BYTES
```

for the same runtime concept.

Owner-approved values replace the three pending defaults before FINAL.

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

# 30. Producers JSON Serialization — FIX-3/FIX-11

Exact environment:

```text
DEVICE_FINGERPRINT_PRODUCERS_JSON
```

Value is a JSON array containing:

```text
1..32 producer objects
when feature is enabled
```

Each object has EXACT keys:

```json
{
  "producer_id": "sensor-zefer-01",
  "bearer_token": "<secret>",
  "capture_source_id": "zefer-span-01",
  "site_id": "0123456789abcdef01234567",
  "allowed_guest_cidrs": ["192.168.8.0/22"],
  "allowed_source_kinds": ["dhcp", "tcp_syn", "tls_client", "quic_client"]
}
```

No extra keys.

Validation:

```text
producer_id exact machine-id contract

bearer_token 32..256

capture_source_id exact machine-id contract

site_id exact 24 lowercase hex

allowed_guest_cidrs:
1..32 unique strict networks

allowed_source_kinds:
1..32 unique valid source-kind identifiers
```

Producer secret is always redacted from repr/telemetry.

Sensor `capture_interface` is NOT part of central Task-01 config.

---

# 31. Direct TLS Configuration

When enabled:

```text
DEVICE_FINGERPRINT_TLS_CERT_PATH
DEVICE_FINGERPRINT_TLS_KEY_PATH
```

must be:

```text
absolute
non-empty
readable at service startup
distinct files
```

The service starts no plain-HTTP fallback.

If TLS material is unavailable:

```text
startup FAIL
no listener
```

Exact production file paths/ownership are INFRA decisions required before FINAL.

---

# 32. Management Network Configuration

```text
DEVICE_FINGERPRINT_API_ALLOWED_NETWORKS
```

is strict CSV of CIDRs.

When enabled:

```text
must contain 1..32 networks
no duplicate networks
strict ip_network(..., strict=True)
```

`request.remote_addr` must fall inside at least one configured network.

Application CIDR check is mandatory even if firewall ACL exists.

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

# 49. Exact HTTP Status + Error Code Contract — FIX-20

Exact POST/health error contract:

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

with sanitized response and telemetry.

Do NOT remap an unexpected application bug to 400 or repository-unavailable unless it objectively belongs there.

For 401:

```text
WWW-Authenticate: Bearer
```

For 429:

```text
Retry-After: 1
```

No other V1 error code is emitted by these endpoints.

---

# 50. Exact POST + Health Response Shapes — FIX-20

All responses are bounded, non-sensitive and deterministic.

## POST batch success — EXACT

Both batch endpoints return exactly:

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

For 409 specifically:

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

No conflict_count or other optional conflict metadata.

## GET /health result — EXACT

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

`result.status` is exactly one of:

```text
initializing
ready
degraded
unavailable
stopping
```

`reason` is null or one exact runtime reason_code.

No payload, secret, raw exception, SQL text or sensitive filesystem path is echoed.

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

# 70. Retention Contract — FIX-14


P2 raw/high-risk durable retention:

```text
0
```

P1 device evidence retention:

```text
DEVICE_FINGERPRINT_RETENTION_DAYS
```

Tech Lead recommendation / Owner-pending default:

```text
30 days
```

Source-health P0 retention:

```text
SOURCE_HEALTH_RETENTION_DAYS = 30
```

fixed repository constant in V1.

Therefore:

```text
evidence cutoff =
central_now - config.retention_days
```

```text
source-health cutoff =
central_now - 30 days
```

Both durable retention clocks use observed_at, not ingested_at.

Owner approval is required only for P1 device-evidence retention.

---

# 71. Retention Cleanup Algorithm — FIX-14


Every 300 seconds, when service is running, maintenance may run.

Evidence cutoff:

```text
central_now - config.retention_days
```

Source-health cutoff:

```text
central_now - SOURCE_HEALTH_RETENTION_DAYS
```

For each table, delete ordered by observed_at + primary row id in chunks of at most 500 rows.

Maximum:

```text
20 chunks / table / pass
```

Maximum row deletions per maintenance pass:

```text
10,000 device evidence
+
10,000 source-health rows
```

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

# 74. Enabled Startup + Maintenance Loop — FIX-19

Exact enabled sequence after repository/app composition:

```text
install SIGTERM/SIGINT handlers

start one maintenance thread

runtime → ready

enter app.run(...)
```

Normal first maintenance pass is delayed:

```text
after RETENTION_SCAN_INTERVAL_SECONDS
```

not immediately on startup.

Loop is fixed-delay, non-overlapping and interruptible:

```text
if stop_event.wait(RETENTION_SCAN_INTERVAL_SECONDS):
    exit

run one bounded retention pass

repeat
```

Only one maintenance pass may execute at once.

Existing state transitions remain:

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

# 80. Concurrency Guard + Active Ingest Tracking — FIX-19/FIX-21

Evidence and source-health POST share one:

```text
BoundedSemaphore(
    config.max_concurrent_ingest_requests
)
```

repository default:

```text
DEFAULT_MAX_CONCURRENT_INGEST_REQUESTS = 2
```

Health GET does not consume an ingest slot.

If no slot is immediately available:

```text
429 concurrency_limit
Retry-After: 1
```

No blocking wait.

Runtime owns thread-safe:

```text
active_ingest_count
+
Condition
```

An ingest request becomes active ONLY after:

```text
runtime state accepts writes
+
concurrency slot acquired
```

Exact lifecycle:

```text
acquire semaphore nonblocking

register active_ingest_count += 1

execute ingest

finally:
    active_ingest_count -= 1
    notify Condition
    release semaphore
```

Transition to stopping prevents NEW ingest registrations.

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

# 103. Signal / Total Shutdown Budget — FIX-19

Exact SIGTERM/SIGINT handler performs ONLY:

```text
1. runtime state → stopping
2. stop accepting new ingest
3. set maintenance stop event
4. raise SystemExit(0)
```

Signal handler MUST NOT wait, join, run retention, audit DB health, close DB or release lock.

`SystemExit(0)` unwinds blocking Flask/Werkzeug `app.run(...)`.

Outer idempotent finalizer creates ONE TOTAL deadline:

```text
deadline =
monotonic_now + SHUTDOWN_TIMEOUT_SECONDS
```

where:

```text
SHUTDOWN_TIMEOUT_SECONDS = 20.0
```

Finalization order:

```text
1. accepting writes already false

2. wait on active-ingest Condition
   until active_ingest_count == 0
   OR deadline

3. join maintenance thread
   using ONLY remaining time
   before SAME deadline

4. close repository/resources

5. release writer lock LAST

6. best-effort stopped telemetry
```

The budget is one shared 20-second application shutdown budget, not 20s+20s.

If deadline expires, emit sanitized shutdown-timeout telemetry and continue termination with no new ingest accepted.

Finalization is idempotent.

`TimeoutStopSec=30` stays outside and larger than the app shutdown budget.

---

# 104. Systemd Install / Activation / Mutable Artifact Lifecycle — FIX-12/FIX-22

External unit:

```text
fingerprint-evidence.service
```

Core shape:

```text
Type=simple
WorkingDirectory=/opt/CaptivePortal
EnvironmentFile=/etc/default/captive-portal
ExecStart=/usr/bin/python3 -m app.device_fingerprint.cli run
Restart=on-failure
RestartSec=5
TimeoutStopSec=30
KillSignal=SIGTERM
```

No socket activation.

## Before Owner activation

```text
service installed
disabled
inactive

DEVICE_FINGERPRINT_EVIDENCE_ENABLED=false
```

## Activation

```text
DEVICE_FINGERPRINT_EVIDENCE_ENABLED=true

systemd operational intent:
enable + start
```

Resulting intent:

```text
enabled + active
```

After reboot an activated service is eligible to start automatically.

## Deactivation / rollback

```text
systemd operational intent:
disable + stop

DEVICE_FINGERPRINT_EVIDENCE_ENABLED=false
```

Exact systemctl commands belong to deployment/infra procedure, not Coder implementation.

## Mutable artifact invariant

No Git checkout/artifact mutation under `/opt/CaptivePortal` while this service from that checkout is alive.

Before checkout mutation it must be stopped. After controlled update, restart only if activation state requires and verify loaded artifact identity.

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

# 110. DB File Permissions

On POSIX after DB creation:

```text
chmod 0640
```

Writer lock:

```text
0640
```

Parent directory must already be controlled/safe or be created under project-approved path.

Exact OS owner/group is INFRA-owned before FINAL.

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

# 128. Exact Application + Canonical Governance/Documentation Boundary — FIX-18

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
```

Only to replace the absolute single-entrypoint rule with the controlled auxiliary-entrypoint policy from section 6.

## MODIFY canonical documentation

```text
AGENTS.md
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

## NEW current module contract

```text
docs/modules/device-fingerprint.md
```

After implementation:

```text
status =
current module contract

repository status =
current; default disabled
```

It summarizes the current module ownership/runtime/security/persistence and links to the accepted FINAL instead of duplicating the whole TASK.

Required doc semantics:

```text
docs/README.md
→ knowledge map/current modules entry

docs/module-index.md
→ Device Fingerprint Evidence
   current; default disabled

docs/configuration.md
→ DEVICE_FINGERPRINT_* defaults
   enabled requirements
   secret externality

docs/security.md
→ dedicated direct-TLS internal service
   per-producer Bearer
   direct-peer CIDR allowlist
   request.remote_addr authority
   no proxy-header trust

docs/logging.md
→ captivportal.device_fingerprint
   safe telemetry
   fingerprint namespace query stripping
   no payload/Bearer/MAC/IP operational logging

docs/project-inventory.md
→ auxiliary process/persistence/default-disabled state

docs/deployment.md
→ artifact-owned stop/update/restart invariant

docs/architecture.md / README*
→ controlled auxiliary composition exception
```

No unrelated documentation rewrite.

---

# 129. Explicit NO-TOUCH Outside R6 Boundary

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

# 131. Exact Test File Boundary — R6

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

# 138. Required HTTP Security Tests — FIX-15


Must prove:

```text
dedicated Flask app only
API prefix exact

query key rejection is case-insensitive for:
token
access_token
bearer_token

presence of any forbidden query credential
→ 400 before Bearer authentication

missing Bearer → 401
wrong scheme → 401
non-ASCII/malformed Bearer → 401
valid syntax wrong Bearer → 401

valid syntax secret uses hmac.compare_digest
against every configured producer

disallowed request.remote_addr → 403

X-Forwarded-For ignored
Forwarded ignored
X-Real-IP ignored

body producer mismatch → 403
Site mismatch → 403
capture source mismatch → 403
source kind mismatch → 403

unknown schema → 400

413 limits
429 nonblocking concurrency
503 unavailable/stopping/storage guard

no raw body in response/logging
```

Direct TLS / authoritative peer handling remains an infrastructure acceptance item after concrete endpoint values are frozen.

---

# 139. Required Lifecycle / State Machine Tests — FIX-19/FIX-20

Must prove:

```text
constructor/factory starts NO maintenance thread

enabled CLI starts exactly one maintenance thread

first maintenance pass waits 300s / mocked equivalent

maintenance fixed-delay and non-overlapping

stop_event interrupts wait

initializing → ready

ready → degraded(retention_failed)

degraded → ready

ready/degraded → unavailable(storage_limit)

storage_limit → ready only after accepted recovery proof

storage_unavailable latched

storage_corrupt latched

signal:
runtime→stopping
accepting writes false
stop_event set
SystemExit(0)

active_ingest_count registers only
after runtime acceptance + semaphore acquisition

active ingest unregisters in finally

ONE total 20s shutdown deadline
covers active drain + maintenance join

repository closes after bounded drain/join

writer lock released LAST

shutdown timeout telemetry on deadline exhaustion
```

HTTP health tests verify exact section-50 shape and state/status mapping.

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

# 142. Exact Coder Narrow Test Commands — R6 FROZEN

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

Exact command grouping is frozen in R6 unless TechLead10 returns a new FIX.

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

# 144. Operational Activation / Deployment Lifecycle — FIX-12


After implementation, official acceptance, publication and Owner deploy authorization:

```text
1. deploy code artifact with foundation default disabled

2. ensure fingerprint-evidence.service is stopped

3. verify target Git SHA/tree

4. perform controlled checkout/artifact update

5. verify worktree/artifact coherence

6. provision/update external systemd unit

7. provision endpoint/TLS/firewall/producer config

8. keep DEVICE_FINGERPRINT_EVIDENCE_ENABLED=false
   until separate Owner activation

9. explicit activation:
   set enabled=true

10. start fingerprint-evidence.service

11. verify loaded artifact identity

12. verify TLS/API health

13. verify schema user_version/quick_check

14. verify production evidence schema registry is empty

15. verify no packet producer is active

16. foundation acceptance
```

Permanent checkout invariant:

```text
Before ANY future Git checkout/artifact mutation
under /opt/CaptivePortal:

fingerprint-evidence.service must be stopped
if it is running from that checkout.
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

# 146. OWNER DECISION REQUIRED — P1 Retention

TechLead recommendation:

```text
P1 normalized evidence retention =
30 days
```

Architect recommendation:

```text
ACCEPT 30 days
```

P2:

```text
0 durable
```

already frozen.

FINAL is blocked on explicit Owner acceptance/rejection of:

```text
30 days
```

---

# 147. OWNER DECISION REQUIRED — Clock Bounds

TechLead10 accepts the architecture proposal:

```text
maximum future skew =
120 seconds

maximum delayed event age =
86400 seconds
```

FINAL is blocked on explicit Owner acceptance/rejection.

No Coder choice.

---

# 148. INFRA DECISIONS REQUIRED — Production Endpoint

Need real values:

```text
DEVICE_FINGERPRINT_BIND_ADDRESS

DEVICE_FINGERPRINT_PORT

DEVICE_FINGERPRINT_TLS_CERT_PATH

DEVICE_FINGERPRINT_TLS_KEY_PATH

DEVICE_FINGERPRINT_API_ALLOWED_NETWORKS
```

Architecture already freezes:

```text
direct TLS in fingerprint-evidence.service

request.remote_addr authoritative

no reverse proxy

no X-Forwarded-For trust
```

Only concrete values remain.

---

# 149. INFRA DECISIONS REQUIRED — Service OS Identity

Need exact:

```text
systemd User

systemd Group

ownership/group of:
DB directory
DB/lock
TLS certificate
TLS private key
```

Requirements:

```text
service can read TLS cert/key

service can create/write DB/lock

no broader permission than necessary
```

Coder must not choose OS identity.

---

# 150. INFRA DECISIONS REQUIRED — Firewall / ACL Owner

Need exact deployment contract:

```text
which host/firewall enforces
management-network restriction

allowed sensor/management source CIDRs

who owns rule deployment
```

Application CIDR allowlist remains mandatory regardless.

---

# 151. INFRA DECISIONS REQUIRED — Initial Producer Mapping

Need actual initial V1 configuration values:

```text
producer_id

capture_source_id

site_id

allowed_guest_cidrs

allowed_source_kinds
```

and external secret generation/rotation procedure.

A future Task-02 sensor can reuse the provisioned producer identity.

No credential value goes into this document/Git.

---

# 152. Infrastructure Values Must Not Be Inferred

Do NOT infer endpoint values from:

```text
known CaptivPortal VM IP

known Site addresses

existing public FQDN

Analytics port

main Flask port
```

Owner/infra must explicitly freeze them.

---

# 153. FINAL Blocking Matrix — R6

```text
FIX-1…FIX-17 =
CLOSED / PRESERVED

FIX-18 =
CLOSED IN R6 CANDIDATE

FIX-19 =
CLOSED IN R6 CANDIDATE

FIX-20 =
CLOSED IN R6 CANDIDATE

FIX-21 =
CLOSED IN R6 CANDIDATE

FIX-22 =
CLOSED IN R6 CANDIDATE
```

Only genuine external FINAL blockers remain:

```text
OWNER:
P1 evidence retention = 30 days acceptance

OWNER:
maximum future skew = 120 seconds acceptance

OWNER:
maximum delayed event age = 86400 seconds acceptance

INFRA:
bind address
port
TLS cert path
TLS key path
allowed management CIDRs
systemd User
systemd Group
DB/lock/TLS ownership
firewall enforcement
initial producer/capture mapping
credential generation/rotation procedure
```

No research or Coder-facing architecture blocker remains in R6 candidate.

---

# 154. TechLead10 Recheck Checklist — R6

Please recheck ONLY:

```text
FIX-18
python.instructions controlled entrypoint policy
complete canonical docs surface
new docs/modules/device-fingerprint.md

FIX-19
one maintenance thread
delayed first pass
non-overlap
active_ingest_count
one total 20s shutdown budget
writer lock released last

FIX-20
exact error codes/messages
no optional 409 metadata
exact POST success
exact /health result
health query policy

FIX-21
fixed constants
vs DEFAULT_* configurable defaults
vs config.* runtime values
no competing payload-limit names

FIX-22
no source-health cursor
disabled/inactive before activation
enable+start activation
disable+stop rollback
R6 labels
```

Also confirm FIX-1…FIX-17 semantics remain preserved and Owner/Infra blockers remain external only.

Expected:

```text
PASS
```

or a narrow explicit remaining FIX.

---

# 155. R6 Final Candidate Status

```text
TASK =
TASK-DEVICE-FINGERPRINT-01-DRAFT-R6-FINAL-CANDIDATE

ARCHITECTURE DIRECTION =
PASS

RESEARCH =
CLOSED / DO NOT REOPEN

FIX-1…FIX-22 =
INCORPORATED

CURRENT GATE =
TECHLEAD10 FINAL SOURCE / CONTRADICTION RECHECK

IMPLEMENTATION-READY =
NO

CODER =
HOLD

IMPLEMENTATION =
NOT AUTHORIZED

BRANCH =
NOT AUTHORIZED

COMMIT =
NOT AUTHORIZED

PUSH =
NOT AUTHORIZED

PR =
NOT AUTHORIZED

DEPLOY =
NOT AUTHORIZED
```

---

# 156. Next Workflow — R6

```text
TASK-DEVICE-FINGERPRINT-01-DRAFT-R6-FINAL-CANDIDATE
        ↓
TechLead10 final source/contradiction recheck
        ↓
expected PASS
        ↓
Owner freezes:
30d P1 evidence retention
120s future skew
86400s delayed-event age
        ↓
Infra freezes:
bind/port
TLS paths
management CIDRs
systemd User/Group
filesystem ownership
firewall owner/rules
initial producer mapping
credential lifecycle
        ↓
Architect issues:
TASK-DEVICE-FINGERPRINT-01-FINAL
        ↓
TechLead10 FINAL consistency recheck
        ↓
Owner explicit implementation authorization
        ↓
Coder
```

Until then:

```text
CODER = HOLD
NO IMPLEMENTATION
NO BRANCH
NO COMMIT
NO PUSH
NO PR
NO DEPLOY
```

**End of DRAFT-R6-FINAL-CANDIDATE.**

---

