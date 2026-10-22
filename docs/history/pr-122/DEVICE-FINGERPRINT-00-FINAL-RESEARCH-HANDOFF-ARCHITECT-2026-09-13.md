# DEVICE-FINGERPRINT-00 — FINAL Research Handoff to Architect

**Project:** CaptivPortal  
**Research:** Passive Mobile / Personal Device Fingerprinting — Source Feasibility & Architecture Inputs  
**Date:** 2026-09-13  
**Prepared by:** Tech Lead research stream for Owner / Architect  
**Repository baseline:** `3dc85735ddf5d05dd20733d15dfe1c22c9c4fde5`  
**Repository tree:** `8312658be3ba272998f46212d9bad76950e3867e`

---

## 0. CONTROL STATUS

```text
DEVICE-FINGERPRINT-00          = FINAL RESEARCH COMPLETE
LIVE BOUNDED EVIDENCE          = PASS
TOOL FEASIBILITY               = PASS
ARCHITECTURE INPUTS            = READY
ARCHITECTURE DRAFT             = UNBLOCKED FOR ARCHITECT REVIEW
CODER                          = HOLD
IMPLEMENTATION                 = NOT AUTHORIZED
PRODUCTION COLLECTION          = NOT AUTHORIZED
DB / SCHEMA CHANGE             = NOT AUTHORIZED
CLASSIFIER IMPLEMENTATION      = NOT AUTHORIZED
DEVICE CARD CHANGE             = NOT AUTHORIZED
```

This document closes the research task. It does **not** authorize implementation. Its purpose is to give the Architect enough verified input to prepare a future `TASK-DEVICE-FINGERPRINT-01-DRAFT` without guessing about the current network, capture visibility, protocol availability, parser capability, privacy boundary, or sensor feasibility.

---

# 1. EXECUTIVE VERDICT

Passive device fingerprint evidence is technically feasible in the current CaptivPortal environment.

The live lab proved that the selected pre-NAT switched capture path can observe the owner-controlled guest device with its original IPv4 and MAC and can expose useful client-originated evidence from:

```text
L2/L3 binding
DHCP
TCP SYN
TLS-over-TCP
QUIC / HTTP3
DNS
mDNS
portal HTTP User-Agent / Client Hints
IPv6 link-local behavior
```

The strongest architecture is **not** a single “device detector.” It is a versioned multi-source evidence pipeline:

```text
existing CaptivPortal / Omada facts
                +
passive packet evidence
                +
portal HTTP evidence
                ↓
source-specific normalization
                ↓
privacy-minimized evidence records
                ↓
future classifier
                ↓
derived classification + confidence
```

The classifier must remain downstream and non-authoritative. A device class, OS family, vendor, model family, browser/runtime family, or confidence score is a **derived conclusion**, never a replacement for the raw source facts.

The production-safe implementation direction is:

```text
Suricata 8.x
    → primary protocol/event extractor

small bounded parsers
    → exact DHCP PRL / option order
    → exact TCP SYN stack vector
    → exact QUIC transport-parameter vector only if the Architect decides it adds enough value

portal request extractor
    → normalized User-Agent / low-entropy Client Hints

tshark / dumpcap
    → lab ground truth and bounded validation, not the main production event engine
```

The packet sensor must be in a **separate failure domain from captive authorization**. Fingerprinting failure must never break, delay, deny, or change guest authorization.

---

# 2. LIVE TOPOLOGY AND CAPTURE PROOF

## 2.1 Confirmed guest network

Cisco guest L3 interface:

```text
Gi0/1.20
 description Guest
 encapsulation dot1Q 20
 ip address 192.168.10.1 255.255.252.0
 ip access-group GUEST_TTL_FILTER in
 ip flow ingress
 ip flow egress
 ip nat inside
```

Canonical guest network:

```text
network = 192.168.8.0/22
gateway = 192.168.10.1
```

DHCP authority is the Cisco router:

```text
ip dhcp pool Guest
 network 192.168.8.0 255.255.252.0
 default-router 192.168.10.1
 dns-server 192.168.0.1
```

WAN boundary:

```text
Gi0/0 = 192.168.100.10
ip nat outside
ip nat inside source list 100 interface GigabitEthernet0/0 overload
```

Therefore traffic observed on the Catalyst guest path is **pre-NAT**.

IPv6 routing is not enabled on the Cisco baseline (`show ipv6 route` produced no routing table; `no ipv6 cef`).

## 2.2 Confirmed switch path

Catalyst 2960 guest VLAN = VLAN 20.

Relevant trunks carry VLAN 20:

```text
Gi1/0/1   router trunk
Gi1/0/5   EAP225
Gi1/0/10  EAP613 NEW
Gi1/0/15  EAP613
```

Research sensor destination:

```text
Gi1/0/40
```

Final temporary research SPAN running state:

```text
Session 1
Type                     : Local Session
Source VLANs:
    Both                 : 10,20
Destination Ports        : Gi1/0/40
    Encapsulation        : Native
          Ingress        : Enabled, default VLAN = 10
    Ingress encap        : Untagged
```

The sensor PC simultaneously retained normal network access and received `192.168.0.105` on Gi1/0/40.

**Important limitation:** this research SPAN does not preserve VLAN tags. VLAN 10 and VLAN 20 traffic are mixed on the destination. The live experiments therefore selected guest traffic by the proven guest subnet and owner-controlled MAC. A future design must not infer VLAN/Site from a missing tag. Capture scope/Site must come from trusted sensor configuration or a deliberately scoped mirror configuration.

No startup configuration save was authorized for the temporary research SPAN.

