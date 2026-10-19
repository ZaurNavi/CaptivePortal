# TASK-DEVICE-FINGERPRINT-02-DRAFT-R4

## Core Packet Sensor + Network Evidence

**Project:** CaptivPortal  
**Program:** Device Fingerprint  
**Parent foundation:** `TASK-DEVICE-FINGERPRINT-01`  
**Research predecessor:** `DEVICE-FINGERPRINT-00 FINAL R2`  
**Revision:** `DRAFT-R4`  
**Prepared:** 2026-09-14  
**Status:** `FOR TECHLEAD10 SOURCE / ARCHITECTURE REVIEW`  
**Implementation-ready:** `NO`  
**Coder:** `HOLD`  
**Implementation authorization:** `NOT GRANTED`  
**Production activation:** `NOT AUTHORIZED`

---

# 0. Control Gate — FIX-3A…FIX-3C INCORPORATED


```text
DEVICE-FINGERPRINT-00 =
CLOSED / PASS

TASK-DEVICE-FINGERPRINT-01 =
IMPLEMENTED / MERGED / CONSUMED

TASK-DEVICE-FINGERPRINT-02-DRAFT-R3 =
TECHLEAD10 FIX-3 — FINAL NARROW CONSISTENCY FIX

TASK-DEVICE-FINGERPRINT-02-DRAFT-R4 =
FIX-3A…FIX-3C INCORPORATED

ARCHITECTURE CORE =
PASS / PRESERVED

FIX-2A…FIX-2K =
PRESERVED

NEW BROAD RESEARCH =
NOT REQUIRED

PRE-FINAL ARCHITECTURE CLOSURE =
PENDING AFTER R4 PASS

POST-IMPLEMENTATION ACCEPTANCE =
DEFINED / NOT YET EXECUTABLE

IMPLEMENTATION-READY =
NO

CODER =
HOLD

IMPLEMENTATION =
NOT AUTHORIZED

PRODUCTION ACTIVATION =
NOT AUTHORIZED
```

R4 changes ONLY:

```text
FIX-3A =
remove last TLS-version contradiction

FIX-3B =
separate pre-FINAL architecture closure
from post-implementation acceptance

FIX-3C =
restore Gate D / workflow sequencing

EDITORIAL =
specified stale R2→R3 wording cleanup
```

No architectural redesign.

---

# 1. Fresh Repository Rebind

Repository:

```text
ZaurNavi/CaptivePortal
```

Fresh `main` at DRAFT assembly:

```text
HEAD =
414de85c311e72405dc25446461dcd458b5ae597

TREE =
9f267dc0944a91f7a4b81dccee8a77e0ec05fbe0
```

Current main includes:

```text
PR #122
TASK-DEVICE-FINGERPRINT-01
Device Fingerprint Evidence Foundation
```

Task-01 current repository state confirms:

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
EMPTY

initial authorized source kinds =
dhcp
tcp_syn
tls_client
quic_client
```

TechLead10 must fresh-rebind this baseline again before any
implementation-ready FINAL.

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

# 18. Core Listener Readiness Guard — FIX-1A


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

# 19. systemd Dependency Direction — FIX-2A


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

# 20. Suricata Version

V1 freezes:

```text
Suricata =
8.0.6
```

Installation source:

```text
official OISF Suricata 8 Ubuntu PPA
for Ubuntu 22.04 Jammy
```

Acceptance requires:

```text
suricata -V / build-info
reports 8.0.6
```

Automatic major/minor upgrade:

```text
NOT ALLOWED
```

Any Suricata version change:

```text
requires Task-02 compatibility recheck
for EVE fields / JA4 behavior / performance
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

# 23. Suricata Capture Filter — FIX-1C


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

# 24. EVE Unix Datagram Lifecycle — FIX-1G


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

# 26. TLS EVE Privacy Configuration — FIX-3A


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

# 27. QUIC EVE Privacy Projection — FIX-1I


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

# 28. Suricata L2/L3 Identity Authority — FIX-1H


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

# 29. Raw Capture Path + Kernel BPF — FIX-1C


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

# 31. Suricata Privilege Model — FIX-2I


R3 selects a dedicated non-root service model:

```text
User=suricata
Group=suricata
```

Initial capability candidate:

```text
AmbientCapabilities=CAP_NET_RAW
CapabilityBoundingSet=CAP_NET_RAW
NoNewPrivileges=true
```

Not granted by default:

```text
CAP_NET_ADMIN
CAP_SYS_NICE
CAP_SYS_ADMIN
```

