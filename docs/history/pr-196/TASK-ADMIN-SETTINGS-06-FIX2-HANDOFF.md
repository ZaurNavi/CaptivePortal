# TASK-ADMIN-SETTINGS-06-FIX2 — A3 compatibility handoff

FIX2 is test/benchmark-only. The dirty FIX1 candidate was preserved; its production source was not reopened. No independent acceptance/publication is declared.

## Required result

```ini
TASK=TASK-ADMIN-SETTINGS-06-FIX2
BASE_HEAD=3467da8abd4ad4bb5b381a13e374e2e8faf4685e
BASE_TREE=2e3cb2b345af370275cb9b8fe35729f6f5218d35
HEAD=UNCOMMITTED
WORKTREE=DIRTY
P1_01=CLOSED
P1_02=CLOSED
P1_03=PASS
P1_04=PASS
PRODUCTION_FILES_CHANGED_DURING_FIX2=NO
MANDATORY_PLAN_CALLERS=PASS
ANALYTICS_PLAN_CALLERS=PASS
ACTIVATION_SIGNATURE_COMPAT=PASS
REGISTRY_46_COMPAT=PASS
SCHEMA_V5_COMPAT=PASS
STAGE6_NEW_TESTS=173 PASS / 0 FAIL
FIX2_COMPAT_TESTS=222 PASS / 0 FAIL
NODE_CHECK=PASS
COMPILEALL=PASS
DIFF_CHECK=PASS
PATCH_BYTES=254136
PATCH_SHA256=c024bbca7927119d5f6ee707de54f98205282a8f4b2f353c519b09e0e1fcebbd
OPEN_P0=0
OPEN_P1=0
COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO
```

OPEN_P0/OPEN_P1 above are known assigned-scope findings after Coder verification, not a replacement for independent Tech Lead acceptance.

## Exact FIX2_TEST_FILES_CHANGED

Relative to FIX1 candidate tree 87af8a3077690076f03735357a52d1ba496640a6:

```text
tests/admin_web/completed_guest_traffic_capacity_benchmark.py
tests/admin_web/current_guest_traffic_capacity_benchmark.py
tests/admin_web/test_controller_settings_stage3.py
tests/admin_web/test_controller_settings_stage4.py
tests/admin_web/test_device_fingerprint_presentation.py
tests/admin_web/test_portal_settings_stage5.py
tests/analytics/test_current_traffic_runtime.py
tests/analytics/test_historical_traffic_runtime.py
tests/analytics/test_prepared_observation_runtime.py
tests/settings_control/test_controller_secret_startup.py
tests/settings_control/test_controller_stage3.py
tests/test_admin_controller_settings.py
tests/web/test_portal_presentation_stage5.py
```

13 files changed, 147 additions, 49 deletions. Only the eleven A3 files and the two already-authorized settings_control compatibility files changed. No shared fixture, other benchmark, production module, Home template or Home-ordering assertion was changed.

## Identity / complete replacement patch

```ini
WORKTREE_PATH=C:\CaptivPortal-Lab\coder-admin-settings-06
BRANCH=feature/admin-settings-06-feature-controls
LOCAL_HEAD=3467da8abd4ad4bb5b381a13e374e2e8faf4685e
CANDIDATE_TREE=7b6cfa20c23c097e87059ca12a593f697f0a36a2
PATCH_PATH=C:\CaptivPortal-Lab\artifacts\TASK-ADMIN-SETTINGS-06-FIX2-CANDIDATE.patch
PATCH_BYTES=254136
PATCH_SHA256=c024bbca7927119d5f6ee707de54f98205282a8f4b2f353c519b09e0e1fcebbd
PATCH_REVERSE_APPLY_CHECK=PASS
NORMAL_INDEX_STAGED_FILES=0
COMPLETE_BASE_TO_CANDIDATE=74 files / 2171 additions / 355 deletions
FIX1_TO_FIX2_PRODUCTION_DIFF=EMPTY
```

The patch includes all reviewed draft/new files, not just FIX2. It was generated through a separate external temporary Git index; no staging/commit was performed in the normal worktree index. Prior patches and handoffs remain unchanged.

