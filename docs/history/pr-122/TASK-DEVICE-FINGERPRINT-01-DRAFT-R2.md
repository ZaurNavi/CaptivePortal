# TASK-DEVICE-FINGERPRINT-01-DRAFT-R2

## Passive Mobile / Personal Device Fingerprint Evidence Foundation

**Project:** CaptivPortal  
**Program:** Passive Mobile / Personal Device Fingerprinting  
**Research predecessor:** `DEVICE-FINGERPRINT-00`  
**Task:** `TASK-DEVICE-FINGERPRINT-01-DRAFT-R2`  
**Parent task:** `TASK-DEVICE-FINGERPRINT-01`  
**Type:** Architecture / foundation design  
**Status:** `DRAFT — FOR OWNER + TECH LEAD REVIEW`  
**Implementation-ready:** `NO`  
**Implementation authorization:** `NOT GRANTED`  
**Coder:** `HOLD`  
**Branch / commit / push / PR / deploy:** `NOT AUTHORIZED`  
**Prepared:** 2026-09-14

---

# 0. Control Status

```text
DEVICE-FINGERPRINT-00 = CLOSED / RESEARCH PASS
TASK-DEVICE-FINGERPRINT-01-DRAFT-R2 = DRAFT — FOR OWNER + TECH LEAD REVIEW
CODER = HOLD
IMPLEMENTATION = NOT AUTHORIZED
PRODUCTION COLLECTION = NOT AUTHORIZED
DB / SCHEMA CHANGE = NOT AUTHORIZED
CLASSIFIER IMPLEMENTATION = NOT AUTHORIZED
DEVICE CARD CHANGE = NOT AUTHORIZED
```

This DRAFT is an architecture proposal only. It does not authorize a packet sensor, evidence database, new service, classifier, Admin UI change, production SPAN change, or any other implementation.

## R2 research disposition

```text
RESEARCH HANDOFF =
DEVICE-FINGERPRINT-00 FINAL R2

R2 STATUS =
ACCEPTED AS SUPERSEDING RESEARCH INPUT

ARCHITECTURE DRAFT =
UPDATED / NO NEW FEASIBILITY RESEARCH REQUIRED
```

R2 corrections frozen into this revision:

```text
TCP SYN =
PHASE-1 WEAK SUPPORTING

V1 packet sensor placement =
D — SEPARATE PHYSICAL SENSOR

existing host/VM packet sensor =
NOT PROVEN

portal Accept / Accept-Language =
NOT PROVEN IN RETAINED RESEARCH

TCP DF / IPv4-ID / ECN =
NOT PROVEN

production Suricata CPU/RAM/EVE rate =
NOT TESTED

long-duration sensor soak =
NOT TESTED

multi-platform packet ground truth =
ANDROID ONLY
```

These are implementation/acceptance limits, not blockers to architecture drafting.

---

# 1. Repository / Research Baselines

## 1.1 Current repository `main`

```text
HEAD = 14ab4034dd9fe170b33795322c29c543bf6c2544
TREE = f328a665ef08a76c7f14a36a1a2e45d47c230468
```

Current `main` is the documentation/KB-sync merge on top of the runtime parent used by the feasibility research.

## 1.2 Runtime/code parent used by research

```text
HEAD = 3dc85735ddf5d05dd20733d15dfe1c22c9c4fde5
TREE = 8312658be3ba272998f46212d9bad76950e3867e
```

Therefore:

```text
RESEARCH CODE DRIFT = NO MATERIAL RUNTIME DRIFT IDENTIFIED
CURRENT MAIN DRIFT = DOCUMENTATION / KB MERGE
```

Tech Lead must fresh-rebind `main` before any future implementation-ready FINAL.

---

# 2. Research Gate Result

`DEVICE-FINGERPRINT-00 FINAL R2` closes the original blockers and supersedes the first research handoff.

Live bounded evidence proved:

```text
pre-NAT client IPv4 visibility
original client MAC visibility
DHCP visibility
TCP SYN visibility
TLS ClientHello visibility
QUIC / HTTP3 visibility
DNS visibility
mDNS visibility
portal User-Agent / low-entropy Client Hints
IPv6 link-local behavior
bounded current sensor capacity
```

Primary parser feasibility:

```text
Suricata 8.x = PASS
```

Known parser gaps:

```text
exact DHCP PRL / option order → small packet-level parser required
exact TCP SYN fingerprint vector → small packet-level parser required
exact QUIC transport parameters/order → optional dedicated parser only if later justified
```

Research also proved approximately 50% SPAN duplication in bounded captures. Deduplication is therefore a hard architecture requirement.

---

# 3. Product Goal

The Phase-1 product question is intentionally narrow:

> Is this most likely a smartphone, tablet, or laptop; what OS family, vendor and possible model family are supported by evidence; and how certain are we?

Primary Phase-1 target classes:

```text
smartphone
tablet
laptop
unknown
```

Primary future OS families:

```text
Android
iOS / iPadOS
Windows
macOS
Linux
unknown
```

Phase 2 General / IoT classification is future work.

---

# 4. Architectural Placement

Current CaptivPortal remains conceptually:

```text
Authorization / Identity
        ↓
Snapshots / Webhook evidence
        ↓
Registry + Visit Lifecycle
        ↓
Observation + Current State
        ↓
Analytics
        ↓
Admin Web
```

Passive Device Fingerprinting is NOT inserted into Authorization.

Proposed parallel evidence path:

```text
                  Existing CaptivPortal facts
        Registry / Visit / Observation / Current State
                         │
                         │ read-only later
                         ▼
Passive Network ──► Fingerprint Evidence ◄── Portal Header Evidence
                         │
                         ▼
                 Future Classifier
                         │
                         ▼
              Derived Classification
                    ┌────┴────┐
                    ▼         ▼
                 Admin     Analytics
```

Hard invariant:

```text
Fingerprint failure MUST NOT become an Authorization failure.
```

---

# 5. Domain Ownership Decision

Create a new logical domain:

```text
Device Fingerprint Evidence
```

Proposed namespace:

```text
app/device_fingerprint/
```

Ownership:

```text
Visitor Registry
→ device_id / MAC identity / device history

Observation
→ historical Omada/controller observations

Current State
→ current wireless state

Visit Lifecycle
→ visit/session chronology

Device Fingerprint Evidence
→ NEW normalized passive evidence

Future Classifier
→ derived classification

Analytics/Admin
→ downstream consumers
```

Fingerprinting does not create a second Device Registry and does not duplicate Omada collection.

---

# 6. Four Semantic Layers — Non-Negotiable

```text
1. RAW ACQUISITION OBSERVATION
2. NORMALIZED EVIDENCE
3. DERIVED CLASSIFICATION
4. GROUND TRUTH
```

Example:

```text
RAW:
DHCP packet / ClientHello / portal request

NORMALIZED EVIDENCE:
DHCP PRL vector
JA4 component/family
portal platform=Android
TCP SYN vector

CLASSIFICATION:
device_class=smartphone
os_family=Android
confidence=high

GROUND TRUTH:
Owner-controlled Nokia G21 / Android
```

These concepts must never collapse into one field/table/authority.

---

# 7. Task-01 Scope

`TASK-DEVICE-FINGERPRINT-01` is the **Evidence Foundation**, not the classifier.

Future implementation scope:

```text
domain models
normalized evidence envelope
evidence persistence
idempotent ingest boundary
read boundary
retention/privacy enforcement
source/capture scope identity
source health/availability semantics
delivery retry/idempotency contract
operational telemetry
foundation test harness
```

