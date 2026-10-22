# DEVICE-TRAFFIC-ENRICHMENT-ARCHITECTURE-v0.3

**Project:** CaptivPortal  
**Program prefix:** `DTI` — Device Traffic Intelligence  
**Status:** `DRAFT — TECHLEAD TL-R1..TL-R20 INCORPORATED / FINAL BOUNDED REVIEW PENDING`  
**Architecture:** YES  
**Roadmap:** YES  
**Implementation:** NO  
**Coder task:** NO  
**Production change:** NO

## Review disposition

```text
SOURCE REVIEW =
TECH LEAD REVIEW — DEVICE-TRAFFIC-ENRICHMENT-ARCHITECTURE-v0.1

ARCHITECTURE CORE =
PASS

ROADMAP DIRECTION =
PASS

REDESIGN REQUIRED =
NO

INCORPORATED =
TL-R1 ... TL-R20

ROADMAP SEQUENCE CHANGE =
NO

CODER =
HOLD

PRODUCTION =
NO CHANGE
```

This v0.3 is a bounded refinement of v0.2. It incorporates only TL-R16..TL-R20 on top of the already accepted TL-R1..TL-R15 set. It does not redesign the accepted DTI program, change roadmap sequence, or authorize implementation.

---

# 1. ARCHITECTURE DISPOSITION

```text
INITIATIVE =
ACCEPT WITH ARCHITECTURE REFINEMENT

DEVICE-FINGERPRINT SEMANTICS CHANGE =
NO

TASK-DEVICE-FINGERPRINT-06 EXPANSION =
NO

AUTHORIZATION / CAPPORT EFFECT =
NO

AUTOMATIC OMADA ACTIONS =
NO

RAW PACKET SURVEILLANCE SYSTEM =
NO
```

`Device Traffic Enrichment / Device Intelligence` становится отдельной программой CaptivPortal.

Она отвечает не на:

```text
WHAT IS THIS DEVICE?
```

Это остаётся зоной Device Fingerprint.

Она отвечает на:

```text
HOW IS THIS DEVICE USING THE NETWORK?
WHEN?
HOW MUCH?
WHICH NETWORK PROTOCOLS?
WHICH LIKELY SERVICE FAMILIES?
HOW HEALTHY IS THE TRANSPORT?
HOW DID ITS NETWORK BEHAVIOR CHANGE?
ARE THERE ADVISORY ANOMALIES?
```

---

# 2. FUNDAMENTAL DATA PRINCIPLE

Постоянный поток:

```text
PACKETS / CONTROLLER FACTS
        ↓
SOURCE OBSERVATIONS
        ↓
NORMALIZED DURABLE FACTS
        ↓
IDENTITY / TIME CORRELATION
        ↓
DERIVED / REBUILDABLE INTELLIGENCE
        ↓
DEVICE NETWORK READ MODEL
        ↓
DEVICE CARD / ANALYTICS
```

Запрещён целевой поток:

```text
Device Card
    ↓
raw packet / PCAP / EVE / flow scan
    ↓
ad-hoc interpretation
```

UI ничего не классифицирует и не анализирует самостоятельно.

---

# 3. SOURCE-OF-TRUTH OWNERSHIP

Для каждого класса данных остаётся свой владелец.

| Domain | Authoritative source |
|---|---|
| Device identity / Registry identity | Existing CaptivPortal Registry / identity contracts |
| Physical Visit | Visit Lifecycle |
| Device fingerprint identity | Persisted authoritative `ClassificationResult` |
| Current controller/AP/client state | Current State |
| Historical Omada measurements | Observation Foundation |
| RF / RSSI / SNR analytics | Existing Observation + Wireless Analytics |
| Network/AP Historical Traffic | Existing Traffic Projection |
| Packet-observed device traffic | NEW DTI Network Observation Foundation |
| Packet protocol metadata | NEW DTI normalized network observations |
| Service-family recognition | NEW versioned DTI recognition layer |
| Transport-quality assessment | NEW DTI quality layer |
| Behavior profile | NEW derived DTI layer |
| Security/anomaly signal | NEW advisory DTI layer |

There shall be no competing:

```text
Device Card fingerprint classifier
Traffic classifier for device_class
UI classifier
```

## 3.1 DTI vs Existing Traffic Ownership Matrix

CaptivPortal already has existing traffic semantic owners:

```text
CurrentTrafficReadService
CurrentGuestTrafficReadService
HistoricalTrafficReadService
CompletedGuestSessionTrafficReadService
```

DTI creates a different evidence domain:

```text
packet/SPAN-observed device traffic
```

Permanent invariant:

```text
CONTROLLER / OBSERVATION TRAFFIC
!=
DTI PACKET-OBSERVED TRAFFIC
```

DTI MUST NOT silently:

```text
replace existing Current Guest Traffic with a DTI value
mix both values
average both values
choose whichever is larger
call both values one authoritative metric
```

Until a separate future reconciliation contract exists, DTI product naming is source-specific:

```text
Observed Network Traffic (SPAN)
```

Existing traffic products retain their current semantic ownership and naming.

If a Device Card has both an existing traffic value and a DTI value, the UI MUST either:

```text
show them separately with provenance
```

or use only the source explicitly declared by the frozen contract for that field.

### Traffic ownership matrix

| Product metric/domain | Canonical semantic owner | Other sources |
|---|---|---|
| Current controller/AP traffic | Existing Current Traffic contract | DTI may cross-check only |
| Current authorized guest traffic | Existing Current Guest Traffic contract | DTI may cross-check only |
| Historical Observation/AP traffic | Existing Historical Traffic / Traffic Projection contract | DTI may cross-check only |
| Completed guest-session traffic under existing product semantics | Existing Completed Guest Session Traffic contract | DTI may cross-check only |
| Packet/SPAN-observed per-device traffic | DTI Traffic Accounting contract | Omada/NetFlow may cross-check only |
| DTI protocol/service activity | DTI normalized observation + recognition contracts | Existing traffic products are not alternate owners |

Permanent rule:

```text
ONE PRODUCT METRIC
→ ONE SEMANTIC OWNER
```

Other sources may be:

```text
cross-check
diagnostic
supporting evidence
```

but are not competing calculators for the same product number.

Source failover is allowed only when the SAME frozen metric contract explicitly defines the alternate source, its equivalence semantics, and failover conditions.

---

# 4. MAJOR NEW ARCHITECTURE DECISION:
# NETWORK OBSERVATION FOUNDATION

Не создавать отдельный parser/collector для каждой будущей UI-функции.

Целевая модель:

```text
                         SPAN / RSPAN
                              │
                 ┌────────────┴────────────┐
                 │                         │
         sensor adapters             protocol engine
                 │                         │
                 └────────────┬────────────┘
                              ↓
                 NORMALIZED NETWORK EVIDENCE
                              ↓
                  NETWORK OBSERVATION STORE
                              ↓
        ┌─────────────┬────────────┬──────────────┐
        ↓             ↓            ↓              ↓
     Traffic       Protocol      Quality       Security
   Accounting     Intelligence  Intelligence   Signals
        │             │            │              │
        └─────────────┴──────┬─────┴──────────────┘
                             ↓
                    Correlation / Read Models
                             ↓
                         Device Card
```

Один capture source может иметь несколько специализированных consumers, но не пять независимых семантических интерпретаций одного пакета.

---

# 5. SENSOR RESPONSIBILITY DECISION

## 5.1 Existing custom fingerprint sensor

Сохраняет свою существующую область:

```text
DHCP fingerprint evidence
TCP SYN fingerprint evidence
existing source-health
existing Device Fingerprint contracts
```

Его frozen Device Fingerprint semantics не расширяются молча.

---

## 5.2 Suricata

Архитектурное направление:

```text
Suricata =
GENERAL NETWORK METADATA PRODUCER
```

а не только fingerprint helper.

