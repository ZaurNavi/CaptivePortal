# TASK-DTI-00 — CAPABILITY & CAPTURE BASELINE
## FINAL SYSADMIN RESEARCH CONTRACT — DTI00-R1 INCORPORATED

**Project:** CaptivPortal  
**Program:** Device Traffic Enrichment / Device Intelligence  
**Program prefix:** DTI  
**Task:** TASK-DTI-00  
**Role:** System / Network Administrator — Infrastructure Research  
**Contract status:** APPROVED FOR SYSADMIN RESEARCH  
**Task type:** RESEARCH / LAB / INVENTORY  
**Implementation:** NO  
**Coder action:** HOLD  
**Production feature activation:** NO  
**Production configuration change:** NO  

---

# 1. PURPOSE

TASK-DTI-00 must prove what the existing physical and host-side mirror/capture path actually provides before any DTI implementation begins.

The task must determine, with reproducible evidence:

- what traffic is physically mirrored;
- from which source/interface/VLAN scope;
- which traffic directions are visible;
- where the capture point is relative to L2, first L3 hop, gateway, NAT and uplink;
- whether client MAC, IPv4, IPv6 and VLAN identity are actually visible;
- whether both sides of representative flows are visible;
- whether the traffic observed by the production parser is the traffic presented on the mirror destination;
- whether capture presentation is affected by NIC/kernel offloads;
- whether mirror topology can duplicate frames;
- whether mirror oversubscription or pre-host loss is possible;
- what local and parser drop evidence exists;
- what current sensor/parser software is running;
- how the accepted Device Fingerprint Suricata path can coexist with future DTI;
- whether a lightweight traffic meter is needed;
- whether Zeek is justified by a concrete capability gap;
- what role existing NetFlow/nfdump can play;
- what traffic/event rates and host resources actually look like under natural load;
- what the storage-growth baseline looks like;
- what remains UNKNOWN.

The task does **not** implement DTI.

---

# 2. RESEARCH PRINCIPLE — DO NOT ASSUME

Every material conclusion must be classified as one of:

```text
OBSERVED
CONFIGURATION-PROVEN
CONTROLLED-TRACE-PROVEN
MODELED
UNKNOWN
NOT_APPLICABLE
```

Do not turn:

```text
probably
normally
should be
likely
```

into a proven fact.

If a fact cannot be established safely and read-only:

```text
STATUS = UNKNOWN / BLOCKED
```

with the reason recorded.

---

# 3. ACCEPTED ARCHITECTURE BASELINE TO VERIFY

Expected reference topology:

```text
guest client
    ↓
AP
    ↓
Catalyst L2 switching / guest VLAN
    ↓
SPAN / RSPAN mirror copy
    ↓
mirror destination
    ↓
sensor capture path

original packet continues:
    ↓
Cisco gateway
    ↓
first L3 routing
    ↓
NAT / uplink
    ↓
Internet
```

This is a reference to be verified, not permission to assume current reality.

If the actual topology differs:

```text
DO NOT FIX
DO NOT RECONFIGURE
DO NOT MOVE THE MIRROR
```

Record the discrepancy.

---

# 4. HARD SAFETY BOUNDARY

Without separate explicit Owner authorization, TASK-DTI-00 MUST NOT:

- change switch configuration;
- change SPAN/RSPAN configuration;
- change mirror source/destination;
- change VLANs/trunks/native VLANs;
- move cabling;
- change Cisco router configuration;
- change routing/NAT/ACLs;
- change Omada configuration;
- restart CaptivPortal;
- restart accepted production Fingerprint services;
- modify `fingerprint-suricata.service`;
- enable additional production Suricata outputs;
- modify production Suricata configuration;
- install Zeek;
- install a new production parser;
- install packages merely for convenience if not already present;
- change NIC offload settings;
- change promiscuous-mode configuration;
- change bridge/vSwitch/VLAN configuration;
- change IRQ/RPS/RFS tuning;
- change systemd limits;
- change firewall policy;
- run synthetic stress/load tests;
- generate large artificial network traffic;
- create a persistent full PCAP;
- dump arbitrary user payload content.

Preferred mode:

```text
READ-ONLY INSPECTION
+
BOUNDED PASSIVE OBSERVATION
+
ONE CONTROLLED OWNER-APPROVED CLIENT TRACE
```

---

# 5. PERMITTED ACTIONS

Allowed where already supported by existing tools:

- read configuration;
- read switch/router/interface counters;
- inspect interfaces, bridges, vSwitches, VLAN subinterfaces and namespaces;
- inspect process/service state;
- inspect routes and host networking;
- inspect SPAN/RSPAN state;
- inspect NetFlow configuration;
- inspect existing logs/stats;
- inspect Suricata stats/capabilities;
- bounded packet observation;
- bounded resource observation;
- one non-destructive controlled known-client trace.

Prefer:

```text
metadata / headers
limited packet count
limited time window
no persistent payload archive
```

---

# 6. RESEARCH PRIVACY BOUNDARY

Research evidence MUST NOT publish unrelated visitor browsing metadata.

Use primarily:

```text
Owner-controlled / explicitly approved test client
```

For other clients where identity is not technically required:

```text
MAC     → redact/anonymize
IP      → redact/anonymize
DNS/SNI → omit unless technically necessary
```

Packet observation is:

```text
headers / metadata only
```

Forbidden without separate Owner authorization:

```text
payload hexdumps
ASCII payload dumps
full HTTP content
arbitrary visitor DNS/SNI history
persistent full PCAP
```

The report must contain:

```text
RESEARCH_PRIVACY_BOUNDARY = PASS / FAIL
```

---

# 7. EVIDENCE INDEX — MANDATORY

The final report MUST contain a reproducible Evidence Index.

Format:

```text
E01
Host/device:
Timestamp UTC:
Command / observation:
Sanitized output:
Supports conclusion:

E02
...
```

Every major conclusion must cite one or more Evidence IDs.

At minimum, the following outputs must cite evidence IDs:

- CaptureTopologyReference
- CapturePlacementProof
- HostCapturePathProof
- CaptureScopeBinding
- CaptureQuality result
- ControlledClientTraceProof
- ResourceBudgetBaseline
- FingerprintSensorCoexistenceRecommendation
- TrafficAccountingSourceRecommendation

For the accepted production Fingerprint sensor baseline, record read-only where available:

```text
binary/version
systemd unit identity
capture interface
config path
config identity/hash where safe
service uptime/restart state
```

Do not include secrets.

---

# 8. RESEARCH BLOCK A — PHYSICAL / LOGICAL CAPTURE TOPOLOGY

Build the exact topology.

Determine:

```text
AP identity / attachment
switch identity
switch port(s)
guest VLAN(s)
SPAN/RSPAN source
SPAN/RSPAN direction
RSPAN VLAN where applicable
mirror destination
sensor host
sensor physical NIC
gateway
first L3 device
NAT location
uplink
```

Required topology diagram:

```text
Client
  ↓
AP <identity>
  ↓
Switch <identity> / port <...>
  ↓
Guest VLAN <...>
  ↓
Mirror source <...>
  ↓
SPAN/RSPAN
  ↓
Mirror destination <...>
  ↓
Sensor physical ingress <...>
  ↓
Host capture path <...>
  ↓
Capture interface <...>
  ↓
Parser/observer <...>

Original packet:
  ↓
Gateway <...>
  ↓
NAT point <...>
  ↓
WAN/uplink <...>
```

---

# 9. RESEARCH BLOCK B — CAPTURE PLACEMENT PROOF

Prove the observation point relative to:

```text
guest VLAN
L2 switching
first L3 hop
default gateway
NAT
uplink
```

Required verdicts:

```text
CAPTURE_BEFORE_FIRST_L3 =
YES / NO / UNKNOWN

CAPTURE_PRE_NAT =
YES / NO / MIXED / UNKNOWN

CLIENT_L2_IDENTITY_AVAILABLE =
YES / NO / PARTIAL / UNKNOWN
```

Each verdict must reference evidence IDs.

---

# 10. RESEARCH BLOCK C — COMPLETE HOST CAPTURE PATH PROOF

Do not stop at:

```text
switch → mirror destination → physical NIC
```

Prove the complete actual path to the production parser:

```text
switch mirror destination
        ↓
physical NIC
        ↓
host / hypervisor forwarding layer
        ↓
bridge / vSwitch / VLAN handling
        ↓
VM/vNIC or namespace where applicable
        ↓
capture interface
        ↓
AF_PACKET/libpcap/other input
        ↓
Suricata / fingerprint sensor / observer
```

For each possible layer determine:

```text
physical interface
virtual interface
bridge/vSwitch membership
VLAN handling
promiscuous mode
MAC filtering
network namespace
VM/vNIC mapping
capture process binding
capture input method
```

If a layer does not exist:

```text
NOT_APPLICABLE
```

If it cannot be proven:

```text
UNKNOWN
```

Do not change any settings.

Required artifact:

```text
HostCapturePathProof
```

Required verdict:

```text
HOST_CAPTURE_PATH_PROVEN =
YES / PARTIAL / NO / UNKNOWN
```

---

# 11. RESEARCH BLOCK D — SPAN / RSPAN CONTRACT

Record actual mirror configuration:

```text
source interface(s)
source VLAN(s)
source direction: RX / TX / BOTH / other
destination interface
RSPAN VLAN
trunk path
allowed VLANs
native VLAN where relevant
```

Do not infer real direction only from a name or comment.

Prove from configuration and/or bounded observation.

---

# 12. RESEARCH BLOCK E — CLIENT MAC VISIBILITY

Determine whether the parser/capture interface sees the actual client MAC.

Inspect, where naturally present:

```text
client-originated unicast
return unicast
ARP
DHCP
broadcast
multicast
IPv6
```

Required:

```text
SOURCE_MAC_VISIBLE =
YES / NO / CONDITIONAL / UNKNOWN

DESTINATION_MAC_VISIBLE =
YES / NO / CONDITIONAL / UNKNOWN
```

Explain:

- when it is the client MAC;
- when it is AP/switch/router MAC;
- when it cannot be proven.

---

# 13. RESEARCH BLOCK F — VLAN VISIBILITY

Determine:

```text
802.1Q tag visible at capture API?
VLAN ID visible?
RSPAN alters presentation?
bridge/vSwitch/VLAN subinterface alters presentation?
NIC/kernel offload alters presentation?
```

Required:

```text
VLAN_TAG_VISIBLE =
YES / NO / CONDITIONAL / UNKNOWN
```

Important:

```text
VLAN tag absent in tcpdump/libpcap
!=
VLAN tag absent on mirrored wire
```

until hardware/kernel VLAN offload/presentation has been accounted for.

If the tag is not visible to the parser, identify another proved Site-binding mechanism if one exists.

---

# 14. RESEARCH BLOCK G — NIC / KERNEL CAPTURE PRESENTATION EFFECTS

Read-only inspect relevant offloads:

```text
GRO
LRO
GSO
TSO
RX checksum offload
TX checksum offload
RX VLAN offload
TX VLAN offload
other capture-affecting features
```

Do not change them.

Interpretation rules:

```text
host-captured packet length/count
may differ from wire representation
because of aggregation/offload
```

and:

```text
bad checksum shown by local capture
may be an offload artifact,
not a real corrupted packet
```

The report must explain any known presentation effects on:

- VLAN visibility;
- packet counts;
- packet lengths;
- checksum interpretation;
- any evidence used for duplicate detection/accounting.

Required verdict:

```text
CAPTURE_PRESENTATION_EFFECTS =
ACCOUNTED / PARTIAL / UNKNOWN
```

---

# 15. RESEARCH BLOCK H — BOTH SIDES OF FLOW

For an ordinary controlled client flow determine:

```text
client → remote direction visible?
remote → client direction visible?
```

Required:

```text
FLOW_CLIENT_TO_REMOTE =
VISIBLE / PARTIAL / NOT_VISIBLE / UNKNOWN

FLOW_REMOTE_TO_CLIENT =
VISIBLE / PARTIAL / NOT_VISIBLE / UNKNOWN
```

Record asymmetry explicitly.

---

# 16. RESEARCH BLOCK I — PRE-NAT / POST-NAT

Determine:

```text
original client private IP visible?
translated/public address visible?
where NAT occurs relative to capture?
```

Required:

```text
OBSERVATION_POINT =
PRE_NAT / POST_NAT / MIXED / UNKNOWN
```

---

# 17. RESEARCH BLOCK J — CONTROLLED KNOWN-CLIENT TRACE

One controlled end-to-end trace is mandatory.

Use only:

```text
Owner-controlled / explicitly approved test client
```

Do not use a random visitor.

No destructive action is required.

Do NOT force:

```text
disconnect
DHCP renewal
reauthorization
session reset
```

A small natural/controlled sequence is sufficient, where available:

```text
known client MAC/IP
→ gateway traffic
→ DNS activity
→ small Internet HTTPS flow
```

Record exact UTC window.

Correlate:

```text
known test-device MAC
known IP at time T
controller/DHCP state where available
observed L2 frame
observed L3 endpoint
upload direction
return direction
pre/post-NAT state
capture timestamp
```

Goal:

```text
prove one complete correlation path in practice
```

If IPv6 is actually available, perform a separate bounded IPv6 observation.

If IPv6 is absent on the tested path:

```text
IPv6 controlled trace = NOT_OBSERVED / UNKNOWN
```

Required artifact:

```text
ControlledClientTraceProof
```

Required verdict:

```text
CONTROLLED_CLIENT_TRACE =
PASS / PARTIAL / BLOCKED
```

---

# 18. RESEARCH BLOCK K — MIRROR DUPLICATION

Determine whether the same original packet/frame can appear at the sensor more than once because of mirror/capture topology.

Investigate:

```text
SPAN BOTH direction
multiple mirror sources
VLAN + physical interface mirrored together
RSPAN topology
uplink + access source overlap
host/vSwitch fan-out
other duplicate-producing arrangements
```

Permanent research rule:

```text
MIRROR DUPLICATE
!=
TCP RETRANSMISSION
```

`DUPLICATE_RISK` refers only to:

```text
same original packet/frame appearing multiple times
because of mirror topology/capture behavior
```

When testing duplication, use enough packet identity to distinguish:

```text
same mirrored frame
vs
later protocol retransmission
```

Document the evidence basis.

Required:

```text
DUPLICATE_RISK =
NONE_PROVEN / POSSIBLE / CONFIRMED / UNKNOWN
```

---

# 19. RESEARCH BLOCK L — MIRROR CAPACITY / HEADROOM

Do not infer capture completeness from host-local drops alone.

Permanent rule:

```text
zero sensor drops
!=
zero mirror loss
```

Research:

```text
mirror destination link speed
source interface/VLAN link rates
natural source traffic rates
potential aggregate source rate
observed destination rate
oversubscription possibility
```

Where safe, use the same bounded observation window to record:

```text
source-side switch counters BEFORE/AFTER
mirror destination/sensor counters BEFORE/AFTER
sensor captured packets/bytes
```

Perform approximate reconciliation.

Billing-grade equality is not required.

Required verdict:

```text
MIRROR_OVERSUBSCRIPTION_RISK =
LOW_PROVEN / POSSIBLE / CONFIRMED / UNKNOWN
```

And:

```text
CAPTURE_COMPLETENESS_EVIDENCE =
SUFFICIENT / PARTIAL / INSUFFICIENT / UNKNOWN
```

Important:

```text
CAPTURE_QUALITY_BASELINE = PASS
```

means sufficient quality evidence/monitorability exists.

It does **not** mean 100% of all packets were captured.

---

# 20. RESEARCH BLOCK M — CAPTURE SOURCE → SITE BINDING

Prove the mapping:

```text
capture source
+
interface / VLAN / topology scope
        ↓
Site
```

For each source record:

```text
capture_source_id
physical/logical source
interface
VLAN scope
SSID relevance where provable
Site
basis of mapping
ambiguity
```

Do not infer Site solely because only one Site currently exists.

If ambiguous:

```text
SITE_MAPPING = AMBIGUOUS
```

Do not guess.

---

# 21. RESEARCH BLOCK N — CAPTURE QUALITY BASELINE

Collect available quality indicators:

```text
sensor interface state
link state
speed/duplex
RX packets/bytes
RX drops
RX errors
RX missed
kernel capture drops
parser drops
Suricata drops
ingest drops where already observable
capture lag where observable
clock/NTP health
mirror capacity/headroom evidence
host capture path confidence
presentation/offload interpretation
```

Permanent principle:

```text
PROCESS RUNNING
!=
CAPTURE COMPLETE
```

and:

```text
zero observed traffic
!=
zero real traffic
```

without sufficient completeness evidence.

---

# 22. RESEARCH BLOCK O — CAPTURE NIC BASELINE

For the capture NIC record read-only:

```text
interface name
driver
NIC chipset/model
link speed
duplex
MTU
MAC
offload state
RX/TX counters
errors
drops
missed packets
ring statistics where available
```

Do not change NIC settings.

---

# 23. RESEARCH BLOCK P — SENSOR SOFTWARE INVENTORY

Inventory everything already consuming or related to mirror traffic:

```text
custom Fingerprint sensor
Suricata
other packet parser
tcpdump/tshark if installed
flow collector
NetFlow/nfdump-related services where relevant
```

For each:

```text
name
version
service/unit
process
runtime user
config path
config identity/hash where safe
capture interface
input mode
output path
enabled event/output families
service uptime
restart state
CPU usage
RAM usage
disk usage
```

Do not expose secrets.

---

# 24. RESEARCH BLOCK Q — FINGERPRINT SENSOR COEXISTENCE

The accepted Device Fingerprint sensor path is protected.

Do not modify `fingerprint-suricata.service`.

Evaluate:

```text
OPTION A
reuse existing Suricata process
+
additional versioned DTI output
proven not to affect Fingerprint

OPTION B
separate DTI Suricata instance

OPTION C
another proved safe fan-out arrangement
```

For each assess:

```text
functional impact
CPU
RAM
disk/IO
capture drops
capture timing
source-health behavior
operational complexity
isolation
```

Required:

```text
FINGERPRINT_SURICATA_COEXISTENCE_RECOMMENDATION =
A / B / C / UNRESOLVED
```

Recommendation only. No implementation authorization.

---

# 25. RESEARCH BLOCK R — SURICATA CAPABILITY INVENTORY

Without modifying config, distinguish:

```text
SUPPORTED BY INSTALLED VERSION
```

from:

```text
CURRENTLY ENABLED IN PRODUCTION
```

Research capabilities for:

```text
flow
DNS
TLS
QUIC
HTTP metadata
DHCP
ARP where applicable
ICMP
stats
drops
alerts
other useful metadata
```

---

# 26. RESEARCH BLOCK S — LIGHTWEIGHT TRAFFIC METER

Determine whether current components can reliably support:

```text
periodic bytes up/down
current traffic rate
peak rate
long-lived flow accounting
current network activity
Visit boundary slicing
```

If terminal Suricata flow events are insufficient, explain why.

Required:

```text
TRAFFIC_ACCOUNTING_SOURCE_RECOMMENDATION =
SURICATA_ONLY / LIGHTWEIGHT_METER / COMBINED / UNRESOLVED
```

No implementation.

---

# 27. RESEARCH BLOCK T — ZEEK GAP ANALYSIS

Zeek is NOT baseline.

Do not install it.

Evaluate only whether a concrete gap remains after considering:

```text
existing custom sensor
+
Suricata
+
possible lightweight meter
```

Required:

```text
ZEEK_REQUIRED =
NO / POSSIBLY_LATER / JUSTIFIED_GAP / UNRESOLVED
```

If `JUSTIFIED_GAP`, name the exact capability gap.

"Zeek can do more" is not a valid justification.

---

# 28. RESEARCH BLOCK U — NETFLOW / NFDUMP OVERLAP

Inventory:

```text
exporter
export interface/source
collector IP
collector port
NetFlow version
observation point
available fields
```

Determine:

```text
what NetFlow can cross-check
what it cannot prove
whether it is useful as aggregate diagnostic evidence
```

Do not treat NetFlow as the primary MAC/device identity source without proof.

Required:

```text
NETFLOW_ROLE =
CROSS_CHECK / DIAGNOSTIC / NOT_USEFUL / UNKNOWN
```

---

# 29. RESEARCH BLOCK V — TRAFFIC VOLUME BASELINE

Use bounded natural observation windows.

Do not generate synthetic load.

For each sample:

```text
UTC start
UTC end
duration
capture packets/sec
capture bytes/sec
approx Mbps
event rate
flow rate where available
Suricata EVE rate where already enabled
drop counters before/after
```

Where naturally available, collect:

```text
quiet/low window
normal window
higher natural activity window
```

---

# 30. RESEARCH BLOCK W — PROTOCOL MIX SAMPLE

Without enabling new parsers, produce a bounded approximate picture where possible:

```text
IPv4 / IPv6
TCP / UDP / ICMP
ARP
DNS
DHCP
QUIC-like UDP/443
TLS-like TCP/443
mDNS
SSDP
other
```

No deep content inspection is required.

---

# 31. RESEARCH BLOCK X — CLOCK / TIME BASELINE

For relevant systems/sources record:

```text
timezone
UTC time
NTP enabled
NTP synchronized
clock offset if known
```

Especially:

```text
sensor host
hypervisor if applicable
switch/router timestamp source where relevant
Suricata timestamps
NetFlow collector
```

---

# 32. RESEARCH BLOCK Y — RESOURCE BASELINE

No resource conclusion may be based on one instantaneous sample.

Permanent rule:

```text
NO RESOURCE CONCLUSION
FROM ONE top/free/ps SNAPSHOT
```

For each representative natural-traffic window record:

```text
UTC start/end
duration
CPU/load
memory
IO
process CPU/RAM
capture interface counters before/after
Suricata counters before/after
drop counters before/after
```

At minimum:

```text
quiet/idle baseline
normal natural traffic window
```

Multiple bounded samples are allowed.

Do not generate artificial load.

If sensor is inside a VM and hypervisor contention/CPU steal is visible, record it.

If hypervisor-level evidence is unavailable:

```text
UNKNOWN
```

is acceptable.

---

# 33. RESEARCH BLOCK Z — RESOURCE DEGRADATION RECOMMENDATION

Architecture principle:

```text
DTI DEGRADES FIRST.
Portal / accepted Fingerprint path must not be sacrificed.
```

Recommend, but do not apply:

```text
DTI CPU ceiling candidate
DTI RAM ceiling candidate
DTI disk allocation candidate
DTI queue/spool ceiling candidate
disk free-space safety threshold candidate
backpressure behavior
drop behavior
systemd/cgroup isolation if justified
```

---

# 34. STORAGE VOLUME ESTIMATE — MEASURED VS MODELED

Separate clearly:

## MEASURED

Actual existing:

```text
packet rate
byte rate
EVE/event rate
existing log/output growth
existing storage growth
```

## MODELED

Future normalized DTI observation volume.

Every modeled estimate must include:

```text
record-size assumption/range
event-rate assumption
retention assumption
MIN / EXPECTED / HIGH
```

Never present MODELED as MEASURED.

Example output:

| Class | Basis | Per hour | Per day | 7 days | 30 days |
|---|---|---:|---:|---:|---:|
| Existing EVE | MEASURED | | | | |
| Future normalized observations | MODELED | | | | |

DTI-00 does not select the final storage engine.

---

# 35. CAPABILITY MATRIX — REQUIRED

Use statuses:

```text
AVAILABLE
PARTIAL
UNRELIABLE
NOT_AVAILABLE
UNKNOWN
```

Minimum rows:

| Capability | Status | Evidence ID(s) | Limitation |
|---|---|---|---|
| client MAC | | | |
| client IPv4 | | | |
| client IPv6 | | | |
| VLAN identity | | | |
| Site attribution | | | |
| upload direction | | | |
| download direction | | | |
| pre-NAT identity | | | |
| both flow directions | | | |
| bytes | | | |
| packets | | | |
| flow count | | | |
| TCP visibility | | | |
| UDP visibility | | | |
| ARP | | | |
| DHCP | | | |
| DNS | | | |
| TLS metadata | | | |
| QUIC metadata | | | |
| ICMP | | | |
| mDNS | | | |
| SSDP | | | |
| capture drop evidence | | | |
| mirror oversubscription evidence | | | |
| parser drop evidence | | | |
| event timestamps | | | |
| host capture path | | | |
| controlled client correlation | | | |
| NetFlow cross-check | | | |

Additional rows are welcome.

---

# 36. REQUIRED DELIVERABLES

The report must contain or attach the following logical artifacts:

1. `DTICaptureCapabilityMatrix`
2. `CaptureTopologyReference`
3. `CapturePlacementProof`
4. `HostCapturePathProof`
5. `CaptureScopeBinding`
6. `CaptureQualityRequirementsAndBaseline`
7. `ControlledClientTraceProof`
8. `MirrorCapacityHeadroomAssessment`
9. `ResourceBudgetBaseline`
10. `ResourceDegradationPolicyRecommendation`
11. `ParserAllocationDecisionRecommendation`
12. `FingerprintSensorCoexistenceDecisionRecommendation`
13. `TrafficAccountingSourceDecisionRecommendation`
14. `StorageVolumeEstimateMeasuredVsModeled`
15. `EvidenceIndex`

---

# 37. PARSER ALLOCATION RECOMMENDATION TABLE

Complete:

| Fact family | Recommended producer | Evidence/Reason |
|---|---|---|
| Fingerprint DHCP | | |
| Fingerprint TCP SYN | | |
| Raw packet traffic accounting | | |
| DNS metadata | | |
| TLS metadata | | |
| QUIC metadata | | |
| flow lifecycle | | |
| Security alerts | | |
| Capture health | | |

Candidate producers:

```text
existing fingerprint sensor
Suricata
lightweight meter
NetFlow cross-check
other discovered existing component
```

---

# 38. REQUIRED REPORT STRUCTURE

Return one main document:

```text
TASK-DTI-00-CAPABILITY-CAPTURE-BASELINE-REPORT
```

Recommended structure:

1. Executive Summary
2. Environment / Evidence Timestamp
3. Evidence Index
4. Current Capture Topology
5. CapturePlacementProof
6. HostCapturePathProof
7. SPAN/RSPAN Configuration Evidence
8. NIC / Kernel Presentation & Offload Effects
9. Client MAC / VLAN Visibility
10. Direction / Both-Sides Flow Evidence
11. NAT Placement
12. ControlledClientTraceProof
13. Mirror Duplication Analysis
14. Mirror Capacity / Headroom
15. CaptureScopeBinding / Site Mapping
16. Capture Quality Baseline
17. Sensor Software Inventory
18. Suricata Capability Inventory
19. Fingerprint Sensor Coexistence Analysis
20. Lightweight Meter Analysis
21. Zeek Gap Analysis
22. NetFlow Overlap
23. Traffic Volume / Protocol Sample
24. Clock / Time Baseline
25. Interval-Based Resource Baseline
26. Storage Volume Estimate — MEASURED vs MODELED
27. DTICaptureCapabilityMatrix
28. Recommendations
29. Unknowns / Blockers
30. Changes Made
31. Final DTI-00 Verdict

---

# 39. FINAL VERDICT — REQUIRED EXACT FIELDS

```text
TASK =
TASK-DTI-00

MODE =
RESEARCH / LAB / INVENTORY

CAPTURE_TOPOLOGY_PROVEN =
YES / PARTIAL / NO

CAPTURE_PLACEMENT_PROVEN =
YES / PARTIAL / NO

HOST_CAPTURE_PATH_PROVEN =
YES / PARTIAL / NO / UNKNOWN

CONTROLLED_CLIENT_TRACE =
PASS / PARTIAL / BLOCKED

CLIENT_MAC_VISIBILITY =
YES / PARTIAL / NO / UNKNOWN

VLAN_VISIBILITY =
YES / PARTIAL / NO / UNKNOWN

PRE_NAT_VISIBILITY =
YES / NO / MIXED / UNKNOWN

BOTH_FLOW_DIRECTIONS =
YES / PARTIAL / NO / UNKNOWN

CAPTURE_PRESENTATION_EFFECTS =
ACCOUNTED / PARTIAL / UNKNOWN

DUPLICATE_RISK =
NONE_PROVEN / POSSIBLE / CONFIRMED / UNKNOWN

MIRROR_OVERSUBSCRIPTION_RISK =
LOW_PROVEN / POSSIBLE / CONFIRMED / UNKNOWN

CAPTURE_COMPLETENESS_EVIDENCE =
SUFFICIENT / PARTIAL / INSUFFICIENT / UNKNOWN

CAPTURE_SCOPE_TO_SITE_PROVEN =
YES / PARTIAL / NO

CAPTURE_QUALITY_BASELINE =
PASS / PARTIAL / UNKNOWN

RESOURCE_BASELINE =
PASS / PARTIAL / UNKNOWN

FINGERPRINT_SURICATA_COEXISTENCE_RECOMMENDATION =
A / B / C / UNRESOLVED

TRAFFIC_ACCOUNTING_SOURCE_RECOMMENDATION =
SURICATA_ONLY / LIGHTWEIGHT_METER / COMBINED / UNRESOLVED

ZEEK_REQUIRED =
NO / POSSIBLY_LATER / JUSTIFIED_GAP / UNRESOLVED

NETFLOW_ROLE =
CROSS_CHECK / DIAGNOSTIC / NOT_USEFUL / UNKNOWN

RESEARCH_PRIVACY_BOUNDARY =
PASS / FAIL

OPEN_P0 =
<number>

OPEN_P1 =
<number>

BLOCKERS =
<exact list or NONE>

CHANGES_MADE =
NONE

DTI_00_VERDICT =
PASS / PARTIAL / BLOCKED
```

---

# 40. PASS CONDITIONS

`DTI_00_VERDICT = PASS` is allowed only when sufficient evidence exists for the major baseline questions:

- mirror topology;
- full host capture path;
- capture placement relative to L2/L3/NAT/uplink;
- client MAC visibility;
- VLAN/Site attribution;
- directionality;
- controlled known-client correlation;
- pre/post NAT;
- capture presentation/offload effects;
- duplicate behavior;
- mirror capacity/oversubscription risk;
- capture quality evidence;
- sensor/parser inventory;
- interval-based resource baseline;
- Fingerprint/Suricata coexistence recommendation;
- traffic-accounting source recommendation.

Not every future capability must be AVAILABLE.

Valid findings include:

```text
PARTIAL
NOT_AVAILABLE
UNKNOWN
```

if they are honestly evidenced and do not leave a major baseline assumption falsely treated as proven.

---

# 41. STOP CONDITIONS

Stop the affected research block and return a blocker if continuing requires:

- changing production configuration;
- restarting a production capture service;
- changing Fingerprint Suricata config;
- enabling new parser outputs;
- installing a new parser;
- reconfiguring SPAN/RSPAN;
- moving the mirror destination;
- changing VLAN/trunk/bridge/vSwitch behavior;
- changing NIC offloads;
- persistent PCAP;
- intrusive/artificial load test;
- changing network path;
- collecting prohibited visitor payload/content.

Blocker format:

```text
DTI-00 RESEARCH BLOCKER

ITEM =
WHY REQUIRED =
WHY READ-ONLY / CONTROLLED EVIDENCE IS INSUFFICIENT =
PROPOSED TEST/CHANGE =
PRODUCTION IMPACT =
CHANGES_MADE = NONE
```

Owner / Architect / TechLead decides whether a separate authorization is warranted.

---

# 42. SUCCESS IS NOT “EVERYTHING WORKS”

The research is successful when reality is known.

Useful conclusions may be:

```text
this direction is not visible
VLAN tag is hidden by host presentation/offload
client MAC is unavailable in a specific path
mirror may oversubscribe
same frame may be mirrored twice
Suricata is insufficient for exact current-rate accounting
NetFlow is useful only as cross-check
host capture path cannot be fully proven
resource headroom is insufficient
capture completeness cannot be established
```

Do not optimize the report toward a PASS answer.

---

# 43. AUTHORIZATION STATE

```text
TASK-DTI-00 =
APPROVED FOR SYSADMIN RESEARCH

ARCHITECTURE =
FINAL / NO CHANGE

ROADMAP =
FINAL / NO CHANGE

IMPLEMENTATION =
NO

CODER =
HOLD

PRODUCTION FEATURE ACTIVATION =
NO

PRODUCTION CONFIG CHANGE =
NO

FINGERPRINT CONTRACT CHANGE =
NO

NEXT AFTER REPORT =
ARCHITECT + TECHLEAD REVIEW
→ exact TASK-DTI-01 technical contract if DTI-00 evidence allows it
```
