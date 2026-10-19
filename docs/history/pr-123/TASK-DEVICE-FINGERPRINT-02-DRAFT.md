# TASK-DEVICE-FINGERPRINT-02-DRAFT

## Core Packet Sensor + Network Evidence

**Project:** CaptivPortal  
**Program:** Device Fingerprint  
**Parent foundation:** `TASK-DEVICE-FINGERPRINT-01`  
**Research predecessor:** `DEVICE-FINGERPRINT-00 FINAL R2`  
**Revision:** `DRAFT`  
**Prepared:** 2026-09-14  
**Status:** `FOR TECHLEAD10 SOURCE / ARCHITECTURE REVIEW`  
**Implementation-ready:** `NO`  
**Coder:** `HOLD`  
**Implementation authorization:** `NOT GRANTED`  
**Production activation:** `NOT AUTHORIZED`

---

# 0. Control Gate

```text
DEVICE-FINGERPRINT-00 =
CLOSED / PASS

TASK-DEVICE-FINGERPRINT-01 =
IMPLEMENTED / MERGED TO MAIN

TASK-DEVICE-FINGERPRINT-02 =
THIS DRAFT

ARCHITECTURE DIRECTION =
SAME-VM PASSIVE SENSOR

OLD PHYSICAL-SENSOR REQUIREMENT =
SUPERSEDED FOR TASK-02

CODER =
HOLD

IMPLEMENTATION =
NOT AUTHORIZED

PRODUCTION ACTIVATION =
NOT AUTHORIZED
```

This is a NEW separate task.

It does NOT reopen Task-01.

It consumes the existing Task-01 evidence service, envelope, security,
retention, idempotency and source-health contracts.

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

# 18. Service Startup Isolation

Task-02 MUST NOT worsen the known CaptivPortal cold-start problem.

One-way startup guard:

```text
CaptivPortal core may start without sensor.

Sensor may wait for CaptivPortal core.

CaptivPortal MUST NEVER wait for sensor.
```

`fingerprint-sensor.service` uses a bounded preflight against:

```text
http://127.0.0.1:8088/capport/api
```

Expected:

```text
HTTP 200
```

Purpose:

```text
avoid launching packet-processing workload
during the current core cold-start window
```

This is a temporary one-way safety guard.

It does NOT solve `TASK-STARTUP-AVAILABILITY-01`.

If the core readiness preflight is not satisfied:

```text
sensor exits/retries

core Portal remains unaffected
```

---

# 19. systemd Dependency Direction

Required direction:

```text
fingerprint-sensor.service
After=captive-portal.service

fingerprint-sensor.service
Wants=fingerprint-evidence.service

fingerprint-sensor.service
After=fingerprint-evidence.service
```

NOT:

```text
captive-portal.service Requires fingerprint-sensor.service

captive-portal.service After fingerprint-sensor.service

fingerprint-evidence.service Requires fingerprint-sensor.service
```

Suricata:

```text
fingerprint-suricata.service
After=fingerprint-sensor.service
```

No Task-02 service is a prerequisite for Authorization.

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

# 23. Suricata Capture Filter

Suricata BPF scope:

```text
(net 192.168.8.0/22)
OR
(udp and (port 67 or port 68))
```

Purpose:

```text
TLS/QUIC scope only guest network

retain DHCP needed before client has guest IP
```

DHCP events still require independent Site-scope proof before emission.

BPF is performance filtering, NOT Site authority.

---

# 24. Suricata EVE Transport

V1 uses:

```text
EVE filetype =
unix_dgram
```

Runtime socket:

```text
/run/captive-portal/fingerprint-sensor/suricata-eve.sock
```

Properties:

```text
tmpfs /run

not durable

no eve.json regular file

no logrotate persistence

no full EVE spool
```

`fingerprint-sensor.service` owns the receive socket.

Suricata sends transient EVE datagrams.

Failure of EVE delivery:

```text
does not block Authorization

does not create raw disk storage

TLS/QUIC source-health becomes unavailable/degraded
```

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

TLS logging MUST avoid raw SNI.

