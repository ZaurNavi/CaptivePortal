# TASK-DTI-NI-02B — R1 repair handoff

Status: bounded repairs implemented; HOLD FOR TECH LEAD REVIEW. This is a dirty review candidate, not an accepted production artifact.

## Identity and disposition

```text
BASE_HEAD=e32c695e53ffb2b173178189581751728c2ee0c2
BASE_TREE=6348fe5fddb22f597ba8a6e40cf5f96a4d9d73ac
OLD_CANDIDATE_TREE=aff1464ef26caca4c8a2c5543f840850b9a50f2d
NEW_CANDIDATE_TREE=2e3cb2b345af370275cb9b8fe35729f6f5218d35
WORKTREE=C:\CaptivePortal-NI02B
BRANCH=feature/dti-ni-02b-device-network-projection
WORKTREE_STATE=DIRTY / reviewed candidate preserved
ACTUAL_INDEX_STAGED_FILES=0
WINDOWS_LINUX_CANDIDATE_TREE_MATCH=YES

P1_01_SOURCE_HOT_PATH_RESULT=PASS
SOURCE_HOT_PATH_FOREIGN_KEY_CHECK_COUNT=0
SOURCE_HOT_PATH_QUICK_CHECK_COUNT=0
SOURCE_HOT_PATH_INTEGRITY_CHECK_COUNT=0

P1_02_REGISTRY_HOT_PATH_RESULT=PASS
REGISTRY_500_ROW_QUICK_CHECK_COUNT=0
REGISTRY_500_ROW_FOREIGN_KEY_CHECK_COUNT=0
REGISTRY_500_ROW_INTEGRITY_CHECK_COUNT=0
REGISTRY_TRUST_PROBES_PER_500_ROW_PASS=1
REGISTRY_EXACT_AUTHORITY_POINT_READS_PER_500_ROW_PASS=500

P2_01_FROZEN_CONFIG_RESULT=PASS
NI02B_FOCUSED=105 passed
NI01_REGRESSION=368 passed
NI02A_REGRESSION=106 passed
LINUX_TARGETED_TOTAL=579 passed / 0 failed / 0 errors / 0 skipped
REGISTRY_COMPATIBILITY=5 passed / 0 failed / 0 errors / 0 skipped

HEADROOM_PROOF=PASS
FIXED_HEADROOM_BYTES=16777216
MAX_MEASURED_TRANSACTION_GROWTH_BYTES=2707064
MAX_PENDING_TRANSACTION_GROWTH_BYTES=1593832
COMPILEALL=PASS
GIT_DIFF_CHECK=PASS
PATCH_REVERSE_APPLY_CHECK=PASS
BLOCKERS=NONE

COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOYMENT=NO
PRODUCTION_ACTION=NO
FULL_REPOSITORY_TESTS=NO
CENTRAL_LAB_OFFICIAL_GATE=NO
LIVE_NETWORK_TESTS=NO
HOLD_FOR_TECH_LEAD_REVIEW=YES
```

## Repairs and preserved boundaries

P1-01: ordinary source snapshots no longer run foreign_key_check. mode=ro, query_only, FK enforcement, busy timeout 500, BEGIN and bounded schema validation remain. Each selected observation point-looks up its exact source health and ingest run. Missing refs, health capture/generation disagreement, run/observation normalizer disagreement, invalid run identity/timestamp data fail closed. Existing generation, capture-binding, observation/offset/Site/endpoint/timestamp checks remain. SQL traces for all four ordinary source methods prove all three global audit counts are zero. Corruption tests include absent capture binding/endpoints/health/run, invalid generation/identity and inconsistent health/run ownership.

P1-02: evaluate_many performs one read-only metadata/singleton trust probe per nonempty batch. It uses the existing Registry schema validator with audit_snapshot_counts=False and a bounded singleton state read; it does not call validate_runtime_health, get_stats or enumerate reader_state. Actual identity authority remains VisitorRegistryReadService.get_device_by_mac for each distinct canonical MAC. No last_ip/last_site_id inference. Failed point reads return safe registry_unavailable; identity conflicts still fail closed. Each initial prepared source batch and each reconciliation pass uses one adapter batch. Stop checks remain between Registry points and before projection commit. A real disposable Registry + projection 500-row reconciliation test records one probe, 500 exact authority calls and zero global scans.