## 2.3 Capture visibility verdict

```text
Guest IPv4 visibility             = PASS
Pre-NAT client IP visibility      = PASS
Original client MAC visibility    = PASS
L2 ↔ L3 binding observable        = PASS
Bidirectional protocol traffic    = PASS
DHCP visibility                   = PASS
TCP visibility                    = PASS
TLS visibility                    = PASS
QUIC visibility                   = PASS
DNS visibility                    = PASS
mDNS visibility                   = PASS
IPv6 link-local visibility        = PASS
Global/routed guest IPv6          = NOT AVAILABLE on current routing baseline
VLAN tag preservation             = FAIL in research SPAN mode / not required for the bounded proof
SPAN duplicates                   = CONFIRMED / dedup required
```

This closes the original topology/capture blocker.

---

# 3. CONTROLLED GROUND-TRUTH DEVICE

Owner-controlled Android device used for bounded proof:

```text
Device ground truth : Nokia G21
OS                   : Android
Observed OS detail   : Android 13 from portal WebView UA
Guest IPv4           : 192.168.10.132
Observed guest MAC   : be:00:7d:9b:04:2e
MAC property         : locally administered / private-style MAC
```

Cisco ARP independently confirmed:

```text
192.168.10.132  be00.7d9b.042e  ARPA  Gi0/1.20
```

Research identity rule:

```text
MAC = current observed device/session binding
MAC ≠ global person identity
private/randomized MAC similarity MUST NOT trigger cross-MAC merge
```

Only this Android device was used as the controlled packet-level ground-truth device. Other platform observations seen incidentally in portal traffic are not treated as a labeled multi-platform dataset.

**Architectural consequence:** the architecture draft is unblocked, but production classifier accuracy across iOS/Windows/macOS/Linux remains a later validation gate. It must not be invented from the Android dataset.

---

# 4. EXISTING CAPTIVPORTAL FACT OWNERSHIP

The packet collector must not duplicate facts already owned by existing CaptivPortal domains.

Existing ownership includes, depending on domain/read surface:

```text
Visitor Registry
    device_id
    MAC identity record
    historical snapshots

Observation Storage
    controller client facts
    IP / IPv6 list
    SSID
    AP
    band/radio/channel
    RSSI / SNR
    controller names / types
    traffic / activity context

Current State
    current materialized client state

Visit Lifecycle
    visit/session chronology
    auth/session relationship
    source events
    reconnect / lifecycle context

Portal redirect/request context
    clientMac
    clientIp
    site
    apMac
    SSID
    radioId
```

Therefore the new passive fingerprint subsystem should own only **new evidence**, such as:

```text
DHCP client option behavior
TCP SYN stack vector
TLS / QUIC ClientHello fingerprint evidence
portal UA / Client Hints normalization
optional DNS capability behavior
optional local-discovery behavior
```

It must reference existing device/site/session context instead of rebuilding it from packets.

---

# 5. LIVE SOURCE RESULTS

## 5.1 DHCP — PASS / CORE

Capture: `guest-dhcp-01.pcapng`.

Controlled Android DORA was observed end-to-end.

Client evidence:

```text
MAC                  = be:00:7d:9b:04:2e
assigned IPv4        = 192.168.10.132
Vendor Class         = android-dhcp-13
Client Identifier    = same observed MAC
maximum message size = 1500
hostname             = absent
```

Full manually verified PRL:

```text
1,3,6,15,26,28,51,58,59,43,114,108
```

Client option order:

```text
DISCOVER = 53,61,57,60,55,80,255
REQUEST  = 53,61,50,54,57,60,55,255
```

Additional capability signals:

```text
option 80  Rapid Commit
option 114 CAPPORT support request
option 108 IPv6-Only Preferred capability signal
```

Option 108 proves client capability/request behavior only; it does not prove routed IPv6 was active.

### Suricata DHCP result

Suricata 8.0.6 extended DHCP EVE correctly exposes:

```text
MAC/IP assignment
Client-ID
Vendor Class
requested IP
lease-related fields
normalized parameter names
```

But it does **not** preserve the full raw 12-item PRL or exact raw client option order in EVE. The EVE `params` view exposed only a normalized subset in this sample.

### DHCP architecture decision

```text
DHCP raw visibility                    = PASS
Suricata protocol extraction           = PASS
Full PRL through Suricata EVE          = INCOMPLETE
Exact DHCP option order through EVE    = FAIL
DHCP fingerprint value                 = STRONG
Phase-1                                = CORE
```

Recommended extraction model:

```text
Suricata DHCP event
        +
small packet-level DHCP feature parser
        → exact PRL
        → exact option-order vector
        → selected capability flags
```

Do not retain general DHCP packet payload after normalized evidence is produced.

---

## 5.2 TCP SYN — PASS / CORE-SUPPORTING

Capture: `guest-tcp-syn-01.pcapng`.

Raw capture contained 128 mirrored SYN packets = 64 unique client SYNs after SPAN dedup.

All 64 unique SYNs from the controlled Android shared the same observed stack vector:

```text
TTL                  = 64
TCP Window           = 65535
MSS                  = 1460
Window Scale         = 8
SACK Permitted       = yes
TCP Timestamp        = yes
TCP option order     = MSS → SACK → Timestamp → NOP → WindowScale
```

This is strong evidence of a stable client stack signature within the bounded window, but it is **not** an exact OS/model authority. VPNs, tethering, middleboxes, kernel/browser changes and network path changes can alter some properties.

### Suricata TCP result

Suricata EVE confirms TCP SYN flows and `tcp_flags=02`, but the standard flow output does not expose the fingerprint vector required by this research:

```text
TTL
raw Window
MSS
Window Scale
SACK
Timestamp presence/value class
ordered TCP options
```

### TCP architecture decision

```text
TCP SYN visibility                   = PASS
Stable bounded stack vector          = PASS
Suricata flow recognition            = PASS
Suricata full SYN fingerprint EVE    = FAIL / insufficient
TCP SYN as sole OS authority         = REJECT
TCP SYN as supporting evidence       = STRONG
```

Recommended extraction model:

```text
small packet-level SYN feature parser
    → normalized stack vector
    → no payload collection
```

p0f may be used later as a comparison/oracle, but its OS label must not become canonical truth without local labeled validation.

---

## 5.3 TLS-over-TCP — PASS / JA4 CORE

Capture: `guest-tls-01.pcapng`.

Manual analysis found 18 unique client TLS ClientHello events.

Observed inputs included:

```text
TLS 1.3 capability
cipher suites
extensions
supported groups
signature algorithms
ALPN
SNI where visible
GREASE-related variation
ECH extension presence
```

All observed ALPN values were:

```text
h2,http/1.1
```

The normalized non-GREASE cipher list was stable, but TLS extension ordering was deliberately/randomly permuted across the ClientHello set.

### JA3 live result

With Suricata JA3 explicitly enabled:

```text
18 ClientHello
18 unique JA3 hashes
```

Therefore classic JA3 is extremely unstable for this Chromium-style client sample and must not be the primary fingerprint.

### JA4 live result

Suricata JA4 distribution:

```text
15 / 18  t13d1517h2_8daaf6152771_cb7bf5808d99
 1 / 18  t13d1516h2_8daaf6152771_9b887d9acb53
 1 / 18  t13d1513h2_8daaf6152771_eca864cca44a
 1 / 18  t13d1518h2_8daaf6152771_e2d80978ab2e
```

The middle JA4 component remained constant across all 18 observations:

```text
8daaf6152771
```

This is materially more stable than JA3 and supports component/family-based evidence rather than exact-string identity.

### ECH limitation

ECH extension type was observed in most TLS ClientHello events, but extension presence alone does **not** prove that a real inner ECH handshake was used; GREASE ECH must remain possible.

### TLS architecture decision

```text
TLS ClientHello extraction           = PASS
JA3 extraction                       = PASS
JA3 exact stability                  = FAIL / VERY WEAK
JA4 extraction                       = PASS
JA4 bounded stability                = STRONG
SNI                                  = privacy-sensitive / nonessential
ECH presence                         = observable signal only
JA4 as sole OS/device authority      = REJECT
JA4 as Phase-1 evidence              = CORE
```

Raw SNI browsing history must not be a durable fingerprint record.

---

## 5.4 QUIC / HTTP3 — PASS / JA4 CORE

Capture: `guest-quic-01.pcapng`.

Manual ground truth:

```text
captured UDP/443 packets              = 14,778
unique after SPAN dedup               = 7,389
client QUIC flows                     = 35
QUIC version                          = v1
unique QUIC Initial                   = 207
unique client Initial                 = 91
fully reconstructed ClientHello       = 28
```

For all 28 reconstructed client ClientHello messages:

```text
TLS 1.3 capability      = present
ALPN                    = h3
QUIC transport params   = extension present
ECH ext 0xfe0d          = present
SNI / outer SNI         = visible in the sample
```

Manual normalization reduced heavy extension-order permutation to three primary extension-set families with distribution `13 + 13 + 2`.

### Suricata QUIC result

Suricata 8.0.6 reproduced the useful handshake layer directly from the same PCAP and emitted `event_type=quic`, QUIC version, SNI, JA3, JA4 and TLS extension lists.

Client JA4 distribution:

```text
13 × q13d0311h3_55b375c5d22e_653d80c3fe9d
13 × q13d0312h3_55b375c5d22e_178839b6cec1
 2 × q13d0313h3_55b375c5d22e_226f3f127bbe
```

This exactly mirrors the three manually observed normalized families.

Classic JA3 again showed extension-order instability; the 28 client ClientHello events produced 28 distinct JA3 hashes.

Suricata exposes the presence of the `quic_transport_parameters` TLS extension but does not expose all exact internal transport-parameter values/order in the standard EVE object used here.

### QUIC architecture decision

```text
QUIC v1 passive recognition            = PASS
Initial / ClientHello recovery          = PASS
HTTP3 ALPN h3                           = PASS
JA3 stability                           = FAIL / VERY WEAK
JA4 normalization/stability             = STRONG
Suricata QUIC extractor                 = PASS
exact QUIC TP values/order in EVE       = NOT PROVIDED
Phase-1                                 = CORE where present
```

Only if the Architect decides exact QUIC transport-parameter behavior adds meaningful classifier value should a small dedicated QUIC feature parser be added. It is **not required** to justify the Phase-1 architecture.

---

## 5.5 Portal User-Agent / Client Hints — PASS / CORE

The production ingress path was verified as:

```text
nginx :80/:443
    → local backend 127.0.0.1:8088
```

Existing journal/request logs do not persist User-Agent / Client Hint fingerprint evidence, but bounded loopback observation proved the headers reach the application path and preserve the real guest IP through proxy headers.

For the controlled Android `.132`, the captive WebView request exposed:

```text
sec-ch-ua-platform : "Android"
sec-ch-ua-mobile   : ?1
sec-ch-ua          : Android WebView / Chromium family
User-Agent         : Android 13; Nokia G21; WebView context
```

