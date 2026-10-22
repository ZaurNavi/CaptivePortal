# TASK-DTI-00B — LIGHTWEIGHT PERIODIC TRAFFIC METER PROTOTYPE & ADMISSION FIXTURE

**Project:** CaptivPortal  
**Program:** Device Traffic Enrichment / Device Intelligence (DTI)  
**Task:** TASK-DTI-00B  
**Purpose:** Close the remaining TASK-DTI-00 program gate by implementing and validating a bounded lightweight periodic traffic-accounting meter prototype/fixture.  
**Status:** DRAFT FOR TECH LEAD REVIEW  
**Architecture:** BOUNDED / NO ROADMAP REDESIGN  
**Implementation:** PROTOTYPE / ADMISSION FIXTURE ONLY AFTER TECH LEAD APPROVAL  
**Production feature activation:** NO  
**Production deployment:** NO  
**Coder:** HOLD UNTIL TECH LEAD ACCEPTANCE  
**DTI-01:** HOLD UNTIL TASK-DTI-00B + TASK-DTI-00A FINAL PASS  

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

source_sequence / emission identity
where needed for replay/idempotency testing
```

The production DTI schema is intentionally NOT frozen by this prototype.

---

# 8. PERIODIC SLICE CONTRACT

The prototype must emit bounded half-open intervals:

```text
[slice_start_utc, slice_end_utc)
```

Exact production bucket duration is NOT frozen here.

For the prototype/admission fixture, choose a test cadence that is:

```text
short enough to prove current-rate/current-activity semantics
long enough to avoid meaningless scheduler noise
```

The chosen cadence must be documented and justified.

At least two cadences may be tested if useful.

---

# 9. NO FINAL BYTE-BASIS FREEZE

The prototype must explicitly state its native counted byte basis.

Candidate examples:

```text
captured Ethernet frame bytes
IP total length bytes
other header-derived basis
```

But TASK-DTI-00B does NOT decide the final user-visible TrafficAccountingContract byte basis.

Required:

```text
METER_NATIVE_BYTE_BASIS =
<exact proved basis>
```

and independent reconciliation against reference truth.

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

---

# 17. DEDUP DESIGN BOUNDARY

The meter may include a prototype dedup mechanism only if required to prove feasibility.

Any dedup must be:

```text
bounded in memory
time-bounded
deterministic
observable through counters
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

# 28. REQUIRED PROTOTYPE ARTIFACTS

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

# 29. REQUIRED ADMISSION MATRICES

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
| stable slice identity | | | |
| replay/idempotency support | | | |
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

# 30. REQUIRED FINAL OWNERSHIP DECISION

After meter admission, TASK-DTI-00A must be able to finalize one of:

```text
TRAFFIC_ACCOUNTING_SOURCE_DECISION =
LIGHTWEIGHT_METER
```

or:

```text
TRAFFIC_ACCOUNTING_SOURCE_DECISION =
EXPLICIT_SPLIT_OWNERSHIP
```

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

# 31. ACCEPTANCE GATES

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
```

---

# 32. FINAL REPORT

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
<exact>

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

REPLAY_IDEMPOTENCY_SUPPORT =
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

# 33. PROGRAM CLOSURE AFTER PASS

If TASK-DTI-00B passes, return the evidence to TASK-DTI-00A final review.

Required final program sequence:

```text
TASK-DTI-00B PASS
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

# 34. AUTHORIZATION STATE

```text
TASK-DTI-00B CONTRACT =
DRAFT FOR TECH LEAD REVIEW

ARCHITECT DECISION =
LIGHTWEIGHT PERIODIC METER PROTOTYPE/ADMISSION REQUIRED

CODER =
HOLD UNTIL TECH LEAD ACCEPTS THIS CONTRACT

PRODUCTION FEATURE ACTIVATION =
NO

PRODUCTION DEPLOYMENT =
NO

PRODUCTION PACKET CONSUMER ATTACHMENT =
REQUIRES SEPARATE OWNER AUTHORIZATION IF NEEDED

DTI-01 =
HOLD

NEXT =
TECH LEAD REVIEW OF TASK-DTI-00B
```
