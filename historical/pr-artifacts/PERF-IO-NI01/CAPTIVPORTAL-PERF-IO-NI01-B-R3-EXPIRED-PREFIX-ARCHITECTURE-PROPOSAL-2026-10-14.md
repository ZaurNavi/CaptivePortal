# CAPTIVPORTAL — PERF-IO-NI01-B / R3 architecture addendum proposal

**Author:** Tech Lead  
**Date:** 2026-10-14  
**Status:** `ARCHITECT_REVIEW_REQUIRED` — proposed change, **NOT yet an approved amendment** to R2  
**Existing normative contract:** `CAPTIVPORTAL-PERF-IO-NI01-ARCHITECTURE-CONTRACT-R2-FINAL-TECHLEAD-2026-10-14.md`  
**Candidate PR:** [#210](https://github.com/ZaurNavi/CaptivePortal/pull/210), HEAD `166a1546c96cdfc09b624b614b6b0080c425a3d3`, tree `793ffd7025b7161c4cfab193077d114c5e042422`  
**Base main:** `018985edaa008847b64051dc49c90914d0a60238`, tree `b73f0ed2450e24b7fe4298630999f402a980cce1`

## 1. Why R3 is necessary

R2 §4.B1 requires *two* time-index scans, each `LIMIT 5000`, with SQL predicate `sensitive_endpoint_presence_state!='expired'`, and selection of the globally oldest 5000 eligible observations. The shipped PR #210 implements this accurately, but the predicate is not covered by either `idx_nm_observations_event` or `idx_nm_observations_ingested`. `LIMIT 5000` bounds returned rows, not scanned entries. An early prefix of 100,000 already-expired records can force two lengthy scans. Per Coder's file-backed evidence, sensitive SQL VM-step lower bound rises ~11×, to 1.1M; independent simplified lab evidence also observed 1.1M total steps across the two indexed branches versus 645k for the legacy observation-ID scan in a 100k-expired / 5001-eligible fixture. These are **SQLite VM steps**, not verified physical HDD IOPS.

R2 §4.B2 explicitly prohibits changing schema/indexes or the category state machine without Architecture Review. Consequently **do not implement this deviation until Architect ratification**. Owner requests to resolve this problem *before* merging PR #210.

## 2. Preferred solution: bounded raw-index lookahead + explicit legacy fallback

No new durable state, schema, index, migrations, PRAGMA changes or new feature flag.

For **B=ON and `sensitive` category**, change only candidate search. Keep the legacy `B=OFF` path unchanged. Keep **`core` B=ON** on R2's existing two index-ordered eligible queries, because it has no expired sensitive-state filter.

1. For each indexed branch (`event_at`, then `ingested_at`), issue a `SELECT observation_id,event_at,ingested_at,sensitive_endpoint_presence_state FROM network_metadata_observations WHERE <time_field> < :cutoff ORDER BY <time_field>,observation_id LIMIT 5000`. **Do not put the sensitive-presence filter in SQL.** This deliberately bounds the number of raw index entries returned/inspected by the branch at 5000, even when a large prefix has already-expired records.
2. Stream/consume rows in time/index order. If **any** row in the branch is `sensitive_endpoint_presence_state='expired'`, **stop reading immediately**, close the cursor and discard B candidates; execute the **existing, unmodified legacy sensitive selection** once (`WHERE (event_at<? OR ingested_at<?) AND sensitive_endpoint_presence_state!='expired' ORDER BY observation_id LIMIT 5000`). Return those IDs. This is a performance/cost circuit breaker, **not** a recovery for SQL errors or malformed data. It may conservatively fallback on even one expired row.
3. If neither branch encounters an expired row, all returned rows are eligible. Validate canonical full `observation_id`, timestamps, cutoff and consistent duplicates as already done by PR #210. De-duplicate and select the earliest 5000 by `(min(event_at,ingested_at), observation_id)`. The combined returned-row bound remains ≤ 10,000, deletion ≤ 5,000, with the original global 20-batch-per-pass budget unchanged.
4. **Never** fallback on `sqlite3.Error`, interrupted query, invalid timestamp, invalid identity, unexpected/contradictory stored value, capacity stop, or integrity error: preserve fail-closed behavior. Fallback is allowed **only** after explicit verified `expired` state in the raw indexed prefix. Do not swallow exceptions or report false success.
5. `B=OFF`: the existing legacy query/path is byte-equivalent; `A` unaffected. `B=ON` but fallback: eligible selection is legacy-ordered instead of globally-oldest. This is the **single intentional R2 algorithmic relaxation requiring Architect approval**; it preserves strict TTL predicate, bounded number of deleted IDs per transaction, retention category priority, eventual cleanup and source/replay invariants.

### Correctness sketch

Under the fast path, each branch returns its first ≤5000 raw rows and **none is expired**. If the branch has ≥5000 older rows, it therefore contains the earliest 5000 eligible rows for that timestamp ordering; if it has fewer, it contains all rows for that range. For any eligible row outside the union of both branch results, the branch corresponding to its minimum timestamp already has ≥5000 eligible predecessors (ordering ties by `observation_id`). Thus it cannot belong to the global earliest 5000. On the fallback path, the existing legacy selection is used verbatim, so strict 14-day sensitive eligibility and eventual cleanup are preserved (though selection order differs). `core` remains R2.

### Honest bounds

- On `sensitive` fast path: max 5000 inspected raw rows per time branch, max 10,000 combined returned, max 5000 deletion IDs.
- On `sensitive` fallback: index lookahead terminates at the **first expired** row (worst case ≤5000 rows of the triggering branch; potentially one fully read preceding branch). The ensuing **legacy query retains its own unbounded scan cost**, so this is **regression avoidance**, not a proof of bounded physical I/O for the entire retention pass.
- No added write-amplification from two new indexes. This does **not** claim to solve the entire underlying cost of legacy sensitive retention on extremely old databases. True indexed search among nonexpired rows would require separate Architecture Review of partial/composite indexes, index maintenance I/O, schema versioning/migrations, and HDD economics.

## 3. Safety contracts, unchanged

- 14d sensitive / 30d core / 45d health+faults / 90d generations+bindings+runs; exact `<` cutoff, event/ingested `OR` eligibility.
- `expire_touched_identity`, `_delete`, `run`, cap `RETENTION_MAX_BATCHES_PER_PASS=20`, batch size 5000, transaction/rollback/foreign-key cascades, global capacity stop and telemetry unchanged.
- `network_metadata_checkpoint`, `source_records` digest / replay, source-generation lineage, `BEGIN IMMEDIATE`, WAL, `synchronous=FULL`, schema/index signatures unchanged.
- `NETWORK_METADATA_RETENTION_INDEXED_V1_ENABLED` remains independent and default OFF. B=OFF digest exactly unchanged; B=ON digest remains tagged. No new flag.
- No production tests, no synthetic data on production, no production config/restart/deploy until separate Owner decision.

## 4. Minimum R3 acceptance matrix

1. **Exact fixture parity:** B=OFF legacy and B=ON sensitive-fast select strictly eligible items at 14d; B=ON fast chooses globally-oldest when both branches are free of expired entries. Ties/OR/unique full IDs and 0/1/5000/5001/20000 eligible rows.
2. **Fallback cases:** expired in first row, middle, and 5000th raw row of `event_at` and of `ingested_at` branch; overlap/ties; 100,000 expired + 5001 eligible tail. Verify earliest detection short-circuits, cursor closed, old **unmodified** legacy selector invoked at most once, and no duplicate deletions.
3. **Fail-closed:** corrupted timestamp/ID, contradictory duplicates, SQL error in either branch or fallback, interrupted iteration/transaction, open failure — no fake empty selection, no checkpoint advancement, no retention-success telemetry.
4. **Regression:** core R2 path unchanged; other 5 categories untouched; four A/B combinations, source lineage and replay, capacity stop, 20×5000 budget, foreign keys and durability.
5. **Adversarial performance:** independent lab file-backed SQLite, exact DDL/index signatures, fresh vs large-expired-prefix vs interleaved distributions; per-branch `EXPLAIN`, progress VM steps, elapsed distributions and physical read bytes/ops where available. Compare B=ON guarded / original PR #210 B / legacy with comparable warm/cold cache conditions; report provenance. **Never infer physical HDD IOPS from SQL VM steps alone.**
6. **Release:** only after Architect approves this addendum: targeted new/changed B tests by Coder; Tech Lead runs independent regression and performance gate; PR review then Owner merges. B remains default OFF and production activation stays separate.

## 5. Decision requested from Chief Architect

Approve or reject **R3 bounded sensitive raw-index lookahead with legacy fallback**, specifically the conditional relaxation from R2 globally-oldest order to legacy ordering when `expired` is encountered. Confirm no schema change and scope limited to `app/network_metadata/retention.py`, `tests/network_metadata/test_retention.py`, `docs/configuration.md` (plus narrowly necessary test documentation), with the same feature flag. If rejected, provide a single explicit replacement architecture contract; **Coder remains HOLD** and PR #210 stays draft/unmerged.

**PROPOSED VERDICT:** `R3_ACCEPT_FOR_IMPLEMENTATION` — *not valid until Chief Architect ratifies.*
