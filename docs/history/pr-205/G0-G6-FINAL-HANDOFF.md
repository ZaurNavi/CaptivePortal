# TASK-DTI-NI-04 — G0–G6 local implementation handoff

Prepared for TechLead23 source review on 2026-10-14. This is not an official acceptance manifest or production admission.

## Disposition

- Coder implementation WP-B1 → WP-F: complete local candidate.
- Final clean-commit targeted verification: **746 PASS / 0 FAIL / 0 ERROR / 0 SKIP**, 24.87s.
- G2 correctness: **PASS**, original 369 targeted tests.
- G2 performance: **ACCEPTED BY OWNER EXCEPTION**, **not formal performance PASS**.
- Original G2 throughput loss 6.3078% (reported 6.31%) versus normal 5% limit is expressly accepted by Owner. The proposed twelve-run protocol was cancelled and was not executed.
- Full Project/Central/full repository gates: **NOT RUN BY CODER**, reserved for Tech Lead.
- Independent source/admission review and production-class QA: pending Tech Lead/Owner.
- PUSH / PR / MERGE / DEPLOY / PRODUCTION MIGRATION / SERVICE RESTART / FEATURE ACTIVATION: **NO**.

## Exact Git identity

```text
BASE_HEAD=b1442efc434716d35e21b9e3124c3b9cd2222fbe
BASE_TREE=1ea6a2d452a5c8147d2a9cdce6c5dcecd9900575
HEAD=42c585225d28557f06f5824026329401ae8d3aab
TREE=cbe9ac1d3efed53a3d66b60915b9f1c21e7caa5c
BRANCH=task/dti-ni-04-background-materialization
WORKTREE=/home/zaur_navi/captivportal-lab/worktrees/dti-ni-04-background-materialization
WORKTREE_STATUS=CLEAN
git status --porcelain=<empty>
FILES_CHANGED=50
ADDITIONS=3910
DELETIONS=86
```

| Stage | Local commit | Tree |
| --- | --- | --- |
| G1 proposed compatibility bridge | 36e2b462a39533c32954215e40d9097167591237 | 2541384db1c6a0c4a8b307c54fc1c966ed6c4152 |
| G2 exact frozen delivery candidate | d102ce84ebb67c9e1084cdf8da113e943f0d6dd1 | bb8f6186b3d03c78c6eda8d061faeadca38857d1 |
| G3 store/evaluator/worker foundation | b48419523be00a51b6993688e2d244251f09672c | 7cb9eda8d4ee7a97edaf7ad9a7d0ffff5164b892 |
| G4 recovery/generation verification | b560dbe904e8f9f199d61eda37edc8961f6d8d1f | c888250698898a10b1c46dccee8f404c5c212237 |
| G5 materialized V3 read/UI | 82e67adafe4a72144601e72f025cd1d6f0693465 | aa805b631f7d749d714ddec4a72ea0ded1f22cab |
| G6 shadow/release foundation | 62b09057b5f05d5f55d6e58289e0ade19f1114df | b6eacf5574d23a330fb0be17802bd7f74bb0e0f5 |
| G6 final native FULL/replay/category verification | 42c585225d28557f06f5824026329401ae8d3aab | cbe9ac1d3efed53a3d66b60915b9f1c21e7caa5c |

All history is local, linear and unrevised. G3's shared worker includes the lower-priority paging machinery; G4 separately verifies its durable resume, throttle, generation switch and live-priority contracts. Later G6 commits harden the store/read boundary and close native SQLite FULL/replay acceptance edges. Final tests run on the clean final commit, not an uncommitted replacement tree.

Proposed `NI04_MAT_COMPAT_BASE_SHA` is G1 above; it requires independent Tech Lead acceptance before any operational use. The old b1442efc binary is forbidden as a post-extension rollback floor.

## Complete replacement patch

