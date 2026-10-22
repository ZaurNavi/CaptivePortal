# TASK-DTI-NI-04 Background Materialized Service Intelligence — G2 HOLD

## Decision required

Implementation stopped at G2 because one measured paired throughput comparison
exceeded the mandatory <=5% regression budget.
No durability weakening, unapproved optimization or selective aggregation was applied.
G3–G6 are not started and no PR has been created.
Full/Central gates are reserved for Tech Lead under the test-ownership correction;
their absence is not the blocker.

The first pair passed both thresholds; the reverse-order pair passed the p95
commit threshold but measured a 6.3078% throughput loss.
These results are inconsistent enough that Coder does not claim G2 performance PASS.
Tech Lead disposition is required: approve a controlled, predeclared validation
protocol/workload and repeat, or assign a bounded source optimization.

## Frozen source and local state

```ini
BASE_HEAD=b1442efc434716d35e21b9e3124c3b9cd2222fbe
BASE_TREE=1ea6a2d452a5c8147d2a9cdce6c5dcecd9900575
BRANCH=task/dti-ni-04-background-materialization
WORKTREE=/home/zaur_navi/captivportal-lab/worktrees/dti-ni-04-background-materialization
LOCAL_HEAD=36e2b462a39533c32954215e40d9097167591237
LOCAL_HEAD_TREE=2541384db1c6a0c4a8b307c54fc1c966ed6c4152
LOCAL_HEAD_PARENT=b1442efc434716d35e21b9e3124c3b9cd2222fbe
G2_PARTIAL_CANDIDATE_TREE=bb8f6186b3d03c78c6eda8d061faeadca38857d1
WORKTREE_STATE=DIRTY / G2 DRAFT PRESERVED
REAL_INDEX=UNCHANGED / NO STAGED FILES
```

The one local commit is G1's independently reviewable compatibility bridge:
`feat(ni02b): add Service Intelligence schema compatibility bridge`.
It is a **proposed** rollback-floor commit, not a Tech Lead accepted release.
`NI04_MAT_COMPAT_BASE_SHA` must be assigned only after independent acceptance.

G0: exact baseline/tree verified, clean isolated worktree created, declared
projection consumers inventoried; unrelated worktrees preserved.

G1: Coder targeted PASS — 329 passed, 0 failed, 0 skipped.
Bridge accepts exact Core-only/Core+Extension, fails closed for partial/unknown
objects, preserves Core DDL/user_version/identities, maintains feed/change index
when present independently of NI-04 publication.
Installation is absent/default disabled in the G1 commit.
Old b1442efc binary rejection against the migrated fixture is explicitly tested.

G2 draft: explicit locked-writer installer, atomic candidate feed, authoritative
change index seeding/upkeep, bounded delivery/identity/coverage/backfill read APIs,
consumer enqueue/checkpoint primitive and exact targeted replay primitive.
Operator input preflight and startup timeout source are included.
The NI-04 full store and worker are not yet implemented.

## Measured G2 load evidence

Environment: qualified Python 3.10.12 virtualenv, Ubuntu 22.04 native Git worktrees
under WSL2, SQLite 3.37.2, WAL/FULL/foreign_keys enabled.
Clean baseline worktree:
`/home/zaur_navi/captivportal-lab/worktrees/ni04-materialization-load-baseline`.
Its HEAD/tree exactly match BASE_HEAD/BASE_TREE; bytecode is external.

Load is declared synthetic, not a captured production sample:
approximately 65% local DNS, 20% outbound TLS, 15% outbound QUIC, two authoritative
synthetic devices, 256 observations/batch, three warm-up batches and 60 measured
batches per process. Source/authority/Registry inputs are in-memory disposable
fixtures; the real ProjectionRepository/Service and real durable SQLite writes run.
Source-record construction and warm-up are excluded. Whole-poll time measures
bounded source-fixture reads, actual prepare/evaluation and actual transaction
commit/maintenance. Commit p95 times commit_dispositions independently.
Every run checks exact projected edge count, feed eligibility count and checkpoint.
No telemetry containing real device/traffic identifiers is produced.

