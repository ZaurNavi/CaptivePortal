# TASK-ADMIN-SETTINGS-06-FIX1 — R1 bounded repair handoff

This report supersedes first-handoff claims for P1-01/P1-02. The original dirty implementation is preserved. Only the two assigned defects are repaired; no acceptance/publication is declared.

```ini
TASK=TASK-ADMIN-SETTINGS-06-FIX1
BASE_HEAD=3467da8abd4ad4bb5b381a13e374e2e8faf4685e
BASE_TREE=2e3cb2b345af370275cb9b8fe35729f6f5218d35
HEAD=UNCOMMITTED
WORKTREE=DIRTY
P1_01=PASS
P1_02=PASS
TARGETED_TESTS=751 PASS / 1 FAIL
NEW_STAGE6_TESTS=173 PASS / 0 FAIL
COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO
```

## Identity and patch

```ini
WORKTREE_PATH=C:\CaptivPortal-Lab\coder-admin-settings-06
BRANCH=feature/admin-settings-06-feature-controls
LOCAL_HEAD=3467da8abd4ad4bb5b381a13e374e2e8faf4685e
CANDIDATE_TREE=87af8a3077690076f03735357a52d1ba496640a6
PATCH_PATH=C:\CaptivPortal-Lab\artifacts\TASK-ADMIN-SETTINGS-06-FIX1-CANDIDATE.patch
PATCH_BYTES=220324
PATCH_SHA256=a5af1bf649e11cb2294b6943f00a35957cff97185923cb9268deedb15a4c1fd8
PATCH_REVERSE_APPLY_CHECK=PASS
NORMAL_INDEX_STAGED_FILES=0
```

The complete replacement patch is BASE→FIX1, including all new candidate files. It was exported using an external temporary index; the normal Git index remains unstaged. Original first-candidate patch/report were not overwritten.

Complete candidate: 63 files, 2024 additions, 306 deletions. Scope unchanged.

## Exact FIX1 delta files

Relative to first candidate tree 2e5f224217f38c5545b413295d9f2effdd8c8d74:

```text
M	app/admin_web/routes.py
M	app/settings_control/services.py
M	app/settings_control/validation.py
M	tests/admin_web/test_feature_settings_stage6.py
M	tests/settings_control/test_features_stage6.py
```

No other source/test file changed during FIX1. In particular home.html and test_home_traffic.py are unchanged from the first candidate; the baseline Home-ordering issue was not repaired.

## P1-01 evidence

- validate_features_candidate is now a separate real method, not an alias or call to validate_portal_candidate.
- Features mutation dispatch explicitly calls that method.
- It builds the candidate AdminFeaturePlanV1 and supplies that exact plan to the shared general/conditional semantic validator.
- General primitives, feature primitives/graph, R1.1 outer-gate semantics, base Admin semantics and feature-selected prerequisites remain validated.
- Non-secret Controller normalization and Portal validation follow; no Controller secret resolution/decryption/master-key access is introduced.
- The runtime/startup mandatory plan boundary is unchanged; mutation plans do not replace the startup plan.
- Existing A–G/H matrix tests, secret isolation, managed-secret carry-forward and one-startup-plan tests pass.

New focused cases in test_features_stage6.py:

```text
test_features_mutation_rejects_invalid_enabled_prerequisites:
HOME_ACTIVITY + HOME_LIVE, Current State disabled                         PASS
HOME_ACTIVITY + HOME_LIVE, Current State Site scope missing               PASS
HOME_HEALTH, malformed supporting request timeout                        PASS
DEVICE_LIST_CONTEXT, invalid cursor secret                               PASS
TRAFFIC_PROJECTION_READ + TRAFFIC + TRAFFIC_HISTORY, relative read DB path PASS
```

Each uses the normal mutation service to enable the feature(s) from a valid disabled startup state. Each asserts validation_failed / HTTP 422 / configuration_prerequisite_invalid; configured generation stays 0, overrides stay empty, and no mutation audit or idempotency receipt is committed. A forbidden Portal-method spy ensures the service does not use that path; secret resolve/keys/decrypt spies fail on access.

test_features_validation_uses_own_candidate_plan passes: methods are distinct, Portal validation and secret resolve are forbidden, exactly one candidate plan is built, the candidate enables Home Health while the immutable startup plan remains disabled.

## P1-02 evidence

Features HTTP mutation now applies only str(uuid.UUID(key)) == key, exactly like the common Settings boundary; no version check remains.

test_features_accepts_canonical_non_v4_uuid_and_replays passes for canonical UUIDv1, UUIDv3, UUIDv5 and nil UUID. Each POST returns 201, replay returns the identical accepted receipt, only one changed generation is created, and the exact key is persisted in the Features idempotency namespace.

The former UUIDv4-only test expectation is replaced by rejection of a noncanonical braced UUID. CSRF, If-Match, body-size, malformed/noncanonical UUID and no-op behavior are retained.

## Executed tests and syntax checks

Windows; Python 3.10.11:
C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe.
Node v24.19.0.
PYTHONPYCACHEPREFIX=C:\CaptivPortal-Lab\tmp\settings06-fix1-pycache.

Repair-focused command:

```text
python -m pytest -q tests/settings_control/test_features_stage6.py tests/admin_web/test_feature_settings_stage6.py
 --basetemp=C:\CaptivPortal-Lab\tmp\settings06-fix1-repair
 --junitxml=C:\CaptivPortal-Lab\artifacts\TASK-ADMIN-SETTINGS-06-FIX1-repair.xml
 --tb=short
RESULT=139 passed / 0 failed
```

Final task-focused run used the same mandatory TASK §37 test-file set and the same three narrow direct compatibility files from the first handoff (test_settings_routes.py, test_settings_ui.py, test_schema_v4_portal.py), not a full repository gate:

```text
python -m pytest -q <same explicit task-focused file arguments>
 --basetemp=C:\CaptivPortal-Lab\tmp\settings06-fix1-focused
 --junitxml=C:\CaptivPortal-Lab\artifacts\TASK-ADMIN-SETTINGS-06-FIX1-focused.xml
 --tb=short
RESULT=751 passed / 1 failed / 0 errors / 0 skipped
```

The exact executed shell command derives file arguments from the first handoff's explicit file list:

```powershell
$env:PYTHONPYCACHEPREFIX='C:\CaptivPortal-Lab\tmp\settings06-fix1-pycache'
$stage6TaskSuites = Get-Content -LiteralPath 'C:\CaptivPortal-Lab\artifacts\TASK-ADMIN-SETTINGS-06-FIRST-HANDOFF.md' |
  Where-Object { $_ -match '^  tests/.+\.py$' } | ForEach-Object { $_.Trim() }
& 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe' -m pytest -q @stage6TaskSuites --basetemp='C:\CaptivPortal-Lab\tmp\settings06-fix1-focused' --junitxml='C:\CaptivPortal-Lab\artifacts\TASK-ADMIN-SETTINGS-06-FIX1-focused.xml' --tb=short
```

752 cases actually executed; 37 distinct test files. The extracted arguments contain five repeated paths already in the explicit list; pytest collected each test once in this run, as verified by the JUnit inventory.

New Stage-6 test files:

| File | Pass | Fail |
|---|---:|---:|
| test_features_stage6.py | 95 | 0 |
| test_schema_v5_features.py | 11 | 0 |
| test_secret_recovery_v5.py | 2 | 0 |
| test_feature_settings_stage6.py | 44 | 0 |
| test_feature_settings_stage6_frontend.py | 11 | 0 |
| test_feature_plan_stage6.py | 10 | 0 |
| Total | 173 | 0 |

```text
python -m compileall -q app/settings_control/validation.py app/settings_control/services.py
 app/admin_web/routes.py tests/settings_control/test_features_stage6.py
 tests/admin_web/test_feature_settings_stage6.py                  PASS
node --check app/admin_web/static/features_settings.js            PASS
git diff --check                                                 PASS
complete external-index candidate diff --check                    PASS
git apply --reverse --check complete replacement patch            PASS
```

## Remaining unchanged baseline failure

```text
tests/admin_web/test_home_traffic.py::test_home_template_delivers_traffic_only_when_enabled
tests/admin_web/test_home_traffic.py:637
actual order offsets=[6850,10547,10471]
expected sorted offsets=[6850,10471,10547]
```

Same failure as first handoff. Neither its assertion nor Home template changed in FIX1. No skip/xfail/deselection or unrelated ordering repair was made. The entire focused gate is NOT declared all-green.

No full pytest, Central Lab, production, deployment, migration on production, service restart, commit, push or PR was performed. Tech Lead owns independent source review and acceptance.

## Complete replacement name-status

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
M	tests/admin_web/conftest.py
A	tests/admin_web/feature_settings_stage6_ui.cjs
M	tests/admin_web/test_config.py
M	tests/admin_web/test_device_current_context.py
A	tests/admin_web/test_feature_settings_stage6.py
A	tests/admin_web/test_feature_settings_stage6_frontend.py
M	tests/admin_web/test_home_activity.py
M	tests/admin_web/test_home_health.py
M	tests/admin_web/test_home_live.py
M	tests/admin_web/test_home_traffic.py
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
A	tests/analytics/test_feature_plan_stage6.py
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
```

## Complete replacement stat

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
 tests/admin_web/conftest.py                        |   9 +-
 tests/admin_web/feature_settings_stage6_ui.cjs     | 128 +++++++
 tests/admin_web/test_config.py                     |  11 +-
 tests/admin_web/test_device_current_context.py     |  23 +-
 tests/admin_web/test_feature_settings_stage6.py    | 221 +++++++++++
 .../test_feature_settings_stage6_frontend.py       |  42 ++
 tests/admin_web/test_home_activity.py              |  12 +-
 tests/admin_web/test_home_health.py                |  12 +-
 tests/admin_web/test_home_live.py                  |  22 +-
 tests/admin_web/test_home_traffic.py               |  22 +-
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
 tests/analytics/test_feature_plan_stage6.py        |  80 ++++
 tests/analytics/test_runtime.py                    |  20 +-
 tests/settings_control/__init__.py                 |   8 +
 tests/settings_control/test_activation.py          |  15 +-
 .../test_controller_secret_repository.py           |   5 +-
 .../test_controller_secret_service.py              |   5 +-
 .../test_controller_secret_startup.py              |  11 +-
 tests/settings_control/test_controller_stage3.py   |   7 +-
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
 63 files changed, 2024 insertions(+), 306 deletions(-)
```

HOLD FOR TECH LEAD REVIEW.