Preferred Suricata TLS custom fields are limited to those required by Task-02:

```text
version

ja4

client_alpns

client_handshake
```

Transient `client_handshake` is consumed only to derive approved normalized
capabilities such as extension-presence booleans.

Never spool/store:

```text
SNI

certificate

certificate chain

subject

issuer

serial

JA3 string/hash
```

JA3 is not a Task-02 primary feature.

---

# 27. QUIC EVE Privacy Projection

Suricata QUIC EVE may contain fields beyond Task-02 durable schema.

Adapter may transiently inspect:

```text
ja4

version

extensions[].type

flow identity

source L2/L3 identity
```

Adapter MUST discard before spool:

```text
sni

ua

JA3

JA3S

CYU

extension values

destination identity
```

Only normalized approved payload enters spool.

---

# 28. L2 Identity from Suricata EVE

EVE configuration enables transient Ethernet metadata.

For Task-02 client TLS/QUIC evidence:

```text
observed_mac =
original Ethernet source MAC

observed_ip =
original guest source IP
```

Evidence emission requires:

```text
source IP ∈ 192.168.8.0/22

AND

original source MAC available
```

If EVE lacks original MAC:

```text
NO device evidence row

telemetry =
missing_l2_identity

source path may be degraded
```

No IP-only identity fallback.

---

# 29. Raw Packet Capture Path

`fingerprint-sensor.service` opens a passive:

```text
AF_PACKET
SOCK_RAW
```

socket on:

```text
enp8s0
```

Purpose:

```text
raw packet counts

SPAN duplicate suppression

DHCP exact parser

TCP SYN exact parser
```

Raw packet bytes:

```text
memory only

never written to spool

never written to disk

never logged
```

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

# 32. Runtime Filesystem Boundary

Sensor runtime dir:

```text
/run/captive-portal/fingerprint-sensor
```

Owner:

```text
fingerprint-sensor:fingerprint-sensor
```

Mode:

```text
0750
```

EVE socket:

```text
/run/captive-portal/fingerprint-sensor/suricata-eve.sock
```

Suricata receives supplementary group access only for this runtime socket.

No EVE file is written to:

```text
/var/log

/opt/CaptivePortal

/var/lib
```

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

# 34. TLS Trust for Same-VM Producer

Producer does NOT use:

```text
verify=False
```

Task-02 trust anchor copy:

```text
/etc/captive-portal/device-fingerprint/sensor-ca.crt
```

This contains the public certificate/CA material required to validate:

```text
https://192.168.0.202:9443
```

Ownership:

```text
root:fingerprint-sensor
```

Mode:

```text
0644 or 0640
```

Server identity validation requires:

```text
SAN IP =
192.168.0.202
```

No access to Task-01 private key is required.

---

# 35. Packet Dedup — Mandatory

Transport idempotency from Task-01:

```text
!=
packet/SPAN dedup
```

Task-02 owns packet dedup.

Two layers are frozen:

```text
A.
raw exact-frame dedup
for raw parser input + packet telemetry

B.
Suricata semantic-event dedup
for TLS/QUIC normalized evidence
```

---

# 36. Raw Exact-Frame Dedup Algorithm

For every received Ethernet frame:

```text
raw_packet_count += 1
```

Compute transient key:

```text
BLAKE2s-128(
    captured_length
    ||
    exact captured frame bytes
)
```

Raw frame bytes are discarded after parse/dedup.

Dedup timestamp source:

```text
kernel receive timestamp
SCM_TIMESTAMPNS / equivalent nanosecond timestamp
```

Dedup horizon:

```text
2 milliseconds
```

Bounded cache:

```text
maximum entries =
65,536
```

Rule:

```text
same exact-frame hash
seen within 2 ms
→ SPAN duplicate

duplicate_packet_count += 1

do not pass to DHCP/TCP semantic parser
```

Otherwise:

```text
deduplicated_packet_count += 1

pass to parser
```

Cache is in memory only.

---

# 37. Raw Dedup Safety

Dedup MUST NOT collapse based on:

```text
5-tuple alone

TCP sequence alone

MAC alone

DHCP transaction ID alone

JA4 alone
```

Acceptance must prove:

```text
exact mirror copies within horizon
→ collapsed

distinct DHCP messages
→ preserved

distinct TLS/QUIC handshakes
→ preserved

TCP retransmission outside 2 ms
→ preserved

same semantic payload on a new flow
→ preserved
```

If lab evidence shows legitimate traffic can be collapsed at 2 ms:

```text
FAIL
→ return to Architect/Tech Lead
```

Coder may not silently tune the horizon.

---

# 38. Suricata Semantic Dedup

Suricata capture is independent from the raw parser AF_PACKET socket.

Task-02 does NOT attempt to feed a user-space deduplicated packet stream into Suricata.

Instead TLS/QUIC adapter uses a bounded semantic duplicate cache.

Key includes transient:

```text
source_kind

Suricata flow_id

tx_id when present

guest source IP

original source MAC

JA4
```

TTL:

```text
30 seconds
```

Maximum entries:

```text
65,536
```

Same key within TTL:

```text
semantic_duplicate_event_count += 1

NO second normalized evidence event
```

New Suricata flow identity:

```text
new event
```

This prevents retransmitted QUIC Initial / repeated EVE copies from creating
duplicate normalized rows while preserving separate connections.

---

# 39. Dedup Telemetry

Required sensor telemetry:

```text
raw_packet_count

duplicate_packet_count

deduplicated_packet_count

dedup_ratio

semantic_duplicate_event_count

dhcp_candidate_count

dhcp_scoped_count

tcp_syn_event_count

tls_eve_count

tls_normalized_count

quic_eve_count

quic_normalized_count
```

Invariant:

```text
raw_packet_count
=
duplicate_packet_count
+
deduplicated_packet_count
```

for frames processed by the raw capture loop.

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

# 42. DHCP Transaction Scope Resolver

Use transient DHCP transaction cache keyed by:

```text
client MAC
+
DHCP transaction ID
```

TTL:

```text
60 seconds
```

Cache stores only parsed normalized candidate fields.

No raw packet bytes.

Guest scope becomes PROVEN when the same transaction/client yields any accepted:

```text
requested IP ∈ 192.168.8.0/22

ciaddr ∈ 192.168.8.0/22

server OFFER/ACK yiaddr ∈ 192.168.8.0/22
```

Only after proof:

```text
buffered client DHCP candidate events
may become normalized evidence
```

Unproven candidates after 60 seconds:

```text
discard

NO evidence
```

This prevents VLAN10 DHCP leakage into Zefer_Parki evidence.

---

# 43. DHCP Evidence Direction

Task-02 emits normalized device evidence only for client-originated DHCP:

```text
DISCOVER

REQUEST

INFORM

DECLINE

RELEASE
```

Server OFFER/ACK/NAK may be inspected transiently only for scope proof.

They are not emitted as device fingerprint evidence.

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

# 47. DHCP Envelope Mapping

```text
source_kind =
dhcp

source_subtype =
message_type

observed_mac =
DHCP client MAC

observed_ip =
guest requested/ciaddr IP when proven
otherwise null

quality_state =
valid
or partial
```

`valid` requires:

```text
guest scope proven

message parsed without truncation

option sequence structurally valid
```

`partial` is allowed when optional DHCP fields are absent but core message
and scope remain valid.

Malformed/truncated frame:

```text
NO evidence
telemetry only
```

---

# 48. TCP SYN Schema Registration

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

Only outbound client:

```text
SYN=1
ACK=0

source IP ∈ guest CIDR
```

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

# 50. TCP SYN Field Contract

```text
ip_version =
4 | 6
```

```text
observed_ttl =
integer 0..255
```

```text
tcp_window =
integer 0..65535
```

```text
mss =
null
or integer 0..65535
```

```text
window_scale =
null
or integer 0..14
```

```text
sack_permitted =
boolean
```

```text
timestamps_present =
boolean
```

```text
tcp_option_order =
array[int]
0..255
maximum 32
order preserved
```

Task-02 does not run p0f as authoritative classification.

