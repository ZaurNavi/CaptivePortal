# TASK-DEVICE-FINGERPRINT-02-DRAFT-R2

## Core Packet Sensor + Network Evidence

**Project:** CaptivPortal  
**Program:** Device Fingerprint  
**Parent foundation:** `TASK-DEVICE-FINGERPRINT-01`  
**Research predecessor:** `DEVICE-FINGERPRINT-00 FINAL R2`  
**Revision:** `DRAFT-R2`  
**Prepared:** 2026-09-14  
**Status:** `FOR TECHLEAD10 SOURCE / ARCHITECTURE REVIEW`  
**Implementation-ready:** `NO`  
**Coder:** `HOLD`  
**Implementation authorization:** `NOT GRANTED`  
**Production activation:** `NOT AUTHORIZED`

---

# 0. Control Gate — FIX-1A…FIX-1N INCORPORATED


```text
DEVICE-FINGERPRINT-00 =
CLOSED / PASS

TASK-DEVICE-FINGERPRINT-01 =
IMPLEMENTED / MERGED / CONSUMED

TASK-DEVICE-FINGERPRINT-02-DRAFT =
TECHLEAD10 FIX-1

TASK-DEVICE-FINGERPRINT-02-DRAFT-R2 =
FIX-1A…FIX-1N INCORPORATED

ARCHITECTURE CORE =
ACCEPTED

SENSOR PLACEMENT =
SAME VM / 192.168.0.202 / enp8s0

OLD PHYSICAL SENSOR REQUIREMENT =
SUPERSEDED

NEW BROAD RESEARCH =
NOT REQUIRED

RAW DEDUP HORIZON =
PENDING BOUNDED CALIBRATION BEFORE FINAL

IMPLEMENTATION-READY =
NO

CODER =
HOLD

IMPLEMENTATION =
NOT AUTHORIZED

PRODUCTION ACTIVATION =
NOT AUTHORIZED
```

R2 changes only the TechLead10 FIX-1A…FIX-1N deltas on top of the accepted
Task-02 architecture.

Task-01 remains closed.

Startup Availability debt remains a separate task.

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

# 19. systemd Dependency Direction — FIX-1A/FIX-1G


Required one-way direction:

```text
fingerprint-sensor.service
After=captive-portal.service

fingerprint-sensor.service
Wants=fingerprint-evidence.service

fingerprint-sensor.service
After=fingerprint-evidence.service

fingerprint-sensor.service
Wants=fingerprint-suricata.service
```

`Wants=fingerprint-suricata.service` requests the auxiliary Suricata service
when the sensor starts; it does NOT make sensor readiness depend on Suricata readiness.

Forbidden:

```text
captive-portal.service Requires=fingerprint-sensor.service
captive-portal.service After=fingerprint-sensor.service
captive-portal.service Requires=fingerprint-suricata.service
```

Suricata:

```text
fingerprint-suricata.service

After=fingerprint-sensor.service
BindsTo=fingerprint-sensor.service
PartOf=fingerprint-sensor.service
```

`After=` alone is NOT socket readiness.

Suricata `ExecStartPre` must pass the bounded Unix-socket guard from sections 24/87.

Because sensor Wants Suricata and Suricata is PartOf/BindsTo sensor:

```text
sensor stop/restart
→ Suricata stops with it

sensor start/restart
→ Suricata is requested again
→ socket preflight waits for replacement socket
```

Core Authorization never waits for either Task-02 service.

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

# 26. TLS EVE Privacy Configuration — FIX-1I


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

`client_handshake` is transient and used only for:

```text
client hello version

extension TYPE presence
```

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

# 31. Suricata Privilege Model

Suricata uses dedicated system identity:

```text
suricata
```

Startup may require elevated capture privileges.

Frozen security direction:

```text
root only for capture initialization

Suricata run-as:
user=suricata
group=suricata

bounded capabilities:
CAP_NET_RAW
CAP_NET_ADMIN
CAP_SYS_NICE
```

No access to:

```text
Task-01 evidence DB

Portal auth secrets

Omada credentials

producer Bearer token
```

Suricata does not perform HTTP ingest.

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

The duplicate horizon is NOT frozen in R2.

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

# 42. DHCP Scope Resolver — FIX-1F


Mixed VLAN10/VLAN20 RSPAN requires stronger authority than a client-requested IP.

Frozen guest DHCP authority:

```text
guest CIDR =
192.168.8.0/22

expected guest DHCP server/source =
192.168.10.1

expected DHCP Server Identifier option 54 =
192.168.10.1
```

Transient transaction key:

```text
client MAC
+
DHCP transaction ID
```

Transaction cache TTL:

```text
60 seconds
```

No raw bytes in cache.

## Direct guest scope

A client packet is directly guest-scoped when an actual client-owned address is:

```text
IPv4 source ∈ 192.168.8.0/22

OR

ciaddr ∈ 192.168.8.0/22
```

## Zero-address DORA

For:

```text
0.0.0.0 → 255.255.255.255
```

client DISCOVER/REQUEST remains buffered.

It may be released only after same bounded MAC+XID transaction observes server:

```text
OFFER
or
ACK
```

with ALL:

```text
yiaddr ∈ 192.168.8.0/22

server packet source IPv4 =
192.168.10.1

DHCP option 54 Server Identifier =
192.168.10.1
```

`requested_ip` may assist correlation but:

```text
requested_ip ALONE
MUST NOT establish Site authority
```

Unproven transaction after 60 seconds:

```text
discard
```

No normalized evidence.

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

# 47. DHCP Complete Task-01 Envelope — FIX-1H


Frozen envelope:

```text
source_kind =
dhcp

source_subtype =
discover | request | inform | decline | release

extractor_name =
packet-dhcp

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
kernel packet receive timestamp
of the original CLIENT DHCP packet,
converted to canonical UTC milliseconds
```

NOT:

```text
scope-confirmation time

normalization time

spool time

delivery time
```

Identity authority:

```text
observed_mac =
original Ethernet client source MAC
```

When Ethernet/DHCP hardware identity permits exact cross-check, mismatched
client hardware address causes rejection/telemetry.

`observed_ip`:

```text
actual guest source/ciaddr
when directly present

OR

exact yiaddr/assigned guest address
from confirmed same transaction/lease correlation

OR

null when no exact guest client IP can be assigned
```

Quality:

```text
valid =
guest scope proven
+
complete structurally valid DHCP option parse

partial =
guest scope proven
+
core DHCP valid
+
optional fields absent
```

Malformed/truncated packet:

```text
NO evidence
```

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

# 54. JA4 Canonical Family Validation — FIX-1H


Common full JA4 structure:

```text
A_B_C
```

with:

```text
B =
12 lowercase hex

C =
12 lowercase hex
```

Stored:

```text
ja4
ja4_a
ja4_b
ja4_c
```

must split exactly.

TLS Task-02 validation additionally requires:

```text
ja4_a starts with:
t
```

QUIC Task-02 validation additionally requires:

```text
ja4_a starts with:
q
```

A payload is rejected if family prefix does not match `source_kind`.

Full JA4:

```text
4..128 printable ASCII
```

No arbitrary A-component family is accepted.

---

# 55. TLS Client Version / ALPN Contract — FIX-1H


TLS version MUST derive from CLIENT evidence.

Primary authority:

```text
tls.client_handshake.version
```

Normalize after trim/case-insensitive comparison:

```text
"TLS 1.2"
→ tls1_2

"TLS 1.3"
→ tls1_3

any other non-empty bounded client-version string
→ other
```

Do NOT use:

```text
tls.server_handshake.version

server-negotiated version

top-level tls.version as a client-version substitute
```

If `tls.client_handshake.version` is absent, the ONLY allowed fallback is the
already validated TLS JA4 A component:

```text
ja4_a[1:3] == "12"
→ tls1_2

ja4_a[1:3] == "13"
→ tls1_3

otherwise
→ other
```

Fallback use forces:

```text
quality_state =
partial
```

`client_alpns` is an ordered array of 0..8 printable ASCII strings, each 1..32 characters.

No server ALPN.

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

# 57. TLS Complete Envelope / Quality — FIX-1H


Timestamp authority:

```text
observed_at =
Suricata top-level EVE timestamp
converted to canonical UTC milliseconds
```

NOT normalization/spool/delivery time.

Identity:

```text
observed_mac =
EVE original ether.src_mac

observed_ip =
EVE src_ip
inside 192.168.8.0/22
```

Quality:

```text
valid =
JA4 family valid
+
MAC/IP valid
+
client version derived from client_handshake
+
extension metadata sufficient
```

```text
partial =
JA4/MAC/IP valid
but approved optional client metadata
(extension list or primary client version field)
is incomplete
```

No event without valid TLS-family JA4.

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

R2 allows only representations proven by the Task-02 Suricata 8.0.6 fixture:

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

# 62. QUIC Unavailable Behavior

If Suricata cannot produce QUIC JA4 for a valid guest flow:

```text
NO fabricated device evidence
```

If QUIC parser capability itself is unavailable:

```text
source-health:
quic_client =
unavailable

reason_code =
suricata_quic_unavailable
```

If runtime/package does not support QUIC JA4 at all:

```text
status =
unsupported
```

This must be explicit and observable.

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

Exact R2 proposal:

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

# 67. Sensor Defaults — R2


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

# 69. Spool SQLite Physical Contract — FIX-1J


Private transport spool:

```text
/var/lib/captive-portal/fingerprint-sensor/spool.sqlite3
```

SQLite mode:

```text
journal_mode =
DELETE

synchronous =
FULL

foreign_keys =
ON

busy_timeout =
500 ms

auto_vacuum =
NONE
```

No WAL mode.

Possible durable artifacts are therefore:

```text
spool.sqlite3

spool.sqlite3-journal
```

`spool_bytes` means:

```text
size(spool.sqlite3)
+
size(spool.sqlite3-journal if present)
```

The SQLite main DB logical ceiling is configured through:

```text
PRAGMA max_page_count
```

to:

```text
SPOOL_MAIN_DB_MAX_BYTES =
112 MiB
```

leaving:

```text
16 MiB
```

reserved durable transaction/headroom inside the absolute 128 MiB directory
budget.

No VACUUM is required for normal capacity recovery; freed pages are reused.

---

# 70. Spool Record / Transaction Bounds — FIX-1J


Each queued row stores only normalized transport data:

```text
queue_id

endpoint_kind =
evidence | source_health

event_id

observed_at

canonical_json

canonical_sha256

attempt_count

next_attempt_at

created_at
```

No token.

No raw packet/EVE.

Transaction bounds:

```text
enqueue transaction =
maximum 100 events

eviction/delete transaction =
maximum 100 rows

delivery acknowledgement delete =
maximum 100 rows
```

Canonical event size remains constrained by Task-01 payload/request limits.

The fixed transaction bounds plus 16 MiB reserved headroom are part of the hard
durable-footprint contract.

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

# 72. Spool Hard Capacity Algorithm — FIX-1J


Absolute Task-02 durable spool budget:

```text
all durable spool artifacts together
<=
134217728 bytes
```

Before EVERY durable enqueue:

```text
1. capture local UTC wall clock:
   datetime.now(timezone.utc)

2. purge stale rows

3. measure spool_bytes:
   main DB + rollback journal

4. check row-count bound

5. if capacity insufficient:
   evict according to frozen policy
   in bounded 100-row transactions

6. re-measure

7. only if:
   durable footprint + reserved transaction headroom
   remains within hard budget
   → insert

8. otherwise:
   DROP normalized evidence
   sensor → degraded
   emit spool_capacity_drop telemetry
```

Eviction order:

```text
oldest device evidence first
```

Source-health may receive higher eviction priority, but:

```text
source-health priority
MUST NEVER exceed the absolute byte cap
```

If SQLite cannot reclaim reusable page capacity or cannot safely preserve
headroom:

```text
no further durable enqueue

no unbounded growth

degraded / spool_capacity
```

No raw packet is ever used as fallback durable storage.

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

# 84. Sensor Runtime State

Local runtime states:

```text
disabled

initializing

ready

degraded

unavailable

stopping
```

`ready`:

```text
raw capture alive

spool healthy

delivery loop alive

Suricata path available
or explicitly unsupported only where accepted
```

`degraded`:

```text
one evidence family unavailable
but other families continue
```

`unavailable`:

```text
capture interface unavailable

spool corrupt/unavailable

identity/security config invalid
```

None changes Authorization state.

---

# 85. Sensor CLI Startup — FIX-1A/FIX-1B/FIX-1K


Exact disabled lifecycle:

```text
1. parse CLI

2. read sensor-owned environment

3. build enough sensor config
   to determine ENABLED

4. if disabled:
   exit 0
```

Disabled mode performs NO:

```text
artifact identity capture

TCP readiness polling

spool open

AF_PACKET

EVE socket

HTTP delivery

Suricata workload
```

Enabled lifecycle:

```text
1. strict sensor-only config validation

2. capture_loaded_artifact_identity(
       "fingerprint-sensor.service"
   )

3. if artifact identity fails:
   exit non-zero
   NO capture

4. poll TCP 127.0.0.1:8088
   using frozen readiness guard

5. interface safety preflight

6. initialize bounded spool

7. create/bind EVE Unix datagram socket

8. mark EVE socket ready

9. attach kernel BPF
   before AF_PACKET receive loop

10. start raw capture/parser

11. start producer/delivery worker

12. initialize source-health state

13. runtime ready/degraded
```

Suricata service is independent and starts only after its socket preflight passes.

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

# 93. Resource Isolation — Accepted Initial Ceilings


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

TechLead10 accepts these as initial ceilings.

Coder may NOT raise them.

If Gate F cannot pass within these ceilings:

```text
FAIL
→ Architect + TechLead10 review
```

Do not silently trade Authorization safety for packet completeness.

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

# 101. Spool Recovery / Hard Footprint Gate — FIX-1J


Controlled test:

```text
Task-01 evidence service unavailable
for 10 minutes
```

Sensor must continue capture, store only normalized events, and not block Authorization.

During outage continuously verify:

```text
size(spool.sqlite3)
+
size(spool.sqlite3-journal if present)
<=
134217728 bytes
```

Also verify:

```text
main DB respects 112 MiB logical ceiling

row count <= 100000

stale purge precedes enqueue

capacity eviction occurs before overflow

source-health prioritization never exceeds byte cap
```

Force a near-capacity scenario.

If headroom cannot be preserved:

```text
new normalized evidence is dropped/evicted per policy

sensor becomes degraded

telemetry emitted

durable footprint remains within cap
```

After Task-01 restore:

```text
delivery resumes automatically

stable event IDs preserved

central idempotency remains safe
```

Target at normal event rate:

```text
queue returns below 10% of row/byte capacity
within 15 minutes
```

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

# 108. TLS Oracle Gate — FIX-1H/FIX-1I


Controlled Suricata 8.0.6 fixture must prove:

```text
TLS-family JA4 starts with "t"

full JA4 components split exactly

client version derives from:
tls.client_handshake.version

server-handshake version not used

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

---

# 109. QUIC Oracle Gate — FIX-1H/FIX-1I


Controlled Suricata 8.0.6 fixture must prove:

```text
QUIC-family JA4 starts with "q"

full JA4 split exactly

actual emitted quic.version representation
belongs to allowed R2 adapter set

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

# 116. Repository Deployment Boundary — FIX-1K RESOLVED


TechLead10 resolves a new task-owned repository subtree:

```text
deploy/device-fingerprint/
```

Freeze repository artifacts:

```text
deploy/device-fingerprint/suricata.yaml

deploy/device-fingerprint/raw-capture.bpf

deploy/device-fingerprint/fingerprint-suricata.service

deploy/device-fingerprint/fingerprint-sensor.service
```

Repository files are templates/artifacts, not live unit files.

Production deployment copies approved units to:

```text
/etc/systemd/system/
```

Production Suricata config deploy target:

```text
/etc/captive-portal/device-fingerprint/suricata.yaml
```

Raw capture BPF deploy target:

```text
/etc/captive-portal/device-fingerprint/raw-capture.bpf
```

Ownership:

```text
root:root

0644
```

unless secret-bearing content is ever added; no secret is permitted in these
files.

Sensor enabled startup MUST use:

```python
capture_loaded_artifact_identity(
    "fingerprint-sensor.service"
)
```

Artifact identity failure:

```text
fail closed

no capture

no spool

no EVE socket
```

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

# 123. Gate D — Linux Sensor Functional + Suricata Fixture Gate


Required:

```text
YES
```

Must prove:

```text
sensor-only config isolation
(no app.settings/app.config import)

disabled CLI exit 0
before artifact/spool/capture

artifact identity fail-closed

TCP core readiness guard

AF_PACKET least privilege

kernel BPF attached before Python receive

raw packet count reflects BPF-admitted packets

interface exactness/no L3 mutation

live raw dedup calibration evidence

DHCP mixed-VLAN authority rules

TCP SYN IPv4 parser

Suricata 8.0.6 exact version

suricata -T

TLS JA4 family/client-version mapping

QUIC JA4/version fixture mapping

NO default semantic JA4 suppressor

Unix datagram socket lifecycle

262144-byte EVE datagram bound

MSG_TRUNC rejection

Suricata restart/reconnect

sensor restart → replacement socket → Suricata recovery

spool hard durable bound

retry

HTTPS/Bearer/TLS trust

source health
```

No production activation required.

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

# 128. Production Activation Order — FIX-1N


Merge/deploy does NOT activate Task-02.

Required high-level activation sequence:

```text
1.
deploy accepted code
with sensor disabled

2.
install exact Suricata 8.0.6
and pin/prevent unattended version drift

3.
create:
fingerprint-sensor user/group
fingerprint-eve group
runtime/spool directories
exact permissions

4.
deploy accepted:
Suricata config
raw BPF
systemd units

5.
deploy:
sensor CA trust
producer Bearer credential

6.
verify Task-01:
fingerprint-evidence.service
TLS/auth health

7.
verify enp8s0:
exact interface
NO IPv4
NO IPv6/link-local
NO routes
NO bridge/master
forwarding=0

8.
verify core:
TCP connect
127.0.0.1:8088

9.
start fingerprint-sensor.service FIRST

prove:
core guard PASS
spool healthy
raw capture ready
EVE socket exists/bound/permissions correct

10.
start fingerprint-suricata.service

prove:
socket preflight
8.0.6
stats heartbeat
TLS/QUIC EVE

11.
prove:
DHCP
TCP SYN
TLS JA4
QUIC JA4
source-health
normalized Task-01 ingest

12.
execute required resource/failure-isolation acceptance

13.
only after Owner acceptance:
separately authorize persistent enable-at-boot
```

Rollback of Task-02 stops/disables:

```text
fingerprint-suricata.service

fingerprint-sensor.service
```

and may remove Task-02 live config/secrets only under explicit rollback plan.

Normal Task-02 rollback MUST NOT touch:

```text
captive-portal.service

enp1s0

enp8s0 infrastructure configuration

Catalyst RSPAN

Task-01 canonical evidence DB
```

unless separately Owner-authorized.

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

# 133. TechLead10 Review — Raw Dedup Calibration Delta


R2 no longer freezes `2 ms`.

Please confirm calibration contract:

```text
BLAKE2s-128

capture_source_id + length + exact bytes

bounded 65,536 cache

120-second / 250,000 admitted-packet calibration

no raw retention

FINAL horizon chosen from measured separation
```

Before FINAL the bounded calibration result is required.

If no safe horizon exists:

```text
return FIX
```

---

# 134. TechLead10 Review — DHCP Mixed-VLAN Authority Delta


Please PASS/FIX:

```text
requested_ip alone =
NOT authority

direct source/ciaddr guest =
authority

zero-address DORA =
buffer until OFFER/ACK

required server source =
192.168.10.1

required option 54 =
192.168.10.1

yiaddr guest =
required

DECLINE/RELEASE =
actual guest address
or confirmed guest lease cache
```

No unproven VLAN10 DHCP event may enter Task-01.

---

# 135. TechLead10 Review — Complete Envelope / Suricata Privacy Delta


Please PASS/FIX:

```text
all four source kinds
have complete Task-01 envelope mapping

DHCP/TCP observed_at =
kernel receive timestamp

TLS/QUIC observed_at =
Suricata EVE timestamp

TCP V1 =
IPv4 only

TLS JA4 family =
t...

QUIC JA4 family =
q...

TLS version =
client_handshake.version

Suricata JA4 =
enabled

Suricata JA3 =
disabled

TLS custom EVE allowlist =
ja4, client_alpns, client_handshake

Ethernet metadata =
enabled
```

---

# 136. TechLead10 Review — Spool Physical Bound Delta


Please PASS/FIX:

```text
SQLite journal_mode =
DELETE

main DB logical ceiling =
112 MiB

absolute durable footprint =
128 MiB

reserved transaction headroom =
16 MiB

spool_bytes =
main + rollback journal

bounded <=100-row transactions

stale purge
→ capacity check
→ eviction
→ recheck
→ insert

cannot preserve headroom
→ drop normalized evidence
→ degraded
→ telemetry

clock =
local UTC wall clock
```

---

# 137. TechLead10 Review — Resource / Metric Delta


Resource ceilings are preserved:

```text
sensor:
CPUQuota=50%
MemoryMax=256M

Suricata:
CPUQuota=150%
MemoryHigh=768M
MemoryMax=1024M
```

Gate F metric contracts now frozen:

```text
Suricata drops:
Δcapture.kernel_drops
/
(Δcapture.kernel_packets + Δcapture.kernel_drops)

Authorization duration:
auth.session_finished.duration_ms

eligible:
final_state=AUTHORIZED

baseline:
60 min sensor OFF
>=30 samples

sensor-on:
60 min sensor ON
>=30 samples

extend to max 4h if insufficient

p95:
nearest rank

threshold:
relative <=20%
AND
absolute <=100ms
```

Please PASS/FIX.

---

# 138. TechLead10 Review — Core Readiness / EVE Lifecycle Delta


Please PASS/FIX:

```text
NO /capport/api readiness request

TCP:
127.0.0.1:8088

connect timeout:
1s

poll:
10s

max continuous wait:
1800s

timeout:
sensor exits non-zero

RestartSec:
30s

NO raw/spool/EVE workload before guard PASS
```

EVE:

```text
socket owner:
fingerprint-sensor:fingerprint-eve

0660

max datagram:
262144

MSG_TRUNC:
discard/degrade

Suricata:
After + BindsTo + PartOf sensor

socket guard:
1830s

sensor restart:
Suricata reconnect/restart required
```

---

# 139. TechLead10 Review — Repository / Config Isolation Delta


Resolved repository deployment subtree:

```text
deploy/device-fingerprint/
```

Live targets:

```text
/etc/systemd/system/

/etc/captive-portal/device-fingerprint/suricata.yaml

/etc/captive-portal/device-fingerprint/raw-capture.bpf
```

Please confirm sensor config isolation:

```text
ALL sensor parsing:
app/device_fingerprint_sensor/config.py

NO sensor config in:
app/config.py
app/settings.py
app/__init__.py
run.py
```

and enabled sensor uses:

```text
capture_loaded_artifact_identity(
"fingerprint-sensor.service"
)
```

---

# 140. Remaining Items Before FINAL — R2


Broad architecture review is substantially closed.

Remaining evidence/decision items before FINAL:

```text
1.
RUN bounded raw duplicate-horizon calibration
on real RSPAN→enp8s0 path.

2.
Freeze measured RAW_DEDUP_HORIZON_MS.

3.
RUN Suricata 8.0.6 TLS/QUIC fixture
and confirm:
- actual semantic EVE multiplicity
- actual quic.version representation subset
- required TLS client_handshake fields

4.
TechLead10 PASS/FIX
on R2 deltas:
config isolation
DHCP authority
EVE lifecycle
spool physical bound
metrics
activation order.

5.
Freeze exact package pin/deployment commands
for production activation procedure.

6.
Freeze final changed-file boundary
after delta review.
```

These are bounded implementation-contract closure items.

No new broad fingerprint research is required.

---

# 141. Control Status — DRAFT-R2


```text
TASK =
TASK-DEVICE-FINGERPRINT-02-DRAFT-R2

TITLE =
Core Packet Sensor + Network Evidence

REPOSITORY BASELINE =
main@414de85c311e72405dc25446461dcd458b5ae597

TASK-01 FOUNDATION =
CURRENT / CONSUMED

SAME-VM SENSOR PLACEMENT =
PASS

CAPTURE INTERFACE =
enp8s0

FIX-1A…FIX-1N =
INCORPORATED

RAW DEDUP HORIZON =
PENDING BOUNDED CALIBRATION

SURICATA FIXTURE DELTA =
PENDING BOUNDED GATE D EVIDENCE

IMPLEMENTATION-READY =
NO

CURRENT GATE =
TECHLEAD10 R2 DELTA / SOURCE REVIEW

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

CLASSIFIER =
NOT AUTHORIZED

DEVICE CARD =
NOT AUTHORIZED

TASK-03 =
NOT INCLUDED
```

---

# 142. Next Workflow — R2


```text
TASK-DEVICE-FINGERPRINT-02-DRAFT-R2
        ↓
TechLead10 delta/source review
        ↓
PASS or narrow FIX
        ↓
bounded raw dedup calibration
+
bounded Suricata 8.0.6 fixture proof
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
exact Gate A
        ↓
Tech Lead static Gate B
        ↓
Central Lab Gate C
        ↓
Linux/Suricata Gate D
        ↓
failure-isolation Gate E
        ↓
resource/soak Gate F
        ↓
privacy Gate G
        ↓
exact-candidate acceptance
        ↓
separate publication authorization
        ↓
separate merge
        ↓
separate deploy
        ↓
separate production activation
```

Until explicit Owner implementation authorization:

```text
CODER = HOLD

NO IMPLEMENTATION

NO BRANCH

NO COMMIT

NO PUSH

NO PR

NO DEPLOY

NO ACTIVATION
```

**End of TASK-DEVICE-FINGERPRINT-02-DRAFT-R2.**

---

