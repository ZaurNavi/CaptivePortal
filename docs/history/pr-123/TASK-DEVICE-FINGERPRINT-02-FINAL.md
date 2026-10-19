# TASK-DEVICE-FINGERPRINT-02-FINAL

## Core Packet Sensor + Network Evidence

**Project:** CaptivPortal  
**Program:** Device Fingerprint  
**Parent foundation:** `TASK-DEVICE-FINGERPRINT-01`  
**Research predecessor:** `DEVICE-FINGERPRINT-00 FINAL R2`  
**Revision:** `FINAL`  
**Prepared:** 2026-09-14  
**Status:** `FINAL — FOR TECHLEAD10 FINAL SOURCE / CONSISTENCY REVIEW`  
**Implementation-ready:** `YES — CONTRACT COMPLETE; EXECUTION NOT AUTHORIZED`  
**Coder:** `HOLD`  
**Implementation authorization:** `NOT GRANTED`  
**Production activation:** `NOT AUTHORIZED`

---

# 0. Final Control Gate


```text
DEVICE-FINGERPRINT-00 =
CLOSED / PASS

TASK-DEVICE-FINGERPRINT-01 =
IMPLEMENTED / MERGED / CONSUMED

TASK-DEVICE-FINGERPRINT-02 DRAFT REVIEW =
CLOSED

ARCHITECTURE =
PASS

TECHNICAL CONTRACTS =
PASS

PRE-FINAL BOUNDED ARCHITECTURE CLOSURE =
PASS

NEW BROAD RESEARCH =
NOT REQUIRED

TASK-DEVICE-FINGERPRINT-02-FINAL =
ASSEMBLED

CURRENT GATE =
TECHLEAD10 FINAL SOURCE / CONSISTENCY REVIEW

TECHLEAD10 FINAL PASS =
PENDING

OWNER IMPLEMENTATION AUTHORIZATION =
NOT GRANTED

CODER =
HOLD
```

This FINAL freezes the complete Task-02 implementation contract.

It does NOT authorize:

```text
implementation
branch
commit
push
PR
merge
deploy
production activation
```

Coder implementation begins only after:

```text
1. TechLead10 FINAL consistency PASS

AND

2. Owner explicit implementation authorization
```

---

# 1. Final Repository Baseline


Repository:

```text
ZaurNavi/CaptivePortal
```

Fresh `main` recheck immediately before FINAL assembly:

```text
HEAD =
414de85c311e72405dc25446461dcd458b5ae597

TREE =
9f267dc0944a91f7a4b81dccee8a77e0ec05fbe0
```

Current main contains:

```text
PR #122
TASK-DEVICE-FINGERPRINT-01
Device Fingerprint Evidence Foundation
```

Material repository drift from the Task-02 DRAFT source baseline:

```text
NO
```

Task-01 repository state consumed by Task-02 remains:

```text
fingerprint-evidence.service =
independent auxiliary service

API =
/api/internal/device-fingerprint/v1

direct TLS =
YES

producer Bearer + peer CIDR authorization =
YES

production EvidenceSchemaRegistry =
EMPTY before Task-02 implementation

authorized producer source kinds =
dhcp
tcp_syn
tls_client
quic_client
```

Before Coder begins implementation, TechLead10 performs the normal fresh
implementation-baseline rebind.

If `main` materially drifts before implementation authorization:

```text
STOP
→ TechLead10 source rebind
```

---

# 2. Program Boundary

Canonical staged program:

```text
DEVICE-FINGERPRINT-00
Source Feasibility / Privacy / Sensor Research
=
CLOSED / PASS

DEVICE-FINGERPRINT-01
Passive Evidence Foundation
=
IMPLEMENTED

DEVICE-FINGERPRINT-02
Core Packet Sensor + Network Evidence
=
CURRENT

DEVICE-FINGERPRINT-03
Portal UA / Client Hints

DEVICE-FINGERPRINT-03A
Multi-Platform Labeled Evidence Matrix

DEVICE-FINGERPRINT-04
Classification Engine

DEVICE-FINGERPRINT-05
Identity / Classification Integration

DEVICE-FINGERPRINT-06
Device Card / Admin Presentation
```

Task-02 core evidence:

```text
DHCP

TCP SYN

TLS JA4

QUIC JA4
```

---

# 3. Task-01 Boundary Preserved

Task-01 already owns:

```text
normalized evidence envelope

source-health envelope

HTTPS/Bearer protected ingest

producer/site/capture/source authorization

idempotent central persistence

retention

central read boundary

central runtime health

central SQLite schema
```

Task-02 MUST NOT create:

```text
second canonical evidence DB

alternative evidence API

alternative producer identity model

device_id integration

classification tables

Admin/UI storage

raw packet archive
```

Task-02 modifies Task-01 only where Task-01 explicitly reserved ownership
for later source schema registration:

```text
EvidenceSchemaRegistry production registration
```

---

# 4. Architecture Delta — Sensor Placement

Old architecture assumption:

```text
D — separate physical sensor
```

Reason at the time:

```text
same-VM packet capture path
had not been proven
```

That uncertainty is now closed.

Task-02 V1 freezes:

```text
PRODUCTION SENSOR PLACEMENT =
SAME EXISTING CAPTIVPORTAL VM

VM =
192.168.0.202

capture interface =
enp8s0
```

The old physical-sensor requirement is superseded for Task-02.

Task-01 itself is NOT reopened.

---

# 5. Proven Infrastructure Path

Accepted V1 path:

```text
Catalyst RSPAN
        ↓
OMV enp7s0f1.999
        ↓
libvirt direct/macvtap passthrough
        ↓
CaptivPortal VM
        ↓
enp8s0
        ↓
fingerprint packet sensor runtime
        ↓
normalized evidence
        ↓
Task-01 fingerprint-evidence.service
```

Infrastructure feasibility:

```text
PASS
```

Application/resource coexistence:

```text
NOT YET ACCEPTED
→ Task-02 responsibility
```

---

# 6. Proven Catalyst / RSPAN Baseline

Switch:

```text
WS-C2960S-48LPS-L
IOS 15.2(2)E9
```

RSPAN:

```text
source VLANs =
10,20

direction =
BOTH

destination =
remote VLAN999
```

Trunk:

```text
Gi1/0/48

native VLAN =
40

allowed VLANs =
40,999
```

```text
VLAN999 =
remote-span enabled
```

Old Local SPAN:

```text
Gi1/0/40 =
REMOVED
```

---

# 7. Proven OMV / KVM Transport

OMV:

```text
7.7.24-7
```

KVM plugin:

```text
7.1.9
```

libvirt:

```text
11.3.0
```

QEMU:

```text
10.0.2
```

Physical NIC:

```text
enp7s0f1
```

Existing Storage native VLAN40 endpoint:

```text
192.168.2.220/24
```

RSPAN termination:

```text
enp7s0f1.999
```

RSPAN termination properties:

```text
UP

802.1Q VLAN999

NO IPv4

NO IPv6

NO routes

NO bridge/master
```

---

# 8. Proven VM Capture Interface

Production VM primary NIC remains:

```text
enp1s0

MAC =
52:54:00:0d:2f:54

source =
br0

IPv4 =
192.168.0.202/24

default gateway =
192.168.0.1
```

UNCHANGED.

Sensor NIC:

```text
libvirt type =
direct

source =
enp7s0f1.999

mode =
passthrough

model =
virtio

MAC =
52:54:00:59:23:b8

guest interface =
enp8s0
```

Required sensor interface state:

```text
UP

NO IPv4

NO IPv6

NO IPv6 link-local

NO DHCPv4

NO DHCPv6

NO RA

NO routes

NO gateway

NO bridge/master

IPv4 forwarding for enp8s0 =
0

IPv6 forwarding for enp8s0 =
0
```

Global VM forwarding remains untouched.

---

# 9. Capture Proof Accepted

Inside the production VM on:

```text
enp8s0
```

proven:

```text
ORIGINAL L2 VISIBILITY =
PASS

ORIGINAL L3 VISIBILITY =
PASS

MULTIPLE ORIGINAL SOURCE MACs =
PASS

MULTIPLE ORIGINAL DESTINATION MACs =
PASS

SENSOR MAC DOES NOT REPLACE ORIGINAL MACs =
PASS

VLAN10 traffic =
PASS

VLAN20 traffic =
PASS

both direction visibility =
PASS where traffic exists
```

Representative protocols observed:

```text
ARP

IPv4

UDP

TCP

DNS

TCP/443

UDP/443
```

RSPAN transport VLAN tag preservation inside guest is NOT required.

---

# 10. Storage / Production Regression Baseline

Accepted after INFRA change:

```text
Storage VLAN40 =
WORKING

OMV 192.168.2.220 =
WORKING

file server 192.168.2.200 =
WORKING

NFSv4 =
WORKING

/srv/remotemount/Data_1 =
READABLE

TCP/2049 =
ESTABLISHED

primary CaptivPortal network =
WORKING

Captive Portal =
WORKING
```

Therefore:

```text
same-VM capture transport =
ACCEPTED
```

---

# 11. Hard Failure-Isolation Invariant

Permanent:

```text
FINGERPRINT SENSOR FAILURE
MUST NEVER
BECOME AUTHORIZATION FAILURE
```

Task-02 MUST NOT integrate packet capture into:

```text
run.py

captive-portal.service

Authorization request handler

Portal request path

Admin request path
```

Task-02 services are auxiliary failure domains.

---

# 12. Process / Service Topology

Task-02 V1 freezes three independent runtime roles:

```text
EXISTING:
fingerprint-evidence.service
(Task-01 central ingest + storage)

NEW:
fingerprint-sensor.service
(Task-02 raw packet parser + EVE adapter + dedup + spool + producer)

NEW:
fingerprint-suricata.service
(Task-02 Suricata protocol extraction)
```

Topology:

```text
                    enp8s0
                   /      \
                  /        \
                 ↓          ↓
fingerprint-sensor.service  fingerprint-suricata.service
raw AF_PACKET               AF_PACKET / Suricata
DHCP + TCP SYN              TLS + QUIC JA4
packet dedup                EVE
          \                 /
           \               /
            ↓             ↓
        normalized sensor pipeline
                  ↓
        bounded normalized spool
                  ↓
 HTTPS/Bearer → 192.168.0.202:9443
                  ↓
        fingerprint-evidence.service
```

No process is a child of `captive-portal.service`.

---

# 13. Existing Task-01 Transport Is Preserved

Same-VM placement does NOT weaken Task-01 transport.

Task-02 producer uses:

```text
HTTPS

URL base =
https://192.168.0.202:9443/api/internal/device-fingerprint/v1

Bearer =
existing producer credential

TLS hostname/SAN validation =
192.168.0.202
```

No switch to:

```text
plain HTTP

loopback unauthenticated ingest

Unix socket bypass

direct SQLite

shared Python object call
```

Task-01 API remains the trust boundary.

---

# 14. Producer Identity — Frozen

Task-02 uses the existing initial producer authority:

```text
producer_id =
sensor-zefer-01

capture_source_id =
zefer-span-01

site_id =
6a64f17630da7c70d232187a

Site =
Zefer_Parki

allowed_guest_cidrs =
[
  "192.168.8.0/22"
]

allowed_source_kinds =
[
  "dhcp",
  "tcp_syn",
  "tls_client",
  "quic_client"
]
```