---

# 51. TCP SYN Envelope

```text
source_kind =
tcp_syn

source_subtype =
ipv4 | ipv6

observed_mac =
original Ethernet source MAC

observed_ip =
guest source IP

quality_state =
valid
```

If packet is truncated or option structure invalid:

```text
NO evidence

parser malformed counter incremented
```

TCP SYN remains supporting evidence only.

---

# 52. TLS JA4 Schema Registration

Production registry key:

```text
(
    source_kind = "tls_client",
    feature_schema_version = 1
)
```

Extractor:

```text
extractor_name =
suricata-tls-ja4

extractor_version =
8.0.6
```

Only client-originated EVE events with:

```text
source IP ∈ guest CIDR

original source MAC present

tls.ja4 present
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

# 54. JA4 Canonical Contract

`ja4` must be a bounded printable ASCII string:

```text
4..128 chars
```

with exactly three underscore-separated components:

```text
ja4_a
_
ja4_b
_
ja4_c
```

`ja4_b` and `ja4_c`:

```text
12 lowercase hex each
```

Stored component fields MUST exactly equal the split full JA4.

No case conversion of the full JA4 except validation of expected lowercase hash
components.

---

# 55. TLS Version / ALPN Contract

```text
tls_version_family =
tls1_2
|
tls1_3
|
other
```

`client_alpns`:

```text
ordered array
0..8 elements

each:
printable ASCII
1..32 chars
```

Order preserved.

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

# 57. TLS Quality

```text
quality_state =
valid
```

when:

```text
JA4 valid

MAC present

guest source IP valid

required common fields valid
```

If JA4 exists but extension metadata is absent:

```text
quality_state =
partial

ech_extension_present =
null

grease_extension_present =
null
```

No event without JA4.

---

# 58. QUIC JA4 Schema Registration

Production registry key:

```text
(
    source_kind = "quic_client",
    feature_schema_version = 1
)
```

Extractor:

```text
extractor_name =
suricata-quic-ja4

extractor_version =
8.0.6
```

Only:

```text
guest source IP

original source MAC

quic.ja4 present
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

# 60. QUIC Version Contract

Normalize QUIC version to:

```text
0x
+
8 lowercase hex digits
```

Examples:

```text
0x00000001
```

If Suricata provides an integer:

```text
normalize to unsigned 32-bit hex
```

Invalid/unrepresentable version:

```text
NO evidence
```

---

# 61. QUIC Extension Presence

From transient:

```text
quic.extensions[].type
```

derive:

```text
ech_extension_present =
bool | null

grease_extension_present =
bool | null
```

Do NOT inspect/store:

```text
extension values
```

If extension type list absent:

```text
null

quality_state =
partial
```

JA4 remains core.

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

# 63. Production Schema Registry Modification

Task-02 modifies:

```text
app/device_fingerprint/schema_registry.py
```

Production builder changes conceptually from:

```text
empty registry
```

to:

```text
registry = EvidenceSchemaRegistry()

register dhcp v1

register tcp_syn v1

register tls_client v1

register quic_client v1

freeze

return
```

Validators are pure central validators.

They MUST NOT import:

```text
AF_PACKET

Suricata

sensor spool

requests

systemd

capture runtime
```

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

New package:

```text
app/device_fingerprint_sensor/
```

Proposed exact files:

```text
__init__.py

config.py

models.py

capture.py

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

No capture code is added to:

```text
app/device_fingerprint/
```

except pure central payload validators/registration.

---

# 66. Sensor Configuration

New settings prefix:

```text
DEVICE_FINGERPRINT_SENSOR_
```

Minimum exact config concepts:

```text
ENABLED

INTERFACE

PRODUCER_ID

CAPTURE_SOURCE_ID

SITE_ID

GUEST_CIDRS

EVIDENCE_BASE_URL

CA_CERT_PATH

SPOOL_PATH

SPOOL_MAX_BYTES

SPOOL_MAX_EVENTS

DELIVERY_BATCH_SIZE

HTTP_TIMEOUT_SECONDS

DEDUP_HORIZON_MS