Before FINAL, bounded Gate D proves exact minimum privileges on Suricata 8.0.6
AF_PACKET/enp8s0 with frozen config.

Proof starts with CAP_NET_RAW only.

If a specific required operation demonstrably needs CAP_NET_ADMIN or
CAP_SYS_NICE, return exact evidence to Architect/TechLead10 before FINAL.

No broad root runtime and no conflicting root-start + privilege-drop model.

---

# 32. Runtime / Spool Filesystem Boundary — FIX-1G/FIX-1J


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

# 36. Raw Exact-Frame Dedup — FIX-1D


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
nanosecond-resolution where available
```

Bounded in-memory cache:

```text
maximum entries =
65,536
```

The duplicate horizon is NOT frozen in R3.

Current status:

```text
RAW_DEDUP_HORIZON =
CALIBRATION_REQUIRED BEFORE FINAL
```

Only the measured horizon accepted by Architect + TechLead10 may enter FINAL.

Raw frame bytes are discarded immediately after parse/dedup processing.

---

# 37. Raw Dedup Calibration Gate — FIX-1D


Before Task-02 FINAL, run one bounded calibration on the proven path:

```text
Catalyst RSPAN
→ enp7s0f1.999
→ macvtap/direct
→ enp8s0
```

Calibration capture scope is the same raw BPF as production:

```text
DHCPv4
+
outbound guest IPv4 TCP SYN
```

Bound:

```text
maximum duration =
120 seconds

maximum admitted packets =
250,000

whichever occurs first
```

Calibration does NOT persist raw packets.

It may retain only transient:

```text
BLAKE2s-128 frame hash

capture length

packet class

receive timestamp

repeat delta
```

Output is a bounded summary only:

```text
exact-frame repeat count

repeat-delta histogram

verified mirror duplicate delta distribution

verified legitimate repeated-frame/retransmission delta distribution

candidate safe horizon

ambiguous/overlap count
```

Horizon acceptance rule:

```text
there must be a measurable separation
between verified mirror-copy deltas
and legitimate repeated-frame deltas
```

If distributions overlap such that no safe horizon exists:

```text
FAIL

do not deploy time-window exact-frame dedup

return to Architect + TechLead10
```

Coder may not choose/tune the horizon.

The earlier `2 ms` number is explicitly NOT treated as research-proven.

---

# 38. Suricata Semantic Event Handling — FIX-1E


V1 has:

```text
NO 30-second
flow + MAC + IP + JA4
semantic suppression
```

Every qualifying Suricata TLS/QUIC client event that passes normalization creates
one new normalized source event with one stable newly-created
`source_event_id`.

Task-01 idempotency handles only HTTP delivery retry duplication.

Gate D must feed controlled duplicated TLS/QUIC traffic through Suricata 8.0.6
and record:

```text
input handshake count

Suricata EVE count

normalized event count
```

If duplicate semantic EVE events are actually proven:

```text
STOP

capture the exact observed duplicate discriminator

return to Architect + TechLead10

define a narrow dedup rule
from observed transaction/event identity
```

Any future EVE dedup must use an exact transaction/event discriminator where
available.

JA4 + flow + long TTL alone is forbidden as a dedup identity.

---

# 39. Dedup / Capture Telemetry — FIX-1C/FIX-1E


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

# 42. DHCP Scope Resolver — FIX-2D


R3 candidate guest DHCP authority:

```text
guest CIDR =
192.168.8.0/22

candidate server source =
192.168.10.1

candidate option 54 =
192.168.10.1
```

These two authority values are NOT FINAL until bounded live proof on `enp8s0`.

Before FINAL observe one controlled/normal guest OFFER or ACK and retain only:

```text
server source IP
option 54
yiaddr guest/not-guest
client MAC
XID
MAC+XID correlation result
timestamp
```

No raw durable capture.

If observed authority differs, do not force 192.168.10.1; return observed values
and freeze them in FINAL.

After authority is frozen, zero-address DORA release requires:

```text
same MAC+XID transaction
OFFER/ACK
yiaddr ∈ guest CIDR
server source == frozen authority
option 54 == frozen authority
```

`requested_ip` alone never establishes Site authority.

---

# 43. DHCP Message-Specific Scope Rules — FIX-1F


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

# 47. DHCP Complete Task-01 Envelope — FIX-2C


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

# 51. TCP SYN Complete Task-01 Envelope — FIX-1H


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

# 52. TLS JA4 Schema Registration — FIX-1H


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

# 54. JA4 Structural Validation — FIX-2K


Task-02 validates Suricata-produced JA4; it never reconstructs JA4.

Full shape:

```text
A_B_C
```

Exactly three components.

`B` and `C`:

```text
exactly 12 lowercase hex each
```

A component is exactly 10 characters:

```text
0      transport
1..2   TLS version code
3      SNI flag
4..5   cipher count
6..7   extension count
8..9   ALPN representation
```

R3 candidate structural parser:

```text
transport =
t | q

