# TASK-DEVICE-FINGERPRINT-01-DRAFT-R4-FINAL-CANDIDATE

## Passive Mobile / Personal Device Fingerprint Evidence Foundation

**Project:** CaptivPortal  
**Program:** Passive Mobile / Personal Device Fingerprinting  
**Research predecessor:** `DEVICE-FINGERPRINT-00 FINAL R2`  
**Parent task:** `TASK-DEVICE-FINGERPRINT-01`  
**Revision:** `DRAFT-R4-FINAL-CANDIDATE`  
**Status:** `FOR TECHLEAD10 FINAL CONTRADICTION / SOURCE RECHECK`  
**Implementation-ready:** `NO`  
**Implementation authorization:** `NOT GRANTED`  
**Coder:** `HOLD`  
**Branch / commit / push / PR / deploy:** `NOT AUTHORIZED`  
**Prepared:** 2026-09-14

---

# 0. Control Gate

```text
DEVICE-FINGERPRINT-00 =
CLOSED / FINAL R2 PASS

DRAFT-R2 =
TECH LEAD FIX-1…FIX-6

DRAFT-R3 =
FIX-1…FIX-6 INCORPORATED

TECHLEAD10 R3 RECHECK =
FIX-7…FIX-11

DRAFT-R4-FINAL-CANDIDATE =
FIX-1…FIX-11 INCORPORATED

ARCHITECTURE DIRECTION =
ACCEPTED

IMPLEMENTATION-READY =
NO

CODER =
HOLD

IMPLEMENTATION =
NOT AUTHORIZED
```

This document is the FINAL candidate requested by TechLead10.

It is NOT `TASK-DEVICE-FINGERPRINT-01-FINAL`.

No implementation begins until:

```text
TechLead10 source/contradiction recheck
+
Owner/infra decisions frozen
+
Architect issues FINAL
+
Owner explicitly authorizes implementation
```

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

# 6. Central Process Boundary — FIX-7

V1 central process is exactly:

```text
fingerprint-evidence.service
        ↓
python3 -m app.device_fingerprint.cli run
        ↓
DEDICATED Device Fingerprint Flask application
        ↓
ONLY /api/internal/device-fingerprint/v1/*
        ↓
Device Fingerprint Service / Repository
```

This Flask application belongs only to the auxiliary process.

It MUST NOT:

```text
register its blueprint in the main CaptivPortal Flask app

import/run Authorization

depend on main captive-portal.service HTTP health

turn captive-portal.service into fingerprint writer
```

`run.py` remains NO-TOUCH.

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

# 13. Bearer Credential Contract

Each producer credential:

```text
generated outside Git

minimum length =
32 characters

maximum length =
256 characters

non-empty after no trimming ambiguity

never query-string supplied

never logged

redacted from repr

constant-time comparison
```

The configured secret is compared exactly.

Authentication checks every configured producer secret using:

```text
hmac.compare_digest
```

without using plaintext-token dictionary lookup as the authorization decision.

Configuration forbids duplicate secrets, so successful comparison resolves exactly one producer.

Do not silently trim a secret.

Duplicate configured Bearer credentials:

```text
CONFIG ERROR
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

# 24. Exact Environment Variable Names — FIX-11

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

No Coder-defined alternative names.

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

# 26. Exact Resource Constants — FIX-11

Frozen Task-01 R4 values:

```text
SCHEMA_VERSION =
1

BUSY_TIMEOUT_MS =
500

WAL_AUTOCHECKPOINT_PAGES =
1000

JOURNAL_SIZE_LIMIT_BYTES =
67_108_864

MAX_DB_BYTES =
1_073_741_824
(1 GiB logical main database ceiling)

MAX_HTTP_REQUEST_BYTES =
1_048_576
(1 MiB)

MAX_HTTP_RESPONSE_BYTES =
65_536
(64 KiB)

MAX_EVENTS_PER_BATCH =
100

MAX_NORMALIZED_PAYLOAD_BYTES =
8_192
(8 KiB canonical UTF-8 payload/event)

MAX_CONCURRENT_INGEST_REQUESTS =
2

RETENTION_SCAN_INTERVAL_SECONDS =
300

