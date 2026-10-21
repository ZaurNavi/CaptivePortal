# TASK-DTI-00A — CAPTURE CONSUMER COEXISTENCE & TRAFFIC ACCOUNTING SOURCE ADMISSION

**Project:** CaptivPortal  
**Program:** Device Traffic Enrichment / Device Intelligence (DTI)  
**Task:** TASK-DTI-00A  
**Type:** BOUNDED RESEARCH / ADMISSION VALIDATION  
**Primary executor:** System / Network Administrator  
**Architecture owner:** Architect  
**Review:** Tech Lead  
**Contract status:** APPROVED FOR SYSADMIN EXECUTION — DTI00A-R1..R10 INCORPORATED  
**Coder:** HOLD  
**DTI-01:** HOLD  
**Production feature activation:** NO  
**Production configuration change:** NOT AUTHORIZED BY THIS DOCUMENT  

---

# 1. PURPOSE

TASK-DTI-00A exists only to close the remaining DTI-00 program gate.

It MUST produce final evidence-backed decisions for:

```text
FingerprintSensorCoexistenceDecision
TrafficAccountingSourceDecision
ParserAllocationDecision
ResourceDegradationPolicy sufficient for DTI-01
```

This task does NOT repeat TASK-DTI-00.

The accepted DTI-00 physical/host baseline is the input evidence for this task.

---

# 2. ACCEPTED BASELINE — DO NOT RE-INVESTIGATE

Treat the following as accepted unless the environment is explicitly changed before execution:

```text
Capture topology:
Catalyst RSPAN
→ remote VLAN999
→ Gi1/0/48
→ omv-hp enp7s0f1
→ enp7s0f1.999
→ macvtap0
→ Ubuntu VM
→ enp8s0
→ fingerprint-sensor + fingerprint-suricata

Capture placement:
PRE-NAT

Client MAC:
VISIBLE

Client private IPv4:
VISIBLE

Both flow directions:
VISIBLE

CaptureScopeBinding:
zefer-span-01
→ site_id 6a64f17630da7c70d232187a
→ guest 192.168.8.0/22

RSPAN systematic BOTH-direction duplication:
REMEDIATED / CLOSED

Current RSPAN source:
VLAN10 + VLAN20
RX-only

Residual exact repeats:
POSSIBLE / low-rate
must remain an accounting-quality consideration

CaptureQuality baseline:
PASS

Capture completeness:
PARTIAL

Mirror oversubscription risk:
POSSIBLE

Fingerprint raw sensor:
SPECIALIZED / FROZEN
DHCP + guest outbound TCP SYN + existing source health
NOT a general traffic meter

Current Suricata:
8.0.6
AF_PACKET on enp8s0
current production role = Fingerprint TLS/QUIC/JA4 + stats
installed capability includes additional flow/DNS/DHCP/HTTP/alert families
not all are production-admitted

Zeek:
NOT REQUIRED

NetFlow:
DIAGNOSTIC / CROSS-CHECK ONLY
NOT DTI-critical
```

Do not spend this task re-proving those facts.

---

# 3. QUESTIONS THIS TASK MUST ANSWER

## Q1 — Suricata coexistence

Can the existing production Suricata be safely reused as:

```text
DTI GENERAL METADATA PRODUCER
```

through an additional isolated/versioned DTI output without materially degrading or changing the accepted Fingerprint path?

Required final result:

```text
FINGERPRINT_SURICATA_COEXISTENCE_DECISION =
A / B / C
```

where:

```text
A =
reuse existing Suricata process
with additional isolated/versioned DTI output

B =
separate DTI Suricata instance

C =
another proved safe fan-out topology
```

Option A is the FIRST admission candidate.

Do not evaluate B/C unless A fails the admission gate or cannot be tested safely.

---

## Q2 — Traffic accounting source

Can admitted Suricata semantics satisfy the periodic traffic-accounting primitives required by future DTI?

Required final result:

```text
TRAFFIC_ACCOUNTING_SOURCE_DECISION =
SURICATA
/
LIGHTWEIGHT_METER
/
EXPLICIT_SPLIT_OWNERSHIP
```

A split result is valid.

Example only if supported by evidence:

```text
Suricata
→ protocol metadata
→ TLS/QUIC/DNS
→ flow lifecycle

Lightweight periodic meter
→ interval packet/byte slices
→ current rate
→ current network activity
→ Visit slicing
```

Do not force all capabilities into one producer.