DEDUP_MAX_ENTRIES

SEMANTIC_DEDUP_TTL_SECONDS

CORE_READY_URL

CORE_READY_TIMEOUT_SECONDS
```

No hidden reuse of unrelated Observation/Analytics settings.

---

# 67. Sensor Config Defaults — DRAFT FROZEN

```text
DEVICE_FINGERPRINT_SENSOR_ENABLED =
false

DEVICE_FINGERPRINT_SENSOR_INTERFACE =
enp8s0

DEVICE_FINGERPRINT_SENSOR_PRODUCER_ID =
sensor-zefer-01

DEVICE_FINGERPRINT_SENSOR_CAPTURE_SOURCE_ID =
zefer-span-01

DEVICE_FINGERPRINT_SENSOR_SITE_ID =
6a64f17630da7c70d232187a

DEVICE_FINGERPRINT_SENSOR_GUEST_CIDRS =
192.168.8.0/22

DEVICE_FINGERPRINT_SENSOR_EVIDENCE_BASE_URL =
https://192.168.0.202:9443/api/internal/device-fingerprint/v1

DEVICE_FINGERPRINT_SENSOR_CA_CERT_PATH =
/etc/captive-portal/device-fingerprint/sensor-ca.crt

DEVICE_FINGERPRINT_SENSOR_SPOOL_PATH =
/var/lib/captive-portal/fingerprint-sensor/spool.sqlite3

DEVICE_FINGERPRINT_SENSOR_SPOOL_MAX_BYTES =
134217728

DEVICE_FINGERPRINT_SENSOR_SPOOL_MAX_EVENTS =
100000

DEVICE_FINGERPRINT_SENSOR_DELIVERY_BATCH_SIZE =
100

DEVICE_FINGERPRINT_SENSOR_HTTP_TIMEOUT_SECONDS =
5

DEVICE_FINGERPRINT_SENSOR_DEDUP_HORIZON_MS =
2

DEVICE_FINGERPRINT_SENSOR_DEDUP_MAX_ENTRIES =
65536

DEVICE_FINGERPRINT_SENSOR_SEMANTIC_DEDUP_TTL_SECONDS =
30

DEVICE_FINGERPRINT_SENSOR_CORE_READY_URL =
http://127.0.0.1:8088/capport/api

DEVICE_FINGERPRINT_SENSOR_CORE_READY_TIMEOUT_SECONDS =
300
```

Enabled production validation requires exact frozen identity/interface values.

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

# 69. Spool Format

Use local SQLite:

```text
/var/lib/captive-portal/fingerprint-sensor/spool.sqlite3
```

Purpose:

```text
atomic enqueue

restart recovery

stable retry identity

bounded queue
```

Only normalized Task-01 request events enter.

No raw packet or raw EVE.

Spool schema is Task-02 private transport implementation.

---

# 70. Spool Record Minimum

Each queued record stores:

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

`canonical_json` contains only the Task-01 normalized event object.

No Bearer token.

No destination browsing identity.

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

# 72. Spool Bounds

Hard bounds:

```text
max main spool bytes =
128 MiB

max queued rows =
100,000
```

Before enqueue:

```text
purge stale
```

If still full:

```text
evict oldest normalized DEVICE EVIDENCE first

preserve newer evidence

preserve bounded source-health where possible

emit spool_eviction telemetry
```

Never grow beyond bound.

Never block Authorization.

---

# 73. Spool Stale Expiry

Before delivery:

```text
if central_now - observed_at
>
Task-01 max delayed age (86400s)

→ do not send

→ delete from spool

→ telemetry:
stale_spool_event_dropped
```

No attempt to rewrite observed_at.

No timestamp forgery to extend retention.

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

# 75. Delivery Retry Policy

Initial retry delay:

```text
1 second
```

Exponential backoff:

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

No tight retry loop.

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

# 85. Sensor Startup

When disabled:

```text
CLI exits 0

no raw socket

no spool open

no HTTP

no Suricata dependency activation
```

When enabled:

```text
1. config validation

2. artifact identity capture