## Repair evidence

### Admin mandatory plan and adoption

- Bootstrap-owning Controller/Portal tests pass boot.feature_plan to each runtime and assert exact object identity.
- Settings-only/synthetic Admin tests and both capacity benchmark harnesses construct a real AdminFeaturePlanV1 from a synthetic ResolvedSettingsSnapshot using the exact same settings mapping passed to the runtime. No Settings DB is added solely to obtain a plan.
- Real Admin runtime adoption receives the same plan and an Analytics structural test object with that plan and historical_source_mode=base.
- Deployment-disabled generic Portal adoption uses the existing tests.settings_control.adopt(boot) helper.
- Device Fingerprint read composition still proves no classification DB creation and retains every presentation/security assertion.
- No production None fallback, optional argument, old-signature shim, mock feature graph or environment reread was introduced.

### Analytics and run.py spies

- Every direct Analytics factory call in the three A3 files uses a real plan derived from that test's exact settings mapping.
- Non-Projection tests explicitly prove historical_source_mode=base; no feature is enabled merely to satisfy the signature.
- Prepared Observation/AP24 test uses the same plan for Analytics and Admin; provider/worker isolation assertions remain unchanged.
- The composition-specific _configure_admin_web spy now accepts the keyword and asserts it is exactly the plan captured from bootstrap, rather than silently accepting arbitrary kwargs.

Static AST inspection of the exact thirteen FIX2 files found 10 direct Admin factory calls and 8 direct Analytics factory calls; every call supplies feature_plan. Every direct activation adopt call supplies Analytics and the feature_plan keyword. Syntax check covers the two non-pytest benchmark harnesses.

### Registry / schema / startup validation

- Controller read-model compatibility proves exact General twelve keys, exact Controller three keys, exact Portal fourteen keys and Features seventeen coexisting; ordinary total=46.
- OMADA_CLIENT_SECRET remains explicitly excluded from the ordinary registry.
- Stage-4 secret-definition immutability and secret-outside-registry assertions are retained and domain counts updated to 12/3/14/17.
- The validation spy accepts feature_plan and asserts the startup argument is boot.feature_plan, while still proving raw client_secret is absent and secret resolution is explicit.
- v1 migration test now explicitly observes v1→v2→v3→v4→v5 in order; at every step it verifies exact generation/target/activation history and replay response bytes. Existing audit/type/override/failure-rollback assertions remain. Reopening v5 does not rerun migrations.

## Executed focused commands and evidence

No full repository gate, Central Lab, production test, benchmark main/capacity gate or production action was run.

### Final Windows Stage-6 group — 173 PASS

Python 3.10.11; existing interpreter:
C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe.

PYTHONPYCACHEPREFIX=C:\CaptivPortal-Lab\tmp\settings06-fix2-pycache.

```text
python -m pytest -q
 tests/analytics/test_feature_plan_stage6.py
 tests/settings_control/test_features_stage6.py
 tests/settings_control/test_schema_v5_features.py
 tests/settings_control/test_secret_recovery_v5.py
 tests/admin_web/test_feature_settings_stage6.py
 tests/admin_web/test_feature_settings_stage6_frontend.py
 --basetemp=C:\CaptivPortal-Lab\tmp\settings06-fix2-stage6
 --junitxml=C:\CaptivPortal-Lab\artifacts\TASK-ADMIN-SETTINGS-06-FIX2-stage6.xml
 --tb=short
RESULT=173 passed / 0 failed / 0 errors / 0 skipped
```

### Final Windows compatibility group — 193 PASS

```text
python -m pytest -q
 tests/analytics/test_current_traffic_runtime.py
 tests/analytics/test_historical_traffic_runtime.py
 tests/analytics/test_prepared_observation_runtime.py
 tests/admin_web/test_controller_settings_stage3.py
 tests/admin_web/test_portal_settings_stage5.py
 tests/admin_web/test_device_fingerprint_presentation.py
 tests/test_admin_controller_settings.py
 tests/web/test_portal_presentation_stage5.py
 tests/settings_control/test_controller_stage3.py
 tests/admin_web/completed_guest_traffic_capacity_benchmark.py
 tests/admin_web/current_guest_traffic_capacity_benchmark.py
 --basetemp=C:\CaptivPortal-Lab\tmp\settings06-fix2-compat
 --junitxml=C:\CaptivPortal-Lab\artifacts\TASK-ADMIN-SETTINGS-06-FIX2-compat.xml
 --tb=short
RESULT=193 passed / 0 failed / 0 errors / 0 skipped
```