```text
PATCH_PATH=C:\CaptivPortal-Lab\handoffs\ni04-background-materialization-20261013\G0-G6-final-candidate.patch
PATCH_BYTES=281551
PATCH_SHA256=c54e67c03e4303c9a25d457b5b2ddd4719a23f1eaa9f1598592e7706bfd81ee3
PATCH_REVERSE_APPLY_CHECK=PASS
GIT_DIFF_CHECK_BASE_TO_HEAD=PASS
```

Earlier partial patches, G2 HOLD handoff and raw load results are retained unchanged. They are historical stage evidence, not overwritten by this handoff.

## Work-package implementation mapping

| WP | Implementation | Contract behavior |
| --- | --- | --- |
| B1/G1–G2 | projection schema/repository/service_extension/delivery reader, CLI and preflight | unchanged Core V1; optional exact three-table extension; installer after writer lock; transactional seed; candidate-only atomic outbox; monotonic lifetime cursors; bounded exact identity/coverage readers |
| B2/G3 | materialization_schema + materialization_repository | eight closed tables, no category table; WAL/FULL/FK; exclusive writer; verified immutable facts and deterministic IDs; atomic facts/rollups/coverage/checkpoint; bounded retention/capacity; no raw endpoints/hostnames |
| C/G3 | evaluator + legacy read refactor + source_adapter + worker + CLI/unit | exactly one evidence evaluator; entire-batch provenance verification before any matcher; unchanged pure matcher; bounded live/evidence batches; exact identity recheck; replay enqueue/CAS; coverage reconciliation; independent process |
| D/G4 | shared worker paging lane + backfill/generation tests | capture H; live starts above H; fixed 24h keyset; <=128/page and <=1 page/s; yield to live; durable resume; gap recovery retains old cursor until completed scan and prevents unsupported negative claims |
| E/G5 | materialized_read_service/models/serialization + Admin composition/config/routes/pages/template/NI04 IIFE | serve reads only NI04 DB; four bounded product queries; <=13 recent rows, publish <=12; categories from selected Services only; exact 1h/24h cutoffs; V3 new materialization object; V2 off/shadow preserved; no fallback |
| F/G6 | shadow comparison, targeted native end-to-end/latency/RSS/failure tests, operator docs | same-time positive-set comparison; legacy deadline classified separately; explicit mode/rollback plan; G2 Owner exception disclosed; no operational activation by Coder |

No new recognition rules, taxonomy, knowledge manifest, ruleset or research registry bytes were created/changed.

## Store schema / durability

Dedicated path: /opt/CaptivePortal/data/network_service_intelligence.sqlite3, default 512 MiB, permitted 128 MiB..2 GiB.

Tables:
1. service_materialization_schema
2. service_materialization_generations
3. service_recognition_observations
4. device_service_rollups
5. device_materialization_state
6. service_materialization_checkpoints
7. service_binding_replay_jobs
8. service_materialization_runtime

DDL/indexes/triggers are in materialization_schema.py. One active generation is enforced by partial unique index and checked against the runtime pointer. Exact admitted tuple versions/digests bind each generation. Positive observation identity is checked against the original accepted canonical ServiceObservation semantics; conflicting lineage is never overwritten.

The bounded checkpoint additionally records recovery high-water/new-live cursor/cutoff and last gap timestamp. This does not add a history table or change upstream semantics. It prevents the delivery cursor from silently jumping across a retention gap: new live work is tracked separately, recovery is resumable, and negative completeness remains blocked for the affected 24h window.

SQLite policy is WAL / synchronous FULL / FK ON / busy_timeout 500 / autocheckpoint 1000. Fact+rollup+coverage+cursor commit is atomic. Real native SQLITE_FULL and injected crashes prove whole-batch rollback; Python 3.10 canonical FULL text is classified capacity_halted without exposing exception payload. Retention is bounded, refuses current-positive deletion, and does not VACUUM. Capacity stops progress, not evidence preservation.

The DB contains protected Site/Device/MAC and exact observation/rule lineage as required, but no raw SNI, DNS names, IP, ports, packet payload or NI01 JSON. Operational telemetry has one constant event and an exact nonnegative-int allowlist; bool/unknown fields/out-of-range values are rejected.

## Final targeted commands and results

Interpreter:
`/home/zaur_navi/captivportal-lab/test-gate-platform-01-r1-venv/bin/python`

Working directory:
`/home/zaur_navi/captivportal-lab/worktrees/dti-ni-04-background-materialization`

All invocations use external PYTHONPYCACHEPREFIX:
`/home/zaur_navi/captivportal-lab/tmp/ni04mat-pycache`.

Final clean-commit scoped command:

```bash
python -m pytest -q -rs -o junit_family=legacy \
  --junitxml=/mnt/c/CaptivPortal-Lab/handoffs/ni04-background-materialization-20261013/G3-G6-clean-commit-targeted-08.xml \
  tests/network_service_recognition \
  tests/admin_web/test_device_service_intelligence.py \
  tests/admin_web/test_device_service_intelligence_frontend.py \
  tests/admin_web/test_materialized_service_intelligence.py \
  tests/admin_web/test_materialized_service_frontend.py
```

Result: **746 passed / 0 failed / 0 errors / 0 skipped**, 24.87s. XML execution timestamp: 2026-10-14T00:01:18.979723+04:00.

Stage-local XML retained:
- G2: 369 PASS (accepted original).
- G3-store-worker-03: 101 PASS.
- G4-backfill-04: 10 PASS.
- G5-v3-read-06: 66 PASS.
- G3-G6-clean-commit-targeted-08: 746 PASS, final authoritative Coder scoped run.

Counts overlap: do not add them into a fictitious total of unique tests.

Syntax/static checks:
- compileall on all changed Python files, pycache outside repository: PASS.
- node --check app/admin_web/static/admin.js: PASS.
- node --check new materialized_service_intelligence.cjs: PASS.
- git diff --check BASE..HEAD: PASS.
- reverse-apply check of exact replacement patch: PASS.
- clean Git status after verification: PASS.

## Acceptance mapping and explicit limits

Test names below refer to tests/network_service_recognition unless another directory is shown.

| Requirement | Evidence |
| --- | --- |
| AC-M01 background positive | test_materialization_worker::test_background_positive_no_admin_request; test_materialization_end_to_end::test_real_three_store_background_roundtrip_immutable_upstream |
| AC-M02 serve isolation | test_materialized_read::test_v3_positive_query_only_no_source_reads; Admin test_serve_composition_does_not_parse_upstream_env |
| AC-M03 YouTube/control semantics | real disposable three-store YouTube roundtrip; public synthetic identity only; protected Owner control recipe in release runbook, real control not executed by Coder |
| AC-M04 late src/new feed | test_live_atomic_and_idempotent_overlap plus accepted NI02B late-resolution/feed tests; no edge/recognition before authoritative relevant src delivery |
| AC-M05 peer pending | test_peer_pending_and_reconciliation_without_new_edge; admitted V2 pending regression tests |
| AC-M06 clear without new src | same reconciliation test; no duplicate fact |
| AC-M07 late Registry | test_non_authoritative_live_then_exact_binding_replay; full-closed-schema enqueue/crash tests |
| AC-M08 no reassignment | test_immutable_no_cross_identity_replay; test_exact_mac_conflict_no_reassignment |
| AC-M09/M10 crashes | atomic_fact_coverage_cursor_crash; live_crash_checkpoint_exact; page_cursor_and_results_atomic; full closed-store binding enqueue crash |
| AC-M11 idempotency | live overlap, same edge replay, original feed duplicate and deterministic replay/CAS tests |
| AC-M12 feed gap | test_gap_no_false_cursor_progress; old cursor retained until captured recovery completes; gap timestamp blocks complete negative coverage |
| AC-M13/M14 time windows | worker_outage_and_cutoff_without_write; original exact half-open Recent/Last tests retained |
| AC-M15 worker stopped | outage cutoff + honest_degradation_preserves_valid_positive |
| AC-M16 negative safety | no_result_incomplete_never_sufficient_negative; safely_evaluated_unknown_is_distinct_from_never_processed |
| AC-M17/M18 generations | atomic_generation_switch_no_mixed_publication; promotion_guard_and_atomic_active_switch; same_identity_conflict_no_overwrite |
| AC-M19 expired rules | expired_generation_not_published; unchanged admitted artifact eligibility tests |
| AC-M20 privacy | closed_store_and_pragmas; public DTO privacy canaries; closed telemetry tests |
| AC-M21 latency | 300 reader samples + 20 authenticated Flask test-client samples; production-class/browser/network certification remains TL/Owner |
| AC-M22 live latency | 20 real three-store incremental samples; local manual-cycle fixture, not systemd scheduling/capacity certification |
| AC-M23 resource isolation | backfill yields to live, 1-page/s throttle, coverage cadence and bounded RSS; production-class Portal/Auth differential/coexistence stress remains TL/Owner |
| AC-M24 upstream immutability | real three-store before/after logical dumps; protected Git blob comparison |
| AC-M25 no fallback | unavailable_store_no_legacy_fallback; explicit serve composition; HTTP V3 failure version; legacy off/shadow tests |

