# TASK-ADMIN-SETTINGS-04-FIX1 — local source-review handoff

Status: READY_FOR_TECH_LEAD_REVIEW. Local implementation and targeted evidence only; independent Tech Lead acceptance/publication remains pending.

## Required result

```ini
TASK=TASK-ADMIN-SETTINGS-04-FIX1
FIX1_BASE=698ba5b03887c90181cf78d63e156a7a965fe802
FIX1_COMMIT=87d2e7bb9a55749d427187600014042a872a447b
FIX1_PARENT=698ba5b03887c90181cf78d63e156a7a965fe802
FIX1_TREE=8fce7e75a1187d81c814395a80680871b5848aaf
WORKTREE=C:\CaptivPortal-Lab\coder-admin-settings-04
BRANCH=feature/admin-settings-04-controller-secret-management
WORKTREE_STATE=CLEAN
GIT_STATUS_PORCELAIN=<empty>

FIX1_CHANGED_FILES=15
FIX1_ADDITIONS=446
FIX1_DELETIONS=39
FIX1_PRODUCTION_FILES=5
FIX1_TEST_FILES=10

FULL_ORIGINAL_BASE_TO_FIX1_PATCH_PATH=C:\CaptivPortal-Lab\artifacts\TASK-ADMIN-SETTINGS-04-FIX1_BASE-to-CANDIDATE.patch
BASE_FOR_PATCH=430acb4f235a606f05acc78e7f983824e4448644
BASE_TREE=06e0edf54f37e4b9a3d4c3b8f3a1f37b181c3b3b
FULL_PATCH_BYTES=185342
FULL_PATCH_SHA256=e0d1104be06299242fb9bc14056e96af431a4ebe7e5714ca3ce65c6ef076fe16
PATCH_REVERSE_APPLY_CHECK=PASS
FULL_PATCH_FILES=43
FULL_PATCH_ADDITIONS=2139
FULL_PATCH_DELETIONS=98

P1_01_CONTROLLER_SECRET_DEFINITION=PASS
P1_02_SAFE_ADMIN_METADATA_BOUNDARY=PASS
P1_03_RECOVERY_EFFECTIVE_UID_IDENTITY=PASS
P1_04_STAGE3_FRONTEND_REGRESSION=PASS
P1_05_AESGCM_AVAILABILITY=PASS
TL_FIX1_B1_OPERATION_BOUND_RETRY_KEY=PASS

STAGE3_FRONTEND_EXECUTABLE_TEST=8 passed / 0 failed / 0 skipped
STAGE4_SECRET_UI_EXECUTABLE_TEST=23 passed / 0 failed / 0 skipped
TARGETED_TEST_RESULT=163 passed / 0 failed / 0 skipped
DIRECT_COMPATIBILITY_RESULT=214 passed / 0 failed / 0 skipped
TOTAL_TARGETED_FINAL_RESULT=377 passed / 0 failed / 0 skipped
COMPILEALL=PASS
NODE_CHECK=PASS
GIT_DIFF_CHECK=PASS
FULL_REPOSITORY_PYTEST=NOT_RUN_BY_CODER_PER_TASK
CENTRAL_LAB=NOT_RUN_BY_CODER
OPEN_P0=0 known to Coder; independent review pending
OPEN_P1=0 known to Coder; independent review pending

COMMIT=ONE_ADDITIONAL_LOCAL_FIX1_COMMIT
HISTORY_REWRITE=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO
```

## FIX1 changed-file list

Paths are relative to the isolated Settings-04 worktree above. These are the exact `git diff --name-status FIX1_PARENT FIX1_COMMIT` rows:

```text
M app/admin_web/controller_settings.py
M app/admin_web/static/controller_settings.js
M app/settings_control/bootstrap.py
M app/settings_control/controller_secret.py
M app/settings_control/secret_recovery.py
M tests/admin_web/controller_settings_stage3_ui.cjs
A tests/admin_web/controller_settings_stage4_ui.cjs
M tests/admin_web/test_controller_settings_stage4.py
A tests/admin_web/test_controller_settings_stage4_frontend.py
M tests/settings_control/test_controller_secret_crypto.py
M tests/settings_control/test_controller_secret_repository.py
M tests/settings_control/test_controller_secret_service.py
M tests/settings_control/test_controller_secret_startup.py
M tests/settings_control/test_controller_stage3.py
M tests/settings_control/test_secret_recovery.py
```