Потенциальные consumers:

```text
Fingerprint
Protocol Intelligence
DNS Intelligence
TLS Intelligence
QUIC Intelligence
Security Signals
Service Recognition inputs
```

Но:

```text
Suricata EVE != product database
Suricata EVE != Device Card API
```

Между EVE и продуктом обязательно существует normalizer/versioned contract.

### 5.2.1 Fingerprint Sensor Coexistence Boundary

The already accepted Device Fingerprint Suricata path is protected.

```text
DTI MUST NOT broaden or mutate the admitted
fingerprint-suricata.service configuration in place
without a separate compatibility/admission decision.
```

DTI-00 MUST select and prove one topology:

```text
A. reuse the same Suricata process with an additional
   versioned output proven not to change Fingerprint behavior;

B. use a separate DTI Suricata instance;

C. use another explicitly proved fan-out arrangement.
```

Until that decision is accepted, Coder MUST NOT simply enable additional DNS/HTTP/flow outputs in the existing fingerprint Suricata configuration.

The coexistence review MUST include effects on:

```text
functional output
CPU
RAM
capture drops
capture timing
source-health behavior
```

---

## 5.3 Lightweight Traffic Meter

Для traffic accounting отдельно предусматривается возможность специализированного лёгкого collector:

```text
packet headers
    ↓
bounded in-memory flow/accounting state
    ↓
periodic normalized traffic slices
```

Причина: terminal flow events могут быть недостаточны для:

```text
current rate
current activity
accurate visit boundaries
long-lived flow accounting
```

Поэтому Suricata НЕ фиксируется как единственный источник traffic byte accounting.

Это должно быть доказано в Phase 0.

---

## 5.4 Zeek

```text
BASELINE COMPONENT =
NO
```

Zeek допускается как Phase-0 research candidate только если будет доказан функциональный gap, который нельзя разумно закрыть:

```text
existing sensor
+
Suricata
+
lightweight accounting collector
```

Не ставить второй тяжёлый full-traffic parser просто потому, что он существует.

---

## 5.5 Existing NetFlow / nfdump

Может использоваться как:

```text
cross-check
network-level aggregate
diagnostic evidence
```

Но НЕ как основной device identity source.

Причина:

```text
no reliable L2/MAC identity timeline
possible different observation point
```

---

# 6. NEW MANDATORY FOUNDATION:
# CAPTURE QUALITY / COMPLETENESS

Любое traffic число бессмысленно без понимания качества захвата.

Вводится отдельное понятие:

```text
CaptureQuality
```

Минимально должно учитывать:

```text
sensor alive
capture interface alive
capture drops
kernel drops where observable
parser drops
ingest drops
ingest lag
SPAN source/direction identity
capture topology identity
duplicate/mirrored-frame handling
clock health
```

Result semantics должны поддерживать минимум:

```text
usable
partial
stale
unavailable
unknown
```

Точное naming фиксируется в отдельном ТЗ.

Критический инвариант:

```text
sensor process alive
!=
capture complete
```

И:

```text
zero observed traffic
!=
zero real traffic
```

если capture quality не доказан.

Traffic Enrichment не является billing-grade accounting system без отдельного будущего доказательства.

---

# 7. NEW MANDATORY FOUNDATION:
# NETWORK ADDRESS BINDING TIMELINE

Запрещено:

```text
IP address → device
```

без временной привязки.

Нужен отдельный Site-scoped temporal contract:

```text
NetworkAddressBindingTimeline
```

Концептуально:

```text
site_id
MAC
IP family
IP address
valid_from
valid_to / open
source
provenance
binding authority/status
observed_at
```

Источники должны быть исследованы отдельно:

```text
DHCP
ARP
IPv6 ND
DHCPv6 where applicable
Omada Current State
Omada Observation
other proved network evidence
```

Никакой источник заранее не объявляется абсолютным без Phase-2 validation.

Требуется поддержка:

```text
IPv4
IPv6
temporary IPv6
multiple simultaneous addresses
IP reassignment
DHCP renewal
address reuse
ambiguous binding
```

## 7.1 Attribution Quality / Coverage

`CaptureQuality` answers:

```text
how well did we observe the traffic?
```

Per-device accounting requires an independent question:

```text
how much of the observed traffic could be safely attributed
to the intended Site + device identity?
```

`FlowAttributionResult` MUST support explicit non-success states conceptually such as:

```text
resolved
ambiguous
unattributed
invalid
```

Exact enum is frozen in TASK-DTI-02.

Permanent invariants:

```text
ambiguous traffic
MUST NOT be silently assigned to a device

unattributed traffic
MUST NOT silently disappear while a result is called complete
```

Device/day/Visit summaries MUST carry at least:

```text
capture_quality
attribution_coverage/status
```

A complete per-device traffic result is allowed only when BOTH are sufficient.

```text
CaptureQuality = sufficient
```

does NOT imply:

```text
Device Traffic = complete
```

if observed flows cannot be safely attributed.

---

# 8. IDENTITY RULES

Primary network identity boundary:

```text
site_id + MAC
```

Далее, где доказуемо:

```text
site_id + MAC
    ↓
existing device_id
    ↓
existing visit_id
```

Traffic Intelligence:

- НЕ создаёт новый `device_id`;
- НЕ создаёт новый Visit;
- НЕ объединяет MAC автоматически;
- НЕ использует fingerprint similarity для cross-MAC identity;
- НЕ объявляет private/random MAC новым физическим устройством или тем же физическим устройством без отдельной identity authority.

V1:

```text
CROSS-MAC DEVICE MERGE =
FORBIDDEN
```

## 8.1 Pre-Registry Observation / Late Identity Binding

DTI network observations MAY exist for an admitted:

```text
site_id + MAC
```

before the existing CaptivPortal Registry has an authoritative `device_id`.

This is a normal lifecycle state, not an ingestion error.

Conceptual state:

```text
UNBOUND / NOT-YET-REGISTRY-RESOLVED OBSERVATION
```

Permanent rules:

```text
no device_id yet
!=
drop the traffic
!=
invent device_id
```

DTI MUST retain otherwise valid Site+MAC observations according to the accepted retention policy when Registry identity is not yet available.

DTI MUST NOT create a substitute `device_id`, substitute Device record, substitute Visit, or parallel identity namespace.

If the existing authoritative CaptivPortal identity later resolves:

```text
site_id + MAC
        ↓
authoritative existing device_id
```

DTI MAY deterministically late-bind / re-project the already retained eligible Site+MAC observations to that authoritative identity.

Late binding:

```text
MUST NOT rewrite the original observation identity
MUST retain correlation/projection lineage
MUST use the accepted temporal/site identity contract
MUST NOT perform cross-MAC identity inference
```

An unbound observation alone does NOT authorize creation of a Device Card.

Exact mechanics are frozen in:

```text
TASK-DTI-02
→ identity/binding resolution state and late-correlation rules

TASK-DTI-04
→ deterministic projection/rebuild of retained observations
   after authoritative device_id becomes available
```

---

# 9. MULTI-SITE PRINCIPLE

Вся новая persistence должна быть Site-aware.

Запрещено:

```text
MAC → traffic
MAC → services
MAC → behavior
```

как глобальный namespace.

Минимальная граница:

```text
site_id + ...
```

Site и future Tenant остаются разными понятиями.

## 9.1 Capture Scope → Site Authority

A sensor producer is NOT allowed to assign arbitrary `site_id`.

DTI requires a proved mapping:

```text
capture source / interface / VLAN / topology scope
                    ↓
                   Site
```

Conceptual contract:

```text
CaptureScopeBinding
```

It MUST establish:

```text
which capture source is authorized to emit evidence for which Site
which interface/VLAN/topology scope belongs to that Site
which source identity and topology identity are admitted
what happens when the scope is ambiguous or unknown
```

Permanent rule:

```text
UNKNOWN OR AMBIGUOUS SITE ATTRIBUTION
→ MUST NOT BE GUESSED
```

Evidence with unresolved Site scope cannot enter a Site-specific per-device product result as if attribution were proven.

---

# 10. DIRECTION SEMANTICS

Все traffic directions в product layer задаются:

```text
FROM CLIENT PERSPECTIVE
```

То есть:

```text
upload
download
```

нельзя механически приравнять к parser-specific:

```text
toserver
toclient
src
dst
```

Нужен доказанный client endpoint через:

```text
Site
+
guest scope
+
MAC/IP binding
+
flow endpoint
```

---

# 11. TRAFFIC BYTE SEMANTICS

До реализации обязательно заморозить, что означает:

```text
bytes
```

Нельзя молча смешивать:

```text
L2 frame bytes
IP bytes
transport bytes
application payload bytes
Omada traffic counters
Suricata flow bytes
NetFlow bytes
```

Предварительное product naming:

```text
Observed Network Traffic
```

а не:

```text
Downloaded Content
```

пока точная accounting basis не доказана.

Также требуется определить:

```text
retransmitted bytes
duplicate mirrored packets
fragmentation
partial flows
flows already active at capture start
flows ending after capture stop
```

## 11.1 TrafficAccountingScope

Before DTI-03 implementation, the accounting contract MUST freeze which observed network path classes enter each product total.

Minimum scope classes:

```text
unicast
broadcast
multicast
link-local
local Site/LAN traffic
gateway/control traffic
Internet-bound traffic
```

Examples that MUST receive explicit semantics:

```text
client → DHCP broadcast
client → mDNS multicast
multicast frame visible on SPAN
guest → local gateway DNS
guest → another local client
guest → Internet
ARP
IPv6 ND
ICMP/control traffic
```

Permanent rule:

```text
one mirrored multicast/broadcast frame
DOES NOT automatically become download bytes
for every client that might have received it
```

DTI MUST distinguish:

```text
observed packet/path class
from
per-device attributable accounting
```

`TrafficAccountingScope` MUST define for every admitted class whether it is:

```text
included in Observed Network Traffic (SPAN)
reported separately
excluded from a specific product metric
or not safely attributable
```

Default architecture meaning:

```text
Observed Network Traffic (SPAN)
IS NOT automatically Internet-only traffic.
```

The product MUST NOT be described as:

```text
Internet usage
WAN usage
downloaded Internet data
```

unless a later frozen metric contract separately proves and defines an Internet-only scope.

TASK-DTI-03 MUST freeze the exact scope table and multicast/broadcast attribution behavior before implementation.

---

# 12. TIME CONTRACT

Network telemetry MUST distinguish source/event time from delivery time.

Conceptually:

```text
captured_at / event_at
ingested_at
processed_at where required
source sequence / ordering identity
ingest lag
clock-health provenance
```

Exact field names are deferred, but the distinction is architectural and mandatory.

Permanent rule:

```text
CURRENT ACTIVITY / VISIT CORRELATION / FRESHNESS
use accepted event/capture time semantics,
not merely ingest arrival time.
```

Therefore:

```text
old event delivered late
!=
current activity
```

New network observations use:

```text
UTC internally
```

Analytics intervals:

```text
[from_utc, to_utc)
```

User-facing:

```text
Today
Yesterday
day boundaries
```

are calculated by Site timezone.

Host timezone is not business-time authority.

---

# 13. CAPABILITY MATRIX v0.2

Status meanings:

```text
AVAILABLE
directly observable in principle from admitted mirror position,
subject to implementation and capture-quality validation

PARTIAL
observable only partially or dependent on encryption/correlation

UNRELIABLE
possible inference exists but not suitable as normal product truth

NOT AVAILABLE
SPAN alone cannot supply it, or architecture forbids it
```

| Capability | SPAN status | Preferred source | Key limitation | Priority |
|---|---|---|---|---|
| L3/L4 endpoints | AVAILABLE | Traffic Meter / parser | capture quality | P0 |
| packets/bytes | AVAILABLE | Traffic Meter | exact byte basis/dedup required | P0 |
| upload/download | PARTIAL until binding proven | Meter + Binding Timeline | endpoint attribution | P0 |
| current activity | AVAILABLE | periodic traffic slices | freshness required | P0 |
| current traffic rate | AVAILABLE | periodic traffic slices | bucket/cadence proof | P0 |
| flow count | AVAILABLE | flow/accounting | flow definition required | P0 |
| TCP connections | AVAILABLE | flow/accounting | asymmetric capture | P1 |
| UDP activity | AVAILABLE | flow/accounting | no true connection semantics | P1 |
| activity duration | PARTIAL | flow/accounting | idle timeout semantics | P1 |
| plaintext DNS | PARTIAL | Suricata/parser | DoH/DoT/VPN | P1 |
| NXDOMAIN/failures | PARTIAL | DNS observations | encrypted DNS invisible | P1 |
| DNS latency | PARTIAL | query/response correlation | capture loss | P1 |
| TLS version | PARTIAL | Suricata | only visible handshake metadata | P1 |
| TLS SNI | PARTIAL | Suricata | ECH/missing SNI | P1 |
| ALPN | PARTIAL | Suricata | handshake visibility | P1 |
| certificate metadata | PARTIAL | Suricata | privacy/retention | P2 |
| QUIC version/metadata | PARTIAL | Suricata | encrypted payload | P1 |
| HTTP plaintext protocol | PARTIAL | parser | HTTPS dominates | P2 |
| HTTP content/body | NOT AVAILABLE / NOT ALLOWED | none | privacy + encryption | NEVER |
| mDNS | PARTIAL | protocol parser | local multicast scope | P2 |
| SSDP | PARTIAL | protocol parser | parser validation required | P2 |
| STUN/TURN | PARTIAL | protocol parser | app identity not implied | P2 |
| NTP | AVAILABLE/PARTIAL | protocol parser | simple metadata only | P2 |
| ICMP | AVAILABLE | meter/parser | semantics vary | P2 |
| ARP | AVAILABLE | binding layer | spoofing/authority caveat | P0/P1 |
| IPv6 ND | AVAILABLE | binding layer | temporary addresses | P0/P1 |
| VPN/tunnel presence | PARTIAL | protocol/flow rules | encrypted inner traffic hidden | P2 |
| exact inner VPN services | NOT AVAILABLE | none | tunnel encryption | NO |
| service family | PARTIAL | versioned recognition | inference only | P1 |
| exact application | UNRELIABLE | multiple metadata signals | CDN/shared infra/ECH | P3 |
| ASN/org | NOT AVAILABLE from SPAN alone | external enrichment DB | external governance | P2 |
| geographic destination | PARTIAL external inference | GeoIP-style source | endpoint location ≠ user | P3 |
| TCP retransmission indicators | PARTIAL | transport parser | capture loss biases result | P1 |
| TCP reset behavior | AVAILABLE/PARTIAL | transport parser | context needed | P1 |
| SYN failures | PARTIAL | transport parser | incomplete capture | P1 |
| passive RTT | PARTIAL/UNPROVEN | transport analysis | asymmetric paths/capture | P2 |
| Wi-Fi RSSI/SNR | NOT AVAILABLE from SPAN | Omada Observation/Current State | controller source | existing |
| radio retries/airtime | NOT AVAILABLE from SPAN | Omada/controller | separate wireless truth | existing |
| behavior profile | PARTIAL after history exists | derived analytics | descriptive only | P2 |
| network behavior role | UNRELIABLE initially | derived analytics | must not replace device_class | P3 |
| scan/fan-out signals | PARTIAL | flow/security analytics | false positives | P2 |
| known malicious IOC | NOT AVAILABLE from SPAN alone | external TI | licensing/freshness/FP | P3 |
| user content/messages | NOT AVAILABLE / FORBIDDEN | none | product boundary | NEVER |

---