Task-01 does NOT implement production:

```text
Suricata packet sensor
DHCP parser
TCP SYN parser
TLS/QUIC adapter
Portal UA adapter
classification weights
Device Card fields
```

---

# 8. Staged Program

```text
DEVICE-FINGERPRINT-00
Source Feasibility / Privacy / Sensor Research
= CLOSED / PASS

DEVICE-FINGERPRINT-01
Passive Evidence Foundation
= THIS DRAFT

DEVICE-FINGERPRINT-02
Core Packet Sensor + Network Evidence
DHCP + TCP SYN + TLS JA4 + QUIC JA4

DEVICE-FINGERPRINT-03
Portal/Application Evidence
UA + low-entropy Client Hints

DEVICE-FINGERPRINT-03A
Multi-Platform Labeled Evidence Matrix

DEVICE-FINGERPRINT-04
Mobile / Personal Classification Engine

DEVICE-FINGERPRINT-05
Device Identity / Classification Read Integration

DEVICE-FINGERPRINT-06
Device Card / Admin Integration
```

Optional later:

```text
DEVICE-FINGERPRINT-OPT-DNS
DEVICE-FINGERPRINT-OPT-MDNS
```

Future domains:

```text
DEVICE-FINGERPRINT-IOT-01
DEVICE-FINGERPRINT-ACTIVE-01
```

---

# 9. Process Topology Decision

Research requires a separate packet-capture failure domain.

Architect recommendation:

```text
AUXILIARY MULTI-PROCESS TOPOLOGY = ACCEPT
```

Conceptual target:

```text
Catalyst SPAN / passive feed
        ↓
fingerprint-sensor.service
        ↓
normalized evidence transport
        ↓
fingerprint-evidence.service
        ↓
device_fingerprint_evidence.sqlite3
```

Later:

```text
Captive Portal request path
        ↓ best-effort non-blocking emission
portal evidence adapter
        ↓
same evidence ingest boundary
```

The existing authorization process remains the critical core and does not become dependent on either auxiliary service.

---

# 10. Why Auxiliary Processes Are Justified

Fingerprinting is an intentional auxiliary exception to the project's primarily single-process runtime because:

```text
packet capture needs elevated/network privileges
Suricata/parser crashes must not crash authorization
capture workload has independent CPU/RAM behavior
remote/dedicated sensor placement is plausible
raw packet visibility must remain isolated
```

A future implementation-ready FINAL must include the corresponding ADR/documentation update.

---

# 11. Component Model

```text
A. Packet Sensor
B. Packet Evidence Adapter
C. Portal Evidence Adapter
D. Evidence Ingest Boundary
E. Evidence Repository
F. Evidence Read Service
G. Retention / Maintenance
H. Operational Telemetry
I. Future Classifier
```

Task-01 primarily owns D–H and freezes the contracts A–C must consume later.

---

# 12. Packet Sensor Boundary

Future Packet Sensor responsibility:

```text
receive passive mirrored traffic
run Suricata
run bounded custom header parsers
perform packet/SPAN dedup before semantic counts
drop raw/high-risk fields not permitted downstream
produce normalized evidence events
buffer only normalized evidence for delivery
```

It must NOT:

```text
authorize clients
query Omada
write CaptivPortal source DBs
classify canonical device truth
merge identities
retain long PCAP
```

---

# 13. Production Sensor Placement — R2 FROZEN DIRECTION


R2 changes the placement recommendation from generic “dedicated endpoint” to an explicit V1 architecture baseline:

```text
PRODUCTION PACKET SENSOR PLACEMENT =
D — SEPARATE PHYSICAL SENSOR
```

Reason:

```text
this is the only packet-capture placement
proven live in DEVICE-FINGERPRINT-00

original MAC/IP visibility was proven

pre-NAT protocol visibility was proven

packet privileges/resource spikes are isolated
from captive authorization
```

The V1 architecture therefore assumes:

```text
Catalyst trusted passive mirror/feed
        ↓
separate physical sensor
        ↓
authenticated normalized-evidence transport
        ↓
central evidence service
```

Still NOT frozen at this DRAFT stage:

```text
exact physical model
final OS
final NIC
SPAN wiring/configuration
service packaging
production parser sizing
```

Option C:

```text
separate sensor process/VM on an existing host
```

may only replace the physical-sensor baseline after an explicit future proof of:

```text
capture-interface delivery
original L2 visibility
capacity
privilege isolation
failure isolation
```

Current research does NOT prove:

```text
CaptivPortal VM as packet sensor

existing hypervisor NIC as packet sensor

router-side general packet sensor
```

Rejected:

```text
packet capture inside Flask/auth request process
```

---

# 14. Capture Scope Contract

Every production capture source requires trusted configuration:

```text
capture_source_id
site_id
capture_interface
allowed guest IPv4 CIDRs
allowed IPv6 prefixes if applicable
expected VLAN IDs if tags are available
capture mode
```

Current research path mixed VLANs and did not preserve tags.

A sensor must not infer Site from a missing VLAN tag.

If packet scope cannot be proven:

```text
NO fingerprint evidence record
```

If overlapping Site address spaces share an untagged mirror:

```text
UNSUPPORTED until capture scope becomes unambiguous.
```

---

# 15. Central Evidence Service

Architect recommendation:

```text
fingerprint-evidence.service
```

Responsibilities:

```text
validate normalized evidence envelope
authenticate producer
enforce source/capture scope
idempotent ingest
persist evidence
retention cleanup
read-only health metadata
operational telemetry
```

It does not parse raw packets.

---

# 16. No Remote SQLite

Forbidden:

```text
remote sensor opening evidence SQLite
SMB/NFS SQLite writes
shared DB file from sensor
sensor importing repository and writing over network filesystem
```

Transport terminates at the evidence service.

---

# 17. Evidence Transport Contract

Architecture requires:

```text
authenticated
bounded
versioned
machine-readable
idempotent
management-network only
```

Preferred direction:

```text
HTTPS JSON batch ingest
```

Remote producers must never connect directly to storage.

Exact transport security mechanism is a Tech Lead finalization item.

---

# 18. Ingest Authentication

DRAFT preference:

```text
HTTPS
+
producer identity
+
rotatable pre-shared ingest credential
+
management-network ACL
```

mTLS may replace PSK if infrastructure review prefers it.

Hard invariants:

```text
NO anonymous ingest
NO guest-network-accessible ingest endpoint
```

---

# 19. Delivery Semantics

Packet Sensor:

```text
AT LEAST ONCE
+
bounded normalized-evidence spool
```

Central repository:

```text
IDEMPOTENT
```

Portal evidence later uses best-effort bounded delivery and must never block auth.

---

# 20. Raw Packet Retention

```text
GENERAL RAW PCAP RETENTION = FORBIDDEN
```

Raw bytes may exist only in transient capture/parser buffers or an explicitly Owner-authorized diagnostic window.

They are not normal product persistence.

---

# 21. Suricata EVE Privacy Boundary

Full EVE events must NOT automatically become durable evidence.

Examples of fields rejected from normal durable evidence:

```text
raw SNI
DNS rrname
arbitrary mDNS names
packet payload
full request headers
cookies/tokens
```

Adapters must project only approved normalized fields.

---

# 22. Evidence Repository Decision

Task-01 should introduce separate persistence:

```text
device_fingerprint_evidence.sqlite3
```

Reason:

```text
new source family
different privacy/retention policy
different writer/process lifecycle
remote producer ingest
must not mutate Registry/Observation schemas
independently disableable/rebuildable
```

