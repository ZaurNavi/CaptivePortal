# DEVICE-FINGERPRINT-00 — FINAL Research Handoff to Architect — R2

**Project:** CaptivPortal  
**Research:** Passive Mobile / Personal Device Fingerprinting — Source Feasibility & Architecture Inputs  
**Date:** 2026-09-14  
**Prepared by:** Tech Lead research stream for Owner / Architect  
**Repository baseline:** `3dc85735ddf5d05dd20733d15dfe1c22c9c4fde5`  
**Repository tree:** `8312658be3ba272998f46212d9bad76950e3867e`

---

## 0. CONTROL STATUS

```text
DEVICE-FINGERPRINT-00          = FINAL RESEARCH HANDOFF COMPLETE (R2)
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

This R2 document closes the research handoff against the original 30-section research brief. It explicitly distinguishes PASS/CONDITIONAL/FAIL/NOT TESTED and does not hide unmeasured sub-items. It does **not** authorize implementation. Its purpose is to give the Architect enough verified input to prepare a future `TASK-DEVICE-FINGERPRINT-01-DRAFT` without guessing about the current network, capture visibility, protocol availability, parser capability, privacy boundary, or sensor feasibility.

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

## 5.2 TCP SYN — PASS / PHASE-1 WEAK SUPPORTING

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
| TCP SYN stack vector | PASS | small parser + tshark oracle | source MAC/IP/time | Moderate | Strong supporting | **PHASE-1 WEAK SUPPORTING** |
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

Research placement recommendation for the first architecture draft is **D — separate physical sensor**, because this is the only packet-capture placement proven live and it provides the cleanest failure/privilege isolation. The exact hardware lifecycle and production sizing remain Architecture/implementation decisions; option C may only be reconsidered after an explicit capture-interface and resource proof.

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


---

# R2 FORMAL REQUIREMENT-CLOSURE ADDENDUM

This addendum is part of the FINAL handoff. It closes the formal reporting gaps found when the first FINAL was checked line-by-line against the original `DEVICE-FINGERPRINT-00 — Passive Source Feasibility Research` brief.

A `NOT TESTED` result below is intentional. The research brief explicitly permits `NOT TESTED`; it is preferable to inventing a PASS. Items marked `NOT TESTED / NOT BLOCKING` are deferred to implementation acceptance where they do not affect the architectural boundary decision.

## R2-1. Original brief gate status

```text
DEVICE-FINGERPRINT-00              = RESEARCH HANDOFF COMPLETE
LIVE BOUNDED CORE FEASIBILITY      = PASS
ARCHITECTURE DRAFT                 = UNBLOCKED
CODER                              = HOLD
IMPLEMENTATION                     = NOT AUTHORIZED
PRODUCTION FEATURE                 = FORBIDDEN UNTIL SEPARATE OWNER AUTHORIZATION
```

The next authorized activity after Architect review is preparation of `TASK-DEVICE-FINGERPRINT-01-DRAFT`. No Coder task is authorized by this handoff.

---

# R2-2. TOPOLOGY-AND-CAPTURE-VISIBILITY — capture-point alternatives

The research requirement was to consider multiple possible capture locations, not merely prove that SPAN exists. The live proof supports exactly one packet-capture topology today: Catalyst SPAN into a dedicated physical sensor.

| Candidate capture point | Live tested? | Original MAC | Original client IP | Pre-NAT | DHCP/TCP/TLS/QUIC/DNS | VLAN tag in tested mode | Both directions | Research decision |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Catalyst SPAN → dedicated physical sensor Gi1/0/40 | **YES** | PASS | PASS | PASS | PASS for tested protocols | **NO** in current untagged mixed SPAN | PASS for tested unicast flows | **PROVEN / RECOMMENDED BASIS** |
| Existing server/hypervisor NIC | NO | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | Do not assume |
| CaptivPortal VM direct packet capture | NO for guest L2 packet feed | NOT TESTED | Portal HTTP real guest IP PASS, packet L2 NOT TESTED | N/A for portal requests | Portal headers only proven | N/A | N/A | **Not a proven packet sensor** |
| Router-side packet capture | NO | NOT TESTED as capture surface | Router ARP/DHCP/config independently confirms client/network facts | Router is NAT boundary | NOT TESTED as general capture engine | N/A | NOT TESTED | Validation/context only in this research |
| Other passive TAP/mirror | NO | NOT TESTED | NOT TESTED | depends | NOT TESTED | depends | NOT TESTED | No evidence |

**Research recommendation:** choose **D. separate physical sensor** for the first architecture draft because it is the only packet-sensor placement proven live and it gives the cleanest privilege/failure isolation. Option C (separate sensor process/VM on the same host) may be reconsidered only after a future explicit NIC/capture/load proof; it is not proven here.

The current mixed VLAN10+20 SPAN configuration is a research arrangement, not a production capture-scope contract. Site/VLAN scope must be explicit in future design; missing 802.1Q tags must never be guessed.

---

# R2-3. EXISTING-FACT-INVENTORY

This is the ownership-level inventory required by the brief. Exact table/column names are an implementation-time repository contract; this research determines whether the fact is already owned by CaptivPortal and therefore must **not** be recollected from packets.

| FACT | SOURCE DOMAIN | PERSISTED? | HISTORICAL? | CURRENT? | device_id available/resolvable? | MAC | IP | timestamp | already useful for fingerprint/context? |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| controller `device_type` / canonical `device_type_key` | Observation / Current State | YES | YES via observation history | YES | YES/resolvable | YES | YES | YES | supporting context; **reuse** |
| controller/client name | Observation / Current State | YES | YES | YES | YES/resolvable | YES | YES | YES | weak supporting; reuse |
| hostname | Observation / Current State where supplied | YES when supplied | YES when observed | YES when supplied | YES/resolvable | YES | YES | YES | weak/conditional; reuse |
| `system_name` | Observation / Current State where supplied | YES when supplied | YES | YES | YES/resolvable | YES | YES | YES | weak supporting; reuse |
| `connect_device_type` | Observation / Current State where supplied | YES when supplied | YES | YES | YES/resolvable | YES | YES | YES | controller hint only; reuse |
| MAC | Visitor Registry / Observation / Current State | YES | YES | YES | direct identity relation | YES | — | YES | identity binding, not classifier truth |
| IPv4 / observed IPv6 | Observation / Current State | YES | YES | YES | YES/resolvable | YES | YES | YES | correlation/context; reuse |
| SSID | Observation / Current State / portal context | YES/available | YES where observed | YES | YES/resolvable | YES | YES | YES | context; reuse |
| AP MAC/name | Observation / Current State / portal context | YES | YES | YES | YES/resolvable | YES | YES | YES | context; reuse |
| radio / band / channel | Observation / Current State | YES | YES | YES | YES/resolvable | YES | YES | YES | supporting behavior/context; reuse |
| RSSI / SNR | Observation / Current State/history | YES | YES | YES | YES/resolvable | YES | YES | YES | supporting behavior; reuse |
| active/auth state | Current State / Visit/Auth lifecycle | YES | historical via lifecycle/observations | YES | YES | YES | YES | YES | context; reuse |
| uptime / connection duration | Current State / Observation / lifecycle-derived | YES where source provides | YES/derivable | YES | YES | YES | YES | YES | behavior support; reuse |
| traffic counters | Traffic/Observation read surfaces | YES | YES where retained | YES | YES/resolvable | YES | YES | YES | behavior support; reuse |
| Visit duration/state | Visit Lifecycle | YES | YES | current visit available | YES | YES | IP/context where present | YES | behavior support; reuse |
| Visitor Registry snapshots | Visitor Registry | YES | YES | current identity available | direct | YES | context-dependent | YES | identity/history; reuse |
| Current State facts | Current State | YES | snapshot/current | YES | YES | YES | YES | YES | current context; reuse |
| Observation client history | Observation Storage | YES | YES | latest derivable/current feeds exist | YES/resolvable | YES | YES | YES | history/context; reuse |

**Rule:** packet collection must not duplicate these domains merely because the same values can also be inferred from packets.

---

# R2-4. CAPTURE SAFETY RESULT

```text
Active scanning / Nmap OS scan          = NOT PERFORMED
Banner grabbing                         = NOT PERFORMED
SNMP probing of clients                 = NOT PERFORMED
HTTP probing of clients                 = NOT PERFORMED
Crafted TCP/TLS/QUIC probes             = NOT PERFORMED
Controlled ground truth                 = Owner-controlled Android only
Raw PCAP                                = bounded temporary lab artifacts
Git commit of raw PCAP                  = NO
Normal project log ingestion of PCAP    = NO
Production collector/service            = NO
Production schema/worker changes        = NO
```

The final architecture report uses normalized/sanitized feature descriptions. Sensitive destination names encountered during raw tool output are not proposed as durable evidence.

---

# R2-5. DHCP REQUIREMENT CLOSURE

| DHCP item | Result |
|---|---|
| Discover | PASS |
| Request | PASS |
| client MAC | PASS |
| hostname option | **ABSENT in controlled Android sample** |
| client identifier | PASS |
| vendor class identifier | PASS: `android-dhcp-13` |
| user class | NOT OBSERVED / no positive evidence |
| parameter request list | PASS, exact 12-item PRL manually verified |
| ordered DHCP option list | PASS via packet truth |
| requested IP | PASS |
| maximum message size | PASS: 1500 |
| FQDN option | NOT OBSERVED in controlled sample |
| vendor-specific client options | no stable client-provided vendor payload established; NOT CLAIMED |
| other stable client options | option 80/108/114 capability-related behavior observed as documented |

Platform matrix:

```text
Android       = PASS / controlled Nokia G21
Apple iOS     = NOT TESTED
Windows       = NOT TESTED at packet-level DHCP ground truth
macOS         = NOT TESTED
Linux         = NOT TESTED
```

These unavailable platforms are deliberately not assigned inferred PASS/FAIL.

---

# R2-6. PORTAL-UA-CLIENT-HINTS-PROOF — passive vs requested entropy

| Header/evidence | Controlled live result | Category |
|---|---|---|
| User-Agent | PASS | NATURALLY SENT / PASSIVE |
| `Sec-CH-UA` | PASS | NATURALLY SENT / PASSIVE in observed Chromium/WebView contexts |
| `Sec-CH-UA-Mobile` | PASS | NATURALLY SENT / PASSIVE |
| `Sec-CH-UA-Platform` | PASS | NATURALLY SENT / PASSIVE |
| `Accept` | not recorded in the retained research excerpt | **NOT TESTED / not needed to unblock architecture** |
| `Accept-Language` | not recorded in the retained research excerpt | **NOT TESTED / not needed to unblock architecture** |
| `Sec-CH-UA-Model` | no passive CH proof | REQUIRES higher-entropy negotiation/behavior; **DEFER** |
| platform version | no passive CH proof | REQUIRES higher-entropy Client Hints; **DEFER** |
| architecture / bitness | no passive CH proof | REQUIRES higher-entropy Client Hints; **DEFER** |
| JS `getHighEntropyValues()` | NOT USED | active page behavior; **REJECT from passive Phase-1 core / DEFER** |

Important distinction: the model `Nokia G21` and Android 13 were observed in one WebView **User-Agent string**, not proved as `Sec-CH-UA-Model` / high-entropy CH fields.

Portal evidence varies by runtime/context on the same device; it must be stored as observations with provenance, not one immutable device string.

---

# R2-7. TCP/IP PASSIVE STACK REQUIREMENT CLOSURE

| TCP/IP property | Result |
|---|---|
| IP version | PASS: IPv4 in controlled SYN set |
| observed TTL | PASS: 64 |
| DF behavior | NOT TESTED / not retained in final evidence summary |
| IPv4 ID behavior | NOT TESTED |
| TCP window | PASS: 65535 |
| MSS | PASS: 1460 |
| window scale | PASS: 8 |
| SACK | PASS |
| timestamps | PASS |
| ECN | NOT TESTED |
| TCP option set | PASS |
| TCP option order | PASS: MSS→SACK→Timestamp→NOP→WindowScale |
| capture pre-NAT | PASS |
| router/NAT alteration before capture | impossible at this capture point because observation occurs before router NAT |
| AP/switch middlebox alteration independently A/B-proven | NOT TESTED; no claim beyond observed client-side vector at the selected point |

`p0f` remains optional comparison evidence only, not canonical OS authority.

---

# R2-8. TLS VISIBILITY CLASSIFICATION

| TLS evidence | Research visibility class |
|---|---|
| TLS version/capability | VISIBLE in parseable ClientHello |
| cipher suite vector | VISIBLE in parseable ClientHello |
| extension set/order | VISIBLE in parseable ClientHello |
| supported groups | VISIBLE in parseable ClientHello |
| signature algorithms | VISIBLE in parseable ClientHello |
| ALPN | VISIBLE in the tested ClientHello set; do not assume every future flow supplies equivalent usable value |
| JA3 | VISIBLE, but exact stability FAIL |
| JA4 | VISIBLE, strong normalized evidence in tested set |
| ECH extension presence | VISIBLE as extension signal |
| proof of real ECH vs GREASE | **NOT AVAILABLE from presence alone** |
| outer SNI where sent | VISIBLE in tested set, privacy-sensitive |
| inner SNI / inner ClientHello under real ECH | **HIDDEN BY ECH / NOT AVAILABLE without keys** |

Therefore TLS/SNI is not specified as universally available. JA4 is evidence, not identity.

---

# R2-9. QUIC / HTTP3 REQUIREMENT CLOSURE

```text
QUIC version v1                  = PASS
Initial visibility              = PASS
ClientHello recovery            = PASS
JA4                             = PASS / strong normalized signal
ALPN h3                         = PASS in all 28 reconstructed CH
ECH extension signal            = PASS; real-vs-GREASE CONDITIONAL
transport-parameter extension   = PASS
exact TP values/order in EVE    = NOT PROVIDED by tested Suricata output
custom QUIC parser required V1  = NO, unless Architect explicitly selects exact TP vector
```

Suricata was tested before recommending custom parsing, satisfying the research constraint.

---

# R2-10. PACKET-PARSER-TOOL-COMPARISON

`LIVE PROOF` below means proven in this CaptivPortal lab. `DESK` means a candidate capability assessment, not local runtime proof.

| Capability | Suricata 8.0.6 | tshark/dumpcap | Zeek | p0f |
|---|---|---|---|---|
| Project live/offline proof | **LIVE OFFLINE against real PCAPs** | **LIVE capture/reference** | DESK ONLY | DESK ONLY |
| Ubuntu deployment feasibility | expected suitable for Linux sensor; not installed in this lab phase | expected suitable; standard packet toolchain | expected suitable; not locally validated | expected suitable; not locally validated |
| live-interface support | product capability; Windows Npcap build confirmed, production Linux live mode not exercised | PASS in research via Npcap | DESK candidate | DESK candidate |
| required privilege boundary | packet-capture privilege required; isolate from portal | packet-capture privilege required | packet-capture privilege required | packet-capture privilege required |
| VLAN visibility | depends on feed; tested SPAN stripped tag | sees what capture feed contains | depends on feed | depends on feed |
| machine-readable output | EVE JSON PASS | structured fields/JSON-capable reference role | rich structured logs by design, not locally tested | signature output; not evidence repository by itself |
| DHCP normalized fields | PASS | PASS raw/reference | candidate | no |
| exact ordered DHCP options | **insufficient EVE** | PASS/reference | not proven here | no |
| TCP fingerprint metadata | flow/SYN only; insufficient exact vector | PASS/reference | not chosen for exact vector in this research | purpose-built passive TCP signature candidate |
| TLS fields | PASS | PASS/reference | candidate | no |
| JA3/JA4 | JA3+JA4 PASS | reference/manual possible | plugin/framework-dependent; not proven | no |
| QUIC | PASS incl. CH/JA4 | PASS/reference/manual analysis | capable ecosystem candidate, not locally proven | no |
| DNS | PASS | PASS | candidate | no |
| mDNS | PASS | PASS | candidate | no |
| LLMNR | supported candidate; no Android live traffic to prove | reference if traffic exists | candidate | no |
| IPv6 metadata | packet/app metadata support; bounded IPv6 frame visibility proven by packet tooling, not exhaustive Suricata feature test | PASS/reference | candidate | limited relevance |
| CPU/RAM in this research | **NOT MEASURED** | capture drops measured; process resource profile not measured | NOT TESTED | NOT TESTED |
| integration complexity | lowest for core structured event path | high if used as permanent parser; best oracle | additional framework/ops complexity | narrow TCP-only companion |
| custom parsing still required? | DHCP exact order + TCP SYN exact vector; optional QUIC TP | not recommended as main production parser | would not remove all project-specific normalization needs | yes for all non-TCP sources |

**Tool recommendation:** Suricata primary; small bounded raw-feature parsers only where Suricata EVE lacks required exact vectors; tshark/dumpcap acceptance oracle; Zeek/p0f not required for V1.

---

# R2-11. DNS OBSERVABILITY / PRIVACY RESULT

```text
guest-advertised resolver             = 192.168.0.1
plain UDP/53 from controlled Android  = PASS
TCP/53                                = not observed/proved in retained sample
117 unique queries / 116 responses    = observed after dedup summary
DoT/853                               = NOT OBSERVED
DoH                                   = NOT TESTED / cannot be inferred absent
HTTP3/QUIC can bypass classic DNS     = architecture must tolerate missing DNS evidence
capture before resolver               = PASS for client→192.168.0.1 query path at SPAN
```

Privacy-safe candidate flow:

```text
raw query (ephemeral)
→ bounded rule/capability match
→ normalized coarse evidence + rule version
→ raw query discarded
```

Raw FQDN retention is REJECTED.

---

# R2-12. IPv6 REQUIREMENT CLOSURE

Current guest router baseline has no routed IPv6 service. The controlled Android nevertheless emitted link-local IPv6/multicast behavior.

```text
IPv6 frames             = PASS
link-local              = PASS
RS/RA/NS/NA/DAD full matrix = NOT exhaustively classified in retained research evidence
SLAAC global            = UNAVAILABLE current network
privacy/global addresses= NOT OBSERVED
IPv6 Phase-1 dependency = REJECT
future IPv6-ready model = REQUIRED
```

---

# R2-13. mDNS / LLMNR REQUIREMENT CLOSURE

```text
mDNS Android/Google discovery     = PASS
Google Cast service-family signal = PASS
LLMNR on controlled Android       = NOT OBSERVED
Apple Bonjour/AirPlay             = NOT TESTED
Windows LLMNR                     = NOT TESTED
full IoT classification           = OUT OF SCOPE / REJECT
```

Raw local names are not normal durable evidence.

---

# R2-14. MAC / PRIVATE-MAC EVIDENCE

Controlled Android MAC:

```text
be:00:7d:9b:04:2e
```

The locally administered bit is set; therefore:

```text
private/local-admin MAC observed      = PASS
OUI hardware-vendor authority         = NOT USABLE for this MAC
same-MAC stability during bounded test= PASS within the captured research window
cross-MAC identity inference          = FORBIDDEN
```

A global OUI may be weak supporting evidence only when the MAC is globally administered.

---

# R2-15. EXISTING BEHAVIOR EVIDENCE REUSE

| Behavior | Existing fact or new passive fact? | Research action |
|---|---|---|
| session / visit duration | EXISTING | reuse Visit Lifecycle |
| reconnect / repeat visits | EXISTING | reuse lifecycle/history |
| traffic totals | EXISTING | reuse Traffic/Observation |
| current/previous activity | EXISTING | reuse Current State/Observation |
| AP association | EXISTING | reuse Observation/Current State |
| band/radio/channel | EXISTING | reuse Observation/Current State |
| roaming evidence | existing facts may make it derivable; exact canonical derivation not re-proven here | do not recollect packet-side by default |
| RSSI/SNR history | EXISTING | reuse Observation history |
| uptime/connection duration | EXISTING/source-derived | reuse |
| DHCP option behavior | **NEW PASSIVE FACT** | fingerprint domain |
| TCP SYN stack vector | **NEW PASSIVE FACT** | fingerprint domain |
| TLS/QUIC JA4 | **NEW PASSIVE FACT** | fingerprint domain |
| portal UA/CH normalization | **NEW evidence from existing request path** | fingerprint domain, no packet duplication |
| optional DNS/mDNS normalized hints | **NEW PASSIVE FACT** | optional only |

---

# R2-16. IDENTITY-CORRELATION-FEASIBILITY MATRIX

| New source | site_id at raw observation? | timestamp | source MAC | source IP | destination IP | VLAN | SSID | device_id | visit_id/auth_session |
|---|---|---|---|---|---|---|---|---|---|
| DHCP packet | capture scope/config supplies site context; not packet-native | PASS | PASS | client pre-address phase may be absent then assigned | server/gateway | tag absent in tested SPAN | not packet-native | exact MAC resolver candidate | only if exact time/MAC lifecycle relation exists |
| TCP SYN | capture scope supplies site | PASS | PASS at L2 capture | PASS | PASS | tag absent tested mode | not packet-native | exact MAC resolver candidate | exact temporal join only |
| TLS/TCP | capture scope supplies site | PASS | PASS at L2 capture | PASS | PASS | tag absent tested mode | not packet-native | exact MAC resolver candidate | exact temporal join only |
| QUIC | capture scope supplies site | PASS | PASS at L2 capture | PASS | PASS | tag absent tested mode | not packet-native | exact MAC resolver candidate | exact temporal join only |
| DNS/mDNS | capture scope supplies site | PASS | PASS at L2 capture | PASS | PASS/multicast | tag absent tested mode | not packet-native | exact MAC resolver candidate | exact temporal join only |
| Portal UA/CH | portal/site parameters/context | PASS | request path may have clientMac + real IP depending request context | PASS where supplied | portal | N/A | portal redirect context where supplied | existing portal/registry resolver | session relation may be exact in auth/session request context |

Ambiguities/races that Architecture must handle:

```text
mixed/untagged SPAN cannot itself prove VLAN/site
IP reuse across time forbids IP-only durable identity
DHCP pre-address events may not yet contain source IPv4
visitor/session state may race packet arrival
private MAC rotation creates a new MAC identity; similarity MUST NOT merge it
visit_id/auth_session_id may be unavailable for unauthenticated/pre-visit packet evidence
```

---

# R2-17. LAB-GROUND-TRUTH-EVIDENCE QUALITY MATRIX

Ground truth dataset in this research contains one controlled physical device: Nokia G21 / Android. This is sufficient for source feasibility, not for classifier population accuracy.

| SOURCE | AVAILABLE? | CONSISTENT in bounded sample? | distinguishing value | false/misleading case | privacy cost | collection cost | recommended phase |
|---|---|---|---|---|---|---|---|
| Existing controller/context | PASS | generally contextual | environment/state | controller labels may be generic/wrong | low-moderate existing | already collected | PHASE-1 CORE reuse |
| DHCP | PASS | strong stable vector in sample | OS/runtime networking family | versions/vendors can share vectors; hostname absent | moderate | low | PHASE-1 CORE |
| TCP SYN | PASS | 64/64 same vector | stack family | NAT/tunnel/kernel/path changes | moderate | low | PHASE-1 WEAK SUPPORTING (strong signal, never authority) |
| Portal UA/CH | PASS | context-variable by design | platform/runtime/WebView/model when supplied | same device emits different UA | moderate-high raw | very low | PHASE-1 CORE |
| TLS JA4 | PASS | dominant 15/18 + valid variants | client TLS family | upgrades/config/context change | moderate | medium | PHASE-1 CORE |
| QUIC JA4 | PASS | 3 families 13/13/2 | HTTP3 client family | QUIC absent/blocked or client changes | moderate | medium | PHASE-1 CORE where present |
| JA3 | PASS | 18/18 TLS and 28/28 QUIC unique | poor exact value | randomized extension order | moderate | medium | REJECT primary |
| DNS behavior | PASS plain DNS | behavior-rich, not identity-stable | optional capability/ecosystem | DoH/missing traffic/app-dependent | **high raw** | medium | PHASE-1 OPTIONAL normalized only |
| mDNS | PASS | repeated Google Cast query | ecosystem/app capability | installed apps/services dominate | medium-high raw | low | PHASE-1 OPTIONAL |
| LLMNR | no traffic | N/A | possible platform hint | absence proves little | medium-high raw | low | DEFER / optional |
| IPv6 link-local | PASS | observed | stack behavior | current network lacks routed v6 | moderate | low | PHASE-1 WEAK SUPPORTING / no dependency |
| private-MAC flag | PASS | stable in bounded window | qualifier | no vendor identity | low | trivial | PHASE-1 WEAK SUPPORTING |

No classifier rules were tuned on random visitor devices.

---

# R2-18. EVIDENCE SOURCE RANKING — exact brief categories

| Source | Ranking |
|---|---|
| Existing Omada/CaptivPortal facts | **PHASE-1 CORE** (reuse, not recollect) |
| DHCP exact vector | **PHASE-1 CORE** |
| Portal UA/default low-entropy Client Hints | **PHASE-1 CORE** |
| TLS JA4 | **PHASE-1 CORE** |
| QUIC JA4 | **PHASE-1 CORE** where present |
| TCP SYN vector | **PHASE-1 WEAK SUPPORTING** |
| Hostname | **PHASE-1 WEAK SUPPORTING** when present |
| MAC global OUI | **PHASE-1 WEAK SUPPORTING** only for globally administered MAC |
| private/local-admin MAC qualifier | **PHASE-1 WEAK SUPPORTING** |
| DNS ecosystem/capability | **PHASE-1 OPTIONAL** normalized only |
| mDNS service family | **PHASE-1 OPTIONAL** |
| LLMNR | **DEFER** until labeled useful traffic exists |
| IPv4 stack behavior | **PHASE-1 WEAK SUPPORTING** |
| routed/global IPv6 behavior | **DEFER** current network unavailable |
| existing connection behavior | **PHASE-1 WEAK SUPPORTING** via existing domains |
| JA3 exact fingerprint | **REJECT** as primary fingerprint |
| raw DNS/SNI history | **REJECT** |
| high-entropy JS/client-hint fingerprinting | **DEFER / REJECT from passive core** |

---

# R2-19. PRIVACY CLASSIFICATION

| Evidence | Privacy class | Retention recommendation |
|---|---|---|
| local-admin MAC flag / protocol capability booleans | LOW SENSITIVITY | normal normalized evidence retention candidate |
| DHCP normalized PRL/option vector | MODERATE | normalized only; no payload |
| TCP SYN normalized vector | MODERATE | normalized only |
| JA4 / normalized TLS/QUIC feature vector | MODERATE | durable candidate with extractor/schema version |
| raw User-Agent/model/OS string | **HIGH / SPECIAL RETENTION** | normalize promptly; raw none/short bounded retention |
| normalized UA platform/runtime/mobile/WebView | MODERATE | durable candidate |
| raw DNS names | **HIGH / SPECIAL RETENTION** | never normal durable history; ephemeral match only |
| raw TLS/QUIC SNI | **HIGH / SPECIAL RETENTION** | reject durable browsing history |
| arbitrary mDNS/LLMNR names | HIGH / SPECIAL RETENTION | normalize service family if justified; raw discard |
| raw PCAP/full payload | **HIGH / SPECIAL RETENTION** | lab-only bounded; reject product retention |
| existing connection behavior | MODERATE | remain in existing owning domain; fingerprint uses references/features, not duplicate raw history |

---

# R2-20. RAW VS DURABLE EVIDENCE + IRREVERSIBILITY TRADEOFF

```text
RAW ACQUISITION DATA
    → packet/header/request event
    → ephemeral normalization window
    → privacy-minimized normalized evidence
    → raw discarded according to policy