The same physical device in regular Chrome produced a different UA representation and Chromium/Chrome version family, while another portal API request showed a more generic Chrome-like UA.

### Portal architecture decision

```text
Real guest IP at portal             = PASS
User-Agent availability             = PASS
low-entropy Client Hints            = PASS
WebView differentiation             = PASS
model extraction                    = CONDITIONAL but observed
OS version extraction               = CONDITIONAL but observed
single raw UA stability             = FAIL
multi-observation UA/CH evidence    = STRONG
Phase-1                             = CORE
```

Raw UA must be treated as an observation, not as one permanent authoritative device field.

Recommended durable normalization should prefer:

```text
platform family
mobile boolean
browser/runtime family
webview/captive-context signal
model family only when explicitly present and policy-approved
OS major only when explicitly present and policy-approved
extractor/parser version
```

No high-entropy `Accept-CH` expansion or JavaScript fingerprinting is authorized by this research.

---

## 5.6 DNS — PASS / OPTIONAL ONLY

Capture: `guest-dns-01.pcapng`.

Manual result:

```text
466 raw packets
233 unique after SPAN dedup
117 queries
116 responses
54 unique queried names
resolver = 192.168.0.1:53/UDP
DoT/853 observed = 0
```

The sample included both `A` and modern `HTTPS` RR queries.

Suricata 8.0.6 correctly emitted:

```text
request / response
rrname
rrtype
A answers
CNAME
SOA
TTL
rcode
```

This proves good parser capability but simultaneously demonstrates the privacy problem: standard DNS EVE contains a detailed browsing/application-domain history.

### DNS architecture decision

```text
Plain UDP/53 visibility             = PASS
Suricata DNS extraction            = PASS
A / HTTPS RR visibility            = PASS
raw FQDN privacy risk              = HIGH
raw DNS durable retention          = REJECT
DNS as OS/device authority         = FAIL
DNS as supporting evidence         = OPTIONAL
DoH                                = NOT TESTED / unresolved from DNS log
DoT                                = NOT OBSERVED in bounded sample
```

If DNS evidence is ever used, the safe pattern is:

```text
raw DNS event
    ↓ transient rule evaluation
normalized capability/ecosystem feature
    ↓
raw name discarded
```

The system must not build a durable visitor browsing-history dataset.

---

## 5.7 mDNS / LLMNR — mDNS PASS, LLMNR NOT OBSERVED

Capture: `guest-local-discovery-01.pcapng`.

Controlled Android emitted Google Cast discovery:

```text
_googlecast._tcp.local
_CC1AD845._sub._googlecast._tcp.local
```

Suricata 8.0.6 recognized these natively as `event_type=mdns` from:

```text
192.168.10.132:5353 → 224.0.0.251:5353
```

The 12 captured packets represented three logical requests duplicated approximately ×4 by the current mixed SPAN/multicast path.

No LLMNR traffic from this Android was present in the bounded capture.

### Local discovery architecture decision

```text
mDNS visibility                    = PASS
Suricata mDNS extraction           = PASS
Google Cast service-family signal  = PASS
raw mDNS name privacy              = MEDIUM-HIGH
mDNS as device authority           = FAIL
mDNS Phase-1                       = OPTIONAL / supporting only
LLMNR from Android                 = NOT OBSERVED
LLMNR live Android extraction      = NOT TESTED because no traffic existed
```

Recommended durable form, if later justified:

```text
mdns_present = true
service_family = googlecast
rrtype = PTR
bounded observation count
```

Do not retain arbitrary raw local service/device names as a normal fingerprint dataset.

---

## 5.8 IPv6 — VISIBILITY PASS / ROUTED GUEST IPv6 UNAVAILABLE

A 60-second IPv6 observation on the current mixed SPAN showed the controlled Android using:

```text
link-local IPv6 = fe80::bc00:7dff:fe9b:42e
mDNS multicast  = ff02::fb
ICMPv6 traffic  = ff02::16 and ff02::2 related activity
```

The link-local address is consistent with the observed local MAC binding in this capture window.

No global `2000::/3` or ULA address and no routed guest IPv6 traffic were observed for the controlled Android.

### IPv6 architecture decision

```text
IPv6 frame visibility               = PASS
Android link-local visibility       = PASS
MAC ↔ link-local binding            = PASS
Global / ULA Android address        = NOT OBSERVED
Routed guest IPv6                   = UNAVAILABLE on current router baseline
Phase-1 core requirement            = NO
Future collector IPv6 support       = REQUIRED
```

The future architecture must accept IPv6 evidence when it exists, but Phase-1 classification must not depend on global IPv6 because the current guest environment does not provide it.

---

# 6. SPAN DUPLICATION — HARD DESIGN REQUIREMENT

The research repeatedly proved mirrored duplication:

```text
DHCP       ≈ duplicated
TLS/QUIC   ≈ duplicated
DNS        exactly 466 raw → 233 unique in bounded sample
TCP SYN    128 raw → 64 unique
mDNS       multicast path produced ≈ ×4 copies
capacity   ≈ ~50% duplicate packets/bytes in broader captures
```

A production evidence pipeline therefore requires deterministic deduplication **before evidence counts are interpreted**.

The Architect should explicitly define a dedup contract. It must be protocol-aware enough not to collapse real retransmissions or repeated application events.

Research does not prescribe the final algorithm, but candidate inputs include bounded combinations of:

```text
capture timestamp bucket
L2/L3/L4 tuple
packet length
protocol-specific transaction identifiers
selected immutable header bytes/hash
capture source identifier
```

Dedup itself must be measurable so operators can see raw packet count, dedup count and dedup ratio.

---