---

# 23. Evidence DB Ownership

Single writer:

```text
fingerprint-evidence.service
```

Read-only consumers later:

```text
classifier
Admin composition
Analytics
engineering tools
```

Forbidden writers:

```text
Admin Web
Analytics
Visitor Registry
Observation
Current State
Portal request handler
Packet sensor direct DB access
```

---

# 24. Evidence Schema — DRAFT Source Envelope + Resolvable Identity Links


The normalized source-evidence record should represent acquisition facts and provenance.

Proposed immutable source envelope:

```text
evidence_id

producer_id
source_event_id

source_kind
source_subtype

extractor_name
extractor_version
feature_schema_version
rule_version when applicable

site_id
capture_source_id

observed_at

observed_mac
observed_ip

privacy_class
quality_state
availability_state

payload_json
payload_sha256

ingested_at
```

R2 additionally requires the architecture to be able to represent exact-resolved links to existing identity/lifecycle owners:

```text
device_id
visit_id
auth_session_id
```

Those links are NOT source facts and are NOT owned by the packet producer.

Architectural separation:

```text
IMMUTABLE EVIDENCE
=
what was observed + provenance

EXACT IDENTITY/LIFECYCLE LINK
=
derived relation to Registry / Visit / Auth owner
```

Recommended representation is a separate derived binding layer, conceptually:

```text
evidence_identity_links

evidence_id
device_id when exact-resolved
visit_id when exact-resolved
auth_session_id when exact-resolved
resolution_kind
resolved_at
resolver_version
```

This keeps the source evidence immutable while allowing:

```text
late exact resolution

re-resolution if ownership data becomes available later

auditable relation to observed MAC/IP/time
```

This is architecture input only, not schema authorization.

---

# 25. Evidence / Retry Identity

Repository-owned:

```text
evidence_id
```

Producer supplies:

```text
producer_id
source_event_id
```

Central uniqueness:

```text
UNIQUE(producer_id, source_event_id)
```

This protects delivery retries.

It is NOT packet/SPAN dedup.

---

# 26. Two Dedup Problems

## A. Mirror / packet duplication

Owner:

```text
Packet Sensor / source adapter
```

Must happen before evidence counts.

## B. Transport retry duplication

Owner:

```text
Evidence Repository
```

Uses producer event identity.

Do not conflate them.

---

# 27. SPAN Dedup Contract

Research observed ~50% duplicates.

Future sensor must provide:

```text
deterministic
bounded-memory
protocol-safe dedup

raw packet count
duplicate packet count
deduplicated count
dedup ratio
```

It must not collapse:

```text
legitimate retransmissions
separate application events
```

Exact algorithm is a Task-02 finalization item, not Task-01.

---

# 28. Source Kind Registry

Core reserved kinds:

```text
dhcp
tcp_syn
tls_client
quic_client
portal_client
```

Optional later Phase-1:

```text
dns_ecosystem
mdns_service
ipv6_stack
```

Future Phase-2 can add kinds without redefining old schemas.

---

# 29. Source-Specific Versioning

Every record carries:

```text
source_kind
feature_schema_version
extractor_name
extractor_version
```

Classifier later consumes a versioned source contract, not arbitrary unversioned JSON.

---

# 30. Payload Schema Rule

Each:

```text
(source_kind, feature_schema_version)
```

owns an exact allowlisted payload schema.

No unrestricted JSON.

Reasons:

```text
privacy
stable classifier input
bounded storage
versioned semantics
```

---

# 31. DRAFT DHCP Payload

Future normalized DHCP evidence may include:

```text
message_family
vendor_class
client_identifier_kind
parameter_request_list
client_option_order
maximum_message_size
rapid_commit_requested
capport_requested
ipv6_only_preferred_requested
hostname_present
```

Not:

```text
raw DHCP packet
```

Source evidence such as:

```text
vendor_class="android-dhcp-13"
```

must remain source evidence.

```text
os_family="Android"
```

belongs only to future classification.

---

# 32. DRAFT TCP SYN Payload — ONLY PROVEN CORE VECTOR


R2 requires the initial TCP evidence schema to distinguish proven fields from unmeasured candidates.

Proven controlled Android SYN vector fields:

```text
ip_version
observed_ttl
tcp_window
mss
window_scale
sack_permitted
timestamps_present
tcp_option_order
```

These are valid candidates for the first TCP feature schema.

Research did NOT retain/prove enough evidence to freeze these into V1 payload semantics yet:

```text
df_behavior
ipv4_id_behavior_class
ecn_flags
```

Therefore they are:

```text
DEFERRED OPTIONAL FIELDS
```

until Task-02 explicitly proves them.

No payload bytes.

No p0f OS label as canonical source truth.

TCP SYN is supporting evidence, not OS authority.

---

# 33. DRAFT TLS / QUIC Payload

Preferred durable shape:

```text
protocol_family
JA4
stable JA4 components where useful
TLS version capability
ALPN family when safely visible
ECH extension observed boolean
GREASE behavior summary
ClientHello feature schema version
```

Raw SNI:

```text
NOT DURABLE
```

---

# 34. JA4 Semantics

Research proved JA4 materially more stable than JA3, but one physical device still produced multiple legitimate JA4 variants.

Therefore:

```text
JA4 = EVIDENCE
JA4 != DEVICE IDENTITY
JA4 != ABSOLUTE OS TRUTH
```

Future classifier may use full JA4, components or observed family distribution, but cannot merge identities based on JA4 similarity.

---

# 35. Explicit JA3 Decision

Research found:

```text
TLS:
18 ClientHello
18 unique JA3

QUIC:
28 reconstructed ClientHello
28 unique JA3
```

Therefore:

```text
JA3 PRIMARY FINGERPRINT = REJECT
```

JA3 is not needed as a Phase-1 primary classifier input.

---

# 36. Portal Evidence Boundary — R2 PROVEN FIELDS


The controlled live research proved naturally supplied passive fields:

```text
User-Agent
Sec-CH-UA
Sec-CH-UA-Mobile
Sec-CH-UA-Platform
```

These form the Phase-1 Portal core evidence candidates.

R2 explicitly records that the retained research excerpt did NOT prove:

```text
Accept
Accept-Language
```

Therefore Task-03 must not rely on either field until a bounded implementation/lab proof confirms actual availability/value.

High-entropy Client Hints remain outside passive core:

```text
Sec-CH-UA-Model
platform version
architecture
bitness
```

No Phase-1 default:

```text
Accept-CH expansion
JavaScript getHighEntropyValues()
canvas/audio fingerprinting
```

Important semantic boundary:

```text
Nokia G21 / Android 13
was observed in a WebView User-Agent,
NOT as proof of Sec-CH-UA-Model.
```

---

# 37. Portal Failure Isolation

Any future portal evidence emission must be:

```text
best-effort
bounded
non-blocking
```

If evidence submission is unavailable:

```text
portal request continues
authorization continues
```

Forbidden:

```text
synchronous remote retry in auth/request path
auth failure because fingerprint submit failed
```

Preferred later pattern:

```text
request extracts allowed normalized facts
        ↓
non-blocking bounded local handoff
        ↓
background adapter
        ↓
evidence ingest
```

---

# 38. Portal Durable Payload

Raw UA is variable and privacy-relevant.

Preferred normalized durable fields later:

```text
platform_family
mobile_boolean
browser_runtime_family
webview_boolean
captive_context_hint
os_major_hint if explicitly present and approved
model_hint if explicitly present and approved
parser_version
```

Normal durable raw UA retention:

```text
NO
```