# 14. EXISTING TRAFFIC PROJECTION RELATIONSHIP

Existing Traffic Projection remains:

```text
Observation
    ↓
derived historical network/AP traffic projection
```

It is NOT repurposed into:

```text
packet flow storage
device network evidence DB
DNS/TLS/QUIC store
```

What MAY be reused:

```text
versioned projection pattern
derived/disposable storage model
rebuild semantics
health semantics
read-service pattern
bounded reconciliation
```

What is NOT reused automatically:

```text
schema
source meaning
traffic semantics
retention values
```

---

# 15. EXISTING WIRELESS ANALYTICS RELATIONSHIP

Existing controller-derived:

```text
RSSI
SNR
client traffic counters
AP/radio rates
retry/drop/error counters
```

remain their own evidence family.

DTI does not recreate them from SPAN.

Target Device Card may compose:

```text
Wi-Fi / Controller Quality
+
Packet-observed Transport Quality
```

but must display them as separate evidence types.

V1 SHOULD NOT create one opaque:

```text
Network Health Score = 87
```

---

# 16. DATA MODEL — ARCHITECTURAL CLASSES

Exact schemas are deferred to individual implementation TЗ.

## 16.1 Normalized durable observations

Conceptual classes:

```text
CaptureHealthObservation

NetworkFlowSlice
NetworkAddressBindingObservation

ProtocolObservation
DnsObservation
TlsObservation
QuicObservation

TransportSignalObservation

SensorSecurityObservation
```

These are facts/observations.

No business-level service claim belongs inside a raw flow observation.

---

## 16.2 Derived/versioned intelligence

```text
FlowAttribution

ServiceObservation
DestinationEnrichment

DeviceActivityInterval

NetworkQualityAssessment
SecuritySignal

VisitNetworkSummary
DeviceNetworkSummary
DeviceCurrentNetworkState

BehaviorProfile
DeviceNetworkChangeEvent
```

These must be rebuildable from their retained dependencies wherever retention permits.

---

# 17. STORAGE OWNERSHIP

Logical ownership is frozen now; physical DB engine is NOT.

Proposed logical stores:

```text
Network Observation Store
Device Network Projection Store
Recognition Knowledge Store
```

Important:

```text
DO NOT put general high-volume flow telemetry
into Device Fingerprint Task-01 DB.
```

Fingerprint evidence and high-volume network telemetry have different:

```text
retention
cardinality
query pattern
consumer set
failure semantics
```

Physical storage choice:

```text
SQLite preferred only if Phase-0/Phase-1
capacity benchmark proves it safely bounded.
```

If not, alternative storage needs separate architecture review.

No premature DB technology change.

---

# 18. RETENTION CLASSES

Exact durations are intentionally NOT frozen in v0.1.

### R0 — Packet payload

```text
durable retention = NONE by default
```

No indefinite PCAP.

Diagnostic PCAP requires separate explicit Owner authorization.

### R1 — Parser transport/raw EVE

```text
transient / bounded operational use
```

Not permanent product history.

### R2 — Normalized network observations

```text
medium retention
```

Exact days require Phase-0 storage measurements.

### R3 — Address binding timeline

Must remain long enough to safely attribute every retained observation that may be rebuilt.

Invariant:

```text
binding evidence needed for rebuild
must not expire before dependent observation
```

### Rebuild dependency closure

The same retention rule applies to every dependency required for deterministic rebuild.

A rebuildable derived result may depend on:

```text
normalized observations
CaptureQuality evidence
NetworkAddressBindingTimeline
CaptureScopeBinding / topology identity
recognition rules or policy version
other explicitly frozen correlation dependencies
```

Permanent invariant:

```text
required rebuild dependency
MUST remain available for at least as long as the retained
source observations/results that claim deterministic rebuildability.
```

If a mandatory dependency has expired or is unavailable:

```text
projection MUST NOT claim deterministic rebuildability
```

The affected result must expose the appropriate unavailable/partial/not-rebuildable semantics defined by its task contract.

### R4 — Visit summaries

```text
long retention
```

### R5 — Device aggregate history

```text
long retention
```

### R6 — Security advisory signals

Policy-defined retention.

---

# 19. PRIVACY / MINIMIZATION

Default:

```text
METADATA OVER PAYLOAD
```

Do not persist by default:

```text
full PCAP
HTTP bodies
message contents
credentials
cookies
authorization headers
URL query strings
form data
full arbitrary HTTP headers
raw application payload
```

Special care:

```text
DNS names
SNI
destination IP
```

are metadata but may still reveal sensitive activity.

Therefore:

- raw endpoint/domain history gets shorter retention;
- product-facing long-term history prefers service families/categories and aggregates;
- detailed remote endpoint lists belong to restricted diagnostics, not default Device Card;
- service recognition never implies inspected content.

## 19.1 SensitiveNetworkMetadata Access Boundary

The following are treated as conceptually sensitive network metadata:

```text
raw domain names / DNS query history
raw SNI history
remote IP history
fine-grained endpoint timelines
other similarly identifying network metadata
```

`SensitiveNetworkMetadata` MUST NOT automatically inherit the same presentation/access policy as ordinary Device Card aggregates.

Before DTI-06/DTI-07 expose such data, their implementation contracts MUST freeze:

```text
default Device Card visibility
engineering diagnostic visibility
authorization/capability requirement
Site scope
retention class
audit expectations where appropriate
```

Default product principle:

```text
long-term product-facing surfaces
PREFER
service / service category / aggregates
OVER
raw domain lists / raw SNI lists / remote-IP history
```

Raw sensitive metadata may be exposed only through an explicitly authorized diagnostic capability.

Exact RBAC/capability names are deferred to the corresponding implementation task.

---

# 20. SERVICE RECOGNITION CONTRACT

Pipeline:

```text
normalized observations
        ↓
versioned recognition rules
        ↓
supported service inference
```

Every result must retain:

```text
observed_at
rule/version
supporting signal types
source/provenance
resolution status
```

No arbitrary numeric confidence percentage in V1 unless calibrated.

Prefer semantic support states such as:

```text
directly_supported
multi_signal_supported
ambiguous
unknown
unavailable
```

Exact enum deferred to its TЗ.

Important:

```text
Google-owned endpoint
!=
Google Search

Cloudflare/CDN endpoint
!=
specific application
```

## 20.1 Recognition Taxonomy Contract

Recognition MUST keep distinct dimensions separate.

Minimum conceptual taxonomy:

```text
Infrastructure / Organization
    Google
    Cloudflare
    Meta

Service
    YouTube
    WhatsApp
    Netflix

Service Category
    streaming
    messaging
    cloud storage
```

Permanent rule:

```text
organization/provider
!=
service
!=
service category
```

Example:

```text
Google endpoint
→ organization/provider = Google

does NOT imply
→ service = Google Search
```

No single overloaded `service_family` field may collapse all three dimensions.

TASK-DTI-07 MUST freeze an explicit `RecognitionTaxonomyContract` before implementation.

---

# 21. CURRENT ACTIVITY FRESHNESS

The product concept is explicitly named:

```text
Network Activity
```

to avoid collision with Presence / Online / Authorization state.

DTI `Active` means:

```text
qualifying network traffic for this device
was observed within the accepted freshness window
under sufficient capture and attribution conditions.
```

It does NOT mean:

```text
Wi-Fi client online
authorized
physically present
current Omada presence
```

`Idle` is permitted only when ALL are true:

```text
CaptureQuality sufficient
+
device attribution sufficient
+
fresh observation window fully covered
+
no qualifying device traffic observed in that window
```

Otherwise the result is:

```text
Unknown / Unavailable
```

rather than `Idle`.

Network Activity must explicitly support freshness.

Conceptual output:

```text
evaluated_at
last_observed_at
age
freshness_state
```

Minimum semantics:

```text
fresh
stale
unavailable
```