version =
13 | 12 | 11 | 10 | s3 | s2 | 00

SNI =
d | i

cipher count =
two ASCII decimal digits

extension count =
two ASCII decimal digits

ALPN representation =
two ASCII alphanumeric chars
```

Family constraints:

```text
tls_client → transport t
quic_client → transport q
```

Before FINAL, controlled Suricata 8.0.6 fixtures must confirm exact accepted
A-component output domain. A valid fixture outside this candidate parser returns
a narrow FIX; validation is not loosened generically.

---

# 55. TLS Version Authority — FIX-2E


Durable:

```text
tls_version_family
```

derives ONLY from validated TLS JA4 A component:

```text
ja4_a[1:3] == "13" → tls1_3
ja4_a[1:3] == "12" → tls1_2
anything else       → other
```

`tls.client_handshake.version` may be inspected transiently only as
consistency/debug evidence.

It is NOT durable TLS-version authority.

No server TLS version is used.

`client_handshake` remains transiently useful for extension TYPE information,
ECH presence and GREASE presence.

`client_alpns` remains separately approved.

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

# 57. TLS Complete Envelope / Quality — FIX-2E


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

# 58. QUIC JA4 Schema Registration — FIX-1H


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

# 60. QUIC Version Adapter — FIX-1H


Normalized durable form:

```text
0x
+
8 lowercase hex digits
```

Example:

```text
0x00000001
```

Suricata 8.0.6 documentation is internally inconsistent between examples and
generated schema about JSON representation of `quic.version`.

Therefore adapter behavior is fixture-driven.

R3 candidate allows only representations proven by the Task-02 Suricata 8.0.6 fixture:

```text
A.
JSON integer
0..4294967295

B.
JSON decimal string
whose parsed unsigned value is 0..4294967295

C.
JSON hexadecimal string
matching:
0x[0-9A-Fa-f]{1,8}
```

All are normalized to:

```text
0x########
lowercase
```

Any other representation:

```text
NO evidence

quic_version_invalid += 1
```

Before FINAL, Gate D fixture evidence must confirm which subset of A/B/C
Suricata 8.0.6 actually emits; FINAL may narrow but MUST NOT widen beyond proven
representations.

---

# 61. QUIC Extension Presence + Complete Envelope — FIX-1H


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

# 62. Required JA4 Capability / Runtime Failure Semantics — FIX-2F


Initial Task-02 V1 acceptance requires:

```text
dhcp = available
tcp_syn = available
tls_client = available
quic_client = available
```

Gate D:

```text
TLS JA4 fixture = PASS
QUIC JA4 fixture = PASS
```

If accepted Suricata 8.0.6 build cannot produce either JA4 family:

```text
Gate D = FAIL
Production activation = BLOCKED
```

Runtime `unsupported` may remain observable for an unexpected later capability
loss, but it cannot satisfy initial V1 acceptance.

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

# 65. Sensor Package Boundary — FIX-1B/FIX-1K


New package remains:

```text
app/device_fingerprint_sensor/
```

Exact R3 proposal:

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

# 66. Sensor-Only Configuration Boundary — FIX-1B


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

# 67. Sensor Defaults — R3


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
NOT SET UNTIL CALIBRATION / FINAL

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

There is NO semantic JA4 dedup TTL setting in V1.

Enabled production validation requires the frozen interface/site/producer/capture
identity values.

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

# 69. Spool SQLite Operational Budget — FIX-2G


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

# 70. Spool Transaction Bounds — FIX-2G


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

# 72. Spool Capacity Algorithm — FIX-2G


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

# 73. Spool Clock / Stale Expiry — FIX-1J


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

# 84. Sensor Runtime State / V1 Acceptance — FIX-2F


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

# 85. Sensor CLI Startup — FIX-2B


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

# 87. Suricata Service Startup / Reconnect — FIX-1G/FIX-1K


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

# 93. Resource Isolation — Accepted Ceilings / Capability Proof Pending


Accepted resource ceilings remain unchanged.

Suricata exact capabilities are NOT FINAL-frozen.

R3 candidate:

```text
CAP_NET_RAW only
```

Before FINAL, Gate D proves exact minimum set.

No CAP_NET_ADMIN or CAP_SYS_NICE by default.

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

# 95. Resource / Capture Telemetry — FIX-1L


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

# 96. Performance Gate — Exact Suricata Packet-Loss Metric — FIX-1L


Use Suricata EVE `stats` counters over the same measurement window:

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

Gate:

```text
<= 0.01
(1.0%)
```

over each required 15-minute sustained evaluation segment.

Also record:

```text
capture.kernel_ifdrops
```

when available, but it is not substituted into the kernel-drop denominator.

Counter reset/process restart invalidates that segment and it must be rerun.

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

# 99. Performance Gate — Deterministic Authorization p95 — FIX-1L


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

# 101. Near-Cap Spool Physical-Footprint Gate — FIX-2G


Before FINAL, controlled near-cap proof must record:

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

Acceptance wording:

```text
application behavior remains bounded
NO unbounded durable growth
operational budget controls behave as designed
```

Do not claim a filesystem-enforced absolute 128 MiB hard ceiling.

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

# 103. Suricata Restart / EVE Socket Lifecycle Gate — FIX-1G


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

# 105. Dedup Calibration / Fixture Set — FIX-1D/FIX-1E


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

# 108. TLS Oracle Gate — FIX-3A


Controlled Suricata 8.0.6 fixture must prove:

```text
TLS-family JA4 starts with "t"