---

# 39. DNS Policy

DNS is not Phase-1 core.

If activated later:

```text
raw DNS FQDN
→ transient rule evaluation only

normalized ecosystem/capability evidence
→ may persist

raw name
→ discarded
```

No durable browsing history.

No classifier dependency on complete DNS visibility.

---

# 40. mDNS / LLMNR Policy

mDNS is optional supporting evidence.

Durable candidate:

```text
mdns_present=true
service_family=googlecast
```

Not:

```text
arbitrary raw service/device name
```

LLMNR remains optional and cannot become a Phase-1 dependency until it is observed/validated on appropriate labeled devices.

---

# 41. IPv6 Policy

Collector architecture must be IPv6-capable.

Current routed/global guest IPv6:

```text
NOT AVAILABLE
```

Therefore classifier Phase-1 must not require global IPv6.

Link-local behavior may be supporting evidence.

---

# 42. Existing Facts Reuse

Future classifier reads existing domains instead of copying facts into fingerprint storage.

Existing facts may include:

```text
raw device_type
device_type_key
hostname
name
MAC
IP
SSID
AP
band
radio/channel
RSSI/SNR
current auth state
Visit/session chronology
traffic/activity context
```

No second Omada collector.

---

# 43. Device Type Foundation Relationship

Current production semantics:

```text
device_type
=
raw/source evidence

device_type_key
=
lexical derived key
```

Fingerprint classification must not overwrite either.

Example:

```text
device_type="unknown"
device_type_key="unknown"

future:
device_class="smartphone"
os_family="Android"
classification_state="high_confidence"
```

All may coexist.

---

# 44. Identity Binding — Primary Rule

At collection time the primary evidence binding is:

```text
site_id
+
observed_mac
+
observed_at
```

when MAC is available.

Visitor Registry remains `device_id` owner.

Evidence repository does NOT create device identity.

---

# 45. Exact Identity Resolution — SOURCE IMMUTABLE, LINKS DERIVED


R2 requires the architecture to support exact links to:

```text
device_id
visit_id
auth_session_id
```

when they can be proven.

Ownership remains:

```text
device_id
→ Visitor Registry

visit_id
→ Visit Lifecycle

auth_session_id
→ Auth/session owner
```

Task-01 evidence source rows do NOT create those identities.

Primary source binding remains:

```text
site_id
+
observed_mac
+
observed_at
```

Recommended resolution architecture:

```text
immutable evidence
        ↓
read-only exact resolver
        ↓
derived evidence_identity_link
```

Allowed resolution:

```text
observed MAC
→ exact Registry identity
→ device_id

site + IP + observed_at
→ exact valid time-bounded mapping
→ MAC
→ device_id

exact lifecycle/auth correlation
→ visit_id/auth_session_id
```

If exact resolution is unavailable:

```text
link remains absent
```

No fuzzy fallback.

This satisfies both requirements:

```text
source evidence remains immutable/auditable

exact-resolved identity links can exist durably
without making fingerprinting the identity owner
```

Cross-MAC similarity is never a resolver.

---

# 46. IP-Only Evidence

If future evidence lacks MAC:

```text
IP + observed_at + site
```

may only be resolved through an exact time-bounded resolver.

Rejected:

```text
IP-only long-term identity
nearest-device fuzzy match
cross-site private-IP assumptions
```

Until exact resolution exists:

```text
IP-only evidence may remain unresolved
or be excluded from device classification.
```

---

# 47. Private MAC Rule

Research ground-truth Android used a locally administered MAC.

Hard invariants:

```text
private/random MAC does not force unknown
if other evidence is strong

fingerprint similarity MUST NOT merge
two MAC/device identities
```

Cross-MAC continuity is a separate future architecture.

---

# 48. Evidence Query Identity

Task-01 internal read contract should primarily support:

```text
site_id + observed_mac + time window

site_id + source_kind + time window
```

Future Device Card/classifier first obtains MAC through Registry.

No inferred person identity.

---

# 49. Persistence Strategy

Architect recommendation:

```text
ONE append-oriented normalized evidence DB
```

with common envelope + versioned source payload.

Reasons:

```text
heterogeneous sources
future Phase-2 extensibility
immutable source evidence
classification remains downstream
```

Do not create one DB per protocol.

---

# 50. Evidence Mutability

Accepted evidence rows are immutable.

Allowed:

```text
retention deletion
```

Not allowed:

```text
rewrite evidence when classifier changes
replace source payload with classification
silently change extractor version
```

If corrected source evidence must be represented later:

```text
new versioned evidence event
```

with explicit provenance.

---

# 51. Classification Persistence

NOT Task-01.

Task-01 evidence DB must not include source-row fields such as:

```text
device_class
os_family
vendor
model_hint
confidence
classification_state
```

Those belong to future classifier ownership.

---

# 52. Privacy Classes

DRAFT:

```text
P0 = low/bounded operational evidence
P1 = moderate fingerprint evidence
P2 = high/privacy-sensitive transient material
```

Examples:

```text
P0:
source availability
private-MAC boolean
extractor version

P1:
DHCP PRL
TCP SYN vector
JA4
normalized portal platform/runtime/model hint
normalized mDNS family

P2:
raw DNS names
raw SNI
raw UA
raw mDNS names
raw packet bytes
```

---

# 53. Retention Proposal

Architect proposes for review:

```text
P2 raw/high-risk =
0 durable retention

P1 normalized fingerprint evidence =
30 days default

P0 operational/source-health evidence =
30 days default
or existing telemetry retention
```

Rationale:

```text
enough history for repeated evidence and classifier validation

bounded privacy/storage

long-term product history can later persist derived classification
without keeping destination-level raw material
```

Owner/Tech Lead may adjust before FINAL.

---

# 54. Diagnostic Raw Capture Exception

Any diagnostic PCAP retention requires:

```text
explicit Owner authorization
named bounded test window
bounded size/duration
controlled storage
documented deletion
```

Not normal service behavior.

---

# 55. Retention Enforcement

Evidence writer owns cleanup.

Cleanup is based on approved evidence privacy/source class.

Cleanup failure:

```text
may degrade fingerprint service
MUST NOT affect Authorization
```

If storage reaches a hard safety ceiling:

```text
prefer stop accepting new fingerprint evidence
over unbounded disk growth
```

---

# 56. Ingest Validation

Central ingest rejects:

```text
unknown producer
unknown capture source
unsupported feature schema
invalid Site
invalid MAC syntax where required
invalid timestamp
oversized batch/payload
unapproved payload fields
high-risk raw fields
malformed JSON
```

Rejected ingest cannot mutate any existing source DB.

---

# 57. Payload Allowlist

Every:

```text
(source_kind, feature_schema_version)
```

has an exact payload field/type allowlist.

No arbitrary JSON.

A payload schema change requires an explicit version change/review.

---

# 58. High-Risk Field Denylist

Defense-in-depth denylist includes ordinary:

```text
raw packet payload
raw SNI
raw DNS rrname
raw arbitrary mDNS names
HTTP cookies
Authorization headers
portal credentials/tokens
full request headers
```

Even if a producer sends them, central ingest rejects the event.

---

# 59. Evidence Quality vs Classification Confidence

Evidence source state is not classifier confidence.

DRAFT source record concepts:

```text
quality_state:
valid
partial
degraded

availability_state:
available
unavailable
unsupported
```

Exact enum names can be refined before FINAL.

Do not write `high_confidence` into evidence source rows.

---

# 60. Source Health Model

One health boolean is insufficient.

Operational health must distinguish:

```text
sensor process alive
capture packets arriving
parser events arriving
evidence accepted
delivery backlog
capture drops
dedup ratio
```

---

# 61. Sensor Telemetry

Future minimum:

```text
raw_packets_total
raw_bytes_total
capture_drop_count
duplicate_packet_count
deduplicated_packet_count
dedup_ratio
events_by_source_kind
events_rejected_privacy
normalized_spool_depth
normalized_spool_bytes
delivery_success
delivery_failure
parser_version
sensor_artifact_identity
capture_source_id
```

No raw destination identifiers in telemetry.

---

# 62. Evidence Service Telemetry

Future minimum:

```text
ingest_received
ingest_accepted
ingest_duplicate
ingest_rejected
records_by_source_kind
db_health
db_bytes
retention_deleted
retention_failure
producer_last_seen
capture_source_last_seen
source_schema_versions
service_artifact_identity
```

---

# 63. Health Integration

Fingerprint health may later be surfaced by Admin/Home System Health, but not in Task-01 UI.

Permanent semantic:

```text
Fingerprint unavailable
!=
CaptivPortal unavailable
```

Existing source Device Card facts remain usable.

---

# 64. Failure Isolation Matrix

Required:

```text
sensor DOWN → Authorization works
Suricata DOWN → Authorization works
custom parser DOWN → Authorization works
transport DOWN → Authorization works
evidence service DOWN → Authorization works
evidence DB unavailable → Authorization works
classifier DOWN → Authorization works
Admin fingerprint panel DOWN → source Device Card remains usable
```

---

# 65. Portal Adapter Failure Isolation

Future portal emitter must never:

```text
block auth while waiting for evidence service
retry synchronously in request path
fail HTTP auth flow because evidence delivery failed
```

If bounded local handoff is full:

```text
drop fingerprint evidence
emit bounded operational counter
continue portal flow
```

---

# 66. Phase-1 Source Priority — R2 FORMAL RANKING


## PHASE-1 CORE / REUSE

```text
existing CaptivPortal/Omada facts
```

## PHASE-1 CORE — NEW EVIDENCE

```text
DHCP exact vector

Portal UA / proven low-entropy Client Hints

TLS JA4

QUIC JA4 where present
```

## PHASE-1 WEAK SUPPORTING

```text
TCP SYN normalized stack vector

hostname when present

private/local-admin MAC qualifier

global OUI only when MAC is globally administered

IPv4 stack behavior already proven in approved TCP vector

IPv6 link-local behavior when present

existing Visit/connection behavior via existing domains
```

Important R2 correction:

```text
TCP SYN
IS NOT
"CORE-SUPPORTING"
```

It is intentionally:

```text
PHASE-1 WEAK SUPPORTING
```

despite a stable 64/64 vector in the bounded Android sample, because network path/kernel/tunnel behavior can change the signal.

## PHASE-1 OPTIONAL

```text
DNS normalized ecosystem/capability

mDNS service family

exact QUIC transport parameters
```

## DEFER

```text
LLMNR
routed/global IPv6 behavior
high-entropy Client Hints
```

## REJECT / NOT PRIMARY

```text
JA3 exact fingerprint as primary

raw DNS/SNI history

continuous PCAP

p0f as canonical authority
```

---

# 67. QUIC Transport Parameters

Exact QUIC transport parameter values/order:

```text
OPTIONAL / NOT TASK-01
```

Suricata already provides useful QUIC/JA4 evidence.

Do not build a custom QUIC TP parser unless later labeled classifier experiments prove useful incremental value.

---

# 68. DNS Decision

Architect recommendation:

```text
DNS EVIDENCE = DEFERRED OPTIONAL
```

Reasons:

```text
privacy cost high
DoH makes coverage incomplete
destinations represent apps/user activity more than device truth
```

Classifier must not depend on DNS.

---

# 69. mDNS Decision

```text
mDNS SERVICE FAMILY = OPTIONAL / SUPPORTING
```

Only normalized family may persist.

Phase-1 core can ship without mDNS.

---

# 70. LLMNR Decision

```text
OPTIONAL
NOT OBSERVED ON ANDROID RESEARCH
NOT CORE
```

Validate later on labeled Windows devices if desired.

---

# 71. Ground-Truth Boundary — R2 EXPLICIT LIMIT


Packet-level controlled ground truth in the research is exactly:

```text
Nokia G21
Android
```

No other platform is accepted as labeled packet-level ground truth from DEVICE-FINGERPRINT-00.

Formal R2 status:

```text
Android = PASS / controlled

iOS/iPadOS = NOT TESTED

Windows packet-level ground truth = NOT TESTED

macOS = NOT TESTED

Linux = NOT TESTED
```

Incidental portal/network observations from other devices do not become labeled truth.

Before classifier production trust, Owner-controlled labeled matrices are required across available platforms.

Architecture drafting is NOT blocked by this limitation.

Classifier accuracy claims ARE blocked by it.

---

# 72. Classifier Task Gate

`TASK-DEVICE-FINGERPRINT-04` must not become implementation-ready until:

```text
core evidence adapters exist
+
multi-platform labeled matrix exists
```

Unavailable platforms remain:

```text
NOT TESTED
```

---

# 73. Future Classification Contract — Concept Only

Candidate later output:

```text
device_class
form_factor
os_family
vendor
model_hint
classification_state
confidence_score
evidence_sources
classifier_version
classified_at
```

Task-01 implements none of this.

---

# 74. Classification State Direction

Conceptual future states:

```text
unknown
weak
probable
high_confidence
conflicting
```

Exact thresholds and numeric confidence are deliberately not frozen before multi-platform evidence exists.

---

# 75. Conflict Semantics

Future classifier must support contradictions explicitly.

Example:

```text
hostname → iPhone-like
DHCP → Windows-like
TCP → Windows-like
Portal UA → Windows
```

Required direction:

```text
conflict detected
→ lower confidence
→ conflicting/probable/unknown
```

Forbidden:

```text
one source silently wins without versioned policy
```

---

# 76. Progressive Classification

Evidence may accumulate:

```text
private MAC
→ unknown

+ DHCP
→ probable

+ portal
→ stronger

+ JA4 / TCP
→ stronger
```

Scheduling/recalculation belongs to Task-04.

---

# 77. Reclassification

Normalized evidence should support classifier rule changes within retention window.

```text
new classifier version
→ re-read normalized evidence
→ recalculate
```

Old raw packet features that were never retained cannot be recreated. Their historical source schema remains what it was.

---

# 78. Internal Evidence Read Boundary

Task-01 should expose an internal read service only.

Candidate queries:

```text
list Site+MAC evidence by time range
latest evidence per source kind
source availability summary
bounded counts
```

No public/browser evidence API in Task-01.

---

# 79. Read Query Bounds

Every read must be bounded by:

```text
Site
MAC or source kind
time range
limit/cursor
```

No unbounded evidence dump.

---

# 80. Analytics Boundary

Fingerprint Evidence is not Analytics.

Evidence answers:

```text
what passive evidence was observed?
```

Classifier later answers:

```text
what derived device classification follows?
```

Analytics may later aggregate derived outputs but never owns extraction.

---

# 81. Admin Boundary

Device Card later consumes bounded derived classification.

Task-01 does not expose packet-level evidence to browser/Admin.

Potential future presentation:

```text
Device class
OS family
Vendor
Model hint
Confidence
bounded "why" explanation
```

---

# 82. Phase-2 Compatibility

Generic evidence envelope must permit new future source kinds without changing current evidence meaning.

But Task-01 must not pre-create IoT classifier semantics.

Future:

```text
SSDP
UPnP
DLNA
WS-Discovery
NBNS
HomeKit
printer/camera/NAS/media discovery
```

remain Phase 2.

---

# 83. Active Fingerprinting Boundary

Explicitly outside Phase 1:

```text
port scan
banner grab
SNMP client query
HTTP device probe
active OS scan
crafted TCP/TLS/QUIC probe
```

Any active task requires separate architecture and Owner approval.

---

# 84. Feature Flags

Future implementation should be disabled by default.

Proposed gates:

```text
FINGERPRINT_EVIDENCE_ENABLED

FINGERPRINT_SENSOR_ENABLED
```

Later source gates:

```text
FINGERPRINT_DHCP_ENABLED
FINGERPRINT_TCP_SYN_ENABLED
FINGERPRINT_TLS_ENABLED
FINGERPRINT_QUIC_ENABLED
FINGERPRINT_PORTAL_ENABLED
FINGERPRINT_DNS_ENABLED
FINGERPRINT_MDNS_ENABLED
```

Production activation is separate from merge/deploy.

---

# 85. Why Feature Gates Are Appropriate

This foundation introduces:

```text
new service
new persistence
new data collection
new privacy surface
```

Unlike the lexical Device Type foundation, a disabled-by-default controlled rollout is appropriate.

---

# 86. Evidence Repository Availability State

Candidate state family:

```text
disabled
initializing
ready
degraded
unavailable
```

Exact state machine belongs to implementation-ready FINAL.

No state may affect guest authorization.

---

# 87. Storage Safety Guard

Future config should include:

```text
retention_days
max_db_bytes
max_ingest_batch_records
max_payload_bytes
max_normalized_spool_bytes
```

No unlimited disk consumption.

If DB reaches hard safety ceiling:

```text
stop accepting new fingerprint evidence
emit degraded/unavailable health
preserve CaptivPortal core
```

---

# 88. Sensor Normalized Spool

Allowed:

```text
bounded normalized evidence events
```

Not allowed:

```text
long raw PCAP spool
raw DNS backlog
raw SNI backlog
```

Future Task-02 freezes:

```text
maximum age
maximum bytes
overflow policy
retry cadence
```

---

# 89. Backpressure

Evidence ingest must enforce:

```text
bounded request bytes
bounded batch size
bounded processing time
```

Overload returns explicit retryable failure to remote sensor.

Portal request path does not synchronously retry.

---

# 90. Artifact Identity

Future services should use project artifact identity principles:

```text
fingerprint-evidence.service
fingerprint-sensor.service
```

Where a service executes from the mutable CaptivPortal artifact, startup-captured immutable artifact identity is mandatory.

---

# 91. Deployment Lifecycle

A future implementation must add artifact-owned long-running services to the authoritative deployment manifest.

No mutable checkout update while an artifact-owned fingerprint process from that checkout is alive.

Sensor may eventually use separately packaged immutable deployment; that belongs to Task-02 deployment review.

---

# 92. Security Boundary

Packet capture privileges are isolated.

Sensor must have:

```text
least required capture capability
no Omada credentials
no Portal auth credentials
no Registry write credentials
no source DB write access
only evidence-ingest credential
```

Central ingest credential cannot authorize guests.

---

# 93. Producer Authorization

Each producer is configured with:

```text
producer_id
allowed capture_source_id
allowed site_id
allowed source kinds
```

A producer cannot submit arbitrary Site/source combinations.

---

# 94. Site Isolation

Evidence ingest and reads are Site-scoped.

Forbidden:

```text
Site-A producer → Site-B evidence

Site-A Admin/classifier → Site-B evidence

cross-site identity merging
```

---

# 95. Data Minimization

If a field is not required by approved classification input:

```text
DO NOT PERSIST IT
```

Parser capability does not justify persistence.

---

# 96. Missing Evidence Semantics

Permanent project invariant applies:

```text
missing / unavailable / unsupported
!=
negative evidence
```

Examples:

```text
no QUIC
!= no QUIC support

no portal UA
!= not Android

no DHCP hostname
!= embedded

no mDNS
!= not Apple/Google
```

Future classifier must preserve this distinction.

---

# 97. Evidence Staleness

Every evidence event persists:

```text
observed_at
```

Source-specific freshness/staleness horizons belong to classifier policy, not Task-01 storage.

Task-01 does not mark old evidence as false.

---

# 98. Evidence Count Semantics

Evidence counts mean:

```text
accepted deduplicated logical source events
```

not:

```text
raw mirrored packet copies
```

Packet source adapters guarantee semantic dedup before ingest. Central idempotency handles delivery retries only.

---

# 99. Ground Truth Storage

Owner-controlled ground truth belongs to:

```text
lab fixtures / acceptance dataset
```

not normal production visitor evidence.

Never assign unverified ground-truth OS/model labels to visitors.

---

# 100. Proposed Task-01 Module Layout — DRAFT

Conceptual:

```text
app/device_fingerprint/
    __init__.py
    config.py
    models.py
    schema.py
    repository.py
    service.py
    read_service.py
    ingest.py
    telemetry.py
    cli.py
```

This is not yet a Coder file boundary.

Tech Lead must rebind naming/patterns before FINAL.

---

# 101. Proposed Persistence Path — DRAFT

Candidate:

```text
/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3
```

Repository default:

```text
disabled
```

No existing DB is modified.

---

# 102. Proposed Central Unit — DRAFT

Candidate:

```text
fingerprint-evidence.service
```

Owns:

```text
DB initialize/migrate
authenticated ingest
retention
health
graceful shutdown
```

It does not own packet capture.

---

# 103. Proposed Sensor Unit — FUTURE TASK-02

Candidate:

```text
fingerprint-sensor.service
```

Owns:

```text
capture
Suricata lifecycle/integration
DHCP/TCP custom extraction
packet dedup
privacy projection
normalized spool
delivery
```

No sensor implementation is authorized in Task-01.

---

# 104. Internal Ingest API — DRAFT

Candidate endpoint family:

```text
POST /internal/device-fingerprint/v1/evidence/batch
GET  /internal/device-fingerprint/v1/health
```

Exact framework/path is not frozen.

No public captive portal route.

No anonymous endpoint.

---

# 105. No Public Browser API

Task-01 does not create a browser-facing fingerprint endpoint.

Future classifier/Admin integration gets a separate read contract.

---

# 106. Task-01 Future Test Architecture

Implementation-ready FINAL should include narrow tests for:

```text
schema initialization

disabled mode

ingest envelope validation

producer/site authorization

payload allowlists

privacy denylist

idempotent retry

Site/MAC read bounds

retention cleanup

max DB/payload guards

DB unavailable behavior

source schema versioning

telemetry safe fields

service failure isolation

no existing source DB mutation
```

---

# 107. Sensor Acceptance — Future Task-02

Official acceptance must compare normalized output to bounded packet-oracle captures.

Required:

```text
DHCP exact PRL match

DHCP exact option order match

TCP SYN vector match

TLS JA4 match

QUIC JA4 match

raw packet count
dedup count
dedup ratio

forbidden raw SNI/DNS fields absent
```

---

# 108. Dedup Acceptance — Future Task-02

Fixture must contain:

```text
mirror duplicate packet copies
legitimate retransmission
separate same-flow logical events
```

Required:

```text
mirror duplicates collapse

legitimate retransmission/event
does NOT collapse incorrectly
```

Production sensor activation is forbidden until this gate passes.

---

# 109. Privacy Acceptance

Static + runtime DB/log proof must demonstrate:

```text
no raw packet bytes
no raw SNI
no raw DNS rrname
no cookie/auth header
no full raw UA
no arbitrary local-discovery names
```

---

# 110. Failure Isolation Acceptance

Owner + Tech Lead must prove:

```text
stop fingerprint-evidence.service
→ Auth PASS

stop fingerprint-sensor.service
→ Auth PASS

make evidence DB unavailable
→ Auth PASS

fill normalized sensor spool
→ Auth PASS

future classifier unavailable
→ Auth PASS
```

---

# 111. Existing Database Integrity Gate

Fingerprint feature must not mutate:

```text
visitor_registry.sqlite3
observations.sqlite3
current_state.sqlite3
visits.sqlite3
traffic_projection.sqlite3
```

Official acceptance captures schema/signature/count evidence before/after.

---

# 112. Capacity Acceptance — R2 MEASURED VS UNMEASURED


Research proved bounded receive/capture feasibility:

```text
~22–30 kpps raw mirrored traffic

~160–200 Mbit/s raw mirrored L2 traffic

~50% duplication

0 observed capture-interface drops
```

Research did NOT measure:

```text
production Suricata CPU

production Suricata RAM

sustained EVE event output rate

DHCP events/day population estimate

TLS/QUIC events/day production estimate

DNS events/day estimate

long-duration peak/soak capacity
```

Therefore:

```text
CURRENT SENSOR RECEIVE FEASIBILITY = PASS BOUNDED

PRODUCTION PARSER SIZING = NOT TESTED

LONG-DURATION SOAK = NOT TESTED
```

Before Task-02 production activation, Gate A must prove:

```text
selected physical sensor host

selected production Suricata mode

CPU/RAM under representative load

sustained output rate

capture/parser drops

dedup cost

normalized event rate

spool growth/recovery

longer bounded soak
```

No architecture or implementation document may convert the bounded receive proof into an unlimited capacity claim.

---

# 113. Classification Acceptance — Future Task-04

Before broad production trust, labeled devices as available:

```text
Android
iOS/iPadOS
Windows
macOS
Linux
```

Metrics should include:

```text
coverage
precision for high-confidence claims
conflict rate
unknown rate
false-high-confidence rate
```

Exact thresholds are deferred until multi-platform evidence exists.

---

# 114. Unknown Is Correct

Product invariant:

```text
honest unknown
>
false confident classification
```

Do not optimize solely for low unknown percentage.

---

# 115. Classification Provenance — Future

Future classification must answer:

```text
why did we classify this?
```

Minimum provenance:

```text
classifier_version
evidence source kinds used
evidence time window
conflict state
```

No opaque unversioned final label.

---

# 116. No Source Override

Future classification does not rewrite:

```text
Omada device_type
device_type_key
hostname
Registry snapshots
Observation facts
Current State facts
```

Derived classification remains separate.

---

# 117. Device Card Future Fields — NOT TASK-01

Potential later fields:

```text
device_class
form_factor
os_family
vendor
model_hint
classification_state
confidence
classified_at
```

No Device Card change until Task-06.

---

# 118. Future Analytics — NOT TASK-01

Potential later metrics:

```text
device-class distribution
OS-family distribution
unknown/conflicting share
source coverage
confidence distribution
```

Analytics only consumes read models.

---

# 119. Phase-2 Compatibility

Foundation envelope is generic enough for future source kinds, but Task-01 does not implement IoT semantics.

No premature classes:

```text
smart_tv
printer
camera
NAS
speaker
IoT
```

---

# 120. Active Fingerprinting Future Domain

Separate future task:

```text
DEVICE-FINGERPRINT-ACTIVE-01
```

Passive foundation must contain no hidden active-probe hooks.

---

# 121. Open Architecture Question A — Ingest Security

Before implementation-ready FINAL, Tech Lead should recommend one exact transport/security model:

```text
HTTPS + PSK/token + management ACL
or
mTLS
or
equivalent authenticated management-plane transport
```

Hard invariant:

```text
no anonymous remote ingest
```

No additional live packet research is required.

---

# 122. Open Architecture Question B — Central Service Binding

Tech Lead should determine:

```text
management bind address
port
TLS termination
firewall/ACL owner
credential distribution/rotation
```

No public Internet exposure.

---

# 123. Open Architecture Question C — Normalized Retention

Architect proposal:

```text
P1 normalized evidence = 30 days
P2 raw/high-risk = 0 durable
```

Owner/Tech Lead should accept or adjust before FINAL.

---

# 124. Open Architecture Question D — Exact Schema Envelope

Tech Lead should review:

```text
common columns
source_event uniqueness
payload_json canonicalization
index requirements
user_version/schema version
retention indexes
```

No schema implementation until FINAL.

---

# 125. Open Architecture Question E — Site Configuration Authority

Tech Lead must decide how trusted:

```text
capture_source_id
site_id
guest CIDRs
optional VLAN IDs
```

are represented using current configuration patterns.

No Site inference from packet contents.

---

# 126. Open Architecture Question F — Service Composition Pattern

Tech Lead must rebind current patterns for:

```text
separate Python CLI service
systemd lifecycle
artifact identity
logging/telemetry
shutdown
config/env
SQLite writer lock/ownership
```

Task-01 FINAL should reuse current accepted patterns rather than invent a second service framework.

---

# 127. Open Architecture Question G — Optional DNS/mDNS

Architect recommendation:

```text
not enabled in core initial launch
```

Owner may approve later optional tasks after core classifier demonstrates value.

---

# 128. Open Architecture Question H — Exact Packet Dedup Algorithm

This belongs to Task-02.

A narrow fixture/spike may be necessary before Task-02 FINAL.

It does not block Task-01 foundation.

---

# 129. Open Architecture Question I — Physical Sensor Implementation Details


R2 closes the placement family for V1 architecture:

```text
D — SEPARATE PHYSICAL SENSOR
```

remains the baseline.

Task-02 still must choose and prove exact:

```text
hardware
OS
capture NIC
switch/SPAN wiring
Suricata package/runtime
custom parser runtime
service manager
local normalized spool
management-network path
```

A VM/existing-host sensor is not an equal unproven option in this DRAFT.

It may only replace D after explicit Owner/Tech Lead-approved capture/interface/resource proof.

---

# 130. Explicit Task-01 Non-Goals

Task-01 does NOT:

```text
install Suricata

configure production SPAN

capture production packets

parse DHCP

parse TCP SYN

parse TLS/QUIC

collect DNS/mDNS

collect Portal UA/CH

classify devices

merge MAC identities

modify Registry schema

modify Observation schema

modify Current State schema

modify Visit schema

modify Traffic

modify Device Card

modify Admin UI

implement IoT classification

implement active fingerprinting
```

---

# 131. Privacy Non-Goals

No:

```text
person identity
cross-MAC tracking
behavioral surveillance
browsing history
destination history
session content inspection
TLS decryption
MITM
credential collection
```

---

# 132. Source Data Non-Goals

Do not durably retain just because parsers provide it:

```text
full EVE
full HTTP headers
raw ClientHello
raw DNS names
raw SNI
raw packet payload
raw multicast names
```

Only approved normalized evidence persists.

---

# 133. Rollout Model — Future

```text
merge disabled Evidence Foundation
        ↓
deploy
        ↓
foundation DB/service smoke with no producers
        ↓
Task-02 sensor implementation
        ↓
lab feed
        ↓
bounded passive production feed
        ↓
Task-03 portal evidence
        ↓
multi-platform labeled validation
        ↓
Task-04 classifier
```

Merge/deploy never automatically means production collection is enabled.

---

# 134. Rollback Model

Task-01 rollback:

```text
stop/disable fingerprint-evidence.service
rollback artifact
```

No effect on existing core domains.

Evidence DB may remain dormant until explicit data disposition.

No source DB rollback.

---

# 135. Architecture Invariants Summary

```text
PASSIVE PHASE 1 = YES

SEPARATE DOMAIN = YES

VISITOR REGISTRY EXTENSION = NO

OBSERVATION EXTENSION = NO

ANALYTICS SOURCE OWNER = NO

AUTH DEPENDENCY = FORBIDDEN

RAW SOURCE FACTS = PRESERVED

NORMALIZED EVIDENCE = SEPARATE

CLASSIFICATION = SEPARATE

GROUND TRUTH = LAB-ONLY / SEPARATE

NEW PERSISTENCE = YES / PROPOSED

REMOTE SQLITE = FORBIDDEN

SENSOR FAILURE DOMAIN = SEPARATE

CENTRAL EVIDENCE WRITER = SEPARATE AUXILIARY SERVICE

SURICATA = PRIMARY FUTURE EXTRACTOR

CUSTOM CORE PARSERS = DHCP + TCP SYN

JA3 = NOT PRIMARY

JA4 = CORE EVIDENCE, NOT IDENTITY

DNS = OPTIONAL / PRIVACY-SENSITIVE

mDNS = OPTIONAL

GLOBAL IPv6 = NOT REQUIRED

SPAN DEDUP = MANDATORY

CROSS-MAC MERGE = FORBIDDEN

GENERAL PCAP RETENTION = FORBIDDEN

RAW DNS/SNI DURABLE = FORBIDDEN

FEATURES DEFAULT = DISABLED

CODER = HOLD
```

---

# 136. Tech Lead Rebind Required Before FINAL

Repository/source review:

```text
current config/settings patterns

current separate-service CLI/systemd patterns

SQLite schema/repository lifecycle

artifact identity lifecycle

mutable-checkout service inventory

internal management API/security patterns

telemetry/logging conventions

Visitor Registry exact MAC/device read boundary

current Site configuration authority

health-state conventions

test-gate conventions
```

Infrastructure review:

```text
management-network ingest reachability
TLS/credential mechanism
candidate evidence service bind/port
```

No Coder design decision may remain in FINAL.

---

# 137. Research-to-Architecture Traceability

```text
RESEARCH:
pre-NAT MAC/IP visible

ARCHITECTURE:
Site+MAC primary evidence binding
```

```text
RESEARCH:
SPAN duplication ≈50%

ARCHITECTURE:
packet-level dedup mandatory
```

```text
RESEARCH:
Suricata parses DHCP/TLS/QUIC/DNS/mDNS

ARCHITECTURE:
Suricata primary extractor
```

```text
RESEARCH:
exact DHCP PRL/order absent in EVE

ARCHITECTURE:
small DHCP parser
```

```text
RESEARCH:
full TCP SYN vector absent in EVE

ARCHITECTURE:
small SYN parser
```

```text
RESEARCH:
JA3 unstable / JA4 materially more stable

ARCHITECTURE:
JA4 core evidence
JA3 not primary
```

```text
RESEARCH:
one physical device emits context-dependent UA

ARCHITECTURE:
normalized multi-observation Portal evidence
```

```text
RESEARCH:
DNS/SNI expose destination history

ARCHITECTURE:
no raw durable destination data
```

```text
RESEARCH:
private MAC is real current behavior

ARCHITECTURE:
OUI weak
cross-MAC merge forbidden
```

```text
RESEARCH:
global routed IPv6 unavailable

ARCHITECTURE:
IPv6 supported but not Phase-1 dependency
```

---

# 138. Proposed Owner / Tech Lead Review Questions — R2


Please review specifically:

```text
1. Separate Device Fingerprint Evidence domain.

2. Auxiliary fingerprint-evidence.service
   as separate writer/failure domain.

3. Separate device_fingerprint_evidence.sqlite3.

4. D — separate physical sensor
   as V1 packet-capture baseline.

5. Site+MAC+observed_at
   as primary acquisition binding.

6. Immutable source evidence
   + separate exact identity/lifecycle link layer.

7. Common envelope
   + versioned source payload schemas.

8. 30-day normalized evidence retention proposal.

9. High-risk raw retention = zero.

10. Authenticated management-plane ingest direction.

11. TCP SYN = Phase-1 weak supporting,
    not core authority.

12. DNS/mDNS deferred optional.

13. Classifier blocked on multi-platform labeled matrix.

14. Production parser CPU/RAM/event-rate/soak
    as mandatory Task-02 acceptance,
    not research-proven capacity.

15. Future roadmap decomposition.
```

Return:

```text
PASS
```

or:

```text
FIX-1 / FIX-N
with exact architectural correction.
```

---

# 139. R2 Formal Untested Items Carried Forward

The following are intentionally NOT promoted to proven architecture facts:

```text
multi-platform packet ground truth beyond Android

Accept / Accept-Language retained portal proof

high-entropy Client Hints

TCP DF behavior

IPv4 ID behavior

TCP ECN classification

independent AP/switch middlebox A/B comparison

DoH behavior

routed/global guest IPv6

Windows LLMNR

Apple Bonjour/AirPlay labeled proof

Suricata production CPU/RAM

sustained EVE output rate

population/day event estimates

long-duration soak capacity

existing server/VM packet-capture viability
```

Routing of these unknowns:

```text
Task-02 sensor acceptance:
TCP optional vectors
Suricata resource sizing
EVE rate
soak
dedup
physical host proof

Task-03 portal acceptance:
Accept / Accept-Language only if desired
high-entropy hints remain deferred

Task-03A labeled matrix:
iOS/iPadOS
Windows
macOS
Linux
Apple/Windows local-discovery behavior

optional DNS task:
DoH behavior

future IPv6 work:
routed/global IPv6
```

None of these reopens `DEVICE-FINGERPRINT-00`.

They are explicit later validation gates.

---

# 140. DRAFT Status

```text
TASK =
TASK-DEVICE-FINGERPRINT-01-DRAFT-R2

TITLE =
Passive Mobile / Personal Device Fingerprint Evidence Foundation

RESEARCH =
PASS

ARCHITECTURE DIRECTION =
READY FOR REVIEW

IMPLEMENTATION-READY =
NO

CODER =
HOLD

IMPLEMENTATION AUTHORIZATION =
NOT GRANTED

PRODUCTION SENSOR =
NOT AUTHORIZED

PRODUCTION COLLECTION =
NOT AUTHORIZED

NEW DB =
NOT AUTHORIZED

NEW SERVICE =
NOT AUTHORIZED

CLASSIFIER =
NOT AUTHORIZED

DEVICE CARD =
NOT AUTHORIZED
```

---

# 141. Next Workflow

```text
DEVICE-FINGERPRINT-00
RESEARCH PASS
        ↓
TASK-DEVICE-FINGERPRINT-01-DRAFT-R2
        ↓
Owner + Tech Lead architecture review
        ↓
FIXes if required
        ↓
Tech Lead PASS
        ↓
TASK-DEVICE-FINGERPRINT-01-FINAL
Evidence Foundation only
        ↓
Owner implementation authorization
        ↓
Coder
        ↓
Owner + Tech Lead acceptance
        ↓
DEVICE-FINGERPRINT-02
Core Packet Sensor + Network Evidence
```

**End of DRAFT.**