---

# 4. PERMANENT SEMANTIC RULES

Preserve:

```text
ONE PRODUCT METRIC
→ ONE SEMANTIC OWNER
```

Do NOT silently combine:

```text
Suricata bytes
NetFlow bytes
Omada counters
packet-meter bytes
```

into one product number.

Other sources may be used only as:

```text
cross-check
diagnostic evidence
supporting evidence
```

unless a later frozen reconciliation contract explicitly permits otherwise.

Also preserve:

```text
MIRROR DUPLICATE
!=
NETWORK RETRANSMISSION
```

and:

```text
missing source
!=
zero traffic
!=
healthy
!=
complete
```

---

# 5. BYTE BASIS — DO NOT FREEZE PRODUCT SEMANTICS HERE

TASK-DTI-00A MUST record the native byte semantics of every candidate.

Possible native meanings may include:

```text
L2 frame bytes
IP bytes
transport bytes
application payload bytes
Suricata flow bytes
other candidate-native byte counters
```

But this task MUST NOT accidentally define the final user-visible DTI byte basis.

The later:

```text
TrafficAccountingContract
```

will freeze the product byte basis explicitly.

TASK-DTI-00A answers:

```text
what does each candidate actually count?
can it support the required temporal/accounting behavior?
```

not:

```text
what final product byte definition must be used?
```

---

# 6. EXECUTION CLASSIFICATION — REQUIRED BEFORE EACH TEST

Every validation step MUST first be classified as exactly one of:

```text
READ_ONLY_PRODUCTION_OBSERVATION

LAB_OR_SHADOW_VALIDATION

TEMPORARY_CONTROLLED_PRODUCTION_COMPATIBILITY_TEST
```

Permanent protection:

```text
NEW PACKET CONSUMER
ON PRODUCTION enp8s0
!=
AUTOMATICALLY SAFE SHADOW TEST
```

Any new:

```text
AF_PACKET socket
libpcap capture process
Suricata instance
traffic meter
packet sniffer
```

attached to production `enp8s0` MUST be classified as:

```text
TEMPORARY_CONTROLLED_PRODUCTION_COMPATIBILITY_TEST
```

unless the validation is independently proven to occur on an isolated lab/replay path.

Before attaching any new packet consumer, document:

```text
socket/capture mode
AF_PACKET fanout usage
cluster/fanout identity where applicable
copy vs load-sharing behavior
expected interaction with existing consumers
rollback
```

An experimental consumer MUST NOT accidentally steal or redistribute packets away from accepted Fingerprint consumers.

For every step record:

```text
TEST_ID
CLASS
SYSTEM
PURPOSE
CHANGE_REQUIRED = YES / NO
OWNER_AUTH_REQUIRED = YES / NO
ROLLBACK_REQUIRED = YES / NO
```

Writing this contract does NOT authorize a production change.

---

# 7. HARD AUTHORIZATION BOUNDARY

Any step that changes any of the following requires separate explicit Owner authorization BEFORE execution:

```text
fingerprint-suricata.service
production Suricata configuration
production Suricata output families
production EVE destinations
production capture configuration
SPAN / RSPAN
NIC settings
bridge / VLAN / macvtap configuration
firewall
systemd resource limits
production service restart
```

Without that authorization:

```text
DO NOT EXECUTE
RETURN AUTHORIZATION BLOCKER
```

This task itself is not that authorization.

## 7.1 Exact pre-test identity and rollback proof

Before any Owner-authorized production Suricata compatibility test, capture the exact pre-test identity of:

```text
Suricata version
service unit identity
drop-ins
environment/config sources
main config identity/hash
included config identity/hash
existing EVE destination identity
existing output/event-family configuration
capture interface
service state
MainPID/start timestamp where useful
Fingerprint runtime/source-health state
```

Sensitive values MUST be redacted.

After rollback, prove for every intentionally changed config object:

```text
CONFIG_IDENTITY_AFTER_ROLLBACK
=
CONFIG_IDENTITY_BEFORE_TEST
```

Also prove:

```text
services active
Fingerprint runtime healthy
accepted Fingerprint outputs resumed
no unexpected restart loop
```

`ROLLBACK_STATUS = PASS` means exact-state restoration, not merely “service started again”.

---

# 8. CODER BOUNDARY

Default:

```text
CODER = HOLD
```

Sysadmin MUST NOT invent or write production DTI application code.

If the evidence shows that a temporary lab-only helper/prototype is absolutely required to compare accounting semantics:

```text
STOP
→ raise IMPLEMENTATION DEPENDENCY
→ Architect + Tech Lead review
```

The helper/prototype must not be created implicitly under sysadmin authority.

---

# 9. PHASE A — MINIMAL CURRENT-STATE CONFIRMATION

Purpose:

Confirm that the accepted DTI-00 baseline has not materially changed before admission testing.

Do NOT repeat the broad inventory.

Read-only checks only:

```text
fingerprint-sensor active?
fingerprint-suricata active?
capture interface still enp8s0?
current RSPAN still VLAN10+VLAN20 RX-only?
RSPAN destination still VLAN999?
Fingerprint runtime_state healthy?
Suricata capture health current?
new capture drop growth already present before test?
current CPU/RAM/I/O baseline?
current existing EVE output identity?
```

If a material baseline change is found:

```text
STOP ADMISSION
→ BASELINE_DRIFT
```

and report the exact change.

Do not automatically reopen all of DTI-00.

---

# 10. PHASE B — SURICATA OPTION A ADMISSION DESIGN

Before any test, document the exact proposed Option A delta.

It must be the smallest possible conceptual change:

```text
existing Fingerprint Suricata path
remains accepted owner of existing TLS/QUIC/JA4/stats path

additional DTI output
must be isolated
must be version-identifiable
must not replace existing Fingerprint output
must not change Fingerprint event semantics
must not widen Fingerprint raw BPF
```

Document:

```text
which new event families are needed for this admission test
where the DTI output would go
how it is isolated from the existing Fingerprint consumer
how rollback restores the exact pre-test state
how output growth is bounded
how privacy is bounded
```

Option A MUST preserve the existing Fingerprint-facing EVE contract.

Before test, prove:

```text
existing Fingerprint EVE destination identity
existing enabled event-family selectors
existing TLS output semantics
existing QUIC output semantics
existing stats semantics
existing Fingerprint consumer socket/path
```

During the candidate test:

```text
new DTI flow/DNS/etc. events
MUST NOT leak into the existing Fingerprint consumer stream
```

unless a separate Fingerprint compatibility contract explicitly permits them.

Expected result for the preferred isolated-output design:

```text
UNEXPECTED_DTI_EVENTS_IN_FINGERPRINT_STREAM = 0
```

Do NOT enable unrelated event families merely because Suricata supports them.

---

# 11. PHASE C — SURICATA COEXISTENCE COMPATIBILITY GATE

The test must prove that an additional DTI output does not materially degrade or alter:

```text
Fingerprint functional output
Fingerprint source-health behavior
Suricata capture health
kernel/capture drops
CPU
RAM
I/O
event latency/timing
service stability
existing TLS/QUIC Fingerprint normalization
```

## Required baseline/test/post-test windows

Use interval-based evidence.

For each window record:

```text
UTC start
UTC end
duration

fingerprint-sensor service state
fingerprint-suricata service state

Fingerprint accepted evidence counters
Fingerprint source-health/runtime state

Suricata capture packets
Suricata capture bytes/rate where available
Suricata kernel/capture drops
EVE invalid/truncated counters where available

CPU
RAM
I/O

candidate output/event count
output/event rate
output/storage growth

queue/socket health where observable
```

BEFORE / DURING / AFTER windows MUST include enough input-volume evidence to judge comparability.

If input load differs materially:

```text
DO NOT claim direct resource regression/improvement
without normalization or additional evidence.
```

One instantaneous `top`/`ps` snapshot is insufficient.

---

# 12. SURICATA COEXISTENCE FAIL CONDITIONS

Option A admission MUST fail or remain unresolved if the test causes or correlates with any of:

```text
Fingerprint functional regression
accepted TLS/QUIC/JA4 evidence loss
Fingerprint source-health regression
service crash/restart not part of the controlled procedure
new sustained capture-drop growth attributable to the test
EVE truncation/invalid growth attributable to the test
unbounded queue/output growth
material CPU/RAM/I/O pressure without a bounded policy
event-latency/timing degradation that threatens accepted Fingerprint behavior
rollback failure
```

A resource delta alone is not automatically failure.

It must be interpreted against:

```text
service stability
capture health
host headroom
bounded growth
DTI-degrades-first principle
```

---

# 13. SURICATA COEXISTENCE PASS RESULT

Option A may PASS only when evidence supports:

```text
existing Fingerprint path remains functionally unchanged
existing source-health semantics remain intact
capture health remains acceptable
no unacceptable new drop growth
resource impact is measured and bounded
output growth is measured and bounded
rollback is proven
DTI output isolation is proven
```

Then:

```text
FINGERPRINT_SURICATA_COEXISTENCE_DECISION = A
```

If A fails:

```text
DO NOT DEPLOY A
```

Then Architect/Tech Lead decide whether this same task may proceed to B/C evaluation or whether a separate bounded task is required.

---

# 14. PHASE D — ACCOUNTING SOURCE ADMISSION

The accounting source question is independent from metadata coexistence.

Do NOT infer:

```text
Suricata Option A passes coexistence
→ therefore Suricata owns traffic accounting
```

That conclusion is forbidden without accounting evidence.

The candidate accounting source must be evaluated against the future DTI product primitives.

---

# 15. REQUIRED ACCOUNTING TEST SCENARIOS

## 15.1 AccountingReferenceTruth — mandatory

A candidate traffic source MUST NOT validate itself.

For each controlled accounting scenario define:

```text
AccountingReferenceTruth
```

At minimum record:

```text
controlled test client
exact UTC interval
flow endpoints
direction
test start/end
known or independently measured traffic operation
independent endpoint/network counters where available
candidate-native counters
capture-quality state
```

The reference may be:

```text
controlled sender/receiver counters
known transfer size plus documented protocol-overhead limitations
independent bounded packet observation
another non-authoritative diagnostic source
```

depending on the property being tested.

Forbidden circular validation:

```text
Suricata says 100 MB
therefore Suricata correctly counted 100 MB
```

For temporal semantics separately prove:

```text
known event timeline
vs
candidate emission/update timeline
```

Billing-grade equality is NOT required because the final product byte basis remains intentionally unfrozen.

The purpose is to prove:

```text
counter behavior
temporal behavior
interval behavior
continuity behavior
```

against independent evidence.

## 15.2 Scenario set

The bounded validation must cover, where executable under the authorized test method:

```text
1. short completed flow

2. long-lived flow crossing multiple accounting intervals

3. idle period

4. traffic burst

5. flow already active before observation window begins

6. flow ending after observation window ends

7. Visit boundary occurring inside a continuing flow

8. capture/parser restart

9. residual exact mirrored repeat

10. network retransmission

11. partial capture / degraded CaptureQuality

12. IPv4

13. IPv6 where naturally available

14. upload

15. download
```

If a scenario cannot be executed without a new authorization:

```text
STATUS = BLOCKED_BY_AUTHORIZATION
```

Do not fake the scenario.

### Visit-boundary rule

DTI-00A evaluates:

```text
Visit-slicing CAPABILITY
```

It does NOT modify the production Visit/Auth/CAPPORT lifecycle merely to manufacture a boundary.

Preferred test:

```text
controlled long-lived flow
+
declared synthetic logical boundary T
↓
can candidate data be deterministically sliced at T?
```

Do NOT disconnect, reauthorize, reset session, force Visit closure, or manipulate CAPPORT merely to create the boundary.

### Production-disturbance minimization

For unsafe/artificial scenarios such as:

```text
parser restart
exact mirrored duplicate
network retransmission
partial capture
```

use this preferred order:

```text
1. READ_ONLY natural evidence if sufficient
2. isolated controlled lab/shadow fixture
3. temporary production compatibility test only if necessary
```

Production disturbance is NOT required when the semantic property can be proven with an isolated fixture.

Do NOT reconfigure production RSPAN to recreate the old duplication defect.

Do NOT restart production Fingerprint Suricata merely to satisfy a checklist item unless separate Owner authorization exists and the property cannot otherwise be proven.

---

# 16. CONTROLLED CLIENT

When identity-correlated traffic is required for the accounting test, use only:

```text
Owner-controlled / explicitly approved test client
```

Do not use arbitrary visitors.

This is the correct point to reopen a controlled-client trace if required by the accounting evidence.

A previous DTI-00 deferral does not prohibit using it here when the concrete gate requires it.

Before using the controlled client, record execution-time authorization:

```text
CONTROLLED_CLIENT_AUTHORIZED = YES
CURRENT_MAC =
CURRENT_IPV4 =
CURRENT_IPV6 = <if naturally present>
SITE =
UTC_CONFIRMATION =
```

Do NOT copy an old MAC/IP blindly.

Ordinary bounded client traffic is permitted only after the test plan identifies that device as the authorized test subject.

No arbitrary visitor may become an accounting ground-truth source.

---

# 17. REQUIRED CANDIDATE PROPERTIES

For every accounting candidate determine whether it can provide:

```text
bounded periodic slices
stable event identity
capture/event time basis
direction
native byte basis
packet basis where applicable
flow lifecycle
restart semantics
dedup compatibility
quality provenance
resource observability
bounded output/storage behavior
```

Each property result:

```text
PASS
PARTIAL
FAIL
UNKNOWN
NOT_APPLICABLE
```

must cite evidence.

---

# 18. PERIODIC ACCOUNTING REQUIREMENT

The candidate must be judged against:

```text
periodic observed bytes
current rate
current network activity
Visit boundary slicing
long-lived flows
upload/download
partial capture
capture restart
dedup
quality status
```

A terminal flow record may be useful for:

```text
flow lifecycle
history
protocol metadata
```

while still being insufficient for:

```text
current rate
interval accounting
accurate Visit overlap
long-lived flow slicing
```

This distinction MUST be explicit.

---

# 19. SURICATA ACCOUNTING EVALUATION

For Suricata specifically determine from actual admitted/test output:

```text
when byte/packet counters are emitted
whether intermediate/periodic state exists
what event marks flow creation/update/end
whether counters are cumulative or interval-local
whether direction is stable
what happens on parser restart
what happens to long-lived flows
what happens to a flow spanning multiple intervals
what happens when capture quality degrades
whether stable event identity exists across updates
whether duplicate mirrored frames affect native counters
whether network retransmissions affect native counters
```

Do NOT infer semantics solely from field names.

---

# 20. LIGHTWEIGHT PERIODIC METER DECISION RULE

A lightweight periodic meter becomes REQUIRED CANDIDATE if Suricata cannot safely satisfy the periodic accounting semantics.

Examples of evidence that may justify this:

```text
terminal-only flow totals
no trustworthy interval slicing
Visit boundary cannot be represented without approximation
long-lived flow cannot be accounted per interval
restart destroys required accounting continuity semantics
current rate cannot be derived with acceptable freshness
```

However:

```text
LIGHTWEIGHT_METER_REQUIRED
```

does not authorize implementation.

If proving the meter requires code/prototype work:

```text
IMPLEMENTATION_DEPENDENCY =
REQUIRED
```

and TASK-DTI-00A remains open until that dependency is separately approved and executed.

---

# 21. VALID SPLIT-OWNERSHIP OUTCOME

The following type of result is explicitly valid:

```text
PARSER_ALLOCATION_DECISION = FINAL

Fingerprint raw
→ DHCP fingerprint evidence
→ outbound TCP SYN fingerprint evidence
→ existing source health

Suricata
→ TLS/QUIC/JA4 Fingerprint path
→ DTI protocol metadata
→ DNS/TLS/QUIC metadata
→ flow lifecycle

Lightweight periodic meter
→ periodic bytes/packets
→ current rate
→ current activity
→ Visit-overlap slicing

NetFlow
→ diagnostic/cross-check only

Zeek
→ not admitted
```

But only if evidence supports that exact allocation.

---

# 22. DEDUP / RETRANSMISSION ADMISSION REQUIREMENT

The accounting-source decision must explicitly state how the candidate behaves with:

```text
residual exact mirror repeat
network retransmission
```

Required distinction:

```text
same mirrored original frame repeated by capture topology
!=
new protocol transmission/retransmission on the wire
```

Do not solve this by silently dropping all similar packets.

For every candidate record:

```text
native duplicate behavior
native retransmission behavior
whether external dedup is required
where dedup would occur
whether byte totals before/after dedup differ
quality/provenance effect
```

Final DTI accounting semantics are not frozen here, but feasibility must be proven.

---

# 23. CAPTURE QUALITY INTERACTION

For each candidate determine:

```text
what health signal proves source alive?
what signal detects capture drops?
what signal detects parser drops?
what happens when source becomes stale?
what happens when capture is partial?
can current traffic incorrectly appear as zero?
```

Required invariant:

```text
degraded / missing source
→ stale / unavailable / insufficient coverage
```

not:

```text
degraded / missing source
→ zero traffic
```

---

# 24. RESOURCE ADMISSION

Use the accepted DTI-00 resource baseline as comparison.

Measure candidate incremental cost:

```text
CPU
RAM
I/O
capture drops
event/output rate
disk growth
queue/socket pressure
service stability
```

No conclusion from one instantaneous sample.

The task must produce:

```text
RESOURCE_DEGRADATION_POLICY =
SUFFICIENTLY_BOUNDED_FOR_DTI_01
```

or:

```text
RESOURCE_DEGRADATION_POLICY =
NOT_SUFFICIENT
```

It MUST also produce:

```text
DTI01_RESOURCE_BUDGET_CANDIDATE
```

with evidence-backed candidate envelopes for at least:

```text
incremental CPU envelope
incremental RAM envelope
output/storage growth envelope
queue/socket ceiling where applicable
drop/error trigger
backpressure/degradation behavior
disk-full behavior
```

Exact enforcement values may still be frozen in DTI-01, but DTI-00A must provide enough measured evidence that DTI-01 does not invent its capacity model.

The policy must preserve:

```text
DTI pressure
→ DTI degrades first

Portal/Auth/CAPPORT/Fingerprint
→ protected
```

---

# 25. PRIVACY BOUNDARY

Accounting-source admission does not justify collecting arbitrary visitor content.

Use:

```text
headers / metadata
controlled test client where identity is required
bounded evidence windows
```

Do not publish:

```text
visitor payload
HTTP content
arbitrary visitor DNS/SNI history
credentials
cookies
authorization headers
```

If DNS/TLS metadata is enabled temporarily for coexistence evidence, retain only what is required to prove event/producer behavior and redact unrelated visitor identifiers from the final report.

---

# 26. NETFLOW — OUT OF CRITICAL PATH

Do NOT repair, reconfigure or expand NetFlow under TASK-DTI-00A.

Accepted role:

```text
NETFLOW_ROLE =
DIAGNOSTIC / CROSS-CHECK ONLY
```

No:

```text
firewall change
exporter change
collector repair
retirement change
```

is required for DTI-00A.

---

# 27. NIC / RSPAN — NO TUNING

Do NOT change:

```text
RSPAN
RX ring
NIC offloads
bridge/macvtap
VLAN transport
```

merely to improve an admission result.

The current accepted baseline remains the test substrate.

If new sustained capture misses appear only when a candidate output/consumer is introduced, record that as admission evidence.

Do not hide it by tuning during the same test.

---

# 28. OWNER AUTHORIZATION REQUEST PACKET — REQUIRED WHEN NEEDED

If the planned Option A validation requires any production delta or restart, Sysadmin MUST stop and return exactly one deliberate authorization request.

Use:

```text
DTI-00A OWNER AUTHORIZATION REQUEST

TEST_ID =
PURPOSE =

CURRENT_STATE_IDENTITY =
<config/service identities>

EXACT_TEMPORARY_DELTA =
<files/settings/output changes>

NEW_OUTPUT_DESTINATION =
EVENT_FAMILIES =
EXPECTED_DURATION =

SERVICE_RESTART_REQUIRED =
YES / NO

PRODUCTION_PACKET_PATH_CHANGE =
YES / NO

EXPECTED_FINGERPRINT_EFFECT =
NONE

MONITORING_GATES =
<exact health/resource/drop checks>

STOP_CONDITIONS =
<exact>

ROLLBACK =
<exact procedure>

ROLLBACK_IDENTITY_CHECK =
<exact>

DATA_PRIVACY_SCOPE =
<exact>

CHANGES_ALREADY_MADE =
NONE
```

Sysadmin MUST stop at this point.

Only explicit Owner approval authorizes execution.

This is intended to avoid a chain of ad-hoc production approvals.

---

# 37. EVIDENCE INDEX — REQUIRED

Every material conclusion must cite reproducible evidence IDs.

Format:

```text
A01
Host/system:
UTC timestamp:
Test class:
Command/observation:
Sanitized output:
Supports conclusion:

A02
...
```

Required evidence-linked outputs:

```text
SuricataOptionACompatibilityResult
AccountingCandidateMatrix
AccountingScenarioResults
NativeByteSemanticsMatrix
DedupRetransmissionBehavior
ResourceAdmissionResult
ParserAllocationDecision
TrafficAccountingSourceDecision
```

---

# 37. REQUIRED ACCOUNTING CANDIDATE MATRIX

Complete at minimum:

| Capability | Suricata | Lightweight meter | Final owner |
|---|---|---|---|
| Protocol metadata | | | |
| Flow lifecycle | | | |
| Periodic bytes | | | |
| Periodic packets | | | |
| Current rate | | | |
| Current activity | | | |
| Long-lived flow slicing | | | |
| Visit-boundary slicing | | | |
| Upload/download | | | |
| Restart semantics | | | |
| Stable event identity | | | |
| Dedup compatibility | | | |
| Retransmission semantics | | | |
| CaptureQuality provenance | | | |
| Resource observability | | | |

If the lightweight meter has not been implemented/tested:

```text
NOT_TESTED / IMPLEMENTATION_DEPENDENCY
```

is the only valid entry.

Do not invent capabilities.

---

# 37. REQUIRED SURICATA COEXISTENCE MATRIX

| Dimension | Before test | During candidate output | After rollback/final | Verdict |
|---|---|---|---|---|
| Fingerprint service state | | | | |
| Fingerprint runtime/source health | | | | |
| Fingerprint EVE destination identity | | | | |
| Fingerprint EVE event-family set | | | | |
| Unexpected DTI event families seen by Fingerprint consumer | | | | |
| Fingerprint normalizer rejected/ignored-event behavior | | | | |
| TLS normalization | | | | |
| QUIC normalization | | | | |
| Suricata capture packets | | | | |
| Suricata capture drops | | | | |
| EVE invalid/truncated | | | | |
| CPU | | | | |
| RAM | | | | |
| I/O | | | | |
| Event/output rate | | | | |
| Disk/output growth | | | | |
| Event latency/timing | | | | |
| Rollback | | | | |

---

# 37. REQUIRED REPORT

Return:

```text
TASK-DTI-00A-CAPTURE-CONSUMER-COEXISTENCE-AND-TRAFFIC-ACCOUNTING-SOURCE-ADMISSION-REPORT
```

Recommended structure:

```text
1. Executive Summary
2. Accepted DTI-00 Baseline Used
3. Authorization / Test Classification
4. Minimal Pre-Test Baseline Confirmation
5. Proposed Suricata Option A Delta
6. Suricata Coexistence Test
7. Fingerprint Compatibility Results
8. Resource / Capture-Health Results
9. Accounting Candidate Semantics
10. Accounting Test Scenarios
11. Native Byte Semantics Matrix
12. Dedup vs Retransmission Behavior
13. Accounting Candidate Matrix
14. Parser Allocation Decision
15. Traffic Accounting Source Decision
16. Resource Degradation Policy
17. DTI01 Resource Budget Candidate
18. Privacy / Safety Compliance
19. Evidence Index
20. Unknowns / Blockers
21. Changes Made
22. Final Verdict
```

---

# 37. REQUIRED FINAL VERDICT

Use exactly:

```text
TASK =
TASK-DTI-00A

DTI00_BASELINE_DRIFT =
NO / YES

SURICATA_OPTION_A_TESTED =
YES / NO / BLOCKED

SURICATA_OPTION_A_COMPATIBILITY =
PASS / FAIL / PARTIAL / NOT_TESTED

FINGERPRINT_FUNCTIONAL_REGRESSION =
NO / YES / UNKNOWN

FINGERPRINT_SOURCE_HEALTH_REGRESSION =
NO / YES / UNKNOWN

UNEXPECTED_DTI_EVENTS_IN_FINGERPRINT_STREAM =
0 / <number> / UNKNOWN

NEW_CAPTURE_DROP_GROWTH =
NO / YES / UNKNOWN

RESOURCE_IMPACT =
BOUNDED / UNBOUNDED / PARTIAL / UNKNOWN

FINGERPRINT_SURICATA_COEXISTENCE_DECISION =
A / B / C / UNRESOLVED

SURICATA_ACCOUNTING_SEMANTICS =
SUFFICIENT / PARTIAL / INSUFFICIENT / NOT_TESTED

LIGHTWEIGHT_METER_REQUIRED =
NO / YES / UNRESOLVED

LIGHTWEIGHT_METER_TEST_STATUS =
NOT_REQUIRED / TESTED / NOT_TESTED / IMPLEMENTATION_DEPENDENCY

TRAFFIC_ACCOUNTING_SOURCE_DECISION =
SURICATA / LIGHTWEIGHT_METER / EXPLICIT_SPLIT_OWNERSHIP / UNRESOLVED

PARSER_ALLOCATION_DECISION =
FINAL / PARTIAL / UNRESOLVED

RESOURCE_DEGRADATION_POLICY =
SUFFICIENTLY_BOUNDED_FOR_DTI_01 / NOT_SUFFICIENT / UNRESOLVED

DTI01_RESOURCE_BUDGET_CANDIDATE =
COMPLETE / PARTIAL / UNRESOLVED

OPEN_P0 =
<number>

OPEN_P1 =
<number>

AUTHORIZATION_BLOCKERS =
<exact list or NONE>

IMPLEMENTATION_DEPENDENCIES =
<exact list or NONE>

CHANGES_MADE =
<exact list or NONE>

ROLLBACK_STATUS =
NOT_APPLICABLE / PASS / FAIL / UNKNOWN

DTI_00A_VERDICT =
PASS / PARTIAL / FAIL / BLOCKED

DTI_00_PROGRAM_STATUS =
CLOSED / HOLD
```

---

# 37. PASS CONDITIONS

TASK-DTI-00A may PASS only when all are true:

```text
1. Fingerprint/Suricata coexistence topology has a final A/B/C decision.

2. Accounting source has a final:
   SURICATA
   or LIGHTWEIGHT_METER
   or EXPLICIT_SPLIT_OWNERSHIP decision.

3. Parser allocation is FINAL.

4. Native byte semantics of admitted candidate(s) are documented.

5. Periodic/current-rate/Visit-boundary capability is evidence-backed.

6. Duplicate vs retransmission behavior is explicitly accounted for.

7. CaptureQuality interaction is defined.

8. Resource degradation policy is sufficiently bounded for DTI-01.

9. No open P0/P1 prevents admission.

10. Any production test change had explicit Owner authorization and clean rollback/final-state evidence.
```

Then:

```text
DTI_00A_VERDICT = PASS
DTI_00_PROGRAM_STATUS = CLOSED
```

Only after this may Architect write the exact TASK-DTI-01 specification.

---

# 37. VALID PARTIAL / BLOCKED OUTCOMES

A truthful PARTIAL/BLOCKED result is preferable to an invented PASS.

Examples:

```text
Suricata metadata coexistence passes,
but accounting semantics are insufficient
and lightweight meter requires separate prototype approval.

Option A cannot be tested without Owner authorization.

Candidate output causes new sustained capture drops.

Visit-boundary slicing cannot be proven.

Restart semantics remain unknown.

Native byte basis is not understood.
```

In these cases:

```text
DTI_00_PROGRAM_STATUS = HOLD
DTI_01 = HOLD
```

and the report must identify the exact missing dependency.

---

# 37. NON-GOALS

Do NOT:

```text
repeat full topology inventory
repeat Cisco gateway investigation
repeat Site-binding investigation
repeat broad protocol inventory
repeat broad resource inventory
repeat RSPAN root-cause investigation
repair NetFlow
investigate PRTG
re-evaluate Zeek
change RX ring
change NIC offloads
redesign Device Fingerprint
implement DTI-01
build Device Card
freeze final user-visible byte basis
```

---

# 37. AUTHORIZATION STATE

```text
TASK-DTI-00A SYSADMIN CONTRACT =
PASS / APPROVED FOR SYSADMIN EXECUTION

TECH LEAD BOUNDED REVIEW =
DTI00A-R1..R10 INCORPORATED

DTI-00 EVIDENCE BASELINE =
FROZEN / ACCEPTED

RSPAN P1 =
CLOSED

IMPLEMENTATION =
NO

CODER =
HOLD

PRODUCTION FEATURE ACTIVATION =
NO

PRODUCTION CONFIG CHANGE =
NOT AUTHORIZED BY THIS DOCUMENT

DTI-01 =
HOLD UNTIL TASK-DTI-00A PASS

NEXT AFTER TASK-DTI-00A PASS =
ARCHITECT WRITES EXACT TASK-DTI-01
NETWORK OBSERVATION FOUNDATION
```


---

# 38. REQUIRED EXECUTION SEQUENCE

```text
Phase A
read-only baseline confirmation
        ↓
Phase B
exact Option-A test design
        ↓
if production delta/restart required:
DTI-00A OWNER AUTHORIZATION REQUEST
        ↓
Owner explicit approval
        ↓
bounded test
        ↓
rollback / exact-state validation
        ↓
accounting-source evidence
        ↓
final DTI-00A report
```

Until explicit Owner approval:

```text
NO PRODUCTION SURICATA CHANGE
NO NEW PRODUCTION PACKET CONSUMER
NO PRODUCTION RESTART
```