RETENTION_DELETE_CHUNK_ROWS =
500

MAX_RETENTION_CHUNKS_PER_PASS =
20

SHUTDOWN_TIMEOUT_SECONDS =
20.0
```

These values are frozen in R4.

If TechLead10 rejects a value, it returns as an explicit FIX before FINAL.

Coder does not choose them.

---

# 27. Configurable vs Fixed Limits

Environment-configurable within strict bounds:

```text
RETENTION_DAYS

MAX_FUTURE_SKEW_SECONDS

MAX_DELAYED_EVENT_AGE_SECONDS

MAX_DB_BYTES

MAX_HTTP_REQUEST_BYTES

MAX_EVENTS_PER_BATCH

MAX_PAYLOAD_BYTES

MAX_CONCURRENT_INGEST_REQUESTS
```

Repository constants, not environment knobs in V1:

```text
SCHEMA_VERSION=1

BUSY_TIMEOUT_MS=500

WAL_AUTOCHECKPOINT_PAGES=1000

JOURNAL_SIZE_LIMIT_BYTES=67_108_864

MAX_HTTP_RESPONSE_BYTES=65_536

RETENTION_SCAN_INTERVAL_SECONDS=300

RETENTION_DELETE_CHUNK_ROWS=500

MAX_RETENTION_CHUNKS_PER_PASS=20

SHUTDOWN_TIMEOUT_SECONDS=20.0
```

---

# 28. Config Bounds

Strict V1 bounds:

```text
RETENTION_DAYS:
1..90

MAX_FUTURE_SKEW_SECONDS:
0..600

MAX_DELAYED_EVENT_AGE_SECONDS:
60..604800

MAX_DB_BYTES:
67_108_864 .. 8_589_934_592
(64 MiB .. 8 GiB)

MAX_HTTP_REQUEST_BYTES:
65_536 .. 4_194_304
(64 KiB .. 4 MiB)

MAX_EVENTS_PER_BATCH:
1..500

MAX_PAYLOAD_BYTES:
256 .. 65_536

MAX_CONCURRENT_INGEST_REQUESTS:
1..8

PORT:
1..65535
```

Values outside bounds:

```text
CONFIG ERROR
```

---

# 29. Enabled / Disabled Behavior — FIX-11

Default:

```text
DEVICE_FINGERPRINT_EVIDENCE_ENABLED=false
```

When disabled:

```text
CLI `run`
→ exits 0 as intentional disabled no-op

no Flask bind
no TLS listener
no DB creation/migration
no writer lock acquisition
no artifact-owned long-running process remains
```

This avoids a `Restart=on-failure` loop for an intentionally disabled feature.

The unit should remain disabled until controlled activation.

When enabled, configuration is fail-closed and requires:

```text
bind address

port

TLS cert path

TLS key path

non-empty allowed networks

non-empty producer configuration

valid DB/lock paths
```

Missing/invalid required enabled config:

```text
process exits before listener
```

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

# 38. Evidence Body Contract

`POST /evidence/batch` root JSON shape:

```json
{
  "producer_id": "sensor-zefer-01",
  "events": [
    {
      "source_event_id": "00000000-0000-4000-8000-000000000001",
      "source_kind": "test_kind",
      "source_subtype": null,
      "extractor_name": "test-extractor",
      "extractor_version": "1.0.0",
      "feature_schema_version": 1,
      "rule_version": null,
      "site_id": "0123456789abcdef01234567",
      "capture_source_id": "zefer-span-01",
      "observed_at": "2026-09-14T10:00:00.000Z",
      "observed_mac": "AA:BB:CC:DD:EE:FF",
      "observed_ip": "192.168.10.50",
      "quality_state": "valid",
      "payload": {}
    }
  ]
}
```

`test_kind` above is illustrative test-only, not a production registration.

Root has EXACT:

```text
producer_id
events
```

No additional root fields.

---

# 39. Evidence Event Required / Nullable Fields

Required:

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

Nullable/optional but must be present in canonical event contract:

```text
source_subtype
rule_version
observed_ip
```

An implementation may require exact event keys including nullable keys so canonical event shape is deterministic.

`payload` must be a JSON object.

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

# 41. Canonical Payload JSON — FIX-4

After source-schema validation, central service constructs canonical payload JSON:

```python
json.dumps(
    approved_payload,
    ensure_ascii=True,
    allow_nan=False,
    sort_keys=True,
    separators=(",", ":"),
)
```

Then:

```text
UTF-8 encode
```

Forbidden:

```text
NaN
Infinity
-Infinity
unknown fields
producer-owned serialized JSON bytes
insignificant-whitespace variance
```

Maximum canonical UTF-8 payload size:

```text
MAX_PAYLOAD_BYTES
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