# 7. SENSOR CAPACITY PROOF

Current research sensor:

```text
Windows 10 desktop
Intel Core i3-7100
~32 GB RAM
Wireshark / TShark 4.6.8
Npcap
physical Ethernet capture interface
```

## 7.1 Full snaplen bounded capture

Approximate 3-second capture:

```text
actual duration            = 3.055 s
PCAPNG size                ≈ 75.8 MiB
packets                    = 91,347
frame bytes                = 76,400,063
raw mirrored packet rate   ≈ 29.9 kpps
raw mirrored L2 rate       ≈ 200 Mbit/s
write rate                 ≈ 26 MB/s
interface drops            = 0
bounded dedup unique       ≈ 46,060
packet duplication         ≈ 49.6%
byte duplication           ≈ 50.1%
approx useful rate         ≈ 100 Mbit/s / 15.1 kpps
```

## 7.2 Snaplen 96 bounded capture

Approximate 10-second capture:

```text
duration                   = 9.985 s
file size                  = 25.33 MiB
packets                    = 223,823
raw mirrored packet rate   ≈ 22.4 kpps
original L2 rate           ≈ 162.3 Mbit/s
written rate               ≈ 15.5 Mbit/s / 2.66 MB/s
interface drops            = 0
dedup unique               ≈ 113,173
packet duplication         ≈ 49.4%
approx useful rate         ≈ 82.8 Mbit/s / 11.3 kpps
```

## 7.3 Capacity verdict

```text
Current bounded sensor feasibility   = PASS
~22–30 kpps raw mirror handling      = PASS in bounded windows
~160–200 Mbit/s raw mirror handling  = PASS in bounded windows
capture drops                        = 0
SPAN duplication                     ≈ 50% confirmed
continuous full PCAP retention       = REJECT
streaming feature extraction         = REQUIRED
long-duration maximum capacity       = NOT TESTED / not required to close research
```

This proves feasibility at current observed rates; it does not authorize indefinite PCAP capture or claim long-term capacity under every future network load.

---

# 8. TOOL EVALUATION

## 8.1 Suricata 8.0.6 live/offline proof

Official Windows x64 Suricata 8.0.6 package was administratively extracted for research only; no Suricata service installation or live capture was started.

Verified build capabilities included:

```text
Suricata 8.0.6 RELEASE
Npcap = yes
JA3   = yes
JA4   = yes
```

All Suricata tests were offline against bounded PCAP files.

### Proven extractor coverage

| Source | Suricata result | Architecture use |
|---|---|---|
| DHCP | Good normalized protocol extraction; exact PRL/order incomplete | Primary + small DHCP parser |
| TLS | ClientHello, SNI, extensions, JA3, JA4 | **Primary** |
| QUIC | v1, ClientHello, SNI, extensions, JA3, JA4 | **Primary** |
| DNS | Full structured request/response data | Optional/transient only |
| mDNS | Native structured events | Optional/supporting |
| TCP flow | SYN/state visible, fingerprint vector insufficient | Small SYN parser required |

### Suricata verdict

```text
Primary production extractor candidate = PASS
```

## 8.2 tshark / dumpcap

Already demonstrated as the best research/reference layer for:

```text
exact packet truth
DHCP option order
TCP SYN options
bounded capture
cross-checking Suricata extraction
manual QUIC/TLS validation
```

Recommended role: **lab oracle / acceptance evidence**, not the main production evidence engine.

## 8.3 Zeek

Desk assessment remains useful: strong semantic/correlation framework and potential companion, but live installation is no longer required to establish feasibility because Suricata already covered the required core protocol surface.

Recommended Phase-1 role:

```text
optional / not required
```

## 8.4 p0f

p0f remains conceptually relevant for passive TCP/IP OS-family comparison, but it is not required for the architecture and must not be trusted as an authoritative OS label without local validation.

Recommended Phase-1 role:

```text
optional weak oracle / not required
```

---

# 9. SOURCE FEASIBILITY MATRIX — FINAL

| SOURCE | LIVE VISIBILITY | PRIMARY TOOL | IDENTITY BINDING | PRIVACY | QUALITY | PHASE-1 DECISION |
|---|---|---|---|---|---|---|
| Existing Omada/CaptivPortal facts | PASS | Existing services/DB | Existing MAC/device_id/Visit relationships | Existing policy | Strong contextual | **CORE / REUSE** |
| DHCP Vendor Class / Client-ID / selected fields | PASS | Suricata | source MAC → device identity | Moderate | Strong supporting | **CORE** |
| DHCP exact PRL / option order | PASS via packet truth | small parser + tshark oracle | source MAC | Moderate | Strong | **CORE** |
| TCP SYN stack vector | PASS | small parser + tshark oracle | source MAC/IP/time | Moderate | Strong supporting | **CORE-SUPPORTING** |
| Portal UA | PASS | portal request extractor | portal client MAC/IP/session | Moderate-high | Strong but context-variable | **CORE** |
| Low-entropy UA Client Hints | PASS | portal request extractor | same | Moderate | Strong when supplied | **CORE** |
| High-entropy UA-CH via Accept-CH | NOT TESTED / would require behavior change | portal | same | High | Potentially strong | **DEFER** |
| JS high-entropy fingerprint | NOT TESTED / active page behavior | JS | same | High | Potentially strong | **REJECT from passive core / DEFER** |
| TLS JA3 | PASS | Suricata | flow source MAC/IP | Moderate | **Very weak exact stability** | **DO NOT USE AS PRIMARY** |
| TLS JA4 | PASS | Suricata | flow source MAC/IP | Moderate | Strong normalized family signal | **CORE** |
| QUIC JA3 | PASS | Suricata | flow source MAC/IP | Moderate | **Very weak exact stability** | **DO NOT USE AS PRIMARY** |
| QUIC JA4 | PASS | Suricata | flow source MAC/IP | Moderate | Strong normalized family signal | **CORE where present** |
| QUIC exact transport params/order | PASS manually / incomplete in EVE | optional small parser | flow source | Moderate | Potential additional value | **OPTIONAL** |
| Raw TLS/QUIC SNI | PASS in this sample | Suricata | flow source | **High** | Browsing destination, not device truth | **REJECT durable** |
| DNS A / HTTPS behavior | PASS | Suricata | source MAC/IP | **High raw** | Optional capability clue | **OPTIONAL normalized only** |
| Raw DNS history | PASS for plain DNS only | Suricata | source MAC/IP | **High** | Intrusive/incomplete | **REJECT durable** |
| mDNS service family | PASS | Suricata | source MAC | Medium-high raw | Weak ecosystem clue | **OPTIONAL** |
| LLMNR | NOT OBSERVED on Android | Suricata if emitted | source MAC | Medium-high raw | Platform-supporting only | **OPTIONAL / no Android proof** |
| IPv6 link-local behavior | PASS | packet extractor | source MAC/time | Moderate | Supporting | **SUPPORTED, not Phase-1 dependency** |
| Global/routed IPv6 | UNAVAILABLE current baseline | — | — | — | — | **NOT REQUIRED** |
| MAC OUI | Existing MAC available | derived | direct | Low | Weak when global MAC | **SUPPORTING** |
| Local-admin/private MAC bit | PASS from observed MAC | derived | direct | Low | Useful qualifier | **SUPPORTING** |
| Existing connection/visit behavior | PASS existing | Visit/Observation | existing device_id/MAC | Existing policy | Supporting | **REUSE; do not recollect** |

---

# 10. PRIVACY AND RETENTION BOUNDARY

## 10.1 Never normal durable evidence

```text
general raw PCAP
raw DNS query history
raw browsing-domain history
raw SNI history
arbitrary mDNS/LLMNR device/service names
full packet payload
```

## 10.2 Prefer normalized durable evidence

Good candidates:

```text
DHCP PRL vector
DHCP option-order vector
selected DHCP capability booleans
TCP SYN normalized vector
JA4 and/or stable JA4 components
TLS/QUIC protocol capability fields
portal platform/mobile/runtime/WebView normalization
local-admin MAC qualifier
optional normalized mDNS service family
optional normalized DNS capability/ecosystem feature
extractor/schema/rule versions
source availability/quality state
```

## 10.3 Raw User-Agent

Raw UA can contain model and OS details and varies by request context. If temporarily captured for normalization, it should have short bounded retention or no durable retention at all. The durable layer should store normalized facts plus provenance/version, not assume one UA string permanently represents a device.

## 10.4 Destination identifiers

SNI, DNS and some local-discovery names describe where/how the user is communicating. They are not needed as long-term visitor browsing history to classify a device. Any future rule that consumes them should preferably transform them transiently to a coarse, explicitly justified evidence feature and discard the raw name.

---

# 11. IDENTITY CORRELATION CONTRACT FOR ARCHITECTURE

## 11.1 Primary binding

Within the current CaptivPortal identity model:

```text
packet / portal observation
        ↓
observed MAC
        ↓
exact Visitor Registry lookup
        ↓
device_id
```

The evidence record must preserve the observed MAC even after `device_id` is resolved so that the original binding can be audited.

## 11.2 IP fallback

Only if a source lacks MAC:

```text
IP + observed_at + site/capture scope
        ↓
exact current/lease/observation resolution valid at that time
        ↓
MAC
        ↓
device_id
```

Rejected:

```text
IP-only long-term identity
nearest-device fuzzy match
cross-MAC merge based on similar fingerprint
cross-site private-IP assumptions
```

## 11.3 Private MAC rule

The controlled Android itself used a locally administered MAC. Therefore private/randomized MAC handling is not theoretical.

**Hard invariant:**

```text
fingerprint similarity can increase classification confidence
fingerprint similarity cannot merge two different MAC/device_id identities
```

Cross-MAC continuity, if ever desired, is a different future architecture problem and is outside this task.

---

# 12. RECOMMENDED PROCESS TOPOLOGY

## 12.1 Hard boundary

The passive collector must **not** run inside the captive authorization/request execution path.

Required failure behavior:

```text
sensor down              → portal still works
capture missing          → portal still works
Suricata down            → portal still works
evidence writer down     → portal still works
classifier down          → portal still works
Device Card enrichment missing → source facts remain available
```

## 12.2 Recommended components

Conceptual topology:

```text
Catalyst SPAN / passive feed
        ↓
Packet Sensor
        ├─ Suricata 8.x
        ├─ DHCP exact-vector parser
        ├─ TCP SYN exact-vector parser
        └─ optional QUIC TP parser
        ↓
Normalized Evidence Adapter
        ↓
Future Evidence Repository
        ↑
Portal Header Evidence Adapter
        ↑
CaptivPortal request path (read-only evidence emission; auth independent)

Existing Registry / Observation / Current State / Visit Lifecycle
        ↓
Identity + context resolver
        ↓
Future classifier
        ↓
Derived classification / confidence
        ↓
Admin read surfaces
```

The exact production sensor host is intentionally **not selected by research**. The key architectural requirement is a separate service/failure domain and a passive feed. The bounded hardware test proves a modest dedicated sensor can handle the observed current mirror rate without drops.

---

