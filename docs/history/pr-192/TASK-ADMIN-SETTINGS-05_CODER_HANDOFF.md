# TASK-ADMIN-SETTINGS-05 — Coder implementation handoff

Status: local implementation ready for Tech Lead source review. This is NOT an independent acceptance verdict or publication authorization.

## Required result

```text
TASK = TASK-ADMIN-SETTINGS-05
BASE = c05d0fccfb1c0ed67a2e3fbd5d6f58ee2b2d2ed9
BASE_TREE = 59df8aa855fe094e173db611fbbdf5714c229b86
BRANCH = feature/admin-settings-05-portal-guest-experience
WORKTREE_PATH = C:\CaptivPortal-Lab\coder-admin-settings-05
HEAD = 5f1766d50fdcb1a2e09eb7dc13fd0df8e5847a50
PARENT = c05d0fccfb1c0ed67a2e3fbd5d6f58ee2b2d2ed9
TREE = 85a27d2c9e3f3ad5116d68427f654a8142e156b9
SUBJECT = ADMIN-SETTINGS-05: add guest portal presentation settings
WORKTREE = CLEAN
CHANGED_FILE_COUNT = 44
ADDITIONS = 1676
DELETIONS = 109
FOCUSED_TESTS = 300 passed / 0 failed / 0 skipped
DIRECT_SETTINGS_COMPATIBILITY = 169 passed / 0 failed / 0 skipped
NATIVE_CAPPORT_PORTAL_ENTRY = 37 passed / 0 failed / 0 skipped
FINAL_RECOVERY_RECHECK = 9 passed / 0 failed / 0 skipped
STATIC_CHECKS = PASS
SCHEMA_V4 = PASS
BREAK_GLASS_V4 = PASS
PORTAL_API = PASS
PORTAL_RENDERING = PASS
CAPPORT_JSON_REGRESSION = PASS
STAGE4_REGRESSION = PASS
CONTRACT_CLARIFICATION_C1 = IMPLEMENTED
OPEN_P0 = 0 observed in task-scoped checks
OPEN_P1 = 0 observed in task-scoped checks
DEVIATIONS = NONE
ARCHITECTURE_AMBIGUITY = NONE
PATCH_PATH = C:\CaptivPortal-Lab\artifacts\TASK-ADMIN-SETTINGS-05_BASE-to-CANDIDATE.patch
PATCH_BYTES = 162745
PATCH_SHA256 = f297b326080a056c8780c6ddb537a219e10b2662e9c3cadffbc1776596f47169
PATCH_REVERSE_APPLY_CHECK = PASS
COMMIT = ONE LOCAL COMMIT
PUSH = NO
PR = NO
MERGE = NO
DEPLOY = NO
SERVICE_RESTART = NO
PRODUCTION_TEST = NO
PRODUCTION_ACTION = NO
FULL_REPOSITORY_TESTS = NO
CENTRAL_LAB = NOT RUN / PENDING TECH LEAD
```

## Implementation summary and contract mapping