The two new files are disposable executable UI test support and its focused pytest wrapper. No new production module, dependency, schema/configuration/documentation change, generated database, bytecode, secret/key material or Lab output is in FIX1.

## Bounded repair mapping

| Review item | Implementation and focused proof |
| --- | --- |
| P1-01 | Frozen/slotted `ControllerSecretDefinitionV1` with non-init exact fields and one `CONTROLLER_SECRET_DEFINITION`. Key/scope/apply/target metadata is consumed by secret persistence/audit and Controller read projection. Definition stays outside the unchanged 15-item ordinary registry. Exact fields and immutable assignments are tested. |
| P1-02 | Bootstrap passes a distinct frozen `ControllerSecretMetadataService` to Admin reads, not the raw-bearing `ControllerSecretRepository`. It retains only Store/filesystem references plus deployment presence/source facts. No resolver, `_deployment`, decrypted value, `OmadaClientSecretResolution`, raw-bearing bound method or closure is retained. A disposable sentinel structural traversal checks instance fields/reachable object data before and after mutation. The actual Admin runtime wiring is asserted. Controller reads are tested with decrypt/raw repository reads forbidden. Startup/mutation alone retain fallback raw material. |
| P1-03 | Default recovery audit operator comes from `pwd.getpwuid(os.geteuid()).pw_name`, using a lazy Linux import. Explicit test injection remains supported. Spoofing USER/LOGNAME/LNAME/USERNAME does not affect the effective-UID account. The real recovery main path runs only with disposable injected Store/filesystem boundaries; stdout is exactly a safe generation receipt, stderr empty, and no key read/decrypt occurs. |
| P1-04 | Existing Stage-3 executable DOM harness now models Controller v3 and new secret nodes; all eight ordinary scenarios remain. A new executable harness runs the actual browser script for 23 secret/capability/cleanup/retry scenarios, using the actual password-input template attributes. |
| P1-05 | Shared Store/key validation initializes AESGCM using the derived encryption key after existing integrity/filesystem/key/HKDF checks. Initialization alone performs no encryption, decryption or network operation. Both import and constructor failures safely mark availability unavailable and reject mutation with a secret-free error. |
| TL-FIX1-B1 | An uncertain retry identity includes operation as well as key. Same-operation retry reuses the key; switching replace/clear, cancel, 412 or any definitive response discards it. Network failure still clears raw fields. Retrying replacement requires re-entry rather than submitting the cleared value. Executable tests cover both switch directions, same-operation replace/clear retry, cancel, 412 and definitive response after uncertainty. |

Executable Stage-4 scenarios: read-only, ordinary writer (ordinary save remains functional), independently authorized secret writer, two empty password inputs, mismatch/no POST, replace/clear confirmation and cancellation, explicit cancel cleanup, changed success and replay GET, clear success, 422/403/409/412/413/500/503 cleanup, 412 reload/new key, network uncertainty cleanup and re-entry, same-operation retry, operation change and definitive-response key discard. Confirmation/rendered text is checked against a disposable sentinel; console/storage/cookie persistence boundaries reject use. No live browser/product/production acceptance is claimed.

The former tests that deliberately faulted raw mutation/startup operations through `secret_metadata_service` now fault the explicitly raw-bearing mutation boundary instead. Assertions, atomicity, replay and fail-closed semantics are preserved, not weakened.

## Exact targeted commands and environment

Environment: existing WSL Ubuntu-22.04, Python 3.10.12, system cryptography 3.4.8; existing pytest dependencies supplied through the previously used path. Plugin autoload disabled, external bytecode prefix `/tmp/as04-fix1-pycache`. No package installation/upgrade/downgrade. Executable UI checks use WSL Node v24.20.0; direct syntax check uses Windows Node v24.19.0.

Executed from `C:\CaptivPortal-Lab\coder-admin-settings-04`:

```powershell
wsl -d Ubuntu-22.04 --cd /mnt/c/CaptivPortal-Lab/coder-admin-settings-04 --exec env 'PYTHONPATH=/mnt/c/Users/Zaur Navi/AppData/Local/Programs/Python/Python310/Lib/site-packages' PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPYCACHEPREFIX=/tmp/as04-fix1-pycache python3 -m pytest -q tests/settings_control/test_controller_secret_crypto.py tests/settings_control/test_controller_secret_repository.py tests/settings_control/test_controller_secret_service.py tests/settings_control/test_controller_secret_startup.py tests/settings_control/test_secret_recovery.py tests/admin_web/test_controller_settings_stage4.py tests/admin_web/test_global_capabilities_stage4.py tests/settings_control/test_validation.py tests/admin_web/test_controller_settings_stage3_frontend.py tests/admin_web/test_controller_settings_stage4_frontend.py --basetemp /tmp/as04-fix1-focused-final
```

Final focused result: **163 passed in 8.03s**, zero failures/skips. This includes Stage-3 frontend **8 PASS** and Stage-4 frontend **23 PASS**. An earlier same-scope run also passed; the final run additionally verifies strengthened sentinel reinspection after mutation and actual Admin-runtime metadata wiring.

```powershell
wsl -d Ubuntu-22.04 --cd /mnt/c/CaptivPortal-Lab/coder-admin-settings-04 --exec env 'PYTHONPATH=/mnt/c/Users/Zaur Navi/AppData/Local/Programs/Python/Python310/Lib/site-packages' PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPYCACHEPREFIX=/tmp/as04-fix1-pycache python3 -m pytest -q tests/settings_control/test_repository.py tests/settings_control/test_services.py tests/settings_control/test_bootstrap.py tests/settings_control/test_run_integration.py tests/settings_control/test_controller_stage3.py tests/admin_web/test_config.py tests/admin_web/test_settings_routes.py tests/admin_web/test_controller_settings_stage3.py tests/test_admin_controller_settings.py tests/test_omada_configuration.py --basetemp /tmp/as04-fix1-compatibility
```

Direct compatibility result: **214 passed in 24.54s**, zero failures/skips. No production file changed after these tests; the final focused run strengthened only two focused test assertions.

Static/identity checks:

```powershell
wsl -d Ubuntu-22.04 --cd /mnt/c/CaptivPortal-Lab/coder-admin-settings-04 --exec env PYTHONPYCACHEPREFIX=/tmp/as04-fix1-pycache python3 -m compileall -q app run.py
node --check app/admin_web/static/controller_settings.js
git diff --check
git diff --check HEAD^ HEAD
git diff --check 430acb4f235a606f05acc78e7f983824e4448644 HEAD
git apply --reverse --check C:/CaptivPortal-Lab/artifacts/TASK-ADMIN-SETTINGS-04-FIX1_BASE-to-CANDIDATE.patch
git status --porcelain
```

All passed. Staged tree equaled committed tree. Worktree remained clean after commit/patch checks. Reverse-check validates applicability without applying or mutating files.

## Scope, known limitations and next owner action

No schema-v3/AES frame/HKDF/HMAC/ETag/capability/activation/GC/filesystem/break-glass contract redesign. No live credential test, systemd authority, hot reconnect, provider ordering change or production action. Scope Extension 01 remains intact. The original candidate was not reset, amended, squashed or rebased; FIX1 is exactly one additional local commit.

The 18 Tech-Lead-confirmed baseline failures are not repaired or rerun here. Full/broad regression and independent review remain Tech Lead responsibility. Coder does not declare this new candidate accepted or production-ready.

Read-only preservation check of parallel NI worktree:

```ini
NI_WORKTREE=C:\CaptivPortal-Lab\coder-dti-ni-01
NI_HEAD=f3a69e90fd48381889bcd32d5158fbbb359f446d
NI_TREE=0a0ec87cd26d63b321ce62446178f4d8ab46cc02
NI_STATUS_PORCELAIN=<empty>
NI_WORKTREE_UNCHANGED=YES
```

Agent execution summary: Codex desktop, bounded implementation mode in the preserved Settings-04 worktree; five production files and ten test/support files changed; two new executable UI test/support files; targeted local checks only; one additional immutable local commit; full original-base patch exported; no subagents, remote publication, full gate, production access, deployment, activation or service restart. No known remaining implementation blocker; independent Tech Lead source/broad review pending.

HOLD for Tech Lead review.