```

Examples:

```text
raw ClientHello
→ JA4 + selected normalized capabilities + extractor version

raw DNS FQDN
→ optional coarse ecosystem/capability rule result + rule version
→ FQDN discarded

raw UA
→ platform/runtime/mobile/WebView/model-if-approved normalized observation
→ raw UA discarded/short-retained
```

**Important tradeoff:** once raw data is discarded, future extractors cannot reconstruct new features that were never normalized. This is intentional privacy minimization. Therefore the future schema/version contract must allow extractor evolution, and any decision to add a new feature may require new observations rather than retroactive extraction from old raw traffic.

---

# R2-21. EVIDENCE VERSIONING INPUT

Conceptual fields required by Architecture (not a DB schema):

```text
source_kind
source_subtype
extractor_name
extractor_version
feature_schema_version
rule_version (for rule-derived evidence)
observed_at
site_id / capture_scope
observed_mac
observed_ip when useful
device_id only when exact-resolved
visit_id/auth_session_id only when exact-resolved
quality_state
availability_state
privacy_class
normalized payload
```

---

# R2-22. CAPACITY / SENSOR VIABILITY — measured vs not measured

### Measured live capture capacity

```text
~22–30 kpps raw mirrored traffic       = PASS bounded
~160–200 Mbit/s raw mirrored L2        = PASS bounded
capture interface drops                = 0
SPAN duplication                       ≈ 50%
full PCAP continuous storage           = REJECT
streaming feature extraction           = REQUIRED
```

### Requested sub-measurements not performed

```text
Suricata production parser CPU         = NOT TESTED
Suricata production parser RAM         = NOT TESTED
sustained EVE event output rate        = NOT TESTED
DHCP events/day population estimate    = NOT TESTED (needs client population/churn assumptions)
TLS/QUIC event/day production estimate = NOT TESTED
DNS event/day production estimate      = NOT TESTED
long-duration peak sensor load         = NOT TESTED
```

These omissions mean **production sizing is not complete**. They do **not** block the Architecture DRAFT because the research has already proven the protocol surface and a dedicated sensor can receive the current mirror without drops. They become mandatory Gate A sizing/soak tests before production deployment.

**Placement recommendation:** **D — separate physical sensor** for V1 design. It is the only capture placement proven live and isolates packet privileges/resource spikes from captive authorization. A future C option may be reconsidered only after an explicit capture-interface and resource proof.

---

# R2-23. FAILURE BOUNDARY — HARD CONTRACT

```text
Fingerprint acquisition failure     MUST NOT break captive authorization
Extractor failure                   MUST NOT break captive authorization
Evidence repository failure         MUST NOT break captive authorization
Classifier failure                  MUST NOT break captive authorization
Device Card enrichment unavailable  MUST NOT remove existing source facts
```

No future implementation may make packet evidence synchronous/required for authorization unless a completely separate Owner-approved security architecture supersedes this rule.

---

# R2-24. FINAL FEASIBILITY TABLE — required brief format

| SOURCE | LIVE VISIBILITY | TOOL | IDENTITY BINDING | PRIVACY | QUALITY | PHASE-1 DECISION | BLOCKERS |
|---|---|---|---|---|---|---|---|
| Existing Omada/CaptivPortal | PASS | existing domains | existing device_id/MAC/Visit | existing policy | strong context | PHASE-1 CORE / REUSE | no recollection |
| DHCP normalized | PASS | Suricata | source MAC→device_id | MODERATE | strong | PHASE-1 CORE | dedup |
| DHCP exact PRL/order | PASS packet truth | small parser | source MAC→device_id | MODERATE | strong | PHASE-1 CORE | custom bounded extractor |
| TCP SYN | PASS | small parser + tshark oracle | MAC/IP/time | MODERATE | supporting | PHASE-1 WEAK SUPPORTING | exact parser + dedup |
| Portal UA/default CH | PASS | portal adapter | portal MAC/IP/session | MODERATE/HIGH raw | strong/context-variable | PHASE-1 CORE | normalization/privacy |
| TLS JA4 | PASS | Suricata | MAC/IP/flow/time | MODERATE | strong family signal | PHASE-1 CORE | missing flows/ECH-aware semantics |
| QUIC JA4 | PASS | Suricata | MAC/IP/flow/time | MODERATE | strong where present | PHASE-1 CORE where present | QUIC may be absent/blocked |
| JA3 | PASS extraction | Suricata | flow | MODERATE | exact stability FAIL | REJECT primary | randomized order |
| raw SNI | PASS sample | Suricata | flow | HIGH | destination not device truth | REJECT durable | privacy |
| DNS capability/ecosystem | PASS plain DNS | Suricata | MAC/IP/time | HIGH raw | optional | PHASE-1 OPTIONAL normalized | DoH/missing DNS/privacy |
| raw DNS history | PASS plain DNS | Suricata | MAC/IP/time | HIGH | intrusive/incomplete | REJECT durable | privacy |
| mDNS service family | PASS | Suricata | source MAC | MODERATE-HIGH raw | weak/supporting | PHASE-1 OPTIONAL | raw-name privacy |
| LLMNR | NOT OBSERVED | Suricata candidate | source MAC | MODERATE-HIGH raw | unknown local value | DEFER | no labeled traffic |
| IPv6 link-local | PASS | packet tooling | MAC/time | MODERATE | supporting | PHASE-1 WEAK SUPPORTING | current routed v6 absent |
| routed IPv6 | UNAVAILABLE | — | — | — | — | DEFER | router baseline |
| MAC/OUI | PASS MAC | derived | direct | LOW | weak/private-MAC constrained | PHASE-1 WEAK SUPPORTING | local-admin OUI unusable |
| existing connection behavior | PASS existing | Visit/Observation | existing device_id | MODERATE | supporting | PHASE-1 WEAK SUPPORTING / REUSE | no duplicate collector |

---

# R2-25. REQUIRED REPORT INDEX

The original brief permitted the ten reports as sections of one consolidated Markdown. This R2 maps them explicitly:

```text
1. TOPOLOGY-AND-CAPTURE-VISIBILITY
   → original §§2,6 + R2-2