No second producer identity is introduced.

---

# 15. Task-01 Clock / Retry Constraints Consumed

Task-02 consumes:

```text
maximum future skew =
120 seconds

maximum delayed event age =
86400 seconds

max central batch =
100 events

max normalized payload =
8192 bytes
```

Producer MUST drop from spool before delivery if an event has become too old
for Task-01 acceptance.

Task-02 does not redefine these values.

---

# 16. Capture Interface Contract

Production capture interface is EXACTLY:

```text
enp8s0
```

When enabled, config validation MUST reject any other interface.

No discovery heuristic.

Forbidden capture interfaces:

```text
enp1s0

br0

enp7s0f1

enp7s0f1.999
```

Task-02 code never modifies:

```text
IP addressing

routes

gateway

forwarding

bridge membership
```

on any interface.

---

# 17. Interface Safety Preflight

Before packet capture starts, sensor preflight verifies:

```text
interface exists

interface name == enp8s0

operstate permits capture

NO IPv4 assigned

NO IPv6 assigned

NO IPv6 link-local

NO default route through interface

NO master/bridge

NO DHCP client process configured for interface

per-interface IPv4 forwarding = 0

per-interface IPv6 forwarding = 0
```

Any violation:

```text
sensor runtime =
UNAVAILABLE

NO packet capture

NO interface mutation

NO attempt to auto-fix
```

Return exact evidence to operator.

---

# 18. Core Listener Readiness Guard


The sensor must not create packet-processing workload during the current
CaptivPortal cold-start window.

The readiness guard is TRANSPORT readiness only.

Frozen:

```text
CORE_READY_HOST =
127.0.0.1

CORE_READY_PORT =
8088

per-connect timeout =
1 second

poll interval =
10 seconds

maximum continuous startup wait =
1800 seconds
```

Criterion:

```text
successful TCP connect
to
127.0.0.1:8088
```

This proves only:

```text
core HTTP listener has bound
```

It does NOT call:

```text
/capport/api

Authorization

CAPPORT business logic

Admin

Analytics
```

Loopback is therefore not required to be a configured captive client network.

Before guard PASS, sensor CLI may perform only:

```text
CLI parse

sensor-only env/config parse

artifact identity capture

bounded TCP readiness polling
```

Before guard PASS it MUST NOT:

```text
open AF_PACKET

open/create spool DB

bind EVE Unix datagram socket

start packet parser workers

start delivery worker

trigger Suricata workload
```

If no listener exists after 1800 seconds:

```text
sensor exits non-zero
```

systemd:

```text
Restart=on-failure

RestartSec=30
```

CaptivPortal remains fully independent.

This guard does NOT solve `TASK-STARTUP-AVAILABILITY-01`.

---

# 19. systemd Dependency Direction


`fingerprint-sensor.service` has only:

```text
After=captive-portal.service
```

There is NO pull-in dependency from sensor to Task-01 evidence service and NO
pull-in dependency from sensor to Suricata.

Forbidden from sensor:

```text
Wants=fingerprint-evidence.service
Requires=fingerprint-evidence.service
BindsTo=fingerprint-evidence.service

Wants=fingerprint-suricata.service
Requires=fingerprint-suricata.service
BindsTo=fingerprint-suricata.service
```

If Task-01 evidence service is stopped/unavailable, sensor uses normalized spool
and delivery retry. Starting Task-02 MUST NOT activate Task-01.

Suricata relationship:

```text
fingerprint-suricata.service

After=fingerprint-sensor.service
BindsTo=fingerprint-sensor.service
PartOf=fingerprint-sensor.service
```

Starting sensor alone DOES NOT start Suricata.

Activation sequence remains deterministic:

```text
start sensor
→ prove raw/EVE readiness
→ separately start Suricata
```

CaptivPortal never waits for Task-02.

---

# 20. Suricata Version / Package — Frozen


Production target:

```text
Suricata =
8.0.6 RELEASE

Ubuntu package =
1:8.0.6-0ubuntu2

source =
OISF Suricata stable PPA / Ubuntu 22.04 Jammy
```

PRE-FINAL environment proof:

```text
JA4 =
SUPPORTED

AF_PACKET =
SUPPORTED

Unix socket EVE =
SUPPORTED
```

Package drift policy:

```text
suricata package =
APT hold
```

Vendor service policy:

```text
suricata.service =
masked
inactive
```

Only the Task-02 custom:

```text
fingerprint-suricata.service
```

may capture `enp8s0`.

Any Suricata version change requires explicit Task-02 compatibility recheck for:

```text
EVE schema
JA4 behavior
QUIC representation
capture behavior
performance
```

---

# 21. Suricata Role

Suricata is used only as passive protocol extractor.

Task-02 does NOT use Suricata for:

```text
IPS

packet blocking

NFQUEUE

inline forwarding

firewall verdict

file extraction

alert rules

malware detection

DNS history collection

HTTP history collection
```

Task-02 requires:

```text
TLS JA4

QUIC JA4

capture/stats health

transient L2 identity metadata
```

---

# 22. Suricata Capture Mode

Frozen:

```text
capture =
AF_PACKET

interface =
enp8s0

mode =
passive IDS

runmode =
workers

threads =
1 initially

tpacket-v3 =
enabled

copy-mode =
NONE

IPS/inline =
NO
```

No packet forwarding/copy target.

Performance tuning may change ring sizing after acceptance evidence,
but not capture semantics.

---

# 23. Suricata Capture Filter


Suricata receives only guest-network IP traffic:

```text
net 192.168.8.0/22
```

Purpose:

```text
preserve both directions
of guest TCP/TLS/QUIC flows

avoid VLAN10 unrelated IP workload

avoid duplicate raw DHCP ownership
```

Suricata does NOT add:

```text
udp port 67/68
```

outside guest IP scope.

Exact DHCP traffic is owned by the dedicated raw DHCP parser.

The Suricata BPF is performance/privacy scope, not Site identity authority.

---

# 24. EVE Unix Datagram Lifecycle


V1 EVE transport remains:

```text
unix_dgram
```

Socket:

```text
/run/captive-portal/fingerprint-sensor/suricata-eve.sock
```

Dedicated shared group:

```text
fingerprint-eve
```

Socket ownership:

```text
owner =
fingerprint-sensor

group =
fingerprint-eve

mode =
0660
```

Both service users receive only required membership in:

```text
fingerprint-eve
```

Lifecycle:

```text
1. core TCP readiness guard PASS

2. fingerprint-sensor creates runtime directory

3. fingerprint-sensor creates + binds Unix datagram socket

4. chmod/chown exact socket

5. EVE receiver enters receive loop

6. sensor marks:
   eve_socket_ready = true

7. only then may Suricata pass its ExecStartPre guard
```

`fingerprint-suricata.service` uses a bounded socket guard:

```text
path must exist

file type must be Unix socket

poll interval =
1 second

maximum wait =
1830 seconds
```

If guard fails:

```text
Suricata exits non-zero
Restart=on-failure
RestartSec=30
```

Sensor restart replaces the socket.

Therefore Suricata uses:

```text
BindsTo=fingerprint-sensor.service

PartOf=fingerprint-sensor.service
```

and MUST be restarted/reconnected whenever the sensor service is restarted.

Maximum accepted EVE datagram:

```text
262144 bytes
```

Receiver uses truncation detection.

If:

```text
MSG_TRUNC
or
received datagram > accepted bound
```

then:

```text
do not parse JSON

do not emit partial evidence

eve_datagram_truncated += 1

TLS/QUIC EVE path =
degraded

reason =
eve_datagram_truncated
```

A later valid EVE/stats heartbeat may transition the path back to available.

No regular `eve.json` file is used.

---

# 25. Suricata EVE Types

Enabled EVE subsets:

```text
tls

quic

stats
```

Disabled/not configured for Task-02 evidence:

```text
alert

dns

http

fileinfo

files

smtp

ssh

flow/netflow history

packet

metadata not required by TLS/QUIC adapter
```

DHCP normalized evidence comes from the exact raw DHCP parser,
not from Suricata DHCP EVE.

TCP SYN normalized evidence comes from the exact raw TCP parser.

---

# 26. TLS EVE Privacy Configuration


Privacy is enforced first in Suricata configuration and again in the adapter.

Required protocol fingerprint config:

```text
app-layer.protocols.tls.ja4-fingerprints =
yes

app-layer.protocols.tls.ja3-fingerprints =
no
```

EVE Ethernet metadata:

```text
enabled
```

so original L2 identity is available where Suricata exposes it.

TLS EVE uses CUSTOM logging only.

Allowed TLS custom fields:

```text
ja4

client_alpns

client_handshake
```

`client_handshake` is transiently inspected only for:

```text
extension TYPE presence
```

and optionally:

```text
version consistency/debug telemetry
```

It is NOT durable TLS-version authority.

Do NOT configure TLS EVE to emit:

```text
sni

subject

issuer

serial

certificate

chain

fingerprint

ja3

ja3s

server_handshake

server_alpns
```

Adapter allowlisting/discard remains defense-in-depth.

No raw ClientHello is durably retained.

---

# 27. QUIC EVE Privacy Projection


Suricata QUIC EVE may structurally contain privacy-sensitive fields that Task-02
does not need.

Adapter allowlist may inspect only:

```text
quic.ja4

quic.version

quic.extensions[].type

top-level timestamp

flow_id

src_ip

ether.src_mac

required interface/event metadata
```

Adapter MUST ignore/discard:

```text
sni

ua

ja3

ja3s

cyu

extensions[].values

destination identity
```

Only approved normalized fields may reach spool.

No raw QUIC Initial or ClientHello is stored.

---

# 28. Suricata L2/L3 Identity Authority


Suricata EVE Ethernet metadata is enabled.

For Task-02 TLS/QUIC client evidence:

```text
observed_mac =
top-level EVE:
ether.src_mac

observed_ip =
top-level EVE:
src_ip
```

Eligibility requires:

```text
src_ip ∈ 192.168.8.0/22

ether.src_mac present and valid
```

Do NOT use destination/server MAC or an IP-only fallback.

If `ether.src_mac` is absent:

```text
NO device evidence

missing_l2_identity += 1

affected source path may be degraded
```

No IP-only identity fallback is permitted.

---

# 29. Raw Capture Path + Kernel BPF


`fingerprint-sensor.service` owns one passive Linux:

```text
AF_PACKET
SOCK_RAW
```

capture socket on exactly:

```text
enp8s0
```

Before the first packet can be delivered to Python parsing/hashing, a classic
kernel BPF compiled from the frozen capture expression MUST be attached.

Canonical raw-capture BPF:

```text
(udp and (port 67 or port 68))
or
(
  src net 192.168.8.0/22
  and
  tcp[tcpflags] & (tcp-syn|tcp-ack) == tcp-syn
)
```

Required semantics:

```text
DHCPv4
UDP port 67 or 68

OR

outbound guest IPv4 TCP SYN
source in 192.168.8.0/22
SYN=1
ACK=0
```

The BPF executes in kernel before Python receives the frame.

