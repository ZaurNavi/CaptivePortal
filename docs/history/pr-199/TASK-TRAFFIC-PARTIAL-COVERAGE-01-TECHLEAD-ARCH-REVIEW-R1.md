# TASK-TRAFFIC-PARTIAL-COVERAGE-01 — TECH LEAD ARCHITECTURE REVIEW R1

**From:** CaptivPortal Technical Lead  
**To:** CaptivPortal Architect  
**Reviewed source:** `TASK-TRAFFIC-PARTIAL-COVERAGE-01-ARCHITECTURE-CONTRACT-v1(2).md`  
**Baseline:** `main@e8061de9fbd6da8be5cd269779070a4db4d59d64`  
**Tree:** `d5503fe1f2b5774bbe55cb2d34dba63246f56f6f`  
**Review date:** 2026-10-11

## Verdict

```text
CORE ARCHITECTURE = ACCEPTED IN PRINCIPLE
SELECTED OPTION = 3 / COMBINATION
OWNER ZERO-CONTRIBUTION PROPOSAL = ACCEPT WITH LIMITS

NEW COLLECTOR / NEW DB / SCHEMA CHANGE = NOT REQUIRED

TECH LEAD IMPLEMENTATION READINESS = HOLD
OPEN P0 = 0
OPEN P1 = 4
OPEN P2 = 1

CODER TASK = NOT ISSUED
CODER = HOLD
PRODUCTION = NO CHANGE
```

The combination is appropriate: confirmed, temporally aligned Offline APs are
excluded from the live *online population*, while other missing measurements
remain visibly partial. Do not synthesize numeric zeros, mix Wired and LAN,
change Observation/Projection writers, or alter strict legacy metrics.

The following items are **narrow corrections** to the same architecture, not a
request for redesign. Please issue `ARCHITECTURE-CONTRACT-v1-R1` with explicit
replace/add paragraphs and revised fixtures; preserve the rest unchanged.

## P1-01 — Unknown historical overlay presence has no valid DTO encoding

**Locations:** §§17, 18, 19, 24–25, T17–T19.

The example JSON types `partial_coverage.has_partial_measurements` as `false`
(a boolean). But §17 says that after an overlay failure/capacity exhaustion it
must be `unknown/not asserted`, without freezing a wire-level JSON value.

**Required correction:**
1. Freeze the exact JSON representation for true, false **and unknown**:
   e.g. `boolean | null`, or a named closed enum. No unspecified strings and
   no silently substituting false on error.
2. Freeze the same representation for `source_coverage_insufficient`.
3. Freeze `comparison_allowed`, `ap_share_allowed`, reason/status fields, and
   the presence/absence of numeric partial buckets for every failure status.
4. Add exact JSON assertions to T17/T18 and a `source_coverage_insufficient`
   fixture.

**Why blocking:** otherwise Coder must invent API behavior; `false` can
incorrectly imply that there were no partial cycles.

## P1-02 — Historical overlay numeric sample admission and denominator

**Locations:** §§14–15, T05, T11, T20.

§14 admits a structurally valid `partial` cycle even when every rate is
`source_unavailable`. §15 then describes an overlay bucket as
`partial_measured` and specifies directional arithmetic means, but does not
define behavior for a cycle with *zero valid measurements*, or for cycles
where only one direction is valid.

**Required correction:**
1. Freeze when a structurally admissible cycle becomes an actual **numeric
   overlay sample**: pair-required vs independent directional evidence.
2. For no valid selected-source directions/pairs, specify whether an
   evidence-only bucket is returned, its exact status, null numeric values,
   counts and safe UI representation. **It may never become 0 Mbps.**
3. If download and upload availability differ between samples, define the
   exact denominators for each mean and when `total_mbps` is allowed to be
   non-null. Avoid synthesizing a combined value with no coherent
   supporting samples.
4. Freeze the exact `coverage_ratio` formula and `measured_sample_count`
   meaning when bucket populations vary and some samples have no valid
   measured pair.
5. Add fixtures for: all directions unavailable; download-only;
   upload-only; different-valid-direction samples; varying observed AP count.

**Why blocking:** no numeric or averaging rule may be left for Coder to invent.

## P1-03 — Historical UI and strict statistics when overlay health is unknown

**Locations:** §§16–17, 19, 24–25, 28; T17/T18.

§17 correctly says `comparison_allowed=false` and `ap_share_allowed=false`
when overlay fails or is capacity-limited. But the historical UI text in
§§24–25 is specified only when partial overlay **exists**. It does not freeze
what the UI may claim for Average and Peak when partial coverage **may exist
but cannot be checked**.

**Required correction:**
1. For each `unavailable`, `capacity_limited`, and
   `source_coverage_insufficient` outcome, freeze exact UI quality message
   and Average/Peak labels or suppression.
2. A strict Average/Peak can remain accessible as a *complete-coverage-only*
   statistic if its own strict source remains sound, but it must **not** be
   presented as a proven whole-period statistic when partial coverage status
   is unknown.
3. Freeze the allowed state and numeric fields for comparison and AP share
   in each failure branch.
4. Add visible-result assertions to T17/T18 and the retention/coverage test.

**Why blocking:** without this, outage of the overlay could make the UI
overclaim completeness precisely when evidence is missing.

## P1-04 — Test T15 requires a reason absent from the closed enum

**Locations:** §11.1 and T15.

T15 requires a reason that identifies a **status/measurement conflict**, but
§11.1's closed `coverage_reasons` enum does not include a named
status/measurement-conflict reason.

**Required correction:** either admit an exact
`status_measurement_conflict` enum value, or explicitly freeze the exact
combination of existing enum values that represents T15. Update T15 to
assert that precise wire value/composition. Do not leave a new string to
Coder discretion.

## P2-01 — Precedence for fully measured partial source cycles

**Locations:** §§0.1, 4.3 and 9.2.

§4.3 says all installed/**observed** APs measured means a complete installed
result, while §9.2 permits `complete_installed` only with aligned matched
Current State or a legacy source cycle `complete=1/result=success`.

Specify one outcome for:

```text
Observation result=partial (e.g. radios endpoint failure)
all AP Wired/LAN rates fully valid
Current State evidence unavailable
```

Is it `partial_measured` until the installed population is proven, as §9.2
seems to imply? If so, make that precedence explicit in §4.3 to avoid
Coder interpreting “observed” as “installed”.

## Acceptance of corrected contract

An updated version may be accepted without another broad architecture round
when it:

- answers P1-01 ... P1-04 and P2-01 precisely;
- freezes exact wire values and deterministic test outcomes;
- preserves all other v1 decisions;
- retains no DB migration, no new collector, no new Omada requests;
- retains feature default OFF and independent Owner approval for code/merge/
  activation and any required production restart.

After that, Technical Lead will issue a bounded implementation task
for Coder. Until then: `CODER=HOLD`, `PRODUCTION=NO CHANGE`.