R1-QA01..04: G2 seed-with-empty-audit, audit retention/ID reuse, monotonic recreation tests.
R1-QA05..06: original real-SQLite queue crash tests plus final full closed NI04 store enqueue/crash tests.
R1-QA07: exact-MAC-only replay test and worker late-binding replay.
R1-QA08: G1 periodic/safe-reason no-sequence and G2 obsolete-authority cleanup.

R2-QA01/02/03/06/07/08/09: original G1 Core-only/extension/off-upkeep, old binary rejection, exact object/meta/mutated-Core tests.
R2-QA04/05/12: original G2 each-DDL/DML interruption, postcommit/restart/no-op installer tests.
R2-QA10: closed declared-input preflight + runbook; production process inventory execution not performed.
R2-QA11: deterministic virtual-clock slow-start fixture (120s versus >=180s declared budget), not physical production disk/startup certification.

R3-QA01/02: 13th unique category excluded.
R3-QA03: shared category timestamp from selected recent services.
R3-QA04: Service ties and explicit equal-category timestamp ID ordering.
R3-QA05: old non-recent Service cannot add category.
R3-QA06: query-only read isolation, four bounded product queries, no independent category table.

Additional: real native SQLite full-page failure, 30s worker deadline rollback, one-writer lock, malformed/contradictory rollup fail-closed, forged observation digest rejection, unknown schema object rejection and default-OFF no-DB startup.

## G2 original measurements — preserved

| Original order | p95 commit ms | throughput edges/s |
| --- | ---: | ---: |
| baseline 1 | 89.517094 | 2179.262307 |
| candidate 1 | 92.838186 | 2229.268456 |
| candidate 2 | 87.960716 | 2229.023899 |
| baseline 2 | 80.664834 | 2379.091184 |

Original protocol: 3 warmup + 60 measured batches/run, 256 observations/batch, fixed candidate mix. Pair 1 p95 +3.7100%, throughput +2.2946%. Pair 2 p95 +9.0447%, throughput -6.3078%. No sample was excluded or overwritten. Frozen candidate source is bound to local G2 commit/tree above, whose code is unchanged in final HEAD.

`G2-load-results.json` still hashes to d4b2187b2e69241a6ecfec0b57708b552e51c873221f2d0645bae7c5da784389.
G2 performance is **OWNER EXCEPTION**, not formal PASS. No twelve-run retest or NI02B performance repair was performed after the override.

## Final local latency/RSS evidence

From final clean-commit XML; no discarded sample or inferred production claim.

| Scoped fixture | Samples | p95 ms | p99 ms | max ms |
| --- | ---: | ---: | ---: | ---: |
| materialized reader, 10 warmup | 300 | 5.678328 | 7.448918 | 15.111967 |
| authenticated Flask API test-client | 20 | 3.699543 | 3.836408 | 3.836408 |
| real three-store incremental live cycle | 20 | 80.696995 | 105.029937 | 105.029937 |

Single additional real roundtrip cycle: 68.156822ms.
Final measured process RSS high-water delta: 0 bytes. This means no increment above the already-established test-process high-water during that fixture, not that worker memory use is zero. Earlier retained runs measured 524288 and 393216 bytes of high-water delta; all runs are retained. This is not a production-class steady-state capacity certification.

Native environment: WSL Ubuntu-22.04, Python 3.10.12, SQLite 3.37.2. Interpreter SHA256 a2f33a6e006989270f4340528eb61f8f97366e00a5d1b602ac8672ea44fc56ae. Worker and reader origins verified under the exact worktree; PYTHONPATH absent. Full origin/environment JSON accompanies the handoff.

## UI / sample / deployment limits

V3-anonymized-example.json is generated by the real worker/store/read/serializer over a disposable synthetic fixture. It contains no raw MAC/IP/SNI/edge/source refs. It is an example, not an official acceptance artifact.

Real Node VM tests cover strict V3, forbidden extra fields/types, positive+lag and empty+incomplete text, exactly one Materialization line, explicit V2 off/shadow compatibility, cadence/backoff, hide/show, manual refresh and DOM-less safety. Existing NI03 CSS/JS/prefix checks pass unchanged. No fabricated browser screenshot is supplied; independent real-browser/accessibility acceptance remains with Tech Lead/Owner.

The release runbook is docs/network-service-materialization-release.md. Reader-first compatibility rollout, exact bridge admission, verified backup, no concurrent backfill, NI02B-alone transactional install, >=180s supervisor budget, shadow/current/backfill/closure checks and non-destructive rollback are mandatory before any Owner-authorized production operation.

Outstanding admission work (not Coder full-gate blockers):
- independent source/semantic review of final exact tree;
- Full Project/Central/native platform acceptance owned by Tech Lead;
- production-class capacity/WAL-reader-pressure/coexistence, physical disk stalls and Portal/Auth/CAPPORT differential latency;
- real-browser/accessibility QA and protected Owner control identity;
- exact compatibility bridge operational admission and all migration/shadow/serve authorizations.

No unconditional FULL PASS / production readiness / merge release is claimed.

## Protected source proof

Git diff against frozen BASE is empty for NI01 acquisition/parser/writer/schema, NI02A attribution, NI03, Fingerprint, frozen NI04 knowledge/matcher/artifact admission, NI02B service/retention/shared reader, Portal/Auth/CAPPORT/run.py. Changed-file inventory is restricted to this lane. Final NI02B production/deploy code is byte-identical to the frozen G2 commit: `git diff --exit-code d102ce8..HEAD -- app/network_metadata_projection deploy/network-metadata-projection` PASS.

Real worker tests also compare unchanged upstream row dumps. The existing unrelated dirty main worktree and other prior worktrees were not edited/reset/rebased/cleaned.

## Full changed-file list

Paths are relative to the native worktree above. Exact byte sizes/SHA256 are in G0-G6-source-inventory.json.

