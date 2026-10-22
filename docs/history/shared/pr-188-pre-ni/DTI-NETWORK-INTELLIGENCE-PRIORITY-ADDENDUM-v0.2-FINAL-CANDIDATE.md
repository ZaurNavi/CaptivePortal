# DTI — NETWORK INTELLIGENCE PRIORITY ADDENDUM v0.2
## FINAL CANDIDATE — Revised Product Milestone & Execution Roadmap

**Project:** CaptivPortal  
**Program:** Device Traffic Enrichment / Device Intelligence (DTI)  
**Artifact type:** Focused Architecture Addendum / Revised Execution Roadmap  
**Status:** `FINAL CANDIDATE FOR TECH LEAD REVIEW`  
**Base architecture:** `DEVICE-TRAFFIC-ENRICHMENT-ARCHITECTURE-v0.3_FINAL_TECHLEAD_ACCEPTED.md`  
**Architecture rewrite:** NO  
**Roadmap reprioritization:** YES  
**TL-NI-R1..TL-NI-R15:** INCORPORATED  
**Coder:** HOLD  
**Sysadmin:** HOLD  
**Production:** NO CHANGE  
**Periodic Traffic Meter lane:** PARKED  

---

# 1. DISPOSITION

The DTI program remains valid.

The implementation priority is changed from:

```text
traffic-first
```

to:

```text
NETWORK INTELLIGENCE FIRST
```

The former product path:

```text
DTI-03 periodic traffic accounting
→ DTI-04 traffic summaries
→ DTI-05 SPAN Traffic Device Card MVP
```

is:

```text
PARKED
```

All evidence from DTI-00 / DTI-00A / DTI-00B remains retained.

No periodic-meter redesign, optimization round, Coder rework, Sysadmin retest, or production change is authorized by this addendum.

The active product objective is:

```text
Tell the operator NEW things
about how a Device uses the network.
```

---

# 2. FROZEN NON-DUPLICATION PRINCIPLE

The active Network Intelligence lane MUST NOT rebuild product facts already owned elsewhere.

Existing facts, not new DTI goals:

```text
MAC
IP
SSID
AP
Presence / Online
Authorization
Radio / RSSI / SNR
Controller device type/platform where available
existing Current Guest Traffic
first seen
last seen
Visits
existing Device Fingerprint identity
```

These may be consumed only as:

```text
correlation input
context
composition input
```

They MUST NOT become:

```text
alternate DTI semantic owners
new DTI product claims
duplicated collectors/read models merely for Network Intelligence
```

Permanent:

```text
EXISTING FACT
→ EXISTING SEMANTIC OWNER
```

Network Intelligence adds only new network-observed semantic dimensions.

---

# 3. PARKED TRAFFIC LANE

The following remain PARKED:

```text
lightweight periodic packet meter
5-second packet traffic accounting
DTI-03 periodic traffic accounting
DTI-04 Visit / Device Traffic Summaries
DTI-05 SPAN Traffic Device Card MVP
```

Also parked:

```text
current SPAN traffic rate
periodic packet/byte buckets
SPAN upload/download totals
SPAN Visit totals
SPAN Today / 7-day totals
SPAN peak-rate metrics
```

Existing CaptivPortal / Omada traffic products remain untouched.

The parked lane MUST NOT block metadata-derived:

```text
Protocol Intelligence
Service Recognition
Infrastructure / Organization context
safe Transport Health subsets
```

Any future metric that truly requires periodic packet accounting remains parked until that lane is separately reopened.

---

# 4. NEW ACTIVE PRODUCT MILESTONE

## Milestone

```text
DTI-NI-M1
FRESH DEVICE NETWORK INTELLIGENCE
```

## Product questions

The Device Card should be able to answer:

```text
Which supported protocol families has this Device used recently?

Which supported services were recently recognized?

Which infrastructure / organizations are supported by evidence?

Are there conservative transport-health signals worth showing?

How fresh is each result?

How complete is the source / attribution / recognition coverage?
```

It MUST NOT claim new DTI ownership for:

```text
online state
authorization state
AP association
RSSI/SNR
traffic bytes/rates
Device identity
Device Fingerprint
```

---

# 5. DEFAULT DEVICE CARD OUTPUT — V1

The default Device Card consumes only product-safe derived summaries.

## 5.1 Protocol Intelligence

Visible:

```text
Recent Protocols
Last Protocol Observation
Freshness
Coverage / Availability
```

Each protocol item may contain:

```text
protocol_family
last_observed_at
support_state
freshness_state
```

V1 protocol families are observed/supported families, NOT mutually exclusive traffic categories.

Examples:

```text
QUIC
may also imply UDP activity

TLS
may also coexist with TCP

DNS
may use UDP or TCP
```

Therefore V1 MUST NOT derive from the protocol list:

```text
traffic percentages
traffic totals
exclusive category shares
```

## Dominant Protocol

For DTI-NI-M1 V1:

```text
DOMINANT PROTOCOL =
OUT OF SCOPE
```

It is not optional V1 functionality.

A future separately justified ranking contract may reintroduce it.

---

## 5.2 Recent Services

Visible:

```text
Recent Services
Service Categories
Last Service Observation
Freshness
Recognition Coverage
```

Each supported service may contain:

```text
service_id / display label
service_category_id where resolved
support_state
last_observed_at
freshness_state
```

Default UI does NOT expose raw DNS/SNI/IP history.

---

## 5.3 Infrastructure / Organization

Visible:

```text
Recent Infrastructure / Organizations
```

Examples of the dimension:

```text
Google
Meta
Cloudflare
Microsoft
Apple
```

This dimension is supporting context.

It MUST NOT imply a specific service by itself.

It MUST NOT become a raw remote-IP product.

---

## 5.4 Transport Health

Visible only for admitted evidence:

```text
Transport Health
Recent Transport Signals
Last Health Observation
Freshness
Coverage / Availability
```

No opaque global score in V1.

Forbidden unsupported claims:

```text
packet-loss %
RTT
retransmission %
bandwidth-quality score
generic "bad Internet"
```

---

# 6. SOURCE DIRECTION

Preferred source:

```text
EXISTING admitted production Suricata
```

Target flow:

```text
existing production Suricata
        ↓
isolated / versioned DTI metadata output
        ↓
DTI metadata ingest / normalizer
        ↓
normalized durable metadata observations
        ↓
temporal Device attribution
        ↓
Device-relative metadata edges
        ↓
Protocol / Service / Transport intelligence
        ↓
DeviceNetworkIntelligenceReadModelV1
        ↓
Device Card
```

Forbidden:

```text
another Python full-packet traffic meter for this lane
one collector per UI feature
Device Card reading raw EVE
Device Card reading PCAP
UI performing attribution
UI performing recognition
UI reconstructing source semantics
```

The accepted Fingerprint-facing Suricata contract remains protected.

---

# 7. SURICATA V1 EVENT-FAMILY POLICY

## Mandatory first Network Intelligence source candidates

```text
dns
tls
quic
stats
```

## Conditional family

```text
flow =
CONDITIONAL / ADMISSION-GATED
```

`flow` may later be admitted for:

```text
generic TCP/UDP/ICMP observations
flow lifecycle
connection-oriented intelligence
Tier-B Transport Health
```

But:

```text
FLOW FAILURE
FLOW EXCESSIVE COST
FLOW UNSUITABLE FRESHNESS
```

MUST NOT block:

```text
DNS Intelligence
TLS Intelligence
QUIC Intelligence
Service Recognition based on admitted metadata
```

Terminal flow events are NOT automatically valid Fresh/current protocol evidence.

For every family:

```text
PRODUCT FRESHNESS
REQUIRES PROVEN EVENT-EMISSION SEMANTICS
```

A terminal event arriving now MUST NOT be labeled Fresh if its semantic event time belongs to an older observation.

## Explicitly outside first candidate set

```text
http
alert
dhcp
```

Rationale:

```text
HTTP adds unnecessary privacy/cardinality for V1.

alert belongs to later Security lane.

DHCP identity/context should reuse existing admitted
CaptivPortal / Fingerprint / network evidence.
```

---

# 8. REUSE OF ACCEPTED OPTION-A EVIDENCE

DTI-NI-00 MUST NOT restart Suricata coexistence research from zero.

Already accepted bounded evidence established that:

```text
existing production Suricata
+
isolated/versioned second EVE output
```

can coexist without observed Fingerprint regression under the tested Option-A admission.

Therefore DTI-NI-00 researches only the DELTA required for Network Intelligence:

```text
final family set
exact output transport
delivery/replay semantics
event-field semantics
per-family resource/cardinality
combined resource/cardinality
freshness/emission semantics
privacy boundary
```

Do NOT re-prove unchanged:

```text
capture topology
Fingerprint coexistence topology
RSPAN placement
basic Option-A feasibility
```

merely for documentation completeness.

---

# 9. EXACT DELIVERY / REPLAY IDENTITY CONTRACT

Before implementation, DTI-NI-00 MUST freeze:

```text
exact EVE transport:
  file / socket / other admitted mechanism

rotation semantics
source restart semantics
reader restart semantics
ingest restart semantics
reader checkpoint semantics
partial-write behavior
duplicate-delivery behavior
replay behavior
```

For every admitted family define deterministic source-event identity where source semantics permit it.

Required invariant:

```text
same source identity
+
same semantic payload
→ idempotent replay
```

Conflict invariant:

```text
same source identity
+
different semantic payload
→ CONFLICT
→ reject / quarantine / quality fault
```

Forbidden:

```text
heuristic event deduplication
```

Implementation MUST NOT double Device intelligence because:

```text
EVE file replayed
reader restarted
ingest restarted
source restarted
```

---

# 10. NORMALIZED OBSERVATION CONTRACTS

The active lane implements the metadata-only first slice of the logical Network Observation Foundation.

No periodic traffic bucket is required.

## 10.1 NetworkMetadataEnvelopeV1

Common fields:

```text
observation_id
schema_version

source_type = suricata
source_version
source_event_family
source_event_identity

capture_source_id
capture_scope_binding_version

network_scope_id
network_scope_state

site_id

event_at
ingested_at

source_health_ref
provenance
```

Where applicable:

```text
flow_id
transaction_id
src_ip
dst_ip
src_port
dst_port
transport_protocol
app_protocol
```

`event_at` and `ingested_at` are distinct.

Late arrival MUST NOT make an old event current.

---

## 10.2 Capture / Network Scope

`site_id` alone is NOT sufficient scope.

Current mirrored traffic may contain more than one source network.

Required:

```text
capture_source_id
capture_scope_binding_version
network_scope_id / network_scope_state
```

Before Device projection:

```text
event
→ admitted capture source
→ proven intended network population
→ Site
```

If network scope is:

```text
unknown
ambiguous
outside intended CaptivPortal population
```

then:

```text
NO Site/Device product attribution
```

Never silently turn every event visible on the capture interface into guest Device intelligence.

---

## 10.3 DnsObservationV1

Minimum where source semantics are admitted:

```text
event_at
source_event_identity
flow_id / transaction_id where available
query endpoint
resolver endpoint
query_name
query_type
response_code / result
timing fields only when proven
source/provenance
```

Raw query names are SensitiveNetworkMetadata.

---

## 10.4 TlsObservationV1

Minimum where visible:

```text
event_at
source_event_identity
flow_id where available
endpoints
SNI
TLS version
ALPN
bounded certificate metadata only if separately admitted
source/provenance
```

Encrypted absence is not negative evidence.

---

## 10.5 QuicObservationV1

Minimum where visible:

```text
event_at
source_event_identity
flow_id where available
endpoints
QUIC version
observable handshake metadata
source/provenance
```

Opaque/encrypted facts remain unknown.

---

## 10.6 FlowProtocolObservationV1 — Conditional

Exists only if `flow` passes admission.

Possible fields:

```text
event_at
source_event_identity
flow_id
src/dst endpoints
ports
transport protocol
admitted app_protocol
flow start/end/state
source/provenance
```

Terminal flow event semantics MUST NOT be treated as current evidence without proven event-emission rules.

Suricata completed-flow bytes remain metadata/diagnostic facts, not an alternate Traffic owner.

---

## 10.7 NetworkMetadataSourceHealthV1

Layer-specific source state:

```text
evaluated_at
capture_source_id
capture_health
metadata_output_health
last_output_event_at
source_generation/version
```

This contract prevents:

```text
no metadata observed
```

from silently meaning:

```text
no protocol activity
no service activity
```

when source coverage is unavailable.

---

# 11. TEMPORAL DEVICE ATTRIBUTION CONTRACT

Attribution is internal infrastructure, not a Device Card feature.

Required chain:

```text
Suricata event
        ↓
capture_source_id
        ↓
network_scope
        ↓
Site
        ↓
endpoint IP at event_at
        ↓
temporal Site + IP binding
        ↓
Site + MAC
        ↓
existing device_id where authoritative
```

## 11.1 IPv4 / IPv6 scope

For DTI-NI-M1 V1:

```text
IPv4 temporal attribution =
REQUIRED
```

```text
IPv6 temporal attribution =
REQUIRED ONLY WHEN TRUSTWORTHY AUTHORITY IS PROVEN
```

If IPv6 binding authority is insufficient:

```text
IPv6 event
→ unattributed / unsupported for Device projection
```

Forbidden:

```text
guess
borrow IPv4 identity
cross-MAC merge
block IPv4 milestone because IPv6 is unresolved
```

IPv6 may receive a separate later admission.

---

## 11.2 Binding sources

Reuse existing evidence where admitted:

```text
Current State
Registry
Visit Lifecycle
existing DHCP/Fingerprint evidence
existing historical Observation evidence
```

Do NOT build:

```text
alternate Registry
alternate Visit system
alternate DHCP product
```

An admission gate must freeze the minimum source authority for:

```text
Site + IP + event_at
→ Site + MAC
```

---

## 11.3 Attribution result

Conceptual:

```text
NetworkMetadataAttributionResultV1
```

Minimum states:

```text
resolved
ambiguous
unattributed
not_yet_registry_resolved
invalid
```