| Pair | Baseline commit p95 ms | Extension commit p95 ms | p95 delta | Baseline edges/s | Extension edges/s | Throughput loss |
|---|---:|---:|---:|---:|---:|---:|
| 1, baseline then extension | 89.517094 | 92.838186 | +3.7100% | 2179.262307 | 2229.268456 | -2.2946% |
| 2, extension then baseline | 80.664834 | 87.960716 | +9.0447% | 2379.091184 | 2229.023899 | **+6.3078%** |

All runs processed 25,333 measured projected edges; each extension fixture committed
5,635 eligible feed rows including warm-up. There was no checkpoint/edge mismatch.
The raw values, interpreter/platform, source hash and actual clean/dirty Git states
are retained in G2-load-results.json. Dirty candidate source was used only in Lab;
its final transport tree is recorded above.

Invocation (qualified interpreter abbreviated as PYTHON below):

```sh
PYTHON=/home/zaur_navi/captivportal-lab/test-gate-platform-01-r1-venv/bin/python
DRIVER=/home/zaur_navi/captivportal-lab/worktrees/dti-ni-04-background-materialization/tests/network_metadata_projection/service_delivery_load.py
BASE=/home/zaur_navi/captivportal-lab/worktrees/ni04-materialization-load-baseline
CAND=/home/zaur_navi/captivportal-lab/worktrees/dti-ni-04-background-materialization
LAB_TMP=/home/zaur_navi/captivportal-lab/tmp
export PYTHONPYCACHEPREFIX=/home/zaur_navi/captivportal-lab/tmp/ni04mat-load-pycache
export PYTHONPATH=

# Execution order: baseline_1, candidate_1, candidate_2, baseline_2.
cd "$BASE"
"$PYTHON" "$DRIVER" --repository "$BASE" --batches 60 --lab-temp "$LAB_TMP"
cd "$CAND"
"$PYTHON" "$DRIVER" --repository "$CAND" --extension --batches 60 --lab-temp "$LAB_TMP"
"$PYTHON" "$DRIVER" --repository "$CAND" --extension --batches 60 --lab-temp "$LAB_TMP"
cd "$BASE"
"$PYTHON" "$DRIVER" --repository "$BASE" --batches 60 --lab-temp "$LAB_TMP"
```

No assertion or budget was weakened after seeing these measurements.
No median/average policy was chosen after the failing pair to convert it to PASS.
This does not prove a production performance regression, but it does block a
Coder claim that the specified G2 performance gate passed.

## Targeted correctness evidence

Final directly affected group: **369 passed in 16.78s; 0 failed / errors / skipped**.
Exact node outcomes are in G2-targeted.xml.
Of these, 61 new cases cover G1 bridge (21), G2 producer/delivery/migration (32)
and B1 consumer enqueue/replay contracts (8).
NI-03 V1 directly affected regression: 50 PASS.

```sh
PYTHONPYCACHEPREFIX=/home/zaur_navi/captivportal-lab/tmp/ni04mat-pycache \
/home/zaur_navi/captivportal-lab/test-gate-platform-01-r1-venv/bin/python -m pytest -q -rs \
  -o junit_family=legacy \
  --junitxml=/mnt/c/CaptivPortal-Lab/handoffs/ni04-background-materialization-20261013/G2-targeted.xml \
  tests/network_metadata_projection \
  tests/network_protocol_intelligence \
  tests/network_service_recognition/test_protected_readers.py \
  tests/network_service_recognition/test_binding_replay_contract.py
```

Coverage includes:

- R1-QA-01/02/03/04/08: deterministic authoritative seed with empty audit history,
  original audit ID reuse/retention, sequence non-reuse, periodic/safe-reason changes.
- R1-QA-05/06/07: actual SQL enqueue+cursor transaction crash behavior and exact
  Site+MAC replay primitive. These use a minimal disposable SQLite queue/checkpoint
  fixture; full-store startup/worker integration remains G3, not claimed here.
- R2-QA-01/02/03/06/07/08/09: dual compatibility, old binary incompatibility,
  partial/mutated/unknown schema rejection, off-mode feed/index upkeep.
- R2-QA-04/05/12: crash injection after each installer DDL/DML stage, before/after
  commit, repeat/restart no duplication.
- R2-QA-10: operator input preflight refuses missing/wrong consumer bridge
  identity, absent verified backup, concurrent backfill and inadequate timeout.
  It validates supplied inputs only and grants no production authorization.
- R2-QA-11: virtual-clock slow-start fixture spanning 120s within declared 180s
  budget, with complete transactional schema. Actual production startup and
  SysAdmin supervisor behavior are not claimed.
- Feed uses primary-key search, not a full feed/edge scan. Current index identity
  contradiction fails closed. Coverage-only interface returns no fact list.
- Bounds, canonical cursor types, read-only dump equality, exact identity,
  half-open replay selection and source/edge/checkpoint preservation are tested.

Compileall of changed/new Python source/tests and git diff --check: PASS.
After the measured G2 issue, no further production-source edit was made.

## Partial changed-file inventory and transport

Combined BASE to dirty G2 draft: **13 files, 1,415 additions, 16 deletions**.

- app/network_metadata_projection/schema.py
- app/network_metadata_projection/repository.py
- app/network_metadata_projection/service_extension.py
- app/network_metadata_projection/cli.py
- app/network_metadata_projection/service_delivery_read_service.py
- app/network_service_recognition/binding_replay.py
- deploy/network-metadata-projection/network-metadata-projection.service
- docs/network-service-materialization.md
- scripts/ni04_materialization_preflight.py
- tests/network_metadata_projection/test_service_extension_bridge.py
- tests/network_metadata_projection/test_service_delivery.py
- tests/network_metadata_projection/service_delivery_load.py
- tests/network_service_recognition/test_binding_replay_contract.py

```ini
FULL_PARTIAL_PATCH=G0-G2-partial-candidate.patch
FULL_PARTIAL_PATCH_BYTES=84138
FULL_PARTIAL_PATCH_SHA256=fed9c176cf295f0c1bc3af11b1eae20a4d5cfd202d9c808c928600c96e3468bf
G2_DELTA_PATCH=G2-delta-from-bridge.patch
G2_DELTA_PATCH_BYTES=61161
G2_DELTA_PATCH_SHA256=fac38651897704669b5e144c61867d0eef3a145087e3e2255a7e2dbbf6b3f544
LOAD_RESULTS_SHA256=d4b2187b2e69241a6ecfec0b57708b552e51c873221f2d0645bae7c5da784389
TARGETED_XML_SHA256=c78a6b4fd870da16cffb75335ba42f221a9bf36ccb915b58e786aecf7cb94e94
```

NI-01, NI-02A, NI-03, Portal/Auth/CAPPORT, Admin source, Fingerprint and the
existing matcher/knowledge artifact files remain untouched.
NI-02B attribution/pending/retention/service algorithms remain unchanged;
the draft adds only the explicitly authorized extension/install/delivery scope.

```ini
G0=PASS / CODER
G1=TARGETED_PASS / PROPOSED_BRIDGE_COMMIT
G2=HOLD / THROUGHPUT_BUDGET_EXCEEDED_IN_SECOND_PAIR
G3=NOT_STARTED
G4=NOT_STARTED
G5=NOT_STARTED
G6=NOT_STARTED
FULL_PROJECT_GATE=NOT_RUN / TECH_LEAD_OWNERSHIP
CENTRAL_FULL_GATE=NOT_RUN / TECH_LEAD_OWNERSHIP
FULL_REPOSITORY_REGRESSION=NOT_RUN / TECH_LEAD_OWNERSHIP
G2_COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
PRODUCTION_MIGRATION=NO
DEPLOY=NO
PRODUCTION_CHANGE=NO
NI05_ACTIVATION=NO
NI06_ACTIVATION=NO
NEXT_ACTION=TECH_LEAD_G2_DISPOSITION
```
