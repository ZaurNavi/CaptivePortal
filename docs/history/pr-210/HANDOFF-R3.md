# PERF-IO-NI01-B — PR #210 R3 follow-up

B_IMPLEMENTATION=PASS_TARGETED
B_ACTIVATION=HOLD
MERGE_HOLD_PERF_REVIEW=YES
MERGE=HOLD
DEPLOY=NO
PRODUCTION_B=OFF_UNCHANGED
PRODUCTION_A=UNCHANGED

## Identity and scope

- Existing PR: https://github.com/ZaurNavi/CaptivePortal/pull/210 (keep DRAFT / unmerged).
- Branch/worktree: `task/perf-io-ni01-b`, `/home/zaur_navi/captivportal-lab/worktrees/perf-io-ni01-b`.
- Base main: `018985edaa008847b64051dc49c90914d0a60238`; tree `b73f0ed2450e24b7fe4298630999f402a980cce1`.
- Original R2 PR head / follow-up parent: `166a1546c96cdfc09b624b614b6b0080c425a3d3`; tree `793ffd7025b7161c4cfab193077d114c5e042422`.
- Updated head: `fd6eb48d6326f40c51e85ca18fc1df9827e44118`.
- Updated tree: `55c42fff98533dd66416bf49ae0b16bd4e11cae6` (matches staged tree).
- One normal follow-up commit; no history rewrite or second PR.
- Follow-up scope: exactly `app/network_metadata/retention.py`, `tests/network_metadata/test_retention.py`, `docs/configuration.md`; 415 insertions / 19 deletions.
- Combined PR remains six files; original config/model/test_config content unchanged.

Normative authority: Chief Architect ratified Architecture Addendum R3 and Tech Lead Implementation TASK v2 dated 2026-10-14. The fallback order exception is explicit, not a new architecture decision by Coder.

## Implementation

Only B=ON sensitive now uses streamed raw event/ingested index lookahead, each SQL LIMIT 5000 with no state predicate. Every visited UUIDv5, both canonical timestamps, branch strict eligibility and closed presence state are validated before fallback; repeated identity tuples include state and must agree.

Each raw cursor closes unconditionally in finally, before another query opens. The first verified expired row stops consumption, clears candidates and permits exactly one original legacy sensitive SELECT. That cursor also closes on success/error and returned IDs are canonical UUIDv5 validated. Fallback preserves literal SQL/parameters and legacy ID order; it does not assert oldest-K or global validation of unvisited timestamps.

Without encountered expired, fast-path global-oldest K remains. Invalid visited data, SQLite failures/interruption and capacity pressure are not fallback triggers. B=ON core and B=OFF selectors remain the old R2/legacy implementations respectively. No new flag/digest/schema/index/store/PRAGMA or writer changes.

## Focused results on final production source

**205 distinct targeted cases PASS: 193 retention/config + 12 crash/replay. Zero FAIL / SKIP / DESELECT in these explicit suites.**

Final main focused command from B worktree:

```sh
PYTHONPYCACHEPREFIX=/home/zaur_navi/captivportal-lab/tmp/perf-io-ni01-b-pycache /home/zaur_navi/captivportal-lab/test-gate-platform-01-r1-venv/bin/python -m pytest -q -s -p no:cacheprovider -o junit_family=xunit1 tests/network_metadata/test_retention.py tests/network_metadata/test_config.py --junitxml=/mnt/c/CaptivPortal-Lab/handoffs/perf-io-ni01-b-r3-20261014/focused-final.xml
```

193 PASS in 118.79s. Includes all 104 B cases, unchanged config/digest tests (read-only), remaining focused retention regression. R2 assertions reconciled only where R3 changes query shape or ordering; no skip/xfail. Cases cover 0/1/5000/5001/20000 fast-path eligibility, OR/ties/crossover, strict boundaries/mixed state, both branch expired positions 0/2499/4999, true lazy consumption, one legacy query, unseen expired beyond K, duplicate inconsistency and malformed UUID/time/state, SQLite execute/iterate/interrupt/close failures in both raw streams and fallback, invalid fallback IDs, cursor discipline, 100001-row global 20-batch budget, source/capacity/WAL-reader/rollback, FK/digest/replay and four A/B combinations.