Permanent:

```text
IP-only permanent identity = FORBIDDEN
cross-MAC merge = FORBIDDEN
ambiguous remains ambiguous
missing attribution does not become another Device
no device_id yet does not drop observation
no device_id yet does not invent identity
```

Pre-Registry observations follow the already accepted late-binding principle.

---

# 12. DEVICE-RELATIVE EVENT PROJECTION

Service Recognition MUST NOT operate directly on generic:

```text
src_ip / dst_ip
```

or an unqualified “destination endpoint”.

After temporal attribution, normalize into:

```text
DeviceNetworkMetadataEdgeV1
```

Minimum:

```text
site_id
device_id
or Site+MAC pre-Registry identity

event_at

device_endpoint
peer_endpoint

device_endpoint_role =
src / dst

peer_scope =
local / external / unknown

direction =
outbound / inbound / local / unknown

source_observation_ref
attribution_state
network_scope_state
```

One source event may produce:

```text
0
1
or 2
```

Device-relative edges.

For local Device↔Device traffic:

```text
each resolved Device
may receive its own Device-relative edge
```

The peer is NOT automatically “Internet”.

---

# 13. PROTOCOL SUMMARY CONTRACT

Derived contract:

```text
DeviceProtocolSummaryV1
```

Minimum:

```text
site_id
device_id
evaluated_at

window_policy_id
window_start
window_end

recent_protocols[]
last_protocol_observed_at

freshness_state

source_coverage_state
attribution_coverage_state
availability_state

source_generation/version
```

Each item:

```text
protocol_family
last_observed_at
support_state
supporting_observation_types
```

Support states conceptually:

```text
directly_observed
deterministically_derived
ambiguous
unknown
unavailable
```

Protocol families are NON-EXCLUSIVE.

No percentages or totals are derived from the list.

`dominant_protocol_family` is absent from V1.

---

# 14. COVERAGE / EMPTY RESULT SEMANTICS

Freshness and coverage are separate dimensions.

Minimum health/coverage dimensions:

```text
source_coverage
attribution_coverage
recognition_coverage where applicable
```

Product-safe result states conceptually equivalent to:

```text
supported_results_present

no_supported_result_observed_with_sufficient_coverage

insufficient_source_coverage

insufficient_attribution

recognition_limited

unavailable
```

Exact enums may be refined by task contract.

Forbidden wording:

```text
No services used
```

for V1.

Preferred when justified:

```text
No supported services recognized in the recent window
```

A blank list MUST NOT ambiguously collapse:

```text
no network use
no supported recognition
encrypted/unobservable service
source unavailable
attribution unavailable
```

---

# 15. SERVICE RECOGNITION CONTRACT

Pipeline:

```text
DeviceNetworkMetadataEdgeV1
        ↓
versioned RecognitionRuleSet
        ↓
ServiceObservationV1
        ↓
DeviceServiceSummaryV1
```

## 15.1 Evidence strength classes

### Strong / directly associated evidence

May include:

```text
admitted same-event / same-flow SNI rule
admitted specific Suricata application protocol
other directly associated admitted signal
```

### Correlated evidence

May include:

```text
DNS name
→ answer endpoint
→ bounded temporal connection correlation
```

### Weak contextual evidence

Examples:

```text
shared destination IP
CDN ownership
generic cloud-provider ownership
```

Weak context MUST NOT alone imply a specific service.

Permanent:

```text
IP-only exact service inference =
FORBIDDEN
```

unless an explicitly admitted deterministic mapping proves it.

Provider ownership remains separate from Service.

---

## 15.2 Recognition inputs

Allowed after attribution/device-relative projection:

```text
DNS name where visible
SNI where visible
peer endpoint
port/protocol
admitted Suricata app_protocol
multiple associated observations
versioned local rules
```

---

## 15.3 ServiceObservationV1

Minimum:

```text
site_id
device_id
observed_at

organization_id optional
service_id optional
service_category_id optional

evidence_strength_class
support_state
supporting_signal_types
evidence_refs

recognition_ruleset_id
recognition_ruleset_version

resolution_state
```

Preferred support/resolution states:

```text
directly_supported
multi_signal_supported
ambiguous
unknown
unavailable
```

No arbitrary numerical confidence percentage in V1.

---

## 15.4 Required recognition fixtures

Must include:

```text
shared CDN
shared cloud provider
multiple services behind same organization
DNS cache
ECH / no SNI
VPN/tunnel visibility loss
local resolver
public resolver
```

---

# 16. TAXONOMY BOUNDARY

Permanent dimensions:

```text
Infrastructure / Organization
!=
Service
!=
Service Category
```

Examples:

```text
Google infrastructure
!=
Google Search

Meta infrastructure
!=
WhatsApp

Cloudflare infrastructure
!=
specific application
```

