# F-B2 MISSING VALUE CLOSURE — OWNER APPROVAL PROPOSAL

**From:** ARCHITECT2  
**To:** OWNER / TECHLEAD12  
**Scope:** R14 / F-B2 only  
**Repository baseline verified:**  
`main = ba58bcc83824d7a7b80a196785ab4b301862b00f`  
`tree = 7cf8abcea4f09a7fa270f52b8d34c8c221360524`

## Disposition

This document is an architecture **PROPOSAL FOR OWNER APPROVAL**.

Architect2 selection alone is NOT Owner authorization.

Until Owner approval:

```text
TASK-DEVICE-FINGERPRINT-03R2-I = HOLD
Coder code changes = NO
```

This closure changes no source-health semantics except supplying the three previously undefined SourceHealthPolicy inputs requested by TechLead12.

---

# 1. NETWORK FRESHNESS

## 1.1 Exact value

```text
network SourceHealthPolicy.freshness_timeout_ms =
NOT YET FROZEN
```

No value is selected by cadence inference.

The current admitted network emitter remains:

```text
mode = PERIODIC
nominal_interval_ms = 300000
same_state_heartbeat_required = true
```

The freshness timeout MUST be derived from retained heartbeat timing evidence.

## 1.2 Exact measurement/proof procedure

Measurement scope is each authoritative network source-health scope independently:

```text
(
    site_id,
    binding_epoch_id,
    producer_id,
    capture_source_id,
    source_kind
)
```

Only rows belonging to the admitted network SourceHealthEmitterContract and the same binding epoch may participate.

Required observation:

```text
total continuous observation = 48 hours

derivation window = first 24 hours
validation window = following 24 hours
```

For EACH network source-health scope, EACH 24-hour phase MUST contain at least:

```text
288 successfully persisted PERIODIC heartbeat events
```

with no intentional maintenance, process stop, emitter-contract cutover, binding cutover, or known operator-induced interruption inside the evaluated phase.

If this minimum is not met, the phase is not evidence for timeout derivation.

For every consecutive compatible heartbeat pair:

```text
H_i
H_(i+1)
```

with no explicit `unavailable` / `unsupported` state transition between them, compute:

```text
central_visibility_peak_ms(i)
=
H_(i+1).ingested_at
-
H_i.observed_at
```

using canonical UTC millisecond timestamps.

This quantity captures the age of the previously visible source-health heartbeat immediately before the next heartbeat becomes centrally durable, including actual scheduling and delivery delay observed by Task-01.

For the 24-hour derivation window:

```text
M =
maximum central_visibility_peak_ms
across ALL admitted network source-health scopes
```

Then derive:

```text
network_freshness_candidate_ms
=
max(
    300000,
    smallest whole-second millisecond value STRICTLY GREATER THAN M
)
```

Exact rounding:

```text
network_freshness_candidate_ms
=
max(
    300000,
    (floor(M / 1000) + 1) * 1000
)
```

The second 24-hour window is a holdout validation.

PASS requires for every evaluated scope:

```text
central_visibility_peak_ms(i)
<= network_freshness_candidate_ms
```

for the complete validation window, with:

```text
false freshness expiry before the next compatible persisted heartbeat = 0
```

If ANY validation observation exceeds the candidate:

```text
PROOF = FAIL

add the failing observation to derivation evidence
recompute by the same formula
start a NEW independent 24-hour validation window
```

No manual padding and no guessed multiplier is permitted.

## 1.3 Existing production evidence

Existing production heartbeat evidence is sufficient ONLY if retained evidence already contains a continuous period satisfying the exact 48-hour split and per-scope event-count rules above.

Repository source/tests alone are NOT timing evidence.

If such retained production evidence exists outside Git, it may be used without waiting for a new 48-hour observation.

If it does not exist, the exact network freshness value remains undefined until this proof completes.

## 1.4 Freeze rule after evidence

After successful proof, report exactly:

```text
M
derived network_freshness_candidate_ms
derivation interval
validation interval
per-scope event counts
maximum validation central_visibility_peak_ms
```

The numeric value becomes the proposed frozen:

```text
network SourceHealthPolicy.freshness_timeout_ms
```

only after evidence review and Owner approval.

---

# 2. TASK01 TIMESTAMP-SKEW CONTRACT REF

## 2.1 Proposed exact canonical string

```text
Task01TimestampSkewContract:v1:max_future_source_event_skew_seconds=120
```

## 2.2 Meaning

This string identifies the active Task-01 timestamp acceptance contract:

```text
maximum permitted future source-event skew
relative to Task-01 acceptance time
=
120 seconds
```

It is a contract-reference string, NOT a new ArtifactContent type and NOT an ArtifactContent ID.

SourceHealthPolicy field:

```text
task01_timestamp_skew_contract_ref
=
"Task01TimestampSkewContract:v1:max_future_source_event_skew_seconds=120"
```

Exact bound:

```text
120 seconds
```

Materialization/admission MUST fail if the active Task-01 implementation/configuration does not enforce this exact bound.

---

# 3. TASK01 DELAYED-EVENT CONTRACT REF

## 3.1 Proposed exact canonical string

```text
Task01DelayedEventContract:v1:max_delayed_event_age_seconds=86400
```

## 3.2 Meaning

This string identifies the active Task-01 delayed-event acceptance contract:

```text
maximum permitted delayed source-event age
=
86400 seconds
=
24 hours
```

It is a contract-reference string, NOT a new ArtifactContent type and NOT an ArtifactContent ID.

SourceHealthPolicy field:

```text
task01_delayed_event_contract_ref
=
"Task01DelayedEventContract:v1:max_delayed_event_age_seconds=86400"
```

Exact bound:

```text
86400 seconds
```

Materialization/admission MUST fail if the active Task-01 implementation/configuration does not enforce this exact bound.

---

# 4. R14 IMPACT

Disposition:

```text
R14 impact =
BOUNDED FORMAL CLOSURE ONLY
```

No architecture redesign is required.

This proposal supplies exact values/derivation for already-required SourceHealthPolicy fields.

Unchanged:

```text
network emitter cadence = 300000 ms

portal emitter cadence = 60000 ms

portal freshness timeout = 180000 ms

SourceHealthPolicy coverage semantics

Task-01 delayed-event behavior

Task-01 timestamp validation behavior

binding epochs

SourceEvaluability semantics

classification semantics

Task-04 scope

Authorization isolation
```

No new gate number is created.

The network freshness measurement is evidence required to materialize the existing F-B2 policy contract; it is not a new feature or new source-health semantic.

---

# 5. OWNER APPROVAL REQUIRED

```text
Owner approval required =
YES
```

Requested Owner decision:

```text
APPROVE

1. network freshness derivation/validation procedure exactly as written;

2. canonical timestamp-skew ref:
   Task01TimestampSkewContract:v1:max_future_source_event_skew_seconds=120

3. canonical delayed-event ref:
   Task01DelayedEventContract:v1:max_delayed_event_age_seconds=86400
```

Owner approval of this proposal does NOT by itself invent the network freshness number.

The exact numeric network freshness timeout remains HOLD until the required timing evidence passes and the resulting value is presented for evidence review / Owner acceptance.

Until that closure:

```text
TASK-DEVICE-FINGERPRINT-03R2-I = HOLD
Coder code changes = NO
```