Implementation direction:

```text
libpcap compiles the frozen expression
for DLT_EN10MB

compiled classic-BPF instructions
are attached to the AF_PACKET socket
before receive loop starts
```

No full-feed Python capture path is allowed.

Raw parser owns:

```text
DHCP exact parsing

TCP SYN exact parsing

raw-path dedup
```

Raw bytes remain memory-only.

---

# 30. Raw Packet Privilege Model

Dedicated service identity:

```text
User =
fingerprint-sensor

Group =
fingerprint-sensor
```

Systemd capabilities:

```text
AmbientCapabilities =
CAP_NET_RAW

CapabilityBoundingSet =
CAP_NET_RAW

NoNewPrivileges =
true
```

The sensor process receives NO:

```text
CAP_NET_ADMIN

CAP_SYS_ADMIN

root filesystem write authority

Task-01 DB write access

Omada credential

Authorization credential
```

It must not configure `enp8s0`.

---

# 31. Suricata Privilege Model — Final Target


Service identity:

```text
User =
suricata

Group =
suricata
```

No broad root runtime.

PRE-FINAL optional `CAP_NET_RAW` feasibility test:

```text
NOT EXECUTED
```

Therefore FINAL implementation target is:

```text
AmbientCapabilities =
CAP_NET_RAW

CapabilityBoundingSet =
CAP_NET_RAW

NoNewPrivileges =
true
```

Not authorized in the implementation contract:

```text
CAP_NET_ADMIN

CAP_SYS_NICE

CAP_SYS_ADMIN

any other additional capability
```

POST-IMPLEMENTATION Gate D MUST prove that the exact accepted Suricata 8.0.6
AF_PACKET configuration operates with the FINAL target.

If Gate D proves an additional capability is genuinely required:

```text
FAIL

→ return exact operation/error evidence
  to TechLead10 + Architect

→ do NOT silently add capability

→ candidate is not accepted
```

---

# 32. Runtime / Spool Filesystem Boundary


Runtime directory:

```text
/run/captive-portal/fingerprint-sensor

owner =
fingerprint-sensor:fingerprint-eve

mode =
0750
```

EVE socket:

```text
/run/captive-portal/fingerprint-sensor/suricata-eve.sock

owner =
fingerprint-sensor

group =
fingerprint-eve

mode =
0660
```

Suricata receives supplementary membership only in `fingerprint-eve` for socket access.

Durable spool directory:

```text
/var/lib/captive-portal/fingerprint-sensor

owner =
fingerprint-sensor:fingerprint-sensor

mode =
0750
```

Spool DB/journal:

```text
owner =
fingerprint-sensor:fingerprint-sensor

mode =
0640 where applicable
```

No EVE file is written to `/var/log`, `/opt/CaptivePortal`, or durable spool.

---

# 33. Producer Secret Storage

Task-02 producer Bearer token MUST NOT be stored in Git or `.env.example`.

Producer secret file:

```text
/etc/captive-portal/device-fingerprint/sensor.bearer
```

Ownership:

```text
root:fingerprint-sensor
```

Mode:

```text
0640
```

Preferred systemd delivery:

```text
LoadCredential=
device-fingerprint-bearer:
/etc/captive-portal/device-fingerprint/sensor.bearer
```

Sensor reads:

```text
$CREDENTIALS_DIRECTORY/device-fingerprint-bearer
```

No token in:

```text
command line

journald

telemetry

spool

traceback
```

---

# 34. TLS Trust for Same-VM Producer — Exact


Producer MUST validate Task-01 TLS.

Forbidden:

```text
verify=False
```

Trust material:

```text
/etc/captive-portal/device-fingerprint/sensor-ca.crt

owner =
root:root

mode =
0644
```

It contains only public certificate/CA material needed to validate:

```text
https://192.168.0.202:9443
```

Server identity validation requires:

```text
SAN IP =
192.168.0.202
```

Sensor has no read-access requirement to the Task-01 TLS private key.

---

# 35. Packet Dedup — Mandatory / Two Distinct Questions


Task-01 transport idempotency:

```text
!=
packet/SPAN dedup
```

Task-02 owns raw mirrored-packet dedup for the BPF-admitted DHCP/TCP capture path.

Task-02 does NOT invent an unproven TLS/QUIC semantic suppressor.

Frozen V1 split:

```text
A.
raw exact-frame dedup
for BPF-admitted DHCP/TCP frames

B.
NO Suricata semantic JA4 suppression by default
```

Suricata owns stream/reassembly/application transaction semantics.

Gate D must measure whether duplicate TLS/QUIC semantic EVE events actually
exist before any future event-level suppression is introduced.

---

# 36. Raw Exact-Frame Dedup — Frozen


For every frame admitted by the RAW DHCP/TCP kernel BPF:

```text
raw_packet_count += 1
```

Transient exact-frame key:

```text
BLAKE2s-128(
    capture_source_id
    ||
    captured_length
    ||
    exact captured Ethernet frame bytes
)
```

Timestamp authority:

```text
kernel packet receive timestamp
nanosecond resolution where available
```

Bounded in-memory cache:

```text
maximum entries =
65,536
```

FINAL duplicate horizon:

```text
RAW_DEDUP_HORIZON_MS =
0.25

derived comparison horizon =
250,000 ns
```

Duplicate rule:

```text
same exact-frame key
AND
0 <= repeat_delta_ns <= 250000

→ mirrored duplicate
→ duplicate_packet_count += 1
→ do not pass duplicate to DHCP/TCP semantic parser
```

Otherwise:

```text
deduplicated_packet_count += 1
→ pass to parser
```

Raw frame bytes are memory-only and are discarded after parse/dedup processing.

No semantic:

```text
5-tuple
MAC
TCP sequence
DHCP XID
JA4
```

is used as the raw duplicate identity.

---

# 37. Raw Dedup PRE-FINAL Calibration — PASS


Measured on the real production visibility path:

```text
Catalyst RSPAN
→ enp7s0f1.999
→ macvtap/direct
→ enp8s0
```

Capture scope matched the production raw DHCP/TCP BPF.

Measured:

```text
BPF-scope packets =
501

exact-frame repeats =
258

minimum repeat delta =
0.000050 ms

p95 repeat delta =
0.082101 ms

maximum repeat delta =
0.206980 ms

all observed exact-frame repeats =
< 0.25 ms
```

Closure result:

```text
RAW_DEDUP_HORIZON_MS =
0.25

PRE-FINAL CALIBRATION =
PASS
```

No raw PCAP was retained as part of closure evidence.

POST-IMPLEMENTATION Gate D MUST still prove with controlled fixtures that:

```text
legitimate retransmission/repeat traffic
is NOT falsely suppressed
by the 0.25 ms exact-frame rule
```

If that fixture fails:

```text
Gate D =
FAIL

do not silently retune the horizon
```

---

# 38. Suricata Semantic Event Handling — Frozen


PRE-FINAL Suricata 8.0.6 fixture evidence:

```text
TLS same-flow + JA4 repeat keys =
0

QUIC same-flow + JA4 repeat keys =
0
```

Therefore Task-02 V1 has:

```text
NO semantic JA4 event suppression
```

Every qualifying Suricata TLS/QUIC client event that passes normalization creates
one normalized source event with one stable newly-created `source_event_id`.

Task-01 idempotency remains:

```text
HTTP transport retry idempotency only
```

It is NOT packet/event semantic dedup.

Forbidden V1 dedup identities include:

```text
JA4 + flow + time window

JA4 + MAC + IP + time window
```

If a future version proves real duplicate EVE semantics:

```text
new evidence
→ narrow explicit contract
→ no silent V1 suppressor
```

---

# 39. Dedup / Capture Telemetry


Raw-path telemetry:

```text
raw_packet_count

duplicate_packet_count

deduplicated_packet_count

raw_dedup_ratio

dhcp_candidate_count

dhcp_scoped_count

tcp_syn_event_count
```

Meaning:

```text
raw_packet_count =
packets admitted by the RAW DHCP/TCP kernel BPF

NOT every packet on enp8s0
```

Invariant after final calibrated dedup is enabled:

```text
raw_packet_count
=
duplicate_packet_count
+
deduplicated_packet_count
```

Suricata/full guest-IP feed telemetry comes from Suricata stats:

```text
capture.kernel_packets

capture.kernel_drops

capture.kernel_ifdrops when present
```

TLS/QUIC adapter telemetry:

```text
tls_eve_count

tls_normalized_count

quic_eve_count

quic_normalized_count

eve_datagram_truncated

eve_json_invalid

missing_l2_identity
```

No `semantic_duplicate_event_count` exists in V1 unless later evidence justifies
a dedup contract.

---

# 40. Guest Scope — No VLAN Tag Dependency

Inside VM:

```text
RSPAN transport VLAN tag
is not Site authority
```

Task-02 does NOT infer Site from missing/present VLAN999 tag.

For ordinary IP evidence:

```text
client source IP ∈ 192.168.8.0/22
```

is required.

Then:

```text
site_id =
6a64f17630da7c70d232187a

capture_source_id =
zefer-span-01
```

comes from trusted producer configuration.

No cross-Site inference.

---

# 41. DHCP Scope Problem

DHCP Discover commonly has:

```text
source IP =
0.0.0.0

destination =
255.255.255.255
```

Because RSPAN carries VLAN10 and VLAN20 and VLAN tags are not a required
guest-side signal, Task-02 MUST NOT emit every observed DHCP Discover as
Zefer_Parki evidence.

---

# 42. DHCP Scope Resolver — Frozen Authority


Guest DHCP authority is now measured and frozen:

```text
guest CIDR =
192.168.8.0/22

DHCP_SERVER_AUTHORITY =
192.168.10.1

DHCP_OPTION54_AUTHORITY =
192.168.10.1
```

PRE-FINAL live evidence:

```text
multiple correlated OFFER/ACK transactions =
CONFIRMED

server source IPv4 =
192.168.10.1

DHCP option 54 =
192.168.10.1

yiaddr =
observed inside 192.168.8.0/22

MAC + XID correlation =
PASS
```

For zero-address DORA, buffered client evidence may be released only when the
same bounded MAC+XID transaction observes:

```text
OFFER
or
ACK
```

with ALL:

```text
yiaddr ∈ 192.168.8.0/22

server source IPv4 =
192.168.10.1

option 54 =
192.168.10.1
```

`requested_ip` alone never establishes Site authority.

Server OFFER/ACK data is authority/correlation input only and is not emitted as
device fingerprint evidence.

---

# 43. DHCP Message-Specific Scope Rules


Task-02 may emit client:

```text
DISCOVER

REQUEST

INFORM

DECLINE

RELEASE
```

Rules:

```text
DISCOVER:
buffer if zero-address;
release only after confirmed guest OFFER/ACK authority.

REQUEST:
if actual source/ciaddr guest → direct;
otherwise buffer until confirmed guest ACK/OFFER authority.
requested_ip alone is insufficient.

INFORM:
requires actual source or ciaddr
inside guest CIDR.

DECLINE:
requires matching confirmed guest lease/transaction cache
or another exact confirmed guest binding.
requested_ip alone is insufficient.

RELEASE:
requires actual guest source/ciaddr
OR matching confirmed guest lease cache.
```

