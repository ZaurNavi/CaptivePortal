# TASK-ADMIN-SETTINGS-05-FIX1 — Coder handoff

TASK=TASK-ADMIN-SETTINGS-05-FIX1
HEAD=a4b19fadfa6eae7e7956eacee12304a0cae596fe
PARENT=5f1766d50fdcb1a2e09eb7dc13fd0df8e5847a50
TREE=2b176bda9d00e4e5699c8fc36be97e3f9da45d3d
BRANCH=feature/admin-settings-05-portal-guest-experience
WORKTREE_PATH=C:\CaptivPortal-Lab\coder-admin-settings-05
WORKTREE=CLEAN
FOUR_FAILURE_RECHECK=4 PASS / 0 FAIL / 0 SKIP
FOCUSED_TESTS=300 PASS / 0 FAIL / 0 SKIP
DIFF_CHECK=PASS
PRODUCTION_FILES_CHANGED=NO
OPEN_P0=0 observed
OPEN_P1=0 observed
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO
FULL_REPOSITORY_RUN=NO
CENTRAL_LAB_RUN=NO

## FIX1 scope

- Exact registry count 29; General 12 original keys/order/defaults preserved; Controller exact 3; Portal exact ordered 14.
- Ordinary registry excludes OMADA_CLIENT_SECRET; domain ownership remains separate.
- Portal copy/support defaults asserted at PORTAL_SETTING_DEFAULTS authority.
- Template wiring asserted for description and all seven support fields.
- Each social anchor separately retains target="_blank" and rel="noopener noreferrer".
- Existing frontend, flag/colors, Wi-Fi decoration and compact-credit assertions preserved.
- No production implementation, other tests, expected design values or original implementation commit modified.

## FIX1 name-status / stat

```text
M tests/settings_control/test_definitions.py
M tests/test_admin_controller_settings.py
M tests/test_portal_design.py

tests/settings_control/test_definitions.py | 21 +20 -1
tests/test_admin_controller_settings.py | 8 +7 -1
tests/test_portal_design.py | 36 +23 -13
3 files changed, 50 insertions(+), 15 deletions(-)
```

## Exact executed commands

Shell: PowerShell. Existing WSL Ubuntu-22.04 / Python 3.10; existing dependency paths only, no installation. Cache and disposable pytest state outside repository.

Four-failure recheck:
```powershell
wsl -d Ubuntu-22.04 --cd /mnt/c/CaptivPortal-Lab/coder-admin-settings-05 --exec env 'PYTHONPATH=/mnt/c/Users/Zaur Navi/AppData/Local/Programs/Python/Python310/Lib/site-packages' PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPYCACHEPREFIX=/tmp/as05-fix1-pycache python3 -m pytest -q tests/settings_control/test_definitions.py::test_exact_ordered_definitions_and_shared_defaults tests/test_admin_controller_settings.py::test_frontend_nonsecret_writable_and_general_allowlist_unchanged tests/test_portal_design.py::test_portal_uses_requested_flag_colors_and_copy tests/test_portal_design.py::test_portal_has_wifi_decor_support_and_compact_credit --basetemp /tmp/as05-fix1-four
```
Result: 4 passed in 10.45s; exit 0.

Mandatory focused:
```powershell
wsl -d Ubuntu-22.04 --cd /mnt/c/CaptivPortal-Lab/coder-admin-settings-05 --exec env 'PYTHONPATH=/mnt/c/Users/Zaur Navi/AppData/Local/Programs/Python/Python310/Lib/site-packages' PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPYCACHEPREFIX=/tmp/as05-fix1-pycache python3 -m pytest -q tests/settings_control/test_portal_stage5.py tests/settings_control/test_schema_v4_portal.py tests/settings_control/test_secret_recovery_v4.py tests/settings_control/test_secret_recovery.py tests/settings_control/test_repository.py tests/settings_control/test_controller_stage3.py tests/settings_control/test_controller_secret_repository.py tests/admin_web/test_portal_settings_stage5.py tests/admin_web/test_portal_settings_stage5_frontend.py tests/admin_web/test_settings_routes.py tests/admin_web/test_global_capabilities_stage4.py tests/web/test_portal_presentation_stage5.py tests/test_capport_portal_presentation_stage5.py tests/test_capport_discovery_frontend.py tests/test_auth_retry_frontend.py --basetemp /tmp/as05-fix1-focused
```
Result: 300 passed in 15.10s; exit 0.

Diff checks:
```text
git diff --check
git diff --cached --check
git diff --check HEAD^ HEAD
```
All PASS. Final git status --porcelain: empty.
Production content check: git diff --quiet HEAD^ HEAD -- app run.py .env.example docs; exit 0.

## Patch artifacts

FIX1-only exact parent-to-implementation patch:
C:\CaptivPortal-Lab\artifacts\TASK-ADMIN-SETTINGS-05-FIX1_PARENT-to-FIX1.patch
BASE=5f1766d50fdcb1a2e09eb7dc13fd0df8e5847a50
BYTES=5759
SHA256=60af327abd0a2f77ba3948becfa63cf09dd0174d71023f43581c23dc0a8ac843

Complete original Stage-5 BASE-to-FINAL patch:
C:\CaptivPortal-Lab\artifacts\TASK-ADMIN-SETTINGS-05_BASE-to-FIX1.patch
BASE=c05d0fccfb1c0ed67a2e3fbd5d6f58ee2b2d2ed9
BYTES=168504
SHA256=3e3846da513952349b624e5b0cfb812fe060d62c77a45f18f7ee0890a64e681c