- Exactly fourteen writable GLOBAL public string definitions were added to the existing registry; twelve General integers and three non-secret Controller strings remain unchanged. Defaults have one immutable code authority. Existing config → settings flow exposes the fourteen canonical environment names and lowercase runtime keys.
- Text validation preserves accepted bytes: NFC, code-point bounds, edge-whitespace/control/bidi rejection, single-line branding and maximum four LF description lines. HTML-like plain text remains valid and is escaped. Optional contacts allow exactly empty; phone/email hrefs are server-derived and social URLs use exact frozen HTTPS authority/path/query rules.
- SettingsStore schema v4 uses the existing nine tables. v3→v4 validates the accepted physical schema/history/secret references and replaces ONLY mutation-audit and idempotency leaf tables in one initialization transaction. IDs, values, JSON response bytes, fingerprints, timestamps, secret versions/bindings and configured/effective/activation state are preserved. v1/v2 follow the existing chain through v3. Migration writes no Portal default overrides. An impossible preexisting Portal override in v3 is rejected.
- Generation 0 remains `system / settings_bootstrap`, with no overrides/audit/receipts. Resolver precedence is persisted override → explicit environment → repository default. Clear removes ownership rather than writing a default.
- Portal Save uses `validate_portal_candidate(snapshot)`: existing General/Admin checks, canonical non-secret Controller prerequisites and all fourteen Portal values. C1 prohibits secret resolve/keys/master-key/decrypt I/O; no alternative/dummy/startup secret is supplied. `carry_secret=True` inherits the parent's binding unchanged. General/Controller full secret validation and Stage-4 mutation/startup boundaries are preserved.
- Changed/no-op/replay use the common head, CAS, immutable audit and domain-scoped receipts. Portal success is a closed state-only response with no value echo. Identical replay precedes CAS; conflict and stale generation remain 409/412. Invalid batches create no generation/audit/success receipt.
- Recovery uses the current-v4 existing-only opener; it neither creates, initializes, migrates nor repairs a DB. Exact schema/triggers, integrity/FK, generation-0/target/history and secret references are validated. Existing filesystem policy remains mandatory. Local clear needs no master key/decrypt, copies all ordinary overrides including Portal, and does not advance effective generation. No service-control authority was added.
- GLOBAL Portal page/read/write use the common Settings services and explicit non-default Portal capabilities. POST requires both read and write. Strict JSON rejects duplicate members, non-finite constants, wrong types/domains/fields. Existing bounded body, CSRF, quoted ETag and UUIDv4 requirements remain. No fake Site context or navigation-time Store query is introduced.
- Dedicated `portal_settings.js` uses server metadata and safe DOM text, fourteen controls, description textareas, persisted-only reset, untrimmed batched save and explicit pending/no-op/412/422 handling. No preview/restart/browser-persistence/credential controller was added; existing admin.js was not changed.
- One immutable startup projection overlays only title/greeting/description on all three complete localization catalogs. Normal Portal, CAPPORT normal/discovery/error HTML share the same projection; request-time Settings/environment access is absent. Support links are conditional; all empty hides the complete support section. CAPPORT JSON, Auth session results, retry/counter localization and `/success` remain non-consumers/unchanged contracts.
- Actual Portal composition errors during create_app record `portal_configuration_adoption_failed`, do not advance effective generation and abort serving. Unrelated composition/operational failures are not reclassified as Portal adoption failures. Existing adopted guest projection does not depend on Store availability.
- Four deployment/Admin/configuration documentation files describe schema/recovery compatibility, public values, default-off permissions and external restart/rollback authority; no deploy/service action was performed.

## Exact changed files — git diff --name-status BASE HEAD

```text
M .env.example
M app/admin_web/capabilities.py
M app/admin_web/routes.py
M app/admin_web/runtime.py
A app/admin_web/static/portal_settings.js
M app/admin_web/templates/admin/base.html
A app/admin_web/templates/admin/settings_portal.html
M app/capport/routes.py
M app/config.py
A app/portal_presentation.py
M app/settings.py
M app/settings_control/activation.py
M app/settings_control/definitions.py
M app/settings_control/repository.py
M app/settings_control/resolver.py
M app/settings_control/secret_recovery.py
M app/settings_control/services.py
M app/settings_control/validation.py
A app/settings_control/value_validation.py
M app/web/localization.py
M app/web/portal_entry.py
M app/web/templates/portal.html
M app/web/web.py
M docs/configuration.md
M docs/deployment.md
M docs/modules/admin-web.md
M run.py
A tests/admin_web/portal_settings_stage5_ui.cjs
A tests/admin_web/test_portal_settings_stage5.py
A tests/admin_web/test_portal_settings_stage5_frontend.py
M tests/settings_control/test_controller_secret_repository.py
M tests/settings_control/test_controller_secret_startup.py
M tests/settings_control/test_controller_stage3.py
A tests/settings_control/test_portal_stage5.py
M tests/settings_control/test_repository.py
A tests/settings_control/test_schema_v4_portal.py
M tests/settings_control/test_secret_recovery.py
A tests/settings_control/test_secret_recovery_v4.py
M tests/test_auth_retry_frontend.py
M tests/test_capport_discovery_frontend.py
A tests/test_capport_portal_presentation_stage5.py
M tests/test_capport_routes.py
M tests/test_portal_entry.py
A tests/web/test_portal_presentation_stage5.py
```