No overloaded `service_family` field may collapse the dimensions.

Recognition ownership remains one versioned `RecognitionRuleSet` boundary.

---

# 17. NI-05 ORGANIZATION CONTEXT — NOT A SECOND RECOGNITION ENGINE

`DTI-NI-04` owns recognition.

It produces independent dimensions:

```text
organization_id
service_id
service_category_id
```

Therefore:

```text
DTI-NI-05
```

is ONLY:

```text
organization-context summary
aggregation
product projection
```

It is NOT:

```text
another destination-recognition engine
another rules engine
another IP ownership classifier
```

NI-05 summarizes the organization dimension produced by the admitted recognition pipeline.

---

# 18. FRESHNESS CONTRACT

Freshness is Network Intelligence freshness.

It does NOT inherit Omada Presence / Online semantics.

## 18.1 Time basis

Semantic freshness:

```text
event_at
```

Delivery monitoring:

```text
ingested_at
```

Late delivery cannot make old evidence fresh.

---

## 18.2 Named windows

V1 uses:

```text
ALLOWED_EVENT_LATENESS
CURRENT_WINDOW
RECENT_WINDOW
HISTORY_RETENTION
```

Numeric values MUST be frozen by the freshness admission gate before NI-03 implementation.

Coder MUST NOT invent them.

Required:

```text
ALLOWED_EVENT_LATENESS
<
CURRENT_WINDOW
<
RECENT_WINDOW
<
HISTORY_RETENTION
```

---

## 18.3 Presentation freshness

```text
fresh
recent
stale
unavailable
```

### fresh

Qualifying attributed observation inside `CURRENT_WINDOW` and required coverage sufficient.

### recent

No qualifying observation inside `CURRENT_WINDOW`, but qualifying evidence inside `RECENT_WINDOW` and required coverage sufficient.

### stale

Known historical result exists but last supporting `event_at` is outside `RECENT_WINDOW`.

### unavailable

Source / output / ingest / attribution / recognition dependency is insufficient for a current/recent statement.

`unavailable` is NOT:

```text
no activity
no protocol
no service
```

---

## 18.4 Late event

If:

```text
ingested_at - event_at > ALLOWED_EVENT_LATENESS
```

the event is late.

It may update retained historical evidence if otherwise valid.

It MUST NOT resurrect:

```text
Fresh Protocol
Recent Service
Current Transport Health
```

based on arrival time.

---

# 19. LAYERED HEALTH MODEL

Network Intelligence health MUST NOT collapse to one Suricata state.

Separate conceptual dimensions:

```text
capture_health
metadata_output_health
metadata_ingest_health
attribution_coverage
recognition_coverage
```

Examples:

```text
Suricata capture healthy
+
DTI metadata output broken
→ Network Intelligence unavailable
```

```text
Protocol Intelligence healthy
+
Recognition rules unavailable
→ Protocol Intelligence remains valid
→ Service Intelligence degrades independently
```

Each Device Card sub-domain degrades independently.

---

# 20. UI FRESHNESS DELIVERY CONTRACT

V1 Device Card decision:

```text
DELIVERY MODE =
BOUNDED AUTOMATIC POLLING
+
MANUAL REFRESH PERMITTED
```

No websocket/live push is required.

The read model exposes at minimum:

```text
evaluated_at
last_observed_at
freshness_state
source/coverage state
```

The exact numeric minimum polling interval MUST be frozen in the NI-G4/NI-03 product contract after actual source-delivery/freshness measurements.

Architectural constraint:

```text
UI_POLL_INTERVAL
>=
admitted minimum source/read-model refresh interval
```

and:

```text
UI MUST NOT poll substantially faster
than underlying evidence can meaningfully change.
```

Manual refresh is subject to the same server-side minimum refresh / rate-limit contract.

Required behavior:

```text
no overlapping UI requests
no uncontrolled polling fan-out
no inheritance of Current Device Context polling semantics by assumption
```

The NI read model SHOULD expose a server-defined:

```text
next_refresh_not_before
or equivalent refresh-policy metadata
```

so UI does not invent cadence.

---

# 21. SENSITIVE METADATA / RETENTION / PAYLOAD BOUNDARY

Permanent V1 rules:

```text
NO PACKET PAYLOAD PERSISTENCE

NO HTTP CONTENT

NO DNS PAYLOAD BEYOND ADMITTED METADATA FIELDS

NO TLS APPLICATION CONTENT

NO PCAP PRODUCT STORAGE
```

SensitiveNetworkMetadata:

```text
raw DNS names/history
raw SNI
remote IP history
fine-grained endpoint timelines
```

is restricted and short-retained according to the admitted retention contract.

Default Device Card receives only derived product-safe summaries.

## Logical classes

### NI-R0