Both exported with git diff --binary --full-index from immutable commits.
Previous original candidate patch retained unchanged.

## Complete BASE-to-FINAL name-status and stat

This includes the previously accepted original implementation plus this 3-test repair. Production changes in this cumulative diff are original Stage-5 changes, not FIX1 changes.

```text
M	.env.example
M	app/admin_web/capabilities.py
M	app/admin_web/routes.py
M	app/admin_web/runtime.py
A	app/admin_web/static/portal_settings.js
M	app/admin_web/templates/admin/base.html
A	app/admin_web/templates/admin/settings_portal.html
M	app/capport/routes.py
M	app/config.py
A	app/portal_presentation.py
M	app/settings.py
M	app/settings_control/activation.py
M	app/settings_control/definitions.py
M	app/settings_control/repository.py
M	app/settings_control/resolver.py
M	app/settings_control/secret_recovery.py
M	app/settings_control/services.py
M	app/settings_control/validation.py
A	app/settings_control/value_validation.py
M	app/web/localization.py
M	app/web/portal_entry.py
M	app/web/templates/portal.html
M	app/web/web.py
M	docs/configuration.md
M	docs/deployment.md
M	docs/modules/admin-web.md
M	run.py
A	tests/admin_web/portal_settings_stage5_ui.cjs
A	tests/admin_web/test_portal_settings_stage5.py
A	tests/admin_web/test_portal_settings_stage5_frontend.py
M	tests/settings_control/test_controller_secret_repository.py
M	tests/settings_control/test_controller_secret_startup.py
M	tests/settings_control/test_controller_stage3.py
M	tests/settings_control/test_definitions.py
A	tests/settings_control/test_portal_stage5.py
M	tests/settings_control/test_repository.py
A	tests/settings_control/test_schema_v4_portal.py
M	tests/settings_control/test_secret_recovery.py
A	tests/settings_control/test_secret_recovery_v4.py
M	tests/test_admin_controller_settings.py
M	tests/test_auth_retry_frontend.py
M	tests/test_capport_discovery_frontend.py
A	tests/test_capport_portal_presentation_stage5.py
M	tests/test_capport_routes.py
M	tests/test_portal_design.py
M	tests/test_portal_entry.py
A	tests/web/test_portal_presentation_stage5.py
 .env.example                                       |  24 ++
 app/admin_web/capabilities.py                      |   3 +-
 app/admin_web/routes.py                            |  58 ++++-
 app/admin_web/runtime.py                           |   6 +
 app/admin_web/static/portal_settings.js            |  93 +++++++
 app/admin_web/templates/admin/base.html            |   9 +-
 app/admin_web/templates/admin/settings_portal.html |  14 ++
 app/capport/routes.py                              |  12 +-
 app/config.py                                      |  17 ++
 app/portal_presentation.py                         | 163 ++++++++++++
 app/settings.py                                    |  19 ++
 app/settings_control/activation.py                 |   2 +-
 app/settings_control/definitions.py                |  29 ++-
 app/settings_control/repository.py                 |  91 ++++---
 app/settings_control/resolver.py                   |   9 +-
 app/settings_control/secret_recovery.py            |   2 +-
 app/settings_control/services.py                   |  74 ++++--
 app/settings_control/validation.py                 |  25 +-
 app/settings_control/value_validation.py           |  29 +++
 app/web/localization.py                            |  19 +-
 app/web/portal_entry.py                            |   7 +-
 app/web/templates/portal.html                      |  33 ++-
 app/web/web.py                                     |   9 +-
 docs/configuration.md                              |  51 +++-
 docs/deployment.md                                 |  27 +-
 docs/modules/admin-web.md                          |  32 +++
 run.py                                             |   8 +-
 tests/admin_web/portal_settings_stage5_ui.cjs      |  67 +++++
 tests/admin_web/test_portal_settings_stage5.py     | 138 ++++++++++
 .../test_portal_settings_stage5_frontend.py        |  33 +++
 .../test_controller_secret_repository.py           |   2 +-
 .../test_controller_secret_startup.py              |   4 +-
 tests/settings_control/test_controller_stage3.py   |   2 +-
 tests/settings_control/test_definitions.py         |  21 +-
 tests/settings_control/test_portal_stage5.py       | 277 +++++++++++++++++++++
 tests/settings_control/test_repository.py          |   4 +-
 tests/settings_control/test_schema_v4_portal.py    | 109 ++++++++
 tests/settings_control/test_secret_recovery.py     |   2 +-
 tests/settings_control/test_secret_recovery_v4.py  |  89 +++++++
 tests/test_admin_controller_settings.py            |   8 +-
 tests/test_auth_retry_frontend.py                  |   2 +
 tests/test_capport_discovery_frontend.py           |   2 +
 tests/test_capport_portal_presentation_stage5.py   |  33 +++
 tests/test_capport_routes.py                       |   5 +-
 tests/test_portal_design.py                        |  36 ++-
 tests/test_portal_entry.py                         |   6 +
 tests/web/test_portal_presentation_stage5.py       | 145 +++++++++++
 47 files changed, 1726 insertions(+), 124 deletions(-)
```

HOLD for Tech Lead R2 review. Coder does not declare overall Task acceptance.