The four new production files are exactly the authorized files. Existing test edits change only version/registry expectations, the renamed recovery opener, and injection of the required safe startup presentation into direct HTML/handler fixtures. No unrelated production path was edited.

## Exact diff stat

```text
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
 tests/settings_control/test_portal_stage5.py       | 277 +++++++++++++++++++++
 tests/settings_control/test_repository.py          |   4 +-
 tests/settings_control/test_schema_v4_portal.py    | 109 ++++++++
 tests/settings_control/test_secret_recovery.py     |   2 +-
 tests/settings_control/test_secret_recovery_v4.py  |  89 +++++++
 tests/test_auth_retry_frontend.py                  |   2 +
 tests/test_capport_discovery_frontend.py           |   2 +
 tests/test_capport_portal_presentation_stage5.py   |  33 +++
 tests/test_capport_routes.py                       |   5 +-
 tests/test_portal_entry.py                         |   6 +
 tests/web/test_portal_presentation_stage5.py       | 145 +++++++++++
 44 files changed, 1676 insertions(+), 109 deletions(-)
```

## Verification — exact commands and final results

Working directory for all commands: `C:\CaptivPortal-Lab\coder-admin-settings-05`.

Linux commands used the existing Ubuntu-22.04 WSL environment, Python 3.10.12 and cryptography 3.4.8, with the already available pure-Python test dependencies, plugin autoload disabled and all pycache/temp outputs outside the repository. No dependency installation was performed.

### Mandatory focused set — 300 passed, 0 failed, 0 skipped

```powershell
wsl -d Ubuntu-22.04 --cd /mnt/c/CaptivPortal-Lab/coder-admin-settings-05 --exec env 'PYTHONPATH=/mnt/c/Users/Zaur Navi/AppData/Local/Programs/Python/Python310/Lib/site-packages' PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPYCACHEPREFIX=/tmp/as05-pycache python3 -m pytest -q --tb=short tests/settings_control/test_portal_stage5.py tests/settings_control/test_schema_v4_portal.py tests/settings_control/test_secret_recovery_v4.py tests/settings_control/test_secret_recovery.py tests/settings_control/test_repository.py tests/settings_control/test_controller_stage3.py tests/settings_control/test_controller_secret_repository.py tests/admin_web/test_portal_settings_stage5.py tests/admin_web/test_portal_settings_stage5_frontend.py tests/admin_web/test_settings_routes.py tests/admin_web/test_global_capabilities_stage4.py tests/web/test_portal_presentation_stage5.py tests/test_capport_portal_presentation_stage5.py tests/test_capport_discovery_frontend.py tests/test_auth_retry_frontend.py --basetemp /tmp/as05-required-ready
```

All exact listed existing test files were present. No replacement command was needed.

### Directly affected Settings/Controller compatibility — 169 passed, 0 failed, 0 skipped

```powershell
wsl -d Ubuntu-22.04 --cd /mnt/c/CaptivPortal-Lab/coder-admin-settings-05 --exec env 'PYTHONPATH=/mnt/c/Users/Zaur Navi/AppData/Local/Programs/Python/Python310/Lib/site-packages' PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPYCACHEPREFIX=/tmp/as05-pycache python3 -m pytest -q --tb=short tests/settings_control/test_controller_secret_service.py tests/settings_control/test_controller_secret_startup.py tests/settings_control/test_controller_secret_crypto.py tests/settings_control/test_run_integration.py tests/admin_web/test_controller_settings_stage3.py tests/admin_web/test_controller_settings_stage3_frontend.py tests/admin_web/test_controller_settings_stage4.py tests/admin_web/test_controller_settings_stage4_frontend.py tests/admin_web/test_settings_ui.py --basetemp /tmp/as05-direct-final
```

### Direct CAPPORT/PortalEntry compatibility — native Windows, 37 passed, 0 failed, 0 skipped