No old event delivered late, and no yesterday's protocol/service, may appear as current Network Activity.

Exact freshness thresholds are measured/frozen later.

---

# 22. DEVICE CARD TARGET MODEL

## Default-visible

```text
Identity
  existing fingerprint summary
  first/last seen
  visit count

Network Activity
  active / idle / unavailable
  current observed rate
  last network activity
  dominant protocol family
  likely service + support state

Traffic
  Observed Network Traffic (SPAN)
  current Visit
  today
  7 days
  download/upload
  peak observed rate

Network Quality
  Wi-Fi signal from controller
  transport health from SPAN
  recent significant issue

Security
  advisory signals observed
  OR no advisory signals observed with sufficient coverage
  OR insufficient coverage / unavailable
```

## Expandable detail

```text
24h / 30d traffic
protocol distribution
service categories
DNS summary
TLS/QUIC summary
connection counts
remote organization/ASN summary
Visit-level network summaries
network issue timeline
behavior changes
```

## Engineering/debug only

```text
raw flow identities
raw remote IP list
exact parser source records
recognition-rule provenance
capture quality internals
binding evidence
drop/reconcile diagnostics
```

---

# 23. HISTORY MODEL

History is append/derive, not historical rewrite.

```text
normalized observation
    ↓
time correlation
    ↓
Visit summary
    ↓
day/window summary
    ↓
Device lifetime aggregate
```

Original observations are not rewritten merely because a later model becomes smarter.

A later recognition ruleset may produce:

```text
new derived projection/version
```

without mutating the original observation.

## 23.1 Derived Intelligence Version Lineage

Every rebuildable derived result MUST allow an auditor to determine, conceptually:

```text
input observation generation / covered range
capture/topology generation where relevant
binding/correlation contract version
recognition/policy version where relevant
derived algorithm/version
evaluated_at / generated_at
```

When rules or algorithms change:

```text
old observation is not rewritten
old derived generation may remain audit-visible
new generation becomes current only through explicit projection semantics
```

A newer model MUST NOT silently relabel an old result as if it had been produced by the older generation.

---

# 24. VISIT CORRELATION

A flow may:

```text
start before Visit
continue through Visit
finish after Visit
```

Therefore simple:

```text
flow end timestamp belongs to Visit
```

is forbidden.

Traffic accounting must support time slicing/bucketing sufficiently to attribute overlap.

Exact bucket size/cadence is deferred to Phase 0/3.

Visit summary only includes traffic attributable to the Visit according to its frozen temporal contract.

## 24.1 Traffic Population / Authorization Boundary Contract

SPAN may observe a device before authorization.

DTI therefore freezes three distinct populations:

```text
1. Device-observed traffic
2. Visit-authorized traffic
3. Current Visit traffic
```

### Device-observed traffic

For a Site + device + requested time window, this means all safely attributed DTI packet-observed traffic that satisfies the DTI accounting contract, regardless of whether the device was already authorized.

Therefore:

```text
Device Today Traffic
INCLUDES safely attributed pre-auth / captive traffic
within the Site-local Today window.
```

This is why the product is source-specific `Observed Network Traffic (SPAN)`.

### Visit-authorized traffic

DTI MUST use the existing accepted Visit/authorization authority. It MUST NOT infer authorization start from the first Ethernet/IP frame.

For the first DTI milestone, Visit traffic is bounded by the existing Visit interval.

### Current Visit traffic

```text
Current Visit Traffic
=
only the overlap between safely attributed DTI traffic
and the exact existing current Visit interval
```

Traffic before Visit start and after Visit close is excluded from that Visit, even if physically observed.

Example:

```text
12:00 DHCP
12:01 captive portal traffic
12:03 authorization succeeds / Visit starts
12:30 Visit closes
```

Result:

```text
Device Today Traffic may include 12:00–12:30
Current Visit Traffic includes only 12:03–12:30
```

Coder MUST NOT redefine these populations.

TASK-DTI-03 freezes accounting population mechanics; TASK-DTI-04 freezes Visit/window projection mechanics.

---

# 25. NETWORK QUALITY PRINCIPLE

Transport quality != Wi-Fi quality.

SPAN can potentially support:

```text
retransmission indicators
resets
failed handshakes
connection churn
DNS latency/failures
stalls where measurable
```

Omada supports:

```text
RSSI
SNR
radio/controller facts
```

They may appear together in UI but retain separate provenance.

A transport-quality result must consume CaptureQuality.

If capture itself is degraded:

```text
quality assessment
→ partial / unavailable
```

rather than accusing the network/client.

---

# 26. SECURITY PRINCIPLE

Security layer is:

```text
ADVISORY ONLY
```

It MUST NOT automatically:

```text
block client
disconnect client
unauthorize client
rate-limit client
modify Access Policy
change CAPPORT result
change Device Fingerprint
```

Examples:

```text
high fan-out
possible scan behavior
unusual failed connection rate
suspicious DNS pattern
known IOC match
```

are signals, not final malicious-user verdicts.

Security summary MUST include coverage semantics.

Minimum conceptual result states:

```text
signals_present
no_signals_observed_with_sufficient_coverage
insufficient_coverage
unavailable
```

Permanent rules:

```text
sensor unavailable
!=
No threats

no alert
!=
device is safe
```

Preferred product wording when evidence is sufficient:

```text
No advisory signals observed
```

Never:

```text
Device is safe
```

Security remains advisory.

---

# 27. EXTERNAL INTELLIGENCE GOVERNANCE

No threat/reputation feed enters production simply because it is available.

Before admission evaluate:

```text
source ownership
license
redistribution rights
provenance
versioning
update cadence
freshness
offline behavior
false-positive behavior
retention
coverage
cost
```

Reuse Device Fingerprint knowledge-governance principles conceptually, but do not automatically bind this program to R14 artifact schemas.

---

# 28. FAILURE ISOLATION

Permanent invariant:

```text
Traffic Intelligence failure
MUST NOT break:

Portal
Authorization
CAPPORT
Omada integration
Device Fingerprint
Core Device Card
```

If source disappears:

```text
Current Traffic Intelligence → unavailable/stale
historical retained summaries → still readable with provenance
```

No failure is converted into zero.

DTI evidence semantics are conservative:

```text
missing/unavailable source
→ stale / unavailable / insufficient coverage
```

never:

```text
missing source
→ accept result anyway
```

The phrase `fail-open` is reserved for the intentional Authorization/CAPPORT failure-isolation boundary and MUST NOT describe DTI evidence acceptance.

---

# 29. PERFORMANCE PRINCIPLE

Capture/ingestion runs out-of-band from Portal request processing.

```text
Portal/Auth thread
!=
packet processing thread
```

Heavy work:

```text
async / worker / auxiliary service
```

Device Card reads:

```text
indexed/precomputed read models
```

not raw history scans.

Because the production environment is modest, deployment of multiple full packet analyzers must be benchmarked rather than assumed safe.

Permanent degradation principle:

```text
WHEN DTI RESOURCE BUDGET IS EXCEEDED,
DTI DEGRADES OR LOSES ITS OWN OBSERVATIONS FIRST.

Core Portal, Omada integration and the accepted
Device Fingerprint path MUST NOT be sacrificed.
```

DTI-00 / DTI-01 must freeze applicable limits for:

```text
CPU budget
memory budget
disk budget
queue/spool ceiling
backpressure
drop behavior
service resource isolation / cgroup/systemd limits where justified
disk-full behavior
```

Unbounded queueing is forbidden.

If ingest cannot keep up, the preferred failure shape is:

```text
bounded drop / reject
+
CaptureQuality degradation
+
telemetry
```

not silent resource growth.

---

# 30. ROADMAP OVERVIEW

I recommend changing the original 0–9 sequence to:

```text
DTI-00  Capability / Capture Baseline
   ↓
DTI-01  Network Observation Foundation
   ↓
DTI-02  Network Address Binding & Attribution
   ↓
DTI-03  Per-Device Traffic Accounting + Current Activity
   ↓
DTI-04  Visit / Device Traffic Summaries
   ↓
DTI-05  Device Card Traffic MVP
   ↓
 ┌───────────────┬─────────────────┐
 ↓               ↓                 ↓
DTI-06          DTI-08            DTI-09
Protocol        Network           Behavioral
Intelligence    Quality           History
 ↓
DTI-07
Service /
Destination
Recognition
 └───────────────┬─────────────────┘
                 ↓
              DTI-10
        Security / Anomaly
                 ↓
              DTI-11
 External Intelligence — conditional
```

The reason Device Card MVP moves earlier:

```text
traffic accounting
+
visit summary
+
current activity
```

already has strong product value and should not wait for advanced security/service inference.

---

# 31. TASK-DTI-00
# CAPABILITY & CAPTURE BASELINE

**Goal**

Prove what the existing physical mirrored traffic actually provides.

**Scope**

```text
SPAN/RSPAN topology inventory
direction inventory
guest VLAN coverage
L2 switching placement
L3/default-gateway placement
NAT placement
uplink placement
client MAC visibility at capture point
VLAN-tag visibility/preservation
pre-NAT vs post-NAT visibility
both-sides-of-flow visibility
capture loss/drop evidence
duplicate/mirror topology behavior
clock behavior
actual traffic volume
events/sec
flows/sec
protocol mix sample
current sensor inventory
Suricata capability inventory
Fingerprint Suricata coexistence options
capture-source/interface/VLAN → Site scope mapping
NetFlow overlap
resource baseline
CPU/RAM/disk/queue-spool degradation budget candidates
```

Evaluate whether lightweight meter is needed.

Evaluate Zeek only as comparison candidate.

**Dependencies**

Existing SPAN/RSPAN and Network Sensor architecture.

**Contracts to produce**

```text
DTICaptureCapabilityMatrix
CaptureTopologyReference
CapturePlacementProof
CaptureScopeBinding
CaptureQuality requirements
ResourceBudgetBaseline
ResourceDegradationPolicy
ParserAllocationDecision
FingerprintSensorCoexistenceDecision
TrafficAccountingSourceDecision
```

**Implementation boundary**

Research/lab/inventory only.

**Acceptance**

Must answer:

```text
what is captured?
in which direction?
what can be missed?
where the observation point sits relative to VLAN/L2/L3/gateway/NAT/uplink?
is client MAC actually visible there?
are VLAN tags visible/preserved where required?
are both sides of the flow visible?
is traffic observed pre-NAT or post-NAT?
can mirror topology duplicate the same packet?
which capture source/interface/VLAN/topology scope is authorized for which Site?
what happens for ambiguous/unknown Site scope?
how much traffic?
what parser owns which facts?
which Suricata coexistence topology protects the accepted Fingerprint path?
can current host/sensor resources support it?
what degrades first when DTI exceeds CPU/RAM/disk/queue budgets?
```

No unknown major capture assumptions.

**Production risk**

NONE during research.

**Device Card benefit**

None directly. Unblocks trustworthy data.

---

# 32. TASK-DTI-01
# NETWORK OBSERVATION FOUNDATION

**Goal**

Create one normalized durable contract for SPAN-derived traffic facts.

**Scope**

```text
capture health
flow slices
basic protocol observations
source identity
captured/event time
ingest time
processing time where required
source event identity / source sequence
ingest identity / sequence where required
ingest lag
clock-health provenance
authoritative Site scope via CaptureScopeBinding
schema/version
bounded ingestion
delivery/retry/replay semantics
duplicate/conflict semantics
bounded spool semantics if used
retention
backpressure/drop telemetry
resource ceiling behavior
```

**Dependencies**

DTI-00 PASS.

**Contracts**

Conceptually:

```text
NetworkObservationEnvelope
CaptureHealthObservation
NetworkFlowSlice
NetworkObservationSourceContract
NetworkObservationDeliveryContract
NetworkObservationIdentityContract
NetworkObservationRetentionPolicy
ResourceDegradationPolicy
```

**Implementation boundary**

Separate auxiliary ingestion path.

No UI.
No Device Fingerprint semantic changes.
No Auth/CAPPORT changes.

**Acceptance**

- Site isolation through accepted `CaptureScopeBinding`;
- unknown/ambiguous Site scope is rejected from Site-specific product attribution;
- no payload persistence;
- exact source/provenance;
- event/capture time is distinct from ingest time;
- source ordering/sequence and ingest lag are observable where applicable;
- deterministic schema validation;
- stable observation/source-event identity;
- duplicate replay is idempotent;
- restart/retry/replay cannot double traffic;
- same identity + different payload is conflict/fail-closed for that observation;
- delivery semantics are explicit;
- spool, if used, is bounded and has explicit restart/replay semantics;
- bounded storage;
- source outage is failure-isolated from Portal/Auth/CAPPORT;
- DTI source health becomes stale/unavailable as defined by its evidence contract;
- missing evidence is never converted to zero, healthy, complete, idle, or otherwise accepted as positive evidence;
- capture/ingest drops observable;
- resource ceilings/backpressure/disk-full behavior degrade DTI first;
- benchmark within approved CPU/RAM/disk budget.

**Risk**

MEDIUM — high-volume ingest foundation.

**Benefit**

Foundation for all later traffic features.

---

# 33. TASK-DTI-02
# NETWORK ADDRESS BINDING & ATTRIBUTION

**Goal**

Safely answer:

```text
which IP belonged to which Site+MAC at time T?
```

**Scope**

IPv4 + IPv6 temporal binding.

Research source authority for:

```text
DHCP
ARP
ND
Omada persisted state
other accepted observations
```

**Dependencies**

DTI-01.

**Contracts**

```text
NetworkAddressBindingObservation
NetworkAddressBindingTimeline
FlowAttributionResult
AttributionCoverage
RegistryIdentityBindingState
LateIdentityCorrelationContract
```

**Acceptance**

Fixtures for:

```text
DHCP renewal
IP reassignment
same IP reused by different MAC
multiple addresses
temporary IPv6
overlapping/contradictory observations
missing binding
ambiguous binding
```

No IP-only attribution.

No cross-MAC identity merge.

Ambiguous traffic is never assigned to a device.

Unattributed traffic is measured/reported and cannot silently disappear from completeness semantics.

Per-device totals are complete only when both CaptureQuality and AttributionCoverage meet their frozen requirements.

Pre-Registry lifecycle fixtures MUST include:

```text
Site+MAC observation before device_id exists
later authoritative Registry device_id resolution
deterministic late correlation of retained eligible observations
no observation rewrite
no invented device_id
no Device Card creation from unbound observation alone
```

**Risk**

HIGH semantic risk if wrong.

**Benefit**

Makes per-device traffic trustworthy.

---

# 34. TASK-DTI-03
# PER-DEVICE TRAFFIC ACCOUNTING + CURRENT ACTIVITY

**Goal**

Provide reliable device traffic accounting and live activity primitives.

**Scope**

```text
observed bytes up/down
packets
flow count
TCP connection count where defined
current rate
peak rate
active/idle state
last network activity
```

Define:

```text
byte basis
direction
bucket size
flow lifecycle
retransmission treatment
dedup
capture-quality handling
TrafficAccountingScope
unicast/broadcast/multicast treatment
local/LAN/gateway/control/Internet-path semantics
```

**Dependencies**

DTI-01 + DTI-02.

**Contracts**

```text
TrafficAccountingContract
TrafficAccountingScope
TrafficPopulationAuthorizationBoundaryContract
DeviceTrafficBucket
DeviceCurrentActivity
```

**Acceptance**

Controlled traffic must reconcile within explicitly justified tolerance.

Test:

```text
long-lived flow
short bursts
idle
counter reset equivalent
capture restart
packet duplicate
partial capture
IP reassignment
IPv4/IPv6
```

Traffic population semantics must preserve:

```text
Device-observed traffic
Visit-authorized traffic
Current Visit traffic
```

`Device Today Traffic` includes safely attributed pre-auth traffic in the Today window.

`Current Visit Traffic` is strictly limited to the existing Visit interval.

Accounting scope MUST prove which unicast/broadcast/multicast/link-local/local/gateway/Internet classes enter each metric.

A mirrored multicast/broadcast frame MUST NOT be multiplied into per-device download traffic merely because multiple clients could have received it.

`Observed Network Traffic (SPAN)` MUST NOT be labeled Internet-only unless a separate frozen Internet-scope metric is later proven.

`Network Activity: Idle` is valid only with sufficient CaptureQuality, sufficient attribution, a fully covered fresh window, and no qualifying traffic.

Current network activity must age to stale/unavailable correctly and must never be inferred from late replay arrival.

**Risk**

HIGH because product numbers must be trustworthy.

**Benefit**

Very high.

This is first stage where:

```text
Observed Network Traffic (SPAN)
Today traffic primitive
Network Activity: Active/Idle/Unavailable
```

becomes possible.

---

# 35. TASK-DTI-04
# VISIT & DEVICE TRAFFIC SUMMARIES

**Goal**

Turn low-level traffic accounting into useful historical product data.

**Scope**

```text
current Visit traffic
completed Visit traffic
today
24h
7d
30d
device lifetime aggregate where justified

upload/download
peak
active duration
connection count
```

**Dependencies**

DTI-03 + existing Visit/Registry.

**Contracts**

```text
VisitNetworkSummary
DeviceNetworkSummary
DeviceNetworkProjection
LateIdentityProjection
DerivedResultLineage
RebuildDependencyClosure
```

**Architecture**

Derived/versioned/rebuildable projection.

Do not modify Visit source history to inject analytics.

**Acceptance**

- deterministic rebuild only when dependency closure is retained;
- exact derived-result lineage/version generation;
- exact Site boundary;
- Visit boundary handling;
- pre-auth Device Today traffic vs Visit traffic semantics preserved;
- retained unbound Site+MAC observations may be deterministically late-projected only after authoritative Registry identity resolves;
- late binding never rewrites original observation identity and never invents device identity;
- open Visit behavior;
- closed Visit behavior;
- Site timezone day boundaries;
- source/capture quality carried forward;
- attribution coverage/status carried forward;
- no N+1/raw scan in Device Card.

**Risk**

MEDIUM.

**Benefit**

Very high.

---

# 36. TASK-DTI-05
# DEVICE CARD TRAFFIC MVP

**Goal**

Expose the first useful result early.

**Initial Device Card blocks**

```text
Network Activity
Observed Network Traffic (SPAN)
basic History
```

Initial fields:

```text
Network Activity: active/idle/unavailable
current observed SPAN rate
last network activity

Observed Network Traffic (SPAN)
current Visit
today
7 days
up/down
peak

security coverage state when Security layer is later enabled
```

**Dependencies**

DTI-04 + existing Device Card/read infrastructure.

**Contracts**

```text
DeviceNetworkReadModel v1
internal Device network read boundary
```

**Implementation boundary**

UI reads prepared backend model only.

**Acceptance**

- UI performs no analytics;
- no raw observation reads;
- freshness visible;
- unavailable != zero;
- source/provenance available to engineering view;
- Site-safe;
- Device Fingerprint result unchanged.

**Risk**

LOW/MEDIUM.

**Benefit**

Immediate visible product value.

---

# 37. TASK-DTI-06
# PROTOCOL / DNS / TLS / QUIC INTELLIGENCE

**Goal**

Add protocol metadata without content inspection.

**Scope**

Product subset first:

```text
DNS
TLS
QUIC
TCP
UDP
ICMP
DHCP
NTP
mDNS
SSDP
STUN/TURN
tunnel indicators
```

For DNS:

```text
queries where visible
unique domains
NXDOMAIN/failure
resolver
latency where provable
```

For TLS:

```text
SNI where visible
version
ALPN
bounded certificate metadata
```

For QUIC:

```text
version
observable handshake metadata
```

**Dependencies**

DTI-01/02/03.

**Contracts**

Typed normalized protocol observations + protocol summary.

**Acceptance**

- DoH/DoT/ECH/VPN limitations explicit;
- encrypted absence never becomes negative evidence;
- no payload storage;
- exact parser versions/provenance;
- malformed/unknown protocol safely handled.

**Risk**

MEDIUM privacy/cardinality.

**Benefit**

High.

---

# 38. TASK-DTI-07
# SERVICE & DESTINATION RECOGNITION

**Goal**

Convert protocol/destination metadata into explicitly separated organization/infrastructure, service, and service-category dimensions.

**Examples**

```text
Infrastructure / Organization:
Google
Cloudflare
Meta
Microsoft
Apple

Service:
YouTube
WhatsApp
Telegram
Netflix
Spotify

Service Category:
streaming
messaging
social
gaming
cloud storage
software update
```

**Inputs — V1 required**

```text
DNS where available
SNI where available
destination IP
port/protocol
multiple supporting observations
local/versioned recognition rules
```

**Optional external enrichment**

```text
ASN/org
IP ownership
other benign destination enrichment
```

is NOT required for DTI-07 PASS and MUST remain unavailable until a separately governed/admitted enrichment source exists.

Permanent dependency rule:

```text
DTI-07 V1
MUST NOT depend on an external enrichment source
that has not yet been admitted.
```

**Contracts**

```text
RecognitionTaxonomyContract
ServiceRecognitionRuleSet
ServiceObservation
DestinationEnrichment
ServiceSummary
```

**Acceptance**

- versioned taxonomy;
- versioned ruleset;
- organization/provider, service and category remain separate;
- provenance;
- ambiguous result allowed;
- CDN ambiguity tested;
- shared IP tested;
- DNS caching tested;
- ECH/no-SNI tested;
- no claim of packet-content visibility;
- exact service != provider unless proven;
- DTI-07 PASS does not require ASN/org;
- absence of optional external enrichment must degrade only the enrichment dimension, not invalidate locally supported recognition;
- no unadmitted external source may be required by the V1 recognition path.

**Risk**

MEDIUM/HIGH semantic inference risk.

**Benefit**

High.

---

# 39. TASK-DTI-08
# NETWORK QUALITY INTELLIGENCE

**Goal**

Provide transport-quality evidence complementary to Omada RF.

**Potential metrics**

```text
TCP retransmission indicator
resets
failed SYN/connect ratio
connection churn
DNS latency/failure
short aborted sessions
stall indicators where defensible
passive RTT only if proven
```

**Dependencies**

DTI-00 capture-quality proof + DTI-03/06.

**Contracts**

```text
TransportQualityMetrics
NetworkQualityAssessment
```

**Acceptance**

- capture quality is mandatory input;
- degraded capture cannot produce false poor-network verdict;
- RF and transport evidence remain separate;
- no unsupported packet-loss percentage;
- no unsupported RTT;
- controlled fault scenarios where feasible.

**Risk**

HIGH interpretation risk.

**Benefit**

Very high for troubleshooting.

---

# 40. TASK-DTI-09
# BEHAVIORAL HISTORY / DEVICE EVOLUTION

**Goal**

Describe normal historical patterns without turning behavior into identity proof or security verdict.

**Possible outputs**

```text
typical active hours
typical Visit duration
typical traffic volume
upload/download profile
typical protocol mix
typical service categories
burst profile

new service family observed
traffic pattern changed
protocol mix changed
TLS/QUIC pattern changed
```

**Dependencies**

Enough retained history from DTI-04/06/07.

**Contracts**

```text
BehaviorProfile
DeviceNetworkChangeEvent
```

Potential future:

```text
network_behavior_role
```

only if separately proven useful.

**Forbidden**

```text
behavior → device_id
behavior → fingerprint device_class overwrite
```

**Acceptance**

- deterministic historical windows;
- minimum sample/coverage requirements;
- no result-driven identity merge;
- insufficient history -> insufficient_data;
- descriptive only.

**Risk**

MEDIUM.

**Benefit**

Medium/high after history accumulates.

---

# 41. TASK-DTI-10
# SECURITY / ANOMALY ADVISORY LAYER

**Goal**

Provide useful operator warnings without automatic enforcement.

**Signals**

Potentially:

```text
connection fan-out
possible scanning pattern
high failed destination ratio
DNS anomaly
connection churn
unusual outbound traffic
known local Suricata alert
lateral probing indicators
```

**Dependencies**

Stable DTI foundation and behavior history.

**Contracts**

```text
SecuritySignal
SecuritySignalPolicy
SecurityCoverage
SecuritySummary
```

**Acceptance**

- advisory only;
- no block/disconnect;
- no Auth influence;
- false-positive handling;
- suppression/expiry;
- provenance;
- severity semantics;
- source health;
- explicit security coverage;
- `signals_present`;
- `no_signals_observed_with_sufficient_coverage`;
- `insufficient_coverage`;
- `unavailable`;
- unavailable coverage never renders as `No threats`;
- ambiguous/unknown valid.

**Risk**

HIGH false-positive/operator-trust risk.

**Benefit**

Useful but not early critical path.

---

# 42. TASK-DTI-11
# EXTERNAL INTELLIGENCE GOVERNANCE + OPTIONAL INTEGRATION

DTI-11 keeps external governance outside the DTI-07 V1 critical path.

External sources are split into distinct governance classes.

## DTI-11A — Benign Destination / Ownership Enrichment Research & Admission

Candidate classes:

```text
ASN databases
IP ownership datasets
benign domain/service mapping sources
```

These MAY later enrich:

```text
Infrastructure / Organization
destination ownership
service-recognition supporting evidence
```

They are optional. DTI-07 V1 must already be able to PASS without them.

## DTI-11B — Security / Threat Intelligence Research & Admission

Candidate classes:

```text
IP reputation
domain reputation
malware IOC sources
other threat-intelligence feeds
```

These belong to the advisory security domain and MUST NOT be treated as equivalent to benign ASN/ownership enrichment.

## DTI-11C — Optional Integration

An integration subtask exists only after the corresponding source class has an explicit admission decision.

Every admitted source requires, as applicable:

```text
version
provenance
freshness
license
update mechanism
offline behavior
coverage semantics
false-positive semantics where relevant
```

Research/admission output:

```text
ACCEPT SOURCE
REJECT SOURCE
NOT JUSTIFIED
```

No DTI-11 research result by itself authorizes production activation.

**Risk**

HIGH governance/dependency risk.

**Benefit**

Optional.

---

# 43. CROSS-CUTTING ACCEPTANCE GATES

Every implementation task later MUST address applicable gates:

```text
G1  Site isolation
G2  Authorization/CAPPORT fail-open
G3  Capture quality
G4  Identity attribution correctness
G5  Attribution completeness / ambiguity coverage
G6  IPv4 + IPv6
G7  UTC / half-open time semantics
G8  event/capture time != ingest time
G9  privacy minimization
G10 no raw content retention
G11 provenance/versioning
G12 freshness/staleness
G13 deterministic rebuild where derived
G14 rebuild dependency closure
G15 resource/storage budget + bounded degradation
G16 source failure behavior
G17 no Device Fingerprint semantic drift
G18 Fingerprint Suricata coexistence protection
G19 no silent Omada-counter/SPAN-value mixing
G20 one product metric → one semantic owner
G21 authoritative CaptureScopeBinding / Site attribution
G22 traffic population / authorization boundary correctness
G23 ingestion idempotency / replay safety
G24 derived-result version lineage
G25 multi-site compatibility
G26 bounded query/read performance
G27 observability
G28 rollback/deactivation
G29 production untouched until separate approval
G30 pre-Registry observation / late identity binding correctness
G31 TrafficAccountingScope incl. multicast/broadcast/local-path semantics
G32 external enrichment dependency/admission correctness
G33 DTI source outage conservative evidence semantics
G34 SensitiveNetworkMetadata access/minimization boundary
```

---

# 44. FIRST PRODUCT MILESTONE

The first useful release should NOT wait for the entire roadmap.

Recommended milestone:

```text
DTI-00 PASS
DTI-01 PASS
DTI-02 PASS
DTI-03 PASS
DTI-04 PASS
DTI-05 PASS
```

Result:

```text
Device Card

Network Activity
  Active / Idle / Unavailable
  Current observed SPAN rate
  Last network activity

Observed Network Traffic (SPAN)
  Current Visit
  Today
  7 Days
  Upload
  Download
  Peak

History
  Visit traffic summaries
```

Only after this stable slice:

```text
protocols
services
quality
behavior
security
```

are layered on top.

---

# 45. ITEMS EXPLICITLY NOT FROZEN BY v0.3

These require research/task-specific contracts:

```text
exact database engine
exact flow bucket duration
exact flow timeout
exact retention days
exact CaptureQuality enum
exact binding authority precedence
exact Suricata event configuration
exact Traffic Meter implementation
exact service recognition sources
exact domain retention representation
exact ASN database/provider
exact quality thresholds
exact anomaly thresholds
exact threat feed
exact TrafficAccountingScope class table/details
exact SensitiveNetworkMetadata RBAC/capability names
exact UI layout
```

Architect/Coder must not invent these values from this roadmap.

---

# 46. ROADMAP INTEGRATION DECISION

After Owner + TechLead review, register this program in project roadmap as:

```text
DEVICE TRAFFIC ENRICHMENT / DEVICE INTELLIGENCE
PROGRAM PREFIX = DTI
```

It is:

```text
SEPARATE FROM DEVICE-FINGERPRINT TASK-06
```

but consumes/reuses:

```text
existing Device identity
existing Visit Lifecycle
existing Observation/Current State
existing Analytics patterns
existing Device Fingerprint authoritative result
existing SPAN infrastructure
```

Each `TASK-DTI-*` item receives its OWN future full technical specification before any Coder work.

No roadmap entry itself authorizes implementation.

---

# 47. ARCHITECT v0.3 VERDICT

```text
DEVICE_TRAFFIC_ENRICHMENT =
ARCHITECTURE / ROADMAP REVISION READY FOR TECHLEAD FINAL BOUNDED REVIEW

TECHLEAD V0.2 CORE VERDICT =
PASS

TL-R1 ... TL-R15 =
ACCEPTED

TL-R16 ... TL-R20 =
INCORPORATED

REDESIGN =
NO

ROADMAP SEQUENCE =
UNCHANGED

FIRST PRODUCT MILESTONE =
DTI-00 → DTI-01 → DTI-02 → DTI-03 → DTI-04 → DTI-05

V0.3 BOUNDED REFINEMENTS =
16. pre-Registry Site+MAC observations may exist and late-bind only to authoritative existing device_id
17. TrafficAccountingScope freezes unicast/broadcast/multicast/local/gateway/Internet semantics
18. DTI-07 V1 has no mandatory external enrichment dependency; benign enrichment and threat intelligence governance are separate classes
19. DTI source outage uses conservative stale/unavailable/insufficient evidence semantics; fail-open wording reserved for Auth/CAPPORT isolation
20. SensitiveNetworkMetadata receives a distinct access/minimization boundary

IMPLEMENTATION =
NO

CODER =
HOLD

ROADMAP REGISTRATION =
HOLD UNTIL TECHLEAD FINAL ACCEPTANCE

PRODUCTION CHANGE =
NO

NEXT =
TECHLEAD FINAL BOUNDED REVIEW OF v0.3
```