Additional command (same interpreter/cache prefix, final production source):

```sh
python -m pytest -q -p no:cacheprovider tests/network_metadata/test_checkpoint_crash.py::test_final_conflict_health_owns_new_prefix_and_stops_evaluation tests/network_metadata/test_checkpoint_crash.py::test_final_partial_health_rolls_back_or_commits_with_entire_batch tests/network_metadata/test_checkpoint_crash.py::test_expired_event_aggregate_checkpoint_and_health_commit_atomically --junitxml=/mnt/c/CaptivPortal-Lab/handoffs/perf-io-ni01-b-r3-20261014/crash-compatibility.xml
```

12 PASS in 1.76s. These test files unchanged.

Earlier preparatory run: 193 PASS, 5 JUnit-format warnings, 121.17s, retained as `focused.log/xml`. Benchmark fixture then expanded to explicit same-connection warm repetition after fresh connection; EOF timing retained instead of deferred close-time overwrite. Full focused suite repeated after those measurement-only edits, as R3 requires. Production source did not change during this refinement; no functional failures hidden or excluded.

Environment: native WSL Ubuntu 22.04; Python 3.10.12; SQLite 3.37.2; qualified Lab venv above. Interpreter SHA256 `a2f33a6e006989270f4340528eb61f8f97366e00a5d1b602ac8672ea44fc56ae`.
`py_compile` for both changed Python files and `git diff --check` (working/staged/commit) PASS. Full Project / Central Gate NOT RUN (Tech Lead ownership).

Static/AST freeze PASS vs exact R2 parent: `run`, `_delete`, `expire_touched_identity`; entire prior `_select` AST after excluding only inserted R3 sensitive branch, including core/OFF/other classes. Byte equality PASS for config.py, models.py, schema.py, repository.py, service.py and test_config.py. Exact V1 schema/FKs/WAL/FULL verified by integration fixtures. Production A, its configuration digest semantics and downstream modules unchanged.

## Actual SQL / EXPLAIN

Raw lookaheads, parameters `[canonical cutoff14]`:

```sql
SELECT observation_id,event_at,ingested_at,sensitive_endpoint_presence_state FROM network_metadata_observations WHERE event_at<? ORDER BY event_at,observation_id LIMIT 5000;
SELECT observation_id,event_at,ingested_at,sensitive_endpoint_presence_state FROM network_metadata_observations WHERE ingested_at<? ORDER BY ingested_at,observation_id LIMIT 5000;
```

Actual plans:

```text
SEARCH network_metadata_observations USING INDEX idx_nm_observations_event (event_at<?)
SEARCH network_metadata_observations USING INDEX idx_nm_observations_ingested (ingested_at<?)
```

No temp sort or identity-PK scan for raw branches. Expired-prefix executes first raw branch, visits exactly 1 validated row, closes it, does not open second, then executes literal legacy SQL once:

```sql
SELECT observation_id FROM network_metadata_observations WHERE (event_at<? OR ingested_at<?) AND sensitive_endpoint_presence_state!='expired' ORDER BY observation_id LIMIT 5000;
```

Legacy plan: `SCAN network_metadata_observations USING INDEX sqlite_autoindex_network_metadata_observations_1` (intentional fallback, no new index). Selected IDs and order exactly equal B=OFF on the same fixed fixture. Actual SQL strings, parameters, per-query plans, visited rows, closed state and costs are retained in `focused-final.log/xml`.

## Whole-cost comparison (not physical IOPS)

Three deterministic order rounds: legacy→R2→R3; R3→legacy→R2; R2→R3→legacy. Each mode uses a fresh SQLite connection then immediate warm same-connection repeat. 54 measured selections total, three samples per mode/cache/distribution; same unchanged file-backed V1 DB within distribution. R2 code loaded read-only from exact parent Git blob, not recreated or edited in history. Benchmark toggles selector mode only against the same synthetic fixture; it is not a runtime/admission configuration change.

