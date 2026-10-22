# TASK-DTI-00B — ARCHITECTURE ADDENDUM
## Mirror Duplicate Accounting + Production Meter Placement

**Project:** CaptivPortal  
**Program:** Device Traffic Enrichment / Device Intelligence (DTI)  
**Task:** TASK-DTI-00B  
**Artifact type:** SHORT ARCHITECTURE ADDENDUM  
**Status:** ARCHITECT DECISION — FOR TECH LEAD REVIEW  
**Coder:** HOLD / current prototype work complete  
**Coder rework:** NOT AUTHORIZED  
**Production:** NO CHANGE  
**Sysadmin live test:** NOT YET AUTHORIZED  
**DTI-01:** HOLD  

---

# 1. MirrorDuplicateAccountingPolicy

```text
MIRROR_DUPLICATE_ACCOUNTING_POLICY =
NO_HEURISTIC_DEDUP
+
COUNT_AMBIGUOUS_OBSERVATIONS
+
DEGRADE / QUALIFY ACCOUNTING QUALITY
```

## Frozen rules

The lightweight meter MUST NOT suppress a packet merely because it has:

```text
same bytes
same headers
same length
same 5-tuple
close timestamp
```

unless trustworthy capture/mirror provenance proves that two observations represent the same physical transmission.

Permanent distinction:

```text
MIRROR DUPLICATE
!=
NETWORK RETRANSMISSION
```

Legitimate retransmissions and legitimate repeated datagrams remain observed network traffic and MUST be counted.

If deterministic duplicate provenance exists:

```text
same physical transmission
→ multiple capture observations
```

then bounded dedup MAY occur before accounting.

Such dedup MUST retain:

```text
provenance
raw observation count
deduplicated count
quality state
bounded cache semantics
```

If duplicate risk is suspected but exact packet identity cannot be proven:

```text
DO NOT GUESS
DO NOT SILENTLY DROP
```

Instead:

```text
packet remains counted in raw observed accounting
+
AccountingQuality / CaptureQuality
records possible mirror-duplicate overcount risk
```

Therefore product/accounting output must conceptually preserve:

```text
ObservedTrafficValue
+
AccountingQuality / CaptureQuality provenance
```

and MUST NOT falsely claim exact completeness.

Zero/idle semantics remain independent:

```text
possible duplicate risk
!=
capture unavailable
!=
capture incomplete
!=
source missing
```

None of those conditions may silently become zero traffic.

---

# 2. ProductionMeterPlacementDecision

```text
PRODUCTION_METER_PLACEMENT_CANDIDATE =
DIRECT_INDEPENDENT_CONSUMER_ON_ENP8S0
```

This is the FIRST production admission candidate.

Required packet-delivery semantics:

```text
lightweight meter
→ separate direct packet consumer
→ production enp8s0
→ independent packet copy semantics
```

Forbidden:

```text
NO PACKET_FANOUT load-sharing with Fingerprint
NO shared fanout cluster that distributes packets away from existing consumers
NO Fingerprint BPF modification
NO Suricata modification
NO RSPAN modification
NO NIC/offload/ring modification for this admission
```

The candidate must receive an independent copy of observable traffic.

The accepted existing consumers remain unchanged:

```text
fingerprint-sensor
fingerprint-suricata
```

This decision authorizes ONLY the architecture candidate.

It does NOT authorize live attachment to production.

---

# 3. G26 Closure Rule

```text
G26 =
SATISFIABLE BY CONSERVATIVE SAFE HANDLING
```

Generic heuristic dedup is NOT required for PASS.

G26 is considered satisfied when all are proven:

```text
1. no unsafe suppression of ambiguous packets

2. legitimate retransmissions remain counted

3. exact dedup occurs only when trustworthy duplicate provenance exists

4. ambiguous duplicate risk is retained as
   AccountingQuality / CaptureQuality provenance

5. product totals do not claim exact completeness
   when duplicate overcount risk remains

6. zero / idle / unavailable semantics remain distinct
```

Therefore:

```text
SAFE HANDLING =
no unsafe suppression
+
explicit duplicate-risk provenance
+
quality degradation when exact duplicate identity cannot be proven
+
exact dedup only when trustworthy provenance exists
```

is sufficient to close G26.

No additional generic packet-dedup heuristic is required.

---

# 4. Linux / Live Resource Admission Rule

Production live admission does NOT require sustained 2x-baseline throughput as an absolute PASS condition.

Required PASS condition:

```text
accepted real operating region
≈ current production capture load
must be sustainable
with bounded and observable resource behavior
```

Current reference region:

```text
~19,000 packets/sec
~156.6 Mbit/sec
```

The live admission must prove at that region:

```text
packet consumer attachment works
independent packet delivery works
PACKET_STEALING = NO

Fingerprint sensor remains healthy
Fingerprint Suricata remains healthy
TLS/QUIC/JA4 path remains healthy

no new sustained capture/kernel drop growth
attributable to the meter

CPU/RAM cost is bounded
queue/backpressure behavior is observable
timing remains acceptable
clean detach / rollback works
```

Higher load, including approximately 2x baseline, is:

```text
HEADROOM / DEGRADATION CHARACTERIZATION
```

not a mandatory PASS threshold.

If overload occurs, acceptable behavior is:

```text
bounded drop / reject / backpressure
+
CaptureQuality degradation
+
explicit telemetry
```

Unacceptable behavior:

```text
unbounded memory
unbounded queue
silent lost accounting
loss without quality degradation
packet stealing
silent Fingerprint degradation
```

Exact production CPU/RAM/systemd/cgroup limits remain later DTI-01 scope.

---

# 5. Exact Remaining Sysadmin Admission Dependency

The remaining required dependency is ONE bounded, Owner-authorized live production admission test of:

```text
DIRECT_INDEPENDENT_CONSUMER_ON_ENP8S0
```

using the already-reviewed lightweight-meter prototype artifact.

The live test must prove only properties that offline testing cannot prove.

## Required live admission evidence

```text
1. prototype attaches successfully to actual Linux production capture path

2. delivery semantics are independent-copy, not fanout/load-sharing

3. PACKET_STEALING = NO

4. fingerprint-sensor remains healthy

5. fingerprint-suricata remains healthy

6. existing TLS/QUIC/JA4 Fingerprint normalization remains healthy

7. no new sustained capture/kernel drop growth attributable to meter

8. actual Linux CPU/RAM impact is bounded

9. current real baseline workload is sustainable

10. live queue/backpressure/drop behavior is observable

11. clean detach / rollback succeeds

12. real residual mirror-repeat behavior is measured and carried as quality provenance
```

Before execution, Sysadmin must receive a separate explicit Owner authorization.

Until that authorization:

```text
NO PRODUCTION PACKET ATTACHMENT
NO PRODUCTION CHANGE
NO SERVICE DEPLOYMENT
NO RSPAN CHANGE
NO NIC CHANGE
```

## Expected result

If live admission passes:

```text
PRODUCTION_METER_PLACEMENT_DECISION =
DIRECT_INDEPENDENT_CONSUMER_ON_ENP8S0 — ADMITTED

PACKET_STEALING =
NO

MIRROR_DUPLICATE_ACCOUNTING_POLICY =
ACCEPTED

G26 =
CLOSED

DTI01_RESOURCE_BUDGET_CANDIDATE =
COMPLETABLE / FINALIZABLE

TASK-DTI-00B =
PASS
```

Then the result returns to TASK-DTI-00A for final:

```text
TrafficAccountingSourceDecision
ParserAllocationDecision
ResourceDegradationPolicy
DTI-00 program closure
```

Only after DTI-00 is closed may Architect issue the exact TASK-DTI-01 specification.

---

# 6. Authorization State

```text
CODER =
HOLD / CURRENT PROTOTYPE WORK COMPLETE

CODER REWORK =
NOT AUTHORIZED

COMMIT =
NO

PUSH =
NO

PR =
NO

PRODUCTION =
NO CHANGE

SYSADMIN LIVE TEST =
NOT YET AUTHORIZED

DTI-01 =
HOLD

NEXT =
TECH LEAD REVIEW OF THIS ADDENDUM
→ exact bounded SYSADMIN live admission task
```
