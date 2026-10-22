# PERF-IO-NI01-B — NI-01 retention indexed-selection optimization
## TECH LEAD IMPLEMENTATION TASK v1 — SEPARATE CODER PACKAGE

**Project:** CaptivPortal / `ZaurNavi/CaptivePortal`  
**Issued:** 2026-10-14 / Tech Lead  
**Decision:** **IMPLEMENTATION SPECIFICATION READY / CODER START QUEUED**. Do not modify B source files until A is separately reviewed/merged and Tech Lead supplies the *new exact B base HEAD/TREE*; **B implementation is authorized only after that baseline handoff**. No B production activation authority.  
**Architecture:** `CAPTIVPORTAL-PERF-IO-NI01-ARCHITECTURE-CONTRACT-R2-FINAL-TECHLEAD-2026-10-14.md`, §§1–2, 4–8, 10, normative and superseding R1.  
**Priority:** P1, but retention activation is independently gated by an expired-heavy adversarial-performance case.

## 0. Pinned source / branch sequencing

The Tech Lead-verified research-to-current source inventory is:

```text
RESEARCH_HEAD=3b5f70cec467939995fecc7667169239000b7308
RESEARCH_TREE=5d52a536adffe55475ec9dd9d4b3e2d7ea8eeb2b
CURRENT_MAIN_AT_TASK_AUTHORING=27087766d3f2e104a44da3f36aa6e72a082b12de
CURRENT_TREE_AT_TASK_AUTHORING=3fe941f1962e6df72d102ba36da60bf25f3bd70a
B_BASE_HEAD=TO_BE_REPINNED_AFTER_A_REVIEW_AND_MERGE
B_BASE_TREE=TO_BE_REPINNED_AFTER_A_REVIEW_AND_MERGE
```

Reason: A and B both legitimately update `app/network_metadata/config.py` and `models.py`; two simultaneously edited branches introduce avoidable code/merge/retest friction. **B is a separately reviewable PR**, not a commit on A's branch. After A merges, Tech Lead repins and approves B base; Coder verifies exact HEAD/TREE and a clean separate worktree. If architecture-sensitive source changed unexpectedly, HOLD and report drift. No Coder test reruns for A.

## 1. Purpose / immutable invariants

Replace the potentially expensive `ORDER BY observation_id LIMIT 5000` scan used by **only** `sensitive`/`core` retention with **two independently bounded, index-order SELECTs**, deduplicate and choose globally oldest eligible observations. Use **existing** indexes; no new schema objects.

**Independent strict deployment flag:**

```text
NETWORK_METADATA_RETENTION_INDEXED_V1_ENABLED=false  # unset/default OFF
```

A and B are independent. After B implementation, the four configurations OFF/OFF, ON/OFF, OFF/ON, ON/ON must all parse and behave correctly. Preserve original NI-01 durable observations, TTL eligibility, FK cascade, replay identity, source checkpoint, generation, fault/health categories, strict SQLite schema V1, WAL/FULL/FK, no leakage to NI-02B/NI-04, no product/API/Portal changes.

**Important:** This algorithm is approved as a design. Successful correctness tests or `EXPLAIN` plans do **not** approve B production activation. When an early index prefix contains many already-expired sensitive rows, a `LIMIT 5000` returned rows does **not** cap index entries/pages read. The adversarial performance check is a real release gate; B remains OFF if that risk is not acceptable.

## 2. Closed implementation file scope

Only:

```text
app/network_metadata/retention.py
app/network_metadata/config.py
app/network_metadata/models.py
```

Allowed targeted tests (only test B behavior):

```text
tests/network_metadata/test_retention.py
tests/network_metadata/test_config.py
tests/network_metadata/test_repository.py
tests/network_metadata/test_checkpoint_crash.py
tests/network_metadata/test_capacity.py
tests/network_metadata/test_health.py
```

Allowed documentation: `docs/configuration.md`; optionally `.env.example` for strict default-OFF declaration only.

Explicitly forbidden: `app/network_metadata/schema.py`, `repository.py`, `service.py`, `normalizer.py`, `scope.py`, `read_service.py`, `projection_source.py`, any `app/network_metadata_projection/**`, NI-04, Device Fingerprint, `run.py`, `app/settings.py`, Admin, CAPPORT, Omada, systemd, schema/index/migration and any production DB mutation. Any new dependency/scope requirement → STOP, Tech Lead/Architect return; no lateral workaround.

## 3. Exact B SQL selection, sensitive/core only

In `RetentionPolicy._select(kind, cutoff)`, when B=ON and `kind in {"sensitive", "core"}`, execute **exactly two indexed time-order branches**, each restricted by the original strict eligibility, not `AND` replacing `OR`. The SQL branch shape is:

```sql
-- Branch 1:
SELECT observation_id, event_at, ingested_at
FROM network_metadata_observations
WHERE event_at < :cutoff
  -- sensitive only: AND sensitive_endpoint_presence_state!='expired'
ORDER BY event_at, observation_id LIMIT 5000;

-- Branch 2:
SELECT observation_id, event_at, ingested_at
FROM network_metadata_observations
WHERE ingested_at < :cutoff
  -- sensitive only: AND sensitive_endpoint_presence_state!='expired'
ORDER BY ingested_at, observation_id LIMIT 5000;
```

`cutoff = now - 14 days` for sensitive; `now - 30 days` for core. **Strict `<`, never `<=`.** For both branches, sensitive adds the same `!= 'expired'` state filter, core has no such extra predicate. No `UNION DISTINCT`, CTE with unrestricted sort, per-candidate read, temporary durable table, extra index or cross-run cursor.

- Fetch at most `5000 + 5000 = 10000` rows; deduplicate by the **full canonical `observation_id`** (not truncated/prefix/hash), retaining the tuple with matching timestamps.
- For every eligible unique row compare **validated canonical** timestamps `event_at` and `ingested_at`; sort by `(min(event_at, ingested_at), observation_id)` and select **at most 5000** IDs; do not depend on unordered row sequence.
- Feed selected IDs into the **unchanged** `_delete(kind, ids)` in the **existing transaction**.
- The old order by `observation_id` may intentionally change to oldest eligible first. All *eligible observations* must eventually be processed under the original bounded best-effort pass rules; no earlier expiration and no artificially “complete” status.

**Why two 5000-limited branches suffice for global oldest 5000:** if a candidate's smaller age timestamp is in branch `event_at`, any candidate that outranks it by `(min timestamp, observation_id)` also belongs to an earlier-or-tied prefix in one of the branches. Any globally top-5000 candidate necessarily survives at least one branch's top-5000 selection. Prove this with deterministic test data, ties and both timestamp orderings; do not merely rely on this explanation as a test.

All other retention classes (`health`, `faults`, `generations`, `bindings`, `runs`) and `expire_touched_identity` stay unchanged. Preserve 14/30/45/90 day policies, class priority, 5000 deletion IDs per transaction, **global** `RETENTION_MAX_BATCHES_PER_PASS=20`, FK cascades, capacity guard, source cursor/checkpoint, stable storage/unavailable fail-closed behavior. No durability PRAGMA adjustment.

## 4. Feature flag and configuration lineage

Add immutable `retention_indexed_v1_enabled: bool = False` config field (Python name local; env key exact) and parse strictly lowercase literal `true`/`false` *only when* `NETWORK_METADATA_ENABLED=true`. NI-01 disabled ignores malformed new fields. Invalid enabled setting → controlled startup failure. OFF omits flag from canonical digest input, retaining legacy configuration digest for any existing A combination. ON includes the flag in canonical digest/run lineage. No Admin toggle and no hot reload.

The existing A switch and A implementation, if merged, **must be preserved** unchanged and four A/B flag combinations supported. B's OFF code path is literally the legacy `_select` behavior.

## 5. Coder-focused acceptance matrix

Implement focused deterministic tests covering R2 B-01..B-06 without invoking full-system regression:

1. **Index plans / bounds:** representative **file-backed Lab** fixtures, `EXPLAIN QUERY PLAN` for both branch SQL; demonstrate `idx_nm_observations_event` and `idx_nm_observations_ingested` range SEARCH on chosen fixture (rather than old observation-id PK scan), at most 5k rows/branch, 10k combined, 5k deletion IDs.
2. **Eligibility / eventual catch-up:** 0,1,5000,5001,20000 eligible observations, expected selection/catch-up compared with legacy; permitted internal ordering difference only; no premature expiration.
3. **Timestamp matrix:** old event/new ingest, reversed, same age/ties, mixed state, already-expired sensitive prefixes, future timestamps, **14/30 day exact strict boundaries**, canonical formats.
4. **Adversarial expired-heavy prefix:** construct file-backed data with a sufficiently large time-ordered early prefix already in `sensitive_endpoint_presence_state='expired'`; measure or instrument cost and report page/read/latency limitations candidly. **If performance is unsafe/uncertain: B activation HOLD**, not schema workaround.
5. **Global retention bounding / faults:** 20 × 5000 transaction ceiling; slow reader/WAL/capacity/no-source/SQLite exception paths when narrow deterministic fixtures suffice; checkpoint/source authority remains unchanged; no deadlock or faked success.
6. **Compatibility:** FK delete effects, digest expiration and exact schema signature, B OFF parity, independent A/B config/digest. Prove no NI-02B/NI-04 outward contract mutation by keeping original persisted shapes.

**Coder runs ONLY the targeted B tests impacted by changed code**, once at final handoff, with exact commands and results. Broad Central Lab, full project, physical host I/O, prolonged multi-run or production tests belong to Tech Lead. Heavy IO/load acceptance and any uncertainty about expired-heavy runtime safety go to Tech Lead as a HOLD/evidence handoff; do not replace precise unit tests with stress on production.

## 6. Exit criteria / status vocabulary

Coder may report:

- `B_IMPLEMENTATION_PASS`: source contract implemented, OFF preserves legacy, targeted tests PASS; **does not** assert physical disk win or B activation.
- `B_ACTIVATION_HOLD_EXPIRED_PREFIX`: correctness implemented but adversarial performance gate not established or unsafe; provide reproducible fixture and observed evidence.
- `BLOCKED_SCOPE` or `BLOCKED_ARCH`: if implementation needs schema/index/new file outside whitelist or violates invariants.

Correctness, source identity, schema/failure cases and independent A combination are **non-waivable**. An unsafe/performance-uncertain B may be left **OFF** for future Tech Lead evidence, not silently declared production-ready.

## 7. Publication / handoff

After B base re-pin approval, create separate B branch/worktree from exact new baseline. Commit, push, open **separate B PR**; no merge/deploy/restart. Submit:

```text
TASK=PERF-IO-NI01-B
RESULT=B_IMPLEMENTATION_PASS | B_ACTIVATION_HOLD_EXPIRED_PREFIX | BLOCKED_...
B_BASE_HEAD=...
B_BASE_TREE=...
CANDIDATE_HEAD=...
CANDIDATE_TREE=...
FLAG=NETWORK_METADATA_RETENTION_INDEXED_V1_ENABLED (DEFAULT_OFF)
A_FLAG_COMPATIBILITY=...
SOURCE_FILE_SCOPE=...
FOCUSED_TEST_COMMANDS_AND_COUNTS=...
EXPLAIN_BRANCHES=...
EXPIRED_PREFIX_EVIDENCE=...
EQUIVALENCE_AND_REPLAY=...
PR_URL=...
MERGE=NO
ACTIVATION=NO
PRODUCTION_CHANGE=NO
```

## 8. Release and physical performance belong to Tech Lead / Owner

Tech Lead performs independent larger file-backed pre-production comparisons and the four A/B combinations on isolated, equivalent workloads, including read/write ops, page traversal, time, byte backlogs, checkpoint progression and physical I/O where safely measurable. Owner separately decides B merge, dormant deploy, each controlled flag activation or restart; A and B have **independent** rollback. Any failed expired-prefix gate means **B flag remains OFF**; new index/schema design returns to Architect rather than widening this task.

**Tech Lead directive:** `B CONTRACT READY / START QUEUED UNTIL POST-A BASE REPIN`. **Do not bundle B into A.**