Confirmed guest lease cache is memory-only and keyed by:

```text
client MAC
assigned guest IP
guest DHCP server authority
```

Lease-cache expiry:

```text
min(observed DHCP lease time, 86400 seconds)
```

If lease time is absent:

```text
3600 seconds
```

Server OFFER/ACK/NAK is used only for authority/correlation and is not emitted as
device evidence.

---

# 44. DHCP Schema Registration

Production registry key:

```text
(
    source_kind = "dhcp",
    feature_schema_version = 1
)
```

Extractor:

```text
extractor_name =
packet-dhcp

extractor_version =
1.0.0
```

`rule_version`:

```text
null
```

---

# 45. DHCP Payload v1 — Exact Keys

Exactly:

```text
message_type

parameter_request_list

option_order

vendor_class

client_identifier_kind

maximum_message_size

rapid_commit_requested

capport_requested

ipv6_only_preferred_requested

hostname_present
```

No extra key.

---

# 46. DHCP Payload v1 — Field Contract

```text
message_type =
discover | request | inform | decline | release
```

```text
parameter_request_list =
array[int]
0..255
maximum 64
order preserved
```

```text
option_order =
array[int]
0..255
maximum 64
order preserved
```

```text
vendor_class =
null
or printable ASCII string
1..128
```

```text
client_identifier_kind =
absent | mac | opaque
```

No raw opaque client identifier.

```text
maximum_message_size =
null
or integer 576..65535
```

Booleans:

```text
rapid_commit_requested

capport_requested

ipv6_only_preferred_requested

hostname_present
```

No raw hostname.

---

# 47. DHCP Complete Task-01 Envelope


Frozen constants:

```text
source_kind = dhcp

source_subtype =
discover | request | inform | decline | release

extractor_name = packet-dhcp
extractor_version = 1.0.0
feature_schema_version = 1
rule_version = null
```

`observed_at`:

```text
kernel receive timestamp of ORIGINAL CLIENT DHCP event
→ canonical UTC milliseconds
```

`observed_mac`:

```text
original client Ethernet source MAC
```

`observed_ip` derives ONLY from ORIGINAL CLIENT event:

```text
actual client IPv4 source ∈ 192.168.8.0/22
OR
actual client ciaddr ∈ 192.168.8.0/22
OTHERWISE
null
```

Forbidden:

```text
yiaddr backfill
requested_ip backfill
```

Later OFFER/ACK/yiaddr/requested_ip are scope/correlation inputs only.

Quality rules remain `valid` / `partial` only after guest scope is proven.
Malformed/truncated client packet emits no evidence.

---

# 48. TCP SYN Schema Registration — IPv4 V1


Production registry key:

```text
(
    source_kind = "tcp_syn",
    feature_schema_version = 1
)
```

Extractor:

```text
extractor_name =
packet-tcp-syn

extractor_version =
1.0.0
```

V1 eligibility:

```text
IPv4 ONLY

SYN=1

ACK=0

source IPv4 ∈ 192.168.8.0/22
```

Routed guest IPv6 is outside the current producer authority and outside Task-02
V1.

---

# 49. TCP SYN Payload v1 — Exact Keys

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

No:

```text
DF behavior

IPv4 ID classification

ECN classification

sequence number

ports

destination IP

payload
```

Those were not proven as Phase-1 core fields.

---

# 50. TCP SYN Field Contract — IPv4 V1


```text
ip_version =
4
```

Only value `4` is valid in Task-02 V1.

```text
observed_ttl =
integer 0..255

tcp_window =
integer 0..65535

mss =
null
or integer 0..65535

window_scale =
null
or integer 0..14

sack_permitted =
boolean

timestamps_present =
boolean

tcp_option_order =
array[int]
0..255
maximum 32
order preserved
```

No:

```text
DF behavior

IPv4 ID classification

ECN classification

sequence number

ports

destination IP

payload
```

No p0f OS classification.

---

# 51. TCP SYN Complete Task-01 Envelope


Frozen:

```text
source_kind =
tcp_syn

source_subtype =
ipv4

extractor_name =
packet-tcp-syn

extractor_version =
1.0.0

feature_schema_version =
1

rule_version =
null
```

Timestamp authority:

```text
observed_at =
kernel receive timestamp
converted to canonical UTC milliseconds
```

Identity:

```text
observed_mac =
original Ethernet source MAC

observed_ip =
original IPv4 guest source IP
```

Quality:

```text
valid
```

only when:

```text
full IPv4/TCP SYN header parse succeeds

option structure valid

source IP guest-scoped

original source MAC valid
```

Truncated/malformed:

```text
NO evidence
```

---

# 52. TLS JA4 Schema Registration


Production key:

```text
("tls_client", 1)
```

Frozen envelope constants:

```text
source_kind =
tls_client

source_subtype =
client_hello

extractor_name =
suricata-tls-ja4

extractor_version =
8.0.6

feature_schema_version =
1

rule_version =
null
```

Evidence requires client-oriented Suricata data with:

```text
guest src_ip

original ether.src_mac

TLS-family JA4

top-level Suricata timestamp
```

---

# 53. TLS JA4 Payload v1 — Exact Keys

```text
ja4

ja4_a

ja4_b

ja4_c

tls_version_family

client_alpns

ech_extension_present

grease_extension_present
```

No:

```text
JA3

SNI

destination hostname

certificate

cipher list

raw extension list

raw ClientHello
```

---

# 54. JA4 Structural Validation — Final


Task-02 validates Suricata-produced JA4.

It does NOT reconstruct JA4.

Full shape:

```text
A_B_C
```

Exactly three components.

`B` and `C`:

```text
exactly 12 lowercase hexadecimal characters each
```

A component is exactly 10 characters:

```text
0      transport
1..2   TLS version code
3      SNI d/i flag
4..5   cipher count
6..7   extension count
8..9   ALPN representation
```

FINAL structural parser:

```text
transport =
t | q

version code =
13 | 12 | 11 | 10 | s3 | s2 | 00

SNI flag =
d | i

cipher count =
two ASCII decimal digits

extension count =
two ASCII decimal digits

ALPN representation =
two ASCII alphanumeric characters
```

Family constraint:

```text
tls_client
→ transport == t

quic_client
→ transport == q
```

PRE-FINAL Suricata 8.0.6 fixture observed valid A prefixes including:

```text
TLS:
t13...
t12...

QUIC:
q13...
q00...
```

The fixture confirms the expected structure and current observed version subset.
The validator does not widen beyond the frozen structural contract.

---

# 55. TLS Version Authority — Final


Durable:

```text
tls_version_family
```

derives ONLY from the already validated TLS JA4 A component:

```text
ja4_a[1:3] == "13"
→ tls1_3

ja4_a[1:3] == "12"
→ tls1_2

any other accepted JA4 version code
→ other
```

`tls.client_handshake.version`:

```text
may be inspected transiently
for consistency/debug evidence only
```

It is NOT durable TLS-version authority.

No server TLS version is used.

`client_handshake` remains transiently useful for:

```text
extension TYPE list
ECH presence
GREASE presence
```

---

# 56. TLS Extension Presence

From transient Suricata client handshake extension IDs:

```text
ech_extension_present =
true | false | null

grease_extension_present =
true | false | null
```

`null` means:

```text
Suricata event did not provide sufficient extension metadata
```

ECH presence:

```text
extension type 0xFE0D / 65037
```

GREASE detection uses the standard reserved-value pattern.

Raw extension list is discarded before spool.

---

# 57. TLS Complete Envelope / Quality


Timestamp authority:

```text
observed_at =
Suricata top-level EVE timestamp
→ canonical UTC milliseconds
```

Identity:

```text
observed_mac =
EVE ether.src_mac

observed_ip =
EVE src_ip ∈ 192.168.8.0/22
```

Quality:

```text
valid =
structurally valid TLS-family JA4
+
MAC/IP valid
+
approved extension metadata available

partial =
JA4/MAC/IP valid
but optional approved extension metadata absent
```

`tls_version_family` always comes from JA4 A component, never
`client_handshake.version`.

No evidence without valid TLS-family JA4.

---

# 58. QUIC JA4 Schema Registration


Production key:

```text
("quic_client", 1)
```

Frozen envelope constants:

```text
source_kind =
quic_client

source_subtype =
client_hello

extractor_name =
suricata-quic-ja4

extractor_version =
8.0.6

feature_schema_version =
1

rule_version =
null
```

Evidence requires:

```text
guest src_ip

original ether.src_mac

QUIC-family JA4

Suricata top-level timestamp
```

---

# 59. QUIC JA4 Payload v1 — Exact Keys

```text
ja4

ja4_a

ja4_b

ja4_c

quic_version

ech_extension_present

grease_extension_present
```

No:

```text
SNI

UA

JA3

JA3S

CYU

extension values

raw Initial

raw ClientHello
```

---

# 60. QUIC Version Adapter — Final


Actual Suricata 8.0.6 EVE representation proven PRE-FINAL:

```text
JSON type =
STRING
```

Observed examples:

```json
"1"
"faceb002"
```

FINAL accepted input representation:

```text
JSON string

regex =
[0-9a-f]{1,8}
```

There is NO required `0x` prefix in the Suricata input.

There is NO integer JSON input in the FINAL V1 contract.

Adapter parses the string as an unsigned hexadecimal value and normalizes to:

```text
0x
+
8 lowercase hexadecimal digits
```

Examples:

```text
"1"
→
0x00000001

"faceb002"
→
0xfaceb002
```

The original Suricata representation is NOT persisted.

Any other type or string representation:

```text
NO evidence

quic_version_invalid += 1
```

POST-IMPLEMENTATION Gate D verifies that the implementation conforms exactly to
this frozen adapter contract.

---

# 61. QUIC Extension Presence + Complete Envelope


From transient:

```text
quic.extensions[].type
```

derive only:

```text
ech_extension_present =
bool | null

grease_extension_present =
bool | null
```

Never consume durable extension values.

Timestamp authority:

```text
observed_at =
Suricata top-level EVE timestamp
converted to UTC milliseconds
```

Identity:

```text
observed_mac =
original EVE ether.src_mac

observed_ip =
EVE src_ip
inside 192.168.8.0/22
```

Quality:

```text
valid =
QUIC-family JA4 valid
+
QUIC version valid
+
MAC/IP valid
+
extension TYPE metadata available
```

```text
partial =
JA4/version/MAC/IP valid
but extension TYPE metadata absent
```

If extension list absent:

```text
ECH =
null

GREASE =
null
```

No event without valid QUIC-family JA4.

---

# 62. Required Core Source Capability


Initial Task-02 V1 acceptance requires:

```text
dhcp =
available

tcp_syn =
available

tls_client =
available

quic_client =
available
```

PRE-FINAL Suricata fixture closure established:

```text
TLS JA4 support =
PASS

QUIC JA4 support =
PASS
```

POST-IMPLEMENTATION Gate D must again prove the implemented immutable candidate
produces both required JA4 families.

Runtime `unsupported` may represent a later operational capability loss but does
NOT satisfy initial V1 acceptance.

No substitute fingerprint is fabricated.

---