full JA4 components split exactly

tls_version_family derives from
validated JA4 A component

ja4_a[1:3] == "13"
→ tls1_3

ja4_a[1:3] == "12"
→ tls1_2

other accepted JA4 version code
→ other

client_handshake.version
may be observed only for
consistency/debug proof

server-handshake version
is not used

ALPN client order preserved

ECH extension presence derived
only from transient client extension TYPES

GREASE presence derived
only from transient client extension TYPES

top-level EVE timestamp
→ observed_at UTC milliseconds

ether.src_mac
→ observed_mac

src_ip guest
→ observed_ip
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

Do NOT restore `tls.client_handshake.version` as durable TLS-version authority.

---

# 109. QUIC Oracle Gate — FIX-1H/FIX-1I


Controlled Suricata 8.0.6 fixture must prove:

```text
QUIC-family JA4 starts with "q"

full JA4 split exactly

actual emitted quic.version representation
belongs to allowed R3 candidate adapter set

normalized quic_version =
0x########

extension TYPE booleans correct or null

top-level EVE timestamp
→ observed_at UTC milliseconds

ether.src_mac
→ observed_mac

guest src_ip
→ observed_ip
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

The fixture result is source evidence for FINAL narrowing of accepted
`quic.version` input representations.

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

# 116. Repository Deployment + libpcap Boundary — FIX-2H/FIX-2K


Repository subtree remains:

```text
deploy/device-fingerprint/
```

Raw BPF implementation is frozen to Python stdlib `ctypes` + system libpcap.

No:

```text
Scapy
pcapy
new packet-capture Python framework
```

V1 calls:

```text
pcap_open_dead(DLT_EN10MB, snaplen)
pcap_compile(...)
copy bpf_program to Linux sock_filter/sock_fprog
setsockopt(SOL_SOCKET, SO_ATTACH_FILTER, ...)
pcap_freecode(...)
pcap_close(...)
```

Filter attaches before raw receive loop.

Ubuntu 22.04 runtime package:

```text
libpcap0.8
```

No runtime development package is required because no native Python extension is
compiled.

Before FINAL/activation runbook, record exact installed Jammy package version.

Gate D proves unrelated RSPAN traffic never increments `raw_packet_count`.

Enabled sensor continues to use existing artifact-identity mechanism and fails
closed before capture on identity failure.

---

# 117. Existing Files To Modify — FIX-1B


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

# 118. Explicit NO-TOUCH Application Areas — FIX-1B


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

# 120. Gate A — Exact Coder Focused Verification — FIX-1M


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

# 128. Production Activation Order — FIX-2A/FIX-2J


Merge/deploy does NOT activate Task-02.

Activation sequence:

```text
1. deploy accepted code with sensor disabled

2. install exact approved Suricata 8.0.6
   using approved no-auto-start procedure

3. prove vendor suricata.service:
   inactive
   and not permitted to auto-start

4. pin/prevent unattended Suricata version drift