3. one-way core-ready preflight

4. interface safety preflight

5. spool initialize

6. bind transient EVE socket

7. raw AF_PACKET capture

8. delivery worker

9. source-health initialization

10. ready/degraded
```

No `run.py` modification.

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

# 87. Suricata Service Startup

Before running live:

```text
suricata -T
```

must validate config.

Runtime start requires:

```text
enp8s0 exists

sensor EVE receiver socket ready

Suricata version == 8.0.6
```

If not:

```text
fingerprint-suricata.service fails/retries

fingerprint-sensor.service continues raw DHCP/TCP
and marks TLS/QUIC unavailable
```

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

# 90. No Full EVE Persistence

Forbidden:

```text
/var/log/suricata/eve.json
```

for Task-02 evidence pipeline.

No generic EVE archive.

No Loki shipping of raw EVE.

Only sanitized Task-02 operational telemetry may go to existing logging stack.

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

# 93. Resource Isolation — systemd

Initial safety budgets:

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

These protect the production VM.

If acceptance cannot meet packet-processing requirements inside these bounds:

```text
FAIL
→ Tech Lead / Architect review
```

Coder does not silently raise limits.

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

# 95. Resource Telemetry

Minimum periodic telemetry:

```text
sensor_cpu_time

sensor_rss_bytes

suricata_pid_alive

suricata_version

suricata_capture_packets

suricata_kernel_drops

suricata_decoder_drops where available

eve_received

eve_socket_drops where available

raw_packet_count

duplicate_packet_count

deduplicated_packet_count

spool_rows

spool_bytes

oldest_spool_age_seconds

delivery_success

delivery_retry

delivery_permanent_reject

events_per_source_kind
```

No destination identifiers.

---

# 96. Performance Gate — Packet Rate

Research baseline showed approximately:

```text
~200 Mbit/s raw mirrored load
with duplication

~100 Mbit/s useful
```

Task-02 acceptance must prove on current same VM:

```text
sensor services remain stable
at current production observed load
```

Packet loss gate:

```text
Suricata capture drop ratio
<= 1.0% sustained
over a 15-minute evaluation window
```

Any sustained higher loss:

```text
FAIL
```

unless Tech Lead approves a documented revised threshold based on measured
hardware constraints.

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

# 99. Performance Gate — Authorization

Compare same-VM baseline:

```text
sensor OFF
```

against:

```text
sensor ON
```

Required:

```text
0 task-attributable Authorization failures

0 new 502 caused by sensor

core Portal remains reachable

CAPPORT remains functional
```

Latency gate:

```text
Authorization p95 increase
<= 20%

AND

absolute p95 increase
<= 100 ms
```

If either bound fails:

```text
FAIL / review
```

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

# 101. Spool Recovery Gate

Controlled test:

```text
Task-01 evidence service unavailable
for 10 minutes
```

Sensor must:

```text
continue capture

store only normalized events

remain under spool bounds

not block Authorization
```

After restore:

```text
delivery resumes automatically

queue drains

stable event IDs preserved

central duplicate handling safe
```

Target:

```text
queue returns below 10% of capacity
within 15 minutes
```

at normal production event rate.

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

# 103. Suricata Restart Recovery Gate

Controlled restart:

```text
fingerprint-suricata.service
```

must prove:

```text
DHCP/TCP raw parser continues

TLS/QUIC source-health → unavailable

no core Portal impact

after Suricata recovery:
TLS/QUIC → available
normalization resumes
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

# 105. Dedup Acceptance PCAP Set

Task-02 test fixtures must include sanitized synthetic/controlled PCAPs for:

```text
exact duplicate Ethernet frames inside 2 ms

same frame after dedup horizon

TCP legitimate retransmission

DHCP Discover/Request sequence

DHCP duplicated mirror copies

TLS ClientHello duplicate mirror copies

two separate TLS connections with same JA4

QUIC Initial retransmissions

two separate QUIC flows with same JA4
```

Fixtures must contain no real browsing destinations/credentials.

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

# 108. TLS Oracle Gate

Against controlled current Suricata 8.0.6 fixture:

```text
JA4 extracted

full JA4 split exactly

version family normalized

ALPN order preserved

ECH extension presence derived if metadata available

GREASE presence derived if metadata available

SNI absent from normalized event/spool
```

JA3 absent from normalized event.

---

# 109. QUIC Oracle Gate

Against controlled current fixture:

```text
QUIC JA4 extracted

components exact

version normalized

extension-presence fields correct or null

SNI absent

UA absent

JA3 absent

CYU absent
```

If current Suricata cannot produce required JA4 on fixture:

```text
Task-02 QUIC gate =
FAIL / FIX
```

Do not fabricate substitute fingerprint.

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

# 116. Proposed Repository File Boundary — NEW

New central schema file:

```text
app/device_fingerprint/network_schemas.py
```

New sensor package:

```text
app/device_fingerprint_sensor/__init__.py
app/device_fingerprint_sensor/config.py
app/device_fingerprint_sensor/models.py
app/device_fingerprint_sensor/capture.py
app/device_fingerprint_sensor/dedup.py
app/device_fingerprint_sensor/scope.py
app/device_fingerprint_sensor/dhcp.py
app/device_fingerprint_sensor/tcp_syn.py
app/device_fingerprint_sensor/eve.py
app/device_fingerprint_sensor/normalizer.py
app/device_fingerprint_sensor/spool.py
app/device_fingerprint_sensor/producer.py
app/device_fingerprint_sensor/health.py
app/device_fingerprint_sensor/telemetry.py
app/device_fingerprint_sensor/runtime.py
app/device_fingerprint_sensor/cli.py
```

Repository-owned deployment config:

```text
deploy/device-fingerprint/suricata.yaml

deploy/device-fingerprint/capture.bpf

deploy/device-fingerprint/fingerprint-suricata.service

deploy/device-fingerprint/fingerprint-sensor.service
```

If repository has no accepted `deploy/` convention at fresh Tech Lead rebind:

```text
Tech Lead must rebind exact deployment-file location
before FINAL
```

Coder does not invent location.

---

# 117. Proposed Existing Files To Modify

```text
app/device_fingerprint/schema_registry.py

app/config.py

app/settings.py

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

Purpose is narrow:

```text
register Task-02 schemas

add sensor config

document same-VM architecture delta

document services / security / privacy / deployment
```

No unrelated rewrite.

---

# 118. Explicit NO-TOUCH Application Areas

```text
run.py

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

Task-02 does not alter those domains.

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

# 120. Gate A — Coder Focused Tests

Coder responsibility only after FINAL + Owner authorization.

Focused groups:

```text
network schema validators

sensor config/scope

packet dedup

DHCP parser

TCP SYN parser

EVE TLS/QUIC adapter

spool

producer/retry

source health

runtime/CLI
```

Plus:

```text
python -m compileall -q \
  app/device_fingerprint \
  app/device_fingerprint_sensor

git diff --check
```

Exact pytest commands to be frozen in FINAL after TechLead file-boundary PASS.

Coder does NOT run official broad regression.

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

# 123. Gate D — Linux Sensor Functional Gate

Required:

```text
YES
```

Dedicated Linux/production-compatible environment.

Must prove:

```text
AF_PACKET capture

CAP_NET_RAW least privilege

interface exactness

no L3 interface mutation

raw dedup

DHCP parser

TCP SYN parser

Suricata 8.0.6 config test

TLS JA4

QUIC JA4

EVE privacy projection

spool/retry

HTTPS/Bearer/TLS validation

source-health

restart recovery
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

# 125. Gate F — Same-VM Resource / Soak

Required:

```text
YES
```

Must include:

```text
2-hour soak

CPU

RAM

packet rate

Suricata drops

EVE rate

normalized evidence rate

spool growth

dedup ratio

Task-01 ingest rate

Authorization regression comparison

Observation/Current State/Visit/Traffic Projection health
```

Infrastructure visibility proof alone is insufficient.

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

# 128. Production Activation Is Separate

Even after merged Task-02 code:

```text
sensor default =
disabled
```

Production activation requires separate Owner-authorized workflow including:

```text
Suricata package install/version proof