Datasets: all-eligible 20000; interleaved 20000 (10000 expired); expired-prefix 100000 expired + 5001 eligible tail. Raw state/eligibility, legacy parity and global-oldest behavior checked for every selection. Progress callbacks count every 100 SQL VM steps, separately for every raw/R2/legacy statement including the entire fallback; figures are lower-bound resolution, not zero-cost when below 100. Total wall clock includes row consumption, required UUID/timestamp validation and sorting. No OS page-cache flush, disk-cold guarantee, physical page/read-byte/ops or HDD IOPS measurement. Reopened connection is not a cold-host benchmark.

Median complete selection seconds:

| distribution/cache | legacy | R2 | R3 |
| --- | ---: | ---: | ---: |
| all eligible / fresh connection | 0.020631 | 0.324892 | 0.333832 |
| all eligible / warm connection | 0.016502 | 0.342968 | 0.328763 |
| interleaved / fresh connection | 0.034325 | 0.351948 | 0.078636 |
| interleaved / warm connection | 0.032543 | 0.364697 | 0.083141 |
| expired prefix / fresh connection | 0.262233 | 0.417835 | 0.321252 |
| expired prefix / warm connection | 0.261533 | 0.452214 | 0.249274 |

SQL VM lower bounds (per complete selection):

- All eligible: legacy 45000; R2 100000; R3 45000 event + 45000 ingested = 90000.
- Interleaved: legacy 75300; R2 150000; R3 raw lookahead below 100 + full fallback 75300.
- Expired prefix: legacy 644800–644900; R2 1100000; R3 raw lookahead below 100 + full fallback 644800–644900. **The fallback scan cost is not omitted.**

Stable cleanup with real unchanged delete transactions and final empty selection also recorded per selection, including full fallback and combined selection VM total; 20000 / 10000 / 5001 eligible sets eventually exhausted without checkpoint drift or FK violations. Entire cleanup elapsed includes selection/validation/delete; SQL VM accounting is explicitly for selectors, not mutation statements. Separate global-budget test proves 20×5000 transaction ceiling. Raw JSON `R3_STABLE_CATCHUP` preserves all intermediate/final scans, not just the first successful selection.

R3 removes the specific R2 state-filtered time-index amplification in these fixtures, **not an unconditional performance defect closure**. Fresh-connection expired-prefix median is ~22.5% slower than legacy; warm median is ~4.7% faster; aggregate six-sample median is ~21% slower. Interleaved and all-eligible complete latency also remain above legacy (R2/R3 have additional required canonical validation/global sorting). No sample was discarded. These are instrumented local timings, not independent release acceptance; variability and cache conditions matter.

**B_ACTIVATION_HOLD / MERGE_HOLD_PERF_REVIEW.** Tech Lead/Chief Architect must disposition remaining complete-path cost and qualify the new SHA independently. No new index, schema workaround, weaker validation or unauthorized optimization was added. B remains default OFF; this publication updates the existing draft for review only.

## Patch artifacts / handoff

External directory: `C:\CaptivPortal-Lab\handoffs\perf-io-ni01-b-r3-20261014`.

- `R3-followup.patch`: exact old PR head→follow-up, 31154 bytes, SHA256 `8a9551992e507db2a421ec40355aa8c3fb791d59dd29e3e5c3f479351f249da5`.
- `PERF-IO-NI01-B-R3-replacement.patch`: exact main base→updated candidate, 54477 bytes, SHA256 `d5ae98b7a7f66d8e5da71dd0eb4d3bca74792625ccd8f3bea822ae482abdd8ab`.
- `focused-final.log/xml`, `focused.log/xml`, `crash-compatibility.log/xml`: preserved exact execution evidence.

No production access/test/DB/service/configuration change. No deployment/restart/flag activation. No merge or auto-merge. Final handoff to Tech Lead for independent review on updated HEAD/TREE.