The capacity benchmark files are not pytest tests: collection/import/syntax were checked, but their Owner-only main()/capacity measurements were NOT executed.

### Existing WSL crypto compatibility group — 29 PASS

Windows interpreter lacks cryptography. Existing WSL Ubuntu-22.04 provides system cryptography 3.4.8. Existing perf-venv Python 3.10.12 / pytest 9.1.1 was used with the existing system packages exposed through a process-only PYTHONPATH. No dependency installation or security mocking was performed.

```text
wsl -d Ubuntu-22.04 --cd /mnt/c/CaptivPortal-Lab/coder-admin-settings-06 --
 env PYTHONPATH=/usr/lib/python3/dist-packages
 PYTHONPYCACHEPREFIX=/home/zaur_navi/captivportal-lab/tmp/settings06-fix2-pycache
 /home/zaur_navi/captivportal-lab/perf-venv/bin/python -m pytest -q
 tests/admin_web/test_controller_settings_stage4.py
 tests/settings_control/test_controller_secret_startup.py
 --basetemp=/home/zaur_navi/captivportal-lab/tmp/settings06-fix2-crypto
 --junitxml=/mnt/c/CaptivPortal-Lab/artifacts/TASK-ADMIN-SETTINGS-06-FIX2-wsl-crypto.xml
 --tb=short
RESULT=29 passed / 0 failed / 0 errors / 0 skipped / 3 system-package deprecation warnings
```

Real Stage-4 encryption/decryption and security assertions executed in this group. No skip, xfail, decrypt stub or artifact-identity bypass was added.

FIX2_COMPAT_TESTS=193 Windows + 29 WSL = 222 PASS.

### Initial combined-run fixture discovery issue — retained, not hidden

An earlier combined Windows command mixing the compatibility and new Stage-6 files returned 361 passed / 5 setup errors. The five errors were analytics_stack not found in test_feature_plan_stage6.py. The same file run alone returned 10 PASS with the unchanged real existing fixture. Final separated task-focused groups above returned 173 + 193 PASS without changing any fixture or test source to hide the issue.

Initial evidence remains:
C:\CaptivPortal-Lab\artifacts\TASK-ADMIN-SETTINGS-06-FIX2-windows.xml.

No claim is made that the initial combined attempt passed. Tech Lead may consider this command-order/fixture-discovery observation when selecting broader test invocations.

### Syntax / source checks

```text
node --check app/admin_web/static/features_settings.js           PASS
node --check tests/admin_web/feature_settings_stage6_ui.cjs       PASS
python -m compileall -q <exact thirteen FIX2 files listed above> PASS
git diff --check                                                PASS
complete candidate diff --check through external index           PASS
git apply --reverse --check replacement complete patch           PASS
FIX1 tree→FIX2 tree diff under app/ and run.py                    EMPTY
```

## Boundaries and pending review

- FIX1 P1-01/P1-02 remain closed; their production bytes were not changed.
- No mandatory runtime/activation boundary was weakened.
- Dirty worktree remains uncommitted; no artifact-identity semantics changed.
- Baseline Home-ordering issue remains untouched and was not rerun/repaired in FIX2.
- Broader clean-candidate acceptance belongs to Tech Lead.
- Benchmark capacity runs were not authorized as Coder compatibility tests and remain Owner-only.

## Complete BASE→FIX2 name-status

