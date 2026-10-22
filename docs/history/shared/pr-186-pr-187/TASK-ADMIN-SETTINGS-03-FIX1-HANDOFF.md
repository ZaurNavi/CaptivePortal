# TASK-ADMIN-SETTINGS-03 — FIX1 source-review handoff

```ini
FIX1_COMMIT=3513f6838423d06e0b3852e2d212efa5478539e2
FIX1_PARENT=913b500076d9b831fb0cdc0e3fae142b7742a1a3
FIX1_TREE=06611fff6650fa0eb3be2e5ff301010146413fe7
ORIGINAL_BASE=c1167180daec9ca17d13ab44326f143122db8d5e
WORKTREE=C:\CaptivPortal-Lab\coder-admin-settings-03
WORKTREE_STATE=CLEAN

FIX1_CHANGED_FILES=6
FIX1_ADDITIONS=84
FIX1_DELETIONS=13

FULL_BASE_TO_FIX1_PATCH_PATH=C:\CaptivPortal-Lab\artifacts\TASK-ADMIN-SETTINGS-03-FIX1_BASE-to-CANDIDATE.patch
FULL_PATCH_BYTES=139393
FULL_PATCH_SHA256=db2ccfc2dbf1cfd8372658e9b2c58891d813e2b90202629836cafcd6fa63aa15
PATCH_REVERSE_APPLY_CHECK=PASS

FOCUSED_TESTS=194 passed / 0 failed / 0 skipped
CONTROLLER_TESTS=61 passed / 0 failed / 0 skipped
COMPILEALL=PASS
NODE_CHECK=PASS
GIT_DIFF_CHECK=PASS

P1-01=IMPLEMENTED; required regression cases PASS; pending Tech Lead review
P1-02=IMPLEMENTED; required regression cases PASS; pending Tech Lead review
BLOCKERS=NONE

FULL_REPOSITORY_TESTS_RERUN=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO
```

## Bounded repair

- Only `SettingsError(code="settings_store_unavailable")` degrades to effective-only HTTP 200. RuntimeError and non-store SettingsError propagate to the existing sanitized HTTP 503 route boundary.
- Missing/non-callable configured boundaries fail Controller composition. Null/empty returned projections fail the read surface instead of fabricating a Store outage.
- Controller V2 emits `mutation_available=true` for a configured read and `false` for the admitted Store-outage path. This is availability, not principal authorization.
- The dedicated browser controller requires both this server flag and the independent write capability (and ETag). A read-only principal still receives availability=true, but no edit controls.
- No schema, migration, mutation engine, startup ordering, runtime composition, or unrelated production code changed in FIX1.
- The pre-existing Home Traffic failure remains outside scope, as accepted in Tech Lead R1; no full-suite rerun was performed for this bounded repair.

## FIX1 changed files relative to parent

```text
M app/admin_web/controller_settings.py
M app/admin_web/static/controller_settings.js
M tests/admin_web/controller_settings_stage3_ui.cjs
M tests/admin_web/test_controller_settings_stage3.py
M tests/admin_web/test_controller_settings_stage3_frontend.py
M tests/test_admin_controller_settings.py
6 files changed, 84 insertions(+), 13 deletions(-)
```

## Verification commands

```text
python -m pytest -q tests/settings_control tests/test_admin_controller_settings.py tests/admin_web/test_settings_routes.py tests/admin_web/test_settings_ui.py tests/admin_web/test_controller_settings_stage3.py tests/admin_web/test_controller_settings_stage3_frontend.py tests/test_omada_configuration.py --basetemp C:/CaptivPortal-Lab/tmp/as03-fix1-focused-01 --tb=short
194 passed in 10.70s

python -m pytest -q tests/test_admin_controller_settings.py tests/admin_web/test_controller_settings_stage3.py tests/admin_web/test_controller_settings_stage3_frontend.py --basetemp C:/CaptivPortal-Lab/tmp/as03-fix1-controller-01 --tb=short
61 passed in 6.04s

PYTHONPYCACHEPREFIX=C:\CaptivPortal-Lab\tmp\as03-fix1-pycache
python -m compileall -q app run.py
node --check app/admin_web/static/controller_settings.js
git diff --check
git diff --check c1167180daec9ca17d13ab44326f143122db8d5e HEAD
git apply --reverse --check C:/CaptivPortal-Lab/artifacts/TASK-ADMIN-SETTINGS-03-FIX1_BASE-to-CANDIDATE.patch
All exit statuses: 0

git status --porcelain
<empty>
```

## P1 regression evidence

```text
FIX1-R01 SettingsError(settings_store_unavailable) -> 200 effective-only, mutation_available=false: PASS
FIX1-R02 RuntimeError -> 503 controller_settings_read_unavailable: PASS
FIX1-R03 non-store SettingsError -> 503 controller_settings_read_unavailable: PASS
FIX1-R04 missing/malformed configured boundary -> read-surface unavailable: PASS
Additional narrow malformed projection None/{} -> 503, no fabricated store_state: PASS
FIX1-M01 normal read -> mutation_available=true: PASS
FIX1-M02 post-adoption Store outage -> mutation_available=false: PASS
FIX1-M03 read-only principal -> API availability=true, edit control absent: PASS
FIX1-M04 outage -> browser controls disabled/absent: PASS
Server flag=false despite available store_state + ETag -> browser controls disabled/absent: PASS
```

## Complete original BASE-to-FIX1 name-status

```text
M app/admin_web/controller_settings.py
M app/admin_web/policy.py
M app/admin_web/routes.py
M app/admin_web/runtime.py
M app/admin_web/static/controller_settings.js
M app/admin_web/templates/admin/base.html
M app/admin_web/templates/admin/settings_controller.html
M app/controllers/omada_config.py
M app/settings_control/activation.py
M app/settings_control/bootstrap.py
M app/settings_control/definitions.py
M app/settings_control/models.py
M app/settings_control/repository.py
M app/settings_control/resolver.py
M app/settings_control/services.py
M app/settings_control/validation.py
M docs/configuration.md
M docs/modules/admin-web.md
M run.py
A tests/admin_web/controller_settings_stage3_ui.cjs
A tests/admin_web/test_controller_settings_stage3.py
A tests/admin_web/test_controller_settings_stage3_frontend.py
M tests/admin_web/test_settings_routes.py
M tests/settings_control/__init__.py
M tests/settings_control/test_bootstrap.py
A tests/settings_control/test_controller_stage3.py
M tests/settings_control/test_definitions.py
M tests/settings_control/test_repository.py
M tests/settings_control/test_resolver.py
M tests/settings_control/test_run_integration.py
M tests/settings_control/test_validation.py
M tests/test_admin_controller_settings.py
M tests/visitor_registry/test_snapshot_runtime.py
```

## Complete original BASE-to-FIX1 diff stat

```text
 app/admin_web/controller_settings.py               |  70 +++--
 app/admin_web/policy.py                            |   2 +-
 app/admin_web/routes.py                            |  36 ++-
 app/admin_web/runtime.py                           |   3 +-
 app/admin_web/static/controller_settings.js        | 112 ++++++--
 app/admin_web/templates/admin/base.html            |   1 +
 .../templates/admin/settings_controller.html       |   5 +-
 app/controllers/omada_config.py                    |  25 +-
 app/settings_control/activation.py                 |   2 +-
 app/settings_control/bootstrap.py                  |   4 +-
 app/settings_control/definitions.py                |  36 ++-
 app/settings_control/models.py                     |   6 +-
 app/settings_control/repository.py                 | 151 ++++++++---
 app/settings_control/resolver.py                   |  16 ++
 app/settings_control/services.py                   |  79 ++++--
 app/settings_control/validation.py                 |   8 +
 docs/configuration.md                              |  54 +++-
 docs/modules/admin-web.md                          |  45 +++-
 run.py                                             |  47 ++--
 tests/admin_web/controller_settings_stage3_ui.cjs  |  80 ++++++
 tests/admin_web/test_controller_settings_stage3.py | 206 +++++++++++++++
 .../test_controller_settings_stage3_frontend.py    |  12 +
 tests/admin_web/test_settings_routes.py            |  10 +-
 tests/settings_control/__init__.py                 |   5 +-
 tests/settings_control/test_bootstrap.py           |   7 +-
 tests/settings_control/test_controller_stage3.py   | 282 +++++++++++++++++++++
 tests/settings_control/test_definitions.py         |   7 +-
 tests/settings_control/test_repository.py          |  10 +-
 tests/settings_control/test_resolver.py            |   5 +-
 tests/settings_control/test_run_integration.py     |  71 ++++++
 tests/settings_control/test_validation.py          |   7 +-
 tests/test_admin_controller_settings.py            |  46 ++--
 tests/visitor_registry/test_snapshot_runtime.py    |   8 +-
 33 files changed, 1252 insertions(+), 206 deletions(-)
```