2. EXISTING-FACT-INVENTORY
   → original §4 + R2-3

3. PASSIVE-SOURCE-FEASIBILITY-MATRIX
   → original §9 + R2-17/R2-18/R2-24

4. PORTAL-UA-CLIENT-HINTS-PROOF
   → original §5.5 + R2-6

5. PACKET-PARSER-TOOL-COMPARISON
   → original §8 + R2-10

6. LAB-GROUND-TRUTH-EVIDENCE
   → original §3 + R2-17

7. IDENTITY-CORRELATION-FEASIBILITY
   → original §11 + R2-16

8. PRIVACY-RETENTION-RECOMMENDATION
   → original §10 + R2-19/R2-20

9. CAPACITY-SENSOR-PLACEMENT-RESULT
   → original §§7,12 + R2-22

10. FINAL-RESEARCH-HANDOFF
    → original §§17–20 + R2-26/R2-27
```

---

# R2-26. FINAL SOURCE VERDICTS

```text
Existing Omada/CaptivPortal context = PASS
DHCP                                = PASS
TCP SYN                             = PASS
Portal UA/default Client Hints      = PASS
TLS                                 = PASS
TLS JA3 primary stability           = FAIL
TLS JA4                             = PASS
QUIC                                = PASS
QUIC JA3 primary stability          = FAIL
QUIC JA4                            = PASS
DNS plain observability             = PASS
DNS as device authority             = FAIL
DoT in bounded sample               = NOT OBSERVED
DoH                                 = NOT TESTED
mDNS                                = PASS
LLMNR controlled Android            = NOT TESTED / no traffic observed
IPv6 link-local                     = PASS
Routed guest IPv6                   = UNAVAILABLE current baseline
High-entropy Client Hints           = NOT TESTED / DEFER
Cross-MAC identity merge            = REJECT
Continuous raw PCAP retention       = REJECT
Raw DNS/SNI durable history         = REJECT
Suricata primary extractor          = PASS
Dedicated physical sensor viability = PASS bounded
Production parser sizing            = NOT TESTED
```

---

# R2-27. FINAL ANSWERS REQUIRED BY THE RESEARCH BRIEF

### Can Phase 1 be implemented passively?

**YES.** Core evidence was observed without active client probing.

### Where must packet capture occur?

At a trusted **pre-NAT passive mirror/feed** that preserves original client MAC/IP. The only live-proven placement in this research is Catalyst SPAN to the dedicated physical sensor. For V1 architecture the research recommends **D — separate physical sensor**.

### Which sources are realistically available?

Core: existing CaptivPortal facts, DHCP, portal UA/default Client Hints, TLS JA4, QUIC JA4 where present. TCP SYN is strong supporting evidence. DNS/mDNS are optional and privacy-sensitive. Routed IPv6 and useful LLMNR are not available/proven in the current baseline.

### Which sources are privacy-safe enough for V1?

Normalized DHCP/TCP/JA4/portal-derived features are acceptable candidates with policy/versioning. Raw PCAP, DNS query history and SNI history are not acceptable durable V1 evidence. Raw UA/local-discovery names require bounded/ephemeral normalization.

### What should be durable normalized evidence?

Versioned source-specific normalized feature vectors plus provenance, observation time, site/capture scope, observed MAC/IP and exact-resolved identity links. Raw browsing destination history is excluded.

### Which parser/sensor stack is recommended?

Suricata 8.x primary + small DHCP exact-vector parser + small TCP SYN exact-vector parser; optional QUIC TP parser only if Architect chooses it; tshark/dumpcap as lab/acceptance oracle.

### Can current hardware host it?

A dedicated current sensor **can receive the observed bounded mirror load without drops**. Production parser CPU/RAM/soak sizing is **NOT TESTED** and must be proven before deployment. The research does not claim that the CaptivPortal VM can host the packet sensor.

### How should evidence bind to `device_id`?

Primary: observed MAC → exact Visitor Registry/current identity → `device_id`. Fallback only when MAC unavailable: site/capture scope + IP + exact observation time → valid lease/current mapping → MAC → device_id. IP-only durable identity and fingerprint-based cross-MAC merge are forbidden.

### Which proposed sources should be removed from Phase 1?

```text
JA3 as primary fingerprint
raw DNS/SNI history
continuous raw PCAP
active scans/probes
cross-MAC merge
high-entropy JS/client-hint fingerprinting
routed IPv6 dependency
LLMNR dependency
p0f as canonical authority
```

### Which questions still block Architecture DRAFT?

**NONE.** Remaining unknowns are implementation/placement/retention/acceptance decisions, not source-feasibility blockers. Production deployment remains blocked until sizing, multi-platform labeled validation, dedup, privacy and failure-isolation gates pass.

---

# R2-28. FORMAL COMPLIANCE NOTES / KNOWN UNTESTED ITEMS

The following original research sub-items were not measured and are intentionally carried forward rather than guessed:

```text
multi-platform packet ground truth beyond Android
Accept / Accept-Language retained proof
high-entropy CH model/platform-version/arch/bitness
TCP DF / IPv4-ID / ECN classification
independent AP/switch middlebox A/B comparison
DoH behavior
routed/global guest IPv6 behavior
Windows LLMNR / Apple Bonjour labeled proof
Suricata production CPU/RAM
sustained EVE output rate
population/day event estimates
long-duration soak capacity
existing host/VM packet-capture viability
```

They do not invalidate the proven passive architecture. Those relevant to production quality become acceptance gates in `TASK-DEVICE-FINGERPRINT-01-DRAFT`.

---

# R2-29. FORBIDDEN / UNCHANGED

This handoff does **not** authorize:

```text
production fingerprint collector
new DB schema
permanent worker/service
Visitor Registry schema changes
Observation schema changes
Device Card changes
classification engine
automatic profiling action
cross-MAC identity merging
active scanning or client probing
long-term raw PCAP
visitor DNS history
GitHub implementation PR
```

---

# R2-30. HANDOFF TO ARCHITECT

Architect may now prepare `TASK-DEVICE-FINGERPRINT-01-DRAFT` with exact:

```text
module boundaries
D separate-sensor topology (or a documented Owner-approved alternative after proof)
evidence contract
persistence ownership
identity binding
dedup contract
retention/privacy contract
source priorities
classification boundary
health/failure isolation
roadmap
multi-platform validation strategy
capacity/soak acceptance strategy
testing/acceptance gates
```

Tech Lead review is required before any Coder task. Coder remains HOLD.
