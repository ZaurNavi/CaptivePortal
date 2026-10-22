# CAPTIVPORTAL — PERF-IO-NI01-B / Architecture Addendum R3
## Expired-prefix guard and legacy fallback — Chief Architect ratification

**Status:** `ARCHITECT_R3_ACCEPTED_WITH_CLARIFICATIONS / READY_FOR_TECH_LEAD_TASK_REVISION`  
**Date:** 2026-10-14 (Asia/Baku)  
**Authority:** Chief Architect, CaptivPortal  
**Project:** CaptivPortal · NI-01 Performance & Disk-I/O Optimization  
**Normative parent:** `CAPTIVPORTAL-PERF-IO-NI01-ARCHITECTURE-CONTRACT-R2-FINAL-TECHLEAD-2026-10-14.md`  
**Original proposal reviewed:** `CAPTIVPORTAL-PERF-IO-NI01-B-R3-EXPIRED-PREFIX-ARCHITECTURE-PROPOSAL-2026-10-14(1).md`  
**Tech Lead's prepared hold task reviewed:** `TASK-PERF-IO-NI01-B-R3-PR210-CORRECTION-CODER-HOLD-2026-10-14(1).md`  
**Existing PR:** [#210](https://github.com/ZaurNavi/CaptivePortal/pull/210), branch `task/perf-io-ni01-b` (DRAFT / UNMERGED at review)  
**PR base:** `main@018985edaa008847b64051dc49c90914d0a60238`; source-provided tree `b73f0ed2450e24b7fe4298630999f402a980cce1`  
**Reviewed candidate:** `166a1546c96cdfc09b624b614b6b0080c425a3d3`; source-provided tree `793ffd7025b7161c4cfab193077d114c5e042422`  
**GitHub review evidence:** PR metadata confirmed DRAFT/UNMERGED at review, exact candidate HEAD, six-file diff; candidate implementation `app/network_metadata/retention.py`, focused tests inspected. The supplied tree SHAs are handoff identities; Tech Lead shall verify them independently before action.  
**Authorization:** Architecture exception only. **Coder HOLD until Tech Lead explicitly authorizes the revised implementation task; merge/deploy/activation HOLD.** Production A remains unchanged.

---

## 1. Verdict and rationale

**VERDICT: `R3_ACCEPT_FOR_IMPLEMENTATION`, subject to the exact clarifications in this ratified contract.**

Accept **B=ON / sensitive** bounded, index-ordered raw lookahead followed by **one** unchanged *legacy SQL selector* if and only if an explicitly checked `sensitive_endpoint_presence_state='expired'` row is encountered in the bounded lookahead. This is a **performance-regression guard**, not an unconditional cure for costly legacy scans.

**Explicitly approved departure from R2:** when fallback is triggered, selected eligible observations are ordered by the existing legacy `observation_id` ordering instead of R2's global oldest-first `(min(event_at,ingested_at), observation_id)`. The order is internal, not a public API promise or immutable source fact. It is acceptable only because the exact eligible predicate, 5000-item selection cap, 20-batch global budget, state transitions and transaction boundaries do not change. Do not claim identical *first 5000 IDs* in a fallback window; prove identical *eligibility* and eventual set completion for a stable finite fixture.

### Why R3 is necessary

The R2 B=ON sensitive queries use `(time < cutoff) AND state!='expired'` with indexes built on time, not state. A `LIMIT 5000` on returned rows does **not** bound the entries SQLite must examine through a large expired prefix. The supplied independent lab evidence describes approximately 1.1 million SQL VM steps for both B sensitive queries on the 100k-expired fixture versus approximately 645k for the legacy selector. These figures are **lab VM steps**, not physical IOPS or a guaranteed production speedup. The current PR #210 candidate implements the problematic query shape.

### Exact scope of ratification

- B=ON `sensitive`: **R3 raw-index lookahead + conditional legacy fallback**.
- B=ON `core`: **R2 algorithm unchanged**.
- B=OFF `sensitive` and `core`: **literal legacy selection unchanged**.
- A ingestion optimization: **not affected; production A left running unchanged**.
- All remaining retention classes: **unchanged**.

---

## 2. Normative R3 algorithm — sensitive B=ON only

Let `K=5000`, `age=cutoff[14]`. Keep the exact existing time cutoff and strict `<` comparison.

1. Issue the first indexed, **raw** query in `event_at,observation_id` order:

   ```sql
   SELECT observation_id,event_at,ingested_at,sensitive_endpoint_presence_state
   FROM network_metadata_observations
   WHERE event_at < ?
   ORDER BY event_at,observation_id
   LIMIT 5000;
   ```

2. **Stream** rows, not `fetchall()` before inspection. The returned row count is bounded by K; query plan must use `idx_nm_observations_event` for the time range and index order, with no temp sort/full identity-index scan in accepted baseline distributions. Validate every visited row's canonical observation ID, both canonical timestamps, eligibility against the corresponding branch cutoff, and presence state *before* acting on its `expired` value. A malformed visited row is an error, **never** a fallback trigger. On repeated identity across branches require identical timestamps/state.
3. On the **first verified** `expired` row: immediately close the active cursor, discard all in-memory indexed candidates, **do not run or continue the second lookahead**, and run the **exact pre-R2 legacy sensitive SELECT SQL once** (same `OR`, `state!='expired'`, `ORDER BY observation_id`, `LIMIT 5000`, same parameters). Return its selection in legacy order; no oldest-first re-sort. Do not retry or invoke the legacy SELECT a second time in the same `_select` call.
4. If the first branch reaches EOF or its K cap without expired, close its cursor **before** opening the second indexed raw query:

   ```sql
   SELECT observation_id,event_at,ingested_at,sensitive_endpoint_presence_state
   FROM network_metadata_observations
   WHERE ingested_at < ?
   ORDER BY ingested_at,observation_id
   LIMIT 5000;
   ```

   Stream, validate and short-circuit on the first verified expired row exactly as above. Never keep two active cursors open simultaneously.
5. If **neither** indexed branch encounters an expired row, all lookahead rows are eligible. Deduplicate by exact canonical observation ID, reject inconsistent duplicate tuples, select the first K by `(min(event_at,ingested_at), observation_id)`. Process-local candidate storage: at most `2K=10,000` raw rows / `10,000` distinct IDs. Return at most K IDs.
6. The fallback is **not** a recovery path for SQL errors, iterator interruption, malformed IDs/timestamps/state, suspicious contradictory values, unavailable store, or capacity pressure. Raise the existing controlled corruption/unavailable error; do not reinterpret an exception as `[]`, skip retention success conditions, or mutate checkpoint.
7. Cursor lifecycle is unconditional: close on EOF, first expired, exception and early return. The fallback SELECT itself must respect the existing B=OFF SQL and response cap; it is allowed only **once per invocation**, not once per row/batch.

**Validation boundary clarification:** do not silently weaken R2 validation for *visited indexed rows*. Canonical IDs from the fallback result should also be checked before returning, without changing its SQL, ordering or eligibility predicate. A raw legacy SELECT that does not project timestamps cannot prove the validity of every unvisited fallback row's timestamp; do **not** claim global integrity inspection by this guard. Existing DB/schema invariants and legacy error semantics remain in force. Any attempt to introduce unbounded validation scans is out of scope.

---

## 3. Proof obligations and allowed semantic relaxation

**Fast path:** if each branch's first K raw time-index entries contains no expired row, then those prefixes are also that branch's first K eligible entries. For any eligible observation absent from both prefixes, the branch corresponding to its earlier timestamp already has at least K eligible entries preceding it (with the observation-ID tie-break). It cannot belong to the global oldest K. Therefore the fast path preserves R2 top-K correctness.

**Fallback:** the existing legacy SQL selects at most K observations satisfying precisely:

```sql
(event_at < cutoff14 OR ingested_at < cutoff14)
AND sensitive_endpoint_presence_state != 'expired'
```

All selected rows are eligible for the **existing sensitive `_delete` transition**. UUID/observation-ID order may be different from oldest-first; it is still deterministic for a fixed SQLite snapshot. In a **finite, stable eligible set**, repeated successful passes remove every eligible row. Do not assert a hard completion deadline, guaranteed fairness under unlimited arrivals, or retention freshness that the fixed 20-batch budget cannot provide. The `core` 30-day and other category priorities remain the existing contract.

**Crucial performance limitation:** the **lookahead** is bounded to 5000 raw rows per branch, but the **legacy fallback SELECT's physical/VM scan cost is not bounded by K**. The fallback also adds limited preliminary SQL to the legacy cost. This R3 guard prevents the specific *state-filtered time-index read amplification* exhibited by R2; it **does not guarantee** total B=ON I/O ≤ B=OFF I/O for every workload. Qualification against legacy is still mandatory.

---

## 4. Hard freeze: invariants and prohibited changes

- SQLite V1 schema, every index/constraint, triggers, FK rules and schema signature: **unchanged**.
- WAL, `synchronous=FULL`, transactions, `BEGIN IMMEDIATE`, checkpoint, replay/identity digests, source provenance: **unchanged**.
- Sensitive TTL 14 days / core TTL 30 days / diagnostic and lineage TTL 45/90 days; strict cutoff `<`, `OR` eligibility: **unchanged**.
- `run`, `_delete`, `expire_touched_identity`, retention parent budget (`20 × ≤5000`) and category priority: **unchanged**.
- `NETWORK_METADATA_RETENTION_INDEXED_V1_ENABLED=false` by default. OFF configuration digest and semantics frozen; ON retains PR #210 digest semantics. No new flag, no runtime toggle, no Admin Settings exposure.
- No modifications to NI-02B/NI-04, Fingerprint, Portal, Auth, Suricata, source filtering, controller or any writer beyond the identified selector.
- No migration, index creation, additional SQLite datastore, persistent cursor, maintenance write or schema revision.

---

## 5. Allowed implementation file scope

**Modify only:**

1. `app/network_metadata/retention.py` — B=ON sensitive `_select` implementation only.
2. `tests/network_metadata/test_retention.py` — new R3 targeted cases **and adaptation of R2 tests whose ordering / expected SQL counts have legitimately changed under fallback**.
3. `docs/configuration.md` — document conditional order, fallback and physical-I/O limitation.

`app/network_metadata/config.py`, `models.py`, `schema.py`, `repository.py`, `service.py`, read boundaries, consumers and systemd files are strictly out of change scope. `tests/network_metadata/test_config.py` remains **read-only regression verification**. No second PR: one follow-up commit onto existing `task/perf-io-ni01-b` / PR #210. No rebase, history rewrite, uncontrolled merge or new source modifications unless Tech Lead obtains renewed architectural approval.

---

## 6. Mandatory QA matrix — amended from prepared Coder TASK

### Functional correctness

- F1: empty, 1, 5000, 5001, 20000-row *eligible, no expired-prefix* fixtures: fast result exactly global oldest-K; valid `event_at` and `ingested_at` OR cases; strict equality boundary; duplicate/overlap/ties.
- F2: `expired` at first, middle and last (index 0, 2499, 4999) **in each separate branch**. Assert true lazy consumption, that the first detected expired stops scanning, active cursor is closed, no second branch if first triggered fallback, **exactly one** literal legacy SQL SELECT, and legacy output IDs/order matching B=OFF in the same fixture.
- F3: two-branch overlap, `expired` after first K raw positions (never encountered), and divergent `event_at`/`ingested_at` ranking. Verify fast-path top-K remains correct where no expired row was examined; verify fallback when one is examined.
- F4: 100,000-expired + 5001-eligible file-backed fixture with **exact V1 schema/FKs**: correct fallback eligibility, no state-filtered R2 expensive indexed query, bounded raw lookahead + one legacy SELECT. Compare a stable fixture to B=OFF, including *selected IDs* and behavior on repeated passes.
- F5: `not_observed` counts as *eligible* under existing `state!='expired'`; do not misclassify it as fallback. Mixed states, timestamps, ties and URL-unrelated metadata do not change retention effects.
- F6: on every visited row validate ID, both timestamps and status **before** treating expired as a trigger. Corrupt visited data, SQLite error in first/second cursor or legacy fallback, interrupted iteration, invalid duplicate and bad configuration fail closed without fake `[]`, without checkpoint change or false `retention_completed`.
- F7: core B=ON byte-/AST-equivalent to PR #210; B=OFF both categories unchanged; `run`, `_delete`, `expire_touched_identity` byte-/AST-equivalent; all 20 deletion batches, transactions, FK cascades, capacity stops, health/faults/lineage/read DTO and A/B independence unchanged.

### Existing passing tests MUST be reconciled and rerun

**Important correction to prepared Tech Lead HOLD task:** Existing B tests in `tests/network_metadata/test_retention.py` assume exactly two SELECT statements and global oldest-first output. At least `test_b_strict_boundaries_mixed_presence_and_future` exercises expired states and must now expect legitimate fallback-to-legacy order. `test_b_explain_actual_queries_and_expired_heavy_prefix` assumes two R2 queries and global-oldest returned IDs; R3 intentionally changes its expired-prefix branch to one/two streamed probes plus one legacy SELECT and different ordering. It is **not valid** to leave those tests stale, nor to treat earlier 61 B PASS and 1549 integration PASS as certification of modified code.

Coder shall adjust *only affected assertions* to distinguish R3 fast vs fallback and rerun **all B-focused tests** (not merely newly added tests), plus `tests/network_metadata/test_config.py` targeted A/B semantics, and focused crash/retention/compatibility tests. Tech Lead must then rerun independently required full regression and performance/security gates on the **new exact PR head/tree**. Failed old assertions cannot be waived silently.

### Adversarial performance evidence

- P1: SQL `EXPLAIN QUERY PLAN` of both raw lookahead branches must use the existing time indexes (`idx_nm_observations_event`, `idx_nm_observations_ingested`), without temp sort or full PK index scan on admitted distributions.
- P2: measure per-branch raw rows inspected and one-time legacy fallback SQL count; separately report SQL VM steps for bounded probes **and** legacy fallback (do not omit the latter). Compare R2 PR #210, R3 guarded and B=OFF legacy on identical file-backed fixtures, expired-heavy, interleaved and no-expired, with cache conditions disclosed.
- P3: retain physical-I/O/latency/recovery evidence as **independent** release/activation gate. VM-step reduction in a synthetic query is not the same as measured HDD IOPS reduction.
- P4: if R3 still causes material B=ON regression relative to B=OFF under representative expired-heavy workloads, keep `B_ACTIVATION_HOLD`; do not merge claiming the performance defect solved. Escalate any index/schema/cursor strategy to Chief Architect as a separate request.

---

## 7. Governance, sequencing and acceptance

1. **Architecture review complete:** R3 accepted with this precise scope and limitations. It authorizes Tech Lead to issue/revise an implementation TASK; **it does not directly grant Coder GO**.
2. Tech Lead reconciles its prepared `TASK-PERF-IO-NI01-B-R3-PR210-CORRECTION-CODER-HOLD-2026-10-14` with §6 above, verifies PR/base exact SHA/tree and explicitly issues Coder authorization.
3. Coder makes focused follow-up commit to **existing** PR #210; no main merge or production operations.
4. Tech Lead performs independent source/QA/performance assessment against updated head, with mandatory required release gates. If failed, PR stays draft and B remains OFF.
5. Owner separately authorizes merge after all gates and separately controls any later production deploy/activation. Existing production A remains ON and unmodified throughout.

**Passing source/test results do not constitute automatic production admission.**

```text
DECISION=PERF-IO-NI01-B-R3
ARCHITECT_VERDICT=ACCEPTED_WITH_CLARIFICATIONS
ALGORITHM=B_ON_SENSITIVE_RAW_INDEXED_K5000_LOOKAHEAD_ELSE_SINGLE_LEGACY_FALLBACK
FALLBACK_TRIGGER=VERIFIED_EXPIRED_ROW_ONLY
FALLBACK_ORDER=LEGACY_OBSERVATION_ID_ORDER_ALLOWED
FAST_PATH_ORDER=GLOBAL_OLDEST_K_PRESERVED
B_ON_CORE=UNCHANGED
B_OFF=UNCHANGED
SCHEMA_INDEX_DURABILITY_CHANGE=NO
ADDITIONAL_FEATURE_FLAG=NO
ALLOWED_FILES=app/network_metadata/retention.py;tests/network_metadata/test_retention.py;docs/configuration.md
PR=210
PR_STATUS=DRAFT_UNMERGED_AT_REVIEW
CODER_GO=NO_UNTIL_REVISED_TECH_LEAD_TASK
MERGE=HOLD
PRODUCTION_B_ACTIVATION=HOLD_UNTIL_INDEPENDENT_PERF_AND_OWNER
PRODUCTION_A=UNCHANGED
```