# 49. Evidence HTTP Status Contract — FIX-8

```text
200 =
complete successful batch
including idempotent duplicate NO-OPs

400 =
malformed request
invalid JSON
query-string credential
canonical validation failure
unknown/unsupported evidence schema
duplicate source_event_id inside same request

401 =
missing/invalid Bearer

403 =
authenticated producer unauthorized for:
source network
producer_id
Site
capture_source_id
source_kind

409 =
existing retry key
with conflicting immutable content

413 =
HTTP request / batch / event / payload
limit exceeded

429 =
bounded ingest concurrency exhausted

503 =
repository temporarily unavailable
hard storage guard
service unavailable/stopping
```

No other success class for ingest.

---

# 50. Deterministic Response Contract

Every response:

```text
bounded
non-sensitive
deterministic
```

Success shape:

```json
{
  "api_version": "device-fingerprint.internal.v1",
  "request_id": "<canonical uuid>",
  "result": {
    "status": "ok",
    "received": 10,
    "inserted": 8,
    "duplicate_noop": 2
  }
}
```

Error shape:

```json
{
  "api_version": "device-fingerprint.internal.v1",
  "request_id": "<canonical uuid>",
  "error": {
    "code": "invalid_request",
    "message": "The request is invalid."
  }
}
```

No:

```text
submitted payload echo
secret echo
raw exception
SQL text
filesystem secret path
```

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

# 52. Source Health Request Body

`POST /source-health/batch` exact root:

```json
{
  "producer_id": "sensor-zefer-01",
  "events": [
    {
      "source_health_event_id": "00000000-0000-4000-8000-000000000002",
      "site_id": "0123456789abcdef01234567",
      "capture_source_id": "zefer-span-01",
      "source_kind": "dhcp",
      "status": "available",
      "reason_code": null,
      "observed_at": "2026-09-14T10:00:00.000Z"
    }
  ]
}
```

Root exact keys:

```text
producer_id
events
```

Event exact keys:

```text
source_health_event_id
site_id
capture_source_id
source_kind
status
reason_code
observed_at
```

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

# 54. Source Health Idempotency

Producer creates:

```text
source_health_event_id
```

once before spool/delivery.

Central uniqueness:

```text
UNIQUE (
    producer_id,
    source_health_event_id
)
```

Central canonical source-health content:

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

Central service computes:

```text
content_sha256
```

over deterministic canonical JSON of the immutable submitted health content excluding central:

```text
source_health_id
ingested_at
```

Same retry key + same canonical content:

```text
200 duplicate NO-OP
```

Same retry key + different content:

```text
409
NO overwrite
```

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

# 69. Main Database Hard Ceiling

Frozen R4 contract:

```text
MAX_DB_BYTES =
1 GiB
default
```

Writer sets SQLite:

```text
PRAGMA max_page_count
```

consistent with configured:

```text
MAX_DB_BYTES
```

and actual page size.

This is the logical main DB ceiling.

WAL is separately bounded by:

```text
journal_size_limit =
64 MiB
```

If SQLite reports full/max-page condition:

```text
write batch =
503

runtime =
unavailable / storage_limit
```

Retention may still execute to free eligible data.

---

# 70. Retention Contract

TechLead-accepted / Owner-pending P1 normalized evidence retention:

```text
30 days
```

P2 raw/high-risk:

```text
0 durable
```

Source-health P0 V1 retention:

```text
30 days
```

All durable retention cutoffs use:

```text
observed_at
```

not `ingested_at`.

Owner approval of P1 30 days is still required.

---