```text
raw Suricata transport/EVE
transient / bounded operational transport
not product history
```

### NI-R1

```text
normalized sensitive endpoint metadata
short retention
restricted engineering/diagnostic access
```

### NI-R2

```text
normalized protocol observations
medium retention
```

### NI-R3

```text
derived protocol/service/organization summaries
longer product retention
```

### NI-R4

```text
Transport Health evidence/assessments
policy-defined
```

Numeric retention durations require storage/cardinality + privacy admission.

Rebuild dependency closure remains mandatory.

---

# 22. TRANSPORT HEALTH V1 — INDEPENDENT SUBSET

Only metadata-derived signals independent of periodic packet accounting may enter V1.

## Tier A admission target

```text
DNS failure indicator
DNS result/rcode category
last DNS failure observation
DNS latency where transaction timing is proven
```

## Tier B — conditional on admitted `flow` and exact field semantics

```text
TCP reset indicator
failed connection indicator
connection churn
short aborted session indicator
```

Tier-B MUST NOT block Tier-A.

If exact semantics are not proven:

```text
UNAVAILABLE
```

is correct.

Explicitly forbidden without separate proof:

```text
packet-loss %
RTT
retransmission %
generic Internet-health verdict
```

RF remains existing Omada/Observation/Wireless Analytics ownership.

---

# 23. REVISED DEPENDENCY GRAPH

Old traffic-first dependency is superseded for the active lane.

New active chain:

```text
accepted DTI-00 capture/source evidence
        ↓
DTI-NI-00
Suricata Metadata Source & Field Semantics Admission
        ↓
DTI-NI-01
Metadata-Only Network Observation Foundation
        ↓
DTI-NI-02
Temporal Device Attribution + Device-relative Projection
        ↓
DTI-NI-03
Protocol Intelligence + Protocol Device Card
        ↓
DTI-NI-04
Service Recognition
        ↓
DTI-NI-05
Organization Context Projection
        ↓
DTI-NI-06
Transport Health V1
```

Parked parallel lane:

```text
DTI-03 periodic accounting
DTI-04 traffic summaries
DTI-05 SPAN Traffic MVP
=
PARKED
```

No dependency from parked DTI-03 to:

```text
DTI-NI-03
DTI-NI-04
DTI-NI-05
```

Only Transport Health signals that specifically require parked traffic semantics remain excluded/parked.

---

# 24. RELATIONSHIP TO ORIGINAL DTI-01 / DTI-02

Original architectural principles remain valid:

```text
normalized durable facts
Site-aware evidence
event_at != ingested_at
provenance/versioning
failure isolation
temporal attribution
late identity binding
```

But the active lane does NOT wait for monolithic traffic-centric DTI-01/02/03.

Instead:

```text
DTI-NI-01 =
metadata-only first implementation slice
of the logical Network Observation Foundation

DTI-NI-02 =
metadata-attribution first implementation slice
using accepted identity principles
```

If the Traffic lane is reopened later, it should extend the same logical foundation rather than create a competing parallel foundation.

---

# 25. STAGED EXECUTION ROADMAP

## DTI-NI-00 — SURICATA METADATA SOURCE & FIELD SEMANTICS ADMISSION

**Type:** Research / admission  
**Coder:** HOLD  
**Sysadmin:** HOLD until exact contract/authorization

Research only the remaining DELTA.

### Mandatory family candidates

```text
dns
tls
quic
stats
```

### Conditional family

```text
flow
```

### Required decisions

```text
exact EVE transport
rotation
restart
checkpoint
partial-write
duplicate/replay
source-event identity
event_at semantics
delivery lag
source health
network-scope fields
privacy
per-family cardinality
combined cardinality
resource cost
```

### Per-family measured output

For each candidate:

```text
events/sec
bytes/sec
bytes/day modeled from bounded measured sample
max event size
unique flow_id rate where applicable
DNS-name cardinality where applicable
SNI cardinality where applicable
output growth
Suricata CPU delta
Suricata RSS delta
capture-drop delta
```

Also measure the combined candidate set.

Admission outcome MUST be family-specific:

```text
dns = admitted / rejected / conditional
tls = admitted / rejected / conditional
quic = admitted / rejected / conditional
stats = admitted / rejected / conditional
flow = admitted / rejected / conditional
```

An expensive family is not admitted merely because architecture once listed it.

### Outputs

```text
SuricataMetadataSourceContractV1
EventFieldSemanticMatrix
DeliveryReplayIdentityContractV1
NetworkScopeSourceContractV1
FreshnessPolicyCandidate
MetadataCardinalityResourceReport
```

---

## DTI-NI-01 — METADATA-ONLY NETWORK OBSERVATION FOUNDATION

After NI-00 PASS.

Implement:

```text
NetworkMetadataEnvelopeV1
DnsObservationV1
TlsObservationV1
QuicObservationV1
conditional FlowProtocolObservationV1
NetworkMetadataSourceHealthV1

bounded ingest
idempotent replay
conflict handling
provenance/version
retention classes
layered health
```

No traffic buckets.

No Device Card yet.

---

## DTI-NI-02 — TEMPORAL DEVICE ATTRIBUTION + DEVICE-RELATIVE PROJECTION

After attribution-authority admission.

Implement:

```text
NetworkMetadataAttributionResultV1
IPv4 temporal Site+IP→Site+MAC
existing device_id binding
ambiguous/unattributed handling
pre-Registry late binding
DeviceNetworkMetadataEdgeV1
```

IPv6 is admitted separately if trustworthy authority exists.

No new Registry.

No cross-MAC merge.

---

## DTI-NI-03 — PROTOCOL INTELLIGENCE + DEVICE CARD P1

First visible Network Intelligence milestone.

Implement:

```text
DeviceProtocolSummaryV1

Recent Protocols
Last Protocol Observation
fresh/recent/stale/unavailable
source coverage
attribution coverage
```

No Dominant Protocol.

No protocol percentages.

No protocol traffic totals.

Device Card uses bounded automatic polling + manual refresh under frozen refresh-policy contract.

---

## DTI-NI-04 — SERVICE RECOGNITION

Implement:

```text
RecognitionTaxonomyContractV1
RecognitionRuleSetV1
ServiceObservationV1
DeviceServiceSummaryV1

Recent Services
Service Categories
coverage-aware empty states
```

Provider != service != category.

IP-only exact service inference forbidden unless deterministic mapping is explicitly admitted.

---

## DTI-NI-05 — ORGANIZATION CONTEXT PROJECTION

Implement only:

```text
organization summary
aggregation
Device Card projection
```

It consumes the organization dimension from NI-04.

It does NOT own recognition rules.

No raw IP-list product.

No mandatory external ASN/org source for V1.

---

## DTI-NI-06 — TRANSPORT HEALTH V1

Implement admitted independent signals.

Order:

```text
Tier A DNS health
        ↓
conditional Tier B flow-derived health
```

No periodic-meter dependency.

No unsupported global network verdict.

---

# 26. RESEARCH / ADMISSION GATES

No Coder authorization is issued by this addendum.

## NI-G1 — Suricata family/output admission

Reuse Option-A evidence.

Prove DELTA only:

```text
dns
tls
quic
stats
conditional flow
```

For each family:

```text
isolated/versioned output
Fingerprint-facing stream unchanged
resource/cardinality acceptable
capture health acceptable
rollback
privacy
event freshness/emission semantics
```

---

## NI-G2 — Delivery / replay identity

Freeze:

```text
transport
rotation
checkpoint
partial-write
restart
duplicate delivery
replay
source-event identity
idempotency
conflict behavior
```

No heuristic event dedup.

---

## NI-G3 — Field semantics

Controlled fixtures must prove:

```text
event timestamps
flow / transaction identity
endpoint semantics
DNS semantics
TLS semantics
QUIC semantics
conditional flow semantics
stats/health semantics
```

Do not infer from field names.

---

## NI-G4 — Capture/network scope admission

Prove:

```text
capture_source_id
capture_scope_binding_version
network_scope_id/state
intended CaptivPortal population filtering
```

Unknown/ambiguous scope MUST NOT become Device product data.

---

## NI-G5 — Temporal attribution authority

V1 required:

```text
IPv4 Site+IP+event_at → Site+MAC
```

Test:

```text
current binding
IP reassignment
ambiguous binding
missing binding
local Device↔Device
pre-Registry
late device_id
```

IPv6 only if trustworthy authority is separately proven.

---

## NI-G6 — Freshness + UI delivery policy

Measure:

```text
source emission behavior
event delivery lag
ingest lag
late events
source/output/ingest outage
read-model update cadence
```

Then freeze numeric:

```text
ALLOWED_EVENT_LATENESS
CURRENT_WINDOW
RECENT_WINDOW
minimum UI polling interval
```

before NI-03.

Coder/UI MUST NOT choose them.

---

## NI-G7 — Service Recognition knowledge admission

Freeze:

```text
taxonomy
evidence-strength classes
rule format
rule provenance/version
fixtures
shared CDN behavior
shared provider behavior
DNS cache
ECH/no-SNI
VPN/tunnel loss
resolver cases
IP-only inference prohibition
```

---

## NI-G8 — Transport Health signal admission

For each product signal prove:

```text
source fields
event semantics
fixture
false-positive boundary
health dependency
freshness
coverage
```

Unsupported signal remains unavailable.

---

# 27. EXISTING FACTS EXPLICITLY NOT REBUILT