# 63. Production Schema Registry Modification — Task-01 Reserved Extension Point


Task-02 changes only the Task-01 extension point explicitly reserved for later
source schemas.

`build_production_schema_registry()` becomes conceptually:

```text
registry = EvidenceSchemaRegistry()

register ("dhcp", 1)

register ("tcp_syn", 1)

register ("tls_client", 1)

register ("quic_client", 1)

freeze

return
```

No Task-01:

```text
HTTP contract

DB schema

retention

idempotency

security boundary
```

is redefined.

Validators remain pure central payload validators with no capture/runtime imports.

---

# 64. Shared Central Schema File

New:

```text
app/device_fingerprint/network_schemas.py
```

Owns only:

```text
DHCP v1 validator

TCP SYN v1 validator

TLS JA4 v1 validator

QUIC JA4 v1 validator
```

No packet parsing.

No producer delivery.

No classification.

---

# 65. Sensor Package Boundary


New package remains:

```text
app/device_fingerprint_sensor/
```

Exact FINAL proposal:

```text
__init__.py

config.py

models.py

capture.py

capture_filter.py

dedup.py

scope.py

dhcp.py

tcp_syn.py

eve.py

normalizer.py

spool.py

producer.py

health.py

telemetry.py

runtime.py

cli.py
```

Critical isolation:

```text
app/device_fingerprint_sensor/config.py
```

owns ALL sensor environment parsing/defaults/strict validation.

It MUST NOT import:

```text
app.settings

app.config
```

Main runtime MUST NOT import:

```text
app.device_fingerprint_sensor
```

No sensor parsing executes on the `run.py` import/startup path.

---

# 66. Sensor-Only Configuration Boundary


All variables:

```text
DEVICE_FINGERPRINT_SENSOR_*
```

are read directly from the sensor process environment by:

```text
app/device_fingerprint_sensor/config.py
```

The main CaptivPortal configuration path:

```text
app
→ app.settings
→ app.config
```

MUST NOT:

```text
parse

validate

default

compose

import
```

sensor settings.

Explicit NO-TOUCH for sensor config integration:

```text
app/config.py

app/settings.py

app/__init__.py

run.py
```

`.env.example` may document sensor variables as comments/placeholders only.

Operational `EnvironmentFile` may contain sensor variables; main CaptivPortal
simply ignores them.

---

# 67. Sensor Defaults — Final


Sensor-only defaults live exclusively in:

```text
app/device_fingerprint_sensor/config.py
```

Frozen/default concepts:

```text
ENABLED =
false

INTERFACE =
enp8s0

PRODUCER_ID =
sensor-zefer-01

CAPTURE_SOURCE_ID =
zefer-span-01

SITE_ID =
6a64f17630da7c70d232187a

GUEST_CIDRS =
192.168.8.0/22

DHCP_SERVER_AUTHORITY =
192.168.10.1

DHCP_OPTION54_AUTHORITY =
192.168.10.1

EVIDENCE_BASE_URL =
https://192.168.0.202:9443/api/internal/device-fingerprint/v1

CA_CERT_PATH =
/etc/captive-portal/device-fingerprint/sensor-ca.crt

SPOOL_PATH =
/var/lib/captive-portal/fingerprint-sensor/spool.sqlite3

SPOOL_TOTAL_BUDGET_BYTES =
134217728

SPOOL_MAIN_DB_MAX_BYTES =
117440512

SPOOL_WRITE_HEADROOM_BYTES =
16777216

SPOOL_MAX_EVENTS =
100000

DELIVERY_BATCH_SIZE =
100

HTTP_TIMEOUT_SECONDS =
5

RAW_DEDUP_MAX_ENTRIES =
65536

RAW_DEDUP_HORIZON_MS =
0.25

CORE_READY_HOST =
127.0.0.1

CORE_READY_PORT =
8088

CORE_READY_CONNECT_TIMEOUT_SECONDS =
1

CORE_READY_POLL_INTERVAL_SECONDS =
10

CORE_READY_MAX_WAIT_SECONDS =
1800

EVE_MAX_DATAGRAM_BYTES =
262144

EVE_SOCKET_WAIT_SECONDS =
1830
```

There is NO semantic JA4 dedup TTL in V1.

All `DEVICE_FINGERPRINT_SENSOR_*` environment parsing remains isolated to:

```text
app/device_fingerprint_sensor/config.py
```

and does not enter `app/config.py`, `app/settings.py` or `run.py`.

---

# 68. Spool Is Not a Second Evidence Database

Task-02 durable spool is:

```text
transport queue only
```

It is NOT:

```text
canonical evidence history

classification source of truth

query surface

Admin source

Analytics source
```

Canonical evidence remains:

```text
Task-01 device_fingerprint_evidence.sqlite3
```

---

# 69. Spool SQLite Operational Budget


Spool remains SQLite DELETE-journal mode.

```text
main DB logical ceiling =
112 MiB

configured operational durable-footprint budget =
128 MiB

operational transaction headroom target =
16 MiB
```

Possible durable artifacts:

```text
spool.sqlite3
spool.sqlite3-journal
```

`spool_bytes` is current physical main + rollback-journal size.

Accuracy rule:

```text
128 MiB =
APPLICATION OPERATIONAL BUDGET

NOT
filesystem/kernel-enforced absolute quota
```

`PRAGMA max_page_count` limits main DB growth but does not mathematically cap
every in-flight rollback-journal byte.

Task-02 guarantees bounded transactions, pre/post physical checks,
degrade/drop/stop-enqueue behavior and NO unbounded growth.

A true filesystem hard quota is separate infrastructure, not invented by Coder.

---

# 70. Spool Transaction Bounds


Transaction bounds:

```text
enqueue <= 100 rows
eviction/delete <= 100 rows
ack delete <= 100 rows
```

Before enqueue:

```text
stale purge
→ physical-size measure
→ row/main-DB capacity check
→ bounded eviction/drop if needed
→ bounded transaction
→ immediate post-transaction measure
```

If post-transaction physical footprint exceeds the 128 MiB operational budget:

```text
sensor = degraded / spool_capacity
new durable enqueue = stopped
bounded purge/eviction may run
telemetry emitted
```

No claim that in-flight rollback journal can never transiently cross the
application budget.

---

# 71. Stable Event ID

For device evidence:

```text
source_event_id =
uuid4

created ONCE
before spool insert
```

For source health:

```text
source_health_event_id =
uuid4

created ONCE
before spool insert
```

Retry MUST reuse it.

No regeneration after:

```text
429

500

503

timeout

connection error

service restart
```

---

# 72. Spool Capacity Algorithm


Configured controls:

```text
main DB logical ceiling = 112 MiB
operational budget = 128 MiB
row cap = 100000
```

Flow:

```text
local UTC wall clock
→ stale purge
→ measure
→ bounded eviction
→ re-measure
→ bounded insert
→ post-transaction re-measure
```

Oldest device evidence is evicted first.

Source-health priority never disables capacity controls.

If operational headroom cannot be preserved:

```text
drop/evict normalized evidence
degrade sensor
emit sanitized telemetry
stop new durable enqueue if needed
```

Permanent:

```text
NO unbounded spool growth
```

---

# 73. Spool Clock / Stale Expiry


Clock authority for producer-side age decisions:

```text
local VM UTC wall clock

datetime.now(timezone.utc)
```

captured at the purge/delivery decision.

If:

```text
local_utc_now - event.observed_at
>
86400 seconds
```

then:

```text
do not send

delete from spool

stale_spool_event_dropped += 1
```

No observed_at rewrite.

Task-01 independently revalidates:

```text
future skew <= 120 seconds

delayed age <= 86400 seconds
```

Producer clock does not replace central validation.

---

# 74. Delivery Batch

Task-02 sends endpoint-homogeneous batches:

```text
evidence batch

OR

source-health batch
```

Maximum:

```text
100 events
```

Producer root:

```text
producer_id =
sensor-zefer-01
```

No mixed endpoint types in one HTTP request.

---

# 75. Delivery Retry Policy — Preserved


Initial delay:

```text
1 second
```

Backoff:

```text
1
2
4
8
16
30
30
...
seconds
```

Maximum:

```text
30 seconds
```

Jitter:

```text
±10%
```

429:

```text
honor valid Retry-After
1..60 seconds

otherwise normal backoff
```

No tight loop.

Stable event IDs are preserved across all retries.

---

# 76. HTTP Result Handling

```text
200
→ remove acknowledged batch rows
```

```text
429
→ keep rows
→ honor valid Retry-After 1..60 seconds
→ otherwise normal backoff
```

```text
500
503
connection error
TLS transient error
timeout
→ keep rows
→ retry/backoff
```

```text
400
401
403
404
405
409
413
→ NON-TRANSIENT producer/schema/config fault
→ stop normal delivery
→ runtime degraded/unavailable
→ retain bounded rows until stale/administrative correction
→ emit sanitized telemetry
```

Task-02 must not hammer Task-01 on permanent rejection.

---

# 77. At-Least-Once Delivery

Delivery semantics:

```text
at-least-once
```

Central Task-01 idempotency resolves retries.

Producer may resend a batch if:

```text
HTTP connection closed
after request send
before reliable response
```

Stable event IDs make this safe.

---

# 78. Source Health Model

Task-02 emits Task-01 source-health events separately from device evidence.

No MAC.

No IP.

No fake per-device unavailable evidence.

Health is keyed by:

```text
site_id

capture_source_id

source_kind

observed_at
```

---

# 79. Source Health — Capture Interface

If `enp8s0` preflight/capture fails:

for all:

```text
dhcp
tcp_syn
tls_client
quic_client
```

emit/spool:

```text
status =
unavailable

reason_code =
capture_interface_unavailable
```

When restored:

```text
status =
available

reason_code =
null
```

---

# 80. Source Health — Raw Parser

If raw parser fails while Suricata remains healthy:

```text
dhcp =
unavailable
reason=raw_parser_unavailable

tcp_syn =
unavailable
reason=raw_parser_unavailable
```

TLS/QUIC health is independent.

---

# 81. Source Health — Suricata

If Suricata/EVE path is unavailable:

```text
tls_client =
unavailable
reason=suricata_unavailable

quic_client =
unavailable
reason=suricata_unavailable
```

If only QUIC JA4 unsupported:

```text
quic_client =
unsupported
reason=suricata_quic_unavailable
```

DHCP/TCP can continue.

---

# 82. Source Health — Delivery

Task-02 maintains local delivery health telemetry.

When Task-01 ingest cannot be reached:

```text
spool continues within bounds
```

It also creates source-health point events for affected source kinds:

```text
status =
unavailable

reason_code =
ingest_delivery_unavailable
```

These are themselves queued and delivered after recovery if still within
the 24-hour Task-01 acceptance age.

After recovery:

```text
available / null
```

This describes central visibility of the source path, not device state.

---

# 83. Health Transition Dedup

Do not emit source-health every loop.

Emit only on:

```text
state transition

or periodic heartbeat
```

Heartbeat interval:

```text
300 seconds
```

Same status/reason inside heartbeat window:

```text
NO new event
```

---

# 84. Sensor Runtime State / V1 Acceptance


Local states remain:

```text
disabled
initializing
ready
degraded
unavailable
stopping
```