5. create service identities/groups/directories

6. deploy approved config/BPF/custom units

7. verify libpcap0.8 installed/version recorded

8. deploy sensor CA trust + producer credential

9. verify Task-01 evidence service ONLY IF
   Owner independently activated it

   If Task-01 is unavailable:
   sensor may start and spool.
   Task-02 MUST NOT start Task-01.

10. verify enp8s0 safety

11. verify TCP 127.0.0.1:8088 ready

12. start fingerprint-sensor.service ONLY

13. prove spool/producer/interface/raw BPF/raw capture/EVE socket ready

14. start fingerprint-suricata.service SEPARATELY

15. prove vendor suricata.service still inactive/non-auto-start

16. prove all four evidence families + source-health/delivery

17. run resource/failure-isolation acceptance

18. only after Owner acceptance:
    separately authorize enable-at-boot
```

ONLY `fingerprint-suricata.service` may capture `enp8s0` for Task-02.

Exact safe apt/systemd no-auto-start procedure is frozen in FINAL activation
runbook.

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

# 130. TechLead10 Review — Architecture Delta

Please confirm:

```text
A.
old physical sensor placement
is superseded for Task-02

B.
same-VM placement:
192.168.0.202 / enp8s0
is accepted

C.
Task-01 remains closed/not reopened

D.
HTTPS/Bearer transport remains unchanged
```

---

# 131. TechLead10 Review — Process Topology

Please PASS/FIX:

```text
fingerprint-evidence.service
existing

fingerprint-sensor.service
new

fingerprint-suricata.service
new
```

and exact one-way dependency direction.

---

# 132. TechLead10 Review — Suricata

Please PASS/FIX:

```text
Suricata 8.0.6

OISF Ubuntu PPA

AF_PACKET

workers / 1 thread initial

EVE unix_dgram

TLS/QUIC/stats only

no persistent EVE

no rules/IPS
```

---

# 133. TechLead10 R3 Delta — FIX-2A/2B


Please PASS/FIX:

```text
no sensor pull-in of Task-01 evidence service
no sensor pull-in of Suricata

Suricata:
After/BindsTo/PartOf sensor

sensor starts alone

spool + producer before interface preflight

interface fail:
queue unavailable source-health if possible
one bounded delivery attempt
exit non-zero
```

---

# 134. TechLead10 R3 Delta — FIX-2C/2D


Please PASS/FIX:

```text
DHCP observed_ip =
original source/ciaddr only

NO yiaddr/requested_ip backfill

192.168.10.1 authority =
candidate only

bounded live proof required before FINAL
```

---

# 135. TechLead10 R3 Delta — FIX-2E/2F/2K


Please PASS/FIX:

```text
tls_version_family =
JA4 A component authority

client_handshake.version =
transient debug only

TLS JA4 mandatory
QUIC JA4 mandatory

JA4 structural parser:
10-char A + 12hex B + 12hex C

fixture must confirm exact output domain
```

---

# 136. TechLead10 R3 Delta — FIX-2G


Please PASS/FIX:

```text
128 MiB =
application operational budget

NOT filesystem hard quota

112 MiB main logical ceiling
bounded <=100-row transactions
pre/post physical checks
degrade/drop/stop-enqueue
NO unbounded growth
near-cap proof required
```

---

# 137. TechLead10 R3 Delta — FIX-2H/2I


Please PASS/FIX:

```text
stdlib ctypes + system libpcap
pcap_open_dead / pcap_compile / SO_ATTACH_FILTER
Ubuntu package libpcap0.8
no Scapy/pcapy

Suricata User=suricata Group=suricata
candidate CAP_NET_RAW only
no CAP_NET_ADMIN/SYS_NICE without proof
no root runtime
```

---

# 138. TechLead10 R3 Delta — FIX-2J


Please PASS/FIX:

```text
only fingerprint-suricata.service captures enp8s0

vendor suricata.service:
inactive
non-auto-start

package installation must prevent accidental vendor service startup

sensor starts first
Suricata starts separately
```

---

# 139. Accepted R2 Items Preserved


All TechLead10 PASS items from R2 remain preserved unless explicitly corrected
by FIX-2A…FIX-2K.

---

# 140. PRE-FINAL Bounded Architecture Closure Evidence — FIX-3B/FIX-3C


After TechLead10 R4 DRAFT consistency PASS, and BEFORE Architect issues FINAL,
run ONLY bounded evidence that does NOT depend on unimplemented Task-02
application code.

Required PRE-FINAL closure:

```text
1.
RAW RSPAN DUPLICATE CALIBRATION

