# TASK-DTI-NI-00 — SURICATA METADATA SOURCE & FIELD SEMANTICS ADMISSION
## Exact Bounded Sysadmin Research / Admission Contract

**Project:** CaptivPortal  
**Program:** Device Traffic Enrichment / Device Intelligence (DTI)  
**Lane:** Network Intelligence  
**Task:** `TASK-DTI-NI-00`  
**Type:** BOUNDED SYSADMIN RESEARCH / ADMISSION  
**Architecture basis:** `DTI — NETWORK INTELLIGENCE PRIORITY ADDENDUM v0.2 FINAL / TECH LEAD ACCEPTED`  
**Status:** `DRAFT FOR TECH LEAD REVIEW`  
**Coder:** HOLD  
**Sysadmin execution:** HOLD UNTIL THIS CONTRACT IS REVIEWED  
**Production:** NO CHANGE BY THIS DOCUMENT  
**Periodic Traffic Meter:** PARKED  
**Device Card implementation:** NOT AUTHORIZED  

---

# 1. PURPOSE

TASK-DTI-NI-00 exists to admit the Suricata metadata source contract required by the new active Network Intelligence lane.

It MUST answer, with reproducible evidence:

```text
Which Suricata metadata families are safe/useful enough to admit?

What exactly does each emitted field mean?

When does the event semantically occur?

How is an event identified for replay/idempotency?

How is the event delivered, rotated, replayed and checkpointed?

How do we prove that an event belongs to the intended CaptivPortal network population?

What freshness/latency behavior is actually available?

What resource/cardinality/privacy cost does each family impose?
```

This task does NOT implement Protocol Intelligence, Service Recognition, Temporal Device Attribution, Device Card, or Transport Health product logic.

---

# 2. ACCEPTED BASELINE — REUSE, DO NOT RE-INVESTIGATE

Treat the following as accepted evidence unless Phase A detects material drift:

```text
Capture path / placement:
accepted DTI-00 baseline
pre-NAT
client MAC/private IPv4 visible
both directions visible

Production Suricata:
8.0.6
AF_PACKET / enp8s0 / workers

Existing Fingerprint-facing EVE:
unix_dgram
/run/captive-portal/fingerprint-sensor/suricata-eve.sock

Existing Fingerprint Suricata role:
TLS / QUIC / JA4 + stats

Accepted Option-A evidence:
existing production Suricata
+
separate isolated/versioned second EVE output
can coexist without observed Fingerprint regression
under the previous bounded DTI-00A admission

Accepted capture population fact:
current mirror contains more than one source network
and cannot be treated as "all events = Guest Device events"

Periodic traffic meter:
PARKED / OUT OF THIS TASK
```

Last accepted DTI-00A production Suricata config identity was:

```text
SHA256 =
28609c533bbf97c09e58d175e2b9c24effa76ac98535e03665937a9c57c6e56f
```

This hash is a baseline reference only.

Phase A MUST read-only confirm current identity before any temporary delta.

If material drift exists:

```text
STOP MUTATING WORK
→ BASELINE_DRIFT
→ report exact drift
```

Do NOT reopen broad DTI-00 topology research automatically.

---

# 3. REUSE / DO-NOT-REPEAT RULE

Do NOT re-investigate from zero:

```text
RSPAN topology
capture placement
basic enp8s0 visibility
existing Fingerprint capture topology
basic Option-A coexistence feasibility
periodic traffic-meter work
```

Research only the remaining Network Intelligence DELTA:

```text
metadata family admission
exact output transport
field semantics
delivery/replay identity
network-scope eligibility
freshness/emission behavior
resource/cardinality
privacy
rollback
later attribution prerequisites
```

---

# 4. SOURCE FAMILY POLICY

## 4.1 Mandatory first candidates

Evaluate independently:

```text
DNS
TLS
QUIC
STATS
```

## 4.2 Conditional candidate

Evaluate independently:

```text
FLOW
```

`flow` is NOT allowed to block admission of:

```text
DNS
TLS
QUIC
Service Recognition based on other admitted metadata
```

Known previous evidence already shows terminal flow output may be delayed until flow termination.

Therefore:

```text
FLOW arrival time
!=
automatically Fresh/current observation time
```

## 4.3 Outside first candidate set

Do NOT admit under NI-00:

```text
HTTP
ALERT
DHCP
```

No event family is admitted merely because installed Suricata supports it.

---

# 5. FAMILY-SPECIFIC ADMISSION PRINCIPLE

