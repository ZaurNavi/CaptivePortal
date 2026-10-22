# DTI — NETWORK INTELLIGENCE PRIORITY ADDENDUM v0.1
## Revised Product Milestone & Execution Roadmap

**Project:** CaptivPortal  
**Program:** Device Traffic Enrichment / Device Intelligence (DTI)  
**Artifact type:** Focused Architecture Addendum / Revised Execution Roadmap  
**Status:** DRAFT FOR OWNER + TECH LEAD REVIEW  
**Base architecture:** `DEVICE-TRAFFIC-ENRICHMENT-ARCHITECTURE-v0.3_FINAL_TECHLEAD_ACCEPTED.md`  
**Architecture rewrite:** NO  
**Roadmap reprioritization:** YES  
**Coder:** HOLD  
**Production:** NO CHANGE  
**Periodic Traffic Meter lane:** PARKED  

---

# 1. DISPOSITION

The DTI program remains valid, but its implementation priority changes.

The former first product path:

```text
DTI-03 periodic traffic accounting
→ DTI-04 traffic summaries
→ DTI-05 SPAN Traffic Device Card MVP
```

is now:

```text
PARKED
```

The evidence is retained.

No redesign or remediation of the periodic meter is authorized by this addendum.

The new active lane is:

```text
NETWORK INTELLIGENCE
```

Its purpose is:

```text
Tell the operator NEW things about
how a Device uses the network.
```

The active lane MUST NOT spend its first stages reproducing facts already owned by Omada / Current State / Registry / Visit / Device Fingerprint.

---

# 2. FROZEN NON-DUPLICATION PRINCIPLE

The following facts are existing product/context facts and are NOT new Network Intelligence product goals:

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

They MAY be consumed as:

```text
correlation input
context
display composition input
```

They MUST NOT be:

```text
re-collected as a new DTI product
re-implemented as an alternate owner
re-labeled as new Network Intelligence
```

Permanent ownership remains:

```text
existing fact
→ existing semantic owner
```

Network Intelligence only adds new network-observed meaning.

---

# 3. PARKED LANE

The following are parked until a future Owner/Architect/Tech Lead decision explicitly reopens them:

```text
lightweight periodic packet meter
5-second packet traffic accounting
DTI-03 periodic traffic accounting
DTI-04 Visit / Device Traffic Summaries
DTI-05 SPAN Traffic Device Card MVP
```

Also parked with that lane:

```text
current SPAN traffic rate
periodic packet/byte traffic buckets
SPAN upload/download totals
SPAN Visit traffic totals
SPAN Today / 7-day traffic totals
SPAN peak-rate product metrics
```

Existing CaptivPortal/Omada traffic products remain untouched.

Traffic-derived metrics that truly require the parked periodic accounting source remain dependent on the parked lane.

The parked lane does NOT block metadata-derived Protocol, Service, Organization, or safe Transport Health intelligence.

---

# 4. NEW ACTIVE PRODUCT MILESTONE

## Milestone ID

```text
DTI-NI-M1
FRESH DEVICE NETWORK INTELLIGENCE
```

## Product objective

The Device Card gains a new Network Intelligence section that answers:

```text
Which network protocol families has this Device used recently?

Which likely services has it used recently?

Which infrastructure / organizations are supported by evidence?

Are there conservative transport-health signals worth showing?

How fresh is this intelligence?
```

It does NOT answer with new DTI ownership for:

```text
online state
authorization state
AP association
RSSI/SNR
traffic bytes/rates
identity/fingerprint
```

---

# 5. EXACT DEFAULT DEVICE CARD OUTPUTS — DTI-NI-M1

The default Device Card Network Intelligence block contains only product-safe derived outputs.

## 5.1 Protocol Summary

```text
Recent Protocols
Last Protocol Observation
Protocol Freshness
Protocol Availability
```

Each recent protocol item may contain:

```text
protocol_family
last_observed_at
freshness_state
support/provenance state
```

Initial protocol families targeted:

```text
DNS
TLS
QUIC
TCP
UDP
ICMP
```

Additional protocol labels:

```text
NTP
mDNS
SSDP
STUN
TURN
tunnel indicators
```

are visible only after their derivation is separately admitted as defensible.

No unsupported protocol label is fabricated.

### Dominant protocol

```text
Dominant Protocol
```

is OPTIONAL.

It MUST remain unavailable unless a frozen ranking basis proves what “dominant” means.

The parked packet-meter lane MUST NOT be implicitly reintroduced merely to populate this field.

---

## 5.2 Recent Services

Default product output:

```text
Recent Services
```

For each supported service:

```text
service_id / display label
service_category where resolved
support_state
last_observed_at
freshness_state
```

No raw domain, SNI, or remote IP is required for the default card.

---

## 5.3 Infrastructure / Organization

Default product output:

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

This dimension is context/supporting evidence.

It is NOT a remote-IP-history product.

It MUST NOT imply a specific service without separate service evidence.

---

## 5.4 Transport Health

Default product output is a conservative summary of admitted signals only:

```text
Transport Health
Recent Transport Signals
Last Health Observation
Freshness / Availability
```

No single opaque “Internet score” is introduced in V1.

No unsupported:

```text
packet loss %
RTT
retransmission %
bad Internet
```

claim is allowed.

---

# 6. SOURCE DIRECTION

The preferred source remains the EXISTING admitted Suricata capture process.

Target producer model:

```text
existing production Suricata
        ↓
isolated / versioned DTI metadata output
        ↓
DTI metadata normalizer
        ↓
normalized durable network metadata observations
        ↓
temporal Device attribution
        ↓
Protocol / Service / Transport Intelligence
        ↓
Device Network Intelligence read model
        ↓
Device Card
```

Forbidden:

```text
one collector per UI feature
another Python full-packet traffic meter for this lane
Device Card reading raw EVE directly
Device Card scanning PCAP
UI performing recognition/classification
```

The existing Fingerprint-facing Suricata output remains protected and unchanged.

---

# 7. EXACT SURICATA EVENT FAMILIES REQUIRED FOR V1

The Network Intelligence V1 source contract requires the following Suricata EVE families:

```text
flow
dns
tls
quic
stats
```

## Purpose

```text
flow
→ transport protocol / endpoints / flow lifecycle metadata
→ generic TCP/UDP/ICMP context where present
→ candidate transport-health evidence

dns
→ DNS query/response metadata
→ response/result semantics
→ candidate DNS failure/latency evidence

tls
→ visible TLS metadata
→ SNI where available
→ TLS version / ALPN where available

quic
→ visible QUIC metadata
→ observable QUIC handshake/version metadata

stats
→ source / parser / capture health
→ evidence availability context
```

## Explicitly NOT required for V1

```text
http
alert
dhcp
```

Reason:

```text
HTTP is not required for the first product milestone
and creates unnecessary privacy/cardinality surface.

Security alerts belong to the later Security lane.

DHCP identity/context should reuse existing admitted
CaptivPortal / Fingerprint / network evidence rather than
creating a competing DHCP product path.
```

Installed Suricata capability is NOT equivalent to production admission.

The exact V1 event-family output requires a bounded admission gate before Coder implementation.

---

# 8. NORMALIZED OBSERVATION CONTRACTS

The Network Intelligence lane implements a METADATA-ONLY first slice of the existing logical Network Observation Foundation.

It does NOT require periodic traffic buckets.

## 8.1 NetworkMetadataEnvelopeV1

Common fields:

```text
observation_id
schema_version

source_type = suricata
source_version
source_event_family

capture_source_id
site_id

event_at
ingested_at

source_event_id / flow_id where available

src_ip
dst_ip
transport_protocol
app_protocol where source semantics support it

source_health_ref
provenance
```

`event_at` and `ingested_at` MUST remain distinct.

Late delivery cannot rewrite an old event as current intelligence.

---

## 8.2 FlowProtocolObservationV1

Purpose:

```text
transport / flow lifecycle metadata
```

Minimum semantic fields where provided/proven:

```text
flow_id
event_at
src_ip
dst_ip
src_port
dst_port
transport_protocol
app_protocol
flow_start_at
flow_end_at / state where available
source/provenance
```

This contract MUST NOT turn Suricata completed-flow bytes into the new authoritative Traffic product.

---

## 8.3 DnsObservationV1

Minimum semantic fields where available:

```text
event_at
flow_id / transaction identity where source provides it
client/resolver endpoints
query name
query type
response code / result
response timing fields only when source semantics are proven
source/provenance
```

Raw query names are SensitiveNetworkMetadata.

---

## 8.4 TlsObservationV1

Minimum:

```text
event_at
flow_id
endpoints
SNI where visible
TLS version where visible
ALPN where visible
bounded certificate metadata only if separately admitted
source/provenance
```

No encrypted absence becomes negative evidence.

---

## 8.5 QuicObservationV1

Minimum:

```text
event_at
flow_id where available
endpoints
QUIC version where visible
observable handshake metadata
source/provenance
```

Encrypted/opaque fields remain unknown.

---

## 8.6 NetworkMetadataSourceHealthV1

Derived from admitted health evidence:

```text
evaluated_at
capture_source_id
source_state
last_source_event_at
parser/capture health references
availability_state
```

It exists so that:

```text
no metadata observed
```

is not silently interpreted as:

```text
device used no protocols/services
```

when source coverage is unavailable.

---

# 9. TEMPORAL DEVICE ATTRIBUTION CONTRACT

Attribution is internal infrastructure.

It is NOT itself a new Device Card feature.

Required chain:

```text
Suricata network event
        ↓
admitted capture_source_id
        ↓
Site
        ↓
candidate endpoint IP at event_at
        ↓
temporal Site + IP binding
        ↓
authoritative Site + MAC
        ↓
existing device_id when available
```

## 9.1 Site

Site is obtained only from the admitted:

```text
CaptureScopeBinding
```

Unknown/ambiguous Site is never guessed.

---

## 9.2 Endpoint attribution

A normalized event may yield:

```text
0
1
or 2
```

device-attribution edges.

For each endpoint whose IP can be temporally resolved at `event_at`:

```text
site_id + IP + event_at
→ site_id + MAC
```

then, where already authoritative:

```text
site_id + MAC
→ existing device_id
```

Local Device-to-Device flows therefore do not require inventing one endpoint as “the device” and the other as “the Internet”.

---

## 9.3 Binding sources

V1 MUST reuse existing evidence where admitted, such as:

```text
Current State
Registry
Visit Lifecycle
existing DHCP/Fingerprint evidence
existing historical Observation evidence
```

The Network Intelligence lane MUST NOT build an alternate Registry, Visit system, or DHCP product.

Before implementation, a research/admission gate must prove which existing source or combination can establish a trustworthy temporal binding at `event_at`.

No source is silently declared authoritative without that gate.

---

## 9.4 Attribution result

Conceptual contract:

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

Rules:

```text
IP-only permanent identity = FORBIDDEN

cross-MAC merge = FORBIDDEN

ambiguous attribution
→ remains ambiguous

missing attribution
→ does not become another Device

no device_id yet
→ do not drop observation
→ do not invent device_id
```

Pre-Registry observations retain:

```text
Site + MAC attribution
```

and may later be deterministically projected to an authoritative existing `device_id` under the already accepted late-binding principle.

An unbound observation does NOT create a Device Card.

---

# 10. PROTOCOL SUMMARY CONTRACT

Derived product contract:

```text
DeviceProtocolSummaryV1
```

Minimum fields:

```text
site_id
device_id
evaluated_at

window_policy_id
window_start
window_end

recent_protocols[]
last_protocol_observed_at

dominance_status
dominant_protocol_family optional

freshness_state
availability_state

source_generation/version
attribution_status
```

## Recent protocol item

```text
protocol_family
last_observed_at
support_state
supporting_observation_types
```

V1 support states:

```text
directly_observed
deterministically_derived
ambiguous
unknown
unavailable
```

No numerical confidence percentage in V1.

## Dominance

Dominance MUST NOT mean:

```text
most bytes
```

while the traffic-accounting lane is parked.

A dominance field may be enabled only if an independent frozen ranking contract defines a defensible metadata-based basis.

Otherwise:

```text
dominance_status = unavailable
```

---

# 11. SERVICE RECOGNITION CONTRACT

Pipeline:

```text
normalized attributed metadata
        ↓
versioned RecognitionRuleSet
        ↓
ServiceObservationV1
        ↓
DeviceServiceSummaryV1
```

## Inputs allowed in V1

```text
DNS name where visible
SNI where visible
destination endpoint
port/protocol
Suricata app_protocol where semantics are admitted
multiple supporting observations
local/versioned recognition rules
```

## ServiceObservationV1

Minimum:

```text
site_id
device_id
observed_at

organization_id optional
service_id optional
service_category_id optional

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

No arbitrary confidence percentage in V1.

---

# 12. TAXONOMY BOUNDARY

The dimensions are permanently separate:

```text
Infrastructure / Organization
!=
Service
!=
Service Category
```

Examples:

```text
organization = Google
does NOT imply
service = Google Search