```text
M	app/admin_web/capabilities.py
M	app/admin_web/config.py
M	app/admin_web/routes.py
M	app/admin_web/runtime.py
M	app/admin_web/static/admin.css
A	app/admin_web/static/features_settings.js
M	app/admin_web/templates/admin/base.html
A	app/admin_web/templates/admin/settings_features.html
M	app/analytics/runtime.py
M	app/settings_control/activation.py
M	app/settings_control/bootstrap.py
M	app/settings_control/definitions.py
A	app/settings_control/features.py
M	app/settings_control/models.py
M	app/settings_control/repository.py
M	app/settings_control/resolver.py
M	app/settings_control/services.py
M	app/settings_control/validation.py
M	app/settings_control/value_validation.py
M	app/traffic_projection/config.py
M	run.py
M	tests/admin_web/completed_guest_traffic_capacity_benchmark.py
M	tests/admin_web/conftest.py
M	tests/admin_web/current_guest_traffic_capacity_benchmark.py
A	tests/admin_web/feature_settings_stage6_ui.cjs
M	tests/admin_web/test_config.py
M	tests/admin_web/test_controller_settings_stage3.py
M	tests/admin_web/test_controller_settings_stage4.py
M	tests/admin_web/test_device_current_context.py
M	tests/admin_web/test_device_fingerprint_presentation.py
A	tests/admin_web/test_feature_settings_stage6.py
A	tests/admin_web/test_feature_settings_stage6_frontend.py
M	tests/admin_web/test_home_activity.py
M	tests/admin_web/test_home_health.py
M	tests/admin_web/test_home_live.py
M	tests/admin_web/test_home_traffic.py
M	tests/admin_web/test_portal_settings_stage5.py
M	tests/admin_web/test_routes.py
M	tests/admin_web/test_runtime.py
M	tests/admin_web/test_settings_routes.py
M	tests/admin_web/test_traffic_ap.py
M	tests/admin_web/test_traffic_ap_share.py
M	tests/admin_web/test_traffic_completed_sessions.py
M	tests/admin_web/test_traffic_current.py
M	tests/admin_web/test_traffic_evidence.py
M	tests/admin_web/test_traffic_foundation.py
M	tests/admin_web/test_traffic_history.py
M	tests/admin_web/test_traffic_independent_ranges.py
M	tests/admin_web/test_traffic_online_guests.py
M	tests/admin_web/test_traffic_peak.py
M	tests/admin_web/test_traffic_statistics.py
M	tests/analytics/test_current_traffic_runtime.py
A	tests/analytics/test_feature_plan_stage6.py
M	tests/analytics/test_historical_traffic_runtime.py
M	tests/analytics/test_prepared_observation_runtime.py
M	tests/analytics/test_runtime.py
M	tests/settings_control/__init__.py
M	tests/settings_control/test_activation.py
M	tests/settings_control/test_controller_secret_repository.py
M	tests/settings_control/test_controller_secret_service.py
M	tests/settings_control/test_controller_secret_startup.py
M	tests/settings_control/test_controller_stage3.py
M	tests/settings_control/test_definitions.py
A	tests/settings_control/test_features_stage6.py
M	tests/settings_control/test_portal_stage5.py
M	tests/settings_control/test_repository.py
M	tests/settings_control/test_run_integration.py
M	tests/settings_control/test_schema_v4_portal.py
A	tests/settings_control/test_schema_v5_features.py
A	tests/settings_control/test_secret_recovery_v5.py
M	tests/settings_control/test_services.py
M	tests/settings_control/test_validation.py
M	tests/test_admin_controller_settings.py
M	tests/web/test_portal_presentation_stage5.py
```

## Complete BASE→FIX2 stat