Every family receives its own verdict:

```text
DNS   = ADMIT / REJECT / CONDITIONAL / UNRESOLVED
TLS   = ADMIT / REJECT / CONDITIONAL / UNRESOLVED
QUIC  = ADMIT / REJECT / CONDITIONAL / UNRESOLVED
STATS = ADMIT / REJECT / CONDITIONAL / UNRESOLVED
FLOW  = ADMIT / REJECT / CONDITIONAL / UNRESOLVED
```

One expensive, unsuitable, delayed, or semantically weak family MUST NOT automatically fail the other independent families.

Global task PASS means:

```text
research/admission questions are answered with evidence
+
family-specific decisions are explicit
+
delivery/replay/network-scope/freshness/resource/privacy contracts are sufficiently defined for Architect + Tech Lead review
```

It does NOT mean every family must be ADMIT.

Separate output:

```text
NI_IMPLEMENTATION_READINESS =
READY_WITH_ADMITTED_SET
/
HOLD_NO_VIABLE_SET
/
HOLD_MISSING_DEPENDENCY
```

---

# 6. HARD EXECUTION BOUNDARY

TASK-DTI-NI-00 has two execution classes.

## Class A — READ-ONLY PREFLIGHT / OFFLINE RESEARCH

Allowed after contract approval without production mutation:

```text
read current service/config identities
read existing health/stats
inspect current EVE schema/examples already present
inspect Suricata version/capabilities
construct candidate configs outside production path
run configuration validation against candidate copies
perform offline replay using bounded controlled fixtures
analyze previous DTI-00A evidence
analyze resource/cardinality from already accepted evidence where sufficient
```

## Class B — TEMPORARY PRODUCTION SURICATA OUTPUT CHANGE

Any step that changes production Suricata output/configuration requires BEFORE execution:

```text
1. exact Tech Lead review of the temporary delta
2. explicit Owner authorization
```

This document itself does NOT authorize Class B.

Until both approvals exist:

```text
NO production Suricata config mutation
NO production Suricata restart
NO new permanent EVE output
NO package install
NO NIC/RSPAN/offload/ring tuning
NO periodic traffic meter
NO Device Card work
```

---

# 7. REQUIRED EXECUTION SEQUENCE

```text
PHASE A
Read-only baseline confirmation
        ↓
PHASE B
Offline schema / field / fixture research
        ↓
PHASE C
Exact candidate EVE transport + family delta design
        ↓
PHASE D
Tech Lead review of exact temporary delta
        ↓
PHASE E
Owner explicit authorization
        ↓
PHASE F
Bounded production family/admission windows
        ↓
PHASE G
Exact rollback + identity validation
        ↓
PHASE H
Evidence synthesis / family-specific verdicts
        ↓
FINAL TASK-DTI-NI-00 REPORT
```

If Phase B/C proves that production mutation is unnecessary for a required conclusion, do not mutate production merely to satisfy a checklist.

---

# 8. PHASE A — READ-ONLY BASELINE CONFIRMATION

Confirm only what is necessary to ensure accepted evidence is still applicable.

Record:

```text
Suricata version
service unit identity
MainPID / start time
NRestarts
capture interface
runmode
main config path
main config hash
included config hashes where relevant
Fingerprint EVE destination identity
Fingerprint enabled family set
Fingerprint runtime/source-health state
current capture/drop counters
current CPU/RSS baseline
current clock/UTC synchronization state sufficient for lag measurements
```

Also confirm no material drift in:

```text
existing Fingerprint-facing EVE contract
capture interface = enp8s0
basic Option-A assumptions
```

Expected:

```text
DTI_NI_00_BASELINE_DRIFT = NO
```

If YES, report exact drift and stop before mutation.

---

# 9. PHASE B — CONTROLLED / OFFLINE FIELD-SEMANTICS FIXTURES

Before production family admission, determine as much semantic truth as possible offline.

Use only:

```text
Owner-authorized controlled client evidence
or
explicit synthetic/controlled fixtures
or
previous accepted bounded evidence
```

Do NOT use arbitrary visitor activity as semantic ground truth.

## 9.1 Controlled semantic timeline

For every tested family, record independently known:

```text
fixture/test id
UTC start/end
client endpoint
peer/resolver endpoint where known
intended action
actual packet/application action where known
expected protocol family
source capture/evidence reference
```

Compare against emitted Suricata event(s).

The event source MUST NOT validate itself.

---

# 10. EXACT EVENT FIELD SEMANTICS MATRIX

Create `EventFieldSemanticMatrix`.

For every field used by future Network Intelligence, record:

```text
family
JSON path / source field name
example sanitized value
source documentation meaning if available
controlled observed meaning
nullable/optional behavior
one-event / transaction / flow cardinality
semantic timestamp relation
endpoint relation
stability across replay
privacy class
ADMIT / DO_NOT_USE / CONDITIONAL
Evidence IDs
```

Do NOT infer meaning only from field names.

---

# 11. DNS SEMANTICS — REQUIRED

Determine with controlled evidence:

```text
query vs response event relationship
whether one transaction emits one or multiple events
transaction identity where present
flow_id relationship where present
query_name field
query_type field
response/result/rcode semantics
resolver/client endpoint semantics
answer fields needed/not needed for V1
response timing / latency fields if present
whether timing can be proven as DNS transaction latency
retransmitted/repeated query behavior
late event behavior
```

The report MUST distinguish:

```text
DNS query observed
DNS response observed
DNS failure/result category
DNS latency proven
```

Do NOT claim DNS latency if source semantics do not prove it.

Raw DNS names are SensitiveNetworkMetadata.

---

# 12. TLS SEMANTICS — REQUIRED

Determine:

```text
source event identity
flow_id relationship
which endpoint is client/server where provable
SNI presence/absence semantics
TLS version semantics
ALPN semantics
certificate metadata actually emitted if any
emission timing relative to handshake
repeated TLS event behavior per flow
ECH/no-SNI behavior
late event behavior
```

Required invariant:

```text
SNI absent
!=
service absent
```

No TLS application content is admitted.

---

# 13. QUIC SEMANTICS — REQUIRED

Determine:

```text
source event identity
flow_id relationship where present
endpoint semantics
QUIC version field semantics
observable handshake metadata
emission timing
multiple event behavior
opaque/encrypted limitations
late event behavior
```

Required:

```text
opaque / unavailable metadata
→ unknown
```

not negative evidence.

---

# 14. STATS / SOURCE-HEALTH SEMANTICS — REQUIRED

Determine exact usable source-health semantics for Network Intelligence.

At minimum map the availability/meaning of:

```text
capture packets
capture/kernel drops
EVE invalid/truncated counters where available
output/write errors where available
parser/source health
process lifetime/reset semantics
stats emission interval
stats timestamp meaning
```

Important accepted precedent:

```text
Suricata process-lifetime counters may reset on restart.
```

Therefore define which deltas are comparable only within one process lifetime.

`capture_health` and `metadata_output_health` MUST remain distinct concepts.

---

# 15. FLOW — CONDITIONAL ADMISSION

Reuse previous DTI-00A flow evidence first.

Do NOT repeat production flow-only coexistence testing unless a specific unresolved delta requires it.

Determine:

```text
emission timing
terminal/current limitations
flow start/end/state semantics
flow_id stability
src/dst semantics
transport protocol semantics
app_protocol specificity/limitations
completed-flow counters role
resource/cardinality cost
freshness suitability
```

Permanent:

```text
Suricata completed-flow bytes
!=
authoritative DTI periodic Traffic metric
```

Possible outcome:

```text
FLOW = CONDITIONAL
```

for historical flow lifecycle / Tier-B Transport Health while excluded from Fresh Protocol evidence.

---

# 16. SOURCE-EVENT IDENTITY CONTRACT

DTI-NI-00 MUST produce a candidate deterministic event identity for every admitted family where source semantics permit it.

For each family define:

```text
source identity tuple
scope of uniqueness
restart behavior
rotation behavior
replay behavior
whether source identity survives replay
whether identity may collide
```

Permanent rules:

```text
same source identity + same semantic payload
→ IDEMPOTENT REPLAY
```

```text
same source identity + conflicting semantic payload
→ CONFLICT
→ reject/quarantine/quality fault
```

Forbidden:

```text
same bytes + close timestamp → same event
```

No heuristic event deduplication.

If Suricata does not provide a sufficient native identifier, a derived deterministic identity may be recommended ONLY when:

```text
the exact immutable source-field tuple is frozen
+
its replay/collision behavior is tested
+
it does not depend on timing-nearness heuristics
```

Otherwise mark:

```text
EVENT_IDENTITY = UNRESOLVED
```

and do not admit replay-safe ingest for that family yet.

---

# 17. EVENT_AT CONTRACT

For every family determine what the Suricata timestamp semantically refers to.

Possible meanings to distinguish:

```text
packet/event observation time
transaction event time
handshake observation time
flow creation/update/end time
stats emission time
```

Do not assume all EVE `timestamp` fields mean the same lifecycle point.

For each family return:

```text
EVENT_AT_SOURCE_FIELD
EVENT_AT_SEMANTIC_MEANING
EVENT_AT_FRESHNESS_SAFE = YES / NO / CONDITIONAL
```

A delayed terminal event MUST be evaluated by the semantic event time, not file-arrival time.

---

# 18. EVE DELIVERY TRANSPORT ADMISSION

DTI-NI-00 must investigate and recommend the exact isolated/versioned delivery transport for the future Network Intelligence ingester.

Candidates may include:

```text
regular JSON file
Unix socket
other mechanism already supported and safely bounded
```

Do NOT pre-admit one merely because it is easy to configure.

For each candidate evaluate:

```text
isolation from Fingerprint stream
atomic/partial write behavior
backpressure behavior
restart behavior
replay capability
rotation behavior
reader checkpoint feasibility
failure visibility
bounded disk/socket behavior
privacy/access permissions
rollback
operational simplicity
```

Required output:

```text
EVE_DELIVERY_TRANSPORT_RECOMMENDATION =
<exact mechanism or UNRESOLVED>
```

The final architecture freeze occurs after Architect + Tech Lead review of evidence.

---

# 19. ROTATION / CHECKPOINT / RESTART / PARTIAL-WRITE CONTRACT

For the recommended transport, explicitly determine:

```text
rotation trigger/behavior
old/new stream identity
reader checkpoint key
checkpoint persistence expectation
partial JSON/write behavior
truncated event behavior
source restart behavior
ingest/reader restart implication
duplicate delivery possibility
lost-event possibility
replay procedure
```

Output artifact:

```text
DeliveryReplayIdentityContractV1
```

It MUST be sufficient for later Coder work to implement idempotent ingest without inventing transport semantics.

---

# 20. CAPTURE / NETWORK SCOPE CONTRACT

`site_id` alone is insufficient.

Current mirror includes more than one source network.

NI-00 MUST prove what evidence is sufficient to identify the intended CaptivPortal/Guest network population BEFORE Device attribution.

Required concepts:

```text
capture_source_id
capture_scope_binding_version
network_scope_id
network_scope_state
```

Investigate what can be proven from admitted metadata, current accepted network facts, and endpoint scope.

The task MUST explicitly determine whether original VLAN identity is or is not available in the emitted event path.

Do not assume VLAN visibility from switch configuration alone.

Where VLAN identity is absent at the parser output, determine the exact safe V1 alternative for network-scope eligibility, for example only if proven:

```text
accepted source scope
+
admitted IPv4 network population rule
+
future temporal attribution
```

Do NOT invent this rule without evidence.

Required states:

```text
resolved_intended_population
resolved_other_population
ambiguous
unknown
```

Permanent:

```text
unknown/ambiguous network scope
→ NO Device product attribution
```

---

# 21. NETWORK-SCOPE CONTROLLED EVIDENCE

Where safely available, use controlled/known endpoints to prove separation between:

```text
intended CaptivPortal/Guest population
and
other mirrored source population
```

Do not use arbitrary visitor identity as ground truth.

At minimum return:

```text
which emitted fields support network-scope filtering
which accepted network facts are required
which cases remain ambiguous
what exact evidence NI-02 will need
```

This task does NOT implement Temporal Device Attribution.

---

# 22. ACTUAL EVENT DELIVERY LAG / FRESHNESS EVIDENCE

For each admitted candidate family measure:

```text
event semantic time
first observable output/delivery time
ingest-observation time used by the research harness
lag = observed delivery time - semantic event time
```

Use synchronized UTC clocks and record clock-health evidence.

Return distribution where sample size permits:

```text
sample count
minimum
median / p50
p95
p99 where meaningful
maximum
```

Also document known semantic outliers such as terminal flow events.

The task does NOT freeze final product freshness windows.

It produces:

```text
FreshnessPolicyCandidate
```

with measured evidence sufficient for later NI-G6 to freeze:

```text
ALLOWED_EVENT_LATENESS
CURRENT_WINDOW
RECENT_WINDOW
minimum UI polling interval
```

---

# 23. LATE-EVENT EXAMPLES

Create controlled examples where possible that prove:

```text
old semantic event
+
late output/arrival
!=
Fresh result
```

For each example record:

```text
event_at
delivery_observed_at
lag
family
why event is late
product implication
```

No historical event may masquerade as current because it was delivered now.

---

# 24. RESOURCE / CARDINALITY MEASUREMENT PLAN

Measure every candidate family independently where applicable, plus the proposed combined admitted family set.

## 24.1 Baseline window

Before family tests record a bounded baseline window with:

```text
duration
input capture packet delta
input/capture rate where available
Suricata CPU
Suricata RSS
capture/kernel drop delta
Fingerprint health
existing EVE invalid/truncated counters
```

## 24.2 Family windows

Preferred minimum bounded observation window per family:

```text
180 seconds
```

If natural event volume is insufficient, use controlled activity inside the same bounded window or mark:

```text
INSUFFICIENT_SAMPLE
```

Do not extend collection indefinitely.

## 24.3 Combined window

After individual family measurements, measure the proposed combined admitted candidate set for at least:

```text
300 seconds
```

unless Tech Lead approves another exact bounded duration.

## 24.4 Load comparability

For every baseline/family/combined window record input packet/capture volume.

If natural network load differs materially:

```text
DO NOT claim direct CPU/RSS improvement/regression
without normalization or additional evidence.
```

---

# 25. REQUIRED PER-FAMILY RESOURCE / CARDINALITY OUTPUT

For each family return where applicable:

```text
events/sec
bytes/sec
modeled bytes/day from measured bounded sample
max event size
unique flow_id rate
DNS-name cardinality
SNI cardinality
output growth
Suricata CPU delta
Suricata RSS delta
capture-drop delta
Fingerprint health delta
```

For cardinality metrics report:

```text
raw event count
unique count
measurement window
sanitization method
```

Do NOT publish visitor raw DNS/SNI values in the report.

Repeat the resource/cardinality measurement for the proposed combined family set.

---

# 26. FAMILY RESOURCE ADMISSION RULE

A family may be `ADMIT` only if:

```text
field semantics are sufficient
+
source-event identity/replay behavior is sufficient or bounded by an accepted transport contract
+
freshness semantics are fit for its intended product role
+
resource/cardinality impact is bounded
+
no unacceptable Fingerprint regression
+
no unacceptable new capture/drop regression
+
privacy boundary is acceptable
```

A family may be `CONDITIONAL` when useful only for a narrower role.

Example:

```text
FLOW = CONDITIONAL
for historical lifecycle / Tier-B health
but NOT Fresh Protocol evidence
```

---

# 27. FINGERPRINT PROTECTION GATE

Any production metadata-output test MUST preserve the accepted Fingerprint-facing contract.

Before/during/after record:

```text
Fingerprint EVE destination identity
Fingerprint EVE event-family set
unexpected DTI families visible to Fingerprint consumer
Fingerprint runtime/source health
TLS normalization progress
QUIC normalization progress
JA4 path health where observable
Suricata process state / restarts
capture/kernel drop deltas
EVE invalid/truncated counters
CPU/RSS
```

Preferred isolated-output invariant:

```text
UNEXPECTED_DTI_EVENTS_IN_FINGERPRINT_STREAM = 0
```

No Fingerprint BPF modification.

No Fingerprint consumer contract modification.

---

# 28. EXACT TEMPORARY PRODUCTION DELTA DESIGN

Before requesting authorization, Sysadmin must prepare the exact candidate plan.

For each planned variant include:

```text
TEST_ID
family/families enabled
exact candidate config identity/hash
exact changed config object(s)
exact isolated output destination
output transport
file/socket permissions
event-family selectors
expected duration
whether restart is required
expected Fingerprint effect = NONE
monitoring gates
stop conditions
rollback procedure
rollback identity verification
privacy/data scope
changes already made = NONE
```

No production test may begin until Tech Lead reviews this exact packet and Owner explicitly authorizes it.

---

# 29. OWNER AUTHORIZATION REQUEST FORMAT

Use exactly:

```text
TASK-DTI-NI-00 OWNER AUTHORIZATION REQUEST

TEST_PLAN_ID =
PURPOSE =

CURRENT_PRODUCTION_IDENTITY =
<service/config/hash/output identities>

TEMPORARY_VARIANTS =
<exact family/output variants>

EXACT_TEMPORARY_DELTA =
<exact files/settings/output changes>

EVE_OUTPUT_TRANSPORT =
OUTPUT_DESTINATION =
EVENT_FAMILIES =
TEST_DURATIONS =

SERVICE_RESTARTS_REQUIRED =
<exact count / sequence>

PRODUCTION_PACKET_PATH_CHANGE =
NO

RSPAN_NIC_OFFLOAD_RING_CHANGE =
NO

EXPECTED_FINGERPRINT_EFFECT =
NONE

MONITORING_GATES =
<exact>

STOP_CONDITIONS =
<exact>

ROLLBACK =
<exact>

ROLLBACK_IDENTITY_CHECK =
<exact>

DATA_PRIVACY_SCOPE =
<exact temporary sensitive metadata exposure and cleanup>

CHANGES_ALREADY_MADE =
NONE
```

Sysadmin stops here until explicit authorization.

---

# 30. PRIVACY / SENSITIVE METADATA EXECUTION BOUNDARY

Permanent V1 rules:

```text
NO PACKET PAYLOAD PERSISTENCE
NO HTTP CONTENT
NO DNS PAYLOAD BEYOND ADMITTED METADATA FIELDS
NO TLS APPLICATION CONTENT
NO PCAP PRODUCT STORAGE
```

Temporary NI-00 output may expose:

```text
raw DNS names
raw SNI
remote IPs
fine-grained endpoint metadata
```

These are `SensitiveNetworkMetadata`.

For temporary production evidence:

```text
restricted file/socket permissions
bounded duration
no arbitrary raw values pasted into final report
visitor values redacted or aggregated
controlled-client values may be shown only where necessary
raw temporary output removed after evidence acceptance unless separately retained by explicit decision
```

Cardinality reports should use counts/aggregates, not visitor-domain lists.

---

# 31. EXACT ROLLBACK REQUIREMENT

Before any authorized production mutation, capture:

```text
Suricata version
service unit/drop-ins
main config path/hash
included config hashes
Fingerprint EVE destination
Fingerprint family set
capture interface
service state
MainPID/start timestamp
Fingerprint runtime/source-health state
```

After test restore every intentionally changed object.

Required:

```text
CONFIG_IDENTITY_AFTER_ROLLBACK
=
CONFIG_IDENTITY_BEFORE_TEST
```

for all changed config objects.

Then prove:

```text
services active
Fingerprint runtime healthy
accepted Fingerprint output resumed
no restart loop
no candidate output remains active
no temporary raw evidence remains beyond approved retention
```

`ROLLBACK_STATUS = PASS` means exact restoration, not merely service startup.

---

# 32. DELIVERY / REPLAY TEST CASES

For the candidate delivery transport, prove or characterize:

```text
normal append/delivery
source restart
reader/consumer restart simulation
rotation
partial/truncated event handling
duplicate replay
same event delivered twice
same source identity with conflicting payload
checkpoint resume
end-of-file / socket interruption behavior
```

Where no product reader exists yet, use a bounded research harness or standard inspection mechanism only if it does not become a project/runtime dependency.

Do NOT authorize Coder product implementation merely to run NI-00.

If a new implementation dependency is genuinely required:

```text
STOP
→ IMPLEMENTATION DEPENDENCY
→ Architect + Tech Lead review
```

---

# 33. NETWORK SCOPE SOURCE CONTRACT OUTPUT

NI-00 must produce:

```text
NetworkScopeSourceContractV1
```

It must state:

```text
accepted capture_source_id
capture_scope_binding_version
what network_scope_id means
how intended Guest/CaptivPortal population is identified
what evidence is authoritative
what fields are required
what ambiguity states exist
what cannot be resolved in NI-00
what NI-02 must prove later
```

No every-event-to-Guest shortcut is allowed.

---

# 34. EXACT REMAINING TEMPORAL-ATTRIBUTION DEPENDENCY

NI-00 does NOT implement attribution.

It MUST return the exact evidence inputs needed by the later Temporal Device Attribution admission task.

At minimum:

```text
which endpoint fields are available per admitted family
whether src/dst roles are semantically stable
whether local/external scope can be identified yet
which event timestamp must be used for binding
which flow/transaction identity can correlate related observations
what network-scope state is available
what IPv4 evidence is sufficient for later Site+IP+event_at → Site+MAC research
what IPv6 evidence remains missing/optional
```

Required output:

```text
TEMPORAL_ATTRIBUTION_NEXT_DEPENDENCY =
<exact list>
```

---

# 35. REQUIRED OUTPUT ARTIFACTS

Return all of:

```text
1. SuricataMetadataSourceContractV1

2. EventFieldSemanticMatrix

3. DeliveryReplayIdentityContractV1

4. NetworkScopeSourceContractV1

5. FreshnessPolicyCandidate

6. MetadataCardinalityResourceReport

7. FamilySpecificAdmissionVerdicts

8. TemporalAttributionNextDependency

9. EvidenceIndex

10. TASK-DTI-NI-00 FINAL REPORT
```

These may be sections of one report if every contract is explicit and independently reviewable.

---

# 36. EVIDENCE INDEX

Every material conclusion cites an Evidence ID.

Format:

```text
NI00-E001
Host/system:
UTC start/end:
Execution class:
Family:
Test/observation:
Sanitized output/artifact:
Supports conclusion:
Privacy treatment:
```

No uncited semantic claim may become an admission fact.

---

# 37. REQUIRED FAMILY ADMISSION MATRIX

| Dimension | DNS | TLS | QUIC | STATS | FLOW |
|---|---|---|---|---|---|
| Field semantics proven | | | | | |
| Event identity proven | | | | | |
| event_at semantics proven | | | | | |
| Endpoint semantics proven | | | | | |
| Freshness suitability | | | | | |
| Replay/idempotency feasibility | | | | | |
| Network-scope eligibility inputs | | | | | |
| Resource bounded | | | | | |
| Cardinality bounded | | | | | |
| Privacy acceptable | | | | | |
| Fingerprint regression | | | | | |
| Capture/drop regression | | | | | |
| Final verdict | | | | | |

Allowed cell states:

```text
PASS
PARTIAL
FAIL
NOT_APPLICABLE
UNRESOLVED
```

Final family verdict:

```text
ADMIT
REJECT
CONDITIONAL
UNRESOLVED
```

---

# 38. REQUIRED RESOURCE / CARDINALITY MATRIX

For each family and combined set return:

| Metric | Baseline | DNS | TLS | QUIC | STATS | FLOW | Combined proposed set |
|---|---:|---:|---:|---:|---:|---:|---:|
| Window seconds | | | | | | | |
| Capture/input packets | | | | | | | |
| Events | | | | | | | |
| Events/sec | | | | | | | |
| Output bytes | | | | | | | |
| Bytes/sec | | | | | | | |
| Modeled bytes/day | | | | | | | |
| Max event bytes | | | | | | | |
| Unique flow IDs | | | | | | | |
| Unique DNS names | | | | | | | |
| Unique SNI values | | | | | | | |
| Suricata CPU | | | | | | | |
| Suricata RSS | | | | | | | |
| Capture-drop delta | | | | | | | |
| Fingerprint health | | | | | | | |

For non-applicable fields use `N/A`, never fabricated zero.

---

# 39. STOP CONDITIONS DURING AUTHORIZED PRODUCTION TEST

Immediately abort candidate run and rollback on any of:

```text
Fingerprint functional regression
Fingerprint source-health regression
unexpected DTI families entering Fingerprint stream
unexpected restart loop
new sustained capture-drop growth attributable to candidate
unbounded output growth
unbounded resource growth
Suricata instability
rollback uncertainty
privacy boundary violation
candidate writes outside approved path
```

Resource growth is interpreted against actual input load.

---

# 40. RESEARCH PASS CONDITIONS

`TASK-DTI-NI-00` may be research/admission PASS when:

```text
1. DNS/TLS/QUIC/STATS all have explicit family verdicts.

2. FLOW has an explicit independent verdict.

3. Exact EVE delivery transport recommendation exists.

4. Rotation/checkpoint/restart/partial-write/replay semantics are explicit.

5. Event identity behavior is explicit per admitted family.

6. event_at semantics are explicit per admitted family.

7. Field semantic matrix is evidence-backed.

8. Network-scope contract prevents all-enp8s0-events→Guest projection.

9. Actual delivery-lag evidence exists.

10. Per-family and combined resource/cardinality evidence exists.

11. Privacy treatment is accepted.

12. Exact rollback is PASS for any temporary production delta.

13. Fingerprint contract remains protected.

14. Exact next attribution dependency is documented.

15. OPEN P0 = 0.
```

A rejected family does NOT automatically prevent task PASS if its rejection is evidence-backed and independent admitted families remain usable.

---

# 41. VALID PARTIAL / BLOCKED OUTCOMES

Truthful partial outcomes are allowed.

Examples:

```text
DNS/TLS admitted, QUIC conditional due insufficient sample.

FLOW rejected for freshness/resource reasons.

Output transport replay semantics unresolved.

Network-scope identification cannot safely separate Guest from other mirrored population.

Event identity is not deterministic enough for replay-safe ingest.

Production family test requires authorization not yet granted.
```

In these cases do not fabricate admission.

---

# 42. REQUIRED FINAL VERDICT

Use exactly:

```text
TASK =
TASK-DTI-NI-00

MODE =
SYSADMIN RESEARCH / ADMISSION

DTI_NI_00_BASELINE_DRIFT =
NO / YES

EVE_DELIVERY_TRANSPORT_RECOMMENDATION =
<exact mechanism / UNRESOLVED>

DELIVERY_REPLAY_IDENTITY_CONTRACT =
PASS / PARTIAL / FAIL / UNRESOLVED

NETWORK_SCOPE_SOURCE_CONTRACT =
PASS / PARTIAL / FAIL / UNRESOLVED

EVENT_FIELD_SEMANTICS =
PASS / PARTIAL / FAIL

EVENT_AT_SEMANTICS =
PASS / PARTIAL / FAIL

FRESHNESS_POLICY_CANDIDATE =
COMPLETE / PARTIAL / UNRESOLVED

DNS_ADMISSION =
ADMIT / REJECT / CONDITIONAL / UNRESOLVED

TLS_ADMISSION =
ADMIT / REJECT / CONDITIONAL / UNRESOLVED

QUIC_ADMISSION =
ADMIT / REJECT / CONDITIONAL / UNRESOLVED

STATS_ADMISSION =
ADMIT / REJECT / CONDITIONAL / UNRESOLVED

FLOW_ADMISSION =
ADMIT / REJECT / CONDITIONAL / UNRESOLVED

FINGERPRINT_FUNCTIONAL_REGRESSION =
NO / YES / NOT_TESTED

FINGERPRINT_SOURCE_HEALTH_REGRESSION =
NO / YES / NOT_TESTED

UNEXPECTED_DTI_EVENTS_IN_FINGERPRINT_STREAM =
0 / <number> / NOT_TESTED / UNKNOWN

NEW_CAPTURE_DROP_REGRESSION =
NO / YES / NOT_TESTED / UNKNOWN

METADATA_CARDINALITY_RESOURCE_REPORT =
COMPLETE / PARTIAL / UNRESOLVED

PRIVACY_BOUNDARY =
PASS / FAIL / PARTIAL

ROLLBACK_STATUS =
NOT_APPLICABLE / PASS / FAIL / UNKNOWN

TEMPORAL_ATTRIBUTION_NEXT_DEPENDENCY =
<exact summary>

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

TASK_DTI_NI_00_VERDICT =
PASS / PARTIAL / FAIL / BLOCKED

NI_IMPLEMENTATION_READINESS =
READY_WITH_ADMITTED_SET / HOLD_NO_VIABLE_SET / HOLD_MISSING_DEPENDENCY
```

---

# 43. NON-GOALS / FORBIDDEN WORK

Do NOT:

```text
resume periodic traffic meter
optimize R2.1 meter
retest DTI-00B meter
implement Device Card
implement Protocol Summary product
implement Service Recognition product
implement Temporal Device Attribution product
build a new Registry
build a new DHCP product
install Zeek
repair NetFlow
change RSPAN
change NIC/offloads/rings
add HTTP content collection
enable alert/security lane
persist packet payload
create PCAP product storage
change Fingerprint semantics
change Auth/CAPPORT
```

---

# 44. CURRENT AUTHORIZATION STATE

```text
ARCHITECTURE v0.2 =
FINAL / TECH LEAD ACCEPTED

TASK-DTI-NI-00 CONTRACT =
DRAFT FOR TECH LEAD REVIEW

CODER =
HOLD

SYSADMIN =
HOLD UNTIL CONTRACT REVIEW

PRODUCTION =
NO CHANGE

TEMPORARY PRODUCTION SURICATA OUTPUT CHANGE =
NOT AUTHORIZED BY THIS DOCUMENT

PERIODIC TRAFFIC METER =
PARKED

DEVICE CARD IMPLEMENTATION =
NO

NEXT =
TECH LEAD REVIEW OF TASK-DTI-NI-00 CONTRACT
→ read-only Sysadmin preflight after approval
→ exact temporary delta review
→ Owner authorization
→ bounded NI-00 admission execution
```