service account creation

capability/permissions

sensor cert trust

producer secret deployment

Task-01 evidence service state

systemd units

interface preflight

resource baseline

controlled activation

rollback plan
```

No activation authorization is contained in this DRAFT.

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

# 133. TechLead10 Review — Dedup

Please PASS/FIX:

```text
raw BLAKE2s exact-frame dedup

2 ms horizon

65,536 cache entries

semantic TLS/QUIC dedup

30s TTL

65,536 event entries
```

This is a high-value review item.

---

# 134. TechLead10 Review — DHCP Scope

Please confirm mixed RSPAN source safety:

```text
DHCP client evidence
must remain buffered/uncommitted
until guest scope is proven
by requested/ciaddr/yiaddr
inside 192.168.8.0/22
```

No unproven Discover may become Zefer_Parki evidence.

---

# 135. TechLead10 Review — Exact Schemas

Please PASS/FIX feature schema v1 for:

```text
dhcp

tcp_syn

tls_client

quic_client
```

No classifier fields.

No destination identity.

No raw privacy-sensitive fields.

---

# 136. TechLead10 Review — Spool

Please PASS/FIX:

```text
SQLite private transport queue

128 MiB

100,000 rows

at-least-once

stable UUID

100 event batches

1→30s exponential backoff

24h stale expiry

oldest evidence eviction when full
```

---

# 137. TechLead10 Review — Resource Caps

Please PASS/FIX initial safety budgets:

```text
sensor:
CPUQuota 50%
MemoryMax 256M

Suricata:
CPUQuota 150%
MemoryHigh 768M
MemoryMax 1024M
```

Final values must be frozen before Coder implementation.

---

# 138. TechLead10 Review — Startup Guard

Please PASS/FIX temporary one-way guard:

```text
sensor waits for:
http://127.0.0.1:8088/capport/api = 200

CaptivPortal never waits for sensor
```

This is only to avoid worsening existing cold-start debt.

It does not solve Startup Availability task.

---

# 139. TechLead10 Review — Repository File Boundary

Fresh-source-bind:

```text
deployment file location

systemd unit ownership

docs update surface

schema registry modification point

sensor package location
```

If repository conventions differ, return a narrow FIX.

---

# 140. Open Items Before FINAL

No broad research is required.

The following need TechLead source/architecture decision:

```text
1.
exact repository location
for Suricata/systemd deploy artifacts

2.
PASS/FIX on 2 ms raw dedup horizon

3.
PASS/FIX on semantic dedup key/TTL

4.
PASS/FIX on systemd resource caps

5.
PASS/FIX on one-way core-ready preflight

6.
Suricata unix_dgram exact deployment behavior
on Ubuntu 22.04 package

7.
final focused test command grouping

8.
exact production activation gate order
```

These are implementation contract finalization items, not new fingerprint research.

---

# 141. Control Status

```text
TASK =
TASK-DEVICE-FINGERPRINT-02-DRAFT

TITLE =
Core Packet Sensor + Network Evidence

REPOSITORY BASELINE =
main@414de85c311e72405dc25446461dcd458b5ae597

TASK-01 FOUNDATION =
CURRENT / CONSUMED

SENSOR PLACEMENT =
SAME VM 192.168.0.202

CAPTURE INTERFACE =
enp8s0

CORE SOURCE KINDS =
dhcp
tcp_syn
tls_client
quic_client

IMPLEMENTATION-READY =
NO

CURRENT GATE =
TECHLEAD10 SOURCE / ARCHITECTURE REVIEW

CODER =
HOLD

IMPLEMENTATION =
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

# 142. Next Workflow

```text
TASK-DEVICE-FINGERPRINT-02-DRAFT
        ↓
TechLead10 source / architecture review
        ↓
PASS or FIX-N
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
focused Gate A
        ↓
Tech Lead static review
        ↓
Central Lab / Linux / same-VM soak /
privacy / isolation gates
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

**End of TASK-DEVICE-FINGERPRINT-02-DRAFT.**