```powershell
$env:PYTHONPATH='C:\CaptivPortal-Lab\coder-admin-settings-05;C:\Users\Zaur Navi\AppData\Local\Programs\Python\Python310\Lib\site-packages'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONPYCACHEPREFIX='C:\CaptivPortal-Lab\artifacts\as05-native-pycache'
& 'C:\Users\Zaur Navi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -q --tb=short tests/test_capport_routes.py tests/test_portal_entry.py --basetemp C:\CaptivPortal-Lab\artifacts\as05-native-direct
```

Bundled native Python 3.12.14 / cryptography 50.0.1 was used for this Windows-bound fixture set. An earlier Linux compatibility attempt failed two unchanged probe fixtures because `C:/explicit/probe.jsonl` is not an absolute Linux path. Their original paths and assertions were preserved, and the complete two-file group passed natively. Other implementation-stage failures in new tests were corrected to exact existing HTTP/schema semantics before the final green runs. No skip/xfail/deselection or production semantic workaround was introduced.

### Last recovery-fixture recheck — 9 passed, 0 failed, 0 skipped

After strengthening the generation-0 corruption fixture to restore its immutable trigger (so rejection proves the root invariant rather than a missing trigger), the final exact test file was rechecked:

```powershell
wsl -d Ubuntu-22.04 --cd /mnt/c/CaptivPortal-Lab/coder-admin-settings-05 --exec env 'PYTHONPATH=/mnt/c/Users/Zaur Navi/AppData/Local/Programs/Python/Python310/Lib/site-packages' PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPYCACHEPREFIX=/tmp/as05-pycache python3 -m pytest -q --tb=short tests/settings_control/test_secret_recovery_v4.py --basetemp /tmp/as05-recovery-final
```

### Static and artifact checks — PASS

```powershell
wsl -d Ubuntu-22.04 --cd /mnt/c/CaptivPortal-Lab/coder-admin-settings-05 --exec env PYTHONPYCACHEPREFIX=/tmp/as05-static-pycache python3 -m compileall -q app/portal_presentation.py app/settings_control app/web app/capport app/admin_web run.py
node --check app/admin_web/static/portal_settings.js
git diff --check
git diff --cached --check
git diff --check HEAD^ HEAD
git apply --reverse --check C:/CaptivPortal-Lab/artifacts/TASK-ADMIN-SETTINGS-05_BASE-to-CANDIDATE.patch
git status --porcelain
```

All checks exited 0; final porcelain output was empty. Exact staged tree was verified before the single commit; HEAD's parent and tree were verified after it. The patch is generated with `git diff --binary --full-index BASE HEAD`, including all new files.

## Acceptance matrix / limitations

| Gate | Environment / candidate | Coder result |
| --- | --- | --- |
| schema v4 and atomic migration | disposable SQLite / final source | PASS |
| Stage-4 v4 recovery | disposable filesystem and DB / final source | PASS |
| Portal API and C1 secret separation | disposable Flask/Settings stack / final source | PASS |
| safe guest rendering and CAPPORT JSON | offline Flask / final source | PASS |
| executable Portal frontend | disposable Node DOM/fetch / final source | PASS |
| direct Controller/Stage-4/startup compatibility | offline WSL / final source | PASS |
| Windows-bound CAPPORT/PortalEntry fixtures | native Windows / final source | PASS |
| static checks and patch reverse-check | exact committed tree 85a27d2c9e3f3ad5116d68427f654a8142e156b9 | PASS |
| independent source/acceptance review | Tech Lead / exact committed candidate | PENDING |
| broader/full regression | Tech Lead responsibility | NOT RUN BY CODER |
| Central Lab / production tests | not authorized to Coder | NOT RUN |
| publication/deployment | separate authorization required | HOLD |

No real master key/production DB/network service was used. No production/browser visual acceptance or full-repository acceptance is claimed. Other worktrees were not modified. No additional dependency, worker, systemd, secret, Omada API, CAPPORT configuration, Auth, redirect, Site-scoped or device-fingerprint semantics were introduced.

PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO
