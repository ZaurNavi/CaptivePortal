# TASK-PERF-IO-NI01-B-R3 — Correct expired-prefix amplification in PR #210

**Issuer:** Tech Lead  
**Executor:** Coder  
**Date:** 2026-10-14  
**Status:** `PREPARED / CODER_HOLD_PENDING_ARCHITECT_R3` — **not GO until ratification**  
**Existing PR:** [#210](https://github.com/ZaurNavi/CaptivePortal/pull/210) · `task/perf-io-ni01-b`  
**Candidate HEAD:** `166a1546c96cdfc09b624b614b6b0080c425a3d3`  
**Candidate TREE:** `793ffd7025b7161c4cfab193077d114c5e042422`  
**Base main:** `018985edaa008847b64051dc49c90914d0a60238`  
**Dependency:** Chief Architect's ratification of attached `CAPTIVPORTAL-PERF-IO-NI01-B-R3-EXPIRED-PREFIX-ARCHITECTURE-PROPOSAL-2026-10-14.md`.

## 1. Scope and intended change

Do not merge, deploy, activate B, or create a second PR. After R3 approval, add a **follow-up commit** to the **existing PR #210**, preserving PR history (no forced history rewrite). Production A remains ON and untouched.

Modify only:
- `app/network_metadata/retention.py`
- `tests/network_metadata/test_retention.py`
- `docs/configuration.md`

Keep `app/network_metadata/config.py`, `models.py`, `schema.py`, `repository.py`, `service.py`, downstream modules, NI-01 database schema/indexes/PRAGMAs unchanged.

1. In B=ON `sensitive` replace the two `WHERE time<? AND state!='expired'` queries with two `WHERE time<? ORDER BY time,id LIMIT 5000` raw indexed branches, retrieving `state` in the projection.
2. Stream each cursor. First `expired` row → close cursor, discard candidates and execute unchanged legacy sensitive query **once**. Fallback means performance mitigation, **not** error recovery. Strictly enforce legacy predicates.
3. When no `expired` encountered, keep R2's canonical validation, deduplication and oldest-5000 ordering. Preserve the full 10k result bound and 5k deletion bound.
4. Leave `core` B indexed path byte-for-byte or AST-equivalent to PR #210. Leave `run`, `_delete`, `expire_touched_identity` byte-for-byte/AST-equivalent to PR #210. B=OFF query unchanged; A flag and lineage untouched.
5. No new feature flags, cursors, database writes or schema/index maintenance. Ensure all temporary cursors close before executing fallback or returning, and do not keep two SQLite cursors open simultaneously.

## 2. New targeted tests only

- First/middle/last (`index 0, 2499, 4999`) expired item in both time streams; fallback exactly once, no unbounded indexed branch scan; validate selected IDs against legacy.
- All eligible and interleaved timelines, candidate disjointness/overlap, ties, mixed event vs ingest, boundaries, and exact oldest-K when fast path selected.
- 100k expired-prefix file-backed fixture with exact existing V1 schema and FK; return correct eligible IDs with bounded **indexed lookahead** and one legacy query. Independently measure both branches and fallback VM steps and note the legacy term is not bounded.
- SQLite fail-closed errors, invalid retained IDs/timestamps, interrupted cursor, transaction/rollback, no checkpoint movement; no silent fallback on errors.
- Config OFF lineage unchanged; B/ON digest unchanged from #210; A/B independence and no impact on existing fault logic. Run only newly required focused tests; do **not** re-run the already passing 61 B tests if relevant source paths are unchanged (rerun only directly impacted test cases).
- New EXPLAIN plans; compare original #210 vs guarded vs legacy on the same lab distribution; no unsubstantiated claim of HDD physical IOPS reductions.

## 3. Handoff and gates

- Stop immediately if new schema/index, deletion semantic modification, bigger source scope, or altered durability seems necessary. Ask Tech Lead; no self-approved workaround.
- `git diff --check`, focused tests, verify exact HEAD/TREE and changed-files list, update current PR #210 with follow-up commit **only after R3 is ratified**.
- Report first/last expired row evidence; stable expected deletion ID set in fallback; SQL counts and VM steps; candidate/legacy behavior; explicit `B_ACTIVATION_GATE` status.
- Tech Lead separately owns independent integration/physical I/O performance gate and PR final review.

**Until R3 approval:** `CODER=HOLD / PR210=UNMERGED / B_DEFAULT_OFF / PRODUCTION=NO / MERGE=OWNER_ONLY`.
