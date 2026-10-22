# TASK-DTI-00B — LIGHTWEIGHT PERIODIC TRAFFIC METER PROTOTYPE & ADMISSION FIXTURE

**Project:** CaptivPortal  
**Program:** Device Traffic Enrichment / Device Intelligence (DTI)  
**Task:** TASK-DTI-00B  
**Purpose:** Close the remaining TASK-DTI-00 program gate by implementing and validating a bounded lightweight periodic traffic-accounting meter prototype/fixture.  
**Status:** REVISED — TL-R1..TL-R11 INCORPORATED / SHORT TECH LEAD CONFIRMATION PENDING  
**Architecture:** BOUNDED / NO ROADMAP REDESIGN  
**Implementation:** OFFLINE/LAB PROTOTYPE ONLY AFTER TECH LEAD CONFIRMATION  
**Production feature activation:** NO  
**Production deployment:** NO  
**Production packet attachment:** NOT AUTHORIZED  
**Coder:** HOLD UNTIL TECH LEAD CONFIRMATION  
**DTI-01:** HOLD UNTIL TASK-DTI-00B + TASK-DTI-00A FINAL PASS  

**Implementation base commit:** `c8d8d620dfed06caee92a498b891bf2faa37a6a9`  
**Implementation base tree:** `be3470c378180aa215d527c6de6b686583ae0d79`

---

# 1. ARCHITECT DECISION

The following DTI-00A conclusions are accepted as architecture input:

```text
FINGERPRINT_SURICATA_COEXISTENCE_DECISION = A

Suricata current/future role =
existing Fingerprint TLS/QUIC/JA4 producer
+
preferred DTI general metadata producer
+
flow-lifecycle / completed-flow producer

SURICATA_ACCOUNTING_SEMANTICS =
INSUFFICIENT FOR SOLE PERIODIC ACCOUNTING

LIGHTWEIGHT_METER_REQUIRED =
YES
```

Reason:

```text
Suricata terminal flow totals were accurate for the tested completed flow,
but did not provide the interval/current semantics required by DTI.
```

Therefore the DTI architecture proceeds with a candidate split ownership:

```text
Suricata
→ metadata
→ flow lifecycle
→ completed-flow totals

Lightweight periodic meter
→ periodic packet/byte slices
→ current rate
→ current activity
→ long-lived-flow interval accounting
→ Visit-boundary slicing
```

This split is CANDIDATE ownership until TASK-DTI-00B admission passes.

If the lightweight meter passes admission, ownership freezes as:

```text
Lightweight meter
→ authoritative owner of packet-observed periodic accounting
→ periodic packet/byte slices
→ current-rate primitive
→ current-activity primitive
→ long-lived-flow interval slicing
→ Visit-boundary slicing

Suricata
→ protocol metadata
→ flow lifecycle
→ completed-flow totals as flow metadata / diagnostic cross-check
```

Suricata completed-flow byte counters MUST NOT silently become a second authoritative Traffic accounting source.

Forbidden fallback:

```text
meter unavailable
→ use Suricata bytes as equivalent product Traffic metric
```

unless a future separately frozen reconciliation contract explicitly permits it.

Permanent invariant:

```text
ONE PRODUCT METRIC
→ ONE SEMANTIC OWNER
```

---

# 2. TASK PURPOSE

TASK-DTI-00B must answer one bounded question:

```text
Can a minimal lightweight periodic meter
provide authoritative interval accounting primitives
required by DTI without harming the accepted
Fingerprint / Suricata production path?
```

The task must produce enough evidence to allow TASK-DTI-00A to close:

```text
TRAFFIC_ACCOUNTING_SOURCE_DECISION
PARSER_ALLOCATION_DECISION
RESOURCE_DEGRADATION_POLICY
DTI01_RESOURCE_BUDGET_CANDIDATE
```

---

# 3. NON-GOALS

TASK-DTI-00B MUST NOT:

```text
implement DTI-01
create durable DTI production storage
create Device Card UI
create service recognition
create DNS/TLS/QUIC product intelligence
change Device Fingerprint semantics
change Authorization/CAPPORT
change Omada
change RSPAN
change NIC/offload/ring settings
replace Suricata
introduce Zeek
repair NetFlow
freeze final user-visible byte basis
deploy a permanent production service
create a general packet archive
```

---

# 4. EXECUTION MODE

Preferred order:

```text
1. OFFLINE / LAB REPLAY
2. ISOLATED SHADOW FIXTURE
3. TEMPORARY CONTROLLED PRODUCTION COMPATIBILITY TEST
   only if remaining admission evidence cannot be obtained otherwise
```

A new packet consumer on production `enp8s0` is NOT automatically a safe shadow test.

If the prototype must attach to production `enp8s0`, execution requires:

```text
TEMPORARY_CONTROLLED_PRODUCTION_COMPATIBILITY_TEST
+
separate explicit Owner authorization
```

before attachment.

Functional/accounting admission and production-topology admission are separate.

TASK-DTI-00B functional/accounting admission MAY PASS completely offline.

However, if final intended production parser allocation is:

```text
lightweight meter
→ direct packet consumer
→ production enp8s0
```

then DTI-00 PROGRAM CLOSURE requires one separately Owner-authorized production coexistence test proving at minimum:

```text
no packet stealing
no Fingerprint functional regression
no Fingerprint source-health regression
no new sustained capture-drop growth
bounded CPU/RAM impact
clean detach / rollback
```

Therefore:

```text
PACKET_STEALING = NOT_APPLICABLE
```

is acceptable for an offline TASK-DTI-00B report, but is NOT sufficient to close DTI-00 if final production topology requires the meter to become a direct packet consumer.

---

# 5. PROTOTYPE ROLE

The prototype shall be:

```text
LIGHTWEIGHT
BOUNDED
HEADER/METADATA ONLY
NO PAYLOAD RETENTION
NO GENERAL PCAP ARCHIVE
NO BUSINESS LOGIC
NO DEVICE CLASSIFICATION
NO AUTHORIZATION EFFECT
```

Its responsibility is limited to deriving normalized periodic accounting primitives from observed packet headers.

Conceptual output:

```text
PeriodicTrafficSlice
```

The exact final DTI durable schema is NOT implemented here.

## 5.1 Prototype Accounting Scope

TASK-DTI-00B prototype admission scope is intentionally narrow.

Mandatory accounted traffic:

```text
controlled subject MAC
+
IPv4 / IPv6
+
unicast traffic
+
subject MAC is L2 source or destination
```

TASK-DTI-00B does NOT freeze final product semantics for:

```text
broadcast
multicast
ARP
LLDP
other L2 traffic classes
```

Those remain future `TrafficAccountingScope` work.

---

# 6. MINIMUM INPUT SEMANTICS

The prototype must be able to observe enough packet/header information to derive:

```text
capture/event timestamp
source MAC
destination MAC
IPv4 / IPv6 endpoint where present
IP protocol
packet length / native byte basis
client-relative direction when proven by test fixture
capture-source identity
```

The prototype MUST NOT require application payload.

Mandatory offline prototype input:

```text
classic PCAP
Ethernet link type
microsecond or nanosecond timestamps
```

`PCAPNG` is NOT mandatory for PASS.

```text
NEW PROJECT/RUNTIME DEPENDENCY = NO
```

Prototype parsing must remain inside research/prototype code.

If Coder determines a new external dependency is genuinely required:

```text
STOP
→ IMPLEMENTATION DEPENDENCY
→ TECH LEAD REVIEW
```

Do not modify project/runtime requirements silently.

---

# 7. PROTOTYPE OUTPUT — MINIMUM FIELDS

Each emitted periodic slice must contain at least:

```text
schema_version
prototype_version

capture_source_id
site_scope/test_scope

slice_start_utc
slice_end_utc

subject_key
    test-client MAC for admission fixture

upload_packets
download_packets

upload_bytes_native
download_bytes_native

first_packet_at
last_packet_at

capture_quality_state

slice_id
run_session_id

source_sequence / emission identity
where needed for replay/idempotency testing
```

`slice_id` and `run_session_id` are different concepts.

`slice_id` MUST be deterministic from semantic slice identity including at minimum:

```text
schema_version
capture_source_id
subject_key
slice_start_utc
slice_end_utc
```

Replay invariant:

```text
same bounded input
→ same semantic slice
→ same slice_id
→ same accounting payload
```

If the same `slice_id` produces a different semantic accounting payload:

```text
CONFLICT
```

not another valid slice.

`run_session_id` may differ between executions.

The production DTI schema is intentionally NOT frozen by this prototype.

---

# 8. PERIODIC SLICE CONTRACT

The prototype must emit bounded half-open intervals:

```text
[slice_start_utc, slice_end_utc)
```

Exact production bucket duration is NOT frozen here.

Primary admission cadence:

```text
PRIMARY_TEST_SLICE = 5 seconds
```

Alignment:

```text
UTC epoch-aligned
half-open intervals
```

Example:

```text
[12:00:00, 12:00:05)
[12:00:05, 12:00:10)
```

Additional cadences may be tested experimentally.

TASK-DTI-00B PASS MUST be demonstrated using the 5-second primary admission cadence.

This does NOT freeze the final production DTI bucket duration.

---

# 9. NO FINAL BYTE-BASIS FREEZE

For TASK-DTI-00B prototype/admission only, freeze:

```text
METER_NATIVE_BYTE_BASIS =
L3 IP packet length
```

Definition:

```text
IPv4 =
IPv4 total_length

IPv6 =
40-byte IPv6 base header + payload_length
```

Do NOT count as the prototype authoritative basis:

```text
pcap captured length
Ethernet frame length
TCP payload
application payload
```

This does NOT freeze the final user-visible `TrafficAccountingContract` byte basis.

It freezes only a reproducible native basis for this prototype.

Independent reconciliation against reference truth remains mandatory.

---

# 10. ACCOUNTING REFERENCE TRUTH

The meter MUST NOT validate itself.

For every controlled scenario define:

```text
AccountingReferenceTruth
```

using one or more of:

```text
bounded PCAP from Owner-authorized controlled client
independent packet counts
independent byte totals
controlled sender/receiver counters
known event timeline
known synthetic logical boundary T
```

Reference truth and meter output must be independently derived.

Circular validation is forbidden.

## 10.1 Fixture Coverage Manifest

Every offline fixture MUST define an authoritative coverage window.

Required concepts:

```text
capture_source_id
test/site scope
subject_mac
coverage_start_utc
coverage_end_utc
capture_quality_intervals
optional synthetic Visit boundary T
```

Within proven healthy coverage:

```text
no qualifying subject traffic
→ normal zero slice is allowed
```

Outside proven coverage, or during degraded/unavailable coverage:

```text
no observed packets
MUST NOT become
zero traffic
```

Permanent invariant:

```text
ZERO TRAFFIC
!=
SOURCE MISSING / CAPTURE DEGRADED / PROTOTYPE UNAVAILABLE
```

---

# 11. REQUIRED SCENARIOS

The prototype/admission fixture must cover:

```text
A. short completed flow
B. long-lived flow crossing multiple slices
C. idle interval
D. traffic burst
E. flow active before slice/window start
F. flow ending after slice/window end
G. synthetic logical Visit boundary T inside a continuing flow
H. prototype restart between intervals
I. replay of same bounded fixture for deterministic/reproducible output
J. exact mirrored duplicate fixture
K. network retransmission fixture
L. partial-capture / degraded-quality fixture
M. IPv4
N. IPv6 where naturally available or isolated fixture exists
O. upload
P. download
```

Production disturbance is not required when a semantic property can be proven offline.

---

# 12. VISIT-BOUNDARY CAPABILITY

Do NOT manipulate production Visit/Auth/CAPPORT state.

Use:

```text
controlled long-lived flow
+
synthetic logical boundary T
```

Then prove:

```text
sum(before T)
+
sum(after T)
=
whole observed interval
```

subject to the prototype's native byte semantics and quality state.

The goal is to prove deterministic slicing capability, not Visit integration.

---

# 13. CURRENT RATE SEMANTICS

The prototype must prove that rate can be derived from completed periodic slices without waiting for flow termination.

At minimum demonstrate:

```text
rate for active slice
rate after burst
rate during idle
rate freshness after traffic stops
```

The prototype must expose enough timing information that a future DTI Current Activity layer can distinguish:

```text
ACTIVE
IDLE
STALE / UNAVAILABLE
```

Do not implement final product state semantics here.

---

# 14. CURRENT ACTIVITY SUPPORT

The prototype must prove timely evidence for:

```text
last observed packet time
recent traffic within current slice/window
absence of qualifying traffic under sufficient capture coverage
```

It MUST NOT turn:

```text
source missing
capture degraded
prototype stopped
```

into:

```text
IDLE
```

Instead the prototype/fixture must expose insufficient/unavailable quality evidence.

---

# 15. DIRECTION SEMANTICS

For admission testing, direction is from the controlled client perspective:

```text
UPLOAD = client → network
DOWNLOAD = network → client
```

The fixture must prove direction from:

```text
known controlled-client MAC/IP
+
observed packet endpoints
```

Do not infer product direction only from generic parser labels.

---

# 16. DUPLICATE VS RETRANSMISSION

The prototype must explicitly prove distinct behavior for:

```text
MIRROR DUPLICATE
!=
NETWORK RETRANSMISSION
```

For the controlled duplicate fixture:

```text
same original captured frame repeated by capture/replay topology
```

For retransmission fixture:

```text
new network transmission of equivalent higher-layer data
```

The admission report must state:

```text
native behavior before dedup
dedup method if used
dedup horizon
dedup identity
false-positive risk
false-negative risk
effect on byte/packet totals
effect on provenance
```

Do NOT silently drop retransmissions as duplicates.

Mirror-duplicate handling is a PASS gate.

If a safe bounded method cannot be demonstrated without incorrectly suppressing legitimate retransmissions:

```text
TASK_DTI_00B_VERDICT = PARTIAL
```

Do not fabricate PASS.

Network retransmission remains counted as actual observed network traffic.

---

# 17. DEDUP DESIGN BOUNDARY

The meter may include a prototype dedup mechanism only if required to prove feasibility.

Any dedup must be:

```text
bounded in memory
time-bounded
deterministic
observable through counters
configurable
fail-safe
```

At minimum expose:

```text
raw_packets_seen
duplicate_candidates
deduplicated_packets
dedup_cache_entries
dedup_evictions
```

The existing Fingerprint dedup implementation MUST NOT be imported as a semantic dependency merely because it already exists.

Reuse of ideas is allowed; ownership/contracts remain separate.

---

# 18. RESTART SEMANTICS

Prototype restart must be tested safely, preferably offline/shadow.

Required evidence:

```text
what happens to an open interval?
is partial slice emitted, dropped, or marked incomplete?
does sequence identity reset?
can replay duplicate an already-emitted slice?
can downstream detect restart?
does current accounting become unavailable during the gap?
```

The final production restart policy is not frozen, but the candidate must demonstrate a deterministic feasible model.

---

# 19. IDEMPOTENCY / REPLAY

The fixture must prove that repeating the same input does not create ambiguous accounting output.

Required concept:

```text
stable slice identity
or
stable source/event identity
```

sufficient for future DTI ingestion to prevent duplicate persistence.

Required test:

```text
same bounded input replayed twice
→ outputs are deterministically comparable
→ future ingest can identify duplicate generation
```

The durable DTI ingest implementation remains DTI-01 scope.

---

# 20. CAPTURE QUALITY PROVENANCE

Each prototype slice must carry or be correlated with enough state to determine:

```text
capture healthy
capture partial/degraded
source unavailable
prototype unavailable
```

Required invariant:

```text
missing/degraded evidence
!=
zero traffic
```

The meter must not output a normal complete zero slice when it knows input capture was unavailable.

---

# 21. SOURCE / SITE BOUNDARY

For the prototype fixture:

```text
capture_source_id
```

must remain explicit.

Current accepted production binding may be used if executing against the approved production capture path.

The prototype MUST NOT invent Site attribution.

Multi-Site product schema is not implemented here.

---

# 22. RESOURCE DESIGN GOAL

The candidate is intentionally called lightweight.

The admission must measure:

```text
incremental CPU
incremental RAM
queue/buffer use
output rate
disk growth if any
packet/capture drops
scheduler/timing behavior
```

The prototype must have bounded:

```text
memory
queue
output
```

No unbounded growth.

Resource admission must approximate the known real capture workload, not merely measure maximum offline parser speed.

Accepted DTI-00 reference baseline:

```text
VLAN999:
~19,000 packets/s
~156.6 Mbit/s
```

TASK-DTI-00B resource tests MUST include where the fixture permits:

```text
1. paced replay approximately matching baseline load
2. bounded higher-load run approximately 2x baseline
```

Measure at minimum:

```text
CPU
RSS / memory
queue/buffer usage
processed packets
dropped/rejected input packets
slice emission rate
output bytes/rate
timing drift
```

Hard failure conditions:

```text
unbounded memory
unbounded queue
silent lost accounting
loss without CaptureQuality degradation
sustained inability to keep up with baseline admission load
```

Exact final production CPU/RAM/systemd/cgroup limits remain DTI-01 scope.

---

# 23. DTI01 RESOURCE BUDGET CANDIDATE

TASK-DTI-00B must return evidence sufficient to complete:

```text
DTI01_RESOURCE_BUDGET_CANDIDATE
```

At minimum:

```text
meter incremental CPU envelope
meter incremental RAM envelope
slice output rate
modeled normalized storage rate
queue/buffer ceiling candidate
drop/error trigger candidate
backpressure/degradation behavior candidate
disk-full behavior candidate
```

Exact production enforcement remains DTI-01 scope.

---

# 24. PRODUCTION COMPATIBILITY GATE

If, and only if, offline/lab evidence is insufficient and the meter must attach to production `enp8s0`, then before execution:

```text
STOP
→ OWNER AUTHORIZATION REQUEST
```

The request must include:

```text
TEST_ID
prototype binary/version/hash
capture mode
AF_PACKET/libpcap mode
fanout/cluster identity if any
copy vs load-sharing behavior
expected interaction with existing Fingerprint consumers
expected duration
CPU/RAM/output bounds
monitoring gates
stop conditions
rollback
data/privacy scope
CHANGES_ALREADY_MADE = NONE
```

No production attachment without explicit approval.

---

# 25. FINGERPRINT PROTECTION

Any production compatibility test must prove no material regression in:

```text
fingerprint-sensor service state
fingerprint-suricata service state
Fingerprint runtime_state
Fingerprint source health
TLS/QUIC/JA4 normalization
Suricata capture drops
kernel/capture drops
CPU
RAM
I/O
event timing
```

The lightweight meter is the component under test.

Fingerprint must not be modified to accommodate it.

---

# 26. NO PACKET STEALING

If using AF_PACKET or equivalent on production capture interface, the prototype must prove whether delivery is:

```text
independent copy
fanout load-sharing
clustered delivery
other
```

Admission MUST FAIL if the prototype steals/distributes packets away from accepted Fingerprint consumers.

---

# 27. PRIVACY

Use only:

```text
Owner-authorized controlled client
bounded fixtures
headers/metadata
```

Do not retain:

```text
application payload
HTTP body
cookies
credentials
arbitrary visitor DNS/SNI history
general visitor flow archive
```

A bounded research PCAP for the controlled test client may be used only under explicit approved test scope and should be deleted after evidence acceptance unless another retention decision is made.

---

# 28. CODER / SYSADMIN RESPONSIBILITY AND IMPLEMENTATION BOUNDARY

## Coder

After Tech Lead confirmation only:

```text
implements prototype
implements deterministic synthetic fixtures
runs offline targeted tests
creates replay/admission artifacts

NO production access
NO enp8s0 attachment
NO systemd production service
NO production config change
```

Coder MUST NEVER independently attach the prototype to production `enp8s0`.

Allowed implementation area:

```text
research/dti_00b/**
tests/dti_00b/**
```

Forbidden:

```text
app/**
systemd/**
production configuration
requirements.txt
DB/schema
Device Fingerprint production code
Suricata production config
Auth/CAPPORT
Admin Web
Omada
RSPAN/NIC configuration
```

Targeted Coder verification:

```text
pytest tests/dti_00b -q
```

plus syntax/import checks for changed prototype files.

Coder does NOT run the broad/full project gate for this prototype task.

Coder does NOT:

```text
push
open PR
merge
deploy
touch production
```

until subsequent Tech Lead review.

## Sysadmin

Only after a reviewed prototype artifact exists:

```text
executes any later host/live compatibility validation
follows exact approved runbook
requires explicit Owner authorization where production enp8s0
attachment or production effect is involved
```

---

# 35. REQUIRED PROTOTYPE ARTIFACTS

The implementation dependency, once Tech Lead authorizes Coder involvement, must produce at minimum:

```text
1. prototype source/package
2. version/hash identity
3. exact run instructions
4. exact input mode
5. exact output schema
6. resource bounds/config
7. test fixtures
8. replay instructions
9. no-production-deploy statement
10. rollback/cleanup instructions
```

No systemd production service is required for the prototype unless a later explicit test authorization requires one.

---

# 35. REQUIRED ADMISSION MATRICES

## 29.1 Accounting capability matrix

| Capability | Lightweight meter | Reference truth | Verdict |
|---|---|---|---|
| periodic bytes | | | |
| periodic packets | | | |
| current rate primitive | | | |
| current activity primitive | | | |
| long-lived flow slicing | | | |
| synthetic Visit-boundary slicing | | | |
| upload/download | | | |
| restart semantics | | | |
| deterministic slice_id | | | |
| run/session identity | | | |
| replay/idempotency support | | | |
| healthy-coverage zero slices | | | |
| degraded/unavailable non-zero semantics | | | |
| mirror duplicate handling | | | |
| retransmission distinction | | | |
| CaptureQuality provenance | | | |
| bounded resource behavior | | | |

## 29.2 Reconciliation matrix

For every controlled scenario:

| Scenario | Reference packets | Meter packets | Reference bytes | Meter bytes | Timing/slice verdict | Quality |
|---|---:|---:|---:|---:|---|---|

Do not require billing-grade equality until final byte basis is frozen.

Any mismatch must be explained.

---

# 35. REQUIRED FINAL OWNERSHIP DECISION

After meter admission, TASK-DTI-00A must finalize packet-observed periodic accounting ownership.

If TASK-DTI-00B PASS confirms the candidate:

```text
LIGHTWEIGHT METER =
AUTHORITATIVE OWNER OF PACKET-OBSERVED PERIODIC ACCOUNTING
```

Suricata remains:

```text
metadata / flow lifecycle / completed-flow diagnostic cross-check
```

and MUST NOT become an implicit fallback accounting owner.

The formal decision may be represented as:

```text
TRAFFIC_ACCOUNTING_SOURCE_DECISION =
LIGHTWEIGHT_METER
```

with parser allocation documenting explicit split ownership across non-overlapping semantic domains.

Expected split if evidence confirms the current direction:

```text
Fingerprint raw
→ Fingerprint DHCP/TCP-SYN evidence only

Suricata
→ Fingerprint TLS/QUIC/JA4
→ DTI general protocol metadata
→ flow lifecycle
→ completed-flow totals

Lightweight meter
→ authoritative periodic packet/byte slices
→ current rate primitive
→ current activity primitive
→ long-lived-flow interval slicing
→ Visit-boundary slicing

NetFlow
→ diagnostic / cross-check only

Zeek
→ not admitted
```

But the final decision MUST follow evidence.

---

# 35. ACCEPTANCE GATES

TASK-DTI-00B may PASS only if all are evidence-backed:

```text
G1  periodic packet slices correct
G2  periodic byte slices correct under declared native byte basis
G3  upload/download correct
G4  short-flow behavior correct
G5  long-lived-flow interval behavior correct
G6  idle interval semantics correct
G7  burst behavior correct
G8  synthetic Visit boundary deterministically sliceable
G9  restart semantics deterministic
G10 replay/idempotency support feasible
G11 mirror duplicate handling explicit
G12 retransmission not silently treated as mirror duplicate
G13 CaptureQuality provenance present
G14 missing source never becomes normal zero
G15 resource use bounded and measured
G16 output/storage growth bounded
G17 no payload retention
G18 Fingerprint path protected
G19 no packet stealing in any production compatibility test
G20 DTI01 resource-budget candidate complete enough for DTI-01

G21 prototype accounting scope limited to subject-MAC unicast IPv4/IPv6

G22 native prototype byte basis = L3 IP packet length

G23 PASS demonstrated at UTC epoch-aligned 5-second cadence

G24 coverage manifest correctly distinguishes healthy zero vs missing/degraded source

G25 deterministic slice_id + separate run/session identity proven

G26 mirror-duplicate handling proven without suppressing legitimate retransmission

G27 mandatory classic-PCAP Ethernet offline input works without new project/runtime dependency

G28 baseline-load paced replay is sustainable; higher bounded load characterized

G29 offline functional/accounting PASS is explicitly separated from any later production direct-consumer admission
```

---

# 35. FINAL REPORT

Return:

```text
TASK-DTI-00B-LIGHTWEIGHT-PERIODIC-TRAFFIC-METER-PROTOTYPE-ADMISSION-REPORT
```

Required final fields:

```text
TASK =
TASK-DTI-00B

PROTOTYPE_IMPLEMENTED =
YES / NO

PROTOTYPE_VERSION =
<id>

EXECUTION_MODE =
OFFLINE_LAB / SHADOW / TEMPORARY_PRODUCTION_TEST

CONTROLLED_CLIENT_USED =
YES / NO

METER_NATIVE_BYTE_BASIS =
L3 IP packet length

PRIMARY_TEST_SLICE =
5 seconds / UTC epoch-aligned / half-open

PROTOTYPE_ACCOUNTING_SCOPE =
subject-MAC unicast IPv4/IPv6 only

PERIODIC_PACKET_SLICES =
PASS / PARTIAL / FAIL

PERIODIC_BYTE_SLICES =
PASS / PARTIAL / FAIL

CURRENT_RATE_PRIMITIVE =
PASS / PARTIAL / FAIL

CURRENT_ACTIVITY_PRIMITIVE =
PASS / PARTIAL / FAIL

LONG_LIVED_FLOW_SLICING =
PASS / PARTIAL / FAIL

VISIT_BOUNDARY_SLICING =
PASS / PARTIAL / FAIL

UPLOAD_DOWNLOAD =
PASS / PARTIAL / FAIL

RESTART_SEMANTICS =
PASS / PARTIAL / FAIL

DETERMINISTIC_SLICE_ID =
PASS / PARTIAL / FAIL

RUN_SESSION_IDENTITY =
PASS / PARTIAL / FAIL

REPLAY_IDEMPOTENCY_SUPPORT =
PASS / PARTIAL / FAIL

COVERAGE_ZERO_SEMANTICS =
PASS / PARTIAL / FAIL

MIRROR_DUPLICATE_HANDLING =
PASS / PARTIAL / FAIL

RETRANSMISSION_DISTINCTION =
PASS / PARTIAL / FAIL

CAPTURE_QUALITY_PROVENANCE =
PASS / PARTIAL / FAIL

RESOURCE_IMPACT =
BOUNDED / UNBOUNDED / UNKNOWN

FINGERPRINT_REGRESSION =
NO / YES / NOT_APPLICABLE

PACKET_STEALING =
NO / YES / NOT_APPLICABLE / UNKNOWN

OFFLINE_FUNCTIONAL_ACCOUNTING_ADMISSION =
PASS / PARTIAL / FAIL

PRODUCTION_TOPOLOGY_ADMISSION_REQUIRED =
YES / NO

DTI01_RESOURCE_BUDGET_CANDIDATE =
COMPLETE / PARTIAL / UNRESOLVED

OPEN_P0 =
<number>

OPEN_P1 =
<number>

IMPLEMENTATION_DEPENDENCIES =
<list or NONE>

CHANGES_MADE =
<exact>

ROLLBACK_STATUS =
NOT_APPLICABLE / PASS / FAIL

TASK_DTI_00B_VERDICT =
PASS / PARTIAL / FAIL / BLOCKED
```

---

# 35. PROGRAM CLOSURE AFTER PASS

If TASK-DTI-00B functional/accounting admission passes, return the evidence to TASK-DTI-00A final review.

If the final intended production topology requires the lightweight meter to become a direct packet consumer on production `enp8s0`, DTI-00 closure additionally requires one separately Owner-authorized production coexistence test.

Required sequence:

```text
TASK-DTI-00B OFFLINE FUNCTIONAL/ACCOUNTING PASS
        ↓
is direct production packet consumer required?
        ↓
YES → Owner-authorized production coexistence admission
NO  → continue
        ↓
TASK-DTI-00A FINAL ACCOUNTING/PARSER ALLOCATION DECISION
        ↓
TASK-DTI-00 = CLOSED
        ↓
Architect writes exact TASK-DTI-01
NETWORK OBSERVATION FOUNDATION
```

DTI-01 MUST NOT begin before this closure.

---

# 35. AUTHORIZATION STATE

```text
TASK-DTI-00B CONTRACT =
REVISED / TL-R1..TL-R11 INCORPORATED
SHORT TECH LEAD CONFIRMATION PENDING

ARCHITECT DECISION =
LIGHTWEIGHT PERIODIC METER PROTOTYPE/ADMISSION REQUIRED

BASE_COMMIT =
c8d8d620dfed06caee92a498b891bf2faa37a6a9

BASE_TREE =
be3470c378180aa215d527c6de6b686583ae0d79

CODER =
HOLD UNTIL TECH LEAD CONFIRMATION

EXPECTED AFTER TECH LEAD CONFIRMATION =
CODER AUTHORIZED FOR OFFLINE/LAB PROTOTYPE IMPLEMENTATION ONLY

PRODUCTION FEATURE ACTIVATION =
NO

PRODUCTION DEPLOYMENT =
NO

PRODUCTION PACKET CONSUMER ATTACHMENT =
NOT AUTHORIZED

DTI-01 =
HOLD

NEXT =
TECH LEAD SHORT CONFIRMATION OF R1 CONTRACT
```


---

# 36. TECH LEAD R1 DISPOSITION INCORPORATED

```text
TECH LEAD REVIEW =
ARCHITECTURE DIRECTION PASS
TASK BOUNDARY PASS
ROADMAP CHANGE NO
REDESIGN NO

TL-R1..TL-R11 =
INCORPORATED AS BINDING REQUIREMENTS

CONTRACT STATE =
AWAITING SHORT TECH LEAD CONFIRMATION

CODER =
HOLD

PRODUCTION =
NO CHANGE

PRODUCTION PACKET ATTACHMENT =
NOT AUTHORIZED

DTI-01 =
HOLD
```