Real path:
Catalyst RSPAN
→ enp7s0f1.999
→ enp8s0

Determine:
RAW_DEDUP_HORIZON_MS

or prove:
no safe horizon exists.

2.
LIVE DHCP AUTHORITY OBSERVATION

Determine actual:
guest DHCP server source IP
DHCP option 54 authority

Retain normalized proof only.
No raw durable capture.

3.
SURICATA 8.0.6
CONTROLLED FIXTURE / ENVIRONMENT PROOF

Determine:
TLS JA4 output
QUIC JA4 output
JA4 A-component actual domain
actual quic.version representation
client_handshake extension representation
ether.src_mac availability
TLS/QUIC semantic EVE multiplicity

4.
PACKAGE / ENVIRONMENT FACTS

Confirm:
exact available Suricata 8.0.6 package/source
exact libpcap0.8 package/version

Prepare:
safe package pin procedure
safe vendor-service no-auto-start procedure

5.
OPTIONAL PRE-FINAL
SURICATA PRIVILEGE FEASIBILITY

If an approved Linux environment is available,
a direct bounded Suricata test MAY prove:

CAP_NET_RAW only

If not performed pre-FINAL:

FINAL may freeze CAP_NET_RAW-only
as implementation target

and Gate D MUST prove it
post-implementation.

Coder may not silently add capability.
```

Explicitly NOT PRE-FINAL because these require Task-02 implementation:

```text
sensor config-isolation runtime proof

disabled sensor CLI behavior

artifact-identity runtime proof

core TCP readiness implementation proof

ctypes/libpcap implementation proof

SO_ATTACH_FILTER implementation proof

raw_packet_count implementation behavior

interface-preflight implementation

source-health generation

custom EVE receiver implementation

MSG_TRUNC implementation

producer HTTPS/retry implementation

spool schema/runtime implementation

near-cap spool physical-footprint proof

sensor restart recovery

custom systemd runtime behavior

full EVE socket replacement/reconnect integration

Gate D application-functional acceptance

Gate E failure isolation

Gate F resource/soak

Gate G durable privacy proof
```

No production activation is implied by PRE-FINAL closure evidence.

Any host-changing proof action still requires explicit Owner authorization.

---

# 141. Control Status — DRAFT-R4


```text
TASK =
TASK-DEVICE-FINGERPRINT-02-DRAFT-R4

ARCHITECTURE CORE =
PASS

FIX-2A…FIX-2K =
PRESERVED

FIX-3A…FIX-3C =
INCORPORATED

NEW BROAD RESEARCH =
NOT REQUIRED

CURRENT GATE =
TECHLEAD10 R4 FINAL DRAFT CONSISTENCY REVIEW

PRE-FINAL CLOSURE EVIDENCE =
NOT YET RUN

RAW DEDUP HORIZON =
NOT FINAL

DHCP SERVER AUTHORITY =
CANDIDATE / NOT FINAL

SURICATA PACKAGE / FIXTURE FACTS =
PENDING PRE-FINAL CLOSURE

SURICATA MINIMUM CAPABILITIES =
CAP_NET_RAW TARGET
OPTIONAL PRE-FINAL PROOF
OTHERWISE GATE D PROOF

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

PRODUCTION ACTIVATION =
NOT AUTHORIZED
```

---

# 142. Next Workflow — R4


```text
TASK-DEVICE-FINGERPRINT-02-DRAFT-R4
        ↓
TechLead10 final DRAFT consistency review
        ↓
PASS
        ↓
bounded PRE-FINAL architecture closure evidence
        ↓
freeze:
RAW_DEDUP_HORIZON_MS
DHCP authority
Suricata JA4 fixture facts
quic.version representation
EVE multiplicity
package/libpcap facts
safe package/service procedure
optional privilege feasibility fact
        ↓
Architect + TechLead10
TASK-DEVICE-FINGERPRINT-02-FINAL
        ↓
TechLead10 FINAL consistency PASS
        ↓
Owner explicit implementation authorization
        ↓
Coder implementation
        ↓
Gate A
        ↓
Gate B
        ↓
Central candidate preparation / Gate C
        ↓
Gate D
        ↓
Gate E
        ↓
Gate F
        ↓
Gate G
        ↓
exact-candidate acceptance/publication governance
```

Until Owner explicitly authorizes implementation:

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

**End of TASK-DEVICE-FINGERPRINT-02-DRAFT-R4.**

---