```text
app/admin_web/config.py
app/admin_web/pages.py
app/admin_web/query_service.py
app/admin_web/routes.py
app/admin_web/runtime.py
app/admin_web/static/admin.js
app/admin_web/templates/admin/device.html
app/config.py
app/network_metadata_projection/cli.py
app/network_metadata_projection/repository.py
app/network_metadata_projection/schema.py
app/network_metadata_projection/service_delivery_read_service.py
app/network_metadata_projection/service_extension.py
app/network_service_recognition/binding_replay.py
app/network_service_recognition/cli.py
app/network_service_recognition/evaluator.py
app/network_service_recognition/materialization_config.py
app/network_service_recognition/materialization_repository.py
app/network_service_recognition/materialization_schema.py
app/network_service_recognition/materialization_telemetry.py
app/network_service_recognition/materialized_read_service.py
app/network_service_recognition/models.py
app/network_service_recognition/read_service.py
app/network_service_recognition/serialization.py
app/network_service_recognition/shadow.py
app/network_service_recognition/source_adapter.py
app/network_service_recognition/worker.py
app/settings.py
deploy/network-metadata-projection/network-metadata-projection.service
deploy/network-service-recognition/network-service-recognition.env.example
deploy/network-service-recognition/network-service-recognition.service
docs/network-service-materialization-backfill.md
docs/network-service-materialization-release.md
docs/network-service-materialization.md
scripts/ni04_materialization_preflight.py
tests/admin_web/materialized_service_intelligence.cjs
tests/admin_web/test_materialized_service_frontend.py
tests/admin_web/test_materialized_service_intelligence.py
tests/network_metadata_projection/service_delivery_load.py
tests/network_metadata_projection/test_service_delivery.py
tests/network_metadata_projection/test_service_extension_bridge.py
tests/network_service_recognition/memory_measurement.py
tests/network_service_recognition/test_binding_replay_contract.py
tests/network_service_recognition/test_materialization_backfill.py
tests/network_service_recognition/test_materialization_end_to_end.py
tests/network_service_recognition/test_materialization_generations.py
tests/network_service_recognition/test_materialization_store.py
tests/network_service_recognition/test_materialization_worker.py
tests/network_service_recognition/test_materialized_categories.py
tests/network_service_recognition/test_materialized_read.py
```

## Evidence identities

All files below are under C:\CaptivPortal-Lab\handoffs\ni04-background-materialization-20261013.

| File | Bytes | SHA256 |
| --- | ---: | --- |
| G2-load-results.json | 4040 | `d4b2187b2e69241a6ecfec0b57708b552e51c873221f2d0645bae7c5da784389` |
| G2-targeted.xml | 93614 | `c78a6b4fd870da16cffb75335ba42f221a9bf36ccb915b58e786aecf7cb94e94` |
| G3-store-worker-03.xml | 23814 | `de38c6ac00a0c6c5e94f36a9e4e780eff83af696da86935f550040150155a671` |
| G4-backfill-04.xml | 2650 | `03edc58d868de6adfe3fd1ce8f8d059766629ee8be6f6263bb0544dcc40fdedd` |
| G5-v3-read-06.xml | 16030 | `e001e64488b16b05a396f330ee9ba11120b72681bdf355e8b69d339adf24e5a0` |
| G3-G6-clean-commit-targeted-08.xml | 196837 | `91615b22e7a801c8e2e39d53e65b139b946f6ef95f07d9a6726a28eca22e6f0d` |
| G0-G6-final-candidate.patch | 281551 | `c54e67c03e4303c9a25d457b5b2ddd4719a23f1eaa9f1598592e7706bfd81ee3` |

The companion JSON inventories and this handoff are outside Git. No database, diagnostic state, pycache, secrets or external evidence was committed.

```ini
LOCAL_COMMITS=YES
WORKTREE_CLEAN=YES
PUSH=NO
PR=NO
MERGE=NO
PRODUCTION_MIGRATION=NO
DEPLOY=NO
SERVICE_RESTART=NO
FEATURE_ACTIVATION=NO
PRODUCTION_ACTION=NO
FULL_PROJECT_GATE=NOT_RUN_BY_CODER
CENTRAL_FULL_GATE=NOT_RUN_BY_CODER
G2_PERFORMANCE=ACCEPTED_BY_OWNER_EXCEPTION
NEXT_ACTION=TECHLEAD23_INDEPENDENT_SOURCE_AND_ADMISSION_REVIEW
```