| Existing fact | Existing owner/context | NI use |
|---|---|---|
| MAC | Registry / existing network state | correlation only |
| IP | Current State / existing evidence | temporal correlation only |
| SSID | Omada / Current State | context only |
| AP | Omada / Current State | context only |
| Presence / Online | Current State | context only |
| Authorization | Auth / Visit Lifecycle | context only |
| RSSI / SNR | Observation / Wireless Analytics | compose only |
| Radio/channel state | Omada / Observation | compose only |
| Controller device type/platform | existing controller facts | context only |
| Current Guest Traffic | existing traffic contract | no replacement |
| Historical traffic products | existing traffic contracts | no replacement |
| First/last seen | existing Registry/product | compose only |
| Visits | Visit Lifecycle | context/correlation |
| Device identity | Registry | consume only |
| Device Fingerprint | persisted authoritative ClassificationResult | compose only |

Permanent:

```text
NETWORK INTELLIGENCE
ADDS NEW SEMANTICS
NOT COPIES OF EXISTING FIELDS
```

---

# 28. DEVICE CARD READ MODEL

Conceptual:

```text
DeviceNetworkIntelligenceReadModelV1
```

Composes independently degradable sub-domains:

```text
ProtocolSummary
ServiceSummary
OrganizationContextSummary
TransportHealthSummary

freshness
source coverage
attribution coverage
recognition coverage
evaluated_at
last_observed_at
refresh policy metadata
```

UI MUST NOT:

```text
read raw EVE
read raw DNS/SNI/IP history
perform attribution
perform recognition
derive health
```

---

# 29. FAILURE ISOLATION

Network Intelligence failure MUST NOT affect:

```text
Portal/Auth
CAPPORT
Omada integration
Device Fingerprint
Current State
Visit Lifecycle
existing traffic products
```

Failure degrades only the affected NI layer.

Examples:

```text
metadata output broken
→ Network Intelligence source unavailable
→ Fingerprint may remain healthy
```

```text
recognition unavailable
→ Protocol Intelligence may remain fresh/valid
→ Service Intelligence unavailable
```

Missing source MUST NOT become:

```text
no protocols
no services
device offline
traffic zero
```

---

# 30. SUPERSESSION / PRESERVATION

This addendum supersedes only execution ordering/product-priority assumptions that made the parked Traffic lane a prerequisite for metadata intelligence.

Superseded:

```text
DTI-06 requiring DTI-03
DTI-07 operationally blocked by DTI-03
metadata-safe DTI-08 subset requiring DTI-03
traffic-first DTI-00→05 as first product milestone
```

Preserved from accepted DTI v0.3:

```text
DTI != Device Fingerprint
DTI != Authorization/CAPPORT

Site-aware evidence
CaptureScopeBinding
no IP-only permanent identity
no cross-MAC merge
late authoritative device_id binding
metadata over payload
SensitiveNetworkMetadata restriction
organization != service != category
source/provenance/versioning
event_at != ingested_at
conservative unavailable semantics
failure isolation
one product metric → one semantic owner
```

---

# 31. FINAL CANDIDATE REVIEW DISPOSITION

```text
NETWORK INTELLIGENCE REPRIORITIZATION =
ACCEPTED IN PRINCIPLE / FINAL TECH LEAD CONFIRMATION PENDING

PERIODIC TRAFFIC METER =
PARKED

DTI-NI-M1 =
FRESH DEVICE NETWORK INTELLIGENCE

MANDATORY FIRST SURICATA CANDIDATES =
dns + tls + quic + stats

FLOW =
CONDITIONAL / ADMISSION-GATED

IPV4 TEMPORAL ATTRIBUTION =
REQUIRED V1

IPV6 TEMPORAL ATTRIBUTION =
NON-BLOCKING / SEPARATE ADMISSION IF NEEDED

DOMINANT PROTOCOL =
OUT OF V1

PROTOCOL FAMILIES =
NON-EXCLUSIVE

SERVICE IP-ONLY EXACT INFERENCE =
FORBIDDEN UNLESS DETERMINISTIC MAPPING ADMITTED

NI-05 =
ORGANIZATION CONTEXT PROJECTION
NOT SECOND RECOGNITION ENGINE

UI DELIVERY =
BOUNDED AUTOMATIC POLLING + MANUAL REFRESH
EXACT MINIMUM INTERVAL FROZEN AFTER NI-G6 MEASUREMENT

PAYLOAD PERSISTENCE =
NO

CODER =
HOLD

SYSADMIN =
HOLD

PRODUCTION =
NO CHANGE

NEXT =
TECH LEAD REVIEW OF v0.2 FINAL CANDIDATE
→ if PASS:
Architect issues exact TASK-DTI-NI-00
SURICATA METADATA SOURCE & FIELD SEMANTICS ADMISSION
```