# 71. Retention Cleanup Algorithm

Every:

```text
300 seconds
```

when service is running, maintenance may run.

Per pass, for each table:

```text
cutoff =
central_now - retention_days
```

Delete rows ordered by:

```text
observed_at
primary row id
```

in chunks of at most:

```text
500 rows
```

Maximum:

```text
20 chunks / table / pass
```

Maximum row deletions:

```text
10,000 evidence
+
10,000 source-health
per maintenance pass
```

Each delete chunk:

```text
one bounded transaction
```

Do not hold one giant cleanup transaction.

---

# 72. Retention Eligibility

Evidence:

```text
observed_at < cutoff
```

Source health:

```text
observed_at < cutoff
```

Strict less-than.

No `ingested_at` retention eligibility.

No source-kind-specific retention in schema v1.

---

# 73. Runtime State Machine — FIX-11

Configuration-disabled is NOT a served runtime state.

If:

```text
DEVICE_FINGERPRINT_EVIDENCE_ENABLED=false
```

the `run` command does not start.

Running process state set:

```text
initializing
ready
degraded
unavailable
stopping
```

No other runtime state in Task-01 V1.

---

# 74. Runtime State Transitions

Startup:

```text
process starts
→ initializing
```

After:

```text
config valid
artifact identity captured
writer lock owned
DB initialize + quick_check + schema validation PASS
Flask app constructed
TLS files readable
```

then:

```text
ready
```

Maintenance failure while repository remains healthy:

```text
ready
→ degraded
reason=retention_failed
```

Next successful retention pass:

```text
degraded(retention_failed)
→ ready
```

Repository integrity/storage health failure:

```text
ready/degraded
→ unavailable
reason=storage_unavailable
or
storage_corrupt
```

Hard DB ceiling/full:

```text
ready/degraded
→ unavailable
reason=storage_limit
```

Signal:

```text
any running state
→ stopping
```

---

# 75. Unavailable Recovery Semantics

```text
unavailable/storage_corrupt
=
latched until operator restart/recovery
```

```text
unavailable/storage_unavailable
=
latched until process restart
after underlying storage is restored
```

Task-01 does not implement automatic DB repair.

```text
unavailable/storage_limit
```

may still run retention cleanup.

If cleanup succeeds and storage returns below the hard guard:

```text
repository quick_check + schema validation
→ ready
```

No source/auth state is modified.

---

# 76. Runtime Health HTTP Status

`GET /health` is protected by Bearer + network ACL.

HTTP:

```text
200
for:
ready
degraded

503
for:
initializing
unavailable
stopping
```

Payload is bounded and contains:

```text
api_version
request_id
state
reason
artifact identity safe fields
db/schema version
retention_days
last_successful_retention_at
```

No secret/path details.

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

# 80. Concurrency Guard

Evidence and source-health POST share one:

```text
BoundedSemaphore(
    max_concurrent_ingest_requests
)
```

Health GET does not consume an ingest slot.

If no ingest slot:

```text
429
Retry-After: 1
```

No blocking wait.

---

# 81. HTTP Request Size

Flask app config:

```text
MAX_CONTENT_LENGTH =
max_http_request_bytes
```

Additionally reject inconsistent/oversized bodies fail-closed.

413 body is sanitized.

No body echo.

---

# 82. Batch Count

For both POST endpoints:

```text
1..MAX_EVENTS_PER_BATCH
```

events required.

Empty batch:

```text
400
```

Too many:

```text
413
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

# 89. Read Service — Task-01 Scope

Internal Python read service only.

No HTTP evidence-query endpoint.

Required methods conceptually:

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

latest_evidence_by_source(
    site_id,
    observed_mac,
    *,
    through_utc,
)

latest_source_health(
    site_id,
    capture_source_id,
    source_kind,
    *,
    through_utc,
)
```

Method names above are frozen R4 Task-01 contracts.

If TechLead10 requires a rename, that must be returned as an explicit FIX before FINAL.

No Device Card route.

---

# 90. Read Bounds

Evidence queries require:

```text
site_id
observed_mac
bounded time range
limit
```

Maximum read page:

```text
500 rows
```

Default:

```text
100
```