Initial V1 `ready` acceptance requires ALL:

```text
dhcp = available
tcp_syn = available
tls_client = available
quic_client = available

raw capture healthy
spool healthy
delivery worker healthy
Suricata EVE path healthy
```

After activation, a source-family failure may yield `degraded`.

`unsupported` is observable but not an accepted initial-ready state for TLS or
QUIC.

Task-02 state never changes Authorization readiness.

---

# 85. Sensor CLI Startup


Disabled lifecycle is unchanged and exits 0 before artifact/spool/capture work.

Enabled startup after strict config:

```text
1. capture_loaded_artifact_identity(
     "fingerprint-sensor.service"
   )

2. TCP core readiness 127.0.0.1:8088

3. initialize bounded normalized spool

4. start producer/delivery capability

5. interface safety preflight
```

If interface preflight FAILS:

```text
NO AF_PACKET
NO EVE socket
NO Suricata capture

enqueue source-health:
dhcp/tcp_syn/tls_client/quic_client
status=unavailable
reason=capture_interface_unavailable
```

If spool is healthy, perform ONE bounded best-effort delivery attempt with
5-second HTTP timeout and no startup retry loop.

Then exit non-zero; systemd `RestartSec=30`.

If spool cannot initialize, emit sanitized local telemetry only and exit
non-zero.

On later successful start, available/null source-health transitions are emitted
as source families become available.

Only after interface PASS:

```text
6. create/bind EVE socket
7. attach raw kernel BPF
8. start raw AF_PACKET parser
9. initialize raw source health
10. remain initializing/degraded until separately started Suricata is healthy
```

---

# 86. Sensor Shutdown

Signal:

```text
SIGTERM / SIGINT
```

Must:

```text
stop accepting new raw/EVE events

close AF_PACKET capture

stop EVE receiver

finish current bounded spool transaction

stop delivery worker

close spool

release runtime socket
```

Shutdown budget:

```text
20 seconds
```

No Authorization executor interaction.

No central evidence DB handle exists in this process.

---

# 87. Suricata Service Startup / Reconnect


Before Suricata live start:

```text
suricata -T
```

MUST pass using deployed approved config.

Required package version:

```text
8.0.6
```

Service preconditions:

```text
enp8s0 exists

fingerprint-sensor.service active

/run/captive-portal/fingerprint-sensor/suricata-eve.sock
exists and is Unix socket

socket wait <= 1830 seconds
```

Unit relationships:

```text
After=fingerprint-sensor.service

BindsTo=fingerprint-sensor.service

PartOf=fingerprint-sensor.service

Restart=on-failure

RestartSec=30
```

If sensor restarts/replaces its socket:

```text
Suricata must stop

then restart

then pass the replacement-socket check

then reconnect
```

Sensor restart acceptance MUST prove TLS/QUIC EVE resumes.

Package activation pins exact:

```text
Suricata 8.0.6
```

and prevents unattended package drift to another Suricata version until an
explicit compatibility recheck.

---

# 88. Suricata Startup Health

Sensor considers Suricata path available only after:

```text
valid stats/EVE heartbeat observed

version expected

capture interface expected

no fatal EVE output error
```

Process existence alone:

```text
!= Suricata source ready
```

---

# 89. No Persistent PCAP

Forbidden production outputs:

```text
pcap-log

pcap ring

dumpcap files

tcpdump files

Suricata packet output

AF_PACKET raw spool
```

Raw capture for debugging requires separate Owner authorization.

Task-02 normal mode creates none.

---

# 90. No Full EVE Persistence — Privacy Primary Control


Forbidden production file:

```text
/var/log/suricata/eve.json
```

Task-02 EVE transport is Unix datagram only.

No generic EVE archive.

No raw EVE Loki shipping.

Primary privacy control is:

```text
Suricata configuration field minimization
```

Adapter allowlist/discard is defense-in-depth.

Only sanitized Task-02 operational telemetry may enter existing logging.

---

# 91. Privacy Denylist

Task-02 MUST NOT durably store or forward:

```text
raw PCAP

packet payload

raw full Ethernet/IP/TCP frame

SNI

DNS name/history

HTTP host/path

full TLS ClientHello

full QUIC Initial

JA3 string/hash

raw DHCP packet

raw DHCP opaque client identifier

raw hostname from DHCP

credentials

cookies

authorization headers

person identity
```

---

# 92. No Cross-MAC Identity

Task-02 evidence identity:

```text
observed MAC
+
observed time
+
trusted Site/capture scope
```

Task-02 does NOT:

```text
merge randomized MACs

link devices by JA4

link devices by DHCP PRL

link devices by TCP vector

create person identity

infer persistent identity across Site
```

---

# 93. Resource Isolation — Exact Final Ceilings


`fingerprint-sensor.service`:

```text
CPUQuota =
50%

MemoryMax =
256M

TasksMax =
64

Nice =
10
```

`fingerprint-suricata.service`:

```text
CPUQuota =
150%

MemoryHigh =
768M

MemoryMax =
1024M

Nice =
10
```

Permanent:

```text
Coder may NOT raise these values.
```

If Gate F cannot pass within them:

```text
FAIL
→ Architect + TechLead10 review
```

Do not trade core Authorization safety for packet completeness.

Suricata capability target is independently frozen:

```text
CAP_NET_RAW only
```

and must be proven at POST-IMPLEMENTATION Gate D.

---

# 94. No Core Service Resource Dependency

Task-02 does NOT modify limits of:

```text
captive-portal.service

fingerprint-evidence.service

traffic-projection.service

Observation

Current State
```

Sensor pressure may drop fingerprint evidence.

It must not steal unlimited resources from core runtime.

---

# 95. Resource / Capture Telemetry


Minimum periodic telemetry:

```text
sensor CPU time / cgroup usage

sensor RSS/current memory

Suricata CPU / cgroup usage

Suricata memory.current

Suricata process/version

stats.capture.kernel_packets

stats.capture.kernel_drops

stats.capture.kernel_ifdrops when present

EVE received

EVE truncated

raw BPF-admitted packet count

raw duplicate count

raw deduplicated count

spool rows

spool_bytes =
main DB + journal

oldest spool age

delivery success/retry/permanent reject

normalized events per source_kind
```

No destination identifiers.

---

# 96. Performance Gate — Exact Suricata Packet-Loss Metric


Formal POST-IMPLEMENTATION Gate F uses Suricata EVE `stats` counters over the
same measurement window:

```text
K0 =
stats.capture.kernel_packets at window start

K1 =
stats.capture.kernel_packets at window end

D0 =
stats.capture.kernel_drops at window start

D1 =
stats.capture.kernel_drops at window end
```

Deltas:

```text
P =
K1 - K0

D =
D1 - D0
```

Valid measurement requires:

```text
P > 0

D >= 0

counter reset/wrap =
NO
```

Drop ratio:

```text
suricata_kernel_drop_ratio =
D / (P + D)
```

Gate F threshold:

```text
<= 0.01
(1.0%)
```

over each required 15-minute sustained evaluation segment.

Also record:

```text
capture.kernel_ifdrops
```

when available.

PRE-FINAL 90-second fixture informational result:

```text
Suricata packets =
378438

drops =
1439

reported/derived drop ratio =
~0.38%
```

This PRE-FINAL value is:

```text
INFORMATIONAL ONLY

NOT Gate F acceptance
```

Formal resource/drop/Authorization performance acceptance remains
POST-IMPLEMENTATION Gate F.

---

# 97. Performance Gate — CPU

During normal 2-hour soak:

```text
combined fingerprint-sensor
+
fingerprint-suricata
```

must remain within configured systemd CPU caps.

Additionally:

```text
no sustained CPU starvation
of captive-portal.service

no system load runaway

no task-attributable auth failures
```

CPU quota throttling that causes unacceptable evidence loss:

```text
FAIL
```

not a reason to raise quota automatically.

---

# 98. Performance Gate — RAM

Required:

```text
no OOM

no swap storm attributable to sensor

sensor RSS remains < 256 MiB cap

Suricata remains < 1024 MiB cap

combined bounded
```

Memory pressure that degrades Authorization:

```text
FAIL
```

---

# 99. Performance Gate — Deterministic Authorization p95


Authoritative duration source:

```text
/opt/CaptivePortal/logs/auth_telemetry.log
```

Event:

```text
auth.session_finished
```

Field:

```text
duration_ms
```

Eligible sample:

```text
event == "auth.session_finished"

final_state == "AUTHORIZED"

duration_ms is finite numeric >= 0
```

Two windows use the SAME immutable candidate and same VM:

```text
BASELINE:
Task-02 sensor + Suricata disabled

SENSOR-ON:
Task-02 sensor + Suricata enabled
```

Window duration:

```text
60 minutes each
```

Minimum eligible samples:

```text
30 successful authorization sessions
per window
```

If either 60-minute window has fewer than 30:

```text
extend that window
up to 4 hours total
```

If still fewer than 30:

```text
normal-traffic p95 =
INSUFFICIENT_SAMPLE

Gate F cannot claim p95 PASS from ambient traffic.

Owner + Tech Lead must run
an approved controlled authorization cohort
with >=30 successful sessions
for baseline and sensor-on
on the same candidate/environment.
```

p95 calculation:

```text
nearest-rank percentile

rank =
ceil(0.95 * N)

sort duration_ms ascending

p95 =
value at 1-based rank
```

Acceptance:

```text
sensor_on_p95 <= baseline_p95 * 1.20

AND

sensor_on_p95 - baseline_p95 <= 100 ms
```

Also mandatory:

```text
0 Task-02-attributable authorization failures

0 new Task-02-attributable 502
```

No operator-defined alternate duration field or percentile algorithm.

---

# 100. Performance Gate — Existing Read/Worker Domains

During soak verify no material Task-02 regression in:

```text
Admin

Observation

Current State

Visit Lifecycle

Traffic Projection

fingerprint-evidence.service
```

No:

```text
unexpected restart

new DB corruption

persistent source unavailable state

runaway queue/backlog
```

---

# 101. Near-Cap Spool Physical-Footprint Gate — POST-IMPLEMENTATION


This proof requires implemented Task-02 spool/runtime code.

Execution phase:

```text
POST-IMPLEMENTATION

under:
Gate D / Gate F

against:
the immutable candidate
```

Controlled near-capacity proof must record:

```text
main DB size
rollback journal size
combined spool_bytes
largest observed transient journal
post-transaction footprint
drop/eviction counts
degraded transition
```

Prove:

```text
journal_mode DELETE
112 MiB main DB logical ceiling
<=100-row transactions
pre-enqueue guard
post-transaction verification
row cap 100000
stale purge
bounded eviction/drop
```

Acceptance:

```text
application behavior remains bounded
NO unbounded durable growth
operational budget controls behave as designed
```

Do not claim a filesystem-enforced absolute 128 MiB hard ceiling.

This section is NOT PRE-FINAL architecture closure evidence.

---

# 102. Sensor Restart Recovery Gate

Controlled restart:

```text
fingerprint-sensor.service
```

must prove:

```text
spooled events survive restart

no raw packet storage appears

delivery resumes

old event IDs unchanged

new event IDs unique

source-health transition emitted
```