P2-01: every processing numeric environment value must equal its frozen V1 value; smaller and larger values are rejected. max_db_bytes alone retains the 64 MiB..64 GiB range/default 16 GiB. Paths remain supplied. Default OFF still ignores enabled-only malformed values. Reconciliation selects exact 500 / unresolved 400 / authoritative 100 quotas plus the unchanged frozen spillover; no proportional quota calculation.

No R1 edits to NI-01 schema/writer/normalizer/retention, Registry source/schema/writer, NI-02A writer/schema/repository, T1 semantics, projection schema, edge identity, retry semantics or capacity model. Other worktrees and historical patch/evidence files were not edited. No global cache was added. The original implementation/T1 handoff remains historical; this replacement patch and tree supersede its candidate identity.

## Exact R1 file scope

Compared to old candidate tree aff1464...:

```text
M app/network_metadata/projection_source.py
M app/network_metadata_projection/config.py
M app/network_metadata_projection/registry_adapter.py
M app/network_metadata_projection/repository.py
M app/network_metadata_projection/service.py
M tests/network_metadata_projection/support.py
M tests/network_metadata_projection/test_capacity_config.py
M tests/network_metadata_projection/test_integration.py
M tests/network_metadata_projection/test_projection_source.py
A tests/network_metadata_projection/test_registry_hot_path.py
```

R1_DIFF_STAT=10 files changed, 270 insertions(+), 27 deletions(-).

Production file reasons follow P1-01/P1-02/P2-01 above. Test support now provides batch evaluation with cancellation; capacity tests freeze all ten processing settings plus admitted capacity bounds; existing read-only integration test forbids both single/batch upstream Registry calls; source tests trace four methods and corrupt exact dependencies; the new Registry test file covers 500-row batching, initial Site/MAC batching, future/partial/unavailable/unreadable state, point-read errors, returned identity validation and cancellation without commit.

Full replacement patch against BASE=e32c695e...:

```text
M .env.example
M app/network_attribution/models.py
M app/network_attribution/read_service.py
M app/network_attribution/validation.py
A app/network_metadata/projection_source.py
A app/network_metadata_projection/__init__.py
A app/network_metadata_projection/cli.py
A app/network_metadata_projection/config.py
A app/network_metadata_projection/models.py
A app/network_metadata_projection/read_service.py
A app/network_metadata_projection/registry_adapter.py
A app/network_metadata_projection/repository.py
A app/network_metadata_projection/retention.py
A app/network_metadata_projection/schema.py
A app/network_metadata_projection/service.py
A app/network_metadata_projection/telemetry.py
A app/network_metadata_projection/validation.py
A deploy/network-metadata-projection/README.md
A deploy/network-metadata-projection/network-metadata-projection.env.example
A deploy/network-metadata-projection/network-metadata-projection.service
A tests/network_attribution/test_read_timestamp_interoperability.py
A tests/network_metadata_projection/__init__.py
A tests/network_metadata_projection/support.py
A tests/network_metadata_projection/test_capacity_config.py
A tests/network_metadata_projection/test_integration.py
A tests/network_metadata_projection/test_projection.py
A tests/network_metadata_projection/test_projection_source.py
A tests/network_metadata_projection/test_registry_hot_path.py
```

FULL_DIFF_STAT=28 files changed, 2993 insertions(+), 24 deletions(-).

## Exact checks and evidence

Environment: isolated WSL Ubuntu-22.04, user zaur_navi; mirror /home/zaur_navi/captivportal-lab/coder-ni02b; Python 3.10.12 at /home/zaur_navi/captivportal-lab/perf-venv/bin/python. Mandatory SQL trace/WAL/capacity/writer-lock/headroom cases ran natively on Linux. No production-size or live source was accessed.

Final targeted command:

```bash
PYTHONPATH=. /home/zaur_navi/captivportal-lab/perf-venv/bin/python -B -m pytest -q -s -o junit_family=legacy \
  tests/network_metadata_projection tests/network_metadata tests/network_attribution \
  --basetemp=/home/zaur_navi/captivportal-lab/ni02b-r1-complete-20261009 \
  --junitxml=/mnt/c/CaptivPortal-Lab/artifacts/TASK-DTI-NI-02B_R1_linux-targeted-results.xml --tb=short
```

Registry compatibility command (same authorized five tests):

```bash
PYTHONPATH=. /home/zaur_navi/captivportal-lab/perf-venv/bin/python -B -m pytest -q -o junit_family=legacy \
  tests/visitor_registry/test_device_registry.py::test_registry_read_service_derives_device_type_keys_without_mutating_raw_source \
  tests/visitor_registry/test_device_registry.py::test_schema_and_singleton_are_created \
  tests/visitor_registry/test_device_registry.py::test_startup_rejects_singleton_with_invalid_runtime_state \
  tests/visitor_registry/test_device_registry.py::test_future_and_partial_schemas_are_preserved_and_rejected \
  tests/visitor_registry/test_device_registry.py::test_read_only_cli_lists_cards_and_never_exposes_raw_json \
  --basetemp=/home/zaur_navi/captivportal-lab/ni02b-r1-registry-20261009 \
  --junitxml=/mnt/c/CaptivPortal-Lab/artifacts/TASK-DTI-NI-02B_R1_registry-compatibility-results.xml --tb=short
```

Compileall: Windows canonical C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe -m compileall -q app/network_metadata/projection_source.py app/network_metadata_projection tests/network_metadata_projection, with PYTHONPYCACHEPREFIX=C:\CaptivPortal-Lab\tmp\ni02b-r1-compile-final-20261009. Exit 0. No repo pycache generated by this check.

Both actual dirty diff and complete external-index candidate diff passed git diff --check. Candidate identity was captured with an external temporary Git index, not the actual index; the full binary/full-index patch passed reverse apply --cached --reverse --check. The isolated Linux mirror independently returned the identical candidate tree, using Git canonical text and file-mode handling.

JUnit evidence:

```text
C:\CaptivPortal-Lab\artifacts\TASK-DTI-NI-02B_R1_linux-targeted-results.xml
BYTES=125739
SHA256=73a135776fe6df1e6608c11c63401608cfbb58574266ab3b7839f4c5552eeaba

C:\CaptivPortal-Lab\artifacts\TASK-DTI-NI-02B_R1_registry-compatibility-results.xml
BYTES=1314
SHA256=eb9f65191d972bafec363ab8667de5650e761dd0d94c7e7cbc54b070d405e0a4
```

Incremental runs exposed errors only in the newly added disposable Registry fixture setup (missing parent directories and required edge_at); those fixtures were corrected. Final exact-candidate run has no failures/errors/skips. No existing test was skipped, weakened or removed.

## Replacement full review patch

```text
PATCH_PATH=C:\CaptivPortal-Lab\artifacts\TASK-DTI-NI-02B_R1_BASE-to-CANDIDATE.patch
PATCH_BYTES=179541
PATCH_SHA256=a79d62374f3f04be7766f362fe95068ee9e39d873e396fd6b3d4df88522ac93b
PATCH_BASE=e32c695e53ffb2b173178189581751728c2ee0c2
PATCH_TARGET_TREE=2e3cb2b345af370275cb9b8fe35729f6f5218d35
```

Owner action: Tech Lead reviews this exact replacement candidate. Candidate acceptance/publication/production remain unauthorized. No new architecture ambiguity or outstanding implementation blocker identified.

Agent execution summary: single primary Coder, implementation mode, PowerShell + dedicated Linux Lab, five bounded production files and five test/support files changed relative to previous candidate; nine new Registry test cases plus source/config regressions; only task-authorized module/compatibility checks; no official full gate, commit, push, PR, deploy or activation.