# 13. NORMALIZED EVIDENCE MODEL — ARCHITECTURE INPUT ONLY

No DB schema is authorized, but the future architecture should be able to represent at least:

```text
evidence_id / immutable record identity
source_kind
source_subtype
extractor_name
extractor_version
feature_schema_version
observed_at
capture_scope / site_id
observed_mac
observed_ip when useful
device_id when exact-resolved
visit_id / auth_session_id only when exact-resolved
availability state
quality state
privacy class
normalized payload
rule/version for rule-derived features
```

Important semantic separation:

```text
RAW OBSERVATION
    what a source actually said

NORMALIZED EVIDENCE
    stable machine representation of that source observation

CLASSIFICATION
    inferred device/OS/runtime conclusion + confidence

GROUND TRUTH
    independently known test label
```

These four concepts must not be collapsed into one table/field or one authoritative string.

---

# 14. CLASSIFIER INPUT GUIDANCE

Research supports a future evidence fusion model, not a single signature lookup.

Recommended source classes:

### Strong/core

```text
DHCP exact vector/family
TLS JA4 family/components
QUIC JA4 family/components when present
portal UA + low-entropy CH normalization
```

### Strong supporting

```text
TCP SYN normalized stack vector
selected existing controller facts
```

### Weak/supporting

```text
hostname when available
MAC global OUI when usable
private/local-admin MAC qualifier
mDNS service family
normalized DNS capability/ecosystem hints
existing connection behavior
```

### Never authoritative

```text
JA3 exact hash
SNI/domain history
one raw UA string
p0f OS label without validation
one DNS name
one mDNS service
private MAC OUI
```

The Architect should define explicit confidence behavior for:

```text
source missing
source contradictory
source stale
source version changed
multiple observations disagree
only one source available
```

“Unknown” is a valid classification state and must be preferred over forced certainty.

---

# 15. IMPORTANT FALSE-POSITIVE / STABILITY FINDINGS

The live work produced several concrete anti-assumptions that should directly influence architecture:

1. **JA3 exact hashes are not stable enough** for the observed modern Chromium TLS/QUIC client because extension order is permuted.
2. **JA4 is materially more stable**, but still has multiple legitimate variants for one physical device/runtime. Treat JA4 as family/component evidence, not unique identity.
3. **One physical device can emit different User-Agent strings** depending on WebView, normal Chrome, captive/API context and browser version.
4. **DHCP hostname may be absent**; absence is not evidence of a platform.
5. **Private MAC invalidates hardware-vendor inference from OUI.**
6. **DNS and SNI primarily describe destinations/apps**, not the device itself.
7. **mDNS service discovery reflects installed capabilities/apps/ecosystem**, not exact hardware truth.
8. **IPv6 link-local behavior can exist even while routed/global guest IPv6 is unavailable.**
9. **SPAN duplication is large enough to materially corrupt counts** if dedup is not designed explicitly.
10. **Capture/parser success must not become an auth dependency.**

---

# 16. WHAT PHASE 1 SHOULD EXCLUDE

The Architect should keep the first implementation draft free of:

```text
active OS scanning
Nmap-style probes
special crafted TCP/TLS/QUIC probes
cross-MAC identity merging
person identification
continuous full PCAP retention
visitor DNS browsing history
raw SNI history
high-entropy Client Hints requiring Accept-CH by default
JavaScript high-entropy fingerprint collection by default
LLMNR dependence
routed IPv6 dependence
p0f as canonical authority
JA3 as primary fingerprint
```

This keeps V1 passive, bounded, privacy-minimized and operationally independent from captive authorization.

---

# 17. ARCHITECTURE QUESTIONS THAT REMAIN — NOT RESEARCH BLOCKERS

The following are now design decisions for the Architect, not reasons to continue live research:

```text
1. Exact production sensor deployment location/service ownership.
2. Capture-scope configuration model and Site mapping.
3. Deterministic dedup contract.
4. Exact normalized evidence contract and storage ownership.
5. Retention periods by privacy class.
6. Identity resolver API/boundary to Visitor Registry / Visit Lifecycle.
7. Which JA4 components/full values are retained.
8. Whether exact QUIC transport parameters add enough value for V1.
9. Whether optional DNS/mDNS features are worth their privacy cost in V1.
10. Classifier output taxonomy and confidence model.
11. Staleness/contradiction semantics.
12. Metrics/health/operational observability.
13. Feature flags and rollback behavior.
14. Admin read-surface integration boundaries.
15. Multi-platform labeled acceptance matrix required before production trust.
```

---

# 18. REQUIRED FUTURE ACCEPTANCE GATES

Research is complete, but an implementation task should not be accepted into production without at least these gates.

## Gate A — capture/sensor

```text
correct capture scope
no auth coupling
bounded drops at expected load
SPAN dedup proven
no general long-PCAP persistence
```

## Gate B — extractor contracts

```text
DHCP exact PRL/order matches packet oracle
TCP SYN vector matches packet oracle
TLS/QUIC JA4 matches Suricata/reference evidence
portal UA/CH normalized without changing auth behavior
privacy-rejected fields are not durably stored
```

## Gate C — identity

```text
exact MAC → device_id resolution
safe IP/time fallback only when required
no fuzzy device merge
no cross-MAC merge
site/capture scope enforced
```

## Gate D — classifier

```text
source evidence remains independently queryable
classification includes confidence/provenance
unknown state supported
contradictory evidence tested
one source cannot silently override all others
```

## Gate E — labeled device matrix

Before trusting broad OS/device claims in production, validate owner-controlled labeled samples across platforms as available:

```text
Android
Apple iOS/iPadOS
Windows
macOS if available
Linux if available
```

Unavailable platforms remain `NOT TESTED`; they must not receive invented accuracy claims.

## Gate F — failure isolation

```text
stop sensor       → captive access still passes
stop parser       → captive access still passes
break evidence DB → captive access still passes
break classifier  → captive access still passes
```

---

# 19. FINAL ARCHITECT HANDOFF

The original research questions can now be answered as follows.

### Can CaptivPortal collect useful fingerprint evidence passively?

**YES. Live PASS.**

### Is the current network capture point viable?

**YES for bounded proof.** Original client MAC/IP and all required core protocol families were observable pre-NAT. Current research SPAN is mixed/untagged and therefore is not itself the final production configuration.

### What is the recommended main parser?

**Suricata 8.x.** It was proven offline against real current guest captures for DHCP, TLS, QUIC, DNS and mDNS.

### Does Suricata replace all custom extraction?

**NO.** Exact DHCP PRL/option order and full TCP SYN stack vectors require a small packet-level feature extractor. Exact QUIC transport-parameter values/order are optional and would also need dedicated extraction if selected.

### What are the strongest V1 evidence sources?

```text
existing CaptivPortal/Omada context
DHCP exact vector
portal UA / low-entropy Client Hints
TLS JA4
QUIC JA4 when available
TCP SYN normalized stack vector
```

### What should not be used as primary truth?

```text
JA3 exact hash
one UA string
DNS/SNI destination history
p0f label
hostname
OUI under private MAC
mDNS alone
```

### Can raw traffic be retained as a normal product feature?

**NO.** Continuous/full PCAP and raw destination history are rejected. The design should stream-extract normalized evidence and discard sensitive/raw data quickly.

### Can fingerprinting affect guest authorization?

**NO.** It must remain informational/enrichment only unless a completely separate future security architecture explicitly changes that policy.

### Can different private MACs be auto-merged because fingerprints look similar?

**NO. Hard reject.**

### Is current hardware capacity plausible?

**YES for current observed bounded rates.** The sensor handled approximately 22–30 kpps and 160–200 Mbit/s raw mirrored traffic with zero observed capture drops. This proves feasibility, not unlimited future capacity.

### Is more live research required before the Architect can draft the next task?

**NO.** The remaining questions are architecture/design decisions and later implementation acceptance gates. Multi-platform labeled validation is still required before broad production classifier trust, but it does not block the architecture draft.

---

# 20. RECOMMENDED NEXT PROJECT STATE

After Architect accepts this research:

```text
DEVICE-FINGERPRINT-00                → CLOSED / RESEARCH PASS
TASK-DEVICE-FINGERPRINT-01-DRAFT     → may be prepared by Architect
CODER                                → remains HOLD
IMPLEMENTATION                       → remains NOT AUTHORIZED
```

The Architect should return a controlled architecture/TZ handoff to Tech Lead for review before any Coder task is issued.

---

# APPENDIX A — RESEARCH ARTIFACTS / LIVE EVIDENCE

Primary bounded captures used during research:

```text
guest-dhcp-01.pcapng
guest-tcp-syn-01.pcapng
guest-tls-01.pcapng
guest-quic-01.pcapng
guest-dns-01.pcapng
guest-local-discovery-01.pcapng
```

Suricata offline evidence directories:

```text
suricata-dhcp-...
suricata-tls-...
suricata-quic-01
suricata-dns-01
suricata-local-discovery-01
suricata-tcp-syn-01
```

Suricata research binary:

```text
Suricata 8.0.6 RELEASE
Windows x64 administrative extraction
live service installation = NO
live Suricata capture      = NO
all tested analysis        = offline -r PCAP
```

---

# APPENDIX B — RESEARCH SAFETY / PRIVACY RECORD

The research intentionally used:

```text
owner-controlled device for destructive/identifying validation
bounded temporary packet captures
no active OS scan
no crafted probing
no visitor classifier tuning from unknown ground truth
no long-term PCAP requirement
no production schema change
no production collector deployment
no authorization behavior change
```

During packet analysis, raw destination names were necessarily visible in bounded research output. Their presence in a research artifact is evidence of the privacy risk and **not** a recommendation to store them in production.

---

# APPENDIX C — ARCHITECTURAL NON-NEGOTIABLES

```text
1. Passive only for Phase 1.
2. Auth path remains independent.
3. Existing domain ownership is reused, not duplicated.
4. Raw observation ≠ normalized evidence ≠ classification ≠ ground truth.
5. MAC is current identity binding, not global person identity.
6. No automatic cross-MAC merge.
7. Unknown/conflicting evidence is first-class.
8. Extractor/version provenance is stored with normalized evidence.
9. SPAN dedup is mandatory.
10. Raw PCAP/DNS/SNI browsing history is not a normal durable feature.
11. JA3 is not a primary fingerprint.
12. JA4 is evidence, not identity.
13. Multi-platform accuracy claims require labeled validation.
14. Failure of fingerprinting never fails captive access.
```

---

## FINAL TECH LEAD RESEARCH VERDICT

`DEVICE-FINGERPRINT-00` has achieved its research objective. The current CaptivPortal environment can support a passive, privacy-minimized, multi-source fingerprint evidence layer without active probing and without coupling it to captive authorization. The capture path, source visibility, primary parser, parser gaps, privacy hazards, duplication behavior and bounded hardware feasibility have all been demonstrated sufficiently to move from research into **architecture drafting**.

Implementation remains explicitly unauthorized until the Architect produces the next controlled design and Tech Lead/Owner accept it.
