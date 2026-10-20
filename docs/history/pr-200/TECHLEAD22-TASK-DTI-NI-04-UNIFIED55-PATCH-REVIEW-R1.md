# TECHLEAD22 — TASK-DTI-NI-04-UNIFIED55 — PATCH REVIEW R1

**Date:** 2026-10-12, Asia/Baku  
**Role:** Technical Lead / source and contract review  
**Reviewed:** `TASK-DTI-NI-04-UNIFIED55.patch`, `NI04-UNIFIED55-HANDOFF.md`  
**Base:** `22cdde5d4168de02d142c840028a4d66167e47f7` / tree `a783d1cb3b2f33107ba64878ae5d3d8b80463f38` (base claimed by handoff; baseline files cross-checked against GitHub where needed)  
**Patch SHA-256 (independently recalculated):** `228f1e2c5ffda1b543450562704919efd186abc54d96387c5cea84054a3d46b2`  
**Review disposition:** **BOUNDED WHITESPACE EXCEPTION ACCEPTED; IMPLEMENTATION CANDIDATE REPAIR REQUIRED (OPEN P1=2).**  
**Commit / Push / PR / Merge / Deploy / Production:** NOT AUTHORIZED by this review.

## 1. Bounded whitespace disposition — ACCEPTED EXCEPTION

The complete supplied replacement patch has exactly three newly added lines with trailing spaces, all in:

`docs/network-service-recognition/lane-a-evidence-pack-v1.md`: lines **4, 5, 6**.

Each uses exactly two trailing ASCII spaces for an intentional Markdown hard line break. Extracted file SHA-256 = `5b57eedbe0dd60194e25d22f18e9701102f7893cf443649de2b406a0b1ef540a`; it is byte-identical to the separately supplied Lane A R3 evidence file. No other added line in the supplied patch has trailing spaces/tabs.

**Decision:** preserve these three evidence lines byte-identically. Coder must report the native full candidate `git diff --cached --check` as **FAIL with this exact bounded exception**, never as unqualified PASS. A separate whitelist audit must prove the complete failure set is exactly `(path, 4), (path, 5), (path, 6)` with precisely two spaces each; any other whitespace failure is a stop. Do not globally disable whitespace checks, modify core.whitespace, or silently normalize this evidence artifact.

The whitespace HOLD itself is **CLOSED**. This does **not** imply general candidate acceptance.

## 2. Independent source review — P1 findings

### P1-01 — Incomplete retained NI-01 ↔ NI-02B source-device endpoint reconciliation

**Locations:**

- `app/network_metadata_projection/recognition_read_service.py`: `RecognitionProjectionEdgeFactV1` and `read_service_recognition_snapshot()`; includes only peer endpoint, not the source device endpoint.
- `app/network_service_recognition/read_service.py`: lines 78–94; when NI-01 `sensitive_endpoint_presence_state == 'observed_retained'`, checks `(dst_ip, dst_port, transport_protocol)` against projected peer endpoint, but never compares `(src_ip, src_port)` against the **projected authoritative device endpoint**.
- `tests/network_service_recognition/test_summary.py`: `test_exact_cross_store_provenance()` covers other fields but not an NI-01 source/device-endpoint mismatch.

**Risk:** A source/projection disagreement about the **device/source endpoint** is not rejected before a direct SNI is attributed to the selected Device. Although NI-02B supplies authoritative Site+Device identity, the contract additionally requires complete cross-store provenance for the source observation. Matching only the peer endpoint leaves one half of the retained endpoint tuple unchecked.

**Required bounded repair:** Extend the NI-02B **read-only recognition fact DTO** with the source-side device endpoint fields from the existing NI-02B schema (no schema/writer change). Before any positive recognition, verify both endpoint sides of a retained NI-01 source record agree with the NI-02B fact, including source IP/port and peer IP/port/transport. Preserve event-time Site+Device and `device_endpoint_role='src'`; reject the **whole read**, not one fact, on mismatch. For NI-01 legitimately `expired` endpoints, follow the already-frozen coverage/expiry behavior; do not invent a fallback or require an unauthorized schema change.

**Mandatory negative test:** take an otherwise-valid authoritative outbound external fact with matching retained TLS SNI and peer endpoint, mutate only the NI-01 retained `src_ip` (and separately `src_port`) to disagree with the projected device endpoint. Expected: **source_unavailable / no Service result**. Add a positive exact-source+peer endpoint case and a multi-fact all-or-nothing case.

### P1-02 — Auto-refresh cadence bypass via hide/show / IntersectionObserver

**Location:** added NI-04 coordinator in `app/admin_web/static/admin.js`, `visibilitychange` and `IntersectionObserver` handlers.

**Observed logic:** on every visibility return or positive intersection event the code calls `refresh(false)` immediately, without checking elapsed time since the last NI-04 read. Repeated quick hide/show or scroll away/back can issue automatic GETs far more frequently than the architecture's **120-second normal interval**; this matters because each read may touch two upstream SQLite stores. The Node test checks one visibility return but not return before 120 seconds.

**Required bounded repair:** distinguish first-visible request and manually requested Refresh (immediate subject to single in-flight gate) from subsequent automatic requests. On a visibility return, if >=120 seconds elapsed since the latest automatic/read cadence anchor, refresh immediately; otherwise schedule exactly the remaining time. Avoid duplicate timers and preserve cancellation/in-flight/manual coalescing. Add deterministic Node tests for hide/show after e.g. 5s (no immediate request), after >=120s (immediate), and repeated intersection notifications (no request storm). Maintain existing 120/300/600 backoff for failures; no aggressive retry via visibility state changes.

## 3. Verified facts / review limits

- Patch file SHA-256 independently verified.
- Exactly 37 paths declared by the patch: 27 new / 10 modified; additive integration is consistent with handoff inventory.
- Exact extracted Lane A runtime JSON raw SHA-256 verified against the supplied R3 identities: taxonomy `58ff1a1e49cf07229f0247bbeeca6db79acc99b6cd19437aa6245a1ab5c8cfc0`; manifest `6f1617441b8ce20aed6d91056a685c9efa444b04cfe79e42f57e7db0091d57a0`; ruleset `e6493f24b802a21e34fcbc436f2e7b150172d3bab3e04db7cb4c7005466c94c1`.
- All 3 semantic artifact SHA-256 digests independently recomputed and PASS.
- Corrected 55-service registry SHA-256 `70893ee3ec5ccd283c9bccce7948a5d914d8ad3a8f5ca81785a1654a9cbf79c7` independently verified. Catalog entries are not admitted rules; the active candidate remains the original 5 exact SNI rules.
- 18 new/extracted Python source files compiled in-memory without syntax errors.
- **Coder-reported** 209 focused tests PASS on Windows; not independently rerun against a full checked-out candidate in this Tech Lead sandbox.
- Native Linux, full official gates, real writer/reader coexistence, performance/RSS, differential Portal/Auth/CAPPORT, NI-03 compatibility and browser accessibility all still **PENDING**.

## 4. Exact Coder directive

1. Whitespace blocker is CLOSED with an exact 3-line evidence exception as above.
2. **Coder may continue only bounded local repairs P1-01 and P1-02 in existing `feature/dti-ni-04-unified55` worktree.** No new service rule, taxonomy/category change, new source, store or broad architecture redesign.
3. Produce a replacement **complete patch**, not a delta-only patch; include its SHA-256 and external-index candidate TREE.
4. Re-run all previously green focused tests plus mandatory new negatives; run compile and JS syntax; show full-candidate diff check **FAIL only for approved 3 lines**, with exact whitelist proof.
5. Handoff exact modified-file inventory and tests; leave baseline and old evidence bytes unchanged.
6. **No commit, push, PR, merge, deployment, feature activation or production action** on this review authority. After bounded repair, return the new complete patch to Tech Lead for source re-review; then schedule separate Linux/official acceptance gates under Owner decision.

## 5. Final verdict

```text
WHITESPACE_EXACT_THREE_LINE_EXCEPTION = APPROVED
WHITESPACE_BLOCKER = CLOSED
SOURCE_REVIEW = REPAIR_REQUIRED
OPEN_P0 = 0
OPEN_P1 = 2
CURRENT_PATCH_ACCEPTED = NO
CODER_LOCAL_BOUNDED_REPAIR = AUTHORIZED
CODER_PUBLICATION = HOLD
LAB_FULL_ACCEPTANCE = PENDING
MERGE = HOLD
PRODUCTION = NO_CHANGE
```