organization = Meta
does NOT imply
service = WhatsApp

organization = Cloudflare
does NOT imply
a specific application
```

No single overloaded `service_family` value may collapse the three dimensions.

V1 recognition rules MUST preserve this separation in storage, read model, and UI.

---

# 13. INFRASTRUCTURE / ORGANIZATION CONTEXT

Infrastructure/Organization is primarily a supporting recognition dimension.

Default product surface:

```text
Recent Infrastructure / Organizations
```

It may contain:

```text
organization/provider
last_observed_at
support_state
freshness_state
```

It MUST NOT expose:

```text
remote IP history
raw endpoint timeline
all observed destinations
```

by default.

V1 MUST NOT depend on ASN/IP-ownership external enrichment.

Optional external enrichment remains a separately admitted future dependency.

Absence of external enrichment must not invalidate locally supported service/provider results.

---

# 14. FRESHNESS / STALE / UNAVAILABLE CONTRACT

Freshness is based on network-intelligence evidence.

It MUST NOT reuse Omada Presence/Online as network-intelligence freshness.

## 14.1 Time basis

Use:

```text
event_at
```

for semantic freshness.

Use:

```text
ingested_at
```

for delivery/lag monitoring.

A late old event may update historical evidence but MUST NOT masquerade as current/recent intelligence.

---

## 14.2 Named windows

V1 uses policy-defined named windows:

```text
CURRENT_WINDOW
RECENT_WINDOW
HISTORY_RETENTION
ALLOWED_EVENT_LATENESS
```

Their numeric durations MUST be frozen by the source/freshness admission task from measured Suricata delivery behavior and product requirements before the corresponding product task is implemented.

They MUST NOT be hard-coded ad hoc by Coder.

Required ordering:

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

## 14.3 Presentation states

```text
fresh
recent
stale
unavailable
```

Definitions:

### fresh

At least one qualifying attributed observation exists inside `CURRENT_WINDOW`, and source/attribution coverage is sufficient.

### recent

No qualifying observation is inside `CURRENT_WINDOW`, but qualifying evidence exists inside `RECENT_WINDOW`, and source/attribution coverage is sufficient.

### stale

Known historical result exists, but its last supporting `event_at` is outside `RECENT_WINDOW`.

A stale result MUST NOT be shown as current/recent.

### unavailable

Current source/coverage/attribution is insufficient to make a current/recent statement.

Examples:

```text
Suricata metadata source unavailable
capture health insufficient
Site attribution unresolved
device attribution unresolved
required recognition dependency unavailable
```

`unavailable` is NOT equivalent to `no activity`.

---

## 14.4 Late event

If:

```text
ingested_at - event_at > ALLOWED_EVENT_LATENESS
```

the event is:

```text
late
```

It may enter durable historical observation if otherwise valid.

It MUST be evaluated by `event_at`, not arrival time.

It MUST NOT resurrect:

```text
Fresh Protocol
Recent Service
Current Transport Health
```

if its event time belongs to an older window.

---

# 15. SENSITIVE METADATA / RETENTION BOUNDARY

SensitiveNetworkMetadata includes:

```text
raw DNS names / query history
raw SNI
remote IP history
fine-grained endpoint timelines
```

These do NOT inherit ordinary Device Card presentation rights.

## Logical retention classes

### NI-R0 — raw Suricata transport/EVE

```text
transient / bounded operational transport
not product history
```

### NI-R1 — normalized sensitive endpoint metadata

```text
short retention
restricted engineering/diagnostic access
```

Examples:

```text
raw DNS
raw SNI
raw remote IP
```

### NI-R2 — normalized protocol observations

```text
medium retention
enough for derived summary/rebuild requirements
```

### NI-R3 — derived Device protocol/service summaries

```text
longer product retention
product-safe dimensions preferred
```

### NI-R4 — Transport Health observations/assessments

```text
policy-defined retention
```

Numeric retention days are NOT frozen in this addendum.

Before implementation they require:

```text
cardinality/storage measurement
privacy review
rebuild-dependency closure
```

Permanent rule:

```text
a dependency required to rebuild a retained derived result
must not expire before that derived result's claimed rebuildability.
```

Default Device Card surfaces prefer:

```text
service
service category
organization/provider
protocol summary
aggregates
```

over raw DNS/SNI/IP history.

---

# 16. TRANSPORT HEALTH V1 — INDEPENDENT SUBSET

Transport Health V1 may use only metadata-derived signals that do NOT require periodic traffic buckets.

## Candidate V1 signals

### Tier A — target for admission

```text
DNS failure indicator
last DNS failure observation
DNS result/rcode category
DNS latency where transaction timing is proven
```

### Tier B — admit only after exact Suricata field/fixture proof

```text
TCP reset indicator
failed connection indicator
connection churn
short aborted session indicator
```

If exact source semantics are not proven:

```text
UNAVAILABLE
```

is the correct product result.

## Explicitly forbidden V1 claims

```text
packet-loss percentage
RTT unless independently proven
retransmission percentage
bandwidth quality score
generic "bad Internet"
```

RF metrics:

```text
RSSI
SNR
radio retry/error
```

remain owned by existing Omada/Observation/Wireless Analytics and are not recreated here.

---

# 17. REVISED DEPENDENCY GRAPH

## Old dependency

```text
DTI-06 Protocol Intelligence
        ↓ depended on
DTI-01 + DTI-02 + DTI-03
```

This dependency is superseded for the Network Intelligence lane.

## New dependency

```text
DTI-00 accepted capture/source evidence
        ↓
DTI-NI-00
Suricata Metadata Source + Field Semantics Admission
        ↓
DTI-NI-01
Metadata-Only Network Observation Foundation
        ↓
DTI-NI-02
Temporal Device Attribution
        ↓
DTI-NI-03
Protocol Intelligence + Protocol Device Card
        ↓
DTI-NI-04
Service Recognition
        ↓
DTI-NI-05
Infrastructure / Organization Context
        ↓
DTI-NI-06
Transport Health V1
```

Parallel parked lane:

```text
DTI-03 periodic accounting
DTI-04 traffic summaries
DTI-05 SPAN Traffic MVP
        =
PARKED
```

No arrow exists from parked DTI-03 to:

```text
DTI-NI-03
DTI-NI-04
DTI-NI-05
```

Transport Health signals that genuinely require packet-rate/accounting semantics remain parked/excluded.

---

# 18. RELATIONSHIP TO ORIGINAL DTI-01 / DTI-02

The original conceptual principles remain valid:

```text
normalized durable facts
Site-aware source identity
event time vs ingest time
provenance/versioning
failure isolation
temporal attribution
late identity binding
```

However the ACTIVE Network Intelligence lane implements only the minimum metadata subset needed for protocol/service intelligence.

Therefore:

```text
original broad DTI-01
is NOT a prerequisite as one monolithic traffic+metadata task

original broad DTI-02
is NOT a prerequisite as full traffic-accounting attribution
```

Instead:

```text
DTI-NI-01 =
metadata-only first implementation slice
of the logical Network Observation Foundation

DTI-NI-02 =
metadata-attribution first implementation slice
using the already frozen identity principles
```

Future reopening of the traffic lane may extend the same logical foundation rather than create a parallel competing one.

---

# 19. STAGED IMPLEMENTATION ROADMAP

## DTI-NI-00 — SURICATA METADATA SOURCE & SEMANTICS ADMISSION

**Type:** Research / admission  
**Coder:** HOLD

Goal:

```text
prove exact V1 EVE family configuration and field semantics
without changing the accepted Fingerprint-facing stream
```

Must decide:

```text
flow/dns/tls/quic/stats isolated output contract
event identity semantics
event_at semantics
delivery lag distribution
source health semantics
field/cardinality profile
resource/output volume
privacy impact
```

Output:

```text
SuricataMetadataSourceContractV1
FreshnessPolicyCandidate
EventFieldSemanticMatrix
```

---

## DTI-NI-01 — METADATA-ONLY NETWORK OBSERVATION FOUNDATION

**Type:** implementation after NI-00 PASS

Implement:

```text
NetworkMetadataEnvelopeV1
FlowProtocolObservationV1
DnsObservationV1
TlsObservationV1
QuicObservationV1
NetworkMetadataSourceHealthV1
bounded ingest
provenance/version
retention class enforcement
```

No traffic buckets.

No Device Card yet.

---

## DTI-NI-02 — TEMPORAL DEVICE ATTRIBUTION

**Type:** implementation after attribution-source admission

Implement:

```text
NetworkMetadataAttributionResultV1
temporal Site+IP→Site+MAC resolution
existing device_id binding where available
ambiguous/unattributed states
pre-Registry late-binding path
```

No new Registry.

No cross-MAC merge.

---

## DTI-NI-03 — PROTOCOL INTELLIGENCE + DEVICE CARD P1

Implement:

```text
DeviceProtocolSummaryV1
Recent Protocols
Last Protocol Observation
fresh/recent/stale/unavailable
```

This is the FIRST visible Network Intelligence delivery.

It does NOT wait for Service Recognition or Transport Health.

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
```

Ambiguous/unknown are first-class outcomes.

---

## DTI-NI-05 — INFRASTRUCTURE / ORGANIZATION CONTEXT

Implement/support:

```text
organization/provider dimension
recent organization context
supporting recognition evidence
```

No external ASN/org dependency required for PASS.

No raw IP-list product.

---

## DTI-NI-06 — TRANSPORT HEALTH V1

Implement only admitted metadata-derived signals.

Initial order:

```text
DNS failure/result
DNS latency if proven
then separately proven TCP/flow health indicators
```

No periodic-byte-meter dependency.

---

# 20. PRODUCT DELIVERY SEQUENCE

```text
NI-00 research/admission
        ↓
NI-01 normalized metadata
        ↓
NI-02 attribution
        ↓
NI-03 Protocol Card
        ↓
FIRST NEW USER-VISIBLE VALUE
        ↓
NI-04 Recent Services / Categories
        ↓
NI-05 Infrastructure / Organization
        ↓
DTI-NI-M1 core complete
        ↓
NI-06 Transport Health V1
```

Transport Health may ship incrementally after its own signal-admission gates.

---

# 21. REQUIRED RESEARCH / ADMISSION GATES BEFORE CODER

No Coder authorization is issued by this addendum.

## NI-G1 — Suricata V1 Output Admission

Prove exact isolated/versioned output for:

```text
flow
dns
tls
quic
stats
```

Must prove:

```text
Fingerprint-facing EVE contract unchanged
unexpected DTI events in Fingerprint stream = 0
bounded resource/output growth
no new sustained capture-drop regression
rollback
privacy scope
```

---

## NI-G2 — Event Field Semantics Admission

Using real/controlled fixtures, prove:

```text
event timestamp meaning
flow_id / transaction identity where applicable
src/dst endpoint semantics
transport protocol fields
app_protocol semantics
DNS query/response/result fields
TLS SNI/version/ALPN fields
QUIC visible fields
stats/source-health fields
late-event behavior
```

Do not infer semantics from field names alone.

---

## NI-G3 — Temporal Attribution Authority Admission

Prove the minimum source combination that can answer:

```text
Site + IP + event_at
→ Site + MAC
```

Test:

```text
current IPv4
IP reassignment
ambiguous binding
missing binding
two local Device endpoints
pre-Registry observation
late device_id resolution
IPv6 where evidence permits
```

Outcome must freeze:

```text
binding source authority
validity interval semantics
contradiction handling
late-binding behavior
```

No IP-only permanent identity.

---

## NI-G4 — Freshness Policy Admission

Measure:

```text
Suricata event delivery lag
normal processing/ingest lag
late-event examples
source outage behavior
```

Then freeze numeric:

```text
ALLOWED_EVENT_LATENESS
CURRENT_WINDOW
RECENT_WINDOW
```

before NI-03 product implementation.

Coder MUST NOT choose these values.

---

## NI-G5 — Service Recognition Knowledge Admission

Before NI-04 implementation freeze:

```text
RecognitionTaxonomyContractV1
local/versioned rule format
rule provenance
rule versioning
test corpus
ambiguous/CDN/shared-IP behavior
ECH/no-SNI behavior
provider != service fixtures
```

No unadmitted external enrichment dependency.

---

## NI-G6 — Transport Health Signal Admission

Before each Transport Health signal is product-visible, prove:

```text
exact source fields
event semantics
controlled fixture
false-positive boundary
CaptureQuality dependency
freshness semantics
```

Unsupported signals remain unavailable.

---

# 22. EXISTING FACTS EXPLICITLY NOT REBUILT

The active Network Intelligence lane MUST NOT implement alternate ownership for:

| Existing fact | Existing owner/context | Network Intelligence use |
|---|---|---|
| MAC | Existing Registry / controller/network state | correlation only |
| IP | Current State / controller/network evidence | temporal correlation only |
| SSID | Existing Current State / Omada | context only |
| AP | Existing Current State / Omada | context only |
| Presence / Online | Current State | context only |
| Authorization | Auth / Visit Lifecycle | context only |
| RSSI / SNR | Observation / Wireless Analytics | compose only |
| Radio state/channel | Omada / Observation | compose only |
| Controller device type/platform | Existing controller facts where available | context only |
| Current Guest Traffic | Existing traffic contract | no DTI replacement |
| Historical existing traffic products | Existing Traffic Projection/contracts | no DTI replacement |
| First/last seen | Registry/current product | compose only |
| Visits | Visit Lifecycle | correlation/context only |
| Device identity | Existing Registry identity | consume only |
| Device Fingerprint | authoritative persisted ClassificationResult | compose only |

Permanent:

```text
Network Intelligence adds NEW semantic dimensions.
It does not win by copying existing fields.
```

---

# 23. DEVICE CARD READ-MODEL PRINCIPLE

The Device Card MUST consume a derived read model.

Conceptual:

```text
DeviceNetworkIntelligenceReadModelV1
```

It composes:

```text
DeviceProtocolSummaryV1
DeviceServiceSummaryV1
OrganizationContextSummaryV1
TransportHealthSummaryV1
freshness / source availability
```

The UI MUST NOT:

```text
read raw EVE
read raw DNS history
read raw SNI history
scan remote IP history
perform recognition rules
perform temporal IP→MAC attribution
```

---

# 24. FAILURE ISOLATION

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

If Suricata DTI metadata output or NI ingest is unavailable:

```text
Network Intelligence
→ stale / unavailable
```

not:

```text
protocol = none
service = none
device offline
traffic = zero
```

Retained older intelligence may remain visible only as:

```text
stale historical result
```

with `last_observed_at`.

---

# 25. SUPERSESSION / PRESERVATION RULE

This addendum supersedes ONLY these parts of the previous execution ordering:

```text
DTI-06 requiring DTI-03
DTI-07 being operationally blocked by DTI-03
DTI-08 metadata-safe subset requiring DTI-03
first product milestone being DTI-00→05 traffic-first
```

It does NOT supersede accepted v0.3 principles for:

```text
DTI != Device Fingerprint
DTI != Authorization/CAPPORT

Site-aware evidence
no IP-only permanent identity
no cross-MAC merge
late authoritative device_id binding
metadata over payload
SensitiveNetworkMetadata restriction
organization != service != category
source/provenance/versioning
event time != ingest time
conservative unavailable semantics
failure isolation
one product metric → one semantic owner
```

---

# 26. REVIEW DECISIONS REQUESTED

Owner + Tech Lead review should explicitly decide:

```text
A. NETWORK INTELLIGENCE reprioritization =
ACCEPT / REJECT

B. PERIODIC TRAFFIC METER LANE =
PARKED / REOPEN

C. DTI-NI-M1 product target =
ACCEPT / REVISE

D. V1 Suricata families =
flow + dns + tls + quic + stats
ACCEPT / REVISE

E. metadata-only foundation independent from DTI-03 =
ACCEPT / REJECT

F. temporal attribution contract =
ACCEPT / REVISE

G. freshness contract =
ACCEPT / REVISE

H. service/provider/category taxonomy =
ACCEPT / REVISE

I. Transport Health V1 conservative subset =
ACCEPT / REVISE

J. staged roadmap DTI-NI-00..06 =
ACCEPT / REVISE
```

---

# 27. CURRENT AUTHORIZATION STATE

```text
ARCHITECTURE ADDENDUM =
DRAFT FOR OWNER + TECH LEAD REVIEW

PERIODIC TRAFFIC METER =
PARKED

DTI-03 =
PARKED

DTI-04 =
PARKED

DTI-05 SPAN TRAFFIC MVP =
PARKED

NETWORK INTELLIGENCE LANE =
PROPOSED ACTIVE PRIORITY

CODER =
HOLD

SYSADMIN EXECUTION =
NOT AUTHORIZED BY THIS ADDENDUM

PRODUCTION =
NO CHANGE

NEXT =
OWNER + TECH LEAD REVIEW
→ if accepted:
Architect issues exact DTI-NI-00 research/admission contract
→ only after required gates:
task-specific Coder contracts
```