Maximum requested time range:

```text
configured retention_days
```

with the strict configuration bound:

```text
1..90 days
```

A read window cannot exceed the durable retention policy configured for that artifact.

No unbounded full table scan read API.

---

# 91. Read Cursor

Cursor is stable tuple:

```text
observed_at
evidence_id
```

for device evidence.

Source-health cursor:

```text
observed_at
source_health_id
```

Ordering:

```text
observed_at ASC
id ASC
```

No offset pagination.

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

# 102. CLI Lifecycle

Entry:

```text
python3 -m app.device_fingerprint.cli run
```

Order:

```text
1. parse command
2. load get_settings()
3. build strict DeviceFingerprintConfig
4. require enabled
5. configure dedicated logger
6. capture artifact identity
7. create runtime/service
8. acquire writer lock
9. initialize repository
10. build/freeze production schema registry
11. create dedicated Flask app
12. mark ready
13. run direct-TLS Flask/Werkzeug server
14. graceful shutdown/finally
15. release writer lock
```

No implicit migration command outside startup schema-v1 initialization.

---

# 103. Signal / Shutdown Contract

Install:

```text
SIGTERM
SIGINT
```

Handler:

```text
mark runtime stopping
request maintenance thread stop
cause HTTP run loop/process to unwind
```

Handler must not perform an unbounded join.

Finalization:

```text
stop accepting writes

maintenance thread bounded join
<= 20 seconds

close repository resources

release writer lock

best-effort stopped telemetry
```

No shutdown action touches Authorization.

---

# 104. Systemd Unit Shape

Future deployment unit is frozen in shape:

```text
fingerprint-evidence.service
```

Core directives:

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

OS:

```text
User
Group
```

and TLS/DB file permissions must be frozen by infrastructure before FINAL.

No systemd socket activation.

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

# 116. HTTP Health Authentication

`GET /health` requires:

```text
valid configured producer Bearer
+
allowed remote management network
```

No body producer_id.

Any valid configured producer credential may query service health in V1.

No unauthenticated health endpoint.

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

# 119. 409 Semantics

If any existing retry identity has different canonical immutable content:

```text
HTTP 409

error.code =
idempotency_conflict
```

Entire write transaction rolls back.

Response does NOT identify the conflicting MAC/payload.

May include only bounded:

```text
conflict_count
```

if desired.

No overwrite/update.

---

# 120. 503 Storage Guard

503 covers:

```text
repository unavailable

repository bounded busy

service state unavailable/stopping

hard database storage ceiling
```

Use sanitized code indicating category.

Producer may retry later according to Task-02 spool policy.

Task-01 does not define sensor retry cadence.

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

# 122. Privacy Retention Clock

For an evidence row:

```text
privacy expiry =
observed_at + retention_days
```

not:

```text
ingested_at + retention_days
```

For source health:

```text
expiry =
observed_at + source_health_retention_days
```

A late accepted event has less remaining durable life.

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

# 128. Task-01 Exact Application File Boundary — R4

## NEW

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

## MODIFY

```text
app/config.py

app/settings.py

.env.example
```

No other application/config file is authorized by this R4 candidate.

---

# 129. Explicit Application NO-TOUCH

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

Task-01 reuses their contracts but does not edit them.

If FINAL implementation objectively requires another application file:

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

# 131. Exact Test File Boundary — R4

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

# 138. Required HTTP Security Tests

Must prove:

```text
direct Flask app only

API prefix exact

query credential rejected

missing bearer 401

wrong bearer 401

constant-time verification path

disallowed network 403

body producer mismatch 403

Site mismatch 403

capture source mismatch 403

source kind mismatch 403

unknown schema 400

413 limits

429 nonblocking concurrency

503 unavailable/stopping/storage guard

no raw body in response/logging

no Forwarded/XFF trust
```

---

# 139. Required State Machine Tests

Must prove transitions:

```text
initializing → ready

ready → degraded(retention_failed)

degraded → ready

ready/degraded → unavailable(storage_limit)

storage_limit → ready after successful retention+health

ready/degraded → unavailable(storage_unavailable)

storage_unavailable latched

storage_corrupt latched

any → stopping
```