```text
 app/admin_web/capabilities.py                      |   3 +-
 app/admin_web/config.py                            | 117 +-----
 app/admin_web/routes.py                            |  54 ++-
 app/admin_web/runtime.py                           |  17 +-
 app/admin_web/static/admin.css                     |   7 +
 app/admin_web/static/features_settings.js          | 119 ++++++
 app/admin_web/templates/admin/base.html            |   9 +-
 .../templates/admin/settings_features.html         |  12 +
 app/analytics/runtime.py                           |  25 +-
 app/settings_control/activation.py                 |  38 +-
 app/settings_control/bootstrap.py                  |  10 +-
 app/settings_control/definitions.py                |  35 ++
 app/settings_control/features.py                   |  61 +++
 app/settings_control/models.py                     |   1 +
 app/settings_control/repository.py                 |  43 ++-
 app/settings_control/resolver.py                   |   2 +
 app/settings_control/services.py                   |  82 +++-
 app/settings_control/validation.py                 |  53 ++-
 app/settings_control/value_validation.py           |   4 +
 app/traffic_projection/config.py                   |  24 ++
 run.py                                             |  13 +-
 .../completed_guest_traffic_capacity_benchmark.py  |  18 +-
 tests/admin_web/conftest.py                        |   9 +-
 .../current_guest_traffic_capacity_benchmark.py    |  18 +-
 tests/admin_web/feature_settings_stage6_ui.cjs     | 128 +++++++
 tests/admin_web/test_config.py                     |  11 +-
 tests/admin_web/test_controller_settings_stage3.py |   9 +-
 tests/admin_web/test_controller_settings_stage4.py |   7 +-
 tests/admin_web/test_device_current_context.py     |  23 +-
 .../test_device_fingerprint_presentation.py        |  10 +-
 tests/admin_web/test_feature_settings_stage6.py    | 221 +++++++++++
 .../test_feature_settings_stage6_frontend.py       |  42 ++
 tests/admin_web/test_home_activity.py              |  12 +-
 tests/admin_web/test_home_health.py                |  12 +-
 tests/admin_web/test_home_live.py                  |  22 +-
 tests/admin_web/test_home_traffic.py               |  22 +-
 tests/admin_web/test_portal_settings_stage5.py     |   7 +-
 tests/admin_web/test_routes.py                     |  12 +-
 tests/admin_web/test_runtime.py                    |  26 +-
 tests/admin_web/test_settings_routes.py            |  18 +-
 tests/admin_web/test_traffic_ap.py                 |  25 +-
 tests/admin_web/test_traffic_ap_share.py           |  27 +-
 tests/admin_web/test_traffic_completed_sessions.py |  23 +-
 tests/admin_web/test_traffic_current.py            |  12 +-
 tests/admin_web/test_traffic_evidence.py           |  21 +-
 tests/admin_web/test_traffic_foundation.py         |  23 +-
 tests/admin_web/test_traffic_history.py            |  26 +-
 tests/admin_web/test_traffic_independent_ranges.py |  25 +-
 tests/admin_web/test_traffic_online_guests.py      |  23 +-
 tests/admin_web/test_traffic_peak.py               |  27 +-
 tests/admin_web/test_traffic_statistics.py         |   5 +-
 tests/analytics/test_current_traffic_runtime.py    |  12 +-
 tests/analytics/test_feature_plan_stage6.py        |  80 ++++
 tests/analytics/test_historical_traffic_runtime.py |  18 +-
 .../analytics/test_prepared_observation_runtime.py |  22 +-
 tests/analytics/test_runtime.py                    |  20 +-
 tests/settings_control/__init__.py                 |   8 +
 tests/settings_control/test_activation.py          |  15 +-
 .../test_controller_secret_repository.py           |   5 +-
 .../test_controller_secret_service.py              |   5 +-
 .../test_controller_secret_startup.py              |  24 +-
 tests/settings_control/test_controller_stage3.py   |  30 +-
 tests/settings_control/test_definitions.py         |   2 +-
 tests/settings_control/test_features_stage6.py     | 422 +++++++++++++++++++++
 tests/settings_control/test_portal_stage5.py       |   5 +-
 tests/settings_control/test_repository.py          |   4 +-
 tests/settings_control/test_run_integration.py     |  17 +-
 tests/settings_control/test_schema_v4_portal.py    |   4 +-
 tests/settings_control/test_schema_v5_features.py  | 119 ++++++
 tests/settings_control/test_secret_recovery_v5.py  |  73 ++++
 tests/settings_control/test_services.py            |   7 +-
 tests/settings_control/test_validation.py          |   2 +-
 tests/test_admin_controller_settings.py            |  36 +-
 tests/web/test_portal_presentation_stage5.py       |   3 +-
 74 files changed, 2171 insertions(+), 355 deletions(-)
```

HOLD FOR TECH LEAD REVIEW.

COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO

