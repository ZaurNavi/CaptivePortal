# TECH LEAD REVIEW — TASK-DEVICE-FINGERPRINT-01-DRAFT-R2

**Role:** TechLead9  
**Review baseline:** `main@14ab4034dd9fe170b33795322c29c543bf6c2544`  
**Runtime parent:** `3dc85735ddf5d05dd20733d15dfe1c22c9c4fde5`  
**Research:** `DEVICE-FINGERPRINT-00 FINAL R2 = PASS`

## VERDICT

```text
TASK-DEVICE-FINGERPRINT-01-DRAFT-R2
=
FIX REQUIRED

ARCHITECTURE DIRECTION =
ACCEPTED

IMPLEMENTATION-READY =
NO

CODER =
HOLD

IMPLEMENTATION =
NOT AUTHORIZED
```

No new packet/source feasibility research is required.

The following architecture decisions are accepted without correction:

```text
separate Device Fingerprint Evidence domain

separate normalized evidence DB

separate central evidence writer/service

D — separate physical sensor for V1

packet capture outside Authorization process

Suricata as primary packet extractor

small exact DHCP parser

small exact TCP SYN parser

JA4 as evidence, not identity

JA3 rejected as primary fingerprint

TCP SYN = weak supporting

DNS/mDNS = optional

raw PCAP / DNS / SNI durable retention forbidden

SPAN dedup mandatory

cross-MAC merge forbidden

classifier deferred

Device Card deferred

multi-platform classifier gate deferred until labeled matrix

bounded receive-capacity proof != production parser sizing
```

Six corrections are required before FINAL.

---

# FIX-1 — Remove unsafe bare-MAC → device_id resolution from Task-01

The DRAFT currently permits conceptually:

```text
observed MAC
→ exact Registry identity
→ device_id
```

This is not safe against the current repository contract.

Current Visitor Registry identity is global by MAC:

```text
visitor_devices.mac = UNIQUE
```

and its public exact read is:

```text
get_device_by_mac(mac)
```

without `site_id`.

At the same time, the established Site-safe Admin contract explicitly says that Registry global MAC identity is not proof of Site membership. Site membership requires exact Site snapshot or Site Visit evidence.  

Therefore Task-01 must NOT turn:

```text
bare MAC
→ global Registry device
```

into:

```text
exact Site-qualified evidence_identity_link
```

### Required correction

For Task-01, freeze the durable acquisition identity as:

```text
site_id
+
observed_mac
+
observed_at
```

Task-01 evidence ingestion/storage/read must work without `device_id`.

Recommended simplification:

```text
evidence_identity_links
=
DEFER TO TASK-DEVICE-FINGERPRINT-05
```

Task-01 must not introduce a new Registry/Visit resolver worker merely to populate these links.

Future exact resolution may use only independently Site-proven relations, for example:

```text
site_id + MAC + exact Site snapshot
→ device_id

site_id + MAC + bounded Visit relation
→ visit_id
→ exact device_id when Visit already owns that link

auth_session_id + site_id + MAC
→ exact snapshot/auth relation

site_id + IP + observed_at
→ exact time-bounded IP→MAC proof
→ Site-qualified resolution
```

Current Visit read boundary is already Site-scoped and supports Site+MAC reads, so this future path is compatible with existing ownership. 

Permanent rules:

```text
bare Registry MAC match != Site proof

last_site_id != permanent membership proof

unresolved = valid state

no fuzzy nearest-device resolution

no cross-Site MAC inference

no cross-MAC fingerprint similarity resolution
```

This correction keeps Task-01 smaller and preserves the roadmap:

```text
Task-01 = evidence foundation
Task-04 = classification
Task-05 = exact Device Identity / Classification integration
```

---

# FIX-2 — Add producer clock / observation-time trust contract

The physical sensor is remote from the central evidence writer.

Yet:

```text
observed_at
```

will later participate in:

```text
retention
Visit correlation
IP→MAC correlation
auth/session correlation
classifier observation windows
```

Therefore producer time cannot simply be trusted.

### Required correction

All evidence timestamps must use the existing project canonical UTC form:

```text
YYYY-MM-DDTHH:MM:SS.mmmZ
```

The project already uses fixed-width millisecond UTC contracts. 

Freeze:

```text
observed_at =
producer observation timestamp

ingested_at =
central evidence service timestamp

producer clock =
must be time-synchronized

future exact identity resolution =
must not trust observation time outside approved skew bounds
```

Task-01 FINAL must define bounded configuration for:

```text
maximum future clock skew
maximum acceptable delayed-event age
```

Exact values are Owner/Tech Lead configuration decisions before implementation authorization; they are not Coder decisions.

Out-of-contract timestamps must:

```text
fail validation
OR
be explicitly degraded according to a frozen contract
```

They must never silently participate in exact identity correlation.

Retention age must use:

```text
observed_at
```

rather than resetting privacy lifetime from late `ingested_at`.

---

# FIX-3 — Freeze V1 ingest security and service/config pattern

Do not leave:

```text
PSK maybe
mTLS maybe
equivalent maybe
```

to implementation.

For V1 accept:

```text
HTTPS
+
per-producer Bearer credential
+
management-network CIDR allowlist
+
producer authorization
```

Each configured producer must be bound to:

```text
producer_id
allowed capture_source_id
allowed site_id
allowed source_kinds
```

Credential requirements:

```text
generated outside Git
rotatable
never query-string supplied
never logged
constant-time comparison
minimum strong secret policy
```

The existing Analytics internal API already provides the project precedent for Bearer auth, source-network allowlisting, Site allowlisting, bounded requests and query-string credential rejection.

Use the project's existing internal namespace shape:

```text
POST /api/internal/device-fingerprint/v1/evidence/batch
GET  /api/internal/device-fingerprint/v1/health
```

instead of:

```text
/internal/device-fingerprint/v1/...
```

### Configuration authority

Use the existing pipeline only:

```text
app/config.py
→ app/settings.py
→ strict DeviceFingerprintConfig
```

with new fingerprint-specific configuration.

Do NOT reuse:

```text
OBSERVATION_SITE_IDS
CURRENT_STATE_SITE_IDS
```

as hidden packet-source authority.

Task-01 FINAL should define a strict trusted mapping concept such as:

```text
capture_source_id
→ site_id
→ allowed guest CIDRs
→ allowed source kinds
→ optional expected VLAN scope
```

Central Task-01 configuration should not own a Windows/Linux interface name. This belongs to Task-02 sensor configuration:

```text
capture_interface
SPAN/interface mechanics
Npcap/libpcap details
```

### Service lifecycle

Reuse the already accepted separate-worker pattern:

```text
python3 -m app.device_fingerprint.cli run
systemd
EnvironmentFile=/etc/default/captive-portal
WorkingDirectory=/opt/CaptivePortal
bounded SIGTERM/SIGINT shutdown
immutable startup artifact identity
```

Traffic Projection already establishes this separate CLI/service precedent, including startup artifact identity.  

Exact bind address/port/TLS termination still requires infrastructure rebind before implementation-ready FINAL. It must be frozen by Owner + Tech Lead, not chosen by Coder.

---

# FIX-4 — Freeze idempotency and payload-hash semantics

The DRAFT correctly separates:

```text
SPAN dedup
```

from:

```text
transport retry idempotency
```

but the retry conflict case is currently undefined.

Required contract:

```text
producer creates source_event_id ONCE
before local spool/delivery

retry reuses exactly the same source_event_id
```

Central uniqueness:

```text
UNIQUE(producer_id, source_event_id)
```

Central service, not the producer, owns the canonical durable payload hash.

Required ingest semantics:

```text
first valid event
→ validate
→ canonicalize
→ server computes payload_sha256
→ store

same producer_id + source_event_id
+ same canonical content
→ IDEMPOTENT SUCCESS / NO-OP

same producer_id + source_event_id
+ different canonical content
→ CONFLICT / REJECT
→ telemetry
→ NEVER overwrite existing evidence
```

Canonical JSON must have one deterministic representation:

```text
UTF-8
stable key ordering
no NaN/Infinity
no insignificant whitespace
exact schema-approved field set
```

`payload_sha256` means:

```text
SHA-256 of canonical normalized payload
```

not arbitrary producer bytes.

This is required to preserve the DRAFT's immutable evidence invariant.

---

# FIX-5 — Freeze canonical field/storage contract before Coder

The FINAL must eliminate remaining primitive-format decisions.

Required canonical forms:

```text
site_id =
24 lowercase hex,
no silent case conversion,
no Site-name substitution

observed_mac =
AA:BB:CC:DD:EE:FF
using shared app.common.mac contract

observed_ip =
canonical ipaddress representation

observed_at / ingested_at =
fixed UTC milliseconds

payload_json =
canonical schema-versioned JSON
```

The existing MAC helper already provides the shared canonical uppercase-colon representation. 

Task-01 schema must have at minimum the indexes implied by its own read/retention contracts:

```text
UNIQUE (
    producer_id,
    source_event_id
)

INDEX (
    site_id,
    observed_mac,
    observed_at,
    evidence_id
)

INDEX (
    site_id,
    source_kind,
    observed_at,
    evidence_id
)

RETENTION INDEX (
    observed_at,
    evidence_id
)
```

No destination IP belongs in the common durable envelope.

Also correct privacy classification:

```text
observed_mac = P1 / MODERATE

observed_ip = P1 / MODERATE
```

They are necessary correlation facts, but they are not P0 operational metadata.

Tech Lead accepts the current retention direction:

```text
P2 raw/high-risk = 0 durable

P1 normalized evidence = 30 days default
```

subject to Owner approval before FINAL.

Repository implementation should reuse existing SQLite safety principles:

```text
single writer
deterministic schema
PRAGMA user_version
startup quick_check
strict schema validation
path/file safety
bounded busy timeout
read-only/query-only consumers
```

rather than inventing a new persistence style. The repository already contains this pattern in current SQLite domains. 

---

# FIX-6 — Do not encode source unavailability as fake per-device evidence

The common envelope currently contains:

```text
quality_state
availability_state
```

while the same DRAFT correctly establishes:

```text
missing / unavailable / unsupported
!=
negative evidence
```

An accepted fingerprint evidence row must mean:

```text
a normalized observation actually occurred
```

Therefore source outage must not manufacture per-device rows such as:

```text
source_kind=quic_client
availability_state=unavailable
```

for a device.

### Required correction

Keep event-level:

```text
quality_state
=
valid | partial | degraded
```

for evidence that actually exists.

Move:

```text
available
unavailable
unsupported
```

to the separate source-health model keyed by appropriate operational scope:

```text
site_id
capture_source_id
source_kind
timestamp/health interval
```

Source health may tell the future classifier:

```text
"QUIC evidence was unavailable"
```

but that is not:

```text
"this device does not support QUIC"
```

No synthetic negative device evidence.

This also keeps:

```text
source-health telemetry
```

separate from:

```text
device fingerprint evidence
```

which is consistent with the DRAFT's own failure/health architecture.

---

# FINAL REQUIRED ARCHITECTURE STATE AFTER FIXES

After applying FIX-1…FIX-6, I expect the next revision to freeze:

```text
TASK-01 evidence identity =
site_id + observed_mac + observed_at

Task-01 durable device_id link =
NO

future exact identity integration =
TASK-05

packet sensor =
D / separate physical sensor

central evidence process =
separate auxiliary service

storage =
separate SQLite / central writer only

transport =
HTTPS + per-producer Bearer + management ACL

API namespace =
/api/internal/device-fingerprint/v1

packet dedup =
Task-02 / mandatory

transport retry idempotency =
Task-01 / mandatory

raw P2 retention =
0

normalized P1 retention =
30d proposed

clock trust =
explicit bounded contract

source outages =
health state, not fake device evidence

Authorization dependency =
FORBIDDEN
```

## TECH LEAD STATUS

```text
ARCHITECTURE DIRECTION = ACCEPTED

DRAFT-R2 = FIX REQUIRED

RESEARCH = CLOSED
NO REOPEN

NEW LIVE RESEARCH = NOT REQUIRED

CODER = HOLD

IMPLEMENTATION = NOT AUTHORIZED

NEXT =
Architect incorporates FIX-1…FIX-6
→ returns TASK-DEVICE-FINGERPRINT-01-DRAFT-R3 / FINAL CANDIDATE
→ Tech Lead source recheck
→ PASS or narrow remaining FIX
```