and HTTP acceptance per state.

---

# 140. Required Retention Tests

Must prove:

```text
cutoff uses observed_at

ingested_at does not extend retention

strict < cutoff

500 rows/chunk

20 chunks max/table/pass

both tables cleaned

no other DB touched

retention failure degradation
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

# 142. Exact Coder Narrow Test Commands — R4 FROZEN

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

These are entirely task-owned test modules, so file-level execution is narrow and exact.

Coder does NOT run the full repository suite.

Exact command grouping is frozen in R4; FINAL should carry it unchanged unless TechLead10 returns a FIX.

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

# 144. Operational Activation Order — FUTURE

After implementation and official acceptance:

```text
1. merge/deploy foundation artifact disabled

2. provision external systemd unit

3. provision endpoint/TLS/firewall/producer config

4. keep DEVICE_FINGERPRINT_EVIDENCE_ENABLED=false

5. controlled activation window

6. enable + start fingerprint-evidence.service

7. verify artifact identity

8. verify TLS/API health

9. verify DB schema/quick_check

10. verify production schema registry is empty

11. verify no packet producer is active

12. foundation PASS

13. only later Task-02
```

Task-01 activation does not activate packet collection.

---

# 145. Rollback

Rollback:

```text
stop/disable fingerprint-evidence.service

set enabled=false

rollback artifact if needed
```

No source DB restore.

No Authorization rollback.

New fingerprint DB remains isolated and may be preserved until explicit data disposition.

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

# 153. FINAL Blocking Matrix

```text
FIX-1 =
CLOSED

FIX-2 =
CLOSED ARCHITECTURALLY
Owner clock acceptance pending

FIX-3 =
CLOSED ARCHITECTURALLY
concrete endpoint infra pending

FIX-4 =
CLOSED

FIX-5 =
CLOSED

FIX-6 =
CLOSED

FIX-7 =
CLOSED ARCHITECTURALLY
direct-TLS endpoint values pending

FIX-8 =
CLOSED

FIX-9 =
CLOSED

FIX-10 =
CLOSED

FIX-11 =
CLOSED AS R4 CANDIDATE
TechLead10 source recheck pending
```

---

# 154. TechLead10 Recheck Checklist

Please recheck:

```text
A. Dedicated auxiliary Flask app
   is not registered in main app.

B. Direct TLS ownership removes
   XFF/proxy ambiguity.

C. Batch semantics are all-or-nothing.

D. HTTP status classes are complete.

E. Production schema registry is empty
   in Task-01.

F. Source-health is point-event only.

G. Exact schema/tables/columns/indexes
   are complete.

H. Limits are explicit and not Coder choices.

I. State machine is exact.

J. Config/env names and producers JSON
   are complete.

K. FIX-1…FIX-6 remain preserved.

L. Remaining OWNER/INFRA section
   contains only genuine external decisions.
```

Expected result:

```text
PASS
```

or narrow remaining:

```text
FIX-N
```

---

# 155. Final Candidate Status

```text
TASK =
TASK-DEVICE-FINGERPRINT-01-DRAFT-R4-FINAL-CANDIDATE

ARCHITECTURE DIRECTION =
ACCEPTED

RESEARCH =
CLOSED / DO NOT REOPEN

FIX-1…FIX-11 =
INCORPORATED

CURRENT GATE =
TECHLEAD10 FINAL CONTRADICTION / SOURCE RECHECK

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

# 156. Next Workflow

```text
TASK-DEVICE-FINGERPRINT-01-DRAFT-R4-FINAL-CANDIDATE
        ↓
TechLead10 final contradiction/source recheck
        ↓
PASS or narrow FIX
        ↓
Owner freezes:
30d retention
120s future skew
86400s delayed age
        ↓
Infra freezes:
bind/port
TLS cert/key paths
management CIDRs
systemd User/Group
firewall owner/rules
initial producer mapping
        ↓
Architect issues:
TASK-DEVICE-FINGERPRINT-01-FINAL
        ↓
FINAL recheck
        ↓
Owner explicit implementation authorization
        ↓
Coder
```

**End of DRAFT-R4-FINAL-CANDIDATE.**