---

# 103. Suricata Restart / EVE Socket Lifecycle Gate


Controlled Suricata restart must prove:

```text
DHCP/TCP raw parser continues

TLS/QUIC health → unavailable during interruption

core Portal unaffected

replacement/reused EVE socket validated

Suricata reconnects

valid EVE heartbeat resumes

TLS/QUIC health → available

normalized TLS/QUIC resumes
```

Controlled SENSOR restart must additionally prove:

```text
old EVE Unix datagram socket disappears

Suricata stops due relationship

sensor creates/binds replacement socket

Suricata socket preflight sees new socket

Suricata restarts

TLS/QUIC EVE resumes
```

---

# 104. Same-VM Soak Gate

Minimum live soak:

```text
2 hours
```

on production-compatible VM environment / approved window.

Required:

```text
sensor enabled

Suricata enabled

Task-01 evidence service enabled

normal real mirrored traffic
```

Production activation itself is NOT authorized by this DRAFT.

Exact execution environment/window belongs to Owner + Tech Lead acceptance plan.

---

# 105. Dedup Calibration / Fixture Set


Sanitized fixture/calibration set includes:

```text
raw exact duplicate DHCP frame

raw exact duplicate TCP SYN frame

same exact raw frame after long interval

legitimate TCP SYN retransmission/repeat

DHCP Discover/Request sequence

TLS duplicate-mirror input fixture

two separate TLS connections with same JA4

QUIC Initial retransmission/duplicate input

two separate QUIC flows with same JA4
```

Two distinct gates:

```text
A.
live bounded raw timestamp calibration
on real RSPAN→enp8s0 path

B.
Suricata 8.0.6 fixture replay
to observe actual EVE multiplicity
```

No semantic EVE suppression is added unless B proves it is required.

---

# 106. DHCP Oracle Gate

For controlled Nokia/known test capture, parser must reproduce exact ordered:

```text
PRL

option order

vendor class

max message size

Rapid Commit presence

CAPPORT presence

IPv6-Only Preferred presence
```

No OS label is produced.

---

# 107. TCP SYN Oracle Gate

Controlled fixture must reproduce:

```text
TTL

window

MSS

window scale

SACK

timestamps

exact option order
```

No p0f classification.

---

# 108. TLS JA4 Closure Facts + Gate D Oracle


PRE-FINAL Suricata 8.0.6 fixture:

```text
TLS events =
156

TLS events with JA4 =
156

coverage =
156 / 156
```

Observed JA4 A prefixes include:

```text
t13...
t12...
```

Observed L2 field:

```text
ether.src_mac =
PRESENT
```

Observed `client_handshake` representation:

```text
object with:
ciphers
exts
sig_algs
version
```

Observed:

```text
client_handshake.exts =
integer extension TYPE list
```

Durable contract remains:

```text
tls_version_family =
validated JA4 A component authority

client_handshake.version =
transient consistency/debug only

server-handshake version =
not used
```

POST-IMPLEMENTATION Gate D MUST prove the implemented adapter:

```text
accepts valid TLS-family JA4

splits JA4 exactly

maps version family from JA4 A

preserves approved client ALPN order

derives ECH/GREASE only from transient extension TYPE values

uses top-level EVE timestamp as observed_at

uses ether.src_mac as observed_mac

uses guest src_ip as observed_ip
```

Durable normalized/spool output must contain NO:

```text
SNI
JA3
JA3S
certificate
ClientHello
raw extension list
```

---

# 109. QUIC JA4 Closure Facts + Gate D Oracle


PRE-FINAL Suricata 8.0.6 fixture:

```text
QUIC events =
447

QUIC events with JA4 =
55
```

Observed JA4 A prefixes include:

```text
q13...
q00...
```

Observed:

```text
ether.src_mac =
PRESENT

quic.extensions[].type =
integer TYPE values
```

ECH extension type:

```text
65037
```

was observed.

Observed `quic.version` JSON representation:

```text
STRING
```

including:

```json
"1"
"faceb002"
```

POST-IMPLEMENTATION Gate D MUST prove the implemented adapter:

```text
accepts required QUIC-family JA4

validates exact JA4 structure

normalizes quic.version
according to section 60

derives ECH/GREASE from extension TYPE only

uses top-level EVE timestamp as observed_at

uses ether.src_mac as observed_mac

uses guest src_ip as observed_ip
```

Durable normalized/spool output contains NO:

```text
SNI
UA
JA3
JA3S
CYU
extension values
raw QUIC Initial
```

---

# 110. Central Evidence Registration Gate

Task-02 tests must prove:

```text
build_production_schema_registry()
contains exactly:

("dhcp", 1)

("tcp_syn", 1)

("tls_client", 1)

("quic_client", 1)
```

and still rejects:

```text
unknown source kind

unknown schema version

extra payload fields

invalid field types

forbidden P2 keys
```

---

# 111. Task-01 Regression Gate

Task-02 MUST prove no change to:

```text
Task-01 HTTP endpoint contract

Bearer auth

CIDR authorization

batch atomicity

retry idempotency

retention

central schema v1 tables/indexes

source-health schema

read API
```

Only production payload registry expands.

---

# 112. Startup Isolation Constraint

Separate debt:

```text
TASK-STARTUP-AVAILABILITY-01-DRAFT
```

is explicitly OUT OF Task-02 scope.

Task-02 MUST NOT:

```text
reorder run.py startup

change main Flask listener lifecycle

change Observation startup

change Traffic Projection source semantics
```

Task-02 only ensures:

```text
sensor waits one-way for core readiness

core never waits for sensor
```

---

# 113. Task-02 Non-Goals

Not implemented:

```text
Portal UA / Client Hints producer
→ Task-03

multi-platform labeled matrix
→ Task-03A

classification engine
→ Task-04

device_id / visit_id / auth_session integration
→ Task-05

Device Card/Admin fingerprint UI
→ Task-06

DNS ecosystem evidence
→ optional later task

mDNS evidence
→ optional later task

IoT classification

active scans

active fingerprinting
```

---

# 114. No Production Sensor Activation By Merge

Repository default:

```text
DEVICE_FINGERPRINT_SENSOR_ENABLED=false
```

Suricata/sensor units are:

```text
installed but disabled/inactive
```

after code deployment until separate Owner activation.

Task-01 evidence service activation is also separate production procedure.

---

# 115. Mutable Checkout Lifecycle

Task-02 Python sensor executes from:

```text
/opt/CaptivePortal
```

Therefore before Git checkout/artifact mutation:

```text
fingerprint-sensor.service
must be stopped
if active
```

Existing Task-01 rule also requires:

```text
fingerprint-evidence.service
stopped before checkout mutation
```

If Suricata config is repository-derived and deployed from same artifact,
deployment must update it only while Suricata service is stopped.

---

# 116. Repository Deployment / Package / libpcap Boundary


Exact repository subtree:

```text
deploy/device-fingerprint/
```

Exact repository artifacts:

```text
deploy/device-fingerprint/suricata.yaml

deploy/device-fingerprint/raw-capture.bpf

deploy/device-fingerprint/fingerprint-suricata.service

deploy/device-fingerprint/fingerprint-sensor.service
```

Repository files are templates/artifacts, not live unit files.

Production unit targets:

```text
/etc/systemd/system/fingerprint-sensor.service

/etc/systemd/system/fingerprint-suricata.service
```

Production Suricata config:

```text
/etc/captive-portal/device-fingerprint/suricata.yaml
```

Production raw-capture BPF artifact:

```text
/etc/captive-portal/device-fingerprint/raw-capture.bpf
```

Non-secret deployed config/BPF:

```text
root:root

0644
```

No secret may be placed in repository deploy artifacts.

Producer Bearer credential remains under its separately protected secret-storage
contract.

## Frozen package facts

```text
Suricata =
8.0.6 RELEASE

Ubuntu Suricata package =
1:8.0.6-0ubuntu2

source =
OISF Suricata stable PPA / Jammy

libpcap runtime package =
libpcap0.8

libpcap version =
1.10.1-4ubuntu1.22.04.1
```

## Raw BPF implementation direction

No Python packet-capture framework dependency is added.

Forbidden:

```text
Scapy

pcapy

new Python libpcap wrapper/framework
```

Use Python stdlib:

```text
ctypes

ctypes.util
```

and system libpcap:

```text
pcap_open_dead(DLT_EN10MB, snaplen)

pcap_compile(...)

copy compiled bpf_program
into Linux sock_filter[] / sock_fprog

setsockopt(
    SOL_SOCKET,
    SO_ATTACH_FILTER,
    ...
)

pcap_freecode(...)

pcap_close(...)
```

Kernel filter attaches BEFORE raw receive loop.

Gate D proves unrelated RSPAN traffic never increments:

```text
raw_packet_count
```

Enabled sensor uses:

```python
capture_loaded_artifact_identity(
    "fingerprint-sensor.service"
)
```

Artifact identity failure:

```text
fail closed

no capture
```

---

# 117. Existing Files To Modify


Modify only as required:

```text
app/device_fingerprint/schema_registry.py

.env.example

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

docs/modules/device-fingerprint.md
```

Explicitly removed from Task-02 MODIFY scope:

```text
app/config.py

app/settings.py
```

because sensor-only environment parsing must not enter the main runtime import
path.

No unrelated documentation rewrite.

---

# 118. Explicit NO-TOUCH Application Areas


```text
run.py

app/__init__.py

app/config.py

app/settings.py

app/auth/**

app/web/**

app/capport/**

app/visitor_registry/**

app/visit_lifecycle/**

app/observations/**

app/current_state/**

app/analytics/**

app/admin_web/**

app/traffic_projection/**
```

Task-02 must not create a sensor import edge from any of these domains.

---

# 119. Proposed Test Boundary

New:

```text
tests/device_fingerprint/test_network_schemas.py

tests/device_fingerprint_sensor/__init__.py

tests/device_fingerprint_sensor/test_config.py

tests/device_fingerprint_sensor/test_dedup.py

tests/device_fingerprint_sensor/test_scope.py

tests/device_fingerprint_sensor/test_dhcp.py

tests/device_fingerprint_sensor/test_tcp_syn.py

tests/device_fingerprint_sensor/test_eve.py

tests/device_fingerprint_sensor/test_spool.py

tests/device_fingerprint_sensor/test_producer.py

tests/device_fingerprint_sensor/test_health.py

tests/device_fingerprint_sensor/test_runtime.py

tests/device_fingerprint_sensor/test_cli.py
```

PCAP fixtures:

```text
tests/fixtures/device_fingerprint/
```

must be sanitized and bounded.

---

# 120. Gate A — Exact Coder Focused Verification


Only after FINAL + explicit Owner implementation authorization, Coder runs
exactly:

```bash
python -m pytest -q \
  tests/device_fingerprint/test_network_schemas.py \
  tests/device_fingerprint_sensor
```

Then:

```bash
python -m compileall -q \
  app/device_fingerprint \
  app/device_fingerprint_sensor
```

Then:

```bash
git diff --check
```

Coder records:

```text
baseline commit/tree

changed files

exact commands

passed/skipped/failed

environment

candidate identity

anything not executed
```

Coder MUST NOT run:

```text
official Central Lab/full repository regression

live Suricata acceptance

production activation
```

Suricata live/config verification belongs to external Linux Gate D.

---

# 121. Gate B — Tech Lead Static / Source Review

Mandatory.

Verify:

```text
FINAL conformance

same-VM architecture

no run.py change

no auth change

no raw persistence

Task-01 API unchanged

four schema keys exact

payload schemas exact

dedup exact

guest scope exact

DHCP mixed-VLAN scope protection

spool bounds

retry semantics

secret handling

Suricata privacy config

capability isolation

systemd direction

documentation reconciliation
```

Result:

```text
PASS
or
RETURN TO CODER
```

---

# 122. Gate C — Central Full Regression

Required:

```text
YES
```

Use fresh discovered official Central Lab gate.

Physical operator:

```text
Owner
```

Technical direction / evidence:

```text
Tech Lead
```

Must verify no regression to existing CaptivPortal product.

Candidate immutable identity rules from Task-01 remain applicable.

---

# 123. Gate D — Linux Sensor Functional + Suricata Acceptance


Required:

```text
YES
```

Execution point:

```text
AFTER:
Coder Gate A
TechLead Gate B
Central candidate preparation

BEFORE:
final exact-candidate acceptance/publication
```

Gate D executes ONLY against the implemented immutable candidate.

It must prove:

```text
sensor config isolation

disabled CLI no-op

artifact identity fail-closed

core TCP readiness implementation

libpcap0.8 available

ctypes/libpcap implementation

pcap_open_dead / pcap_compile path

SO_ATTACH_FILTER implementation

unrelated traffic excluded
before raw_packet_count

AF_PACKET least privilege

interface exactness

raw dedup implementation uses
the PRE-FINAL frozen horizon

DHCP implementation uses
the PRE-FINAL frozen authority

DHCP observed_ip no-backfill

source-health generation

Suricata exact 8.0.6

vendor suricata.service
inactive/non-auto-start

suricata -T

FINAL-frozen capability set

TLS JA4 PASS

QUIC JA4 PASS

JA4 structural validation

actual EVE multiplicity behavior
matches frozen adapter contract

actual quic.version representation
matches frozen adapter contract

client_handshake extension behavior

ether.src_mac

custom EVE receiver

Unix datagram lifecycle

262144-byte datagram bound

MSG_TRUNC rejection/degraded behavior

producer HTTPS/retry implementation

spool schema/runtime implementation

near-cap spool physical-footprint proof

sensor restart recovery

custom systemd service runtime behavior

full EVE socket replacement/reconnect integration
```

If TLS or QUIC JA4 fails:

```text
Gate D =
FAIL

production activation =
BLOCKED
```

If runtime privilege behavior differs from the FINAL-frozen capability contract:

```text
Gate D =
FAIL
→ return exact evidence to TechLead
```

Gate D does NOT generate architecture facts that should have been frozen
pre-FINAL.

---

# 124. Gate E — Same-VM Failure Isolation

Required:

```text
YES
```

Prove separately:

```text
sensor disabled
→ Authorization unaffected

sensor process crashed
→ Authorization unaffected

Suricata crashed
→ Authorization unaffected

spool unavailable
→ Authorization unaffected

evidence service unavailable
→ Authorization unaffected

enp8s0 down
→ Authorization unaffected
```

Also:

```text
enp1s0 default route unchanged

Portal remains operational
```

---

# 125. Gate F — Deterministic Same-VM Resource / Soak


Required:

```text
YES
```

Minimum:

```text
2-hour sensor-on soak
```

Same immutable candidate.

Collect:

```text
CPU/cgroup usage

RAM/cgroup usage

Suricata packet counters

Suricata kernel drops

EVE rate

normalized evidence rate

spool growth/bytes

raw dedup ratio using FINAL-calibrated horizon

Task-01 ingest rate

Authorization session telemetry

Observation health

Current State health

Visit Lifecycle health

Traffic Projection health
```

Suricata packet drop calculation is EXACTLY section 96.

Authorization p95 calculation is EXACTLY section 99.

Resource ceilings remain section 93.

Infrastructure packet visibility alone is insufficient.

Any core regression attributable to Task-02:

```text
FAIL
```

---

# 126. Gate G — Privacy / Durable Storage Proof

Required.

Search all Task-02 durable locations and logs.

Must prove absence of:

```text
pcap

raw frame bytes

SNI

DNS history

full EVE

JA3

raw ClientHello

raw QUIC Initial

credentials
```

Spool must contain only approved normalized JSON.

---

# 127. Candidate Identity / Publication Governance

Same project invariant:

```text
all required gates apply
to one immutable candidate
```

Record:

```text
baseline commit/tree

candidate patch SHA256
or immutable Lab candidate commit/tree

changed files
```

Before official gates PASS:

```text
NO normal publication commit
NO push
NO PR
```

After exact-candidate acceptance:

```text
Tech Lead may separately authorize
branch / commit / push / Draft PR
```

No merge/deploy/activation implied.

---

# 128. Production Activation Order — Frozen


Merge/deploy does NOT activate Task-02.

Safe Suricata package/service procedure proven PRE-FINAL:

```text
1.
mask vendor suricata.service
BEFORE package installation

2.
install exact Suricata candidate:
1:8.0.6-0ubuntu2

3.
verify vendor suricata.service
remains inactive

4.
ensure vendor suricata.service
remains masked

5.
apt-mark hold suricata
```

Production invariant:

```text
vendor suricata.service =
masked + inactive

ONLY:
fingerprint-suricata.service

may capture enp8s0 for Task-02
```

Full activation order:

```text
1.
deploy accepted code
with sensor disabled

2.
perform frozen safe Suricata package procedure

3.
verify exact:
Suricata 8.0.6 RELEASE
package 1:8.0.6-0ubuntu2

4.
verify:
libpcap0.8
1.10.1-4ubuntu1.22.04.1

5.
create service identities/groups/directories

6.
deploy accepted:
Suricata config
raw BPF
custom systemd units

7.
deploy sensor CA trust
and producer credential

8.
verify Task-01 evidence service
ONLY IF Owner independently activated it

If Task-01 is unavailable:
Task-02 may start and spool.

Task-02 MUST NOT start Task-01.

9.
verify enp8s0 safety preflight

10.
verify TCP 127.0.0.1:8088 ready

11.
start fingerprint-sensor.service ONLY

12.
prove:
spool ready
producer worker ready
interface preflight PASS
raw BPF attached
raw capture ready
EVE socket ready

13.
start fingerprint-suricata.service SEPARATELY

14.
prove vendor suricata.service
still masked + inactive

15.
prove:
DHCP
TCP SYN
TLS JA4
QUIC JA4
source health
normalized delivery/spool behavior

16.
execute required failure-isolation/resource/privacy acceptance

17.
only after Owner acceptance:
separately authorize persistent enable-at-boot
```

Rollback stops Task-02 custom services and does not touch core CaptivPortal,
network infrastructure or Task-01 canonical evidence DB unless separately
Owner-authorized.

---

# 129. Architecture Risks

Primary risks:

```text
same-VM CPU/RAM contention

RSPAN duplicates

mixed VLAN10/VLAN20 capture scope

raw capture privilege

Suricata transient privacy fields

spool growth during ingest outage

Task-01 schema mismatch

cold-start workload contention
```

Each has an explicit control in this DRAFT.

---

# 130. PRE-FINAL Bounded Architecture Closure — PASS

Closure result:

```text
PRE-FINAL BOUNDED ARCHITECTURE CLOSURE =
PASS

NO FURTHER PRE-FINAL HOST TESTING REQUIRED
```

Frozen measured facts:

```text
RAW_DEDUP_HORIZON_MS =
0.25

DHCP_SERVER_AUTHORITY =
192.168.10.1

DHCP_OPTION54_AUTHORITY =
192.168.10.1

Suricata =
8.0.6 RELEASE

Suricata Ubuntu package =
1:8.0.6-0ubuntu2

Suricata source =
OISF stable PPA / Jammy

libpcap0.8 =
1.10.1-4ubuntu1.22.04.1

vendor suricata.service =
masked + inactive

suricata package =
APT hold

TLS JA4 =
SUPPORTED / FIXTURE PASS

QUIC JA4 =
SUPPORTED / FIXTURE PASS

semantic JA4 suppressor =
NONE

Suricata capability implementation target =
CAP_NET_RAW only

PRE-FINAL CAP_NET_RAW feasibility =
NOT EXECUTED

POST-IMPLEMENTATION Gate D privilege proof =
MANDATORY
```

Privacy closure evidence:

```text
persistent PCAP =
NO

fixture EVE =
RAM-backed only

fixture EVE after test =
REMOVED

durable SNI/destination fixture output =
NONE
```

Informational PRE-FINAL performance sample:

```text
duration =
90 seconds

Suricata packets =
378438

drops =
1439

drop ratio =
~0.38%
```

This performance sample is NOT Gate F acceptance.

All application-runtime proofs remain POST-IMPLEMENTATION:

```text
Gate A
Gate B
Gate C
Gate D
Gate E
Gate F
Gate G
```


---

# 131. FINAL Control Status

```text
TASK =
TASK-DEVICE-FINGERPRINT-02-FINAL

ARCHITECTURE =
PASS

TECHNICAL CONTRACT =
COMPLETE

PRE-FINAL CLOSURE =
PASS

REPOSITORY BASELINE =
CURRENT / NO DRIFT

CURRENT GATE =
TECHLEAD10 FINAL SOURCE / CONSISTENCY REVIEW

TECHLEAD10 FINAL PASS =
PENDING

IMPLEMENTATION-READY =
YES — CONTRACT COMPLETE

OWNER IMPLEMENTATION AUTHORIZATION =
NOT GRANTED

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

MERGE =
NOT AUTHORIZED BY THIS FINAL

DEPLOY =
NOT AUTHORIZED

PRODUCTION ACTIVATION =
NOT AUTHORIZED
```


---

# 132. Next Workflow

```text
TASK-DEVICE-FINGERPRINT-02-FINAL
        ↓
TechLead10 FINAL source / consistency review
        ↓
FINAL PASS
        ↓
Owner explicit implementation authorization
        ↓
Coder implementation
        ↓
Gate A — focused Coder verification
        ↓
Gate B — Tech Lead static/source review
        ↓
Gate C — Central full regression
        ↓
Gate D — Linux sensor + Suricata functional acceptance
        ↓
Gate E — same-VM failure isolation
        ↓
Gate F — deterministic resource / soak / performance
        ↓
Gate G — privacy / durable-storage proof
        ↓
Owner + TechLead exact-candidate acceptance
        ↓
separate publication authorization
        ↓
branch / publication commit / push / Draft PR
        ↓
Owner-controlled merge
        ↓
separate deploy authorization
        ↓
separate production activation authorization
```

Until TechLead10 FINAL PASS + Owner explicit implementation authorization:

```text
CODER = HOLD

NO IMPLEMENTATION

NO BRANCH

NO COMMIT

NO PUSH

NO PR

NO DEPLOY

NO PRODUCTION ACTIVATION
```

**End of TASK-DEVICE-FINGERPRINT-02-FINAL.**

